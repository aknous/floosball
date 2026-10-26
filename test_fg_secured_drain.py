"""A team already in field-goal range, tied or within a kick, runs the clock (2026-10-19).

Reported from prod game 4688 (Extras 19, Pinecones 16, OT): last frame, tied 13-13 on
1st and 10 at the 12 with 1:39 left, the Extras used both timeouts, kicked with 1:22 left
and the Pinecones drove for the tying field goal at 0:00. The rule that keeps the clock
running for a last-second kick (`_isFgDrainMode`) only switches on inside 1:00; above it
the offensive timeout window treated "in range, tied or trailing by <= 3" as a reason to
STOP the clock. A standard Q4 in the same spot called a timeout 87% of the time.

`Game._isFgSecuredDrain` covers 1:00 to `FG_SECURE_DRAIN_SECS`: no hurry-up, no
clock-stopping timeout, spike or sideline throw. Recognising the spot is a coach call
(owner: "tied to coach clock management"), read once per drive.

Run: .venv/bin/python test_fg_secured_drain.py
"""
import os
import random
import sys
import types
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import logging
logging.disable(logging.CRITICAL)
_stub = types.ModuleType('floosball_game'); _stub.Game = type('G', (), {})
sys.modules.setdefault('floosball_game', _stub)
import managers.timingManager  # noqa: F401
if sys.modules.get('floosball_game') is _stub:
    del sys.modules['floosball_game']

from scenario import Scenario
from game_rules import GameRules

TRIALS = 200


def spot(*, clock=99, offScore=13, defScore=13, ballOn=12, clockMgmt=None, quarter=4,
         gameRules=None):
    s = Scenario(gameRules=gameRules)
    s.situation(quarter=quarter, clock=clock, offScore=offScore, defScore=defScore, down=1,
                distance=10, ballOn=ballOn, offTimeouts=3, defTimeouts=3)
    if clockMgmt is not None:
        s.g.offensiveTeam.coach.clockManagement = clockMgmt
    return s


def timeoutRate(**kw):
    random.seed(4)
    hits = 0
    for _ in range(TRIALS):
        s = spot(**kw)
        hits += s.clockDecision() == 'timeout'
    return hits / TRIALS


class InRangeRunsTheClock(unittest.TestCase):

    def testASharpClockManagerNeverStopsTheClockInRange(self):
        self.assertEqual(timeoutRate(clockMgmt=100), 0.0)
        self.assertEqual(timeoutRate(clockMgmt=100, offScore=10), 0.0)   # down 3

    def testAPoorClockManagerStillSometimesDoes(self):
        # The read is the coach's: a poor clock manager often misses the drain. With 1:39
        # left he still does not stop the clock, because the drive does not need the time
        # (`_offensiveTimeoutNeeded`, 2026-10-26); he just does not slow it down either.
        def drainRead(clockMgmt):
            random.seed(4)
            return sum(spot(clockMgmt=clockMgmt).g._isFgSecuredDrain() for _ in range(TRIALS)) / TRIALS
        self.assertLess(drainRead(60), 0.7)
        self.assertGreater(drainRead(80), drainRead(60))   # better coach, reads it more
        self.assertLess(timeoutRate(clockMgmt=60), 0.10)

    def testOutOfRangeStillStopsTheClock(self):
        # Out of comfortable range the drain does not apply, and the timeout comes once
        # the clock binds: held at 1:39 with three in hand, spent at 0:30.
        self.assertLess(timeoutRate(clockMgmt=100, ballOn=40), 0.10)
        self.assertGreater(timeoutRate(clockMgmt=100, ballOn=40, clock=30), 0.6)

    def testAheadOrInTheLastMinuteIsLeftAlone(self):
        s = spot(clockMgmt=100, offScore=20)
        self.assertFalse(s.g._isFgSecuredDrain())                         # up 7
        s = spot(clockMgmt=100, clock=45)
        self.assertFalse(s.g._isFgSecuredDrain())                         # FG drain owns it
        s = spot(clockMgmt=100, quarter=2)
        self.assertFalse(s.g._isFgSecuredDrain())                         # end of a half

    def testTempoBleedsWhenTiedAndStopsHurryingWhenBehind(self):
        s = spot(clockMgmt=100)
        self.assertEqual(s.g._classifyTempoIntent()[0], 'burnClock')
        s = spot(clockMgmt=100, offScore=10)
        self.assertEqual(s.g._classifyTempoIntent()[0], 'neutral')

    def testNoSidelineThrowsWhileDraining(self):
        s = spot(clockMgmt=100)
        self.assertFalse(s.g._shouldTargetSideline(0, s.g.offensiveTeam.coach))

    def testTheReadIsHeldForTheDrive(self):
        random.seed(2)
        for _ in range(40):
            s = spot(clockMgmt=70)
            first = s.g._isFgSecuredDrain()
            self.assertTrue(all(s.g._isFgSecuredDrain() == first for _ in range(5)))

    def testFramesReadsTheFrame(self):
        gr = GameRules(); gr.gameFormat = 'frames'; gr.framesPerGame = 6
        # Frame 2 with 1:39 left = 18:21 elapsed = 11:39 left in Q2; tied in the frame,
        # behind by 10 overall (the total does not decide frame 2).
        s = Scenario(gameRules=gr)
        s.situation(quarter=2, clock=699, offScore=20, defScore=30, down=1, distance=10,
                    ballOn=12, offTimeouts=2, defTimeouts=2)
        g = s.g
        g._frameIndex = 1
        g._frameStartHome, g._frameStartAway = 20, 30
        g.offensiveTeam.coach.clockManagement = 100
        self.assertTrue(g._isFgSecuredDrain())


class FramesTrailingHurry(unittest.TestCase):

    def _tempo(self, *, frameMargin, secsLeft=200, frame=6, framesOff=2.5, framesDef=2.5):
        gr = GameRules(); gr.gameFormat = 'frames'; gr.framesPerGame = 6
        elapsed = 600 * (frame - 1) + (600 - secsLeft)
        s = Scenario(gameRules=gr)
        s.situation(quarter=elapsed // 900 + 1, clock=900 - elapsed % 900, down=1,
                    distance=10, ballOn=62, offTimeouts=2, defTimeouts=2)
        g = s.g
        g._frameIndex = frame - 1
        g._framesWonHome, g._framesWonAway = framesOff, framesDef
        g._frameStartHome, g._frameStartAway = 14, 14
        g.homeScore = 14 + max(0, frameMargin)
        g.awayScore = 14 + max(0, -frameMargin)
        return g._classifyTempoIntent()

    def testBehindWithThreeMinutesLeftPicksUpThePace(self):
        # Prod game 4691: last frame, frames level, down 3 with 3:14 left.
        self.assertEqual(self._tempo(frameMargin=-3), ('hurryUp', 25))
        self.assertEqual(self._tempo(frameMargin=-10)[0], 'hurryUp')
        self.assertEqual(self._tempo(frameMargin=-3, frame=2)[0], 'hurryUp')

    def testAheadOrEarlyIsUnchanged(self):
        self.assertEqual(self._tempo(frameMargin=3)[0], 'neutral')
        self.assertEqual(self._tempo(frameMargin=-3, secsLeft=420)[0], 'neutral')


if __name__ == '__main__':
    unittest.main(verbosity=1)
