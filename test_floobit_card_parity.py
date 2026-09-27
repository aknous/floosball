"""A Floobit-card lineup must not out-earn an FP lineup by a multiple.

Users reported that equipping only Floobit cards earns far more than playing for FP and
leaderboard position, before counting what an FP hand costs to assemble. Measured on the
season-7 production snapshot: Floobit-heavy lineups netted +5,600 Floobits for the season
while FP-only lineups finished ~700-1,200 down. The gap was three cards, not the category:
Trust Fund (168 Floobits a card-week), Gold Rush (115) and Highlight Reel (85), against
18-45 for every other Floobit card. Two fixes:
  - those three brought back into that band (growth cap, and halved);
  - leaderboard prizes 5x, since the rank prize is what pays for competing on FP.

Run: .venv/bin/python test_floobit_card_parity.py
"""
import os
import sys
import types
import logging
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
logging.disable(logging.CRITICAL)

import constants  # noqa: E402
from managers.cardEffects import buildEffectConfig, _computeTrustFund  # noqa: E402

class TrustFundGrowthIsCapped(unittest.TestCase):
    def test_growth_stops_at_the_cap(self):
        p = {'baseFloobits': 20, 'growthPerWeek': 10}
        pay = lambda weeks: _computeTrustFund(p, types.SimpleNamespace(rosterUnchangedWeeks=weeks), None, None).floobits
        cap = constants.TRUST_FUND_GROWTH_WEEKS_CAP
        self.assertEqual(pay(cap), 20 + 10 * cap)
        self.assertEqual(pay(20), pay(cap), 'a season-long unchanged lineup must not keep growing')
        self.assertLess(pay(cap - 1), pay(cap), 'patience still pays up to the cap')


class GoldRushAndHighlightReelAreHalved(unittest.TestCase):
    """Pinned against the pre-change builders, measured at three ratings."""
    OLD = {'gold_rush': {70: 10, 85: 15, 95: 18}, 'highlight_reel': {70: 13, 85: 17, 95: 19}}
    KEY = {'gold_rush': 'perCardFloobits', 'highlight_reel': 'rewardValue'}

    def test_halved_within_rounding(self):
        from managers.cardEffects import EFFECT_EDITION_TIER
        for effect, byRating in self.OLD.items():
            for rating, old in byRating.items():
                new = buildEffectConfig(EFFECT_EDITION_TIER[effect], rating, 3,
                                        forceEffect=effect)['primary'][self.KEY[effect]]
                self.assertLessEqual(abs(new - old / 2), 1, f'{effect} @ {rating}: {new} vs old {old}')


class LeaderboardPaysForCompeting(unittest.TestCase):
    def test_prizes_are_the_5x_table(self):
        self.assertEqual(constants.WEEKLY_LEADERBOARD_PRIZES, {1: 150, 2: 100, 3: 75})
        self.assertEqual(constants.WEEKLY_LEADERBOARD_TOP_PCT_PRIZE, 30)
        self.assertEqual(constants.SEASON_LEADERBOARD_PRIZES, {1: 1000, 2: 650, 3: 400})
        self.assertEqual(constants.SEASON_LEADERBOARD_TOP_PCT_PRIZE, 150)

    def test_prizes_stay_ordered(self):
        for table in (constants.WEEKLY_LEADERBOARD_PRIZES, constants.SEASON_LEADERBOARD_PRIZES):
            self.assertGreater(table[1], table[2])
            self.assertGreater(table[2], table[3])
        self.assertGreater(constants.WEEKLY_LEADERBOARD_PRIZES[3], constants.WEEKLY_LEADERBOARD_TOP_PCT_PRIZE)
        self.assertGreater(constants.SEASON_LEADERBOARD_PRIZES[3], constants.SEASON_LEADERBOARD_TOP_PCT_PRIZE)


if __name__ == '__main__':
    unittest.main(verbosity=2)
