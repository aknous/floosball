"""
SeasonManager - Manages season simulation, scheduling, and progression
Replaces the scattered season-related functions and global variables from floosball.py
"""

import math
from typing import List, Dict, Any, Optional, Tuple
import asyncio
import datetime
import floosball_team as FloosTeam
import floosball_player as FloosPlayer
import floosball_game as FloosGame
from logger_config import get_logger
from .timingManager import TimingManager, TimingMode

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

class SeasonManager:
    """Manages season simulation, scheduling, and progression"""
    
    def __init__(self, serviceContainer, leagueManager, playerManager, recordsManager):
        self.serviceContainer = serviceContainer
        self.leagueManager = leagueManager
        self.playerManager = playerManager
        self.recordsManager = recordsManager
        
        self.currentSeason: Optional[Season] = None
        self.seasonHistory: List[Season] = []

        # Initialize timing manager with default fast mode
        self.timingManager = TimingManager(TimingMode.FAST)
        
        logger.info("SeasonManager initialized")
    
    def setTimingMode(self, mode: TimingMode) -> None:
        """Set timing mode for simulation"""
        self.timingManager.setMode(mode)
        logger.info(f"Season timing mode set to {mode.value}")
    
    def setTimingModeFromString(self, mode_str: str) -> None:
        """Set timing mode from string (scheduled/sequential/fast)"""
        mode_str = mode_str.lower()
        if mode_str == 'scheduled':
            self.setTimingMode(TimingMode.SCHEDULED)
        elif mode_str == 'sequential':
            self.setTimingMode(TimingMode.SEQUENTIAL)
        elif mode_str == 'fast':
            self.setTimingMode(TimingMode.FAST)
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

        if seasonNumber > 1:
            # Handle offseason activities
            await self._handleOffseason()

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
        
        # Simulate regular season
        await self._simulateRegularSeason()
        
        # Simulate playoffs
        await self._simulatePlayoffs()
        
        # Handle season completion
        await self._completeSeasonSimulation()
        
        logger.info(f"Season {self.currentSeason.seasonNumber} simulation complete")
    
    async def _simulateRegularSeason(self) -> None:
        """Simulate all regular season games"""
        for week in self.currentSeason.schedule:
            self.currentSeason.currentWeek = self.currentSeason.schedule.index(week)+1
            self.currentSeason.currentWeekText = f'Week {self.currentSeason.currentWeek}'
            logger.info(f"Simulating week {self.currentSeason.currentWeek} in {self.timingManager.getModeString()} mode")
            weekStartTime = week['startTime']
            weekSetupTime = weekStartTime - datetime.timedelta(minutes=10)

            # Wait for week setup time
            await self.timingManager.waitForWeekSetup(weekSetupTime)

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

            # Post-week processing (matches original floosball.py lines 688-699)
            self._updateWeeklyStats()
            self._updateStandings()

            # Update player performance ratings for the week
            self._updatePlayerPerformanceRatings(week)

            # Sort players and defenses (matches original)
            self.playerManager.sortPlayersByPosition()
            teamManager = self.serviceContainer.getService('team_manager')
            if teamManager:
                teamManager.sortDefenses()

            # Update playoff picture and check for clinches (matches original)
            self.updatePlayoffPicture()
            self.checkForClinches()

            # Additional record checks (matches original)
            self.recordsManager.checkCareerRecords()
            self.recordsManager.checkSeasonRecords(self.currentSeason.seasonNumber)

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
        
        # Determine playoff teams
        playoffTeams = self.leagueManager.getPlayoffTeams()
        
        # Create playoff bracket
        self._createPlayoffBracket(playoffTeams)
        
        # Simulate playoff rounds
        await self._simulatePlayoffRounds()

    async def _simulateGame(self, game: FloosGame.Game) -> None:
        """Simulate a single game"""
        
        try:
            # Create game instance with timing manager
            gameInstance = game
            
            # Simulate the game
            await gameInstance.playGame()
            
            # Update team records
            self._updateTeamRecords(gameInstance)
            
            # Process post-game statistics (replaces original postgame() method)
            self.recordsManager.processPostGameStats(gameInstance)
            
            # Update ELO ratings based on game result
            teamManager = self.serviceContainer.getService('team_manager')
            if teamManager and hasattr(gameInstance, 'winningTeam') and gameInstance.winningTeam:
                teamManager.updateEloAfterGame(
                    gameInstance.homeTeam, 
                    gameInstance.awayTeam, 
                    gameInstance.homeScore, 
                    gameInstance.awayScore, 
                    gameInstance.winningTeam,
                    getattr(gameInstance, 'homeTeamWinProbability', None),
                    getattr(gameInstance, 'awayTeamWinProbability', None)
                )
            
            # Check for records
            self.recordsManager.checkPlayerGameRecords()
            self.recordsManager.checkTeamGameRecords(gameInstance)
            
        except Exception as e:
            logger.error(f"Error simulating game: {e}")
    
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
            
            # Update records based on game result
            if game.homeScore > game.awayScore:
                # Home team wins
                homeTeam.seasonTeamStats['wins'] += 1
                awayTeam.seasonTeamStats['losses'] += 1
            else:
                # Away team wins
                awayTeam.seasonTeamStats['wins'] += 1
                homeTeam.seasonTeamStats['losses'] += 1
            
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
                    newGame.id = 's{0}w{1}g{2}'.format(self.currentSeason, week, newGame)
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


        if (now.day + dayOffset) > monthDays:
            if now.month + 1 > 12:
                return datetime.datetime(now.year + 1, 1, dayOffset - (monthDays - now.day), startTimeHour)
            else:
                return datetime.datetime(now.year, now.month + 1, dayOffset - (monthDays - now.day), startTimeHour)
        else:
            if startTimeHour + utcOffset == 24:
                return datetime.datetime(now.year, now.month, now.day + dayOffset, 0)
            else:
                return datetime.datetime(now.year, now.month, now.day + dayOffset, startTimeHour + utcOffset)
    
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
    
    def _createPlayoffBracket(self, playoffTeams: Dict[str, List[FloosTeam.Team]]) -> None:
        """Create playoff bracket from qualified teams"""
        bracket = []
        
        # Simple single-elimination bracket
        for leagueName, teams in playoffTeams.items():
            if len(teams) >= 2:
                # Create semi-final matchups
                for i in range(0, len(teams), 2):
                    if i + 1 < len(teams):
                        matchup = {
                            'homeTeam': teams[i],
                            'awayTeam': teams[i + 1],
                            'round': 'semifinals',
                            'league': leagueName,
                            'completed': False,
                            'winner': None
                        }
                        bracket.append(matchup)
        
        self.currentSeason.playoffBracket = bracket
        logger.info(f"Created playoff bracket with {len(bracket)} matchups")
    
    async def _simulatePlayoffRounds(self) -> None:
        """Simulate all playoff rounds"""
        currentRound = 'semifinals'
        
        while True:
            # Get games for current round
            roundGames = [game for game in self.currentSeason.playoffBracket 
                         if game['round'] == currentRound and not game['completed']]
            
            if not roundGames:
                break
                
            logger.info(f"Simulating {currentRound}")
            
            # Simulate round games concurrently (like original)
            gameResultTasks = [self._simulatePlayoffGame(game) for game in roundGames]
            
            # Wait for all games in the round to complete concurrently
            roundResults = await asyncio.gather(*gameResultTasks)
            
            # Collect winners
            roundWinners = []
            for winner in roundResults:
                if winner:
                    roundWinners.append(winner)
            
            # Create next round if needed
            if len(roundWinners) > 1:
                nextRound = 'finals' if currentRound == 'semifinals' else 'championship'
                
                # Wait between playoff rounds
                await self.timingManager.waitForPlayoffRound()
                
                # Pair winners for next round
                for i in range(0, len(roundWinners), 2):
                    if i + 1 < len(roundWinners):
                        nextGame = {
                            'homeTeam': roundWinners[i],
                            'awayTeam': roundWinners[i + 1],
                            'round': nextRound,
                            'league': 'championship',
                            'completed': False,
                            'winner': None
                        }
                        self.currentSeason.playoffBracket.append(nextGame)
                
                currentRound = nextRound
                
                # Extra delay for championship game
                if nextRound == 'championship':
                    await self.timingManager.waitForChampionship()
            elif len(roundWinners) == 1:
                # Single champion
                self.currentSeason.champion = roundWinners[0]
                break
            else:
                break
    
    async def _simulatePlayoffGame(self, game: Dict[str, Any]) -> Optional[FloosTeam.Team]:
        """Simulate a single playoff game"""
        
        try:
            # Create game instance with timing manager
            gameInstance = FloosGame.Game(game['homeTeam'], game['awayTeam'], self.timingManager)
            
            # Set game type (playoff games)
            gameInstance.isRegularSeasonGame = False
            
            # Simulate the game
            await gameInstance.playGame()
            
            # Determine winner
            winner = game['homeTeam'] if gameInstance.homeScore > gameInstance.awayScore else game['awayTeam']
            
            # Update game result
            game['completed'] = True
            game['winner'] = winner
            game['result'] = gameInstance
            
            # Update team records
            self._updateTeamRecords(gameInstance)
            
            # Process post-game statistics (replaces original postgame() method)
            self.recordsManager.processPostGameStats(gameInstance)
            
            # Update ELO ratings based on playoff game result
            teamManager = self.serviceContainer.getService('team_manager')
            if teamManager and hasattr(gameInstance, 'winningTeam') and gameInstance.winningTeam:
                teamManager.updateEloAfterGame(
                    gameInstance.homeTeam, 
                    gameInstance.awayTeam, 
                    gameInstance.homeScore, 
                    gameInstance.awayScore, 
                    gameInstance.winningTeam,
                    getattr(gameInstance, 'homeTeamWinProbability', None),
                    getattr(gameInstance, 'awayTeamWinProbability', None)
                )
            
            # Check for records
            self.recordsManager.checkPlayerGameRecords()
            self.recordsManager.checkTeamGameRecords(gameInstance)
            
            logger.info(f"Playoff game complete: {winner.name} advances")
            return winner
            
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
        
        # Handle player offseason activities
        self.playerManager.handleOffseasonActivities()
        
        # Handle free agency and contracts
        await self._processFreeAgency()
        
        # Handle rookie draft if applicable
        await self._processRookieDraft()
        
        # Update team ratings based on roster changes
        await self._updateTeamRatings()
        
        logger.info("Offseason activities complete")
    
    async def _processFreeAgency(self) -> None:
        """Process free agency period"""
        logger.info("Processing free agency")
        
        # Get contract manager if available
        try:
            contractManager = self.serviceContainer.getService('contract_manager')
            await contractManager.handleFreeAgency()
        except ValueError:
            # Basic free agency handling without contract manager
            await self._basicFreeAgencyHandling()
    
    async def _basicFreeAgencyHandling(self) -> None:
        """Basic free agency handling without contract manager"""
        # Move expired contract players to free agency
        for player in self.playerManager.activePlayers:
            if hasattr(player, 'termRemaining') and player.termRemaining <= 0:
                if player not in self.playerManager.freeAgents:
                    player.team = 'Free Agent'
                    self.playerManager.freeAgents.append(player)
    
    async def _processRookieDraft(self) -> None:
        """Process rookie draft if new players are needed"""
        # Simple logic: generate rookies if roster sizes are low
        totalRosterSpots = len(self.leagueManager.teams) * 6  # 6 players per team
        currentPlayers = len(self.playerManager.activePlayers)
        
        if currentPlayers < totalRosterSpots * 0.8:  # If rosters are less than 80% full
            logger.info("Generating rookie class")
            
            # Generate new rookies
            rookiesNeeded = max(5, (totalRosterSpots - currentPlayers) // 2)
            
            for _ in range(rookiesNeeded):
                # Create rookie player (position random)
                import random
                positions = [FloosPlayer.Position.QB, FloosPlayer.Position.RB, 
                           FloosPlayer.Position.WR, FloosPlayer.Position.TE, FloosPlayer.Position.K]
                position = random.choice(positions)
                
                rookie = self.playerManager.createPlayer(position, random.randint(60, 90))
                if rookie:
                    rookie.serviceTime = FloosPlayer.PlayerServiceTime.Rookie
                    self.playerManager.rookieDraftList.append(rookie)
            
            logger.info(f"Generated {len(self.playerManager.rookieDraftList)} rookies")
    
    async def _updateTeamRatings(self) -> None:
        """Update team ratings based on current rosters"""
        teamManager = self.serviceContainer.getService('team_manager')
        if teamManager:
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
            
            # Update service time
            if hasattr(player, 'serviceTime'):
                if player.seasonsPlayed >= 3 and player.serviceTime == FloosPlayer.PlayerServiceTime.Rookie:
                    player.serviceTime = FloosPlayer.PlayerServiceTime.Veteran1
            
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
        
    def _initializeSeasonStats(self) -> None:
        """Initialize season statistics tracking"""
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
        
        # Update player game stats and development
        for player in self.playerManager.activePlayers:
            if hasattr(player, 'postgameChanges'):
                player.postgameChanges()
            if hasattr(player, 'sync_stats_dicts'):
                player.sync_stats_dicts()
        
        logger.debug(f"Updated weekly stats for week {self.currentSeason.currentWeek}")
        
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
    
    def checkForClinches(self) -> None:
        """Check for playoff clinches and top seed clinches (matches original Season.checkForClinches)"""
        if not self.currentSeason or not hasattr(self.currentSeason, 'playoffTeams'):
            return
            
        remainingWeeks = 28 - self.currentSeason.currentWeek if self.currentSeason.currentWeek else 28
        
        for league in self.leagueManager.leagues:
            standings = league.getStandings()
            if len(standings) < 2:
                continue
                
            team1 = standings[0]['team']  # First place team
            team2 = standings[1]['team']  # Second place team
            
            playoffTeamList = self.currentSeason.playoffTeams.get(league.name, [])
            nonPlayoffTeamsList = self.currentSeason.nonPlayoffTeams.get(league.name, [])
            
            # Check for top seed clinch
            if not getattr(team1, 'clinchedTopSeed', False):
                team1_wins = team1.seasonTeamStats.get('wins', 0) if hasattr(team1, 'seasonTeamStats') else 0
                team2_wins = team2.seasonTeamStats.get('wins', 0) if hasattr(team2, 'seasonTeamStats') else 0
                
                # Simple clinch check: if team1 wins + remaining weeks < team2 max possible wins
                if team1_wins > team2_wins + remainingWeeks or remainingWeeks == 0:
                    team1.clinchedTopSeed = True
                    if hasattr(self.currentSeason, 'leagueHighlights'):
                        highlight = {
                            'event': {
                                'text': f'{team1.city} {team1.name} have clinched the #1 seed'
                            }
                        }
                        self.currentSeason.leagueHighlights.insert(0, highlight)
            
            # Check for playoff clinches on final week
            if remainingWeeks == 0:  # Final week
                for team in playoffTeamList:
                    if not getattr(team, 'clinchedPlayoffs', False):
                        team.clinchedPlayoffs = True
                        if hasattr(self.currentSeason, 'leagueHighlights'):
                            highlight = {
                                'event': {
                                    'text': f'{team.city} {team.name} have clinched a playoff berth'
                                }
                            }
                            self.currentSeason.leagueHighlights.insert(0, highlight)
                
                # Mark eliminated teams
                for team in nonPlayoffTeamsList:
                    if not getattr(team, 'eliminated', False):
                        team.eliminated = True
    
    def saveSeasonStats(self) -> None:
        """Save season statistics to file (matches original Season.saveSeasonStats)"""
        if not self.currentSeason:
            return
            
        import json
        import os
        
        # Create season directory
        seasonDir = f'season{self.currentSeason.seasonNumber}'
        if not os.path.exists(seasonDir):
            os.makedirs(seasonDir)
        
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
        
        # Save standings to file
        standingsFile = os.path.join(seasonDir, 'standings.json')
        try:
            with open(standingsFile, 'w') as f:
                json.dump(standingsData, f, indent=4)
            logger.info(f"Saved season {self.currentSeason.seasonNumber} standings")
        except Exception as e:
            logger.error(f"Failed to save standings: {e}")
        
        # Save season highlights if available
        if hasattr(self.currentSeason, 'leagueHighlights') and self.currentSeason.leagueHighlights:
            highlightsFile = os.path.join(seasonDir, 'highlights.json')
            try:
                with open(highlightsFile, 'w') as f:
                    json.dump(self.currentSeason.leagueHighlights, f, indent=4)
                logger.info(f"Saved season {self.currentSeason.seasonNumber} highlights")
            except Exception as e:
                logger.error(f"Failed to save highlights: {e}")
    
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