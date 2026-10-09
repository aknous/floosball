"""The offseason board's transactions show the real re-signings, and label every move.

Reported (season 9): the board showed a block of "SIGN" entries that were really
prospects released when their window ran out, and no re-signings at all.

Two causes. (1) `_runPreDraftPass` listed a team's re-signings from fan-vote results
(`resign_player`), which only the deleted binding-vote system produced, so every team
read zero; production had 28 `resign` recap rows that season. The same source decided
cut vs. expired, so every front-office cut read as an expired contract. Both now come
from the recap log (`SeasonManager.frontOfficeMovesByTeam`), and `/api/offseason`
re-reads it on every request (`_withFrontOfficeMoves`), since the transaction list lives
in memory and an offseason that ran under the old code holds empty lists. (2) The
frontend labeled any type it did not know as a signing; `prospect_release` and
`prospect_release` now has its own label and carries its team abbr. The pool cull is
not shown at all (owner: its names go back into the name pool).

Run: .venv/bin/python -m pytest -q test_offseason_transactions.py
"""
import os
import sys
import tempfile
import types

HERE = os.path.dirname(os.path.abspath(__file__))
os.environ['DATABASE_DIR'] = tempfile.mkdtemp(prefix='floo_offseason_tx_')
sys.path.insert(0, HERE)
import logging
logging.disable(logging.CRITICAL)

import pytest

from database.connection import init_db, get_session
from database.models import SeasonRecapEvent

init_db()
import api.main as apiMain  # noqa: E402
from managers.seasonManager import SeasonManager  # noqa: E402

SEASON = 9


def _event(eventType, playerId, name, teamId=4, abbr='NYS', team='Strangers', **kw):
    return SeasonRecapEvent(season=SEASON, event_type=eventType, team_id=teamId, team_abbr=abbr,
                            team_name=team, player_id=playerId, player_name=name, position='WR',
                            rating=80, tier='TierB', **kw)


@pytest.fixture
def sm(monkeypatch):
    session = get_session()
    session.query(SeasonRecapEvent).delete()
    session.add_all([
        _event('resign', 1, 'Kept Him'),
        _event('walked', 2, 'Contract Ran Out'),
        _event('cut', 3, 'Cut For Upgrade', detail='GM upgrade cut'),
        _event('cut', 4, 'Cut In A Trade', trade_id=77),
        _event('resign', 5, 'Kept Elsewhere', teamId=8, abbr='PHI', team='Pinecones'),
        SeasonRecapEvent(season=SEASON - 1, event_type='resign', team_id=4, team_abbr='NYS',
                         team_name='Strangers', player_id=6, player_name='Last Year'),
    ])
    session.commit()
    session.close()
    stub = types.SimpleNamespace(currentSeason=types.SimpleNamespace(seasonNumber=SEASON))
    stub.frontOfficeMovesByTeam = lambda: SeasonManager.frontOfficeMovesByTeam(stub)
    teams = [types.SimpleNamespace(name='Strangers', abbr='NYS'),
             types.SimpleNamespace(name='Pinecones', abbr='PHI')]
    monkeypatch.setattr(apiMain, 'floosball_app',
                        types.SimpleNamespace(teamManager=types.SimpleNamespace(teams=teams)))
    return stub


def test_reSigningsAndDeparturesComeFromTheRecapLog(sm):
    moves = sm.frontOfficeMovesByTeam()
    nys = moves[4]
    assert [p['name'] for p in nys['resigns']] == ['Kept Him']
    reasons = {p['name']: p['reason'] for p in nys['cuts']}
    assert reasons == {'Contract Ran Out': 'expired', 'Cut For Upgrade': 'cut'}
    assert [p['name'] for p in moves[8]['resigns']] == ['Kept Elsewhere']


def test_theBoardFillsAnEmptyTeamSetupFromTheLog(sm):
    """Production season 9: the pre-draft pass ran under the old code and every
    team_setup holds empty lists. The board reads the log instead."""
    stale = [{'type': 'team_setup', 'team': 'Strangers', 'teamAbbr': 'NYS', 'teamId': 4,
              'resigns': [], 'cuts': [], 'promotions': []}]
    out = apiMain._withFrontOfficeMoves(sm, stale)
    nys = next(t for t in out if t.get('teamId') == 4)
    assert [p['name'] for p in nys['resigns']] == ['Kept Him']
    assert {p['reason'] for p in nys['cuts']} == {'expired', 'cut'}
    # A team with moves but no entry (lost to a restart) gets one.
    assert any(t.get('teamId') == 8 and t['resigns'] for t in out)


def test_aReleasedProspectNamesItsTeam(sm):
    out = apiMain._withFrontOfficeMoves(sm, [
        {'type': 'prospect_release', 'team': 'Pinecones', 'teamAbbr': '', 'playerId': 9,
         'player': 'Washed Out', 'position': 'K', 'rating': 90}])
    rel = next(t for t in out if t.get('type') == 'prospect_release')
    assert rel['teamAbbr'] == 'PHI'


def test_thePreDraftPassNoLongerReadsFanVotes():
    with open(os.path.join(HERE, 'managers', 'seasonManager.py')) as f:
        src = f.read()
    body = src.split('    async def _runPreDraftPass(')[1].split('\n    async def ')[0]
    assert "resign_player" not in body
    assert 'frontOfficeMovesByTeam()' in body


def test_thePoolCullIsNeverPublished():
    with open(os.path.join(HERE, 'managers', 'seasonManager.py')) as f:
        assert "'type': 'pool_cull'" not in f.read()
    with open(os.path.join(HERE, 'api', 'main.py')) as f:
        assert "t.get('type') != 'pool_cull'" in f.read()
