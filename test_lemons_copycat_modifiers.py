"""Regression: Lemons only multiplies when it is live, and Copycat is not doubled twice.

⚠️ LEMONS HAD A HARDCODED x2.5 FALLBACK (fixed 2026-10-07). `_applyTradeoffEffects` read
`primaryMult if primaryMult else 2.5`. A missed power bar leaves the multiplier at exactly
1.0, which "applied" x1.0 and tagged the target card "× 1.0 (Lemons)" (reported from prod,
season 8). Grounded zeroes it, and 0 fell through to the fallback, so the modifier that
disables FPx effects left Lemons paying a full, untiered x2.5.

⚠️ COPYCAT COPIED A FRENZY-DOUBLED VALUE AND WAS THEN DOUBLED AGAIN. It read the other
card's `totalFP`, which already carried the weekly modifier, and Frenzy doubled Copycat's
own output on top: a 4x copy. It now copies `preMatchFP`, the card's own output.

Run: python3 test_lemons_copycat_modifiers.py
"""
import unittest

from test_group_project_amplifiers import card, freebie
from managers.cardEffectCalculator import calculateWeekCardBonuses, CardCalcContext


def run(cards, modifier="", playerFP=10.0):
    ctx = CardCalcContext()
    pids = {c.user_card.card_template.player_id for c in cards}
    ctx.rosterPlayerIds = set(pids)
    ctx.rosterPlayerPositions = {p: 2 for p in pids}
    ctx.weekPlayerStats = {p: {"fantasyPoints": playerFP} for p in pids}
    ctx.activeModifier = modifier
    result = calculateWeekCardBonuses(cards, ctx)
    return result, {b.effectName: b for b in result.cardBreakdowns}


def lemons(gate=None):
    return card(5, "double_down", 105, {"rewardValue": 2.5}, gate=gate)


class LemonsIsLiveOrDoesNothing(unittest.TestCase):

    def testLemonsMultipliesTheLowestCard(self):
        _, bds = run([freebie(1, 101, fp=20.0), lemons()])
        self.assertAlmostEqual(bds["freebie"].totalFP, 50.0)
        self.assertIn("× 2.5 (Lemons)", bds["freebie"].equation)

    def testAMissedBarPaysNothingAndSaysSo(self):
        _, bds = run([freebie(1, 101, fp=20.0), lemons(gate=50)])
        self.assertAlmostEqual(bds["freebie"].totalFP, 20.0)
        self.assertNotIn("Lemons", bds["freebie"].equation)
        self.assertIn("didn't clear", bds["double_down"].equation)

    def testGroundedSwitchesLemonsOff(self):
        _, bds = run([freebie(1, 101, fp=20.0), lemons()], modifier="grounded")
        self.assertAlmostEqual(bds["freebie"].totalFP, 20.0)
        self.assertNotIn("Lemons", bds["freebie"].equation)
        self.assertIn("Grounded", bds["double_down"].equation)

    def testNothingToMultiplySaysSo(self):
        _, bds = run([freebie(1, 101, fp=0.0), lemons()])
        self.assertIn("No FP-earning cards", bds["double_down"].equation)

    def testTheMarkerNeverReachesTheLineupFPx(self):
        for mod in ("", "grounded", "amplify"):
            result, _ = run([freebie(1, 101, fp=20.0), lemons()], modifier=mod)
            self.assertEqual(result.multFactors, [], mod)


class CopycatIsDoubledOnce(unittest.TestCase):

    def testFrenzyDoublesTheCopyOnce(self):
        _, bds = run([freebie(1, 101, fp=50.0), card(2, "copycat", 102, {"_noParams": True})],
                     modifier="frenzy")
        self.assertAlmostEqual(bds["freebie"].totalFP, 100.0)
        self.assertAlmostEqual(bds["copycat"].totalFP, 100.0,
                               msg="Copycat copied the doubled value and was doubled again")

    def testAnOrdinaryWeekCopiesTheCard(self):
        _, bds = run([freebie(1, 101, fp=50.0), card(2, "copycat", 102, {"_noParams": True})])
        self.assertAlmostEqual(bds["copycat"].totalFP, 50.0)


if __name__ == "__main__":
    unittest.main()
