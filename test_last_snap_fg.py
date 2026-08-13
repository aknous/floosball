"""The last snap of a half is the last snap, whatever the down number says.

⚠️ "IS THIS MY LAST CHANCE" WAS BEING ASKED AS "IS THIS MY LAST DOWN". `playCaller`
splits on `down < downsPerSeries` (clock management) versus `down == downsPerSeries`
(`_fourthDownCaller`), and only the second branch knows how to end a half — it takes a
makeable field goal once the clock dips inside ~15-35s. That is fine for as long as the
last down IS the fourth.

`downsPerSeries` is a MUTABLE RULE (3 to 5 — the Cores change it). At five downs a 4th
down is no longer final, so it takes the clock-management branch, which had no
end-of-half kick of its own. Reported from a live game: 4th and 3 on the opponent's 11 —
a ~28 yard kick — run for a single yard as the clock hit 0:00, half over, no points.
Owner: "the play was genuinely the last play of the half, so down should not have
mattered."

Measured over 150 games a side, five-down ruleset: halves that expired with the ball in
range and no kick fell **61 -> 39 (-36%)** and late field-goal attempts rose 91 -> 107.
At four downs, where `_fourthDownCaller` already covered the final down, attempts rose
89 -> 110 and wasted halves were flat.

⚠️ A SECOND FIX WAS TRIED AND REVERTED, and the reason is recorded in the engine:
`_estimateAvailablePlays` counts a play that does not fit (it enters on `secs > 2` then
subtracts the 7 a play costs), so at 0:15 it reports two plays when one run does not fit
once. Tightening it measured WORSE — late FG attempts 33 -> 18 at four downs — because
that count feeds eight decisions with opposite senses (`<= 1` kicks, `>= 2` hurries up,
`>= 1` allows a spike), so lowering it buys a kick and loses the clock management that
gets a drive into range at all.

Run: .venv/bin/python test_last_snap_fg.py
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import logging
logging.disable(logging.CRITICAL)

import managers  # noqa: F401  — breaks the floosball_game circular import
import floosball_game as fg
from constants import (FINAL_SNAP_SECS, LAST_SNAP_HUDDLE_SECS,
                       LAST_SNAP_LIVE_SECS)


STOPPABLE = LAST_SNAP_LIVE_SECS + FINAL_SNAP_SECS                       # ~7s
RUNNING = STOPPABLE + LAST_SNAP_HUDDLE_SECS                            # ~19s


class StubGame:
    _lastSnapBeforeBreak = fg.Game._lastSnapBeforeBreak

    def __init__(self, secs, clockRunning=True, timeouts=0):
        self.gameClockSeconds = secs
        self.clockRunning = clockRunning
        self.homeTimeoutsRemaining = self.awayTimeoutsRemaining = timeouts
        self.offensiveTeam = self.homeTeam = object()
        self.awayTeam = object()

    def _offenseEffectiveSecs(self):
        return self.gameClockSeconds


class LastSnapWindowTests(unittest.TestCase):
    def testAnExpiredClockIsAlwaysTheLastSnap(self):
        self.assertTrue(StubGame(0)._lastSnapBeforeBreak())
        self.assertTrue(StubGame(-3)._lastSnapBeforeBreak())

    def testAClockRunningWithNoTimeoutNeedsTheWholeHuddle(self):
        """Nothing can stop the clock, so another snap costs a hurry-up huddle (~12s)
        plus the live ball before the kick can even be snapped. The reported play ran at
        roughly 0:17."""
        self.assertTrue(StubGame(15, clockRunning=True, timeouts=0)._lastSnapBeforeBreak(),
                        'a run at 0:15 with the clock live and no timeout leaves no snap')
        self.assertTrue(StubGame(RUNNING - 1, True, 0)._lastSnapBeforeBreak())
        self.assertFalse(StubGame(RUNNING, True, 0)._lastSnapBeforeBreak())

    def testAStoppableClockEarnsTheWiderWindow(self):
        """⚠️ THE WINDOW IS NOT ONE NUMBER. With the clock stopped, or a timeout in hand
        to stop it, the huddle is skipped and a play plus the kick fit inside ~7s — so an
        offense that has managed its clock keeps the options it earned. Owner: "18 seconds
        seems like a lot of time, I would expect it to be around the 8 second mark"."""
        # Two ways to be stoppable: the clock is live but a timeout is in hand, or it is
        # already stopped. Either way the huddle is skipped.
        for running, tos in ((True, 2), (False, 0)):
            self.assertFalse(StubGame(15, clockRunning=running, timeouts=tos)._lastSnapBeforeBreak(),
                             'a team that can stop the clock still has a play at 0:15')
            self.assertTrue(StubGame(STOPPABLE - 1, running, tos)._lastSnapBeforeBreak())

    def testPlentyOfClockIsNeverTheLastSnap(self):
        """The rule must not fire while a drive still has plays in it, or an offense
        kicks from the 40 with a minute left instead of driving."""
        for running, tos in ((True, 0), (True, 3), (False, 0), (False, 3)):
            self.assertFalse(StubGame(45, running, tos)._lastSnapBeforeBreak())
            self.assertFalse(StubGame(120, running, tos)._lastSnapBeforeBreak())

    def testItDoesNotConsultTheDownAtAll(self):
        """THE POINT. The helper takes no down and reads none — that is what makes the
        decision independent of a mutable rule."""
        import inspect
        src = inspect.getsource(fg.Game._lastSnapBeforeBreak)
        self.assertNotIn('self.down', src)
        self.assertNotIn('downsPerSeries', src.split('"""')[-1],
                         'the executable body must not branch on the ruleset')


class PlacementTests(unittest.TestCase):
    """Where the rule sits is the whole fix — inside either branch it would inherit the
    down split it exists to bypass."""

    @staticmethod
    def _source():
        here = os.path.dirname(os.path.abspath(__file__))
        with open(os.path.join(here, 'floosball_game.py')) as fh:
            return fh.read()

    def testTheRuleIsCalledAboveTheDownSplit(self):
        src = self._source()
        call = src.index('_lastSnapBeforeBreak()')
        split = src.index('# Clock management — evaluated before any play selection on non-final downs')
        self.assertLess(call, split,
                        'the last-snap kick sits below the down split, so it is back to '
                        'being a down-dependent decision')

    def testTheDeadDisjunctIsGone(self):
        """⚠️ The end-of-half branch inside the clock-management block tested
        `down == downsPerSeries` while the enclosing gate is `down < downsPerSeries` —
        unreachable by construction, which is what left that path resting entirely on the
        play estimate."""
        src = self._source()
        block = src[src.index("endOfHalfPush = ("):]
        block = block[:block.index('# Late-game FG')]
        self.assertNotIn('self.down == self.gameRules.downsPerSeries', block)

    def testTheSneakLookGuardFollowsTheRuleset(self):
        """⚠️ It read `down >= 4`, which is only the final down when the ruleset runs
        four. At THREE downs the guard never fired and the fake could be called on the
        down that ends the drive — the exact case it exists to prevent."""
        src = self._source()
        block = src[src.index('def _selectSneakLook'):]
        block = block[:block.index('\n    def ', 10)]
        self.assertIn('self.down >= self.gameRules.downsPerSeries', block)
        self.assertNotIn('self.down >= 4', block)

    def testTheConversionStatsArePositional(self):
        """`down == 3` / `down == 4` measured the wrong downs the moment the rule moved:
        at five downs the fourth-down counter logged a routine down, at three it could
        never log anything and the third-down counter was silently the FINAL down.
        Attempts and conversions must agree, or the rate mixes two different downs."""
        src = self._source()
        self.assertNotIn('if self.down == 3:\n                        self.home3rdDownAtt', src)
        self.assertIn('_lastDown = self.gameRules.downsPerSeries', src)
        self.assertNotIn('if downBefore == 3:', src)
        self.assertEqual(src.count('_setupDown = _lastDown - 1'), 2,
                         'attempts and conversions must both be positional')


if __name__ == '__main__':
    unittest.main(verbosity=2)
