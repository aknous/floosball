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
    @property
    def leagueList(self) -> List[League]:
        """Backward compatibility property for global leagueList"""
        return self.leagues