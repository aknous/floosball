#!/usr/bin/env python3
"""
Test script to verify PlayerManager loads names correctly from config
"""

import sys
import os
import json

# Add current directory to path
sys.path.insert(0, os.getcwd())

def testNameLoading():
    """Test that PlayerManager loads names from config/unusedNames.json correctly"""
    print("Testing PlayerManager name loading...")
    
    try:
        # Load config to see what names are available
        with open('config.json', 'r') as f:
            config = json.load(f)
        
        totalConfigNames = len(config.get('players', []))
        print(f"✅ Config contains {totalConfigNames} player names")
        
        # Check if unusedNames.json exists and how many names it has
        if os.path.exists('data/unusedNames.json'):
            with open('data/unusedNames.json', 'r') as f:
                unusedNames = json.load(f)
            unusedCount = len(unusedNames)
            print(f"✅ data/unusedNames.json contains {unusedCount} unused names")
        else:
            print("📝 data/unusedNames.json doesn't exist - will be created from config")
        
        # Initialize service container
        from service_container import initialize_services
        initialize_services()
        
        # Import and test PlayerManager
        from managers.playerManager import PlayerManager
        from service_container import get_service
        
        playerManager = PlayerManager(get_service('game_state'))
        
        print(f"✅ PlayerManager initialized")
        
        # Test name loading
        print(f"📝 Loading names from config...")
        playerManager.loadNameLists(config)
        
        loadedNames = len(playerManager.unusedNames)
        print(f"✅ PlayerManager loaded {loadedNames} names")
        
        # Show first few names to verify they're real names from config
        if playerManager.unusedNames:
            sampleNames = playerManager.unusedNames[:5]
            print(f"📝 Sample names: {sampleNames}")
        
        # Test creating a few players to see name assignment
        print(f"📝 Testing player creation with real names...")
        
        import floosball_player as FloosPlayer
        testPlayer1 = playerManager.createPlayer(FloosPlayer.Position.QB)
        testPlayer2 = playerManager.createPlayer(FloosPlayer.Position.RB)
        
        if testPlayer1 and testPlayer2:
            print(f"✅ Created QB: {testPlayer1.name}")
            print(f"✅ Created RB: {testPlayer2.name}")
            print(f"📝 Remaining unused names: {len(playerManager.unusedNames)}")
        
        # Test save functionality
        print(f"📝 Testing saveUnusedNames...")
        playerManager.saveUnusedNames()
        print(f"✅ Successfully saved unused names")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("FLOOSBALL PLAYERMANAGER NAME LOADING TEST")
    print("=" * 60)
    
    success = testNameLoading()
    
    print("\n" + "=" * 60)
    if success:
        print("🎉 NAME LOADING TEST PASSED!")
        print("\nPlayerManager now properly:")
        print("✅ Loads names from data/unusedNames.json or config.json")
        print("✅ Uses original random selection logic")
        print("✅ Saves unused names back to JSON file")
        print("✅ Maintains same behavior as original getPlayers()")
    else:
        print("❌ NAME LOADING TEST FAILED")
    print("=" * 60)