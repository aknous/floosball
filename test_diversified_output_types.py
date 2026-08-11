"""A blank is not an output type.

⚠️ THE `standard` NO-EFFECT FLOOR PRINT STORES `outputType: ''`, and Diversified counted
that empty string as a type of its own. `set(ctx.equippedCardOutputTypes)` over a hand of
six starter prints plus one flat-FP card returns `{'', 'fp'}` — TWO unique output types —
so the card paid double for a hand carrying no output diversity whatsoever. That is the
reverse of what it is for.

Measured on a live database: 192 of 722 templates carry the blank, so this reached any
hand holding a starter print, which is most new readers' hands.

Reported from the shop: a card reading "+65.7 FP per unique output type" projecting
"+87.6 FP, up to +131.4 FP". 131.4 is 2 x 65.7, and 87.6 is that ceiling weighted by the
gate — but the payout is DISCRETE, so no real week could ever land on 87.6. The ceiling
now reads 65.7 exactly, which is the card text.

⚠️ The other three readers of that list — `anthem` ("fp"), `gold_rush` ("floobits"),
`stacked_deck` ("mult") — each test for one NAMED type, so a blank never matched them and
they were not affected. That asymmetry is why this survived: only the effect that asks how
MANY distinct types there are can be fooled by a type that isn't one.

Run: .venv/bin/python test_diversified_output_types.py
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

PER_TYPE = 10.0
PRIMARY = {'perTypeFP': PER_TYPE}


def _bonus(outputTypes):
    ctx = CardCalcContext(userId=1, season=1, weekNumber=5)
    ctx.equippedCardOutputTypes = list(outputTypes)
    return ce.EFFECT_REGISTRY['diversified'](PRIMARY, ctx, 1, 1).fpBonus


class DiversifiedTests(unittest.TestCase):
    def testTheStarterHandDoesNotManufactureAType(self):
        """THE REGRESSION, in the hand it was reported from: six no-effect prints and one
        flat-FP card is ONE output type, not two."""
        hand = ['', '', '', '', '', '', 'fp']
        self.assertEqual(_bonus(hand), PER_TYPE,
                         'the blank output type of a no-effect card is still being '
                         'counted, so the card pays double for an undiversified hand')

    def testAHandOfNothingButBlanksPaysNothing(self):
        """A lineup of starter prints has no output at all. It used to score a full type
        for the emptiness."""
        self.assertEqual(_bonus(['', '', '', '', '', '']), 0.0)

    def testAGenuinelyDiverseHandStillCountsEveryType(self):
        """The fix must not cost a real hand its count — this is the payout the card
        exists for."""
        self.assertEqual(_bonus(['fp', 'mult', 'floobits']), PER_TYPE * 3)
        self.assertEqual(_bonus(['fp', 'fp', 'mult', 'mult', 'floobits', '']),
                         PER_TYPE * 3)

    def testDuplicatesStillCountOnce(self):
        self.assertEqual(_bonus(['fp', 'fp', 'fp', 'fp']), PER_TYPE)

    def testAnEmptyOrMissingListIsSafe(self):
        """`equippedCardOutputTypes` defaults to an empty list, and the effect can be
        computed before the hand is built."""
        self.assertEqual(_bonus([]), 0.0)
        ctx = CardCalcContext(userId=1, season=1, weekNumber=5)
        ctx.equippedCardOutputTypes = None
        self.assertEqual(ce.EFFECT_REGISTRY['diversified'](PRIMARY, ctx, 1, 1).fpBonus, 0.0)

    def testTheCeilingIsAWholeMultipleOfTheCardText(self):
        """The card promises a payout per type, so every reachable payout is a whole
        multiple of it. That is what made the reported 131.4 checkable as wrong."""
        for hand in (['fp'], ['fp', 'mult'], ['fp', 'mult', 'floobits'],
                     ['', '', 'fp'], ['', 'mult', 'floobits']):
            bonus = _bonus(hand)
            self.assertAlmostEqual(bonus / PER_TYPE, round(bonus / PER_TYPE), places=6,
                                   msg=f'{hand} pays a fraction of a type')
            self.assertLessEqual(bonus, PER_TYPE * 3,
                                 f'{hand} exceeds the three real output types')


class OtherReadersTests(unittest.TestCase):
    """The three effects that read the same list were NOT affected, and must stay that
    way — each asks for one named type, which a blank can never be."""

    def testAnthemCountsOnlyRealFlatFPCards(self):
        ctx = CardCalcContext(userId=1, season=1, weekNumber=5)
        ctx.equippedCardOutputTypes = ['', '', '', 'fp', 'fp', 'fp']
        primary = {'tier3FP': 25, 'tier4FP': 35, 'tier5FP': 50}
        self.assertEqual(ce.EFFECT_REGISTRY['anthem'](primary, ctx, 1, 1).fpBonus, 25,
                         'a blank is being counted as a flat-FP card')

    def testGoldRushCountsOnlyRealFloobitsCards(self):
        ctx = CardCalcContext(userId=1, season=1, weekNumber=5)
        ctx.equippedCardOutputTypes = ['', '', 'floobits', 'floobits']
        # Its own card is subtracted, leaving one other floobits card.
        self.assertEqual(
            ce.EFFECT_REGISTRY['gold_rush']({'perCardFloobits': 3}, ctx, 1, 1).floobits, 3)

    def testStackedDeckCountsOnlyRealMultCards(self):
        """Blanks give it nothing to compound with, so it stays neutral — and the same
        hand with those blanks made real does compound, which is what proves the blanks
        were the reason rather than the maths."""
        def stacked(hand):
            ctx = CardCalcContext(userId=1, season=1, weekNumber=5)
            ctx.equippedCardOutputTypes = hand
            return ce.EFFECT_REGISTRY['stacked_deck']({'perCardMult': 0.1}, ctx, 1, 1).multBonus

        self.assertEqual(stacked(['', '', 'mult']), 1.0,
                         'a blank is being compounded as a multiplier card')
        self.assertGreater(stacked(['mult', 'mult', 'mult']), 1.0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
