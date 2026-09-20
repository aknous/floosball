"""Contact, coverage and yards after catch — the shapes, not the levels.

Three defects lived here, and all three were the same kind: a model that stopped
responding in the region it is used most.

1. `baseContact` was piecewise and its slope fell from 1.6 to 0.45 at exactly throw
   quality 70. Short throws average 79 and medium 70.6, so 76% of all passes sat on that
   plateau and the two tiers came out 3.8 contact points apart against a real 14.6-point
   completion gap.
2. Coverage barely decided a catch. `PASS_COVERAGE_DISRUPTION_K` spanned ~14 points of
   contact across the WHOLE range from blanketed to wide open, so a receiver with a
   defender draped on him still caught 45%, and completion moved 8 points across the band
   holding 88% of throws.
3. `YAC_THROW_MULT` judged placement ABSOLUTELY. `PASS_TYPE_DIFFICULTY` has already cut a
   deep throw's quality for being deep, so reading the result as "badly thrown" charges
   for depth twice: a deep ball averages tq 32.6 and landed in the `bad` bucket on
   essentially every snap. Measured NFL yards after catch run 4.04 / 3.26 / 4.13 / 5.69 by
   tier — flat to RISING with depth, since a receiver who catches a deep ball is past the
   defense — while the sim ran 2.31 / 1.44 / 0.89 / -0.18, collapsing.

⚠️ These assert SHAPE (monotonic, continuous, responsive, correctly normalised). The
LEVELS belong to the harness, `playcall_nfl_check.py`, measured against real play-by-play.
A test that pins levels here would have to be rewritten by anyone retuning, which is how
a shape defect survives a calibration pass.
"""
import logging
import math
import sys
import types
import warnings

logging.disable(logging.CRITICAL)
warnings.filterwarnings('ignore')

if 'floosball_game' not in sys.modules:
    _stub = types.ModuleType('floosball_game')
    _stub.Game = type('G', (), {})
    sys.modules['floosball_game'] = _stub
    import managers.timingManager                                        # noqa: F401
    del sys.modules['floosball_game']

import floosball_game as FG                                              # noqa: E402
from constants import (PASS_CONTACT_CEILING, PASS_CONTACT_CENTER,        # noqa: E402
                       PASS_CONTACT_STEEPNESS, PASS_TYPE_DIFFICULTY,
                       PASS_COVERAGE_DISRUPTION_K, PASS_TIER_DISRUPTION,
                       YAC_THROW_MULT, PASS_DEPTH_MEANS)


def _contact(tq):
    return PASS_CONTACT_CEILING / (1.0 + math.exp(-PASS_CONTACT_STEEPNESS * (tq - PASS_CONTACT_CENTER)))


def test_contactRisesSmoothlyWithThrowQuality():
    """No corner. The old form's slope fell 1.6 -> 0.45 at tq 70, which is where short
    (79) and medium (70.6) both live."""
    xs = list(range(0, 101))
    ys = [_contact(x) for x in xs]
    assert ys == sorted(ys), 'contact is not monotonic in throw quality'
    slopes = [ys[i + 1] - ys[i] for i in range(len(ys) - 1)]
    worst = max(abs(slopes[i + 1] - slopes[i]) for i in range(len(slopes) - 1))
    assert worst < 0.05, f'contact has a slope discontinuity of {worst:.3f}'


def test_contactStillRespondsWhereMostThrowsLand():
    """The measured failure: between a typical medium throw and a typical short one the
    model must move enough to express that they are different plays."""
    assert _contact(79) - _contact(70) > 3.0, (
        f'short {_contact(79):.1f} vs medium {_contact(70):.1f} — the plateau is back')


def test_contactSaturatesWithoutReachingCertainty():
    assert _contact(100) < PASS_CONTACT_CEILING
    assert _contact(100) > 90, 'a perfectly placed ball should nearly always be reachable'
    assert _contact(0) < 15, 'a ball thrown nowhere should nearly never be'


def test_coverageActuallyDecidesTheCatch():
    """Blanketed vs wide open has to be worth a real share of the catch. Under the old
    K=15 the whole range bought 4.3 contact points at short and 12.4 at deep, so a
    receiver with a defender draped on him still caught 45%.
    ⚠️ The bar is per tier and deliberately LOW for short: `PASS_TIER_DISRUPTION` prices a
    quick release at 0.40 on purpose, so that a trailing offense can still move the ball
    underneath against tight coverage. It is the DEEP end that has to be decisive."""
    spans = {}
    for tier in ('short', 'medium', 'long', 'deep'):
        mult = PASS_TIER_DISRUPTION[tier]
        blanketed = (100 - 0) / 100 * 0.80 * PASS_COVERAGE_DISRUPTION_K * mult
        wideOpen = (100 - 90) / 100 * 0.80 * PASS_COVERAGE_DISRUPTION_K * mult
        spans[tier] = blanketed - wideOpen
        assert spans[tier] > 14, f'{tier}: coverage spans only {spans[tier]:.1f} contact points'
    assert spans['deep'] > 35, f"deep coverage spans only {spans['deep']:.1f} contact points"


def test_coverageBitesHarderTheDeeperTheThrow():
    tiers = ['short', 'medium', 'long', 'deep']
    mults = [PASS_TIER_DISRUPTION[t] for t in tiers]
    assert mults == sorted(mults), f'tier disruption is not increasing with depth: {mults}'


def _yacBucket(tq, tier):
    placement = tq / (PASS_TYPE_DIFFICULTY[tier] or 1.0)
    return ('elite' if placement >= 80 else 'good' if placement >= 60
            else 'poor' if placement >= 40 else 'bad')


def test_aNormalDeepBallIsNotJudgedABadThrow():
    """The double-charge. A deep throw's quality is ALREADY multiplied down by
    PASS_TYPE_DIFFICULTY, so the raw number must not be read as poor placement — a
    typical deep ball measures tq ~33 and would bucket as `bad` without normalising."""
    typical = {'short': 79.0, 'medium': 62.0, 'long': 49.0, 'deep': 33.0}
    for tier, tq in typical.items():
        assert _yacBucket(tq, tier) in ('good', 'elite'), (
            f'a typical {tier} throw (tq {tq}) buckets as {_yacBucket(tq, tier)!r}')


def test_theSameQbThrowingWellScoresTheSameAtEveryDepth():
    """Normalisation means 'well thrown FOR THIS KIND of throw', so an equally good
    ball reads the same whatever its depth."""
    buckets = {t: _yacBucket(80.0 * PASS_TYPE_DIFFICULTY[t], t)
               for t in ('short', 'medium', 'long', 'deep')}
    assert len(set(buckets.values())) == 1, f'same placement, different buckets: {buckets}'


def test_aCompetentThrowKeepsMostOfItsYardsAfterCatch():
    assert YAC_THROW_MULT['good'] >= 0.9, (
        'a catchable, competently placed ball should not cost a quarter of the YAC')
    ladder = [YAC_THROW_MULT[k] for k in ('bad', 'poor', 'good', 'elite')]
    assert ladder == sorted(ladder), f'YAC multiplier ladder is not monotonic: {ladder}'


def test_theDepthTiersStayOrderedAndSpaced():
    """PASS_TYPE_DIFFICULTY must fall with depth, and the short->medium rung was the one
    that had drifted — 0.016 per air yard against 0.031 and 0.022 for the rungs above it,
    which is why medium completed nearly as often as short."""
    order = ['short', 'medium', 'long', 'deep']
    vals = [PASS_TYPE_DIFFICULTY[t] for t in order]
    assert vals == sorted(vals, reverse=True), f'difficulty is not falling with depth: {vals}'
    slopes = [(vals[i] - vals[i + 1]) / (PASS_DEPTH_MEANS[order[i + 1]] - PASS_DEPTH_MEANS[order[i]])
              for i in range(3)]
    assert max(slopes) / min(slopes) < 2.0, (
        f'difficulty per air yard is uneven across the ladder: '
        f'{[round(s, 4) for s in slopes]}')


if __name__ == '__main__':
    passed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith('test_'):
            fn()
            passed += 1
            print(f'  ok  {name}')
    print(f'\n{passed} passed')
