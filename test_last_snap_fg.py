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
from constants import LAST_SNAP_WINDOW_SECS


class StubGame:
    _lastSnapBeforeBreak = fg.Game._lastSnapBeforeBreak

    def __init__(self, secs):
        self.gameClockSeconds = secs

    def _offenseEffectiveSecs(self):
        return self.gameClockSeconds


class LastSnapWindowTests(unittest.TestCase):
    def testAnExpiredClockIsAlwaysTheLastSnap(self):
        self.assertTrue(StubGame(0)._lastSnapBeforeBreak())
        self.assertTrue(StubGame(-3)._lastSnapBeforeBreak())

    def testTheWindowCoversASnapThatWouldNotFit(self):
        """A snap is a hurry-up huddle (~12s) plus the live ball (4-6s for a run), so
        under ~18s there is no play after this one. The reported reading was a run at
        roughly 0:15."""
        self.assertTrue(StubGame(15)._lastSnapBeforeBreak(),
                        'a run at 0:15 leaves no time for another snap')
        self.assertTrue(StubGame(LAST_SNAP_WINDOW_SECS)._lastSnapBeforeBreak())

    def testPlentyOfClockIsNotTheLastSnap(self):
        """The rule must not fire while a drive still has plays in it, or an offense
        kicks from the 40 with a minute left instead of driving."""
        self.assertFalse(StubGame(LAST_SNAP_WINDOW_SECS + 1)._lastSnapBeforeBreak())
        self.assertFalse(StubGame(45)._lastSnapBeforeBreak())
        self.assertFalse(StubGame(120)._lastSnapBeforeBreak())

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
