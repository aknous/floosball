"""Position-specific stats never land on the wrong-position card.

An effect that reads a position stat (carries=RB, receptions=WR/TE, completions=QB,
YAC=WR/TE, ...) must only ever mint on a card of a matching position — otherwise it
reads ~0 and the card is dead. Both hold today by construction (POSITION_EXCLUSIVE_POOLS); this locks it so a pool
edit can't break it. (Gates are now FP-based, so gate stats no longer vary by position.)

Run: .venv/bin/python test_card_position_stats.py
"""
import sys
sys.path.insert(0, '/Users/andrew/Projects/floosball')
import logging; logging.disable(logging.CRITICAL)
import random
from managers.cardEffects import (buildEffectConfig, POSITION_EXCLUSIVE_POOLS,
                                   SHARED_EFFECT_POOL)

failures = []
def expect(desc, cond):
    print(f"  [{'OK' if cond else 'FAIL'}] {desc}")
    if not cond:
        failures.append(desc)

# Effects that read a HARDCODED position stat -> the only position they may mint on.
POS_SPECIFIC = {
    'gunslinger': 1, 'air_raid': 1,                       # QB: pass yds / pass TDs
    'workhorse': 2, 'goal_line_vulture': 2,               # RB: carries / rush TDs
    'expedition': 2, 'stampede': 2,
    'possession': 3, 'trebuchet': 3, 'double_trouble': 3,  # WR: receptions / catches
    'slippery': 3, 'jailbreak': 3, 'ace_up_the_sleeve': 3,
    'safety_blanket': 4, 'industrious': 4,                # TE: receptions
    'three_pointer': 5, 'sniper': 5, 'leg_day': 5,        # K: FGs
}

print("1. Position-specific effects only ever mint on their matching position")
random.seed(7)
misplaced = set()
for pos in (1, 2, 3, 4, 5):
    for _ in range(400):
        en = buildEffectConfig('base', 80, pos)['effectName']
        if en in POS_SPECIFIC and POS_SPECIFIC[en] != pos:
            misplaced.add((en, pos))
expect(f"2000 random draws never cross positions  {misplaced or ''}", not misplaced)

print("2. No position-exclusive effect leaks into the shared (any-position) pool")
shared = {e['effectName'] if isinstance(e, dict) else e for e in SHARED_EFFECT_POOL}
leaked = {e for lst in POSITION_EXCLUSIVE_POOLS.values() for e in lst} & shared
expect(f"no exclusive effect in the shared pool  {leaked or ''}", not leaked)

print()
if failures:
    print(f">>> {len(failures)} FAILURE(S)")
    for f in failures:
        print("   -", f)
    sys.exit(1)
print("PASS — position stats stay on matching-position cards, effect and gate alike.")
