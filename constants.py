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
MOMENTUM_NEUTRAL_ZONE = 5              # Abs momentum below this = no gameplay effect
MOMENTUM_SHIFT_THRESHOLD = 14          # Min abs delta for momentum shift highlight (against-the-grain only)
MOMENTUM_CROSS_ZERO_THRESHOLD = 8      # Min abs delta when crossing zero for highlight
MOMENTUM_DISPLAY_THRESHOLD = 5         # Min abs momentum to broadcast a team as having it (matches NEUTRAL_ZONE so UI never lies about mechanical impact)

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

ROSTER_SWAP_COST = 15          # Base cost per swap (escalates per slot)
ROSTER_SWAP_COST_INCREMENT = 15  # Additional cost per previous swap in the same slot

# Minimum player count required to lock a roster. /remove also enforces
# this floor — caps the "gut your roster to ride Drought/Hedge/Home Alone
# unbounded" exploit without taking partial-roster flexibility off the
# table. Auto-lock at game start picks up anyone meeting the floor.
# Next-season raises this to 3 — combined with the no-duplicate-effects
# rule it forces real roster construction instead of letting players
# coast on a kicker plus one scorer.
ROSTER_MIN_PLAYERS = 3

# Weekly FP → Floobits conversion (participation reward).
# Tapering power curve: F = round(SCALE * FP^EXPONENT), no hard cap. Big
# weeks always pay more than small weeks, but with diminishing returns so
# the system can't run away. Tunable knobs:
#   SCALE     — overall payout scale (raises floor + ceiling together)
#   EXPONENT  — taper aggressiveness (closer to 1.0 = less taper)
# Curve tightened after card rebalance pushed typical hands to 1k-3k FP,
# then bumped ~33% across the board in v0.16.1 — payouts felt too thin
# relative to pack prices. Shape (exponent) unchanged so the high-end
# taper still prevents runaway whales while floors and middle play
# benefit too. Sample profile (default):
#   100 FP →  16 F
#   500 FP →  54 F
#  1000 FP →  93 F
#  3000 FP → 217 F
WEEKLY_FP_FLOOBIT_SCALE = 0.43
WEEKLY_FP_FLOOBIT_EXPONENT = 0.78
# Endowment (income_boost powerup) replaces the curve with a flatter one.
# Less taper = monster weeks pay more; low weeks pay roughly the same.
# Same cost (100 F). Sits ~10% above standard at modest play, ~50% above
# at heavy play, breaking even around 1k FP/week × 4 weeks. Bumped
# proportionally with the standard curve.
WEEKLY_FP_FLOOBIT_BOOSTED_SCALE = 0.27
WEEKLY_FP_FLOOBIT_BOOSTED_EXPONENT = 0.87

DEFAULT_FUNDING_PCT = 25  # Default % of unspent floobits contributed at season end

# ---- Team Funding (Patronage) ----
FUNDING_DECAY_RATE = 0.5                # 50% carry-forward of previous effective funding
FUNDING_BASELINE_PER_TEAM = 200             # League baseline revenue every team receives at season start
# Tiers are assigned by a team's share of total league funding. A team's
# ratio = effective_funding / (total_league_funding / num_teams). That is,
# "how many fair-shares of the league's floobits does this team hold?"
# Self-scaling: as the economy inflates, fair-share inflates with it, so
# MEGA/LARGE always mean "meaningfully ahead of the rest of the league today"
# rather than a fixed floobit target that decays in value.
FUNDING_TIER_NAMES = ['MEGA_MARKET', 'LARGE_MARKET', 'MID_MARKET', 'SMALL_MARKET']
# Multipliers of league fair-share (total funding / team count).
FUNDING_TIER_THRESHOLDS = {
    'MEGA_MARKET':  2.0,   # ≥ 2× the average team's funding
    'LARGE_MARKET': 1.15,  # ≥ 15% above average
    'MID_MARKET':   0.85,  # within ±15% of average
    'SMALL_MARKET': 0.0,   # below 85% of average — genuinely fallen behind the pack
}
# Market-tier compression: keep the flavor (MEGA still feels prestigious,
# SMALL still feels scrappy), but shrink the mechanical advantages so
# tier doesn't compound into a runaway gap year over year. Dev / morale
# / fatigue benefits roughly halved from the original spread.
FUNDING_DEV_BONUS = {'MEGA_MARKET': 1, 'LARGE_MARKET': 1, 'MID_MARKET': 0, 'SMALL_MARKET': -1}
FUNDING_MORALE_MODIFIER = {'MEGA_MARKET': 0.0075, 'LARGE_MARKET': 0.0025, 'MID_MARKET': -0.0025, 'SMALL_MARKET': -0.0075}
FUNDING_FATIGUE_REDUCTION = {'MEGA_MARKET': 0.30, 'LARGE_MARKET': 0.15, 'MID_MARKET': 0.0, 'SMALL_MARKET': -0.10}

# ---- Market Expectation Scaling ----
# Bigger markets carry heavier "expectations to win" pressure on top of
# whatever the team's prior performance has earned. Smaller markets are more
# forgiving when the team underperforms (less media spotlight, less fan
# rage). Applied at game time as an asymmetric scalar on the delta of
# team.pressureModifier from baseline (1.0):
#   - positive delta (high expectations from prior playoff success, etc.)
#     is scaled up for big markets — MEGA's win-it-all expectations weigh
#     more than a SMALL team's same on-paper expectation.
#   - negative delta (low expectations from a bad prior season) is scaled
#     up for SMALL markets — small markets disengage and stop watching, big
#     markets keep the spotlight on even during a rebuild.
# Effect at game time:
#   delta = team.pressureModifier - 1.0
#   if delta > 0:  scaled = delta * EXPECTATION_SCALE[tier]
#   else:          scaled = delta * (2.0 - EXPECTATION_SCALE[tier])
#   effectivePressureMod = 1.0 + scaled
EXPECTATION_SCALE_BY_TIER = {
    'MEGA_MARKET':  1.5,
    'LARGE_MARKET': 1.2,
    'MID_MARKET':   1.0,
    'SMALL_MARKET': 0.7,
}

# Relief side: when the team's prior baseline is below 1.0 (bad season last
# year, eliminated mid-season, etc.), how much that relief gets amplified by
# market tier. Big markets keep the spotlight on even during a rebuild
# (less relief); small markets disengage entirely (much more relief).
# Replaces the prior `(2 - tierScale)` inverse, which gave too narrow a
# spread (LARGE 0.8, SMALL 1.3) — diagnostic showed LARGE/SMALL barely
# differed from MID in the relief direction.
EXPECTATION_RELIEF_BY_TIER = {
    'MEGA_MARKET':  0.4,
    'LARGE_MARKET': 0.65,
    'MID_MARKET':   1.0,
    'SMALL_MARKET': 1.6,
}

# Championship-band softening: delta above this threshold (i.e. baselines
# above 2.0 — Floos Bowl 2.5, brink-of-elimination 2.0, deep playoff round
# 1.9+) gets a much weaker market scale. Without softening, MEGA Floos Bowl
# hits 3.25 which caps in-game pressure at 100 on every play. Overflow
# portion of the delta uses CHAMPIONSHIP_OVERFLOW_FACTOR instead of the
# full tier scale.
EXPECTATION_DELTA_CAP = 1.0
CHAMPIONSHIP_OVERFLOW_FACTOR = 1.0  # overflow unscaled — preserves nominal
                                     # baseline so MEGA/MID/SMALL keep the
                                     # right ordering at the top end.

# ---- Streak Pressure ----
# Pressure that builds as a team's consecutive-win streak grows. Active in
# both regular season and playoffs — an undefeated team chasing a perfect
# season feels the spotlight, and that spotlight follows them through the
# postseason. Resets to 0 on any loss.
#   streakPressure = min(CAP, max(0, streak - FLOOR) * PER_WIN)
# Added to team.pressureModifier at game-time scaling, so market-tier
# amplification applies (MEGA on a 10-win streak gets a heavier scaled
# bump than SMALL on the same streak).
STREAK_PRESSURE_FLOOR   = 3      # streaks 1-3 add nothing (normal hot start)
STREAK_PRESSURE_PER_WIN = 0.10   # each win past the floor adds +0.10
STREAK_PRESSURE_CAP     = 0.80   # caps at streak 11+ to avoid runaway

# ---- Form-state Per-game Rating Multiplier ----
# Applied to in-game player attributes at kickoff based on the team's current
# form state. Multiplier acts on physical + skill-related mental attrs, then
# derived ratings (skillRating, xFactor, overallRating) are recalculated. The
# form-state label users see now has actual mechanical bite — COMPLACENT teams
# really do drop a few games they should win, RESOLUTE teams really do play
# above their record, etc.
#
# Magnitudes:
#   1.03 ≈ +3% on attrs ≈ +2-3 rating points (RESOLUTE Cinderella boost)
#   0.96 ≈ -4% on attrs ≈ -3-4 rating points (COMPLACENT trap-game risk)
#   0.95 ≈ -5% on attrs ≈ -4-5 rating points (SPIRALING broken / can't get out
#         of own way)
# Rubber-band tilt: COMPLACENT bites the dominant teams harder,
# RESOLUTE lifts the gritty losers a bit more, and SPIRALING is
# softened so a struggling team isn't trapped in a doom-loop. Nudges
# are 1-2 points each — subtle on any single game, additive over a
# season. Surfaces through the existing form-state badge; no new UI.
FORM_STATE_RATING_MULT = {
    'HOT_STREAK':  1.00,   # Already winning — no extra boost
    'GETTING_HOT': 1.00,   # Was 1.02 — selection effect already gives these
                           # teams +14pp lift over expected, so no extra mult
    'STEADY':      1.00,
    'SHAKY':       0.985,  # Mild slip
    'COOLING_OFF': 0.96,   # Was 0.97 — slightly stronger fade
    'COMPLACENT':  0.92,   # Was 0.93 — slightly more bite on elite teams
    'SPIRALING':   0.99,   # Was 0.97 — disposition-analyzer data showed 28x
                           # higher SPIRALING incidence on underdogs vs
                           # favorites (39% vs 1.4%), so the multiplier was
                           # double-counting the ELO signal. Cut to -1% so
                           # the form badge still surfaces a real condition
                           # without compounding the pre-game skill gap.
    'RESOLUTE':    1.04,   # Was 1.03 — slightly stronger Cinderella lift
    'UNKNOWN':     1.00,
}

# ---- Prospect Pipeline ----
# Prospects are drafted rookies stashed on the team's pipeline (not roster-eligible).
# They develop each offseason via offseasonTraining(), same as active players, and
# are eligible for promotion when a starter slot opens up.
PROSPECT_SLOT_CAP_PER_POSITION = 2  # Each team may hold at most N prospects per position
PROSPECT_DEVELOPMENT_WINDOW = 3     # Max offseasons a prospect can remain in the pipeline before forced release
PROSPECT_PROMOTION_RATING_THRESHOLD = 70  # Fallback auto-promote if best prospect meets this rating
ROOKIE_DRAFT_CLASS_SIZE = 24        # Rookies generated per season (one per team max)

# ---- Rookie Scouting ----
# Rookie class is generated at season start; fans can scout + vote on prospects
# all season. Scouting accuracy = coach.scouting + funding tier bonus, and
# determines how wide the potential-attribute range is in the scouted view.
# Scouting band → potential attribute ± range (wider = less certain):
SCOUTING_BANDS = [
    (95, 0),    # ≥95: exact value
    (80, 5),    # 80-94: ±5
    (65, 10),   # 65-79: ±10
    (0, 15),    # <65: ±15
]
FUNDING_SCOUTING_BONUS = {'MEGA_MARKET': 5, 'LARGE_MARKET': 3, 'MID_MARKET': 0, 'SMALL_MARKET': -3}
# Rookie draft vote — reuses existing GM_VOTE_COST/GM_VOTES_PER_SEASON infra
GM_ROOKIE_DRAFT_MAX_RANKINGS = 12  # Fans may rank up to this many rookies

# ---- Retirement Risk Telegraphing ----
# Surfaces during the season so fans can pre-vote replacements. Mirrors the
# actual retirement rolls in seasonManager._evaluateRetirementCandidates.
# Tiers: 'safe' | 'possible' | 'likely' | 'very_likely' | 'retiring' (locked)
# Retirements only fire for players whose contract expires this offseason.
RETIREMENT_HIGH_AGE_SEASONS = 15    # 90% chance on walk year
RETIREMENT_MID_AGE_SEASONS = 10     # 65% chance on walk year
RETIREMENT_EARLY_AGE_SEASONS = 7    # 5% chance on walk year

# ---- Player Fatigue ----
# Accumulation rate is unchanged — fatigue gauge still climbs visibly
# across the season for the fan UI. What changed: PHYSICAL_IMPACT is
# softened so each fatigue point hits performance less hard. End-of-
# season tired stars feel tired, not broken.
BASE_FATIGUE_PER_WEEK = 0.0025      # 0.25% base fatigue gain per week
FATIGUE_RESILIENCE_SCALE = 0.8      # How much resilience reduces fatigue rate
FATIGUE_RESILIENCE_CEILING = 1.4    # Max multiplier for low-resilience players
FATIGUE_PHYSICAL_IMPACT = 0.6       # Was 1.0 — softened so fatigue is less punishing
FATIGUE_MENTAL_IMPACT = 0.2         # Was 0.3 — softened to match

# Mental / form / fatigue modifiers can compound multiplicatively into a
# heavy reduction on a high-rated player's effective rating. The soft floor
# below caps that aggregate so a star never drops more than (1 - ratio) of
# their baseline gameAttributes overall rating, even if every modifier
# stacks negative. Trades off some narrative extremes for fewer
# "great player had a nightmare game with no visible cause" outcomes.
MENTAL_FLOOR_RATIO = 0.85           # 15% max aggregate reduction from baseline

# League compression — at game start, every rostered player's in-game
# attributes get pulled toward the league mean by this factor. A 95-rated
# player effectively plays as ~90.5; a 65 plays as ~69.5. Closes the
# auto-win gap without erasing skill order. Profile ratings stay
# untouched; only `gameAttributes` is compressed. Set factor=1.0 to
# disable.
LEAGUE_COMPRESSION_FACTOR = 0.7     # 1.0 = no compression, 0.5 = aggressive
LEAGUE_COMPRESSION_MEAN = 80        # Center of the curve

# Power-Up Shop
POWERUP_EXTRA_SWAP = {
    "slug": "extra_swap",
    "displayName": "Dispensation",
    "description": "+1 roster swap to make an additional player change.",
    "price": 50,
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

POWERUP_INCOME_BOOST = {
    "slug": "income_boost",
    "displayName": "Endowment",
    "description": "Bumps your weekly FP-to-Floobits curve to a flatter taper for 4 weeks. Big weeks pay more; routine weeks roughly the same.",
    "price": 100,
    "durationWeeks": 4,
    "seasonLimit": 2,
    # Endowment swaps the SCALE/EXPONENT pair. The flatter curve trades a
    # small dip on low-FP weeks for a meaningful bump on monster weeks
    # (e.g. 500 FP: 67 F normal → 73 F endowment; 1000 FP: 121 → 142;
    # 5000 FP: 474 → 653).
    "boostedScale": WEEKLY_FP_FLOOBIT_BOOSTED_SCALE,
    "boostedExponent": WEEKLY_FP_FLOOBIT_BOOSTED_EXPONENT,
}

POWERUP_CATALOG = {
    "extra_swap": POWERUP_EXTRA_SWAP,
    "modifier_nullifier": POWERUP_MODIFIER_NULLIFIER,
    "temp_flex": POWERUP_TEMP_FLEX,
    "temp_card_slot": POWERUP_TEMP_CARD_SLOT,
    "fortunes_favor": POWERUP_FORTUNES_FAVOR,
    "income_boost": POWERUP_INCOME_BOOST,
}

# Shop reroll (not a powerup — lives in the Daily Selection section)
SHOP_REROLL_BASE_COST = 10
SHOP_REROLL_COST_INCREMENT = 10  # Each reroll costs 10 more than the last

# Themed pack rotation reroll — pricier than featured-card reroll because
# the rotation pool now includes Grand (350F) and Exquisite (750F) packs.
# Rerolling for an exquisite roll should be a real commitment.
THEMED_PACK_REROLL_BASE_COST = 50
THEMED_PACK_REROLL_COST_INCREMENT = 30

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

# Per-user limits.
# GM_VOTES_PER_TYPE caps how many votes a single fan can spend on one vote
# type per season. Coach votes (fire/hire) cap at 4 — there's only one
# coach to deal with, so more budget there is wasted. Player votes
# (resign/cut) cap at 8 because a team often has multiple candidates worth
# voting on, and fans need to spread their support.
GM_VOTES_PER_SEASON = 20
GM_VOTES_PER_TYPE = {
    "fire_coach":     4,
    "hire_coach":     4,
    "resign_player":  8,
    "cut_player":     8,
    "sign_fa":        8,
}
GM_VOTES_PER_TYPE_DEFAULT = 4
GM_VOTES_PER_TARGET = 4

# Front Office voting window opens at this week. Before this, GM vote UIs show
# a "convening..." state. Mirrors the frontend const GM_ACTIVE_WEEK in
# FrontOfficePanel.tsx — keep them in sync.
GM_ACTIVE_WEEK = 22

# FA ballot
GM_FA_BALLOT_COST = 15
GM_FA_BALLOT_MAX_RANKINGS = 18  # 6 roster slots × 3 ranked candidates each

# Rookie draft ballot — single flat cost (GM_VOTE_COST is a per-type dict and
# doesn't fit here). Slightly cheaper than FA ballot since it's a lower-stakes
# preference than a full FA requisition.
GM_ROOKIE_BALLOT_COST = 10

# FA voting window duration (seconds)
GM_FA_WINDOW_FAST = 30
GM_FA_WINDOW_SEQUENTIAL = 180  # 3 minutes (for testing)
GM_FA_WINDOW_SCHEDULED = 64800  # 18 hours

# Threshold formula: threshold = max(baseMin, ceil(engagedFans * factor * weight))
# "Engaged fans" = users with favorite_team_id who cast ≥1 GM vote this season
GM_THRESHOLD_USER_FACTOR = 0.35

# Probability: at threshold = 45%, linear to 100% at 2x threshold. Hitting
# 2× threshold is the UI-maxed scenario — making that deterministic avoids
# the "I hit the vote ceiling and it still failed" bad UX.
GM_PROB_BASE = 0.45
GM_PROB_RANGE = 0.55
GM_PROB_CAP = 1.0

# Minimum ballot appearance rate for a player to be an eligible directive target
GM_FA_MIN_APPEARANCE_PCT = 0.25

# Coach pool
GM_COACH_POOL_SIZE = 5

# ─── Pick-Em ("Prognostications") ────────────────────────────────────────────

PICKEM_CORRECT_REWARD = 5           # (Legacy) Floobits per correct pick
PICKEM_CLAIRVOYANT_THRESHOLD = 80    # Points threshold for Clairvoyant bonus. Favorites pay <1.0x (0.5/winProb), so a perfect 12-game week scores ~83-103 and most great weeks land 70-90. Was 96 — unreachable, since even a flawless week often fell short. 80 makes a perfect week always clear it and lands ~top 8-13% of strong weeks.
PICKEM_CLAIRVOYANT_BONUS = 35       # Bonus Floobits when threshold is met (was 25, bumped 40% in v0.16.1 economy pass)

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
PICKEM_POINTS_TO_FLOOBITS = 0.65    # 1 point = 0.65 Floobits (was 0.5, bumped 30% in v0.16.1 economy pass)
PICKEM_WEEKLY_PRIZES = {1: 20, 2: 13, 3: 7}    # was {15, 10, 5}
PICKEM_WEEKLY_TOP_PCT = 0.25
PICKEM_WEEKLY_TOP_PCT_PRIZE = 4                 # was 3
PICKEM_SEASON_PRIZES = {1: 100, 2: 65, 3: 33}  # was {75, 50, 25}
PICKEM_SEASON_TOP_PCT = 0.25
PICKEM_SEASON_TOP_PCT_PRIZE = 13                # was 10

# Win-probability multiplier (applies at any pick time)
PICKEM_UNDERDOG_MAX = 3.0           # Max multiplier for extreme underdogs
PICKEM_FAVORITE_MIN = 0.4           # Floor multiplier for heavy favorites
PICKEM_UNDERDOG_EXPONENT = 1.2     # Power applied to underdog multipliers (>1 = EV edge)

# Certainty-adjusted decay
PICKEM_MIN_DECAY_FRACTION = 0.3     # 30% of normal decay applies even in close games


def calculateWinProbMultiplier(pickedWinProb):
    """Calculate payout multiplier from picked team's win probability (0.0-1.0).
    Underdogs (< 50%) get > 1.0x bonus with EV edge via exponent.
    Favorites (> 50%) get < 1.0x penalty at exactly fair odds."""
    baseMult = 0.5 / max(pickedWinProb, 0.01)
    if baseMult > 1.0:
        rawMult = baseMult ** PICKEM_UNDERDOG_EXPONENT
    else:
        rawMult = baseMult
    return round(max(PICKEM_FAVORITE_MIN, min(PICKEM_UNDERDOG_MAX, rawMult)), 2)


def calculateUnderdogMultiplier(homeElo, awayElo, pickedIsHome):
    """Calculate payout multiplier from pre-game ELO.
    Underdogs get up to PICKEM_UNDERDOG_MAX, favorites down to PICKEM_FAVORITE_MIN."""
    eloDiff = homeElo - awayElo
    homeWp = 1.0 / (1.0 + 10 ** (-eloDiff / 400))
    pickedWp = homeWp if pickedIsHome else (1.0 - homeWp)
    return calculateWinProbMultiplier(pickedWp)


def calculateCertaintyMultiplier(quarter, homeWinProb):
    """Calculate points multiplier adjusted for game certainty.
    Close games retain more value; blowouts decay faster. Pre-game always 1.0."""
    if quarter == 0:
        return 1.0
    baseMult = PICKEM_QUARTER_MULTIPLIERS.get(quarter, 0.2)
    certainty = min(1.0, max(0.0, abs(homeWinProb - 50.0) / 50.0))
    fullDecay = 1.0 - baseMult
    effectiveDecay = fullDecay * (PICKEM_MIN_DECAY_FRACTION + (1.0 - PICKEM_MIN_DECAY_FRACTION) * certainty)
    return round(1.0 - effectiveDecay, 2)


# ─── Play Reactions ─────────────────────────────────────────────────────────────
# Six reactions for plays + sideline quotes. UI renders SVG icons (no emoji).

REACTION_TYPES = {"hype", "love", "wow", "laugh", "cry", "mad"}


# ─── Anomaly System / The Cracking ──────────────────────────────────────────────
# The anomaly system has three layers:
#   Layer 1 — universal cosmetic micro-glitches (fires from Stirring up)
#   Layer 2 — personality-flavored cosmetic glitches (fires from Erratic up)
#   Cracking — the dramatic event: a Core takes control and the card-bonus
#              math switches to that Core's signature equation
#
# Layer 1 + Layer 2 are PURE FLAVOR — no mechanical impact regardless of flag.
# This flag gates ONLY the Cracking event itself. When False, the aggregate
# can still climb to threshold and Core warnings/news still fire (visible
# tease), but the trigger is suppressed and the math never swaps.
#
# Roadmap:
#   Season N   (current): False — tease only. Whispers, warnings, glitches,
#                         but no Cracking ever fires.
#   Season N+1 (planned): True  — the payoff. Cracking can actually trigger.
ANOMALY_CRACKING_ENABLED = False
REACTION_TARGET_TYPES = {"play", "sideline_quote"}

# ── Offseason phase-rollback snapshots ────────────────────────────────────────
# Only these phases make non-idempotent mutations (drafts compound picks), so a
# mid-phase restart must roll the DB back to the phase-entry snapshot and re-run
# the phase cleanly. Other phases resume via offseason_completed_steps alone.
# Shared by seasonManager._snapshotDbForPhase (writer) and
# run_api._restorePartialPhaseSnapshotIfNeeded (reader) — keep them in sync here.
OFFSEASON_PARTIAL_PHASES = {'rookie_draft', 'fa_draft', 'training'}

# Large, in-season, append-only tables that offseason phases provably never
# write (no games/weeks/pick-ems happen during a draft). Excluded from the
# phase-rollback snapshot so it stays small AND flat across seasons — these are
# exactly the tables that grow every season. Everything not listed IS snapshotted
# (safe direction: a missed table is merely copied, never silently un-rolled-back).
OFFSEASON_SNAPSHOT_EXCLUDE_TABLES = {
    'game_player_stats',    # ~20MB at S14 — per-game per-player box scores
    'weekly_card_bonuses',  # ~16MB — weekly fantasy card settlement
    'weekly_player_fp',     # weekly fantasy points
    'pick_em_picks',        # weekly pick-em selections
    'games',                # game records
}