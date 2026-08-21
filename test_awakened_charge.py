"""Awakened charge meter: a per-game bar per awakened player, fed by positive
involvement, that latches READY on filling and discharges when the signature power
covers the situation.

⚠️ THE METER IS FLAT PER INVOLVEMENT, NOT SCALED BY YARDS (constants.py's
AWAKENED_INVOLVE_PER_GAME says so outright). This test used to assert
`50 * AWAKENED_CHARGE_PER_YARD`, alongside AWAKENED_CHARGE_QB_SHARE and
AWAKENED_CHARGE_KICKER — all three constants are GONE, so the module raised
ImportError and not one assertion ran. The charge for a position is now
THRESHOLD / AWAKENED_INVOLVE_PER_GAME[pos], i.e. a position fills roughly once over a
normal game, and a quiet game legitimately fails to fire.

⚠️ THE PLAYERS MUST BE THE OFFENSE'S REAL ROSTER OBJECTS. `_posOf` reverse-looks-up the
position by IDENTITY in `offensiveTeam.rosterDict`, so a bare stub player resolves to ''
and silently charges 0 — a test built on stubs would pass a "no charge" assertion for
entirely the wrong reason.

Run: .venv/bin/python test_awakened_charge.py
"""
import os, sys
sys.path.insert(0, os.getcwd())
from scenario import Scenario, PlayType
from constants import (AWAKENED_CHARGE_THRESHOLD, AWAKENED_INVOLVE_PER_GAME,
                       AWAKENED_CHARGE_DEF_EVENT)

failures = []
def expect(label, cond):
    print(f"  [{'OK' if cond else 'FAIL'}] {label}")
    if not cond:
        failures.append(label)


class Play:
    """⚠️ `offense=` IS REQUIRED on any run/pass play. `_posOf` reads the roster off the
    PLAY (`play.offense`), not off the game, so a play without it resolves every position
    to '' and charges 0 -- which reads as "the meter is broken" rather than "the fixture
    is incomplete". The kicker branch hides this, because it passes a literal 'K'."""
    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)


class Pl:
    def __init__(self, pid):
        self.id = pid


def involve(pos):
    return AWAKENED_CHARGE_THRESHOLD / AWAKENED_INVOLVE_PER_GAME[pos]


g = Scenario().game
off = g.offensiveTeam
RB, K = off.rosterDict['rb'], off.rosterDict['k']
DEF, NOBODY = Pl(9001), Pl(9099)

g._awakenedCharge = {RB.id: 0.0, K.id: 0.0, DEF.id: 0.0}
g._awakenedFills = {RB.id: 0, K.id: 0, DEF.id: 0}
g._awakenedReady = {RB.id: False, K.id: False, DEF.id: False}
# 'pickpocket' was removed when the power catalog was expanded; no_clip is universal.
g._awakenedPower = {RB.id: 'no_clip', K.id: 'moonshot', DEF.id: 'no_clip'}

print("1. Offense charges a FLAT amount per involvement; only awakened players accrue")
g._accumulateAwakenedCharge(Play(runner=RB, yardage=50, isPassCompletion=False, offense=off), PlayType.Run)
expect("a run charges the back one involvement's worth",
       abs(g._awakenedCharge[RB.id] - involve('RB')) < 0.01)
g._accumulateAwakenedCharge(Play(runner=NOBODY, yardage=40, isPassCompletion=False, offense=off), PlayType.Run)
expect("a run by a NON-tracked player adds nothing", NOBODY.id not in g._awakenedCharge)

# The point of the redesign: a 2-yarder is worth exactly what a 60-yarder is.
before = g._awakenedCharge[RB.id]
g._accumulateAwakenedCharge(Play(runner=RB, yardage=2, isPassCompletion=False, offense=off), PlayType.Run)
short = g._awakenedCharge[RB.id] - before
expect("a 2-yard run charges the same as a 50-yard run (flat, not per-yard)",
       abs(short - involve('RB')) < 0.01)

print("\n2. Meter caps at the threshold and latches READY (no overflow)")
for _ in range(20):   # well past a fill
    g._accumulateAwakenedCharge(Play(runner=RB, yardage=5, isPassCompletion=False, offense=off), PlayType.Run)
expect("charge caps at the threshold",
       abs(g._awakenedCharge[RB.id] - AWAKENED_CHARGE_THRESHOLD) < 0.01)
expect("crossing the threshold latches ready", g._awakenedReady[RB.id] is True)
g._accumulateAwakenedCharge(Play(runner=RB, yardage=20, isPassCompletion=False, offense=off), PlayType.Run)
expect("a ready meter does not accumulate further",
       abs(g._awakenedCharge[RB.id] - AWAKENED_CHARGE_THRESHOLD) < 0.01)

print("\n3. Kicker fast-charge (made FG only) + defensive stop charge")
g._accumulateAwakenedCharge(Play(kicker=K, isFgGood=True), PlayType.FieldGoal)
# K expects 0.5 involvements a game, so one made kick is worth two full meters --
# it caps, which is what "fast-charge" means.
expect("a made FG fills the kicker's meter outright",
       abs(g._awakenedCharge[K.id] - AWAKENED_CHARGE_THRESHOLD) < 0.01)
expect("...and latches the kicker ready", g._awakenedReady[K.id] is True)
g._accumulateAwakenedCharge(Play(runner=NOBODY, yardage=2, tackledBy=DEF, offense=off), PlayType.Run)
expect("defensive playmaker stop charges the flat defensive event",
       abs(g._awakenedCharge[DEF.id] - AWAKENED_CHARGE_DEF_EVENT) < 0.01)

print("\n4. _awakenedTryFire — ready + covered fires, resets, counts; otherwise no-op")
fire = g._awakenedTryFire('run', RB)
expect("a ready player whose power covers the situation fires",
       bool(fire) and fire['power'] == 'no_clip' and bool(fire['flavor']))
expect("firing resets the meter + clears ready",
       g._awakenedCharge[RB.id] == 0.0 and g._awakenedReady[RB.id] is False)
expect("firing counts a fire", g._awakenedFills[RB.id] == 1)
expect("a discharged meter does not fire again", g._awakenedTryFire('run', RB) is None)

# ⚠️ Part-charged, NOT ready. The defensive event is 0.0 by design (offense dominates
# the meter), so this is set directly rather than accrued -- accruing it would leave 0
# and the "meter intact" assertion below would hold vacuously.
g._awakenedCharge[DEF.id] = AWAKENED_CHARGE_THRESHOLD * 0.18
g._awakenedReady[DEF.id] = False
expect("a not-ready player does not fire",
       g._awakenedTryFire('strip', DEF) is None and g._awakenedCharge[DEF.id] > 0)

expect("a ready player does NOT fire on a situation its power doesn't cover",
       g._awakenedTryFire('pick', K) is None)
expect("...and that non-fire leaves the meter intact (still ready)", g._awakenedReady[K.id] is True)
expect("the same player fires on a covered situation",
       (g._awakenedTryFire('kick', K) or {}).get('power') == 'moonshot')

print("\n5. awakenedChargeState() exposure")
st = g.awakenedChargeState()
expect("state reports charge/pct/ready/fires/power",
       RB.id in st and st[RB.id]['fires'] == 1
       and st[RB.id]['power'] == 'no_clip' and 'ready' in st[RB.id])

print()
if failures:
    print(f"FAILED ({len(failures)}): " + "; ".join(failures))
    raise SystemExit(1)
print("ALL AWAKENED CHARGE+FIRE TESTS PASS")
