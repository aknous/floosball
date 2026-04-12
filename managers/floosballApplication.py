"""
FloosballApplication - Main application orchestrator
Coordinates all manager components and provides the main entry point for the refactored floosball system
"""

import asyncio
from typing import Dict, Any, Optional
from logger_config import get_logger
from database.connection import SessionLocal
from database.models import SimulationState as DBSimulationState

# Import managers
from managers.playerManager import PlayerManager
from managers.teamManager import TeamManager
from managers.leagueManager import LeagueManager
from managers.seasonManager import SeasonManager
from managers.recordManager import RecordManager
from managers.fantasyTracker import FantasyTracker
from managers.personalityManager import PersonalityManager

logger = get_logger("floosball.application")

class FloosballApplication:
    """Main application class that orchestrates all components"""
    
    def __init__(self, serviceContainer):
        logger.info("Initializing FloosballApplication")
        
        # Store service container
        self.serviceContainer = serviceContainer
        
        # Create a single shared database session for all managers to prevent locking
        from database.connection import get_session
        self.shared_db_session = get_session()
        
        # Initialize managers
        self.playerManager = PlayerManager(serviceContainer)
        self.teamManager = TeamManager(serviceContainer)
        self.leagueManager = LeagueManager(serviceContainer)
        self.recordsManager = RecordManager(serviceContainer)
        self.personalityManager = PersonalityManager(serviceContainer)
        
        # Override each manager's session with the shared one to prevent lock conflicts
        if self.shared_db_session:
            self.playerManager.db_session = self.shared_db_session
            self.teamManager.db_session = self.shared_db_session
            self.leagueManager.db_session = self.shared_db_session
            self.recordsManager.db_session = self.shared_db_session
            
            # Re-initialize repositories with shared session
            from database import repositories
            self.playerManager.player_repo = repositories.PlayerRepository(self.shared_db_session)
            self.playerManager.name_repo = repositories.UnusedNameRepository(self.shared_db_session)
            self.teamManager.team_repo = repositories.TeamRepository(self.shared_db_session)
            self.teamManager.league_repo = repositories.LeagueRepository(self.shared_db_session)
            self.leagueManager.league_repo = repositories.LeagueRepository(self.shared_db_session)
            self.recordsManager.record_repo = repositories.RecordRepository(self.shared_db_session)
            logger.info("All managers using shared database session to prevent locking")
        
        # SeasonManager depends on other managers, so initialize last
        self.seasonManager = SeasonManager(
            serviceContainer,
            self.leagueManager,
            self.playerManager,
            self.recordsManager
        )
        
        # SeasonManager also gets the shared session
        if self.shared_db_session:
            self.seasonManager.db_session = self.shared_db_session
            from database import repositories
            self.seasonManager.game_repo = repositories.GameRepository(self.shared_db_session)
        
        # FantasyTracker reads from DB + live data; no shared session needed
        self.fantasyTracker = FantasyTracker(serviceContainer)

        # Register managers with service container for cross-dependencies
        self._registerManagersWithServices()
        
        # Set up state update callback for season manager
        self.seasonManager.setStateUpdateCallback(self._onSeasonStateUpdate)
        
        logger.info("FloosballApplication initialized successfully")
    
    def _registerManagersWithServices(self) -> None:
        """Register managers with service container for dependency injection"""
        self.serviceContainer.registerService('player_manager', self.playerManager)
        self.serviceContainer.registerService('team_manager', self.teamManager)
        self.serviceContainer.registerService('league_manager', self.leagueManager)
        self.serviceContainer.registerService('season_manager', self.seasonManager)
        self.serviceContainer.registerService('records_manager', self.recordsManager)
        self.serviceContainer.registerService('fantasy_tracker', self.fantasyTracker)
        self.serviceContainer.registerService('personality_manager', self.personalityManager)
        
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

        # Assign personality (archetype / demeanor / quirk) to the full player pool.
        # Runs after generation so Unique/Common caps are applied league-wide in a
        # single pass. Existing players with archetype already set are left alone
        # unless they came from a pre-personality schema (nullable archetype).
        logger.info("Assigning personality traits...")
        allPlayers = (
            self.playerManager.activePlayers
            + self.playerManager.freeAgents
            + self.playerManager.rookieDraftList
        )
        summary = self.personalityManager.assignToPlayerPool(allPlayers)
        logger.info(
            f"Personality assigned: {summary['quirked']}/{summary['total']} quirked, "
            f"{len(summary['activeUniques'])} active uniques"
        )
        
        # Generate teams (but don't initialize yet - need players first)
        logger.info("Setting up teams...")
        self.teamManager.generateTeams(config)
        
        # Save teams to database so leagues can reference them
        if self.teamManager.db_session:
            self.teamManager.saveTeamData()
        
        # Create leagues and distribute teams
        logger.info("Setting up leagues...")
        self.leagueManager.createLeagues(config)
        
        # Assign loaded players to their teams (if resuming from saved state)
        logger.info("Assigning players to teams...")
        self.playerManager.assignPlayersToTeams()
        
        # Conduct initial draft if no existing rosters
        if self._needsInitialDraft():
            logger.info("Conducting initial draft...")
            self.playerManager.conductInitialDraft()

        # Seed each team with a starter prospect class. Runs on every boot,
        # but seedInitialProspects is idempotent: skips any team that already
        # has prospects. So this fires on:
        #   - Fresh starts (all 24 teams seeded)
        #   - First deploy of this feature to existing prod (teams have full
        #     rosters but empty pipelines → all seeded)
        #   - Subsequent boots (prospects exist → no-op per team)
        logger.info("Seeding initial prospect pipelines (idempotent)...")
        self.playerManager.seedInitialProspects(prospectsPerTeam=3)
        
        # Now initialize teams after players are assigned
        logger.info("Initializing teams with rosters...")
        self.teamManager.initializeTeams()
        
        # Initialize ELO ratings for all teams
        logger.info("Calculating initial ELO ratings...")
        self.teamManager.setNewElo()
        
        # Register state update callback with season manager
        self.seasonManager.setStateUpdateCallback(self._onSeasonStateUpdate)
        
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
        
        needsDraft = emptyRosterCount > len(self.teamManager.teams) * 0.5  # More than 50% empty
        logger.info(f"Draft check: {emptyRosterCount}/{len(self.teamManager.teams)} teams have empty rosters. Needs draft: {needsDraft}")
        return needsDraft
    
    async def _saveInitialState(self) -> None:
        """Save initial league state"""
        self.playerManager.savePlayerData()
        self.playerManager.saveUnusedNames()
        self.leagueManager.saveLeagueData()  # This saves teams with league_id
        self.teamManager.saveTeamData()  # Save teams again to persist league assignments
        self.recordsManager.saveRecordsToFile()
    
    async def runSimulation(self) -> None:
        """Run the main league simulation"""
        logger.info("Starting league simulation")
        
        gameState = self.serviceContainer.getService('game_state')
        
        # Check for existing simulation state
        savedState = self._loadSimulationState()
        
        resumeMidOffseason = False
        if savedState and savedState['is_active']:
            totalSeasons = savedState['total_seasons']
            seasonsPlayed = savedState['current_season'] - 1  # We'll restart the current season
            resumeFromWeek = savedState['current_week']  # Skip completed weeks on resume

            # If the process died mid-offseason, the season's regular play + playoffs
            # already persisted to DB. Replaying would roll rosters back and nuke
            # that work (this is the bug that wiped production before). Treat the
            # offseason as complete: advance past it, then start the next season.
            if savedState.get('in_offseason'):
                logger.warning(
                    f"Resume: simulation_state.in_offseason=True for season "
                    f"{savedState['current_season']} — treating offseason as complete "
                    f"and advancing to the next season rather than replaying."
                )
                seasonsPlayed = savedState['current_season']  # advance past completed season
                resumeFromWeek = 0
                resumeMidOffseason = True
            else:
                logger.info(f"Resuming simulation from Season {savedState['current_season']}, Week {savedState['current_week']}")

            # Update game state
            gameState.setState('totalSeasons', totalSeasons)
            gameState.setState('seasonsPlayed', seasonsPlayed)
        else:
            totalSeasons = gameState.getState('totalSeasons', 0)
            seasonsPlayed = gameState.getState('seasonsPlayed', 0)
            resumeFromWeek = 0
            logger.info(f"Starting new simulation - {totalSeasons} seasons")

        # If we recovered from a mid-offseason crash, persist the advance + clear
        # the flag right away so another immediate restart won't repeat this.
        if resumeMidOffseason:
            self._saveSimulationState(
                current_season=seasonsPlayed + 1,
                current_week=0,
                in_playoffs=False,
                total_seasons=totalSeasons,
                is_active=True,
                in_offseason=False,
            )
            gameState.setState('seasonsPlayed', seasonsPlayed)
        
        # Mark simulation as active (preserve resumeFromWeek so a second
        # restart before the week loop progresses doesn't lose the checkpoint)
        self._saveSimulationState(
            current_season=seasonsPlayed + 1,
            current_week=resumeFromWeek,
            in_playoffs=False,
            total_seasons=totalSeasons,
            is_active=True
        )
        
        logger.info(f"Simulating {totalSeasons - seasonsPlayed} seasons")
        
        while True:
            currentSeason = seasonsPlayed + 1
            logger.info(f"=== SEASON {currentSeason} ===")

            # Update simulation state for this season (preserve week checkpoint
            # for the first iteration so a quick re-restart doesn't lose progress)
            self._saveSimulationState(
                current_season=currentSeason,
                current_week=resumeFromWeek,
                in_playoffs=False,
                total_seasons=totalSeasons,
                is_active=True
            )

            # Start new season
            await self.seasonManager.startNewSeason()

            # Run season simulation (this will update state as it progresses)
            await self.seasonManager.runSeasonSimulation(resumeFromWeek=resumeFromWeek)
            resumeFromWeek = 0  # Only skip weeks for the first (resumed) season

            # Mark offseason as in-progress BEFORE running it. If we crash mid-
            # offseason (deploy, OOM, whatever), resume logic will skip replay.
            self._saveSimulationState(
                current_season=currentSeason,
                current_week=self.seasonManager.currentSeason.currentWeek if self.seasonManager.currentSeason else 0,
                in_playoffs=False,
                total_seasons=totalSeasons,
                is_active=True,
                in_offseason=True,
            )

            # Handle offseason
            await self.seasonManager.handleOffseason()

            # Finalize season: increment counter, clear the offseason flag, and
            # save all state immediately so a restart during the between-seasons
            # wait doesn't replay the season.
            seasonsPlayed += 1
            gameState = self.serviceContainer.getService('game_state')
            gameState.setState('seasonsPlayed', seasonsPlayed)
            await self._saveSeasonState()
            self._saveSimulationState(
                current_season=seasonsPlayed + 1,
                current_week=0,
                in_playoffs=False,
                total_seasons=totalSeasons,
                is_active=True,
                in_offseason=False,
            )

            # Wait between seasons (SCHEDULED: polls until Monday; others: fixed delay)
            await self.seasonManager.timingManager.waitBetweenSeasons()

            # Move to next season
            self.seasonManager.advanceToNextSeason()
        
        logger.info("League simulation complete")
    
    async def _saveSeasonState(self) -> None:
        """Save state after each season"""
        self.playerManager.savePlayerData()
        self.recordsManager.saveRecordsToFile()
        
        # Save team data after every season (includes all-time stats, championships, roster history)
        self.teamManager.saveTeamData()
        logger.info("Saved season state (players, records, teams)")
    
    def _loadSimulationState(self) -> Optional[Dict[str, Any]]:
        """Load simulation state from database using existing session"""
        try:
            session = self.teamManager.db_session
            if not session:
                logger.warning("No database session available for loading state")
                return None
            
            state = session.query(DBSimulationState).filter_by(id=1).first()
            if state:
                logger.info(f"Found saved simulation state: Season {state.current_season}, Week {state.current_week}")
                return {
                    'current_season': state.current_season,
                    'current_week': state.current_week,
                    'in_playoffs': state.in_playoffs,
                    'playoff_round': state.playoff_round,
                    'total_seasons': state.total_seasons,
                    'is_active': state.is_active,
                    'in_offseason': bool(getattr(state, 'in_offseason', False)),
                    'last_saved': state.last_saved
                }
            return None
        except Exception as e:
            logger.warning(f"Could not load simulation state: {e}")
            return None
    
    def _saveSimulationState(self, current_season: int, current_week: int,
                            in_playoffs: bool, total_seasons: int,
                            is_active: bool, playoff_round: Optional[str] = None,
                            in_offseason: Optional[bool] = None) -> None:
        """Save simulation state to database using existing session.

        in_offseason is set True right before handleOffseason() runs, then
        cleared after seasonsPlayed has been advanced. If omitted, the existing
        value is preserved — so routine within-season saves don't accidentally
        wipe the flag.
        """
        try:
            # Use the teamManager's existing database session to avoid locking issues
            session = self.teamManager.db_session
            if not session:
                logger.warning("No database session available, skipping state save")
                return

            state = session.query(DBSimulationState).filter_by(id=1).first()
            if not state:
                state = DBSimulationState(
                    id=1,
                    current_season=current_season,
                    current_week=current_week,
                    in_playoffs=in_playoffs,
                    playoff_round=playoff_round,
                    total_seasons=total_seasons,
                    is_active=is_active,
                    in_offseason=bool(in_offseason) if in_offseason is not None else False,
                )
                session.add(state)
            else:
                state.current_season = current_season
                state.current_week = current_week
                state.in_playoffs = in_playoffs
                state.playoff_round = playoff_round
                state.total_seasons = total_seasons
                state.is_active = is_active
                if in_offseason is not None:
                    state.in_offseason = bool(in_offseason)

            # Commit the transaction - WAL mode should prevent locking
            session.commit()
            logger.debug(f"Saved simulation state: Season {current_season}, Week {current_week}, Active: {is_active}")
        except Exception as e:
            logger.debug(f"Could not save simulation state (will retry later): {e}")
            # Don't rollback or log error - state will be saved at next opportunity
            pass
    
    async def _onSeasonStateUpdate(self, current_season: int, current_week: int, 
                                   in_playoffs: bool, playoff_round: Optional[str] = None) -> None:
        """Callback from SeasonManager when state changes (e.g., week completes)"""
        gameState = self.serviceContainer.getService('game_state')
        totalSeasons = gameState.getState('totalSeasons', 0)
        
        # Save updated state to database
        self._saveSimulationState(
            current_season=current_season,
            current_week=current_week,
            in_playoffs=in_playoffs,
            total_seasons=totalSeasons,
            is_active=True,
            playoff_round=playoff_round
        )
        logger.debug(f"State updated: S{current_season}W{current_week} (Playoffs: {in_playoffs})")
    
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
        simState = self._loadSimulationState()
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
            'simulationState': simState,
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