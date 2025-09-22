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
    
    def generatePlayers(self, config: Dict[str, Any]) -> None:
        """Generate initial player pool (replaces getPlayers function)"""
        logger.info("Generating initial player pool")
        
        playerConfig = config.get('playerConfig', {})
        totalPlayers = playerConfig.get('totalPlayers', 144)  # Match original default
        
        # Load name lists from main config
        self.loadNameLists(config)
        
        # Generate players by position
        self.generatePlayersByPosition(totalPlayers)
        
        # Save remaining unused names
        self.saveUnusedNames()
        
        logger.info(f"Generated {len(self.activePlayers)} total players")
    
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