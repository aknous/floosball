"""A defense that has stopped the clock on a drive keeps stopping it (fixed 2026-10-20).

`_checkDefensiveTimeout` rolls once per snap on the coach's clock IQ and nothing asks
again during the huddle. Prod game 4759, final frame: the Beans, a point behind in the
match with the Strangers draining on the Beans' 14, called a timeout at 1:26 and then
sat on their last one at 1:20 while 48 seconds ran off. Once a defense has called a
timeout on a drive, the read holds for that drive; every situational gate still applies.

Run: .venv/bin/python -m pytest test_defensive_timeout_commit.py
"""
import random
import unittest

import numpy as np

from random_batch import clear_all_batch_caches
from test_frames_buzzer import framesGame

TRIALS = 300


def reportedSpot():
    # Final frame, 1:20 left. The Strangers (offense, home) trail the frame 2-10 but
    # lead the match: frames 3-2, so a lost frame levels them and they are up 1 on total.
    _s, g = framesGame(frame=6, secsLeft=80, frameMargin=-8, totalMargin=1,
                       framesOff=3.0, framesDef=2.0, ballOn=14, down=2, distance=10)
    g.awayTimeoutsRemaining = 1
    g.defensiveTeam.coach.clockManagement = 60     # the poorest clock manager: 50% a snap
    g._drivesBy = {id(g.offensiveTeam): 5}
    return g


def timeoutRate(committed):
    random.seed(0); np.random.seed(0); clear_all_batch_caches()
    calls = 0
    for _ in range(TRIALS):
        g = reportedSpot()
        if committed:
            g._defTimeoutDrive = (id(g.offensiveTeam), 5, g.currentQuarter, g._frameIndex)
        g._checkDefensiveTimeout()
        calls += g.awayTimeoutsRemaining == 0
    return calls / TRIALS


class DefensiveTimeoutCommitTests(unittest.TestCase):

    def testTheSpotIsATrailingDefense(self):
        g = reportedSpot()
        self.assertLess(g._clockMargin(forDefense=True), 0)

    def testACoachWhoAlreadyStoppedTheClockDoesItAgain(self):
        self.assertEqual(timeoutRate(committed=True), 1.0)

    def testAFreshDriveIsStillTheCoachsRead(self):
        rate = timeoutRate(committed=False)
        self.assertGreater(rate, 0.35)
        self.assertLess(rate, 0.65)

    def testTheCommitmentEndsWithTheDrive(self):
        random.seed(0); np.random.seed(0); clear_all_batch_caches()
        calls = 0
        for _ in range(TRIALS):
            g = reportedSpot()
            g._defTimeoutDrive = (id(g.offensiveTeam), 4, g.currentQuarter, g._frameIndex)
            g._checkDefensiveTimeout()
            calls += g.awayTimeoutsRemaining == 0
        self.assertLess(calls / TRIALS, 0.65)

    def testTheGatesStillApply(self):
        # Committed, but out of timeouts: nothing to call.
        g = reportedSpot()
        g.awayTimeoutsRemaining = 0
        g._defTimeoutDrive = (id(g.offensiveTeam), 5, g.currentQuarter, g._frameIndex)
        g._checkDefensiveTimeout()
        self.assertTrue(g.clockRunning)


if __name__ == '__main__':
    unittest.main()
