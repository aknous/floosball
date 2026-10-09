"""The offseason board has a Prospects board (the draft class) and a Free Agents board.

Reported: the free-agent list in the offseason showed players tagged "New", read as
prospects. They were free agents: on production all 19 were season-6 draftees whose
three-season prospect window had run out without a promotion, released into the pool
(`_advanceProspectWindow` resets `seasonsPlayed` to 0). The tag (`isNewcomer`, "never
played a pro season") dated from when the rookie draft was excised and the pool was the
only way into the league; with the draft back it mislabeled released prospects. Owner
(2026-10-09): drop the tag, and give the draft class its own board.

`_offseasonDraftClass` serves the class at every phase in GET /api/offseason `rookies`,
with the team that took each player. ⚠️ The draft CLEARS `is_upcoming_rookie`, so the
picks are read from this season's `rookie_pick` recap events (durable across a restart).

Run: .venv/bin/python -m pytest -q test_offseason_prospects_board.py
"""
import os
import sys
import tempfile
import types

HERE = os.path.dirname(os.path.abspath(__file__))
_TMP = tempfile.mkdtemp(prefix='floo_prospects_board_')
os.environ['DATABASE_DIR'] = _TMP
sys.path.insert(0, HERE)
import logging
logging.disable(logging.CRITICAL)

import pytest

from database.connection import init_db, get_session
from database.models import SeasonRecapEvent

init_db()
import api.main as apiMain  # noqa: E402


def _player(pid, name, rating=80, **flags):
    p = types.SimpleNamespace(id=pid, name=name, playerRating=rating,
                              position=types.SimpleNamespace(name='WR'),
                              playerTier=types.SimpleNamespace(name='TierB'),
                              seasonsPlayed=0, prospect_seasons=0,
                              is_upcoming_rookie=False, is_undrafted=False)
    for k, v in flags.items():
        setattr(p, k, v)
    return p


@pytest.fixture
def app(monkeypatch):
    season = 9
    players = [
        _player(1, 'Still Waiting', rating=84, is_upcoming_rookie=True),
        _player(2, 'Taken First', rating=90),                       # drafted (recap)
        _player(3, 'Nobody Took', rating=70, is_undrafted=True),     # undrafted this year
        _player(4, 'Old Undrafted', rating=72, is_undrafted=True, seasonsPlayed=2),
        _player(5, 'Released Prospect', rating=90, prospect_seasons=3),
        _player(6, 'Veteran', rating=88, seasonsPlayed=6),
    ]
    session = get_session()
    session.query(SeasonRecapEvent).delete()
    session.add(SeasonRecapEvent(season=season, event_type='rookie_pick', player_id=2,
                                 team_abbr='NYS', player_name='Taken First'))
    session.add(SeasonRecapEvent(season=season - 3, event_type='rookie_pick', player_id=5,
                                 team_abbr='PHI', player_name='Released Prospect'))
    session.commit()
    session.close()
    fake = types.SimpleNamespace(
        seasonManager=types.SimpleNamespace(currentSeason=types.SimpleNamespace(seasonNumber=season)),
        playerManager=types.SimpleNamespace(activePlayers=players))
    monkeypatch.setattr(apiMain, 'floosball_app', fake)
    return fake


def test_theClassIsWhoIsLeftWhoWasTakenAndWhoWasNot(app):
    board = {e['name']: e for e in apiMain._offseasonDraftClass()}
    assert set(board) == {'Still Waiting', 'Taken First', 'Nobody Took'}
    assert board['Taken First']['draftedBy'] == 'NYS'
    assert board['Still Waiting']['draftedBy'] is None and not board['Still Waiting']['undrafted']
    assert board['Nobody Took']['undrafted'] is True


def test_aReleasedProspectIsNotInThisClass(app):
    """The players behind the report: drafted three seasons ago, released this offseason.
    They are free agents, not this year's prospects."""
    names = {e['name'] for e in apiMain._offseasonDraftClass()}
    assert 'Released Prospect' not in names
    assert 'Old Undrafted' not in names


def test_bestFirst(app):
    ratings = [e['rating'] for e in apiMain._offseasonDraftClass()]
    assert ratings == sorted(ratings, reverse=True)


def test_noFreeAgentListCarriesTheNewcomerTag():
    for rel in ('api/main.py', 'managers/playerManager.py'):
        with open(os.path.join(HERE, rel)) as f:
            assert 'isNewcomer' not in f.read(), rel
