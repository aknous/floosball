"""Frames: every frame ending is managed like the end of a game (owner, 2026-10-09).

The end-of-period clock decisions (timeouts on both sides, spikes, sideline throws, the
field-goal and touchdown drains, the last-play kick and Hail Mary, the late fourth-down
branches) were gated on `currentQuarter in (2, 4)`, so in Frames they only fired at the
end of frames 3 and 6, the two frames that end with a quarter. Measured over 60 games,
offensive timeouts in the last 2:00 of a frame ran 0.00 / 0.32 / 3.45 / 0.00 / 0.02 /
0.30 a game across frames 1-6; defensive timeouts were zero outside frames 3 and 6.

Now each decision asks `Game._periodEnd()` (the format decides: the frame buzzer in
Frames) and reasons from `Game._clockMargin()` (what it takes to win the frame; the
total score in the final frame with the frames level). Rules decided by the owner:
2 timeouts per team every frame, and no two-minute warning in Frames.

Every other format plays byte-identical games before and after (checked by replaying
seeded games and hashing every play).

Run: .venv/bin/python test_frames_clock_management.py
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
from constants import FRAMES_TIMEOUTS_PER_FRAME

HERE = os.path.dirname(os.path.abspath(__file__))
FRAME_LEN = 600   # 3600s / 6 frames
TRIALS = 60


def framesGame(*, frame, secsLeft, frameMargin=0, totalMargin=None, framesOff=0.0,
               framesDef=0.0, ballOn=50, down=1, offTimeouts=2, defTimeouts=2):
    """A Frames game in frame `frame` (1-6) with `secsLeft` on the frame clock, the
    offense (home) ahead by `frameMargin` inside the frame and by `totalMargin` overall
    (defaults to the frame margin), the clock running."""
    gr = GameRules()
    gr.gameFormat = 'frames'
    gr.framesPerGame = 6
    elapsed = FRAME_LEN * (frame - 1) + (FRAME_LEN - secsLeft)
    quarter = elapsed // gr.quarterLengthSeconds + 1
    clock = gr.quarterLengthSeconds - elapsed % gr.quarterLengthSeconds
    s = Scenario(gameRules=gr)
    s.situation(quarter=int(quarter), clock=int(clock), offense='home',
                offScore=0, defScore=0, down=down, distance=10, ballOn=ballOn)
    g = s.g
    totalMargin = frameMargin if totalMargin is None else totalMargin
    # Entering the frame the offense was ahead by (total - frame); it then went
    # ahead by `frameMargin` inside it.
    entry = totalMargin - frameMargin
    g._frameStartHome, g._frameStartAway = 30 + max(0, entry), 30 + max(0, -entry)
    g.homeScore = g._frameStartHome + max(0, frameMargin)
    g.awayScore = g._frameStartAway + max(0, -frameMargin)
    g._frameIndex = frame - 1
    g._framesWonHome, g._framesWonAway = framesOff, framesDef
    g.homeTimeoutsRemaining, g.awayTimeoutsRemaining = offTimeouts, defTimeouts
    g.clockRunning = True
    g._clockStoppedByWarning = False
    return s, g


def offenseTimeoutRate(**kw):
    random.seed(7)
    hits = 0
    for _ in range(TRIALS):
        s, _g = framesGame(**kw)
        if s.clockDecision() == 'timeout':
            hits += 1
    return hits / TRIALS


def defenseTimeoutRate(**kw):
    random.seed(7)
    hits = 0
    for _ in range(TRIALS):
        _s, g = framesGame(**kw)
        before = g.awayTimeoutsRemaining
        g._checkDefensiveTimeout()
        hits += g.awayTimeoutsRemaining < before
    return hits / TRIALS


class FramesClockManagementTests(unittest.TestCase):

    def testEveryFrameEndingIsAPeriodEnding(self):
        for frame in range(1, 7):
            _s, g = framesGame(frame=frame, secsLeft=90)
            self.assertEqual(g._periodEnd(), ('game', 90), f'frame {frame}')
            _s, g = framesGame(frame=frame, secsLeft=400)
            self.assertIsNone(g._periodEnd()[0], f'frame {frame} with 6:40 left')

    def testAnOffenseBehindInAnyFrameStopsTheClock(self):
        for frame in (1, 2, 4, 5):
            rate = offenseTimeoutRate(frame=frame, secsLeft=80, frameMargin=-3)
            self.assertGreater(rate, 0.5, f'frame {frame}: {rate:.2f}')

    def testAnOffenseAheadInTheFrameDoesNotStopTheClock(self):
        self.assertEqual(offenseTimeoutRate(frame=2, secsLeft=80, frameMargin=3), 0.0)

    def testADefenseBehindInAnyFrameStopsTheClock(self):
        for frame in (1, 2, 4, 5):
            rate = defenseTimeoutRate(frame=frame, secsLeft=50, frameMargin=3)
            self.assertGreater(rate, 0.4, f'frame {frame}: {rate:.2f}')

    def testTheDefenseReadsTheFrameNotTheTotal(self):
        # Ahead by 20 overall, behind by 3 in the frame: losing the frame, so stop it.
        self.assertGreater(defenseTimeoutRate(frame=2, secsLeft=50, frameMargin=3,
                                              totalMargin=-20), 0.4)
        # Behind by 20 overall, ahead by 10 in the frame with the offense far away: the
        # clock is its friend.
        self.assertEqual(defenseTimeoutRate(frame=2, secsLeft=50, frameMargin=-10,
                                            totalMargin=20, ballOn=25), 0.0)

    def testASettledFrameEndsLikeAHalfForTheSideBehindOnly(self):
        _s, g = framesGame(frame=2, secsLeft=60, frameMargin=-30)
        self.assertEqual(g._periodEnd()[0], 'half')                   # offense, behind
        self.assertEqual(g._periodEnd(forDefense=True)[0], 'game')    # defense, ahead
        self.assertFalse(g._isGarbageTime(g._clockMargin()))
        # The trailing side still plays for the total score: it stops the clock.
        self.assertGreater(offenseTimeoutRate(frame=2, secsLeft=60, frameMargin=-30), 0.5)
        # The side ahead does not (the owner's frame-leader rule).
        self.assertEqual(offenseTimeoutRate(frame=2, secsLeft=60, frameMargin=30), 0.0)
        # In the final frame a decided frame decides the match: no 'half' ending.
        _s, g = framesGame(frame=6, secsLeft=60, frameMargin=-30)
        self.assertEqual(g._periodEnd()[0], 'game')

    def testTwoTimeoutsEveryFrameAndNoHalftimeReset(self):
        _s, g = framesGame(frame=1, secsLeft=300, offTimeouts=0, defTimeouts=0)
        g.format.onPeriodStart(g) if g.currentQuarter == 1 else None
        self.assertEqual((g.homeTimeoutsRemaining, g.awayTimeoutsRemaining),
                         (FRAMES_TIMEOUTS_PER_FRAME,) * 2)
        # Spend them, then cross into frame 2: a fresh allotment.
        g.homeTimeoutsRemaining = g.awayTimeoutsRemaining = 0
        g.gameClockSeconds = 900 - FRAME_LEN - 1    # just past the frame 1 buzzer
        g.format.awardFrames(g)
        self.assertEqual(g._frameIndex, 1)
        self.assertEqual((g.homeTimeoutsRemaining, g.awayTimeoutsRemaining),
                         (FRAMES_TIMEOUTS_PER_FRAME,) * 2)
        # Halftime does not top Frames up to 3.
        self.assertIsNone(g.format.halftimeTimeouts())
        _s, g = framesGame(frame=3, secsLeft=1, offTimeouts=1, defTimeouts=0)
        g.gameClockSeconds = 0
        g.advanceQuarter()
        self.assertEqual((g.homeTimeoutsRemaining, g.awayTimeoutsRemaining), (1, 0))

    def testNoPhantomTwoMinuteWarningInFrames(self):
        # Just above 2:00 of a frame that ends with Q4: nothing is coming to stop the
        # clock for free, so a timeout there is not wasted.
        _s, g = framesGame(frame=6, secsLeft=125)
        self.assertFalse(g._twoMinuteWarningPending(125))

    def testStandardPeriodEndsAreTheQuarters(self):
        s = Scenario(gameRules=GameRules())
        for quarter, kind in ((1, None), (2, 'half'), (3, None), (4, 'game'), (5, 'overtime')):
            s.situation(quarter=quarter, clock=100, offense='home', offScore=0, defScore=0,
                        down=1, distance=10, ballOn=50)
            self.assertEqual(s.g._periodEnd(), (kind, 100), f'Q{quarter}')

    def testTheTimeoutDecisionsDoNotTestTheQuarter(self):
        """They ask `_periodEnd()`. A quarter test creeping back in is how Frames lost
        every frame ending but two."""
        with open(os.path.join(HERE, 'floosball_game.py')) as f:
            src = f.read()
        for fn in ('_checkDefensiveTimeout', '_maybeCallTimeoutToSaveSnap'):
            body = src.split(f'    def {fn}(self')[1].split('\n    def ')[0]
            code = '\n'.join(line.split('#')[0] for line in body.splitlines())
            self.assertNotIn('currentQuarter in', code, fn)
            self.assertNotIn('currentQuarter ==', code, fn)


if __name__ == '__main__':
    unittest.main(verbosity=2)
