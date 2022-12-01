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
    TouchdownXP = 'Touchdown, XP is Good'
    TouchdownNoXP = 'Touchdown, XP No Good'
    Safety = 'Safety'
    Fumble = 'Fumble'
    Interception = 'Interception'

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
        self.homeScoreOT = 0
        self.awayScoreQ1 = 0
        self.awayScoreQ2 = 0
        self.awayScoreQ3 = 0
        self.awayScoreQ4 = 0
        self.awayScoreOT = 0
        self.currentQuarter = 0
        self.homePlaysTotal = 0
        self.awayPlaysTotal = 0
        self.home1stDownsTotal = 0
        self.away1stDownsTotal = 0
        self.homeTurnoversTotal = 0
        self.awayTurnoversTotal = 0
        self.isHalftime = False
        self.isOvertime = False
        self.isRegularSeasonGame = None
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
        self.play: Play = None
        self.gameDict = {}
        self.playsList: list[Play] = []
        self.scoringPlaysList: list[Play] = []

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

        for pos, player in self.homeTeam.rosterDict.items():
            player: FloosPlayer.Player
            playerDict = {}
            if player.position is FloosPlayer.Position.QB:
                homeTeamPassYards += player.gameStatsDict['passYards']
                player.gameStatsDict['totalYards'] = player.gameStatsDict['passYards']
                if player.gameStatsDict['passComp'] > 0:
                    player.gameStatsDict['ypc'] = round(player.gameStatsDict['passYards']/player.gameStatsDict['passComp'],2)
                    player.gameStatsDict['passCompPerc'] = round((player.gameStatsDict['passComp']/player.gameStatsDict['passAtt'])*100)
            elif player.position is FloosPlayer.Position.RB:
                homeTeamRushYards += player.gameStatsDict['runYards']
                player.gameStatsDict['totalYards'] = player.gameStatsDict['rcvYards'] + player.gameStatsDict['runYards']
                if player.gameStatsDict['carries'] > 0:
                    player.gameStatsDict['ypc'] = round(player.gameStatsDict['runYards']/player.gameStatsDict['carries'],2)
                if player.gameStatsDict['receptions'] > 0:
                    player.gameStatsDict['ypr'] = round(player.gameStatsDict['rcvYards']/player.gameStatsDict['receptions'],2)
                    player.gameStatsDict['rcvPerc'] = round((player.gameStatsDict['receptions']/player.gameStatsDict['passTargets'])*100)
            elif player.position is FloosPlayer.Position.WR or player.position is FloosPlayer.Position.TE:
                player.gameStatsDict['totalYards'] = player.gameStatsDict['rcvYards']
                if player.gameStatsDict['receptions'] > 0:
                    player.gameStatsDict['ypr'] = round(player.gameStatsDict['rcvYards']/player.gameStatsDict['receptions'],2)
                    player.gameStatsDict['rcvPerc'] = round((player.gameStatsDict['receptions']/player.gameStatsDict['passTargets'])*100)
            elif player.position is FloosPlayer.Position.K:
                if player.gameStatsDict['fgs'] > 0:
                    player.gameStatsDict['fgPerc'] = round((player.gameStatsDict['fgs']/player.gameStatsDict['fgAtt'])*100)
                else:
                    player.gameStatsDict['fgPerc'] = 0

            playerDict['name'] = player.name
            playerDict['ratingStars'] = player.playerTier.value
            playerDict['gameStats'] = copy.deepcopy(player.gameStatsDict)

            homeTeamStatsDict[pos] = playerDict

        for pos, player in self.awayTeam.rosterDict.items():
            playerDict = {}
            if player.position is FloosPlayer.Position.QB:
                awayTeamPassYards += player.gameStatsDict['passYards']
                player.gameStatsDict['totalYards'] = player.gameStatsDict['passYards']
                if player.gameStatsDict['passComp'] > 0:
                    player.gameStatsDict['ypc'] = round(player.gameStatsDict['passYards']/player.gameStatsDict['passComp'],2)
                    player.gameStatsDict['passCompPerc'] = round((player.gameStatsDict['passComp']/player.gameStatsDict['passAtt'])*100)
            elif player.position is FloosPlayer.Position.RB:
                awayTeamRushYards += player.gameStatsDict['runYards']
                player.gameStatsDict['totalYards'] = player.gameStatsDict['rcvYards'] + player.gameStatsDict['runYards']
                if player.gameStatsDict['carries'] > 0:
                    player.gameStatsDict['ypc'] = round(player.gameStatsDict['runYards']/player.gameStatsDict['carries'],2)
                if player.gameStatsDict['receptions'] > 0:
                    player.gameStatsDict['ypr'] = round(player.gameStatsDict['rcvYards']/player.gameStatsDict['receptions'],2)
                    player.gameStatsDict['rcvPerc'] = round((player.gameStatsDict['receptions']/player.gameStatsDict['passTargets'])*100)
            elif player.position is FloosPlayer.Position.WR or player.position is FloosPlayer.Position.TE:
                player.gameStatsDict['totalYards'] = player.gameStatsDict['rcvYards']
                if player.gameStatsDict['receptions'] > 0:
                    player.gameStatsDict['ypr'] = round(player.gameStatsDict['rcvYards']/player.gameStatsDict['receptions'],2)
                    player.gameStatsDict['rcvPerc'] = round((player.gameStatsDict['receptions']/player.gameStatsDict['passTargets'])*100)
            elif player.position is FloosPlayer.Position.K:
                if player.gameStatsDict['fgs'] > 0:
                    player.gameStatsDict['fgPerc'] = round((player.gameStatsDict['fgs']/player.gameStatsDict['fgAtt'])*100)
                else:
                    player.gameStatsDict['fgPerc'] = 0

            playerDict['name'] = player.name
            playerDict['ratingStars'] = player.playerTier.value
            playerDict['gameStats'] = copy.deepcopy(player.gameStatsDict)

            awayTeamStatsDict[pos] = playerDict

        homeTeamTotalYards = homeTeamPassYards + homeTeamRushYards
        awayTeamTotalYards = awayTeamPassYards + awayTeamRushYards

        homeTeamStatsDict['passYards'] = homeTeamPassYards
        homeTeamStatsDict['rushYards'] = homeTeamRushYards
        homeTeamStatsDict['totalYards'] = homeTeamTotalYards
        homeTeamStatsDict['defenseRating'] = self.homeTeam.defenseTier
        homeTeamStatsDict['teamName'] = self.homeTeam.name
        homeTeamStatsDict['teamCity'] = self.homeTeam.city
        homeTeamStatsDict['teamcolor'] = self.homeTeam.color
        homeTeamStatsDict['teamAbbr'] = self.homeTeam.abbr
        homeTeamStatsDict['id'] = self.homeTeam.id
        homeTeamStatsDict['record'] = '{}-{}'.format(self.homeTeam.seasonTeamStats['wins'], self.homeTeam.seasonTeamStats['losses'])
        homeTeamStatsDict['score'] = self.homeScore
        homeTeamStatsDict['qtr1pts'] = self.homeScoreQ1
        homeTeamStatsDict['qtr2pts'] = self.homeScoreQ2
        homeTeamStatsDict['qtr3pts'] = self.homeScoreQ3
        homeTeamStatsDict['qtr4pts'] = self.homeScoreQ4
        homeTeamStatsDict['OTpts'] = self.homeScoreOT
        homeTeamStatsDict['1stDowns'] = self.home1stDownsTotal
        homeTeamStatsDict['totalPlays'] = self.homePlaysTotal
        homeTeamStatsDict['turnovers'] = self.homeTurnoversTotal
        homeTeamStatsDict['sacks'] = self.homeTeam.gameDefenseStats['sacks']
        homeTeamStatsDict['safeties'] = self.homeTeam.gameDefenseStats['safeties']

        awayTeamStatsDict['passYards'] = awayTeamPassYards
        awayTeamStatsDict['rushYards'] = awayTeamRushYards
        awayTeamStatsDict['totalYards'] = awayTeamTotalYards
        awayTeamStatsDict['defenseRating'] = self.awayTeam.defenseTier
        awayTeamStatsDict['teamName'] = self.awayTeam.name
        awayTeamStatsDict['teamCity'] = self.awayTeam.city
        awayTeamStatsDict['teamcolor'] = self.awayTeam.color
        awayTeamStatsDict['teamAbbr'] = self.awayTeam.abbr
        awayTeamStatsDict['id'] = self.awayTeam.id
        awayTeamStatsDict['record'] = '{}-{}'.format(self.awayTeam.seasonTeamStats['wins'], self.awayTeam.seasonTeamStats['losses'])
        awayTeamStatsDict['score'] = self.awayScore
        awayTeamStatsDict['qtr1pts'] = self.awayScoreQ1
        awayTeamStatsDict['qtr2pts'] = self.awayScoreQ2
        awayTeamStatsDict['qtr3pts'] = self.awayScoreQ3
        awayTeamStatsDict['qtr4pts'] = self.awayScoreQ4
        awayTeamStatsDict['OTpts'] = self.awayScoreOT
        awayTeamStatsDict['1stDowns'] = self.away1stDownsTotal
        awayTeamStatsDict['totalPlays'] = self.awayPlaysTotal
        awayTeamStatsDict['turnovers'] = self.awayTurnoversTotal
        awayTeamStatsDict['sacks'] = self.awayTeam.gameDefenseStats['sacks']
        awayTeamStatsDict['safeties'] = self.awayTeam.gameDefenseStats['safeties']

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
        else:
            down = '1st'
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
        homeTeamOffenseStatsDict = {}
        awayTeamOffenseStatsDict = {}
        homeTeamStatsDict = {}
        awayTeamStatsDict = {}
        homeTeamPassYards = 0
        awayTeamPassYards = 0
        homeTeamRushYards = 0
        awayTeamRushYards = 0
        homeTeamTotalYards = 0
        awayTeamTotalYards = 0

        gameStatsDict = {}

        for pos, player in self.homeTeam.rosterDict.items():
            player: FloosPlayer.Player
            playerDict = {}
            if player.position is FloosPlayer.Position.QB:
                homeTeamPassTds = player.gameStatsDict['tds']
                homeTeamPassYards += player.gameStatsDict['passYards']
                player.gameStatsDict['totalYards'] = player.gameStatsDict['passYards']
                if player.gameStatsDict['passComp'] > 0:
                    player.gameStatsDict['ypc'] = round(player.gameStatsDict['passYards']/player.gameStatsDict['passComp'],2)
                    player.gameStatsDict['passCompPerc'] = round((player.gameStatsDict['passComp']/player.gameStatsDict['passAtt'])*100)
            elif player.position is FloosPlayer.Position.RB:
                homeTeamRushYards += player.gameStatsDict['runYards']
                homeTeamRushTds = player.gameStatsDict['runTds']
                player.gameStatsDict['totalYards'] = player.gameStatsDict['rcvYards'] + player.gameStatsDict['runYards']
                if player.gameStatsDict['carries'] > 0:
                    player.gameStatsDict['ypc'] = round(player.gameStatsDict['runYards']/player.gameStatsDict['carries'],2)
                if player.gameStatsDict['receptions'] > 0:
                    player.gameStatsDict['ypr'] = round(player.gameStatsDict['rcvYards']/player.gameStatsDict['receptions'],2)
                    player.gameStatsDict['rcvPerc'] = round((player.gameStatsDict['receptions']/player.gameStatsDict['passTargets'])*100)
            elif player.position is FloosPlayer.Position.WR or player.position is FloosPlayer.Position.TE:
                player.gameStatsDict['totalYards'] = player.gameStatsDict['rcvYards']
                if player.gameStatsDict['receptions'] > 0:
                    player.gameStatsDict['ypr'] = round(player.gameStatsDict['rcvYards']/player.gameStatsDict['receptions'],2)
                    player.gameStatsDict['rcvPerc'] = round((player.gameStatsDict['receptions']/player.gameStatsDict['passTargets'])*100)
            elif player.position is FloosPlayer.Position.K:
                homeTeamFgs = player.gameStatsDict['fgs']
                if player.gameStatsDict['fgs'] > 0:
                    player.gameStatsDict['fgPerc'] = round((player.gameStatsDict['fgs']/player.gameStatsDict['fgAtt'])*100)
                else:
                    player.gameStatsDict['fgPerc'] = 0

            playerDict['name'] = player.name
            playerDict['ratingStars'] = player.playerTier.value
            playerDict['gameStats'] = copy.deepcopy(player.gameStatsDict)

            homeTeamStatsDict[pos] = playerDict

        for pos, player in self.awayTeam.rosterDict.items():
            playerDict = {}
            if player.position is FloosPlayer.Position.QB:
                awayTeamPassYards += player.gameStatsDict['passYards']
                awayTeamPassTds = player.gameStatsDict['tds']
                player.gameStatsDict['totalYards'] = player.gameStatsDict['passYards']
                if player.gameStatsDict['passComp'] > 0:
                    player.gameStatsDict['ypc'] = round(player.gameStatsDict['passYards']/player.gameStatsDict['passComp'],2)
                    player.gameStatsDict['passCompPerc'] = round((player.gameStatsDict['passComp']/player.gameStatsDict['passAtt'])*100)
            elif player.position is FloosPlayer.Position.RB:
                awayTeamRushYards += player.gameStatsDict['runYards']
                awayTeamRushTds = player.gameStatsDict['runTds']
                player.gameStatsDict['totalYards'] = player.gameStatsDict['rcvYards'] + player.gameStatsDict['runYards']
                if player.gameStatsDict['carries'] > 0:
                    player.gameStatsDict['ypc'] = round(player.gameStatsDict['runYards']/player.gameStatsDict['carries'],2)
                if player.gameStatsDict['receptions'] > 0:
                    player.gameStatsDict['ypr'] = round(player.gameStatsDict['rcvYards']/player.gameStatsDict['receptions'],2)
                    player.gameStatsDict['rcvPerc'] = round((player.gameStatsDict['receptions']/player.gameStatsDict['passTargets'])*100)
            elif player.position is FloosPlayer.Position.WR or player.position is FloosPlayer.Position.TE:
                player.gameStatsDict['totalYards'] = player.gameStatsDict['rcvYards']
                if player.gameStatsDict['receptions'] > 0:
                    player.gameStatsDict['ypr'] = round(player.gameStatsDict['rcvYards']/player.gameStatsDict['receptions'],2)
                    player.gameStatsDict['rcvPerc'] = round((player.gameStatsDict['receptions']/player.gameStatsDict['passTargets'])*100)
            elif player.position is FloosPlayer.Position.K:
                awayTeamFgs = player.gameStatsDict['fgs']
                if player.gameStatsDict['fgs'] > 0:
                    player.gameStatsDict['fgPerc'] = round((player.gameStatsDict['fgs']/player.gameStatsDict['fgAtt'])*100)
                else:
                    player.gameStatsDict['fgPerc'] = 0

            playerDict['name'] = player.name
            playerDict['ratingStars'] = player.playerTier.value
            playerDict['gameStats'] = copy.deepcopy(player.gameStatsDict)

            awayTeamStatsDict[pos] = playerDict

        homeTeamTotalYards = homeTeamPassYards + homeTeamRushYards
        awayTeamTotalYards = awayTeamPassYards + awayTeamRushYards

        homeTeamOffenseStatsDict['passYards'] = homeTeamPassYards
        homeTeamOffenseStatsDict['rushYards'] = homeTeamRushYards
        homeTeamOffenseStatsDict['totalYards'] = homeTeamTotalYards
        homeTeamOffenseStatsDict['passTds'] = homeTeamPassTds
        homeTeamOffenseStatsDict['runTds'] = homeTeamRushTds
        homeTeamOffenseStatsDict['tds'] = homeTeamPassTds + homeTeamRushTds
        homeTeamOffenseStatsDict['fgs'] = homeTeamFgs
        homeTeamOffenseStatsDict['score'] = self.homeScore
        homeTeamStatsDict['offense'] = homeTeamOffenseStatsDict
        homeTeamStatsDict['defense'] = self.homeTeam.gameDefenseStats
        homeTeamStatsDict['defenseRating'] = self.homeTeam.defenseTier
        homeTeamStatsDict['teamName'] = self.homeTeam.name
        homeTeamStatsDict['teamCity'] = self.homeTeam.city
        homeTeamStatsDict['teamcolor'] = self.homeTeam.color
        homeTeamStatsDict['teamAbbr'] = self.homeTeam.abbr
        homeTeamStatsDict['id'] = self.homeTeam.id
        homeTeamStatsDict['record'] = '{}-{}'.format(self.homeTeam.seasonTeamStats['wins'], self.homeTeam.seasonTeamStats['losses'])
        homeTeamStatsDict['score'] = self.homeScore
        homeTeamStatsDict['qtr1pts'] = self.homeScoreQ1
        homeTeamStatsDict['qtr2pts'] = self.homeScoreQ2
        homeTeamStatsDict['qtr3pts'] = self.homeScoreQ3
        homeTeamStatsDict['qtr4pts'] = self.homeScoreQ4
        homeTeamStatsDict['OTpts'] = self.homeScoreOT
        homeTeamStatsDict['1stDowns'] = self.home1stDownsTotal
        homeTeamStatsDict['totalPlays'] = self.homePlaysTotal
        homeTeamStatsDict['turnovers'] = self.homeTurnoversTotal
        homeTeamStatsDict['sacks'] = self.homeTeam.gameDefenseStats['sacks']
        homeTeamStatsDict['safeties'] = self.homeTeam.gameDefenseStats['safeties']

        awayTeamOffenseStatsDict['passYards'] = awayTeamPassYards
        awayTeamOffenseStatsDict['rushYards'] = awayTeamRushYards
        awayTeamOffenseStatsDict['totalYards'] = awayTeamTotalYards
        awayTeamOffenseStatsDict['passTds'] = awayTeamPassTds
        awayTeamOffenseStatsDict['runTds'] = awayTeamRushTds
        awayTeamOffenseStatsDict['tds'] = awayTeamPassTds + awayTeamRushTds
        awayTeamOffenseStatsDict['fgs'] = awayTeamFgs
        awayTeamOffenseStatsDict['score'] = self.awayScore
        awayTeamStatsDict['offense'] = awayTeamOffenseStatsDict
        awayTeamStatsDict['defense'] = self.awayTeam.gameDefenseStats
        awayTeamStatsDict['passYards'] = awayTeamPassYards
        awayTeamStatsDict['rushYards'] = awayTeamRushYards
        awayTeamStatsDict['totalYards'] = awayTeamTotalYards
        awayTeamStatsDict['defenseRating'] = self.awayTeam.defenseTier
        awayTeamStatsDict['teamName'] = self.awayTeam.name
        awayTeamStatsDict['teamCity'] = self.awayTeam.city
        awayTeamStatsDict['teamcolor'] = self.awayTeam.color
        awayTeamStatsDict['teamAbbr'] = self.awayTeam.abbr
        awayTeamStatsDict['id'] = self.awayTeam.id
        awayTeamStatsDict['record'] = '{}-{}'.format(self.awayTeam.seasonTeamStats['wins'], self.awayTeam.seasonTeamStats['losses'])
        awayTeamStatsDict['score'] = self.awayScore
        awayTeamStatsDict['qtr1pts'] = self.awayScoreQ1
        awayTeamStatsDict['qtr2pts'] = self.awayScoreQ2
        awayTeamStatsDict['qtr3pts'] = self.awayScoreQ3
        awayTeamStatsDict['qtr4pts'] = self.awayScoreQ4
        awayTeamStatsDict['OTpts'] = self.awayScoreOT
        awayTeamStatsDict['1stDowns'] = self.away1stDownsTotal
        awayTeamStatsDict['totalPlays'] = self.awayPlaysTotal
        awayTeamStatsDict['turnovers'] = self.awayTurnoversTotal
        awayTeamStatsDict['sacks'] = self.awayTeam.gameDefenseStats['sacks']
        awayTeamStatsDict['safeties'] = self.awayTeam.gameDefenseStats['safeties']

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
        else:
            down = '1st'
        gameStatsDict['downText'] = '{0} & {1}'.format(down, self.yardsToFirstDown)
        if self.yardsToEndzone < 10:
            gameStatsDict['yardsTo1stDwn'] = self.yardsToEndzone
        else:
            gameStatsDict['yardsTo1stDwn'] = self.yardsToFirstDown
        gameStatsDict['yardsToEZ'] = self.yardsToEndzone
        gameStatsDict['yardLine'] = self.yardLine
        gameStatsDict['playsLeft'] = 132 - self.totalPlays
        gameStatsDict['status'] = self.status.name


        self.gameDict['gameStats'] = gameStatsDict


    def playCaller(self):
        if self.currentQuarter == 5:
            if self.yardsToEndzone <= 20:
                x = randint(1,10)
                if x > 1:
                    self.play.playType = PlayType.FieldGoal
            elif self.yardsToEndzone <= 30:
                x = randint(1,10)
                if x > 4:
                    self.play.playType = PlayType.FieldGoal
            elif self.yardsToEndzone <= 40:
                x = randint(1,10)
                if x > 6:
                    self.play.playType = PlayType.FieldGoal

        if self.totalPlays == 65:
            if self.yardsToEndzone <= 10:
                x = randint(1,10)
                if x > 4:
                    self.play.playType = PlayType.FieldGoal
                else:
                    if self.yardsToEndzone <= 3:
                        x = randint(1,10)
                        if x > 3:
                            self.play.runPlay()
                        else:
                            self.play.passPlay(PassType.short)
                    else:
                        self.play.passPlay(PassType.medium)
            elif self.yardsToEndzone > 10 and self.yardsToEndzone <= 45:
                x = randint(1,10)
                if x > 1:
                    self.play.playType = PlayType.FieldGoal
                else:
                    self.play.passPlay(PassType.long)
            else:
                self.play.passPlay(PassType.long)
        if self.totalPlays == 131:
            if self.homeTeam == self.play.offense and self.homeScore <= self.awayScore:
                scoreDiff = self.awayScore - self.homeScore
                if scoreDiff <= 3 and self.yardsToEndzone < 50:
                    self.play.playType = PlayType.FieldGoal
                else:
                    self.homeTeam.inGamePush()
                    self.play.passPlay(PassType.long)
            elif self.awayTeam == self.play.offense and self.awayScore <= self.homeScore:
                scoreDiff = self.homeScore - self.awayScore
                if scoreDiff <= 3 and self.yardsToEndzone < 50:
                    self.play.playType = PlayType.FieldGoal
                else:
                    self.awayTeam.inGamePush()
                    self.play.passPlay(PassType.long)
            else:
                self.play.passPlay(PassType.long)
        elif self.down <= 2:
            if self.currentQuarter == 4:
                if self.homeTeam == self.play.offense and self.homeScore < self.awayScore:
                    scoreDiff = self.awayScore - self.homeScore
                    x = randint(1,10)
                    if x < 4:
                        self.play.runPlay()
                    elif x >= 4 and x < 9:
                        self.play.passPlay(PassType.medium)
                    else:
                        self.play.passPlay(PassType.long)
                elif self.awayTeam == self.play.offense and self.awayScore < self.homeScore:
                    scoreDiff = self.homeScore - self.awayScore
                    x = randint(1,10)
                    if x < 4:
                        self.play.runPlay()
                    elif x >= 4 and x < 9:
                        self.play.passPlay(PassType.medium)
                    else:
                        self.play.passPlay(PassType.long)
            elif self.yardsToEndzone <= 20:
                x = randint(1,10)
                if x <= 3:
                    self.play.runPlay()
                else:
                    y = randint(1,10)
                    if y <= 4:
                        self.play.passPlay(PassType.short)
                    elif y > 4 and y <= 8:
                        self.play.passPlay(PassType.medium)
                    else:
                        self.play.passPlay(PassType.long)
            if self.yardsToSafety <= 5:
                x = randint(1,10)
                if x <= 4:
                    y = randint(0,1)
                    if y == 0:
                        self.play.passPlay(PassType.medium)
                    else:
                        self.play.passPlay(PassType.long)
                else:
                    self.play.runPlay()
            else:
                x = randint(0,1)
                if x == 1:
                    self.play.runPlay()
                else:
                    y = randint(1,10)
                    if y <= 4:
                        self.play.passPlay(PassType.short)
                    elif y > 4 and y <= 8:
                        self.play.passPlay(PassType.medium)
                    else:
                        self.play.passPlay(PassType.long)
    
        elif self.down == 3:
            if self.currentQuarter == 4:
                if self.homeTeam == self.play.offense and self.homeScore < self.awayScore:
                    scoreDiff = self.awayScore - self.homeScore
                    x = randint(1,10)
                    if x < 3:
                        self.play.runPlay()
                    elif x >= 3 and x < 7:
                        self.play.passPlay(PassType.medium)
                    else:
                        self.play.passPlay(PassType.long)
                elif self.awayTeam == self.play.offense and self.awayScore < self.homeScore:
                    scoreDiff = self.homeScore - self.awayScore
                    x = randint(1,10)
                    if x < 3:
                        self.play.runPlay()
                    elif x >= 3 and x < 7:
                        self.play.passPlay(PassType.medium)
                    else:
                        self.play.passPlay(PassType.long)
            if self.yardsToFirstDown <= 4:
                x = randint(1,10)
                if x < 7:
                    self.play.runPlay()
                elif x >= 7 and x < 9:
                    self.play.passPlay(PassType.short)
                else:
                    self.play.passPlay(PassType.medium)
            else:
                x = randint(1,10)
                if x < 6:
                    self.play.passPlay(PassType.medium)
                elif x >= 6 and x < 9:
                    self.play.passPlay(PassType.short)
                else:
                    self.play.passPlay(PassType.long)
        elif self.down == 4:
            if self.currentQuarter == 4 and self.awayTeam == self.play.offense and self.awayScore < self.homeScore:
                scoreDiff = self.homeScore - self.awayScore
                if self.totalPlays > 120 and self.yardsToEndzone < 20:
                    if scoreDiff <= 3:
                        self.play.playType = PlayType.FieldGoal
                    else:
                        self.play.passPlay(PassType.medium)
                elif self.totalPlays > 120 and self.yardsToEndzone > 20:
                    if self.yardsToEndzone < 45 and scoreDiff <= 3:
                        x = randint(1,10)
                        if x > 5:
                            self.play.playType = PlayType.FieldGoal
                        else:
                            self.play.passPlay(PassType.long)
                    else:
                        self.play.passPlay(PassType.long)
                elif self.yardsToFirstDown <= 2:
                    if self.yardsToSafety > 20:
                        if self.yardsToEndzone <= 30:
                            self.play.playType = PlayType.FieldGoal
                        else:
                            x = randint(1,3)
                            if x <= 2:
                                self.play.passPlay(PassType.short)
                            else:
                                self.play.passPlay(PassType.medium)
                    else:
                        x = randint(1,10)
                        if x > 8:
                            self.play.playType = PlayType.Punt
                        else:
                            x = randint(1,3)
                            if x == 1:
                                self.play.runPlay()
                            elif x == 2:
                                self.play.passPlay(PassType.short)
                            else:
                                self.play.passPlay(PassType.medium)         
                else:
                    if self.yardsToEndzone > 30 and self.yardsToEndzone < 45 and self.yardsToFirstDown > 6:
                        x = randint(1,10)
                        if x > 3:
                            self.play.playType = PlayType.FieldGoal
                        else:
                            self.play.passPlay(PassType.medium)
                    else:
                        self.play.passPlay(PassType.medium)
            elif self.currentQuarter == 4 and self.homeTeam == self.play.offense and self.homeScore < self.awayScore:
                scoreDiff = self.awayScore - self.homeScore
                if self.totalPlays > 120 and self.yardsToEndzone < 20:
                    if scoreDiff <= 3:
                        self.play.playType = PlayType.FieldGoal
                    else:
                        self.play.passPlay(PassType.medium)
                elif self.totalPlays > 120 and self.yardsToEndzone > 20:
                    if self.yardsToEndzone < 45 and scoreDiff <= 3:
                        x = randint(1,10)
                        if x > 5:
                            self.play.playType = PlayType.FieldGoal
                        else:
                            self.play.passPlay(PassType.long)
                    else:
                        self.play.passPlay(PassType.long)
                elif self.yardsToFirstDown <= 2:
                    if self.yardsToSafety > 20:
                        if self.yardsToEndzone <= 30:
                            self.play.playType = PlayType.FieldGoal
                        else:
                            x = randint(1,3)
                            if x <= 2:
                                self.play.passPlay(PassType.short)
                            else:
                                self.play.passPlay(PassType.medium)
                    else:
                        x = randint(1,10)
                        if x > 8:
                            self.play.playType = PlayType.Punt
                        else:
                            x = randint(1,3)
                            if x == 1:
                                self.play.runPlay()
                            elif x == 2:
                                self.play.passPlay(PassType.short)
                            else:
                                self.play.passPlay(PassType.medium)         
                else:
                    if self.yardsToEndzone > 30 and self.yardsToEndzone < 55 and self.yardsToFirstDown > 6:
                        x = randint(1,10)
                        if x > 3:
                            self.play.playType = PlayType.FieldGoal
                        else:
                            self.play.passPlay(PassType.medium)
                    else:
                        self.play.passPlay(PassType.medium)
            elif self.currentQuarter == 4 and self.homeTeam == self.play.offense and self.homeScore > self.awayScore:
                if self.yardsToEndzone < 40:
                    self.play.playType = PlayType.FieldGoal
                else:
                    self.play.playType = PlayType.Punt
            elif self.currentQuarter == 4 and self.awayTeam == self.play.offense and self.awayScore > self.homeScore:
                if self.yardsToEndzone < 40:
                    self.play.playType = PlayType.FieldGoal
                else:
                    self.play.playType = PlayType.Punt
            elif self.yardsToEndzone <= 5:
                    x = randint(1,10)
                    if x < 6:
                        self.play.playType = PlayType.FieldGoal
                    else:
                        y = randint(1,10)
                        if y < 5:
                            self.play.runPlay()
                        elif y >= 5 and y < 8:
                            self.play.passPlay(PassType.short)
                        else:
                            self.play.passPlay(PassType.medium)

            elif self.yardsToEndzone <= 20:
                if self.yardsToFirstDown <= 2:
                    x = randint(1,10)
                    if x >= 4:
                        self.play.playType = PlayType.FieldGoal
                    else:
                        y = randint(1,3)
                        if y == 1:
                            self.play.runPlay()
                        elif y == 2:
                            self.play.passPlay(PassType.short)
                        else:
                            self.play.passPlay(PassType.medium)
                else:
                    x = randint(1,10)
                    if x < 8:
                        self.play.playType = PlayType.FieldGoal
                    else:
                        self.play.passPlay(PassType.medium)
            elif self.yardsToEndzone <= 35:
                if self.yardsToFirstDown <= 2:
                    x = randint(1,10)
                    if x >= 2:
                        self.play.playType = PlayType.FieldGoal
                    else:
                        y = randint(1,3)
                        if y == 1:
                            self.play.runPlay()
                        elif y == 2:
                            self.play.passPlay(PassType.short)
                        else:
                            self.play.passPlay(PassType.medium)
                else:
                    x = randint(1,10)
                    if x < 9:
                        self.play.playType = PlayType.FieldGoal
                    else:
                        self.play.passPlay(PassType.medium)
            elif self.yardsToEndzone <= 45:
                    x = randint(1,10)
                    if x < 4:
                        self.play.playType = PlayType.FieldGoal
                    else:
                        self.play.playType = PlayType.Punt
            elif self.yardsToSafety <= 20:
                self.play.playType = PlayType.Punt
            else:
                if self.yardsToFirstDown <= 2:
                    x = randint(1,10)
                    if x < 8:
                        self.play.playType = PlayType.Punt
                    elif x >= 7 and x < 9:
                        self.play.passPlay(PassType.short)
                    else:
                        self.play.passPlay(PassType.medium)
                else:
                    x = randint(1,10)
                    if x < 10:
                        self.play.playType = PlayType.Punt
                    else:
                        y = randint(0,1)
                        if y == 0:
                            self.play.passPlay(PassType.medium)
                        else:
                            self.play.passPlay(PassType.long)

    def turnover(self, offense: FloosTeam.Team, defense: FloosTeam.Team, yards):
        self.offensiveTeam = defense
        self.defensiveTeam = offense
        self.yardsToEndzone = yards
        self.yardsToSafety = 100 - self.yardsToEndzone
        self.yardsToFirstDown = 10
        self.defensiveTeam.updateGameEnergy(self.driveLength/5)

    # def scoreChange(self):
    #     pass

    def formatPlayText(self):
        text = None
        if self.play.playType is PlayType.Run:
            if self.play.isFumble:
                if self.play.playResult is PlayResult.Fumble:
                    text = '{} Fumbles, {} recovers'.format(self.play.runner.name, self.play.defense.name)
                else:
                    text = '{} Fumbles, {} recovers'.format(self.play.runner.name, self.play.offense.name)
            else:
                text = '{} runs for {} yards'.format(self.play.runner.name, self.play.yardage)
        elif self.play.playType is PlayType.Pass:
            if self.play.isSack:
                if self.play.isFumble:
                    if self.play.isFumbleLost:
                        text = '{} sacked and Fumbles, {} recovers'.format(self.play.passer.name, self.play.defense.name)
                    else:
                        text = '{} sacked and Fumbles, {} recovers'.format(self.play.passer.name, self.play.offense.name)
                else:
                    text = '{} sacked for {} yards'.format(self.play.passer.name, self.play.defense.name)
            elif self.play.isPassCompletion:
                text = '{} pass to {} complete for {} yards'.format(self.play.passer.name, self.play.receiver.name, self.play.yardage)
            elif self.play.playResult is PlayResult.Interception:
                text = '{} pass intercepted'.format(self.play.passer.name)
            else:
                text = '{} pass to {} incomplete'.format(self.play.passer.name, self.play.receiver.name)
        elif self.play.playType == PlayType.FieldGoal:
            text = '{}yd Field Goal attempt by {}'.format(self.play.fgDistance, self.play.kicker.name)
        elif self.play.playType is PlayType.Punt:
            text = '{} {}'.format(self.play.offense.name, self.play.playResult)
        
        self.play.playText = text

    def postgame(self): 
        if self.isRegularSeasonGame:   
            self.homeTeam.seasonTeamStats['Offense']['pts'] += self.homeScore
            homeScoreDiff = self.homeScore - self.homeTeam.gameDefenseStats['ptsAlwd']
            self.homeTeam.seasonTeamStats['scoreDiff'] += homeScoreDiff
            self.awayTeam.seasonTeamStats['Offense']['pts'] += self.awayScore
            awayScoreDiff = self.awayScore - self.awayTeam.gameDefenseStats['ptsAlwd']
            self.awayTeam.seasonTeamStats['scoreDiff'] += awayScoreDiff

            if self.winningTeam.seasonTeamStats['streak'] >= 0:
                self.winningTeam.seasonTeamStats['streak'] += 1
            else:
                self.winningTeam.seasonTeamStats['streak'] = 1

            self.winningTeam.seasonTeamStats['Defense']['ints'] += self.winningTeam.gameDefenseStats['ints']
            self.winningTeam.seasonTeamStats['Defense']['fumRec'] += self.winningTeam.gameDefenseStats['fumRec']
            self.winningTeam.seasonTeamStats['Defense']['sacks'] += self.winningTeam.gameDefenseStats['sacks']
            self.winningTeam.seasonTeamStats['Defense']['safeties'] += self.winningTeam.gameDefenseStats['safeties']
            self.winningTeam.seasonTeamStats['Defense']['runYardsAlwd'] += self.winningTeam.gameDefenseStats['runYardsAlwd']
            self.winningTeam.seasonTeamStats['Defense']['passYardsAlwd'] += self.winningTeam.gameDefenseStats['passYardsAlwd']
            self.winningTeam.seasonTeamStats['Defense']['totalYardsAlwd'] += self.winningTeam.gameDefenseStats['totalYardsAlwd']
            self.winningTeam.seasonTeamStats['Defense']['runTdsAlwd'] += self.winningTeam.gameDefenseStats['runTdsAlwd']
            self.winningTeam.seasonTeamStats['Defense']['passTdsAlwd'] += self.winningTeam.gameDefenseStats['passTdsAlwd']
            self.winningTeam.seasonTeamStats['Defense']['tdsAlwd'] += self.winningTeam.gameDefenseStats['tdsAlwd']
            self.winningTeam.seasonTeamStats['Defense']['ptsAlwd'] += self.winningTeam.gameDefenseStats['ptsAlwd']
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
            self.losingTeam.seasonTeamStats['Defense']['safeties'] += self.losingTeam.gameDefenseStats['safeties']
            self.losingTeam.seasonTeamStats['Defense']['runYardsAlwd'] += self.losingTeam.gameDefenseStats['runYardsAlwd']
            self.losingTeam.seasonTeamStats['Defense']['passYardsAlwd'] += self.losingTeam.gameDefenseStats['passYardsAlwd']
            self.losingTeam.seasonTeamStats['Defense']['totalYardsAlwd'] += self.losingTeam.gameDefenseStats['totalYardsAlwd']
            self.losingTeam.seasonTeamStats['Defense']['runTdsAlwd'] += self.losingTeam.gameDefenseStats['runTdsAlwd']
            self.losingTeam.seasonTeamStats['Defense']['passTdsAlwd'] += self.losingTeam.gameDefenseStats['passTdsAlwd']
            self.losingTeam.seasonTeamStats['Defense']['tdsAlwd'] += self.losingTeam.gameDefenseStats['tdsAlwd']
            self.losingTeam.seasonTeamStats['Defense']['ptsAlwd'] += self.losingTeam.gameDefenseStats['ptsAlwd']
            self.losingTeam.seasonTeamStats['winPerc'] = round(self.losingTeam.seasonTeamStats['wins']/(self.losingTeam.seasonTeamStats['wins']+self.losingTeam.seasonTeamStats['losses']),3)
            self.losingTeam.seasonTeamStats['divWinPerc'] = round(self.losingTeam.seasonTeamStats['divWins']/(self.losingTeam.seasonTeamStats['divWins']+self.losingTeam.seasonTeamStats['divLosses']),3)
            self.losingTeam.gameDefenseStats = copy.deepcopy(FloosTeam.teamStatsDict['Defense'])

        for player in self.homeTeam.rosterDict.values():
            player.postgameChanges()

            if 'passComp' in player.gameStatsDict:
                player.gameStatsDict['totalYards'] = player.gameStatsDict['passYards']

                if player.gameStatsDict['passComp'] > 0:
                    player.gameStatsDict['ypc'] = round(player.gameStatsDict['passYards']/player.gameStatsDict['passComp'], 2)
                    player.gameStatsDict['passCompPerc'] = round((player.gameStatsDict['passComp']/player.gameStatsDict['passAtt'])*100)

                if self.isRegularSeasonGame: 
                    player.seasonStatsDict['passAtt'] += player.gameStatsDict['passAtt']
                    player.seasonStatsDict['passComp'] += player.gameStatsDict['passComp']
                    player.seasonStatsDict['tds'] += player.gameStatsDict['tds']
                    player.seasonStatsDict['ints'] += player.gameStatsDict['ints']
                    player.seasonStatsDict['passYards'] += player.gameStatsDict['passYards']
                    player.seasonStatsDict['totalYards'] += player.gameStatsDict['passYards']
                    player.seasonStatsDict['pass20+'] += player.gameStatsDict['pass20+']

                    if player.gameStatsDict['longest'] > player.seasonStatsDict['longest']:
                        player.seasonStatsDict['longest'] = player.gameStatsDict['longest']

                    if player.seasonStatsDict['passComp'] > 0:
                        player.seasonStatsDict['ypc'] = round(player.seasonStatsDict['passYards']/player.seasonStatsDict['passComp'], 2)
                        player.seasonStatsDict['passCompPerc'] = round((player.seasonStatsDict['passComp']/player.seasonStatsDict['passAtt'])*100)

            if 'receptions' in player.gameStatsDict:
                player.gameStatsDict['totalYards'] = player.gameStatsDict['rcvYards']

                if player.gameStatsDict['receptions'] > 0:
                    player.gameStatsDict['ypr'] = round(player.gameStatsDict['rcvYards']/player.gameStatsDict['receptions'],2)
                    player.gameStatsDict['rcvPerc'] = round((player.gameStatsDict['receptions']/player.gameStatsDict['passTargets'])*100)

                if self.isRegularSeasonGame:
                    player.seasonStatsDict['receptions'] += player.gameStatsDict['receptions']
                    player.seasonStatsDict['passTargets'] += player.gameStatsDict['passTargets']
                    player.seasonStatsDict['rcvYards'] += player.gameStatsDict['rcvYards']
                    player.seasonStatsDict['rcvTds'] += player.gameStatsDict['rcvTds']
                    player.seasonStatsDict['totalYards'] += player.gameStatsDict['rcvYards']
                    player.seasonStatsDict['pass20+'] += player.gameStatsDict['pass20+']

                    if player.gameStatsDict['longest'] > player.seasonStatsDict['longest']:
                        player.seasonStatsDict['longest'] = player.gameStatsDict['longest']

                    if player.seasonStatsDict['receptions'] > 0:
                        player.seasonStatsDict['ypr'] = round(player.seasonStatsDict['rcvYards']/player.seasonStatsDict['receptions'],2)
                        player.seasonStatsDict['rcvPerc'] = round((player.seasonStatsDict['receptions']/player.seasonStatsDict['passTargets'])*100)

            if 'carries' in player.gameStatsDict:
                player.gameStatsDict['totalYards'] = player.gameStatsDict['rcvYards'] + player.gameStatsDict['runYards']

                if player.gameStatsDict['carries'] > 0:
                    player.gameStatsDict['ypc'] = round(player.gameStatsDict['runYards']/player.gameStatsDict['carries'],2)

                if self.isRegularSeasonGame:
                    player.seasonStatsDict['carries'] += player.gameStatsDict['carries']
                    player.seasonStatsDict['runYards'] += player.gameStatsDict['runYards']
                    player.seasonStatsDict['runTds'] += player.gameStatsDict['runTds']
                    player.seasonStatsDict['fumblesLost'] += player.gameStatsDict['fumblesLost']
                    player.seasonStatsDict['totalYards'] += player.gameStatsDict['runYards']
                    player.seasonStatsDict['run20+'] += player.gameStatsDict['run20+']

                    if player.gameStatsDict['longest'] > player.seasonStatsDict['longest']:
                        player.seasonStatsDict['longest'] = player.gameStatsDict['longest']

                    if player.seasonStatsDict['carries'] > 0:
                        player.seasonStatsDict['ypc'] = round(player.seasonStatsDict['runYards']/player.seasonStatsDict['carries'],2)
            if 'fgs' in player.gameStatsDict:
                if player.gameStatsDict['fgs'] > 0:
                    player.gameStatsDict['fgPerc'] = round((player.gameStatsDict['fgs']/player.gameStatsDict['fgAtt'])*100)
                else:
                    player.gameStatsDict['fgPerc'] = 0

                if self.isRegularSeasonGame:
                    player.seasonStatsDict['fgAtt'] += player.gameStatsDict['fgAtt']
                    player.seasonStatsDict['fg45+'] += player.gameStatsDict['fg45+']
                    player.seasonStatsDict['fgs'] += player.gameStatsDict['fgs']

                    if player.gameStatsDict['longest'] > player.seasonStatsDict['longest']:
                        player.seasonStatsDict['longest'] = player.gameStatsDict['longest']

                    if player.seasonStatsDict['fgs'] > 0:
                        player.seasonStatsDict['fgPerc'] = round((player.seasonStatsDict['fgs']/player.seasonStatsDict['fgAtt'])*100)
                    else:
                        player.seasonStatsDict['fgPerc'] = 0

        for player in self.awayTeam.rosterDict.values():
            player.postgameChanges()

            if 'passComp' in player.gameStatsDict:
                player.gameStatsDict['totalYards'] = player.gameStatsDict['passYards']

                if player.gameStatsDict['passComp'] > 0:
                    player.gameStatsDict['ypc'] = round(player.gameStatsDict['passYards']/player.gameStatsDict['passComp'],2)
                    player.gameStatsDict['passCompPerc'] = round((player.gameStatsDict['passComp']/player.gameStatsDict['passAtt'])*100)

                if self.isRegularSeasonGame:
                    player.seasonStatsDict['passAtt'] += player.gameStatsDict['passAtt']
                    player.seasonStatsDict['passComp'] += player.gameStatsDict['passComp']
                    player.seasonStatsDict['tds'] += player.gameStatsDict['tds']
                    player.seasonStatsDict['ints'] += player.gameStatsDict['ints']
                    player.seasonStatsDict['passYards'] += player.gameStatsDict['passYards']
                    player.seasonStatsDict['totalYards'] += player.gameStatsDict['passYards']
                    player.seasonStatsDict['pass20+'] += player.gameStatsDict['pass20+']

                    if player.gameStatsDict['longest'] > player.seasonStatsDict['longest']:
                        player.seasonStatsDict['longest'] = player.gameStatsDict['longest']

                    if player.seasonStatsDict['passComp'] > 0:
                        player.seasonStatsDict['ypc'] = round(player.seasonStatsDict['passYards']/player.seasonStatsDict['passComp'],2)
                        player.seasonStatsDict['passCompPerc'] = round((player.seasonStatsDict['passComp']/player.seasonStatsDict['passAtt'])*100)

            if 'receptions' in player.gameStatsDict:
                player.gameStatsDict['totalYards'] = player.gameStatsDict['rcvYards']

                if player.gameStatsDict['receptions'] > 0:
                    player.gameStatsDict['ypr'] = round(player.gameStatsDict['rcvYards']/player.gameStatsDict['receptions'],2)
                    player.gameStatsDict['rcvPerc'] = round((player.gameStatsDict['receptions']/player.gameStatsDict['passTargets'])*100)

                if self.isRegularSeasonGame:
                    player.seasonStatsDict['receptions'] += player.gameStatsDict['receptions']
                    player.seasonStatsDict['passTargets'] += player.gameStatsDict['passTargets']
                    player.seasonStatsDict['rcvYards'] += player.gameStatsDict['rcvYards']
                    player.seasonStatsDict['rcvTds'] += player.gameStatsDict['rcvTds']
                    player.seasonStatsDict['totalYards'] += player.gameStatsDict['rcvYards']
                    player.seasonStatsDict['pass20+'] += player.gameStatsDict['pass20+']

                    if player.gameStatsDict['longest'] > player.seasonStatsDict['longest']:
                        player.seasonStatsDict['longest'] = player.gameStatsDict['longest']

                    if player.seasonStatsDict['receptions'] > 0:
                        player.seasonStatsDict['ypr'] = round(player.seasonStatsDict['rcvYards']/player.seasonStatsDict['receptions'],2)
                        player.seasonStatsDict['rcvPerc'] = round((player.seasonStatsDict['receptions']/player.seasonStatsDict['passTargets'])*100)

            if 'carries' in player.gameStatsDict:
                player.gameStatsDict['totalYards'] = player.gameStatsDict['rcvYards'] + player.gameStatsDict['runYards']

                if player.gameStatsDict['carries'] > 0:
                    player.gameStatsDict['ypc'] = round(player.gameStatsDict['runYards']/player.gameStatsDict['carries'],2)

                if self.isRegularSeasonGame:
                    player.seasonStatsDict['carries'] += player.gameStatsDict['carries']
                    player.seasonStatsDict['runYards'] += player.gameStatsDict['runYards']
                    player.seasonStatsDict['runTds'] += player.gameStatsDict['runTds']
                    player.seasonStatsDict['fumblesLost'] += player.gameStatsDict['fumblesLost']
                    player.seasonStatsDict['totalYards'] += player.gameStatsDict['runYards']
                    player.seasonStatsDict['run20+'] += player.gameStatsDict['run20+']

                    if player.gameStatsDict['longest'] > player.seasonStatsDict['longest']:
                        player.seasonStatsDict['longest'] = player.gameStatsDict['longest']

                    if player.seasonStatsDict['carries'] > 0:
                        player.seasonStatsDict['ypc'] = round(player.seasonStatsDict['runYards']/player.seasonStatsDict['carries'],2)

            if 'fgs' in player.gameStatsDict:
                if player.gameStatsDict['fgs'] > 0:
                    player.gameStatsDict['fgPerc'] = round((player.gameStatsDict['fgs']/player.gameStatsDict['fgAtt'])*100)
                else:
                    player.gameStatsDict['fgPerc'] = 0

                if self.isRegularSeasonGame:
                    player.seasonStatsDict['fg45+'] += player.gameStatsDict['fg45+']
                    player.seasonStatsDict['fgAtt'] += player.gameStatsDict['fgAtt']
                    player.seasonStatsDict['fgs'] += player.gameStatsDict['fgs']
                    if player.seasonStatsDict['fgs'] > 0:
                        player.seasonStatsDict['fgPerc'] = round((player.seasonStatsDict['fgs']/player.seasonStatsDict['fgAtt'])*100)
                    else:
                        player.seasonStatsDict['fgPerc'] = 0
            
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
            for k in player.gameStatsDict.keys():
                player.gameStatsDict[k] = 0
        for player in self.awayTeam.rosterDict.values():
            player: FloosPlayer.Player
            player.gameAttributes = copy.deepcopy(player.attributes)
            for k in player.gameStatsDict.keys():
                player.gameStatsDict[k] = 0

        #await asyncio.sleep(15)
        x = randint(0,1)
        if x == 0:
            self.offensiveTeam = self.homeTeam
            self.defensiveTeam = self.awayTeam
            coinFlipWinner = self.homeTeam
            coinFlipLoser = self.awayTeam
        else:
            self.offensiveTeam = self.awayTeam
            self.defensiveTeam = self.homeTeam
            coinFlipWinner = self.awayTeam
            coinFlipLoser = self.homeTeam

        self.status = GameStatus.Active

        while self.totalPlays < 132 or self.homeScore == self.awayScore:

            if self.totalPlays < 1:
                self.yardsToFirstDown = 10
                self.yardsToEndzone = 80
                self.yardsToSafety = 20

            self.down = 1
            self.driveLength = 0

            while self.down <= 4:

                if self.totalPlays > 0:
                    self.formatPlayText()
                    if self.play.playResult is PlayResult.FieldGoalGood or self.play.playResult is PlayResult.Safety or self.play.playResult is PlayResult.TouchdownXP or self.play.playResult is PlayResult.TouchdownNoXP:
                        self.scoringPlaysList.insert(0, self.play)
                        self.play.scoreChange = True
                    self.playsList.insert(0,self.play)

                if self.totalPlays == 132 and self.homeScore != self.awayScore:
                    break

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
                        #await asyncio.sleep(60)
                        self.isHalftime = False
                    if self.currentQuarter != 3:
                        self.currentQuarter = 3
                        self.turnover(coinFlipLoser, coinFlipWinner, possReset)
                        self.down = 1
                        self.driveLength = 0
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
                elif self.totalPlays >= 132 and self.homeScore == self.awayScore:
                    if self.currentQuarter != 5:
                        self.currentQuarter = 5
                        self.isOvertime = True
                        x = randint(0,1)
                        if x == 0:
                            self.turnover(self.homeTeam, self.awayTeam, possReset)
                        else:
                            self.turnover(self.awayTeam, self.homeTeam, possReset)
                        self.down = 1
                        self.driveLength = 0
                        self.homeTeam.resetDetermination()
                        self.homeTeam.resetConfidence()
                        self.awayTeam.resetDetermination()
                        self.awayTeam.resetConfidence()
                

                if self.yardsToEndzone > 50:
                    self.yardLine = '{0} {1}'.format(self.offensiveTeam.abbr, (100-self.yardsToEndzone))
                else:
                    self.yardLine = '{0} {1}'.format(self.defensiveTeam.abbr, self.yardsToEndzone)

                self.play = Play(self)
                
                #await asyncio.sleep(randint(15, 30))

                self.playCaller()
                self.totalPlays += 1
                self.driveLength += 1
                if self.offensiveTeam is self.homeTeam:
                    self.homePlaysTotal += 1
                if self.offensiveTeam is self.awayTeam:
                    self.awayPlaysTotal += 1
                self.defensiveTeam.updateGameEnergy(-.75)


                if self.play.playType is PlayType.FieldGoal:
                    self.play.fieldGoalTry()
                    if self.play.isFgGood:
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
                            elif self.currentQuarter == 5:
                                self.homeScoreOT += 3
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
                            elif self.currentQuarter == 5:
                                self.awayScoreOT += 3
                        self.defensiveTeam.gameDefenseStats['ptsAlwd'] += 3
                        self.play.playResult = PlayResult.FieldGoalGood
                        if self.currentQuarter == 5 and self.homeScore != self.awayScore:
                            break
                        else:
                            self.turnover(self.offensiveTeam, self.defensiveTeam, possReset)
                            break
                    else:
                        self.play.playResult = PlayResult.FieldGoalNoGood
                        self.turnover(self.offensiveTeam, self.defensiveTeam, self.yardsToSafety)
                        break
                if self.play.playType is PlayType.Punt:
                    self.play.playResult = PlayResult.Punt
                    puntDistance = randint(30, 60)
                    if puntDistance >= self.yardsToEndzone:
                        puntDistance = self.yardsToEndzone - 20
                    newYards = 100 - (self.yardsToEndzone - puntDistance)
                    self.turnover(self.offensiveTeam, self.defensiveTeam, newYards)
                    break
                elif self.play.isFumbleLost or self.play.isInterception:
                    if self.offensiveTeam is self.homeTeam:
                        self.homeTurnoversTotal += 1
                    elif self.offensiveTeam is self.awayTeam:
                        self.awayTurnoversTotal += 1
                    if self.play.yardage > self.yardsToEndzone:
                        self.turnover(self.offensiveTeam, self.defensiveTeam, possReset)
                    else:
                        self.turnover(self.offensiveTeam, self.defensiveTeam, (self.yardsToSafety + self.play.yardage))
                    break
                else:
                    if self.play.yardage >= self.yardsToEndzone:
                        self.play.isTd = True
                        if self.play.playType is PlayType.Run:
                            self.play.runner.gameStatsDict['runTds'] += 1
                            self.play.runner.updateInGameConfidence(.01)
                            self.play.defense.gameDefenseStats['runTdsAlwd'] += 1
                            self.play.defense.gameDefenseStats['tdsAlwd'] += 1
                        elif self.play.playType is PlayType.Pass:
                            self.play.passer.gameStatsDict['tds'] += 1
                            self.play.receiver.gameStatsDict['rcvTds'] += 1
                            self.play.defense.gameDefenseStats['passTdsAlwd'] += 1
                            self.play.defense.gameDefenseStats['tdsAlwd'] += 1
                            self.play.passer.updateInGameConfidence(.01)
                            self.play.receiver.updateInGameConfidence(.01)

                        self.play.defense.gameDefenseStats['ptsAlwd'] += 6

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
                            elif self.currentQuarter == 5:
                                self.homeScoreOT += 6

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
                            elif self.currentQuarter == 5:
                                self.awayScoreOT += 6

                        #self.scoreChange()
                        self.play.extraPointTry()
                        if self.play.isXpGood:
                            self.play.playResult = PlayResult.TouchdownXP
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
                                elif self.currentQuarter == 5:
                                    self.homeScoreOT += 1
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
                                elif self.currentQuarter == 5:
                                    self.awayScoreOT += 1 

                            self.play.defense.gameDefenseStats['ptsAlwd'] += 1

                        else:
                            self.play.playResult = PlayResult.TouchdownNoXP
                        self.turnover(self.offensiveTeam, self.defensiveTeam, possReset)
                        break

                    elif self.play.yardage >= self.yardsToFirstDown:
                        self.down = 1
                        if self.offensiveTeam is self.homeTeam:
                            self.home1stDownsTotal += 1
                        elif self.offensiveTeam is self.awayTeam:
                            self.away1stDownsTotal += 1
                        if self.yardsToEndzone < 10:
                            self.yardsToFirstDown = self.yardsToEndzone
                        else:
                            self.yardsToFirstDown = 10
                        self.yardsToSafety += self.play.yardage
                        self.yardsToEndzone -= self.play.yardage
                        self.play.playResult = PlayResult.FirstDown
                        continue

                    elif (self.yardsToSafety + self.play.yardage) <= 0:
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
                            elif self.currentQuarter == 5:
                                self.homeScoreOT += 2

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
                            elif self.currentQuarter == 5:
                                self.awayScoreOT += 2

                        self.play.defense.gameDefenseStats['safeties'] += 1

                        self.play.playResult = PlayResult.Safety
                        self.play.isSafety = True
                        #self.scoreChange()
                        self.turnover(self.offensiveTeam, self.defensiveTeam, possReset)
                        break

                    elif self.play.yardage < self.yardsToFirstDown:
                        self.yardsToEndzone -= self.play.yardage
                        self.yardsToSafety += self.play.yardage
                        self.yardsToFirstDown -= self.play.yardage
                        if self.down < 4:
                            self.down += 1
                            if self.down == 2:
                                self.play.playResult = PlayResult.SecondDown
                            elif self.down == 3:
                                self.play.playResult = PlayResult.ThirdDown
                            elif self.down == 4:
                                self.play.playResult = PlayResult.FourthDown
                            continue
                        else:
                            self.play.playResult = PlayResult.TurnoverOnDowns
                            self.turnover(self.offensiveTeam, self.defensiveTeam, self.yardsToSafety)
                            break
            
        else:
            self.formatPlayText()
            if self.play.playResult is PlayResult.FieldGoalGood or self.play.playResult is PlayResult.Safety or self.play.playResult is PlayResult.TouchdownXP or self.play.playResult is PlayResult.TouchdownNoXP:
                self.scoringPlaysList.insert(0, self.play)
                self.play.scoreChange = True
            self.playsList.insert(0,self.play)

        if self.awayScore > self.homeScore:
            self.winningTeam = self.awayTeam
            self.losingTeam = self.homeTeam
            self.gameDict['score'] = '{0} - {1}'.format(self.awayScore, self.homeScore)
        elif self.homeScore > self.awayScore:
            self.winningTeam = self.homeTeam
            self.losingTeam = self.awayTeam
            self.gameDict['score'] = '{0} - {1}'.format(self.homeScore, self.awayScore)

        if self.isRegularSeasonGame:
            self.winningTeam.seasonTeamStats['wins'] += 1
            self.losingTeam.seasonTeamStats['losses'] += 1

            if self.winningTeam.division is self.losingTeam.division:
                self.winningTeam.seasonTeamStats['divWins'] += 1
                self.losingTeam.seasonTeamStats['divLosses'] += 1

        self.status = GameStatus.Final
        self.gameDict['winningTeam'] = self.winningTeam.name
        self.gameDict['losingTeam'] = self.losingTeam.name
        self.saveGameData()
        self.homeTeam.getAverages()
        self.awayTeam.getAverages()
        self.winningTeam.updateRating()
        self.losingTeam.updateRating()



class Play():
    def __init__(self, game:Game):
        self.offense = game.offensiveTeam
        self.defense = game.defensiveTeam
        self.homeTeamScore = game.homeScore
        self.awayTeamScore = game.awayScore
        self.quarter = game.currentQuarter
        self.down = game.down
        self.playsLeft = 132 - game.totalPlays
        self.yardLine = game.yardLine
        self.yardsToEndzone = game.yardsToEndzone
        if self.yardsToEndzone <= 10:
            self.yardsTo1st = 'Goal'
        else:
            self.yardsTo1st = game.yardsToFirstDown
        self.yardage = 0
        self.fgDistance = 0
        self.playType: PlayType = None
        self.passType: PassType = None
        self.playResult: PlayResult = None
        self.runner: FloosPlayer.PlayerRB = None
        self.passer: FloosPlayer.PlayerQB = None
        self.receiver: FloosPlayer.Player = None
        self.kicker: FloosPlayer.PlayerK = None
        self.isPassCompletion = False
        self.isSack = False
        self.isFumble = False
        self.isFumbleLost = False
        self.isFumbleRecovered = False
        self.isInterception = False
        self.isTd = False
        self.isXpTry = False
        self.isFgGood = False
        self.isXpGood = False
        self.isSafety = False
        self.scoreChange = False
        self.playText = ''

    def fieldGoalTry(self):
        self.kicker = self.offense.rosterDict['k']
        self.kicker.gameStatsDict['fgAtt'] += 1
        yardsToFG = self.yardsToEndzone + 17
        self.fgDistance = yardsToFG
        x = randint(1,100)
        if yardsToFG <= 20:
            if (self.kicker.gameAttributes.overallRating + 20) >= x:
                self.isFgGood = True
                self.kicker.gameStatsDict['fgs'] += 1
                self.kicker.updateInGameConfidence(.005)
            else:
                self.kicker.updateInGameConfidence(-.02)
        elif yardsToFG > 20 and yardsToFG <= 45:
            if (self.kicker.gameAttributes.overallRating + 5) >= x:
                self.isFgGood = True
                self.kicker.gameStatsDict['fgs'] += 1
                self.kicker.updateInGameConfidence(.01)
            else:
                self.kicker.updateInGameConfidence(-.015)
        elif yardsToFG > 45 and yardsToFG <= 55:
            if (self.kicker.gameAttributes.overallRating - 20) >= x:
                self.isFgGood = True
                self.kicker.gameStatsDict['fgs'] += 1
                self.kicker.gameStatsDict['fg45+'] += 1
                self.kicker.updateInGameConfidence(.015)
            else:
                self.kicker.updateInGameConfidence(-.01)
        else:
            if (self.kicker.gameAttributes.overallRating - 30) >= x:
                self.isFgGood = True
                self.kicker.gameStatsDict['fgs'] += 1
                self.kicker.gameStatsDict['fg45+'] += 1
                self.kicker.updateInGameConfidence(.02)
            else:
                self.kicker.updateInGameConfidence(-.01)
        if self.isFgGood:
            if yardsToFG > self.kicker.gameStatsDict['longest']:
                self.kicker.gameStatsDict['longest'] = yardsToFG
        self.kicker.updateRating()

    def extraPointTry(self):
        self.playType = PlayType.ExtraPoint
        self.kicker = self.offense.rosterDict['k']
        x = randint(1,100)
        if (self.kicker.gameAttributes.overallRating + 10) >= x:
            self.isXpGood = True
        self.kicker.updateRating()
    
    def runPlay(self):
        self.playType = PlayType.Run
        self.runner = self.offense.rosterDict['rb']
        blocker: FloosPlayer.PlayerTE = self.offense.rosterDict['te']
        self.runner.gameStatsDict['carries'] += 1
        x = randint(1,100)
        fumbleRoll = randint(1,100)
        fumbleResist = round(((self.runner.gameAttributes.power*1) + (self.runner.gameAttributes.luck*.7) + (self.runner.gameAttributes.discipline*1.3))/3)
        playStrength = ((self.runner.gameAttributes.overallRating*1.3) + (blocker.gameAttributes.power*.7))/2
        if (self.defense.runDefenseRating + randint(-3,3)) >= (playStrength + randint(-3,3)):
            if x < 20:
                self.yardage = randint(-2,0)
                self.runner.updateInGameConfidence(-.005)
            elif x >= 20 and x <= 70:
                self.yardage = randint(0,3)
            elif x > 70 and x <= 99:
                self.yardage = randint(4,7)
            else:
                if self.yardsToEndzone < 7:
                    self.yardage = randint(0, self.yardsToEndzone)
                else:
                    self.yardage = randint(7, self.yardsToEndzone)
                self.runner.updateInGameConfidence(.01)
            if (fumbleRoll/fumbleResist) > 1.15:
                #fumble
                self.isFumble = True
                if (self.defense.runDefenseRating + randint(-3,3)) >= ((((self.runner.gameAttributes.power*1.3)+(self.runner.gameAttributes.luck*.7))/2) + randint(-3,3)):
                    self.runner.gameStatsDict['fumblesLost'] += 1
                    self.runner.updateInGameConfidence(-.02)
                    self.defense.updateGameConfidence(.02)
                    self.defense.gameDefenseStats['fumRec'] += 1
                    self.isFumbleLost = True
                    self.playResult = PlayResult.Fumble

        else:
            if x < 50:
                self.yardage = randint(0,3)
            elif x >= 50 and x < 85:
                self.yardage = randint(4,7)
            elif x >= 85 and x < 90:
                self.yardage = randint(8,10)
                self.runner.updateInGameConfidence(.005)
            elif x >= 90 and x <= 95:
                self.yardage = randint(11,20)
            else:
                if self.yardsToEndzone < 20:
                    self.yardage = randint(0, self.yardsToEndzone)
                else:
                    self.yardage = randint(20, self.yardsToEndzone)
                self.runner.updateInGameConfidence(.01)
            if (fumbleRoll/fumbleResist) > 1.2:
                #fumble
                self.isFumble = True
                if (self.defense.runDefenseRating + randint(-3,3)) >= ((((self.runner.gameAttributes.power*1.3)+(self.runner.gameAttributes.luck*.7))/2) + randint(-3,3)):
                    self.runner.gameStatsDict['fumblesLost'] += 1
                    self.runner.updateInGameConfidence(-.02)
                    self.defense.updateGameConfidence(.02)
                    self.defense.gameDefenseStats['fumRec'] += 1
                    self.isFumbleLost = True
                    self.playResult = PlayResult.Fumble

        if self.yardage > self.yardsToEndzone:
            self.yardage = self.yardsToEndzone

        self.runner.gameStatsDict['runYards'] += self.yardage
        self.runner.gameStatsDict['carries'] += 1
        self.defense.gameDefenseStats['runYardsAlwd'] += self.yardage
        self.defense.gameDefenseStats['totalYardsAlwd'] += self.yardage
        if self.yardage >= 20:
            self.runner.gameStatsDict['run20+'] += 1
        if self.yardage > self.runner.gameStatsDict['longest']:
            self.runner.gameStatsDict['longest'] = self.yardage

    def passPlay(self, passType: PassType):
        self.passType = passType
        self.playType = PlayType.Pass
        self.passer = self.offense.rosterDict['qb']
        rb: FloosPlayer.PlayerRB = self.offense.rosterDict['rb']
        wr1: FloosPlayer.PlayerWR = self.offense.rosterDict['wr1']
        wr2: FloosPlayer.PlayerWR = self.offense.rosterDict['wr2']
        te: FloosPlayer.PlayerTE = self.offense.rosterDict['te']
        sackRoll = randint(1,1000)
        sackModifyer = (self.defense.defenseRating + randint(-3,3))/(self.passer.gameAttributes.agility + randint(-3,3))

        if sackRoll < round(100 * (sackModifyer)):
            self.yardage = round(-(randint(0,5) * sackModifyer))
            self.defense.gameDefenseStats['sacks'] += 1
            self.isSack = True
            fumbleRoll = randint(1,100)
            fumbleResist = round(((self.passer.gameAttributes.power*1) + (self.passer.gameAttributes.luck*.7) + (self.passer.gameAttributes.discipline*1.3))/3)
            if (fumbleRoll/fumbleResist) > 1.15:
                #fumble
                self.isFumble = True
                if (self.defense.defenseRating + randint(-3,3)) >= ((((self.passer.gameAttributes.power*1.3)+(self.passer.gameAttributes.luck*.7))/2) + randint(-3,3)):
                    self.passer.updateInGameConfidence(-.02)
                    self.defense.updateGameConfidence(.02)
                    self.defense.gameDefenseStats['fumRec'] += 1
                    self.isFumbleLost = True
                    self.playResult = PlayResult.Fumble
        else:
            self.passer.gameStatsDict['passAtt'] += 1
            passTarget = randint(1,10)

            if passType.value == 1:
                if passTarget < 4:
                    self.receiver = rb 
                elif passTarget >= 4 and passTarget < 8:
                    self.receiver  = te
                else:
                    x = randint(1,2)
                    if x == 1:
                        self.receiver = wr1
                    else:
                        self.receiver = wr2

                accRoll = randint(1,100)
                receiverYACRating = (self.receiver.gameAttributes.agility+self.receiver.gameAttributes.speed+self.receiver.gameAttributes.playMakingAbility)/3
                if accRoll < (self.passer.gameAttributes.overallRating - (self.defense.passDefenseRating/12)):
                    dropRoll = round(randint(1,100) + (self.defense.passDefenseRating/10))
                    if (self.receiver.gameAttributes.hands) > dropRoll:
                        passYards = randint(0,5)
                        yac = 0
                        x = randint(1,10)
                        if receiverYACRating > self.defense.defenseRating:
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
                            
                        self.yardage = passYards + yac
                        if self.yardage > self.yardsToEndzone:
                            self.yardage = self.yardsToEndzone
                        self.passer.gameStatsDict['passYards'] += self.yardage
                        self.passer.gameStatsDict['passComp'] += 1
                        self.receiver.gameStatsDict['passTargets'] += 1
                        self.receiver.gameStatsDict['receptions'] += 1
                        self.receiver.gameStatsDict['rcvYards'] += self.yardage
                        self.defense.gameDefenseStats['passYardsAlwd'] += self.yardage
                        self.defense.gameDefenseStats['totalYardsAlwd'] += self.yardage
                        self.passer.updateInGameConfidence(0.005)
                        self.receiver.updateInGameConfidence(0.005)
                        self.isPassCompletion = True
                        if self.yardage >= 20:
                            self.passer.gameStatsDict['pass20+'] += 1
                            self.receiver.gameStatsDict['pass20+'] += 1
                        if self.yardage > self.passer.gameStatsDict['longest']:
                            self.passer.gameStatsDict['longest'] = self.yardage
                        if self.yardage > self.receiver.gameStatsDict['longest']:
                            self.receiver.gameStatsDict['longest'] = self.yardage
                    else:
                        self.receiver.gameStatsDict['passTargets'] += 1
                        self.receiver.updateInGameConfidence(-.005)

                else:
                    interceptRoll = randint(1,100)
                    if interceptRoll <= 8:
                        self.yardage = randint(-2,5)
                        self.passer.gameStatsDict['ints'] += 1
                        self.passer.updateInGameConfidence(-.02)
                        self.defense.updateGameConfidence(.02)
                        self.defense.gameDefenseStats['ints'] += 1
                        self.playResult = PlayResult.Interception
                    else:
                        self.passer.updateInGameConfidence(-.005)

            elif passType.value == 2:
                if passTarget < 2:
                    self.receiver = rb   
                elif passTarget >= 3 and passTarget < 5:
                    self.receiver = te
                else:
                    x = randint(1,2)
                    if x == 1:
                        self.receiver = wr1
                    else:
                        self.receiver = wr2
                accRoll = randint(1,100)
                receiverYACRating = (self.receiver.gameAttributes.agility+self.receiver.gameAttributes.speed+self.receiver.gameAttributes.playMakingAbility)/3
                if accRoll < (self.passer.gameAttributes.overallRating - (self.defense.passDefenseRating/8)):
                    dropRoll = round(randint(1,100) + (self.defense.passDefenseRating/10))
                    if self.receiver.gameAttributes.overallRating > dropRoll:
                        passYards = randint(5,10)
                        yac = 0
                        x = randint(1,10)
                        if receiverYACRating > self.defense.defenseRating:
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
                        self.yardage = passYards + yac
                        if self.yardage > self.yardsToEndzone:
                            self.yardage = self.yardsToEndzone
                        self.passer.gameStatsDict['passYards'] += self.yardage
                        self.passer.gameStatsDict['passComp'] += 1
                        self.receiver.gameStatsDict['passTargets'] += 1
                        self.receiver.gameStatsDict['receptions'] += 1
                        self.receiver.gameStatsDict['rcvYards'] += self.yardage
                        self.defense.gameDefenseStats['passYardsAlwd'] += self.yardage
                        self.defense.gameDefenseStats['totalYardsAlwd'] += self.yardage
                        self.passer.updateInGameConfidence(.005)
                        self.receiver.updateInGameConfidence(.005)
                        self.isPassCompletion = True
                        if self.yardage >= 20:
                            self.passer.gameStatsDict['pass20+'] += 1
                            self.receiver.gameStatsDict['pass20+'] += 1
                        if self.yardage > self.passer.gameStatsDict['longest']:
                            self.passer.gameStatsDict['longest'] = self.yardage
                        if self.yardage > self.receiver.gameStatsDict['longest']:
                            self.receiver.gameStatsDict['longest'] = self.yardage
                    else:
                        self.receiver.gameStatsDict['passTargets'] += 1 
                        self.receiver.updateInGameConfidence(-.005)
                else:
                    interceptRoll = randint(1,100)
                    if interceptRoll <= 10:
                        self.yardage = randint(0,10)
                        self.passer.gameStatsDict['ints'] += 1 
                        self.passer.updateInGameConfidence(-.02)
                        self.defense.updateGameConfidence(.02)
                        self.defense.gameDefenseStats['ints'] += 1
                        self.playResult = PlayResult.Interception
                    else:  
                        self.passer.updateInGameConfidence(-.005)

            elif passType.value == 3:
                if passTarget < 3:
                    self.receiver = te   
                else:
                    x = randint(1,2)
                    if x == 1:
                        self.receiver = wr1
                    else:
                        self.receiver = wr2
                accRoll = randint(1,100)
                receiverYACRating = (self.receiver.gameAttributes.agility+self.receiver.gameAttributes.speed+self.receiver.gameAttributes.playMakingAbility)/3
                if accRoll < (self.passer.gameAttributes.overallRating - (self.defense.passDefenseRating/5)):
                    dropRoll = round(randint(1,100) + (self.defense.passDefenseRating/10))
                    if self.receiver.gameAttributes.overallRating > dropRoll:
                        passYards = randint(11,20)
                        yac = 0
                        x = randint(1,10)
                        if receiverYACRating > self.defense.defenseRating:
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
                        self.yardage = passYards + yac
                        if self.yardage > self.yardsToEndzone:
                            self.yardage = self.yardsToEndzone
                        self.passer.gameStatsDict['passYards'] += self.yardage
                        self.passer.gameStatsDict['passComp'] += 1
                        self.receiver.gameStatsDict['passTargets'] += 1
                        self.receiver.gameStatsDict['receptions'] += 1
                        self.receiver.gameStatsDict['rcvYards'] += self.yardage
                        self.defense.gameDefenseStats['passYardsAlwd'] += self.yardage
                        self.defense.gameDefenseStats['totalYardsAlwd'] += self.yardage
                        self.passer.updateInGameConfidence(.01)
                        self.receiver.updateInGameConfidence(.01)
                        self.isPassCompletion = True
                        if self.yardage >= 20:
                            self.passer.gameStatsDict['pass20+'] += 1
                            self.receiver.gameStatsDict['pass20+'] += 1
                        if self.yardage > self.passer.gameStatsDict['longest']:
                            self.passer.gameStatsDict['longest'] = self.yardage
                        if self.yardage > self.receiver.gameStatsDict['longest']:
                            self.receiver.gameStatsDict['longest'] = self.yardage
                    else:
                        self.receiver.gameStatsDict['passTargets'] += 1  
                        self.receiver.updateInGameConfidence(-.005)
                else:
                    interceptRoll = randint(1,100)
                    if interceptRoll <= 15:
                        self.yardage = randint(-5,20)
                        self.passer.gameStatsDict['ints'] += 1 
                        self.passer.updateInGameConfidence(-.02)
                        self.defense.updateGameConfidence(.02)
                        self.defense.gameDefenseStats['ints'] += 1
                        self.playResult = PlayResult.Interception
                    else: 
                        self.passer.updateInGameConfidence(-.005)
