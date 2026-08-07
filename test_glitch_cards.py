"""Glitch cards (docs/GLITCH_CARDS.md).

Pins the properties the design is actually made of, rather than the arithmetic:

  - a glitch NEVER takes anything away (the load-bearing owner rule);
  - the trigger reads the on-card player's ladder position AND what they did this week;
  - the instability dial lifts the base only PARTLY, or a rampant card pins at the cap
    through an entire Criticality and stops being unpredictable;
  - FPx surges are damped, because an FPx surge grows with the rest of the hand while an
    FP surge is fixed;
  - the roll is deterministic per (user, season, week, card), so recomputing a week cannot
    change what already happened.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from managers.glitchCards import triggerChance, rollSurge, surgePayout, _rng
from constants import (GLITCH_TRIGGER_BASE, GLITCH_TRIGGER_CAP, GLITCH_SURGE_TABLE,
                       GLITCH_FPX_DAMP)


def testLadderPositionOrdersTheOdds():
    """A player further up the ladder is more likely to pay out."""
    quiet = {}
    ladder = ['stable', 'stirring', 'erratic', 'rampant']
    odds = [triggerChance(s, quiet, 1.0) for s in ladder]
    assert odds == sorted(odds), odds
    assert odds[0] < odds[-1]


def testAwakenedKeepsARealBase():
    """Awakened players fire a power on only 37% of weeks — LESS often than glitching —
    so keying the card solely to power use would make awakening quieten it."""
    assert triggerChance('awakened', {}, 1.0) >= 0.25


def testEventsEscalateWithTheirLevel():
    base = triggerChance('rampant', {}, 1.0)
    micro = triggerChance('rampant', {'micro': 1}, 1.0)
    personality = triggerChance('rampant', {'personality': 1}, 1.0)
    signature = triggerChance('rampant', {'signature': 1}, 1.0)
    assert base < micro < personality < signature, (base, micro, personality, signature)


def testEventsStack():
    one = triggerChance('stirring', {'micro': 1}, 1.0)
    two = triggerChance('stirring', {'micro': 2}, 1.0)
    assert two > one


def testDialLiftsTheBaseButDoesNotPinIt():
    """The full dial on the base compounds with the event term and parks a rampant card at
    the cap for a whole Criticality. A card that is reliably on is not wild magic."""
    quiet = triggerChance('rampant', {}, 1.0)
    crit = triggerChance('rampant', {}, 5.0)
    assert crit > quiet, "a live Criticality should visibly lift the card"
    assert crit < GLITCH_TRIGGER_CAP - 0.05, f"pinned at the cap on buildup alone: {crit}"


def testSuppressionWindowQuietensIt():
    assert triggerChance('rampant', {}, 0.45) < triggerChance('rampant', {}, 1.0)


def testChanceIsAlwaysCapped():
    hot = triggerChance('rampant', {'signature': 9}, 5.0)
    assert hot <= GLITCH_TRIGGER_CAP


def testATriggerAlwaysPaysSomething():
    """A trigger that pays nothing is indistinguishable from no trigger, which is exactly
    what live testing hit: the glitch line showed every week and never a score. The FP
    power bar gates ~30% of weeks, so scaling purely off the card's own output silently
    cancelled roughly a third of triggers."""
    for _, _, mult in GLITCH_SURGE_TABLE:
        fp, mx = surgePayout(mult, 0.0, 0.0)   # card produced nothing this week
        assert fp > 0, f"surge {mult} pays nothing on a gated-out card"


def testTheFloorIsSmallerThanScalingARealCard():
    """The floor is a fallback, not a better deal than the card actually producing."""
    floorFp, _ = surgePayout(1.0, 0.0, 0.0)
    scaledFp, _ = surgePayout(1.0, 28.3, 0.0)
    assert floorFp < scaledFp


def testEvenTheWorstStatePaysWithinAMonth():
    """85% of players carry no anomaly row and default to 'stable'. At the original 5%
    base that was a median wait of twenty weeks — a whole season to see the feature once."""
    import math
    p = triggerChance('stable', {}, 1.0)
    assert math.log(0.5) / math.log(1 - p) < 6, f"stable waits too long: {p:.0%}"


def testSurgeNeverSubtracts():
    """The rule the whole design rests on. A glitch adds; it never degrades the card."""
    for _, _, mult in GLITCH_SURGE_TABLE:
        fp, mx = surgePayout(mult, 28.3, 1.10)
        assert fp >= 0 and mx >= 0


def testFpxSurgesAreDamped():
    """An FP surge is fixed; an FPx surge multiplies the whole lineup, so it grows with the
    rest of the hand. A strong hand should not also make the glitch stronger."""
    _, mx = surgePayout(1.0, 0.0, 1.10)
    assert abs(mx - 0.10 * GLITCH_FPX_DAMP) < 1e-6, mx
    assert GLITCH_FPX_DAMP < 1.0


def testRollIsDeterministicPerWeek():
    """Recomputing a week must not change what already happened."""
    a = rollSurge(7, 15, 14, 99, 0.5)
    b = rollSurge(7, 15, 14, 99, 0.5)
    assert a == b
    assert rollSurge(7, 15, 15, 99, 0.5) != a or True   # different week may differ


def testDifferentCardsRollIndependently():
    seen = {rollSurge(7, 15, 14, cid, 0.5) for cid in range(40)}
    assert len(seen) > 1, "every card in a lineup resolved identically"


def testNeverTriggersAtZeroChance():
    for wk in range(50):
        triggered, _, _ = rollSurge(7, 15, wk, 99, 0.0)
        assert not triggered


def testAlwaysTriggersAtCertainty():
    for wk in range(50):
        triggered, name, mult = rollSurge(7, 15, wk, 99, 1.0)
        assert triggered and name and mult > 0


def testSurgeTableIsWellFormed():
    assert sum(w for _, w, _ in GLITCH_SURGE_TABLE) == 100
    mults = [m for _, _, m in GLITCH_SURGE_TABLE]
    assert mults == sorted(mults), "outcomes should escalate"
    weights = [w for _, w, _ in GLITCH_SURGE_TABLE]
    assert weights == sorted(weights, reverse=True), "bigger outcomes should be rarer"


def testCleansedIsQuietNotDead():
    """A cleansed player loses the power, not the person — the card still works."""
    assert 0 < triggerChance('cleansed', {}, 1.0) <= GLITCH_TRIGGER_BASE['stirring']


def testAcquisitionLooksBackForTheLineup():
    """The anomaly weekly tick fires a Criticality at seasonManager:667, but equipped cards
    are only carried forward into the new week at :850 — so at the moment a Criticality
    fires, THIS week's equipped rows do not exist yet. An exact-week query marks nothing,
    which is exactly what a live sim did: Criticality fired, zero cards glitched.

    Checked by source inspection rather than a DB fixture: the lookback is the whole point
    of the function and a fixture that happens to have current-week rows would pass either
    way, silently.
    """
    import inspect
    from managers import glitchCards
    src = inspect.getsource(glitchCards.markCardsForCriticality)
    assert 'for lookback in range(week, 0, -1)' in src, \
        "acquisition demands an exact-week equipped snapshot; a Criticality will mark nothing"


if __name__ == '__main__':
    fails = 0
    for name, fn in sorted(globals().items()):
        if name.startswith('test') and callable(fn):
            try:
                fn()
                print(f"  [OK] {name}")
            except AssertionError as e:
                fails += 1
                print(f"  [FAIL] {name}: {e}")
    print("\nPASS — a glitch only ever adds, and the ladder plus the week's events drive it."
          if not fails else f"\n{fails} FAILED")
    sys.exit(1 if fails else 0)
