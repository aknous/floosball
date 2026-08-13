"""Chess clock: punt on the last snap rather than gift the spot.

⚠️ A CHESS-CLOCK LOCKOUT IS A TURNOVER AT THE SPOT. `_chessClockDepletionTurnover` calls
`turnover(..., self.yardsToSafety)`, so an offense that lets its possession budget run out
on its own 8 hands the opponent the ball on the 8. Reported: teams deep in their own end
playing on until the clock died and gifting an easy score.

The possession is lost EITHER WAY, so the only thing still on the table is field position,
and a punt is worth ~40 yards of it. That makes this the exact counterpart of the existing
`chessClockFG` decision: same trigger, and where a kick would have banked points, a punt
banks field.

⚠️ TRAILING IS THE EXCEPTION. Once the budget is gone the offense never possesses again,
so a trailing team's last snap is its last chance to score — punting there concedes the
game to buy field position it will never use.

Measured over 120 chess-clock games a side: lockouts 52 -> 41, and the ones that matter —
a gift from inside the offense's OWN 40 — **22 -> 14 (-36%)**, with the decision firing 17
times and exactly 0 with the flag off.

Run: .venv/bin/python test_chess_clock_punt.py
"""

import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import logging
logging.disable(logging.CRITICAL)

import managers  # noqa: F401  — breaks the floosball_game circular import
from constants import CHESS_CLOCK_PUNT_ENABLED

HERE = os.path.dirname(os.path.abspath(__file__))


def _block():
    """The chessClockPunt decision, as source."""
    with open(os.path.join(HERE, 'floosball_game.py')) as fh:
        src = fh.read()
    start = src.index('# ⚠️ OUT OF RANGE ON THE LAST SNAP: PUNT')
    return src[start:src.index('# Drive Clock about to expire', start)]


class ChessClockPuntTests(unittest.TestCase):
    def testTheDecisionExistsAndPunts(self):
        block = _block()
        self.assertIn("'decision': 'chessClockPunt'", block)
        self.assertIn('self.play.playType = PlayType.Punt', block)

    def testOnlyOutOfKickRange(self):
        """In range the existing chessClockFG block already took the points — this is its
        counterpart, not a competitor. Range is read from THIS kicker (and its charged
        extension), never a constant."""
        block = _block()
        self.assertIn('self.yardsToEndzone > _ppKMax', block)
        self.assertIn('maxFgDistance', block)
        self.assertIn('_chargedKickerMaxFg', block)

    def testATrailingTeamDoesNotPunt(self):
        """⚠️ The exception that makes this correct rather than merely tidy. Once the
        budget is gone the offense never possesses again, so punting while behind concedes
        the game for field position it will never use."""
        self.assertIn('scoreDiff >= 0', _block())

    def testItIsTheLastSnapAndTheCoachSeesIt(self):
        """It fires only on the last snap the budget allows, and recognising that the
        CLOCK rather than the DOWN is what ends this drive is clock management — so a
        sharp staff does it near-always and a poor one gets caught playing the down."""
        block = _block()
        self.assertIn('self._lastSnapBeforeBreak()', block)
        self.assertIn('gameIQ', block)

    def testGarbageTimeIsExcluded(self):
        self.assertIn('_isGarbageTime', _block())

    def testItIsFlagged(self):
        """Every layer here gets an independent switch, so an A/B toggles this rule and
        nothing else. ⚠️ The first measurement tried to undo the decision after the fact
        by re-running playCaller — that re-rolled its randomness and mutated insights, and
        the arms diverged so badly the 'off' arm reported FEWER lockouts than 'on'."""
        self.assertIn('CHESS_CLOCK_PUNT_ENABLED', _block())
        self.assertTrue(CHESS_CLOCK_PUNT_ENABLED, 'shipped default should be on')

    def testItSitsWithTheOtherChessClockDecision(self):
        """Next to chessClockFG, inside the non-final-down clock-management block — the
        final down already reaches _fourthDownCaller, which punts on its own."""
        with open(os.path.join(HERE, 'floosball_game.py')) as fh:
            src = fh.read()
        self.assertLess(src.index("'decision': 'chessClockFG'"),
                        src.index("'decision': 'chessClockPunt'"))
        self.assertIn('self.down < self.gameRules.downsPerSeries', _block())


class LockoutIsASpotTurnoverTests(unittest.TestCase):
    """The premise. If this ever stops being true the rule loses its point, so it is
    asserted rather than assumed."""

    def testTheOpponentTakesOverAtTheSpot(self):
        with open(os.path.join(HERE, 'floosball_game.py')) as fh:
            src = fh.read()
        body = re.search(r'def _chessClockDepletionTurnover\(.*?\n    def ', src, re.S).group(0)
        self.assertIn('self.turnover(self.offensiveTeam, self.defensiveTeam, self.yardsToSafety)',
                      body,
                      'a lockout no longer hands the ball over at the spot — re-check '
                      'whether the punt still buys anything')


if __name__ == '__main__':
    unittest.main(verbosity=2)
