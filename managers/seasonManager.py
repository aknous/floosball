"""
SeasonManager - Manages season simulation, scheduling, and progression
Replaces the scattered season-related functions and global variables from floosball.py
"""

import math
import os
import json
import traceback
from typing import List, Dict, Any, Optional, Tuple
import asyncio
import datetime
import floosball_team as FloosTeam
import floosball_player as FloosPlayer
import floosball_game as FloosGame
from logger_config import get_logger
from .timingManager import TimingManager, TimingMode

# Database imports
try:
    from database.config import USE_DATABASE
    from database.connection import get_session
    from database import repositories
    from database.models import Game as DBGame, GamePlayerStats as DBGamePlayerStats
    DB_IMPORTS_AVAILABLE = True
except ImportError:
    USE_DATABASE = False
    DB_IMPORTS_AVAILABLE = False
    DBGame = None
    DBGamePlayerStats = None
    repositories = None
    get_session = None

# WebSocket broadcasting support (optional)
try:
    from api.game_broadcaster import broadcaster
    from api.event_models import SeasonEvent, StandingsEvent, LeagueNewsEvent, OffseasonEvent
    from api_response_builders import LeagueResponseBuilder
    BROADCASTING_AVAILABLE = True
except ImportError:
    BROADCASTING_AVAILABLE = False
    broadcaster = None
    SeasonEvent = None
    StandingsEvent = None
    LeagueNewsEvent = None
    OffseasonEvent = None
    LeagueResponseBuilder = None

logger = get_logger("floosball.seasonManager")

class Season:
    """Represents a single season"""
    
    def __init__(self, seasonNumber: int):
        self.seasonNumber = seasonNumber
        self.currentSeason = seasonNumber  # Backward compatibility
        self.currentWeek = 0
        self.currentWeekText = None
        self.startDate: datetime.datetime = datetime.datetime.utcnow()
        self.activeGames = None
        self.completedWeekGames = None  # Finished games kept for display until next week
        self.schedule: List[Dict[str, FloosGame.Game]] = []
        self.playoffBracket: List[Dict[str, Any]] = []
        self.isComplete = False
        self.champion: Optional[FloosTeam.Team] = None
        self.leagueChampions: Dict[str, FloosTeam.Team] = {}
        self.playoffTeams: Dict[str, List[FloosTeam.Team]] = {}
        self.nonPlayoffTeams: Dict[str, List[FloosTeam.Team]] = {}
        self.leagueHighlights: List[Dict[str, Any]] = []
        self.freeAgencyOrder: List[FloosTeam.Team] = []
        self.mvp: Optional[Dict[str, Any]] = None
        self.allProPlayerIds: set = set()

class SeasonManager:
    """Manages season simulation, scheduling, and progression"""
    
    def __init__(self, serviceContainer, leagueManager, playerManager, recordsManager):
        self.serviceContainer = serviceContainer
        self.leagueManager = leagueManager
        self.playerManager = playerManager
        self.recordsManager = recordsManager
        
        self.currentSeason: Optional[Season] = None
        self.seasonHistory: List[Season] = []
        
        # Callback for state updates (set by application)
        self.stateUpdateCallback = None
        
        # Database support
        self.db_session = None
        self.game_repo = None
        
        if DB_IMPORTS_AVAILABLE and USE_DATABASE:
            self.db_session = get_session()
            self.game_repo = repositories.GameRepository(self.db_session)
            logger.info("SeasonManager using DATABASE storage")
        else:
            logger.info("SeasonManager using JSON file storage")

        # Initialize timing manager with default fast mode
        self.timingManager = TimingManager(TimingMode.FAST)
        
        # Game stats file
        self.game_stats_file = None
        
        # Track games for verbose logging
        self.games_simulated_this_season = 0
        
        # Global game counter for unique IDs across all seasons
        self._gameIdCounter = 0

        # Offseason transaction history (persists for page refresh)
        self._offseasonTransactions: list = []

        # Cached next-game-start timestamp (set once, survives page refreshes)
        self._cachedNextGameStart: Optional[datetime.datetime] = None

        logger.info("SeasonManager initialized")
    
    def setStateUpdateCallback(self, callback):
        """Set callback function for state updates"""
        self.stateUpdateCallback = callback
        logger.debug("State update callback registered")
    
    def setTimingMode(self, mode: TimingMode) -> None:
        """Set timing mode for simulation"""
        self.timingManager.setMode(mode)
        logger.info(f"Season timing mode set to {mode.value}")
    
    def setTimingModeFromString(self, mode_str: str, scheduleGap: int = 60) -> None:
        """Set timing mode from string (scheduled/sequential/turbo/fast/test-scheduled)"""
        mode_str = mode_str.lower()
        if mode_str == 'scheduled':
            self.setTimingMode(TimingMode.SCHEDULED)
        elif mode_str == 'sequential':
            self.setTimingMode(TimingMode.SEQUENTIAL)
        elif mode_str == 'turbo':
            self.setTimingMode(TimingMode.TURBO)
        elif mode_str == 'fast':
            self.setTimingMode(TimingMode.FAST)
        elif mode_str == 'demo':
            self.setTimingMode(TimingMode.DEMO)
        elif mode_str == 'test-scheduled':
            self.timingManager.scheduleGap = scheduleGap
            self.setTimingMode(TimingMode.TEST_SCHEDULED)
        else:
            logger.warning(f"Unknown timing mode '{mode_str}', using FAST")
            self.setTimingMode(TimingMode.FAST)
    
    def setCustomTimingDelays(self, delays: Dict[str, float]) -> None:
        """Set custom timing delays"""
        self.timingManager.setCustomDelays(delays)
    
    def getTimingMode(self) -> str:
        """Get current timing mode as string"""
        return self.timingManager.getModeString()
    
    async def startNewSeason(self) -> None:
        """Initialize and start a new season"""
        seasonNumber = self.serviceContainer.getService('game_state').getState('seasonsPlayed', 0) + 1
        logger.info(f"Starting season {seasonNumber}")
        
        self.currentSeason = Season(seasonNumber)
        
        # Clear previous season data
        self._clearSeasonData()

        # Create new season schedule — load from DB if resuming, otherwise generate fresh
        scheduleLoaded = False
        if DB_IMPORTS_AVAILABLE and USE_DATABASE and self.game_repo:
            if self.game_repo.has_schedule(seasonNumber):
                logger.info(f"Existing schedule found for season {seasonNumber} — loading from database")
                scheduleLoaded = self._loadScheduleFromDatabase(seasonNumber)
                if not scheduleLoaded:
                    logger.warning("Schedule load from database failed — falling back to fresh generation")
        if not scheduleLoaded:
            self.createSchedule()
        
        # Initialize season stats
        self._initializeSeasonStats()

        # Generate card templates for the new season
        self._generateCardTemplates(seasonNumber)

        logger.info(f"Season {seasonNumber} initialized with {len(self.currentSeason.schedule)} games")
    
    async def runSeasonSimulation(self, resumeFromWeek: int = 0) -> None:
        """Run full season simulation.

        Args:
            resumeFromWeek: If > 0, skip regular-season weeks up to and including this week
                            (they were already completed before a restart).
        """
        if not self.currentSeason:
            logger.error("No current season to simulate")
            return

        logger.info(f"Running simulation for season {self.currentSeason.seasonNumber}")
        
        # Reset game counter for verbose logging
        self.games_simulated_this_season = 0
        
        # Open game stats file
        self._openGameStatsFile()
        
        # Simulate regular season
        await self._simulateRegularSeason(resumeFromWeek=resumeFromWeek)

        # Select MVP and All-Pro based on regular season performance
        await self._selectSeasonMVP()
        self._selectSeasonAllPro()

        # End-of-regular-season cleanup (unequip cards, etc.)
        self._processEndOfRegularSeason()

        # Simulate playoffs
        await self._simulatePlayoffs()
        
        # Close game stats file
        self._closeGameStatsFile()
        
        # Handle season completion
        await self._completeSeasonSimulation()
        
        logger.info(f"Season {self.currentSeason.seasonNumber} simulation complete")
    
    async def _simulateRegularSeason(self, resumeFromWeek: int = 0) -> None:
        """Simulate all regular season games.

        Args:
            resumeFromWeek: Skip weeks up to and including this number (already completed).
        """
        strCurrentSeason = 'season{}'.format(self.currentSeason.seasonNumber)

        # On mid-season resume, restore accumulated stats from the DB checkpoint
        # so standings and leaderboards reflect weeks already simulated.
        if resumeFromWeek > 0:
            logger.info(f"Restoring season {self.currentSeason.seasonNumber} stats from week {resumeFromWeek} checkpoint")
            teamManager = self.serviceContainer.getService('team_manager')
            if teamManager:
                teamManager.loadSeasonTeamStats(self.currentSeason.seasonNumber)
            playerManager = self.serviceContainer.getService('player_manager')
            if playerManager:
                playerManager.loadCurrentSeasonStats(self.currentSeason.seasonNumber)
            # Clean up orphaned game data from any interrupted week
            # (the next week will replay from scratch, generating new records)
            self._cleanupOrphanedWeekGames(
                self.currentSeason.seasonNumber, resumeFromWeek + 1
            )

        for week in self.currentSeason.schedule:
            roundIndex = self.currentSeason.schedule.index(week)  # 0-indexed
            self.currentSeason.currentWeek = roundIndex + 1
            dayNum = roundIndex // 7 + 1    # 1-indexed day (1–4), used for day-boundary events
            self.currentSeason.currentWeekText = f'Week {self.currentSeason.currentWeek}'

            # Skip weeks that were completed before a restart
            if self.currentSeason.currentWeek <= resumeFromWeek:
                logger.info(f"Skipping {self.currentSeason.currentWeekText} — already completed before restart")
                continue

            logger.info(f"Simulating {self.currentSeason.currentWeekText} in {self.timingManager.getModeString()} mode")

            # Select weekly modifier
            weeklyModifier = self._selectWeeklyModifier(
                self.currentSeason.seasonNumber, self.currentSeason.currentWeek
            )



            weekStartTime = week['startTime']

            # Cache the game start time so REST API returns a stable value on refresh
            if self.timingManager._isScheduledMode:
                self._cachedNextGameStart = weekStartTime
            else:
                # Sequential/turbo: compute from delays relative to now
                delays = self.timingManager.delays
                gap = delays.get('week_start_wait', 30) + delays.get('game_announcement', 30)
                self._cachedNextGameStart = datetime.datetime.utcnow() + datetime.timedelta(seconds=gap)

            # Broadcast week start event
            if BROADCASTING_AVAILABLE and broadcaster.is_enabled():
                nextStartIso = self._cachedNextGameStart.isoformat() + 'Z' if self._cachedNextGameStart else None
                modInfo = {
                    "name": weeklyModifier,
                    "displayName": self.MODIFIER_DISPLAY.get(weeklyModifier, weeklyModifier.title()),
                    "description": self.MODIFIER_DESCRIPTIONS.get(weeklyModifier, ""),
                } if weeklyModifier else None
                week_event = SeasonEvent.weekStart(
                    seasonNumber=self.currentSeason.seasonNumber,
                    weekNumber=self.currentSeason.currentWeek,
                    games=[],
                    weekText=self.currentSeason.currentWeekText,
                    modifier=weeklyModifier,
                    modifierInfo=modInfo,
                    nextGameStartTime=nextStartIso,
                )
                broadcaster.broadcast_sync('season', week_event)
            weekSetupTime = weekStartTime - datetime.timedelta(minutes=10)
            self.currentSeason.activeGames = week['games']
            self.currentSeason.completedWeekGames = None  # Clear previous week's finished games

            # Wait for week setup time
            await self.timingManager.waitForWeekSetup(weekSetupTime)

            for game in range(0,len(self.currentSeason.activeGames)):
                self.currentSeason.activeGames[game].leagueHighlights = self.currentSeason.leagueHighlights
                self.currentSeason.activeGames[game].calculateWinProbability()

            # Add league highlight for week starting
            if hasattr(self.currentSeason, 'leagueHighlights'):
                self.currentSeason.leagueHighlights.insert(0, {
                    'event': {'text': f'{self.currentSeason.currentWeekText} Starting Soon...'}
                })

            # Wait for games to start
            await self.timingManager.waitForGamesStart(weekStartTime)

            # Clear cached countdown — games are starting now
            self._cachedNextGameStart = None

            # Auto-lock all equipped cards and unlocked rosters at game start
            try:
                from database.connection import get_session as _getSession
                from database.repositories.card_repositories import EquippedCardRepository
                from database.models import FantasyRoster
                lockSession = _getSession()
                EquippedCardRepository(lockSession).lockAllForWeek(
                    self.currentSeason.seasonNumber, self.currentSeason.currentWeek
                )
                # Auto-lock rosters that have all slots filled
                tracker = self.serviceContainer.getService('fantasy_tracker') if self.serviceContainer else None
                unlocked = lockSession.query(FantasyRoster).filter_by(
                    season=self.currentSeason.seasonNumber, is_locked=False
                ).all()
                for roster in unlocked:
                    filledSlots = {rp.slot for rp in roster.players}
                    if len(filledSlots) >= 6:
                        roster.is_locked = True
                        roster.locked_at = datetime.datetime.utcnow()
                        for rp in roster.players:
                            rp.points_at_lock = (
                                tracker.getPlayerSeasonFP(
                                    rp.player_id, self.currentSeason.seasonNumber
                                ) if tracker else 0
                            )
                        logger.info(f"Auto-locked roster for user {roster.user_id}")
                lockSession.commit()
                lockSession.close()
            except Exception as e:
                logger.error(f"Failed to auto-lock cards/rosters for week {self.currentSeason.currentWeek}: {e}")

            # Add game start highlight
            if hasattr(self.currentSeason, 'leagueHighlights'):
                self.currentSeason.leagueHighlights.insert(0, {
                    'event': {'text': f'{self.currentSeason.currentWeekText} Start'}
                })

            # Simulate games in the week concurrently (like original)
            weekGames = week['games']

            # Create tasks for all games in the week to run concurrently
            gameTasks = [self._simulateGame(game) for game in weekGames]

            # Start periodic leaderboard broadcast during games
            leaderboardTask = asyncio.ensure_future(self._broadcastLeaderboardPeriodically())

            # Wait for all games in the week to complete concurrently
            await asyncio.gather(*gameTasks)

            # Stop periodic leaderboard broadcast
            leaderboardTask.cancel()
            try:
                await leaderboardTask
            except asyncio.CancelledError:
                pass

            # Clear active games so roster swaps are unlocked between weeks.
            # Keep a reference so the API can still serve them until next week.
            self.currentSeason.completedWeekGames = self.currentSeason.activeGames
            self.currentSeason.activeGames = None

            # Notify about week completion (for state saving)
            await self._onWeekComplete(self.currentSeason.currentWeek, in_playoffs=False)

            # Note: Week game data is now stored in the database, JSON output disabled
            # gameDict = {}
            # for game_idx, game in enumerate(weekGames):
            #     strGame = f'Game {game_idx + 1}'
            #     gameResults = game.gameDict
            #     gameDict[strGame] = gameResults
            # from serializers import serialize_object
            # weekDict = serialize_object(gameDict)
            # jsonFile = open(os.path.join(weekFilePath, '{}.json'.format(self.currentSeason.currentWeekText)), "w+")
            # jsonFile.write(json.dumps(weekDict, indent=4))
            # jsonFile.close()

            # Post-week processing (matches original floosball.py lines 688-699)
            self._updateWeeklyStats()
            self._updateStandings()

            # Update player performance ratings for the week
            self._updatePlayerPerformanceRatings(self.currentSeason.currentWeek)

            # Sort players and defenses (matches original)
            self.playerManager.sortPlayersByPosition()
            teamManager = self.serviceContainer.getService('team_manager')
            if teamManager:
                teamManager.sortDefenses()

            # Update playoff picture and check for clinches (matches original)
            self.updatePlayoffPicture()
            newClinchEvents = self.checkForClinches()

            # Broadcast clinch/elimination events and award Floobits for team achievements
            from constants import CLINCH_PLAYOFF_REWARD, CLINCH_TOPSEED_REWARD
            for event in newClinchEvents:
                if BROADCASTING_AVAILABLE and broadcaster.is_enabled() and LeagueNewsEvent:
                    await broadcaster.broadcast_season_event(LeagueNewsEvent.leagueNews(event['text']))
                if event['type'] == 'clinch_playoff':
                    self._awardFavoriteTeamBonus(
                        event['teamId'], CLINCH_PLAYOFF_REWARD, 'team_clinch_playoff',
                        description=f'Favorite team clinched playoffs (Week {self.currentSeason.currentWeek})',
                        season=self.currentSeason.seasonNumber, week=self.currentSeason.currentWeek)
                elif event['type'] == 'clinch_topseed':
                    self._awardFavoriteTeamBonus(
                        event['teamId'], CLINCH_TOPSEED_REWARD, 'team_clinch_topseed',
                        description=f'Favorite team clinched #1 seed (Week {self.currentSeason.currentWeek})',
                        season=self.currentSeason.seasonNumber, week=self.currentSeason.currentWeek)

            # Broadcast standings with updated clinch/elimination flags
            # Use await directly (we're in an async method) so it fires immediately, not as a deferred task
            if BROADCASTING_AVAILABLE and broadcaster.is_enabled() and StandingsEvent and LeagueResponseBuilder:
                standingsData = []
                for league in self.leagueManager.leagues:
                    standingsData.append({
                        'name': league.name,
                        'standings': LeagueResponseBuilder.buildStandingsResponse(league.teamList)['standings']
                    })
                await broadcaster.broadcast_season_event(StandingsEvent.standingsUpdate(standings=standingsData))

            self._checkRecords()

            # Additional record checks (matches original)
            self.recordsManager.checkCareerRecords()
            self.recordsManager.checkSeasonRecords(self.currentSeason.seasonNumber)

            # Commit all games from this week to database
            if DB_IMPORTS_AVAILABLE and USE_DATABASE and self.db_session:
                try:
                    self.db_session.commit()
                    logger.debug(f"Committed {len(weekGames)} games from week {self.currentSeason.currentWeek}")
                except Exception as e:
                    logger.error(f"Failed to commit week games: {e}")
                    self.db_session.rollback()

            # Checkpoint: save team + player season stats after each week so a restart
            # can recover mid-season state without losing accumulated stats.
            self._saveTeamSeasonStatsToDatabase()
            playerManager = self.serviceContainer.getService('player_manager')
            if playerManager:
                playerManager.savePlayerData()

            # Add game end highlight
            if hasattr(self.currentSeason, 'leagueHighlights'):
                self.currentSeason.leagueHighlights.insert(0, {
                    'event': {'text': f'{self.currentSeason.currentWeekText} End'}
                })

            # Wait after week completes
            await self.timingManager.waitAfterWeek()

            # Broadcast day-boundary events after the last round of each day
            isLastRoundOfDay = (roundIndex % 7 == 6)
            if isLastRoundOfDay and BROADCASTING_AVAILABLE and broadcaster.is_enabled() and SeasonEvent:
                if dayNum < 4:
                    await broadcaster.broadcast_season_event(SeasonEvent.dayComplete(dayNum))
                else:
                    await broadcaster.broadcast_season_event(SeasonEvent.regularSeasonComplete())
    
    async def _simulatePlayoffs(self) -> None:
        """Simulate playoff games"""
        logger.info("Starting playoff simulation")
        
        
        # Simulate playoff rounds
        await self._simulatePlayoffRounds()

    async def _simulateGame(self, game: FloosGame.Game) -> None:
        """Simulate a single game"""

        try:
            # Create game instance with timing manager
            gameInstance = game

            # Track games simulated this season
            self.games_simulated_this_season += 1

            # Wire fantasy tracker callback for each player so FP generation
            # flows through FantasyTracker (updates both _weekFP and gameStatsDict)
            fantasyTracker = self.serviceContainer.getService('fantasy_tracker')
            if fantasyTracker:
                for team in [gameInstance.homeTeam, gameInstance.awayTeam]:
                    for player in team.rosterDict.values():
                        if player:
                            pid = player.id
                            player.stat_tracker._on_fantasy_points = (
                                lambda pts, _pid=pid: fantasyTracker.addPlayerPoints(_pid, pts)
                            )

            # Simulate the game
            await gameInstance.playGame()

            # Clear fantasy tracker callbacks after game
            if fantasyTracker:
                for team in [gameInstance.homeTeam, gameInstance.awayTeam]:
                    for player in team.rosterDict.values():
                        if player:
                            player.stat_tracker._on_fantasy_points = None

            # Save game to database. Note: gameStatsDict['fantasyPoints'] is already
            # zeroed by _accumulatePostgameStats inside playGame(), but each player's
            # _lastGameFantasyPoints preserves the value for DB persistence.
            if DB_IMPORTS_AVAILABLE and USE_DATABASE and self.game_repo:
                self._saveGameToDatabase(gameInstance)

            # Update team records
            self._updateTeamRecords(gameInstance)

            # Process post-game statistics (record-checking, team stat accumulation)
            self.recordsManager.processPostGameStats(gameInstance)

            # Log detailed game stats
            self._logGameStats(gameInstance)

            # Update ELO ratings based on game result using pre-game win probability
            teamManager = self.serviceContainer.getService('team_manager')
            if teamManager and hasattr(gameInstance, 'winningTeam') and gameInstance.winningTeam:
                teamManager.updateEloAfterGame(
                    gameInstance.homeTeam,
                    gameInstance.awayTeam,
                    gameInstance.homeScore,
                    gameInstance.awayScore,
                    gameInstance.winningTeam,
                    getattr(gameInstance, 'preGameHomeWinProbability', None),
                    getattr(gameInstance, 'preGameAwayWinProbability', None)
                )

            # Broadcast standings update after ELO has been updated
            if BROADCASTING_AVAILABLE and broadcaster.is_enabled() and StandingsEvent and LeagueResponseBuilder:
                standingsData = []
                for league in self.leagueManager.leagues:
                    standingsData.append({
                        'name': league.name,
                        'standings': LeagueResponseBuilder.buildStandingsResponse(league.teamList)['standings']
                    })
                await broadcaster.broadcast_season_event(StandingsEvent.standingsUpdate(standings=standingsData))

            # Check for records
            self.recordsManager.checkPlayerGameRecords()
            self.recordsManager.checkTeamGameRecords(gameInstance)

        except Exception as e:
            logger.error(
                f"Error simulating game ({game.homeTeam.name} vs {game.awayTeam.name}): {e}\n"
                + traceback.format_exc()
            )
            # Force-finish the game so it doesn't stay stuck as "Live" forever
            if getattr(game, 'status', None) != FloosGame.GameStatus.Final:
                game.status = FloosGame.GameStatus.Final
                if not getattr(game, 'winningTeam', None):
                    if game.homeScore > game.awayScore:
                        game.winningTeam = game.homeTeam
                        game.losingTeam = game.awayTeam
                    elif game.awayScore > game.homeScore:
                        game.winningTeam = game.awayTeam
                        game.losingTeam = game.homeTeam
                    else:
                        game.winningTeam = game.homeTeam
                        game.losingTeam = game.awayTeam
                try:
                    # Update season win/loss records (normally done inside playGame())
                    if getattr(game, 'isRegularSeasonGame', False) and getattr(game, 'winningTeam', None):
                        game.winningTeam.seasonTeamStats.setdefault('wins', 0)
                        game.losingTeam.seasonTeamStats.setdefault('losses', 0)
                        game.winningTeam.seasonTeamStats['wins'] += 1
                        game.losingTeam.seasonTeamStats['losses'] += 1
                    self._updateTeamRecords(game)
                except Exception as recordErr:
                    logger.warning(f"Failed to update records after game error recovery: {recordErr}")

    def _openGameStatsFile(self) -> None:
        """Open file for game statistics logging"""
        try:
            filename = f"logs/game_stats_season_{self.currentSeason.seasonNumber}.txt"
            os.makedirs(os.path.dirname(filename), exist_ok=True)
            self.game_stats_file = open(filename, 'w', encoding='utf-8')
            self.game_stats_file.write(f"GAME STATISTICS - SEASON {self.currentSeason.seasonNumber}\n")
            self.game_stats_file.write(f"{'='*80}\n\n")
            logger.info(f"Opened game stats file: {filename}")
        except Exception as e:
            logger.error(f"Failed to open game stats file: {e}")
            self.game_stats_file = None
    
    def _closeGameStatsFile(self) -> None:
        """Close game statistics file"""
        try:
            if self.game_stats_file:
                self.game_stats_file.write(f"\n{'='*80}\n")
                self.game_stats_file.write(f"END OF SEASON {self.currentSeason.seasonNumber}\n")
                self.game_stats_file.close()
                self.game_stats_file = None
                logger.info("Closed game stats file")
        except Exception as e:
            logger.error(f"Failed to close game stats file: {e}")
    
    def _logGameStats(self, game: FloosGame.Game) -> None:
        """Log detailed game statistics to file"""
        if not self.game_stats_file:
            return
            
        try:
            # Get game data which calculates yards
            gameData = game.getGameData()
            homeStats = gameData['homeTeam']
            awayStats = gameData['awayTeam']
            
            # Write to file instead of logger
            f = self.game_stats_file
            
            # Basic game info
            f.write(f"\n{'='*80}\n")
            f.write(f"GAME COMPLETE: {game.awayTeam.abbr} @ {game.homeTeam.abbr}\n")
            f.write(f"FINAL SCORE: {game.awayTeam.abbr} {game.awayScore} - {game.homeTeam.abbr} {game.homeScore}\n")
            
            # Quarter scores
            f.write(f"  Q1: {game.awayScoreQ1}-{game.homeScoreQ1}  |  Q2: {game.awayScoreQ2}-{game.homeScoreQ2}  |  Q3: {game.awayScoreQ3}-{game.homeScoreQ3}  |  Q4: {game.awayScoreQ4}-{game.homeScoreQ4}")
            if game.awayScoreOT > 0 or game.homeScoreOT > 0:
                f.write(f"  |  OT: {game.awayScoreOT}-{game.homeScoreOT}")
            f.write("\n")
            
            # Team stats comparison
            f.write(f"\nTEAM STATISTICS:\n")
            f.write(f"{'Stat':<25} {game.awayTeam.abbr:>10} {game.homeTeam.abbr:>10}\n")
            f.write(f"{'-'*45}\n")
            
            # Basic game stats
            f.write(f"{'Total Plays':<25} {awayStats['totalPlays']:>10} {homeStats['totalPlays']:>10}\n")
            f.write(f"{'First Downs':<25} {awayStats['1stDowns']:>10} {homeStats['1stDowns']:>10}\n")
            f.write(f"{'Turnovers':<25} {awayStats['turnovers']:>10} {homeStats['turnovers']:>10}\n")
            
            # Offensive stats
            f.write(f"{'Pass Yards':<25} {awayStats['offense']['passYards']:>10} {homeStats['offense']['passYards']:>10}\n")
            f.write(f"{'Rush Yards':<25} {awayStats['offense']['rushYards']:>10} {homeStats['offense']['rushYards']:>10}\n")
            f.write(f"{'Total Yards':<25} {awayStats['offense']['totalYards']:>10} {homeStats['offense']['totalYards']:>10}\n")
            f.write(f"{'Pass TDs':<25} {awayStats['offense']['passTds']:>10} {homeStats['offense']['passTds']:>10}\n")
            f.write(f"{'Rush TDs':<25} {awayStats['offense']['runTds']:>10} {homeStats['offense']['runTds']:>10}\n")
            f.write(f"{'Field Goals':<25} {awayStats['offense']['fgs']:>10} {homeStats['offense']['fgs']:>10}\n")
            
            # Defensive stats
            f.write(f"{'Sacks':<25} {awayStats['sacks']:>10} {homeStats['sacks']:>10}\n")
            f.write(f"{'Interceptions':<25} {game.awayTeam.gameDefenseStats.get('ints', 0):>10} {game.homeTeam.gameDefenseStats.get('ints', 0):>10}\n")
            f.write(f"{'Fumbles Recovered':<25} {game.awayTeam.gameDefenseStats.get('fumRec', 0):>10} {game.homeTeam.gameDefenseStats.get('fumRec', 0):>10}\n")
            
            # Team ratings
            f.write(f"\nTEAM RATINGS:\n")
            f.write(f"{'Offense Rating':<25} {game.awayTeam.offenseRating:>10} {game.homeTeam.offenseRating:>10}\n")
            f.write(f"{'Defense Rating':<25} {game.awayTeam.defenseOverallRating:>10} {game.homeTeam.defenseOverallRating:>10}\n")
            f.write(f"{'Overall Rating':<25} {game.awayTeam.overallRating:>10} {game.homeTeam.overallRating:>10}\n")
            
            f.write(f"{'='*80}\n\n")
            
            # Flush to ensure it's written
            f.flush()
            
        except Exception as e:
            logger.error(f"Error logging game stats: {e}")
    
    async def _broadcastLeaderboardPeriodically(self, interval: int = 10):
        """Broadcast leaderboard data every `interval` seconds while games are active."""
        while True:
            await asyncio.sleep(interval)
            self._broadcastLeaderboardUpdate()

    def _broadcastLeaderboardUpdate(self):
        """Compute and broadcast current leaderboard via WebSocket."""
        if not BROADCASTING_AVAILABLE or not broadcaster.is_enabled():
            return
        try:
            from api.main import _computeLeaderboardData
            data = _computeLeaderboardData()
            event = {
                'event': 'leaderboard_update',
                'leaderboard': data.get('leaderboard', []),
                'season': data.get('season'),
                'week': self.currentSeason.currentWeek if self.currentSeason else 0,
            }
            broadcaster.broadcast_sync('season', event)
        except Exception as e:
            logger.warning(f"Leaderboard broadcast failed: {e}")
            import traceback
            logger.debug(traceback.format_exc())

    async def _onWeekComplete(self, week: int, in_playoffs: bool, playoff_round: Optional[str] = None) -> None:
        """Called after each week completes - triggers state save and card effect processing"""
        if self.stateUpdateCallback:
            await self.stateUpdateCallback(
                current_season=self.currentSeason.seasonNumber,
                current_week=week,
                in_playoffs=in_playoffs,
                playoff_round=playoff_round
            )

        # Bank FP from in-memory accumulator to WeeklyPlayerFP DB table
        fantasyTracker = self.serviceContainer.getService('fantasy_tracker')
        if fantasyTracker:
            fantasyTracker.bankWeek(self.currentSeason.seasonNumber, week)

        # Grant roster swap every week (regular season only)
        if not in_playoffs:
            self._grantRosterSwaps(self.currentSeason.seasonNumber)

        # Process card effects for this week (persists bonuses to DB)
        self._processWeekCardEffects(self.currentSeason.seasonNumber, week)

        # Award weekly leaderboard prizes (after card effects are finalized)
        if not in_playoffs:
            self._awardWeeklyLeaderboardPrizes(self.currentSeason.seasonNumber, week)

        # Unlock equipped cards now that week is over
        try:
            from database.connection import get_session as _getSession
            from database.repositories.card_repositories import EquippedCardRepository
            unlockSession = _getSession()
            EquippedCardRepository(unlockSession).unlockWeek(
                self.currentSeason.seasonNumber, week
            )
            unlockSession.commit()
            unlockSession.close()
            logger.info(f"Unlocked equipped cards for week {week}")
        except Exception as e:
            logger.error(f"Failed to unlock equipped cards for week {week}: {e}")

        # Broadcast week_end event so frontend can refresh card state
        if BROADCASTING_AVAILABLE and broadcaster.is_enabled():
            nextStart = self.getNextGameStartTime(week)
            nextStartIso = nextStart.isoformat() + 'Z' if nextStart else None
            weekEndEvent = SeasonEvent.weekEnd(
                seasonNumber=self.currentSeason.seasonNumber,
                weekNumber=week,
                results=[],
                nextGameStartTime=nextStartIso,
            )
            broadcaster.broadcast_sync('season', weekEndEvent)

        # Broadcast final leaderboard with persisted card bonuses
        self._broadcastLeaderboardUpdate()

    def _grantRosterSwaps(self, season: int) -> None:
        """Grant 1 swap to all locked rosters.
        Cap is 1 normally, 2 if user has a Champion-classified card equipped."""
        try:
            from database.connection import get_session as _getSession
            from database.models import FantasyRoster, EquippedCard, UserCard, CardTemplate
            swapSession = _getSession()
            rosters = swapSession.query(FantasyRoster).filter_by(
                season=season, is_locked=True
            ).all()
            updated = 0
            for roster in rosters:
                # Check if user has a Champion card equipped
                hasChampion = swapSession.query(EquippedCard).join(
                    UserCard, EquippedCard.user_card_id == UserCard.id
                ).join(
                    CardTemplate, UserCard.card_template_id == CardTemplate.id
                ).filter(
                    EquippedCard.user_id == roster.user_id,
                    EquippedCard.season == season,
                    CardTemplate.classification.isnot(None),
                    CardTemplate.classification.contains("champion")
                ).first() is not None
                maxSwaps = 2 if hasChampion else 1
                if roster.swaps_available < maxSwaps:
                    roster.swaps_available = min(roster.swaps_available + 1, maxSwaps)
                    updated += 1
            swapSession.commit()
            swapSession.close()
            if updated > 0:
                logger.info(f"Granted roster swap to {updated} users for season {season}")
        except Exception as e:
            logger.error(f"Failed to grant roster swaps: {e}")

    def _processWeekCardEffects(self, season: int, week: int) -> None:
        """Calculate and persist card effect bonuses for all users after a week completes."""
        try:
            from database.connection import get_session as _getSession
            from database.models import (
                FantasyRoster, FantasyRosterSwap, Game, GamePlayerStats,
                Player, User, WeeklyCardBonus, WeeklyPlayerFP
            )
            from database.repositories.card_repositories import EquippedCardRepository, CurrencyRepository
            from managers.cardEffectCalculator import calculateWeekCardBonuses, CardCalcContext
            from managers.cardEffects import _countPlayerTds, checkStreakCondition

            session = _getSession()
            try:
                equippedRepo = EquippedCardRepository(session)
                currencyRepo = CurrencyRepository(session)

                # Get all locked equipped cards for this week
                allEquipped = equippedRepo.getAllForWeek(season, week)
                if not allEquipped:
                    session.close()
                    return

                # Group by user_id
                byUser = {}
                for eq in allEquipped:
                    if not eq.locked:
                        continue
                    byUser.setdefault(eq.user_id, []).append(eq)

                # Get FP from WeeklyPlayerFP (banked by FantasyTracker)
                weekFPRows = session.query(WeeklyPlayerFP).filter_by(
                    season=season, week=week
                ).all()
                weekFPByPlayer = {row.player_id: row.fantasy_points for row in weekFPRows}

                # Get sub-stats from GamePlayerStats (for card conditionals)
                gameStats = (
                    session.query(GamePlayerStats)
                    .join(Game, GamePlayerStats.game_id == Game.id)
                    .filter(Game.season == season, Game.week == week)
                    .all()
                )

                # Build per-player stats dict (convert raw DB format to card-calc format)
                from managers.fantasyTracker import _dbStatsToCardFormat
                weekPlayerStats = {}
                for gps in gameStats:
                    weekPlayerStats[gps.player_id] = _dbStatsToCardFormat(
                        gps.passing_stats, gps.rushing_stats,
                        gps.receiving_stats, gps.kicking_stats,
                        weekFPByPlayer.get(gps.player_id, 0),
                        teamId=gps.team_id,
                    )
                for pid, fp in weekFPByPlayer.items():
                    if pid not in weekPlayerStats:
                        weekPlayerStats[pid] = _dbStatsToCardFormat(
                            {}, {}, {}, {}, fp,
                        )

                # ─── Build shared context data ───────────────────────────────

                # Team results from DB games (teamId → won)
                weekGames = session.query(Game).filter_by(season=season, week=week).all()
                teamResults = {}
                for g in weekGames:
                    if g.home_score > g.away_score:
                        teamResults[g.home_team_id] = True
                        teamResults[g.away_team_id] = False
                    elif g.away_score > g.home_score:
                        teamResults[g.away_team_id] = True
                        teamResults[g.home_team_id] = False
                    else:  # Tie
                        teamResults[g.home_team_id] = False
                        teamResults[g.away_team_id] = False

                # Build game lookup by team for opponent ELO
                teamGameMap = {}  # teamId → Game row
                for g in weekGames:
                    teamGameMap[g.home_team_id] = g
                    teamGameMap[g.away_team_id] = g

                # Player ratings and positions
                allPlayerIds = set()
                for userId, userEquipped in byUser.items():
                    roster = session.query(FantasyRoster).filter_by(
                        user_id=userId, season=season, is_locked=True
                    ).first()
                    if roster:
                        allPlayerIds.update(rp.player_id for rp in roster.players)

                playerRatingsMap = {}
                playerPositionMap = {}
                if allPlayerIds:
                    playerRows = session.query(
                        Player.id, Player.player_rating, Player.position
                    ).filter(Player.id.in_(allPlayerIds)).all()
                    for pid, rating, pos in playerRows:
                        playerRatingsMap[pid] = rating or 60
                        playerPositionMap[pid] = pos

                # Player performance ratings from live objects
                playerPerfRatings = {}
                if self.playerManager:
                    for p in self.playerManager.activePlayers:
                        perfRating = getattr(p, 'seasonPerformanceRating', 0)
                        if perfRating > 0:
                            playerPerfRatings[p.id] = perfRating

                # Game performance ratings (per-game, for Boom Week / Game Ball / Dud Insurance)
                gamePerfRatings = {}
                if self.playerManager and gameStats:
                    gamePerfRatings = self.playerManager.calculateGamePerformanceRatings(gameStats)

                # Team data from live objects (ELO, streaks, losses, playoff status)
                teamManager = self.serviceContainer.getService('team_manager')

                # Count big plays from in-memory game objects per team
                bigPlaysByTeam = {}
                if self.currentSeason and self.currentSeason.activeGames:
                    for game in self.currentSeason.activeGames:
                        homeId = getattr(game, 'homeTeam', {})
                        awayId = getattr(game, 'awayTeam', {})
                        if hasattr(homeId, 'id'):
                            homeId = homeId.id
                        if hasattr(awayId, 'id'):
                            awayId = awayId.id
                        homeCount = 0
                        awayCount = 0
                        for entry in getattr(game, 'gameFeed', []):
                            if entry.get('isBigPlay'):
                                # Count for both teams since we can't easily tell which
                                homeCount += 1
                                awayCount += 1
                        bigPlaysByTeam[homeId] = bigPlaysByTeam.get(homeId, 0) + homeCount
                        bigPlaysByTeam[awayId] = bigPlaysByTeam.get(awayId, 0) + awayCount

                # ─── Get weekly modifier ──────────────────────────────────────
                activeModifier = ""
                try:
                    from database.models import WeeklyModifier
                    modRow = session.query(WeeklyModifier).filter_by(
                        season=season, week=week
                    ).first()
                    if modRow:
                        activeModifier = modRow.modifier
                except Exception:
                    pass

                # ─── Process each user ───────────────────────────────────────
                for userId, userEquipped in byUser.items():
                    roster = session.query(FantasyRoster).filter_by(
                        user_id=userId, season=season, is_locked=True
                    ).first()
                    if not roster:
                        continue

                    rosterPlayerIds = {rp.player_id for rp in roster.players}

                    # Compute user's raw weekly FP and TDs
                    weekRawFP = 0.0
                    rosterTotalTds = 0
                    for rp in roster.players:
                        pStats = weekPlayerStats.get(rp.player_id, {})
                        weekRawFP += pStats.get("fantasyPoints", 0)
                        rosterTotalTds += _countPlayerTds(pStats)

                    rosterPlayerRatings = {
                        pid: playerRatingsMap.get(pid, 60) for pid in rosterPlayerIds
                    }
                    rosterPlayerPositions = {
                        pid: playerPositionMap.get(pid, 0) for pid in rosterPlayerIds
                    }

                    # Build team IDs and names for roster players
                    rosterPlayerTeamIds = {}
                    rosterPlayerNames = {}
                    for pid in rosterPlayerIds:
                        ps = weekPlayerStats.get(pid, {})
                        teamId = ps.get("teamId")
                        if teamId:
                            rosterPlayerTeamIds[pid] = teamId
                    if self.playerManager:
                        for pid in rosterPlayerIds:
                            player = self.playerManager.getPlayerById(pid)
                            if player:
                                rosterPlayerNames[pid] = player.name
                                if pid not in rosterPlayerTeamIds and hasattr(player, 'team') and hasattr(player.team, 'id'):
                                    rosterPlayerTeamIds[pid] = player.team.id

                    streakCounts = {
                        eq.id: getattr(eq, 'streak_count', 1) for eq in userEquipped
                    }

                    # User's favorite team data
                    userRow = session.get(User, userId)
                    userFavoriteTeamId = userRow.favorite_team_id if userRow else None

                    favoriteTeamElo = 1500.0
                    favoriteTeamStreak = 0
                    favoriteTeamPriorStreak = 0
                    favoriteTeamSeasonLosses = 0
                    favoriteTeamInPlayoffs = False
                    favoriteTeamWonThisWeek = False
                    favoriteTeamOpponentElo = 1500.0
                    favoriteTeamBigPlays = 0
                    favoriteTeamGameFinal = False

                    if userFavoriteTeamId and teamManager:
                        favTeam = teamManager.getTeamById(userFavoriteTeamId)
                        if favTeam:
                            favoriteTeamElo = getattr(favTeam, 'elo', 1500.0)
                            favStats = getattr(favTeam, 'seasonTeamStats', {})
                            favoriteTeamStreak = favStats.get('streak', 0)
                            favoriteTeamPriorStreak = favStats.get('priorStreak', 0)
                            favoriteTeamSeasonLosses = favStats.get('losses', 0)
                            favoriteTeamWonThisWeek = teamResults.get(userFavoriteTeamId, False)
                            favoriteTeamBigPlays = bigPlaysByTeam.get(userFavoriteTeamId, 0)

                            # Playoff status: check if team is in top 6 of its league
                            if self.leagueManager:
                                teamLeague = self.leagueManager.getTeamLeague(favTeam)
                                if teamLeague:
                                    standings = teamLeague.getStandings()
                                    for idx, entry in enumerate(standings):
                                        if entry['team'] == favTeam:
                                            favoriteTeamInPlayoffs = idx < 6
                                            break

                            # Opponent ELO from this week's game
                            favGame = teamGameMap.get(userFavoriteTeamId)
                            if favGame:
                                if favGame.home_team_id == userFavoriteTeamId:
                                    oppTeam = teamManager.getTeamById(favGame.away_team_id)
                                else:
                                    oppTeam = teamManager.getTeamById(favGame.home_team_id)
                                if oppTeam:
                                    favoriteTeamOpponentElo = getattr(oppTeam, 'elo', 1500.0)
                                # Week is complete — all games are final
                                favoriteTeamGameFinal = True

                    # League average ELO
                    leagueAverageElo = 1500.0
                    if teamManager:
                        allTeams = teamManager.teams
                        if allTeams:
                            leagueAverageElo = sum(getattr(t, 'elo', 1500.0) for t in allTeams) / len(allTeams)

                    # Roster unchanged weeks (from swap history)
                    lastSwap = (
                        session.query(FantasyRosterSwap.swap_week)
                        .filter_by(roster_id=roster.id)
                        .order_by(FantasyRosterSwap.swap_week.desc())
                        .first()
                    )
                    rosterUnchangedWeeks = week if not lastSwap else max(0, week - lastSwap[0])

                    # Check for user-level modifier override (Modifier Nullifier power-up)
                    userModifier = activeModifier
                    try:
                        from database.models import UserModifierOverride
                        modOverride = session.query(UserModifierOverride).filter_by(
                            user_id=userId, season=season, week=week
                        ).first()
                        if modOverride:
                            userModifier = modOverride.override_modifier
                    except Exception:
                        pass

                    # Compute kicker season FG misses for Good Neighbor
                    kickerSeasonFgMisses = 0
                    kickerPids = [rp.player_id for rp in roster.players
                                  if playerPositionMap.get(rp.player_id) == 5]
                    if kickerPids:
                        seasonKickerStats = (
                            session.query(GamePlayerStats)
                            .join(Game, GamePlayerStats.game_id == Game.id)
                            .filter(Game.season == season, Game.week < week,
                                    GamePlayerStats.player_id.in_(kickerPids))
                            .all()
                        )
                        for ks in seasonKickerStats:
                            kStats = ks.kicking_stats or {}
                            if isinstance(kStats, str):
                                import json as _jsonk
                                kStats = _jsonk.loads(kStats)
                            kickerSeasonFgMisses += kStats.get("fg_missed", 0)

                    # Compute chanceBonus from Fortune's Favor + fortunate modifier
                    chanceBonus = 0.0
                    if userModifier == "fortunate":
                        chanceBonus += 0.15
                    try:
                        from database.repositories.shop_repository import ShopPurchaseRepository
                        shopRepo = ShopPurchaseRepository(session)
                        if hasattr(shopRepo, 'getActiveFortunesFavor') and shopRepo.getActiveFortunesFavor(userId, season, week):
                            chanceBonus += 0.10
                    except Exception:
                        pass

                    # Build context
                    calcCtx = CardCalcContext(
                        userId=userId,
                        season=season,
                        weekNumber=week,
                        chanceBonus=chanceBonus,
                        kickerSeasonFgMisses=kickerSeasonFgMisses,
                        rosterPlayerIds=rosterPlayerIds,
                        weekPlayerStats=weekPlayerStats,
                        weekRawFP=weekRawFP,
                        rosterPlayerRatings=rosterPlayerRatings,
                        rosterTotalTds=rosterTotalTds,
                        rosterPlayerPositions=rosterPlayerPositions,
                        streakCounts=streakCounts,
                        userFavoriteTeamId=userFavoriteTeamId,
                        favoriteTeamElo=favoriteTeamElo,
                        leagueAverageElo=leagueAverageElo,
                        favoriteTeamStreak=favoriteTeamStreak,
                        favoriteTeamPriorStreak=favoriteTeamPriorStreak,
                        favoriteTeamSeasonLosses=favoriteTeamSeasonLosses,
                        favoriteTeamInPlayoffs=favoriteTeamInPlayoffs,
                        favoriteTeamWonThisWeek=favoriteTeamWonThisWeek,
                        favoriteTeamOpponentElo=favoriteTeamOpponentElo,
                        favoriteTeamBigPlays=favoriteTeamBigPlays,
                        favoriteTeamGameFinal=favoriteTeamGameFinal,
                        rosterUnchangedWeeks=rosterUnchangedWeeks,
                        teamResults=teamResults,
                        playerPerformanceRatings=playerPerfRatings,
                        gamePerformanceRatings=gamePerfRatings,
                        rosterPlayerTeamIds=rosterPlayerTeamIds,
                        rosterPlayerNames=rosterPlayerNames,
                        activeModifier=userModifier,
                        unusedSwaps=(roster.swaps_available or 0) + (roster.purchased_swaps or 0),
                    )

                    # Calculate card bonuses
                    result = calculateWeekCardBonuses(userEquipped, calcCtx)

                    # Formula: (rosterFP + Σ flat FP) × FPx₁ × FPx₂ × ...
                    baseFP = weekRawFP + result.totalBonusFP
                    multProduct = 1.0
                    for f in result.multFactors:
                        multProduct *= f
                    totalFP = round(baseFP * multProduct, 2)
                    # Subtract raw FP so we store only the card bonus portion
                    totalFP = round(totalFP - weekRawFP, 2)
                    if totalFP < 0:
                        totalFP = 0.0

                    # Persist FP bonus
                    if totalFP > 0 or result.floobitsEarned > 0:
                        if totalFP > 0:
                            roster.card_bonus_points = (roster.card_bonus_points or 0) + totalFP
                        import json as _json
                        breakdownDicts = [{
                            "slotNumber": b.slotNumber,
                            "edition": b.edition,
                            "playerId": b.playerId,
                            "playerName": b.playerName,
                            "effectName": b.effectName,
                            "displayName": b.displayName,
                            "detail": b.detail,
                            "category": b.category,
                            "outputType": b.outputType,
                            "primaryFP": b.primaryFP,
                            "primaryMult": b.primaryMult,
                            "primaryFloobits": b.primaryFloobits,
                            "matchMultiplied": b.matchMultiplied,
                            "matchMultiplier": b.matchMultiplier,
                            "preMatchFP": b.preMatchFP,
                            "preMatchFloobits": b.preMatchFloobits,
                            "conditionalBonus": b.conditionalBonus,
                            "conditionalLabel": b.conditionalLabel,
                            "secondaryFP": b.secondaryFP,
                            "secondaryFloobits": b.secondaryFloobits,
                            "secondaryMult": b.secondaryMult,
                            "totalFP": b.totalFP,
                            "floobitsEarned": b.floobitsEarned,
                            "playerStatLine": b.playerStatLine,
                            "equation": b.equation,
                            "isChanceEffect": b.isChanceEffect,
                            "chanceRoll": b.chanceRoll,
                            "chanceThreshold": b.chanceThreshold,
                            "chanceTriggered": b.chanceTriggered,
                        } for b in result.cardBreakdowns]
                        storedJson = _json.dumps({
                            "breakdowns": breakdownDicts,
                            "equationSummary": {
                                "weekRawFP": round(weekRawFP, 1),
                                "totalBonusFP": round(result.totalBonusFP, 2),
                                "multFactors": [round(f, 2) for f in result.multFactors],
                            },
                        })
                        weekBonus = WeeklyCardBonus(
                            roster_id=roster.id,
                            user_id=userId,
                            season=season,
                            week=week,
                            bonus_fp=totalFP,
                            breakdowns_json=storedJson,
                        )
                        session.add(weekBonus)
                        logger.info(
                            f"Card bonus for user {userId} week {week}: "
                            f"+{totalFP:.2f} FP (total: {roster.card_bonus_points:.2f})"
                        )

                    # Credit Floobits from cards
                    if result.floobitsEarned > 0:
                        cardNames = ", ".join(
                            b.displayName for b in result.cardBreakdowns if b.floobitsEarned > 0
                        )
                        currencyRepo.addFunds(
                            userId, result.floobitsEarned, "card_effect",
                            description=f"Week {week} card earnings ({cardNames})",
                            season=season, week=week,
                        )
                        logger.info(
                            f"Card Floobits for user {userId} week {week}: "
                            f"+{result.floobitsEarned} Floobits"
                        )

                    # ─── Streak management ──────────────────────────────────
                    for eq in userEquipped:
                        effectConfig = eq.user_card.card_template.effect_config or {}
                        effectName = effectConfig.get("effectName", "")
                        category = effectConfig.get("category", "")

                        if category == "streak":
                            from managers.cardEffects import STREAK_CONFIGS
                            # Ironclad modifier: streaks can't reset this week
                            if activeModifier == "ironclad":
                                conditionMet = True
                            else:
                                conditionMet = checkStreakCondition(
                                    effectName, calcCtx, eq.user_card.card_template.player_id
                                )
                            if conditionMet:
                                eq.streak_count = getattr(eq, 'streak_count', 0) + 1
                            elif not STREAK_CONFIGS.get(effectName, {}).get("noReset", False):
                                eq.streak_count = 0
                            # If noReset=True and condition not met, streak stays unchanged

                session.commit()
            except Exception as e:
                session.rollback()
                logger.error(f"Error processing week card effects: {e}")
                import traceback
                logger.debug(traceback.format_exc())
            finally:
                session.close()
        except ImportError as e:
            logger.warning(f"Card effect processing unavailable: {e}")

    def _applyGameStatsToRow(self, dbRow, gameStatsDict: dict) -> None:
        """Copy team stat totals from gameDict['gameStats'] into a DB Game row."""
        if not gameStatsDict:
            return
        hOff = gameStatsDict.get('homeTeam', {}).get('offense', {})
        hDef = gameStatsDict.get('homeTeam', {}).get('defense', {})
        aOff = gameStatsDict.get('awayTeam', {}).get('offense', {})
        aDef = gameStatsDict.get('awayTeam', {}).get('defense', {})

        dbRow.home_rush_yards = hOff.get('rushYards')
        dbRow.home_pass_yards = hOff.get('passYards')
        dbRow.home_rush_tds   = hOff.get('runTds')
        dbRow.home_pass_tds   = hOff.get('passTds')
        dbRow.home_fgs        = hOff.get('fgs')
        dbRow.home_sacks      = hDef.get('sacks')
        dbRow.home_ints       = hDef.get('ints')
        dbRow.home_fum_rec    = hDef.get('fumRec')

        dbRow.away_rush_yards = aOff.get('rushYards')
        dbRow.away_pass_yards = aOff.get('passYards')
        dbRow.away_rush_tds   = aOff.get('runTds')
        dbRow.away_pass_tds   = aOff.get('passTds')
        dbRow.away_fgs        = aOff.get('fgs')
        dbRow.away_sacks      = aDef.get('sacks')
        dbRow.away_ints       = aDef.get('ints')
        dbRow.away_fum_rec    = aDef.get('fumRec')

    def _cleanupOrphanedWeekGames(self, season: int, week: int) -> None:
        """Remove Game + GamePlayerStats records left behind by an interrupted week.

        When the app crashes mid-week, completed games were already saved to the DB.
        On resume the week replays from scratch, creating new records.  The old
        records must be deleted first so queries (e.g. _getFullWeekPlayerStats)
        don't return duplicate/stale data.
        """
        if not DB_IMPORTS_AVAILABLE or not USE_DATABASE:
            return
        try:
            from database.connection import get_session as _getSession
            session = _getSession()
            orphanedGames = session.query(DBGame).filter_by(
                season=season, week=week
            ).all()
            if not orphanedGames:
                session.close()
                return
            gameIds = [g.id for g in orphanedGames]
            # Delete player stats first (FK dependency)
            deleted = session.query(DBGamePlayerStats).filter(
                DBGamePlayerStats.game_id.in_(gameIds)
            ).delete(synchronize_session='fetch')
            for g in orphanedGames:
                session.delete(g)
            session.commit()
            session.close()
            logger.info(
                f"Cleaned up {len(orphanedGames)} orphaned games and "
                f"{deleted} player stat records for S{season}W{week}"
            )
        except Exception as e:
            logger.warning(f"Failed to clean up orphaned week games: {e}")

    def _saveGameToDatabase(self, game: FloosGame.Game) -> None:
        """Save a completed game to the database"""
        try:
            # If the game was pre-inserted at schedule creation time, update that row
            if getattr(game, 'dbId', None):
                db_game = self.db_session.get(DBGame, game.dbId)
                if db_game:
                    db_game.home_score = game.homeScore
                    db_game.away_score = game.awayScore
                    db_game.status = 'final'
                    db_game.is_overtime = game.isOvertimeGame if hasattr(game, 'isOvertimeGame') else False
                    db_game.is_playoff = game.isPlayoff if hasattr(game, 'isPlayoff') else False
                    db_game.playoff_round = getattr(game, 'playoffRound', None)
                    db_game.total_plays = game.totalPlays if hasattr(game, 'totalPlays') else None
                    if hasattr(game, 'homeScoresByQuarter') and game.homeScoresByQuarter:
                        if len(game.homeScoresByQuarter) > 0: db_game.home_score_q1 = game.homeScoresByQuarter[0]
                        if len(game.homeScoresByQuarter) > 1: db_game.home_score_q2 = game.homeScoresByQuarter[1]
                        if len(game.homeScoresByQuarter) > 2: db_game.home_score_q3 = game.homeScoresByQuarter[2]
                        if len(game.homeScoresByQuarter) > 3: db_game.home_score_q4 = game.homeScoresByQuarter[3]
                        if len(game.homeScoresByQuarter) > 4: db_game.home_score_ot = sum(game.homeScoresByQuarter[4:])
                    if hasattr(game, 'awayScoresByQuarter') and game.awayScoresByQuarter:
                        if len(game.awayScoresByQuarter) > 0: db_game.away_score_q1 = game.awayScoresByQuarter[0]
                        if len(game.awayScoresByQuarter) > 1: db_game.away_score_q2 = game.awayScoresByQuarter[1]
                        if len(game.awayScoresByQuarter) > 2: db_game.away_score_q3 = game.awayScoresByQuarter[2]
                        if len(game.awayScoresByQuarter) > 3: db_game.away_score_q4 = game.awayScoresByQuarter[3]
                        if len(game.awayScoresByQuarter) > 4: db_game.away_score_ot = sum(game.awayScoresByQuarter[4:])
                    self._applyGameStatsToRow(db_game, game.gameDict.get('gameStats'))
                    self.db_session.flush()
                    playerStats = self._extractPlayerStatsFromGame(game)
                    if playerStats:
                        self._savePlayerGameStats(db_game.id, playerStats)
                    self.db_session.flush()
                    logger.debug(f"Updated game in database: {game.awayTeam.abbr} @ {game.homeTeam.abbr}, Score: {game.awayScore}-{game.homeScore}")
                    return

            # No pre-existing row — fall through to INSERT (playoff games and backward compat)
            # Create database game record
            db_game = DBGame(
                season=self.currentSeason.seasonNumber,
                week=self.currentSeason.currentWeek,
                home_team_id=game.homeTeam.id,
                away_team_id=game.awayTeam.id,
                home_score=game.homeScore,
                away_score=game.awayScore,
                is_overtime=game.isOvertimeGame if hasattr(game, 'isOvertimeGame') else False,
                is_playoff=game.isPlayoff if hasattr(game, 'isPlayoff') else False,
                playoff_round=getattr(game, 'playoffRound', None),
                total_plays=game.totalPlays if hasattr(game, 'totalPlays') else None,
                status='final',
            )
            
            # Save quarter scores if available
            if hasattr(game, 'homeScoresByQuarter') and game.homeScoresByQuarter:
                if len(game.homeScoresByQuarter) > 0:
                    db_game.home_score_q1 = game.homeScoresByQuarter[0]
                if len(game.homeScoresByQuarter) > 1:
                    db_game.home_score_q2 = game.homeScoresByQuarter[1]
                if len(game.homeScoresByQuarter) > 2:
                    db_game.home_score_q3 = game.homeScoresByQuarter[2]
                if len(game.homeScoresByQuarter) > 3:
                    db_game.home_score_q4 = game.homeScoresByQuarter[3]
                if len(game.homeScoresByQuarter) > 4:
                    db_game.home_score_ot = sum(game.homeScoresByQuarter[4:])
            
            if hasattr(game, 'awayScoresByQuarter') and game.awayScoresByQuarter:
                if len(game.awayScoresByQuarter) > 0:
                    db_game.away_score_q1 = game.awayScoresByQuarter[0]
                if len(game.awayScoresByQuarter) > 1:
                    db_game.away_score_q2 = game.awayScoresByQuarter[1]
                if len(game.awayScoresByQuarter) > 2:
                    db_game.away_score_q3 = game.awayScoresByQuarter[2]
                if len(game.awayScoresByQuarter) > 3:
                    db_game.away_score_q4 = game.awayScoresByQuarter[3]
                if len(game.awayScoresByQuarter) > 4:
                    db_game.away_score_ot = sum(game.awayScoresByQuarter[4:])
            
            self._applyGameStatsToRow(db_game, game.gameDict.get('gameStats'))
            self.game_repo.save(db_game)
            self.db_session.flush()  # Get the ID

            # Save player stats from game rosters
            playerStats = self._extractPlayerStatsFromGame(game)
            if playerStats:
                self._savePlayerGameStats(db_game.id, playerStats)
            
            # Don't commit yet - will batch commit at end of week
            self.db_session.flush()  # Flush to get IDs but don't commit
            logger.debug(f"Saved game to database: {game.awayTeam.abbr} @ {game.homeTeam.abbr}, Score: {game.awayScore}-{game.homeScore}")
            
        except Exception as e:
            logger.error(f"Failed to save game to database: {e}")
            self.db_session.rollback()
    
    def _extractPlayerStatsFromGame(self, game) -> Dict:
        """Extract per-player game stats from a Game object's team rosters."""
        playerStats = {}
        for team in [game.homeTeam, game.awayTeam]:
            if not hasattr(team, 'rosterDict'):
                continue
            for player in team.rosterDict.values():
                if not player or not hasattr(player, 'gameStatsDict'):
                    continue
                gd = player.gameStatsDict
                # Only include players who actually participated
                hasStats = (
                    gd.get('passing', {}).get('att', 0) > 0
                    or gd.get('rushing', {}).get('carries', 0) > 0
                    or gd.get('receiving', {}).get('targets', 0) > 0
                    or gd.get('kicking', {}).get('fgAtt', 0) > 0
                    or gd.get('kicking', {}).get('xpAtt', 0) > 0
                    or gd.get('fantasyPoints', 0) != 0
                )
                if hasStats:
                    # _accumulatePostgameStats zeroes gd['fantasyPoints'] inside
                    # playGame(), so by the time we get here it's 0.  Use the
                    # preserved value stashed on the player object instead.
                    gameFP = getattr(player, '_lastGameFantasyPoints', None)
                    if gameFP is None:
                        gameFP = gd.get('fantasyPoints', 0)
                    playerStats[player.id] = {
                        'teamId': team.id,
                        'fantasyPoints': gameFP,
                        'passing': gd.get('passing'),
                        'rushing': gd.get('rushing'),
                        'receiving': gd.get('receiving'),
                        'kicking': gd.get('kicking'),
                    }
        return playerStats

    def _savePlayerGameStats(self, game_id: int, player_stats: Dict) -> None:
        """Save player game statistics to database"""
        try:
            for player_id, stats in player_stats.items():
                if isinstance(stats, dict):
                    db_stats = DBGamePlayerStats(
                        game_id=game_id,
                        player_id=player_id,
                        team_id=stats.get('teamId', 0),
                        fantasy_points=stats.get('fantasyPoints', 0),
                        passing_stats=stats.get('passing'),
                        rushing_stats=stats.get('rushing'),
                        receiving_stats=stats.get('receiving'),
                        kicking_stats=stats.get('kicking'),
                        defense_stats=stats.get('defense'),
                    )
                    self.game_repo.save_player_stats(db_stats)
        except Exception as e:
            logger.error(f"Failed to save player game stats: {e}")
    
    def _updateTeamRecords(self, game) -> None:
        """Update team win/loss records"""
        try:
            homeTeam = game.homeTeam
            awayTeam = game.awayTeam
            
            # Check if game has score attributes
            if not hasattr(game, 'homeScore') or not hasattr(game, 'awayScore'):
                logger.error(f"Game object missing score attributes: {dir(game)}")
                return
                
            # Initialize season stats if needed
            if not hasattr(homeTeam, 'seasonTeamStats'):
                homeTeam.seasonTeamStats = {'wins': 0, 'losses': 0}
            if not hasattr(awayTeam, 'seasonTeamStats'):
                awayTeam.seasonTeamStats = {'wins': 0, 'losses': 0}
            
            # Ensure stats are initialized
            homeTeam.seasonTeamStats.setdefault('wins', 0)
            homeTeam.seasonTeamStats.setdefault('losses', 0)
            awayTeam.seasonTeamStats.setdefault('wins', 0)
            awayTeam.seasonTeamStats.setdefault('losses', 0)
        
            
            # Update all-time records
            if not hasattr(homeTeam, 'allTimeTeamStats'):
                homeTeam.allTimeTeamStats = {'wins': 0, 'losses': 0}
            if not hasattr(awayTeam, 'allTimeTeamStats'):
                awayTeam.allTimeTeamStats = {'wins': 0, 'losses': 0}
                
            if game.homeScore > game.awayScore:
                homeTeam.allTimeTeamStats['wins'] += 1
                awayTeam.allTimeTeamStats['losses'] += 1
            else:
                awayTeam.allTimeTeamStats['wins'] += 1
                homeTeam.allTimeTeamStats['losses'] += 1
                
        except Exception as e:
            logger.error(f"Error updating team records: {e}")
            logger.error(f"Game attributes: {dir(game) if hasattr(game, '__dict__') else 'No __dict__'}")
    
    def createSchedule(self) -> None:
        """Generate season schedule (matches original floosball.py algorithm)"""
        import floosball_team as FloosTeam
        if not self.currentSeason:
            return
            
        logger.info("Creating season schedule using original algorithm")
        
        # Ensure we have exactly 2 leagues (original assumption)
        if len(self.leagueManager.leagues) != 2:
            logger.error(f"Original algorithm expects exactly 2 leagues, found {len(self.leagueManager.leagues)}")
            return
            
        # Generate full season schedule using original algorithm
        schedule = self._generateSchedule()
        self.currentSeason.schedule.clear()
        dateTimeNow = datetime.datetime.utcnow()

        # Calculate number of weeks (original formula)
        numOfWeeks = int(((len(self.leagueManager.leagues[0].teamList) - 1) * 2) + (len(self.leagueManager.leagues[0].teamList) / 2))
        
        # Convert generated schedule to our current season format
        for week in range(numOfWeeks):
            if week < len(schedule):
                gameList = []
                weekGames = schedule[week]
                numOfGames = len(weekGames)
                weekStartTime = self.getWeekStartTime(dateTimeNow, week)
                for x in range(numOfGames):
                    game = weekGames[x]
                    homeTeam: FloosTeam.Team = game[0] 
                    awayTeam: FloosTeam.Team = game[1]
                    newGame: FloosGame.Game = FloosGame.Game(homeTeam=homeTeam, awayTeam=awayTeam, timingManager=self.timingManager)
                    
                    # Assign unique integer ID and metadata
                    self._gameIdCounter += 1
                    newGame.id = self._gameIdCounter
                    newGame.seasonNumber = self.currentSeason.seasonNumber
                    newGame.week = week
                    newGame.gameNumber = x
                    newGame.gameType = 'regular'
                    
                    newGame.status = FloosGame.GameStatus.Scheduled
                    newGame.isRegularSeasonGame = True
                    newGame.startTime = weekStartTime

                    # Persist scheduled game to DB immediately so resume can reconstruct the schedule
                    if DB_IMPORTS_AVAILABLE and USE_DATABASE and self.game_repo:
                        dbRow = DBGame(
                            season=self.currentSeason.seasonNumber,
                            week=week + 1,  # store 1-indexed
                            home_team_id=homeTeam.id,
                            away_team_id=awayTeam.id,
                            game_date=weekStartTime,
                            status='scheduled',
                        )
                        self.game_repo.save(dbRow)
                        self.db_session.flush()
                        newGame.dbId = dbRow.id

                    homeTeam.schedule.append(newGame)
                    awayTeam.schedule.append(newGame)
                    gameList.append(newGame)
                self.currentSeason.schedule.append({'startTime': weekStartTime, 'games': gameList})

        if DB_IMPORTS_AVAILABLE and USE_DATABASE and self.game_repo:
            try:
                self.db_session.commit()
                logger.debug(f"Persisted {numOfWeeks}-week schedule to database")
            except Exception as e:
                logger.error(f"Failed to persist schedule to database: {e}")
                self.db_session.rollback()

        logger.info(f"Created {numOfWeeks}-week schedule with {len(self.currentSeason.schedule)} games")

    def _loadScheduleFromDatabase(self, seasonNumber: int) -> bool:
        """Reconstruct in-memory schedule from persisted DB rows.

        Returns True if the schedule was successfully loaded, False if it should
        fall back to fresh schedule generation.
        """
        if not (DB_IMPORTS_AVAILABLE and USE_DATABASE and self.game_repo):
            return False

        rows = self.game_repo.get_by_season_ordered(seasonNumber)
        if not rows:
            return False

        teamManager = self.serviceContainer.getService('team_manager')
        if not teamManager:
            logger.error("TeamManager not available for schedule reconstruction")
            return False

        teamById = {t.id: t for t in teamManager.teams}
        now = datetime.datetime.utcnow()
        weekMap: Dict[int, Dict] = {}  # 1-indexed week → {startTime, games}

        for row in rows:
            homeTeam = teamById.get(row.home_team_id)
            awayTeam = teamById.get(row.away_team_id)
            if not homeTeam or not awayTeam:
                logger.error(f"Team not found for DB game id={row.id} "
                             f"(home={row.home_team_id}, away={row.away_team_id}); aborting schedule load")
                return False

            self._gameIdCounter += 1
            newGame = FloosGame.Game(homeTeam=homeTeam, awayTeam=awayTeam,
                                     timingManager=self.timingManager)
            newGame.id = self._gameIdCounter
            newGame.dbId = row.id
            newGame.seasonNumber = seasonNumber
            newGame.week = row.week - 1   # 0-indexed (matches original createSchedule convention)
            newGame.gameType = 'playoff' if row.is_playoff else 'regular'
            newGame.isRegularSeasonGame = not row.is_playoff
            newGame.status = (FloosGame.GameStatus.Final if row.status == 'final'
                              else FloosGame.GameStatus.Scheduled)

            # Use stored game_date if present; otherwise compute from current time
            weekIdx = row.week - 1
            startTime = row.game_date if row.game_date else self.getWeekStartTime(now, weekIdx)
            newGame.startTime = startTime

            # Reconstruct minimal gameDict['gameStats'] from stored columns so
            # getAverages() can include this game when calculating season averages.
            if row.status == 'final' and row.home_rush_yards is not None:
                hRushYds = row.home_rush_yards or 0
                hPassYds = row.home_pass_yards or 0
                aRushYds = row.away_rush_yards or 0
                aPassYds = row.away_pass_yards or 0
                hRushTds = row.home_rush_tds or 0
                hPassTds = row.home_pass_tds or 0
                aRushTds = row.away_rush_tds or 0
                aPassTds = row.away_pass_tds or 0
                newGame.gameDict['gameStats'] = {
                    'homeTeam': {
                        'offense': {
                            'rushYards': hRushYds, 'passYards': hPassYds,
                            'totalYards': hRushYds + hPassYds,
                            'runTds': hRushTds, 'passTds': hPassTds,
                            'tds': hRushTds + hPassTds,
                            'fgs': row.home_fgs or 0,
                            'score': row.home_score,
                        },
                        'defense': {
                            'sacks': row.home_sacks or 0,
                            'ints': row.home_ints or 0,
                            'fumRec': row.home_fum_rec or 0,
                            'passYardsAlwd': aPassYds, 'runYardsAlwd': aRushYds,
                            'totalYardsAlwd': aRushYds + aPassYds,
                            'passTdsAlwd': aPassTds, 'runTdsAlwd': aRushTds,
                            'tdsAlwd': aRushTds + aPassTds,
                            'ptsAlwd': row.away_score,
                        },
                    },
                    'awayTeam': {
                        'offense': {
                            'rushYards': aRushYds, 'passYards': aPassYds,
                            'totalYards': aRushYds + aPassYds,
                            'runTds': aRushTds, 'passTds': aPassTds,
                            'tds': aRushTds + aPassTds,
                            'fgs': row.away_fgs or 0,
                            'score': row.away_score,
                        },
                        'defense': {
                            'sacks': row.away_sacks or 0,
                            'ints': row.away_ints or 0,
                            'fumRec': row.away_fum_rec or 0,
                            'passYardsAlwd': hPassYds, 'runYardsAlwd': hRushYds,
                            'totalYardsAlwd': hRushYds + hPassYds,
                            'passTdsAlwd': hPassTds, 'runTdsAlwd': hRushTds,
                            'tdsAlwd': hRushTds + hPassTds,
                            'ptsAlwd': row.home_score,
                        },
                    },
                }

            if row.week not in weekMap:
                weekMap[row.week] = {'startTime': startTime, 'games': []}
            weekMap[row.week]['games'].append(newGame)

            homeTeam.schedule.append(newGame)
            awayTeam.schedule.append(newGame)

        self.currentSeason.schedule = [weekMap[w] for w in sorted(weekMap)]
        logger.info(f"Loaded {len(rows)} games ({len(weekMap)} weeks) from DB for season {seasonNumber}")
        return True

    def getWeekStartTime(self, now:datetime.datetime, week:int):
        from managers.timingManager import TimingMode

        # TEST_SCHEDULED: compressed timeline — each round starts gap seconds apart
        if self.timingManager.mode == TimingMode.TEST_SCHEDULED:
            if not hasattr(self, '_testScheduleAnchor'):
                self._testScheduleAnchor = datetime.datetime.utcnow()
            gap = self.timingManager.scheduleGap
            return self._testScheduleAnchor + datetime.timedelta(seconds=week * gap)

        dateNow = datetime.datetime.now()
        dateNowUtc = datetime.datetime.utcnow()
        if dateNow.day == dateNowUtc.day:
            utcOffset = dateNowUtc.hour - dateNow.hour
        elif dateNowUtc.day > dateNow.day:
            utcOffset = (dateNowUtc.hour + 24) - dateNow.hour
        elif dateNow.day > dateNowUtc.day:
            utcOffset = dateNowUtc.hour - (dateNow.hour + 24)

        startTimeHoursList = [11, 12, 13, 14, 15, 16, 17]
        startTimeHour = startTimeHoursList[week % 7]
        adjustedHour = (startTimeHour + utcOffset) % 24

        if week > 28:
            # Playoffs: schedule relative to today (unchanged legacy logic kept intact)
            startDay = 4
            todayWeekDay = dateNowUtc.isoweekday()
            if week == 32:
                startDayOffset = 0 if todayWeekDay == startDay + 5 else (startDay + 5) - todayWeekDay
            else:
                if todayWeekDay == startDay + 5:
                    startDayOffset = startDay + 4
                elif todayWeekDay == startDay + 4:
                    startDayOffset = 0
                else:
                    startDayOffset = (startDay + 4) - todayWeekDay
            dayOffset = startDayOffset
            targetDate = (now + datetime.timedelta(days=dayOffset)).date()
        else:
            # Regular season: 28 rounds across 4 game days (7 rounds/day), anchored to
            # the season's actual start date instead of "next Thursday"
            dayNumber = math.floor(week / 7)  # 0–3
            seasonStart = self.currentSeason.startDate if self.currentSeason else now
            targetDate = (seasonStart + datetime.timedelta(days=dayNumber)).date()

        return datetime.datetime(targetDate.year, targetDate.month, targetDate.day, adjustedHour)

    def getNextGameStartTime(self, currentWeek: int) -> 'datetime.datetime | None':
        """Return the start time of the next week's games, or None if no next week.

        For SCHEDULED / TEST_SCHEDULED modes the time comes from the schedule.
        For SEQUENTIAL / TURBO modes we estimate from delay config.
        For FAST mode we return None (no meaningful wait).
        """
        from managers.timingManager import TimingMode

        if self.timingManager.mode == TimingMode.FAST:
            return None

        schedule = self.currentSeason.schedule if self.currentSeason else []
        nextIndex = currentWeek  # schedule is 0-indexed, currentWeek is 1-indexed

        if self.timingManager._isScheduledMode:
            # Look up from schedule directly
            if nextIndex < len(schedule):
                return schedule[nextIndex]['startTime']
            return None

        # SEQUENTIAL / TURBO: return cached timestamp if available
        if self._cachedNextGameStart is not None:
            return self._cachedNextGameStart

        # Compute once and cache
        delays = self.timingManager.delays
        gap = delays.get('week_end_wait', 120) + delays.get('week_start_wait', 30) + delays.get('game_announcement', 30)
        self._cachedNextGameStart = datetime.datetime.utcnow() + datetime.timedelta(seconds=gap)
        return self._cachedNextGameStart

    def _generateSchedule(self) -> List[List[tuple]]:
        """Generate full season schedule using original algorithm"""
        import random
        import copy
        
        schedule = []
        
        # Get copies of league team lists
        league1Teams = copy.copy(self.leagueManager.leagues[0].teamList)
        league2Teams = copy.copy(self.leagueManager.leagues[1].teamList)
        
        # Generate different types of games
        league1Games = self._generateIntraleagueGames(league1Teams)
        league2Games = self._generateIntraleagueGames(league2Teams)
        interleagueGames = self._generateInterleagueGames(copy.copy(league1Teams), copy.copy(league2Teams))
        
        # Combine intra-league games by week
        intraleagueGames = []
        for x in range(len(league1Games)):
            week = []
            week.extend(league1Games[x])
            week.extend(league2Games[x])
            intraleagueGames.append(week)
        
        # Combine all games and shuffle (matches original)
        schedule = interleagueGames + intraleagueGames
        random.shuffle(schedule)

        # Post-process: ensure no team plays the same opponent in consecutive weeks.
        # The double round-robin produces mirror weeks (same pairs, swapped home/away)
        # that can land adjacent after shuffling.
        schedule = self._fixBackToBackMatchups(schedule)

        return schedule
    
    def _fixBackToBackMatchups(self, schedule: List[List[tuple]]) -> List[List[tuple]]:
        """Eliminate consecutive weeks where the same two teams play each other.
        Uses restart-with-reshuffle to avoid getting stuck in swap cycles."""
        import random

        def matchupPairs(week):
            return frozenset((min(h.id, a.id), max(h.id, a.id)) for h, a in week)

        def hasConflicts(sched):
            return any(matchupPairs(sched[i]) & matchupPairs(sched[i + 1]) for i in range(len(sched) - 1))

        for _attempt in range(50):
            random.shuffle(schedule)
            n = len(schedule)
            for _ in range(50):
                changed = False
                for i in range(n - 1):
                    if matchupPairs(schedule[i]) & matchupPairs(schedule[i + 1]):
                        candidates = list(range(i + 2, n))
                        random.shuffle(candidates)
                        for j in candidates:
                            schedule[i + 1], schedule[j] = schedule[j], schedule[i + 1]
                            checkIdxs = sorted({i, i + 1, j - 1, j} & set(range(n - 1)))
                            if all(not (matchupPairs(schedule[k]) & matchupPairs(schedule[k + 1])) for k in checkIdxs):
                                changed = True
                                break
                            schedule[i + 1], schedule[j] = schedule[j], schedule[i + 1]  # revert
                if not changed:
                    break
            if not hasConflicts(schedule):
                return schedule  # clean solution found
        return schedule  # best effort after all restarts

    def _generateIntraleagueGames(self, teams: List[FloosTeam.Team]) -> List[List[tuple]]:
        """Generate intra-league games using original round-robin algorithm"""
        n = len(teams)
        tempTeams = teams.copy()
        weeks = []
        
        # First round-robin
        for week in range(n - 1):
            games = []
            for i in range(n // 2):
                if week % 2 == 0:
                    home = tempTeams[i]
                    away = tempTeams[n - 1 - i]
                    games.append((home, away))
                else:
                    home = tempTeams[n - 1 - i]
                    away = tempTeams[i]
                    games.append((home, away))
            
            weeks.append(games)
            tempTeams.insert(1, tempTeams.pop())
        
        # Second round-robin (reverse home/away)
        reverseWeeks = []
        for week in weeks:
            reverse = [(away, home) for home, away in week]
            reverseWeeks.append(reverse)
        
        weeks.extend(reverseWeeks)
        return weeks
    
    def _generateInterleagueGames(self, league1: List[FloosTeam.Team], league2: List[FloosTeam.Team]) -> List[List[tuple]]:
        """Generate inter-league games using original complex algorithm"""
        import random
        
        weeks = []
        group1Weeks = []
        group2Weeks = []
        league1Group1Teams = []
        league1Group2Teams = []
        league2Group1Teams = []
        league2Group2Teams = []
        
        # Split leagues into groups
        for x in range(len(self.leagueManager.leagues[0].teamList)):
            if x < (len(self.leagueManager.leagues[0].teamList) / 2):
                league1Group1Teams.append(league1.pop(random.randrange(len(league1))))
                league2Group1Teams.append(league2.pop(random.randrange(len(league2))))
            else:
                league1Group2Teams.append(league1.pop(random.randrange(len(league1))))
                league2Group2Teams.append(league2.pop(random.randrange(len(league2))))
        
        # Generate Group 1 matchups
        for x in range(len(league1Group1Teams)):
            games = []
            for y in range(len(league1Group1Teams)):
                a = x + y
                z = int(a % (len(league1Group1Teams)))
                if y % 2 == 0:
                    games.append((league1Group1Teams[y], league2Group1Teams[z]))
                else:
                    games.append((league2Group1Teams[z], league1Group1Teams[y]))
            group1Weeks.append(games)
        
        # Generate Group 2 matchups
        for x in range(len(league1Group2Teams)):
            games = []
            for y in range(len(league1Group2Teams)):
                a = x + y
                z = int(a % (len(league1Group2Teams)))
                if y % 2 == 0:
                    games.append((league1Group2Teams[y], league2Group2Teams[z]))
                else:
                    games.append((league2Group2Teams[z], league1Group2Teams[y]))
            group2Weeks.append(games)
        
        # Combine group weeks
        for x in range(len(group1Weeks)):
            week = []
            week.extend(group1Weeks[x])
            week.extend(group2Weeks[x])
            weeks.append(week)
        
        return weeks
    
    async def _simulatePlayoffRounds(self) -> None:
        """Simulate all playoff rounds"""
        
        playoffDict = {}
        playoffTeams = {}
        playoffsByeTeams = {}
        playoffsNonByeTeams = {}
        nonPlayoffTeamList = []
        strCurrentSeason = 'season{}'.format(self.currentSeason.seasonNumber)
        x = 0
        for league in self.leagueManager.leagues:
            playoffTeamsList = []
            playoffsByeTeamList = []
            playoffsNonByeTeamList = []
            list.sort(league.teamList, key=lambda team: (team.seasonTeamStats['winPerc'],team.seasonTeamStats['scoreDiff']), reverse=True)

            playoffTeamsList.extend(league.teamList[:int(len(league.teamList)/2)])
            nonPlayoffTeamList.extend(league.teamList[int(len(league.teamList)/2):])
            playoffsByeTeamList.extend(playoffTeamsList[:2])
            playoffsNonByeTeamList.extend(playoffTeamsList[2:])
            list.sort(playoffsByeTeamList, key=lambda team: (team.seasonTeamStats['winPerc'],team.seasonTeamStats['scoreDiff']), reverse=True)
            list.sort(playoffsNonByeTeamList, key=lambda team: (team.seasonTeamStats['winPerc'],team.seasonTeamStats['scoreDiff']), reverse=True)

            # Award top seed Floobits if not already clinched mid-season
            if not getattr(playoffsByeTeamList[0], 'clinchedTopSeed', False):
                from constants import CLINCH_TOPSEED_REWARD
                self._awardFavoriteTeamBonus(
                    playoffsByeTeamList[0].id, CLINCH_TOPSEED_REWARD, 'team_clinch_topseed',
                    description='Favorite team clinched #1 seed',
                    season=self.currentSeason.seasonNumber)
            playoffsByeTeamList[0].clinchedTopSeed = True
            playoffsByeTeamList[0].seasonTeamStats['topSeed'] = True

            # Mark top seed in their league
            topSeed = playoffsByeTeamList[0]
            season_str = 'Season {}'.format(self.currentSeason.seasonNumber)
            if season_str not in topSeed.topSeeds:
                topSeed.topSeeds.append(season_str)
            _topSeedText = '{0} {1} clinched the {2} top seed!'.format(topSeed.city, topSeed.name, league.name)
            self.currentSeason.leagueHighlights.insert(0, {'event': {'text': _topSeedText}})
            if BROADCASTING_AVAILABLE and broadcaster.is_enabled() and LeagueNewsEvent:
                await broadcaster.broadcast_season_event(LeagueNewsEvent.leagueNews(_topSeedText))

            playoffTeams[league.name] = playoffTeamsList.copy()
            playoffsByeTeams[league.name] = playoffsByeTeamList.copy()
            playoffsNonByeTeams[league.name] = playoffsNonByeTeamList.copy()

            for team in playoffsByeTeamList:
                team: FloosTeam.Team
                team.playoffAppearances += 1
                team.seasonTeamStats['madePlayoffs'] = True
                if not team.clinchedPlayoffs:
                    from constants import CLINCH_PLAYOFF_REWARD
                    self._awardFavoriteTeamBonus(
                        team.id, CLINCH_PLAYOFF_REWARD, 'team_clinch_playoff',
                        description='Favorite team clinched playoffs',
                        season=self.currentSeason.seasonNumber)
                team.clinchedPlayoffs = True
                team.winningStreak = False
            for team in playoffsNonByeTeamList:
                team: FloosTeam.Team
                team.playoffAppearances += 1
                team.seasonTeamStats['madePlayoffs'] = True
                team.winningStreak = False
                if not team.clinchedPlayoffs:
                    team.clinchedPlayoffs = True
                    team.eliminated = False
                    from constants import CLINCH_PLAYOFF_REWARD
                    self._awardFavoriteTeamBonus(
                        team.id, CLINCH_PLAYOFF_REWARD, 'team_clinch_playoff',
                        description='Favorite team clinched playoffs',
                        season=self.currentSeason.seasonNumber)
                    _clinchText = '{0} {1} have clinched a playoff berth'.format(team.city, team.name)
                    self.currentSeason.leagueHighlights.insert(0, {'event': {'text': _clinchText}})
                    if BROADCASTING_AVAILABLE and broadcaster.is_enabled() and LeagueNewsEvent:
                        await broadcaster.broadcast_season_event(LeagueNewsEvent.leagueNews(_clinchText))

        for team in nonPlayoffTeamList:
            team: FloosTeam.Team
            team.winningStreak = False
            if not team.eliminated:
                team.eliminated = True
                team.clinchedPlayoffs = False
                _elimText = '{0} {1} have faded from playoff contention'.format(team.city, team.name)
                self.currentSeason.leagueHighlights.insert(0, {'event': {'text': _elimText}})
                if BROADCASTING_AVAILABLE and broadcaster.is_enabled() and LeagueNewsEvent:
                    await broadcaster.broadcast_season_event(LeagueNewsEvent.leagueNews(_elimText))


        self.currentSeason.freeAgencyOrder.extend(nonPlayoffTeamList)
        list.sort(self.currentSeason.freeAgencyOrder, key=lambda team: (team.seasonTeamStats['winPerc'],team.seasonTeamStats['scoreDiff']), reverse=False)
        import floosball_methods as FloosMethods
        numOfRounds = FloosMethods.getPower(2, len(self.leagueManager.teams)/2)

        for x in range(numOfRounds):

            playoffGamesDict = {}
            playoffGamesList = []
            playoffGamesTasks = []
            self.currentSeason.leagueHighlights = []
            currentRound = x + 1
            gameNumber = 1
            roundStartTime = self.getWeekStartTime(datetime.datetime.utcnow(), 28 + currentRound)


            if x < numOfRounds - 1:
                for league in self.leagueManager.leagues:
                    teamsInRound = []
                    gamesList = []

                    if currentRound == 1:
                        teamsInRound.extend(playoffsNonByeTeams[league.name])
                        for team in playoffTeams[league.name]:
                            team: FloosTeam.Team
                            team.pressureModifier = 1.5

                    else:
                        teamsInRound.extend(playoffTeams[league.name])
                        for team in playoffTeams[league.name]:
                            team: FloosTeam.Team
                            team.pressureModifier += .2

                    list.sort(teamsInRound, key=lambda team: (team.seasonTeamStats['winPerc'],team.seasonTeamStats['scoreDiff']), reverse=True)

                    hiSeed = 0
                    lowSeed = len(teamsInRound) - 1

                    while lowSeed > hiSeed:
                        newGame = FloosGame.Game(teamsInRound[hiSeed], teamsInRound[lowSeed], timingManager=self.timingManager)
                        
                        # Assign unique integer ID and metadata
                        self._gameIdCounter += 1
                        newGame.id = self._gameIdCounter
                        newGame.seasonNumber = self.currentSeason.seasonNumber
                        newGame.playoffRound = currentRound
                        newGame.gameNumber = gameNumber
                        newGame.gameType = 'playoff'
                        
                        newGame.status = FloosGame.GameStatus.Scheduled
                        newGame.startTime = roundStartTime
                        newGame.isRegularSeasonGame = False
                        newGame.calculateWinProbability()
                        gamesList.append(newGame)
                        playoffGamesTasks.append(self._simulatePlayoffGame(newGame))
                        newGame.leagueHighlights = self.currentSeason.leagueHighlights
                        hiSeed += 1
                        lowSeed -= 1
                        gameNumber += 1
                    
                    playoffGamesDict[league.name] = gamesList.copy()
                    playoffGamesList.extend(gamesList)

                self.currentWeek = 'Playoffs Round {}'.format(x+1)
                self.currentWeekText = 'Playoffs Round {}'.format(x+1)
                if currentRound != 1:
                    await self.timingManager.waitForPlayoffRound()
            else:
                floosbowlTeams = []
                for league in self.leagueManager.leagues:
                    floosbowlTeams.extend(playoffTeams[league.name])
                for team in floosbowlTeams:
                    team.leagueChampion = True
                list.sort(floosbowlTeams, key=lambda team: (team.seasonTeamStats['winPerc'],team.seasonTeamStats['scoreDiff']), reverse=True)
                newGame = FloosGame.Game(floosbowlTeams[0], floosbowlTeams[1], timingManager=self.timingManager)
                
                # Assign unique integer ID and metadata
                self._gameIdCounter += 1
                newGame.id = self._gameIdCounter
                newGame.seasonNumber = self.currentSeason.seasonNumber
                newGame.playoffRound = currentRound
                newGame.gameNumber = gameNumber
                newGame.gameType = 'playoff'
                
                newGame.status = FloosGame.GameStatus.Scheduled
                newGame.startTime = roundStartTime
                newGame.isRegularSeasonGame = False
                newGame.calculateWinProbability()
                playoffGamesList.append(newGame)
                playoffGamesTasks.append(self._simulatePlayoffGame(newGame))
                newGame.leagueHighlights = self.currentSeason.leagueHighlights
                self.currentWeek = 'Floos Bowl'
                self.currentWeekText = 'Floos Bowl'
                newGame.homeTeam.pressureModifier = 2.5
                newGame.awayTeam.pressureModifier = 2.5
                await self.timingManager.waitForChampionship()

            self.currentSeason.activeGames = playoffGamesList
            self.currentSeason.completedWeekGames = None  # Clear previous round's finished games
            self.currentSeason.currentWeekText = self.currentWeekText
            self.currentSeason.schedule.append({'startTime': roundStartTime, 'games': playoffGamesList})

            # Broadcast playoff round start so the frontend updates the week label
            if BROADCASTING_AVAILABLE and broadcaster.is_enabled():
                await broadcaster.broadcast_season_event(SeasonEvent.weekStart(
                    seasonNumber=self.currentSeason.seasonNumber,
                    weekNumber=28 + currentRound,
                    games=[],
                    weekText=self.currentWeekText
                ))

            # Lock equipped cards for playoff week
            try:
                from database.connection import get_session as _getSession
                from database.repositories.card_repositories import EquippedCardRepository
                lockSession = _getSession()
                EquippedCardRepository(lockSession).lockWeek(
                    self.currentSeason.seasonNumber, 28 + currentRound
                )
                lockSession.commit()
                lockSession.close()
            except Exception as e:
                logger.error(f"Failed to lock equipped cards for playoff round {currentRound}: {e}")

            self.currentSeason.leagueHighlights.insert(0, {'event': {'text': '{} Starting Soon...'.format(self.currentWeekText)}})

            #await asyncio.sleep(30)
            # while datetime.datetime.utcnow() < roundStartTime:
            #     await asyncio.sleep(30)
                
            self.currentSeason.leagueHighlights.insert(0, {'event': {'text': '{} Start'.format(self.currentWeekText)}})

            # Start periodic leaderboard broadcast during playoff games
            playoffLeaderboardTask = asyncio.ensure_future(self._broadcastLeaderboardPeriodically())

            await asyncio.gather(*playoffGamesTasks)

            # Stop periodic leaderboard broadcast
            playoffLeaderboardTask.cancel()
            try:
                await playoffLeaderboardTask
            except asyncio.CancelledError:
                pass

            # Clear active games so roster swaps are unlocked between rounds.
            # Keep a reference so the API can still serve them until next round.
            self.currentSeason.completedWeekGames = self.currentSeason.activeGames
            self.currentSeason.activeGames = None

            if len(playoffGamesList) == 1:
                game: FloosGame.Game = playoffGamesList[0]
                playoffTeamsList.clear()
                
                season_str = 'Season {}'.format(self.currentSeason.seasonNumber)
                
                # Both teams in the Floosbowl are league champions
                if season_str not in game.winningTeam.leagueChampionships:
                    game.winningTeam.leagueChampionships.append(season_str)
                game.winningTeam.seasonTeamStats['leagueChamp'] = True
                
                # Only the winner is the Floosball champion
                if season_str not in game.winningTeam.floosbowlChampionships:
                    game.winningTeam.floosbowlChampionships.append(season_str)
                game.winningTeam.floosbowlChampion = True
                game.winningTeam.seasonTeamStats['floosbowlChamp'] = True
                
                self.currentSeason.champion = game.winningTeam
                runnerUp: FloosTeam.Team = game.losingTeam
                
                # Runner-up is also a league champion (made it to Floosbowl)
                if season_str not in runnerUp.leagueChampionships:
                    runnerUp.leagueChampionships.append(season_str)
                runnerUp.seasonTeamStats['leagueChamp'] = True
                runnerUp.eliminated = True
                
                _champText = '{0} {1} are Floos Bowl champions!'.format(self.currentSeason.champion.city, self.currentSeason.champion.name)
                self.currentSeason.leagueHighlights.insert(0, {'event': {'text': _champText}})
                if BROADCASTING_AVAILABLE and broadcaster.is_enabled() and LeagueNewsEvent:
                    await broadcaster.broadcast_season_event(LeagueNewsEvent.leagueNews(_champText))
                playoffDict['Floos Bowl'] = gameResults
                self.currentSeason.freeAgencyOrder.append(runnerUp)
                self.currentSeason.freeAgencyOrder.append(self.currentSeason.champion)
                for player in self.currentSeason.champion.rosterDict.values():
                    if player:
                        player:FloosPlayer.Player
                        # Make sure team reference is valid
                        team_abbr = player.team.abbr if hasattr(player.team, 'abbr') else 'UNK'
                        team_color = player.team.color if hasattr(player.team, 'color') else '#000000'
                        player.leagueChampionships.append({'Season': self.currentSeason.seasonNumber, 'team': team_abbr, 'teamColor': team_color})

                self.recordsManager.updateChampionshipHistory(self.currentSeason.seasonNumber, self.currentSeason.champion, runnerUp)

                # Award Floobits to users whose favorite team won the Floosbowl
                from constants import FLOOSBOWL_WIN_REWARD
                self._awardFavoriteTeamBonus(
                    self.currentSeason.champion.id, FLOOSBOWL_WIN_REWARD, 'team_floosbowl_win',
                    description='Favorite team won the Floos Bowl!',
                    season=self.currentSeason.seasonNumber)
            else:
                for league in self.leagueManager.leagues:
                    for game in playoffGamesDict[league.name]:
                        game: FloosGame.Game
                        gameResults = game.gameDict
                        playoffDict[game.id] = gameResults
                        for team in playoffTeams[league.name]:
                            # Use direct object reference instead of gameDict to avoid KeyError
                            if game.losingTeam and team.name == game.losingTeam.name:
                                team.eliminated = True
                                _playoffElimText = '{0} {1} have faded from playoff contention'.format(team.city, team.name)
                                self.currentSeason.leagueHighlights.insert(0, {'event': {'text': _playoffElimText}})
                                if BROADCASTING_AVAILABLE and broadcaster.is_enabled() and LeagueNewsEvent:
                                    await broadcaster.broadcast_season_event(LeagueNewsEvent.leagueNews(_playoffElimText))
                                self.currentSeason.freeAgencyOrder.append(team)
                                playoffTeams[league.name].remove(team)
                                break

                

            # Note: Postseason data is now stored in the database, JSON output disabled
            # games_dir = os.path.join('{}/games'.format(strCurrentSeason))
            # os.makedirs(games_dir, exist_ok=True)
            # jsonFile = open(os.path.join(games_dir, 'postseason.json'), "w+")
            # jsonFile.write(json.dumps(playoffDict, indent=4))
            # jsonFile.close()
            
            # Commit playoff games from this round to database
            if DB_IMPORTS_AVAILABLE and USE_DATABASE and self.db_session:
                try:
                    self.db_session.commit()
                    logger.debug(f"Committed playoff round {x+1} games")
                except Exception as e:
                    logger.error(f"Failed to commit playoff games: {e}")
                    self.db_session.rollback()
            
            if x < numOfRounds - 1:
                self.playerManager.sortPlayersByPosition()
                teamManager = self.serviceContainer.getService('team_manager')
                if teamManager:
                    teamManager.sortDefenses()
                #await asyncio.sleep(30)
            
    
    async def _simulatePlayoffGame(self, game: FloosGame.Game) -> None:
        """Simulate a single playoff game"""

        try:
            # Create game instance with timing manager
            gameInstance = game

            # Set game type (playoff games)
            gameInstance.isRegularSeasonGame = False
            gameInstance.isPlayoff = True

            # Wire fantasy tracker callback for each player
            fantasyTracker = self.serviceContainer.getService('fantasy_tracker')
            if fantasyTracker:
                for team in [gameInstance.homeTeam, gameInstance.awayTeam]:
                    for player in team.rosterDict.values():
                        if player:
                            pid = player.id
                            player.stat_tracker._on_fantasy_points = (
                                lambda pts, _pid=pid: fantasyTracker.addPlayerPoints(_pid, pts)
                            )

            # Simulate the game
            await gameInstance.playGame()

            # Clear fantasy tracker callbacks after game
            if fantasyTracker:
                for team in [gameInstance.homeTeam, gameInstance.awayTeam]:
                    for player in team.rosterDict.values():
                        if player:
                            player.stat_tracker._on_fantasy_points = None
            
            # Determine winner
            winner = game.homeTeam if gameInstance.homeScore > gameInstance.awayScore else game.awayTeam
            
            # Save game to database (player._lastGameFantasyPoints preserves FP after zeroing)
            if DB_IMPORTS_AVAILABLE and USE_DATABASE and self.game_repo:
                self._saveGameToDatabase(gameInstance)

            # Update team records
            self._updateTeamRecords(gameInstance)

            # Process post-game statistics (record-checking, team stat accumulation)
            self.recordsManager.processPostGameStats(gameInstance)

            # Update ELO ratings based on playoff game result using pre-game win probability
            teamManager = self.serviceContainer.getService('team_manager')
            if teamManager and hasattr(gameInstance, 'winningTeam') and gameInstance.winningTeam:
                teamManager.updateEloAfterGame(
                    gameInstance.homeTeam,
                    gameInstance.awayTeam,
                    gameInstance.homeScore,
                    gameInstance.awayScore,
                    gameInstance.winningTeam,
                    getattr(gameInstance, 'preGameHomeWinProbability', None),
                    getattr(gameInstance, 'preGameAwayWinProbability', None)
                )

            # Check for records
            self.recordsManager.checkPlayerGameRecords()
            self.recordsManager.checkTeamGameRecords(gameInstance)
            
        except Exception as e:
            logger.error(f"Error simulating playoff game: {e}")
            return None
    
    async def _completeSeasonSimulation(self) -> None:
        """Handle season completion tasks"""
        if not self.currentSeason:
            return
            
        logger.info("Completing season simulation")
        
        # Mark season as complete
        self.currentSeason.isComplete = True
        
        # Update league champions
        self.currentSeason.leagueChampions = self.leagueManager.getLeagueChampions()
        
        # Check season records
        self.recordsManager.checkSeasonRecords(self.currentSeason)
        
        # Update career records
        self.recordsManager.checkCareerRecords()
        
        # Handle player season progression
        await self._handlePlayerSeasonProgression()
        
        # Save season statistics
        self.saveSeasonStats()
        
        # Add to season history
        self.seasonHistory.append(self.currentSeason)
        
        # Update game state
        seasonNumber = self.currentSeason.seasonNumber
        self.serviceContainer.getService('game_state').setState('seasonsPlayed', seasonNumber)
        
        logger.info(f"Season {seasonNumber} completed. Champion: {self.currentSeason.champion.name if self.currentSeason.champion else 'None'}")
    
    async def handleOffseason(self) -> None:
        """Handle offseason activities"""
        await self._handleOffseason()
    
    async def _handleOffseason(self) -> None:
        """Handle offseason activities"""
        logger.info("Processing offseason activities")
        
        # Set offseason status
        if self.currentSeason:
            self.currentSeason.currentWeek = 'Offseason'
            self.currentSeason.currentWeekText = 'Offseason'
        
        # Wait for offseason timing
        await self.timingManager.waitForOffseason()
        
        # STEP 1: Player offseason training (without resetting performance ratings yet)
        logger.info("Step 1: Player offseason training")
        # Build a map of player id → coach dev rating for rostered players
        rosteredDevRating: dict = {}
        teamManager = self.serviceContainer.getService('team_manager')
        for team in teamManager.teams:
            coachDevRating = getattr(getattr(team, 'coach', None), 'playerDevelopment', 50)
            for posGroup in team.rosterDict.values():
                if posGroup is not None and hasattr(posGroup, 'id'):
                    rosteredDevRating[posGroup.id] = coachDevRating
        for player in self.playerManager.activePlayers:
            if hasattr(player, 'offseasonTraining'):
                devRating = rosteredDevRating.get(getattr(player, 'id', None), 50)
                player.offseasonTraining(coachDevRating=devRating)
        
        # STEP 1.5: Increment free agent years for existing free agents
        logger.info("Step 1.5: Increment free agent years")
        for player in self.playerManager.freeAgents:
            if hasattr(player, 'freeAgentYears'):
                player.freeAgentYears += 1
            else:
                # Initialize for players missing the attribute
                player.freeAgentYears = 1
        
        # STEP 2: Process contract decrements and retirements for rostered players
        logger.info("Step 2: Contract decrements and team retirements")
        await self._processRosteredPlayerContracts()
        
        # STEP 3: Replacement player generation is handled in conductFreeAgencySimulation (Step 4)
        # This ensures all retirements (both rostered and free agent) are processed before generating replacements
        
        # STEP 4: Run comprehensive free agency simulation (includes free agent retirements and replacement generation)
        # Performance ratings from previous season are used to evaluate cuts
        logger.info("Step 4: Free agency simulation")
        await self._processFreeAgency()

        # STEP 4.5: Handle retired players on fantasy rosters
        # Must run before Step 7 (HoF) which clears newlyRetiredPlayers
        retiredPlayerIds = {
            p.id for p in self.playerManager.newlyRetiredPlayers
            if hasattr(p, 'id')
        }
        # Also include players retired in Step 2 (rostered contract retirements)
        # that were already moved to retiredPlayers list
        retiredPlayerIds.update(
            p.id for p in self.playerManager.retiredPlayers
            if hasattr(p, 'id')
        )
        if retiredPlayerIds:
            nextSeason = (self.currentSeason.seasonNumber if self.currentSeason else 0) + 1
            logger.info(f"Step 4.5: Handling {len(retiredPlayerIds)} retired players on fantasy rosters")
            self._handleRetiredPlayerRosters(retiredPlayerIds, nextSeason)

        # STEP 5: Reset season performance ratings AFTER free agency
        # This allows performance ratings to be used in cut decisions
        logger.info("Step 5: Reset season performance ratings")
        for player in self.playerManager.activePlayers:
            if hasattr(player, 'seasonPerformanceRating'):
                player.seasonPerformanceRating = 0
        
        # STEP 6: Update team ratings and defenses after roster changes
        logger.info("Step 6: Update team ratings")
        await self._updateTeamRatings()
        
        # STEP 7: Induct Hall of Fame players
        logger.info("Step 7: Hall of Fame inductions")
        self.playerManager.inductHallOfFame()
        
        # STEP 8: Save unused names
        self.playerManager.saveUnusedNames()

        # STEP 9: User season transitions (pending favorites, fantasy roster finalization)
        logger.info("Step 9: Processing user season transitions")
        self._processUserSeasonTransitions()

        # STEP 9.5: Season-end economy payouts (leaderboard prizes + FP-to-Floobits)
        logger.info("Step 9.5: Awarding season-end prizes")
        self._awardSeasonEndPrizes(self.currentSeason.seasonNumber)

        # STEP 10: Generate card templates for newly drafted rookies
        logger.info("Step 10: Generating rookie card templates")
        nextSeason = (self.currentSeason.seasonNumber if self.currentSeason else 0) + 1
        self._generateRookieCardTemplates(nextSeason)

        logger.info("Offseason activities complete")
    
    def _generateCardTemplates(self, seasonNumber: int) -> None:
        """Generate card templates for all active players for a season.

        Uses a dedicated session to avoid holding a write lock on the shared
        simulation session (which would block API endpoints on SQLite).
        Passes previous season's MVP, Champion, and All-Pro data for classification.
        """
        try:
            from managers.cardManager import CardManager
            from database.connection import get_session

            # Extract classification data from previous season
            mvpPlayerId = None
            championPlayerIds = set()
            allProPlayerIds = set()

            if self.currentSeason:
                # MVP player ID
                mvpData = getattr(self.currentSeason, 'mvp', None)
                if mvpData and isinstance(mvpData, dict):
                    mvpPlayerId = mvpData.get('id')

                # Champion team's player IDs (all 6 roster players)
                champion = getattr(self.currentSeason, 'champion', None)
                if champion and hasattr(champion, 'rosterDict'):
                    for player in champion.rosterDict.values():
                        if player and hasattr(player, 'id'):
                            championPlayerIds.add(player.id)

                # All-Pro player IDs (top performer per position)
                allProPlayerIds = getattr(self.currentSeason, 'allProPlayerIds', set())

            session = get_session()
            cardManager = CardManager(self.serviceContainer)
            count = cardManager.generateSeasonTemplates(
                session, seasonNumber,
                mvpPlayerId=mvpPlayerId,
                championPlayerIds=championPlayerIds,
                allProPlayerIds=allProPlayerIds,
            )
            session.commit()
            session.close()
            logger.info(f"Card template generation complete: {count} templates for season {seasonNumber}")
        except Exception as e:
            logger.warning(f"Card template generation failed: {e}")
            import traceback
            logger.debug(traceback.format_exc())

    def _generateRookieCardTemplates(self, seasonNumber: int) -> None:
        """Generate card templates for newly drafted rookies.

        Uses a dedicated session to avoid holding a write lock on the shared
        simulation session.
        """
        try:
            from managers.cardManager import CardManager
            from database.connection import get_session
            session = get_session()
            cardManager = CardManager(self.serviceContainer)
            count = cardManager.generateRookieTemplates(session, seasonNumber)
            session.commit()
            session.close()
            logger.info(f"Rookie card template generation complete: {count} templates for season {seasonNumber}")
        except Exception as e:
            logger.warning(f"Rookie card template generation failed: {e}")

    def _processUserSeasonTransitions(self) -> None:
        """Apply pending favorite team changes, finalize scores, and carry rosters forward."""
        from database.connection import get_session
        from database.models import (
            User, FantasyRoster, FantasyRosterPlayer, PlayerSeasonStats, Player,
        )

        completedSeason = self.currentSeason.seasonNumber if self.currentSeason else None
        if completedSeason is None:
            return

        nextSeason = completedSeason + 1
        session = get_session()
        try:
            # Promote pending favorite teams
            pendingUsers = session.query(User).filter(
                User.pending_favorite_team_id.isnot(None)
            ).all()
            for u in pendingUsers:
                logger.info(f"User {u.id}: promoting pending favorite team {u.pending_favorite_team_id}")
                u.favorite_team_id = u.pending_favorite_team_id
                u.pending_favorite_team_id = None
                u.favorite_team_locked_season = None

            # Finalize fantasy roster scores from DB season stats
            lockedRosters = session.query(FantasyRoster).filter_by(
                season=completedSeason, is_locked=True
            ).all()
            for roster in lockedRosters:
                totalPoints = 0.0
                for rp in roster.players:
                    seasonStat = session.query(PlayerSeasonStats).filter_by(
                        player_id=rp.player_id, season=completedSeason
                    ).first()
                    finalFp = seasonStat.fantasy_points if seasonStat else 0
                    earned = max(0, finalFp - rp.points_at_lock)
                    totalPoints += earned
                roster.total_points = totalPoints
                logger.info(f"Fantasy roster {roster.id} (user {roster.user_id}): finalized at {totalPoints:.1f} pts")

            # Carry rosters forward: clone locked rosters into new season
            # Only carry forward players who are still active (not retired)
            activePlayerIds = {
                p.id for p in session.query(Player.id).filter_by(is_active=True).all()
            }

            carriedCount = 0
            for oldRoster in lockedRosters:
                # Check if new season roster already exists (idempotent)
                existingNew = session.query(FantasyRoster).filter_by(
                    user_id=oldRoster.user_id, season=nextSeason
                ).first()
                if existingNew:
                    continue

                newRoster = FantasyRoster(
                    user_id=oldRoster.user_id,
                    season=nextSeason,
                    is_locked=False,
                    total_points=0.0,
                    card_bonus_points=0.0,
                    swaps_available=0,
                )
                session.add(newRoster)
                session.flush()  # Get newRoster.id

                for rp in oldRoster.players:
                    if rp.player_id not in activePlayerIds:
                        continue  # Skip retired players
                    newRp = FantasyRosterPlayer(
                        roster_id=newRoster.id,
                        player_id=rp.player_id,
                        slot=rp.slot,
                        points_at_lock=0.0,
                    )
                    session.add(newRp)

                carriedCount += 1
                logger.info(f"Carried forward roster for user {oldRoster.user_id} to season {nextSeason}")

            if carriedCount:
                logger.info(f"Carried {carriedCount} rosters forward to season {nextSeason}")

            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Error processing user season transitions: {e}")
            import traceback
            logger.debug(traceback.format_exc())
        finally:
            session.close()

    async def _processFreeAgency(self) -> None:
        """Process free agency period using comprehensive simulation"""
        logger.info("Processing free agency")
        
        # Use the free agency order built during playoffs
        # Order: Non-playoff teams (worst to best) → Playoff losers by round → Runner-up → Champion
        if not self.currentSeason or not hasattr(self.currentSeason, 'freeAgencyOrder'):
            logger.error("No free agency order available (playoffs must be completed first)")
            return
        
        freeAgencyOrder = self.currentSeason.freeAgencyOrder
        
        # Get league highlights list
        leagueHighlights = []
        if self.currentSeason and hasattr(self.currentSeason, 'leagueHighlights'):
            leagueHighlights = self.currentSeason.leagueHighlights
        
        # Broadcast offseason start with draft order
        if BROADCASTING_AVAILABLE and broadcaster:
            try:
                draftOrderList = [
                    {'name': t.name, 'abbr': getattr(t, 'abbr', t.name[:3].upper()), 'id': getattr(t, 'id', None)}
                    for t in freeAgencyOrder
                ]
                await broadcaster.broadcast_season_event(OffseasonEvent.start(draftOrderList))
            except Exception as e:
                logger.warning(f"Could not broadcast offseason start: {e}")

        # Run the comprehensive free agency simulation (sync), collecting events
        currentSeasonNum = self.currentSeason.seasonNumber if hasattr(self, 'currentSeasonNumber') else 1
        eventLog = []
        freeAgencyHistory = self.playerManager.conductFreeAgencySimulation(
            freeAgencyOrder=freeAgencyOrder,
            currentSeason=currentSeasonNum,
            leagueHighlights=leagueHighlights,
            eventLog=eventLog,
        )

        # Replay events with delay so frontend sees live updates
        self._offseasonTransactions = []
        if BROADCASTING_AVAILABLE and broadcaster and eventLog:
            try:
                for entry in eventLog:
                    if entry['type'] == 'pick':
                        # Keep snapshot in sync: remove signed player before broadcasting
                        if self.playerManager._freeAgentSnapshot is not None:
                            self.playerManager._freeAgentSnapshot = [
                                fa for fa in self.playerManager._freeAgentSnapshot
                                if fa['name'] != entry['player']
                            ]
                        await broadcaster.broadcast_season_event(
                            OffseasonEvent.pick(
                                entry['team'], entry['teamAbbr'],
                                entry['player'], entry['position'],
                                entry['rating'], entry['tier'],
                            )
                        )
                    elif entry['type'] == 'cut':
                        # Keep snapshot in sync: add cut player back before broadcasting
                        if self.playerManager._freeAgentSnapshot is not None:
                            cutFa = {
                                'name': entry['player'], 'position': entry['position'],
                                'rating': entry['rating'], 'tier': entry.get('tier', 'TierC'),
                            }
                            self.playerManager._freeAgentSnapshot = sorted(
                                self.playerManager._freeAgentSnapshot + [cutFa],
                                key=lambda fa: -fa['rating']
                            )
                        await broadcaster.broadcast_season_event(
                            OffseasonEvent.cut(
                                entry['team'], entry['teamAbbr'],
                                entry['player'], entry['position'],
                                entry['rating'], entry.get('tier', ''),
                            )
                        )
                    elif entry['type'] == 'team_complete':
                        await broadcaster.broadcast_season_event(
                            OffseasonEvent.team_complete(entry['team'], entry['teamAbbr'])
                        )
                    if entry['type'] != 'team_complete':
                        self._offseasonTransactions.append(entry)
                    await self.timingManager.waitBetweenOffseasonPicks()
                await broadcaster.broadcast_season_event(
                    OffseasonEvent.complete(len(self.playerManager.freeAgents))
                )
                # Clear snapshot so REST endpoint switches back to live freeAgents
                self.playerManager._freeAgentSnapshot = None
            except Exception as e:
                logger.warning(f"Could not broadcast offseason events: {e}")
                self.playerManager._freeAgentSnapshot = None

        logger.info(f"Free agency complete: {len(freeAgencyHistory)} transactions")
    
    async def _processRosteredPlayerContracts(self) -> None:
        """Process contract decrements and retirements for players on team rosters"""
        from random import randint
        
        teamManager = self.serviceContainer.getService('team_manager')
        if not teamManager:
            return
        
        leagueHighlights = []
        if self.currentSeason and hasattr(self.currentSeason, 'leagueHighlights'):
            leagueHighlights = self.currentSeason.leagueHighlights
        
        for team in teamManager.teams:
            # Initialize cuts available for free agency
            team.cutsAvailable = 2
            
            for position, player in list(team.rosterDict.items()):
                if player is None:
                    continue
                
                # Note: service time is updated in _handlePlayerSeasonProgression based on seasonsPlayed
                # Don't update it here to avoid overwriting the correct logic
                
                # Decrement contract term
                player.termRemaining -= 1
                
                # Check for retirement
                shouldRetire = False
                
                if player.seasonsPlayed > player.attributes.longevity:
                    # Player is past their longevity
                    if player.termRemaining <= 0:
                        # Contract expired - higher retirement chance
                        if player.seasonsPlayed > 15:
                            shouldRetire = randint(1, 100) > 10  # 90% retire
                        elif player.seasonsPlayed > 10:
                            shouldRetire = randint(1, 100) > 35  # 65% retire
                        elif player.seasonsPlayed >= 7:
                            shouldRetire = randint(1, 100) > 95  # 5% retire
                    else:
                        # Still under contract - lower retirement chance
                        if player.seasonsPlayed > 15:
                            shouldRetire = randint(1, 100) > 30  # 70% retire
                        elif player.seasonsPlayed > 10:
                            shouldRetire = randint(1, 100) > 75  # 25% retire
                        elif player.seasonsPlayed >= 7:
                            shouldRetire = randint(1, 100) > 90  # 10% retire
                
                if shouldRetire:
                    # Player retires
                    self._executePlayerRetirement(player, team, position, leagueHighlights)
                elif player.termRemaining <= 0:
                    # Contract expired - move to free agency
                    player.previousTeam = team.name
                    # TODO: capHit feature not fully developed - disabled for now
                    # team.playerCap -= getattr(player, 'capHit', 0)
                    if player.currentNumber in team.playerNumbersList:
                        team.playerNumbersList.remove(player.currentNumber)
                    player.team = 'Free Agent'
                    player.freeAgentYears = 0
                    # Only add to free agents if not already there (defensive check)
                    if player not in self.playerManager.freeAgents:
                        self.playerManager.freeAgents.append(player)
                    team.rosterDict[position] = None
                    
                    leagueHighlights.insert(0, {
                        'event': {'text': f'{player.name} has become a Free Agent'}
                    })
    
    def _executePlayerRetirement(self, player, team, position, leagueHighlights):
        """Execute the retirement of a player from a team roster"""
        player.previousTeam = team.name
        player.seasonPerformanceRating = 0
        # TODO: capHit feature not fully developed - disabled for now
        # team.playerCap -= getattr(player, 'capHit', 0)
        if player.currentNumber in team.playerNumbersList:
            team.playerNumbersList.remove(player.currentNumber)
        player.team = 'Retired'
        player.serviceTime = FloosPlayer.PlayerServiceTime.Retired
        
        self.playerManager.retiredPlayers.append(player)
        self.playerManager.newlyRetiredPlayers.append(player)
        if player in self.playerManager.activePlayers:
            self.playerManager.activePlayers.remove(player)
        if player in self.playerManager.freeAgents:
            self.playerManager.freeAgents.remove(player)
        self.playerManager.removeFromPositionList(player)
        
        team.rosterDict[position] = None
        
        leagueHighlights.insert(0, {
            'event': {'text': f'{player.name} has retired after {player.seasonsPlayed} seasons'}
        })
        
        # Add name variant back to unused names for legacy naming
        self._recyclePlayerName(player.name)
    
    def _recyclePlayerName(self, name: str) -> None:
        """Convert retired player name to legacy variant and add to unused names"""
        # Name progression: Base -> Jr. -> III -> IV -> V -> VI -> VII -> VIII -> IX -> X -> XI
        if name.endswith('Jr.'):
            name = name.replace('Jr.', 'III')
        elif name.endswith('IV'):
            name = name.replace('IV', 'V')
        elif name.endswith('VIII'):
            name = name.replace('VIII', 'IX')
        elif name.endswith('IX'):
            name = name.replace('IX', 'X')
        elif name.endswith('III'):
            name = name.replace('III', 'IV')
        elif name.endswith('V') or name.endswith('X'):
            name += 'I'
        else:
            name += ' Jr.'
        
        self.playerManager.unusedNames.append(name)
    
    # NOTE: This method is no longer used - free agent retirements are handled
    # by playerManager._processFreeAgentRetirements() within conductFreeAgencySimulation()
    # Kept for reference only
    def _processFreeAgentRetirements_UNUSED(self) -> None:
        """Process retirements of players who've been free agents for 3+ years"""
        from random import randint
        
        leagueHighlights = []
        if self.currentSeason and hasattr(self.currentSeason, 'leagueHighlights'):
            leagueHighlights = self.currentSeason.leagueHighlights
        
        # Process free agent aging and retirement
        # Note: freeAgentYears is already incremented in _processContractExpirations
        for player in list(self.playerManager.freeAgents):
            if player.freeAgentYears > 3:
                shouldRetire = False
                x = randint(1, 10)
                
                # Retirement probability based on tier
                if player.playerTier.value == 1 and x > 3:  # TierD: 70% retire
                    shouldRetire = True
                elif player.playerTier.value == 2 and x > 5:  # TierC: 50% retire
                    shouldRetire = True
                elif x > 8:  # TierB/A/S: 20% retire
                    shouldRetire = True
                
                if shouldRetire:
                    player.team = 'Retired'
                    player.serviceTime = FloosPlayer.PlayerServiceTime.Retired
                    self.playerManager.retiredPlayers.append(player)
                    self.playerManager.newlyRetiredPlayers.append(player)
                    if player in self.playerManager.freeAgents:
                        self.playerManager.freeAgents.remove(player)
                    self.playerManager.safeRemove(self.playerManager.activePlayers, player)
                    self.playerManager.removeFromPositionList(player)
                    
                    leagueHighlights.insert(0, {
                        'event': {'text': f'{player.name} has retired after {player.seasonsPlayed} seasons'}
                    })
                    
                    # Recycle name
                    self._recyclePlayerName(player.name)
    
    def _generateReplacementPlayers(self) -> None:
        """Generate new players to replace retirees"""
        import numpy as np
        from random import randint
        
        newPlayerCount = 12  # Base number of new players per offseason
        numRetired = len(self.playerManager.newlyRetiredPlayers)
        numOfPlayers = max(newPlayerCount, numRetired)
        
        # Generate player skill seeds
        meanPlayerSkill = 80
        stdDevPlayerSkill = 7
        playerAverages = np.random.normal(meanPlayerSkill, stdDevPlayerSkill, numOfPlayers)
        playerAverages = np.clip(playerAverages, 60, 100).tolist()
        
        # Generate replacement for each retired player (position-matched)
        for player in self.playerManager.newlyRetiredPlayers:
            if not playerAverages:
                break
            
            seed = int(playerAverages.pop(randint(0, len(playerAverages) - 1)))
            newPlayer = None
            
            if player.position == FloosPlayer.Position.QB:
                newPlayer = FloosPlayer.PlayerQB(seed)
                self.playerManager.activeQbs.append(newPlayer)
            elif player.position == FloosPlayer.Position.RB:
                newPlayer = FloosPlayer.PlayerRB(seed)
                self.playerManager.activeRbs.append(newPlayer)
            elif player.position == FloosPlayer.Position.WR:
                newPlayer = FloosPlayer.PlayerWR(seed)
                self.playerManager.activeWrs.append(newPlayer)
            elif player.position == FloosPlayer.Position.TE:
                newPlayer = FloosPlayer.PlayerTE(seed)
                self.playerManager.activeTes.append(newPlayer)
            elif player.position == FloosPlayer.Position.K:
                newPlayer = FloosPlayer.PlayerK(seed)
                self.playerManager.activeKs.append(newPlayer)
            
            if newPlayer:
                newPlayer.name = self._getUnusedName()
                newPlayer.team = 'Free Agent'
                newPlayer.id = len(self.playerManager.activePlayers) + len(self.playerManager.retiredPlayers) + 1
                newPlayer.freeAgentYears = 0
                self.playerManager.activePlayers.append(newPlayer)
                self.playerManager.freeAgents.append(newPlayer)
        
        # Generate additional random rookies if we need more than just replacements
        if newPlayerCount > numRetired:
            posList = [FloosPlayer.Position.QB, FloosPlayer.Position.RB, 
                      FloosPlayer.Position.WR, FloosPlayer.Position.TE, FloosPlayer.Position.K]
            
            for _ in range(newPlayerCount - numRetired):
                if not playerAverages:
                    break
                
                seed = int(playerAverages.pop(randint(0, len(playerAverages) - 1)))
                pos = posList[randint(0, len(posList) - 1)]
                newPlayer = None
                
                if pos == FloosPlayer.Position.QB:
                    newPlayer = FloosPlayer.PlayerQB(seed)
                    self.playerManager.activeQbs.append(newPlayer)
                elif pos == FloosPlayer.Position.RB:
                    newPlayer = FloosPlayer.PlayerRB(seed)
                    self.playerManager.activeRbs.append(newPlayer)
                elif pos == FloosPlayer.Position.WR:
                    newPlayer = FloosPlayer.PlayerWR(seed)
                    self.playerManager.activeWrs.append(newPlayer)
                elif pos == FloosPlayer.Position.TE:
                    newPlayer = FloosPlayer.PlayerTE(seed)
                    self.playerManager.activeTes.append(newPlayer)
                elif pos == FloosPlayer.Position.K:
                    newPlayer = FloosPlayer.PlayerK(seed)
                    self.playerManager.activeKs.append(newPlayer)
                
                if newPlayer:
                    newPlayer.name = self._getUnusedName()
                    newPlayer.team = 'Free Agent'
                    newPlayer.id = len(self.playerManager.activePlayers) + len(self.playerManager.retiredPlayers) + 1
                    newPlayer.freeAgentYears = 0
                    self.playerManager.activePlayers.append(newPlayer)
                    self.playerManager.freeAgents.append(newPlayer)
        
        logger.info(f"Generated {numOfPlayers} new players to replace retirees")
    
    def _getUnusedName(self) -> str:
        """Get an unused name from the pool"""
        from random import randint
        
        if not self.playerManager.unusedNames:
            logger.error("No unused names available!")
            return f"Player {randint(1000, 9999)}"
        
        return self.playerManager.unusedNames.pop(randint(0, len(self.playerManager.unusedNames) - 1))
    
    async def _updateTeamRatings(self) -> None:
        """Update team ratings and defenses based on current rosters"""
        teamManager = self.serviceContainer.getService('team_manager')
        if teamManager:
            # Update each team's defensive ratings based on their roster
            for team in teamManager.teams:
                team.updateDefense()
            
            # Sort and tier defenses across the league
            teamManager.sortDefenses()
            
            # Update overall team ratings
            teamManager.updateTeamRatings()
    
    async def _handlePlayerSeasonProgression(self) -> None:
        """Handle player progression at season end"""
        for player in self.playerManager.activePlayers:
            # Increment seasons played
            if hasattr(player, 'seasonsPlayed'):
                player.seasonsPlayed += 1
            else:
                player.seasonsPlayed = 1
            
            # Decrement contract terms
            if hasattr(player, 'termRemaining') and player.termRemaining > 0:
                player.termRemaining -= 1
            
            # Update service time using proper progression logic
            if player.seasonsPlayed >= 10:
                player.serviceTime = FloosPlayer.PlayerServiceTime.Veteran4
            elif player.seasonsPlayed >= 7:
                player.serviceTime = FloosPlayer.PlayerServiceTime.Veteran3
            elif player.seasonsPlayed >= 4:
                player.serviceTime = FloosPlayer.PlayerServiceTime.Veteran2
            elif player.seasonsPlayed >= 2:
                player.serviceTime = FloosPlayer.PlayerServiceTime.Veteran1
            else:
                player.serviceTime = FloosPlayer.PlayerServiceTime.Rookie
            
            # Archive season stats
            if hasattr(player, 'seasonStatsDict') and hasattr(player, 'seasonStatsArchive'):
                import copy
                archivedStats = copy.deepcopy(player.seasonStatsDict)
                # Ensure season number and metadata are present
                archivedStats['season'] = self.currentSeason.seasonNumber if self.currentSeason else 0
                archivedStats['gp'] = player.gamesPlayed
                archivedStats['team'] = player.team.name if hasattr(player.team, 'name') else (player.team if isinstance(player.team, str) else 'FA')
                archivedStats['color'] = getattr(player.team, 'color', '#94a3b8') if hasattr(player.team, 'name') else '#94a3b8'
                player.seasonStatsArchive.append(archivedStats)

            # Reset season stats for next year
            if hasattr(player, 'seasonStatsDict'):
                import copy as _copy
                player.seasonStatsDict = _copy.deepcopy(FloosPlayer.playerStatsDict)
                player.seasonStatsDict['team'] = player.team.name if hasattr(player.team, 'name') else (player.team if isinstance(player.team, str) else None)
                player.gamesPlayed = 0
                # Update stat_tracker reference to new season dict
                if hasattr(player, 'stat_tracker'):
                    player.stat_tracker.season_stats_dict = player.seasonStatsDict
    
    def _clearSeasonData(self) -> None:
        """Clear season-specific data for new season"""
        # Clear league standings
        self.leagueManager.clearSeasonData()
        
        # Clear team season stats
        teamManager = self.serviceContainer.getService('team_manager')
        if teamManager:
            teamManager.clearTeamSeasonStats()
        
        # Clear player season stats (handled in progression)
    
    def _saveRosterHistory(self) -> None:
        """Save current roster for each team in their roster history"""
        teamManager = self.serviceContainer.getService('team_manager')
        if not teamManager:
            return
        
        for team in teamManager.teams:
            # Build roster snapshot
            rosterDict = {}
            for pos, player in team.rosterDict.items():
                if player:
                    # Get position as integer (enum value)
                    position_value = player.position if isinstance(player.position, int) else player.position.value if hasattr(player.position, 'value') else 0
                    # Get tier as integer (enum value)
                    tier_value = player.playerTier if isinstance(player.playerTier, int) else player.playerTier.value if hasattr(player, 'playerTier') and hasattr(player.playerTier, 'value') else 0
                    
                    rosterDict[pos] = {
                        'name': player.name,
                        'pos': position_value,
                        'rating': player.playerRating,
                        'stars': tier_value,
                        'termRemaining': player.termRemaining,
                        'id': player.id,
                        'number': player.currentNumber
                    }
            
            # Add defense info
            rosterDict['defense'] = {
                'passDefenseStars': round((((team.defensePassCoverageRating - 60)/40)*4)+1) if team.defensePassCoverageRating else 1,
                'runDefenseStars': round((((team.defenseRunCoverageRating - 60)/40)*4)+1) if team.defenseRunCoverageRating else 1,
                'passDefenseRating': team.defensePassCoverageRating,
                'runDefenseRating': team.defenseRunCoverageRating
            }
            
            # Add to roster history
            if not hasattr(team, 'rosterHistory'):
                team.rosterHistory = []
            
            team.rosterHistory.append({
                'season': self.currentSeason.seasonNumber,
                'roster': rosterDict
            })
            
            logger.debug(f"Saved roster history for {team.name}, season {self.currentSeason.seasonNumber}")
        
    def _initializeSeasonStats(self) -> None:
        """Initialize season statistics tracking"""
        # Save roster history for each team at the start of the season
        self._saveRosterHistory()
        
        # Initialize team season stats
        for team in self.leagueManager.teams:
            if not hasattr(team, 'seasonTeamStats'):
                team.seasonTeamStats = {
                    'wins': 0,
                    'losses': 0,
                    'winPerc': 0.0,
                    'streak': 0,
                    'scoreDiff': 0,
                    'Offense': {
                        'pts': 0,
                        'runTds': 0,
                        'passTds': 0,
                        'tds': 0,
                        'fgs': 0,
                        'passYards': 0,
                        'runYards': 0,
                        'totalYards': 0
                    },
                    'Defense': {
                        'ints': 0,
                        'fumRec': 0,
                        'sacks': 0,
                        'safeties': 0,
                        'runYardsAlwd': 0,
                        'passYardsAlwd': 0,
                        'totalYardsAlwd': 0,
                        'runTdsAlwd': 0,
                        'passTdsAlwd': 0,
                        'tdsAlwd': 0,
                        'ptsAlwd': 0
                    }
                }
            
            # Initialize additional team attributes that Game class may need
            if not hasattr(team, 'winningStreak'):
                team.winningStreak = False
    
    def _updateWeeklyStats(self) -> None:
        """Update weekly statistics and averages for teams and players"""
        # Update team averages (matches original)
        teamManager = self.serviceContainer.getService('team_manager')
        if teamManager:
            for team in teamManager.teams:
                if hasattr(team, 'getAverages'):
                    team.getAverages()
        
        # Sync stats dicts for all active players (postgameChanges is called per-game in floosball_game.py)
        for player in self.playerManager.activePlayers:
            if hasattr(player, 'sync_stats_dicts'):
                player.sync_stats_dicts()
        
        logger.debug(f"Updated weekly stats for week {self.currentSeason.currentWeek}")

    def _checkRecords(self) -> None:
        """Check for records after weekly games (matches original record checks)"""
        self.recordsManager.checkPlayerGameRecords()
        self.recordsManager.checkSeasonRecords(self.currentSeason.seasonNumber if self.currentSeason else 0)
        self.recordsManager.checkCareerRecords()
        
    def _updatePlayerPerformanceRatings(self, week: int) -> None:
        """Update player performance ratings for the given week (matches original getPerformanceRating call)"""
        self.playerManager.calculatePerformanceRatings(week)
        logger.debug(f"Updated player performance ratings for week {week}")

    async def _selectSeasonMVP(self) -> None:
        """Select the season MVP using z-score analysis of performance ratings across positions"""
        candidates = self.playerManager._computeMvpCandidates()
        if not candidates:
            logger.warning("Could not determine MVP — not enough eligible players")
            return

        winner = candidates[0]
        mvpPlayer = winner['player']

        # Award MVP to the player
        if not hasattr(mvpPlayer, 'mvpAwards'):
            mvpPlayer.mvpAwards = []
        mvpPlayer.mvpAwards.append({
            'Season': self.currentSeason.seasonNumber,
            'team': winner.get('teamAbbr', ''),
            'teamColor': winner.get('teamColor', '#334155')
        })

        # Store broadcast-safe version (no player object)
        mvpResult = dict(winner)
        mvpResult.pop('player', None)
        self.currentSeason.mvp = mvpResult
        logger.info(f"Season {self.currentSeason.seasonNumber} MVP: {mvpResult['name']} ({mvpResult['position']}, {mvpResult['team']}) — z-score: {mvpResult['zScore']}")

        # Broadcast MVP announcement
        if BROADCASTING_AVAILABLE and broadcaster.is_enabled() and SeasonEvent:
            await broadcaster.broadcast_season_event(
                SeasonEvent.mvpAnnouncement(mvpResult, self.currentSeason.seasonNumber)
            )

    # ─── Season Transition ──────────────────────────────────────────────────────

    def _processEndOfRegularSeason(self) -> None:
        """Clean up fantasy state at end of regular season (before playoffs).

        - Unequip all cards (deletes EquippedCard rows for the season)
        - Streak counts are on EquippedCard, so they're reset by deletion
        - Cards stay in user collections (UserCard untouched)
        """
        if not self.currentSeason:
            return

        seasonNum = self.currentSeason.seasonNumber
        try:
            from database.connection import get_session
            from database.models import EquippedCard

            session = get_session()
            try:
                deleted = session.query(EquippedCard).filter_by(season=seasonNum).delete()
                session.commit()
                logger.info(f"End of regular season S{seasonNum}: unequipped {deleted} cards")
            except Exception as e:
                session.rollback()
                logger.error(f"Error during end-of-regular-season cleanup: {e}")
            finally:
                session.close()
        except ImportError:
            pass

    def _handleRetiredPlayerRosters(self, retiredPlayerIds: set, nextSeason: int) -> None:
        """Remove retired players from fantasy rosters and auto-fill if enabled.

        Called during offseason after retirements are processed.
        """
        if not retiredPlayerIds:
            return

        try:
            from database.connection import get_session
            from database.models import FantasyRoster, FantasyRosterPlayer, Player, User

            session = get_session()
            try:
                # Find all roster slots containing retired players (from the most recent season)
                completedSeason = nextSeason - 1
                affectedSlots = (
                    session.query(FantasyRosterPlayer)
                    .join(FantasyRoster)
                    .filter(
                        FantasyRoster.season == completedSeason,
                        FantasyRosterPlayer.player_id.in_(retiredPlayerIds),
                    )
                    .all()
                )

                if not affectedSlots:
                    return

                # Group by roster for auto-fill processing
                rosterSlots: dict = {}  # rosterId → list of (slot, position)
                for rp in affectedSlots:
                    rosterSlots.setdefault(rp.roster_id, []).append(rp)

                # Get all rostered player IDs (to exclude from auto-fill candidates)
                allRosteredIds = {
                    rp.player_id
                    for rp in session.query(FantasyRosterPlayer.player_id)
                    .join(FantasyRoster)
                    .filter(FantasyRoster.season == completedSeason)
                    .all()
                }

                # Position mapping for slot names
                slotPositionMap = {"QB": 1, "RB": 2, "WR1": 3, "WR2": 3, "TE": 4, "K": 5}

                for rosterId, retiredSlots in rosterSlots.items():
                    roster = session.get(FantasyRoster, rosterId)
                    if not roster:
                        continue

                    user = session.get(User, roster.user_id)
                    autoFill = user.auto_fill_roster if user else True

                    for rp in retiredSlots:
                        retiredName = rp.player_id  # For logging
                        slot = rp.slot
                        session.delete(rp)
                        logger.info(f"Removed retired player {retiredName} from roster {rosterId} slot {slot}")

                        if autoFill:
                            posValue = slotPositionMap.get(slot)
                            if posValue is not None:
                                # Find best available player at this position
                                bestPlayer = (
                                    session.query(Player)
                                    .filter(
                                        Player.position == posValue,
                                        Player.is_active == True,
                                        ~Player.id.in_(allRosteredIds),
                                    )
                                    .order_by(Player.player_rating.desc())
                                    .first()
                                )
                                if bestPlayer:
                                    newRp = FantasyRosterPlayer(
                                        roster_id=rosterId,
                                        player_id=bestPlayer.id,
                                        slot=slot,
                                        points_at_lock=0.0,
                                    )
                                    session.add(newRp)
                                    allRosteredIds.add(bestPlayer.id)
                                    logger.info(f"Auto-filled {slot} with {bestPlayer.id} (rating {bestPlayer.player_rating})")

                session.commit()
                logger.info(f"Processed {len(affectedSlots)} retired player roster removals")
            except Exception as e:
                session.rollback()
                logger.error(f"Error handling retired player rosters: {e}")
                import traceback
                logger.debug(traceback.format_exc())
            finally:
                session.close()
        except ImportError:
            pass

    # ─── Weekly Modifier Selection ────────────────────────────────────────────

    MODIFIER_WEIGHTS = {
        "amplify": 10, "cascade": 8, "ironclad": 10, "overdrive": 10,
        "payday": 10, "grounded": 5, "wildcard": 8,
        "longshot": 10, "frenzy": 10, "synergy": 10, "steady": 10,
        "fortunate": 8,
    }

    MODIFIER_DISPLAY = {
        "amplify": "Amplify", "cascade": "Cascade", "ironclad": "Ironclad",
        "overdrive": "Overdrive", "payday": "Payday", "grounded": "Grounded",
        "wildcard": "Wildcard", "longshot": "Longshot",
        "frenzy": "Frenzy", "synergy": "Synergy", "steady": "Steady",
        "fortunate": "Fortunate",
    }

    MODIFIER_DESCRIPTIONS = {
        "amplify": "FPx bonus portions are doubled",
        "cascade": "FPx bonus portions are doubled",
        "ironclad": "Streak cards can't reset this week",
        "overdrive": "Match bonus is 2.5x instead of 1.5x",
        "payday": "Floobits earned are tripled",
        "grounded": "All FPx effects disabled",
        "wildcard": "All cards treated as matched",
        "longshot": "Conditional thresholds halved",
        "frenzy": "+FP values are doubled",
        "synergy": "Bonus FPx for each unique position in your card slots",
        "steady": "No special effect — all normal rules apply",
        "fortunate": "Chance card trigger rates increased by 15%",
    }

    def _selectWeeklyModifier(self, season: int, week: int) -> str:
        """Select a weekly modifier for the given season/week.

        Avoids repeats within the last 3 weeks. Stores the result in DB.
        Returns the modifier slug (e.g., "amplify").
        """
        import random as _random
        try:
            from database.connection import get_session
            from database.models import WeeklyModifier

            session = get_session()
            try:
                # Check if already selected (for resumability)
                existing = session.query(WeeklyModifier).filter_by(
                    season=season, week=week
                ).first()
                if existing:
                    logger.info(f"Weekly modifier already set for S{season}W{week}: {existing.modifier}")
                    return existing.modifier

                # Get recent modifiers to avoid repeats
                recentMods = (
                    session.query(WeeklyModifier.modifier)
                    .filter_by(season=season)
                    .filter(WeeklyModifier.week >= max(1, week - 3))
                    .filter(WeeklyModifier.week < week)
                    .all()
                )
                recentSet = {r[0] for r in recentMods}

                # Build weighted pool excluding recent
                pool = []
                weights = []
                for mod, weight in self.MODIFIER_WEIGHTS.items():
                    if mod not in recentSet:
                        pool.append(mod)
                        weights.append(weight)

                # If all modifiers are excluded (shouldn't happen with 11 mods and 3-week window), use full pool
                if not pool:
                    pool = list(self.MODIFIER_WEIGHTS.keys())
                    weights = list(self.MODIFIER_WEIGHTS.values())

                selected = _random.choices(pool, weights=weights, k=1)[0]

                # Persist
                session.add(WeeklyModifier(season=season, week=week, modifier=selected))
                session.commit()
                logger.info(f"Weekly modifier for S{season}W{week}: {self.MODIFIER_DISPLAY.get(selected, selected)}")
                return selected
            except Exception as e:
                session.rollback()
                logger.error(f"Error selecting weekly modifier: {e}")
                return "steady"  # Default to no effect
            finally:
                session.close()
        except ImportError:
            return "steady"

    # ─── Floobits Economy ─────────────────────────────────────────────────────

    def _awardFavoriteTeamBonus(self, teamId: int, amount: int, transactionType: str,
                                 description: str, season: int, week: int = None) -> int:
        """Award Floobits to all users whose favorite_team_id matches teamId.
        Returns the number of users rewarded."""
        try:
            from database.connection import get_session
            from database.models import User
            from database.repositories.card_repositories import CurrencyRepository

            session = get_session()
            try:
                users = session.query(User).filter_by(
                    favorite_team_id=teamId, is_active=True
                ).all()
                if not users:
                    session.close()
                    return 0
                currencyRepo = CurrencyRepository(session)
                from database.repositories.notification_repository import NotificationRepository
                notifRepo = NotificationRepository(session)
                count = 0
                for user in users:
                    currencyRepo.addFunds(
                        user.id, amount, transactionType,
                        description=description,
                        season=season, week=week,
                    )
                    notifRepo.create(
                        user.id, 'favorite_team',
                        'Team Bonus',
                        f'{description}! +{amount} Floobits',
                        data={'teamId': teamId, 'amount': amount},
                    )
                    count += 1
                session.commit()
                logger.info(f"Awarded {amount} Floobits ({transactionType}) to {count} users for team {teamId}")
                return count
            except Exception as e:
                session.rollback()
                logger.error(f"Error awarding favorite team bonus: {e}")
                return 0
            finally:
                session.close()
        except ImportError:
            return 0

    def _awardWeeklyLeaderboardPrizes(self, season: int, week: int) -> None:
        """Award Floobits to top leaderboard performers for the week."""
        from constants import (
            WEEKLY_LEADERBOARD_PRIZES, WEEKLY_LEADERBOARD_TOP_PCT_PRIZE,
            WEEKLY_LEADERBOARD_TOP_PCT,
        )

        fantasyTracker = self.serviceContainer.getService('fantasy_tracker')
        if not fantasyTracker:
            return

        try:
            snapshot = fantasyTracker.getSnapshot(season)
        except Exception as e:
            logger.error(f"Error getting snapshot for weekly leaderboard: {e}")
            return

        entries = snapshot.get('entries', [])
        if not entries:
            return

        # Sort by weekTotal descending for weekly ranking
        weekRanked = sorted(entries, key=lambda e: e['weekTotal'], reverse=True)

        totalEntries = len(weekRanked)
        top25Cutoff = max(3, int(totalEntries * WEEKLY_LEADERBOARD_TOP_PCT))

        try:
            from database.connection import get_session
            from database.repositories.card_repositories import CurrencyRepository

            session = get_session()
            try:
                currencyRepo = CurrencyRepository(session)
                from database.repositories.notification_repository import NotificationRepository
                notifRepo = NotificationRepository(session)
                awarded = 0
                for i, entry in enumerate(weekRanked):
                    userId = entry['userId']
                    weekRank = i + 1

                    if entry['weekTotal'] <= 0:
                        continue  # No prize for zero participation

                    prize = WEEKLY_LEADERBOARD_PRIZES.get(weekRank)
                    if prize is None and weekRank <= top25Cutoff and totalEntries >= 4:
                        prize = WEEKLY_LEADERBOARD_TOP_PCT_PRIZE

                    if not prize:
                        continue

                    currencyRepo.addFunds(
                        userId, prize, 'leaderboard_weekly',
                        description=f'Week {week} leaderboard #{weekRank}',
                        season=season, week=week,
                    )
                    notifRepo.create(
                        userId, 'leaderboard_weekly',
                        f'Week {week} Leaderboard',
                        f'You placed #{weekRank} on the Week {week} leaderboard! +{prize} Floobits',
                        data={'season': season, 'week': week, 'rank': weekRank, 'prize': prize},
                    )
                    awarded += 1
                    logger.info(f"Weekly leaderboard prize: user {userId} #{weekRank} = {prize} Floobits")

                session.commit()
                if awarded:
                    logger.info(f"Awarded weekly leaderboard prizes to {awarded} users for week {week}")

                # Email top-3 finishers
                try:
                    from managers.emailManager import sendPrizeEmails
                    sendPrizeEmails(
                        session, weekRanked,
                        WEEKLY_LEADERBOARD_PRIZES,
                        f'Week {week} leaderboard',
                        topN=3,
                    )
                except Exception as emailErr:
                    logger.warning(f"Error sending weekly prize emails: {emailErr}")
            except Exception as e:
                session.rollback()
                logger.error(f"Error awarding weekly leaderboard prizes: {e}")
            finally:
                session.close()
        except ImportError:
            pass

    def _awardSeasonEndPrizes(self, completedSeason: int) -> None:
        """Award season-end leaderboard prizes and FP-to-Floobits conversion."""
        import math
        from constants import (
            SEASON_LEADERBOARD_PRIZES, SEASON_LEADERBOARD_TOP_PCT_PRIZE,
            SEASON_LEADERBOARD_TOP_PCT, SEASON_FP_PAYOUT_DIVISOR,
        )

        fantasyTracker = self.serviceContainer.getService('fantasy_tracker')
        if not fantasyTracker:
            return

        try:
            snapshot = fantasyTracker.getSnapshot(completedSeason)
        except Exception as e:
            logger.error(f"Error getting snapshot for season-end prizes: {e}")
            return

        entries = snapshot.get('entries', [])
        if not entries:
            return

        # Entries are already sorted by seasonTotal descending from getSnapshot()
        totalEntries = len(entries)
        top25Cutoff = max(3, int(totalEntries * SEASON_LEADERBOARD_TOP_PCT))

        try:
            from database.connection import get_session
            from database.repositories.card_repositories import CurrencyRepository

            session = get_session()
            try:
                currencyRepo = CurrencyRepository(session)
                from database.repositories.notification_repository import NotificationRepository
                notifRepo = NotificationRepository(session)

                for i, entry in enumerate(entries):
                    userId = entry['userId']
                    seasonRank = i + 1
                    seasonTotal = entry['seasonTotal']

                    # --- Leaderboard prize ---
                    prize = SEASON_LEADERBOARD_PRIZES.get(seasonRank)
                    if prize is None and seasonRank <= top25Cutoff and totalEntries >= 4:
                        prize = SEASON_LEADERBOARD_TOP_PCT_PRIZE

                    if prize:
                        currencyRepo.addFunds(
                            userId, prize, 'leaderboard_season',
                            description=f'Season {completedSeason} leaderboard #{seasonRank}',
                            season=completedSeason,
                        )
                        notifRepo.create(
                            userId, 'leaderboard_season',
                            f'Season {completedSeason} Leaderboard',
                            f'You placed #{seasonRank} on the Season {completedSeason} leaderboard! +{prize} Floobits',
                            data={'season': completedSeason, 'rank': seasonRank, 'prize': prize},
                        )
                        logger.info(
                            f"Season leaderboard prize: user {userId} #{seasonRank} = {prize} Floobits"
                        )

                    # --- FP-to-Floobits conversion ---
                    fpPayout = math.floor(seasonTotal / SEASON_FP_PAYOUT_DIVISOR) if seasonTotal > 0 else 0
                    if fpPayout > 0:
                        currencyRepo.addFunds(
                            userId, fpPayout, 'season_fp_payout',
                            description=f'Season {completedSeason} FP payout ({seasonTotal:.0f} FP)',
                            season=completedSeason,
                        )
                        notifRepo.create(
                            userId, 'season_fp_payout',
                            f'Season {completedSeason} FP Payout',
                            f'Season {completedSeason} complete! Your {seasonTotal:.0f} FP earned you {fpPayout} Floobits',
                            data={'season': completedSeason, 'fp': seasonTotal, 'payout': fpPayout},
                        )
                        logger.info(
                            f"Season FP payout: user {userId} = {fpPayout} Floobits "
                            f"({seasonTotal:.0f} FP / {SEASON_FP_PAYOUT_DIVISOR})"
                        )

                session.commit()
                logger.info(f"Season-end prizes awarded for season {completedSeason}")

                # Email top-3 season finishers
                try:
                    from managers.emailManager import sendPrizeEmails
                    sendPrizeEmails(
                        session, entries,
                        SEASON_LEADERBOARD_PRIZES,
                        f'Season {completedSeason} leaderboard',
                        topN=3,
                    )
                except Exception as emailErr:
                    logger.warning(f"Error sending season prize emails: {emailErr}")
            except Exception as e:
                session.rollback()
                logger.error(f"Error awarding season-end prizes: {e}")
            finally:
                session.close()
        except ImportError:
            pass

    # ─── Awards ────────────────────────────────────────────────────────────────

    def _selectSeasonAllPro(self) -> None:
        """Select All-Pro players — top performer at each position from the current season."""
        candidates = self.playerManager._computeMvpCandidates()
        if not candidates:
            logger.warning("Could not determine All-Pro — not enough eligible players")
            return

        # Group by position, take the top candidate per position
        bestByPosition: dict = {}
        for c in candidates:
            pos = c['position']
            if pos not in bestByPosition:
                bestByPosition[pos] = c

        allProIds = {c['id'] for c in bestByPosition.values()}
        allProNames = [f"{c['name']} ({c['position']})" for c in bestByPosition.values()]

        self.currentSeason.allProPlayerIds = allProIds
        logger.info(f"Season {self.currentSeason.seasonNumber} All-Pro: {', '.join(allProNames)}")
    
    def _updateStandings(self) -> None:
        """Update league standings"""
        for league in self.leagueManager.leagues:
            league.getStandings()
    
    def updatePlayoffPicture(self) -> None:
        """Update playoff picture based on current standings (matches original Season.updatePlayoffPicture)"""
        if not self.currentSeason:
            return
            
        self.currentSeason.playoffTeams = {}
        nonPlayoffTeams = {}
        
        for league in self.leagueManager.leagues:
            # Sort teams by win percentage and score differential
            standings = league.getStandings()
            teams = [standing['team'] for standing in standings]
            
            # Split into playoff and non-playoff teams (half make playoffs)
            sliceIndex = len(teams) // 2
            playoffTeams = teams[:sliceIndex]
            nonPlayoffTeams_league = teams[sliceIndex:]
            
            self.currentSeason.playoffTeams[league.name] = playoffTeams
            nonPlayoffTeams[league.name] = nonPlayoffTeams_league
        
        # Store non-playoff teams for clinching logic
        self.currentSeason.nonPlayoffTeams = nonPlayoffTeams
    
    def checkForClinches(self) -> list:
        """Check for playoff clinches, top seed clinches, and eliminations mid-season.
        Delegates to leagueManager.checkPlayoffClinching() and returns new event texts to broadcast.
        """
        if not self.currentSeason:
            return []
        leagueHighlights = getattr(self.currentSeason, 'leagueHighlights', [])
        return self.leagueManager.checkPlayoffClinching(
            currentWeek=self.currentSeason.currentWeek,
            leagueHighlights=leagueHighlights
        )
    
    def saveSeasonStats(self) -> None:
        """Save season statistics to file (matches original Season.saveSeasonStats)"""
        if not self.currentSeason:
            return
            
        import json
        import os
        
        # Save season to database
        self._saveSeasonToDatabase()
        
        # Save team season stats to database
        self._saveTeamSeasonStatsToDatabase()
        
        # Save championships to Championship table
        self._saveChampionshipsToDatabase()
        
        # Accumulate season stats into all-time stats
        self._accumulateAllTimeStats()
        
        # Note: Season directories and JSON files disabled - data is in database
        # seasonDir = f'season{self.currentSeason.seasonNumber}'
        # if not os.path.exists(seasonDir):
        #     os.makedirs(seasonDir)
        
        # Save standings history
        standingsData = {}
        for league in self.leagueManager.leagues:
            standings = league.getStandings()
            standingsData[league.name] = []
            
            for standing in standings:
                team = standing['team']
                teamData = {
                    'name': f"{team.city} {team.name}",
                    'wins': standing['wins'],
                    'losses': standing['losses'],
                    'winPct': standing['winPct'],
                    'id': team.id
                }
                standingsData[league.name].append(teamData)
        
        # Note: Standings and highlights are now stored in the database, JSON output disabled
        # standingsFile = os.path.join(seasonDir, 'standings.json')
        # try:
        #     with open(standingsFile, 'w') as f:
        #         json.dump(standingsData, f, indent=4)
        #     logger.info(f"Saved season {self.currentSeason.seasonNumber} standings")
        # except Exception as e:
        #     logger.error(f"Failed to save standings: {e}")
        # 
        # if hasattr(self.currentSeason, 'leagueHighlights') and self.currentSeason.leagueHighlights:
        #     highlightsFile = os.path.join(seasonDir, 'highlights.json')
        #     try:
        #         from serializers import serialize_object
        #         serializedHighlights = serialize_object(self.currentSeason.leagueHighlights)
        #         with open(highlightsFile, 'w') as f:
        #             json.dump(serializedHighlights, f, indent=4)
        #         logger.info(f"Saved season {self.currentSeason.seasonNumber} highlights")
        #     except Exception as e:
        #         logger.error(f"Failed to save highlights: {e}")
    
    def _saveSeasonToDatabase(self) -> None:
        """Save season record to database"""
        if not DB_IMPORTS_AVAILABLE or not USE_DATABASE or not self.db_session:
            return
            
        try:
            from database.models import Season as DBSeason
            
            # Create or update season record
            db_season = self.db_session.query(DBSeason).filter_by(season_number=self.currentSeason.seasonNumber).first()
            
            if not db_season:
                db_season = DBSeason(
                    season_number=self.currentSeason.seasonNumber,
                    start_date=getattr(self.currentSeason, 'startDate', None),
                    current_week=self.currentSeason.currentWeek if isinstance(self.currentSeason.currentWeek, int) else 1,
                    playoffs_started=getattr(self.currentSeason, 'playoffsStarted', False)
                )
            else:
                db_season.current_week = self.currentSeason.currentWeek if isinstance(self.currentSeason.currentWeek, int) else 1
                db_season.playoffs_started = getattr(self.currentSeason, 'playoffsStarted', False)
                db_season.end_date = datetime.now()
            
            # Set champion team ID
            if hasattr(self.currentSeason, 'champion') and self.currentSeason.champion:
                db_season.champion_team_id = self.currentSeason.champion.id
            
            self.db_session.add(db_season)
            self.db_session.commit()
            logger.info(f"Saved season {self.currentSeason.seasonNumber} to database")
            
        except Exception as e:
            logger.error(f"Failed to save season to database: {e}")
            self.db_session.rollback()
    
    def _saveTeamSeasonStatsToDatabase(self) -> None:
        """Save team season stats to database including ELO"""
        if not DB_IMPORTS_AVAILABLE or not USE_DATABASE or not self.db_session:
            return
            
        try:
            from database.models import TeamSeasonStats as DBTeamSeasonStats
            
            teamManager = self.serviceContainer.getService('team_manager')
            if not teamManager:
                return
            
            for team in teamManager.teams:
                if not hasattr(team, 'seasonTeamStats'):
                    continue
                
                stats = team.seasonTeamStats
                
                # Create or update team season stats
                db_stats = self.db_session.query(DBTeamSeasonStats).filter_by(
                    team_id=team.id,
                    season=self.currentSeason.seasonNumber
                ).first()
                
                if not db_stats:
                    db_stats = DBTeamSeasonStats(
                        team_id=team.id,
                        season=self.currentSeason.seasonNumber
                    )
                
                # Update stats
                db_stats.elo = stats.get('elo', getattr(team, 'elo', 1500))
                db_stats.wins = stats.get('wins', 0)
                db_stats.losses = stats.get('losses', 0)
                db_stats.win_percentage = stats.get('winPerc', 0.0)
                db_stats.streak = stats.get('streak', 0)
                db_stats.score_differential = stats.get('scoreDiff', 0)
                db_stats.made_playoffs = stats.get('madePlayoffs', False)
                db_stats.league_champion = stats.get('leagueChamp', False)
                db_stats.floosball_champion = stats.get('floosbowlChamp', False)
                db_stats.top_seed = stats.get('topSeed', False)
                
                # Denormalized offensive stats
                offense = stats.get('Offense', {})
                db_stats.points = offense.get('pts', 0)
                db_stats.touchdowns = offense.get('tds', 0)
                db_stats.field_goals = offense.get('fgs', 0)
                db_stats.total_yards = offense.get('totalYards', 0)
                db_stats.passing_yards = offense.get('passYards', 0)
                db_stats.rushing_yards = offense.get('runYards', 0)
                db_stats.passing_tds = offense.get('passTds', 0)
                db_stats.rushing_tds = offense.get('runTds', 0)
                
                # Denormalized defensive stats
                defense = stats.get('Defense', {})
                db_stats.points_allowed = defense.get('ptsAlwd', 0)
                db_stats.sacks = defense.get('sacks', 0)
                db_stats.interceptions = defense.get('ints', 0)
                db_stats.fumbles_recovered = defense.get('fumRec', 0)
                db_stats.total_yards_allowed = defense.get('totalYardsAlwd', 0)
                
                # JSON for detailed breakdown
                db_stats.offense_stats = stats.get('Offense', {})
                db_stats.defense_stats = stats.get('Defense', {})
                
                self.db_session.add(db_stats)
            
            self.db_session.commit()
            logger.info(f"Saved team season stats for season {self.currentSeason.seasonNumber}")
            
        except Exception as e:
            logger.error(f"Failed to save team season stats: {e}")
            self.db_session.rollback()
    
    def _saveChampionshipsToDatabase(self) -> None:
        """Save championships to Championship table for efficient querying"""
        if not DB_IMPORTS_AVAILABLE or not USE_DATABASE or not self.db_session:
            return
            
        try:
            from database.models import Championship as DBChampionship
            
            teamManager = self.serviceContainer.getService('team_manager')
            if not teamManager:
                return
            
            for team in teamManager.teams:
                # Save top seeds
                if hasattr(team, 'topSeeds') and team.topSeeds:
                    for season_str in team.topSeeds:
                        season_num = int(season_str.replace('Season ', ''))
                        
                        # Check if already exists
                        existing = self.db_session.query(DBChampionship).filter_by(
                            team_id=team.id,
                            season=season_num,
                            championship_type='regular_season'
                        ).first()
                        
                        if not existing:
                            championship = DBChampionship(
                                team_id=team.id,
                                season=season_num,
                                championship_type='regular_season'
                            )
                            self.db_session.add(championship)
                
                # Save league championships (Floosbowl finalists)
                if hasattr(team, 'leagueChampionships') and team.leagueChampionships:
                    for season_str in team.leagueChampionships:
                        season_num = int(season_str.replace('Season ', ''))
                        
                        existing = self.db_session.query(DBChampionship).filter_by(
                            team_id=team.id,
                            season=season_num,
                            championship_type='league'
                        ).first()
                        
                        if not existing:
                            championship = DBChampionship(
                                team_id=team.id,
                                season=season_num,
                                championship_type='league'
                            )
                            self.db_session.add(championship)
                
                # Save Floosbowl championships (winners only)
                if hasattr(team, 'floosbowlChampionships') and team.floosbowlChampionships:
                    for season_str in team.floosbowlChampionships:
                        season_num = int(season_str.replace('Season ', ''))
                        
                        existing = self.db_session.query(DBChampionship).filter_by(
                            team_id=team.id,
                            season=season_num,
                            championship_type='floosbowl'
                        ).first()
                        
                        if not existing:
                            championship = DBChampionship(
                                team_id=team.id,
                                season=season_num,
                                championship_type='floosbowl'
                            )
                            self.db_session.add(championship)
            
            self.db_session.commit()
            logger.info(f"Saved championships for season {self.currentSeason.seasonNumber}")
            
        except Exception as e:
            logger.error(f"Failed to save championships: {e}")
            self.db_session.rollback()
    
    def _accumulateAllTimeStats(self) -> None:
        """Accumulate season stats into all-time stats (matches legacy floosball_legacy.py lines 459-469)"""
        teamManager = self.serviceContainer.getService('team_manager')
        if not teamManager:
            return
        
        for team in teamManager.teams:
            if not hasattr(team, 'seasonTeamStats') or not hasattr(team, 'allTimeTeamStats'):
                continue
            
            # Accumulate stats from season into all-time
            team.allTimeTeamStats['wins'] += team.seasonTeamStats['wins']
            team.allTimeTeamStats['losses'] += team.seasonTeamStats['losses']
            team.allTimeTeamStats['Offense']['tds'] += team.seasonTeamStats['Offense']['tds']
            team.allTimeTeamStats['Offense']['fgs'] += team.seasonTeamStats['Offense']['fgs']
            team.allTimeTeamStats['Offense']['passYards'] += team.seasonTeamStats['Offense']['passYards']
            team.allTimeTeamStats['Offense']['runYards'] += team.seasonTeamStats['Offense']['runYards']
            team.allTimeTeamStats['Offense']['totalYards'] += team.seasonTeamStats['Offense']['totalYards']
            team.allTimeTeamStats['Defense']['sacks'] += team.seasonTeamStats['Defense']['sacks']
            team.allTimeTeamStats['Defense']['ints'] += team.seasonTeamStats['Defense']['ints']
            team.allTimeTeamStats['Defense']['fumRec'] += team.seasonTeamStats['Defense']['fumRec']
            
            # Calculate all-time win percentage
            total_games = team.allTimeTeamStats['wins'] + team.allTimeTeamStats['losses']
            if total_games > 0:
                team.allTimeTeamStats['winPerc'] = round(team.allTimeTeamStats['wins'] / total_games, 3)
        
        logger.info("Accumulated season stats into all-time stats")
    
    def advanceToNextSeason(self) -> None:
        """Move to next season"""
        if self.currentSeason:
            self.currentSeason = None
        
        logger.info("Advanced to next season")
    
    def clearPlayerSeasonStats(self) -> None:
        """Clear and archive player season stats (matches original Season.clearPlayerSeasonStats)"""
        import copy
        
        for player in self.playerManager.activePlayers:
            if player.seasonsPlayed > 0:
                # Set final rating for the season
                player.seasonStatsDict['rating'] = player.playerTier.value
                
                # Archive the season stats
                seasonStatsCopy = copy.deepcopy(player.seasonStatsDict)
                
                # Remove old archive entry and insert new one at beginning
                if hasattr(player, 'seasonStatsArchive') and player.seasonStatsArchive:
                    player.seasonStatsArchive.pop(0)
                player.seasonStatsArchive.insert(0, seasonStatsCopy)
                
                # Reset season stats to default
                import floosball_player as FloosPlayer
                if hasattr(FloosPlayer, 'playerStatsDict'):
                    player.seasonStatsDict = copy.deepcopy(FloosPlayer.playerStatsDict)
                else:
                    # Default reset if playerStatsDict not available
                    player.seasonStatsDict = {
                        'passing': {'att': 0, 'comp': 0, 'yards': 0, 'tds': 0, 'ints': 0},
                        'rushing': {'carries': 0, 'yards': 0, 'tds': 0, 'fumblesLost': 0},
                        'receiving': {'targets': 0, 'receptions': 0, 'yards': 0, 'tds': 0},
                        'kicking': {'fgAtt': 0, 'fgs': 0, 'xpAtt': 0, 'xps': 0, 'fgYards': 0},
                        'defense': {'tackles': 0, 'sacks': 0, 'interceptions': 0, 'fumbleRecoveries': 0},
                        'fantasyPoints': 0,
                        'team': '',
                        'season': 0,
                        'rating': 0,
                        'gp': 0
                    }
                
                # Reset games played
                player.gamesPlayed = 0
        
        logger.info("Cleared player season stats")
    
    def clearTeamSeasonStats(self) -> None:
        """Clear and archive team season stats (matches original Season.clearTeamSeasonStats)"""
        import copy
        
        for team in self.leagueManager.teams:
            # Archive current season stats
            if hasattr(team, 'seasonTeamStats'):
                # Set final values
                team.seasonTeamStats['elo'] = getattr(team, 'elo', 1500)
                team.seasonTeamStats['overallRating'] = getattr(team, 'overallRating', 80)
                
                # Archive the stats
                if not hasattr(team, 'statArchive'):
                    team.statArchive = []
                team.statArchive.insert(0, team.seasonTeamStats.copy())
                
                # Reset season stats
                import floosball_team as FloosTeam
                if hasattr(FloosTeam, 'teamStatsDict'):
                    team.seasonTeamStats = copy.deepcopy(FloosTeam.teamStatsDict)
                else:
                    # Default reset if teamStatsDict not available
                    team.seasonTeamStats = {
                        'wins': 0,
                        'losses': 0,
                        'winPerc': 0.0,
                        'scoreDiff': 0,
                        'season': 0,
                        'Offense': {'totalYards': 0, 'tds': 0, 'pts': 0},
                        'Defense': {'ints': 0, 'fumRec': 0, 'sacks': 0}
                    }
            
            # Clear schedule
            if hasattr(team, 'schedule'):
                team.schedule = []
        
        logger.info("Cleared team season stats")
    
    def getSeasonStats(self) -> Dict[str, Any]:
        """Get current season statistics"""
        if not self.currentSeason:
            return {}
        
        stats = {
            'seasonNumber': self.currentSeason.seasonNumber,
            'currentWeek': self.currentSeason.currentWeek,
            'totalGames': len(self.currentSeason.schedule),
            'completedGames': len([g for g in self.currentSeason.schedule if g['completed']]),
            'isComplete': self.currentSeason.isComplete,
            'champion': self.currentSeason.champion.name if self.currentSeason.champion else None,
            'leagueChampions': {k: v.name for k, v in self.currentSeason.leagueChampions.items()}
        }
        
        return stats
    
    def getCurrentSeason(self) -> Optional[Season]:
        """Get current season object"""
        return self.currentSeason
    
    def getSeasonHistory(self) -> List[Season]:
        """Get all completed seasons"""
        return self.seasonHistory