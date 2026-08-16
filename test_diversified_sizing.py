"""Diversified pays a COUNT, so it must be sized like one.

⚠️ THERE ARE ONLY THREE OUTPUT TYPES, AND A REAL HAND HOLDS NEARLY ALL OF THEM. Measured
over 4,000 hands sampled at real pack weights: 63% hold all three, 98% hold at least two,
mean 2.61. So "variety" is very nearly a free condition, and whatever this card mints is
collected ~2.6x over. It had been written as though it paid once.

At `holographic`'s EDITION_POWER_SCALE the old constants minted ~69.5/type at rating 85 —
a mean of 181 FP and a ceiling of 208. Measured in a hand of REAL cards: 144.5 mean /
208.5 p90 / 347.5 max, against a holographic median effect of 13.0 FP and a best mintable
peer around 47. It out-paid every PRISMATIC cross card several times over (Anthem 28.4,
Copycat 39.9, Last Resort 49.3), which is backwards — a rarer tier should pay more.

⚠️ THE SPREAD HARNESS CANNOT SEE THIS, WHICH IS WHY IT SURVIVED A BALANCE PASS.
`simcheck_effect_spread` fills the other five slots with no-effect floor prints, whose
output type is blank and (correctly) counts as nothing — so it scores this card at ONE
type and reported a tame 38.0 FP. Any card that reads the HAND has to be measured in a
hand. That instrument limitation is the real lesson here.

⚠️ It was not always wrong. Production's season-16 and season-17 templates carry
17.4-19.9 per type, which lands 52-60 FP at three types — squarely in the peer band. The
holographic EDITION_POWER_SCALE retune (0.47 -> 1.70, 2026-08-06) multiplied it 3.6x, and
a card that collects its constant 2.6x over is exactly where a global dial change does the
most damage.

⚠️ Values are FROZEN AT MINT, so this reaches newly-minted templates only. Templates
regenerate at the season boundary, so landing it before the next season starts applies it
uniformly with no migration. A mid-season deploy would leave that season's cards hot.

Run: .venv/bin/python test_diversified_sizing.py
"""

import logging
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
logging.disable(logging.CRITICAL)

from managers.cardEffects import (  # noqa: E402
    EFFECT_EDITION_TIER, EFFECT_REGISTRY, buildEffectConfig,
)
from managers.cardEffectCalculator import CardCalcContext  # noqa: E402

# Measured over 4,000 sampled hands at real pack weights (scratch harness). Held here as
# the constant the sizing is derived FROM, so a future reader can see the arithmetic.
MEAN_TYPES_IN_HAND = 2.61
MAX_TYPES = 3

# The band the card has to live in, from simcheck_effect_spread on real season-17
# rosters plus the cross-card measurement in a real hand.
HOLO_MEDIAN_EFFECT_FP = 13.0
PEER_CEILING_FP = 75.0     # best measured holographic effect of any kind


def perType(rating: int) -> float:
    cfg = buildEffectConfig('holographic', rating, 3, forceEffect='diversified')
    return cfg['primary']['perTypeFP']


class SizingTests(unittest.TestCase):
    def testMaxPayoutStaysInsideTheTierCeiling(self):
        """Three types is the card's ceiling, and 63% of hands reach it — so the CEILING
        is the number that has to be peer-sized, not the mean."""
        for rating in (70, 75, 85, 92):
            ceiling = perType(rating) * MAX_TYPES
            self.assertLessEqual(
                ceiling, PEER_CEILING_FP,
                f"rating {rating}: {ceiling:.1f} FP at three types exceeds the best "
                f"measured holographic effect ({PEER_CEILING_FP} FP)")

    def testExpectedPayoutBeatsTheTierMedianWithoutDwarfingIt(self):
        """It should be a good holographic, not a different game. The old build sat at
        ~181 FP expected against a 13.0 FP tier median — 14x."""
        for rating in (70, 85, 92):
            expected = perType(rating) * MEAN_TYPES_IN_HAND
            self.assertGreater(expected, HOLO_MEDIAN_EFFECT_FP,
                               'a holographic should beat the tier median')
            self.assertLess(
                expected, HOLO_MEDIAN_EFFECT_FP * 6,
                f"rating {rating}: {expected:.1f} FP expected is more than 6x the "
                f"{HOLO_MEDIAN_EFFECT_FP} FP tier median")

    def testItMatchesTheValuesProductionAlreadyMintedCorrectly(self):
        """Seasons 16 and 17 carry 17.4-19.9 per type. Those were measured-correct; the
        edition-scale retune is what moved them. Landing back in that band is the check
        that this is a restoration rather than a fresh guess."""
        for rating in (75, 85, 92):
            self.assertTrue(
                15.0 <= perType(rating) <= 22.0,
                f"rating {rating}: {perType(rating)}/type is outside the 15-22 band "
                f"production minted before the retune")

    def testItStillRewardsAHigherRatedPlayer(self):
        self.assertGreater(perType(92), perType(70),
                           'rating must still scale the payout')


class BehaviorTests(unittest.TestCase):
    """The count itself — unchanged by the resize, pinned so a future edit cannot
    quietly reintroduce the blank-type bug alongside a retune."""

    def _score(self, types):
        ctx = CardCalcContext()
        ctx.equippedCardOutputTypes = types
        primary = buildEffectConfig('holographic', 85, 3,
                                    forceEffect='diversified')['primary']
        return EFFECT_REGISTRY['diversified'](primary, ctx, 1, 1).fpBonus

    def testABlankIsNotAnOutputType(self):
        """The `base` no-effect floor print stores an empty outputType. Six of them plus
        one real card is ONE type, not two."""
        self.assertEqual(self._score(['', '', '', '', '', 'fp']),
                         self._score(['fp']))

    def testPayoutIsLinearInTheCount(self):
        one = self._score(['fp'])
        self.assertAlmostEqual(self._score(['fp', 'mult']), one * 2, places=1)
        self.assertAlmostEqual(self._score(['fp', 'mult', 'floobits']), one * 3, places=1)

    def testAnEmptyHandPaysNothing(self):
        self.assertEqual(self._score([]), 0)
        self.assertEqual(self._score(['', '']), 0)


class TierOrderTests(unittest.TestCase):
    def testItIsStillAHolographic(self):
        """The sizing above is written against the holographic band. If the card is ever
        moved up a tier the numbers here stop being the right target."""
        self.assertEqual(EFFECT_EDITION_TIER['diversified'], 'holographic')

    def testItDoesNotOutPayThePrismaticCrossCards(self):
        """A rarer tier should pay more. Anthem is the prismatic hand-composition card;
        measured at 28.4 mean / 76.5 max in a real hand."""
        anthem = buildEffectConfig('prismatic', 85, 3, forceEffect='anthem')['primary']
        self.assertLessEqual(
            perType(85) * MAX_TYPES, anthem['tier5FP'],
            'Diversified at its ceiling out-pays Anthem at its own — the tiers invert')


if __name__ == '__main__':
    unittest.main(verbosity=2)
