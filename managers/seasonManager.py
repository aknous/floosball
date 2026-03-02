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
        self.activeGames = None
        self.schedule: List[Dict[str, FloosGame.Game]] = []
        self.playoffBracket: List[Dict[str, Any]] = []
        self.isComplete = False
        self.champion: Optional[FloosTeam.Team] = None
        self.leagueChampions: Dict[str, FloosTeam.Team] = {}
        self.playoffTeams: Dict[str, List[FloosTeam.Team]] = {}
        self.nonPlayoffTeams: Dict[str, List[FloosTeam.Team]] = {}
        self.leagueHighlights: List[Dict[str, Any]] = []
        self.freeAgencyOrder: List[FloosTeam.Team] = []

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

        logger.info("SeasonManager initialized")
    
    def setStateUpdateCallback(self, callback):
        """Set callback function for state updates"""
        self.stateUpdateCallback = callback
        logger.debug("State update callback registered")
    
    def setTimingMode(self, mode: TimingMode) -> None:
        """Set timing mode for simulation"""
        self.timingManager.setMode(mode)
        logger.info(f"Season timing mode set to {mode.value}")
    
    def setTimingModeFromString(self, mode_str: str) -> None:
        """Set timing mode from string (scheduled/sequential/turbo/fast)"""
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

        # Create new season schedule
        self.createSchedule()
        
        # Initialize season stats
        self._initializeSeasonStats()
        
        logger.info(f"Season {seasonNumber} initialized with {len(self.currentSeason.schedule)} games")
    
    async def runSeasonSimulation(self) -> None:
        """Run full season simulation"""
        if not self.currentSeason:
            logger.error("No current season to simulate")
            return
            
        logger.info(f"Running simulation for season {self.currentSeason.seasonNumber}")
        
        # Reset game counter for verbose logging
        self.games_simulated_this_season = 0
        
        # Open game stats file
        self._openGameStatsFile()
        
        # Simulate regular season
        await self._simulateRegularSeason()
        
        # Simulate playoffs
        await self._simulatePlayoffs()
        
        # Close game stats file
        self._closeGameStatsFile()
        
        # Handle season completion
        await self._completeSeasonSimulation()
        
        logger.info(f"Season {self.currentSeason.seasonNumber} simulation complete")
    
    async def _simulateRegularSeason(self) -> None:
        """Simulate all regular season games"""
        strCurrentSeason = 'season{}'.format(self.currentSeason.seasonNumber)
        # weekFilePath = '{}/games'.format(strCurrentSeason)
        
        # Note: Season directory creation disabled - data is in database
        # if not os.path.isdir(strCurrentSeason):
        #     os.mkdir(strCurrentSeason)
        # if not os.path.isdir(weekFilePath):
        #     os.mkdir(weekFilePath)
        
        for week in self.currentSeason.schedule:
            self.currentSeason.currentWeek = self.currentSeason.schedule.index(week)+1
            self.currentSeason.currentWeekText = f'Week {self.currentSeason.currentWeek}'
            logger.info(f"Simulating week {self.currentSeason.currentWeek} in {self.timingManager.getModeString()} mode")
            
            # Broadcast week start event
            if BROADCASTING_AVAILABLE and broadcaster.is_enabled():
                week_event = SeasonEvent.weekStart(
                    seasonNumber=self.currentSeason.seasonNumber,
                    weekNumber=self.currentSeason.currentWeek,
                    games=[]  # Could populate with game info if needed
                )
                broadcaster.broadcast_sync('season', week_event)
            
            weekStartTime = week['startTime']
            weekSetupTime = weekStartTime - datetime.timedelta(minutes=10)
            self.currentSeason.activeGames = week['games']

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

            # Add game start highlight
            if hasattr(self.currentSeason, 'leagueHighlights'):
                self.currentSeason.leagueHighlights.insert(0, {
                    'event': {'text': f'{self.currentSeason.currentWeekText} Start'}
                })

            # Simulate games in the week concurrently (like original)
            weekGames = week['games']

            # Create tasks for all games in the week to run concurrently
            gameTasks = [self._simulateGame(game) for game in weekGames]

            # Wait for all games in the week to complete concurrently
            await asyncio.gather(*gameTasks)
            
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

            # Broadcast any new clinch/elimination events
            if BROADCASTING_AVAILABLE and broadcaster.is_enabled() and LeagueNewsEvent:
                for text in newClinchEvents:
                    await broadcaster.broadcast_season_event(LeagueNewsEvent.leagueNews(text))

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

            # Add game end highlight
            if hasattr(self.currentSeason, 'leagueHighlights'):
                self.currentSeason.leagueHighlights.insert(0, {
                    'event': {'text': f'{self.currentSeason.currentWeekText} End'}
                })

            # Wait after week completes
            await self.timingManager.waitAfterWeek()
    
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
            
            # Simulate the game
            await gameInstance.playGame()
            
            # Update team records
            self._updateTeamRecords(gameInstance)
            
            # Process post-game statistics (replaces original postgame() method)
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

            # Save game to database if enabled
            if DB_IMPORTS_AVAILABLE and USE_DATABASE and self.game_repo:
                self._saveGameToDatabase(gameInstance)

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
                except Exception:
                    pass

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
    
    async def _onWeekComplete(self, week: int, in_playoffs: bool, playoff_round: Optional[str] = None) -> None:
        """Called after each week completes - triggers state save"""
        if self.stateUpdateCallback:
            await self.stateUpdateCallback(
                current_season=self.currentSeason.seasonNumber,
                current_week=week,
                in_playoffs=in_playoffs,
                playoff_round=playoff_round
            )
    
    def _saveGameToDatabase(self, game: FloosGame.Game) -> None:
        """Save a completed game to the database"""
        try:
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
            
            self.game_repo.save(db_game)
            self.db_session.flush()  # Get the ID
            
            # Save player stats if available
            if hasattr(game, 'playerStats') and game.playerStats:
                self._savePlayerGameStats(db_game.id, game.playerStats)
            
            # Don't commit yet - will batch commit at end of week
            self.db_session.flush()  # Flush to get IDs but don't commit
            logger.debug(f"Saved game to database: {game.awayTeam.abbr} @ {game.homeTeam.abbr}, Score: {game.awayScore}-{game.homeScore}")
            
        except Exception as e:
            logger.error(f"Failed to save game to database: {e}")
            self.db_session.rollback()
    
    def _savePlayerGameStats(self, game_id: int, player_stats: Dict) -> None:
        """Save player game statistics to database"""
        try:
            for player_id, stats in player_stats.items():
                if isinstance(stats, dict):
                    db_stats = DBGamePlayerStats(
                        game_id=game_id,
                        player_id=player_id,
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
                    homeTeam.schedule.append(newGame)
                    awayTeam.schedule.append(newGame)
                    gameList.append(newGame)
                self.currentSeason.schedule.append({'startTime': weekStartTime, 'games': gameList})
                

        logger.info(f"Created {numOfWeeks}-week schedule with {len(self.currentSeason.schedule)} games")


    def getWeekStartTime(self, now:datetime.datetime, week:int):
        dateNow = datetime.datetime.now()
        dateNowUtc = datetime.datetime.utcnow()
        if dateNow.day == dateNowUtc.day:
            utcOffset = dateNowUtc.hour - dateNow.hour
        elif dateNowUtc.day > dateNow.day:
            utcOffset = (dateNowUtc.hour + 24) - dateNow.hour
        elif dateNow.day > dateNowUtc.day:
            utcOffset = dateNowUtc.hour - (dateNow.hour + 24)

        startDay = 4
        monthDays = 0
        startTimeHoursList = [11, 12, 13, 14, 15, 16, 17]

        if now.month == 1 or now.month == 3 or now.month == 5 or now.month == 7 or now.month == 8 or now.month == 10 or now.month == 12:
            monthDays = 31
        elif now.month == 4 or now.month == 6 or now.month == 9 or now.month == 11:
            monthDays = 30
        elif now.month == 2:
            if (now.year % 4) == 0:
                monthDays = 29
            else:
                monthDays = 28

        startTimeHour = startTimeHoursList[week%7]


        todayWeekDay = dateNowUtc.isoweekday()

        if week > 28:
            if week == 32:
                if todayWeekDay == startDay + 5:
                    startDayOffset = 0
                else:
                    startDayOffset = (startDay + 5) - todayWeekDay
            else:
                if todayWeekDay == startDay + 5:
                    startDayOffset = startDay + 4
                elif todayWeekDay == startDay + 4:
                    startDayOffset = 0
                else:
                    startDayOffset = (startDay + 4) - todayWeekDay
            dayOffset = startDayOffset
        else:
            if todayWeekDay == startDay - 1:
                startDayOffset = startDay - 1
            elif todayWeekDay == startDay:
                startDayOffset = 0
            else:
                startDayOffset = startDay + 7 - todayWeekDay

            dayOffset = math.floor((week)/7) + startDayOffset


        adjustedHour = (startTimeHour + utcOffset) % 24

        if (now.day + dayOffset) > monthDays:
            if now.month + 1 > 12:
                return datetime.datetime(now.year + 1, 1, dayOffset - (monthDays - now.day), adjustedHour)
            else:
                return datetime.datetime(now.year, now.month + 1, dayOffset - (monthDays - now.day), adjustedHour)
        else:
            return datetime.datetime(now.year, now.month, now.day + dayOffset, adjustedHour)
    
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
        
        return schedule
    
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

            self.currentSeason.leagueHighlights.insert(0, {'event': {'text': '{} Starting Soon...'.format(self.currentWeekText)}})

            #await asyncio.sleep(30)
            # while datetime.datetime.utcnow() < roundStartTime:
            #     await asyncio.sleep(30)
                
            self.currentSeason.leagueHighlights.insert(0, {'event': {'text': '{} Start'.format(self.currentWeekText)}})
            await asyncio.gather(*playoffGamesTasks)

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
            
            # Simulate the game
            await gameInstance.playGame()
            
            # Determine winner
            winner = game.homeTeam if gameInstance.homeScore > gameInstance.awayScore else game.awayTeam
            
            # Update team records
            self._updateTeamRecords(gameInstance)
            
            # Process post-game statistics (replaces original postgame() method)
            self.recordsManager.processPostGameStats(gameInstance)
            
            # Update ELO ratings based on playoff game result
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
            
            # Save playoff game to database if enabled
            if DB_IMPORTS_AVAILABLE and USE_DATABASE and self.game_repo:
                self._saveGameToDatabase(gameInstance)
            
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
        for player in self.playerManager.activePlayers:
            if hasattr(player, 'offseasonTraining'):
                player.offseasonTraining()
        
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
        
        logger.info("Offseason activities complete")
    
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
                player.seasonStatsArchive.append(player.seasonStatsDict.copy())
            
            # Reset season stats for next year
            if hasattr(player, 'seasonStatsDict'):
                # Reset to default structure
                player.seasonStatsDict = {
                    'passing': {'att': 0, 'comp': 0, 'yards': 0, 'tds': 0, 'ints': 0},
                    'rushing': {'carries': 0, 'yards': 0, 'tds': 0, 'fumblesLost': 0},
                    'receiving': {'targets': 0, 'receptions': 0, 'yards': 0, 'tds': 0},
                    'kicking': {'fgAtt': 0, 'fgs': 0, 'xpAtt': 0, 'xps': 0, 'fgYards': 0},
                    'defense': {'tackles': 0, 'sacks': 0, 'interceptions': 0, 'fumbleRecoveries': 0},
                    'fantasyPoints': 0,
                    'team': player.team.name if hasattr(player.team, 'name') else str(player.team)
                }
    
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