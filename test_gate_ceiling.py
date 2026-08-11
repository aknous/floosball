"""The ceiling assumes the gate clears.

⚠️ THE OPTIMISTIC PASS ROLLED THE GATE ON/OFF AGAINST AN INFLATED AVERAGE. `gateRatio`
only special-cased the EXPECTED projection; the optimistic variant fell through to the
LIVE branch, which tests the depicted player's weekly FP against the threshold. In the
peak context that FP is the season average scaled by `_PEAK_STAT_INFLATION` (1.75) — so a
player whose inflated average still misses the bar gated to a hard 0.0, the peak breakdown
came back empty, and `bestCaseFP = max(expected, 0)` pinned the ceiling to the EXPECTED
value.

Reported as an Odometer reading "up to 0.8 FP". Measured on template 457: the player
averages 5.6 FP against a threshold of 12 (inflated 9.8, still short), while the effect
itself computed 16.0 at peak stats. His real weeks include 12, 12 and 11 — the bar IS
cleared in practice. The ceiling was 19x too low.

The ceiling answers "what does this pay when the week goes well", and clearing the bar is
part of the week going well, not a hurdle standing in front of it.

⚠️ `max(expected, peak)` downstream is why this looked like a MISSING range rather than a
wrong number, and why it sat. Over a 160-card sample, 114 were gated and 1 was pinned —
rare, because most players clear their bar once inflated, and worst precisely where the
card is already marginal.

Run: .venv/bin/python test_gate_ceiling.py
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import logging
logging.disable(logging.CRITICAL)

import managers  # noqa: F401  — breaks the floosball_game circular import
from managers import cardEffects as ce
from managers.cardEffectCalculator import CardCalcContext

GATE = {'threshold': 12, 'inverse': False, 'allPro': False,
        'text': 'Unlocks once this player reaches 12 FP'}
INVERSE_GATE = dict(GATE, inverse=True)
PLAYER = 39

# The reported player: two weeks of 16 clear a 12 FP bar.
HISTORY = [6, 5, 4, 10, 12, 2, 2, 6, 7, 2, 12, 4, 4, 1, 2, 11]


def _ctx(variant, weeklyFP=9.8):
    """`weeklyFP` is what the LIVE branch would read — the peak context's inflated
    season average. 9.8 is the reported card's 5.6 x 1.75, deliberately UNDER the bar."""
    ctx = CardCalcContext(userId=1, season=1, weekNumber=5)
    ctx.isProjection = True
    ctx.projectionVariant = variant
    ctx.weekPlayerStats = {PLAYER: {'fantasyPoints': weeklyFP}}
    ctx.playerWeeklyFP = {PLAYER: list(HISTORY)}
    return ctx


class GateCeilingTests(unittest.TestCase):
    def testTheCeilingClearsAGateTheInflatedAverageWouldMiss(self):
        """THE REGRESSION, at the exact numbers it was reported with."""
        self.assertEqual(ce.gateRatio(GATE, _ctx('optimistic'), PLAYER), 1.0,
                         'the ceiling still fails the gate on an inflated average, so it '
                         'collapses back to the expected value and no range is shown')

    def testTheCeilingClearsEvenAtZeroProduction(self):
        """A player with no recorded FP at all still has a ceiling — the gate is part of
        the good case by definition."""
        self.assertEqual(ce.gateRatio(GATE, _ctx('optimistic', weeklyFP=0.0), PLAYER), 1.0)

    def testAnInverseGateAlsoClearsAtTheCeiling(self):
        """⚠️ Latent — `_INVERSE_GATE_EFFECTS` is empty today. An inverse card is ON while
        FP stays UNDER the bar, and inflating FP is exactly what fails it, so such a card
        could never have shown a ceiling. Covered before one ships."""
        self.assertEqual(
            ce.gateRatio(INVERSE_GATE, _ctx('optimistic', weeklyFP=99.0), PLAYER), 1.0)

    def testTheExpectedValueStillUsesTheEmpiricalClearRate(self):
        """The fix must not touch the expected pass — that is where the honest number
        lives. Two of sixteen weeks clear the bar, Laplace-smoothed to 3/18."""
        ratio = ce.gateRatio(GATE, _ctx('expected'), PLAYER)
        self.assertAlmostEqual(ratio, 3 / 18, places=6)

    def testTheExpectedValueIgnoresTheInflatedAverage(self):
        """It reads history, not this week's stat line — so the peak inflation cannot
        leak into it."""
        self.assertAlmostEqual(ce.gateRatio(GATE, _ctx('expected', weeklyFP=999.0), PLAYER),
                               3 / 18, places=6)

    def testLiveScoringIsUntouched(self):
        """⚠️ Live is a real on/off switch and must stay one — a fractional or forced gate
        in live scoring would pay a card that never fired."""
        live = CardCalcContext(userId=1, season=1, weekNumber=5)
        live.weekPlayerStats = {PLAYER: {'fantasyPoints': 9.8}}
        self.assertEqual(ce.gateRatio(GATE, live, PLAYER), 0.0)
        live.weekPlayerStats = {PLAYER: {'fantasyPoints': 12.0}}
        self.assertEqual(ce.gateRatio(GATE, live, PLAYER), 1.0)
        live.weekPlayerStats = {}
        self.assertEqual(ce.gateRatio(GATE, live, PLAYER), 0.0)

    def testAnUngatedCardIsAlwaysOn(self):
        for variant in ('expected', 'optimistic'):
            self.assertEqual(ce.gateRatio({'threshold': 0}, _ctx(variant), PLAYER), 1.0)


class CeilingOrderingTests(unittest.TestCase):
    """The property the range has to satisfy, stated directly: for a gated card the
    ceiling is what it pays when the gate clears, which is never below the expected
    value."""

    def testTheCeilingIsNeverBelowTheExpectedRatio(self):
        for weeklyFP in (0.0, 5.0, 9.8, 12.0, 40.0):
            expected = ce.gateRatio(GATE, _ctx('expected', weeklyFP), PLAYER)
            ceiling = ce.gateRatio(GATE, _ctx('optimistic', weeklyFP), PLAYER)
            self.assertGreaterEqual(ceiling, expected, f'weeklyFP={weeklyFP}')


if __name__ == '__main__':
    unittest.main(verbosity=2)
