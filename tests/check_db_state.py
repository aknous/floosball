"""Quick check of database state"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database.connection import get_session
from database.models import Team, Player, League

session = get_session()

# Check teams
teams = session.query(Team).all()
print(f'Teams: {len(teams)}')
for t in teams[:5]:
    print(f'  {t.name}: league_id={t.league_id}')

# Check leagues
leagues = session.query(League).all()
print(f'\nLeagues: {len(leagues)}')
for l in leagues:
    print(f'  {l.name} (id={l.id})')

# Check players
players = session.query(Player).all()
print(f'\nPlayers: {len(players)}')
for p in players[:5]:
    print(f'  {p.name}: team_id={p.team_id}')

session.close()
