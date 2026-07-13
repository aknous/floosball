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

# ---- Rating generation: parity + prospect true-skill model (docs/PARITY_PROSPECT_PLAN.md) ----
# The generated attribute distribution now defines a player's TRUE SKILL — the
# mature level they reliably develop INTO, not their entry level. Three tiers:
#   current (plays now) <= trueSkill (mature target) <= potential (rare ceiling).
# Calibrated to a 14-season fresh sim (whole active pool): (76,8) settled ~8%
# 4-5-star / mean 74 with ZERO creep; (78,10) lands the steady-state ~16-17% (in
# the 15-20% target) with a wider spread (healthy scrub tail for differentiation).
# The mean only shifts the FIXED distribution up — it does not affect the no-creep
# mechanism (the dev arc caps growth at true skill regardless).
GEN_TRUESKILL_MEAN = 78
GEN_TRUESKILL_STD = 10
# potential = trueSkill + randint(0, POTENTIAL_HEADROOM). Narrowed from the old
# 30: true skill is the reliable target; potential is the occasional overshoot.
POTENTIAL_HEADROOM = 15
# Rookies/prospects DEBUT this many attribute points below their true skill and
# develop up into it over their early seasons (~6-9 rating pts; calibrate). A
# future 5-star looks like a solid 3-4-star as a rookie. Founding/FA-generated
# (non-rookie) players skip the discount — they enter already at their level.
PROSPECT_ENTRY_DISCOUNT = 11

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
# Per-player decline SEVERITY multiplier (stable per player, seeded off id) so not
# everyone follows the same arc. Low end = ages gracefully, good for a long career;
# ~MODE = a normal gradual decline; high end = falls off a cliff. The whole decline
# (base + steepening) scales by this on the downside only. Drawn triangular around
# MODE so a GRADUAL falloff is the common case and the ageless/cliff tails are rarer.
DEV_DECLINE_FACTOR_LOW = 0.3
DEV_DECLINE_FACTOR_HIGH = 1.5
DEV_DECLINE_FACTOR_MODE = 0.85
# Prospects / early-career players are boom-or-bust: widen both ends; good dev
# (positive devBias) skews the spread toward boom.
DEV_PROSPECT_SPREAD = 4
DEV_PROSPECT_SEASONS = 1         # seasonsPlayed <= this (or is_prospect) → volatile
# A rising player climbs reliably toward their TRUE SKILL (the growth cap). Each
# non-declining season there's a gated chance they OVERSHOOT past true skill
# toward their potential ceiling — the overachiever who exceeds projection. Good
# coaching/facilities (devBias) raise the odds. Most players settle at true skill.
# See docs/PARITY_PROSPECT_PLAN.md. NOTE: DEV_RISE_RANGE is intentionally NOT
# flattened — the true-skill cap is the parity lever; the rise rate just sets how
# fast a rookie closes the entry discount (~2-3 seasons).
DEV_OVERSHOOT_BASE_CHANCE = 0.12     # per rising/peak season, per attribute
DEV_OVERSHOOT_BIAS_PER_POINT = 0.05  # each devBias point added to that chance
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
# risks. History: 0.22/0.26/0.08 ran ~2.9%; 0.19/0.22/0.07 still ran 2.74% over prod
# season 10; a 16% trim (0.16/0.185/0.06) OVERSHOT to 1.85% on a developed-league sim
# (the rate is steeper-than-linear in the Ks). Settled at a ~8% trim from the 0.19
# baseline to land ~2.3% per attempt. The blowout INT-fests are handled separately by
# INT_DESPERATION_DAMPEN below — the base rate shouldn't be flattened to fix the tail.
INT_BAD_READ_K = 0.175   # QB throws into coverage (actual openness × coverage)
INT_BAD_THROW_K = 0.20   # errant ball (throw quality), gated by defender proximity
INT_DEF_PLAY_K = 0.065   # above-average DB jumps a contested throw

# League coverage baseline — the value in-game pass coverage centers on (the
# LEAGUE_COMPRESSION_MEAN target). Absolute coverage terms anchor here so they
# don't creep as the league ages: an evolved league's compressed coverage drifts
# up from this baseline, and a fixed sub-baseline anchor (the old 60 / 72) made
# every defender's contribution grow season over season, compounding the pick
# rate. Anchoring on the baseline keeps a league-average defender's contribution
# stable across seasons while still rewarding above-average coverage. Matches the
# 80 covFactor already centers on (see calculateCatchProbability).
LEAGUE_COVERAGE_BASELINE = 80

# Pass-completion coverage suppression (calculateCatchProbability, Phase 1/contact).
# Both knobs feed contactProb, i.e. COMPLETION probability ONLY — they do NOT touch
# the INT paths, so raising them adds coverage breakups / incompletions WITHOUT more
# interceptions. Tuned on a developed-league (prod S12) resume sim: the old 18 / 0.10
# ran ~74% completion (INT ~2.0%); raised to 40 / 0.45 to land ~66-67% (INT held
# ~2.1%). DISRUPTION_K is openness- and tier-scaled (short passes barely affected, so
# the short game stays reliable for catch-up drives); BASELINE_SLOPE is a flat
# per-point pressure that does most of the aggregate work.
# ANCHORING (done): coverageBaseline is now SYMMETRIC around LEAGUE_COVERAGE_BASELINE
# (see calculateCatchProbability) instead of a fixed 70 anchor. Below the league mean
# it REFUNDS completion (raises young/expansion leagues), above it SUPPRESSES (holds
# mature leagues) — so completion stays flat as coverage climbs rather than creeping.
# This is the same pattern the INT model uses (covFactor centered on the baseline).
# The offense side (baseContact from throwQuality) is still absolute; the symmetric
# coverage term is what keeps the offense-vs-defense balance league-relative here.
# Tuned on paired young-league (fresh) + mature (prod S12 resume) sims to hold
# completion ~66-67% at BOTH ends.
PASS_COVERAGE_DISRUPTION_K = 15      # x tier x (1-openness) x (coverage/100) -> contact loss
PASS_COVERAGE_BASELINE_SLOPE = 1.9   # symmetric contact loss/gain per coverage point off the mean

# Desperation-deep INT dampener — a trailing team forced to chuck it deep in garbage
# time was minting 9-INT games (the Floos Bowl, a 44-0 sim game). A genuine desperation
# heave is a low-percentage prayer, but it shouldn't get PICKED at the full contested-
# deep rate either (the defense is sitting back, the throw is just air-mailed). When a
# pass is a deep/long throw AND the offense is in desperation mode (trailing late /
# mustThrow), scale the computed INT probability by this factor. 1.0 = no dampening.
INT_DESPERATION_DAMPEN = 0.55

# Clutch turnover amplification — high-pressure games (gamePressure >= CLUTCH_PRESSURE_THRESHOLD)
# spike both fumbles and INTs for a CHOKING player. The base rates are NFL-realistic; only this
# clutch SPIKE was too hot (turnover-fest Floos Bowls), so it's DAMPENED here (not the base).
FUMBLE_BASE_THRESHOLD = 98        # run-fumble roll threshold; > this = fumble (~2% base, was 97/~3%).
FUMBLE_CHOKE_FLOOR = 95           # clutch choke can't drop the fumble threshold below this (was 92)
FUMBLE_CHOKE_SWING_K = 1.0        # per-unit-of-choke drop on the threshold (was 2.0)
INT_CHOKE_BOOST_K = 0.0           # clutch-choke INT-prob boost OFF (was 1.5) — the QB's throw-quality
                                  # drop under pressure already raises clutch INTs; this extra boost double-counted.

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

# Mental model — Confidence × Discipline (docs/MENTAL_MODEL.md). Starting values;
# tune via /simcheck + the scenario harness.
MENTAL_EXEC_GAIN = 3.0       # rating pts of execution per full confidence unit (C=±1)
MENTAL_FROZEN_K = 2.0        # extra underperformance for low-confidence × undisciplined ("frozen")
MENTAL_GUNSLINGER_K = 6.0    # pp added to turnover odds for high-confidence × undisciplined
# Aggression (play-style): confidence drives a QB's willingness to force a throw
# into a tight window vs check down / throw it away.
MENTAL_AGGR_ROLL_K = 25      # +/- to the "force the throw" roll per full confidence unit
MENTAL_AGGR_BAIL_K = 15      # shifts the throw-away bail threshold per full confidence unit
MENTAL_DIVE_K = 10          # catch-prob (pp) a confident receiver gains laying out for a contested ball

# WPA -> player value attribution (see docs/WPA_MVP_PLAN.md). Per-play win
# probability swing is credited to the players involved and accumulated into a
# season total that feeds the MVP + All-Pro defense value metrics.
WPA_PASS_QB_SHARE = 0.6      # completed pass: QB share of the WPA (receiver gets the remainder)
DEF_PLAYMAKER_BONUS = 2.0    # defensive-WPA share weight multiplier for the tagged defender on a play

# MVP + All-Pro value metric (flat z-score blend, pooled within position group):
#   mvpScore = MVP_PERF_WEIGHT*perfZ + MVP_WPA_WEIGHT*offenseWpaZ + MVP_DEF_WPA_WEIGHT*defWpaZ
# perfZ = z of the OVERALL (two-way) performance rating, which already composites
# offensive + defensive PRODUCTION (see below), so defensive production is in perfZ
# and there's no separate box term. The only standalone defensive term is the
# defensive clutch WPA (defWpaZ). Both WPA terms are INDIVIDUAL — offense to the
# ball-handler, defense to the playmaker (floosball_game _attributeWpa) — so neither
# clusters the ballot the way the old team-shared defensive WPA did. Defense is
# secondary (it's 30% of the perf composite + a small WPA term), so offense leads
# but a two-way standout climbs, and All-Pro (top mvpScore per slot) reflects defense.
# Players are two-way, so the OVERALL performance rating composites offensive and
# defensive production (offense-dominant); MVP/All-Pro run off it.
PERF_OFFENSE_WEIGHT = 0.7    # offensive-production share of the overall performance rating
PERF_DEFENSE_WEIGHT = 0.3    # defensive-production share of the overall performance rating
# Unified MVP (flat): production composite (two-way, via perfZ of the OVERALL rating)
# + clutch WPA on each side. Defensive production lives inside perfZ now (via the
# overall composite), so there's no separate box defValue term — only the clutch
# defensive WPA remains, as a secondary term.
MVP_PERF_WEIGHT = 0.7        # overall (two-way) production-composite z share
MVP_WPA_WEIGHT = 0.3         # per-snap OFFENSIVE WPA share (offensive clutch)
MVP_DEF_WPA_WEIGHT = 0.2     # individual DEFENSIVE WPA share (defensive clutch; secondary)
# Per-defensive-group box weights (DEF_BOX_WEIGHTS, below) now feed the DEFENSIVE
# performance rating; defValue's box term and the old MVP_DEF_WEIGHT/MVP_DEF_BOX_WEIGHT
# are retired by the unify.

# Per-defensive-position weights for the box-stat composite (z-scored within
# group) — the box (production) term of defValue, blended with individual
# defensive WPA. Coverage value is invisible to the box, so CB/S lean hard on
# ints/PBUs to capture it (and the WPA term picks up clutch coverage swings).
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
# Flavor: chance a newly-generated coach reuses a RETIRED player's name (a former
# player returning as a coach), instead of drawing a fresh name from the pool.
COACH_RETIRED_NAME_CHANCE = 0.30

# Mid-game re-plan (see floosball_game._maybeReadjustGameplans). The mid-game
# adjustment reads the running (cumulative) box score, which is a THIN sample
# early in the game — re-planning off one noisy quarter chased variance and cost
# wins. These make the correction sample-aware: skip it below a floor of plays,
# and scale its magnitude by how much data backs the read.
REPLAN_MIN_PLAYS = 10             # a side needs >= this many plays before its plan is re-adjusted
REPLAN_FULL_CONFIDENCE_PLAYS = 30 # plays at which the adjustment runs at full magnitude (confidence=1.0)

# Quick-game (short-pass) suppression. The struggling-offense adjustment sets a
# pass-depth bias toward quick, high-percentage throws to build rhythm — but that
# is a rhythm/ball-control tool, WRONG in catch-up mode where the offense needs
# chunk plays. _applyGameplanMods suppresses the bias when the offense is in
# catch-up mode (let the deep/desperation play-calling ride instead).
QUICKGAME_SUPPRESS_DEFICIT = 9    # 2nd half: behind by 2+ scores -> need chunks, drop the quick game
QUICKGAME_LATE_DEFICIT = 3       # Q4/OT: behind by a FG or more -> need to hurry, drop the quick game

# runPassRatio wiring (see Game._applyGameplanMods). The offensive gameplan's
# runPassRatio (0.25-0.75, 0.5 neutral, higher = more run) was never consumed by
# play selection; these map its deviation from neutral into multiplicative nudges
# on the run weight (up) and the four pass-tier weights (down), so the mid-game
# adjustment toward "what's working" actually shifts the run/pass mix.
RUNPASS_RUN_SWING = 1.2          # run-weight multiplier = 1 + (ratio-0.5)*this  (r=0.75 -> run x1.30)
RUNPASS_PASS_SWING = 1.0         # pass-tier multiplier = 1 - (ratio-0.5)*this   (r=0.75 -> pass x0.75)

# Live RB feed (Game._applyMatchupMods): the play-caller leans on a talented
# back every down, not just via the pre-game gameplan. run weight is scaled by
# the RB's offensive rating vs a neutral baseline, so a stud gets meaningfully
# more carries and a weak back fewer. Independent of the defense read.
RB_FEED_NEUTRAL = 80             # RB offensive rating at which the feed is neutral (x1.0)
RB_FEED_RANGE = 20               # rating spread mapped to +/- one unit of the swing
RB_FEED_STRENGTH = 0.5           # run *= 1 + STRENGTH*(rating-NEUTRAL)/RANGE  (rating 90 -> run x1.25)
RB_FEED_MIN_MULT = 0.7           # floor so a weak back still runs sometimes

# ---------------------------------------------------------------------------
# Run-play CONCEPTS (playbook diversification Phase 1 — see docs/PLAYBOOK_PLAN.md)
# ---------------------------------------------------------------------------
# Every run is now a CONCEPT that exploits (or is punished by) the defense's
# commitment. The coach calls the concept (fit to personnel + expected defense);
# a per-play EXECUTION roll on player attributes decides whether the deception
# lands (full edge) or telegraphs (edge reversed). `conceptEdge` > 0 => weaker
# effective run defense => more yards.
RUN_CONCEPT_ENABLED = True        # master toggle (A/B the whole concept layer)
RUN_CONCEPT_EDGE_STRENGTH = 0.30  # scales realized edge into the effectiveRunDef multiplier.
                                  # Kept modest so concepts REDISTRIBUTE yards (gain vs the wrong
                                  # defense, lose vs the right one) rather than inflate the run game.
RUN_VS_BLITZ_BONUS = 0.06         # realism fix: ANY run vs an active blitz gashes the vacated front
                                  # (was missing — runDefMult ignored the blitz). Concepts stack on top.

# Per concept: `deception` (0=execution-flat like power, ~0.8=swings hard on execution),
# `exec` (player-attribute weights for the execution roll, summing ~1),
# `edge` (matchup vs the live defensive scheme: blitz on/off, runStopFocus dev from 0.5,
#         aggressiveness dev from 0.5), `gaps` (which run gap the concept attacks, so the
#         narrated direction matches the concept — dives go inside, sweeps go to the edge).
# base = baseline call propensity before coach/personnel/read.
RUN_CONCEPTS = {
    'power':   {'base': 0.46, 'deception': 0.10, 'exec': {'power': 0.6, 'discipline': 0.4},
                'edge': {'blitz': 0.00, 'runFocus': -0.35, 'aggr': 0.00},
                'gaps': {'A-gap': 0.60, 'B-gap': 0.30, 'C-gap': 0.10}},
    'draw':    {'base': 0.16, 'deception': 0.80, 'exec': {'creativity': 0.4, 'focus': 0.3, 'vision': 0.3},
                'edge': {'blitz': 0.45, 'runFocus': -0.45, 'aggr': 0.10},
                'gaps': {'A-gap': 0.45, 'B-gap': 0.40, 'C-gap': 0.15}},
    'counter': {'base': 0.16, 'deception': 0.70, 'exec': {'agility': 0.5, 'creativity': 0.5},
                # `flat` = inherent misdirection value (harder to defend than a straight run);
                # runFocus POSITIVE = the counter beats a run-committed D that over-flows to the
                # fake; aggr POSITIVE = beats over-pursuit. Defenses average ~0.4 aggr, so the
                # flat + runFocus terms keep counter viable when the aggr term is negative.
                'edge': {'flat': 0.05, 'blitz': 0.10, 'runFocus': 0.10, 'aggr': 0.30},
                'gaps': {'A-gap': 0.15, 'B-gap': 0.45, 'C-gap': 0.40}},
    'sweep':   {'base': 0.22, 'deception': 0.40, 'exec': {'speed': 0.4, 'agility': 0.3, 'blocking': 0.3},
                'edge': {'blitz': 0.05, 'runFocus': 0.35, 'aggr': -0.45},
                'gaps': {'A-gap': 0.05, 'B-gap': 0.25, 'C-gap': 0.70}},
}

# Defensive counter-adaptation (Phase 1b): the D-coach reads the offense's run-
# concept tendencies during the game and adjusts to take them away — lean on
# draws and the D stops blitzing; lean on counters and it plays disciplined;
# power/inside and it stacks the box; sweeps and it seals the edge. Applied inside
# adjustDefensiveGameplan, gated by the D-coach's adaptability. Counter and sweep
# pull aggressiveness in OPPOSITE directions, so a balanced ground game can't be
# fully countered (the cat-and-mouse).
DEF_COUNTER_STRENGTH = 0.6        # scales the whole counter adjustment
DEF_COUNTER_MIN_RUNS = 5          # need this many run-concept samples before countering

# ---------------------------------------------------------------------------
# Play-action (pass concept — Phase 2, see docs/PLAYBOOK_PLAN.md)
# ---------------------------------------------------------------------------
# A pass off a run fake. The pass-side of "exploit the defense's commitment":
# when the fake is SOLD (QB execution) against a run-committed / blitzing defense,
# the linebackers and safeties bite -> receivers come open and the rush is slower.
# Vs a pass-committed defense nobody bites (no benefit) and the wasted fake time
# lets the rush get home (the downside that makes it a real decision).
PLAY_ACTION_ENABLED = True
PLAY_ACTION_OPENNESS = 22         # receiver openness points at a fully-sold PA vs a run-committed D
                                  # (added to REAL openness -> completion; scaled by paEffect 0-1)
PLAY_ACTION_RUSH_RELIEF = 0.18    # how much a sold fake slows the pass rush (LBs frozen)
PLAY_ACTION_BACKFIRE = 0.10       # extra pass rush when PA is called vs a pass-committed D (wasted fake)
PLAY_ACTION_EXEC = {'creativity': 0.5, 'focus': 0.3, 'agility': 0.2}  # QB sells the fake

# ---------------------------------------------------------------------------
# Route concepts (pass concepts vs COVERAGE — Phase 2, see docs/PLAYBOOK_PLAN.md)
# ---------------------------------------------------------------------------
# A route concept that beats the coverage it faces springs receivers open —
# mesh (crossers/rubs) beats MAN, flood (overload) beats ZONE, screen beats the
# BLITZ (rushers upfield). Vs the wrong look it's neutral; MATCH coverage (the
# hybrid) blunts concepts. The coach calls the concept that beats the defense's
# coverage tendency (scouting read); a smart QB executes it (reads/times it).
PASS_CONCEPT_ENABLED = True
PASS_CONCEPT_OPENNESS = 20        # receiver openness points on a matched, well-run concept (× execution)
PASS_CONCEPT_MATCH_DAMP = 0.4     # concept effect vs MATCH coverage (it's built to handle concepts)
PASS_CONCEPT_EXEC = {'instinct': 0.4, 'creativity': 0.35, 'focus': 0.25}  # QB reads/times the concept
# base = call propensity before the coach's scouting read; `beats` = the look it defeats.
PASS_CONCEPTS = {
    'standard': {'base': 0.55, 'beats': None},
    'mesh':     {'base': 0.15, 'beats': 'man'},
    'flood':    {'base': 0.15, 'beats': 'zone'},
    'screen':   {'base': 0.15, 'beats': 'blitz'},
}

# ---------------------------------------------------------------------------
# RPO — run-pass option (Phase 2, see docs/PLAYBOOK_PLAN.md)
# ---------------------------------------------------------------------------
# A run look where the QB reads the box AT THE SNAP and either hands it off (into
# a light box) or pulls it and throws a quick pass (into the box a loaded front
# vacated). The offense always has the numbers IF the QB reads it right — so the
# value is the READ (gated by QB instinct/vision), not a big per-play bonus. The
# defensive scheme is rolled pre-snap (in _executeRpo) and reused by the resolver.
RPO_ENABLED = True
RPO_LOADED_RUNFOCUS = 0.63        # runStopFocus above this (or a blitz) = a genuinely loaded box -> throw;
                                  # otherwise the give is the default (keeps RPOs run-first, not pass-heavy)
RPO_READ_BASE = 0.55             # base chance the QB reads the box correctly
RPO_READ_SKILL = 0.40            # + up to this from QB read skill (instinct/vision) -> ~0.95 for an elite QB
RPO_BONUS = 0.14                 # relief for the CORRECT option (run vs light box / pass vs vacated coverage)
RPO_OPENNESS = 16                # receiver openness points on a correctly-read RPO throw
RPO_EXEC = {'instinct': 0.5, 'vision': 0.5}   # QB reads the box
RPO_QB_FIT = {'instinct': 0.35, 'vision': 0.3, 'agility': 0.35}  # which QBs run RPOs well

# ---------------------------------------------------------------------------
# Trick plays (Phase 3, see docs/PLAYBOOK_PLAN.md) — high-variance CALLED SHOTS
# ---------------------------------------------------------------------------
# Rare gadgets a BOLD coach calls when the matchup is right and the game lets him
# afford the risk. Each beats a specific defensive commitment; if that commitment
# ISN'T there (or the players don't execute), it blows up (sack / stuff / big loss).
# "When" rules (in _selectTrickPlay): only aggressive coaches, keyed to the D's
# tendency, in a manageable field-position band, NOT in hurry-up / short-yardage /
# red zone / backed up, and NOT as a desperation heave (called shots only).
TRICK_PLAY_ENABLED = True
TRICK_PLAY_BASE = 0.02            # base rate for a max-aggressive coach in an ideal spot (per-eligible-play; rolls compound over a game, so kept low — gadgets are a rare called shot, a few per team per SEASON)
# Chance a BOLD coach dials up a gadget (a flea-flicker deep shot) instead of a
# straight heave on the final snap of a possession when the Drive Clock is about
# to expire out of FG range. Scaled by the same aggressiveness lean as the normal
# trigger (0 below aggr 78, up to this at aggr 100), so only bold coaches gamble it.
HAIL_MARY_TRICK_CHANCE = 0.15
TRICK_FIELD_MIN_YTE = 21         # not in the red zone (yardsToEndzone must exceed this)
TRICK_FIELD_MAX_YTE = 85         # not backed up in own territory (must be at/under this)
# resolves: 'run'|'pass'; trigger: which D commitment it beats; exec: the key
# player's attributes (the deceiver / ball-carrier); payoff/backfire magnitudes.
TRICK_PLAYS = {
    'flea_flicker': {'resolves': 'pass', 'trigger': 'run_commit', 'carrier': 'qb',
                     'exec': {'creativity': 0.4, 'instinct': 0.3, 'armStrength': 0.3},
                     'openness': 42, 'sack_backfire': 0.35},
    'statue':       {'resolves': 'run', 'trigger': 'rush', 'carrier': 'rb',
                     'exec': {'creativity': 0.5, 'focus': 0.5},
                     'relief': 0.38, 'backfire': 0.28},
    'reverse':      {'resolves': 'run', 'trigger': 'pursuit', 'carrier': 'wr',
                     'exec': {'speed': 0.4, 'agility': 0.4, 'creativity': 0.2},
                     'relief': 0.42, 'backfire': 0.40},
}

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
SUPPORTER_BASE_DIVIDEND = 10          # flat Floobits/week while your team is active
SUPPORTER_WIN_BONUS = 5               # base bonus the weeks your team wins
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
SUPPORTER_PLAYOFF_WIN_BONUS = {1: 5, 2: 10, 3: 15, 4: 25}
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
# bumped ~33% in v0.16.1, then ~2.3x next-season: actually playing fantasy was
# earning ~830 F/season vs ~5k from parking Floobit-output cards, so FP play
# wasn't a viable income path. Shape (exponent) unchanged so the high-end taper
# still prevents runaway whales while floors and middle play benefit too.
# Floobit-output cards stay as-is (a deliberate earn-over-FP strategy); this
# just makes FP play a real alternative. Sample profile (default):
#   100 FP →  40 F
#   500 FP → 140 F
#  1000 FP → 241 F
#  3000 FP → 565 F
WEEKLY_FP_FLOOBIT_SCALE = 1.10
WEEKLY_FP_FLOOBIT_EXPONENT = 0.78
# Endowment (income_boost powerup): a flat +25% on ANYTHING credited to the bank
# while it's active — fantasy, pick-em, showcase + supporter dividends, etc. Applied
# once at the choke point (CurrencyRepository.addFunds), so every income stream is
# boosted uniformly (not just fantasy). 1.25 = +25%.
INCOME_BOOST_MULTIPLIER = 1.25

DEFAULT_FUNDING_PCT = 25  # Default % of unspent floobits contributed at season end
# Currency-transaction types that count as a fan funding their team. Markets→Facilities
# added 'facility_contribution' (active funding goes to the Treasury now); 'team_contribution'
# is still written by the passive season-end tax. Patron rank, funding leaderboards, and the
# Patron achievement all key off this set so facility contributions count like the old ones.
CONTRIBUTION_TX_TYPES = ('team_contribution', 'facility_contribution')

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

# ============================================================================
# FACILITIES  (Markets→Facilities system — see docs/MARKETS_FACILITIES_PLAN.md)
# ============================================================================
# Fan-funded, fan-voted team facilities replace the passive market-tier perks.
# Each facility drives an effect the sim ALREADY applies (the FUNDING_* dicts
# above); the per-level effect curves are calibrated so the one-time
# tier→facilities MIGRATION reproduces today's perks with no nerf:
#   MEGA_MARKET→Lv4, LARGE_MARKET→Lv3, MID_MARKET→Lv2, SMALL_MARKET→Lv1.
# Read the level→effect tables below at those indices to confirm parity.
# The lone deliberate change: SMALL-market PENALTIES become neutral — a built
# facility can't be a penalty, so the floor rises from "penalized" to "neutral,
# just hasn't built much yet" (Lv0/Lv1 = 0). Lv5 is a new above-MEGA ceiling.
# Curves are back-loaded (real effects at Lv3+) to hold migration parity; the
# smoothing of low levels is a tuning task (see plan doc §14).
FACILITY_MAX_LEVEL = 5

# facility_key -> {name, effect (which sim effect it drives), levels[0..5]}
FACILITY_CATALOG = {
    'training':    {'name': 'Training Facility',    'effect': 'dev_bonus',
                    'levels': [0, 0.4, 0.8, 1.2, 1.6, 2.0]},             # player-dev bias; every level a real step (resolved to int probabilistically in apply_offseason_training)
    'locker_room': {'name': 'Locker Room',          'effect': 'morale',
                    'levels': [0.0, 0.0, 0.0, 0.0025, 0.0075, 0.01]},    # pregame morale nudge (cf FUNDING_MORALE_MODIFIER)
    'recovery':    {'name': 'Recovery Center',       'effect': 'fatigue_reduction',
                    'levels': [0.0, 0.0, 0.0, 0.15, 0.30, 0.35]},        # weekly fatigue-gain reduction (cf FUNDING_FATIGUE_REDUCTION)
    'scouting':    {'name': 'Scouting Department',    'effect': 'scouting_bonus',
                    'levels': [0, 0, 0, 3, 5, 7]},                       # rookie scouting accuracy (cf FUNDING_SCOUTING_BONUS)
    'stadium':     {'name': 'Stadium',               'effect': 'home_morale',
                    'levels': [0.0, 0.001, 0.002, 0.003, 0.004, 0.005]}, # NEW — everyone starts Lv0; effect unwired until a later phase
}

# Migration: starting level for the four legacy-perk facilities by current tier.
MIGRATION_TIER_START_LEVEL = {'MEGA_MARKET': 4, 'LARGE_MARKET': 3, 'MID_MARKET': 2, 'SMALL_MARKET': 1}
MIGRATION_STADIUM_START_LEVEL = 0  # new facility nobody has built yet

# Appeal (FA-draft attractiveness) = weighted sum of facility levels. Flat
# weights to start; higher Appeal drafts free agents first. Tune later.
APPEAL_LEVEL_WEIGHTS = {k: 1.0 for k in FACILITY_CATALOG}

# ---- Facility economy (share-denominated costs; plan doc §5) ----
# Costs/upkeep are denominated in SHARES, not absolute Floobits, so they
# self-scale with the economy: 1 share = (total Floobits distributed to users
# last season) / num_teams. Indexed by level (0..5): the cost to REACH a level
# and the per-season cost to MAINTAIN it. Lv0 = free (unbuilt). At S10's ~6,000F
# share these read as Lv5 upgrade ≈ 5,100F, Lv5 upkeep ≈ 1,800F/season; full-max
# (5 facilities × Lv5) ≈ 9,000F/season upkeep. Tune via the economy harness.
FACILITY_UPGRADE_COST_SHARES = [0.0, 0.05, 0.10, 0.20, 0.42, 0.85]  # cost to reach level i
# Upkeep is steep at the top so the soft cap bites: an average-income team
# (≈1 share of income) sustains only a partial/specialized build; a whale
# (≈2.5×) can just hold a full max (engage-or-decay). Tuned via the harness.
FACILITY_UPKEEP_SHARES       = [0.0, 0.005, 0.015, 0.045, 0.115, 0.400]  # upkeep to hold level i
# A facility that ends the season with upkeep unmet slips this many levels.
FACILITY_DECAY_LEVELS = 1
# Rookie draft vote — reuses existing GM_VOTE_COST/GM_VOTES_PER_SEASON infra
GM_ROOKIE_DRAFT_MAX_RANKINGS = 12  # Fans may rank up to this many rookies

# ---- Player career length (longevity = the retirement clock) ----
# Longevity is a quality-weighted base: a random floor..ceiling plus a bonus that
# scales with the player's talent, so better players (the ones who keep a roster
# spot) last longer. Set in playerManager.createPlayer from the talent seed; the
# flat randint in PlayerAttributes.__init__ is just a fallback. Career length is
# roughly longevity + 1 (see the retirement bands below).
LONGEVITY_BASE_MIN = 6              # floor of the random base (was a flat 4-10)
LONGEVITY_BASE_MAX = 12             # ceiling of the random base
LONGEVITY_QUALITY_PIVOT = 82       # talent (seed/rating) above which the bonus starts
LONGEVITY_QUALITY_DIVISOR = 4      # +1 longevity per this many points above the pivot
LONGEVITY_QUALITY_MAX_BONUS = 4    # cap on the quality bonus
LONGEVITY_CEILING = 16             # hard cap on total longevity

# ---- Retirement (keyed to yearsPast = seasonsPlayed - longevity) ----
# `longevity` (quality-weighted, see above) is the intended retirement clock, so we
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

# ---- Name reuse ----
# When a player retires their name is recycled to its next generational variant
# (Base -> Jr. -> III -> IV ...). Instead of returning to the usable pool right
# away, the variant is held for this many seasons before it can be assigned to a
# new player, so a familiar name doesn't reappear the very next season.
NAME_REUSE_DELAY_SEASONS = 5

# ---- Locker-room attitude drift (the toxic <-> leader axis) ----
# Attitude drifts with team record (seasonManager._driftAttitudes): winning trends
# a roster toward Leader, losing toward Toxic. To stop the league from polarizing
# to the poles over many seasons (which empties the middle and turns the FA pool
# into a toxicity sink), a weak MEAN-REVERSION pulls every player back toward
# neutral each week, proportional to their distance from it. The reversion is
# weaker than the active win/loss push, so a genuinely losing team still sours --
# just slower -- while a soured player on a mid-tier team or in the FA pool recovers
# (~+0.4/week at attitude 40 -> Sour in a season, Steady in two).
ATTITUDE_NEUTRAL = 80              # global fallback anchor (used only if a player has no baseline)
# Reversion now pulls toward each player's attitude_baseline (their DISPOSITION), not a
# global neutral — so attitude is a stable trait, and a bad season is a recoverable dip
# rather than a slide into permanent toxicity. Rate raised 0.01 -> 0.05 so reversion
# actually dominates the drift (the old 0.01 was glacial — veterans soured monotonically
# with tenure because the drift accumulated faster than reversion could recover).
ATTITUDE_REVERT_RATE = 0.05       # weekly reversion = this fraction of distance-to-BASELINE
ATTITUDE_DRIFT_MAGNITUDE = 1.5    # win/loss drift multiplier on |winPct-0.5| (dampened 3 -> 1.5)

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

# ---- League realignment (one-time competitive rebalance) ----
# One league had drifted persistently stronger than the other. A one-time
# realignment ranks all teams by combined win% over the last
# LEAGUE_REALIGN_WINDOW_SEASONS completed seasons and serpentine-splits them
# evenly across the two leagues (rank 1->A, 2->B, 3->B, 4->A, ...) so neither
# league stays lopsided. Fires once at a new-season boundary (gated by the
# `league_realigned` app_setting) and the resulting alignment persists via the
# `league_alignment` app_setting, honored by LeagueManager.createLeagues.
LEAGUE_REALIGN_WINDOW_SEASONS = 2

# ---- Retention limits (parity — docs/PARITY_PROSPECT_PLAN.md Phase 5) ----
# Force stacked teams to break up by limiting RETENTION, not salary. Two levers,
# each independently switchable, applied in the offseason re-sign pass:
#  - Re-sign-once: a team may re-sign a given player only RESIGN_ONCE_LIMIT times;
#    after that the player is FORCED to walk to FA (a homegrown core can't be kept
#    forever — guaranteed circulation). Tracked per player via team_resign_count,
#    which increments on each re-sign and resets to 0 when the player walks.
#  - Re-sign count limit: a team may re-sign at most RESIGN_LIMIT_PER_OFFSEASON
#    players in a single offseason; the rest of its expiring players walk. Forces
#    an annual "who do we protect?" decision.
RESIGN_ONCE_ENABLED = True
RESIGN_ONCE_LIMIT = 1             # re-signs allowed with the SAME team before a forced walk
                                  # (1 = a player stays ~2 contracts / 4-5 yrs, then walks —
                                  # this is the real dynasty-breaker; 2 let a 6-peat re-emerge)
RESIGN_LIMIT_ENABLED = True
RESIGN_LIMIT_PER_OFFSEASON = 2    # max players a team may re-sign per offseason

# ---- Cores rule-change vote (docs/RULE_CHANGES_PLAN.md) ----
# A Core-driven, user-voted live rule mutation. Each game day (weeks 1/8/15/22) there's
# an escalating chance a vote fires: Aris opens a CHANGE vote, Pyre opens a REVERT vote.
# Most-voted option wins (no quorum); the winner applies immediately and drifts across
# seasons until reverted. The engine (game_rules.applyRuleChange/revertRule) is safe:
# only floosball_game.py reads the mutable fields (WP/pick-em/MVP are insulated).
RULE_VOTE_ENABLED = True
# Fire chance keyed to consecutive prior game-days THIS season that didn't fire
# (0 misses -> 25%, ramping to a guaranteed fire once three in a row have missed).
RULE_VOTE_RAMP = [0.25, 0.50, 0.75, 1.0]
RULE_VOTE_REVERT_GATE = 3          # changed-rule count that unlocks Pyre reverts (then 50/50 change/revert)
RULE_VOTE_BALLOT_SIZE = 4          # candidate rules offered per vote (plus a "None" option)
RULE_VOTE_CLOSE_LEAD_MINUTES = 15  # vote closes this many minutes before the day's first game
RULE_VOTE_SIM_AUTOPICK = False     # headless sims: random-pick a winner for engine testing (prod stays user-driven)

# The rules Aris/Pyre can vote on. Each field declares its ALTERNATE space, either:
#   "values": [...]           a discrete list of allowed alternates, or
#   "range": [lo, hi]         a numeric range (with "float": True to allow one-decimal
#                             values, e.g. a touchdown worth 6.4; otherwise whole numbers).
# A CHANGE vote proposes one specific value from that space (chosen when the vote opens,
# always different from the current value AND the default), so a rule can be changed again
# to a NEW value before it is ever reverted. A REVERT vote (Pyre) always returns a rule to
# its default. Structural rules stay integer (lists); scoring values may be float (ranges).
RULE_VOTE_CANDIDATES = {
    "downsPerSeries":             {"label": "Downs per series",              "values": [3, 5]},
    "firstDownDistance":          {"label": "Yards to a first down",         "values": [5, 8, 12, 15]},
    "touchdownPoints":            {"label": "Touchdown points",              "range": [4, 9], "float": True},
    "fieldGoalPoints":            {"label": "Field goal points",             "range": [1, 5], "float": True},
    # safetyPoints intentionally NOT votable — safeties are too infrequent for the
    # option to feel worth it (owner 2026-07-12).
    # One general dead-ball clock rule (incompletion / out of bounds / turnover). Default
    # True; the only proposable CHANGE is turning it OFF (a running clock).
    "clockStopsOnDeadBall":       {"label": "Clock stops on dead balls", "values": [False]},
    # Display-only ENUM: how the score is shown (no engine effect). `valueLabels`
    # gives each option a clean display name for the ballot/Rulebook.
    "scoringModel":               {"label": "How the score is shown",
                                   "values": ["additive", "spread", "subtractive"],
                                   "valueLabels": {"additive": "Additive",
                                                   "spread": "Spread",
                                                   "subtractive": "Subtractive"}},
    # On/off MECHANIC toggle (the Conversion Ladder). A bool default False, so the
    # only proposable CHANGE is enabling it; disabling is a REVERT to default.
    "conversionLadderEnabled":    {"label": "Conversion Ladder",
                                   "values": [True], "valueLabels": {True: "On", False: "Off"}},
    # On/off MECHANIC toggle (Sideline Goals). Bool default False — the only proposable
    # CHANGE is enabling it; disabling is a REVERT to default.
    "sidelineGoalsEnabled":       {"label": "Sideline Goals",
                                   "values": [True], "valueLabels": {True: "On", False: "Off"}},
    # On/off MECHANIC toggle (Contested Scoring). Same shape — the only proposable
    # CHANGE is enabling it; disabling is a REVERT to default.
    "contestedScoringEnabled":    {"label": "Contested Scoring",
                                   "values": [True], "valueLabels": {True: "On", False: "Off"}},
    # PRESET candidate (the Drive Clock). Not a scalar field=value — each option is
    # a full {unit, reset, limit} bundle applied as a patch. `gate` is the on/off
    # field used to tell whether the mechanic is currently changed (for revert +
    # changed-count). A CHANGE proposes one random preset (offered only when off);
    # a REVERT resets all the preset's fields to their defaults.
    "driveClock":                 {"label": "Drive Clock", "gate": "driveClockEnabled",
                                   "presets": None},  # filled below (needs DRIVE_CLOCK_PRESETS)
    # PRESET candidate (the Game Format / win condition). One format at a time; each
    # preset is a full {gameFormat, ...config} bundle. `gate` = gameFormat (changed
    # when != 'standard'). Swap-directly: a CHANGE can propose a different format even
    # when one is already active (see ruleVoteManager). Only built formats appear.
    "gameFormat":                 {"label": "Game Format", "gate": "gameFormat",
                                   "presets": None},  # filled below (needs GAME_FORMAT_PRESETS)
}

# The score-display model (additive/spread/subtractive) is a lens over the two
# CUMULATIVE point totals — it only reads sensibly when the raw point total IS the
# meaningful score. So it's offerable on the ballot ONLY under these formats; under
# 'target'/'bust' (the number's race to X is the story) and 'frames' (the score shown
# is frames-won, not points) only additive makes sense, so the candidate is withheld
# (owner 2026-07-12). A REVERT to additive is always allowed (see ruleVoteManager).
SCORING_MODEL_FORMATS = frozenset({'standard', 'play_limit', 'chess_clock', 'innings'})

# Criticality chaos: chance a chaos game picks a non-standard game FORMAT (the format is
# chosen FIRST, then the other rules are randomized within ranges that fit it). Not 1.0
# so some chaos games stay standard-format-with-scrambled-rules.
CHAOS_FORMAT_CHANCE = 0.65

# How the non-format candidates READ on the ballot. A SCALAR shows "<short>: <proposed>"
# with a "Current: <current>" sub-line. An ON/OFF toggle shows an "<enable>" action line
# with a brief "<desc>" under it. (Formats have their own GAME_FORMAT_DESCRIPTIONS; the
# Drive Clock uses "Enable Drive Clock" + the chosen preset's label as the sub-line.)
RULE_BALLOT_META = {
    # scalars — short main-line label
    "downsPerSeries":          {"short": "Downs"},
    "firstDownDistance":       {"short": "Yards to 1st"},
    "touchdownPoints":         {"short": "Touchdown"},
    "fieldGoalPoints":         {"short": "Field goal"},
    "scoringModel":            {"short": "Score display"},
    # on/off toggles — action label + brief explanation
    "conversionLadderEnabled": {"enable": "Enable Conversion Ladder",
                                "desc": "After a touchdown, go for 3, 4, or 5 points from further out instead of the safe kick."},
    "sidelineGoalsEnabled":    {"enable": "Enable Sideline Goals",
                                "desc": "Throw at the sideline hoops for a bonus point while driving down the field."},
    "contestedScoringEnabled": {"enable": "Enable Contested Scoring",
                                "desc": "A touchdown only counts if the scorer beats a defender in a one-on-one contest at the goal line."},
    "clockStopsOnDeadBall":    {"enable": "Enable Running Clock",
                                "desc": "The clock keeps running through incompletions, out of bounds, and turnovers."},
    "driveClock":              {"enable": "Enable Drive Clock"},
}

# ── Conversion Ladder (dormant mechanic — docs/CONVERSION_LADDER_PLAN.md) ──
# After a touchdown the offense picks ONE rung. The safe 1-pt kick and the 2-pt
# try always exist (from extraPointPoints / twoPointConversionPoints); the ladder
# adds higher-value tries snapped from further out (harder to convert). Each rung
# is one run/pass from its distance — "harder from further" emerges from the play
# resolution, not a dial. Off by default; switched on by a Cores vote.
CONVERSION_LADDER_RUNGS = [
    {"points": 3, "distance": 5},
    {"points": 4, "distance": 10},
    {"points": 5, "distance": 15},
]

# ── Sideline Goals (dormant mechanic — docs/SIDELINE_GOALS_PLAN.md) ────────────
# Hoop shots at sideline hoops for `sidelineGoalPoints`. TWO pairs per attacking
# direction: a MIDFIELD pair (~the 50) and an END-ZONE pair (flanking the goal being
# attacked). Each pair is usable ONCE per drive (make or miss locks it). A MAKE banks
# the point + counts as a completion; a MISS is just an INCOMPLETION — both consume the
# down and the drive continues (no turnover). Difficulty EMERGES from the throw: the
# downfield distance from the ball to the near hoop, plus the QB's accuracy/arm vs
# coverage. So a point-blank shot is easy and a long one is hard.
SIDELINE_GOAL_POINTS = 1                 # default points per make (mirrors GameRules default)
# Make-probability model: base (point-blank) − distance − coverage + QB skill.
SIDELINE_GOAL_BASE_MAKE = 0.85           # point-blank make prob (neutral QB, neutral coverage)
SIDELINE_GOAL_DISTANCE_PENALTY = 0.02    # − make prob per yard of downfield distance to the hoop
SIDELINE_GOAL_ACCURACY_SPAN = 0.008      # +/- make prob per skill point off 80 (±~0.16 over the range)
SIDELINE_GOAL_PRESSURE_PENALTY = 0.15    # max make-prob reduction under elite coverage
SIDELINE_GOAL_MIN_MAKE = 0.30            # floor
SIDELINE_GOAL_MAX_MAKE = 0.92            # ceiling — never automatic
# Hoop geometry (in yardsToEndzone terms — distance to the attacking goal line).
SIDELINE_GOAL_MIDFIELD_YARD = 50         # the midfield pair sits at the 50
SIDELINE_GOAL_MIDFIELD_RANGE = 14        # midfield pair in range this many yards BEFORE the 50 only
                                         # (once the LOS is PAST midfield the hoops are behind you)
SIDELINE_GOAL_ENDZONE_MIN = 3            # end-zone pair reachable from the ... 3 ...
SIDELINE_GOAL_ENDZONE_RANGE = 18         # ... out to the 18 (the red zone; not from the goal line itself)
# Play-caller: attempt chance when a fresh pair is in range (a low-risk point-grab now).
SIDELINE_GOAL_ATTEMPT_INRANGE = 0.55     # base chance when in range of an unused pair (a
                                         # low-risk point — teams grab it readily when they can)
SIDELINE_GOAL_ATTEMPT_STALL_MULT = 1.4   # x when the drive is stalling (salvage a point)
SIDELINE_GOAL_ATTEMPT_AGGR_SPAN = 0.25   # + up to this for a max-aggressiveness coach
SIDELINE_GOAL_ATTEMPT_MAX = 0.90         # cap on the attempt chance

# ── Contested Scoring (dormant mechanic — docs/CONTESTED_SCORING_PLAN.md) ──────
# Rugby-flavored: a rushing / receiving / QB-scramble TD is only PROVISIONAL — the
# scorer must complete an ACTION to bank it, and the best-suited defender gets one
# last-resort contest to cancel it. The defense winning is RARE and dramatic (a stuff
# = no points, back to the play's LOS, down advances) — not a scoring nerf. Everything
# emerges from player attributes (natural-emergence principle); off by default.
# Each contest TYPE keys off a different attribute so different players shine; the
# scorer/defender attribute is a weighted blend of real `floosball_player` stats.
CONTEST_TYPES = [
    # key            label            scorer attrs (weighted)          defender attrs (weighted)     solo   weight
    {'key': 'dunk',        'label': 'Dunk',          'scorer': [('power', 0.7), ('xFactor', 0.3)],     'defender': [('power', 0.6), ('agility', 0.4)], 'solo': False, 'weight': 1.0},
    {'key': 'race',        'label': 'Race',          'scorer': [('speed', 1.0)],                       'defender': [('speed', 1.0)],                   'solo': False, 'weight': 1.0},
    {'key': 'arm_wrestle', 'label': 'Arm Wrestle',   'scorer': [('power', 1.0)],                       'defender': [('power', 1.0)],                   'solo': False, 'weight': 1.0},
    {'key': 'beauty',      'label': 'Beauty Contest', 'scorer': [('xFactor', 0.6), ('creativity', 0.4)], 'defender': [('xFactor', 0.6), ('creativity', 0.4)], 'solo': False, 'weight': 0.8},
    {'key': 'backflip',    'label': 'Backflip',      'scorer': [('agility', 1.0)],                     'defender': None,                               'solo': True,  'weight': 1.0},
]
# Balance — P(defense wins) scales with the attribute ratio (see the plan). Even-matchup
# ~13%; a star scorer vs a weak defender almost always banks (~5%); a weak scorer vs a
# stud defender is the danger zone (~25-30%).
CONTEST_DEFENSE_BASE = 0.13              # even-matchup (ratio 1.0) defense-win probability
CONTEST_RATIO_POWER = 2.0               # how sharply the def/scorer attr ratio swings it
CONTEST_DEFENSE_FLOOR = 0.03            # a star scorer is never a sure loss for the defense-win roll
CONTEST_DEFENSE_CEIL = 0.32            # even a mismatch tops out here — offense still wins most
CONTEST_BOTCH_BASE = 0.11              # solo (backflip) botch prob at a neutral (80) scorer
# Mental modifier (phase 2, light): a clutch scorer finishes, a choker fumbles the dunk.
CONTEST_MENTAL_SPAN = 0.05             # max +/- to P(def wins) from pressureHandling + selfBelief
# During a Criticality the contest goes haywire — the defense-win rate is boosted.
CONTEST_CRITICALITY_DEFENSE_MULT = 2.2  # x P(def wins) while a Criticality is live
# Per-type phrasing for the contest play-feed entry (its own beat). "TOUCHDOWN" appears
# ONLY on a win (the entry that books the score), so a stuffed score never shows a TD
# that then vanishes. Gender-neutral; {scorer}/{defender} filled at narration time.
CONTEST_NARRATION = {
    'dunk': {
        'win':   ["{scorer} rises and HAMMERS it over the crossbar. TOUCHDOWN, six points!",
                  "{scorer} throws it down on {defender}. That counts — six points!"],
        'stuff': ["{scorer} goes up for the slam but {defender} swats it away. No good.",
                  "{defender} rises with {scorer} and stuffs the dunk. No points."],
    },
    'race': {
        'win':   ["{scorer} beats {defender} across the end zone. TOUCHDOWN!",
                  "{scorer} outruns {defender} to the far pylon. Six points!"],
        'stuff': ["{defender} runs {scorer} down before the pylon. No good.",
                  "{scorer} races for the corner but {defender} tags him short. No points."],
    },
    'arm_wrestle': {
        'win':   ["{scorer} pins {defender} at the goal line. TOUCHDOWN!",
                  "{scorer} overpowers {defender} and drives across. Six points!"],
        'stuff': ["{defender} out-muscles {scorer} at the line. No good.",
                  "{scorer} can't budge {defender} an inch. Stuffed, no points."],
    },
    'beauty': {
        'win':   ["The judges love {scorer}'s pose over {defender}'s. TOUCHDOWN!",
                  "{scorer} strikes it; {defender} can't match the flair. Six points!"],
        'stuff': ["{defender} out-poses {scorer} — the judges aren't buying it. No good.",
                  "{scorer}'s form falls flat next to {defender}. No points."],
    },
    'backflip': {
        'win':   ["{scorer} flips over the line and STICKS the landing. TOUCHDOWN!",
                  "{scorer} nails the backflip clean. Six points!"],
        'stuff': ["{scorer} flips but stumbles the landing. No good, no points.",
                  "{scorer} can't stick it, hands down. Waved off."],
    },
}
CONTEST_TYPE_LABELS = {t['key']: t['label'] for t in CONTEST_TYPES}

# ── Drive Clock (dormant mechanic — docs/DRIVE_CLOCK_PLAN.md) ──
# A shot-clock for possessions. Two mode knobs: unit ('seconds' of game clock vs
# 'plays' per snap) × reset ('possession' = a hard cap on the whole drive,
# 'series' = refills on each first down). Expire before scoring (or a first down,
# in series mode) = turnover on downs. Off by default; a Cores vote picks a PRESET
# (each a full {enabled, unit, reset, limit} bundle — the compound-rule vote).
DRIVE_CLOCK_DEFAULT_LIMIT = {"seconds": 90, "plays": 6}
# Tuned against the clock-management behavior: when the drive clock is low the
# offense hurries up (~17s/play instead of ~40s), so the seconds limits are kept
# tight enough to still bite. plays/series is deliberately OMITTED — a snap counter
# that refills on each first down is just the down system (N tries to convert).
DRIVE_CLOCK_PRESETS = [
    {"key": "dc_90s_possession", "label": "90 seconds, whole drive",
     "patch": {"driveClockEnabled": True, "driveClockUnit": "seconds",
               "driveClockReset": "possession", "driveClockLimit": 90}},
    {"key": "dc_45s_series", "label": "45 seconds, resets each first down",
     "patch": {"driveClockEnabled": True, "driveClockUnit": "seconds",
               "driveClockReset": "series", "driveClockLimit": 45}},
    {"key": "dc_6plays_possession", "label": "6 plays, whole drive",
     "patch": {"driveClockEnabled": True, "driveClockUnit": "plays",
               "driveClockReset": "possession", "driveClockLimit": 6}},
]
# Wire the presets into the vote candidate (declared above with presets=None to
# avoid a forward-reference).
RULE_VOTE_CANDIDATES["driveClock"]["presets"] = DRIVE_CLOCK_PRESETS

# ── Game Formats / win conditions (docs/GAME_FORMATS_PLAN.md) ──
# Each preset is a full {gameFormat, ...config} bundle. One format at a time. ONLY the
# formats we've tested enough to ship are offerable here (a vote / Criticality can only
# pick from this list). The target / play_limit / bust FORMATS still exist in
# game_formats.py (dormant) — re-add their presets below to re-enable them (owner
# 2026-07-13: hold target/play_limit/bust until they're tested).
GAME_FORMAT_PRESETS = [
    {"key": "gf_chess_clock_18", "label": "Chess Clock (18:00 each)",
     "patch": {"gameFormat": "chess_clock", "offenseClockBudgetSeconds": 1080}},
    {"key": "gf_innings_3", "label": "Innings (3, try-driven)",
     "patch": {"gameFormat": "innings", "inningsPerGame": 3, "triesPerInning": 3}},
    {"key": "gf_frames_6", "label": "Frames (6, match play)",
     "patch": {"gameFormat": "frames", "framesPerGame": 6}},
    # HELD until tested (re-add to re-enable) — the formats themselves are still built:
    #   {"key": "gf_target_30",      "label": "First to 30",
    #    "patch": {"gameFormat": "target", "targetScore": 30}},
    #   {"key": "gf_play_limit_30",  "label": "30 Plays a Quarter",
    #    "patch": {"gameFormat": "play_limit", "playsPerQuarter": 30}},
    #   {"key": "gf_bust_18",        "label": "Darts (land on 18)",
    #    "patch": {"gameFormat": "bust", "targetScore": 18, "sidelineGoalsEnabled": True,
    #              "touchdownPoints": 6, "fieldGoalPoints": 3, "safetyPoints": 2,
    #              "extraPointPoints": 1, "twoPointConversionPoints": 2}},
]
RULE_VOTE_CANDIDATES["gameFormat"]["presets"] = GAME_FORMAT_PRESETS

# Brief, number-free descriptions of each game format for the vote ballot (keyed by the
# format's `gameFormat` value). Shown as the sub-line under "Game Format: <name>".
GAME_FORMAT_DESCRIPTIONS = {
    "standard":    "The usual game. Most points at the final whistle wins.",
    "target":      "A race to the target score. First team to reach it wins.",
    "play_limit":  "No clock. Each quarter is a fixed number of plays.",
    "chess_clock": "Each team gets a set amount of time to possess the ball. Once a team runs out, they can't get the ball back.",
    "innings":     "Teams get 3 \"tries\" per inning. Most points wins.",
    "frames":      "Match play. The game splits into frames. The team with the most points in a frame wins the frame. Most frames wins.",
    "bust":        "Land directly on the target score to win. Overshoot it and the points are voided. Auto-enables sideline targets to help you land it exactly.",
}

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

# Playoff bye reprieve: the top-2 seeds rest through round 1, so their players
# recover a little fatigue while everyone else takes another week of wear.
# Modest by design ("a bit") and scaled by market tier — richer clubs have the
# facilities/medical staff to recover more (same logic as FUNDING_FATIGUE_REDUCTION).
# Each value is a flat fatigue reduction (gauge is 0..1, ~0.0025 gained/week),
# applied once after round 1 and floored at 0.
PLAYOFF_BYE_FATIGUE_RECOVERY = {'MEGA_MARKET': 0.012, 'LARGE_MARKET': 0.009, 'MID_MARKET': 0.006, 'SMALL_MARKET': 0.004}

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
# Center of the compression curve — this is the effective baseline every player
# plays at, so it also sets the league's overall scoring level (higher = more
# offense). Raised 80 -> 84 to recover the scoring the attribute remap cost:
# the remap (skill-creep fix) lowered profile ratings and pulled total scoring
# from ~38 to ~33 pts/game; nudging the in-game baseline up restores ~35 without
# re-inflating any displayed rating (compression only touches the live
# gameAttributes copy). Measured: +1 mean ~= +0.2 pts/team. See _applyLeagueCompression.
LEAGUE_COMPRESSION_MEAN = 84        # Center of the curve

# ── Chess-clock timeouts ──────────────────────────────────────────────────
# In the Chess Clock format the offense's possession budget IS its real clock,
# and a timeout stops the pre-snap huddle drain — so a team preserves its budget
# by calling timeouts once it's GETTING low (not just at the final snap). When
# the offense's remaining budget drops to this many seconds and it's trailing or
# tied, it spends a timeout before the huddle to squeeze more plays out of what's
# left. ~2-3 plays of budget; bounded by the 3 timeouts a team holds.
CHESS_CLOCK_TIMEOUT_PRESERVE_SECS = 90

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

# ── Defensive returns (INT / fumble run-backs) ──────────────────────────────
# After a turnover the recovering defender runs it back. Return distance is
# SPEED-driven (small mean, exponential tail); a speed-scaled breakaway can take
# it a long way and, if it clears the field, produces a pick-six / scoop-and-score
# (the existing defensive-TD branch fires off the resulting field position). The
# geometry self-limits TDs — a house-call needs a near-full-field return. Flip
# RETURN_ENABLED to disable. Tune the breakaway constants to set the pick-six rate.
RETURN_ENABLED = True
RETURN_BASE_YARDS = 4.0          # mean return yards at the speed pivot
RETURN_SPEED_PIVOT = 80          # speed at which base yards apply
RETURN_YARDS_PER_SPEED = 0.3     # mean yards added per speed point above the pivot
RETURN_BREAKAWAY_BASE = 1.5      # % base breakaway (long return) chance
RETURN_BREAKAWAY_PER_SPEED = 0.15  # added breakaway % per speed point above the pivot
RETURN_BREAKAWAY_MAX = 8         # cap on breakaway chance
RETURN_BREAKAWAY_MEAN = 18       # mean EXTRA yards a breakaway adds (exponential tail);
                                 # added on top of the base return, then clamped to the
                                 # field — so a breakaway rarely reaches the end zone
                                 # unless the recovery was already deep (keeps TDs rare)
RETURN_INT_SPOT_BY_DEPTH = {     # where an INT is caught (air yards), by pass depth
    'short': (0, 6), 'medium': (4, 14), 'long': (10, 28), 'hailMary': (15, 45),
}

# ── Blocked kicks (FG / punt) ───────────────────────────────────────────────
# Rare special-teams blocks. The defense recovers at the line of scrimmage and
# can run it back (reuses the return model above). Geometry makes blocked-punt
# scoop-and-scores likelier than blocked FGs — a punting team is backed up, so
# the return to the end zone is short. Tuned for a handful of blocks per league
# season; flip the ENABLED flags to disable.
FG_BLOCK_ENABLED = True
FG_BLOCK_CHANCE = 0.25     # % of FG attempts blocked
PUNT_BLOCK_ENABLED = True
PUNT_BLOCK_CHANCE = 0.1    # % of punts blocked (punts are far more frequent than FGs)

# ── RB pass option (safety-valve checkdown) ─────────────────────────────────
# RBs catch passes: a dump-off to the back when the QB is about to be sacked, or
# when no one downfield is open (instead of throwing it away). Resolves as a short
# completion to the RB — the RB stat + fantasy plumbing already supports receiving,
# so pass-catching backs get realistic receiving production. Keep volume modest (a
# few catches a game). Flip RB_CHECKDOWN_ENABLED to disable.
RB_CHECKDOWN_ENABLED = True
RB_CHECKDOWN_PRESSURE_CHANCE = 45   # % of would-be sacks dumped to the RB instead
RB_CHECKDOWN_OPEN_CHANCE = 55       # % of "no one open" dropbacks checked down to the RB
RB_CHECKDOWN_BASE_YAC = 3.5         # mean YAC on a dump-off at RB speed pivot 78
RB_CHECKDOWN_YAC_PER_SPEED = 0.12   # mean YAC added per RB speed point above 78
# Designed RB screen — a called play (not a pressure reaction) on clean dropbacks.
# Blockers set up out front, so screens carry more YAC upside than a dump-off.
RB_SCREEN_ENABLED = True
RB_SCREEN_CHANCE = 1                # % of clean (non-pressure) dropbacks that are a screen
RB_SCREEN_BASE_YAC = 5.5           # mean YAC on a screen at RB speed pivot 78

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
    "description": "+25% on all Floobit income for 4 weeks — fantasy, pick-em, showcase, and supporter dividends.",
    "price": 100,
    "durationWeeks": 4,
    "seasonLimit": 2,
    # Flat +25% on anything credited while active, applied at the bank
    # (CurrencyRepository.addFunds). See INCOME_BOOST_MULTIPLIER.
    "boostMultiplier": INCOME_BOOST_MULTIPLIER,
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
SHOP_REROLL_COST_INCREMENT = 5   # Each reroll costs 5 more than the last

# Themed pack rotation reroll — pricier than the featured-card reroll because
# the rotation pool includes the higher pack tiers. Rerolling for a premium pack
# should be a real commitment, but not a wall.
THEMED_PACK_REROLL_BASE_COST = 35
THEMED_PACK_REROLL_COST_INCREMENT = 20

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
# the edition multiplier. Escalating so maxing is a multi-week sink (the
# same-effect duplicate requirement is the primary gate), but cut next-season
# alongside the broader economy pass — a Diamond T4 was ~1080 F. Mults chosen so
# base×mult lands on a round 5 at every tier (e.g. Diamond: 80/240/560).
CARD_TIER_UPGRADE_COST = {2: 50, 3: 150, 4: 350}
CARD_TIER_EDITION_COST_MULT = {
    "base": 1.0, "holographic": 1.2, "prismatic": 1.4, "diamond": 1.6,
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
# Recency: newer cards pay more, keyed by card age (seasons old). Newest score full;
# older cards taper but stay meaningfully valuable (the decline was too aggressive
# before — old cards fell off a cliff). Ages past the table use the floor. Non-linear
# on purpose (a flat per-season step can't do this).
SHOWCASE_RECENCY_BY_AGE = {0: 1.0, 1: 0.9, 2: 0.75, 3: 0.6}
SHOWCASE_RECENCY_FLOOR = 0.5   # 4+ seasons old — keep a strong floor so old cards still count
# Upgrade tier lifts a card's showcase value: ×(1 + (tier−1) × THIS).
SHOWCASE_TIER_BONUS_PER_LEVEL = 0.15
# Set bonuses are FLAT completion rewards that ADD into one multiplier:
# score = Σ cardPoints × (1 + Σ bonuses), with the sum capped here so stacked sets
# can't run away. Card quality is already priced into cardPoints (edition/recency/
# tier), so a completed set pays its full bonus regardless of the editions in it.
SHOWCASE_MAX_SET_BONUS = 1.5
# Score → grade (first threshold the score meets, scanning high to low).
# Calibrated against target card-quality profiles + the real season-9 showcases.
# The top grades demand QUALITY (fresh, high-edition, decorated cards), not
# volume or holo set-stacking — edition-scaled sets + steep recency see to that:
#   F/D/C  random accumulation (casual→F/D, regular→D, dedicated/whale→C)
#   B      a deliberately curated showcase, even of holos (full sets)
#   A      a strong fresh showcase (8 decorated prismatics, 8 bare diamonds,
#          or a few decorated diamonds among prismatics)
#   S      ~5-6+ fresh decorated diamonds (compound classifications) — the
#          collector trophy, reached via the collectible shop over time
# S is set so a strong-but-imperfect diamond showcase clears it (not a perfect
# 8/8), since only ~18 players can ever be a decorated diamond — assembling 8
# fresh would be unattainable. Re-featuring last season's diamonds (all 1 yr
# old, ×0.85) still grades well; two seasons old falls off (the recency cliff).
SHOWCASE_GRADE_THRESHOLDS = [
    ("S", 700), ("A", 480), ("B", 240), ("C", 120), ("D", 45), ("F", 0),
]
# Grade is now a legible LABEL only (it no longer sets the payout) — the showcase
# pays a WEEKLY DIVIDEND scaled continuously by the live score, not a flat lump.
#
# Weekly dividend = round(SHOWCASE_DIVIDEND_RATE × finalScore), paid every regular-
# season week (28 weeks) off whatever is featured that week. Calibrated so a
# sustained top showcase earns roughly the OLD end-of-season lump across a full
# season, but the top end is now rewarded above the old flat cap (a perfect S
# out-earns a barely-S one). Reference points at this rate (×28 weeks, if held all
# season): D-entry (45)≈164F, C-entry (120)≈437F, B-entry (240)≈874F, A-entry
# (480)≈1747F, S-entry (700)≈2548F, perfect-ish (~1000)≈3640F. Realized totals run
# lower since the showcase is empty/partial early-season. Re-tune via
# tune_showcase.py / simcheck.
SHOWCASE_DIVIDEND_RATE = 0.13

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
AWARD_MVP_QUORUM = 3                # FLOOR for distinct voters before the fan MVP stands
AWARD_MVP_BALLOT_SIZE = 5   # top N players overall on the MVP ballot (by mvpScore)
AWARD_HOF_QUORUM = 3                # FLOOR for distinct voters before fan induction stands
# Quorum scales with engagement: required voters = max(floor, ceil(activeUsers ×
# this fraction)), where active users = the recent-login + engaged base the
# anomaly threshold uses (anomalyManager._countActiveUsers).
AWARD_QUORUM_ACTIVE_FRACTION = 0.20
AWARD_HOF_BALLOT_PREFILTER = 10     # _computeHofPoints needed to make the ballot (looser than the 22 auto-induct)
AWARD_HOF_CLASS_CAP = 5             # max inductions per season
AWARD_HOF_BALLOT_TENURE = 5         # seasons a candidate stays on the ballot before being dropped
AWARD_HOF_APPROVAL_FRACTION = 0.5   # fraction of HoF voters who must approve to be induct-eligible
AWARD_HOF_AUTO_INDUCT_POINTS = 40   # below quorum, only auto-induct slam-dunks at/above this _computeHofPoints
                                    # (multiple MVPs/rings/records). Merely-qualified players (>=22) need fan votes.

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

# Awakened (L4) signature powers — the mechanical L4 layer (docs/AWAKENED_POWERS_PLAN.md).
# Separate gate from Criticality so the powers can be built + tested on a branch without going live.
# When False: awakening assigns no signature abilities, nothing is surfaced, no game effect.
# When True: awakened players get a fixed offensive + defensive ability + a per-game charge meter
# that fires the ability (~1-2/game), with Criticality as the overdrive. Default OFF.
ANOMALY_AWAKENED_POWERS_ENABLED = False

# Runtime anomaly-intensity presets — the 'anomaly_intensity' app_settings knob maps to one of these
# numeric multipliers, applied to the per-play glitch probability AND the per-game glitch cap. 'normal'
# is the design baseline (1.0); 'chaos' floods, 'low' dampens. Default preset is 'normal'.
ANOMALY_INTENSITY_PRESETS = {'low': 0.5, 'normal': 1.0, 'high': 2.5, 'chaos': 5.0}

# Awakened charge meter (P2) — a per-game bar per awakened player, fed by impact-weighted positive
# involvement (yards on offense, stops on defense, made kicks). Fills ~1-2x/game for a focal player;
# each fill = the signature ability is ready to fire (P3). Tuned in playtest (Criticality scales these
# up via the instability dial in P5).
AWAKENED_CHARGE_THRESHOLD = 100.0   # meter fills at this, then resets and the ability is "ready"
# Charge per PLAY THE PLAYER IS INVOLVED IN (a carry / pass attempt / reception / kick) — a FLAT amount,
# NOT scaled by yards, so a 2-yarder and a 60-yarder charge the same and game-to-game variance is low.
# Each value is the typical number of such involvements a position gets per game; the per-involvement
# charge is THRESHOLD / value, so a position fills ~once over a normal game (late), and falls short on
# a quiet game (so it can fail to fire). Tune these to move the rate per position.
AWAKENED_INVOLVE_PER_GAME = {'QB': 16.0, 'RB': 13.0, 'WR': 5.5, 'TE': 5.5, 'K': 0.5}
AWAKENED_CHARGE_DEF_EVENT = 0.0     # flat charge per defensive stop — kept small so offense dominates
AWAKENED_POWERING_UP_PCT = 0.5      # charge fraction that triggers the "powering up..." feed beat
AWAKENED_DEF_FIRE_CHANCE = 35       # % a ready, position-appropriate defender discharges on a covered snap
                                    # (gates defensive fires so they don't dominate offense — A-lite)
AWAKENED_CRITICALITY_CHARGE_MULT = 4.0  # during a Criticality the charge meter fills this much faster

# A charged awakened kicker extends their FG range, but NOT to infinity — an
# 87-yard attempt reads as broken even for a powered kicker. This is the max
# KICK distance (yardsToEndzone + fgSnapDistance) a charged kicker will attempt;
# their in-range check uses max(normal max, this). ~70 = a huge-but-believable
# "superpowered" boot (the real record is 66). Set very high to restore the old
# "from anywhere" behavior.
AWAKENED_FG_MAX_YARDS = 70

# Play-calling bias toward an AWAKENED (powered-up) skill player — the offense
# feeds the star. Without this the play-caller ignores awakened state entirely,
# so a powered-up RB could sit through six straight passes. Applied as a weight
# multiplier on the play type that targets the awakened player, and (for pass
# catchers) a perceived-openness nudge so the QB actually looks their way.
# Moderate on purpose: it steers the game toward the awakened player without
# making the offense one-dimensional, and it stacks multiplicatively under the
# situational/clock layers so desperation passing still overrides a run bias.
AWAKENED_PLAYCALL_RUN_BIAS = 2.2        # awakened RB: run-weight multiplier
AWAKENED_PLAYCALL_PASS_BIAS = 1.7       # awakened WR/TE: pass-tier (short/medium/long/deep) multiplier
AWAKENED_RECEIVER_OPENNESS_BONUS = 22   # awakened receiver: perceived-openness nudge (0-100 scale)
                                        # (the OVERDRIVE: ~1/game normally -> ~several/game = "frequent")

# Awakened fire outcomes (P3) — when a power fires (run/scramble/pass) the play is always SUCCESSFUL:
# it gains at least a first down (floored at AWAKENED_FORCE_MIN_GAIN), PLUS an exponential tail so
# longer breakaways are progressively rarer instead of every fire being a 40+ bomb. Capped at the end
# zone (reaching it = a TD). So a fired play is usually a clean conversion, occasionally a chunk play,
# rarely a house call. Tail = the exponential mean of the bonus yardage above the first-down floor.
AWAKENED_FORCE_MIN_GAIN = 10   # floor: never less than a first down's worth (max'd with yardsToFirstDown)
AWAKENED_FORCE_GAIN_TAIL = 12  # exponential mean of bonus yards beyond the floor (lower = tighter to the floor)

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
# During a Criticality the mechanical glitch spreads league-wide: ANY carrier can
# warp (parity — every team is in the chaos), but non-cultivated players (not
# rampant/awakened) fire at this fraction of the full rate, so genuinely-awakened
# players still trigger more (the retained edge). 1.0 = full parity, 0 = old behavior.
CRITICALITY_L3_FLOOR_FRACTION = 0.4

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