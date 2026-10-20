"""Frames: the pass play reads the FRAME, not the total (fixed 2026-10-20).

Prod game 4759: the Beans, down 4-8 in frame 3 with 0:43 left but up 19-17 overall,
went for it on 4th & 9 from their own 31 and the QB threw it away. The 'must throw'
rule read the total score, so a team behind in the frame but ahead overall was allowed
to throw away the down. The defense's situational scheme and the carrier's late
sideline awareness read the total and the Q4 clock the same way; all three now go
through `_situationalClock`, which is the real quarter, clock and score elsewhere.

Run: .venv/bin/python -m pytest test_frames_must_throw.py
"""
import random
import unittest

import numpy as np

import floosball_game as FG
from random_batch import clear_all_batch_caches
from scenario import Scenario
from test_frames_buzzer import framesGame


def mustThrowOn(g):
    """The mustThrow the pass play hands target selection, on one real pass snap."""
    seen = []
    orig = FG.Play.selectPassTarget

    def spy(self, *a, **kw):
        seen.append(kw.get('mustThrow'))
        return orig(self, *a, **kw)
    FG.Play.selectPassTarget = spy
    try:
        random.seed(0); np.random.seed(0); clear_all_batch_caches()
        g.play.passPlay(g._selectPassPlay('medium'))
    finally:
        FG.Play.selectPassTarget = orig
    return seen[0] if seen else None


class MustThrowTests(unittest.TestCase):

    def testTheReportedSpotForcesTheThrow(self):
        # Frame 3, 0:43 left, down 4 in the frame, up 2 overall, 4th & 9 at the own 31.
        _s, g = framesGame(frame=3, secsLeft=43, frameMargin=-4, totalMargin=2,
                           ballOn=69, down=4, distance=9)
        self.assertIs(mustThrowOn(g), True)

    def testAFrameLeaderMayStillThrowItAway(self):
        # Up 4 in the frame though down 2 overall: no reason to force a throw.
        _s, g = framesGame(frame=3, secsLeft=43, frameMargin=4, totalMargin=-2,
                           ballOn=69, down=4, distance=9)
        self.assertIs(mustThrowOn(g), False)

    def testFrameEndingClockForcesTheThrowOnAnyDown(self):
        # Down 3 in the frame with 0:20 left, 2nd down: time expiring while trailing.
        _s, g = framesGame(frame=2, secsLeft=20, frameMargin=-3, totalMargin=10,
                           ballOn=40, down=2, distance=10)
        self.assertIs(mustThrowOn(g), True)

    def testStandardUnchanged(self):
        s = Scenario()
        s.situation(quarter=2, clock=600, offScore=10, defScore=14, down=4, distance=9, ballOn=69)
        self.assertIs(mustThrowOn(s.g), True)
        s.situation(quarter=2, clock=600, offScore=14, defScore=10, down=4, distance=9, ballOn=69)
        self.assertIs(mustThrowOn(s.g), False)


class SituationalReadTests(unittest.TestCase):

    def testTheDefenseReadsTheFrameEnding(self):
        captured = []
        orig = FG.getDefensiveScheme

        def spy(*a, **kw):
            captured.append(a)
            return orig(*a, **kw)
        FG.getDefensiveScheme = spy
        try:
            _s, g = framesGame(frame=3, secsLeft=43, frameMargin=-4, totalMargin=2,
                               ballOn=69, down=4, distance=9)
            random.seed(0); np.random.seed(0); clear_all_batch_caches()
            g.play.passPlay(g._selectPassPlay('medium'))
        finally:
            FG.getDefensiveScheme = orig
        self.assertTrue(captured)
        _gp, _down, _ytg, _fp, scoreDiff, quarter, clock = captured[0][:7]
        self.assertEqual((scoreDiff, quarter, clock), (-4, 4, 43))


if __name__ == '__main__':
    unittest.main()
