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

# ---- Career-arc development (player_development.py) ----
# Players rise toward a per-player PEAK season (a jittered fraction of their
# longevity), plateau, then decline — decline is decoupled from the retirement
# clock so it actually shows. The phase SIGN is intrinsic (seasonsPlayed vs
# peakSeason); coach playerDevelopment + market tier (devBias) only modulate how
# fast/much a RISING player climbs (= realized peak height), never reversing the
# decline. This replaces the old prime/decline binary that let ratings ratchet
# upward forever (league inflated to all-5-star by ~season 9).
DEV_PEAK_FRACTION_LOW = 0.55     # peak season ≈ this..HIGH × longevity, jittered per player
DEV_PEAK_FRACTION_HIGH = 0.65
DEV_PEAK_SEASON_MIN = 2          # even short-longevity players get a brief rise
DEV_PRIME_WINDOW = 1             # seasons either side of peak still counted as "prime" (career-stage display)
# Per-attribute change ranges (min, max) BEFORE devBias / ceiling cap / prospect spread.
DEV_RISE_RANGE = (-1, 5)         # pre-peak: skews up (devBias added here)
DEV_PEAK_RANGE = (-2, 2)         # at peak: roughly flat
DEV_DECLINE_RANGE = (-5, 1)      # post-peak base: skews down (steepens over time)
# Decline steepens with seasons past peak; each season shifts the range down by
# this, plus an extra kick once past longevity, capped so it can't run away.
DEV_DECLINE_STEEPEN_PER_SEASON = 1
DEV_DECLINE_PAST_LONGEVITY_KICK = 2
DEV_DECLINE_MAX_STEEPEN = 6
# Prospects / early-career players are boom-or-bust: widen both ends; good dev
# (positive devBias) skews the spread toward boom.
DEV_PROSPECT_SPREAD = 4
DEV_PROSPECT_SEASONS = 1         # seasonsPlayed <= this (or is_prospect) → volatile
# Trained attributes can fade this low in decline (below MIN_ATTRIBUTE_VALUE so
# aging vets actually drop into lower tiers and the league spreads out).
DEV_ATTRIBUTE_FLOOR = 55

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

# Interception model — three independent pick paths in calculateCatchProbability.
# Each K scales one path's contribution before they combine as independent
# risks. The combined league INT rate is ~linear in these. The prior values
# (0.22/0.26/0.08) drifted the rate to ~2.9% per attempt (above the NFL ~2.3%
# target); scaled down ~14% to land near ~2.5% — still a touch above NFL, but
# back in a realistic band.
INT_BAD_READ_K = 0.19    # QB throws into coverage (actual openness × coverage)
INT_BAD_THROW_K = 0.22   # errant ball (throw quality), gated by defender proximity
INT_DEF_PLAY_K = 0.07    # above-average DB jumps a contested throw

# Hail mary: a desperation end-zone heave into a crowd should connect only as a
# rare miracle. The normal two-phase catch model lands a contested deep ball
# well above that, so the hail-mary catch probability is scaled down to target
# ~5% completion (a completion = TD, since the ball is thrown to the end zone).
# Tune up for more forgiving, down for rarer. Calibrated via a multi-season sim.
HAIL_MARY_COMPLETION_SCALE = 0.18

# Clutch/Choke thresholds
CLUTCH_PRESSURE_THRESHOLD = 50    # Min gamePressure (0-100) for clutch/choke consideration
CLUTCH_MODIFIER_THRESHOLD = 2.0   # Min keyPressureMod for clutch
CHOKE_MODIFIER_THRESHOLD = 1.5    # Min abs(keyPressureMod) for choke
CLUTCH_WPA_THRESHOLD = 6.0        # Min WPA% impact for clutch plays
CHOKE_WPA_THRESHOLD = 5.0         # Min WPA% impact for choke plays

# WPA -> player value attribution (see docs/WPA_MVP_PLAN.md). Per-play win
# probability swing is credited to the players involved and accumulated into a
# season total that feeds the MVP + All-Pro defense value metrics.
WPA_PASS_QB_SHARE = 0.6      # completed pass: QB share of the WPA (receiver gets the remainder)
DEF_PLAYMAKER_BONUS = 2.0    # defensive-WPA share weight multiplier for the tagged defender on a play

# MVP + All-Pro defense value-metric blend weights (z-scores, pooled within position group).
# MVP total value = offenseScore + defValue, where:
#   offenseScore = MVP_PERF_WEIGHT*perfZ + MVP_WPA_WEIGHT*offenseWpaZ
#   defValue     = MVP_DEF_WPA_WEIGHT*defWpaZ + MVP_DEF_BOX_WEIGHT*defBoxZ
MVP_PERF_WEIGHT = 0.6        # season performance rating (box-score percentile) share of offense score
MVP_WPA_WEIGHT = 0.4         # offensive WPA share of offense score
MVP_DEF_WPA_WEIGHT = 0.7     # defensive WPA share of defensive value (carries coverage box can't see)
MVP_DEF_BOX_WEIGHT = 0.3     # defensive box-stat share of defensive value (rewards splashy plays)

# Per-defensive-position weights for the box-stat composite (z-scored within
# group). Coverage value is invisible to the box, so CB/S lean on ints/PBUs and
# the WPA term carries the rest.
DEF_BOX_WEIGHTS = {
    'DE': {'sacks': 3.0, 'tfl': 2.0, 'forcedFumbles': 2.0, 'tackles': 0.5, 'ints': 1.0, 'passBreakups': 0.5},
    'LB': {'tackles': 1.0, 'tfl': 1.5, 'sacks': 2.0, 'forcedFumbles': 2.0, 'ints': 1.5, 'passBreakups': 1.0},
    'CB': {'passBreakups': 2.0, 'ints': 3.0, 'tackles': 0.5, 'sacks': 1.0, 'tfl': 0.5, 'forcedFumbles': 1.0},
    'S':  {'ints': 2.5, 'passBreakups': 2.0, 'tackles': 1.0, 'sacks': 1.0, 'tfl': 0.5, 'forcedFumbles': 1.5},
}

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

# ── Supporter income (fan loyalty dividends) — feature/fan-income ──────────────
# A non-fantasy, IDLE Floobit path: back a team, earn passively, claim on login.
# Tenure (weeks backing the current favorite team) drives a loyalty multiplier;
# team performance nudges the weekly dividend. The guaranteed base stays small —
# real profit is concentrated in the contingent milestone payouts (the CLINCH_* /
# FLOOSBOWL_WIN rewards above, scaled by loyalty in a later phase), so only
# long-tenure fans of great teams come out ahead of what they fund. All tunable;
# validate against fantasy income with a sim-check.
# Activity gate: "idle" means doesn't watch games, NOT abandoned the account.
# A fan who hasn't logged in within this many REAL days is frozen — no tenure
# tick, no dividend — until they return (so dormant accounts don't rack up
# Floobits). A sim-season plays out in ~1 real week, so 14 days ≈ "sign in about
# once every season or two" is enough to keep earning. Tunable.
SUPPORTER_ACTIVITY_WINDOW_DAYS = 14
SUPPORTER_BASE_DIVIDEND = 6           # flat Floobits/week while your team is active
SUPPORTER_WIN_BONUS = 4               # base bonus the weeks your team wins
# Win-quality add-ons, stacked onto the win bonus (the whole dividend is then
# multiplied by Tenure × Funding, so great weeks for long-haul patrons pay big).
# Most are read straight off the game (scores, quarter scores, playoff flag).
SUPPORTER_SHUTOUT_BONUS = 3           # opponent held to 0
SUPPORTER_BLOWOUT_MARGIN = 21        # win by >= this (3 scores) is a blowout
SUPPORTER_BLOWOUT_BONUS = 2           # added on a blowout win
SUPPORTER_COMEBACK_BONUS = 3          # won after trailing at the end of Q3
SUPPORTER_STREAK_BONUS_PER_WIN = 1    # +1 per win in the streak beyond the first (a lone win adds 0)...
SUPPORTER_STREAK_BONUS_CAP = 6        # ...capped here (a 7+ win streak maxes it)
SUPPORTER_UNDERDOG_WIN_BONUS = 3      # added on an upset win (beat a higher-ELO opponent — same rule as the UPSET badge / house_money card)
# Playoff wins pay more, scaled by round (1=Rd1, 2=Rd2, 3=League Championship,
# 4=Floos Bowl). Keyed by round number = week - 28.
SUPPORTER_PLAYOFF_WIN_BONUS = {1: 4, 2: 6, 3: 8, 4: 12}
SUPPORTER_TEAM_CHANGE_TENURE_KEEP = 0.5  # fraction of tenure kept on a team change (soft reset)
# Patron rank — your share of your team's funding, applied ON TOP of loyalty.
# Percentile thresholds (top X% of a team's contributors this season); the single
# biggest backer is always the Patron. Frames as recognition/status, and the
# combined ceiling (top loyalty × top patron = 2.0 × 1.5 = 3.0) keeps even the
# best corner only mildly profitable. (maxPercentile, multiplier, label) ascending.
SUPPORTER_PATRON_TIERS = [
    (0.10, 1.5,  'Patron'),      # top 10% (or the biggest backer)
    (0.25, 1.3,  'Benefactor'),  # top 25%
    (0.50, 1.15, 'Backer'),      # top half
]
# Loyalty tiers by supporter_weeks (persists across seasons; ~28 wks = 1 season).
# (minWeeks, multiplier, label), descending — first match from the top wins.
# Gaps WIDEN as you climb (28 → 56 → 84 wks between tiers) so each tier is a
# bigger commitment than the last and the top tier is a genuine long-hauler.
SUPPORTER_LOYALTY_TIERS = [
    (168, 2.0,  'Lifer'),     # ~6 seasons
    (84,  1.5,  'Faithful'),  # ~3 seasons
    (28,  1.25, 'Regular'),   # ~1 season
    (0,   1.0,  'New Fan'),
]
# Weeks of tenure one season represents (matches the tier spacing above). Used by
# the one-time tenure backfill to convert seasons-as-a-fan into supporter_weeks.
SUPPORTER_WEEKS_PER_SEASON = 28

# ── Spectator income (the cheer bar) — feature/fan-income ──────────────────────
# The ACTIVE non-fantasy path: watch live games, fill a segmented bar, get paid
# per segment. Server-validated (fill is credited only for plays that actually
# happened in a game you're heartbeating, so you can't earn faster than the game
# plays) and hard-capped per game + per week, so idling/botting nets little.
SPECTATOR_FILL_PER_PLAY = 1.0          # bar fill per witnessed play
SPECTATOR_FILL_PER_POINT = 0.6         # bonus fill per point scored while watching (TDs/FGs fill faster)
SPECTATOR_SEGMENT_SIZE = 18.0          # fill needed to complete a segment (~18 plays)
SPECTATOR_SEGMENT_PAYOUT = 3           # Floobits per completed segment
SPECTATOR_RALLY_FILL = 5.0             # a (free) rally adds this much
SPECTATOR_REACTION_FILL = 1.0          # a reaction adds this (diminishing, capped/game)
SPECTATOR_REACTION_CAP_PER_GAME = 8    # max reaction-fill events credited per game
SPECTATOR_SUPPORTED_TEAM_MULT = 1.5    # watching your favorite team fills faster
SPECTATOR_HEARTBEAT_WINDOW_SEC = 60    # must claim/heartbeat within this to count as "present" (rally/reaction gate)
SPECTATOR_MAX_PLAYS_PER_HEARTBEAT = 12 # legacy heartbeat: cap plays credited per beat (claim model caps to real progress instead)
SPECTATOR_WEEKLY_PAYOUT_CAP = 60       # max Floobits/week from spectating
# Big plays — any play that flashes the field / posts a big-play WPA highlight
# (WPA swing >= 7). Bonus fill on TOP of the per-play fill; worth more when your
# own supported team is the one making it.
SPECTATOR_BIG_PLAY_FILL = 4.0          # bonus fill per witnessed big play
SPECTATOR_OWN_BIG_PLAY_MULT = 2.0      # multiplier when YOUR team makes the big play

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
# bumped ~33% in v0.16.1, then nudged up another ~12% next-season — payouts
# still felt a touch thin against pack/upgrade prices. Shape (exponent)
# unchanged so the high-end taper still prevents runaway whales while
# floors and middle play benefit too. Sample profile (default):
#   100 FP →  17 F
#   500 FP →  61 F
#  1000 FP → 105 F
#  3000 FP → 247 F
WEEKLY_FP_FLOOBIT_SCALE = 0.48
WEEKLY_FP_FLOOBIT_EXPONENT = 0.78
# Endowment (income_boost powerup) replaces the curve with a flatter one.
# Less taper = monster weeks pay more; low weeks pay roughly the same.
# Same cost (100 F). Sits ~10% above standard at modest play, ~50% above
# at heavy play, breaking even around 1k FP/week × 4 weeks. Bumped
# proportionally with the standard curve.
WEEKLY_FP_FLOOBIT_BOOSTED_SCALE = 0.30
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

# ---- Retirement (keyed to yearsPast = seasonsPlayed - longevity) ----
# `longevity` (randint 4-10 per player) is the intended retirement clock, so we
# band on how many seasons a player is PAST it — not absolute seasonsPlayed,
# which can't grow past league age (a young league would otherwise never retire
# its vets). These bands are the SINGLE SOURCE OF TRUTH for both the actual roll
# (seasonManager._evaluateRetirementCandidates) and the displayed risk tier
# (playerManager.computeRetirementRisk / computeRetirementOdds), so the label a
# user sees always matches the real odds.
# Tiers: 'safe' | 'possible' | 'likely' | 'very_likely' | 'retiring' (locked)
RETIREMENT_YEARS_PAST_HIGH  = 3     # 3+ seasons past longevity → very_likely
RETIREMENT_YEARS_PAST_MID   = 1     # 1-2 past → likely
RETIREMENT_YEARS_PAST_EARLY = 0     # just reached longevity → possible
RETIREMENT_CHANCE_HIGH  = 90        # % chance once eligible (yearsPast >= HIGH)
RETIREMENT_CHANCE_MID   = 65        # % chance (yearsPast >= MID)
RETIREMENT_CHANCE_EARLY = 25        # % chance (yearsPast >= EARLY)
# Phased contract gate: a player only newly enters retirement territory on their
# walk season (termRemaining == 1). But once they're this many seasons past
# longevity and still playing, they retire even mid-contract.
RETIREMENT_MIDCONTRACT_YEARS_PAST = 3

# ---- Roster Supply Floor ----
# After retirements are known, guarantee the league has enough living players at
# EACH position to fill every roster slot (24 teams × {QB1,RB1,WR2,TE1,K1}),
# else a position run (many retirements at one spot + a thin rookie class) could
# leave slots permanently empty. The supply check (playerManager.ensurePositionSupply)
# tops up only the per-position deficit into the FA pool — a no-op in the normal
# case where the pool is already deep. This buffer is the small cushion kept
# ABOVE exact slot demand so the FA draft has some choice and late FA retirements
# don't re-open a gap. Only matters when a position is genuinely short.
ROSTER_SUPPLY_BUFFER_PER_POSITION = 3

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

# ── QB scrambles ──────────────────────────────────────────────────────────
# A pressured QB can escape a would-be sack and run instead. AGILITY gates the
# escape (whether they scramble at all); SPEED drives the yardage. A pocket QB
# (low agility) almost never gets out and still takes the sack. Tunable; flip
# QB_SCRAMBLE_ENABLED to disable without code changes.
QB_SCRAMBLE_ENABLED = True
QB_SCRAMBLE_AGILITY_THRESHOLD = 78    # below this agility → essentially no scrambling
QB_SCRAMBLE_CHANCE_PER_AGILITY = 2.0  # % escape chance per agility point above the threshold
QB_SCRAMBLE_MAX_CHANCE = 65           # cap on escape chance (% of would-be sacks)
QB_SCRAMBLE_BASE_YARDS = 4.0          # mean scramble yards at the speed pivot
QB_SCRAMBLE_SPEED_PIVOT = 78          # speed at which base yards apply
QB_SCRAMBLE_YARDS_PER_SPEED = 0.25    # mean yards added per speed point above the pivot
QB_SCRAMBLE_OOB_CHANCE = 20           # % a scramble goes out of bounds (stops the clock)
QB_SCRAMBLE_FUMBLE_CHANCE = 3         # % a scramble ends in a fumble
# Sacks are rare (~0.8/game), so sack-escape scrambles alone barely register. The
# realistic primary trigger is "no one open": instead of throwing it away, a mobile
# QB tucks and runs. This is the dominant scramble path; agility gates the decision.
QB_SCRAMBLE_OPEN_RUN_PER_AGILITY = 3.0  # % tuck-and-run chance per agility pt above the threshold
QB_SCRAMBLE_OPEN_RUN_MAX = 75           # cap on the tuck-and-run chance (% of would-be throwaways)

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
    "description": "Increases your weekly fantasy Floobit payout for 4 weeks.",
    "price": 100,
    "durationWeeks": 4,
    "seasonLimit": 2,
    # Endowment swaps the SCALE/EXPONENT pair. The flatter curve trades a
    # small dip on low-FP weeks for a meaningful bump on monster weeks
    # (e.g. 500 FP: 61 F normal → 70 F endowment; 1000 FP: 105 → 132;
    # 5000 FP: 423 → 596).
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

# ---- Card Upgrade Tiers (Level Up) ----
# Cards level I->IV (tier 1->4) by feeding ONE same-effect duplicate + Floobits.
# Same effect ⇒ same edition (effects are edition-locked), so the duplicate is a
# free rarity gate. Tier is per-instance, seasonal (expires with the card unless
# vaulted). Tune all of the below via simcheck_cards_v3.
CARD_TIER_MAX = 4
# Single value multiplier on a card's OWN output (FP / FPx-delta / Floobits).
CARD_TIER_MULT = {1: 1.0, 2: 1.15, 3: 1.32, 4: 1.5}
# Structural cards produce no own output (isAmplifier / isAdvantage) — leveling
# them adds a flat per-tier dividend instead. Sized PER EDITION to land near that
# edition's output band at max tier, so a fully-upgraded card is worth the cost
# (a Diamond should pay Diamond-band FP, not a flat 55). FP for FP/FPx-side
# cards, Floobits for floobit-output ones.
CARD_TIER_DIVIDEND_FP = {
    "base":        {1: 0, 2: 12, 3: 24, 4: 36},
    "holographic": {1: 0, 2: 18, 3: 34, 4: 52},
    "prismatic":   {1: 0, 2: 26, 3: 48, 4: 72},
    "diamond":     {1: 0, 2: 34, 3: 60, 4: 90},
}
CARD_TIER_DIVIDEND_FLOOBITS = {
    "base":        {1: 0, 2: 8,  3: 16, 4: 24},
    "holographic": {1: 0, 2: 11, 3: 21, 4: 32},
    "prismatic":   {1: 0, 2: 14, 3: 27, 4: 40},
    "diamond":     {1: 0, 2: 18, 3: 34, 4: 50},
}
# Floobit cost to perform the upgrade INTO a tier (I->II uses [2], etc.), before
# the edition multiplier. Steep + escalating so maxing is a multi-week sink, not
# a day-one rush (the same-effect duplicate requirement is the primary gate).
CARD_TIER_UPGRADE_COST = {2: 72, 3: 225, 4: 540}
CARD_TIER_EDITION_COST_MULT = {
    "base": 1.0, "holographic": 1.25, "prismatic": 1.6, "diamond": 2.0,
}

# ─── Card Showcase (seasonal collection payout) ──────────────────────────────
# An 8-slot showcase filled from the permanent Vault. Scored each season into a
# letter grade (F→S) that pays out flat Floobits at season end, then clears.
# Scoring is hidden (grade + named sets only) — see showcaseManager. All values
# below are owner-approved starting points; tune via /simcheck before balancing.
SHOWCASE_SLOTS = 8
# Per-card base = EDITION_POINTS × recency + Σ CLASSIFICATION_POINTS, ×tier mult.
SHOWCASE_EDITION_POINTS = {"base": 1, "holographic": 4, "prismatic": 12, "diamond": 30}
SHOWCASE_CLASSIFICATION_POINTS = {"rookie": 5, "all_pro": 10, "champion": 12, "mvp": 20}
# Recency: newer cards pay more. recency = max(FLOOR, 1 − STEP × seasonsOld).
SHOWCASE_RECENCY_FLOOR = 0.25
SHOWCASE_RECENCY_STEP = 0.25
# Upgrade tier lifts a card's showcase value: ×(1 + (tier−1) × THIS).
SHOWCASE_TIER_BONUS_PER_LEVEL = 0.15
# Set bonuses ADD into one multiplier: score = Σ cardPoints × (1 + Σ bonuses),
# with the bonus sum capped here so stacked sets can't run away.
SHOWCASE_MAX_SET_BONUS = 2.5
# Score → grade (first threshold the score meets, scanning high to low).
# Calibrated via tune_showcase.py Monte Carlo (recency-1.0 best-8 showcases):
# casual≈D, regular≈C, dedicated≈B, whale≈A, top-few-%-whale≈S.
SHOWCASE_GRADE_THRESHOLDS = [
    ("S", 270), ("A", 175), ("B", 115), ("C", 70), ("D", 35), ("F", 0),
]
# Grade → flat Floobit payout at season end.
# Calibrated next-season to read as a strong second income against a season of
# fantasy, without eclipsing it (showcase pays once/season and clears, and the
# permanent-vault cost — vaulted cards can't be equipped/sold — justifies it).
# S capped at 3000 (a first pass at 5000 ran too hot). Old table was
# 50/120/250/450/800, below even a casual fantasy season. Re-tune via
# tune_showcase.py / simcheck.
SHOWCASE_GRADE_PAYOUT = {"F": 0, "D": 250, "C": 600, "B": 1200, "A": 2000, "S": 3000}

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

# Fire / cut / resign pass threshold as a fraction of the team's active fanbase.
# net (yea − nay) votes must reach ceil(fanCount × GM_PASS_FRACTION) to pass —
# a majority of the fanbase, not the whole of it. 0.5 = simple majority; raise
# toward 1.0 for a stricter near-consensus bar. ceil() keeps a tiny fanbase
# honest (e.g. 1 fan still needs net 1). Single-vote means each fan contributes
# at most ±1, so this is a genuine "majority of fans agree" gate.
GM_PASS_FRACTION = 0.5

# Per-user GM limits.
#
# LEGACY: the per-season / per-type / per-target caps below are retired. The
# single-vote model (one vote per fan per target, withdraw to change, flat
# per-vote cost) replaced hard caps entirely, so nothing in the live vote path
# reads these anymore. Kept defined only so any stray importer doesn't break.
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

# Tribune secret achievement: cast this many GM votes in a single season. Under
# single-vote a fan votes at most once per decision, so a season's ceiling is
# roughly their team's slate (~6 roster calls plus the coach). 6 reads as
# "voted on basically everything" while staying reachable across seasons.
GM_TRIBUNE_VOTE_THRESHOLD = 6

# Front Office voting window opens at this week. Before this, GM vote UIs show
# a "convening..." state. Mirrors the frontend const GM_ACTIVE_WEEK in
# FrontOfficePanel.tsx — keep them in sync.
GM_ACTIVE_WEEK = 22

# ── Fan-voted awards (MVP & Hall of Fame) — see docs/AWARDS_VOTING_PLAN.md ──
# Voting is free. Below the quorum (and in fast/sim modes, where no one votes),
# the awards fall back to the algorithm: value-metric MVP, HoF-points induction.
AWARD_MVP_QUORUM = 3                # min distinct voters before the fan MVP stands
AWARD_MVP_BALLOT_PER_POSITION = 3   # top N per position on the MVP ballot
AWARD_HOF_QUORUM = 3                # min distinct voters before fan induction stands
AWARD_HOF_BALLOT_PREFILTER = 10     # _computeHofPoints needed to make the ballot (looser than the 22 auto-induct)
AWARD_HOF_CLASS_CAP = 5             # max inductions per season
AWARD_HOF_BALLOT_TENURE = 5         # seasons a candidate stays on the ballot before being dropped
AWARD_HOF_APPROVAL_FRACTION = 0.5   # fraction of HoF voters who must approve to be induct-eligible

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

# Playoff bracket challenge — floobit prizes by final rank (one-time/season).
PLAYOFF_BRACKET_PRIZES = {1: 120, 2: 75, 3: 40}
PLAYOFF_BRACKET_TOP_PCT = 0.25
PLAYOFF_BRACKET_TOP_PCT_PRIZE = 15

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


# ─── Anomaly System / The Criticality ──────────────────────────────────────────────
# The anomaly system has three layers:
#   Layer 1 — universal cosmetic micro-glitches (fires from Stirring up)
#   Layer 2 — personality-flavored cosmetic glitches (fires from Erratic up)
#   Criticality — the dramatic event: a Core takes control and the card-bonus
#              math switches to that Core's signature equation
#
# Layer 1 + Layer 2 are PURE FLAVOR — no mechanical impact regardless of flag.
# This flag gates ONLY the Criticality event itself. When False, the aggregate
# can still climb to threshold and Core warnings/news still fire (visible
# tease), but the trigger is suppressed and the math never swaps.
#
# Roadmap (full event DEFERRED — decided 2026-06-04):
#   This season (shipping): False — the tease. Whispers, warnings, glitches, the
#     instability dial, and the near-miss SUPPRESSION cycle + Cores dialogue. The
#     full event never fires.
#   A future season (deferred, NOT the next one): flip True — the payoff. A Core
#     seizes the card-bonus math, the Reset purges the awakened, L4 control powers
#     land. Pushed back beyond the upcoming season. Do NOT enable without an
#     explicit go from the owner.
ANOMALY_CRITICALITY_ENABLED = False

# ── Glitch firing hygiene ─────────────────────────────────────────────────────
# Per-play per-candidate glitch probability = min(CAP, attention / SCALE ×
# instability). Tuned DOWN hard from last season (was attention/1000 with no
# per-game cap), which flooded game feeds with glitch lines. Now glitches are
# rare, spaced by a cooldown, and hard-capped per game so each one reads as a
# notable "huh" instead of wallpaper. (The league instability dial that scales
# these with the suppression cycle lands in P3.)
ANOMALY_GLITCH_PROB_SCALE = 3000.0   # higher = rarer (was effectively 1000)
ANOMALY_GLITCH_PROB_CAP = 0.12       # per-candidate probability ceiling
ANOMALY_GLITCH_MAX_PER_GAME = 3      # hard cap on glitch lines per game
ANOMALY_GLITCH_COOLDOWN_PLAYS = 10   # minimum plays between glitch lines
# Cumulative layer weights — a player's ladder state is the CEILING; each glitch
# rolls a layer up to it. L1 = cosmetic micro, L2 = cosmetic personality.
# (L3 = game-impacting, added at rampant+ in P2.)
ANOMALY_L2_WEIGHT_ERRATIC = 0.35     # P(L2 vs L1) at erratic
ANOMALY_L2_WEIGHT_RAMPANT = 0.50     # P(L2 vs L1) at rampant / awakened

# ── L3 (game-impacting) glitch effects ────────────────────────────────────────
# At rampant/awakened a ball-carrier's play can glitch and the YARDAGE changes
# for real — involuntary, NOT the deliberate Control powers (those are a later
# season). Skewed heavily positive. Negatives are modest "stumbles" that only
# fire on short, down-advancing plays and never change possession or score —
# no turnovers this season. All tunable.
ANOMALY_L3_TRIGGER_PROB = 0.12       # chance per qualifying touch (then capped/cooled per game)
ANOMALY_L3_HELP_CHANCE = 0.78        # P(bonus yards) vs a stumble
ANOMALY_L3_POS_YARDS = (3, 12)       # bonus-yard range (can extend a drive; rarely score near the goal line)
ANOMALY_L3_NEG_YARDS = (2, 5)        # stumble loss range (field position only)
ANOMALY_L3_MAX_NEG_PER_TEAM = 1      # cap stumbles per team per game
ANOMALY_L3_LATE_QUARTER = 4          # Q4+ counts as "late"
ANOMALY_L3_CLOSE_MARGIN = 8          # within this margin in a late game → no stumbles

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