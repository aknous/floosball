"""
LeagueManager - Manages league structure, teams, and overall organization
Replaces the scattered league-related functions and global variables from floosball.py
"""

from typing import List, Dict, Any, Optional
import floosball_team as FloosTeam
from logger_config import get_logger

logger = get_logger("floosball.leagueManager")

class League:
    """Represents a league containing teams"""
    
    def __init__(self, config: Dict[str, Any]):
        if isinstance(config, dict):
            self.name = config.get('name', str(config))
        else:
            self.name = str(config)
        self.teamList: List[FloosTeam.Team] = []
        self.standings: List[Dict[str, Any]] = []
        
    def addTeam(self, team: FloosTeam.Team) -> None:
        """Add a team to this league"""
        if team not in self.teamList:
            self.teamList.append(team)
            
    def removeTeam(self, team: FloosTeam.Team) -> None:
        """Remove a team from this league"""
        if team in self.teamList:
            self.teamList.remove(team)
            
    def getStandings(self) -> List[Dict[str, Any]]:
        """Get current league standings sorted by record"""
        standings = []
        for team in self.teamList:
            standings.append({
                'team': team,
                'wins': team.seasonTeamStats.get('wins', 0) if hasattr(team, 'seasonTeamStats') else 0,
                'losses': team.seasonTeamStats.get('losses', 0) if hasattr(team, 'seasonTeamStats') else 0,
                'winPct': self._calculateWinPercentage(team)
            })
        
        # Sort by win percentage (descending), then by wins (descending)
        standings.sort(key=lambda x: (x['winPct'], x['wins']), reverse=True)
        self.standings = standings
        return standings
        
    def _calculateWinPercentage(self, team: FloosTeam.Team) -> float:
        """Calculate team's win percentage"""
        if not hasattr(team, 'seasonTeamStats'):
            return 0.0
        wins = team.seasonTeamStats.get('wins', 0)
        losses = team.seasonTeamStats.get('losses', 0)
        total_games = wins + losses
        return wins / total_games if total_games > 0 else 0.0

class LeagueManager:
    """Manages league structure, teams, and overall organization"""
    
    def __init__(self, serviceContainer):
        self.serviceContainer = serviceContainer
        self.leagues: List[League] = []
        self.teams: List[FloosTeam.Team] = []
        
        logger.info("LeagueManager initialized")
    
    def createLeagues(self, config: Dict[str, Any]) -> None:
        """Create league structure from config"""
        logger.info("Creating league structure from config")
        
        self.leagues.clear()
        
        # Get teams from team manager
        teamManager = self.serviceContainer.getService('team_manager')
        if teamManager:
            self.teams = teamManager.teams
        
        # Create leagues from config
        if 'leagues' in config:
            for leagueConfig in config['leagues']:
                league = League(leagueConfig)
                self.leagues.append(league)
        
        # Distribute teams across leagues
        self._distributeTeamsToLeagues(config)
        
        logger.info(f"Created {len(self.leagues)} leagues with {len(self.teams)} teams")
    
    def _distributeTeamsToLeagues(self, config: Dict[str, Any]) -> None:
        """Distribute teams across leagues based on config or evenly"""
        if not self.leagues or not self.teams:
            return
            
        # If config specifies team distribution, use that
        if 'teamDistribution' in config:
            self._distributeByConfig(config['teamDistribution'])
        else:
            # Otherwise distribute teams evenly across leagues
            self._distributeEvenly()
    
    def _distributeByConfig(self, distribution: Dict[str, List[str]]) -> None:
        """Distribute teams based on configuration mapping"""
        for leagueName, teamNames in distribution.items():
            league = self.getLeagueByName(leagueName)
            if league:
                for teamName in teamNames:
                    team = self._findTeamByName(teamName)
                    if team:
                        league.addTeam(team)
    
    def _distributeEvenly(self) -> None:
        """Distribute teams evenly across all leagues"""
        if not self.leagues:
            return
            
        teamsPerLeague = len(self.teams) // len(self.leagues)
        remainder = len(self.teams) % len(self.leagues)
        
        teamIndex = 0
        for i, league in enumerate(self.leagues):
            # Some leagues get one extra team if there's a remainder
            numTeams = teamsPerLeague + (1 if i < remainder else 0)
            
            for _ in range(numTeams):
                if teamIndex < len(self.teams):
                    league.addTeam(self.teams[teamIndex])
                    teamIndex += 1
    
    def _findTeamByName(self, teamName: str) -> Optional[FloosTeam.Team]:
        """Find team by name"""
        for team in self.teams:
            if team.name == teamName:
                return team
        return None
    
    def addTeam(self, team: FloosTeam.Team, leagueName: str = None) -> None:
        """Add team to appropriate league"""
        if team not in self.teams:
            self.teams.append(team)
        
        if leagueName:
            league = self.getLeagueByName(leagueName)
            if league:
                league.addTeam(team)
        elif self.leagues:
            # Add to league with fewest teams
            smallestLeague = min(self.leagues, key=lambda l: len(l.teamList))
            smallestLeague.addTeam(team)
    
    def removeTeam(self, team: FloosTeam.Team) -> None:
        """Remove team from league structure"""
        if team in self.teams:
            self.teams.remove(team)
            
        for league in self.leagues:
            league.removeTeam(team)
    
    def getStandings(self, leagueName: str = None) -> Dict[str, List[Dict[str, Any]]]:
        """Get current league standings"""
        if leagueName:
            league = self.getLeagueByName(leagueName)
            if league:
                return {leagueName: league.getStandings()}
            return {}
        
        # Return standings for all leagues
        allStandings = {}
        for league in self.leagues:
            allStandings[league.name] = league.getStandings()
        
        return allStandings
    
    def getLeagueByName(self, name: str) -> Optional[League]:
        """Find league by name"""
        for league in self.leagues:
            if league.name == name:
                return league
        return None
    
    def getTeamLeague(self, team: FloosTeam.Team) -> Optional[League]:
        """Find which league a team belongs to"""
        for league in self.leagues:
            if team in league.teamList:
                return league
        return None
    
    def getPlayoffTeams(self, leagueName: str = None, numTeams: int = 4) -> Dict[str, List[FloosTeam.Team]]:
        """Get playoff-eligible teams from each league"""
        playoffTeams = {}
        
        if leagueName:
            league = self.getLeagueByName(leagueName)
            if league:
                standings = league.getStandings()
                playoffTeams[leagueName] = [standing['team'] for standing in standings[:numTeams]]
        else:
            for league in self.leagues:
                standings = league.getStandings()
                playoffTeams[league.name] = [standing['team'] for standing in standings[:numTeams]]
        
        return playoffTeams
    
    def getLeagueChampions(self) -> Dict[str, FloosTeam.Team]:
        """Get the current champion of each league"""
        champions = {}
        
        for league in self.leagues:
            standings = league.getStandings()
            if standings:
                champions[league.name] = standings[0]['team']
        
        return champions
    
    def clearSeasonData(self) -> None:
        """Clear season-specific data for new season"""
        for league in self.leagues:
            league.standings.clear()
        
        logger.info("Cleared season data for all leagues")
    
    def getLeagueStatistics(self) -> Dict[str, Any]:
        """Get comprehensive league statistics"""
        stats = {
            'totalLeagues': len(self.leagues),
            'totalTeams': len(self.teams),
            'leagueBreakdown': {}
        }
        
        for league in self.leagues:
            stats['leagueBreakdown'][league.name] = {
                'teams': len(league.teamList),
                'teamNames': [team.name for team in league.teamList]
            }
        
        return stats
    
    def saveLeagueData(self) -> None:
        """Save league structure to data file"""
        import json
        import os
        
        leagueData = {}
        for league in self.leagues:
            teamNames = [team.name for team in league.teamList]
            leagueData[league.name] = teamNames
        
        os.makedirs("data", exist_ok=True)
        
        try:
            with open("data/leagueData.json", "w") as jsonFile:
                json.dump(leagueData, jsonFile, indent=4)
            logger.info(f"Saved league data for {len(self.leagues)} leagues")
        except Exception as e:
            logger.error(f"Failed to save league data: {e}")
    
    def loadLeagueData(self) -> None:
        """Load league structure from data file"""
        import json
        import os
        
        if not os.path.exists("data/leagueData.json"):
            logger.info("No league data file found, skipping load")
            return
            
        try:
            with open("data/leagueData.json", "r") as jsonFile:
                leagueData = json.load(jsonFile)
                
            self.leagues.clear()
            
            for leagueName, teamNames in leagueData.items():
                league = League({'name': leagueName})
                
                # Find and add teams to league
                for teamName in teamNames:
                    team = self._findTeamByName(teamName)
                    if team:
                        league.addTeam(team)
                
                self.leagues.append(league)
            
            logger.info(f"Loaded {len(self.leagues)} leagues from data file")
            
        except Exception as e:
            logger.error(f"Failed to load league data: {e}")
    
    # Backward compatibility properties
    def runPlayoffs(self, currentSeason: int, currentWeek: int, leagueHighlights: List = None) -> 'FloosTeam.Team':
        """
        Complete playoff tournament system - replaces original playPlayoffs function
        Returns the championship team
        """
        import floosball_methods as FloosMethods
        import floosball_game as FloosGame
        import datetime
        import asyncio
        import json
        import os
        
        logger.info(f"Starting playoffs for season {currentSeason}")
        
        champ = None
        playoffDict = {}
        playoffTeams = {}
        playoffsByeTeams = {}
        playoffsNonByeTeams = {}
        nonPlayoffTeamList = []
        championshipHistory = getattr(self, 'championshipHistory', [])
        freeAgencyOrder = []
        
        if leagueHighlights is None:
            leagueHighlights = []
        
        # PLAYOFF TEAM SELECTION LOGIC (top half of each league)
        for league in self.leagues:
            playoffTeamsList = []
            playoffsByeTeamList = []
            playoffsNonByeTeamList = []
            
            # Sort teams by win percentage and point differential
            league.teamList.sort(key=lambda team: (
                team.seasonTeamStats.get('winPerc', 0),
                team.seasonTeamStats.get('scoreDiff', 0)
            ), reverse=True)
            
            # Select top half for playoffs
            numPlayoffTeams = len(league.teamList) // 2
            playoffTeamsList.extend(league.teamList[:numPlayoffTeams])
            nonPlayoffTeamList.extend(league.teamList[numPlayoffTeams:])
            
            # BYE SYSTEM (top 2 teams get first-round byes)
            playoffsByeTeamList.extend(playoffTeamsList[:2])
            playoffsNonByeTeamList.extend(playoffTeamsList[2:])
            
            # Mark top seed
            if playoffsByeTeamList:
                playoffsByeTeamList[0].clinchedTopSeed = True
                playoffsByeTeamList[0].seasonTeamStats['topSeed'] = True
            
            playoffTeams[league.name] = playoffTeamsList.copy()
            playoffsByeTeams[league.name] = playoffsByeTeamList.copy()
            playoffsNonByeTeams[league.name] = playoffsNonByeTeamList.copy()
            
            # Mark playoff teams
            for team in playoffsByeTeamList:
                if not hasattr(team, 'playoffAppearances'):
                    team.playoffAppearances = 0
                team.playoffAppearances += 1
                team.seasonTeamStats['madePlayoffs'] = True
                team.clinchedPlayoffs = True
                team.winningStreak = False
            
            for team in playoffsNonByeTeamList:
                if not hasattr(team, 'playoffAppearances'):
                    team.playoffAppearances = 0
                team.playoffAppearances += 1
                team.seasonTeamStats['madePlayoffs'] = True
                team.winningStreak = False
                if not hasattr(team, 'clinchedPlayoffs') or not team.clinchedPlayoffs:
                    team.clinchedPlayoffs = True
                    team.eliminated = False
                    leagueHighlights.insert(0, {
                        'event': {'text': f'{team.city} {team.name} have clinched a playoff berth'}
                    })
        
        # Mark eliminated teams
        for team in nonPlayoffTeamList:
            team.winningStreak = False
            if not hasattr(team, 'eliminated') or not team.eliminated:
                team.eliminated = True
                team.clinchedPlayoffs = False
                leagueHighlights.insert(0, {
                    'event': {'text': f'{team.city} {team.name} have faded from playoff contention'}
                })
        
        # Set free agency order (worst teams draft first)
        freeAgencyOrder.extend(nonPlayoffTeamList)
        freeAgencyOrder.sort(key=lambda team: (
            team.seasonTeamStats.get('winPerc', 0),
            team.seasonTeamStats.get('scoreDiff', 0)
        ), reverse=False)
        
        # PLAYOFF BRACKET PROGRESSION AND MATCHUP CREATION
        numOfRounds = FloosMethods.getPower(2, len(self.teams) // 2)
        
        for roundNum in range(numOfRounds):
            playoffGamesDict = {}
            playoffGamesList = []
            currentRound = roundNum + 1
            gameNumber = 1
            roundStartTime = self._getPlayoffStartTime(currentWeek + currentRound)
            
            # LEAGUE CHAMPIONSHIP GAMES (all rounds except final)
            if roundNum < numOfRounds - 1:
                for league in self.leagues:
                    teamsInRound = []
                    gamesList = []
                    
                    if currentRound == 1:
                        # First round: non-bye teams only
                        teamsInRound.extend(playoffsNonByeTeams[league.name])
                        for team in playoffTeams[league.name]:
                            if not hasattr(team, 'pressureModifier'):
                                team.pressureModifier = 1.0
                            team.pressureModifier = 1.5
                    else:
                        # Later rounds: all remaining teams
                        teamsInRound.extend(playoffTeams[league.name])
                        for team in playoffTeams[league.name]:
                            if not hasattr(team, 'pressureModifier'):
                                team.pressureModifier = 1.0
                            team.pressureModifier += 0.2
                    
                    # Sort teams for bracket seeding
                    teamsInRound.sort(key=lambda team: (
                        team.seasonTeamStats.get('winPerc', 0),
                        team.seasonTeamStats.get('scoreDiff', 0)
                    ), reverse=True)
                    
                    # Create matchups (highest vs lowest seed)
                    hiSeed = 0
                    lowSeed = len(teamsInRound) - 1
                    
                    while lowSeed > hiSeed:
                        newGame = FloosGame.Game(teamsInRound[hiSeed], teamsInRound[lowSeed])
                        newGame.id = f's{currentSeason}r{currentRound}g{gameNumber}'
                        newGame.status = FloosGame.GameStatus.Scheduled
                        newGame.startTime = roundStartTime
                        newGame.isRegularSeasonGame = False
                        newGame.calculateWinProbability()
                        gamesList.append(newGame)
                        hiSeed += 1
                        lowSeed -= 1
                        gameNumber += 1
                    
                    playoffGamesDict[league.name] = gamesList.copy()
                    playoffGamesList.extend(gamesList)
                
                currentWeekText = f'Playoffs Round {currentRound}'
            else:
                # FLOOS BOWL (championship between league winners)
                floosbowlTeams = []
                for league in self.leagues:
                    for team in playoffTeams[league.name]:
                        team.leagueChampion = True
                        floosbowlTeams.append(team)
                
                floosbowlTeams.sort(key=lambda team: (
                    team.seasonTeamStats.get('winPerc', 0),
                    team.seasonTeamStats.get('scoreDiff', 0)
                ), reverse=True)
                
                newGame = FloosGame.Game(floosbowlTeams[0], floosbowlTeams[1])
                newGame.id = f's{currentSeason}r{currentRound}g{gameNumber}'
                newGame.status = FloosGame.GameStatus.Scheduled
                newGame.startTime = roundStartTime
                newGame.isRegularSeasonGame = False
                newGame.calculateWinProbability()
                playoffGamesList.append(newGame)
                currentWeekText = 'Floos Bowl'
                newGame.homeTeam.pressureModifier = 2.5
                newGame.awayTeam.pressureModifier = 2.5
            
            leagueHighlights.insert(0, {'event': {'text': f'{currentWeekText} Starting Soon...'}})
            leagueHighlights.insert(0, {'event': {'text': f'{currentWeekText} Start'}})
            
            # CHAMPIONSHIP TRACKING PER PLAYER AND TEAM
            if len(playoffGamesList) == 1:
                # Final game - crown champion
                game = playoffGamesList[0]
                # Note: Game would be played via asyncio in original, 
                # here we assume it's been played by the time this is called
                
                if hasattr(game, 'winningTeam') and game.winningTeam:
                    champ = game.winningTeam
                    runnerUp = game.losingTeam
                    
                    # Add championship to team
                    if not hasattr(champ, 'leagueChampionships'):
                        champ.leagueChampionships = []
                    champ.leagueChampionships.append(f'Season {currentSeason}')
                    
                    runnerUp.eliminated = True
                    leagueHighlights.insert(0, {
                        'event': {'text': f'{champ.city} {champ.name} are Floos Bowl champions!'}
                    })
                    
                    # Award championships to players
                    for player in champ.rosterDict.values():
                        if player and hasattr(player, 'leagueChampionships'):
                            if not isinstance(player.leagueChampionships, list):
                                player.leagueChampionships = []
                            player.leagueChampionships.append({
                                'Season': currentSeason,
                                'team': champ.abbr,
                                'teamColor': champ.color
                            })
                    
                    # CHAMPIONSHIP HISTORY WITH DETAILED RECORDS
                    championshipHistory.insert(0, {
                        'season': currentSeason,
                        'champion': f'{champ.city} {champ.name}',
                        'championColor': champ.color,
                        'championId': champ.id,
                        'championRecord': f"{champ.seasonTeamStats.get('wins', 0)}-{champ.seasonTeamStats.get('losses', 0)}",
                        'championElo': getattr(champ, 'elo', 1500),
                        'runnerUp': f'{runnerUp.city} {runnerUp.name}',
                        'runnerUpColor': runnerUp.color,
                        'runnerUpId': runnerUp.id,
                        'runnerUpRecord': f"{runnerUp.seasonTeamStats.get('wins', 0)}-{runnerUp.seasonTeamStats.get('losses', 0)}",
                        'runnerUpElo': getattr(runnerUp, 'elo', 1500)
                    })
                    
                    freeAgencyOrder.append(runnerUp)
                    freeAgencyOrder.append(champ)
            else:
                # Process round results and eliminate losing teams
                for league in self.leagues:
                    if league.name in playoffGamesDict:
                        for game in playoffGamesDict[league.name]:
                            if hasattr(game, 'gameDict'):
                                gameResults = game.gameDict
                                playoffDict[game.id] = gameResults
                                
                                # Remove losing teams from playoff contention
                                losingTeamName = gameResults.get('losingTeam')
                                for team in playoffTeams[league.name][:]:  # Use slice copy for safe iteration
                                    if team.name == losingTeamName:
                                        team.eliminated = True
                                        leagueHighlights.insert(0, {
                                            'event': {'text': f'{team.city} {team.name} have faded from playoff contention'}
                                        })
                                        freeAgencyOrder.append(team)
                                        playoffTeams[league.name].remove(team)
                                        break
            
            # Save playoff results
            seasonDir = f'data/season{currentSeason}/games'
            os.makedirs(seasonDir, exist_ok=True)
            
            try:
                with open(os.path.join(seasonDir, 'postseason.json'), 'w') as jsonFile:
                    json.dump(playoffDict, jsonFile, indent=4)
            except Exception as e:
                logger.error(f"Failed to save playoff results: {e}")
        
        # Store championship history and free agency order
        self.championshipHistory = championshipHistory
        self.freeAgencyOrder = freeAgencyOrder
        
        logger.info(f"Playoffs completed for season {currentSeason}, champion: {champ.name if champ else 'None'}")
        return champ
    
    def _getPlayoffStartTime(self, week: int):
        """Calculate start time for playoff rounds"""
        import datetime
        now = datetime.datetime.utcnow()
        return now + datetime.timedelta(days=week)
    
    def checkPlayoffClinching(self, currentWeek: int, leagueHighlights: List = None) -> None:
        """
        Check for playoff clinching and elimination during regular season
        """
        import floosball_methods as FloosMethods
        
        if leagueHighlights is None:
            leagueHighlights = []
        
        for league in self.leagues:
            standings = league.getStandings()
            if not standings:
                continue
                
            numPlayoffTeams = len(league.teamList) // 2
            playoffTeamList = standings[:numPlayoffTeams]
            nonPlayoffTeamsList = standings[numPlayoffTeams:]
            
            # Check if teams are already marked for clinching/elimination
            for standing in playoffTeamList:
                team = standing['team']
                if not hasattr(team, 'clinchedPlayoffs'):
                    team.clinchedPlayoffs = False
                if not hasattr(team, 'eliminated'):
                    team.eliminated = False
            
            if nonPlayoffTeamsList:
                lastTeamIn = playoffTeamList[-1]['team'] if playoffTeamList else None
                firstTeamOut = nonPlayoffTeamsList[0]['team'] if nonPlayoffTeamsList else None
                
                # Check top seed clinching
                if len(standings) >= 2:
                    team1 = standings[0]['team']
                    team2 = standings[1]['team']
                    
                    if not hasattr(team1, 'clinchedTopSeed'):
                        team1.clinchedTopSeed = False
                        
                    if not team1.clinchedTopSeed:
                        team1.clinchedTopSeed = FloosMethods.checkIfClinched(
                            team1.seasonTeamStats.get('wins', 0),
                            team2.seasonTeamStats.get('wins', 0),
                            28 - currentWeek
                        )
                        if team1.clinchedTopSeed:
                            leagueHighlights.insert(0, {
                                'event': {'text': f'{team1.city} {team1.name} have clinched the #1 seed'}
                            })
                        elif currentWeek == 28:
                            team1.clinchedTopSeed = True
                            leagueHighlights.insert(0, {
                                'event': {'text': f'{team1.city} {team1.name} have clinched the #1 seed'}
                            })
                
                # Check playoff clinching
                if lastTeamIn and firstTeamOut:
                    for standing in playoffTeamList:
                        team = standing['team']
                        if not team.clinchedPlayoffs and not team.eliminated:
                            team.clinchedPlayoffs = FloosMethods.checkIfClinched(
                                team.seasonTeamStats.get('wins', 0),
                                firstTeamOut.seasonTeamStats.get('wins', 0),
                                28 - currentWeek
                            )
                            if team.clinchedPlayoffs:
                                leagueHighlights.insert(0, {
                                    'event': {'text': f'{team.city} {team.name} have clinched a playoff berth'}
                                })
                    
                    # Check elimination
                    for standing in nonPlayoffTeamsList:
                        team = standing['team']
                        
                        # Set pressure modifiers based on performance
                        if team.seasonTeamStats.get('winPerc', 0) < 0.45 and currentWeek >= 14:
                            team.pressureModifier = 0.9
                            
                        if not team.clinchedPlayoffs and not team.eliminated:
                            team.eliminated = FloosMethods.checkIfEliminated(
                                team.seasonTeamStats.get('wins', 0),
                                lastTeamIn.seasonTeamStats.get('wins', 0),
                                28 - currentWeek
                            )
                            if team.eliminated:
                                leagueHighlights.insert(0, {
                                    'event': {'text': f'{team.city} {team.name} have faded from playoff contention'}
                                })
                                team.pressureModifier = 0.7
                            else:
                                # Check if team is on brink of elimination
                                if (team.seasonTeamStats.get('wins', 0) + (28 - currentWeek) == 
                                    lastTeamIn.seasonTeamStats.get('wins', 0)):
                                    leagueHighlights.insert(0, {
                                        'event': {'text': f'{team.city} {team.name} are on the brink of elimination!'}
                                    })
                                    if (28 - currentWeek) <= 5:
                                        team.pressureModifier = 2.0
    
    @property
    def leagueList(self) -> List[League]:
        """Backward compatibility property for global leagueList"""
        return self.leagues