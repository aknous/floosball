"""Season player stats survive the end of the season.

⚠️ THE SEASON DICT IS WIPED THE MOMENT THE SEASON ENDS. `_handlePlayerSeasonProgression`
archives every `seasonStatsDict` into `seasonStatsArchive` and then RESETS it to the
blank template. The season NUMBER does not advance until the next season starts, so for
the whole offseason every surface reading the live dict served zeros for a season that
had just been played in full. Reported 2026-08-14 as all season player stats being
cleared once the season ended.

Three surfaces, one cause:
  * the stats page took its in-memory branch because `liveSeason` asked "is this the
    current season number" rather than "is it still being played";
  * `/api/stats/leaders` read the live dict;
  * `/api/players` read the live dict.

⚠️ THE STATS PAGE NEEDED NO FALLBACK — `savePlayerData()` runs immediately BEFORE the
reset, so `PlayerSeasonStats` already held the finished season in full and the page just
had to stop taking the memory branch. Only the surfaces with no DB path use the archive.

⚠️ `isLive` is load-bearing, not decoration. Callers add `gameStatsDict` on top for a
mid-game-accurate figure, and against an ARCHIVED row that adds the Floos Bowl's own
numbers to a total the playoffs never fed into. It is why the Top Players panel showed
exactly one row, reading 42: fantasy points alone carried the addend, so it was the only
category that looked alive, and the number was a single game's.

Run: .venv/bin/python test_offseason_stats.py
"""

import os
import re
import sys
import types
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import logging
logging.disable(logging.CRITICAL)

HERE = os.path.dirname(os.path.abspath(__file__))

# The usual circular-import break: register a stub so seasonManager's annotations
# resolve, then let the real module load once `managers` is cached.
if 'floosball_game' not in sys.modules:
    _stub = types.ModuleType('floosball_game')
    class _GameStub: pass
    _stub.Game = _GameStub
    sys.modules['floosball_game'] = _stub
    import managers.timingManager  # noqa: F401
    del sys.modules['floosball_game']

import api.main as apiMain  # noqa: E402


class _Player:
    def __init__(self):
        self.seasonStatsDict = {'passing': {'yards': 0}, 'fantasyPoints': 0}
        self.gameStatsDict = {'fantasyPoints': 42}
        self.seasonStatsArchive = [
            {'season': 1, 'passing': {'yards': 4000}, 'fantasyPoints': 300},
            {'season': 2, 'passing': {'yards': 9026}, 'fantasyPoints': 696},
        ]


class _Season:
    def __init__(self, number, complete):
        self.seasonNumber = number
        self.isComplete = complete


class _App:
    def __init__(self, season):
        self.seasonManager = types.SimpleNamespace(currentSeason=season)


class SeasonStatsForTests(unittest.TestCase):
    def setUp(self):
        self._saved = apiMain.floosball_app

    def tearDown(self):
        apiMain.floosball_app = self._saved

    def testDuringASeasonItIsLive(self):
        apiMain.floosball_app = _App(_Season(2, complete=False))
        sd, isLive = apiMain._seasonStatsFor(_Player())
        self.assertTrue(isLive)
        self.assertEqual(sd['passing']['yards'], 0, 'should be the live dict, blank or not')

    def testOnceCompleteItServesTheArchivedSeason(self):
        """The reported bug."""
        apiMain.floosball_app = _App(_Season(2, complete=True))
        sd, isLive = apiMain._seasonStatsFor(_Player())
        self.assertFalse(isLive)
        self.assertEqual(sd['passing']['yards'], 9026)

    def testItMatchesTheSeasonRatherThanTakingTheLastRow(self):
        """⚠️ A player who missed the year must not serve an older season as if it were
        this one — taking `archive[-1]` would do exactly that."""
        apiMain.floosball_app = _App(_Season(3, complete=True))
        player = _Player()   # archive holds seasons 1 and 2 only
        sd, isLive = apiMain._seasonStatsFor(player)
        self.assertTrue(isLive, 'no row for season 3 — fall back to live, not to season 2')
        self.assertIsNot(sd, player.seasonStatsArchive[-1])

    def testAnEmptyArchiveIsNotAnError(self):
        apiMain.floosball_app = _App(_Season(2, complete=True))
        player = _Player()
        player.seasonStatsArchive = []
        sd, isLive = apiMain._seasonStatsFor(player)
        self.assertTrue(isLive)

    def testNoAppDoesNotRaise(self):
        apiMain.floosball_app = None
        sd, isLive = apiMain._seasonStatsFor(_Player())
        self.assertTrue(isLive)


def _source() -> str:
    with open(os.path.join(HERE, 'api', 'main.py')) as fh:
        return fh.read()


class CallSiteTests(unittest.TestCase):
    """The rules that live at the call sites rather than in the helper."""

    def testTheStatsPageStopsBeingLiveWhenTheSeasonIsComplete(self):
        """⚠️ It reads the DB once it is not live, and the DB has the season in full."""
        src = _source()
        start = src.index('liveSeason = (')
        line = src[start:src.index('\n', start)]
        self.assertIn('_smComplete', line,
                      'liveSeason is back to meaning "the current season NUMBER"')

    def testTheLeadersEntryUsesTheSameSourceAsTheSort(self):
        """⚠️ THIS IS THE REGRESSION THAT ALREADY HAPPENED ONCE. An earlier pass fixed
        `extractStat` and left the response entry reading the live dict, which sorted the
        board correctly and printed every number on it as 0 — the worse of the two
        failures, because a wrong order looks wrong and a wrong value looks
        authoritative."""
        src = _source()
        start = src.index('def get_stat_leaders')
        # ⚠️ Bound at the next TOP-LEVEL def, not the next @app. — the helpers between
        # this endpoint and the next route include `_seasonStatsFor`, which legitimately
        # names the live dict, and a wider slice reports it as the bug.
        end = min(i for i in (src.find('\n@app.', start), src.find('\ndef ', start)) if i != -1)
        body = src[start:end]
        stripped = '\n'.join(re.sub(r'#.*$', '', ln) for ln in body.split('\n'))
        self.assertNotIn('player.seasonStatsDict', stripped,
                         'the leaders endpoint is reading the live dict again')

    def testTheInGameAddendIsGatedOnIsLive(self):
        """Adding `gameStatsDict` to an ARCHIVED row credits the Floos Bowl's points to a
        season total the playoffs never fed into."""
        src = _source()
        for marker in ('if isLive else 0', 'if _sdLive else 0'):
            self.assertIn(marker, src, 'an in-game addend lost its isLive gate')

    def testThePlayersListUsesTheHelper(self):
        src = _source()
        start = src.index('# Merge season + in-game stats for live accuracy')
        block = src[start:start + 400]
        self.assertIn('_seasonStatsFor(player)', block)
        self.assertIn('if sdLive else {}', block)


if __name__ == '__main__':
    unittest.main(verbosity=2)
