import enum
import  json
import os
from random import randint
import statistics



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

playerList = []
teamList = []
divisionList = []   
scheduleList = []
scheduleScheme = [
    ('1112','1314','2122','2324'),
    ('1311','1412','2321','2422'),
    ('1114','1213','2124','2223'),
    ('1121','1222','1323','1424'),
    ('2112','2211','2314','2413'),
    ('1123','1224','1321','1422'),
    ('2114','2213','2312','2411'),
    ('1211','1413','2221','2423'),
    ('1113','1214','2123','2224'),
    ('1411','1312','2421','2322')]


def _prepare_for_serialization(obj):
    serialized_dict = dict()
    for k, v in obj.__dict__.items():
        if v != 0:
            if isinstance(v, list):
                listDict = {}
                y = 0
                for item in v:
                    y += 1
                    listDict[y] = _prepare_for_serialization(item)
                serialized_dict[k] = listDict
            else: 
                serialized_dict[k] = v.name if isinstance(v, Position) else v
    return serialized_dict                    

def getStat():
    x = randint(1,100)
    if x >= 97:
        return randint(95, 100)
    elif x < 97 and x >= 75:
        return randint(90, 94)
    elif x < 75 and x >= 25:
        return randint(80, 89)
    else:
        return randint(70, 79)

class Division:
    def __init__(self, name):
        self.name = name
        self.teamList = []

class Team:
    def __init__(self, name):
        self.name = name
        self.offenseRating = 0
        self.runDefenseRating = 0
        self.passDefenseRating = 0
        self.defenseRating = 0
        self.overallRating = 0

        self.wins = 0
        self.losses = 0
        self.winPercent = 0
        self.sacks = 0
        self.touchdowns = 0
        self.interceptions = 0
        self.fumbleRecoveries = 0
        self.passYards = 0
        self.runYards = 0
        self.totalYards = 0

        self.qbList = []
        self.rbList = []
        self.wrList = []
        self.teList = []
        self.kList = []
        self.teamRoster = []
        self.startersList = []

    def setupTeam(self):
        self.startersList.append(self.qbList[0])
        self.startersList.append(self.rbList[0])
        self.startersList.append(self.wrList[0])
        self.startersList.append(self.wrList[1])
        self.startersList.append(self.teList[0])
        self.startersList.append(self.kList[0])

        
        if self.overallRating == 0:
            count = 0
            rating = 0

            for player in self.startersList:
                rating += player.overallRating 
                count += 1

            self.offenseRating = round(rating/count)
            self.runDefenseRating = getStat()
            self.passDefenseRating = getStat()
            self.defenseRating = round(statistics.mean([self.runDefenseRating, self.passDefenseRating]))
            self.overallRating = round(statistics.mean([self.offenseRating, self.runDefenseRating, self.passDefenseRating]))

class Player:
    def __init__(self):
        self.position = None
        self.name = ''
        self.team = "Free Agent"
        self.overallRating = 0
        self.speed = getStat()
        self.hands = getStat()
        self.agility = getStat()
        self.power = getStat()
        self.startingConfidence = 0
        self.confidence = 0
        self.focus = 0
        self.energy = 100

class PlayerQB(Player):
    def __init__(self):
        super().__init__()
        self.position = Position.QB
        self.armStrength = getStat()
        self.accuracy = getStat()
        self.qbRating = round((self.armStrength + self.accuracy + self.agility)/3)
        self.overallRating = self.qbRating
        self.startingConfidence = self.overallRating
        self.confidence = self.overallRating

        self.gamePassAttempts = 0
        self.gamePassCompletions = 0
        self.gameCompPercent = 0
        self.gameTouchdowns = 0
        self.gameIntsThrown = 0
        self.gamePassYards = 0
        self.gameYardsPerCompletion = 0

        self.passAttempts = 0
        self.passCompletions = 0
        self.compPercent = 0
        self.touchdowns = 0
        self.intsThrown = 0
        self.passYards = 0
        self.yardsPerCompletion = 0
        self.totalYards = 0

    def calculateRating(self):
        self.qbRating = round((self.armStrength + self.accuracy + self.agility + self.confidence)/4)

class PlayerRB(Player):
    def __init__(self):
        super().__init__()
        self.position = Position.RB

        self.rbRating = round((self.speed + self.power + self.agility)/3)
        self.overallRating = self.rbRating
        self.startingConfidence = self.overallRating
        self.confidence = self.overallRating

        self.gameCarries = 0
        self.gameReceptions = 0
        self.gamePassTargets = 0
        self.gameRvcPercent = 0
        self.gameTouchdowns = 0
        self.gameFumblesLost = 0
        self.gameRcvYards = 0
        self.gameRunYards = 0
        self.gameTotalYards = 0
        self.gameYardsPerCarry = 0

        self.carries = 0
        self.receptions = 0
        self.passTargets = 0
        self.rvcPercent = 0
        self.rcvYards = 0
        self.runYards = 0
        self.totalYards = 0
        self.yardsPerCarry = 0
        self.touchdowns = 0
        self.fumblesLost = 0
        self.yardsPerReception = 0
        self.totalYards = 0

    def calculateRating(self):
        self.rbRating = round((self.speed + self.power + self.agility + self.confidence)/4)

class PlayerWR(Player):
    def __init__(self):
        super().__init__()
        self.position = Position.WR

        self.wrRating = round((self.speed + self.hands + self.agility)/3)
        self.overallRating = self.wrRating
        self.startingConfidence = self.overallRating
        self.confidence = self.overallRating

        self.gameReceptions = 0
        self.gamePassTargets = 0
        self.gameRvcPercent = 0
        self.gameTouchdowns = 0
        self.gameRcvYards = 0
        self.gameTotalYards = 0
        self.gameYardsPerReception = 0

        self.receptions = 0
        self.passTargets = 0
        self.rvcPercent = 0
        self.rcvYards = 0
        self.totalYards = 0
        self.touchdowns = 0
        self.yardsPerReception = 0
        self.totalYards = 0

    def calculateRating(self):
        self.wrRating = round((self.speed + self.hands + self.agility + self.confidence)/4)

class PlayerTE(Player):
    def __init__(self):
        super().__init__()
        self.position = Position.TE

        self.teRating = round((self.power + self.hands + self.agility)/3)
        self.overallRating = self.teRating
        self.startingConfidence = self.overallRating
        self.confidence = self.overallRating

        self.gameReceptions = 0
        self.gamePassTargets = 0
        self.gameRvcPercent = 0
        self.gameTouchdowns = 0
        self.gameRcvYards = 0
        self.gameTotalYards = 0
        self.gameYardsPerReception = 0

        self.receptions = 0
        self.passTargets = 0
        self.rvcPercent = 0
        self.rcvYards = 0
        self.totalYards = 0
        self.touchdowns = 0
        self.yardsPerReception = 0
        self.totalYards = 0

    def calculateRating(self):
        self.teRating = round((self.power + self.hands + self.agility + self.confidence)/4)

class PlayerK(Player):
    def __init__(self):
        super().__init__()
        self.position = Position.K

        self.legStrength = getStat()
        self.accuracy = getStat()
        self.kRating = round((self.legStrength + self.power + self.accuracy)/3)
        self.overallRating = self.kRating
        self.startingConfidence = self.overallRating
        self.confidence = self.overallRating

        self.gameFgAttempts = 0
        self.gameFieldGoals = 0
        self.gameFgPercent = 0

        self.fgAttempts = 0
        self.fieldGoals = 0
        self.fgPercent = 0
        self.totalYards = 0

    def calculateRating(self):
        self.kRating = round((self.legStrength + self.power + self.accuracy + self.confidence)/4)

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

    def fieldGoalTry(self, offense):
        kicker = offense.kList[0]
        kicker.gameFgAttempts += 1
        yardsToFG = self.yardsToEndzone + 10
        x = randint(1,100)
        if yardsToFG <= 35:
            if (kicker.kRating + 10) >= x:
                fgSuccess = True
                kicker.gameFieldGoals += 1
            else:
                fgSuccess = False
        elif yardsToFG > 35 and yardsToFG <= 50:
            if (kicker.kRating) >= x:
                fgSuccess = True
                kicker.gameFieldGoals += 1
            else:
                fgSuccess = False
        else:
            if (kicker.kRating - 10) >= x:
                fgSuccess = True
                kicker.gameFieldGoals += 1
            else:
                fgSuccess = False
        self.lastPlay.insert(0, PlayType.FieldGoal)
        self.lastPlay.insert(1, kicker)
        self.lastPlay.insert(2, '')
        self.lastPlay.insert(3, 0)
        return fgSuccess

    def extraPointTry(self, offense):
        kicker = offense.kList[0]
        x = randint(1,100)
        if (kicker.kRating + 10) >= x:
            fgSuccess = True
        else:
            fgSuccess = False
        return fgSuccess

    def runPlay(self, offense, defense):
        runner = offense.rbList[0]
        runner.focus = round(((runner.confidence + runner.energy)/2),2)
        blocker1 = offense.teList[0]
        blocker2 = offense.rbList[1]
        yardage = 0
        x = randint(1,100)
        fumbleRoll = randint(1,100)
        playStrength = (((runner.rbRating - (100 - runner.energy) + runner.confidence)/2) + blocker1.power + blocker2.power)/3
        if defense.runDefenseRating >= playStrength:
            if (fumbleRoll/runner.focus) < 1.20:
                if x < 20:
                    yardage = randint(-2,0)
                elif x >= 20 and x <= 70:
                    yardage = randint(0,3)
                elif x > 70 and x <= 99:
                    yardage = randint(4,7)
                else:
                    if self.yardsToEndzone < 7:
                        yardage = randint(0, self.yardsToEndzone)
                    else:
                        yardage = randint(7, self.yardsToEndzone)
            else:
                #fumble
                yardage = 1004
                runner.gameCarries += 1
                runner.gameFumblesLost += 1
                runner.confidence = round(runner.confidence - 1, 2)
                defense.fumbleRecoveries += 1
                self.lastPlay.insert(0, PlayType.Run)
                self.lastPlay.insert(1, runner) 
                self.lastPlay.insert(2, '')
                self.lastPlay.insert(3, yardage)
                return yardage

        else:
            if (fumbleRoll/runner.focus) < 1.15:
                if x < 50:
                    yardage = randint(0,3)
                elif x >= 50 and x < 85:
                    yardage = randint(4,7)
                elif x >= 85 and x < 90:
                    yardage = randint(8,10)
                elif x >= 90 and x <= 95:
                    yardage = randint(11,20)
                else:
                    if self.yardsToEndzone < 20:
                        yardage = randint(0, self.yardsToEndzone)
                    else:
                        yardage = randint(20, self.yardsToEndzone)
            else:
                #fumble
                yardage = 1004
                runner.gameCarries += 1
                runner.gameFumblesLost += 1
                runner.confidence = round(runner.confidence - 1, 2)
                defense.fumbleRecoveries += 1
                self.lastPlay.insert(0, PlayType.Run)
                self.lastPlay.insert(1, runner) 
                self.lastPlay.insert(2, '')
                self.lastPlay.insert(3, yardage)
                return yardage

        if yardage > self.yardsToEndzone:
            yardage = self.yardsToEndzone

        runner.gameRunYards += yardage
        runner.gameCarries += 1
        runner.energy = round(runner.energy - (yardage/10),2)
        runner.confidence = round(runner.confidence + (yardage/125), 2)
        self.lastPlay.insert(0, PlayType.Run)
        self.lastPlay.insert(1, runner) 
        self.lastPlay.insert(2, '')
        self.lastPlay.insert(3, yardage)
        return yardage

    def passPlay(self, offense, defense, passType):
        passer = offense.qbList[0]
        rb = offense.rbList[0]
        wr = offense.wrList[randint(0,1)]
        te = offense.teList[0]
        receiver = ''
        passer.focus = round(((passer.confidence + passer.energy)/2),2)
        sackRoll = randint(1,1000)
        sackModifyer = defense.passDefenseRating/passer.agility

        if sackRoll < round(100 * (sackModifyer)):
            yardage = round(-(randint(0,10) * sackModifyer))
            # print("\n{0} sacked {1} for {2} yard(s)".format(defense.name, passer.name, yardage))
            defense.sacks += 1
            passer.energy -= 2
            self.lastPlay.insert(0, PlayType.Pass)
            self.lastPlay.insert(1, passer) 
            self.lastPlay.insert(2, '')
            self.lastPlay.insert(3, 1004)
            return yardage
        else:
            passer.gamePassAttempts += 1
            passTarget = randint(1,10)

            if passType.value == 1:
                if passTarget < 3:
                    receiver = rb   
                elif passTarget >= 3 and passTarget < 9:
                    receiver = wr
                else:
                    receiver = te
                passer.energy = round(passer.energy - .1, 2)
                accRoll = randint(1,100)
                if accRoll < ((passer.accuracy + passer.focus)/2) - (defense.passDefenseRating/12):
                    dropRoll = round(randint(1,100) + (defense.passDefenseRating/10))
                    if receiver.hands > dropRoll:
                        passYards = randint(0,4)
                        yac = 0
                        x = randint(1,10)
                        if ((receiver.agility + receiver.speed)/2) > defense.defenseRating:
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
                        passer.gamePassYards += yardage
                        passer.gamePassCompletions += 1
                        passer.confidence = round(passer.confidence + .05, 2) 
                        receiver.gamePassTargets += 1
                        receiver.gameReceptions += 1
                        receiver.gameRcvYards += yardage
                        receiver.energy = round(receiver.energy - (yardage/5),2)
                        receiver.confidence = round(receiver.confidence + (yardage/125), 2)
                        self.lastPlay.insert(0, PlayType.Pass)
                        self.lastPlay.insert(1, passer) 
                        self.lastPlay.insert(2, receiver)
                        self.lastPlay.insert(3, yardage)

                        return yardage
                    else:
                        # print("\n{0}'s pass to {1} is incomplete".format(passer.name, receiver.name))
                        yardage = 0
                        receiver.gamePassTargets += 1   
                        receiver.confidence = round(receiver.confidence - .5, 2)                  
                        self.lastPlay.insert(0, PlayType.Pass)
                        self.lastPlay.insert(1, passer) 
                        self.lastPlay.insert(2, receiver)
                        self.lastPlay.insert(3, yardage)
                        return yardage

                else:
                    interceptRoll = randint(1,100)
                    if interceptRoll <= 5:
                        # print("\n{0} defense has intercepted {1}'s pass!".format(defense.name, passer.name))
                        yardage = 1003
                        passer.gameIntsThrown += 1
                        passer.confidence = round(passer.confidence - 1, 2) 
                        defense.interceptions += 1
                        self.lastPlay.insert(0, PlayType.Pass)
                        self.lastPlay.insert(1, passer) 
                        self.lastPlay.insert(2, receiver)
                        self.lastPlay.insert(3, yardage)
                        return yardage
                    else:
                        # print("\n{0}'s pass to {1} is incomplete".format(passer.name, receiver.name))
                        yardage = 0
                        passer.confidence = round(passer.confidence - .5, 2) 
                        self.lastPlay.insert(0, PlayType.Pass)
                        self.lastPlay.insert(1, passer) 
                        self.lastPlay.insert(2, receiver)
                        self.lastPlay.insert(3, yardage)
                        return yardage


            elif passType.value == 2:
                if passTarget < 3:
                    receiver = rb   
                elif passTarget >= 3 and passTarget < 5:
                    receiver = te
                else:
                    receiver = wr
                passer.energy = round(passer.energy - .1, 2)
                accRoll = randint(1,100)
                if accRoll < (((passer.accuracy + passer.armStrength + passer.focus)/3) - (defense.passDefenseRating/8)):
                    dropRoll = round(randint(1,100) + (defense.passDefenseRating/10))
                    if receiver.hands > dropRoll:
                        passYards = randint(5,10)
                        yac = 0
                        x = randint(1,10)
                        if ((receiver.agility + receiver.speed)/2) > defense.defenseRating:
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
                        passer.gamePassYards += yardage
                        passer.gamePassCompletions += 1
                        passer.confidence = round(passer.confidence + .1, 2) 
                        receiver.gamePassTargets += 1
                        receiver.gameReceptions += 1
                        receiver.gameRcvYards += yardage
                        receiver.energy = round(receiver.energy - (yardage/5),2)
                        receiver.confidence = round(receiver.confidence + (yardage/125), 2)
                        self.lastPlay.insert(0, PlayType.Pass)
                        self.lastPlay.insert(1, passer) 
                        self.lastPlay.insert(2, receiver)
                        self.lastPlay.insert(3, yardage)
                        return yardage
                    else:
                        # print("\n{0}'s pass to {1} is incomplete".format(passer.name, receiver.name))
                        yardage = 0
                        receiver.gamePassTargets += 1
                        receiver.confidence = round(receiver.confidence - .5, 2)                   
                        self.lastPlay.insert(0, PlayType.Pass)
                        self.lastPlay.insert(1, passer) 
                        self.lastPlay.insert(2, receiver)
                        self.lastPlay.insert(3, yardage)
                        return yardage
                else:
                    interceptRoll = randint(1,100)
                    if interceptRoll <= 5:
                        # print("\n{0} defense has intercepted {1}'s pass!".format(defense.name, passer.name))
                        yardage = 1003
                        passer.gameIntsThrown += 1
                        passer.confidence = round(passer.confidence - 1, 2) 
                        defense.interceptions += 5
                        self.lastPlay.insert(0, PlayType.Pass)
                        self.lastPlay.insert(1, passer) 
                        self.lastPlay.insert(2, receiver)
                        self.lastPlay.insert(3, yardage)
                        return yardage
                    else:
                        # print("\n{0}'s pass to {1} is incomplete".format(passer.name, receiver.name))
                        yardage = 0   
                        passer.confidence = round(passer.confidence - .5, 2)                 
                        self.lastPlay.insert(0, PlayType.Pass)
                        self.lastPlay.insert(1, passer) 
                        self.lastPlay.insert(2, receiver)
                        self.lastPlay.insert(3, yardage)
                        return yardage

            elif passType.value == 3:
                if passTarget < 3:
                    receiver = te   
                else:
                    receiver = wr
                passer.energy = round(passer.energy - .1, 2)
                accRoll = randint(1,100)
                if accRoll < (((passer.accuracy + passer.armStrength + passer.focus)/3) - (defense.passDefenseRating/5)):
                    dropRoll = round(randint(1,100) + (defense.passDefenseRating/10))
                    if receiver.hands > dropRoll:
                        passYards = randint(11,20)
                        yac = 0
                        x = randint(1,10)
                        if ((receiver.agility + receiver.speed)/2) > defense.defenseRating:
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
                        passer.gamePassYards += yardage
                        passer.gamePassCompletions += 1
                        passer.confidence = round(passer.confidence + .2, 2) 
                        receiver.gamePassTargets += 1
                        receiver.gameReceptions += 1
                        receiver.gameRcvYards += yardage
                        receiver.energy = round(receiver.energy - (yardage/5),2)
                        receiver.confidence = round(receiver.confidence + (yardage/125), 2)
                        self.lastPlay.insert(0, PlayType.Pass)
                        self.lastPlay.insert(1, passer) 
                        self.lastPlay.insert(2, receiver)
                        self.lastPlay.insert(3, yardage)
                        return yardage
                    else:
                        # print("\n{0}'s pass to {1} is incomplete".format(passer.name, receiver.name))
                        yardage = 0
                        receiver.gamePassTargets += 1  
                        receiver.confidence = round(receiver.confidence - .5, 2)                      
                        self.lastPlay.insert(0, PlayType.Pass)
                        self.lastPlay.insert(1, passer) 
                        self.lastPlay.insert(2, receiver)
                        self.lastPlay.insert(3, yardage)
                        return yardage
                else:
                    interceptRoll = randint(1,100)
                    if interceptRoll <= 5:
                        # print("\n{0} defense has intercepted {1}'s pass!".format(defense.name, passer.name))
                        yardage = 1003
                        passer.gameIntsThrown += 1
                        passer.confidence = round(passer.confidence - 1, 2) 
                        defense.interceptions += 1
                        self.lastPlay.insert(0, PlayType.Pass)
                        self.lastPlay.insert(1, passer) 
                        self.lastPlay.insert(2, receiver)
                        self.lastPlay.insert(3, yardage)
                        return yardage
                    else:
                        # print("\n{0}'s pass to {1} is incomplete".format(passer.name, receiver.name))
                        yardage = 0        
                        passer.confidence = round(passer.confidence - .5, 2)        
                        self.lastPlay.insert(0, PlayType.Pass)
                        self.lastPlay.insert(1, passer) 
                        self.lastPlay.insert(2, receiver)
                        self.lastPlay.insert(3, yardage)
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
                        self.lastPlay.insert(0, PlayType.Punt)
                        self.lastPlay.insert(1, '')
                        self.lastPlay.insert(2, '')
                        self.lastPlay.insert(3, 1002)
                        return 1002
                    elif x >= 7 and x < 9:
                        return self.passPlay(offense, defense, PassType.short)
                    else:
                        return self.passPlay(offense, defense, PassType.medium)
                else:
                    x = randint(1,10)
                    if x < 10:
                        self.lastPlay.insert(0, PlayType.Punt)
                        self.lastPlay.insert(1, '')
                        self.lastPlay.insert(2, '')
                        self.lastPlay.insert(3, 1002)
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
        for player in self.homeTeam.startersList:
            # print('\n{0} | {1} | {2}'.format(player.name, player.position.name, player.overallRating))

            player.energy += 25
            if player.energy > 100:
                player.energy = 100

            player.calculateRating()

            if player.position.value == 1:
                # print('Pass Attempts: {0} | Pass Completions: {1} | Yards Passing: {2} | Touchdowns: {3} | Interceptions: {4}'.format(player.gamePassAttempts, player.gamePassCompletions, player.gamePassYards, player.gameTouchdowns, player.gameIntsThrown))
                player.passAttempts += player.gamePassAttempts
                player.passCompletions += player.gamePassCompletions
                player.passYards += player.gamePassYards
                player.totalYards += player.gamePassYards
                player.intsThrown += player.gameIntsThrown
                player.touchdowns += player.gameTouchdowns

                player.gamePassAttempts = 0
                player.gamePassCompletions = 0
                player.gamePassYards = 0
                player.gameIntsThrown = 0
                player.gameTouchdowns = 0

            elif player.position.value == 2:
                # print('Carries: {0} | Yards Rushing: {1} | Pass Targets: {2} | Receptions: {3} | Yards Receiving: {4} | Touchdowns: {5}'.format(player.gameCarries, player.gameRunYards, player.gamePassTargets, player.gameReceptions, player.gameRcvYards, player.gameTouchdowns))
                player.carries += player.gameCarries
                player.receptions += player.gameReceptions
                player.passTargets += player.gamePassTargets
                player.rcvYards += player.gameRcvYards
                player.runYards += player.gameRunYards
                player.fumblesLost += player.gameFumblesLost
                player.totalYards += (player.gameRcvYards + player.gameRunYards)
                player.touchdowns += player.gameTouchdowns

                player.gameCarries = 0
                player.gameFumblesLost = 0
                player.gameReceptions = 0
                player.gamePassTargets = 0
                player.gameTouchdowns = 0
                player.gameRcvYards = 0
                player.gameRunYards = 0

            elif player.position.value == 3 or player.position.value == 4:
                # print('Pass Targets: {0} | Receptions: {1} | Yards Receiving: {2} | Touchdowns: {3}'.format(player.gamePassTargets, player.gameReceptions, player.gameRcvYards, player.gameTouchdowns))
                player.receptions += player.gameReceptions
                player.passTargets += player.gamePassTargets
                player.rcvYards += player.gameRcvYards
                player.totalYards += player.gameRcvYards
                player.touchdowns += player.gameTouchdowns

                player.gameReceptions = 0
                player.gamePassTargets = 0
                player.gameTouchdowns = 0
                player.gameRcvYards = 0

            elif player.position.value == 5:
                # print('FG Attempts: {0} | FGs: {1}'.format(player.gameFgAttempts, player.gameFieldGoals))
                player.fgAttempts += player.gameFgAttempts
                player.fieldGoals += player.gameFieldGoals
                player.gameFgAttempts = 0
                player.gameFieldGoals = 0



        # print('\n{0} Player Stats'.format(self.awayTeam.name))    
        for player in self.awayTeam.startersList:
            # print('\n{0} | {1} | {2}'.format(player.name, player.position.name, player.overallRating))

            player.energy += 25
            if player.energy > 100:
                player.energy = 100

            player.calculateRating()

            if player.position.value == 1:
                # print('Pass Attempts: {0} | Pass Completions: {1} | Yards Passing: {2} | Touchdowns: {3} | Interceptions: {4}'.format(player.gamePassAttempts, player.gamePassCompletions, player.gamePassYards, player.gameTouchdowns, player.gameIntsThrown))
                player.passAttempts += player.gamePassAttempts
                player.passCompletions += player.gamePassCompletions
                player.passYards += player.gamePassYards
                player.totalYards += player.gamePassYards
                player.intsThrown += player.gameIntsThrown
                player.touchdowns += player.gameTouchdowns

                player.gamePassAttempts = 0
                player.gamePassCompletions = 0
                player.gamePassYards = 0
                player.gameIntsThrown = 0
                player.gameTouchdowns = 0

            elif player.position.value == 2:
                # print('Carries: {0} | Yards Rushing: {1} | Pass Targets: {2} | Receptions: {3} | Yards Receiving: {4} | Touchdowns: {5}'.format(player.gameCarries, player.gameRunYards, player.gamePassTargets, player.gameReceptions, player.gameRcvYards, player.gameTouchdowns))
                player.carries += player.gameCarries
                player.receptions += player.gameReceptions
                player.passTargets += player.gamePassTargets
                player.rcvYards += player.gameRcvYards
                player.runYards += player.gameRunYards
                player.totalYards += (player.gameRcvYards + player.gameRunYards)
                player.touchdowns += player.gameTouchdowns

                player.gameCarries = 0
                player.gameReceptions = 0
                player.gamePassTargets = 0
                player.gameTouchdowns = 0
                player.gameRcvYards = 0
                player.gameRunYards = 0

            elif player.position.value == 3 or player.position.value == 4:
                # print('Pass Targets: {0} | Receptions: {1} | Yards Receiving: {2} | Touchdowns: {3}'.format(player.gamePassTargets, player.gameReceptions, player.gameRcvYards, player.gameTouchdowns))
                player.receptions += player.gameReceptions
                player.passTargets += player.gamePassTargets
                player.rcvYards += player.gameRcvYards
                player.totalYards += player.gameRcvYards
                player.touchdowns += player.gameTouchdowns

                player.gameReceptions = 0
                player.gamePassTargets = 0
                player.gameTouchdowns = 0
                player.gameRcvYards = 0

            elif player.position.value == 5:
                # print('FG Attempts: {0} | FGs: {1}'.format(player.gameFgAttempts, player.gameFieldGoals))
                player.fgAttempts += player.gameFgAttempts
                player.fieldGoals += player.gameFieldGoals
                player.gameFgAttempts = 0
                player.gameFieldGoals = 0

    def playGame(self):
        print("\n----------------------------------------------------------------------------------------")
        # print("\nGame Start: {0}[OAR:{1}|OR:{2}|RDR:{3}|PDR:{4}] v. {5}[OAR:{6}|OR:{7}|RDR:{8}|PDR:{9}])".format(self.awayTeam.name, self.awayTeam.overallRating, self.awayTeam.offenseRating, self.awayTeam.runDefenseRating, self.awayTeam.passDefenseRating, self.homeTeam.name, self.homeTeam.overallRating, self.homeTeam.offenseRating, self.homeTeam.runDefenseRating, self.homeTeam.passDefenseRating))
        self.totalPlays = 0
        possReset = 80
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
                if self.totalPlays == 132 and self.homeScore != self.awayScore:
                    break
                self.lastPlay.clear()
                # print("\nDOWN: {0}".format(self.down))
                yardsGained = self.playCaller(self.offensiveTeam, self.defensiveTeam)
                self.totalPlays += 1

                if yardsGained == 1001:
                    if self.fieldGoalTry(self.offensiveTeam):
                        if self.offensiveTeam == self.homeTeam:
                            self.homeScore += 3
                        elif self.offensiveTeam == self.awayTeam:
                            self.awayScore += 3
                        # print("\n{0} field goal is GOOD. KICKER: {1}".format(self.offensiveTeam.name,self.lastPlay[1].name))
                        # self.scoreChange()
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
                        if self.lastPlay[0].value == 1:
                            self.lastPlay[1].gameTouchdowns += 1
                            self.lastPlay[1].confidence += 1
                            # print("\n{0} TOUCHDOWN. {1} yard run by {2}".format(self.offensiveTeam.name, yardsGained, self.lastPlay[1].name))
                        elif self.lastPlay[0].value == 2:
                            self.lastPlay[1].gameTouchdowns += 1
                            self.lastPlay[2].gameTouchdowns += 1
                            self.lastPlay[1].confidence += 1
                            self.lastPlay[2].confidence += 1
                            # print("\n{0} TOUCHDOWN. {1} yard pass from {2} to {3}".format(self.offensiveTeam.name, yardsGained, self.lastPlay[1].name, self.lastPlay[2].name))

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
            self.awayTeam.wins += 1
            self.homeTeam.losses += 1
            print("\nRESULT: {0}[OAR:{1}|OR:{2}|RDR:{3}|PDR:{4}] def. {5}[OAR:{6}|OR:{7}|RDR:{8}|PDR:{9}]).".format(self.winningTeam.name, self.winningTeam.overallRating, self.winningTeam.offenseRating, self.winningTeam.runDefenseRating, self.winningTeam.passDefenseRating, self.losingTeam.name, self.losingTeam.overallRating, self.losingTeam.offenseRating, self.losingTeam.runDefenseRating, self.losingTeam.passDefenseRating))
            print("SCORE: {0}-{1}".format(self.awayScore, self.homeScore))
        elif self.homeScore > self.awayScore:
            self.winningTeam = self.homeTeam
            self.losingTeam = self.awayTeam
            self.homeTeam.wins += 1
            self.awayTeam.losses += 1
            print("\nRESULT: {0}[OAR:{1}|OR:{2}|RDR:{3}|PDR:{4}] def. {5}[OAR:{6}|OR:{7}|RDR:{8}|PDR:{9}]).".format(self.winningTeam.name, self.winningTeam.overallRating, self.winningTeam.offenseRating, self.winningTeam.runDefenseRating, self.winningTeam.passDefenseRating, self.losingTeam.name, self.losingTeam.overallRating, self.losingTeam.offenseRating, self.losingTeam.runDefenseRating, self.losingTeam.passDefenseRating))
            print("SCORE: {0}-{1}".format(self.homeScore, self.awayScore))
        # print("\nGAME OVER")
        
def draft():
    draftOrderList = []
    draftQueueList = teamList.copy()
    playerDraftList = playerList.copy()
    rounds = 15

    qbs = 0
    rbs = 0
    wrs = 0
    tes = 0
    ks = 0

    for x in playerList:
        if x.position == 1:
            qbs += 1
        elif x.position == 2:
            rbs += 1
        elif x.position == 3:
            wrs += 1
        elif x.position == 4:
            tes += 1
        elif x.position == 5:
            ks += 1

    #print('\n Available Players by Position')
    #print('\n QBs = {0} | RBs = {1} | WRs = {2} | TEs = {3} | Ks = {4}'.format(qbs, rbs, wrs, tes, ks))


    for x in range(len(teamList)):
        rand = randint(0,len(draftQueueList) - 1)
        draftOrderList.insert(x, draftQueueList[rand])
        draftQueueList.pop(rand)

    for x in range(1, int(rounds)):
        #print('\nRound {0}'.format(x))
        for team in draftOrderList:
            bestAvailableQB = Player()
            bestAvailableRB = Player()
            bestAvailableWR = Player()
            bestAvailableTE = Player()
            bestAvailableK = Player()
            bestAvailablePlayer = Player()
            pick = Player()

            for player in playerDraftList:
                if player.overallRating > bestAvailablePlayer.overallRating:
                    bestAvailablePlayer = player
                if player.position.value == 1:
                    if player.overallRating > bestAvailableQB.overallRating:
                        bestAvailableQB = player
                elif player.position.value == 2:
                    if player.overallRating > bestAvailableRB.overallRating:
                        bestAvailableRB = player
                elif player.position.value == 3:
                    if player.overallRating > bestAvailableWR.overallRating:
                        bestAvailableWR = player
                elif player.position.value == 4:
                    if player.overallRating > bestAvailableTE.overallRating:
                        bestAvailableTE = player
                elif player.position.value == 5:
                    if player.overallRating > bestAvailableK.overallRating:
                        bestAvailableK = player

                if len(team.qbList) < 2 and len(team.rbList) < 2 and len(team.wrList) < 3 and len(team.teList) < 2 and len(team.kList) < 1:
                    pick = bestAvailablePlayer
                if len(team.qbList) >= 2 or len(team.rbList) >= 2 or len(team.wrList) >= 3 or len(team.teList) >= 2 or len(team.kList) >= 1:
                    if len(team.qbList) < 2  and len(bestAvailableQB.name) > 0:
                        pick = bestAvailableQB
                    elif len(team.rbList) < 2  and len(bestAvailableRB.name) > 0:
                        pick = bestAvailableRB
                    elif len(team.wrList) < 3  and len(bestAvailableWR.name) > 0:
                        pick = bestAvailableWR
                    elif len(team.teList) < 2  and len(bestAvailableTE.name) > 0:
                        pick = bestAvailableTE
                    elif len(team.kList) < 1  and len(bestAvailableK.name) > 0:
                        pick = bestAvailableK
                    else:
                        pick = bestAvailablePlayer


            if pick.position.value == 1:
                team.qbList.append(pick)
            elif pick.position.value == 2:
                team.rbList.append(pick)
            elif pick.position.value == 3:
                team.wrList.append(pick)
            elif pick.position.value == 4:
                team.teList.append(pick)
            elif pick.position.value == 5:
                team.kList.append(pick)
            team.teamRoster.append(pick)
            #print('{0} took {1}, {2}, rated {3}'.format(team.name, pick.name, pick.position, pick.overallRating))
            pick.team = team.name
            playerDraftList.remove(pick)
            bestAvailablePlayer = ''
            bestAvailableQB = ''
            bestAvailableRB = ''
            bestAvailableWR = ''
            bestAvailableTE = ''
            pick = ''

    # print("\n")
    # print("\nFree Agents")
    # for player in playerDraftList:
    #     print("{0} | {1} | {2}".format(player.name, player.overallRating, player.position))
    
def getPlayers():

    if os.path.exists("playerData.json"):
        with open('playerData.json') as jsonFile:
            playerData = json.load(jsonFile)
            for x in playerData:
                player = playerData[x]
                if player['position'] == 'QB':
                    newPlayer = PlayerQB()
                    newPlayer.qbRating = player['qbRating']
                    newPlayer.armStrength = player['armStrength']
                    newPlayer.accuracy = player['accuracy']
                elif player['position'] == 'RB':
                    newPlayer = PlayerRB()
                    newPlayer.rbRating = player['rbRating']
                elif player['position'] == 'WR':
                    newPlayer = PlayerWR()
                    newPlayer.wrRating = player['wrRating']
                elif player['position'] == 'TE':
                    newPlayer = PlayerTE()
                    newPlayer.teRating = player['teRating']
                elif player['position'] == 'K':
                    newPlayer = PlayerK()
                    newPlayer.kRating = player['kRating']
                    newPlayer.legStrength = player['legStrength']
                    newPlayer.accuracy = player['accuracy']

                newPlayer.name = player['name']
                newPlayer.overallRating = player['overallRating']
                newPlayer.speed = player['speed']
                newPlayer.hands = player['hands']
                newPlayer.agility = player['agility']
                newPlayer.power = player['power']

                playerList.append(newPlayer)
    else:
        dict = {}
        z = 0
        jsonFile = open("playerData.json", "w+") 
        fileObjext = open("playerNames.json", "r")
        jsonContent = fileObjext.read()
        playerNames = json.loads(jsonContent)
        for x in playerNames['players']:
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
            z += 1
            dict[z] = _prepare_for_serialization(player)

        jsonFile.write(json.dumps(dict, indent=4))
        jsonFile.close()

def getTeams():

    if os.path.exists("teamData.json"):
        with open('teamData.json') as jsonFile:
            teamData = json.load(jsonFile)
            for x in teamData:
                team = teamData[x]
                newTeam = Team(team['name'])
                newTeam.offenseRating = team['offenseRating']
                newTeam.runDefenseRating = team['runDefenseRating']
                newTeam.passDefenseRating = team['passDefenseRating']
                newTeam.defenseRating = team['defenseRating']
                newTeam.overallRating = team['overallRating']

                teamRoster = team['teamRoster']
                for y in teamRoster:
                    player = teamRoster[y]
                    for z in playerList:
                        if z.name == player['name']:
                            newTeam.teamRoster.append(z)
                            z.team = newTeam.name
                            if z.position.value == 1:
                                newTeam.qbList.append(z)
                            elif z.position.value == 2:
                                newTeam.rbList.append(z)
                            elif z.position.value == 3:
                                newTeam.wrList.append(z)
                            elif z.position.value == 4:
                                newTeam.teList.append(z)
                            elif z.position.value == 5:
                                newTeam.kList.append(z)

                teamList.append(newTeam)

    else:
        fileObjext = open("teams.json", "r")
        jsonContent = fileObjext.read()
        teamNames = json.loads(jsonContent)
        for x in teamNames['teams']:
            team = Team(x)
            teamList.append(team)

def getDivisons():

    if os.path.exists("divisionData.json"):
        with open('divisionData.json') as jsonFile:
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
        fileObjext = open("divisions.json", "r")
        jsonContent = fileObjext.read()
        divisionNames = json.loads(jsonContent)
        for x in divisionNames['divisions']:
            division = Division(x)
            divisionList.append(division)

def initTeams():
    dict = {}
    y = 0
    jsonFile = open("teamData.json", "w+")
    for team in teamList:
        team.setupTeam()
        y += 1
        dict[y] = _prepare_for_serialization(team)
        
    jsonFile.write(json.dumps(dict, indent=4))
    jsonFile.close()
        
def initDivisions():
    tempTeamList = teamList.copy()
    while len(tempTeamList) > 0:
        x = randint(0,len(tempTeamList)-1)
        if len(tempTeamList) % 2 == 0:
            divisionList[0].teamList.append(tempTeamList[x])
        else:
            divisionList[1].teamList.append(tempTeamList[x])
        tempTeamList.remove(tempTeamList[x])
    # for division in divisionList:
    #     print("\n{0} Division\n".format(division.name))
    #     for team in division.teamList:
    #         print(team.name)

def createSchedule():
    numOfWeeks = 10
    
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
    jsonFile = open("teamData.json", "w+")
    for team in teamList:
        team.winPercent = round((team.wins/(team.wins + team.losses)),3)

        for player in team.startersList:
            if hasattr(player, "passCompletions"):
                player.yardsPerCompletion = round(player.passYards/player.passCompletions)
                player.compPercent = round((player.passCompletions/player.passAttempts)*100)
                team.passYards += player.passYards
            if hasattr(player, "receptions"):
                player.yardsPerReception = round(player.rcvYards/player.receptions)
                player.rvcPercent = round((player.receptions/player.passTargets)*100)
            if hasattr(player, "carries"):
                player.yardsPerCarry = round(player.runYards/player.carries)
                team.runYards += player.runYards
            if hasattr(player, "fieldGoals"):
                if player.fieldGoals > 0:
                    player.fgPercent = round((player.fieldGoals/player.fgAttempts)*100)
                else:
                    player.fgPercent = 0
            if hasattr(player, "touchdowns"):
                team.touchdowns += player.touchdowns

        team.totalYards = team.passYards + team.runYards

        y += 1
        dict[y] = _prepare_for_serialization(team)

    jsonFile.write(json.dumps(dict, indent=4))
    jsonFile.close()


def startSeason():
    for week in scheduleList:
        print("\n-------------------------------------------------\n")
        print("Week {0}".format(scheduleList.index(week)+1))
        for game in range(0,len(week)):
            week[game].playGame()  
            week[game].postgame()

    getSeasonStats()
    dict = {}
    jsonFile = open("divisionData.json", "w+")
    for division in divisionList:
        list.sort(division.teamList, key=lambda team: team.winPercent, reverse=True)
        xlist = []
        print("\n{0} Division".format(division.name))
        for team in division.teamList:
            xlist.append(team.name)
            print("{0}[OAR:{1}|OR:{2}|RDR:{3}|PDR:{4}] ({5}-{6}) {7}".format(team.name, team.overallRating, team.offenseRating, team.runDefenseRating, team.passDefenseRating, team.wins, team.losses, team.winPercent))
        dict[division.name] = xlist

    jsonFile.write(json.dumps(dict, indent=4))
    jsonFile.close()


def init():
    getPlayers()
    getTeams()

    if not os.path.exists("teamData.json"):
        draft()

    initTeams()
    getDivisons()
    if not os.path.exists("divisionData.json"):
        initDivisions()

    createSchedule()
    startSeason()

init()