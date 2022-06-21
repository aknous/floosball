import enum
from random import randint
import copy
import asyncio
import floosball_player as FloosPlayer
import floosball_team

class PlayType(enum.Enum):
    Run = 1
    Pass = 2
    FieldGoal = 3
    Punt = 4
    
class PassType(enum.Enum):
    short = 1
    medium = 2
    long = 3

class GameStatus(enum.Enum):
    Scheduled = 1
    Active = 2
    Final = 3

class PlayResult(enum.Enum):
    FirstDown = '1st Down'
    SecondDown = '2nd Down'
    ThirdDown = '3rd Down'
    FourthDown = '4th Down'
    Punt = 'Punt'
    TurnoverOnDowns = 'Turnover On Downs'
    FieldGoalGood = 'Field Goal is Good!'
    FieldGoalNoGood = 'Field Goal is No Good!'
    ExtraPointGood = 'Extra Point is Good!'
    ExtraPointNoGood = 'Extra Point is No Good!'
    Touchdown = 'Touchdown!'
    Safety = 'Safety!'
    Fumble = 'Fumble!'
    Interception = 'Interception!'


playDict = {'offense': None, 'defense': None, 'down': None, 'yardsTo1st': None, 'play': None, 'yardage': None, 'runner': None, 'passer': None, 'receiver': None, 'completion': None, 'sack': None, 'kicker': None, 'result': None, 'playText': None}

class Game:
    def __init__(self, homeTeam, awayTeam):
        self.id = None
        self.status = None
        self.homeTeam : floosball_team.Team = homeTeam
        self.awayTeam : floosball_team.Team = awayTeam
        self.awayScore = 0
        self.homeScore = 0
        self.currentQuarter = 0
        self.down = 0
        self.yardsToFirstDown = 0
        self.yardsToEndzone = 0
        self.yardsToSafety = 0
        self.offensiveTeam = ''
        self.defensiveTeam = ''
        self.totalPlays = 0
        self.lastPlay = []
        self.winningTeam = ''
        self.losingTeam = ''
        self.gameDict = {}
        self.playsDict = {}

    def getGameData(self):
        homeTeamStatsDict = {}
        awayTeamStatsDict = {}
        homeTeamPassYards = 0
        awayTeamPassYards = 0
        homeTeamRushYards = 0
        awayTeamRushYards = 0
        homeTeamTotalYards = 0
        awayTeamTotalYards = 0

        gameStatsDict = {}

        for player in self.homeTeam.rosterDict.values():
            playerDict = {}
            if player.position is FloosPlayer.Position.QB:
                homeTeamPassYards += player.gameStatsDict['passYards']
                player.gameStatsDict['totalYards'] = player.gameStatsDict['passYards']
                if player.gameStatsDict['passComp'] > 0:
                    player.gameStatsDict['ypc'] = round(player.gameStatsDict['passYards']/player.gameStatsDict['passComp'])
                    player.gameStatsDict['passCompPerc'] = round((player.gameStatsDict['passComp']/player.gameStatsDict['passAtt'])*100)
            elif player.position is FloosPlayer.Position.RB:
                homeTeamRushYards += player.gameStatsDict['runYards']
                player.gameStatsDict['totalYards'] = player.gameStatsDict['rcvYards'] + player.gameStatsDict['runYards']
                if player.gameStatsDict['carries'] > 0:
                    player.gameStatsDict['ypc'] = round(player.gameStatsDict['runYards']/player.gameStatsDict['carries'])
                if player.gameStatsDict['receptions'] > 0:
                    player.gameStatsDict['ypr'] = round(player.gameStatsDict['rcvYards']/player.gameStatsDict['receptions'])
                    player.gameStatsDict['rcvPerc'] = round((player.gameStatsDict['receptions']/player.gameStatsDict['passTargets'])*100)
            elif player.position is FloosPlayer.Position.WR or player.position is FloosPlayer.Position.TE:
                player.gameStatsDict['totalYards'] = player.gameStatsDict['rcvYards']
                if player.gameStatsDict['receptions'] > 0:
                    player.gameStatsDict['ypr'] = round(player.gameStatsDict['rcvYards']/player.gameStatsDict['receptions'])
                    player.gameStatsDict['rcvPerc'] = round((player.gameStatsDict['receptions']/player.gameStatsDict['passTargets'])*100)
            elif player.position is FloosPlayer.Position.K:
                if player.gameStatsDict['fgs'] > 0:
                    player.gameStatsDict['fgPerc'] = round((player.gameStatsDict['fgs']/player.gameStatsDict['fgAtt'])*100)
                else:
                    player.gameStatsDict['fgPerc'] = 0

            playerDict['name'] = player.name
            playerDict['overallRating'] = player.attributes.overallRating
            playerDict['tier'] = player.playerTier.name
            playerDict['gameStats'] = copy.deepcopy(player.gameStatsDict)

            homeTeamStatsDict[player.position.name] = playerDict

        for player in self.awayTeam.rosterDict.values():
            playerDict = {}
            if player.position is FloosPlayer.Position.QB:
                awayTeamPassYards += player.gameStatsDict['passYards']
                player.gameStatsDict['totalYards'] = player.gameStatsDict['passYards']
                if player.gameStatsDict['passComp'] > 0:
                    player.gameStatsDict['ypc'] = round(player.gameStatsDict['passYards']/player.gameStatsDict['passComp'])
                    player.gameStatsDict['passCompPerc'] = round((player.gameStatsDict['passComp']/player.gameStatsDict['passAtt'])*100)
            elif player.position is FloosPlayer.Position.RB:
                awayTeamRushYards += player.gameStatsDict['runYards']
                player.gameStatsDict['totalYards'] = player.gameStatsDict['rcvYards'] + player.gameStatsDict['runYards']
                if player.gameStatsDict['carries'] > 0:
                    player.gameStatsDict['ypc'] = round(player.gameStatsDict['runYards']/player.gameStatsDict['carries'])
                if player.gameStatsDict['receptions'] > 0:
                    player.gameStatsDict['ypr'] = round(player.gameStatsDict['rcvYards']/player.gameStatsDict['receptions'])
                    player.gameStatsDict['rcvPerc'] = round((player.gameStatsDict['receptions']/player.gameStatsDict['passTargets'])*100)
            elif player.position is FloosPlayer.Position.WR or player.position is FloosPlayer.Position.TE:
                player.gameStatsDict['totalYards'] = player.gameStatsDict['rcvYards']
                if player.gameStatsDict['receptions'] > 0:
                    player.gameStatsDict['ypr'] = round(player.gameStatsDict['rcvYards']/player.gameStatsDict['receptions'])
                    player.gameStatsDict['rcvPerc'] = round((player.gameStatsDict['receptions']/player.gameStatsDict['passTargets'])*100)
            elif player.position is FloosPlayer.Position.K:
                if player.gameStatsDict['fgs'] > 0:
                    player.gameStatsDict['fgPerc'] = round((player.gameStatsDict['fgs']/player.gameStatsDict['fgAtt'])*100)
                else:
                    player.gameStatsDict['fgPerc'] = 0

            playerDict['name'] = player.name
            playerDict['overallRating'] = player.attributes.overallRating
            playerDict['tier'] = player.playerTier.name
            playerDict['gameStats'] = copy.deepcopy(player.gameStatsDict)

            awayTeamStatsDict[player.position.name] = playerDict

        homeTeamTotalYards = homeTeamPassYards + homeTeamRushYards
        awayTeamTotalYards = awayTeamPassYards + awayTeamRushYards

        homeTeamStatsDict['passYards'] = homeTeamPassYards
        homeTeamStatsDict['rushYards'] = homeTeamRushYards
        homeTeamStatsDict['totalYards'] = homeTeamTotalYards
        homeTeamStatsDict['overallRating'] = self.homeTeam.overallRating
        homeTeamStatsDict['offenseRating'] = self.homeTeam.offenseRating
        homeTeamStatsDict['defenseRating'] = self.homeTeam.defenseRating
        homeTeamStatsDict['runDefenseRating'] = self.homeTeam.runDefenseRating
        homeTeamStatsDict['passDefenseRating'] = self.homeTeam.passDefenseRating

        awayTeamStatsDict['passYards'] = awayTeamPassYards
        awayTeamStatsDict['rushYards'] = awayTeamRushYards
        awayTeamStatsDict['totalYards'] = awayTeamTotalYards
        awayTeamStatsDict['overallRating'] = self.awayTeam.overallRating
        awayTeamStatsDict['offenseRating'] = self.awayTeam.offenseRating
        awayTeamStatsDict['defenseRating'] = self.awayTeam.defenseRating
        awayTeamStatsDict['runDefenseRating'] = self.awayTeam.runDefenseRating
        awayTeamStatsDict['passDefenseRating'] = self.awayTeam.passDefenseRating

        gameStatsDict[self.homeTeam.name] = homeTeamStatsDict
        gameStatsDict[self.awayTeam.name] = awayTeamStatsDict


        return gameStatsDict


    def saveGameData(self):
        winningTeamStatsDict = {}
        losingTeamStatsDict = {}
        winningTeamPassYards = 0
        losingTeamPassYards = 0
        winningTeamRushYards = 0
        losingTeamRushYards = 0
        winningTeamTotalYards = 0
        losingTeamTotalYards = 0

        for player in self.winningTeam.rosterDict.values():
            playerDict = {}
            if player.position is FloosPlayer.Position.QB:
                winningTeamPassYards += player.gameStatsDict['passYards']
                player.gameStatsDict['totalYards'] = player.gameStatsDict['passYards']
                if player.gameStatsDict['passComp'] > 0:
                    player.gameStatsDict['ypc'] = round(player.gameStatsDict['passYards']/player.gameStatsDict['passComp'])
                    player.gameStatsDict['passCompPerc'] = round((player.gameStatsDict['passComp']/player.gameStatsDict['passAtt'])*100)
            elif player.position is FloosPlayer.Position.RB:
                winningTeamRushYards += player.gameStatsDict['runYards']
                player.gameStatsDict['totalYards'] = player.gameStatsDict['rcvYards'] + player.gameStatsDict['runYards']
                if player.gameStatsDict['carries'] > 0:
                    player.gameStatsDict['ypc'] = round(player.gameStatsDict['runYards']/player.gameStatsDict['carries'])
                if player.gameStatsDict['receptions'] > 0:
                    player.gameStatsDict['ypr'] = round(player.gameStatsDict['rcvYards']/player.gameStatsDict['receptions'])
                    player.gameStatsDict['rcvPerc'] = round((player.gameStatsDict['receptions']/player.gameStatsDict['passTargets'])*100)
            elif player.position is FloosPlayer.Position.WR or player.position is FloosPlayer.Position.TE:
                player.gameStatsDict['totalYards'] = player.gameStatsDict['rcvYards']
                if player.gameStatsDict['receptions'] > 0:
                    player.gameStatsDict['ypr'] = round(player.gameStatsDict['rcvYards']/player.gameStatsDict['receptions'])
                    player.gameStatsDict['rcvPerc'] = round((player.gameStatsDict['receptions']/player.gameStatsDict['passTargets'])*100)
            elif player.position is FloosPlayer.Position.K:
                if player.gameStatsDict['fgs'] > 0:
                    player.gameStatsDict['fgPerc'] = round((player.gameStatsDict['fgs']/player.gameStatsDict['fgAtt'])*100)
                else:
                    player.gameStatsDict['fgPerc'] = 0

            playerDict['name'] = player.name
            playerDict['overallRating'] = player.attributes.overallRating
            playerDict['tier'] = player.playerTier.name
            playerDict['gameStats'] = copy.deepcopy(player.gameStatsDict)

            winningTeamStatsDict[player.position.name] = playerDict

            for k in player.gameStatsDict.keys():
                player.gameStatsDict[k] = 0

        for player in self.losingTeam.rosterDict.values():
            playerDict = {}
            if player.position is FloosPlayer.Position.QB:
                losingTeamPassYards += player.gameStatsDict['passYards']
                player.gameStatsDict['totalYards'] = player.gameStatsDict['passYards']
                if player.gameStatsDict['passComp'] > 0:
                    player.gameStatsDict['ypc'] = round(player.gameStatsDict['passYards']/player.gameStatsDict['passComp'])
                    player.gameStatsDict['passCompPerc'] = round((player.gameStatsDict['passComp']/player.gameStatsDict['passAtt'])*100)
            elif player.position is FloosPlayer.Position.RB:
                losingTeamRushYards += player.gameStatsDict['runYards']
                player.gameStatsDict['totalYards'] = player.gameStatsDict['rcvYards'] + player.gameStatsDict['runYards']
                if player.gameStatsDict['carries'] > 0:
                    player.gameStatsDict['ypc'] = round(player.gameStatsDict['runYards']/player.gameStatsDict['carries'])
                if player.gameStatsDict['receptions'] > 0:
                    player.gameStatsDict['ypr'] = round(player.gameStatsDict['rcvYards']/player.gameStatsDict['receptions'])
                    player.gameStatsDict['rcvPerc'] = round((player.gameStatsDict['receptions']/player.gameStatsDict['passTargets'])*100)
            elif player.position is FloosPlayer.Position.WR or player.position is FloosPlayer.Position.TE:
                player.gameStatsDict['totalYards'] = player.gameStatsDict['rcvYards']
                if player.gameStatsDict['receptions'] > 0:
                    player.gameStatsDict['ypr'] = round(player.gameStatsDict['rcvYards']/player.gameStatsDict['receptions'])
                    player.gameStatsDict['rcvPerc'] = round((player.gameStatsDict['receptions']/player.gameStatsDict['passTargets'])*100)
            elif player.position is FloosPlayer.Position.K:
                if player.gameStatsDict['fgs'] > 0:
                    player.gameStatsDict['fgPerc'] = round((player.gameStatsDict['fgs']/player.gameStatsDict['fgAtt'])*100)
                else:
                    player.gameStatsDict['fgPerc'] = 0

            playerDict['name'] = player.name
            playerDict['overallRating'] = player.attributes.overallRating
            playerDict['tier'] = player.playerTier.name
            playerDict['gameStats'] = copy.deepcopy(player.gameStatsDict)

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
                self.lastPlayDict['result'] = PlayResult.Fumble.value
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
                self.lastPlayDict['result'] = PlayResult.Fumble.value
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
            yardage = round(-(randint(0,5) * sackModifyer))
            # print("\n{0} sacked {1} for {2} yard(s)".format(defense.name, passer.name, yardage))
            defense.seasonTeamStats['Defense']['sacks'] += 1
            #self.lastPlay.insert(0, PlayType.Pass)
            self.lastPlayDict['play'] = PlayType.Pass.name
            #self.lastPlay.insert(1, passer) 
            self.lastPlayDict['passer'] = passer
            self.lastPlayDict['yardage'] = yardage
            self.lastPlayDict['sack'] = True
            return yardage
        else:
            passer.gameStatsDict['passAtt'] += 1
            passTarget = randint(1,10)

            if passType.value == 1:
                if passTarget < 4:
                    receiver = rb   
                elif passTarget >= 4 and passTarget < 6:
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
                        self.lastPlayDict['completion'] = True
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
                        self.lastPlayDict['completion'] = False
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
                        self.lastPlayDict['result'] = PlayResult.Interception.value
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
                        self.lastPlayDict['completion'] = False
                        return yardage


            elif passType.value == 2:
                if passTarget < 3:
                    receiver = rb   
                elif passTarget >= 3 and passTarget < 7:
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
                        self.lastPlayDict['completion'] = True
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
                        self.lastPlayDict['completion'] = False
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
                        self.lastPlayDict['result'] = PlayResult.Interception.value
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
                        self.lastPlayDict['completion'] = False
                        return yardage

            elif passType.value == 3:
                if passTarget < 4:
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
                        self.lastPlayDict['completion'] = True
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
                        self.lastPlayDict['completion'] = False
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
                        self.lastPlayDict['result'] = PlayResult.Interception.value
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
                        self.lastPlayDict['completion'] = False
                        return yardage

    def playCaller(self, offense, defense):
        if self.currentQuarter == 5:
            x = randint(1,10)
            if self.yardsToEndzone <= 55 and self.yardsToEndzone > 40 and x > 7:
                return 1001
            if self.yardsToEndzone <= 40 and self.yardsToEndzone > 30 and x > 3:
                return 1001
            else:
                return 1001

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
                if self.totalPlays > 120 and self.yardsToEndzone < 20:
                    return self.passPlay(offense, defense, PassType.medium)
                elif self.totalPlays > 120 and self.yardsToEndzone > 20:
                    return self.passPlay(offense, defense, PassType.long)
                elif self.yardsToFirstDown <= 2:
                    if self.yardsToSafety > 20:
                        x = randint(1,3)
                        if x == 1:
                            return self.runPlay(offense, defense)
                        elif x == 2:
                            return self.passPlay(offense, defense, PassType.short)
                        else:
                            return self.passPlay(offense, defense, PassType.medium)
                    else:
                        x = randint(1,10)
                        if x > 8:
                            self.lastPlayDict['play'] = PlayType.Punt.name
                            return 1002
                        else:
                            x = randint(1,3)
                            if x == 1:
                                return self.runPlay(offense, defense)
                            elif x == 2:
                                return self.passPlay(offense, defense, PassType.short)
                            else:
                                return self.passPlay(offense, defense, PassType.medium)         
                else:
                    if self.yardsToEndzone > 30 and self.yardsToSafety < 55 and self.yardsToFirstDown > 6:
                        x = randint(1,10)
                        if x > 6:
                            return 1001
                        else:
                            return self.passPlay(offense, defense, PassType.medium)
                    else:
                        return self.passPlay(offense, defense, PassType.medium)
            elif self.currentQuarter == 4 and self.homeTeam == offense and self.homeScore < self.awayScore:
                if self.totalPlays > 120 and self.yardsToEndzone < 20:
                    return self.passPlay(offense, defense, PassType.medium)
                elif self.totalPlays > 120 and self.yardsToEndzone > 20:
                    return self.passPlay(offense, defense, PassType.long)
                elif self.yardsToFirstDown <= 2:
                    if self.yardsToSafety > 20:
                        x = randint(1,3)
                        if x == 1:
                            return self.runPlay(offense, defense)
                        elif x == 2:
                            return self.passPlay(offense, defense, PassType.short)
                        else:
                            return self.passPlay(offense, defense, PassType.medium)
                    else:
                        x = randint(1,10)
                        if x > 8:
                            self.lastPlayDict['play'] = PlayType.Punt.name
                            return 1002
                        else:
                            x = randint(1,3)
                            if x == 1:
                                return self.runPlay(offense, defense)
                            elif x == 2:
                                return self.passPlay(offense, defense, PassType.short)
                            else:
                                return self.passPlay(offense, defense, PassType.medium)         
                else:
                    if self.yardsToEndzone > 30 and self.yardsToSafety < 55 and self.yardsToFirstDown > 6:
                        x = randint(1,10)
                        if x > 6:
                            return 1001
                        else:
                            return self.passPlay(offense, defense, PassType.medium)
                    else:
                        return self.passPlay(offense, defense, PassType.medium)

            elif self.yardsToEndzone <= 5:
                    x = randint(1,10)
                    if x < 6:
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
                    x = randint(1,10)
                    if x >= 4:
                        return 1001
                    else:
                        y = randint(1,3)
                        if y == 1:
                            return self.runPlay(offense, defense)
                        elif y == 2:
                            return self.passPlay(offense, defense, PassType.short)
                        else:
                            return self.passPlay(offense, defense, PassType.medium)
                else:
                    x = randint(1,10)
                    if x < 8:
                        return 1001
                    else:
                        return self.passPlay(offense, defense, PassType.medium)
            elif self.yardsToSafety <= 20:
                self.lastPlayDict['play'] = PlayType.Punt.name
                return 1002
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
        pass
        #print('\nGame {} SCORE CHANGE'.format(self.id))
        #print("{0}: {1}".format(self.awayTeam.name, self.awayScore))
        #print("{0}: {1}".format(self.homeTeam.name, self.homeScore))

    def formatPlayText(self, play):
        text = None
        if play['play'] == PlayType.Run.name:
            if play['result'] == PlayResult.Fumble.value:
                text = '{0}:: {1} {2}'.format(play['offense'].name, play['runner'].name, play['result'])
            else:
                text = '{0}:: {1} runs for {2} yards. {3}'.format(play['offense'].name, play['runner'].name, play['yardage'], play['result'])
        elif play['play'] == PlayType.Pass.name:
            if play['sack']:
                text = '{0}:: {1} sacked for {2} yards. {3}'.format(play['offense'].name, play['passer'].name, play['yardage'], play['result'])
            elif play['completion']:
                text = '{0}:: {1} pass to {2} complete for {3} yards. {4}'.format(play['offense'].name, play['passer'].name, play['receiver'].name, play['yardage'], play['result'])
            elif play['result'] == PlayResult.Interception.value:
                text = '{0}:: {1} pass intercepted by {2}.'.format(play['offense'].name, play['passer'].name, play['defense'].name)
            else:
                text = '{0}:: {1} pass to {2} incomplete. {3}'.format(play['offense'].name, play['passer'].name, play['receiver'].name, play['result'])
        elif play['play'] == PlayType.FieldGoal.name:
            text = '{0}:: Field Goal attempt by {1}. {2}'.format(play['offense'].name, play['kicker'].name, play['result'])
        elif play['play'] == PlayType.Punt.name:
            text = '{0}:: {1} {2}'.format(play['offense'].name, play['offense'].name, play['result'])
        
        play['playText'] = text

    def postgame(self):    
        # print('\n{0} Player Stats'.format(self.homeTeam.name))   

        self.winningTeam.seasonTeamStats['winPerc'] = round(self.winningTeam.seasonTeamStats['wins']/(self.winningTeam.seasonTeamStats['wins']+self.winningTeam.seasonTeamStats['losses']),3)
        self.losingTeam.seasonTeamStats['winPerc'] = round(self.losingTeam.seasonTeamStats['wins']/(self.losingTeam.seasonTeamStats['wins']+self.losingTeam.seasonTeamStats['losses']),3)

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

    async def playGame(self):
        # print("\nGame {0} Start: {1} v. {2}".format(self.id, self.awayTeam.name, self.homeTeam.name))
        self.status = GameStatus.Active
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

            if self.totalPlays < 1:
                self.yardsToFirstDown = 10
                self.yardsToEndzone = 80
                self.yardsToSafety = 20

            self.down = 1

            # print("\nGame {0}: {1} is on offense. {2} yard(s) to the endzone".format(self.id, self.offensiveTeam.name, self.yardsToEndzone))

            while self.down <= 4:

                if self.totalPlays < 33:
                    self.currentQuarter = 1
                elif self.totalPlays >= 33 and self.totalPlays < 66:
                    self.currentQuarter = 2
                elif self.totalPlays >= 66 and self.totalPlays < 100:
                    self.currentQuarter = 3
                elif self.totalPlays >= 100 and self.totalPlays < 132:
                    self.currentQuarter = 4
                elif self.totalPlays >= 132:
                    self.currentQuarter = 5

                if self.totalPlays > 0:
                    self.formatPlayText(self.lastPlayDict)
                    play = str(self.totalPlays)
                    self.playsDict[play] = self.lastPlayDict
                if self.totalPlays == 132 and self.homeScore != self.awayScore:
                    break

                #self.lastPlay.clear()
                self.lastPlayDict = copy.deepcopy(playDict)

                self.lastPlayDict['offense'] = self.offensiveTeam
                self.lastPlayDict['defense'] = self.defensiveTeam
                self.lastPlayDict['down'] = self.down
                self.lastPlayDict['yardsTo1st'] = self.yardsToFirstDown

                # print("\nDOWN: {0}".format(self.down))
                await asyncio.sleep(randint(10, 30))
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
                        self.scoreChange()
                        self.lastPlayDict['result'] = '{0} {1}-{2}'.format(PlayResult.FieldGoalGood.value, self.awayScore, self.homeScore)
                        if self.currentQuarter == 5 and self.homeScore != self.awayScore:
                            break
                        else:
                            self.turnover(self.offensiveTeam, self.defensiveTeam, possReset)
                            break
                    else:
                        # print("\n{0} field goal is NO GOOD. KICKER: {1}".format(self.offensiveTeam.name,self.lastPlay[1].name))
                        # print("Turnover")
                        self.lastPlayDict['result'] = PlayResult.FieldGoalNoGood.value
                        self.turnover(self.offensiveTeam, self.defensiveTeam, self.yardsToSafety)
                        break
                elif yardsGained == 1002:
                    # print("\n{0} punt.".format(self.offensiveTeam.name))
                    # print("Turnover")
                    self.lastPlayDict['result'] = PlayResult.Punt.value
                    puntDistance = randint(30, 60)
                    if puntDistance >= self.yardsToEndzone:
                        puntDistance = self.yardsToEndzone - 20
                    newYards = 100 - (self.yardsToEndzone - puntDistance)
                    self.turnover(self.offensiveTeam, self.defensiveTeam, newYards)
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

                        if self.offensiveTeam == self.homeTeam:
                            self.homeScore += 6
                        elif self.offensiveTeam == self.awayTeam:
                            self.awayScore += 6

                        self.scoreChange()

                        if self.extraPointTry(self.offensiveTeam):
                            if self.offensiveTeam == self.homeTeam:
                                self.homeScore += 1
                            elif self.offensiveTeam == self.awayTeam:
                                self.awayScore += 1
                            # print("\n{0} extra point is GOOD.".format(self.offensiveTeam.name))
                            self.scoreChange()
                        else:
                            pass
                            # print("\n{0} extra point is NO GOOD.".format(self.offensiveTeam.name))    
                        self.lastPlayDict['result'] = '{0} {1}-{2}'.format(PlayResult.Touchdown.value, self.awayScore, self.homeScore)
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
                        self.lastPlayDict['result'] = PlayResult.FirstDown.value
                        # print("\n{0} FIRST DOWN. {1} yard(s) to endzone".format(self.offensiveTeam.name, self.yardsToEndzone))
                        continue

                    elif (self.yardsToSafety + yardsGained) <= 0:
                        if self.defensiveTeam == self.homeTeam:
                            self.homeScore += 2
                        elif self.defensiveTeam == self.awayTeam:
                            self.awayScore += 2
                        # print("\nSAFETY")
                        self.lastPlayDict['result'] = PlayResult.Safety.value
                        self.scoreChange()
                        self.turnover(self.offensiveTeam, self.defensiveTeam, possReset)
                        break

                    elif yardsGained < self.yardsToFirstDown:
                        if self.down < 4:
                            self.yardsToEndzone -= yardsGained
                            self.yardsToFirstDown -= yardsGained
                            self.down += 1
                            if self.down == 2:
                                self.lastPlayDict['result'] = '{0} and {1}'.format(PlayResult.SecondDown.value, self.yardsToFirstDown)
                            elif self.down == 3:
                                self.lastPlayDict['result'] = '{0} and {1}'.format(PlayResult.ThirdDown.value, self.yardsToFirstDown)
                            elif self.down == 4:
                                self.lastPlayDict['result'] = '{0} and {1}'.format(PlayResult.FourthDown.value, self.yardsToFirstDown)
                            continue
                        else:
                            # print("\nTurnover on downs")
                            self.lastPlayDict['result'] = PlayResult.TurnoverOnDowns.value
                            self.turnover(self.offensiveTeam, self.defensiveTeam, self.yardsToSafety)
                            break
            
        else:
            self.formatPlayText(self.lastPlayDict)
            play = str(self.totalPlays)
            self.playsDict[play] = self.lastPlayDict

        if self.awayScore > self.homeScore:
            self.winningTeam = self.awayTeam
            self.losingTeam = self.homeTeam
            self.awayTeam.seasonTeamStats['wins'] += 1
            self.homeTeam.seasonTeamStats['losses'] += 1
            self.gameDict['score'] = '{0} - {1}'.format(self.awayScore, self.homeScore)
            #print("\nGame {}).".format(self.id))
            #print("\nRESULT: {0} def. {1}.".format(self.winningTeam.name, self.losingTeam.name))
            #print("SCORE: {0}-{1}".format(self.awayScore, self.homeScore))
        elif self.homeScore > self.awayScore:
            self.winningTeam = self.homeTeam
            self.losingTeam = self.awayTeam
            self.homeTeam.seasonTeamStats['wins'] += 1
            self.awayTeam.seasonTeamStats['losses'] += 1
            self.gameDict['score'] = '{0} - {1}'.format(self.homeScore, self.awayScore)
            #print("\nGame {}).".format(self.id))
            #print("\nRESULT: {0} def. {1}.".format(self.winningTeam.name, self.losingTeam.name))
            #print("SCORE: {0}-{1}".format(self.homeScore, self.awayScore))

        self.gameDict['winningTeam'] = self.winningTeam.name
        self.gameDict['losingTeam'] = self.losingTeam.name
        self.saveGameData()
        self.winningTeam.updateRating()
        self.losingTeam.updateRating()
        self.status = GameStatus.Final



