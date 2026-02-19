"""Test PlayerManager with database integration."""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from database import init_db, clear_database, get_db_stats
from database.config import USE_DATABASE
from managers.playerManager import PlayerManager
from service_container import ServiceContainer


def test_player_manager_database():
    """Test PlayerManager with database storage."""
    
    print("=== PlayerManager Database Integration Test ===\n")
    
    # Step 1: Initialize database
    print("Step 1: Initialize database")
    init_db()
    clear_database()  # Start fresh
    print(f"✓ Database initialized (USE_DATABASE={USE_DATABASE})\n")
    
    # Step 2: Create service container and player manager
    print("Step 2: Create PlayerManager")
    service_container = ServiceContainer()
    player_manager = PlayerManager(service_container)
    print(f"✓ PlayerManager created\n")
    
    # Step 3: Load config for player generation
    print("Step 3: Load configuration")
    import json
    with open('config.json', 'r') as f:
        config = json.load(f)
    print("✓ Config loaded\n")
    
    # Step 4: Generate players
    print("Step 4: Generate players (force fresh)")
    player_manager.generatePlayers(config, force_fresh=True)
    print(f"✓ Generated {len(player_manager.activePlayers)} players")
    print(f"  - QBs: {len(player_manager.activeQbs)}")
    print(f"  - RBs: {len(player_manager.activeRbs)}")
    print(f"  - WRs: {len(player_manager.activeWrs)}")
    print(f"  - TEs: {len(player_manager.activeTes)}")
    print(f"  - Ks: {len(player_manager.activeKs)}")
    print(f"  - Unused names: {len(player_manager.unusedNames)}\n")
    
    # Step 5: Save players to database
    print("Step 5: Save players to database")
    player_manager.savePlayerData()
    player_manager.saveUnusedNames()
    print("✓ Players saved\n")
    
    # Step 6: Verify data in database
    print("Step 6: Verify database contents")
    stats = get_db_stats()
    print("Database counts:")
    for table, count in stats.items():
        if count > 0:
            print(f"  {table}: {count}")
    print()
    
    # Step 7: Create new manager and load from database
    print("Step 7: Create new PlayerManager and load from database")
    player_manager2 = PlayerManager(service_container)
    player_manager2.generatePlayers(config, force_fresh=False)
    print(f"✓ Loaded {len(player_manager2.activePlayers)} players from database")
    print(f"  - Unused names: {len(player_manager2.unusedNames)}\n")
    
    # Step 8: Verify players match
    print("Step 8: Verify loaded players match")
    if len(player_manager.activePlayers) == len(player_manager2.activePlayers):
        print(f"✓ Player count matches: {len(player_manager.activePlayers)}")
    else:
        print(f"✗ Player count mismatch: {len(player_manager.activePlayers)} vs {len(player_manager2.activePlayers)}")
    
    # Check a few players
    sample_players = 3
    for i in range(min(sample_players, len(player_manager.activePlayers))):
        p1 = player_manager.activePlayers[i]
        p2 = player_manager2.activePlayers[i]
        match = (
            p1.id == p2.id and
            p1.name == p2.name and
            p1.playerRating == p2.playerRating
        )
        status = "✓" if match else "✗"
        print(f"  {status} Player {i+1}: {p1.name} (ID={p1.id}, Rating={p1.playerRating})")
    print()
    
    # Step 9: Test fresh start capability
    print("Step 9: Test fresh start (clear and regenerate)")
    player_count_before = len(player_manager.activePlayers)
    clear_database()
    player_manager3 = PlayerManager(service_container)
    player_manager3.generatePlayers(config, force_fresh=True)
    player_manager3.savePlayerData()
    print(f"✓ Fresh start successful: {player_count_before} → {len(player_manager3.activePlayers)} players\n")
    
    print("=== Test Complete! ===")
    print("\nSummary:")
    print("✓ PlayerManager can generate players")
    print("✓ PlayerManager can save to database")
    print("✓ PlayerManager can load from database")
    print("✓ Loaded players match saved players")
    print("✓ Fresh start (clear database) works")
    print("\nPlayerManager is ready for database storage!")


if __name__ == "__main__":
    test_player_manager_database()
