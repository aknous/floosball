import enum
from random import randint
import floosball_methods as FloosMethods

class Position(enum.Enum):
    QB = 1
    RB = 2
    WR = 3
    TE = 4
    K = 5

class PlayerTier(enum.Enum):
    SuperStar = 5
    Elite = 4
    AboveAverage = 3
    Average = 2
    BelowAverage = 1

qbStatsDict = {'passAtt': 0, 'passComp': 0, 'passCompPerc': 0, 'tds': 0, 'ints': 0, 'passYards': 0, 'ypc': 0, 'totalYards': 0}
rbStatsDict = {'carries': 0, 'receptions': 0, 'passTargets': 0, 'rcvPerc': 0, 'rcvYards': 0, 'runYards': 0, 'ypc': 0, 'tds': 0, 'fumblesLost': 0, 'ypr': 0, 'totalYards': 0}
wrStatsDict = {'receptions': 0, 'passTargets': 0, 'rcvPerc': 0, 'rcvYards': 0, 'ypr': 0, 'tds': 0, 'totalYards': 0}
kStatsDict = {'fgAtt': 0, 'fgs': 0, 'fgPerc': 0}

class Player:
    def __init__(self):
        self.position = None
        self.name = ''
        self.id = 0
        self.team = None
        self.previousTeam = None
        self.attributes = PlayerAttributes()
        self.gameAttributes: PlayerAttributes = None
        self.playerTier = PlayerTier
        self.seasonsPlayed = 0
        self.term = 0
        self.seasonPerformanceRating = 0

        self.gameStatsDict = None
        self.seasonStatsDict = None
        self.careerStatsDict = None

    def updateInGameRating(self):
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
    def __init__(self):
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
        self.discipline = FloosMethods.getStat(1,100,1)
        self.focus = 0
        self.instinct = 0
        self.creativity = 0
        self.luck = FloosMethods.getStat(1,100,1)
        self.playMakingAbility = 0
        self.getPlayerAttributes()
        self.calculateIntangibles()

        
    def calculateIntangibles(self):
        self.playMakingAbility = round(((self.instinct*1.2) + (self.luck*.7) + (self.focus*.8) + (self.creativity*1.2))/3.9)

    def getPlayerAttributes(self):
        x = randint(1, 100)
        skillValList = []
        if x >= 95:
            # SuperStar array
           for y in range(10):
                if y <= 8:
                    skillValList.append(randint(90, 100))
                else:
                    skillValList.append(randint(80, 89))
        elif x >= 85 and x < 95:
            # Elite array
           for y in range(10):
                if y <= 7:
                    skillValList.append(randint(90, 100))
                else:
                    skillValList.append(randint(80, 89))
        elif x >= 50 and x < 85:
            # AboveAverage array
           for y in range(10):
                if y <= 2:
                    skillValList.append(randint(90, 100))
                elif y > 2 and y < 7:
                    skillValList.append(randint(80, 89))
                else:
                    skillValList.append(randint(70, 79))
        elif x >= 10 and x < 50:
            # Average array
           for y in range(10):
                if y < 5:
                    skillValList.append(randint(80, 89))
                else:
                    skillValList.append(randint(70, 79))
        else:
            # BelowAverage array
           for y in range(10):
                if y < 3:
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


class PlayerQB(Player):
    def __init__(self):
        super().__init__()
        self.position = Position.QB
        self.updateRating()

        self.gameStatsDict = qbStatsDict.copy()
        self.seasonStatsDict = qbStatsDict.copy()
        self.careerStatsDict = qbStatsDict.copy()

    def updateInGameRating(self):
        self.gameAttributes.calculateIntangibles()
        self.gameAttributes.skillRating = round(((self.gameAttributes.armStrength*1.2) + (self.gameAttributes.accuracy*1.3) + (self.gameAttributes.agility*.5))/3)
        self.gameAttributes.overallRating = round((((self.gameAttributes.skillRating*1.2) + (self.gameAttributes.playMakingAbility*.8))/2) * ((self.gameAttributes.confidence+self.gameAttributes.determination)/2))
        if self.gameAttributes.overallRating > 100:
            self.gameAttributes.overallRating = 100

    def updateRating(self):
        self.attributes.calculateIntangibles()
        self.attributes.skillRating = round(((self.attributes.armStrength*1.2) + (self.attributes.accuracy*1.3) + (self.attributes.agility*.5))/3)
        self.attributes.overallRating = round(((self.attributes.skillRating*1.2) + (self.attributes.playMakingAbility*.8))/2)

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

class PlayerRB(Player):
    def __init__(self):
        super().__init__()
        self.position = Position.RB

        self.updateRating()

        self.gameStatsDict = rbStatsDict.copy()
        self.seasonStatsDict = rbStatsDict.copy()
        self.careerStatsDict = rbStatsDict.copy()

    def updateInGameRating(self):
        self.gameAttributes.calculateIntangibles()
        self.gameAttributes.skillRating = round(((self.gameAttributes.speed*.7) + (self.gameAttributes.power*1.3) + (self.gameAttributes.agility*1))/3)
        self.gameAttributes.overallRating = round((((self.gameAttributes.skillRating*1.2) + (self.gameAttributes.playMakingAbility*.8))/2) * ((self.gameAttributes.confidence+self.gameAttributes.determination)/2))
        if self.gameAttributes.overallRating > 100:
            self.gameAttributes.overallRating = 100

    def updateRating(self):
        self.attributes.calculateIntangibles()
        self.attributes.skillRating = round(((self.attributes.speed*.7) + (self.attributes.power*1.3) + (self.attributes.agility*1))/3)
        self.attributes.overallRating = round(((self.attributes.skillRating*1.2) + (self.attributes.playMakingAbility*.8))/2)

    def offseasonTraining(self):
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
        self.attributes.hands += randint(-2, 2)
        if self.attributes.hands > 100:
            self.attributes.hands = 100
        elif self.attributes.hands < 70:
            self.attributes.hands = 70
        
class PlayerWR(Player):
    def __init__(self):
        super().__init__()
        self.position = Position.WR

        self.updateRating()

        self.gameStatsDict = wrStatsDict.copy()
        self.seasonStatsDict = wrStatsDict.copy()
        self.careerStatsDict = wrStatsDict.copy()

    def updateInGameRating(self):
        self.gameAttributes.calculateIntangibles()
        self.gameAttributes.skillRating = round(((self.gameAttributes.speed*.7) + (self.gameAttributes.hands*1.5) + (self.gameAttributes.agility*.8))/3)
        self.gameAttributes.overallRating = round((((self.gameAttributes.skillRating*1.2) + (self.gameAttributes.playMakingAbility*.8))/2) * ((self.gameAttributes.confidence+self.gameAttributes.determination)/2))
        if self.gameAttributes.overallRating > 100:
            self.gameAttributes.overallRating = 100

    def updateRating(self):
        self.attributes.calculateIntangibles()
        self.attributes.skillRating = round(((self.attributes.speed*.7) + (self.attributes.hands*1.5) + (self.attributes.agility*.8))/3)
        self.attributes.overallRating = round(((self.attributes.skillRating*1.2) + (self.attributes.playMakingAbility*.8))/2)

    def offseasonTraining(self):
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
        self.attributes.hands += randint(-5, 5)
        if self.attributes.hands > 100:
            self.attributes.hands = 100
        elif self.attributes.hands < 70:
            self.attributes.hands = 70

class PlayerTE(Player):
    def __init__(self):
        super().__init__()
        self.position = Position.TE

        self.updateRating()

        self.gameStatsDict = wrStatsDict.copy()
        self.seasonStatsDict = wrStatsDict.copy()
        self.careerStatsDict = wrStatsDict.copy()
    
    def updateInGameRating(self):
        self.gameAttributes.calculateIntangibles()
        self.gameAttributes.skillRating = round(((self.gameAttributes.power*1.3) + (self.gameAttributes.hands*1) + (self.gameAttributes.agility*.7))/3)
        self.gameAttributes.overallRating = round((((self.gameAttributes.skillRating*1.2) + (self.gameAttributes.playMakingAbility*.8))/2) * ((self.gameAttributes.confidence+self.gameAttributes.determination)/2))
        if self.gameAttributes.overallRating > 100:
            self.gameAttributes.overallRating = 100

    def updateRating(self):
        self.attributes.calculateIntangibles()
        self.attributes.skillRating = round(((self.attributes.power*1.3) + (self.attributes.hands*1) + (self.attributes.agility*.7))/3)
        self.attributes.overallRating = round(((self.attributes.skillRating*1.2) + (self.attributes.playMakingAbility*.8))/2)

    def offseasonTraining(self):
        self.attributes.agility += randint(-5, 5)
        if self.attributes.agility > 100:
            self.attributes.agility = 100
        elif self.attributes.agility < 70:
            self.attributes.agility = 70
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
        self.attributes.speed += randint(-2, 2)
        if self.attributes.speed > 100:
            self.attributes.speed = 100
        elif self.attributes.speed < 70:
            self.attributes.speed = 70

class PlayerK(Player):
    def __init__(self):
        super().__init__()
        self.position = Position.K
        self.updateRating()

        self.gameStatsDict = kStatsDict.copy()
        self.seasonStatsDict = kStatsDict.copy()
        self.careerStatsDict = kStatsDict.copy()
    
    def updateInGameRating(self):
        self.gameAttributes.calculateIntangibles()
        self.gameAttributes.skillRating = round((self.gameAttributes.legStrength + self.gameAttributes.accuracy)/2)
        self.gameAttributes.overallRating = round((((self.gameAttributes.skillRating*1.2) + (self.gameAttributes.playMakingAbility*.8))/2) * ((self.gameAttributes.confidence+self.gameAttributes.determination)/2))
        if self.gameAttributes.overallRating > 100:
            self.gameAttributes.overallRating = 100

    def updateRating(self):
        self.attributes.calculateIntangibles()
        self.attributes.skillRating = round((self.attributes.legStrength + self.attributes.accuracy)/2)
        self.attributes.overallRating = round(((self.attributes.skillRating*1.2) + (self.attributes.playMakingAbility*.8))/2)

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

    