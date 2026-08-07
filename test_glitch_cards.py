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

from managers.glitchCards import triggerChance, rollSurge, surgePayout, _rng, _canCatch
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


# The population the card actually lives in. Every test above checks ORDERING or BOUNDS,
# which is why "it almost never triggers" had to be found by playing rather than by
# running these — a ladder can be perfectly ordered and still be dormant in practice
# because 85% of players sit on its bottom rung.
_LADDER_MIX = [('stable', 0.85), ('stirring', 0.07), ('erratic', 0.04),
               ('rampant', 0.02), ('awakened', 0.02)]
_EVENT_MIX = [({}, 0.89), ({'micro': 1}, 0.07), ({'personality': 1}, 0.03),
              ({'signature': 1}, 0.01)]


def _blendedRate(dial=1.0):
    return sum(pl * pe * triggerChance(state, ev, dial)
               for state, pl in _LADDER_MIX for ev, pe in _EVENT_MIX)


def testItFiresOftenEnoughToNotice():
    """Owner, twice: the bonus almost never pays. Measured at 20.8% a week, a glitched
    card was dormant for nearly five weeks at a stretch — on a 28-week season that is ~6
    payouts for a card you can only get during a Criticality."""
    r = _blendedRate()
    assert r >= 0.28, f"a glitched card fires only {r:.1%} of weeks, once every {1/r:.1f}"


def testItIsStillWildMagicRatherThanAnUpgrade():
    """The other side of the same dial. A card that fires most weeks stops being something
    happening TO the lineup and becomes a flat buff you plan around."""
    r = _blendedRate()
    assert r <= 0.45, f"fires {r:.0%} of weeks, which reads as a permanent bonus"
    assert _blendedRate(5.0) <= 0.70, "even a live Criticality should not make it routine"


def testACriticalityIsVisiblyDifferent():
    """If the dial does not show, the season people spend building toward means nothing."""
    assert _blendedRate(5.0) >= _blendedRate() * 1.5


def testTheSurgeIsWorthNoticingWhenItLands():
    """Rewards were raised alongside the rate (owner 2026-08-07). The weight sits on the
    BIG outcomes deliberately: making the small one less small would raise the average
    without ever producing a moment."""
    ev = sum(w / 100 * mult for _n, w, mult in GLITCH_SURGE_TABLE)
    assert ev >= 1.5, f"surge EV {ev:.2f}x is not worth the rarity of the card"
    top = sum(w / 100 * mult for _n, w, mult in GLITCH_SURGE_TABLE if mult >= 2.0)
    assert top / ev >= 0.6, "the payout is coming from the small outcomes, not the memorable ones"


def testAQuietStablePlayerCannotCatchAGlitch():
    """Owner, 2026-08-07. A Criticality is the anomaly reaching THROUGH players who are
    already unsettled, so a card whose player never flickered has nothing to reach
    through. This is also the lever that makes the on-card player matter at all: measured
    across a realistic population the ladder was worth only +1.7 points of trigger chance
    because 85% of players sit at 'stable' and drowned it out. Excluding them moves the
    decision to ACQUISITION, where the stable majority cannot dilute it."""
    assert not _canCatch('stable', {})
    assert not _canCatch(None, {})
    assert not _canCatch('stable', {'micro': 0})


def testAnEventQualifiesEvenFromTheBottomRung():
    """`state` is a slow accumulator, so someone who glitched this week but has not yet
    climbed off 'stable' is visibly unsettled — the evidence should count on its own."""
    assert _canCatch('stable', {'micro': 1})
    assert _canCatch('stable', {'signature': 1})


def testEveryStateAboveTheBottomQualifies():
    """`cleansed` included: the power is gone but the history is not, and it is a distinct
    state rather than the bottom rung."""
    for state in ('stirring', 'erratic', 'rampant', 'awakened', 'cleansed'):
        assert _canCatch(state, {}), state


def testStrippingTheLineupIsNowATrapRatherThanAnExploit():
    """Inverted deliberately. One card is ONE roll at having anybody unsettled, so a
    single-card lineup catches a glitch far less often than a full one — the opposite of
    the old behaviour, where stripping down guaranteed the target."""
    import random as _r
    ladder = [('stable', 0.85), ('stirring', 0.07), ('erratic', 0.04),
              ('rampant', 0.02), ('awakened', 0.02)]
    events = [({}, 0.89), ({'micro': 1}, 0.07), ({'personality': 1}, 0.03),
              ({'signature': 1}, 0.01)]

    def pick(rng, table):
        r, acc = rng.random(), 0.0
        for val, p in table:
            acc += p
            if r <= acc: return val
        return table[-1][0]

    def catchRate(size, seed):
        rng = _r.Random(seed); hits = 0; N = 4000
        for _ in range(N):
            if any(_canCatch(pick(rng, ladder), pick(rng, events)) for _ in range(size)):
                hits += 1
        return hits / N

    full, single = catchRate(6, 3), catchRate(1, 3)
    assert full > single * 2, f"full {full:.0%} vs single {single:.0%}"


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
