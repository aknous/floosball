"""Undoing an owner-directed re-sign, and the re-sign block surviving a restart.

Season 8: the Strangers re-signed Bolt Newtonian (74 QB) for three seasons while holding
the #1 pick with two top QB prospects in the class. The owner asked for the re-sign to be
undone rather than cut (a fee for a contract signed hours earlier). And `previousTeam`,
which stops a team re-signing a player it just let go in the FA draft, was never saved, so
every offseason restart lifted that block.

Run: .venv/bin/python -m pytest -q test_release_resigned.py
"""
import json
import os
import tempfile
import types

os.environ['DATABASE_DIR'] = tempfile.mkdtemp(prefix='floos_release_')

from sqlalchemy import text                                    # noqa: E402
from database import connection                                # noqa: E402
from database.connection import init_db, get_session           # noqa: E402

init_db()


RECAP = ("INSERT INTO season_recap_events (season, event_type, team_name, player_id, detail, "
         "sort_order, created_at) VALUES (8, :t, :n, :p, :d, 0, CURRENT_TIMESTAMP)")


def _seed(teamId=1, termRemaining=3, steps=('frontoffice_decisions',), season=8):
    s = get_session()
    s.execute(text("DELETE FROM players")); s.execute(text("DELETE FROM season_recap_events"))
    s.execute(text("DELETE FROM simulation_state")); s.execute(text("DELETE FROM app_settings WHERE key LIKE 'undo_%'"))
    s.execute(text("INSERT INTO players (id, name, position, team_id, term, term_remaining, team_resign_count, "
                   "free_agent_years, seasons_played, is_prospect, is_undrafted, prospect_seasons, "
                   "on_prospect_contract, is_upcoming_rookie, will_retire, is_hof, created_at, updated_at) "
                   "VALUES (209, 'Bolt Newtonian', 1, :t, 3, :tr, 2, 0, 5, 0, 0, 0, 0, 0, 0, 0, "
                   "CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"), {'t': teamId, 'tr': termRemaining})
    s.execute(text(RECAP), {'t': 'resign', 'n': 'Strangers', 'p': 209, 'd': '3 season(s)'})
    s.execute(text("INSERT INTO simulation_state (id, current_season, current_week, in_playoffs, in_offseason, "
                   "total_seasons, is_active, last_saved, created_at, offseason_completed_steps) "
                   "VALUES (1, :s, 32, 0, 1, 8, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, :st)"),
              {'s': season, 'st': json.dumps(list(steps))})
    s.commit(); s.close()


def _state():
    s = get_session()
    p = s.execute(text("SELECT team_id, term_remaining, team_resign_count FROM players WHERE id=209")).fetchone()
    e = s.execute(text("SELECT event_type FROM season_recap_events WHERE player_id=209")).fetchone()
    s.close()
    return tuple(p), e[0]


def _run():
    connection._releaseResignedPlayer('undo_resign_bolt_newtonian_s8', playerId=209,
                                      name='Bolt Newtonian', teamId=1, season=8)


def test_the_resign_is_undone_once():
    _seed()
    _run()
    assert _state() == ((None, 0, 0), 'walked')
    s = get_session()
    s.execute(text("UPDATE players SET team_id = 5 WHERE id = 209")); s.commit(); s.close()
    _run()                                       # marker set: never runs again
    assert _state()[0][0] == 5


def test_it_leaves_a_changed_state_alone():
    _seed(steps=('frontoffice_decisions', 'fa_draft'))       # the FA draft has run
    _run()
    assert _state() == ((1, 3, 2), 'resign')


def test_previous_team_is_restored_for_this_offseasons_departures():
    import managers.playerManager as PM
    s = get_session()
    s.execute(text("DELETE FROM season_recap_events"))
    s.execute(text(RECAP), {'t': 'walked', 'n': 'Strangers', 'p': 1, 'd': None})
    s.execute(text(RECAP), {'t': 'cut', 'n': 'Phones', 'p': 2, 'd': None})
    s.commit(); s.close()
    pm = PM.PlayerManager.__new__(PM.PlayerManager)
    pm.db_session = get_session()
    walked = types.SimpleNamespace(id=1, freeAgentYears=0, previousTeam=None)
    cut = types.SimpleNamespace(id=2, freeAgentYears=0, previousTeam=None)
    veteranFa = types.SimpleNamespace(id=3, freeAgentYears=2, previousTeam=None)
    pm.freeAgents = [walked, cut, veteranFa]
    pm.restorePreviousTeams(8)
    assert walked.previousTeam == 'Strangers' and cut.previousTeam == 'Phones'
    assert veteranFa.previousTeam is None


if __name__ == '__main__':
    import sys, pytest
    sys.exit(pytest.main(['-q', __file__]))
