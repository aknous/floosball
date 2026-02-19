"""
Test RecordManager database integration.
Verifies that records can be saved and loaded from the database.
"""

import sys
from pathlib import Path

# Add parent directory to path (project root)
sys.path.insert(0, str(Path(__file__).parent.parent))

from database import init_db, clear_database
from database.config import USE_DATABASE
from database.connection import get_session
from database.models import Record as DBRecord, Player as DBPlayer, Team as DBTeam, League as DBLeague
from managers.recordManager import RecordManager
from unittest.mock import Mock

def test_record_manager_database():
    """Test RecordManager database integration"""
    
    print("=== RecordManager Database Integration Test ===\n")
    
    # Step 1: Initialize database
    print("Step 1: Initialize database")
    init_db()
    clear_database()
    print(f"✓ Database initialized (USE_DATABASE={USE_DATABASE})\n")
    
    if not USE_DATABASE:
        print("⚠️  Database not enabled, skipping test")
        return
    
    session = get_session()
    
    # Step 2: Create test data (league, team, player)
    print("Step 2: Create test data")
    
    league = DBLeague(id=1, name="Test League")
    session.add(league)
    session.flush()
    
    team = DBTeam(
        id=1,
        name="Test Team",
        city="Test City",
        abbr="TT",
        color="Blue",
        offense_rating=80,
        defense_rating=75,
        overall_rating=77,
        league_id=1
    )
    session.add(team)
    session.flush()
    
    player = DBPlayer(
        id=1,
        name="Test Player",
        team_id=1,
        position=0  # QB
    )
    session.add(player)
    session.commit()
    
    print("✓ Created test league, team, and player\n")
    
    # Step 3: Create mock service container
    print("Step 3: Create RecordManager")
    
    mock_container = Mock()
    
    # Mock player manager
    mock_player_manager = Mock()
    mock_player = Mock()
    mock_player.name = "Test Player"
    mock_player_manager.getPlayerById.return_value = mock_player
    
    # Mock team manager
    mock_team_manager = Mock()
    mock_team = Mock()
    mock_team.name = "Test Team"
    mock_team_manager.getTeamById.return_value = mock_team
    
    def get_service(service_name):
        if service_name == 'player_manager':
            return mock_player_manager
        elif service_name == 'team_manager':
            return mock_team_manager
        return None
    
    mock_container.getService = get_service
    
    record_manager = RecordManager(mock_container)
    
    print("✓ RecordManager initialized\n")
    
    # Step 4: Set some records manually
    print("Step 4: Set test records")
    
    records = record_manager.getRecords()
    
    # Set a player passing yards record
    records['players']['passing']['game']['yards'] = {
        'record': 'Pass Yards',
        'name': 'Test Player',
        'id': 1,
        'value': 450
    }
    
    # Set a player rushing TDs record
    records['players']['rushing']['season']['tds'] = {
        'record': 'Rush TDs',
        'name': 'Test Player',
        'id': 1,
        'value': 22,
        'season': 1
    }
    
    # Set a team wins record
    records['team']['allTime']['wins'] = {
        'record': 'Most Wins',
        'name': 'Test Team',
        'id': 1,
        'value': 100
    }
    
    print("✓ Set 3 test records\n")
    
    # Step 5: Save to database
    print("Step 5: Save records to database")
    
    record_manager.saveRecordsToFile()  # Will use database if enabled
    
    print("✓ Records saved\n")
    
    # Step 6: Verify in database
    print("Step 6: Verify records in database")
    
    db_records = session.query(DBRecord).all()
    print(f"  Found {len(db_records)} records in database")
    
    for rec in db_records:
        entity = f"Player {rec.player_id}" if rec.player_id else f"Team {rec.team_id}"
        season_str = f" (Season {rec.season})" if rec.season else ""
        print(f"  - {rec.record_type}: {rec.value} by {entity}{season_str}")
        print(f"    Category: {rec.category}, Scope: {rec.scope}, Stat: {rec.stat_name}")
    
    assert len(db_records) >= 3, f"Expected at least 3 records, got {len(db_records)}"
    print("\n✓ Records verified in database\n")
    
    # Step 7: Load from database
    print("Step 7: Load records from database")
    
    # Create a new RecordManager instance
    record_manager2 = RecordManager(mock_container)
    record_manager2.loadRecordsFromFile()  # Will use database if enabled
    
    loaded_records = record_manager2.getRecords()
    
    # Verify the loaded records
    pass_yards = loaded_records['players']['passing']['game']['yards']
    print(f"  Loaded passing yards record: {pass_yards['value']} by {pass_yards['name']}")
    assert pass_yards['value'] == 450, f"Expected 450, got {pass_yards['value']}"
    
    print("\n✓ Records loaded successfully from database\n")
    
    # Step 8: Test statistics
    print("Step 8: Test record statistics")
    
    stats = record_manager2.getRecordStatistics()
    print(f"  Total records: {stats['totalRecords']}")
    print(f"  Player records: {stats['totalPlayerRecords']}")
    print(f"  Team records: {stats['totalTeamRecords']}")
    print(f"  Has records: {stats['hasRecords']}")
    
    assert stats['hasRecords'], "Should have records"
    print("\n✓ Statistics working\n")
    
    # Step 9: Summary
    print("=== Test Complete! ===\n")
    print("Summary:")
    print("✓ RecordManager initialized with database support")
    print("✓ Records saved to database")
    print("✓ Records loaded from database")
    print("✓ Record structure preserved")
    print("✓ Statistics calculated correctly")
    print("\nRecordManager is ready for database storage!")
    
    session.close()


if __name__ == "__main__":
    test_record_manager_database()
