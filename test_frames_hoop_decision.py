"""Sideline goals in Frames: the hoop decision reads the FRAME (fixed 2026-10-20).

`_shouldAttemptHoopShot` decided its late need from the TOTAL score and the Q4 game
clock while `_isHurryUp` reads the frame. At every frame ending but the last, a team
tied in the frame hit the hurry-up guard with no late need to lift it, and a frame
leader got the base roll. Prod season 11 (16 Frames games), last 2:00 of a frame with a
hoop in range: tied or down 1 shot 5% of snaps, leaders 45%. Every hoop shot stops the
clock, so the leader was also handing time back.

Run: .venv/bin/python -m pytest test_frames_hoop_decision.py
"""
import random
import unittest

import numpy as np

from random_batch import clear_all_batch_caches
from scenario import Scenario
from game_rules import GameRules
from test_frames_buzzer import framesGame

TRIALS = 300


def reseed(s=0):
    random.seed(s); np.random.seed(s); clear_all_batch_caches()


def framesRate(**kw):
    """Attempt rate with the midfield pair two yards out (a near tap, no quality hold)."""
    reseed()
    hits = 0
    for _ in range(TRIALS):
        _s, g = framesGame(ballOn=52, **kw)
        g.gameRules.sidelineGoalsEnabled = True
        g.gameRules.sidelineGoalPoints = 1
        g._hoopPairResult = None
        g.isOvertime = False
        if g._shouldAttemptHoopShot():
            hits += 1
    return hits / TRIALS


def standardRate(**situation):
    reseed()
    gr = GameRules()
    gr.sidelineGoalsEnabled = True
    gr.sidelineGoalPoints = 1
    s = Scenario(gameRules=gr)
    hits = 0
    for _ in range(TRIALS):
        s.situation(ballOn=52, **situation)
        s.g._hoopPairResult = None
        s.g.isOvertime = False
        if s.g._shouldAttemptHoopShot():
            hits += 1
    return hits / TRIALS


class FrameEndingTests(unittest.TestCase):

    def testATiedFrameShootsForTheLead(self):
        # Frame 2, 1:00 left, tied in the frame, though well ahead on the total.
        rate = framesRate(frame=2, secsLeft=60, frameMargin=0, totalMargin=14)
        self.assertGreater(rate, 0.8)

    def testAFrameLeaderDoesNotStopTheClock(self):
        # Up 3 in the frame with 1:00 left, though behind on the total.
        rate = framesRate(frame=2, secsLeft=60, frameMargin=3, totalMargin=-10)
        self.assertEqual(rate, 0.0)

    def testEarlyInAFrameTheBaseRollStillApplies(self):
        # 7:00 left: no frame ending in play, so leaders and tied teams both roll.
        for margin in (0, 3):
            rate = framesRate(frame=2, secsLeft=420, frameMargin=margin)
            self.assertGreater(rate, 0.3, f'frame margin {margin}')

    def testTheFinalFrameReadsTheMatch(self):
        # Last frame, frames level, tied in the frame and on the total: a point wins it.
        rate = framesRate(frame=6, secsLeft=60, frameMargin=0, totalMargin=0,
                          framesOff=2.5, framesDef=2.5)
        self.assertGreater(rate, 0.8)

    def testJustShortOfWinningReadsAsTied(self):
        # The final frame's margin sits an epsilon below 0 when any score wins.
        _s, g = framesGame(frame=6, secsLeft=60)
        g.gameRules.sidelineGoalsEnabled = True
        g._hoopPairResult = None
        self.assertEqual(g._hoopPointsNeeded(-0.001), 'helpful')
        self.assertIsNone(g._hoopPointsNeeded(0.001))


class StandardTests(unittest.TestCase):

    def testATiedTeamLateStillShoots(self):
        self.assertGreater(standardRate(quarter=4, clock=60, offScore=10, defScore=10), 0.8)

    def testALeaderLateDoesNotShoot(self):
        self.assertEqual(standardRate(quarter=4, clock=60, offScore=13, defScore=10), 0.0)

    def testALeaderEarlyStillRolls(self):
        self.assertGreater(standardRate(quarter=2, clock=600, offScore=13, defScore=10), 0.3)


if __name__ == '__main__':
    unittest.main()
