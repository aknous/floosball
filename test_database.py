"""Test script to verify database creation and basic operations."""

from database import init_db, get_session, get_db_stats
from database.models import League, Team, Player

def test_database_setup():
    """Test that database is created and accessible."""
    print("Testing database setup...\n")
    
    # Test 1: Check database file exists
    from pathlib import Path
    db_path = Path(__file__).parent / "data" / "floosball.db"
    if db_path.exists():
        print(f"✓ Database file created: {db_path}")
    else:
        print(f"✗ Database file not found: {db_path}")
        return False
    
    # Test 2: Get database statistics
    try:
        stats = get_db_stats()
        print(f"\n✓ Database connection successful")
        print("\nTable counts:")
        for table, count in stats.items():
            print(f"  {table}: {count}")
    except Exception as e:
        print(f"\n✗ Database connection failed: {e}")
        return False
    
    # Test 3: Test basic CRUD operations
    print("\n--- Testing basic CRUD operations ---\n")
    session = get_session()
    try:
        # Create a test league
        test_league = League(name="Test League")
        session.add(test_league)
        session.commit()
        print(f"✓ Created league: {test_league}")
        
        # Read the league back
        league = session.query(League).filter_by(name="Test League").first()
        print(f"✓ Retrieved league: {league}")
        
        # Create a test team
        test_team = Team(
            id=999,
            name="Test Team",
            city="Test City",
            abbr="TST",
            color="blue",
            offense_rating=85,
            defense_rating=80,
            overall_rating=82,
            league_id=test_league.id
        )
        session.add(test_team)
        session.commit()
        print(f"✓ Created team: {test_team}")
        
        # Create a test player
        test_player = Player(
            id=9999,
            name="Test Player",
            team_id=test_team.id,
            position=0,  # QB
            seasons_played=5
        )
        session.add(test_player)
        session.commit()
        print(f"✓ Created player: {test_player}")
        
        # Test relationships
        team_with_players = session.query(Team).filter_by(id=999).first()
        print(f"\n✓ Team {team_with_players.name} has {len(team_with_players.players)} player(s)")
        print(f"✓ Team league: {team_with_players.league.name}")
        
        # Cleanup test data
        session.delete(test_player)
        session.delete(test_team)
        session.delete(test_league)
        session.commit()
        print(f"\n✓ Cleanup successful")
        
        print("\n✅ All tests passed!")
        return True
        
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        session.rollback()
        return False
    finally:
        session.close()


if __name__ == "__main__":
    test_database_setup()
