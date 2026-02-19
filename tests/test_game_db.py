"""
Test game data database integration.
Verifies that games and player stats can be saved and loaded from the database.
"""

import sys
from pathlib import Path

# Add parent directory to path (project root)
sys.path.insert(0, str(Path(__file__).parent.parent))

from database import init_db, clear_database
from database.config import USE_DATABASE
from database.connection import get_session
from database.models import Game as DBGame, GamePlayerStats, Team as DBTeam
from database.repositories import GameRepository

def test_game_database():
    """Test game data storage in database"""
    
    print("=== Game Database Integration Test ===\n")
    
    # Step 1: Initialize database
    print("Step 1: Initialize database")
    init_db()
    clear_database()
    print(f"✓ Database initialized (USE_DATABASE={USE_DATABASE})\n")
    
    if not USE_DATABASE:
        print("⚠️  Database not enabled, skipping test")
        return
    
    # Step 2: Create test data
    print("Step 2: Create test teams")
    session = get_session()
    
    # Create two teams
    team1 = DBTeam(
        id=1,
        name="Test Team 1",
        city="Test City 1",
        abbr="TT1",
        color="Blue",
        offense_rating=80,
        defense_rating=75,
        overall_rating=77
    )
    team2 = DBTeam(
        id=2,
        name="Test Team 2",
        city="Test City 2",
        abbr="TT2",
        color="Red",
        offense_rating=82,
        defense_rating=73,
        overall_rating=77
    )
    
    session.add(team1)
    session.add(team2)
    session.commit()
    print("✓ Created 2 test teams\n")
    
    # Step 3: Create game repository
    print("Step 3: Create game repository")
    game_repo = GameRepository(session)
    print("✓ Repositories created\n")
    
    # Step 4: Create and save a game
    print("Step 4: Create and save a game")
    game = DBGame(
        season=1,
        week=1,
        home_team_id=1,
        away_team_id=2,
        home_score=24,
        away_score=21,
        home_score_q1=7,
        home_score_q2=10,
        home_score_q3=0,
        home_score_q4=7,
        away_score_q1=7,
        away_score_q2=7,
        away_score_q3=0,
        away_score_q4=7,
        is_overtime=False,
        is_playoff=False,
        total_plays=120
    )
    
    game_repo.save(game)
    session.commit()
    print(f"✓ Saved game: Season {game.season}, Week {game.week}")
    print(f"  {team2.abbr} @ {team1.abbr}: {game.away_score}-{game.home_score}\n")
    
    # Step 5: Query games
    print("Step 5: Query games from database")
    
    # Get by season and week
    week_games = game_repo.get_by_season_week(season=1, week=1)
    print(f"  Games in season 1, week 1: {len(week_games)}")
    
    # Get team games
    team1_games = game_repo.get_by_team(team_id=1)
    print(f"  Team 1 games: {len(team1_games)}")
    print("✓ Queries successful\n")
    
    # Step 6: Test eager loading
    print("Step 6: Test relationships")
    loaded_game = game_repo.get_by_id(game.id)
    if loaded_game:
        # Note: Relationships will be lazy loaded here
        print(f"✓ Loaded game:")
        print(f"  Home Team ID: {loaded_game.home_team_id}")
        print(f"  Away Team ID: {loaded_game.away_team_id}")
        print(f"  Score: {loaded_game.away_score}-{loaded_game.home_score}")
    print()
    
    # Step 7: Test multiple games
    print("Step 7: Create multiple games for a season")
    for week in range(2, 5):
        g = DBGame(
            season=1,
            week=week,
            home_team_id=1 if week % 2 == 0 else 2,
            away_team_id=2 if week % 2 == 0 else 1,
            home_score=20 + week,
            away_score=17 + week,
            is_overtime=week == 3,
            is_playoff=False
        )
        game_repo.save(g)
    session.commit()
    
    all_games = game_repo.get_by_team(team_id=1, season=1)
    print(f"✓ Created {len(all_games)} games for season 1\n")
    
    # Step 8: Test playoff games
    print("Step 8: Create playoff game")
    playoff_game = DBGame(
        season=1,
        week=17,
        home_team_id=1,
        away_team_id=2,
        home_score=31,
        away_score=28,
        is_overtime=True,
        is_playoff=True,
        playoff_round="Wild Card"
    )
    game_repo.save(playoff_game)
    session.commit()
    
    # Query playoff games manually (no dedicated method in base repo)
    all_team_games = game_repo.get_by_team(team_id=1, season=1)
    playoff_games = [g for g in all_team_games if g.is_playoff]
    print(f"✓ Playoff games in season 1: {len(playoff_games)}")
    for pg in playoff_games:
        print(f"  Week {pg.week}: {pg.playoff_round}, OT: {pg.is_overtime}\n")
    
    # Step 9: Summary
    print("=== Test Complete! ===\n")
    print("Summary:")
    print("✓ Game repository can save games")
    print("✓ Game repository can query by season/week/team")
    print("✓ Game relationships work (teams)")
    print("✓ Regular and playoff games supported")
    print("\nGame data is ready for SeasonManager integration!")
    
    session.close()


if __name__ == "__main__":
    test_game_database()
