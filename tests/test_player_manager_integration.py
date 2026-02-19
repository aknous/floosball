#!/usr/bin/env python3
"""
Test script to verify PlayerManager integration with floosball.py
"""

import sys
import os

# Add current directory to path so we can import floosball modules
sys.path.insert(0, os.getcwd())

def testPlayerManagerIntegration():
    """Test that PlayerManager integration works correctly"""
    print("Testing PlayerManager integration...")
    
    try:
        # Import floosball module
        import floosball
        
        print(f"✅ Successfully imported floosball module")
        print(f"✅ Version: {floosball.__version__}")
        
        # Check if PlayerManager was imported
        if hasattr(floosball, 'PlayerManager'):
            print("✅ PlayerManager class is available")
        else:
            print("❌ PlayerManager class not found")
            return False
        
        # Test would require full initialization
        print("✅ Basic import test passed")
        print("\nNote: Full integration test requires running floosball.startLeague()")
        print("which would initialize the entire league system.")
        
        return True
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

def testBackwardCompatibility():
    """Test that global variable names still exist"""
    print("\nTesting backward compatibility...")
    
    try:
        import floosball
        
        # Check that global variables exist (they should be empty initially)
        globalVars = [
            'activePlayerList', 'freeAgentList', 'retiredPlayersList', 
            'hallOfFame', 'activeQbList', 'activeRbList', 'activeWrList',
            'activeTeList', 'activeKList'
        ]
        
        for varName in globalVars:
            if hasattr(floosball, varName):
                print(f"✅ Global variable '{varName}' exists")
            else:
                print(f"❌ Global variable '{varName}' missing")
                return False
        
        print("✅ All expected global variables exist")
        return True
        
    except Exception as e:
        print(f"❌ Backward compatibility test failed: {e}")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("FLOOSBALL PLAYER MANAGER INTEGRATION TEST")
    print("=" * 60)
    
    success1 = testPlayerManagerIntegration()
    success2 = testBackwardCompatibility()
    
    print("\n" + "=" * 60)
    if success1 and success2:
        print("🎉 ALL TESTS PASSED - Integration appears successful!")
        print("\nNext steps:")
        print("1. Run a full simulation to test complete functionality")  
        print("2. Verify API endpoints still work correctly")
        print("3. Check that player statistics are maintained")
    else:
        print("❌ SOME TESTS FAILED - Integration needs fixes")
    print("=" * 60)