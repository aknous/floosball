"""The draft takes the obvious player, in the right position order, and can cut for an upgrade.

⚠️ THIS EXISTS BECAUSE A FIRST-OVERALL PICK PASSED ON A 5-STAR RB FOR A 2-STAR WR (owner,
2026-09-13). Three separate faults stacked to produce it, and each is pinned below.

Run: .venv/bin/python test_draft_priority.py
"""
import sys, os, random, statistics as st
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import logging; logging.disable(logging.WARNING)

fails = []
def expect(d, c):
    print(f"  [{'OK' if c else 'FAIL'}] {d}")
    if not c: fails.append(d)

from constants import POSITION_VALUE, FO_SCOUT_NOISE_MAX, FO_SCOUT_NOISE_FLOOR, \
                      FO_DRAFT_CUT_UPGRADE_MARGIN
from managers.frontOfficeBrain import FrontOfficeBrain
from managers.playerManager import PlayerManager

class Pos:
    def __init__(s, v): s.value = v; s.name = {1:'QB',2:'RB',3:'WR',4:'TE',5:'K'}[v]
class Tier:
    def __init__(s, v): s.value = v
class Attrs:
    def __init__(s, r): s.skillRating = r
class P:
    def __init__(s, pid, pos, rating, seasons=0, ceiling=None):
        s.id = pid; s.name = f"P{pid}"; s.position = Pos(pos)
        s.playerRating = float(rating); s.attributes = Attrs(rating)
        s.seasonsPlayed = float(seasons); s.longevity = 12
        s._ceiling = float(ceiling if ceiling is not None else rating)
        s.willRetire = False; s.team = 'Free Agent'; s.freeAgentYears = 0
        s.is_prospect = False; s.playerTier = Tier('A'); s.term = 2; s.termRemaining = 2
        s.previousTeam = 'Rookie'
    def computeCeilingRating(s): return s._ceiling
class T:
    def __init__(s):
        s.id = 14; s.name = 'Slippers'; s.abbr = 'KCS'; s.coach = None; s.prospects = []
        s.facilities = {'training':2,'locker_room':2,'recovery':2,'clubhouse':2,'stadium':2}
        s.rosterDict = {'qb':None,'rb':None,'wr1':None,'wr2':None,'te':None,'k':None}
        s._draftFilledSlots = set()
    def assignPlayerNumber(s, p): pass
class Coach:
    def __init__(s, sc): s.id = sc; s.scouting = sc; s.playerDevelopment = 80

brain = FrontOfficeBrain(playerManager=None)

print("\n1. Position priority is QB > RB > WR > TE > K")
order = [k for k, _ in sorted(POSITION_VALUE.items(), key=lambda kv: -kv[1])]
expect(f"order is {' > '.join(order)}", order == ['QB','RB','WR','TE','K'])
# ⚠️ RB ABOVE WR IS THE OWNER'S CALL *and* the engine's own FLOOS_POS_FORCE measurement
# (QB +2.52, RB +1.25, WR +0.91, TE +0.54, K -0.93 wins a season). The table used to
# contradict both.
expect("RB outranks WR (it did not before)", POSITION_VALUE['RB'] > POSITION_VALUE['WR'])

print("\n2. An obvious pick is obvious, even to an incompetent GM")
# ⚠️ THE REPORTED CASE. A 5-star RB (92) against a 2-star WR (70). Before the scouting
# error was bounded by the career arc this flipped 28.5% of the time at scouting 60 and
# 11.4% at scouting 80 -- a flat +-12 blanket over the whole rating, applied to a number
# that is written on the sheet for anyone to read.
team = T()
rb, wr = P(1, 2, 92), P(2, 3, 70)
for sc in (60, 70, 80, 90):
    flips = 0; N = 600
    for i in range(N):
        b = brain.buildDraftBoard(team, [rb, wr], coach=Coach(sc), rng=random.Random(i))
        if b.get(2, 0) > b.get(1, 0): flips += 1
    expect(f"scouting {sc}: the 2-star WR outranks the 5-star RB {100*flips/N:.1f}% "
           f"(was 28.5% at 60 / 11.4% at 80)", flips / N <= 0.02)

print("\n3. ...but boards still differ where the answer is genuinely uncertain")
# ⚠️ THE ERROR IS ON THE ARC, so a project with real headroom is where GMs disagree. If this
# ever reads 0 the per-team draft board has stopped meaning anything.
project = P(3, 2, 70, ceiling=95)
vals = [brain.buildDraftBoard(team, [project], coach=Coach(70),
                              rng=random.Random(i)).get(3, 0) for i in range(600)]
prime = P(4, 2, 70, ceiling=70)
pvals = [brain.buildDraftBoard(team, [prime], coach=Coach(70),
                               rng=random.Random(i)).get(4, 0) for i in range(600)]
expect(f"a project with 25 points of headroom still splits opinion (sd {st.pstdev(vals):.2f})",
       st.pstdev(vals) > 1.0)
expect(f"a player with no headroom is read nearly exactly (sd {st.pstdev(pvals):.2f})",
       st.pstdev(pvals) < st.pstdev(vals))
expect("the noise floor cannot cross a tier", FO_SCOUT_NOISE_FLOOR * 2 < 8)

print("\n4. A club cuts for an obvious upgrade at a FILLED position")
class Stub:
    """Just enough PlayerManager for _attemptRosterFill."""
    def __init__(s, fas, board):
        s.freeAgents = list(fas); s._faDraftBoards = {14: board}
    def _leftThisTeamThisOffseason(s, p, t): return False
    def _getPlayerTerm(s, p): return 2

def runPick(incumbentRating, faRating, filledThisDraft=()):
    t = T()
    inc = P(10, 2, incumbentRating); inc.team = t
    t.rosterDict = {'qb':P(20,1,80),'rb':inc,'wr1':P(21,3,80),'wr2':P(22,3,80),
                    'te':P(23,4,80),'k':P(24,5,80)}
    for p in t.rosterDict.values(): p.team = t
    t._draftFilledSlots = set(filledThisDraft)
    fa = P(11, 2, faRating)
    board = {}
    for p in list(t.rosterDict.values()) + [fa]:
        board[p.id] = brain.decisionValue(p, None, rng=random.Random(0), team=t)
    pm = Stub([fa], board)
    hl = []
    PlayerManager._attemptRosterFill(pm, t, [t], [], [fa], [], [], [], {}, hl)
    return t.rosterDict['rb'], hl

got, hl = runPick(60, 95)
expect(f"a 95 free agent replaces a 60 incumbent (rb is now {got.playerRating:.0f})",
       got.id == 11)
expect("and the cut is announced", any('released' in (h.get('event') or {}).get('text','')
                                       for h in hl))
got, _ = runPick(88, 92)
expect(f"a marginal upgrade does NOT cost a starter his job (rb is still "
       f"{got.playerRating:.0f})", got.id == 10)
got, _ = runPick(60, 95, filledThisDraft=('rb',))
expect("a slot filled EARLIER IN THIS DRAFT is off limits (no churn)", got.id == 10)
expect("the margin is well above the ordinary offseason one",
       FO_DRAFT_CUT_UPGRADE_MARGIN > 6.0)

print("\n" + ("FAIL" if fails else "PASS") + " — the draft takes the obvious man and can upgrade a filled slot.")
for f in fails: print("   -", f)
sys.exit(1 if fails else 0)
