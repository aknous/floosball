"""Gate revenue and the league donation match (docs/TREASURY_PAYROLL_PLAN.md §4).

The league pays each team's Treasury every regular-season week for its active fans,
weighted by how many of the site's games each played that week (manual pick-em picks,
a fielded lineup, Showcase cards; tops out at two), concave in the total, scaled by the
Stadium. And it matches each fan's donations up to a per-season cap.

Run: python test_gate_revenue.py  (throwaway temp DB)
"""
import os, sys, tempfile, shutil, datetime
sys.path.insert(0, os.getcwd())
_tmp = tempfile.mkdtemp(prefix="floo_gate_")
os.environ["DATABASE_DIR"] = _tmp

from database.connection import init_db, get_session
init_db()
from managers import gateRevenue as G, facilitiesManager as FM
from database.models import (User, TeamFacility, TeamTreasury, TreasuryIncome, PickEmPick,
                             WeeklyCardBonus, ShowcaseSlot)
from constants import (GATE_PARTICIPATION_BOOST, GATE_FAN_EXPONENT, DONATION_MATCH_RATE,
                       DONATION_MATCH_CAP_SHARES)

failures = []
def expect(label, cond):
    print(f"  [{'OK' if cond else 'FAIL'}] {label}")
    if not cond:
        failures.append(label)

SU = 5000.0

print("1. the pure pieces")
expect("an active fan weighs 1.0; one game adds the first boost; it tops out at two",
       (G.fanWeight(0), G.fanWeight(1), G.fanWeight(2), G.fanWeight(3))
       == (1.0, 1 + GATE_PARTICIPATION_BOOST[1], 1 + GATE_PARTICIPATION_BOOST[2], 1 + GATE_PARTICIPATION_BOOST[2]))
one, two = G.gateAmount([1.0], 0, SU), G.gateAmount([1.0, 1.0], 0, SU)
expect("no fans, no gate", G.gateAmount([], 0, SU) == 0)
expect("concave: two fans earn more than one but less than double", one < two < 2 * one)
expect("the exponent is what sets the second fan's worth", abs(two / one - 2 ** GATE_FAN_EXPONENT) < 0.02)
expect("a bigger Stadium brings in more", G.gateAmount([1.0], 5, SU) > one)
cap = int(round(DONATION_MATCH_CAP_SHARES * SU))
expect("the match pays the rate on a donation under the cap",
       G.matchFor(100, 0, SU) == (100, int(round(100 * DONATION_MATCH_RATE))))
expect("and only on what is left of the season's cap", G.matchFor(500, cap - 50, SU)[0] == 50)
expect("nothing once the cap is used", G.matchFor(500, cap, SU) == (0, 0))

print("2. weekly gate in the database")
s = get_session()
now = datetime.datetime.utcnow()
def user(i, team, loggedIn=True):
    u = User(clerk_id=f"c{i}", email=f"u{i}@x.test", username=f"u{i}", favorite_team_id=team,
             is_active=True, last_login_at=now if loggedIn else now - datetime.timedelta(days=60))
    s.add(u); s.flush(); return u.id
a = user(1, 1); b = user(2, 1); c = user(3, 2); stale = user(4, 3, loggedIn=False)
for tid in (1, 2, 3):
    s.add(TeamTreasury(team_id=tid, balance=0))
    s.add(TeamFacility(team_id=tid, facility_key='stadium', level=0, upkeep_funded=0))
s.add(PickEmPick(user_id=a, season=5, week=3, game_index=0, home_team_id=1, away_team_id=2,
                 picked_team_id=1, is_auto=False))
s.add(PickEmPick(user_id=b, season=5, week=3, game_index=0, home_team_id=1, away_team_id=2,
                 picked_team_id=1, is_auto=True))
s.add(WeeklyCardBonus(roster_id=1, user_id=a, season=5, week=3, bonus_fp=0))
s.commit()
act = G.participationByUser(s, [a, b, c], 5, 3)
expect("a made picks and fielded a lineup (2); b's auto-picks don't count (0)", act == {a: 2, b: 0, c: 0})
paid = G.accrueWeeklyGate(s, 5, 3, SU, [1, 2, 3])
s.commit()
expect("team 1 is paid for both its fans, weighted",
       paid.get(1) == G.gateAmount([G.fanWeight(2), G.fanWeight(0)], 0, SU))
expect("team 2 is paid for its one fan", paid.get(2) == one)
expect("a fan who hasn't logged in recently doesn't count (team 3 gets nothing)", 3 not in paid)
expect("the money is in the Treasury", FM.getTreasury(s, 1) == paid[1])
again = G.accrueWeeklyGate(s, 5, 3, SU, [1, 2, 3]); s.commit()
expect("a re-run of the same week pays nothing twice", again == {} and FM.getTreasury(s, 1) == paid[1])
expect("the season's gate reads back", G.gateThisSeason(s, 1, 5) == paid[1])

print("3. the donation match")
m1 = G.matchDonation(s, a, 1, 5, 300, SU, 'treasury'); s.commit()
m2 = G.matchDonation(s, a, 1, 5, cap, SU, 'season_end'); s.commit()
m3 = G.matchDonation(s, a, 1, 5, 500, SU, 'treasury'); s.commit()
expect("the first donation is matched in full", m1 == int(round(300 * DONATION_MATCH_RATE)))
expect("the next is matched only up to the season cap", m2 == int(round((cap - 300) * DONATION_MATCH_RATE)))
expect("past the cap, nothing", m3 == 0 and G.matchRemaining(s, a, 5, SU) == 0)
expect("a new season starts a fresh cap", G.matchRemaining(s, a, 6, SU) == cap)
expect("the match is in the Treasury on top of the gate", FM.getTreasury(s, 1) == paid[1] + m1 + m2)
s.close()

shutil.rmtree(_tmp, ignore_errors=True)
print()
if failures:
    print(f"FAILED ({len(failures)}): " + "; ".join(failures))
    raise SystemExit(1)
print("ALL GATE REVENUE TESTS PASS")
