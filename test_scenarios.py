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


# ── 8. Clock-management skill drives the plays-remain decision ───────────
# With a WINNING FG already in hand and 2+ plays left, the smart play is to
# DRAIN the clock and kick on the last snap. A sharp clock-management coach
# does that almost always; a poor one gambles the ball on a TD far more often.
print("8. Clock-management skill: a sharp coach drains for the winning FG, a poor one gambles")
def drainRate(clockMgmt, n=300):
    s = Scenario()
    s.home.coach.clockManagement = clockMgmt
    s.home.coach.aggressiveness = 80          # neutral aggression — isolate clock IQ
    drains = 0
    for i in range(n):
        _r.seed(i)
        # trailing by 2 (a FG WINS), 30s, 1st down, 1 timeout -> 2 plays available
        s.situation(quarter=4, clock=30, offense='home', offScore=20, defScore=22,
                    down=1, distance=10, ballOn=16, offTimeouts=1, defTimeouts=3, clockRunning=False)
        if s.clockDecision() == 'setupFG':
            drains += 1
    return drains / n
sharpDrain = drainRate(100)   # clock IQ 1.0
poorDrain = drainRate(60)     # clock IQ 0.0
expect("a sharp clock-management coach drains for the winning FG more than a poor one (skill matters)",
       sharpDrain > poorDrain + 0.08)
expect("a sharp coach drains (sets up the FG) the vast majority of the time", sharpDrain > 0.85)
expect("a poor coach gambles for the TD noticeably more often", poorDrain < 0.85)
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

# ── 12. Stretch for the first down — confidence drives the reach ─────────
print("12. A confident carrier reaches the ball across the marker to convert")
def stretchRun(conf):
    s = Scenario(); g = s.game; firstDowns = 0; notes = {}
    for _ in range(N):
        s.situation(quarter=2, clock=600, offense='home', offScore=0, defScore=0,
                    down=3, distance=5, ballOn=50)
        s.home.rosterDict['rb'].gameAttributes.confidenceModifier = conf
        g.play.runPlay()
        nt = getattr(g.play, '_stretchNote', None)
        if nt: notes[nt] = notes.get(nt, 0) + 1
        if g.play.yardage >= 5 and not getattr(g.play, 'isFumbleLost', False):
            firstDowns += 1
    return firstDowns / N * 100, notes
reseed(8); confConv, confNotes = stretchRun(5)
reseed(8); timidConv, timidNotes = stretchRun(-5)
expect("confident carrier converts the first down more than a tentative one", confConv > timidConv + 5.0)
expect("confident carrier narrates reaching across the marker", confNotes.get('stretch_first', 0) > 0)
expect("tentative carrier never reaches (takes the spot)", timidNotes.get('stretch_first', 0) == 0)

# ── 13. Dive for a catch — confidence makes a receiver lay out ───────────
print("13. A confident receiver lays out for contested balls (diving grabs)")
def diveGrabs(conf):
    s = Scenario(awayDefPass=90, awayDefRun=90); g = s.game; dives = 0
    for _ in range(N):
        s.situation(quarter=2, clock=600, offense='home', offScore=0, defScore=0,
                    down=1, distance=10, ballOn=60)
        for slot in ('wr1', 'wr2', 'te'):
            s.home.rosterDict[slot].gameAttributes.confidenceModifier = conf
        g.play.passPlay(g._selectPassPlay('medium'))
        if getattr(g.play, '_diveCatch', False): dives += 1
    return dives
reseed(1); confDives = diveGrabs(5)
reseed(1); timidDives = diveGrabs(-5)
expect("confident receiver makes diving grabs on contested balls", confDives > 0)
expect("a non-confident receiver never lays out for a diving grab", timidDives == 0)

# ── 14. Determination & Resilience — the two confidence shock absorbers ──
# Deterministic: they scale confidence's DOWNWARD drift by source.
print("14. Determination resists scoreboard loss; resilience resists own-mistake loss")
_sp = Scenario().home.rosterDict['wr1']
def drift(attr_name, attr_val, source, val=-0.10):
    setattr(_sp.gameAttributes, attr_name, attr_val)
    _sp.gameAttributes.confidenceModifier = 0.0
    _sp.updateInGameConfidence(val, source=source)
    return _sp.gameAttributes.confidenceModifier
expect("high resilience (100) shrugs off an own mistake (~no drop)", abs(drift('resilience', 100, 'mistake')) < 1e-9)
expect("neutral resilience (80) takes the full mistake drop", abs(drift('resilience', 80, 'mistake') + 0.10) < 1e-9)
expect("low resilience (60) spirals (≈2x the mistake drop)", drift('resilience', 60, 'mistake') < -0.18)
expect("high determination/selfBelief (100) holds when losing (~no drop)", abs(drift('selfBelief', 100, 'scoreboard')) < 1e-9)
expect("low determination/selfBelief (60) folds when losing (≈2x)", drift('selfBelief', 60, 'scoreboard') < -0.18)
_sp.gameAttributes.resilience = 100; _sp.gameAttributes.confidenceModifier = 0.0
_sp.updateInGameConfidence(+0.10, source='mistake')
expect("a positive drift (good play) is never scaled", abs(_sp.gameAttributes.confidenceModifier - 0.10) < 1e-9)

# ── 15. Catch-side stretch + the POWER grounding ─────────────────────────
# The stretch now keys off a physical attribute (power) for the reach, not just
# confidence — and it fires on catches, not only runs.
print("15. A receiver stretches for the marker; power drives the reach")
def catchStretch(conf, power):
    s = Scenario(awayDefPass=85); g = s.game; converted = camShort = 0
    for _ in range(2500):
        s.situation(quarter=2, clock=600, offense='home', offScore=0, defScore=0,
                    down=3, distance=12, ballOn=55)
        for sl in ('wr1', 'wr2', 'te'):
            r = s.home.rosterDict[sl]
            r.gameAttributes.confidenceModifier = conf; r.gameAttributes.power = power
        g.play.passPlay(g._selectPassPlay('medium'))
        n = getattr(g.play, '_stretchNote', None)
        if n == 'stretch_first': converted += 1
        elif n == 'stretch_short': camShort += 1
    return converted, camShort
reseed(2); powConv, powShort = catchStretch(5, 95)    # confident + powerful
reseed(2); weakConv, weakShort = catchStretch(5, 62)  # confident + weak
reseed(2); timidConv, _ = catchStretch(-5, 95)        # tentative
expect("a receiver reaches the ball across the marker on a catch (catch-side wired)", powConv > 0)
expect("a powerful receiver converts the reach more than a weak one (power grounding)", powConv > weakConv)
expect("a weak receiver comes up short more often than a powerful one", weakShort > powShort)
expect("a tentative receiver never reaches", timidConv == 0)

# ── 16. Attitude baseline anchor (P4) ────────────────────────────────────
# Attitude is now a stable trait: a disposition baseline is set at generation,
# and the offseason drift mean-reverts toward THAT (not a global neutral).
print("16. Attitude carries a disposition baseline set at generation")
_apTeam = Scenario().home
_bases = [(p.attributes.attitude, getattr(p.attributes, 'attitudeBaseline', None))
          for p in _apTeam.rosterDict.values() if p]
expect("every generated player has a positive attitudeBaseline", all(b for _, b in _bases))
expect("attitudeBaseline equals the generated attitude (the anchor starts on the disposition)",
       all(a == b for a, b in _bases))


print()
if failures:
    print(f"FAILED ({len(failures)}): " + "; ".join(failures))
    raise SystemExit(1)
print("ALL SCENARIOS PASS")
