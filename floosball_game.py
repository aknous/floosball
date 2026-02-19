import enum
from gettext import find
from random import randint
from random_batch import batched_randint, batched_random, batched_choice
import copy
from stats_optimization import get_optimized_stats
import asyncio
import math
import statistics
from secrets import choice
from time import sleep
import floosball_player as FloosPlayer
import floosball_team as FloosTeam
import floosball_methods as FloosMethods
import datetime
import numpy as np
import matplotlib.pyplot as plt
from constants import (
    GAME_MAX_PLAYS, PLAYS_TO_FOURTH_QUARTER, PLAYS_TO_THIRD_QUARTER,
    RATING_SCALE_MIN, RATING_RANGE, PERCENTAGE_MULTIPLIER, FIELD_LENGTH,
    PRESSURE_BASE, PRESSURE_MAX_ADDITIONAL, PRESSURE_CALCULATION_DIVISOR
)

# Import TimingManager for game-level timing control
try:
    from managers.timingManager import TimingManager, TimingMode
    TIMING_AVAILABLE = True
except ImportError:
    # Fallback if timing manager not available
    TIMING_AVAILABLE = False
    TimingManager = None
    TimingMode = None


class PlayType(enum.Enum):
    Run = 'Run'
    Pass = 'Pass'
    FieldGoal = 'Field Goal Try'
    Punt = 'Punt'
    ExtraPoint = 'Extra Point'
    Spike = 'Spike'
    Kneel = 'Kneel'
    
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
                            'rb': None
                        }
                    },
                    'Play2': {
                        'dropback': QbDropback.long,
                        'targets': {
                            'wr1': PassType.long,
                            'wr2': PassType.long,
                            'te': PassType.medium,
                            'rb': None
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
                            'te': PassType.medium,
                            'rb': None
                        }
                    },
                    'Play6': {
                        'dropback': QbDropback.medium,
                        'targets': {
                            'wr1': PassType.medium,
                            'wr2': PassType.medium,
                            'te': PassType.medium,
                            'rb': None
                        }
                    },
                    'Play7': {
                        'dropback': QbDropback.medium,
                        'targets': {
                            'wr1': PassType.medium,
                            'wr2': None,
                            'te': PassType.medium,
                            'rb': None
                        }
                    },
                    'Play8': {
                        'dropback': QbDropback.short,
                        'targets': {
                            'wr1': PassType.short,
                            'wr2': PassType.short,
                            'te': PassType.short,
                            'rb': None
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
                    },
                    'Play11': {
                        'dropback': QbDropback.short,
                        'targets': {
                            'wr1': None,
                            'wr2': None,
                            'te': PassType.short,
                            'rb': PassType.short
                        }
                    },
                    'Play12': {
                        'dropback': QbDropback.short,
                        'targets': {
                            'wr1': None,
                            'wr2': None,
                            'te': PassType.short,
                            'rb': None
                        }
                    },
                    'Play13': {
                        'dropback': QbDropback.medium,
                        'targets': {
                            'wr1': None,
                            'wr2': None,
                            'te': PassType.medium,
                            'rb': None
                        }
                    }
                }

def returnShortPassPlay():
    return choice(['Play8','Play10', 'Play11', 'Play12'])

def returnMediumPassPlay():
    return choice(['Play3','Play6','Play7', 'Play13'])

def returnLongPassPlay():
    return choice(['Play1','Play2','Play4','Play5'])
    
class Game:
    def __init__(self, homeTeam, awayTeam, timingManager=None):
        self.id = None
        self.status = None
        self.homeTeam : FloosTeam.Team = homeTeam
        self.awayTeam : FloosTeam.Team = awayTeam
        self.awayScore = 0
        self.homeScore = 0
        
        # Play-by-play logging
        self.play_log_file = None
        self.verbose_logging = False
        
        # Set up timing manager for game-level delays
        if timingManager is not None:
            self.timingManager = timingManager
        elif TIMING_AVAILABLE:
            # Create default fast timing manager if none provided
            self.timingManager = TimingManager(TimingMode.FAST)
        else:
            self.timingManager = None
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
        
        # Game clock system
        self.gameClockSeconds = 900  # 15 minutes per quarter
        self.clockRunning = False
        self.homeTimeoutsRemaining = 3
        self.awayTimeoutsRemaining = 3
        self.twoMinuteWarningShown = False
        
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
        self.firstOtPossessionComplete = False  # Track if both teams have had initial OT possession
        self.startTime: datetime.datetime = None
        self.isTwoPtConv = False
        self.isOnsideKick = False
        self.gamePressure = 0

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
            playerDict['ratingStars'] = round((((player.attributes.skillRating - 60)/40)*4)+1)
            playerDict['playerTier'] = player.playerTier.value
            playerDict['gameStats'] = player.gameStats.to_legacy_dict()

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
            playerDict['ratingStars'] = round((((player.attributes.skillRating - 60)/40)*4)+1)
            playerDict['playerTier'] = player.playerTier.value
            playerDict['gameStats'] = player.gameStats.to_legacy_dict()

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
        gameStatsDict['playsLeft'] = GAME_MAX_PLAYS - self.totalPlays
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
            playerDict['ratingStars'] = round((((player.attributes.skillRating - 60)/40)*4)+1)
            playerDict['playerTier'] = player.playerTier.value
            playerDict['gameStats'] = player.gameStats.to_legacy_dict()

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
            playerDict['ratingStars'] = round((((player.attributes.skillRating - 60)/40)*4)+1)
            playerDict['playerTier'] = player.playerTier.value
            playerDict['gameStats'] = player.gameStats.to_legacy_dict()

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
        gameStatsDict['playsLeft'] = GAME_MAX_PLAYS - self.totalPlays
        gameStatsDict['status'] = self.status.name


        self.gameDict['gameStats'] = gameStatsDict


    def playCaller(self):
        runDefenseFactor = 0.0015 * self.defensiveTeam.defenseRunCoverageRating   # Influences how sharply success drops with distance
        passDefenseFactor = 0.0015 * self.defensiveTeam.defensePassRating 
        skillFactor = 2      # Scales how impactful kicker skill is

        runBaseProbability = round(1 / (1 + math.exp(runDefenseFactor * (self.yardsToFirstDown - 3))), 2)
        rbNormalizedSkill = (self.offensiveTeam.rosterDict["rb"].gameAttributes.overallRating - RATING_SCALE_MIN) / RATING_RANGE
        runSuccessProbability = round(runBaseProbability * (rbNormalizedSkill * skillFactor), 2)
        runSuccessProbability = round(max(0, min(1, runSuccessProbability)) * PERCENTAGE_MULTIPLIER)

        passOffenseNormalizedSkill = (round(statistics.mean([self.offensiveTeam.rosterDict["qb"].gameAttributes.overallRating, self.offensiveTeam.rosterDict["wr1"].gameAttributes.overallRating, self.offensiveTeam.rosterDict["wr2"].gameAttributes.overallRating, self.offensiveTeam.rosterDict["te"].gameAttributes.overallRating])) - RATING_SCALE_MIN) / RATING_RANGE
       
        shortPassBaseProbability = round(1 / (1 + math.exp(passDefenseFactor * (self.yardsToFirstDown - 7))), 2)
        shortPassSuccessProbability = round(shortPassBaseProbability * (passOffenseNormalizedSkill * skillFactor), 2)
        shortPassSuccessProbability = round(max(0, min(1, shortPassSuccessProbability)) * PERCENTAGE_MULTIPLIER)

        medPassBaseProbability = round(1 / (1 + math.exp(passDefenseFactor * (self.yardsToFirstDown - 3))), 2)
        medPassSuccessProbability = round(medPassBaseProbability * (passOffenseNormalizedSkill * skillFactor), 2)
        medPassSuccessProbability = round(max(0, min(1, medPassSuccessProbability)) * PERCENTAGE_MULTIPLIER)

        longPassBaseProbability = round(1 / (1 + math.exp(passDefenseFactor * (self.yardsToFirstDown + 2))), 2)
        longPassSuccessProbability = round(longPassBaseProbability * (passOffenseNormalizedSkill * skillFactor), 2)
        longPassSuccessProbability = round(max(0, min(1, longPassSuccessProbability)) * PERCENTAGE_MULTIPLIER)

        if self.homeTeam == self.play.offense:
            scoreDiff = self.awayScore - self.homeScore
        else: scoreDiff = self.homeScore - self.awayScore

        # OVERTIME: Be aggressive on 4th down
        if self.currentQuarter == 5:
            if self.down == 4:
                # Always try FG if in range
                if self.yardsToEndzone <= (self.offensiveTeam.rosterDict['k'].maxFgDistance - 17):
                    self.play.playType = PlayType.FieldGoal
                    return
                
                # If game is tied, be VERY aggressive - almost never punt
                if self.homeScore == self.awayScore:
                    if self.yardsToFirstDown <= 3:
                        # Short yardage - go for it with run or short pass
                        x = batched_randint(1, 2)
                        if x == 1:
                            self.play.runPlay()
                        else:
                            self.play.passPlay(returnShortPassPlay())
                        return
                    elif self.yardsToFirstDown <= 7:
                        # Medium yardage - go for it with pass
                        self.play.passPlay(returnMediumPassPlay())
                        return
                    elif self.yardsToFirstDown <= 15:
                        # Long yardage - aggressive pass
                        self.play.passPlay(returnLongPassPlay())
                        return
                    else:
                        # 4th & 16+ from bad field position - only time to punt in tied OT
                        if self.yardsToSafety < 15:
                            # Too dangerous to go for it from own end zone
                            self.play.playType = PlayType.Punt
                            return
                        else:
                            # Still go for it - desperation pass
                            self.play.passPlay(returnLongPassPlay())
                            return
                
                # If leading in OT, be aggressive to put game away
                elif scoreDiff > 0:
                    if self.yardsToFirstDown <= 2:
                        self.play.passPlay(returnShortPassPlay())
                        return
                    elif self.yardsToFirstDown <= 8:
                        self.play.passPlay(returnMediumPassPlay())
                        return
                    else:
                        self.play.passPlay(returnLongPassPlay())
                        return
                
                # If trailing in OT, ultra aggressive
                else:
                    if self.yardsToFirstDown <= 10:
                        self.play.passPlay(returnMediumPassPlay())
                        return
                    else:
                        self.play.passPlay(returnLongPassPlay())
                        return
        
        # END OF HALF: Be aggressive if in FG range with little time left
        if self.currentQuarter == 2 and self.gameClockSeconds < 120 and self.down == 4:
            if self.yardsToEndzone <= (self.offensiveTeam.rosterDict['k'].maxFgDistance - 17):
                self.play.playType = PlayType.FieldGoal
                return
        
        # END OF GAME: Aggressive FG attempts when time is running out
        if self.currentQuarter == 4 and self.gameClockSeconds < 120 and self.down == 4:
            if scoreDiff >= 0:
                if scoreDiff <= 3 and self.yardsToEndzone <= (self.offensiveTeam.rosterDict['k'].maxFgDistance - 17):
                    self.play.playType = PlayType.FieldGoal
                    return
        
        # NORMAL DOWN LOGIC
        if self.down <= 2:
            if self.currentQuarter == 4:
                if scoreDiff > 0:
                    scoreDiff = self.awayScore - self.homeScore
                    x = batched_randint(1,10)
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
                x = batched_randint(1,10)
                if x <= 5:
                    self.play.runPlay()
                    return
                else:
                    y = batched_randint(1,10)
                    if y <= 4:
                        self.play.passPlay(returnShortPassPlay())
                        return
                    else:
                        self.play.passPlay(returnMediumPassPlay())
                        return
            elif self.yardsToEndzone <= 20:
                x = batched_randint(1,10)
                if x <= 4:
                    self.play.runPlay()
                    return
                else:
                    y = batched_randint(1,10)
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
                x = batched_randint(1,10)
                if x <= 3:
                    y = batched_randint(0,1)
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
                x = batched_randint(0,1)
                if x == 1:
                    self.play.runPlay()
                    return
                else:
                    y = batched_randint(1,10)
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
                if scoreDiff > 0:
                    x = batched_randint(1,10)
                    # Early in Q4 with small lead, be more conservative
                    if self.gameClockSeconds > 600 and scoreDiff <= 7:
                        if x < 7:
                            self.play.passPlay(returnMediumPassPlay())
                            return
                        else:
                            self.play.passPlay(returnShortPassPlay())
                            return
                    if x < 3:
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
                x = batched_randint(1,10)
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
                x = batched_randint(1,10)
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
            # FIRST: Always punt when deep in own territory (safety concern)
            if self.yardsToSafety <= 35:
                self.play.playType = PlayType.Punt
                return
            
            # Check if in field goal range
            kickerMaxDistance = self.offensiveTeam.rosterDict['k'].maxFgDistance - 17
            inFieldGoalRange = self.yardsToEndzone <= kickerMaxDistance
            
            if scoreDiff > 0:
                # When LEADING, be conservative on 4th down
                # Late in game with lead, prioritize FGs to extend lead
                if self.currentQuarter == 4 and self.gameClockSeconds < 300:
                    if inFieldGoalRange and self.yardsToEndzone <= 40:
                        # In range late - kick FG to extend lead
                        self.play.playType = PlayType.FieldGoal
                        return
                    # Not in FG range - consider going for 4th & 1 to run clock
                    if self.yardsToFirstDown <= 1 and self.yardsToSafety > 50:
                        # Very short yardage past midfield - 40% go for it to run clock
                        x = batched_randint(1,10)
                        if x <= 4:
                            self.play.runPlay()
                            return
                    # Otherwise punt to protect lead
                    self.play.playType = PlayType.Punt
                    return
                
                # Earlier in game with lead - kick FGs, otherwise punt
                if inFieldGoalRange and self.yardsToEndzone <= 35:
                    # Easy/medium FG range - take the points
                    self.play.playType = PlayType.FieldGoal
                    return
                # Not in FG range - consider 4th & 1 conversion
                if self.yardsToFirstDown == 1 and self.yardsToSafety > 45:
                    # 4th & 1 in opponent territory - 30% go for it
                    x = batched_randint(1,10)
                    if x <= 3:
                        self.play.runPlay()
                        return
                # Default when leading: PUNT
                self.play.playType = PlayType.Punt
                return
            
            # When trailing, prioritize field goals to get on the board
            elif scoreDiff < 0 and inFieldGoalRange:
                if self.yardsToEndzone <= 25:
                    # Close to endzone - almost always kick FG when losing
                    self.play.playType = PlayType.FieldGoal
                    return
                elif self.currentQuarter >= 3:
                    # Late in game, need points - kick FG 90% of the time
                    x = batched_randint(1,10)
                    if x <= 9:
                        self.play.playType = PlayType.FieldGoal
                        return
                    # 10% chance go for TD
                    self.play.passPlay(returnMediumPassPlay())
                    return
                else:
                    # Early in game - 70% kick FG, 30% go for TD
                    x = batched_randint(1,10)
                    if x <= 7:
                        self.play.playType = PlayType.FieldGoal
                        return
                    self.play.passPlay(returnMediumPassPlay())
                    return
            
            elif self.yardsToEndzone <= 5 and inFieldGoalRange:
                    x = batched_randint(1,10)
                    if x < 7:
                        self.play.playType = PlayType.FieldGoal
                        return
                    else:
                        y = batched_randint(1,10)
                        if y < 6:
                            self.play.runPlay()
                            return
                        elif y >= 6 and y < 9:
                            self.play.passPlay(returnShortPassPlay())
                            return
                        else:
                            self.play.passPlay(returnMediumPassPlay())
                            return

            elif self.yardsToEndzone <= 20 and inFieldGoalRange:
                # Red zone - almost always kick FG
                if self.yardsToFirstDown <= 1:
                    # Very short yardage - 30% go for it
                    x = batched_randint(1,10)
                    if x >= 7:
                        y = randint(1,3)
                        if y == 1:
                            self.play.runPlay()
                            return
                        else:
                            self.play.passPlay(returnShortPassPlay())
                            return
                self.play.playType = PlayType.FieldGoal
                return
            elif self.yardsToEndzone <= 35 and inFieldGoalRange:
                # Medium range FG - usually kick
                if self.yardsToFirstDown <= 2:
                    # Short yardage - 70% kick FG, 30% go for it
                    x = batched_randint(1,10)
                    if x <= 7:
                        self.play.playType = PlayType.FieldGoal
                        return
                    else:
                        y = randint(1,3)
                        if y == 1:
                            self.play.runPlay()
                            return
                        else:
                            self.play.passPlay(returnShortPassPlay())
                            return
                else:
                    # Long yardage - 85% kick FG
                    x = batched_randint(1,100)
                    if x <= 85:
                        self.play.playType = PlayType.FieldGoal
                        return
                    else:
                        self.play.passPlay(returnMediumPassPlay())
                        return
            elif inFieldGoalRange:
                # Long FG attempt - 70% kick, 30% punt
                x = batched_randint(1,10)
                if x <= 7:
                    self.play.playType = PlayType.FieldGoal
                    return
                else:
                    self.play.playType = PlayType.Punt
                    return
            # Not in FG range and not deep in own territory - punt
            else:
                # Very short yardage - consider going for it
                if self.yardsToFirstDown == 1:
                    # 4th & 1 - be aggressive only if past midfield or desperate
                    if self.yardsToSafety > 50 or (scoreDiff < -14 and self.currentQuarter >= 3):
                        x = batched_randint(1,10)
                        if x <= 3:  # 30% go for it
                            self.play.runPlay()
                            return
                    # Otherwise punt
                    self.play.playType = PlayType.Punt
                    return
                elif self.yardsToFirstDown == 2:
                    # 4th & 2 - rarely go for it, only when desperate
                    if scoreDiff < -21 and self.currentQuarter == 4 and self.gameClockSeconds < 600:
                        x = batched_randint(1,10)
                        if x <= 2:  # 20% go for it when down 3+ scores late
                            self.play.passPlay(returnShortPassPlay())
                            return
                    # Otherwise punt
                    self.play.playType = PlayType.Punt
                    return
                else:
                    # 4th & 3+ - almost always punt
                    # Only exception: down multiple scores in Q4
                    if scoreDiff < -17 and self.currentQuarter == 4 and self.gameClockSeconds < 300:
                        x = batched_randint(1,100)
                        if x <= 10:  # 10% go for it when desperate
                            self.play.passPlay(returnMediumPassPlay())
                            return
                    # Default: PUNT
                    self.play.playType = PlayType.Punt
                    return

    def turnover(self, offense: FloosTeam.Team, defense: FloosTeam.Team, yards):
        if self.totalPlays > GAME_MAX_PLAYS:
            if offense is self.homeTeam:
                if self.otHomeHadPos == False:
                    self.otHomeHadPos = True
            elif offense is self.awayTeam:
                if self.otAwayHadPos == False:
                    self.otAwayHadPos = True
        
        # Update OT possession tracking
        if self.currentQuarter == 5:
            if self.otHomeHadPos and self.otAwayHadPos:
                self.firstOtPossessionComplete = True
        
        self.offensiveTeam = defense
        self.defensiveTeam = offense
        self.yardsToEndzone = yards
        self.yardsToSafety = FIELD_LENGTH - self.yardsToEndzone
        self.down = 1
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
        # TODO: These team defense stats could be optimized similar to player stats
        self.winningTeam.gameDefenseStats = copy.deepcopy(FloosTeam.teamStatsDict['Defense'])
        self.losingTeam.gameDefenseStats = copy.deepcopy(FloosTeam.teamStatsDict['Defense'])

        # Sync optimized stat_tracker data to legacy gameStatsDict for all players
        for player in self.homeTeam.rosterDict.values():
            if player:
                player.sync_stats_dicts()
        for player in self.awayTeam.rosterDict.values():
            if player:
                player.sync_stats_dicts()

        for player in self.homeTeam.rosterDict.values():
            player.postgameChanges()

            player.seasonStatsDict['fantasyPoints'] += player.gameStatsDict['fantasyPoints']

            if player.gameStatsDict['passing']['att'] > 0:
                if player.gameStatsDict['passing']['comp'] > 0:
                    player.gameStatsDict['passing']['ypc'] = round(player.gameStatsDict['passing']['yards']/player.gameStatsDict['passing']['comp'], 2)
                    player.gameStatsDict['passing']['compPerc'] = round((player.gameStatsDict['passing']['comp']/player.gameStatsDict['passing']['att'])*100)

                if self.isRegularSeasonGame: 
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
                    player.seasonStatsDict['receiving']['20+'] += player.gameStatsDict['receiving']['20+']

                    if player.gameStatsDict['receiving']['longest'] > player.seasonStatsDict['receiving']['longest']:
                        player.seasonStatsDict['receiving']['longest'] = player.gameStatsDict['receiving']['longest']

                    if player.seasonStatsDict['receiving']['yards'] > 0:
                        player.seasonStatsDict['receiving']['ypr'] = round(player.seasonStatsDict['receiving']['yards']/player.seasonStatsDict['receiving']['receptions'],2)
                        player.seasonStatsDict['receiving']['rcvPerc'] = round((player.seasonStatsDict['receiving']['receptions']/player.seasonStatsDict['receiving']['targets'])*100)

            if player.gameStatsDict['rushing']['carries'] > 0:

                player.gameStatsDict['rushing']['ypc'] = round(player.gameStatsDict['rushing']['yards']/player.gameStatsDict['rushing']['carries'],2)

                if self.isRegularSeasonGame:
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
                    player.seasonStatsDict['receiving']['20+'] += player.gameStatsDict['receiving']['20+']

                    if player.gameStatsDict['receiving']['longest'] > player.seasonStatsDict['receiving']['longest']:
                        player.seasonStatsDict['receiving']['longest'] = player.gameStatsDict['receiving']['longest']

                    if player.seasonStatsDict['receiving']['yards'] > 0:
                        player.seasonStatsDict['receiving']['ypr'] = round(player.seasonStatsDict['receiving']['yards']/player.seasonStatsDict['receiving']['receptions'],2)
                        player.seasonStatsDict['receiving']['rcvPerc'] = round((player.seasonStatsDict['receiving']['receptions']/player.seasonStatsDict['receiving']['targets'])*100)

            if player.gameStatsDict['rushing']['carries'] > 0:

                player.gameStatsDict['rushing']['ypc'] = round(player.gameStatsDict['rushing']['yards']/player.gameStatsDict['rushing']['carries'],2)

                if self.isRegularSeasonGame:
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


    async def playGame(self):
        self.totalPlays = 0
        possReset = 80
        coinFlipWinner = None
        coinFlipLoser = None

        # Initialize clock for Q1
        self.currentQuarter = 1
        self.gameClockSeconds = 900
        self.clockRunning = False

        for player in self.homeTeam.rosterDict.values():
            player: FloosPlayer.Player
            player.gameAttributes = copy.deepcopy(player.attributes)
            player.reset_game_stats()
        for player in self.awayTeam.rosterDict.values():
            player: FloosPlayer.Player
            player.gameAttributes = copy.deepcopy(player.attributes)
            player.reset_game_stats()

        x = batched_randint(0,1)
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
        self.gameFeed.insert(0, {'event':  {
                                                'text': '{} wins the coin toss'.format(coinFlipWinner.name),
                                                'quarter': 1,
                                                'timeRemaining': self.formatTime(self.gameClockSeconds)
                                            }
                                        })
        
        # Main game loop - run until game is over
        while not self.isGameOver():
            # Format and add previous play to feed BEFORE quarter transitions
            # This ensures Q4 plays appear before OT events
            lastPlayFormatted = False
            if self.totalPlays > 0 and self.gameClockSeconds <= 0:
                # Only format if the play was actually executed (has playText)
                if hasattr(self.play, 'playText') and self.play.playText:
                    self.formatPlayText()
                    if self.play.isSack:
                        self.defensiveTeam.gameDefenseStats['fantasyPoints'] += 1
                    if self.play.isFumbleLost or self.play.isInterception or self.play.scoreChange or self.play.yardage >= 30:
                        self.highlights.insert(0, {'play': self.play})
                        self.leagueHighlights.insert(0, {'play': self.play})
                    self.gameFeed.insert(0, {'play': self.play})
                    lastPlayFormatted = True
            
            # Check for quarter transitions
            if self.gameClockSeconds <= 0:
                oldQuarter = self.currentQuarter
                self.advanceQuarter()
                
                # Defensive check: If still in OT and clock is still 0 after advanceQuarter, force reset
                if self.currentQuarter >= 5 and self.gameClockSeconds <= 0 and self.homeScore == self.awayScore:
                    self.gameClockSeconds = 600  # Force clock reset to prevent infinite loop
                
                if oldQuarter == 2:
                    # Halftime
                    self.isHalftime = True
                    self.gameFeed.insert(0, {'event':  {
                                                    'text': 'Halftime',
                                                    'quarter': 2,
                                                    'timeRemaining': '0:00'
                                                }
                                            })
                    if self.timingManager:
                        await self.timingManager.waitForHalftime()
                    self.isHalftime = False
                    
                    # Switch possession for second half
                    self.turnover(coinFlipWinner, coinFlipLoser, possReset)
                    self.down = 1
                
                elif oldQuarter == 4 and self.currentQuarter == 5:
                    # First Overtime period
                    self.gameFeed.insert(0, {'event':  {
                                                    'text': 'Start Overtime',
                                                    'quarter': 'OT',
                                                    'timeRemaining': self.formatTime(self.gameClockSeconds)
                                                }
                                            })
                    self.isOvertime = True
                    x = batched_randint(0,1)
                    if x == 0:
                        coinFlipWinner = self.homeTeam
                        coinFlipLoser = self.awayTeam
                    else:
                        coinFlipWinner = self.awayTeam
                        coinFlipLoser = self.homeTeam
                    self.gameFeed.insert(0, {'event':  {
                                                    'text': '{} wins the OT coin toss'.format(coinFlipWinner.name),
                                                    'quarter': 'OT',
                                                    'timeRemaining': self.formatTime(self.gameClockSeconds)
                                                }
                                            })
                    self.turnover(coinFlipLoser, coinFlipWinner, possReset)
                    self.down = 1
                
                elif oldQuarter == 5 and self.currentQuarter == 5:
                    # Additional OT period (still tied)
                    self.gameFeed.insert(0, {'event':  {
                                                    'text': 'Start Additional Overtime Period',
                                                    'quarter': 'OT',
                                                    'timeRemaining': self.formatTime(self.gameClockSeconds)
                                                }
                                            })
                    # Do coin flip for new OT period
                    x = batched_randint(0,1)
                    if x == 0:
                        coinFlipWinner = self.homeTeam
                        coinFlipLoser = self.awayTeam
                    else:
                        coinFlipWinner = self.awayTeam
                        coinFlipLoser = self.homeTeam
                    self.gameFeed.insert(0, {'event':  {
                                                    'text': '{} wins the OT coin toss'.format(coinFlipWinner.name),
                                                    'quarter': 'OT',
                                                    'timeRemaining': self.formatTime(self.gameClockSeconds)
                                                }
                                            })
                    self.turnover(coinFlipLoser, coinFlipWinner, possReset)
                    self.down = 1
                
                # Quarter start messages
                if self.currentQuarter == 2:
                    if self.timingManager:
                        await self.timingManager.waitForQuarterBreak()
                    self.gameFeed.insert(0, {'event':  {
                                                    'text': 'Start 2nd Quarter',
                                                    'quarter': 2,
                                                    'timeRemaining': self.formatTime(self.gameClockSeconds)
                                                }
                                            })
                elif self.currentQuarter == 3:
                    if self.timingManager:
                        await self.timingManager.waitForQuarterBreak()
                    self.gameFeed.insert(0, {'event':  {
                                                    'text': 'Start 3rd Quarter',
                                                    'quarter': 3,
                                                    'timeRemaining': self.formatTime(self.gameClockSeconds)
                                                }
                                            })
                elif self.currentQuarter == 4:
                    if self.timingManager:
                        await self.timingManager.waitForQuarterBreak()
                    self.gameFeed.insert(0, {'event':  {
                                                    'text': 'Start 4th Quarter',
                                                    'quarter': 4,
                                                    'timeRemaining': self.formatTime(self.gameClockSeconds)
                                                }
                                            })

            # Start new possession if needed
            if self.down == 0 or self.down > 4:
                self.down = 1
                self.yardsToFirstDown = 10
                self.yardsToEndzone = 80
                self.yardsToSafety = 20

            # Possession loop - while offense has downs
            while self.down <= 4 and self.gameClockSeconds > 0:
                # Show previous play if exists (unless already formatted at quarter transition)
                if self.totalPlays > 0 and not lastPlayFormatted:
                    self.formatPlayText()
                    if self.play.isSack:
                        self.defensiveTeam.gameDefenseStats['fantasyPoints'] += 1
                    if self.play.isFumbleLost or self.play.isInterception or self.play.scoreChange or self.play.yardage >= 30:
                        self.highlights.insert(0, {'play': self.play})
                        self.leagueHighlights.insert(0, {'play': self.play})
                    self.gameFeed.insert(0, {'play': self.play})
                
                # Reset flag after first iteration
                lastPlayFormatted = False

                # Update yardline display
                if self.yardsToEndzone > 50:
                    self.yardLine = '{0} {1}'.format(self.offensiveTeam.abbr, (100-self.yardsToEndzone))
                else:
                    self.yardLine = '{0} {1}'.format(self.defensiveTeam.abbr, self.yardsToEndzone)

                # Create new play
                self.play = Play(self)
                
                # Between-plays timing
                if self.timingManager:
                    await self.timingManager.waitBetweenPlays()

                # PRE-SNAP: Consume huddle/snap time
                if self.clockRunning:
                    preSnapTime = self.calculatePreSnapTime()
                    self.consumeGameTime(preSnapTime)
                    self.checkTwoMinuteWarning()
                    
                    # Check if clock expired during pre-snap
                    if self.gameClockSeconds <= 0:
                        break

                # Call and execute play
                self.playCaller()
                
                # Log pre-play situation
                if self.verbose_logging:
                    self.logPlay(f"\n--- PLAY #{self.totalPlays + 1} ---")
                    self.logPlay(f"Quarter {self.currentQuarter}, {self.formatTime(self.gameClockSeconds)} - Score: {self.awayTeam.abbr} {self.awayScore}, {self.homeTeam.abbr} {self.homeScore}")
                    self.logPlay(f"{self.down}{self.getOrdinal(self.down)} & {self.yardsToFirstDown if self.yardsToFirstDown != 'Goal' else 'Goal'} at {self.yardLine}")
                    self.logPlay(f"Offense: {self.offensiveTeam.abbr} (Rating: {self.offensiveTeam.offenseRating})")
                    self.logPlay(f"Defense: {self.defensiveTeam.abbr} (Pass Cov: {self.defensiveTeam.defensePassCoverageRating}, Run: {self.defensiveTeam.defenseRunCoverageRating}, Rush: {self.defensiveTeam.defensePassRushRating})")
                    pressure = self.calculateGamePressure()
                    self.logPlay(f"Game Pressure: {pressure:.1f}")
                
                self.totalPlays += 1
                if self.offensiveTeam is self.homeTeam:
                    self.homePlaysTotal += 1
                if self.offensiveTeam is self.awayTeam:
                    self.awayPlaysTotal += 1

                # PLAY EXECUTION: Handle different play types
                if self.play.playType is PlayType.FieldGoal:
                    if self.verbose_logging:
                        self.logPlay(f"Play Type: FIELD GOAL ATTEMPT from {self.yardsToEndzone + 17} yards")
                    
                    self.play.fieldGoalTry()
                    
                    if self.verbose_logging:
                        kicker = self.offensiveTeam.rosterDict['k']
                        self.logPlay(f"  Kicker: {kicker.name} (Leg: {kicker.attributes.legStrength}, Acc: {kicker.attributes.accuracy})")
                        self.logPlay(f"  Result: {'GOOD' if self.play.isFgGood else 'NO GOOD'}")
                    
                    # Consume time for field goal (always stops clock)
                    playDuration = self.calculatePlayDuration(PlayType.FieldGoal, False)
                    self.consumeGameTime(playDuration)
                    self.checkTwoMinuteWarning()
                    
                    if self.play.isFgGood:
                        self._addScore(self.offensiveTeam, 3)
                        self.defensiveTeam.gameDefenseStats['ptsAlwd'] += 3
                        self.play.playResult = PlayResult.FieldGoalGood
                        self.play.scoreChange = True
                        self.play.homeTeamScore = self.homeScore
                        self.play.awayTeamScore = self.awayScore
                        self.clockRunning = False  # Clock stops after score
                        
                        if self.verbose_logging:
                            self.logPlay(f"  >>> SCORE! {self.offensiveTeam.abbr} now leads/trails {self.homeScore}-{self.awayScore}")
                        
                        # Check if OT should end after score
                        if self.checkOvertimeEnd():
                            break
                        
                        self.turnover(self.offensiveTeam, self.defensiveTeam, possReset)
                        break
                    else:
                        self.play.playResult = PlayResult.FieldGoalNoGood
                        self.clockRunning = False  # Clock stops after turnover
                        self.turnover(self.offensiveTeam, self.defensiveTeam, self.yardsToSafety)
                        break
                        
                if self.play.playType is PlayType.Punt:
                    self.play.playResult = PlayResult.Punt
                    kicker = self.offensiveTeam.rosterDict['k']
                    assert kicker is not None, f"Team {self.offensiveTeam.teamName} has no kicker in roster!"
                    maxPuntYards = round(70*(kicker.attributes.legStrength/100))
                    if maxPuntYards > self.yardsToEndzone:
                        maxPuntYards = self.yardsToEndzone + 10
                    puntDistance = randint((maxPuntYards-20), maxPuntYards)
                    if puntDistance >= self.yardsToEndzone:
                        puntDistance = self.yardsToEndzone - 20
                    newYards = 100 - (self.yardsToEndzone - puntDistance)
                    
                    # Consume time for punt (always stops clock)
                    playDuration = self.calculatePlayDuration(PlayType.Punt, False)
                    self.consumeGameTime(playDuration)
                    self.checkTwoMinuteWarning()
                    self.clockRunning = False  # Clock stops after punt
                    
                    self.turnover(self.offensiveTeam, self.defensiveTeam, newYards)
                    break
                    
                # POST-PLAY: Consume play duration time (for run/pass plays)
                playDuration = self.calculatePlayDuration(self.play.playType, self.play.isInBounds)
                self.consumeGameTime(playDuration)
                
                # Log play result for run/pass plays
                if self.verbose_logging and self.play.playType in [PlayType.Run, PlayType.Pass]:
                    self.logPlay(f"Play Type: {self.play.playType.value}")
                    if self.play.playType == PlayType.Run:
                        runner = self.offensiveTeam.rosterDict['rb']
                        self.logPlay(f"  Runner: {runner.name} (Pwr: {runner.attributes.power}, Spd: {runner.attributes.speed}, Agl: {runner.attributes.agility})")
                    elif self.play.playType == PlayType.Pass:
                        qb = self.offensiveTeam.rosterDict['qb']
                        if hasattr(self.play, 'receiver') and self.play.receiver:
                            self.logPlay(f"  Passer: {qb.name} (Arm: {qb.attributes.armStrength}, Acc: {qb.attributes.accuracy})")
                            self.logPlay(f"  Target: {self.play.receiver.name} (Spd: {self.play.receiver.attributes.speed}, Hands: {self.play.receiver.attributes.hands})")
                    
                    self.logPlay(f"  Gain: {self.play.yardage} yards")
                    if self.play.isFumbleLost:
                        self.logPlay(f"  >>> FUMBLE LOST!")
                    if self.play.isInterception:
                        self.logPlay(f"  >>> INTERCEPTION!")
                    if self.play.isSack:
                        self.logPlay(f"  >>> SACK!")
                
                # Determine if clock should run after play
                self.clockRunning = self.shouldClockRun()
                
                # Check for two-minute warning
                self.checkTwoMinuteWarning()
                
                # Handle turnovers
                if self.play.isFumbleLost or self.play.isInterception:
                    self.defensiveTeam.gameDefenseStats['fantasyPoints'] += 2
                    if self.offensiveTeam is self.homeTeam:
                        self.homeTurnoversTotal += 1
                    elif self.offensiveTeam is self.awayTeam:
                        self.awayTurnoversTotal += 1
                    if self.play.yardage >= self.yardsToEndzone:
                        self.turnover(self.offensiveTeam, self.defensiveTeam, possReset)
                    elif (self.yardsToSafety + self.play.yardage) <= 0:
                        self._addScore(self.defensiveTeam, 6)
    
                        self.play.extraPointTry(self.defensiveTeam)
                        if self.play.isXpGood:
                            self.play.playResult = PlayResult.TouchdownXP
                            self._addScore(self.defensiveTeam, 1) 
                        else:
                            self.play.playResult = PlayResult.TouchdownNoXP
                        self.defensiveTeam.gameDefenseStats['fantasyPoints'] += 3
                        self.play.isTd = True
                        self.play.scoreChange = True
                        self.play.homeTeamScore = self.homeScore
                        self.play.awayTeamScore = self.awayScore
                        
                        # Check if OT should end after score
                        if self.checkOvertimeEnd():
                            break
                        
                        self.turnover(self.defensiveTeam, self.offensiveTeam, possReset)
                        break
                    else:
                        self.turnover(self.offensiveTeam, self.defensiveTeam, (self.yardsToSafety + self.play.yardage))
                    break
                    
                # Handle normal play outcomes
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

                        self._addScore(self.offensiveTeam, 6)

                        self.play.extraPointTry(self.offensiveTeam)
                        if self.play.isXpGood:
                            self.play.playResult = PlayResult.TouchdownXP
                            self._addScore(self.offensiveTeam, 1)

                            self.play.defense.gameDefenseStats['ptsAlwd'] += 1

                        else:
                            self.play.playResult = PlayResult.TouchdownNoXP
                        
                        if self.verbose_logging:
                            self.logPlay(f"  >>> TOUCHDOWN! {self.offensiveTeam.abbr} scores! XP: {'GOOD' if self.play.isXpGood else 'NO GOOD'}")
                            self.logPlay(f"  >>> New Score: {self.awayTeam.abbr} {self.awayScore}, {self.homeTeam.abbr} {self.homeScore}")
                        
                        self.play.scoreChange = True
                        self.play.homeTeamScore = self.homeScore
                        self.play.awayTeamScore = self.awayScore
                        
                        # Check if OT should end after score
                        if self.checkOvertimeEnd():
                            break
                        
                        self.turnover(self.offensiveTeam, self.defensiveTeam, possReset)
                        break

                    elif self.play.yardage >= self.yardsToFirstDown:
                        if self.verbose_logging:
                            self.logPlay(f"  >>> FIRST DOWN!")
                        
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
                            self._addScore(self.defensiveTeam, 6)
    
                            self.play.extraPointTry(self.defensiveTeam)
                            if self.play.isXpGood:
                                self.play.playResult = PlayResult.TouchdownXP
                                self._addScore(self.defensiveTeam, 1) 

                            else:
                                self.play.playResult = PlayResult.TouchdownNoXP

                            self.play.isTd = True
                            self.play.scoreChange = True
                            self.play.homeTeamScore = self.homeScore
                            self.play.awayTeamScore = self.awayScore
                            
                            # Check if OT should end after score
                            if self.checkOvertimeEnd():
                                break
                            
                            self.turnover(self.defensiveTeam, self.offensiveTeam, possReset)
                            break
                        else:
                            self._addScore(self.defensiveTeam, 2)

                            self.play.defense.gameDefenseStats['safeties'] += 1

                            self.play.playResult = PlayResult.Safety
                            self.defensiveTeam.gameDefenseStats['fantasyPoints'] += 2
                            self.play.isSafety = True
                            self.play.scoreChange = True
                            self.play.homeTeamScore = self.homeScore
                            self.play.awayTeamScore = self.awayScore
                            
                            # Check if OT should end after score
                            if self.checkOvertimeEnd():
                                break
                            
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
        
        # Game over - show final play if it was a score or big play
        if self.totalPlays > 0 and self.play:
            if self.play.scoreChange and not self.isOvertime:
                self.formatPlayText()
                if self.play.isFumbleLost or self.play.isInterception or self.play.scoreChange or self.play.yardage >= 30:
                    self.highlights.insert(0, {'play': self.play})
                    self.leagueHighlights.insert(0, {'play': self.play})
                self.gameFeed.insert(0, {'play': self.play})

        # Determine winner
        if self.awayScore > self.homeScore:
            self.winningTeam = self.awayTeam
            self.losingTeam = self.homeTeam
            self.gameDict['score'] = '{0} - {1}'.format(self.awayScore, self.homeScore)
            self.gameFeed.insert(0, {'event':  {
                                                'text': 'Final: {} - {} | {} - {}'.format(self.awayTeam.abbr, self.awayScore, self.homeTeam.abbr, self.homeScore),
                                                'quarter': 'Final',
                                                'timeRemaining': '0:00'
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
                                                'timeRemaining': '0:00'
                                            }
                                        })
            self.leagueHighlights.insert(0, {'event':  {
                                                'text': 'Game Final: {} - {} | {} - {}'.format(self.homeTeam.name, self.homeScore, self.awayTeam.name, self.awayScore)
                                            }
                                        })
        else:
            # Tie game (should only happen in OT time expiration)
            self.winningTeam = self.homeTeam  # Arbitrary - treat as home team win
            self.losingTeam = self.awayTeam
            self.gameDict['score'] = '{0} - {1} (TIE)'.format(self.homeScore, self.awayScore)
            self.gameFeed.insert(0, {'event':  {
                                                'text': 'Final (TIE): {} - {} | {} - {}'.format(self.homeTeam.abbr, self.homeScore, self.awayTeam.abbr, self.awayScore),
                                                'quarter': 'Final',
                                                'timeRemaining': '0:00'
                                            }
                                        })
            self.leagueHighlights.insert(0, {'event':  {
                                                'text': 'Game Final (TIE): {} - {} | {} - {}'.format(self.homeTeam.name, self.homeScore, self.awayTeam.name, self.awayScore)
                                            }
                                        })

        if self.isRegularSeasonGame:
            if self.homeScore != self.awayScore:  # No ties in season standings
                self.winningTeam.seasonTeamStats['wins'] += 1
                self.losingTeam.seasonTeamStats['losses'] += 1
            else:  # Tie game - both teams get a tie
                self.homeTeam.seasonTeamStats['ties'] = self.homeTeam.seasonTeamStats.get('ties', 0) + 1
                self.awayTeam.seasonTeamStats['ties'] = self.awayTeam.seasonTeamStats.get('ties', 0) + 1

        
        self.status = GameStatus.Final
        self.gameDict['winningTeam'] = self.winningTeam.name
        self.gameDict['losingTeam'] = self.losingTeam.name
        self.saveGameData()
        self.homeTeam.getAverages()
        self.awayTeam.getAverages()
        self.winningTeam.updateRating()
        self.losingTeam.updateRating()
        self.calculateWinProbability()  # Calculate probabilities for external ELO update
        # Note: Post-game stat processing now handled by RecordManager.processPostGameStats()
        
        # Close play log file if open
        if self.play_log_file:
            self.play_log_file.write(f"\n{'='*100}\n")
            self.play_log_file.write(f"GAME COMPLETE: {self.awayTeam.abbr} {self.awayScore} - {self.homeTeam.abbr} {self.homeScore}\n")
            self.play_log_file.write(f"{'='*100}\n")
            self.play_log_file.close()
            self.play_log_file = None
    
    def enableVerboseLogging(self, log_file_path):
        """Enable verbose play-by-play logging to a file"""
        try:
            import os
            os.makedirs(os.path.dirname(log_file_path), exist_ok=True)
            self.play_log_file = open(log_file_path, 'w', encoding='utf-8')
            self.verbose_logging = True
            
            # Write header
            self.play_log_file.write(f"{'='*100}\n")
            self.play_log_file.write(f"PLAY-BY-PLAY LOG: {self.awayTeam.abbr} @ {self.homeTeam.abbr}\n")
            self.play_log_file.write(f"{'='*100}\n\n")
        except Exception as e:
            print(f"Failed to enable verbose logging: {e}")
            self.verbose_logging = False
    
    def logPlay(self, message):
        """Log a play-by-play message"""
        if self.verbose_logging and self.play_log_file:
            self.play_log_file.write(message + "\n")
            self.play_log_file.flush()
    
    def getOrdinal(self, n):
        """Get ordinal suffix for a number (1st, 2nd, 3rd, 4th)"""
        if n == 1:
            return "st"
        elif n == 2:
            return "nd"
        elif n == 3:
            return "rd"
        else:
            return "th"

    def calculateGamePressure(self):
        pressure = 0

        # Quarter pressure (0-40)
        if self.currentQuarter == 4:
            # Pressure increases as 4th quarter progresses
            pressure += PRESSURE_BASE + min(PRESSURE_MAX_ADDITIONAL, PRESSURE_MAX_ADDITIONAL * ((GAME_MAX_PLAYS - self.totalPlays) / PRESSURE_CALCULATION_DIVISOR))
        elif self.currentQuarter == 5:  # Overtime
            pressure += 40
        else:
            pressure += 5 * self.currentQuarter

        # Score differential pressure (0-30)
        score_diff = abs(self.homeScore - self.awayScore)
        if score_diff == 0:
            pressure += 30  # Tie game
        elif score_diff <= 3:
            pressure += 25  # One field goal difference
        elif score_diff <= 7:
            pressure += 20  # One possession game
        elif score_diff <= 14:
            pressure += 10  # Two possession game

        # Down and distance pressure (0-20)
        if self.down == 4:
            pressure += 20  # Fourth down
        elif self.down == 3:
            pressure += 15  # Third down
        elif self.down == 2:
            pressure += 5   # Second down

        # Field position pressure (0-10)
        if self.yardsToEndzone <= 10:  # Red zone
            pressure += 10
        elif self.yardsToEndzone <= 30:
            pressure += 5

        # Apply the modifier
        pressure = pressure * self.offensiveTeam.pressureModifier

        return min(100, pressure)  # Cap at 100

    def formatTime(self, seconds: int) -> str:
        """Format seconds into MM:SS display format"""
        minutes = seconds // 60
        secs = seconds % 60
        return f"{minutes}:{secs:02d}"
    
    def calculatePreSnapTime(self) -> int:
        """
        Calculate time consumed before snap (huddle, line up, snap count).
        Adjusts based on game situation.
        """
        baseTime = 35  # Default time between plays
        
        # Get score differential
        if self.offensiveTeam == self.homeTeam:
            scoreDiff = self.homeScore - self.awayScore
        else:
            scoreDiff = self.awayScore - self.homeScore
        
        # Situational adjustments
        if self.gameClockSeconds < 300 and scoreDiff < 0:  # Trailing with <5 min
            if scoreDiff <= -8:  # Down by 2+ scores
                baseTime = 15  # Hurry-up offense
            else:
                baseTime = 25  # Faster pace
        elif self.gameClockSeconds < 300 and scoreDiff > 8:  # Winning by 2+ scores
            baseTime = 40  # Burn clock
        elif self.gameClockSeconds < 120:  # Under 2 minutes
            if scoreDiff < 0:  # Trailing
                baseTime = 12  # Fast tempo
            elif scoreDiff > 0:  # Leading
                baseTime = 38  # Milk clock
        
        # Add variance
        return baseTime + batched_randint(-3, 3)
    
    def calculatePlayDuration(self, playType: PlayType, isInBounds: bool = True) -> int:
        """
        Calculate time consumed during play execution (snap to whistle).
        For clock-stopping plays, includes time for officials to spot ball and restart.
        """
        if playType == PlayType.Run:
            if isInBounds:
                return batched_randint(4, 6)  # Clock runs
            else:
                return batched_randint(3, 5) + 10  # Out of bounds + spot time
        
        elif playType == PlayType.Pass:
            if self.play.isPassCompletion and isInBounds:
                return batched_randint(3, 6)  # Completion in bounds, clock runs
            elif self.play.isPassCompletion and not isInBounds:
                return batched_randint(3, 5) + 10  # Out of bounds + spot time
            elif self.play.isSack:
                return batched_randint(3, 5)  # Sack, clock runs
            else:  # Incomplete
                return batched_randint(2, 3) + 10  # Incomplete + spot time
        
        elif playType == PlayType.FieldGoal or playType == PlayType.Punt:
            return 5 + 15  # Kick + reset time
        
        elif playType == PlayType.Spike:
            return 3  # Quick spike
        
        elif playType == PlayType.Kneel:
            return 40  # Maximum time runoff
        
        return 5  # Default
    
    def shouldClockRun(self) -> bool:
        """
        Determine if clock should be running after a play.
        Returns True if clock runs, False if it stops.
        """
        # Clock always stops after these events
        if self.play.playType == PlayType.FieldGoal:
            return False
        if self.play.playType == PlayType.Punt:
            return False
        if self.play.playType == PlayType.Spike:
            return False
        if self.play.isFumbleLost or self.play.isInterception:
            return False  # Turnover stops clock
        if self.play.scoreChange:
            return False  # Score stops clock
        
        # Pass plays
        if self.play.playType == PlayType.Pass:
            if self.play.isPassCompletion:
                # Completed pass - check if in bounds
                return self.play.isInBounds
            else:
                return False  # Incomplete stops clock
        
        # Run plays - clock runs unless out of bounds
        if self.play.playType == PlayType.Run:
            if self.play.isInBounds:
                return True  # Run in bounds, clock runs
            else:
                return False  # Out of bounds stops clock
        
        # Kneel - clock always runs
        if self.play.playType == PlayType.Kneel:
            return True
    
    def consumeGameTime(self, seconds: int):
        """Consume time from game clock"""
        if seconds > 0:
            self.gameClockSeconds -= seconds
            if self.gameClockSeconds < 0:
                self.gameClockSeconds = 0

    def checkTwoMinuteWarning(self):
        """Check and trigger two-minute warning"""
        if not self.twoMinuteWarningShown and self.gameClockSeconds <= 120:
            if self.currentQuarter == 2 or self.currentQuarter == 4:
                self.twoMinuteWarningShown = True
                self.clockRunning = False
                # Two-minute warning is like a free timeout
                self.gameFeed.insert(0, {'event': {
                    'text': 'Two-Minute Warning',
                    'quarter': self.currentQuarter,
                    'timeRemaining': self.formatTime(self.gameClockSeconds)
                }})
    
    def advanceQuarter(self):
        """Transition to next quarter"""
        if self.currentQuarter == 1:
            self.currentQuarter = 2
            self.gameClockSeconds = 900
            self.twoMinuteWarningShown = False
        elif self.currentQuarter == 2:
            # Halftime
            self.currentQuarter = 3
            self.gameClockSeconds = 900
            self.isHalftime = False
            # Reset timeouts for second half
            self.homeTimeoutsRemaining = 3
            self.awayTimeoutsRemaining = 3
            self.twoMinuteWarningShown = False
        elif self.currentQuarter == 3:
            self.currentQuarter = 4
            self.gameClockSeconds = 900
            self.twoMinuteWarningShown = False
        elif self.currentQuarter == 4:
            # Check for overtime
            if self.homeScore == self.awayScore:
                self.currentQuarter = 5
                self.gameClockSeconds = 600  # 10 minute OT
                self.isOvertime = True
                self.twoMinuteWarningShown = False
            # else game is over
        elif self.currentQuarter >= 5:
            # Additional OT periods - reset clock if game is still tied
            if self.homeScore == self.awayScore:
                self.gameClockSeconds = 600  # Another 10 minute OT period
                self.twoMinuteWarningShown = False
                # Keep currentQuarter at 5 for tracking (all OT periods shown as "OT")
            # else game is over with a winner
    
    def isGameOver(self) -> bool:
        """Check if game should end"""
        # Game over if clock expired in regulation and not tied
        if self.currentQuarter == 4 and self.gameClockSeconds <= 0:
            return self.homeScore != self.awayScore
        
        # In OT (Q5+), check if game should end
        if self.currentQuarter >= 5:
            # If score is not tied and both teams have had possession, game over (sudden death)
            if self.homeScore != self.awayScore and self.firstOtPossessionComplete:
                return True
            # If clock expires and game is still tied, reset for another OT period
            if self.gameClockSeconds <= 0 and self.homeScore == self.awayScore:
                # This shouldn't normally happen here (advanceQuarter should handle it)
                # but adding as defensive check to prevent infinite loops
                return False
        
        return False
    
    def checkOvertimeEnd(self) -> bool:
        """Check if scoring in OT should end the game (hybrid sudden death)"""
        if self.currentQuarter != 5:
            return False
        
        # Mark if both teams have now had possession
        if self.otHomeHadPos and self.otAwayHadPos:
            self.firstOtPossessionComplete = True
        
        # If both teams have had possession and someone is ahead, game over (sudden death)
        if self.firstOtPossessionComplete and self.homeScore != self.awayScore:
            return True
        
        return False

    def _addScore(self, team: FloosTeam.Team, points: int):
        """
        Add points to a team's score and update the appropriate quarter score.
        Consolidates repeated scoring logic throughout the game.
        
        Args:
            team: The team to award points to (homeTeam or awayTeam)
            points: Number of points to add
        """
        if team == self.homeTeam:
            self.homeScore += points
            if self.currentQuarter == 1:
                self.homeScoreQ1 += points
            elif self.currentQuarter == 2:
                self.homeScoreQ2 += points
            elif self.currentQuarter == 3:
                self.homeScoreQ3 += points
            elif self.currentQuarter == 4:
                self.homeScoreQ4 += points
            elif self.currentQuarter == 5:
                self.homeScoreOT += points
        else:  # awayTeam
            self.awayScore += points
            if self.currentQuarter == 1:
                self.awayScoreQ1 += points
            elif self.currentQuarter == 2:
                self.awayScoreQ2 += points
            elif self.currentQuarter == 3:
                self.awayScoreQ3 += points
            elif self.currentQuarter == 4:
                self.awayScoreQ4 += points
            elif self.currentQuarter == 5:
                self.awayScoreOT += points


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
        self.timeRemaining = game.formatTime(game.gameClockSeconds)
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
        self.isInBounds = True  # Default to in bounds
        self.playText = ''

    def fieldGoalTry(self):
        self.game.gamePressure = self.game.calculateGamePressure()
        self.kicker = self.offense.rosterDict['k']
        assert self.kicker is not None, f"Team {self.offense.teamName} has no kicker in roster!"
        self.kicker.addFgAttempt(self.game.isRegularSeasonGame)
        yardsToFG = self.yardsToEndzone + 17
        self.fgDistance = yardsToFG
        distanceFactor = 0.12   # Gentler drop-off with distance (was 0.15)
        skillFactor = 1.5       # Adjusted kicker skill impact (was 2)

        # Base probability uses sigmoid centered at 52 yards (was 50)
        baseProbability = round(1 / (1 + math.exp(distanceFactor * (self.fgDistance - 52))), 2)
        normalizedSkill = (self.kicker.gameAttributes.overallRating - 50) / 50  # Wider range (was 60-100)
        
        # Apply pressure modifier to kicker's effective skill
        pressureModifier = self.kicker.attributes.getPressureModifier(self.game.gamePressure)
        adjustedSkill = normalizedSkill + (pressureModifier / 100)  # Normalize pressure modifier to skill scale
        
        # Final probability: base * skill, then add bonus for short kicks
        probability = baseProbability * (0.4 + adjustedSkill * skillFactor)  # Minimum 40% of base
        
        # Bonus for chip shots (under 30 yards)
        if self.fgDistance < 30:
            probability = min(1.0, probability + 0.15)
        
        probability = round(max(0.05, min(1, probability)) * 100)  # 5-100% range

        x = batched_randint(1,100)

        if x <= probability:
            self.isFgGood = True
            self.kicker.addFg(self.fgDistance, self.game.isRegularSeasonGame)
            if yardsToFG > self.kicker.gameStatsDict['kicking']['longest']:
                self.kicker.gameStatsDict['kicking']['longest'] = yardsToFG
        else:
            self.kicker.addMissedFg(self.fgDistance, self.game.isRegularSeasonGame)

        if yardsToFG <= 20:
            if self.isFgGood:
                self.kicker.updateInGameConfidence(.005)
            else:
                self.kicker.updateInGameConfidence(-.02)
        elif yardsToFG > 20 and yardsToFG <= 30:
            if self.isFgGood:
                self.kicker.updateInGameConfidence(.01)
            else:
                self.kicker.updateInGameConfidence(-.015)
        elif yardsToFG > 30 and yardsToFG <= 40:
            if self.isFgGood:
                self.kicker.updateInGameConfidence(.01)
            else:
                self.kicker.updateInGameConfidence(-.015)
        elif yardsToFG > 40 and yardsToFG <= 45:
            if self.isFgGood:
                self.kicker.updateInGameConfidence(.015)
            else:
                self.kicker.updateInGameConfidence(-.01)
        elif yardsToFG > 45 and yardsToFG <= 50:
            if self.isFgGood:
                self.kicker.updateInGameConfidence(.015)
            else:
                self.kicker.updateInGameConfidence(-.01)
        elif yardsToFG > 50 and yardsToFG <= 55:
            if self.isFgGood:
                self.kicker.updateInGameConfidence(.015)
            else:
                self.kicker.updateInGameConfidence(-.01)
        elif yardsToFG > 55 and yardsToFG <= 60:
            if self.isFgGood:
                self.kicker.updateInGameConfidence(.02)
            else:
                self.kicker.updateInGameConfidence(-.005)
        else:
            if self.isFgGood:
                self.kicker.updateInGameConfidence(.025)
            else:
                self.kicker.updateInGameConfidence(-.005)

        self.kicker.updateInGameRating()

    def extraPointTry(self, offense: FloosTeam.Team):
        self.kicker = offense.rosterDict['k']
        assert self.kicker is not None, f"Team {offense.teamName} has no kicker in roster!"
        x = batched_randint(1,100)
        
        # Apply pressure modifier to kicker's rating for extra point attempts
        pressureModifier = self.kicker.attributes.getPressureModifier(self.game.gamePressure)
        adjustedRating = self.kicker.gameAttributes.overallRating + pressureModifier
        
        if (adjustedRating + 15) >= x:
            self.isXpGood = True
            self.kicker.addExtraPoint()
        else:
            self.kicker.addMissedExtraPoint()

        self.kicker.updateInGameRating()
    
    def calculateGapQuality(self, gapType: str, rbPower: int, rbAgility: int, blockingRating: int, defenseRunCoverage: int) -> float:
        """
        STAGE 1: Calculate how good each gap is (similar to receiver openness).
        Returns quality rating 0-100 where:
        - 0-30: Gap is stuffed/well defended
        - 30-60: Gap has moderate opening
        - 60-100: Gap is wide open
        
        Gap types:
        - 'A-gap': Inside power run (favors power, blocking critical)
        - 'B-gap': Off-tackle (balanced power/agility)
        - 'C-gap': Outside run (favors agility, speed)
        - 'bounce': Improvised outside run (high risk/reward, agility-dependent)
        """
        # Different gaps favor different attributes
        if gapType == 'A-gap':
            # Power run - heavily depends on blocking and RB power
            rbSkill = (rbPower * 1.5 + rbAgility * 0.5) / 2
            blockingImpact = 0.7  # Blocking very important
        elif gapType == 'B-gap':
            # Off-tackle - balanced run
            rbSkill = (rbPower * 1.0 + rbAgility * 1.0) / 2
            blockingImpact = 0.5  # Blocking moderately important
        elif gapType == 'C-gap':
            # Outside run - agility matters more
            rbSkill = (rbPower * 0.5 + rbAgility * 1.5) / 2
            blockingImpact = 0.4  # Blocking less critical
        else:  # bounce
            # Improvised/broken play - pure agility, risky
            rbSkill = rbAgility
            blockingImpact = 0.2  # Minimal blocking help
        
        # Calculate gap effectiveness
        offenseStrength = (rbSkill * (1 - blockingImpact)) + (blockingRating * blockingImpact)
        skillDifferential = offenseStrength - defenseRunCoverage
        
        # Mean quality shifts based on matchup
        meanQuality = 50 + (skillDifferential / 2.5)
        meanQuality = max(10, min(90, meanQuality))
        
        # Standard deviation - more variance for risky gaps
        if gapType == 'bounce':
            stdDev = 30  # High variance - boom or bust
        elif gapType == 'C-gap':
            stdDev = 20  # Moderate variance
        else:
            stdDev = 15  # Lower variance for power runs
        
        # Sample from Gaussian and clamp to 0-100
        quality = np.random.normal(meanQuality, stdDev)
        return max(0, min(100, quality))
    
    def selectRunGap(self, gapList: list, rbVision: int, rbDiscipline: int):
        """
        STAGE 2: RB finds and selects a gap based on vision and discipline.
        High vision = accurately perceives gap quality
        Low vision = distorted perception (sees gaps as better/worse than they are)
        High discipline = sticks to designed play
        Low discipline = freelances more, takes risks
        
        Returns: selected gap dict with perceived and actual quality
        """
        # Calculate how accurately RB perceives gap quality
        # High vision (85+): ±5 quality error, Medium (70-84): ±15 error, Low (<70): ±25 error
        if rbVision >= 85:
            visionErrorRange = 5
        elif rbVision >= 70:
            visionErrorRange = 15
        else:
            visionErrorRange = 25
        
        # Create perceived gaps with vision-adjusted quality
        perceivedGaps = []
        for gap in gapList:
            actualQuality = gap['quality']
            visionError = batched_randint(-visionErrorRange, visionErrorRange)
            perceivedQuality = max(0, min(100, actualQuality + visionError))
            
            perceivedGaps.append({
                'type': gap['type'],
                'quality': perceivedQuality,  # What RB thinks
                'actualQuality': actualQuality,  # What it really is
                'isDesigned': gap['isDesigned']  # Was this the called play?
            })
        
        # Sort by perceived quality
        sortedGaps = sorted(perceivedGaps, key=lambda g: g['quality'], reverse=True)
        
        # Find the designed gap
        designedGap = next((g for g in sortedGaps if g['isDesigned']), sortedGaps[0])
        bestPerceivedGap = sortedGaps[0]
        
        # Discipline determines if RB hits designed gap or reads and freelances
        if rbDiscipline >= 85:
            # Elite discipline: always hits designed gap unless it looks terrible
            if designedGap['quality'] >= 30 or batched_randint(1, 100) <= 90:
                return designedGap
            else:
                # Designed gap looks stuffed, audible to best option
                return bestPerceivedGap
        elif rbDiscipline >= 70:
            # Good discipline: usually hits designed gap, sometimes reads
            if designedGap['quality'] >= 25 or batched_randint(1, 100) <= 70:
                return designedGap
            else:
                return bestPerceivedGap
        elif rbDiscipline >= 55:
            # Average discipline: reads more often
            if designedGap['quality'] >= 40 and batched_randint(1, 100) <= 60:
                return designedGap
            else:
                return bestPerceivedGap
        else:
            # Low discipline: freelances often, goes for home runs
            if batched_randint(1, 100) <= 40:
                return designedGap
            else:
                # Tends to bounce outside looking for big play
                bounceGap = next((g for g in sortedGaps if g['type'] == 'bounce'), bestPerceivedGap)
                return bounceGap
    
    def runPlay(self):
        """
        Improved running play using multi-stage system similar to passing:
        1. Calculate quality of multiple gaps
        2. RB vision determines accuracy of gap perception
        3. RB discipline determines gap selection (designed vs audible)
        4. Execute run through selected gap
        5. Breakaway potential (second level yards)
        """
        self.playType = PlayType.Run
        self.runner = self.offense.rosterDict['rb']
        assert self.runner is not None, f"Team {self.offense.teamName} has no RB in roster!"
        blocker: FloosPlayer.PlayerTE = self.offense.rosterDict['te']
        assert blocker is not None, f"Team {self.offense.teamName} has no TE in roster!"

        # Apply pressure modifier to runner's performance
        runnerPressureMod = self.runner.attributes.getPressureModifier(self.game.gamePressure)
        
        # STAGE 1: Calculate gap quality (like receiver openness)
        # Randomly determine designed play (which gap is the call)
        designedGapType = batched_choice(['A-gap', 'B-gap', 'C-gap'])
        
        gapList = []
        for gapType in ['A-gap', 'B-gap', 'C-gap', 'bounce']:
            quality = self.calculateGapQuality(
                gapType,
                self.runner.attributes.power,
                self.runner.attributes.agility,
                blocker.attributes.blocking,
                self.defense.defenseRunCoverageRating
            )
            gapList.append({
                'type': gapType,
                'quality': quality,
                'isDesigned': (gapType == designedGapType)
            })
        
        # STAGE 2: RB selects gap based on vision and discipline
        selectedGap = self.selectRunGap(
            gapList,
            self.runner.attributes.vision,
            self.runner.attributes.discipline
        )
        
        # STAGE 3: Execute run through selected gap
        # Gap quality affects initial yards (like throw quality affects completion)
        gapQuality = selectedGap['actualQuality']  # Use actual, not perceived
        
        # Calculate offensive strength with pressure modifier
        rbPowerRating = (self.runner.attributes.power * 1.5 + 
                        self.runner.attributes.agility * 1.2 + 
                        self.runner.attributes.playMakingAbility * 0.8 +
                        self.runner.attributes.xFactor * 0.5) / 4
        
        stage1Offense = ((rbPowerRating * 0.8) + (blocker.attributes.blocking * 0.2)) + runnerPressureMod
        
        # Adjust offense rating based on gap quality
        # Good gap quality = better chance for yards
        qualityBonus = (gapQuality - 50) / 10  # -5 to +5 bonus
        adjustedOffense = stage1Offense + qualityBonus
        
        # Calculate initial burst yards using Gaussian distribution
        if self.yardsToEndzone >= 10:
            stage1MaxYards = 10
        else:
            stage1MaxYards = self.yardsToEndzone + 5
        
        stage1Yardages = np.arange(0, stage1MaxYards + 1)
        
        # Boost offensive production - division by 2.5 instead of 3.5, plus more base yards
        mean_stage1 = ((adjustedOffense - self.defense.defenseRunCoverageRating) / 2.5) + 2.5
        mean_stage1 = min(stage1MaxYards + 1, max(0, mean_stage1))
        
        relative_strength = ((adjustedOffense * 2) - self.defense.defenseRunCoverageRating) / 100
        absolute_skill = (adjustedOffense + self.defense.defenseRunCoverageRating) / 200
        std_dev_stage1 = max(1, (stage1MaxYards + 1 - 0) / 4 * (1 + relative_strength) * absolute_skill)
        
        # Create Gaussian curve for initial yards
        stage1Curve = np.exp(-((stage1Yardages - mean_stage1) ** 2) / (2 * std_dev_stage1 ** 2))
        stage1Curve /= np.sum(stage1Curve)
        
        stage1YardsGained = int(np.random.choice(stage1Yardages, p=stage1Curve))
        self.yardage = stage1YardsGained
        
        # STAGE 4: Breakaway potential (second level)
        if self.yardage < self.yardsToEndzone and stage1YardsGained >= stage1MaxYards * 0.5:
            self.runner.updateInGameConfidence(.005)
            
            # Calculate breakaway potential (speed/agility focused) - BOOSTED
            stage2Offense = ((self.runner.attributes.speed * 1.5 + 
                            self.runner.attributes.agility * 1.2 + 
                            self.runner.attributes.playMakingAbility * 0.8 +
                            self.runner.attributes.xFactor * 0.5) / 4) + runnerPressureMod
            
            offenseContribution2 = (2.0 * stage2Offense) / 100  # was 1.5
            defenseContribution = 0.2 * self.defense.defenseRunCoverageRating / 100  # was 0.3
            stage2DecayRate = round(0.06 + 0.1 * (np.exp(defenseContribution) - offenseContribution2), 3)  # was 0.08
            
            if self.yardsToEndzone >= 10:
                stage2MaxYards = 10
            else:
                stage2MaxYards = self.yardsToEndzone + 5
            
            stage2Yardages = np.arange(0, stage2MaxYards + 1)
            stage2Curve = np.exp(-stage2DecayRate * stage2Yardages)
            stage2Curve /= np.sum(stage2Curve)
            
            stage2YardsGained = int(np.random.choice(stage2Yardages, p=stage2Curve))
            self.yardage += stage2YardsGained
        
        # Fumble check
        fumbleRoll = batched_randint(1, 100)
        fumbleResist = round(((self.runner.gameAttributes.power * 0.8) + 
                             (self.runner.gameAttributes.discipline * 1.2)) / 2 + 
                            self.runner.gameAttributes.luckModifier)
        fumbleResistModifier = 0
        if fumbleResist >= 92:
            fumbleResistModifier = -2
        elif fumbleResist >= 84:
            fumbleResistModifier = -1
        elif fumbleResist >= 68 and fumbleResist <= 75:
            fumbleResistModifier = 1
        elif fumbleResist <= 67:
            fumbleResistModifier = 2
        
        if (fumbleRoll + fumbleResistModifier) > 97:
            self.isFumble = True
            runnerRecoveryMod = self.runner.attributes.getPressureModifier(self.game.gamePressure)
            if (self.defense.defenseRunCoverageRating + batched_randint(-5, 5)) >= \
               (self.runner.gameAttributes.overallRating + runnerRecoveryMod + batched_randint(-5, 5)):
                self.runner.addFumble(self.game.isRegularSeasonGame)
                self.runner.updateInGameConfidence(-.02)
                self.defense.updateInGameConfidence(.02)
                self.defense.gameDefenseStats['fumRec'] += 1
                self.isFumbleLost = True
                self.playResult = PlayResult.Fumble
        
        # Clamp yardage to endzone
        if self.yardage > self.yardsToEndzone:
            self.yardage = self.yardsToEndzone
        
        # Determine if run went out of bounds (for clock management)
        if selectedGap['type'] == 'C-gap' or selectedGap['type'] == 'bounce':
            # Outside runs more likely to go out of bounds
            oobChance = 25 if selectedGap['type'] == 'bounce' else 15
        else:
            # Inside runs rarely go out
            oobChance = 5
        
        self.isInBounds = batched_randint(1, 100) > oobChance
        
        # Update stats
        self.runner.addRushYards(self.yardage, self.game.isRegularSeasonGame)
        self.runner.addCarry(self.game.isRegularSeasonGame)
        self.defense.gameDefenseStats['runYardsAlwd'] += self.yardage
        self.defense.gameDefenseStats['totalYardsAlwd'] += self.yardage
        
        if self.yardage >= 20:
            self.runner.gameStatsDict['rushing']['20+'] += 1
        if self.yardage > self.runner.gameStatsDict['rushing']['longest']:
            self.runner.gameStatsDict['rushing']['longest'] = self.yardage
        

    def calculateSackProbability(self, defensePassRush: int, qbMobility: int, blockingModifier: int, dropbackDepth: int) -> float:
        """
        Calculate sack probability using logistic curve based on pass rush vs protection.
        Returns probability (0-100) that QB gets sacked.
        """
        # Calculate pass rush differential (defense rush vs offensive protection)
        # Boost blocking modifier impact significantly (multiply by 12)
        qbProtection = qbMobility + (blockingModifier * 12)
        rushDifferential = defensePassRush - qbProtection
        
        # Dropback depth increases sack risk (3-step=1, 5-step=2, 7-step=3)
        rushDifferential += (dropbackDepth - 1) * 2  # Reduced from 3 to 2
        
        # Base sack rate at even matchup (differential = 0) is ~2% (was 5%)
        # Logistic function: probability increases smoothly with rush advantage
        baseSackRate = 2.0
        steepness = 0.06  # Reduced from 0.10 for even gentler curve
        
        # Shift the curve so 0 differential = baseSackRate
        probability = (baseSackRate * 2) / (1 + np.exp(-steepness * rushDifferential))
        
        return max(0.5, min(15, probability))  # Reduced max from 25% to 15%, min from 1% to 0.5%
    
    def calculatePressureImpact(self, defensePassRush: int, qbAccuracy: int, blockingModifier: int) -> float:
        """
        Calculate throw quality degradation from defensive pressure.
        Returns degradation factor (0.6 to 1.0) where lower = more disruption.
        """
        # Calculate pressure differential
        qbPressureResistance = (qbAccuracy * 0.7) + blockingModifier
        pressureDifferential = defensePassRush - qbPressureResistance
        
        # Use exponential decay for degradation
        # High pressure differential = more degradation
        # Formula: 1.0 - (maxDegradation * (1 / (1 + exp(-steepness * differential))))
        maxDegradation = 0.4  # Maximum 40% quality loss
        steepness = 0.12
        
        degradationAmount = maxDegradation * (1 / (1 + np.exp(-steepness * pressureDifferential)))
        degradationFactor = 1.0 - degradationAmount
        
        return max(0.6, min(1.0, degradationFactor))  # Between 60% and 100% quality
    
    def calculateReceiverOpenness(self, receiver, defensePassCoverage: int) -> float:
        """
        Stage 1: Calculate how open a receiver is on a scale of 0-100.
        Returns openness rating where:
        - 0-30: Well covered
        - 30-60: Partially open
        - 60-100: Wide open
        """
        receiverSkill = receiver.gameAttributes.routeRunning
        
        # Create Gaussian distribution for openness based on skill differential
        skillDifferential = receiverSkill - defensePassCoverage
        
        # Mean openness shifts based on skill differential
        meanOpenness = 50 + (skillDifferential / 2)  # Range roughly 30-70
        meanOpenness = max(10, min(90, meanOpenness))  # Clamp to reasonable range
        
        # Standard deviation - better receivers have more consistent separation
        stdDev = max(10, 25 - (receiverSkill / 10))
        
        # Sample from Gaussian and clamp to 0-100
        openness = np.random.normal(meanOpenness, stdDev)
        return max(0, min(100, openness))
    
    def selectPassTarget(self, targetList: list, qbVision: int, qbDiscipline: int):
        """
        Stage 2: QB finds and selects a receiver based on vision and discipline.
        High vision = accurately perceives receiver openness
        Low vision = distorted perception (sees receivers as more/less open than they are)
        High discipline = won't throw to covered receivers
        Returns: (selectedTarget, willThrowAway)
        """
        # Calculate how accurately QB perceives openness
        # High vision (90+): ±5% error, Medium (70-89): ±15% error, Low (<70): ±25% error
        if qbVision >= 90:
            visionErrorRange = 5
        elif qbVision >= 70:
            visionErrorRange = 15
        else:
            visionErrorRange = 25
        
        # Create perceived targets with vision-adjusted openness
        perceivedTargets = []
        for target in targetList:
            actualOpenness = target['openness']
            visionError = batched_randint(-visionErrorRange, visionErrorRange)
            perceivedOpenness = max(0, min(100, actualOpenness + visionError))
            
            perceivedTargets.append({
                'receiver': target['receiver'],
                'openness': perceivedOpenness,  # What QB thinks
                'actualOpenness': actualOpenness,  # What it really is
                'route': target['route']
            })
        
        # Sort by perceived openness (what QB thinks they see)
        sortedTargets = sorted(perceivedTargets, key=lambda t: t['openness'], reverse=True)
        
        # QB makes decision based on perceived openness
        for target in sortedTargets:
            perceivedOpenness = target['openness']
            
            # Discipline check using perceived openness
            if qbDiscipline >= 90:
                # Elite discipline: only throw to open receivers (60+) or throw away
                if perceivedOpenness >= 60 or batched_randint(1, 100) <= 20:
                    return (target, False)
            elif qbDiscipline >= 75:
                # Good discipline: prefer open, sometimes throw to partial (40+)
                if perceivedOpenness >= 40 or batched_randint(1, 100) <= 30:
                    return (target, False)
            elif qbDiscipline >= 60:
                # Average discipline: will throw to most receivers
                if perceivedOpenness >= 25 or batched_randint(1, 100) <= 50:
                    return (target, False)
            else:
                # Low discipline: throws to anyone, risky
                if batched_randint(1, 100) <= 70:
                    return (target, False)
        
        # No suitable receiver found - throw away or force it
        if qbDiscipline >= 80:
            return (None, True)  # Throw away
        elif batched_randint(1, 100) <= qbDiscipline:
            return (None, True)  # Throw away based on discipline
        else:
            # Force throw to what QB thinks is least covered
            return (sortedTargets[0], False)
    
    def calculateThrowQuality(self, passType, qbAccuracy: int, qbXFactor: int, defensePassRush: int, blockingModifier: int, qbPressureMod: float) -> float:
        """
        Stage 3: Calculate throw quality (0-100) based on QB skill, pass type, and pressure.
        Higher quality = easier to catch, less likely to be intercepted
        Returns throw quality rating (0-100)
        """
        # Base accuracy from QB
        baseAccuracy = (qbAccuracy + qbXFactor) / 2 + qbPressureMod
        
        # Pass type difficulty modifier
        passTypeDifficulty = {
            PassType.short: 1.0,     # Easiest
            PassType.medium: 0.85,   # Moderate
            PassType.long: 0.7,      # Hardest
            PassType.hailMary: 0.5   # Extremely difficult
        }
        difficultyMod = passTypeDifficulty.get(passType, 0.85)
        
        # Calculate pressure impact using smooth degradation curve
        pressureDegradation = self.calculatePressureImpact(
            defensePassRush,
            qbAccuracy,
            blockingModifier
        )
        
        # Apply all modifiers
        throwQuality = baseAccuracy * difficultyMod * pressureDegradation
        
        # Add natural variance
        throwQuality += batched_randint(-10, 10)
        
        return max(5, min(100, throwQuality))
    
    def calculateCatchProbability(self, throwQuality: float, receiverHands: int, receiverOpenness: float, defensePassCoverage: int, receiverPressureMod: float) -> dict:
        """
        Stage 4: Calculate catch probability and interception risk.
        Returns: {'catchProb': float, 'intProb': float, 'dropProb': float}
        """
        adjustedHands = receiverHands + receiverPressureMod
        
        # Good throws are easier to catch
        # Openness matters more for bad throws
        if throwQuality >= 70:
            # Good throw - mostly about hands
            baseCatchProb = adjustedHands * 0.9
        elif throwQuality >= 50:
            # Decent throw - hands + openness both matter
            baseCatchProb = (adjustedHands * 0.6) + (receiverOpenness * 0.3)
        else:
            # Bad throw - need to be open AND skilled
            baseCatchProb = (adjustedHands * 0.4) + (receiverOpenness * 0.4)
        
        # Defense can contest catches on covered receivers
        defenseFactor = max(0, (100 - receiverOpenness) / 100) * (defensePassCoverage / 100)
        
        catchProb = baseCatchProb * (1 - defenseFactor * 0.5)
        
        # Interception probability (bad throws to covered receivers)
        intProb = 0
        if throwQuality < 50 and receiverOpenness < 50:
            intProb = ((50 - throwQuality) / 10) * ((50 - receiverOpenness) / 50) * (defensePassCoverage / 100) * 12
        
        # Drop probability (good throw, but receiver bobbles it)
        dropProb = max(0, (100 - baseCatchProb) * (defensePassCoverage / 200))
        
        return {
            'catchProb': min(95, max(5, catchProb)),
            'intProb': min(25, max(0, intProb)),
            'dropProb': min(30, max(0, dropProb))
        }
    
    def calculatePassYardage(self, passType, throwQuality: float) -> int:
        """
        Calculate air yards using Gaussian distribution based on pass type and throw quality.
        Better throws travel farther and more accurately.
        """
        # Base mean and std dev for each pass type - BOOSTED for better offense
        passTypeParams = {
            PassType.short: {'mean': 6.0, 'stdDev': 2.5},    # was 4.5, 2.0
            PassType.medium: {'mean': 14, 'stdDev': 4.0},    # was 11, 3.5
            PassType.long: {'mean': 25, 'stdDev': 6},        # was 20, 5
            PassType.hailMary: {'mean': 50, 'stdDev': 10}
        }
        
        params = passTypeParams.get(passType, {'mean': 11, 'stdDev': 3.5})
        
        # Adjust mean based on throw quality (better throws travel intended distance)
        qualityFactor = max(0.7, throwQuality / 70)  # was 75, now easier threshold
        adjustedMean = params['mean'] * qualityFactor
        
        # Sample from Gaussian
        airYards = int(np.random.normal(adjustedMean, params['stdDev']))
        
        return max(0, airYards)

    def passPlay(self, playKey):
        self.play = passPlayBook[playKey]
        self.playType = PlayType.Pass
        self.passer: FloosPlayer.PlayerQB = self.offense.rosterDict['qb']
        assert self.passer is not None, f"Team {self.offense.teamName} has no QB in roster!"
        self.receiver: FloosPlayer.PlayerWR = None
        self.selectedTarget = None
        self.blockingModifier = 0
        self.passType = None

        if passPlayBook[playKey]['targets']['te'] is None:
            te = self.offense.rosterDict['te']
            assert te is not None, f"Team {self.offense.teamName} has no TE in roster!"
            self.blockingModifier += te.attributes.blockingModifier
        if passPlayBook[playKey]['targets']['rb'] is None:
            rb = self.offense.rosterDict['rb']
            assert rb is not None, f"Team {self.offense.teamName} has no RB in roster!"
            self.blockingModifier += rb.attributes.blockingModifier

        # Calculate sack probability using probability curve
        qbMobility = round((self.passer.gameAttributes.agility + self.passer.gameAttributes.xFactor) / 2)
        sackProbability = self.calculateSackProbability(
            self.defense.defensePassRushRating,
            qbMobility,
            self.blockingModifier,
            passPlayBook[playKey]['dropback'].value
        )
        
        sackRoll = batched_randint(1, 100)
        if sackRoll <= sackProbability:
            # Sack yardage using exponential distribution (most 3-7 yards, occasional 10+)
            rushAdvantage = max(0, self.defense.defensePassRushRating - qbMobility) / 20
            sackYardages = np.arange(0, 16)
            sackDecayRate = max(0.3, 0.5 - rushAdvantage)  # Better rush = deeper sacks
            sackCurve = np.exp(-sackDecayRate * sackYardages)
            sackCurve /= np.sum(sackCurve)
            
            self.yardage = -int(np.random.choice(sackYardages, p=sackCurve))
            self.defense.gameDefenseStats['sacks'] += 1
            self.isSack = True
            fumbleRoll = batched_randint(1,100)
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
                if (self.defense.defensePassRushRating + batched_randint(-5,5)) >= (self.passer.gameAttributes.power + self.passer.gameAttributes.luckModifier + batched_randint(-5,5)):
                    self.passer.updateInGameConfidence(-.02)
                    self.defense.updateInGameConfidence(.02)
                    self.defense.gameDefenseStats['fumRec'] += 1
                    self.isFumbleLost = True
                    self.playResult = PlayResult.Fumble
        else:
            self.passer.addPassAttempt(self.game.isRegularSeasonGame)
            targets:dict = passPlayBook[playKey]['targets']
            targetList = []
            
            # STAGE 1: Calculate receiver openness (0-100 scale)
            for key in targets.keys():
                if targets[key] is not None:
                    receiver = self.offense.rosterDict[key]
                    openness = self.calculateReceiverOpenness(receiver, self.defense.defensePassCoverageRating)
                    receiverStatusDict = {
                        'receiver': receiver,
                        'openness': openness,
                        'route': targets[key]
                    }
                    targetList.append(receiverStatusDict)
            
            # STAGE 2: QB selects target based on vision and discipline
            selectedTarget, willThrowAway = self.selectPassTarget(
                targetList,
                self.passer.attributes.vision,
                self.passer.gameAttributes.discipline
            )
            
            if willThrowAway or selectedTarget is None:
                self.passType = PassType.throwAway
                self.receiver = None
            else:
                self.selectedTarget = selectedTarget
                self.receiver = selectedTarget['receiver']
                self.passType = selectedTarget['route']
            
            # Handle throw away
            if self.passType == PassType.throwAway:
                self.yardage = 0
                self.passer.addMissedPass(self.game.isRegularSeasonGame)
            else:
                # Apply pressure modifiers
                qbPressureMod = self.passer.attributes.getPressureModifier(self.game.gamePressure)
                receiverPressureMod = self.receiver.attributes.getPressureModifier(self.game.gamePressure)
                
                # STAGE 3: Calculate throw quality
                throwQuality = self.calculateThrowQuality(
                    self.passType,
                    self.passer.gameAttributes.accuracy,
                    self.passer.gameAttributes.xFactor,
                    self.defense.defensePassRushRating,
                    self.blockingModifier,
                    qbPressureMod
                )
                
                # STAGE 4: Calculate catch probability and outcome
                catchProbs = self.calculateCatchProbability(
                    throwQuality,
                    self.receiver.gameAttributes.hands,
                    self.selectedTarget['openness'],
                    self.defense.defensePassCoverageRating,
                    receiverPressureMod
                )
                
                # Roll for outcome
                outcomeRoll = batched_randint(1, 100)
                
                # Check for interception first (bad throw to covered receiver)
                if outcomeRoll <= catchProbs['intProb']:
                    self.yardage = randint(-5, 10)
                    self.passer.addInterception(self.game.isRegularSeasonGame)
                    self.passer.addMissedPass(self.game.isRegularSeasonGame)
                    self.passer.updateInGameConfidence(-.02)
                    self.defense.updateInGameConfidence(.02)
                    self.defense.gameDefenseStats['ints'] += 1
                    self.isInterception = True
                    self.playResult = PlayResult.Interception
                # Check for catch
                elif outcomeRoll <= (catchProbs['intProb'] + catchProbs['catchProb']):
                    # COMPLETION!
                    self.receiver.addRcvPassTarget(self.game.isRegularSeasonGame)
                    
                    # Calculate air yards based on throw quality
                    passYards = self.calculatePassYardage(self.passType, throwQuality)
                    passYards = min(passYards, self.yardsToEndzone)
                    
                    # STAGE 5: Calculate YAC (similar to running play breakaway)
                    yac = 0
                    if passYards < self.yardsToEndzone:
                        receiverYACRating = (self.receiver.gameAttributes.agility + 
                                           self.receiver.gameAttributes.speed + 
                                           self.receiver.gameAttributes.playMakingAbility) / 3
                        
                        # YAC potential based on field position
                        yacMaxYards = min(15, self.yardsToEndzone - passYards)
                        
                        if yacMaxYards > 0:
                            yacYardages = np.arange(0, yacMaxYards + 1)
                            
                            # YAC decay rate based on receiver vs defense - BOOSTED
                            yacOffense = receiverYACRating + receiverPressureMod
                            yacDefense = self.defense.defensePassCoverageRating
                            offenseContribution = (2.0 * yacOffense) / 100  # was 1.5
                            defenseContribution = 0.2 * yacDefense / 100    # was 0.3
                            yacDecayRate = round(0.08 + 0.1 * (np.exp(defenseContribution) - offenseContribution), 3)  # was 0.12
                            
                            # Exponential decay curve for YAC
                            yacCurve = np.exp(-yacDecayRate * yacYardages)
                            yacCurve /= np.sum(yacCurve)
                            
                            yac = int(np.random.choice(yacYardages, p=yacCurve))
                    
                    self.yardage = passYards + yac
                    if self.yardage > self.yardsToEndzone:
                        yac = self.yardsToEndzone - passYards
                        self.yardage = self.yardsToEndzone
                    
                    # Determine if receiver went out of bounds (for clock management)
                    # Longer passes and sideline routes more likely to go OOB
                    if self.passType == PassType.short:
                        oobChance = 10
                    elif self.passType == PassType.medium:
                        oobChance = 20
                    elif self.passType == PassType.long:
                        oobChance = 30  # Deep sideline shots
                    else:
                        oobChance = 15
                    
                    self.isInBounds = batched_randint(1, 100) > oobChance
                    
                    # Update stats
                    self.passer.addPassYards(self.yardage, self.game.isRegularSeasonGame)
                    self.passer.addCompletion(self.game.isRegularSeasonGame)
                    self.receiver.addReception(self.game.isRegularSeasonGame)
                    self.receiver.addReceiveYards(self.yardage, self.game.isRegularSeasonGame)
                    self.receiver.addYAC(yac, self.game.isRegularSeasonGame)
                    self.defense.gameDefenseStats['passYardsAlwd'] += self.yardage
                    self.defense.gameDefenseStats['totalYardsAlwd'] += self.yardage
                    
                    # Confidence boosts based on play quality
                    confBoost = 0.005 if throwQuality >= 70 else 0.003
                    self.passer.updateInGameConfidence(confBoost)
                    self.receiver.updateInGameConfidence(confBoost)
                    self.defense.updateInGameConfidence(-confBoost)
                    self.isPassCompletion = True
                    
                    # Track long completions
                    if self.yardage >= 20:
                        self.passer.gameStatsDict['passing']['20+'] += 1
                        self.receiver.gameStatsDict['receiving']['20+'] += 1
                    if self.yardage > self.passer.gameStatsDict['passing']['longest']:
                        self.passer.gameStatsDict['passing']['longest'] = self.yardage
                    if self.yardage > self.receiver.gameStatsDict['receiving']['longest']:
                        self.receiver.gameStatsDict['receiving']['longest'] = self.yardage
                
                # Check for drop
                elif outcomeRoll <= (catchProbs['intProb'] + catchProbs['catchProb'] + catchProbs['dropProb']):
                    # DROPPED PASS
                    self.receiver.addRcvPassTarget(self.game.isRegularSeasonGame)
                    self.receiver.addPassDrop(self.game.isRegularSeasonGame)
                    self.receiver.updateInGameConfidence(-.005)
                    self.defense.updateInGameConfidence(.005)
                    self.passIsDropped = True
                    self.yardage = 0
                
                else:
                    # INCOMPLETE (missed throw)
                    self.passer.addMissedPass(self.game.isRegularSeasonGame)
                    self.defense.updateInGameConfidence(.003)
                    self.passer.updateInGameConfidence(-.003)
                    self.yardage = 0

