"""
TeamManager - Centralized team management for Floosball

Handles team creation, loading, roster management, and team data persistence.
Replaces scattered team management functions from floosball.py
"""

import json
import os
import glob
import random as _random
from typing import Dict, List, Any, Optional
import floosball_team as FloosTeam
import floosball_player as FloosPlayer
import floosball_coach as FloosCoach
from logger_config import getLogger
import numpy as np

# Database imports
try:
    from database.config import USE_DATABASE
    from database.connection import get_session
    from database.repositories import TeamRepository, LeagueRepository
    from database.models import Team as DBTeam, League as DBLeague
    DATABASE_AVAILABLE = True
except ImportError:
    DATABASE_AVAILABLE = False
    USE_DATABASE = False

class TeamManager:
    """Manages all team-related operations including creation, loading, and roster management"""
    
    def __init__(self, serviceContainer):
        self.serviceContainer = serviceContainer
        self.teams: List[FloosTeam.Team] = []
        self.leagues: List = []  # Will be typed properly when League class is available
        self.logger = getLogger("floosball.team_manager")
        
        # Database session and repositories (if database enabled)
        self.db_session = None
        self.team_repo = None
        self.league_repo = None
        
        if DATABASE_AVAILABLE and USE_DATABASE:
            self.db_session = get_session()
            self.team_repo = TeamRepository(self.db_session)
            self.league_repo = LeagueRepository(self.db_session)
            self.logger.info("TeamManager using DATABASE storage")
        else:
            self.logger.info("TeamManager using JSON file storage")

        # Fallback name pool, used only when playerManager.unusedNames isn't
        # available. The primary path now looks up the live unusedNames each
        # call (via _liveCoachPool) so that mutations always land on the
        # actual list, not a stale reference left over from before
        # playerManager re-assigned its unusedNames.
        self._coachNamePool: List[str] = []

    def _liveCoachPool(self) -> Optional[List[str]]:
        """Return the live unusedNames list from playerManager, or fall
        back to the local seed pool. Crucially, this re-resolves the
        list on every call — playerManager.loadNameLists reassigns
        self.unusedNames to a new list (DB / JSON paths both do this),
        so caching the reference once at generateTeams time made coach
        name removals land on a dead list and the same name showed up
        on a player generated later in the session.
        """
        playerMgr = getattr(self.serviceContainer, 'playerManager', None)
        if playerMgr is not None:
            live = getattr(playerMgr, 'unusedNames', None)
            if isinstance(live, list):
                return live
        return self._coachNamePool if self._coachNamePool else None

    def generateTeams(self, config: Dict[str, Any]) -> None:
        """
        Generate teams from config or load from saved data
        Replaces getTeams() function from floosball.py
        """
        self.teams.clear()
        # Seed the fallback pool from config — only consumed when playerManager
        # isn't available. Live coach naming reads playerManager.unusedNames
        # via _liveCoachPool so removals stay in sync.
        self._coachNamePool = list(config.get('players', []))

        # Try database first if enabled
        if DATABASE_AVAILABLE and USE_DATABASE and self.team_repo:
            if self._loadTeamsFromDatabase():
                self.assignCoachesToTeams()
                self.generateCoachPool()
                self.logger.info(f"Generated {len(self.teams)} teams from database")
                return
        
        # Fall back to JSON file loading
        if os.path.exists("data/teamData"):
            self._loadTeamsFromData()
            # If no teams were loaded, fall back to config
            if len(self.teams) == 0:
                self._createTeamsFromConfig(config)
        else:
            self._createTeamsFromConfig(config)
            
        self.assignCoachesToTeams()
        self.generateCoachPool()
        self.logger.info(f"Generated {len(self.teams)} teams")

    def _loadTeamsFromDatabase(self) -> bool:
        """Load teams from database"""
        try:
            # Get all teams from database
            db_teams = self.team_repo.get_all()
            
            if not db_teams:
                self.logger.debug("No teams found in database")
                return False
            
            # Convert database teams to game Team objects
            for db_team in db_teams:
                team = self._createTeamFromDatabase(db_team)
                if team:
                    self.teams.append(team)
            
            self.logger.info(f"Loaded {len(self.teams)} teams from database")

            # Load standing facilities onto each team (Markets→Facilities)
            self.loadFacilities()

            # Rebuild team rosters from player-team relationships
            self._rebuildTeamRosters()

            return True
            
        except Exception as e:
            self.logger.error(f"Failed to load teams from database: {e}")
            return False
    
    def loadFacilities(self) -> None:
        """Populate each team's `facilities` dict (facility_key -> level) from
        team_facilities (Markets→Facilities). Persistent across seasons. Safe to
        call repeatedly — fully replaces each team's dict."""
        try:
            from database.models import TeamFacility
            if not self.db_session:
                return
            byTeam = {}
            for row in self.db_session.query(TeamFacility).all():
                byTeam.setdefault(row.team_id, {})[row.facility_key] = row.level
            for team in self.teams:
                team.facilities = byTeam.get(team.id, {})
        except Exception as e:
            self.logger.warning(f"Failed to load team facilities: {e}")

    def ensureTeamFacilities(self) -> None:
        """Seed facilities for any team that has none, GRANDFATHERED from the
        team's current market tier (MEGA→Lv4, LARGE→Lv3, MID→Lv2, SMALL→Lv1;
        Stadium Lv0) so an existing DB reproduces today's tier perks. The tier is
        read from the latest team_funding row (team.fundingTier isn't populated
        yet at this point in boot). Idempotent — teams that already have facility
        rows are skipped. This is the RELIABLE seed point (runs after saveTeamData,
        with teams persisted); the init-time migration no-ops when teams don't
        exist yet, which is why this — not a flat MID baseline — does the
        grandfathering. A fresh league with no funding history falls back to MID."""
        try:
            from database.models import TeamFacility, TeamFunding
            from constants import (FACILITY_CATALOG, MIGRATION_TIER_START_LEVEL,
                                   MIGRATION_STADIUM_START_LEVEL)
            from sqlalchemy import func
            if not self.db_session:
                return
            existing = {tid for (tid,) in self.db_session.query(TeamFacility.team_id).distinct().all()}
            # latest-season market tier per team (the grandfather basis)
            sub = (self.db_session.query(TeamFunding.team_id, func.max(TeamFunding.season).label('s'))
                   .group_by(TeamFunding.team_id).subquery())
            tierByTeam = {tid: (tier or 'MID_MARKET') for tid, tier in
                          self.db_session.query(TeamFunding.team_id, TeamFunding.funding_tier)
                          .join(sub, (TeamFunding.team_id == sub.c.team_id) & (TeamFunding.season == sub.c.s)).all()}
            seeded = 0
            for team in self.teams:
                if not getattr(team, 'id', None) or team.id in existing:
                    continue
                tier = tierByTeam.get(team.id, 'MID_MARKET')
                for key in FACILITY_CATALOG:
                    level = (MIGRATION_STADIUM_START_LEVEL if key == 'stadium'
                             else MIGRATION_TIER_START_LEVEL.get(tier, 2))
                    self.db_session.add(TeamFacility(team_id=team.id, facility_key=key, level=level))
                seeded += 1
            if seeded:
                self.db_session.commit()
                self.logger.info(f"Seeded facilities (tier-grandfathered) for {seeded} team(s)")
            self.loadFacilities()
        except Exception as e:
            self.db_session.rollback() if self.db_session else None
            self.logger.warning(f"ensureTeamFacilities failed: {e}")

    def _createTeamFromDatabase(self, db_team) -> Optional[FloosTeam.Team]:
        """Create a game Team object from database Team model"""
        try:
            # Create basic team
            team = FloosTeam.Team(db_team.name)
            
            # Basic info
            team.id = db_team.id
            team.city = db_team.city
            team.abbr = db_team.abbr
            team.color = db_team.color
            team.secondaryColor = getattr(db_team, 'secondary_color', db_team.color)
            team.tertiaryColor = getattr(db_team, 'tertiary_color', db_team.color)
            team.logoInvert = bool(getattr(db_team, 'logo_invert', False) or False)
            
            # Ratings
            team.offenseRating = db_team.offense_rating or 0
            team.defenseRunCoverageRating = db_team.defense_run_coverage_rating or 0
            team.defensePassCoverageRating = db_team.defense_pass_coverage_rating or 0
            team.defensePassRushRating = db_team.defense_pass_rush_rating or 0
            team.defenseRating = db_team.defense_rating or 0
            team.overallRating = db_team.overall_rating or 0
            
            # Performance data
            team.gmScore = db_team.gm_score or 0
            team.defenseOverallTier = db_team.defense_tier or 0
            team.defenseSeasonPerformanceRating = db_team.defense_season_performance or 0
            # Where the club sits in its hot/cold arc — restored so a mid-season
            # restart doesn't flatten every team back to neutral form.
            team.formOffset = getattr(db_team, 'form_offset', 0.0) or 0.0
            # Division membership survives a restart. Without this, a mid-season deploy
            # silently un-divisions the whole league.
            team.division = getattr(db_team, 'division', None)

            # Historical stats (stored as JSON in database)
            team.allTimeTeamStats = db_team.all_time_stats or {}
            team.divisionTitles = db_team.division_titles or []
            team.leagueChampionships = db_team.league_championships or []
            team.floosbowlChampionships = db_team.floosbowl_championships or []
            team.regularSeasonChampions = db_team.top_seeds or []  # top_seeds = regular season champions
            team.playoffAppearances = db_team.playoff_appearances if isinstance(db_team.playoff_appearances, int) else 0
            
            # Roster history if available
            if db_team.roster_history:
                team.rosterHistory = db_team.roster_history
            
            # Note: Roster will be populated separately after players are loaded
            # This is handled by PlayerManager assigning players to teams
            
            return team
            
        except Exception as e:
            self.logger.error(f"Failed to create team from database: {e}")
            return None
    
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
        newTeam.secondaryColor = teamData.get('secondaryColor', teamData['color'])
        newTeam.tertiaryColor = teamData.get('tertiaryColor', teamData['color'])
        newTeam.logoInvert = bool(teamData.get('logoInvert', False))
        
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
        newTeam.divisionTitles = teamData.get('divisionTitles', [])
        newTeam.leagueChampionships = teamData['leagueChampionships']
        newTeam.floosbowlChampionships = teamData['floosbowlChampionships']
        newTeam.topSeeds = teamData.get('topSeeds', teamData.get('regularSeasonChampions', []))
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
    
    def _rebuildTeamRosters(self) -> None:
        """Rebuild team rosters from player-team relationships after loading from database"""
        # Get players from player manager
        playerManager = self.serviceContainer.getService('player_manager')
        if not playerManager:
            self.logger.warning("PlayerManager not available, cannot rebuild rosters")
            return
        
        all_players = playerManager.activePlayers
        self.logger.info(f"Rebuilding rosters from {len(all_players)} active players")
        
        # Build a dictionary of team_id -> players
        team_players = {}
        players_without_team = 0
        for player in all_players:
            # Check if player has a team assignment
            if hasattr(player, 'team') and player.team is not None:
                team_id = player.team if isinstance(player.team, int) else player.team.id
                if team_id not in team_players:
                    team_players[team_id] = []
                team_players[team_id].append(player)
            else:
                players_without_team += 1
        
        self.logger.info(f"Found players assigned to {len(team_players)} teams")
        self.logger.info(f"DEBUG: {players_without_team} players without team assignment")
        self.logger.info(f"DEBUG: team_players keys = {list(team_players.keys())}")
        
        # Assign players to teams
        teams_with_rosters = 0
        for team in self.teams:
            if team.id in team_players:
                # Clear existing roster
                team.rosterDict = {}
                team.playerCap = 0
                team.playerNumbersList = []
                
                # Track WR count for proper slot assignment (max 2: wr1 and wr2)
                wr_count = 0
                
                # Assign players based on their position
                # Roster keys are ONLY: qb, rb, wr1, wr2, te, k
                for player in team_players[team.id]:
                    # Get position value (handle both enum and int)
                    if hasattr(player.position, 'value'):
                        pos_value = player.position.value
                    else:
                        pos_value = int(player.position)
                    
                    # Map position value to roster key
                    # Position enum: QB=1, RB=2, WR=3, TE=4, K=5
                    position_map = {
                        1: 'qb',   # Quarterback - single slot
                        2: 'rb',   # Running Back - single slot  
                        3: 'wr',   # Wide Receiver - has wr1, wr2 slots
                        4: 'te',   # Tight End - single slot
                        5: 'k'     # Kicker - single slot
                    }
                    
                    # Skip positions not in the roster
                    if pos_value not in position_map:
                        continue
                    
                    pos_key = position_map[pos_value]
                    
                    # Handle WR positions (wr1, wr2 only)
                    if pos_key == 'wr':
                        wr_count += 1
                        if wr_count <= 2:
                            roster_key = f"wr{wr_count}"
                        else:
                            # Skip additional WRs beyond wr2
                            continue
                    else:
                        # Single slot positions (qb, rb, te, k)
                        # Only use first player at this position
                        if pos_key in team.rosterDict:
                            continue
                        roster_key = pos_key
                    
                    team.rosterDict[roster_key] = player
                    team.playerCap += player.capHit
                    # Only track non-zero numbers — zero is a sentinel for
                    # "unassigned" and would otherwise pollute the dedupe set.
                    if player.currentNumber:
                        team.playerNumbersList.append(player.currentNumber)

                    # Update player's team reference to be the Team object
                    player.team = team

                # Backfill jersey numbers for any rostered player still at 0.
                # Legacy promoted-prospect data shipped without a number; this
                # one-shot pass assigns one on first boot after the fix.
                backfilled = 0
                for player in team.rosterDict.values():
                    if player and not getattr(player, 'currentNumber', 0):
                        team.assignPlayerNumber(player)
                        backfilled += 1
                if backfilled:
                    self.logger.info(f"Backfilled {backfilled} jersey number(s) for {team.name}")

                teams_with_rosters += 1
                # Debug: print first team's roster keys
                if teams_with_rosters == 1:
                    self.logger.info(f"DEBUG: First team roster keys: {list(team.rosterDict.keys())}")
                self.logger.debug(f"Rebuilt roster for {team.name}: {len(team.rosterDict)} players")

        self.logger.info(f"Rebuilt rosters for {teams_with_rosters}/{len(self.teams)} teams")
    
    def _createTeamsFromConfig(self, config: Dict[str, Any]) -> None:
        """Create new teams from configuration"""
        teamId = 1
        
        for teamConfig in config['teams']:
            team = FloosTeam.Team(teamConfig['name'])
            team.city = teamConfig['city']
            team.abbr = teamConfig['abbr']
            team.color = teamConfig['color']
            team.secondaryColor = teamConfig.get('secondaryColor', teamConfig['color'])
            team.tertiaryColor = teamConfig.get('tertiaryColor', teamConfig['color'])
            team.logoInvert = bool(teamConfig.get('logoInvert', False))
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
        
        # Pre-generate team avatars
        self._pregenerateAvatars()
            
        self.logger.info(f"Initialized {len(self.teams)} teams")
    
    def _pregenerateAvatars(self) -> None:
        """Pre-generate avatars for all teams"""
        try:
            from avatar_generator import getAvatarGenerator
            avatarGen = getAvatarGenerator()
            generated = avatarGen.pregenerateTeamAvatars(self.teams)
            self.logger.info(f"Avatar pre-generation complete: {generated} new, {len(self.teams) - generated} cached")
        except Exception as e:
            self.logger.warning(f"Failed to pre-generate avatars: {e}")
    
    def _setupAndSaveTeam(self, team: FloosTeam.Team) -> None:
        """Setup team and save to database or JSON file"""
        team.setupTeam()
        
        # Save to database or JSON based on configuration
        if DATABASE_AVAILABLE and USE_DATABASE and self.team_repo:
            self._saveTeamToDatabase(team)
        else:
            self._saveTeamToJSON(team)
    
    def saveTeamData(self) -> None:
        """Save all teams to database or JSON"""
        if DATABASE_AVAILABLE and USE_DATABASE and self.team_repo:
            for team in self.teams:
                self._saveTeamToDatabase(team)
            self.db_session.commit()
            self.logger.info(f"Saved {len(self.teams)} teams to database")
        else:
            for team in self.teams:
                self._saveTeamToJSON(team)
            self.logger.info(f"Saved {len(self.teams)} teams to JSON files")
    
    def _saveTeamToDatabase(self, team: FloosTeam.Team) -> None:
        """Save a single team to database"""
        try:
            # Create or update team in database
            db_team = self.team_repo.get_by_id(team.id)
            
            if not db_team:
                # Create new team
                from database.models import Team as DBTeam
                db_team = DBTeam(
                    id=team.id,
                    name=team.name,
                    city=team.city,
                    abbr=team.abbr,
                    color=team.color,
                    secondary_color=getattr(team, 'secondaryColor', team.color),
                    tertiary_color=getattr(team, 'tertiaryColor', team.color),
                    logo_invert=bool(getattr(team, 'logoInvert', False))
                )
            else:
                # Update color fields if they exist
                db_team.secondary_color = getattr(team, 'secondaryColor', team.color)
                db_team.tertiary_color = getattr(team, 'tertiaryColor', team.color)
                db_team.logo_invert = bool(getattr(team, 'logoInvert', False))
            
            # Update team data
            db_team.offense_rating = team.offenseRating
            db_team.defense_run_coverage_rating = team.defenseRunCoverageRating
            db_team.defense_pass_coverage_rating = team.defensePassCoverageRating
            db_team.defense_pass_rush_rating = team.defensePassRushRating
            db_team.defense_rating = team.defenseRating
            db_team.overall_rating = team.overallRating
            db_team.gm_score = team.gmScore
            db_team.defense_tier = team.defenseOverallTier
            db_team.defense_season_performance = team.defenseSeasonPerformanceRating
            db_team.form_offset = getattr(team, 'formOffset', 0.0) or 0.0
            db_team.division = getattr(team, 'division', None)

            # Historical stats (stored as JSON)
            db_team.all_time_stats = team.allTimeTeamStats
            db_team.division_titles = getattr(team, 'divisionTitles', []) or []
            db_team.league_championships = team.leagueChampionships
            db_team.floosbowl_championships = team.floosbowlChampionships
            db_team.top_seeds = team.topSeeds
            db_team.playoff_appearances = team.playoffAppearances
            
            # Denormalized all-time stats for efficient querying
            if team.allTimeTeamStats:
                db_team.all_time_wins = team.allTimeTeamStats.get('wins', 0)
                db_team.all_time_losses = team.allTimeTeamStats.get('losses', 0)
                offense = team.allTimeTeamStats.get('Offense', {})
                db_team.all_time_points = offense.get('pts', 0)
                db_team.all_time_yards = offense.get('totalYards', 0)
                db_team.all_time_touchdowns = offense.get('tds', 0)
            
            if hasattr(team, 'rosterHistory'):
                db_team.roster_history = team.rosterHistory
            
            # Handle league assignment - look up league_id from league name if available
            if hasattr(team, 'league') and team.league:
                # Team has a league name, look up the league_id
                if self.league_repo:
                    db_league = self.league_repo.get_by_name(team.league)
                    if db_league:
                        db_team.league_id = db_league.id
            # If team doesn't have a league but db_team already has league_id, preserve it
            # (This prevents overwriting league assignments set by LeagueManager)
            
            # Roster is managed through Player.team_id foreign keys
            
            self.team_repo.save(db_team)
            self.db_session.commit()
            
        except Exception as e:
            self.logger.error(f"Failed to save team {team.name} to database: {e}")
            self.db_session.rollback()
    
    def _saveTeamToJSON(self, team: FloosTeam.Team) -> None:
        """Save team to JSON file (legacy mode)"""
        team.setupTeam()
        
        teamDict = {
            'name': team.name,
            'city': team.city,
            'abbr': team.abbr,
            'color': team.color,
            'secondaryColor': getattr(team, 'secondaryColor', team.color),
            'tertiaryColor': getattr(team, 'tertiaryColor', team.color),
            'logoInvert': bool(getattr(team, 'logoInvert', False)),
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
            'topSeeds': team.topSeeds,
            'divisionTitles': getattr(team, 'divisionTitles', []) or [],
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
                
                # Archive current stats if they have real game data (skip empty defaults)
                hasGameData = team.seasonTeamStats.get('wins', 0) > 0 or team.seasonTeamStats.get('losses', 0) > 0
                if hasattr(team, 'statArchive') and team.seasonTeamStats and hasGameData:
                    team.statArchive.insert(0, copy.deepcopy(team.seasonTeamStats))
                
                # Properly restore the full structure from teamStatsDict
                team.seasonTeamStats = copy.deepcopy(FloosTeam.teamStatsDict)
                
                # Restore preserved values
                team.seasonTeamStats['elo'] = current_elo
                team.seasonTeamStats['overallRating'] = current_rating
                sm = self.serviceContainer.getService('season_manager')
                team.seasonTeamStats['season'] = sm.currentSeason.seasonNumber if sm and sm.currentSeason else 1
                
                # Clear schedule and season-specific flags for new season
                team.schedule = []

            # Reset season-specific flags (must happen even if seasonTeamStats missing)
            team.eliminated = False
            team.clinchedPlayoffs = False
            team.clinchedTopSeed = False
            team.leagueChampion = False
            team.floosbowlChampion = False
            team.winningStreak = False

        self.logger.info("Cleared season stats for all teams")

    def loadSeasonTeamStats(self, seasonNumber: int) -> None:
        """Restore team.seasonTeamStats from DB for a season in progress (used on mid-season resume)."""
        if not (DATABASE_AVAILABLE and USE_DATABASE and self.db_session):
            return
        try:
            from database.models import TeamSeasonStats as DBTeamSeasonStats
            for team in self.teams:
                dbStats = self.db_session.query(DBTeamSeasonStats).filter_by(
                    team_id=team.id, season=seasonNumber
                ).first()
                if dbStats:
                    team.seasonTeamStats['wins'] = dbStats.wins
                    team.seasonTeamStats['losses'] = dbStats.losses
                    team.seasonTeamStats['winPerc'] = dbStats.win_percentage or 0.0
                    team.seasonTeamStats['streak'] = dbStats.streak or 0
                    team.seasonTeamStats['scoreDiff'] = dbStats.score_differential or 0
                    # Without these the division and league records restart from zero on
                    # every boot, and the playoff tiebreaker compares partial seasons.
                    team.seasonTeamStats['divWins'] = getattr(dbStats, 'div_wins', 0) or 0
                    team.seasonTeamStats['divLosses'] = getattr(dbStats, 'div_losses', 0) or 0
                    team.seasonTeamStats['divTies'] = getattr(dbStats, 'div_ties', 0) or 0
                    team.seasonTeamStats['lgWins'] = getattr(dbStats, 'lg_wins', 0) or 0
                    team.seasonTeamStats['lgLosses'] = getattr(dbStats, 'lg_losses', 0) or 0
                    team.seasonTeamStats['lgTies'] = getattr(dbStats, 'lg_ties', 0) or 0
                    team.seasonTeamStats['elo'] = dbStats.elo or team.seasonTeamStats.get('elo', 1500)
                    team.elo = team.seasonTeamStats['elo']
                    team.seasonTeamStats['madePlayoffs'] = dbStats.made_playoffs
                    team.seasonTeamStats['bigPlays'] = dbStats.big_plays or 0
                    team.seasonTeamStats['peakStreak'] = dbStats.peak_streak or 0
                    if dbStats.offense_stats:
                        team.seasonTeamStats['Offense'].update(dbStats.offense_stats)
                    if dbStats.defense_stats:
                        team.seasonTeamStats['Defense'].update(dbStats.defense_stats)
                    self.logger.debug(
                        f"Restored season stats for {team.name}: "
                        f"{dbStats.wins}W-{dbStats.losses}L"
                    )
            self.logger.info(f"Restored team season stats for season {seasonNumber}")
        except Exception as e:
            self.logger.error(f"Failed to restore team season stats: {e}")

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
                if team.overallRating > 0 and meanRating > 0:
                    teamRatingRank = round(team.overallRating / meanRating, 2)
                    team.elo = round(team.elo * teamRatingRank)
                    self.logger.debug(f"Team {team.name}: ELO updated for new team to {team.elo} (rank: {teamRatingRank}, rating: {team.overallRating})")
                else:
                    # If rating not calculated yet, keep default 1500
                    self.logger.warning(f"Team {team.name}: overallRating is {team.overallRating}, keeping default ELO 1500")

            
            # Clamp to reasonable bounds at season reset
            team.elo = max(800, min(2200, team.elo))

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
    
    def updateEloAfterGame(self, homeTeam, awayTeam, homeScore: int, awayScore: int, winningTeam,
                           preGameHomeWp: float = None, preGameAwayWp: float = None) -> None:
        """
        Update ELO ratings for both teams after a game based on the result and margin of victory.

        Args:
            preGameHomeWp: Home win probability at kickoff as 0-1 decimal (stored on game object).
                           Falls back to ELO-derived probability if not provided.
            preGameAwayWp: Away win probability at kickoff as 0-1 decimal.
        """
        import math

        k = 20  # K-factor - controls rating volatility

        homeTeamElo = getattr(homeTeam, 'elo', 1500)
        awayTeamElo = getattr(awayTeam, 'elo', 1500)

        # Use pre-game WP stored at kickoff (0-1 decimal), or fall back to ELO calculation
        if preGameHomeWp is not None and preGameAwayWp is not None:
            homeTeamWinProbability = preGameHomeWp
            awayTeamWinProbability = preGameAwayWp
        else:
            homeTeamWinProbability, awayTeamWinProbability = self.calculateWinProbability(homeTeam, awayTeam)

        # Margin of victory multiplier (538-style): bigger upsets count more
        # Clamp denominator to avoid near-zero or negative values for extreme ELO gaps
        scoreDiff = abs(homeScore - awayScore)

        if winningTeam == homeTeam:
            movDenominator = max(0.3, (homeTeamElo - awayTeamElo) * 0.001 + 2.2)
            marginOfVictoryMultiplier = math.log(scoreDiff + 1) * (2.2 / movDenominator)
            homeTeam.elo = round(homeTeamElo + (k * marginOfVictoryMultiplier) * (1 - homeTeamWinProbability))
            awayTeam.elo = round(awayTeamElo + (k * marginOfVictoryMultiplier) * (0 - awayTeamWinProbability))
        else:
            movDenominator = max(0.3, (awayTeamElo - homeTeamElo) * 0.001 + 2.2)
            marginOfVictoryMultiplier = math.log(scoreDiff + 1) * (2.2 / movDenominator)
            homeTeam.elo = round(homeTeamElo + (k * marginOfVictoryMultiplier) * (0 - homeTeamWinProbability))
            awayTeam.elo = round(awayTeamElo + (k * marginOfVictoryMultiplier) * (1 - awayTeamWinProbability))
        
        # No in-season clamping - ELO moves freely; bounds applied at season reset in setNewElo()
        
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
        """Get team by ID via an O(1) id->team index.

        Called heavily when building standings/snapshots/favorite-team data;
        the index is rebuilt only when the team count changes (32 teams,
        effectively never mid-season)."""
        count = len(self.teams)
        if getattr(self, '_teamByIdCount', None) != count or not hasattr(self, '_teamById'):
            self._teamById = {t.id: t for t in self.teams}
            self._teamByIdCount = count
        return self._teamById.get(teamId)
    
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
        """Set the prior-season expectation baseline for every team. Called at
        season start. Sets `team.priorSeasonPressure` based on last season's
        playoff finish or win percentage; resets `inSeasonPressure` to 1.0.
        The live `pressureModifier` is initialized to the prior baseline and
        then wanes across the regular season as in-season forces take over
        (see applyRegularSeasonPressureBlend).
        """
        self.logger.info(f"Setting prior-season pressure baselines for season {currentSeason}")

        for team in self.teams:
            prior = 1.0  # Default: no prior expectations

            # Only apply historical pressure if this is not the first season
            if currentSeason > 1 and hasattr(team, 'statArchive') and len(team.statArchive) > 0:
                previousSeason = team.statArchive[0]

                if previousSeason.get('madePlayoffs', False):
                    if not previousSeason.get('floosbowlChamp', False):
                        leagueChamp = previousSeason.get('leageChamp', False)  # legacy typo in stored key
                        topSeed = previousSeason.get('topSeed', False)
                        if leagueChamp and topSeed:
                            prior = 1.5
                        elif leagueChamp or topSeed:
                            prior = 1.4
                        else:
                            prior = 1.2
                    # Floos Bowl champs ride at 1.0 — they already won it all,
                    # nothing to prove. (Could flip to a "defend the throne"
                    # bump later if it feels right.)
                else:
                    winPerc = previousSeason.get('winPerc', 0)
                    if winPerc < 0.25:
                        prior = 0.7
                    elif winPerc < 0.4:
                        prior = 0.8
                    elif winPerc < 0.5:
                        prior = 0.9
                    else:
                        prior = 1.0

            team.priorSeasonPressure = prior
            team.inSeasonPressure = 1.0
            team.pressureModifier = prior  # Game-time value starts at full prior expectation
            team.currentWinStreak = 0
            team.streakPressure = 0.0
            # Form arcs are a within-season story — everyone starts flat, and
            # the oscillation layer builds a new arc off this season's results.
            team.formOffset = 0.0
            self.logger.debug(f"{team.name}: priorSeasonPressure={prior}")

        self.logger.info("Prior-season pressure baselines set")
        self.logPressureSnapshot("season_start", season=currentSeason, week=0)
    
    def updateInSeasonPressureModifiers(self, currentWeek: int, nonPlayoffTeamsList: List, lastTeamIn) -> List[Dict[str, str]]:
        """Update each team's `inSeasonPressure` (NOT pressureModifier directly)
        based on current standings and elimination math. The blended live
        pressureModifier gets recomputed in applyRegularSeasonPressureBlend.
        """
        leagueHighlights = []

        self.logger.info(f"Updating in-season pressure for week {currentWeek}")

        for standing in nonPlayoffTeamsList:
            team = standing['team'] if isinstance(standing, dict) else standing

            # Poor performers late in season: in-season pressure dips
            if team.seasonTeamStats.get('winPerc', 0) < 0.45 and currentWeek >= 14:
                team.inSeasonPressure = 0.9

            if not getattr(team, 'clinchedPlayoffs', False) and not getattr(team, 'eliminated', False):
                import floosball_methods as FloosMethods

                team.eliminated = FloosMethods.checkIfEliminated(
                    team.seasonTeamStats.get('wins', 0),
                    lastTeamIn.seasonTeamStats.get('wins', 0),
                    28 - currentWeek
                )

                if team.eliminated:
                    leagueHighlights.insert(0, {
                        'event': {'text': f'{team.city} {team.name} have faded from playoff contention'}
                    })
                    team.inSeasonPressure = 0.7
                else:
                    teamMaxWins = team.seasonTeamStats.get('wins', 0) + (28 - currentWeek)
                    lastTeamWins = lastTeamIn.seasonTeamStats.get('wins', 0)

                    if teamMaxWins == lastTeamWins:
                        leagueHighlights.insert(0, {
                            'event': {'text': f'{team.city} {team.name} are on the brink of elimination!'}
                        })
                        if (28 - currentWeek) <= 5:
                            team.inSeasonPressure = 2.0  # Must-win

        self.logger.info(f"In-season pressure update complete for week {currentWeek}")
        return leagueHighlights

    def applyRegularSeasonPressureBlend(self, currentWeek: int, season: int = None) -> None:
        """Blend prior-season expectation into in-season pressure based on
        how far we are into the regular season. Call this at week start during
        the regular season — the live `pressureModifier` becomes the blended
        value used by the game pressure calculation. Playoff and Floos Bowl
        code continues to set pressureModifier directly and overrides the
        blend.

        progress: 0 at week 1, 1 at week 15+. Linear ramp.
            week 1  → 100% prior, 0% in-season
            week 8  → ~50/50
            week 15 → 0% prior, 100% in-season
        """
        progress = max(0.0, min(1.0, (currentWeek - 1) / 14.0))
        for team in self.teams:
            prior = getattr(team, 'priorSeasonPressure', 1.0)
            inseason = getattr(team, 'inSeasonPressure', 1.0)
            blended = prior * (1.0 - progress) + inseason * progress
            team.pressureModifier = round(blended, 3)
        self.logPressureSnapshot(f"week_blend(progress={progress:.2f})",
                                 season=season, week=currentWeek)
    
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
        self.logPressureSnapshot(f"playoff_round_{currentRound}")
    
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
        self.logPressureSnapshot("floos_bowl")
    
    def resetPressureModifiers(self) -> None:
        """Reset all team pressure modifiers to default (1.0)"""
        self.logger.info("Resetting all pressure modifiers to default")

        for team in self.teams:
            team.pressureModifier = 1.0

        self.logger.info("All pressure modifiers reset to 1.0")

    def logPressureSnapshot(self, context: str, season: int = None, week: int = None) -> None:
        """Diagnostic dump of every team's pressure modifier — both the raw
        baseline value and the market-tier scaled effective value used at game
        time. Writes to logs/pressure_diag.log via the dedicated pressure_diag
        logger (separate from the main app log). Tagged with context/season/
        week so you can grep across the file to track fluctuations.
        """
        diagLogger = _getPressureDiagLogger()
        for team in self.teams:
            diagLogger.info(formatPressureDiagLine(team, context, season=season, week=week))

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

    # -------------------------------------------------------------------------
    # Coach management
    # -------------------------------------------------------------------------

    def generateCoach(self, seed: int = None, deferSave: bool = False) -> FloosCoach.Coach:
        """Create a new Coach with generated attributes and a unique name from the pool.

        Prefers playerManager.popUniqueName when available so any name
        already attached to a live player or coach is dropped from the
        pool rather than handed to the new coach. Defensive against the
        kind of pollution that produced coach/player and player/player
        collisions in past seasons.

        deferSave=True skips the per-call saveUnusedNames database write.
        Caller is responsible for invoking playerMgr.saveUnusedNames()
        after the batch completes. Used by batch coach-generation paths
        (e.g. generateCoachCandidates) to avoid 96 separate write-lock
        acquisitions inside one outer transaction.
        """
        coach = FloosCoach.Coach()
        coach.generateAttributes(seed=seed)
        playerMgr = None
        try:
            playerMgr = self.serviceContainer.getService('player_manager')
        except Exception:
            pass

        name = None
        # Flavor: a retired player occasionally returns as a coach — reuse their name
        # rather than drawing a fresh one. Skip names already worn by a live coach.
        try:
            from constants import COACH_RETIRED_NAME_CHANCE
            retired = getattr(playerMgr, 'retiredPlayers', None) if playerMgr else None
            if retired and _random.random() < COACH_RETIRED_NAME_CHANCE:
                usedCoachNames = {t.coach.name for t in self.teams
                                  if getattr(t, 'coach', None) and getattr(t.coach, 'name', None)}
                cands = [p.name for p in retired
                         if getattr(p, 'name', None) and p.name not in usedCoachNames]
                if cands:
                    name = _random.choice(cands)
        except Exception:
            name = None

        if name is not None:
            pass  # took a retired player's name above
        elif playerMgr and hasattr(playerMgr, 'popUniqueName'):
            name = playerMgr.popUniqueName()
            if name is not None and not deferSave:
                playerMgr.saveUnusedNames()
        else:
            # Fallback: legacy path against the local pool. Still mutates
            # the live unusedNames via _liveCoachPool when present.
            pool = self._liveCoachPool()
            if pool:
                name = _random.choice(pool)
                pool.remove(name)
                if playerMgr and hasattr(playerMgr, 'saveUnusedNames') and not deferSave:
                    playerMgr.saveUnusedNames()

        if name is not None:
            coach.name = name
        else:
            coach.generateName()
        return coach

    def _saveCoachToDatabase(self, team: FloosTeam.Team, session=None) -> None:
        """Persist team.coach to the coaches table and set Team.coach_id.

        Single source of truth: Team.coach_id. We write Coach row attributes
        (name, ratings, etc.) and point the team at the coach via coach_id.
        No Coach.team_id back-reference — it doesn't exist anymore.

        Optional `session` lets callers (e.g. the GM hire-coach resolution
        flow) share their connection so this save lands in the same
        transaction.
        """
        targetSession = session if session is not None else self.db_session
        if not (DATABASE_AVAILABLE and USE_DATABASE and targetSession and team.coach):
            return
        try:
            from database.models import Coach as DBCoach
            from database.models import Team as DBTeam
            dbCoach = targetSession.get(DBCoach, team.coach.id) if team.coach.id else None
            isNew = dbCoach is None
            if isNew:
                # Populate required fields BEFORE add() so the implicit flush
                # at .id access doesn't INSERT with NULL name (coaches.name
                # is NOT NULL).
                dbCoach = DBCoach(name=team.coach.name)
            dbCoach.name = team.coach.name
            dbCoach.seasons_coached = team.coach.seasonsCoached
            dbCoach.seasons_with_team = getattr(team.coach, 'seasonsWithTeam', 0)
            dbCoach.offensive_mind = team.coach.offensiveMind
            dbCoach.defensive_mind = team.coach.defensiveMind
            dbCoach.adaptability = team.coach.adaptability
            dbCoach.aggressiveness = team.coach.aggressiveness
            dbCoach.clock_management = team.coach.clockManagement
            dbCoach.player_development = team.coach.playerDevelopment
            dbCoach.scouting = getattr(team.coach, 'scouting', 80)
            dbCoach.attitude = getattr(team.coach, 'attitude', 80)
            dbCoach.fan_trust = getattr(team.coach, 'fanTrust', 80)
            dbCoach.overall_rating = team.coach.overallRating
            if isNew:
                targetSession.add(dbCoach)
            targetSession.flush()
            team.coach.id = dbCoach.id
            # Single source of truth — point the team at this coach.
            dbTeam = targetSession.get(DBTeam, team.id)
            if dbTeam:
                dbTeam.coach_id = dbCoach.id
            if session is None:
                targetSession.commit()
        except Exception as e:
            self.logger.error(f"Failed to save coach for {team.name}: {e}")
            if session is None:
                targetSession.rollback()
            else:
                raise

    def _loadCoachFromDatabase(self, team: FloosTeam.Team) -> bool:
        """Load this team's coach from DB via Team.coach_id. Returns True if found."""
        if not (DATABASE_AVAILABLE and USE_DATABASE and self.db_session):
            return False
        try:
            from database.models import Coach as DBCoach
            from database.models import Team as DBTeam
            dbTeam = self.db_session.get(DBTeam, team.id)
            if not dbTeam or not dbTeam.coach_id:
                return False
            dbCoach = self.db_session.get(DBCoach, dbTeam.coach_id)
            if dbCoach is None:
                return False
            coach = FloosCoach.Coach()
            coach.id = dbCoach.id
            coach.name = dbCoach.name
            coach.seasonsCoached = dbCoach.seasons_coached
            coach.seasonsWithTeam = getattr(dbCoach, 'seasons_with_team', 0) or 0
            # Backfill seasonsCoached if it was never incremented (pre-fix data)
            if coach.seasonsCoached == 0:
                from database.models import Season as DBSeason
                latestSeason = self.db_session.query(DBSeason).order_by(DBSeason.season_number.desc()).first()
                if latestSeason and latestSeason.season_number > 1:
                    coach.seasonsCoached = latestSeason.season_number - 1
                    dbCoach.seasons_coached = coach.seasonsCoached
                    self.db_session.commit()
                    self.logger.info(f"Backfilled {coach.name} seasonsCoached to {coach.seasonsCoached}")
            coach.offensiveMind = dbCoach.offensive_mind
            coach.defensiveMind = dbCoach.defensive_mind
            coach.adaptability = dbCoach.adaptability
            coach.aggressiveness = dbCoach.aggressiveness
            coach.clockManagement = dbCoach.clock_management
            coach.playerDevelopment = dbCoach.player_development
            coach.scouting = getattr(dbCoach, 'scouting', 80) or 80
            coach.attitude = getattr(dbCoach, 'attitude', 80) or 80
            coach.fanTrust = getattr(dbCoach, 'fan_trust', 80) or 80
            team.coach = coach
            # Remove coach name from the LIVE unused-names pool so no future
            # player gets it. Goes through _liveCoachPool to read whatever
            # list playerManager currently considers authoritative — caching
            # the reference at generateTeams time was unsafe because
            # loadNameLists reassigns it.
            pool = self._liveCoachPool()
            if pool and coach.name in pool:
                pool.remove(coach.name)
                playerMgr = getattr(self.serviceContainer, 'playerManager', None)
                if playerMgr:
                    playerMgr.saveUnusedNames()
            self.logger.debug(f"Loaded coach {coach.name} from DB for {team.name}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to load coach for {team.name}: {e}")
            return False

    def assignCoachesToTeams(self) -> None:
        """Assign a coach to each team. Loads from DB if available; generates new one otherwise."""
        for team in self.teams:
            if team.coach is None:
                if not self._loadCoachFromDatabase(team):
                    team.coach = self.generateCoach()
                    self._saveCoachToDatabase(team)
                    self.logger.debug(f"Generated and saved coach {team.coach.name} for {team.name}")

    def hireCoach(self, team: FloosTeam.Team, coach: FloosCoach.Coach, session=None) -> None:
        """Assign a specific coach to a team and persist the assignment.

        Without _saveCoachToDatabase, the new coach exists only in memory —
        the GM hire-coach fallback path (no vote met threshold → auto-generate
        a coach) leaves the team coachless on the next restart, since
        _loadCoachFromDatabase finds no Coach row tied to team_id.

        Optional `session` is forwarded to _saveCoachToDatabase so callers
        like the GM resolution flow can keep all writes on one connection
        and avoid SQLite write-lock contention.
        """
        team.coach = coach
        self._saveCoachToDatabase(team, session=session)

    def fireCoach(self, team: FloosTeam.Team, session=None) -> None:
        """Remove a team's coach. Single write: Team.coach_id = None.

        With the dual-direction model gone, fire is a one-step operation —
        we null out the team's pointer at the coach and the coach itself
        becomes an unassigned row (no Team.coach_id references it).
        """
        team.coach = None
        targetSession = session if session is not None else self.db_session
        if not (DATABASE_AVAILABLE and USE_DATABASE and targetSession is not None):
            return
        try:
            from database.models import Team as DBTeam
            dbTeam = targetSession.get(DBTeam, team.id)
            if dbTeam is not None:
                dbTeam.coach_id = None
                targetSession.flush()
        except Exception as e:
            self.logger.error(
                f"fireCoach: failed to clear Team.coach_id for {team.name}: {e}"
            )

    def handleCoachRetirement(self, season: int) -> None:
        """Increment seasonsCoached, then resolve GM turnover for every team.

        Three sim-decided exits (plan Part C): RETIRE (the tenure curve, and it
        takes precedence), FIRED (poor record, softened by tenure grace and
        locker-room goodwill), and LEFT (voluntary). Each rolls the same
        replacement gamble. Fan sentiment feeds fire/leave once Part D lands;
        until then those terms are neutral.

        On retirement, the old Coach DB row is deleted before the new
        coach is generated and saved. Without this, the retired coach's
        row keeps team_id = team.id, _saveCoachToDatabase inserts a
        second row with the same team_id, and _loadCoachFromDatabase's
        .first() query can resurrect the retired coach on the next boot.
        """
        from managers.gmTurnover import GmTurnover, EXIT_FIRED
        turnover = GmTurnover()
        exits = {'retired': 0, 'fired': 0, 'left': 0}

        # GM heat comes from fans' like/dislike of the GM — one considered
        # stance per fan, rather than the rate-limited post spam an earlier
        # version read. Negative = hostile fanbase. Loaded once for the league.
        gmHeat = {}
        try:
            if self.db_session is not None:
                from database.repositories.sentiment_repository import CoachSentimentRepository
                gmHeat = CoachSentimentRepository(self.db_session).getStandingMap()
        except Exception as e:
            self.logger.warning(f"GM turnover: fan standing unavailable, running neutral: {e}")
        if gmHeat:
            self.logger.info(f"GM turnover: fan heat on {len(gmHeat)} team(s)")

        for team in self.teams:
            if team.coach:
                team.coach.seasonsCoached += 1
                # Tenure AT THIS CLUB — what the fire pressure is judged on.
                team.coach.seasonsWithTeam = getattr(team.coach, 'seasonsWithTeam', 0) + 1

            # Retirement takes precedence — a GM going out on their own terms
            # isn't also fired. Then roll the sim-decided exits (plan Part C).
            exitKind = None
            if team.coach and team.coach.shouldRetire():
                exitKind = 'retired'
            elif team.coach:
                rolled = turnover.evaluateExit(
                    team, team.coach,
                    sentiment=gmHeat.get(getattr(team.coach, 'id', None), 0.0),
                    history=self._gmTenureHistory(team))
                if rolled:
                    exitKind = 'fired' if rolled == EXIT_FIRED else 'left'
                    self.logger.info(turnover.describeExit(rolled, team.coach, team))

            if exitKind:
                exits[exitKind] += 1
                retiringName = team.coach.name
                retiringSeasons = team.coach.seasonsCoached
                retiringId = getattr(team.coach, 'id', None)
                if exitKind == 'retired':
                    self.logger.info(
                        f"{retiringName} retires after {retiringSeasons} seasons with {team.name}"
                    )
                    # A retiree is DONE — drop the row so it can't be re-linked
                    # and can't pollute the unassigned coach pool.
                    if (DATABASE_AVAILABLE and USE_DATABASE and self.db_session
                            and retiringId is not None):
                        try:
                            from database.models import Coach as DBCoach
                            dbCoach = self.db_session.get(DBCoach, retiringId)
                            if dbCoach is not None:
                                self.db_session.delete(dbCoach)
                                self.db_session.flush()
                        except Exception as e:
                            self.logger.warning(
                                f"handleCoachRetirement: failed to delete retired "
                                f"coach {retiringName} (id={retiringId}): {e}"
                            )
                else:
                    # ⚠️ BANK THE SEASON THEY JUST COACHED BEFORE THEY LEAVE.
                    # `seasonsCoached += 1` at the top of this loop is in memory
                    # only, and the save below writes the INCOMING coach — so a
                    # departing GM's final season was never persisted and they
                    # entered the market showing stale tenure. That is precisely
                    # the field the carousel is meant to surface, so without this
                    # a GM fired after three seasons is hired elsewhere reading
                    # as a first-timer.
                    self._persistCoachTenure(retiringId, retiringSeasons)
                # ⚠️ A FIRED OR DEPARTED GM IS **KEPT** (owner, 2026-08-13).
                # Their row survives and becomes unassigned the moment
                # _saveCoachToDatabase repoints Team.coach_id, so another club
                # can hire them — the carousel the plan calls "a real trade, not
                # a reroll". Deleting them cost two things: a GM simply ceased
                # to exist mid-career (no rival rebuild, no story), and their
                # NAME went with them — `_recyclePlayerName` only ever runs on
                # players, so every turnover permanently burned a name out of
                # the shared pool. Measured before this: 662 -> 594 pooled names
                # across 8 seasons with the live population flat.
                team.coach = self._hireReplacementCoach(team, excludeCoachId=retiringId)
                self._saveCoachToDatabase(team)
                # ⚠️ VERIFY THE HIRE LANDED. Hiring off the pool re-points an
                # EXISTING coach row rather than inserting a fresh one, so a
                # stale or contended row can leave the club with `coach_id` NULL
                # while the in-memory object looks fine — `_saveCoachToDatabase`
                # swallows its own failure and rolls back. Caught in a 6-season
                # sim as one club (of 32) finishing with no coach at all, which
                # the baseline never produced. Generating is always available as
                # a fallback, so a vacancy is never the outcome.
                if not self._coachIsLinked(team):
                    self.logger.warning(
                        f"{team.name}: pool hire did not stick — generating instead")
                    team.coach = self.generateCoach()
                    self._saveCoachToDatabase(team)
                # ⚠️ A NEW HIRE STARTS AT ZERO TENURE HERE, whatever their career count
                # says. Pool hires bring `seasonsCoached` from a previous club, and tenure
                # pressure is judged on time at THIS club — without this reset an incoming
                # GM would inherit the drought that got the last one fired.
                if team.coach is not None:
                    team.coach.seasonsWithTeam = 0
                    self._saveCoachToDatabase(team)
                self.logger.info(f"{team.name} hires new coach {team.coach.name}")
                self._recordCoachChange(team, exitKind, retiringName, retiringSeasons)

        total = sum(exits.values())
        if total:
            self.logger.info(
                f"GM turnover: {total} change(s) — {exits['retired']} retired, "
                f"{exits['fired']} fired, {exits['left']} stepped down")

    def _persistCoachTenure(self, coachId, seasons: int) -> None:
        """Write a departing GM's season count to their row.

        Surviving coaches get theirs persisted by the sweep in seasonManager
        after this method returns; a coach who has just been replaced is not in
        that sweep, so this is their only chance to record the season they
        actually coached.
        """
        if coachId is None:
            return
        if not (DATABASE_AVAILABLE and USE_DATABASE and self.db_session):
            return
        try:
            from database.models import Coach as DBCoach
            dbCoach = self.db_session.get(DBCoach, coachId)
            if dbCoach is not None:
                dbCoach.seasons_coached = int(seasons or 0)
                self.db_session.flush()
        except Exception as e:
            self.logger.warning(
                f"_persistCoachTenure: could not bank tenure for coach {coachId}: {e}")

    def _recordCoachChange(self, team, exitKind: str, retiringName: str,
                           retiringSeasons: int) -> None:
        """Put a GM change into the Season Recap.

        ⚠️ NOTHING RECORDED THESE UNTIL 2026-08-13, and the whole reading half
        was already built: `SeasonRecapEvent` documents `coach_fire | coach_hire`
        as valid types, the frontend declares them, and `SeasonRecap.tsx` renders
        a COACHING CHANGES block that colors them and prints "Fired"/"Hired".
        `_recordOffseasonEvent` was simply never called with either, so the
        section rendered NOTHING from the day it shipped — `announce()` returns
        null on an empty list, so it looked absent rather than broken. The only
        trace a GM change left anywhere was a server log line no user can read.
        (Fourth instance of this pattern in the codebase; the dead fantasy roster
        tables account for three.)

        It matters more now that a fired GM lands in the pool and can resurface
        at a rival with their tenure intact — that is a story the sim generates
        and used to throw away.

        Only a genuine FIRING records `coach_fire`; the frontend prints that type
        as the literal word "Fired", so routing a retirement or a resignation
        through it would state something untrue. Those carry their reason in the
        hire line instead, which is why every exit records a hire and only one
        kind records a departure.
        """
        seasonManager = None
        try:
            seasonManager = self.serviceContainer.getService('season_manager')
        except Exception:
            pass
        if seasonManager is None or not hasattr(seasonManager, '_recordOffseasonEvent'):
            return

        def _plural(n, word):
            return f"{n} {word}{'s' if n != 1 else ''}"

        try:
            if exitKind == 'fired':
                seasonManager._recordOffseasonEvent(
                    'coach_fire', team=team,
                    detail=f"{retiringName} after {_plural(retiringSeasons, 'season')}")

            arrived = getattr(team.coach, 'name', 'a new GM')
            prior = int(getattr(team.coach, 'seasonsCoached', 0) or 0)
            # Prior tenure is the interesting part of a market hire: it is how a
            # reader spots the GM they watched get fired turning up somewhere else.
            if prior > 0:
                arrived = f"{arrived} ({_plural(prior, 'prior season')})"
            if exitKind == 'retired':
                detail = f"{arrived}, replacing {retiringName} (retired)"
            elif exitKind == 'left':
                detail = f"{arrived}, replacing {retiringName} (stepped down)"
            else:
                detail = arrived
            seasonManager._recordOffseasonEvent('coach_hire', team=team, detail=detail)
        except Exception as e:
            # A recap line is never worth failing an offseason over.
            self.logger.warning(f"_recordCoachChange failed for {team.name}: {e}")

    def _coachIsLinked(self, team) -> bool:
        """Is this club's coach actually persisted AND pointed at by the club?

        `Team.coach_id` is the single source of truth, so an in-memory
        `team.coach` proves nothing on its own.
        """
        if getattr(team, 'coach', None) is None:
            return False
        if not (DATABASE_AVAILABLE and USE_DATABASE and self.db_session):
            return True                     # no DB to disagree with
        try:
            from database.models import Team as DBTeam
            dbTeam = self.db_session.get(DBTeam, team.id)
            return bool(dbTeam is not None and dbTeam.coach_id
                        and dbTeam.coach_id == getattr(team.coach, 'id', None))
        except Exception:
            return False

    def _gmTenureHistory(self, team):
        """Newest-first season records for the CURRENT GM's time at this club.

        Feeds `GmTurnover.tenurePressure`, which asks how long it has been since this GM
        got anywhere — so the window is their tenure AT THIS CLUB (`seasonsWithTeam`), not
        the career counter a pool hire carries in from a previous job.

        Each entry: {'winPct', 'madePlayoffs', 'wonPlayoffRound'}. A missing or unreadable
        history returns [] and the pressure term is simply 0 — never gate a GM's job on a
        query that failed.
        """
        coach = getattr(team, 'coach', None)
        tenure = int(getattr(coach, 'seasonsWithTeam', 0) or 0) if coach else 0
        if tenure <= 0 or self.db_session is None:
            return []
        try:
            from database.models import TeamSeasonStats
            rows = (self.db_session.query(TeamSeasonStats)
                    .filter(TeamSeasonStats.team_id == team.id)
                    .order_by(TeamSeasonStats.season.desc())
                    .limit(tenure).all())
            if not rows:
                return []
            # Deepest playoff round reached, per season. Winning a round is what resets the
            # stall clock, and `made_playoffs` alone cannot say whether they won one.
            advanced = set()
            try:
                from playoff_history import buildPlayoffHistory
                for entry in buildPlayoffHistory(self.db_session, team.id):
                    if int(entry.get('deepestRound') or 0) >= 2:
                        advanced.add(int(entry['season']))
            except Exception as e:
                self.logger.debug(f"GM tenure: playoff history unavailable for {team.name}: {e}")
            out = []
            for r in rows:
                played = float((r.wins or 0) + (r.losses or 0))
                out.append({
                    'winPct': (float(r.wins or 0) / played) if played > 0 else 0.5,
                    'madePlayoffs': bool(r.made_playoffs),
                    'wonPlayoffRound': int(r.season) in advanced,
                })
            return out
        except Exception as e:
            self.logger.warning(f"GM tenure history unavailable for {team.name}: {e}")
            return []

    def _hireReplacementCoach(self, team, excludeCoachId=None):
        """Fill a vacancy from the unassigned GM pool, or generate if it's empty.

        THE POOL COMES FIRST, and that is the point: fired and departed GMs land
        there, so a club that sacks its GM in one offseason can watch them turn
        up at a rival in the next. Generating a fresh coach every time made
        turnover a reroll — a name appeared, a name vanished, and nothing carried
        between clubs.

        It also stops the name leak. A generated coach draws from the SAME
        `unused_names` pool players use and nothing ever recycles a coach's name,
        so every turnover used to burn one permanently. Hiring from the pool
        draws nothing.

        ⚠️ The pick is RANDOM among those available, deliberately. Ranking the
        market would mean ranking `Coach.overallRating`, which the class itself
        documents as carrying almost no signal — since Part B made coaches
        SPECIALISTS, the central limit drags that average to the middle for
        everyone, and it excludes `scouting` and `attitude`, the two most
        GM-critical traits. There is no scalar worth sorting on, which is the
        same reason the plan calls a replacement "better-or-worse per dimension,
        not simply up or down". A random draw from the market IS that gamble.

        ⚠️ `excludeCoachId` is the GM who just left THIS club. They are on the
        market — for everyone else. A club immediately re-hiring the person it
        just fired would read as a bug whatever their attributes say.
        """
        # ⚠️ IN USE IN MEMORY COUNTS AS TAKEN. `getAvailableCoaches` asks only
        # whether a row is referenced by `Team.coach_id`, so a club holding a
        # coach whose link was never persisted (coach_id NULL) leaves that row
        # looking free — and another club hires the GM it is already using.
        # Caught in a production-shaped rehearsal: two clubs sat on NULL
        # coach_id while their GMs were handed to Broads and Monuments, putting
        # the same two names on four clubs. The stale link is a pre-existing
        # fault; generating a fresh coach every time used to hide it, because
        # pool rows were never hired at all.
        inUse = {getattr(getattr(t, 'coach', None), 'id', None) for t in self.teams}
        inUse.discard(None)
        candidates = []
        try:
            candidates = [c for c in self.getAvailableCoaches()
                          if c.id not in inUse
                          and (excludeCoachId is None or c.id != excludeCoachId)]
        except Exception as e:
            self.logger.warning(f"_hireReplacementCoach: pool unavailable: {e}")
        if not candidates:
            return self.generateCoach()

        pick = _random.choice(candidates)
        coach = FloosCoach.Coach()
        coach.id = pick.id
        coach.name = pick.name
        coach.seasonsCoached = getattr(pick, 'seasons_coached', 0) or 0
        coach.offensiveMind = pick.offensive_mind
        coach.defensiveMind = pick.defensive_mind
        coach.adaptability = pick.adaptability
        coach.aggressiveness = pick.aggressiveness
        coach.clockManagement = pick.clock_management
        coach.playerDevelopment = pick.player_development
        coach.scouting = getattr(pick, 'scouting', 80) or 80
        coach.attitude = getattr(pick, 'attitude', 80) or 80
        coach.fanTrust = getattr(pick, 'fan_trust', 80) or 80
        self.logger.info(
            f"{team.name} hires {coach.name} off the GM market "
            f"({coach.seasonsCoached} prior season(s))")
        return coach

    def generateCoachPool(self, count: int = 12) -> None:
        """Top up the unassigned coach pool to `count` entries.

        Preserves existing pool entries — earlier versions of this method
        wiped and regenerated the pool on every boot, which invalidated any
        outstanding GM hire_coach votes (target_player_id pointed at a
        Coach DB row that no longer existed). With existing rows preserved,
        an in-flight vote keeps its target through restarts and offseason
        transitions, and only NEW coaches are added when the pool runs low.
        """
        if not (DATABASE_AVAILABLE and USE_DATABASE and self.db_session):
            return
        from database.models import Coach as DBCoach, Team as DBTeam
        try:
            # Count unassigned coaches: those not referenced by any Team.coach_id.
            assignedIds = (self.db_session.query(DBTeam.coach_id)
                           .filter(DBTeam.coach_id != None)
                           .subquery())
            existing = (self.db_session.query(DBCoach)
                        .filter(~DBCoach.id.in_(assignedIds))
                        .count())
            needed = max(0, count - existing)
            if needed == 0:
                return
            for _ in range(needed):
                coach = self.generateCoach()
                dbCoach = DBCoach(
                    name=coach.name,
                    seasons_coached=0,
                    offensive_mind=coach.offensiveMind,
                    defensive_mind=coach.defensiveMind,
                    adaptability=coach.adaptability,
                    aggressiveness=coach.aggressiveness,
                    clock_management=coach.clockManagement,
                    player_development=coach.playerDevelopment,
                    scouting=getattr(coach, 'scouting', 80),
                    attitude=getattr(coach, 'attitude', 80),
                    fan_trust=getattr(coach, 'fanTrust', 80),
                    overall_rating=coach.overallRating,
                )
                self.db_session.add(dbCoach)
            self.db_session.flush()
            self.logger.info(
                f"Topped up coach pool: added {needed} (existing {existing}, target {count})"
            )
        except Exception as e:
            self.logger.error(f"Failed to top up coach pool: {e}")
            self.db_session.rollback()

    def getAvailableCoaches(self):
        """Return list of unassigned coaches (no Team.coach_id pointing at them)."""
        if not (DATABASE_AVAILABLE and USE_DATABASE and self.db_session):
            return []
        from database.models import Coach as DBCoach, Team as DBTeam
        assignedIds = (self.db_session.query(DBTeam.coach_id)
                       .filter(DBTeam.coach_id != None)
                       .subquery())
        return (self.db_session.query(DBCoach)
                .filter(~DBCoach.id.in_(assignedIds))
                .all())

    # ── Per-team Coach Candidates (new hire flow) ────────────────────────────

    # Quality seeds for the 3 generated candidates per vacancy. Each seed
    # centers a normal(σ=10) distribution clamped to [60, 100] in
    # Coach.generateAttributes — so a seed of 90 produces a coach with
    # overall_rating ≈ 87-92, 80 ≈ 77-82, 72 ≈ 68-74. Premium guarantees
    # the user always has at least one attractive option.
    COACH_CANDIDATE_SEEDS = (90, 80, 72)

    def generateCoachCandidates(self, team, season: int, session=None) -> list:
        """Generate 3 candidate coaches for a team's hire vote.

        Each is persisted as an unassigned Coach DB row (team_id=NULL) plus
        a CoachCandidate join row tying them to this team's hire cycle.
        Returns the list of CoachCandidate rows.

        Idempotent — if candidates already exist for (team, season), they
        are returned as-is. Use clearCoachCandidates to force a regen.
        """
        from database.models import Coach as DBCoach, CoachCandidate
        targetSession = session if session is not None else self.db_session
        if targetSession is None:
            return []

        existing = (
            targetSession.query(CoachCandidate)
            .filter(CoachCandidate.team_id == team.id, CoachCandidate.season == season)
            .order_by(CoachCandidate.slot.asc())
            .all()
        )
        if existing:
            return existing

        # Generate the 3 coaches with quality seeds. Shuffle slot order so
        # the premium isn't always slot 0 in the UI.
        seeds = list(self.COACH_CANDIDATE_SEEDS)
        _random.shuffle(seeds)

        candidates = []
        for slot, seed in enumerate(seeds):
            # deferSave=True: skip the per-call saveUnusedNames DB write so
            # the outer batch transaction isn't fighting another session
            # for SQLite's write lock 3 times per team × 32 teams. Names
            # mutate self.unusedNames in memory; we flush once after the
            # loop via the playerMgr.saveUnusedNames() call below.
            coach = self.generateCoach(seed=seed, deferSave=True)
            # Persist as unassigned Coach row
            dbCoach = DBCoach(
                name=coach.name,
                seasons_coached=0,
                offensive_mind=coach.offensiveMind,
                defensive_mind=coach.defensiveMind,
                adaptability=coach.adaptability,
                aggressiveness=coach.aggressiveness,
                clock_management=coach.clockManagement,
                player_development=coach.playerDevelopment,
                scouting=getattr(coach, 'scouting', 80),
                attitude=getattr(coach, 'attitude', 80),
                fan_trust=getattr(coach, 'fanTrust', 80),
                overall_rating=coach.overallRating,
            )
            targetSession.add(dbCoach)
            targetSession.flush()
            cand = CoachCandidate(
                team_id=team.id, coach_id=dbCoach.id,
                season=season, slot=slot,
            )
            targetSession.add(cand)
            candidates.append(cand)

        targetSession.flush()
        self.logger.info(
            f"Generated {len(candidates)} coach candidates for {team.name} "
            f"(ratings: {[c.coach.overall_rating for c in candidates]})"
        )
        return candidates

    def getCoachCandidates(self, team, season: int, session=None) -> list:
        """Read the team's candidate slate for the season (lazy gen if missing)."""
        from database.models import CoachCandidate
        targetSession = session if session is not None else self.db_session
        if targetSession is None:
            return []
        rows = (
            targetSession.query(CoachCandidate)
            .filter(CoachCandidate.team_id == team.id, CoachCandidate.season == season)
            .order_by(CoachCandidate.slot.asc())
            .all()
        )
        if not rows:
            rows = self.generateCoachCandidates(team, season, session=targetSession)
        return rows

    def clearCoachCandidates(self, teamId: int, season: int,
                              keepCoachId: int = None, session=None,
                              deferNameSave: bool = False) -> int:
        """Remove this team's candidate slate after a hire resolves. Coaches
        not chosen are deleted entirely and their names returned to the
        unused-name pool (per design — coach names are scarce).

        keepCoachId: the winning candidate's coach_id; that coach row is
        preserved (it's now the team's hired coach). Pass None to wipe
        all candidates (e.g. when retracting a vacancy).

        deferNameSave=True appends the released names to the in-memory
        pool but skips the database write. Used by batch callers (GM
        hire resolution) so the per-team saves don't compete with the
        outer transaction for SQLite's write lock. Caller must invoke
        playerMgr.saveUnusedNames() once after the outer commit.
        """
        from database.models import Coach as DBCoach, CoachCandidate
        targetSession = session if session is not None else self.db_session
        if targetSession is None:
            return 0

        candidates = (
            targetSession.query(CoachCandidate)
            .filter(CoachCandidate.team_id == teamId, CoachCandidate.season == season)
            .all()
        )
        if not candidates:
            return 0

        releasedNames = []
        for cand in candidates:
            if keepCoachId is not None and cand.coach_id == keepCoachId:
                # Winner — leave Coach row alone, just drop the candidate link.
                targetSession.delete(cand)
                continue
            coach = targetSession.get(DBCoach, cand.coach_id)
            if coach is not None:
                releasedNames.append(coach.name)
                targetSession.delete(coach)
            targetSession.delete(cand)
        targetSession.flush()

        # Return names to the unused-name pool so they cycle back into use.
        if releasedNames:
            try:
                playerMgr = self.serviceContainer.getService('player_manager')
                if playerMgr is not None and hasattr(playerMgr, 'unusedNames'):
                    for nm in releasedNames:
                        if nm and nm not in playerMgr.unusedNames:
                            playerMgr.unusedNames.append(nm)
                    if not deferNameSave and hasattr(playerMgr, 'saveUnusedNames'):
                        playerMgr.saveUnusedNames()
            except Exception as e:
                self.logger.warning(
                    f"clearCoachCandidates: failed to return names {releasedNames!r}: {e}"
                )
        return len(candidates)

    def hireCoachFromPool(self, team: FloosTeam.Team, coachId: int, session=None) -> bool:
        """Hire a coach from the pool by DB id. Returns True on success.

        Optional `session` lets the GM resolution flow share its own session
        so the team_id update and the gm_vote_results insert run on the same
        connection, avoiding SQLite write-lock contention.
        """
        targetSession = session if session is not None else self.db_session
        if not (DATABASE_AVAILABLE and USE_DATABASE and targetSession is not None):
            return False
        from database.models import Coach as DBCoach
        from database.models import Team as DBTeam
        dbCoach = targetSession.get(DBCoach, coachId)
        if not dbCoach:
            return False
        # Check unassigned via Team.coach_id (single source of truth).
        # A coach is "available" if no team has them as coach_id.
        teamUsing = (targetSession.query(DBTeam)
                     .filter(DBTeam.coach_id == coachId, DBTeam.id != team.id)
                     .first())
        if teamUsing is not None:
            return False
        # Build in-memory coach and assign
        coach = FloosCoach.Coach()
        coach.id = dbCoach.id
        coach.name = dbCoach.name
        coach.offensiveMind = dbCoach.offensive_mind
        coach.defensiveMind = dbCoach.defensive_mind
        coach.adaptability = dbCoach.adaptability
        coach.aggressiveness = dbCoach.aggressiveness
        coach.clockManagement = dbCoach.clock_management
        coach.playerDevelopment = dbCoach.player_development
        coach.scouting = getattr(dbCoach, 'scouting', 80) or 80
        coach.attitude = getattr(dbCoach, 'attitude', 80) or 80
        coach.fanTrust = getattr(dbCoach, 'fan_trust', 80) or 80
        team.coach = coach
        # Single write — point the team at the new coach.
        dbTeam = targetSession.get(DBTeam, team.id)
        if dbTeam:
            dbTeam.coach_id = dbCoach.id
        targetSession.flush()
        self.logger.info(f"{team.name} hired coach {coach.name} from pool")
        return True


# ── Pressure diagnostic logging (module-level helpers) ──────────────────────

_pressureDiagLogger = None


def _getPressureDiagLogger():
    """Lazy-init a dedicated logger that writes only to logs/pressure_diag.log.
    Keeps PRESSURE_DIAG lines out of the main app log so testing this feature
    doesn't drown out other diagnostic output.
    """
    global _pressureDiagLogger
    if _pressureDiagLogger is not None:
        return _pressureDiagLogger
    import logging
    import os
    diagLogger = logging.getLogger("floosball.pressure_diag")
    diagLogger.setLevel(logging.INFO)
    diagLogger.propagate = False
    if not diagLogger.handlers:
        os.makedirs("logs", exist_ok=True)
        handler = logging.FileHandler("logs/pressure_diag.log")
        handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
        diagLogger.addHandler(handler)
    _pressureDiagLogger = diagLogger
    return diagLogger


def formatPressureDiagLine(team, context: str, season: int = None, week: int = None) -> str:
    """Build a single PRESSURE_DIAG log line for one team. Mirrors the
    game-time scaling in floosball_game.calculateGamePressure exactly so
    the log values match what the simulation actually applies.
    """
    from constants import (
        EXPECTATION_SCALE_BY_TIER,
        EXPECTATION_RELIEF_BY_TIER,
        EXPECTATION_DELTA_CAP,
        CHAMPIONSHIP_OVERFLOW_FACTOR,
    )
    base = getattr(team, 'pressureModifier', 1.0)
    streakAdd = getattr(team, 'streakPressure', 0.0)
    streak = getattr(team, 'currentWinStreak', 0)
    effective = base + streakAdd
    tier = getattr(team, 'fundingTier', 'UNKNOWN')
    delta = effective - 1.0
    if delta > 0:
        tierScale = EXPECTATION_SCALE_BY_TIER.get(tier, 1.0)
        cap = min(delta, EXPECTATION_DELTA_CAP)
        overflow = max(0.0, delta - EXPECTATION_DELTA_CAP)
        scaledDelta = cap * tierScale + overflow * CHAMPIONSHIP_OVERFLOW_FACTOR
    else:
        reliefScale = EXPECTATION_RELIEF_BY_TIER.get(tier, 1.0)
        scaledDelta = delta * reliefScale
    scaled = 1.0 + scaledDelta
    return (
        f"PRESSURE_DIAG s={season if season is not None else '-'} "
        f"w={week if week is not None else '-'} ctx={context} "
        f"team={team.name} tier={tier} base={base:.2f} streak={streak} "
        f"streakP={streakAdd:.2f} scaled={scaled:.2f}"
    )


def logPressureDiag(team, context: str, season: int = None, week: int = None) -> None:
    """Log one team's pressure state at a mutation site. Used by
    seasonManager / leagueManager at the inline pressureModifier assignments.
    """
    _getPressureDiagLogger().info(formatPressureDiagLine(team, context, season=season, week=week))