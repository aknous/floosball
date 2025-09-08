"""
Integration example showing how PlayerManager replaces the scattered 
player management code in floosball.py
"""

from managers.playerManager import PlayerManager
from service_container import get_service, set_game_state
from config_manager import get_config

# Example: How the refactored version would work
class RefactoredFloosball:
    """Example of how floosball.py would look with PlayerManager"""
    
    def __init__(self):
        # Initialize service container (already done)
        from service_container import initialize_services
        initialize_services()
        
        # Initialize managers
        self.playerManager = PlayerManager(get_service('gameStateManager'))
        
    async def startLeague(self):
        """Refactored version of startLeague function"""
        # Load config (same as before)
        config = get_config()
        
        # Initialize players using PlayerManager instead of scattered global code
        self.playerManager.generatePlayers(config)
        
        # Conduct initial draft
        self.playerManager.conductInitialDraft()
        
        # Sort players by position and rating
        self.playerManager.sortPlayersByPosition()
        
        # Continue with rest of league initialization...
        
    def getPlayerStats(self):
        """Example of getting player statistics"""
        return self.playerManager.getStatistics()
    
    def getActiveQbs(self):
        """Replace global activeQbList with clean method"""
        return self.playerManager.activeQbs
    
    def findPlayerById(self, playerId: int):
        """Replace scattered player search with clean method"""
        return self.playerManager.getPlayerById(playerId)

# Backward compatibility layer (temporary during migration)
class BackwardCompatibility:
    """Provides global variable access for existing API code"""
    
    def __init__(self, playerManager: PlayerManager):
        self.playerManager = playerManager
    
    @property
    def activePlayerList(self):
        """Replace global activePlayerList"""
        return self.playerManager.activePlayers
    
    @property 
    def freeAgentList(self):
        """Replace global freeAgentList"""
        return self.playerManager.freeAgents
    
    @property
    def retiredPlayersList(self):
        """Replace global retiredPlayersList"""
        return self.playerManager.retiredPlayers
    
    @property
    def hallOfFame(self):
        """Replace global hallOfFame"""
        return self.playerManager.hallOfFame
    
    @property
    def activeQbList(self):
        """Replace global activeQbList"""
        return self.playerManager.activeQbs
    
    @property
    def activeRbList(self):
        """Replace global activeRbList"""
        return self.playerManager.activeRbs
    
    @property
    def activeWrList(self):
        """Replace global activeWrList"""
        return self.playerManager.activeWrs
    
    @property
    def activeTeList(self):
        """Replace global activeTeList"""
        return self.playerManager.activeTes
    
    @property
    def activeKList(self):
        """Replace global activeKList"""  
        return self.playerManager.activeKs

# Usage example:
if __name__ == "__main__":
    # Create refactored application
    app = RefactoredFloosball()
    
    # Run league initialization
    import asyncio
    asyncio.run(app.startLeague())
    
    # Get statistics
    stats = app.getPlayerStats()
    print(f"Player Statistics: {stats}")
    
    # Find specific players
    qbs = app.getActiveQbs()
    print(f"Found {len(qbs)} active quarterbacks")
    
    # Backward compatibility example
    compat = BackwardCompatibility(app.playerManager)
    oldStyleAccess = compat.activePlayerList  # Works like old global variable
    print(f"Backward compatible access: {len(oldStyleAccess)} active players")