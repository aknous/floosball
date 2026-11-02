"""Draft info on the profile, the draft class on the stats page, and the Transactions page
open all season (owner, 2026-11-02).

Run: .venv/bin/python -m pytest -q test_draft_info_and_class.py
"""
import os
import sys
import tempfile
from types import SimpleNamespace

HERE = os.path.dirname(os.path.abspath(__file__))
os.environ['DATABASE_DIR'] = tempfile.mkdtemp(prefix='floo_draftinfo_')
sys.path.insert(0, HERE)
import logging
logging.disable(logging.CRITICAL)

from database.connection import init_db, get_session
from database.models import SeasonRecapEvent

init_db()
import api.main as api  # noqa: E402


def _setup():
    s = get_session()
    for i, (pid, team) in enumerate([(101, 5), (102, 7), (103, 5)]):
        s.add(SeasonRecapEvent(season=10, event_type='rookie_pick', team_id=team,
                               team_abbr=f"T{team}", team_name=f"Team {team}", player_id=pid))
    s.commit()
    s.close()
    teams = [SimpleNamespace(id=5, name='Waffles', city='Stl', abbr='STL', color='#111'),
             SimpleNamespace(id=7, name='Raccoons', city='Ral', abbr='RAL', color='#222')]
    api.floosball_app = SimpleNamespace(
        teamManager=SimpleNamespace(teams=teams),
        seasonManager=SimpleNamespace(currentSeason=SimpleNamespace(seasonNumber=13)))


_setup()


def test_aDraftedPlayerShowsTeamSeasonAndPick():
    info = api._draftInfo(SimpleNamespace(id=103))
    assert info['status'] == 'drafted'
    assert (info['season'], info['pick'], info['teamId'], info['teamName']) == (10, 3, 5, 'Waffles')


def test_theIncomingClassAndTheUndraftedAndTheFounders():
    assert api._draftInfo(SimpleNamespace(id=900, is_upcoming_rookie=True)) == {'status': 'class', 'season': 13}
    assert api._draftInfo(SimpleNamespace(id=901, is_undrafted=True)) == {'status': 'undrafted'}
    assert api._draftInfo(SimpleNamespace(id=902)) is None


def test_theDraftClassIsNotAFreeAgent():
    rookie = SimpleNamespace(is_upcoming_rookie=True, is_prospect=False, team='Upcoming Rookie')
    fa = SimpleNamespace(is_upcoming_rookie=False, is_prospect=False, team='Free Agent')
    assert api._playerStatus(rookie, None) == 'class'
    assert api._playerStatus(fa, None) == 'fa'
    assert 'class' in api._PLAYER_STATUSES


def test_theTransactionsPageIsOpenAllSeason():
    assert api._transactionsAvailable(SimpleNamespace(currentWeek=1, isComplete=False)) is True
    assert api._transactionsAvailable(None) is False
