"""
LeagueManager - Manages league structure, teams, and overall organization
Replaces the scattered league-related functions and global variables from floosball.py
"""

from typing import List, Dict, Any, Optional
import floosball_team as FloosTeam
from logger_config import get_logger

# Database imports
try:
    from database.config import USE_DATABASE
    from database.connection import get_session
    from database.repositories import LeagueRepository, TeamRepository
    from database.models import League as DBLeague, Team as DBTeam
    DATABASE_AVAILABLE = True
except ImportError:
    DATABASE_AVAILABLE = False
    USE_DATABASE = False

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
            team.league = self.name
            team.leagueRef = self
            
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
                'winPct': self._calculateWinPercentage(team),
                'scoreDiff': team.seasonTeamStats.get('scoreDiff', 0) if hasattr(team, 'seasonTeamStats') else 0
            })

        # Sort by win percentage (descending), then by score differential (descending)
        standings.sort(key=lambda x: (x['winPct'], x['scoreDiff']), reverse=True)
        self.standings = standings
        return standings
        
    def _calculateWinPercentage(self, team: FloosTeam.Team) -> float:
        """Calculate team's win percentage"""
        if not hasattr(team, 'seasonTeamStats'):
            return 0.0
        wins = team.seasonTeamStats.get('wins', 0)
        losses = team.seasonTeamStats.get('losses', 0)
        total_games = wins + losses
        return round(wins / total_games, 3) if total_games > 0 else 0.0

class LeagueManager:
    """Manages league structure, teams, and overall organization"""
    
    def __init__(self, serviceContainer):
        self.serviceContainer = serviceContainer
        self.leagues: List[League] = []
        self.teams: List[FloosTeam.Team] = []
        
        # Database session and repositories (if database enabled)
        self.db_session = None
        self.league_repo = None
        self.team_repo = None
        
        if DATABASE_AVAILABLE and USE_DATABASE:
            self.db_session = get_session()
            self.league_repo = LeagueRepository(self.db_session)
            self.team_repo = TeamRepository(self.db_session)
            logger.info("LeagueManager using DATABASE storage")
        else:
            logger.info("LeagueManager using JSON file storage")
        
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
        
        # Distribute teams across leagues (config order / even split)
        self._distributeTeamsToLeagues(config)

        # If a prior one-time realignment saved a custom alignment, honor it — this
        # overrides the config-order split so realigned leagues survive restarts/deploys
        # (the split is otherwise recomputed from config order on every boot).
        self._applyPersistedAlignment()

        # Save to database if enabled
        if DATABASE_AVAILABLE and USE_DATABASE:
            self._saveLeaguesToDatabase()

        logger.info(f"Created {len(self.leagues)} leagues with {len(self.teams)} teams")
    
    def _saveLeaguesToDatabase(self) -> None:
        """Save leagues and team assignments to database"""
        try:
            # Save each league
            for league in self.leagues:
                # Check if league exists
                db_league = self.league_repo.get_by_name(league.name)
                if not db_league:
                    # Create new league
                    db_league = DBLeague(name=league.name)
                    self.league_repo.save(db_league)
                    self.db_session.flush()  # Get the ID
                
                # Update team league assignments
                for team in league.teamList:
                    db_team = self.team_repo.get_by_id(team.id)
                    if db_team:
                        db_team.league_id = db_league.id
                        team.league = league.name  # Update in-memory object too
                        logger.debug(f"Assigned team {team.name} (id={team.id}) to league {league.name} (id={db_league.id})")
                    else:
                        logger.warning(f"Could not find team {team.name} (id={team.id}) in database")
            
            self.db_session.commit()
            logger.info(f"Saved {len(self.leagues)} leagues to database")
            
        except Exception as e:
            logger.error(f"Failed to save leagues to database: {e}")
            self.db_session.rollback()
    
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

    def _applyPersistedAlignment(self) -> None:
        """Override the config-order distribution with a saved `league_alignment`
        (from a prior one-time realignment), so realigned leagues survive restarts
        and deploys. No-op when no alignment is stored or it doesn't cleanly cover
        the current team set (falls back to the config-order split)."""
        try:
            from game_rules import _readAppSetting
            raw = _readAppSetting('league_alignment')
        except Exception:
            raw = None
        if not raw:
            return
        import json
        try:
            alignment = json.loads(raw)  # {leagueName: [teamId, ...]}
        except Exception:
            return
        byId = {t.id: t for t in self.teams}
        allIds = [tid for ids in alignment.values() for tid in ids]
        # Every current team must be assigned exactly once, and every league name
        # in the alignment must exist — otherwise ignore and keep the config split.
        if sorted(allIds) != sorted(byId.keys()):
            logger.warning("Saved league_alignment doesn't cover current teams; keeping config-order split")
            return
        leagueByName = {lg.name: lg for lg in self.leagues}
        if any(name not in leagueByName for name in alignment):
            logger.warning("Saved league_alignment references unknown league; keeping config-order split")
            return
        for name, ids in alignment.items():
            league = leagueByName[name]
            league.teamList[:] = [byId[i] for i in ids if i in byId]
            for t in league.teamList:
                t.league = name
        logger.info("Applied persisted league alignment from app_settings")

    def realignByRecentPerformance(self, seasonNumber: int, windowSeasons: int = 2) -> Optional[Dict[str, Any]]:
        """One-time competitive realignment: rank all teams by combined win% over the
        last `windowSeasons` completed seasons and serpentine-split them evenly across
        the two leagues (rank 1->A, 2->B, 3->B, 4->A, ...), so neither league stays
        perpetually stronger. Reassigns in-memory membership, persists team.league_id,
        and stores the result as the `league_alignment` app_setting (honored on future
        boots). Returns a summary dict, or None if it can't run yet (no DB / not two
        leagues / no completed-season history in the window)."""
        if not (DATABASE_AVAILABLE and USE_DATABASE and self.db_session):
            return None
        if len(self.leagues) != 2 or len(self.teams) < 2:
            return None
        firstSeason = max(1, seasonNumber - windowSeasons)
        lastSeason = seasonNumber - 1  # window = last completed seasons
        if lastSeason < firstSeason:
            return None
        try:
            from sqlalchemy import text
            rows = self.db_session.execute(text(
                "SELECT team_id, COALESCE(SUM(wins), 0), COALESCE(SUM(losses), 0), "
                "COALESCE(SUM(score_differential), 0) FROM team_season_stats "
                "WHERE season BETWEEN :a AND :b GROUP BY team_id"),
                {"a": firstSeason, "b": lastSeason}).fetchall()
        except Exception as e:
            logger.error(f"League realignment: failed to read team_season_stats: {e}")
            return None
        agg = {r[0]: (r[1], r[2], r[3]) for r in rows}
        if not agg:
            return None  # no history yet — let the caller retry next season

        def sortKey(team):
            w, l, sd = agg.get(team.id, (0, 0, 0))
            winPct = (w / (w + l)) if (w + l) else 0.5
            # Best first: highest win%, then point differential; team.id as a stable
            # deterministic final tiebreak.
            return (-winPct, -sd, team.id)

        ranked = sorted(self.teams, key=sortKey)

        # Serpentine split into the two leagues: rank%4 in {0,3} -> league A, else B.
        # For an even team count this yields equal-size leagues with balanced strength.
        groups = ([], [])
        for rank, team in enumerate(ranked):
            groups[0 if (rank % 4 in (0, 3)) else 1].append(team)

        priorLeagueByTeam = {t.id: lg.name for lg in self.leagues for t in lg.teamList}
        moved = []
        for i, league in enumerate(self.leagues):
            league.teamList[:] = groups[i]
            for t in groups[i]:
                if priorLeagueByTeam.get(t.id) != league.name:
                    moved.append({'team': t.name, 'from': priorLeagueByTeam.get(t.id), 'to': league.name})
                t.league = league.name

        # Persist: team.league_id (via the existing saver) + the durable alignment map.
        try:
            self._saveLeaguesToDatabase()
        except Exception as e:
            logger.error(f"League realignment: failed to persist league_id: {e}")
        try:
            import json
            from game_rules import _writeAppSetting
            alignment = {lg.name: [t.id for t in lg.teamList] for lg in self.leagues}
            _writeAppSetting('league_alignment', json.dumps(alignment))
        except Exception as e:
            logger.error(f"League realignment: failed to persist league_alignment: {e}")

        return {
            'seasonNumber': seasonNumber,
            'window': [firstSeason, lastSeason],
            'moved': moved,
            'alignment': {lg.name: [t.name for t in lg.teamList] for lg in self.leagues},
        }

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
            
            # Note: Playoff results now stored in database, JSON output disabled
            # seasonDir = f'data/season{currentSeason}/games'
            # os.makedirs(seasonDir, exist_ok=True)
            # try:
            #     with open(os.path.join(seasonDir, 'postseason.json'), 'w') as jsonFile:
            #         json.dump(playoffDict, jsonFile, indent=4)
            # except Exception as e:
            #     logger.error(f"Failed to save playoff results: {e}")
        
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
    
    def checkPlayoffClinching(self, currentWeek: int, leagueHighlights: List = None) -> List[dict]:
        """
        Check for playoff clinching and elimination during regular season.
        Returns a list of event dicts: {'text': str, 'type': str, 'teamId': int}.
        type values: 'clinch_playoff', 'clinch_topseed', 'eliminated'
        """
        import floosball_methods as FloosMethods

        if leagueHighlights is None:
            leagueHighlights = []

        newEvents: List[dict] = []
        remaining = 28 - currentWeek

        def _emit(text: str, eventType: str, teamId: int) -> None:
            leagueHighlights.insert(0, {'event': {'text': text}})
            newEvents.append({'text': text, 'type': eventType, 'teamId': teamId})

        for league in self.leagues:
            standings = league.getStandings()
            if not standings:
                continue

            numPlayoffTeams = len(league.teamList) // 2
            playoffTeamList = standings[:numPlayoffTeams]
            nonPlayoffTeamsList = standings[numPlayoffTeams:]

            # Ensure flags exist
            for standing in playoffTeamList:
                team = standing['team']
                if not hasattr(team, 'clinchedPlayoffs'):
                    team.clinchedPlayoffs = False
                if not hasattr(team, 'eliminated'):
                    team.eliminated = False

            if nonPlayoffTeamsList:
                lastTeamIn = playoffTeamList[-1]['team'] if playoffTeamList else None
                firstTeamOut = nonPlayoffTeamsList[0]['team'] if nonPlayoffTeamsList else None

                # --- Top seed clinch ---
                if len(standings) >= 2:
                    team1 = standings[0]['team']
                    team2 = standings[1]['team']
                    if not hasattr(team1, 'clinchedTopSeed'):
                        team1.clinchedTopSeed = False
                    if not team1.clinchedTopSeed:
                        if FloosMethods.checkIfClinched(
                            team1.seasonTeamStats.get('wins', 0),
                            team2.seasonTeamStats.get('wins', 0),
                            remaining
                        ) or currentWeek == 28:
                            team1.clinchedTopSeed = True
                            _emit(f'{team1.city} {team1.name} have clinched the #1 seed', 'clinch_topseed', team1.id)

                # --- Playoff berth clinches ---
                if lastTeamIn and firstTeamOut:
                    for standing in playoffTeamList:
                        team = standing['team']
                        if not team.clinchedPlayoffs and not team.eliminated:
                            if FloosMethods.checkIfClinched(
                                team.seasonTeamStats.get('wins', 0),
                                firstTeamOut.seasonTeamStats.get('wins', 0),
                                remaining
                            ) or currentWeek == 28:
                                team.clinchedPlayoffs = True
                                _emit(f'{team.city} {team.name} have clinched a playoff berth', 'clinch_playoff', team.id)

                    # --- Eliminations ---
                    # Update inSeasonPressure (NOT pressureModifier directly).
                    # The blended live value is recomputed at week start via
                    # teamManager.applyRegularSeasonPressureBlend.
                    for standing in nonPlayoffTeamsList:
                        team = standing['team']

                        if team.seasonTeamStats.get('winPerc', 0) < 0.45 and currentWeek >= 14:
                            team.inSeasonPressure = 0.9

                        if not team.clinchedPlayoffs and not team.eliminated:
                            if FloosMethods.checkIfEliminated(
                                team.seasonTeamStats.get('wins', 0),
                                lastTeamIn.seasonTeamStats.get('wins', 0),
                                remaining
                            ) or currentWeek == 28:
                                team.eliminated = True
                                _emit(f'{team.city} {team.name} have faded from playoff contention', 'eliminated', team.id)
                                team.inSeasonPressure = 0.7
                            else:
                                # On the brink of elimination
                                if (team.seasonTeamStats.get('wins', 0) + remaining ==
                                        lastTeamIn.seasonTeamStats.get('wins', 0)):
                                    leagueHighlights.insert(0, {
                                        'event': {'text': f'{team.city} {team.name} are on the brink of elimination!'}
                                    })
                                    if remaining <= 5:
                                        team.inSeasonPressure = 2.0

        return newEvents
    
    @property
    def leagueList(self) -> List[League]:
        """Backward compatibility property for global leagueList"""
        return self.leagues