"""Constructed-scenario regression suite (built on scenario.Scenario).

Locks in this session's late-game / FG / clock fixes by constructing the exact
situations and running the REAL engine decisions over them — no waiting for a
rare occurrence in a random sim.

Run: .venv/bin/python test_scenarios.py   (exits non-zero on any failure)
"""
import random
from scenario import Scenario, PlayType
import floosball_player as FP

failures = []
def expect(desc, cond):
    print(f"  [{'OK' if cond else 'FAIL'}] {desc}")
    if not cond:
        failures.append(desc)


# ── 1. FG range model: leg 60->50, 80->58, 100->66 ───────────────────────
print("1. FG range model scales across the legStrength domain (60-100)")
def maxFgFor(leg):
    k = FP.PlayerK(80, 80)
    k.attributes.legStrength = leg
    k.updateRating()
    return k.maxFgDistance
for leg, want in [(60, 50), (61, 50), (80, 58), (100, 66)]:
    got = maxFgFor(leg)
    expect(f"legStrength {leg} -> maxFgDistance {want}", got == want)


# ── 2. A below-average leg attempts a 45-yarder (opp 28) ─────────────────
print("2. A 61-leg kicker (maxFg 50) attempts a 45-yard FG from the opp 28")
s = Scenario()
s.setKickerLeg('home', 50)  # ~leg 61
random.seed(1)
fgs = sum(s.situation(quarter=4, clock=400, offense='home', offScore=14, defScore=14,
                      down=4, distance=6, ballOn=28).fourthDownPlay() is PlayType.FieldGoal
          for _ in range(40))
expect("attempts the FG most of the time (>=30/40)", fgs >= 30)


# ── 3. Never punt from inside the opponent's 40 ──────────────────────────
print("3. Never punt from inside the opponent's 40 (out of FG range -> go for it)")
s = Scenario()
s.setKickerLeg('home', 45)  # weak leg: 38+17=55 is out of range
random.seed(2)
punts = sum(s.situation(quarter=2, clock=600, offense='home', offScore=10, defScore=10,
                        down=4, distance=8, ballOn=38).fourthDownPlay() is PlayType.Punt
            for _ in range(50))
expect("0 punts from the opp 38 out of FG range", punts == 0)


# ── 4. Late-game timeout for a tied team in FG range ─────────────────────
print("4. Tied team in FG range burns timeouts late; not in deep territory")
s = Scenario()
random.seed(3)
def toCount(clock, ballOn):
    return sum(s.situation(quarter=4, clock=clock, offense='home', offScore=14, defScore=14,
                           down=2, distance=7, ballOn=ballOn, offTimeouts=3, defTimeouts=3,
                           clockRunning=True).clockDecision() == 'timeout'
               for _ in range(60))
inRange_240 = toCount(160, 30)     # 2:40, in FG range
deep_240    = toCount(160, 72)     # 2:40, own territory
inRange_150 = toCount(110, 30)     # 1:50 (inside 2:00), in FG range
expect("at 2:40 in FG range, timeout fires sometimes (was 0 before the window fix)", inRange_240 > 0)
expect("at 2:40 in deep territory, timeout does NOT fire", deep_240 == 0)
expect("inside 2:00 in FG range, timeout fires almost always (>=50/60)", inRange_150 >= 50)


# ── 5. Kneel on 4th down only when it ends the game ──────────────────────
print("5. 4th-down kneel only when the opponent can't stop the clock")
s = Scenario()
random.seed(4)
# Leading, 4th down, 28s left, ball at the opponent's 33 (the reported spot).
def kneels(defTimeouts):
    return sum(s.situation(quarter=4, clock=28, offense='home', offScore=21, defScore=20,
                           down=4, distance=5, ballOn=33, offTimeouts=2, defTimeouts=defTimeouts,
                           clockRunning=True).fourthDownPlay() is PlayType.Kneel
               for _ in range(40))
oppHasTO = kneels(2)   # opponent could stop the clock -> never kneel into a turnover
oppNoTO  = kneels(0)   # opponent can't stop it -> kneel runs out the clock (game-ender)
expect("opponent has timeouts -> never kneel (0/40)", oppHasTO == 0)
expect("opponent out of timeouts -> kneel to end it (>0/40)", oppNoTO > 0)


# ── 6. OT walk-off: a defensive score ends the game ──────────────────────
print("6. A defensive score in OT ends the game (real Game predicates)")
s = Scenario()
# 1st OT, home (had first possession) leads 20-14 after a return TD; second
# possession not yet flagged complete, clock still running.
s.situation(quarter=5, clock=240, offense='away', offScore=14, defScore=20,
            down=1, distance=10, ballOn=50, otPeriod=1,
            otFirstPossTeam=s.home, otFirstPossComplete=True, otSecondPossComplete=False)
expect("before the walk-off flag, isGameOver is False (the old bug)", s.gameOver() is False)
expect("checkOvertimeEnd(defensiveScore=True) -> walk-off", s.overtimeEnds(defensiveScore=True) is True)
s.g.otSecondPossComplete = True   # what the fix sets at the defensive-score site
expect("after the fix flag, isGameOver -> True (game ends)", s.gameOver() is True)


# ── 7. Last-play FG: kick the game-winner/tier instead of running ────────
# Trailing by 1-2 (FG wins) or 3 (FG ties), or tied (FG wins): on the LAST
# realistic play (down 4, or only ~1 snap fits), kick the FG — don't gamble the
# final play on a TD. The gate is the play-count estimate (which accounts for
# timeouts/spikes needed to stop the clock), NOT a fixed clock threshold.
print("7. A game-winning/tying FG is kicked on the last play, not deferred to a run")
def fgCall(deficit, clock, down, ballOn=16, offTO=1):
    s = Scenario()
    s.situation(quarter=4, clock=clock, offense='home', offScore=20, defScore=20 + deficit,
                down=down, distance=10, ballOn=ballOn, offTimeouts=offTO, defTimeouts=3,
                clockRunning=False)
    return s.callPlay()
expect("trailing by 2, 1st down, 14s, 1 timeout (the reported bug) -> kicks the winner",
       fgCall(2, 14, 1) is PlayType.FieldGoal)
expect("trailing by 2, no timeouts, 12s -> kicks (last play)", fgCall(2, 12, 1, offTO=0) is PlayType.FieldGoal)
expect("trailing by 3 (FG ties), last play -> kicks the tying FG", fgCall(3, 12, 1) is PlayType.FieldGoal)
expect("tied (FG wins), last play -> kicks the winner", fgCall(0, 12, 1) is PlayType.FieldGoal)
expect("3rd down, no timeouts (can't spike), ~1 play left -> kicks", fgCall(2, 20, 3, offTO=0) is PlayType.FieldGoal)
expect("4th down in range, trailing -> kicks", fgCall(2, 25, 4) is PlayType.FieldGoal)
# Plays remain (90s): should NOT auto-kick — play on for the TD. Frequency check
# since the defer carries a small coach-miss chance.
import random as _r
kicks = 0
for i in range(60):
    _r.seed(i)
    if fgCall(2, 90, 1) is PlayType.FieldGoal:
        kicks += 1
expect("with 2+ plays left (90s), it does NOT auto-kick (plays on for the TD)", kicks < 18)


print()
if failures:
    print(f"FAILED ({len(failures)}): " + "; ".join(failures))
    raise SystemExit(1)
print("ALL SCENARIOS PASS")
