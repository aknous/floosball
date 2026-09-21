"""A team protecting a late lead runs the ball, on every down.

⚠️ THE OLD LAYERS WERE MULTIPLIERS ON THE RUN WEIGHT, AND A MULTIPLIER CAPS OUT. They
topped out near 2.7x: enough to take 1st & 10 to ~73% runs, but 3rd & 8 only to ~32%,
because a pass-heavy row can only be pulled so far that way. Measured against NFL
2021-25 play-by-play, a leading team inside the final two minutes passed 53% of the
time in the sim against the NFL's 13%.

The NFL's pass rate falls by about the same LOG-ODDS amount on every down as the clock
runs down (~0.5 with 10-15 minutes left, 3.5-4.4 inside two minutes), so the layer now
scales every pass option by exp(-shift) — the play-call tiers and the RPO alike.

Run: .venv/bin/python test_lead_protection.py
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import logging
logging.disable(logging.CRITICAL)

from scenario import Scenario  # noqa: E402

PASS = ('short', 'medium', 'long', 'deep')


def passShare(s):
    g = s.game
    w = g._getBasePlayWeights()
    w = g._applySituationalMods(dict(w), s._scoreDiff(), g.offensiveTeam.coach)
    tot = sum(max(0.0, w[k]) for k in ('run',) + PASS)
    return sum(max(0.0, w[k]) for k in PASS) / tot


class LeadProtection(unittest.TestCase):

    def _share(self, clock, down, distance, offScore=24, defScore=17, quarter=4):
        s = Scenario()
        s.situation(quarter=quarter, clock=clock, down=down, distance=distance, ballOn=65,
                    offScore=offScore, defScore=defScore, defTimeouts=2)
        return passShare(s)

    def testInsideTwoMinutesEveryDownLeansRun(self):
        self.assertLess(self._share(90, 1, 10), 0.08, '1st & 10 up 7 at 1:30 still throws')
        self.assertLess(self._share(90, 3, 8), 0.60,
                        '3rd & 8 up 7 at 1:30 throws as if the lead did not exist')

    def testThirdAndLongStillThrowsSometimes(self):
        """A first down ends the game, so 3rd & long is not an automatic run."""
        self.assertGreater(self._share(90, 3, 8), 0.15)

    def testTheShiftGrowsAsTheClockRunsDown(self):
        shares = [self._share(c, 1, 10) for c in (840, 450, 200, 60)]
        self.assertEqual(shares, sorted(shares, reverse=True), shares)

    def testTrailingAndTiedTeamsAreUntouched(self):
        s = Scenario()
        s.situation(quarter=4, clock=90, down=1, distance=10, ballOn=65, offScore=17, defScore=17)
        self.assertEqual(s.game._leadProtectKeep(0), 1.0)
        self.assertEqual(s.game._leadProtectKeep(-3), 1.0)

    def testTheRpoIsAPassOptionToo(self):
        """RPOs chose give-or-throw after the weights and leaked ~30% of late-lead passes."""
        s = Scenario()
        s.situation(quarter=4, clock=60, down=1, distance=10, ballOn=65, offScore=24, defScore=17)
        self.assertLess(s.game._leadProtectKeep(), 0.1)
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               'floosball_game.py')) as fh:
            src = fh.read()
        start = src.index('def _selectRpo')
        body = src[start:src.index('\n    def ', start + 10)]
        self.assertIn('self._leadProtectKeep()', body)


class ChasingTwoScores(unittest.TestCase):
    """The mirror: down two scores in Q4 the sim passed 63-67% of the time vs the NFL's
    80%, because the trailing branches were run-weight multipliers that capped out."""

    def _share(self, offScore, defScore, clock=480):
        s = Scenario()
        s.situation(quarter=4, clock=clock, down=1, distance=10, ballOn=65,
                    offScore=offScore, defScore=defScore)
        return passShare(s)

    def testTwoScoresDownThrowsMoreThanOneScoreDown(self):
        self.assertGreater(self._share(7, 21), self._share(14, 21) + 0.15)

    def testOneScoreDownIsNotShifted(self):
        """One possession still ties it, so the clock is not yet the enemy."""
        self.assertAlmostEqual(self._share(17, 21), self._share(21, 21), delta=0.08)


if __name__ == '__main__':
    unittest.main()
