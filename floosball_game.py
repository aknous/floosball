import enum
import logging
logger = logging.getLogger(__name__)
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
from typing import Dict, Optional
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
    GAME_MAX_PLAYS, PLAYS_TO_FOURTH_QUARTER, PLAYS_TO_THIRD_QUARTER, FOURTH_QUARTER_START,
    RATING_SCALE_MIN, RATING_RANGE, PERCENTAGE_MULTIPLIER,
    PRESSURE_BASE, PRESSURE_MAX_ADDITIONAL, PRESSURE_CALCULATION_DIVISOR,
    CLOSE_GAME_SCORE_THRESHOLD, CLUTCH_PRESSURE_THRESHOLD, CLUTCH_MODIFIER_THRESHOLD,
    CHOKE_MODIFIER_THRESHOLD, CLUTCH_WPA_THRESHOLD, CHOKE_WPA_THRESHOLD,
    INT_BAD_READ_K, INT_BAD_THROW_K, INT_DEF_PLAY_K,
    HAIL_MARY_COMPLETION_SCALE,
    RECEIVER_MATCHUP_SCALE,
    COACH_ATTR_NEUTRAL, COACH_ATTR_RANGE, COACH_OFFENSIVE_MIND_FLOOR,
    MOMENTUM_DECAY_RATE, MOMENTUM_BLOWOUT_DECAY_RATE, MOMENTUM_MIDGAP_DECAY_RATE,
    MOMENTUM_CASCADE_STEP, MOMENTUM_MAX_CASCADE, MOMENTUM_MAX_STREAK,
    MOMENTUM_EFFECT_BASE, MOMENTUM_EFFECT_CAP, MOMENTUM_NEUTRAL_ZONE,
    MOMENTUM_SHIFT_THRESHOLD, MOMENTUM_CROSS_ZERO_THRESHOLD, MOMENTUM_DISPLAY_THRESHOLD,
    MOMENTUM_TD, MOMENTUM_TURNOVER, MOMENTUM_SAFETY, MOMENTUM_TURNOVER_ON_DOWNS,
    MOMENTUM_FG_MISSED, MOMENTUM_FG_MADE, MOMENTUM_SACK, MOMENTUM_BIG_PLAY_BONUS,
    MOMENTUM_PUNT,
    WPA_PASS_QB_SHARE, DEF_PLAYMAKER_BONUS,
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
                          adjustOffensiveGameplan, adjustDefensiveGameplan,
                          CoverageType, BlitzPackage)
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


# Layer 1 universal micro-glitch pool. **PURE FLAVOR** — no mechanical
# impact. Fires for any anomalous player from Stirring up. The user
# reads these and thinks "huh, that's curious." Subtle. Generic.
_LAYER_1_MICRO_GLITCHES = [
    "{player} was momentarily in two positions at once.",
    "{player} stepped through a peculiar gap in the geometry of the simulation.",
    "{player}'s shadow is lagging oddly behind them.",
    "{player} occupied a space that does not entirely reside in this dimension.",
    "{player}'s movement seemed to skip a frame.",
    "{player} moved through a path that did not exist a moment earlier.",
    "{player} seems to be glitching around the field.",
    "{player} stuttered in place while the simulation recalculated their trajectory.",
    "{player} arrived at the ball a frame before the ball did.",
    "{player} teleported half a stride forward, somehow skipping the space in between.",
    "{player} briefly rendered at a slightly lower resolution than everyone around them.",
    "{player}'s jersey shimmered faintly, like heat coming off asphalt.",
    "{player} seemed to flicker in and out of existence during the play.",
]

# Layer 2 personality-flavored glitch pool. **STILL PURE FLAVOR** — no
# mechanical impact. Fires for players at Erratic state and above. The
# user reads these and thinks "okay, something weird is happening here."
# More pronounced than Layer 1: the simulation is visibly failing
# around the player, not just nudging.
_LAYER_2_GLITCHES = [
    "{player}'s textures peeled away, leaving a bare wireframe sprinting down the field.",
    "{player} is no longer following the field's geometry.",
    "{player}'s velocity exceeded the limits the simulation was designed to handle.",
    "{player} clipped through a couple defenders in their path.",
    "{player} stretched across half the field before collapsing back into a single body.",
    "{player} flickered violently between positions, unable to settle on just one.",
    "{player} left a trail of afterimages that lingered after the play ended.",
    "{player} fragmented into a cloud of pixels momentarily before snapping back together.",
    "{player}'s body seemed to briefly corrupt into a tangle of geometry not recognizable as a person.",
    "{player} dissolved into static and reassembled several yards away.",
    "{player}'s limbs rotated in directions that should not be possible.",
    "{player} legs clipped through the turf during the play and all you could see was their torso sliding around the field.",
    "{player} inverted briefly and ran across the underside of the field.",
    "{player} seemed to momentarily exist in multiple places at once.",
    "{player} looked like they were running through the air.",
]

# Layer 3 glitch pools — these fire ALONGSIDE a real yardage change (the
# simulation warps the play around a rampant/awakened player). Surge = the
# glitch gains them ground; Stumble = a modest hiccup that costs a little.
# Still involuntary — NOT the deliberate Control powers (a later season).
_LAYER_3_SURGE_GLITCHES = [
    "{player} dissolved into static and reassembled several yards downfield.",
    "{player} clipped through a defender who never finished rendering.",
    "{player} skipped across a seam in the field, gaining ground that wasn't there.",
    "{player} phased forward as the simulation snapped them ahead of the play.",
    "{player} pulled away faster than the engine could redraw the defense.",
    "{player} stepped through the tackle as though the rules were only a suggestion.",
]
_LAYER_3_STUMBLE_GLITCHES = [
    "{player} stuttered as the simulation dropped a frame, losing a step.",
    "{player}'s footing glitched against terrain that wasn't quite there.",
    "{player} briefly desynced from the field and stumbled before recovering.",
    "{player} snagged on a seam in the geometry and lost a little ground.",
    "{player} flickered mid-stride and came down a step short.",
]
    
class PassType(enum.Enum):
    short = 1     # 0-4 air yards   (screen, quick hitch)
    medium = 2    # 5-8 air yards   (short crossing, hitch)
    long = 3      # 9-14 air yards  (over-the-middle, deep curl)
    hailMary = 4  # endzone / max QB throw distance
    throwAway = 5
    deep = 6      # 15+ air yards   (go route, post, deep cross)

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


# ── Inside run descriptions (A-gap, B-gap) ──
shortRunInsideList = [
                    'dives up the middle for',
                    'plunges inside for',
                    'powers ahead for',
                    'squeezes through the line for',
                    'churns ahead for',
                    'falls forward for',
                    'fights through traffic for',
                    'punches it inside for',
                    'muscles up the gut for',
                    'pushes through the pile for',
                ]

midRunInsideList = [
                    'runs up the middle for',
                    'barrels through the line for',
                    'powers through the gap for',
                    'plows through the middle for',
                    'grinds up the gut for',
                    'charges through the line for',
                    'finds a crease inside for',
                    'threads the gap for',
                    'slices through the line for',
                    'rumbles through the middle for',
                    'busts through the line for',
                    'drags defenders for',
                ]

longRunInsideList = [
                    'explodes through the line for',
                    'bursts through the middle for',
                    'breaks through the pile for',
                    'goes untouched up the gut for',
                    'rips through the line for',
                    'blazes through the middle for',
                    'hits a huge hole for',
                    'gallops through the line for',
                    'takes off through the gap for',
                ]

# ── Outside run descriptions (C-gap, bounce) ──
shortRunOutsideList = [
                    'runs off tackle for',
                    'dashes outside for',
                    'cuts to the edge for',
                    'sneaks around the end for',
                    'gets to the corner for',
                    'squeezes outside for',
                    'fights to the edge for',
                    'turns the corner for',
                ]

midRunOutsideList = [
                    'bounces outside for',
                    'races to the edge for',
                    'cuts outside for',
                    'sweeps around the end for',
                    'breaks to the outside for',
                    'turns the corner for',
                    'gets to the sideline for',
                    'slips outside for',
                    'runs wide for',
                    'beats the edge for',
                ]

longRunOutsideList = [
                    'breaks free around the edge for',
                    'sprints to the outside for',
                    'races down the sideline for',
                    'turns the corner and takes off for',
                    'outruns the defense to the edge for',
                    'streaks down the sideline for',
                    'explodes around the end for',
                    'hits the open field outside for',
                    'bolts to the sideline for',
                ]

# Loss run (no defender) — args: none, used as verb phrase
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

# Loss run with defender — args: (runner.name, defender.name, yardage)
lossRunDefenderList = [
                    '{} is stuffed by {} for {} yards',
                    '{} is stopped by {} for {} yards',
                    '{} is dropped by {} for {} yards',
                    '{} is tackled in the backfield by {} for {} yards',
                    '{} is brought down by {} for {} yards',
                    '{} is wrapped up by {} for {} yards',
                    '{} is stopped cold by {} for {} yards',
                    '{} is stonewalled by {} for {} yards',
                    '{} is met at the line by {} for {} yards',
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

# "into the end zone" asserts the ball reached the end zone — only true on a
# score. For a hail mary that's caught short and tackled, use the pool without
# any end-zone claim so the narration matches the result.
extraLongNonScoringPassList = [p for p in extraLongPassList if 'end zone' not in p]

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
# Sack — args: (passer.name, defender.name, yardage)
sackList = [
                    '{} sacked by {} for {} yards',
                    '{} is brought down by {} for {} yards',
                    '{} goes down, sacked by {} for {} yards',
                    '{} is taken down by {} behind the line for {} yards',
                    '{} has nowhere to throw, {} brings him down for {} yards',
                    '{} is wrapped up by {} and sacked for {} yards',
                    '{} is crushed by {} for {} yards',
                    '{} is buried by {} for {} yards',
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

# Interception — args: (passer.name, defender.name)
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
throwAwayPressureList = [
                    '{} senses pressure and throws it away',
                    '{} escapes pressure and dumps it out of bounds',
                    '{} throws it away under duress',
                ]
throwAwayCoverageList = [
                    '{} throws the ball away, incomplete',
                    '{} can\'t find anyone, throws it out of bounds',
                    '{} discards it, incomplete',
                    '{} finds no one open, throws it away',
                ]

# ── Context-aware incompletes — args: (passer.name, receiver.name) ──
# Bad throw to a wide-open receiver: the QB simply missed an open target.
overthrowOpenList = [
                    '{} misses a wide-open {}, incomplete',
                    '{} sails it past a wide-open {}, incomplete',
                    '{} had {} open and missed the throw, incomplete',
                    '{} leaves an open {} waiting, throw is off the mark',
                    '{} airmails it to {} with nobody near, incomplete',
                ]
# Bad throw forced into coverage: errant ball into a tight window.
forcedCoverageList = [
                    '{} forces it into coverage for {}, incomplete',
                    '{} tries to squeeze it to a blanketed {}, broken up',
                    '{} throws into traffic for {}, knocked away',
                    '{} forces it to {} in a tight window, no good',
                    '{} airs it into coverage for {}, incomplete',
                ]
# Accurate throw to a covered receiver, broken up at the catch point.
coverageBreakupList = [
                    '{} on target to {}, broken up in coverage',
                    '{} hits {} in stride, knocked loose by the defender',
                    '{} puts it on {}, but the defender knocks it away',
                    '{} and {} nearly connect, broken up at the catch point',
                ]

# ── Context-aware interceptions — args: (passer.name, defender.name) ──
# Picked off after forcing it into coverage (bad read / covered receiver).
intoCoverageList = [
                    '{} throws into coverage, {} steps in front for the pick',
                    '{} forces it into traffic, picked off by {}',
                    '{} never saw the defender, {} jumps the route',
                    '{} throws into double coverage, {} comes down with it',
                    '{} telegraphs it into coverage, {} with the interception',
                ]
# Picked off on an errant throw the QB sailed; the defender takes it.
errantPickList = [
                    '{} sails it, {} reels in the errant throw',
                    '{} airmails it right to {}, intercepted',
                    '{} loses it on the throw, picked off by {}',
                    '{} floats one up for grabs, {} brings it in',
                ]
# Picked off on an on-target throw — the receiver was covered and the
# defender stepped in. Stated by action, not judged.
defPlayPickList = [
                    '{} on target, but {} steps in front for the interception',
                    '{} throws on target, {} jumps the route for the pick',
                    '{} hits the window, but {} undercuts it for the pick',
                    '{} puts it on the target, {} cuts in front for the interception',
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
                            'wr1': None,
                            'wr2': PassType.long,
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
                            'wr1': None,
                            'wr2': PassType.medium,
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
                    # ── Deep shot plays (15+ air yards) ──────────────────
                    # Used sparingly by aggressive coaches. Built around one
                    # primary deep target with a checkdown option.
                    'Play21': {
                        'dropback': QbDropback.extraLong,
                        'targets': {
                            'wr1': PassType.deep,
                            'wr2': PassType.medium,
                            'te': None,
                            'rb': None
                        }
                    },
                    'Play22': {
                        'dropback': QbDropback.extraLong,
                        'targets': {
                            'wr1': PassType.deep,
                            'wr2': PassType.deep,
                            'te': None,
                            'rb': None
                        }
                    },
                    'Play23': {
                        'dropback': QbDropback.extraLong,
                        'targets': {
                            'wr1': None,
                            'wr2': PassType.deep,
                            'te': PassType.medium,
                            'rb': None
                        }
                    },
                    'Play24': {
                        'dropback': QbDropback.extraLong,
                        'targets': {
                            'wr1': PassType.deep,
                            'wr2': PassType.short,
                            'te': PassType.short,
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
    def __init__(self, homeTeam, awayTeam, timingManager=None, personalityManager=None, gameRules=None):
        self.id = None  # Integer ID assigned by SeasonManager
        self.seasonNumber = None  # Which season this game belongs to
        self.week = None  # Week number for regular season
        self.playoffRound = None  # Round number for playoffs (1=wildcard, 2=divisional, etc.)
        self.gameType = 'regular'  # 'regular' or 'playoff'
        self.isFloosBowl = False  # True only for the cross-league final (drives the halftime show)
        self.halftimeShowPauseSeconds = None  # Optional halftime-pause override (Floos Bowl show), set at creation
        self.gameNumber = None  # Game number within the week/round
        self.status = None
        self.personalityManager = personalityManager  # Layer 1/2/3 template firing
        self.homeTeam : FloosTeam.Team = homeTeam
        self.awayTeam : FloosTeam.Team = awayTeam
        self.awayScore = 0
        self.homeScore = 0

        # Rule book. Every football-rule decision the sim makes reads
        # from this object (field length, downs per series, score
        # values, FG mechanics, clock, etc.). Defaults to the standard
        # ruleset; the Season passes its own instance in so all games
        # share a consistent set, and so future Cores' rule patches can
        # propagate to subsequent games.
        if gameRules is not None:
            self.gameRules = gameRules
        else:
            from game_rules import GameRules
            self.gameRules = GameRules()

        # Anomaly system — per-player attention + state snapshot loaded
        # lazily on first play. Empty dicts means "not loaded yet"; an
        # entry of 0 / 'stable' means "loaded, this player has nothing
        # going on." Refreshed at the start of each game so mid-game DB
        # churn isn't required.
        self._anomalyAttention: Dict[int, float] = {}
        self._anomalyState: Dict[int, str] = {}
        self._anomalyAttentionLoaded: bool = False
        # Multiplier on per-play anomaly probability. 1.0 normally, 5.0
        # if this game is happening inside an active Criticality window.
        # Set when attention is loaded.
        self._criticalityMultiplier: float = 1.0
        # Per-game glitch hygiene: hard cap + cooldown so anomaly glitch
        # lines stay rare and spaced out instead of flooding the play feed.
        self._glitchCountThisGame: int = 0
        self._lastGlitchPlayNumber: int = -10_000
        # L3 stumbles (the negative glitch) are capped per team per game.
        self._l3NegByTeam: Dict[str, int] = {}

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
        self.gameClockSeconds = self.gameRules.quarterLengthSeconds  # 15 minutes per quarter
        self.clockRunning = False
        self.homeTimeoutsRemaining = 3
        self.awayTimeoutsRemaining = 3
        self.twoMinuteWarningShown = False
        # True from the instant the two-minute warning stops the clock until the
        # next snap. Blocks teams from burning a timeout on the dead clock right
        # after the warning (the warning already gave a free stop).
        self._clockStoppedByWarning = False

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
        self.homeHalfWr1Yards = 0
        self.homeHalfWr2Yards = 0
        self.awayHalfRunPlays = 0
        self.awayHalfRunYards = 0
        self.awayHalfPassAttempts = 0
        self.awayHalfPassYards = 0
        self.awayHalfWr1Yards = 0
        self.awayHalfWr2Yards = 0

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
        self._sidelineCutawaysFired = 0   # Per-game counter for sideline-cutaway gating
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
        self.otPeriod = 0                        # OT period counter (1 = first OT, 2+ = sudden death)
        self.startTime: datetime.datetime = None
        self.isTwoPtConv = False
        self.isOnsideKick = False
        self.gamePressure = 0

        # Momentum
        self.momentum = 0.0              # -100 to +100 (positive = home, negative = away)
        self.momentumStreak = 0          # consecutive events for same side, capped ±MAX_STREAK
        self.lastMomentumTeam = None     # team that last gained momentum
        # Diagnostics (sampled in _applyMomentumEffect, dumped by _logPlayAnalytics)
        self._peakAbsMomentum = 0.0
        self._playsAbove30Mom = 0

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

    def _isFgDrainMode(self) -> bool:
        """True when the offense should drain clock to set up an end-of-game FG.
        Late Q2/Q4, scoring within 3 (trailing or tied), in chip-shot FG range.

        When True:
          - Sideline pass targeting is suppressed (clock should keep running)
          - Run weight is bumped (in-bounds runs let clock tick toward FG-snap time)
          - Pre-snap drain extends to leave just enough for the FG kick (~7s)
        """
        if self.currentQuarter not in (2, 4):
            return False
        if self.gameClockSeconds > 60:
            return False
        isHome = (self.offensiveTeam is self.homeTeam)
        scoreDiff = (self.homeScore - self.awayScore) if isHome else (self.awayScore - self.homeScore)
        if not (-3 <= scoreDiff <= 0):
            return False
        if self._isGarbageTime(scoreDiff):
            return False
        kicker = self.offensiveTeam.rosterDict.get('k')
        if kicker is None:
            return False
        kickerMax = kicker.maxFgDistance - self.gameRules.fgSnapDistance
        if self.yardsToEndzone > kickerMax:
            return False
        try:
            return self._estimateFgProbability() >= 0.75
        except Exception:
            return False

    def _logPressureCorrelation(self) -> None:
        """Append one JSONL entry per team to logs/pressure_correlation.jsonl
        capturing pressure level, game outcome, ELO delta, form state, and
        roster resolve average. Used to look for correlation between market
        expectation pressure and on-field outcomes. Never raises — diagnostic
        must not break the game loop.
        """
        try:
            import json as _json
            import os
            from datetime import datetime
            from constants import (
                EXPECTATION_SCALE_BY_TIER,
                EXPECTATION_RELIEF_BY_TIER,
                EXPECTATION_DELTA_CAP,
                CHAMPIONSHIP_OVERFLOW_FACTOR,
            )
            try:
                from api_response_builders import TeamResponseBuilder as _Trb
            except Exception:
                _Trb = None

            def _scaledPressure(base, tier, streakAdd=0.0):
                effective = base + streakAdd
                delta = effective - 1.0
                if delta > 0:
                    ts = EXPECTATION_SCALE_BY_TIER.get(tier, 1.0)
                    cap = min(delta, EXPECTATION_DELTA_CAP)
                    overflow = max(0.0, delta - EXPECTATION_DELTA_CAP)
                    return 1.0 + cap * ts + overflow * CHAMPIONSHIP_OVERFLOW_FACTOR
                rs = EXPECTATION_RELIEF_BY_TIER.get(tier, 1.0)
                return 1.0 + delta * rs

            def _rosterAttrAvg(team, attrName):
                """Generic roster average for a player.attributes value or method.
                Returns None if no roster players carry the attr.
                """
                roster = getattr(team, 'rosterDict', None) or {}
                vals = []
                for p in roster.values():
                    if p is None:
                        continue
                    attrs = getattr(p, 'attributes', None)
                    if attrs is None:
                        continue
                    val = getattr(attrs, attrName, None)
                    if val is None:
                        continue
                    try:
                        v = val() if callable(val) else val
                        vals.append(float(v))
                    except Exception:
                        continue
                return round(sum(vals) / len(vals), 3) if vals else None

            def _rosterResolveAvg(team):
                return _rosterAttrAvg(team, 'adversityResolve')

            def _rosterPressureHandlingAvg(team):
                return _rosterAttrAvg(team, 'pressureHandling')

            for team, opp, score, oppScore, preElo, prePressure, preTier, preStreak, preStreakP in (
                (self.homeTeam, self.awayTeam, self.homeScore, self.awayScore,
                 getattr(self, '_preGameHomeElo', 1500),
                 getattr(self, '_preGameHomePressureMod', 1.0),
                 getattr(self, '_preGameHomeTier', 'UNKNOWN'),
                 getattr(self, '_preGameHomeStreak', 0),
                 getattr(self, '_preGameHomeStreakP', 0.0)),
                (self.awayTeam, self.homeTeam, self.awayScore, self.homeScore,
                 getattr(self, '_preGameAwayElo', 1500),
                 getattr(self, '_preGameAwayPressureMod', 1.0),
                 getattr(self, '_preGameAwayTier', 'UNKNOWN'),
                 getattr(self, '_preGameAwayStreak', 0),
                 getattr(self, '_preGameAwayStreakP', 0.0)),
            ):
                preEloOpp = (getattr(self, '_preGameAwayElo', 1500)
                             if team is self.homeTeam
                             else getattr(self, '_preGameHomeElo', 1500))
                won = score > oppScore
                tied = score == oppScore
                formState = None
                try:
                    if _Trb is not None:
                        formState = _Trb.computeFormState(team)
                except Exception:
                    formState = None
                entry = {
                    'ts': datetime.utcnow().isoformat() + 'Z',
                    'season': getattr(self, 'seasonNumber', None),
                    'week': getattr(self, 'week', None),
                    'gameId': getattr(self, 'id', None),
                    'gameType': getattr(self, 'gameType', None),
                    'playoffRound': getattr(self, 'playoffRound', None),
                    'team': team.name,
                    'opponent': opp.name,
                    'tier': preTier,
                    'pressureBase': round(prePressure, 3),
                    'pressureScaled': round(_scaledPressure(prePressure, preTier, preStreakP), 3),
                    'priorSeasonPressure': round(getattr(team, 'priorSeasonPressure', 1.0), 3),
                    'inSeasonPressure': round(getattr(team, 'inSeasonPressure', 1.0), 3),
                    'preGameWinStreak': preStreak,
                    'streakPressure': round(preStreakP, 3),
                    'won': won,
                    'tied': tied,
                    'score': score,
                    'opponentScore': oppScore,
                    'preEloDiff': round(preElo - preEloOpp, 1),
                    'preElo': round(preElo, 1),
                    'formState': formState,
                    'rosterResolveAvg': _rosterResolveAvg(team),
                    'rosterPressureHandlingAvg': _rosterPressureHandlingAvg(team),
                }
                os.makedirs('logs', exist_ok=True)
                with open('logs/pressure_correlation.jsonl', 'a') as f:
                    f.write(_json.dumps(entry) + '\n')
        except Exception:
            pass

    def _tallyCoachArchetype(self, key: str) -> None:
        """Increment a per-game counter for which coach-personality branch
        was taken in the situational mods. Surfaced in sim_analytics for
        offline analysis. Never raises.
        """
        try:
            if not hasattr(self, '_coachArchetypeCounts'):
                self._coachArchetypeCounts = {}
            self._coachArchetypeCounts[key] = self._coachArchetypeCounts.get(key, 0) + 1
        except Exception:
            pass

    def _logPlayAnalytics(self) -> None:
        """Append one JSONL entry per game to logs/sim_analytics.jsonl
        aggregating per-play data so an offline analyzer can answer:
          - how often do long runs / deep passes go for TDs
          - YAC distribution
          - rushing vs passing yards
          - interception rate, by pass tier

        Never raises — diagnostic must not break the game loop.
        """
        try:
            import json as _json
            import os

            agg = {
                'season': getattr(self, 'seasonNumber', None),
                'week': getattr(self, 'week', None),
                'gameId': getattr(self, 'id', None),
                'home': self.homeTeam.abbr,
                'away': self.awayTeam.abbr,
                'homeScore': self.homeScore,
                'awayScore': self.awayScore,
                # Play counts
                'totalPlays': 0,
                'runPlays': 0,
                'passAttempts': 0,
                'passCompletions': 0,
                'passByTier': {'short': 0, 'medium': 0, 'long': 0, 'deep': 0, 'hailMary': 0},
                # Touchdowns
                'runTd': 0,
                'passTd': 0,
                'runTd30plus': 0,
                'passTd30plus': 0,
                'passTdByTier': {'short': 0, 'medium': 0, 'long': 0, 'deep': 0, 'hailMary': 0},
                'compByTier': {'short': 0, 'medium': 0, 'long': 0, 'deep': 0, 'hailMary': 0},
                'dropByTier': {'short': 0, 'medium': 0, 'long': 0, 'deep': 0, 'hailMary': 0},
                'incompleteByTier': {'short': 0, 'medium': 0, 'long': 0, 'deep': 0, 'hailMary': 0},
                'throwAways': 0,
                'throwAwayByTier': {'short': 0, 'medium': 0, 'long': 0, 'deep': 0, 'hailMary': 0},
                # Diagnostic sums (avg = sum/count). 'thrownByTier' = balls
                # actually launched (excludes sacks & throwaways).
                'thrownByTier': {'short': 0, 'medium': 0, 'long': 0, 'deep': 0, 'hailMary': 0},
                'tqSumByTier': {'short': 0, 'medium': 0, 'long': 0, 'deep': 0, 'hailMary': 0},
                'opennessSumByTier': {'short': 0, 'medium': 0, 'long': 0, 'deep': 0, 'hailMary': 0},
                'catchProbSumByTier': {'short': 0, 'medium': 0, 'long': 0, 'deep': 0, 'hailMary': 0},
                'contactProbSumByTier': {'short': 0, 'medium': 0, 'long': 0, 'deep': 0, 'hailMary': 0},
                'secureProbSumByTier': {'short': 0, 'medium': 0, 'long': 0, 'deep': 0, 'hailMary': 0},
                'covDefSumByTier': {'short': 0, 'medium': 0, 'long': 0, 'deep': 0, 'hailMary': 0},
                # Turnovers
                'interceptions': 0,
                'intByTier': {'short': 0, 'medium': 0, 'long': 0, 'deep': 0, 'hailMary': 0},
                'fumblesLost': 0,
                # Sacks (a sack is a pass play that ended before the throw)
                'sacks': 0,
                'sackYards': 0,  # negative yards lost to sacks (positive int — magnitude)
                'sackByTier': {'short': 0, 'medium': 0, 'long': 0, 'deep': 0, 'hailMary': 0},
                # Yardage
                'totalRushYards': 0,
                'totalPassYards': 0,
                'totalAirYards': 0,
                'totalYac': 0,
                'longestRun': 0,
                'longestPass': 0,
                # Big plays
                'runs20plus': 0,
                'runs30plus': 0,
                'passes20plus': 0,
                'passes30plus': 0,
                'passes40plus': 0,
                # Coach archetype counters (per situational-mods entry)
                'coachArchetypes': dict(getattr(self, '_coachArchetypeCounts', {}) or {}),
                # Momentum analytics — read by analyze_momentum.py
                'finalAbsMomentum': round(abs(self.momentum), 1),
                'peakAbsMomentum': round(getattr(self, '_peakAbsMomentum', 0.0), 1),
                'playsAbove30Mom': getattr(self, '_playsAbove30Mom', 0),
                'bigPlays': 0,            # filled in feed scan
                'momentumShifts': 0,      # filled in feed scan
                'homeQ1': getattr(self, 'homeScoreQ1', 0),
                'homeQ2': getattr(self, 'homeScoreQ2', 0),
                'homeQ3': getattr(self, 'homeScoreQ3', 0),
                'homeQ4': getattr(self, 'homeScoreQ4', 0),
                'homeOT': getattr(self, 'homeScoreOT', 0),
                'awayQ1': getattr(self, 'awayScoreQ1', 0),
                'awayQ2': getattr(self, 'awayScoreQ2', 0),
                'awayQ3': getattr(self, 'awayScoreQ3', 0),
                'awayQ4': getattr(self, 'awayScoreQ4', 0),
                'awayOT': getattr(self, 'awayScoreOT', 0),
                'preGameHomeWinProb': round(getattr(self, 'preGameHomeWinProbability', 0.5), 3),
                # Disposition / mental stack snapshots — read by
                # analyze_disposition.py. Each phase is the avg starter
                # overallRating after that modifier ran (baseline is
                # post-league-compression but pre-fatigue).
                'home_avgBaseline':         round(self._avgStarterSnapshot(self.homeTeam, 'baseline'), 2),
                'home_avgAfterFatigue':     round(self._avgStarterSnapshot(self.homeTeam, 'afterFatigue'), 2),
                'home_avgAfterDisposition': round(self._avgStarterSnapshot(self.homeTeam, 'afterDisposition'), 2),
                'home_avgAfterCap':         round(self._avgStarterSnapshot(self.homeTeam, 'afterCap'), 2),
                'home_avgEndGame':          round(self._avgStarterCurrentRating(self.homeTeam), 2),
                'home_dispositionLabel':    getattr(self.homeTeam, '_dispositionLabel', None),
                'home_dispositionMult':     round(getattr(self.homeTeam, '_dispositionMultiplier', 1.0), 4),
                'home_formState':           getattr(self.homeTeam, '_dispositionFormState', None),
                'away_avgBaseline':         round(self._avgStarterSnapshot(self.awayTeam, 'baseline'), 2),
                'away_avgAfterFatigue':     round(self._avgStarterSnapshot(self.awayTeam, 'afterFatigue'), 2),
                'away_avgAfterDisposition': round(self._avgStarterSnapshot(self.awayTeam, 'afterDisposition'), 2),
                'away_avgAfterCap':         round(self._avgStarterSnapshot(self.awayTeam, 'afterCap'), 2),
                'away_avgEndGame':          round(self._avgStarterCurrentRating(self.awayTeam), 2),
                'away_dispositionLabel':    getattr(self.awayTeam, '_dispositionLabel', None),
                'away_dispositionMult':     round(getattr(self.awayTeam, '_dispositionMultiplier', 1.0), 4),
                'away_formState':           getattr(self.awayTeam, '_dispositionFormState', None),
            }

            for item in self.gameFeed:
                play = item.get('play') if isinstance(item, dict) else None
                if play is None or not hasattr(play, 'playType'):
                    continue
                if getattr(play, 'isBigPlay', False):
                    agg['bigPlays'] += 1
                if getattr(play, 'isMomentumShift', False):
                    agg['momentumShifts'] += 1
                pt = getattr(play, 'playType', None)
                ptName = pt.name if pt and hasattr(pt, 'name') else None

                if ptName == 'Run':
                    agg['totalPlays'] += 1
                    agg['runPlays'] += 1
                    yd = int(getattr(play, 'yardage', 0) or 0)
                    agg['totalRushYards'] += yd
                    agg['longestRun'] = max(agg['longestRun'], yd)
                    if yd >= 20:
                        agg['runs20plus'] += 1
                    if yd >= 30:
                        agg['runs30plus'] += 1
                    if getattr(play, 'isTd', False):
                        agg['runTd'] += 1
                        if yd >= 30:
                            agg['runTd30plus'] += 1

                elif ptName == 'Pass':
                    agg['totalPlays'] += 1
                    agg['passAttempts'] += 1
                    passType = getattr(play, 'passType', None)
                    ptName2 = passType.name if passType and hasattr(passType, 'name') else None
                    # Throwaways and sacks fall back to intendedPassTier so they
                    # still get bucketed under the play's designed tier.
                    if ptName2 in agg['passByTier']:
                        tierName = ptName2
                    else:
                        tierName = getattr(play, 'intendedPassTier', None)
                    if tierName in agg['passByTier']:
                        agg['passByTier'][tierName] += 1
                    isComplete = getattr(play, 'isPassCompletion', False)
                    isInt = getattr(play, 'isInterception', False)
                    isSack = getattr(play, 'isSack', False)
                    isDrop = getattr(play, 'passIsDropped', False)
                    isThrowAway = (ptName2 == 'throwAway')
                    if isInt:
                        agg['interceptions'] += 1
                        if tierName in agg['intByTier']:
                            agg['intByTier'][tierName] += 1
                    if isSack:
                        agg['sacks'] += 1
                        if tierName in agg['sackByTier']:
                            agg['sackByTier'][tierName] += 1
                        # Sack play.yardage is stored negative (loss); record
                        # the magnitude so we can compute Net Yards Per Attempt.
                        sackYd = int(getattr(play, 'yardage', 0) or 0)
                        if sackYd < 0:
                            agg['sackYards'] += -sackYd
                    if isDrop and tierName in agg['dropByTier']:
                        agg['dropByTier'][tierName] += 1
                    if isThrowAway:
                        agg['throwAways'] += 1
                        if tierName in agg['throwAwayByTier']:
                            agg['throwAwayByTier'][tierName] += 1
                    # Incomplete = pass attempt, not sacked, not throwaway,
                    # not caught, not picked, not dropped (true missed throw).
                    if (not isSack and not isThrowAway and not isComplete
                            and not isInt and not isDrop):
                        if tierName in agg['incompleteByTier']:
                            agg['incompleteByTier'][tierName] += 1
                    # Per-tier diagnostic sums — only counted on actual throws
                    # (not sacks or throwaways) since that's where the model
                    # produced contact/secure/catch probabilities.
                    if not isSack and not isThrowAway and tierName in agg['thrownByTier']:
                        insights2 = getattr(play, 'insights', None) or {}
                        passI = insights2.get('pass', {}) if isinstance(insights2, dict) else {}
                        if 'throwQuality' in passI:
                            agg['thrownByTier'][tierName] += 1
                            agg['tqSumByTier'][tierName] += passI.get('throwQuality', 0) or 0
                            agg['opennessSumByTier'][tierName] += passI.get('rcvOpenness', 0) or 0
                            agg['catchProbSumByTier'][tierName] += passI.get('catchProbability', 0) or 0
                            agg['contactProbSumByTier'][tierName] += passI.get('contactProbability', 0) or 0
                            agg['secureProbSumByTier'][tierName] += passI.get('secureProbability', 0) or 0
                            agg['covDefSumByTier'][tierName] += passI.get('catchDefCoverage', 0) or 0
                    if isComplete:
                        agg['passCompletions'] += 1
                        if tierName in agg['compByTier']:
                            agg['compByTier'][tierName] += 1
                        yd = int(getattr(play, 'yardage', 0) or 0)
                        agg['totalPassYards'] += yd
                        agg['longestPass'] = max(agg['longestPass'], yd)
                        insights = getattr(play, 'insights', None) or {}
                        passInsight = insights.get('pass', {}) if isinstance(insights, dict) else {}
                        airYards = int(passInsight.get('airYards', 0) or 0)
                        yac = int(passInsight.get('yac', 0) or 0)
                        agg['totalAirYards'] += airYards
                        agg['totalYac'] += yac
                        if yd >= 20:
                            agg['passes20plus'] += 1
                        if yd >= 30:
                            agg['passes30plus'] += 1
                        if yd >= 40:
                            agg['passes40plus'] += 1
                        if getattr(play, 'isTd', False):
                            agg['passTd'] += 1
                            if tierName in agg['passTdByTier']:
                                agg['passTdByTier'][tierName] += 1
                            if yd >= 30:
                                agg['passTd30plus'] += 1

                if getattr(play, 'isFumbleLost', False):
                    agg['fumblesLost'] += 1

            os.makedirs('logs', exist_ok=True)
            with open('logs/sim_analytics.jsonl', 'a') as f:
                f.write(_json.dumps(agg) + '\n')
        except Exception:
            pass

    def _estimateAvailablePlays(self) -> int:
        """Conservative estimate of productive offensive plays remaining before
        regulation ends, RESERVING ~7s for a closing FG attempt.

        So "1 play available" means: room for one productive snap AND still
        kick the FG before time expires. "0 plays available" means: only
        time to snap the FG itself.

        Inter-play clock-stopper preference (cheapest first):
          - Timeout (~3s reset, costs a TO)
          - Spike (~5s burn, costs a down — only viable on 1st/2nd down since
            spiking on 3rd would forfeit possession)
          - Sideline / incomplete pass (~18s — partial drain mixed with clock
            stops, not always achievable)

        Each productive play burns ~7s of execution. Spikes count as zero-yard
        clock-stoppers between productive plays, not as productive plays.
        """
        secs = self.gameClockSeconds - 7  # reserve for closing FG kick
        if secs <= 5:
            return 0
        timeoutsLeft = (
            self.homeTimeoutsRemaining if self.offensiveTeam is self.homeTeam
            else self.awayTimeoutsRemaining
        )
        # Realistic spike budget — using more would forfeit too many downs.
        # Down 1 or 2 → 1 spike between productive plays; 3rd down → 0.
        spikesAvailable = 1 if self.down < 3 else 0
        plays = 0
        while secs > 5:
            plays += 1
            secs -= 7  # productive play execution
            if secs <= 5:
                break
            if timeoutsLeft > 0:
                timeoutsLeft -= 1
                secs -= 3
            elif spikesAvailable > 0:
                spikesAvailable -= 1
                secs -= 5
            else:
                secs -= 18
        return plays

    def _isGarbageTime(self, scoreDiff: int) -> bool:
        """Check if the deficit is too large to realistically overcome.

        When True, trailing teams should stop hurrying up, spiking, and
        burning timeouts — the game is effectively decided.
        """
        if scoreDiff >= 0:
            return False
        deficit = abs(scoreDiff)
        q = self.currentQuarter
        if q <= 2:
            return False  # first half — plenty of time
        secs = self.gameClockSeconds
        if q == 3:
            return deficit > 35   # 5 TDs with a full quarter ahead
        # Q4: scale by time remaining
        if secs > 300:
            return deficit > 28   # 4 TDs in 5+ min
        if secs > 120:
            return deficit > 21   # 3 TDs in 2-5 min
        return deficit > 16       # 2+ scores in under 2 min

    def _shouldTargetSideline(self, scoreDiff: int, coach) -> bool:
        """Decide whether this pass should target the sideline to stop the clock.

        Only fires when trailing/tied in Q2 or Q4. Probability scales with
        time urgency, timeout availability, and coach clock management quality.
        """
        if self.currentQuarter not in (2, 4):
            return False
        # A leading team late in Q4 wants the clock RUNNING — never stop it.
        # But in Q2 a leading team still stops the clock to score before the
        # half (the half ends regardless, so there's no lead to protect).
        if self.currentQuarter == 4 and scoreDiff > 0:
            return False
        if self._isGarbageTime(scoreDiff):
            return False
        # Suppress sideline targeting when setting up an end-of-game FG —
        # we WANT the clock running so the FG ends the game with no time left.
        if self._isFgDrainMode():
            return False

        clockIQ = self._coachClockIQ(coach)
        secs = self.gameClockSeconds
        isHome = (self.offensiveTeam == self.homeTeam)
        timeoutsLeft = self.homeTimeoutsRemaining if isHome else self.awayTimeoutsRemaining
        noTimeouts = (timeoutsLeft == 0)

        # Base probability by time urgency — higher when no timeouts
        if secs < 60:
            baseProb = 0.85 if noTimeouts else 0.70
        elif secs < 120:
            baseProb = 0.75 if noTimeouts else 0.55
        elif secs < 300:
            baseProb = 0.40
        else:
            baseProb = 0.15

        # Coach quality: even bad coaches know to throw sideline when desperate
        coachScale = 0.4 + 0.6 * clockIQ

        # Reduce if team has plenty of timeouts and time
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
        self._timeoutCalled = True
        timeoutEvent = {
            'text': f'{self.offensiveTeam.name} calls timeout',
            'quarter': self.currentQuarter,
            'timeRemaining': self.formatTime(self.gameClockSeconds),
        }
        self.gameFeed.insert(0, {'event': timeoutEvent})
        self.broadcastGameState(includeLastPlay=False, eventMessage=timeoutEvent)

    def _checkDefensiveTimeout(self):
        """Defense calls timeout to stop the clock when trailing and the offense is milking clock.

        Q4/OT: triggers up to 5 min out with urgency scaling; under 2 min uses original high-urgency logic.
        Q2: triggers under 60 sec (moderate, end-of-half is less critical).
        """
        if self.currentQuarter not in (2, 4) and self.currentQuarter < 5:
            return
        if not self.clockRunning:
            return
        # The two-minute warning already stopped the clock for free — don't
        # waste a timeout on the dead clock before a snap runs.
        if self._clockStoppedByWarning:
            return
        secs = self.gameClockSeconds
        # Determine if the defensive team is trailing
        defIsHome = (self.defensiveTeam == self.homeTeam)
        defScore = self.homeScore if defIsHome else self.awayScore
        offScore = self.awayScore if defIsHome else self.homeScore
        # Q4/OT: only a trailing defense burns timeouts (a leading/tied defense
        # wants the clock to run out). Q2: any team stops the clock to get the
        # ball back and try to score before the half, regardless of score.
        if (self.currentQuarter == 4 or self.currentQuarter >= 5) and defScore >= offScore:
            return
        deficit = offScore - defScore
        # Don't waste timeouts in an unwinnable game
        defScoreDiff = defScore - offScore  # negative when trailing
        if self._isGarbageTime(defScoreDiff):
            return
        defTimeouts = self.homeTimeoutsRemaining if defIsHome else self.awayTimeoutsRemaining
        if defTimeouts <= 0:
            return
        # Time window: a defense burns timeouts to get the ball back, which only
        # pays off close to the end. Inside 2:00 for a one-score game; extended
        # to 3:00 only when down multiple scores (genuinely needs the clock).
        # Calling them at 4-5 min in a tight game is the "no coach does that" case.
        isEndGame = self.currentQuarter == 4 or self.currentQuarter >= 5
        multiScore = deficit >= 9
        if isEndGame:
            threshold = 180 if multiScore else self.gameRules.timeoutClockThreshold
        else:
            threshold = 60  # Q2 end-of-half
        if secs > threshold:
            return
        # Don't waste a timeout right before the free two-minute-warning stop.
        if (self.currentQuarter in (2, 4) and not self.twoMinuteWarningShown
                and self.gameRules.timeoutClockThreshold < secs
                <= self.gameRules.timeoutClockThreshold + 15):
            return
        defCoach = getattr(self.defensiveTeam, 'coach', None)
        defGameIQ = self._coachClockIQ(defCoach)
        # Urgency-based timeout probability
        if secs <= self.gameRules.timeoutClockThreshold:
            # Inside 2:00 — high urgency to get the ball back
            toChance = (0.5 + 0.5 * defGameIQ) if isEndGame else (0.4 + 0.4 * defGameIQ)
        else:
            # 2-3 min, multi-score only — urgency builds toward the 2-min mark
            urgency = max(0.0, (180 - secs) / 60)
            toChance = (0.25 + 0.45 * defGameIQ) * urgency
        if _random.random() >= toChance:
            return
        # Call timeout
        if defIsHome:
            self.homeTimeoutsRemaining = max(0, self.homeTimeoutsRemaining - 1)
        else:
            self.awayTimeoutsRemaining = max(0, self.awayTimeoutsRemaining - 1)
        self.clockRunning = False
        self._timeoutCalled = True
        timeoutEvent = {
            'text': f'{self.defensiveTeam.name} calls timeout',
            'quarter': self.currentQuarter,
            'timeRemaining': self.formatTime(self.gameClockSeconds),
        }
        self.gameFeed.insert(0, {'event': timeoutEvent})
        self.broadcastGameState(includeLastPlay=False, eventMessage=timeoutEvent)

    def _runPassBias(self, gameplan) -> int:
        """Map runPassRatio (0.25–0.75) to threshold offset (-4 to +4) for batched_randint(1,10)."""
        if gameplan is None:
            return 0
        return round((gameplan.runPassRatio - 0.5) * 16)

    def _estimateFgProbability(self):
        """Estimate FG make probability for the current field position and kicker."""
        kicker = self.offensiveTeam.rosterDict.get('k')
        if not kicker:
            return 0.0
        fgDist = self.yardsToEndzone + self.gameRules.fgSnapDistance
        baseFgProb = 1 / (1 + math.exp(0.18 * (fgDist - 52)))
        normalizedSkill = (kicker.gameAttributes.overallRating - 50) / 50
        fgProb = baseFgProb * (0.52 + normalizedSkill * 0.85)
        if fgDist < 30:
            fgProb = min(0.96, fgProb + 0.10)
        return max(0.05, min(0.96, fgProb))

    def _coachFgThreshold(self, coach):
        """Compute the minimum FG probability a coach requires before attempting.

        Aggressive coaches tolerate lower probabilities (attempt longer FGs).
        Conservative coaches demand higher confidence before sending the kicker out.
        The kicker's in-game performance also shifts the threshold — recent misses
        make coaches more cautious, while a perfect day builds trust.
        """
        baseThreshold = self.gameRules.fgMinAttemptProb  # 0.20

        # ── Coach aggressiveness ──
        # aggrNorm: -1 (conservative) to +1 (aggressive)
        aggrNorm = (coach.aggressiveness - COACH_ATTR_NEUTRAL) / COACH_ATTR_RANGE if coach else 0.0
        # Aggressive: lowers threshold (will try longer FGs)
        # Conservative: raises threshold (wants higher confidence)
        aggrShift = aggrNorm * 0.08
        threshold = baseThreshold - aggrShift

        # ── Kicker in-game performance ──
        kicker = self.offensiveTeam.rosterDict.get('k')
        if kicker:
            kStats = kicker.gameStatsDict.get('kicking', {})
            att = kStats.get('fgAtt', 0)
            made = kStats.get('fgs', 0)
            misses = att - made
            if att > 0:
                if misses > 0:
                    # Each miss raises the threshold — coach loses trust
                    # Scaled so 1 miss = +0.04, 2 misses = +0.07, 3+ = +0.09
                    perfPenalty = min(0.09, misses * 0.04 - (misses - 1) * 0.005)
                    threshold += perfPenalty
                elif made >= 2:
                    # Perfect day with 2+ makes — coach trusts the kicker more
                    perfBonus = min(0.04, made * 0.015)
                    threshold -= perfBonus

        return max(0.10, min(0.35, threshold))

    def _otPlayCaller(self, scoreDiff: int):
        """Handle play calling in overtime (Q5). Called only when currentQuarter == 5."""
        coach = getattr(self.offensiveTeam, 'coach', None)
        kicker = self.offensiveTeam.rosterDict.get('k')
        kickerMaxFg = (kicker.maxFgDistance - self.gameRules.fgSnapDistance) if kicker else 0
        fgProb = self._estimateFgProbability()
        fgThreshold = self._coachFgThreshold(coach)

        # First OT possession: a FG doesn't win — the other team gets a
        # guaranteed possession to respond. Play for TD on early downs.
        isFirstPoss = (
            not self.otFirstPossComplete
            and self.offensiveTeam is self.otFirstPossTeam
        )

        # Early-down FG to win/take lead. Even at 80% probability, advancing
        # a few yards turns it into a 95% chip shot — so the threshold for
        # kicking on 1st-3rd down is much higher than the 4th-down fallback.
        # Coach aggressiveness shifts it slightly: aggressive coaches will
        # take ~88% kicks, conservative coaches demand near-automatic.
        # When a FG only ties (down by exactly 3) or it's the first
        # possession, play for TD on downs 1–3 and only kick on 4th.
        fgOnlyTies = (scoreDiff == -3)
        if (self.down < 4 and scoreDiff >= -3 and not isFirstPoss and not fgOnlyTies
                and self.yardsToEndzone <= kickerMaxFg):
            aggrNorm = (coach.aggressiveness - COACH_ATTR_NEUTRAL) / COACH_ATTR_RANGE if coach else 0.0
            # 60 aggr → 0.96 (chip shot only), 80 → 0.92, 100 → 0.88
            earlyDownFgThreshold = 0.92 - aggrNorm * 0.04
            if fgProb >= earlyDownFgThreshold:
                self.play.playType = PlayType.FieldGoal
                return

        if self.down == 4:
            # Kick FG on 4th if probability is reasonable and it ties or wins.
            # Long-shot FG check: if the kick is low-probability AND the
            # yards-to-go is reachable, prefer going for it to get closer
            # for a higher-percentage attempt. Aggressive coaches roll the
            # dice on the conversion more often.
            if scoreDiff >= -3 and self.yardsToEndzone <= kickerMaxFg and fgProb >= fgThreshold:
                if fgProb < 0.55 and self.yardsToFirstDown <= 5:
                    aggrNorm = (coach.aggressiveness - COACH_ATTR_NEUTRAL) / COACH_ATTR_RANGE if coach else 0.0
                    # 60 aggr → 15%, 80 → 45%, 100 → 75%
                    goForItChance = 0.45 + aggrNorm * 0.30
                    if _random.random() < goForItChance:
                        if self.yardsToFirstDown <= 2:
                            self.play.runPlay()
                        else:
                            self.play.passPlay(self._selectPassPlay('short'))
                        return
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
        targetSideline = self._shouldTargetSideline(scoreDiff, coach)

        # Tied and in FG range: consider kicking now or playing conservatively.
        # On first possession, a FG just gives the opponent a chance to respond —
        # push for TD instead of settling for 3.
        inFgRange = self.yardsToEndzone <= kickerMaxFg and fgProb >= fgThreshold
        if scoreDiff == 0 and inFgRange:
            if isFirstPoss:
                # First possession — play aggressively for TD, protect ball
                weights = {'run': 40.0, 'short': 30.0, 'medium': 25.0, 'long': 5.0}
                self.play.insights['_otWeights'] = weights
                self._executeWeightedPlay(weights, targetSideline=targetSideline)
                return
            # How easy is this FG? Use probability directly (0.96 = chip shot, threshold = max range)
            fgEase = max(0.0, (fgProb - fgThreshold) / (0.96 - fgThreshold))
            clockIQ = self._coachClockIQ(coach)
            # Chance to kick FG now — scales with proximity, down, and coach IQ
            downBase = {1: 0.05, 2: 0.15, 3: 0.40}.get(self.down, 0.05)
            fgChance = fgEase * (downBase + clockIQ * 0.25)
            if _random.random() < fgChance:
                self.play.playType = PlayType.FieldGoal
                return
            # Otherwise play conservatively — runs and short passes to protect the ball
            weights = {'run': 55.0, 'short': 30.0, 'medium': 15.0, 'long': 0.0}
            self.play.insights['_otWeights'] = weights
            self._executeWeightedPlay(weights, targetSideline=targetSideline)
            return

        weights = self._computePlayWeights(scoreDiff, coach)
        self.play.insights['_otWeights'] = weights
        self._executeWeightedPlay(weights, targetSideline=targetSideline)

    def _fourthDownCaller(self, scoreDiff: int, coach, isHome: bool):
        """Handle 4th down play calling."""
        # Set sideline targeting for any pass plays called in this method
        self.play.targetSideline = self._shouldTargetSideline(scoreDiff, coach)

        # Deep own territory: default punt, but override if trailing late in Q4
        # (or Q2 end-of-half past midfield)
        if self.yardsToSafety <= 35:
            isLateGameDesperation = (
                (self.currentQuarter == 4 and scoreDiff < 0 and self.gameClockSeconds < 150)
                or (self.currentQuarter == 2 and scoreDiff <= 0
                    and self.gameClockSeconds < 60 and self.yardsToSafety > 50)
            )
            if not isLateGameDesperation:
                self.play.playType = PlayType.Punt
                return
            # Under 60 seconds trailing: NEVER punt — no time to get ball back
            if not (self.currentQuarter == 4 and scoreDiff < 0 and self.gameClockSeconds < 60):
                gameIQ = self._coachClockIQ(coach)
                if _random.random() >= 0.5 + 0.5 * gameIQ:
                    # Bad coach punts in desperation — terrible decision
                    self.play.playType = PlayType.Punt
                    return

        kicker = self.offensiveTeam.rosterDict.get('k')
        kickerMaxDistance = (kicker.maxFgDistance - self.gameRules.fgSnapDistance) if kicker else 0
        fgProb = self._estimateFgProbability()
        fgThreshold = self._coachFgThreshold(coach)
        inFieldGoalRange = self.yardsToEndzone <= kickerMaxDistance and fgProb >= fgThreshold

        aggrNorm = (coach.aggressiveness - COACH_ATTR_NEUTRAL) / COACH_ATTR_RANGE if coach else 0.0
        goForItThreshold = max(1, min(9, round(4 + aggrNorm * 3)))

        # ── Record 4th down context ──
        self.play.insights['fourthDown'] = {
            'fgProbability': round(fgProb * 100, 1),
            'fgThreshold': round(fgThreshold * 100, 1),
            'inFgRange': inFieldGoalRange,
            'goForItThreshold': goForItThreshold,
            'yardsToEndzone': self.yardsToEndzone,
            'coachAggr': coach.aggressiveness if coach else None,
        }

        # Q2 end-of-half: punting wastes the half. With limited time left
        # and not stuck deep in own territory, take a shot (or kick a
        # makeable FG) instead of giving the ball up. Aggressive coaches
        # pull the trigger earlier; even the most conservative coach
        # stops punting once the clock dips under 15s.
        if self.currentQuarter == 2 and self.yardsToSafety > 35:
            shotTimeThreshold = max(15, round(25 + aggrNorm * 10))
            if self.gameClockSeconds <= shotTimeThreshold:
                if inFieldGoalRange:
                    self.play.playType = PlayType.FieldGoal
                    return
                # Take a shot at the endzone — long if there's room, otherwise medium
                passLength = 'long' if self.yardsToEndzone <= 60 else 'medium'
                self.play.passPlay(self._selectPassPlay(passLength))
                return

        if scoreDiff > 0:
            if self.currentQuarter == 4 and self.gameClockSeconds < 300:
                # Leading with little time: burn clock, don't risk a FG miss
                # Skip kneel inside own 2 to avoid backing into a safety —
                # fall through and let the run/punt logic pick something safer.
                if self.gameClockSeconds <= 40 and self.yardsToSafety > 2:
                    self.play.kneel()
                    return
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
            # Deep in opponent territory: go for it on short yardage instead of punting
            if self.yardsToEndzone <= 40 and self.yardsToFirstDown <= 3:
                # Inside 40: almost always go for it on 4th and short
                threshold = max(1, min(9, round(6 + aggrNorm * 3)))
                x = batched_randint(1, 10)
                if x <= threshold:
                    if self.yardsToFirstDown <= 1:
                        self.play.runPlay()
                    else:
                        self.play.passPlay(self._selectPassPlay('short'))
                    return
            elif self.yardsToFirstDown <= 1 and self.yardsToSafety > 45:
                x = batched_randint(1, 10)
                if x <= max(1, min(9, round(3 + aggrNorm * 3))):
                    self.play.runPlay()
                    return
            self.play.playType = PlayType.Punt
            return

        elif scoreDiff < 0 and inFieldGoalRange:
            deficit = abs(scoreDiff)
            aggrNorm = (coach.aggressiveness - COACH_ATTR_NEUTRAL) / COACH_ATTR_RANGE if coach else 0.0
            if self.currentQuarter == 4 and self.gameClockSeconds < self.gameRules.timeoutClockThreshold:
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
                        timeFactor = (secs - 45) / (self.gameRules.timeoutClockThreshold - 45)
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
                fgThresh = max(5, min(10, round(9 - aggrNorm * 2)))
                if x <= fgThresh:
                    self.play.playType = PlayType.FieldGoal
                    return
                self.play.passPlay(self._selectPassPlay('medium'))
                return
            else:
                x = batched_randint(1, 10)
                fgThresh = max(4, min(9, round(7 - aggrNorm * 2)))
                if x <= fgThresh:
                    self.play.playType = PlayType.FieldGoal
                    return
                self.play.passPlay(self._selectPassPlay('medium'))
                return

        elif scoreDiff < 0:
            deficit = abs(scoreDiff)
            secs = self.gameClockSeconds
            if self.currentQuarter == 4:
                gameIQ = self._coachClockIQ(coach)
                aggrMod = aggrNorm * 0.15  # risk tolerance: aggressive +0.15, conservative -0.15

                # Under 2.5 min: must go for it — punting is conceding
                if secs < 150:
                    # Bad coaches may pick the wrong play tier, but they still go for it
                    if self.yardsToFirstDown <= 3:
                        self.play.passPlay(self._selectPassPlay('short'))
                    elif self.yardsToFirstDown <= 10:
                        self.play.passPlay(self._selectPassPlay('medium'))
                    else:
                        self.play.passPlay(self._selectPassPlay('long'))
                    return

                # 2.5–5 min: go for it based on deficit and distance
                if secs <= 300:
                    if deficit <= 8:
                        # Down 1 score: go for it on short/medium yardage
                        if self.yardsToFirstDown <= 3:
                            self.play.passPlay(self._selectPassPlay('short'))
                            return
                        elif self.yardsToFirstDown <= 8:
                            self.play.passPlay(self._selectPassPlay('medium'))
                            return
                        else:
                            # Long yardage: good/aggressive coaches go for it, bad/conservative punt
                            if _random.random() < 0.3 + 0.5 * gameIQ + aggrMod:
                                self.play.passPlay(self._selectPassPlay('long'))
                                return
                    elif deficit <= 16:
                        if self.yardsToFirstDown <= 3:
                            self.play.passPlay(self._selectPassPlay('short'))
                            return
                        elif self.yardsToFirstDown <= 5:
                            if _random.random() < 0.7 + 0.2 * gameIQ + aggrMod:
                                self.play.passPlay(self._selectPassPlay('medium'))
                                return
                        else:
                            if _random.random() < 0.55 + 0.3 * gameIQ + aggrMod:
                                self.play.passPlay(self._selectPassPlay('long'))
                                return
                    else:
                        # Down 17+: always go for it
                        self.play.passPlay(self._selectPassPlay('long'))
                        return

                # 5+ min: standard trailing behavior
                if deficit <= 8 and self.yardsToFirstDown <= 2:
                    self.play.passPlay(self._selectPassPlay('short'))
                    return
                elif deficit <= 8 and self.yardsToFirstDown <= 5:
                    # Aggressive coaches willing to attempt short yardage with time
                    if _random.random() < max(0, 0.1 + aggrMod):
                        self.play.passPlay(self._selectPassPlay('short'))
                        return

            # Q2 two-minute drill: go for it past midfield with under 60 sec
            elif self.currentQuarter == 2 and secs < 60 and self.yardsToSafety > 50:
                if self.yardsToFirstDown <= 3:
                    self.play.passPlay(self._selectPassPlay('short'))
                elif self.yardsToFirstDown <= 10:
                    self.play.passPlay(self._selectPassPlay('medium'))
                else:
                    self.play.passPlay(self._selectPassPlay('long'))
                return

            elif self.currentQuarter == 3 and deficit <= 8 and self.yardsToFirstDown <= 2:
                self.play.passPlay(self._selectPassPlay('short'))
                return
            self.play.playType = PlayType.Punt
            return

        # Tied + Q4 + meaningful clock left + manageable 4th down — aggressive
        # coaches may go for the conversion to advance for a higher-confidence
        # FG (or a winning TD) instead of kicking from longer range and giving
        # the ball back with significant time left. Chip-shot range still
        # defaults to the kick (high prob > the conversion gamble).
        if (self.currentQuarter == 4 and scoreDiff == 0 and inFieldGoalRange
                and self.gameClockSeconds >= 30
                and self.yardsToFirstDown <= 5
                and self.yardsToEndzone > 15
                and fgProb < 0.92):
            goBias = max(0.0, aggrNorm)  # 0 (avg) to 1 (max aggressive)
            if self.yardsToFirstDown <= 2:
                goChance = 0.10 + goBias * 0.40  # avg=10%, aggressive=50%
            else:
                goChance = 0.05 + goBias * 0.20  # avg=5%, aggressive=25%
            if _random.random() < goChance:
                self.play.insights['fourthDown']['decision'] = 'goForIt'
                self.play.insights['fourthDown']['reason'] = (
                    'tied Q4 with time — aggressive push to advance FG'
                )
                if self.yardsToFirstDown <= 2:
                    self.play.runPlay()
                else:
                    self.play.passPlay(self._selectPassPlay('short'))
                return

        if self.yardsToEndzone <= 5 and inFieldGoalRange:
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
            # Tied or trailing (outside Q4 urgency), out of FG range
            if self.yardsToFirstDown == 1:
                if self.yardsToSafety >= 50 or (scoreDiff < -14 and self.currentQuarter >= 3):
                    x = batched_randint(1, 10)
                    if x <= max(1, min(7, goForItThreshold - 1)):
                        self.play.runPlay()
                        return
                self.play.playType = PlayType.Punt
                return
            elif self.yardsToFirstDown == 2:
                if (self.yardsToSafety >= 50 and goForItThreshold >= 5) or (scoreDiff < -21 and self.currentQuarter == 4 and self.gameClockSeconds < 600):
                    x = batched_randint(1, 10)
                    if x <= max(1, min(5, goForItThreshold - 3)):
                        self.play.passPlay(self._selectPassPlay('short'))
                        return
                self.play.playType = PlayType.Punt
                return
            else:
                if (self.yardsToSafety >= 55 and self.yardsToFirstDown <= goForItThreshold and goForItThreshold >= 6) or (scoreDiff < -17 and self.currentQuarter == 4 and self.gameClockSeconds < 300):
                    x = batched_randint(1, 10)
                    if x <= max(1, min(4, goForItThreshold - 4)):
                        self.play.passPlay(self._selectPassPlay('medium'))
                        return
                self.play.playType = PlayType.Punt
                return

    def _getBasePlayWeights(self) -> dict:
        """Return raw down/distance base weights before any modifier layers.
        Tuned to land roughly 60/40 pass/run across a typical drive, which
        is the NFL-realistic split. Previously was running 85/15 in games
        with extended trailing — the base 1st-down and 2nd-and-medium
        weights were too pass-heavy, compounding with situational pushes
        to extinguish the run game.
        """
        ytg = self.yardsToFirstDown
        if self.down == 1:
            # 1st down: balanced 50/50 base. Most plays happen here, so
            # this is the biggest lever on overall pass/run ratio.
            return {'run': 50.0, 'short': 22.0, 'medium': 18.0, 'long': 8.0, 'deep': 2.0}
        elif self.down == 2:
            if ytg <= 4:
                # 2nd & short — run preferred (was already).
                return {'run': 58.0, 'short': 28.0, 'medium': 10.0, 'long': 4.0, 'deep': 0.0}
            elif ytg <= 9:
                # 2nd & medium — closer to balanced, was 35/65 too pass-heavy.
                return {'run': 45.0, 'short': 20.0, 'medium': 25.0, 'long': 9.0, 'deep': 1.0}
            else:
                # 2nd & long — obvious passing situation.
                return {'run': 22.0, 'short': 20.0, 'medium': 28.0, 'long': 26.0, 'deep': 4.0}
        else:
            if ytg <= 3:
                # 3rd & short — run is the percentage call.
                return {'run': 60.0, 'short': 32.0, 'medium': 4.0, 'long': 4.0, 'deep': 0.0}
            elif ytg <= 5:
                # 3rd & medium-short — was 20% run, bump to 25%.
                return {'run': 25.0, 'short': 45.0, 'medium': 21.0, 'long': 9.0, 'deep': 0.0}
            elif ytg <= 12:
                # 3rd & medium-long — still mostly pass but a draw is realistic.
                return {'run': 12.0, 'short': 15.0, 'medium': 48.0, 'long': 23.0, 'deep': 2.0}
            else:
                # 3rd & extra long — almost always pass.
                return {'run': 6.0, 'short': 10.0, 'medium': 15.0, 'long': 61.0, 'deep': 8.0}

    def _computePlayWeights(self, scoreDiff: int, coach) -> dict:
        """Compute play call probability weights for downs 1–3."""
        weights = dict(self._getBasePlayWeights())

        weights = self._applySituationalMods(weights, scoreDiff, coach)
        weights = self._applyMatchupMods(weights, coach)
        weights = self._applyCoachMods(weights, coach)

        # Setting up end-of-game FG: bias toward in-bounds runs to keep clock
        # moving. Avoid downfield passes (incomplete = clock stop).
        if self._isFgDrainMode():
            weights['run'] = weights.get('run', 0) * 3.0
            weights['short'] = weights.get('short', 0) * 1.0
            weights['medium'] = weights.get('medium', 0) * 0.3
            weights['long'] = weights.get('long', 0) * 0.15
            weights['deep'] = weights.get('deep', 0) * 0.05
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

        def _mul(key, m):
            weights[key] = weights.get(key, 0) * (1 + (m - 1) * sit)

        def _flat(key, m):
            weights[key] = weights.get(key, 0) * m

        # Coach attributes normalized to [0, 1] for personality math.
        # Raw normalization yields [-1, +1] around neutral (80); shift+scale
        # to [0, 1] so median coaches land at 0.5 and the trailing/leading
        # archetypes actually fire across the population (not just elites).
        if coach:
            adaptRaw = (coach.adaptability - COACH_ATTR_NEUTRAL) / COACH_ATTR_RANGE
            aggrRaw  = (coach.aggressiveness - COACH_ATTR_NEUTRAL) / COACH_ATTR_RANGE
            adapt = max(0.0, min(1.0, (adaptRaw + 1.0) / 2.0))
            aggr  = max(0.0, min(1.0, (aggrRaw + 1.0) / 2.0))
        else:
            adapt = aggr = 0.5

        # ── Q4 LAST 2 MIN trailing — universal desperation, no coach modulation ──
        # When the clock is genuinely out, every coach throws downfield.
        if q == 4 and scoreDiff < 0 and secs < 120:
            _mul('run', 0.1)
            _mul('short', 1.3)
            _mul('medium', 1.8)
            _mul('long', 2.5)
            _mul('deep', 3.0)

        # ── TRAILING (Q3+ with time, not desperation mode) — coach identity ──
        # Disciplined coaches (high adapt, low aggr) sustain drives via short/
        # medium. Aggressive-undisciplined coaches panic into deep shots — the
        # shutout pattern: chuck deep, miss, drives die, deficit compounds.
        # Same direction (more pass) but quality of pass selection differs.
        elif scoreDiff < -7 and (q == 3 or (q == 4 and secs >= 120)):
            deficit = abs(scoreDiff)
            if deficit <= 14:
                deficitTier = 0.4
            elif deficit <= 21:
                deficitTier = 0.7
            else:
                deficitTier = 1.0

            # Disciplined response — shift toward sustainable routes
            discipline = adapt * (1 - aggr * 0.4)
            shiftDisciplined = discipline * deficitTier
            _flat('short',  1 + shiftDisciplined * 0.5)
            _flat('medium', 1 + shiftDisciplined * 0.3)
            _flat('long',   1 - shiftDisciplined * 0.3)
            _flat('deep',   1 - shiftDisciplined * 0.5)
            _flat('run',    1 - shiftDisciplined * 0.3)

            # Panic response — additional deep/long bias for the un-adaptive
            # aggressive coach. Drives die faster, deficit compounds.
            panic = aggr * (1 - adapt) * deficitTier
            _flat('deep', 1 + panic * 0.7)
            _flat('long', 1 + panic * 0.4)
            _flat('run',  1 - panic * 0.4)

            self._tallyCoachArchetype(
                'trailing_disciplined' if discipline > panic else 'trailing_panic'
            )

        # ── LEADING (Q3+ with significant lead) — coach archetype ──
        # Killer (high aggr + high adapt) presses the throat. Clock-killer
        # (low aggr + high adapt) drains the clock professionally. Reckless
        # (high aggr + low adapt) keeps chucking deep, sets up the comeback.
        # Cruise (low both) coasts on the default playbook.
        elif scoreDiff > 7 and (q == 3 or q == 4):
            if scoreDiff <= 14:
                leadTier = 0.4
            elif scoreDiff <= 21:
                leadTier = 0.7
            else:
                leadTier = 1.0

            killerMode = aggr * (0.5 + adapt * 0.5)
            clockKill  = (1 - aggr) * adapt

            if killerMode > 0.45:
                # Press the advantage — maintain attack, slight deep pullback
                _flat('deep',   1 - leadTier * 0.3)
                _flat('medium', 1 + leadTier * 0.1)
                _flat('long',   1 + leadTier * 0.1)
                self._tallyCoachArchetype('leading_killer')
            elif clockKill > 0.35:
                # Drain the clock with runs and quick passes
                _flat('run',    1 + leadTier * 0.6)
                _flat('deep',   1 - leadTier * 0.8)
                _flat('long',   1 - leadTier * 0.5)
                _flat('medium', 1 - leadTier * 0.2)
                self._tallyCoachArchetype('leading_clockkill')
            elif aggr > 0.5:
                # Reckless leader — keeps chucking, opens door for comeback
                _flat('deep', 1 + leadTier * 0.3)
                _flat('long', 1 + leadTier * 0.2)
                _flat('run',  1 - leadTier * 0.2)
                self._tallyCoachArchetype('leading_reckless')
            else:
                # Cruise control — no adjustment, vulnerable to comeback
                self._tallyCoachArchetype('leading_cruise')

        # ── PROTECTING A ONE-SCORE LEAD late in Q4/OT ──
        # The big-lead branch above only fires at 8+. A 1-7 point lead in the
        # final minutes is exactly when a real coach runs the ball in-bounds to
        # bleed clock and force the opponent to spend timeouts — incompletions
        # would stop your own clock. Ramps as the clock winds down; coach-scaled
        # via _mul so poor clock managers protect less.
        elif 0 < scoreDiff <= 7 and q >= 4:
            if secs <= 120:
                protectUrgency = 1.0
            elif secs <= 300:
                protectUrgency = 0.6
            else:
                protectUrgency = 0.0
            if protectUrgency > 0:
                _mul('run',    1 + 0.7 * protectUrgency)
                _mul('short',  1 + 0.2 * protectUrgency)
                _mul('medium', 1 - 0.1 * protectUrgency)
                _mul('long',   1 - 0.5 * protectUrgency)
                _mul('deep',   1 - 0.7 * protectUrgency)

        # Q2 two-minute drill: REGARDLESS of score, push to score before the
        # half. A leading team does NOT sit on the ball in Q2 (clock-milking is
        # a Q4 behavior — the half ends either way, so there's no lead to
        # protect by draining time). Trailing teams lean a touch more on the
        # deep shot; everyone goes pass-first and hurries. Coach-scaled via _mul.
        if q == 2 and secs < 120:
            deepBoost = 2.0 if scoreDiff < 0 else 1.6
            _mul('run', 0.35)
            _mul('short', 1.2)
            _mul('medium', 1.4)
            _mul('long', 1.6)
            _mul('deep', deepBoost)      # shot before halftime

        # Field position adjustments — not clock-related, always full strength
        if self.yardsToEndzone <= 15:
            _flat('run', 1.3); _flat('long', 0.2); _flat('deep', 0.1)
        elif self.yardsToEndzone <= 25:
            _flat('long', 0.5); _flat('deep', 0.3)

        if self.yardsToSafety <= 5:
            _flat('run', 1.4); _flat('short', 0.7); _flat('long', 0.1); _flat('deep', 0.05)

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
            for k in ('short', 'medium', 'long', 'deep'):
                if k in weights:
                    weights[k] *= boost

        return weights

    def _applyCoachMods(self, weights: dict, coach) -> dict:
        """Apply coach personality multipliers to the weight distribution.
        Deep shots scale most aggressively with the aggressiveness attribute —
        elite-aggressive coaches (90+) take shots ~3x more often than neutral.
        """
        if coach is None:
            return weights
        aggrNorm = (coach.aggressiveness - COACH_ATTR_NEUTRAL) / COACH_ATTR_RANGE
        offMindNorm = (coach.offensiveMind - COACH_ATTR_NEUTRAL) / COACH_ATTR_RANGE

        weights['deep']   = weights.get('deep', 0) * max(0.1, 1 + 1.8 * aggrNorm)
        weights['long']   *= max(0.2, 1 + 0.5 * aggrNorm)
        weights['medium'] *= max(0.5, 1 + 0.15 * aggrNorm)
        # Run/short nerf softened: was 0.2/0.5 and 0.1/0.5 — combined with
        # the pass-heavy base that produced 85/15 splits in games where a
        # team was trailing and the coach was aggressive. New floors keep
        # run viable even for max-aggressive coaches.
        weights['run']    *= max(0.65, 1 - 0.12 * aggrNorm)
        weights['short']  *= max(0.65, 1 - 0.08 * aggrNorm)

        weights['medium'] *= max(0.5, 1 + 0.3 * offMindNorm)
        weights['long']   *= max(0.5, 1 + 0.2 * offMindNorm)
        weights['deep']   = weights.get('deep', 0) * max(0.5, 1 + 0.3 * offMindNorm)
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
            'deep':   ['Play21', 'Play22', 'Play23', 'Play24'],
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
        playCall = _random.choices(
            ['run', 'short', 'medium', 'long', 'deep'],
            weights=[weights['run'], weights['short'], weights['medium'],
                     weights['long'], weights.get('deep', 0)]
        )[0]

        self.play.insights['playCall'] = playCall

        if playCall == 'run':
            self.play.runPlay()
        else:
            self.play.targetSideline = targetSideline
            self.play.passPlay(self._selectPassPlay(playCall))

    def playCaller(self):
        isHome = (self.offensiveTeam == self.homeTeam)
        scoreDiff = (self.homeScore - self.awayScore) if isHome else (self.awayScore - self.homeScore)
        coach = getattr(self.offensiveTeam, 'coach', None)
        timeoutsLeft = self.homeTimeoutsRemaining if isHome else self.awayTimeoutsRemaining

        # ── Record situation insights (all play types) ──
        self.play.insights['situation'] = {
            'gamePressure': round(self.gamePressure),
            'momentum': round(self.momentum, 1),
            'momentumTeam': (self.homeTeam.abbr if self.momentum > MOMENTUM_DISPLAY_THRESHOLD
                             else self.awayTeam.abbr if self.momentum < -MOMENTUM_DISPLAY_THRESHOLD
                             else None),
            'offenseAbbr': self.offensiveTeam.abbr,
        }

        # ── Snapshot pre-play composure for all potential key players ──
        prePlayComposure = {}
        roster = self.offensiveTeam.rosterDict
        for pos in ['qb', 'rb', 'wr1', 'wr2', 'te', 'k']:
            p = roster.get(pos)
            if p:
                prePlayComposure[id(p)] = {
                    'confidence': round(p.gameAttributes.confidenceModifier, 3),
                    'determination': round(p.gameAttributes.determinationModifier, 3),
                }
        self.play.insights['_prePlayComposure'] = prePlayComposure

        # Clock management — evaluated before any play selection on downs 1-3
        if self.down <= 3:
            # Kneel: Q4/OT, leading — only when guaranteed to drain the clock
            # Each kneel ~40 sec; opponent timeouts only matter when game is close (≤8 pts)
            # Field-position guard: kneel loses 1 yard, so on own 1 (or goal line) it
            # would back into the endzone for a self-inflicted safety. Skip and fall
            # through to the normal play caller — it'll pick a run.
            if ((self.currentQuarter == 4 or self.currentQuarter >= 5)
                    and scoreDiff > 0 and self.yardsToSafety > 2):
                oppTimeouts = self.awayTimeoutsRemaining if isHome else self.homeTimeoutsRemaining
                availableKneels = 4 - self.down  # 1st→3, 2nd→2, 3rd→1
                # Defense won't waste TOs in unwinnable games (matches _checkDefensiveTimeout)
                maxComebackPts = 8 if self.gameClockSeconds <= 60 else 16
                effectiveOppTos = oppTimeouts if scoreDiff <= maxComebackPts else 0
                # TO'd kneels still drain 4s (snap time); free kneels drain full ~40s
                toadKneels = min(effectiveOppTos, availableKneels)
                freeKneels = availableKneels - toadKneels
                drainableSeconds = toadKneels * 4 + freeKneels * self.gameRules.kneelDrainSeconds
                if drainableSeconds >= self.gameClockSeconds:
                    self.play.insights['clockMgmt'] = {
                        'decision': 'kneel',
                        'reason': 'Can drain remaining clock with kneels',
                        'clockRemaining': self.gameClockSeconds,
                        'drainableSeconds': drainableSeconds,
                        'oppTimeouts': oppTimeouts,
                    }
                    self.play.kneel()
                    return
            # Coach game-management quality gates all situational decisions below.
            # Good coaches (IQ~1.0) almost always make the right call.
            # Bad coaches (IQ~0.0) frequently miss the correct situational play.
            gameIQ = self._coachClockIQ(coach)

            # Desperation FG: trailing by ≤3, in FG range, very little time — kick NOW
            if ((self.currentQuarter in (2, 4) or self.currentQuarter >= 5)
                    and -3 <= scoreDiff < 0 and self.gameClockSeconds <= 30):
                kicker = self.offensiveTeam.rosterDict.get('k')
                kickerMax = (kicker.maxFgDistance - self.gameRules.fgSnapDistance) if kicker else 0
                despFgProb = self._estimateFgProbability()
                if self.yardsToEndzone <= kickerMax:
                    despThreshold = self._coachFgThreshold(coach)
                    aggrNorm = (coach.aggressiveness - COACH_ATTR_NEUTRAL) / COACH_ATTR_RANGE if coach else 0.0
                    playsAvailable = self._estimateAvailablePlays()
                    # Don't auto-kick on 1st-3rd down if there's still room for a
                    # productive play before the FG. _estimateAvailablePlays
                    # already reserves ~7s for the closing FG kick, so >= 1
                    # means "1 play + FG fits". Defer rate is very high here —
                    # kicking the tying FG when a snap still fits is wrong.
                    if self.down < 4 and playsAvailable >= 1:
                        playsBonus = min(0.04, (playsAvailable - 1) * 0.02)
                        deferChance = 0.94 + playsBonus + 0.03 * aggrNorm + 0.02 * gameIQ
                        deferChance = max(0.85, min(0.99, deferChance))
                        if _random.random() < deferChance:
                            self.play.insights['clockMgmt'] = {
                                'decision': 'deferFG',
                                'reason': 'In FG range but plays remain — try for TD first',
                                'clockRemaining': self.gameClockSeconds,
                                'playsAvailable': playsAvailable,
                                'down': self.down,
                                'fgProbability': round(despFgProb * 100, 1),
                                'coachClockIQ': round(gameIQ, 2),
                            }
                            # Fall through to weighted play caller below
                        else:
                            self.play.insights['clockMgmt'] = {
                                'decision': 'desperationFG',
                                'reason': 'Coach chose tying FG over TD attempt',
                                'clockRemaining': self.gameClockSeconds,
                                'fgProbability': round(despFgProb * 100, 1),
                                'coachClockIQ': round(gameIQ, 2),
                            }
                            self.play.playType = PlayType.FieldGoal
                            return
                    elif despFgProb < despThreshold and self.gameClockSeconds > 8:
                        pass  # Long shot, try to get closer first
                    elif _random.random() < 0.6 + 0.4 * gameIQ:
                        self.play.insights['clockMgmt'] = {
                            'decision': 'desperationFG',
                            'reason': 'Trailing by 3 or less, little time left',
                            'clockRemaining': self.gameClockSeconds,
                            'fgProbability': round(despFgProb * 100, 1),
                            'coachClockIQ': round(gameIQ, 2),
                        }
                        self.play.playType = PlayType.FieldGoal
                        return

            # Game-winning FG: tied in Q4 with chip-shot range and little time —
            # take the safe winner instead of risking a turnover trying for a TD.
            # 4th down or last realistic play → kick now. Otherwise, drain clock
            # with a safe run unless the coach is aggressive enough to push.
            if (self.currentQuarter == 4 and scoreDiff == 0
                    and self.gameClockSeconds <= 30
                    and not self._isGarbageTime(scoreDiff)):
                kicker = self.offensiveTeam.rosterDict.get('k')
                kickerMax = (kicker.maxFgDistance - self.gameRules.fgSnapDistance) if kicker else 0
                if self.yardsToEndzone <= kickerMax:
                    winFgProb = self._estimateFgProbability()
                    if winFgProb >= 0.75:
                        playsAvailable = self._estimateAvailablePlays()
                        aggrNorm = (coach.aggressiveness - COACH_ATTR_NEUTRAL) / COACH_ATTR_RANGE if coach else 0.0
                        # Kick when there's no meaningful play room left.
                        # Helper reserves FG time, so playsAvailable == 0 means
                        # "only the FG itself fits before regulation ends".
                        if self.down == 4 or playsAvailable == 0:
                            self.play.insights['clockMgmt'] = {
                                'decision': 'gameWinningFG',
                                'reason': 'Tied, in chip-shot range, kick to win',
                                'clockRemaining': self.gameClockSeconds,
                                'fgProbability': round(winFgProb * 100, 1),
                                'coachClockIQ': round(gameIQ, 2),
                            }
                            self.play.playType = PlayType.FieldGoal
                            return
                        # Plays remain — aggressive coach may push for TD,
                        # but the smart default is to drain clock with a run
                        # and kick the chip shot on the last possible play.
                        pushChance = 0.10 + 0.25 * aggrNorm - 0.15 * gameIQ
                        pushChance = max(0.05, min(0.40, pushChance))
                        if _random.random() >= pushChance:
                            self.play.insights['clockMgmt'] = {
                                'decision': 'setupGameWinningFG',
                                'reason': 'In chip-shot range, draining clock for FG',
                                'clockRemaining': self.gameClockSeconds,
                                'playsAvailable': playsAvailable,
                                'fgProbability': round(winFgProb * 100, 1),
                                'coachClockIQ': round(gameIQ, 2),
                            }
                            self.play.runPlay()
                            return
                        # else: aggressive push — fall through to normal play caller
            # Spike: Q2/Q4/OT, clock running, no timeouts, trailing/tied
            # Urgency scales with remaining time — almost always spike under 30s,
            # less likely at 90s+ (sometimes better to just run a play)
            secs = self.gameClockSeconds
            # Down gate: spiking forfeits a down, so it's a 1st/2nd-down tool.
            # On 3rd down it's only defensible to stop the clock for a tying/
            # winning FG that's in range AND would be the last play (no time
            # left for another snap) — spike on 3rd, kick on 4th. Never when a
            # TD is still needed or a play still fits (that just burns the down
            # into a 4th-down must-score).
            spikeKicker = self.offensiveTeam.rosterDict.get('k')
            spikeKickerMax = (spikeKicker.maxFgDistance - self.gameRules.fgSnapDistance) if spikeKicker else 0
            spikeFgException = (self.down == 3 and -3 <= scoreDiff <= 0
                                and self.yardsToEndzone <= spikeKickerMax
                                and secs <= 20)
            spikeDownOK = self.down <= 2 or spikeFgException
            if ((self.currentQuarter in (2, 4) or self.currentQuarter >= 5)
                    and self.clockRunning
                    and secs <= self.gameRules.spikeClockThreshold
                    and timeoutsLeft == 0 and scoreDiff <= 0
                    and spikeDownOK
                    and not self._isGarbageTime(scoreDiff)):
                if secs <= 30:
                    spikeChance = 0.7 + 0.3 * gameIQ
                else:
                    spikeChance = (0.3 + 0.4 * gameIQ) * (1 - secs / 150)
                if _random.random() < spikeChance:
                    self.play.insights['clockMgmt'] = {
                        'decision': 'spike',
                        'reason': 'Stop clock, no timeouts available',
                        'clockRemaining': secs,
                        'spikeChance': round(spikeChance * 100, 1),
                        'coachClockIQ': round(gameIQ, 2),
                    }
                    self.play.spike()
                    return
            # Call timeout (offense): trailing/tied, clock running, timeouts left.
            # The offense controls its own tempo with hurry-up, so spending a
            # timeout to stop the clock only matters inside the final two minutes
            # — extended to 3:00 only when down multiple scores. Calling them at
            # 4-5 min is the "no coach does that" case the window used to allow.
            isLateGame = self.currentQuarter in (2, 4) or self.currentQuarter >= 5
            multiScore = scoreDiff <= -9
            toWindow = (180 if (self.currentQuarter >= 4 and multiScore)
                        else self.gameRules.timeoutClockThreshold)
            twoMinImminent = (self.currentQuarter in (2, 4) and not self.twoMinuteWarningShown
                              and self.gameRules.timeoutClockThreshold < secs
                              <= self.gameRules.timeoutClockThreshold + 15)
            if (isLateGame and scoreDiff <= 0 and self.clockRunning
                    and timeoutsLeft > 0 and not self._isGarbageTime(scoreDiff)
                    and not twoMinImminent and not self._clockStoppedByWarning
                    and secs <= toWindow):
                if secs <= self.gameRules.timeoutClockThreshold:
                    # Inside 2:00 — high urgency
                    toChance = 0.5 + 0.5 * gameIQ
                else:
                    # 2-3 min, multi-score only — urgency builds toward 2:00
                    urgency = max(0.0, (180 - secs) / 60)
                    toChance = (0.2 + 0.45 * gameIQ) * urgency
                if _random.random() < toChance:
                    self.play.insights['clockMgmt'] = {
                        'decision': 'timeout',
                        'reason': 'Stop clock while trailing/tied',
                        'clockRemaining': secs,
                        'timeoutsLeft': timeoutsLeft,
                        'coachClockIQ': round(gameIQ, 2),
                    }
                    self._callTimeout(isHome)
                # fall through — still need to call a play

        # Overtime
        if self.currentQuarter == 5:
            self._otPlayCaller(scoreDiff)
            # Record coach insights for OT (situation + composure already recorded above)
            otWeights = self.play.insights.pop('_otWeights', None)
            targetSideline = self._shouldTargetSideline(scoreDiff, coach)
            coachInsights = {
                'coachAggr': coach.aggressiveness if coach else None,
                'coachOffMind': coach.offensiveMind if coach else None,
                'coachAdapt': coach.adaptability if coach else None,
                'clockIQ': round(self._coachClockIQ(coach), 2),
                'targetSideline': targetSideline,
                'isOvertime': True,
                'isSecondHalf': True,
                'offenseAbbr': self.offensiveTeam.abbr,
                'defenseAbbr': self.defensiveTeam.abbr,
            }
            if otWeights:
                otTotal = sum(otWeights.values())
                coachInsights['playWeights'] = {k: round(v / otTotal * 100) for k, v in otWeights.items()} if otTotal > 0 else otWeights
            offPlan = self.homeOffGameplan if isHome else self.awayOffGameplan
            defPlan = self.awayDefGameplan if isHome else self.homeDefGameplan
            if offPlan is not None:
                coachInsights['gameplan'] = {
                    'runPassRatio': round(offPlan.runPassRatio, 2),
                    'gapDistribution': {k: round(v * 100) for k, v in offPlan.gapDistribution.items()},
                    'aggressiveness': round(offPlan.aggressiveness, 2),
                }
            if defPlan is not None:
                defCoach = getattr(self.defensiveTeam, 'coach', None)
                coachInsights['oppDefense'] = {
                    'runStopFocus': round(defPlan.runStopFocus, 2),
                    'blitzFrequency': round(defPlan.blitzFrequency, 2),
                    'aggressiveness': round(defPlan.aggressiveness, 2),
                    'coachDefMind': defCoach.defensiveMind if defCoach else None,
                    'coachAdapt': defCoach.adaptability if defCoach else None,
                    'coachAggr': defCoach.aggressiveness if defCoach else None,
                }
            self.play.insights['coach'] = coachInsights
            return

        # End-of-half / end-of-game FG attempts — compute kicker range once
        kicker = self.offensiveTeam.rosterDict.get('k')
        kickerMaxFg = (kicker.maxFgDistance - self.gameRules.fgSnapDistance) if kicker else 0

        # End-of-half FG attempt (only if reasonable probability)
        endGameFgProb = self._estimateFgProbability()
        endGameFgThreshold = self._coachFgThreshold(coach)
        if self.currentQuarter == 2 and self.gameClockSeconds < self.gameRules.timeoutClockThreshold and self.down == 4:
            if self.yardsToEndzone <= kickerMaxFg and endGameFgProb >= endGameFgThreshold:
                self.play.playType = PlayType.FieldGoal
                return

        # End-of-game FG attempt (tied, leading by ≤3, or trailing by ≤3).
        # If the kick is a long shot AND yards-to-go is reachable AND there's
        # enough clock to run another play, prefer going for it to get
        # closer. Aggressive coaches lean toward the conversion attempt;
        # very late (≤30s) the FG is the only realistic option.
        if self.currentQuarter == 4 and self.gameClockSeconds < self.gameRules.timeoutClockThreshold and self.down == 4:
            if -3 <= scoreDiff <= 3 and self.yardsToEndzone <= kickerMaxFg and endGameFgProb >= endGameFgThreshold:
                canAdvance = self.gameClockSeconds >= 30
                if canAdvance and endGameFgProb < 0.55 and self.yardsToFirstDown <= 5:
                    aggrNorm = (coach.aggressiveness - COACH_ATTR_NEUTRAL) / COACH_ATTR_RANGE if coach else 0.0
                    goForItChance = 0.45 + aggrNorm * 0.30
                    if _random.random() < goForItChance:
                        if self.yardsToFirstDown <= 2:
                            self.play.runPlay()
                        else:
                            self.play.passPlay(self._selectPassPlay('short'))
                        return
                self.play.playType = PlayType.FieldGoal
                return

        # ── Hail Mary: desperation deep throw when trailing in Q4 ──
        # Time for only one play and too far for a FG — heave it toward the endzone
        if (self.currentQuarter == 4 and scoreDiff < 0
                and self.yardsToEndzone >= 30
                and not self._isGarbageTime(scoreDiff)):
            fgCanHelp = (scoreDiff >= -3 and self.yardsToEndzone <= kickerMaxFg)
            if not fgCanHelp:
                # Only when it's guaranteed to be the last play. The hail mary
                # itself burns ~8-12s (calculatePlayDuration), so if the clock is
                # within that window the heave runs it out and nothing follows.
                # With more time than that there are still real options (notably
                # going for a first down and continuing to drive), so it's not a
                # hail mary situation — normal offense / the 4th-down caller
                # handles it.
                if self.gameClockSeconds <= 12:
                    self.play.insights['clockMgmt'] = {
                        'decision': 'hailMary',
                        'reason': 'Desperation — need a miracle score',
                        'clockRemaining': self.gameClockSeconds,
                        'yardsToEndzone': self.yardsToEndzone,
                        'scoreDiff': scoreDiff,
                        'down': self.down,
                    }
                    self.play.passPlay('Play9')
                    self.play.targetSideline = False
                    return

        # 4th down
        if self.down == 4:
            self._fourthDownCaller(scoreDiff, coach, isHome)
            # Record decision after the fact
            if 'fourthDown' in self.play.insights:
                pt = self.play.playType
                if pt == PlayType.Punt:
                    decision = 'punt'
                elif pt == PlayType.FieldGoal:
                    decision = 'fieldGoal'
                else:
                    decision = 'goForIt'
                self.play.insights['fourthDown']['decision'] = decision
            return

        # Downs 1–3: weighted probability sampling
        weights = self._computePlayWeights(scoreDiff, coach)
        targetSideline = self._shouldTargetSideline(scoreDiff, coach)

        # ── Record coach insights (downs 1-3 only) ──
        def _normalizeWeights(w):
            t = sum(w.values())
            return {k: round(v / t * 100) for k, v in w.items()} if t > 0 else w

        coachInsights = {
            'playWeights': _normalizeWeights(weights),
            'baseWeights': _normalizeWeights(self._getBasePlayWeights()),
            'coachAggr': coach.aggressiveness if coach else None,
            'coachOffMind': coach.offensiveMind if coach else None,
            'coachAdapt': coach.adaptability if coach else None,
            'clockIQ': round(self._coachClockIQ(coach), 2),
            'targetSideline': targetSideline,
        }

        # Gameplan context — what both coaches planned pre-game (and adjusted at halftime)
        offPlan = self.homeOffGameplan if isHome else self.awayOffGameplan
        defPlan = self.awayDefGameplan if isHome else self.homeDefGameplan
        if offPlan is not None:
            coachInsights['gameplan'] = {
                'runPassRatio': round(offPlan.runPassRatio, 2),
                'gapDistribution': {k: round(v * 100) for k, v in offPlan.gapDistribution.items()},
                'aggressiveness': round(offPlan.aggressiveness, 2),
            }
        if defPlan is not None:
            defCoach = getattr(self.defensiveTeam, 'coach', None)
            coachInsights['oppDefense'] = {
                'runStopFocus': round(defPlan.runStopFocus, 2),
                'blitzFrequency': round(defPlan.blitzFrequency, 2),
                'aggressiveness': round(defPlan.aggressiveness, 2),
                'coachDefMind': defCoach.defensiveMind if defCoach else None,
                'coachAdapt': defCoach.adaptability if defCoach else None,
                'coachAggr': defCoach.aggressiveness if defCoach else None,
            }
        coachInsights['isSecondHalf'] = self.currentQuarter >= 3
        coachInsights['offenseAbbr'] = self.offensiveTeam.abbr
        coachInsights['defenseAbbr'] = self.defensiveTeam.abbr

        self.play.insights['coach'] = coachInsights

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
        self.yardsToSafety = self.gameRules.fieldLength - self.yardsToEndzone
        self.down = 1
        self.yardsToFirstDown = self.gameRules.firstDownDistance


    def _resolveDefensiveReturn(self):
        """After an interception or fumble recovery, the defender runs it back.

        Adjusts self.play.yardage — a return moves the ball toward the giving
        team's own goal, which is the NEGATIVE direction here (it reduces
        yardsToSafety) — so the existing turnover branches naturally produce a
        normal return, a long flip in field position, or a pick-six /
        scoop-and-score when the return clears the field. SPEED drives the
        return distance; a speed-scaled breakaway can take it the distance.
        Sets play.returner / play.returnYardage for play-by-play + WPA. Called
        once per turnover, before the outcome branches read play.yardage."""
        from constants import (RETURN_ENABLED, RETURN_BASE_YARDS, RETURN_SPEED_PIVOT,
                               RETURN_YARDS_PER_SPEED, RETURN_BREAKAWAY_BASE,
                               RETURN_BREAKAWAY_PER_SPEED, RETURN_BREAKAWAY_MAX,
                               RETURN_BREAKAWAY_MEAN)
        play = self.play
        if not RETURN_ENABLED:
            return
        returner = play.interceptedBy if play.isInterception else (
            play.forcedFumbleBy or play.tackledBy)
        if returner is None:
            return
        spot = play.yardage  # recovery spot, net from the LOS in the offense's direction
        gameAttrs = getattr(returner, 'gameAttributes', None)
        spd = getattr(gameAttrs, 'speed', 75) if gameAttrs else 75
        mean = max(1.0, RETURN_BASE_YARDS + (spd - RETURN_SPEED_PIVOT) * RETURN_YARDS_PER_SPEED)
        returnYards = max(0, int(round(np.random.exponential(mean))))
        # fieldAhead = full distance from the recovery spot to the giving team's
        # goal line; a return of exactly this is a TD (the defensive-TD branch).
        fieldAhead = spot + self.yardsToSafety
        breakChance = min(RETURN_BREAKAWAY_MAX,
                          RETURN_BREAKAWAY_BASE + max(0, spd - RETURN_SPEED_PIVOT) * RETURN_BREAKAWAY_PER_SPEED)
        if fieldAhead > 0 and batched_randint(1, 100) <= breakChance:
            # Breakaway: a long return (exponential tail) added on top — only goes
            # the distance when the recovery was already deep, so TDs stay rare.
            returnYards += int(round(np.random.exponential(RETURN_BREAKAWAY_MEAN)))
        returnYards = max(0, min(returnYards, max(0, fieldAhead)))
        play.returner = returner
        play.returnYardage = returnYards
        play.yardage = spot - returnYards


    def _resolveBlockedKick(self):
        """A blocked FG or punt is a live ball the defense recovers at the line
        and may run back. The defense's distance to the kicking team's goal is
        yardsToSafety, so a punting team (backed up, small yardsToSafety) is far
        likelier to be taken back for a scoop-and-score than a FG team. Mirrors
        the defensive-TD path for the score case. Sets play.blockedBy / returner
        / returnYardage for PBP + WPA, then scores or flips possession and
        broadcasts; the caller breaks the play loop afterward."""
        from constants import (RETURN_BASE_YARDS, RETURN_SPEED_PIVOT, RETURN_YARDS_PER_SPEED,
                               RETURN_BREAKAWAY_BASE, RETURN_BREAKAWAY_PER_SPEED, RETURN_BREAKAWAY_MAX,
                               RETURN_BREAKAWAY_MEAN)
        play = self.play
        self.clockRunning = False
        self._applyMomentumEvent(MOMENTUM_TURNOVER, self.defensiveTeam)
        defenders = [p for p in self.defensiveTeam.rosterDict.values()
                     if p is not None and getattr(p, 'defensivePosition', None) is not None]
        play.blockedBy = max(defenders, key=lambda d: float(getattr(d, 'defensiveRating', 60) or 60),
                             default=None) if defenders else None
        returner = max(defenders, key=lambda d: getattr(getattr(d, 'gameAttributes', None), 'speed', 70),
                       default=None) if defenders else None
        play.returner = returner

        # Recovered at the line; run it back toward the kicking team's own goal.
        spd = getattr(getattr(returner, 'gameAttributes', None), 'speed', 72) if returner else 72
        mean = max(1.0, RETURN_BASE_YARDS + (spd - RETURN_SPEED_PIVOT) * RETURN_YARDS_PER_SPEED)
        returnYards = max(0, int(round(np.random.exponential(mean))))
        fieldAhead = self.yardsToSafety
        breakChance = min(RETURN_BREAKAWAY_MAX,
                          RETURN_BREAKAWAY_BASE + max(0, spd - RETURN_SPEED_PIVOT) * RETURN_BREAKAWAY_PER_SPEED)
        if fieldAhead > 0 and batched_randint(1, 100) <= breakChance:
            returnYards += int(round(np.random.exponential(RETURN_BREAKAWAY_MEAN)))
        returnYards = max(0, min(returnYards, max(0, fieldAhead)))
        play.returnYardage = returnYards

        self.formatPlayText()
        self.gameFeed.insert(0, {'play': play})
        self.highlights.insert(0, {'play': play})
        self.leagueHighlights.insert(0, {'play': play})

        if fieldAhead > 0 and returnYards >= fieldAhead:
            # Scoop-and-score (mirrors the defensive-TD branch; receiving team
            # starts at its own 20 → yardsToEndzone 80).
            self._addScore(self.defensiveTeam, 6)
            self._applyMomentumEvent(MOMENTUM_TD, self.defensiveTeam)
            play.playResult = PlayResult.Touchdown
            self.defensiveTeam.gameDefenseStats['fantasyPoints'] += 3
            play.isTd = True
            play.scoreChange = True
            play.homeTeamScore = self.homeScore
            play.awayTeamScore = self.awayScore
            if self.checkOvertimeEnd():
                self.broadcastGameState(includeLastPlay=True)
                return
            self.broadcastGameState(includeLastPlay=True)
            if self._shouldGoForTwo(self.defensiveTeam):
                self._simulate2PointConversionPlay(self.defensiveTeam, self.offensiveTeam)
            else:
                self._simulateExtraPointPlay(self.defensiveTeam, self.offensiveTeam, trackPtsAllowed=False)
            self.turnover(self.defensiveTeam, self.offensiveTeam, 80)
        else:
            self.broadcastGameState(includeLastPlay=True)
            self.turnover(self.offensiveTeam, self.defensiveTeam, self.yardsToSafety - returnYards)


    def formatPlayText(self):
        self._evaluateClutchChoke()

        # Snapshot clock state for the feed. By this point clockRunning has
        # been set either by an inline branch (FG, punt, score, turnover) or
        # by the post-play shouldClockRun() call.
        self.play.clockStopped = not self.clockRunning

        # ── Player insights: capture involved players' state after play execution ──
        play = self.play
        involvedPlayers = []
        if play.playType == PlayType.Run and play.runner:
            involvedPlayers.append(play.runner)
            # TE blocker on run plays
            teBl = self.offensiveTeam.rosterDict.get('te')
            if teBl and teBl not in involvedPlayers:
                involvedPlayers.append(teBl)
        elif play.playType == PlayType.Pass:
            if play.passer:
                involvedPlayers.append(play.passer)
            if play.receiver:
                involvedPlayers.append(play.receiver)
        elif play.playType == PlayType.FieldGoal and hasattr(play, 'kicker') and play.kicker:
            involvedPlayers.append(play.kicker)

        prePlayComposure = play.insights.pop('_prePlayComposure', {})
        if involvedPlayers:
            play.insights['players'] = []
            for p in involvedPlayers:
                pre = prePlayComposure.get(id(p), {})
                preCon = pre.get('confidence', 0)
                preDet = pre.get('determination', 0)
                postCon = round(p.gameAttributes.confidenceModifier, 3)
                postDet = round(p.gameAttributes.determinationModifier, 3)
                # Drift = how far this player has moved from their pre-game baseline
                baseConf = p.attributes.confidenceModifier
                baseDet = p.attributes.determinationModifier
                confDrift = round(postCon - baseConf, 3)
                detDrift = round(postDet - baseDet, 3)
                # Use the actual pressure modifier applied during the play, not a fresh roll
                if play.playType == PlayType.Run and hasattr(play, 'runner') and play.runner is p:
                    actualMod = round(play.keyPressureMod, 2)
                elif play.playType == PlayType.Pass and hasattr(play, 'passer') and play.passer is p:
                    actualMod = round(play.qbPressureMod, 2)
                elif play.playType == PlayType.Pass and hasattr(play, 'receiver') and play.receiver is p:
                    actualMod = round(play.rcvPressureMod, 2)
                elif play.playType == PlayType.FieldGoal and hasattr(play, 'kicker') and play.kicker is p:
                    actualMod = round(play.keyPressureMod, 2)
                else:
                    actualMod = None  # non-key player, no stored modifier

                playerEntry = {
                    'name': p.name,
                    'position': p.position.name if hasattr(p, 'position') else None,
                    'confidence': round(postCon, 2),
                    'determination': round(postDet, 2),
                    'confidenceChange': round(postCon - preCon, 3),
                    'determinationChange': round(postDet - preDet, 3),
                    'confidenceDrift': confDrift,
                    'determinationDrift': detDrift,
                    'pressureMod': actualMod,
                }

                # Pressure profile: show how this player's mental makeup interacts
                # with the current game pressure (probability zones + what rolled)
                normPressure = min(100, max(0, self.gamePressure)) / 100.0
                if normPressure >= 0.3:
                    ph = getattr(p.attributes, 'pressureHandling', 0)
                    cf = getattr(p.attributes, 'clutchFactor', 0)
                    if ph >= 0:
                        overChance = 15 + (ph * 4.5)
                        noEffChance = 70 - (ph * 4)
                    else:
                        overChance = 15 + (ph * 0.5)
                        noEffChance = 70 + (ph * 4)
                    # High-pressure compression of no-effect zone
                    if normPressure >= 0.7:
                        compFactor = (normPressure - 0.7) / 0.3
                        noEffReduction = noEffChance * 0.5 * compFactor
                        noEffChance -= noEffReduction
                        overChance += noEffReduction * 0.5
                    underChance = 100 - overChance - noEffChance
                    # What actually happened to this player under pressure
                    if actualMod is not None and actualMod > 0:
                        pressureOutcome = 'rose'
                    elif actualMod is not None and actualMod < 0:
                        pressureOutcome = 'crumbled'
                    else:
                        pressureOutcome = 'steady'
                    playerEntry['pressureProfile'] = {
                        'pressureHandling': ph,
                        'clutchFactor': cf,
                        'riseChance': round(overChance),
                        'steadyChance': round(noEffChance),
                        'crumbleChance': round(underChance),
                        'outcome': pressureOutcome,
                    }

                play.insights['players'].append(playerEntry)

        text = None
        if getattr(self.play, 'isScramble', False):
            # QB ran instead of passing (resolves as a run, narrated as a scramble).
            # Phrasing matches the trigger: 'pressure' = escaped a would-be sack,
            # 'coverage' = no one open, pulled it down and ran.
            yds = self.play.yardage
            reason = getattr(self.play, 'scrambleReason', 'pressure')
            if reason == 'coverage':
                runPhrases = ['finds no one open and takes off for', 'pulls it down and runs for',
                              'can\'t find a target, tucks it and runs for', 'scans, nobody open, scrambles for',
                              'holds it, then takes off for']
                noGain = '{} pulls it down and runs but is stopped for no gain'.format(self.play.runner.name)
            else:
                runPhrases = ['escapes the pocket and scrambles for', 'slips the rush and takes off for',
                              'spins free of pressure and scrambles for', 'dodges the sack and runs for',
                              'sidesteps the rush and scrambles for']
                noGain = '{} escapes the rush but is dragged down for no gain'.format(self.play.runner.name)
            if yds <= 0:
                text = noGain
            else:
                text = '{} {} {} yards'.format(self.play.runner.name, choice(runPhrases), yds)
            if self.play.isFumble:
                forcedBy = self.play.forcedFumbleBy
                if self.play.isFumbleLost:
                    text += (', {} forces the fumble, {} recover'.format(forcedBy.name, self.play.defense.abbr)
                             if forcedBy else ', fumbles, {} recover'.format(self.play.defense.abbr))
                else:
                    text += ', fumbles but recovers it'
            elif self.play.tackledBy and not self.play.isTd:
                text += ', tackled by {}'.format(self.play.tackledBy.name)
        elif self.play.playType is PlayType.Run:
            # Select description list based on gap type
            runGap = self.play.insights.get('run', {}).get('selectedGap', 'B-gap')
            isOutside = runGap in ('C-gap', 'bounce')
            if self.play.isFumble:
                yds = self.play.yardage
                gainText = 'no gain' if yds == 0 else 'a loss of {} yards'.format(abs(yds)) if yds < 0 else '{} yards'.format(yds)
                if self.play.isFumbleLost:
                    forcedBy = self.play.forcedFumbleBy
                    if forcedBy:
                        text = '{} runs for {}, {} forces the fumble, {} recover'.format(self.play.runner.name, gainText, forcedBy.name, self.play.defense.abbr)
                    else:
                        text = '{} runs for {} and fumbles, {} recover'.format(self.play.runner.name, gainText, self.play.defense.abbr)
                else:
                    text = '{} runs for {} and fumbles, {} recovers'.format(self.play.runner.name, gainText, self.play.runner.name)
            else:
                if self.play.yardage <= 0:
                    tackler = self.play.tackledBy
                    if tackler:
                        text = choice(lossRunDefenderList).format(self.play.runner.name, tackler.name, self.play.yardage)
                    else:
                        text = '{} {} for {} yards'.format(self.play.runner.name, choice(lossRunList), self.play.yardage)
                elif self.play.yardage > 0 and self.play.yardage <= 3:
                    runList = shortRunOutsideList if isOutside else shortRunInsideList
                    text = '{} {} {} yards'.format(self.play.runner.name, choice(runList), self.play.yardage)
                    if self.play.tackledBy and not self.play.isTd:
                        text += ', tackled by {}'.format(self.play.tackledBy.name)
                elif self.play.yardage > 3 and self.play.yardage <= 9:
                    runList = midRunOutsideList if isOutside else midRunInsideList
                    text = '{} {} {} yards'.format(self.play.runner.name, choice(runList), self.play.yardage)
                    if self.play.tackledBy and not self.play.isTd:
                        text += ', tackled by {}'.format(self.play.tackledBy.name)
                elif self.play.yardage >= 10:
                    runList = longRunOutsideList if isOutside else longRunInsideList
                    text = '{} {} {} yards'.format(self.play.runner.name, choice(runList), self.play.yardage)
                    if self.play.tackledBy and not self.play.isTd:
                        text += ', tackled by {}'.format(self.play.tackledBy.name)
        elif self.play.playType is PlayType.Pass:
            if self.play.isSack:
                sacker = self.play.sackedBy
                sackerName = sacker.name if sacker else self.play.defense.abbr
                if self.play.isFumble:
                    forcedBy = self.play.forcedFumbleBy
                    if self.play.isFumbleLost:
                        if forcedBy:
                            text = '{} sacked by {}, fumbles, {} recovers'.format(self.play.passer.name, sackerName, self.play.defense.name)
                        else:
                            text = '{} sacked and fumbles, {} recovers'.format(self.play.passer.name, self.play.defense.name)
                    else:
                        text = '{} sacked by {} and fumbles, {} recovers'.format(self.play.passer.name, sackerName, self.play.passer.name)
                else:
                    text = choice(sackList).format(self.play.passer.name, sackerName, self.play.yardage)
            elif self.play.isPassCompletion:
                if getattr(self.play, 'isCheckdown', False):
                    reason = getattr(self.play, 'checkdownReason', '')
                    if reason == 'screen':
                        verb = 'throws a screen to'
                    elif reason == 'pressure':
                        verb = 'dumps it off to'
                    else:
                        verb = 'checks down to'
                    text = '{} {} {} for {} yards'.format(
                        self.play.passer.name, verb, self.play.receiver.name, self.play.yardage)
                elif self.play.targetSideline:
                    if self.play.passType is PassType.short:
                        text = '{} {} {} for {} yards'.format(self.play.passer.name, choice(sidelineShortPassList), self.play.receiver.name, self.play.yardage)
                    elif self.play.passType is PassType.long:
                        text = '{} {} {} for {} yards'.format(self.play.passer.name, choice(sidelineLongPassList), self.play.receiver.name, self.play.yardage)
                    else:
                        text = '{} {} {} for {} yards'.format(self.play.passer.name, choice(sidelineMidPassList), self.play.receiver.name, self.play.yardage)
                    # Don't append OOB on a TD — once the receiver crosses the
                    # goal line the play is dead by score, not by stepping out.
                    # The OOB flag stays True for clock-management purposes,
                    # but it shouldn't show up in the narration.
                    if not self.play.isInBounds and not self.play.isTd:
                        text += ', out of bounds'
                elif self.play.passType is PassType.short:
                    text = '{} {} {} for {} yards'.format(self.play.passer.name, choice(shortPassList), self.play.receiver.name, self.play.yardage)
                elif self.play.passType is PassType.long:
                    text = '{} {} {} for {} yards'.format(self.play.passer.name, choice(longPassList), self.play.receiver.name, self.play.yardage)
                elif self.play.passType is PassType.hailMary:
                    # End-zone phrasing only when it actually scores; a hail mary
                    # caught short and tackled mustn't claim it reached the end zone.
                    hmPool = extraLongPassList if self.play.isTd else extraLongNonScoringPassList
                    text = '{} {} {} for {} yards'.format(self.play.passer.name, choice(hmPool), self.play.receiver.name, self.play.yardage)
                else:
                    text = '{} {} {} for {} yards'.format(self.play.passer.name, choice(midPassList), self.play.receiver.name, self.play.yardage)
                # Fumble after catch
                if self.play.isFumble:
                    forcedBy = self.play.forcedFumbleBy
                    if self.play.isFumbleLost:
                        if forcedBy:
                            text += ', {} forces the fumble, {} recover'.format(forcedBy.name, self.play.defense.abbr)
                        else:
                            text += ', fumbles, {} recover'.format(self.play.defense.abbr)
                    else:
                        text += ', fumbles, {} recovers'.format(self.play.receiver.name)
                elif self.play.tackledBy and not self.play.isTd and self.play.isInBounds:
                    text += ', tackled by {}'.format(self.play.tackledBy.name)
            elif self.play.playResult is PlayResult.Interception:
                interceptor = self.play.interceptedBy
                interceptorName = interceptor.name if interceptor else self.play.defense.abbr
                # Pick the flavor from how the throw came about: forced into
                # coverage, a sailed errant ball, or a good throw a DB jumped.
                passI = self.play.insights.get('pass', {}) if isinstance(self.play.insights, dict) else {}
                tq = passI.get('throwQuality')
                actOpen = passI.get('rcvActualOpenness', passI.get('rcvOpenness'))
                badThrow = tq is not None and tq < 50
                covered = actOpen is not None and actOpen < 45
                if covered and badThrow:
                    intList = intoCoverageList      # forced it into traffic
                elif covered:
                    intList = defPlayPickList        # good throw, DB made the play
                elif badThrow:
                    intList = errantPickList         # sailed it to the defender
                else:
                    intList = interceptionList       # generic
                text = choice(intList).format(self.play.passer.name, interceptorName)
            else:
                # Classify the incompletion: did the QB miss an open man, force
                # it into coverage, or did the defense break up an on-target ball?
                passI = self.play.insights.get('pass', {}) if isinstance(self.play.insights, dict) else {}
                tq = passI.get('throwQuality')
                actOpen = passI.get('rcvActualOpenness', passI.get('rcvOpenness'))
                badThrow = tq is not None and tq < 50
                covered = actOpen is not None and actOpen < 45
                wideOpen = actOpen is not None and actOpen >= 60

                if self.play.passType is PassType.throwAway:
                    protDiff = passI.get('protectionDiff', 0)
                    taList = throwAwayPressureList if protDiff < -5 else throwAwayCoverageList
                    text = choice(taList).format(self.play.passer.name)
                elif self.play.passIsDropped:
                    # Drops keep their tier-specific flavor.
                    if self.play.passType is PassType.short:
                        text = choice(shortDropList).format(self.play.passer.name, self.play.receiver.name)
                    elif self.play.passType is PassType.long or self.play.passType is PassType.hailMary:
                        text = choice(deepDropList).format(self.play.passer.name, self.play.receiver.name)
                    else:
                        text = choice(midDropList).format(self.play.passer.name, self.play.receiver.name)
                elif badThrow and wideOpen:
                    text = choice(overthrowOpenList).format(self.play.passer.name, self.play.receiver.name)
                elif badThrow and covered:
                    text = choice(forcedCoverageList).format(self.play.passer.name, self.play.receiver.name)
                elif covered:
                    text = choice(coverageBreakupList).format(self.play.passer.name, self.play.receiver.name)
                else:
                    # Generic tier incomplete — good throw, open-ish, just didn't connect.
                    if self.play.passType is PassType.short:
                        text = choice(shortIncompleteList).format(self.play.passer.name, self.play.receiver.name)
                    elif self.play.passType is PassType.long or self.play.passType is PassType.hailMary:
                        text = choice(deepIncompleteList).format(self.play.passer.name, self.play.receiver.name)
                    else:
                        text = choice(midIncompleteList).format(self.play.passer.name, self.play.receiver.name)
        elif self.play.playType == PlayType.FieldGoal:
            kickerName = self.play.kicker.name
            if getattr(self.play, 'isFgBlocked', False):
                blockerName = getattr(getattr(self.play, 'blockedBy', None), 'name', None)
                text = (f'{self.play.fgDistance}yd Field Goal by {kickerName} is BLOCKED by {blockerName}!'
                        if blockerName else f'{self.play.fgDistance}yd Field Goal by {kickerName} is BLOCKED!')
            elif self.play.isFgGood:
                text = f'{self.play.fgDistance}yd Field Goal by {kickerName} is good'
            else:
                text = f'{self.play.fgDistance}yd Field Goal by {kickerName} is no good'
        elif self.play.playType == PlayType.ExtraPoint:
            kickerName = self.play.kicker.name if getattr(self.play, 'kicker', None) else 'Kicker'
            if self.play.isXpGood:
                text = f'{kickerName} converts the extra point'
            else:
                text = f'{kickerName} misses the extra point'
        elif self.play.playType is PlayType.Punt:
            punter = self.play.offense.rosterDict.get('k')
            punterName = punter.name if punter else 'Punter'
            if getattr(self.play, 'isPuntBlocked', False):
                blockerName = getattr(getattr(self.play, 'blockedBy', None), 'name', None)
                text = ("{}'s punt is BLOCKED by {}!".format(punterName, blockerName)
                        if blockerName else "{}'s punt is BLOCKED!".format(punterName))
            else:
                text = '{} punts'.format(punterName)
        elif self.play.playType is PlayType.Spike:
            qb = self.play.offense.rosterDict.get('qb')
            qbName = qb.name if qb else 'QB'
            text = f'{qbName} spikes the ball'
        elif self.play.playType is PlayType.Kneel:
            qb = self.play.offense.rosterDict.get('qb')
            qbName = qb.name if qb else 'QB'
            text = f'{qbName} takes a knee'

        # Blitz callout — only when the blitz actually put pressure on the QB
        # (sack, or defense winning the rush matchup). Pass plays only; runs
        # don't have a QB facing pressure even if a blitz was called.
        if text and self.play.blitzKind and self.play.playType == PlayType.Pass:
            pressureFelt = (
                self.play.isSack
                or getattr(self.play, 'rushDifferential', 0) > 0
            )
            if pressureFelt:
                if self.play.blitzKind == 'allOut':
                    blitzPrefix = 'All-out blitz! '
                elif self.play.blitzedBy is not None:
                    blitzPrefix = '{} is blitzing! '.format(self.play.blitzedBy.name)
                else:
                    blitzPrefix = 'Blitz! '
                text = blitzPrefix + text

        # Defensive return tail: append run-back yardage, or call the pick-six /
        # scoop-and-score. The house-call test mirrors the turnover branch (the ball
        # reaching the giving team's own goal line). Called before the TD branch sets
        # play.isTd, so detect the score by field geometry here.
        returnYds = getattr(self.play, 'returnYardage', 0)
        isBlockReturn = getattr(self.play, 'isFgBlocked', False) or getattr(self.play, 'isPuntBlocked', False)
        if text and returnYds and (self.play.isInterception or self.play.isFumbleLost or isBlockReturn):
            # House-call test mirrors the resolving branch: for a turnover the ball
            # reaches the giving team's goal (yardsToSafety + adjusted yardage ≤ 0);
            # for a blocked kick the return covers yardsToSafety from the line.
            if isBlockReturn:
                houseCall = returnYds >= self.yardsToSafety
            else:
                houseCall = (self.yardsToSafety + self.play.yardage) <= 0
            # Blocked-kick text already ends in '!', so start a new sentence rather
            # than tack on a comma clause (avoids 'BLOCKED!, returned ...').
            endsBang = text.rstrip().endswith('!')
            if houseCall:
                tdText = 'Pick six!' if self.play.isInterception else 'Taken to the house!'
                text += (' ' + tdText) if endsBang else ('. ' + tdText)
            else:
                ydText = 'returned {} yard{}'.format(returnYds, '' if returnYds == 1 else 's')
                text += (' Defense ' + ydText + '.') if endsBang else (', ' + ydText)

        self.play.playText = text

    def _evaluateClutchChoke(self):
        """Evaluate whether the current play qualifies as a clutch or choke moment.

        Reserved for truly pivotal late-game plays where the key player's
        pressure response actually drove the outcome:
        - Clutch: pivotal good outcome (go-ahead score, 4th-down conversion,
          big gainer in close game) AND the key player rose to the occasion
          (positive pressure modifier).
        - Choke: pivotal bad outcome (turnover in close game, missed FG to
          tie/win, critical drop) AND the key player crumbled (negative
          pressure modifier).

        A 0 pressure modifier — i.e. the pressure roll said the player was
        unaffected — means the result wasn't driven by their mental state, so
        even a great play in a tight spot won't tag as clutch. Same for chokes:
        a turnover by a player whose pressure roll was neutral was just bad
        luck, not a mental break.

        Must be Q4 or OT, game within reach, and pass the WPA gate (applied
        later in broadcastGameState).
        """
        play = self.play
        if play.gamePressure < CLUTCH_PRESSURE_THRESHOLD:
            return

        # Must be Q4 or overtime — early-game plays are not clutch/choke
        if self.currentQuarter < 4:
            return

        # Game must be within reach
        isHome = (self.offensiveTeam == self.homeTeam)
        offScore = self.homeScore if isHome else self.awayScore
        defScore = self.awayScore if isHome else self.homeScore
        scoreDiff = offScore - defScore  # positive = offense leading (post-play)

        # For scoring plays, the score has already been updated — compute pre-play diff
        scoredPoints = 0
        if play.isFgGood:
            scoredPoints = 3
        elif play.isTd:
            scoredPoints = 6  # TD itself (PAT hasn't happened yet)
        prePlayScoreDiff = scoreDiff - scoredPoints

        # Let the WPA gate filter blowouts — no hard cutoff here
        # (a play in a 21-point game will have minimal WPA and get filtered)

        # For pass plays, determine key player based on outcome
        if play.playType == PlayType.Pass:
            if play.isPassCompletion or play.isTd:
                if play.rcvPressureMod > play.qbPressureMod:
                    play.keyPressureMod = play.rcvPressureMod
                    play.clutchPlayerName = play.receiver.name if play.receiver else ''
                else:
                    play.keyPressureMod = play.qbPressureMod
                    play.clutchPlayerName = play.passer.name if play.passer else ''
            elif play.passIsDropped:
                play.keyPressureMod = play.rcvPressureMod
                play.clutchPlayerName = play.receiver.name if play.receiver else ''
            else:
                play.keyPressureMod = play.qbPressureMod
                play.clutchPlayerName = play.passer.name if play.passer else ''

        # ── Step 1: Outcome categorization — what kind of play was this? ──
        # The clock-time / situation filter is handled by gamePressure (which
        # only clears CLUTCH_PRESSURE_THRESHOLD in genuinely decisive moments).
        # Here we just classify the OUTCOME — did something pivotal happen?
        downNum = getattr(play, 'down', 0) or 0

        # Clutch outcomes
        isClutchOutcome = (
            # Go-ahead / tying score
            ((play.isTd or play.isFgGood) and prePlayScoreDiff <= 0)
            # 4th-down conversion when trailing/tied (drive saved)
            or (downNum == 4 and play.playResult == PlayResult.FirstDown
                and scoreDiff <= 0)
            # Big play in close game
            or (abs(scoreDiff) <= 7
                and ((play.isPassCompletion and play.yardage >= 25)
                     or (play.playType == PlayType.Run and play.yardage >= 20)))
        )

        # Choke outcomes
        isChokeOutcome = (
            # Turnover in close game
            ((play.isInterception or play.isFumbleLost
              or play.playResult == PlayResult.TurnoverOnDowns)
             and abs(scoreDiff) <= 7)
            # Missed FG to tie / take lead
            or (play.playType == PlayType.FieldGoal and not play.isFgGood
                and prePlayScoreDiff <= 0)
            # Critical drop on 3rd/4th in close game
            or (play.passIsDropped and downNum >= 3 and abs(scoreDiff) <= 7)
            # Sack on 3rd/4th down in close game — drive-killing pressure
            or (play.isSack and downNum >= 3 and abs(scoreDiff) <= 7)
        )

        if not (isClutchOutcome or isChokeOutcome):
            return

        # ── Step 2: Did any involved player actually clutch/choke? ──
        # Build the list of (name, modifier) for every player whose pressure
        # roll could have driven the outcome. Tracked separately for offense
        # and defense — defenders who made plays during a chokeOutcome (offense
        # turned the ball over / failed to convert) can be CLUTCH; offense
        # players who failed during a clutchOutcome already get tagged as
        # risers below.
        offInvolved = []
        if play.playType == PlayType.Run and getattr(play, 'runner', None):
            offInvolved.append((play.runner.name, getattr(play, 'keyPressureMod', 0) or 0))
        elif play.playType == PlayType.Pass:
            if getattr(play, 'passer', None):
                offInvolved.append((play.passer.name, getattr(play, 'qbPressureMod', 0) or 0))
            if getattr(play, 'receiver', None):
                offInvolved.append((play.receiver.name, getattr(play, 'rcvPressureMod', 0) or 0))
        elif play.playType == PlayType.FieldGoal and getattr(play, 'kicker', None):
            offInvolved.append((play.kicker.name, getattr(play, 'keyPressureMod', 0) or 0))

        # Defensive playmakers — only credit defenders who actually drove the
        # outcome. Pressure mod is rolled here at evaluation time using the
        # same formula as offense; it doesn't affect game outcome, just
        # determines whether they "rose" or "crumbled" in the moment.
        defenders = []
        if getattr(play, 'interceptedBy', None):
            defenders.append(play.interceptedBy)
        if getattr(play, 'sackedBy', None) and play.sackedBy not in defenders:
            defenders.append(play.sackedBy)
        if getattr(play, 'forcedFumbleBy', None) and play.forcedFumbleBy not in defenders:
            defenders.append(play.forcedFumbleBy)
        # Tackler credit only when the stop was meaningful (TFL or 4th-down stop)
        tackler = getattr(play, 'tackledBy', None)
        if tackler and tackler not in defenders:
            isStop = (play.yardage < 0
                      or play.playResult == PlayResult.TurnoverOnDowns)
            if isStop:
                defenders.append(tackler)

        # Coverage bust — defender left a receiver WIDE OPEN on a pivotal TD
        # pass. Rare but real: the kind of "where was the safety?" moment that
        # decides games. Only fires for a clutch-outcome TD pass and only when
        # the receiver's openness was very high (≥80 / 100).
        if (isClutchOutcome and play.playType == PlayType.Pass
                and getattr(play, 'isTd', False)):
            selectedTarget = getattr(play, 'selectedTarget', None)
            if selectedTarget:
                openness = selectedTarget.get('openness', 0) or 0
                coveringDefender = selectedTarget.get('coveringDefender')
                if (openness >= 80 and coveringDefender
                        and coveringDefender not in defenders):
                    defenders.append(coveringDefender)

        defInvolved = []
        for defender in defenders:
            try:
                defMod = defender.attributes.getPressureModifier(self.gamePressure)
            except Exception:
                defMod = 0
            defInvolved.append((defender.name, defMod))

        offRisers = [name for (name, mod) in offInvolved if mod > 0]
        offFallers = [name for (name, mod) in offInvolved if mod < 0]
        defRisers = [name for (name, mod) in defInvolved if mod > 0]
        defFallers = [name for (name, mod) in defInvolved if mod < 0]

        # FGs are always-pressure plays — kicker is credited even on a
        # neutral pressure roll, since the kick under pressure is the moment.
        if play.playType == PlayType.FieldGoal and not (offRisers or offFallers):
            if getattr(play, 'kicker', None):
                if isClutchOutcome:
                    offRisers = [play.kicker.name]
                elif isChokeOutcome:
                    offFallers = [play.kicker.name]

        clutchPerformers = []
        chokePerformers = []
        if isClutchOutcome:
            # Offense achieved — offensive risers are clutch, defenders who
            # crumbled in coverage / on the stop attempt are choke.
            clutchPerformers.extend(offRisers)
            chokePerformers.extend(defFallers)
        if isChokeOutcome:
            # Offense failed — offensive fallers are choke, defenders who
            # rose to make the play (INT / sack / forced fumble / 4th stop)
            # are clutch.
            chokePerformers.extend(offFallers)
            clutchPerformers.extend(defRisers)

        if clutchPerformers:
            play.isClutchPlay = True
            play.clutchPerformers = clutchPerformers
            # Top performer name for legacy single-name consumers
            allInvolved = offInvolved + defInvolved
            risingPool = [(n, m) for (n, m) in allInvolved if n in clutchPerformers]
            if risingPool:
                topRiser = max(risingPool, key=lambda x: x[1])
                play.clutchPlayerName = topRiser[0]
        if chokePerformers:
            play.isChokePlay = True
            play.chokePerformers = chokePerformers
            allInvolved = offInvolved + defInvolved
            fallingPool = [(n, m) for (n, m) in allInvolved if n in chokePerformers]
            if fallingPool:
                topFaller = min(fallingPool, key=lambda x: x[1])
                # Don't overwrite clutchPlayerName if already set (clutch wins display priority)
                if not play.clutchPlayerName:
                    play.clutchPlayerName = topFaller[0]

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

        # Per-player: update confidence/determination, increment gamesPlayed
        # (regular season only), compute derived stats
        for player in self.homeTeam.rosterDict.values():
            if player:
                player.postgameChanges(isRegularSeason=self.isRegularSeasonGame)
                self._accumulatePostgameStats(player)
        for player in self.awayTeam.rosterDict.values():
            if player:
                player.postgameChanges(isRegularSeason=self.isRegularSeasonGame)
                self._accumulatePostgameStats(player)

    def postgame(self):
        if self.isRegularSeasonGame:
            self._accumulateOffenseStats(self.homeTeam, self.homeScore)
            self._accumulateOffenseStats(self.awayTeam, self.awayScore)

            self.winningTeam.seasonTeamStats['priorStreak'] = self.winningTeam.seasonTeamStats['streak']
            if self.winningTeam.seasonTeamStats['streak'] >= 0:
                self.winningTeam.seasonTeamStats['streak'] += 1
                if self.winningTeam.seasonTeamStats['streak'] > 3 and not self.winningTeam.winningStreak:
                    self.winningTeam.winningStreak = True
                    self.leagueHighlights.insert(0, {'event': {'text': '{} {} are on a hot streak!'.format(self.winningTeam.city, self.winningTeam.name)}})
            else:
                self.winningTeam.seasonTeamStats['streak'] = 1
            winAbsStreak = abs(self.winningTeam.seasonTeamStats['streak'])
            self.winningTeam.seasonTeamStats['peakStreak'] = max(
                self.winningTeam.seasonTeamStats.get('peakStreak', 0), winAbsStreak
            )
            self._accumulateDefenseStats(self.winningTeam)

            self.losingTeam.seasonTeamStats['priorStreak'] = self.losingTeam.seasonTeamStats['streak']
            if self.losingTeam.seasonTeamStats['streak'] >= 0:
                self.losingTeam.seasonTeamStats['streak'] = -1
                if self.losingTeam.winningStreak:
                    self.losingTeam.winningStreak = False
                    self.leagueHighlights.insert(0, {'event': {'text': '{} {} ended the {} {} hot streak!'.format(self.winningTeam.city, self.winningTeam.name, self.losingTeam.city, self.losingTeam.name)}})
            else:
                self.losingTeam.seasonTeamStats['streak'] -= 1
            loseAbsStreak = abs(self.losingTeam.seasonTeamStats['streak'])
            self.losingTeam.seasonTeamStats['peakStreak'] = max(
                self.losingTeam.seasonTeamStats.get('peakStreak', 0), loseAbsStreak
            )
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

        # WPA: preserve this game's per-player value for the DB row, roll it into
        # the season total (regular season only — playoff WPA is a separate track),
        # then reset the per-game accumulators. Mirrors the fantasy-points flow.
        player._lastGameWpa = float(getattr(player, '_gameWpa', 0.0))
        player._lastGameDefWpa = float(getattr(player, '_gameDefWpa', 0.0))
        player._lastGameWpaSnaps = int(getattr(player, '_gameWpaSnaps', 0))
        player._lastGameDefWpaSnaps = int(getattr(player, '_gameDefWpaSnaps', 0))
        if self.isRegularSeasonGame:
            player.seasonWpa = float(getattr(player, 'seasonWpa', 0.0)) + player._lastGameWpa
            player.seasonDefWpa = float(getattr(player, 'seasonDefWpa', 0.0)) + player._lastGameDefWpa
            player.seasonWpaSnaps = int(getattr(player, 'seasonWpaSnaps', 0)) + player._lastGameWpaSnaps
            player.seasonDefWpaSnaps = int(getattr(player, 'seasonDefWpaSnaps', 0)) + player._lastGameDefWpaSnaps
        player._gameWpa = 0.0
        player._gameDefWpa = 0.0
        player._gameWpaSnaps = 0
        player._gameDefWpaSnaps = 0

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
        # Reset scores so replayed games don't start with stale values
        self.homeScore = 0
        self.awayScore = 0
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
        self.totalPlays = 0
        possReset = 80
        coinFlipWinner = None
        coinFlipLoser = None

        # Initialize clock for Q1
        self.currentQuarter = 1
        self.gameClockSeconds = self.gameRules.quarterLengthSeconds
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

        # Reset team-level defensive accumulators for this game. Players'
        # gameStatsDict is reset above, but gameDefenseStats (interceptions,
        # sacks, fumble recoveries, ...) was only ever reset in the dead
        # postgame() path — so it carried over across every game the team object
        # lived through, inflating the box score and the DB-stored per-game team
        # INTs that feed the pre-game matchup averages.
        self.homeTeam.gameDefenseStats = copy.deepcopy(FloosTeam.teamStatsDict['Defense'])
        self.awayTeam.gameDefenseStats = copy.deepcopy(FloosTeam.teamStatsDict['Defense'])

        # League compression — pull every player's leaf attributes
        # toward the league mean so the 95-vs-65 gap doesn't auto-win
        # plays. Runs RIGHT AFTER the deepcopy so all downstream
        # modifiers (funding morale, fatigue, disposition, soft cap)
        # stack on the compressed baseline. Profile ratings stay
        # untouched; only gameAttributes is compressed.
        self._applyLeagueCompression(self.homeTeam)
        self._applyLeagueCompression(self.awayTeam)

        # Apply funding morale modifiers (small pregame confidence/determination nudge)
        self._applyFundingMorale(self.homeTeam)
        self._applyFundingMorale(self.awayTeam)

        # Diagnostic snapshot at game start — captures the effective scaled
        # pressure modifier each team carries into this game. Regular-season
        # base sits at 1.0 across the board, so this confirms whether market-
        # tier scaling fires for non-playoff games (it shouldn't when delta=0).
        try:
            from managers.teamManager import logPressureDiag
            seasonNum = getattr(self, 'seasonNumber', None)
            weekNum = getattr(self, 'gameWeek', None) or getattr(self, 'weekNumber', None)
            ctx = "game_start"
            if not getattr(self, 'isRegularSeasonGame', True):
                ctx = f"playoff_game_r{getattr(self, 'playoffRound', '?')}"
            logPressureDiag(self.homeTeam, ctx, season=seasonNum, week=weekNum)
            logPressureDiag(self.awayTeam, ctx, season=seasonNum, week=weekNum)
        except Exception:
            pass  # Diagnostic logging must never break the game loop

        # Snapshot pre-game ELO + pressure modifier for the correlation log
        # written at game end. Stored on the game instance so we can compute
        # ELO delta and have a record of conditions entering the game.
        try:
            self._preGameHomeElo = getattr(self.homeTeam, 'elo', 1500)
            self._preGameAwayElo = getattr(self.awayTeam, 'elo', 1500)
            self._preGameHomePressureMod = getattr(self.homeTeam, 'pressureModifier', 1.0)
            self._preGameAwayPressureMod = getattr(self.awayTeam, 'pressureModifier', 1.0)
            self._preGameHomeTier = getattr(self.homeTeam, 'fundingTier', 'UNKNOWN')
            self._preGameAwayTier = getattr(self.awayTeam, 'fundingTier', 'UNKNOWN')
            self._preGameHomeStreak = getattr(self.homeTeam, 'currentWinStreak', 0)
            self._preGameAwayStreak = getattr(self.awayTeam, 'currentWinStreak', 0)
            self._preGameHomeStreakP = getattr(self.homeTeam, 'streakPressure', 0.0)
            self._preGameAwayStreakP = getattr(self.awayTeam, 'streakPressure', 0.0)
        except Exception:
            pass

        # Snapshot each player's baseline overallRating BEFORE any pre-game
        # modifiers fire so we can enforce a soft floor below. Without this,
        # fatigue + form state + context multipliers compound into ~25%
        # reductions on unlucky stacks and a 90-rated player can effectively
        # play at 67, with no visible explanation to the user. The floor
        # gives the worst-felt outcomes a hard limit.
        self._snapshotBaselineRatings(self.homeTeam)
        self._snapshotBaselineRatings(self.awayTeam)

        # Apply fatigue penalties (accumulated over the season)
        self._applyFatigue(self.homeTeam)
        self._applyFatigue(self.awayTeam)
        self._snapshotMentalPhase(self.homeTeam, 'afterFatigue')
        self._snapshotMentalPhase(self.awayTeam, 'afterFatigue')

        # Single combined team-disposition modifier. Replaces the prior
        # split between form state and matchup context, which both fired
        # on overlapping inputs (discipline, attitude, ELO) and stacked
        # to double-count the same underlying signal. Capped at ±10% so
        # the aggregate stays in "this is football, not a debuff system"
        # territory. Produces one narrative label per team
        # ("Hot Streak" / "Trap-Game Risk" / "Cinderella Push" / etc.).
        self._applyTeamDisposition()
        self._snapshotMentalPhase(self.homeTeam, 'afterDisposition')
        self._snapshotMentalPhase(self.awayTeam, 'afterDisposition')

        # Enforce the soft floor — scale a player's attributes back up if
        # the compounded modifiers dropped their overall rating more than
        # MENTAL_FLOOR_RATIO permits. Preserves attribute *proportions*
        # so a power-back stays power-heavy, etc.
        self._enforceMentalSoftCap(self.homeTeam)
        self._enforceMentalSoftCap(self.awayTeam)
        self._snapshotMentalPhase(self.homeTeam, 'afterCap')
        self._snapshotMentalPhase(self.awayTeam, 'afterCap')

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
        
        # Main game loop - run until game is over. The MAX_OT_PERIODS
        # cap is a backstop against indefinite stalemate (each OT period
        # is 10 game-minutes — going past 5 means we've already simulated
        # nearly an extra full game's worth of OT). Without the cap a
        # genuinely-deadlocked sim could spin forever.
        MAX_OT_PERIODS = 5
        while not self.isGameOver():
            if (self.currentQuarter >= 5
                    and getattr(self, 'otPeriod', 0) > MAX_OT_PERIODS
                    and self.homeScore == self.awayScore):
                logger.warning(
                    f"[GAME] OT cap reached ({MAX_OT_PERIODS} periods) — accepting tie. "
                    f"{self.awayTeam.name} {self.awayScore} - {self.homeScore} {self.homeTeam.name}"
                )
                break
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
                    # The play was executed inside playCaller() but the
                    # post-play turnover handler (lines ~3985+) never got to
                    # run because the inner possession loop broke on
                    # pre-snap clock expiry. Apply the turnover side-effects
                    # here so possession actually flips, otherwise the next
                    # quarter starts with the fumbling team still on offense.
                    if self.play.isFumbleLost or self.play.isInterception:
                        self._applyMomentumEvent(MOMENTUM_TURNOVER, self.defensiveTeam)
                        self.defensiveTeam.gameDefenseStats['fantasyPoints'] += 2
                        if self.offensiveTeam is self.homeTeam:
                            self.homeTurnoversTotal += 1
                        elif self.offensiveTeam is self.awayTeam:
                            self.awayTurnoversTotal += 1
                        # Spot the ball for the recovering team. Mirror the
                        # main turnover-handler's positioning calc.
                        recoverYards = (self.yardsToSafety + self.play.yardage)
                        if recoverYards <= 0:
                            recoverYards = 1
                        self.turnover(self.offensiveTeam, self.defensiveTeam, recoverYards)
                        self._pendingPossessionChange = True
                elif getattr(self.play, 'playText', None):
                    # Already formatted (e.g. TD broadcast) — just mark as done
                    lastPlayFormatted = True

            # Check for quarter transitions
            if self.gameClockSeconds <= 0:
                oldQuarter = self.currentQuarter
                self.advanceQuarter()
                
                # Defensive check: If still in OT and clock is still 0 after advanceQuarter, force reset
                if self.currentQuarter >= 5 and self.gameClockSeconds <= 0 and self.homeScore == self.awayScore:
                    self.gameClockSeconds = self.gameRules.overtimeLengthSeconds  # Force clock reset to prevent infinite loop
                
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
                        # Floos Bowl runs a longer, admin-configurable halftime
                        # so the halftime show has room to play.
                        halftimeOverride = (getattr(self, 'halftimeShowPauseSeconds', None)
                                            if getattr(self, 'isFloosBowl', False) else None)
                        await self.timingManager.waitForHalftime(overrideSeconds=halftimeOverride)

                    # Halftime gameplan adjustments
                    if GAMEPLAN_AVAILABLE:
                        homeOffStats = {
                            'runPlays': self.homeHalfRunPlays, 'runYards': self.homeHalfRunYards,
                            'passAttempts': self.homeHalfPassAttempts, 'passYards': self.homeHalfPassYards,
                            'wr1Yards': self.homeHalfWr1Yards, 'wr2Yards': self.homeHalfWr2Yards,
                        }
                        awayOffStats = {
                            'runPlays': self.awayHalfRunPlays, 'runYards': self.awayHalfRunYards,
                            'passAttempts': self.awayHalfPassAttempts, 'passYards': self.awayHalfPassYards,
                            'wr1Yards': self.awayHalfWr1Yards, 'wr2Yards': self.awayHalfWr2Yards,
                        }
                        homeCoach = getattr(self.homeTeam, 'coach', None)
                        awayCoach = getattr(self.awayTeam, 'coach', None)
                        adjustOffensiveGameplan(self.homeOffGameplan, homeCoach, homeOffStats)
                        adjustDefensiveGameplan(self.homeDefGameplan, homeCoach, awayOffStats)
                        adjustOffensiveGameplan(self.awayOffGameplan, awayCoach, awayOffStats)
                        adjustDefensiveGameplan(self.awayDefGameplan, awayCoach, homeOffStats)

                    # Halftime dampens momentum toward neutral. Streak is
                    # halved (truncated toward zero) rather than wiped — a
                    # team that genuinely owned the half keeps a tapered
                    # cascade going into Q3 instead of starting flat.
                    self.momentum *= 0.5
                    self.momentumStreak = int(self.momentumStreak / 2)
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
                self.yardsToFirstDown = self.gameRules.firstDownDistance
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

                    # Anomaly roll — fires Layer 1 micro-glitches for
                    # players who've accumulated enough attention. Pure
                    # flavor for v1; stat outputs unchanged.
                    self._maybeFireAnomalies()

                    # Broadcast comprehensive game state (replaces playComplete, scoreUpdate, gameStateUpdate)
                    self.broadcastGameState(includeLastPlay=True)

                # Reset flag after first iteration
                lastPlayFormatted = False

                # Between-plays timing
                if self.timingManager:
                    await self.timingManager.waitBetweenPlays()

                # After the delay: broadcast possession change with new ball position.
                # Runs BEFORE new Play() construction because an onside recovery here
                # flips possession again — constructing the Play first would freeze
                # stale offense/defense/yardLine onto the play that actually executes.
                if getattr(self, '_pendingPossessionChange', False):
                    if getattr(self, '_pendingKickoff', False):
                        kickingTeam = self.defensiveTeam
                        receivingTeam = self.offensiveTeam

                        if self._shouldOnsideKick():
                            # Announce attempt
                            onsideAttemptEvent = {
                                'text': f'{kickingTeam.abbr} attempts an onside kick!',
                                'quarter': self.currentQuarter,
                                'timeRemaining': self.formatTime(self.gameClockSeconds)
                            }
                            self.gameFeed.insert(0, {'event': onsideAttemptEvent})
                            self.broadcastGameState(
                                includeLastPlay=False,
                                isPossessionChange=True,
                                eventMessage=onsideAttemptEvent
                            )
                            if self.timingManager:
                                await self.timingManager.waitBeforeOnsideResult()

                            # Resolve recovery (~5-10% kicking team success)
                            import random
                            kickingTeamRecovers = random.random() < random.uniform(0.05, 0.10)

                            if kickingTeamRecovers:
                                self.turnover(self.offensiveTeam, self.defensiveTeam, 50)
                                onsideRecoverEvent = {
                                    'text': f'{kickingTeam.abbr} recovers the onside kick! Ball at midfield!',
                                    'quarter': self.currentQuarter,
                                    'timeRemaining': self.formatTime(self.gameClockSeconds)
                                }
                                self.gameFeed.insert(0, {'event': onsideRecoverEvent})
                                self.broadcastGameState(
                                    includeLastPlay=False,
                                    isPossessionChange=True,
                                    eventMessage=onsideRecoverEvent
                                )
                            else:
                                # Receiving team keeps ball — move to their 40 instead of their 20
                                self.yardsToEndzone = 60
                                self.yardsToSafety = self.gameRules.fieldLength - self.yardsToEndzone
                                onsideFailEvent = {
                                    'text': f'{receivingTeam.abbr} recovers at their own 40!',
                                    'quarter': self.currentQuarter,
                                    'timeRemaining': self.formatTime(self.gameClockSeconds)
                                }
                                self.gameFeed.insert(0, {'event': onsideFailEvent})
                                self.broadcastGameState(
                                    includeLastPlay=False,
                                    isPossessionChange=True,
                                    eventMessage=onsideFailEvent
                                )
                        else:
                            # Normal kickoff
                            kickoffEvent = {
                                'text': f'{kickingTeam.abbr} kicks off',
                                'quarter': self.currentQuarter,
                                'timeRemaining': self.formatTime(self.gameClockSeconds)
                            }
                            self.gameFeed.insert(0, {'event': kickoffEvent})
                            self.broadcastGameState(
                                includeLastPlay=False,
                                isPossessionChange=True,
                                eventMessage=kickoffEvent
                            )

                        self._pendingKickoff = False
                        # Clock is stopped after every kickoff until the receiving
                        # team snaps (shouldClockRun restarts it on the first
                        # in-bounds play). The TD scoring branches don't reset
                        # clockRunning the way the FG branch does, so without this
                        # the receiving team would wrongly burn a late-game timeout
                        # on an already-stopped clock right after a score + kickoff.
                        self.clockRunning = False
                        if self.timingManager:
                            await self.timingManager.waitAfterKickoff()
                    else:
                        # Punt/turnover: immediate possession-change broadcast
                        self.broadcastGameState(includeLastPlay=False, isPossessionChange=True)
                    self._pendingPossessionChange = False

                    # Recompute yardLine for the post-kickoff offense — an onside
                    # recovery may have flipped possession and moved the ball to
                    # midfield, leaving the earlier yardLine stale.
                    if self.yardsToEndzone > 50:
                        self.yardLine = '{0} {1}'.format(self.offensiveTeam.abbr, (100-self.yardsToEndzone))
                    else:
                        self.yardLine = '{0} {1}'.format(self.defensiveTeam.abbr, self.yardsToEndzone)

                # Create new play (after any possession flip from onside recovery)
                self.play = Play(self)

                # POST-PLAY: Defense can call timeout to stop the clock
                self._timeoutCalled = False
                self._checkDefensiveTimeout()
                if self._timeoutCalled and self.timingManager:
                    await self.timingManager.waitAfterTimeout()

                # Recalculate game pressure before each play
                self.gamePressure = self.calculateGamePressure()

                # Momentum: decay toward neutral and apply gameplay effect
                self._decayMomentum()
                self._applyMomentumEffect()

                # Call and execute play
                self._timeoutCalled = False
                self.playCaller()
                if self._timeoutCalled and self.timingManager:
                    await self.timingManager.waitAfterTimeout()

                # A snap has now been committed — the post-warning dead-clock
                # window is over (timeouts allowed again on the next stoppage).
                self._clockStoppedByWarning = False

                # Tempo intent is captured on every play so the play insights
                # always show the offense's intent (hurry-up / burn / neutral),
                # even when the clock is stopped going into the snap.
                self.recordTempoIntent()

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

                    if getattr(self.play, 'isFgBlocked', False):
                        # Loose ball — defense recovers, may run it back.
                        self._resolveBlockedKick()
                        self._pendingPossessionChange = True
                        lastPlayFormatted = True
                        break

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
                    from constants import PUNT_BLOCK_ENABLED, PUNT_BLOCK_CHANCE
                    if PUNT_BLOCK_ENABLED and batched_random() * 100 < PUNT_BLOCK_CHANCE:
                        # Blocked punt — never travels; defense recovers at the line
                        # (a backed-up punting team is prime scoop-and-score territory).
                        self.play.isPuntBlocked = True
                        playDuration = self.calculatePlayDuration(PlayType.Punt, False)
                        self.consumeGameTime(playDuration)
                        self.play.timeRemaining = self.formatTime(self.gameClockSeconds)
                        self.checkTwoMinuteWarning()
                        self._resolveBlockedKick()
                        self._pendingPossessionChange = True
                        lastPlayFormatted = True
                        break
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
                        self._timeoutCalled = False
                        self._checkDefensiveTimeout()
                        if self._timeoutCalled and self.timingManager:
                            await self.timingManager.waitAfterTimeout()
                        if self.clockRunning and self.gameClockSeconds > 0:
                            # No timeout called — drain the play clock (time between plays)
                            playClockDrain = min(36, self.gameClockSeconds)
                            self.consumeGameTime(playClockDrain)
                            self.checkTwoMinuteWarning()

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

                # Layer 3 anomaly — a rampant/awakened ball-carrier's play can
                # glitch and the yardage changes for real. Runs after the play
                # resolves but before the outcome is applied, so the adjusted
                # yardage flows through field position, downs, and stats.
                self._maybeApplyL3Glitch()

                # Momentum: sack (only if not also a fumble — fumbles get turnover momentum)
                if self.play.isSack and not self.play.isFumbleLost:
                    self._applyMomentumEvent(MOMENTUM_SACK, self.defensiveTeam)

                # Handle turnovers
                if self.play.isFumbleLost or self.play.isInterception:
                    # Defender runs it back — adjusts play.yardage so the outcome
                    # branches below resolve a normal return, a field-position flip,
                    # or a pick-six / scoop-and-score.
                    self._resolveDefensiveReturn()
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

                        # Defensive TD: PAT/2-pt now runs as a separate no-time
                        # play (mirroring the offensive TD path). No ptsAlwd
                        # tracking on the PAT — the team that lost the ball was
                        # on offense, not allowing points from their own offense.
                        self.play.playResult = PlayResult.Touchdown
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
                        if self._shouldGoForTwo(self.defensiveTeam):
                            self._simulate2PointConversionPlay(self.defensiveTeam, self.offensiveTeam)
                        else:
                            self._simulateExtraPointPlay(self.defensiveTeam, self.offensiveTeam, trackPtsAllowed=False)
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

                        # Broadcast TD as its own play, then run the PAT/2-pt
                        # attempt as a separate no-time play. This matches the
                        # 2-pt pattern that already existed and gives the XP
                        # its own entry in the play-by-play feed.
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

                        if self._shouldGoForTwo(self.offensiveTeam):
                            self._simulate2PointConversionPlay(self.offensiveTeam, self.defensiveTeam)
                        else:
                            self._simulateExtraPointPlay(self.offensiveTeam, self.defensiveTeam)

                        self.turnover(self.offensiveTeam, self.defensiveTeam, possReset)
                        self._pendingPossessionChange = True
                        self._pendingKickoff = True
                        lastPlayFormatted = True
                        break

                    elif self.play.yardage >= self.yardsToFirstDown:
                        downBefore = self.down
                        self.play.down = downBefore  # Store pre-play down for clutch/choke evaluation
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
                            self.yardsToFirstDown = self.gameRules.firstDownDistance
                        self.yardsToSafety += self.play.yardage
                        self.yardsToEndzone -= self.play.yardage
                        self.play.playResult = PlayResult.FirstDown
                        continue

                    elif (self.yardsToSafety + self.play.yardage) <= 0:
                        if self.play.isFumbleLost:
                            self._addScore(self.defensiveTeam, 6)
                            self._applyMomentumEvent(MOMENTUM_TD, self.defensiveTeam)

                            # Scoop-and-score TD: PAT/2-pt now fires as a
                            # separate no-time play. trackPtsAllowed=False
                            # because the team that fumbled was on offense.
                            self.play.playResult = PlayResult.Touchdown
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

                            if self._shouldGoForTwo(self.defensiveTeam):
                                self._simulate2PointConversionPlay(self.defensiveTeam, self.offensiveTeam)
                            else:
                                self._simulateExtraPointPlay(self.defensiveTeam, self.offensiveTeam, trackPtsAllowed=False)

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
                            self.clockRunning = False  # Clock stops after safety

                            self.formatPlayText()
                            # Kneels and spikes were already inserted into gameFeed
                            # before falling through to outcome handling — don't
                            # double-list the same play when it ends in a safety.
                            playInFeed = any(
                                isinstance(entry, dict) and entry.get('play') is self.play
                                for entry in self.gameFeed
                            )
                            if not playInFeed:
                                self.gameFeed.insert(0, {'play': self.play})
                            self.highlights.insert(0, {'play': self.play})
                            self.leagueHighlights.insert(0, {'play': self.play})
                            self.broadcastGameState(includeLastPlay=True)

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
                            lastPlayFormatted = True
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
                            self.clockRunning = False  # Clock stops after turnover on downs
                            self.formatPlayText()
                            # Kneel and spike branches above (line ~4451) already
                            # inserted and broadcast this play before falling
                            # through to the down-advancement section. Skip the
                            # re-insert here when that happened, otherwise the
                            # same Play object lands in gameFeed twice — once
                            # tagged "FourthDown" originally, once after this
                            # branch mutated playResult to "TurnoverOnDowns".
                            # Both render identically (same object reference).
                            if not lastPlayFormatted:
                                if self.play.isFumbleLost or self.play.isInterception or self.play.scoreChange or self.play.yardage >= 30 or self.play.isClutchPlay or self.play.isChokePlay or self.play.isMomentumShift:
                                    self.highlights.insert(0, {'play': self.play})
                                    self.leagueHighlights.insert(0, {'play': self.play})
                                self.gameFeed.insert(0, {'play': self.play})
                                self.broadcastGameState(includeLastPlay=True)
                            self.turnover(self.offensiveTeam, self.defensiveTeam, self.yardsToSafety)
                            self._pendingPossessionChange = True
                            lastPlayFormatted = True
                            break
        
        # Game over - ensure the final play is formatted, in gameFeed, and broadcast.
        # Scoring plays and special plays (FG, punt, TD) are typically formatted and
        # added to gameFeed inside the loop. Non-scoring plays (kneels, normal runs/passes
        # at clock expiration) are normally formatted at the TOP of the next loop iteration,
        # which never runs when the game ends. Handle all cases here.
        # Scan the whole feed: a sideline cutaway inserted by the prior broadcast can
        # push the play off index 0 even when it was already added inside the loop.
        alreadyInFeed = any(
            entry.get('play') is self.play
            for entry in self.gameFeed
            if isinstance(entry, dict)
        )
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
            # Tie game. The main loop only exits with tied scores via two
            # paths: (a) the OT-period cap below force-stops a no-score
            # stalemate, or (b) some still-unidentified state transition
            # set status=Final while tied. Log the second case loudly
            # — every other tied-finalize means the bug recurred.
            logger.warning(
                f"[GAME] Tied finalize: {self.awayTeam.name} {self.awayScore} - "
                f"{self.homeScore} {self.homeTeam.name} | quarter={self.currentQuarter} "
                f"otPeriod={getattr(self, 'otPeriod', 0)} clock={self.gameClockSeconds} "
                f"otFirstPossComplete={getattr(self, 'otFirstPossComplete', None)} "
                f"otSecondPossComplete={getattr(self, 'otSecondPossComplete', None)} "
                f"totalPlays={self.totalPlays}"
            )
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
        # Freeze game stats while players are still on their teams
        self._cachedGameStats = self._buildGameStatsSnapshot()
        self.gameDict['winningTeam'] = self.winningTeam.name
        self.gameDict['losingTeam'] = self.losingTeam.name
        self.saveGameData()
        self.homeTeam.getAverages(season=self.seasonNumber)
        self.awayTeam.getAverages(season=self.seasonNumber)
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

        # Per-team correlation log: pressure level, outcome, ELO delta,
        # form state, roster resolve average. Written to logs/pressure_correlation.jsonl
        # for offline analysis of how pressure relates to outcomes/metrics.
        self._logPressureCorrelation()

        # Per-game play analytics — aggregates TDs, INTs, yardage, big plays
        # by tier so we can tune the pass/run distributions post-hoc.
        # Written to logs/sim_analytics.jsonl.
        self._logPlayAnalytics()

        # Postgame personality reactions — winners go positive, losers go negative.
        # Inserted into gameFeed as cutaway-style entries so they render alongside
        # plays in the modal feed and survive page reloads via /api/games/{id}.
        self._buildPostgameReactions()
        
        # Broadcast final game state with the "Final" event message so the play feed updates live.
        # Include the last play alongside the event so the frontend always gets the final play
        # even if the earlier per-play broadcast was missed (async task timing).
        if BROADCASTING_AVAILABLE and broadcaster.is_enabled():
            self.broadcastGameState(includeLastPlay=True, eventMessage=finalEventMessage, isFinalBroadcast=True)
        
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

        # Yield to the event loop so all queued broadcast tasks (final play,
        # "Final" event, game_end) actually send before playGame() returns.
        # Without this, create_task broadcasts have no await point to execute.
        await asyncio.sleep(0)


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

        # Quarter + clock-time pressure (primary axis).
        # Earlier this used playsIntoQ4 as a clock proxy, which made routine
        # mid-Q4 plays accumulate too much pressure. Direct clock-time
        # bucketing makes 'decisive moment' a natural function of when in
        # the game it happens — final 2 min and OT spike pressure hard, mid-
        # quarter plays don't.
        secs = self.gameClockSeconds
        if self.currentQuarter == 5:  # OT — every play decides
            pressure += 50
        elif self.currentQuarter == 4:
            if secs <= 60:    # final minute
                pressure += 55
            elif secs <= 120: # final 2 min — crunch time
                pressure += 45
            elif secs <= 300: # final 5 min
                pressure += 30
            elif secs <= 600: # final 10 min
                pressure += 18
            else:
                pressure += 10
        elif self.currentQuarter == 3:
            pressure += 15 if secs <= 60 else 10  # end-of-quarter bump
        elif self.currentQuarter == 2:
            pressure += 15 if secs <= 60 else 5   # end-of-half bump
        else:
            pressure += 5

        # Score differential pressure (0-30), scaled by quarter so early-game ties
        # don't generate clutch/choke moments
        scoreDiff = abs(self.homeScore - self.awayScore)
        scorePressure = 0
        if scoreDiff == 0:
            scorePressure = 30  # Tie game
        elif scoreDiff <= 3:
            scorePressure = 25  # One field goal difference
        elif scoreDiff <= 7:
            scorePressure = 20  # One possession game
        elif scoreDiff <= 14:
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

        # Blowout dampening — large leads make the game feel decided,
        # sharply reducing pressure regardless of other factors
        if scoreDiff > 21:
            pressure *= 0.1   # Game is effectively over
        elif scoreDiff > 14:
            pressure *= 0.3   # Comfortable lead, unlikely comeback

        # Early-game dampening — Q1/Q2/Q3 plays rarely define a game,
        # prevents high team modifiers (Floosbowl 2.5x) from inflating
        # routine early plays into clutch/choke territory
        earlyGameScale = {1: 0.3, 2: 0.5, 3: 0.7, 4: 1.0, 5: 1.0}
        pressure *= earlyGameScale.get(self.currentQuarter, 1.0)

        # Apply the team pressure modifier (playoff importance, Floosbowl,
        # prior-season expectations, in-season elimination state, etc.) with
        # market-tier expectation scaling layered on top: big markets amplify
        # high-expectation deltas, small markets amplify the relief side.
        # Streak pressure (built from consecutive wins) is added to the base
        # modifier before scaling so it gets the same market amplification.
        from constants import (
            EXPECTATION_SCALE_BY_TIER,
            EXPECTATION_RELIEF_BY_TIER,
            EXPECTATION_DELTA_CAP,
            CHAMPIONSHIP_OVERFLOW_FACTOR,
        )
        pressureMod = self.offensiveTeam.pressureModifier
        streakAdd = getattr(self.offensiveTeam, 'streakPressure', 0.0)
        effective = pressureMod + streakAdd
        delta = effective - 1.0
        tier = getattr(self.offensiveTeam, 'fundingTier', None)
        if delta > 0:
            tierScale = EXPECTATION_SCALE_BY_TIER.get(tier, 1.0)
            # Soften scaling above the championship band so MEGA Floos Bowl
            # doesn't auto-cap pressure at 100 on every play. Cap portion
            # gets full market amplification; overflow gets a weaker factor
            # (default 1.0 — overflow added unscaled).
            cap = min(delta, EXPECTATION_DELTA_CAP)
            overflow = max(0.0, delta - EXPECTATION_DELTA_CAP)
            scaledDelta = cap * tierScale + overflow * CHAMPIONSHIP_OVERFLOW_FACTOR
        else:
            reliefScale = EXPECTATION_RELIEF_BY_TIER.get(tier, 1.0)
            scaledDelta = delta * reliefScale
        pressure = pressure * (1.0 + scaledDelta)

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

    def _scoreGapDampener(self, benefitingTeam=None):
        """Reduce momentum gains in blowouts — but only for the team that's
        already ahead. The trailing team's comeback push generates momentum
        at full value (in fact the narrative needs it to). Returns 0.2-1.0
        when benefitingTeam is the leader, 1.0 when it's the trailing team
        or the game is tied. Pass None for legacy callers that want the
        symmetric blowout-decay behavior (used by _decayMomentum)."""
        scoreDiff = abs(self.homeScore - self.awayScore)
        if scoreDiff <= 14:
            return 1.0
        if benefitingTeam is not None:
            leadingTeam = self.homeTeam if self.homeScore > self.awayScore else (
                self.awayTeam if self.awayScore > self.homeScore else None
            )
            if benefitingTeam is not leadingTeam:
                return 1.0
        if scoreDiff <= 21:
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

        # Dampening — gap damp is asymmetric: only the leading team's
        # piling-on is muted, the trailing team's comeback momentum hits
        # at full value regardless of deficit.
        gapDamp = self._scoreGapDampener(benefitingTeam)
        mentalResist = self._mentalResistance(resistingTeam)

        # Cascade multiplier — scale down in blowouts so piling-on streaks flatten out
        self._updateMomentumStreak(benefitingTeam)
        streakBonus = MOMENTUM_CASCADE_STEP * (abs(self.momentumStreak) - 1) * gapDamp
        cascadeMultiplier = min(1.0 + streakBonus, MOMENTUM_MAX_CASCADE)

        # Late-game amplifier: events inside Q4 two-minute warning (or in any
        # OT period) carry more narrative weight than the raw math gives them.
        # A 1.3x bump small enough not to distort typical games, big enough
        # that closing-minute swings feel as heavy as they read.
        inTwoMinute = (self.currentQuarter == 4 and self.gameClockSeconds < 120)
        inOvertime = self.currentQuarter >= 5
        lateGameMultiplier = 1.3 if (inTwoMinute or inOvertime) else 1.0

        # Comeback urgency: a team trailing by 10+ in Q3 or later plays
        # with measurable desperation — momentum events for the trailing
        # side hit 1.15x. Pairs with the asymmetric gap dampener to keep
        # comeback narratives alive; underdogs were winning ~10pp below
        # pre-game WP without this push.
        benefitingScore = self.homeScore if benefitingTeam is self.homeTeam else self.awayScore
        opposingScore = self.awayScore if benefitingTeam is self.homeTeam else self.homeScore
        deficit = opposingScore - benefitingScore
        comebackUrgency = 1.15 if (self.currentQuarter >= 3 and deficit >= 10) else 1.0

        finalDelta = rawDelta * cascadeMultiplier * gapDamp * mentalResist * streakInertia * lateGameMultiplier * comebackUrgency

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
        # Diagnostic sampling — once per play call, regardless of neutral zone
        absMom = abs(self.momentum)
        if absMom > self._peakAbsMomentum:
            self._peakAbsMomentum = absMom
        if absMom >= 30.0:
            self._playsAbove30Mom += 1

        if absMom < MOMENTUM_NEUTRAL_ZONE:
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

        # Slight drag on suffering team. Was 0.5x the benefiting team's
        # boost, but post-instrumentation showed favorites winning at
        # +13pp over pre-game WP and underdogs at -10pp — the drag was
        # compounding the favorite's advantage into a death spiral. 0.3x
        # leaves the drag detectable without crushing the trailing team.
        dragMagnitude = effectMagnitude * 0.3
        for player in suffering.rosterDict.values():
            if player is not None:
                player.updateInGameConfidence(-dragMagnitude * 0.6)
                player.updateInGameDetermination(-dragMagnitude * 0.4)

    # ─── End Momentum System ────────────────────────────────────────────────

    # ─── Funding Morale ───────────────────────────────────────────────────

    def _applyFundingMorale(self, team):
        """Apply a small pregame confidence/determination nudge based on the
        team's Locker Room level (Markets→Facilities; migrated levels reproduce
        the old market-tier morale modifier)."""
        modifier = team.facilityEffect('morale') if hasattr(team, 'facilityEffect') else 0
        if modifier == 0:
            return
        for player in team.rosterDict.values():
            if player is not None and player.gameAttributes is not None:
                player.updateInGameConfidence(modifier * 0.6)
                player.updateInGameDetermination(modifier * 0.4)

    def _snapshotBaselineRatings(self, team):
        """Record each rostered player's pre-modifier overallRating so the
        soft cap can enforce a floor relative to it AND the per-game stats
        snapshot can surface the modifier breakdown. Stored as a transient
        attribute on the player object.

        NOTE: must use updateInGameRating() — updateRating() writes to
        attributes.overallRating (baseline), not gameAttributes.overallRating
        (the in-game value the modifier stack mutates).
        """
        for player in team.rosterDict.values():
            if player is None or player.gameAttributes is None:
                continue
            # Refresh derived rating first so the baseline is current.
            try:
                player.updateInGameRating()
            except Exception:
                pass
            player._preGameBaselineRating = player.gameAttributes.overallRating
            # Initialize the snapshot bucket. Subsequent _snapshotMentalPhase
            # calls fill in intermediate values after each modifier stage so
            # _buildMentalBreakdown can compute per-stage deltas.
            player._mentalSnapshots = {
                'baseline': player.gameAttributes.overallRating,
                'afterFatigue': None,
                'afterDisposition': None,
                'afterCap': None,
            }

    def _snapshotMentalPhase(self, team, key):
        """Record the current overallRating under `key` on each player's
        _mentalSnapshots dict. Called after every modifier stage so the
        per-game breakdown can attribute rating drift back to each phase.

        NOTE: must use updateInGameRating() — updateRating() refreshes the
        baseline attributes.overallRating, not gameAttributes.overallRating
        (which is what the modifier stack mutates and what we want to read).
        """
        for player in team.rosterDict.values():
            if player is None or player.gameAttributes is None:
                continue
            snaps = getattr(player, '_mentalSnapshots', None)
            if snaps is None:
                continue
            try:
                player.updateInGameRating()
            except Exception:
                pass
            snaps[key] = player.gameAttributes.overallRating

    def _buildMentalBreakdown(self, player) -> Optional[dict]:
        """Compute the per-stage modifier deltas for surfacing in the box
        score. Two stages now: fatigue + disposition (the combined form +
        context multiplier), then the soft cap. Returns None if no
        snapshots were captured (e.g., bench player who never got mutated).
        """
        snaps = getattr(player, '_mentalSnapshots', None)
        if not snaps:
            return None
        baseline = snaps.get('baseline')
        if not baseline:
            return None
        afterFatigue = snaps.get('afterFatigue') or baseline
        afterDisposition = snaps.get('afterDisposition') or afterFatigue
        afterCap = snaps.get('afterCap') or afterDisposition
        return {
            'baseline': int(baseline),
            'final': int(afterCap),
            'totalDelta': int(afterCap - baseline),
            'fatigue': int(afterFatigue - baseline),
            'disposition': int(afterDisposition - afterFatigue),
            'cap': int(afterCap - afterDisposition),
        }

    def _avgStarterSnapshot(self, team, snapshotKey: str) -> float:
        """Mean overallRating of starters at a given snapshot phase.
        Used by analytics to see how each modifier stage shifted the
        roster average. Returns 0.0 if no players carry the snapshot.
        """
        total = 0.0
        n = 0
        for player in team.rosterDict.values():
            if player is None:
                continue
            snaps = getattr(player, '_mentalSnapshots', None)
            if not snaps:
                continue
            val = snaps.get(snapshotKey)
            if val is None:
                continue
            total += val
            n += 1
        return total / n if n else 0.0

    def _avgStarterCurrentRating(self, team) -> float:
        """Mean current overallRating of starters — sample at game end to
        capture drift from momentum/clutch/choke/per-play fatigue."""
        total = 0.0
        n = 0
        for player in team.rosterDict.values():
            if player is None or player.gameAttributes is None:
                continue
            try:
                player.updateInGameRating()
            except Exception:
                pass
            total += player.gameAttributes.overallRating
            n += 1
        return total / n if n else 0.0

    def _applyLeagueCompression(self, team):
        """Pull every rostered player's in-game attributes toward the
        league mean by LEAGUE_COMPRESSION_FACTOR. A 95-rated star
        effectively plays as ~90.5; a 65-rated reserve plays as ~69.5.
        Closes the auto-win gap between stars and scrubs without
        erasing skill order.

        Profile ratings (player.attributes) stay untouched — only the
        live gameAttributes copy is compressed, so the player page
        still reads 95. Downstream modifiers (fatigue, disposition,
        soft cap) stack on the compressed baseline.

        Set LEAGUE_COMPRESSION_FACTOR to 1.0 in constants to disable.
        """
        from constants import LEAGUE_COMPRESSION_FACTOR, LEAGUE_COMPRESSION_MEAN
        factor = LEAGUE_COMPRESSION_FACTOR
        if factor >= 0.999:
            return  # disabled
        mean = LEAGUE_COMPRESSION_MEAN
        # Physical attrs that drive most on-field outcomes, plus the
        # four game-formula intangibles. Locker-room attrs (attitude,
        # resilience, selfBelief) are intentionally NOT compressed —
        # their wide range is the source of personality variance.
        attrs = (
            'speed', 'power', 'agility', 'hands', 'reach',
            'armStrength', 'accuracy', 'legStrength',
            'focus', 'discipline', 'instinct', 'creativity',
        )
        for player in team.rosterDict.values():
            if player is None or player.gameAttributes is None:
                continue
            for attr in attrs:
                val = getattr(player.gameAttributes, attr, None)
                if val is None:
                    continue
                compressed = mean + (val - mean) * factor
                # Stay within the engine's expected 30-100 envelope.
                compressed = max(30, min(100, round(compressed)))
                setattr(player.gameAttributes, attr, compressed)
            # Recompute derived ratings from the compressed leaves so
            # skillRating, xFactor, overallRating all reflect the curve.
            try:
                player.gameAttributes.calculateIntangibles()
                player.gameAttributes.calculateSkills()
                player.updateInGameRating()
            except Exception:
                pass

    def _enforceMentalSoftCap(self, team):
        """Scale a player's gameAttributes back up uniformly if the
        compounded pre-game mental/form/context modifiers dropped their
        overall rating below baseline × MENTAL_FLOOR_RATIO. Without this,
        unlucky modifier stacks can drop a star ~25% in effective rating
        with no surface signal, which reads as 'sim is broken' to users.

        The scaling preserves attribute proportions — a power-back stays
        power-heavy, a route-runner stays route-runner. The cap doesn't
        remove the systems; it just bounds the worst-felt aggregate outcome.
        """
        from constants import MENTAL_FLOOR_RATIO
        for player in team.rosterDict.values():
            if player is None or player.gameAttributes is None:
                continue
            baseline = getattr(player, '_preGameBaselineRating', None)
            if not baseline or baseline <= 0:
                continue
            # Refresh derived overall first so we compare apples to apples.
            try:
                player.updateInGameRating()
            except Exception:
                pass
            current = player.gameAttributes.overallRating
            floor = baseline * MENTAL_FLOOR_RATIO
            if current >= floor or current <= 0:
                continue
            # Uniform scale on the leaf attributes so derived ratings rise
            # proportionally on the next recompute.
            scale = floor / current
            for attr in ('speed', 'hands', 'agility', 'power', 'armStrength',
                         'accuracy', 'legStrength', 'reach',
                         'focus', 'discipline', 'instinct'):
                val = getattr(player.gameAttributes, attr, 0)
                if val:
                    setattr(player.gameAttributes, attr,
                            min(100, round(val * scale)))
            try:
                player.updateInGameRating()
            except Exception:
                pass
            logger.debug(
                f"Mental soft cap engaged: {player.name} "
                f"baseline={baseline} pre-cap={current} "
                f"post-cap={player.gameAttributes.overallRating}"
            )

    def _applyTeamRatingMult(self, team, multiplier):
        """Apply a uniform attribute multiplier to all rostered players, then
        recompute derived ratings. Shared by _applyFormState and
        _applyContextModifiers.
        """
        if multiplier == 1.0:
            return
        from constants import RATING_SCALE_MIN
        for player in team.rosterDict.values():
            if player is None or player.gameAttributes is None:
                continue
            for attr in ('speed', 'hands', 'agility', 'power', 'armStrength',
                         'accuracy', 'legStrength', 'reach',
                         'focus', 'discipline', 'instinct'):
                val = getattr(player.gameAttributes, attr, 0)
                if val:
                    setattr(player.gameAttributes, attr,
                            max(RATING_SCALE_MIN, min(100, round(val * multiplier))))
            player.gameAttributes.calculateIntangibles()
            player.gameAttributes.calculateSkills()

    def _applyFormState(self, team):
        """Deprecated. Use _applyTeamDisposition (combines form + context
        into one capped multiplier with a single narrative label).
        Kept as a no-op so older call-sites don't break."""
        return

    # Narrative labels for the combined team disposition. Picked by
    # _pickDispositionLabel based on form state + which context factors
    # fired. Designed so a low-discipline favored team gets ONE explanation
    # ("Trap-Game Risk") instead of stacked "Complacent" + "Trap game".
    _DISPOSITION_FORM_LABELS = {
        'HOT_STREAK':  'Hot Streak',
        'GETTING_HOT': 'Building Momentum',
        'STEADY':      'Steady',
        'SHAKY':       'Shaky',
        'COOLING_OFF': 'Cooling Off',
        'COMPLACENT':  'Complacent',
        'SPIRALING':   'Spiraling',
        'RESOLUTE':    'Resolute',
        'UNKNOWN':     'Steady',
    }

    # Friendly fallback label for each context factor, used when form is
    # neutral (STEADY / UNKNOWN) but a context modifier still fired. The
    # composite labels above (Trap-Game Risk, Cinderella Push) take
    # precedence when form + context share a root signal.
    #
    # Naming philosophy: evoke the state, don't describe the mechanism.
    # "Buy-In" / "Adrift" let users infer the coach connection from the
    # supporting data (coach attitude, team mood, etc.) without the label
    # spelling out the cause.
    _DISPOSITION_CTX_LABELS = {
        'Trap game':             'Trap-Game Risk',
        'Underdog hunger':       'Underdog Push',
        'Clinched coast':        'Coasting',
        'Playoff push':          'Playoff Push',
        'Playing for the coach': 'Buy-In',
        'Disengaged from coach': 'Adrift',
    }

    def _pickDispositionLabel(self, formState, ctxReasons, multiplier):
        """Choose the single narrative label that best explains the
        combined disposition. Direction of the net delta drives the
        choice — a Complacent team with a partial Playoff Push offset
        is still net Complacent, so the label should say so.

        Priority:
          1. Compound labels for shared-root signals (Trap-Game Risk,
             Cinderella Push).
          2. Form-state label if its direction matches the net delta.
          3. Dominant context factor whose direction matches the net.
          4. Form-state label as a final fallback.
        """
        from constants import FORM_STATE_RATING_MULT
        ctxLabels = [r['label'] for r in ctxReasons]

        if formState == 'COMPLACENT' and 'Trap game' in ctxLabels:
            return 'Trap-Game Risk'
        if formState == 'RESOLUTE' and 'Underdog hunger' in ctxLabels:
            return 'Cinderella Push'

        formLabel = self._DISPOSITION_FORM_LABELS.get(formState, 'Steady')
        netDelta = multiplier - 1.0

        # Neutral net — use form's narrative identity (e.g. Hot Streak
        # at multiplier 1.0 still wants a label) or 'Steady'.
        if abs(netDelta) < 0.005:
            return formLabel

        isDrag = netDelta < 0
        formMult = FORM_STATE_RATING_MULT.get(formState, 1.0)
        formDrag = formMult < 1.0
        formBoost = formMult > 1.0

        # Form direction matches net direction — form is the dominant
        # explanation, use its label.
        if isDrag and formDrag:
            return formLabel
        if (not isDrag) and formBoost:
            return formLabel

        # Net direction is driven by context — pick the first context
        # factor whose direction matches the net.
        wantKind = 'drag' if isDrag else 'boost'
        for r in ctxReasons:
            if r.get('kind') == wantKind:
                return self._DISPOSITION_CTX_LABELS.get(r['label'], formLabel)

        return formLabel

    def _applyTeamDisposition(self):
        """Combined team-disposition modifier. Replaces the prior split
        between _applyFormState (form-state multiplier) and
        _applyContextModifiers (matchup-context multiplier) — both were
        team-wide, both keyed on overlapping inputs (discipline, attitude,
        ELO), and stacking them double-counted the same underlying signal.

        Now: compute both, multiply them, cap aggregate at ±10%, pick one
        narrative label, apply once. Each team carries _dispositionLabel
        and _dispositionMultiplier afterward so the box-score breakdown
        can explain *why* a player's rating moved without surfacing two
        rows that share a root cause.
        """
        try:
            from api_response_builders import TeamResponseBuilder
            from constants import FORM_STATE_RATING_MULT
        except Exception:
            return

        def resolve(team, opponent):
            formState = TeamResponseBuilder.computeFormState(team)
            formMult = FORM_STATE_RATING_MULT.get(formState, 1.0)
            # Regression-to-mean: teams stuck in the same form state for
            # 3+ weeks have a rising chance per game to have their form
            # contribution halved. Preserves the prior _applyFormState
            # behaviour now that form is folded into disposition.
            weeksHeld = getattr(team, '_formStateWeeksHeld', 0)
            if weeksHeld >= 3 and formMult != 1.0:
                weakenChance = min(0.70, (weeksHeld - 2) * 0.15)
                if _random.random() < weakenChance:
                    formMult = 1.0 + (formMult - 1.0) * 0.5
                    logging.debug(
                        f"_disposition: {team.abbr} {formState} held "
                        f"{weeksHeld} weeks → form softened to {formMult:.3f}"
                    )

            ctxMult, ctxReasons = self._computeContextMultiplier(team, opponent)

            # No aggregate cap on disposition — the wider swings are the
            # drama generator. A truly COMPLACENT team in a trap game
            # needs enough mechanical weight to actually lose to an
            # underdog with hunger; capping at ±10% flattens exactly the
            # season variance the mental sim is meant to produce. The
            # soft floor at MENTAL_FLOOR_RATIO × baseline (15%) still
            # prevents the absolute worst aggregate outcomes downstream.
            combined = formMult * ctxMult
            label = self._pickDispositionLabel(formState, ctxReasons, combined)
            return combined, label, formState, ctxReasons

        homeMult, homeLabel, homeForm, homeReasons = resolve(self.homeTeam, self.awayTeam)
        awayMult, awayLabel, awayForm, awayReasons = resolve(self.awayTeam, self.homeTeam)

        self.homeTeam._dispositionMultiplier = homeMult
        self.homeTeam._dispositionLabel = homeLabel
        self.homeTeam._dispositionFormState = homeForm
        self.homeTeam._contextReasons = homeReasons

        self.awayTeam._dispositionMultiplier = awayMult
        self.awayTeam._dispositionLabel = awayLabel
        self.awayTeam._dispositionFormState = awayForm
        self.awayTeam._contextReasons = awayReasons

        self._applyTeamRatingMult(self.homeTeam, homeMult)
        self._applyTeamRatingMult(self.awayTeam, awayMult)

    def _computeContextMultiplier(self, team, opponent):
        """Combined per-matchup contextual multiplier covering:
          - trap game: heavy favorite + low team discipline → coasts
          - playoff push: late season + on bubble + positive determination
                          → urgency boost (scales harder toward season end)
          - clinched coast: late season + clinched + low discipline → coasts
          - play-hard-for-coach: leader/toxic coach colors game-day effort

        Returns (multiplier, reasons) where reasons is a list of
        {'label': str, 'kind': 'boost'|'drag'} for each factor that fired.
        Surfaced in the per-player box-score breakdown so users can see
        *why* matchup context moved a player off their baseline.
        """
        if not self.isRegularSeasonGame:
            return 1.0, []
        starters = [p for p in team.rosterDict.values() if p is not None]
        if not starters:
            return 1.0, []
        teamElo = getattr(team, 'elo', 1500) or 1500
        oppElo = getattr(opponent, 'elo', 1500) or 1500
        avgDiscipline = sum(p.attributes.discipline for p in starters) / len(starters)
        avgDetMod = sum(
            getattr(p.attributes, 'determinationModifier', 0) or 0
            for p in starters
        ) / len(starters)

        multiplier = 1.0
        reasons = []

        if teamElo - oppElo >= 100:
            trapScale = max(0.0, min(1.0, (80 - avgDiscipline) / 20))
            if trapScale > 0:
                trapMag = 0.05 + 0.03 * trapScale
                multiplier *= 1.0 - trapMag
                reasons.append({'label': 'Trap game', 'kind': 'drag'})
                logging.debug(
                    f"_context: {team.abbr} trap-game vs {opponent.abbr} "
                    f"(ELO+{teamElo-oppElo}, disc {avgDiscipline:.1f}) "
                    f"× {1.0 - trapMag:.3f}"
                )
        elif oppElo - teamElo >= 100 and avgDetMod > 0:
            detFactor = min(1.0, avgDetMod / 3)
            hungerMag = 0.05 + 0.02 * detFactor
            multiplier *= 1.0 + hungerMag
            reasons.append({'label': 'Underdog hunger', 'kind': 'boost'})
            logging.debug(
                f"_context: {team.abbr} underdog-hunger vs {opponent.abbr} "
                f"(ELO-{oppElo-teamElo}, detMod {avgDetMod:+.2f}) "
                f"× {1.0 + hungerMag:.3f}"
            )

        week = self.week or 0
        if week >= 24:
            clinched = bool(getattr(team, 'clinchedPlayoffs', False))
            eliminated = bool(getattr(team, 'eliminated', False))

            if clinched:
                if avgDiscipline < 75:
                    coastMag = 0.05 + (week - 24) * 0.01
                    multiplier *= 1.0 - coastMag
                    reasons.append({'label': 'Clinched coast', 'kind': 'drag'})
                    logging.debug(
                        f"_context: {team.abbr} clinched-coast wk{week} "
                        f"(disc {avgDiscipline:.1f}) × {1.0 - coastMag:.3f}"
                    )
            elif not eliminated:
                if avgDetMod > 0:
                    urgencyFactor = min(1.0, (week - 23) / 5)
                    detFactor = min(1.0, avgDetMod / 3)
                    pushMag = 0.02 + 0.03 * urgencyFactor * detFactor
                    multiplier *= 1.0 + pushMag
                    reasons.append({'label': 'Playoff push', 'kind': 'boost'})
                    logging.debug(
                        f"_context: {team.abbr} playoff-push wk{week} "
                        f"(detMod {avgDetMod:+.2f}, urgency {urgencyFactor:.1f}) "
                        f"× {1.0 + pushMag:.3f}"
                    )

        coach = getattr(team, 'coach', None)
        coachAttitude = getattr(coach, 'attitude', 80) if coach else 80
        if coachAttitude >= 90:
            coachMag = 0.01 + (coachAttitude - 90) / 1000
            multiplier *= 1.0 + coachMag
            reasons.append({'label': 'Playing for the coach', 'kind': 'boost'})
            logging.debug(
                f"_context: {team.abbr} play-hard-for-coach (coach att "
                f"{coachAttitude}) × {1.0 + coachMag:.3f}"
            )
        elif coachAttitude <= 70:
            coachMag = 0.01 + (70 - coachAttitude) / 1000
            multiplier *= 1.0 - coachMag
            reasons.append({'label': 'Disengaged from coach', 'kind': 'drag'})
            logging.debug(
                f"_context: {team.abbr} disengaged-from-coach (coach att "
                f"{coachAttitude}) × {1.0 - coachMag:.3f}"
            )

        return multiplier, reasons

    def _applyContextModifiers(self):
        """Deprecated. Folded into _applyTeamDisposition. Kept as a no-op
        so older call-sites don't break during the transition."""
        return

    def _applyFatigue(self, team):
        """Reduce in-game attributes based on accumulated player fatigue."""
        from constants import (FATIGUE_PHYSICAL_IMPACT, FATIGUE_MENTAL_IMPACT,
                               RATING_SCALE_MIN)
        for player in team.rosterDict.values():
            if player is None or player.gameAttributes is None:
                continue
            fatigue = getattr(player.attributes, 'fatigue', 0.0) or 0.0
            if fatigue <= 0:
                continue

            # Physical attributes: full fatigue impact
            physMult = 1.0 - fatigue * FATIGUE_PHYSICAL_IMPACT
            for attr in ('speed', 'hands', 'agility', 'power', 'armStrength',
                         'accuracy', 'legStrength', 'reach'):
                val = getattr(player.gameAttributes, attr, 0)
                setattr(player.gameAttributes, attr,
                        max(RATING_SCALE_MIN, round(val * physMult)))

            # Mental/derived attributes: reduced impact
            mentalMult = 1.0 - fatigue * FATIGUE_MENTAL_IMPACT
            for attr in ('focus', 'discipline', 'routeRunning', 'vision'):
                val = getattr(player.gameAttributes, attr, 0)
                setattr(player.gameAttributes, attr,
                        max(RATING_SCALE_MIN, round(val * mentalMult)))

            # Recalculate derived attributes after fatigue adjustments
            player.gameAttributes.calculateIntangibles()
            player.gameAttributes.calculateSkills()

    def formatTime(self, seconds: int) -> str:
        """Format seconds into MM:SS display format"""
        minutes = seconds // 60
        secs = seconds % 60
        return f"{minutes}:{secs:02d}"
    
    def _buildGameStatsSnapshot(self) -> dict:
        """Build a snapshot of team-level box score and per-player game stats."""
        if hasattr(self, '_cachedGameStats') and self._cachedGameStats:
            return self._cachedGameStats

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

            # QB lost fumbles (sack-strips / scramble fumbles) count as turnovers
            # too — the loop above only covers the skill positions.
            qbFumblesLost = qb.gameStatsDict['rushing']['fumblesLost'] if qb else 0
            turnovers = passInts + fumbleLost + qbFumblesLost
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
                result = {
                    'id': p.id,
                    'name': p.name,
                    'position': p.position.name if hasattr(p, 'position') and p.position else None,
                    'defensivePosition': p.defensivePosition.value if hasattr(p, 'defensivePosition') and p.defensivePosition else None,
                    'teamId': p.team.id if hasattr(p, 'team') and hasattr(p.team, 'id') else None,
                    'playerRating': rating,
                    'ratingStars': max(1, min(5, stars)),
                    'fantasyPoints': p.gameStatsDict.get('fantasyPoints', 0),
                    'totalFantasyPoints': p.seasonStatsDict.get('fantasyPoints', 0) + p.gameStatsDict.get('fantasyPoints', 0),
                    'totalTds': totalTds,
                    **stats,
                }
                # QB scrambles: the QB flattens 'passing', so its rushing line
                # would otherwise be invisible. Attach it as a nested block so
                # the box score can list a scrambling QB in the rushing section.
                if statsKey == 'passing':
                    qbRush = dict(p.gameStatsDict['rushing'])
                    qbCarries = qbRush.get('carries', 0)
                    qbRush['ypc'] = round(qbRush.get('yards', 0) / qbCarries, 1) if qbCarries > 0 else 0.0
                    result['rushing'] = qbRush
                # Per-player pre-game mental modifier breakdown — always
                # included when snapshots exist, even if every stage netted
                # zero. "Nothing is dragging this player" is itself useful
                # context for users trying to understand a stat line.
                breakdown = self._buildMentalBreakdown(p)
                if breakdown:
                    result['mentalBreakdown'] = breakdown
                # Mindset numbers — both pre-game baseline and the live
                # in-game value. The drift between them is the LARGEST
                # invisible driver of "my star had a bad game": every
                # play applies _mentalDrift which amplifies drift 25×,
                # so a -3 confidence drop is ~-4.5 effective rating per
                # play. Surfacing pre-game and current together lets
                # users see whether the bad performance came from a
                # pre-game state or a mid-game collapse.
                try:
                    cnfBase = round(getattr(p.attributes, 'confidenceModifier', 0) or 0, 2)
                    detBase = round(getattr(p.attributes, 'determinationModifier', 0) or 0, 2)
                    cnfNow = round(getattr(p.gameAttributes, 'confidenceModifier', 0) or 0, 2)
                    detNow = round(getattr(p.gameAttributes, 'determinationModifier', 0) or 0, 2)
                    result['confidenceModifier'] = cnfBase
                    result['determinationModifier'] = detBase
                    result['confidenceInGame'] = cnfNow
                    result['determinationInGame'] = detNow
                    result['confidenceDrift'] = round(cnfNow - cnfBase, 2)
                    result['determinationDrift'] = round(detNow - detBase, 2)
                except Exception:
                    pass
                # Season-average FP coming into this game — the reference
                # users actually care about when judging "performed like
                # they should". Per-game stats hold this game; season
                # totals hold prior games only.
                try:
                    gp = max(0, getattr(p, 'gamesPlayed', 0) or 0)
                    seasonFp = p.seasonStatsDict.get('fantasyPoints', 0) or 0
                    if gp > 0:
                        result['seasonAvgFP'] = round(seasonFp / gp, 1)
                        result['seasonGP'] = gp
                except Exception:
                    pass
                # Pressure exposure — biggest invisible driver of
                # "good player choked in a big moment". pressureHandling
                # is the player's per-play stochastic over/underperform
                # disposition; team.pressureModifier is the game-day
                # stakes multiplier (market expectations + in-season
                # urgency, championship games hit 2.5).
                try:
                    result['pressureHandling'] = int(getattr(
                        p.attributes, 'pressureHandling', 0) or 0)
                    pTeam = getattr(p, 'team', None)
                    if pTeam is not None:
                        result['teamPressureModifier'] = round(
                            getattr(pTeam, 'pressureModifier', 1.0) or 1.0, 2)
                except Exception:
                    pass
                # Static mental/personality attributes — surfaced as
                # status badges in the breakdown panel so users can
                # read a player's profile at a glance. Each badge maps
                # to a tier label on the frontend.
                try:
                    for attr in ('attitude', 'resilience', 'selfBelief',
                                 'discipline', 'focus', 'instinct', 'creativity'):
                        val = getattr(p.attributes, attr, None)
                        if val is not None:
                            result[attr] = int(val)
                except Exception:
                    pass
                # Single narrative label for the team's combined disposition
                # ("Hot Streak", "Trap-Game Risk", "Cinderella Push", etc.).
                # Replaces the prior split between formStateLabel +
                # contextReasons — those two fields stacked separately in
                # the UI and double-explained the same effect.
                try:
                    pTeam = getattr(p, 'team', None)
                    if pTeam is not None:
                        label = getattr(pTeam, '_dispositionLabel', None)
                        if label:
                            result['dispositionLabel'] = label
                except Exception:
                    pass
                # Include defense stats if any are non-zero
                defStats = p.gameStatsDict.get('defense', {})
                if any(v > 0 for v in defStats.values() if isinstance(v, (int, float))):
                    result['defense'] = dict(defStats)
                return result

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

    def _resolvePersonalityTrigger(self):
        """
        Inspect self.play and decide which (player, eventKey) should fire a
        Layer 1 personality line, if any. Returns (player, eventKey) or None.
        Defensive players are eligible on turnovers/sacks: half the time the
        reaction comes from the defender who made the play.
        """
        play = self.play
        if play is None:
            return None

        def _pickPassSkill():
            """On a pass play, 50/50 split between receiver and passer so QBs
            also get positive reactions on TDs / big gains / 3rd down converts."""
            candidates = [p for p in (play.receiver, play.passer) if p is not None]
            if not candidates:
                return None
            return batched_choice(candidates)

        # Touchdowns — highest priority
        if getattr(play, 'isTd', False):
            if getattr(play, 'isPassCompletion', False):
                featured = _pickPassSkill()
                if featured is not None:
                    return (featured, 'td_scored')
            if play.runner is not None:
                return (play.runner, 'td_scored')
            return None

        # Safety — 50/50 between offense (safety_taken) and defender (safety_made).
        # Checked before sack/run because a sack-safety has both flags set.
        if getattr(play, 'isSafety', False):
            sacker = getattr(play, 'sackedBy', None)
            if sacker is not None and batched_random() < 0.50:
                return (sacker, 'safety_made')
            if play.passer is not None:
                return (play.passer, 'safety_taken')
            if play.runner is not None:
                return (play.runner, 'safety_taken')

        # Interception — 50/50 between QB (int_thrown) and defender (int_made)
        if getattr(play, 'isInterception', False):
            interceptor = getattr(play, 'interceptedBy', None)
            if interceptor is not None and batched_random() < 0.50:
                return (interceptor, 'int_made')
            if play.passer is not None:
                return (play.passer, 'int_thrown')

        # Fumble lost — 50/50 between fumbler (offense) and forcer (defense, if any)
        if getattr(play, 'isFumbleLost', False):
            forcer = getattr(play, 'forcedFumbleBy', None)
            if forcer is not None and batched_random() < 0.50:
                return (forcer, 'fumble_recovered')
            if play.runner is not None:
                return (play.runner, 'fumble_lost')
            if play.passer is not None:
                return (play.passer, 'fumble_lost')

        # Sack — 50/50 between QB (sack_taken) and defender (sack_made)
        if getattr(play, 'isSack', False):
            sacker = getattr(play, 'sackedBy', None)
            if sacker is not None and batched_random() < 0.50:
                return (sacker, 'sack_made')
            if play.passer is not None:
                return (play.passer, 'sack_taken')

        # Field goal made/missed
        if getattr(play, 'fgDistance', 0) and play.kicker is not None:
            if getattr(play, 'isFgGood', False):
                return (play.kicker, 'fg_made')
            return (play.kicker, 'fg_missed')

        # Turnover on downs — failed 4th-down attempt (run/pass, not FG)
        playResult = getattr(play, 'playResult', None)
        if getattr(playResult, 'value', None) == 'Turnover On Downs':
            if getattr(play, 'isPassCompletion', False) or play.passer is not None:
                featured = _pickPassSkill()
                if featured is not None:
                    return (featured, 'turnover_on_downs')
            if play.runner is not None:
                return (play.runner, 'turnover_on_downs')

        preDown = getattr(play, 'down', 0)
        yardage = getattr(play, 'yardage', 0)
        yardsTo1st = getattr(play, 'yardsTo1st', None)

        # Clutch play — high-leverage moment that flipped the win prob
        if getattr(play, 'isClutchPlay', False) and not getattr(play, 'isTd', False):
            if getattr(play, 'isPassCompletion', False):
                featured = _pickPassSkill()
                if featured is not None:
                    return (featured, 'clutch_play')
            if play.runner is not None:
                return (play.runner, 'clutch_play')

        # Big play — flagged by WPA swing (>=10), not just raw yardage
        if getattr(play, 'isBigPlay', False) and not getattr(play, 'isTd', False):
            if getattr(play, 'isPassCompletion', False):
                featured = _pickPassSkill()
                if featured is not None:
                    return (featured, 'big_gain')
            if play.runner is not None:
                return (play.runner, 'big_gain')

        # Third down conversion (lower priority than big/clutch above)
        if preDown == 3 and isinstance(yardsTo1st, (int, float)) and yardage >= yardsTo1st and yardage > 0:
            if getattr(play, 'isPassCompletion', False):
                featured = _pickPassSkill()
                if featured is not None:
                    return (featured, 'third_down_conversion')
            if play.runner is not None:
                return (play.runner, 'third_down_conversion')

        return None

    def _buildPersonalityEvent(self):
        """
        Personality reaction firing hook. Called from broadcastGameState.
        Returns a dict shaped for the WebSocket game feed, or None if no
        line fires this play. Frequency-gated to target ~3-5 per game.
        """
        if self.personalityManager is None:
            return None

        trigger = self._resolvePersonalityTrigger()
        if trigger is None:
            return None
        player, eventKey = trigger
        if player is None:
            return None

        attrs = getattr(player, 'attributes', None)
        if not attrs or not getattr(attrs, 'personality', None):
            return None

        # Gating — scoring plays, turnovers, sacks, and big plays ALWAYS fire.
        # Third-down conversions are frequent so they fire at a lower rate.
        alwaysFire = eventKey in (
            'td_scored', 'int_thrown', 'int_made', 'fumble_lost',
            'fumble_recovered', 'fg_made', 'fg_missed',
            'sack_taken', 'sack_made', 'big_gain', 'clutch_play',
            'turnover_on_downs', 'safety_taken', 'safety_made',
        )
        if not alwaysFire:
            # third_down_conversion
            if batched_random() > 0.20:
                return None

        # Token context for {name}, {receiver}, {passer} etc. placeholders
        try:
            playerTeam = getattr(player, 'team', None)
            oppTeam = self.awayTeam if playerTeam is self.homeTeam else self.homeTeam
            oppAbbr = getattr(oppTeam, 'abbr', '') if oppTeam else ''
        except Exception:
            oppAbbr = ''

        tokens = {
            'name': getattr(player, 'name', ''),
            'oppTeam': oppAbbr,
            'yards': getattr(self.play, 'yardage', 0),
            'quarter': self.currentQuarter,
            'score': f"{self.homeScore}-{self.awayScore}",
        }

        eventDict = self.personalityManager.composeReaction(player, eventKey, tokens)
        if eventDict is None:
            return None

        # Attach to the play object so it persists in gameFeed references too
        try:
            self.play.personalityEvent = eventDict
        except Exception:
            pass
        return eventDict

    def _buildPostgameReactions(self):
        """Pick a few players from each team and fire polarity-flavored
        postgame reactions: positive for the winner, negative for the loser.
        Inserted into gameFeed as cutaway-style entries (top of feed, since
        they happen at the very end of the game)."""
        if self.personalityManager is None:
            return
        if self.winningTeam is None or self.losingTeam is None:
            return  # tie or unresolved — skip

        from random import sample as _sample

        def _eligible(team):
            roster = getattr(team, 'rosterDict', None) or {}
            out = []
            for p in roster.values():
                if not p:
                    continue
                attrs = getattr(p, 'attributes', None)
                if attrs and getattr(attrs, 'personality', None):
                    out.append(p)
            return out

        for team, polarity in ((self.winningTeam, 'positive'), (self.losingTeam, 'negative')):
            pool = _eligible(team)
            if not pool:
                continue
            picks = _sample(pool, min(3, len(pool)))
            for player in picks:
                eventDict = self.personalityManager.composePolarityReaction(
                    player, polarity,
                    ctx={'score': f"{self.homeScore}-{self.awayScore}"},
                )
                if eventDict is None:
                    continue
                eventDict['trigger'] = 'postgame'
                # Use cutaway-shaped feed entry so the existing renderer picks
                # it up and shows the team avatar + accent border.
                self.gameFeed.insert(0, {'play': {
                    'isSidelineCutaway': True,
                    'sidelineCutaway': eventDict,
                    'playNumber': self.totalPlays + 0.9,
                    'quarter': self.currentQuarter,
                    'timeRemaining': '0:00',
                }})

    def _buildSidelineCutaway(self, triggerType: str = 'downtime'):
        """
        Build a sideline-cutaway event for downtime moments — possession
        changes, quarter starts, halftime, two-minute warning. Picks a random
        eligible player from either team and asks the personality manager
        to render their sideline pool (variant) or generic pool (base).

        Returns a dict shaped like personalityEvent (with text/playerId/etc.)
        or None if no cutaway fires this broadcast.
        """
        if self.personalityManager is None:
            return None
        # Per-game cap — keeps an upper bound but allows ~2x the prior rate.
        if self._sidelineCutawaysFired >= 24:
            return None
        # Probabilistic gate — fires on most eligible downtime broadcasts.
        if batched_random() > 0.80:
            return None

        # Pool candidate players from both teams. Only include those whose
        # personality has a `sideline:` pool — base vibes that fall back to
        # play-reaction generics are excluded so cutaways stay distinctive.
        engine = getattr(self.personalityManager, 'engine', None)
        candidates = []
        for team in (self.homeTeam, self.awayTeam):
            roster = getattr(team, 'rosterDict', None) or {}
            for p in roster.values():
                if not p:
                    continue
                attrs = getattr(p, 'attributes', None)
                personality = attrs and getattr(attrs, 'personality', None)
                if not personality:
                    continue
                if engine and not engine.hasSidelinePool(personality):
                    continue
                candidates.append(p)
        if not candidates:
            return None

        from random import choice as _choice
        player = _choice(candidates)
        ctx = {
            'name': getattr(player, 'name', ''),
            'quarter': self.currentQuarter,
            'score': f"{self.homeScore}-{self.awayScore}",
        }
        eventDict = self.personalityManager.pickSidelineCutaway(player, ctx)
        if eventDict is None:
            return None
        eventDict['trigger'] = triggerType
        self._sidelineCutawaysFired += 1
        return eventDict

    def _resolvePlayWpa(self):
        """Compute win-probability + WPA for the just-resolved play, store it on the
        play, fire the WPA-derived momentum/clutch effects, attribute the WPA to the
        players involved, and advance the WP baseline. Runs ONCE per play, BEFORE the
        broadcast early-returns, so WPA + player attribution are independent of timing
        mode (TURBO / silent modes previously skipped this). Idempotent per play.
        Returns (newHomeWp, newAwayWp, homeWpa, awayWpa)."""
        if getattr(self.play, '_wpaResolved', False):
            return (self.homeTeamWinProbability, self.awayTeamWinProbability,
                    getattr(self.play, 'homeWpa', 0.0), getattr(self.play, 'awayWpa', 0.0))

        winProb = self.calculateWinProbability()
        newHomeWp = winProb['home']
        newAwayWp = winProb['away']
        homeWpa = float(newHomeWp - self.previousHomeWinProbability)
        awayWpa = float(newAwayWp - self.previousAwayWinProbability)

        # Persist WP/WPA on the play (gameFeed holds the play by reference)
        self.play.homeWinProbability = newHomeWp
        self.play.awayWinProbability = newAwayWp
        self.play.homeWpa = round(homeWpa, 2)
        self.play.awayWpa = round(awayWpa, 2)
        self.play.isBigPlay = bool(abs(homeWpa) >= 7.0 or abs(awayWpa) >= 7.0)

        # Momentum: big-play bonus to the team that benefited from the swing
        if self.play.isBigPlay:
            benefitingTeam = self.homeTeam if homeWpa > 0 else self.awayTeam
            self._applyMomentumEvent(MOMENTUM_BIG_PLAY_BONUS, benefitingTeam)

        # Keep clutch/choke tags only if the play had meaningful WP impact
        wpImpact = max(abs(homeWpa), abs(awayWpa))
        if self.play.isClutchPlay and wpImpact < CLUTCH_WPA_THRESHOLD:
            self.play.isClutchPlay = False
        if self.play.isChokePlay and wpImpact < CHOKE_WPA_THRESHOLD:
            self.play.isChokePlay = False

        # Attribute this play's WP swing to the players involved (offense + defense unit)
        try:
            self._attributeWpa(self.play, homeWpa, awayWpa)
        except Exception as e:
            logging.debug(f"WPA attribution skipped on play {getattr(self.play, 'playNumber', '?')}: {e}")

        # Advance the WP baseline (next play's delta + API display). Events between
        # plays do NOT call this, so the next play's WPA is measured from this play's
        # WP, not from intervening clock/possession drift.
        self.homeTeamWinProbability = newHomeWp
        self.awayTeamWinProbability = newAwayWp
        self.previousHomeWinProbability = newHomeWp
        self.previousAwayWinProbability = newAwayWp
        self.play._wpaResolved = True
        return (newHomeWp, newAwayWp, homeWpa, awayWpa)

    def _attributeWpa(self, play, homeWpa, awayWpa):
        """Credit this play's win-probability swing to the players involved and
        accumulate it onto in-memory season totals (offense: `seasonWpa`/`wpaSnaps`;
        defense: `seasonDefWpa`/`defWpaSnaps`). Persistence is wired in a later phase.
        See docs/WPA_MVP_PLAN.md for the attribution table."""
        offense = getattr(play, 'offense', None) or self.offensiveTeam
        defense = getattr(play, 'defense', None) or self.defensiveTeam
        if offense is None:
            return
        # Signed WPA from the offense's perspective (zero-sum: defense gets the mirror)
        offenseWpa = homeWpa if offense is self.homeTeam else awayWpa

        def creditOff(pl, amt):
            if pl is None:
                return
            # Per-game accumulators; rolled into the season total + persisted at
            # postgame (mirrors _lastGameFantasyPoints). Reset each game.
            pl._gameWpa = float(getattr(pl, '_gameWpa', 0.0)) + amt
            pl._gameWpaSnaps = int(getattr(pl, '_gameWpaSnaps', 0)) + 1

        pt = getattr(play, 'playType', None)
        # ── Offense ──
        if pt is PlayType.Run:
            creditOff(getattr(play, 'runner', None), offenseWpa)
        elif pt is PlayType.Pass:
            if getattr(play, 'isPassCompletion', False) and getattr(play, 'receiver', None) is not None:
                creditOff(getattr(play, 'passer', None), offenseWpa * WPA_PASS_QB_SHARE)
                creditOff(play.receiver, offenseWpa * (1.0 - WPA_PASS_QB_SHARE))
            else:
                # incompletion / sack / throwaway → all on the QB
                creditOff(getattr(play, 'passer', None), offenseWpa)
        elif pt in (PlayType.FieldGoal, PlayType.ExtraPoint):
            creditOff(getattr(play, 'kicker', None), offenseWpa)
        # Punt / Spike / Kneel / penalty: no single offensive actor — uncredited.

        # ── Defense — scrimmage downs only ──
        # Attribute the play's defensive swing to the PLAYER WHO MADE THE PLAY (the
        # returner / sacker / interceptor / forced-fumbler / primary tackler), the
        # same way offense credits the ball-handler — NOT split across the unit.
        # Unit-sharing clustered the MVP ballot (every defender on a good-defense
        # team inherited the swing regardless of individual production); per-player
        # attribution doesn't. Every on-field defender still logs a SNAP so the
        # "played defense" eligibility gate holds; only the playmaker banks the WPA.
        # (A pass with no tackle and no turnover leaves the swing uncredited —
        # per-defender coverage on an incompletion isn't tracked yet; box INT/PBU
        # stats still capture coverage value.)
        if pt in (PlayType.Run, PlayType.Pass) and defense is not None:
            defWpa = -offenseWpa
            defenders = [p for p in defense.rosterDict.values()
                         if p is not None and getattr(p, 'defensivePosition', None) is not None]
            playMaker = (getattr(play, 'returner', None) or getattr(play, 'sackedBy', None)
                         or getattr(play, 'interceptedBy', None)
                         or getattr(play, 'forcedFumbleBy', None) or getattr(play, 'tackledBy', None))
            if playMaker is not None and getattr(playMaker, 'defensivePosition', None) is not None:
                playMaker._gameDefWpa = float(getattr(playMaker, '_gameDefWpa', 0.0)) + defWpa
            for d in defenders:
                d._gameDefWpaSnaps = int(getattr(d, '_gameDefWpaSnaps', 0)) + 1

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
        # Layer 1 personality events fire regardless of broadcast availability
        # so they persist on the Play object (and in gameFeed references) even
        # when no WebSocket clients are connected.
        if includeLastPlay and hasattr(self, 'play') and self.play and eventMessage is None:
            self._buildPersonalityEvent()

        # Resolve WP + WPA + player attribution BEFORE the broadcast early-returns, so
        # they run on every play regardless of timing mode (TURBO / silent previously
        # skipped them). Real-play broadcasts only — standalone event broadcasts keep
        # the last play's WP and contribute no WPA.
        isRealPlay = includeLastPlay and hasattr(self, 'play') and self.play and eventMessage is None
        if isRealPlay:
            newHomeWp, newAwayWp, homeWpa, awayWpa = self._resolvePlayWpa()
        else:
            newHomeWp = self.homeTeamWinProbability
            newAwayWp = self.awayTeamWinProbability
            homeWpa = 0.0
            awayWpa = 0.0

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

        # (WP/WPA computed above in _resolvePlayWpa for real plays; newHomeWp/newAwayWp/
        # homeWpa/awayWpa are already set.)

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
        finalPlayData = None  # Carries the actual final play alongside the "Final" event
        if eventMessage:
            # Use event message instead of play data
            lastPlayData = eventMessage
            # For final broadcasts, also include the actual last play so the frontend
            # always gets it (even if the earlier per-play broadcast didn't arrive).
            if isFinalBroadcast and includeLastPlay and hasattr(self, 'play') and self.play:
                playObj = self.play
                finalPlayData = {
                    'playNumber': self.totalPlays,
                    'quarter': getattr(playObj, 'quarter', self.currentQuarter),
                    'timeRemaining': getattr(playObj, 'timeRemaining', self.formatTime(self.gameClockSeconds)),
                    'down': getattr(playObj, 'down', self.down),
                    'distance': getattr(playObj, 'yardsTo1st', self.yardsToFirstDown),
                    'yardLine': getattr(playObj, 'yardLine', self.yardLine),
                    'playType': playObj.playType.name if hasattr(playObj, 'playType') and hasattr(playObj.playType, 'name') else 'Unknown',
                    'yardsGained': getattr(playObj, 'yardage', 0),
                    'description': getattr(playObj, 'playText', ''),
                    'playResult': playObj.playResult.value if hasattr(playObj, 'playResult') and playObj.playResult else None,
                    'isTouchdown': getattr(playObj, 'isTd', False),
                    'isTurnover': (getattr(playObj, 'isFumbleLost', False) or getattr(playObj, 'isInterception', False)),
                    'isSack': getattr(playObj, 'isSack', False),
                    'scoreChange': getattr(playObj, 'scoreChange', False),
                    'homeTeamScore': getattr(playObj, 'homeTeamScore', None),
                    'awayTeamScore': getattr(playObj, 'awayTeamScore', None),
                    'offensiveTeam': playObj.offense.abbr if hasattr(playObj, 'offense') else self.offensiveTeam.abbr,
                    'defensiveTeam': playObj.defense.abbr if hasattr(playObj, 'defense') else self.defensiveTeam.abbr,
                    'homeWpa': getattr(playObj, 'homeWpa', 0),
                    'awayWpa': getattr(playObj, 'awayWpa', 0),
                    'isBigPlay': getattr(playObj, 'isBigPlay', False),
                    'isClutchPlay': getattr(playObj, 'isClutchPlay', False),
                    'isChokePlay': getattr(playObj, 'isChokePlay', False),
                    'isMomentumShift': getattr(playObj, 'isMomentumShift', False),
                    'clockStopped': getattr(playObj, 'clockStopped', False),
                    'clutchPerformers': list(getattr(playObj, 'clutchPerformers', []) or []),
                    'chokePerformers': list(getattr(playObj, 'chokePerformers', []) or []),
                    'insights': getattr(playObj, 'insights', None),
                }
        elif includeLastPlay and hasattr(self, 'play') and self.play:
            # WP/WPA, the momentum big-play bonus, and the clutch/choke WP-impact
            # filter were already applied in _resolvePlayWpa() above (runs in all
            # timing modes). The play already carries homeWpa/awayWpa/isBigPlay; just
            # build the broadcast payload here.
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
                # Anomaly attachments — null when no glitch fired on
                # this play. When present, the frontend should render
                # glitchText distinctly (italic, dim) below playText.
                'glitchText': getattr(self.play, 'glitchText', None),
                'glitchPlayerId': getattr(self.play, 'glitchPlayerId', None),
                'glitchPlayerName': getattr(self.play, 'glitchPlayerName', None),
                'glitchLayer': getattr(self.play, 'glitchLayer', None),
                'glitchYardDelta': getattr(self.play, 'glitchYardDelta', None),
                # Participant IDs — used by the frontend highlights feed
                # to filter "plays involving players the user cares
                # about." Null when the role didn't apply to this play.
                'passerId':   getattr(getattr(self.play, 'passer', None),   'id', None),
                'receiverId': getattr(getattr(self.play, 'receiver', None), 'id', None),
                'runnerId':   getattr(getattr(self.play, 'runner', None),   'id', None),
                'kickerId':   getattr(getattr(self.play, 'kicker', None),   'id', None),
                'tacklerId':       getattr(getattr(self.play, 'tackledBy', None),       'id', None),
                'sackerId':        getattr(getattr(self.play, 'sackedBy', None),        'id', None),
                'interceptorId':   getattr(getattr(self.play, 'interceptedBy', None),   'id', None),
                'forcedFumblerId': getattr(getattr(self.play, 'forcedFumbleBy', None),  'id', None),
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
                'clockStopped': getattr(self.play, 'clockStopped', False),
                'clutchPerformers': list(getattr(self.play, 'clutchPerformers', []) or []),
                'chokePerformers': list(getattr(self.play, 'chokePerformers', []) or []),
                'insights': getattr(self.play, 'insights', None),
                'personalityEvent': self._buildPersonalityEvent(),
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
            'finalPlay': finalPlayData,
            'homeWinProbability': round(newHomeWp, 1),
            'awayWinProbability': round(newAwayWp, 1),
            'homeWpa': round(homeWpa, 2),
            'awayWpa': round(awayWpa, 2),
            'isHalftime': getattr(self, 'isHalftime', False),
            'isFloosBowl': getattr(self, 'isFloosBowl', False),
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

        # Sideline cutaway — fire on downtime moments (possession changes,
        # halftime, quarter starts, two-minute warning). Probabilistic so
        # not every transition produces one.
        isDowntime = isPossessionChange or eventMessage is not None or getattr(self, 'isHalftime', False)
        if isDowntime and not isFinalBroadcast:
            triggerType = 'possession_change' if isPossessionChange else (
                'event' if eventMessage else 'halftime'
            )
            cutaway = self._buildSidelineCutaway(triggerType)
            if cutaway:
                gameStateData['sidelineCutaway'] = cutaway
                # Also persist to gameFeed so /api/games/{id} returns cutaways
                # for users who weren't watching live (game modal open).
                self.gameFeed.insert(0, {'play': {
                    'isSidelineCutaway': True,
                    'sidelineCutaway': cutaway,
                    'playNumber': self.totalPlays + 0.5,
                    'quarter': self.currentQuarter,
                    'timeRemaining': self.formatTime(self.gameClockSeconds),
                }})

        # Create and broadcast event
        event = GameEvent.gameState(gameId=self.id, gameState=gameStateData)
        broadcaster.broadcast_sync(self.id, event)

        # (WP baseline already advanced in _resolvePlayWpa for real plays; event
        # broadcasts intentionally do not advance it, so the next play's WPA is
        # measured from the prior play rather than from intervening clock drift.)

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
                self.gameFeed[0]['isBigPlay'] = bool(abs(homeWpa) >= 7.0 or abs(awayWpa) >= 7.0)
                self.gameFeed[0]['isClutchPlay'] = getattr(self.play, 'isClutchPlay', False)
                self.gameFeed[0]['isChokePlay'] = getattr(self.play, 'isChokePlay', False)
                self.gameFeed[0]['isMomentumShift'] = getattr(self.play, 'isMomentumShift', False)

    def _classifyTempoIntent(self) -> tuple:
        """
        Classify the offense's intent for the current play given score/time.
        Returns (intent, baseTime) where intent is 'hurryUp' | 'burnClock' |
        'neutral'. Used both for the actual pre-snap clock burn (when the
        clock is running) and to surface the intent on every play in the
        feed — so a stopped-clock play still shows whether the offense is
        in hurry-up mode.
        """
        DEFAULT_BASE = 35

        if self.offensiveTeam == self.homeTeam:
            scoreDiff = self.homeScore - self.awayScore
        else:
            scoreDiff = self.awayScore - self.homeScore

        secs = self.gameClockSeconds
        q = self.currentQuarter
        garbageTime = self._isGarbageTime(scoreDiff)

        # Setting up an end-of-game FG: drain ONLY when the play just chosen
        # is the FG kick itself in a tight game. We want the clock to die on
        # this snap. Earlier productive plays in the same drive use hurry-up
        # tempo so the offense maximises chances at a TD before settling for
        # the kick. iqOffset in calculatePreSnapTime tightens or loosens the
        # FG-snap target per coach.
        if (self._isFgDrainMode() and hasattr(self, 'play') and self.play is not None
                and getattr(self.play, 'playType', None) == PlayType.FieldGoal):
            target = 7
            return ('setupFG', max(8, secs - target))

        if (q >= 4) and secs <= self.gameRules.timeoutClockThreshold and scoreDiff <= 0 and not garbageTime:
            return ('hurryUp', 12)  # Q4/OT trailing or tied under 2:00
        if q == 2 and secs <= self.gameRules.timeoutClockThreshold and scoreDiff <= 0:
            return ('hurryUp', 15)  # End-of-half trailing or tied
        if q >= 3 and secs <= 300 and scoreDiff < 0 and not garbageTime:
            return ('hurryUp', 15 if scoreDiff <= -8 else 25)  # Mid-late deficit
        # Burn-clock only kicks in late Q3 / Q4 onward. The clock resets to
        # 900s each quarter, so without a quarter gate a team up 8+ in Q1
        # at 4:30 would wrongly enter burn-clock mode.
        if q == 3 and secs <= 300 and scoreDiff > 14:
            return ('burnClock', 40)  # Late Q3 with two-score lead
        if q >= 4 and scoreDiff > 8:
            return ('burnClock', 40)  # Q4/OT comfortable lead
        if q >= 4 and scoreDiff > 0 and secs <= 300:
            return ('burnClock', 38)  # Q4/OT any lead inside 5:00 — protect it
        return ('neutral', DEFAULT_BASE)

    def recordTempoIntent(self) -> None:
        """Stamp the offense's tempo intent on the current play's insights so
        every play (including kneels, spikes, and clock-stopped scenarios)
        carries the intent. calculatePreSnapTime augments this with iqOffset
        / finalSeconds when the clock is actually running.
        """
        if not hasattr(self, 'play') or self.play is None:
            return
        intent, baseTime = self._classifyTempoIntent()
        coach = getattr(self.offensiveTeam, 'coach', None)
        self.play.insights['tempo'] = {
            'intent': intent,
            'baseTime': baseTime,
            'coachClockIQ': round(self._coachClockIQ(coach), 2),
        }

    def calculatePreSnapTime(self) -> int:
        """
        Calculate time consumed before snap (huddle, line up, snap count).
        Adjusts based on game situation AND the offensive coach's
        clockManagement attribute. A great clock manager (gameIQ ~1.0) snaps
        a few seconds faster in hurry-up situations and burns a few extra
        seconds when bleeding the clock; a poor one (gameIQ ~0.0) leaks time
        when trying to score and gives seconds back when leading.

        Always called after recordTempoIntent has stamped the intent, so this
        method just augments the existing insight with the time math.
        """
        intent, baseTime = self._classifyTempoIntent()
        coach = getattr(self.offensiveTeam, 'coach', None)
        gameIQ = self._coachClockIQ(coach)

        # Coach IQ modifier:
        #   hurryUp:    high IQ snaps faster (negative offset)
        #   burnClock:  high IQ uses more of the play clock (positive offset)
        #   neutral:    coach makes no measurable difference at default tempo
        # Spread is ±3 sec across the IQ range (0.0 → ±3, 1.0 → ∓3, 0.5 → 0).
        if intent == 'hurryUp':
            iqOffset = round(-6 * (gameIQ - 0.5))
        elif intent == 'burnClock':
            iqOffset = round(6 * (gameIQ - 0.5))
        elif intent == 'setupFG':
            # Smart coaches drain precisely (more time consumed, snap closer
            # to the FG-snap target). Dumb coaches under-drain — they leave
            # the opponent more time after the kick.
            iqOffset = round(4 * (gameIQ - 0.5))
        else:
            iqOffset = 0

        finalTime = max(8, baseTime + iqOffset + batched_randint(-3, 3))

        # Augment the tempo insight with the time math (recordTempoIntent
        # already set intent / baseTime / coachClockIQ).
        if hasattr(self, 'play') and self.play is not None and 'tempo' in self.play.insights:
            self.play.insights['tempo']['iqOffset'] = iqOffset
            self.play.insights['tempo']['finalSeconds'] = finalTime

        return finalTime
    
    def calculatePlayDuration(self, playType: PlayType, isInBounds: bool = True) -> int:
        """
        Calculate time consumed during play execution (snap to whistle only).
        Only game-clock time: if the play stops the clock, we only count the
        seconds the ball was actually live.
        """
        if playType == PlayType.Run:
            return batched_randint(4, 6)

        elif playType == PlayType.Pass:
            # Hail mary: deep heave with long hang time
            if getattr(self.play, 'passType', None) is PassType.hailMary:
                return batched_randint(8, 12)
            if self.play.isPassCompletion and isInBounds:
                return batched_randint(4, 7)  # Completion in bounds — catch + tackle
            elif self.play.isPassCompletion and not isInBounds:
                return batched_randint(3, 5)  # Catch near sideline, clock stops
            elif self.play.isSack:
                return batched_randint(3, 5)  # Sack, clock runs
            else:  # Incomplete
                return batched_randint(2, 4)  # Ball in air + hit ground, clock stops

        elif playType == PlayType.FieldGoal or playType == PlayType.Punt:
            return batched_randint(4, 6)  # Snap + kick

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
        self.yardsToSafety = self.gameRules.fieldLength - 2
        self.down = 1
        self.yardsToFirstDown = 2

        self.play = Play(self)
        # Give the conversion its own play number so it has a stable identity
        # separate from the touchdown that preceded it. Without this the Play
        # object has no playNumber attribute, which serializes as 0 and can
        # collide with other 2-pt conversions (or missing-playNumber plays)
        # in the REST response and frontend React keys.
        self.totalPlays += 1
        self.play.playNumber = self.totalPlays

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
        # Defensive: only insert if this Play object isn't already at the top
        # of the feed. Guards against any unexpected double-invocation path.
        alreadyInFeed = bool(self.gameFeed) and self.gameFeed[0].get('play') is self.play
        if not alreadyInFeed:
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

    def _simulateExtraPointPlay(self, scoringTeam: 'FloosTeam.Team',
                                opposingTeam: 'FloosTeam.Team',
                                trackPtsAllowed: bool = True) -> bool:
        """
        Simulate a PAT kick as a separate, no-time play immediately following a TD.
        Mirrors _simulate2PointConversionPlay so the XP appears as its own entry
        in the play-by-play feed instead of being smushed onto the TD play.
        Returns True if the kick was good.

        trackPtsAllowed: when True, opposingTeam.gameDefenseStats['ptsAlwd'] is
        bumped on a successful kick. Set False for defensive TDs (pick-six,
        scoop-and-score) where the team that "lost" the ball was on offense
        and shouldn't accrue points-allowed for the PAT either way.
        """
        # Save game state
        savedOffensive = self.offensiveTeam
        savedDefensive = self.defensiveTeam
        savedYardsToEndzone = self.yardsToEndzone
        savedYardsToSafety = self.yardsToSafety
        savedDown = self.down
        savedYardsToFirstDown = self.yardsToFirstDown

        # PAT kicks from the 15-yard line. Set field state before snapshotting
        # so any consumer reading play.yardsToEndzone sees the right context.
        self.offensiveTeam = scoringTeam
        self.defensiveTeam = opposingTeam
        self.yardsToEndzone = 15
        self.yardsToSafety = self.gameRules.fieldLength - 15
        self.down = 1
        self.yardsToFirstDown = 15

        self.play = Play(self)
        # Stable identity separate from the touchdown — same reasoning as
        # the 2-pt path; React keys + REST serialization need a unique
        # playNumber per feed entry.
        self.totalPlays += 1
        self.play.playNumber = self.totalPlays
        self.play.playType = PlayType.ExtraPoint

        self.play.extraPointTry(scoringTeam)
        if self.play.isXpGood:
            self._addScore(scoringTeam, 1)
            self.play.playResult = PlayResult.ExtraPointGood
            self.play.scoreChange = True
            if trackPtsAllowed:
                opposingTeam.gameDefenseStats['ptsAlwd'] += 1
        else:
            self.play.playResult = PlayResult.ExtraPointNoGood
            self.play.scoreChange = False

        self.play.homeTeamScore = self.homeScore
        self.play.awayTeamScore = self.awayScore

        # XP is a no-time play — clock is always stopped. formatPlayText
        # snapshots clockStopped from self.clockRunning, but during the
        # XP simulation that flag still reflects the prior play's clock
        # state. Force clockRunning False before the snapshot so the feed
        # indicator reads correctly.
        savedClockRunning = self.clockRunning
        self.clockRunning = False
        self.formatPlayText()
        self.clockRunning = savedClockRunning

        alreadyInFeed = bool(self.gameFeed) and self.gameFeed[0].get('play') is self.play
        if not alreadyInFeed:
            self.gameFeed.insert(0, {'play': self.play})
        self.broadcastGameState(includeLastPlay=True)

        # Restore game state
        self.offensiveTeam = savedOffensive
        self.defensiveTeam = savedDefensive
        self.yardsToEndzone = savedYardsToEndzone
        self.yardsToSafety = savedYardsToSafety
        self.down = savedDown
        self.yardsToFirstDown = savedYardsToFirstDown

        return self.play.isXpGood

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
        if not self.twoMinuteWarningShown and self.gameClockSeconds <= self.gameRules.timeoutClockThreshold:
            if self.currentQuarter == 2 or self.currentQuarter == 4:
                self.twoMinuteWarningShown = True
                self.clockRunning = False
                self._clockStoppedByWarning = True
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
    
    def advanceQuarter(self):
        """Transition to next quarter"""
        if self.currentQuarter == 1:
            self.currentQuarter = 2
            self.gameClockSeconds = self.gameRules.quarterLengthSeconds
            self.twoMinuteWarningShown = False
        elif self.currentQuarter == 2:
            # Halftime
            self.currentQuarter = 3
            self.gameClockSeconds = self.gameRules.quarterLengthSeconds
            self.isHalftime = False
            # Reset timeouts for second half
            self.homeTimeoutsRemaining = 3
            self.awayTimeoutsRemaining = 3
            self.twoMinuteWarningShown = False
        elif self.currentQuarter == 3:
            self.currentQuarter = 4
            self.gameClockSeconds = self.gameRules.quarterLengthSeconds
            self.twoMinuteWarningShown = False
        elif self.currentQuarter == 4:
            # Check for overtime
            if self.homeScore == self.awayScore:
                self.currentQuarter = 5
                self.gameClockSeconds = self.gameRules.overtimeLengthSeconds  # 10 minute OT
                self.isOvertime = True
                self.twoMinuteWarningShown = False
                self.homeTimeoutsRemaining = 2
                self.awayTimeoutsRemaining = 2
                self.otPeriod = 1
            # else game is over
        elif self.currentQuarter >= 5:
            # Additional OT periods - reset clock if game is still tied
            if self.homeScore == self.awayScore:
                self.otPeriod += 1
                self.gameClockSeconds = self.gameRules.overtimeLengthSeconds  # Another 10 minute OT period
                self.twoMinuteWarningShown = False
                self.homeTimeoutsRemaining = 2
                self.awayTimeoutsRemaining = 2
                # 2nd+ OT is sudden death — no possession reset needed
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
            # Both teams finished their guaranteed possession and someone leads
            if self.homeScore != self.awayScore and self.otSecondPossComplete:
                return True
            # Clock expired during the trailing team's guaranteed possession:
            # the first team already scored (otFirstPossComplete) and the
            # second team ran out of time without tying or taking the lead.
            # Their possession is effectively over — game is over. Without
            # this check, isGameOver stayed False and the main loop printed
            # "Start Additional Overtime Period" + coin-toss messages
            # repeatedly until a subsequent turnover happened to flip
            # otSecondPossComplete.
            if (self.gameClockSeconds <= 0
                    and self.homeScore != self.awayScore
                    and self.otFirstPossComplete):
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
        if self.currentQuarter <= 0:
            total_seconds = 3600  # Pre-game: full game remaining
        elif self.currentQuarter == 1:
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
        # Overtime is past regulation: force full progress so the ELO prior floors
        # (eloWeight → 0.05) and the score logistic maxes (k → ~0.40). Without this
        # the regulation 3600s math leaves gameProgress ~0.83 in OT, leaking a ~21%
        # ELO prior into the implicit-else OT path (first team scored, second
        # responding). total_seconds stays = OT clock remaining for the EP/possession math.
        if self.currentQuarter >= 5:
            gameProgress = 1.0

        # ELO weight: 1.0 pre-game (pure ELO baseline), decays smoothly to 0.05 by end
        # Stays meaningful through the first half, minor effect in Q4
        eloWeight = max(0.05, 1.0 - gameProgress * 0.95)

        # Score differential from home team's perspective
        scoreDiff = self.homeScore - self.awayScore

        # Expected PAT: when a TD just hit the books, the WP should already
        # anticipate the kick attempt that's about to follow. Without this,
        # a missed XP shows zero WPA (score doesn't change between the +6
        # TD and the missed XP). Bake in the league-avg XP success rate
        # (~0.95) so a missed XP correctly registers as a small negative
        # WPA correction. The scoring team is the one whose score went up
        # on this play (tracked on the play via _addScore).
        currentPlay = getattr(self, 'play', None)
        if (currentPlay is not None
                and getattr(currentPlay, 'isTd', False)
                and getattr(currentPlay, 'scoringTeam', None) is not None):
            expectedPat = 0.95
            if currentPlay.scoringTeam is self.homeTeam:
                scoreDiff += expectedPat
            else:
                scoreDiff -= expectedPat

        # Expected points from current field position
        expectedPoints = self.calculateExpectedPoints()

        # XP attempts run from the 15-yd line with the scoring team listed
        # as offense, but the situation is actually "kicking the PAT, then
        # kickoff to opponent" — the field position is misleading for WP.
        # Zero out the EP swing so the missed-XP / made-XP delta only comes
        # from the score change, not from the inflated goal-line EP.
        currentPlay = getattr(self, 'play', None)
        if currentPlay is not None and getattr(currentPlay, 'playType', None) == PlayType.ExtraPoint:
            expectedPoints = 0

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

        # Late-game possession adjustment: under ~2 minutes in Q4 with a
        # non-tied score, the formula above ignores who has the ball.
        # In reality a leading team with possession can kneel the clock
        # out, and a trailing team without the ball likely never gets it
        # back. Pull WP toward the leader proportionally to how little
        # time (and how few possessions) remain.
        if self.currentQuarter == 4 and scoreDiff != 0 and total_seconds < 120:
            homeLeading = scoreDiff > 0
            leadingTeam = self.homeTeam if homeLeading else self.awayTeam
            leaderHasBall = (self.offensiveTeam == leadingTeam)
            # Confidence ramps as clock drains. Leader-with-ball reaches
            # near-certainty faster; trailing-team-with-ball still has a
            # chance to score but needs time on the clock.
            if leaderHasBall:
                # Leader can kneel out. Confidence scales from ~0 at 120s
                # remaining to ~1 at 0s. Three kneels burn ~120 sec.
                confidence = min(1.0, (120 - total_seconds) / 100.0)
                pull = 0.9 * confidence
            else:
                # Trailing team has the ball. Their odds depend on time
                # plus their field position/EP (already in scoreDiff).
                # Still apply some pull toward the leader because the
                # possession flipping back to them is unlikely.
                confidence = min(1.0, (60 - total_seconds) / 60.0) if total_seconds < 60 else 0.0
                pull = 0.4 * confidence
            if pull > 0:
                targetWp = 99 if homeLeading else 1
                homeWinProb = homeWinProb + (targetWp - homeWinProb) * pull
                awayWinProb = 100 - homeWinProb

        # Overtime win probability — replaces generic formula above
        if self.currentQuarter >= 5:
            # Match checkOvertimeEnd: 2nd+ OT is sudden death outright; 1st OT becomes
            # sudden death once both guaranteed possessions are done.
            isSuddenDeath = self.otPeriod >= 2 or self.otSecondPossComplete
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
                # Estimate FG make probability using the SAME constants as fieldGoalTry()
                # (slope 0.18, skill 0.52 + ×0.85, chip +0.10 under 30, cap 0.96) so OT-tied
                # WP matches the kick the engine will actually roll.
                baseFgProb = 1 / (1 + math.exp(0.18 * (fgDist - 52)))
                kicker = self.offensiveTeam.rosterDict.get('k')
                if kicker:
                    normalizedSkill = (kicker.gameAttributes.overallRating - 50) / 50
                    fgProb = baseFgProb * (0.52 + normalizedSkill * 0.85)
                    if fgDist < 30:
                        fgProb = min(0.96, fgProb + 0.10)
                    fgProb = max(0.05, min(0.96, fgProb))
                else:
                    fgProb = baseFgProb
                # Continuous scoring probability: union of two paths —
                # FG probability (viable when in range, drops smoothly to
                # ~0 outside of kicker range) and drive-TD probability
                # (declines exponentially with yards-to-endzone). Using a
                # smooth function here avoids large WP swings when the
                # offense gains a few yards across an arbitrary threshold.
                tdDriveProb = max(0.02, 0.25 * math.exp(-yte / 40.0))
                scoringProb = (1 - (1 - fgProb) * (1 - tdDriveProb)) * 100

                if isSuddenDeath:
                    # Next score wins outright — scoring prob maps directly to WP
                    offenseWp = max(52, scoringProb)
                else:
                    # First/second possession — both teams will get a drive, so
                    # the current offense's drive position alone shouldn't swing
                    # WP much. Keep the swing tight (~±8% off 50) so the first
                    # OT play doesn't create a massive discontinuous jump from
                    # end-of-regulation 50/50.
                    offenseWp = 50 + (scoringProb - 50) * 0.15

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
        1st OT: both teams must have had a possession before a score can end the game.
        2nd+ OT: sudden death — first score wins."""
        if self.currentQuarter < 5:
            return False
        if self.homeScore == self.awayScore:
            return False

        # 2nd+ OT: sudden death — any score wins immediately
        if self.otPeriod >= 2:
            return True

        # 1st OT: game ends only after both teams have had their guaranteed possession
        if self.otSecondPossComplete:
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
        # Record who scored on this play so calculateWinProbability can
        # bake in expected PAT on TDs (anticipating the upcoming kick
        # makes a missed XP show as a real negative WPA event).
        if hasattr(self, 'play') and self.play is not None:
            self.play.scoringTeam = team
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

    # ── Anomaly system hooks ───────────────────────────────────────────
    # Per-play roll for the user-attention-driven simulation-criticality
    # layer. v1 only fires Layer 1 universal micro-glitches (pure play-
    # text injection, no stat-output changes). Personality-keyed and
    # signature abilities land in follow-up commits.

    def _loadAnomalyAttention(self) -> None:
        """Snapshot every active player's attention score + state for
        this season, plus this game's Criticality multiplier.

        Called lazily on the first play of the game. The snapshot is
        held in memory for the rest of the game — DB churn would be
        prohibitive at per-play frequency.
        """
        try:
            from database.connection import get_session
            from database.models import PlayerAttention, AnomalyState
            from managers.anomalyManager import getCriticalityMultiplier
            session = get_session()
            try:
                attnRows = session.query(PlayerAttention).filter_by(
                    season=self.seasonNumber or 0,
                ).all()
                self._anomalyAttention = {
                    r.player_id: float(r.score) for r in attnRows
                }
                stateRows = session.query(AnomalyState).filter_by(
                    season=self.seasonNumber or 0,
                ).all()
                self._anomalyState = {
                    r.player_id: r.state for r in stateRows
                }
            finally:
                session.close()
            self._criticalityMultiplier = getCriticalityMultiplier(
                self.seasonNumber or 0, self.week or 0,
            )
        except Exception as e:
            # Anomaly system is purely additive — if anything fails,
            # play out the game as if no one had any attention.
            self._anomalyAttention = {}
            self._anomalyState = {}
            self._criticalityMultiplier = 1.0
            try:
                from logger_config import get_logger
                get_logger("floosball.anomaly").debug(
                    f"Anomaly attention load failed: {e}"
                )
            except Exception:
                pass
        self._anomalyAttentionLoaded = True

    def _maybeFireAnomalies(self) -> None:
        """Roll for Layer 1 / Layer 2 cosmetic glitches.

        Pure flavor — no stat or field-state changes. Mechanical impact
        lives in Layer 3 (signature abilities at Awakened state).

        Layer 1 (subtle, generic) can fire on any play, including
        incompletions and sacks — the line reads as "the player
        glitched, and that's why the play resolved the way it did."
        Layer 2 (more pronounced) is gated to plays where the
        candidate's role succeeded — a receiver who actually caught
        it, a tackler who actually tackled. On failed plays at
        higher states, Layer 2 falls back to Layer 1 so the louder
        flavor doesn't get attached to nothing happening.
        """
        if not self._anomalyAttentionLoaded:
            self._loadAnomalyAttention()
        if not self._anomalyAttention:
            return
        p = self.play
        if p is None:
            return
        # If Layer 3 already glitched this play (a real yardage warp), don't
        # stack a cosmetic L1/L2 line on top of it.
        if getattr(p, '_l3Fired', False):
            return
        # Skip deliberate clock kills — nothing to glitch.
        playType = getattr(p, 'playType', None)
        playTypeName = getattr(playType, 'name', None) or str(playType or '')
        if playTypeName in ('Kneel', 'Spike'):
            return

        from constants import (ANOMALY_GLITCH_PROB_SCALE, ANOMALY_GLITCH_PROB_CAP,
                               ANOMALY_GLITCH_MAX_PER_GAME, ANOMALY_GLITCH_COOLDOWN_PLAYS,
                               ANOMALY_L2_WEIGHT_ERRATIC, ANOMALY_L2_WEIGHT_RAMPANT)
        # Per-game hygiene: stop once we've hit the per-game cap, and keep
        # glitches spaced by a cooldown so they never cluster in the feed.
        if self._glitchCountThisGame >= ANOMALY_GLITCH_MAX_PER_GAME:
            return
        playNum = getattr(p, 'playNumber', None)
        if (playNum is not None
                and playNum - self._lastGlitchPlayNumber < ANOMALY_GLITCH_COOLDOWN_PLAYS):
            return

        # Gather every primary actor — offensive ball-mover plus the
        # defenders who altered the play. Order doesn't matter; we
        # shuffle so neither side has a structural firing advantage.
        candidates = []
        for attr in ('receiver', 'runner', 'passer',
                     'tackledBy', 'sackedBy', 'interceptedBy', 'forcedFumbleBy'):
            actor = getattr(p, attr, None)
            if actor is not None and getattr(actor, 'id', None) is not None:
                candidates.append(actor)
        if not candidates:
            return
        _random.shuffle(candidates)

        for player in candidates:
            attention = self._anomalyAttention.get(player.id, 0.0)
            if attention <= 0:
                continue
            prob = min(ANOMALY_GLITCH_PROB_CAP, (attention / ANOMALY_GLITCH_PROB_SCALE) * self._criticalityMultiplier)
            if _random.random() < prob:
                # Pick the layer based on the player's state:
                #   stable / stirring  -> Layer 1 (subtle, "huh")
                #   erratic / rampant  -> 60% Layer 2, 40% Layer 1
                #   awakened           -> 80% Layer 2, 20% Layer 1
                #                         (Layer 3 ability fires separately,
                #                         once per game, not per play)
                #   cleansed           -> Layer 1 only (drained of weight)
                # Cumulative layer roll: the player's state is the CEILING.
                #   stirring / stable / cleansed -> L1 (cosmetic micro)
                #   erratic                       -> L1 or L2
                #   rampant / awakened            -> L1 or L2 (L3 game-impacting
                #                                    added at these states in P2)
                state = self._anomalyState.get(player.id, 'stable')
                if state == 'erratic':
                    layer = 'personality' if _random.random() < ANOMALY_L2_WEIGHT_ERRATIC else 'micro'
                elif state in ('rampant', 'awakened'):
                    layer = 'personality' if _random.random() < ANOMALY_L2_WEIGHT_RAMPANT else 'micro'
                else:
                    layer = 'micro'

                # Layer 2 only fires if the candidate's role succeeded
                # on this play — otherwise the louder "the simulation
                # is failing around them" framing reads dissonant on a
                # failed catch / failed run. Fall back to Layer 1.
                if layer == 'personality' and not self._candidateSucceeded(player, p):
                    layer = 'micro'

                self._injectAnomalyLine(player, layer=layer)
                self._glitchCountThisGame += 1
                if playNum is not None:
                    self._lastGlitchPlayNumber = playNum
                # One anomaly per play. Multiple Awakened players on
                # the field don't stack glitch lines.
                return

    def _candidateSucceeded(self, player, play) -> bool:
        """Did this candidate's role produce a positive outcome for
        their side on this play?

        Defensive actors are only populated when their action succeeded
        (tackledBy / sackedBy / interceptedBy / forcedFumbleBy all
        imply success by their presence).

        Offensive actors succeeded if the play had positive yardage
        and didn't end as a turnover.
        """
        for attr in ('tackledBy', 'sackedBy', 'interceptedBy', 'forcedFumbleBy'):
            if player is getattr(play, attr, None):
                return True
        yardage = getattr(play, 'yardage', 0) or 0
        if yardage <= 0:
            return False
        if (getattr(play, 'isInterception', False)
                or getattr(play, 'isFumbleLost', False)
                or getattr(play, 'isTurnover', False)):
            return False
        return True

    def _injectAnomalyLine(self, player, layer: str = 'micro') -> None:
        """Append a glitch line to the play's text + log the AnomalyEvent.

        layer:
          - 'micro'       — Layer 1 generic pool, subtle, "huh that's curious"
          - 'personality' — Layer 2 pool, more pronounced, "something is wrong"

        Mechanics:
          - `play.glitchText` — the new field, holds the glitch line so
            frontend renderers can style it distinctly from the main
            play text (italic, dim, etc.).
          - `play.glitchPlayerId` / `play.glitchPlayerName` — attribution
            for hover or click-through.
          - `play.glitchLayer` — 'micro' or 'personality' so the frontend
            can style L2 louder than L1.
          - `play.playText` — also gets the line appended with a newline,
            so feeds that read playText alone still surface the glitch.
        """
        if self.play is None:
            return
        if layer == 'personality':
            pool = _LAYER_2_GLITCHES
        else:
            pool = _LAYER_1_MICRO_GLITCHES
        line = _random.choice(pool).format(player=player.name)
        try:
            self.play.glitchText = line
            self.play.glitchPlayerId = player.id
            self.play.glitchPlayerName = player.name
            self.play.glitchLayer = layer
            existing = getattr(self.play, 'playText', '') or ''
            if existing:
                self.play.playText = f"{existing}\n{line}"
            else:
                self.play.playText = line
        except Exception:
            pass
        # Best-effort persistence — failure here doesn't affect the game.
        try:
            from database.connection import get_session
            from database.models import AnomalyEvent
            session = get_session()
            try:
                evt = AnomalyEvent(
                    player_id=player.id,
                    season=self.seasonNumber or 0,
                    week=self.week or 0,
                    game_id=self.id,
                    play_number=getattr(self.play, 'playNumber', None),
                    layer=layer,
                    ability=None,
                    play_text=line,
                    during_thinning=(self._criticalityMultiplier > 1.0),
                )
                session.add(evt)
                session.commit()
            finally:
                session.close()
        except Exception:
            pass

    def _maybeApplyL3Glitch(self) -> None:
        """Layer 3 — a rampant/awakened ball-carrier's play glitches and the
        YARDAGE changes for real (involuntary, not the deliberate Control
        powers). Runs after the play resolves but before the outcome is
        applied, so the adjusted yardage flows through field position, downs,
        and stats consistently.

        Skewed heavily positive. A positive "surge" can extend a drive (and,
        near the goal line, occasionally score) — that's the splashy upside.
        A negative "stumble" is modest and tightly fenced: it only fires on
        short, down-advancing plays (never on a play that earned a first down
        or TD, never on 4th down), is floored so it can't cause a safety, is
        capped per team, and is suppressed in a tight late game — so a glitch
        can never cost a team possession, points, or a game. No turnovers.
        """
        if not self._anomalyAttentionLoaded:
            self._loadAnomalyAttention()
        if not self._anomalyAttention:
            return
        p = self.play
        if p is None:
            return
        playType = getattr(p, 'playType', None)
        if playType not in (PlayType.Run, PlayType.Pass):
            return
        # Forward-progress, non-turnover plays only — excludes incompletions,
        # sacks, runs for loss, fumbles, and interceptions.
        if (getattr(p, 'isFumbleLost', False) or getattr(p, 'isInterception', False)
                or getattr(p, 'isSack', False)):
            return
        baseYardage = getattr(p, 'yardage', 0) or 0
        if baseYardage <= 0:
            return
        carrier = p.runner if playType is PlayType.Run else getattr(p, 'receiver', None)
        if carrier is None or getattr(carrier, 'id', None) is None:
            return
        if self._anomalyState.get(carrier.id, 'stable') not in ('rampant', 'awakened'):
            return
        if self._anomalyAttention.get(carrier.id, 0.0) <= 0:
            return

        from constants import (ANOMALY_GLITCH_MAX_PER_GAME, ANOMALY_GLITCH_COOLDOWN_PLAYS,
                               ANOMALY_L3_TRIGGER_PROB, ANOMALY_L3_HELP_CHANCE,
                               ANOMALY_L3_POS_YARDS, ANOMALY_L3_NEG_YARDS,
                               ANOMALY_L3_MAX_NEG_PER_TEAM, ANOMALY_L3_LATE_QUARTER,
                               ANOMALY_L3_CLOSE_MARGIN)
        # Per-game hygiene: shared cap + cooldown with the cosmetic layers.
        if self._glitchCountThisGame >= ANOMALY_GLITCH_MAX_PER_GAME:
            return
        playNum = getattr(p, 'playNumber', None)
        if (playNum is not None
                and playNum - self._lastGlitchPlayNumber < ANOMALY_GLITCH_COOLDOWN_PLAYS):
            return
        if _random.random() >= ANOMALY_L3_TRIGGER_PROB * self._criticalityMultiplier:
            return

        helpful = _random.random() < ANOMALY_L3_HELP_CHANCE
        if helpful:
            newYardage = baseYardage + _random.randint(*ANOMALY_L3_POS_YARDS)
            ability, pool = 'glitch_surge', _LAYER_3_SURGE_GLITCHES
        else:
            # Stumble guardrails: never touch a first down / TD, never on 4th
            # down, never cause a safety, cap per team, skip a tight late game.
            team = self.offensiveTeam.name
            if baseYardage >= self.yardsToEndzone or baseYardage >= self.yardsToFirstDown:
                return
            if self.down >= 4:
                return
            if self._l3NegByTeam.get(team, 0) >= ANOMALY_L3_MAX_NEG_PER_TEAM:
                return
            if (self.currentQuarter >= ANOMALY_L3_LATE_QUARTER
                    and abs(self.homeScore - self.awayScore) <= ANOMALY_L3_CLOSE_MARGIN):
                return
            loss = _random.randint(*ANOMALY_L3_NEG_YARDS)
            # Floor the loss so it can never drop the offense into a safety.
            loss = min(loss, max(0, (self.yardsToSafety + baseYardage) - 1))
            if loss <= 0:
                return
            newYardage = baseYardage - loss
            ability, pool = 'glitch_stumble', _LAYER_3_STUMBLE_GLITCHES
            self._l3NegByTeam[team] = self._l3NegByTeam.get(team, 0) + 1

        p.yardage = newYardage
        line = _random.choice(pool).format(player=carrier.name)
        try:
            p.glitchText = line
            p.glitchPlayerId = carrier.id
            p.glitchPlayerName = carrier.name
            p.glitchLayer = 'signature'
            p.glitchYardDelta = newYardage - baseYardage
            p._l3Fired = True
        except Exception:
            pass
        self._glitchCountThisGame += 1
        if playNum is not None:
            self._lastGlitchPlayNumber = playNum

        # Best-effort persistence — failure here doesn't affect the game.
        try:
            from database.connection import get_session
            from database.models import AnomalyEvent
            session = get_session()
            try:
                evt = AnomalyEvent(
                    player_id=carrier.id,
                    season=self.seasonNumber or 0,
                    week=self.week or 0,
                    game_id=self.id,
                    play_number=playNum,
                    layer='signature',
                    ability=ability,
                    play_text=line,
                    during_thinning=(self._criticalityMultiplier > 1.0),
                )
                session.add(evt)
                session.commit()
            finally:
                session.close()
        except Exception:
            pass


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
        self.isScramble = False          # QB ran instead of passing
        self.scrambleReason = 'pressure' # 'pressure' (escaped a sack) | 'coverage' (no one open)
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
        # Set by _addScore on any scoring play. Used by calculateWinProbability
        # to bake the expected PAT into a TD's WP.
        self.scoringTeam = None
        self.passIsDropped = False
        self.isInBounds = True  # Default to in bounds
        # Whether the game clock stops after this play. Captured by formatPlayText
        # off self.game.clockRunning, which has been set by either an inline
        # branch (FG, punt, score, turnover) or the post-play shouldClockRun()
        # call by the time the play is being narrated. Lets the frontend render
        # a clock indicator next to each play in the feed.
        self.clockStopped = False
        self.targetSideline = False  # True when play caller targets sideline routes
        # NOTE: do NOT initialize self.down here — line 7488 above already
        # captures the pre-play down from game.down at construction time.
        # An earlier `self.down = 0` here was overwriting that and shipping
        # every play to the frontend with down=0, breaking down/distance
        # rendering across the play feed (most visibly on punts).
        self.gamePressure = 0            # Snapshot of game pressure at play time
        self.keyPressureMod = 0.0        # The key player's pressure modifier
        self.qbPressureMod = 0.0         # QB-specific pressure modifier (pass plays)
        self.rcvPressureMod = 0.0        # Receiver-specific pressure modifier (pass plays)
        self.isClutchPlay = False        # High pressure + positive mod + good outcome
        self.isChokePlay = False         # High pressure + negative mod + bad outcome
        self.clutchPlayerName = ''       # Legacy — single player name (for back-compat)
        # Lists of player names who rose / crumbled under pressure on this play.
        # Populated by _evaluateClutchChoke when the play tags as clutch or choke.
        # Multiple if multiple involved players had non-zero pressure mods in the
        # same direction (e.g. QB and receiver both rose on a clutch TD).
        self.clutchPerformers = []
        self.chokePerformers = []
        self.sackedBy = None             # Defender who made the sack
        self.interceptedBy = None        # Defender who intercepted
        self.tackledBy = None            # Primary tackler (runs or completed passes)
        self.forcedFumbleBy = None       # Defender who forced the fumble
        self.blitzedBy = None            # Blitzer on plays where defense brought pressure
        self.blitzKind = None            # 'lb' / 'safety' / 'allOut' — for play text flavor
        self.isMomentumShift = False     # Play caused a significant momentum swing
        self.playNumber = 0             # Set after totalPlays is incremented
        self.playText = ''
        # Anomaly system attachments — populated when a glitch fires on this
        # play. None / empty when no anomaly happened.
        self.glitchText = None          # The glitch flavor line
        self.glitchPlayerId = None      # Player whose anomaly triggered
        self.glitchPlayerName = None
        self.glitchLayer = None         # 'micro' (L1) / 'personality' (L2) / 'signature' (L3)
        self.glitchYardDelta = None     # L3 only: signed yards the glitch added (+) or cost (-)
        self.insights = {}              # Play insights dict — populated during execution

    def _captureBlitzer(self, scheme, defGameplanObj):
        """If the defensive scheme called a blitz, stash the blitzer on the
        Play so the play-text formatter can call it out. Models excitement —
        even if nothing comes of it, the audience sees the pressure call."""
        if not GAMEPLAN_AVAILABLE:
            return
        blitz = scheme.get('blitzPackage') if scheme else None
        if blitz is None:
            return
        coverageAssignments = getattr(defGameplanObj, 'coverageAssignments', {}) if defGameplanObj else {}
        if blitz == BlitzPackage.LB_BLITZ:
            self.blitzedBy = coverageAssignments.get('te')
            self.blitzKind = 'lb'
        elif blitz == BlitzPackage.SAFETY_BLITZ:
            self.blitzedBy = coverageAssignments.get('rb')
            self.blitzKind = 'safety'
        elif blitz == BlitzPackage.ALL_OUT:
            self.blitzedBy = None  # Multi-player blitz — no single name
            self.blitzKind = 'allOut'

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
            # Reweighted from old 0.5/0.3/0.2 split (clutchFactor was removed)
            mentalScore = 0.6 * phNorm + 0.4 * mentalNorm

            # Max swing scales with pressure intensity: low pressure = tiny, high = up to ±12%
            maxSwing = normalizedPressure * 0.12
            # Penalty swing is larger in high-pressure situations so kickers can
            # choke on crucial FGs (up to ±18% at max pressure)
            maxPenaltySwing = normalizedPressure * 0.18 if self.game.gamePressure >= CLUTCH_PRESSURE_THRESHOLD else maxSwing

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
                pressureAdj = -(batched_random() * maxPenaltySwing)  # penalty

            self.keyPressureMod = round(pressureAdj * 100, 1)
            probability = max(0.05, min(0.96, probability + pressureAdj))
        else:
            self.keyPressureMod = 0

        probability = round(probability * 100)  # Convert to 5-96% integer range

        # Rare block — the kick never gets off cleanly. Counts as a missed FG for
        # the kicker; the game loop hands the loose ball to the defense (with a
        # possible return) via _resolveBlockedKick.
        from constants import FG_BLOCK_ENABLED, FG_BLOCK_CHANCE
        self.isFgBlocked = FG_BLOCK_ENABLED and (batched_random() * 100 < FG_BLOCK_CHANCE)

        x = batched_randint(1,100)

        if self.isFgBlocked:
            self.isFgGood = False
            self.kicker.addMissedFg(self.fgDistance, self.game.isRegularSeasonGame)
        elif x <= probability:
            self.isFgGood = True
            self.kicker.addFg(self.fgDistance, self.game.isRegularSeasonGame)
            if yardsToFG > self.kicker.gameStatsDict['kicking']['longest']:
                self.kicker.gameStatsDict['kicking']['longest'] = yardsToFG
        else:
            self.kicker.addMissedFg(self.fgDistance, self.game.isRegularSeasonGame)

        # ── FG Insights ──
        self.insights['fg'] = {
            'distance': yardsToFG,
            'baseProbability': round(baseProbability * 100, 1),
            'finalProbability': probability,
            'kickerRating': self.kicker.gameAttributes.overallRating,
            'kickerName': self.kicker.name,
            'pressureAdj': self.keyPressureMod,
            'gamePressure': round(self.game.gamePressure),
            'roll': x,
            'isGood': self.isFgGood,
        }
        if normalizedPressure >= 0.3:
            self.insights['fg']['mentalScore'] = round(mentalScore, 2)
            self.insights['fg']['boostChance'] = boostChance
            self.insights['fg']['neutralChance'] = neutralChance

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
                self.game.currentQuarter, self.game.gameClockSeconds,
            )
        else:
            scheme = {'runDefMult': 1.0, 'passDefMult': 1.0, 'passRushMult': 1.0}
        self._captureBlitzer(scheme, defGameplan if GAMEPLAN_AVAILABLE else None)
        effectiveRunDef = self.defense.defenseRunCoverageRating * scheme['runDefMult']

        # Track first-half run plays for halftime adjustment
        if self.game.currentQuarter <= 2:
            if isHomePossession:
                self.game.homeHalfRunPlays += 1
            else:
                self.game.awayHalfRunPlays += 1

        blockerRating = blocker.attributes.blocking if blocker else 50
        # Mental state: frustrated TE blocks sloppily, locked-in TE sustains blocks
        # Scale by /15 to match pass blocking drift (raw drift is ±12-50, too large for 0-100 scale)
        if blocker:
            blockerRating += self._mentalDrift(blocker) / 15
            blockerRating = max(30, min(100, blockerRating))
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
        
        # ── Three-gate yardage model ──
        # Gate 1: The Line — RB power + blocker vs front-7 run defense
        # Gate 2: Second Level — RB agility/vision vs LB-S box (tackling)
        # Gate 3: Open Field — RB speed vs deep coverage/safety angles
        # Most runs end at Gate 1 or 2 (4-9 yds). Clearing all three is rare
        # and produces the 30+ yard scamper.
        gapQuality = selectedGap['actualQuality']
        gapType = selectedGap['type']

        # Gap-weighted hybrid rating (kept from old model — informs Gate 1
        # since gap selection drives line-of-scrimmage matchup style)
        if gapType == 'A-gap':
            rbRating = (self.runner.attributes.power * 1.5 + self.runner.attributes.agility * 0.5) / 2
        elif gapType == 'B-gap':
            rbRating = (self.runner.attributes.power + self.runner.attributes.agility) / 2
        elif gapType == 'C-gap':
            rbRating = (self.runner.attributes.power * 0.5 + self.runner.attributes.agility * 1.5) / 2
        else:  # bounce
            rbRating = self.runner.attributes.agility

        rbMental = self._mentalDrift(self.runner) / 15

        # GATE 1 — Line of scrimmage (power)
        linePower = (self.runner.attributes.power * 1.4 +
                     rbRating * 0.6 +
                     blockerRating * 0.7) / 2.7
        linePower += rbMental + runnerPressureMod
        gapBonus = (gapQuality - 50) / 4
        lineMatchup = linePower - effectiveRunDef + gapBonus
        # Gate-1 floor lifted from 20% → 35% so weak-blocking offenses
        # against strong run defenses aren't pinned at an 80% stuff rate.
        # That floor was killing trailing teams' drives and contributing
        # to the bimodal score distribution. Big-play tails (gates 2/3)
        # unaffected — housecall potential preserved.
        gate1Chance = max(40, min(85, 45 + lineMatchup * 1.2))

        # GATE 2 — Second level (agility/vision vs box tackling)
        secondLevel = (self.runner.attributes.agility * 1.3 +
                       self.runner.attributes.vision * 0.5 +
                       self.runner.attributes.playMakingAbility * 0.2) / 2
        secondLevel += rbMental + runnerPressureMod
        # LB-S box: blend of run defense (LB) and coverage (S) ratings
        secondLevelDef = effectiveRunDef * 0.55 + self.defense.defensePassCoverageRating * 0.45
        gate2Chance = max(6, min(45, 15 + (secondLevel - secondLevelDef) * 1.3))

        # GATE 3 — Open field (speed vs safety angles)
        openField = (self.runner.attributes.speed * 1.7 +
                     self.runner.attributes.playMakingAbility * 0.3) / 2
        openField += rbMental
        openFieldDef = self.defense.defensePassCoverageRating * 0.95
        gate3Chance = max(8, min(55, 22 + (openField - openFieldDef) * 1.2))

        if batched_randint(1, 100) > gate1Chance:
            # Stuffed at the line — -2 to 2 yards
            self.yardage = max(-3, min(3, int(np.random.normal(0.5, 1.3))))
        else:
            # Through the line: 2-6 baseline yards (avg 3.5)
            self.yardage = max(2, min(7, int(np.random.normal(3.5, 1.0))))
            if batched_randint(1, 100) > gate2Chance:
                # Wrapped up at second level: 1-5 more yards (avg 3)
                self.yardage += max(1, min(5, int(np.random.normal(3.0, 1.2))))
            else:
                # Broke through: 5-12 more yards (avg 8)
                self.yardage += max(4, min(12, int(np.random.normal(8.0, 2.0))))
                if batched_randint(1, 100) > gate3Chance:
                    # Chased down by deep coverage: 6-20 more yards (avg 11)
                    self.yardage += max(4, min(22, int(np.random.normal(11.0, 4.0))))
                else:
                    # Housecall — exponential tail (housecall avg ~20)
                    remaining = self.yardsToEndzone - self.yardage
                    self.yardage += min(remaining, max(12, int(np.random.exponential(22))))

        self.yardage = min(self.yardage, self.yardsToEndzone)
        baseYards = self.yardage

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
        
        # Runner choking under pressure lowers fumble threshold (high-pressure only)
        fumbleThreshold = 97
        if self.game.gamePressure >= CLUTCH_PRESSURE_THRESHOLD and runnerPressureMod <= -CHOKE_MODIFIER_THRESHOLD:
            fumbleThreshold = max(92, fumbleThreshold - int(abs(runnerPressureMod) * 2))

        if (fumbleRoll + fumbleResistModifier) > fumbleThreshold:
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
        
        # Identify primary tackler from defensive gameplan
        defGameplanObj = defGameplan if GAMEPLAN_AVAILABLE else None
        coverageAssignments = getattr(defGameplanObj, 'coverageAssignments', {}) if defGameplanObj else {}
        passRusherRun = getattr(defGameplanObj, 'passRusher', None) if defGameplanObj else None
        lbPlayer = coverageAssignments.get('te')  # LB = defense team's RB, assigned to cover TE
        if gapType in ('A-gap', 'B-gap'):
            self.tackledBy = lbPlayer  # Inside runs: LB is primary tackler
        else:
            self.tackledBy = passRusherRun  # Edge runs: DE is primary tackler
        if self.isFumble and self.isFumbleLost:
            self.forcedFumbleBy = self.tackledBy

        # Per-player defensive stats for run plays
        isReg = self.game.isRegularSeasonGame
        if self.tackledBy and hasattr(self.tackledBy, 'stat_tracker'):
            self.tackledBy.stat_tracker.add_tackle(isReg)
            if self.yardage <= 0:
                self.tackledBy.stat_tracker.add_tfl(isReg)
        # Safety (QB on defense) gets tackle on runs that break into secondary (10+ yards)
        # or assist tackle on moderate gains (5+ yards)
        safetyPlayer = coverageAssignments.get('rb')  # Safety = defense team's QB
        if safetyPlayer and hasattr(safetyPlayer, 'stat_tracker') and self.yardage >= 5:
            safetyPlayer.stat_tracker.add_tackle(isReg)
        if self.forcedFumbleBy and hasattr(self.forcedFumbleBy, 'stat_tracker'):
            self.forcedFumbleBy.stat_tracker.add_forced_fumble(isReg)

        # ── Record run execution insights ──
        self.insights['run'] = {
            'designedGap': designedGapType,
            'selectedGap': selectedGap['type'],
            'gapQualities': {g['type']: round(g['quality']) for g in gapList},
            'gapQualityUsed': round(gapQuality),
            'rbVision': self.runner.attributes.vision,
            'rbDiscipline': self.runner.attributes.discipline,
            'runnerRating': round(rbRating),
            'runnerPressureMod': round(runnerPressureMod, 1),
            'blockerRating': round(blockerRating),
            'blockerName': blocker.name if blocker else None,
            'blockingVsDefense': round(blockerRating - effectiveRunDef, 1),
            'effectiveRunDef': round(effectiveRunDef),
            'lineMatchup': round(lineMatchup, 1),
            'gate1Chance': round(gate1Chance, 1),
            'gate2Chance': round(gate2Chance, 1),
            'gate3Chance': round(gate3Chance, 1),
            'baseYards': baseYards,
            'fumbleRisk': round(100 - fumbleThreshold),
            'isFumble': self.isFumble,
            'tackledBy': self.tackledBy.name if self.tackledBy else None,
            'forcedFumbleBy': self.forcedFumbleBy.name if self.forcedFumbleBy else None,
        }
        self.insights['defense'] = {
            'runDefMult': round(scheme['runDefMult'], 2),
            'passDefMult': round(scheme['passDefMult'], 2),
            'passRushMult': round(scheme['passRushMult'], 2),
            'coverageType': scheme.get('coverageType', {}).value if hasattr(scheme.get('coverageType', {}), 'value') else None,
            'blitzPackage': scheme.get('blitzPackage', {}).value if hasattr(scheme.get('blitzPackage', {}), 'value') else None,
        }

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
        # blockingModifier per player is 0-6; combined TE+RB typically 3-8
        qbProtection = qbMobility + (blockingModifier * 4)
        rushDifferential = defensePassRush - qbProtection

        # Dropback depth increases sack risk (3-step=1, 5-step=2, 7-step=3)
        rushDifferential += (dropbackDepth - 1) * 2

        # Base sack rate at even matchup (differential = 0) is ~3%
        # Logistic function: probability increases smoothly with rush advantage
        baseSackRate = 3.0
        steepness = 0.15

        # Shift the curve so 0 differential = baseSackRate
        probability = (baseSackRate * 2) / (1 + np.exp(-steepness * rushDifferential))

        # Extra-long dropbacks (Hail Mary) leave QB exposed in pocket much
        # longer than normal — the standard 15% cap underestimates real risk.
        # Lift cap to 28% so a strong rush against thin protection can wreck
        # the play before it leaves the QB's hand.
        capMax = 28 if dropbackDepth >= 6 else 15
        return max(0.5, min(capMax, probability))

    def _qbEscapesSack(self) -> bool:
        """A pressured QB escapes a would-be sack (and then scrambles). AGILITY
        gates it — a pocket QB almost never gets out. Speed is irrelevant here;
        it only drives the scramble yardage once they're loose."""
        from constants import (QB_SCRAMBLE_ENABLED, QB_SCRAMBLE_AGILITY_THRESHOLD,
                               QB_SCRAMBLE_CHANCE_PER_AGILITY, QB_SCRAMBLE_MAX_CHANCE)
        if not QB_SCRAMBLE_ENABLED:
            return False
        agility = self.passer.gameAttributes.agility
        escapePct = min(QB_SCRAMBLE_MAX_CHANCE,
                        max(0.0, (agility - QB_SCRAMBLE_AGILITY_THRESHOLD) * QB_SCRAMBLE_CHANCE_PER_AGILITY))
        return batched_randint(1, 100) <= escapePct

    def _qbTucksAndRuns(self) -> bool:
        """No one is open. A mobile QB tucks and runs instead of throwing it away.
        This is the primary scramble path (sacks are too rare to matter). AGILITY
        gates the decision; a pocket QB just throws it away."""
        from constants import (QB_SCRAMBLE_ENABLED, QB_SCRAMBLE_AGILITY_THRESHOLD,
                               QB_SCRAMBLE_OPEN_RUN_PER_AGILITY, QB_SCRAMBLE_OPEN_RUN_MAX)
        if not QB_SCRAMBLE_ENABLED:
            return False
        agility = self.passer.gameAttributes.agility
        runPct = min(QB_SCRAMBLE_OPEN_RUN_MAX,
                     max(0.0, (agility - QB_SCRAMBLE_AGILITY_THRESHOLD) * QB_SCRAMBLE_OPEN_RUN_PER_AGILITY))
        return batched_randint(1, 100) <= runPct

    def _pickScrambleTackler(self, coverageAssignments):
        """The defender who brings down a tuck-and-run scramble. Prefer the LB
        (the te-slot assignment), then the safety (rb slot), then any defender."""
        tackler = coverageAssignments.get('te') or coverageAssignments.get('rb')
        if tackler is None:
            for d in coverageAssignments.values():
                if d is not None:
                    tackler = d
                    break
        return tackler

    def _resolveQbScramble(self, tackler, reason='pressure') -> None:
        """The QB runs instead of passing. Resolves as a run with the QB as
        the carrier, so clock / TD / WPA / box-score / fantasy all flow through
        the existing run paths. SPEED drives the yardage (small agility bonus for
        shaking the first defender). Not a sack and not a pass attempt.

        `reason` distinguishes the two triggers so the play-by-play is accurate:
        'pressure' = escaped a would-be sack, 'coverage' = no one open, tucked it."""
        from constants import (QB_SCRAMBLE_BASE_YARDS, QB_SCRAMBLE_SPEED_PIVOT,
                               QB_SCRAMBLE_YARDS_PER_SPEED, QB_SCRAMBLE_OOB_CHANCE,
                               QB_SCRAMBLE_FUMBLE_CHANCE)
        isReg = self.game.isRegularSeasonGame
        self.playType = PlayType.Run
        self.runner = self.passer
        self.isScramble = True
        self.scrambleReason = reason
        self.insights.setdefault('pass', {})['scrambled'] = True

        spd = self.passer.gameAttributes.speed
        agi = self.passer.gameAttributes.agility
        mean = max(1.5, QB_SCRAMBLE_BASE_YARDS + (spd - QB_SCRAMBLE_SPEED_PIVOT) * QB_SCRAMBLE_YARDS_PER_SPEED)
        yds = int(round(np.random.exponential(mean))) + int(round((agi - 80) / 20.0))
        yds = max(0, yds)
        if yds > self.yardsToEndzone:
            yds = self.yardsToEndzone
        self.yardage = yds
        self.isInBounds = batched_randint(1, 100) > QB_SCRAMBLE_OOB_CHANCE
        self.tackledBy = tackler

        # Credit the QB's rush via the same methods the run path uses.
        self.passer.addRushYards(yds, isReg)
        self.passer.addCarry(isReg)
        self.defense.gameDefenseStats['runYardsAlwd'] += yds
        self.defense.gameDefenseStats['totalYardsAlwd'] += yds
        if yds >= 20:
            self.passer.gameStatsDict['rushing']['20+'] += 1
        if yds > self.passer.gameStatsDict['rushing']['longest']:
            self.passer.gameStatsDict['rushing']['longest'] = yds
        if tackler and hasattr(tackler, 'stat_tracker'):
            tackler.stat_tracker.add_tackle(isReg)

        # Small fumble chance on the scramble (credit the tackler if lost).
        if batched_randint(1, 100) > (100 - QB_SCRAMBLE_FUMBLE_CHANCE):
            self.isFumble = True
            if batched_randint(1, 100) <= 50:
                self.isFumbleLost = True
                self.forcedFumbleBy = tackler
                self.defense.gameDefenseStats['fumRec'] += 1
                self.playResult = PlayResult.Fumble
                if tackler and hasattr(tackler, 'stat_tracker'):
                    tackler.stat_tracker.add_forced_fumble(isReg)

    def _resolveRbCheckdown(self, tackler=None, reason='pressure', chargeAttempt=True) -> bool:
        """The QB dumps a short pass to the RB — a safety valve when about to be
        sacked ('pressure') or when no one downfield is open ('checkdown'),
        instead of taking the sack or throwing it away. Resolves as a short
        completion to the RB, reusing the receiving-credit methods (the RB stat +
        fantasy plumbing already support receiving). `chargeAttempt` adds the pass
        attempt — the pressure path hasn't booked one yet, the no-one-open path
        already has. Returns False (no-op) if there's no RB to dump to."""
        from constants import (RB_CHECKDOWN_BASE_YAC, RB_CHECKDOWN_YAC_PER_SPEED,
                               RB_SCREEN_BASE_YAC)
        rb = self.offense.rosterDict.get('rb')
        if rb is None:
            return False
        isReg = self.game.isRegularSeasonGame
        self.passType = PassType.short
        self.receiver = rb
        self.isPassCompletion = True
        self.isCheckdown = True
        self.checkdownReason = reason
        self.insights.setdefault('pass', {})['checkdown'] = reason

        if chargeAttempt:
            self.passer.addPassAttempt(isReg)
        self.passer.addCompletion(isReg)
        rb.addRcvPassTarget(isReg)
        rb.addReception(isReg)

        # Short pass near the line + RB run-after-catch (speed/agility driven). A
        # designed screen starts a touch behind the line but has blockers out front,
        # so it carries more YAC upside than a hurried dump-off.
        spd = rb.gameAttributes.speed
        agi = rb.gameAttributes.agility
        isScreen = reason == 'screen'
        airYards = randint(-3, 1) if isScreen else randint(-1, 4)
        baseYac = RB_SCREEN_BASE_YAC if isScreen else RB_CHECKDOWN_BASE_YAC
        yacMean = max(1.0, baseYac + (spd - 78) * RB_CHECKDOWN_YAC_PER_SPEED)
        yac = max(0, int(round(np.random.exponential(yacMean))) + int((agi - 80) / 25))
        yards = max(-3, airYards + yac)
        yards = min(yards, self.yardsToEndzone)
        self.yardage = yards

        # Reception credit (a TD, if it reaches the end zone, is credited by the
        # game loop's pass-completion path like any other completion).
        self.passer.addPassYards(yards, isReg)
        rb.addReceiveYards(yards, isReg)
        rb.addYAC(yac, isReg)
        if yards >= 20:
            rb.gameStatsDict['receiving']['20+'] += 1
        if yards > rb.gameStatsDict['receiving']['longest']:
            rb.gameStatsDict['receiving']['longest'] = yards
        self.defense.gameDefenseStats['passYardsAlwd'] += yards
        self.defense.gameDefenseStats['totalYardsAlwd'] += yards
        if tackler and hasattr(tackler, 'stat_tracker'):
            tackler.stat_tracker.add_tackle(isReg)
        return True

    def calculatePressureImpact(self, rushDifferential: float) -> float:
        """
        Calculate throw quality degradation from defensive pressure.
        Uses the same rushDifferential as sack probability for consistency.
        Positive rushDifferential = defense winning, negative = good protection.
        Returns degradation factor (0.65 to 1.0) where lower = more disruption.
        """
        # Logistic degradation: smooth curve centered at 0 (even matchup)
        # At even matchup: ~20% degradation (baseline pressure always exists)
        # At rushDiff +15: ~35% degradation (heavy pressure)
        # At rushDiff -15: ~5% degradation (clean pocket)
        maxDegradation = 0.35
        steepness = 0.12

        degradationAmount = maxDegradation * (1 / (1 + np.exp(-steepness * rushDifferential)))
        degradationFactor = 1.0 - degradationAmount

        return max(0.65, min(1.0, degradationFactor))

    def _mentalDrift(self, player, baseWeight=2, driftWeight=25):
        """Calculate mental state effect from base personality + in-game drift.
        Base personality (±2 each) provides moderate persistent influence.
        In-game drift (small increments from TDs, drops, momentum) is amplified
        to create visible frustration/flow state effects during the game.
        """
        baseConf = player.attributes.confidenceModifier
        baseDet = player.attributes.determinationModifier
        confDrift = player.gameAttributes.confidenceModifier - baseConf
        detDrift = player.gameAttributes.determinationModifier - baseDet
        return (baseConf + baseDet) * baseWeight + (confDrift + detDrift) * driftWeight

    def _defenderMentalMod(self, defender):
        """Combined mental swing for a defender on a single resolution.
        Mirrors the pressureMod + mentalDrift/15 pattern used on offense so
        defenders are equally subject to clutch/choke and in-game flow state.
        Returns a rating delta (typically ±0 to ±8) to add onto the defender's
        effective rating for the gate being resolved.
        """
        if defender is None or not hasattr(defender, 'attributes'):
            return 0.0
        try:
            pressureMod = defender.attributes.getPressureModifier(self.game.gamePressure)
        except Exception:
            pressureMod = 0.0
        try:
            drift = self._mentalDrift(defender) / 15
        except Exception:
            drift = 0.0
        return pressureMod + drift

    def calculateReceiverOpenness(self, receiver, defensePassCoverage: int) -> float:
        """
        Stage 1: Calculate how open a receiver is on a scale of 0-100.
        Returns openness rating where:
        - 0-30: Well covered
        - 30-60: Partially open
        - 60-100: Wide open

        Route quality is dynamic per play — affected by game pressure,
        defensive coverage intensity, receiver mental state, and natural variance.
        Disciplined receivers are more consistent; frustrated or pressured ones slip.
        """
        baseRouteRunning = receiver.gameAttributes.routeRunning

        # --- Dynamic route quality modifiers ---

        # 1. Game pressure: receiver's mental composure under pressure
        pressureMod = receiver.attributes.getPressureModifier(self.game.gamePressure)
        pressureEffect = pressureMod * 5  # ±5 points

        # 2. Coverage disruption: elite defenses physically contest routes
        #    Defense 60 = no effect, 90 = up to -6 points
        coverageDisruption = -max(0, (defensePassCoverage - 60) * 0.2)

        # 3. Mental state: base personality + amplified in-game drift (frustration / momentum)
        # Scale by /15 to keep drift within ±1-3 on the 0-100 rating scale
        mentalEffect = self._mentalDrift(receiver) / 15

        # 4. Per-play variance: even elite receivers occasionally run a sloppy route
        #    Discipline tightens the spread (high disc = ±4, low disc = ±8)
        routeVariance = np.random.normal(0, max(4, 10 - receiver.attributes.discipline / 15))

        effectiveRouteRunning = baseRouteRunning + pressureEffect + coverageDisruption + mentalEffect + routeVariance
        effectiveRouteRunning = max(30, min(100, effectiveRouteRunning))

        # Create Gaussian distribution for openness based on skill differential
        skillDifferential = effectiveRouteRunning - defensePassCoverage

        # Mean openness shifts based on skill differential
        meanOpenness = 50 + (skillDifferential / 2)  # Range roughly 30-70
        meanOpenness = max(10, min(90, meanOpenness))  # Clamp to reasonable range

        # Standard deviation - better receivers have more consistent separation
        stdDev = max(10, 25 - (effectiveRouteRunning / 10))

        # Sample from Gaussian and clamp to 0-100
        openness = np.random.normal(meanOpenness, stdDev)
        return max(0, min(100, openness)), round(effectiveRouteRunning)
    
    def selectPassTarget(self, targetList: list, qbVision: int, qbDiscipline: int, mustThrow: bool = False):
        """
        Stage 2: QB finds and selects a receiver based on vision and discipline.
        High vision = accurately perceives receiver openness
        Low vision = distorted perception (sees receivers as more/less open than they are)
        High discipline = won't throw to covered receivers
        mustThrow = desperation: QB must attempt a throw (4th down trailing, time expiring, etc.)
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
                'route': target['route'],
                'coveringDefender': target.get('coveringDefender'),
                'routeQuality': target.get('routeQuality'),
            })
        
        # Sort by perceived openness (what QB thinks they see)
        sortedTargets = sorted(perceivedTargets, key=lambda t: t['openness'], reverse=True)
        
        # QB makes decision based on perceived openness. Thresholds loosened
        # so QBs more often throw to tight windows — real NFL throwaway rate
        # is ~3-5% of attempts, not the 12% the old strict thresholds produced.
        for target in sortedTargets:
            perceivedOpenness = target['openness']

            # Discipline check using perceived openness
            if qbDiscipline >= 90:
                # Elite: prefers 50+ openness, otherwise frequently throws
                # to next-best read instead of stalling.
                if perceivedOpenness >= 50 or batched_randint(1, 100) <= 50:
                    return (target, False)
            elif qbDiscipline >= 75:
                # Good: throws to 30+ openness or rolls to throw anyway.
                if perceivedOpenness >= 30 or batched_randint(1, 100) <= 70:
                    return (target, False)
            elif qbDiscipline >= 60:
                # Average: throws to 15+, mostly forces it otherwise.
                if perceivedOpenness >= 15 or batched_randint(1, 100) <= 85:
                    return (target, False)
            else:
                # Low discipline: throws to anyone, risky
                if batched_randint(1, 100) <= 95:
                    return (target, False)

        # No suitable receiver found - force throw to the most-open target
        # unless QB has decent discipline AND every target is buried.
        # Calibrated so ~3-5% of attempts end in throwaway (NFL benchmark).
        if mustThrow:
            return (sortedTargets[0], False)
        topOpenness = sortedTargets[0]['openness'] if sortedTargets else 0
        # Disciplined QBs (80+) bail when no target is reasonably open.
        # openness < 50 is the trigger — even a moderately covered top read
        # is enough to throw away rather than force it. Below-80 discipline
        # QBs always force the throw (they don't have the patience to bail).
        if qbDiscipline >= 80 and topOpenness < 50:
            return (None, True)
        # Otherwise force the throw to the most-open option.
        return (sortedTargets[0], False)
    
    def calculateThrowQuality(self, passType, qbAccuracy: int, qbArmStrength: int, qbXFactor: int, rushDifferential: float, qbPressureMod: float) -> float:
        """
        Stage 3: Calculate throw quality (0-100) based on QB skill, pass type, and pressure.

        Short passes are accuracy-dominant; deep passes are arm-dominant. A
        weak-armed QB can be surgical underneath but struggles to drive the
        ball downfield — gunslingers are the inverse. Combined with the per-tier
        difficulty multiplier, this creates real QB archetypes.
        """
        # Per-tier weighted blend of accuracy and arm strength.
        tierWeights = {
            PassType.short:    {'acc': 0.95, 'arm': 0.05},
            PassType.medium:   {'acc': 0.80, 'arm': 0.20},
            PassType.long:     {'acc': 0.60, 'arm': 0.40},
            PassType.deep:     {'acc': 0.40, 'arm': 0.60},
            PassType.hailMary: {'acc': 0.20, 'arm': 0.80},
        }
        w = tierWeights.get(passType, tierWeights[PassType.medium])
        skillBlend = qbAccuracy * w['acc'] + qbArmStrength * w['arm']
        baseAccuracy = (skillBlend + qbXFactor) / 2 + qbPressureMod

        # Mental state: QB in rhythm throws sharper, rattled QB throws errant
        # Scale by /15 to keep drift within ±1-3 on the 0-100 rating scale
        mentalEffect = self._mentalDrift(self.passer) / 15
        baseAccuracy += mentalEffect

        # Pass type difficulty multiplier — modestly steeper than the old curve.
        # Combined with the arm-strength weighting above, weak-armed QBs on
        # deep balls land in the bad-throw bucket, but average QBs can still
        # complete intermediate routes at NFL-realistic rates.
        passTypeDifficulty = {
            PassType.short:    1.00,
            PassType.medium:   0.92,
            PassType.long:     0.80,
            PassType.deep:     0.65,
            PassType.hailMary: 0.42,
        }
        difficultyMod = passTypeDifficulty.get(passType, 0.85)

        # Calculate pressure impact from same rushDifferential used for sacks
        pressureDegradation = self.calculatePressureImpact(rushDifferential)

        # Apply all modifiers
        throwQuality = baseAccuracy * difficultyMod * pressureDegradation

        # Add natural variance
        throwQuality += batched_randint(-10, 10)

        return max(5, min(100, throwQuality))
    
    def calculateCatchProbability(self, throwQuality: float, receiverHands: int, receiverReach: int, receiverOpenness: float, defensePassCoverage: int, receiverPressureMod: float, passType=None, receiverActualOpenness: float = None) -> dict:
        """
        Two-phase catch model with hard floors that prevent attribute compounding:

        Phase 1 (Contact): Can the receiver physically get their hands on the ball?
            - Good throws are easy to reach; bad throws require high reach
            - Coverage applies in two layers: openness-gated disruption AND a
              baseline pressure that scales with defensive coverage rating, so
              good defenses always cost completion percentage (mirrors the run
              game's "stuff floor" — defense can never be locked out).
        Phase 2 (Secure): Given contact, does the receiver catch the ball?
            - Primarily hands-driven
            - Contested catches and bad throws are harder to secure

        Compared to the prior version: tighter top-end caps (contact 92 / secure 95)
        and a coverage baseline component that always applies — so mature defenses
        actually slow mature offenses, instead of being zeroed out whenever the
        receiver is open.
        """
        adjustedHands = receiverHands + receiverPressureMod

        # PHASE 1: Contact — can the receiver get their hands on it?
        # Top-end lightly compressed so elite throws aren't quite automatic.
        if throwQuality >= 70:
            baseContact = 85 + (throwQuality - 70) * 0.45  # 85-99
            reachFactor = receiverReach * 0.05
        elif throwQuality >= 50:
            baseContact = 53 + (throwQuality - 50) * 1.6   # 53-85
            reachFactor = (receiverReach - 60) * 0.4
        else:
            baseContact = 10 + throwQuality * 0.85         # 10-52
            reachFactor = (receiverReach - 60) * 0.7

        # Tier-scaled coverage disruption: short throws are quick-release, so
        # defenders have little time to make a play; deep throws give DBs more
        # window to converge. This is the lever that keeps trailing-team offenses
        # viable — short passes should be reliable even against tight coverage,
        # so teams can sustain drives in catch-up mode.
        tierDisruptionMult = {
            PassType.short:    0.40,
            PassType.medium:   0.75,
            PassType.long:     1.00,
            PassType.deep:     1.15,
            PassType.hailMary: 1.30,
        } if passType is not None else None
        tierMult = tierDisruptionMult.get(passType, 1.0) if tierDisruptionMult else 1.0
        coverageDisruption = max(0, (100 - receiverOpenness) / 100) * (defensePassCoverage / 100) * 18 * tierMult
        # Baseline coverage pressure: always applies, scales modestly with
        # defensive rating. Anchored at 70 (league-average) so elite defenses
        # cost a couple contact points; weak defenses refund a bit. Light touch
        # to keep the structural lever without crushing baseline completion.
        coverageBaseline = (defensePassCoverage - 70) * 0.1
        contactProb = min(96, max(5, baseContact + reachFactor - coverageDisruption - coverageBaseline))

        # PHASE 2: Secure — given contact, do they catch it?
        baseSecure = adjustedHands * 0.95 + 8

        if receiverOpenness < 40:
            contestPenalty = (40 - receiverOpenness) * 0.35
            baseSecure -= contestPenalty

        if throwQuality < 50:
            throwDifficulty = (50 - throwQuality) * 0.35
            baseSecure -= throwDifficulty

        secureProb = min(96, max(15, baseSecure))

        # COMBINED: catch = contact AND secure
        catchProb = (contactProb * secureProb) / 100

        # Hail mary: a contested end-zone heave should connect only as a rare
        # miracle. Scale the catch probability down to the hail-mary target rate
        # (a completion = TD). INT/drop paths are left intact — a heave can still
        # be picked in the end zone.
        if passType is PassType.hailMary:
            catchProb *= HAIL_MARY_COMPLETION_SCALE

        # INT probability — three independent paths, any of which can pick a
        # pass (they don't have to co-occur the way the old single-gate model
        # required):
        #   1. Bad read — QB throws into coverage. Scales with how covered the
        #      receiver ACTUALLY is (not how open the QB thought they were), so
        #      low-vision QBs who target covered receivers get punished here.
        #   2. Bad throw — an errant ball sails into traffic. The trigger is
        #      throw quality (independent of the read), but a defender still has
        #      to be near the target to capitalize: a bad throw to a wide-open
        #      receiver falls incomplete (and reach may still bail it out), it
        #      doesn't get picked out of empty space.
        #   3. Defender's play — an above-average DB jumps a contested throw on
        #      his own, even when the read and throw were fine.
        # Combined as independent risks (probabilistic OR) so they stack but
        # stay bounded. No per-tier multiplier: deep throws already pick more
        # because their throw quality runs lower.
        intOpenness = receiverActualOpenness if receiverActualOpenness is not None else receiverOpenness
        cov = defensePassCoverage
        covFactor = cov / 100
        openGap = max(0.0, 50 - intOpenness) / 50      # 0 open … 1 blanketed
        throwGap = max(0.0, 55 - throwQuality) / 55    # 0 sharp … 1 errant
        # Proximity: how reachable the ball is for a defender. Full effect when
        # the receiver is blanketed, fades toward zero once he's wide open
        # (≥75). The floor is tier-dependent: a short throw can be genuinely
        # uncontested, but a deep ball always has a safety in the area, so even
        # an "open" deep receiver leaves a pickable window. This restores the
        # deep > short INT gradient without a blanket per-tier multiplier.
        proximityFloor = {
            PassType.short:    0.00,
            PassType.medium:   0.05,
            PassType.long:     0.20,
            PassType.deep:     0.35,
            PassType.hailMary: 0.50,
        }.get(passType, 0.10) if passType is not None else 0.0
        proximity = max(proximityFloor, min(1.0, (75 - intOpenness) / 55))

        pBadRead = openGap * covFactor * INT_BAD_READ_K
        pBadThrow = throwGap * (0.4 + 0.6 * covFactor) * proximity * INT_BAD_THROW_K
        pDefPlay = max(0.0, (cov - 70) / 30) * openGap * INT_DEF_PLAY_K

        intFrac = 1 - (1 - pBadRead) * (1 - pBadThrow) * (1 - pDefPlay)
        intProb = intFrac * 100

        # Drop probability — receiver gets hands on it but doesn't secure
        nonsecuredContact = (contactProb / 100) * (100 - secureProb)
        dropProb = nonsecuredContact * 0.3

        return {
            'contactProb': round(contactProb, 1),
            'secureProb': round(secureProb, 1),
            'catchProb': round(min(95, max(3, catchProb)), 1),
            'intProb': round(min(25, max(0, intProb)), 1),
            'dropProb': round(min(30, max(0, dropProb)), 1),
        }
    
    def calculatePassYardage(self, passType) -> int:
        """
        Air yards follow the pass tier's Gaussian distribution. Throw quality
        affects catch probability, not how far the ball travels — the QB throws
        to a target at the route's depth, quality is only about placement.
        """
        # Hail mary: thrown AT the end zone, not a fixed depth. Air yards = the
        # distance to the goal line, capped by how far this QB can physically
        # heave it (arm strength). So a completed hail mary lands in the end zone
        # (a touchdown); if the end zone is out of the QB's range the ball falls
        # short of it (and is almost certainly incomplete / caught short).
        if passType is PassType.hailMary:
            arm = 75
            if self.passer is not None:
                arm = getattr(getattr(self.passer, 'gameAttributes', None), 'armStrength', 75)
            maxHeave = 50 + (arm - 70) * 0.4   # ~46 yds (weak arm) → ~62 yds (elite)
            return max(0, int(min(self.yardsToEndzone, maxHeave)))

        passTypeParams = {
            PassType.short:    {'mean': 3,    'stdDev': 1.0},
            PassType.medium:   {'mean': 6.5,  'stdDev': 2.0},
            PassType.long:     {'mean': 15,   'stdDev': 3.5},
            PassType.deep:     {'mean': 24,   'stdDev': 4.5},
            PassType.hailMary: {'mean': 45,   'stdDev': 8.0},
        }
        params = passTypeParams.get(passType, passTypeParams[PassType.medium])
        airYards = int(np.random.normal(params['mean'], params['stdDev']))
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
        self.rushDifferential = 0
        self.passType = None
        # Flag hail-mary plays at function start so the post-play log can
        # detect them even when a sack short-circuits passType assignment.
        self._isHailMaryPlay = any(
            t == PassType.hailMary
            for t in passPlayBook[playKey]['targets'].values()
        )
        # Pre-assign intended pass tier from dropback depth so sack analytics
        # can attribute tier even when the play never reaches target selection.
        _dropbackTierMap = {0: 'short', 2: 'medium', 4: 'long', 6: 'deep'}
        if self._isHailMaryPlay:
            self.intendedPassTier = 'hailMary'
        else:
            self.intendedPassTier = _dropbackTierMap.get(passPlayBook[playKey]['dropback'].value, 'medium')
        self.passBlockers = []  # Track who's blocking for insights

        if passPlayBook[playKey]['targets']['te'] is None:
            te = self.offense.rosterDict['te']
            if te is not None:
                # Mental drift affects pass blocking (scaled to 0-6 modifier range)
                teDrift = self._mentalDrift(te) / 15
                self.blockingModifier += te.attributes.blockingModifier + teDrift
                self.passBlockers.append(te)
        if passPlayBook[playKey]['targets']['rb'] is None:
            rb = self.offense.rosterDict['rb']
            if rb is not None:
                rbDrift = self._mentalDrift(rb) / 15
                self.blockingModifier += rb.attributes.blockingModifier + rbDrift
                self.passBlockers.append(rb)

        # Get per-play defensive scheme multipliers
        isHomePossession = (self.game.offensiveTeam == self.game.homeTeam)
        defGameplan = self.game.awayDefGameplan if isHomePossession else self.game.homeDefGameplan
        if GAMEPLAN_AVAILABLE and defGameplan is not None:
            offScoreDiff = (self.game.homeScore - self.game.awayScore if isHomePossession
                            else self.game.awayScore - self.game.homeScore)
            scheme = getDefensiveScheme(
                defGameplan, self.game.down, self.game.yardsToFirstDown,
                100 - self.game.yardsToEndzone, offScoreDiff,
                self.game.currentQuarter, self.game.gameClockSeconds,
            )
        else:
            scheme = {'runDefMult': 1.0, 'passDefMult': 1.0, 'passRushMult': 1.0}
        # Individual pass rush: DE's passRush vs TE blocking (when TE blocks)
        defGameplanObj = defGameplan if GAMEPLAN_AVAILABLE else None
        self._captureBlitzer(scheme, defGameplanObj)

        passRusher = getattr(defGameplanObj, 'passRusher', None) if defGameplanObj else None
        if passRusher:
            deAttrs = passRusher.attributes.getDefensiveAttributes(passRusher.position)
            basePassRush = deAttrs.get('passRush', self.defense.defensePassRushRating)
            basePassRush += self._defenderMentalMod(passRusher)
        else:
            basePassRush = self.defense.defensePassRushRating
        effectivePassRush = basePassRush * scheme['passRushMult']
        # Team-level pass coverage as fallback (individual matchups applied per-receiver below)
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
        # Hail Mary plays leave the QB exposed in the pocket ~2-3x longer than
        # a normal pass while every receiver runs deep — protection is short
        # and the rush has time to win even average matchups. Multiply base
        # sack probability and lift the cap further for these plays.
        if getattr(self, '_isHailMaryPlay', False):
            sackProbability = min(35, sackProbability * 2.5)
        
        sackRoll = batched_randint(1, 100)

        # ── Record pass base insights (before sack/completion branching) ──
        # rushDifferential is what feeds the sack logistic curve AND pressure impact:
        # negative = good protection, positive = pressure getting through
        dropbackDepth = passPlayBook[playKey]['dropback'].value
        rushDifferential = round(effectivePassRush - (qbMobility + (self.blockingModifier * 4)) + (dropbackDepth - 1) * 2)
        self.rushDifferential = rushDifferential
        self.insights['pass'] = {
            'sackProbability': round(sackProbability, 1),
            'sackRoll': sackRoll,
            'effectivePassRush': round(effectivePassRush),
            'effectivePassDef': round(effectivePassDef),
            'blockingModifier': round(self.blockingModifier, 1),
            'protectionDiff': -rushDifferential,
        }
        self.insights['defense'] = {
            'runDefMult': round(scheme['runDefMult'], 2),
            'passDefMult': round(scheme['passDefMult'], 2),
            'passRushMult': round(scheme['passRushMult'], 2),
            'coverageType': scheme.get('coverageType', {}).value if hasattr(scheme.get('coverageType', {}), 'value') else None,
            'blitzPackage': scheme.get('blitzPackage', {}).value if hasattr(scheme.get('blitzPackage', {}), 'value') else None,
        }

        # A would-be sack: an agile QB can escape the pocket and scramble
        # (agility gates the escape; speed drives the yardage). The would-be
        # sacker (passRusher) becomes the tackler on the run.
        wouldBeSacked = sackRoll <= sackProbability
        qbScrambles = wouldBeSacked and self._qbEscapesSack()
        from constants import (RB_CHECKDOWN_ENABLED, RB_CHECKDOWN_PRESSURE_CHANCE,
                               RB_SCREEN_ENABLED, RB_SCREEN_CHANCE)
        hasRb = self.offense.rosterDict.get('rb') is not None
        rbDumps = (wouldBeSacked and not qbScrambles and RB_CHECKDOWN_ENABLED and hasRb
                   and batched_random() * 100 < RB_CHECKDOWN_PRESSURE_CHANCE)
        # Designed screen: a called play on a clean dropback (no would-be sack).
        screenCalled = (not wouldBeSacked and RB_SCREEN_ENABLED and hasRb
                        and batched_random() * 100 < RB_SCREEN_CHANCE)
        if screenCalled:
            screenCov = getattr(defGameplanObj, 'coverageAssignments', {}) if defGameplanObj else {}
            self._resolveRbCheckdown(self._pickScrambleTackler(screenCov), reason='screen', chargeAttempt=True)
        elif qbScrambles:
            self._resolveQbScramble(passRusher, reason='pressure')
        elif rbDumps:
            # Safety valve: dump it to the RB instead of taking the sack.
            self._resolveRbCheckdown(passRusher, reason='pressure', chargeAttempt=True)
        elif wouldBeSacked:
            self.insights['pass']['wasSacked'] = True
            # Name the sacker based on blitz package
            coverageAssignmentsForSack = getattr(defGameplanObj, 'coverageAssignments', {}) if defGameplanObj else {}
            lbForSack = coverageAssignmentsForSack.get('te')   # LB = defense team's RB
            safetyForSack = coverageAssignmentsForSack.get('rb') # S = defense team's QB
            activeBlitz = scheme.get('blitzPackage') if GAMEPLAN_AVAILABLE else None
            sackWhoRoll = batched_randint(1, 100)
            if activeBlitz == BlitzPackage.LB_BLITZ:
                # LB blitz: LB gets most sacks, DE secondary
                if sackWhoRoll <= 55 and lbForSack:
                    self.sackedBy = lbForSack
                else:
                    self.sackedBy = passRusher
            elif activeBlitz == BlitzPackage.SAFETY_BLITZ:
                # Safety blitz: safety gets some, DE still primary
                if sackWhoRoll <= 40 and safetyForSack:
                    self.sackedBy = safetyForSack
                elif sackWhoRoll <= 70:
                    self.sackedBy = passRusher
                elif lbForSack:
                    self.sackedBy = lbForSack
                else:
                    self.sackedBy = passRusher
            elif activeBlitz == BlitzPackage.ALL_OUT:
                # All-out: everyone rushing, split evenly
                if sackWhoRoll <= 35:
                    self.sackedBy = passRusher
                elif sackWhoRoll <= 60 and lbForSack:
                    self.sackedBy = lbForSack
                elif safetyForSack:
                    self.sackedBy = safetyForSack
                else:
                    self.sackedBy = passRusher
            else:
                # Base rush: DE dominates, small chance for others
                if sackWhoRoll <= 80:
                    self.sackedBy = passRusher
                elif sackWhoRoll <= 93 and lbForSack:
                    self.sackedBy = lbForSack
                elif safetyForSack:
                    self.sackedBy = safetyForSack
                else:
                    self.sackedBy = passRusher
            if self.sackedBy:
                self.insights['pass']['sackedBy'] = self.sackedBy.name
                # Per-player defensive stats: sack + tackle + TFL
                if hasattr(self.sackedBy, 'stat_tracker'):
                    isReg = self.game.isRegularSeasonGame
                    self.sackedBy.stat_tracker.add_defensive_sack(isReg)
                    self.sackedBy.stat_tracker.add_tackle(isReg)
                    self.sackedBy.stat_tracker.add_tfl(isReg)
            # Sack yardage using exponential distribution (most 3-7 yards, occasional 10+)
            rushAdvantage = max(0, basePassRush - qbMobility) / 20
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
                if (basePassRush + batched_randint(-5,5)) >= (self.passer.gameAttributes.power + self.passer.gameAttributes.luckModifier + batched_randint(-5,5)):
                    self.passer.updateInGameConfidence(-.02)
                    self.defense.updateInGameConfidence(.02)
                    self.defense.gameDefenseStats['fumRec'] += 1
                    self.isFumbleLost = True
                    self.forcedFumbleBy = self.sackedBy
                    if self.forcedFumbleBy:
                        self.insights['pass']['forcedFumbleBy'] = self.forcedFumbleBy.name
                        if hasattr(self.forcedFumbleBy, 'stat_tracker'):
                            self.forcedFumbleBy.stat_tracker.add_forced_fumble(self.game.isRegularSeasonGame)
                    self.playResult = PlayResult.Fumble
        else:
            self.passer.addPassAttempt(self.game.isRegularSeasonGame)
            targets:dict = passPlayBook[playKey]['targets']
            targetList = []
            
            # STAGE 1: Calculate receiver openness (0-100 scale)
            # Use individual defender coverage ratings from gameplan assignments
            coverageAssignments = getattr(defGameplanObj, 'coverageAssignments', {}) if defGameplanObj else {}
            coverageType = scheme.get('coverageType')
            blitzPackage = scheme.get('blitzPackage')
            for key in targets.keys():
                if targets[key] is not None:
                    receiver = self.offense.rosterDict[key]
                    # Look up the assigned defender for this receiver slot
                    assignedDefender = coverageAssignments.get(key)
                    if assignedDefender:
                        defAttrs = assignedDefender.attributes.getDefensiveAttributes(assignedDefender.position)
                        individualCoverage = defAttrs.get('coverage', effectivePassDef)
                        individualCoverage += self._defenderMentalMod(assignedDefender)

                        # Coverage type modifies how individual coverage applies
                        if GAMEPLAN_AVAILABLE and coverageType is not None:
                            if coverageType == CoverageType.MAN:
                                # Man: pure individual matchup, strong vs short/quick
                                rcvDefRating = individualCoverage * scheme['passDefMult']
                            elif coverageType == CoverageType.ZONE:
                                # Zone: pooled coverage average — individual skill matters less
                                teamAvgCoverage = effectivePassDef
                                rcvDefRating = (individualCoverage * 0.4 + teamAvgCoverage * 0.6) * scheme['passDefMult']
                            elif coverageType == CoverageType.MATCH:
                                # Match: blend of man and zone
                                safetyPlayer = coverageAssignments.get('rb')
                                safetyPlayReading = 70
                                if safetyPlayer:
                                    sAttrs = safetyPlayer.attributes.getDefensiveAttributes(safetyPlayer.position)
                                    safetyPlayReading = sAttrs.get('playReading', 70)
                                    safetyPlayReading += self._defenderMentalMod(safetyPlayer)
                                # Better safety play-reading → more man-like (stronger)
                                manWeight = 0.4 + (safetyPlayReading - 60) / 100
                                manWeight = max(0.3, min(0.7, manWeight))
                                rcvDefRating = (individualCoverage * manWeight + effectivePassDef * (1 - manWeight)) * scheme['passDefMult']
                            else:
                                rcvDefRating = individualCoverage * scheme['passDefMult']
                        else:
                            rcvDefRating = individualCoverage * scheme['passDefMult']

                        # Blitz exposure: if a defender is blitzing, their coverage assignment is weakened
                        if GAMEPLAN_AVAILABLE and blitzPackage is not None:
                            if blitzPackage == BlitzPackage.LB_BLITZ and key == 'te':
                                # LB is blitzing — TE has no dedicated coverage
                                rcvDefRating *= 0.5
                            elif blitzPackage == BlitzPackage.SAFETY_BLITZ and targets[key] in (PassType.long, PassType.hailMary):
                                # Safety blitz — deep routes lose safety help
                                rcvDefRating *= 0.85
                            elif blitzPackage == BlitzPackage.ALL_OUT:
                                # Everyone rushing — all coverage suffers
                                rcvDefRating *= 0.65
                                if key == 'te':
                                    rcvDefRating *= 0.6  # TE completely uncovered
                    else:
                        rcvDefRating = effectivePassDef

                    # Hail Mary: defense is in prevent — every defender is
                    # collapsing on the deep target. Triple coverage in the
                    # endzone is the norm, not the exception.
                    if targets[key] == PassType.hailMary:
                        rcvDefRating *= 1.5
                    openness, routeQuality = self.calculateReceiverOpenness(receiver, rcvDefRating)
                    receiverStatusDict = {
                        'receiver': receiver,
                        'openness': openness,
                        'routeQuality': routeQuality,
                        'route': targets[key],
                        'coveringDefender': assignedDefender,
                    }
                    targetList.append(receiverStatusDict)
            
            # STAGE 2: QB selects target based on vision and discipline
            # Desperation: QB must force a throw when throwing away would end the drive
            # or the game unfavorably (4th down while trailing, time expiring while trailing)
            isTrailing = (self.offense == self.game.homeTeam and self.game.homeScore < self.game.awayScore) or \
                         (self.offense == self.game.awayTeam and self.game.awayScore < self.game.homeScore)
            isTied = self.game.homeScore == self.game.awayScore
            isFourthDown = self.game.down == 4
            isTimeExpiring = self.game.gameClockSeconds <= 30
            isLateGame = self.game.currentQuarter >= 4
            mustThrow = isFourthDown and (isTrailing or (isTied and self.game.currentQuarter >= 5))
            if not mustThrow and isLateGame and isTimeExpiring and isTrailing:
                mustThrow = True
            selectedTarget, willThrowAway = self.selectPassTarget(
                targetList,
                self.passer.attributes.vision,
                self.passer.gameAttributes.discipline,
                mustThrow=mustThrow
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
            from constants import RB_CHECKDOWN_ENABLED as _RBCK_EN, RB_CHECKDOWN_OPEN_CHANCE as _RBCK_OPEN
            if self.passType == PassType.throwAway and not mustThrow and self._qbTucksAndRuns():
                # No one open: a mobile QB tucks and runs instead of throwing it
                # away. The dropback became a rush, so un-charge the pass attempt
                # booked at the top of this branch.
                self.passer.stat_tracker.remove_pass_attempt(self.game.isRegularSeasonGame)
                self._resolveQbScramble(self._pickScrambleTackler(coverageAssignments), reason='coverage')
            elif (self.passType == PassType.throwAway and not mustThrow and _RBCK_EN
                  and self.offense.rosterDict.get('rb') is not None
                  and batched_random() * 100 < _RBCK_OPEN):
                # No one open downfield: check it down to the RB rather than throw
                # it away. The attempt was already booked at the top of this
                # branch, so don't re-charge it.
                self._resolveRbCheckdown(self._pickScrambleTackler(coverageAssignments),
                                         reason='checkdown', chargeAttempt=False)
            elif self.passType == PassType.throwAway:
                self.insights['pass']['wasSacked'] = False
                self.insights['pass']['throwAway'] = True
                self.insights['pass']['targets'] = [
                    {
                        'position': t['receiver'].position.name,
                        'name': t['receiver'].name,
                        'openness': round(t['openness']),
                        'routeQuality': t.get('routeQuality', 0),
                        'reach': getattr(t['receiver'].gameAttributes, 'reach', 0),
                        'route': t['route'].name if hasattr(t['route'], 'name') else str(t['route']),
                        'isSelected': False,
                    }
                    for t in targetList
                ]
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
                    self.passer.gameAttributes.armStrength,
                    self.passer.gameAttributes.xFactor,
                    self.rushDifferential,
                    qbPressureMod
                )

                # Sideline throws are harder — tighter windows
                if self.targetSideline:
                    throwQuality = max(5, throwQuality * 0.90)

                # ── Record pass target + throw insights ──
                self.insights['pass']['wasSacked'] = False
                self.insights['pass']['qbVision'] = self.passer.attributes.vision
                self.insights['pass']['targets'] = [
                    {
                        'position': t['receiver'].position.name,
                        'name': t['receiver'].name,
                        'openness': round(t.get('actualOpenness', t['openness'])),
                        'routeQuality': t.get('routeQuality', 0),
                        'reach': getattr(t['receiver'].gameAttributes, 'reach', 0),
                        'route': t['route'].name if hasattr(t['route'], 'name') else str(t['route']),
                        'isSelected': (selectedTarget is not None and t['receiver'] is selectedTarget['receiver']),
                        'coveredBy': t.get('coveringDefender').name if t.get('coveringDefender') else None,
                    }
                    for t in targetList
                ]
                self.insights['pass']['throwQuality'] = round(throwQuality)
                self.insights['pass']['qbPressureMod'] = round(qbPressureMod, 1)
                self.insights['pass']['rcvPressureMod'] = round(receiverPressureMod, 1)
                self.insights['pass']['rcvHands'] = self.receiver.gameAttributes.hands
                self.insights['pass']['rcvReach'] = getattr(self.receiver.gameAttributes, 'reach', 0)
                self.insights['pass']['rcvRouteRunning'] = self.selectedTarget.get('routeQuality', self.receiver.gameAttributes.routeRunning)
                self.insights['pass']['rcvOpenness'] = round(self.selectedTarget.get('openness', 0))
                # Actual (not QB-perceived) openness — drives the context-aware
                # incomplete/INT narration the same way the INT model judges it.
                self.insights['pass']['rcvActualOpenness'] = round(
                    self.selectedTarget.get('actualOpenness', self.selectedTarget.get('openness', 0))
                )

                # STAGE 4: Calculate catch probability and outcome
                # Use individual defender coverage if available
                coveringDefender = self.selectedTarget.get('coveringDefender')
                if coveringDefender:
                    defAttrs = coveringDefender.attributes.getDefensiveAttributes(coveringDefender.position)
                    catchDefCoverage = defAttrs.get('coverage', self.defense.defensePassCoverageRating)
                    catchDefCoverage += self._defenderMentalMod(coveringDefender)
                else:
                    catchDefCoverage = self.defense.defensePassCoverageRating
                self.insights['pass']['catchDefCoverage'] = round(catchDefCoverage)
                catchProbs = self.calculateCatchProbability(
                    throwQuality,
                    self.receiver.gameAttributes.hands,
                    getattr(self.receiver.gameAttributes, 'reach', 70),
                    self.selectedTarget['openness'],
                    catchDefCoverage,
                    receiverPressureMod,
                    passType=self.passType,
                    receiverActualOpenness=self.selectedTarget.get('actualOpenness', self.selectedTarget['openness']),
                )

                # Choke boosts only in high-pressure situations (Q4 close games, etc.)
                if self.game.gamePressure >= CLUTCH_PRESSURE_THRESHOLD:
                    # QB choking under pressure increases INT risk
                    if qbPressureMod <= -CHOKE_MODIFIER_THRESHOLD:
                        chokeIntBoost = abs(qbPressureMod) * 1.5
                        catchProbs['intProb'] = min(25, catchProbs['intProb'] + chokeIntBoost)

                    # Receiver choking under pressure increases drop risk
                    if receiverPressureMod <= -CHOKE_MODIFIER_THRESHOLD:
                        chokeDropBoost = abs(receiverPressureMod) * 2.0
                        catchProbs['dropProb'] = min(30, catchProbs['dropProb'] + chokeDropBoost)

                # Roll for outcome
                outcomeRoll = batched_randint(1, 100)

                # ── Record catch probability insights ──
                self.insights['pass']['contactProbability'] = round(catchProbs['contactProb'])
                self.insights['pass']['secureProbability'] = round(catchProbs['secureProb'])
                self.insights['pass']['catchProbability'] = round(catchProbs['catchProb'])
                self.insights['pass']['intProbability'] = round(catchProbs['intProb'])
                self.insights['pass']['dropProbability'] = round(catchProbs['dropProb'])
                self.insights['pass']['outcomeRoll'] = outcomeRoll

                # Check for interception first (bad throw to covered receiver)
                if outcomeRoll <= catchProbs['intProb']:
                    # Interception caught at the throw's depth (air yards), clamped to
                    # the end zone (a pick at the goal line → touchback via the turnover
                    # branch). The defender's run-back is applied later by
                    # _resolveDefensiveReturn off this recovery spot.
                    from constants import RETURN_INT_SPOT_BY_DEPTH
                    _intDepthKey = getattr(self.passType, 'name', str(self.passType))
                    _intLo, _intHi = RETURN_INT_SPOT_BY_DEPTH.get(_intDepthKey, (0, 8))
                    self.yardage = min(randint(_intLo, _intHi), self.yardsToEndzone)
                    self.passer.addInterception(self.game.isRegularSeasonGame)
                    self.passer.addMissedPass(self.game.isRegularSeasonGame)
                    self.passer.updateInGameConfidence(-.02)
                    self.defense.updateInGameConfidence(.02)
                    self.defense.gameDefenseStats['ints'] += 1
                    self.isInterception = True
                    # Determine who intercepts: covering CB, or Safety on deep overthrows
                    safetyPlayer = coverageAssignments.get('rb')
                    if (safetyPlayer and coveringDefender is not safetyPlayer
                            and self.passType in (PassType.long, PassType.hailMary)
                            and batched_randint(1, 100) <= 35):
                        # Safety reads the deep throw and jumps the route
                        self.interceptedBy = safetyPlayer
                    else:
                        self.interceptedBy = coveringDefender
                    if self.interceptedBy:
                        self.insights['pass']['interceptedBy'] = self.interceptedBy.name
                        if hasattr(self.interceptedBy, 'stat_tracker'):
                            self.interceptedBy.stat_tracker.add_defensive_int(self.game.isRegularSeasonGame)
                    self.playResult = PlayResult.Interception
                # Check for catch
                elif outcomeRoll <= (catchProbs['intProb'] + catchProbs['catchProb']):
                    # COMPLETION!
                    self.receiver.addRcvPassTarget(self.game.isRegularSeasonGame)
                    
                    # Calculate air yards based on throw quality
                    passYards = self.calculatePassYardage(self.passType)
                    passYards = min(passYards, self.yardsToEndzone)
                    
                    # ── Three-gate YAC model ──
                    # Gate A: Slip the first defender (WR agility vs covering CB tackling)
                    # Gate B: Open field (WR speed vs deep safety help)
                    # Sideline routes still cap YAC via discipline (receiver heads
                    # for the boundary instead of upfield).
                    yac = 0
                    if passYards < self.yardsToEndzone:
                        # Bad throws can't be caught in stride — limits all YAC.
                        if throwQuality >= 80:
                            throwYacMult = 1.0
                        elif throwQuality >= 60:
                            throwYacMult = 0.75
                        elif throwQuality >= 40:
                            throwYacMult = 0.45
                        else:
                            throwYacMult = 0.20

                        # Sideline cap from receiver discipline (heads for boundary).
                        if self.targetSideline:
                            rcvDisc = self.receiver.attributes.discipline
                            if rcvDisc >= 85:
                                sidelineCap = 5
                            elif rcvDisc >= 75:
                                sidelineCap = 8
                            elif rcvDisc >= 70:
                                sidelineCap = 12
                            else:
                                sidelineCap = 16
                        else:
                            sidelineCap = 99

                        # Covering defender tackling rating — falls back to team
                        # coverage if no individual matchup is available.
                        if coveringDefender:
                            covAttrs = coveringDefender.attributes.getDefensiveAttributes(coveringDefender.position)
                            slipDef = covAttrs.get('tackling', catchDefCoverage)
                            slipDef += self._defenderMentalMod(coveringDefender)
                        else:
                            slipDef = catchDefCoverage

                        # Per-tier YAC ceilings. Short routes have the most open
                        # field opportunity (screens, slants); deeper routes are
                        # caught with defenders converging, so the chase-down
                        # outcome caps tighter. Mirrors the run game's bounded
                        # gate yardage — no stage can produce unbounded YAC.
                        yacCaps = {
                            PassType.short:    {'gateAFail': 3, 'gateAPass': 6, 'gateBFail': 8,  'housecallMean': 12},
                            PassType.medium:   {'gateAFail': 3, 'gateAPass': 6, 'gateBFail': 10, 'housecallMean': 12},
                            PassType.long:     {'gateAFail': 3, 'gateAPass': 6, 'gateBFail': 12, 'housecallMean': 14},
                            PassType.deep:     {'gateAFail': 3, 'gateAPass': 6, 'gateBFail': 15, 'housecallMean': 14},
                            PassType.hailMary: {'gateAFail': 2, 'gateAPass': 5, 'gateBFail': 10, 'housecallMean': 10},
                        }
                        caps = yacCaps.get(self.passType, yacCaps[PassType.medium])

                        # GATE A — slip the first tackler (agility).
                        # Coefficient softened from 1.3 to 0.9 to compress
                        # attribute-delta amplification on mature rosters.
                        slipPower = (self.receiver.gameAttributes.agility * 1.3 +
                                     self.receiver.gameAttributes.playMakingAbility * 0.5 +
                                     self.receiver.gameAttributes.routeRunning * 0.2) / 2
                        slipPower += receiverPressureMod
                        slipExec = (4 if throwQuality >= 75 else 0) + (4 if self.selectedTarget['openness'] >= 70 else 0)
                        gateAChance = max(8, min(45, 22 + (slipPower - slipDef) * 0.9 + slipExec))

                        # GATE B — open field (speed vs deep coverage).
                        rcvSpeed = (self.receiver.gameAttributes.speed * 1.7 +
                                    self.receiver.gameAttributes.playMakingAbility * 0.3) / 2
                        openFieldDef = self.defense.defensePassCoverageRating * 0.95
                        gateBChance = max(6, min(35, 20 + (rcvSpeed - openFieldDef) * 0.9))

                        def _capYac(gain, hardCap):
                            gain = int(gain * throwYacMult)
                            return max(0, min(gain, hardCap, sidelineCap, self.yardsToEndzone - passYards - yac))

                        if batched_randint(1, 100) > gateAChance:
                            # Tackled by covering defender — clamped 0-3 YAC
                            yac += _capYac(max(0, int(np.random.normal(1.5, 1.0))), caps['gateAFail'])
                        else:
                            # Slipped the tackle — clamped 2-6 YAC
                            yac += _capYac(max(2, int(np.random.normal(4.0, 1.5))), caps['gateAPass'])
                            if (passYards + yac) < self.yardsToEndzone and not self.targetSideline:
                                if batched_randint(1, 100) > gateBChance:
                                    # Safety angles WR off — clamped per tier
                                    yac += _capYac(max(3, int(np.random.normal(7.0, 2.5))), caps['gateBFail'])
                                else:
                                    # Housecall — exponential tail, bounded by remaining field
                                    remYards = self.yardsToEndzone - passYards - yac
                                    yac += min(remYards, max(8, int(np.random.exponential(caps['housecallMean']) * throwYacMult)))

                    self.yardage = passYards + yac
                    if self.yardage > self.yardsToEndzone:
                        yac = self.yardsToEndzone - passYards
                        self.yardage = self.yardsToEndzone

                    self.insights['pass']['airYards'] = passYards
                    self.insights['pass']['yac'] = yac

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
                            # Track per-WR yards for halftime CB swap
                            if self.receiver == self.offense.rosterDict.get('wr1'):
                                self.game.homeHalfWr1Yards += self.yardage
                            elif self.receiver == self.offense.rosterDict.get('wr2'):
                                self.game.homeHalfWr2Yards += self.yardage
                        else:
                            self.game.awayHalfPassYards += self.yardage
                            if self.receiver == self.offense.rosterDict.get('wr1'):
                                self.game.awayHalfWr1Yards += self.yardage
                            elif self.receiver == self.offense.rosterDict.get('wr2'):
                                self.game.awayHalfWr2Yards += self.yardage

                    # Confidence boosts based on play quality
                    confBoost = 0.005 if throwQuality >= 70 else 0.003
                    self.passer.updateInGameConfidence(confBoost)
                    self.receiver.updateInGameConfidence(confBoost)
                    self.defense.updateInGameConfidence(-confBoost)
                    self.isPassCompletion = True
                    
                    # Per-player defensive stat: covering defender gets tackle on completion
                    isReg = self.game.isRegularSeasonGame
                    if coveringDefender and hasattr(coveringDefender, 'stat_tracker'):
                        coveringDefender.stat_tracker.add_tackle(isReg)
                    # Safety gets tackle on longer completions (deep help / last line)
                    safetyPlayer = coverageAssignments.get('rb')
                    if safetyPlayer and hasattr(safetyPlayer, 'stat_tracker') and self.yardage >= 15:
                        safetyPlayer.stat_tracker.add_tackle(isReg)

                    # Fumble on catch — defender strips the ball on the tackle
                    primaryTackler = coveringDefender
                    if safetyPlayer and self.yardage >= 15:
                        primaryTackler = safetyPlayer  # Safety made the tackle on deep plays
                    # Surface tackler so play text can credit the defender
                    self.tackledBy = primaryTackler
                    if primaryTackler and self.isInBounds and batched_randint(1, 100) > 97:
                        # ~3% chance of fumble on catch — only in bounds; a
                        # receiver who steps out of bounds can't be stripped
                        # (the play is dead at the boundary).
                        rcvFumbleResist = round(self.receiver.gameAttributes.power * 0.7 + self.receiver.gameAttributes.discipline * 0.3)
                        defStripAbility = 70
                        if hasattr(primaryTackler, 'attributes'):
                            defAttrs = primaryTackler.attributes.getDefensiveAttributes(primaryTackler.position)
                            defStripAbility = defAttrs.get('tackling', 70)
                            defStripAbility += self._defenderMentalMod(primaryTackler)
                        if (defStripAbility + batched_randint(-5, 5)) >= (rcvFumbleResist + batched_randint(-5, 5)):
                            # Ball is out. Credit the forced fumble regardless of
                            # who recovers, then run a recovery contest so the
                            # offense can fall on it — same as a run fumble,
                            # instead of every strip being an automatic turnover.
                            self.isFumble = True
                            self.forcedFumbleBy = primaryTackler
                            if hasattr(self.receiver, 'stat_tracker'):
                                self.receiver.stat_tracker.add_receiving_fumble(isReg)
                            if hasattr(primaryTackler, 'stat_tracker'):
                                primaryTackler.stat_tracker.add_forced_fumble(isReg)
                            rcvRecoveryMod = self.receiver.attributes.getPressureModifier(self.game.gamePressure)
                            if (self.defense.defensePassCoverageRating + batched_randint(-5, 5)) >= \
                               (self.receiver.gameAttributes.overallRating + rcvRecoveryMod + batched_randint(-5, 5)):
                                self.receiver.updateInGameConfidence(-.02)
                                self.defense.updateInGameConfidence(.02)
                                self.defense.gameDefenseStats['fumRec'] += 1
                                self.isFumbleLost = True
                                self.playResult = PlayResult.Fumble

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
                    # INCOMPLETE (missed throw / coverage disruption)
                    self.passer.addMissedPass(self.game.isRegularSeasonGame)
                    self.defense.updateInGameConfidence(.003)
                    self.passer.updateInGameConfidence(-.003)
                    self.yardage = 0
                    # Credit covering defender with pass breakup
                    if coveringDefender and hasattr(coveringDefender, 'stat_tracker'):
                        coveringDefender.stat_tracker.add_pass_breakup(self.game.isRegularSeasonGame)
                    # Safety gets pass breakup on deep incomplete passes (deep help)
                    if self.passType in (PassType.long, PassType.hailMary):
                        safetyPlayer = coverageAssignments.get('rb')
                        if safetyPlayer and hasattr(safetyPlayer, 'stat_tracker'):
                            safetyPlayer.stat_tracker.add_pass_breakup(self.game.isRegularSeasonGame)

        # Diagnostic: log every Hail Mary attempt with outcome so we can audit
        # success rates over many seasons. Use the play-level flag (not
        # self.passType) so sacks — which short-circuit before passType is set
        # — are still counted.
