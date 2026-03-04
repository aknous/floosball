"""
PlayerManager - Manages player lifecycle, lists, and organization
Replaces the scattered player-related global variables and functions in floosball.py
"""

from typing import List, Optional, Dict, Any
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
            
            # Set up season stats dict if not present
            if not hasattr(player, 'seasonStatsDict') or player.seasonStatsDict is None:
                player.seasonStatsDict = player.careerStatsDict.copy() if hasattr(player, 'careerStatsDict') else {}
            
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
            
            # Set loaded players as active players
            self.activePlayers = loaded_players
            
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
            player.term = db_player.term
            player.termRemaining = db_player.term_remaining
            player.capHit = db_player.cap_hit
            player.playerRating = db_player.player_rating
            player.freeAgentYears = db_player.free_agent_years
            
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
                attrs = db_player.attributes
                player.attributes.overallRating = attrs.overall_rating
                player.attributes.speed = attrs.speed
                player.attributes.hands = attrs.hands
                player.attributes.agility = attrs.agility
                player.attributes.power = attrs.power
                player.attributes.armStrength = attrs.arm_strength
                player.attributes.accuracy = attrs.accuracy
                player.attributes.legStrength = attrs.leg_strength
                player.attributes.skillRating = attrs.skill_rating
                player.attributes.potentialSpeed = attrs.potential_speed
                player.attributes.potentialHands = attrs.potential_hands
                player.attributes.potentialAgility = attrs.potential_agility
                player.attributes.potentialPower = attrs.potential_power
                player.attributes.potentialArmStrength = attrs.potential_arm_strength
                player.attributes.potentialAccuracy = attrs.potential_accuracy
                player.attributes.potentialLegStrength = attrs.potential_leg_strength
                player.attributes.potentialSkillRating = attrs.potential_skill_rating
                player.attributes.routeRunning = attrs.route_running
                player.attributes.vision = attrs.vision
                player.attributes.blocking = attrs.blocking
                player.attributes.discipline = attrs.discipline
                player.attributes.attitude = attrs.attitude
                player.attributes.focus = attrs.focus
                player.attributes.instinct = attrs.instinct
                player.attributes.creativity = attrs.creativity
                player.attributes.resilience = attrs.resilience
                player.attributes.clutchFactor = attrs.clutch_factor
                player.attributes.pressureHandling = attrs.pressure_handling
                player.attributes.longevity = attrs.longevity
                player.attributes.playMakingAbility = attrs.play_making_ability
                player.attributes.xFactor = attrs.x_factor
                player.attributes.confidenceModifier = attrs.confidence_modifier
                player.attributes.determinationModifier = attrs.determination_modifier
                player.attributes.luckModifier = attrs.luck_modifier
            
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
                        player.term = self._getPlayerTerm(player.playerTier)
                        player.termRemaining = player.term
                    contract_fixes += 1
                    logger.info(f"Fixed contract for {player.name}: term={player.term}, termRemaining={player.termRemaining}")
            else:
                # Player missing contract attributes - initialize them
                player.term = self._getPlayerTerm(player.playerTier)
                player.termRemaining = player.term
                contract_fixes += 1
                logger.info(f"Initialized contract for {player.name}: term={player.term}, termRemaining={player.termRemaining}")
        
        if contract_fixes > 0:
            logger.info(f"Fixed contract state for {contract_fixes} players during team assignment")
        
        for player in self.activePlayers:
            if not hasattr(player, 'team') or player.team is None:
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
        
        logger.info(f"Assigned {assigned_count} players to team rosters")
    
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
        
        # Generate player skill seeds like original code
        meanPlayerSkill = 80
        stdDevPlayerSkill = 7
        playerAverages = np.random.normal(meanPlayerSkill, stdDevPlayerSkill, totalPlayers)
        playerAverages = np.clip(playerAverages, 60, 100)
        playerAverages = playerAverages.tolist()
        
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
            
            if position and playerAverages:
                seed = int(playerAverages.pop(randint(0, len(playerAverages) - 1)))
                player = self.createPlayer(position, seed)
                if player:
                    player.id = playerId
                    playerId += 1
                    self.activePlayers.append(player)
                    self.addToPositionList(player)
    
    def createPlayer(self, position: FloosPlayer.Position, physicalSeed: int = None, mentalSeed: int = None) -> Optional[FloosPlayer.Player]:
        """Create a single player of specified position"""
        from random import randint
        
        if not self.unusedNames:
            logger.warning("No more unused names available")
            return None
        
        # Use same logic as original: pick random index and pop
        nameIndex = randint(0, len(self.unusedNames) - 1)
        name = self.unusedNames.pop(nameIndex)
        
        # Generate default seeds if not provided
        if physicalSeed is None:
            physicalSeed = randint(60, 100)
        if mentalSeed is None:
            mentalSeed = randint(60, 100)
        
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
    
    def _getPlayerTerm(self, tier: FloosPlayer.PlayerTier) -> int:
        """Get contract term based on tier with random ranges like original getPlayerTerm function"""
        from random import randint
        
        if tier == FloosPlayer.PlayerTier.TierS:
            return randint(4, 6)  # S-tier: 4-6 years
        elif tier == FloosPlayer.PlayerTier.TierA:
            return randint(3, 4)  # A-tier: 3-4 years  
        elif tier == FloosPlayer.PlayerTier.TierD:
            return 1  # D-tier: 1 year
        else:
            return randint(1, 3)  # B/C-tier: 1-3 years
    
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
                    selectedPlayer.term = self._getPlayerTerm(selectedPlayer.playerTier)
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
        player.team = None
        
        # Add to retirement lists
        self.retiredPlayers.append(player)
        self.newlyRetiredPlayers.append(player)
    
    def promoteToHallOfFame(self, player: FloosPlayer.Player) -> None:
        """Promote retired player to Hall of Fame"""
        if player not in self.retiredPlayers:
            logger.warning(f"Cannot promote {player.name} - not in retired players")
            return
        
        logger.info(f"Promoting {player.name} to Hall of Fame")
        
        # Move from retired to HoF
        self.retiredPlayers.remove(player)
        self.hallOfFame.append(player)
        
        # Could publish event here for achievements/notifications
        # self.serviceContainer.getService('eventManager').publish('playerHofInduction', player)
    
    def sortPlayersByPosition(self) -> None:
        """Sort players and assign tiers (replaces sortPlayers function)"""
        logger.debug("Sorting players and assigning tiers")
        
        # Assign player tiers for realistic distribution:
        # S (~2-3%): Superstar/Generational
        # A (~8-10%): Great/Franchise  
        # B (~25-30%): Good
        # C (~40-45%): Average
        # D (~15-20%): Bad
        tierS = 93  # Top ~2-3%
        tierA = 87  # Next ~8-10%
        tierB = 77  # Next ~25-30%
        tierC = 69  # Next ~40-45%
        # Below 69 = Tier D (~15-20%)
        
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
        """Find player by ID across all lists"""
        # Search active players
        for player in self.activePlayers:
            if player.id == playerId:
                return player
        
        # Search retired players
        for player in self.retiredPlayers:
            if player.id == playerId:
                return player
        
        # Search hall of fame
        for player in self.hallOfFame:
            if player.id == playerId:
                return player
        
        # Search free agents
        for player in self.freeAgents:
            if player.id == playerId:
                return player
        
        return None
    
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
    
    def loadCurrentSeasonStats(self, seasonNumber: int) -> None:
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
                # Keep StatTracker pointing at the restored dict so stats accumulated
                # during subsequent games go to the right place.
                player.stat_tracker.season_stats_dict = player.seasonStatsDict
                restored += 1
            logger.info(f"Restored season {seasonNumber} stats for {restored} players")
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
            team_id_stats = {'with_team': 0, 'free_agent': 0, 'retired': 0, 'null': 0, 'errors': 0}
            
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
                        # player.team is 'Free Agent' or 'Retired' - save as None
                        team_id = None
                        if player.team == 'Retired':
                            team_id_stats['retired'] += 1
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
                        player_rating=player.playerRating,
                        free_agent_years=player.freeAgentYears,
                        service_time=player.serviceTime.name if hasattr(player, 'serviceTime') else None,
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
                    db_player.player_rating = player.playerRating
                    db_player.free_agent_years = player.freeAgentYears
                    db_player.service_time = player.serviceTime.name if hasattr(player, 'serviceTime') else None
                
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
                            agility=attrs.agility,
                            power=attrs.power,
                            arm_strength=attrs.armStrength,
                            accuracy=attrs.accuracy,
                            leg_strength=attrs.legStrength,
                            skill_rating=attrs.skillRating,
                            potential_speed=attrs.potentialSpeed,
                            potential_hands=attrs.potentialHands,
                            potential_agility=attrs.potentialAgility,
                            potential_power=attrs.potentialPower,
                            potential_arm_strength=attrs.potentialArmStrength,
                            potential_accuracy=attrs.potentialAccuracy,
                            potential_leg_strength=attrs.potentialLegStrength,
                            potential_skill_rating=attrs.potentialSkillRating,
                            route_running=attrs.routeRunning,
                            vision=attrs.vision,
                            blocking=attrs.blocking,
                            discipline=attrs.discipline,
                            attitude=attrs.attitude,
                            focus=attrs.focus,
                            instinct=attrs.instinct,
                            creativity=attrs.creativity,
                            resilience=attrs.resilience,
                            clutch_factor=attrs.clutchFactor,
                            pressure_handling=attrs.pressureHandling,
                            longevity=attrs.longevity,
                            play_making_ability=attrs.playMakingAbility,
                            x_factor=attrs.xFactor,
                            confidence_modifier=attrs.confidenceModifier,
                            determination_modifier=attrs.determinationModifier,
                            luck_modifier=attrs.luckModifier,
                        )
                        self.db_session.add(db_attrs)
                    else:
                        # Update existing attributes
                        db_attrs.overall_rating = attrs.overallRating
                        db_attrs.speed = attrs.speed
                        db_attrs.hands = attrs.hands
                        db_attrs.agility = attrs.agility
                        db_attrs.power = attrs.power
                        db_attrs.arm_strength = attrs.armStrength
                        db_attrs.accuracy = attrs.accuracy
                        db_attrs.leg_strength = attrs.legStrength
                        db_attrs.skill_rating = attrs.skillRating
                        db_attrs.potential_speed = attrs.potentialSpeed
                        db_attrs.potential_hands = attrs.potentialHands
                        db_attrs.potential_agility = attrs.potentialAgility
                        db_attrs.potential_power = attrs.potentialPower
                        db_attrs.potential_arm_strength = attrs.potentialArmStrength
                        db_attrs.potential_accuracy = attrs.potentialAccuracy
                        db_attrs.potential_leg_strength = attrs.potentialLegStrength
                        db_attrs.potential_skill_rating = attrs.potentialSkillRating
                        db_attrs.route_running = attrs.routeRunning
                        db_attrs.vision = attrs.vision
                        db_attrs.blocking = attrs.blocking
                        db_attrs.discipline = attrs.discipline
                        db_attrs.attitude = attrs.attitude
                        db_attrs.focus = attrs.focus
                        db_attrs.instinct = attrs.instinct
                        db_attrs.creativity = attrs.creativity
                        db_attrs.resilience = attrs.resilience
                        db_attrs.clutch_factor = attrs.clutchFactor
                        db_attrs.pressure_handling = attrs.pressureHandling
                        db_attrs.longevity = attrs.longevity
                        db_attrs.play_making_ability = attrs.playMakingAbility
                        db_attrs.x_factor = attrs.xFactor
                        db_attrs.confidence_modifier = attrs.confidenceModifier
                        db_attrs.determination_modifier = attrs.determinationModifier
                        db_attrs.luck_modifier = attrs.luckModifier
                
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
                        # Update JSON
                        db_career_stats.passing_stats = stats_dict.get('passing')
                        db_career_stats.rushing_stats = stats_dict.get('rushing')
                        db_career_stats.receiving_stats = stats_dict.get('receiving')
                        db_career_stats.kicking_stats = stats_dict.get('kicking')
                        db_career_stats.defense_stats = stats_dict.get('defense')
                
                # Save season stats (if we have a current season)
                season_manager = self.serviceContainer.getService('season_manager')
                if season_manager and hasattr(season_manager, 'currentSeason') and season_manager.currentSeason:
                    current_season = season_manager.currentSeason.seasonNumber
                    
                    if hasattr(player, 'seasonStatsDict') and player.seasonStatsDict:
                        db_season_stats = self.db_session.query(PlayerSeasonStats).filter_by(
                            player_id=player.id, season=current_season
                        ).first()
                        
                        season_dict = player.seasonStatsDict
                        
                        # Extract denormalized stats from JSON
                        s_passing = season_dict.get('passing') or {}
                        s_rushing = season_dict.get('rushing') or {}
                        s_receiving = season_dict.get('receiving') or {}
                        s_defense = season_dict.get('defense') or {}
                        
                        if db_season_stats is None:
                            db_season_stats = PlayerSeasonStats(
                                player_id=player.id,
                                season=current_season,
                                team_id=player.teamId if hasattr(player, 'teamId') else None,
                                games_played=season_dict.get('gamesPlayed', 0),
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
                                receptions=s_receiving.get('recs', 0),
                                # Denormalized defensive stats
                                sacks=s_defense.get('sacks', 0),
                                interceptions=s_defense.get('ints', 0),
                                tackles=s_defense.get('tackles', 0),
                                # JSON for detailed stats
                                passing_stats=season_dict.get('passing'),
                                rushing_stats=season_dict.get('rushing'),
                                receiving_stats=season_dict.get('receiving'),
                                kicking_stats=season_dict.get('kicking'),
                                defense_stats=season_dict.get('defense'),
                            )
                            self.db_session.add(db_season_stats)
                        else:
                            db_season_stats.team_id = player.teamId if hasattr(player, 'teamId') else None
                            db_season_stats.games_played = season_dict.get('gamesPlayed', 0)
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
                            db_season_stats.receptions = s_receiving.get('recs', 0)
                            # Update denormalized defensive stats
                            db_season_stats.sacks = s_defense.get('sacks', 0)
                            db_season_stats.interceptions = s_defense.get('ints', 0)
                            db_season_stats.tackles = s_defense.get('tackles', 0)
                            # Update JSON
                            db_season_stats.passing_stats = season_dict.get('passing')
                            db_season_stats.rushing_stats = season_dict.get('rushing')
                            db_season_stats.receiving_stats = season_dict.get('receiving')
                            db_season_stats.kicking_stats = season_dict.get('kicking')
                            db_season_stats.defense_stats = season_dict.get('defense')
            
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
            from database.models import UnusedName
            
            # Clear existing unused names
            self.db_session.query(UnusedName).delete()
            self.db_session.flush()  # Ensure delete is committed before insert
            
            # Add current unused names
            self.name_repo.add_names_batch(self.unusedNames)
            self.db_session.commit()
            
            logger.info(f"Saved {len(self.unusedNames)} unused names to database")
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
    
    def handleOffseasonActivities(self) -> None:
        """Handle end-of-season player activities"""
        logger.info("Processing offseason player activities")
        
        # Apply offseason training to all active players
        for player in self.activePlayers:
            player.offseasonTraining()
        
        # Check for retirements
        self.processRetirements()
        
        # Check for Hall of Fame promotions (using original logic)
        self.inductHallOfFame()
        
        # Additional HoF promotions for edge cases
        self.processHofPromotions()
    
    def processRetirements(self) -> None:
        """Process player retirements"""
        retirementCandidates = []
        
        for player in self.activePlayers:
            # Retirement logic (adjust criteria as needed)
            if (player.seasonsPlayed > 15 or 
                (player.seasonsPlayed > 10 and player.playerRating < 70) or
                player.seasonsPlayed > 20):
                retirementCandidates.append(player)
        
        for player in retirementCandidates:
            self.retirePlayer(player)
    
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
    
    def inductHallOfFame(self) -> None:
        """Induct newly retired players into Hall of Fame (matches original inductHallOfFame function)"""
        if len(self.newlyRetiredPlayers) > 0:
            for player in self.newlyRetiredPlayers:
                # HoF criteria from original: TierS players or TierA players with championships
                if player.playerTier.value == 5:  # TierS
                    self.hallOfFame.append(player)
                    # Add highlight if season context is available
                    seasonManager = self.serviceContainer.getService('season_manager')
                    if seasonManager and seasonManager.currentSeason and hasattr(seasonManager.currentSeason, 'leagueHighlights'):
                        highlight = {
                            'event': {
                                'text': f'{player.name} has been inducted into the Floosball Hall of Fame'
                            }
                        }
                        seasonManager.currentSeason.leagueHighlights.insert(0, highlight)
                elif player.playerTier.value == 4 and hasattr(player, 'leagueChampionships') and len(player.leagueChampionships):  # TierA with championships
                    self.hallOfFame.append(player)
                    # Add highlight if season context is available  
                    seasonManager = self.serviceContainer.getService('season_manager')
                    if seasonManager and seasonManager.currentSeason and hasattr(seasonManager.currentSeason, 'leagueHighlights'):
                        highlight = {
                            'event': {
                                'text': f'{player.name} has been inducted into the Floosball Hall of Fame'
                            }
                        }
                        seasonManager.currentSeason.leagueHighlights.insert(0, highlight)
            
            # Clear newly retired list
            self.newlyRetiredPlayers.clear()
    
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
                    player.playerRating = round(player.attributes.skillRating + adjustment)
        
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
                    player.playerRating = round(player.attributes.skillRating + adjustment)
        
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
                    player.playerRating = round(player.attributes.skillRating + adjustment)
        
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
                    player.playerRating = round(player.attributes.skillRating + adjustment)
        
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
                    player.playerRating = round(player.attributes.skillRating + adjustment)
        
        # Sort players by performance ratings
        self.activeQbs.sort(key=lambda player: getattr(player, 'seasonPerformanceRating', 0), reverse=True)
        self.activeRbs.sort(key=lambda player: getattr(player, 'seasonPerformanceRating', 0), reverse=True)
        self.activeWrs.sort(key=lambda player: getattr(player, 'seasonPerformanceRating', 0), reverse=True)
        self.activeTes.sort(key=lambda player: getattr(player, 'seasonPerformanceRating', 0), reverse=True)
        self.activeKs.sort(key=lambda player: getattr(player, 'seasonPerformanceRating', 0), reverse=True)
        
        logger.info(f"Performance ratings calculated for week {currentWeek}")
    
    def conductFreeAgencySimulation(self, freeAgencyOrder: List, currentSeason: int, leagueHighlights: List = None, eventLog: List = None) -> Dict[str, Any]:
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
        
        # Process free agent retirements (players with 3+ years as free agents)
        log_fa("\n=== FREE AGENT RETIREMENTS ===")
        self._processFreeAgentRetirements(currentSeason, leagueHighlights)
        
        # Generate replacement players for retired players
        log_fa("\n=== REPLACEMENT PLAYERS GENERATED ===")
        self._generateReplacementPlayers(currentSeason)
        
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
        
        if not teams:
            logger.error("No teams available for free agency!")
            return freeAgencyDict
        
        # Initialize team completion status and cuts available
        for team in teams:
            team.freeAgencyComplete = False
            team.cutsAvailable = 2  # Each team gets 2 cuts per season
        
        logger.info(f"Free agency starting with {len(self.freeAgents)} free agents and {len(teams)} teams")
        
        # MULTI-ROUND FREE AGENCY PROCESS - matches original exactly
        teamsComplete = 0
        roundNum = 0
        maxRounds = 100  # Safety valve to prevent infinite loops
        
        while teamsComplete < len(teams):
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
                
                # PHASE 1: Try to cut and upgrade players (if cuts available)
                if team.cutsAvailable > 0:
                    cutMade = self._attemptPlayerCutAndUpgrade(
                        team, freeAgentQbList, freeAgentRbList, freeAgentWrList,
                        freeAgentTeList, freeAgentKList, freeAgencyDict, leagueHighlights,
                        eventLog=eventLog
                    )
                    team.cutsAvailable -= 1  # Decrement cuts regardless of success
                    if cutMade:
                        continue  # If cut was made, skip roster fill this round

                # PHASE 2: Attempt to fill ONE open roster spot
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
    
    def _processFreeAgentRetirements(self, currentSeason: int, leagueHighlights: List) -> None:
        """Process retirements of long-term free agents"""
        retirements = []
        
        for player in self.freeAgents[:]:  # Use slice copy for safe iteration
            freeAgentYears = getattr(player, 'freeAgentYears', 0)
            
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
        meanPlayerSkill = 78
        stdDevPlayerSkill = 10
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
    
    def _attemptPlayerCutAndUpgrade(self, team, freeAgentQbList, freeAgentRbList, freeAgentWrList,
                                   freeAgentTeList, freeAgentKList, freeAgencyDict, leagueHighlights,
                                   eventLog=None) -> bool:
        """Attempt to cut current player and sign upgrade
        
        Prioritizes cutting low performers and signing A/S tier players.
        Teams will be more aggressive about cutting for elite talent.
        """
        from random import randint
        
        # Build list of eligible players to cut (tier <= 3), sorted by performance rating (worst first)
        eligibleCutCandidates = []
        for pos, player in team.rosterDict.items():
            if player is not None and player.playerTier.value <= 3:
                # Check if free agents available at this position
                hasFreeAgents = False
                if player.position.value == 1 and len(freeAgentQbList) > 0:  # QB
                    hasFreeAgents = True
                elif player.position.value == 2 and len(freeAgentRbList) > 0:  # RB
                    hasFreeAgents = True
                elif player.position.value == 3 and len(freeAgentWrList) > 0:  # WR
                    hasFreeAgents = True
                elif player.position.value == 4 and len(freeAgentTeList) > 0:  # TE
                    hasFreeAgents = True
                elif player.position.value == 5 and len(freeAgentKList) > 0:  # K
                    hasFreeAgents = True
                
                if hasFreeAgents:
                    eligibleCutCandidates.append((pos, player))
        
        # Sort by performance rating (lowest first) to prioritize cutting poor performers
        eligibleCutCandidates.sort(key=lambda x: x[1].seasonPerformanceRating)
        
        # GM skill determines evaluation range for free agents
        gmScore = getattr(team, 'gmScore', 1)
        
        # Try each candidate in order (worst performers first)
        for pos, currentPlayer in eligibleCutCandidates:
            compPlayer = None
            
            # Get free agent list for this position
            freeAgentList = None
            if pos == 'qb':
                freeAgentList = freeAgentQbList
            elif pos == 'rb':
                freeAgentList = freeAgentRbList
            elif pos in ['wr1', 'wr2']:
                freeAgentList = freeAgentWrList
            elif pos == 'te':
                freeAgentList = freeAgentTeList
            elif pos == 'k':
                freeAgentList = freeAgentKList
            
            if not freeAgentList or len(freeAgentList) == 0:
                continue
            
            # First, check if there are any A or S tier players available (prioritize elite talent)
            elitePlayers = [p for p in freeAgentList if p.playerTier.value >= 4]  # A=4, S=5
            
            if elitePlayers:
                # If elite players available, consider them first
                if gmScore >= len(elitePlayers):
                    i = len(elitePlayers) - 1
                else:
                    i = gmScore
                compPlayer = elitePlayers[randint(0, i)]
                
                # For A/S tier free agents, be more aggressive:
                # - Cut if compPlayer is higher tier OR
                # - Cut if same tier but current player has low performance (< 70)
                if compPlayer.playerTier.value > currentPlayer.playerTier.value:
                    self._executeCutAndSigning(
                        team, pos, currentPlayer, compPlayer,
                        freeAgentQbList, freeAgentRbList, freeAgentWrList,
                        freeAgentTeList, freeAgentKList,
                        freeAgencyDict, leagueHighlights, eventLog=eventLog
                    )
                    return True
                elif (compPlayer.playerTier.value == currentPlayer.playerTier.value and
                      currentPlayer.seasonPerformanceRating < 70):
                    # Replace underperformer with same tier elite player
                    self._executeCutAndSigning(
                        team, pos, currentPlayer, compPlayer,
                        freeAgentQbList, freeAgentRbList, freeAgentWrList,
                        freeAgentTeList, freeAgentKList,
                        freeAgencyDict, leagueHighlights, eventLog=eventLog
                    )
                    return True

            # If no elite players signed, use standard evaluation
            if gmScore >= len(freeAgentList):
                i = len(freeAgentList) - 1
            else:
                i = gmScore
            compPlayer = freeAgentList[randint(0, i)]

            # Standard rule: upgrade must be 2+ tiers higher
            if compPlayer and (compPlayer.playerTier.value - 1) > currentPlayer.playerTier.value:
                self._executeCutAndSigning(
                    team, pos, currentPlayer, compPlayer,
                    freeAgentQbList, freeAgentRbList, freeAgentWrList,
                    freeAgentTeList, freeAgentKList,
                    freeAgencyDict, leagueHighlights, eventLog=eventLog
                )
                return True
        
        return False
    
    def _executeCutAndSigning(self, team, position, cutPlayer, newPlayer,
                             freeAgentQbList, freeAgentRbList, freeAgentWrList,
                             freeAgentTeList, freeAgentKList,
                             freeAgencyDict, leagueHighlights, eventLog=None):
        """Execute the cutting of one player and signing of another - matches original exactly"""
        
        # Assign new player to roster first
        team.rosterDict[position] = newPlayer
        newPlayer.term = self._getPlayerTerm(newPlayer.playerTier)
        newPlayer.termRemaining = newPlayer.term
        newPlayer.team = team
        newPlayer.freeAgentYears = 0
        
        # Cut player - set contract to 0, move to free agency
        cutPlayer.termRemaining = 0
        cutPlayer.team = 'Free Agent'
        cutPlayer.previousTeam = team.name
        
        # Handle player numbers
        if cutPlayer.currentNumber in team.playerNumbersList:
            team.playerNumbersList.remove(cutPlayer.currentNumber)
        team.assignPlayerNumber(newPlayer)
        
        # TODO: capHit feature not fully developed - disabled for now
        # team.playerCap -= cutPlayer.capHit
        # team.playerCap += newPlayer.capHit
        
        # Add cut player to main free agent list
        if cutPlayer not in self.freeAgents:
            self.freeAgents.append(cutPlayer)
        
        # Remove new player from main free agent list
        if newPlayer in self.freeAgents:
            self.freeAgents.remove(newPlayer)
        
        # Add league highlights
        leagueHighlights.insert(0, {
            'event': {'text': f'{team.name} has cut {cutPlayer.name}'}
        })
        leagueHighlights.insert(0, {
            'event': {'text': f'{team.name} signed {newPlayer.name} ({newPlayer.position.name}) for {newPlayer.term} season(s)'}
        })

        # Collect events for WebSocket broadcast
        if eventLog is not None:
            teamAbbr = getattr(team, 'abbr', team.name[:3].upper())
            eventLog.append({
                'type': 'cut',
                'team': team.name,
                'teamAbbr': teamAbbr,
                'player': cutPlayer.name,
                'position': cutPlayer.position.name,
                'rating': round(cutPlayer.playerRating, 1),
                'tier': cutPlayer.playerTier.name,
            })
            eventLog.append({
                'type': 'pick',
                'team': team.name,
                'teamAbbr': teamAbbr,
                'player': newPlayer.name,
                'position': newPlayer.position.name,
                'rating': round(newPlayer.playerRating, 1),
                'tier': newPlayer.playerTier.name,
            })

        # Remove new player from position-specific free agent list
        if newPlayer.position.value == 1:  # QB
            if newPlayer in freeAgentQbList:
                freeAgentQbList.remove(newPlayer)
        elif newPlayer.position.value == 2:  # RB
            if newPlayer in freeAgentRbList:
                freeAgentRbList.remove(newPlayer)
        elif newPlayer.position.value == 3:  # WR
            if newPlayer in freeAgentWrList:
                freeAgentWrList.remove(newPlayer)
        elif newPlayer.position.value == 4:  # TE
            if newPlayer in freeAgentTeList:
                freeAgentTeList.remove(newPlayer)
        elif newPlayer.position.value == 5:  # K
            if newPlayer in freeAgentKList:
                freeAgentKList.remove(newPlayer)
        
        # Add cut player to position-specific free agent list and re-sort
        if cutPlayer.position.value == 1:  # QB
            freeAgentQbList.append(cutPlayer)
            freeAgentQbList.sort(key=lambda p: p.attributes.skillRating, reverse=True)
        elif cutPlayer.position.value == 2:  # RB
            freeAgentRbList.append(cutPlayer)
            freeAgentRbList.sort(key=lambda p: p.attributes.skillRating, reverse=True)
        elif cutPlayer.position.value == 3:  # WR
            freeAgentWrList.append(cutPlayer)
            freeAgentWrList.sort(key=lambda p: p.attributes.skillRating, reverse=True)
        elif cutPlayer.position.value == 4:  # TE
            freeAgentTeList.append(cutPlayer)
            freeAgentTeList.sort(key=lambda p: p.attributes.skillRating, reverse=True)
        elif cutPlayer.position.value == 5:  # K
            freeAgentKList.append(cutPlayer)
            freeAgentKList.sort(key=lambda p: p.attributes.skillRating, reverse=True)
        
        logger.debug(f"{team.name} cut {cutPlayer.name} and signed {newPlayer.name}")
    
    def _attemptRosterFill(self, team, teams, freeAgentQbList, freeAgentRbList, freeAgentWrList,
                          freeAgentTeList, freeAgentKList, freeAgencyDict, leagueHighlights,
                          eventLog=None) -> bool:
        """Attempt to fill ONE random open roster position (matching original logic)
        
        Returns True if roster is complete (no open positions), False otherwise
        """
        from random import randint, choice
        
        # Build list of all open positions
        openRosterPosList = []
        for pos in ['qb', 'rb', 'wr1', 'wr2', 'te', 'k']:
            if team.rosterDict.get(pos) is None:
                openRosterPosList.append(pos)
        
        # If no open positions, roster is complete
        if len(openRosterPosList) == 0:
            return True
        
        # Randomly choose ONE open position to fill
        pos = choice(openRosterPosList)
        
        # Map position to free agent list
        freeAgentLists = {
            'qb': freeAgentQbList, 'rb': freeAgentRbList, 
            'wr1': freeAgentWrList, 'wr2': freeAgentWrList,
            'te': freeAgentTeList, 'k': freeAgentKList
        }
        
        freeAgentList = freeAgentLists[pos]
        
        # If no free agents available at this position, return False (not complete, try again next round)
        if not freeAgentList or len(freeAgentList) == 0:
            return False
        
        # GM skill determines evaluation range
        gmScore = getattr(team, 'gmScore', 1)
        if gmScore >= len(freeAgentList):
            evalRange = len(freeAgentList) - 1
        else:
            evalRange = gmScore
        
        # Safety check
        if evalRange < 0:
            evalRange = 0
        
        # GM picks from their evaluation range
        selectedIndex = randint(0, evalRange)
        
        # CRITICAL: Check if player is already on a roster BEFORE popping
        candidate = freeAgentList[selectedIndex]
        for other_team in [t for t in teams if t != team]:
            for pos_key, roster_player in other_team.rosterDict.items():
                if roster_player is not None and roster_player.id == candidate.id:
                    logger.error(f"BUG: {candidate.name} in free agent list but already on {other_team.name} at {pos_key}! Removing from FA lists.")
                    # Remove from position-specific list
                    freeAgentList.pop(selectedIndex)
                    # Remove from master list
                    if candidate in self.freeAgents:
                        self.freeAgents.remove(candidate)
                    # Try again with a different player
                    return False
        
        # Player is clean, safe to sign
        selectedPlayer = freeAgentList.pop(selectedIndex)
        
        # Remove from main free agents list
        if selectedPlayer in self.freeAgents:
            self.freeAgents.remove(selectedPlayer)
        else:
            logger.warning(f"Player {selectedPlayer.name} not found in self.freeAgents when signing to {team.name}")
        
        # Assign to team
        selectedPlayer.team = team
        selectedPlayer.freeAgentYears = 0
        team.rosterDict[pos] = selectedPlayer
        team.assignPlayerNumber(selectedPlayer)
        
        # Set contract terms
        selectedPlayer.term = self._getPlayerTerm(selectedPlayer.playerTier)
        selectedPlayer.termRemaining = selectedPlayer.term
        
        # Record transaction
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
        
        # Add highlight
        leagueHighlights.insert(0, {
            'event': {'text': f'{team.name} signed {selectedPlayer.name} ({selectedPlayer.position.name}) for {selectedPlayer.term} season(s)'}
        })

        # Collect event for WebSocket broadcast
        if eventLog is not None:
            teamAbbr = getattr(team, 'abbr', team.name[:3].upper())
            eventLog.append({
                'type': 'pick',
                'team': team.name,
                'teamAbbr': teamAbbr,
                'player': selectedPlayer.name,
                'position': selectedPlayer.position.name,
                'rating': round(selectedPlayer.playerRating, 1),
                'tier': selectedPlayer.playerTier.name,
            })

        logger.debug(f"{team.name} filled {pos} with {selectedPlayer.name}")
        return False  # Roster not complete yet, has more open positions
    
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
        newPlayer.term = self._getPlayerTerm(newPlayer.playerTier)
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
    
    def getAdvancedPlayerTerm(self, tier) -> int:
        """Get contract term with original random ranges - replaces simplified _getPlayerTerm"""
        from random import randint
        
        if tier == FloosPlayer.PlayerTier.TierS:
            return randint(4, 6)  # S-tier: 4-6 years
        elif tier == FloosPlayer.PlayerTier.TierA:
            return randint(3, 4)  # A-tier: 3-4 years  
        elif tier == FloosPlayer.PlayerTier.TierD:
            return 1  # D-tier: 1 year
        else:
            return randint(1, 3)  # B/C-tier: 1-3 years
    
    def processContractDecrements(self, currentSeason: int) -> Dict[str, List[Dict[str, Any]]]:
        """
        Process contract term decrements and salary cap management for all players.
        This is the main salary cap management function called during offseason.
        
        Returns:
            Dict containing expired players, retired players, and free agents by category
        """
        logger.info(f"Processing contract decrements for season {currentSeason}")
        
        expiredPlayers = []
        newRetiredPlayers = []
        contractStatus = {
            'expired': [],
            'retired': [],
            'freeAgents': [],
            'activeContracts': []
        }
        
        # Get teams from service container
        teamManager = self.serviceContainer.getService('team_manager')
        teams = teamManager.teams if teamManager else []
        
        # Process each team's roster
        for team in teams:
            if not hasattr(team, 'rosterDict'):
                continue
                
            # Reset team salary cap for new season
            team.playerCap = 0
            
            # Process each roster position
            for position, player in list(team.rosterDict.items()):
                if player is None:
                    continue
                
                # Increment seasons played and update service time
                player.seasonsPlayed += 1
                self._updatePlayerServiceTime(player)
                
                # Decrement contract term
                if hasattr(player, 'termRemaining'):
                    player.termRemaining -= 1
                else:
                    # Initialize termRemaining if missing
                    player.termRemaining = getattr(player, 'term', 1) - 1
                
                # Process retirement logic before checking contract expiration
                retirePlayerBool = self._checkPlayerRetirement(player)
                
                if retirePlayerBool:
                    # Player retires
                    self._executePlayerRetirement(player, team, position, newRetiredPlayers, contractStatus)
                elif player.termRemaining <= 0:
                    # Contract expired - move to free agency
                    self._executeContractExpiration(player, team, position, expiredPlayers, contractStatus)
                else:
                    # Player remains under contract - add to salary cap
                    if hasattr(player, 'capHit'):
                        team.playerCap += player.capHit
                    contractStatus['activeContracts'].append({
                        'player': player.name,
                        'team': team.name,
                        'position': position,
                        'termRemaining': player.termRemaining,
                        'capHit': getattr(player, 'capHit', 0)
                    })
        
        # Add newly retired players to global retired list
        if newRetiredPlayers:
            if not hasattr(self, 'retiredPlayers'):
                self.retiredPlayers = []
            self.retiredPlayers.extend(newRetiredPlayers)
        
        logger.info(f"Contract processing complete: {len(contractStatus['expired'])} expired, "
                   f"{len(contractStatus['retired'])} retired, {len(contractStatus['activeContracts'])} active")
        
        return contractStatus
    
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
    
    def _checkPlayerRetirement(self, player) -> bool:
        """
        Check if player should retire based on age, longevity, and contract status.
        Replaces original retirement logic from offseason processing.
        """
        from random import randint
        
        # Only check retirement if player is over their longevity threshold
        if player.seasonsPlayed <= player.attributes.longevity:
            return False
        
        # Only consider retirement at end of contract
        if getattr(player, 'termRemaining', 1) > 0:
            return False
        
        # Retirement probability based on seasons played
        if player.seasonsPlayed > 15:
            # Very old players: 90% chance to retire
            retirementChance = randint(1, 100)
            return retirementChance > 10
        elif player.seasonsPlayed > 10:
            # Old players: 65% chance to retire
            retirementChance = randint(1, 100)
            return retirementChance > 35
        elif player.seasonsPlayed > 8:
            # Aging players: 30% chance to retire
            retirementChance = randint(1, 100)
            return retirementChance > 70
        
        return False
    
    def _executePlayerRetirement(self, player, team, position, retiredList, contractStatus) -> None:
        """Execute player retirement - remove from team and add to retired list"""
        logger.debug(f"{player.name} retiring from {team.name}")
        
        # Update player status
        player.previousTeam = team.name
        player.seasonPerformanceRating = 0
        player.team = 'Retired'
        
        # TODO: capHit feature not fully developed - disabled for now
        # if hasattr(team, 'playerCap') and hasattr(player, 'capHit'):
        #     team.playerCap -= player.capHit
        
        if hasattr(team, 'playerNumbersList') and hasattr(player, 'currentNumber'):
            if player.currentNumber in team.playerNumbersList:
                team.playerNumbersList.remove(player.currentNumber)
        
        # Clear roster position
        team.rosterDict[position] = None
        
        # Remove from active lists
        if player in self.activePlayers:
            self.activePlayers.remove(player)
        self.removeFromPositionList(player)
        
        # Add to retired list
        retiredList.append(player)
        
        # Update contract status tracking
        contractStatus['retired'].append({
            'player': player.name,
            'previousTeam': team.name,
            'position': position,
            'seasonsPlayed': player.seasonsPlayed,
            'finalRating': getattr(player.attributes, 'overallRating', 0)
        })
        
        # Mark service time as retired
        import floosball_player as FloosPlayer
        player.serviceTime = FloosPlayer.PlayerServiceTime.Retired
    
    def _executeContractExpiration(self, player, team, position, expiredList, contractStatus) -> None:
        """Execute contract expiration - move player to free agency"""
        logger.debug(f"{player.name} contract expired, moving to free agency")
        
        # Update player status
        player.previousTeam = team.name
        player.team = 'Free Agent'
        
        # TODO: capHit feature not fully developed - disabled for now
        # if hasattr(team, 'playerCap') and hasattr(player, 'capHit'):
        #     team.playerCap -= player.capHit
        
        if hasattr(team, 'playerNumbersList') and hasattr(player, 'currentNumber'):
            if player.currentNumber in team.playerNumbersList:
                team.playerNumbersList.remove(player.currentNumber)
        
        # Clear roster position
        team.rosterDict[position] = None
        
        # Move to free agency (player stays in activePlayers and position lists)
        if player not in self.freeAgents:
            self.freeAgents.append(player)
        
        # Add to expired list
        expiredList.append(player)
        
        # Update contract status tracking
        contractStatus['expired'].append({
            'player': player.name,
            'previousTeam': team.name,
            'position': position,
            'rating': getattr(player.attributes, 'overallRating', 0),
            'seasonsPlayed': player.seasonsPlayed
        })
        
        contractStatus['freeAgents'].append(player)
    
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