"""Regression: the diamond rework (owner, 2026-10-07).

Measured in hands built for them (simcheck_effect_marginal.py PROBE_ARM=built), the
diamonds ranged from 14 to 110 FP a normal week against ~60 for the best non-diamond
synergy cards. The target is ~1.25x that. Three were redesigned because their partner
cards could not fill a lineup:

  * Sharpshooter doubled FIELD GOALS only, and one kicker slot held its only partner. It
    is now a precision amplifier: completions, well-placed throws, contested catches and
    field goals all count extra.
  * Advantage only raised the hit rate. A second roll that also hits now pays the
    jackpot again.
  * Catalyst raised odds, duplicating Advantage and Providence. It now enlarges every
    jackpot that hits, by how far its player clears a position-scaled baseline.

Run: python3 test_diamond_rework.py
"""
import unittest
from types import SimpleNamespace
from unittest import mock

import managers.cardEffects as ce
import managers.cardEffectCalculator as cec
from managers.cardEffectCalculator import calculateWeekCardBonuses, CardCalcContext

QB, RB, WR, TE, K = 1, 2, 3, 4, 5


def card(eqId, effectName, playerId, position, edition="diamond", rating=92, primary=None):
    cfg = ce.buildEffectConfig(edition, rating, position, forceEffect=effectName)
    cfg.pop("gate", None)
    if primary:
        cfg["primary"].update(primary)
    template = SimpleNamespace(effect_config=cfg, position=position, player_id=playerId,
                               player_rating=rating, edition=edition,
                               player_name=f"P{playerId}")
    return SimpleNamespace(id=eqId, user_card=SimpleNamespace(card_template=template, tier=1),
                           slot_number=eqId)


def run(cards, stats):
    ctx = CardCalcContext()
    ctx.userId, ctx.season, ctx.weekNumber = 1, 9, 10
    pids = {c.user_card.card_template.player_id for c in cards}
    ctx.rosterPlayerIds = set(pids)
    ctx.rosterPlayerPositions = {c.user_card.card_template.player_id: c.user_card.card_template.position
                                 for c in cards}
    ctx.rosterPlayerNames = {p: f"P{p}" for p in pids}
    ctx.weekPlayerStats = {p: stats.get(p, {"fantasyPoints": 20}) for p in pids}
    ctx.weekRawFP = sum(s.get("fantasyPoints", 0) for s in ctx.weekPlayerStats.values())
    res = calculateWeekCardBonuses(cards, ctx)
    return {b.effectName: b for b in res.cardBreakdowns}


QB_LINE = {"fantasyPoints": 25, "passing_stats": {"comp": 20, "goodThrows": 10, "att": 30}}


class SharpshooterIsPrecision(unittest.TestCase):

    def testItMultipliesCompletionsForAQbCard(self):
        cadence = card(1, "cadence", 101, QB, edition="metallic", rating=85)
        alone = run([cadence], {101: QB_LINE})["cadence"].totalFP
        withIt = run([cadence, card(2, "sharpshooter", 102, RB)],
                     {101: QB_LINE, 102: {"fantasyPoints": 25}})["cadence"].totalFP
        self.assertGreater(alone, 0)
        self.assertAlmostEqual(withIt, alone * 3, delta=1.0)

    def testItCountsEveryAccuracyStat(self):
        stats = {cat: set(fields) for cat, fields in cec.SHARPSHOOTER_STATS}
        self.assertEqual(stats, {"passing_stats": {"comp", "goodThrows"},
                                 "receiving_stats": {"contestedCatches"},
                                 "kicking_stats": {"fgs", "fgYards"}})


def _Rolls(rolls):
    """Stand-in for _AdvantageRNG.random: records `rolls` and returns the best."""
    rolls = sorted(rolls)

    def random(rng_self):
        if rng_self._record is not None:
            rng_self._record.append(rolls)
        return rolls[0]
    return random


HOUDINI_LINE = {"fantasyPoints": 25, "rushing_stats": {"runYards": 120, "brokenTackles": 3}}


class AdvantageDoubleJackpot(unittest.TestCase):

    def _houdini(self, rolls):
        hand = [card(1, "houdini", 101, RB, edition="prismatic", rating=85),
                card(2, "advantage", 102, QB)]
        with mock.patch.object(cec._AdvantageRNG, "random", _Rolls(rolls)):
            return run(hand, {101: HOUDINI_LINE, 102: {"fantasyPoints": 20}})["houdini"]

    def testTwoHitsPayTheJackpotTwice(self):
        one = self._houdini([0.01, 0.99, 0.99])
        two = self._houdini([0.01, 0.02, 0.99])
        self.assertTrue(one.chanceTriggered and two.chanceTriggered)
        miss = self._houdini([0.99, 0.99, 0.99])
        jackpot = one.totalFP - miss.totalFP
        self.assertGreater(jackpot, 0)
        self.assertAlmostEqual(two.totalFP, one.totalFP + jackpot, delta=0.2)
        self.assertIn("jackpot doubled", two.equation)

    def testTierOneRollsThree(self):
        cfg = ce.buildEffectConfig("diamond", 92, QB, forceEffect="advantage")
        self.assertEqual(cfg["primary"]["rollCount"], 3)


class _HitUnlessForcedMiss:
    def __call__(self, ctx, userCardId, seedExtra=""):
        return cec._ProjectionMissRNG() if ctx.projectionForceMiss else cec._ProjectionRNG()


class CatalystEnlargesJackpots(unittest.TestCase):

    def _houdini(self, catalystFP):
        hand = [card(1, "houdini", 101, RB, edition="prismatic", rating=85)]
        stats = {101: HOUDINI_LINE}
        if catalystFP is not None:
            hand.append(card(2, "catalyst", 102, QB))
            stats[102] = {"fantasyPoints": catalystFP}
        with mock.patch.object(cec, "_chanceRoll", _HitUnlessForcedMiss()):
            return run(hand, stats)["houdini"]

    def testABigGameEnlargesTheJackpot(self):
        plain = self._houdini(None)
        quiet = self._houdini(5)
        big = self._houdini(30)
        self.assertTrue(plain.chanceTriggered)
        self.assertAlmostEqual(quiet.totalFP, plain.totalFP, delta=0.1)
        self.assertGreater(big.totalFP, plain.totalFP)
        self.assertIn("Catalyst", big.equation)

    def testItNoLongerRaisesOdds(self):
        hand = [card(2, "catalyst", 102, QB)]
        ctx = CardCalcContext()
        ctx.userId, ctx.season, ctx.weekNumber = 1, 9, 10
        ctx.rosterPlayerIds = {102}
        ctx.rosterPlayerPositions = {102: QB}
        ctx.rosterPlayerNames = {102: "P102"}
        ctx.weekPlayerStats = {102: {"fantasyPoints": 40}}
        calculateWeekCardBonuses(hand, ctx)
        self.assertEqual(ctx.chanceBonus, 0.0)
        self.assertGreater(ctx.catalystJackpotBoost, 0.0)

    def testTheBaselineFollowsThePosition(self):
        qb = ce.buildEffectConfig("diamond", 92, QB, forceEffect="catalyst")["primary"]
        te = ce.buildEffectConfig("diamond", 92, TE, forceEffect="catalyst")["primary"]
        self.assertLess(te["baselineSolo"], qb["baselineSolo"])
        self.assertGreater(te["perFpPct"], qb["perFpPct"])


class SnakeEyesFollowsThePosition(unittest.TestCase):

    def testATeNeedsAWorseGameForEachTier(self):
        qb = ce.buildEffectConfig("diamond", 92, QB, forceEffect="snake_eyes")["primary"]["tiers"]
        te = ce.buildEffectConfig("diamond", 92, TE, forceEffect="snake_eyes")["primary"]["tiers"]
        self.assertEqual([m for _, m in qb], [m for _, m in te])
        for (tq, _), (tt, _) in zip(qb[1:], te[1:]):
            self.assertLess(tt, tq)


class DiamondSizing(unittest.TestCase):

    def testTheRunawaysAreTrimmedAndTheWeakLifted(self):
        def p(e):
            return ce.buildEffectConfig("diamond", 92, QB, forceEffect=e)["primary"]
        self.assertLess(p("doubler")["tdMult"], 2.0)
        self.assertGreater(p("conductor")["boostPct"], 40)
        for e, (factor, _) in ce._DIAMOND_SIZE.items():
            self.assertEqual(ce.EFFECT_EDITION_TIER[e], "diamond", e)


class TheTextFollowsTheNumbers(unittest.TestCase):

    def testTheStatAmplifierPillsQuoteTheMintedMultiplier(self):
        """The pills hardcoded "2x" / "3x"; Doubler mints at 1.71 and older Sharpshooters
        at 2.0, so the pill must read the card."""
        from managers.cardProjection import _amplifierDescription
        for effect, key in (("doubler", "tdMult"), ("surveyor", "yardMult"),
                            ("sharpshooter", "fgMult")):
            primary = ce.buildEffectConfig("diamond", 92, QB, forceEffect=effect)["primary"]
            self.assertIn(f"{primary[key]:g}x", _amplifierDescription(effect, primary, True), effect)
        old = {"fgMult": 2.0}
        self.assertIn("2x", _amplifierDescription("sharpshooter", old, True))

    def testNoTooltipQuotesARedesignedMultiplier(self):
        for effect in ("sharpshooter", "doubler"):
            self.assertNotRegex(ce.EFFECT_TOOLTIPS[effect], r"\d+x", effect)


if __name__ == "__main__":
    unittest.main()
