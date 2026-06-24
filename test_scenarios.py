"""Constructed-scenario regression suite (built on scenario.Scenario).

Locks in this session's late-game / FG / clock fixes by constructing the exact
situations and running the REAL engine decisions over them — no waiting for a
rare occurrence in a random sim.

Run: .venv/bin/python test_scenarios.py   (exits non-zero on any failure)
"""
import random
import numpy as np
from scenario import Scenario, PlayType
from random_batch import clear_all_batch_caches
import floosball_player as FP


def reseed(s=0):
    """Make the engine's RNG deterministic for the frequency-based mental tests:
    the sim draws through random_batch (cached) + numpy, so seed both and flush
    the caches. Without this these tests are flaky run-to-run."""
    random.seed(s)
    np.random.seed(s)
    clear_all_batch_caches()


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


# ── 7. The model's math is correct AND position-agnostic (deterministic) ─
# The Confidence x Discipline helpers (docs/MENTAL_MODEL.md) are pure functions
# applied at every gate, so they affect EVERY ball-handling position the same
# way. Unit-test them directly across QB / RB / WR / TE / K — no RNG, no flake.
print("7. Confidence x Discipline math is correct for every position")
_s = Scenario()
_s.situation(quarter=2, clock=600, offense='home', offScore=0, defScore=0, down=1, distance=10, ballOn=60)
_p = _s.game.play   # the helpers live on Play (where per-play resolution runs)
def setM(p, c, d):
    p.gameAttributes.confidenceModifier = c
    p.gameAttributes.discipline = d
qb, rb = _s.home.rosterDict['qb'], _s.home.rosterDict['rb']
setM(qb, 5, 80);  expect("confidenceState +5 -> +1", abs(_p._confidenceState(qb) - 1.0) < 1e-9)
setM(qb, -5, 80); expect("confidenceState -5 -> -1", abs(_p._confidenceState(qb) + 1.0) < 1e-9)
setM(qb, 0, 60);  expect("undiscipline disc60 -> 1.0", abs(_p._undiscipline(qb) - 1.0) < 1e-9)
setM(qb, 0, 80);  expect("undiscipline disc80 -> 0.0", abs(_p._undiscipline(qb)) < 1e-9)
for name in ('qb', 'rb', 'wr1', 'te', 'k'):
    p = _s.home.rosterDict[name]
    setM(p, 5, 95);  surg = _p._confExecution(p)
    setM(p, 5, 62);  guns = _p._confExecution(p)
    setM(p, -5, 95); mgr  = _p._confExecution(p)
    setM(p, -5, 62); frz  = _p._confExecution(p)
    expect(f"{name}: high-C execution beats low-C", min(surg, guns) > max(mgr, frz))
    expect(f"{name}: frozen (lowC,lowD) underperforms more than the manager (lowC,highD)", frz < mgr - 0.1)
    expect(f"{name}: discipline does NOT change execution at high C (surgeon==gunslinger)", abs(surg - guns) < 1e-9)
    setM(p, 5, 62);  expect(f"{name}: gunslinger (highC,lowD) pays a turnover tax", _p._gunslingerTax(p) > 1.0)
    setM(p, 5, 95);  expect(f"{name}: surgeon (highC,highD) pays ~no tax", _p._gunslingerTax(p) < 0.5)
    setM(p, -5, 62); expect(f"{name}: low confidence -> no gunslinger tax", _p._gunslingerTax(p) == 0.0)

# ── 8. Emergent QB archetypes (pass game, frequency) ─────────────────────
print("8. The QB archetypes emerge in real pass plays")
N = 700
def passQuadrant(conf, disc):
    s = Scenario(); g = s.game; comp = ints = 0
    for _ in range(N):
        s.situation(quarter=2, clock=600, offense='home', offScore=0, defScore=0,
                    down=1, distance=10, ballOn=60)
        for p in s.home.rosterDict.values():
            if p: p.gameAttributes.confidenceModifier = conf; p.gameAttributes.discipline = disc
        g.play.passPlay(g._selectPassPlay('medium'))
        if getattr(g.play, 'isInterception', False): ints += 1
        elif getattr(g.play, 'isPassCompletion', False): comp += 1
    return comp / N * 100, ints / N * 100
reseed(1); surgC, surgI = passQuadrant(5, 95)
reseed(1); gunC,  gunI  = passQuadrant(5, 62)
reseed(1); mgrC,  mgrI  = passQuadrant(-5, 95)
reseed(1); frzC,  frzI  = passQuadrant(-5, 62)
expect("high confidence completes more than low confidence", min(surgC, gunC) > max(mgrC, frzC) + 2.0)
expect("gunslinger (high C, low D) throws more INTs than the surgeon", gunI > surgI + 1.0)
expect("surgeon barely turns it over despite high confidence", surgI < 1.5)

# ── 9. RB run game — confidence is multi-position ────────────────────────
print("9. A confident RB runs for more than a rattled one")
def rbYpc(conf):
    s = Scenario(); g = s.game; tot = 0
    for _ in range(N):
        s.situation(quarter=2, clock=600, offense='home', offScore=0, defScore=0,
                    down=1, distance=10, ballOn=60)
        s.home.rosterDict['rb'].gameAttributes.confidenceModifier = conf
        g.play.runPlay(); tot += g.play.yardage
    return tot / N
reseed(2); rbHi = rbYpc(5)
reseed(2); rbLo = rbYpc(-5)
expect("confident RB averages more yards than a rattled RB", rbHi > rbLo + 0.5)

# ── 10. Aggression (P2) — confident forces it, rattled bails ─────────────
# The effect is real but modest (bail is a small fraction of dropbacks); assert
# the deterministic directional gap.
print("10. A confident QB forces throws; a rattled QB bails")
def bailRate(conf):
    s = Scenario(); g = s.game; bail = 0
    for _ in range(N):
        s.situation(quarter=2, clock=600, offense='home', offScore=0, defScore=0,
                    down=1, distance=10, ballOn=60)
        s.home.rosterDict['qb'].gameAttributes.confidenceModifier = conf
        g.play.passPlay(g._selectPassPlay('medium'))
        if getattr(g.play, 'isThrowAway', False) or getattr(g.play, 'selectedTarget', None) is None:
            bail += 1
    return bail / N * 100
reseed(5); confBail = bailRate(5)
reseed(5); rattledBail = bailRate(-5)
expect("rattled QB bails more than a confident QB", rattledBail > confBail + 1.0)

# ── 11. Situational sideline decision (clock-aware OOB) ───────────────────
print("11. Ball-carriers make clock-aware out-of-bounds decisions")
def oobRun(scoreDiff, disc=95, inst=95, conf=0):
    s = Scenario(); g = s.game; oob = 0; notes = {}
    for _ in range(N):
        s.situation(quarter=4, clock=90, offense='home',
                    offScore=14 + max(0, scoreDiff), defScore=14 + max(0, -scoreDiff),
                    down=2, distance=8, ballOn=55)
        rb = s.home.rosterDict['rb']
        rb.gameAttributes.discipline = disc; rb.gameAttributes.instinct = inst
        rb.gameAttributes.confidenceModifier = conf
        g.play.runPlay()
        if not g.play.isInBounds: oob += 1
        n = getattr(g.play, '_sidelineNote', None)
        if n: notes[n] = notes.get(n, 0) + 1
    return oob / N * 100, notes
reseed(6); trailOOB, trailNotes = oobRun(-7)          # trailing late, smart
reseed(6); leadOOB,  leadNotes  = oobRun(+7)          # leading late, smart
reseed(6); _, greedyNotes       = oobRun(-7, disc=62, conf=5)  # trailing, greedy gunslinger
expect("trailing-late carrier gets out of bounds far more than a leading one",
       trailOOB > leadOOB + 8.0)
expect("leading-late carrier stays in bounds (doesn't stop its own clock)", leadOOB < 3.0)
expect("trailing-late smart carrier narrates getting out to stop the clock",
       trailNotes.get('smart_oob', 0) > 0)
expect("leading-late smart carrier narrates staying in bounds",
       leadNotes.get('stays_inbounds', 0) > 0)
expect("greedy/undisciplined carrier sometimes gets tackled in bounds gambling for yards",
       greedyNotes.get('tackled_inbounds', 0) > 0)


print()
if failures:
    print(f"FAILED ({len(failures)}): " + "; ".join(failures))
    raise SystemExit(1)
print("ALL SCENARIOS PASS")
