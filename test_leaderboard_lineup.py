"""A leaderboard row shows one moment, not two.

⚠️ REPORTED FROM PRODUCTION with screenshots. A user's lineup read
"Frig Lagotis / Gold Rush", the leaderboard showed the same row as
"Frig Lagotis / Battering Ram", and an earlier capture of that row showed
"Locust Clambake / Battering Ram". Three different answers for one slot.

The cause was that the two halves of the row came from different points in time. The
PLAYERS were taken from the LIVE equipped set (`equippedByUser`), while `cardBreakdowns`
for a banked week come from the stored record — the cards that actually scored. Change a
card after a week banks and the row pairs today's player with that week's effect.

The rule this pins: once a week's bonus is banked the week is settled, so the row uses
the lineup that was persisted for it. Only an unbanked week reads live equipment.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def chooseLineup(isCurrentSeason, banked, persistedWeek, liveEquipped):
    """The selection exactly as fantasyTracker runs it.

    Kept as a pure function here because the surrounding assembly needs a season, a
    database and ten collaborating maps; the DECISION is the part that was wrong.
    """
    if isCurrentSeason and not (banked and persistedWeek):
        return liveEquipped
    return persistedWeek


LIVE = [('eqNew', 'Frig Lagotis')]
BANKED = [('eqOld', 'Locust Clambake')]


class LeaderboardLineupTests(unittest.TestCase):
    def testABankedWeekUsesTheLineupThatPlayed(self):
        """THE REGRESSION. The card is historic, so the player must be too."""
        self.assertEqual(
            chooseLineup(isCurrentSeason=True, banked=True,
                         persistedWeek=BANKED, liveEquipped=LIVE),
            BANKED)

    def testALiveWeekStillFollowsWhatIsEquippedNow(self):
        # Mid-week the reader is watching their current lineup score.
        self.assertEqual(
            chooseLineup(isCurrentSeason=True, banked=False,
                         persistedWeek=BANKED, liveEquipped=LIVE),
            LIVE)

    def testAPastSeasonAlwaysUsesThePersistedLineup(self):
        self.assertEqual(
            chooseLineup(isCurrentSeason=False, banked=True,
                         persistedWeek=BANKED, liveEquipped=LIVE),
            BANKED)
        self.assertEqual(
            chooseLineup(isCurrentSeason=False, banked=False,
                         persistedWeek=BANKED, liveEquipped=LIVE),
            BANKED)

    def testABankedWeekWithNoPersistedLineupFallsBackToLive(self):
        """Older rows have a banked bonus but no per-week lineup saved.

        Showing the live lineup there is imperfect, but it beats an empty expansion.
        """
        self.assertEqual(
            chooseLineup(isCurrentSeason=True, banked=True,
                         persistedWeek=[], liveEquipped=LIVE),
            LIVE)

    def testChangingCardsAfterABankedWeekDoesNotMoveTheRow(self):
        """The specific behaviour from the screenshots."""
        beforeSwap = chooseLineup(True, True, BANKED, BANKED)
        afterSwap = chooseLineup(True, True, BANKED, LIVE)
        self.assertEqual(beforeSwap, afterSwap,
                         'the banked row moved when the user changed a card')


if __name__ == '__main__':
    unittest.main(verbosity=2)
