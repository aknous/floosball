"""
TeamManager - Centralized team management for Floosball

Handles team creation, loading, roster management, and team data persistence.
Replaces scattered team management functions from floosball.py
"""

import json
import os
import glob
from typing import Dict, List, Any, Optional
import floosball_team as FloosTeam
import floosball_player as FloosPlayer
from logger_config import getLogger
import numpy as np

class TeamManager:
    """Manages all team-related operations including creation, loading, and roster management"""
    
    def __init__(self, serviceContainer):
        self.serviceContainer = serviceContainer
        self.teams: List[FloosTeam.Team] = []
        self.leagues: List = []  # Will be typed properly when League class is available
        self.logger = getLogger("floosball.team_manager")
        
    def generateTeams(self, config: Dict[str, Any]) -> None:
        """
        Generate teams from config or load from saved data
        Replaces getTeams() function from floosball.py
        """
        self.teams.clear()
        
        if os.path.exists("data/teamData"):
            self._loadTeamsFromData()
            # If no teams were loaded, fall back to config
            if len(self.teams) == 0:
                self._createTeamsFromConfig(config)
        else:
            self._createTeamsFromConfig(config)
            
        self.logger.info(f"Generated {len(self.teams)} teams")
    
    def _loadTeamsFromData(self) -> None:
        """Load teams from saved JSON data files"""
        fileList = glob.glob("data/teamData/team*.json")
        
        for file in fileList:
            with open(file) as jsonFile:
                teamData = json.load(jsonFile)
                newTeam = self._createTeamFromData(teamData)
                self.teams.append(newTeam)
                
        self.logger.info(f"Loaded {len(self.teams)} teams from data")
    
    def _createTeamFromData(self, teamData: Dict[str, Any]) -> FloosTeam.Team:
        """Create a team object from saved data"""
        newTeam = FloosTeam.Team(teamData['name'])
        
        # Basic team info
        newTeam.id = teamData['id']
        newTeam.city = teamData['city']
        newTeam.abbr = teamData['abbr']
        newTeam.color = teamData['color']
        
        # Ratings
        newTeam.offenseRating = teamData['offenseRating']
        newTeam.defenseRunCoverageRating = teamData['defenseRunCoverageRating']
        newTeam.defensePassCoverageRating = teamData['defensePassCoverageRating']
        newTeam.defensePassRushRating = teamData['defensePassRushRating']
        newTeam.defenseRating = teamData['defenseRating']
        newTeam.overallRating = teamData['overallRating']
        
        # Performance and tier data
        newTeam.gmScore = teamData['gmScore']
        newTeam.defenseOverallTier = teamData['defenseTier']
        newTeam.defenseSeasonPerformanceRating = teamData['defenseSeasonPerformanceRating']
        
        # Historical stats
        newTeam.allTimeTeamStats = teamData['allTimeTeamStats']
        newTeam.leagueChampionships = teamData['leagueChampionships']
        newTeam.floosbowlChampionships = teamData['floosbowlChampionships']
        newTeam.regularSeasonChampions = teamData['regularSeasonChampions']
        newTeam.playoffAppearances = teamData['playoffAppearances']
        
        if 'rosterHistory' in teamData:
            newTeam.rosterHistory = teamData['rosterHistory']
        
        # Load roster - need to match with active players
        self._loadTeamRoster(newTeam, teamData['roster'])
        
        return newTeam
    
    def _loadTeamRoster(self, team: FloosTeam.Team, rosterData: Dict[str, Any]) -> None:
        """Load team roster from saved data, matching with active players"""
        # Get active players from player manager
        activePlayerList = self.serviceContainer.getService('player_manager').activePlayers
        
        for pos, playerData in rosterData.items():
            for player in activePlayerList:
                if player.name == playerData['name']:
                    team.rosterDict[pos] = player
                    team.playerCap += player.capHit
                    team.playerNumbersList.append(playerData['currentNumber'])
                    break
    
    def _createTeamsFromConfig(self, config: Dict[str, Any]) -> None:
        """Create new teams from configuration"""
        teamId = 1
        
        for teamConfig in config['teams']:
            team = FloosTeam.Team(teamConfig['name'])
            team.city = teamConfig['city']
            team.abbr = teamConfig['abbr']
            team.color = teamConfig['color']
            team.id = teamId
            
            self.teams.append(team)
            teamId += 1
            
        self.logger.info(f"Created {len(self.teams)} new teams from config")
    
    def initializeTeams(self) -> None:
        """
        Initialize teams and save to data files
        Replaces initTeams() function from floosball.py
        """
        if not os.path.exists('data/teamData'):
            os.makedirs('data/teamData')
            
        for team in self.teams:
            self._setupAndSaveTeam(team)
        
        # Assign offense tiers like original initTeams() function  
        self._assignOffenseTiers()
        
        # Call sortDefenses at the end like original initTeams() function
        self.sortDefenses()
            
        self.logger.info(f"Initialized {len(self.teams)} teams")
    
    def _setupAndSaveTeam(self, team: FloosTeam.Team) -> None:
        """Setup team and save to JSON file"""
        team.setupTeam()
        
        teamDict = {
            'name': team.name,
            'city': team.city,
            'abbr': team.abbr,
            'color': team.color,
            'id': team.id,
            'offenseRating': team.offenseRating,
            'defenseRunCoverageRating': team.defenseRunCoverageRating,
            'defensePassRating': team.defensePassRating,
            'defensePassCoverageRating': team.defensePassCoverageRating,
            'defensePassRushRating': team.defensePassRushRating,
            'defenseRating': team.defenseRating,
            'overallRating': team.overallRating,
            'allTimeTeamStats': team.allTimeTeamStats,
            'floosbowlChampionships': team.floosbowlChampionships,
            'regularSeasonChampions': team.regularSeasonChampions,
            'leagueChampionships': team.leagueChampionships,
            'playoffAppearances': team.playoffAppearances,
            'gmScore': team.gmScore,
            'defenseTier': team.defenseOverallTier,
            'defenseSeasonPerformanceRating': team.defenseSeasonPerformanceRating
        }
        
        # Add roster data
        rosterDict = {}
        for pos, player in team.rosterDict.items():
            if player:  # Check if position is filled
                # Ensure player is assigned to this team like original
                if player.team != team:
                    player.team = team
                    
                playerDict = {
                    'name': player.name,
                    'id': player.id,
                    'tier': player.playerTier.name,
                    'currentNumber': getattr(player, 'currentNumber', 0),
                    'term': getattr(player, 'term', 0),
                    'termRemaining': getattr(player, 'termRemaining', 0),
                    'seasonsPlayed': getattr(player, 'seasonsPlayed', 0),
                    'careerStatsDict': getattr(player, 'careerStatsDict', {}),
                    'overallRating': getattr(player.attributes, 'overallRating', 0) if hasattr(player, 'attributes') else 0
                }
                rosterDict[pos] = playerDict
                
        teamDict['roster'] = rosterDict
        
        # Save to file
        fileName = f"data/teamData/team{team.id}.json"
        with open(fileName, "w+") as jsonFile:
            json.dump(teamDict, jsonFile, indent=2)
    
    def generateLeagues(self, config: Dict[str, Any]) -> None:
        """
        Generate leagues from config or load from saved data
        Replaces getLeagues() function from floosball.py
        """
        self.leagues.clear()
        
        if os.path.exists("data/leagueData.json"):
            self._loadLeaguesFromData()
        else:
            self._createLeaguesFromConfig(config)
            
        self.logger.info(f"Generated {len(self.leagues)} leagues")
    
    def _loadLeaguesFromData(self) -> None:
        """Load leagues from saved JSON data"""
        # Import League class dynamically to avoid circular imports
        import sys
        floosball_module = sys.modules.get('floosball')
        if floosball_module and hasattr(floosball_module, 'League'):
            League = floosball_module.League
        else:
            # Fallback - create a simple League class matching original
            class League:
                def __init__(self, config):
                    if isinstance(config, dict):
                        self.name = config.get('name', str(config))
                    else:
                        # Handle string names by creating config dict
                        self.name = str(config)
                    self.teamList = []
        
        with open('data/leagueData.json') as jsonFile:
            leagueData = json.load(jsonFile)
            
            for leagueName in leagueData:
                # League constructor expects config dict with 'name' key
                league = League({'name': leagueName})
                teamNamesInLeague = leagueData[leagueName]
                
                # Match team names with actual team objects
                for teamName in teamNamesInLeague:
                    for team in self.teams:
                        if team.name == teamName:
                            league.teamList.append(team)
                            break
                            
                self.leagues.append(league)
    
    def _createLeaguesFromConfig(self, config: Dict[str, Any]) -> None:
        """Create new leagues from configuration"""
        # Import League class dynamically to avoid circular imports
        import sys
        floosball_module = sys.modules.get('floosball')
        if floosball_module and hasattr(floosball_module, 'League'):
            League = floosball_module.League
        else:
            # Fallback - create a simple League class matching original
            class League:
                def __init__(self, config):
                    if isinstance(config, dict):
                        self.name = config.get('name', str(config))
                    else:
                        # Handle string names by creating config dict
                        self.name = str(config)
                    self.teamList = []
        
        for leagueConfig in config['leagues']:
            league = League(leagueConfig)
            self.leagues.append(league)
    
    def assignPlayerNumber(self, team: FloosTeam.Team, player: FloosPlayer.Player) -> None:
        """Assign a player number to a player on a team"""
        team.assignPlayerNumber(player)
    
    def updateTeamRatings(self) -> None:
        """
        Update team defense ratings based on performance
        Replaces team rating calculation logic from floosball.py
        """
        if not self.teams:
            return
            
        # Collect all team ratings for normalization
        defenseBaseSkills = [team.defenseRating for team in self.teams]
        defensePerformances = [team.defenseSeasonPerformanceRating for team in self.teams]
        
        # Calculate performance adjustments
        avgBaseSkill = np.mean(defenseBaseSkills) if defenseBaseSkills else 0
        avgPerformance = np.mean(defensePerformances) if defensePerformances else 0
        
        for team in self.teams:
            # Calculate weighted defense performance
            if hasattr(team, 'defenseRunCoverageSeasonPerformanceRating'):
                generalDefSeasonPerformanceRating = (team.defenseSeasonPerformanceRating * 2 + avgPerformance) / 3
                weightedScore = round(np.mean([
                    team.defenseRunCoverageSeasonPerformanceRating,
                    team.defensePassCoverageSeasonPerformanceRating,
                    generalDefSeasonPerformanceRating
                ]))
                team.defenseSeasonPerformanceRating = weightedScore
            
            # Apply tier adjustments
            performanceDiff = team.defenseSeasonPerformanceRating - avgPerformance
            baseDiff = team.defenseRating - avgBaseSkill
            adjustment = (performanceDiff + baseDiff) / 2
            
            team.defenseOverallTier = round(team.defenseRating + adjustment)
            
        self.logger.info("Updated team ratings for all teams")
    
    def sortDefenses(self) -> None:
        """
        Sort and assign defense tiers based on ratings
        Replaces sortDefenses() function from floosball.py
        """
        if not self.teams:
            return
            
        import floosball_player as FloosPlayer
        
        # Collect defense rating lists for percentile calculations
        teamDefenseOverallRatingList = [team.defenseOverallRating for team in self.teams if hasattr(team, 'defenseOverallRating')]
        teamDefensePassRatingList = [team.defensePassRating for team in self.teams]
        teamDefenseRunRatingList = [team.defenseRunCoverageRating for team in self.teams]

        # Assign defense overall tiers
        if teamDefenseOverallRatingList:
            tier5perc = np.percentile(teamDefenseOverallRatingList, 95)
            tier4perc = np.percentile(teamDefenseOverallRatingList, 80)
            tier3perc = np.percentile(teamDefenseOverallRatingList, 30)
            tier2perc = np.percentile(teamDefenseOverallRatingList, 10)

            for team in self.teams:
                if hasattr(team, 'defenseOverallRating'):
                    if team.defenseOverallRating >= tier5perc:
                        team.defenseOverallTier = FloosPlayer.PlayerTier.TierS.value
                    elif team.defenseOverallRating >= tier4perc:
                        team.defenseOverallTier = FloosPlayer.PlayerTier.TierA.value
                    elif team.defenseOverallRating >= tier3perc:
                        team.defenseOverallTier = FloosPlayer.PlayerTier.TierB.value
                    elif team.defenseOverallRating >= tier2perc:
                        team.defenseOverallTier = FloosPlayer.PlayerTier.TierC.value
                    else:
                        team.defenseOverallTier = FloosPlayer.PlayerTier.TierD.value

        # Assign defense pass tiers
        if teamDefensePassRatingList:
            tier5perc = np.percentile(teamDefensePassRatingList, 95)
            tier4perc = np.percentile(teamDefensePassRatingList, 80)
            tier3perc = np.percentile(teamDefensePassRatingList, 30)
            tier2perc = np.percentile(teamDefensePassRatingList, 10)

            for team in self.teams:
                if team.defensePassRating >= tier5perc:
                    team.defensePassTier = FloosPlayer.PlayerTier.TierS.value
                elif team.defensePassRating >= tier4perc:
                    team.defensePassTier = FloosPlayer.PlayerTier.TierA.value
                elif team.defensePassRating >= tier3perc:
                    team.defensePassTier = FloosPlayer.PlayerTier.TierB.value
                elif team.defensePassRating >= tier2perc:
                    team.defensePassTier = FloosPlayer.PlayerTier.TierC.value
                else:
                    team.defensePassTier = FloosPlayer.PlayerTier.TierD.value

        # Assign defense run tiers  
        if teamDefenseRunRatingList:
            tier5perc = np.percentile(teamDefenseRunRatingList, 95)
            tier4perc = np.percentile(teamDefenseRunRatingList, 80)
            tier3perc = np.percentile(teamDefenseRunRatingList, 30)
            tier2perc = np.percentile(teamDefenseRunRatingList, 10)

            for team in self.teams:
                if team.defenseRunCoverageRating >= tier5perc:
                    team.defenseRunTier = FloosPlayer.PlayerTier.TierS.value
                elif team.defenseRunCoverageRating >= tier4perc:
                    team.defenseRunTier = FloosPlayer.PlayerTier.TierA.value
                elif team.defenseRunCoverageRating >= tier3perc:
                    team.defenseRunTier = FloosPlayer.PlayerTier.TierB.value
                elif team.defenseRunCoverageRating >= tier2perc:
                    team.defenseRunTier = FloosPlayer.PlayerTier.TierC.value
                else:
                    team.defenseRunTier = FloosPlayer.PlayerTier.TierD.value
                    
        self.logger.info("Sorted defense tiers for all teams")
    
    def _assignOffenseTiers(self) -> None:
        """
        Assign offense tiers based on ratings
        Part of original initTeams() function
        """
        if not self.teams:
            return
            
        import floosball_player as FloosPlayer
        
        # Collect offense rating lists for percentile calculations
        teamOffenseRatingList = [team.offenseRating for team in self.teams]
        
        # Assign offense tiers
        if teamOffenseRatingList:
            tier5perc = np.percentile(teamOffenseRatingList, 95)
            tier4perc = np.percentile(teamOffenseRatingList, 80)
            tier3perc = np.percentile(teamOffenseRatingList, 30)
            tier2perc = np.percentile(teamOffenseRatingList, 10)

            for team in self.teams:
                if team.offenseRating >= tier5perc:
                    team.offenseTier = FloosPlayer.PlayerTier.TierS.value
                elif team.offenseRating >= tier4perc:
                    team.offenseTier = FloosPlayer.PlayerTier.TierA.value
                elif team.offenseRating >= tier3perc:
                    team.offenseTier = FloosPlayer.PlayerTier.TierB.value
                elif team.offenseRating >= tier2perc:
                    team.offenseTier = FloosPlayer.PlayerTier.TierC.value
                else:
                    team.offenseTier = FloosPlayer.PlayerTier.TierD.value
                    
        self.logger.info("Assigned offense tiers for all teams")
    
    
    def clearTeamSeasonStats(self) -> None:
        """Clear season statistics for all teams"""
        import floosball_team as FloosTeam
        import copy
        
        for team in self.teams:
            if hasattr(team, 'seasonTeamStats'):
                # Save current elo and rating before reset
                current_elo = team.seasonTeamStats.get('elo', getattr(team, 'elo', 1500))
                current_rating = team.seasonTeamStats.get('overallRating', getattr(team, 'overallRating', 80))
                
                # Archive current stats if they exist
                if hasattr(team, 'statArchive') and team.seasonTeamStats:
                    team.statArchive.insert(0, copy.deepcopy(team.seasonTeamStats))
                
                # Properly restore the full structure from teamStatsDict
                team.seasonTeamStats = copy.deepcopy(FloosTeam.teamStatsDict)
                
                # Restore preserved values
                team.seasonTeamStats['elo'] = current_elo
                team.seasonTeamStats['overallRating'] = current_rating
                team.seasonTeamStats['season'] = getattr(self.serviceContainer.getService('season_manager'), 'currentSeasonNumber', 1) if self.serviceContainer.getService('season_manager') else 1
                
                # Clear schedule for new season
                team.schedule = []
        
        self.logger.info("Cleared season stats for all teams")
    
    def setNewElo(self) -> None:
        """
        Complete ELO Rating System that calculates team ELO based on overall rating and historical performance.
        Replaces the original setNewElo() function.
        """
        import statistics
        
        self.logger.info("Calculating new ELO ratings for all teams")
        
        ratingList = []
        eloList = []
        
        # Collect current ratings and ELOs
        for team in self.teams:
            ratingList.append(team.overallRating)
            eloList.append(getattr(team, 'elo', 1500))
        
        meanRating = round(statistics.mean(ratingList)) if ratingList else 80
        
        # Update ELO for each team
        for team in self.teams:
            # Initialize ELO if not present
            if not hasattr(team, 'elo'):
                team.elo = 1500  # Default starting ELO
            
            # Check if team has historical data (stat archives)
            if hasattr(team, 'statArchive') and len(team.statArchive) > 0:
                # For teams with historical data: average current ELO with 1500 (regression to mean)
                team.elo = round((team.elo + 1500) / 2)
                self.logger.debug(f"Team {team.name}: ELO updated with history regression to {team.elo}")
            else:
                # For new teams: adjust ELO based on overall rating relative to league mean
                teamRatingRank = round(team.overallRating / meanRating, 2) if meanRating > 0 else 1.0
                team.elo = round(team.elo * teamRatingRank)
                self.logger.debug(f"Team {team.name}: ELO updated for new team to {team.elo} (rank: {teamRatingRank})")
            
            # Ensure ELO is stored in season stats
            if hasattr(team, 'seasonTeamStats'):
                team.seasonTeamStats['elo'] = team.elo
        
        self.logger.info(f"ELO ratings updated for {len(self.teams)} teams (mean rating: {meanRating})")
    
    def calculateWinProbability(self, homeTeam, awayTeam) -> tuple:
        """
        Calculate win probabilities for two teams based on their ELO ratings
        Returns tuple of (home_win_probability, away_win_probability)
        """
        import math
        
        ELO_DIVISOR = 400  # Standard ELO divisor constant
        
        homeTeamElo = getattr(homeTeam, 'elo', 1500)
        awayTeamElo = getattr(awayTeam, 'elo', 1500)
        
        # Use standard ELO probability calculation
        homeTeamWinProbability = round(1.0 / (1 + math.pow(10, (awayTeamElo - homeTeamElo) / ELO_DIVISOR)), 2)
        awayTeamWinProbability = round(1.0 / (1 + math.pow(10, (homeTeamElo - awayTeamElo) / ELO_DIVISOR)), 2)
        
        return homeTeamWinProbability, awayTeamWinProbability
    
    def updateEloAfterGame(self, homeTeam, awayTeam, homeScore: int, awayScore: int, winningTeam) -> None:
        """
        Update ELO ratings for both teams after a game based on the result and margin of victory
        """
        import math
        
        k = 35  # K-factor for ELO calculations - controls rating volatility
        
        homeTeamElo = getattr(homeTeam, 'elo', 1500)
        awayTeamElo = getattr(awayTeam, 'elo', 1500)
        
        # Calculate pre-game win probabilities
        homeTeamWinProbability, awayTeamWinProbability = self.calculateWinProbability(homeTeam, awayTeam)
        
        # Calculate margin of victory multiplier (accounts for score differential)
        scoreDiff = abs(homeScore - awayScore)
        
        if winningTeam == homeTeam:
            # Home team won
            marginOfVictoryMultiplier = math.log(scoreDiff + 1) * (2.2 / ((homeTeamElo - awayTeamElo) * 0.001 + 2.2))
            homeTeam.elo = round(homeTeamElo + (k * marginOfVictoryMultiplier) * (1 - homeTeamWinProbability))
            awayTeam.elo = round(awayTeamElo + (k * marginOfVictoryMultiplier) * (0 - awayTeamWinProbability))
        else:
            # Away team won  
            marginOfVictoryMultiplier = math.log(scoreDiff + 1) * (2.2 / ((awayTeamElo - homeTeamElo) * 0.001 + 2.2))
            homeTeam.elo = round(homeTeamElo + (k * marginOfVictoryMultiplier) * (0 - homeTeamWinProbability))
            awayTeam.elo = round(awayTeamElo + (k * marginOfVictoryMultiplier) * (1 - awayTeamWinProbability))
        
        # Update season stats with new ELO
        if hasattr(homeTeam, 'seasonTeamStats'):
            homeTeam.seasonTeamStats['elo'] = homeTeam.elo
        if hasattr(awayTeam, 'seasonTeamStats'):
            awayTeam.seasonTeamStats['elo'] = awayTeam.elo
        
        self.logger.debug(f"ELO updated after game: {homeTeam.name}={homeTeam.elo}, {awayTeam.name}={awayTeam.elo}")
    
    def getTeamsByEloRanking(self) -> List[FloosTeam.Team]:
        """Get teams sorted by ELO rating (highest first)"""
        return sorted(self.teams, key=lambda team: getattr(team, 'elo', 1500), reverse=True)
    
    def getEloStatistics(self) -> Dict[str, Any]:
        """Get ELO statistics for all teams"""
        import statistics
        
        eloRatings = [getattr(team, 'elo', 1500) for team in self.teams]
        
        if not eloRatings:
            return {}
        
        return {
            'mean': round(statistics.mean(eloRatings)),
            'median': round(statistics.median(eloRatings)),
            'min': min(eloRatings),
            'max': max(eloRatings),
            'range': max(eloRatings) - min(eloRatings),
            'standardDeviation': round(statistics.stdev(eloRatings)) if len(eloRatings) > 1 else 0
        }
    
    def getTeamById(self, teamId: int) -> Optional[FloosTeam.Team]:
        """Get team by ID"""
        for team in self.teams:
            if team.id == teamId:
                return team
        return None
    
    def getTeamByName(self, teamName: str) -> Optional[FloosTeam.Team]:
        """Get team by name"""
        for team in self.teams:
            if team.name == teamName:
                return team
        return None
    
    def getTeamStatistics(self) -> Dict[str, Any]:
        """Get comprehensive team statistics"""
        return {
            'totalTeams': len(self.teams),
            'totalLeagues': len(self.leagues),
            'averageTeamRating': np.mean([team.overallRating for team in self.teams]) if self.teams else 0,
            'teams': [{'id': team.id, 'name': team.name, 'rating': team.overallRating} for team in self.teams]
        }
    
    @property
    def teamList(self) -> List[FloosTeam.Team]:
        """Backward compatibility property for global teamList"""
        return self.teams
    
    @property
    def leagueList(self) -> List:
        """Backward compatibility property for global leagueList"""
        return self.leagues
    
    def setPressureModifiersForNewSeason(self, currentSeason: int) -> None:
        """
        Set pressure modifiers for teams based on previous season performance.
        Called at the start of each new season.
        """
        self.logger.info(f"Setting pressure modifiers for season {currentSeason}")
        
        for team in self.teams:
            # Initialize pressure modifier to default
            team.pressureModifier = 1.0
            
            # Only apply historical pressure if this is not the first season
            if currentSeason > 1 and hasattr(team, 'statArchive') and len(team.statArchive) > 0:
                previousSeason = team.statArchive[0]  # Most recent season is at index 0
                
                # Teams that made playoffs get pressure based on how far they went
                if previousSeason.get('madePlayoffs', False):
                    if not previousSeason.get('floosbowlChamp', False):
                        # Made playoffs but didn't win championship - pressure increases
                        leagueChamp = previousSeason.get('leageChamp', False)  # Note: typo in original key
                        topSeed = previousSeason.get('topSeed', False)
                        
                        if leagueChamp and topSeed:
                            team.pressureModifier = 1.5  # High expectations
                            self.logger.debug(f"{team.name}: Pressure 1.5 (League champ + top seed)")
                        elif leagueChamp or topSeed:
                            team.pressureModifier = 1.4  # Medium-high expectations
                            self.logger.debug(f"{team.name}: Pressure 1.4 (League champ OR top seed)")
                        else:
                            team.pressureModifier = 1.2  # Made playoffs, some pressure
                            self.logger.debug(f"{team.name}: Pressure 1.2 (Made playoffs)")
                    # Note: Floos Bowl champions get default 1.0 (no extra pressure)
                else:
                    # Teams that missed playoffs get reduced pressure based on how bad they were
                    winPerc = previousSeason.get('winPerc', 0)
                    
                    if winPerc < 0.25:
                        team.pressureModifier = 0.7  # Very bad season, low pressure
                        self.logger.debug(f"{team.name}: Pressure 0.7 (Win% < 25%)")
                    elif winPerc < 0.4:
                        team.pressureModifier = 0.8  # Bad season, reduced pressure
                        self.logger.debug(f"{team.name}: Pressure 0.8 (Win% < 40%)")
                    elif winPerc < 0.5:
                        team.pressureModifier = 0.9  # Below average, slight reduction
                        self.logger.debug(f"{team.name}: Pressure 0.9 (Win% < 50%)")
                    else:
                        team.pressureModifier = 1.0  # Decent season, normal pressure
                        self.logger.debug(f"{team.name}: Pressure 1.0 (Win% >= 50%)")
            else:
                # New teams or first season get default pressure
                self.logger.debug(f"{team.name}: Pressure 1.0 (New team/First season)")
        
        self.logger.info("Pressure modifiers set for all teams based on previous season")
    
    def updateInSeasonPressureModifiers(self, currentWeek: int, nonPlayoffTeamsList: List, lastTeamIn) -> List[Dict[str, str]]:
        """
        Update pressure modifiers during the season based on playoff implications.
        
        Args:
            currentWeek: Current week number
            nonPlayoffTeamsList: List of teams not currently in playoffs
            lastTeamIn: Team object representing the last team to make playoffs
            
        Returns:
            List of highlight events generated from pressure changes
        """
        leagueHighlights = []
        
        self.logger.info(f"Updating in-season pressure modifiers for week {currentWeek}")
        
        for standing in nonPlayoffTeamsList:
            team = standing['team'] if isinstance(standing, dict) else standing
            
            # Set pressure modifiers for poor performing teams late in season
            if team.seasonTeamStats.get('winPerc', 0) < 0.45 and currentWeek >= 14:
                team.pressureModifier = 0.9
                self.logger.debug(f"{team.name}: Reduced pressure (0.9) for poor performance late in season")
            
            # Check elimination status and set pressure accordingly
            if not getattr(team, 'clinchedPlayoffs', False) and not getattr(team, 'eliminated', False):
                import floosball_methods as FloosMethods
                
                # Check if team is mathematically eliminated
                team.eliminated = FloosMethods.checkIfEliminated(
                    team.seasonTeamStats.get('wins', 0),
                    lastTeamIn.seasonTeamStats.get('wins', 0),
                    28 - currentWeek
                )
                
                if team.eliminated:
                    leagueHighlights.insert(0, {
                        'event': {'text': f'{team.city} {team.name} have faded from playoff contention'}
                    })
                    team.pressureModifier = 0.7  # Eliminated teams have very low pressure
                    self.logger.debug(f"{team.name}: Eliminated - pressure set to 0.7")
                else:
                    # Check if team is on brink of elimination (must win out to match last team in)
                    teamMaxWins = team.seasonTeamStats.get('wins', 0) + (28 - currentWeek)
                    lastTeamWins = lastTeamIn.seasonTeamStats.get('wins', 0)
                    
                    if teamMaxWins == lastTeamWins:
                        leagueHighlights.insert(0, {
                            'event': {'text': f'{team.city} {team.name} are on the brink of elimination!'}
                        })
                        
                        # High pressure if close to elimination late in season
                        if (28 - currentWeek) <= 5:
                            team.pressureModifier = 2.0  # Maximum pressure for must-win situations
                            self.logger.debug(f"{team.name}: Brink of elimination - pressure set to 2.0")
        
        self.logger.info(f"In-season pressure update complete for week {currentWeek}")
        return leagueHighlights
    
    def setPlayoffPressureModifiers(self, playoffTeams: Dict[str, List], currentRound: int) -> None:
        """
        Set pressure modifiers for playoff teams based on round.
        
        Args:
            playoffTeams: Dictionary mapping league names to list of playoff teams
            currentRound: Current playoff round number (1=first round, higher=later rounds)
        """
        self.logger.info(f"Setting playoff pressure modifiers for round {currentRound}")
        
        for leagueName, teamList in playoffTeams.items():
            self.logger.debug(f"Setting pressure for {len(teamList)} teams in {leagueName}")
            for team in teamList:
                # Ensure team has pressure modifier attribute
                if not hasattr(team, 'pressureModifier'):
                    team.pressureModifier = 1.0
                
                if currentRound == 1:
                    # First round of playoffs - set base playoff pressure
                    team.pressureModifier = 1.5
                    self.logger.debug(f"{team.name}: First round playoff pressure set to 1.5")
                else:
                    # Later rounds - increase pressure incrementally
                    team.pressureModifier += 0.2
                    self.logger.debug(f"{team.name}: Round {currentRound} pressure increased to {team.pressureModifier}")
        
        self.logger.info(f"Playoff pressure modifiers set for round {currentRound}")
    
    def setFloosBowlPressure(self, homeTeam, awayTeam) -> None:
        """
        Set maximum pressure for Floos Bowl (championship game).
        
        Args:
            homeTeam: Home team in championship
            awayTeam: Away team in championship
        """
        self.logger.info("Setting Floos Bowl pressure modifiers")
        
        homeTeam.pressureModifier = 2.5  # Maximum pressure for championship
        awayTeam.pressureModifier = 2.5  # Maximum pressure for championship
        
        self.logger.debug(f"{homeTeam.name}: Floos Bowl pressure set to 2.5")
        self.logger.debug(f"{awayTeam.name}: Floos Bowl pressure set to 2.5")
        
        self.logger.info("Floos Bowl pressure modifiers set")
    
    def resetPressureModifiers(self) -> None:
        """Reset all team pressure modifiers to default (1.0)"""
        self.logger.info("Resetting all pressure modifiers to default")
        
        for team in self.teams:
            team.pressureModifier = 1.0
        
        self.logger.info("All pressure modifiers reset to 1.0")
    
    def getPressureStatistics(self) -> Dict[str, Any]:
        """Get pressure modifier statistics for all teams"""
        import statistics
        
        pressureValues = [getattr(team, 'pressureModifier', 1.0) for team in self.teams]
        
        if not pressureValues:
            return {}
        
        return {
            'mean': round(statistics.mean(pressureValues), 2),
            'median': round(statistics.median(pressureValues), 2),
            'min': min(pressureValues),
            'max': max(pressureValues),
            'range': round(max(pressureValues) - min(pressureValues), 2),
            'teamPressures': [
                {'team': team.name, 'pressure': getattr(team, 'pressureModifier', 1.0)} 
                for team in self.teams
            ]
        }