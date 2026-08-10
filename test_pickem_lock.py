"""A pick closes at KICKOFF, not at the final whistle.

⚠️ THE OLD RULE MADE SENSE WHEN YOU PICKED ONE GAME AT A TIME. Picks stayed open until
Final, and the timing multiplier existed to price that: a pick made in Q3 was worth 40%
of a pre-game one. Once a reader could take a whole day's slate in advance, picking a
game already in progress stopped being a prediction and became watching the result
arrive, so kickoff is the line (owner, 2026-08-10).

The consequence worth pinning: every NEW pick is pre-game, so its timing multiplier is
always the full 1.0 and the only multiplier left is the underdog one. That is what makes
the page explainable — ten points times one number.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import managers  # noqa: F401  — breaks the api.main circular import
from api.main import _pickemPickable
from constants import PICKEM_QUARTER_MULTIPLIERS

SCHEDULED, ACTIVE, FINAL = 1, 2, 3


class PickemLockTests(unittest.TestCase):
    def testAScheduledGameIsPickable(self):
        self.assertTrue(_pickemPickable(SCHEDULED))

    def testALiveGameIsNotPickable(self):
        # THE CHANGE. This used to be allowed, at a reduced multiplier.
        self.assertFalse(_pickemPickable(ACTIVE))

    def testAFinalGameIsNotPickable(self):
        self.assertFalse(_pickemPickable(FINAL))

    def testAnUnknownStatusStaysPickable(self):
        # A game whose status has not resolved yet reads as pre-game rather than
        # locking a reader out of a slate that has not started.
        self.assertTrue(_pickemPickable(None))

    def testEveryPickableGamePaysTheFullTimingMultiplier(self):
        """The simplification the page's copy now relies on.

        If a pickable game could ever carry less than the full timing multiplier, the
        header's "10 points times that team's multiplier" would be a lie.
        """
        self.assertTrue(_pickemPickable(SCHEDULED))
        self.assertEqual(PICKEM_QUARTER_MULTIPLIERS.get(0, 1.0), 1.0)

    def testTheDecayTableSurvivesForOldPicks(self):
        # Picks made under the old rule keep what they earned, so the table must not
        # be deleted just because nothing new consumes it.
        for quarter in (1, 2, 3, 4):
            self.assertIn(quarter, PICKEM_QUARTER_MULTIPLIERS)
            self.assertLess(PICKEM_QUARTER_MULTIPLIERS[quarter], 1.0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
