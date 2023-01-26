import enum
from os import stat
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
    DB = 6
    LB = 7
    DL = 8
    DE = 9

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
    Retired = 'Retired'

playerStatsDict =   {   
                        'team': None,
                        'season': 0,
                        'gp': 0,
                        'passing': {
                            'att': 0, 
                            'comp': 0, 
                            'compPerc': 0, 
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
                            'longest': 0
                        },
                        'defense': {
                            'tackles': 0,
                            'sacks': 0,
                            'fumRec': 0,
                            'ints': 0,
                            'passTargets': 0, 
                            'passDisruptions': 0,
                            'passDisPerc': 0
                        }
                    }

qbStatsDict = {
                'passAtt': 0, 
                'passComp': 0, 
                'passCompPerc': 0, 
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
                'fg45+': 0,
                'longest': 0
            }

class Player:
    def __init__(self, seed = None):
        self.position = None
        self.name = ''
        self.id = 0
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
        self.attributes.confidence = round((self.attributes.confidence + self.gameAttributes.confidence)/2)
        self.attributes.determination = round((self.attributes.determination + self.gameAttributes.determination)/2)
        self.gamesPlayed += 1
        self.seasonStatsDict['gp'] = self.gamesPlayed
        if isinstance(self.team,Team):
            if self.team.seasonTeamStats['winPerc'] > .5:
                self.attributes.attitude += randint (-1,2)
                self.attributes.confidence += randint(0,10)/1000
                self.attributes.determination += randint(0,10)/1000
            else:
                self.attributes.attitude += randint (-2,1)
                self.attributes.confidence += randint(-10,5)/1000
                self.attributes.determination += randint(-5,10)/1000
        
        self.updateRating()

    def updateInGameRating(self):
        pass

    def updateRating(self):
        pass

    def updateInGameDetermination(self, value):
        self.gameAttributes.determination = round(self.gameAttributes.determination + value, 2)
        self.updateInGameRating()

    def updateInGameConfidence(self, value):
        self.gameAttributes.confidence = round(self.gameAttributes.confidence + value, 2)
        self.updateInGameRating()

    def offseasonTraining(self):
        pass


class PlayerAttributes:
    def __init__(self, seed = None):
        self.overallRating = 0
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
        
        #intangibles
        self.confidence = 1
        self.determination = 1
        self.discipline = 0
        self.focus = 0
        self.instinct = 0
        self.creativity = 0
        self.longevity = randint(3,8)
        self.luck = FloosMethods.getStat(1,100,1)
        self.attitude = 0
        self.playMakingAbility = 0
        self.xFactor = 0
        self.getPlayerAttributes(seed)
        self.calculateIntangibles()

        
    def calculateIntangibles(self):
        self.playMakingAbility = round((self.instinct+self.creativity)/2)
        self.xFactor = round((((self.attitude*1) + (self.luck*.8) + (self.focus*1) + (self.discipline*1.2))/4) * ((self.confidence+self.determination)/2))

    def getPlayerAttributes(self, seed = None):
        x = 0
        if seed is None:
            x = randint(1, 100)
        else:
            x = seed

        skillValList = []
        if x >= 95:
            # Tier S array
           for y in range(12):
                if y <= 10:
                    skillValList.append(randint(90, 100))
                else:
                    skillValList.append(randint(85, 89))
        elif x >= 85 and x < 95:
            # Tier A array
           for y in range(12):
                if y <= 8:
                    skillValList.append(randint(90, 100))
                else:
                    skillValList.append(randint(85, 89))
        elif x >= 50 and x < 85:
            # Tier B array
           for y in range(12):
                if y <= 4:
                    skillValList.append(randint(90, 100))
                elif y > 4 and y < 9:
                    skillValList.append(randint(85, 89))
                else:
                    skillValList.append(randint(75, 79))
        elif x >= 10 and x < 50:
            # Tier C array
           for y in range(12):
                if y < 6:
                    skillValList.append(randint(80, 89))
                else:
                    skillValList.append(randint(60, 79))
        else:
            # Tier D array
           for y in range(12):
                if y < 4:
                    skillValList.append(randint(80, 89))
                else:
                    skillValList.append(randint(60, 79))
        
        self.speed = skillValList.pop(randint(0, len(skillValList)) - 1)
        self.hands = skillValList.pop(randint(0, len(skillValList)) - 1)
        self.agility = skillValList.pop(randint(0, len(skillValList)) - 1)
        self.power = skillValList.pop(randint(0, len(skillValList)) - 1)
        self.armStrength = skillValList.pop(randint(0, len(skillValList)) - 1)
        self.accuracy = skillValList.pop(randint(0, len(skillValList)) - 1)
        self.legStrength = skillValList.pop(randint(0, len(skillValList)) - 1)
        self.instinct = skillValList.pop(randint(0, len(skillValList)) - 1)
        self.focus = skillValList.pop(randint(0, len(skillValList)) - 1)
        self.creativity = skillValList.pop(randint(0, len(skillValList)) - 1)
        self.attitude = skillValList.pop(randint(0, len(skillValList)) - 1)
        self.discipline = skillValList.pop(randint(0, len(skillValList)) - 1)

    def changeStat(self, value):
        if value >= 95:
            value += randint(-10, 0)
        elif value <= 75:
            value += randint(0, 10)
        else:
            value += randint(5, 5)


class PlayerQB(Player):
    def __init__(self, seed = None):
        super().__init__(seed)
        self.position = Position.QB
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
        self.gameAttributes.skillRating = round(((self.gameAttributes.armStrength*1.2) + (self.gameAttributes.accuracy*1.3) + (self.gameAttributes.agility*.5))/3)
        self.gameAttributes.overallRating = round(((self.gameAttributes.skillRating*2) + (self.gameAttributes.playMakingAbility*1.5) + (self.gameAttributes.xFactor*1.5))/5)
        if self.gameAttributes.overallRating > 100:
            self.gameAttributes.overallRating = 100

    def updateRating(self):
        self.attributes.calculateIntangibles()
        self.attributes.skillRating = round(((self.attributes.armStrength*1.2) + (self.attributes.accuracy*1.3) + (self.attributes.agility*.5))/3)
        self.attributes.overallRating = round(((self.attributes.skillRating*2) + (self.attributes.playMakingAbility*1.5) + (self.attributes.xFactor*1.5))/5)
        self.playerRating = self.attributes.overallRating


    def offseasonTraining(self):
        self.attributes.attitude += randint(-5,5)
        if self.attributes.attitude > 100:
            self.attributes.attitude = 100
        self.attributes.luck += randint(-5,5)
        if self.attributes.luck > 100:
            self.attributes.luck = 100
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
        super().__init__(seed)
        self.position = Position.RB
        self.isOpen = False

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
        self.gameAttributes.skillRating = round(((self.gameAttributes.speed*.7) + (self.gameAttributes.power*1.3) + (self.gameAttributes.agility*1))/3)
        self.gameAttributes.overallRating = round(((self.gameAttributes.skillRating*2) + (self.gameAttributes.playMakingAbility*1.5) + (self.gameAttributes.xFactor*1.5))/5)
        if self.gameAttributes.overallRating > 100:
            self.gameAttributes.overallRating = 100

    def updateRating(self):
        self.attributes.calculateIntangibles()
        self.attributes.skillRating = round(((self.attributes.speed*.7) + (self.attributes.power*1.3) + (self.attributes.agility*1))/3)
        self.attributes.overallRating = round(((self.attributes.skillRating*2) + (self.attributes.playMakingAbility*1.5) + (self.attributes.xFactor*1.5))/5)
        self.playerRating = self.attributes.overallRating


    def offseasonTraining(self):
        self.attributes.attitude += randint(-5,5)
        if self.attributes.attitude > 100:
            self.attributes.attitude = 100
        self.attributes.luck += randint(-5,5)
        if self.attributes.luck > 100:
            self.attributes.luck = 100
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
        super().__init__(seed)
        self.position = Position.WR
        self.isOpen = False

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
        self.gameAttributes.skillRating = round(((self.gameAttributes.speed*.7) + (self.gameAttributes.hands*1.5) + (self.gameAttributes.agility*.8))/3)
        self.gameAttributes.overallRating = round(((self.gameAttributes.skillRating*2) + (self.gameAttributes.playMakingAbility*1.5) + (self.gameAttributes.xFactor*1.5))/5)
        if self.gameAttributes.overallRating > 100:
            self.gameAttributes.overallRating = 100

    def updateRating(self):
        self.attributes.calculateIntangibles()
        self.attributes.skillRating = round(((self.attributes.speed*.7) + (self.attributes.hands*1.5) + (self.attributes.agility*.8))/3)
        self.attributes.overallRating = round(((self.attributes.skillRating*2) + (self.attributes.playMakingAbility*1.5) + (self.attributes.xFactor*1.5))/5)
        self.playerRating = self.attributes.overallRating


    def offseasonTraining(self):
        self.attributes.attitude += randint(-5,5)
        if self.attributes.attitude > 100:
            self.attributes.attitude = 100
        self.attributes.luck += randint(-5,5)
        if self.attributes.luck > 100:
            self.attributes.luck = 100
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
        super().__init__(seed)
        self.position = Position.TE
        self.isOpen = False

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
        self.gameAttributes.skillRating = round(((self.gameAttributes.power*1.3) + (self.gameAttributes.hands*1) + (self.gameAttributes.agility*.7))/3)
        self.gameAttributes.overallRating = round(((self.gameAttributes.skillRating*2) + (self.gameAttributes.playMakingAbility*1.5) + (self.gameAttributes.xFactor*1.5))/5)
        if self.gameAttributes.overallRating > 100:
            self.gameAttributes.overallRating = 100

    def updateRating(self):
        self.attributes.calculateIntangibles()
        self.attributes.skillRating = round(((self.attributes.power*1.3) + (self.attributes.hands*1) + (self.attributes.agility*.7))/3)
        self.attributes.overallRating = round(((self.attributes.skillRating*2) + (self.attributes.playMakingAbility*1.5) + (self.attributes.xFactor*1.5))/5)
        self.playerRating = self.attributes.overallRating


    def offseasonTraining(self):
        self.attributes.attitude += randint(-5,5)
        if self.attributes.attitude > 100:
            self.attributes.attitude = 100
        self.attributes.luck += randint(-5,5)
        if self.attributes.luck > 100:
            self.attributes.luck = 100
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
        super().__init__(seed)
        self.position = Position.K
        self.maxFgDistance = 0
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
        self.gameAttributes.skillRating = round((self.gameAttributes.legStrength + self.gameAttributes.accuracy)/2)
        self.gameAttributes.overallRating = round(((self.gameAttributes.skillRating*2) + (self.gameAttributes.playMakingAbility*1.5) + (self.gameAttributes.xFactor*1.5))/5)
        if self.gameAttributes.overallRating > 100:
            self.gameAttributes.overallRating = 100

    def updateRating(self):
        self.attributes.calculateIntangibles()
        self.attributes.skillRating = round((self.attributes.legStrength + self.attributes.accuracy)/2)
        self.attributes.overallRating = round(((self.attributes.skillRating*2) + (self.attributes.playMakingAbility*1.5) + (self.attributes.xFactor*1.5))/5)
        self.playerRating = self.attributes.overallRating
        self.maxFgDistance = round(70*(self.attributes.legStrength/100))


    def offseasonTraining(self):
        self.attributes.attitude += randint(-5,5)
        if self.attributes.attitude > 100:
            self.attributes.attitude = 100
        self.attributes.luck += randint(-5,5)
        if self.attributes.luck > 100:
            self.attributes.luck = 100
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

class PlayerDB(Player):
    def __init__(self, seed = None):
        super().__init__(seed)
        self.position = Position.DB

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
        self.attributes.potentialSkillRating = round(((self.attributes.potentialHands*.7) + (self.attributes.potentialSpeed*1) + (self.attributes.potentialAgility*1.3))/3)

    def updateInGameRating(self):
        self.gameAttributes.calculateIntangibles()
        self.gameAttributes.skillRating = round(((self.gameAttributes.speed*1) + (self.gameAttributes.hands*.7) + (self.gameAttributes.agility*1.3))/3)
        self.gameAttributes.overallRating = round(((self.gameAttributes.skillRating*2) + (self.gameAttributes.playMakingAbility*1.5) + (self.gameAttributes.xFactor*1.5))/5)
        if self.gameAttributes.overallRating > 100:
            self.gameAttributes.overallRating = 100

    def updateRating(self):
        self.attributes.calculateIntangibles()
        self.attributes.skillRating = round(((self.attributes.speed*1) + (self.attributes.hands*.7) + (self.attributes.agility*1.3))/3)
        self.attributes.overallRating = round(((self.attributes.skillRating*2) + (self.attributes.playMakingAbility*1.5) + (self.attributes.xFactor*1.5))/5)
        self.playerRating = self.attributes.overallRating


    def offseasonTraining(self):
        self.attributes.attitude += randint(-5,5)
        if self.attributes.attitude > 100:
            self.attributes.attitude = 100
        self.attributes.luck += randint(-5,5)
        if self.attributes.luck > 100:
            self.attributes.luck = 100
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

        if self.attributes.hands > self.attributes.potentialPower:
            self.attributes.hands = self.attributes.potentialPower
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



class PlayerDefBasic(Player):
    def __init__(self, pos: Position, seed = None):
        super().__init__(seed)
        self.position = pos

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
        self.attributes.potentialSkillRating = round(((self.attributes.potentialPower*.7) + (self.attributes.potentialSpeed*1) + (self.attributes.potentialAgility*1.3))/3)

    def updateInGameRating(self):
        self.gameAttributes.calculateIntangibles()
        self.gameAttributes.skillRating = round(((self.gameAttributes.speed*.5) + (self.gameAttributes.power*1.2) + (self.gameAttributes.agility*1.3))/3)
        self.gameAttributes.overallRating = round(((self.gameAttributes.skillRating*2) + (self.gameAttributes.playMakingAbility*1.5) + (self.gameAttributes.xFactor*1.5))/5)
        if self.gameAttributes.overallRating > 100:
            self.gameAttributes.overallRating = 100

    def updateRating(self):
        self.attributes.calculateIntangibles()
        self.attributes.skillRating = round(((self.attributes.speed*.5) + (self.attributes.power*1.2) + (self.attributes.agility*1.3))/3)
        self.attributes.overallRating = round(((self.attributes.skillRating*2) + (self.attributes.playMakingAbility*1.5) + (self.attributes.xFactor*1.5))/5)
        self.playerRating = self.attributes.overallRating

    def offseasonTraining(self):
        self.attributes.attitude += randint(-5,5)
        if self.attributes.attitude > 100:
            self.attributes.attitude = 100
        self.attributes.luck += randint(-5,5)
        if self.attributes.luck > 100:
            self.attributes.luck = 100
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