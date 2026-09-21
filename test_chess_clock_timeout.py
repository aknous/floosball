"""Chess clock: spend a timeout before a down, at any score.

Reported from prod game 2779: the Strangers, up 27-3 with their possession budget
nearly gone, went hurry-up and SPIKED to preserve it — and never called a timeout,
finishing the game with all three in hand. Two rules disagreed about the scoreboard:

- the last-gasp tempo and the chess-clock spike ignore it ("a lockout is a turnover at
  the spot whatever the lead"),
- the only budget-preserving timeout (`chessBudgetNeed` in `_maybeCallTimeoutToSaveSnap`)
  required trailing/tied.

So a leading offense could stop the clock only by forfeiting a down. The timeout now
follows the same rule as the tempo and the spike, and the chess-clock spike (like the
standard one) requires no timeouts left — a timeout stops the clock just as well and
keeps the down.

Measured over 150 synthetic chess-clock games, same seeds: chess-clock spikes thrown
with a timeout in hand 86 of 120 -> 0 of 56; mid-drive lockouts 31 -> 13.

Run: .venv/bin/python test_chess_clock_timeout.py
"""
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import logging
logging.disable(logging.CRITICAL)

import managers  # noqa: F401  — breaks the floosball_game circular import
import floosball_game as fg
from floosball_game import PlayType
from constants import CHESS_CLOCK_TIMEOUT_PRESERVE_SECS

HERE = os.path.dirname(os.path.abspath(__file__))


class Team:
    def __init__(self, name):
        self.name = name


class StubPlay:
    def __init__(self, playType):
        self.playType = playType
        self.insights = {}


class Fmt:
    def __init__(self, key):
        self.key = key


class StubGame:
    _maybeCallTimeoutToSaveSnap = fg.Game._maybeCallTimeoutToSaveSnap
    _callTimeout = fg.Game._callTimeout
    _isGarbageTime = fg.Game._isGarbageTime
    _chessClockLow = fg.Game._chessClockLow

    def __init__(self, *, budget, homeScore, awayScore, quarter=4, secs=298,
                 timeouts=3, clockRunning=True, playType=PlayType.Run, fmt='chess_clock'):
        self.homeTeam, self.awayTeam = Team('NYS'), Team('PHI')
        self.offensiveTeam = self.homeTeam
        self.format = Fmt(fmt)
        self.budget = budget
        self.currentQuarter = quarter
        self.gameClockSeconds = secs
        self.homeScore, self.awayScore = homeScore, awayScore
        self.homeTimeoutsRemaining = self.awayTimeoutsRemaining = timeouts
        self.clockRunning = clockRunning
        self.play = StubPlay(playType)
        self._timeoutCalled = False
        self.gameFeed = []

    def _chessClockOffenseSecs(self):
        return self.budget if self.format.key == 'chess_clock' else None

    def _offenseEffectiveSecs(self):
        return self.budget if self.format.key == 'chess_clock' else self.gameClockSeconds

    def _isNoHuddle(self):
        return True   # prod 2779 was no-huddle; chess clock is exempt from that check

    def _noHuddlePreSnapSecs(self):
        return 6

    def _oneScore(self):
        return 7

    def _maxPossession(self):
        return 8

    def formatTime(self, s):
        return f'{s}s'

    def broadcastGameState(self, **kw):
        pass


def calledTimeout(**kw):
    g = StubGame(**kw)
    before = g.homeTimeoutsRemaining
    g._maybeCallTimeoutToSaveSnap()
    return g.homeTimeoutsRemaining < before and not g.clockRunning


LOW = 40   # budget seconds — inside both the timeout window and the spike threshold


class ChessClockTimeoutTests(unittest.TestCase):
    def testTheReportedCaseALeaderSavesItsBudget(self):
        """Prod 2779: Q4 4:58, up 27-3, budget nearly out, three timeouts."""
        self.assertTrue(calledTimeout(budget=LOW, homeScore=27, awayScore=3))

    def testTrailingAndTiedStillDo(self):
        self.assertTrue(calledTimeout(budget=LOW, homeScore=3, awayScore=10))
        self.assertTrue(calledTimeout(budget=LOW, homeScore=10, awayScore=10))

    def testAnyQuarter(self):
        self.assertTrue(calledTimeout(budget=LOW, homeScore=14, awayScore=0, quarter=3, secs=600))

    def testNotWhileTheBudgetIsHealthy(self):
        self.assertFalse(calledTimeout(budget=CHESS_CLOCK_TIMEOUT_PRESERVE_SECS + 30,
                                       homeScore=27, awayScore=3))

    def testNotWithNoneLeft(self):
        self.assertFalse(calledTimeout(budget=LOW, homeScore=27, awayScore=3, timeouts=0))

    def testNotForAPunt(self):
        self.assertFalse(calledTimeout(budget=LOW, homeScore=27, awayScore=3,
                                       playType=PlayType.Punt))

    def testAHopelessChaseStillGivesUp(self):
        """Garbage time looks only DOWNWARD, so it still spares a buried trailer."""
        self.assertFalse(calledTimeout(budget=LOW, homeScore=0, awayScore=40, secs=100))

    def testStandardFormatLeaderStillDrains(self):
        """Outside chess clock nothing changed: a Q4 leader lets the clock run."""
        self.assertFalse(calledTimeout(budget=LOW, homeScore=14, awayScore=7, secs=8,
                                       fmt='standard'))

    def testTheChessSpikeWaitsForTheTimeoutsToBeGone(self):
        """The spike costs a down; with a timeout in hand the play is called and the
        save-snap timeout stops the clock instead. Mirrors the standard spike's gate."""
        with open(os.path.join(HERE, 'floosball_game.py')) as fh:
            src = fh.read()
        end = src.index("'reason': 'Preserve the possession clock'")
        start = src.rindex('if (self._chessClockLow(45)', 0, end)
        self.assertIn('timeoutsLeft == 0', src[start:end])
        # ...and `timeoutsLeft` there is playCaller's own, set before the block.
        body = re.search(r'    def playCaller\(self\):.*?\n    def ', src, re.S).group(0)
        self.assertLess(body.index('timeoutsLeft = '), body.index('if (self._chessClockLow(45)'))


if __name__ == '__main__':
    unittest.main(verbosity=2)
