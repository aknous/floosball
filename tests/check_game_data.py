"""
Quick test to verify games are saved during actual season simulation.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database import init_db
from database.config import USE_DATABASE
from database.connection import get_session
from database.repositories import GameRepository
import sqlite3

def check_database_games():
    """Check how many games are in the database"""
    print("=== Checking Game Data in Database ===\n")
    
    if not USE_DATABASE:
        print("⚠️  Database not enabled")
        return
    
    # Direct SQL query to see what's in the games table
    db_path = "data/floosball.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Count total games
    cursor.execute("SELECT COUNT(*) FROM games")
    total_games = cursor.fetchone()[0]
    print(f"Total games in database: {total_games}")
    
    # Get games by season
    cursor.execute("""
        SELECT season, week, COUNT(*) as game_count 
        FROM games 
        GROUP BY season, week 
        ORDER BY season, week
    """)
    
    games_by_week = cursor.fetchall()
    if games_by_week:
        print("\nGames by season/week:")
        for season, week, count in games_by_week:
            print(f"  Season {season}, Week {week}: {count} games")
    
    # Show a few sample games
    cursor.execute("""
        SELECT g.id, g.season, g.week, 
               ht.abbr as home_team, g.home_score,
               at.abbr as away_team, g.away_score,
               g.is_overtime, g.is_playoff
        FROM games g
        LEFT JOIN teams ht ON g.home_team_id = ht.id
        LEFT JOIN teams at ON g.away_team_id = at.id
        ORDER BY g.season, g.week, g.id
        LIMIT 10
    """)
    
    sample_games = cursor.fetchall()
    if sample_games:
        print("\nSample games:")
        for game in sample_games:
            game_id, season, week, home, home_score, away, away_score, ot, playoff = game
            ot_str = " (OT)" if ot else ""
            playoff_str = " [PLAYOFF]" if playoff else ""
            print(f"  Game {game_id}: S{season} W{week} - {away} @ {home}: {away_score}-{home_score}{ot_str}{playoff_str}")
    
    # Check player stats
    cursor.execute("SELECT COUNT(*) FROM game_player_stats")
    total_stats = cursor.fetchone()[0]
    print(f"\nTotal player stat records: {total_stats}")
    
    conn.close()
    print("\n✓ Database check complete!")


if __name__ == "__main__":
    check_database_games()
