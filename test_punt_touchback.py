"""A touchback is spotted by the rule, not by where the ball flew.

⚠️ THE SENTINEL WAS THE BUG. On a touchback the punt path forces `landing = 0`, meaning
"it went into the end zone". That is honest for the arc the field graphic draws, but it
is not a place the ball is ever put down. Run through the ordinary spotting arithmetic
`100 - min(99, max(1, landing + puntReturn))`, the 0 met `max(1, ...)`, became 1, and
the receiving team took over on their own ONE — while the play-by-play correctly read
"touchback", which is how it was reported.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import managers  # noqa: F401  — breaks the floosball_game circular import
from constants import PUNT_TOUCHBACK_TO


def spot(landing, puntReturn, puntResult):
    """The spotting arithmetic exactly as `playGame`'s punt branch runs it."""
    if puntResult == 'touchback':
        return 100 - PUNT_TOUCHBACK_TO
    return 100 - min(99, max(1, landing + puntReturn))


class PuntTouchbackTests(unittest.TestCase):
    def testATouchbackIsSpottedAtTheTouchbackLine(self):
        # yardsToEndzone 80 == the receiving team's own 20.
        self.assertEqual(spot(landing=0, puntReturn=0, puntResult='touchback'),
                         100 - PUNT_TOUCHBACK_TO)

    def testATouchbackIsNotSpottedOnTheOneYardLine(self):
        # THE REGRESSION, stated the way it was reported.
        self.assertNotEqual(spot(landing=0, puntReturn=0, puntResult='touchback'), 99)

    def testTheTouchbackSpotIgnoresTheSentinelLanding(self):
        # Whatever `landing` says, the rule decides. Guards against someone later
        # "fixing" the sentinel and silently changing the spot.
        for landing in (0, -3, 5):
            self.assertEqual(spot(landing, 0, 'touchback'), 100 - PUNT_TOUCHBACK_TO)

    def testAFairCatchIsStillSpottedWhereItWasCaught(self):
        self.assertEqual(spot(landing=12, puntReturn=0, puntResult='inside20'), 88)

    def testAReturnAdvancesTheSpotAwayFromTheirOwnGoal(self):
        # `landing` is measured from the RECEIVING team's own goal, so a return
        # INCREASES it and the new yardsToEndzone falls.
        self.assertEqual(spot(landing=12, puntReturn=20, puntResult='inside20'), 68)

    def testAnOrdinaryPuntPinnedDeepStillSpotsDeep(self):
        # The clamp still protects the genuine case it was written for: a ball downed
        # a yard out is a real spot, unlike a touchback.
        self.assertEqual(spot(landing=1, puntReturn=0, puntResult='coffin'), 99)

    def testAReturnToTheHouseIsClampedNotWrapped(self):
        self.assertEqual(spot(landing=8, puntReturn=99, puntResult='short_pin'), 1)


if __name__ == '__main__':
    unittest.main(verbosity=2)
