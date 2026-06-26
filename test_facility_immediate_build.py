"""Mid-season immediate facility build + upkeep waiver.

When a facility project is fully funded MID-SEASON it builds immediately — the
facility level jumps and its perks go live from the team's next game, instead of
waiting for the season-end resolution. A facility built this way also waives
upkeep for the rest of that season (it was under construction the year it
completed), exactly like a facility with an open project.

Run: python test_facility_immediate_build.py  (throwaway temp DB)
"""
import os, sys, tempfile, shutil
sys.path.insert(0, os.getcwd())
_tmp = tempfile.mkdtemp(prefix="floo_fac_")
os.environ["DATABASE_DIR"] = _tmp

from database.connection import init_db, get_session
init_db()
import managers.facilitiesManager as FM
from database.models import TeamFacility, FacilityProject, TeamTreasury
from constants import FACILITY_UPGRADE_COST_SHARES

failures = []
def expect(label, cond):
    print(f"  [{'OK' if cond else 'FAIL'}] {label}")
    if not cond:
        failures.append(label)

# 1. PURE resolver: upkeep + decay waived for a facility built mid-season this year
print("1. resolveSeasonEnd waives upkeep & decay for a facility built mid-season this year")
fac = [{'key': 'training', 'level': 2, 'upkeep_funded': 0}]
decay = FM.resolveSeasonEnd(fac, [], 0, 1000, 5)                                   # empty treasury
waived = FM.resolveSeasonEnd(fac, [], 0, 1000, 5, builtThisSeasonKeys={'training'})
dT = {f['key']: f for f in decay['facilities']}['training']
wT = {f['key']: f for f in waived['facilities']}['training']
expect("without the waiver, an unpaid Lv2 facility decays", dT['level'] < 2)
expect("with the waiver, the built facility keeps its level (no decay)", wT['level'] == 2)
expect("with the waiver, upkeep cost reads 0 this season", wT['upkeepCost'] == 0)

# 2. buildProjectNow applies the upgrade immediately (DB)
print("2. buildProjectNow jumps the facility level the moment the bar fills")
s = get_session()
s.add(TeamFacility(team_id=99, facility_key='training', level=1, upkeep_funded=0))
proj = FacilityProject(team_id=99, facility_key='training', kind='upgrade', target_level=2,
                       cost_shares=FACILITY_UPGRADE_COST_SHARES[2], funded=100,
                       opened_season=5, status='open')
s.add(proj); s.commit()
teamObj = type('T', (), {'facilities': {'training': 1}})()
newLevel = FM.buildProjectNow(s, 99, proj, teamObj, season=5)
s.commit()
fac99 = s.query(TeamFacility).filter_by(team_id=99, facility_key='training').first()
expect("facility level jumps to the target immediately", fac99.level == 2)
expect("buildProjectNow returns the new level", newLevel == 2)
expect("project marked built with built_season set", proj.status == 'built' and proj.built_season == 5)
expect("in-memory team.facilities reflects the new level (perks live next game)",
       teamObj.facilities.get('training') == 2)

# 3. Season-end: no upkeep the build season, upkeep resumes the next (DB)
print("3. season-end waives upkeep the build season, charges it the following season")
s.add(TeamTreasury(team_id=99, balance=0)); s.commit()   # empty treasury -> any upkeep charge forces decay
team99 = type('T', (), {'id': 99, 'name': 'Test', 'facilities': {}})()
FM.applySeasonEnd(s, [team99], season=5, shareUnit=1000); s.commit()
after5 = s.query(TeamFacility).filter_by(team_id=99, facility_key='training').first()
expect("build season (5): facility does NOT decay (upkeep waived)", after5.level == 2)
FM.applySeasonEnd(s, [team99], season=6, shareUnit=1000); s.commit()
after6 = s.query(TeamFacility).filter_by(team_id=99, facility_key='training').first()
expect("following season (6): upkeep applies — empty treasury now decays it", after6.level < 2)

shutil.rmtree(_tmp, ignore_errors=True)
print()
if failures:
    print(f"FAILED ({len(failures)}): " + "; ".join(failures))
    raise SystemExit(1)
print("ALL FACILITY IMMEDIATE-BUILD TESTS PASS")
