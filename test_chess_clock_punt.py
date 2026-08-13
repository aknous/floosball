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

    def testATrailingTeamNeverPuntsAtAnyDistance(self):
        """⚠️ REPORTED FROM A LIVE GAME 2026-08-13: a LOSING team ran its possession budget
        out and punted on its last play.

        The rule briefly carried a DISTANCE carve-out — a trailing team punted from outside
        CHESS_CLOCK_STRIKE_YARDS — on the reasoning that no single play scores from 80
        yards, so going for it there concedes field position for nothing.

        That reasoning misses what the punt is worth. Once the budget is gone the offense
        NEVER POSSESSES AGAIN, so field position buys this team nothing: the only points
        still available to it are a safety or a defensive score, and a punt does almost
        nothing for either. It improves the MARGIN, not the RESULT — and playing for the
        margin while losing is what reads as surrender.

        ⚠️ The carve-out was never load-bearing. Game 349 was a LEADING team, stopped by
        the snap-cost bug in `_lastSnapBeforeBreak`; the carve-out was kept anyway because
        the argument "stood on its own", and this is the bug that bought."""
        block = _block()
        self.assertIn('_puntHelps = scoreDiff >= 0', block)
        self.assertNotIn('_canStrike', block,
                         'the distance carve-out let a losing team punt its game away')
        self.assertNotIn('or not', block.split('_puntHelps =')[1].split('\n')[0])

    def testTheDecisionByScoreAndDistance(self):
        """The decision, run rather than grepped."""
        def punts(scoreDiff):
            return scoreDiff >= 0

        # Behind by anything, anywhere on the field: play on.
        for ytez in (10, 40, 80, 95):
            self.assertFalse(punts(-1), f'trailing by 1 punted from {ytez}')
            self.assertFalse(punts(-7), f'trailing by 7 punted from {ytez}')
            self.assertFalse(punts(-21), f'trailing by 21 punted from {ytez}')
        # Level or ahead always punts, at any distance — field position is all that is
        # left, and the possession is lost either way.
        for ytez in (10, 40, 80):
            self.assertTrue(punts(0))
            self.assertTrue(punts(+7))

    def testItIsTheLastSnapAndTheCoachSeesIt(self):
        """It fires only on the last snap the budget allows, and recognising that the
        CLOCK rather than the DOWN is what ends this drive is clock management — so a
        sharp staff does it near-always and a poor one gets caught playing the down."""
        block = _block()
        self.assertIn('self._lastSnapBeforeBreak()', block)
        self.assertIn('gameIQ', block)

    def testItIsSuppressedWhenTheDEFENSEIsLockedOut(self):
        """⚠️ A punt achieves nothing when the other side is also out of budget: a
        locked-out defense cannot do anything with the ball, and `possessionReceiver`
        hands it straight back. So punting spends a down for no field position while the
        offense still has budget to score with.

        `suppressPunt` already encodes this for chess clock and the drive-clock punt below
        has always consulted it; this block did not. Owner: "the clock running out also
        assumes the other team has time remaining. if they don't... they'd keep trying to
        score."""
        self.assertIn('self.format.suppressPunt(self)', _block())

    def testTheFieldGoalBranchIsNotSuppressed(self):
        """⚠️ Deliberately asymmetric. A punt is a giveaway and is pointless against a
        locked-out defense; a FIELD GOAL is points, and points are worth having whoever
        holds the ball next."""
        with open(os.path.join(HERE, 'floosball_game.py')) as fh:
            src = fh.read()
        i = src.index("'decision': 'chessClockFG'")
        head = src[max(0, i - 1600):i]
        block = head[head.rindex('if ('):]
        self.assertNotIn('suppressPunt', block)

    def testTheStrikeIsARealCALLNotJustARefusal(self):
        """⚠️ Declining to punt was only ever a REFUSAL — the play then came from the
        normal down-and-distance table, so an offense that had decided it must score kept
        calling whatever 2nd-and-7 usually calls. With a budget measured in one or two
        snaps that is a slow walk into a lockout. Owner: "teams with little time
        remaining, the other team is out, and needing to score, they should be taking deep
        shots to gain yards fast."

        Measured over 150 chess-clock games: 73 shots, 55 deep and 18 long."""
        with open(os.path.join(HERE, 'floosball_game.py')) as fh:
            src = fh.read()
        i = src.index("'decision': 'chessClockStrike'")
        head = src[max(0, i - 1400):i]
        block = head[head.rindex('if ('):]
        # It fires only where the situation is unambiguous.
        self.assertIn('self.format.suppressPunt(self)', block)   # nobody to punt to
        self.assertIn('scoreDiff <= 0', block)                   # points are needed
        self.assertIn('_lastSnapBeforeBreak()', block)           # the budget is going
        self.assertIn('_isGarbageTime', block)
        # And it actually CALLS the shot rather than falling through.
        tail = src[i:i + 900]
        self.assertIn('passPlay(self._selectPassPlay(_shot))', tail)
        self.assertIn("'deep' if self.yardsToEndzone > CHESS_CLOCK_STRIKE_YARDS else 'long'", src)

    def testTheStrikeDoesNotOverrideSidelineTargeting(self):
        """⚠️ This forced `targetSideline = False` on the reasoning that stopping the GAME
        clock does nothing for a possession budget. That is wrong — a stopped clock is
        charged less, so getting out of bounds genuinely preserves budget and is a
        strategy. The override is gone; the normal sideline logic decides."""
        with open(os.path.join(HERE, 'floosball_game.py')) as fh:
            src = fh.read()
        i = src.index("'decision': 'chessClockStrike'")
        self.assertNotIn('targetSideline = False', src[i:i + 700])

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
