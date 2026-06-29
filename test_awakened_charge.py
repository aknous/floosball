"""Awakened (L4) powers — P2 charge meter + P3 firing.

P2: the meter accumulates impact-weighted involvement (yards on offense, a flat stop on defense, a
chunk per made FG), caps at the threshold, and latches READY (it does not overflow).
P3: _awakenedTryFire discharges a ready player whose power covers the situation (resets the meter,
counts a fire, returns the flavor); it no-ops otherwise.

Run: python test_awakened_charge.py
"""
import os, sys
sys.path.insert(0, os.getcwd())
from scenario import Scenario, PlayType
from constants import (AWAKENED_CHARGE_THRESHOLD, AWAKENED_CHARGE_PER_YARD, AWAKENED_CHARGE_QB_SHARE,
                       AWAKENED_CHARGE_KICKER, AWAKENED_CHARGE_DEF_EVENT)

failures = []
def expect(label, cond):
    print(f"  [{'OK' if cond else 'FAIL'}] {label}")
    if not cond:
        failures.append(label)

class Pl:
    def __init__(self, pid): self.id = pid
class Play:
    def __init__(self, **kw):
        for k, v in kw.items(): setattr(self, k, v)

g = Scenario().game
RB, K, DEF, NOBODY = Pl(1), Pl(2), Pl(3), Pl(99)
g._awakenedCharge = {1: 0.0, 2: 0.0, 3: 0.0}
g._awakenedFills = {1: 0, 2: 0, 3: 0}
g._awakenedReady = {1: False, 2: False, 3: False}
g._awakenedPower = {1: 'no_clip', 2: 'moonshot', 3: 'pickpocket'}

print("1. Offense charges by yards; only awakened players accrue")
g._accumulateAwakenedCharge(Play(runner=RB, yardage=50, isPassCompletion=False), PlayType.Run)
expect("50-yd run -> 50 * per_yard charge", abs(g._awakenedCharge[1] - 50 * AWAKENED_CHARGE_PER_YARD) < 0.01)
g._accumulateAwakenedCharge(Play(runner=Pl(99), yardage=40, isPassCompletion=False), PlayType.Run)
expect("a run by a NON-tracked player adds nothing", 99 not in g._awakenedCharge)

print("\n2. Meter caps at the threshold and latches READY (no overflow)")
g._accumulateAwakenedCharge(Play(runner=RB, yardage=60, isPassCompletion=False), PlayType.Run)  # +72 -> caps
expect("charge caps at the threshold", abs(g._awakenedCharge[1] - AWAKENED_CHARGE_THRESHOLD) < 0.01)
expect("crossing the threshold latches ready", g._awakenedReady[1] is True)
g._accumulateAwakenedCharge(Play(runner=RB, yardage=20, isPassCompletion=False), PlayType.Run)
expect("a ready meter does not accumulate further", abs(g._awakenedCharge[1] - AWAKENED_CHARGE_THRESHOLD) < 0.01)

print("\n3. Kicker fast-charge (made FG only) + defensive stop charge")
g._accumulateAwakenedCharge(Play(kicker=K, isFgGood=True), PlayType.FieldGoal)
expect("made FG charges the kicker a fixed chunk", abs(g._awakenedCharge[2] - AWAKENED_CHARGE_KICKER) < 0.01)
g._accumulateAwakenedCharge(Play(runner=NOBODY, yardage=2, tackledBy=DEF), PlayType.Run)
expect("defensive playmaker stop charges a flat event", abs(g._awakenedCharge[3] - AWAKENED_CHARGE_DEF_EVENT) < 0.01)

print("\n4. _awakenedTryFire — ready + covered fires, resets, counts; otherwise no-op")
# RB (no_clip) is ready and no_clip covers 'run' -> fires.
fire = g._awakenedTryFire('run', RB)
expect("a ready player whose power covers the situation fires", fire and fire['power'] == 'no_clip' and fire['flavor'])
expect("firing resets the meter + clears ready", g._awakenedCharge[1] == 0.0 and g._awakenedReady[1] is False)
expect("firing counts a fire", g._awakenedFills[1] == 1)
expect("a discharged meter does not fire again", g._awakenedTryFire('run', RB) is None)
# DEF (pickpocket) is NOT ready (only 18 charge) -> no fire, no discharge.
expect("a not-ready player does not fire", g._awakenedTryFire('strip', DEF) is None and g._awakenedCharge[3] > 0)
# Make K ready, then test situation coverage: moonshot covers 'kick' but NOT 'pick'.
g._awakenedReady[2] = True
expect("a ready player does NOT fire on a situation its power doesn't cover", g._awakenedTryFire('pick', K) is None)
expect("...and that non-fire leaves the meter intact (still ready)", g._awakenedReady[2] is True)
expect("the same player fires on a covered situation", (g._awakenedTryFire('kick', K) or {}).get('power') == 'moonshot')

print("\n5. awakenedChargeState() exposure")
st = g.awakenedChargeState()
expect("state reports charge/pct/ready/fires/power", 1 in st and st[1]['fires'] == 1 and st[1]['power'] == 'no_clip' and 'ready' in st[1])

print()
if failures:
    print(f"FAILED ({len(failures)}): " + "; ".join(failures))
    raise SystemExit(1)
print("ALL AWAKENED CHARGE+FIRE TESTS PASS")
