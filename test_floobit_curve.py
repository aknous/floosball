"""The weekly FP -> Floobits curve tapers the tail without moving typical play.

⚠️ THE TAPER WAS WORKING AND THE TAIL WAS STILL RUNNING AWAY. Measured over 2,221 real
user-weeks (production, seasons 12+, post-card-rebalance): the power curve compresses an
FP spread of 30.7x (p50 261 FP, p99 8,006 FP) to 14.5x in Floobits, so the taper does its
job — but the absolute tail was p99 1,219 F and a max of 5,165 F for ONE week against a
median week of 84 F. A pack costs 40-100 F.

Two obvious levers are both wrong, which is the point of this file:

  SHARPENING THE EXPONENT applies from the first point, so it cannot touch the tail
  without dragging typical play with it — 0.78 -> 0.70 takes the median week 84 F -> 54 F
  and total payout to 56%. That undoes the deliberate ~2.3x lift the curve was given
  because playing fantasy earned ~830 F/season against ~5k from parking Floobit-output
  cards. The median is exactly what that lift was bought for.

  A HARD CAP was already tried and removed (`2bf171b`, "replace cap with log curve"). It
  makes every week past the cap pay identically, so a great week and an absurd week are
  indistinguishable and the reason to keep playing dies at the cap.

So: a second, harsher taper past a knee. Below the knee nothing changes at all; above it
each doubling of FP pays 2^0.45 instead of 2^0.78. Continuous and monotonic.

Run: .venv/bin/python test_floobit_curve.py
"""

import logging
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
logging.disable(logging.CRITICAL)

from constants import (  # noqa: E402
    WEEKLY_FP_FLOOBIT_EXPONENT, WEEKLY_FP_FLOOBIT_KNEE, WEEKLY_FP_FLOOBIT_SCALE,
    WEEKLY_FP_FLOOBIT_TAIL_EXPONENT, weeklyFpFloobits,
)

# Real percentiles of a user-week's FP, production seasons 12+ (n=2,221).
P25, P50, P75, P90, P99 = 130.0, 261.0, 703.0, 1696.0, 8006.0
OBSERVED_MAX = 50970.0


def oldCurve(fp):
    """What the curve paid before the knee — a single unbroken power taper."""
    return round(WEEKLY_FP_FLOOBIT_SCALE * (fp ** WEEKLY_FP_FLOOBIT_EXPONENT))


class TypicalPlayTests(unittest.TestCase):
    """⚠️ The whole constraint. Everything at or below the knee must be untouched."""

    def testEveryPercentileBelowTheKneeIsUnchanged(self):
        for name, fp in (('p25', P25), ('p50', P50), ('p75', P75)):
            self.assertLess(fp, WEEKLY_FP_FLOOBIT_KNEE,
                            f'{name} moved above the knee — re-derive this test')
            self.assertEqual(weeklyFpFloobits(fp), oldCurve(fp),
                             f'{name} changed; the knee is meant to bite only the tail')

    def testTheMedianWeekStillPaysWhatTheLiftBoughtIt(self):
        self.assertEqual(weeklyFpFloobits(P50), oldCurve(P50))

    def testTheKneeSitsBelowP90SoItBitesRoughlyTheTopDecile(self):
        self.assertLess(WEEKLY_FP_FLOOBIT_KNEE, P90)
        self.assertGreater(WEEKLY_FP_FLOOBIT_KNEE, P75)


class TailTests(unittest.TestCase):
    def testP99IsCutSubstantially(self):
        self.assertLess(weeklyFpFloobits(P99), oldCurve(P99) * 0.70,
                        'the p99 week should lose a real share of its payout')

    def testTheObservedMaximumIsCutHarderThanP99(self):
        """A harsher exponent compounds with distance, so the further out a week is, the
        more it gives up. That is the property a flat cap cannot have."""
        p99Ratio = weeklyFpFloobits(P99) / oldCurve(P99)
        maxRatio = weeklyFpFloobits(OBSERVED_MAX) / oldCurve(OBSERVED_MAX)
        self.assertLess(maxRatio, p99Ratio)

    def testP90BarelyMoves(self):
        """It sits just past the knee, so it should be nicked, not cut."""
        self.assertGreater(weeklyFpFloobits(P90), oldCurve(P90) * 0.90)


class ShapeTests(unittest.TestCase):
    def testItIsContinuousAtTheKnee(self):
        """Both branches must agree at the knee, or there is a step in the payout that a
        user can see by scoring one more point."""
        k = WEEKLY_FP_FLOOBIT_KNEE
        self.assertEqual(weeklyFpFloobits(k), oldCurve(k))
        self.assertLessEqual(abs(weeklyFpFloobits(k + 1) - weeklyFpFloobits(k)), 1)

    def testItIsStrictlyMonotonic(self):
        """⚠️ THE PROPERTY A HARD CAP GIVES UP. A bigger week must always be worth more,
        including far out in the tail."""
        prev = -1
        fp = 1.0
        while fp <= 200000:
            cur = weeklyFpFloobits(fp)
            self.assertGreaterEqual(cur, prev, f'payout fell going into {fp} FP')
            prev = cur
            fp *= 1.15
        self.assertGreater(weeklyFpFloobits(100000), weeklyFpFloobits(50000),
                           'the tail must still reward a bigger week')

    def testTheTailTaperIsActuallyHarsher(self):
        self.assertLess(WEEKLY_FP_FLOOBIT_TAIL_EXPONENT, WEEKLY_FP_FLOOBIT_EXPONENT)

    def testZeroAndNegativePayNothing(self):
        self.assertEqual(weeklyFpFloobits(0), 0)
        self.assertEqual(weeklyFpFloobits(-5), 0)

    def testItReturnsAnInt(self):
        for fp in (1, P50, P99, OBSERVED_MAX):
            self.assertIsInstance(weeklyFpFloobits(fp), int)


class SingleSourceTests(unittest.TestCase):
    def testSeasonManagerUsesTheSharedCurve(self):
        """The curve was inlined at its one call site. Anything that recomputes it by hand
        drifts the moment the shape changes — which is what this whole file is about."""
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            'managers', 'seasonManager.py')
        with open(path) as fh:
            src = fh.read()
        self.assertIn('weeklyFpFloobits(weekFp)', src)
        self.assertNotIn('WEEKLY_FP_FLOOBIT_SCALE * (weekFp', src,
                         'the curve is being recomputed inline again')


if __name__ == '__main__':
    unittest.main(verbosity=2)
