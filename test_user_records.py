"""Fantasy records come from the banked lineup snapshot, not the dead roster tables.

⚠️ THIS IS THE THIRD TIME `fantasy_rosters` / `fantasy_roster_players` HAVE SILENTLY
EMPTIED A FEATURE. The fantasy/cards fusion made the EQUIPPED CARDS the roster and left
both tables unwritten — measured: **0 rows in each** — so anything joining them matches
nothing and reports nothing, without erroring.

They have now taken:
  1. Field General's backfill,
  2. the Veteran achievement (a whole season with nobody credited), and
  3. `/api/history/user-records`, which returned `{"weeklyFP": [], "seasonFP": []}` on
     production and showed an empty Fantasy Records page. Reported as "fantasy records
     don't seem to be working".

⚠️ THE BANKED RECORD IS `weekly_card_bonuses`. Its `breakdowns_json` is written once when
a week settles and never revised, and it carries the `playerId` of every slot — the only
honest answer to "who did this user field in week N". `equipped_cards` is the LIVE lineup
and is carried forward week to week, so reading it would score every past week against
today's hand; the fantasy leaderboards had to learn the same rule.

Run: .venv/bin/python test_user_records.py
"""

import os
import re
import sys
import json
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import logging
logging.disable(logging.CRITICAL)

HERE = os.path.dirname(os.path.abspath(__file__))


def _endpoint() -> str:
    with open(os.path.join(HERE, 'api', 'main.py')) as fh:
        src = fh.read()
    start = src.index('async def get_history_user_records')
    return src[start:src.index('\n@app.', start)]


def _code(block: str) -> str:
    """The block with ONLY its leading docstring stripped.

    ⚠️ NOT a blanket `re.sub('\"\"\".*?\"\"\"')` — the SQL in this endpoint lives in
    `text(\"\"\"...\"\"\")` blocks, so a blanket strip removes the queries too and every
    assertion below passes vacuously. The first version of this file did exactly that,
    which would have let the reported bug through untouched.
    """
    m = re.search(r'"""', block)
    if not m:
        return block
    close = block.index('"""', m.end())
    return block[:m.start()] + block[close + 3:]


class SourceTests(unittest.TestCase):
    def testItDoesNotQueryTheDeadTables(self):
        """THE REGRESSION. Both tables hold zero rows, so a join against them returns
        nothing and reports nothing."""
        code = _code(_endpoint())
        self.assertNotIn('fantasy_roster_players', code,
                         'fantasy records are being read from a table nothing writes')
        self.assertNotIn('fantasy_rosters', code)

    def testItReadsTheBankedSnapshot(self):
        code = _code(_endpoint())
        self.assertIn('weekly_card_bonuses', code)
        self.assertIn('breakdowns_json', code)
        self.assertIn('weekly_player_fp', code)

    def testItDoesNotReadTheLiveLineup(self):
        """⚠️ `equipped_cards` is carried forward week to week, so scoring a PAST week
        from it prices that week against today's hand."""
        self.assertNotIn('equipped_cards', _code(_endpoint()))


class AggregationTests(unittest.TestCase):
    """The arithmetic, run against synthetic rows in the shape the queries return."""

    @staticmethod
    def _rollup(bonusRows, fpByPlayerWeek, limit=10):
        """Mirrors the endpoint: per banked week, sum the lineup's FP and add the bonus."""
        weekly, seasonAcc = [], {}
        for r in bonusRows:
            try:
                breakdowns = json.loads(r['breakdowns_json'] or '[]')
            except (ValueError, TypeError):
                breakdowns = []
            playerIds = [b.get('playerId') for b in breakdowns if b.get('playerId')]
            if not playerIds:
                continue
            playerFp = sum(fpByPlayerWeek.get((pid, r['season'], r['week']), 0.0)
                           for pid in set(playerIds))
            total = playerFp + float(r['bonus_fp'] or 0)
            weekly.append((r['user_id'], r['season'], r['week'], total))
            key = (r['user_id'], r['season'])
            seasonAcc[key] = seasonAcc.get(key, 0.0) + total
        weekly.sort(key=lambda t: t[3], reverse=True)
        season = sorted(((u, s, v) for (u, s), v in seasonAcc.items()),
                        key=lambda t: t[2], reverse=True)
        return weekly[:limit], season[:limit]

    def testAWeekSumsItsLineupPlusTheCardBonus(self):
        rows = [{'user_id': 1, 'season': 1, 'week': 3, 'bonus_fp': 12.0,
                 'breakdowns_json': json.dumps([{'playerId': 10}, {'playerId': 11}])}]
        fp = {(10, 1, 3): 20.0, (11, 1, 3): 30.0}
        weekly, _ = self._rollup(rows, fp)
        self.assertEqual(weekly[0][3], 62.0, '20 + 30 players, + 12 card bonus')

    def testADuplicatedPlayerIsCountedOnce(self):
        """A breakdown can name the same player in two slots (FLEX). Their week's FP is
        one number, not two."""
        rows = [{'user_id': 1, 'season': 1, 'week': 3, 'bonus_fp': 0.0,
                 'breakdowns_json': json.dumps([{'playerId': 10}, {'playerId': 10}])}]
        weekly, _ = self._rollup(rows, {(10, 1, 3): 25.0})
        self.assertEqual(weekly[0][3], 25.0)

    def testALegacyRowWithNoBreakdownIsSkippedNotScoredZero(self):
        """⚠️ A row with no breakdown predates snapshot storage. Recording it as 0 would
        read as a user who fielded a team and scored nothing."""
        rows = [{'user_id': 1, 'season': 1, 'week': 3, 'bonus_fp': 5.0,
                 'breakdowns_json': None}]
        weekly, season = self._rollup(rows, {})
        self.assertEqual(weekly, [])
        self.assertEqual(season, [])

    def testSeasonTotalsSumTheWeeks(self):
        rows = [
            {'user_id': 1, 'season': 1, 'week': 1, 'bonus_fp': 0.0,
             'breakdowns_json': json.dumps([{'playerId': 10}])},
            {'user_id': 1, 'season': 1, 'week': 2, 'bonus_fp': 0.0,
             'breakdowns_json': json.dumps([{'playerId': 10}])},
        ]
        fp = {(10, 1, 1): 10.0, (10, 1, 2): 15.0}
        _, season = self._rollup(rows, fp)
        self.assertEqual(season[0][2], 25.0)

    def testTheBestWeekLeadsAndTotalsAreRanked(self):
        rows = [
            {'user_id': 1, 'season': 1, 'week': 1, 'bonus_fp': 0.0,
             'breakdowns_json': json.dumps([{'playerId': 10}])},
            {'user_id': 2, 'season': 1, 'week': 1, 'bonus_fp': 0.0,
             'breakdowns_json': json.dumps([{'playerId': 11}])},
        ]
        fp = {(10, 1, 1): 40.0, (11, 1, 1): 90.0}
        weekly, _ = self._rollup(rows, fp)
        self.assertEqual(weekly[0][0], 2, 'the bigger week ranks first')
        self.assertEqual(weekly[0][3], 90.0)

    def testMalformedJsonDoesNotRaise(self):
        rows = [{'user_id': 1, 'season': 1, 'week': 3, 'bonus_fp': 1.0,
                 'breakdowns_json': '{not json'}]
        weekly, season = self._rollup(rows, {})
        self.assertEqual((weekly, season), ([], []))


if __name__ == '__main__':
    unittest.main(verbosity=2)
