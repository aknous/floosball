"""The stats page's status chips and its rows must agree.

⚠️ THE CHIP SAID 56 AND THE FOOTER SAID 41. Reported from the live page: the Free Agent
chip counted 56 players and the table showed "Showing 41 of 41"; filtered to QB the chip
said 4 and one player appeared.

Both numbers derive from the same `candidates` list and the same `_playerStatus`, so they
agree BY CONSTRUCTION at selection time — the divergence could only be in how rows were
built afterwards. It was: the database branch looped over `PlayerSeasonStats` rows and
intersected them with the selection, so anyone with no row for the season, or one with
`games_played == 0` (filtered out by the query), vanished from the page while still being
counted in the chip.

⚠️ FREE AGENTS ARE THE POPULATION WITH NO STAT ROW, which is why this reads as a
free-agent bug rather than a stats bug — an unsigned free agent played no games, so there
is nothing in the table for them. Measured on a season-21 database: 29 teamless
non-retired players, **0** with a qualifying stat row.

⚠️ And it only shows in the DATABASE branch. The live branch loops the selection directly
and emits a row for everyone, empty stats included — so the page is correct mid-season and
wrong all through the offseason, which is when it was reported.

⚠️ THESE ARE STRUCTURAL ASSERTIONS, NOT BEHAVIORAL ONES, and that is a compromise rather
than a preference. `GET /api/stats/players` reads `floosball_app`'s live PlayerManager
pools, so exercising it needs a booted simulation; there is no cheap seam. What is pinned
instead is the SHAPE that caused the bug — which collection each branch loops.

Stated because this file would otherwise flatter itself: a source-text assertion fails on
an innocent rename and passes on a behavioral regression that keeps the same words. It is
the best guard available here, not a good one. If a seam ever appears — the row builder
extracted from the endpoint, say — replace this wholesale with a real call.

Run: .venv/bin/python test_stats_facets.py
"""
import io
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

SRC = io.open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'api', 'main.py'),
              encoding='utf-8').read()


def _statsPlayersBody() -> str:
    """The body of GET /api/stats/players."""
    start = SRC.index('@app.get("/api/stats/players"')
    end = SRC.index('@app.', start + 10)
    return SRC[start:end]


class TheChipAndTheTableCountTheSamePeople(unittest.TestCase):

    def testRowsAreBuiltFromTheSELECTIONNotFromStatRows(self):
        """⚠️ THE FIX, AND THE ONE THING THAT MUST NOT REGRESS. Looping the stat rows
        silently drops every selected player who has none."""
        body = _statsPlayersBody()
        self.assertNotIn(
            'for playerId, statRows in bySeasonRows.items():', body,
            'the database branch is looping stat rows again — players without a row '
            'will be counted in the chip and missing from the table')
        self.assertIn('for p in selected:', body,
                      'the database branch must iterate the selection')

    def testAPlayerWithNoStatRowStillGetsARow(self):
        """The empty line is the honest rendering of someone who did not play, and it is
        what the live branch has always produced."""
        body = _statsPlayersBody()
        self.assertIn('statRows = bySeasonRows.get(p.id) or []', body)
        self.assertIn('if not statRows:', body,
                      'no empty-stats branch — a player without stats has nowhere to go')

    def testBothBranchesLoopTheSameCollection(self):
        """⚠️ The live branch was always right; the database branch was the odd one. If
        they ever loop different things again, they can disagree again."""
        body = _statsPlayersBody()
        self.assertEqual(
            body.count('for p in selected:'), 2,
            'the live branch and the database branch should both iterate `selected`')

    def testFacetsAreCountedFromTheSameCandidatesAsSelection(self):
        """The two numbers have to share a source, or agreement is a coincidence."""
        body = _statsPlayersBody()
        self.assertIn('for p in candidates:', body, 'facets must count `candidates`')
        self.assertIn('selected = [p for p in candidates', body,
                      'selection must filter the same `candidates`')

    def testTheGamesPlayedFilterStaysOnAGGREGATIONOnly(self):
        """⚠️ `games_played > 0` is right for SUMMING and wrong for INCLUSION. Keeping it
        on the query is fine — a zero-game row adds nothing — as long as absence from the
        query no longer removes the player."""
        body = _statsPlayersBody()
        self.assertIn('_PSS.games_played > 0', body,
                      'the aggregation filter should still be there')
        idx = body.index('_PSS.games_played > 0')
        after = body[idx:]
        self.assertLess(after.index('for p in selected:'), after.index('rows.append'),
                        'the selection loop must come between the query and the rows')


if __name__ == '__main__':
    unittest.main(verbosity=2)
