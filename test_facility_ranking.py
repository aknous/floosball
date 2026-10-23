"""Ranked facility ballots and the payment run's build order (owner, 2026-10-22).

Fans rank all five facilities; the team's order is a points count over its current
fans' ballots (first choice n points, last 1), ties to the facility the team is
weakest in. The offseason payment run pays upkeep, then funds projects in that
order, at most one level per facility, until the money runs out.

Run: python test_facility_ranking.py  (throwaway temp DB)
"""
import os, sys, tempfile, shutil, json
sys.path.insert(0, os.getcwd())
_tmp = tempfile.mkdtemp(prefix="floo_rank_")
os.environ["DATABASE_DIR"] = _tmp

from database.connection import init_db, get_session
init_db()
import managers.facilitiesManager as FM
from database.models import (TeamFacility, FacilityProject, FacilityRanking, FacilityVote,
                             User, AppSetting)
from constants import FACILITY_CATALOG, FACILITY_UPGRADE_COST_SHARES

failures = []
def expect(label, cond):
    print(f"  [{'OK' if cond else 'FAIL'}] {label}")
    if not cond:
        failures.append(label)

KEYS = list(FACILITY_CATALOG)
SU = 1000.0

print("1. the combined order")
levels = {k: 2 for k in KEYS}
levels[KEYS[3]] = 0
expect("no ballots: weakest facility first, then catalog order",
       FM.combinedOrder(levels, []) == [KEYS[3]] + [k for k in KEYS if k != KEYS[3]])
mine = list(reversed(KEYS))
expect("one fan: the team follows that fan's list", FM.combinedOrder(levels, [mine]) == mine)
a = [KEYS[0], KEYS[1], KEYS[2], KEYS[3], KEYS[4]]
b = [KEYS[1], KEYS[0], KEYS[2], KEYS[3], KEYS[4]]
c = [KEYS[1], KEYS[2], KEYS[0], KEYS[3], KEYS[4]]
expect("points count: two first choices beat one", FM.combinedOrder(levels, [a, b, c])[0] == KEYS[1])
expect("a tie goes to the facility the team is weakest in",
       FM.combinedOrder({KEYS[0]: 3, KEYS[1]: 1}, [a, b])[0] == KEYS[1])
expect("a partial or stale ballot is completed in the fallback order",
       FM.normalizeBallot(['nonsense', KEYS[4], KEYS[4]], levels)[:2] == [KEYS[4], KEYS[3]])

print("2. the pure payment run")
def fac(lv):
    return [{'key': k, 'level': lv.get(k, 0), 'upkeep_funded': 0} for k in KEYS]
def projects(lv, funded=None):
    return [{'id': i, 'facility_key': k, 'target_level': lv.get(k, 0) + 1,
             'cost_shares': FACILITY_UPGRADE_COST_SHARES[lv.get(k, 0) + 1],
             'funded': (funded or {}).get(k, 0)} for i, k in enumerate(KEYS)]
lv0 = {k: 0 for k in KEYS}
cost1 = FM.projectCostFloobits(FACILITY_UPGRADE_COST_SHARES[1], SU)
order = [KEYS[2], KEYS[0], KEYS[4], KEYS[1], KEYS[3]]
res = FM.resolvePaymentRun(fac(lv0), projects(lv0), cost1 * 2 + 1, SU, order=order)
builtKeys = [p['facility_key'] for p in res['projects'] if p['built']]
expect("funds facilities in ranked order and moves down the list",
       builtKeys == [KEYS[2], KEYS[0]])
third = next(p for p in res['projects'] if p['facility_key'] == KEYS[4])
expect("the next one gets what is left, carried on its bar", third['funded'] == 1 and res['leftover'] == 0)
expect("one level per facility, even with money to spare",
       max(f['level'] for f in FM.resolvePaymentRun(fac(lv0), projects(lv0), 10**9, SU)['facilities']) == 1)
res = FM.resolvePaymentRun(fac(lv0), projects(lv0, {KEYS[3]: cost1}), 0, SU, order=order)
expect("a bar fans already funded builds with an empty pot",
       [p['facility_key'] for p in res['projects'] if p['built']] == [KEYS[3]])
res = FM.resolvePaymentRun(fac(lv0), projects(lv0), 10**9, SU, blockedKeys={KEYS[0]})
expect("a blocked facility is not built", not any(p['built'] and p['facility_key'] == KEYS[0]
                                                  for p in res['projects']))
lv3 = {k: 3 for k in KEYS}
pr = projects(lv3, {KEYS[0]: 10**6})
# KEYS[0] last, so the refund is not spent on the projects ahead of it.
res = FM.resolvePaymentRun(fac(lv3), pr, 0, SU, order=KEYS[1:] + KEYS[:1])
p0 = next(p for p in res['projects'] if p['facility_key'] == KEYS[0])
expect("a facility that decayed rebuilds the level it lost (3), not the one above (4)",
       p0['target_level'] == 3 and p0['built'])
expect("and the funding beyond that cheaper level goes back to the treasury",
       res['leftover'] == 10**6 - FM.projectCostFloobits(FACILITY_UPGRADE_COST_SHARES[3], SU))

print("3. ballots in the database")
s = get_session()
users = []
for i, fav in enumerate([1, 1, 2]):
    u = User(clerk_id=f"c{i}", email=f"u{i}@x.test", username=f"user{i}", favorite_team_id=fav)
    s.add(u); s.flush(); users.append(u.id)
FM.setRanking(s, 1, users[0], mine)
FM.setRanking(s, 1, users[2], a)          # user 2 now favors team 2
s.commit()
expect("only the team's current fans count", FM.teamBallots(s, 1) == [mine])
try:
    FM.setRanking(s, 1, users[0], KEYS[:3]); bad = False
except ValueError:
    bad = True
expect("a ranking must list every facility once", bad)
expect("getRanking reads it back", FM.getRanking(s, 1, users[0]) == mine)

print("4. the one-shot backfill seeds a ranking from a fan's last vote")
from database.connection import _backfillFacilityRankings, _FACILITY_RANKINGS_MARKER
s.query(AppSetting).filter_by(key=_FACILITY_RANKINGS_MARKER).delete()
s.add(FacilityVote(team_id=1, user_id=users[1], facility_key=KEYS[2], season=3))
s.add(FacilityVote(team_id=1, user_id=users[1], facility_key=KEYS[4], season=4))
s.commit(); s.close()
_backfillFacilityRankings()
s = get_session()
seeded = FM.getRanking(s, 1, users[1])
expect("the latest vote becomes the first choice", seeded and seeded[0] == KEYS[4] and len(seeded) == len(KEYS))
expect("an existing ranking is not overwritten", FM.getRanking(s, 1, users[0]) == mine)
s.close()

shutil.rmtree(_tmp, ignore_errors=True)
print()
if failures:
    print(f"FAILED ({len(failures)}): " + "; ".join(failures))
    raise SystemExit(1)
print("ALL FACILITY RANKING TESTS PASS")
