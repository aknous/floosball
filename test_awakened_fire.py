"""Awakened (L4) powers — P3 firing end-to-end through real play resolution.

Drives runPlay() / fieldGoalTry() on a Scenario game with a charged awakened player and asserts the
power forces the outcome (big run / made FG), suppresses the fumble, discharges the meter, and tags
the play. A control case (no ready player) confirms the resolution is untouched.

Run: python test_awakened_fire.py
"""
import os, sys
sys.path.insert(0, os.getcwd())
from scenario import Scenario
from constants import AWAKENED_FORCE_RUN_GAIN, AWAKENED_FORCE_PASS_GAIN

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
expect("the run is forced to at least the breakaway floor", p.yardage >= AWAKENED_FORCE_RUN_GAIN)
expect("a fired run does not fumble", not p.isFumbleLost)
expect("firing discharged the meter", s.game._awakenedReady[rb.id] is False and s.game._awakenedFills[rb.id] == 1)

print("\n2. Control — a non-ready runner runs normally (resolution untouched)")
s2 = Scenario()
s2.situation(quarter=1, clock=800, offense='home', down=1, distance=10, ballOn=80)
s2.game._awakenedReady = {}; s2.game._awakenedPower = {}; s2.game._awakenedCharge = {}
s2.game.play.runPlay()
expect("no fire tag when nobody is ready", s2.game.play.awakenedFire is None)

print("\n3. A charged kicker whose power covers 'kick' makes the FG automatically")
s3 = Scenario()
s3.situation(quarter=4, clock=120, offense='home', down=4, distance=8, ballOn=35)  # ~52yd FG
g3 = s3.game
k = g3.offensiveTeam.rosterDict['k']
g3._awakenedCharge = {k.id: 100.0}; g3._awakenedFills = {k.id: 0}
g3._awakenedReady = {k.id: True}; g3._awakenedPower = {k.id: 'moonshot'}
g3.play.fieldGoalTry()
expect("the FG is forced good", g3.play.isFgGood)
expect("the FG is tagged as an awakened fire", g3.play.awakenedFire and g3.play.awakenedFire['power'] == 'moonshot')
expect("firing discharged the kicker's meter", g3._awakenedReady[k.id] is False)

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
    expect("fired pass forces the breakaway floor", fired.yardage >= AWAKENED_FORCE_PASS_GAIN)
    expect("fired pass does not fumble", not fired.isFumbleLost)

print("\n5. A charged defender strips a run (forced fumble lost, credited to the defender)")
s5 = Scenario()
s5.situation(quarter=2, clock=600, offense='home', down=1, distance=10, ballOn=60)
g5 = s5.game
lb = g5.defensiveTeam.rosterDict['rb']   # LB (the defense's RB slot) — only the DEFENDER is ready
g5._awakenedCharge = {lb.id: 100.0}; g5._awakenedFills = {lb.id: 0}
g5._awakenedReady = {lb.id: True}; g5._awakenedPower = {lb.id: 'pickpocket'}   # covers run + defense
g5.play.runPlay()
p5 = g5.play
expect("the run is tagged as a defensive fire", p5.awakenedFire and p5.awakenedFire['situation'] == 'defense')
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
    g6._awakenedReady = {cb.id: True}; g6._awakenedPower = {cb.id: 'highway_robbery'}  # covers defense
    g6.play.passPlay(g6._selectPassPlay('medium'))
    if g6.play.awakenedFire and g6.play.awakenedFire['situation'] == 'defense':
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
