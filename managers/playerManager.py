"""
PlayerManager - Manages player lifecycle, lists, and organization
Replaces the scattered player-related global variables and functions in floosball.py
"""

from typing import List, Optional, Dict, Any, Tuple
import floosball_player as FloosPlayer
import floosball_team as FloosTeam
from logger_config import get_logger

# Database imports
try:
    from database import get_session, clear_database
    from database.config import USE_DATABASE
    from database.repositories import PlayerRepository, UnusedNameRepository
    from database.models import Player as DBPlayer, PlayerAttributes as DBPlayerAttributes
    DATABASE_AVAILABLE = True
except ImportError:
    DATABASE_AVAILABLE = False
    USE_DATABASE = False

logger = get_logger("floosball.playerManager")

class PlayerManager:
    """Manages player lifecycle, lists, and organization"""
    
    def __init__(self, serviceContainer):
        self.serviceContainer = serviceContainer
        
        # Database session and repositories (if database enabled)
        self.db_session = None
        self.player_repo = None
        self.name_repo = None
        
        if DATABASE_AVAILABLE and USE_DATABASE:
            self.db_session = get_session()
            self.player_repo = PlayerRepository(self.db_session)
            self.name_repo = UnusedNameRepository(self.db_session)
            logger.info("PlayerManager using DATABASE storage")
        else:
            logger.info("PlayerManager using JSON file storage")
        
        # Main player lists (replaces global variables)
        self.activePlayers: List[FloosPlayer.Player] = []
        self.freeAgents: List[FloosPlayer.Player] = []
        self.retiredPlayers: List[FloosPlayer.Player] = []
        self.newlyRetiredPlayers: List[FloosPlayer.Player] = []
        self.hallOfFame: List[FloosPlayer.Player] = []
        self.rookieDraftList: List[FloosPlayer.Player] = []
        self.unusedNames: List[str] = []
        # Recycled retiree names held out of the usable pool until their season.
        # In-memory list of (name, availableSeason); persisted alongside unusedNames.
        self.pendingNames: List[tuple] = []
        
        # Position-specific lists (replaces activeQbList, etc.)
        self.activeQbs: List[FloosPlayer.Player] = []
        self.activeRbs: List[FloosPlayer.Player] = []
        self.activeWrs: List[FloosPlayer.Player] = []
        self.activeTes: List[FloosPlayer.Player] = []
        self.activeKs: List[FloosPlayer.Player] = []
        
        logger.info("PlayerManager initialized")
    
    def __del__(self):
        """Cleanup database session when manager is destroyed"""
        if self.db_session:
            try:
                self.db_session.close()
            except Exception:
                pass
    
    def generatePlayers(self, config: Dict[str, Any], force_fresh: bool = False) -> None:
        """Generate or load initial player pool (replaces getPlayers function)"""
        logger.info("Generating initial player pool")
        
        # First try to load existing players (unless force fresh is requested)
        if not force_fresh and self._loadExistingPlayers():
            logger.info(f"Loaded {len(self.activePlayers)} existing players from data files")
            # Still need to load unused names for replacement player generation
            self.loadNameLists(config)
            return
        
        # If no existing players found, generate new ones
        logger.info("No existing players found, generating new player pool")
        leagueConfig = config.get('leagueConfig', {})
        totalPlayers = leagueConfig.get('initialPlayerCount', 144)
        
        # Load name lists from main config
        self.loadNameLists(config)
        
        # Generate players by position
        self.generatePlayersByPosition(totalPlayers)
        
        # Save remaining unused names
        self.saveUnusedNames()
        
        logger.info(f"Generated {len(self.activePlayers)} total players")
    
    def _loadExistingPlayers(self) -> bool:
        """
        Load existing players from data files or database
        Returns True if players were loaded, False if no existing players found
        """
        # Try database first if enabled
        if DATABASE_AVAILABLE and USE_DATABASE and self.player_repo:
            logger.debug("Attempting to load players from database")
            return self._loadPlayersFromDatabase()
        
        # Fall back to JSON files
        logger.debug("Attempting to load players from JSON files")
        return self._loadPlayersFromJSON()
    
    def _loadPlayersFromJSON(self) -> bool:
        """
        Load existing players from JSON data files
        Returns True if players were loaded, False if no existing players found
        """
        import os
        import glob
        import json
        
        player_data_path = "data/playerData"
        
        # Check if player data directory exists and has files
        if not os.path.exists(player_data_path):
            logger.debug("Player data directory does not exist")
            return False
        
        player_files = glob.glob(os.path.join(player_data_path, "player*.json"))
        if not player_files:
            logger.debug("No player data files found")
            return False
        
        logger.info(f"Found {len(player_files)} existing player files, loading...")
        
        # Load players from JSON files
        loaded_players = []
        for file_path in sorted(player_files):
            try:
                with open(file_path, 'r') as f:
                    player_data = json.load(f)
                
                # Create player object from data
                player = self._createPlayerFromData(player_data)
                if player:
                    loaded_players.append(player)
                    
            except Exception as e:
                logger.warning(f"Failed to load player from {file_path}: {e}")
                continue
        
        if not loaded_players:
            logger.warning("No valid players could be loaded from data files")
            return False
        
        # Set loaded players as active players
        self.activePlayers = loaded_players
        
        # Rebuild position lists from loaded players
        self.rebuildPositionLists()
        
        # Organize players by position and assign tiers
        self.sortPlayersByPosition()
        
        logger.info(f"Successfully loaded {len(loaded_players)} players from data files")
        return True
    
    def _createPlayerFromData(self, player_data: Dict[str, Any]) -> FloosPlayer.Player:
        """Create a Player object from saved JSON data using position-specific classes"""
        import floosball_player as FloosPlayer
        
        try:
            # Get position value to determine which class to instantiate
            position_value = player_data.get('position', 1)
            player_rating = player_data.get('playerRating', 74)
            player_name = player_data['name']
            
            # Create position-specific player instance with rating as seed
            player = None
            if position_value == 1:  # QB
                player = FloosPlayer.PlayerQB(player_rating)
            elif position_value == 2:  # RB
                player = FloosPlayer.PlayerRB(player_rating)
            elif position_value == 3:  # WR
                player = FloosPlayer.PlayerWR(player_rating)
            elif position_value == 4:  # TE
                player = FloosPlayer.PlayerTE(player_rating)
            elif position_value == 5:  # K
                player = FloosPlayer.PlayerK(player_rating)
            else:
                logger.warning(f"Invalid position {position_value} for player {player_name}, defaulting to QB")
                player = FloosPlayer.PlayerQB(player_rating)
            
            # Set name
            player.name = player_name
            
            # Set basic properties
            player.id = player_data.get('id', 1)
            player.currentNumber = player_data.get('currentNumber', 0)
            player.preferredNumber = player_data.get('preferredNumber', 0)
            player.seasonsPlayed = player_data.get('seasonsPlayed', 0)
            player.term = player_data.get('term', 2)
            player.termRemaining = player_data.get('termRemaining', 2)
            player.capHit = player_data.get('capHit', 2)
            player.seasonPerformanceRating = player_data.get('seasonPerformanceRating', 0)
            player.playerRating = player_rating
            player.freeAgentYears = player_data.get('freeAgentYears', 0)
            
            # Set player tier
            tier_name = player_data.get('tier', 'TierC')
            try:
                player.playerTier = getattr(FloosPlayer.PlayerTier, tier_name)
            except AttributeError:
                logger.warning(f"Unknown tier {tier_name} for player {player.name}, defaulting to TierC")
                player.playerTier = FloosPlayer.PlayerTier.TierC
            
            # Set service time
            service_time_name = player_data.get('serviceTime', 'Rookie')
            try:
                player.serviceTime = getattr(FloosPlayer.PlayerServiceTime, service_time_name)
            except AttributeError:
                logger.warning(f"Unknown service time {service_time_name} for player {player.name}, defaulting to Rookie")
                player.serviceTime = FloosPlayer.PlayerServiceTime.Rookie
            
            # Set team (may be string or None)
            team_name = player_data.get('team')
            if team_name and team_name != 'Free Agent' and team_name != 'Retired':
                player.team = team_name  # Will be resolved to team object later
            else:
                player.team = team_name  # Keep as string for Free Agent/Retired
            
            # Load attributes - overwrite the auto-generated attributes with saved values
            if 'attributes' in player_data:
                attr_data = player_data['attributes']
                for attr_name, attr_value in attr_data.items():
                    if hasattr(player.attributes, attr_name):
                        setattr(player.attributes, attr_name, attr_value)
            
            # Load career stats
            if 'careerStats' in player_data:
                player.careerStatsDict = player_data['careerStats']
            
            # Load season stats archive
            if 'seasonStatsArchive' in player_data:
                archive_data = player_data['seasonStatsArchive']
                # Convert from dict with numeric keys back to list
                if isinstance(archive_data, dict):
                    player.seasonStatsArchive = [archive_data[str(i)] for i in sorted([int(k) for k in archive_data.keys()])]
                else:
                    player.seasonStatsArchive = archive_data
            
            # Load awards/accolades
            player.mvpAwards = player_data.get('mvpAwards', [])
            player.allProSeasons = player_data.get('allProSeasons', [])
            player.leagueChampionships = player_data.get('leagueChampionships', [])

            # Set up season stats dict if not present
            if not hasattr(player, 'seasonStatsDict') or player.seasonStatsDict is None:
                player.seasonStatsDict = player.careerStatsDict.copy() if hasattr(player, 'careerStatsDict') else {}

            # Recalculate dual ratings (offensive/defensive) from loaded attributes
            player.updateRating()

            return player
            
        except Exception as e:
            logger.error(f"Failed to create player from data: {e}")
            return None
    
    def _loadPlayersFromDatabase(self) -> bool:
        """
        Load existing players from database if they exist
        Returns True if players were loaded, False if no existing players found
        """
        if not self.player_repo:
            logger.debug("Database not available")
            return False
        
        try:
            # Load all players from database
            db_players = self.player_repo.get_all()
            
            if not db_players:
                logger.debug("No players found in database")
                return False
            
            logger.info(f"Found {len(db_players)} players in database, loading...")
            
            # Convert database players to game Player objects
            loaded_players = []
            for db_player in db_players:
                game_player = self._createPlayerFromDatabase(db_player)
                if game_player:
                    loaded_players.append(game_player)
            
            if not loaded_players:
                logger.warning("No valid players could be loaded from database")
                return False

            # Split by service_time. Retired players belong on retiredPlayers,
            # not activePlayers — without this, the Retired tab is empty after
            # a server restart until a runtime retirement re-populates it.
            # Hall of Fame members are a subset of retired and also belong on
            # the hallOfFame list (which the /api/players?status=hof endpoint
            # reads). Without this routing the HoF tab is empty after restart.
            from floosball_player import PlayerServiceTime as _PST
            self.activePlayers = []
            self.retiredPlayers = []
            self.hallOfFame = []
            for p in loaded_players:
                if getattr(p, 'serviceTime', None) == _PST.Retired:
                    self.retiredPlayers.append(p)
                    if getattr(p, 'is_hof', False):
                        self.hallOfFame.append(p)
                else:
                    self.activePlayers.append(p)

            # Persist any backfilled seasonsPlayed/serviceTime values
            try:
                self.db_session.commit()
            except Exception:
                self.db_session.rollback()

            # Rebuild position lists from loaded players
            self.rebuildPositionLists()

            # Organize players by position and assign tiers
            self.sortPlayersByPosition()

            # Note: Players will be assigned to teams later after teams are loaded

            logger.info(f"Successfully loaded {len(loaded_players)} players from database")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load players from database: {e}")
            return False
    
    def _createPlayerFromDatabase(self, db_player) -> FloosPlayer.Player:
        """Create a game Player object from database Player model"""
        try:
            # Determine position and create appropriate player class
            position_value = db_player.position
            player_rating = db_player.player_rating or 74
            
            # Create position-specific player instance
            if position_value == 1:  # QB
                player = FloosPlayer.PlayerQB(player_rating)
            elif position_value == 2:  # RB
                player = FloosPlayer.PlayerRB(player_rating)
            elif position_value == 3:  # WR
                player = FloosPlayer.PlayerWR(player_rating)
            elif position_value == 4:  # TE
                player = FloosPlayer.PlayerTE(player_rating)
            elif position_value == 5:  # K
                player = FloosPlayer.PlayerK(player_rating)
            else:
                logger.warning(f"Invalid position {position_value}, defaulting to QB")
                player = FloosPlayer.PlayerQB(player_rating)
            
            # Set basic properties from database
            player.name = db_player.name
            player.id = db_player.id
            player.currentNumber = db_player.current_number
            player.preferredNumber = db_player.preferred_number
            player.team = db_player.team_id
            player.seasonsPlayed = db_player.seasons_played
            # Backfill seasonsPlayed if never incremented (pre-fix data)
            if player.seasonsPlayed == 0:
                from database.models import PlayerSeasonStats as DBPlayerSeasonStats
                actualSeasons = self.db_session.query(DBPlayerSeasonStats).filter(
                    DBPlayerSeasonStats.player_id == player.id,
                    DBPlayerSeasonStats.games_played > 0
                ).count()
                if actualSeasons > 0:
                    player.seasonsPlayed = actualSeasons
                    db_player.seasons_played = actualSeasons
                    self._updatePlayerServiceTime(player)
                    db_player.service_time = player.serviceTime.name
                    logger.debug(f"Backfilled {player.name} seasonsPlayed={actualSeasons}, serviceTime={player.serviceTime.name}")
            player.term = db_player.term
            player.termRemaining = db_player.term_remaining
            player.capHit = db_player.cap_hit
            player.teamResignCount = int(getattr(db_player, 'team_resign_count', 0) or 0)
            player.playerRating = db_player.player_rating
            player.freeAgentYears = db_player.free_agent_years
            # Prospect pipeline state
            player.is_prospect = bool(getattr(db_player, 'is_prospect', False))
            player.is_undrafted = bool(getattr(db_player, 'is_undrafted', False))
            player.prospect_seasons = int(getattr(db_player, 'prospect_seasons', 0) or 0)
            player.drafting_team_id = getattr(db_player, 'drafting_team_id', None)
            player.is_upcoming_rookie = bool(getattr(db_player, 'is_upcoming_rookie', False))
            player.willRetire = bool(getattr(db_player, 'will_retire', False))
            player.is_hof = bool(getattr(db_player, 'is_hof', False))
            player.hof_season = getattr(db_player, 'hof_season', None)
            player.mvpAwards = list(getattr(db_player, 'mvp_awards', None) or [])
            player.allProSeasons = list(getattr(db_player, 'all_pro_seasons', None) or [])
            player.leagueChampionships = list(getattr(db_player, 'league_championships', None) or [])
            
            # Load tier if present
            if db_player.tier:
                from floosball_player import PlayerTier
                player.playerTier = PlayerTier[db_player.tier] if hasattr(PlayerTier, db_player.tier) else PlayerTier.TierC
            
            # Load service time if present
            if db_player.service_time:
                from floosball_player import PlayerServiceTime
                player.serviceTime = PlayerServiceTime[db_player.service_time] if hasattr(PlayerServiceTime, db_player.service_time) else PlayerServiceTime.Rookie
            
            # Load attributes from related table
            if db_player.attributes:
                import numpy as np
                attrs = db_player.attributes
                player.attributes.overallRating = attrs.overall_rating
                player.attributes.speed = attrs.speed
                player.attributes.hands = attrs.hands
                if attrs.reach and attrs.reach > 0:
                    player.attributes.reach = attrs.reach
                else:
                    # Backfill reach for pre-existing players using physical seed
                    physicalSeed = (attrs.overall_rating + 60) / 2
                    player.attributes.reach = int(np.clip(np.random.normal(physicalSeed, 8), 60, 100))
                player.attributes.agility = attrs.agility
                player.attributes.power = attrs.power
                player.attributes.armStrength = attrs.arm_strength
                player.attributes.accuracy = attrs.accuracy
                player.attributes.legStrength = attrs.leg_strength
                player.attributes.skillRating = attrs.skill_rating
                player.attributes.potentialSpeed = attrs.potential_speed
                player.attributes.potentialHands = attrs.potential_hands
                if attrs.potential_reach and attrs.potential_reach > 0:
                    player.attributes.potentialReach = attrs.potential_reach
                else:
                    player.attributes.potentialReach = int(np.clip(player.attributes.reach + np.random.randint(-5, 11), 60, 100))
                player.attributes.potentialAgility = attrs.potential_agility
                player.attributes.potentialPower = attrs.potential_power
                player.attributes.potentialArmStrength = attrs.potential_arm_strength
                player.attributes.potentialAccuracy = attrs.potential_accuracy
                player.attributes.potentialLegStrength = attrs.potential_leg_strength
                player.attributes.potentialSkillRating = attrs.potential_skill_rating
                # True skill: fall back to the current attr when unset (0/null) —
                # pre-migration players and any not yet percentile-remapped start
                # with trueSkill == current so the dev arc has a valid target.
                player.attributes.trueSkillSpeed = getattr(attrs, 'true_skill_speed', 0) or player.attributes.speed
                player.attributes.trueSkillHands = getattr(attrs, 'true_skill_hands', 0) or player.attributes.hands
                player.attributes.trueSkillReach = getattr(attrs, 'true_skill_reach', 0) or player.attributes.reach
                player.attributes.trueSkillAgility = getattr(attrs, 'true_skill_agility', 0) or player.attributes.agility
                player.attributes.trueSkillPower = getattr(attrs, 'true_skill_power', 0) or player.attributes.power
                player.attributes.trueSkillArmStrength = getattr(attrs, 'true_skill_arm_strength', 0) or player.attributes.armStrength
                player.attributes.trueSkillAccuracy = getattr(attrs, 'true_skill_accuracy', 0) or player.attributes.accuracy
                player.attributes.trueSkillLegStrength = getattr(attrs, 'true_skill_leg_strength', 0) or player.attributes.legStrength
                player.attributes.routeRunning = attrs.route_running
                player.attributes.vision = attrs.vision
                player.attributes.blocking = attrs.blocking
                player.attributes.discipline = attrs.discipline
                player.attributes.attitude = attrs.attitude
                player.attributes.attitudeBaseline = getattr(attrs, 'attitude_baseline', None) or attrs.attitude
                player.attributes.focus = attrs.focus
                player.attributes.instinct = attrs.instinct
                player.attributes.creativity = attrs.creativity
                player.attributes.resilience = attrs.resilience
                player.attributes.clutchFactor = attrs.clutch_factor
                player.attributes.selfBelief = getattr(attrs, 'self_belief', 80) or 80
                player.attributes.pressureHandling = attrs.pressure_handling
                player.attributes.longevity = attrs.longevity
                player.attributes.playMakingAbility = attrs.play_making_ability
                player.attributes.xFactor = attrs.x_factor
                player.attributes.confidenceModifier = attrs.confidence_modifier
                player.attributes.determinationModifier = attrs.determination_modifier
                player.attributes.luckModifier = attrs.luck_modifier
                player.attributes.defensiveTalent = getattr(attrs, 'defensive_talent', 0) or 0
                player.attributes.fatigue = getattr(attrs, 'fatigue', 0.0) or 0.0
                player.attributes.personality = getattr(attrs, 'personality', None)
                player.attributes.quirk = getattr(attrs, 'quirk', None)
                player.attributes.mood = getattr(attrs, 'mood', 3) or 3
                player.attributes.hometown = getattr(attrs, 'hometown', None)
                player.attributes.favorite_category = getattr(attrs, 'favorite_category', None)
                player.attributes.favorite_item = getattr(attrs, 'favorite_item', None)
                player.attributes.motto = getattr(attrs, 'motto', None)

            # Load career stats from related table
            if db_player.career_stats:
                for stat_record in db_player.career_stats:
                    if stat_record.season == 0:  # Career totals
                        player.careerStatsDict = {
                            'passing': stat_record.passing_stats or {},
                            'rushing': stat_record.rushing_stats or {},
                            'receiving': stat_record.receiving_stats or {},
                            'kicking': stat_record.kicking_stats or {},
                            'defense': stat_record.defense_stats or {},
                            'gamesPlayed': stat_record.games_played,
                            'fantasyPoints': stat_record.fantasy_points,
                        }
                        # Re-point stat_tracker at the restored dict — without
                        # this, in-game stat increments go to the original
                        # empty dict from Player.__init__ and never reach
                        # career totals (only fantasy points slipped through
                        # via separate end-of-season rollup paths).
                        if hasattr(player, 'stat_tracker'):
                            player.stat_tracker.career_stats_dict = player.careerStatsDict

            # Recalculate dual ratings (offensive/defensive) from loaded attributes
            player.updateRating()

            return player
            
        except Exception as e:
            logger.error(f"Failed to create player from database: {e}")
            return None
    
    def assignPlayersToTeams(self) -> None:
        """
        Assign loaded players to their teams' rosters.
        This should be called after both teams and players have been loaded from the database.
        """
        # Get team manager from service container
        teamManager = self.serviceContainer.getService('team_manager')
        if not teamManager:
            logger.warning("Team manager not available, cannot assign players to teams")
            return
        
        teams = teamManager.teams
        if not teams:
            logger.warning("No teams available, cannot assign players")
            return
        
        # Create a lookup dictionary for teams by ID
        team_lookup = {team.id: team for team in teams}
        
        # Assign each player to their team's roster
        assigned_count = 0
        contract_fixes = 0
        for player in self.activePlayers:
            # Fix any players with invalid contract state (defensive initialization)
            if hasattr(player, 'term') and hasattr(player, 'termRemaining'):
                if player.termRemaining is None or player.termRemaining <= 0:
                    # If player has a valid term, use it; otherwise set default
                    if player.term and player.term > 0:
                        player.termRemaining = player.term
                    else:
                        # Set default contract based on tier
                        player.term = self._getPlayerTerm(player)
                        player.termRemaining = player.term
                    contract_fixes += 1
                    logger.info(f"Fixed contract for {player.name}: term={player.term}, termRemaining={player.termRemaining}")
            else:
                # Player missing contract attributes - initialize them
                player.term = self._getPlayerTerm(player)
                player.termRemaining = player.term
                contract_fixes += 1
                logger.info(f"Initialized contract for {player.name}: term={player.term}, termRemaining={player.termRemaining}")
        
        if contract_fixes > 0:
            logger.info(f"Fixed contract state for {contract_fixes} players during team assignment")
        
        # Pass 1 — prospects: route to their drafting team's pipeline, not the roster.
        # Prospects have is_prospect=True + drafting_team_id set (team_id is NULL in DB).
        prospectCount = 0
        for player in self.activePlayers:
            if getattr(player, 'is_prospect', False) and getattr(player, 'drafting_team_id', None):
                team = team_lookup.get(player.drafting_team_id)
                if team is not None:
                    if not hasattr(team, 'prospects'):
                        team.prospects = []
                    if player not in team.prospects:
                        team.prospects.append(player)
                    player.team = 'Prospect'  # canonical runtime marker
                    prospectCount += 1

        if prospectCount > 0:
            logger.info(f"Restored {prospectCount} prospects to team pipelines")

        # Upcoming rookies are visible for scouting but not on any team — skip
        # all rostering/FA logic for them. Their player.team stays 'Upcoming Rookie'.
        upcomingCount = 0
        for player in self.activePlayers:
            if getattr(player, 'is_upcoming_rookie', False):
                player.team = 'Upcoming Rookie'
                upcomingCount += 1
        if upcomingCount > 0:
            logger.info(f"Skipped {upcomingCount} upcoming rookies from roster/FA assignment")

        faCount = 0
        for player in self.activePlayers:
            # Prospects are handled above; don't try to roster them
            if getattr(player, 'is_prospect', False):
                continue
            # Upcoming rookies are pre-draft — not rostered, not in FA pool
            if getattr(player, 'is_upcoming_rookie', False):
                continue
            if not hasattr(player, 'team') or player.team is None:
                # Player has no team — mark as free agent
                player.team = 'Free Agent'
                if player not in self.freeAgents:
                    self.freeAgents.append(player)
                    faCount += 1
                continue

            # player.team may be an integer (freshly loaded from DB) or a Team
            # object (already resolved in a previous assignPlayersToTeams call).
            if isinstance(player.team, int):
                team_id = player.team
            else:
                team_id = getattr(player.team, 'id', None)
            team = team_lookup.get(team_id)

            if not team:
                logger.warning(f"Player {player.name} has team_id {team_id} but team not found")
                continue

            # Determine which roster position to fill based on player's position
            position = player.position.value

            if position == 1:  # QB
                team.rosterDict['qb'] = player
                player.team = team  # Update player's team reference
                assigned_count += 1
            elif position == 2:  # RB
                team.rosterDict['rb'] = player
                player.team = team  # Update player's team reference
                assigned_count += 1
            elif position == 3:  # WR
                if team.rosterDict.get('wr1') is None:
                    team.rosterDict['wr1'] = player
                    player.team = team  # Update player's team reference
                    assigned_count += 1
                elif team.rosterDict.get('wr2') is None:
                    team.rosterDict['wr2'] = player
                    player.team = team  # Update player's team reference
                    assigned_count += 1
                else:
                    logger.warning(f"Team {team.name} already has 2 WRs, cannot assign {player.name}")
            elif position == 4:  # TE
                team.rosterDict['te'] = player
                player.team = team  # Update player's team reference
                assigned_count += 1
            elif position == 5:  # K
                team.rosterDict['k'] = player
                player.team = team  # Update player's team reference
                assigned_count += 1

        logger.info(f"Assigned {assigned_count} players to team rosters, {faCount} free agents identified")
    
    def loadNameLists(self, config: Dict[str, Any]) -> None:
        """Load player name lists from database, initializing from config if needed"""
        if DATABASE_AVAILABLE and USE_DATABASE and self.name_repo:
            # Try to load from database
            if self._loadNamesFromDatabase():
                return
            
            # Database is empty, initialize from config
            logger.info("Initializing unused names database from config")
            if 'players' in config:
                self.unusedNames = config['players'].copy()
                # Save to database for future use
                self.name_repo.add_names_batch(self.unusedNames)
                self.db_session.commit()
                logger.info(f"Initialized database with {len(self.unusedNames)} names from config")
            else:
                logger.error("No player names found in config!")
                self.unusedNames = []
        else:
            # Fallback to JSON file storage (legacy mode)
            self._loadNamesFromJSON(config)
    
    def _loadNamesFromDatabase(self) -> bool:
        """Load unused names from database"""
        try:
            from database.models import UnusedName
            
            # Get all unused names from database
            db_names = self.db_session.query(UnusedName).all()

            # Also load held (pending) retiree names with their release season.
            try:
                from database.models import PendingName
                self.pendingNames = [(p.name, p.available_season)
                                     for p in self.db_session.query(PendingName).all()]
                if self.pendingNames:
                    logger.info(f"Loaded {len(self.pendingNames)} held (pending) names from database")
            except Exception as e:
                logger.error(f"Failed to load pending names: {e}")

            if db_names:
                self.unusedNames = [name.name for name in db_names]
                logger.info(f"Loaded {len(self.unusedNames)} unused names from database")
                return True
            else:
                logger.debug("No unused names found in database")
                return False
                
        except Exception as e:
            logger.error(f"Failed to load names from database: {e}")
            return False
    
    def _loadNamesFromJSON(self, config: Dict[str, Any]) -> None:
        """Load player name lists from unusedNames.json or config (legacy JSON mode only)"""
        import os
        import json
        
        # First try to load from existing unusedNames.json
        if os.path.exists("data/unusedNames.json"):
            try:
                with open("data/unusedNames.json", "r") as jsonFile:
                    unusedNamesDict = json.load(jsonFile)
                    self.unusedNames = list(unusedNamesDict.values())
                    logger.info(f"Loaded {len(self.unusedNames)} unused names from data/unusedNames.json")
                    return
            except Exception as e:
                logger.warning(f"Failed to load unusedNames.json: {e}, falling back to config")
        
        # If unusedNames.json doesn't exist or is empty, load from config
        if not self.unusedNames and 'players' in config:
            self.unusedNames = config['players'].copy()
            logger.info(f"Loaded {len(self.unusedNames)} names from config")
            self.saveUnusedNames()  # Create initial unusedNames.json
        elif not self.unusedNames:
            logger.error("No player names found in config!")
            self.unusedNames = []
    
    def generatePlayersByPosition(self, totalPlayers: int) -> None:
        """Generate players distributed across positions"""
        import numpy as np
        from random import randint

        # Generate dual seeds (physical + mental) from normal distribution.
        # Parity distribution (docs/PARITY_PROSPECT_PLAN.md); founding players
        # are established, so they enter at their true skill (no entry discount).
        from constants import GEN_TRUESKILL_MEAN, GEN_TRUESKILL_STD
        meanPlayerSkill = GEN_TRUESKILL_MEAN
        stdDevPlayerSkill = GEN_TRUESKILL_STD
        physicalSeeds = np.random.normal(meanPlayerSkill, stdDevPlayerSkill, totalPlayers)
        physicalSeeds = np.clip(physicalSeeds, 60, 100).tolist()
        mentalSeeds = np.random.normal(meanPlayerSkill, stdDevPlayerSkill, totalPlayers)
        mentalSeeds = np.clip(mentalSeeds, 60, 100).tolist()

        # Position distribution (matches original pattern: y = x%6)
        playerId = 1
        for x in range(totalPlayers):
            y = x % 6
            position = None
            if y == 0:
                position = FloosPlayer.Position.QB
            elif y == 1:
                position = FloosPlayer.Position.RB
            elif y == 2 or y == 3:  # Two slots for WR
                position = FloosPlayer.Position.WR
            elif y == 4:
                position = FloosPlayer.Position.TE
            elif y == 5:
                position = FloosPlayer.Position.K

            if position and physicalSeeds:
                physSeed = int(physicalSeeds.pop(randint(0, len(physicalSeeds) - 1)))
                mentIdx = randint(0, len(mentalSeeds) - 1)
                mentSeed = int(mentalSeeds.pop(mentIdx))
                player = self.createPlayer(position, physSeed, mentSeed)
                if player:
                    player.id = playerId
                    playerId += 1
                    self.activePlayers.append(player)
                    self.addToPositionList(player)
    
    def isNameInUse(self, name: str) -> bool:
        """True if `name` is already attached to ANY player ever created
        (active, free agent, RETIRED, or Hall-of-Fame) or any Coach row
        (assigned or pool). Used by name-pool readers to skip polluted entries.

        A retired/inducted player's name must NEVER be reused as a bare name —
        generational reuse happens only via the suffix progression in
        seasonManager._recyclePlayerName (Jr./III/IV...), which yields a DISTINCT
        name. So the check spans every player row, not just the live roster.
        """
        # In-memory check — active roster, free agents, AND retirees (the
        # retired list isn't in activePlayers but its names are still taken;
        # this also catches an in-offseason retiree before its DB row is saved).
        for lst in (self.activePlayers, getattr(self, 'freeAgents', []) or [],
                    getattr(self, 'retiredPlayers', []) or []):
            for p in lst:
                if getattr(p, 'name', None) == name:
                    return True
        # Coach check: scan rostered coaches (in-memory on Team objects)
        # AND the unassigned pool (DB) so we catch both cases.
        teamMgr = None
        try:
            teamMgr = self.serviceContainer.getService('team_manager')
        except Exception:
            pass
        if teamMgr:
            for team in getattr(teamMgr, 'teams', []):
                coach = getattr(team, 'coach', None)
                if coach and getattr(coach, 'name', None) == name:
                    return True
        if DATABASE_AVAILABLE and USE_DATABASE and self.db_session is not None:
            try:
                from database.models import Coach as DBCoach, Player as DBPlayer
                if self.db_session.query(DBCoach).filter(DBCoach.name == name).first():
                    return True
                # ANY player row — covers retired & HOF players that aren't in
                # the in-memory active list. This is the guard against reusing a
                # former player's name on a freshly generated backfill/rookie.
                if self.db_session.query(DBPlayer).filter(DBPlayer.name == name).first():
                    return True
            except Exception:
                pass
        return False

    def popUniqueName(self) -> Optional[str]:
        """Pop a name from unusedNames, skipping any already attached to a
        live player or coach. Polluted names are dropped from the pool
        rather than put back — they're not actually 'unused', and leaving
        them in would just defer the same collision to a later draw.
        Returns None when the pool is empty.
        """
        from random import randint
        skipped: List[str] = []
        try:
            while self.unusedNames:
                idx = randint(0, len(self.unusedNames) - 1)
                candidate = self.unusedNames.pop(idx)
                if not self.isNameInUse(candidate):
                    return candidate
                skipped.append(candidate)
            return None
        finally:
            if skipped:
                logger.warning(
                    f"Name pool had {len(skipped)} polluted entr"
                    f"{'y' if len(skipped) == 1 else 'ies'} dropped during draw: "
                    f"{', '.join(repr(n) for n in skipped[:5])}"
                    f"{'...' if len(skipped) > 5 else ''}"
                )

    def createPlayer(self, position: FloosPlayer.Position, physicalSeed: int = None, mentalSeed: int = None) -> Optional[FloosPlayer.Player]:
        """Create a single player of specified position"""
        from random import randint
        import numpy as np
        from constants import GEN_TRUESKILL_MEAN, GEN_TRUESKILL_STD

        name = self.popUniqueName()
        if name is None:
            logger.warning("No usable unused names available")
            return None
        
        # Generate default seeds if not provided. Uses the same Gaussian
        # distribution as the league-balanced rookie class so one-off
        # player creations match the compressed talent curve.
        if physicalSeed is None:
            physicalSeed = int(np.clip(np.random.normal(GEN_TRUESKILL_MEAN, GEN_TRUESKILL_STD), 60, 100))
        if mentalSeed is None:
            mentalSeed = int(np.clip(np.random.normal(GEN_TRUESKILL_MEAN, GEN_TRUESKILL_STD), 60, 100))
        
        # Create player based on position with dual seeds
        player = None
        if position == FloosPlayer.Position.QB:
            player = FloosPlayer.PlayerQB(physicalSeed, mentalSeed)
        elif position == FloosPlayer.Position.RB:
            player = FloosPlayer.PlayerRB(physicalSeed, mentalSeed)
        elif position == FloosPlayer.Position.WR:
            player = FloosPlayer.PlayerWR(physicalSeed, mentalSeed)
        elif position == FloosPlayer.Position.TE:
            player = FloosPlayer.PlayerTE(physicalSeed, mentalSeed)
        elif position == FloosPlayer.Position.K:
            player = FloosPlayer.PlayerK(physicalSeed, mentalSeed)
        
        # Assign the name to the player
        if player:
            player.name = name
            # Assign personality immediately so newly-generated rookies/replacements
            # never enter the pool with NULL personality.
            try:
                personalityManager = self.serviceContainer.getService('personality_manager')
                if personalityManager:
                    personalityManager.assignPersonality(player)
            except Exception as e:
                logger.warning(f"Failed to assign personality to new {position.name}: {e}")

            # Quality-weighted career length: a random base + a bonus that scales
            # with the player's talent seed, so better players (the ones who keep
            # a roster spot) last longer. Overrides the flat random longevity set
            # in PlayerAttributes.__init__. See the LONGEVITY_* constants; the
            # longevity migration script mirrors this formula.
            attrs = getattr(player, 'attributes', None)
            if attrs is not None:
                from constants import (LONGEVITY_BASE_MIN, LONGEVITY_BASE_MAX,
                                       LONGEVITY_QUALITY_PIVOT, LONGEVITY_QUALITY_DIVISOR,
                                       LONGEVITY_QUALITY_MAX_BONUS, LONGEVITY_CEILING)
                quality = (physicalSeed + mentalSeed) / 2.0
                bonus = min(LONGEVITY_QUALITY_MAX_BONUS,
                            max(0.0, (quality - LONGEVITY_QUALITY_PIVOT) / LONGEVITY_QUALITY_DIVISOR))
                attrs.longevity = int(min(LONGEVITY_CEILING,
                    randint(LONGEVITY_BASE_MIN, LONGEVITY_BASE_MAX) + bonus))

        return player

    def addToPositionList(self, player: FloosPlayer.Player) -> None:
        """Add player to appropriate position list"""
        if player.position == FloosPlayer.Position.QB:
            self.activeQbs.append(player)
        elif player.position == FloosPlayer.Position.RB:
            self.activeRbs.append(player)
        elif player.position == FloosPlayer.Position.WR:
            self.activeWrs.append(player)
        elif player.position == FloosPlayer.Position.TE:
            self.activeTes.append(player)
        elif player.position == FloosPlayer.Position.K:
            self.activeKs.append(player)
    
    def removeFromPositionList(self, player: FloosPlayer.Player) -> None:
        """Remove player from position list"""
        if player.position == FloosPlayer.Position.QB:
            self.safeRemove(self.activeQbs, player)
        elif player.position == FloosPlayer.Position.RB:
            self.safeRemove(self.activeRbs, player)
        elif player.position == FloosPlayer.Position.WR:
            self.safeRemove(self.activeWrs, player)
        elif player.position == FloosPlayer.Position.TE:
            self.safeRemove(self.activeTes, player)
        elif player.position == FloosPlayer.Position.K:
            self.safeRemove(self.activeKs, player)
    
    def safeRemove(self, playerList: List[FloosPlayer.Player], player: FloosPlayer.Player) -> None:
        """Safely remove player from list"""
        if player in playerList:
            playerList.remove(player)
    
    def hasReachedResignLimit(self, player) -> bool:
        """True if this team can no longer re-sign the player (re-sign-once limit
        reached). Single source of truth for re-sign eligibility, shared by the
        offseason retention pass, the eligible-targets API, and vote validation.
        An expiring player who hits the limit is forced to walk to free agency."""
        from constants import RESIGN_ONCE_ENABLED, RESIGN_ONCE_LIMIT
        if not RESIGN_ONCE_ENABLED:
            return False
        return (getattr(player, 'teamResignCount', 0) or 0) >= RESIGN_ONCE_LIMIT

    def _getPlayerTerm(self, player) -> int:
        """Decide contract term for a signing / promotion / re-sign.

        Rookies (seasonsPlayed == 0) get a standard prove-it contract keyed to
        tier. Otherwise the term is a tier-random range, capped by how much
        useful career the player likely has left — we never offer a deal that
        runs well past their expected retirement (longevity - seasonsPlayed).
        """
        from random import randint
        tier = player.playerTier
        seasonsPlayed = getattr(player, 'seasonsPlayed', 0) or 0

        # First contract: fixed rookie deal so diamond prospects/rookies don't
        # get six-year commitments before playing a snap.
        if seasonsPlayed == 0:
            if tier in (FloosPlayer.PlayerTier.TierS, FloosPlayer.PlayerTier.TierA):
                return 3
            if tier == FloosPlayer.PlayerTier.TierD:
                return 1
            return 2  # B / C

        # Veteran: roll by tier, then clamp to expected career runway.
        # Star (S/A) deals are SHORT (2-3, was 4-6 / 3-4) so a player cycles through
        # their ~2 contracts (re-sign-once retention limit) in ~4-5 years rather than
        # a decade — keeps talent circulating for parity. See PARITY_PROSPECT_PLAN.md P5.
        if tier == FloosPlayer.PlayerTier.TierS:
            base = randint(2, 3)
        elif tier == FloosPlayer.PlayerTier.TierA:
            base = randint(2, 3)
        elif tier == FloosPlayer.PlayerTier.TierD:
            base = 1
        else:
            base = randint(1, 3)

        # Longevity is how many pro seasons the player is expected to last.
        # Remaining career = longevity - seasonsPlayed; add 1 so a contract
        # that slightly outruns retirement is still OK (players sometimes
        # stick around a year longer than projected).
        longevity = getattr(getattr(player, 'attributes', None), 'longevity', 6) or 6
        remaining = max(1, longevity - seasonsPlayed + 1)

        # Tier-based contract floor — top players get longer deals at the
        # end of their career than the bare runway clamp would suggest.
        # An aged TierS still commands at least a 3-year offer (teams take
        # the dead-cap risk for hall-of-fame trajectory players); TierA
        # holds at 2 years; lower tiers fall to the runway floor of 1.
        if tier == FloosPlayer.PlayerTier.TierS:
            floor = 2
        elif tier == FloosPlayer.PlayerTier.TierA:
            floor = 2
        else:
            floor = 1
        return max(floor, min(base, remaining))
    
    def conductInitialDraft(self) -> None:
        """Conduct the initial draft (replaces playerDraft function)"""
        from random import randint, choice
        import floosball_methods as FloosMethods
        
        logger.info("Starting initial player draft")
        
        # Get teams from service container
        # Get teams from team manager service
        teamManager = self.serviceContainer.getService('team_manager')
        teams = teamManager.teams if teamManager else []
        
        if not teams:
            logger.error("No teams available for draft!")
            return
        
        if not self.activePlayers:
            logger.error("No players available for draft!")
            return
        
        # Create position-specific draft lists (matches original)
        draftQbList = [p for p in self.activePlayers if p.position.value == 1]
        draftRbList = [p for p in self.activePlayers if p.position.value == 2] 
        draftWrList = [p for p in self.activePlayers if p.position.value == 3]
        draftTeList = [p for p in self.activePlayers if p.position.value == 4]
        draftKList = [p for p in self.activePlayers if p.position.value == 5]
        
        # Sort by skillRating (matches original)
        draftQbList.sort(key=lambda p: p.attributes.skillRating, reverse=True)
        draftRbList.sort(key=lambda p: p.attributes.skillRating, reverse=True)
        draftWrList.sort(key=lambda p: p.attributes.skillRating, reverse=True)
        draftTeList.sort(key=lambda p: p.attributes.skillRating, reverse=True)
        draftKList.sort(key=lambda p: p.attributes.skillRating, reverse=True)
        
        playerDraftList = self.activePlayers.copy()
        playerDraftList.sort(key=lambda p: p.attributes.skillRating, reverse=True)
        
        # Create random draft order (matches original)
        draftOrderList = []
        draftQueueList = teams.copy()
        
        for x in range(len(teams)):
            rand = randint(0, len(draftQueueList) - 1)
            draftOrderList.insert(x, draftQueueList[rand])
            draftQueueList.pop(rand)
        
        # Conduct 6 rounds of draft (matches original)
        rounds = 6
        
        for x in range(1, rounds + 1):
            for team in draftOrderList:
                openPosList = []
                selectedPlayer = None
                bestAvailablePlayer = playerDraftList[0] if playerDraftList else None
                
                if x == 1 and bestAvailablePlayer:  # First round - best available
                    if bestAvailablePlayer.position.value == 1:
                        selectedPlayer = draftQbList.pop(0)
                        team.rosterDict['qb'] = selectedPlayer
                        playerDraftList.remove(selectedPlayer)
                    elif bestAvailablePlayer.position.value == 2:
                        selectedPlayer = draftRbList.pop(0)
                        team.rosterDict['rb'] = selectedPlayer
                        playerDraftList.remove(selectedPlayer)
                    elif bestAvailablePlayer.position.value == 3:
                        selectedPlayer = draftWrList.pop(0)
                        if team.rosterDict['wr1'] is None:
                            team.rosterDict['wr1'] = selectedPlayer
                        elif team.rosterDict['wr2'] is None:
                            team.rosterDict['wr2'] = selectedPlayer
                        playerDraftList.remove(selectedPlayer)
                    elif bestAvailablePlayer.position.value == 4:
                        selectedPlayer = draftTeList.pop(0)
                        team.rosterDict['te'] = selectedPlayer
                        playerDraftList.remove(selectedPlayer)
                    elif bestAvailablePlayer.position.value == 5:
                        selectedPlayer = draftKList.pop(0)
                        team.rosterDict['k'] = selectedPlayer
                        playerDraftList.remove(selectedPlayer)
                else:  # Later rounds - fill needs
                    if team.rosterDict['qb'] is None:
                        openPosList.append(FloosPlayer.Position.QB.value)
                    if team.rosterDict['rb'] is None:
                        openPosList.append(FloosPlayer.Position.RB.value)
                    if team.rosterDict['wr1'] is None or team.rosterDict['wr2'] is None:
                        openPosList.append(FloosPlayer.Position.WR.value)
                    if team.rosterDict['te'] is None:
                        openPosList.append(FloosPlayer.Position.TE.value)
                    if team.rosterDict['k'] is None:
                        openPosList.append(FloosPlayer.Position.K.value)
                    
                    if openPosList:
                        z = choice(openPosList)
                        
                        if z == FloosPlayer.Position.QB.value and draftQbList:
                            i = min(team.gmScore, len(draftQbList) - 1)
                            selectedPlayer = draftQbList.pop(randint(0, i))
                            team.rosterDict['qb'] = selectedPlayer
                            playerDraftList.remove(selectedPlayer)
                        elif z == FloosPlayer.Position.RB.value and draftRbList:
                            i = min(team.gmScore, len(draftRbList) - 1)
                            selectedPlayer = draftRbList.pop(randint(0, i))
                            team.rosterDict['rb'] = selectedPlayer
                            playerDraftList.remove(selectedPlayer)
                        elif z == FloosPlayer.Position.WR.value and draftWrList:
                            i = min(team.gmScore, len(draftWrList) - 1)
                            selectedPlayer = draftWrList.pop(randint(0, i))
                            if team.rosterDict['wr1'] is None:
                                team.rosterDict['wr1'] = selectedPlayer
                            elif team.rosterDict['wr2'] is None:
                                team.rosterDict['wr2'] = selectedPlayer
                            playerDraftList.remove(selectedPlayer)
                        elif z == FloosPlayer.Position.TE.value and draftTeList:
                            i = min(team.gmScore, len(draftTeList) - 1)
                            selectedPlayer = draftTeList.pop(randint(0, i))
                            team.rosterDict['te'] = selectedPlayer
                            playerDraftList.remove(selectedPlayer)
                        elif z == FloosPlayer.Position.K.value and draftKList:
                            i = min(team.gmScore, len(draftKList) - 1)
                            selectedPlayer = draftKList.pop(randint(0, i))
                            team.rosterDict['k'] = selectedPlayer
                            playerDraftList.remove(selectedPlayer)
                
                if selectedPlayer:
                    selectedPlayer.team = team
                    # Set player term based on tier (avoiding circular import)
                    selectedPlayer.term = self._getPlayerTerm(selectedPlayer)
                    selectedPlayer.termRemaining = selectedPlayer.term
                    
                    # Ensure seasonStatsDict exists and has team info
                    if not hasattr(selectedPlayer, 'seasonStatsDict') or selectedPlayer.seasonStatsDict is None:
                        selectedPlayer.seasonStatsDict = {}
                    selectedPlayer.seasonStatsDict['team'] = selectedPlayer.team.name
                    
                    # Ensure seasonStatsArchive exists
                    if not hasattr(selectedPlayer, 'seasonStatsArchive'):
                        selectedPlayer.seasonStatsArchive = []
                    
                    # Assign player number
                    team.assignPlayerNumber(selectedPlayer)
            
            # Reverse draft order for next round (snake draft)
            draftOrderList.reverse()
        
        # Move remaining players to free agency
        undrafted_count = 0
        for playerList in [draftQbList, draftRbList, draftWrList, draftTeList, draftKList]:
            for player in playerList:
                # Check if player is actually on a roster before marking as free agent
                is_on_roster = False
                for team in teams:
                    if player in team.rosterDict.values():
                        is_on_roster = True
                        logger.error(f"ERROR: {player.name} is in {team.name}'s roster but still in draft list!")
                        break
                
                if not is_on_roster:
                    player.team = 'Free Agent'
                    self.freeAgents.append(player)
                    undrafted_count += 1
                else:
                    # Player is on a roster, ensure they have correct team reference
                    for team in teams:
                        if player in team.rosterDict.values():
                            player.team = team
                            break
        
        logger.info(f"Draft complete: {undrafted_count} undrafted players moved to free agency")
        
        # Rebuild position lists
        self.rebuildPositionLists()
        
        logger.info(f"Draft complete. {len(self.activePlayers)} players drafted, "
                   f"{len(self.freeAgents)} free agents")
    
    def draftPlayerToTeam(self, player: FloosPlayer.Player, team: FloosTeam.Team) -> None:
        """Draft a player to a specific team"""
        player.team = team
        player.serviceTime = FloosPlayer.PlayerServiceTime.Rookie
        
        # Add to team roster (assuming team has a roster management method)
        if hasattr(team, 'addPlayer'):
            team.addPlayer(player)
        
        # Add to active players
        self.activePlayers.append(player)
    
    def retirePlayer(self, player: FloosPlayer.Player) -> None:
        """Move player to retirement"""
        logger.info(f"Retiring player: {player.name}")
        
        # Remove from active lists
        self.safeRemove(self.activePlayers, player)
        self.safeRemove(self.freeAgents, player)
        self.removeFromPositionList(player)
        
        # Update player status
        player.serviceTime = FloosPlayer.PlayerServiceTime.Retired
        player.team = 'Retired'
        
        # Add to retirement lists
        self.retiredPlayers.append(player)
        self.newlyRetiredPlayers.append(player)

    def computeRetirementOdds(self, player):
        """Single source of truth for whether a rostered player is eligible to
        retire THIS offseason and at what probability. Used by both the actual
        roll (seasonManager._evaluateRetirementCandidates) and the displayed
        risk tier (computeRetirementRisk), so the two never drift.

        Bands key off `yearsPast = seasonsPlayed - longevity` (longevity is the
        intended retirement clock; absolute seasonsPlayed can't grow past league
        age). Phased contract gate: a player only enters retirement territory on
        their walk season (termRemaining == 1), but once they're
        RETIREMENT_MIDCONTRACT_YEARS_PAST seasons past longevity they retire even
        mid-contract.

        Returns (chancePct: int, eligible: bool, yearsPast: int). When not
        eligible this offseason, chancePct is 0.
        """
        from constants import (
            RETIREMENT_YEARS_PAST_HIGH, RETIREMENT_YEARS_PAST_MID,
            RETIREMENT_YEARS_PAST_EARLY, RETIREMENT_CHANCE_HIGH,
            RETIREMENT_CHANCE_MID, RETIREMENT_CHANCE_EARLY,
            RETIREMENT_MIDCONTRACT_YEARS_PAST,
        )
        seasons = getattr(player, 'seasonsPlayed', 0) or 0
        attrs = getattr(player, 'attributes', None)
        longevity = getattr(attrs, 'longevity', 99) if attrs else 99
        termRemaining = getattr(player, 'termRemaining', 1) or 0
        yearsPast = seasons - longevity

        # Not yet at end of longevity → not a candidate.
        if yearsPast < RETIREMENT_YEARS_PAST_EARLY:
            return 0, False, yearsPast

        # Phased contract gate: walk-season only until deep past longevity.
        isWalkSeason = (termRemaining == 1)
        midContractOk = yearsPast >= RETIREMENT_MIDCONTRACT_YEARS_PAST
        if not isWalkSeason and not midContractOk:
            return 0, False, yearsPast

        if yearsPast >= RETIREMENT_YEARS_PAST_HIGH:
            return RETIREMENT_CHANCE_HIGH, True, yearsPast
        if yearsPast >= RETIREMENT_YEARS_PAST_MID:
            return RETIREMENT_CHANCE_MID, True, yearsPast
        return RETIREMENT_CHANCE_EARLY, True, yearsPast

    def computeRetirementRisk(self, player) -> str:
        """Classify a player's end-of-season retirement risk (display tier).

        Two distinct ideas are surfaced here. The lowest tier ('possible') is an
        intrinsic AGE signal — the player is past their personal longevity clock
        — and is NOT contract-gated, so it survives a re-sign (re-signing a vet
        doesn't make them younger). The louder tiers ('likely' / 'very_likely' /
        'retiring') are RETIREMENT-IMMINENCE signals: they only fire when the
        player is actually eligible to retire this offseason (walk season, or
        deep past longevity — see computeRetirementOdds), so re-signing a
        walk-year vet correctly steps them back down to the plain AGE signal.

        Returns:
          - 'retiring'    — decision is locked, player WILL retire this offseason
          - 'very_likely' — 3+ past longevity & retirement-eligible (90%)
          - 'likely'      — 1-2 past & retirement-eligible (65%)
          - 'possible'    — past longevity (aging); not retirement-eligible yet,
                            OR eligible but only just reached longevity
          - 'safe'        — still before their longevity clock
        """
        from constants import (
            RETIREMENT_YEARS_PAST_HIGH, RETIREMENT_YEARS_PAST_MID,
            RETIREMENT_YEARS_PAST_EARLY,
        )
        # Locked-in retirement (set during _evaluateRetirementCandidates when
        # the GM window opens) overrides any predictive tier.
        if getattr(player, 'willRetire', False):
            return 'retiring'

        _chance, eligible, yearsPast = self.computeRetirementOdds(player)
        # Still in their prime — before the longevity clock — no age signal.
        if yearsPast < RETIREMENT_YEARS_PAST_EARLY:
            return 'safe'
        # Past longevity but locked into a contract this offseason (mid-deal /
        # just re-signed): intrinsically aging, but not up for retirement yet.
        if not eligible:
            return 'possible'
        # Retirement-eligible this offseason → escalate by how far past longevity.
        if yearsPast >= RETIREMENT_YEARS_PAST_HIGH:
            return 'very_likely'
        if yearsPast >= RETIREMENT_YEARS_PAST_MID:
            return 'likely'
        return 'possible'

    def computeCareerStage(self, player) -> str:
        """Where a player sits on their career arc — the FA-ballot / draft view.

        Anchored to the SAME model that drives a player's actual rating arc
        (player_development.peakSeason: a jittered ~0.55-0.65 x longevity), so
        the displayed stage tracks reality rather than a parallel guess:

          - 'developing'      — still climbing toward their peak (upside ahead)
          - 'prime'           — at/around their peak season (DEV_PRIME_WINDOW
                                either side); should hold or improve
          - 'aging'           — past their prime plateau and declining (covers
                                from just-past-peak through the early seasons
                                past longevity, where retire odds are modest)
          - 'near_retirement' — deep past longevity (RETIREMENT_YEARS_PAST_HIGH+,
                                the ~90% retire-odds zone); runway nearly gone
          - 'retiring'        — decision locked, will retire this offseason

        The near_retirement boundary reuses RETIREMENT_YEARS_PAST_HIGH so it
        lines up with computeRetirementOdds' loudest tier; this isn't contract-
        gated because a signed FA gets a fresh term, so what matters is age, not
        this-offseason eligibility.
        """
        from constants import RETIREMENT_YEARS_PAST_HIGH, DEV_PRIME_WINDOW
        from player_development import PlayerDevelopment

        if getattr(player, 'willRetire', False):
            return 'retiring'
        seasons = getattr(player, 'seasonsPlayed', 0) or 0
        attrs = getattr(player, 'attributes', None)
        longevity = getattr(attrs, 'longevity', 99) if attrs else 99

        # Deep past the longevity clock → runway nearly gone, regardless of peak.
        if seasons - longevity >= RETIREMENT_YEARS_PAST_HIGH:
            return 'near_retirement'

        peak = PlayerDevelopment.peakSeason(player)
        if seasons < peak - DEV_PRIME_WINDOW:
            return 'developing'
        if seasons <= peak + DEV_PRIME_WINDOW:
            return 'prime'
        return 'aging'

    def promoteToHallOfFame(self, player: FloosPlayer.Player) -> None:
        """Promote retired player to Hall of Fame. HoFers stay on the
        retiredPlayers list too — load-from-DB routes them into both lists
        so this in-game path must mirror that to stay consistent."""
        if player not in self.retiredPlayers:
            logger.warning(f"Cannot promote {player.name} - not in retired players")
            return
        if player in self.hallOfFame:
            return

        logger.info(f"Promoting {player.name} to Hall of Fame")
        self.hallOfFame.append(player)
        player.is_hof = True
    
    def sortPlayersByPosition(self) -> None:
        """Sort players and assign tiers (replaces sortPlayers function)"""
        logger.debug("Sorting players and assigning tiers")
        
        # Tier thresholds aligned 1:1 with the UI star bands in
        # frontend Components/Stars.tsx::calcStars so a "4-star player" in the
        # UI is always TierA for contract / scouting / classification purposes.
        # The old thresholds (S≥93, A≥87, B≥77, C≥69) created a gap where
        # rating 84-86 showed as 4 stars but contracted as TierB — leading to
        # 1-year deals for visually high-rated players.
        # Star bands: 1★ 60-67 / 2★ 68-75 / 3★ 76-83 / 4★ 84-91 / 5★ 92-100
        tierS = 92  # 5★
        tierA = 84  # 4★
        tierB = 76  # 3★
        tierC = 68  # 2★
        # Below 68 → TierD (1★)
        
        for player in self.activePlayers:
            if player.playerRating >= tierS:
                player.playerTier = FloosPlayer.PlayerTier.TierS
            elif player.playerRating >= tierA:
                player.playerTier = FloosPlayer.PlayerTier.TierA
            elif player.playerRating >= tierB:
                player.playerTier = FloosPlayer.PlayerTier.TierB
            elif player.playerRating >= tierC:
                player.playerTier = FloosPlayer.PlayerTier.TierC
            else:
                player.playerTier = FloosPlayer.PlayerTier.TierD
            
            # Set cap hit for free agents (matches original logic)
            if player.team is None or player.team == 'Free Agent':
                player.capHit = player.playerTier.value
        
        # Also sort position lists by rating  
        self.activeQbs.sort(key=lambda p: p.playerRating, reverse=True)
        self.activeRbs.sort(key=lambda p: p.playerRating, reverse=True)
        self.activeWrs.sort(key=lambda p: p.playerRating, reverse=True)
        self.activeTes.sort(key=lambda p: p.playerRating, reverse=True)
        self.activeKs.sort(key=lambda p: p.playerRating, reverse=True)
    
    def rebuildPositionLists(self) -> None:
        """Rebuild position lists from active players"""
        # Clear existing lists
        self.activeQbs.clear()
        self.activeRbs.clear()
        self.activeWrs.clear()
        self.activeTes.clear()
        self.activeKs.clear()
        
        # Rebuild from active players
        for player in self.activePlayers:
            self.addToPositionList(player)
    
    def getPlayersByPosition(self, position: FloosPlayer.Position) -> List[FloosPlayer.Player]:
        """Get all active players by position"""
        if position == FloosPlayer.Position.QB:
            return self.activeQbs
        elif position == FloosPlayer.Position.RB:
            return self.activeRbs
        elif position == FloosPlayer.Position.WR:
            return self.activeWrs
        elif position == FloosPlayer.Position.TE:
            return self.activeTes
        elif position == FloosPlayer.Position.K:
            return self.activeKs
        return []
    
    def getFreeAgentsByPosition(self, position: FloosPlayer.Position) -> List[FloosPlayer.Player]:
        """Get available free agents by position"""
        return [p for p in self.freeAgents if p.position == position]
    
    def getPlayerById(self, playerId: int) -> Optional[FloosPlayer.Player]:
        """Find a player by ID via an O(1) id→player index.

        Previously this linear-scanned four lists on every call; the fantasy
        snapshot calls it per-user × per-roster-player, which made building the
        leaderboard O(users × roster × allPlayers). The index is rebuilt only
        when the total player population changes (stable within a snapshot, and
        only shifts on draft/retirement/FA churn between weeks)."""
        return self._ensurePlayerIndex().get(playerId)

    def _ensurePlayerIndex(self) -> Dict[int, "FloosPlayer.Player"]:
        """Return the id→player map, rebuilding it if the population changed.

        Last-list-wins ordering matches the old linear-scan precedence
        (active → retired → HoF → free agents)."""
        total = (len(self.activePlayers) + len(self.retiredPlayers)
                 + len(self.hallOfFame) + len(self.freeAgents))
        if getattr(self, '_playerByIdCount', None) != total or not hasattr(self, '_playerById'):
            idx: Dict[int, "FloosPlayer.Player"] = {}
            for player in self.freeAgents:
                idx[player.id] = player
            for player in self.hallOfFame:
                idx[player.id] = player
            for player in self.retiredPlayers:
                idx[player.id] = player
            for player in self.activePlayers:  # active wins on id collision
                idx[player.id] = player
            self._playerById = idx
            self._playerByIdCount = total
        return self._playerById
    
    def getStatistics(self) -> Dict[str, int]:
        """Get player statistics for monitoring"""
        return {
            'activePlayers': len(self.activePlayers),
            'freeAgents': len(self.freeAgents),
            'retiredPlayers': len(self.retiredPlayers),
            'hallOfFame': len(self.hallOfFame),
            'activeQbs': len(self.activeQbs),
            'activeRbs': len(self.activeRbs),
            'activeWrs': len(self.activeWrs),
            'activeTes': len(self.activeTes),
            'activeKs': len(self.activeKs)
        }
    
    def loadCurrentSeasonStats(self, seasonNumber: int, currentWeek: int = 28) -> None:
        """Restore player.seasonStatsDict from PlayerSeasonStats DB rows for an in-progress season.

        Called on mid-season resume so the simulation picks up with correct per-player
        stats (fantasy points, yards, TDs) accumulated in weeks already completed.
        """
        if not (DATABASE_AVAILABLE and USE_DATABASE and self.db_session):
            return
        try:
            from database.models import PlayerSeasonStats
            rows = self.db_session.query(PlayerSeasonStats).filter_by(
                season=seasonNumber
            ).all()
            statsByPlayerId = {row.player_id: row for row in rows}
            restored = 0
            for player in self.activePlayers:
                row = statsByPlayerId.get(player.id)
                if row is None:
                    continue
                player.seasonStatsDict = {
                    'gamesPlayed': row.games_played or 0,
                    'fantasyPoints': row.fantasy_points or 0,
                    'passing': row.passing_stats or {},
                    'rushing': row.rushing_stats or {},
                    'receiving': row.receiving_stats or {},
                    'kicking': row.kicking_stats or {},
                    'defense': row.defense_stats or {},
                }
                # Restore the direct gamesPlayed attribute used by MVP/All-Pro eligibility
                player.gamesPlayed = row.games_played or 0
                # Restore the season WPA value totals (plain attributes, not in the
                # stats dict) so mid-season resume continues accumulating from the
                # persisted total instead of restarting at 0.
                player.seasonWpa = float(getattr(row, 'wpa', 0.0) or 0.0)
                player.seasonDefWpa = float(getattr(row, 'def_wpa', 0.0) or 0.0)
                player.seasonWpaSnaps = int(getattr(row, 'wpa_snaps', 0) or 0)
                player.seasonDefWpaSnaps = int(getattr(row, 'def_snaps', 0) or 0)
                # Keep StatTracker pointing at the restored dict so stats accumulated
                # during subsequent games go to the right place.
                player.stat_tracker.season_stats_dict = player.seasonStatsDict
                restored += 1
            logger.info(f"Restored season {seasonNumber} stats for {restored} players")
            # Recompute seasonPerformanceRating from restored stats so MVP/All-Pro
            # selection works correctly on resume.
            if restored > 0:
                self.calculatePerformanceRatings(currentWeek=currentWeek)
        except Exception as e:
            logger.error(f"Failed to restore player season stats: {e}")

    def savePlayerData(self) -> None:
        """Save player data to database or JSON files"""
        # Use database if enabled
        if DATABASE_AVAILABLE and USE_DATABASE and self.player_repo:
            logger.debug("Saving players to database")
            self._savePlayersToDatabase()
        else:
            logger.debug("Saving players to JSON files")
            self._savePlayersToJSON()
    
    def _savePlayersToDatabase(self) -> None:
        """Save player data to database"""
        logger.info("Saving player data to database")
        
        try:
            from database.models import Player as DBPlayer, PlayerAttributes as DBPlayerAttributes, PlayerCareerStats, PlayerSeasonStats
            
            # Track statistics for debugging
            team_id_stats = {'with_team': 0, 'free_agent': 0, 'retired': 0, 'prospect': 0, 'upcoming_rookie': 0, 'null': 0, 'errors': 0}
            
            # Save all active players (includes free agents)
            all_players_to_save = list(self.activePlayers)
            
            # Also save retired players so their career stats are preserved
            # Use a set to deduplicate by player ID to avoid saving the same player twice
            seen_player_ids = {p.id for p in all_players_to_save}
            for retired_player in self.retiredPlayers:
                if retired_player.id not in seen_player_ids:
                    all_players_to_save.append(retired_player)
                    seen_player_ids.add(retired_player.id)
            
            for player in all_players_to_save:
                # Get team_id from player's team object
                team_id = None
                if hasattr(player, 'team') and player.team:
                    if isinstance(player.team, int):
                        team_id = player.team
                        team_id_stats['with_team'] += 1
                    elif isinstance(player.team, str):
                        # player.team is 'Free Agent' / 'Retired' / 'Prospect' — save as None.
                        # Prospect pipeline ownership is tracked via drafting_team_id.
                        team_id = None
                        if player.team == 'Retired':
                            team_id_stats['retired'] += 1
                        elif player.team == 'Prospect':
                            team_id_stats['prospect'] += 1
                        elif player.team == 'Upcoming Rookie':
                            team_id_stats['upcoming_rookie'] += 1
                        else:
                            team_id_stats['free_agent'] += 1
                    elif hasattr(player.team, 'id'):
                        team_id = player.team.id
                        team_id_stats['with_team'] += 1
                    else:
                        # Unexpected type - log warning and save as None
                        logger.warning(f"Player {player.name} has unexpected team type: {type(player.team)}")
                        team_id = None
                        team_id_stats['errors'] += 1
                else:
                    team_id_stats['null'] += 1
                
                # Create or update player record
                db_player = self.db_session.query(DBPlayer).filter_by(id=player.id).first()
                
                defPosValue = player.defensivePosition.value if hasattr(player, 'defensivePosition') and player.defensivePosition else None

                if db_player is None:
                    # Create new player
                    db_player = DBPlayer(
                        id=player.id,
                        name=player.name,
                        current_number=player.currentNumber,
                        preferred_number=player.preferredNumber,
                        tier=player.playerTier.name if hasattr(player, 'playerTier') else None,
                        team_id=team_id,
                        position=player.position.value if hasattr(player.position, 'value') else player.position,
                        seasons_played=player.seasonsPlayed,
                        term=player.term,
                        term_remaining=player.termRemaining,
                        cap_hit=player.capHit,
                        team_resign_count=int(getattr(player, 'teamResignCount', 0) or 0),
                        player_rating=player.playerRating,
                        offensive_rating=getattr(player, 'offensiveRating', None),
                        defensive_rating=getattr(player, 'defensiveRating', None),
                        defensive_position=defPosValue,
                        free_agent_years=player.freeAgentYears,
                        service_time=player.serviceTime.name if hasattr(player, 'serviceTime') else None,
                        is_prospect=bool(getattr(player, 'is_prospect', False)),
                        is_undrafted=bool(getattr(player, 'is_undrafted', False)),
                        prospect_seasons=int(getattr(player, 'prospect_seasons', 0) or 0),
                        drafting_team_id=getattr(player, 'drafting_team_id', None),
                        is_upcoming_rookie=bool(getattr(player, 'is_upcoming_rookie', False)),
                        will_retire=bool(getattr(player, 'willRetire', False)),
                        is_hof=bool(getattr(player, 'is_hof', False)),
                        hof_season=getattr(player, 'hof_season', None),
                        mvp_awards=list(getattr(player, 'mvpAwards', None) or []),
                        all_pro_seasons=list(getattr(player, 'allProSeasons', None) or []),
                        league_championships=list(getattr(player, 'leagueChampionships', None) or []),
                    )
                    self.db_session.add(db_player)
                else:
                    # Update existing player
                    db_player.name = player.name
                    db_player.current_number = player.currentNumber
                    db_player.preferred_number = player.preferredNumber
                    db_player.tier = player.playerTier.name if hasattr(player, 'playerTier') else None
                    db_player.team_id = team_id
                    db_player.position = player.position.value if hasattr(player.position, 'value') else player.position
                    db_player.seasons_played = player.seasonsPlayed
                    db_player.term = player.term
                    db_player.term_remaining = player.termRemaining
                    db_player.cap_hit = player.capHit
                    db_player.team_resign_count = int(getattr(player, 'teamResignCount', 0) or 0)
                    db_player.player_rating = player.playerRating
                    db_player.offensive_rating = getattr(player, 'offensiveRating', None)
                    db_player.defensive_rating = getattr(player, 'defensiveRating', None)
                    db_player.defensive_position = defPosValue
                    db_player.free_agent_years = player.freeAgentYears
                    db_player.service_time = player.serviceTime.name if hasattr(player, 'serviceTime') else None
                    db_player.is_prospect = bool(getattr(player, 'is_prospect', False))
                    db_player.is_undrafted = bool(getattr(player, 'is_undrafted', False))
                    db_player.prospect_seasons = int(getattr(player, 'prospect_seasons', 0) or 0)
                    db_player.drafting_team_id = getattr(player, 'drafting_team_id', None)
                    db_player.is_upcoming_rookie = bool(getattr(player, 'is_upcoming_rookie', False))
                    db_player.will_retire = bool(getattr(player, 'willRetire', False))
                    db_player.is_hof = bool(getattr(player, 'is_hof', False))
                    db_player.hof_season = getattr(player, 'hof_season', None)
                    db_player.mvp_awards = list(getattr(player, 'mvpAwards', None) or [])
                    db_player.all_pro_seasons = list(getattr(player, 'allProSeasons', None) or [])
                    db_player.league_championships = list(getattr(player, 'leagueChampionships', None) or [])

                # Save or update attributes
                db_attrs = self.db_session.query(DBPlayerAttributes).filter_by(player_id=player.id).first()
                
                if hasattr(player, 'attributes') and player.attributes:
                    attrs = player.attributes
                    if db_attrs is None:
                        db_attrs = DBPlayerAttributes(
                            player_id=player.id,
                            overall_rating=attrs.overallRating,
                            speed=attrs.speed,
                            hands=attrs.hands,
                            reach=attrs.reach,
                            agility=attrs.agility,
                            power=attrs.power,
                            arm_strength=attrs.armStrength,
                            accuracy=attrs.accuracy,
                            leg_strength=attrs.legStrength,
                            skill_rating=attrs.skillRating,
                            potential_speed=attrs.potentialSpeed,
                            potential_hands=attrs.potentialHands,
                            potential_reach=attrs.potentialReach,
                            potential_agility=attrs.potentialAgility,
                            potential_power=attrs.potentialPower,
                            potential_arm_strength=attrs.potentialArmStrength,
                            potential_accuracy=attrs.potentialAccuracy,
                            potential_leg_strength=attrs.potentialLegStrength,
                            potential_skill_rating=attrs.potentialSkillRating,
                            true_skill_speed=getattr(attrs, 'trueSkillSpeed', 0),
                            true_skill_hands=getattr(attrs, 'trueSkillHands', 0),
                            true_skill_reach=getattr(attrs, 'trueSkillReach', 0),
                            true_skill_agility=getattr(attrs, 'trueSkillAgility', 0),
                            true_skill_power=getattr(attrs, 'trueSkillPower', 0),
                            true_skill_arm_strength=getattr(attrs, 'trueSkillArmStrength', 0),
                            true_skill_accuracy=getattr(attrs, 'trueSkillAccuracy', 0),
                            true_skill_leg_strength=getattr(attrs, 'trueSkillLegStrength', 0),
                            route_running=attrs.routeRunning,
                            vision=attrs.vision,
                            blocking=attrs.blocking,
                            discipline=attrs.discipline,
                            attitude=attrs.attitude,
                            attitude_baseline=getattr(attrs, 'attitudeBaseline', 0) or attrs.attitude,
                            focus=attrs.focus,
                            instinct=attrs.instinct,
                            creativity=attrs.creativity,
                            resilience=attrs.resilience,
                            clutch_factor=attrs.clutchFactor,
                            self_belief=getattr(attrs, 'selfBelief', 80),
                            pressure_handling=attrs.pressureHandling,
                            longevity=attrs.longevity,
                            play_making_ability=attrs.playMakingAbility,
                            x_factor=attrs.xFactor,
                            confidence_modifier=attrs.confidenceModifier,
                            determination_modifier=attrs.determinationModifier,
                            luck_modifier=attrs.luckModifier,
                            defensive_talent=getattr(attrs, 'defensiveTalent', 0),
                            fatigue=attrs.fatigue,
                            personality=getattr(attrs, 'personality', None),
                            quirk=getattr(attrs, 'quirk', None),
                            mood=getattr(attrs, 'mood', 3) or 3,
                            hometown=getattr(attrs, 'hometown', None),
                            favorite_category=getattr(attrs, 'favorite_category', None),
                            favorite_item=getattr(attrs, 'favorite_item', None),
                            motto=getattr(attrs, 'motto', None),
                        )
                        self.db_session.add(db_attrs)
                    else:
                        # Update existing attributes
                        db_attrs.overall_rating = attrs.overallRating
                        db_attrs.speed = attrs.speed
                        db_attrs.hands = attrs.hands
                        db_attrs.reach = attrs.reach
                        db_attrs.agility = attrs.agility
                        db_attrs.power = attrs.power
                        db_attrs.arm_strength = attrs.armStrength
                        db_attrs.accuracy = attrs.accuracy
                        db_attrs.leg_strength = attrs.legStrength
                        db_attrs.skill_rating = attrs.skillRating
                        db_attrs.potential_speed = attrs.potentialSpeed
                        db_attrs.potential_hands = attrs.potentialHands
                        db_attrs.potential_reach = attrs.potentialReach
                        db_attrs.potential_agility = attrs.potentialAgility
                        db_attrs.potential_power = attrs.potentialPower
                        db_attrs.potential_arm_strength = attrs.potentialArmStrength
                        db_attrs.potential_accuracy = attrs.potentialAccuracy
                        db_attrs.potential_leg_strength = attrs.potentialLegStrength
                        db_attrs.potential_skill_rating = attrs.potentialSkillRating
                        db_attrs.true_skill_speed = getattr(attrs, 'trueSkillSpeed', 0)
                        db_attrs.true_skill_hands = getattr(attrs, 'trueSkillHands', 0)
                        db_attrs.true_skill_reach = getattr(attrs, 'trueSkillReach', 0)
                        db_attrs.true_skill_agility = getattr(attrs, 'trueSkillAgility', 0)
                        db_attrs.true_skill_power = getattr(attrs, 'trueSkillPower', 0)
                        db_attrs.true_skill_arm_strength = getattr(attrs, 'trueSkillArmStrength', 0)
                        db_attrs.true_skill_accuracy = getattr(attrs, 'trueSkillAccuracy', 0)
                        db_attrs.true_skill_leg_strength = getattr(attrs, 'trueSkillLegStrength', 0)
                        db_attrs.route_running = attrs.routeRunning
                        db_attrs.vision = attrs.vision
                        db_attrs.blocking = attrs.blocking
                        db_attrs.discipline = attrs.discipline
                        db_attrs.attitude = attrs.attitude
                        db_attrs.attitude_baseline = getattr(attrs, 'attitudeBaseline', 0) or attrs.attitude
                        db_attrs.focus = attrs.focus
                        db_attrs.instinct = attrs.instinct
                        db_attrs.creativity = attrs.creativity
                        db_attrs.resilience = attrs.resilience
                        db_attrs.clutch_factor = attrs.clutchFactor
                        db_attrs.self_belief = getattr(attrs, 'selfBelief', 80)
                        db_attrs.pressure_handling = attrs.pressureHandling
                        db_attrs.longevity = attrs.longevity
                        db_attrs.play_making_ability = attrs.playMakingAbility
                        db_attrs.x_factor = attrs.xFactor
                        db_attrs.confidence_modifier = attrs.confidenceModifier
                        db_attrs.determination_modifier = attrs.determinationModifier
                        db_attrs.luck_modifier = attrs.luckModifier
                        db_attrs.defensive_talent = getattr(attrs, 'defensiveTalent', 0)
                        db_attrs.fatigue = attrs.fatigue
                        db_attrs.personality = getattr(attrs, 'personality', None)
                        db_attrs.quirk = getattr(attrs, 'quirk', None)
                        db_attrs.mood = getattr(attrs, 'mood', 3) or 3
                        db_attrs.hometown = getattr(attrs, 'hometown', None)
                        db_attrs.favorite_category = getattr(attrs, 'favorite_category', None)
                        db_attrs.favorite_item = getattr(attrs, 'favorite_item', None)
                        db_attrs.motto = getattr(attrs, 'motto', None)

                # Save career stats (season 0 = career totals)
                if hasattr(player, 'careerStatsDict') and player.careerStatsDict:
                    db_career_stats = self.db_session.query(PlayerCareerStats).filter_by(
                        player_id=player.id, season=0
                    ).first()
                    
                    stats_dict = player.careerStatsDict
                    
                    # Extract denormalized stats from JSON
                    passing = stats_dict.get('passing') or {}
                    rushing = stats_dict.get('rushing') or {}
                    receiving = stats_dict.get('receiving') or {}
                    
                    if db_career_stats is None:
                        db_career_stats = PlayerCareerStats(
                            player_id=player.id,
                            season=0,
                            games_played=stats_dict.get('gamesPlayed', 0),
                            fantasy_points=stats_dict.get('fantasyPoints', 0),
                            # Denormalized columns for leaderboards
                            passing_yards=passing.get('yards', 0),
                            passing_tds=passing.get('tds', 0),
                            passing_ints=passing.get('ints', 0),
                            rushing_yards=rushing.get('yards', 0),
                            rushing_tds=rushing.get('tds', 0),
                            receiving_yards=receiving.get('yards', 0),
                            receiving_tds=receiving.get('tds', 0),
                            # JSON for detailed stats
                            passing_stats=stats_dict.get('passing'),
                            rushing_stats=stats_dict.get('rushing'),
                            receiving_stats=stats_dict.get('receiving'),
                            kicking_stats=stats_dict.get('kicking'),
                            defense_stats=stats_dict.get('defense'),
                        )
                        self.db_session.add(db_career_stats)
                    else:
                        db_career_stats.games_played = stats_dict.get('gamesPlayed', 0)
                        db_career_stats.fantasy_points = stats_dict.get('fantasyPoints', 0)
                        # Update denormalized columns
                        db_career_stats.passing_yards = passing.get('yards', 0)
                        db_career_stats.passing_tds = passing.get('tds', 0)
                        db_career_stats.passing_ints = passing.get('ints', 0)
                        db_career_stats.rushing_yards = rushing.get('yards', 0)
                        db_career_stats.rushing_tds = rushing.get('tds', 0)
                        db_career_stats.receiving_yards = receiving.get('yards', 0)
                        db_career_stats.receiving_tds = receiving.get('tds', 0)
                        # Update JSON — wrap with dict() AND flag_modified()
                        # because the in-memory dict IS the same SQLAlchemy
                        # loaded; without explicit dirty-marking the update
                        # is silently dropped on value-equality.
                        from sqlalchemy.orm.attributes import flag_modified
                        db_career_stats.passing_stats = dict(stats_dict.get('passing') or {})
                        db_career_stats.rushing_stats = dict(stats_dict.get('rushing') or {})
                        db_career_stats.receiving_stats = dict(stats_dict.get('receiving') or {})
                        db_career_stats.kicking_stats = dict(stats_dict.get('kicking') or {})
                        db_career_stats.defense_stats = dict(stats_dict.get('defense') or {})
                        for _f in ('passing_stats', 'rushing_stats', 'receiving_stats',
                                   'kicking_stats', 'defense_stats'):
                            flag_modified(db_career_stats, _f)
                
                # Save season stats (if we have a current season)
                season_manager = self.serviceContainer.getService('season_manager')
                if season_manager and hasattr(season_manager, 'currentSeason') and season_manager.currentSeason:
                    current_season = season_manager.currentSeason.seasonNumber

                    if hasattr(player, 'seasonStatsDict') and player.seasonStatsDict:
                        db_season_stats = self.db_session.query(PlayerSeasonStats).filter_by(
                            player_id=player.id, season=current_season
                        ).first()

                        season_dict = player.seasonStatsDict

                        # Detect if stats have been reset (post-season progression).
                        # If the DB already has real data for this season, don't overwrite with zeros.
                        gamesInMemory = getattr(player, 'gamesPlayed', 0) or season_dict.get('gp', 0)
                        if db_season_stats is not None and (db_season_stats.games_played or 0) > 0 and gamesInMemory == 0:
                            # Stats were already saved; in-memory dict is reset — skip update
                            pass
                        else:
                            # Extract denormalized stats from JSON
                            s_passing = season_dict.get('passing') or {}
                            s_rushing = season_dict.get('rushing') or {}
                            s_receiving = season_dict.get('receiving') or {}
                            s_defense = season_dict.get('defense') or {}

                            # Get team ID from player's team object
                            playerTeamId = player.team.id if hasattr(player, 'team') and hasattr(player.team, 'id') else None

                            if db_season_stats is None:
                                db_season_stats = PlayerSeasonStats(
                                    player_id=player.id,
                                    season=current_season,
                                    team_id=playerTeamId,
                                    games_played=gamesInMemory,
                                    fantasy_points=season_dict.get('fantasyPoints', 0),
                                    # Denormalized passing stats
                                    passing_yards=s_passing.get('yards', 0),
                                    passing_tds=s_passing.get('tds', 0),
                                    passing_ints=s_passing.get('ints', 0),
                                    passing_completions=s_passing.get('comps', 0),
                                    passing_attempts=s_passing.get('atts', 0),
                                    # Denormalized rushing stats
                                    rushing_yards=s_rushing.get('yards', 0),
                                    rushing_tds=s_rushing.get('tds', 0),
                                    rushing_attempts=s_rushing.get('atts', 0),
                                    # Denormalized receiving stats
                                    receiving_yards=s_receiving.get('yards', 0),
                                    receiving_tds=s_receiving.get('tds', 0),
                                    receptions=s_receiving.get('receptions', 0),
                                    # Denormalized defensive stats
                                    sacks=s_defense.get('sacks', 0),
                                    interceptions=s_defense.get('ints', 0),
                                    tackles=s_defense.get('tackles', 0),
                                    # Season WPA value totals (on the player object, not season_dict)
                                    wpa=float(getattr(player, 'seasonWpa', 0.0)),
                                    def_wpa=float(getattr(player, 'seasonDefWpa', 0.0)),
                                    wpa_snaps=int(getattr(player, 'seasonWpaSnaps', 0)),
                                    def_snaps=int(getattr(player, 'seasonDefWpaSnaps', 0)),
                                    # JSON for detailed stats
                                    passing_stats=season_dict.get('passing'),
                                    rushing_stats=season_dict.get('rushing'),
                                    receiving_stats=season_dict.get('receiving'),
                                    kicking_stats=season_dict.get('kicking'),
                                    defense_stats=season_dict.get('defense'),
                                )
                                self.db_session.add(db_season_stats)
                            else:
                                db_season_stats.team_id = playerTeamId
                                db_season_stats.games_played = gamesInMemory
                                db_season_stats.fantasy_points = season_dict.get('fantasyPoints', 0)
                                # Update denormalized passing stats
                                db_season_stats.passing_yards = s_passing.get('yards', 0)
                                db_season_stats.passing_tds = s_passing.get('tds', 0)
                                db_season_stats.passing_ints = s_passing.get('ints', 0)
                                db_season_stats.passing_completions = s_passing.get('comps', 0)
                                db_season_stats.passing_attempts = s_passing.get('atts', 0)
                                # Update denormalized rushing stats
                                db_season_stats.rushing_yards = s_rushing.get('yards', 0)
                                db_season_stats.rushing_tds = s_rushing.get('tds', 0)
                                db_season_stats.rushing_attempts = s_rushing.get('atts', 0)
                                # Update denormalized receiving stats
                                db_season_stats.receiving_yards = s_receiving.get('yards', 0)
                                db_season_stats.receiving_tds = s_receiving.get('tds', 0)
                                db_season_stats.receptions = s_receiving.get('receptions', 0)
                                # Update denormalized defensive stats
                                db_season_stats.sacks = s_defense.get('sacks', 0)
                                db_season_stats.interceptions = s_defense.get('ints', 0)
                                db_season_stats.tackles = s_defense.get('tackles', 0)
                                db_season_stats.wpa = float(getattr(player, 'seasonWpa', 0.0))
                                db_season_stats.def_wpa = float(getattr(player, 'seasonDefWpa', 0.0))
                                db_season_stats.wpa_snaps = int(getattr(player, 'seasonWpaSnaps', 0))
                                db_season_stats.def_snaps = int(getattr(player, 'seasonDefWpaSnaps', 0))
                                # Update JSON — wrap with dict() AND use
                                # flag_modified() because the in-memory dict
                                # we mutate IS the same object SQLAlchemy
                                # loaded from DB. Without flag_modified,
                                # SQLAlchemy compares new == loaded (both
                                # reflect the mutations) and silently skips
                                # the column update.
                                from sqlalchemy.orm.attributes import flag_modified
                                db_season_stats.passing_stats = dict(season_dict.get('passing') or {})
                                db_season_stats.rushing_stats = dict(season_dict.get('rushing') or {})
                                db_season_stats.receiving_stats = dict(season_dict.get('receiving') or {})
                                db_season_stats.kicking_stats = dict(season_dict.get('kicking') or {})
                                db_season_stats.defense_stats = dict(season_dict.get('defense') or {})
                                for _f in ('passing_stats', 'rushing_stats', 'receiving_stats',
                                           'kicking_stats', 'defense_stats'):
                                    flag_modified(db_season_stats, _f)
            
            # Commit all changes
            try:
                self.db_session.commit()
            except Exception as e:
                logger.error(f"Error committing player data to database: {e}")
                self.db_session.rollback()
                raise
            
            # Log statistics about team assignments
            logger.info(f"Saved {len(all_players_to_save)} players to database ({len(self.activePlayers)} active, {len(self.retiredPlayers)} retired)")
            logger.info(f"Team assignment stats: {team_id_stats['with_team']} with teams, "
                       f"{team_id_stats['free_agent']} free agents, "
                       f"{team_id_stats['retired']} retired, "
                       f"{team_id_stats['null']} null teams, "
                       f"{team_id_stats['errors']} errors")
            
            # Verify roster consistency - check if players on rosters have correct team references
            teamManager = self.serviceContainer.getService('team_manager')
            if teamManager:
                roster_mismatches = 0
                for team in teamManager.teams:
                    for pos, player in team.rosterDict.items():
                        if player and hasattr(player, 'team'):
                            if isinstance(player.team, str) and player.team in ['Free Agent', 'Retired']:
                                logger.warning(f"ROSTER MISMATCH: {player.name} is in {team.name}'s roster at {pos} but team='{player.team}'")
                                roster_mismatches += 1
                if roster_mismatches > 0:
                    logger.warning(f"Found {roster_mismatches} players on rosters with incorrect team references")
            
        except Exception as e:
            logger.error(f"Failed to save players to database: {e}")
            self.db_session.rollback()
            raise
    
    def _savePlayersToJSON(self) -> None:
        """Save player data to JSON files (replaces savePlayerData function)"""
        import os
        import json
        from serializers import ModernSerializer
        
        logger.info("Saving player data")
        
        # Create playerData directory (matches original)
        if not os.path.exists('data/playerData'):
            os.makedirs('data/playerData')
        
        # Save individual files per player (matches original format)
        for player in self.activePlayers:
            playerDict = {}
            playerDict['name'] = player.name
            playerDict['id'] = player.id
            playerDict['currentNumber'] = player.currentNumber
            playerDict['preferredNumber'] = player.preferredNumber
            playerDict['tier'] = player.playerTier.name
            playerDict['team'] = player.team.name if hasattr(player.team, 'name') else str(player.team)
            playerDict['position'] = player.position.value if hasattr(player.position, 'value') else str(player.position)
            playerDict['seasonsPlayed'] = player.seasonsPlayed
            playerDict['term'] = player.term
            playerDict['termRemaining'] = player.termRemaining
            playerDict['capHit'] = player.capHit
            playerDict['seasonPerformanceRating'] = player.seasonPerformanceRating
            playerDict['playerRating'] = player.playerRating
            playerDict['freeAgentYears'] = player.freeAgentYears
            playerDict['serviceTime'] = player.serviceTime.name
            # Handle attributes safely to avoid circular references
            if hasattr(player, 'attributes') and player.attributes:
                try:
                    playerDict['attributes'] = vars(player.attributes) if hasattr(player.attributes, '__dict__') else player.attributes
                except:
                    playerDict['attributes'] = {}
            playerDict['mvpAwards'] = getattr(player, 'mvpAwards', [])
            playerDict['allProSeasons'] = getattr(player, 'allProSeasons', [])
            playerDict['leagueChampionships'] = getattr(player, 'leagueChampionships', [])
            playerDict['careerStats'] = player.careerStatsDict
            
            # Handle seasonStatsArchive as numbered dictionary (matches original)
            archiveDict = {}
            if hasattr(player, 'seasonStatsArchive') and player.seasonStatsArchive:
                y = 0
                for item in player.seasonStatsArchive:
                    y += 1
                    archiveDict[y] = item
            playerDict['seasonStatsArchive'] = archiveDict
            
            # Serialize and save individual file (matches original)
            serializedDict = ModernSerializer.serialize(playerDict)
            with open(f"data/playerData/player{player.id}.json", "w") as jsonFile:
                json.dump(serializedDict, jsonFile, indent=4)
        
        logger.info(f"Saved data for {len(self.activePlayers)} active players")
    
    def saveUnusedNames(self) -> None:
        """Save unused names to database or JSON file"""
        # Use database if enabled
        if DATABASE_AVAILABLE and USE_DATABASE and self.name_repo:
            logger.debug("Saving unused names to database")
            self._saveUnusedNamesToDatabase()
        else:
            logger.debug("Saving unused names to JSON file")
            self._saveUnusedNamesToJSON()
    
    def _saveUnusedNamesToDatabase(self) -> None:
        """Save unused names to database"""
        try:
            from database.models import UnusedName, PendingName

            # Clear existing unused names
            self.db_session.query(UnusedName).delete()
            # Full-replace held (pending) names too, so they persist on the same
            # reliable path (and don't accumulate stale rows).
            self.db_session.query(PendingName).delete()
            self.db_session.flush()  # Ensure delete is committed before insert

            # Add current unused names
            self.name_repo.add_names_batch(self.unusedNames)
            for pendName, pendSeason in self.pendingNames:
                self.db_session.add(PendingName(name=pendName, available_season=pendSeason))
            self.db_session.commit()

            logger.debug(f"Saved {len(self.unusedNames)} unused names + {len(self.pendingNames)} held to database")
        except Exception as e:
            logger.error(f"Failed to save unused names to database: {e}")
            self.db_session.rollback()
    
    def _saveUnusedNamesToJSON(self) -> None:
        """Save unused names to JSON file (matches original saveUnusedNames function)"""
        import json
        import os
        
        # Ensure data directory exists
        os.makedirs("data", exist_ok=True)
        
        # Create dictionary with numeric keys like original
        unusedNamesDict = {}
        for i, name in enumerate(self.unusedNames, 1):
            unusedNamesDict[str(i)] = name
        
        try:
            with open("data/unusedNames.json", "w") as jsonFile:
                json.dump(unusedNamesDict, jsonFile, indent=4)
            logger.info(f"Saved {len(self.unusedNames)} unused names to data/unusedNames.json")
        except Exception as e:
            logger.error(f"Failed to save unused names: {e}")

    def addPendingName(self, name: str, availableSeason: int) -> None:
        """Hold a recycled retiree name out of the usable pool until availableSeason.
        Appends to the in-memory pendingNames list (persisted alongside unusedNames
        via the full-replace save) — kept off the shared session's mid-offseason
        transaction, which is lock-prone and may roll back."""
        if not (DATABASE_AVAILABLE and USE_DATABASE):
            # JSON/legacy mode: no delay support — fall back to immediate reuse.
            self.unusedNames.append(name)
            return
        self.pendingNames.append((name, availableSeason))

    def releaseDueNames(self, seasonNumber: int) -> int:
        """Move recycled names whose hold has elapsed (availableSeason <= season)
        back into the usable pool. Called at season start. Returns the count released."""
        if not self.pendingNames:
            return 0
        due = [(n, s) for (n, s) in self.pendingNames if s <= seasonNumber]
        if not due:
            return 0
        for name, _ in due:
            if name not in self.unusedNames:
                self.unusedNames.append(name)
        self.pendingNames = [(n, s) for (n, s) in self.pendingNames if s > seasonNumber]
        # Persist both lists together (full-replace, same reliable path as unused names).
        self.saveUnusedNames()
        logger.info(f"Released {len(due)} retired name(s) back to the pool (season {seasonNumber})")
        return len(due)

    def processHofPromotions(self) -> None:
        """Process Hall of Fame promotions"""
        hofCandidates = []
        
        for player in self.retiredPlayers:
            # Hall of Fame criteria (adjust as needed)
            if (len(player.leagueChampionships) >= 2 or
                player.seasonsPlayed >= 15 and player.playerRating >= 90):
                hofCandidates.append(player)
        
        for player in hofCandidates:
            self.promoteToHallOfFame(player)
    
    # Hall of Fame scoring weights. Tuned so a single MVP alone falls short
    # (player needs supporting accolades), and current record holders are
    # the marquee criterion.
    HOF_POINTS_MVP = 12
    HOF_POINTS_CHAMPIONSHIP = 10
    HOF_POINTS_ALL_PRO = 4
    HOF_POINTS_CAREER_RECORD = 18
    HOF_POINTS_SEASON_RECORD = 6
    HOF_POINTS_GAME_RECORD = 2
    HOF_POINTS_LONG_CAREER = 4       # 10+ seasons
    HOF_POINTS_IRON_MAN = 4          # 14+ seasons (cumulative on top of LONG_CAREER)
    HOF_INDUCT_THRESHOLD = 22

    # Positive record keys per category — negative-stat records like
    # 'ints' / 'fumbles' shouldn't earn HoF credit.
    _HOF_POSITIVE_RECORD_KEYS = {
        'passing':   {'yards', 'tds', 'comps'},
        'rushing':   {'yards', 'tds'},
        'receiving': {'yards', 'tds', 'receptions'},
        'kicking':   {'fgs', 'fgYards'},
        'fantasy':   {'qb', 'rb', 'wr', 'te', 'k'},
    }

    def _countCurrentRecordsHeld(self, playerId: int) -> Dict[str, int]:
        """Return how many positive records this player currently holds at
        each scope. Returns {'game': n, 'season': n, 'career': n}. Silently
        zero'd if the records manager isn't available."""
        out = {'game': 0, 'season': 0, 'career': 0}
        try:
            recordsManager = self.serviceContainer.getService('records_manager')
            if recordsManager is None:
                return out
            records = recordsManager.getRecords() or {}
            players = records.get('players', {}) or {}
            for category, scopes in players.items():
                positiveKeys = self._HOF_POSITIVE_RECORD_KEYS.get(category, set())
                if not positiveKeys or not isinstance(scopes, dict):
                    continue
                for scope, entries in scopes.items():
                    if scope not in out or not isinstance(entries, dict):
                        continue
                    for key, entry in entries.items():
                        if key not in positiveKeys or not isinstance(entry, dict):
                            continue
                        if entry.get('id') == playerId and (entry.get('value') or 0) > 0:
                            out[scope] += 1
        except Exception as e:
            logger.debug(f"HoF record-holder check failed for player {playerId}: {e}")
        return out

    def _computeHofPoints(self, player) -> Tuple[int, Dict[str, Any]]:
        """Score a player against the HoF criteria. Returns (points, breakdown).
        Breakdown is surfaced in the induction highlight so users see *why*."""
        mvps = len(getattr(player, 'mvpAwards', None) or [])
        rings = len(getattr(player, 'leagueChampionships', None) or [])
        allPros = len(getattr(player, 'allProSeasons', None) or [])
        seasons = getattr(player, 'seasonsPlayed', 0) or 0
        records = self._countCurrentRecordsHeld(getattr(player, 'id', 0))

        pts = 0
        pts += mvps * self.HOF_POINTS_MVP
        pts += rings * self.HOF_POINTS_CHAMPIONSHIP
        pts += allPros * self.HOF_POINTS_ALL_PRO
        pts += records['career'] * self.HOF_POINTS_CAREER_RECORD
        pts += records['season'] * self.HOF_POINTS_SEASON_RECORD
        pts += records['game']   * self.HOF_POINTS_GAME_RECORD
        if seasons >= 10:
            pts += self.HOF_POINTS_LONG_CAREER
        if seasons >= 14:
            pts += self.HOF_POINTS_IRON_MAN

        return pts, {
            'mvps': mvps, 'championships': rings, 'allPros': allPros,
            'seasons': seasons,
            'careerRecords': records['career'],
            'seasonRecords': records['season'],
            'gameRecords':   records['game'],
        }

    def inductHallOfFame(self, excludePlayerIds: set = None) -> None:
        """Score retired players against the HoF criteria and induct anyone
        clearing HOF_INDUCT_THRESHOLD.

        Scans the union of this session's newly-retired players AND all
        persisted retirees, skipping anyone already inducted (`is_hof`). Career
        awards and `is_hof` both persist, so this is self-healing: a worthy
        retiree is never permanently missed just because the sim restarted
        between their retirement and this end-of-offseason step (which would
        wipe the in-memory `newlyRetiredPlayers` list). The signature legacy
        criteria (TierS auto / TierA with a ring) are subsumed by the points
        system.

        `excludePlayerIds`: when fan-voted awards are active, the AwardsManager
        owns everyone who reached the HoF ballot (vote + class cap). This call
        then runs as a points-only SAFETY NET for NOT-on-ballot retirees only
        (first-deploy backlog / stragglers), so a balloted player who missed the
        cap or was dropped is never back-doored in.
        """
        exclude = excludePlayerIds or set()
        seen: set = set()
        candidates = []
        for player in [*self.newlyRetiredPlayers, *self.retiredPlayers]:
            pid = getattr(player, 'id', None)
            if pid in seen or pid in exclude or getattr(player, 'is_hof', False):
                continue
            seen.add(pid)
            candidates.append(player)

        inducted = []
        for player in candidates:
            pts, breakdown = self._computeHofPoints(player)
            if pts < self.HOF_INDUCT_THRESHOLD:
                logger.debug(
                    f"HoF: {player.name} retires with {pts}pts — below threshold ({breakdown})"
                )
                continue

            self.hallOfFame.append(player)
            player.is_hof = True
            # Stamp the induction class (the just-ended season). Guarded so a
            # missing season manager never blocks the induction itself.
            try:
                sm = self.serviceContainer.getService('season_manager')
                if sm and getattr(sm, 'currentSeason', None) is not None:
                    player.hof_season = sm.currentSeason.seasonNumber
            except Exception:
                pass
            inducted.append(player)
            logger.info(
                f"HoF induction: {player.name} ({pts}pts) — {breakdown}"
            )

            seasonManager = self.serviceContainer.getService('season_manager')
            if seasonManager and seasonManager.currentSeason and hasattr(seasonManager.currentSeason, 'leagueHighlights'):
                highlight = {
                    'event': {
                        'text': f'{player.name} has been inducted into the Floosball Hall of Fame'
                    }
                }
                seasonManager.currentSeason.leagueHighlights.insert(0, highlight)
                if hasattr(seasonManager, '_recordOffseasonEvent'):
                    seasonManager._recordOffseasonEvent(
                        'hof_induction', player=player,
                        teamName=getattr(player, 'previousTeam', None), detail=f"{pts} pts")

        self.newlyRetiredPlayers.clear()

        # Persist immediately so the is_hof flag (and career awards) reach the
        # DB this offseason. The HoF UI reads is_hof, and there's otherwise no
        # guaranteed player save between here and the next season's games, so
        # without this a restart could drop the inductions from storage.
        if inducted:
            try:
                self.savePlayerData()
            except Exception as e:
                logger.error(f"Failed to persist Hall of Fame inductions: {e}")
    
    def calculatePerformanceRatings(self, currentWeek: int) -> None:
        """
        Complete Performance Rating System that dynamically adjusts player ratings based on weekly performance.
        Uses percentile-based comparisons and weighted scoring across all positions.
        Replaces the original getPerformanceRating(week) function.
        """
        import numpy as np
        from scipy import stats
        import floosball_methods as FloosMethods
        
        logger.info(f"Calculating performance ratings for week {currentWeek}")
        
        baseAdjustmentFactor = 0.2
        gameFactor = min(1, currentWeek / 4)
        effectiveAdjustment = baseAdjustmentFactor * gameFactor
        
        # QB Performance Rating System
        activeQbsWithStats = [qb for qb in self.activeQbs if qb.seasonStatsDict.get('passing', {}).get('yards', 0) > 0]
        if activeQbsWithStats:
            def _pass(qb, key):
                return qb.seasonStatsDict.get('passing', {}).get(key, 0)

            qbStats = {
                "passComp":  [_pass(qb, 'compPerc') for qb in activeQbsWithStats],
                "passYards": [_pass(qb, 'yards')    for qb in activeQbsWithStats],
                "tds":       [_pass(qb, 'tds')      for qb in activeQbsWithStats],
                "ints":      [_pass(qb, 'ints')     for qb in activeQbsWithStats],
            }

            for qb in activeQbsWithStats:
                compPerc  = _pass(qb, 'compPerc')
                passYards = _pass(qb, 'yards')
                tds       = _pass(qb, 'tds')
                ints      = _pass(qb, 'ints')
                
                passCompPercRating = stats.percentileofscore(qbStats["passComp"], compPerc, 'rank')
                passYardsRating = stats.percentileofscore(qbStats["passYards"], passYards, 'rank')
                tdsRating = stats.percentileofscore(qbStats["tds"], tds, 'rank')
                intsRating = 100 - stats.percentileofscore(qbStats["ints"], ints, 'rank')
                
                # QB Weighted Scoring: Completion % (1.2), Passing Yards (1.0), TDs (1.0), INTs (0.8)
                weightedScore = round(((passCompPercRating * 1.2) + (passYardsRating * 1.0) + (tdsRating * 1.0) + (intsRating * 0.8)) / 4)
                
                qb.seasonPerformanceRating = round(FloosMethods.scaleValue(weightedScore, 60, 100, 0, 100))
            
            # QB Base Skill vs Performance Comparison
            qbBaseSkills = [p.attributes.skillRating for p in activeQbsWithStats]
            qbPerformances = [p.seasonPerformanceRating for p in activeQbsWithStats]
            
            if qbBaseSkills and qbPerformances:
                qbBaseSkillPercentiles = [stats.percentileofscore(qbBaseSkills, x) for x in qbBaseSkills]
                qbPerformancePercentiles = [stats.percentileofscore(qbPerformances, x) for x in qbPerformances]
                
                for i, player in enumerate(activeQbsWithStats):
                    percentileDifference = qbPerformancePercentiles[i] - qbBaseSkillPercentiles[i]
                    adjustment = effectiveAdjustment * percentileDifference
                    # seasonPerformanceRating stored for MVP/analysis only;
                    # playerRating stays fixed for the season
        
        # RB Performance Rating System
        activeRbsWithStats = [rb for rb in self.activeRbs if rb.seasonStatsDict.get('rushing', {}).get('yards', 0) > 0]
        
        if activeRbsWithStats:
            def _rush(rb, key):
                return rb.seasonStatsDict.get('rushing', {}).get(key, 0)

            rbStats = {
                "ypc":       [_rush(rb, 'ypc')         for rb in activeRbsWithStats],
                "rushYards": [_rush(rb, 'yards')        for rb in activeRbsWithStats],
                "tds":       [_rush(rb, 'tds')          for rb in activeRbsWithStats],
                "fumbles":   [_rush(rb, 'fumblesLost')  for rb in activeRbsWithStats],
            }

            for rb in activeRbsWithStats:
                ypc       = _rush(rb, 'ypc')
                rushYards = _rush(rb, 'yards')
                tds       = _rush(rb, 'tds')
                fumbles   = _rush(rb, 'fumblesLost')
                
                ypcRating = stats.percentileofscore(rbStats["ypc"], ypc, 'rank')
                rushYardsRating = stats.percentileofscore(rbStats["rushYards"], rushYards, 'rank')
                tdsRating = stats.percentileofscore(rbStats["tds"], tds, 'rank')
                fumblesRating = 100 - stats.percentileofscore(rbStats["fumbles"], fumbles, 'rank')
                
                # RB Weighted Scoring: YPC (1.2), Rushing Yards (1.2), TDs (1.0), Fumbles (0.6)
                weightedScore = ((ypcRating * 1.2) + (rushYardsRating * 1.2) + (tdsRating * 1.0) + (fumblesRating * 0.6)) / 4
                
                rb.seasonPerformanceRating = round(FloosMethods.scaleValue(weightedScore, 60, 100, 0, 100))
            
            # RB Base Skill vs Performance Comparison
            rbBaseSkills = [p.attributes.skillRating for p in activeRbsWithStats]
            rbPerformances = [p.seasonPerformanceRating for p in activeRbsWithStats]
            
            if rbBaseSkills and rbPerformances:
                rbBaseSkillPercentiles = [stats.percentileofscore(rbBaseSkills, x) for x in rbBaseSkills]
                rbPerformancePercentiles = [stats.percentileofscore(rbPerformances, x) for x in rbPerformances]
                
                for i, player in enumerate(activeRbsWithStats):
                    percentileDifference = rbPerformancePercentiles[i] - rbBaseSkillPercentiles[i]
                    adjustment = effectiveAdjustment * percentileDifference
                    # seasonPerformanceRating stored for MVP/analysis only;
                    # playerRating stays fixed for the season
        
        # WR Performance Rating System
        activeWrsWithStats = [wr for wr in self.activeWrs if wr.seasonStatsDict.get('receiving', {}).get('yards', 0) > 0]
        
        if activeWrsWithStats:
            def _rcv(wr, key):
                return wr.seasonStatsDict.get('receiving', {}).get(key, 0)

            wrStats = {
                "receptions": [_rcv(wr, 'receptions') for wr in activeWrsWithStats],
                "drops":      [_rcv(wr, 'drops')      for wr in activeWrsWithStats],
                "rcvPerc":    [_rcv(wr, 'rcvPerc')    for wr in activeWrsWithStats],
                "rcvYards":   [_rcv(wr, 'yards')      for wr in activeWrsWithStats],
                "ypr":        [_rcv(wr, 'ypr')        for wr in activeWrsWithStats],
                "yac":        [_rcv(wr, 'yac')        for wr in activeWrsWithStats],
                "tds":        [_rcv(wr, 'tds')        for wr in activeWrsWithStats],
            }

            for wr in activeWrsWithStats:
                receptions = _rcv(wr, 'receptions')
                drops      = _rcv(wr, 'drops')
                rcvPerc    = _rcv(wr, 'rcvPerc')
                rcvYards   = _rcv(wr, 'yards')
                ypr        = _rcv(wr, 'ypr')
                yac        = _rcv(wr, 'yac')
                tds        = _rcv(wr, 'tds')
                
                recRating = stats.percentileofscore(wrStats["receptions"], receptions, 'rank')
                dropsRating = 100 - stats.percentileofscore(wrStats["drops"], drops, 'rank')
                rcvPercRating = stats.percentileofscore(wrStats["rcvPerc"], rcvPerc, 'rank')
                rcvYardsRating = stats.percentileofscore(wrStats["rcvYards"], rcvYards, 'rank')
                yprRating = stats.percentileofscore(wrStats["ypr"], ypr, 'rank')
                yacRating = stats.percentileofscore(wrStats["yac"], yac, 'rank')
                tdsRating = stats.percentileofscore(wrStats["tds"], tds, 'rank')
                
                # WR 7-Factor Weighted Scoring
                weightedScore = ((recRating * 0.8) + (dropsRating * 1.2) + (rcvPercRating * 1.4) + 
                               (rcvYardsRating * 1.0) + (yprRating * 1.0) + (yacRating * 1.0) + (tdsRating * 0.6)) / 7
                
                wr.seasonPerformanceRating = round(FloosMethods.scaleValue(weightedScore, 60, 100, 0, 100))
            
            # WR Base Skill vs Performance Comparison
            wrBaseSkills = [p.attributes.skillRating for p in activeWrsWithStats]
            wrPerformances = [p.seasonPerformanceRating for p in activeWrsWithStats]
            
            if wrBaseSkills and wrPerformances:
                wrBaseSkillPercentiles = [stats.percentileofscore(wrBaseSkills, x) for x in wrBaseSkills]
                wrPerformancePercentiles = [stats.percentileofscore(wrPerformances, x) for x in wrPerformances]
                
                for i, player in enumerate(activeWrsWithStats):
                    percentileDifference = wrPerformancePercentiles[i] - wrBaseSkillPercentiles[i]
                    adjustment = effectiveAdjustment * percentileDifference
                    # seasonPerformanceRating stored for MVP/analysis only;
                    # playerRating stays fixed for the season
        
        # TE Performance Rating System (Same as WR but separate calculations)
        activeTesWithStats = [te for te in self.activeTes if te.seasonStatsDict.get('receiving', {}).get('yards', 0) > 0]
        
        if activeTesWithStats:
            def _te(te, key):
                return te.seasonStatsDict.get('receiving', {}).get(key, 0)

            teStats = {
                "receptions": [_te(te, 'receptions') for te in activeTesWithStats],
                "drops":      [_te(te, 'drops')      for te in activeTesWithStats],
                "rcvPerc":    [_te(te, 'rcvPerc')    for te in activeTesWithStats],
                "rcvYards":   [_te(te, 'yards')      for te in activeTesWithStats],
                "ypr":        [_te(te, 'ypr')        for te in activeTesWithStats],
                "yac":        [_te(te, 'yac')        for te in activeTesWithStats],
                "tds":        [_te(te, 'tds')        for te in activeTesWithStats],
            }

            for te in activeTesWithStats:
                receptions = _te(te, 'receptions')
                drops      = _te(te, 'drops')
                rcvPerc    = _te(te, 'rcvPerc')
                rcvYards   = _te(te, 'yards')
                ypr        = _te(te, 'ypr')
                yac        = _te(te, 'yac')
                tds        = _te(te, 'tds')
                
                recRating = stats.percentileofscore(teStats["receptions"], receptions, 'rank')
                dropsRating = 100 - stats.percentileofscore(teStats["drops"], drops, 'rank')
                rcvPercRating = stats.percentileofscore(teStats["rcvPerc"], rcvPerc, 'rank')
                rcvYardsRating = stats.percentileofscore(teStats["rcvYards"], rcvYards, 'rank')
                yprRating = stats.percentileofscore(teStats["ypr"], ypr, 'rank')
                yacRating = stats.percentileofscore(teStats["yac"], yac, 'rank')
                tdsRating = stats.percentileofscore(teStats["tds"], tds, 'rank')
                
                # TE 7-Factor Weighted Scoring: Same as WR
                weightedScore = ((recRating * 0.8) + (dropsRating * 1.2) + (rcvPercRating * 1.4) + 
                               (rcvYardsRating * 1.0) + (yprRating * 1.0) + (yacRating * 1.0) + (tdsRating * 0.6)) / 7
                
                te.seasonPerformanceRating = round(FloosMethods.scaleValue(weightedScore, 60, 100, 0, 100))
            
            # TE Base Skill vs Performance Comparison
            teBaseSkills = [p.attributes.skillRating for p in activeTesWithStats]
            tePerformances = [p.seasonPerformanceRating for p in activeTesWithStats]
            
            if teBaseSkills and tePerformances:
                teBaseSkillPercentiles = [stats.percentileofscore(teBaseSkills, x) for x in teBaseSkills]
                tePerformancePercentiles = [stats.percentileofscore(tePerformances, x) for x in tePerformances]
                
                for i, player in enumerate(activeTesWithStats):
                    percentileDifference = tePerformancePercentiles[i] - teBaseSkillPercentiles[i]
                    adjustment = effectiveAdjustment * percentileDifference
                    # seasonPerformanceRating stored for MVP/analysis only;
                    # playerRating stays fixed for the season
        
        # K (Kicker) Performance Rating System
        activeKsWithStats = [k for k in self.activeKs if k.seasonStatsDict.get('kicking', {}).get('fgs', 0) > 0]
        
        if activeKsWithStats:
            def _kick(k, key):
                return k.seasonStatsDict.get('kicking', {}).get(key, 0)

            kStats = {
                "fgPerc": [_kick(k, 'fgPerc') for k in activeKsWithStats if _kick(k, 'fgPerc') > 0],
                "fgs":    [_kick(k, 'fgs')    for k in activeKsWithStats],
                "fgAvg":  [_kick(k, 'fgAvg') for k in activeKsWithStats if _kick(k, 'fgAvg') > 0],
            }

            for k in activeKsWithStats:
                fgPerc = _kick(k, 'fgPerc')
                fgs    = _kick(k, 'fgs')
                fgAvg  = _kick(k, 'fgAvg')
                
                if fgPerc > 0 and fgAvg > 0:
                    fgPercRating = stats.percentileofscore(kStats["fgPerc"], fgPerc, 'rank')
                    fgsRating = stats.percentileofscore(kStats["fgs"], fgs, 'rank')
                    fgAvgRating = stats.percentileofscore(kStats["fgAvg"], fgAvg, 'rank')
                    
                    # K Weighted Scoring: FG% (1.3), FGs Made (0.7), FG Average (1.0)
                    weightedScore = ((fgPercRating * 1.3) + (fgsRating * 0.7) + (fgAvgRating * 1.0)) / 3
                    
                    k.seasonPerformanceRating = round(FloosMethods.scaleValue(weightedScore, 60, 100, 0, 100))
            
            # K Base Skill vs Performance Comparison
            kBaseSkills = [p.attributes.skillRating for p in activeKsWithStats]
            kPerformances = [p.seasonPerformanceRating for p in activeKsWithStats]
            
            if kBaseSkills and kPerformances:
                kBaseSkillPercentiles = [stats.percentileofscore(kBaseSkills, x) for x in kBaseSkills]
                kPerformancePercentiles = [stats.percentileofscore(kPerformances, x) for x in kPerformances]
                
                for i, player in enumerate(activeKsWithStats):
                    percentileDifference = kPerformancePercentiles[i] - kBaseSkillPercentiles[i]
                    adjustment = effectiveAdjustment * percentileDifference
                    # seasonPerformanceRating stored for MVP/analysis only;
                    # playerRating stays fixed for the season

        # ── Defensive + overall (two-way) performance ratings ──
        # Parallel to the offensive ratings above: a player's defensive production
        # (DEF_BOX_WEIGHTS composite) percentile WITHIN their defensive group →
        # 60-100, then an offense-dominant OVERALL composite. The overall rating is
        # what MVP/All-Pro rank on (perfZ) and what the UI shows as the player's
        # season performance; the offensive rating stays separate for the offensive
        # over/under metric.
        from constants import DEF_BOX_WEIGHTS, PERF_OFFENSE_WEIGHT, PERF_DEFENSE_WEIGHT
        defByGroup: Dict[str, list] = {}
        seenDef = set()
        for players in (self.activeQbs, self.activeRbs, self.activeWrs, self.activeTes):
            for p in players:
                if p.id in seenDef:
                    continue
                dpos = getattr(p, 'defensivePosition', None)
                if dpos is None:
                    continue
                seenDef.add(p.id)
                grp = dpos.name if hasattr(dpos, 'name') else str(dpos)
                box = (p.seasonStatsDict.get('defense', {}) or {}) if hasattr(p, 'seasonStatsDict') else {}
                w = DEF_BOX_WEIGHTS.get(grp, {})
                boxScore = sum(wt * float(box.get(k, 0) or 0) for k, wt in w.items())
                defByGroup.setdefault(grp, []).append((p, boxScore))
        for grp, members in defByGroup.items():
            grpScores = [b for _, b in members]
            for p, b in members:
                pctRank = stats.percentileofscore(grpScores, b, 'rank')
                p.seasonDefensivePerformanceRating = round(FloosMethods.scaleValue(pctRank, 60, 100, 0, 100))
        # Overall composite (offense-dominant); offense-only for kickers / no defense.
        for players in (self.activeQbs, self.activeRbs, self.activeWrs, self.activeTes, self.activeKs):
            for p in players:
                offR = getattr(p, 'seasonPerformanceRating', 0) or 0
                defR = getattr(p, 'seasonDefensivePerformanceRating', 0) or 0
                p.seasonOverallPerformanceRating = (
                    round(PERF_OFFENSE_WEIGHT * offR + PERF_DEFENSE_WEIGHT * defR)
                    if (offR and defR) else (offR or defR)
                )

        # Sort players by performance ratings
        self.activeQbs.sort(key=lambda player: getattr(player, 'seasonPerformanceRating', 0), reverse=True)
        self.activeRbs.sort(key=lambda player: getattr(player, 'seasonPerformanceRating', 0), reverse=True)
        self.activeWrs.sort(key=lambda player: getattr(player, 'seasonPerformanceRating', 0), reverse=True)
        self.activeTes.sort(key=lambda player: getattr(player, 'seasonPerformanceRating', 0), reverse=True)
        self.activeKs.sort(key=lambda player: getattr(player, 'seasonPerformanceRating', 0), reverse=True)
        
        logger.info(f"Performance ratings calculated for week {currentWeek}")

    def calculateGamePerformanceRatings(self, gamePlayerStatsList) -> Dict[int, float]:
        """Calculate per-game performance ratings using the same weighted formulas
        as calculatePerformanceRatings, but from single-game stats (GamePlayerStats rows).

        Args:
            gamePlayerStatsList: list of GamePlayerStats ORM rows for the current week

        Returns:
            Dict mapping playerId → gamePerformanceRating (0–100 scale)
        """
        import numpy as np
        from scipy import stats as scipyStats
        import floosball_methods as FloosMethods

        # Build position lookup from active players
        positionMap = {}
        for p in self.activePlayers:
            pos = getattr(p, 'position', None)
            positionMap[p.id] = pos.value if pos else 0

        # Group per-game stats by position
        qbRows = []
        rbRows = []
        wrRows = []
        teRows = []
        kRows = []

        for gps in gamePlayerStatsList:
            posId = positionMap.get(gps.player_id, 0)
            if posId == 1:
                qbRows.append(gps)
            elif posId == 2:
                rbRows.append(gps)
            elif posId == 3:
                wrRows.append(gps)
            elif posId == 4:
                teRows.append(gps)
            elif posId == 5:
                kRows.append(gps)

        ratings = {}

        # QB game ratings
        qbWithStats = [r for r in qbRows if (r.passing_stats or {}).get('yards', 0) > 0]
        if qbWithStats:
            compPercs = [(r.passing_stats or {}).get('compPerc', 0) for r in qbWithStats]
            passYards = [(r.passing_stats or {}).get('yards', 0) for r in qbWithStats]
            tds = [(r.passing_stats or {}).get('tds', 0) for r in qbWithStats]
            ints = [(r.passing_stats or {}).get('ints', 0) for r in qbWithStats]

            for r in qbWithStats:
                cp = (r.passing_stats or {}).get('compPerc', 0)
                py = (r.passing_stats or {}).get('yards', 0)
                td = (r.passing_stats or {}).get('tds', 0)
                intVal = (r.passing_stats or {}).get('ints', 0)

                cpR = scipyStats.percentileofscore(compPercs, cp, 'rank')
                pyR = scipyStats.percentileofscore(passYards, py, 'rank')
                tdR = scipyStats.percentileofscore(tds, td, 'rank')
                intR = 100 - scipyStats.percentileofscore(ints, intVal, 'rank')

                weightedScore = round(((cpR * 1.2) + (pyR * 1.0) + (tdR * 1.0) + (intR * 0.8)) / 4)
                ratings[r.player_id] = round(FloosMethods.scaleValue(weightedScore, 60, 100, 0, 100))

        # RB game ratings
        rbWithStats = [r for r in rbRows if (r.rushing_stats or {}).get('yards', 0) > 0]
        if rbWithStats:
            ypcs = [(r.rushing_stats or {}).get('ypc', 0) for r in rbWithStats]
            rushYards = [(r.rushing_stats or {}).get('yards', 0) for r in rbWithStats]
            tds = [(r.rushing_stats or {}).get('tds', 0) for r in rbWithStats]
            fumbles = [(r.rushing_stats or {}).get('fumblesLost', 0) for r in rbWithStats]

            for r in rbWithStats:
                ypc = (r.rushing_stats or {}).get('ypc', 0)
                ry = (r.rushing_stats or {}).get('yards', 0)
                td = (r.rushing_stats or {}).get('tds', 0)
                fum = (r.rushing_stats or {}).get('fumblesLost', 0)

                ypcR = scipyStats.percentileofscore(ypcs, ypc, 'rank')
                ryR = scipyStats.percentileofscore(rushYards, ry, 'rank')
                tdR = scipyStats.percentileofscore(tds, td, 'rank')
                fumR = 100 - scipyStats.percentileofscore(fumbles, fum, 'rank')

                weightedScore = ((ypcR * 1.2) + (ryR * 1.2) + (tdR * 1.0) + (fumR * 0.6)) / 4
                ratings[r.player_id] = round(FloosMethods.scaleValue(weightedScore, 60, 100, 0, 100))

        # WR game ratings
        wrWithStats = [r for r in wrRows if (r.receiving_stats or {}).get('yards', 0) > 0]
        if wrWithStats:
            recs = [(r.receiving_stats or {}).get('receptions', 0) for r in wrWithStats]
            drops = [(r.receiving_stats or {}).get('drops', 0) for r in wrWithStats]
            rcvPercs = [(r.receiving_stats or {}).get('rcvPerc', 0) for r in wrWithStats]
            rcvYards = [(r.receiving_stats or {}).get('yards', 0) for r in wrWithStats]
            yprs = [(r.receiving_stats or {}).get('ypr', 0) for r in wrWithStats]
            yacs = [(r.receiving_stats or {}).get('yac', 0) for r in wrWithStats]
            tds = [(r.receiving_stats or {}).get('tds', 0) for r in wrWithStats]

            for r in wrWithStats:
                rec = (r.receiving_stats or {}).get('receptions', 0)
                drp = (r.receiving_stats or {}).get('drops', 0)
                rcp = (r.receiving_stats or {}).get('rcvPerc', 0)
                ry = (r.receiving_stats or {}).get('yards', 0)
                ypr = (r.receiving_stats or {}).get('ypr', 0)
                yac = (r.receiving_stats or {}).get('yac', 0)
                td = (r.receiving_stats or {}).get('tds', 0)

                recR = scipyStats.percentileofscore(recs, rec, 'rank')
                drpR = 100 - scipyStats.percentileofscore(drops, drp, 'rank')
                rcpR = scipyStats.percentileofscore(rcvPercs, rcp, 'rank')
                ryR = scipyStats.percentileofscore(rcvYards, ry, 'rank')
                yprR = scipyStats.percentileofscore(yprs, ypr, 'rank')
                yacR = scipyStats.percentileofscore(yacs, yac, 'rank')
                tdR = scipyStats.percentileofscore(tds, td, 'rank')

                weightedScore = ((recR * 0.8) + (drpR * 1.2) + (rcpR * 1.4) +
                                 (ryR * 1.0) + (yprR * 1.0) + (yacR * 1.0) + (tdR * 0.6)) / 7
                ratings[r.player_id] = round(FloosMethods.scaleValue(weightedScore, 60, 100, 0, 100))

        # TE game ratings (same formula as WR)
        teWithStats = [r for r in teRows if (r.receiving_stats or {}).get('yards', 0) > 0]
        if teWithStats:
            recs = [(r.receiving_stats or {}).get('receptions', 0) for r in teWithStats]
            drops = [(r.receiving_stats or {}).get('drops', 0) for r in teWithStats]
            rcvPercs = [(r.receiving_stats or {}).get('rcvPerc', 0) for r in teWithStats]
            rcvYards = [(r.receiving_stats or {}).get('yards', 0) for r in teWithStats]
            yprs = [(r.receiving_stats or {}).get('ypr', 0) for r in teWithStats]
            yacs = [(r.receiving_stats or {}).get('yac', 0) for r in teWithStats]
            tds = [(r.receiving_stats or {}).get('tds', 0) for r in teWithStats]

            for r in teWithStats:
                rec = (r.receiving_stats or {}).get('receptions', 0)
                drp = (r.receiving_stats or {}).get('drops', 0)
                rcp = (r.receiving_stats or {}).get('rcvPerc', 0)
                ry = (r.receiving_stats or {}).get('yards', 0)
                ypr = (r.receiving_stats or {}).get('ypr', 0)
                yac = (r.receiving_stats or {}).get('yac', 0)
                td = (r.receiving_stats or {}).get('tds', 0)

                recR = scipyStats.percentileofscore(recs, rec, 'rank')
                drpR = 100 - scipyStats.percentileofscore(drops, drp, 'rank')
                rcpR = scipyStats.percentileofscore(rcvPercs, rcp, 'rank')
                ryR = scipyStats.percentileofscore(rcvYards, ry, 'rank')
                yprR = scipyStats.percentileofscore(yprs, ypr, 'rank')
                yacR = scipyStats.percentileofscore(yacs, yac, 'rank')
                tdR = scipyStats.percentileofscore(tds, td, 'rank')

                weightedScore = ((recR * 0.8) + (drpR * 1.2) + (rcpR * 1.4) +
                                 (ryR * 1.0) + (yprR * 1.0) + (yacR * 1.0) + (tdR * 0.6)) / 7
                ratings[r.player_id] = round(FloosMethods.scaleValue(weightedScore, 60, 100, 0, 100))

        # K game ratings
        kWithStats = [r for r in kRows if (r.kicking_stats or {}).get('fgs', 0) > 0]
        if kWithStats:
            fgPercs = [(r.kicking_stats or {}).get('fgPerc', 0) for r in kWithStats if (r.kicking_stats or {}).get('fgPerc', 0) > 0]
            fgCounts = [(r.kicking_stats or {}).get('fgs', 0) for r in kWithStats]
            fgAvgs = [(r.kicking_stats or {}).get('fgAvg', 0) for r in kWithStats if (r.kicking_stats or {}).get('fgAvg', 0) > 0]

            for r in kWithStats:
                fgPerc = (r.kicking_stats or {}).get('fgPerc', 0)
                fgs = (r.kicking_stats or {}).get('fgs', 0)
                fgAvg = (r.kicking_stats or {}).get('fgAvg', 0)

                if fgPerc > 0 and fgAvg > 0 and fgPercs and fgAvgs:
                    fgPercR = scipyStats.percentileofscore(fgPercs, fgPerc, 'rank')
                    fgsR = scipyStats.percentileofscore(fgCounts, fgs, 'rank')
                    fgAvgR = scipyStats.percentileofscore(fgAvgs, fgAvg, 'rank')

                    weightedScore = ((fgPercR * 1.3) + (fgsR * 0.7) + (fgAvgR * 1.0)) / 3
                    ratings[r.player_id] = round(FloosMethods.scaleValue(weightedScore, 60, 100, 0, 100))

        return ratings

    def _computeMvpCandidates(self) -> List[Dict[str, Any]]:
        """Compute the MVP value metric (two-way), a flat z-score blend:
          mvpScore = MVP_PERF_WEIGHT*perfZ + MVP_WPA_WEIGHT*offenseWpaRateZ
                     + MVP_DEF_WPA_WEIGHT*defWpaZ
        where perfZ is the z (pooled-std, vs position mean) of the player's OVERALL
        performance rating — a composite of their offensive AND defensive PRODUCTION
        (seasonOverallPerformanceRating). So defensive production is already in perfZ;
        the only standalone defensive term is the individual defensive clutch WPA
        (defWpaZ, from _computeDefValues). offenseWpaRate is per-snap so game volume
        doesn't inflate it. Both WPA terms are per-player (offense→ball-handler,
        defense→playmaker), so neither clusters the way the old team-shared defensive
        WPA did. Defense is secondary (30% of the perf composite + a small WPA term)
        so offense leads but a two-way / standout defender climbs. Sorted by mvpScore.
        """
        import numpy as np
        from api_response_builders import PlayerResponseBuilder
        from constants import MVP_PERF_WEIGHT, MVP_WPA_WEIGHT, MVP_DEF_WPA_WEIGHT

        def wpaRate(p):
            # Per-snap offensive WPA — a rate, not an accumulated volume, so clutch
            # play is rewarded without leverage/volume bias.
            snaps = int(getattr(p, 'seasonWpaSnaps', 0) or 0)
            return float(getattr(p, 'seasonWpa', 0.0)) / snaps if snaps > 0 else 0.0

        positionGroups = {
            'QB': self.activeQbs,
            'RB': self.activeRbs,
            'WR': self.activeWrs,
            'TE': self.activeTes,
            'K': self.activeKs,
        }
        defValues = self._computeDefValues()

        # First pass: eligible players + per-position rating & offensive-WPA means
        positionData = {}  # position -> (eligible, ratingMean, wpaMean)
        allRatings = []
        allWpas = []
        for position, players in positionGroups.items():
            eligible = [p for p in players
                        if getattr(p, 'seasonOverallPerformanceRating', 0) > 0
                        and hasattr(p, 'team') and p.team != 'Free Agent']
            if len(eligible) < 2:
                continue
            ratings = [p.seasonOverallPerformanceRating for p in eligible]
            wpas = [wpaRate(p) for p in eligible]
            positionData[position] = (eligible, float(np.mean(ratings)), float(np.mean(wpas)))
            allRatings.extend(ratings)
            allWpas.extend(wpas)

        if not allRatings:
            return []

        # Pooled stds across all positions — same yardstick for everyone
        pooledStd = float(np.std(allRatings))
        if pooledStd == 0:
            return []
        pooledWpaStd = float(np.std(allWpas)) or 1.0

        candidates = []
        for position, (eligible, posMean, posWpaMean) in positionData.items():
            for player in eligible:
                # perfZ is the two-way production composite (offense + defense box,
                # via seasonOverallPerformanceRating). offenseScore = that + the
                # offensive clutch WPA. defWpaZ adds the defensive clutch WPA (the
                # only defensive term not already inside perfZ). No box defValue —
                # defensive production lives in perfZ now.
                perfZ = (player.seasonOverallPerformanceRating - posMean) / pooledStd
                wpaZ = (wpaRate(player) - posWpaMean) / pooledWpaStd
                offenseScore = MVP_PERF_WEIGHT * perfZ + MVP_WPA_WEIGHT * wpaZ
                defWpaZ = defValues.get(player.id, {}).get('defWpaZ', 0.0)
                mvpScore = offenseScore + MVP_DEF_WPA_WEIGHT * defWpaZ
                hasTeamObj = hasattr(player.team, 'name')
                candidates.append({
                    'player': player,
                    'name': player.name,
                    'id': player.id,
                    'position': position,
                    'team': player.team.name if hasTeamObj else (player.team if isinstance(player.team, str) else 'FA'),
                    'teamAbbr': getattr(player.team, 'abbr', '') if hasTeamObj else '',
                    'teamColor': getattr(player.team, 'color', '#334155') if hasTeamObj else '#334155',
                    'teamId': player.team.id if hasTeamObj else None,
                    'seasonPerformanceRating': getattr(player, 'seasonOverallPerformanceRating', player.seasonPerformanceRating),
                    'offensivePerformanceRating': player.seasonPerformanceRating,
                    'defensivePerformanceRating': getattr(player, 'seasonDefensivePerformanceRating', 0),
                    'zScore': round(perfZ, 3),            # overall production z (logged by _selectSeasonMVP + frontend)
                    'wpaScore': round(wpaZ, 3),
                    'offenseScore': round(offenseScore, 3),
                    'defValue': round(defWpaZ, 3),        # defensive clutch WPA z (defensive production is in zScore now)
                    'mvpScore': round(mvpScore, 3),
                    'seasonWpa': round(float(getattr(player, 'seasonWpa', 0.0)), 2),
                    'gamesPlayed': getattr(player, 'gamesPlayed', 0),
                    'fantasyPoints': player.seasonStatsDict.get('fantasyPoints', 0),
                    'ratingStars': PlayerResponseBuilder.calculateStarRating(player.playerRating),
                })

        candidates.sort(key=lambda x: x['mvpScore'], reverse=True)
        # Dedup by player id — the active position lists can transiently hold a
        # player twice; keep the (already top-sorted) first occurrence.
        seen, deduped = set(), []
        for c in candidates:
            if c['id'] in seen:
                continue
            seen.add(c['id'])
            deduped.append(c)
        return deduped

    def _computeDefValues(self) -> Dict[int, Dict[str, Any]]:
        """Per-player INDIVIDUAL defensive z-scores, pooled within defensive position
        group (S/LB/CB/DE) using that group's own mean and std. Returns defBoxZ
        (position-weighted box-stat production), defWpaZ (defensive WPA, attributed
        to the playmaker — see floosball_game _attributeWpa, so it doesn't cluster),
        and defValue = defBoxZ + defWpaZ (a standalone total used for the
        defensive-candidate ranking + display). NOTE: the unified MVP no longer
        reads defValue — defensive PRODUCTION lives in seasonOverallPerformanceRating
        (perfZ) and MVP adds only defWpaZ (defensive clutch). Returns {playerId:
        {defValue, defWpaZ, defBoxZ, defGroup, seasonDefWpa, boxScore}}."""
        import numpy as np
        from constants import DEF_BOX_WEIGHTS

        # The roster's offensive players double as the defense (K excluded).
        defenders = []  # (player, group, defWpa, boxScore)
        seenDef = set()
        for players in (self.activeQbs, self.activeRbs, self.activeWrs, self.activeTes):
            for p in players:
                if p.id in seenDef:   # active lists can transiently hold a player twice
                    continue
                dpos = getattr(p, 'defensivePosition', None)
                if dpos is None:
                    continue
                if not (hasattr(p, 'team') and p.team != 'Free Agent'):
                    continue
                if int(getattr(p, 'seasonDefWpaSnaps', 0)) <= 0:
                    continue
                seenDef.add(p.id)
                grp = dpos.name if hasattr(dpos, 'name') else str(dpos)
                defWpa = float(getattr(p, 'seasonDefWpa', 0.0))
                box = (p.seasonStatsDict.get('defense', {}) or {}) if hasattr(p, 'seasonStatsDict') else {}
                w = DEF_BOX_WEIGHTS.get(grp, {})
                boxScore = sum(wt * float(box.get(k, 0) or 0) for k, wt in w.items())
                defenders.append((p, grp, defWpa, boxScore))

        if len(defenders) < 2:
            return {}

        # Z-score WITHIN each defensive group (own mean AND own std). The box-stat
        # scale differs wildly between groups (a DE's sack-weighted score dwarfs a
        # CB's INT-weighted one), so using a cross-group pooled std would collapse
        # every within-group z toward zero and make defense inert. Per-group std
        # gives each group's standout a true ~+2, comparable across groups.
        groupWpaStats, groupBoxStats = {}, {}   # grp -> (mean, std)
        for grp in set(g for _, g, _, _ in defenders):
            ds = [d for _, g, d, _ in defenders if g == grp]
            bs = [b for _, g, _, b in defenders if g == grp]
            groupWpaStats[grp] = (float(np.mean(ds)), float(np.std(ds)) or 1.0)
            groupBoxStats[grp] = (float(np.mean(bs)), float(np.std(bs)) or 1.0)

        out: Dict[int, Dict[str, Any]] = {}
        for p, grp, defWpa, boxScore in defenders:
            wMean, wStd = groupWpaStats[grp]
            bMean, bStd = groupBoxStats[grp]
            defWpaZ = (defWpa - wMean) / wStd
            defBoxZ = (boxScore - bMean) / bStd
            defValue = defBoxZ + defWpaZ   # standalone total (ranking/display); MVP uses defWpaZ + perfZ
            out[p.id] = {
                'defValue': round(defValue, 3),
                'defWpaZ': round(defWpaZ, 3),
                'defBoxZ': round(defBoxZ, 3),
                'defGroup': grp,
                'seasonDefWpa': round(defWpa, 2),
                'boxScore': round(boxScore, 1),
            }
        return out

    def _computeDefensiveCandidates(self) -> List[Dict[str, Any]]:
        """Defensive-value rankings (feed the All-Pro defense slots), sorted by defValue desc."""
        from api_response_builders import PlayerResponseBuilder
        defValues = self._computeDefValues()
        if not defValues:
            return []
        byId = {}
        for players in (self.activeQbs, self.activeRbs, self.activeWrs, self.activeTes):
            for p in players:
                byId[p.id] = p
        out = []
        for pid, dv in defValues.items():
            p = byId.get(pid)
            if p is None:
                continue
            hasTeamObj = hasattr(p.team, 'name')
            out.append({
                'player': p,
                'name': p.name,
                'id': p.id,
                'defGroup': dv['defGroup'],
                'position': p.position.name if hasattr(getattr(p, 'position', None), 'name') else None,
                'team': p.team.name if hasTeamObj else 'FA',
                'teamAbbr': getattr(p.team, 'abbr', '') if hasTeamObj else '',
                'teamColor': getattr(p.team, 'color', '#334155') if hasTeamObj else '#334155',
                'teamId': p.team.id if hasTeamObj else None,
                'defValue': dv['defValue'],
                'defWpaScore': dv['defWpaZ'],
                'defBoxScore': dv['defBoxZ'],
                'seasonDefWpa': dv['seasonDefWpa'],
                'gamesPlayed': getattr(p, 'gamesPlayed', 0),
                'ratingStars': PlayerResponseBuilder.calculateStarRating(p.playerRating),
            })
        out.sort(key=lambda x: x['defValue'], reverse=True)
        seen, deduped = set(), []
        for c in out:
            if c['id'] in seen:
                continue
            seen.add(c['id'])
            deduped.append(c)
        return deduped

    def selectAllDefense(self) -> List[Dict[str, Any]]:
        """Defensive half of the All-Pro team — top defValue per defensive group: S, LB, CB, CB, DE."""
        cands = self._computeDefensiveCandidates()
        chosen, used = [], set()
        for grp, n in [('S', 1), ('LB', 1), ('CB', 2), ('DE', 1)]:
            picks = [c for c in cands if c['defGroup'] == grp and c['id'] not in used][:n]
            for c in picks:
                used.add(c['id'])
                d = dict(c)
                d.pop('player', None)
                chosen.append(d)
        return chosen

    def selectMVP(self) -> Optional[Dict[str, Any]]:
        """Select the MVP — the candidate with the highest z-score."""
        candidates = self._computeMvpCandidates()
        if not candidates:
            return None
        mvp = dict(candidates[0])
        mvp.pop('player', None)
        return mvp

    def getMvpRankings(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get top MVP candidates ranked by z-score for the dashboard."""
        candidates = self._computeMvpCandidates()
        results = []
        for rank, c in enumerate(candidates[:limit], 1):
            entry = dict(c)
            entry.pop('player', None)
            entry['rank'] = rank
            results.append(entry)
        return results

    def getPlayerImpact(self, playerId: int) -> Optional[Dict[str, Any]]:
        """This-season impact tiers for a player's offense and defense, from the
        same pooled-z value metrics that drive MVP / All-Pro (offenseScore vs
        defValue). Returns None if the player isn't an eligible active
        contributor this season (e.g. retired / insufficient snaps)."""
        def _tier(z):
            if z is None:
                return None
            if z >= 1.0:
                return 'Elite'
            if z >= 0.3:
                return 'Strong'
            if z >= -0.3:
                return 'Average'
            return 'Quiet'
        offScore = next((c.get('offenseScore') for c in self._computeMvpCandidates()
                         if c['id'] == playerId), None)
        defVal = (self._computeDefValues().get(playerId) or {}).get('defValue')
        if offScore is None and defVal is None:
            return None
        return {
            'offenseTier': _tier(offScore), 'defenseTier': _tier(defVal),
            'offenseScore': round(offScore, 2) if offScore is not None else None,
            'defenseValue': round(defVal, 2) if defVal is not None else None,
        }

    def conductFreeAgencySimulation(self, freeAgencyOrder: List, currentSeason: int, leagueHighlights: List = None, eventLog: List = None, skipRetirements: bool = False) -> Dict[str, Any]:
        """
        Complete Free Agency Simulation System - replaces original free agency logic from offseason() function
        Multi-round system with GM skill-based evaluation, tier upgrades, and salary cap management
        """
        from random import randint, choice
        import copy
        import datetime
        
        logger.info(f"Starting free agency simulation for season {currentSeason}")
        
        # Create detailed free agency log file
        fa_log_path = f"logs/free_agency_season_{currentSeason}.log"
        try:
            import os
            os.makedirs("logs", exist_ok=True)
            fa_log = open(fa_log_path, 'w')
            fa_log.write(f"=== FREE AGENCY LOG - SEASON {currentSeason} ===\n")
            fa_log.write(f"Start Time: {datetime.datetime.now()}\n\n")
        except Exception as e:
            logger.warning(f"Could not create free agency log file: {e}")
            fa_log = None
        
        def log_fa(message):
            """Helper to log to both logger and file"""
            if fa_log:
                fa_log.write(message + "\n")
                fa_log.flush()
        
        freeAgencyDict = {}
        freeAgencyHistory = {}
        teamsComplete = 0
        
        if leagueHighlights is None:
            leagueHighlights = []
        
        # Log pre-free agency roster state
        log_fa("\n=== PRE-FREE AGENCY ROSTER STATE ===")
        teamManager = self.serviceContainer.getService('team_manager')
        teams = teamManager.teams if teamManager else []
        for team in teams:
            roster_players = [f"{pos}:{p.name if p else 'EMPTY'}" for pos, p in team.rosterDict.items()]
            log_fa(f"{team.name}: {', '.join(roster_players)}")
        
        # NOTE: Contract expirations are already handled in seasonManager._processRosteredPlayerContracts()
        # during offseason Step 2, so we don't need to call _processContractExpirations() here
        
        # Process free agent retirements and generate replacements
        # (skipped when GM Mode handles these in earlier offseason steps)
        if not skipRetirements:
            log_fa("\n=== FREE AGENT RETIREMENTS ===")
            self._processFreeAgentRetirements(currentSeason, leagueHighlights)
            log_fa("\n=== REPLACEMENT PLAYERS GENERATED ===")
            self._generateReplacementPlayers(currentSeason)
        else:
            log_fa("\n=== FA RETIREMENTS/ROOKIES: handled in earlier offseason step ===")
        
        log_fa(f"\n=== FREE AGENT POOL (Total: {len(self.freeAgents)}) ===")
        for player in sorted(self.freeAgents, key=lambda p: (p.position.value, -p.attributes.skillRating)):
            log_fa(f"  {player.position.name:3} - {player.name:30} (Skill: {player.attributes.skillRating:3}, Tier: {player.playerTier.name})")

        # Snapshot full pre-signing pool so REST endpoint can serve it during broadcast replay
        self._freeAgentSnapshot = sorted(
            [{"name": p.name, "position": p.position.name,
              "rating": round(p.playerRating, 1), "tier": p.playerTier.name}
             for p in self.freeAgents],
            key=lambda p: -p["rating"]
        )

        # Prepare free agent lists by position, sorted by skill rating
        freeAgentQbList = [p for p in self.freeAgents if p.position.value == 1]
        freeAgentRbList = [p for p in self.freeAgents if p.position.value == 2]
        freeAgentWrList = [p for p in self.freeAgents if p.position.value == 3]
        freeAgentTeList = [p for p in self.freeAgents if p.position.value == 4]
        freeAgentKList = [p for p in self.freeAgents if p.position.value == 5]
        
        # Sort by skill rating (best first)
        freeAgentQbList.sort(key=lambda p: p.attributes.skillRating, reverse=True)
        freeAgentRbList.sort(key=lambda p: p.attributes.skillRating, reverse=True)
        freeAgentWrList.sort(key=lambda p: p.attributes.skillRating, reverse=True)
        freeAgentTeList.sort(key=lambda p: p.attributes.skillRating, reverse=True)
        freeAgentKList.sort(key=lambda p: p.attributes.skillRating, reverse=True)
        
        # Get teams from service container
        teamManager = self.serviceContainer.getService('team_manager')
        teams = teamManager.teams if teamManager else []

        # Append any team missing from the draft order (short persisted faOrder on
        # resume — see freeAgencyPickGenerator) so every roster gets drafted and
        # the completion loop can actually finish.
        if teams:
            orderIds = {getattr(t, 'id', None) for t in freeAgencyOrder}
            missing = [t for t in teams if getattr(t, 'id', None) not in orderIds]
            if missing:
                logger.warning(
                    f"FA draft order was missing {len(missing)} team(s); appending: "
                    f"{[t.name for t in missing]}"
                )
                freeAgencyOrder = list(freeAgencyOrder) + missing

        if not teams:
            logger.error("No teams available for free agency!")
            return freeAgencyDict
        
        # Initialize team completion status
        for team in teams:
            team.freeAgencyComplete = False

        logger.info(f"Free agency starting with {len(self.freeAgents)} free agents and {len(teams)} teams")

        # GM directives: {teamId: [playerId, ...]} — populated by GM Mode sign_fa votes
        gmDirectives = getattr(self, '_gmFaDirectives', {})

        # DIRECTIVE PHASE: Honor GM directives first (one pass per team)
        freeAgentLists = {
            'qb': freeAgentQbList, 'rb': freeAgentRbList,
            'wr1': freeAgentWrList, 'wr2': freeAgentWrList,
            'te': freeAgentTeList, 'k': freeAgentKList,
        }
        for team in freeAgencyOrder:
            directives = gmDirectives.get(getattr(team, 'id', None), [])
            for targetId in directives:
                # Find the targeted player in the FA pool
                targetPlayer = None
                targetListKey = None
                for lKey, faList in freeAgentLists.items():
                    for p in faList:
                        if p.id == targetId:
                            targetPlayer = p
                            targetListKey = lKey
                            break
                    if targetPlayer:
                        break
                if not targetPlayer:
                    continue
                # Don't re-sign a player this team just released this offseason
                # (cut by fan vote, or expired and not kept) even if fans ranked
                # them on the FA ballot.
                if self._leftThisTeamThisOffseason(targetPlayer, team):
                    continue
                # Find open roster slot matching player's position
                openSlot = self._findOpenSlotForPosition(team, targetPlayer.position.value)
                if not openSlot:
                    continue
                # Sign the player
                self._signPlayer(team, targetPlayer, openSlot, freeAgentLists[targetListKey],
                                 freeAgencyDict, leagueHighlights, eventLog, allFaLists=freeAgentLists)
                log_fa(f"  GM DIRECTIVE: {team.name} signs {targetPlayer.name} at {openSlot}")

        # FILL PHASE: Multi-round fill for remaining open roster spots
        teamsComplete = 0
        roundNum = 0
        maxRounds = 100  # Safety valve to prevent infinite loops

        while teamsComplete < len(freeAgencyOrder):
            teamsComplete = 0  # Reset counter each round - original recounts each iteration!
            roundNum += 1

            if roundNum > maxRounds:
                logger.warning(f"Free agency exceeded {maxRounds} rounds, ending simulation")
                # Mark all remaining teams as complete
                for team in teams:
                    if not team.freeAgencyComplete:
                        openPos = [k for k, v in team.rosterDict.items() if v is None]
                        logger.warning(f"{team.name} forced complete with open positions: {openPos}")
                        team.freeAgencyComplete = True
                break

            for team in freeAgencyOrder:
                # Count teams that are already complete
                if team.freeAgencyComplete:
                    teamsComplete += 1
                    continue

                # Attempt to fill ONE open roster spot
                # Returns True if roster complete, False if not complete (has open positions)
                rosterComplete = self._attemptRosterFill(
                    team, teams, freeAgentQbList, freeAgentRbList, freeAgentWrList,
                    freeAgentTeList, freeAgentKList, freeAgencyDict, leagueHighlights,
                    eventLog=eventLog
                )

                if rosterComplete:
                    # No open positions - team is complete
                    teamsComplete += 1
                    team.freeAgencyComplete = True
                    if eventLog is not None:
                        teamAbbr = getattr(team, 'abbr', team.name[:3].upper())
                        eventLog.append({'type': 'team_complete', 'team': team.name, 'teamAbbr': teamAbbr})
        
        # Reset all teams' free agency complete status for next season
        for team in teams:
            team.freeAgencyComplete = False
        
        # Ensure all remaining free agents have team set to 'Free Agent'
        for player in self.freeAgents:
            player.team = 'Free Agent'
        
        # Log post-free agency roster state
        log_fa(f"\n=== POST-FREE AGENCY ROSTER STATE ===")
        log_fa(f"Total rounds: {roundNum}")
        log_fa(f"Total transactions: {len(freeAgencyDict)}\n")
        
        for team in teams:
            roster_players = [f"{pos}:{p.name if p else 'EMPTY'}" for pos, p in team.rosterDict.items()]
            log_fa(f"{team.name}: {', '.join(roster_players)}")
        
        log_fa(f"\n=== REMAINING FREE AGENTS ({len(self.freeAgents)}) ===")
        for player in sorted(self.freeAgents, key=lambda p: (p.position.value, -p.attributes.skillRating)):
            log_fa(f"  {player.position.name:3} - {player.name:30} (Skill: {player.attributes.skillRating:3})")
        
        log_fa(f"\n=== ALL PLAYER TEAM ASSIGNMENTS ===")
        for player in sorted(self.activePlayers, key=lambda p: (p.name)):
            team_name = "FREE AGENT"
            if hasattr(player, 'team'):
                if isinstance(player.team, str):
                    team_name = player.team
                elif hasattr(player.team, 'name'):
                    team_name = player.team.name
                elif isinstance(player.team, int):
                    team_name = f"Team ID {player.team}"
                else:
                    team_name = f"UNKNOWN TYPE: {type(player.team)}"
            log_fa(f"  {player.name:30} -> {team_name}")
        
        # Save free agency history
        freeAgencyHistory[f'offseason {currentSeason}'] = freeAgencyDict
        
        # Close log file
        if fa_log:
            fa_log.write(f"\nEnd Time: {datetime.datetime.now()}\n")
            fa_log.close()
            logger.info(f"Free agency log saved to {fa_log_path}")
        
        logger.info(f"Free agency complete. {len(freeAgencyDict)} transactions made.")
        return freeAgencyHistory

    def freeAgencyPickGenerator(self, freeAgencyOrder: List, currentSeason: int,
                                leagueHighlights: List = None, skipRetirements: bool = False):
        """Generator that yields one FA event at a time for live broadcasting.

        Yields dicts with 'type' key: 'on_clock', 'pick', 'team_complete'.
        Rosters are mutated in-place as each pick is yielded, so the backend
        state is always current and REST endpoints return accurate data.
        """
        import datetime as _dt

        logger.info(f"Starting live free agency for season {currentSeason}")

        freeAgencyDict = {}
        if leagueHighlights is None:
            leagueHighlights = []

        # Log pre-FA rosters
        fa_log_path = f"logs/free_agency_season_{currentSeason}.log"
        try:
            import os
            os.makedirs("logs", exist_ok=True)
            faLog = open(fa_log_path, 'w')
            faLog.write(f"=== FREE AGENCY LOG - SEASON {currentSeason} ===\n")
            faLog.write(f"Start Time: {_dt.datetime.now()}\n\n")
        except Exception:
            faLog = None

        def logFa(msg):
            if faLog:
                faLog.write(msg + "\n")
                faLog.flush()

        teamManager = self.serviceContainer.getService('team_manager')
        teams = teamManager.teams if teamManager else []

        # The persisted playoff faOrder snapshot is taken at the League
        # Championship round, BEFORE the two Floos Bowl finalists are appended,
        # so on a resume the draft order can be short a couple teams. A team
        # missing from the order would never pick AND would stall the completion
        # loop (teamsComplete could never reach the team count) — append any
        # missing teams so every roster is drafted.
        if teams:
            orderIds = {getattr(t, 'id', None) for t in freeAgencyOrder}
            missing = [t for t in teams if getattr(t, 'id', None) not in orderIds]
            if missing:
                logger.warning(
                    f"FA draft order was missing {len(missing)} team(s); appending: "
                    f"{[t.name for t in missing]}"
                )
                freeAgencyOrder = list(freeAgencyOrder) + missing

        logFa("=== PRE-FREE AGENCY ROSTER STATE ===")
        for team in teams:
            rosterPlayers = [f"{pos}:{p.name if p else 'EMPTY'}" for pos, p in team.rosterDict.items()]
            logFa(f"{team.name}: {', '.join(rosterPlayers)}")

        if not skipRetirements:
            self._processFreeAgentRetirements(currentSeason, leagueHighlights)
            self._generateReplacementPlayers(currentSeason)

        logFa(f"\n=== FREE AGENT POOL (Total: {len(self.freeAgents)}) ===")
        for player in sorted(self.freeAgents, key=lambda p: (p.position.value, -p.attributes.skillRating)):
            logFa(f"  {player.position.name:3} - {player.name:30} (Skill: {player.attributes.skillRating:3})")

        # Prepare position-sorted FA lists. Sort by overall playerRating (the
        # rating users see in the FA pool stars) — sorting by skillRating
        # alone would pick offensively-strong players over higher-overall
        # two-way ones, mismatching the "best player available" expectation.
        def _faSort(plist):
            return sorted(plist, key=lambda p: getattr(p, 'playerRating', p.attributes.skillRating), reverse=True)
        freeAgentQbList = _faSort([p for p in self.freeAgents if p.position.value == 1])
        freeAgentRbList = _faSort([p for p in self.freeAgents if p.position.value == 2])
        freeAgentWrList = _faSort([p for p in self.freeAgents if p.position.value == 3])
        freeAgentTeList = _faSort([p for p in self.freeAgents if p.position.value == 4])
        freeAgentKList = _faSort([p for p in self.freeAgents if p.position.value == 5])

        if not teams:
            logger.error("No teams available for free agency!")
            return

        for team in teams:
            openPositions = [k for k in ('qb', 'rb', 'wr1', 'wr2', 'te', 'k')
                            if team.rosterDict.get(k) is None]
            team.freeAgencyComplete = len(openPositions) == 0

        # Build directive queues per team (ordered list of target player IDs)
        freeAgentLists = {
            'qb': freeAgentQbList, 'rb': freeAgentRbList,
            'wr1': freeAgentWrList, 'wr2': freeAgentWrList,
            'te': freeAgentTeList, 'k': freeAgentKList,
        }
        gmDirectives = getattr(self, '_gmFaDirectives', {})
        teamDirectiveQueues = {}
        for team in freeAgencyOrder:
            directives = gmDirectives.get(getattr(team, 'id', None), [])
            if directives:
                teamDirectiveQueues[team.id] = list(directives)

        # --- DRAFT ROUNDS: one pick per team per round ---
        teamsComplete = 0
        roundNum = 0
        maxRounds = 100

        # Completion keys off freeAgencyOrder (the collection actually iterated),
        # NOT len(teams) — otherwise an order short any teams can never satisfy
        # the exit condition and spins straight to the safety valve.
        while teamsComplete < len(freeAgencyOrder):
            teamsComplete = 0
            roundNum += 1
            if roundNum > maxRounds:
                logger.warning(f"Free agency exceeded {maxRounds} rounds, ending")
                for team in teams:
                    if not team.freeAgencyComplete:
                        openPos = [k for k, v in team.rosterDict.items()
                                   if v is None and k in ('qb', 'rb', 'wr1', 'wr2', 'te', 'k')]
                        if openPos:
                            logger.error(
                                f"FA draft force-ended with {team.name} still missing {openPos} "
                                f"— a roster slot was left empty"
                            )
                        team.freeAgencyComplete = True
                break

            for team in freeAgencyOrder:
                if team.freeAgencyComplete:
                    teamsComplete += 1
                    continue

                teamAbbr = getattr(team, 'abbr', team.name[:3].upper())

                # Yield on-the-clock before attempting pick
                yield {'type': 'on_clock', 'team': team.name, 'teamAbbr': teamAbbr}

                # Priority order: walk fan directives (which may interleave FA
                # and prospect IDs). Fan-ranked #1 prospects were already
                # promoted in the pre-draft pass; any remaining prospect in
                # the queue is a fall-through pick (Rule 2 — their higher-
                # ranked FAs ahead of them are gone or no longer eligible).
                directivePick = False
                prospectsById = {p.id: p for p in getattr(team, 'prospects', [])}
                queue = teamDirectiveQueues.get(team.id, [])
                while queue:
                    targetId = queue.pop(0)

                    # Case A — ranked target is a prospect: promote them
                    prospectTarget = prospectsById.get(targetId)
                    if prospectTarget is not None:
                        openSlot = self._findOpenSlotForPosition(team, prospectTarget.position.value)
                        if not openSlot:
                            continue
                        prospectTarget.is_prospect = False
                        prospectTarget.prospect_seasons = 0
                        prospectTarget.drafting_team_id = None
                        prospectTarget.team = team
                        team.rosterDict[openSlot] = prospectTarget
                        if prospectTarget in team.prospects:
                            team.prospects.remove(prospectTarget)
                        try:
                            prospectTarget.term = self._getPlayerTerm(prospectTarget)
                            prospectTarget.termRemaining = prospectTarget.term
                        except Exception:
                            prospectTarget.termRemaining = 1
                        freeAgencyDict.setdefault(team.name, []).append({
                            'action': 'promote', 'player': prospectTarget.name,
                            'position': prospectTarget.position.name, 'slot': openSlot,
                        })
                        leagueHighlights.insert(0, {
                            'event': {'text': f"{team.name} promoted prospect {prospectTarget.name} ({prospectTarget.position.name}) by fan vote"}
                        })
                        logFa(f"  FAN VOTE PROMOTE (fall-through): {team.name} promotes {prospectTarget.name} at {openSlot}")
                        yield {
                            'type': 'pick', 'team': team.name, 'teamAbbr': teamAbbr,
                            'playerId': getattr(prospectTarget, 'id', None),
                            'player': prospectTarget.name, 'position': prospectTarget.position.name,
                            'rating': round(prospectTarget.playerRating, 1), 'tier': prospectTarget.playerTier.name,
                            'isPromotion': True,
                            'slot': openSlot,
                        }
                        directivePick = True
                        openPositions = [k for k, v in team.rosterDict.items() if v is None
                                         and k in ('qb', 'rb', 'wr1', 'wr2', 'te', 'k')]
                        if not openPositions:
                            teamsComplete += 1
                            team.freeAgencyComplete = True
                            yield {'type': 'team_complete', 'team': team.name, 'teamAbbr': teamAbbr}
                        break  # One action per turn

                    # Case B — ranked target is an FA: sign them
                    targetPlayer = None
                    targetListKey = None
                    for lKey, faList in freeAgentLists.items():
                        for p in faList:
                            if p.id == targetId:
                                targetPlayer = p
                                targetListKey = lKey
                                break
                        if targetPlayer:
                            break
                    if not targetPlayer:
                        continue
                    # Skip a player this team just released this offseason (cut
                    # or let walk) even if fans ranked them on the FA ballot.
                    if self._leftThisTeamThisOffseason(targetPlayer, team):
                        continue
                    openSlot = self._findOpenSlotForPosition(team, targetPlayer.position.value)
                    if not openSlot:
                        continue
                    self._signPlayer(team, targetPlayer, openSlot, freeAgentLists[targetListKey],
                                     freeAgencyDict, leagueHighlights, allFaLists=freeAgentLists)
                    logFa(f"  GM DIRECTIVE: {team.name} signs {targetPlayer.name} at {openSlot}")
                    yield {
                        'type': 'pick', 'team': team.name, 'teamAbbr': teamAbbr,
                        'playerId': getattr(targetPlayer, 'id', None),
                        'player': targetPlayer.name, 'position': targetPlayer.position.name,
                        'rating': round(targetPlayer.playerRating, 1), 'tier': targetPlayer.playerTier.name,
                        'slot': openSlot,
                    }
                    directivePick = True
                    # Check if roster is now full
                    openPositions = [k for k, v in team.rosterDict.items() if v is None
                                     and k in ('qb', 'rb', 'wr1', 'wr2', 'te', 'k')]
                    if not openPositions:
                        teamsComplete += 1
                        team.freeAgencyComplete = True
                        yield {'type': 'team_complete', 'team': team.name, 'teamAbbr': teamAbbr}
                    break  # One pick per turn

                if not directivePick:
                    # Rule 3 — no fan directive matched. Sign or promote the
                    # best player available across FAs and prospects (handled
                    # inside _attemptRosterFill). Auto-promote no longer
                    # fires preemptively at a fixed rating floor — a prospect
                    # only gets the slot if they're literally the highest-
                    # rated option on the board.
                    pickEvents = []
                    rosterComplete = self._attemptRosterFill(
                        team, teams, freeAgentQbList, freeAgentRbList, freeAgentWrList,
                        freeAgentTeList, freeAgentKList, freeAgencyDict, leagueHighlights,
                        eventLog=pickEvents,
                    )

                    for ev in pickEvents:
                        # Log path mirrors the directive walk so the FA log
                        # remains a complete record of every roster move.
                        if ev.get('isPromotion'):
                            logFa(f"  PROSPECT PROMOTED (best available): {team.name} promotes {ev['player']} at {ev.get('slot', '?')}")
                        else:
                            logFa(f"  BEST AVAILABLE: {team.name} signs {ev['player']} at {ev.get('slot', '?')}")
                        yield ev

                    # Last resort: the team has open slots but _attemptRosterFill
                    # signed NOTHING (no pick events) — the pool is genuinely empty
                    # at every open position. Generate a replacement FA into the
                    # working lists and retry so the draft can never leave a hole.
                    # (rosterComplete=False alone is the normal mid-draft state —
                    # only an empty pickEvents means nothing was signable.)
                    if not rosterComplete and not pickEvents:
                        slotToPos = {'qb': 1, 'rb': 2, 'wr1': 3, 'wr2': 3, 'te': 4, 'k': 5}
                        posToList = {1: freeAgentQbList, 2: freeAgentRbList, 3: freeAgentWrList,
                                     4: freeAgentTeList, 5: freeAgentKList}
                        openSlots = [k for k, v in team.rosterDict.items()
                                     if v is None and k in slotToPos]
                        generatedAny = False
                        for slot in openSlots:
                            pv = slotToPos[slot]
                            newP = self.generateLastResortFreeAgent(pv)
                            if newP:
                                posToList[pv].insert(0, newP)  # into the draft's working list
                                generatedAny = True
                        if generatedAny:
                            retryEvents = []
                            rosterComplete = self._attemptRosterFill(
                                team, teams, freeAgentQbList, freeAgentRbList, freeAgentWrList,
                                freeAgentTeList, freeAgentKList, freeAgencyDict, leagueHighlights,
                                eventLog=retryEvents,
                            )
                            for ev in retryEvents:
                                logFa(f"  LAST-RESORT SIGN: {team.name} signs {ev['player']} at {ev.get('slot', '?')}")
                                yield ev

                    if rosterComplete:
                        teamsComplete += 1
                        team.freeAgencyComplete = True
                        yield {'type': 'team_complete', 'team': team.name, 'teamAbbr': teamAbbr}

        # Cleanup — keep freeAgencyComplete=True so REST endpoint reports draftComplete correctly
        for player in self.freeAgents:
            player.team = 'Free Agent'

        logFa(f"\n=== POST-FREE AGENCY ROSTER STATE ===")
        logFa(f"Total rounds: {roundNum}")
        for team in teams:
            rosterPlayers = [f"{pos}:{p.name if p else 'EMPTY'}" for pos, p in team.rosterDict.items()]
            logFa(f"{team.name}: {', '.join(rosterPlayers)}")
        if faLog:
            faLog.write(f"\nEnd Time: {_dt.datetime.now()}\n")
            faLog.close()
            logger.info(f"Free agency log saved to {fa_log_path}")

        logger.info(f"Live free agency complete. {len(freeAgencyDict)} transactions made.")

    def _processContractExpirations(self) -> None:
        """Move players with expired contracts to free agency"""
        expiredPlayers = []
        
        # Get all teams to check rosters
        teamManager = self.serviceContainer.getService('team_manager')
        teams = teamManager.teams if teamManager else []
        
        # Build set of all players currently on rosters
        rostered_player_ids = set()
        for team in teams:
            for pos, player in team.rosterDict.items():
                if player is not None:
                    rostered_player_ids.add(player.id)
        
        for player in self.activePlayers:
            if hasattr(player, 'termRemaining') and player.termRemaining <= 0:
                # Only add to free agency if NOT currently on a roster
                if player.id not in rostered_player_ids:
                    expiredPlayers.append(player)
                else:
                    logger.warning(f"Player {player.name} has expired contract but is on a roster - skipping FA add")
        
        for player in expiredPlayers:
            # Free agents stay in activePlayers and position lists
            player.team = 'Free Agent'
            player.freeAgentYears = 0  # Start at 0 when first becoming a free agent
            if player not in self.freeAgents:
                self.freeAgents.append(player)
            
        logger.info(f"Moved {len(expiredPlayers)} players with expired contracts to free agency")
    
    def _processFreeAgentRetirements(self, currentSeason: int, leagueHighlights: List,
                                     preIncrement: bool = False) -> None:
        """Process retirements of long-term free agents.

        preIncrement=True: caller runs BEFORE the offseason free-agent-years
        increment (i.e. at week GM_ACTIVE_WEEK), so tenure is evaluated as
        freeAgentYears + 1 to match the post-increment eligibility the offseason
        path used. This lets the FA pool be finalized by week 22 (retirees removed
        up front) so the supply check + FA ballots see the real pool.
        """
        retirements = []
        bump = 1 if preIncrement else 0

        for player in self.freeAgents[:]:  # Use slice copy for safe iteration
            freeAgentYears = getattr(player, 'freeAgentYears', 0) + bump

            if freeAgentYears >= 3:
                # Base retirement chance by tier
                baseTierChance = 0
                if player.playerTier.value == 1:  # TierD
                    baseTierChance = 0.65
                elif player.playerTier.value == 2:  # TierC  
                    baseTierChance = 0.40
                elif player.playerTier.value == 3:  # TierB
                    baseTierChance = 0.25
                elif player.playerTier.value == 4:  # TierA
                    baseTierChance = 0.15
                elif player.playerTier.value == 5:  # TierS
                    baseTierChance = 0.05
                
                # Increase chance based on years as free agent (after year 3)
                # Add 15% per year after year 3, making long-term free agents retire faster
                yearsMultiplier = (freeAgentYears - 2) * 0.15  # Year 3: +0.15, Year 4: +0.30, Year 5: +0.45, etc.
                retirementChance = min(0.95, baseTierChance + yearsMultiplier)  # Cap at 95%
                
                from random import random
                if random() < retirementChance:
                    retirements.append(player)
                    self.retirePlayer(player)
                    leagueHighlights.insert(0, {
                        'event': {'text': f'{player.name} has retired from football'}
                    })
        
        logger.info(f"Free agent retirements: {len(retirements)} players retired")
    
    def _generateReplacementPlayers(self, currentSeason: int) -> None:
        """Generate replacement players for those who retired
        
        Ensures minimum of 3 new players per offseason, with balanced position distribution.
        Uses dual-seed system to create variety in physical and mental abilities.
        """
        import numpy as np
        from random import randint, choice
        
        # Get number of teams to calculate minimum players needed
        teamManager = self.serviceContainer.getService('team_manager')
        numTeams = len(teamManager.teams) if teamManager else 8
        
        numRetired = len(self.newlyRetiredPlayers)
        minNewPlayers = 3  # Reduced to prevent player pool bloat
        
        # Determine how many players to generate
        numOfPlayers = max(numRetired, minNewPlayers)
        
        # Generate physical and mental seeds separately for variety
        # Using mean 78 and higher stdDev for more realistic distribution
        # Tighter distribution so the league has fewer extreme stars
        # and fewer scrubs — compresses the rating gap that drives the
        # "dominant team" problem. stdDev was 10 → 7. Most seeds now
        # fall in 71-85 (one stdDev band) instead of 68-88, so the
        # league talent ceiling drops without erasing top players.
        meanPlayerSkill = 78
        stdDevPlayerSkill = 7
        physicalSeeds = np.random.normal(meanPlayerSkill, stdDevPlayerSkill, numOfPlayers)
        physicalSeeds = np.clip(physicalSeeds, 60, 100).tolist()
        mentalSeeds = np.random.normal(meanPlayerSkill, stdDevPlayerSkill, numOfPlayers)
        mentalSeeds = np.clip(mentalSeeds, 60, 100).tolist()
        
        # Find the next available player ID
        nextPlayerId = max([p.id for p in self.activePlayers], default=0) + 1
        
        # First: Create replacement players for retired players (matching positions)
        positionCounts = {'QB': 0, 'RB': 0, 'WR': 0, 'TE': 0, 'K': 0}
        for i, retiredPlayer in enumerate(self.newlyRetiredPlayers):
            if physicalSeeds and mentalSeeds:
                # Pop random seeds from both lists
                physIdx = randint(0, len(physicalSeeds) - 1)
                physicalSeed = int(physicalSeeds.pop(physIdx))
                # Pop from same index if possible, otherwise random
                mentIdx = min(physIdx, len(mentalSeeds) - 1) if physIdx < len(mentalSeeds) else randint(0, len(mentalSeeds) - 1)
                mentalSeed = int(mentalSeeds.pop(mentIdx))
                
                newPlayer = self.createPlayer(retiredPlayer.position, physicalSeed, mentalSeed)
                if newPlayer:
                    newPlayer.id = nextPlayerId
                    nextPlayerId += 1
                    newPlayer.team = 'Free Agent'
                    newPlayer.freeAgentYears = 0
                    # Note: Contract terms set after tier assignment
                    # Add to free agents list
                    self.freeAgents.append(newPlayer)
                    # Add to active players and position lists (free agents are active)
                    if newPlayer not in self.activePlayers:
                        self.activePlayers.append(newPlayer)
                    self.addToPositionList(newPlayer)
                    # Track position counts
                    if retiredPlayer.position.value == 1:
                        positionCounts['QB'] += 1
                    elif retiredPlayer.position.value == 2:
                        positionCounts['RB'] += 1
                    elif retiredPlayer.position.value == 3:
                        positionCounts['WR'] += 1
                    elif retiredPlayer.position.value == 4:
                        positionCounts['TE'] += 1
                    elif retiredPlayer.position.value == 5:
                        positionCounts['K'] += 1
        
        # Second: Create additional players if needed to meet minimum
        # Use balanced distribution to ensure enough at each position
        if minNewPlayers > numRetired:
            additionalPlayers = minNewPlayers - numRetired
            
            # Calculate how many we need at each position to maintain balance
            # Each team needs: 1 QB, 1 RB, 2 WR, 1 TE, 1 K
            # We use a weighted distribution: QB=1, RB=1, WR=2, TE=1, K=1 (total weight=6)
            positionWeights = {
                FloosPlayer.Position.QB: 1,
                FloosPlayer.Position.RB: 1, 
                FloosPlayer.Position.WR: 2,  # WR has 2x weight since teams need 2
                FloosPlayer.Position.TE: 1,
                FloosPlayer.Position.K: 1
            }
            
            # Create weighted position list for selection
            weightedPosList = []
            for pos, weight in positionWeights.items():
                weightedPosList.extend([pos] * weight)
            
            for x in range(additionalPlayers):
                if physicalSeeds and mentalSeeds:
                    # Pop random seeds from both lists
                    physIdx = randint(0, len(physicalSeeds) - 1)
                    physicalSeed = int(physicalSeeds.pop(physIdx))
                    mentIdx = min(physIdx, len(mentalSeeds) - 1) if physIdx < len(mentalSeeds) else randint(0, len(mentalSeeds) - 1)
                    mentalSeed = int(mentalSeeds.pop(mentIdx))
                    
                    randomPos = weightedPosList[randint(0, len(weightedPosList) - 1)]
                    newPlayer = self.createPlayer(randomPos, physicalSeed, mentalSeed)
                    if newPlayer:
                        newPlayer.id = nextPlayerId
                        nextPlayerId += 1
                        newPlayer.team = 'Free Agent'
                        newPlayer.freeAgentYears = 0
                        # Note: Contract terms set after tier assignment
                        # Add to free agents list
                        self.freeAgents.append(newPlayer)
                        # Add to active players and position lists
                        if newPlayer not in self.activePlayers:
                            self.activePlayers.append(newPlayer)
                        self.addToPositionList(newPlayer)
        
        # Assign correct tiers to all newly created players based on their ratings
        self.sortPlayersByPosition()
        
        # Count high-tier players for logging (after tiers are assigned)
        highTierCount = sum(1 for p in self.freeAgents[-numOfPlayers:] if p.playerTier.name in ['TierA', 'TierS'])
        logger.info(f"Generated {numOfPlayers} replacement players ({numRetired} retired, {max(0, minNewPlayers - numRetired)} additional, {highTierCount} tier A/S)")

    def generateLastResortFreeAgent(self, posValue: int):
        """Create a single signable free agent at a position, fully initialized
        (tier + added to the FA/active/position pools). Last-resort safety used
        by the live FA draft when a team is on the clock with an open slot and
        the pool at that position is genuinely empty — guarantees the draft can
        never leave a roster hole. Returns the new player (or None on failure)."""
        import numpy as np
        try:
            pos = FloosPlayer.Position(posValue)
        except Exception:
            return None
        phys = int(np.clip(np.random.normal(78, 7), 60, 100))
        ment = int(np.clip(np.random.normal(78, 7), 60, 100))
        newPlayer = self.createPlayer(pos, phys, ment)
        if not newPlayer:
            return None
        newPlayer.id = max([p.id for p in self.activePlayers], default=0) + 1
        newPlayer.team = 'Free Agent'
        newPlayer.freeAgentYears = 0
        self.freeAgents.append(newPlayer)
        if newPlayer not in self.activePlayers:
            self.activePlayers.append(newPlayer)
        self.addToPositionList(newPlayer)
        # Assigns playerTier (needed by the pick event) + a default contract.
        self.sortPlayersByPosition()
        logger.warning(
            f"FA draft last-resort: generated {newPlayer.name} ({pos.name}) — "
            f"the {pos.name} pool was empty for a team on the clock"
        )
        return newPlayer

    def ensurePositionSupply(self, numTeams: int, buffer: int = None) -> dict:
        """Guarantee enough living players AT EACH POSITION to fill every roster
        slot, generating only the per-position deficit into the free-agent pool.

        Supply = genuinely DRAFTABLE players by position: rostered + free agents.
        Excludes retiring players (`willRetire`), already-retired players, AND
        prospects / the upcoming rookie class (`is_prospect`) — prospects are
        locked to their drafting team and can't fill another team's vacancy, so
        counting them overstated availability. Demand = numTeams × slots-at-
        position (WR is ×2) plus a cushion (ROSTER_SUPPLY_BUFFER_PER_POSITION).

        No-op in the normal case (the pool is far deeper than demand); only a
        genuinely thinned position triggers generation. Idempotent: already-
        generated FAs count toward supply, so re-running only fills what's still
        short. Returns {positionName: countGenerated} for the positions topped up.
        """
        import numpy as np
        from random import randint
        from constants import ROSTER_SUPPLY_BUFFER_PER_POSITION
        if buffer is None:
            buffer = ROSTER_SUPPLY_BUFFER_PER_POSITION

        slotsPerPosition = {
            FloosPlayer.Position.QB: 1,
            FloosPlayer.Position.RB: 1,
            FloosPlayer.Position.WR: 2,
            FloosPlayer.Position.TE: 1,
            FloosPlayer.Position.K: 1,
        }

        # Draftable supply by position. Excludes:
        #  - retiring players (`willRetire`) — gone in the offseason;
        #  - prospects / the upcoming rookie class (`is_prospect`) — each is
        #    LOCKED to its drafting team (only that team can promote it), so a
        #    prospect does nothing for another team's vacancy. Counting them
        #    overstated availability and let the FA pool come up short, forcing
        #    the draft's last-resort generation. Excluding them makes the floor
        #    generate enough genuine free agents (over-generating slightly when
        #    prospects do get promoted, which is harmless — the extra FAs just
        #    sit in the pool).
        supply = {pos: 0 for pos in slotsPerPosition}
        for p in self.activePlayers:
            if getattr(p, 'willRetire', False):
                continue
            if getattr(p, 'is_prospect', False):
                continue
            pos = getattr(p, 'position', None)
            if pos in supply:
                supply[pos] += 1

        deficits = {}
        for pos, perTeam in slotsPerPosition.items():
            demand = numTeams * perTeam + buffer
            short = demand - supply[pos]
            if short > 0:
                deficits[pos] = short

        if not deficits:
            return {}

        # Generate the shortfall as free agents (same seed/createPlayer idiom as
        # _generateReplacementPlayers so the new players are valid, signable FAs).
        total = sum(deficits.values())
        meanPlayerSkill, stdDevPlayerSkill = 78, 7
        physicalSeeds = np.clip(np.random.normal(meanPlayerSkill, stdDevPlayerSkill, total), 60, 100).tolist()
        mentalSeeds = np.clip(np.random.normal(meanPlayerSkill, stdDevPlayerSkill, total), 60, 100).tolist()
        nextPlayerId = max([p.id for p in self.activePlayers], default=0) + 1

        generated = {}
        for pos, count in deficits.items():
            for _ in range(count):
                physicalSeed = int(physicalSeeds.pop()) if physicalSeeds else meanPlayerSkill
                mentalSeed = int(mentalSeeds.pop()) if mentalSeeds else meanPlayerSkill
                newPlayer = self.createPlayer(pos, physicalSeed, mentalSeed)
                if not newPlayer:
                    continue
                newPlayer.id = nextPlayerId
                nextPlayerId += 1
                newPlayer.team = 'Free Agent'
                newPlayer.freeAgentYears = 0
                self.freeAgents.append(newPlayer)
                if newPlayer not in self.activePlayers:
                    self.activePlayers.append(newPlayer)
                self.addToPositionList(newPlayer)
                generated[pos.name] = generated.get(pos.name, 0) + 1

        # Assign tiers/contracts to the new free agents.
        self.sortPlayersByPosition()
        if generated:
            logger.info(
                f"Roster supply top-up: generated {generated} "
                f"(supply was {{ {', '.join(f'{k.name}:{v}' for k, v in supply.items())} }}, "
                f"{numTeams} teams, buffer {buffer})"
            )
        return generated

    # ── Prospect Pipeline: rookie class generation + draft ──────────────

    def _generateRookieClass(self, currentSeason: int) -> List:
        """Generate a fresh rookie class of ROOKIE_DRAFT_CLASS_SIZE players.

        Returns the list of new rookies (not yet added to freeAgents or
        activePlayers). Position distribution matches roster shape:
        QB/RB/TE/K weighted 1x, WR weighted 2x (teams start 2 WRs).
        Replaces the old _generateReplacementPlayers flow for the normal
        rookie class — retirement-driven replacements are no longer needed
        because 24 rookies > typical league-wide retirements.
        """
        import numpy as np
        from random import randint
        from constants import ROOKIE_DRAFT_CLASS_SIZE, GEN_TRUESKILL_MEAN, GEN_TRUESKILL_STD

        numRookies = ROOKIE_DRAFT_CLASS_SIZE
        # The generated seed is the rookie's TRUE SKILL (mature target); they
        # debut below it via the entry discount below. Parity distribution.
        meanSkill = GEN_TRUESKILL_MEAN
        stdDev = GEN_TRUESKILL_STD
        physicalSeeds = np.clip(np.random.normal(meanSkill, stdDev, numRookies), 60, 100).tolist()
        mentalSeeds = np.clip(np.random.normal(meanSkill, stdDev, numRookies), 60, 100).tolist()

        # Position weights match roster shape (WR x2 because teams start 2)
        positionWeights = {
            FloosPlayer.Position.QB: 1,
            FloosPlayer.Position.RB: 1,
            FloosPlayer.Position.WR: 2,
            FloosPlayer.Position.TE: 1,
            FloosPlayer.Position.K: 1,
        }
        weightedPosList = []
        for pos, weight in positionWeights.items():
            weightedPosList.extend([pos] * weight)

        nextPlayerId = max([p.id for p in self.activePlayers], default=0) + 1
        rookies = []
        for i in range(numRookies):
            physicalSeed = int(physicalSeeds[i])
            mentalSeed = int(mentalSeeds[i])
            pos = weightedPosList[randint(0, len(weightedPosList) - 1)]
            player = self.createPlayer(pos, physicalSeed, mentalSeed)
            if not player:
                continue
            player.id = nextPlayerId
            nextPlayerId += 1
            # Rookie flags — not in FA pool yet; drafted into prospects or placed into FA below
            player.seasonsPlayed = 0
            player.team = 'Unsigned'
            # Debut below true skill; the dev arc grows them into it.
            from constants import PROSPECT_ENTRY_DISCOUNT
            player.applyEntryDiscount(PROSPECT_ENTRY_DISCOUNT)
            rookies.append(player)
        logger.info(f"Generated rookie class of {len(rookies)} for season {currentSeason}")
        return rookies

    def parityStarFraction(self) -> float:
        """Fraction of the non-retired pool at 4-5-star (rating >= 84). Used to
        detect an OLD inflated pool (needs the one-time parity re-map) vs a
        fresh/already-re-mapped one already on the true-skill curve."""
        pool = [p for p in self.activePlayers
                if getattr(p, 'serviceTime', None) != FloosPlayer.PlayerServiceTime.Retired
                and getattr(p, 'playerRating', 0)]
        if not pool:
            return 0.0
        return sum(1 for p in pool if p.playerRating >= 84) / len(pool)

    def remapPoolToTrueSkill(self) -> int:
        """One-time between-season re-map of the existing (inflated) pool onto
        the new true-skill distribution, rank-preserving PER POSITION (QB/RB/WR/
        TE/K sit on different rating scales, so a pooled map would distort them).

        Deflates every non-retired player (rostered / FA / prospect / upcoming
        rookie) onto the parity curve and FREEZES them: trueSkill = potential =
        current. Freezing is essential — leaving any overshoot headroom (or an
        old inflated potential on the excluded prospect cohort) lets the pool
        climb straight back up over a few seasons (measured: 19% -> 25%). With
        the freeze, only NEW post-cutover rookies develop under the full
        three-tier model; the existing pool holds its deflated ratings and ages
        out. Migration for the parity package — the caller guards it to run once.
        Validated on a prod-copy boot (held ~20%, no creep). See
        docs/PARITY_PROSPECT_PLAN.md Phase 3.
        """
        import numpy as np
        from random import randint
        from constants import (GEN_TRUESKILL_MEAN, GEN_TRUESKILL_STD,
                               PROSPECT_ENTRY_DISCOUNT, POTENTIAL_HEADROOM)
        from floosball_player import _TRUESKILL_ATTR_TRIPLES
        from player_development import PlayerDevelopment

        PHYS = ['speed', 'power', 'agility', 'reach', 'hands', 'armStrength', 'accuracy', 'legStrength']
        posClass = {
            FloosPlayer.Position.QB: FloosPlayer.PlayerQB,
            FloosPlayer.Position.RB: FloosPlayer.PlayerRB,
            FloosPlayer.Position.WR: FloosPlayer.PlayerWR,
            FloosPlayer.Position.TE: FloosPlayer.PlayerTE,
            FloosPlayer.Position.K:  FloosPlayer.PlayerK,
        }
        pool = [p for p in self.activePlayers
                if getattr(p, 'serviceTime', None) != FloosPlayer.PlayerServiceTime.Retired
                and getattr(p, 'playerRating', 0) and getattr(p, 'position', None) in posClass]
        if not pool:
            return 0

        def refCurve(posEnum, M=3000):
            ctor = posClass[posEnum]
            vals = []
            for _ in range(M):
                s = int(np.clip(np.random.normal(GEN_TRUESKILL_MEAN, GEN_TRUESKILL_STD), 60, 100))
                m = int(np.clip(np.random.normal(GEN_TRUESKILL_MEAN, GEN_TRUESKILL_STD), 60, 100))
                vals.append(ctor(s, m).playerRating)
            vals.sort()
            return vals

        def setToRating(p, target):
            # Shift physical athletic attrs to move playerRating toward target
            # (rating moves ~0.8x per unit shift; iterate on the residual).
            # Preserves each player's relative attribute shape.
            for _ in range(12):
                d = target - p.playerRating
                if d == 0:
                    break
                for attr in PHYS:
                    v = getattr(p.attributes, attr, 0)
                    if v > 0:
                        setattr(p.attributes, attr, int(np.clip(v + d, 45, 100)))
                p.updateRating()

        byPos = {}
        for p in pool:
            byPos.setdefault(p.position, []).append(p)

        total = 0
        for posEnum, players in byPos.items():
            ref = refCurve(posEnum)
            M = len(ref); N = len(players)
            order = sorted(range(N), key=lambda i: players[i].playerRating)  # low -> high
            for rank, i in enumerate(order):
                p = players[i]
                pct = (rank + 0.5) / N
                setToRating(p, ref[min(M - 1, int(pct * M))])  # rank places them on the mature curve
                # Career stage decides development runway. The rank above is the
                # player's MATURE level (their spot on the new curve). RISING
                # players (below their peak season) debut BELOW it and develop UP
                # into it — trueSkill = mature rank, current lowered by a bounded
                # runway, potential a touch above. So the aggregate lands ON the
                # curve at maturity (no re-inflation), while young players still
                # visibly grow. PEAK/DECLINING players are FROZEN at their mature
                # rank (trueSkill = potential = current): done growing, and the
                # freeze is what stops the pool climbing back up. Runway is capped
                # at the entry discount new rookies get.
                peak = PlayerDevelopment.peakSeason(p)
                seasons = getattr(p, 'seasonsPlayed', 0) or 0
                if seasons < peak:
                    runway = int(round(PROSPECT_ENTRY_DISCOUNT * (peak - seasons) / max(1, peak)))
                else:
                    runway = 0
                for attr, trueName, potName in _TRUESKILL_ATTR_TRIPLES:
                    cur = getattr(p.attributes, attr, 0)
                    if cur <= 0:
                        setattr(p.attributes, trueName, 0)
                        setattr(p.attributes, potName, 0)
                        continue
                    setattr(p.attributes, trueName, cur)   # trueSkill = mature rank
                    pot = int(np.clip(cur + (randint(0, POTENTIAL_HEADROOM) if runway > 0 else 0), cur, 100))
                    setattr(p.attributes, potName, pot)    # overshoot room only where there's runway
                    if runway > 0:
                        setattr(p.attributes, attr, int(np.clip(cur - runway, 45, cur)))  # debut BELOW, grow up into trueSkill
                p.updateRating()   # rating reflects the lowered debut level for the young
                p.attributes.potentialSkillRating = p.attributes.skillRating
                total += 1

        logger.info(f"Parity re-map: deflated {total} players onto the true-skill curve (rising debut below & grow in, peak/declining frozen)")
        return total

    def countTeamProspectsAtPosition(self, team, position) -> int:
        """How many prospects this team already holds at a given Position enum."""
        return sum(1 for p in getattr(team, 'prospects', []) if p.position == position)

    def hasOpenProspectSlot(self, team, position) -> bool:
        """True if the team can hold another prospect at this position."""
        from constants import PROSPECT_SLOT_CAP_PER_POSITION
        return self.countTeamProspectsAtPosition(team, position) < PROSPECT_SLOT_CAP_PER_POSITION

    def rookieDraftPickGenerator(self, rookies: List, draftOrder: List,
                                 leagueHighlights: list = None,
                                 fanPreferences: Optional[Dict[int, List[int]]] = None):
        """Generator-based rookie draft — yields one event at a time for live
        broadcasting, mirroring freeAgencyPickGenerator.

        Yields dicts with 'type' key: 'on_clock', 'pick', 'skip', 'complete'.
        Roster mutations happen in-place as each pick is yielded, so backend
        state is always current. Seasonmanager drives this with per-pick
        broadcasts + timing delays.
        """
        picks = []
        available = list(rookies)
        rookiesById = {r.id: r for r in rookies}
        fanPreferences = fanPreferences or {}

        for team in draftOrder:
            teamAbbr = getattr(team, 'abbr', team.name[:3].upper())
            if not available:
                break

            openPositions = [
                pos for pos in (FloosPlayer.Position.QB, FloosPlayer.Position.RB,
                                FloosPlayer.Position.WR, FloosPlayer.Position.TE,
                                FloosPlayer.Position.K)
                if self.hasOpenProspectSlot(team, pos)
            ]
            if not openPositions:
                logger.info(f"Rookie draft: {team.name} skipped (all prospect slots full)")
                yield {'type': 'skip', 'team': team.name, 'teamAbbr': teamAbbr,
                       'reason': 'pipeline_full'}
                continue
            eligibleSet = {r.id for r in available if r.position in openPositions}
            if not eligibleSet:
                logger.info(f"Rookie draft: {team.name} passed (no rookies at open positions)")
                yield {'type': 'skip', 'team': team.name, 'teamAbbr': teamAbbr,
                       'reason': 'no_eligible_rookies'}
                continue

            yield {'type': 'on_clock', 'team': team.name, 'teamAbbr': teamAbbr}

            pick = None
            pickSource = 'ai_best'
            for rookieId in fanPreferences.get(team.id, []):
                if rookieId in eligibleSet:
                    pick = rookiesById.get(rookieId)
                    if pick is not None:
                        pickSource = 'fan_vote'
                        break
            if pick is None:
                eligible = [r for r in available if r.id in eligibleSet]
                def pickScore(rookie):
                    prospectsHere = self.countTeamProspectsAtPosition(team, rookie.position)
                    return (rookie.playerRating, -prospectsHere)
                pick = max(eligible, key=pickScore)
            available.remove(pick)

            pick.is_prospect = True
            pick.is_upcoming_rookie = False
            pick.drafting_team_id = team.id
            pick.prospect_seasons = 0
            pick.team = 'Prospect'
            team.prospects.append(pick)
            if pick not in self.activePlayers:
                self.activePlayers.append(pick)
            self.addToPositionList(pick)
            # Assign jersey number now so promoted prospects don't show #0.
            team.assignPlayerNumber(pick)

            pickRecord = {
                "teamId": team.id, "teamName": team.name, "teamAbbr": teamAbbr,
                "playerId": pick.id, "playerName": pick.name,
                "position": pick.position.name,
                "rating": round(pick.playerRating, 1),
                "tier": pick.playerTier.name,
                "source": pickSource,
            }
            picks.append(pickRecord)

            if leagueHighlights is not None:
                voteNote = ' by fan vote' if pickSource == 'fan_vote' else ''
                leagueHighlights.insert(0, {
                    'event': {'text': f"{team.name} drafted {pick.name} ({pick.position.name}, {pick.playerTier.name}){voteNote}"}
                })

            yield {'type': 'pick', **pickRecord}

        # Anything left → FA pool as undrafted rookies
        undrafted = []
        for rookie in available:
            rookie.is_upcoming_rookie = False
            rookie.is_undrafted = True
            rookie.team = 'Free Agent'
            rookie.freeAgentYears = 0
            if rookie not in self.freeAgents:
                self.freeAgents.append(rookie)
            if rookie not in self.activePlayers:
                self.activePlayers.append(rookie)
            self.addToPositionList(rookie)
            undrafted.append(rookie.id)

        self.sortPlayersByPosition()
        voteDrafted = sum(1 for p in picks if p.get('source') == 'fan_vote')
        logger.info(
            f"Rookie draft complete: {len(picks)} drafted ({voteDrafted} via fan vote), "
            f"{len(undrafted)} undrafted to FA"
        )
        yield {'type': 'complete', 'picks': picks, 'undrafted': undrafted}
        return {"picks": picks, "undrafted": undrafted}

    def scoutRookie(self, rookie, effectiveScouting: int) -> dict:
        """Build the fan-facing scouting payload for a single upcoming rookie.

        Current rating is always exact — it's what they are right now. Potential
        attributes are blurred into ±range based on effective scouting (coach
        scouting + funding tier bonus). Higher scouting = tighter range.

        The range center is shifted by a deterministic-but-unguessable
        per-attribute offset so the midpoint of [low, high] doesn't trivially
        reveal the true potential. Offset is bounded to keep the true value
        inside the displayed range.
        """
        from constants import SCOUTING_BANDS
        import hashlib as _hashlib
        # Pick the range size from the band table
        rangeSize = 15
        for threshold, size in SCOUTING_BANDS:
            if effectiveScouting >= threshold:
                rangeSize = size
                break

        def blur(exact: int, attrName: str) -> dict:
            if exact is None:
                return {"low": None, "high": None, "exact": None}
            if rangeSize == 0:
                return {"low": exact, "high": exact, "exact": exact}
            # Deterministic per-(player, attribute) offset within ±rangeSize/2
            # so the midpoint is shifted but the true value remains inside
            # the range. Stable across refreshes — users can't average out
            # the noise by polling.
            seed = int(_hashlib.md5(
                f"scout:{rookie.id}:{attrName}".encode()
            ).hexdigest()[:8], 16)
            half = rangeSize // 2
            offset = (seed % (2 * half + 1)) - half if half > 0 else 0
            center = exact + offset
            low = max(60, center - rangeSize)
            high = min(100, center + rangeSize)
            return {"low": low, "high": high, "exact": None}

        attrs = getattr(rookie, 'attributes', None)
        potentials = {}
        if attrs:
            for name in ('potentialSpeed', 'potentialHands', 'potentialReach',
                        'potentialAgility', 'potentialPower', 'potentialArmStrength',
                        'potentialAccuracy', 'potentialLegStrength',
                        'potentialSkillRating'):
                val = getattr(attrs, name, None)
                if val:
                    potentials[name] = blur(val, name)

        return {
            "playerId": rookie.id,
            "name": rookie.name,
            "position": rookie.position.name,
            "rating": round(rookie.playerRating, 1),
            "tier": rookie.playerTier.name if hasattr(rookie, 'playerTier') else None,
            "longevity": getattr(attrs, 'longevity', None) if attrs else None,
            "potentials": potentials,
            "scoutingAccuracy": effectiveScouting,
            "scoutingRange": rangeSize,
        }

    def _tryPromoteProspect(self, team, freeAgencyDict: dict, leagueHighlights: list) -> Optional[dict]:
        """Promote the best-qualifying prospect into an open roster slot.

        Returns a dict describing the promotion on success, else None. A prospect
        qualifies when their playerRating meets PROSPECT_PROMOTION_RATING_THRESHOLD
        and the team has an open roster slot at that prospect's position. Picks
        the highest-rated eligible prospect if multiple qualify.
        """
        from constants import PROSPECT_PROMOTION_RATING_THRESHOLD
        prospects = getattr(team, 'prospects', [])
        if not prospects:
            return None

        # Candidates must meet the rating floor AND have an open slot at their position
        candidates = []
        for p in prospects:
            if getattr(p, 'playerRating', 0) < PROSPECT_PROMOTION_RATING_THRESHOLD:
                continue
            openSlot = self._findOpenSlotForPosition(team, p.position.value)
            if openSlot:
                candidates.append((p, openSlot))
        if not candidates:
            return None

        best, slot = max(candidates, key=lambda c: c[0].playerRating)
        # Flip flags + move onto roster. Promoted prospects enter their first
        # pro season — reset seasonsPlayed + serviceTime so they show as a
        # rookie in listings (not a veteran from their time in the pipeline).
        best.is_prospect = False
        best.prospect_seasons = 0
        best.drafting_team_id = None
        best.seasonsPlayed = 0
        best.serviceTime = FloosPlayer.PlayerServiceTime.Rookie
        best.previousTeam = getattr(best, 'previousTeam', None)
        best.team = team  # Update runtime team ref so persistence saves team_id correctly
        # Defensive: legacy prospects may have been created before number
        # assignment was added — give them one now if missing.
        if not getattr(best, 'currentNumber', 0):
            team.assignPlayerNumber(best)
        team.rosterDict[slot] = best
        if best in team.prospects:
            team.prospects.remove(best)
        # Contract term for promoted prospect matches tier-based terms
        try:
            best.term = self._getPlayerTerm(best)
            best.termRemaining = best.term
        except Exception:
            best.termRemaining = 1
        freeAgencyDict.setdefault(team.name, []).append({
            'action': 'promote', 'player': best.name,
            'position': best.position.name, 'slot': slot,
        })
        leagueHighlights.insert(0, {
            'event': {'text': f"{team.name} promoted prospect {best.name} ({best.position.name}) to starter"}
        })
        return {
            'id': getattr(best, 'id', None),
            'name': best.name, 'slot': slot,
            'position': best.position.name,
            'rating': round(best.playerRating, 1),
            'tier': best.playerTier.name,
        }

    def snapshotRatingsForSeason(self, season: int) -> int:
        """Record every player's current rating into player_rating_history.

        Called at season start (after the prior offseason's training has
        applied) so each row captures the rating the player carries into
        that season. Idempotent via UNIQUE(player_id, season) — reruns
        update the existing row rather than creating duplicates.
        """
        try:
            from database.models import PlayerRatingHistory as DBHistory
        except ImportError:
            return 0
        if not (DATABASE_AVAILABLE and USE_DATABASE and self.db_session):
            return 0

        # Everyone with a rating — rostered, FA, prospects, upcoming rookies, retired
        allPlayers = list(self.activePlayers) + [
            p for p in self.retiredPlayers if p not in self.activePlayers
        ]
        snapshots = 0
        for player in allPlayers:
            rating = getattr(player, 'playerRating', None)
            if rating is None:
                continue
            existing = self.db_session.query(DBHistory).filter_by(
                player_id=player.id, season=season
            ).first()
            if existing is None:
                self.db_session.add(DBHistory(
                    player_id=player.id,
                    season=season,
                    rating=int(round(rating)),
                    offensive_rating=getattr(player, 'offensiveRating', None),
                    defensive_rating=getattr(player, 'defensiveRating', None),
                ))
                snapshots += 1
            else:
                existing.rating = int(round(rating))
                existing.offensive_rating = getattr(player, 'offensiveRating', None)
                existing.defensive_rating = getattr(player, 'defensiveRating', None)
        try:
            self.db_session.commit()
        except Exception as e:
            self.db_session.rollback()
            logger.warning(f"Rating history snapshot failed for season {season}: {e}")
            return 0
        logger.info(f"Rating history: snapshotted {snapshots} new entries for season {season}")
        return snapshots

    def _advanceProspectWindow(self) -> dict:
        """Increment prospect_seasons on every prospect; release washouts to the FA pool.

        Called once per offseason after training. Prospects past
        PROSPECT_DEVELOPMENT_WINDOW are released as free agents (with is_undrafted
        unchanged — 'washout' is implied by the prospect_seasons counter, not a
        separate flag). Returns a summary dict for logging/broadcasting.
        """
        from constants import PROSPECT_DEVELOPMENT_WINDOW
        teamManager = self.serviceContainer.getService('team_manager')
        released = []
        retained = 0
        if not teamManager:
            return {"released": [], "retained": 0}
        for team in teamManager.teams:
            keep = []
            for prospect in list(getattr(team, 'prospects', [])):
                prospect.prospect_seasons = (getattr(prospect, 'prospect_seasons', 0) or 0) + 1
                if prospect.prospect_seasons >= PROSPECT_DEVELOPMENT_WINDOW:
                    # Release: flip flags, move to FA pool. Prospects who wash
                    # out never played a pro game — keep them at Rookie service
                    # time / 0 seasonsPlayed so they land in the FA pool as a
                    # rookie, not a veteran.
                    prospect.is_prospect = False
                    prospect.drafting_team_id = None
                    prospect.team = 'Free Agent'
                    prospect.freeAgentYears = 0
                    prospect.seasonsPlayed = 0
                    prospect.serviceTime = FloosPlayer.PlayerServiceTime.Rookie
                    if prospect not in self.freeAgents:
                        self.freeAgents.append(prospect)
                    released.append({
                        "playerId": prospect.id,
                        "name": prospect.name,
                        "position": prospect.position.name,
                        "rating": round(getattr(prospect, 'playerRating', 0), 1),
                        "fromTeam": team.name,
                    })
                else:
                    keep.append(prospect)
                    retained += 1
            team.prospects = keep
        if released:
            logger.info(f"Prospect window: released {len(released)} washouts, {retained} prospects retained")
        return {"released": released, "retained": retained}

    def _leftThisTeamThisOffseason(self, player, team) -> bool:
        """True if this player was just released by THIS team this offseason —
        cut by fan vote, or expired and not re-signed.

        Both exits stamp the player identically: previousTeam = the team's name
        and freeAgentYears = 0. So a year-0 free agent whose previous team is
        this one walked out the door this offseason, and the team shouldn't
        auto-re-sign them right back in the same FA draft (the fans either voted
        them out or chose not to keep them). Other teams may still sign them;
        only the team that let them go is blocked, and only for this draft — next
        offseason their freeAgentYears is >= 1, so the block lifts on its own.
        """
        return (
            getattr(player, 'previousTeam', None) == team.name
            and getattr(player, 'freeAgentYears', 1) == 0
        )

    def _attemptRosterFill(self, team, teams, freeAgentQbList, freeAgentRbList, freeAgentWrList,
                          freeAgentTeList, freeAgentKList, freeAgencyDict, leagueHighlights,
                          eventLog=None) -> bool:
        """Sign or promote the best player available — comparing FAs *and*
        the team's prospects across all open roster slots.

        Old behavior was: pick a random open slot, then sign the best FA at
        that position. New behavior:
          1. For each position with an open slot, gather the best FA and
             the best prospect at that position.
          2. Pick the highest-rated overall (by playerRating).
          3. If it's an FA, sign them. If it's a prospect, promote them.

        This makes prospect auto-promotion conditional on actually being the
        top player on the board rather than firing eagerly above a fixed
        rating floor — the user's "best player available" intent.

        Returns True if roster is complete after this turn, False otherwise.
        """
        # Position value → list of slots, and position value → FA list.
        POS_TO_SLOTS = {1: ['qb'], 2: ['rb'], 3: ['wr1', 'wr2'], 4: ['te'], 5: ['k']}
        POS_TO_FALIST = {
            1: freeAgentQbList, 2: freeAgentRbList, 3: freeAgentWrList,
            4: freeAgentTeList, 5: freeAgentKList,
        }

        # First open slot per position (None if all slots at that position filled).
        firstOpenSlotByPos = {}
        for posVal, slots in POS_TO_SLOTS.items():
            for s in slots:
                if team.rosterDict.get(s) is None:
                    firstOpenSlotByPos[posVal] = s
                    break

        # No open slots → roster complete.
        if not firstOpenSlotByPos:
            return True

        # Build candidates: for each open position, best FA + best prospect.
        # A team may not re-sign a player it just released this offseason (cut by
        # fan vote, or expired and not kept), so the best *signable* FA skips
        # those. Fall back to allowing them only if there's nothing else on the
        # board — a roster hole the sim can't run with is worse than overriding
        # the fans for a single slot.
        prospects = getattr(team, 'prospects', []) or []

        def _gather(applyReleaseBlock):
            cands = []  # (slot, player, kind) where kind ∈ {'fa', 'prospect'}
            for posVal, slot in firstOpenSlotByPos.items():
                faList = POS_TO_FALIST.get(posVal, [])
                if applyReleaseBlock:
                    bestFa = next(
                        (p for p in faList if not self._leftThisTeamThisOffseason(p, team)),
                        None,
                    )
                else:
                    bestFa = faList[0] if faList else None
                if bestFa is not None:
                    cands.append((slot, bestFa, 'fa'))
                posProspects = [p for p in prospects if p.position.value == posVal]
                if posProspects:
                    best = max(posProspects, key=lambda p: getattr(p, 'playerRating', 0))
                    cands.append((slot, best, 'prospect'))
            return cands

        candidates = _gather(applyReleaseBlock=True) or _gather(applyReleaseBlock=False)
        if not candidates:
            return False  # open slots exist but no FAs or prospects to fill them

        def _rating(c):
            return getattr(c[1], 'playerRating', getattr(c[1].attributes, 'skillRating', 0))

        # Fan position priority (set by the FA ballot's "fill order"): when present,
        # fill the highest-priority OPEN position first — best player there —
        # OVERRIDING pure rating, so a team that ranked QB/WR ahead of K won't grab
        # a higher-rated kicker first. Positions no fan ranked fall to the back,
        # tie-broken by rating. No priority set -> best-rated overall (legacy).
        priority = getattr(self, '_gmFaPositionPriority', {}).get(getattr(team, 'id', None))
        if priority:
            def _prioKey(c):
                posVal = getattr(getattr(c[1], 'position', None), 'value', None)
                idx = priority.index(posVal) if posVal in priority else len(priority)
                return (idx, -_rating(c))
            slot, candidate, kind = min(candidates, key=_prioKey)
        else:
            slot, candidate, kind = max(candidates, key=_rating)

        teamAbbr = getattr(team, 'abbr', team.name[:3].upper())

        if kind == 'fa':
            # Stale-list defense: if the chosen player is already on a
            # roster (race conditions / promoted prospect leakage), purge.
            for other_team in [t for t in teams if t != team]:
                for pos_key, roster_player in other_team.rosterDict.items():
                    if roster_player is not None and roster_player.id == candidate.id:
                        logger.error(f"BUG: {candidate.name} in free agent list but already on {other_team.name} at {pos_key}! Removing from FA lists.")
                        faList = POS_TO_FALIST[candidate.position.value]
                        if candidate in faList:
                            faList.remove(candidate)
                        if candidate in self.freeAgents:
                            self.freeAgents.remove(candidate)
                        return False

            selectedPlayer = candidate
            POS_TO_FALIST[selectedPlayer.position.value].remove(selectedPlayer)
            if selectedPlayer in self.freeAgents:
                self.freeAgents.remove(selectedPlayer)
            else:
                logger.warning(f"Player {selectedPlayer.name} not found in self.freeAgents when signing to {team.name}")

            selectedPlayer.team = team
            selectedPlayer.freeAgentYears = 0
            team.rosterDict[slot] = selectedPlayer
            team.assignPlayerNumber(selectedPlayer)
            selectedPlayer.term = self._getPlayerTerm(selectedPlayer)
            selectedPlayer.termRemaining = selectedPlayer.term

            transactionId = f"{team.name}_{selectedPlayer.name}"
            freeAgencyDict[transactionId] = {
                'name': selectedPlayer.name,
                'pos': selectedPlayer.position.name,
                'rating': selectedPlayer.attributes.skillRating,
                'tier': selectedPlayer.playerTier.value,
                'term': selectedPlayer.term,
                'previousTeam': getattr(selectedPlayer, 'previousTeam', 'Rookie'),
                'roster': 'Starting'
            }

            leagueHighlights.insert(0, {
                'event': {'text': f'{team.name} signed {selectedPlayer.name} ({selectedPlayer.position.name}) for {selectedPlayer.term} season(s)'}
            })

            if eventLog is not None:
                eventLog.append({
                    'type': 'pick',
                    'team': team.name,
                    'teamAbbr': teamAbbr,
                    'playerId': getattr(selectedPlayer, 'id', None),
                    'player': selectedPlayer.name,
                    'position': selectedPlayer.position.name,
                    'rating': round(selectedPlayer.playerRating, 1),
                    'tier': selectedPlayer.playerTier.name,
                    'slot': slot,
                })

            logger.debug(f"{team.name} filled {slot} with FA {selectedPlayer.name}")
        else:
            # kind == 'prospect' — promote the chosen prospect into the slot.
            promoted = candidate
            promoted.is_prospect = False
            promoted.prospect_seasons = 0
            promoted.drafting_team_id = None
            promoted.seasonsPlayed = 0
            promoted.serviceTime = FloosPlayer.PlayerServiceTime.Rookie
            promoted.team = team
            team.rosterDict[slot] = promoted
            if promoted in team.prospects:
                team.prospects.remove(promoted)
            try:
                promoted.term = self._getPlayerTerm(promoted)
                promoted.termRemaining = promoted.term
            except Exception:
                promoted.termRemaining = 1

            freeAgencyDict.setdefault(team.name, []).append({
                'action': 'promote', 'player': promoted.name,
                'position': promoted.position.name, 'slot': slot,
            })
            leagueHighlights.insert(0, {
                'event': {'text': f"{team.name} promoted prospect {promoted.name} ({promoted.position.name}) to starter"}
            })

            if eventLog is not None:
                eventLog.append({
                    'type': 'pick',
                    'team': team.name,
                    'teamAbbr': teamAbbr,
                    'playerId': getattr(promoted, 'id', None),
                    'player': promoted.name,
                    'position': promoted.position.name,
                    'rating': round(promoted.playerRating, 1),
                    'tier': promoted.playerTier.name,
                    'isPromotion': True,
                    'slot': slot,
                })

            logger.debug(f"{team.name} filled {slot} with promoted prospect {promoted.name}")
        # Check if roster is now complete
        remaining = [k for k in ('qb', 'rb', 'wr1', 'wr2', 'te', 'k') if team.rosterDict.get(k) is None]
        return len(remaining) == 0

    def releasePlayerToFreeAgency(self, player, team, freeAgentLists: dict) -> None:
        """Release a rostered player to the free agent pool (GM Mode cut)."""
        # Find and clear roster slot
        for pos, rostered in list(team.rosterDict.items()):
            if rostered is not None and rostered.id == player.id:
                team.rosterDict[pos] = None
                break
        # Remove number
        if hasattr(player, 'currentNumber') and player.currentNumber in team.playerNumbersList:
            team.playerNumbersList.remove(player.currentNumber)
        player.previousTeam = team.name
        player.team = 'Free Agent'
        player.freeAgentYears = 0
        if player not in self.freeAgents:
            self.freeAgents.append(player)
        # Add to position-specific list
        posVal = player.position.value
        posListMap = {1: 'qb', 2: 'rb', 3: 'wr', 4: 'te', 5: 'k'}
        listKey = posListMap.get(posVal)
        if listKey and listKey in freeAgentLists:
            freeAgentLists[listKey].append(player)
            freeAgentLists[listKey].sort(key=lambda p: p.attributes.skillRating, reverse=True)
        logger.info(f"GM cut: {player.name} released from {team.name} to FA pool")

    def _findOpenSlotForPosition(self, team, positionValue: int) -> str:
        """Find an open roster slot matching a position value. Returns slot key or None."""
        posSlots = {1: ['qb'], 2: ['rb'], 3: ['wr1', 'wr2'], 4: ['te'], 5: ['k']}
        candidates = posSlots.get(positionValue, [])
        for slot in candidates:
            if team.rosterDict.get(slot) is None:
                return slot
        return None

    def _signPlayer(self, team, player, slot: str, faList: list,
                    freeAgencyDict: dict, leagueHighlights: list,
                    eventLog: list = None, allFaLists: dict = None) -> None:
        """Sign a player from the FA pool to a specific roster slot."""
        # Remove from the specific position list
        if player in faList:
            faList.remove(player)
        # Also remove from any other position lists (defensive cleanup)
        if allFaLists:
            seen = set()
            for faL in allFaLists.values():
                listId = id(faL)
                if listId in seen or faL is faList:
                    continue
                seen.add(listId)
                if player in faL:
                    faL.remove(player)
        if player in self.freeAgents:
            self.freeAgents.remove(player)
        player.team = team
        player.freeAgentYears = 0
        team.rosterDict[slot] = player
        team.assignPlayerNumber(player)
        player.term = self._getPlayerTerm(player)
        player.termRemaining = player.term
        txId = f"{team.name}_{player.name}"
        freeAgencyDict[txId] = {
            'name': player.name, 'pos': player.position.name,
            'rating': player.attributes.skillRating,
            'tier': player.playerTier.value, 'term': player.term,
            'previousTeam': getattr(player, 'previousTeam', 'Rookie'),
            'roster': 'Starting',
        }
        leagueHighlights.insert(0, {
            'event': {'text': f'{team.name} signed {player.name} ({player.position.name}) for {player.term} season(s)'}
        })
        if eventLog is not None:
            teamAbbr = getattr(team, 'abbr', team.name[:3].upper())
            eventLog.append({
                'type': 'pick', 'team': team.name, 'teamAbbr': teamAbbr,
                'player': player.name, 'position': player.position.name,
                'rating': round(player.playerRating, 1), 'tier': player.playerTier.name,
            })

    def _executeRosterSigning(self, team, position, newPlayer, freeAgencyDict, leagueHighlights, freeAgentLists=None):
        """Execute signing a player to fill an open roster spot"""
        # TODO: capHit feature not fully developed - disabled for now
        # if hasattr(team, 'playerCap'):
        #     team.playerCap += getattr(newPlayer, 'capHit', newPlayer.playerTier.value)
        
        # Sign new player (remove from free agents, already in activePlayers and position lists)
        if newPlayer in self.freeAgents:
            self.freeAgents.remove(newPlayer)
        
        # Also remove from position-specific free agent lists to prevent double-signing
        if freeAgentLists:
            for fa_list in freeAgentLists.values():
                if newPlayer in fa_list:
                    fa_list.remove(newPlayer)
        
        newPlayer.team = team
        newPlayer.freeAgentYears = 0
        
        # Set contract terms
        newPlayer.term = self._getPlayerTerm(newPlayer)
        newPlayer.termRemaining = newPlayer.term
        
        # Assign to roster
        team.rosterDict[position] = newPlayer
        team.assignPlayerNumber(newPlayer)
        
        # Record transaction
        transactionId = f"{team.name}_signed_{newPlayer.name}"
        freeAgencyDict[transactionId] = {
            'team': team.name,
            'signed': newPlayer.name,
            'position': position,
            'tier': newPlayer.playerTier.name,
            'term': newPlayer.term
        }
        
        # Add highlight
        leagueHighlights.insert(0, {
            'event': {'text': f'{team.city} {team.name} signed {newPlayer.name} ({newPlayer.playerTier.name}) for {newPlayer.term} season(s)'}
        })
        
        logger.debug(f"{team.name} signed {newPlayer.name} to fill {position}")
    
    def _updatePlayerServiceTime(self, player) -> None:
        """Update player service time based on seasons played"""
        import floosball_player as FloosPlayer
        
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
    
    def calculateSalaryCaps(self) -> Dict[str, Any]:
        """
        Calculate and return salary cap information for all teams
        """
        teamManager = self.serviceContainer.getService('team_manager')
        teams = teamManager.teams if teamManager else []
        
        salaryCapInfo = {
            'teams': [],
            'totalSalaryCap': 0,
            'averageSalaryCap': 0,
            'salaryCapRange': {'min': float('inf'), 'max': 0}
        }
        
        for team in teams:
            teamCap = getattr(team, 'playerCap', 0)
            salaryCapInfo['teams'].append({
                'teamName': team.name,
                'salaryCap': teamCap,
                'rosterCount': len([p for p in team.rosterDict.values() if p is not None])
            })
            
            salaryCapInfo['totalSalaryCap'] += teamCap
            salaryCapInfo['salaryCapRange']['min'] = min(salaryCapInfo['salaryCapRange']['min'], teamCap)
            salaryCapInfo['salaryCapRange']['max'] = max(salaryCapInfo['salaryCapRange']['max'], teamCap)
        
        if teams:
            salaryCapInfo['averageSalaryCap'] = round(salaryCapInfo['totalSalaryCap'] / len(teams), 2)
        
        # Handle case where no teams exist
        if salaryCapInfo['salaryCapRange']['min'] == float('inf'):
            salaryCapInfo['salaryCapRange']['min'] = 0
        
        return salaryCapInfo
    
    def assignPlayerCapHits(self) -> None:
        """
        Assign cap hit values to players based on their tier
        Should be called during player initialization
        """
        logger.info("Assigning cap hit values to players")
        
        # Process active players
        for player in self.activePlayers:
            if not hasattr(player, 'capHit') or player.capHit == 0:
                player.capHit = self._calculateCapHit(player)
        
        # Process free agents
        for player in self.freeAgents:
            if not hasattr(player, 'capHit') or player.capHit == 0:
                player.capHit = self._calculateCapHit(player)
        
        logger.info("Cap hit assignment complete")
    
    def _calculateCapHit(self, player) -> int:
        """Calculate cap hit based on player tier"""
        import floosball_player as FloosPlayer
        
        tier_cap_hits = {
            FloosPlayer.PlayerTier.TierS: 5,
            FloosPlayer.PlayerTier.TierA: 4,
            FloosPlayer.PlayerTier.TierB: 3,
            FloosPlayer.PlayerTier.TierC: 2,
            FloosPlayer.PlayerTier.TierD: 1
        }
        
        return tier_cap_hits.get(player.playerTier, 2)

    def validateSalaryCaps(self) -> Dict[str, Any]:
        """
        Validate salary caps for all teams and identify any issues
        """
        teamManager = self.serviceContainer.getService('team_manager')
        teams = teamManager.teams if teamManager else []
        
        validation_results = {
            'valid_teams': [],
            'invalid_teams': [],
            'warnings': [],
            'total_issues': 0
        }
        
        for team in teams:
            calculated_cap = 0
            roster_issues = []
            
            # Calculate expected cap from roster
            for position, player in team.rosterDict.items():
                if player is not None:
                    player_cap = getattr(player, 'capHit', 0)
                    calculated_cap += player_cap
                    
                    # Check for missing cap hit
                    if player_cap == 0:
                        roster_issues.append(f"{position}: {player.name} has no cap hit")
            
            stored_cap = getattr(team, 'playerCap', 0)
            
            team_result = {
                'team': team.name,
                'stored_cap': stored_cap,
                'calculated_cap': calculated_cap,
                'difference': stored_cap - calculated_cap,
                'issues': roster_issues
            }
            
            if abs(stored_cap - calculated_cap) > 0.01 or roster_issues:
                validation_results['invalid_teams'].append(team_result)
                validation_results['total_issues'] += 1
            else:
                validation_results['valid_teams'].append(team_result)
        
        logger.info(f"Salary cap validation: {len(validation_results['valid_teams'])} valid, "
                   f"{len(validation_results['invalid_teams'])} invalid")
        
        return validation_results