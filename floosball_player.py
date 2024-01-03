import enum
from os import stat
import math
from random import randint
import copy
import floosball_methods as FloosMethods
from floosball_team import Team

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
        self.attributes = PlayerAttributes(seed)
        self.gameAttributes: PlayerAttributes = None
        self.playerTier = PlayerTier
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

        self.gameStatsDict = copy.deepcopy(playerStatsDict)
        self.seasonStatsDict = copy.deepcopy(playerStatsDict)
        self.careerStatsDict = copy.deepcopy(playerStatsDict)

        self.seasonStatsArchive = []

    def postgameChanges(self):
        self.attributes.confidenceModifier = round((self.attributes.confidenceModifier + self.gameAttributes.confidenceModifier)/2, 3)
        self.attributes.determinationModifier = round((self.attributes.determinationModifier + self.gameAttributes.determinationModifier)/2, 3)
        self.gamesPlayed += 1
        self.seasonStatsDict['gp'] = self.gamesPlayed
        if isinstance(self.team,Team):
            if self.team.winningStreak:
                self.attributes.confidenceModifier = round(self.attributes.confidenceModifier + (randint(0,25)/100), 3)
            elif self.team.seasonTeamStats['streak'] < -2:
                if self.attributes.attitude < 70:
                    self.attributes.confidenceModifier = round(self.attributes.confidenceModifier + (randint(-20,0)/100), 3)
                    self.attributes.determinationModifier = round(self.attributes.determinationModifier + (randint(-20,0)/100), 3)
                elif self.attributes.attitude < 80:
                    self.attributes.confidenceModifier = round(self.attributes.confidenceModifier + (randint(-10,0)/100), 3)
                    self.attributes.determinationModifier = round(self.attributes.determinationModifier + (randint(-10,0)/100), 3)
                elif self.attributes.attitude < 90:
                    self.attributes.confidenceModifier = round(self.attributes.confidenceModifier + (randint(-5,0)/100), 3)
                    self.attributes.determinationModifier = round(self.attributes.determinationModifier + (randint(-5,0)/100), 3)
                else:
                    self.attributes.determinationModifier = round(self.attributes.determinationModifier + (randint(0,10)/100), 3)

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

    def offseasonTraining(self):
        pass


    def addPassTd(self, yards, isRegularSeason):
        self.gameStatsDict['passing']['tds'] += 1
        self.gameStatsDict['fantasyPoints'] += 4
        if yards >= 40:
            self.gameStatsDict['fantasyPoints'] += 2

        if isRegularSeason:
            self.seasonStatsDict['passing']['tds'] += 1
            self.careerStatsDict['passing']['tds'] += 1

    def addCompletion(self, isRegularSeason):
        self.gameStatsDict['passing']['comp'] += 1

        if isRegularSeason:
            self.seasonStatsDict['passing']['comp'] += 1
            self.careerStatsDict['passing']['comp'] += 1

    def addInterception(self, isRegularSeason):
        self.gameStatsDict['passing']['ints'] += 1
        self.gameStatsDict['fantasyPoints'] += -2

        if isRegularSeason:
            self.seasonStatsDict['passing']['ints'] += 1
            self.careerStatsDict['passing']['ints'] += 1

    def addPassAttempt(self, isRegularSeason):
        self.gameStatsDict['passing']['att'] += 1

        if isRegularSeason:
            self.seasonStatsDict['passing']['att'] += 1
            self.careerStatsDict['passing']['att'] += 1

    def addPassYards(self, yards, isRegularSeason):
        if (math.floor((self.gameStatsDict['passing']['yards'] + yards) / 25)) > (math.floor(self.gameStatsDict['passing']['yards'] / 25)):
            self.gameStatsDict['fantasyPoints'] += (math.floor((self.gameStatsDict['passing']['yards'] + yards) / 25) - math.floor(self.gameStatsDict['passing']['yards'] / 25))

        self.gameStatsDict['passing']['yards'] += yards

        if isRegularSeason:
            self.seasonStatsDict['passing']['yards'] += yards
            self.careerStatsDict['passing']['yards'] += yards

    def addMissedPass(self, isRegularSeason):
        self.gameStatsDict['passing']['missedPass'] += 1

        if isRegularSeason:
            self.seasonStatsDict['passing']['missedPass'] += 1
            self.careerStatsDict['passing']['missedPass'] += 1

    def addRcvPassTarget(self, isRegularSeason):
        self.gameStatsDict['receiving']['targets'] += 1

        if isRegularSeason:
            self.seasonStatsDict['receiving']['targets'] += 1
            self.careerStatsDict['receiving']['targets'] += 1

    def addReception(self, isRegularSeason):
        self.gameStatsDict['receiving']['receptions'] += 1

        if isRegularSeason:
            self.seasonStatsDict['receiving']['receptions'] += 1
            self.careerStatsDict['receiving']['receptions'] += 1

    def addPassDrop(self, isRegularSeason):
        self.gameStatsDict['receiving']['drops'] += 1

        if isRegularSeason:
            self.seasonStatsDict['receiving']['drops'] += 1
            self.careerStatsDict['receiving']['drops'] += 1

    def addReceiveYards(self, yards, isRegularSeason):
        if (math.floor((self.gameStatsDict['receiving']['yards'] + yards) / 10)) > (math.floor(self.gameStatsDict['receiving']['yards'] / 10)):
            self.gameStatsDict['fantasyPoints'] += (math.floor((self.gameStatsDict['receiving']['yards'] + yards) / 10) - math.floor(self.gameStatsDict['receiving']['yards'] / 10))

        self.gameStatsDict['receiving']['yards'] += yards

        if isRegularSeason:
            self.seasonStatsDict['receiving']['yards'] += yards
            self.careerStatsDict['receiving']['yards'] += yards

    def addYAC(self, yac, isRegularSeason):
        self.gameStatsDict['receiving']['yac'] += yac

        if isRegularSeason:
            self.seasonStatsDict['receiving']['yac'] += yac
            self.careerStatsDict['receiving']['yac'] += yac

    def addReceiveTd(self, yards, isRegularSeason):
        self.gameStatsDict['receiving']['tds'] += 1
        self.gameStatsDict['fantasyPoints'] += 6
        if yards >= 40:
            self.gameStatsDict['fantasyPoints'] += 2

        if isRegularSeason:
            self.seasonStatsDict['receiving']['tds'] += 1
            self.careerStatsDict['receiving']['tds'] += 1

    def addCarry(self, isRegularSeason):
        self.gameStatsDict['rushing']['carries'] += 1

        if isRegularSeason:
            self.seasonStatsDict['rushing']['carries'] += 1
            self.careerStatsDict['rushing']['carries'] += 1

    def addRushTd(self, yards, isRegularSeason):
        self.gameStatsDict['rushing']['tds'] += 1
        self.gameStatsDict['fantasyPoints'] += 6
        if yards >= 40:
            self.gameStatsDict['fantasyPoints'] += 2

        if isRegularSeason:
            self.seasonStatsDict['rushing']['tds'] += 1
            self.careerStatsDict['rushing']['tds'] += 1

    def addRushYards(self, yards, isRegularSeason):
        if (math.floor((self.gameStatsDict['rushing']['yards'] + yards) / 10)) > (math.floor(self.gameStatsDict['rushing']['yards'] / 10)):
            self.gameStatsDict['fantasyPoints'] += (math.floor((self.gameStatsDict['rushing']['yards'] + yards) / 10) - math.floor(self.gameStatsDict['rushing']['yards'] / 10))

        self.gameStatsDict['rushing']['yards'] += yards

        if isRegularSeason:
            self.seasonStatsDict['rushing']['yards'] += yards
            self.careerStatsDict['rushing']['yards'] += yards

    def addFumble(self, isRegularSeason):
        self.gameStatsDict['rushing']['fumblesLost'] += 1
        self.gameStatsDict['fantasyPoints'] += -2

        if isRegularSeason:
            self.seasonStatsDict['rushing']['fumblesLost'] += 1
            self.careerStatsDict['rushing']['fumblesLost'] += 1

    def addFgAttempt(self, isRegularSeason):
        self.gameStatsDict['kicking']['fgAtt'] += 1

        if isRegularSeason:
            self.seasonStatsDict['kicking']['fgAtt'] += 1
            self.careerStatsDict['kicking']['fgAtt'] += 1

    def addFg(self, yards, isRegularSeason):
        self.gameStatsDict['kicking']['fgs'] += 1
        self.gameStatsDict['kicking']['fgYards'] += yards

        if yards >= 50:
            self.gameStatsDict['fantasyPoints'] += 5
        elif yards >= 40:
            self.gameStatsDict['fantasyPoints'] += 4
        else:
            self.gameStatsDict['fantasyPoints'] += 3

        if yards >= 45:
            self.gameStatsDict['kicking']['fg45+'] += 1


        if isRegularSeason:
            self.seasonStatsDict['kicking']['fgs'] += 1
            self.careerStatsDict['kicking']['fgs'] += 1
            self.seasonStatsDict['kicking']['fgYards'] += yards
            self.careerStatsDict['kicking']['fgYards'] += yards
            if yards >= 45:
                self.seasonStatsDict['kicking']['fg45+'] += 1
                self.careerStatsDict['kicking']['fg45+'] += 1

            if yards < 50 and yards > 39:
                self.seasonStatsDict['kicking']['fg40to50att'] += 1
                self.seasonStatsDict['kicking']['fg40to50'] += 1
                self.careerStatsDict['kicking']['fg40to50att'] += 1
                self.careerStatsDict['kicking']['fg40to50'] += 1
            elif yards < 40 and yards > 19:
                self.seasonStatsDict['kicking']['fg20to40att'] += 1
                self.seasonStatsDict['kicking']['fg20to40'] += 1
                self.careerStatsDict['kicking']['fg20to40att'] += 1
                self.careerStatsDict['kicking']['fg20to40'] += 1
            elif yards < 20:
                self.seasonStatsDict['kicking']['fgUnder20att'] += 1
                self.seasonStatsDict['kicking']['fgUnder20'] += 1
                self.careerStatsDict['kicking']['fgUnder20att'] += 1
                self.careerStatsDict['kicking']['fgUnder20'] += 1
            else:
                self.seasonStatsDict['kicking']['fgOver50att'] += 1
                self.seasonStatsDict['kicking']['fgOver50'] += 1
                self.careerStatsDict['kicking']['fgOver50att'] += 1
                self.careerStatsDict['kicking']['fgOver50'] += 1


    def addMissedFg(self, yards, isRegularSeason):
        if yards >= 40 and yards < 50:
            self.gameStatsDict['fantasyPoints'] += -1
        elif yards < 40:
            self.gameStatsDict['fantasyPoints'] += -2

        if isRegularSeason:
            if yards < 50 and yards > 39:
                self.seasonStatsDict['kicking']['fg40to50att'] += 1
                self.careerStatsDict['kicking']['fg40to50att'] += 1
            elif yards < 40 and yards >= 20:
                self.seasonStatsDict['kicking']['fg20to40att'] += 1
                self.careerStatsDict['kicking']['fg20to40att'] += 1
            elif yards < 20:
                self.seasonStatsDict['kicking']['fgUnder20att'] += 1
                self.careerStatsDict['kicking']['fgUnder20att'] += 1
            else:
                self.seasonStatsDict['kicking']['fgOver50att'] += 1
                self.careerStatsDict['kicking']['fgOver50att'] += 1


    def addExtraPoint(self):
        self.gameStatsDict['fantasyPoints'] += 1

    def addMissedExtraPoint(self):
        self.gameStatsDict['fantasyPoints'] += -3


class PlayerAttributes:
    def __init__(self, seed = None):
        self.overallRating = 0

        #attributes
        self.speed = 0
        self.hands = 0
        self.agility = 0
        self.power = 0
        self.armStrength = 0
        self.accuracy = 0
        self.legStrength = 0
        self.skillRating = 0

        self.potentialSpeed = 0
        self.potentialHands = 0
        self.potentialAgility = 0
        self.potentialPower = 0
        self.potentialArmStrength = 0
        self.potentialAccuracy = 0
        self.potentialLegStrength = 0
        self.potentialSkillRating = 0

        #skills
        self.routeRunning = 0
        self.vision = 0
        self.blocking = 0
        self.blockingModifier = 0
        
        #intangibles
        self.discipline = 0
        self.focus = 0
        self.instinct = 0
        self.creativity = 0
        self.attitude = 0


        self.longevity = randint(4,10)
        self.playMakingAbility = 0
        self.xFactor = 0

        #modifiers
        self.confidenceModifier = randint(-2, 2)
        self.determinationModifier = randint(-2, 2)
        self.luckModifier = randint(-5, 5)

        
    def calculateIntangibles(self):
        self.playMakingAbility = round((self.instinct+self.creativity)/2)
        self.xFactor = round((((self.focus*1.8) + (self.discipline*1.2))/3) + ((self.confidenceModifier*1.8)+(self.determinationModifier*1.2)/3) + (self.luckModifier))
        if self.xFactor > 100:
            self.xFactor = 100

    def calculateSkills(self):
        self.routeRunning = round(((self.speed*1.2) + (self.agility*1) + (self.xFactor*.8) + (self.playMakingAbility))/4)
        self.vision = round((self.discipline + self.instinct + self.focus)/3)
        self.blocking = round(((self.power*1.2) + (self.xFactor*.8))/2)
        self.blockingModifier = math.floor((self.blocking - 60)/6)


    def getPlayerAttributes(self, position, seed = None):
        x = 0
        if seed is None:
            x = randint(1, 100)
        else:
            x = seed

        skillValList = []
        if x >= 97:
            # Tier S array
           for y in range(8):
                if y <= 3:
                    skillValList.append(randint(90, 100))
                else:
                    skillValList.append(randint(75, 89))
        elif x >= 80 and x < 95:
            # Tier A array
           for y in range(8):
                if y < 1:
                    skillValList.append(randint(90, 100))
                else:
                    skillValList.append(randint(75, 89))
        else:
           for y in range(8):
                skillValList.append(randint(60, 100))


        if position is Position.QB:
            self.armStrength = skillValList.pop(randint(0, len(skillValList)) - 1)
            self.accuracy = skillValList.pop(randint(0, len(skillValList)) - 1)
            self.agility = skillValList.pop(randint(0, len(skillValList)) - 1)
        elif position is Position.RB:
            self.power = skillValList.pop(randint(0, len(skillValList)) - 1)
            self.speed = skillValList.pop(randint(0, len(skillValList)) - 1)
            self.agility = skillValList.pop(randint(0, len(skillValList)) - 1)
            self.hands = randint(60, 100)
        elif position is Position.WR:
            self.hands = skillValList.pop(randint(0, len(skillValList)) - 1)
            self.speed = skillValList.pop(randint(0, len(skillValList)) - 1)
            self.agility = skillValList.pop(randint(0, len(skillValList)) - 1)
        elif position is Position.TE:
            self.hands = skillValList.pop(randint(0, len(skillValList)) - 1)
            self.power = skillValList.pop(randint(0, len(skillValList)) - 1)
            self.agility = skillValList.pop(randint(0, len(skillValList)) - 1)
        elif position is Position.K:
            self.legStrength = skillValList.pop(randint(0, len(skillValList)) - 1)
            self.accuracy = skillValList.pop(randint(0, len(skillValList)) - 1)
            self.agility = skillValList.pop(randint(0, len(skillValList)) - 1)
        else:
            self.power = skillValList.pop(randint(0, len(skillValList)) - 1)
            self.speed = skillValList.pop(randint(0, len(skillValList)) - 1)
            self.agility = skillValList.pop(randint(0, len(skillValList)) - 1)


        self.instinct = skillValList.pop(randint(0, len(skillValList)) - 1)
        self.focus = skillValList.pop(randint(0, len(skillValList)) - 1)
        self.creativity = skillValList.pop(randint(0, len(skillValList)) - 1)
        self.discipline = skillValList.pop(randint(0, len(skillValList)) - 1)
        self.attitude = skillValList.pop(randint(0, len(skillValList)) - 1)

    def changeStat(self, value):
        if value >= 95:
            value += randint(-10, 0)
        elif value <= 75:
            value += randint(0, 10)
        else:
            value += randint(5, 5)


class PlayerQB(Player):
    def __init__(self, seed = None):
        super().__init__()
        self.position = Position.QB
        self.attributes.getPlayerAttributes(self.position, seed)
        self.updateRating()

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

    def updateRating(self):
        self.attributes.calculateIntangibles()
        self.attributes.calculateSkills()
        self.attributes.skillRating = round(((self.attributes.armStrength*1.2) + (self.attributes.accuracy*1.3) + (self.attributes.agility*.5))/3)
        self.attributes.overallRating = round(((self.attributes.skillRating*2) + (self.attributes.playMakingAbility*1.5) + (self.attributes.xFactor*1.5))/5)
        self.playerRating = self.attributes.overallRating


    def offseasonTraining(self):
        self.attributes.attitude += randint(-5,5)
        if self.attributes.attitude > 100:
            self.attributes.attitude = 100
        if self.attributes.attitude < 0:
            self.attributes.attitude = 0
        self.attributes.discipline += randint(-5,5)
        if self.attributes.discipline > 100:
            self.attributes.discipline = 100
        self.attributes.calculateIntangibles()

        if self.seasonsPlayed > self.attributes.longevity:
            if self.attributes.xFactor > 90:
                if self.attributes.armStrength >= 95:
                    self.attributes.armStrength += randint(0,2)
                elif self.attributes.armStrength <= 70:
                    self.attributes.armStrength += randint(0,10)
                else:
                    self.attributes.armStrength += randint(0,5)
                

                if self.attributes.accuracy >= 95:
                    self.attributes.accuracy += randint(0,3)
                elif self.attributes.accuracy <= 70:
                    self.attributes.accuracy += randint(0,10)
                else:
                    self.attributes.accuracy += randint(0,5)  

                if self.attributes.agility >= 95:
                    self.attributes.agility += randint(0,2)
                elif self.attributes.agility <= 70:
                    self.attributes.agility += randint(0,10)
                else:
                    self.attributes.agility += randint(0,5)

            elif self.attributes.xFactor > 75:
                if self.attributes.armStrength >= 95:
                    self.attributes.armStrength += randint(-1,2)
                elif self.attributes.armStrength <= 70:
                    self.attributes.armStrength += randint(0,7)
                else:
                    self.attributes.armStrength += randint(-2,3)

                if self.attributes.accuracy >= 95:
                    self.attributes.accuracy += randint(-1,2)
                elif self.attributes.accuracy <= 70:
                    self.attributes.accuracy += randint(0,7)
                else:
                    self.attributes.accuracy += randint(-2,3)

                if self.attributes.agility >= 95:
                    self.attributes.agility += randint(-1,2)
                elif self.attributes.agility <= 70:
                    self.attributes.agility += randint(0,7)
                else:
                    self.attributes.agility += randint(-2,3)

            else:
                if self.attributes.armStrength >= 95:
                    self.attributes.armStrength += randint(-5,1)
                elif self.attributes.armStrength <= 70:
                    self.attributes.armStrength += randint(0,5)
                else:
                    self.attributes.armStrength += randint(-5,5)

                if self.attributes.accuracy >= 95:
                    self.attributes.accuracy += randint(-5,1)
                elif self.attributes.accuracy <= 70:
                    self.attributes.accuracy += randint(0,5)
                else:
                    self.attributes.accuracy += randint(-5,5)  

                if self.attributes.agility >= 95:
                    self.attributes.agility += randint(-5,1)
                elif self.attributes.agility <= 70:
                    self.attributes.agility += randint(0,5)
                else:
                    self.attributes.agility += randint(-5,5)
        else:
            if self.attributes.xFactor > 90:
                if self.attributes.armStrength >= 95:
                    self.attributes.armStrength += randint(-3,0)
                elif self.attributes.armStrength <= 70:
                    self.attributes.armStrength += randint(-1,5)
                else:
                    self.attributes.armStrength += randint(-3,3)

                if self.attributes.accuracy >= 95:
                    self.attributes.accuracy += randint(-3,0)
                elif self.attributes.accuracy <= 70:
                    self.attributes.accuracy += randint(-1,5)
                else:
                    self.attributes.accuracy += randint(-3,3)  

                if self.attributes.agility >= 95:
                    self.attributes.agility += randint(-3,0)
                elif self.attributes.agility <= 70:
                    self.attributes.agility += randint(-1,5)
                else:
                    self.attributes.agility += randint(-3,3)

            elif self.attributes.xFactor > 75:
                if self.attributes.armStrength >= 95:
                    self.attributes.armStrength += randint(-5,0)
                elif self.attributes.armStrength <= 70:
                    self.attributes.armStrength += randint(-3,3)
                else:
                    self.attributes.armStrength += randint(-5,2)

                if self.attributes.accuracy >= 95:
                    self.attributes.accuracy += randint(-5,0)
                elif self.attributes.accuracy <= 70:
                    self.attributes.accuracy += randint(-3,3)
                else:
                    self.attributes.accuracy += randint(-5,2)

                if self.attributes.agility >= 95:
                    self.attributes.agility += randint(-5,0)
                elif self.attributes.agility <= 70:
                    self.attributes.agility += randint(-3,3)
                else:
                    self.attributes.agility += randint(-5,2)

            else:
                if self.attributes.armStrength >= 95:
                    self.attributes.armStrength += randint(-10,0)
                elif self.attributes.armStrength <= 70:
                    self.attributes.armStrength += randint(-5,2)
                else:
                    self.attributes.armStrength += randint(-7,1)

                if self.attributes.accuracy >= 95:
                    self.attributes.accuracy += randint(-10,0)
                elif self.attributes.accuracy <= 70:
                    self.attributes.accuracy += randint(-5,2)
                else:
                    self.attributes.accuracy += randint(-7,1)  

                if self.attributes.agility >= 95:
                    self.attributes.agility += randint(-10,0)
                elif self.attributes.agility <= 70:
                    self.attributes.agility += randint(-5,2)
                else:
                    self.attributes.agility += randint(-7,1)

        if self.attributes.armStrength > self.attributes.potentialArmStrength:
            self.attributes.armStrength = self.attributes.potentialArmStrength
        if self.attributes.armStrength < 60:
            self.attributes.armStrength = 60
        if self.attributes.accuracy > self.attributes.potentialAccuracy:
            self.attributes.accuracy = self.attributes.potentialAccuracy
        if self.attributes.accuracy < 60:
            self.attributes.accuracy = 60
        if self.attributes.agility > self.attributes.potentialAgility:
            self.attributes.agility = self.attributes.potentialAgility 
        if self.attributes.agility < 60:
            self.attributes.agility = 60

        self.updateRating()

class PlayerRB(Player):
    def __init__(self, seed = None):
        super().__init__()
        self.position = Position.RB
        self.isOpen = False
        self.attributes.getPlayerAttributes(self.position, seed)

        self.updateRating()

        self.attributes.potentialSpeed = self.attributes.speed + randint(0,30)
        self.attributes.potentialPower = self.attributes.power + randint(0,30)
        self.attributes.potentialAgility = self.attributes.agility + randint(0,30)
        if self.attributes.potentialSpeed > 100:
            self.attributes.potentialSpeed = 100
        if self.attributes.potentialPower > 100:
            self.attributes.potentialPower = 100
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
        self.playerRating = self.attributes.overallRating


    def offseasonTraining(self):
        self.attributes.attitude += randint(-5,5)
        if self.attributes.attitude > 100:
            self.attributes.attitude = 100
        if self.attributes.attitude < 0:
            self.attributes.attitude = 0
        self.attributes.discipline += randint(-5,5)
        if self.attributes.discipline > 100:
            self.attributes.discipline = 100
        self.attributes.calculateIntangibles()

        if self.seasonsPlayed > self.attributes.longevity:
            if self.attributes.xFactor > 90:
                if self.attributes.power >= 95:
                    self.attributes.power += randint(0,2)
                elif self.attributes.power <= 70:
                    self.attributes.power += randint(0,10)
                else:
                    self.attributes.power += randint(0,5)

                if self.attributes.speed >= 95:
                    self.attributes.speed += randint(0,3)
                elif self.attributes.speed <= 70:
                    self.attributes.speed += randint(0,10)
                else:
                    self.attributes.speed += randint(0,5)  

                if self.attributes.agility >= 95:
                    self.attributes.agility += randint(0,2)
                elif self.attributes.agility <= 70:
                    self.attributes.agility += randint(0,10)
                else:
                    self.attributes.agility += randint(0,5)

            elif self.attributes.xFactor > 75:
                if self.attributes.power >= 95:
                    self.attributes.power += randint(-1,2)
                elif self.attributes.power <= 70:
                    self.attributes.power += randint(0,7)
                else:
                    self.attributes.power += randint(-2,3)

                if self.attributes.speed >= 95:
                    self.attributes.speed += randint(-1,2)
                elif self.attributes.speed <= 70:
                    self.attributes.speed += randint(0,7)
                else:
                    self.attributes.speed += randint(-2,3)

                if self.attributes.agility >= 95:
                    self.attributes.agility += randint(-1,2)
                elif self.attributes.agility <= 70:
                    self.attributes.agility += randint(0,7)
                else:
                    self.attributes.agility += randint(-2,3)

            else:
                if self.attributes.power >= 95:
                    self.attributes.power += randint(-5,1)
                elif self.attributes.power <= 70:
                    self.attributes.power += randint(0,5)
                else:
                    self.attributes.power += randint(-5,5)

                if self.attributes.speed >= 95:
                    self.attributes.speed += randint(-5,1)
                elif self.attributes.speed <= 70:
                    self.attributes.speed += randint(0,5)
                else:
                    self.attributes.speed += randint(-5,5)  

                if self.attributes.agility >= 95:
                    self.attributes.agility += randint(-5,1)
                elif self.attributes.agility <= 70:
                    self.attributes.agility += randint(0,5)
                else:
                    self.attributes.agility += randint(-5,5)
        else:
            if self.attributes.xFactor > 90:
                if self.attributes.power >= 95:
                    self.attributes.power += randint(-3,0)
                elif self.attributes.power <= 70:
                    self.attributes.power += randint(-1,5)
                else:
                    self.attributes.power += randint(-3,3)

                if self.attributes.speed >= 95:
                    self.attributes.speed += randint(-3,0)
                elif self.attributes.speed <= 70:
                    self.attributes.speed += randint(-1,5)
                else:
                    self.attributes.speed += randint(-3,3)  

                if self.attributes.agility >= 95:
                    self.attributes.agility += randint(-3,0)
                elif self.attributes.agility <= 70:
                    self.attributes.agility += randint(-1,5)
                else:
                    self.attributes.agility += randint(-3,3)

            elif self.attributes.xFactor > 75:
                if self.attributes.power >= 95:
                    self.attributes.power += randint(-5,0)
                elif self.attributes.power <= 70:
                    self.attributes.power += randint(-3,3)
                else:
                    self.attributes.power += randint(-5,2)

                if self.attributes.speed >= 95:
                    self.attributes.speed += randint(-5,0)
                elif self.attributes.speed <= 70:
                    self.attributes.speed += randint(-3,3)
                else:
                    self.attributes.speed += randint(-5,2)

                if self.attributes.agility >= 95:
                    self.attributes.agility += randint(-5,0)
                elif self.attributes.agility <= 70:
                    self.attributes.agility += randint(-3,3)
                else:
                    self.attributes.agility += randint(-5,2)

            else:
                if self.attributes.power >= 95:
                    self.attributes.power += randint(-10,0)
                elif self.attributes.power <= 70:
                    self.attributes.power += randint(-5,2)
                else:
                    self.attributes.power += randint(-7,1)

                if self.attributes.speed >= 95:
                    self.attributes.speed += randint(-10,0)
                elif self.attributes.speed <= 70:
                    self.attributes.speed += randint(-5,2)
                else:
                    self.attributes.speed += randint(-7,1)  

                if self.attributes.agility >= 95:
                    self.attributes.agility += randint(-10,0)
                elif self.attributes.agility <= 70:
                    self.attributes.agility += randint(-5,2)
                else:
                    self.attributes.agility += randint(-7,1)

        if self.attributes.power > self.attributes.potentialPower:
            self.attributes.power = self.attributes.potentialPower
        if self.attributes.power < 60:
            self.attributes.power = 60
        if self.attributes.speed > self.attributes.potentialSpeed:
            self.attributes.speed = self.attributes.potentialSpeed
        if self.attributes.speed < 60:
            self.attributes.speed = 60
        if self.attributes.agility > self.attributes.potentialAgility:
            self.attributes.agility = self.attributes.potentialAgility 
        if self.attributes.agility < 60:
            self.attributes.agility = 60

        self.updateRating()
        
class PlayerWR(Player):
    def __init__(self, seed = None):
        super().__init__()
        self.position = Position.WR
        self.isOpen = False
        self.attributes.getPlayerAttributes(self.position, seed)

        self.updateRating()

        self.attributes.potentialSpeed = self.attributes.speed + randint(0,30)
        self.attributes.potentialHands = self.attributes.hands + randint(0,30)
        self.attributes.potentialAgility = self.attributes.agility + randint(0,30)
        if self.attributes.potentialSpeed > 100:
            self.attributes.potentialSpeed = 100
        if self.attributes.potentialHands > 100:
            self.attributes.potentialHands = 100
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
        self.playerRating = self.attributes.overallRating


    def offseasonTraining(self):
        self.attributes.attitude += randint(-5,5)
        if self.attributes.attitude > 100:
            self.attributes.attitude = 100
        if self.attributes.attitude < 0:
            self.attributes.attitude = 0
        self.attributes.discipline += randint(-5,5)
        if self.attributes.discipline > 100:
            self.attributes.discipline = 100
        self.attributes.calculateIntangibles()

        if self.seasonsPlayed > self.attributes.longevity:
            if self.attributes.xFactor > 90:
                if self.attributes.hands >= 95:
                    self.attributes.hands += randint(0,2)
                elif self.attributes.hands <= 70:
                    self.attributes.hands += randint(0,10)
                else:
                    self.attributes.hands += randint(0,5)

                if self.attributes.speed >= 95:
                    self.attributes.speed += randint(0,3)
                elif self.attributes.speed <= 70:
                    self.attributes.speed += randint(0,10)
                else:
                    self.attributes.speed += randint(0,5)  

                if self.attributes.agility >= 95:
                    self.attributes.agility += randint(0,2)
                elif self.attributes.agility <= 70:
                    self.attributes.agility += randint(0,10)
                else:
                    self.attributes.agility += randint(0,5)

            elif self.attributes.xFactor > 75:
                if self.attributes.hands >= 95:
                    self.attributes.hands += randint(-1,2)
                elif self.attributes.hands <= 70:
                    self.attributes.hands += randint(0,7)
                else:
                    self.attributes.hands += randint(-2,3)

                if self.attributes.speed >= 95:
                    self.attributes.speed += randint(-1,2)
                elif self.attributes.speed <= 70:
                    self.attributes.speed += randint(0,7)
                else:
                    self.attributes.speed += randint(-2,3)

                if self.attributes.agility >= 95:
                    self.attributes.agility += randint(-1,2)
                elif self.attributes.agility <= 70:
                    self.attributes.agility += randint(0,7)
                else:
                    self.attributes.agility += randint(-2,3)

            else:
                if self.attributes.hands >= 95:
                    self.attributes.hands += randint(-5,1)
                elif self.attributes.hands <= 70:
                    self.attributes.hands += randint(0,5)
                else:
                    self.attributes.hands += randint(-5,5)

                if self.attributes.speed >= 95:
                    self.attributes.speed += randint(-5,1)
                elif self.attributes.speed <= 70:
                    self.attributes.speed += randint(0,5)
                else:
                    self.attributes.speed += randint(-5,5)  

                if self.attributes.agility >= 95:
                    self.attributes.agility += randint(-5,1)
                elif self.attributes.agility <= 70:
                    self.attributes.agility += randint(0,5)
                else:
                    self.attributes.agility += randint(-5,5)
        else:
            if self.attributes.xFactor > 90:
                if self.attributes.hands >= 95:
                    self.attributes.hands += randint(-3,0)
                elif self.attributes.hands <= 70:
                    self.attributes.hands += randint(-1,5)
                else:
                    self.attributes.hands += randint(-3,3)

                if self.attributes.speed >= 95:
                    self.attributes.speed += randint(-3,0)
                elif self.attributes.speed <= 70:
                    self.attributes.speed += randint(-1,5)
                else:
                    self.attributes.speed += randint(-3,3)  

                if self.attributes.agility >= 95:
                    self.attributes.agility += randint(-3,0)
                elif self.attributes.agility <= 70:
                    self.attributes.agility += randint(-1,5)
                else:
                    self.attributes.agility += randint(-3,3)

            elif self.attributes.xFactor > 75:
                if self.attributes.hands >= 95:
                    self.attributes.hands += randint(-5,0)
                elif self.attributes.hands <= 70:
                    self.attributes.hands += randint(-3,3)
                else:
                    self.attributes.hands += randint(-5,2)

                if self.attributes.speed >= 95:
                    self.attributes.speed += randint(-5,0)
                elif self.attributes.speed <= 70:
                    self.attributes.speed += randint(-3,3)
                else:
                    self.attributes.speed += randint(-5,2)

                if self.attributes.agility >= 95:
                    self.attributes.agility += randint(-5,0)
                elif self.attributes.agility <= 70:
                    self.attributes.agility += randint(-3,3)
                else:
                    self.attributes.agility += randint(-5,2)

            else:
                if self.attributes.hands >= 95:
                    self.attributes.hands += randint(-10,0)
                elif self.attributes.hands <= 70:
                    self.attributes.hands += randint(-5,2)
                else:
                    self.attributes.hands += randint(-7,1)

                if self.attributes.speed >= 95:
                    self.attributes.speed += randint(-10,0)
                elif self.attributes.speed <= 70:
                    self.attributes.speed += randint(-5,2)
                else:
                    self.attributes.speed += randint(-7,1)  

                if self.attributes.agility >= 95:
                    self.attributes.agility += randint(-10,0)
                elif self.attributes.agility <= 70:
                    self.attributes.agility += randint(-5,2)
                else:
                    self.attributes.agility += randint(-7,1)

        if self.attributes.hands > self.attributes.potentialHands:
            self.attributes.hands = self.attributes.potentialHands
        if self.attributes.hands < 60:
            self.attributes.hands = 60
        if self.attributes.speed > self.attributes.potentialSpeed:
            self.attributes.speed = self.attributes.potentialSpeed
        if self.attributes.speed < 60:
            self.attributes.speed = 60
        if self.attributes.agility > self.attributes.potentialAgility:
            self.attributes.agility = self.attributes.potentialAgility 
        if self.attributes.agility < 60:
            self.attributes.agility = 60

        if self.attributes.hands > self.attributes.potentialHands:
            self.attributes.hands = self.attributes.potentialHands
        if self.attributes.hands < 60:
            self.attributes.hands = 60
        if self.attributes.speed > self.attributes.potentialSpeed:
            self.attributes.speed = self.attributes.potentialSpeed
        if self.attributes.speed < 60:
            self.attributes.speed = 60
        if self.attributes.agility > self.attributes.potentialAgility:
            self.attributes.agility = self.attributes.potentialAgility 
        if self.attributes.agility < 60:
            self.attributes.agility = 60

        self.updateRating()

class PlayerTE(Player):
    def __init__(self, seed = None):
        super().__init__()
        self.position = Position.TE
        self.isOpen = False
        self.attributes.getPlayerAttributes(self.position, seed)

        self.updateRating()

        self.attributes.potentialHands = self.attributes.hands + randint(0,30)
        self.attributes.potentialPower = self.attributes.power + randint(0,30)
        self.attributes.potentialAgility = self.attributes.agility + randint(0,30)
        if self.attributes.potentialHands > 100:
            self.attributes.potentialHands = 100
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


    def offseasonTraining(self):
        self.attributes.attitude += randint(-5,5)
        if self.attributes.attitude > 100:
            self.attributes.attitude = 100
        if self.attributes.attitude < 0:
            self.attributes.attitude = 0
        self.attributes.discipline += randint(-5,5)
        if self.attributes.discipline > 100:
            self.attributes.discipline = 100
        self.attributes.calculateIntangibles()

        if self.seasonsPlayed > self.attributes.longevity:
            if self.attributes.xFactor > 90:
                if self.attributes.power >= 95:
                    self.attributes.power += randint(0,2)
                elif self.attributes.power <= 70:
                    self.attributes.power += randint(0,10)
                else:
                    self.attributes.power += randint(0,5)

                if self.attributes.hands >= 95:
                    self.attributes.hands += randint(0,3)
                elif self.attributes.hands <= 70:
                    self.attributes.hands += randint(0,10)
                else:
                    self.attributes.hands += randint(0,5)  

                if self.attributes.agility >= 95:
                    self.attributes.agility += randint(0,2)
                elif self.attributes.agility <= 70:
                    self.attributes.agility += randint(0,10)
                else:
                    self.attributes.agility += randint(0,5)

            elif self.attributes.xFactor > 75:
                if self.attributes.power >= 95:
                    self.attributes.power += randint(-1,2)
                elif self.attributes.power <= 70:
                    self.attributes.power += randint(0,7)
                else:
                    self.attributes.power += randint(-2,3)

                if self.attributes.hands >= 95:
                    self.attributes.hands += randint(-1,2)
                elif self.attributes.hands <= 70:
                    self.attributes.hands += randint(0,7)
                else:
                    self.attributes.hands += randint(-2,3)

                if self.attributes.agility >= 95:
                    self.attributes.agility += randint(-1,2)
                elif self.attributes.agility <= 70:
                    self.attributes.agility += randint(0,7)
                else:
                    self.attributes.agility += randint(-2,3)

            else:
                if self.attributes.power >= 95:
                    self.attributes.power += randint(-5,1)
                elif self.attributes.power <= 70:
                    self.attributes.power += randint(0,5)
                else:
                    self.attributes.power += randint(-5,5)

                if self.attributes.hands >= 95:
                    self.attributes.hands += randint(-5,1)
                elif self.attributes.hands <= 70:
                    self.attributes.hands += randint(0,5)
                else:
                    self.attributes.hands += randint(-5,5)  

                if self.attributes.agility >= 95:
                    self.attributes.agility += randint(-5,1)
                elif self.attributes.agility <= 70:
                    self.attributes.agility += randint(0,5)
                else:
                    self.attributes.agility += randint(-5,5)
        else:
            if self.attributes.xFactor > 90:
                if self.attributes.power >= 95:
                    self.attributes.power += randint(-3,0)
                elif self.attributes.power <= 70:
                    self.attributes.power += randint(-1,5)
                else:
                    self.attributes.power += randint(-3,3)

                if self.attributes.hands >= 95:
                    self.attributes.hands += randint(-3,0)
                elif self.attributes.hands <= 70:
                    self.attributes.hands += randint(-1,5)
                else:
                    self.attributes.hands += randint(-3,3)  

                if self.attributes.agility >= 95:
                    self.attributes.agility += randint(-3,0)
                elif self.attributes.agility <= 70:
                    self.attributes.agility += randint(-1,5)
                else:
                    self.attributes.agility += randint(-3,3)

            elif self.attributes.xFactor > 75:
                if self.attributes.power >= 95:
                    self.attributes.power += randint(-5,0)
                elif self.attributes.power <= 70:
                    self.attributes.power += randint(-3,3)
                else:
                    self.attributes.power += randint(-5,2)

                if self.attributes.hands >= 95:
                    self.attributes.hands += randint(-5,0)
                elif self.attributes.hands <= 70:
                    self.attributes.hands += randint(-3,3)
                else:
                    self.attributes.hands += randint(-5,2)

                if self.attributes.agility >= 95:
                    self.attributes.agility += randint(-5,0)
                elif self.attributes.agility <= 70:
                    self.attributes.agility += randint(-3,3)
                else:
                    self.attributes.agility += randint(-5,2)

            else:
                if self.attributes.power >= 95:
                    self.attributes.power += randint(-10,0)
                elif self.attributes.power <= 70:
                    self.attributes.power += randint(-5,2)
                else:
                    self.attributes.power += randint(-7,1)

                if self.attributes.hands >= 95:
                    self.attributes.hands += randint(-10,0)
                elif self.attributes.hands <= 70:
                    self.attributes.hands += randint(-5,2)
                else:
                    self.attributes.hands += randint(-7,1)  

                if self.attributes.agility >= 95:
                    self.attributes.agility += randint(-10,0)
                elif self.attributes.agility <= 70:
                    self.attributes.agility += randint(-5,2)
                else:
                    self.attributes.agility += randint(-7,1)

        if self.attributes.power > self.attributes.potentialPower:
            self.attributes.power = self.attributes.potentialPower
        if self.attributes.power < 60:
            self.attributes.power = 60
        if self.attributes.hands > self.attributes.potentialHands:
            self.attributes.hands = self.attributes.potentialHands
        if self.attributes.hands < 60:
            self.attributes.hands = 60
        if self.attributes.agility > self.attributes.potentialAgility:
            self.attributes.agility = self.attributes.potentialAgility 
        if self.attributes.agility < 60:
            self.attributes.agility = 60

        self.updateRating()

class PlayerK(Player):
    def __init__(self, seed = None):
        super().__init__()
        self.position = Position.K
        self.maxFgDistance = 0
        self.attributes.getPlayerAttributes(self.position, seed)

        self.updateRating()

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
        self.playerRating = self.attributes.overallRating
        self.maxFgDistance = round(70*(self.attributes.legStrength/100))


    def offseasonTraining(self):
        self.attributes.attitude += randint(-5,5)
        if self.attributes.attitude > 100:
            self.attributes.attitude = 100
        if self.attributes.attitude < 0:
            self.attributes.attitude = 0
        self.attributes.discipline += randint(-5,5)
        if self.attributes.discipline > 100:
            self.attributes.discipline = 100
        self.attributes.calculateIntangibles()

        if self.seasonsPlayed < self.attributes.longevity:
            if self.attributes.xFactor > 90:
                if self.attributes.legStrength >= 95:
                    self.attributes.legStrength += randint(0,2)
                elif self.attributes.legStrength <= 70:
                    self.attributes.legStrength += randint(0,10)
                else:
                    self.attributes.legStrength += randint(0,5)
                

                if self.attributes.accuracy >= 95:
                    self.attributes.accuracy += randint(0,3)
                elif self.attributes.accuracy <= 70:
                    self.attributes.accuracy += randint(0,10)
                else:
                    self.attributes.accuracy += randint(0,5)  

            elif self.attributes.xFactor > 75:
                if self.attributes.legStrength >= 95:
                    self.attributes.legStrength += randint(-1,2)
                elif self.attributes.legStrength <= 70:
                    self.attributes.legStrength += randint(0,7)
                else:
                    self.attributes.legStrength += randint(-2,3)

                if self.attributes.accuracy >= 95:
                    self.attributes.accuracy += randint(-1,2)
                elif self.attributes.accuracy <= 70:
                    self.attributes.accuracy += randint(0,7)
                else:
                    self.attributes.accuracy += randint(-2,3)

            else:
                if self.attributes.legStrength >= 95:
                    self.attributes.legStrength += randint(-5,1)
                elif self.attributes.legStrength <= 70:
                    self.attributes.legStrength += randint(0,5)
                else:
                    self.attributes.legStrength += randint(-5,5)

                if self.attributes.accuracy >= 95:
                    self.attributes.accuracy += randint(-5,1)
                elif self.attributes.accuracy <= 70:
                    self.attributes.accuracy += randint(0,5)
                else:
                    self.attributes.accuracy += randint(-5,5)  
        else:
            if self.attributes.xFactor > 90:
                if self.attributes.legStrength >= 95:
                    self.attributes.legStrength += randint(-3,0)
                elif self.attributes.legStrength <= 70:
                    self.attributes.legStrength += randint(-1,5)
                else:
                    self.attributes.legStrength += randint(-3,3)

                if self.attributes.accuracy >= 95:
                    self.attributes.accuracy += randint(-3,0)
                elif self.attributes.accuracy <= 70:
                    self.attributes.accuracy += randint(-1,5)
                else:
                    self.attributes.accuracy += randint(-3,3)  

            elif self.attributes.xFactor > 75:
                if self.attributes.legStrength >= 95:
                    self.attributes.legStrength += randint(-5,0)
                elif self.attributes.legStrength <= 70:
                    self.attributes.legStrength += randint(-3,3)
                else:
                    self.attributes.legStrength += randint(-5,2)

                if self.attributes.accuracy >= 95:
                    self.attributes.accuracy += randint(-5,0)
                elif self.attributes.accuracy <= 70:
                    self.attributes.accuracy += randint(-3,3)
                else:
                    self.attributes.accuracy += randint(-5,2)

            else:
                if self.attributes.legStrength >= 95:
                    self.attributes.legStrength += randint(-10,0)
                elif self.attributes.legStrength <= 70:
                    self.attributes.legStrength += randint(-5,2)
                else:
                    self.attributes.legStrength += randint(-7,1)

                if self.attributes.accuracy >= 95:
                    self.attributes.accuracy += randint(-10,0)
                elif self.attributes.accuracy <= 70:
                    self.attributes.accuracy += randint(-5,2)
                else:
                    self.attributes.accuracy += randint(-7,1) 

        if self.attributes.legStrength > self.attributes.potentialLegStrength:
            self.attributes.legStrength = self.attributes.potentialLegStrength
        if self.attributes.legStrength < 60:
            self.attributes.legStrength = 60
        if self.attributes.accuracy > self.attributes.potentialAccuracy:
            self.attributes.accuracy = self.attributes.potentialAccuracy
        if self.attributes.accuracy < 60:
            self.attributes.accuracy = 60

        self.updateRating()