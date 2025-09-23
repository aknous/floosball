"""
PlayerManager - Manages player lifecycle, lists, and organization
Replaces the scattered player-related global variables and functions in floosball.py
"""

from typing import List, Optional, Dict, Any
import floosball_player as FloosPlayer
import floosball_team as FloosTeam
from logger_config import get_logger

logger = get_logger("floosball.playerManager")

class PlayerManager:
    """Manages player lifecycle, lists, and organization"""
    
    def __init__(self, serviceContainer):
        self.serviceContainer = serviceContainer
        
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
    
    def generatePlayers(self, config: Dict[str, Any], force_fresh: bool = False) -> None:
        """Generate or load initial player pool (replaces getPlayers function)"""
        logger.info("Generating initial player pool")
        
        # First try to load existing players (unless force fresh is requested)
        if not force_fresh and self._loadExistingPlayers():
            logger.info(f"Loaded {len(self.activePlayers)} existing players from data files")
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
        Load existing players from data files if they exist
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
        
        # Organize players by position
        self.sortPlayersByPosition()
        
        logger.info(f"Successfully loaded {len(loaded_players)} players from data files")
        return True
    
    def _createPlayerFromData(self, player_data: Dict[str, Any]) -> FloosPlayer.Player:
        """Create a Player object from saved JSON data"""
        import floosball_player as FloosPlayer
        
        try:
            # Create basic player with name
            player = FloosPlayer.Player(player_data['name'])
            
            # Set basic properties
            player.id = player_data.get('id', 1)
            player.currentNumber = player_data.get('currentNumber', 0)
            player.preferredNumber = player_data.get('preferredNumber', 0)
            player.seasonsPlayed = player_data.get('seasonsPlayed', 0)
            player.term = player_data.get('term', 2)
            player.termRemaining = player_data.get('termRemaining', 2)
            player.capHit = player_data.get('capHit', 2)
            player.seasonPerformanceRating = player_data.get('seasonPerformanceRating', 0)
            player.playerRating = player_data.get('playerRating', 74)
            player.freeAgentYears = player_data.get('freeAgentYears', 0)
            
            # Set player tier
            tier_name = player_data.get('tier', 'TierC')
            try:
                player.playerTier = getattr(FloosPlayer.PlayerTier, tier_name)
            except AttributeError:
                logger.warning(f"Unknown tier {tier_name} for player {player.name}, defaulting to TierC")
                player.playerTier = FloosPlayer.PlayerTier.TierC
            
            # Set position
            position_value = player_data.get('position', 1)
            try:
                player.position = FloosPlayer.PlayerPosition(position_value)
            except ValueError:
                logger.warning(f"Invalid position {position_value} for player {player.name}, defaulting to QB")
                player.position = FloosPlayer.PlayerPosition.QB
            
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
            
            # Load attributes
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
                player.seasonStatsArchive = player_data['seasonStatsArchive']
            
            # Set up season stats dict if not present
            if not hasattr(player, 'seasonStatsDict') or player.seasonStatsDict is None:
                player.seasonStatsDict = player.careerStatsDict.copy() if hasattr(player, 'careerStatsDict') else {}
            
            return player
            
        except Exception as e:
            logger.error(f"Failed to create player from data: {e}")
            return None
    
    def loadNameLists(self, config: Dict[str, Any]) -> None:
        """Load player name lists from unusedNames.json or config"""
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
        
        # If unusedNames.json doesn't exist or is empty, load from config and create it
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
    
    def createPlayer(self, position: FloosPlayer.Position, seed: int = None) -> Optional[FloosPlayer.Player]:
        """Create a single player of specified position"""
        from random import randint
        
        if not self.unusedNames:
            logger.warning("No more unused names available")
            return None
        
        # Use same logic as original: pick random index and pop
        nameIndex = randint(0, len(self.unusedNames) - 1)
        name = self.unusedNames.pop(nameIndex)
        
        # Generate default seed if not provided
        if seed is None:
            seed = randint(60, 100)
        
        # Create player based on position with seed
        player = None
        if position == FloosPlayer.Position.QB:
            player = FloosPlayer.PlayerQB(seed)
        elif position == FloosPlayer.Position.RB:
            player = FloosPlayer.PlayerRB(seed)
        elif position == FloosPlayer.Position.WR:
            player = FloosPlayer.PlayerWR(seed)
        elif position == FloosPlayer.Position.TE:
            player = FloosPlayer.PlayerTE(seed)
        elif position == FloosPlayer.Position.K:
            player = FloosPlayer.PlayerK(seed)
        
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
        try:
            playerList.remove(player)
        except ValueError:
            logger.warning(f"Player {player.name} not found in position list")
    
    def _getPlayerTerm(self, tier: FloosPlayer.PlayerTier) -> int:
        """Get contract term for player tier (avoiding circular import)"""
        tier_terms = {
            FloosPlayer.PlayerTier.TierD: 1,
            FloosPlayer.PlayerTier.TierC: 2,
            FloosPlayer.PlayerTier.TierB: 3,
            FloosPlayer.PlayerTier.TierA: 3,
            FloosPlayer.PlayerTier.TierS: 4
        }
        return tier_terms.get(tier, 2)
    
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
        for playerList in [draftQbList, draftRbList, draftWrList, draftTeList, draftKList]:
            for player in playerList:
                player.team = 'Free Agent'
                self.freeAgents.append(player)
        
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
        
        # Assign player tiers (matches original sortPlayers logic)
        tierS = 92
        tierA = 85
        tierB = 75
        tierC = 68
        
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
    
    def savePlayerData(self) -> None:
        """Save player data (replaces savePlayerData function)"""
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
            qbStats = {
                "passComp": [qb.seasonStatsDict['passing']['compPerc'] for qb in activeQbsWithStats],
                "passYards": [qb.seasonStatsDict['passing']['yards'] for qb in activeQbsWithStats],
                "tds": [qb.seasonStatsDict['passing']['tds'] for qb in activeQbsWithStats],
                "ints": [qb.seasonStatsDict['passing']['ints'] for qb in activeQbsWithStats]
            }
            
            for qb in activeQbsWithStats:
                compPerc = qb.seasonStatsDict['passing']['compPerc']
                passYards = qb.seasonStatsDict['passing']['yards']
                tds = qb.seasonStatsDict['passing']['tds']
                ints = qb.seasonStatsDict['passing']['ints']
                
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
            rbStats = {
                "ypc": [rb.seasonStatsDict['rushing']['ypc'] for rb in activeRbsWithStats],
                "rushYards": [rb.seasonStatsDict['rushing']['yards'] for rb in activeRbsWithStats],
                "tds": [rb.seasonStatsDict['rushing']['tds'] for rb in activeRbsWithStats],
                "fumbles": [rb.seasonStatsDict['rushing']['fumblesLost'] for rb in activeRbsWithStats]
            }
            
            for rb in activeRbsWithStats:
                ypc = rb.seasonStatsDict['rushing']['ypc']
                rushYards = rb.seasonStatsDict['rushing']['yards']
                tds = rb.seasonStatsDict['rushing']['tds']
                fumbles = rb.seasonStatsDict['rushing']['fumblesLost']
                
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
            wrStats = {
                "receptions": [wr.seasonStatsDict['receiving']['receptions'] for wr in activeWrsWithStats],
                "drops": [wr.seasonStatsDict['receiving']['drops'] for wr in activeWrsWithStats],
                "rcvPerc": [wr.seasonStatsDict['receiving']['rcvPerc'] for wr in activeWrsWithStats],
                "rcvYards": [wr.seasonStatsDict['receiving']['yards'] for wr in activeWrsWithStats],
                "ypr": [wr.seasonStatsDict['receiving']['ypr'] for wr in activeWrsWithStats],
                "yac": [wr.seasonStatsDict['receiving']['yac'] for wr in activeWrsWithStats],
                "tds": [wr.seasonStatsDict['receiving']['tds'] for wr in activeWrsWithStats]
            }
            
            for wr in activeWrsWithStats:
                receptions = wr.seasonStatsDict['receiving']['receptions']
                drops = wr.seasonStatsDict['receiving']['drops']
                rcvPerc = wr.seasonStatsDict['receiving']['rcvPerc']
                rcvYards = wr.seasonStatsDict['receiving']['yards']
                ypr = wr.seasonStatsDict['receiving']['ypr']
                yac = wr.seasonStatsDict['receiving']['yac']
                tds = wr.seasonStatsDict['receiving']['tds']
                
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
            teStats = {
                "receptions": [te.seasonStatsDict['receiving']['receptions'] for te in activeTesWithStats],
                "drops": [te.seasonStatsDict['receiving']['drops'] for te in activeTesWithStats],
                "rcvPerc": [te.seasonStatsDict['receiving']['rcvPerc'] for te in activeTesWithStats],
                "rcvYards": [te.seasonStatsDict['receiving']['yards'] for te in activeTesWithStats],
                "ypr": [te.seasonStatsDict['receiving']['ypr'] for te in activeTesWithStats],
                "yac": [te.seasonStatsDict['receiving']['yac'] for te in activeTesWithStats],
                "tds": [te.seasonStatsDict['receiving']['tds'] for te in activeTesWithStats]
            }
            
            for te in activeTesWithStats:
                receptions = te.seasonStatsDict['receiving']['receptions']
                drops = te.seasonStatsDict['receiving']['drops']
                rcvPerc = te.seasonStatsDict['receiving']['rcvPerc']
                rcvYards = te.seasonStatsDict['receiving']['yards']
                ypr = te.seasonStatsDict['receiving']['ypr']
                yac = te.seasonStatsDict['receiving']['yac']
                tds = te.seasonStatsDict['receiving']['tds']
                
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
            kStats = {
                "fgPerc": [k.seasonStatsDict['kicking']['fgPerc'] for k in activeKsWithStats if k.seasonStatsDict['kicking']['fgPerc'] > 0],
                "fgs": [k.seasonStatsDict['kicking']['fgs'] for k in activeKsWithStats],
                "fgAvg": [k.seasonStatsDict['kicking'].get('fgAvg', 0) for k in activeKsWithStats if k.seasonStatsDict['kicking'].get('fgAvg', 0) > 0]
            }
            
            for k in activeKsWithStats:
                fgPerc = k.seasonStatsDict['kicking']['fgPerc']
                fgs = k.seasonStatsDict['kicking']['fgs']
                fgAvg = k.seasonStatsDict['kicking'].get('fgAvg', 0)
                
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
    
    def conductFreeAgencySimulation(self, freeAgencyOrder: List, currentSeason: int, leagueHighlights: List = None) -> Dict[str, Any]:
        """
        Complete Free Agency Simulation System - replaces original free agency logic from offseason() function
        Multi-round system with GM skill-based evaluation, tier upgrades, and salary cap management
        """
        from random import randint, choice
        import copy
        
        logger.info(f"Starting free agency simulation for season {currentSeason}")
        
        freeAgencyDict = {}
        freeAgencyHistory = {}
        teamsComplete = 0
        
        if leagueHighlights is None:
            leagueHighlights = []
        
        # Process contract expirations - move players with 0 term remaining to free agency
        self._processContractExpirations()
        
        # Process free agent retirements (players with 3+ years as free agents)
        self._processFreeAgentRetirements(currentSeason, leagueHighlights)
        
        # Generate replacement players for retired players
        self._generateReplacementPlayers(currentSeason)
        
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
        
        # MULTI-ROUND FREE AGENCY PROCESS
        roundNum = 1
        while teamsComplete < len(teams):
            logger.debug(f"Free agency round {roundNum}: {teamsComplete}/{len(teams)} teams complete")
            
            for team in freeAgencyOrder:
                if team.freeAgencyComplete:
                    continue
                
                teamMadeMove = False
                
                # PHASE 1: Try to cut and upgrade players (if cuts available)
                if team.cutsAvailable > 0:
                    cutMade = self._attemptPlayerCutAndUpgrade(
                        team, freeAgentQbList, freeAgentRbList, freeAgentWrList, 
                        freeAgentTeList, freeAgentKList, freeAgencyDict, leagueHighlights
                    )
                    if cutMade:
                        teamMadeMove = True
                        team.cutsAvailable -= 1
                
                # PHASE 2: Fill any open roster spots
                if not teamMadeMove:
                    signedPlayer = self._attemptRosterFill(
                        team, freeAgentQbList, freeAgentRbList, freeAgentWrList,
                        freeAgentTeList, freeAgentKList, freeAgencyDict, leagueHighlights
                    )
                    if signedPlayer:
                        teamMadeMove = True
                
                # PHASE 3: Mark team as complete if no moves possible
                if not teamMadeMove:
                    team.freeAgencyComplete = True
                    teamsComplete += 1
            
            roundNum += 1
            if roundNum > 50:  # Safety valve to prevent infinite loops
                logger.warning("Free agency exceeded 50 rounds, ending simulation")
                break
        
        # Save free agency history
        freeAgencyHistory[f'offseason {currentSeason}'] = freeAgencyDict
        
        logger.info(f"Free agency complete after {roundNum-1} rounds. {len(freeAgencyDict)} transactions made.")
        return freeAgencyHistory
    
    def _processContractExpirations(self) -> None:
        """Move players with expired contracts to free agency"""
        expiredPlayers = []
        
        for player in self.activePlayers:
            if hasattr(player, 'termRemaining') and player.termRemaining <= 0:
                expiredPlayers.append(player)
        
        for player in expiredPlayers:
            self.activePlayers.remove(player)
            self.removeFromPositionList(player)
            player.team = 'Free Agent'
            player.freeAgentYears = getattr(player, 'freeAgentYears', 0) + 1
            self.freeAgents.append(player)
            
        logger.info(f"Moved {len(expiredPlayers)} players with expired contracts to free agency")
    
    def _processFreeAgentRetirements(self, currentSeason: int, leagueHighlights: List) -> None:
        """Process retirements of long-term free agents"""
        retirements = []
        
        for player in self.freeAgents[:]:  # Use slice copy for safe iteration
            if getattr(player, 'freeAgentYears', 0) >= 3:
                retirementChance = 0
                
                # Retirement chances based on tier (original logic)
                if player.playerTier.value == 1:  # TierD
                    retirementChance = 0.65
                elif player.playerTier.value == 2:  # TierC  
                    retirementChance = 0.40
                elif player.playerTier.value == 3:  # TierB
                    retirementChance = 0.25
                elif player.playerTier.value == 4:  # TierA
                    retirementChance = 0.15
                elif player.playerTier.value == 5:  # TierS
                    retirementChance = 0.05
                
                from random import random
                if random() < retirementChance:
                    retirements.append(player)
                    self.retirePlayer(player)
                    leagueHighlights.insert(0, {
                        'event': {'text': f'{player.name} has retired from football'}
                    })
        
        logger.info(f"Free agent retirements: {len(retirements)} players retired")
    
    def _generateReplacementPlayers(self, currentSeason: int) -> None:
        """Generate replacement players for those who retired"""
        import numpy as np
        from random import randint
        
        numRetired = len(self.newlyRetiredPlayers)
        if numRetired == 0:
            return
        
        # Generate replacement players with same distribution as original
        meanPlayerSkill = 80
        stdDevPlayerSkill = 7
        playerAverages = np.random.normal(meanPlayerSkill, stdDevPlayerSkill, numRetired)
        playerAverages = np.clip(playerAverages, 60, 100).tolist()
        
        for i in range(numRetired):
            # Use same position distribution as original (y = x % 6)
            y = i % 6
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
                newPlayer = self.createPlayer(position, seed)
                if newPlayer:
                    newPlayer.team = 'Free Agent'
                    newPlayer.freeAgentYears = 0
                    self.freeAgents.append(newPlayer)
        
        logger.info(f"Generated {numRetired} replacement players")
    
    def _attemptPlayerCutAndUpgrade(self, team, freeAgentQbList, freeAgentRbList, freeAgentWrList, 
                                   freeAgentTeList, freeAgentKList, freeAgencyDict, leagueHighlights) -> bool:
        """Attempt to cut current player and sign upgrade based on GM skill and tier comparison"""
        from random import randint
        
        # Check each position for potential upgrades
        positions = ['qb', 'rb', 'wr1', 'wr2', 'te', 'k']
        freeAgentLists = {
            'qb': freeAgentQbList, 'rb': freeAgentRbList, 'wr1': freeAgentWrList,
            'wr2': freeAgentWrList, 'te': freeAgentTeList, 'k': freeAgentKList
        }
        
        for pos in positions:
            currentPlayer = team.rosterDict.get(pos)
            freeAgentList = freeAgentLists[pos]
            
            # Skip if no current player or no free agents available
            if not currentPlayer or not freeAgentList:
                continue
            
            # Only consider cuts for players in tiers 1-3 (lower tiers eligible for cuts)
            if currentPlayer.playerTier.value > 3:
                continue
            
            # GM skill determines evaluation range
            gmScore = getattr(team, 'gmScore', 1)
            if gmScore >= len(freeAgentList):
                evalRange = len(freeAgentList) - 1
            else:
                evalRange = gmScore
            
            # GM evaluates a free agent based on their skill
            compPlayer = freeAgentList[randint(0, evalRange)]
            
            # Multi-tier comparison logic: upgrade if free agent is significantly better
            if (compPlayer.playerTier.value - 1) > currentPlayer.playerTier.value:
                # Make the cut and signing
                self._executeCutAndSigning(team, pos, currentPlayer, compPlayer, freeAgencyDict, leagueHighlights)
                return True
        
        return False
    
    def _executeCutAndSigning(self, team, position, cutPlayer, newPlayer, freeAgencyDict, leagueHighlights):
        """Execute the cutting of one player and signing of another"""
        # Update salary cap
        if hasattr(team, 'playerCap'):
            team.playerCap -= getattr(cutPlayer, 'capHit', 0)
            team.playerCap += getattr(newPlayer, 'capHit', newPlayer.playerTier.value)
        
        # Move cut player to free agents
        cutPlayer.team = 'Free Agent'
        cutPlayer.freeAgentYears = getattr(cutPlayer, 'freeAgentYears', 0) + 1
        self.freeAgents.append(cutPlayer)
        self.removeFromPositionList(cutPlayer)
        if cutPlayer in self.activePlayers:
            self.activePlayers.remove(cutPlayer)
        
        # Sign new player
        self.freeAgents.remove(newPlayer)
        self.activePlayers.append(newPlayer)
        self.addToPositionList(newPlayer)
        newPlayer.team = team
        newPlayer.freeAgentYears = 0
        
        # Set contract terms based on tier
        newPlayer.term = self._getPlayerTerm(newPlayer.playerTier)
        newPlayer.termRemaining = newPlayer.term
        
        # Assign to roster
        team.rosterDict[position] = newPlayer
        team.assignPlayerNumber(newPlayer)
        
        # Record transaction
        transactionId = f"{team.name}_{cutPlayer.name}_{newPlayer.name}"
        freeAgencyDict[transactionId] = {
            'team': team.name,
            'cut': cutPlayer.name,
            'signed': newPlayer.name,
            'position': position,
            'newTier': newPlayer.playerTier.name,
            'term': newPlayer.term
        }
        
        # Add highlights
        leagueHighlights.insert(0, {
            'event': {'text': f'{team.city} {team.name} has cut {cutPlayer.name}'}
        })
        leagueHighlights.insert(0, {
            'event': {'text': f'{team.city} {team.name} signed {newPlayer.name} ({newPlayer.playerTier.name}) for {newPlayer.term} season(s)'}
        })
        
        logger.debug(f"{team.name} cut {cutPlayer.name} and signed {newPlayer.name}")
    
    def _attemptRosterFill(self, team, freeAgentQbList, freeAgentRbList, freeAgentWrList,
                          freeAgentTeList, freeAgentKList, freeAgencyDict, leagueHighlights) -> bool:
        """Attempt to fill any open roster positions"""
        from random import randint
        
        positions = ['qb', 'rb', 'wr1', 'wr2', 'te', 'k']
        freeAgentLists = {
            'qb': freeAgentQbList, 'rb': freeAgentRbList, 'wr1': freeAgentWrList,
            'wr2': freeAgentWrList, 'te': freeAgentTeList, 'k': freeAgentKList
        }
        
        for pos in positions:
            if team.rosterDict.get(pos) is None:  # Position is open
                freeAgentList = freeAgentLists[pos]
                
                if not freeAgentList:
                    continue
                
                # GM skill determines evaluation range
                gmScore = getattr(team, 'gmScore', 1)
                if gmScore >= len(freeAgentList):
                    evalRange = len(freeAgentList) - 1
                else:
                    evalRange = gmScore
                
                # GM picks from their evaluation range
                newPlayer = freeAgentList[randint(0, evalRange)]
                
                # Sign the player
                self._executeRosterSigning(team, pos, newPlayer, freeAgencyDict, leagueHighlights)
                return True
        
        return False
    
    def _executeRosterSigning(self, team, position, newPlayer, freeAgencyDict, leagueHighlights):
        """Execute signing a player to fill an open roster spot"""
        # Update salary cap
        if hasattr(team, 'playerCap'):
            team.playerCap += getattr(newPlayer, 'capHit', newPlayer.playerTier.value)
        
        # Sign new player
        self.freeAgents.remove(newPlayer)
        self.activePlayers.append(newPlayer)
        self.addToPositionList(newPlayer)
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
        
        # Remove from team salary cap and roster
        if hasattr(team, 'playerCap') and hasattr(player, 'capHit'):
            team.playerCap -= player.capHit
        
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
        
        # Remove from team salary cap and roster
        if hasattr(team, 'playerCap') and hasattr(player, 'capHit'):
            team.playerCap -= player.capHit
        
        if hasattr(team, 'playerNumbersList') and hasattr(player, 'currentNumber'):
            if player.currentNumber in team.playerNumbersList:
                team.playerNumbersList.remove(player.currentNumber)
        
        # Clear roster position
        team.rosterDict[position] = None
        
        # Move to free agency
        if player in self.activePlayers:
            self.activePlayers.remove(player)
        self.removeFromPositionList(player)
        
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