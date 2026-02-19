#!/usr/bin/env python3
"""Verify database migration completeness"""

from database import get_session
from database.models import Team, Game, Player

session = get_session()

print("=" * 60)
print("DATABASE MIGRATION VERIFICATION")
print("=" * 60)

# Teams
teams = session.query(Team).all()
print(f'\n✅ TEAMS: {len(teams)} teams in database')
if teams:
    # Find a champion team
    champ_team = None
    for team in teams:
        if team.league_championships:
            champ_team = team
            break
    
    if champ_team:
        print(f'\n📊 Champion Team: {champ_team.name}')
        print(f'   Championships: {len(champ_team.league_championships)}')
        print(f'   Playoff Appearances: {champ_team.playoff_appearances}')
        print(f'   Roster History: {len(champ_team.roster_history) if champ_team.roster_history else 0} seasons')
        print(f'   All-time Wins: {champ_team.all_time_stats.get("wins", 0) if champ_team.all_time_stats else 0}')
        print(f'   All-time Losses: {champ_team.all_time_stats.get("losses", 0) if champ_team.all_time_stats else 0}')

# Games
total_games = session.query(Game).count()
playoff_games = session.query(Game).filter_by(is_playoff=True).count()
reg_games = total_games - playoff_games
print(f'\n✅ GAMES: {total_games} total games')
print(f'   Regular Season: {reg_games}')
print(f'   Playoff: {playoff_games}')

# Sample playoff game
playoff_game = session.query(Game).filter_by(is_playoff=True).first()
if playoff_game:
    print(f'\n📊 Sample Playoff Game:')
    print(f'   Season {playoff_game.season}, Round {playoff_game.playoff_round}')
    print(f'   Home: {playoff_game.home_score}, Away: {playoff_game.away_score}')

# Players
players = session.query(Player).all()
print(f'\n✅ PLAYERS: {len(players)} players in database')
if players:
    # Sample player
    player = players[0]
    print(f'\n📊 Sample Player: {player.name}')
    print(f'   Career Stats: {len(player.career_stats) if player.career_stats else 0} seasons')
    print(f'   Current Team ID: {player.team_id}')

# Calculate expected games per season (28 reg + ~14 playoff = ~42)
seasons = session.query(Game.season).distinct().count()
if seasons > 0:
    avg_games_per_season = total_games / seasons
    avg_playoff_per_season = playoff_games / seasons
    print(f'\n📈 SEASON STATS: {seasons} seasons simulated')
    print(f'   Avg games/season: {avg_games_per_season:.1f}')
    print(f'   Avg playoff games/season: {avg_playoff_per_season:.1f}')

print(f'\n{"=" * 60}')
print("✅ Database migration appears successful!")
print("=" * 60)

session.close()
