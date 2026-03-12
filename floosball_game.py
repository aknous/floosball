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
    TIMEOUT_CLOCK_THRESHOLD, FG_SNAP_DISTANCE, FG_REASONABLE_RATIO, YARDS_TO_FIRST_DOWN,
    CLOSE_GAME_SCORE_THRESHOLD, CLUTCH_PRESSURE_THRESHOLD, CLUTCH_MODIFIER_THRESHOLD,
    RECEIVER_MATCHUP_SCALE,
    COACH_ATTR_NEUTRAL, COACH_ATTR_RANGE, COACH_OFFENSIVE_MIND_FLOOR,
    MOMENTUM_DECAY_RATE, MOMENTUM_BLOWOUT_DECAY_RATE, MOMENTUM_MIDGAP_DECAY_RATE,
    MOMENTUM_CASCADE_STEP, MOMENTUM_MAX_CASCADE, MOMENTUM_MAX_STREAK,
    MOMENTUM_EFFECT_BASE, MOMENTUM_EFFECT_CAP, MOMENTUM_NEUTRAL_ZONE,
    MOMENTUM_SHIFT_THRESHOLD, MOMENTUM_CROSS_ZERO_THRESHOLD, MOMENTUM_DISPLAY_THRESHOLD,
    MOMENTUM_TD, MOMENTUM_TURNOVER, MOMENTUM_SAFETY, MOMENTUM_TURNOVER_ON_DOWNS,
    MOMENTUM_FG_MISSED, MOMENTUM_FG_MADE, MOMENTUM_SACK, MOMENTUM_BIG_PLAY_BONUS,
    MOMENTUM_PUNT,
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

# Sideline pass text — args: (passer.name, text, receiver.name, yardage)
sidelineShortPassList = [
                    'quick out to',
                    'short sideline pass to',
                    'flips it to the boundary for',
                    'quick hitch to the sideline for',
                    'fires to the flat for',
                    'tosses it to the boundary for',
                ]

sidelineMidPassList = [
                    'fires to the sideline for',
                    'throws an out route to',
                    'hits the comeback route to',
                    'passes to the boundary for',
                    'throws to the sideline for',
                    'dials up the out route to',
                ]

sidelineLongPassList = [
                    'throws a deep sideline pass to',
                    'goes deep down the sideline to',
                    'launches it to the boundary for',
                    'airs it out along the sideline to',
                    'throws deep to the corner for',
                ]

# Clutch/choke play text suffixes — appended to standard play text
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

        # Momentum
        self.momentum = 0.0              # -100 to +100 (positive = home, negative = away)
        self.momentumStreak = 0          # consecutive events for same side, capped ±MAX_STREAK
        self.lastMomentumTeam = None     # team that last gained momentum

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


    def _coachClockIQ(self, coach) -> float:
        """Normalise clockManagement (60–100) to 0.0–1.0 for situational decision gates.

        0.0 = worst (attr 60), 0.5 = neutral (attr 80), 1.0 = best (attr 100).
        """
        if coach is None:
            return 0.5
        return max(0.0, min(1.0, (coach.clockManagement - 60) / 40))

    def _shouldTargetSideline(self, scoreDiff: int, coach) -> bool:
        """Decide whether this pass should target the sideline to stop the clock.

        Only fires when trailing/tied in Q2 or Q4. Probability scales with
        time urgency and coach clock management quality.
        """
        if scoreDiff > 0 or self.currentQuarter not in (2, 4):
            return False

        clockIQ = self._coachClockIQ(coach)
        secs = self.gameClockSeconds

        # Base probability by time urgency
        if secs < 120:
            baseProb = 0.70
        elif secs < 300:
            baseProb = 0.40
        else:
            baseProb = 0.15

        # Coach quality: bad coaches barely use sideline targeting
        coachScale = 0.3 + 0.7 * clockIQ

        # Reduce if team has timeouts available and plenty of time
        isHome = (self.offensiveTeam == self.homeTeam)
        timeoutsLeft = self.homeTimeoutsRemaining if isHome else self.awayTimeoutsRemaining
        if timeoutsLeft >= 2 and secs > 120:
            baseProb *= 0.5

        # Large deficits: need chunk plays over clock stops
        if scoreDiff < -16:
            baseProb *= 0.7

        return _random.random() < baseProb * coachScale

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

    def _checkDefensiveTimeout(self):
        """Defense calls timeout to stop the clock when trailing and the offense is milking clock."""
        if self.currentQuarter not in (2, 4):
            return
        if not self.clockRunning:
            return
        # Determine if the defensive team is trailing
        defIsHome = (self.defensiveTeam == self.homeTeam)
        defScore = self.homeScore if defIsHome else self.awayScore
        offScore = self.awayScore if defIsHome else self.homeScore
        if defScore >= offScore:
            return  # defense is winning or tied — no need
        deficit = offScore - defScore
        # Don't waste timeouts in an unwinnable game.
        # Under 60 sec: max 1 score (8 pts).  60-120 sec: max 2 scores (16 pts).
        maxComebackPts = 8 if self.gameClockSeconds <= 60 else 16
        if deficit > maxComebackPts:
            return
        defTimeouts = self.homeTimeoutsRemaining if defIsHome else self.awayTimeoutsRemaining
        if defTimeouts <= 0:
            return
        # Q4: under 2 min; Q2: under 30 sec (less aggressive at end of half)
        threshold = TIMEOUT_CLOCK_THRESHOLD if self.currentQuarter == 4 else 30
        if self.gameClockSeconds > threshold:
            return
        # Coach quality check — bad defensive coaches may not call timeout (floor 50%)
        defCoach = getattr(self.defensiveTeam, 'coach', None)
        defGameIQ = self._coachClockIQ(defCoach)
        if _random.random() >= 0.5 + 0.5 * defGameIQ:
            return
        # Call timeout
        if defIsHome:
            self.homeTimeoutsRemaining = max(0, self.homeTimeoutsRemaining - 1)
        else:
            self.awayTimeoutsRemaining = max(0, self.awayTimeoutsRemaining - 1)
        self.clockRunning = False
        self.gameFeed.insert(0, {'event': {
            'text': f'{self.defensiveTeam.name} calls timeout',
            'quarter': self.currentQuarter,
            'timeRemaining': self.formatTime(self.gameClockSeconds),
        }})

    def _runPassBias(self, gameplan) -> int:
        """Map runPassRatio (0.25–0.75) to threshold offset (-2 to +2) for batched_randint(1,10)."""
        if gameplan is None:
            return 0
        return round((gameplan.runPassRatio - 0.5) * 8)

    def _estimateFgProbability(self):
        """Estimate FG make probability for the current field position and kicker."""
        kicker = self.offensiveTeam.rosterDict.get('k')
        if not kicker:
            return 0.0
        fgDist = self.yardsToEndzone + FG_SNAP_DISTANCE
        baseFgProb = 1 / (1 + math.exp(0.18 * (fgDist - 52)))
        normalizedSkill = (kicker.gameAttributes.overallRating - 50) / 50
        fgProb = baseFgProb * (0.52 + normalizedSkill * 0.85)
        if fgDist < 30:
            fgProb = min(0.96, fgProb + 0.10)
        return max(0.05, min(0.96, fgProb))

    def _otPlayCaller(self, scoreDiff: int):
        """Handle play calling in overtime (Q5). Called only when currentQuarter == 5."""
        kicker = self.offensiveTeam.rosterDict.get('k')
        kickerMaxFg = (kicker.maxFgDistance - FG_SNAP_DISTANCE) if kicker else 0
        fgDistance = self.yardsToEndzone + FG_SNAP_DISTANCE
        fgProb = self._estimateFgProbability()

        # High-probability FG (>80%) — always kick in OT regardless of down
        if scoreDiff >= -3 and self.yardsToEndzone <= kickerMaxFg and fgProb >= 0.80:
            self.play.playType = PlayType.FieldGoal
            return

        if self.down == 4:
            reasonableMax = round(kicker.maxFgDistance * FG_REASONABLE_RATIO) if kicker else 0
            # Kick FG on 4th if in reasonable range and it ties or wins
            if scoreDiff >= -3 and self.yardsToEndzone <= kickerMaxFg and fgDistance <= reasonableMax:
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

        # Downs 1–3 in OT
        coach = getattr(self.offensiveTeam, 'coach', None)
        targetSideline = self._shouldTargetSideline(scoreDiff, coach)

        # Tied and in FG range: consider kicking now or playing conservatively
        reasonableFg = round(kicker.maxFgDistance * FG_REASONABLE_RATIO) if kicker else 0
        fgDist = self.yardsToEndzone + FG_SNAP_DISTANCE
        inFgRange = self.yardsToEndzone <= kickerMaxFg and fgDist <= reasonableFg
        if scoreDiff == 0 and inFgRange:
            # How easy is this FG? 1.0 = chip shot, 0.0 = at max range
            fgEase = max(0.0, (reasonableFg - fgDist) / reasonableFg) if reasonableFg > 0 else 0.0
            clockIQ = self._coachClockIQ(coach)
            # Chance to kick FG now — scales with proximity, down, and coach IQ
            downBase = {1: 0.05, 2: 0.15, 3: 0.40}.get(self.down, 0.05)
            fgChance = fgEase * (downBase + clockIQ * 0.25)
            if _random.random() < fgChance:
                self.play.playType = PlayType.FieldGoal
                return
            # Otherwise play conservatively — runs and short passes to protect the ball
            weights = {'run': 55.0, 'short': 30.0, 'medium': 15.0, 'long': 0.0}
            self._executeWeightedPlay(weights, targetSideline=targetSideline)
            return

        weights = self._computePlayWeights(scoreDiff, coach)
        self._executeWeightedPlay(weights, targetSideline=targetSideline)

    def _fourthDownCaller(self, scoreDiff: int, coach, isHome: bool):
        """Handle 4th down play calling."""
        # Set sideline targeting for any pass plays called in this method
        self.play.targetSideline = self._shouldTargetSideline(scoreDiff, coach)

        # Don't punt from own territory if trailing in Q4 under 60 sec — should go for it
        # Bad coaches may still punt here (floor 50%)
        if self.yardsToSafety <= 35:
            isLateGameDesperation = (self.currentQuarter == 4 and scoreDiff < 0
                                     and self.gameClockSeconds < 60)
            if not isLateGameDesperation:
                self.play.playType = PlayType.Punt
                return
            gameIQ = self._coachClockIQ(coach)
            if _random.random() >= 0.5 + 0.5 * gameIQ:
                # Bad coach punts in desperation — terrible decision
                self.play.playType = PlayType.Punt
                return

        kicker = self.offensiveTeam.rosterDict.get('k')
        kickerMaxDistance = (kicker.maxFgDistance - FG_SNAP_DISTANCE) if kicker else 0
        reasonableMax = round(kicker.maxFgDistance * FG_REASONABLE_RATIO) if kicker else 0
        fgDistance = self.yardsToEndzone + FG_SNAP_DISTANCE
        inFieldGoalRange = self.yardsToEndzone <= kickerMaxDistance and fgDistance <= reasonableMax

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
            deficit = abs(scoreDiff)
            aggrNorm = (coach.aggressiveness - COACH_ATTR_NEUTRAL) / COACH_ATTR_RANGE if coach else 0.0
            if self.currentQuarter == 4 and self.gameClockSeconds < TIMEOUT_CLOCK_THRESHOLD:
                gameIQ = self._coachClockIQ(coach)
                if deficit <= 3:
                    # FG ties or wins — chip shots are automatic, longer FGs nearly so
                    if self.yardsToEndzone <= 10:
                        # Inside the 10: always kick the chip shot
                        self.play.playType = PlayType.FieldGoal
                        return
                    if _random.random() < 0.9 + 0.1 * gameIQ:
                        self.play.playType = PlayType.FieldGoal
                        return
                    # Bad coach blunder: goes for TD instead of makeable FG
                    if self.yardsToFirstDown <= 5:
                        self.play.passPlay(self._selectPassPlay('short'))
                    else:
                        self.play.passPlay(self._selectPassPlay('medium'))
                    return
                elif deficit <= 8:
                    # Down 4-8: FG doesn't tie — need a TD eventually
                    # With more time, bad coaches may still settle for FG to "stay close"
                    # As time dwindles, FG becomes pointless — below 45 sec, no one kicks
                    secs = self.gameClockSeconds
                    if secs >= 45:
                        timeFactor = (secs - 45) / (TIMEOUT_CLOCK_THRESHOLD - 45)
                        # Bad coaches (low IQ) more likely to settle; good coaches go for TD
                        fgChance = timeFactor * max(0.0, 0.35 - 0.3 * gameIQ)
                        if _random.random() < fgChance:
                            self.play.playType = PlayType.FieldGoal
                            return
                    # Go for TD
                    if self.yardsToFirstDown <= 5:
                        self.play.passPlay(self._selectPassPlay('short'))
                    elif self.yardsToFirstDown <= 10:
                        self.play.passPlay(self._selectPassPlay('medium'))
                    else:
                        self.play.passPlay(self._selectPassPlay('long'))
                    return
                else:
                    # Down 9+: FG is almost meaningless, go for TD
                    # Only very conservative coaches would kick here
                    if aggrNorm < -0.5:
                        self.play.playType = PlayType.FieldGoal
                        return
                    if self.yardsToFirstDown <= 5:
                        self.play.passPlay(self._selectPassPlay('medium'))
                    else:
                        self.play.passPlay(self._selectPassPlay('long'))
                    return
            # Outside late Q4: standard FG logic
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
                # Under 60 sec trailing: should go for it, but bad coaches may punt
                gameIQ = self._coachClockIQ(coach)
                if self.gameClockSeconds < 60 and _random.random() < 0.5 + 0.5 * gameIQ:
                    if self.yardsToFirstDown <= 3:
                        self.play.passPlay(self._selectPassPlay('short'))
                    elif self.yardsToFirstDown <= 10:
                        self.play.passPlay(self._selectPassPlay('medium'))
                    else:
                        self.play.passPlay(self._selectPassPlay('long'))
                    return
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

        weights = self._applySituationalMods(weights, scoreDiff, coach)
        weights = self._applyMatchupMods(weights, coach)
        weights = self._applyCoachMods(weights, coach)
        return weights

    def _applySituationalMods(self, weights: dict, scoreDiff: int, coach=None) -> dict:
        """Apply game-state multipliers: quarter, score, clock, field position.

        clockManagement scales how strongly the coach reacts to game situation.
        A bad clock-management coach (clockIQ~0) applies only ~40% of the optimal
        situational shift; a great coach (clockIQ~1) applies the full adjustment.
        """
        q = self.currentQuarter
        secs = self.gameClockSeconds
        # Scale factor: how much of the situational adjustment applies
        # clockIQ 0.0 → 0.4 (bad coach barely adjusts), 1.0 → 1.0 (full adjustment)
        clockIQ = self._coachClockIQ(coach)
        sit = 0.4 + 0.6 * clockIQ

        if q == 4 and scoreDiff < 0:
            if secs < 120:
                weights['run'] *= 1 + (0.1 - 1) * sit       # optimal: ×0.1
                weights['short'] *= 1 + (1.3 - 1) * sit     # optimal: ×1.3
                weights['medium'] *= 1 + (1.8 - 1) * sit    # optimal: ×1.8
                weights['long'] *= 1 + (2.5 - 1) * sit      # optimal: ×2.5
            elif secs < 300:
                weights['run'] *= 1 + (0.3 - 1) * sit
                weights['medium'] *= 1 + (1.5 - 1) * sit
                weights['long'] *= 1 + (1.8 - 1) * sit
            else:
                weights['run'] *= 1 + (0.6 - 1) * sit
                weights['medium'] *= 1 + (1.2 - 1) * sit
                weights['long'] *= 1 + (1.3 - 1) * sit

        if q == 4 and scoreDiff > 0:
            weights['run'] *= 1 + (1.6 - 1) * sit
            weights['long'] *= 1 + (0.3 - 1) * sit
            weights['medium'] *= 1 + (0.7 - 1) * sit

        if q == 3 and scoreDiff < -10:
            weights['run'] *= 1 + (0.7 - 1) * sit
            weights['medium'] *= 1 + (1.2 - 1) * sit
            weights['long'] *= 1 + (1.4 - 1) * sit

        # Field position adjustments — not clock-related, always full strength
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

    def _executeWeightedPlay(self, weights: dict, targetSideline: bool = False):
        """Sample from the weight distribution and execute the chosen play."""
        play = _random.choices(
            ['run', 'short', 'medium', 'long'],
            weights=[weights['run'], weights['short'], weights['medium'], weights['long']]
        )[0]
        if play == 'run':
            self.play.runPlay()
        else:
            self.play.targetSideline = targetSideline
            self.play.passPlay(self._selectPassPlay(play))

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
                # Defense won't waste TOs in unwinnable games (matches _checkDefensiveTimeout)
                maxComebackPts = 8 if self.gameClockSeconds <= 60 else 16
                effectiveOppTos = oppTimeouts if scoreDiff <= maxComebackPts else 0
                # TO'd kneels still drain 4s (snap time); free kneels drain full ~40s
                toadKneels = min(effectiveOppTos, availableKneels)
                freeKneels = availableKneels - toadKneels
                drainableSeconds = toadKneels * 4 + freeKneels * KNEEL_DRAIN_SECONDS
                if drainableSeconds >= self.gameClockSeconds:
                    self.play.kneel()
                    return
            # Coach game-management quality gates all situational decisions below.
            # Good coaches (IQ~1.0) almost always make the right call.
            # Bad coaches (IQ~0.0) frequently miss the correct situational play.
            gameIQ = self._coachClockIQ(coach)

            # Desperation FG: trailing by ≤3, in FG range, very little time — kick NOW
            if (self.currentQuarter in (2, 4) and -3 <= scoreDiff < 0
                    and self.gameClockSeconds <= 30):
                kicker = self.offensiveTeam.rosterDict.get('k')
                kickerMax = (kicker.maxFgDistance - FG_SNAP_DISTANCE) if kicker else 0
                reasonableMax = round(kicker.maxFgDistance * FG_REASONABLE_RATIO) if kicker else 0
                fgDistance = self.yardsToEndzone + FG_SNAP_DISTANCE
                if self.yardsToEndzone <= kickerMax:
                    # Only attempt very long FGs if there's truly no time for another play
                    if fgDistance > reasonableMax and self.gameClockSeconds > 8:
                        pass  # Skip — try to get closer first
                    elif _random.random() < 0.6 + 0.4 * gameIQ:
                        self.play.playType = PlayType.FieldGoal
                        return
            # Spike: Q4 or Q2, clock running, no timeouts, trailing/tied, ≤45 sec
            if (self.currentQuarter in (2, 4) and self.clockRunning
                    and self.gameClockSeconds <= SPIKE_CLOCK_THRESHOLD
                    and timeoutsLeft == 0 and scoreDiff <= 0):
                # Bad coaches may fail to spike and just run a normal play (floor 50%)
                if _random.random() < 0.5 + 0.5 * gameIQ:
                    self.play.spike()
                    return
            # Call timeout (offense): Q4 or Q2, trailing/tied, clock running, timeouts available
            if (self.currentQuarter in (2, 4) and scoreDiff <= 0 and self.clockRunning
                    and timeoutsLeft > 0 and self.gameClockSeconds <= TIMEOUT_CLOCK_THRESHOLD):
                # Bad coaches may forget to call timeout (floor 50%)
                if _random.random() < 0.5 + 0.5 * gameIQ:
                    self._callTimeout(isHome)
                # fall through — still need to call a play

        # Overtime
        if self.currentQuarter == 5:
            self._otPlayCaller(scoreDiff)
            return

        # End-of-half / end-of-game FG attempts — compute kicker range once
        kicker = self.offensiveTeam.rosterDict.get('k')
        kickerMaxFg = (kicker.maxFgDistance - FG_SNAP_DISTANCE) if kicker else 0

        # End-of-half FG attempt (only if reasonable distance)
        reasonableMax = round(kicker.maxFgDistance * FG_REASONABLE_RATIO) if kicker else 0
        if self.currentQuarter == 2 and self.gameClockSeconds < TIMEOUT_CLOCK_THRESHOLD and self.down == 4:
            fgDistance = self.yardsToEndzone + FG_SNAP_DISTANCE
            if self.yardsToEndzone <= kickerMaxFg and fgDistance <= reasonableMax:
                self.play.playType = PlayType.FieldGoal
                return

        # End-of-game FG attempt (tied, leading by ≤3, or trailing by ≤3)
        if self.currentQuarter == 4 and self.gameClockSeconds < TIMEOUT_CLOCK_THRESHOLD and self.down == 4:
            fgDistance = self.yardsToEndzone + FG_SNAP_DISTANCE
            if -3 <= scoreDiff <= 3 and self.yardsToEndzone <= kickerMaxFg and fgDistance <= reasonableMax:
                self.play.playType = PlayType.FieldGoal
                return

        # 4th down
        if self.down == 4:
            self._fourthDownCaller(scoreDiff, coach, isHome)
            return

        # Downs 1–3: weighted probability sampling
        weights = self._computePlayWeights(scoreDiff, coach)
        targetSideline = self._shouldTargetSideline(scoreDiff, coach)
        self._executeWeightedPlay(weights, targetSideline=targetSideline)

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
        self._evaluateClutchChoke()
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
                if self.play.targetSideline:
                    if self.play.passType is PassType.short:
                        text = '{} {} {} for {} yards'.format(self.play.passer.name, choice(sidelineShortPassList), self.play.receiver.name, self.play.yardage)
                    elif self.play.passType is PassType.long:
                        text = '{} {} {} for {} yards'.format(self.play.passer.name, choice(sidelineLongPassList), self.play.receiver.name, self.play.yardage)
                    else:
                        text = '{} {} {} for {} yards'.format(self.play.passer.name, choice(sidelineMidPassList), self.play.receiver.name, self.play.yardage)
                    if not self.play.isInBounds:
                        text += ', out of bounds'
                elif self.play.passType is PassType.short:
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

    def _evaluateClutchChoke(self):
        """Evaluate whether the current play qualifies as a clutch or choke moment."""
        play = self.play
        if play.gamePressure < CLUTCH_PRESSURE_THRESHOLD:
            return

        # For pass plays, determine key player based on outcome
        if play.playType == PlayType.Pass:
            if play.isPassCompletion or play.isTd:
                # Completion: credit whichever of QB/receiver had larger positive mod
                if play.rcvPressureMod > play.qbPressureMod and play.rcvPressureMod >= CLUTCH_MODIFIER_THRESHOLD:
                    play.keyPressureMod = play.rcvPressureMod
                    play.clutchPlayerName = play.receiver.name if play.receiver else ''
                else:
                    play.keyPressureMod = play.qbPressureMod
                    play.clutchPlayerName = play.passer.name if play.passer else ''
            elif play.passIsDropped:
                # Drop: receiver choked
                play.keyPressureMod = play.rcvPressureMod
                play.clutchPlayerName = play.receiver.name if play.receiver else ''
            else:
                # INT, sack, incomplete: QB responsibility
                play.keyPressureMod = play.qbPressureMod
                play.clutchPlayerName = play.passer.name if play.passer else ''

        if abs(play.keyPressureMod) < CLUTCH_MODIFIER_THRESHOLD:
            return

        isPositiveOutcome = (
            play.isPassCompletion or play.isTd or play.isFgGood
            or play.playResult == PlayResult.FirstDown
        )
        isNegativeOutcome = (
            play.isInterception or play.isFumbleLost or play.isSack
            or play.passIsDropped
            or (play.playType == PlayType.FieldGoal and not play.isFgGood)
            or (play.playType == PlayType.Run and play.yardage <= 0)
        )

        if play.keyPressureMod >= CLUTCH_MODIFIER_THRESHOLD and isPositiveOutcome:
            play.isClutchPlay = True
        elif play.keyPressureMod <= -CLUTCH_MODIFIER_THRESHOLD and isNegativeOutcome:
            play.isChokePlay = True

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

    def _processPlayerPostgame(self):
        """Process player stats after game: sync dicts, update confidence/ratings, compute derived stats"""
        # Sync optimized stat_tracker data to legacy dicts for all players
        for player in self.homeTeam.rosterDict.values():
            if player:
                player.sync_stats_dicts()
        for player in self.awayTeam.rosterDict.values():
            if player:
                player.sync_stats_dicts()

        # Per-player: update confidence/determination, increment gamesPlayed, compute derived stats
        for player in self.homeTeam.rosterDict.values():
            if player:
                player.postgameChanges()
                self._accumulatePostgameStats(player)
        for player in self.awayTeam.rosterDict.values():
            if player:
                player.postgameChanges()
                self._accumulatePostgameStats(player)

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
            self._accumulatePostgameStats(player)


        for player in self.awayTeam.rosterDict.values():
            player.postgameChanges()
            self._accumulatePostgameStats(player)

    def _accumulatePostgameStats(self, player):
        """Accumulate postgame stats for season, career, and compute derived fields"""
        gd = player.gameStatsDict
        sd = player.seasonStatsDict
        cd = player.careerStatsDict

        # Fantasy points: game → season and career (regular season only)
        if self.isRegularSeasonGame:
            # Preserve game FP for DB persistence (_saveGameToDatabase reads this
            # after playGame() returns, by which time gameStatsDict is zeroed)
            player._lastGameFantasyPoints = gd['fantasyPoints']
            sd['fantasyPoints'] += gd['fantasyPoints']
            cd['fantasyPoints'] += gd['fantasyPoints']
            # Clear game FP after merge so _getPlayerLiveFantasyPoints()
            # (which sums season + game) doesn't double-count between games
            gd['fantasyPoints'] = 0

        # Game-level derived stats (always computed)
        if gd['passing']['att'] > 0 and gd['passing']['comp'] > 0:
            gd['passing']['ypc'] = round(gd['passing']['yards'] / gd['passing']['comp'], 2)
            gd['passing']['compPerc'] = round((gd['passing']['comp'] / gd['passing']['att']) * 100)

        if gd['receiving']['receptions'] > 0 and gd['receiving']['yards'] > 0:
            gd['receiving']['ypr'] = round(gd['receiving']['yards'] / gd['receiving']['receptions'], 2)
            gd['receiving']['rcvPerc'] = round((gd['receiving']['receptions'] / gd['receiving']['targets']) * 100)

        if gd['rushing']['carries'] > 0:
            gd['rushing']['ypc'] = round(gd['rushing']['yards'] / gd['rushing']['carries'], 2)

        if gd['kicking']['fgAtt'] > 0:
            if gd['kicking']['fgs'] > 0:
                gd['kicking']['fgPerc'] = round((gd['kicking']['fgs'] / gd['kicking']['fgAtt']) * 100)
            else:
                gd['kicking']['fgPerc'] = 0

        if not self.isRegularSeasonGame:
            return

        # Season-level: accumulate non-tracked fields and compute derived stats
        for statGroup in ['passing', 'rushing', 'receiving', 'kicking']:
            if '20+' in gd.get(statGroup, {}) and '20+' in sd.get(statGroup, {}):
                sd[statGroup]['20+'] += gd[statGroup]['20+']
            if 'longest' in gd.get(statGroup, {}) and 'longest' in sd.get(statGroup, {}):
                if gd[statGroup]['longest'] > sd[statGroup]['longest']:
                    sd[statGroup]['longest'] = gd[statGroup]['longest']
            # Career longest
            if 'longest' in gd.get(statGroup, {}) and 'longest' in cd.get(statGroup, {}):
                if gd[statGroup]['longest'] > cd[statGroup]['longest']:
                    cd[statGroup]['longest'] = gd[statGroup]['longest']
            # Career 20+
            if '20+' in gd.get(statGroup, {}) and '20+' in cd.get(statGroup, {}):
                cd[statGroup]['20+'] += gd[statGroup]['20+']

        # Season derived percentages
        self._computeDerivedStats(sd)
        # Career derived percentages
        self._computeDerivedStats(cd)

        # Season/career kicking distance breakdowns
        for statsDict in [sd, cd]:
            kicking = statsDict.get('kicking', {})
            if kicking.get('fgs', 0) > 0:
                if kicking.get('fgYards', 0) > 0:
                    kicking['fgAvg'] = round(kicking['fgYards'] / kicking['fgs'])
                for prefix in ['fgUnder20', 'fg20to40', 'fg40to50', 'fgOver50']:
                    att = kicking.get(f'{prefix}att', 0)
                    made = kicking.get(prefix, 0)
                    kicking[f'{prefix}perc'] = round((made / att) * 100) if att > 0 else 'N/A'
            elif kicking.get('fgAtt', 0) > 0:
                kicking['fgPerc'] = 0

    @staticmethod
    def _computeDerivedStats(statsDict):
        """Compute percentage and per-unit stats from raw counting stats"""
        p = statsDict.get('passing', {})
        if p.get('comp', 0) > 0 and p.get('att', 0) > 0:
            p['ypc'] = round(p['yards'] / p['comp'], 2)
            p['compPerc'] = round((p['comp'] / p['att']) * 100)

        r = statsDict.get('receiving', {})
        if r.get('receptions', 0) > 0 and r.get('targets', 0) > 0:
            r['ypr'] = round(r['yards'] / r['receptions'], 2)
            r['rcvPerc'] = round((r['receptions'] / r['targets']) * 100)

        ru = statsDict.get('rushing', {})
        if ru.get('carries', 0) > 0:
            ru['ypc'] = round(ru['yards'] / ru['carries'], 2)

        k = statsDict.get('kicking', {})
        if k.get('fgAtt', 0) > 0 and k.get('fgs', 0) > 0:
            k['fgPerc'] = round((k['fgs'] / k['fgAtt']) * 100)
        if k.get('xpAtt', 0) > 0 and k.get('xps', 0) > 0:
            k['xpPerc'] = round((k['xps'] / k['xpAtt']) * 100)

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
                    if self.play.isFumbleLost or self.play.isInterception or self.play.scoreChange or self.play.yardage >= 30 or self.play.isClutchPlay or self.play.isChokePlay or self.play.isMomentumShift:
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

                    # Halftime dampens momentum toward neutral
                    self.momentum *= 0.5
                    self.momentumStreak = 0
                    if abs(self.momentum) < 0.5:
                        self.momentum = 0.0

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
                    if self.play.isFumbleLost or self.play.isInterception or self.play.scoreChange or self.play.yardage >= 30 or self.play.isClutchPlay or self.play.isChokePlay or self.play.isMomentumShift:
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

                # POST-PLAY: Defense can call timeout to stop the clock
                self._checkDefensiveTimeout()

                # Recalculate game pressure before each play
                self.gamePressure = self.calculateGamePressure()

                # Momentum: decay toward neutral and apply gameplay effect
                self._decayMomentum()
                self._applyMomentumEffect()

                # Call and execute play
                self.playCaller()

                # PRE-SNAP: Consume huddle/snap time AFTER play type is known.
                # Skip for kneels and spikes — they handle their own clock internally.
                if self.clockRunning and self.play.playType not in (PlayType.Kneel, PlayType.Spike):
                    preSnapTime = self.calculatePreSnapTime()
                    self.consumeGameTime(preSnapTime)
                    self.checkTwoMinuteWarning()

                    # Check if clock expired during pre-snap
                    if self.gameClockSeconds <= 0:
                        break
                self.totalPlays += 1
                self.play.playNumber = self.totalPlays
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
                    self.play.timeRemaining = self.formatTime(self.gameClockSeconds)
                    self.checkTwoMinuteWarning()

                    if self.play.isFgGood:
                        self._addScore(self.offensiveTeam, 3)
                        self._applyMomentumEvent(MOMENTUM_FG_MADE, self.offensiveTeam)
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
                        self._applyMomentumEvent(MOMENTUM_FG_MISSED, self.defensiveTeam)
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
                    self._applyMomentumEvent(MOMENTUM_PUNT, self.defensiveTeam)
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
                    self.play.timeRemaining = self.formatTime(self.gameClockSeconds)
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

                    # After kneel: defense gets a chance to call timeout before play clock drains
                    if self.play.playType is PlayType.Kneel:
                        self._checkDefensiveTimeout()
                        logging.warning(f"[KNEEL] clockRunning={self.clockRunning}, gameClockSeconds={self.gameClockSeconds}")
                        if self.clockRunning and self.gameClockSeconds > 0:
                            # No timeout called — drain the play clock (time between plays)
                            playClockDrain = min(36, self.gameClockSeconds)
                            logging.warning(f"[KNEEL] Draining play clock: {playClockDrain}s, clock will be {self.gameClockSeconds - playClockDrain}")
                            self.consumeGameTime(playClockDrain)
                            self.checkTwoMinuteWarning()
                        else:
                            logging.warning(f"[KNEEL] Play clock drain SKIPPED")

                    # Fall through to outcome section so the down is advanced correctly

                # POST-PLAY: Consume play duration time (run/pass only — kneel/spike handle their own clock)
                if self.play.playType not in (PlayType.Kneel, PlayType.Spike):
                    playDuration = self.calculatePlayDuration(self.play.playType, self.play.isInBounds)
                    self.consumeGameTime(playDuration)

                # Update play's timeRemaining to reflect post-play clock
                self.play.timeRemaining = self.formatTime(self.gameClockSeconds)

                # Determine if clock should run after play
                self.clockRunning = self.shouldClockRun()
                
                # Check for two-minute warning
                self.checkTwoMinuteWarning()

                # Momentum: sack (only if not also a fumble — fumbles get turnover momentum)
                if self.play.isSack and not self.play.isFumbleLost:
                    self._applyMomentumEvent(MOMENTUM_SACK, self.defensiveTeam)

                # Handle turnovers
                if self.play.isFumbleLost or self.play.isInterception:
                    self._applyMomentumEvent(MOMENTUM_TURNOVER, self.defensiveTeam)
                    self.defensiveTeam.gameDefenseStats['fantasyPoints'] += 2
                    if self.offensiveTeam is self.homeTeam:
                        self.homeTurnoversTotal += 1
                    elif self.offensiveTeam is self.awayTeam:
                        self.awayTurnoversTotal += 1
                    self.formatPlayText()
                    if self.play.isFumbleLost or self.play.isInterception or self.play.scoreChange or self.play.yardage >= 30 or self.play.isClutchPlay or self.play.isChokePlay or self.play.isMomentumShift:
                        self.highlights.insert(0, {'play': self.play})
                        self.leagueHighlights.insert(0, {'play': self.play})
                    self.gameFeed.insert(0, {'play': self.play})

                    if self.play.yardage >= self.yardsToEndzone:
                        self.broadcastGameState(includeLastPlay=True)
                        self.turnover(self.offensiveTeam, self.defensiveTeam, possReset)
                    elif (self.yardsToSafety + self.play.yardage) <= 0:
                        self._addScore(self.defensiveTeam, 6)
                        self._applyMomentumEvent(MOMENTUM_TD, self.defensiveTeam)

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
                        self._applyMomentumEvent(MOMENTUM_TD, self.offensiveTeam)

                        if self._shouldGoForTwo(self.offensiveTeam):
                            # Broadcast TD first, then simulate 2-pt as a separate play
                            self.play.playResult = PlayResult.Touchdown
                            self.play.scoreChange = True
                            self.play.homeTeamScore = self.homeScore
                            self.play.awayTeamScore = self.awayScore
                            self.formatPlayText()
                            if self.play.isFumbleLost or self.play.isInterception or self.play.scoreChange or self.play.yardage >= 30 or self.play.isClutchPlay or self.play.isChokePlay or self.play.isMomentumShift:
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
                            if self.play.isFumbleLost or self.play.isInterception or self.play.scoreChange or self.play.yardage >= 30 or self.play.isClutchPlay or self.play.isChokePlay or self.play.isMomentumShift:
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
                            self._applyMomentumEvent(MOMENTUM_TD, self.defensiveTeam)

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
                            self._applyMomentumEvent(MOMENTUM_SAFETY, self.defensiveTeam)

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
                            self._applyMomentumEvent(MOMENTUM_TURNOVER_ON_DOWNS, self.defensiveTeam)
                            self.turnover(self.offensiveTeam, self.defensiveTeam, self.yardsToSafety)
                            break
        
        # Game over - ensure the final play is formatted, in gameFeed, and broadcast.
        # Scoring plays and special plays (FG, punt, TD) are typically formatted and
        # added to gameFeed inside the loop. Non-scoring plays (kneels, normal runs/passes
        # at clock expiration) are normally formatted at the TOP of the next loop iteration,
        # which never runs when the game ends. Handle all cases here.
        alreadyInFeed = (self.gameFeed and self.gameFeed[0].get('play') is self.play)
        if self.totalPlays > 0 and self.play:
            playActuallyRan = getattr(self.play, 'playResult', None) is not None
            if playActuallyRan and not alreadyInFeed:
                if not getattr(self.play, 'playText', None):
                    self.formatPlayText()
                if self.play.isSack:
                    self.defensiveTeam.gameDefenseStats['fantasyPoints'] += 1
                if self.play.isFumbleLost or self.play.isInterception or self.play.scoreChange or self.play.yardage >= 30 or self.play.isClutchPlay or self.play.isChokePlay or self.play.isMomentumShift:
                    self.highlights.insert(0, {'play': self.play})
                    self.leagueHighlights.insert(0, {'play': self.play})
                self.gameFeed.insert(0, {'play': self.play})

                # Broadcast final play state (before the game-end event below)
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
        # Player postgame processing: sync stats, update confidence/determination, compute derived stats
        self._processPlayerPostgame()
        
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

        # Score differential pressure (0-30), scaled by quarter so early-game ties
        # don't generate clutch/choke moments
        score_diff = abs(self.homeScore - self.awayScore)
        scorePressure = 0
        if score_diff == 0:
            scorePressure = 30  # Tie game
        elif score_diff <= 3:
            scorePressure = 25  # One field goal difference
        elif score_diff <= 7:
            scorePressure = 20  # One possession game
        elif score_diff <= 14:
            scorePressure = 10  # Two possession game

        # Scale score pressure by quarter: Q1=25%, Q2=50%, Q3=75%, Q4/OT=100%
        quarterScale = {1: 0.25, 2: 0.5, 3: 0.75, 4: 1.0, 5: 1.0}
        pressure += scorePressure * quarterScale.get(self.currentQuarter, 1.0)

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

    # ─── Momentum System ────────────────────────────────────────────────────

    def _decayMomentum(self):
        """Decay momentum toward neutral each play."""
        scoreDiff = abs(self.homeScore - self.awayScore)
        if scoreDiff > 21:
            decayRate = MOMENTUM_BLOWOUT_DECAY_RATE
        elif scoreDiff > 14:
            decayRate = MOMENTUM_MIDGAP_DECAY_RATE
        else:
            decayRate = MOMENTUM_DECAY_RATE
        self.momentum *= (1.0 - decayRate)
        if abs(self.momentum) < 0.5:
            self.momentum = 0.0

    def _scoreGapDampener(self):
        """Reduce momentum gains in blowouts. Returns 0.2-1.0."""
        scoreDiff = abs(self.homeScore - self.awayScore)
        if scoreDiff <= 14:
            return 1.0
        elif scoreDiff <= 21:
            return 0.7
        elif scoreDiff <= 28:
            return 0.4
        return 0.2

    def _mentalResistance(self, resistingTeam):
        """High mental stats on the resisting team reduce incoming momentum.
        Returns 0.7-1.0 (lower = more resistance)."""
        players = [p for p in resistingTeam.rosterDict.values() if p is not None]
        if not players:
            return 1.0
        avgMental = sum(
            (getattr(p.attributes, 'resilience', 70) +
             getattr(p.attributes, 'attitude', 70) +
             getattr(p.attributes, 'discipline', 70)) / 3.0
            for p in players
        ) / len(players)
        resistance = 1.0 - 0.3 * ((avgMental - 60) / 40.0)
        return max(0.7, min(1.0, resistance))

    def _updateMomentumStreak(self, benefitingTeam):
        """Track consecutive momentum events for the same team."""
        if benefitingTeam is self.lastMomentumTeam:
            if benefitingTeam is self.homeTeam:
                self.momentumStreak = min(self.momentumStreak + 1, MOMENTUM_MAX_STREAK)
            else:
                self.momentumStreak = max(self.momentumStreak - 1, -MOMENTUM_MAX_STREAK)
        else:
            self.momentumStreak = 1 if benefitingTeam is self.homeTeam else -1
            self.lastMomentumTeam = benefitingTeam

    def _isMomentumShift(self, previousMomentum, newMomentum):
        """Check if a momentum change qualifies as a highlight.

        A momentum shift should represent a dramatic change in who controls the
        game — not routine scoring by a team already dominating.  We require
        either (a) a zero-crossing (actual lead-change in momentum), or (b) a
        large swing that moves *against* the prevailing momentum direction.
        Piling-on events (same direction the momentum is already going) are
        never flagged, no matter how big the raw delta.
        """
        delta = abs(newMomentum - previousMomentum)
        crossedZero = (previousMomentum > 0 and newMomentum < 0) or \
                      (previousMomentum < 0 and newMomentum > 0)

        # Zero-crossing is the clearest shift — the tide literally turned
        if crossedZero and delta >= MOMENTUM_CROSS_ZERO_THRESHOLD:
            return True

        # Non-crossing: only flag if the event pushed *against* the prevailing
        # momentum (a comeback surge), not piling on in the same direction
        sameDirection = (previousMomentum >= 0 and newMomentum > previousMomentum) or \
                        (previousMomentum <= 0 and newMomentum < previousMomentum)
        if sameDirection:
            return False

        # Against-the-grain swing must be large to qualify
        if delta >= MOMENTUM_SHIFT_THRESHOLD:
            return True

        return False

    def _applyMomentumEvent(self, rawDelta, benefitingTeam):
        """Process a momentum event after a play outcome."""
        previousMomentum = self.momentum
        resistingTeam = self.awayTeam if benefitingTeam is self.homeTeam else self.homeTeam

        # Streak inertia: if the opposing team was on a roll, this event
        # is harder to push through.  A streak of 3+ by the other side
        # dampens the incoming event (they have to "break through" the run).
        prevStreak = abs(self.momentumStreak)
        opposingRoll = benefitingTeam is not self.lastMomentumTeam and self.lastMomentumTeam is not None
        if opposingRoll and prevStreak >= 3:
            # 3 → 0.80, 4 → 0.65, 5 → 0.50
            streakInertia = max(0.50, 1.0 - (prevStreak - 2) * 0.15)
        else:
            streakInertia = 1.0

        # Dampening
        gapDamp = self._scoreGapDampener()
        mentalResist = self._mentalResistance(resistingTeam)

        # Cascade multiplier — scale down in blowouts so piling-on streaks flatten out
        self._updateMomentumStreak(benefitingTeam)
        streakBonus = MOMENTUM_CASCADE_STEP * (abs(self.momentumStreak) - 1) * gapDamp
        cascadeMultiplier = min(1.0 + streakBonus, MOMENTUM_MAX_CASCADE)

        finalDelta = rawDelta * cascadeMultiplier * gapDamp * mentalResist * streakInertia

        if benefitingTeam is self.homeTeam:
            self.momentum += finalDelta
        else:
            self.momentum -= finalDelta
        self.momentum = max(-100.0, min(100.0, self.momentum))

        # Mark momentum shift highlight
        if self.play and self._isMomentumShift(previousMomentum, self.momentum):
            self.play.isMomentumShift = True

    def _applyMomentumEffect(self):
        """Apply small per-play confidence/determination nudges based on momentum."""
        if abs(self.momentum) < MOMENTUM_NEUTRAL_ZONE:
            return

        effectMagnitude = MOMENTUM_EFFECT_BASE * (abs(self.momentum) / 50.0)
        effectMagnitude = min(effectMagnitude, MOMENTUM_EFFECT_CAP)

        if self.momentum > 0:
            benefiting = self.homeTeam
            suffering = self.awayTeam
        else:
            benefiting = self.awayTeam
            suffering = self.homeTeam

        # Boost benefiting team
        for player in benefiting.rosterDict.values():
            if player is not None:
                player.updateInGameConfidence(effectMagnitude * 0.6)
                player.updateInGameDetermination(effectMagnitude * 0.4)

        # Slight drag on suffering team
        dragMagnitude = effectMagnitude * 0.5
        for player in suffering.rosterDict.values():
            if player is not None:
                player.updateInGameConfidence(-dragMagnitude * 0.6)
                player.updateInGameDetermination(-dragMagnitude * 0.4)

    # ─── End Momentum System ────────────────────────────────────────────────

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
                stars = min(5, max(1, (rating - 60) // 8 + 1))
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
                # Sum TDs across all stat categories for fantasy card calculations
                totalTds = (
                    p.gameStatsDict.get('passing', {}).get('tds', 0)
                    + p.gameStatsDict.get('rushing', {}).get('tds', 0)
                    + p.gameStatsDict.get('receiving', {}).get('tds', 0)
                )
                return {
                    'id': p.id,
                    'name': p.name,
                    'position': p.position.name if hasattr(p, 'position') and p.position else None,
                    'teamId': p.team.id if hasattr(p, 'team') and hasattr(p.team, 'id') else None,
                    'playerRating': rating,
                    'ratingStars': max(1, min(5, stars)),
                    'fantasyPoints': p.gameStatsDict.get('fantasyPoints', 0),
                    'totalFantasyPoints': p.seasonStatsDict.get('fantasyPoints', 0) + p.gameStatsDict.get('fantasyPoints', 0),
                    'totalTds': totalTds,
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

        # If game is effectively over (e.g. last scoring play in Q4), ensure
        # status reflects Final before this broadcast goes out to the frontend
        if self.status != GameStatus.Final and self.isGameOver():
            self.status = GameStatus.Final

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
            # Store WP data on the Play object so it persists in gameFeed references
            # (gameFeed stores {'play': self.play} by reference)
            self.play.homeWinProbability = newHomeWp
            self.play.awayWinProbability = newAwayWp
            self.play.homeWpa = round(homeWpa, 2)
            self.play.awayWpa = round(awayWpa, 2)
            self.play.isBigPlay = bool(abs(homeWpa) >= 10.0 or abs(awayWpa) >= 10.0)

            # Momentum: big play bonus (team that benefited from WPA swing)
            if self.play.isBigPlay:
                benefitingTeam = self.homeTeam if homeWpa > 0 else self.awayTeam
                self._applyMomentumEvent(MOMENTUM_BIG_PLAY_BONUS, benefitingTeam)

            # Only keep clutch/choke tags if the play had meaningful WP impact
            wpImpact = max(abs(homeWpa), abs(awayWpa))
            if wpImpact < 5.0:
                self.play.isClutchPlay = False
                self.play.isChokePlay = False

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
                'isBigPlay': self.play.isBigPlay,
                'isClutchPlay': getattr(self.play, 'isClutchPlay', False),
                'isChokePlay': getattr(self.play, 'isChokePlay', False),
                'isMomentumShift': getattr(self.play, 'isMomentumShift', False),
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
            'homeTimeouts': self.homeTimeoutsRemaining,
            'awayTimeouts': self.awayTimeoutsRemaining,
            'momentum': round(getattr(self, 'momentum', 0.0), 1),
            'momentumTeam': (self.homeTeam.abbr if self.momentum > MOMENTUM_DISPLAY_THRESHOLD
                             else self.awayTeam.abbr if self.momentum < -MOMENTUM_DISPLAY_THRESHOLD
                             else None) if hasattr(self, 'momentum') else None,
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
                self.gameFeed[0]['isClutchPlay'] = getattr(self.play, 'isClutchPlay', False)
                self.gameFeed[0]['isChokePlay'] = getattr(self.play, 'isChokePlay', False)
                self.gameFeed[0]['isMomentumShift'] = getattr(self.play, 'isMomentumShift', False)

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
            return 4  # Snap to knee-down; play clock drain handled separately
        
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

        # Overtime win probability — replaces generic formula above
        if self.currentQuarter >= 5:
            isSuddenDeath = self.otSecondPossComplete
            homeHasBall = self.offensiveTeam == self.homeTeam

            if isSuddenDeath and scoreDiff != 0:
                # Sudden death + someone is leading → game ends on next score or turnover on downs.
                # Leading team is overwhelmingly likely to win (they can kneel it out or score).
                leadBonus = min(40, abs(scoreDiff) * 10)  # wider lead = more certain
                if scoreDiff > 0:
                    # Home leads
                    homeWinProb = 85 + leadBonus * 0.3
                    if homeHasBall:
                        homeWinProb += 5  # has possession too
                else:
                    # Away leads
                    homeWinProb = 15 - leadBonus * 0.3
                    if not homeHasBall:
                        homeWinProb -= 5  # away has possession too
            elif scoreDiff == 0:
                # Tied in OT — next score wins (or will win after both possess).
                # In FG range, WP should reflect the near-certainty of a made kick.
                yte = self.yardsToEndzone
                fgDist = yte + 17
                # Estimate FG make probability using same formula as fieldGoalTry
                baseFgProb = 1 / (1 + math.exp(0.12 * (fgDist - 52)))
                kicker = self.offensiveTeam.rosterDict.get('k')
                if kicker:
                    normalizedSkill = (kicker.gameAttributes.overallRating - 50) / 50
                    fgProb = baseFgProb * (0.4 + normalizedSkill * 1.5)
                    if fgDist < 30:
                        fgProb = min(1.0, fgProb + 0.15)
                    fgProb = max(0.05, min(1.0, fgProb))
                else:
                    fgProb = baseFgProb
                # Approximate scoring probability for this drive based on field position
                if yte <= 40:
                    # In FG range: scoring prob ≈ FG make prob (they'll kick)
                    scoringProb = fgProb * 100
                elif yte <= 60:
                    # Approaching FG range: decent chance of getting there + scoring
                    scoringProb = fgProb * 100 * 0.6
                else:
                    # Deep in own territory: lower but still have possession edge
                    scoringProb = 25 + expectedPoints * 3

                if isSuddenDeath:
                    # Next score wins outright — scoring prob maps directly to WP
                    offenseWp = max(52, scoringProb)
                else:
                    # First/second possession — other team gets a turn, dampen
                    offenseWp = 50 + (scoringProb - 50) * 0.5

                if homeHasBall:
                    homeWinProb = offenseWp
                else:
                    homeWinProb = 100 - offenseWp
            # else: non-sudden-death with score diff — first possession scored,
            # second team still gets a chance. Use the generic formula from above.

            homeWinProb = max(0.1, min(99.9, homeWinProb))
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
        self.targetSideline = False  # True when play caller targets sideline routes
        self.gamePressure = 0            # Snapshot of game pressure at play time
        self.keyPressureMod = 0.0        # The key player's pressure modifier
        self.qbPressureMod = 0.0         # QB-specific pressure modifier (pass plays)
        self.rcvPressureMod = 0.0        # Receiver-specific pressure modifier (pass plays)
        self.isClutchPlay = False        # High pressure + positive mod + good outcome
        self.isChokePlay = False         # High pressure + negative mod + bad outcome
        self.clutchPlayerName = ''       # Name of the player who clutched/choked
        self.isMomentumShift = False     # Play caused a significant momentum swing
        self.playNumber = 0             # Set after totalPlays is incremented
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
        distanceFactor = 0.18   # Steeper drop-off with distance for realistic miss rates
        skillFactor = 0.85      # Tighter kicker skill impact range

        # Base probability uses sigmoid centered at 52 yards
        baseProbability = round(1 / (1 + math.exp(distanceFactor * (self.fgDistance - 52))), 2)
        normalizedSkill = (self.kicker.gameAttributes.overallRating - 50) / 50

        # Base skill probability (no pressure)
        probability = baseProbability * (0.52 + normalizedSkill * skillFactor)

        # Bonus for chip shots (under 30 yards)
        if self.fgDistance < 30:
            probability = min(0.96, probability + 0.10)

        probability = max(0.05, min(0.96, probability))

        # ── Kicker Pressure System ──
        # FG attempts are uniquely high-pressure — apply a direct probability
        # adjustment based on game pressure and the kicker's mental attributes.
        self.gamePressure = self.game.gamePressure
        self.clutchPlayerName = self.kicker.name
        normalizedPressure = min(100, max(0, self.game.gamePressure)) / 100.0

        if normalizedPressure >= 0.3:
            attrs = self.kicker.attributes
            # Mental composure: average of focus + discipline, normalized to -1..+1
            mentalAvg = (getattr(attrs, 'focus', 80) + getattr(attrs, 'discipline', 80)) / 2
            mentalNorm = (mentalAvg - 80) / 20  # 60→-1, 80→0, 100→+1

            # pressureHandling: -10 to +10, normalize to -1..+1
            phNorm = getattr(attrs, 'pressureHandling', 0) / 10

            # Combined mental score: -1 (chokes) to +1 (ice cold)
            mentalScore = 0.5 * phNorm + 0.3 * mentalNorm + 0.2 * (getattr(attrs, 'clutchFactor', 0) / 100)

            # Max swing scales with pressure intensity: low pressure = tiny, high = up to ±12%
            maxSwing = normalizedPressure * 0.12

            # Roll for outcome — mental score shifts the distribution
            # mentalScore +1: ~70% boost, ~20% neutral, ~10% penalty
            # mentalScore  0: ~25% boost, ~50% neutral, ~25% penalty
            # mentalScore -1: ~10% boost, ~20% neutral, ~70% penalty
            roll = batched_randint(1, 100)
            boostChance = max(5, min(75, int(25 + mentalScore * 45)))
            neutralChance = max(15, min(55, int(50 - abs(mentalScore) * 30)))
            # penaltyChance is the remainder

            if roll <= boostChance:
                pressureAdj = batched_random() * maxSwing  # positive boost
            elif roll <= boostChance + neutralChance:
                pressureAdj = 0
            else:
                pressureAdj = -(batched_random() * maxSwing)  # penalty

            self.keyPressureMod = round(pressureAdj * 100, 1)
            probability = max(0.05, min(0.96, probability + pressureAdj))
        else:
            self.keyPressureMod = 0

        probability = round(probability * 100)  # Convert to 5-96% integer range

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
        """QB kneels to drain the clock. Loses 1 yard, ~4 seconds of game time.
        The remaining play-clock drain (~36 sec) is handled post-play in the game loop,
        AFTER the defense gets a chance to call timeout."""
        self.playType = PlayType.Kneel
        self.yardage = -1
        self.game.clockRunning = True
        # Only drain the actual play time (snap to knee-down)
        kneelDuration = min(4, self.game.gameClockSeconds)
        self.game.gameClockSeconds -= kneelDuration
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
        self.gamePressure = self.game.gamePressure
        self.keyPressureMod = runnerPressureMod
        self.clutchPlayerName = self.runner.name

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

                # QB discipline check: does the QB follow the sideline play call?
                # Discipline range is 60-100
                if self.targetSideline:
                    qbDisc = self.passer.attributes.discipline
                    if qbDisc >= 85:
                        pass  # Elite: always follows the call
                    elif qbDisc >= 75:
                        if _random.random() > 0.90:
                            self.targetSideline = False  # 10% chance to freelance
                    elif qbDisc >= 70:
                        if _random.random() > 0.80:
                            self.targetSideline = False  # 20% chance to freelance
                    else:
                        # 60-69: lowest discipline tier
                        if _random.random() > 0.70:
                            self.targetSideline = False  # 30% chance to freelance

            # Handle throw away
            if self.passType == PassType.throwAway:
                self.yardage = 0
                self.passer.addMissedPass(self.game.isRegularSeasonGame)
            else:
                # Apply pressure modifiers
                qbPressureMod = self.passer.attributes.getPressureModifier(self.game.gamePressure)
                receiverPressureMod = self.receiver.attributes.getPressureModifier(self.game.gamePressure)
                self.gamePressure = self.game.gamePressure
                self.qbPressureMod = qbPressureMod
                self.rcvPressureMod = receiverPressureMod

                # STAGE 3: Calculate throw quality
                throwQuality = self.calculateThrowQuality(
                    self.passType,
                    self.passer.gameAttributes.accuracy,
                    self.passer.gameAttributes.xFactor,
                    self.defense.defensePassRushRating,
                    self.blockingModifier,
                    qbPressureMod
                )

                # Sideline throws are harder — tighter windows
                if self.targetSideline:
                    throwQuality = max(5, throwQuality * 0.90)

                # STAGE 4: Calculate catch probability and outcome
                catchProbs = self.calculateCatchProbability(
                    throwQuality,
                    self.receiver.gameAttributes.hands,
                    self.selectedTarget['openness'],
                    self.defense.defensePassCoverageRating,
                    receiverPressureMod
                )

                # QB choking under pressure increases INT risk
                if qbPressureMod <= -CLUTCH_MODIFIER_THRESHOLD:
                    chokeIntBoost = abs(qbPressureMod) * 0.5
                    catchProbs['intProb'] = min(25, catchProbs['intProb'] + chokeIntBoost)

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
                        
                        # YAC potential based on field position and sideline targeting
                        # Receiver discipline affects YAC cap on sideline routes
                        if self.targetSideline:
                            rcvDisc = self.receiver.attributes.discipline
                            if rcvDisc >= 85:
                                yacCap = 5        # Elite: gets out ASAP
                                decayMult = 2.0   # Very steep — minimal YAC
                            elif rcvDisc >= 75:
                                yacCap = 8        # Good: balances getting out with some YAC
                                decayMult = 1.6
                            elif rcvDisc >= 70:
                                yacCap = 10       # Average: tries a bit more
                                decayMult = 1.3
                            else:
                                yacCap = 12       # 60-69: tries to stretch it
                                decayMult = 1.1
                        else:
                            yacCap = 15
                            decayMult = 1.0
                        yacMaxYards = min(yacCap, self.yardsToEndzone - passYards)
                        
                        if yacMaxYards > 0:
                            yacYardages = np.arange(0, yacMaxYards + 1)
                            
                            # YAC decay rate based on receiver vs defense - BOOSTED
                            yacOffense = receiverYACRating + receiverPressureMod
                            yacDefense = self.defense.defensePassCoverageRating
                            offenseContribution = (2.0 * yacOffense) / 100  # was 1.5
                            defenseContribution = 0.2 * yacDefense / 100    # was 0.3
                            yacDecayRate = round(0.08 + 0.1 * (np.exp(defenseContribution) - offenseContribution), 3)  # was 0.12
                            yacDecayRate *= decayMult

                            # Exponential decay curve for YAC
                            yacCurve = np.exp(-yacDecayRate * yacYardages)
                            yacCurve /= np.sum(yacCurve)
                            
                            yac = int(np.random.choice(yacYardages, p=yacCurve))
                    
                    self.yardage = passYards + yac
                    if self.yardage > self.yardsToEndzone:
                        yac = self.yardsToEndzone - passYards
                        self.yardage = self.yardsToEndzone
                    
                    # Determine if receiver went out of bounds (for clock management)
                    if self.targetSideline:
                        # Sideline route: high OOB base rates
                        if self.passType == PassType.short:
                            oobChance = 75
                        elif self.passType == PassType.medium:
                            oobChance = 85
                        elif self.passType == PassType.long:
                            oobChance = 90
                        else:
                            oobChance = 15
                        # Receiver discipline modifier (60-100 range)
                        rcvDisc = self.receiver.attributes.discipline
                        if rcvDisc >= 85:
                            oobChance += 5    # Elite: gets out immediately
                        elif rcvDisc >= 75:
                            pass              # Good: uses base rates
                        elif rcvDisc >= 70:
                            oobChance -= 5    # Average: slightly more likely to stay in
                        else:
                            oobChance -= 15   # 60-69: tries to extend the play
                    else:
                        # Over the middle: low OOB chance
                        if self.passType == PassType.short:
                            oobChance = 10
                        elif self.passType == PassType.medium:
                            oobChance = 20
                        elif self.passType == PassType.long:
                            oobChance = 30
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

