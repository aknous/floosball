import enum
from gettext import find
from random import randint
import copy
import asyncio
from time import sleep
import floosball_player as FloosPlayer
import floosball_team as FloosTeam

class PlayType(enum.Enum):
    Run = 'Run'
    Pass = 'Pass'
    FieldGoal = 'Field Goal Try'
    Punt = 'Punt'
    ExtraPoint = 'Extra Point'
    
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
    FieldGoalGood = 'Field Goal is Good'
    FieldGoalNoGood = 'Field Goal is No Good'
    ExtraPointGood = 'XP Good'
    ExtraPointNoGood = 'XP No Good'
    Touchdown = 'Touchdown'
    Safety = 'Safety'
    Fumble = 'Fumble'
    Interception = 'Interception'


playDict = {'offense': None, 'defense': None, 'homeTeamScore': 0, 'awayTeamScore': 0, 'quarter': 0, 'down': None, 'playsLeft': 0, 'yardLine': None, 'yardsTo1st': None, 'play': None, 'yardage': None, 'runner': None, 'passer': None, 'receiver': None, 'completion': None, 'sack': None, 'kicker': None, 'fgDistance': None, 'result': None, 'playText': None, 'scoreChange': False, 'isTd': False, 'isFg': False, 'isSafety': False}

class Game:
    def __init__(self, homeTeam, awayTeam):
        self.id = None
        self.status = None
        self.homeTeam : FloosTeam.Team = homeTeam
        self.awayTeam : FloosTeam.Team = awayTeam
        self.awayScore = 0
        self.homeScore = 0
        self.homeScoreQ1 = 0
        self.homeScoreQ2 = 0
        self.homeScoreQ3 = 0
        self.homeScoreQ4 = 0
        self.awayScoreQ1 = 0
        self.awayScoreQ2 = 0
        self.awayScoreQ3 = 0
        self.awayScoreQ4 = 0
        self.currentQuarter = 0
        self.homePlaysTotal = 0
        self.awayPlaysTotal = 0
        self.home1stDownsTotal = 0
        self.away1stDownsTotal = 0
        self.homeTurnoversTotal = 0
        self.awayTurnoversTotal = 0
        self.isHalftime = False
        self.isOvertime = False
        self.down = 0
        self.yardLine = None
        self.yardsToFirstDown = 0
        self.yardsToEndzone = 0
        self.yardsToSafety = 0
        self.offensiveTeam: FloosTeam.Team = None
        self.defensiveTeam: FloosTeam.Team = None
        self.totalPlays = 0
        self.driveLength = 0
        self.winningTeam: FloosTeam.Team = None
        self.losingTeam: FloosTeam.Team = None
        self.gameDict = {}
        self.playsList = []
        self.scoringPlaysList = []

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
            player: FloosPlayer.Player
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
            playerDict['overallRating'] = player.gameAttributes.overallRating
            playerDict['gameStats'] = copy.deepcopy(player.gameStatsDict)

            awayTeamStatsDict[player.position.name] = playerDict

        homeTeamTotalYards = homeTeamPassYards + homeTeamRushYards
        awayTeamTotalYards = awayTeamPassYards + awayTeamRushYards

        homeTeamStatsDict['passYards'] = homeTeamPassYards
        homeTeamStatsDict['rushYards'] = homeTeamRushYards
        homeTeamStatsDict['totalYards'] = homeTeamTotalYards
        homeTeamStatsDict['overallRatingStars'] = round((((self.homeTeam.overallRating - 70)/30)*9)+1)
        homeTeamStatsDict['teamName'] = self.homeTeam.name
        homeTeamStatsDict['teamCity'] = self.homeTeam.city
        homeTeamStatsDict['teamcolor'] = self.homeTeam.color
        homeTeamStatsDict['record'] = '{}-{}'.format(self.homeTeam.seasonTeamStats['wins'], self.homeTeam.seasonTeamStats['losses'])
        homeTeamStatsDict['score'] = self.homeScore
        homeTeamStatsDict['qtr1pts'] = self.homeScoreQ1
        homeTeamStatsDict['qtr2pts'] = self.homeScoreQ2
        homeTeamStatsDict['qtr3pts'] = self.homeScoreQ3
        homeTeamStatsDict['qtr4pts'] = self.homeScoreQ4
        homeTeamStatsDict['1stDowns'] = self.home1stDownsTotal
        homeTeamStatsDict['totalPlays'] = self.homePlaysTotal
        homeTeamStatsDict['turnovers'] = self.homeTurnoversTotal

        awayTeamStatsDict['passYards'] = awayTeamPassYards
        awayTeamStatsDict['rushYards'] = awayTeamRushYards
        awayTeamStatsDict['totalYards'] = awayTeamTotalYards
        awayTeamStatsDict['overallRatingStars'] = round((((self.awayTeam.overallRating - 70)/30)*9)+1)
        awayTeamStatsDict['teamName'] = self.awayTeam.name
        awayTeamStatsDict['teamCity'] = self.awayTeam.city
        awayTeamStatsDict['teamcolor'] = self.awayTeam.color
        awayTeamStatsDict['record'] = '{}-{}'.format(self.awayTeam.seasonTeamStats['wins'], self.awayTeam.seasonTeamStats['losses'])
        awayTeamStatsDict['score'] = self.awayScore
        awayTeamStatsDict['qtr1pts'] = self.awayScoreQ1
        awayTeamStatsDict['qtr2pts'] = self.awayScoreQ2
        awayTeamStatsDict['qtr3pts'] = self.awayScoreQ3
        awayTeamStatsDict['qtr4pts'] = self.awayScoreQ4
        awayTeamStatsDict['1stDowns'] = self.away1stDownsTotal
        awayTeamStatsDict['totalPlays'] = self.awayPlaysTotal
        awayTeamStatsDict['turnovers'] = self.awayTurnoversTotal

        gameStatsDict['homeTeam'] = homeTeamStatsDict
        gameStatsDict['awayTeam'] = awayTeamStatsDict

        gameStatsDict['quarter'] = self.currentQuarter
        gameStatsDict['isHalftime'] = self.isHalftime
        gameStatsDict['isOvertime'] = self.isOvertime
        gameStatsDict['plays'] = self.totalPlays
        if self.offensiveTeam == self.homeTeam:
            gameStatsDict['homeTeamPoss'] = True
            gameStatsDict['awayTeamPoss'] = False
        else:
            gameStatsDict['homeTeamPoss'] = False
            gameStatsDict['awayTeamPoss'] = True
        if self.offensiveTeam == self.homeTeam:
            gameStatsDict['homeTeamPoss'] = True
            gameStatsDict['awayTeamPoss'] = False
        else:
            gameStatsDict['homeTeamPoss'] = False
            gameStatsDict['awayTeamPoss'] = True
        gameStatsDict['down'] = self.down
        if self.down == 1:
            down = '1st'
        elif self.down == 2:
            down = '2nd'
        elif self.down == 3:
            down = '3rd'
        elif self.down == 4:
            down = '4th'
        gameStatsDict['downText'] = '{0} & {1}'.format(down, self.yardsToFirstDown)
        if self.yardsToEndzone < 10:
            gameStatsDict['yardsTo1stDwn'] = self.yardsToEndzone
        else:
            gameStatsDict['yardsTo1stDwn'] = self.yardsToFirstDown
        gameStatsDict['yardsToEZ'] = self.yardsToEndzone
        gameStatsDict['yardLine'] = self.yardLine
        gameStatsDict['playsLeft'] = 132 - self.totalPlays
        gameStatsDict['status'] = self.status.name


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
            player: FloosPlayer.Player
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
            playerDict['overallRating'] = player.gameAttributes.overallRating
            playerDict['tier'] = player.playerTier.name
            playerDict['gameStats'] = copy.deepcopy(player.gameStatsDict)

            winningTeamStatsDict[player.position.name] = playerDict


        for player in self.losingTeam.rosterDict.values():
            player: FloosPlayer.Player
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
            playerDict['overallRating'] = player.gameAttributes.overallRating
            playerDict['tier'] = player.playerTier.name
            playerDict['gameStats'] = copy.deepcopy(player.gameStatsDict)

            losingTeamStatsDict[player.position.name] = playerDict

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

    def fieldGoalTry(self, offense: FloosTeam.Team):
        kicker: FloosPlayer.PlayerK = offense.rosterDict['k']
        kicker.gameStatsDict['fgAtt'] += 1
        yardsToFG = self.yardsToEndzone + 17
        self.lastPlayDict['fgDistance'] = yardsToFG
        x = randint(1,100)
        if yardsToFG <= 20:
            if (kicker.gameAttributes.overallRating + 15) >= x:
                fgSuccess = True
                kicker.gameStatsDict['fgs'] += 1
                kicker.updateInGameConfidence(.005)
            else:
                fgSuccess = False
                kicker.updateInGameConfidence(-.02)
        elif yardsToFG > 20 and yardsToFG <= 40:
            if (kicker.gameAttributes.overallRating) >= x:
                fgSuccess = True
                kicker.gameStatsDict['fgs'] += 1
                kicker.updateInGameConfidence(.01)
            else:
                fgSuccess = False
                kicker.updateInGameConfidence(-.015)
        elif yardsToFG > 50 and yardsToFG <= 60:
            if (kicker.gameAttributes.overallRating - 15) >= x:
                fgSuccess = True
                kicker.gameStatsDict['fgs'] += 1
                kicker.updateInGameConfidence(.015)
            else:
                fgSuccess = False
                kicker.updateInGameConfidence(-.01)
        else:
            if (kicker.gameAttributes.overallRating - 25) >= x:
                fgSuccess = True
                kicker.gameStatsDict['fgs'] += 1
                kicker.updateInGameConfidence(.02)
            else:
                fgSuccess = False
                kicker.updateInGameConfidence(-.01)
        self.lastPlayDict['play'] = PlayType.FieldGoal.value
        self.lastPlayDict['kicker'] = kicker
        kicker.updateRating()
        return fgSuccess

    def extraPointTry(self, offense: FloosTeam.Team):
        kicker: FloosPlayer.PlayerK = offense.rosterDict['k']
        x = randint(1,100)
        if (kicker.gameAttributes.overallRating + 10) >= x:
            fgSuccess = True
        else:
            fgSuccess = False
        kicker.updateRating()
        return fgSuccess

    def runPlay(self, offense: FloosTeam.Team, defense: FloosTeam.Team):
        runner: FloosPlayer.PlayerRB = offense.rosterDict['rb']
        blocker: FloosPlayer.PlayerTE = offense.rosterDict['te']
        yardage = 0
        x = randint(1,100)
        fumbleRoll = randint(1,100)
        fumbleResist = round(((runner.gameAttributes.power*1) + (runner.gameAttributes.luck*.7) + (runner.gameAttributes.discipline*1.3))/3)
        playStrength = ((runner.gameAttributes.overallRating*1.3) + (blocker.gameAttributes.power*.7))/2
        if (defense.runDefenseRating + randint(-3,3)) >= (playStrength + randint(-3,3)):
            if fumbleRoll/fumbleResist < 1.15:
                if x < 20:
                    yardage = randint(-2,0)
                    runner.updateInGameConfidence(-.005)
                elif x >= 20 and x <= 70:
                    yardage = randint(0,3)
                elif x > 70 and x <= 99:
                    yardage = randint(4,7)
                else:
                    if self.yardsToEndzone < 7:
                        yardage = randint(0, self.yardsToEndzone)
                    else:
                        yardage = randint(7, self.yardsToEndzone)
                    runner.updateInGameConfidence(.01)
            else:
                #fumble
                yardage = 1004
                runner.gameStatsDict['carries'] += 1
                runner.gameStatsDict['fumblesLost'] += 1
                runner.updateInGameConfidence(-.02)
                defense.updateGameConfidence(.02)
                defense.gameDefenseStats['fumRec'] += 1
                self.lastPlayDict['play'] = PlayType.Run.value
                self.lastPlayDict['runner'] = runner
                self.lastPlayDict['result'] = PlayResult.Fumble.value
                return yardage

        else:
            if (fumbleRoll/fumbleResist) < 1.2:
                if x < 50:
                    yardage = randint(0,3)
                elif x >= 50 and x < 85:
                    yardage = randint(4,7)
                elif x >= 85 and x < 90:
                    yardage = randint(8,10)
                    runner.updateInGameConfidence(.005)
                elif x >= 90 and x <= 95:
                    yardage = randint(11,20)
                else:
                    if self.yardsToEndzone < 20:
                        yardage = randint(0, self.yardsToEndzone)
                    else:
                        yardage = randint(20, self.yardsToEndzone)
                    runner.updateInGameConfidence(.01)
            else:
                #fumble
                yardage = 1004
                runner.gameStatsDict['carries'] += 1
                runner.gameStatsDict['fumblesLost'] += 1
                defense.gameDefenseStats['fumRec'] += 1
                runner.updateInGameConfidence(-.02)
                defense.updateGameConfidence(.02)
                self.lastPlayDict['play'] = PlayType.Run.value
                self.lastPlayDict['runner'] = runner
                self.lastPlayDict['result'] = PlayResult.Fumble.value
                return yardage

        if yardage > self.yardsToEndzone:
            yardage = self.yardsToEndzone

        runner.gameStatsDict['runYards'] += yardage
        runner.gameStatsDict['carries'] += 1
        defense.gameDefenseStats['runYardsAlwd'] += yardage
        defense.gameDefenseStats['totalYardsAlwd'] += yardage
        self.lastPlayDict['play'] = PlayType.Run.value
        self.lastPlayDict['runner'] = runner
        self.lastPlayDict['yardage'] = yardage
        return yardage

    def passPlay(self, offense: FloosTeam.Team, defense: FloosTeam.Team, passType):
        passer: FloosPlayer.PlayerQB = offense.rosterDict['qb']
        rb: FloosPlayer.PlayerRB = offense.rosterDict['rb']
        wr: FloosPlayer.PlayerWR = offense.rosterDict['wr']
        te: FloosPlayer.PlayerTE = offense.rosterDict['te']
        receiver: FloosPlayer.Player = None
        sackRoll = randint(1,1000)
        sackModifyer = (defense.defenseRating + randint(-3,3))/(passer.gameAttributes.agility + randint(-3,3))

        if sackRoll < round(100 * (sackModifyer)):
            yardage = round(-(randint(0,5) * sackModifyer))
            defense.gameDefenseStats['sacks'] += 1
            self.lastPlayDict['play'] = PlayType.Pass.value
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
                receiverYACRating = (receiver.gameAttributes.agility+receiver.gameAttributes.speed+receiver.gameAttributes.playMakingAbility)/3
                if accRoll < (passer.gameAttributes.overallRating - (defense.passDefenseRating/12)):
                    dropRoll = round(randint(1,100) + (defense.passDefenseRating/10))
                    if (receiver.gameAttributes.hands) > dropRoll:
                        passYards = randint(0,5)
                        yac = 0
                        x = randint(1,10)
                        if receiverYACRating > defense.defenseRating:
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
                        defense.gameDefenseStats['passYardsAlwd'] += yardage
                        defense.gameDefenseStats['totalYardsAlwd'] += yardage
                        passer.updateInGameConfidence(0.005)
                        receiver.updateInGameConfidence(0.005)
                        self.lastPlayDict['play'] = PlayType.Pass.value
                        self.lastPlayDict['passer'] = passer
                        self.lastPlayDict['receiver'] = receiver
                        self.lastPlayDict['yardage'] = yardage
                        self.lastPlayDict['completion'] = True
                        return yardage
                    else:
                        yardage = 0
                        receiver.gameStatsDict['passTargets'] += 1
                        receiver.updateInGameConfidence(-.005)
                        self.lastPlayDict['play'] = PlayType.Pass.value
                        self.lastPlayDict['passer'] = passer
                        self.lastPlayDict['receiver'] = receiver
                        self.lastPlayDict['yardage'] = yardage
                        self.lastPlayDict['completion'] = False
                        return yardage

                else:
                    interceptRoll = randint(1,100)
                    if interceptRoll <= 8:
                        yardage = 1003
                        passer.gameStatsDict['ints'] += 1
                        passer.updateInGameConfidence(-.02)
                        defense.updateGameConfidence(.02)
                        defense.gameDefenseStats['ints'] += 1
                        self.lastPlayDict['play'] = PlayType.Pass.value
                        self.lastPlayDict['passer'] = passer
                        self.lastPlayDict['receiver'] = receiver
                        self.lastPlayDict['yardage'] = yardage
                        self.lastPlayDict['result'] = PlayResult.Interception.value
                        return yardage
                    else:
                        yardage = 0
                        passer.updateInGameConfidence(-.005)
                        self.lastPlayDict['play'] = PlayType.Pass.value
                        self.lastPlayDict['passer'] = passer
                        self.lastPlayDict['receiver'] = receiver
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
                receiverYACRating = (receiver.gameAttributes.agility+receiver.gameAttributes.speed+receiver.gameAttributes.playMakingAbility)/3
                if accRoll < (passer.gameAttributes.overallRating - (defense.passDefenseRating/8)):
                    dropRoll = round(randint(1,100) + (defense.passDefenseRating/10))
                    if receiver.gameAttributes.overallRating > dropRoll:
                        passYards = randint(5,10)
                        yac = 0
                        x = randint(1,10)
                        if receiverYACRating > defense.defenseRating:
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
                        defense.gameDefenseStats['passYardsAlwd'] += yardage
                        defense.gameDefenseStats['totalYardsAlwd'] += yardage
                        passer.updateInGameConfidence(.005)
                        receiver.updateInGameConfidence(.005)
                        self.lastPlayDict['play'] = PlayType.Pass.value
                        self.lastPlayDict['passer'] = passer
                        self.lastPlayDict['receiver'] = receiver
                        self.lastPlayDict['yardage'] = yardage
                        self.lastPlayDict['completion'] = True
                        return yardage
                    else:
                        yardage = 0
                        receiver.gameStatsDict['passTargets'] += 1 
                        receiver.updateInGameConfidence(-.005)  
                        self.lastPlayDict['play'] = PlayType.Pass.value
                        self.lastPlayDict['passer'] = passer
                        self.lastPlayDict['receiver'] = receiver
                        self.lastPlayDict['yardage'] = yardage
                        self.lastPlayDict['completion'] = False
                        return yardage
                else:
                    interceptRoll = randint(1,100)
                    if interceptRoll <= 10:
                        yardage = 1003
                        passer.gameStatsDict['ints'] += 1 
                        passer.updateInGameConfidence(-.02)
                        defense.updateGameConfidence(.02)
                        defense.gameDefenseStats['ints'] += 1
                        self.lastPlayDict['play'] = PlayType.Pass.value
                        self.lastPlayDict['passer'] = passer
                        self.lastPlayDict['receiver'] = receiver
                        self.lastPlayDict['yardage'] = yardage
                        self.lastPlayDict['result'] = PlayResult.Interception.value
                        return yardage
                    else:
                        yardage = 0   
                        passer.updateInGameConfidence(-.005)     
                        self.lastPlayDict['play'] = PlayType.Pass.value
                        self.lastPlayDict['passer'] = passer
                        self.lastPlayDict['receiver'] = receiver
                        self.lastPlayDict['yardage'] = yardage
                        self.lastPlayDict['completion'] = False
                        return yardage

            elif passType.value == 3:
                if passTarget < 4:
                    receiver = te   
                else:
                    receiver = wr
                accRoll = randint(1,100)
                receiverYACRating = (receiver.gameAttributes.agility+receiver.gameAttributes.speed+receiver.gameAttributes.playMakingAbility)/3
                if accRoll < (passer.gameAttributes.overallRating - (defense.passDefenseRating/5)):
                    dropRoll = round(randint(1,100) + (defense.passDefenseRating/10))
                    if receiver.gameAttributes.overallRating > dropRoll:
                        passYards = randint(11,20)
                        yac = 0
                        x = randint(1,10)
                        if receiverYACRating > defense.defenseRating:
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
                        defense.gameDefenseStats['passYardsAlwd'] += yardage
                        defense.gameDefenseStats['totalYardsAlwd'] += yardage
                        passer.updateInGameConfidence(.01)
                        receiver.updateInGameConfidence(.01)
                        self.lastPlayDict['play'] = PlayType.Pass.value
                        self.lastPlayDict['passer'] = passer
                        self.lastPlayDict['receiver'] = receiver
                        self.lastPlayDict['yardage'] = yardage
                        self.lastPlayDict['completion'] = True
                        return yardage
                    else:
                        yardage = 0
                        receiver.gameStatsDict['passTargets'] += 1  
                        receiver.updateInGameConfidence(-.005)        
                        self.lastPlayDict['play'] = PlayType.Pass.value
                        self.lastPlayDict['passer'] = passer
                        self.lastPlayDict['receiver'] = receiver
                        self.lastPlayDict['yardage'] = yardage
                        self.lastPlayDict['completion'] = False
                        return yardage
                else:
                    interceptRoll = randint(1,100)
                    if interceptRoll <= 15:
                        yardage = 1003
                        passer.gameStatsDict['ints'] += 1 
                        passer.updateInGameConfidence(-.02)
                        defense.updateGameConfidence(.02)
                        defense.gameDefenseStats['ints'] += 1
                        self.lastPlayDict['play'] = PlayType.Pass.value
                        self.lastPlayDict['passer'] = passer
                        self.lastPlayDict['receiver'] = receiver
                        self.lastPlayDict['yardage'] = yardage
                        self.lastPlayDict['result'] = PlayResult.Interception.value
                        return yardage
                    else:
                        yardage = 0    
                        passer.updateInGameConfidence(-.005)
                        self.lastPlayDict['play'] = PlayType.Pass.value
                        self.lastPlayDict['passer'] = passer
                        self.lastPlayDict['receiver'] = receiver
                        self.lastPlayDict['yardage'] = yardage
                        self.lastPlayDict['completion'] = False
                        return yardage

    def playCaller(self, offense: FloosTeam.Team, defense: FloosTeam.Team):
        if self.currentQuarter == 5:
            x = randint(1,10)
            if self.yardsToEndzone <= 55 and self.yardsToEndzone > 40 and x > 7:
                return 1001
            if self.yardsToEndzone <= 40 and self.yardsToEndzone > 30 and x > 3:
                return 1001
            else:
                return 1001

        if self.totalPlays == 131:
            if self.homeTeam == offense and self.homeScore < self.awayScore:
                scoreDiff = self.awayScore - self.homeScore
                if scoreDiff <= 3 and self.yardsToEndzone < 50:
                    return 1001
                else:
                    self.homeTeam.inGamePush()
                    return self.passPlay(offense, defense, PassType.long)
            elif self.awayTeam == offense and self.awayScore < self.homeScore:
                scoreDiff = self.homeScore - self.awayScore
                if scoreDiff <= 3 and self.yardsToEndzone < 50:
                    return 1001
                else:
                    self.awayTeam.inGamePush()
                    return self.passPlay(offense, defense, PassType.long)
            else:
                return self.passPlay(offense, defense, PassType.long)
        elif self.down <= 2:
            if self.currentQuarter == 4:
                if self.homeTeam == offense and self.homeScore < self.awayScore:
                    scoreDiff = self.awayScore - self.homeScore
                    x = randint(1,10)
                    if x < 4:
                        return self.runPlay(offense, defense)
                    elif x >= 4 and x < 9:
                        return self.passPlay(offense, defense, PassType.medium)
                    else:
                        return self.passPlay(offense, defense, PassType.long)
                elif self.awayTeam == offense and self.awayScore < self.homeScore:
                    scoreDiff = self.homeScore - self.awayScore
                    x = randint(1,10)
                    if x < 4:
                        return self.runPlay(offense, defense)
                    elif x >= 4 and x < 9:
                        return self.passPlay(offense, defense, PassType.medium)
                    else:
                        return self.passPlay(offense, defense, PassType.long)
            elif self.yardsToEndzone <= 20:
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
            if self.currentQuarter == 4:
                if self.homeTeam == offense and self.homeScore < self.awayScore:
                    scoreDiff = self.awayScore - self.homeScore
                    x = randint(1,10)
                    if x < 3:
                        return self.runPlay(offense, defense)
                    elif x >= 3 and x < 7:
                        return self.passPlay(offense, defense, PassType.medium)
                    else:
                        return self.passPlay(offense, defense, PassType.long)
                elif self.awayTeam == offense and self.awayScore < self.homeScore:
                    scoreDiff = self.homeScore - self.awayScore
                    x = randint(1,10)
                    if x < 3:
                        return self.runPlay(offense, defense)
                    elif x >= 3 and x < 7:
                        return self.passPlay(offense, defense, PassType.medium)
                    else:
                        return self.passPlay(offense, defense, PassType.long)
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
                scoreDiff = self.homeScore - self.awayScore
                if self.totalPlays > 120 and self.yardsToEndzone < 20:
                    if scoreDiff <= 3:
                        return 1001
                    else:
                        return self.passPlay(offense, defense, PassType.medium)
                elif self.totalPlays > 120 and self.yardsToEndzone > 20:
                    if self.yardsToEndzone < 45 and scoreDiff <= 3:
                        x = randint(1,10)
                        if x > 5:
                            return 1001
                        else:
                            return self.passPlay(offense, defense, PassType.long)
                    else:
                        return self.passPlay(offense, defense, PassType.long)
                elif self.yardsToFirstDown <= 2:
                    if self.yardsToSafety > 20:
                        if self.yardsToEndzone <= 30:
                            return 1001
                        else:
                            x = randint(1,3)
                            if x <= 2:
                                return self.passPlay(offense, defense, PassType.short)
                            else:
                                return self.passPlay(offense, defense, PassType.medium)
                    else:
                        x = randint(1,10)
                        if x > 8:
                            self.lastPlayDict['play'] = PlayType.Punt.value
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
                    if self.yardsToEndzone > 30 and self.yardsToEndzone < 55 and self.yardsToFirstDown > 6:
                        x = randint(1,10)
                        if x > 3:
                            return 1001
                        else:
                            return self.passPlay(offense, defense, PassType.medium)
                    else:
                        return self.passPlay(offense, defense, PassType.medium)
            elif self.currentQuarter == 4 and self.homeTeam == offense and self.homeScore < self.awayScore:
                scoreDiff = self.awayScore - self.homeScore
                if self.totalPlays > 120 and self.yardsToEndzone < 20:
                    if scoreDiff <= 3:
                        return 1001
                    else:
                        return self.passPlay(offense, defense, PassType.medium)
                elif self.totalPlays > 120 and self.yardsToEndzone > 20:
                    if self.yardsToEndzone < 45 and scoreDiff <= 3:
                        x = randint(1,10)
                        if x > 5:
                            return 1001
                        else:
                            return self.passPlay(offense, defense, PassType.long)
                    else:
                        return self.passPlay(offense, defense, PassType.long)
                elif self.yardsToFirstDown <= 2:
                    if self.yardsToSafety > 20:
                        if self.yardsToEndzone <= 30:
                            return 1001
                        else:
                            x = randint(1,3)
                            if x <= 2:
                                return self.passPlay(offense, defense, PassType.short)
                            else:
                                return self.passPlay(offense, defense, PassType.medium)
                    else:
                        x = randint(1,10)
                        if x > 8:
                            self.lastPlayDict['play'] = PlayType.Punt.value
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
                    if self.yardsToEndzone > 30 and self.yardsToEndzone < 55 and self.yardsToFirstDown > 6:
                        x = randint(1,10)
                        if x > 3:
                            return 1001
                        else:
                            return self.passPlay(offense, defense, PassType.medium)
                    else:
                        return self.passPlay(offense, defense, PassType.medium)
            elif self.currentQuarter == 4 and self.homeTeam == offense and self.homeScore > self.awayScore:
                if self.yardsToEndzone < 40:
                    return 1001
                else:
                    self.lastPlayDict['play'] = PlayType.Punt.value
                    return 1002
            elif self.currentQuarter == 4 and self.awayTeam == offense and self.awayScore > self.homeScore:
                if self.yardsToEndzone < 40:
                    return 1001
                else:
                    self.lastPlayDict['play'] = PlayType.Punt.value
                    return 1002
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
            elif self.yardsToEndzone <= 35:
                if self.yardsToFirstDown <= 2:
                    x = randint(1,10)
                    if x >= 2:
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
                    if x < 9:
                        return 1001
                    else:
                        return self.passPlay(offense, defense, PassType.medium)
            elif self.yardsToEndzone <= 50:
                    x = randint(1,10)
                    if x < 6:
                        return 1001
                    else:
                        self.lastPlayDict['play'] = PlayType.Punt.value
                        return 1002
            elif self.yardsToSafety <= 20:
                self.lastPlayDict['play'] = PlayType.Punt.value
                return 1002
            else:
                if self.yardsToFirstDown <= 2:
                    x = randint(1,10)
                    if x < 8:
                        self.lastPlayDict['play'] = PlayType.Punt.value
                        return 1002
                    elif x >= 7 and x < 9:
                        return self.passPlay(offense, defense, PassType.short)
                    else:
                        return self.passPlay(offense, defense, PassType.medium)
                else:
                    x = randint(1,10)
                    if x < 10:
                        self.lastPlayDict['play'] = PlayType.Punt.value
                        return 1002
                    else:
                        y = randint(0,1)
                        if y == 0:
                            return self.passPlay(offense, defense, PassType.medium)
                        else:
                            return self.passPlay(offense, defense, PassType.long)

    def turnover(self, offense: FloosTeam.Team, defense: FloosTeam.Team, yards):
        self.offensiveTeam = defense
        self.defensiveTeam = offense
        self.yardsToEndzone = yards
        self.yardsToSafety = 100 - self.yardsToEndzone
        self.yardsToFirstDown = 10
        self.defensiveTeam.updateGameEnergy(self.driveLength/5)

    # def scoreChange(self):
    #     pass

    def formatPlayText(self, play):
        text = None
        if play['play'] == PlayType.Run.value:
            if play['result'] == PlayResult.Fumble.value:
                text = '{} Fumbles, {} recovers'.format(play['runner'].name, play['defense'].name)
            else:
                text = '{} runs for {} yards'.format(play['runner'].name, play['yardage'])
        elif play['play'] == PlayType.Pass.value:
            if play['sack']:
                text = '{} sacked for {} yards'.format(play['passer'].name, play['yardage'])
            elif play['completion']:
                text = '{} pass to {} complete for {} yards'.format(play['passer'].name, play['receiver'].name, play['yardage'])
            elif play['result'] == PlayResult.Interception.value:
                text = '{} pass intercepted'.format(play['passer'].name)
            else:
                text = '{} pass to {} incomplete'.format(play['passer'].name, play['receiver'].name)
        elif play['play'] == PlayType.FieldGoal.value:
            text = '{}yd Field Goal attempt by {}'.format(play['fgDistance'], play['kicker'].name)
        elif play['play'] == PlayType.Punt.value:
            text = '{} {}'.format(play['offense'].name, play['result'])
        
        play['playText'] = text

    def postgame(self):    
        if self.winningTeam.seasonTeamStats['streak'] >= 0:
            self.winningTeam.seasonTeamStats['streak'] += 1
        else:
            self.winningTeam.seasonTeamStats['streak'] = 1

        self.winningTeam.seasonTeamStats['Defense']['ints'] += self.winningTeam.gameDefenseStats['ints']
        self.winningTeam.seasonTeamStats['Defense']['fumRec'] += self.winningTeam.gameDefenseStats['fumRec']
        self.winningTeam.seasonTeamStats['Defense']['sacks'] += self.winningTeam.gameDefenseStats['sacks']
        self.winningTeam.seasonTeamStats['Defense']['runYardsAlwd'] += self.winningTeam.gameDefenseStats['runYardsAlwd']
        self.winningTeam.seasonTeamStats['Defense']['passYardsAlwd'] += self.winningTeam.gameDefenseStats['passYardsAlwd']
        self.winningTeam.seasonTeamStats['Defense']['totalYardsAlwd'] += self.winningTeam.gameDefenseStats['totalYardsAlwd']
        self.winningTeam.seasonTeamStats['Defense']['runTdsAlwd'] += self.winningTeam.gameDefenseStats['runTdsAlwd']
        self.winningTeam.seasonTeamStats['Defense']['passTdsAlwd'] += self.winningTeam.gameDefenseStats['passTdsAlwd']
        self.winningTeam.seasonTeamStats['Defense']['tdsAlwd'] += self.winningTeam.gameDefenseStats['tdsAlwd']
        self.winningTeam.seasonTeamStats['winPerc'] = round(self.winningTeam.seasonTeamStats['wins']/(self.winningTeam.seasonTeamStats['wins']+self.winningTeam.seasonTeamStats['losses']),3)
        self.winningTeam.seasonTeamStats['divWinPerc'] = round(self.winningTeam.seasonTeamStats['divWins']/(self.winningTeam.seasonTeamStats['divWins']+self.winningTeam.seasonTeamStats['divLosses']),3)
        self.winningTeam.gameDefenseStats = copy.deepcopy(FloosTeam.teamStatsDict['Defense'])

        if self.losingTeam.seasonTeamStats['streak'] >= 0:
            self.losingTeam.seasonTeamStats['streak'] = -1
        else:
            self.losingTeam.seasonTeamStats['streak'] -= 1

        self.losingTeam.seasonTeamStats['Defense']['ints'] += self.losingTeam.gameDefenseStats['ints']
        self.losingTeam.seasonTeamStats['Defense']['fumRec'] += self.losingTeam.gameDefenseStats['fumRec']
        self.losingTeam.seasonTeamStats['Defense']['sacks'] += self.losingTeam.gameDefenseStats['sacks']
        self.losingTeam.seasonTeamStats['Defense']['runYardsAlwd'] += self.losingTeam.gameDefenseStats['runYardsAlwd']
        self.losingTeam.seasonTeamStats['Defense']['passYardsAlwd'] += self.losingTeam.gameDefenseStats['passYardsAlwd']
        self.losingTeam.seasonTeamStats['Defense']['totalYardsAlwd'] += self.losingTeam.gameDefenseStats['totalYardsAlwd']
        self.losingTeam.seasonTeamStats['Defense']['runTdsAlwd'] += self.losingTeam.gameDefenseStats['runTdsAlwd']
        self.losingTeam.seasonTeamStats['Defense']['passTdsAlwd'] += self.losingTeam.gameDefenseStats['passTdsAlwd']
        self.losingTeam.seasonTeamStats['Defense']['tdsAlwd'] += self.losingTeam.gameDefenseStats['tdsAlwd']
        self.losingTeam.seasonTeamStats['winPerc'] = round(self.losingTeam.seasonTeamStats['wins']/(self.losingTeam.seasonTeamStats['wins']+self.losingTeam.seasonTeamStats['losses']),3)
        self.losingTeam.seasonTeamStats['divWinPerc'] = round(self.losingTeam.seasonTeamStats['divWins']/(self.losingTeam.seasonTeamStats['divWins']+self.losingTeam.seasonTeamStats['divLosses']),3)
        self.losingTeam.gameDefenseStats = copy.deepcopy(FloosTeam.teamStatsDict['Defense'])

        for player in self.homeTeam.rosterDict.values():
            player.postgameChanges()

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

            for k in player.gameStatsDict.keys():
                player.gameStatsDict[k] = 0
        for player in self.awayTeam.rosterDict.values():
            player.postgameChanges()

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

            for k in player.gameStatsDict.keys():
                player.gameStatsDict[k] = 0
            
            self.winningTeam.resetConfidence()
            self.losingTeam.resetDetermination()

    async def playGame(self):
        self.totalPlays = 0
        possReset = 80
        coinFlipWinner = None
        coinFlipLoser = None

        self.homeTeam.setRoster()
        self.awayTeam.setRoster()
        self.homeTeam.gameDefenseRating = self.homeTeam.defenseRating
        self.homeTeam.gameRunDefenseRating = self.homeTeam.runDefenseRating
        self.homeTeam.gamePassDefenseRating = self.homeTeam.passDefenseRating
        self.awayTeam.gameDefenseRating = self.awayTeam.defenseRating
        self.awayTeam.gameRunDefenseRating = self.awayTeam.runDefenseRating
        self.awayTeam.gamePassDefenseRating = self.awayTeam.passDefenseRating
        self.homeTeam.resetGameEnergy()
        self.awayTeam.resetGameEnergy()

        for player in self.homeTeam.rosterDict.values():
            player: FloosPlayer.Player
            player.gameAttributes = copy.deepcopy(player.attributes)
        for player in self.awayTeam.rosterDict.values():
            player: FloosPlayer.Player
            player.gameAttributes = copy.deepcopy(player.attributes)

        await asyncio.sleep(15)
        x = randint(0,1)
        if x == 0:
            self.offensiveTeam, coinFlipWinner = self.homeTeam
            self.defensiveTeam, coinFlipLoser = self.awayTeam
        else:
            self.offensiveTeam, coinFlipWinner = self.awayTeam
            self.defensiveTeam, coinFlipLoser = self.homeTeam

        self.status = GameStatus.Active

        while self.totalPlays < 132 or self.homeScore == self.awayScore:

            if self.totalPlays < 1:
                self.yardsToFirstDown = 10
                self.yardsToEndzone = 80
                self.yardsToSafety = 20

            self.down = 1
            self.driveLength = 0

            while self.down <= 4:

                if self.totalPlays < 33:
                    if self.currentQuarter != 1:
                        self.currentQuarter = 1
                        x = randint(1,100)
                        y = randint(1,100)
                        if x >= 95:
                            self.homeTeam.teamOverPerform()
                        elif x <= 5:
                            self.homeTeam.teamUnderPerform()
                        if y >= 95:
                            self.awayTeam.teamOverPerform()
                        elif y <= 5:
                            self.awayTeam.teamUnderPerform()
                elif self.totalPlays >= 33 and self.totalPlays < 66:
                    if self.currentQuarter != 2:
                        self.currentQuarter = 2
                elif self.totalPlays >= 66 and self.totalPlays < 100:
                    if self.totalPlays == 66:
                        self.isHalftime = True
                        await asyncio.sleep(60)
                        self.isHalftime = False
                    if self.currentQuarter != 3:
                        self.currentQuarter = 3
                        self.turnover(coinFlipLoser, coinFlipWinner, possReset)
                        self.down = 1
                        self.homeTeam.updateGameEnergy(10)
                        self.awayTeam.updateGameEnergy(10)
                        x = randint(1,100)
                        y = randint(1,100)
                        if x >= 95:
                            self.homeTeam.teamOverPerform()
                        elif x <= 5:
                            self.homeTeam.teamUnderPerform()
                        elif x > 80 and x <= 90:
                            self.homeTeam.resetDetermination()
                        if y >= 95:
                            self.awayTeam.teamOverPerform()
                        elif y <= 5:
                            self.awayTeam.teamUnderPerform()
                        elif y > 80 and y <= 90:
                            self.awayTeam.resetDetermination()
                elif self.totalPlays >= 100 and self.totalPlays < 132:
                    if self.currentQuarter != 4:
                        self.currentQuarter = 4
                    if self.homeScore > self.awayScore and (self.homeScore - self.awayScore) <= 14:
                        x = randint(1,10)
                        if x > 6:
                            self.awayTeam.resetDetermination()
                            self.awayTeam.inGamePush()
                        elif self.awayScore > self.homeScore and (self.awayScore - self.homeScore) <= 14:
                            x = randint(1,10)
                            if x > 6:
                                self.homeTeam.resetDetermination()
                                self.homeTeam.inGamePush()
                elif self.totalPlays >= 132:
                    if self.currentQuarter != 5:
                        self.currentQuarter = 5
                        self.isOvertime = True
                        x = randint(0,1)
                        if x == 0:
                            self.turnover(self.homeTeam, self.awayTeam, possReset)
                        else:
                            self.turnover(self.awayTeam, self.homeTeam, possReset)
                        self.down = 1
                        self.homeTeam.resetDetermination()
                        self.homeTeam.resetConfidence()
                        self.awayTeam.resetDetermination()
                        self.awayTeam.resetConfidence()
                        


                if self.totalPlays > 0 or self.currentQuarter == 5:
                    self.formatPlayText(self.lastPlayDict)
                    self.lastPlayDict['homeTeamScore'] = self.homeScore
                    self.lastPlayDict['awayTeamScore'] = self.awayScore
                    self.lastPlayDict['quarter'] = self.currentQuarter
                    self.lastPlayDict['playsLeft'] = 132 - self.totalPlays
                    self.lastPlayDict['color'] = self.lastPlayDict['offense'].color
                    if self.lastPlayDict['result'] == PlayResult.FieldGoalGood.value or self.lastPlayDict['result'] == PlayResult.Safety.value or self.lastPlayDict['result'] == 'Touchdown, XP Good' or self.lastPlayDict['result'] == 'Touchdown, XP No Good':
                        self.scoringPlaysList.insert(0, self.lastPlayDict)
                        self.lastPlayDict['scoreChange'] = True
                    self.playsList.insert(0,self.lastPlayDict)
                if self.totalPlays == 132 and self.homeScore != self.awayScore:
                    break

                if self.yardsToEndzone > 50:
                    self.yardLine = '{0} {1}'.format(self.offensiveTeam.abbr, (100-self.yardsToEndzone))
                else:
                    self.yardLine = '{0} {1}'.format(self.defensiveTeam.abbr, self.yardsToEndzone)

                self.lastPlayDict = copy.deepcopy(playDict)
                
                self.lastPlayDict['offense'] = self.offensiveTeam
                self.lastPlayDict['defense'] = self.defensiveTeam
                self.lastPlayDict['down'] = self.down
                self.lastPlayDict['yardLine'] = self.yardLine
                if self.yardsToEndzone <= 10:
                    self.lastPlayDict['yardsTo1st'] = 'Goal'
                else:
                    self.lastPlayDict['yardsTo1st'] = self.yardsToFirstDown
                
                await asyncio.sleep(randint(15, 30))
                yardsGained = self.playCaller(self.offensiveTeam, self.defensiveTeam)
                self.totalPlays += 1
                self.driveLength += 1
                if self.offensiveTeam is self.homeTeam:
                    self.homePlaysTotal =+ 1
                if self.offensiveTeam is self.awayTeam:
                    self.awayPlaysTotal =+ 1
                self.defensiveTeam.updateGameEnergy(-.75)


                if yardsGained == 1001:
                    if self.fieldGoalTry(self.offensiveTeam):
                        if self.offensiveTeam == self.homeTeam:
                            self.homeScore += 3
                            if self.currentQuarter == 1:
                                self.homeScoreQ1 += 3
                            elif self.currentQuarter == 2:
                                self.homeScoreQ2 += 3
                            elif self.currentQuarter == 3:
                                self.homeScoreQ3 += 3
                            elif self.currentQuarter == 4:
                                self.homeScoreQ4 += 3
                        elif self.offensiveTeam == self.awayTeam:
                            self.awayScore += 3
                            if self.currentQuarter == 1:
                                self.awayScoreQ1 += 3
                            elif self.currentQuarter == 2:
                                self.awayScoreQ2 += 3
                            elif self.currentQuarter == 3:
                                self.awayScoreQ3 += 3
                            elif self.currentQuarter == 4:
                                self.awayScoreQ4 += 3
                        self.lastPlayDict['result'] = PlayResult.FieldGoalGood.value
                        self.lastPlayDict['isFg'] = True
                        if self.currentQuarter == 5 and self.homeScore != self.awayScore:
                            break
                        else:
                            self.turnover(self.offensiveTeam, self.defensiveTeam, possReset)
                            break
                    else:
                        self.lastPlayDict['result'] = PlayResult.FieldGoalNoGood.value
                        self.turnover(self.offensiveTeam, self.defensiveTeam, self.yardsToSafety)
                        break
                elif yardsGained == 1002:
                    self.lastPlayDict['result'] = PlayResult.Punt.value
                    puntDistance = randint(30, 60)
                    if puntDistance >= self.yardsToEndzone:
                        puntDistance = self.yardsToEndzone - 20
                    newYards = 100 - (self.yardsToEndzone - puntDistance)
                    self.turnover(self.offensiveTeam, self.defensiveTeam, newYards)
                    break
                elif yardsGained == 1003 or yardsGained == 1004:
                    self.turnover(self.offensiveTeam, self.defensiveTeam, self.yardsToSafety)
                    if self.offensiveTeam is self.homeTeam:
                        self.homeTurnoversTotal += 1
                    elif self.offensiveTeam is self.awayTeam:
                        self.awayTurnoversTotal += 1
                    break
                else:
                    if yardsGained >= self.yardsToEndzone:
                        if self.lastPlayDict['play'] == 'Run':
                            self.lastPlayDict['runner'].gameStatsDict['tds'] += 1
                            self.lastPlayDict['runner'].updateInGameConfidence(.01)
                            self.lastPlayDict['defense'].gameDefenseStats['runTdsAlwd'] += 1
                            self.lastPlayDict['defense'].gameDefenseStats['tdsAlwd'] += 1
                        elif self.lastPlayDict['play'] == 'Pass':
                            self.lastPlayDict['passer'].gameStatsDict['tds'] += 1
                            self.lastPlayDict['receiver'].gameStatsDict['tds'] += 1
                            self.lastPlayDict['defense'].gameDefenseStats['passTdsAlwd'] += 1
                            self.lastPlayDict['defense'].gameDefenseStats['tdsAlwd'] += 1
                            self.lastPlayDict['passer'].updateInGameConfidence(.01)
                            self.lastPlayDict['receiver'].updateInGameConfidence(.01)

                        if self.offensiveTeam == self.homeTeam:
                            self.homeScore += 6
                            if self.currentQuarter == 1:
                                self.homeScoreQ1 += 6
                            elif self.currentQuarter == 2:
                                self.homeScoreQ2 += 6
                            elif self.currentQuarter == 3:
                                self.homeScoreQ3 += 6
                            elif self.currentQuarter == 4:
                                self.homeScoreQ4 += 6

                        elif self.offensiveTeam == self.awayTeam:
                            self.awayScore += 6
                            if self.currentQuarter == 1:
                                self.awayScoreQ1 += 6
                            elif self.currentQuarter == 2:
                                self.awayScoreQ2 += 6
                            elif self.currentQuarter == 3:
                                self.awayScoreQ3 += 6
                            elif self.currentQuarter == 4:
                                self.awayScoreQ4 += 6

                        #self.scoreChange()

                        if self.extraPointTry(self.offensiveTeam):
                            self.lastPlayDict['result'] = '{}, {}'.format(PlayResult.Touchdown.value, PlayResult.ExtraPointGood.value)
                            if self.offensiveTeam == self.homeTeam:
                                self.homeScore += 1
                                if self.currentQuarter == 1:
                                    self.homeScoreQ1 += 1
                                elif self.currentQuarter == 2:
                                    self.homeScoreQ2 += 1
                                elif self.currentQuarter == 3:
                                    self.homeScoreQ3 += 1
                                elif self.currentQuarter == 4:
                                    self.homeScoreQ4 += 1
                            elif self.offensiveTeam == self.awayTeam:
                                self.awayScore += 1
                                if self.currentQuarter == 1:
                                    self.awayScoreQ1 += 1
                                elif self.currentQuarter == 2:
                                    self.awayScoreQ2 += 1
                                elif self.currentQuarter == 3:
                                    self.awayScoreQ3 += 1
                                elif self.currentQuarter == 4:
                                    self.awayScoreQ4 += 1  
                        else:
                            self.lastPlayDict['result'] = '{}, {}'.format(PlayResult.Touchdown.value, PlayResult.ExtraPointNoGood.value)
                        self.lastPlayDict['isTd'] = True
                        self.turnover(self.offensiveTeam, self.defensiveTeam, possReset)
                        break

                    elif yardsGained >= self.yardsToFirstDown:
                        self.down = 1
                        if self.offensiveTeam is self.homeTeam:
                            self.home1stDownsTotal += 1
                        elif self.offensiveTeam is self.awayTeam:
                            self.away1stDownsTotal += 1
                        if self.yardsToEndzone < 10:
                            self.yardsToFirstDown = self.yardsToEndzone
                        else:
                            self.yardsToFirstDown = 10
                        self.yardsToSafety += yardsGained
                        self.yardsToEndzone -= yardsGained
                        self.lastPlayDict['result'] = PlayResult.FirstDown.value
                        continue

                    elif (self.yardsToSafety + yardsGained) <= 0:
                        if self.defensiveTeam == self.homeTeam:
                            self.homeScore += 2
                            if self.currentQuarter == 1:
                                self.homeScoreQ1 += 2
                            elif self.currentQuarter == 2:
                                self.homeScoreQ2 += 2
                            elif self.currentQuarter == 3:
                                self.homeScoreQ3 += 2
                            elif self.currentQuarter == 4:
                                self.homeScoreQ4 += 2

                        elif self.defensiveTeam == self.awayTeam:
                            self.awayScore += 2
                            if self.currentQuarter == 1:
                                self.awayScoreQ1 += 2
                            elif self.currentQuarter == 2:
                                self.awayScoreQ2 += 2
                            elif self.currentQuarter == 3:
                                self.awayScoreQ3 += 2
                            elif self.currentQuarter == 4:
                                self.awayScoreQ4 += 2

                        self.lastPlayDict['result'] = PlayResult.Safety.value
                        self.lastPlayDict['isSafety'] = True
                        #self.scoreChange()
                        self.turnover(self.offensiveTeam, self.defensiveTeam, possReset)
                        break

                    elif yardsGained < self.yardsToFirstDown:
                        if self.down < 4:
                            self.yardsToEndzone -= yardsGained
                            self.yardsToSafety += yardsGained
                            self.yardsToFirstDown -= yardsGained
                            self.down += 1
                            if self.down == 2:
                                self.lastPlayDict['result'] = '{}'.format(PlayResult.SecondDown.value)
                            elif self.down == 3:
                                self.lastPlayDict['result'] = '{}'.format(PlayResult.ThirdDown.value)
                            elif self.down == 4:
                                self.lastPlayDict['result'] = '{}'.format(PlayResult.FourthDown.value)
                            continue
                        else:
                            self.lastPlayDict['result'] = PlayResult.TurnoverOnDowns.value
                            self.turnover(self.offensiveTeam, self.defensiveTeam, self.yardsToSafety)
                            break
            
        else:
            self.formatPlayText(self.lastPlayDict)
            self.playsList.insert(0,self.lastPlayDict) 

        if self.awayScore > self.homeScore:
            self.winningTeam = self.awayTeam
            self.losingTeam = self.homeTeam
            self.gameDict['score'] = '{0} - {1}'.format(self.awayScore, self.homeScore)
        elif self.homeScore > self.awayScore:
            self.winningTeam = self.homeTeam
            self.losingTeam = self.awayTeam
            self.gameDict['score'] = '{0} - {1}'.format(self.homeScore, self.awayScore)

        self.winningTeam.seasonTeamStats['wins'] += 1
        self.losingTeam.seasonTeamStats['losses'] += 1

        if self.winningTeam.division is self.losingTeam.division:
            self.winningTeam.seasonTeamStats['divWins'] += 1
            self.losingTeam.seasonTeamStats['divLosses'] += 1


        self.gameDict['winningTeam'] = self.winningTeam.name
        self.gameDict['losingTeam'] = self.losingTeam.name
        self.saveGameData()
        self.winningTeam.updateRating()
        self.losingTeam.updateRating()
        self.status = GameStatus.Final



