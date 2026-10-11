"""Regression: Bonsai, Metronome and Snowball Fight, sized over a season (2026-10-07).

A carried streak cannot be priced one week at a time, so these were measured with
simcheck_streak_season.py, which drives the real week-end streak code (now the extracted
SeasonManager._prepareStreakContext / _advanceStreaks) over real players' seasons. Their
season averages ran 42-61 FP a week against ~25 for prismatic cards already at the top of
their band, and _BAND_TRIM brings them to it.

⚠️ METRONOME GREW ON ONE BAR AND PAID ON ANOTHER. Its streak condition read the flat
CARD_GATE_FP_THRESHOLDS (the metallic row) while its payout is gated on the card's own
prismatic bar, two points higher, so a week between the two grew the streak and paid 0.

Run: python3 test_streak_season_cards.py
"""
import unittest
from types import SimpleNamespace

import managers.cardEffects as ce
from managers.cardEffectCalculator import CardCalcContext
from managers.seasonManager import SeasonManager

QB = 1


def ctxFor(fp):
    ctx = CardCalcContext()
    ctx.rosterPlayerPositions = {7: QB}
    ctx.weekPlayerStats = {7: {"fantasyPoints": fp}}
    return ctx


class MetronomeUsesItsOwnBar(unittest.TestCase):

    def testAWeekBetweenTheTwoBarsDoesNotGrowTheStreak(self):
        cfg = ce.buildEffectConfig("prismatic", 85, QB, forceEffect="metronome")
        bar = ce.cardBarThreshold(cfg)
        from constants import CARD_GATE_FP_THRESHOLDS
        self.assertGreater(bar, CARD_GATE_FP_THRESHOLDS[QB])
        between = CARD_GATE_FP_THRESHOLDS[QB]
        self.assertFalse(ce.checkStreakCondition("metronome", ctxFor(between), 7, barThreshold=bar))
        self.assertTrue(ce.checkStreakCondition("metronome", ctxFor(bar), 7, barThreshold=bar))


class TheExtractedStreakPassesBehave(unittest.TestCase):

    def _eq(self):
        cfg = ce.buildEffectConfig("prismatic", 85, QB, forceEffect="metronome")
        tpl = SimpleNamespace(effect_config=cfg, player_id=7, position=QB)
        return SimpleNamespace(id=1, user_card=SimpleNamespace(card_template=tpl, tier=1),
                               streak_count=1, peak_output=None, weeks_since_break=0)

    def testMetronomeGrowsOnAHotWeekAndHoldsOnACold(self):
        sm = SeasonManager.__new__(SeasonManager)
        eq = self._eq()
        hot = ctxFor(40)
        hot.streakCounts = {1: 1}
        sm._prepareStreakContext([eq], hot, "")
        self.assertTrue(hot.liveStreakConditionsMet[1])
        sm._advanceStreaks([eq], hot, "", None)
        self.assertEqual(eq.streak_count, 2)
        cold = ctxFor(0)
        cold.streakCounts = {1: 2}
        sm._prepareStreakContext([eq], cold, "")
        sm._advanceStreaks([eq], cold, "", None)
        self.assertEqual(eq.streak_count, 2, "Metronome never resets on a cold week")


class TheStreakCardsAreTrimmed(unittest.TestCase):

    def testTheTrimReachesTheMintedValues(self):
        for effect, keys in (("bonsai", ("baseFP", "growthFP")),
                             ("metronome", ("baseReward", "growthPerTick")),
                             ("snowball_fight", ("baseReward", "growthPerTick"))):
            factor, trimmed = ce._BAND_TRIM[effect]
            self.assertLess(factor, 1.0, effect)
            self.assertEqual(set(trimmed), set(keys), effect)
            primary = ce.buildEffectConfig("prismatic", 85, QB, forceEffect=effect)["primary"]
            for k in keys:
                self.assertGreater(primary[k], 0, (effect, k))


if __name__ == "__main__":
    unittest.main()
