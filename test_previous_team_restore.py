"""`previousTeam` survives an offseason restart.

It stops a team re-signing a player it just cut or let walk in the FA draft, and it was
never saved, so every offseason restart lifted that block. The resume restores it from
this season's walked/cut recap rows.

Run: .venv/bin/python -m pytest -q test_previous_team_restore.py
"""
import os
import tempfile
import types

os.environ['DATABASE_DIR'] = tempfile.mkdtemp(prefix='floos_release_')

from sqlalchemy import text                                    # noqa: E402
from database.connection import init_db, get_session           # noqa: E402

init_db()

RECAP = ("INSERT INTO season_recap_events (season, event_type, team_name, player_id, detail, "
         "sort_order, created_at) VALUES (8, :t, :n, :p, :d, 0, CURRENT_TIMESTAMP)")


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
