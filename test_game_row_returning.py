"""Regression: a game row saves the returner's punt-return line.

⚠️ d0d115d (2026-08-06) added `returning_stats` to the per-game save but never to the dict
`_extractPlayerStatsFromGame` builds, so the save read a key that was never set and wrote
NULL on every game row. Measured on prod: all ~43,000 game rows through season 8 NULL, and
since the week-end card stats are rebuilt from those rows, Runback paid 0 FP on all 73 of its
equipped card-weeks.

Run: python3 test_game_row_returning.py
"""
import unittest
from types import SimpleNamespace

from managers.seasonManager import SeasonManager


class ReturningReachesTheGameRow(unittest.TestCase):

    def testTheExtractedLineCarriesReturns(self):
        returning = {"puntReturns": 3, "puntReturnYards": 41, "puntReturnTds": 0}
        player = SimpleNamespace(id=7, gameStatsDict={
            "passing": {}, "rushing": {"carries": 4}, "receiving": {}, "kicking": {},
            "defense": {}, "returning": returning, "fantasyPoints": 6,
        })
        team = SimpleNamespace(id=1, rosterDict={"rb": player})
        empty = SimpleNamespace(id=2, rosterDict={})
        sm = SeasonManager.__new__(SeasonManager)
        sm.serviceContainer = None
        stats = sm._extractPlayerStatsFromGame(SimpleNamespace(homeTeam=team, awayTeam=empty))
        self.assertEqual(stats[7].get("returning"), returning)


if __name__ == "__main__":
    unittest.main()
