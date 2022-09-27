import enum
from os import stat
from random import randint
import floosball_methods as FloosMethods
from floosball_team import Team

class Position(enum.Enum):
    QB = 1
    RB = 2
    WR = 3
    TE = 4
    K = 5

class PlayerTier(enum.Enum):
    SuperStar = 'Super Star'
    Elite = 'Elite'
    AboveAverage = 'Above Average'
    Average = 'Average'
    BelowAverage = 'Below Average'

qbStatsDict = {'passAtt': 0, 'passComp': 0, 'passCompPerc': 0, 'tds': 0, 'ints': 0, 'passYards': 0, 'ypc': 0, 'totalYards': 0}
rbStatsDict = {'carries': 0, 'receptions': 0, 'passTargets': 0, 'rcvPerc': 0, 'rcvYards': 0, 'runYards': 0, 'ypc': 0, 'runTds': 0, 'rcvTds': 0, 'tds': 0, 'fumblesLost': 0, 'ypr': 0, 'totalYards': 0}
wrStatsDict = {'receptions': 0, 'passTargets': 0, 'rcvPerc': 0, 'rcvYards': 0, 'ypr': 0, 'tds': 0, 'totalYards': 0}
kStatsDict = {'fgAtt': 0, 'fgs': 0, 'fgPerc': 0}

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
        self.seasonPerformanceRating = 0
        self.freeAgentYears = 0

        self.gameStatsDict = None
        self.seasonStatsDict = None
        self.careerStatsDict = None

    def postgameChanges(self):
        self.attributes.confidence = round((self.attributes.confidence + self.gameAttributes.confidence)/2)
        self.attributes.determination = round((self.attributes.determination + self.gameAttributes.determination)/2)
        self.gamesPlayed += 1
        if isinstance(self.team,Team):
            if self.team.seasonTeamStats['winPerc'] > .5:
                self.attributes.attitude += randint (-1,2)
                self.attributes.confidence += randint(0,10)/1000
                self.attributes.determination += randint(0,10)/1000
            else:
                self.attributes.attitude += randint (-2,1)
                self.attributes.confidence += randint(-10,5)/1000
                self.attributes.determination += randint(-5,10)/1000
        else:
            print('In postgameChanges, player team is {}'.format(self.team))
        
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
        self.attributes.armStrength += randint(-5, 5)
        if self.attributes.armStrength > 100:
            self.attributes.armStrength = 100
        elif self.attributes.armStrength < 70:
            self.attributes.armStrength = 70
        self.attributes.accuracy += randint(-5, 5)
        if self.attributes.accuracy > 100:
            self.attributes.accuracy = 100
        elif self.attributes.accuracy < 70:
            self.attributes.accuracy = 70
        self.attributes.agility += randint(-5, 5)
        if self.attributes.agility > 100:
            self.attributes.agility = 100
        elif self.attributes.agility < 70:
            self.attributes.agility = 70
        self.attributes.speed += randint(-5, 5)
        if self.attributes.speed > 100:
            self.attributes.speed = 100
        elif self.attributes.speed < 70:
            self.attributes.speed = 70
        self.attributes.power += randint(-5, 5)
        if self.attributes.power > 100:
            self.attributes.power = 100
        elif self.attributes.power < 70:
            self.attributes.power = 70
        self.attributes.hands += randint(-5, 5)
        if self.attributes.hands > 100:
            self.attributes.hands = 100
        elif self.attributes.hands < 70:
            self.attributes.hands = 70
        self.attributes.legStrength += randint(-5, 5)
        if self.attributes.legStrength > 100:
            self.attributes.legStrength = 100
        elif self.attributes.legStrength < 70:
            self.attributes.legStrength = 70



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
        
        #intangibles
        self.confidence = 1
        self.determination = 1
        self.discipline = 0
        self.focus = 0
        self.instinct = 0
        self.creativity = 0
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
            # SuperStar array
           for y in range(12):
                if y <= 10:
                    skillValList.append(randint(90, 100))
                else:
                    skillValList.append(randint(80, 89))
        elif x >= 85 and x < 95:
            # Elite array
           for y in range(12):
                if y <= 8:
                    skillValList.append(randint(90, 100))
                else:
                    skillValList.append(randint(80, 89))
        elif x >= 50 and x < 85:
            # AboveAverage array
           for y in range(12):
                if y <= 4:
                    skillValList.append(randint(90, 100))
                elif y > 4 and y < 9:
                    skillValList.append(randint(80, 89))
                else:
                    skillValList.append(randint(70, 79))
        elif x >= 10 and x < 50:
            # Average array
           for y in range(12):
                if y < 6:
                    skillValList.append(randint(80, 89))
                else:
                    skillValList.append(randint(70, 79))
        else:
            # BelowAverage array
           for y in range(12):
                if y < 4:
                    skillValList.append(randint(80, 89))
                else:
                    skillValList.append(randint(70, 79))
        
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

        self.gameStatsDict = qbStatsDict.copy()
        self.seasonStatsDict = qbStatsDict.copy()
        self.careerStatsDict = qbStatsDict.copy()

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

    def offseasonTraining(self):
        self.attributes.attitude += randint(-5,5)
        self.attributes.luck += randint(-5,5)
        self.attributes.discipline += randint(-5,5)
        self.attributes.calculateIntangibles()

        if self.attributes.xFactor > 90:
            if self.attributes.armStrength >= 95:
                self.attributes.armStrength += randint(-3,0)
            elif self.attributes.armStrength <= 75:
                self.attributes.armStrength += randint(0,10)
            else:
                self.attributes.armStrength += randint(0,5)
            if self.attributes.armStrength > 100:
                self.attributes.armStrength = 100

            if self.attributes.accuracy >= 95:
                self.attributes.accuracy += randint(-3,0)
            elif self.attributes.accuracy <= 75:
                self.attributes.accuracy += randint(0,10)
            else:
                self.attributes.accuracy += randint(0,5)
            if self.attributes.accuracy > 100:
                self.attributes.accuracy = 100  

            if self.attributes.agility >= 95:
                self.attributes.agility += randint(-3,0)
            elif self.attributes.agility <= 75:
                self.attributes.agility += randint(0,10)
            else:
                self.attributes.agility += randint(0,5)
            if self.attributes.agility > 100:
                self.attributes.agility = 100 

        elif self.attributes.xFactor > 75:
            if self.attributes.armStrength >= 95:
                self.attributes.armStrength += randint(-5,0)
            elif self.attributes.armStrength <= 75:
                self.attributes.armStrength += randint(0,7)
            else:
                self.attributes.armStrength += randint(-3,3)
            if self.attributes.armStrength > 100:
                self.attributes.armStrength = 100

            if self.attributes.accuracy >= 95:
                self.attributes.accuracy += randint(-5,0)
            elif self.attributes.accuracy <= 75:
                self.attributes.accuracy += randint(0,7)
            else:
                self.attributes.accuracy += randint(-3,3)
            if self.attributes.accuracy > 100:
                self.attributes.accuracy = 100  

            if self.attributes.agility >= 95:
                self.attributes.agility += randint(-5,0)
            elif self.attributes.agility <= 75:
                self.attributes.agility += randint(0,7)
            else:
                self.attributes.agility += randint(-3,3)
            if self.attributes.agility > 100:
                self.attributes.agility = 100 

        else:
            if self.attributes.armStrength >= 95:
                self.attributes.armStrength += randint(-10,0)
            elif self.attributes.armStrength <= 75:
                self.attributes.armStrength += randint(0,5)
            else:
                self.attributes.armStrength += randint(-5,5)
            if self.attributes.armStrength > 100:
                self.attributes.armStrength = 100

            if self.attributes.accuracy >= 95:
                self.attributes.accuracy += randint(-10,0)
            elif self.attributes.accuracy <= 75:
                self.attributes.accuracy += randint(0,5)
            else:
                self.attributes.accuracy += randint(-5,5)
            if self.attributes.accuracy > 100:
                self.attributes.accuracy = 100  

            if self.attributes.agility >= 95:
                self.attributes.agility += randint(-10,0)
            elif self.attributes.agility <= 75:
                self.attributes.agility += randint(0,5)
            else:
                self.attributes.agility += randint(-5,5)
            if self.attributes.agility > 100:
                self.attributes.agility = 100 

        self.updateRating()

class PlayerRB(Player):
    def __init__(self, seed = None):
        super().__init__(seed)
        self.position = Position.RB

        self.updateRating()

        self.gameStatsDict = rbStatsDict.copy()
        self.seasonStatsDict = rbStatsDict.copy()
        self.careerStatsDict = rbStatsDict.copy()

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

    def offseasonTraining(self):
        self.attributes.attitude += randint(-5,5)
        self.attributes.luck += randint(-5,5)
        self.attributes.discipline += randint(-5,5)
        self.attributes.calculateIntangibles()

        if self.attributes.xFactor > 90:
            if self.attributes.speed >= 95:
                self.attributes.speed += randint(-3,0)
            elif self.attributes.speed <= 75:
                self.attributes.speed += randint(0,10)
            else:
                self.attributes.speed += randint(0,5)
            if self.attributes.speed > 100:
                self.attributes.speed = 100

            if self.attributes.hands >= 95:
                self.attributes.hands += randint(-3,0)
            elif self.attributes.hands <= 75:
                self.attributes.hands += randint(0,10)
            else:
                self.attributes.hands += randint(0,5)
            if self.attributes.hands > 100:
                self.attributes.hands = 100  

            if self.attributes.agility >= 95:
                self.attributes.agility += randint(-3,0)
            elif self.attributes.agility <= 75:
                self.attributes.agility += randint(0,10)
            else:
                self.attributes.agility += randint(0,5)
            if self.attributes.agility > 100:
                self.attributes.agility = 100 

        elif self.attributes.xFactor > 75:
            if self.attributes.speed >= 95:
                self.attributes.speed += randint(-5,0)
            elif self.attributes.speed <= 75:
                self.attributes.speed += randint(0,7)
            else:
                self.attributes.speed += randint(-3,3)
            if self.attributes.speed > 100:
                self.attributes.speed = 100

            if self.attributes.hands >= 95:
                self.attributes.hands += randint(-5,0)
            elif self.attributes.hands <= 75:
                self.attributes.hands += randint(0,7)
            else:
                self.attributes.hands += randint(-3,3)
            if self.attributes.hands > 100:
                self.attributes.hands = 100  

            if self.attributes.agility >= 95:
                self.attributes.agility += randint(-5,0)
            elif self.attributes.agility <= 75:
                self.attributes.agility += randint(0,7)
            else:
                self.attributes.agility += randint(-3,3)
            if self.attributes.agility > 100:
                self.attributes.agility = 100 

        else:
            if self.attributes.speed >= 95:
                self.attributes.speed += randint(-10,0)
            elif self.attributes.speed <= 75:
                self.attributes.speed += randint(0,5)
            else:
                self.attributes.speed += randint(-5,5)
            if self.attributes.speed > 100:
                self.attributes.speed = 100

            if self.attributes.hands >= 95:
                self.attributes.hands += randint(-10,0)
            elif self.attributes.hands <= 75:
                self.attributes.hands += randint(0,5)
            else:
                self.attributes.hands += randint(-5,5)
            if self.attributes.hands > 100:
                self.attributes.hands = 100  

            if self.attributes.agility >= 95:
                self.attributes.agility += randint(-10,0)
            elif self.attributes.agility <= 75:
                self.attributes.agility += randint(0,5)
            else:
                self.attributes.agility += randint(-5,5)
            if self.attributes.agility > 100:
                self.attributes.agility = 100 

        self.updateRating()
        
class PlayerWR(Player):
    def __init__(self, seed = None):
        super().__init__(seed)
        self.position = Position.WR

        self.updateRating()

        self.gameStatsDict = wrStatsDict.copy()
        self.seasonStatsDict = wrStatsDict.copy()
        self.careerStatsDict = wrStatsDict.copy()

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

    def offseasonTraining(self):
        self.attributes.attitude += randint(-5,5)
        self.attributes.luck += randint(-5,5)
        self.attributes.discipline += randint(-5,5)
        self.attributes.calculateIntangibles()

        if self.attributes.xFactor > 90:
            if self.attributes.speed >= 95:
                self.attributes.speed += randint(-3,0)
            elif self.attributes.speed <= 75:
                self.attributes.speed += randint(0,10)
            else:
                self.attributes.speed += randint(0,5)
            if self.attributes.speed > 100:
                self.attributes.speed = 100

            if self.attributes.hands >= 95:
                self.attributes.hands += randint(-3,0)
            elif self.attributes.hands <= 75:
                self.attributes.hands += randint(0,10)
            else:
                self.attributes.hands += randint(0,5)
            if self.attributes.hands > 100:
                self.attributes.hands = 100  

            if self.attributes.agility >= 95:
                self.attributes.agility += randint(-3,0)
            elif self.attributes.agility <= 75:
                self.attributes.agility += randint(0,10)
            else:
                self.attributes.agility += randint(0,5)
            if self.attributes.agility > 100:
                self.attributes.agility = 100 

        elif self.attributes.xFactor > 75:
            if self.attributes.speed >= 95:
                self.attributes.speed += randint(-5,0)
            elif self.attributes.speed <= 75:
                self.attributes.speed += randint(0,7)
            else:
                self.attributes.speed += randint(-3,3)
            if self.attributes.speed > 100:
                self.attributes.speed = 100

            if self.attributes.hands >= 95:
                self.attributes.hands += randint(-5,0)
            elif self.attributes.hands <= 75:
                self.attributes.hands += randint(0,7)
            else:
                self.attributes.hands += randint(-3,3)
            if self.attributes.hands > 100:
                self.attributes.hands = 100  

            if self.attributes.agility >= 95:
                self.attributes.agility += randint(-5,0)
            elif self.attributes.agility <= 75:
                self.attributes.agility += randint(0,7)
            else:
                self.attributes.agility += randint(-3,3)
            if self.attributes.agility > 100:
                self.attributes.agility = 100 

        else:
            if self.attributes.speed >= 95:
                self.attributes.speed += randint(-10,0)
            elif self.attributes.speed <= 75:
                self.attributes.speed += randint(0,5)
            else:
                self.attributes.speed += randint(-5,5)
            if self.attributes.speed > 100:
                self.attributes.speed = 100

            if self.attributes.hands >= 95:
                self.attributes.hands += randint(-10,0)
            elif self.attributes.hands <= 75:
                self.attributes.hands += randint(0,5)
            else:
                self.attributes.hands += randint(-5,5)
            if self.attributes.hands > 100:
                self.attributes.hands = 100  

            if self.attributes.agility >= 95:
                self.attributes.agility += randint(-10,0)
            elif self.attributes.agility <= 75:
                self.attributes.agility += randint(0,5)
            else:
                self.attributes.agility += randint(-5,5)
            if self.attributes.agility > 100:
                self.attributes.agility = 100 

        self.updateRating()

class PlayerTE(Player):
    def __init__(self, seed = None):
        super().__init__(seed)
        self.position = Position.TE

        self.updateRating()

        self.gameStatsDict = wrStatsDict.copy()
        self.seasonStatsDict = wrStatsDict.copy()
        self.careerStatsDict = wrStatsDict.copy()
    
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

    def offseasonTraining(self):
        self.attributes.attitude += randint(-5,5)
        self.attributes.luck += randint(-5,5)
        self.attributes.discipline += randint(-5,5)
        self.attributes.calculateIntangibles()

        if self.attributes.xFactor > 90:
            if self.attributes.power >= 95:
                self.attributes.power += randint(-3,0)
            elif self.attributes.power <= 75:
                self.attributes.power += randint(0,10)
            else:
                self.attributes.power += randint(0,5)
            if self.attributes.power > 100:
                self.attributes.power = 100

            if self.attributes.hands >= 95:
                self.attributes.hands += randint(-3,0)
            elif self.attributes.hands <= 75:
                self.attributes.hands += randint(0,10)
            else:
                self.attributes.hands += randint(0,5)
            if self.attributes.hands > 100:
                self.attributes.hands = 100  

            if self.attributes.agility >= 95:
                self.attributes.agility += randint(-3,0)
            elif self.attributes.agility <= 75:
                self.attributes.agility += randint(0,10)
            else:
                self.attributes.agility += randint(0,5)
            if self.attributes.agility > 100:
                self.attributes.agility = 100 

        elif self.attributes.xFactor > 75:
            if self.attributes.power >= 95:
                self.attributes.power += randint(-5,0)
            elif self.attributes.power <= 75:
                self.attributes.power += randint(0,7)
            else:
                self.attributes.power += randint(-3,3)
            if self.attributes.power > 100:
                self.attributes.power = 100

            if self.attributes.hands >= 95:
                self.attributes.hands += randint(-5,0)
            elif self.attributes.hands <= 75:
                self.attributes.hands += randint(0,7)
            else:
                self.attributes.hands += randint(-3,3)
            if self.attributes.hands > 100:
                self.attributes.hands = 100  

            if self.attributes.agility >= 95:
                self.attributes.agility += randint(-5,0)
            elif self.attributes.agility <= 75:
                self.attributes.agility += randint(0,7)
            else:
                self.attributes.agility += randint(-3,3)
            if self.attributes.agility > 100:
                self.attributes.agility = 100 

        else:
            if self.attributes.power >= 95:
                self.attributes.power += randint(-10,0)
            elif self.attributes.power <= 75:
                self.attributes.power += randint(0,5)
            else:
                self.attributes.power += randint(-5,5)
            if self.attributes.power > 100:
                self.attributes.power = 100

            if self.attributes.hands >= 95:
                self.attributes.hands += randint(-10,0)
            elif self.attributes.hands <= 75:
                self.attributes.hands += randint(0,5)
            else:
                self.attributes.hands += randint(-5,5)
            if self.attributes.hands > 100:
                self.attributes.hands = 100  

            if self.attributes.agility >= 95:
                self.attributes.agility += randint(-10,0)
            elif self.attributes.agility <= 75:
                self.attributes.agility += randint(0,5)
            else:
                self.attributes.agility += randint(-5,5)
            if self.attributes.agility > 100:
                self.attributes.agility = 100 

        self.updateRating()

class PlayerK(Player):
    def __init__(self, seed = None):
        super().__init__(seed)
        self.position = Position.K
        self.updateRating()

        self.gameStatsDict = kStatsDict.copy()
        self.seasonStatsDict = kStatsDict.copy()
        self.careerStatsDict = kStatsDict.copy()
    
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

    def offseasonTraining(self):
        self.attributes.accuracy += randint(-5, 5)
        if self.attributes.accuracy > 100:
            self.attributes.accuracy = 100
        elif self.attributes.accuracy < 70:
            self.attributes.accuracy = 70
        self.attributes.legStrength += randint(-5, 5)
        if self.attributes.legStrength > 100:
            self.attributes.legStrength = 100
        elif self.attributes.legStrength < 70:
            self.attributes.legStrength = 70

        self.attributes.attitude += randint(-5,5)
        self.attributes.luck += randint(-5,5)
        self.attributes.discipline += randint(-5,5)
        self.attributes.calculateIntangibles()

        if self.attributes.xFactor > 90:
            if self.attributes.legStrength >= 95:
                self.attributes.legStrength += randint(-3,0)
            elif self.attributes.legStrength <= 75:
                self.attributes.legStrength += randint(0,10)
            else:
                self.attributes.legStrength += randint(0,5)
            if self.attributes.legStrength > 100:
                self.attributes.legStrength = 100

            if self.attributes.accuracy >= 95:
                self.attributes.accuracy += randint(-3,0)
            elif self.attributes.accuracy <= 75:
                self.attributes.accuracy += randint(0,10)
            else:
                self.attributes.accuracy += randint(0,5)
            if self.attributes.accuracy > 100:
                self.attributes.accuracy = 100   

        elif self.attributes.xFactor > 75:
            if self.attributes.legStrength >= 95:
                self.attributes.legStrength += randint(-5,0)
            elif self.attributes.legStrength <= 75:
                self.attributes.legStrength += randint(0,7)
            else:
                self.attributes.legStrength += randint(-3,3)
            if self.attributes.legStrength > 100:
                self.attributes.legStrength = 100

            if self.attributes.accuracy >= 95:
                self.attributes.accuracy += randint(-5,0)
            elif self.attributes.accuracy <= 75:
                self.attributes.accuracy += randint(0,7)
            else:
                self.attributes.accuracy += randint(-3,3)
            if self.attributes.accuracy > 100:
                self.attributes.accuracy = 100  

        else:
            if self.attributes.legStrength >= 95:
                self.attributes.legStrength += randint(-10,0)
            elif self.attributes.legStrength <= 75:
                self.attributes.legStrength += randint(0,5)
            else:
                self.attributes.legStrength += randint(-5,5)
            if self.attributes.legStrength > 100:
                self.attributes.legStrength = 100

            if self.attributes.accuracy >= 95:
                self.attributes.accuracy += randint(-10,0)
            elif self.attributes.accuracy <= 75:
                self.attributes.accuracy += randint(0,5)
            else:
                self.attributes.accuracy += randint(-5,5)
            if self.attributes.accuracy > 100:
                self.attributes.accuracy = 100  

        self.updateRating()

    