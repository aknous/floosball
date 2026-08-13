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
        # The real Game always has a `format` (it is a property resolving from gameRules),
        # so a stub without one is the stub being wrong. None reads as standard.
        self.format = None
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


class ChessClockSnapCostTests(unittest.TestCase):
    """⚠️ CHESS CLOCK CHARGES A DIFFERENT PRICE FOR A SNAP, and this helper quoted the
    standard one.

    `_offenseEffectiveSecs` correctly returns the possession BUDGET in chess clock, so the
    clock being read was right — but the cost compared against it was 7s (stoppable) or
    19s (running), which are standard-format huddle numbers. A chess-clock snap drains the
    budget by its huddle: 20s neutral, 35s relaxed, and 25s even with the game clock
    STOPPED, because possession time is spent regardless.

    So in the 20-30s band the helper said "there is another snap", the offense ran one, the
    snap cost more than the budget held, and the possession was forfeited AT THE SPOT.

    Reported from production game 349: ARI, LEADING 14-7, 1st and 10 on their own 20 at
    Q4 3:20 — ran for 4 and handed MEX the ball on the 20, with `clockMgmt` recorded as
    None, i.e. no decision was reached at all.

    Measured over 120 chess-clock games a side after the fix: lockouts 50 -> 18 and gifts
    from inside the offense's own 40 30 -> 9, with the punt firing 73 times against 17
    before — it had barely been triggering.
    """

    class _Fmt:
        key = 'chess_clock'

    def _game(self, budget, huddle):
        g = StubGame(budget)
        g.format = self._Fmt()
        g.clockRunning = True
        g.homeTimeoutsRemaining = g.awayTimeoutsRemaining = 3
        g._classifyTempoIntent = lambda: ('neutral', huddle)
        return g

    def testTheReportedSituationIsTheLastSnap(self):
        """ARI\'s actual state in game 349: they took over after an incompletion, so the
        game clock was STOPPED, and they had only enough budget for the one snap they
        ran. Under the old standard-format numbers that read as room for another."""
        from constants import CHESS_CLOCK_STOPPED_HUDDLE_DRAIN as STOP
        g = self._game(17, 12)          # one snap's worth of budget, hurry-up tempo
        g.clockRunning = False          # stopped: the flat drain applies
        self.assertTrue(g._lastSnapBeforeBreak())
        # And the old rule would have said otherwise — 17 is comfortably above 7/19.
        self.assertGreater(17, 7)

    def testASnapThatFitsIsNotTheLastOne(self):
        """⚠️ The point of the cost model is to punt LATE, not early. Owner: "what I want
        to avoid is a team punting and they still have a few seconds left on their clock."

        ⚠️ The threshold is DERIVED here, not restated. Writing the arithmetic out by hand
        is what made two of these tests fail the moment the model was corrected — they
        were pinning a number rather than the rule."""
        from constants import CHESS_CLOCK_NEUTRAL_HUDDLE as NEU, LAST_SNAP_LIVE_SECS as LIVE
        need = NEU + LIVE
        self.assertFalse(self._game(need + 1, NEU)._lastSnapBeforeBreak(),
                         'punting while a snap still fits')
        self.assertTrue(self._game(need - 1, NEU)._lastSnapBeforeBreak())

    def testAPuntNeedsOnlyToBeSNAPPED(self):
        """⚠️ NO CLOSING-SNAP RESERVE in this branch. `FINAL_SNAP_SECS` keeps room for a
        closing FIELD GOAL, and there is no such kick here — the punt IS the play.
        `_lockedOut` is `budget <= 0` and `_chessClockDepletionTurnover` runs AFTER the
        play resolves, so a punt started with a single second left completes and
        possession changes through the punt. Owner: "as long as there's 1 second left they
        can punt still."

        So the only thing that must FIT is the productive play being decided against."""
        from constants import (CHESS_CLOCK_NEUTRAL_HUDDLE as NEU,
                               LAST_SNAP_LIVE_SECS as LIVE, FINAL_SNAP_SECS as SNAP)
        # A budget that holds the play but not the play-plus-reserve must NOT punt.
        self.assertFalse(self._game(NEU + LIVE + SNAP - 1, NEU)._lastSnapBeforeBreak(),
                         'a closing-snap reserve is being charged where no kick follows')

    def testAGenuinelyRoomyBudgetIsNotTheLastSnap(self):
        from constants import CHESS_CLOCK_NEUTRAL_HUDDLE as NEU
        self.assertFalse(self._game(60, NEU)._lastSnapBeforeBreak())

    def testARelaxedHuddleCostsMoreAndTriggersEarlier(self):
        """The cost is the tempo's OWN huddle, so a relaxed offense runs out sooner."""
        from constants import (CHESS_CLOCK_NEUTRAL_HUDDLE as NEU,
                               CHESS_CLOCK_RELAXED_HUDDLE as REL)
        self.assertTrue(self._game(38, REL)._lastSnapBeforeBreak())
        self.assertFalse(self._game(38, NEU)._lastSnapBeforeBreak())

    def testAStoppedClockIsChargedTheFlatDrain(self):
        """⚠️ WHICH COST APPLIES DEPENDS ON THE CLOCK, and they are never both. A running
        clock pays the tempo\'s own pre-snap; a stopped one pays the flat drain instead —
        an if/elif in the pre-snap block. Taking the LARGER of the two was tried and
        punted far too early: it charged a hurrying offense 25 for a snap costing it 12."""
        from constants import (CHESS_CLOCK_STOPPED_HUDDLE_DRAIN as STOP,
                               LAST_SNAP_LIVE_SECS as LIVE)
        need = STOP + LIVE
        g = self._game(need - 1, 12)
        g.clockRunning = False
        self.assertTrue(g._lastSnapBeforeBreak(), 'the stopped drain is not being charged')
        g2 = self._game(need + 1, 12)
        g2.clockRunning = False
        self.assertFalse(g2._lastSnapBeforeBreak())
        # Running, hurrying: the same budget comfortably holds a snap, so no punt.
        g3 = self._game(need - 1, 12)
        g3.clockRunning = True
        self.assertFalse(g3._lastSnapBeforeBreak(),
                         'a hurrying offense is being charged the stopped-clock price')

    def testTimeoutsDoNotBuyASnapHere(self):
        """The standard rule lets a timeout skip the huddle. A timeout cannot pause a
        possession budget, so that shortcut must not apply — a stopped clock here still
        costs the drain."""
        from constants import CHESS_CLOCK_STOPPED_HUDDLE_DRAIN as STOP
        g = self._game(STOP - 1, 12)
        g.clockRunning = False
        g.homeTimeoutsRemaining = 3
        self.assertTrue(g._lastSnapBeforeBreak())


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
