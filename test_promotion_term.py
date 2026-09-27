"""A promoted prospect signs for at least the seasons he had left in the pipeline.

Reported: a team promoted a 2-star prospect and gave him a ONE-year deal. The first
contract keys on today's tier (D -> 1 season), so the club could let him walk after a
year and his development would happen for somebody else. In the pipeline he was the
club's for the rest of his window; promoting him must not hand that back early.

Run: .venv/bin/python test_promotion_term.py
"""

import os
import sys
import types
import logging
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
logging.disable(logging.CRITICAL)

import floosball_player as FloosPlayer  # noqa: E402
from constants import PROSPECT_DEVELOPMENT_WINDOW  # noqa: E402
from managers.playerManager import PlayerManager  # noqa: E402


def _prospect(tier, seasonsIn):
    return types.SimpleNamespace(playerTier=tier, seasonsPlayed=0, prospect_seasons=seasonsIn)


class PromotionTermTest(unittest.TestCase):
    def setUp(self):
        self.pm = PlayerManager.__new__(PlayerManager)   # the term logic needs no state
        self.pm.db_session = None

    def test_two_star_draftee_gets_his_whole_window(self):
        p = _prospect(FloosPlayer.PlayerTier.TierD, 0)
        self.assertEqual(self.pm._getPlayerTerm(p), 1)          # the bug: a 1-year deal
        self.assertEqual(self.pm.promotionTerm(p), PROSPECT_DEVELOPMENT_WINDOW)

    def test_floor_is_seasons_left_not_the_full_window(self):
        for seasonsIn in range(PROSPECT_DEVELOPMENT_WINDOW):
            p = _prospect(FloosPlayer.PlayerTier.TierD, seasonsIn)
            self.assertEqual(self.pm.promotionTerm(p),
                             max(1, PROSPECT_DEVELOPMENT_WINDOW - seasonsIn))

    def test_a_longer_rookie_deal_is_not_shortened(self):
        p = _prospect(FloosPlayer.PlayerTier.TierS, PROSPECT_DEVELOPMENT_WINDOW - 1)
        self.assertEqual(self.pm.promotionTerm(p), self.pm._getPlayerTerm(p))


if __name__ == '__main__':
    unittest.main(verbosity=2)
