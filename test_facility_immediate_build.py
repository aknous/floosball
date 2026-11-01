"""Fan-funded facility builds and ONE UPGRADE PER FACILITY PER YEAR.

When fans fully fund a facility's next level during the season it builds at once,
and its perks go live from the team's next game. A year runs from one offseason
payment run to the next (owner, 2026-10-22):
  - a facility fans built mid-season is skipped by the next payment run, and its
    upkeep is waived there (it was under construction the year it completed);
  - a facility the payment run upgraded cannot be built again by fans until after
    the next run; their money waits on the bar;
  - after this season's run has happened, every fan build waits for season start,
    where `buildPendingProjects` builds it.

Run: python test_facility_immediate_build.py  (throwaway temp DB)
"""
import os, sys, tempfile, shutil
sys.path.insert(0, os.getcwd())
_tmp = tempfile.mkdtemp(prefix="floo_fac_")
os.environ["DATABASE_DIR"] = _tmp

from database.connection import init_db, get_session
init_db()
import managers.facilitiesManager as FM
from database.models import TeamFacility, FacilityProject, TeamTreasury, AppSetting
from constants import FACILITY_CATALOG

failures = []
def expect(label, cond):
    print(f"  [{'OK' if cond else 'FAIL'}] {label}")
    if not cond:
        failures.append(label)

SU = 1000
TEAM = 99
KEYS = list(FACILITY_CATALOG)

def setup(s, levels, treasury=0):
    for k in KEYS:
        s.add(TeamFacility(team_id=TEAM, facility_key=k, level=levels.get(k, 0), upkeep_funded=0))
    s.add(TeamTreasury(team_id=TEAM, balance=treasury))
    s.flush()
    FM.ensureOpenProjects(s, TEAM, levels, 5)
    s.commit()

def proj(s, key):
    return s.query(FacilityProject).filter_by(team_id=TEAM, facility_key=key, status='open').first()

def level(s, key):
    return s.query(TeamFacility).filter_by(team_id=TEAM, facility_key=key).first().level

def fundFully(s, key):
    p = proj(s, key)
    p.funded = FM.projectCostFloobits(p.cost_shares, SU)
    return p

def markRun(s, value):
    row = s.query(AppSetting).filter_by(key=FM.PAYMENT_RUN_KEY).first()
    if row:
        row.value = value
    else:
        s.add(AppSetting(key=FM.PAYMENT_RUN_KEY, value=value))
    s.commit()

team = type('T', (), {'id': TEAM, 'name': 'Test', 'facilities': {}})()

print("1. every facility below the top level has exactly one open project")
s = get_session()
setup(s, {'training': 1, 'stadium': 5})
openKeys = sorted(p.facility_key for p in s.query(FacilityProject).filter_by(team_id=TEAM, status='open'))
expect("all but the maxed facility have an open project",
       openKeys == sorted(k for k in KEYS if k != 'stadium'))
expect("the project targets the next level", proj(s, 'training').target_level == 2)

print("2. a fan-funded project builds immediately, and the next level opens")
p = fundFully(s, 'training')
expect("not blocked mid-season 5", not FM.midSeasonBlocked(s, TEAM, 'training', 5))
newLevel = FM.buildProjectNow(s, TEAM, p, team, season=5)
s.commit()
expect("facility jumps to the target level", level(s, 'training') == 2 and newLevel == 2)
expect("project marked built by fans in season 5",
       p.status == 'built' and p.built_season == 5 and p.built_by == 'fans')
expect("in-memory team.facilities reflects the new level", team.facilities.get('training') == 2)
expect("the next level (3) is open", proj(s, 'training').target_level == 3)
expect("fans cannot build it again this season", FM.midSeasonBlocked(s, TEAM, 'training', 5))

print("3. the payment run skips a facility fans built this year and waives its upkeep")
fundFully(s, 'training')                       # fans fund level 3 too; it must wait
markRun(s, '5')
FM.applyPaymentRun(s, [team], 5, SU)
s.commit()
expect("training stays at 2 (no second upgrade this year), upkeep waived so no decay",
       level(s, 'training') == 2)
expect("its funded level-3 bar is kept", proj(s, 'training').funded > 0)

print("4. after this season's run, every fan build waits for season start")
markRun(s, 'done:5')
expect("blocked for the rest of offseason 5", FM.midSeasonBlocked(s, TEAM, 'recovery', 5))
expect("UI reads it as building next season",
       FM.projectBuildTiming(s, TEAM, 'recovery', 5) == 'next_season')

print("5. season start builds what fans funded while it was blocked")
built = FM.buildPendingProjects(s, [team], 6, SU)
s.commit()
expect("training builds to 3 at season 6 start", level(s, 'training') == 3
       and ('Test', 'training', 3) in built)

print("6. a facility the payment run upgraded cannot be fan-built until the next run")
s.query(TeamTreasury).filter_by(team_id=TEAM).first().balance = 10_000_000
markRun(s, '6')
FM.applyPaymentRun(s, [team], 6, SU)
s.commit()
runBuilt = {p.facility_key for p in s.query(FacilityProject).filter_by(
    team_id=TEAM, status='built', built_by='run', built_season=6)}
# The stadium (level 5) decayed in season 5's run, whose treasury was empty, so it is
# rebuilt here too.
expect("the run built every facility not blocked this year (training was fan-built in 6)",
       runBuilt == {k for k in KEYS if k != 'training'})
expect("the run did not touch training (fans built it this year)", level(s, 'training') == 3)
markRun(s, 'done:6')
expect("a run-built facility is blocked mid-season 7",
       FM.midSeasonBlocked(s, TEAM, 'recovery', 7)
       and FM.projectBuildTiming(s, TEAM, 'recovery', 7) == 'payment_run')
expect("training (not run-built) is open to fans in season 7",
       not FM.midSeasonBlocked(s, TEAM, 'training', 7)
       and FM.projectBuildTiming(s, TEAM, 'training', 7) == 'now')

print("7. upkeep resumes the year after a fan build")
s.query(TeamTreasury).filter_by(team_id=TEAM).first().balance = 0
markRun(s, '7')
before = level(s, 'training')
FM.applyPaymentRun(s, [team], 7, SU)
s.commit()
expect("with an empty treasury, training's upkeep is now charged and it decays",
       level(s, 'training') == before - 1)

s.close()
shutil.rmtree(_tmp, ignore_errors=True)
print()
if failures:
    print(f"FAILED ({len(failures)}): " + "; ".join(failures))
    raise SystemExit(1)
print("ALL FACILITY IMMEDIATE-BUILD TESTS PASS")
