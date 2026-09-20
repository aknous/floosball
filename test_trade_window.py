"""The trade window is ONE rule, and a closed market serves no listings.

⚠️ THIS EXISTS BECAUSE THE RULE WAS IN TWO PLACES AND NEITHER HELD BOTH ENDS.
`runWeeklyPass` carried the deadline (`week > GM_ACTIVE_WEEK`) and `listingsFor`
carried the opening (`hasClarity`), so any caller reaching for listings directly
got a market that never closed. `/api/transactions` is exactly such a caller, and
measured on production at week 28 it served 29 live listings six weeks after the
deadline. A reader cannot tell a stale listing from a live one.
"""
import unittest
from constants import GM_ACTIVE_WEEK, TRADE_MIN_CERTAINTY
import trading
from managers.tradeManager import (
    tradeWindowState, tradeWindowOpen,
    TRADE_WINDOW_OPEN, TRADE_WINDOW_EARLY, TRADE_WINDOW_DEADLINE_PASSED,
    TRADE_WINDOW_DISABLED,
)


def _firstOpenWeek():
    """Derived, not hardcoded: TRADE_MIN_CERTAINTY is a tunable."""
    for w in range(1, 40):
        if trading.contentionRamp(w) >= TRADE_MIN_CERTAINTY:
            return w
    raise AssertionError("the market never opens")


class TestTradeWindow(unittest.TestCase):

    def testDeadlineCloses(self):
        """The week AFTER the deadline is shut. This is the half the API never had."""
        self.assertEqual(tradeWindowState(GM_ACTIVE_WEEK + 1),
                         TRADE_WINDOW_DEADLINE_PASSED)
        self.assertFalse(tradeWindowOpen(GM_ACTIVE_WEEK + 1))
        # production's actual state when this was found
        self.assertFalse(tradeWindowOpen(28))

    def testDeadlineWeekItselfIsStillOpen(self):
        """The deadline is the last day of the market, not the first day after it."""
        self.assertTrue(tradeWindowOpen(GM_ACTIVE_WEEK))

    def testEarlySeasonClosed(self):
        """Before clubs know their season, nothing goes on the block."""
        self.assertEqual(tradeWindowState(1), TRADE_WINDOW_EARLY)
        self.assertFalse(tradeWindowOpen(_firstOpenWeek() - 1))

    def testOpensAtClarity(self):
        self.assertTrue(tradeWindowOpen(_firstOpenWeek()))

    def testOffseasonIsOpen(self):
        """⚠️ week=None is the market's own convention for an offseason pass, and both
        offseason passes run before free agency. A deadline test on the week number
        alone would shut the very market the offseason exists for."""
        self.assertEqual(tradeWindowState(None), TRADE_WINDOW_OPEN)
        self.assertTrue(tradeWindowOpen(None))

    def testKillSwitchWins(self):
        import constants
        real = constants.tradingEnabled
        constants.tradingEnabled = lambda session=None: False
        try:
            self.assertEqual(tradeWindowState(None), TRADE_WINDOW_DISABLED)
            self.assertEqual(tradeWindowState(GM_ACTIVE_WEEK), TRADE_WINDOW_DISABLED)
            self.assertFalse(tradeWindowOpen(GM_ACTIVE_WEEK))
        finally:
            constants.tradingEnabled = real

    def testWeeklyPassUsesTheSharedWindow(self):
        """The pass must not keep its own copy of the deadline.

        A private copy is how the two drifted in the first place, so this reads the
        source rather than the behaviour: behaviourally the two are indistinguishable
        while they happen to agree, which is precisely the state that shipped.
        """
        import inspect
        from managers import tradeManager
        src = inspect.getsource(tradeManager.runWeeklyPass)
        self.assertIn('tradeWindowOpen(week)', src)
        self.assertNotIn('GM_ACTIVE_WEEK', src,
                         "runWeeklyPass is testing the deadline itself again")

    def testApiGatesTheBlockOnTheWindow(self):
        """The fan-facing table is the caller that was serving a closed market."""
        import inspect, re
        import api.main as main
        src = inspect.getsource(main.get_transactions)
        self.assertIn('tradeWindowState', src)
        # the listings loop must sit behind the open check, not behind tradingEnabled()
        self.assertRegex(src, r'if\s+windowState\s*==\s*TRADE_WINDOW_OPEN')
        self.assertNotRegex(src, r'if\s+tradingOn\s+and\s+sm\s+and\s+sm\.currentSeason')


if __name__ == '__main__':
    unittest.main()
