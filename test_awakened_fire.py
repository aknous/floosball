"""Awakened (L4) powers — P3 firing end-to-end through real play resolution.

Drives runPlay() / fieldGoalTry() on a Scenario game with a charged awakened player and asserts the
power forces the outcome (big run / made FG), suppresses the fumble, discharges the meter, and tags
the play. A control case (no ready player) confirms the resolution is untouched.

Run: python test_awakened_fire.py
"""
import os, sys
sys.path.insert(0, os.getcwd())
from scenario import Scenario
# ⚠️ THE RUN/PASS FORCED GAINS WERE UNIFIED. AWAKENED_FORCE_RUN_GAIN and
# AWAKENED_FORCE_PASS_GAIN are GONE -- importing them raised ImportError and no
# assertion in this file ran. A fired power now guarantees a FIRST DOWN
# (max(AWAKENED_FORCE_MIN_GAIN, yardsToFirstDown)) plus an exponential tail, the same
# way for a run and a pass, so the floor is asserted against the live situation rather
# than a per-play-type constant.
from constants import AWAKENED_FORCE_MIN_GAIN

failures = []
def expect(label, cond):
    print(f"  [{'OK' if cond else 'FAIL'}] {label}")
    if not cond:
        failures.append(label)

def readyRunner(s, power='no_clip'):
    g = s.game
    rb = g.offensiveTeam.rosterDict['rb']
    g._awakenedCharge = {rb.id: 100.0}
    g._awakenedFills = {rb.id: 0}
    g._awakenedReady = {rb.id: True}
    g._awakenedPower = {rb.id: power}
    return rb

print("1. A charged runner whose power covers 'run' breaks free (forced gain, no fumble)")
s = Scenario()
s.situation(quarter=1, clock=800, offense='home', down=1, distance=10, ballOn=80)  # own 20
rb = readyRunner(s)
s.game.play.runPlay()
p = s.game.play
expect("the play is tagged as an awakened fire", p.awakenedFire and p.awakenedFire['power'] == 'no_clip')
expect("the fire records WHO used the power", p.awakenedFire['playerName'] == rb.name and p.awakenedFire['playerId'] == rb.id)
expect("the fire records the power name", p.awakenedFire['powerName'] == 'No-Clip')
s.game.formatPlayText()
expect("the PBP text leads with the power name + flavor",
       p.playText.startswith('No-Clip:') and rb.name in p.playText)
expect("the run is forced to at least the breakaway floor",
       p.yardage >= max(AWAKENED_FORCE_MIN_GAIN, int(s.game.yardsToFirstDown or 0)))
expect("a fired run does not fumble", not p.isFumbleLost)
expect("firing discharged the meter", s.game._awakenedReady[rb.id] is False and s.game._awakenedFills[rb.id] == 1)

print("\n2. Control — a non-ready runner runs normally (resolution untouched)")
s2 = Scenario()
s2.situation(quarter=1, clock=800, offense='home', down=1, distance=10, ballOn=80)
s2.game._awakenedReady = {}; s2.game._awakenedPower = {}; s2.game._awakenedCharge = {}
s2.game.play.runPlay()
expect("no fire tag when nobody is ready", s2.game.play.awakenedFire is None)

print("\n3. A charged kicker's power RESCUES a kick, and is not spent on a made one")
# ⚠️ THE KICK FIRE IS A RESCUE, NOT AN OVERRIDE. fieldGoalTry only reaches
# _awakenedTryFire when the kick is beyond normal range or the roll MISSED; a kick that
# rolls good on its own is left alone and the meter stays charged. This section used to
# set up a makeable ~52-yarder and assert a fire, which passed only when the roll
# happened to miss. Use a kick beyond the kicker's range so the branch is deterministic.
s3 = Scenario()
k_probe = Scenario().game.offensiveTeam.rosterDict['k']
_beyond = int(getattr(k_probe, 'maxFgDistance', 55) or 55) + 15
s3.situation(quarter=4, clock=120, offense='home', down=4, distance=8,
             ballOn=_beyond - 17)          # ballOn is yards to the endzone; +17 = FG distance
g3 = s3.game
k = g3.offensiveTeam.rosterDict['k']
g3._awakenedCharge = {k.id: 100.0}; g3._awakenedFills = {k.id: 0}
g3._awakenedReady = {k.id: True}; g3._awakenedPower = {k.id: 'moonshot'}
g3.play.fieldGoalTry()
expect("a kick beyond the kicker's range is forced good by the power", g3.play.isFgGood)
expect("the FG is tagged as an awakened fire",
       bool(g3.play.awakenedFire) and g3.play.awakenedFire['power'] == 'moonshot')
expect("firing discharged the kicker's meter", g3._awakenedReady[k.id] is False)

# The other half of the same rule: an easy kick must NOT spend the power.
# ⚠️ ASSERTED AS AN INVARIANT PLUS A RATE, NOT AS A SINGLE OUTCOME. A first version read
# `(not isFgGood) or (awakenedFire is None and still ready)`, which has a hole: when the
# chip shot's roll MISSES, the power rescues it, so isFgGood is True AND a fire is
# recorded — both clauses go false and the test fails on a rescue working exactly as
# designed. A ~25-yarder misses rarely, so it failed roughly one run in twenty and passed
# twenty in a row while being hunted.
s3b = Scenario()
burned = fired = 0
TRIALS = 40
for _ in range(TRIALS):
    s3b.situation(quarter=4, clock=120, offense='home', down=4, distance=8, ballOn=8)  # ~25yd
    g3b = s3b.game
    kb = g3b.offensiveTeam.rosterDict['k']
    g3b._awakenedCharge = {kb.id: 100.0}; g3b._awakenedFills = {kb.id: 0}
    g3b._awakenedReady = {kb.id: True}; g3b._awakenedPower = {kb.id: 'moonshot'}
    g3b.play.fieldGoalTry()
    didFire = g3b.play.awakenedFire is not None
    stillReady = g3b._awakenedReady[kb.id] is True
    fired += int(didFire)
    burned += int(not stillReady)
    # The invariant holds on EVERY roll: the meter is spent exactly when the power fired.
    if didFire == stillReady:
        expect(f"meter spent iff the power fired (fired={didFire}, ready={stillReady})", False)
        break
expect(f"the meter is spent exactly when the power fires ({burned} spent, {fired} fired)",
       burned == fired)
expect(f"an easy kick usually makes itself and keeps the power ({TRIALS - fired}/{TRIALS})",
       fired <= TRIALS * 0.25)

print("\n4. A charged QB forces the completion (no INT/drop, big gain)")
# A dropback can sack/throw-away (no target), so loop until a real throw fires.
s4 = Scenario()
fired = None
for _ in range(30):
    s4.situation(quarter=1, clock=800, offense='home', down=1, distance=10, ballOn=70)
    g4 = s4.game
    qb = g4.offensiveTeam.rosterDict['qb']
    g4._awakenedCharge = {qb.id: 100.0}; g4._awakenedFills = {qb.id: 0}
    g4._awakenedReady = {qb.id: True}; g4._awakenedPower = {qb.id: 'wormhole'}  # covers throw
    g4.play.passPlay(g4._selectPassPlay('medium'))
    if g4.play.awakenedFire:
        fired = g4.play
        break
expect("a charged QB fires on a throw", fired is not None and fired.awakenedFire['power'] == 'wormhole')
if fired:
    expect("fired pass is a completion, not an interception", fired.isPassCompletion and not fired.isInterception)
    expect("fired pass forces the breakaway floor",
           fired.yardage >= AWAKENED_FORCE_MIN_GAIN)
    expect("fired pass does not fumble", not fired.isFumbleLost)

print("\n5. A charged defender strips a run (forced fumble lost, credited to the defender)")
s5 = Scenario()
s5.situation(quarter=2, clock=600, offense='home', down=1, distance=10, ballOn=60)
g5 = s5.game
lb = g5.defensiveTeam.rosterDict['rb']   # LB (the defense's RB slot) — only the DEFENDER is ready
g5._awakenedCharge = {lb.id: 100.0}; g5._awakenedFills = {lb.id: 0}
# ⚠️ 'pickpocket' NO LONGER EXISTS. The power catalog was expanded to 63 entries
# and renamed; an unknown key makes powerCoversSituation() return False, so the
# defender silently never fires. 'no_clip' is universal and covers strip + pick.
g5._awakenedReady = {lb.id: True}; g5._awakenedPower = {lb.id: 'no_clip'}
# ⚠️ DEFENSIVE FIRES ARE PROBABILITY-GATED (`_awakenedDefFireChance`, default
# AWAKENED_DEF_FIRE_CHANCE = 35%) so they cannot dominate the offense. That gate is
# newer than this test, which assumed a ready+covered defender always discharges. Pin it
# open here so the assertion is about the STRIP mechanics rather than a 35% coin flip.
g5._awakenedDefFireChance = 100.0
g5.play.runPlay()
p5 = g5.play
expect("the run is tagged as a strip fire", p5.awakenedFire and p5.awakenedFire['situation'] == 'strip')
expect("the run is stripped (fumble lost)", p5.isFumbleLost)
expect("the forced fumble is credited to the awakened defender", p5.forcedFumbleBy is lb)

print("\n6. A charged defender picks off a pass (forced INT, credited to the defender)")
s6 = Scenario()
fired6 = None
for _ in range(30):
    s6.situation(quarter=2, clock=600, offense='home', down=1, distance=10, ballOn=60)
    g6 = s6.game
    cb = g6.defensiveTeam.rosterDict['wr1']   # CB; only the defender is ready
    g6._awakenedCharge = {cb.id: 100.0}; g6._awakenedFills = {cb.id: 0}
    g6._awakenedDefFireChance = 100.0   # see note above: pin the defensive gate open
    # 'highway_robbery' was also removed in the catalog expansion; no_clip covers 'pick'.
    g6._awakenedReady = {cb.id: True}; g6._awakenedPower = {cb.id: 'no_clip'}
    g6.play.passPlay(g6._selectPassPlay('medium'))
    if g6.play.awakenedFire and g6.play.awakenedFire['situation'] == 'pick':
        fired6 = g6.play
        break
expect("a charged defender fires on a pass", fired6 is not None)
if fired6:
    expect("the pass is intercepted", fired6.isInterception)
    expect("the pick is credited to the awakened defender", fired6.interceptedBy is cb)

print()
if failures:
    print(f"FAILED ({len(failures)}): " + "; ".join(failures))
    raise SystemExit(1)
print("ALL AWAKENED-FIRE (P3) TESTS PASS")
