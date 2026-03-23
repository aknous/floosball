import enum
from os import stat
import math
from random import randint
from random_batch import batched_randint, batched_random
import copy
from stats_optimization import OptimizedPlayerStats, get_optimized_stats
import numpy as np
import floosball_methods as FloosMethods
from floosball_team import Team
from stat_tracker import StatTracker
from player_development import PlayerDevelopment
from rating_cache import CachedRatingMixin

class Position(enum.Enum):
    QB = 1
    RB = 2
    WR = 3
    TE = 4
    K = 5

class PlayerTier(enum.Enum):
    TierS = 5
    TierA = 4
    TierB = 3
    TierC = 2
    TierD = 1

class PlayerServiceTime(enum.Enum):
    Rookie = 'Rookie'
    Veteran1 = 'Established'
    Veteran2 = 'Veteran'
    Veteran3 = 'Grizzled Veteran'
    Veteran4 = 'Ancient Veteran'
    Retired = 'Retired'

playerStatsDict =   {   
                        'team': None,
                        'season': 0,
                        'gp': 0,
                        'fantasyPoints': 0,
                        'passing': {
                            'att': 0, 
                            'comp': 0, 
                            'compPerc': 0, 
                            'missedPass': 0,
                            'tds': 0, 
                            'ints': 0, 
                            'yards': 0, 
                            'ypc': 0, 
                            '20+': 0,
                            'longest': 0
                        },
                        'rushing': {
                            'carries': 0,
                            'yards': 0, 
                            'ypc': 0, 
                            'tds': 0, 
                            'fumblesLost': 0, 
                            '20+': 0,
                            'longest': 0
                        },
                        'receiving': {
                            'receptions': 0, 
                            'targets': 0, 
                            'rcvPerc': 0, 
                            'drops': 0,
                            'yards': 0,
                            'yac': 0, 
                            'ypr': 0, 
                            'tds': 0,
                            '20+': 0,
                            'longest': 0
                        },
                        'kicking': {
                            'fgAtt': 0, 
                            'fgs': 0, 
                            'fgPerc': 0,
                            'fgYards': 0,
                            'fgAvg': 0,
                            'fg45+': 0,
                            'fgUnder20att': 0,
                            'fgUnder20': 0,
                            'fgUnder20perc': 0,
                            'fg20to40att': 0,
                            'fg20to40': 0,
                            'fg20to40perc': 0,
                            'fg40to50att': 0,
                            'fg40to50': 0,
                            'fg40to50perc': 0,
                            'fgOver50att': 0,
                            'fgOver50': 0,
                            'fgOver50perc': 0,
                            'longest': 0
                        }
                    }

qbStatsDict = {
                'passAtt': 0, 
                'passComp': 0, 
                'passCompPerc': 0, 
                'passMiss': 0,
                'tds': 0, 
                'ints': 0, 
                'passYards': 0, 
                'ypc': 0, 
                'totalYards': 0,
                'pass20+': 0,
                'longest': 0
            }
rbStatsDict = {
                'carries': 0, 
                'receptions': 0, 
                'passTargets': 0, 
                'rcvPerc': 0, 
                'rcvYards': 0, 
                'runYards': 0, 
                'ypc': 0, 
                'runTds': 0, 
                'rcvTds': 0, 
                'fumblesLost': 0, 
                'ypr': 0, 
                'totalYards': 0,
                'run20+': 0,
                'pass20+': 0,
                'longest': 0
            }
wrStatsDict = {
                'receptions': 0, 
                'passTargets': 0, 
                'drops': 0,
                'rcvPerc': 0, 
                'rcvYards': 0, 
                'ypr': 0, 
                'rcvTds': 0, 
                'totalYards': 0,
                'pass20+': 0,
                'longest': 0
            }
kStatsDict = {
                'fgAtt': 0, 
                'fgs': 0, 
                'fgPerc': 0,
                'fgUnder20att': 0,
                'fgUnder20': 0,
                'fgUnder20perc': 0,
                'fg20to40att': 0,
                'fg20to40': 0,
                'fg20to40perc': 0,
                'fg40to50att': 0,
                'fg40to50': 0,
                'fg40to50perc': 0,
                'fgOver50att': 0,
                'fgOver50': 0,
                'fgOver50perc': 0,
                'longest': 0
            }

class Player:
    def __init__(self, seed = None):
        self.position = None
        self.name = ''
        self.id = 0
        self.currentNumber = 0
        self.preferredNumber = randint(0,99)
        self.team: Team = None
        self.previousTeam = None
        self.attributes = PlayerAttributes()
        self.gameAttributes: PlayerAttributes = None
        self.playerTier = PlayerTier.TierC  # Default tier, updated by sortPlayersByPosition
        self.seasonsPlayed = 0
        self.gamesPlayed = 0
        self.term = 0
        self.termRemaining = 0
        self.capHit = 0
        self.seasonPerformanceRating = 0
        self.playerRating = 0
        self.freeAgentYears = 0
        self.serviceTime = PlayerServiceTime.Rookie
        self.leagueChampionships = []
        self.mvpAwards = []

        # Use optimized stats instead of deep copying
        self.gameStats = get_optimized_stats()
        self.seasonStats = get_optimized_stats()
        self.careerStats = get_optimized_stats()
        
        # Keep legacy dict access for backwards compatibility
        self.gameStatsDict = self.gameStats.to_legacy_dict()
        self.seasonStatsDict = self.seasonStats.to_legacy_dict()
        self.careerStatsDict = self.careerStats.to_legacy_dict()
        self.seasonStatsArchive = []

        # Initialize StatTracker with the stats dictionaries
        self.stat_tracker = StatTracker(
            self.gameStatsDict, 
            self.seasonStatsDict, 
            self.careerStatsDict
        )
    
    def sync_stats_dicts(self):
        """Sync FROM updated legacy dictionaries TO optimized stats objects"""
        # Update optimized stats from the legacy dicts that have been updated by stat_tracker
        self.gameStats = OptimizedPlayerStats.from_legacy_dict(self.gameStatsDict)
        self.seasonStats = OptimizedPlayerStats.from_legacy_dict(self.seasonStatsDict)
        self.careerStats = OptimizedPlayerStats.from_legacy_dict(self.careerStatsDict)
    
    def reset_game_stats(self):
        """Reset game stats for a new game using optimized stats"""
        self.gameStats.reset_for_new_game()
        # Sync the reset stats TO the legacy dict (not FROM it)
        self.gameStatsDict = self.gameStats.to_legacy_dict()
        # Update stat_tracker reference to the new dict
        self.stat_tracker.game_stats_dict = self.gameStatsDict

    def postgameChanges(self):
        self.attributes.confidenceModifier = round((self.attributes.confidenceModifier + self.gameAttributes.confidenceModifier)/2, 3)
        self.attributes.determinationModifier = round((self.attributes.determinationModifier + self.gameAttributes.determinationModifier)/2, 3)
        self.gamesPlayed += 1
        # Sync stat_tracker data to optimized objects, then update gp in both
        self.sync_stats_dicts()
        self.seasonStats.gp = self.gamesPlayed
        self.seasonStatsDict['gp'] = self.gamesPlayed
        self.careerStats.gp += 1
        self.careerStatsDict['gp'] = self.careerStatsDict.get('gp', 0) + 1
        if isinstance(self.team,Team):
            if self.team.winningStreak:
                self.attributes.confidenceModifier = round(self.attributes.confidenceModifier + (batched_randint(0,25)/100), 3)
            elif self.team.seasonTeamStats['streak'] < -2:
                if self.attributes.attitude < 70:
                    self.attributes.confidenceModifier = round(self.attributes.confidenceModifier + (batched_randint(-20,0)/100), 3)
                    self.attributes.determinationModifier = round(self.attributes.determinationModifier + (batched_randint(-20,0)/100), 3)
                elif self.attributes.attitude < 80:
                    self.attributes.confidenceModifier = round(self.attributes.confidenceModifier + (batched_randint(-10,0)/100), 3)
                    self.attributes.determinationModifier = round(self.attributes.determinationModifier + (batched_randint(-10,0)/100), 3)
                elif self.attributes.attitude < 90:
                    self.attributes.confidenceModifier = round(self.attributes.confidenceModifier + (batched_randint(-5,0)/100), 3)
                    self.attributes.determinationModifier = round(self.attributes.determinationModifier + (batched_randint(-5,0)/100), 3)
                else:
                    self.attributes.determinationModifier = round(self.attributes.determinationModifier + (batched_randint(0,10)/100), 3)

            if self.attributes.confidenceModifier > 5:
                self.attributes.confidenceModifier = 5
            if self.attributes.determinationModifier > 5:
                self.attributes.determinationModifier = 5

            if self.attributes.confidenceModifier < -5:
                self.attributes.confidenceModifier = -5
            if self.attributes.determinationModifier < -5:
                self.attributes.determinationModifier = -5

        self.updateRating()

    def updateInGameRating(self):
        pass

    def updateRating(self):
        pass

    def updateInGameDetermination(self, value):
        self.gameAttributes.determinationModifier = round(self.gameAttributes.determinationModifier + value, 3)
        self.updateInGameRating()

    def updateInGameConfidence(self, value):
        self.gameAttributes.confidenceModifier = round(self.gameAttributes.confidenceModifier + value, 3)
        self.updateInGameRating()

    def offseasonTraining(self, coachDevRating: int = 50):
        pass


    def addPassTd(self, yards, isRegularSeason):
        self.stat_tracker.add_pass_td(yards, isRegularSeason)

    def addCompletion(self, isRegularSeason):
        self.stat_tracker.add_completion(isRegularSeason)

    def addInterception(self, isRegularSeason):
        self.stat_tracker.add_interception(isRegularSeason)

    def addPassAttempt(self, isRegularSeason):
        self.stat_tracker.add_pass_attempt(isRegularSeason)

    def addPassYards(self, yards, isRegularSeason):
        self.stat_tracker.add_pass_yards(yards, isRegularSeason)

    def addMissedPass(self, isRegularSeason):
        self.stat_tracker.add_missed_pass(isRegularSeason)

    def addRcvPassTarget(self, isRegularSeason):
        self.stat_tracker.add_rcv_pass_target(isRegularSeason)

    def addReception(self, isRegularSeason):
        self.stat_tracker.add_reception(isRegularSeason)

    def addPassDrop(self, isRegularSeason):
        self.stat_tracker.add_pass_drop(isRegularSeason)

    def addReceiveYards(self, yards, isRegularSeason):
        self.stat_tracker.add_receive_yards(yards, isRegularSeason)

    def addYAC(self, yac, isRegularSeason):
        self.stat_tracker.add_yac(yac, isRegularSeason)

    def addReceiveTd(self, yards, isRegularSeason):
        self.stat_tracker.add_receive_td(yards, isRegularSeason)

    def addCarry(self, isRegularSeason):
        self.stat_tracker.add_carry(isRegularSeason)

    def addRushTd(self, yards, isRegularSeason):
        self.stat_tracker.add_rush_td(yards, isRegularSeason)

    def addRushYards(self, yards, isRegularSeason):
        self.stat_tracker.add_rush_yards(yards, isRegularSeason)

    def addFumble(self, isRegularSeason):
        self.stat_tracker.add_fumble(isRegularSeason)

    def addFgAttempt(self, isRegularSeason):
        self.stat_tracker.add_fg_attempt(isRegularSeason)

    def addFg(self, yards, isRegularSeason):
        self.stat_tracker.add_fg(yards, isRegularSeason)
        
        # Handle additional stats not covered by base StatTracker
        if yards >= 40:
            self.gameStatsDict['kicking']['fg40+'] = self.gameStatsDict['kicking'].get('fg40+', 0) + 1
        if yards >= 45:
            self.gameStatsDict['kicking']['fg45+'] += 1
            if isRegularSeason:
                # Use .get() with default for safety when loading old player data
                self.seasonStatsDict['kicking']['fg45+'] = self.seasonStatsDict['kicking'].get('fg45+', 0) + 1
                self.careerStatsDict['kicking']['fg45+'] = self.careerStatsDict['kicking'].get('fg45+', 0) + 1
                
        # Handle distance-specific attempt tracking (these are tracked separately from makes)
        if isRegularSeason:
            if yards < 50 and yards > 39:
                self.seasonStatsDict['kicking']['fg40to50att'] = self.seasonStatsDict['kicking'].get('fg40to50att', 0) + 1
                self.careerStatsDict['kicking']['fg40to50att'] = self.careerStatsDict['kicking'].get('fg40to50att', 0) + 1
            elif yards < 40 and yards > 19:
                self.seasonStatsDict['kicking']['fg20to40att'] = self.seasonStatsDict['kicking'].get('fg20to40att', 0) + 1
                self.careerStatsDict['kicking']['fg20to40att'] = self.careerStatsDict['kicking'].get('fg20to40att', 0) + 1
            elif yards < 20:
                self.seasonStatsDict['kicking']['fgUnder20att'] = self.seasonStatsDict['kicking'].get('fgUnder20att', 0) + 1
                self.careerStatsDict['kicking']['fgUnder20att'] = self.careerStatsDict['kicking'].get('fgUnder20att', 0) + 1
            else:
                self.seasonStatsDict['kicking']['fgOver50att'] = self.seasonStatsDict['kicking'].get('fgOver50att', 0) + 1
                self.careerStatsDict['kicking']['fgOver50att'] = self.careerStatsDict['kicking'].get('fgOver50att', 0) + 1


    def addMissedFg(self, yards, isRegularSeason):
        if yards >= 40 and yards < 50:
            self.stat_tracker.add_fantasy_points(-1)
        elif yards < 40:
            self.stat_tracker.add_fantasy_points(-2)

        if isRegularSeason:
            if yards < 50 and yards > 39:
                self.seasonStatsDict['kicking']['fg40to50att'] = self.seasonStatsDict['kicking'].get('fg40to50att', 0) + 1
                self.careerStatsDict['kicking']['fg40to50att'] = self.careerStatsDict['kicking'].get('fg40to50att', 0) + 1
            elif yards < 40 and yards >= 20:
                self.seasonStatsDict['kicking']['fg20to40att'] = self.seasonStatsDict['kicking'].get('fg20to40att', 0) + 1
                self.careerStatsDict['kicking']['fg20to40att'] = self.careerStatsDict['kicking'].get('fg20to40att', 0) + 1
            elif yards < 20:
                self.seasonStatsDict['kicking']['fgUnder20att'] = self.seasonStatsDict['kicking'].get('fgUnder20att', 0) + 1
                self.careerStatsDict['kicking']['fgUnder20att'] = self.careerStatsDict['kicking'].get('fgUnder20att', 0) + 1
            else:
                self.seasonStatsDict['kicking']['fgOver50att'] = self.seasonStatsDict['kicking'].get('fgOver50att', 0) + 1
                self.careerStatsDict['kicking']['fgOver50att'] = self.careerStatsDict['kicking'].get('fgOver50att', 0) + 1


    def addExtraPoint(self):
        self.stat_tracker.add_fantasy_points(1)

    def addMissedExtraPoint(self):
        self.stat_tracker.add_fantasy_points(-3)


class PlayerAttributes:
    def __init__(self):
        self.overallRating = 0

        #physical attributes
        self.speed = 0
        self.hands = 0
        self.reach = 0
        self.agility = 0
        self.power = 0
        self.armStrength = 0
        self.accuracy = 0
        self.legStrength = 0
        self.skillRating = 0

        self.potentialSpeed = 0
        self.potentialHands = 0
        self.potentialReach = 0
        self.potentialAgility = 0
        self.potentialPower = 0
        self.potentialArmStrength = 0
        self.potentialAccuracy = 0
        self.potentialLegStrength = 0
        self.potentialSkillRating = 0

        #physical skills
        self.routeRunning = 0
        self.vision = 0
        self.blocking = 0
        self.blockingModifier = 0
        
        #dynamic personality attributes
        self.discipline = 0
        self.attitude = 0

        #static personality intangibles
        self.focus = 0
        self.instinct = 0
        self.creativity = 0
        self.resilience = 0
        self.clutchFactor = 0
        self.pressureHandling = randint(-10, 10)  # -10 (chokes) to +10 (thrives under pressure)

        self.longevity = randint(4,10)
        self.playMakingAbility = 0
        self.xFactor = 0

        #modifiers
        self.confidenceModifier = randint(-2, 2)
        self.determinationModifier = randint(-2, 2)
        self.luckModifier = randint(-5, 5)

        
    def calculateIntangibles(self):
        self.playMakingAbility = round((self.instinct+self.creativity)/2)
        self.xFactor = round((((self.focus*1.8) + (self.discipline*1.2))/3) + ((self.confidenceModifier*2.2)+(self.determinationModifier*1.2)/3) + (self.luckModifier))
        if self.xFactor > 100:
            self.xFactor = 100

    def calculateSkills(self):
        self.routeRunning = round(((self.speed*1.2) + (self.agility*1) + (self.xFactor*.8) + (self.playMakingAbility))/4)
        self.vision = round((self.discipline + self.instinct + self.focus)/3)
        self.blocking = round(((self.power*1.2) + (self.xFactor*.8))/2)
        self.blockingModifier = math.floor((self.blocking - 60)/6)
    
    def getPressureModifier(self, gamePressure: int) -> float:
        """Calculate performance modifier based on game pressure and player's pressure handling.
        
        Three possible outcomes: overperform, no effect, or underperform.
        Higher pressureHandling = more likely to overperform AND more likely to have no effect than underperform.
        Lower pressureHandling = more likely to underperform AND more likely to have no effect than overperform.
        
        Args:
            gamePressure: Current game pressure (0-100)
            
        Returns:
            Modifier that affects player performance (positive, zero, or negative)
        """
        # Normalize game pressure to 0-1 scale
        normalizedPressure = min(100, max(0, gamePressure)) / 100.0
        
        # In low pressure situations, minimal impact
        if normalizedPressure < 0.3:
            return 0
        
        # Calculate the magnitude of potential variance based on pressure and pressureHandling
        maxVariance = abs(self.pressureHandling) * normalizedPressure
        
        # Clutch factor increases the magnitude of potential swings
        clutchMultiplier = 1 + (self.clutchFactor / 100.0)
        maxVariance *= clutchMultiplier
        
        # Roll for outcome (1-100)
        roll = batched_randint(1, 100)

        # Map pressureHandling to probability zones
        # pressureHandling +10: overperform 60%, no effect 30%, underperform 10%
        # pressureHandling 0: overperform 15%, no effect 70%, underperform 15%
        # pressureHandling -10: overperform 10%, no effect 30%, underperform 60%

        # Calculate probability zones based on pressureHandling
        if self.pressureHandling >= 0:
            # Positive pressure handling: more overperform, less underperform
            overPerformChance = 15 + (self.pressureHandling * 4.5)  # 15 to 60
            noEffectChance = 70 - (self.pressureHandling * 4)       # 70 to 30
            # underperform is the remainder (15 to 10)
        else:
            # Negative pressure handling: less overperform, more underperform
            overPerformChance = 15 + (self.pressureHandling * 0.5)  # 15 to 10
            noEffectChance = 70 + (self.pressureHandling * 4)       # 70 to 30
            # underperform is the remainder (15 to 60)

        # High pressure compresses the no-effect zone — players are more
        # likely to either rise or crumble in big moments
        if normalizedPressure >= 0.7:
            compressionFactor = (normalizedPressure - 0.7) / 0.3  # 0→1 as pressure goes 70→100
            noEffectReduction = noEffectChance * 0.5 * compressionFactor
            noEffectChance -= noEffectReduction
            overPerformChance += noEffectReduction * 0.5
            # underperform (remainder) gets the other half
        
        if roll <= overPerformChance:
            # Overperform
            return batched_random() * maxVariance
        elif roll <= overPerformChance + noEffectChance:
            # No effect
            return 0
        else:
            # Underperform — use a variance floor so even neutral players can
            # produce choke-level modifiers under high pressure.  The floor only
            # kicks in when pressure is significant (≥0.5 normalised).
            chokeVariance = maxVariance
            if normalizedPressure >= 0.5:
                chokeVariance = max(2.0, maxVariance)
            return -(batched_random() * chokeVariance)


    def getPlayerAttributes(self, position, physicalSeed = None, mentalSeed = None):
        # Generate seeds if not provided
        if physicalSeed is None:
            physicalSeed = randint(60, 100)
        if mentalSeed is None:
            mentalSeed = randint(60, 100)
        
        # Physical skills: use physicalSeed as center with tight variance
        stdDev = 5
        numSkills = 3
        skillValList = np.random.normal(physicalSeed, stdDev, numSkills)
        skillValList = np.clip(skillValList, 60, 100)
        skillValList: list = skillValList.tolist()


        if position is Position.QB:
            self.armStrength = int(skillValList.pop(randint(0, len(skillValList)) - 1))
            self.accuracy = int(skillValList.pop(randint(0, len(skillValList)) - 1))
            self.agility = int(skillValList.pop(randint(0, len(skillValList)) - 1))
        elif position is Position.RB:
            self.power = int(skillValList.pop(randint(0, len(skillValList)) - 1))
            self.speed = int(skillValList.pop(randint(0, len(skillValList)) - 1))
            self.agility = int(skillValList.pop(randint(0, len(skillValList)) - 1))
            self.hands = np.random.normal(physicalSeed, stdDev)
            self.hands = int(np.clip(self.hands, 60, 100))
            self.reach = np.random.normal(physicalSeed, stdDev)
            self.reach = int(np.clip(self.reach, 60, 100))
        elif position is Position.WR:
            self.hands = int(skillValList.pop(randint(0, len(skillValList)) - 1))
            self.speed = int(skillValList.pop(randint(0, len(skillValList)) - 1))
            self.agility = int(skillValList.pop(randint(0, len(skillValList)) - 1))
            self.reach = np.random.normal(physicalSeed, stdDev)
            self.reach = int(np.clip(self.reach, 60, 100))
        elif position is Position.TE:
            self.hands = int(skillValList.pop(randint(0, len(skillValList)) - 1))
            self.power = int(skillValList.pop(randint(0, len(skillValList)) - 1))
            self.agility = int(skillValList.pop(randint(0, len(skillValList)) - 1))
            self.reach = np.random.normal(physicalSeed, stdDev)
            self.reach = int(np.clip(self.reach, 60, 100))
        elif position is Position.K:
            self.legStrength = int(skillValList.pop(randint(0, len(skillValList)) - 1))
            self.accuracy = int(skillValList.pop(randint(0, len(skillValList)) - 1))
            self.agility = int(skillValList.pop(randint(0, len(skillValList)) - 1))
        else:
            self.power = int(skillValList.pop(randint(0, len(skillValList)) - 1))
            self.speed = int(skillValList.pop(randint(0, len(skillValList)) - 1))
            self.agility = int(skillValList.pop(randint(0, len(skillValList)) - 1))

        # Intangibles: use mentalSeed as center with moderate variance
        # This allows independent control of physical vs mental abilities
        stdDev = 7
        numSkills = 6
        intSkillValList = np.random.normal(mentalSeed, stdDev, numSkills)
        intSkillValList = np.clip(intSkillValList, 60, 100)
        intSkillValList: list = intSkillValList.tolist()

        self.instinct = int(intSkillValList.pop(randint(0, len(intSkillValList)) - 1))
        self.focus = int(intSkillValList.pop(randint(0, len(intSkillValList)) - 1))
        self.creativity = int(intSkillValList.pop(randint(0, len(intSkillValList)) - 1))
        self.discipline = int(intSkillValList.pop(randint(0, len(intSkillValList)) - 1))
        self.attitude = int(intSkillValList.pop(randint(0, len(intSkillValList)) - 1))
        self.resilience = int(intSkillValList.pop(randint(0, len(intSkillValList)) - 1))

    def changeStat(self, value):
        if value >= 95:
            value += randint(-10, 0)
        elif value <= 75:
            value += randint(0, 10)
        else:
            value += randint(5, 5)


class PlayerQB(Player, CachedRatingMixin):
    def __init__(self, physicalSeed = None, mentalSeed = None):
        super().__init__()
        self.position = Position.QB
        self.attributes.getPlayerAttributes(self.position, physicalSeed, mentalSeed)
        self.updateRating()
        self.playerRating = self.attributes.overallRating

        self.attributes.potentialArmStrength = self.attributes.armStrength + randint(0,30)
        self.attributes.potentialAccuracy = self.attributes.accuracy + randint(0,30)
        self.attributes.potentialAgility = self.attributes.agility + randint(0,30)
        if self.attributes.potentialArmStrength > 100:
            self.attributes.potentialArmStrength = 100
        if self.attributes.potentialAccuracy > 100:
            self.attributes.potentialAccuracy = 100
        if self.attributes.potentialAgility > 100:
            self.attributes.potentialAgility = 100
        self.attributes.potentialSkillRating = round(((self.attributes.potentialArmStrength*1.2) + (self.attributes.potentialAccuracy*1.3) + (self.attributes.potentialAgility*.5))/3)

    def updateInGameRating(self):
        self.gameAttributes.calculateIntangibles()
        self.gameAttributes.calculateSkills()
        self.gameAttributes.skillRating = round(((self.gameAttributes.armStrength*1.2) + (self.gameAttributes.accuracy*1.3) + (self.gameAttributes.agility*.5))/3)
        self.gameAttributes.overallRating = round(((self.gameAttributes.skillRating*2) + (self.gameAttributes.playMakingAbility*1.5) + (self.gameAttributes.xFactor*1.5))/5)
        if self.gameAttributes.overallRating > 100:
            self.gameAttributes.overallRating = 100

    def _calculate_skill_rating(self) -> float:
        """Calculate QB-specific skill rating"""
        return round(((self.attributes.armStrength*1.2) + (self.attributes.accuracy*1.3) + (self.attributes.agility*.5))/3)
    
    def updateRating(self):
        self.attributes.calculateIntangibles()
        self.attributes.calculateSkills()
        
        # Use cached calculations
        self.attributes.skillRating = self.get_cached_skill_rating()
        self.attributes.overallRating = self.get_cached_overall_rating()
    
    def updateInGameRating(self):
        # Invalidate cache when game attributes change
        self.invalidate_rating_cache()
        self.gameAttributes.calculateIntangibles()
        self.gameAttributes.calculateSkills()
        
        # For game ratings, we still calculate directly since they change frequently
        self.gameAttributes.skillRating = round(((self.gameAttributes.armStrength*1.2) + (self.gameAttributes.accuracy*1.3) + (self.gameAttributes.agility*.5))/3)
        self.gameAttributes.overallRating = round(((self.gameAttributes.skillRating*2) + (self.gameAttributes.playMakingAbility*1.5) + (self.gameAttributes.xFactor*1.5))/5)
        if self.gameAttributes.overallRating > 100:
            self.gameAttributes.overallRating = 100


    def offseasonTraining(self, coachDevRating: int = 50):
        PlayerDevelopment.apply_offseason_training(self, "QB", coachDevRating=coachDevRating)
        self.updateRating()

class PlayerRB(Player):
    def __init__(self, physicalSeed = None, mentalSeed = None):
        super().__init__()
        self.position = Position.RB
        self.isOpen = False
        self.attributes.getPlayerAttributes(self.position, physicalSeed, mentalSeed)
        self.updateRating()
        self.playerRating = self.attributes.overallRating

        self.attributes.potentialSpeed = self.attributes.speed + randint(0,30)
        self.attributes.potentialPower = self.attributes.power + randint(0,30)
        self.attributes.potentialReach = self.attributes.reach + randint(0,30)
        self.attributes.potentialAgility = self.attributes.agility + randint(0,30)
        if self.attributes.potentialSpeed > 100:
            self.attributes.potentialSpeed = 100
        if self.attributes.potentialPower > 100:
            self.attributes.potentialPower = 100
        if self.attributes.potentialReach > 100:
            self.attributes.potentialReach = 100
        if self.attributes.potentialAgility > 100:
            self.attributes.potentialAgility = 100
        self.attributes.potentialSkillRating = round(((self.attributes.potentialPower*1.2) + (self.attributes.potentialSpeed*1.3) + (self.attributes.potentialAgility*.5))/3)

    def updateInGameRating(self):
        self.gameAttributes.calculateIntangibles()
        self.gameAttributes.calculateSkills()
        self.gameAttributes.skillRating = round(((self.gameAttributes.speed*.7) + (self.gameAttributes.power*1.3) + (self.gameAttributes.agility*1))/3)
        self.gameAttributes.overallRating = round(((self.gameAttributes.skillRating*2) + (self.gameAttributes.playMakingAbility*1.5) + (self.gameAttributes.xFactor*1.5))/5)
        if self.gameAttributes.overallRating > 100:
            self.gameAttributes.overallRating = 100

    def updateRating(self):
        self.attributes.calculateIntangibles()
        self.attributes.calculateSkills()
        self.attributes.skillRating = round(((self.attributes.speed*.7) + (self.attributes.power*1.3) + (self.attributes.agility*1))/3)
        self.attributes.overallRating = round(((self.attributes.skillRating*2) + (self.attributes.playMakingAbility*1.5) + (self.attributes.xFactor*1.5))/5)


    def offseasonTraining(self, coachDevRating: int = 50):
        PlayerDevelopment.apply_offseason_training(self, "RB", coachDevRating=coachDevRating)
        self.updateRating()
        
class PlayerWR(Player):
    def __init__(self, physicalSeed = None, mentalSeed = None):
        super().__init__()
        self.position = Position.WR
        self.isOpen = False
        self.attributes.getPlayerAttributes(self.position, physicalSeed, mentalSeed)
        self.updateRating()
        self.playerRating = self.attributes.overallRating

        self.attributes.potentialSpeed = self.attributes.speed + randint(0,30)
        self.attributes.potentialHands = self.attributes.hands + randint(0,30)
        self.attributes.potentialReach = self.attributes.reach + randint(0,30)
        self.attributes.potentialAgility = self.attributes.agility + randint(0,30)
        if self.attributes.potentialSpeed > 100:
            self.attributes.potentialSpeed = 100
        if self.attributes.potentialHands > 100:
            self.attributes.potentialHands = 100
        if self.attributes.potentialReach > 100:
            self.attributes.potentialReach = 100
        if self.attributes.potentialAgility > 100:
            self.attributes.potentialAgility = 100
        self.attributes.potentialSkillRating = round(((self.attributes.potentialHands*1.2) + (self.attributes.potentialSpeed*1.3) + (self.attributes.potentialAgility*.5))/3)

    def updateInGameRating(self):
        self.gameAttributes.calculateIntangibles()
        self.gameAttributes.calculateSkills()
        self.gameAttributes.skillRating = round(((self.gameAttributes.speed*.7) + (self.gameAttributes.hands*1.5) + (self.gameAttributes.agility*.8))/3)
        self.gameAttributes.overallRating = round(((self.gameAttributes.skillRating*2) + (self.gameAttributes.playMakingAbility*1.5) + (self.gameAttributes.xFactor*1.5))/5)
        if self.gameAttributes.overallRating > 100:
            self.gameAttributes.overallRating = 100

    def updateRating(self):
        self.attributes.calculateIntangibles()
        self.attributes.calculateSkills()
        self.attributes.skillRating = round(((self.attributes.speed*.7) + (self.attributes.hands*1.5) + (self.attributes.agility*.8))/3)
        self.attributes.overallRating = round(((self.attributes.skillRating*2) + (self.attributes.playMakingAbility*1.5) + (self.attributes.xFactor*1.5))/5)


    def offseasonTraining(self, coachDevRating: int = 50):
        PlayerDevelopment.apply_offseason_training(self, "WR", coachDevRating=coachDevRating)
        self.updateRating()

class PlayerTE(Player):
    def __init__(self, physicalSeed = None, mentalSeed = None):
        super().__init__()
        self.position = Position.TE
        self.isOpen = False
        self.attributes.getPlayerAttributes(self.position, physicalSeed, mentalSeed)
        self.updateRating()
        self.playerRating = self.attributes.overallRating

        self.attributes.potentialHands = self.attributes.hands + randint(0,30)
        self.attributes.potentialReach = self.attributes.reach + randint(0,30)
        self.attributes.potentialPower = self.attributes.power + randint(0,30)
        self.attributes.potentialAgility = self.attributes.agility + randint(0,30)
        if self.attributes.potentialHands > 100:
            self.attributes.potentialHands = 100
        if self.attributes.potentialReach > 100:
            self.attributes.potentialReach = 100
        if self.attributes.potentialPower > 100:
            self.attributes.potentialPower = 100
        if self.attributes.potentialAgility > 100:
            self.attributes.potentialAgility = 100
        self.attributes.potentialSkillRating = round(((self.attributes.potentialPower*1.2) + (self.attributes.potentialHands*1.3) + (self.attributes.potentialAgility*.5))/3)
    
    def updateInGameRating(self):
        self.gameAttributes.calculateIntangibles()
        self.gameAttributes.calculateSkills()
        self.gameAttributes.skillRating = round(((self.gameAttributes.power*1.3) + (self.gameAttributes.hands*1) + (self.gameAttributes.agility*.7))/3)
        self.gameAttributes.overallRating = round(((self.gameAttributes.skillRating*2) + (self.gameAttributes.playMakingAbility*1.5) + (self.gameAttributes.xFactor*1.5))/5)
        if self.gameAttributes.overallRating > 100:
            self.gameAttributes.overallRating = 100

    def updateRating(self):
        self.attributes.calculateIntangibles()
        self.attributes.calculateSkills()
        self.attributes.skillRating = round(((self.attributes.power*1.3) + (self.attributes.hands*1) + (self.attributes.agility*.7))/3)
        self.attributes.overallRating = round(((self.attributes.skillRating*2) + (self.attributes.playMakingAbility*1.5) + (self.attributes.xFactor*1.5))/5)
        self.playerRating = self.attributes.overallRating


    def offseasonTraining(self, coachDevRating: int = 50):
        PlayerDevelopment.apply_offseason_training(self, "TE", coachDevRating=coachDevRating)
        self.updateRating()

class PlayerK(Player):
    def __init__(self, physicalSeed = None, mentalSeed = None):
        super().__init__()
        self.position = Position.K
        self.maxFgDistance = 0
        self.attributes.getPlayerAttributes(self.position, physicalSeed, mentalSeed)
        self.updateRating()
        self.playerRating = self.attributes.overallRating

        self.attributes.potentialLegStrength = self.attributes.legStrength + randint(0,30)
        self.attributes.potentialAccuracy = self.attributes.accuracy + randint(0,30)
        if self.attributes.potentialLegStrength > 100:
            self.attributes.potentialLegStrength = 100
        if self.attributes.potentialAccuracy > 100:
            self.attributes.potentialAccuracy = 100
        self.attributes.potentialSkillRating = round((self.attributes.potentialLegStrength + self.attributes.potentialAccuracy)/2)
    
    def updateInGameRating(self):
        self.gameAttributes.calculateIntangibles()
        self.gameAttributes.calculateSkills()
        self.gameAttributes.skillRating = round((self.gameAttributes.legStrength + self.gameAttributes.accuracy)/2)
        self.gameAttributes.overallRating = round(((self.gameAttributes.skillRating*2) + (self.gameAttributes.playMakingAbility*1.5) + (self.gameAttributes.xFactor*1.5))/5)
        if self.gameAttributes.overallRating > 100:
            self.gameAttributes.overallRating = 100

    def updateRating(self):
        self.attributes.calculateIntangibles()
        self.attributes.calculateSkills()
        self.attributes.skillRating = round((self.attributes.legStrength + self.attributes.accuracy)/2)
        self.attributes.overallRating = round(((self.attributes.skillRating*2) + (self.attributes.playMakingAbility*1.5) + (self.attributes.xFactor*1.5))/5)
        self.maxFgDistance = round(70*(self.attributes.legStrength/100))


    def offseasonTraining(self, coachDevRating: int = 50):
        PlayerDevelopment.apply_offseason_training(self, "K", coachDevRating=coachDevRating)
        self.updateRating()