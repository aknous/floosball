"""Awakened (L4) powers — P2: per-game charge meter.

Verifies the meter accumulates impact-weighted involvement (yards on offense, a flat stop on defense,
a chunk per made FG), fills + resets at the threshold (counting fills), and only charges players in
the awakened set. No firing yet (P3).

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
RB, K, DEF, NOBODY = Pl(1), Pl(2), Pl(3), Pl(99)   # 99 = an awakened player NOT involved this play
g._awakenedCharge = {1: 0.0, 2: 0.0, 3: 0.0}
g._awakenedFills = {1: 0, 2: 0, 3: 0}
g._awakenedAbilities = {1: {'off': 'battering_ram', 'def': 'strip_score'}}

print("1. Offense charges by yards; only awakened players accrue")
g._accumulateAwakenedCharge(Play(runner=RB, yardage=50, isPassCompletion=False), PlayType.Run)
expect("50-yd run -> 50 * per_yard charge", abs(g._awakenedCharge[1] - 50 * AWAKENED_CHARGE_PER_YARD) < 0.01)
g._accumulateAwakenedCharge(Play(runner=Pl(99), yardage=40, isPassCompletion=False), PlayType.Run)
expect("a run by a NON-tracked player adds nothing", 99 not in g._awakenedCharge)
expect("negative/zero yardage adds nothing",
       (g._accumulateAwakenedCharge(Play(runner=RB, yardage=-3, isPassCompletion=False), PlayType.Run),
        abs(g._awakenedCharge[1] - 60.0) < 0.01)[1])

print("\n2. Meter fills + resets at the threshold, counting fills")
g._accumulateAwakenedCharge(Play(runner=RB, yardage=60, isPassCompletion=False), PlayType.Run)  # +72 -> 132
expect("crossing the threshold counts a fill and carries the remainder",
       g._awakenedFills[1] == 1 and abs(g._awakenedCharge[1] - (132 - AWAKENED_CHARGE_THRESHOLD)) < 0.01)

print("\n3. Kicker fast-charge (made FG only) + defensive stop charge")
g._accumulateAwakenedCharge(Play(kicker=K, isFgGood=True), PlayType.FieldGoal)
expect("made FG charges the kicker a fixed chunk", abs(g._awakenedCharge[2] - AWAKENED_CHARGE_KICKER) < 0.01)
g._accumulateAwakenedCharge(Play(kicker=K, isFgGood=False), PlayType.FieldGoal)
expect("missed FG adds nothing", abs(g._awakenedCharge[2] - AWAKENED_CHARGE_KICKER) < 0.01)
g._accumulateAwakenedCharge(Play(runner=NOBODY, yardage=2, tackledBy=DEF), PlayType.Run)
expect("defensive playmaker stop charges a flat event", abs(g._awakenedCharge[3] - AWAKENED_CHARGE_DEF_EVENT) < 0.01)

print("\n4. Pass completion splits QB / receiver")
g2 = Scenario().game
g2._awakenedCharge = {10: 0.0, 11: 0.0}; g2._awakenedFills = {10: 0, 11: 0}; g2._awakenedAbilities = {}
g2._accumulateAwakenedCharge(Play(passer=Pl(10), receiver=Pl(11), yardage=30, isPassCompletion=True), PlayType.Pass)
expect("QB gets the QB share", abs(g2._awakenedCharge[10] - 30 * AWAKENED_CHARGE_PER_YARD * AWAKENED_CHARGE_QB_SHARE) < 0.01)
expect("receiver gets the rest", abs(g2._awakenedCharge[11] - 30 * AWAKENED_CHARGE_PER_YARD * (1 - AWAKENED_CHARGE_QB_SHARE)) < 0.01)

print("\n5. awakenedChargeState() exposure")
st = g.awakenedChargeState()
expect("state reports charge/pct/fills/abilities for tracked players",
       1 in st and 'pct' in st[1] and st[1]['fills'] == 1 and st[1]['abilities'].get('off') == 'battering_ram')

print()
if failures:
    print(f"FAILED ({len(failures)}): " + "; ".join(failures))
    raise SystemExit(1)
print("ALL AWAKENED-CHARGE P2 TESTS PASS")
