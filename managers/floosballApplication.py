"""
FloosballApplication - Main application orchestrator
Coordinates all manager components and provides the main entry point for the refactored floosball system
"""

import asyncio
from typing import Dict, Any, Optional
from logger_config import get_logger

# Import managers
from managers.playerManager import PlayerManager
from managers.teamManager import TeamManager
from managers.leagueManager import LeagueManager
from managers.seasonManager import SeasonManager
from managers.recordManager import RecordManager

logger = get_logger("floosball.application")

class FloosballApplication:
    """Main application class that orchestrates all components"""
    
    def __init__(self, serviceContainer):
        logger.info("Initializing FloosballApplication")
        
        # Store service container
        self.serviceContainer = serviceContainer
        
        # Initialize managers
        self.playerManager = PlayerManager(serviceContainer)
        self.teamManager = TeamManager(serviceContainer)
        self.leagueManager = LeagueManager(serviceContainer)
        self.recordsManager = RecordManager(serviceContainer)
        
        # SeasonManager depends on other managers, so initialize last
        self.seasonManager = SeasonManager(
            serviceContainer,
            self.leagueManager,
            self.playerManager,
            self.recordsManager
        )
        
        # Register managers with service container for cross-dependencies
        self._registerManagersWithServices()
        
        logger.info("FloosballApplication initialized successfully")
    
    def _registerManagersWithServices(self) -> None:
        """Register managers with service container for dependency injection"""
        self.serviceContainer.registerService('player_manager', self.playerManager)
        self.serviceContainer.registerService('team_manager', self.teamManager)
        self.serviceContainer.registerService('league_manager', self.leagueManager)
        self.serviceContainer.registerService('season_manager', self.seasonManager)
        self.serviceContainer.registerService('records_manager', self.recordsManager)
        
        logger.info("Registered all managers with service container")
    
    async def initializeLeague(self, config: Dict[str, Any], force_fresh: bool = False) -> None:
        """Initialize the entire league system"""
        logger.info("Initializing league system")
        
        # Load configuration
        self._loadConfiguration(config)
        
        # Initialize records manager
        self.recordsManager.loadRecordsFromFile()
        
        # Generate and setup players
        logger.info("Setting up players...")
        self.playerManager.generatePlayers(config, force_fresh=force_fresh)
        self.playerManager.sortPlayersByPosition()
        
        # Generate teams (but don't initialize yet - need players first)
        logger.info("Setting up teams...")
        self.teamManager.generateTeams(config)
        
        # Create leagues and distribute teams
        logger.info("Setting up leagues...")
        self.leagueManager.createLeagues(config)
        
        # Conduct initial draft if no existing rosters
        if self._needsInitialDraft():
            logger.info("Conducting initial draft...")
            self.playerManager.conductInitialDraft()
        
        # Now initialize teams after players are assigned
        logger.info("Initializing teams with rosters...")
        self.teamManager.initializeTeams()
        
        # Initialize ELO ratings for all teams
        logger.info("Calculating initial ELO ratings...")
        self.teamManager.setNewElo()
        
        # Save initial state
        await self._saveInitialState()
        
        logger.info("League initialization complete")
    
    def _loadConfiguration(self, config: Dict[str, Any]) -> None:
        """Load and validate configuration"""
        # Get game state manager from service container
        gameState = self.serviceContainer.getService('game_state')
        
        # Store essential config in game state  
        leagueConfig = config.get('leagueConfig', {})
        gameState.setState('totalSeasons', leagueConfig.get('totalSeasons', 10))
        gameState.setState('seasonsPlayed', leagueConfig.get('lastSeason', 0))
        
        # Set any other global configuration
        if 'salaryCap' in config:
            gameState.setState('salaryCap', config['salaryCap'])
        
        # Configure timing mode
        if 'timingMode' in config:
            self.setTimingMode(config['timingMode'])
        
        # Set custom timing delays
        if 'timingDelays' in config:
            self.setCustomTimingDelays(config['timingDelays'])
    
    def _needsInitialDraft(self) -> bool:
        """Check if we need to conduct an initial draft"""
        # Simple check: if most teams have empty rosters, we need a draft
        emptyRosterCount = 0
        
        for team in self.teamManager.teams:
            if not hasattr(team, 'rosterDict') or not team.rosterDict or all(player is None for player in team.rosterDict.values()):
                emptyRosterCount += 1
        
        return emptyRosterCount > len(self.teamManager.teams) * 0.5  # More than 50% empty
    
    async def _saveInitialState(self) -> None:
        """Save initial league state"""
        self.playerManager.savePlayerData()
        self.playerManager.saveUnusedNames()
        self.leagueManager.saveLeagueData()
        self.recordsManager.saveRecordsToFile()
    
    async def runSimulation(self) -> None:
        """Run the main league simulation"""
        logger.info("Starting league simulation")
        
        gameState = self.serviceContainer.getService('game_state')
        totalSeasons = gameState.getState('totalSeasons', 0)
        seasonsPlayed = gameState.getState('seasonsPlayed', 0)
        
        logger.info(f"Simulating {totalSeasons - seasonsPlayed} seasons")
        
        while seasonsPlayed < totalSeasons:
            logger.info(f"=== SEASON {seasonsPlayed + 1} ===")
            
            # Start new season
            await self.seasonManager.startNewSeason()
            
            # Run season simulation
            await self.seasonManager.runSeasonSimulation()
            
            # Handle offseason
            await self.seasonManager.handleOffseason()
            
            # Update season counter
            seasonsPlayed += 1
            gameState = self.serviceContainer.getService('game_state')
            gameState.setState('seasonsPlayed', seasonsPlayed)
            
            # Save state after each season
            await self._saveSeasonState()
            
            # Move to next season
            self.seasonManager.advanceToNextSeason()
        
        # Final save and cleanup
        await self._completeFinalSimulation()
        
        logger.info("League simulation complete")
    
    async def _saveSeasonState(self) -> None:
        """Save state after each season"""
        self.playerManager.savePlayerData()
        self.recordsManager.saveRecordsToFile()
        
        # Save team data periodically
        seasonsPlayed = self.serviceContainer.getService('game_state').getState('seasonsPlayed', 0)
        if seasonsPlayed % 5 == 0:  # Every 5 seasons
            for team in self.teamManager.teams:
                self.teamManager._setupAndSaveTeam(team)
    
    async def _completeFinalSimulation(self) -> None:
        """Complete final simulation tasks"""
        logger.info("Completing final simulation tasks")
        
        # Save all data
        self.playerManager.savePlayerData()
        self.playerManager.saveUnusedNames()
        self.recordsManager.saveRecordsToFile()
        self.leagueManager.saveLeagueData()
        
        # Final team data save
        for team in self.teamManager.teams:
            self.teamManager._setupAndSaveTeam(team)
        
        logger.info("Final simulation tasks complete")
    
    def setTimingMode(self, mode: str) -> None:
        """Set timing mode for simulation (scheduled/sequential/fast)"""
        self.seasonManager.setTimingModeFromString(mode)
        logger.info(f"Application timing mode set to {mode}")
    
    def setCustomTimingDelays(self, delays: Dict[str, float]) -> None:
        """Set custom timing delays"""
        self.seasonManager.setCustomTimingDelays(delays)
        logger.info(f"Custom timing delays configured: {delays}")
    
    def getTimingMode(self) -> str:
        """Get current timing mode"""
        return self.seasonManager.getTimingMode()
    
    def getLeagueState(self) -> Dict[str, Any]:
        """Get current state of the entire league"""
        return {
            'leagues': [{'name': league.name, 'teams': len(league.teamList)} for league in self.leagueManager.leagues],
            'totalTeams': len(self.teamManager.teams),
            'totalActivePlayers': len(self.playerManager.activePlayers),
            'totalFreeAgents': len(self.playerManager.freeAgents),
            'totalRetiredPlayers': len(self.playerManager.retiredPlayers),
            'hallOfFameCount': len(self.playerManager.hallOfFame),
            'currentSeason': self.seasonManager.currentSeason.seasonNumber if self.seasonManager.currentSeason else None,
            'seasonsPlayed': self.serviceContainer.getService('game_state').getState('seasonsPlayed', 0),
            'totalSeasons': self.serviceContainer.getService('game_state').getState('totalSeasons', 0),
            'timingMode': self.getTimingMode(),
            'records': self.recordsManager.getRecordStatistics()
        }
    
    def getDetailedStatistics(self) -> Dict[str, Any]:
        """Get comprehensive statistics for the entire league"""
        return {
            'players': self.playerManager.getStatistics(),
            'teams': self.teamManager.getTeamStatistics(),
            'leagues': self.leagueManager.getLeagueStatistics(),
            'season': self.seasonManager.getSeasonStats(),
            'records': self.recordsManager.getRecordStatistics()
        }
    
    async def runSingleSeason(self) -> Dict[str, Any]:
        """Run a single season and return results"""
        logger.info("Running single season simulation")
        
        # Start season
        await self.seasonManager.startNewSeason()
        
        # Run simulation
        await self.seasonManager.runSeasonSimulation()
        
        # Get results
        seasonResults = self.seasonManager.getSeasonStats()
        
        # Handle offseason
        await self.seasonManager.handleOffseason()
        
        # Update counters
        gameState = self.serviceContainer.getService('game_state')
        seasonsPlayed = gameState.getState('seasonsPlayed', 0) + 1
        gameState.setState('seasonsPlayed', seasonsPlayed)
        
        # Save state
        await self._saveSeasonState()
        
        # Clean up
        self.seasonManager.advanceToNextSeason()
        
        logger.info("Single season complete")
        return seasonResults
    
    # Backward compatibility methods for global access patterns
    def getActivePlayerList(self) -> list:
        """Backward compatibility: get active player list"""
        return self.playerManager.activePlayers
    
    def getTeamList(self) -> list:
        """Backward compatibility: get team list"""
        return self.teamManager.teams
    
    def getLeagueList(self) -> list:
        """Backward compatibility: get league list"""
        return self.leagueManager.leagues
    
    def getAllTimeRecords(self) -> dict:
        """Backward compatibility: get all-time records"""
        return self.recordsManager.getRecords()
    
    # Manager access methods
    def getPlayerManager(self) -> PlayerManager:
        """Get player manager instance"""
        return self.playerManager
    
    def getTeamManager(self) -> TeamManager:
        """Get team manager instance"""
        return self.teamManager
    
    def getLeagueManager(self) -> LeagueManager:
        """Get league manager instance"""
        return self.leagueManager
    
    def getSeasonManager(self) -> SeasonManager:
        """Get season manager instance"""
        return self.seasonManager
    
    def getRecordsManager(self) -> RecordManager:
        """Get records manager instance"""
        return self.recordsManager