"""Regression: Group Project counts an amplifier when it amplified something.

⚠️ AMPLIFIERS PRODUCE NOTHING OF THEIR OWN, SO "PRODUCED OUTPUT" MISREAD ALL OF THEM.
Group Project (`bonus_round`) pays when 4+ OTHER cards triggered, and it counted a card
as triggered when its breakdown showed FP, Floobits or FPx. Captain, Conductor and the
stat amplifiers return an empty result and apply their boost later, so they never
counted; Lemons returns its multiplier as a MARKER and so counted almost every week. In a
high-end hand the amplifiers are the build, which left the card unusable there (owner,
2026-09-28: count them when they boosted something).

The count and the boosts share one definition per amplifier (`_lemonsTarget`,
`_conductorTargets`, `_captainTargets`), so the count cannot credit a boost that did not
happen. That consistency is asserted here, not just the count.

Run: python3 test_group_project_amplifiers.py
"""
import unittest
from types import SimpleNamespace

from managers.cardEffectCalculator import calculateWeekCardBonuses, CardCalcContext


def card(eqId, effectName, playerId, primary, position=2, gate=None):
    ec = {"effectName": effectName, "primary": primary, "position": position,
          "editionScale": 1.0}
    if gate is not None:
        ec["gate"] = {"threshold": gate}
    template = SimpleNamespace(effect_config=ec, position=position, player_id=playerId,
                               player_rating=80, edition="holographic",
                               player_name=f"Player{playerId}")
    return SimpleNamespace(id=eqId, user_card=SimpleNamespace(card_template=template, tier=1),
                           slot_number=eqId)


def freebie(eqId, playerId, fp=5.0):
    return card(eqId, "freebie", playerId, {"baseFP": fp})


def groupProject(eqId=99):
    return card(eqId, "bonus_round", 900, {"rewardValue": 30.0})


def run(cards, playerFP=10.0, tds=0):
    ctx = CardCalcContext()
    pids = {c.user_card.card_template.player_id for c in cards}
    ctx.rosterPlayerIds = set(pids)
    ctx.rosterPlayerPositions = {p: 2 for p in pids}
    ctx.weekPlayerStats = {p: {"fantasyPoints": playerFP, "rushing_stats": {"runTds": tds}}
                           for p in pids}
    ctx.rosterTotalTds = tds * len(pids)
    result = calculateWeekCardBonuses(cards, ctx)
    # Keyed by effect name for the one-of-a-kind cards; the filler Freebies share a name,
    # so they are also listed under "all" (keying them by name keeps only the last one).
    out = {b.effectName: b for b in result.cardBreakdowns}
    out["all"] = list(result.cardBreakdowns)
    return out


class AmplifiersCountWhenTheyBoosted(unittest.TestCase):

    def testAmplifiersCarryAHighEndHandOverTheLine(self):
        """Two paying cards plus three working amplifiers is five triggers. Under the old
        rule it was three (the two cards and Lemons' marker), short of four."""
        bds = run([freebie(1, 101), freebie(2, 102),
                   card(3, "captain", 103, {"perOvershootPct": 0.05}),
                   card(4, "conductor", 104, {"boostPct": 20}),
                   card(5, "double_down", 105, {"rewardValue": 2.5}),
                   groupProject()])
        gp = bds["bonus_round"]
        self.assertGreater(gp.primaryFP, 0, f"Group Project did not fire: {gp.equation}")
        self.assertIn("5/4", gp.equation)

    def testAnAmplifierWithNothingToBoostDoesNotCount(self):
        """Paying cards that pay nothing leave every amplifier idle, so none of them counts."""
        bds = run([freebie(1, 101, fp=0), freebie(2, 102, fp=0),
                   card(3, "captain", 103, {"perOvershootPct": 0.05}),
                   card(4, "conductor", 104, {"boostPct": 20}),
                   card(5, "double_down", 105, {"rewardValue": 2.5}),
                   groupProject()])
        gp = bds["bonus_round"]
        self.assertEqual(gp.primaryFP, 0)
        self.assertIn("0/4", gp.equation)

    def testCaptainBelowItsOwnBarDoesNotCount(self):
        """Captain boosts nothing when its own player misses the bar, so it is not a
        trigger either. Four other triggers without it would fire; three must not."""
        bds = run([freebie(1, 101), freebie(2, 102),
                   card(3, "captain", 103, {"perOvershootPct": 0.05}, gate=50),
                   card(5, "double_down", 105, {"rewardValue": 2.5}),
                   groupProject()])
        self.assertIn("didn't clear", bds["captain"].equation)
        self.assertIn("3/4", bds["bonus_round"].equation)

    def testLemonsCannotCountOnGroupProjectAlone(self):
        """If Group Project were Lemons' only target, crediting Lemons would let the two
        cards justify each other. Lemons needs another flat-FP card to multiply."""
        bds = run([card(1, "captain", 101, {"perOvershootPct": 0.05}),
                   card(5, "double_down", 105, {"rewardValue": 2.5}),
                   groupProject()])
        self.assertIn("0/4", bds["bonus_round"].equation)

    def testStatAmplifierCountsOnlyWhenItScaledSomething(self):
        base = [freebie(1, 101), freebie(2, 102), freebie(3, 103),
                card(4, "doubler", 104, {"tdMult": 2.0}), groupProject()]
        withTds = run(base, tds=1)["bonus_round"]
        noTds = run(base, tds=0)["bonus_round"]
        self.assertIn("4/4", withTds.equation)
        self.assertIn("3/4", noTds.equation)

    def testAdvantageCountsWhenAChanceCardHit(self):
        """Advantage makes every chance card roll twice and pays nothing itself, so it
        boosted something exactly when a chance card hit. Tested on the rule directly:
        chance rolls are seeded per user/week/card and cannot be steered from here."""
        from managers.cardEffectCalculator import CardBreakdown, _amplifierDidWork
        adv = CardBreakdown(effectName="advantage")
        hit = CardBreakdown(effectName="lucky_break", chanceTriggered=True, primaryFP=10.0)
        miss = CardBreakdown(effectName="lucky_break", chanceTriggered=False)
        ctx = CardCalcContext()
        self.assertTrue(_amplifierDidWork(adv, [miss, hit], ctx))
        self.assertFalse(_amplifierDidWork(adv, [miss], ctx))

    def testTheCountAgreesWithTheBoostsThatHappened(self):
        """Every amplifier Group Project credits must actually have boosted a card."""
        bds = run([freebie(1, 101), freebie(2, 102),
                   card(3, "captain", 103, {"perOvershootPct": 0.05}),
                   card(4, "conductor", 104, {"boostPct": 20}),
                   card(5, "double_down", 105, {"rewardValue": 2.5}),
                   groupProject()])
        self.assertRegex(bds["captain"].equation, r"amplified [1-9]")
        self.assertRegex(bds["conductor"].equation, r"on [1-9]")
        lemoned = [b for b in bds["all"] if "(Lemons)" in (b.equation or "")]
        self.assertEqual(len(lemoned), 1)
        self.assertNotEqual(lemoned[0].effectName, "bonus_round")


if __name__ == "__main__":
    unittest.main(verbosity=2)
