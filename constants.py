# Game Constants
GAME_MAX_PLAYS = 132
PLAYS_TO_FOURTH_QUARTER = 100
PLAYS_TO_THIRD_QUARTER = 66
FOURTH_QUARTER_START = 100

# Rating System Constants
RATING_SCALE_MIN = 60
RATING_SCALE_MAX = 100
RATING_RANGE = 40  # (RATING_SCALE_MAX - RATING_SCALE_MIN)
STARS_MAX = 4
STARS_MIN = 1

# Pressure Calculations
PRESSURE_BASE = 20
PRESSURE_MAX_ADDITIONAL = 20
PRESSURE_CALCULATION_DIVISOR = 33

# Probability Calculations
ELO_DIVISOR = 400
FIELD_LENGTH = 100

# Player Development
MIN_ATTRIBUTE_VALUE = 60
MAX_ATTRIBUTE_VALUE = 100

# Random Generation Ranges
TIER_S_MIN = 95
TIER_S_MAX = 100
TIER_D_MIN = 60
TIER_D_MAX = 74

# Performance Calculations
PERCENTAGE_MULTIPLIER = 100

# Skill Rating Calculations
OFFENSE_CONTRIBUTION_WEIGHT = 0.6
DEFENSE_CONTRIBUTION_WEIGHT = 0.4
STAGE1_OFFENSE_WEIGHT = 0.9
STAGE2_SPEED_AGILITY_WEIGHT = 1.2

# Normalization factors for different calculations
NORMALIZATION_FACTOR = 100

# Game clock
QUARTER_SECONDS = 900           # 15 minutes per quarter
KNEEL_DRAIN_SECONDS = 40        # Clock seconds consumed by a kneel play
SPIKE_CLOCK_THRESHOLD = 120     # Seconds remaining that triggers a spike consideration
TIMEOUT_CLOCK_THRESHOLD = 120   # Seconds remaining that triggers timeout / end-of-half FG logic

# Field & scoring rules
FG_SNAP_DISTANCE = 17           # Yards added to line-of-scrimmage for snap + hold on FG attempts
FG_MIN_ATTEMPT_PROB = 0.20      # Coaches attempt FG if estimated make probability >= 20% (replaces hard ratio cutoff)
YARDS_TO_FIRST_DOWN = 10        # Standard yards needed for a first down
CLOSE_GAME_SCORE_THRESHOLD = 8  # Point differential considered a close game for late-game strategy

# Clutch/Choke thresholds
CLUTCH_PRESSURE_THRESHOLD = 50    # Min gamePressure (0-100) for clutch/choke consideration
CLUTCH_MODIFIER_THRESHOLD = 2.0   # Min keyPressureMod for clutch
CHOKE_MODIFIER_THRESHOLD = 1.5    # Min abs(keyPressureMod) for choke
CLUTCH_WPA_THRESHOLD = 6.0        # Min WPA% impact for clutch plays
CHOKE_WPA_THRESHOLD = 5.0         # Min WPA% impact for choke plays

# Momentum system
MOMENTUM_DECAY_RATE = 0.03              # Per-play decay toward neutral
MOMENTUM_BLOWOUT_DECAY_RATE = 0.08     # Accelerated decay in blowouts (22+ diff)
MOMENTUM_MIDGAP_DECAY_RATE = 0.05      # Moderate decay (15-21 diff)
MOMENTUM_CASCADE_STEP = 0.15           # Multiplier increase per consecutive streak event
MOMENTUM_MAX_CASCADE = 1.6             # Max cascade multiplier (streak of 5)
MOMENTUM_MAX_STREAK = 5                # Max consecutive streak count
MOMENTUM_EFFECT_BASE = 0.005           # Per-play confidence/determination nudge at momentum=50
MOMENTUM_EFFECT_CAP = 0.01             # Hard cap on per-play nudge magnitude
MOMENTUM_NEUTRAL_ZONE = 10             # Abs momentum below this = no gameplay effect
MOMENTUM_SHIFT_THRESHOLD = 14          # Min abs delta for momentum shift highlight (against-the-grain only)
MOMENTUM_CROSS_ZERO_THRESHOLD = 8      # Min abs delta when crossing zero for highlight
MOMENTUM_DISPLAY_THRESHOLD = 5         # Min abs momentum to broadcast a team as having it

# Momentum event deltas (raw, before dampening)
MOMENTUM_TD = 20
MOMENTUM_TURNOVER = 18
MOMENTUM_SAFETY = 18
MOMENTUM_TURNOVER_ON_DOWNS = 12
MOMENTUM_FG_MISSED = 10
MOMENTUM_FG_MADE = 8
MOMENTUM_SACK = 6
MOMENTUM_BIG_PLAY_BONUS = 5
MOMENTUM_PUNT = 4

# Play selection
RECEIVER_MATCHUP_SCALE = 50.0   # Divisor when computing receiver-vs-coverage matchup weight delta

# Coach attribute scaling
COACH_ATTR_NEUTRAL = 80         # Attribute value with zero effect (midpoint of 60-100 range)
COACH_ATTR_RANGE = 20           # Half-range used to normalise coach attributes to [-1, 1]
COACH_OFFENSIVE_MIND_FLOOR = 60 # offensiveMind below this value gives zero matchup weighting

# Floobits Economy — earning amounts
CLINCH_PLAYOFF_REWARD = 25
CLINCH_TOPSEED_REWARD = 50
FLOOSBOWL_WIN_REWARD = 150

WEEKLY_LEADERBOARD_PRIZES = {1: 30, 2: 20, 3: 15}
WEEKLY_LEADERBOARD_TOP_PCT_PRIZE = 5
WEEKLY_LEADERBOARD_TOP_PCT = 0.25

SEASON_LEADERBOARD_PRIZES = {1: 200, 2: 125, 3: 75}
SEASON_LEADERBOARD_TOP_PCT_PRIZE = 25
SEASON_LEADERBOARD_TOP_PCT = 0.25

SEASON_FP_PAYOUT_DIVISOR = 25  # 1 Floobit per N FP

# Power-Up Shop
POWERUP_EXTRA_SWAP = {
    "slug": "extra_swap",
    "displayName": "Dispensation",
    "description": "+1 roster swap to make an additional player change.",
    "price": 35,
}
POWERUP_MODIFIER_NULLIFIER = {
    "slug": "modifier_nullifier",
    "displayName": "Annulment",
    "description": "Your cards operate under Steady (no modifier effect) this week.",
    "price": 60,
}
POWERUP_TEMP_FLEX = {
    "slug": "temp_flex",
    "displayName": "Conscription",
    "description": "Adds a FLEX roster slot (any position) for 4 weeks.",
    "price": 200,
    "durationWeeks": 4,
    "seasonLimit": 2,
}
POWERUP_SHOP_REROLL = {
    "slug": "shop_reroll",
    "displayName": "Requisition",
    "description": "Regenerates your featured shop cards.",
    "price": 30,
}
POWERUP_TEMP_CARD_SLOT = {
    "slug": "temp_card_slot",
    "displayName": "Accession",
    "description": "Adds a 6th card equipment slot for 4 weeks.",
    "price": 200,
    "durationWeeks": 4,
    "seasonLimit": 2,
}

POWERUP_FORTUNES_FAVOR = {
    "slug": "fortunes_favor",
    "displayName": "Patronage",
    "description": "Boosts all chance card trigger rates by 10% for 3 weeks.",
    "price": 125,
    "durationWeeks": 3,
    "seasonLimit": 2,
}

POWERUP_CATALOG = {
    "extra_swap": POWERUP_EXTRA_SWAP,
    "modifier_nullifier": POWERUP_MODIFIER_NULLIFIER,
    "temp_flex": POWERUP_TEMP_FLEX,
    "temp_card_slot": POWERUP_TEMP_CARD_SLOT,
    "shop_reroll": POWERUP_SHOP_REROLL,
    "fortunes_favor": POWERUP_FORTUNES_FAVOR,
}

# Swap cycle length (weeks) — used for All-Pro grant cadence and testing-mode daily limits
SWAP_CYCLE_WEEKS = 7

# Daily refresh boundary for SCHEDULED mode (UTC hour).
# The "floosball day" rolls over at this hour so daily limits and shop refreshes
# don't clash with live games.  10 AM UTC = 5 AM EST / 6 AM EDT — safely between
# the last game ending (~midnight UTC) and the first game starting (5 PM UTC / noon ET).
DAILY_RESET_HOUR_UTC = 10

# ─── GM Mode ────────────────────────────────────────────────────────────────────

GM_VOTE_TYPES = {"fire_coach", "cut_player", "resign_player", "sign_fa", "hire_coach"}

# Cost per vote (Floobits)
GM_VOTE_COST = {
    "fire_coach": 15,
    "cut_player": 10,
    "resign_player": 10,
    "sign_fa": 12,
    "hire_coach": 10,
}

# Action weight for threshold calculation
GM_VOTE_WEIGHT = {
    "fire_coach": 1.5,
    "cut_player": 1.0,
    "resign_player": 0.75,
    "sign_fa": 1.0,
    "hire_coach": 1.0,
}

# Base minimum votes required (floor of threshold)
GM_VOTE_BASE_MIN = {
    "fire_coach": 3,
    "cut_player": 2,
    "resign_player": 2,
    "sign_fa": 2,
    "hire_coach": 2,
}

# Per-user limits
GM_VOTES_PER_SEASON = 20
GM_VOTES_PER_TYPE = 8
GM_VOTES_PER_TARGET = 5

# FA ballot
GM_FA_BALLOT_COST = 15
GM_FA_BALLOT_MAX_RANKINGS = 18  # 6 roster slots × 3 ranked candidates each

# FA voting window duration (seconds)
GM_FA_WINDOW_FAST = 30
GM_FA_WINDOW_SEQUENTIAL = 180  # 3 minutes (for testing)
GM_FA_WINDOW_SCHEDULED = 64800  # 18 hours

# Threshold formula: threshold = max(baseMin, ceil(engagedFans * factor * weight))
# "Engaged fans" = users with favorite_team_id who cast ≥1 GM vote this season
GM_THRESHOLD_USER_FACTOR = 0.35

# Probability: at threshold = 45%, linear to 95% at 2x threshold
GM_PROB_BASE = 0.45
GM_PROB_RANGE = 0.50
GM_PROB_CAP = 0.95

# Minimum ballot appearance rate for a player to be an eligible directive target
GM_FA_MIN_APPEARANCE_PCT = 0.25

# Coach pool
GM_COACH_POOL_SIZE = 5

# ─── Pick-Em ("Prognostications") ────────────────────────────────────────────

PICKEM_CORRECT_REWARD = 5           # (Legacy) Floobits per correct pick
PICKEM_CLAIRVOYANT_THRESHOLD = 96    # Points threshold for Clairvoyant bonus (e.g. 12 games × 8 pts = all correct by Q1)
PICKEM_CLAIRVOYANT_BONUS = 25       # Bonus Floobits when threshold is met

# Points-based system (v2)
PICKEM_BASE_POINTS = 10              # Max points per correct pick (pre-game)
PICKEM_QUARTER_MULTIPLIERS = {       # Multiplier by game quarter at time of pick
    0: 1.0,   # Pre-game (Scheduled status)
    1: 0.8,   # Q1
    2: 0.6,   # Q2
    3: 0.4,   # Q3
    4: 0.2,   # Q4
    5: 0.1,   # OT
}
PICKEM_POINTS_TO_FLOOBITS = 0.5     # 1 point = 0.5 Floobits
PICKEM_WEEKLY_PRIZES = {1: 15, 2: 10, 3: 5}
PICKEM_WEEKLY_TOP_PCT = 0.25
PICKEM_WEEKLY_TOP_PCT_PRIZE = 3
PICKEM_SEASON_PRIZES = {1: 75, 2: 50, 3: 25}
PICKEM_SEASON_TOP_PCT = 0.25
PICKEM_SEASON_TOP_PCT_PRIZE = 10