import enum
from gettext import find
from random import randint
import copy
import asyncio
import math
from secrets import choice
from time import sleep
import floosball_player as FloosPlayer
import floosball_team as FloosTeam
import floosball_methods as FloosMethods
import datetime

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
    hailMary = 4
    throwAway = 5

class GameStatus(enum.Enum):
    Scheduled = 1
    Active = 2
    Final = 3

class QbDropback(enum.Enum):
    short = 0
    medium = 2
    long = 4
    extraLong = 6

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


shortRunList =  [
                    'runs',
                    'dives',
                    'dashes'
                ]

midRunList =    [
                    'runs',
                    'races',
                    'rumbles',
                    'breaks through',
                    'busts through'
                ]

longRunList =   [
                    'runs',
                    'streaks',
                    'explodes',
                    'sprints',
                    'races',
                    'breaks out',
                    'busts out'
                ]

lossRunList =   [
                    'is stuffed',
                    'is stopped'
                ]

shortPassList = [
                    'quick pass to',
                    'short pass to',
                    'tosses to',
                    'passes to',
                    'screen pass to'
                ]

midPassList =   [
                    'zips a pass to',
                    'fires a pass to',
                    'passes to',
                    'throws to',
                    'finds'
                ]

longPassList = [
                    'passes to',
                    'long throw to',
                    'rifles a pass to',
                    'lobs a pass to'
                ]
extraLongPassList = [
                    'heaves it to',
                    'throws a prayer to',
                    'throws a Hail Mary to',
                    'deep pass to',
                    'throws it deep to'
                ]

passPlayBook = {
                    'Play1': {
                        'dropback': QbDropback.long,
                        'targets': {
                            'wr1': PassType.long,
                            'wr2': PassType.medium,
                            'te': PassType.medium,
                            'rb': PassType.short
                        }
                    },
                    'Play2': {
                        'dropback': QbDropback.long,
                        'targets': {
                            'wr1': PassType.long,
                            'wr2': PassType.long,
                            'te': PassType.medium,
                            'rb': PassType.short
                        }
                    },
                    'Play3': {
                        'dropback': QbDropback.medium,
                        'targets': {
                            'wr1': PassType.medium,
                            'wr2': PassType.medium,
                            'te': PassType.short,
                            'rb': None
                        }
                    },
                    'Play4': {
                        'dropback': QbDropback.long,
                        'targets': {
                            'wr1': PassType.long,
                            'wr2': PassType.long,
                            'te': None,
                            'rb': None
                        }
                    },
                    'Play5': {
                        'dropback': QbDropback.long,
                        'targets': {
                            'wr1': PassType.long,
                            'wr2': PassType.medium,
                            'te': PassType.short,
                            'rb': None
                        }
                    },
                    'Play6': {
                        'dropback': QbDropback.medium,
                        'targets': {
                            'wr1': PassType.medium,
                            'wr2': PassType.medium,
                            'te': PassType.medium,
                            'rb': PassType.short
                        }
                    },
                    'Play7': {
                        'dropback': QbDropback.medium,
                        'targets': {
                            'wr1': PassType.medium,
                            'wr2': PassType.medium,
                            'te': PassType.medium,
                            'rb': PassType.medium
                        }
                    },
                    'Play8': {
                        'dropback': QbDropback.short,
                        'targets': {
                            'wr1': PassType.short,
                            'wr2': PassType.short,
                            'te': PassType.short,
                            'rb': PassType.short
                        }
                    },
                    'Play9': {
                        'dropback': QbDropback.extraLong,
                        'targets': {
                            'wr1': PassType.hailMary,
                            'wr2': PassType.hailMary,
                            'te': None,
                            'rb': None
                        }
                    },
                    'Play10': {
                        'dropback': QbDropback.short,
                        'targets': {
                            'wr1': None,
                            'wr2': None,
                            'te': None,
                            'rb': PassType.short
                        }
                    }
                }

def returnShortPassPlay():
    return choice(['Play8','Play10'])

def returnMediumPassPlay():
    return choice(['Play3','Play6','Play7'])

def returnLongPassPlay():
    return choice(['Play1','Play2','Play4','Play5'])
    
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
        self.homeTeamElo = None
        self.awayTeamElo = None
        self.homeTeamWinProbability = None
        self.awayTeamWinProbability = None
        self.totalPlays = 0
        self.winningTeam: FloosTeam.Team = None
        self.losingTeam: FloosTeam.Team = None
        self.play: Play = None
        self.gameDict = {}
        self.gameFeed = []
        self.highlights = []
        self.leagueHighlights = []
        self.otHomeHadPos = False
        self.otAwayHadPos = False
        self.startTime: datetime.datetime = None
        self.isTwoPtConv = False
        self.isOnsideKick = False

    def getGameData(self):
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
                homeTeamPassTds = player.gameStatsDict['passing']['tds']
                homeTeamPassYards += player.gameStatsDict['passing']['yards']
                if player.gameStatsDict['passing']['comp'] > 0:
                    player.gameStatsDict['passing']['ypc'] = round(player.gameStatsDict['passing']['yards']/player.gameStatsDict['passing']['comp'],2)
                    player.gameStatsDict['passing']['compPerc'] = round((player.gameStatsDict['passing']['comp']/player.gameStatsDict['passing']['att'])*100)
            elif player.position is FloosPlayer.Position.RB:
                homeTeamRushYards += player.gameStatsDict['rushing']['yards']
                homeTeamRushTds = player.gameStatsDict['rushing']['tds']
                if player.gameStatsDict['rushing']['carries'] > 0:
                    player.gameStatsDict['rushing']['ypc'] = round(player.gameStatsDict['rushing']['yards']/player.gameStatsDict['rushing']['carries'],2)
                if player.gameStatsDict['receiving']['yards'] > 0:
                    player.gameStatsDict['receiving']['ypr'] = round(player.gameStatsDict['receiving']['yards']/player.gameStatsDict['receiving']['receptions'],2)
                    player.gameStatsDict['receiving']['rcvPerc'] = round((player.gameStatsDict['receiving']['receptions']/player.gameStatsDict['receiving']['targets'])*100)
            elif player.position is FloosPlayer.Position.WR or player.position is FloosPlayer.Position.TE:
                if player.gameStatsDict['receiving']['receptions'] > 0:
                    player.gameStatsDict['receiving']['ypr'] = round(player.gameStatsDict['receiving']['yards']/player.gameStatsDict['receiving']['receptions'],2)
                    player.gameStatsDict['receiving']['rcvPerc'] = round((player.gameStatsDict['receiving']['receptions']/player.gameStatsDict['receiving']['targets'])*100)
            elif player.position is FloosPlayer.Position.K:
                homeTeamFgs = player.gameStatsDict['kicking']['fgs']
                if player.gameStatsDict['kicking']['fgs'] > 0:
                    player.gameStatsDict['kicking']['fgPerc'] = round((player.gameStatsDict['kicking']['fgs']/player.gameStatsDict['kicking']['fgAtt'])*100)
                    player.gameStatsDict['kicking']['fgAvg'] = round(player.gameStatsDict['kicking']['fgYards']/player.gameStatsDict['kicking']['fgs'])
                else:
                    player.gameStatsDict['kicking']['fgPerc'] = 0

            playerDict['name'] = player.name
            playerDict['id'] = player.id
            playerDict['number'] = player.currentNumber
            playerDict['ratingStars'] = player.playerTier.value
            playerDict['gameStats'] = copy.deepcopy(player.gameStatsDict)

            homeTeamStatsDict[pos] = playerDict

        for pos, player in self.awayTeam.rosterDict.items():
            playerDict = {}
            if player.position is FloosPlayer.Position.QB:
                awayTeamPassTds = player.gameStatsDict['passing']['tds']
                awayTeamPassYards += player.gameStatsDict['passing']['yards']
                if player.gameStatsDict['passing']['comp'] > 0:
                    player.gameStatsDict['passing']['ypc'] = round(player.gameStatsDict['passing']['yards']/player.gameStatsDict['passing']['comp'],2)
                    player.gameStatsDict['passing']['compPerc'] = round((player.gameStatsDict['passing']['comp']/player.gameStatsDict['passing']['att'])*100)
            elif player.position is FloosPlayer.Position.RB:
                awayTeamRushYards += player.gameStatsDict['rushing']['yards']
                awayTeamRushTds = player.gameStatsDict['rushing']['tds']
                if player.gameStatsDict['rushing']['carries'] > 0:
                    player.gameStatsDict['rushing']['ypc'] = round(player.gameStatsDict['rushing']['yards']/player.gameStatsDict['rushing']['carries'],2)
                if player.gameStatsDict['receiving']['yards'] > 0:
                    player.gameStatsDict['receiving']['ypr'] = round(player.gameStatsDict['receiving']['yards']/player.gameStatsDict['receiving']['receptions'],2)
                    player.gameStatsDict['receiving']['rcvPerc'] = round((player.gameStatsDict['receiving']['receptions']/player.gameStatsDict['receiving']['targets'])*100)
            elif player.position is FloosPlayer.Position.WR or player.position is FloosPlayer.Position.TE:
                if player.gameStatsDict['receiving']['receptions'] > 0:
                    player.gameStatsDict['receiving']['ypr'] = round(player.gameStatsDict['receiving']['yards']/player.gameStatsDict['receiving']['receptions'],2)
                    player.gameStatsDict['receiving']['rcvPerc'] = round((player.gameStatsDict['receiving']['receptions']/player.gameStatsDict['receiving']['targets'])*100)
            elif player.position is FloosPlayer.Position.K:
                awayTeamFgs = player.gameStatsDict['kicking']['fgs']
                if player.gameStatsDict['kicking']['fgs'] > 0:
                    player.gameStatsDict['kicking']['fgPerc'] = round((player.gameStatsDict['kicking']['fgs']/player.gameStatsDict['kicking']['fgAtt'])*100)
                    player.gameStatsDict['kicking']['fgAvg'] = round(player.gameStatsDict['kicking']['fgYards']/player.gameStatsDict['kicking']['fgs'])
                else:
                    player.gameStatsDict['kicking']['fgPerc'] = 0

            playerDict['name'] = player.name
            playerDict['id'] = player.id
            playerDict['number'] = player.currentNumber
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
        homeTeamStatsDict['defenseRating'] = self.homeTeam.defenseOverallTier
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
        awayTeamStatsDict['defenseRating'] = self.awayTeam.defenseOverallTier
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
        if self.yardsToEndzone <= 10:
            gameStatsDict['yardsTo1stDwn'] = self.yardsToEndzone
            gameStatsDict['downText'] = '{0} & Goal'.format(down)
        else:
            gameStatsDict['yardsTo1stDwn'] = self.yardsToFirstDown
            gameStatsDict['downText'] = '{0} & {1}'.format(down, self.yardsToFirstDown)
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
                homeTeamPassTds = player.gameStatsDict['passing']['tds']
                homeTeamPassYards += player.gameStatsDict['passing']['yards']
                if player.gameStatsDict['passing']['comp'] > 0:
                    player.gameStatsDict['passing']['ypc'] = round(player.gameStatsDict['passing']['yards']/player.gameStatsDict['passing']['comp'],2)
                    player.gameStatsDict['passing']['compPerc'] = round((player.gameStatsDict['passing']['comp']/player.gameStatsDict['passing']['att'])*100)
            elif player.position is FloosPlayer.Position.RB:
                homeTeamRushYards += player.gameStatsDict['rushing']['yards']
                homeTeamRushTds = player.gameStatsDict['rushing']['tds']
                if player.gameStatsDict['rushing']['carries'] > 0:
                    player.gameStatsDict['rushing']['ypc'] = round(player.gameStatsDict['rushing']['yards']/player.gameStatsDict['rushing']['carries'],2)
                if player.gameStatsDict['receiving']['yards'] > 0:
                    player.gameStatsDict['receiving']['ypr'] = round(player.gameStatsDict['receiving']['yards']/player.gameStatsDict['receiving']['receptions'],2)
                    player.gameStatsDict['receiving']['rcvPerc'] = round((player.gameStatsDict['receiving']['receptions']/player.gameStatsDict['receiving']['targets'])*100)
            elif player.position is FloosPlayer.Position.WR or player.position is FloosPlayer.Position.TE:
                if player.gameStatsDict['receiving']['receptions'] > 0:
                    player.gameStatsDict['receiving']['ypr'] = round(player.gameStatsDict['receiving']['yards']/player.gameStatsDict['receiving']['receptions'],2)
                    player.gameStatsDict['receiving']['rcvPerc'] = round((player.gameStatsDict['receiving']['receptions']/player.gameStatsDict['receiving']['targets'])*100)
            elif player.position is FloosPlayer.Position.K:
                homeTeamFgs = player.gameStatsDict['kicking']['fgs']
                if player.gameStatsDict['kicking']['fgs'] > 0:
                    player.gameStatsDict['kicking']['fgPerc'] = round((player.gameStatsDict['kicking']['fgs']/player.gameStatsDict['kicking']['fgAtt'])*100)
                    player.gameStatsDict['kicking']['fgAvg'] = round(player.gameStatsDict['kicking']['fgYards']/player.gameStatsDict['kicking']['fgs'])
                else:
                    player.gameStatsDict['kicking']['fgPerc'] = 0

            playerDict['name'] = player.name
            playerDict['id'] = player.id
            playerDict['ratingStars'] = player.playerTier.value
            playerDict['gameStats'] = copy.deepcopy(player.gameStatsDict)

            homeTeamStatsDict[pos] = playerDict

        for pos, player in self.awayTeam.rosterDict.items():
            playerDict = {}
            if player.position is FloosPlayer.Position.QB:
                awayTeamPassTds = player.gameStatsDict['passing']['tds']
                awayTeamPassYards += player.gameStatsDict['passing']['yards']
                if player.gameStatsDict['passing']['comp'] > 0:
                    player.gameStatsDict['passing']['ypc'] = round(player.gameStatsDict['passing']['yards']/player.gameStatsDict['passing']['comp'],2)
                    player.gameStatsDict['passing']['compPerc'] = round((player.gameStatsDict['passing']['comp']/player.gameStatsDict['passing']['att'])*100)
            elif player.position is FloosPlayer.Position.RB:
                awayTeamRushYards += player.gameStatsDict['rushing']['yards']
                awayTeamRushTds = player.gameStatsDict['rushing']['tds']
                if player.gameStatsDict['rushing']['carries'] > 0:
                    player.gameStatsDict['rushing']['ypc'] = round(player.gameStatsDict['rushing']['yards']/player.gameStatsDict['rushing']['carries'],2)
                if player.gameStatsDict['receiving']['yards'] > 0:
                    player.gameStatsDict['receiving']['ypr'] = round(player.gameStatsDict['receiving']['yards']/player.gameStatsDict['receiving']['receptions'],2)
                    player.gameStatsDict['receiving']['rcvPerc'] = round((player.gameStatsDict['receiving']['receptions']/player.gameStatsDict['receiving']['targets'])*100)
            elif player.position is FloosPlayer.Position.WR or player.position is FloosPlayer.Position.TE:
                if player.gameStatsDict['receiving']['receptions'] > 0:
                    player.gameStatsDict['receiving']['ypr'] = round(player.gameStatsDict['receiving']['yards']/player.gameStatsDict['receiving']['receptions'],2)
                    player.gameStatsDict['receiving']['rcvPerc'] = round((player.gameStatsDict['receiving']['receptions']/player.gameStatsDict['receiving']['targets'])*100)
            elif player.position is FloosPlayer.Position.K:
                awayTeamFgs = player.gameStatsDict['kicking']['fgs']
                if player.gameStatsDict['kicking']['fgs'] > 0:
                    player.gameStatsDict['kicking']['fgPerc'] = round((player.gameStatsDict['kicking']['fgs']/player.gameStatsDict['kicking']['fgAtt'])*100)
                    player.gameStatsDict['kicking']['fgAvg'] = round(player.gameStatsDict['kicking']['fgYards']/player.gameStatsDict['kicking']['fgs'])
                else:
                    player.gameStatsDict['kicking']['fgPerc'] = 0

            playerDict['name'] = player.name
            playerDict['id'] = player.id
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
        homeTeamStatsDict['defenseRating'] = self.homeTeam.defenseOverallTier
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
        awayTeamStatsDict['defenseRating'] = self.awayTeam.defenseOverallTier
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
            if self.homeScore == self.awayScore:
                if self.otHomeHadPos and self.otAwayHadPos:
                    if self.down == 4:
                        if self.yardsToEndzone <= (self.offensiveTeam.rosterDict['k'].maxFgDistance - 17):
                            self.play.playType = PlayType.FieldGoal
                            return
                    else:
                        if self.yardsToEndzone <= 20:
                            self.play.playType = PlayType.FieldGoal
                            return
                elif self.homeTeam == self.play.offense and self.otAwayHadPos:
                    if self.down == 4:
                        if self.yardsToEndzone <= (self.offensiveTeam.rosterDict['k'].maxFgDistance - 17):
                            self.play.playType = PlayType.FieldGoal
                            return
                    else:
                        if self.yardsToEndzone <= 20:
                            self.play.playType = PlayType.FieldGoal
                            return
                elif self.awayTeam == self.play.offense and self.otHomeHadPos:
                    if self.down == 4:
                        if self.yardsToEndzone <= (self.offensiveTeam.rosterDict['k'].maxFgDistance - 17):
                            self.play.playType = PlayType.FieldGoal
                            return
                    else:
                        if self.yardsToEndzone <= 20:
                            self.play.playType = PlayType.FieldGoal
                            return
            if self.down == 4:
                if self.homeTeam == self.play.offense and self.homeScore < self.awayScore:
                    scoreDiff = self.awayScore - self.homeScore
                    if scoreDiff <= 3:
                        if self.yardsToEndzone <= (self.offensiveTeam.rosterDict['k'].maxFgDistance - 17):
                            self.play.playType = PlayType.FieldGoal
                            return
                        elif self.yardsToFirstDown <= 2:
                            self.play.passPlay(returnShortPassPlay())
                            return
                        elif self.yardsToFirstDown <= 8:
                            self.play.passPlay(returnMediumPassPlay())
                            return
                        else:
                            self.play.passPlay(returnLongPassPlay())
                            return
                    else:
                        if self.yardsToFirstDown <= 2:
                            self.play.passPlay(returnShortPassPlay())
                            return
                        elif self.yardsToFirstDown <= 8:
                            self.play.passPlay(returnMediumPassPlay())
                            return
                        else:
                            self.play.passPlay(returnLongPassPlay())
                            return
                elif self.awayTeam == self.play.offense and self.awayScore < self.homeScore:
                    scoreDiff = self.homeScore - self.awayScore
                    if scoreDiff <= 3:
                        if self.yardsToEndzone <= (self.offensiveTeam.rosterDict['k'].maxFgDistance - 17):
                            self.play.playType = PlayType.FieldGoal
                            return
                        elif self.yardsToFirstDown <= 2:
                            self.play.passPlay(returnShortPassPlay())
                            return
                        elif self.yardsToFirstDown <= 8:
                            self.play.passPlay(returnMediumPassPlay())
                            return
                        else:
                            self.play.passPlay(returnLongPassPlay())
                            return
                    else:
                        if self.yardsToFirstDown <= 2:
                            self.play.passPlay(returnShortPassPlay())
                            return
                        elif self.yardsToFirstDown <= 8:
                            self.play.passPlay(returnMediumPassPlay())
                            return
                        else:
                            self.play.passPlay(returnLongPassPlay())
                            return
        if self.totalPlays == 65:
            if self.yardsToEndzone <= 10:
                x = randint(1,10)
                if x > 4:
                    self.play.playType = PlayType.FieldGoal
                    return
                else:
                    if self.yardsToEndzone <= 3:
                        x = randint(1,10)
                        if x > 4:
                            self.play.runPlay()
                            return
                        else:
                            self.play.passPlay(returnShortPassPlay())
                            return
                    else:
                        self.play.passPlay(returnMediumPassPlay())
                        return
            elif self.yardsToEndzone > 15 and self.yardsToEndzone <= (self.offensiveTeam.rosterDict['k'].maxFgDistance - 17):
                x = randint(1,10)
                if x > 1:
                    self.play.playType = PlayType.FieldGoal
                    return
                else:
                    self.play.passPlay(returnLongPassPlay())
                    return
            else:
                if self.yardsToEndzone > (self.offensiveTeam.rosterDict['k'].maxFgDistance - 17):
                    self.play.passPlay('Play9')
                elif self.yardsToEndzone > 15:
                    self.play.passPlay(returnLongPassPlay())
                else:
                    self.play.passPlay(returnMediumPassPlay())
                return
        if self.totalPlays == 131:
            if self.homeTeam == self.play.offense and self.homeScore <= self.awayScore:
                scoreDiff = self.awayScore - self.homeScore
                if scoreDiff <= 3 and self.yardsToEndzone <= (self.offensiveTeam.rosterDict['k'].maxFgDistance - 17):
                    self.play.playType = PlayType.FieldGoal
                    return
                elif self.yardsToEndzone >= (self.offensiveTeam.rosterDict['k'].maxFgDistance - 17):
                    self.play.passPlay('Play9')
                    return
                else:
                    #self.homeTeam.inGamePush()
                    if self.yardsToEndzone > 15:
                        self.play.passPlay(returnLongPassPlay())
                    else:
                        self.play.passPlay(returnMediumPassPlay())
                    return
            elif self.awayTeam == self.play.offense and self.awayScore <= self.homeScore:
                scoreDiff = self.homeScore - self.awayScore
                if scoreDiff <= 3 and self.yardsToEndzone <= (self.offensiveTeam.rosterDict['k'].maxFgDistance - 17):
                    self.play.playType = PlayType.FieldGoal
                    return
                elif self.yardsToEndzone >= (self.offensiveTeam.rosterDict['k'].maxFgDistance - 17):
                    self.play.passPlay('Play9')
                    return
                else:
                    #self.homeTeam.inGamePush()
                    if self.yardsToEndzone > 15:
                        self.play.passPlay(returnLongPassPlay())
                    else:
                        self.play.passPlay(returnMediumPassPlay())
                    return
            else:
                self.play.runPlay()
                return
        elif self.down <= 2:
            if self.currentQuarter == 4:
                if self.homeTeam == self.play.offense and self.homeScore < self.awayScore:
                    scoreDiff = self.awayScore - self.homeScore
                    x = randint(1,10)
                    if x < 5:
                        self.play.runPlay()
                        return
                    elif self.yardsToEndzone > 15:
                        if x >= 4 and x < 9:
                            self.play.passPlay(returnMediumPassPlay())
                            return
                        else:
                            self.play.passPlay(returnLongPassPlay())
                            return
                    else:
                        self.play.passPlay(returnMediumPassPlay())
                        return
                elif self.awayTeam == self.play.offense and self.awayScore < self.homeScore:
                    scoreDiff = self.homeScore - self.awayScore
                    x = randint(1,10)
                    if x < 5:
                        self.play.runPlay()
                        return
                    elif self.yardsToEndzone > 15:
                        if x >= 4 and x < 9:
                            self.play.passPlay(returnMediumPassPlay())
                            return
                        else:
                            self.play.passPlay(returnLongPassPlay())
                            return
                    else:
                        self.play.passPlay(returnMediumPassPlay())
                        return
            elif self.yardsToEndzone <= 10:
                x = randint(1,10)
                if x <= 5:
                    self.play.runPlay()
                    return
                else:
                    y = randint(1,10)
                    if y <= 4:
                        self.play.passPlay(returnShortPassPlay())
                        return
                    else:
                        self.play.passPlay(returnMediumPassPlay())
                        return
            elif self.yardsToEndzone <= 20:
                x = randint(1,10)
                if x <= 4:
                    self.play.runPlay()
                    return
                else:
                    y = randint(1,10)
                    if y <= 4:
                        self.play.passPlay(returnShortPassPlay())
                        return
                    elif y > 4 and y <= 8:
                        self.play.passPlay(returnMediumPassPlay())
                        return
                    else:
                        self.play.passPlay(returnLongPassPlay())
                        return
            if self.yardsToSafety <= 5:
                x = randint(1,10)
                if x <= 3:
                    y = randint(0,1)
                    if y == 0:
                        self.play.passPlay(returnMediumPassPlay())
                        return
                    else:
                        self.play.passPlay(returnLongPassPlay())
                        return
                else:
                    self.play.runPlay()
                    return
            else:
                x = randint(0,1)
                if x == 1:
                    self.play.runPlay()
                    return
                else:
                    y = randint(1,10)
                    if y <= 4:
                        self.play.passPlay(returnShortPassPlay())
                        return
                    elif y > 4 and y <= 8:
                        self.play.passPlay(returnMediumPassPlay())
                        return
                    else:
                        self.play.passPlay(returnLongPassPlay())
                        return
    
        elif self.down == 3:
            if self.currentQuarter == 4:
                if self.homeTeam == self.play.offense and self.homeScore < self.awayScore:
                    scoreDiff = self.awayScore - self.homeScore
                    x = randint(1,10)
                    if x < 5:
                        self.play.runPlay()
                        return
                    elif self.yardsToEndzone > 15:
                        if x >= 3 and x < 7:
                            self.play.passPlay(returnMediumPassPlay())
                            return
                        else:
                            self.play.passPlay(returnLongPassPlay())
                            return
                    else:
                        self.play.passPlay(returnMediumPassPlay())
                        return
                elif self.awayTeam == self.play.offense and self.awayScore < self.homeScore:
                    scoreDiff = self.homeScore - self.awayScore
                    x = randint(1,10)
                    if x < 5:
                        self.play.runPlay()
                        return
                    elif self.yardsToEndzone > 15:
                        if x >= 3 and x < 7:
                            self.play.passPlay(returnMediumPassPlay())
                            return
                        else:
                            self.play.passPlay(returnLongPassPlay())
                            return
                    else:
                        self.play.passPlay(returnMediumPassPlay())
                        return
            if self.yardsToFirstDown <= 4 or self.yardsToEndzone <= 10:
                x = randint(1,10)
                if x < 7:
                    self.play.runPlay()
                    return
                elif x >= 7 and x < 9:
                    self.play.passPlay(returnShortPassPlay())
                    return
                else:
                    self.play.passPlay(returnMediumPassPlay())
                    return
            else:
                x = randint(1,10)
                if x < 6:
                    self.play.passPlay(returnMediumPassPlay())
                    return
                elif x >= 6 and x < 9:
                    self.play.passPlay(returnShortPassPlay())
                    return
                else:
                    self.play.passPlay(returnLongPassPlay())
                    return
        elif self.down == 4:
            if self.currentQuarter == 4 and self.awayTeam == self.play.offense and self.awayScore < self.homeScore:
                scoreDiff = self.homeScore - self.awayScore
                if self.totalPlays > 120 and self.yardsToEndzone < 20:
                    if scoreDiff <= 3:
                        self.play.playType = PlayType.FieldGoal
                        return
                    else:
                        self.play.passPlay(returnMediumPassPlay())
                        return
                elif self.totalPlays > 120 and self.yardsToEndzone > 20:
                    if self.yardsToEndzone <= (self.offensiveTeam.rosterDict['k'].maxFgDistance - 17) and scoreDiff <= 3:
                        x = randint(1,10)
                        if x > 3:
                            self.play.playType = PlayType.FieldGoal
                            return
                        else:
                            self.play.passPlay(returnLongPassPlay())
                            return
                    else:
                        self.play.passPlay(returnLongPassPlay())
                        return
                elif self.yardsToFirstDown <= 2:
                    if self.yardsToSafety > 20:
                        if self.yardsToEndzone <= 30:
                            self.play.playType = PlayType.FieldGoal
                            return
                        else:
                            x = randint(1,3)
                            if x <= 2:
                                self.play.passPlay(returnShortPassPlay())
                                return
                            else:
                                self.play.passPlay(returnMediumPassPlay())
                                return
                    else:
                        x = randint(1,10)
                        if x > 8:
                            self.play.playType = PlayType.Punt
                            return
                        else:
                            x = randint(1,3)
                            if x == 1:
                                self.play.runPlay()
                                return
                            elif x == 2:
                                self.play.passPlay(returnShortPassPlay())
                                return
                            else:
                                self.play.passPlay(returnMediumPassPlay())  
                                return       
                else:
                    if self.yardsToEndzone > 30 and self.yardsToEndzone <= (self.offensiveTeam.rosterDict['k'].maxFgDistance - 17) and self.yardsToFirstDown > 6:
                        x = randint(1,10)
                        if x > 3:
                            self.play.playType = PlayType.FieldGoal
                            return
                        else:
                            self.play.passPlay(returnMediumPassPlay())
                            return
                    else:
                        self.play.passPlay(returnMediumPassPlay())
                        return
            elif self.currentQuarter == 4 and self.homeTeam == self.play.offense and self.homeScore < self.awayScore:
                scoreDiff = self.awayScore - self.homeScore
                if self.totalPlays > 120 and self.yardsToEndzone < 20:
                    if scoreDiff <= 3:
                        self.play.playType = PlayType.FieldGoal
                        return
                    else:
                        self.play.passPlay(returnMediumPassPlay())
                        return
                elif self.totalPlays > 120 and self.yardsToEndzone > 20:
                    if self.yardsToEndzone <= (self.offensiveTeam.rosterDict['k'].maxFgDistance - 17) and scoreDiff <= 3:
                        x = randint(1,10)
                        if x > 3:
                            self.play.playType = PlayType.FieldGoal
                            return
                        else:
                            self.play.passPlay(returnLongPassPlay())
                            return
                    else:
                        self.play.passPlay(returnLongPassPlay())
                        return
                elif self.yardsToFirstDown <= 2:
                    if self.yardsToSafety > 20:
                        if self.yardsToEndzone <= 30:
                            self.play.playType = PlayType.FieldGoal
                            return
                        else:
                            x = randint(1,3)
                            if x <= 2:
                                self.play.passPlay(returnShortPassPlay())
                                return
                            else:
                                self.play.passPlay(returnMediumPassPlay())
                                return
                    else:
                        x = randint(1,10)
                        if x > 8:
                            self.play.playType = PlayType.Punt
                            return
                        else:
                            x = randint(1,3)
                            if x == 1:
                                self.play.runPlay()
                                return
                            elif x == 2:
                                self.play.passPlay(returnShortPassPlay())
                                return
                            else:
                                self.play.passPlay(returnMediumPassPlay())
                                return         
                else:
                    if self.yardsToEndzone > 30 and self.yardsToEndzone <= (self.offensiveTeam.rosterDict['k'].maxFgDistance - 17) and self.yardsToFirstDown > 6:
                        x = randint(1,10)
                        if x > 3:
                            self.play.playType = PlayType.FieldGoal
                            return
                        else:
                            self.play.passPlay(returnMediumPassPlay())
                            return
                    else:
                        self.play.passPlay(returnMediumPassPlay())
                        return
            elif self.currentQuarter == 4 and self.homeTeam == self.play.offense and self.homeScore > self.awayScore:
                if self.yardsToEndzone <= (self.offensiveTeam.rosterDict['k'].maxFgDistance - 17):
                    self.play.playType = PlayType.FieldGoal
                    return
                else:
                    self.play.playType = PlayType.Punt
                    return
            elif self.currentQuarter == 4 and self.awayTeam == self.play.offense and self.awayScore > self.homeScore:
                if self.yardsToEndzone <= (self.offensiveTeam.rosterDict['k'].maxFgDistance - 17):
                    self.play.playType = PlayType.FieldGoal
                    return
                else:
                    self.play.playType = PlayType.Punt
                    return
            elif self.yardsToEndzone <= 5:
                    x = randint(1,10)
                    if x < 7:
                        self.play.playType = PlayType.FieldGoal
                        return
                    else:
                        y = randint(1,10)
                        if y < 6:
                            self.play.runPlay()
                            return
                        elif y >= 6 and y < 9:
                            self.play.passPlay(returnShortPassPlay())
                            return
                        else:
                            self.play.passPlay(returnMediumPassPlay())
                            return

            elif self.yardsToEndzone <= 20:
                if self.yardsToFirstDown <= 2:
                    x = randint(1,10)
                    if x >= 3:
                        self.play.playType = PlayType.FieldGoal
                        return
                    else:
                        y = randint(1,3)
                        if y == 1:
                            self.play.runPlay()
                            return
                        elif y == 2:
                            self.play.passPlay(returnShortPassPlay())
                            return
                        else:
                            self.play.passPlay(returnMediumPassPlay())
                            return
                else:
                    x = randint(1,10)
                    if x < 9:
                        self.play.playType = PlayType.FieldGoal
                        return
                    else:
                        self.play.passPlay(returnMediumPassPlay())
                        return
            elif self.yardsToEndzone <= 35:
                if self.yardsToFirstDown <= 2:
                    x = randint(1,10)
                    if x >= 2:
                        self.play.playType = PlayType.FieldGoal
                        return
                    else:
                        y = randint(1,3)
                        if y == 1:
                            self.play.runPlay()
                            return
                        elif y == 2:
                            self.play.passPlay(returnShortPassPlay())
                            return
                        else:
                            self.play.passPlay(returnMediumPassPlay())
                            return
                else:
                    x = randint(1,10)
                    if x < 9:
                        self.play.playType = PlayType.FieldGoal
                        return
                    else:
                        self.play.passPlay(returnMediumPassPlay())
                        return
            elif self.yardsToEndzone <= (self.offensiveTeam.rosterDict['k'].maxFgDistance - 17):
                    x = randint(1,10)
                    if x < 5:
                        self.play.playType = PlayType.FieldGoal
                        return
                    else:
                        self.play.playType = PlayType.Punt
                        return
            elif self.yardsToSafety <= 40:
                self.play.playType = PlayType.Punt
                return
            else:
                if self.yardsToFirstDown <= 2:
                    x = randint(1,10)
                    if x < 8:
                        self.play.playType = PlayType.Punt
                        return
                    elif x >= 7 and x < 9:
                        self.play.passPlay(returnShortPassPlay())
                        return
                    else:
                        self.play.passPlay(returnMediumPassPlay())
                        return
                else:
                    x = randint(1,100)
                    if x < 95:
                        self.play.playType = PlayType.Punt
                        return
                    else:
                        y = randint(0,1)
                        if y == 0:
                            self.play.passPlay(returnMediumPassPlay())
                            return
                        else:
                            self.play.passPlay(returnLongPassPlay())
                            return

    def turnover(self, offense: FloosTeam.Team, defense: FloosTeam.Team, yards):
        if self.totalPlays > 132:
            if offense is self.homeTeam:
                if self.otHomeHadPos == False:
                    self.otHomeHadPos = True
            elif offense is self.awayTeam:
                if self.otAwayHadPos == False:
                    self.otAwayHadPos = True
        self.offensiveTeam = defense
        self.defensiveTeam = offense
        self.yardsToEndzone = yards
        self.yardsToSafety = 100 - self.yardsToEndzone
        self.yardsToFirstDown = 10


    def formatPlayText(self):
        text = None
        if self.play.playType is PlayType.Run:
            if self.play.isFumble:
                if self.play.isFumbleLost:
                    text = '{} runs for {} yards and fumbles, {} recover'.format(self.play.runner.name, self.play.yardage, self.play.defense.abbr)
                else:
                    text = '{} runs for {} yards and fumbles, {} recovers'.format(self.play.runner.name, self.play.yardage, self.play.runner.name)
            else:
                if self.play.yardage <= 0:
                    text = '{} {} for {} yards'.format(self.play.runner.name, choice(lossRunList), self.play.yardage)
                elif self.play.yardage > 0 and self.play.yardage <= 3:
                    text = '{} {} for {} yards'.format(self.play.runner.name, choice(shortRunList), self.play.yardage)
                elif self.play.yardage > 3 and self.play.yardage <= 9:
                    text = '{} {} for {} yards'.format(self.play.runner.name, choice(midRunList), self.play.yardage)
                elif self.play.yardage >= 10:
                    text = '{} {} for {} yards'.format(self.play.runner.name, choice(longRunList), self.play.yardage)
        elif self.play.playType is PlayType.Pass:
            if self.play.isSack:
                if self.play.isFumble:
                    if self.play.isFumbleLost:
                        text = '{} sacked and fumbles, {} recovers'.format(self.play.passer.name, self.play.defense.name)
                    else:
                        text = '{} sacked and fumbles, {} recovers'.format(self.play.passer.name, self.play.passer.name)
                else:
                    text = '{} sacked for {} yards.'.format(self.play.passer.name, self.play.yardage)
            elif self.play.isPassCompletion:
                if self.play.passType is PassType.short:
                    text = '{} {} {} for {} yards'.format(self.play.passer.name, choice(shortPassList), self.play.receiver.name, self.play.yardage)
                elif self.play.passType is PassType.long:
                    text = '{} {} {} for {} yards'.format(self.play.passer.name, choice(longPassList), self.play.receiver.name, self.play.yardage)
                elif self.play.passType is PassType.hailMary:
                    text = '{} {} {} for {} yards'.format(self.play.passer.name, choice(extraLongPassList), self.play.receiver.name, self.play.yardage)
                else:
                    text = '{} {} {} for {} yards'.format(self.play.passer.name, choice(midPassList), self.play.receiver.name, self.play.yardage)
            elif self.play.playResult is PlayResult.Interception:
                text = '{} pass intercepted by {}'.format(self.play.passer.name, self.play.defense.abbr)
            else:
                if self.play.passType is PassType.short:
                    if self.play.passIsDropped:
                        text = '{} short pass dropped by {}'.format(self.play.passer.name, self.play.receiver.name)
                    else:
                        text = '{} short pass to {} incomplete'.format(self.play.passer.name, self.play.receiver.name)
                elif self.play.passType is PassType.long or self.play.passType is PassType.hailMary:
                    if self.play.passIsDropped:
                        text = '{} deep pass dropped by {}'.format(self.play.passer.name, self.play.receiver.name)
                    else:
                        text = '{} deep pass to {} incomplete'.format(self.play.passer.name, self.play.receiver.name)
                elif self.play.passType is PassType.throwAway:
                    text = '{} throws the ball away, incomplete'.format(self.play.passer.name)
                else:
                    if self.play.passIsDropped:
                        text = '{} pass dropped by {}'.format(self.play.passer.name, self.play.receiver.name)
                    else:
                        text = '{} pass to {} incomplete'.format(self.play.passer.name, self.play.receiver.name)
        elif self.play.playType == PlayType.FieldGoal:
            text = '{}yd Field Goal attempt by {}'.format(self.play.fgDistance, self.play.kicker.name)
        elif self.play.playType is PlayType.Punt:
            text = '{} punts'.format(self.play.offense.rosterDict['k'].name, self.play.playResult.value)
        
        self.play.playText = text

    def postgame(self): 
        if self.isRegularSeasonGame:   
            self.homeTeam.seasonTeamStats['Offense']['pts'] += self.homeScore
            self.homeTeam.seasonTeamStats['Offense']['runTds'] += self.homeTeam.rosterDict['rb'].gameStatsDict['rushing']['tds']
            self.homeTeam.seasonTeamStats['Offense']['passTds'] += self.homeTeam.rosterDict['qb'].gameStatsDict['passing']['tds']
            self.homeTeam.seasonTeamStats['Offense']['tds'] += (self.homeTeam.rosterDict['qb'].gameStatsDict['passing']['tds'] + self.homeTeam.rosterDict['rb'].gameStatsDict['rushing']['tds'])
            self.homeTeam.seasonTeamStats['Offense']['fgs'] += self.homeTeam.rosterDict['k'].gameStatsDict['kicking']['fgs']
            self.homeTeam.seasonTeamStats['Offense']['passYards'] += self.homeTeam.rosterDict['qb'].gameStatsDict['passing']['yards']
            self.homeTeam.seasonTeamStats['Offense']['runYards'] += self.homeTeam.rosterDict['rb'].gameStatsDict['rushing']['yards']
            self.homeTeam.seasonTeamStats['Offense']['totalYards'] += (self.homeTeam.rosterDict['qb'].gameStatsDict['passing']['yards'] + self.homeTeam.rosterDict['rb'].gameStatsDict['rushing']['yards'])
            homeScoreDiff = self.homeScore - self.homeTeam.gameDefenseStats['ptsAlwd']
            self.homeTeam.seasonTeamStats['Offense']['pts'] += self.homeScore
            self.homeTeam.seasonTeamStats['scoreDiff'] += homeScoreDiff

            self.awayTeam.seasonTeamStats['Offense']['pts'] += self.awayScore
            self.awayTeam.seasonTeamStats['Offense']['runTds'] += self.awayTeam.rosterDict['rb'].gameStatsDict['rushing']['tds']
            self.awayTeam.seasonTeamStats['Offense']['passTds'] += self.awayTeam.rosterDict['qb'].gameStatsDict['passing']['tds']
            self.awayTeam.seasonTeamStats['Offense']['tds'] += (self.awayTeam.rosterDict['qb'].gameStatsDict['passing']['tds'] + self.awayTeam.rosterDict['rb'].gameStatsDict['rushing']['tds'])
            self.awayTeam.seasonTeamStats['Offense']['fgs'] += self.awayTeam.rosterDict['k'].gameStatsDict['kicking']['fgs']
            self.awayTeam.seasonTeamStats['Offense']['passYards'] += self.awayTeam.rosterDict['qb'].gameStatsDict['passing']['yards']
            self.awayTeam.seasonTeamStats['Offense']['runYards'] += self.awayTeam.rosterDict['rb'].gameStatsDict['rushing']['yards']
            self.awayTeam.seasonTeamStats['Offense']['totalYards'] += (self.awayTeam.rosterDict['qb'].gameStatsDict['passing']['yards'] + self.awayTeam.rosterDict['rb'].gameStatsDict['rushing']['yards'])
            awayScoreDiff = self.awayScore - self.awayTeam.gameDefenseStats['ptsAlwd']
            self.awayTeam.seasonTeamStats['Offense']['pts'] += self.awayScore
            self.awayTeam.seasonTeamStats['scoreDiff'] += awayScoreDiff

            if self.winningTeam.seasonTeamStats['streak'] >= 0:
                self.winningTeam.seasonTeamStats['streak'] += 1
                if self.winningTeam.seasonTeamStats['streak'] > 3 and not self.winningTeam.winningStreak:
                    self.winningTeam.winningStreak = True
                    self.leagueHighlights.insert(0, {'event':  {'text': '{} {} are on a hot streak!'.format(self.winningTeam.city, self.winningTeam.name)}})
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


            if self.losingTeam.seasonTeamStats['streak'] >= 0:
                self.losingTeam.seasonTeamStats['streak'] = -1
                if self.losingTeam.winningStreak:
                    self.losingTeam.winningStreak = False
                    self.leagueHighlights.insert(0, {'event':  {'text': '{} {} ended the {} {} hot streak!'.format(self.winningTeam.city, self.winningTeam.name, self.losingTeam.city, self.losingTeam.name)}})

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
        

        if self.homeTeam.gameDefenseStats['ptsAlwd'] >= 35:
            self.homeTeam.gameDefenseStats['fantasyPoints'] += -4
        elif self.homeTeam.gameDefenseStats['ptsAlwd'] >= 28 and self.homeTeam.gameDefenseStats['ptsAlwd'] < 35:
            self.homeTeam.gameDefenseStats['fantasyPoints'] += -1
        elif self.homeTeam.gameDefenseStats['ptsAlwd'] >= 14 and self.homeTeam.gameDefenseStats['ptsAlwd'] <= 21:
            self.homeTeam.gameDefenseStats['fantasyPoints'] += 1
        elif self.homeTeam.gameDefenseStats['ptsAlwd'] >= 7 and self.homeTeam.gameDefenseStats['ptsAlwd'] <= 13:
            self.homeTeam.gameDefenseStats['fantasyPoints'] += 4
        elif self.homeTeam.gameDefenseStats['ptsAlwd'] >= 1 and self.homeTeam.gameDefenseStats['ptsAlwd'] <= 6:
            self.homeTeam.gameDefenseStats['fantasyPoints'] += 7
        elif self.homeTeam.gameDefenseStats['ptsAlwd'] == 0:
            self.homeTeam.gameDefenseStats['fantasyPoints'] += 10

        if self.awayTeam.gameDefenseStats['ptsAlwd'] >= 35:
            self.awayTeam.gameDefenseStats['fantasyPoints'] += -4
        elif self.awayTeam.gameDefenseStats['ptsAlwd'] >= 28 and self.awayTeam.gameDefenseStats['ptsAlwd'] < 35:
            self.awayTeam.gameDefenseStats['fantasyPoints'] += -1
        elif self.awayTeam.gameDefenseStats['ptsAlwd'] >= 14 and self.awayTeam.gameDefenseStats['ptsAlwd'] <= 21:
            self.awayTeam.gameDefenseStats['fantasyPoints'] += 1
        elif self.awayTeam.gameDefenseStats['ptsAlwd'] >= 7 and self.awayTeam.gameDefenseStats['ptsAlwd'] <= 13:
            self.awayTeam.gameDefenseStats['fantasyPoints'] += 4
        elif self.awayTeam.gameDefenseStats['ptsAlwd'] >= 1 and self.awayTeam.gameDefenseStats['ptsAlwd'] <= 6:
            self.awayTeam.gameDefenseStats['fantasyPoints'] += 7
        elif self.awayTeam.gameDefenseStats['ptsAlwd'] == 0:
            self.awayTeam.gameDefenseStats['fantasyPoints'] += 10


        self.winningTeam.seasonTeamStats['Defense']['fantasyPoints'] += self.winningTeam.gameDefenseStats['fantasyPoints']
        self.losingTeam.seasonTeamStats['Defense']['fantasyPoints'] += self.losingTeam.gameDefenseStats['fantasyPoints']
        self.winningTeam.gameDefenseStats = copy.deepcopy(FloosTeam.teamStatsDict['Defense'])
        self.losingTeam.gameDefenseStats = copy.deepcopy(FloosTeam.teamStatsDict['Defense'])

        for player in self.homeTeam.rosterDict.values():
            player.postgameChanges()

            player.seasonStatsDict['fantasyPoints'] += player.gameStatsDict['fantasyPoints']

            if player.gameStatsDict['passing']['att'] > 0:
                if player.gameStatsDict['passing']['comp'] > 0:
                    player.gameStatsDict['passing']['ypc'] = round(player.gameStatsDict['passing']['yards']/player.gameStatsDict['passing']['comp'], 2)
                    player.gameStatsDict['passing']['compPerc'] = round((player.gameStatsDict['passing']['comp']/player.gameStatsDict['passing']['att'])*100)

                if self.isRegularSeasonGame: 
                    #player.seasonStatsDict['passing']['att'] += player.gameStatsDict['passing']['att']
                    #player.seasonStatsDict['passing']['comp'] += player.gameStatsDict['passing']['comp']
                    #player.seasonStatsDict['passing']['tds'] += player.gameStatsDict['passing']['tds']
                    #player.seasonStatsDict['passing']['ints'] += player.gameStatsDict['passing']['ints']
                    #player.seasonStatsDict['passing']['yards'] += player.gameStatsDict['passing']['yards']
                    #player.seasonStatsDict['passing']['missedPass'] += player.gameStatsDict['passing']['missedPass']
                    player.seasonStatsDict['passing']['20+'] += player.gameStatsDict['passing']['20+']

                    if player.gameStatsDict['passing']['longest'] > player.seasonStatsDict['passing']['longest']:
                        player.seasonStatsDict['passing']['longest'] = player.gameStatsDict['passing']['longest']

                    if player.seasonStatsDict['passing']['comp'] > 0:
                        player.seasonStatsDict['passing']['ypc'] = round(player.seasonStatsDict['passing']['yards']/player.seasonStatsDict['passing']['comp'], 2)
                        player.seasonStatsDict['passing']['compPerc'] = round((player.seasonStatsDict['passing']['comp']/player.seasonStatsDict['passing']['att'])*100)

            if player.gameStatsDict['receiving']['receptions'] > 0:
                if player.gameStatsDict['receiving']['yards'] > 0:
                    player.gameStatsDict['receiving']['ypr'] = round(player.gameStatsDict['receiving']['yards']/player.gameStatsDict['receiving']['receptions'],2)
                    player.gameStatsDict['receiving']['rcvPerc'] = round((player.gameStatsDict['receiving']['receptions']/player.gameStatsDict['receiving']['targets'])*100)

                if self.isRegularSeasonGame:
                    #player.seasonStatsDict['receiving']['targets'] += player.gameStatsDict['receiving']['targets']
                    #player.seasonStatsDict['receiving']['receptions'] += player.gameStatsDict['receiving']['receptions']
                    #player.seasonStatsDict['receiving']['yac'] += player.gameStatsDict['receiving']['yac']
                    #player.seasonStatsDict['receiving']['yards'] += player.gameStatsDict['receiving']['yards']
                    #player.seasonStatsDict['receiving']['tds'] += player.gameStatsDict['receiving']['tds']
                    #player.seasonStatsDict['receiving']['drops'] += player.gameStatsDict['receiving']['drops']
                    player.seasonStatsDict['receiving']['20+'] += player.gameStatsDict['receiving']['20+']

                    if player.gameStatsDict['receiving']['longest'] > player.seasonStatsDict['receiving']['longest']:
                        player.seasonStatsDict['receiving']['longest'] = player.gameStatsDict['receiving']['longest']

                    if player.seasonStatsDict['receiving']['yards'] > 0:
                        player.seasonStatsDict['receiving']['ypr'] = round(player.seasonStatsDict['receiving']['yards']/player.seasonStatsDict['receiving']['receptions'],2)
                        player.seasonStatsDict['receiving']['rcvPerc'] = round((player.seasonStatsDict['receiving']['receptions']/player.seasonStatsDict['receiving']['targets'])*100)

            if player.gameStatsDict['rushing']['carries'] > 0:

                player.gameStatsDict['rushing']['ypc'] = round(player.gameStatsDict['rushing']['yards']/player.gameStatsDict['rushing']['carries'],2)

                if self.isRegularSeasonGame:
                    #player.seasonStatsDict['rushing']['carries'] += player.gameStatsDict['rushing']['carries']
                    #player.seasonStatsDict['rushing']['yards'] += player.gameStatsDict['rushing']['yards']
                    #player.seasonStatsDict['rushing']['tds'] += player.gameStatsDict['rushing']['tds']
                    #player.seasonStatsDict['rushing']['fumblesLost'] += player.gameStatsDict['rushing']['fumblesLost']
                    player.seasonStatsDict['rushing']['20+'] += player.gameStatsDict['rushing']['20+']

                    if player.gameStatsDict['rushing']['longest'] > player.seasonStatsDict['rushing']['longest']:
                        player.seasonStatsDict['rushing']['longest'] = player.gameStatsDict['rushing']['longest']

                    if player.seasonStatsDict['rushing']['carries'] > 0:
                        player.seasonStatsDict['rushing']['ypc'] = round(player.seasonStatsDict['rushing']['yards']/player.seasonStatsDict['rushing']['carries'],2)

            if player.gameStatsDict['kicking']['fgAtt'] > 0:
                if player.gameStatsDict['kicking']['fgs'] > 0:
                    player.gameStatsDict['kicking']['fgPerc'] = round((player.gameStatsDict['kicking']['fgs']/player.gameStatsDict['kicking']['fgAtt'])*100)
                else:
                    player.gameStatsDict['kicking']['fgPerc'] = 0

                if self.isRegularSeasonGame:
                    #player.seasonStatsDict['kicking']['fgAtt'] += player.gameStatsDict['kicking']['fgAtt']
                    #player.seasonStatsDict['kicking']['fg45+'] += player.gameStatsDict['kicking']['fg45+']
                    #player.seasonStatsDict['kicking']['fgs'] += player.gameStatsDict['kicking']['fgs']
                    #player.seasonStatsDict['kicking']['fgYards'] += player.gameStatsDict['kicking']['fgYards']

                    if player.gameStatsDict['kicking']['longest'] > player.seasonStatsDict['kicking']['longest']:
                        player.seasonStatsDict['kicking']['longest'] = player.gameStatsDict['kicking']['longest']

                    if player.seasonStatsDict['kicking']['fgs'] > 0:
                        player.seasonStatsDict['kicking']['fgPerc'] = round((player.seasonStatsDict['kicking']['fgs']/player.seasonStatsDict['kicking']['fgAtt'])*100)
                        player.seasonStatsDict['kicking']['fgAvg'] = round(player.seasonStatsDict['kicking']['fgYards']/player.seasonStatsDict['kicking']['fgs'])

                        if player.seasonStatsDict['kicking']['fgUnder20att'] > 0:
                            player.seasonStatsDict['kicking']['fgUnder20perc'] = round((player.seasonStatsDict['kicking']['fgUnder20']/player.seasonStatsDict['kicking']['fgUnder20att'])*100)
                        else:
                            player.seasonStatsDict['kicking']['fgUnder20perc'] = 'N/A'

                        if player.seasonStatsDict['kicking']['fg20to40att'] > 0:
                            player.seasonStatsDict['kicking']['fg20to40perc'] = round((player.seasonStatsDict['kicking']['fg20to40']/player.seasonStatsDict['kicking']['fg20to40att'])*100)
                        else:
                            player.seasonStatsDict['kicking']['fg20to40perc'] = 'N/A'

                        if player.seasonStatsDict['kicking']['fg40to50att'] > 0:
                            player.seasonStatsDict['kicking']['fg40to50perc'] = round((player.seasonStatsDict['kicking']['fg40to50']/player.seasonStatsDict['kicking']['fg40to50att'])*100)
                        else:
                            player.seasonStatsDict['kicking']['fg40to50perc'] = 'N/A'

                        if player.seasonStatsDict['kicking']['fgOver50att'] > 0:
                            player.seasonStatsDict['kicking']['fgOver50perc'] = round((player.seasonStatsDict['kicking']['fgOver50']/player.seasonStatsDict['kicking']['fgOver50att'])*100)
                        else:
                            player.seasonStatsDict['kicking']['fgOver50perc'] = 'N/A'

                    else:
                        player.seasonStatsDict['kicking']['fgPerc'] = 0


        for player in self.awayTeam.rosterDict.values():
            player.postgameChanges()
            player.seasonStatsDict['fantasyPoints'] += player.gameStatsDict['fantasyPoints']

            if player.gameStatsDict['passing']['att'] > 0:

                if player.gameStatsDict['passing']['comp'] > 0:
                    player.gameStatsDict['passing']['ypc'] = round(player.gameStatsDict['passing']['yards']/player.gameStatsDict['passing']['comp'], 2)
                    player.gameStatsDict['passing']['compPerc'] = round((player.gameStatsDict['passing']['comp']/player.gameStatsDict['passing']['att'])*100)

                if self.isRegularSeasonGame: 
                    #player.seasonStatsDict['passing']['att'] += player.gameStatsDict['passing']['att']
                    #player.seasonStatsDict['passing']['comp'] += player.gameStatsDict['passing']['comp']
                    #player.seasonStatsDict['passing']['tds'] += player.gameStatsDict['passing']['tds']
                    #player.seasonStatsDict['passing']['ints'] += player.gameStatsDict['passing']['ints']
                    #player.seasonStatsDict['passing']['yards'] += player.gameStatsDict['passing']['yards']
                    #player.seasonStatsDict['passing']['missedPass'] += player.gameStatsDict['passing']['missedPass']
                    player.seasonStatsDict['passing']['20+'] += player.gameStatsDict['passing']['20+']

                    if player.gameStatsDict['passing']['longest'] > player.seasonStatsDict['passing']['longest']:
                        player.seasonStatsDict['passing']['longest'] = player.gameStatsDict['passing']['longest']

                    if player.seasonStatsDict['passing']['comp'] > 0:
                        player.seasonStatsDict['passing']['ypc'] = round(player.seasonStatsDict['passing']['yards']/player.seasonStatsDict['passing']['comp'], 2)
                        player.seasonStatsDict['passing']['compPerc'] = round((player.seasonStatsDict['passing']['comp']/player.seasonStatsDict['passing']['att'])*100)

            if player.gameStatsDict['receiving']['receptions'] > 0:
                if player.gameStatsDict['receiving']['yards'] > 0:
                    player.gameStatsDict['receiving']['ypr'] = round(player.gameStatsDict['receiving']['yards']/player.gameStatsDict['receiving']['receptions'],2)
                    player.gameStatsDict['receiving']['rcvPerc'] = round((player.gameStatsDict['receiving']['receptions']/player.gameStatsDict['receiving']['targets'])*100)

                if self.isRegularSeasonGame:
                    #player.seasonStatsDict['receiving']['targets'] += player.gameStatsDict['receiving']['targets']
                    #player.seasonStatsDict['receiving']['receptions'] += player.gameStatsDict['receiving']['receptions']
                    #player.seasonStatsDict['receiving']['yac'] += player.gameStatsDict['receiving']['yac']
                    #player.seasonStatsDict['receiving']['yards'] += player.gameStatsDict['receiving']['yards']
                    #player.seasonStatsDict['receiving']['tds'] += player.gameStatsDict['receiving']['tds']
                    #player.seasonStatsDict['receiving']['drops'] += player.gameStatsDict['receiving']['drops']
                    player.seasonStatsDict['receiving']['20+'] += player.gameStatsDict['receiving']['20+']

                    if player.gameStatsDict['receiving']['longest'] > player.seasonStatsDict['receiving']['longest']:
                        player.seasonStatsDict['receiving']['longest'] = player.gameStatsDict['receiving']['longest']

                    if player.seasonStatsDict['receiving']['yards'] > 0:
                        player.seasonStatsDict['receiving']['ypr'] = round(player.seasonStatsDict['receiving']['yards']/player.seasonStatsDict['receiving']['receptions'],2)
                        player.seasonStatsDict['receiving']['rcvPerc'] = round((player.seasonStatsDict['receiving']['receptions']/player.seasonStatsDict['receiving']['targets'])*100)

            if player.gameStatsDict['rushing']['carries'] > 0:

                player.gameStatsDict['rushing']['ypc'] = round(player.gameStatsDict['rushing']['yards']/player.gameStatsDict['rushing']['carries'],2)

                if self.isRegularSeasonGame:
                    #player.seasonStatsDict['rushing']['carries'] += player.gameStatsDict['rushing']['carries']
                    #player.seasonStatsDict['rushing']['yards'] += player.gameStatsDict['rushing']['yards']
                    #player.seasonStatsDict['rushing']['tds'] += player.gameStatsDict['rushing']['tds']
                    #player.seasonStatsDict['rushing']['fumblesLost'] += player.gameStatsDict['rushing']['fumblesLost']
                    player.seasonStatsDict['rushing']['20+'] += player.gameStatsDict['rushing']['20+']

                    if player.gameStatsDict['rushing']['longest'] > player.seasonStatsDict['rushing']['longest']:
                        player.seasonStatsDict['rushing']['longest'] = player.gameStatsDict['rushing']['longest']

                    if player.seasonStatsDict['rushing']['carries'] > 0:
                        player.seasonStatsDict['rushing']['ypc'] = round(player.seasonStatsDict['rushing']['yards']/player.seasonStatsDict['rushing']['carries'],2)

            if player.gameStatsDict['kicking']['fgAtt'] > 0:
                if player.gameStatsDict['kicking']['fgs'] > 0:
                    player.gameStatsDict['kicking']['fgPerc'] = round((player.gameStatsDict['kicking']['fgs']/player.gameStatsDict['kicking']['fgAtt'])*100)
                else:
                    player.gameStatsDict['kicking']['fgPerc'] = 0

                if self.isRegularSeasonGame:
                    #player.seasonStatsDict['kicking']['fgAtt'] += player.gameStatsDict['kicking']['fgAtt']
                    #player.seasonStatsDict['kicking']['fg45+'] += player.gameStatsDict['kicking']['fg45+']
                    #player.seasonStatsDict['kicking']['fgs'] += player.gameStatsDict['kicking']['fgs']
                    #player.seasonStatsDict['kicking']['fgYards'] += player.gameStatsDict['kicking']['fgYards']

                    if player.gameStatsDict['kicking']['longest'] > player.seasonStatsDict['kicking']['longest']:
                        player.seasonStatsDict['kicking']['longest'] = player.gameStatsDict['kicking']['longest']

                    if player.seasonStatsDict['kicking']['fgs'] > 0:
                        player.seasonStatsDict['kicking']['fgPerc'] = round((player.seasonStatsDict['kicking']['fgs']/player.seasonStatsDict['kicking']['fgAtt'])*100)
                        player.seasonStatsDict['kicking']['fgAvg'] = round(player.seasonStatsDict['kicking']['fgYards']/player.seasonStatsDict['kicking']['fgs'])

                        if player.seasonStatsDict['kicking']['fgUnder20att'] > 0:
                            player.seasonStatsDict['kicking']['fgUnder20perc'] = round((player.seasonStatsDict['kicking']['fgUnder20']/player.seasonStatsDict['kicking']['fgUnder20att'])*100)
                        else:
                            player.seasonStatsDict['kicking']['fgUnder20perc'] = 'N/A'

                        if player.seasonStatsDict['kicking']['fg20to40att'] > 0:
                            player.seasonStatsDict['kicking']['fg20to40perc'] = round((player.seasonStatsDict['kicking']['fg20to40']/player.seasonStatsDict['kicking']['fg20to40att'])*100)
                        else:
                            player.seasonStatsDict['kicking']['fg20to40perc'] = 'N/A'

                        if player.seasonStatsDict['kicking']['fg40to50att'] > 0:
                            player.seasonStatsDict['kicking']['fg40to50perc'] = round((player.seasonStatsDict['kicking']['fg40to50']/player.seasonStatsDict['kicking']['fg40to50att'])*100)
                        else:
                            player.seasonStatsDict['kicking']['fg40to50perc'] = 'N/A'

                        if player.seasonStatsDict['kicking']['fgOver50att'] > 0:
                            player.seasonStatsDict['kicking']['fgOver50perc'] = round((player.seasonStatsDict['kicking']['fgOver50']/player.seasonStatsDict['kicking']['fgOver50att'])*100)
                        else:
                            player.seasonStatsDict['kicking']['fgOver50perc'] = 'N/A'

                    else:
                        player.seasonStatsDict['kicking']['fgPerc'] = 0
                    
            


    def calculateWinProbability(self):
        self.homeTeamElo = self.homeTeam.elo
        self.awayTeamElo = self.awayTeam.elo
        self.homeTeamWinProbability = FloosMethods.calculateProbability(self.awayTeam.elo, self.homeTeamElo)
        self.awayTeamWinProbability = FloosMethods.calculateProbability(self.homeTeam.elo, self.awayTeamElo)

    def calculateEloChange(self):
        k = 35

        if self.winningTeam is self.homeTeam:
            marginOfVictoryMultiplier = math.log((abs(self.homeScore - self.awayScore) + 1)) * (2.2/((self.homeTeamElo-self.awayTeamElo) * .001 + 2.2))
            self.homeTeam.elo = round((self.homeTeamElo + (k * marginOfVictoryMultiplier) * (1 - self.homeTeamWinProbability)))
            self.awayTeam.elo = round((self.awayTeamElo + (k * marginOfVictoryMultiplier) * (0 - self.awayTeamWinProbability)))
            x = 0
        else:
            marginOfVictoryMultiplier = math.log((abs(self.awayScore - self.homeScore) + 1)) * (2.2/((self.awayTeamElo-self.homeTeamElo) * .001 + 2.2))
            self.homeTeam.elo = round((self.homeTeamElo + (k * marginOfVictoryMultiplier) * (0 - self.homeTeamWinProbability)))
            self.awayTeam.elo = round((self.awayTeamElo + (k * marginOfVictoryMultiplier) * (1 - self.awayTeamWinProbability)))
            x = 0
        

    async def playGame(self):
        self.totalPlays = 0
        possReset = 80
        coinFlipWinner = None
        coinFlipLoser = None
        otContinue = False

        for player in self.homeTeam.rosterDict.values():
            player: FloosPlayer.Player
            player.gameAttributes = copy.deepcopy(player.attributes)
            player.gameStatsDict = copy.deepcopy(FloosPlayer.playerStatsDict)
        for player in self.awayTeam.rosterDict.values():
            player: FloosPlayer.Player
            player.gameAttributes = copy.deepcopy(player.attributes)
            player.gameStatsDict = copy.deepcopy(FloosPlayer.playerStatsDict)

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
        # self.leagueHighlights.insert(0, {'event':  {
        #                                         'text': 'Game Start: {} vs. {}'.format(self.awayTeam.name, self.homeTeam.name)
        #                                     }
        #                                 })
        self.gameFeed.insert(0, {'event':  {
                                                'text': '{} wins the coin toss'.format(coinFlipWinner.name),
                                                'quarter': 1,
                                                'playsRemaining': 132 - self.totalPlays
                                            }
                                        })
        
        while self.totalPlays < 132 or self.homeScore == self.awayScore or otContinue:

            if self.totalPlays < 1:
                self.yardsToFirstDown = 10
                self.yardsToEndzone = 80
                self.yardsToSafety = 20

            self.down = 1

            while self.down <= 4:

                if self.totalPlays > 0:
                    self.formatPlayText()
                    if self.play.isSack:
                        self.defensiveTeam.gameDefenseStats['fantasyPoints'] += 1
                    if self.play.isFumbleLost or self.play.isInterception or self.play.scoreChange or self.play.yardage >= 30:
                        self.highlights.insert(0, {'play': self.play})
                        self.leagueHighlights.insert(0, {'play': self.play})
                    self.gameFeed.insert(0, {'play': self.play})

                if self.totalPlays == 132 and self.homeScore != self.awayScore:
                    break

                if self.totalPlays < 33:
                    if self.currentQuarter != 1:
                        self.currentQuarter = 1
                        self.gameFeed.insert(0, {'event':  {
                                                'text': 'Start 1st Quarter',
                                                'quarter': self.currentQuarter,
                                                'playsRemaining': 132 - self.totalPlays
                                            }
                                        })
                        # x = randint(1,100)
                        # y = randint(1,100)
                        # if x >= 95:
                        #     self.homeTeam.teamOverPerform()
                        # elif x <= 5:
                        #     self.homeTeam.teamUnderPerform()
                        # if y >= 95:
                        #     self.awayTeam.teamOverPerform()
                        # elif y <= 5:
                        #     self.awayTeam.teamUnderPerform()
                elif self.totalPlays >= 33 and self.totalPlays < 66:
                    if self.currentQuarter != 2:
                        #await asyncio.sleep(15)
                        self.currentQuarter = 2
                        self.gameFeed.insert(0, {'event':  {
                                                'text': 'Start 2nd Quarter',
                                                'quarter': self.currentQuarter,
                                                'playsRemaining': 132 - self.totalPlays
                                            }
                                        })
                elif self.totalPlays >= 66 and self.totalPlays < 100:
                    if self.totalPlays == 66:
                        self.isHalftime = True
                        self.gameFeed.insert(0, {'event':  {
                                                'text': 'Halftime',
                                                'quarter': self.currentQuarter,
                                                'playsRemaining': 132 - self.totalPlays
                                            }
                                        })
                        #await asyncio.sleep(60)
                        self.isHalftime = False
                    if self.currentQuarter != 3:
                        self.currentQuarter = 3
                        self.gameFeed.insert(0, {'event':  {
                                                'text': 'Start 3rd Quarter',
                                                'quarter': self.currentQuarter,
                                                'playsRemaining': 132 - self.totalPlays
                                            }
                                        })
                        self.turnover(coinFlipWinner, coinFlipLoser, possReset)
                        self.down = 1
                        #x = randint(1,100)
                        #y = randint(1,100)
                        # if x >= 95:
                        #     self.homeTeam.teamOverPerform()
                        # elif x <= 5:
                        #     self.homeTeam.teamUnderPerform()
                        # elif x > 80 and x <= 90:
                        #     self.homeTeam.resetDetermination()
                        # if y >= 95:
                        #     self.awayTeam.teamOverPerform()
                        # elif y <= 5:
                        #     self.awayTeam.teamUnderPerform()
                        # elif y > 80 and y <= 90:
                        #     self.awayTeam.resetDetermination()
                elif self.totalPlays >= 100 and self.totalPlays < 132:
                    if self.currentQuarter != 4:
                        #await asyncio.sleep(15)
                        self.currentQuarter = 4
                        self.gameFeed.insert(0, {'event':  {
                                                'text': 'Start 4th Quarter',
                                                'quarter': self.currentQuarter,
                                                'playsRemaining': 132 - self.totalPlays
                                            }
                                        })
                    # if self.homeScore > self.awayScore and (self.homeScore - self.awayScore) <= 14:
                    #     x = randint(1,10)
                    #     if x > 6:
                    #         self.awayTeam.resetDetermination()
                    #         #self.awayTeam.inGamePush()
                    # elif self.awayScore > self.homeScore and (self.awayScore - self.homeScore) <= 14:
                    #     x = randint(1,10)
                    #     if x > 6:
                    #         self.homeTeam.resetDetermination()
                    #         #self.homeTeam.inGamePush()
                elif self.totalPlays >= 132:
                    if self.homeScore != self.awayScore:
                        if self.otHomeHadPos and self.otAwayHadPos:
                            otContinue = False
                            break
                    if self.currentQuarter != 5:
                        #await asyncio.sleep(15)
                        self.currentQuarter = 5
                        self.gameFeed.insert(0, {'event':  {
                                                'text': 'Start Overtime',
                                                'quarter': 'OT',
                                                'playsRemaining': 132 - self.totalPlays
                                            }
                                        })
                        self.isOvertime = True
                        otContinue = True
                        x = randint(0,1)
                        if x == 0:
                            self.turnover(self.homeTeam, self.awayTeam, possReset)
                        else:
                            self.turnover(self.awayTeam, self.homeTeam, possReset)
                        
                        self.gameFeed.insert(0, {'event':  {
                                                'text': '{} wins the OT coin toss'.format(self.offensiveTeam.name),
                                                'quarter': '0T',
                                                'playsRemaining': 132 - self.totalPlays
                                            }
                                        })
                        self.down = 1
                

                if self.yardsToEndzone > 50:
                    self.yardLine = '{0} {1}'.format(self.offensiveTeam.abbr, (100-self.yardsToEndzone))
                else:
                    self.yardLine = '{0} {1}'.format(self.defensiveTeam.abbr, self.yardsToEndzone)

                self.play = Play(self)
                
                #await asyncio.sleep(randint(8,20))

                self.playCaller()
                self.totalPlays += 1
                if self.offensiveTeam is self.homeTeam:
                    self.homePlaysTotal += 1
                if self.offensiveTeam is self.awayTeam:
                    self.awayPlaysTotal += 1
                #self.defensiveTeam.updateGameEnergy(-.75)


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
                        self.play.scoreChange = True
                        self.play.homeTeamScore = self.homeScore
                        self.play.awayTeamScore = self.awayScore
                        self.turnover(self.offensiveTeam, self.defensiveTeam, possReset)
                        break
                    else:
                        self.play.playResult = PlayResult.FieldGoalNoGood
                        self.turnover(self.offensiveTeam, self.defensiveTeam, self.yardsToSafety)
                        break
                if self.play.playType is PlayType.Punt:
                    self.play.playResult = PlayResult.Punt
                    maxPuntYards = round(70*(self.offensiveTeam.rosterDict['k'].attributes.legStrength/100))
                    if maxPuntYards > self.yardsToEndzone:
                        maxPuntYards = self.yardsToEndzone + 10
                    puntDistance = randint((maxPuntYards-20), maxPuntYards)
                    if puntDistance >= self.yardsToEndzone:
                        puntDistance = self.yardsToEndzone - 20
                    newYards = 100 - (self.yardsToEndzone - puntDistance)
                    self.turnover(self.offensiveTeam, self.defensiveTeam, newYards)
                    break
                elif self.play.isFumbleLost or self.play.isInterception:
                    self.defensiveTeam.gameDefenseStats['fantasyPoints'] += 2
                    if self.offensiveTeam is self.homeTeam:
                        self.homeTurnoversTotal += 1
                    elif self.offensiveTeam is self.awayTeam:
                        self.awayTurnoversTotal += 1
                    if self.play.yardage >= self.yardsToEndzone:
                        self.turnover(self.offensiveTeam, self.defensiveTeam, possReset)
                    elif (self.yardsToSafety + self.play.yardage) <= 0:
                        if self.defensiveTeam == self.homeTeam:
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

                        elif self.defensiveTeam == self.awayTeam:
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
    
                        self.play.extraPointTry(self.defensiveTeam)
                        if self.play.isXpGood:
                            self.play.playResult = PlayResult.TouchdownXP
                            if self.defensiveTeam == self.homeTeam:
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
                            elif self.defensiveTeam == self.awayTeam:
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
                        else:
                            self.play.playResult = PlayResult.TouchdownNoXP
                        self.defensiveTeam.gameDefenseStats['fantasyPoints'] += 3
                        self.play.isTd = True
                        self.play.scoreChange = True
                        self.play.homeTeamScore = self.homeScore
                        self.play.awayTeamScore = self.awayScore
                        self.turnover(self.defensiveTeam, self.offensiveTeam, possReset)
                        break
                    else:
                        self.turnover(self.offensiveTeam, self.defensiveTeam, (self.yardsToSafety + self.play.yardage))
                    break
                else:
                    if self.play.yardage >= self.yardsToEndzone:
                        self.play.isTd = True
                        if self.play.playType is PlayType.Run:
                            self.play.runner.addRushTd(self.play.yardage, self.isRegularSeasonGame)
                            self.play.runner.updateInGameConfidence(.01)
                            self.play.defense.gameDefenseStats['runTdsAlwd'] += 1
                            self.play.defense.gameDefenseStats['tdsAlwd'] += 1
                        elif self.play.playType is PlayType.Pass:
                            self.play.passer.addPassTd(self.play.yardage, self.isRegularSeasonGame)
                            self.play.receiver.addReceiveTd(self.play.yardage, self.isRegularSeasonGame)
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

                        self.play.extraPointTry(self.offensiveTeam)
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
                        
                        self.play.scoreChange = True
                        self.play.homeTeamScore = self.homeScore
                        self.play.awayTeamScore = self.awayScore
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
                        if self.play.isFumbleLost:
                            if self.defensiveTeam == self.homeTeam:
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
    
                            elif self.defensiveTeam == self.awayTeam:
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
    
                            self.play.extraPointTry(self.defensiveTeam)
                            if self.play.isXpGood:
                                self.play.playResult = PlayResult.TouchdownXP
                                if self.defensiveTeam == self.homeTeam:
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
                                elif self.defensiveTeam == self.awayTeam:
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

                            else:
                                self.play.playResult = PlayResult.TouchdownNoXP

                            self.play.isTd = True
                            self.play.scoreChange = True
                            self.play.homeTeamScore = self.homeScore
                            self.play.awayTeamScore = self.awayScore
                            self.turnover(self.defensiveTeam, self.offensiveTeam, possReset)
                            break
                        else:
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
                            self.defensiveTeam.gameDefenseStats['fantasyPoints'] += 2
                            self.play.isSafety = True
                            self.play.scoreChange = True
                            self.play.homeTeamScore = self.homeScore
                            self.play.awayTeamScore = self.awayScore
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
            if self.play.scoreChange and not self.isOvertime:
                self.formatPlayText()
                if self.play.isFumbleLost or self.play.isInterception or self.play.scoreChange or self.play.yardage >= 30:
                    self.highlights.insert(0, {'play': self.play})
                    self.leagueHighlights.insert(0, {'play': self.play})
                self.gameFeed.insert(0, {'play': self.play})

        if self.awayScore > self.homeScore:
            self.winningTeam = self.awayTeam
            self.losingTeam = self.homeTeam
            self.gameDict['score'] = '{0} - {1}'.format(self.awayScore, self.homeScore)
            self.gameFeed.insert(0, {'event':  {
                                                'text': 'Final: {} - {} | {} - {}'.format(self.awayTeam.abbr, self.awayScore, self.homeTeam.abbr, self.homeScore),
                                                'quarter': 'Final',
                                                'playsRemaining': 132 - self.totalPlays
                                            }
                                        })
            self.leagueHighlights.insert(0, {'event':  {
                                                'text': 'Game Final: {} - {} | {} - {}'.format(self.awayTeam.name, self.awayScore, self.homeTeam.name, self.homeScore)
                                            }
                                        })

        elif self.homeScore > self.awayScore:
            self.winningTeam = self.homeTeam
            self.losingTeam = self.awayTeam
            self.gameDict['score'] = '{0} - {1}'.format(self.homeScore, self.awayScore)
            self.gameFeed.insert(0, {'event':  {
                                                'text': 'Final: {} - {} | {} - {}'.format(self.homeTeam.abbr, self.homeScore, self.awayTeam.abbr, self.awayScore),
                                                'quarter': 'Final',
                                                'playsRemaining': 132 - self.totalPlays
                                            }
                                        })
            self.leagueHighlights.insert(0, {'event':  {
                                                'text': 'Game Final: {} - {} | {} - {}'.format(self.homeTeam.name, self.homeScore, self.awayTeam.name, self.awayScore)
                                            }
                                        })

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
        self.calculateEloChange()
        self.postgame()



class Play():
    def __init__(self, game:Game):
        self.game = game
        self.gameId = game.id
        self.offense = game.offensiveTeam
        self.defense = game.defensiveTeam
        self.homeTeamScore = game.homeScore
        self.awayTeamScore = game.awayScore
        self.homeAbbr = game.homeTeam.abbr
        self.awayAbbr = game.awayTeam.abbr
        self.quarter = game.currentQuarter
        self.down = game.down
        self.playsLeft = 132 - game.totalPlays
        self.yardLine = game.yardLine
        self.yardsToEndzone = game.yardsToEndzone
        self.yardsToSafety = game.yardsToSafety
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
        self.passIsDropped = False
        self.playText = ''

    def fieldGoalTry(self):
        self.kicker = self.offense.rosterDict['k']
        self.kicker.addFgAttempt(self.game.isRegularSeasonGame)
        yardsToFG = self.yardsToEndzone + 17
        self.fgDistance = yardsToFG
        x = randint(1,100)
        if yardsToFG <= 20:
            if (self.kicker.gameAttributes.overallRating + 15) >= x:
                self.isFgGood = True
                self.kicker.addFg(self.fgDistance, self.game.isRegularSeasonGame)
                self.kicker.updateInGameConfidence(.005)
            else:
                self.kicker.updateInGameConfidence(-.02)
        elif yardsToFG > 20 and yardsToFG <= 30:
            if (self.kicker.gameAttributes.overallRating + 10) >= x:
                self.isFgGood = True
                self.kicker.addFg(self.fgDistance, self.game.isRegularSeasonGame)
                self.kicker.updateInGameConfidence(.01)
            else:
                self.kicker.updateInGameConfidence(-.015)
        elif yardsToFG > 30 and yardsToFG <= 40:
            if (self.kicker.gameAttributes.overallRating + 7) >= x:
                self.isFgGood = True
                self.kicker.addFg(self.fgDistance, self.game.isRegularSeasonGame)
                self.kicker.updateInGameConfidence(.01)
            else:
                self.kicker.updateInGameConfidence(-.015)
        elif yardsToFG > 40 and yardsToFG <= 45:
            if (self.kicker.gameAttributes.overallRating) >= x:
                self.isFgGood = True
                self.kicker.addFg(self.fgDistance, self.game.isRegularSeasonGame)
                self.kicker.updateInGameConfidence(.015)
            else:
                self.kicker.updateInGameConfidence(-.01)
        elif yardsToFG > 45 and yardsToFG <= 50:
            if (self.kicker.gameAttributes.overallRating - 10) >= x:
                self.isFgGood = True
                self.kicker.addFg(self.fgDistance, self.game.isRegularSeasonGame)
                self.kicker.updateInGameConfidence(.015)
            else:
                self.kicker.updateInGameConfidence(-.01)
        elif yardsToFG > 50 and yardsToFG <= 55:
            if (self.kicker.gameAttributes.overallRating - 20) >= x:
                self.isFgGood = True
                self.kicker.addFg(self.fgDistance, self.game.isRegularSeasonGame)
                self.kicker.updateInGameConfidence(.015)
            else:
                self.kicker.updateInGameConfidence(-.01)
        elif yardsToFG > 55 and yardsToFG <= 60:
            if (self.kicker.gameAttributes.overallRating - 35) >= x:
                self.isFgGood = True
                self.kicker.addFg(self.fgDistance, self.game.isRegularSeasonGame)
                self.kicker.updateInGameConfidence(.02)
            else:
                self.kicker.updateInGameConfidence(-.005)
        else:
            if (self.kicker.gameAttributes.overallRating - 50) >= x:
                self.isFgGood = True
                self.kicker.addFg(self.fgDistance, self.game.isRegularSeasonGame)
                self.kicker.updateInGameConfidence(.025)
            else:
                self.kicker.updateInGameConfidence(-.005)
        if self.isFgGood:
            if yardsToFG > self.kicker.gameStatsDict['kicking']['longest']:
                self.kicker.gameStatsDict['kicking']['longest'] = yardsToFG
        else:
            self.kicker.addMissedFg(self.fgDistance, self.game.isRegularSeasonGame)
        self.kicker.updateInGameRating()

    def extraPointTry(self, offense: FloosTeam.Team):
        self.kicker = offense.rosterDict['k']
        x = randint(1,100)
        if (self.kicker.gameAttributes.overallRating + 15) >= x:
            self.isXpGood = True
            self.kicker.addExtraPoint()
        else:
            self.kicker.addMissedExtraPoint()

        self.kicker.updateInGameRating()
    
    def runPlay(self):
        self.playType = PlayType.Run
        self.runner = self.offense.rosterDict['rb']
        blocker: FloosPlayer.PlayerTE = self.offense.rosterDict['te']
        x = randint(1,100)
        fumbleRoll = randint(1,100)
        fumbleResist = round(((self.runner.gameAttributes.power*.8) + (self.runner.gameAttributes.discipline*1.2)/2) + self.runner.gameAttributes.luckModifier)
        fumbleResistModifyer = 0
        if fumbleResist >= 92:
            fumbleResistModifyer = -2
        elif fumbleResist >= 84 and fumbleResist <= 91:
            fumbleResistModifyer = -1
        elif fumbleResist >= 68 and fumbleResist <= 75:
            fumbleResistModifyer = 1
        elif fumbleResist >= 60 and fumbleResist <= 67:
            fumbleResistModifyer = 2

        playStrength = (((self.runner.gameAttributes.overallRating*1.2) + (blocker.gameAttributes.blocking*.8))/2) + randint(-10,10)
        defenseStrength = self.defense.defenseRunCoverageRating + randint(-10,10)

        if defenseStrength >= playStrength:
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
                fumbleRoll = 0
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
                    self.yardage = self.yardsToEndzone
                else:
                    self.yardage = randint(20, self.yardsToEndzone)
                self.runner.updateInGameConfidence(.01)
                fumbleRoll = 0

        
        if (fumbleRoll+fumbleResistModifyer) > 97:
            #fumble
            self.isFumble = True
            if (self.defense.defenseRunCoverageRating + randint(-5,5)) >= (self.runner.gameAttributes.overallRating + randint(-5,5)):
                self.runner.addFumble(self.game.isRegularSeasonGame)
                self.runner.updateInGameConfidence(-.02)
                self.defense.updateInGameConfidence(.02)
                self.defense.gameDefenseStats['fumRec'] += 1
                self.isFumbleLost = True
                self.playResult = PlayResult.Fumble

        if self.yardage > self.yardsToEndzone:
            self.yardage = self.yardsToEndzone

        self.runner.addRushYards(self.yardage, self.game.isRegularSeasonGame)
        self.runner.addCarry(self.game.isRegularSeasonGame)
        self.defense.gameDefenseStats['runYardsAlwd'] += self.yardage
        self.defense.gameDefenseStats['totalYardsAlwd'] += self.yardage
        if self.yardage >= 20:
            self.runner.gameStatsDict['rushing']['20+'] += 1
        if self.yardage > self.runner.gameStatsDict['rushing']['longest']:
            self.runner.gameStatsDict['rushing']['longest'] = self.yardage
        

    def passPlay(self, playKey):
        self.play = passPlayBook[playKey]
        self.playType = PlayType.Pass
        self.passer: FloosPlayer.PlayerQB = self.offense.rosterDict['qb']
        self.receiver: FloosPlayer.PlayerWR = None
        self.selectedTarget = None
        self.blockingModifier = 0
        self.passType = None

        if passPlayBook[playKey]['targets']['te'] is None:
            self.blockingModifier += self.offense.rosterDict['te'].attributes.blockingModifier
        if passPlayBook[playKey]['targets']['rb'] is None:
            self.blockingModifier += self.offense.rosterDict['rb'].attributes.blockingModifier

        sackRoll = randint(1,100)
        sackModifyer = round((self.defense.defensePassRushRating + randint(-5,5))/(((self.passer.gameAttributes.agility + self.passer.gameAttributes.xFactor)/2) + self.blockingModifier + randint(-5,5)))

        if sackRoll < round((3 * (sackModifyer)) + passPlayBook[playKey]['dropback'].value):
            self.yardage = round(-(randint(0,5) * sackModifyer))
            self.defense.gameDefenseStats['sacks'] += 1
            self.isSack = True
            fumbleRoll = randint(1,100)
            fumbleResist = round(((self.passer.gameAttributes.power*.7) + (self.passer.gameAttributes.discipline*1.3)/2) + self.passer.gameAttributes.luckModifier)
            fumbleResistModifyer = 0
            if fumbleResist >= 92:
                fumbleResistModifyer = -2
            elif fumbleResist >= 84 and fumbleResist <= 91:
                fumbleResistModifyer = -1
            elif fumbleResist >= 68 and fumbleResist <= 75:
                fumbleResistModifyer = 1
            elif fumbleResist >= 60 and fumbleResist <= 67:
                fumbleResistModifyer = 2
            if (fumbleRoll+fumbleResistModifyer) > 96:
                #fumble
                self.isFumble = True
                if (self.defense.defensePassRushRating + randint(-5,5)) >= (self.passer.gameAttributes.power + self.passer.gameAttributes.luckModifier + randint(-5,5)):
                    self.passer.updateInGameConfidence(-.02)
                    self.defense.updateInGameConfidence(.02)
                    self.defense.gameDefenseStats['fumRec'] += 1
                    self.isFumbleLost = True
                    self.playResult = PlayResult.Fumble
        else:
            self.passer.addPassAttempt(self.game.isRegularSeasonGame)
            targets:dict = passPlayBook[playKey]['targets']
            targetList = []
            
            for key in targets.keys():
                if targets[key] is not None:
                    receiver = self.offense.rosterDict[key]
                    receiverStatusDict = {'receiver': receiver, 'isOpen': False, 'route': targets[key]}
                    if (receiver.gameAttributes.routeRunning + randint(-10,10)) > (self.defense.defensePassCoverageRating + randint(-10,10)):
                        receiverStatusDict['isOpen'] = True
                    targetList.append(receiverStatusDict)
            
            tempTargetList:list = copy.copy(targetList)
            while len(tempTargetList) > 0:
                target = choice(tempTargetList)

                if target['isOpen'] and self.passer.attributes.vision > randint(1,100):
                    self.selectedTarget = target
                    self.receiver = target['receiver']
                    self.passType = target['route']
                    break
                elif self.passer.attributes.vision < 70:
                    x = randint(1,100)
                    if x > 25:
                        self.selectedTarget = target
                        self.receiver = target['receiver']
                        self.passType = target['route']
                        break
                elif self.passer.attributes.vision < 85:
                    x = randint(1,100)
                    if x > 60:
                        self.selectedTarget = target
                        self.receiver = target['receiver']
                        self.passType = target['route']
                        break
                elif self.passer.attributes.vision < 90:
                    x = randint(1,100)
                    if x > 90:
                        self.selectedTarget = target
                        self.receiver = target['receiver']
                        self.passType = target['route']
                        break

                tempTargetList.remove(target)

            if self.receiver is None:
                if self.passer.gameAttributes.discipline < 70:
                    x = randint(0,len(targetList)-1)
                    self.selectedTarget = targetList[x]
                    self.receiver = targetList[x]['receiver']
                    self.passType = targetList[x]['route']
                elif self.passer.gameAttributes.discipline > 90:
                    if randint(1,10) < 10:
                        self.passType = PassType.throwAway
                    else:
                        x = randint(0,len(targetList)-1)
                        self.selectedTarget = targetList[x]
                        self.receiver = targetList[x]['receiver']
                        self.passType = targetList[x]['route']
                else:
                    if randint(1,10) < 5:
                        self.passType = PassType.throwAway
                    else:
                        x = randint(0,len(targetList)-1)
                        self.selectedTarget = targetList[x]
                        self.receiver = targetList[x]['receiver']
                        self.passType = targetList[x]['route']

            if self.receiver is not None:
                accRoll = randint(1,100)
                receiverYACRating = round((self.receiver.gameAttributes.agility+self.receiver.gameAttributes.speed+self.receiver.gameAttributes.playMakingAbility)/3)

            if self.passType.value == 1:
                if (self.selectedTarget['isOpen'] and accRoll < ((self.passer.gameAttributes.accuracy + self.passer.gameAttributes.xFactor)/2)) or (accRoll < (((self.passer.gameAttributes.accuracy + self.passer.gameAttributes.xFactor)/2) - (self.defense.defensePassCoverageRating/12))):
                    dropRoll = round(randint(1,100) + (self.defense.defensePassCoverageRating/10))
                    if (self.receiver.gameAttributes.hands) > dropRoll:
                        passYards = randint(0,5)
                        yac = 0
                        x = randint(1,10)
                        if (receiverYACRating + randint(-10,10)) > (self.defense.defensePassCoverageRating + randint(-10,10)):
                            if x < 2:
                                yac = 0
                            elif x >= 2 and x < 5:
                                yac = randint(0,3)
                            elif x >= 5 and x <= 9:
                                yac = randint(4,7)
                            else:
                                if self.yardsToEndzone < passYards + 7:
                                    yac = self.yardsToEndzone
                                else:
                                    yac = randint(7, self.yardsToEndzone)
                        else:
                            if x < 6:
                                yac = 0
                            elif x >= 6 and x <= 9:
                                yac = randint(0,2)
                            else:
                                yac = randint(3,5)

                        self.yardage = passYards + yac
                        if self.yardage > self.yardsToEndzone and passYards < self.yardsToEndzone:
                            self.yardage = self.yardsToEndzone
                            yac = self.yardsToEndzone - passYards
                        self.passer.addPassYards(self.yardage,self.game.isRegularSeasonGame)
                        self.passer.addCompletion(self.game.isRegularSeasonGame)
                        self.receiver.addRcvPassTarget(self.game.isRegularSeasonGame)
                        self.receiver.addReception(self.game.isRegularSeasonGame)
                        self.receiver.addReceiveYards(self.yardage, self.game.isRegularSeasonGame)
                        self.receiver.addYAC(yac, self.game.isRegularSeasonGame)
                        self.defense.gameDefenseStats['passYardsAlwd'] += self.yardage
                        self.defense.gameDefenseStats['totalYardsAlwd'] += self.yardage
                        self.passer.updateInGameConfidence(0.005)
                        self.receiver.updateInGameConfidence(0.005)
                        self.defense.updateInGameConfidence(-.005)
                        self.isPassCompletion = True
                        if self.yardage >= 20:
                            self.passer.gameStatsDict['passing']['20+'] += 1
                            self.receiver.gameStatsDict['receiving']['20+'] += 1
                        if self.yardage > self.passer.gameStatsDict['passing']['longest']:
                            self.passer.gameStatsDict['passing']['longest'] = self.yardage
                        if self.yardage > self.receiver.gameStatsDict['receiving']['longest']:
                            self.receiver.gameStatsDict['receiving']['longest'] = self.yardage
                    else:
                        self.receiver.addRcvPassTarget(self.game.isRegularSeasonGame)
                        self.receiver.addPassDrop(self.game.isRegularSeasonGame)
                        self.receiver.updateInGameConfidence(-.005)
                        self.defense.updateInGameConfidence(.005)
                        self.passIsDropped = True
                else:
                    interceptRoll = randint(1,100)
                    self.passer.addMissedPass(self.game.isRegularSeasonGame)
                    if interceptRoll <= 5:
                        self.yardage = randint(-2,5)
                        self.passer.addInterception(self.game.isRegularSeasonGame)
                        self.passer.updateInGameConfidence(-.02)
                        self.defense.updateInGameConfidence(.02)
                        self.defense.gameDefenseStats['ints'] += 1
                        self.isInterception = True
                        self.playResult = PlayResult.Interception
                    else:
                        self.defense.updateInGameConfidence(.005)
                        self.passer.updateInGameConfidence(-.005)
            elif self.passType.value == 2:
                if (self.selectedTarget['isOpen'] and accRoll < ((self.passer.gameAttributes.accuracy + self.passer.gameAttributes.xFactor)/2)) or (accRoll < (((self.passer.gameAttributes.accuracy + self.passer.gameAttributes.xFactor)/2) - (self.defense.defensePassCoverageRating/8))):
                    dropRoll = round(randint(1,100) + (self.defense.defensePassCoverageRating/10))
                    if (self.receiver.gameAttributes.hands) > dropRoll:
                        passYards = randint(5,10)
                        yac = 0
                        x = randint(1,10)
                        if (receiverYACRating + randint(-10,10)) > (self.defense.defensePassCoverageRating + randint(-10,10)):
                            if x < 2:
                                yac = 0
                            elif x >= 2 and x < 5:
                                yac = randint(0,3)
                            elif x >= 5 and x <= 9:
                                yac = randint(4,7)
                            else:
                                if self.yardsToEndzone < passYards + 7:
                                    yac = self.yardsToEndzone
                                else:
                                    yac = randint(7, self.yardsToEndzone)
                        else:
                            if x < 6:
                                yac = 0
                            elif x >= 6 and x <= 9:
                                yac = randint(0,2)
                            else:
                                yac = randint(3,5)
                        self.yardage = passYards + yac
                        if self.yardage > self.yardsToEndzone and passYards < self.yardsToEndzone:
                            self.yardage = self.yardsToEndzone
                            yac = self.yardsToEndzone - passYards
                        self.passer.addPassYards(self.yardage, self.game.isRegularSeasonGame)
                        self.passer.addCompletion(self.game.isRegularSeasonGame)
                        self.receiver.addRcvPassTarget(self.game.isRegularSeasonGame)
                        self.receiver.addReception(self.game.isRegularSeasonGame)
                        self.receiver.addReceiveYards(self.yardage, self.game.isRegularSeasonGame)
                        self.receiver.addYAC(yac, self.game.isRegularSeasonGame)
                        self.defense.gameDefenseStats['passYardsAlwd'] += self.yardage
                        self.defense.gameDefenseStats['totalYardsAlwd'] += self.yardage
                        self.passer.updateInGameConfidence(.005)
                        self.receiver.updateInGameConfidence(.005)
                        self.defense.updateInGameConfidence(-.005)
                        self.isPassCompletion = True
                        if self.yardage >= 20:
                            self.passer.gameStatsDict['passing']['20+'] += 1
                            self.receiver.gameStatsDict['receiving']['20+'] += 1
                        if self.yardage > self.passer.gameStatsDict['passing']['longest']:
                            self.passer.gameStatsDict['passing']['longest'] = self.yardage
                        if self.yardage > self.receiver.gameStatsDict['receiving']['longest']:
                            self.receiver.gameStatsDict['receiving']['longest'] = self.yardage
                    else:
                        self.receiver.addRcvPassTarget(self.game.isRegularSeasonGame)
                        self.receiver.addPassDrop(self.game.isRegularSeasonGame)
                        self.defense.updateInGameConfidence(.005)
                        self.receiver.updateInGameConfidence(-.005)
                        self.passIsDropped = True
                else:
                    interceptRoll = randint(1,100)
                    self.passer.addMissedPass(self.game.isRegularSeasonGame)
                    if interceptRoll <= 8:
                        self.yardage = randint(0,10)
                        self.passer.addInterception(self.game.isRegularSeasonGame)
                        self.passer.updateInGameConfidence(-.02)
                        self.defense.updateInGameConfidence(.02)
                        self.defense.gameDefenseStats['ints'] += 1
                        self.isInterception = True
                        self.playResult = PlayResult.Interception
                    else:  
                        self.defense.updateInGameConfidence(.005)
                        self.passer.updateInGameConfidence(-.005)
            elif self.passType.value == 3:
                if (self.selectedTarget['isOpen'] and accRoll < ((self.passer.gameAttributes.accuracy + self.passer.gameAttributes.xFactor)/2)) or (accRoll < (((self.passer.gameAttributes.accuracy + self.passer.gameAttributes.xFactor)/2) - (self.defense.defensePassCoverageRating/5))):
                    dropRoll = round(randint(1,100) + (self.defense.defensePassCoverageRating/10))
                    if (self.receiver.gameAttributes.hands) > dropRoll:
                        passYards = randint(11,20)
                        yac = 0
                        x = randint(1,10)
                        if (receiverYACRating + randint(-10,10)) > (self.defense.defensePassCoverageRating + randint(-10,10)):
                            if x < 2:
                                yac = 0
                            elif x >= 2 and x < 5:
                                yac = randint(0,3)
                            elif x >= 5 and x <= 9:
                                yac = randint(4,7)
                            else:
                                if self.yardsToEndzone < passYards + 7:
                                    yac = self.yardsToEndzone
                                else:
                                    yac = randint(7, self.yardsToEndzone)
                        else:
                            if x < 6:
                                yac = 0
                            elif x >= 6 and x <= 9:
                                yac = randint(0,2)
                            else:
                                yac = randint(3, 5)
                        self.yardage = passYards + yac
                        if self.yardage > self.yardsToEndzone and passYards < self.yardsToEndzone:
                            self.yardage = self.yardsToEndzone
                            yac = self.yardsToEndzone - passYards
                        self.passer.addPassYards(self.yardage, self.game.isRegularSeasonGame)
                        self.passer.addCompletion(self.game.isRegularSeasonGame)
                        self.receiver.addRcvPassTarget(self.game.isRegularSeasonGame)
                        self.receiver.addReception(self.game.isRegularSeasonGame)
                        self.receiver.addReceiveYards(self.yardage, self.game.isRegularSeasonGame)
                        self.receiver.addYAC(yac, self.game.isRegularSeasonGame)
                        self.defense.gameDefenseStats['passYardsAlwd'] += self.yardage
                        self.defense.gameDefenseStats['totalYardsAlwd'] += self.yardage
                        self.passer.updateInGameConfidence(.01)
                        self.receiver.updateInGameConfidence(.01)
                        self.defense.updateInGameConfidence(-.01)
                        self.isPassCompletion = True
                        if self.yardage >= 20:
                            self.passer.gameStatsDict['passing']['20+'] += 1
                            self.receiver.gameStatsDict['receiving']['20+'] += 1
                        if self.yardage > self.passer.gameStatsDict['passing']['longest']:
                            self.passer.gameStatsDict['passing']['longest'] = self.yardage
                        if self.yardage > self.receiver.gameStatsDict['receiving']['longest']:
                            self.receiver.gameStatsDict['receiving']['longest'] = self.yardage
                    else:
                        self.receiver.addRcvPassTarget(self.game.isRegularSeasonGame)
                        self.receiver.addPassDrop(self.game.isRegularSeasonGame)
                        self.receiver.updateInGameConfidence(-.005)
                        self.defense.updateInGameConfidence(.005)
                        self.passIsDropped = True
                else:
                    interceptRoll = randint(1,100)
                    self.passer.addMissedPass(self.game.isRegularSeasonGame) 
                    if interceptRoll <= 10:
                        self.yardage = randint(-5,20)
                        self.passer.addInterception(self.game.isRegularSeasonGame)
                        self.passer.updateInGameConfidence(-.02)
                        self.defense.updateInGameConfidence(.02)
                        self.defense.gameDefenseStats['ints'] += 1
                        self.isInterception = True
                        self.playResult = PlayResult.Interception
                    else: 
                        self.defense.updateInGameConfidence(.005)
                        self.passer.updateInGameConfidence(-.005)
            elif self.passType.value == 4:
                if (self.selectedTarget['isOpen'] and accRoll < ((self.passer.gameAttributes.accuracy + self.passer.gameAttributes.xFactor)/2)) or (accRoll < (((self.passer.gameAttributes.accuracy + self.passer.gameAttributes.xFactor)/2) - (self.defense.defensePassCoverageRating/1.3))):
                    dropRoll = round(randint(1,100) + (self.defense.defensePassCoverageRating/3))
                    if (self.receiver.gameAttributes.hands) > dropRoll:
                        maxYards = round(70*(self.passer.attributes.armStrength/100))
                        if self.yardsToEndzone+10 <= maxYards:
                            maxYards = self.yardsToEndzone+10
                        passYards = randint((maxYards-10),(maxYards))
                        yac = 0
                        x = randint(1,10)
                        if passYards < self.yardsToEndzone:
                            if (receiverYACRating + randint(-10,10)) > (self.defense.defensePassCoverageRating + randint(-10,10)):
                                if x < 2:
                                    yac = 0
                                elif x >= 2 and x < 5:
                                    yac = randint(0,3)
                                elif x >= 5 and x <= 9:
                                    yac = randint(4,7)
                                else:
                                    if self.yardsToEndzone < passYards + 7:
                                        yac = self.yardsToEndzone
                                    else:
                                        yac = randint(7, self.yardsToEndzone)
                            else:
                                if x < 6:
                                    yac = 0
                                elif x >= 6 and x <= 9:
                                    yac = randint(0,2)
                                else:
                                    yac = randint(3, 5)
                        self.yardage = passYards + yac
                        if self.yardage > self.yardsToEndzone and passYards < self.yardsToEndzone:
                            self.yardage = self.yardsToEndzone
                            yac = self.yardsToEndzone - passYards
                        self.passer.addPassYards(self.yardage, self.game.isRegularSeasonGame)
                        self.passer.addCompletion(self.game.isRegularSeasonGame)
                        self.receiver.addRcvPassTarget(self.game.isRegularSeasonGame)
                        self.receiver.addReception(self.game.isRegularSeasonGame)
                        self.receiver.addReceiveYards(self.yardage, self.game.isRegularSeasonGame)
                        self.receiver.addYAC(yac, self.game.isRegularSeasonGame)
                        self.defense.gameDefenseStats['passYardsAlwd'] += self.yardage
                        self.defense.gameDefenseStats['totalYardsAlwd'] += self.yardage
                        self.passer.updateInGameConfidence(.01)
                        self.receiver.updateInGameConfidence(.01)
                        self.defense.updateInGameConfidence(-.01)
                        self.isPassCompletion = True
                        if self.yardage >= 20:
                            self.passer.gameStatsDict['passing']['20+'] += 1
                            self.receiver.gameStatsDict['receiving']['20+'] += 1
                        if self.yardage > self.passer.gameStatsDict['passing']['longest']:
                            self.passer.gameStatsDict['passing']['longest'] = self.yardage
                        if self.yardage > self.receiver.gameStatsDict['receiving']['longest']:
                            self.receiver.gameStatsDict['receiving']['longest'] = self.yardage
                    else:
                        self.receiver.addRcvPassTarget(self.game.isRegularSeasonGame)
                        self.receiver.addPassDrop(self.game.isRegularSeasonGame)
                        self.receiver.updateInGameConfidence(-.005)
                        self.defense.updateInGameConfidence(.005)
                        self.passIsDropped = True
                else:
                    interceptRoll = randint(1,100)
                    self.passer.addMissedPass(self.game.isRegularSeasonGame) 
                    if interceptRoll <= 15:
                        self.yardage = randint(-5,20)
                        self.passer.addInterception(self.game.isRegularSeasonGame)
                        self.passer.updateInGameConfidence(-.02)
                        self.defense.updateInGameConfidence(.02)
                        self.defense.gameDefenseStats['ints'] += 1
                        self.isInterception = True
                        self.playResult = PlayResult.Interception
                    else: 
                        self.defense.updateInGameConfidence(.005)
                        self.passer.updateInGameConfidence(-.005)
            elif self.passType.value == 5:
                self.passer.addMissedPass(self.game.isRegularSeasonGame)
