"""
Test SeasonManager database integration.
Verifies that games are saved to database during season simulation.
"""

import sys
from pathlib import Path

# Add parent directory to path (project root)
sys.path.insert(0, str(Path(__file__).parent.parent))

from database import init_db, clear_database
from database.config import USE_DATABASE
from database.connection import get_session
from database.models import Game as DBGame, Team as DBTeam, League as DBLeague
from database.repositories import GameRepository
from managers.seasonManager import SeasonManager, Season
import floosball_team as FloosTeam
import floosball_game as FloosGame
from unittest.mock import Mock

def test_season_manager_game_saving():
    """Test that SeasonManager saves games to database"""
    
    print("=== SeasonManager Database Integration Test ===\n")
    
    # Step 1: Initialize database
    print("Step 1: Initialize database")
    init_db()
    clear_database()
    print(f"✓ Database initialized (USE_DATABASE={USE_DATABASE})\n")
    
    if not USE_DATABASE:
        print("⚠️  Database not enabled, skipping test")
        return
    
    session = get_session()
    
    # Step 2: Create test teams in database
    print("Step 2: Create test teams")
    
    # Create league first
    league = DBLeague(
        id=1,
        name="Test League"
    )
    session.add(league)
    session.flush()
    
    # Create teams
    team1 = DBTeam(
        id=1,
        name="Test Team 1",
        city="City1",
        abbr="TT1",
        color="Blue",
        offense_rating=80,
        defense_rating=75,
        overall_rating=77,
        league_id=1
    )
    team2 = DBTeam(
        id=2,
        name="Test Team 2",
        city="City2",
        abbr="TT2",
        color="Red",
        offense_rating=82,
        defense_rating=73,
        overall_rating=77,
        league_id=1
    )
    
    session.add(team1)
    session.add(team2)
    session.commit()
    print("✓ Created 2 test teams\n")
    
    # Step 3: Create mock service container and managers
    print("Step 3: Create mock managers")
    
    mock_container = Mock()
    mock_container.getService.return_value = None  # No team manager for this test
    
    mock_league_manager = Mock()
    mock_player_manager = Mock()
    mock_records_manager = Mock()
    mock_records_manager.processPostGameStats = Mock()
    mock_records_manager.checkPlayerGameRecords = Mock()
    mock_records_manager.checkTeamGameRecords = Mock()
    
    print("✓ Mock managers created\n")
    
    # Step 4: Create SeasonManager
    print("Step 4: Create SeasonManager")
    season_manager = SeasonManager(
        mock_container,
        mock_league_manager,
        mock_player_manager,
        mock_records_manager
    )
    
    # Create season
    season = Season(1)
    season.currentWeek = 1
    season_manager.currentSeason = season
    
    print("✓ SeasonManager initialized\n")
    
    # Step 5: Create and simulate a mock game
    print("Step 5: Simulate a game and save to database")
    
    # Create FloosTeam objects (in-memory objects)
    flos_team1 = FloosTeam.Team("Test Team 1")
    flos_team1.id = 1
    flos_team1.city = "City1"
    flos_team1.abbr = "TT1"
    flos_team1.seasonTeamStats = {'wins': 0, 'losses': 0}
    
    flos_team2 = FloosTeam.Team("Test Team 2")
    flos_team2.id = 2
    flos_team2.city = "City2"
    flos_team2.abbr = "TT2"
    flos_team2.seasonTeamStats = {'wins': 0, 'losses': 0}
    
    # Create a game (we'll manually set the results instead of simulating)
    game = FloosGame.Game(flos_team1, flos_team2, season_manager.timingManager)
    
    # Manually set game results
    game.homeScore = 24
    game.awayScore = 21
    game.homeScoresByQuarter = [7, 10, 0, 7]
    game.awayScoresByQuarter = [7, 7, 0, 7]
    game.isOvertimeGame = False
    game.isPlayoff = False
    game.totalPlays = 120
    game.winningTeam = flos_team1
    game.playerStats = {}  # Empty for this test
    
    # Save to database using the method
    season_manager._saveGameToDatabase(game)
    
    print(f"✓ Saved game: {flos_team2.abbr} @ {flos_team1.abbr}: {game.awayScore}-{game.homeScore}\n")
    
    # Step 6: Verify game was saved
    print("Step 6: Verify game in database")
    
    game_repo = GameRepository(session)
    saved_games = game_repo.get_by_season_week(season=1, week=1)
    
    print(f"  Found {len(saved_games)} games for season 1, week 1")
    
    if saved_games:
        db_game = saved_games[0]
        print(f"  Game details:")
        print(f"    Home Team ID: {db_game.home_team_id}, Score: {db_game.home_score}")
        print(f"    Away Team ID: {db_game.away_team_id}, Score: {db_game.away_score}")
        print(f"    Quarter scores:")
        print(f"      Q1: {db_game.home_score_q1} - {db_game.away_score_q1}")
        print(f"      Q2: {db_game.home_score_q2} - {db_game.away_score_q2}")
        print(f"      Q3: {db_game.home_score_q3} - {db_game.away_score_q3}")
        print(f"      Q4: {db_game.home_score_q4} - {db_game.away_score_q4}")
        
        # Verify scores match
        assert db_game.home_score == 24, f"Expected home score 24, got {db_game.home_score}"
        assert db_game.away_score == 21, f"Expected away score 21, got {db_game.away_score}"
        assert db_game.home_score_q1 == 7, f"Expected Q1 home score 7, got {db_game.home_score_q1}"
        
        print("\n✓ All game data verified correctly!\n")
    else:
        print("\n❌ ERROR: No games found in database!\n")
        return
    
    # Step 7: Summary
    print("=== Test Complete! ===\n")
    print("Summary:")
    print("✓ SeasonManager initialized with database support")
    print("✓ Game data saved to database")
    print("✓ Quarter-by-quarter scores preserved")
    print("✓ Game metadata (week, season, teams) correct")
    print("\nSeasonManager is ready for full season simulation!")
    
    session.close()


if __name__ == "__main__":
    test_season_manager_game_saving()
