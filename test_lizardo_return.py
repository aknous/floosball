"""The one-shot that returns Dearie Lizardo to the Raccoons (owner, 2026-10-17).

Lizardo washed out at season 10's step 3.78 with the Raccoons' TE slot empty, the Broads
signed him, and the Raccoons promoted Melkey Boogums into the slot. At boot,
`connection._returnLizardoToRaccoons` puts Lizardo back on a promoted-prospect contract,
sends Boogums back to the pipeline and signs the Broads the best free-agent TE. It must
move nobody unless prod is still in the state it was written against.

Run: .venv/bin/python -m pytest -q test_lizardo_return.py
"""
import os
import tempfile

os.environ['DATABASE_DIR'] = tempfile.mkdtemp(prefix='floos_lizardo_')

from sqlalchemy import text                                          # noqa: E402
from database import connection                                      # noqa: E402
from database.connection import (init_db, get_session, LIZARDO_ID, BOOGUMS_ID,  # noqa: E402
                                 RACCOONS_ID, BROADS_ID)
from database.models import (Player, PlayerAttributes, AppSetting, SimulationState,  # noqa: E402
                             Game, SeasonRecapEvent)

init_db()

FA_TE, WEAK_FA_TE, FA_WR = 77, 143, 500


def _attrs(pid, longevity):
    from sqlalchemy import Integer, Float
    cols = {}
    for col in PlayerAttributes.__table__.columns:
        if col.primary_key or col.nullable or col.default is not None:
            continue
        cols[col.name] = 80 if isinstance(col.type, (Integer, Float)) else 'neutral'
    cols.update(player_id=pid, longevity=longevity)
    return PlayerAttributes(**cols)


def _reset(season=11, lizardoTeam=BROADS_ID, boogumsTeam=RACCOONS_ID, playedGames=0,
           withFa=True):
    s = get_session()
    s.query(AppSetting).filter(AppSetting.key == 'lizardo_returned_s10').delete()
    for table in ('player_attributes', 'players', 'games', 'simulation_state',
                  'season_recap_events'):
        s.execute(text(f"DELETE FROM {table}"))
    s.add(SimulationState(id=1, current_season=season, current_week=0))
    s.add(Player(id=LIZARDO_ID, name='Dearie Lizardo', team_id=lizardoTeam, position=4,
                 tier='TierA', seasons_played=0, prospect_seasons=3, term=3,
                 term_remaining=3, player_rating=86))
    s.add(Player(id=BOOGUMS_ID, name='Melkey Boogums', team_id=boogumsTeam, position=4,
                 tier='TierD', seasons_played=0, prospect_seasons=2, term=1,
                 term_remaining=1, player_rating=62, on_prospect_contract=1))
    if withFa:
        s.add(Player(id=FA_TE, name='Frangelico Dunebuggy', team_id=None, position=4,
                     tier='TierB', seasons_played=10, term=2, term_remaining=0,
                     player_rating=77, free_agent_years=0, service_time='Veteran4'))
        s.add(_attrs(FA_TE, 12))
        s.add(Player(id=WEAK_FA_TE, name='Killtron Kingsley', team_id=None, position=4,
                     tier='TierC', seasons_played=10, player_rating=69,
                     service_time='Veteran4'))
    s.add(Player(id=FA_WR, name='Better Receiver', team_id=None, position=3, tier='TierA',
                 seasons_played=4, player_rating=88, service_time='Veteran1'))
    s.add(SeasonRecapEvent(season=10, event_type='fa_pick', team_abbr='PHI',
                           player_id=LIZARDO_ID, player_name='Dearie Lizardo'))
    s.add(SeasonRecapEvent(season=10, event_type='promotion', team_id=RACCOONS_ID,
                           team_abbr='TOR', player_id=BOOGUMS_ID, player_name='Melkey Boogums'))
    s.add(SeasonRecapEvent(season=8, event_type='rookie_pick', team_id=RACCOONS_ID,
                           team_abbr='TOR', player_id=BOOGUMS_ID, player_name='Melkey Boogums'))
    for _ in range(playedGames):
        s.add(Game(season=11, week=1, home_team_id=RACCOONS_ID, away_team_id=BROADS_ID,
                   home_score=0, away_score=0, status='final'))
    try:
        s.commit()
    finally:
        s.close()


def _state():
    s = get_session()
    rows = {r[0]: r[1:] for r in s.execute(text(
        "SELECT id, team_id, is_prospect, drafting_team_id, on_prospect_contract, term, "
        "term_remaining FROM players"))}
    events = sorted((r[0], r[1]) for r in s.execute(text(
        "SELECT event_type, player_id FROM season_recap_events")))
    marker = s.execute(text(
        "SELECT value FROM app_settings WHERE key = 'lizardo_returned_s10'")).scalar()
    s.close()
    return rows, events, marker


def test_the_return_moves_all_three_once():
    _reset()
    connection._returnLizardoToRaccoons()
    rows, events, marker = _state()
    lTeam, lProspect, _, lProtected, lTerm, lLeft = rows[LIZARDO_ID]
    assert (lTeam, lProtected, lTerm, lLeft) == (RACCOONS_ID, 1, 3, 3)
    bTeam, bProspect, bDraft, bProtected, *_ = rows[BOOGUMS_ID]
    assert (bTeam, bProspect, bDraft, bProtected) == (None, 1, RACCOONS_ID, 0)
    # The best free-agent TE, not the best free agent and not the weaker TE.
    fTeam, *_, fTerm, fLeft = rows[FA_TE]
    assert fTeam == BROADS_ID and 1 <= fTerm <= 3 and fLeft == fTerm
    assert rows[WEAK_FA_TE][0] is None and rows[FA_WR][0] is None
    # The two rows that no longer happened are gone; history before season 10 stays.
    assert events == [('rookie_pick', BOOGUMS_ID)]
    assert marker.startswith('done')
    # One-shot: a second boot moves nobody.
    s = get_session()
    s.execute(text("UPDATE players SET team_id = :t WHERE id = :p"),
              {'t': BROADS_ID, 'p': LIZARDO_ID})
    s.commit(); s.close()
    connection._returnLizardoToRaccoons()
    assert _state()[0][LIZARDO_ID][0] == BROADS_ID


def test_it_also_runs_before_the_season_counter_moves():
    _reset(season=10)
    connection._returnLizardoToRaccoons()
    assert _state()[0][LIZARDO_ID][0] == RACCOONS_ID


def test_it_moves_nobody_once_the_season_has_started():
    _reset(playedGames=1)
    connection._returnLizardoToRaccoons()
    rows, _, marker = _state()
    assert rows[LIZARDO_ID][0] == BROADS_ID and rows[BOOGUMS_ID][0] == RACCOONS_ID
    assert marker.startswith('skipped')


def test_it_moves_nobody_if_either_player_has_moved():
    _reset(boogumsTeam=None)
    connection._returnLizardoToRaccoons()
    rows, _, marker = _state()
    assert rows[LIZARDO_ID][0] == BROADS_ID and marker.startswith('skipped')


def test_it_moves_nobody_without_a_te_for_the_broads():
    _reset(withFa=False)
    connection._returnLizardoToRaccoons()
    rows, _, marker = _state()
    assert rows[LIZARDO_ID][0] == BROADS_ID and marker.startswith('skipped')


def test_it_moves_nobody_in_another_season():
    _reset(season=12)
    connection._returnLizardoToRaccoons()
    rows, _, marker = _state()
    assert rows[LIZARDO_ID][0] == BROADS_ID and marker.startswith('skipped')
