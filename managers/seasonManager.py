"""
SeasonManager - Manages season simulation, scheduling, and progression
Replaces the scattered season-related functions and global variables from floosball.py
"""

import math
import os
import json
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
        strCurrentSeason = 'season{}'.format(self.currentSeason.seasonNumber)
        weekFilePath = '{}/games'.format(strCurrentSeason)
        
        # Create games directory if it doesn't exist
        if not os.path.isdir(strCurrentSeason):
            os.mkdir(strCurrentSeason)
        if not os.path.isdir(weekFilePath):
            os.mkdir(weekFilePath)
        
        for week in self.currentSeason.schedule:
            self.currentSeason.currentWeek = self.currentSeason.schedule.index(week)+1
            self.currentSeason.currentWeekText = f'Week {self.currentSeason.currentWeek}'
            logger.info(f"Simulating week {self.currentSeason.currentWeek} in {self.timingManager.getModeString()} mode")
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

            # Save week's game data to file (matches original startSeason)
            gameDict = {}
            for game_idx, game in enumerate(weekGames):
                strGame = f'Game {game_idx + 1}'
                gameResults = game.gameDict
                gameDict[strGame] = gameResults
            
            from serializers import serialize_object
            weekDict = serialize_object(gameDict)
            jsonFile = open(os.path.join(weekFilePath, '{}.json'.format(self.currentSeason.currentWeekText)), "w+")
            jsonFile.write(json.dumps(weekDict, indent=4))
            jsonFile.close()

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
            self.checkForClinches()
            self._checkRecords()

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
                    self.currentSeason.leagueHighlights.insert(0, {'event': {'text': '{0} {1} have clinched a playoff berth'.format(team.city, team.name)}})

        for team in nonPlayoffTeamList:
            team: FloosTeam.Team
            team.winningStreak = False
            if not team.eliminated:
                team.eliminated = True
                team.clinchedPlayoffs = False
                self.currentSeason.leagueHighlights.insert(0, {'event': {'text': '{0} {1} have faded from playoff contention'.format(team.city, team.name)}})
        

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
                        newGame = FloosGame.Game(teamsInRound[hiSeed], teamsInRound[lowSeed])
                        newGame.id = 's{0}r{1}g{2}'.format(self.currentSeason, currentRound, gameNumber)
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
                newGame = FloosGame.Game(floosbowlTeams[0], floosbowlTeams[1])
                newGame.id = 's{0}r{1}g{2}'.format(self.currentSeason, currentRound, gameNumber)
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

            self.activeGames = playoffGamesList
            self.currentSeason.schedule.append({'startTime': roundStartTime, 'games': playoffGamesList})

            self.currentSeason.leagueHighlights.insert(0, {'event': {'text': '{} Starting Soon...'.format(self.currentWeekText)}})

            #await asyncio.sleep(30)
            # while datetime.datetime.utcnow() < roundStartTime:
            #     await asyncio.sleep(30)
                
            self.currentSeason.leagueHighlights.insert(0, {'event': {'text': '{} Start'.format(self.currentWeekText)}})
            await asyncio.gather(*playoffGamesTasks)

            if len(playoffGamesList) == 1:
                game: FloosGame.Game = playoffGamesList[0]
                playoffTeamsList.clear()
                game.winningTeam.leagueChampionships.append('Season {}'.format(self.currentSeason.seasonNumber))
                game.winningTeam.floosbowlChampion = True
                self.currentSeason.champion = game.winningTeam
                runnerUp: FloosTeam.Team = game.losingTeam
                runnerUp.eliminated = True
                self.currentSeason.leagueHighlights.insert(0, {'event': {'text': '{0} {1} are Floos Bowl champions!'.format(self.currentSeason.champion.city, self.currentSeason.champion.name)}})
                playoffDict['Floos Bowl'] = gameResults
                self.currentSeason.freeAgencyOrder.append(runnerUp)
                self.currentSeason.freeAgencyOrder.append(self.currentSeason.champion)
                for player in self.currentSeason.champion.rosterDict.values():
                    player:FloosPlayer.Player
                    player.leagueChampionships.append({'Season': self.currentSeason.seasonNumber, 'team': player.team.abbr, 'teamColor': player.team.color})

                self.recordsManager.updateChampionshipHistory(self.currentSeason.seasonNumber, self.currentSeason.champion, runnerUp)
            else:
                for league in self.leagueManager.leagues:
                    for game in playoffGamesDict[league.name]:
                        game: FloosGame.Game
                        gameResults = game.gameDict
                        playoffDict[game.id] = gameResults
                        for team in playoffTeams[league.name]:
                            if team.name == gameResults['losingTeam']:
                                team.eliminated = True
                                self.currentSeason.leagueHighlights.insert(0, {'event': {'text': '{0} {1} have faded from playoff contention'.format(team.city, team.name)}})
                                self.currentSeason.freeAgencyOrder.append(team)
                                playoffTeams[league.name].remove(team)
                                break

                

            # Create directory if it doesn't exist
            games_dir = os.path.join('{}/games'.format(strCurrentSeason))
            os.makedirs(games_dir, exist_ok=True)
            
            jsonFile = open(os.path.join(games_dir, 'postseason.json'), "w+")
            jsonFile.write(json.dumps(playoffDict, indent=4))
            jsonFile.close()
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
            
            # Simulate the game
            await gameInstance.playGame()
            
            # Determine winner
            winner = game.homeTeam if gameInstance.homeScore > gameInstance.awayScore else game.awayTeam
            
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
        
        # STEP 1: Player offseason training
        logger.info("Step 1: Player offseason training")
        for player in self.playerManager.activePlayers:
            if hasattr(player, 'offseasonTraining'):
                player.offseasonTraining()
            # Reset season performance rating
            if hasattr(player, 'seasonPerformanceRating'):
                player.seasonPerformanceRating = 0
        
        # STEP 1.5: Increment free agent years for existing free agents
        logger.info("Step 1.5: Increment free agent years")
        for player in self.playerManager.freeAgents:
            if hasattr(player, 'freeAgentYears'):
                player.freeAgentYears += 1
        
        # STEP 2: Process contract decrements and retirements for rostered players
        logger.info("Step 2: Contract decrements and team retirements")
        await self._processRosteredPlayerContracts()
        
        # STEP 3: Generate replacement players for retirees (from rostered player retirements)
        # Note: Free agent retirements are handled within conductFreeAgencySimulation in Step 4
        logger.info("Step 3: Generate replacement players for retired rostered players")
        self._generateReplacementPlayers()
        
        # STEP 4: Run comprehensive free agency simulation (includes free agent retirements)
        logger.info("Step 4: Free agency simulation")
        await self._processFreeAgency()
        
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
        
        # Run the comprehensive free agency simulation
        currentSeasonNum = self.currentSeason.seasonNumber if hasattr(self, 'currentSeasonNumber') else 1
        freeAgencyHistory = self.playerManager.conductFreeAgencySimulation(
            freeAgencyOrder=freeAgencyOrder,
            currentSeason=currentSeasonNum,
            leagueHighlights=leagueHighlights
        )
        
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
                    if player.termRemaining == 0:
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
                elif player.termRemaining == 0:
                    # Contract expired - move to free agency
                    player.previousTeam = team.name
                    # TODO: capHit feature not fully developed - disabled for now
                    # team.playerCap -= getattr(player, 'capHit', 0)
                    if player.currentNumber in team.playerNumbersList:
                        team.playerNumbersList.remove(player.currentNumber)
                    player.team = 'Free Agent'
                    player.freeAgentYears = 0
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
        self.playerManager.activePlayers.remove(player)
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
                from serializers import serialize_object
                serializedHighlights = serialize_object(self.currentSeason.leagueHighlights)
                with open(highlightsFile, 'w') as f:
                    json.dump(serializedHighlights, f, indent=4)
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