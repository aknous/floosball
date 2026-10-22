"""The last seconds of the first half, and a timeout after the game is over.

Prod season 11, week 21 (games 4967-4982):

  * Game 4967: the Strangers' last snap of the half was on their own 48. The QB
    audibled into a run. In Q2 the sim had no Hail Mary at all; the game-clock heave is
    Q4-only. NFL 2019-23: in the last 7s of Q2 from the opponent's 36-50, a quarter of
    the passes are heaves of 40+ air yards.
  * Late in the half, runs. With the clock stopped and no timeout left, a run restarts
    the clock and the next snap pays a full huddle, so the half ends on the run. NFL,
    last 20s of Q2: runs are 4% of plays from the opponent's 36-50 and 10% inside the
    35; the sim ran 22% and 29%.
  * Game 4976: the Vanguards knelt out the last two seconds and the Sodas called a
    timeout at 0:00.

Run: .venv/bin/python -m pytest -q test_end_of_half_drill.py
"""
import collections
import logging
import unittest

logging.disable(logging.CRITICAL)

from game_rules import GameRules
from scenario import Scenario

TRIALS = 40


def half(*, clock, ballOn, offTimeouts=0, clockRunning=True, quarter=2, down=1,
         distance=10, offScore=14, defScore=0, leg=None):
    scenario = Scenario(gameRules=GameRules())
    if leg is not None:
        scenario.setKickerLeg('home', leg)
    scenario.situation(quarter=quarter, clock=clock, offense='home',
                       offScore=offScore, defScore=defScore, down=down,
                       distance=distance, ballOn=ballOn, offTimeouts=offTimeouts,
                       defTimeouts=3, clockRunning=clockRunning)
    return scenario


def decisions(**kw):
    out = collections.Counter()
    for _ in range(TRIALS):
        scenario = half(**kw)
        scenario.callPlay()
        play = scenario.g.play
        cm = (play.insights.get('clockMgmt') or {}).get('decision')
        out[cm or str(play.playType).replace('PlayType.', '')] += 1
    return out


class TheHalfEndsOnAHeave(unittest.TestCase):

    def test_outOfRangeTheLastSnapIsAHeaveAtAnyScore(self):
        # Kicker reaches the 38; the ball is on the 45, inside any QB's heave.
        for offScore, defScore in ((14, 0), (0, 0), (0, 14)):
            out = decisions(clock=4, ballOn=45, leg=55, offScore=offScore, defScore=defScore)
            self.assertEqual(out['hailMary'], TRIALS, (offScore, defScore, out))

    def test_inRangeItKicks(self):
        out = decisions(clock=4, ballOn=30, leg=60)
        self.assertEqual(out['hailMary'], 0, out)
        self.assertEqual(out['lastSnapFG'], TRIALS, out)

    def test_beyondTheHeaveItIsANormalPlay(self):
        out = decisions(clock=4, ballOn=75, leg=55)
        self.assertEqual(out['hailMary'], 0, out)

    def test_notWhileAnotherSnapFits(self):
        out = decisions(clock=40, ballOn=45, leg=55, offTimeouts=2)
        self.assertEqual(out['hailMary'], 0, out)

    def test_notInTheFirstQuarter(self):
        out = decisions(clock=4, ballOn=45, leg=55, quarter=1)
        self.assertEqual(out['hailMary'], 0, out)


class NoRunThatEndsTheHalf(unittest.TestCase):
    # Clock stopped (a catch out of bounds), 18s left, no timeouts, in range: a run
    # restarts the clock and there is no time to line up the kick after it.
    SPOT = dict(clock=18, ballOn=17, leg=60, clockRunning=False, down=2, distance=2)

    def test_theSpotQualifies(self):
        self.assertTrue(half(**self.SPOT).g._runSpendsTheHalf())

    def test_aTimeoutStopsTheClockAfterTheRun(self):
        self.assertFalse(half(**{**self.SPOT, 'offTimeouts': 1}).g._runSpendsTheHalf())

    def test_onlyAtTheEndOfTheHalf(self):
        self.assertFalse(half(**{**self.SPOT, 'quarter': 1}).g._runSpendsTheHalf())
        self.assertFalse(half(**{**self.SPOT, 'clock': 35}).g._runSpendsTheHalf())

    def test_onlyWithPointsInReach(self):
        self.assertFalse(half(**{**self.SPOT, 'ballOn': 80}).g._runSpendsTheHalf())

    def test_itPasses(self):
        # 54% runs without the rule, 11-12% with it (a QB can still audible into one).
        runs = 0
        for _ in range(200):
            scenario = half(**self.SPOT)
            scenario.callPlay()
            runs += scenario.g.play.insights.get('playCall') == 'run'
        self.assertLessEqual(runs, 40, runs)


class NoTimeoutAfterTheGame(unittest.TestCase):

    def test_aTrailingDefenseDoesNotCallOneAtZero(self):
        for _ in range(TRIALS):
            scenario = half(quarter=4, clock=0, ballOn=60, offScore=27, defScore=25)
            scenario.g._checkDefensiveTimeout()
            self.assertEqual(scenario.g.awayTimeoutsRemaining, 3)


if __name__ == '__main__':
    unittest.main()
