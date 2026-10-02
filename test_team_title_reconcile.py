"""A title in the championships table is never missing from the team row.

Prod, season 8 offseason: the team rows' title lists were written only when the whole
offseason finished, while the championships table is written the moment the Floos Bowl
ends. A restart in between reloaded season 7's lists, so all 13 season-8 titles were on the
table and on no team row (the Raccoons' Floos Bowl among them). `top_seeds` also lost every
season's entry to a load bug. `connection._reconcileTeamTitles` repairs both on every boot.

Run: .venv/bin/python -m pytest -q test_team_title_reconcile.py
"""
import json
import os
import tempfile

os.environ['DATABASE_DIR'] = tempfile.mkdtemp(prefix='floos_titles_')

from sqlalchemy import text                                          # noqa: E402
from database import connection                                      # noqa: E402
from database.connection import init_db, get_session                 # noqa: E402
from database.models import Team, Championship                       # noqa: E402

init_db()


def _team(s, tid, name, **cols):
    s.add(Team(id=tid, name=name, city='C', abbr=name[:3].upper(), color='#000000', division='Twill',
                 offense_rating=80, defense_rating=80, overall_rating=80, **cols))


def test_missing_titles_are_restored_and_existing_ones_kept():
    s = get_session()
    _team(s, 1, 'Raccoons', floosbowl_championships=[], league_championships=[],
          division_titles=['Season 2'], top_seeds=[])
    _team(s, 2, 'Midnights', floosbowl_championships=['Season 7'], league_championships=['Season 7'],
          division_titles=[], top_seeds=[])
    s.add_all([Championship(team_id=1, season=8, championship_type=k)
               for k in ('floosbowl', 'league', 'division', 'regular_season')])
    s.add(Championship(team_id=2, season=7, championship_type='floosbowl'))
    s.commit(); s.close()

    connection._reconcileTeamTitles()
    connection._reconcileTeamTitles()                      # idempotent

    s = get_session()
    r = {row[0]: row[1:] for row in s.execute(text(
        'SELECT id, floosbowl_championships, league_championships, division_titles, top_seeds FROM teams'))}
    s.close()
    load = lambda v: json.loads(v) if isinstance(v, str) else v
    fb, lg, div, top = (load(v) for v in r[1])
    assert fb == ['Season 8'] and lg == ['Season 8'] and top == ['Season 8']
    assert div == ['Season 2', {'season': 'Season 8', 'division': 'Twill'}]
    assert load(r[2][0]) == ['Season 7'], "an existing title was touched"


def test_top_seeds_load_into_the_field_that_is_saved():
    src = open(os.path.join(os.path.dirname(__file__), 'managers', 'teamManager.py')).read()
    assert 'team.topSeeds = list(db_team.top_seeds or [])' in src


def test_team_rows_are_saved_when_the_season_ends():
    src = open(os.path.join(os.path.dirname(__file__), 'managers', 'seasonManager.py')).read()
    i = src.index('        self.saveSeasonStats()\n')
    assert 'teamManager.saveTeamData()' in src[i:i + 900]


if __name__ == '__main__':
    import sys, pytest
    sys.exit(pytest.main(['-q', __file__]))
