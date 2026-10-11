"""The one-shot that returns Gibson Gnegy to the Midnights (owner, 2026-10-10).

Gnegy's last promotion chance priced him against Dingers Culpepper on rating alone; he
washed out and the Tuesdays signed him. `connection._returnGnegyToMidnights` swaps the two
at boot: Gnegy to the Midnights on a promoted-prospect contract, Dingers to the Tuesdays
on the sim's normal term. It must move nobody unless prod is still in the state it was
written against.

Run: .venv/bin/python -m pytest -q test_gnegy_swap.py
"""
import os
import tempfile

os.environ['DATABASE_DIR'] = tempfile.mkdtemp(prefix='floos_gnegy_')

from sqlalchemy import text                                          # noqa: E402
from database import connection                                      # noqa: E402
from database.connection import (init_db, get_session, GNEGY_ID, DINGERS_ID,  # noqa: E402
                                 MIDNIGHTS_ID, TUESDAYS_ID)
from database.models import Player, PlayerAttributes, AppSetting, SimulationState, Game  # noqa: E402

init_db()


def _attrs(pid, longevity):
    """A PlayerAttributes row with every required column at a neutral value."""
    from sqlalchemy import Integer, Float
    cols = {}
    for col in PlayerAttributes.__table__.columns:
        if col.primary_key or col.nullable or col.default is not None:
            continue
        cols[col.name] = 80 if isinstance(col.type, (Integer, Float)) else 'neutral'
    cols.update(player_id=pid, longevity=longevity)
    return PlayerAttributes(**cols)


def _reset(season=10, gnegyTeam=TUESDAYS_ID, dingersTeam=MIDNIGHTS_ID, playedGames=0):
    s = get_session()
    s.query(AppSetting).filter(AppSetting.key == 'gnegy_returned_s10').delete()
    s.execute(text("DELETE FROM player_attributes"))
    s.execute(text("DELETE FROM players"))
    s.execute(text("DELETE FROM games"))
    s.execute(text("DELETE FROM simulation_state"))
    s.add(SimulationState(id=1, current_season=season, current_week=0))
    s.add(Player(id=GNEGY_ID, name='Gibson Gnegy', team_id=gnegyTeam, position=2, tier='TierB',
                 seasons_played=0, prospect_seasons=3, term=2, term_remaining=2,
                 player_rating=82))
    s.add(Player(id=DINGERS_ID, name='Dingers Culpepper', team_id=dingersTeam, position=2,
                 tier='TierB', seasons_played=10, term=3, term_remaining=1, team_resign_count=2,
                 player_rating=82))
    s.add(_attrs(DINGERS_ID, 12))
    s.add(_attrs(GNEGY_ID, 9))
    for i in range(playedGames):
        s.add(Game(season=10, week=1, home_team_id=MIDNIGHTS_ID, away_team_id=TUESDAYS_ID,
                   home_score=0, away_score=0, status='final'))
    try:
        s.commit()
    finally:
        s.close()


def _players():
    s = get_session()
    rows = {r[0]: r[1:] for r in s.execute(text(
        "SELECT id, team_id, term, term_remaining, on_prospect_contract, team_resign_count "
        "FROM players"))}
    marker = s.execute(text(
        "SELECT value FROM app_settings WHERE key = 'gnegy_returned_s10'")).scalar()
    s.close()
    return rows, marker


def test_the_swap_moves_both_players_once():
    _reset()
    connection._returnGnegyToMidnights()
    rows, marker = _players()
    gTeam, gTerm, gLeft, gProtected, _ = rows[GNEGY_ID]
    dTeam, dTerm, dLeft, _, dResigns = rows[DINGERS_ID]
    assert (gTeam, gTerm, gLeft, gProtected) == (MIDNIGHTS_ID, 2, 2, 1)
    # Sim's normal term for a 10-season TierB with longevity 12: 1 to 3, a fresh deal.
    assert dTeam == TUESDAYS_ID and 1 <= dTerm <= 3 and dLeft == dTerm and dResigns == 0
    assert marker.startswith('done')
    # One-shot: a second boot moves nobody, even if someone moved them back.
    s = get_session()
    s.execute(text("UPDATE players SET team_id = :t WHERE id = :p"),
              {'t': TUESDAYS_ID, 'p': GNEGY_ID})
    s.commit(); s.close()
    connection._returnGnegyToMidnights()
    assert _players()[0][GNEGY_ID][0] == TUESDAYS_ID


def test_it_moves_nobody_once_the_season_has_started():
    _reset(playedGames=1)
    connection._returnGnegyToMidnights()
    rows, marker = _players()
    assert rows[GNEGY_ID][0] == TUESDAYS_ID and rows[DINGERS_ID][0] == MIDNIGHTS_ID
    assert marker.startswith('skipped')


def test_it_moves_nobody_if_either_player_has_moved():
    _reset(dingersTeam=None)
    connection._returnGnegyToMidnights()
    rows, marker = _players()
    assert rows[GNEGY_ID][0] == TUESDAYS_ID and marker.startswith('skipped')


def test_it_moves_nobody_in_another_season():
    _reset(season=11)
    connection._returnGnegyToMidnights()
    rows, marker = _players()
    assert rows[GNEGY_ID][0] == TUESDAYS_ID and marker.startswith('skipped')
