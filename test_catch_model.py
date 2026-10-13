"""Contact, coverage and yards after catch — the shapes, not the levels.

Three defects lived here, and all three were the same kind: a model that stopped
responding in the region it is used most.

1. `baseContact` was piecewise and its slope fell from 1.6 to 0.45 at exactly throw
   quality 70. Short throws average 79 and medium 70.6, so 76% of all passes sat on that
   plateau and the two tiers came out 3.8 contact points apart against a real 14.6-point
   completion gap.
2. Coverage barely decided a catch, and then had the wrong SHAPE. A linear charge in
   openness (scaled by a depth ladder, short 0.40) left short completion at 63% blanketed
   and 75% wide open against the NFL's 41% and 88%. Real completion climbs over the first
   2-3 yards of separation and is flat beyond, because past arm's length the defender
   cannot reach the ball. Now a logistic in YARDS at arrival (BDB 2021), stronger the
   longer the ball hangs, with the secure step at the drop rate.
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
                       PASS_CONTEST_MID_YARDS, PASS_CONTEST_WIDTH_YARDS,
                       PASS_BREAKUP_BASE, PASS_BREAKUP_PER_AIR_YARD, PASS_SECURE_AT_MEAN,
                       PASS_SECURE_HANDS_SLOPE, GOAL_LINE_CONTEST_MID_YARDS,
                       GOAL_LINE_CATCH_CEILING_RATIO, OPENNESS_QUANTILES_SIM_BY_DEPTH,
                       ARRIVAL_SEPARATION_NFL_BY_DEPTH,
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
    # ⚠️ The bottom end is a RATIO, not a floor. It read `_contact(0) < 15`, a literal
    # picked when the curve's centre sat at 52; recalibrating the centre against live
    # rosters moved it to 16.6 and this failed while nothing it cares about had changed.
    # `calculateThrowQuality` clamps to `max(5, ...)` besides, so quality 0 never happens —
    # 5 is the worst throw the model can actually produce.
    assert _contact(100) < PASS_CONTACT_CEILING
    assert _contact(100) > 90, 'a perfectly placed ball should nearly always be reachable'
    assert _contact(5) < _contact(70) * 0.35, (
        f'the worst throw the model can make is {_contact(5):.0f} against a good one at '
        f'{_contact(70):.0f} — not nearly unreachable enough')


def _contest(sep, mid=PASS_CONTEST_MID_YARDS):
    return 1.0 / (1.0 + math.exp((sep - mid) / PASS_CONTEST_WIDTH_YARDS))


def _strength(tier):
    return min(1.0, PASS_BREAKUP_BASE + PASS_BREAKUP_PER_AIR_YARD * PASS_DEPTH_MEANS[tier])


def test_coverageActuallyDecidesTheCatch():
    """A defender on top of the receiver must break up a large share; the old linear
    charge on a short throw bought ~13 points across the whole range."""
    for tier in ('short', 'medium', 'long', 'deep'):
        span = (_contest(0.3) - _contest(6.0)) * _strength(tier)
        assert span > 0.45, f'{tier}: blanketed vs wide open is worth only {span:.2f}'


def test_theContestEndsPastArmsLength():
    """Past ~3 yards the NFL curve is flat: an open receiver pays for no defender."""
    assert _contest(4.0) < 0.05, f'a receiver 4 yards clear still loses {_contest(4.0):.2f}'
    assert _contest(0.5) > 0.6


def test_breakupStrengthGrowsWithFlightTime():
    vals = [_strength(t) for t in ('short', 'medium', 'long', 'deep')]
    assert vals == sorted(vals) and vals[-1] <= 1.0, vals


def test_anOpenReceiverCatchesAtTheDropRate():
    """Uncontested, the only miss is a drop: a few percent, single digits across hands."""
    assert PASS_SECURE_AT_MEAN >= 94
    assert 20 * PASS_SECURE_HANDS_SLOPE < 10, 'hands 64 to 84 should span single digits'


def test_theSameOpennessIsFewerYardsOnADeeperRoute():
    """NFL routes are tighter at release the deeper they run; openness is 'open for his
    route', so its median maps to fewer yards with depth. Tables must be monotonic."""
    meds = []
    for t in ('short', 'medium', 'long', 'deep'):
        sq, nq = OPENNESS_QUANTILES_SIM_BY_DEPTH[t], ARRIVAL_SEPARATION_NFL_BY_DEPTH[t]
        assert list(sq) == sorted(sq) and list(nq) == sorted(nq), f'{t} table not monotonic'
        assert len(sq) == len(nq)
        meds.append(nq[len(nq) // 2])
    assert meds == sorted(meds, reverse=True), f'median arrival separation by depth: {meds}'


def test_theGoalLineIsHarderToCatchIn():
    assert GOAL_LINE_CONTEST_MID_YARDS > PASS_CONTEST_MID_YARDS
    assert 0.8 < GOAL_LINE_CATCH_CEILING_RATIO < 1.0


def _yacBucket(tq, tier):
    placement = tq / (PASS_TYPE_DIFFICULTY[tier] or 1.0)
    return ('elite' if placement >= 80 else 'good' if placement >= 60
            else 'poor' if placement >= 40 else 'bad')


def test_aNormalDeepBallIsNotJudgedABadThrow():
    """The double-charge. A deep throw's quality is ALREADY multiplied down by
    PASS_TYPE_DIFFICULTY, so the raw number must not be read as poor placement — a
    typical deep ball measures tq ~23 and would bucket as `bad` without normalising."""
    typical = {'short': 79.0, 'medium': 53.0, 'long': 43.0, 'deep': 22.5}
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


def test_theDepthTiersStayOrdered():
    """PASS_TYPE_DIFFICULTY must fall with depth. It is NOT even per air yard: it is set
    so each depth's UNCONTESTED completion matches the NFL's (BDB 2021: 0.874 / 0.768 /
    0.682 / 0.454), and real football drops fastest in the first rung."""
    vals = [PASS_TYPE_DIFFICULTY[t] for t in ('short', 'medium', 'long', 'deep')]
    assert vals == sorted(vals, reverse=True), f'difficulty is not falling with depth: {vals}'


if __name__ == '__main__':
    passed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith('test_'):
            fn()
            passed += 1
            print(f'  ok  {name}')
    print(f'\n{passed} passed')
