"""Frames: a frame's buzzer, end-of-frame play calling, and the tied frame's last snap.

Audited on prod season 11 week 1 (16 Frames games, 2026-10-19):

1. The clock ran through the buzzers of frames 1, 2, 4 and 5 (they end in the middle of
   a quarter, so the quarter clock never stops anything there). The pre-snap huddle ran
   past 0:00, the snap still counted in the old frame, and the overrun came out of the
   next frame: 50 of 73 frame endings overran, 39s a game, up to 46s, and 18 snaps came
   after the buzzer (three field goals among them). `FramesFormat.clampConsumption` now
   stops the huddle one second short of the buzzer and a play in progress at it.
2. The play-calling shifts read the quarter and the total score, so "trailing late →
   stop running" only fired at the end of frame 6: teams behind in a frame inside its
   last minute ran 24% of the time (NFL, trailing by 1-8 in the last minute: 11%).
   `Game._situationalClock` hands those shifts the frame clock and the frame margin.
3. A tied team punted on a frame's last snap (0:02, 0:07, 0:14 left) though the next
   frame restarts at the 20 and a tie is worth half a win. `_frameTieIsShort` sends it
   to the end-of-half shot / last-snap heave instead.

Every other format plays byte-identical games before and after (seeded replay, hashed).

Run: .venv/bin/python test_frames_buzzer.py
"""
import asyncio
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

import numpy as np
import floosball_game as FG
import floosball_team as FT
import game_formats as GF
from managers.timingManager import TimingManager, TimingMode
from scenario import Scenario, _makeTeam
from game_rules import GameRules

FT.Team.getAverages = lambda self, season=None: None
FRAME_LEN = 600   # 3600s / 6 frames
TRIALS = 200


def framesGame(*, frame, secsLeft, frameMargin=0, totalMargin=None, framesOff=0.0,
               framesDef=0.0, ballOn=50, down=1, distance=10):
    """A Frames game in frame `frame` with `secsLeft` on the frame clock, the offense
    (home) ahead by `frameMargin` in the frame and `totalMargin` overall."""
    gr = GameRules()
    gr.gameFormat = 'frames'
    gr.framesPerGame = 6
    elapsed = FRAME_LEN * (frame - 1) + (FRAME_LEN - secsLeft)
    quarter = elapsed // gr.quarterLengthSeconds + 1
    clock = gr.quarterLengthSeconds - elapsed % gr.quarterLengthSeconds
    s = Scenario(gameRules=gr)
    s.situation(quarter=int(quarter), clock=int(clock), offense='home', offScore=0,
                defScore=0, down=down, distance=distance, ballOn=ballOn,
                offTimeouts=0, defTimeouts=0)
    g = s.g
    totalMargin = frameMargin if totalMargin is None else totalMargin
    entry = totalMargin - frameMargin
    g._frameStartHome, g._frameStartAway = 30 + max(0, entry), 30 + max(0, -entry)
    g.homeScore = g._frameStartHome + max(0, frameMargin)
    g.awayScore = g._frameStartAway + max(0, -frameMargin)
    g._frameIndex = frame - 1
    g._framesWonHome, g._framesWonAway = framesOff, framesDef
    g.clockRunning = True
    g._clockStoppedByWarning = False
    return s, g


def runShare(**kw):
    """Run weight as a share of the play-call weights, deterministic."""
    _s, g = framesGame(**kw)
    w = g._applySituationalMods(dict(g._getBasePlayWeights()), 0, g.offensiveTeam.coach)
    return w['run'] / sum(w.values())


class TheBuzzerTests(unittest.TestCase):

    def testAHuddleStopsOneSecondShortOfTheBuzzer(self):
        # A leader killing the clock with 6s left in frame 1 (5:06 left in Q1).
        _s, g = framesGame(frame=1, secsLeft=6, frameMargin=3)
        g.play.playType = FG.PlayType.Run
        g._inPreSnap = True
        g.consumeGameTime(g.calculatePreSnapTime())
        g._inPreSnap = False
        self.assertEqual(g._frameSecsRemaining(), 1)
        self.assertEqual(g.gameClockSeconds, 301)

    def testAPlayInProgressStopsAtTheBuzzer(self):
        _s, g = framesGame(frame=2, secsLeft=3)
        g.consumeGameTime(12)                       # a 12-second Hail Mary from 0:03
        self.assertEqual(g._frameSecsRemaining(), 0)
        self.assertEqual(g.gameClockSeconds, 600)   # 20:00 elapsed = 10:00 left in Q2
        g.consumeGameTime(5)                        # nothing more until the frame commits
        self.assertEqual(g.gameClockSeconds, 600)
        g.format.awardFrames(g)
        self.assertEqual(g._frameIndex, 2)
        self.assertEqual(g._frameSecsRemaining(), 600)   # the next frame is whole

    def testAConversionOnTheBuzzerIsStampedInItsOwnFrame(self):
        _s, g = framesGame(frame=1, secsLeft=2)
        g.consumeGameTime(10)
        play = FG.Play(g)
        self.assertEqual((play.frame, play.frameClock), (1, '0:00'))

    def testNoFrameEverRunsLongInAWholeGame(self):
        rng = random.Random(5)
        random.seed(11); np.random.seed(11)
        teams = []
        for t in range(6):
            team = _makeTeam(f'T{t}', f'T{t:02d}', 10000 + t * 100, phys=rng.randint(74, 92),
                             ment=rng.randint(74, 92), defRun=rng.randint(70, 88),
                             defPass=rng.randint(70, 88))
            team.id = t
            np.random.seed(900 + t)
            team.coach.generateAttributes()
            teams.append(team)
        overruns = []
        orig = GF.FramesFormat.awardFrames

        def award(fmt, game):
            before = getattr(game, '_frameIndex', 0)
            orig(fmt, game)
            if getattr(game, '_frameIndex', 0) > before:
                overruns.append(fmt._elapsed(game) - game._frameIndex * FRAME_LEN)
        GF.FramesFormat.awardFrames = award
        try:
            for i in range(6):
                home, away = rng.sample(teams, 2)
                gr = GameRules(); gr.gameFormat = 'frames'
                game = FG.Game(home, away, gameRules=gr,
                               timingManager=TimingManager(TimingMode.FAST))
                game.id = i
                asyncio.run(asyncio.wait_for(game.playGame(), timeout=180))
        finally:
            GF.FramesFormat.awardFrames = orig
        self.assertGreater(len(overruns), 20)
        self.assertEqual(max(overruns), 0, overruns)

    def testOffFramesNothingIsClamped(self):
        s = Scenario()
        s.situation(quarter=1, clock=306)
        self.assertEqual(s.g.format.clampConsumption(s.g, 40), 40)
        self.assertIsNone(s.g._frameSecsRemaining())


class FramePlayCallingTests(unittest.TestCase):

    def testAFrameEndingReadsAsTheEndOfTheFourth(self):
        _s, g = framesGame(frame=1, secsLeft=90, frameMargin=-7, totalMargin=10)
        self.assertEqual(g._situationalClock(), (4, 90, -7))
        _s, g = framesGame(frame=4, secsLeft=420, frameMargin=-7)
        self.assertEqual(g._situationalClock()[0], 1)   # mid-frame: no late-game shift

    def testBehindLateInAnEarlyFrameStopsRunning(self):
        late = runShare(frame=1, secsLeft=40, frameMargin=-7)
        mid = runShare(frame=1, secsLeft=420, frameMargin=-7)
        self.assertLess(late, 0.6 * mid, f'late {late:.2f} vs mid-frame {mid:.2f}')

    def testATotalLeadIsNotProtectedWhileLosingTheFrame(self):
        # Frame 5, Q4 (47:00 elapsed), behind by 3 in the frame, ahead by 14 overall.
        _s, g = framesGame(frame=5, secsLeft=60, frameMargin=-3, totalMargin=14)
        self.assertEqual(g._leadProtectKeep(), 1.0)
        # Ahead in the frame, it does protect.
        _s, g = framesGame(frame=5, secsLeft=60, frameMargin=3, totalMargin=-14)
        self.assertLess(g._leadProtectKeep(), 1.0)

    def testStandardIsUntouched(self):
        s = Scenario()
        s.situation(quarter=4, clock=90, offScore=10, defScore=17)
        self.assertEqual(s.g._situationalClock(), (4, 90, None))
        self.assertFalse(s.g._frameTieIsShort())


class TiedFrameLastSnapTests(unittest.TestCase):

    def _fourthDown(self, **kw):
        random.seed(3)
        kinds = {}
        for _ in range(TRIALS):
            s, _g = framesGame(down=4, distance=8, **kw)
            pt = s.callPlay()
            kinds[pt] = kinds.get(pt, 0) + 1
        return kinds

    def testATiedTeamDoesNotPuntTheFrameAway(self):
        # 4th and 8 on its own 43 with 0:02 left in frame 2 (prod game 4637).
        kinds = self._fourthDown(frame=2, secsLeft=2, ballOn=57)
        self.assertNotIn(FG.PlayType.Punt, kinds, kinds)
        # And with 0:14 left on the opponent's 44 (prod game 4645).
        kinds = self._fourthDown(frame=4, secsLeft=14, ballOn=44)
        self.assertNotIn(FG.PlayType.Punt, kinds, kinds)

    def testInTheFinalFrameATieThatWinsTheMatchIsKept(self):
        _s, g = framesGame(frame=6, secsLeft=2, framesOff=3.0, framesDef=2.0)
        self.assertFalse(g._frameTieIsShort())
        _s, g = framesGame(frame=6, secsLeft=2, framesOff=2.0, framesDef=3.0)
        self.assertTrue(g._frameTieIsShort())
        _s, g = framesGame(frame=2, secsLeft=2)
        self.assertTrue(g._frameTieIsShort())


if __name__ == '__main__':
    unittest.main(verbosity=1)
