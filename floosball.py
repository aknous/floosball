import enum
import  json
import os
from random import randint
import shutil
import statistics
import copy

class PassType(enum.Enum):
    short = 1
    medium = 2
    long = 3

class Position(enum.Enum):
    QB = 1
    RB = 2
    WR = 3
    TE = 4
    K = 5

class PlayType(enum.Enum):
    Run = 1
    Pass = 2
    FieldGoal = 3
    Punt = 4
 
config = None
totalSeasons = 0
seasonsPlayed = 0
playerList = []
freeAgentList = []
teamList = []
divisionList = []   
scheduleList = []
scheduleScheme = [
    ('1112','1314','2122','2324','3132','3334','4142','4344'),
    ('1311','1412','2321','2422','3331','3432','4341','4442'),
    ('1114','1213','2124','2223','3134','3233','4144','4243'),

    ('1121','1222','1323','1424','3141','3242','3343','3444'),
    ('2112','2211','2314','2413','4132','4231','4334','4433'),
    ('1123','1224','1321','1422','3143','3244','3341','3442'),
    ('2114','2213','2312','2411','4134','4233','4332','4431'),

    ('1131','1232','1333','1434','2141','2242','2343','2444'),
    ('3112','3211','3314','3413','4122','4221','4324','4423'),
    ('1133','1234','1331','1432','2143','2244','2341','2442'),
    ('3114','3213','3312','3411','4124','4223','4322','4421'),

    ('1141','1242','1343','1444','2131','2232','2333','2434'),
    ('4112','4211','4314','4413','3122','3221','3324','3423'),
    ('1143','1244','1341','1442','2133','2234','2331','2432'),
    ('4114','4213','4312','4411','3124','3223','3322','3421'),

    ('1211','1413','2221','2423','3231','3433','4241','4443'),
    ('1113','1214','2123','2224','3133','3234','4143','4244'),
    ('1411','1312','2421','2322','3431','3332','4441','4342')]


def _prepare_for_serialization(obj):
    serialized_dict = dict()
    if isinstance(obj, dict):
        for k, v in obj.items():
            if v != 0:
                if isinstance(v, list):
                    tempDict = {}
                    y = 0
                    for item in v:
                        y += 1
                        tempDict[y] = _prepare_for_serialization(item)
                    serialized_dict[k] = tempDict
                elif isinstance(v, dict):
                    tempDict = {}
                    for a, b in v.items():
                        if isinstance(b, dict):
                            tempDict2 = {}
                            for c, d in b.items():
                                if isinstance(d, dict):
                                    tempDict3 = {}
                                    for e, f in d.items():
                                        if isinstance(f, list):
                                            x = 0
                                            for item in f:
                                                x += 1
                                                tempDict3[x] = _prepare_for_serialization(item)
                                        elif isinstance(d, Player):
                                            tempDict3[e] = f.name
                                        elif isinstance(b, Team):
                                            tempDict3[e] = f.name
                                        else:
                                            tempDict3[e] = f.name if isinstance(f, Position) else f
                                    tempDict2[c] = tempDict3
                                if isinstance(d, list):
                                    z = 0
                                    for item in d:
                                        z += 1
                                        tempDict2[z] = _prepare_for_serialization(item)
                                elif isinstance(d, Player):
                                    tempDict2[c] = d.name
                                elif isinstance(d, Team):
                                    tempDict2[c] = d.name
                                elif isinstance(d, PlayerAttributes):
                                    tempDict2[c] = _prepare_for_serialization(d)
                                else:
                                    tempDict2[c] = d.name if isinstance(d, Position) else d
                            tempDict[a] = tempDict2
                        elif isinstance(b, list):
                            y = 0
                            for item in b:
                                y += 1
                                tempDict[y] = _prepare_for_serialization(item)
                        elif isinstance(b, Player):
                            tempDict[a] = b.name
                        elif isinstance(b, Team):
                            tempDict[a] = b.name
                        elif isinstance(b, PlayerAttributes):
                            tempDict[a] = _prepare_for_serialization(b)
                        else:
                            tempDict[a] = b.name if isinstance(b, Position) else b
                    serialized_dict[k] = tempDict
                else: 
                    if isinstance(v, Position):
                        serialized_dict[k] = v.name 
                    elif isinstance(v, PlayType):
                        serialized_dict[k] = v.name
                    elif isinstance(v, Team):
                        serialized_dict[k] = v.name
                    elif isinstance(v, PlayerAttributes):
                        serialized_dict[k] = _prepare_for_serialization(v)
                    else:
                        serialized_dict[k] = v
    else:
        for k, v in obj.__dict__.items():
            if v != 0:
                if isinstance(v, list):
                    tempDict = {}
                    y = 0
                    for item in v:
                        y += 1
                        tempDict[y] = _prepare_for_serialization(item)
                    serialized_dict[k] = tempDict
                elif isinstance(v, dict):
                    tempDict = {}
                    for a, b in v.items():
                        if isinstance(b, Player):
                            tempDict[a] = _prepare_for_serialization(b)
                        else:
                            tempDict[a] = b.name if isinstance(b, Position) else b
                    serialized_dict[k] = tempDict
                else: 
                    if isinstance(v, Position):
                        serialized_dict[k] = v.name 
                    elif isinstance(v, PlayType):
                        serialized_dict[k] = v.name
                    elif isinstance(v, Team):
                        serialized_dict[k] = v.name
                    elif isinstance(v, PlayerAttributes):
                        serialized_dict[k] = _prepare_for_serialization(v)
                    else:
                        serialized_dict[k] = v
    return serialized_dict                    

def getStat(min, max, weight):
    x = randint(min,max)
    if weight == 1:
        if x >= 95:
            return randint(95, 100)
        elif x < 95 and x >= 75:
            return randint(85, 94)
        elif x < 75 and x >= 25:
            return randint(75, 84)
        else:
            return randint(65, 74)
    else:
        return x

def getPower(x, y):
    z = 1
    while z < y:
        if (x**z) == y:
            return z
        else:
            z += z
    return 0
    

class Division:
    def __init__(self, name):
        self.name = name
        self.teamList = []

teamStatsDict = {'wins': 0, 'losses': 0, 'winPerc': 0, 'Offense': {'tds': 0, 'passYards': 0, 'runYards': 0, 'totalYards': 0}, 'Defense': {'sacks': 0, 'ints': 0, 'fumRec': 0}}

class Team:
    def __init__(self, name):
        self.name = name
        self.offenseRating = 0
        self.runDefenseRating = 0
        self.passDefenseRating = 0
        self.defenseRating = 0
        self.overallRating = 0
        self.divisionChampionships = 0
        self.leagueChampionships = 0
        self.playoffAppearances = 0

        self.seasonTeamStats = copy.deepcopy(teamStatsDict)
        self.allTimeTeamStats = copy.deepcopy(teamStatsDict)
        self.rosterDict : dict[str, Player] = {'qb': None, 'rb': None, 'wr': None, 'te': None, 'k': None}

    def setupTeam(self):
      
        if self.overallRating == 0:
            count = 0
            rating = 0

            for player in self.rosterDict.values():
                rating += player.attributes.overallRating 
                count += 1
            self.offenseRating = round(rating/count)
            self.runDefenseRating = getStat(1,100,1)
            self.passDefenseRating = getStat(1,100,1)
            self.defenseRating = round(statistics.mean([self.runDefenseRating, self.passDefenseRating]))
            self.overallRating = round(statistics.mean([self.offenseRating, self.runDefenseRating, self.passDefenseRating]))

    def updateRating(self):
        count = 0
        rating = 0
        for player in self.rosterDict.values():
            rating += player.attributes.overallRating 
            count += 1
        self.offenseRating = round(rating/count)
        self.overallRating = round(statistics.mean([self.offenseRating, self.runDefenseRating, self.passDefenseRating]))

    def updateDefense(self):
        self.passDefenseRating += randint(-5, 5)
        if self.passDefenseRating > 100:
            self.passDefenseRating = 100
        elif self.passDefenseRating < 0:
            self.passDefenseRating = 0
        self.runDefenseRating += randint(-5, 5)
        if self.runDefenseRating > 100:
            self.runDefenseRating = 100
        elif self.runDefenseRating < 0:
            self.runDefenseRating = 0

        self.defenseRating = round(statistics.mean([self.runDefenseRating, self.passDefenseRating]))

    def offseasonMoves(self):
        bestFreeAgent = None
        hiSkillDiff = 0

        #for player in freeAgentList:
        for x in range(len(freeAgentList)):
            if x < len(freeAgentList):
                if freeAgentList[x].position.value == 1:
                    if freeAgentList[x].attributes.skillRating > self.rosterDict['qb'].attributes.skillRating:
                        skillDiff =  freeAgentList[x].attributes.skillRating - self.rosterDict['qb'].attributes.skillRating
                        if skillDiff > hiSkillDiff:
                            bestFreeAgent = freeAgentList.pop(x)
                elif freeAgentList[x].position.value == 2:
                    if freeAgentList[x].attributes.skillRating > self.rosterDict['rb'].attributes.skillRating:
                        skillDiff =  freeAgentList[x].attributes.skillRating - self.rosterDict['rb'].attributes.skillRating
                        if skillDiff > hiSkillDiff:
                            bestFreeAgent = freeAgentList.pop(x)
                elif freeAgentList[x].position.value == 3:
                    if freeAgentList[x].attributes.skillRating > self.rosterDict['wr'].attributes.skillRating:
                        skillDiff =  freeAgentList[x].attributes.skillRating - self.rosterDict['wr'].attributes.skillRating
                        if skillDiff > hiSkillDiff:
                            bestFreeAgent = freeAgentList.pop(x)
                elif freeAgentList[x].position.value == 4:
                    if freeAgentList[x].attributes.skillRating > self.rosterDict['te'].attributes.skillRating:
                        skillDiff =  freeAgentList[x].attributes.skillRating - self.rosterDict['te'].attributes.skillRating
                        if skillDiff > hiSkillDiff:
                            bestFreeAgent = freeAgentList.pop(x)
                elif freeAgentList[x].position.value == 5:
                    if freeAgentList[x].attributes.skillRating > self.rosterDict['k'].attributes.skillRating:
                        skillDiff =  freeAgentList[x].attributes.skillRating - self.rosterDict['k'].attributes.skillRating
                        if skillDiff > hiSkillDiff:
                            bestFreeAgent = freeAgentList.pop(x)

        if bestFreeAgent is not None:
            if bestFreeAgent.position.value == 1:
                freeAgentList.append(self.rosterDict['qb'])
                self.rosterDict['qb'].team = 'Free Agent'
                self.rosterDict['qb'] = bestFreeAgent
                self.rosterDict['qb'].team = self
            elif bestFreeAgent.position.value == 2:
                freeAgentList.append(self.rosterDict['rb'])
                self.rosterDict['rb'].team = 'Free Agent'
                self.rosterDict['rb'] = bestFreeAgent
                self.rosterDict['rb'].team = self
            elif bestFreeAgent.position.value == 3:
                freeAgentList.append(self.rosterDict['wr'])
                self.rosterDict['wr'].team = 'Free Agent'
                self.rosterDict['wr'] = bestFreeAgent
                self.rosterDict['wr'].team = self
            elif bestFreeAgent.position.value == 4:
                freeAgentList.append(self.rosterDict['te'])
                self.rosterDict['te'].team = 'Free Agent'
                self.rosterDict['te'] = bestFreeAgent
                self.rosterDict['te'].team = self
            elif bestFreeAgent.position.value == 5:
                freeAgentList.append(self.rosterDict['k'])
                self.rosterDict['k'].team = 'Free Agent'
                self.rosterDict['k'] = bestFreeAgent
                self.rosterDict['k'].team = self



class Player:
    def __init__(self):
        self.position = None
        self.name = ''
        self.team = None
        self.attributes = PlayerAttributes()
        self.seasonsPlayed = 0

    def offseasonTraining(self):
        self.attributes.armStrength += randint(-5, 5)
        if self.attributes.armStrength > 100:
            self.attributes.armStrength = 100
        elif self.attributes.armStrength < 0:
            self.attributes.armStrength = 0
        self.attributes.accuracy += randint(-5, 5)
        if self.attributes.accuracy > 100:
            self.attributes.accuracy = 100
        elif self.attributes.accuracy < 0:
            self.attributes.accuracy = 0
        self.attributes.agility += randint(-5, 5)
        if self.attributes.agility > 100:
            self.attributes.agility = 100
        elif self.attributes.agility < 0:
            self.attributes.agility = 0
        self.attributes.speed += randint(-5, 5)
        if self.attributes.speed > 100:
            self.attributes.speed = 100
        elif self.attributes.speed < 0:
            self.attributes.speed = 0
        self.attributes.power += randint(-5, 5)
        if self.attributes.power > 100:
            self.attributes.power = 100
        elif self.attributes.power < 0:
            self.attributes.power = 0
        self.attributes.hands += randint(-5, 5)
        if self.attributes.hands > 100:
            self.attributes.hands = 100
        elif self.attributes.hands < 0:
            self.attributes.hands = 0
        self.attributes.legStrength += randint(-5, 5)
        if self.attributes.legStrength > 100:
            self.attributes.legStrength = 100
        elif self.attributes.legStrength < 0:
            self.attributes.legStrength = 0
        
        if self.team != 'Free Agent':
            if self.team.seasonTeamStats['winPerc'] > .8:
                self.attributes.attitude += randint(0, 5)
                if self.attributes.attitude > 100:
                    self.attributes.attitude = 100
                elif self.attributes.attitude < 0:
                    self.attributes.attitude = 0
            elif self.team.seasonTeamStats['winPerc'] > .6:
                self.attributes.attitude += randint(0, 3)
                if self.attributes.attitude > 100:
                    self.attributes.attitude = 100
                elif self.attributes.attitude < 0:
                    self.attributes.attitude = 0
                self.attributes.determination += randint(0, 3)
                if self.attributes.determination > 100:
                    self.attributes.determination = 100
                elif self.attributes.determination < 0:
                    self.attributes.determination = 0
            elif self.team.seasonTeamStats['winPerc'] > .4:
                self.attributes.attitude += randint(-1, 3)
                if self.attributes.attitude > 100:
                    self.attributes.attitude = 100
                elif self.attributes.attitude < 0:
                    self.attributes.attitude = 0
                self.attributes.determination += randint(0, 5)
                if self.attributes.determination > 100:
                    self.attributes.determination = 100
                elif self.attributes.determination < 0:
                    self.attributes.determination = 0
            elif self.team.seasonTeamStats['winPerc'] > .2:
                self.attributes.attitude += randint(-3, 1)
                if self.attributes.attitude > 100:
                    self.attributes.attitude = 100
                elif self.attributes.attitude < 0:
                    self.attributes.attitude = 0
                self.attributes.determination += randint(-2, 3)
                if self.attributes.determination > 100:
                    self.attributes.determination = 100
                elif self.attributes.determination < 0:
                    self.attributes.determination = 0
            else:
                self.attributes.attitude += randint(-5, 0)
                if self.attributes.attitude > 100:
                    self.attributes.attitude = 100
                elif self.attributes.attitude < 0:
                    self.attributes.attitude = 0
                self.attributes.determination += randint(-3, 1)
                if self.attributes.determination > 100:
                    self.attributes.determination = 100
                elif self.attributes.determination < 0:
                    self.attributes.determination = 0



class PlayerAttributes:
    def __init__(self):
        self.overallRating = 0
        self.speed = getStat(1,100,1)
        self.hands = getStat(1,100,1)
        self.agility = getStat(1,100,1)
        self.power = getStat(1,100,1)
        self.armStrength = getStat(1,100,1)
        self.accuracy = getStat(1,100,1)
        self.legStrength = getStat(1,100,1)
        self.skillRating = 0

        #intangibles
        self.confidence = getStat(1,100,1)
        self.determination = getStat(1,100,1)
        self.discipline = getStat(1,100,1)
        self.focus = getStat(1,100,1)
        self.instinct = getStat(1,100,1)
        self.creativity = getStat(1,100,1)
        self.luck = getStat(1,100,1)
        self.attitude = getStat(1,100,1)
        self.influence = 0
        self.leadershipRating = 0
        self.playMakingAbility = 0
        self.calculateIntangibles()

        
    def calculateIntangibles(self):
        self.playMakingAbility = round(((self.confidence*1.5) + (self.instinct*1.2) + (self.determination*1) + (self.luck*.7) + (self.focus*.8) + (self.creativity*1.2))/6.4)
        self.influence = round(((self.confidence*1)+(self.determination*1)+(self.attitude*1))/3)
        self.leadershipRating = round(((self.confidence*1) + (self.discipline*.8) + (self.attitude*1) + (self.influence*1.5))/(4.3))


    



qbStatsDict = {'passAtt': 0, 'passComp': 0, 'passCompPerc': 0, 'tds': 0, 'ints': 0, 'passYards': 0, 'ypc': 0, 'totalYards': 0}
rbStatsDict = {'carries': 0, 'receptions': 0, 'passTargets': 0, 'rcvPerc': 0, 'rcvYards': 0, 'runYards': 0, 'ypc': 0, 'tds': 0, 'fumblesLost': 0, 'ypr': 0, 'totalYards': 0}
wrStatsDict = {'receptions': 0, 'passTargets': 0, 'rcvPerc': 0, 'rcvYards': 0, 'ypr': 0, 'tds': 0, 'totalYards': 0}
kStatsDict = {'fgAtt': 0, 'fgs': 0, 'fgPerc': 0}

class PlayerQB(Player):
    def __init__(self):
        super().__init__()
        self.position = Position.QB
        self.updateRating()

        self.gameStatsDict = qbStatsDict.copy()
        self.seasonStatsDict = qbStatsDict.copy()
        self.careerStatsDict = qbStatsDict.copy()

    def updateRating(self):
        if self.attributes.confidence > 100:
            self.attributes.confidence = 100
        self.attributes.calculateIntangibles()
        self.attributes.skillRating = round(((self.attributes.armStrength*1.2) + (self.attributes.accuracy*1.3) + (self.attributes.agility*.5))/3)
        self.attributes.overallRating = round(((self.attributes.skillRating*1.2) + (self.attributes.playMakingAbility*.8))/2)



class PlayerRB(Player):
    def __init__(self):
        super().__init__()
        self.position = Position.RB

        self.updateRating()

        self.gameStatsDict = rbStatsDict.copy()
        self.seasonStatsDict = rbStatsDict.copy()
        self.careerStatsDict = rbStatsDict.copy()

    def updateRating(self):
        if self.attributes.confidence > 100:
            self.attributes.confidence = 100
        self.attributes.calculateIntangibles()
        self.attributes.skillRating = round((self.attributes.speed + self.attributes.power + self.attributes.agility)/3)
        self.attributes.overallRating = round(((self.attributes.skillRating*1.2) + (self.attributes.playMakingAbility*.8))/2)
        

class PlayerWR(Player):
    def __init__(self):
        super().__init__()
        self.position = Position.WR

        self.updateRating()

        self.gameStatsDict = wrStatsDict.copy()
        self.seasonStatsDict = wrStatsDict.copy()
        self.careerStatsDict = wrStatsDict.copy()

    def updateRating(self):
        if self.attributes.confidence > 100:
            self.attributes.confidence = 100
        self.attributes.calculateIntangibles()
        self.attributes.skillRating = round((self.attributes.speed + self.attributes.hands + self.attributes.agility)/3)
        self.attributes.overallRating = round(((self.attributes.skillRating*1.2) + (self.attributes.playMakingAbility*.8))/2)

class PlayerTE(Player):
    def __init__(self):
        super().__init__()
        self.position = Position.TE

        self.updateRating()

        self.gameStatsDict = wrStatsDict.copy()
        self.seasonStatsDict = wrStatsDict.copy()
        self.careerStatsDict = wrStatsDict.copy()

    def updateRating(self):
        if self.attributes.confidence > 100:
            self.attributes.confidence = 100
        self.attributes.calculateIntangibles()
        self.attributes.skillRating = round((self.attributes.power + self.attributes.hands + self.attributes.agility)/3)
        self.attributes.overallRating = round(((self.attributes.skillRating*1.2) + (self.attributes.playMakingAbility*.8))/2)

class PlayerK(Player):
    def __init__(self):
        super().__init__()
        self.position = Position.K
        self.updateRating()

        self.gameStatsDict = kStatsDict.copy()
        self.seasonStatsDict = kStatsDict.copy()
        self.careerStatsDict = kStatsDict.copy()
    
    def updateRating(self):
        if self.attributes.confidence > 100:
            self.attributes.confidence = 100
        self.attributes.calculateIntangibles()
        self.attributes.skillRating = round((self.attributes.legStrength + self.attributes.power + self.attributes.accuracy)/3)
        self.attributes.overallRating = round(((self.attributes.skillRating*1.2) + (self.attributes.playMakingAbility*.8))/2)

playDict = {'offense': None, 'defense': None, 'down': None, 'play': None, 'yardage': None, 'runner': None, 'passer': None, 'receiver': None, 'kicker': None, 'turnover': None, 'score': None}

class Game:
    def __init__(self, homeTeam, awayTeam):
        self.homeTeam = homeTeam
        self.awayTeam = awayTeam
        self.awayScore = 0
        self.homeScore = 0
        self.currentQuarter = 0
        self.down = 0
        self.yardsToFirstDown = 0
        self.yardsToEndzone = 0
        self.yardsToSafety = 0
        self.offensiveTeam = ''
        self.defensiveTeam = ''
        self.totalPossessions = 0
        self.totalPlays = 0
        self.lastPlay = []
        self.winningTeam = ''
        self.losingTeam = ''
        self.gameDict = {}

    def saveGameData(self):
        winningTeamStatsDict = {}
        losingTeamStatsDict = {}
        winningTeamPassYards = 0
        losingTeamPassYards = 0
        winningTeamRushYards = 0
        losingTeamRushYards = 0
        winningTeamTotalYards = 0
        losingTeamTotalYards = 0

        playerTempDict = {}

        for player in self.winningTeam.rosterDict.values():
            if player.position is Position.QB:
                winningTeamPassYards += player.gameStatsDict['passYards']
            elif player.position is Position.RB:
                winningTeamRushYards += player.gameStatsDict['runYards']

            playerDict = playerTempDict.copy()
            playerDict['name'] = player.name
            playerDict['overallRating'] = player.attributes.overallRating
            playerDict['gameStats'] = player.gameStatsDict.copy()

            winningTeamStatsDict[player.position.name] = playerDict

            for k in player.gameStatsDict.keys():
                player.gameStatsDict[k] = 0

        for player in self.losingTeam.rosterDict.values():
            if player.position is Position.QB:
                losingTeamPassYards += player.gameStatsDict['passYards']
            elif player.position is Position.RB:
                losingTeamRushYards += player.gameStatsDict['runYards']

            playerDict = playerTempDict.copy()
            playerDict['name'] = player.name
            playerDict['overallRating'] = player.attributes.overallRating
            playerDict['gameStats'] = player.gameStatsDict.copy()

            losingTeamStatsDict[player.position.name] = playerDict

            for k in player.gameStatsDict.keys():
                player.gameStatsDict[k] = 0

        winningTeamTotalYards = winningTeamPassYards + winningTeamRushYards
        losingTeamTotalYards = losingTeamPassYards + losingTeamRushYards

        winningTeamStatsDict['passYards'] = winningTeamPassYards
        winningTeamStatsDict['rushYards'] = winningTeamRushYards
        winningTeamStatsDict['totalYards'] = winningTeamTotalYards
        winningTeamStatsDict['overallRating'] = self.winningTeam.overallRating
        winningTeamStatsDict['offenseRating'] = self.winningTeam.offenseRating
        winningTeamStatsDict['defenseRating'] = self.winningTeam.defenseRating
        winningTeamStatsDict['runDefenseRating'] = self.winningTeam.runDefenseRating
        winningTeamStatsDict['passDefenseRating'] = self.winningTeam.passDefenseRating

        losingTeamStatsDict['passYards'] = losingTeamPassYards
        losingTeamStatsDict['rushYards'] = losingTeamRushYards
        losingTeamStatsDict['totalYards'] = losingTeamTotalYards
        losingTeamStatsDict['overallRating'] = self.losingTeam.overallRating
        losingTeamStatsDict['offenseRating'] = self.losingTeam.offenseRating
        losingTeamStatsDict['defenseRating'] = self.losingTeam.defenseRating
        losingTeamStatsDict['runDefenseRating'] = self.losingTeam.runDefenseRating
        losingTeamStatsDict['passDefenseRating'] = self.losingTeam.passDefenseRating

        self.gameDict[self.winningTeam.name] = winningTeamStatsDict
        self.gameDict[self.losingTeam.name] = losingTeamStatsDict


    def fieldGoalTry(self, offense):
        kicker = offense.rosterDict['k']
        kicker.gameStatsDict['fgAtt'] += 1
        yardsToFG = self.yardsToEndzone + 10
        x = randint(1,100)
        if yardsToFG <= 20:
            if (kicker.attributes.overallRating + 10) >= x:
                fgSuccess = True
                kicker.gameStatsDict['fgs'] += 1
                kicker.attributes.confidence = round(kicker.attributes.confidence * 1.005)
            else:
                fgSuccess = False
                kicker.attributes.confidence = round(kicker.attributes.confidence * .97)
        elif yardsToFG > 20 and yardsToFG <= 40:
            if (kicker.attributes.overallRating) >= x:
                fgSuccess = True
                kicker.gameStatsDict['fgs'] += 1
                kicker.attributes.confidence = round(kicker.attributes.confidence * 1.007)
            else:
                fgSuccess = False
                kicker.attributes.confidence = round(kicker.attributes.confidence * .98)
        else:
            if (kicker.attributes.overallRating - 15) >= x:
                fgSuccess = True
                kicker.gameStatsDict['fgs'] += 1
                kicker.attributes.confidence = round(kicker.attributes.confidence * 1.01)
            else:
                fgSuccess = False
                kicker.attributes.confidence = round(kicker.attributes.confidence * .99)
        #self.lastPlay.insert(0, PlayType.FieldGoal)
        self.lastPlayDict['play'] = PlayType.FieldGoal.name
        #self.lastPlay.insert(1, kicker)
        self.lastPlayDict['kicker'] = kicker
        #self.lastPlay.insert(2, '')
        #self.lastPlay.insert(3, 0)
        kicker.updateRating()
        return fgSuccess

    def extraPointTry(self, offense):
        kicker = offense.rosterDict['k']
        x = randint(1,100)
        if (kicker.attributes.overallRating + 10) >= x:
            fgSuccess = True
            kicker.attributes.confidence = round(kicker.attributes.confidence * 1.005)
        else:
            fgSuccess = False
            kicker.attributes.confidence = round(kicker.attributes.confidence * .97)
        kicker.updateRating()
        return fgSuccess

    def runPlay(self, offense, defense):
        runner = offense.rosterDict['rb']
        blocker = offense.rosterDict['te']
        yardage = 0
        x = randint(1,100)
        fumbleRoll = randint(1,100)
        fumbleResist = round(((runner.attributes.power*1) + (runner.attributes.luck*.7) + (runner.attributes.discipline*1.3))/3)
        playStrength = ((runner.attributes.overallRating*1.3) + (blocker.attributes.power*.7))/2
        if defense.runDefenseRating >= playStrength:
            if fumbleRoll/fumbleResist < 1.15:
                if x < 20:
                    yardage = randint(-2,0)
                    runner.attributes.confidence = round(runner.attributes.confidence * .99)
                elif x >= 20 and x <= 70:
                    yardage = randint(0,3)
                elif x > 70 and x <= 99:
                    yardage = randint(4,7)
                else:
                    if self.yardsToEndzone < 7:
                        yardage = randint(0, self.yardsToEndzone)
                    else:
                        yardage = randint(7, self.yardsToEndzone)
                    runner.attributes.confidence = round(runner.attributes.confidence * 1.01)
            else:
                #fumble
                yardage = 1004
                runner.gameStatsDict['carries'] += 1
                runner.gameStatsDict['fumblesLost'] += 1
                runner.attributes.confidence = round(runner.attributes.confidence * .98)
                defense.seasonTeamStats['Defense']['fumRec'] += 1
                #self.lastPlay.insert(0, PlayType.Run)
                self.lastPlayDict['play'] = PlayType.Run.name
                #self.lastPlay.insert(1, runner) 
                self.lastPlayDict['runner'] = runner
                self.lastPlayDict['turnover'] = True
                #self.lastPlay.insert(2, '')
                #self.lastPlay.insert(3, yardage)
                return yardage

        else:
            if (fumbleRoll/fumbleResist) < 1.2:
                if x < 50:
                    yardage = randint(0,3)
                elif x >= 50 and x < 85:
                    yardage = randint(4,7)
                elif x >= 85 and x < 90:
                    yardage = randint(8,10)
                    runner.attributes.confidence = round(runner.attributes.confidence * 1.01)
                elif x >= 90 and x <= 95:
                    yardage = randint(11,20)
                else:
                    if self.yardsToEndzone < 20:
                        yardage = randint(0, self.yardsToEndzone)
                    else:
                        yardage = randint(20, self.yardsToEndzone)
                    runner.attributes.confidence = round(runner.attributes.confidence * 1.02)
            else:
                #fumble
                yardage = 1004
                runner.gameStatsDict['carries'] += 1
                runner.gameStatsDict['fumblesLost'] += 1
                runner.attributes.confidence = round(runner.attributes.confidence * .98)
                defense.seasonTeamStats['Defense']['fumRec'] += 1
                #self.lastPlay.insert(0, PlayType.Run)
                self.lastPlayDict['play'] = PlayType.Run.name
                #self.lastPlay.insert(1, runner) 
                self.lastPlayDict['runner'] = runner
                self.lastPlayDict['turnover'] = True
                #self.lastPlay.insert(2, '')
                #self.lastPlay.insert(3, yardage)
                return yardage

        if yardage > self.yardsToEndzone:
            yardage = self.yardsToEndzone

        runner.gameStatsDict['runYards'] += yardage
        runner.gameStatsDict['carries'] += 1
        #self.lastPlay.insert(0, PlayType.Run)
        self.lastPlayDict['play'] = PlayType.Run.name
        #self.lastPlay.insert(1, runner) 
        self.lastPlayDict['runner'] = runner
        #self.lastPlay.insert(3, yardage)
        self.lastPlayDict['yardage'] = yardage
        return yardage

    def passPlay(self, offense, defense, passType):
        passer = offense.rosterDict['qb']
        rb = offense.rosterDict['rb']
        wr = offense.rosterDict['wr']
        te = offense.rosterDict['te']
        receiver = ''
        sackRoll = randint(1,1000)
        sackModifyer = defense.passDefenseRating/passer.attributes.agility

        if sackRoll < round(100 * (sackModifyer)):
            yardage = round(-(randint(0,10) * sackModifyer))
            # print("\n{0} sacked {1} for {2} yard(s)".format(defense.name, passer.name, yardage))
            defense.seasonTeamStats['Defense']['sacks'] += 1
            #self.lastPlay.insert(0, PlayType.Pass)
            self.lastPlayDict['play'] = PlayType.Pass.name
            #self.lastPlay.insert(1, passer) 
            self.lastPlayDict['passer'] = passer
            self.lastPlayDict['yardage'] = yardage
            return yardage
        else:
            passer.gameStatsDict['passAtt'] += 1
            passTarget = randint(1,10)

            if passType.value == 1:
                if passTarget < 3:
                    receiver = rb   
                elif passTarget >= 3 and passTarget < 9:
                    receiver = wr
                else:
                    receiver = te
                accRoll = randint(1,100)
                if accRoll < (passer.attributes.overallRating) - (defense.passDefenseRating/12):
                    dropRoll = round(randint(1,100) + (defense.passDefenseRating/10))
                    if receiver.attributes.overallRating > dropRoll:
                        passYards = randint(0,4)
                        yac = 0
                        x = randint(1,10)
                        if receiver.attributes.overallRating > defense.defenseRating:
                            if x < 2:
                                yac = randint(0,3)
                            elif x >= 2 and x <= 9:
                                yac = randint(4,10)
                            else:
                                if self.yardsToEndzone < 11:
                                    yac = randint(0, self.yardsToEndzone)
                                else:
                                    yac = randint(11, self.yardsToEndzone)
                        else:
                            if x <= 6:
                                yac = randint(0,3)
                            else:
                                yac = randint(4,7)
                            
                        yardage = passYards + yac
                        if yardage > self.yardsToEndzone:
                            yardage = self.yardsToEndzone
                        passer.gameStatsDict['passYards'] += yardage
                        passer.gameStatsDict['passComp'] += 1
                        receiver.gameStatsDict['passTargets'] += 1
                        receiver.gameStatsDict['receptions'] += 1
                        receiver.gameStatsDict['rcvYards'] += yardage
                        passer.attributes.confidence = round(passer.attributes.confidence * 1.005)
                        receiver.attributes.confidence = round(receiver.attributes.confidence * 1.005)
                        #self.lastPlay.insert(0, PlayType.Pass)
                        self.lastPlayDict['play'] = PlayType.Pass.name
                        #self.lastPlay.insert(1, passer) 
                        self.lastPlayDict['passer'] = passer
                        #self.lastPlay.insert(2, receiver)
                        self.lastPlayDict['receiver'] = receiver
                        #self.lastPlay.insert(3, yardage)
                        self.lastPlayDict['yardage'] = yardage

                        return yardage
                    else:
                        # print("\n{0}'s pass to {1} is incomplete".format(passer.name, receiver.name))
                        yardage = 0
                        receiver.gameStatsDict['passTargets'] += 1
                        receiver.attributes.confidence = round(receiver.attributes.confidence * .98)                 
                        #self.lastPlay.insert(0, PlayType.Pass)
                        self.lastPlayDict['play'] = PlayType.Pass.name
                        #self.lastPlay.insert(1, passer) 
                        self.lastPlayDict['passer'] = passer
                        #self.lastPlay.insert(2, receiver)
                        self.lastPlayDict['receiver'] = receiver
                        #self.lastPlay.insert(3, yardage)
                        self.lastPlayDict['yardage'] = yardage
                        return yardage

                else:
                    interceptRoll = randint(1,100)
                    if interceptRoll <= 5:
                        # print("\n{0} defense has intercepted {1}'s pass!".format(defense.name, passer.name))
                        yardage = 1003
                        passer.gameStatsDict['ints'] += 1
                        passer.attributes.confidence = round(passer.attributes.confidence * .97)
                        defense.seasonTeamStats['Defense']['ints'] += 1
                        #self.lastPlay.insert(0, PlayType.Pass)
                        self.lastPlayDict['play'] = PlayType.Pass.name
                        #self.lastPlay.insert(1, passer) 
                        self.lastPlayDict['passer'] = passer
                        #self.lastPlay.insert(2, receiver)
                        self.lastPlayDict['receiver'] = receiver
                        #self.lastPlay.insert(3, yardage)
                        self.lastPlayDict['yardage'] = yardage
                        self.lastPlayDict['turnover'] = True
                        return yardage
                    else:
                        # print("\n{0}'s pass to {1} is incomplete".format(passer.name, receiver.name))
                        yardage = 0
                        passer.attributes.confidence = round(passer.attributes.confidence * .99)
                        #self.lastPlay.insert(0, PlayType.Pass)
                        self.lastPlayDict['play'] = PlayType.Pass.name
                        #self.lastPlay.insert(1, passer) 
                        self.lastPlayDict['passer'] = passer
                        #self.lastPlay.insert(2, receiver)
                        self.lastPlayDict['receiver'] = receiver
                        #self.lastPlay.insert(3, yardage)
                        self.lastPlayDict['yardage'] = yardage
                        return yardage


            elif passType.value == 2:
                if passTarget < 3:
                    receiver = rb   
                elif passTarget >= 3 and passTarget < 5:
                    receiver = te
                else:
                    receiver = wr
                accRoll = randint(1,100)
                if accRoll < (passer.attributes.overallRating - (defense.passDefenseRating/8)):
                    dropRoll = round(randint(1,100) + (defense.passDefenseRating/10))
                    if receiver.attributes.overallRating > dropRoll:
                        passYards = randint(5,10)
                        yac = 0
                        x = randint(1,10)
                        if receiver.attributes.overallRating > defense.defenseRating:
                            if x < 2:
                                yac = randint(0,3)
                            elif x >= 2 and x <= 9:
                                yac = randint(4,10)
                            else:
                                if self.yardsToEndzone < 11:
                                    yac = randint(0, self.yardsToEndzone)
                                else:
                                    yac = randint(11, self.yardsToEndzone)
                        else:
                            if x <= 7:
                                yac = randint(0,3)
                            else:
                                yac = randint(4, 7)
                        yardage = passYards + yac
                        if yardage > self.yardsToEndzone:
                            yardage = self.yardsToEndzone
                        passer.gameStatsDict['passYards'] += yardage
                        passer.gameStatsDict['passComp'] += 1
                        receiver.gameStatsDict['passTargets'] += 1
                        receiver.gameStatsDict['receptions'] += 1
                        receiver.gameStatsDict['rcvYards'] += yardage
                        passer.attributes.confidence = round(passer.attributes.confidence * 1.007)
                        receiver.attributes.confidence = round(receiver.attributes.confidence * 1.007)
                        #self.lastPlay.insert(0, PlayType.Pass)
                        self.lastPlayDict['play'] = PlayType.Pass.name
                        #self.lastPlay.insert(1, passer) 
                        self.lastPlayDict['passer'] = passer
                        #self.lastPlay.insert(2, receiver)
                        self.lastPlayDict['receiver'] = receiver
                        #self.lastPlay.insert(3, yardage)
                        self.lastPlayDict['yardage'] = yardage
                        return yardage
                    else:
                        # print("\n{0}'s pass to {1} is incomplete".format(passer.name, receiver.name))
                        yardage = 0
                        receiver.gameStatsDict['passTargets'] += 1 
                        receiver.attributes.confidence = round(receiver.attributes.confidence * .98)                
                        #self.lastPlay.insert(0, PlayType.Pass)
                        self.lastPlayDict['play'] = PlayType.Pass.name
                        #self.lastPlay.insert(1, passer) 
                        self.lastPlayDict['passer'] = passer
                        #self.lastPlay.insert(2, receiver)
                        self.lastPlayDict['receiver'] = receiver
                        #self.lastPlay.insert(3, yardage)
                        self.lastPlayDict['yardage'] = yardage
                        return yardage
                else:
                    interceptRoll = randint(1,100)
                    if interceptRoll <= 5:
                        # print("\n{0} defense has intercepted {1}'s pass!".format(defense.name, passer.name))
                        yardage = 1003
                        passer.gameStatsDict['ints'] += 1 
                        passer.attributes.confidence = round(passer.attributes.confidence * .97)
                        defense.seasonTeamStats['Defense']['ints'] += 5
                        #self.lastPlay.insert(0, PlayType.Pass)
                        self.lastPlayDict['play'] = PlayType.Pass.name
                        #self.lastPlay.insert(1, passer) 
                        self.lastPlayDict['passer'] = passer
                        #self.lastPlay.insert(2, receiver)
                        self.lastPlayDict['receiver'] = receiver
                        #self.lastPlay.insert(3, yardage)
                        self.lastPlayDict['yardage'] = yardage
                        self.lastPlayDict['turnover'] = True
                        return yardage
                    else:
                        # print("\n{0}'s pass to {1} is incomplete".format(passer.name, receiver.name))
                        yardage = 0   
                        passer.attributes.confidence = round(passer.attributes.confidence * .99)             
                        #self.lastPlay.insert(0, PlayType.Pass)
                        self.lastPlayDict['play'] = PlayType.Pass.name
                        #self.lastPlay.insert(1, passer) 
                        self.lastPlayDict['passer'] = passer
                        #self.lastPlay.insert(2, receiver)
                        self.lastPlayDict['receiver'] = receiver
                        #self.lastPlay.insert(3, yardage)
                        self.lastPlayDict['yardage'] = yardage
                        return yardage

            elif passType.value == 3:
                if passTarget < 3:
                    receiver = te   
                else:
                    receiver = wr
                accRoll = randint(1,100)
                if accRoll < (passer.attributes.overallRating - (defense.passDefenseRating/5)):
                    dropRoll = round(randint(1,100) + (defense.passDefenseRating/10))
                    if receiver.attributes.overallRating > dropRoll:
                        passYards = randint(11,20)
                        yac = 0
                        x = randint(1,10)
                        if receiver.attributes.overallRating > defense.defenseRating:
                            if x < 2:
                                yac = randint(0,3)
                            elif x >= 2 and x <= 9:
                                yac = randint(4,10)
                            else:
                                if self.yardsToEndzone < 11:
                                    yac = randint(0, self.yardsToEndzone)
                                else:
                                    yac = randint(11, self.yardsToEndzone)
                        else:
                            if x <= 7:
                                yac = randint(0,3)
                            else:
                                yac = randint(4, 7)
                        yardage = passYards + yac
                        if yardage > self.yardsToEndzone:
                            yardage = self.yardsToEndzone
                        passer.gameStatsDict['passYards'] += yardage
                        passer.gameStatsDict['passComp'] += 1
                        receiver.gameStatsDict['passTargets'] += 1
                        receiver.gameStatsDict['receptions'] += 1
                        receiver.gameStatsDict['rcvYards'] += yardage
                        passer.attributes.confidence = round(passer.attributes.confidence * 1.01)
                        receiver.attributes.confidence = round(receiver.attributes.confidence * 1.01)
                        #self.lastPlay.insert(0, PlayType.Pass)
                        self.lastPlayDict['play'] = PlayType.Pass.name
                        #self.lastPlay.insert(1, passer) 
                        self.lastPlayDict['passer'] = passer
                        #self.lastPlay.insert(2, receiver)
                        self.lastPlayDict['receiver'] = receiver
                        #self.lastPlay.insert(3, yardage)
                        self.lastPlayDict['yardage'] = yardage
                        return yardage
                    else:
                        # print("\n{0}'s pass to {1} is incomplete".format(passer.name, receiver.name))
                        yardage = 0
                        receiver.gameStatsDict['passTargets'] += 1  
                        receiver.attributes.confidence = round(receiver.attributes.confidence * .98)                    
                        #self.lastPlay.insert(0, PlayType.Pass)
                        self.lastPlayDict['play'] = PlayType.Pass.name
                        #self.lastPlay.insert(1, passer) 
                        self.lastPlayDict['passer'] = passer
                        #self.lastPlay.insert(2, receiver)
                        self.lastPlayDict['receiver'] = receiver
                        #self.lastPlay.insert(3, yardage)
                        self.lastPlayDict['yardage'] = yardage
                        return yardage
                else:
                    interceptRoll = randint(1,100)
                    if interceptRoll <= 5:
                        # print("\n{0} defense has intercepted {1}'s pass!".format(defense.name, passer.name))
                        yardage = 1003
                        passer.gameStatsDict['ints'] += 1 
                        passer.attributes.confidence = round(passer.attributes.confidence * .97)
                        defense.seasonTeamStats['Defense']['ints'] += 1
                        #self.lastPlay.insert(0, PlayType.Pass)
                        self.lastPlayDict['play'] = PlayType.Pass.name
                        #self.lastPlay.insert(1, passer) 
                        self.lastPlayDict['passer'] = passer
                        #self.lastPlay.insert(2, receiver)
                        self.lastPlayDict['receiver'] = receiver
                        #self.lastPlay.insert(3, yardage)
                        self.lastPlayDict['yardage'] = yardage
                        self.lastPlayDict['turnover'] = True
                        return yardage
                    else:
                        # print("\n{0}'s pass to {1} is incomplete".format(passer.name, receiver.name))
                        yardage = 0    
                        passer.attributes.confidence = round(passer.attributes.confidence * .99) 
                        #self.lastPlay.insert(0, PlayType.Pass)
                        self.lastPlayDict['play'] = PlayType.Pass.name
                        #self.lastPlay.insert(1, passer) 
                        self.lastPlayDict['passer'] = passer
                        #self.lastPlay.insert(2, receiver)
                        self.lastPlayDict['receiver'] = receiver
                        #self.lastPlay.insert(3, yardage)
                        self.lastPlayDict['yardage'] = yardage
                        return yardage

    def playCaller(self, offense, defense):
        if self.down <= 2:
            if self.yardsToEndzone <= 20:
                x = randint(1,10)
                if x <= 3:
                    return self.runPlay(offense, defense)
                else:
                    y = randint(1,10)
                    if y <= 4:
                        return self.passPlay(offense, defense, PassType.short)
                    elif y > 4 and y <= 8:
                        return self.passPlay(offense, defense, PassType.medium)
                    else:
                        return self.passPlay(offense, defense, PassType.long)
            if self.yardsToSafety <= 5:
                x = randint(1,10)
                if x <= 4:
                    y = randint(0,1)
                    if y == 0:
                        return self.passPlay(offense, defense, PassType.medium)
                    else:
                        return self.passPlay(offense, defense, PassType.long)
                else:
                    return self.runPlay(offense, defense)
            else:
                x = randint(0,1)
                if x == 1:
                    return self.runPlay(offense, defense)
                else:
                    y = randint(1,10)
                    if y <= 4:
                        return self.passPlay(offense, defense, PassType.short)
                    elif y > 4 and y <= 8:
                        return self.passPlay(offense, defense, PassType.medium)
                    else:
                        return self.passPlay(offense, defense, PassType.long)
    
        elif self.down == 3:
            if self.yardsToFirstDown <= 4:
                x = randint(1,10)
                if x < 7:
                    return self.runPlay(offense, defense)
                elif x >= 7 and x < 9:
                    return self.passPlay(offense, defense, PassType.short)
                else:
                    return self.passPlay(offense, defense, PassType.medium)
            else:
                x = randint(1,10)
                if x < 6:
                    return self.passPlay(offense, defense, PassType.medium)
                elif x >= 6 and x < 9:
                    return self.passPlay(offense, defense, PassType.short)
                else:
                    return self.passPlay(offense, defense, PassType.long)
        elif self.down == 4:
            if self.currentQuarter == 4 and self.awayTeam == offense and self.awayScore < self.homeScore:
                if self.totalPlays > 128 and self.yardsToEndzone < 20:
                    return self.passPlay(offense, defense, PassType.medium)
                elif self.totalPlays > 128 and self.yardsToEndzone > 20:
                    return self.passPlay(offense, defense, PassType.long)
                elif self.yardsToFirstDown <= 2:
                    x = randint(1,3)
                    if x == 1:
                        return self.runPlay(offense, defense)
                    elif x == 2:
                        return self.passPlay(offense, defense, PassType.short)
                    else:
                        return self.passPlay(offense, defense, PassType.medium)
                else:
                    return self.passPlay(offense, defense, PassType.medium)
            elif self.currentQuarter == 4 and self.homeTeam == offense and self.homeScore < self.awayScore:
                if self.totalPlays > 128 and self.yardsToEndzone < 20:
                    return self.passPlay(offense, defense, PassType.medium)
                elif self.totalPlays > 128 and self.yardsToEndzone > 20:
                    return self.passPlay(offense, defense, PassType.long)
                elif self.yardsToFirstDown <= 2:
                    x = randint(1,3)
                    if x == 1:
                        return self.runPlay(offense, defense)
                    elif x == 2:
                        return self.passPlay(offense, defense, PassType.short)
                    else:
                        return self.passPlay(offense, defense, PassType.medium)
                else:
                    return self.passPlay(offense, defense, PassType.medium)

            elif self.yardsToEndzone <= 5:
                    x = randint(1,10)
                    if x < 4:
                        return 1001
                    else:
                        y = randint(1,10)
                        if y < 5:
                            return self.runPlay(offense, defense)
                        elif y >= 5 and y < 8:
                            return self.passPlay(offense, defense, PassType.short)
                        else:
                            return self.passPlay(offense, defense, PassType.medium)

            elif self.yardsToEndzone <= 20:
                if self.yardsToFirstDown <= 2:
                    x = randint(1,3)
                    if x == 1:
                        return self.runPlay(offense, defense)
                    elif x == 2:
                        return self.passPlay(offense, defense, PassType.short)
                    else:
                        return self.passPlay(offense, defense, PassType.medium)
                else:
                    x = randint(1,10)
                    if x < 8:
                        return 1001
                    else:
                        return self.passPlay(offense, defense, PassType.medium)
            else:
                if self.yardsToFirstDown <= 2:
                    x = randint(1,10)
                    if x < 7:
                        #self.lastPlay.insert(0, PlayType.Punt)
                        self.lastPlayDict['play'] = PlayType.Punt.name
                        return 1002
                    elif x >= 7 and x < 9:
                        return self.passPlay(offense, defense, PassType.short)
                    else:
                        return self.passPlay(offense, defense, PassType.medium)
                else:
                    x = randint(1,10)
                    if x < 10:
                        #self.lastPlay.insert(0, PlayType.Punt)
                        self.lastPlayDict['play'] = PlayType.Punt.name
                        return 1002
                    else:
                        y = randint(0,1)
                        if y == 0:
                            return self.passPlay(offense, defense, PassType.medium)
                        else:
                            return self.passPlay(offense, defense, PassType.long)

    def turnover(self, offense, defense, yards):
        self.offensiveTeam = defense
        self.defensiveTeam = offense
        self.yardsToEndzone = yards
        self.yardsToSafety = 100 - self.yardsToEndzone
        self.yardsToFirstDown = 10

    def scoreChange(self):
        print("{0}: {1}".format(self.awayTeam.name, self.awayScore))
        print("{0}: {1}".format(self.homeTeam.name, self.homeScore))

    def postgame(self):    
        # print('\n{0} Player Stats'.format(self.homeTeam.name))    
        for player in self.homeTeam.rosterDict.values():
            # print('\n{0} | {1} | {2}'.format(player.name, player.position.name, player.overallRating))
            if 'passComp' in player.gameStatsDict:
                player.gameStatsDict['totalYards'] = player.gameStatsDict['passYards']

                if player.gameStatsDict['passComp'] > 0:
                    player.gameStatsDict['ypc'] = round(player.gameStatsDict['passYards']/player.gameStatsDict['passComp'])
                    player.gameStatsDict['passCompPerc'] = round((player.gameStatsDict['passComp']/player.gameStatsDict['passAtt'])*100)

                player.seasonStatsDict['passAtt'] += player.gameStatsDict['passAtt']
                player.seasonStatsDict['passComp'] += player.gameStatsDict['passComp']
                player.seasonStatsDict['tds'] += player.gameStatsDict['tds']
                player.seasonStatsDict['ints'] += player.gameStatsDict['ints']
                player.seasonStatsDict['passYards'] += player.gameStatsDict['passYards']
                player.seasonStatsDict['totalYards'] += player.gameStatsDict['passYards']

                if player.seasonStatsDict['passComp'] > 0:
                    player.seasonStatsDict['ypc'] = round(player.seasonStatsDict['passYards']/player.seasonStatsDict['passComp'])
                    player.seasonStatsDict['passCompPerc'] = round((player.seasonStatsDict['passComp']/player.seasonStatsDict['passAtt'])*100)

            if 'receptions' in player.gameStatsDict:
                player.gameStatsDict['totalYards'] = player.gameStatsDict['rcvYards']

                if player.gameStatsDict['receptions'] > 0:
                    player.gameStatsDict['ypr'] = round(player.gameStatsDict['rcvYards']/player.gameStatsDict['receptions'])
                    player.gameStatsDict['rcvPerc'] = round((player.gameStatsDict['receptions']/player.gameStatsDict['passTargets'])*100)

                player.seasonStatsDict['receptions'] += player.gameStatsDict['receptions']
                player.seasonStatsDict['passTargets'] += player.gameStatsDict['passTargets']
                player.seasonStatsDict['rcvYards'] += player.gameStatsDict['rcvYards']
                player.seasonStatsDict['tds'] += player.gameStatsDict['tds']
                player.seasonStatsDict['totalYards'] += player.gameStatsDict['rcvYards']
                
                if player.seasonStatsDict['receptions'] > 0:
                    player.seasonStatsDict['ypr'] = round(player.seasonStatsDict['rcvYards']/player.seasonStatsDict['receptions'])
                    player.seasonStatsDict['rcvPerc'] = round((player.seasonStatsDict['receptions']/player.seasonStatsDict['passTargets'])*100)

            if 'carries' in player.gameStatsDict:
                player.gameStatsDict['totalYards'] = player.gameStatsDict['rcvYards'] + player.gameStatsDict['runYards']

                if player.gameStatsDict['carries'] > 0:
                    player.gameStatsDict['ypc'] = round(player.gameStatsDict['runYards']/player.gameStatsDict['carries'])

                player.seasonStatsDict['carries'] += player.gameStatsDict['carries']
                player.seasonStatsDict['runYards'] += player.gameStatsDict['runYards']
                player.seasonStatsDict['tds'] += player.gameStatsDict['tds']
                player.seasonStatsDict['fumblesLost'] += player.gameStatsDict['fumblesLost']
                player.seasonStatsDict['totalYards'] += player.gameStatsDict['runYards']

                if player.seasonStatsDict['carries'] > 0:
                    player.seasonStatsDict['ypc'] = round(player.seasonStatsDict['runYards']/player.seasonStatsDict['carries'])
            if 'fgs' in player.gameStatsDict:
                if player.gameStatsDict['fgs'] > 0:
                    player.gameStatsDict['fgPerc'] = round((player.gameStatsDict['fgs']/player.gameStatsDict['fgAtt'])*100)
                else:
                    player.gameStatsDict['fgPerc'] = 0

                player.seasonStatsDict['fgAtt'] += player.gameStatsDict['fgAtt']
                player.seasonStatsDict['fgs'] += player.gameStatsDict['fgs']
                if player.seasonStatsDict['fgs'] > 0:
                    player.seasonStatsDict['fgPerc'] = round((player.seasonStatsDict['fgs']/player.seasonStatsDict['fgAtt'])*100)
                else:
                    player.seasonStatsDict['fgPerc'] = 0

        # print('\n{0} Player Stats'.format(self.awayTeam.name))    
        for player in self.awayTeam.rosterDict.values():
            # print('\n{0} | {1} | {2}'.format(player.name, player.position.name, player.overallRating))

            if 'passComp' in player.gameStatsDict:
                player.gameStatsDict['totalYards'] = player.gameStatsDict['passYards']

                if player.gameStatsDict['passComp'] > 0:
                    player.gameStatsDict['ypc'] = round(player.gameStatsDict['passYards']/player.gameStatsDict['passComp'])
                    player.gameStatsDict['passCompPerc'] = round((player.gameStatsDict['passComp']/player.gameStatsDict['passAtt'])*100)

                player.seasonStatsDict['passAtt'] += player.gameStatsDict['passAtt']
                player.seasonStatsDict['passComp'] += player.gameStatsDict['passComp']
                player.seasonStatsDict['tds'] += player.gameStatsDict['tds']
                player.seasonStatsDict['ints'] += player.gameStatsDict['ints']
                player.seasonStatsDict['passYards'] += player.gameStatsDict['passYards']
                player.seasonStatsDict['totalYards'] += player.gameStatsDict['passYards']

                if player.seasonStatsDict['passComp'] > 0:
                    player.seasonStatsDict['ypc'] = round(player.seasonStatsDict['passYards']/player.seasonStatsDict['passComp'])
                    player.seasonStatsDict['passCompPerc'] = round((player.seasonStatsDict['passComp']/player.seasonStatsDict['passAtt'])*100)

            if 'receptions' in player.gameStatsDict:
                player.gameStatsDict['totalYards'] = player.gameStatsDict['rcvYards']

                if player.gameStatsDict['receptions'] > 0:
                    player.gameStatsDict['ypr'] = round(player.gameStatsDict['rcvYards']/player.gameStatsDict['receptions'])
                    player.gameStatsDict['rcvPerc'] = round((player.gameStatsDict['receptions']/player.gameStatsDict['passTargets'])*100)

                player.seasonStatsDict['receptions'] += player.gameStatsDict['receptions']
                player.seasonStatsDict['passTargets'] += player.gameStatsDict['passTargets']
                player.seasonStatsDict['rcvYards'] += player.gameStatsDict['rcvYards']
                player.seasonStatsDict['tds'] += player.gameStatsDict['tds']
                player.seasonStatsDict['totalYards'] += player.gameStatsDict['rcvYards']
                
                if player.seasonStatsDict['receptions'] > 0:
                    player.seasonStatsDict['ypr'] = round(player.seasonStatsDict['rcvYards']/player.seasonStatsDict['receptions'])
                    player.seasonStatsDict['rcvPerc'] = round((player.seasonStatsDict['receptions']/player.seasonStatsDict['passTargets'])*100)

            if 'carries' in player.gameStatsDict:
                player.gameStatsDict['totalYards'] = player.gameStatsDict['rcvYards'] + player.gameStatsDict['runYards']

                if player.gameStatsDict['carries'] > 0:
                    player.gameStatsDict['ypc'] = round(player.gameStatsDict['runYards']/player.gameStatsDict['carries'])

                player.seasonStatsDict['carries'] += player.gameStatsDict['carries']
                player.seasonStatsDict['runYards'] += player.gameStatsDict['runYards']
                player.seasonStatsDict['tds'] += player.gameStatsDict['tds']
                player.seasonStatsDict['fumblesLost'] += player.gameStatsDict['fumblesLost']
                player.seasonStatsDict['totalYards'] += player.gameStatsDict['runYards']

                if player.seasonStatsDict['carries'] > 0:
                    player.seasonStatsDict['ypc'] = round(player.seasonStatsDict['runYards']/player.seasonStatsDict['carries'])

            if 'fgs' in player.gameStatsDict:
                if player.gameStatsDict['fgs'] > 0:
                    player.gameStatsDict['fgPerc'] = round((player.gameStatsDict['fgs']/player.gameStatsDict['fgAtt'])*100)
                else:
                    player.gameStatsDict['fgPerc'] = 0

                player.seasonStatsDict['fgAtt'] += player.gameStatsDict['fgAtt']
                player.seasonStatsDict['fgs'] += player.gameStatsDict['fgs']
                if player.seasonStatsDict['fgs'] > 0:
                    player.seasonStatsDict['fgPerc'] = round((player.seasonStatsDict['fgs']/player.seasonStatsDict['fgAtt'])*100)
                else:
                    player.seasonStatsDict['fgPerc'] = 0

        

    def playGame(self):
        #print("\n----------------------------------------------------------------------------------------")
        # print("\nGame Start: {0}[OAR:{1}|OR:{2}|RDR:{3}|PDR:{4}] v. {5}[OAR:{6}|OR:{7}|RDR:{8}|PDR:{9}])".format(self.awayTeam.name, self.awayTeam.overallRating, self.awayTeam.offenseRating, self.awayTeam.runDefenseRating, self.awayTeam.passDefenseRating, self.homeTeam.name, self.homeTeam.overallRating, self.homeTeam.offenseRating, self.homeTeam.runDefenseRating, self.homeTeam.passDefenseRating))
        self.totalPlays = 0
        possReset = 80
        playsDict = {}
        x = randint(0,1)
        if x == 0:
            self.offensiveTeam = self.homeTeam
            self.defensiveTeam = self.awayTeam
        else:
            self.offensiveTeam = self.awayTeam
            self.defensiveTeam = self.homeTeam

        while self.totalPlays < 132 or self.homeScore == self.awayScore:


            if self.totalPossessions < 33:
                self.currentQuarter = 1
            elif self.totalPossessions >= 33 and self.totalPossessions < 66:
                self.currentQuarter = 2
            elif self.totalPossessions >= 66 and self.totalPossessions < 99:
                self.currentQuarter = 3
            else:
                self.currentQuarter = 4

            if self.totalPlays < 1:
                self.yardsToFirstDown = 10
                self.yardsToEndzone = 80
                self.yardsToSafety = 20

            self.down = 1

            # print("\n{0} is on offense. {1} yard(s) to the endzone".format(self.offensiveTeam.name, self.yardsToEndzone))

            while self.down <= 4:

                if self.totalPlays > 0:
                    play = str(self.totalPlays)
                    playsDict[play] = self.lastPlayDict
                if self.totalPlays == 132 and self.homeScore != self.awayScore:
                    break

                #self.lastPlay.clear()
                
                self.lastPlayDict = playDict.copy()

                self.lastPlayDict['offense'] = self.offensiveTeam.name
                self.lastPlayDict['defense'] = self.defensiveTeam.name
                self.lastPlayDict['down'] = self.down

                # print("\nDOWN: {0}".format(self.down))
                yardsGained = self.playCaller(self.offensiveTeam, self.defensiveTeam)
                self.totalPlays += 1

                if self.lastPlayDict['passer'] is not None:
                    self.lastPlayDict['passer'].updateRating()
                if self.lastPlayDict['receiver'] is not None:
                    self.lastPlayDict['receiver'].updateRating()
                if self.lastPlayDict['runner'] is not None:
                    self.lastPlayDict['runner'].updateRating()


                if yardsGained == 1001:
                    if self.fieldGoalTry(self.offensiveTeam):
                        if self.offensiveTeam == self.homeTeam:
                            self.homeScore += 3
                        elif self.offensiveTeam == self.awayTeam:
                            self.awayScore += 3
                        # print("\n{0} field goal is GOOD. KICKER: {1}".format(self.offensiveTeam.name,self.lastPlay[1].name))
                        # self.scoreChange()
                        self.lastPlayDict['score'] = 3
                        self.turnover(self.offensiveTeam, self.defensiveTeam, possReset)
                        break
                    else:
                        # print("\n{0} field goal is NO GOOD. KICKER: {1}".format(self.offensiveTeam.name,self.lastPlay[1].name))
                        # print("Turnover")
                        self.turnover(self.offensiveTeam, self.defensiveTeam, self.yardsToSafety)
                        break
                elif yardsGained == 1002:
                    # print("\n{0} punt.".format(self.offensiveTeam.name))
                    # print("Turnover")
                    self.turnover(self.offensiveTeam, self.defensiveTeam, possReset)
                    break
                elif yardsGained == 1003 or yardsGained == 1004:
                    # print("Turnover")
                    self.turnover(self.offensiveTeam, self.defensiveTeam, self.yardsToSafety)
                    break
                else:
                    if yardsGained >= self.yardsToEndzone:
                        if self.lastPlayDict['play'] == 'Run':
                            self.lastPlayDict['runner'].gameStatsDict['tds'] += 1
                            self.lastPlayDict['runner'].attributes.confidence = round(self.lastPlayDict['runner'].attributes.confidence * 1.02)
                            self.lastPlayDict['runner'].updateRating()
                            # print("\n{0} TOUCHDOWN. {1} yard run by {2}".format(self.offensiveTeam.name, yardsGained, self.lastPlay[1].name))
                        elif self.lastPlayDict['play'] == 'Pass':
                            self.lastPlayDict['passer'].gameStatsDict['tds'] += 1
                            self.lastPlayDict['receiver'].gameStatsDict['tds'] += 1
                            self.lastPlayDict['passer'].attributes.confidence = round(self.lastPlayDict['passer'].attributes.confidence * 1.02)
                            self.lastPlayDict['receiver'].attributes.confidence = round(self.lastPlayDict['receiver'].attributes.confidence * 1.02)
                            self.lastPlayDict['passer'].updateRating()
                            self.lastPlayDict['receiver'].updateRating()
                            # print("\n{0} TOUCHDOWN. {1} yard pass from {2} to {3}".format(self.offensiveTeam.name, yardsGained, self.lastPlay[1].name, self.lastPlay[2].name))
                        self.lastPlayDict['score'] = 6

                        if self.offensiveTeam == self.homeTeam:
                            self.homeScore += 6
                        elif self.offensiveTeam == self.awayTeam:
                            self.awayScore += 6

                        # self.scoreChange()

                        if self.extraPointTry(self.offensiveTeam):
                            if self.offensiveTeam == self.homeTeam:
                                self.homeScore += 1
                            elif self.offensiveTeam == self.awayTeam:
                                self.awayScore += 1
                            self.lastPlayDict['score'] = 1
                            # print("\n{0} extra point is GOOD.".format(self.offensiveTeam.name))
                            # self.scoreChange()
                        else:
                            pass
                            # print("\n{0} extra point is NO GOOD.".format(self.offensiveTeam.name))    

                        self.turnover(self.offensiveTeam, self.defensiveTeam, possReset)
                        break

                    elif yardsGained >= self.yardsToFirstDown:
                        self.down = 1
                        if self.yardsToEndzone < 10:
                            self.yardsToFirstDown = self.yardsToEndzone
                        else:
                            self.yardsToFirstDown = 10
                        self.yardsToSafety += yardsGained
                        self.yardsToEndzone -= yardsGained
                        # print("\n{0} FIRST DOWN. {1} yard(s) to endzone".format(self.offensiveTeam.name, self.yardsToEndzone))
                        continue

                    elif (self.yardsToSafety + yardsGained) <= 0:
                        if self.defensiveTeam == self.homeTeam:
                            self.homeScore += 2
                        elif self.defensiveTeam == self.awayTeam:
                            self.awayScore += 2
                        # print("\nSAFETY")
                        # self.scoreChange()()
                        self.turnover(self.offensiveTeam, self.defensiveTeam, possReset)
                        break

                    elif yardsGained < self.yardsToFirstDown:
                        if self.down < 4:
                            self.yardsToEndzone -= yardsGained
                            self.yardsToFirstDown -= yardsGained
                            self.down += 1
                            continue
                        else:
                            # print("\nTurnover on downs")
                            self.turnover(self.offensiveTeam, self.defensiveTeam, self.yardsToSafety)
                            break
            

        if self.awayScore > self.homeScore:
            self.winningTeam = self.awayTeam
            self.losingTeam = self.homeTeam
            self.awayTeam.seasonTeamStats['wins'] += 1
            self.homeTeam.seasonTeamStats['losses'] += 1
            self.gameDict['score'] = '{0} - {1}'.format(self.awayScore, self.homeScore)
            #print("\nRESULT: {0}[OAR:{1}|OR:{2}|RDR:{3}|PDR:{4}] def. {5}[OAR:{6}|OR:{7}|RDR:{8}|PDR:{9}]).".format(self.winningTeam.name, self.winningTeam.overallRating, self.winningTeam.offenseRating, self.winningTeam.runDefenseRating, self.winningTeam.passDefenseRating, self.losingTeam.name, self.losingTeam.overallRating, self.losingTeam.offenseRating, self.losingTeam.runDefenseRating, self.losingTeam.passDefenseRating))
            #print("SCORE: {0}-{1}".format(self.awayScore, self.homeScore))
        elif self.homeScore > self.awayScore:
            self.winningTeam = self.homeTeam
            self.losingTeam = self.awayTeam
            self.homeTeam.seasonTeamStats['wins'] += 1
            self.awayTeam.seasonTeamStats['losses'] += 1
            self.gameDict['score'] = '{0} - {1}'.format(self.homeScore, self.awayScore)
            #print("\nRESULT: {0}[OAR:{1}|OR:{2}|RDR:{3}|PDR:{4}] def. {5}[OAR:{6}|OR:{7}|RDR:{8}|PDR:{9}]).".format(self.winningTeam.name, self.winningTeam.overallRating, self.winningTeam.offenseRating, self.winningTeam.runDefenseRating, self.winningTeam.passDefenseRating, self.losingTeam.name, self.losingTeam.overallRating, self.losingTeam.offenseRating, self.losingTeam.runDefenseRating, self.losingTeam.passDefenseRating))
            #print("SCORE: {0}-{1}".format(self.homeScore, self.awayScore))

        self.gameDict['winningTeam'] = self.winningTeam.name
        self.gameDict['losingTeam'] = self.losingTeam.name

        self.winningTeam.updateRating()
        self.losingTeam.updateRating()

        # print("\nGAME OVER")        

class Postseason:
    def __init__(self, season):
        self.playoffTeamsList = []
        self.currentSeason = season
    
    def playPlayoffs(self):
        #print("\nFLOOSBALL DIVISIONAL ROUND")
        champ = None
        playoffDict = {}
        x = 0
        for division in divisionList:
            x += 1
            strRound = 'Divisonal Game {}'.format(x)
            list.sort(division.teamList, key=lambda team: team.seasonTeamStats['winPerc'], reverse=True)
            division.teamList[0].divisionChampionships += 1
            division.teamList[0].playoffAppearances += 1
            division.teamList[1].playoffAppearances += 1
            newGame = Game(division.teamList[0], division.teamList[1])
            newGame.playGame()
            newGame.saveGameData()
            gameResults = newGame.gameDict
            self.playoffTeamsList.append(newGame.winningTeam)
            playoffDict[strRound] = gameResults
        
        list.sort(self.playoffTeamsList, key=lambda team: team.seasonTeamStats['winPerc'], reverse=True)

        numOfRounds = getPower(2, len(self.playoffTeamsList))
        winningTeamsList = []
        losingTeam = None

        for x in range(numOfRounds):
            # if (x + 1) == numOfRounds:
            #     #print("\nFLOOSBALL CHAMPIONSHIP GAME")
            # else:
            #     #print("\nFLOOSBALL PLAYOFFS ROUND {0}".format(x + 2))
            if x >= 1:
                self.playoffTeamsList = winningTeamsList

            numOfGames = int(len(self.playoffTeamsList)/2)

            for y in range(numOfGames):
                strPlayoffGame = 'Playoff Game {}'.format(y + 1)
                lastSeed = len(self.playoffTeamsList) - 1
                newGame = Game(self.playoffTeamsList[0], self.playoffTeamsList[lastSeed])
                newGame.playGame()
                newGame.saveGameData()
                gameResults = newGame.gameDict
                if numOfGames == 1:
                    self.playoffTeamsList.clear()
                    newGame.winningTeam.leagueChampionships += 1
                    champ = newGame.winningTeam
                    playoffDict['Championship'] = gameResults
                else:
                    playoffDict[strPlayoffGame] = gameResults
                    if self.playoffTeamsList[0].name == gameResults['winningTeam']:
                        losingTeam = self.playoffTeamsList.pop(lastSeed)
                        winningTeamsList.append(self.playoffTeamsList.pop(0))
                    elif self.playoffTeamsList[lastSeed].name == gameResults['winningTeam']:
                        winningTeamsList.append(self.playoffTeamsList.pop(lastSeed))
                        losingTeam = self.playoffTeamsList.pop(0)

            jsonFile = open(os.path.join('{}/games'.format(self.currentSeason), 'postseason.json'), "w+")
            jsonFile.write(json.dumps(playoffDict, indent=4))
            jsonFile.close()

        return champ

def draft():
    draftOrderList = []
    draftQueueList = teamList.copy()
    playerDraftList = playerList.copy()
    rounds = 15

    draftQbList : list[Player] = []
    draftRbList : list[Player] = []
    draftWrList : list[Player] = []
    draftTeList : list[Player] = []
    draftKList : list[Player] = []

    for player in playerList:
        if player.position.value == 1:
            draftQbList.append(player)
        elif player.position.value == 2:
            draftRbList.append(player)
        elif player.position.value == 3:
            draftWrList.append(player)
        elif player.position.value == 4:
            draftTeList.append(player)
        elif player.position.value == 5:
            draftKList.append(player)
    
    list.sort(draftQbList, key=lambda player: player.attributes.skillRating, reverse=True)
    list.sort(draftRbList, key=lambda player: player.attributes.skillRating, reverse=True)
    list.sort(draftWrList, key=lambda player: player.attributes.skillRating, reverse=True)
    list.sort(draftTeList, key=lambda player: player.attributes.skillRating, reverse=True)
    list.sort(draftKList, key=lambda player: player.attributes.skillRating, reverse=True)
    list.sort(playerDraftList, key=lambda player: player.attributes.overallRating, reverse=True)

    #print('\n Available Players by Position')
    #print('\n QBs = {0} | RBs = {1} | WRs = {2} | TEs = {3} | Ks = {4}'.format(qbs, rbs, wrs, tes, ks))


    for x in range(len(teamList)):
        rand = randint(0,len(draftQueueList) - 1)
        draftOrderList.insert(x, draftQueueList[rand])
        draftQueueList.pop(rand)

    for x in range(1, int(rounds)):
        #print('\nRound {0}'.format(x))
        for team in draftOrderList:

            if x == 1:
                if playerDraftList[0].position.value == 1:
                    team.rosterDict['qb'] = draftQbList.pop(0)
                elif playerDraftList[0].position.value == 2:
                    team.rosterDict['rb'] = draftRbList.pop(0)
                elif playerDraftList[0].position.value == 3:
                    team.rosterDict['wr'] = draftWrList.pop(0)
                elif playerDraftList[0].position.value == 4:
                    team.rosterDict['te'] = draftTeList.pop(0)
                elif playerDraftList[0].position.value == 5:
                    team.rosterDict['k'] = draftKList.pop(0)
            elif playerDraftList[0].position.value == 1 and team.rosterDict['qb'] is None:
                team.rosterDict['qb'] = draftQbList.pop(0)
            elif playerDraftList[0].position.value == 2 and team.rosterDict['rb'] is None:
                team.rosterDict['rb'] = draftRbList.pop(0)
            elif playerDraftList[0].position.value == 3 and team.rosterDict['wr'] is None:
                team.rosterDict['wr'] = draftWrList.pop(0)
            elif playerDraftList[0].position.value == 4 and team.rosterDict['te'] is None:
                team.rosterDict['te'] = draftTeList.pop(0)
            elif playerDraftList[0].position.value == 5 and team.rosterDict['k'] is None:
                team.rosterDict['k'] = draftKList.pop(0)
            elif playerDraftList[0].position.value == 1 and team.rosterDict['qb'] is not None:
                if team.rosterDict['rb'] is None:
                    team.rosterDict['rb'] = draftRbList.pop(0)
                elif team.rosterDict['wr'] is None:
                    team.rosterDict['wr'] = draftWrList.pop(0)
                elif team.rosterDict['te'] is None:
                    team.rosterDict['te'] = draftTeList.pop(0)
                elif team.rosterDict['k'] is None:
                    team.rosterDict['k'] = draftKList.pop(0)
            elif playerDraftList[0].position.value == 2 and team.rosterDict['rb'] is not None:
                if team.rosterDict['qb'] is None:
                    team.rosterDict['qb'] = draftQbList.pop(0)
                elif team.rosterDict['wr'] is None:
                    team.rosterDict['wr'] = draftWrList.pop(0)
                elif team.rosterDict['te'] is None:
                    team.rosterDict['te'] = draftTeList.pop(0)
                elif team.rosterDict['k'] is None:
                    team.rosterDict['k'] = draftKList.pop(0)
            elif playerDraftList[0].position.value == 3 and team.rosterDict['wr'] is not None:
                if team.rosterDict['qb'] is None:
                    team.rosterDict['qb'] = draftQbList.pop(0)
                elif team.rosterDict['rb'] is None:
                    team.rosterDict['rb'] = draftRbList.pop(0)
                elif team.rosterDict['te'] is None:
                    team.rosterDict['te'] = draftTeList.pop(0)
                elif team.rosterDict['k'] is None:
                    team.rosterDict['k'] = draftKList.pop(0)
            elif playerDraftList[0].position.value == 4 and team.rosterDict['te'] is not None:
                if team.rosterDict['qb'] is None:
                    team.rosterDict['qb'] = draftQbList.pop(0)
                elif team.rosterDict['rb'] is None:
                    team.rosterDict['rb'] = draftRbList.pop(0)
                elif team.rosterDict['wr'] is None:
                    team.rosterDict['wr'] = draftWrList.pop(0)
                elif team.rosterDict['k'] is None:
                    team.rosterDict['k'] = draftKList.pop(0)
            elif playerDraftList[0].position.value == 5 and team.rosterDict['k'] is not None:
                if team.rosterDict['qb'] is None:
                    team.rosterDict['qb'] = draftQbList.pop(0)
                elif team.rosterDict['rb'] is None:
                    team.rosterDict['rb'] = draftRbList.pop(0)
                elif team.rosterDict['wr'] is None:
                    team.rosterDict['wr'] = draftWrList.pop(0)
                elif team.rosterDict['te'] is None:
                    team.rosterDict['te'] = draftTeList.pop(0)

            #print('{0} took {1}, {2}, rated {3}'.format(team.name, pick.name, pick.position, pick.overallRating))
    for player in draftQbList:
        freeAgentList.append(player)
        player.team = 'Free Agent'
    for player in draftRbList:
        freeAgentList.append(player)
        player.team = 'Free Agent'
    for player in draftWrList:
        freeAgentList.append(player)
        player.team = 'Free Agent'
    for player in draftTeList:
        freeAgentList.append(player)
        player.team = 'Free Agent'
    for player in draftKList:
        freeAgentList.append(player)
        player.team = 'Free Agent'

    # print("\n")
    # print("\nFree Agents")
    # for player in playerDraftList:
    #     print("{0} | {1} | {2}".format(player.name, player.overallRating, player.position))

def savePlayerData():
    playerDict = {}
    tempPlayerDict = {}
    for x in range(len(playerList)):
        key = 'Player {}'.format(x + 1)
        newDict = tempPlayerDict.copy()
        newDict['name'] = playerList[x].name
        newDict['team'] = playerList[x].team
        newDict['position'] = playerList[x].position
        newDict['seasonsPlayed'] = playerList[x].seasonsPlayed
        newDict['attributes'] = playerList[x].attributes
        newDict['careerStats'] = playerList[x].careerStatsDict
        playerDict[key] = newDict

    dict = _prepare_for_serialization(playerDict)
    jsonFile = open("data/playerData.json", "w+") 
    jsonFile.write(json.dumps(dict, indent=4))
    jsonFile.close()

    
def getPlayers(_config):

    if os.path.exists("data/playerData.json"):
        with open('data/playerData.json') as jsonFile:
            playerData = json.load(jsonFile)
            for x in playerData:
                player = playerData[x]
                if player['position'] == 'QB':
                    newPlayer = PlayerQB()
                    newPlayer.attributes.skillRating = player['skillRating']
                    newPlayer.attributes.armStrength = player['armStrength']
                    newPlayer.attributes.accuracy = player['accuracy']
                elif player['position'] == 'RB':
                    newPlayer = PlayerRB()
                    newPlayer.attributes.skillRating = player['skillRating']
                elif player['position'] == 'WR':
                    newPlayer = PlayerWR()
                    newPlayer.attributes.skillRating = player['skillRating']
                elif player['position'] == 'TE':
                    newPlayer = PlayerTE()
                    newPlayer.attributes.skillRating = player['skillRating']
                elif player['position'] == 'K':
                    newPlayer = PlayerK()
                    newPlayer.attributes.skillRating = player['skillRating']
                    newPlayer.attributes.legStrength = player['legStrength']
                    newPlayer.attributes.accuracy = player['accuracy']

                newPlayer.name = player['name']
                newPlayer.attributes.overallRating = player['overallRating']
                newPlayer.attributes.speed = player['speed']
                newPlayer.attributes.hands = player['hands']
                newPlayer.attributes.agility = player['agility']
                newPlayer.attributes.power = player['power']
                newPlayer.careerStatsDict = player['careerStats']

                playerList.append(newPlayer)
        jsonFile.close()

    else:
        for x in _config['players']:
            y = randint(1,5)
            player = None
            if y == 1:
                player = PlayerQB()
            elif y == 2:
                player = PlayerRB()
            elif y == 3:
                player = PlayerWR()
            elif y == 4:
                player = PlayerTE()
            elif y == 5:
                player = PlayerK()
            player.name = x
            playerList.append(player)

def getTeams(_config):

    if os.path.exists("data/teamData.json"):
        with open('data/teamData.json') as jsonFile:
            teamData = json.load(jsonFile)
            for x in teamData:
                team = teamData[x]
                newTeam = Team(team['name'])
                newTeam.offenseRating = team['offenseRating']
                newTeam.runDefenseRating = team['runDefenseRating']
                newTeam.passDefenseRating = team['passDefenseRating']
                newTeam.defenseRating = team['defenseRating']
                newTeam.overallRating = team['overallRating']
                newTeam.allTimeTeamStats = team['allTimeTeamStats']

                teamRoster = team['rosterDict']
                for player in teamRoster.values():
                    for z in playerList:
                        if z.name == player['name']:
                            if z.position.value == 1:
                                newTeam.rosterDict['qb'] = z
                            elif z.position.value == 2:
                                newTeam.rosterDict['rb'] = z
                            elif z.position.value == 3:
                                newTeam.rosterDict['wr'] = z
                            elif z.position.value == 4:
                                newTeam.rosterDict['te'] = z
                            elif z.position.value == 5:
                                newTeam.rosterDict['k'] = z
                            break

                teamList.append(newTeam)

    else:
        for x in _config['teams']:
            team = Team(x)
            teamList.append(team)

def getDivisons(_config):

    if os.path.exists("data/divisionData.json"):
        with open('data/divisionData.json') as jsonFile:
            divisionData = json.load(jsonFile)
            for x in divisionData:
                division = Division(x)
                jteamList = divisionData[x]
                for team in jteamList:
                    for y in teamList:
                        if y.name == team:
                            division.teamList.append(y)
                            break
                divisionList.append(division)


    else:
        for x in _config['divisions']:
            division = Division(x)
            divisionList.append(division)

def initTeams():
    dict = {}
    y = 0

    for team in teamList:
        for player in team.rosterDict.values():
            player.team = team

    jsonFile = open("data/teamData.json", "w+")
    for team in teamList:
        team.setupTeam()
        y += 1
        dict[y] = _prepare_for_serialization(team)
        
    jsonFile.write(json.dumps(dict, indent=4))
    jsonFile.close()
        
def initDivisions():
    tempTeamList = teamList.copy()
    numOfDivisions = len(divisionList)
    y = 0
    while len(tempTeamList) > 0:
        x = randint(0,len(tempTeamList)-1)
        # if len(tempTeamList) % 2 == 0:
        #     divisionList[0].teamList.append(tempTeamList[x])
        # else:
        #     divisionList[1].teamList.append(tempTeamList[x])
        divisionList[y].teamList.append(tempTeamList[x])
        y += 1
        if y == numOfDivisions:
            y = 0
        tempTeamList.remove(tempTeamList[x])
    # for division in divisionList:
    #     print("\n{0} Division\n".format(division.name))
    #     for team in division.teamList:
    #         print(team.name)

def createSchedule():
    numOfWeeks = len(scheduleScheme)
    scheduleList.clear()
    for week in range(0, numOfWeeks):
        gameList = []
        numOfGames = int(len(teamList)/2)
        # print("\n-------------------------------------------------\n")
        # print("Week {0}".format(week + 1))
        for x in range(0, numOfGames):
            game = scheduleScheme[week][x]
            homeTeam = divisionList[int(game[0]) - 1].teamList[int(game[1]) - 1]
            awayTeam = divisionList[int(game[2]) - 1].teamList[int(game[3]) - 1]
            gameList.append(Game(homeTeam,awayTeam))
            # print("{0} v. {1}".format(awayTeam.name, homeTeam.name))
        scheduleList.append(gameList)

def getSeasonStats():
    dict = {}
    y = 0
    jsonFile = open("data/teamData.json", "w+")
    for team in teamList:

        for player in team.rosterDict.values():
            player.seasonsPlayed += 1
            if 'passComp' in player.seasonStatsDict and player.seasonStatsDict['passYards'] > 0:
                player.careerStatsDict['passAtt'] += player.seasonStatsDict['passAtt']
                player.careerStatsDict['passComp'] += player.seasonStatsDict['passComp']
                player.careerStatsDict['tds'] += player.seasonStatsDict['tds']
                player.careerStatsDict['ints'] += player.seasonStatsDict['ints']
                player.careerStatsDict['passYards'] += player.seasonStatsDict['passYards']
                player.careerStatsDict['totalYards'] += player.seasonStatsDict['passYards']
                player.careerStatsDict['ypc'] = round(player.careerStatsDict['passYards']/player.careerStatsDict['passComp'])
                player.careerStatsDict['passCompPerc'] = round((player.careerStatsDict['passComp']/player.careerStatsDict['passAtt'])*100)
                team.seasonTeamStats['Offense']['passYards'] += player.seasonStatsDict['passYards']
            if 'receptions' in player.seasonStatsDict and player.seasonStatsDict['rcvYards'] > 0:
                player.careerStatsDict['receptions'] += player.seasonStatsDict['receptions']
                player.careerStatsDict['passTargets'] += player.seasonStatsDict['passTargets']
                player.careerStatsDict['rcvYards'] += player.seasonStatsDict['rcvYards']
                player.careerStatsDict['tds'] += player.seasonStatsDict['tds']
                player.careerStatsDict['totalYards'] += player.seasonStatsDict['rcvYards']
                if player.careerStatsDict['receptions'] > 0:
                    player.careerStatsDict['ypr'] = round(player.careerStatsDict['rcvYards']/player.careerStatsDict['receptions'])
                    player.careerStatsDict['rcvPerc'] = round((player.careerStatsDict['receptions']/player.careerStatsDict['passTargets'])*100)
            if 'carries' in player.seasonStatsDict and player.seasonStatsDict['runYards'] > 0:
                player.careerStatsDict['carries'] += player.seasonStatsDict['carries']
                player.careerStatsDict['runYards'] += player.seasonStatsDict['runYards']
                player.careerStatsDict['tds'] += player.seasonStatsDict['tds']
                player.careerStatsDict['fumblesLost'] += player.seasonStatsDict['fumblesLost']
                player.careerStatsDict['totalYards'] += player.seasonStatsDict['runYards']
                player.careerStatsDict['ypc'] = round(player.careerStatsDict['runYards']/player.careerStatsDict['carries'])
                team.seasonTeamStats['Offense']['runYards'] += player.seasonStatsDict['runYards']
            if 'fgs' in player.seasonStatsDict:
                if player.seasonStatsDict['fgs'] > 0:
                    player.seasonStatsDict['fgPerc'] = round((player.seasonStatsDict['fgs']/player.seasonStatsDict['fgAtt'])*100)
                else:
                    player.seasonStatsDict['fgPerc'] = 0

                player.careerStatsDict['fgAtt'] += player.seasonStatsDict['fgAtt']
                player.careerStatsDict['fgs'] += player.seasonStatsDict['fgs']
                if player.careerStatsDict['fgs'] > 0:
                    player.careerStatsDict['fgPerc'] = round((player.careerStatsDict['fgs']/player.careerStatsDict['fgAtt'])*100)
                else:
                    player.careerStatsDict['fgPerc'] = 0
            if 'tds' in player.seasonStatsDict:
                team.seasonTeamStats['Offense']['tds'] += player.seasonStatsDict['tds']



        team.seasonTeamStats['Offense']['totalYards'] = team.seasonTeamStats['Offense']['passYards'] + team.seasonTeamStats['Offense']['runYards']
        team.allTimeTeamStats['wins'] += team.seasonTeamStats['wins']
        team.allTimeTeamStats['losses'] += team.seasonTeamStats['losses']
        team.allTimeTeamStats['Offense']['tds'] += team.seasonTeamStats['Offense']['tds']
        team.allTimeTeamStats['Offense']['passYards'] += team.seasonTeamStats['Offense']['passYards']
        team.allTimeTeamStats['Offense']['runYards'] += team.seasonTeamStats['Offense']['runYards']
        team.allTimeTeamStats['Offense']['totalYards'] += team.seasonTeamStats['Offense']['totalYards']
        team.allTimeTeamStats['Defense']['sacks'] += team.seasonTeamStats['Defense']['sacks']
        team.allTimeTeamStats['Defense']['ints'] += team.seasonTeamStats['Defense']['ints']
        team.allTimeTeamStats['Defense']['fumRec'] += team.seasonTeamStats['Defense']['fumRec']
        team.allTimeTeamStats['winPerc'] = round(team.allTimeTeamStats['wins']/(team.allTimeTeamStats['wins']+team.allTimeTeamStats['losses']),3)


        y += 1
        dict[y] = _prepare_for_serialization(team)

    jsonFile.write(json.dumps(dict, indent=4))
    jsonFile.close()

    savePlayerData()

def clearSeasonStats():
    for team in teamList:
        team.seasonTeamStats = copy.deepcopy(teamStatsDict)

        team.rosterDict['qb'].seasonStatsDict = copy.deepcopy(qbStatsDict)
        team.rosterDict['rb'].seasonStatsDict = copy.deepcopy(rbStatsDict)
        team.rosterDict['wr'].seasonStatsDict = copy.deepcopy(wrStatsDict)
        team.rosterDict['te'].seasonStatsDict = copy.deepcopy(wrStatsDict)
        team.rosterDict['k'].seasonStatsDict = copy.deepcopy(kStatsDict)

def startSeason():
    weekDict = {}
    seasonDict = {}
    gameDictTemp = {}
    currentSeason = seasonsPlayed + 1
    strCurrentSeason = 'season{}'.format(currentSeason)

    weekFilePath = '{}/games'.format(strCurrentSeason)
    if os.path.isdir(weekFilePath):
        for f in os.listdir(weekFilePath):
            os.remove(os.path.join(weekFilePath, f))
    else:
        os.mkdir(weekFilePath)

    for week in scheduleList:
        #print("\n-------------------------------------------------\n")
        #print("Week {0}".format(scheduleList.index(week)+1))
        currentWeek = 'Week {}'.format(scheduleList.index(week)+1)
        gameDict = gameDictTemp.copy()
        for game in range(0,len(week)):
            strGame = 'Game {}'.format(game + 1)
            week[game].playGame()  
            week[game].postgame()
            week[game].saveGameData()
            gameResults = week[game].gameDict
            gameDict[strGame] = gameResults
        weekDict = _prepare_for_serialization(gameDict)
        jsonFile = open(os.path.join(weekFilePath, '{}.json'.format(currentWeek)), "w+")
        jsonFile.write(json.dumps(weekDict, indent=4))
        jsonFile.close()
    
    for team in teamList:
        team.seasonTeamStats['winPerc'] = round((team.seasonTeamStats['wins']/(team.seasonTeamStats['wins'] + team.seasonTeamStats['losses'])),3)

    #seasonDict['games'] = weekDict
    postseason = Postseason(strCurrentSeason)
    leagueChampion = postseason.playPlayoffs()

    getSeasonStats()

    standingsDict = {}
    divStandingsTempDict = {}
    jsonFile = open("data/divisionData.json", "w+")
    for division in divisionList:
        list.sort(division.teamList, key=lambda team: team.seasonTeamStats['winPerc'], reverse=True)
        divStandingsDict = divStandingsTempDict.copy()
        #print("\n{0} Division".format(division.name))
        for team in division.teamList:
            divStandingsDict[team.name] = '{0} - {1}'.format(team.seasonTeamStats['wins'], team.seasonTeamStats['losses'])
        standingsDict[division.name] = divStandingsDict

    jsonFile.write(json.dumps(standingsDict, indent=4))
    jsonFile.close()

    seasonDict['standings'] = standingsDict
    seasonDict['champion'] = leagueChampion.name

    _serialzedDict = _prepare_for_serialization(seasonDict)

    if os.path.isdir(strCurrentSeason):
        for f in os.listdir(strCurrentSeason):
            if os.path.isfile(os.path.join(strCurrentSeason, f)):
                os.remove(os.path.join(strCurrentSeason, f))
    else:
        os.mkdir(strCurrentSeason)
    jsonFile = open(os.path.join(strCurrentSeason, 'seasonData.json'), "w+")
    jsonFile.write(json.dumps(_serialzedDict, indent=4))
    jsonFile.close()

    teamDict = {}
    for team in teamList:
        teamDict[team.name] = _prepare_for_serialization(team)
    
    jsonFile = open(os.path.join(strCurrentSeason, 'teamData.json'), "w+")
    jsonFile.write(json.dumps(teamDict, indent=4))
    jsonFile.close()

    clearSeasonStats()

    
def offseason():
    for player in playerList:
        player.offseasonTraining()
        player.attributes.calculateIntangibles()
        player.updateRating()

    list.sort(teamList, key=lambda team: team.seasonTeamStats['winPerc'], reverse=False)

    freeAgencyRound = 0
    while freeAgencyRound < config['leagueConfig']['freeAgencyRounds']:
        for team in teamList:
            team.offseasonMoves()
        freeAgencyRound += 1

    for team in teamList:
            team.updateDefense()
            team.updateRating()
    

def getConfig():
    fileObjext = open("config.json", "r")
    jsonContent = fileObjext.read()
    config = json.loads(jsonContent)
    fileObjext.close()
    return config

def init():
    global seasonsPlayed
    global totalSeasons
    global config

    config = getConfig()
    totalSeasons = config['leagueConfig']['seasons']
    deleteDataOnStart = config['leagueConfig']['deleteDataOnRestart']

    if os.path.isdir('data'):
        if deleteDataOnStart:
            for f in os.listdir('data'):
                os.remove(os.path.join('data', f))
    else:
        os.mkdir('data')

    getPlayers(config)
    getTeams(config)

    if not os.path.exists("data/teamData.json"):
        draft()

    initTeams()
    savePlayerData()
    getDivisons(config)
    if not os.path.exists("data/divisionData.json"):
        initDivisions()

    
    while seasonsPlayed < totalSeasons:
        createSchedule()
        startSeason()
        offseason()
        seasonsPlayed += 1

init()