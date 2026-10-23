"""A plays drive clock does not count a snap that gains a first down or makes a sideline goal.

Under "8 plays, whole drive" 75% of offensive scores were field goals: a drive chipped
away at ~6 yards a snap and ran out of snaps around the opponent's 25 (owner, 2026-10-23).
With those snaps free (`DRIVE_CLOCK_FREE_SNAPS`) a drive ends on the clock only when it
stalls. Converting on the last snap keeps the drive alive, so that snap is a final down to
the marker, not a touchdown-or-nothing heave.

Run: .venv/bin/python -m pytest -q test_drive_clock_free_snaps.py
"""
import collections
import logging
import unittest

logging.disable(logging.CRITICAL)

import constants
from game_rules import GameRules
from scenario import Scenario

TRIALS = 30


def scenario(*, down=1, distance=10, ballOn=60, snapsLeft=8, unit='plays',
             reset='possession', quarter=1, clock=600, offScore=0, defScore=0):
    rules = GameRules()
    rules.driveClockEnabled = True
    rules.driveClockUnit = unit
    rules.driveClockReset = reset
    rules.driveClockLimit = 8 if unit == 'plays' else 120
    sc = Scenario(gameRules=rules)
    sc.situation(quarter=quarter, clock=clock, offense='home', offScore=offScore,
                 defScore=defScore, down=down, distance=distance, ballOn=ballOn,
                 offTimeouts=3, defTimeouts=3, clockRunning=True)
    sc.game.driveClockRemaining = snapsLeft
    return sc


class TheSwitchIsOn(unittest.TestCase):

    def test_onByDefault(self):
        self.assertTrue(constants.DRIVE_CLOCK_FREE_SNAPS)

    def test_thePresetSaysSo(self):
        preset = next(p for p in constants.DRIVE_CLOCK_PRESETS
                      if p['key'] == 'dc_8plays_possession')
        self.assertIn("first downs and sideline goals don't count", preset['label'])


class AFirstDownSnapIsFree(unittest.TestCase):

    def test_theSnapIsGivenBack(self):
        game = scenario(snapsLeft=5).game
        game._tickDriveClockPlays()
        game._driveClockRefillOnFirstDown()
        self.assertEqual(game.driveClockRemaining, 5)

    def test_convertingOnTheLastSnapKeepsTheDrive(self):
        game = scenario(snapsLeft=1).game
        game._tickDriveClockPlays()
        self.assertTrue(game._driveClockExpired())
        game._driveClockRefillOnFirstDown()
        self.assertFalse(game._driveClockExpired())
        self.assertFalse(game.driveClockExpiredThisPlay)
        self.assertEqual(game.driveClockRemaining, 1)

    def test_neverPastTheLimit(self):
        game = scenario(snapsLeft=8).game
        game._refundDriveClockSnap()
        self.assertEqual(game.driveClockRemaining, 8)

    def test_aSecondsClockIsUntouched(self):
        game = scenario(unit='seconds', snapsLeft=60).game
        game._driveClockRefillOnFirstDown()
        self.assertEqual(game.driveClockRemaining, 60)

    def test_offTheSwitchItCounts(self):
        old = constants.DRIVE_CLOCK_FREE_SNAPS
        constants.DRIVE_CLOCK_FREE_SNAPS = False
        try:
            game = scenario(snapsLeft=5).game
            game._tickDriveClockPlays()
            game._driveClockRefillOnFirstDown()
            self.assertEqual(game.driveClockRemaining, 4)
        finally:
            constants.DRIVE_CLOCK_FREE_SNAPS = old


class AMadeSidelineGoalIsFree(unittest.TestCase):
    """The hoop resolves inside the play call, before the snap is ticked, so the loop
    refunds it after the tick. Checked at the call site, since testing only the helper
    would pass with the loop never calling it."""

    def test_theLoopRefundsAMake(self):
        import inspect, floosball_game
        src = inspect.getsource(floosball_game.Game)
        tick = src.index('self._tickDriveClockPlays()\n')
        after = src[tick:tick + 400]
        self.assertIn("getattr(self.play, 'hoopMade', False)", after)
        self.assertIn('self._refundDriveClockSnap()', after)


class TheLastSnapPlaysToTheMarker(unittest.TestCase):

    def test_theMarkerIsTheYardsToGo(self):
        game = scenario(down=2, distance=6, ballOn=45, snapsLeft=1).game
        self.assertTrue(game._driveClockFinalSnap())
        self.assertFalse(game._driveClockOnlyTdSaves())
        self.assertEqual(game._decisionYardsToGo(), 6)

    def test_noHeaveFromDistance(self):
        """From the opponent's 47 with the marker 3 yards away, the last snap is a short
        conversion, not a Hail Mary."""
        out = collections.Counter()
        for _ in range(TRIALS):
            sc = scenario(down=2, distance=3, ballOn=47, snapsLeft=1, quarter=4,
                          clock=300, defScore=3)
            sc.callPlay()
            out[sc.game.play.insights.get('playCall')] += 1
        self.assertEqual(out['hailMary'], 0, out)


class ChunkPace(unittest.TestCase):
    """Behind the pace the clock demands, the offense leans toward chunk throws from the
    start of the drive, not only in its last few snaps."""

    def _weights(self, snapsLeft, ballOn):
        game = scenario(snapsLeft=snapsLeft, ballOn=ballOn).game
        coach = game.offensiveTeam.coach
        base = {'run': 40.0, 'short': 26.0, 'medium': 10.0, 'long': 14.0, 'deep': 10.0}
        return game._applyDriveClockMods(dict(base), coach), base

    def test_aFreshDriveFromTheOwn25LeansDeep(self):
        w, base = self._weights(snapsLeft=8, ballOn=75)
        self.assertLess(w['run'], base['run'])
        self.assertGreater(w['long'], base['long'])
        self.assertGreater(w['deep'], base['deep'])

    def test_onPaceCallsItStraight(self):
        w, base = self._weights(snapsLeft=8, ballOn=30)
        self.assertEqual(w, base)


if __name__ == '__main__':
    unittest.main()
