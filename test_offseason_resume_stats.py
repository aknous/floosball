"""An offseason restart keeps the finished season's player stats readable.

Prod, season 8 offseason: after a deploy the stats leaders showed every player at 0. The
season-end step archives each player's season into `seasonStatsArchive` (in memory) and
resets the live dict; the restart emptied the archive and `api.main._seasonStatsFor` fell
back to the blank dict. `restoreForOffseasonResume` now rebuilds the entry from
`PlayerSeasonStats` (and reloads team season records, the 0-0 standings half).

Run: .venv/bin/python -m pytest -q test_offseason_resume_stats.py
"""
import os
import tempfile
import types

os.environ['DATABASE_DIR'] = tempfile.mkdtemp(prefix='floos_offres_')

import managers.playerManager as PM                     # noqa: E402
from database.connection import init_db, get_session    # noqa: E402
from database.models import PlayerSeasonStats           # noqa: E402

init_db()


def _manager(players):
    pm = PM.PlayerManager.__new__(PM.PlayerManager)
    pm.activePlayers = players
    pm.db_session = get_session()
    return pm


def test_the_finished_season_is_archived_again_and_the_live_dict_left_blank():
    s = get_session()
    s.add(PlayerSeasonStats(player_id=7, season=8, games_played=28, fantasy_points=301,
                            passing_stats={'yards': 4100, 'tds': 30}))
    s.commit(); s.close()
    team = types.SimpleNamespace(name='Raccoons', color='#123456')
    blank = {'gamesPlayed': 0}
    p = types.SimpleNamespace(id=7, team=team, seasonStatsArchive=[{'season': 7}],
                              seasonStatsDict=blank)
    other = types.SimpleNamespace(id=8, team='Free Agent', seasonStatsArchive=[], seasonStatsDict={})
    pm = _manager([p, other])
    pm.restoreArchivedSeasonStats(8)
    pm.restoreArchivedSeasonStats(8)                      # idempotent
    entries = [a for a in p.seasonStatsArchive if a.get('season') == 8]
    assert len(entries) == 1
    e = entries[0]
    assert e['passing']['yards'] == 4100 and e['fantasyPoints'] == 301 and e['gp'] == 28
    assert e['team'] == 'Raccoons'
    assert p.seasonStatsDict is blank, "the live dict was overwritten"
    assert other.seasonStatsArchive == [], "a player with no row got an entry"


def test_the_offseason_resume_calls_both_restores():
    src = open(os.path.join(os.path.dirname(__file__), 'managers', 'seasonManager.py')).read()
    body = src[src.index('async def restoreForOffseasonResume'):]
    body = body[:body.index('\n    def ')]
    assert 'loadSeasonTeamStats(seasonNumber)' in body
    assert 'restoreArchivedSeasonStats(seasonNumber)' in body


if __name__ == '__main__':
    import sys, pytest
    sys.exit(pytest.main(['-q', __file__]))
