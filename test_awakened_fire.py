"""Awakened (L4) powers — P3 firing end-to-end through real play resolution.

Drives runPlay() / fieldGoalTry() on a Scenario game with a charged awakened player and asserts the
power forces the outcome (big run / made FG), suppresses the fumble, discharges the meter, and tags
the play. A control case (no ready player) confirms the resolution is untouched.

Run: python test_awakened_fire.py
"""
import os, sys
sys.path.insert(0, os.getcwd())
from scenario import Scenario
from constants import AWAKENED_FORCE_RUN_GAIN

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

print()
if failures:
    print(f"FAILED ({len(failures)}): " + "; ".join(failures))
    raise SystemExit(1)
print("ALL AWAKENED-FIRE (P3) TESTS PASS")
