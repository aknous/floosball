#!/usr/bin/env python3
"""Quick database check script"""

from database import get_session
from database.models import Team, Game

session = get_session()

# Check teams
teams = session.query(Team).all()
print(f'Total teams in database: {len(teams)}')

# Check a sample team
if teams:
    team = teams[0]
    print(f'\nSample Team: {team.name}')
    print(f'  League Championships: {team.league_championships}')
    print(f'  Playoff Appearances: {team.playoff_appearances}')
    print(f'  All-time Stats: {team.all_time_stats}')
    print(f'  Roster History Length: {len(team.roster_history) if team.roster_history else 0}')
    if team.roster_history:
        print(f'  First Roster Entry Keys: {list(team.roster_history[0].keys())[:5]}...')

# Check games
total_games = session.query(Game).count()
playoff_games = session.query(Game).filter_by(is_playoff=True).count()
print(f'\nTotal games in database: {total_games}')
print(f'Playoff games: {playoff_games}')
print(f'Regular season games: {total_games - playoff_games}')

session.close()
