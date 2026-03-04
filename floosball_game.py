import enum
import logging
import random as _random
from random import randint
from random_batch import batched_randint, batched_random, batched_choice
import copy
from stats_optimization import get_optimized_stats
import asyncio
import math
import statistics
from random import choice
from time import sleep
import floosball_player as FloosPlayer
import floosball_team as FloosTeam
import floosball_methods as FloosMethods

# WebSocket broadcasting support (optional)
try:
    from api.game_broadcaster import broadcaster
    from api.event_models import GameEvent, PlayerEvent
    BROADCASTING_AVAILABLE = True
except ImportError:
    BROADCASTING_AVAILABLE = False
    broadcaster = None
    GameEvent = None
    PlayerEvent = None
import datetime
import numpy as np
import matplotlib.pyplot as plt
from constants import (
    GAME_MAX_PLAYS, PLAYS_TO_FOURTH_QUARTER, PLAYS_TO_THIRD_QUARTER,
    RATING_SCALE_MIN, RATING_RANGE, PERCENTAGE_MULTIPLIER, FIELD_LENGTH,
    PRESSURE_BASE, PRESSURE_MAX_ADDITIONAL, PRESSURE_CALCULATION_DIVISOR,
    QUARTER_SECONDS, KNEEL_DRAIN_SECONDS, SPIKE_CLOCK_THRESHOLD,
    TIMEOUT_CLOCK_THRESHOLD, FG_SNAP_DISTANCE, YARDS_TO_FIRST_DOWN,
    CLOSE_GAME_SCORE_THRESHOLD, RECEIVER_MATCHUP_SCALE,
    COACH_ATTR_NEUTRAL, COACH_ATTR_RANGE, COACH_OFFENSIVE_MIND_FLOOR,
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

try:
    from gameplan import (generateOffensiveGameplan, generateDefensiveGameplan, getDefensiveScheme,
                          adjustOffensiveGameplan, adjustDefensiveGameplan)
    GAMEPLAN_AVAILABLE = True
except ImportError:
    GAMEPLAN_AVAILABLE = False
    generateOffensiveGameplan = None
    generateDefensiveGameplan = None
    getDefensiveScheme = None


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
    Touchdown2PtGood = 'Touchdown, 2-Pt Good'
    Touchdown2PtNoGood = 'Touchdown, 2-Pt No Good'
    Safety = 'Safety'
    Fumble = 'Fumble'
    Interception = 'Interception'


shortRunList =  [
                    'runs',
                    'dives',
                    'dashes',
                    'plunges',
                    'powers ahead',
                    'squeezes through',
                    'churns ahead',
                    'falls forward',
                    'fights for',
                    'sneaks through',
                    'punches it through',
                    'muscles ahead',
                ]

midRunList =    [
                    'runs',
                    'races',
                    'rumbles',
                    'breaks through',
                    'busts through',
                    'powers through',
                    'cuts through',
                    'slices through',
                    'barrels through',
                    'plows through',
                    'grinds for',
                    'charges for',
                    'bounces outside for',
                    'finds a crease for',
                    'threads the gap for',
                    'drags defenders for',
                ]

longRunList =   [
                    'runs',
                    'streaks',
                    'explodes',
                    'sprints',
                    'races',
                    'breaks out',
                    'busts out',
                    'breaks free for',
                    'rips off',
                    'blazes through for',
                    'gallops for',
                    'goes untouched for',
                    'turns on the jets for',
                    'hits the open field for',
                    'bolts for',
                    'takes off for',
                    'outruns the defense for',
                ]

lossRunList =   [
                    'is stuffed',
                    'is stopped',
                    'is dropped',
                    'is tackled in the backfield',
                    'is brought down',
                    'is swallowed up',
                    'is wrapped up',
                    'is stopped cold',
                    'is smothered',
                    'is stonewalled',
                    'is met at the line',
                ]

shortPassList = [
                    'quick pass to',
                    'short pass to',
                    'tosses to',
                    'passes to',
                    'screen pass to',
                    'dumps it off to',
                    'checks down to',
                    'flips a pass to',
                    'slips a pass to',
                    'hits',
                    'connects with',
                    'delivers a quick strike to',
                    'lays it off to',
                    'zips a quick one to',
                    'fires a short one to',
                ]

midPassList =   [
                    'zips a pass to',
                    'fires a pass to',
                    'passes to',
                    'throws to',
                    'finds',
                    'hits',
                    'connects with',
                    'delivers to',
                    'threads a pass to',
                    'drills it to',
                    'drops it in to',
                    'lasers one to',
                    'hooks up with',
                    'puts it on',
                    'fires a strike to',
                    'dials it up for',
                ]

longPassList = [
                    'passes to',
                    'long throw to',
                    'rifles a pass to',
                    'lobs a pass to',
                    'launches a deep ball to',
                    'bombs it to',
                    'goes deep to',
                    'uncorks a long pass to',
                    'slings it downfield to',
                    'airs it out to',
                    'hurls it to',
                    'connects deep with',
                    'puts it up for',
                    'throws deep to',
                ]

extraLongPassList = [
                    'heaves it to',
                    'throws a prayer to',
                    'throws a Hail Mary to',
                    'deep pass to',
                    'throws it deep to',
                    'launches a desperation heave to',
                    'hurls a bomb to',
                    'flings it with everything to',
                    'heaves a prayer downfield to',
                    'launches it skyward to',
                    'lets it fly to',
                    'chucks it into the end zone to',
                ]

# Sack text — args: (passer.name, yardage)
sackList = [
                    '{} sacked for {} yards',
                    '{} is brought down for {} yards',
                    '{} goes down, sacked for {} yards',
                    '{} is taken down behind the line for {} yards',
                    '{} has nowhere to throw, sacked for {} yards',
                    '{} is wrapped up and sacked for {} yards',
                    '{} is crushed for {} yards',
                    '{} is buried for {} yards',
                ]

# Short incomplete — args: (passer.name, receiver.name)
shortIncompleteList = [
                    '{} short pass to {} incomplete',
                    '{} fires short for {}, incomplete',
                    '{} and {} can\'t connect, incomplete',
                    '{} overthrows {} on the short route, incomplete',
                    '{} short toss to {}, out of reach',
                    '{} misses {} underneath, falls incomplete',
                ]

# Short dropped — args: (passer.name, receiver.name)
shortDropList = [
                    '{} short pass dropped by {}',
                    '{} hits {} in the hands, dropped',
                    '{} short toss dropped by {}',
                    '{} finds {}, but it slips through the hands',
                    '{} and {} with the drop, incomplete',
                    '{} puts it right on {}, can\'t hold on',
                ]

# Medium incomplete — args: (passer.name, receiver.name)
midIncompleteList = [
                    '{} pass to {} incomplete',
                    '{} fires for {}, falls incomplete',
                    '{} and {} can\'t connect, incomplete',
                    '{} throws for {}, out of reach',
                    '{} misses {} on the route, incomplete',
                    '{} can\'t find {} in coverage, incomplete',
                    '{} under pressure, overthrows {}, incomplete',
                ]

# Medium dropped — args: (passer.name, receiver.name)
midDropList = [
                    '{} pass dropped by {}',
                    '{} hits {} on the break, dropped',
                    '{} finds {}, but it\'s a drop',
                    '{} and {} with the miscommunication, incomplete',
                    '{} puts it on {}, let it go, incomplete',
                ]

# Deep incomplete — args: (passer.name, receiver.name)
deepIncompleteList = [
                    '{} deep pass to {} incomplete',
                    '{} goes deep for {}, can\'t connect',
                    '{} launches it for {}, overthrown',
                    '{} and {} can\'t hook up downfield, incomplete',
                    '{} heaves it for {}, well covered, incomplete',
                    '{} throws deep for {}, out of bounds',
                    '{} airs it out for {}, no good',
                ]

# Deep dropped — args: (passer.name, receiver.name)
deepDropList = [
                    '{} deep pass dropped by {}',
                    '{} hits {} in stride, drops it',
                    '{} finds {} deep, but it\'s dropped',
                    '{} deep shot for {}, can\'t hold on',
                    '{} puts it perfectly for {}, drops it, incomplete',
                ]

# Interception — args: (passer.name, defense.abbr)
interceptionList = [
                    '{} pass intercepted by {}',
                    '{} picked off by {}',
                    '{} throws right into coverage, {} intercepts',
                    'Turnover! {} picked off by {}',
                    '{} and the ball is picked off by {}',
                    '{} throws a pick, {} takes it',
                    '{} telegraphs it, {} with the interception',
                ]

# Throw away — args: (passer.name,)
throwAwayList = [
                    '{} throws the ball away, incomplete',
                    '{} senses pressure and throws it away',
                    '{} can\'t find anyone, throws it out of bounds',
                    '{} discards it, incomplete',
                    '{} escapes pressure and dumps it out of bounds',
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
                            'wr2': None,
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
                            'wr2': PassType.short,
                            'te': None,
                            'rb': None
                        }
                    },
                    'Play11': {
                        'dropback': QbDropback.short,
                        'targets': {
                            'wr1': None,
                            'wr2': None,
                            'te': PassType.short,
                            'rb': None
                        }
                    },
                    'Play12': {
                        'dropback': QbDropback.short,
                        'targets': {
                            'wr1': PassType.short,
                            'wr2': None,
                            'te': None,
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
                    },
                    'Play14': {
                        'dropback': QbDropback.short,
                        'targets': {
                            'wr1': PassType.short,
                            'wr2': PassType.short,
                            'te': None,
                            'rb': None
                        }
                    },
                    'Play15': {
                        'dropback': QbDropback.medium,
                        'targets': {
                            'wr1': PassType.medium,
                            'wr2': None,
                            'te': None,
                            'rb': None
                        }
                    },
                    'Play16': {
                        'dropback': QbDropback.medium,
                        'targets': {
                            'wr1': None,
                            'wr2': PassType.medium,
                            'te': None,
                            'rb': None
                        }
                    },
                    'Play17': {
                        'dropback': QbDropback.medium,
                        'targets': {
                            'wr1': PassType.medium,
                            'wr2': None,
                            'te': PassType.short,
                            'rb': None
                        }
                    },
                    'Play18': {
                        'dropback': QbDropback.long,
                        'targets': {
                            'wr1': PassType.long,
                            'wr2': None,
                            'te': None,
                            'rb': None
                        }
                    },
                    'Play19': {
                        'dropback': QbDropback.long,
                        'targets': {
                            'wr1': None,
                            'wr2': PassType.long,
                            'te': PassType.medium,
                            'rb': None
                        }
                    },
                    'Play20': {
                        'dropback': QbDropback.long,
                        'targets': {
                            'wr1': PassType.medium,
                            'wr2': None,
                            'te': PassType.medium,
                            'rb': None
                        }
                    },
                }

def returnShortPassPlay():
    return choice(['Play8', 'Play10', 'Play11', 'Play12', 'Play14'])

def returnMediumPassPlay():
    return choice(['Play3', 'Play6', 'Play7', 'Play13', 'Play15', 'Play16', 'Play17'])

def returnLongPassPlay():
    return choice(['Play1', 'Play2', 'Play4', 'Play5', 'Play18', 'Play19', 'Play20'])
    
class Game:
    def __init__(self, homeTeam, awayTeam, timingManager=None):
        self.id = None  # Integer ID assigned by SeasonManager
        self.seasonNumber = None  # Which season this game belongs to
        self.week = None  # Week number for regular season
        self.playoffRound = None  # Round number for playoffs (1=wildcard, 2=divisional, etc.)
        self.gameType = 'regular'  # 'regular' or 'playoff'
        self.gameNumber = None  # Game number within the week/round
        self.status = None
        self.homeTeam : FloosTeam.Team = homeTeam
        self.awayTeam : FloosTeam.Team = awayTeam
        self.awayScore = 0
        self.homeScore = 0
        
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
        self.home3rdDownAtt = 0
        self.home3rdDownConv = 0
        self.away3rdDownAtt = 0
        self.away3rdDownConv = 0
        self.home4thDownAtt = 0
        self.home4thDownConv = 0
        self.away4thDownAtt = 0
        self.away4thDownConv = 0
        self.homeTurnoversTotal = 0
        self.awayTurnoversTotal = 0

        # First-half tracking for halftime gameplan adjustments
        self.homeHalfRunPlays = 0
        self.homeHalfRunYards = 0
        self.homeHalfPassAttempts = 0
        self.homeHalfPassYards = 0
        self.awayHalfRunPlays = 0
        self.awayHalfRunYards = 0
        self.awayHalfPassAttempts = 0
        self.awayHalfPassYards = 0

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
        self.homeTeamElo = getattr(homeTeam, 'elo', 1500) if homeTeam else 1500
        self.awayTeamElo = getattr(awayTeam, 'elo', 1500) if awayTeam else 1500
        
        # Calculate initial win probabilities based on ELO
        if self.homeTeamElo is not None and self.awayTeamElo is not None:
            self.homeTeamWinProbability = FloosMethods.calculateProbability(self.awayTeamElo, self.homeTeamElo) * 100
            self.awayTeamWinProbability = FloosMethods.calculateProbability(self.homeTeamElo, self.awayTeamElo) * 100
        else:
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
        self.otFirstPossTeam = None             # Team that received ball from OT coin flip
        self.otFirstPossComplete = False        # True once first team's OT possession ends
        self.otSecondPossComplete = False       # True once second team's OT possession ends
        self.startTime: datetime.datetime = None
        self.isTwoPtConv = False
        self.isOnsideKick = False
        self.gamePressure = 0

        # Coaching gameplans (pre-game scouting, generated once per game)
        if GAMEPLAN_AVAILABLE:
            self.homeOffGameplan = generateOffensiveGameplan(
                getattr(homeTeam, 'coach', None), homeTeam, awayTeam)
            self.awayOffGameplan = generateOffensiveGameplan(
                getattr(awayTeam, 'coach', None), awayTeam, homeTeam)
            self.homeDefGameplan = generateDefensiveGameplan(
                getattr(homeTeam, 'coach', None), homeTeam, awayTeam)
            self.awayDefGameplan = generateDefensiveGameplan(
                getattr(awayTeam, 'coach', None), awayTeam, homeTeam)
        else:
            self.homeOffGameplan = self.awayOffGameplan = None
            self.homeDefGameplan = self.awayDefGameplan = None

    def getDisplayId(self) -> str:
        """
        Generate a human-readable display ID for logs/UI
        Format: s1w5g3 (season 1, week 5, game 3) or s1r2g1 (season 1, playoff round 2, game 1)
        """
        if self.gameType == 'playoff':
            return f"s{self.seasonNumber}r{self.playoffRound}g{self.gameNumber}"
        else:
            return f"s{self.seasonNumber}w{self.week}g{self.gameNumber}"

    def _collect_player_stats_for_broadcast(self, team):
        """Collect player stats from a team in format ready for WebSocket broadcast"""
        player_stats = []
        
        for pos, player in team.rosterDict.items():
            player: FloosPlayer.Player
            
            stats = {
                'playerId': str(player.id),
                'playerName': player.name,
                'position': player.position.name,
                'team': team.name,
            }
            
            # Add passing stats if applicable
            if player.gameStatsDict['passing']['att'] > 0:
                stats['passingAttempts'] = player.gameStatsDict['passing']['att']
                stats['passingCompletions'] = player.gameStatsDict['passing']['comp']
                stats['passingYards'] = player.gameStatsDict['passing']['yards']
                stats['passingTouchdowns'] = player.gameStatsDict['passing']['tds']
                stats['interceptions'] = player.gameStatsDict['passing']['ints']
            
            # Add rushing stats if applicable
            if player.gameStatsDict['rushing']['carries'] > 0:
                stats['rushingAttempts'] = player.gameStatsDict['rushing']['carries']
                stats['rushingYards'] = player.gameStatsDict['rushing']['yards']
                stats['rushingTouchdowns'] = player.gameStatsDict['rushing']['tds']
            
            # Add receiving stats if applicable
            if player.gameStatsDict['receiving']['targets'] > 0:
                stats['targets'] = player.gameStatsDict['receiving']['targets']
                stats['receptions'] = player.gameStatsDict['receiving']['receptions']
                stats['receivingYards'] = player.gameStatsDict['receiving']['yards']
                stats['receivingTouchdowns'] = player.gameStatsDict['receiving']['tds']
            
            # Add kicking stats if applicable
            if player.position == FloosPlayer.Position.K:
                stats['fieldGoalsAttempted'] = player.gameStatsDict['kicking']['fgAtt']
                stats['fieldGoalsMade'] = player.gameStatsDict['kicking']['fgs']
                stats['extraPointsAttempted'] = player.gameStatsDict['kicking']['xpAtt']
                stats['extraPointsMade'] = player.gameStatsDict['kicking']['xps']
            
            # Only include players who have stats
            if len(stats) > 4:  # More than just base fields (playerId, playerName, position, team)
                player_stats.append(stats)
        
        return player_stats
    
    def _collect_team_stats_for_broadcast(self, team, is_home=True):
        """Collect team-level stats for WebSocket broadcast"""
        # Calculate total yards
        pass_yards = 0
        rush_yards = 0
        
        for player in team.rosterDict.values():
            pass_yards += player.gameStatsDict['passing']['yards']
            rush_yards += player.gameStatsDict['rushing']['yards']
        
        total_yards = pass_yards + rush_yards
        turnovers = self.homeTurnoversTotal if is_home else self.awayTurnoversTotal
        total_plays = self.homePlaysTotal if is_home else self.awayPlaysTotal
        first_downs = self.home1stDownsTotal if is_home else self.away1stDownsTotal
        sacks = team.gameDefenseStats.get('sacks', 0)
        
        return {
            'teamId': str(team.id),
            'teamName': team.name,
            'totalYards': total_yards,
            'passingYards': pass_yards,
            'rushingYards': rush_yards,
            'turnovers': turnovers,
            'timeOfPossession': '0:00',  # TODO: Track actual time of possession
            'thirdDownConversions': '0/0',  # TODO: Track third down conversions
            'fourthDownConversions': '0/0',  # TODO: Track fourth down conversions
            'penalties': 0,  # TODO: Track penalties
            'penaltyYards': 0,  # TODO: Track penalty yards
            'totalPlays': total_plays,
            'firstDowns': first_downs,
            'sacks': sacks
        }

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
            playerDict['ratingStars'] = round((((player.playerRating - 60)/40)*4)+1)
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
            playerDict['ratingStars'] = round((((player.playerRating - 60)/40)*4)+1)
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
            playerDict['ratingStars'] = round((((player.playerRating - 60)/40)*4)+1)
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
            playerDict['ratingStars'] = round((((player.playerRating - 60)/40)*4)+1)
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


    def _callTimeout(self, isHome: bool):
        """Decrement a timeout, stop the clock, and log the event to the game feed."""
        if isHome:
            self.homeTimeoutsRemaining = max(0, self.homeTimeoutsRemaining - 1)
        else:
            self.awayTimeoutsRemaining = max(0, self.awayTimeoutsRemaining - 1)
        self.clockRunning = False
        self.gameFeed.insert(0, {'event': {
            'text': f'{self.offensiveTeam.name} calls timeout',
            'quarter': self.currentQuarter,
            'timeRemaining': self.formatTime(self.gameClockSeconds),
        }})

    def _runPassBias(self, gameplan) -> int:
        """Map runPassRatio (0.25–0.75) to threshold offset (-2 to +2) for batched_randint(1,10)."""
        if gameplan is None:
            return 0
        return round((gameplan.runPassRatio - 0.5) * 8)

    def _otPlayCaller(self, scoreDiff: int):
        """Handle play calling in overtime (Q5). Called only when currentQuarter == 5."""
        if self.down == 4:
            kicker = self.offensiveTeam.rosterDict.get('k')
            kickerMaxFg = (kicker.maxFgDistance - FG_SNAP_DISTANCE) if kicker else 0
            if self.yardsToEndzone <= kickerMaxFg:
                self.play.playType = PlayType.FieldGoal
                return

            if self.homeScore == self.awayScore:
                if self.yardsToFirstDown <= 3:
                    x = batched_randint(1, 2)
                    if x == 1:
                        self.play.runPlay()
                    else:
                        self.play.passPlay(self._selectPassPlay('short'))
                    return
                elif self.yardsToFirstDown <= 7:
                    self.play.passPlay(self._selectPassPlay('medium'))
                    return
                elif self.yardsToFirstDown <= 15:
                    self.play.passPlay(self._selectPassPlay('long'))
                    return
                else:
                    if self.yardsToSafety < 15:
                        self.play.playType = PlayType.Punt
                        return
                    else:
                        self.play.passPlay(self._selectPassPlay('long'))
                        return

            elif scoreDiff > 0:
                if self.yardsToFirstDown <= 2:
                    self.play.passPlay(self._selectPassPlay('short'))
                    return
                elif self.yardsToFirstDown <= 8:
                    self.play.passPlay(self._selectPassPlay('medium'))
                    return
                else:
                    self.play.passPlay(self._selectPassPlay('long'))
                    return
            else:
                if self.yardsToFirstDown <= 10:
                    self.play.passPlay(self._selectPassPlay('medium'))
                    return
                else:
                    self.play.passPlay(self._selectPassPlay('long'))
                    return

        # Downs 1–3 in OT: use weighted sampling
        coach = getattr(self.offensiveTeam, 'coach', None)
        weights = self._computePlayWeights(scoreDiff, coach)
        self._executeWeightedPlay(weights)

    def _fourthDownCaller(self, scoreDiff: int, coach, isHome: bool):
        """Handle 4th down play calling."""
        if self.yardsToSafety <= 35:
            self.play.playType = PlayType.Punt
            return

        kicker = self.offensiveTeam.rosterDict.get('k')
        kickerMaxDistance = (kicker.maxFgDistance - FG_SNAP_DISTANCE) if kicker else 0
        inFieldGoalRange = self.yardsToEndzone <= kickerMaxDistance

        aggrNorm = (coach.aggressiveness - COACH_ATTR_NEUTRAL) / COACH_ATTR_RANGE if coach else 0.0
        goForItThreshold = max(1, min(9, round(4 + aggrNorm * 3)))

        if scoreDiff > 0:
            if self.currentQuarter == 4 and self.gameClockSeconds < 300:
                if inFieldGoalRange and self.yardsToEndzone <= 40:
                    self.play.playType = PlayType.FieldGoal
                    return
                if self.yardsToFirstDown <= 1 and self.yardsToSafety > 50:
                    x = batched_randint(1, 10)
                    if x <= goForItThreshold:
                        self.play.runPlay()
                        return
                self.play.playType = PlayType.Punt
                return

            if inFieldGoalRange and self.yardsToEndzone <= 35:
                self.play.playType = PlayType.FieldGoal
                return
            if self.yardsToFirstDown == 1 and self.yardsToSafety > 45:
                x = batched_randint(1, 10)
                if x <= max(1, min(9, round(3 + aggrNorm * 3))):
                    self.play.runPlay()
                    return
            self.play.playType = PlayType.Punt
            return

        elif scoreDiff < 0 and inFieldGoalRange:
            if self.yardsToEndzone <= 25:
                self.play.playType = PlayType.FieldGoal
                return
            elif self.currentQuarter >= 3:
                x = batched_randint(1, 10)
                if x <= 9:
                    self.play.playType = PlayType.FieldGoal
                    return
                self.play.passPlay(self._selectPassPlay('medium'))
                return
            else:
                x = batched_randint(1, 10)
                if x <= 7:
                    self.play.playType = PlayType.FieldGoal
                    return
                self.play.passPlay(self._selectPassPlay('medium'))
                return

        elif scoreDiff < 0:
            deficit = abs(scoreDiff)
            if self.currentQuarter == 4:
                if deficit <= 8:
                    if self.yardsToFirstDown <= 3:
                        self.play.passPlay(self._selectPassPlay('short'))
                        return
                    elif self.yardsToFirstDown <= 8:
                        self.play.passPlay(self._selectPassPlay('medium'))
                        return
                    else:
                        self.play.passPlay(self._selectPassPlay('long'))
                        return
                elif deficit <= 16 and self.gameClockSeconds < 480:
                    if self.yardsToFirstDown <= 3:
                        self.play.passPlay(self._selectPassPlay('short'))
                        return
                    elif self.yardsToFirstDown <= 8:
                        x = batched_randint(1, 10)
                        if x <= 8:
                            self.play.passPlay(self._selectPassPlay('medium'))
                            return
                    else:
                        x = batched_randint(1, 10)
                        if x <= 6:
                            self.play.passPlay(self._selectPassPlay('long'))
                            return
                elif deficit > 16 and self.gameClockSeconds < 300:
                    self.play.passPlay(self._selectPassPlay('long'))
                    return
            elif self.currentQuarter == 3 and deficit <= 8 and self.yardsToFirstDown <= 2:
                self.play.passPlay(self._selectPassPlay('short'))
                return
            self.play.playType = PlayType.Punt
            return

        elif self.yardsToEndzone <= 5 and inFieldGoalRange:
            x = batched_randint(1, 10)
            if x < 7:
                self.play.playType = PlayType.FieldGoal
                return
            else:
                y = batched_randint(1, 10)
                if y < 6:
                    self.play.runPlay()
                    return
                elif y < 9:
                    self.play.passPlay(self._selectPassPlay('short'))
                    return
                else:
                    self.play.passPlay(self._selectPassPlay('medium'))
                    return

        elif self.yardsToEndzone <= 20 and inFieldGoalRange:
            if self.yardsToFirstDown <= 1:
                x = batched_randint(1, 10)
                if x >= 7:
                    y = randint(1, 3)
                    if y == 1:
                        self.play.runPlay()
                        return
                    else:
                        self.play.passPlay(self._selectPassPlay('short'))
                        return
            self.play.playType = PlayType.FieldGoal
            return

        elif self.yardsToEndzone <= 35 and inFieldGoalRange:
            if self.yardsToFirstDown <= 2:
                x = batched_randint(1, 10)
                if x <= 7:
                    self.play.playType = PlayType.FieldGoal
                    return
                else:
                    y = randint(1, 3)
                    if y == 1:
                        self.play.runPlay()
                        return
                    else:
                        self.play.passPlay(self._selectPassPlay('short'))
                        return
            else:
                x = batched_randint(1, 100)
                if x <= 85:
                    self.play.playType = PlayType.FieldGoal
                    return
                else:
                    self.play.passPlay(self._selectPassPlay('medium'))
                    return

        elif inFieldGoalRange:
            x = batched_randint(1, 10)
            if x <= 7:
                self.play.playType = PlayType.FieldGoal
                return
            else:
                self.play.playType = PlayType.Punt
                return

        else:
            if self.yardsToFirstDown == 1:
                if self.yardsToSafety > 50 or (scoreDiff < -14 and self.currentQuarter >= 3):
                    x = batched_randint(1, 10)
                    if x <= 3:
                        self.play.runPlay()
                        return
                self.play.playType = PlayType.Punt
                return
            elif self.yardsToFirstDown == 2:
                if scoreDiff < -21 and self.currentQuarter == 4 and self.gameClockSeconds < 600:
                    x = batched_randint(1, 10)
                    if x <= 2:
                        self.play.passPlay(self._selectPassPlay('short'))
                        return
                self.play.playType = PlayType.Punt
                return
            else:
                if scoreDiff < -17 and self.currentQuarter == 4 and self.gameClockSeconds < 300:
                    x = batched_randint(1, 100)
                    if x <= 10:
                        self.play.passPlay(self._selectPassPlay('medium'))
                        return
                self.play.playType = PlayType.Punt
                return

    def _computePlayWeights(self, scoreDiff: int, coach) -> dict:
        """Compute play call probability weights for downs 1–3."""
        ytg = self.yardsToFirstDown
        if self.down == 1:
            weights = {'run': 40.0, 'short': 25.0, 'medium': 20.0, 'long': 15.0}
        elif self.down == 2:
            if ytg <= 4:
                weights = {'run': 55.0, 'short': 30.0, 'medium': 10.0, 'long': 5.0}
            elif ytg <= 9:
                weights = {'run': 35.0, 'short': 20.0, 'medium': 30.0, 'long': 15.0}
            else:
                weights = {'run': 20.0, 'short': 20.0, 'medium': 30.0, 'long': 30.0}
        else:  # down == 3
            if ytg <= 3:
                weights = {'run': 55.0, 'short': 35.0, 'medium': 5.0, 'long': 5.0}
            elif ytg <= 5:
                weights = {'run': 20.0, 'short': 45.0, 'medium': 25.0, 'long': 10.0}
            elif ytg <= 12:
                weights = {'run': 10.0, 'short': 15.0, 'medium': 50.0, 'long': 25.0}
            else:
                weights = {'run': 5.0, 'short': 10.0, 'medium': 15.0, 'long': 70.0}

        weights = self._applySituationalMods(weights, scoreDiff)
        weights = self._applyMatchupMods(weights, coach)
        weights = self._applyCoachMods(weights, coach)
        return weights

    def _applySituationalMods(self, weights: dict, scoreDiff: int) -> dict:
        """Apply game-state multipliers: quarter, score, clock, field position."""
        q = self.currentQuarter
        secs = self.gameClockSeconds

        if q == 4 and scoreDiff < 0:
            if secs < 120:
                weights['run'] *= 0.1; weights['short'] *= 1.3
                weights['medium'] *= 1.8; weights['long'] *= 2.5
            elif secs < 300:
                weights['run'] *= 0.3; weights['medium'] *= 1.5; weights['long'] *= 1.8
            else:
                weights['run'] *= 0.6; weights['medium'] *= 1.2; weights['long'] *= 1.3

        if q == 4 and scoreDiff > 0:
            weights['run'] *= 1.6; weights['long'] *= 0.3; weights['medium'] *= 0.7

        if q == 3 and scoreDiff < -10:
            weights['run'] *= 0.7; weights['medium'] *= 1.2; weights['long'] *= 1.4

        if self.yardsToEndzone <= 15:
            weights['run'] *= 1.3; weights['long'] *= 0.2
        elif self.yardsToEndzone <= 25:
            weights['long'] *= 0.5

        if self.yardsToSafety <= 5:
            weights['run'] *= 1.4; weights['short'] *= 0.7; weights['long'] *= 0.1

        return weights

    def _applyMatchupMods(self, weights: dict, coach) -> dict:
        """Adjust weights based on offense vs defense matchups, scaled by adaptability."""
        adaptNorm = (coach.adaptability - COACH_ATTR_NEUTRAL) / COACH_ATTR_RANGE if coach else 0.0
        defRunRating = self.defensiveTeam.defenseRunCoverageRating
        defPassRating = self.defensiveTeam.defensePassRating

        if defRunRating < 70:
            weights['run'] *= 1 + 0.4 * max(0.0, adaptNorm) * (70 - defRunRating) / 10
        if defRunRating > 85:
            weights['run'] *= max(0.5, 1 - 0.3 * max(0.0, adaptNorm) * (defRunRating - 85) / 15)

        if defPassRating < 70:
            boost = 1 + 0.3 * max(0.0, adaptNorm) * (70 - defPassRating) / 10
            for k in ('short', 'medium', 'long'):
                weights[k] *= boost

        return weights

    def _applyCoachMods(self, weights: dict, coach) -> dict:
        """Apply coach personality multipliers to the weight distribution."""
        if coach is None:
            return weights
        aggrNorm = (coach.aggressiveness - COACH_ATTR_NEUTRAL) / COACH_ATTR_RANGE
        offMindNorm = (coach.offensiveMind - COACH_ATTR_NEUTRAL) / COACH_ATTR_RANGE

        weights['long']   *= max(0.2, 1 + 0.5 * aggrNorm)
        weights['medium'] *= max(0.5, 1 + 0.15 * aggrNorm)
        weights['run']    *= max(0.5, 1 - 0.2 * aggrNorm)
        weights['short']  *= max(0.5, 1 - 0.1 * aggrNorm)

        weights['medium'] *= max(0.5, 1 + 0.3 * offMindNorm)
        weights['long']   *= max(0.5, 1 + 0.2 * offMindNorm)
        weights['short']  *= max(0.5, 1 - 0.1 * offMindNorm)

        return weights

    def _selectPassPlay(self, tier: str) -> str:
        """Select a pass play from the given tier, weighted by receiver-vs-defense matchups.

        Each targeted receiver's routeRunning vs the defense's pass coverage rating
        contributes a matchup delta to that play's weight. Coach offensiveMind scales
        how aggressively the coach exploits favourable matchups (60→neutral, 100→max).
        """
        pools = {
            'short':  ['Play8', 'Play10', 'Play11', 'Play12', 'Play14'],
            'medium': ['Play3', 'Play6', 'Play7', 'Play13', 'Play15', 'Play16', 'Play17'],
            'long':   ['Play1', 'Play2', 'Play4', 'Play5', 'Play18', 'Play19', 'Play20'],
        }
        pool = pools[tier]

        coach = getattr(self.offensiveTeam, 'coach', None)
        # offensiveMind 60 → scale 0.0 (uniform), 80 → 0.5, 100 → 1.0
        offMindScale = max(0.0, (coach.offensiveMind - COACH_OFFENSIVE_MIND_FLOOR) / (COACH_ATTR_NEUTRAL - COACH_OFFENSIVE_MIND_FLOOR)) if coach else 0.5

        defCoverage = self.defensiveTeam.defensePassCoverageRating
        rosterDict = self.offensiveTeam.rosterDict

        receiverRatings = {}
        for pos in ('wr1', 'wr2', 'te'):
            player = rosterDict.get(pos)
            if player is not None:
                receiverRatings[pos] = player.gameAttributes.routeRunning

        weights = []
        for playKey in pool:
            targets = passPlayBook[playKey]['targets']
            weight = 1.0
            for pos, passType in targets.items():
                if pos in ('wr1', 'wr2', 'te') and passType is not None and pos in receiverRatings:
                    matchup = receiverRatings[pos] - defCoverage
                    weight += (matchup / RECEIVER_MATCHUP_SCALE) * offMindScale
            weights.append(max(0.1, weight))

        return _random.choices(pool, weights=weights, k=1)[0]

    def _executeWeightedPlay(self, weights: dict):
        """Sample from the weight distribution and execute the chosen play."""
        play = _random.choices(
            ['run', 'short', 'medium', 'long'],
            weights=[weights['run'], weights['short'], weights['medium'], weights['long']]
        )[0]
        if play == 'run':
            self.play.runPlay()
        elif play == 'short':
            self.play.passPlay(self._selectPassPlay('short'))
        elif play == 'medium':
            self.play.passPlay(self._selectPassPlay('medium'))
        else:
            self.play.passPlay(self._selectPassPlay('long'))

    def playCaller(self):
        isHome = (self.offensiveTeam == self.homeTeam)
        scoreDiff = (self.homeScore - self.awayScore) if isHome else (self.awayScore - self.homeScore)
        coach = getattr(self.offensiveTeam, 'coach', None)
        timeoutsLeft = self.homeTimeoutsRemaining if isHome else self.awayTimeoutsRemaining

        # Clock management — evaluated before any play selection on downs 1-3
        if self.down <= 3:
            # Kneel: Q4, leading — only when guaranteed to drain the clock
            # Each kneel ~40 sec; opponent timeouts only matter when game is close (≤8 pts)
            if self.currentQuarter == 4 and scoreDiff > 0:
                oppTimeouts = self.awayTimeoutsRemaining if isHome else self.homeTimeoutsRemaining
                availableKneels = 4 - self.down  # 1st→3, 2nd→2, 3rd→1
                effectiveOppTos = oppTimeouts if scoreDiff <= 8 else 0
                drainableSeconds = max(0, availableKneels - effectiveOppTos) * KNEEL_DRAIN_SECONDS
                if drainableSeconds >= self.gameClockSeconds:
                    self.play.kneel()
                    return
            # Spike: Q4 or Q2, clock running, <15 sec, no timeouts, not leading
            if (self.currentQuarter in (2, 4) and self.clockRunning
                    and self.gameClockSeconds <= SPIKE_CLOCK_THRESHOLD and timeoutsLeft == 0 and scoreDiff <= 0):
                self.play.spike()
                return
            # Call timeout: Q4, trailing, clock running, timeouts available, <120 sec
            if (self.currentQuarter == 4 and scoreDiff < 0 and self.clockRunning
                    and timeoutsLeft > 0 and self.gameClockSeconds <= TIMEOUT_CLOCK_THRESHOLD):
                self._callTimeout(isHome)
                # fall through — still need to call a play

        # Overtime
        if self.currentQuarter == 5:
            self._otPlayCaller(scoreDiff)
            return

        # End-of-half / end-of-game FG attempts — compute kicker range once
        kicker = self.offensiveTeam.rosterDict.get('k')
        kickerMaxFg = (kicker.maxFgDistance - FG_SNAP_DISTANCE) if kicker else 0

        # End-of-half FG attempt
        if self.currentQuarter == 2 and self.gameClockSeconds < TIMEOUT_CLOCK_THRESHOLD and self.down == 4:
            if self.yardsToEndzone <= kickerMaxFg:
                self.play.playType = PlayType.FieldGoal
                return

        # End-of-game FG attempt
        if self.currentQuarter == 4 and self.gameClockSeconds < TIMEOUT_CLOCK_THRESHOLD and self.down == 4:
            if scoreDiff >= 0:
                if scoreDiff <= 3 and self.yardsToEndzone <= kickerMaxFg:
                    self.play.playType = PlayType.FieldGoal
                    return

        # 4th down
        if self.down == 4:
            self._fourthDownCaller(scoreDiff, coach, isHome)
            return

        # Downs 1–3: weighted probability sampling
        weights = self._computePlayWeights(scoreDiff, coach)
        self._executeWeightedPlay(weights)

    def turnover(self, offense: FloosTeam.Team, defense: FloosTeam.Team, yards):
        # OT possession tracking: detect when each team's possession ends
        # offense = team giving up ball, defense = team receiving ball
        if self.currentQuarter >= 5 and self.otFirstPossTeam is not None:
            if offense is self.otFirstPossTeam and not self.otFirstPossComplete:
                # First team's possession just ended
                self.otFirstPossComplete = True
                self.firstOtPossessionComplete = False  # not complete until second team also done
            elif self.otFirstPossComplete and offense is not self.otFirstPossTeam:
                # Second team's possession just ended — both teams have had their turn
                self.otSecondPossComplete = True
                self.firstOtPossessionComplete = True
        
        self.offensiveTeam = defense
        self.defensiveTeam = offense
        self.yardsToEndzone = yards
        self.yardsToSafety = FIELD_LENGTH - self.yardsToEndzone
        self.down = 1
        self.yardsToFirstDown = YARDS_TO_FIRST_DOWN


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
                    text = choice(sackList).format(self.play.passer.name, self.play.yardage)
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
                text = choice(interceptionList).format(self.play.passer.name, self.play.defense.abbr)
            else:
                if self.play.passType is PassType.short:
                    if self.play.passIsDropped:
                        text = choice(shortDropList).format(self.play.passer.name, self.play.receiver.name)
                    else:
                        text = choice(shortIncompleteList).format(self.play.passer.name, self.play.receiver.name)
                elif self.play.passType is PassType.long or self.play.passType is PassType.hailMary:
                    if self.play.passIsDropped:
                        text = choice(deepDropList).format(self.play.passer.name, self.play.receiver.name)
                    else:
                        text = choice(deepIncompleteList).format(self.play.passer.name, self.play.receiver.name)
                elif self.play.passType is PassType.throwAway:
                    text = choice(throwAwayList).format(self.play.passer.name)
                else:
                    if self.play.passIsDropped:
                        text = choice(midDropList).format(self.play.passer.name, self.play.receiver.name)
                    else:
                        text = choice(midIncompleteList).format(self.play.passer.name, self.play.receiver.name)
        elif self.play.playType == PlayType.FieldGoal:
            text = '{}yd Field Goal attempt by {}'.format(self.play.fgDistance, self.play.kicker.name)
        elif self.play.playType is PlayType.Punt:
            punter = self.play.offense.rosterDict.get('k')
            punterName = punter.name if punter else 'Punter'
            text = '{} punts'.format(punterName)
        elif self.play.playType is PlayType.Spike:
            qb = self.play.offense.rosterDict.get('qb')
            qbName = qb.name if qb else 'QB'
            text = f'{qbName} spikes the ball'
        elif self.play.playType is PlayType.Kneel:
            qb = self.play.offense.rosterDict.get('qb')
            qbName = qb.name if qb else 'QB'
            text = f'{qbName} takes a knee'

        self.play.playText = text

    def _accumulateOffenseStats(self, team, score):
        """Accumulate a team's offensive stats into season totals after a game."""
        roster = team.rosterDict
        qb = roster.get('qb')
        rb = roster.get('rb')
        k  = roster.get('k')
        off = team.seasonTeamStats['Offense']
        off['pts'] += score
        passYards = qb.gameStatsDict['passing']['yards'] if qb else 0
        runYards  = rb.gameStatsDict['rushing']['yards'] if rb else 0
        passTds   = qb.gameStatsDict['passing']['tds']  if qb else 0
        runTds    = rb.gameStatsDict['rushing']['tds']   if rb else 0
        off['passYards']  += passYards
        off['runYards']   += runYards
        off['totalYards'] += passYards + runYards
        off['passTds']    += passTds
        off['runTds']     += runTds
        off['tds']        += passTds + runTds
        if k:
            off['fgs'] += k.gameStatsDict['kicking']['fgs']
        team.seasonTeamStats['scoreDiff'] += score - team.gameDefenseStats['ptsAlwd']

    def _accumulateDefenseStats(self, team):
        """Accumulate a team's defensive stats into season totals after a game."""
        season = team.seasonTeamStats['Defense']
        game   = team.gameDefenseStats
        for key in ('ints', 'fumRec', 'sacks', 'safeties',
                    'runYardsAlwd', 'passYardsAlwd', 'totalYardsAlwd',
                    'runTdsAlwd', 'passTdsAlwd', 'tdsAlwd', 'ptsAlwd'):
            season[key] += game[key]
        total = team.seasonTeamStats['wins'] + team.seasonTeamStats['losses']
        team.seasonTeamStats['winPerc'] = round(team.seasonTeamStats['wins'] / total, 3) if total > 0 else 0.0

    def _calculateDefenseFantasyPoints(self, team):
        """Apply fantasy point bonus/penalty based on points allowed this game."""
        ptsAlwd = team.gameDefenseStats['ptsAlwd']
        if ptsAlwd >= 35:
            team.gameDefenseStats['fantasyPoints'] += -4
        elif ptsAlwd >= 28:
            team.gameDefenseStats['fantasyPoints'] += -1
        elif 14 <= ptsAlwd <= 21:
            team.gameDefenseStats['fantasyPoints'] += 1
        elif 7 <= ptsAlwd <= 13:
            team.gameDefenseStats['fantasyPoints'] += 4
        elif 1 <= ptsAlwd <= 6:
            team.gameDefenseStats['fantasyPoints'] += 7
        elif ptsAlwd == 0:
            team.gameDefenseStats['fantasyPoints'] += 10

    def postgame(self):
        if self.isRegularSeasonGame:
            self._accumulateOffenseStats(self.homeTeam, self.homeScore)
            self._accumulateOffenseStats(self.awayTeam, self.awayScore)

            if self.winningTeam.seasonTeamStats['streak'] >= 0:
                self.winningTeam.seasonTeamStats['streak'] += 1
                if self.winningTeam.seasonTeamStats['streak'] > 3 and not self.winningTeam.winningStreak:
                    self.winningTeam.winningStreak = True
                    self.leagueHighlights.insert(0, {'event': {'text': '{} {} are on a hot streak!'.format(self.winningTeam.city, self.winningTeam.name)}})
            else:
                self.winningTeam.seasonTeamStats['streak'] = 1
            self._accumulateDefenseStats(self.winningTeam)

            if self.losingTeam.seasonTeamStats['streak'] >= 0:
                self.losingTeam.seasonTeamStats['streak'] = -1
                if self.losingTeam.winningStreak:
                    self.losingTeam.winningStreak = False
                    self.leagueHighlights.insert(0, {'event': {'text': '{} {} ended the {} {} hot streak!'.format(self.winningTeam.city, self.winningTeam.name, self.losingTeam.city, self.losingTeam.name)}})
            else:
                self.losingTeam.seasonTeamStats['streak'] -= 1
            self._accumulateDefenseStats(self.losingTeam)

        self._calculateDefenseFantasyPoints(self.homeTeam)
        self._calculateDefenseFantasyPoints(self.awayTeam)


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
                    
            


    def calculateSimpleEloWinProbability(self):
        """
        Legacy simple ELO-only win probability (pre-game).
        Replaced by comprehensive calculateWinProbability() method.
        Kept for reference/compatibility.
        """
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
        
        # Store ELO ratings for use in win probability calculations
        self.homeTeamElo = self.homeTeam.elo
        self.awayTeamElo = self.awayTeam.elo
        
        # Calculate initial win probability using ELO (will be updated throughout game)
        initialWp = self.calculateWinProbability()
        self.homeTeamWinProbability = initialWp['home']
        self.awayTeamWinProbability = initialWp['away']

        # Store pre-game WP (0-1 decimal) for ELO update after game — must use the same
        # value that was displayed at kickoff, not the end-of-game running probability
        self.preGameHomeWinProbability = self.homeTeamWinProbability / 100.0
        self.preGameAwayWinProbability = self.awayTeamWinProbability / 100.0

        # Track previous win probability for WPA (Win Probability Added) calculations
        self.previousHomeWinProbability = self.homeTeamWinProbability
        self.previousAwayWinProbability = self.awayTeamWinProbability
        
        # Broadcast game start event
        if BROADCASTING_AVAILABLE and broadcaster.is_enabled():
            event = GameEvent.gameStart(
                gameId=self.id,
                homeTeam={'name': self.homeTeam.name, 'city': self.homeTeam.city, 'abbr': self.homeTeam.abbr},
                awayTeam={'name': self.awayTeam.name, 'city': self.awayTeam.city, 'abbr': self.awayTeam.abbr},
                startTime=self.startTime
            )
            broadcaster.broadcast_sync(self.id, event)

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
        self.broadcastGameState(includeLastPlay=False, eventMessage={
            'text': '{} wins the coin toss'.format(coinFlipWinner.name),
            'quarter': 1,
            'timeRemaining': self.formatTime(self.gameClockSeconds)
        })
        
        # Main game loop - run until game is over
        while not self.isGameOver():
            # Format and add previous play to feed BEFORE quarter transitions
            # This ensures Q4 plays appear before OT events
            lastPlayFormatted = getattr(self, '_pendingPossessionChange', False)
            if self.totalPlays > 0 and self.gameClockSeconds <= 0:
                # Broadcast the last play with the CURRENT quarter before advanceQuarter() changes it.
                # Use playResult (not playText) to check if the play actually ran.
                quarterEndPlayRan = getattr(self.play, 'playResult', None) is not None
                if quarterEndPlayRan and not getattr(self.play, 'playText', None):
                    # Play ran but hasn't been formatted yet — format and broadcast now
                    self.formatPlayText()
                    if self.play.isSack:
                        self.defensiveTeam.gameDefenseStats['fantasyPoints'] += 1
                    if self.play.isFumbleLost or self.play.isInterception or self.play.scoreChange or self.play.yardage >= 30:
                        self.highlights.insert(0, {'play': self.play})
                        self.leagueHighlights.insert(0, {'play': self.play})
                    self.gameFeed.insert(0, {'play': self.play})
                    self.broadcastGameState(includeLastPlay=True)
                    lastPlayFormatted = True
                elif getattr(self.play, 'playText', None):
                    # Already formatted (e.g. TD broadcast) — just mark as done
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
                    self.broadcastGameState(includeLastPlay=False, eventMessage={
                        'text': 'Halftime',
                        'quarter': 2,
                        'timeRemaining': '0:00'
                    })
                    if self.timingManager:
                        await self.timingManager.waitForHalftime()

                    # Halftime gameplan adjustments
                    if GAMEPLAN_AVAILABLE:
                        homeOffStats = {
                            'runPlays': self.homeHalfRunPlays, 'runYards': self.homeHalfRunYards,
                            'passAttempts': self.homeHalfPassAttempts, 'passYards': self.homeHalfPassYards,
                        }
                        awayOffStats = {
                            'runPlays': self.awayHalfRunPlays, 'runYards': self.awayHalfRunYards,
                            'passAttempts': self.awayHalfPassAttempts, 'passYards': self.awayHalfPassYards,
                        }
                        homeCoach = getattr(self.homeTeam, 'coach', None)
                        awayCoach = getattr(self.awayTeam, 'coach', None)
                        adjustOffensiveGameplan(self.homeOffGameplan, homeCoach, homeOffStats)
                        adjustDefensiveGameplan(self.homeDefGameplan, homeCoach, awayOffStats)
                        adjustOffensiveGameplan(self.awayOffGameplan, awayCoach, awayOffStats)
                        adjustDefensiveGameplan(self.awayDefGameplan, awayCoach, homeOffStats)

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
                    self.broadcastGameState(includeLastPlay=False, eventMessage={
                        'text': 'Start Overtime',
                        'quarter': 'OT',
                        'timeRemaining': self.formatTime(self.gameClockSeconds)
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
                    self.broadcastGameState(includeLastPlay=False, eventMessage={
                        'text': '{} wins the OT coin toss'.format(coinFlipWinner.name),
                        'quarter': 'OT',
                        'timeRemaining': self.formatTime(self.gameClockSeconds)
                    })
                    self.otFirstPossTeam = coinFlipWinner
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
                    self.broadcastGameState(includeLastPlay=False, eventMessage={
                        'text': 'Start Additional Overtime Period',
                        'quarter': 'OT',
                        'timeRemaining': self.formatTime(self.gameClockSeconds)
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
                    self.broadcastGameState(includeLastPlay=False, eventMessage={
                        'text': '{} wins the OT coin toss'.format(coinFlipWinner.name),
                        'quarter': 'OT',
                        'timeRemaining': self.formatTime(self.gameClockSeconds)
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
                    self.broadcastGameState(includeLastPlay=False, eventMessage={
                        'text': 'Start 2nd Quarter',
                        'quarter': 2,
                        'timeRemaining': self.formatTime(self.gameClockSeconds)
                    })
                    # Broadcast end of Q1 stats
                    if BROADCASTING_AVAILABLE and broadcaster.is_enabled():
                        homeStats = self._collect_player_stats_for_broadcast(self.homeTeam)
                        awayStats = self._collect_player_stats_for_broadcast(self.awayTeam)
                        homeTeamStats = self._collect_team_stats_for_broadcast(self.homeTeam, is_home=True)
                        awayTeamStats = self._collect_team_stats_for_broadcast(self.awayTeam, is_home=False)
                        event = PlayerEvent.gameStatsUpdate(
                            gameId=self.id,
                            homePlayerStats=homeStats,
                            awayPlayerStats=awayStats,
                            homeTeamStats=homeTeamStats,
                            awayTeamStats=awayTeamStats
                        )
                        broadcaster.broadcast_sync(self.id, event)
                elif self.currentQuarter == 3:
                    if self.timingManager:
                        await self.timingManager.waitForQuarterBreak()
                    self.gameFeed.insert(0, {'event':  {
                                                    'text': 'Start 3rd Quarter',
                                                    'quarter': 3,
                                                    'timeRemaining': self.formatTime(self.gameClockSeconds)
                                                }
                                            })
                    self.broadcastGameState(includeLastPlay=False, eventMessage={
                        'text': 'Start 3rd Quarter',
                        'quarter': 3,
                        'timeRemaining': self.formatTime(self.gameClockSeconds)
                    })
                    # Broadcast halftime stats
                    if BROADCASTING_AVAILABLE and broadcaster.is_enabled():
                        homeStats = self._collect_player_stats_for_broadcast(self.homeTeam)
                        awayStats = self._collect_player_stats_for_broadcast(self.awayTeam)
                        homeTeamStats = self._collect_team_stats_for_broadcast(self.homeTeam, is_home=True)
                        awayTeamStats = self._collect_team_stats_for_broadcast(self.awayTeam, is_home=False)
                        event = PlayerEvent.gameStatsUpdate(
                            gameId=self.id,
                            homePlayerStats=homeStats,
                            awayPlayerStats=awayStats,
                            homeTeamStats=homeTeamStats,
                            awayTeamStats=awayTeamStats
                        )
                        broadcaster.broadcast_sync(self.id, event)
                elif self.currentQuarter == 4:
                    if self.timingManager:
                        await self.timingManager.waitForQuarterBreak()
                    self.gameFeed.insert(0, {'event':  {
                                                    'text': 'Start 4th Quarter',
                                                    'quarter': 4,
                                                    'timeRemaining': self.formatTime(self.gameClockSeconds)
                                                }
                                            })
                    self.broadcastGameState(includeLastPlay=False, eventMessage={
                        'text': 'Start 4th Quarter',
                        'quarter': 4,
                        'timeRemaining': self.formatTime(self.gameClockSeconds)
                    })
                    # Broadcast end of Q3 stats
                    if BROADCASTING_AVAILABLE and broadcaster.is_enabled():
                        homeStats = self._collect_player_stats_for_broadcast(self.homeTeam)
                        awayStats = self._collect_player_stats_for_broadcast(self.awayTeam)
                        homeTeamStats = self._collect_team_stats_for_broadcast(self.homeTeam, is_home=True)
                        awayTeamStats = self._collect_team_stats_for_broadcast(self.awayTeam, is_home=False)
                        event = PlayerEvent.gameStatsUpdate(
                            gameId=self.id,
                            homePlayerStats=homeStats,
                            awayPlayerStats=awayStats,
                            homeTeamStats=homeTeamStats,
                            awayTeamStats=awayTeamStats
                        )
                        broadcaster.broadcast_sync(self.id, event)

            # Start new possession if needed
            if self.down == 0 or self.down > 4:
                self.down = 1
                self.yardsToFirstDown = YARDS_TO_FIRST_DOWN
                self.yardsToEndzone = 80
                self.yardsToSafety = 20

            # Possession loop - while offense has downs
            while self.down <= 4 and self.gameClockSeconds > 0:
                # Show previous play if exists (unless already formatted at quarter transition)
                # Update yardline display to current ball position (do this before broadcast and play creation)
                if self.yardsToEndzone > 50:
                    self.yardLine = '{0} {1}'.format(self.offensiveTeam.abbr, (100-self.yardsToEndzone))
                else:
                    self.yardLine = '{0} {1}'.format(self.defensiveTeam.abbr, self.yardsToEndzone)

                playActuallyRan = getattr(self.play, 'playResult', None) is not None
                if self.totalPlays > 0 and not lastPlayFormatted and playActuallyRan:
                    self.formatPlayText()
                    if self.play.isSack:
                        self.defensiveTeam.gameDefenseStats['fantasyPoints'] += 1
                    if self.play.isFumbleLost or self.play.isInterception or self.play.scoreChange or self.play.yardage >= 30:
                        self.highlights.insert(0, {'play': self.play})
                        self.leagueHighlights.insert(0, {'play': self.play})
                    self.gameFeed.insert(0, {'play': self.play})

                    # Broadcast comprehensive game state (replaces playComplete, scoreUpdate, gameStateUpdate)
                    self.broadcastGameState(includeLastPlay=True)

                # Reset flag after first iteration
                lastPlayFormatted = False

                # Create new play
                self.play = Play(self)
                
                # Between-plays timing
                if self.timingManager:
                    await self.timingManager.waitBetweenPlays()

                # After the delay: broadcast possession change with new ball position
                if getattr(self, '_pendingPossessionChange', False):
                    if getattr(self, '_pendingKickoff', False):
                        kickingTeam = self.defensiveTeam
                        receivingTeam = self.offensiveTeam

                        if self._shouldOnsideKick():
                            # Announce attempt
                            self.broadcastGameState(
                                includeLastPlay=False,
                                isPossessionChange=True,
                                eventMessage={
                                    'text': f'{kickingTeam.abbr} attempts an onside kick!',
                                    'quarter': self.currentQuarter,
                                    'timeRemaining': self.formatTime(self.gameClockSeconds)
                                }
                            )
                            if self.timingManager:
                                await self.timingManager.waitBeforeOnsideResult()

                            # Resolve recovery (~5-10% kicking team success)
                            import random
                            kickingTeamRecovers = random.random() < random.uniform(0.05, 0.10)

                            if kickingTeamRecovers:
                                self.turnover(self.offensiveTeam, self.defensiveTeam, 50)
                                self.broadcastGameState(
                                    includeLastPlay=False,
                                    isPossessionChange=True,
                                    eventMessage={
                                        'text': f'{kickingTeam.abbr} recovers the onside kick! Ball at midfield!',
                                        'quarter': self.currentQuarter,
                                        'timeRemaining': self.formatTime(self.gameClockSeconds)
                                    }
                                )
                            else:
                                # Receiving team keeps ball — move to their 40 instead of their 20
                                self.yardsToEndzone = 60
                                self.yardsToSafety = FIELD_LENGTH - self.yardsToEndzone
                                self.broadcastGameState(
                                    includeLastPlay=False,
                                    isPossessionChange=True,
                                    eventMessage={
                                        'text': f'{receivingTeam.abbr} recovers at their own 40!',
                                        'quarter': self.currentQuarter,
                                        'timeRemaining': self.formatTime(self.gameClockSeconds)
                                    }
                                )
                        else:
                            # Normal kickoff
                            self.broadcastGameState(
                                includeLastPlay=False,
                                isPossessionChange=True,
                                eventMessage={
                                    'text': f'{kickingTeam.abbr} kicks off',
                                    'quarter': self.currentQuarter,
                                    'timeRemaining': self.formatTime(self.gameClockSeconds)
                                }
                            )

                        self._pendingKickoff = False
                        if self.timingManager:
                            await self.timingManager.waitAfterKickoff()
                    else:
                        # Punt/turnover: immediate possession-change broadcast
                        self.broadcastGameState(includeLastPlay=False, isPossessionChange=True)
                    self._pendingPossessionChange = False

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
                self.totalPlays += 1
                if self.offensiveTeam is self.homeTeam:
                    self.homePlaysTotal += 1
                    if self.down == 3:
                        self.home3rdDownAtt += 1
                    elif self.down == 4 and self.play.playType not in (PlayType.Punt, PlayType.FieldGoal):
                        self.home4thDownAtt += 1
                if self.offensiveTeam is self.awayTeam:
                    self.awayPlaysTotal += 1
                    if self.down == 3:
                        self.away3rdDownAtt += 1
                    elif self.down == 4 and self.play.playType not in (PlayType.Punt, PlayType.FieldGoal):
                        self.away4thDownAtt += 1

                # PLAY EXECUTION: Handle different play types
                if self.play.playType is PlayType.FieldGoal:
                    self.play.fieldGoalTry()
                    
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
                        
                        # Format and broadcast field goal BEFORE checking if game ends
                        self.formatPlayText()
                        if self.play.scoreChange or self.play.yardage >= 30:
                            self.highlights.insert(0, {'play': self.play})
                            self.leagueHighlights.insert(0, {'play': self.play})
                        self.gameFeed.insert(0, {'play': self.play})
                        
                        # Broadcast comprehensive game state
                        self.broadcastGameState(includeLastPlay=True)
                        
                        # Check if OT should end after score
                        if self.checkOvertimeEnd():
                            break
                        
                        self.turnover(self.offensiveTeam, self.defensiveTeam, possReset)
                        self._pendingPossessionChange = True
                        self._pendingKickoff = True
                        lastPlayFormatted = True
                        break
                    else:
                        self.play.playResult = PlayResult.FieldGoalNoGood
                        self.clockRunning = False  # Clock stops after turnover
                        self.formatPlayText()
                        self.gameFeed.insert(0, {'play': self.play})
                        self.broadcastGameState(includeLastPlay=True)
                        self.turnover(self.offensiveTeam, self.defensiveTeam, self.yardsToSafety)
                        self._pendingPossessionChange = True
                        lastPlayFormatted = True
                        break

                if self.play.playType is PlayType.Punt:
                    self.play.playResult = PlayResult.Punt
                    kicker = self.offensiveTeam.rosterDict['k']
                    if kicker is None:
                        logging.error(f"Team {self.offensiveTeam.name} has no kicker - using default punt distance")
                    maxPuntYards = round(70*(kicker.attributes.legStrength/100)) if kicker else 45
                    if maxPuntYards > self.yardsToEndzone:
                        maxPuntYards = self.yardsToEndzone + 10
                    puntDistance = randint((maxPuntYards-20), maxPuntYards)
                    if puntDistance >= self.yardsToEndzone:
                        puntDistance = self.yardsToEndzone - 20
                    self.play.yardage = puntDistance
                    newYards = 100 - (self.yardsToEndzone - puntDistance)
                    
                    # Consume time for punt (always stops clock)
                    playDuration = self.calculatePlayDuration(PlayType.Punt, False)
                    self.consumeGameTime(playDuration)
                    self.checkTwoMinuteWarning()
                    self.clockRunning = False  # Clock stops after punt
                    
                    self.formatPlayText()
                    if self.play.scoreChange or self.play.yardage >= 30:
                        self.highlights.insert(0, {'play': self.play})
                        self.leagueHighlights.insert(0, {'play': self.play})
                    self.gameFeed.insert(0, {'play': self.play})
                    self.broadcastGameState(includeLastPlay=True)
                    self.turnover(self.offensiveTeam, self.defensiveTeam, newYards)
                    self._pendingPossessionChange = True
                    lastPlayFormatted = True
                    break

                # Kneel / Spike: format and log immediately (clock already updated inside kneel()/spike())
                if self.play.playType is PlayType.Kneel or self.play.playType is PlayType.Spike:
                    self.formatPlayText()
                    self.gameFeed.insert(0, {'play': self.play})
                    self.broadcastGameState(includeLastPlay=True)
                    lastPlayFormatted = True
                    # Fall through to outcome section so the down is advanced correctly

                # POST-PLAY: Consume play duration time (run/pass only — kneel/spike handle their own clock)
                if self.play.playType not in (PlayType.Kneel, PlayType.Spike):
                    playDuration = self.calculatePlayDuration(self.play.playType, self.play.isInBounds)
                    self.consumeGameTime(playDuration)
                
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
                    self.formatPlayText()
                    if self.play.isFumbleLost or self.play.isInterception or self.play.scoreChange or self.play.yardage >= 30:
                        self.highlights.insert(0, {'play': self.play})
                        self.leagueHighlights.insert(0, {'play': self.play})
                    self.gameFeed.insert(0, {'play': self.play})

                    if self.play.yardage >= self.yardsToEndzone:
                        self.broadcastGameState(includeLastPlay=True)
                        self.turnover(self.offensiveTeam, self.defensiveTeam, possReset)
                    elif (self.yardsToSafety + self.play.yardage) <= 0:
                        self._addScore(self.defensiveTeam, 6)

                        if self._shouldGoForTwo(self.defensiveTeam):
                            self.play.playResult = PlayResult.Touchdown
                        else:
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
                            self.broadcastGameState(includeLastPlay=True)
                            break

                        self.broadcastGameState(includeLastPlay=True)
                        if self.play.playResult is PlayResult.Touchdown:
                            self._simulate2PointConversionPlay(self.defensiveTeam, self.offensiveTeam)
                        self.turnover(self.defensiveTeam, self.offensiveTeam, possReset)
                    else:
                        self.broadcastGameState(includeLastPlay=True)
                        self.turnover(self.offensiveTeam, self.defensiveTeam, (self.yardsToSafety + self.play.yardage))
                    self._pendingPossessionChange = True
                    lastPlayFormatted = True
                    break
                    
                # Handle normal play outcomes
                else:
                    if self.play.yardage >= self.yardsToEndzone:
                        self.play.isTd = True
                        if self.play.playType is PlayType.Run:
                            self.play.runner.addRushTd(self.play.yardage, self.isRegularSeasonGame)
                            self.play.runner.updateInGameConfidence(.03)
                            self.play.defense.gameDefenseStats['runTdsAlwd'] += 1
                            self.play.defense.gameDefenseStats['tdsAlwd'] += 1
                        elif self.play.playType is PlayType.Pass:
                            self.play.passer.addPassTd(self.play.yardage, self.isRegularSeasonGame)
                            self.play.receiver.addReceiveTd(self.play.yardage, self.isRegularSeasonGame)
                            self.play.defense.gameDefenseStats['passTdsAlwd'] += 1
                            self.play.defense.gameDefenseStats['tdsAlwd'] += 1
                            self.play.passer.updateInGameConfidence(.03)
                            self.play.receiver.updateInGameConfidence(.03)

                        self.play.defense.gameDefenseStats['ptsAlwd'] += 6

                        self._addScore(self.offensiveTeam, 6)

                        if self._shouldGoForTwo(self.offensiveTeam):
                            # Broadcast TD first, then simulate 2-pt as a separate play
                            self.play.playResult = PlayResult.Touchdown
                            self.play.scoreChange = True
                            self.play.homeTeamScore = self.homeScore
                            self.play.awayTeamScore = self.awayScore
                            self.formatPlayText()
                            if self.play.isFumbleLost or self.play.isInterception or self.play.scoreChange or self.play.yardage >= 30:
                                self.highlights.insert(0, {'play': self.play})
                                self.leagueHighlights.insert(0, {'play': self.play})
                            self.gameFeed.insert(0, {'play': self.play})
                            self.broadcastGameState(includeLastPlay=True)
                            if self.checkOvertimeEnd():
                                break
                            self._simulate2PointConversionPlay(self.offensiveTeam, self.defensiveTeam)
                        else:
                            self.play.extraPointTry(self.offensiveTeam)
                            if self.play.isXpGood:
                                self.play.playResult = PlayResult.TouchdownXP
                                self._addScore(self.offensiveTeam, 1)
                                self.play.defense.gameDefenseStats['ptsAlwd'] += 1
                            else:
                                self.play.playResult = PlayResult.TouchdownNoXP
                            self.play.scoreChange = True
                            self.play.homeTeamScore = self.homeScore
                            self.play.awayTeamScore = self.awayScore
                            self.formatPlayText()
                            if self.play.isFumbleLost or self.play.isInterception or self.play.scoreChange or self.play.yardage >= 30:
                                self.highlights.insert(0, {'play': self.play})
                                self.leagueHighlights.insert(0, {'play': self.play})
                            self.gameFeed.insert(0, {'play': self.play})
                            self.broadcastGameState(includeLastPlay=True)
                            if self.checkOvertimeEnd():
                                break

                        self.turnover(self.offensiveTeam, self.defensiveTeam, possReset)
                        self._pendingPossessionChange = True
                        self._pendingKickoff = True
                        lastPlayFormatted = True
                        break

                    elif self.play.yardage >= self.yardsToFirstDown:
                        downBefore = self.down
                        self.down = 1
                        if self.offensiveTeam is self.homeTeam:
                            self.home1stDownsTotal += 1
                            if downBefore == 3: self.home3rdDownConv += 1
                            elif downBefore == 4: self.home4thDownConv += 1
                        elif self.offensiveTeam is self.awayTeam:
                            self.away1stDownsTotal += 1
                            if downBefore == 3: self.away3rdDownConv += 1
                            elif downBefore == 4: self.away4thDownConv += 1
                        if self.yardsToEndzone < 10:
                            self.yardsToFirstDown = self.yardsToEndzone
                        else:
                            self.yardsToFirstDown = YARDS_TO_FIRST_DOWN
                        self.yardsToSafety += self.play.yardage
                        self.yardsToEndzone -= self.play.yardage
                        self.play.playResult = PlayResult.FirstDown
                        continue

                    elif (self.yardsToSafety + self.play.yardage) <= 0:
                        if self.play.isFumbleLost:
                            self._addScore(self.defensiveTeam, 6)

                            if self._shouldGoForTwo(self.defensiveTeam):
                                self.play.playResult = PlayResult.Touchdown
                            else:
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

                            # Broadcast score update
                            if BROADCASTING_AVAILABLE and broadcaster.is_enabled():
                                event = GameEvent.scoreUpdate(
                                    gameId=self.id,
                                    homeScore=self.homeScore,
                                    awayScore=self.awayScore,
                                    scoringPlay={'type': 'touchdown', 'team': self.offensiveTeam.abbr}
                                )
                                broadcaster.broadcast_sync(self.id, event)

                            # Check if OT should end after score
                            if self.checkOvertimeEnd():
                                break

                            if self.play.playResult is PlayResult.Touchdown:
                                self._simulate2PointConversionPlay(self.defensiveTeam, self.offensiveTeam)

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
                            
                            # Broadcast score update
                            if BROADCASTING_AVAILABLE and broadcaster.is_enabled():
                                event = GameEvent.scoreUpdate(
                                    gameId=self.id,
                                    homeScore=self.homeScore,
                                    awayScore=self.awayScore,
                                    scoringPlay={'type': 'safety', 'team': self.defensiveTeam.abbr}
                                )
                                broadcaster.broadcast_sync(self.id, event)
                            
                            # Check if OT should end after score
                            if self.checkOvertimeEnd():
                                break
                            
                            self.turnover(self.offensiveTeam, self.defensiveTeam, possReset)
                            self._pendingPossessionChange = True
                            self._pendingKickoff = True
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
        
        # Game over - show final play if it was a score or big play.
        # In OT, the scoring play may have already been added to gameFeed
        # and broadcast inside the loop before checkOvertimeEnd() broke out.
        alreadyInFeed = (self.gameFeed and self.gameFeed[0].get('play') is self.play)
        if self.totalPlays > 0 and self.play:
            if self.play.scoreChange:
                self.formatPlayText()
                if not alreadyInFeed:
                    if self.play.isFumbleLost or self.play.isInterception or self.play.scoreChange or self.play.yardage >= 30:
                        self.highlights.insert(0, {'play': self.play})
                        self.leagueHighlights.insert(0, {'play': self.play})
                    self.gameFeed.insert(0, {'play': self.play})

                    # Broadcast final game state (only if not already broadcast in the loop)
                    self.broadcastGameState(includeLastPlay=True)

        # Determine winner
        if self.awayScore > self.homeScore:
            self.winningTeam = self.awayTeam
            self.losingTeam = self.homeTeam
            self.gameDict['score'] = '{0} - {1}'.format(self.awayScore, self.homeScore)
            finalEventMessage = {
                'text': 'Final: {} - {} | {} - {}'.format(self.awayTeam.abbr, self.awayScore, self.homeTeam.abbr, self.homeScore),
                'quarter': 'Final',
                'timeRemaining': '0:00'
            }
            self.gameFeed.insert(0, {'event': finalEventMessage})
            self.leagueHighlights.insert(0, {'event':  {
                                                'text': 'Game Final: {} - {} | {} - {}'.format(self.awayTeam.name, self.awayScore, self.homeTeam.name, self.homeScore)
                                            }
                                        })

        elif self.homeScore > self.awayScore:
            self.winningTeam = self.homeTeam
            self.losingTeam = self.awayTeam
            self.gameDict['score'] = '{0} - {1}'.format(self.homeScore, self.awayScore)
            finalEventMessage = {
                'text': 'Final: {} - {} | {} - {}'.format(self.homeTeam.abbr, self.homeScore, self.awayTeam.abbr, self.awayScore),
                'quarter': 'Final',
                'timeRemaining': '0:00'
            }
            self.gameFeed.insert(0, {'event': finalEventMessage})
            self.leagueHighlights.insert(0, {'event':  {
                                                'text': 'Game Final: {} - {} | {} - {}'.format(self.homeTeam.name, self.homeScore, self.awayTeam.name, self.awayScore)
                                            }
                                        })
        else:
            # Tie game (should only happen in OT time expiration)
            self.winningTeam = self.homeTeam  # Arbitrary - treat as home team win
            self.losingTeam = self.awayTeam
            self.gameDict['score'] = '{0} - {1} (TIE)'.format(self.homeScore, self.awayScore)
            finalEventMessage = {
                'text': 'Final (TIE): {} - {} | {} - {}'.format(self.homeTeam.abbr, self.homeScore, self.awayTeam.abbr, self.awayScore),
                'quarter': 'Final',
                'timeRemaining': '0:00'
            }
            self.gameFeed.insert(0, {'event': finalEventMessage})
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
        finalWp = self.calculateWinProbability()  # Now returns 100/0 since isGameOver() is True

        # Stamp the final 100/0 WP onto the last play entry in gameFeed so the
        # WP chart reaches 100% at game end (the event entry inserted above
        # pushed the last play down to gameFeed[1+]).
        for entry in self.gameFeed:
            if 'play' in entry:
                entry['homeWinProbability'] = finalWp['home']
                entry['awayWinProbability'] = finalWp['away']
                break
        # Note: Post-game stat processing now handled by RecordManager.processPostGameStats()
        
        # Broadcast final game state with the "Final" event message so the play feed updates live
        if BROADCASTING_AVAILABLE and broadcaster.is_enabled():
            self.broadcastGameState(includeLastPlay=False, eventMessage=finalEventMessage, isFinalBroadcast=True)
        
        # Broadcast game end event
        if BROADCASTING_AVAILABLE and broadcaster.is_enabled():
            winner = self.winningTeam.name if self.winningTeam else 'Tie'
            
            # Collect final player and team stats
            homeStats = self._collect_player_stats_for_broadcast(self.homeTeam)
            awayStats = self._collect_player_stats_for_broadcast(self.awayTeam)
            homeTeamStats = self._collect_team_stats_for_broadcast(self.homeTeam, is_home=True)
            awayTeamStats = self._collect_team_stats_for_broadcast(self.awayTeam, is_home=False)
            
            # Broadcast game end with stats
            event = GameEvent.gameEnd(
                gameId=self.id,
                finalScore={'home': self.homeScore, 'away': self.awayScore},
                winner=winner,
                stats={
                    'totalPlays': self.totalPlays,
                    'homePlays': self.homePlaysTotal,
                    'awayPlays': self.awayPlaysTotal,
                    'homePlayerStats': homeStats,
                    'awayPlayerStats': awayStats,
                    'homeTeamStats': homeTeamStats,
                    'awayTeamStats': awayTeamStats
                }
            )
            broadcaster.broadcast_sync(self.id, event)
    
    
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
    
    def _buildGameStatsSnapshot(self) -> dict:
        """Build a snapshot of team-level box score and per-player game stats."""
        def teamSnapshot(team):
            roster = team.rosterDict
            qb  = roster.get('qb')
            rb  = roster.get('rb')
            wr1 = roster.get('wr1')
            wr2 = roster.get('wr2')
            te  = roster.get('te')
            k   = roster.get('k')

            # Passing (QB only)
            passYards = qb.gameStatsDict['passing']['yards'] if qb else 0
            passTds   = qb.gameStatsDict['passing']['tds']   if qb else 0
            passAtt   = qb.gameStatsDict['passing']['att']   if qb else 0
            passComp  = qb.gameStatsDict['passing']['comp']  if qb else 0
            passInts  = qb.gameStatsDict['passing']['ints']  if qb else 0

            # Rushing (aggregate all skill positions)
            rushYards = rushTds = rushCarries = fumbleLost = 0
            for slot in ['rb', 'wr1', 'wr2', 'te']:
                p = roster.get(slot)
                if p:
                    rushYards   += p.gameStatsDict['rushing']['yards']
                    rushTds     += p.gameStatsDict['rushing']['tds']
                    rushCarries += p.gameStatsDict['rushing']['carries']
                    fumbleLost  += p.gameStatsDict['rushing']['fumblesLost']

            turnovers = passInts + fumbleLost
            defense   = team.gameDefenseStats

            def playerDict(p, statsKey):
                if not p:
                    return None
                rating = getattr(p, 'playerRating', 0) or 0
                stars = round(((rating - 60) / 40) * 4 + 1) if rating >= 60 else 1
                stats = dict(p.gameStatsDict[statsKey])
                # Compute per-unit averages live (stored values only update end-of-game)
                if statsKey == 'rushing':
                    carries = stats.get('carries', 0)
                    stats['ypc'] = round(stats.get('yards', 0) / carries, 1) if carries > 0 else 0.0
                elif statsKey == 'passing':
                    comp = stats.get('comp', 0)
                    stats['ypc'] = round(stats.get('yards', 0) / comp, 1) if comp > 0 else 0.0
                elif statsKey == 'receiving':
                    recs = stats.get('receptions', 0)
                    stats['ypr'] = round(stats.get('yards', 0) / recs, 1) if recs > 0 else 0.0
                return {
                    'id': p.id,
                    'name': p.name,
                    'position': p.position.name if hasattr(p, 'position') and p.position else None,
                    'playerRating': rating,
                    'ratingStars': max(1, min(5, stars)),
                    'fantasyPoints': round(p.gameStatsDict.get('fantasyPoints', 0), 1),
                    **stats,
                }

            return {
                'team': {
                    'passYards':   passYards,
                    'passComp':    passComp,
                    'passAtt':     passAtt,
                    'passTds':     passTds,
                    'passInts':    passInts,
                    'rushYards':   rushYards,
                    'rushCarries': rushCarries,
                    'rushTds':     rushTds,
                    'totalYards':  passYards + rushYards,
                    'turnovers':   turnovers,
                    'sacks':       defense.get('sacks', 0),
                    'firstDowns':  self.home1stDownsTotal if team is self.homeTeam else self.away1stDownsTotal,
                    'totalPlays':  self.homePlaysTotal if team is self.homeTeam else self.awayPlaysTotal,
                    'thirdDownConv': self.home3rdDownConv if team is self.homeTeam else self.away3rdDownConv,
                    'thirdDownAtt':  self.home3rdDownAtt  if team is self.homeTeam else self.away3rdDownAtt,
                    'fourthDownConv': self.home4thDownConv if team is self.homeTeam else self.away4thDownConv,
                    'fourthDownAtt':  self.home4thDownAtt  if team is self.homeTeam else self.away4thDownAtt,
                },
                'players': {
                    'qb':  playerDict(qb,  'passing'),
                    'rb':  playerDict(rb,  'rushing'),
                    'wr1': playerDict(wr1, 'receiving'),
                    'wr2': playerDict(wr2, 'receiving'),
                    'te':  playerDict(te,  'receiving'),
                    'k':   playerDict(k,   'kicking'),
                }
            }

        return {
            'home': teamSnapshot(self.homeTeam),
            'away': teamSnapshot(self.awayTeam),
        }

    def broadcastGameState(self, includeLastPlay: bool = True, eventMessage: dict = None, isPossessionChange: bool = False, isFinalBroadcast: bool = False):
        """
        Broadcast comprehensive game state after a play or game event.
        This single event replaces score_update, play_complete, and game_state_update.

        Args:
            includeLastPlay: If True, include the last play data in the broadcast
            eventMessage: Optional event message dict (e.g., {'text': 'Halftime', 'quarter': 2, ...})
            isPossessionChange: If True, omit ball position fields so frontend keeps its current state
            isFinalBroadcast: If True, broadcast even in TURBO mode (used for game-end state)
        """
        if not BROADCASTING_AVAILABLE or not broadcaster.is_enabled():
            return

        # In TURBO mode skip all per-play broadcasts; only send the final game state
        from managers.timingManager import TimingMode
        if self.timingManager and self.timingManager.getMode() == TimingMode.TURBO and not isFinalBroadcast:
            return
        
        # Calculate win probabilities
        winProb = self.calculateWinProbability()
        newHomeWp = winProb['home']
        newAwayWp = winProb['away']
        homeWpa = float(newHomeWp - self.previousHomeWinProbability)
        awayWpa = float(newAwayWp - self.previousAwayWinProbability)

        # Compute upset alert: pre-game underdog (35% or less) is now favored by 65%+, starting Q2.
        # Only qualifies as an upset if the pre-game favorite is currently in a playoff spot
        # (top half of their league standings as of this week).
        def teamInPlayoffSpot(team):
            league = getattr(team, 'leagueRef', None)
            if not league:
                return False
            standings = league.getStandings()
            numPlayoffSpots = len(standings) // 2
            for i, entry in enumerate(standings):
                if entry['team'] is team:
                    return i < numPlayoffSpots
            return False

        isUpsetAlert = False
        if hasattr(self, 'preGameHomeWinProbability') and self.currentQuarter >= 2:
            preGameHomeWp = self.preGameHomeWinProbability  # 0-1 decimal
            if preGameHomeWp < 0.35 and newHomeWp >= 65.0 and teamInPlayoffSpot(self.awayTeam):
                isUpsetAlert = True
            elif preGameHomeWp > 0.65 and newAwayWp >= 65.0 and teamInPlayoffSpot(self.homeTeam):
                isUpsetAlert = True
        self.isUpsetAlert = isUpsetAlert

        # Build last play data if requested (and no event message)
        lastPlayData = None
        if eventMessage:
            # Use event message instead of play data
            lastPlayData = eventMessage
        elif includeLastPlay and hasattr(self, 'play') and self.play:
            lastPlayData = {
                'playNumber': self.totalPlays,
                'quarter': self.play.quarter if hasattr(self.play, 'quarter') else self.currentQuarter,
                'timeRemaining': self.formatTime(self.gameClockSeconds),
                'down': self.play.down if hasattr(self.play, 'down') else self.down,
                'distance': self.play.yardsTo1st if hasattr(self.play, 'yardsTo1st') else self.yardsToFirstDown,
                'yardLine': self.play.yardLine if hasattr(self.play, 'yardLine') else self.yardLine,
                'playType': self.play.playType.name if hasattr(self.play, 'playType') and hasattr(self.play.playType, 'name') else str(getattr(self.play, 'playType', 'Unknown')),
                'yardsGained': getattr(self.play, 'yardage', 0),
                'description': getattr(self.play, 'playText', ''),
                'playResult': self.play.playResult.value if hasattr(self.play, 'playResult') and self.play.playResult else None,
                'isTouchdown': getattr(self.play, 'isTd', False),
                'isTurnover': (getattr(self.play, 'isFumbleLost', False) or getattr(self.play, 'isInterception', False)),
                'isSack': getattr(self.play, 'isSack', False),
                'scoreChange': getattr(self.play, 'scoreChange', False),
                'homeTeamScore': getattr(self.play, 'homeTeamScore', None),
                'awayTeamScore': getattr(self.play, 'awayTeamScore', None),
                'offensiveTeam': self.play.offense.abbr if hasattr(self.play, 'offense') else self.offensiveTeam.abbr,
                'defensiveTeam': self.play.defense.abbr if hasattr(self.play, 'defense') else self.defensiveTeam.abbr,
                'homeWpa': round(homeWpa, 2),
                'awayWpa': round(awayWpa, 2),
                'isBigPlay': bool(abs(homeWpa) >= 10.0 or abs(awayWpa) >= 10.0)
            }
        
        # Determine possession team abbreviation and booleans
        possessionAbbr = None
        homeTeamPoss = False
        awayTeamPoss = False
        if hasattr(self, 'offensiveTeam'):
            possessionAbbr = self.offensiveTeam.abbr
            homeTeamPoss = (self.offensiveTeam == self.homeTeam)
            awayTeamPoss = (self.offensiveTeam == self.awayTeam)
        
        # Build comprehensive game state
        gameStateData = {
            'status': self.status.name if hasattr(self.status, 'name') else str(self.status),
            'homeScore': self.homeScore,
            'awayScore': self.awayScore,
            'quarterScores': {
                'home': {
                    'q1': getattr(self, 'homeScoreQ1', 0),
                    'q2': getattr(self, 'homeScoreQ2', 0),
                    'q3': getattr(self, 'homeScoreQ3', 0),
                    'q4': getattr(self, 'homeScoreQ4', 0),
                    'ot': getattr(self, 'homeScoreOT', 0)
                },
                'away': {
                    'q1': getattr(self, 'awayScoreQ1', 0),
                    'q2': getattr(self, 'awayScoreQ2', 0),
                    'q3': getattr(self, 'awayScoreQ3', 0),
                    'q4': getattr(self, 'awayScoreQ4', 0),
                    'ot': getattr(self, 'awayScoreOT', 0)
                }
            },
            'possession': possessionAbbr,
            'homeTeamPoss': homeTeamPoss,
            'awayTeamPoss': awayTeamPoss,
            'quarter': self.currentQuarter,
            'timeRemaining': self.formatTime(self.gameClockSeconds),
            'down': self.down if hasattr(self, 'down') else None,
            'distance': self.yardsToFirstDown if hasattr(self, 'yardsToFirstDown') else None,
            'yardLine': self.yardLine if hasattr(self, 'yardLine') else None,
            'yardsToEndzone': self.yardsToEndzone if hasattr(self, 'yardsToEndzone') else None,
            'yardsToSafety': (100 - self.yardsToEndzone) if hasattr(self, 'yardsToEndzone') else None,
            'isPossessionChange': isPossessionChange,
            'lastPlay': lastPlayData,
            'homeWinProbability': round(newHomeWp, 1),
            'awayWinProbability': round(newAwayWp, 1),
            'homeWpa': round(homeWpa, 2),
            'awayWpa': round(awayWpa, 2),
            'isHalftime': getattr(self, 'isHalftime', False),
            'isOvertime': self.currentQuarter > 4 if hasattr(self, 'currentQuarter') else False,
            'isUpsetAlert': isUpsetAlert,
            'gameStats': self._buildGameStatsSnapshot()
        }
        
        # Create and broadcast event
        event = GameEvent.gameState(gameId=self.id, gameState=gameStateData)
        broadcaster.broadcast_sync(self.id, event)
        
        # Update win probabilities for API access and next WPA calculation
        self.homeTeamWinProbability = newHomeWp
        self.awayTeamWinProbability = newAwayWp
        self.previousHomeWinProbability = newHomeWp
        self.previousAwayWinProbability = newAwayWp

        # Store WP and WPA in the most recent gameFeed play entry so the REST API can return it
        if self.gameFeed and 'play' in self.gameFeed[0]:
            self.gameFeed[0]['homeWinProbability'] = round(newHomeWp, 1)
            self.gameFeed[0]['awayWinProbability'] = round(newAwayWp, 1)
            # Only write WPA and isBigPlay on the play's own broadcast. Subsequent event
            # broadcasts (two-minute warning, quarter start, possession change, halftime, etc.)
            # share the same gameFeed[0] and would overwrite the play's real WPA with ~0.
            if 'homeWpa' not in self.gameFeed[0]:
                self.gameFeed[0]['homeWpa'] = round(homeWpa, 2)
                self.gameFeed[0]['awayWpa'] = round(awayWpa, 2)
                self.gameFeed[0]['isBigPlay'] = bool(abs(homeWpa) >= 10.0 or abs(awayWpa) >= 10.0)
    
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
        elif self.gameClockSeconds < TIMEOUT_CLOCK_THRESHOLD:  # Under 2 minutes
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

    def _shouldOnsideKick(self) -> bool:
        """
        Decide whether the kicking team should attempt an onside kick.
        Must be called from the kickoff handler, where:
          self.defensiveTeam = kicking team (just scored)
          self.offensiveTeam = receiving team
        """
        import random

        if self.currentQuarter >= 5:  # Never in OT
            return False
        if self.currentQuarter != 4:  # Only in Q4
            return False

        kickerScore = self.homeScore if self.defensiveTeam is self.homeTeam else self.awayScore
        receiverScore = self.homeScore if self.offensiveTeam is self.homeTeam else self.awayScore
        deficit = receiverScore - kickerScore

        if deficit <= 0:  # Not trailing
            return False

        # Coach aggressiveness: aggressive coaches try earlier and more consistently
        coach = getattr(self.defensiveTeam, 'coach', None)
        aggressNorm = (getattr(coach, 'aggressiveness', 80) - COACH_ATTR_NEUTRAL) / COACH_ATTR_RANGE  # -1.0 to +1.0

        # Time threshold: 4 min for any deficit, 8 min for large deficits (14+)
        # Aggressive coaches extend the window by up to 60s; conservative coaches shrink it
        baseThreshold = 480 if deficit >= 14 else 240
        timeThreshold = baseThreshold + int(aggressNorm * 60)
        if self.gameClockSeconds >= timeThreshold:
            return False

        # Base 75% → shifts to 60% (conservative) or 90% (aggressive)
        pct = max(0.40, min(0.95, 0.75 + aggressNorm * 0.15))
        return random.random() < pct

    def _shouldGoForTwo(self, scoringTeam: FloosTeam.Team) -> bool:
        """
        Decide whether to go for 2 instead of kicking the extra point.
        Only in Q4. The 6 TD points are already added before this is called.
        """
        import random
        if self.currentQuarter != 4:  # Q1-Q3: always kick; OT (>=5): always kick
            return False
        scoringScore = self.homeScore if scoringTeam is self.homeTeam else self.awayScore
        opponentScore = self.awayScore if scoringTeam is self.homeTeam else self.homeScore
        deficit = opponentScore - scoringScore  # positive = still trailing after TD
        if deficit <= 0:
            return False

        # Base probability by score deficit
        if deficit == 2:             basePct = 0.85  # Kick = down 1; 2-pt = tied
        elif deficit == 8:           basePct = 0.70  # Next TD + 2-pt can tie
        elif deficit in (11, 17, 20): basePct = 0.50  # Multi-score math works out
        elif 1 <= deficit <= 5:      basePct = 0.25  # Close game, occasional aggression
        else:                        return False

        # Coach aggressiveness shifts probability ±0.15
        coach = getattr(scoringTeam, 'coach', None)
        aggressNorm = (getattr(coach, 'aggressiveness', 80) - COACH_ATTR_NEUTRAL) / COACH_ATTR_RANGE  # -1.0 to +1.0
        pct = max(0.05, min(0.95, basePct + aggressNorm * 0.15))
        return random.random() < pct

    def _simulate2PointConversionPlay(self, scoringTeam: FloosTeam.Team, opposingTeam: FloosTeam.Team):
        """
        Simulate a 2-point conversion as a real run or pass play from the 2-yard line.
        Does NOT consume game clock. Broadcasts result as a separate play entry.
        """
        # Save game state
        savedOffensive = self.offensiveTeam
        savedDefensive = self.defensiveTeam
        savedYardsToEndzone = self.yardsToEndzone
        savedYardsToSafety = self.yardsToSafety
        savedDown = self.down
        savedYardsToFirstDown = self.yardsToFirstDown

        # Set up 2-yard-line state before snapshotting into Play()
        self.offensiveTeam = scoringTeam
        self.defensiveTeam = opposingTeam
        self.yardsToEndzone = 2
        self.yardsToSafety = FIELD_LENGTH - 2
        self.down = 1
        self.yardsToFirstDown = 2

        self.play = Play(self)

        # 60% pass, 40% run (2-pt conversions favor passing)
        if batched_randint(1, 10) <= 6:
            self.play.passPlay(self._selectPassPlay('short'))
        else:
            self.play.runPlay()

        twoPointGood = self.play.yardage >= 2
        if twoPointGood:
            self._addScore(scoringTeam, 2)
            self.play.playResult = PlayResult.Touchdown2PtGood
            self.play.scoreChange = True
        else:
            self.play.playResult = PlayResult.Touchdown2PtNoGood
            self.play.scoreChange = False

        self.play.homeTeamScore = self.homeScore
        self.play.awayTeamScore = self.awayScore

        self.formatPlayText()
        self.gameFeed.insert(0, {'play': self.play})
        if twoPointGood:
            self.highlights.insert(0, {'play': self.play})
            self.leagueHighlights.insert(0, {'play': self.play})
        self.broadcastGameState(includeLastPlay=True)

        # Restore game state (turnover() will reset field position, but restore for cleanliness)
        self.offensiveTeam = savedOffensive
        self.defensiveTeam = savedDefensive
        self.yardsToEndzone = savedYardsToEndzone
        self.yardsToSafety = savedYardsToSafety
        self.down = savedDown
        self.yardsToFirstDown = savedYardsToFirstDown

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
        if not self.twoMinuteWarningShown and self.gameClockSeconds <= TIMEOUT_CLOCK_THRESHOLD:
            if self.currentQuarter == 2 or self.currentQuarter == 4:
                self.twoMinuteWarningShown = True
                self.clockRunning = False
                # Two-minute warning is like a free timeout
                self.gameFeed.insert(0, {'event': {
                    'text': 'Two-Minute Warning',
                    'quarter': self.currentQuarter,
                    'timeRemaining': self.formatTime(self.gameClockSeconds)
                }})
                self.broadcastGameState(includeLastPlay=False, eventMessage={
                    'text': 'Two-Minute Warning',
                    'quarter': self.currentQuarter,
                    'timeRemaining': self.formatTime(self.gameClockSeconds)
                })
                self.broadcastGameState(includeLastPlay=False, eventMessage={
                    'text': 'Two-Minute Warning',
                    'quarter': self.currentQuarter,
                    'timeRemaining': self.formatTime(self.gameClockSeconds)
                })
    
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
        # Check status first - if already marked Final, game is definitely over
        if hasattr(self, 'status') and self.status == GameStatus.Final:
            return True
        
        # Game over if clock expired in regulation and not tied
        if self.currentQuarter == 4 and self.gameClockSeconds <= 0:
            return self.homeScore != self.awayScore
        
        # In OT (Q5+), check if game should end
        if self.currentQuarter >= 5:
            # Both teams must have had their guaranteed possession before game can end
            if self.homeScore != self.awayScore and self.otSecondPossComplete:
                return True
            # Clock expired and still tied — let advanceQuarter handle the new OT period
            if self.gameClockSeconds <= 0 and self.homeScore == self.awayScore:
                return False
        
        return False
    
    def calculateWinProbability(self) -> dict:
        """
        Calculate win probability for both teams using formula-based approach.
        Based on: ELO ratings, score differential, time remaining, possession, field position, down/distance
        Returns: {'home': float, 'away': float} percentages (0-100)
        """
        # Get total seconds remaining in game
        if self.currentQuarter == 1:
            total_seconds = self.gameClockSeconds + (3 * 900)  # Q1 + 3 more quarters
        elif self.currentQuarter == 2:
            total_seconds = self.gameClockSeconds + (2 * 900)  # Q2 + 2 more quarters
        elif self.currentQuarter == 3:
            total_seconds = self.gameClockSeconds + 900  # Q3 + Q4
        elif self.currentQuarter == 4:
            total_seconds = self.gameClockSeconds  # Q4 only
        else:  # Overtime
            total_seconds = self.gameClockSeconds  # OT period
        
        # Standard ELO pre-game win probability (properly calibrated)
        eloDiff = 0
        if self.homeTeamElo is not None and self.awayTeamElo is not None:
            eloDiff = self.homeTeamElo - self.awayTeamElo
        eloHomeWp = 100 / (1 + 10 ** (-eloDiff / 400))

        # Game progress: 0.0 at kickoff, 1.0 at end of regulation
        totalGameTime = 3600
        timeElapsed = totalGameTime - total_seconds
        gameProgress = min(1.0, timeElapsed / totalGameTime)

        # ELO weight: 1.0 pre-game (pure ELO baseline), decays smoothly to 0.05 by end
        # Stays meaningful through the first half, minor effect in Q4
        eloWeight = max(0.05, 1.0 - gameProgress * 0.95)

        # Score differential from home team's perspective
        scoreDiff = self.homeScore - self.awayScore

        # Expected points from current field position
        expectedPoints = self.calculateExpectedPoints()

        # Adjust expected points based on who has possession
        if self.offensiveTeam == self.homeTeam:
            homeExpected = expectedPoints
            awayExpected = 0
        else:
            homeExpected = 0
            awayExpected = expectedPoints

        # Scale EP by what fraction of the remaining game this single drive represents.
        # ~150 seconds per possession (both teams); early on EP is 1/24th of the picture,
        # on the last drive it's the whole picture.
        estimatedPossessions = max(1.0, total_seconds / 150.0)
        epWeight = 1.0 / estimatedPossessions
        # Dampen EP further when the score gap is large — a 3-point EP swing
        # shouldn't move WP much in a 21-point blowout.
        epDampener = 1.0 / (1.0 + (abs(scoreDiff) / 7.0) ** 1.5)
        adjustedScoreDiff = scoreDiff + (homeExpected - awayExpected) * epWeight * epDampener

        # Smooth time-sensitivity: k increases from 0.06 at kickoff to ~0.40 late in Q4
        # Power function avoids the discontinuous step jumps of the old approach
        k = 0.06 + (gameProgress ** 0.8) * 0.34

        # Score-based win probability via logistic
        scoreWp = 100 / (1 + np.exp(-k * adjustedScoreDiff))

        # Blend: ELO prior dominates pre-game, actual score dominates as game progresses
        homeWinProb = eloWeight * eloHomeWp + (1 - eloWeight) * scoreWp
        awayWinProb = 100 - homeWinProb

        # Overtime: if tied with possession, slight advantage based on field position
        if self.currentQuarter >= 5:
            if scoreDiff == 0:
                if self.offensiveTeam == self.homeTeam:
                    homeWinProb = 52 + (expectedPoints * 2)
                else:
                    awayWinProb = 52 + (expectedPoints * 2)
                homeWinProb = min(100, max(0, homeWinProb))
                awayWinProb = 100 - homeWinProb

        # Clamp to 0.1% - 99.9% (never show 0% or 100% unless game is actually over)
        if not self.isGameOver():
            homeWinProb = max(0.1, min(99.9, homeWinProb))
            awayWinProb = max(0.1, min(99.9, awayWinProb))
        else:
            if self.homeScore > self.awayScore:
                homeWinProb = 100
                awayWinProb = 0
            elif self.awayScore > self.homeScore:
                homeWinProb = 0
                awayWinProb = 100
            else:
                homeWinProb = 50
                awayWinProb = 50

        return {
            'home': round(homeWinProb, 1),
            'away': round(awayWinProb, 1)
        }
    
    def calculateExpectedPoints(self) -> float:
        """
        Calculate expected points from current field position and down/distance.
        Based on NFL expected points model - varies by field position and situation.
        Returns: Expected points for offensive team (can be negative near own endzone)
        """
        # After any scoring play, field position is stale (ball is about to be
        # placed for a kickoff). Return neutral EP so it doesn't inflate the WP.
        if hasattr(self, 'play') and self.play and getattr(self.play, 'scoreChange', False):
            return 0.0

        # Field position value (0 = own goal line, 100 = opponent goal line)
        field_position = 100 - self.yardsToEndzone

        # Smooth expected points via linear interpolation (avoids step-function
        # jumps at bracket boundaries that cause erratic WP swings on small gains).
        _ep_positions = [0,   5,   20,  40,  50,  60,  70,  80,  90,  100]
        _ep_values    = [-1.5, -1.0, 0.0, 1.0, 2.0, 2.5, 3.0, 3.5, 4.5, 5.5]
        base_ep = float(np.interp(field_position, _ep_positions, _ep_values))
        
        # Down/distance factor — smooth interpolation eliminates step-function jumps
        # at bracket boundaries (e.g., 2nd-and-3 vs 2nd-and-4 no longer a cliff).
        # In FG range (field_position >= 60), floor the factor — the team will
        # kick regardless of conversion odds, so down matters much less.
        inFgRange = field_position >= 60
        ytfd = self.yardsToFirstDown
        if self.down == 1:
            down_factor = 1.0
        elif self.down == 2:
            down_factor = float(np.interp(ytfd, [1, 3, 7, 10, 15], [0.95, 0.92, 0.82, 0.70, 0.60]))
            if inFgRange:
                down_factor = max(down_factor, 0.85)
        elif self.down == 3:
            down_factor = float(np.interp(ytfd, [1, 3, 7, 10, 15], [0.85, 0.70, 0.40, 0.25, 0.15]))
            if inFgRange:
                down_factor = max(down_factor, 0.75)
        else:  # 4th down
            if inFgRange:
                down_factor = 0.65
            else:
                down_factor = float(np.interp(ytfd, [1, 3, 7, 10], [0.15, 0.10, 0.05, 0.03]))
        
        expected_points = base_ep * down_factor
        
        return expected_points
    
    def checkOvertimeEnd(self) -> bool:
        """Check if scoring in OT should end the game.
        Both teams must have had a possession before a score can end the game."""
        if self.currentQuarter < 5:
            return False

        # Game ends on a score only after both teams have had their guaranteed possession
        if self.otSecondPossComplete and self.homeScore != self.awayScore:
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
        
        # Broadcast score update
        if BROADCASTING_AVAILABLE and broadcaster.is_enabled():
            event = GameEvent.scoreUpdate(
                gameId=self.id,
                homeScore=self.homeScore,
                awayScore=self.awayScore,
                scoringPlay={'team': team.abbr, 'points': points, 'quarter': self.currentQuarter}
            )
            broadcaster.broadcast_sync(self.id, event)


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
        if self.kicker is None:
            logging.error(f"Team {self.offense.name} has no kicker - field goal attempt treated as no good")
            self.isFgGood = False
            return
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
                self.kicker.updateInGameConfidence(.015)
            else:
                self.kicker.updateInGameConfidence(-.05)
        elif yardsToFG > 20 and yardsToFG <= 30:
            if self.isFgGood:
                self.kicker.updateInGameConfidence(.03)
            else:
                self.kicker.updateInGameConfidence(-.04)
        elif yardsToFG > 30 and yardsToFG <= 40:
            if self.isFgGood:
                self.kicker.updateInGameConfidence(.03)
            else:
                self.kicker.updateInGameConfidence(-.04)
        elif yardsToFG > 40 and yardsToFG <= 45:
            if self.isFgGood:
                self.kicker.updateInGameConfidence(.045)
            else:
                self.kicker.updateInGameConfidence(-.03)
        elif yardsToFG > 45 and yardsToFG <= 50:
            if self.isFgGood:
                self.kicker.updateInGameConfidence(.045)
            else:
                self.kicker.updateInGameConfidence(-.03)
        elif yardsToFG > 50 and yardsToFG <= 55:
            if self.isFgGood:
                self.kicker.updateInGameConfidence(.045)
            else:
                self.kicker.updateInGameConfidence(-.03)
        elif yardsToFG > 55 and yardsToFG <= 60:
            if self.isFgGood:
                self.kicker.updateInGameConfidence(.06)
            else:
                self.kicker.updateInGameConfidence(-.015)
        else:
            if self.isFgGood:
                self.kicker.updateInGameConfidence(.075)
            else:
                self.kicker.updateInGameConfidence(-.015)

        self.kicker.updateInGameRating()

    def extraPointTry(self, offense: FloosTeam.Team):
        self.kicker = offense.rosterDict['k']
        if self.kicker is None:
            logging.error(f"Team {offense.name} has no kicker - extra point treated as no good")
            self.isXpGood = False
            return
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

    def spike(self):
        """QB spikes the ball to stop the clock. Costs a down, clock stops, 0 yards."""
        self.playType = PlayType.Spike
        self.yardage = 0
        self.isPassCompletion = False
        self.game.clockRunning = False
        if self.game.down == 1:
            self.playResult = PlayResult.SecondDown
        elif self.game.down == 2:
            self.playResult = PlayResult.ThirdDown
        else:
            self.playResult = PlayResult.FourthDown

    def kneel(self):
        """QB kneels to drain the clock. Loses 1 yard, clock runs down ~40 seconds."""
        self.playType = PlayType.Kneel
        self.yardage = -1
        self.game.clockRunning = True
        clockDrain = min(40, self.game.gameClockSeconds)
        self.game.gameClockSeconds -= clockDrain
        if self.game.down == 1:
            self.playResult = PlayResult.SecondDown
        elif self.game.down == 2:
            self.playResult = PlayResult.ThirdDown
        else:
            self.playResult = PlayResult.FourthDown

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
        if self.runner is None:
            logging.error(f"Team {self.offense.name} has no RB - run play yields 0 yards")
            self.yardage = 0
            self.playResult = PlayResult.SecondDown
            return
        blocker: FloosPlayer.PlayerTE = self.offense.rosterDict['te']
        if blocker is None:
            logging.error(f"Team {self.offense.name} has no TE - run play using no blocking bonus")

        # Apply pressure modifier to runner's performance
        runnerPressureMod = self.runner.attributes.getPressureModifier(self.game.gamePressure)
        
        # STAGE 1: Calculate gap quality (like receiver openness)
        # Determine designed play gap — weighted by coach's offensive gameplan
        isHomePossession = (self.game.offensiveTeam == self.game.homeTeam)
        activeOffGameplan = self.game.homeOffGameplan if isHomePossession else self.game.awayOffGameplan
        if activeOffGameplan is not None:
            gapDist = dict(activeOffGameplan.gapDistribution)
            # Short yardage / goal line: power inside
            if self.game.yardsToFirstDown <= 2 or self.game.yardsToEndzone <= 5:
                gapDist = {'A-gap': 0.60, 'B-gap': 0.30, 'C-gap': 0.10}
            designedGapType = _random.choices(
                list(gapDist.keys()), weights=list(gapDist.values()), k=1
            )[0]
        else:
            designedGapType = batched_choice(['A-gap', 'B-gap', 'C-gap'])

        # Get per-play defensive scheme multipliers
        defGameplan = self.game.awayDefGameplan if isHomePossession else self.game.homeDefGameplan
        if GAMEPLAN_AVAILABLE and defGameplan is not None:
            offScoreDiff = (self.game.homeScore - self.game.awayScore if isHomePossession
                            else self.game.awayScore - self.game.homeScore)
            scheme = getDefensiveScheme(
                defGameplan, self.game.down, self.game.yardsToFirstDown,
                100 - self.game.yardsToEndzone, offScoreDiff,
                self.game.currentQuarter, self.game.gameClockSeconds
            )
        else:
            scheme = {'runDefMult': 1.0, 'passDefMult': 1.0, 'passRushMult': 1.0}
        effectiveRunDef = self.defense.defenseRunCoverageRating * scheme['runDefMult']

        # Track first-half run plays for halftime adjustment
        if self.game.currentQuarter <= 2:
            if isHomePossession:
                self.game.homeHalfRunPlays += 1
            else:
                self.game.awayHalfRunPlays += 1

        blockerRating = blocker.attributes.blocking if blocker else 50
        gapList = []
        for gapType in ['A-gap', 'B-gap', 'C-gap', 'bounce']:
            quality = self.calculateGapQuality(
                gapType,
                self.runner.attributes.power,
                self.runner.attributes.agility,
                blockerRating,
                effectiveRunDef
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
        
        stage1Offense = ((rbPowerRating * 0.8) + (blockerRating * 0.2)) + runnerPressureMod
        
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
            self.runner.updateInGameConfidence(.015)
            
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
                self.runner.updateInGameConfidence(-.05)
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
        if self.game.currentQuarter <= 2:
            if isHomePossession:
                self.game.homeHalfRunYards += self.yardage
            else:
                self.game.awayHalfRunYards += self.yardage

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
        if self.passer is None:
            logging.error(f"Team {self.offense.name} has no QB - pass play treated as incomplete")
            self.yardage = 0
            self.isPassCompletion = False
            self.playResult = PlayResult.SecondDown
            return
        self.receiver: FloosPlayer.PlayerWR = None
        self.selectedTarget = None
        self.blockingModifier = 0
        self.passType = None

        if passPlayBook[playKey]['targets']['te'] is None:
            te = self.offense.rosterDict['te']
            if te is not None:
                self.blockingModifier += te.attributes.blockingModifier
        if passPlayBook[playKey]['targets']['rb'] is None:
            rb = self.offense.rosterDict['rb']
            if rb is not None:
                self.blockingModifier += rb.attributes.blockingModifier

        # Get per-play defensive scheme multipliers
        isHomePossession = (self.game.offensiveTeam == self.game.homeTeam)
        defGameplan = self.game.awayDefGameplan if isHomePossession else self.game.homeDefGameplan
        if GAMEPLAN_AVAILABLE and defGameplan is not None:
            offScoreDiff = (self.game.homeScore - self.game.awayScore if isHomePossession
                            else self.game.awayScore - self.game.homeScore)
            scheme = getDefensiveScheme(
                defGameplan, self.game.down, self.game.yardsToFirstDown,
                100 - self.game.yardsToEndzone, offScoreDiff,
                self.game.currentQuarter, self.game.gameClockSeconds
            )
        else:
            scheme = {'runDefMult': 1.0, 'passDefMult': 1.0, 'passRushMult': 1.0}
        effectivePassRush = self.defense.defensePassRushRating * scheme['passRushMult']
        effectivePassDef = self.defense.defensePassCoverageRating * scheme['passDefMult']

        # Track first-half pass attempts for halftime adjustment
        if self.game.currentQuarter <= 2:
            if isHomePossession:
                self.game.homeHalfPassAttempts += 1
            else:
                self.game.awayHalfPassAttempts += 1

        # Calculate sack probability using probability curve
        qbMobility = round((self.passer.gameAttributes.agility + self.passer.gameAttributes.xFactor) / 2)
        sackProbability = self.calculateSackProbability(
            effectivePassRush,
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
                    openness = self.calculateReceiverOpenness(receiver, effectivePassDef)
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
                    if self.game.currentQuarter <= 2:
                        if isHomePossession:
                            self.game.homeHalfPassYards += self.yardage
                        else:
                            self.game.awayHalfPassYards += self.yardage

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

