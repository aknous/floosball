"""
SeasonManager - Manages season simulation, scheduling, and progression
Replaces the scattered season-related functions and global variables from floosball.py
"""

from typing import List, Dict, Any, Optional, Tuple
import asyncio
import floosball_team as FloosTeam
import floosball_player as FloosPlayer
from logger_config import get_logger

logger = get_logger("floosball.seasonManager")

class Season:
    """Represents a single season"""
    
    def __init__(self, seasonNumber: int):
        self.seasonNumber = seasonNumber
        self.currentWeek = 0
        self.schedule: List[Dict[str, Any]] = []
        self.playoffBracket: List[Dict[str, Any]] = []
        self.isComplete = False
        self.champion: Optional[FloosTeam.Team] = None
        self.leagueChampions: Dict[str, FloosTeam.Team] = {}
        
    def addGame(self, homeTeam: FloosTeam.Team, awayTeam: FloosTeam.Team, week: int, gameType: str = 'regular') -> None:
        """Add a game to the season schedule"""
        game = {
            'homeTeam': homeTeam,
            'awayTeam': awayTeam,
            'week': week,
            'gameType': gameType,
            'completed': False,
            'result': None
        }
        self.schedule.append(game)

class SeasonManager:
    """Manages season simulation, scheduling, and progression"""
    
    def __init__(self, serviceContainer, leagueManager, playerManager, recordsManager):
        self.serviceContainer = serviceContainer
        self.leagueManager = leagueManager
        self.playerManager = playerManager
        self.recordsManager = recordsManager
        
        self.currentSeason: Optional[Season] = None
        self.seasonHistory: List[Season] = []
        self.schedule: List[Dict[str, Any]] = []
        
        logger.info("SeasonManager initialized")
    
    async def startNewSeason(self) -> None:
        """Initialize and start a new season"""
        seasonNumber = self.serviceContainer.get_game_state('seasonsPlayed', 0) + 1
        logger.info(f"Starting season {seasonNumber}")
        
        self.currentSeason = Season(seasonNumber)
        
        # Clear previous season data
        self._clearSeasonData()
        
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
        regularSeasonGames = [game for game in self.currentSeason.schedule if game['gameType'] == 'regular']
        
        # Group games by week
        weekGroups = {}
        for game in regularSeasonGames:
            week = game['week']
            if week not in weekGroups:
                weekGroups[week] = []
            weekGroups[week].append(game)
        
        # Simulate each week
        for week in sorted(weekGroups.keys()):
            logger.info(f"Simulating week {week}")
            
            weekGames = weekGroups[week]
            for game in weekGames:
                await self._simulateGame(game)
            
            # Update weekly stats and standings
            self._updateWeeklyStats()
            self._updateStandings()
            
            self.currentSeason.currentWeek = week
    
    async def _simulatePlayoffs(self) -> None:
        """Simulate playoff games"""
        logger.info("Starting playoff simulation")
        
        # Determine playoff teams
        playoffTeams = self.leagueManager.getPlayoffTeams()
        
        # Create playoff bracket
        self._createPlayoffBracket(playoffTeams)
        
        # Simulate playoff rounds
        await self._simulatePlayoffRounds()
    
    async def _simulateGame(self, game: Dict[str, Any]) -> None:
        """Simulate a single game"""
        import floosball_game as FloosGame
        
        try:
            # Create game instance
            gameInstance = FloosGame.Game(game['homeTeam'], game['awayTeam'])
            
            # Simulate the game
            await gameInstance.simulate()
            
            # Update game result
            game['completed'] = True
            game['result'] = gameInstance
            
            # Update team records
            self._updateTeamRecords(gameInstance)
            
            # Check for records
            self.recordsManager.checkPlayerGameRecords()
            self.recordsManager.checkTeamGameRecords(gameInstance)
            
        except Exception as e:
            logger.error(f"Error simulating game: {e}")
            game['completed'] = False
    
    def _updateTeamRecords(self, game) -> None:
        """Update team win/loss records"""
        homeTeam = game.homeTeam
        awayTeam = game.awayTeam
        
        # Initialize season stats if needed
        if not hasattr(homeTeam, 'seasonTeamStats'):
            homeTeam.seasonTeamStats = {'wins': 0, 'losses': 0}
        if not hasattr(awayTeam, 'seasonTeamStats'):
            awayTeam.seasonTeamStats = {'wins': 0, 'losses': 0}
        
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
    
    def createSchedule(self) -> None:
        """Generate season schedule"""
        if not self.currentSeason:
            return
            
        logger.info("Creating season schedule")
        
        # Get all teams from league manager
        allTeams = self.leagueManager.teams
        
        if len(allTeams) < 2:
            logger.error("Need at least 2 teams to create schedule")
            return
        
        # Create round-robin schedule within each league
        for league in self.leagueManager.leagues:
            if len(league.teamList) < 2:
                continue
                
            # Generate round-robin for this league
            self._generateRoundRobin(league.teamList)
        
        # Add inter-league games if multiple leagues exist
        if len(self.leagueManager.leagues) > 1:
            self._addInterLeagueGames()
        
        logger.info(f"Created schedule with {len(self.currentSeason.schedule)} games")
    
    def _generateRoundRobin(self, teams: List[FloosTeam.Team]) -> None:
        """Generate round-robin schedule for a list of teams"""
        import itertools
        
        week = 1
        
        # Generate all possible pairings
        pairings = list(itertools.combinations(teams, 2))
        
        # Distribute games across weeks
        gamesPerWeek = max(1, len(teams) // 2)
        
        for i in range(0, len(pairings), gamesPerWeek):
            weekPairings = pairings[i:i + gamesPerWeek]
            
            for homeTeam, awayTeam in weekPairings:
                self.currentSeason.addGame(homeTeam, awayTeam, week, 'regular')
            
            week += 1
    
    def _addInterLeagueGames(self) -> None:
        """Add games between different leagues"""
        if len(self.leagueManager.leagues) < 2:
            return
            
        # Simple inter-league scheduling: each team plays one team from other leagues
        for i, league1 in enumerate(self.leagueManager.leagues):
            for j, league2 in enumerate(self.leagueManager.leagues):
                if i >= j:  # Only schedule once between each pair of leagues
                    continue
                
                # Pair teams from different leagues
                minTeams = min(len(league1.teamList), len(league2.teamList))
                
                for k in range(minTeams):
                    homeTeam = league1.teamList[k]
                    awayTeam = league2.teamList[k]
                    
                    # Add to later week to avoid conflicts
                    week = len(self.currentSeason.schedule) // max(1, len(self.leagueManager.teams) // 2) + 1
                    self.currentSeason.addGame(homeTeam, awayTeam, week, 'regular')
    
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
            
            # Simulate round games
            roundWinners = []
            for game in roundGames:
                winner = await self._simulatePlayoffGame(game)
                if winner:
                    roundWinners.append(winner)
            
            # Create next round if needed
            if len(roundWinners) > 1:
                nextRound = 'finals' if currentRound == 'semifinals' else 'championship'
                
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
            elif len(roundWinners) == 1:
                # Single champion
                self.currentSeason.champion = roundWinners[0]
                break
            else:
                break
    
    async def _simulatePlayoffGame(self, game: Dict[str, Any]) -> Optional[FloosTeam.Team]:
        """Simulate a single playoff game"""
        import floosball_game as FloosGame
        
        try:
            # Create game instance
            gameInstance = FloosGame.Game(game['homeTeam'], game['awayTeam'])
            
            # Simulate the game
            await gameInstance.simulate()
            
            # Determine winner
            winner = game['homeTeam'] if gameInstance.homeScore > gameInstance.awayScore else game['awayTeam']
            
            # Update game result
            game['completed'] = True
            game['winner'] = winner
            game['result'] = gameInstance
            
            # Update team records
            self._updateTeamRecords(gameInstance)
            
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
        
        # Add to season history
        self.seasonHistory.append(self.currentSeason)
        
        # Update game state
        seasonNumber = self.currentSeason.seasonNumber
        self.serviceContainer.set_game_state('seasonsPlayed', seasonNumber)
        
        logger.info(f"Season {seasonNumber} completed. Champion: {self.currentSeason.champion.name if self.currentSeason.champion else 'None'}")
    
    async def handleOffseason(self) -> None:
        """Handle offseason activities"""
        await self._handleOffseason()
    
    async def _handleOffseason(self) -> None:
        """Handle offseason activities"""
        logger.info("Processing offseason activities")
        
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
        contractManager = self.serviceContainer.getService('contract_manager')
        if contractManager:
            await contractManager.handleFreeAgency()
        else:
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
                    player.serviceTime = FloosPlayer.PlayerServiceTime.Veteran
            
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
                    'Offense': {'totalYards': 0, 'tds': 0, 'pts': 0},
                    'Defense': {'ints': 0, 'fumRec': 0, 'sacks': 0}
                }
    
    def _updateWeeklyStats(self) -> None:
        """Update weekly statistics"""
        # This would update team and player weekly performance metrics
        # Implementation depends on specific stat tracking requirements
        pass
    
    def _updateStandings(self) -> None:
        """Update league standings"""
        for league in self.leagueManager.leagues:
            league.getStandings()
    
    def advanceToNextSeason(self) -> None:
        """Move to next season"""
        if self.currentSeason:
            self.currentSeason = None
        
        logger.info("Advanced to next season")
    
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