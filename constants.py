# Env-override helper — several balance levers below can be A/B'd from the
# environment without editing this file. Imported here so every such lever,
# wherever it sits in the file, can read it.
import os as _os

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
MVP_WPA_WEIGHT = 0.2         # per-GAME OFFENSIVE WPA share (offensive clutch)
# ⚠️ 0.3 -> 0.2, PAIRED with wpaRate moving from per-snap to per-GAME. Measured over
# 20 simulated seasons: per-snap at 0.30 gave quarterbacks 1 MVP in 20 (receivers took
# 11), because a QB logs ~1,233 WPA snaps a season against a receiver's ~290 and so
# carries the league's lowest per-snap rate despite its second-highest raw WPA. Per
# game at 0.30 over-corrects to QB 14 of 20; at 0.20 it splits QB 8 / WR 8 / RB 3 /
# TE 1. Changing either half alone reproduces one of the two failures.
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
# Per-game decay pulling persistent confidence/determination back toward neutral.
# The streak boost in Player.postgameChanges accumulates with nothing pulling it
# back, so a club on a run reaches the +-5 ceiling in ~20 games and stays pinned,
# while a bad start digs a hole the roster can't climb out of. Decay gives a streak
# a real but FADING lift: steady state is roughly meanBoost / (1 - decay), so 0.90
# settles a sustained run near +1.25 instead of pinning at +5. 1.0 disables.
# Measured on fresh 32-club leagues, 24 seasons per arm, against a no-loop control:
#   0.95 -> 23% of the available drop in win std dev (too weak to bother with)
#   0.90 -> 86% of it, and 101% of the drop in 3+ season contender runs
# 0.90 therefore captures nearly all the dispersion benefit while a streak still
# means something. Title concentration only improves part-way at either value,
# which points at roster quality rather than morale for the rest.
CONFIDENCE_DECAY_PER_GAME = 0.90

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
COACH_ATTR_RANGE = 20           # Half-range used to normalize coach attributes to [-1, 1]
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
    # QB SNEAK — situational only. `base` 0 because it is never part of the normal
    # weighting: _selectRunConcept skips it and injects its weight explicitly when
    # the down/distance qualifies. Nothing deceptive (deception 0) — everyone in
    # the stadium knows it's coming; it wins on leverage, not surprise. Punished
    # hard by a run-committed box (runFocus -0.55, steeper than power) because
    # stacking the A-gap is exactly the answer to it, and helped slightly by a
    # blitz (rushers moving upfield vacate the interior surge).
    'sneak':   {'base': 0.00, 'deception': 0.00, 'exec': {'power': 0.7, 'discipline': 0.3},
                'edge': {'blitz': 0.15, 'runFocus': -0.55, 'aggr': 0.00},
                'gaps': {'A-gap': 1.00}},
}

# ---------------------------------------------------------------------------
# Ball-carrier moves — stiff arm / spin / hurdle
# ---------------------------------------------------------------------------
# A carrier about to be brought down tries to beat the tackler for extra yards.
# Slots into the same place `_stretchForFirst` does (the shared run tail, used by
# both runs and receptions) and returns the same shape.
#
# The three-part model these all follow, and which the stretch and the diving
# catch now follow too:
#   WILLINGNESS to try it   <- flair (creativity + xFactor) and mental state
#                              (confidence + determination)
#   ABILITY to pull it off  <- the physical attribute the move actually uses
#   RISK taken on           <- discipline (exposure -> fumble bump)
# That split is what gives `creativity` and `xFactor` real work: before this they
# were almost inert in play resolution (xFactor appeared in one QB-mobility
# calculation, creativity in two concept exec weights and otherwise nothing).
RUNNER_MOVE_ENABLED = True
RUNNER_MOVE_BASE_CHANCE = 0.05    # attempt rate for a neutral-flair, neutral-state carrier
RUNNER_MOVE_FLAIR_K = 0.18        # how much full flair raises the attempt rate
RUNNER_MOVE_STATE_K = 0.06        # how much confidence+determination raise it
# Per move: the attribute(s) that decide success, the yardage band on a make, and
# `risk` scaling the fumble bump on the attempt. Bigger swings cost more.
RUNNER_MOVES = {
    'stiff arm': {'attrs': {'power': 1.0},                  'gain': (1, 3), 'risk': 0.6},
    'spin':      {'attrs': {'agility': 1.0},                'gain': (1, 4), 'risk': 0.9},
    'hurdle':    {'attrs': {'agility': 0.6, 'speed': 0.4},  'gain': (2, 5), 'risk': 1.5},
}
RUNNER_MOVE_BASE_SUCCESS = 42.0   # % before the attribute-vs-tackler term
RUNNER_MOVE_SWING = 1.15          # % per point of (carrier attribute - tackler defense)
RUNNER_MOVE_SUCCESS_MIN = 12.0
RUNNER_MOVE_SUCCESS_MAX = 88.0
# The defender's resistance blends SKILL and DISCIPLINE. Tackling is whether they
# can bring the carrier down; discipline is whether they stay square and refuse to
# bite on the move in the first place — which is what actually beats flair. A
# disciplined defender resists the high-risk moves hardest (`disciplineRiskK`
# scales by the move's own risk), so a hurdle against a squared-up veteran is a
# bad idea and a hurdle against a lunger is not.
RUNNER_MOVE_DEF_TACKLING_W = 0.6
RUNNER_MOVE_DEF_DISCIPLINE_W = 0.4
RUNNER_MOVE_DISCIPLINE_RISK_K = 6.0   # extra % resistance per unit risk from a disciplined defender
# Contact gate — a move only happens at the point of contact. Beyond this many
# yards the carrier is into open field with nobody to beat, and a stiff-arm on a
# 40-yard housecall reads as nonsense.
RUNNER_MOVE_MAX_CONTACT_YARDS = 12
# Beating a man is a confidence event for both players. Small, and it uses the
# same in-game confidence channel everything else does.
RUNNER_MOVE_CONF_CARRIER = 0.04
RUNNER_MOVE_CONF_DEFENSE = -0.02

# Flair — the shared "does this player try audacious things" term, 0..1, built
# from creativity + xFactor around the 80 house-neutral pivot.
FLAIR_PIVOT = 80.0
FLAIR_RANGE = 20.0
FLAIR_CREATIVITY_W = 0.5
FLAIR_XFACTOR_W = 0.5
# How much flair and determination feed the EXISTING audacious plays, so the same
# attributes matter there too rather than only on the new moves.
STRETCH_FLAIR_K = 12.0            # success-chance points at full flair on a stretch
STRETCH_DETERMINATION_K = 8.0     # success-chance points at full determination
DIVE_FLAIR_K = 4.0                # catch-prob points at full flair on a lay-out
DIVE_DETERMINATION_K = 3.0        # catch-prob points at full determination

# ---------------------------------------------------------------------------
# Pre-snap recognition (the defense's read)
# ---------------------------------------------------------------------------
# Everything else in the playbook resolves deception as an OFFENSIVE execution
# roll against the defense's standing gameplan numbers — `conceptTelegraphed` is
# the runner executing badly, play-action bites according to a pre-set
# runStopFocus, tricks pay off against a tendency. The defense never made a
# per-play decision it could be right or wrong about, which is also why
# `defensiveMind` did no per-play work at all.
#
# This is the mirror of the RPO read: before the play resolves, the defense
# commits to run or pass.
PRESNAP_READ_ENABLED = True
# Base accuracy for a league-average defense. 0.50 is deliberate: at the average
# the layer nets ZERO (right and wrong are equally likely, and the payoffs are
# equal and opposite), so it REDISTRIBUTES between sharp and poor defenses
# rather than taxing offense league-wide. League scoring should not move.
PRESNAP_READ_BASE = 0.50
PRESNAP_READ_SKILL = 0.26         # swing from coach defensiveMind + the reader's instinct/focus
PRESNAP_READ_EDGE = 0.09          # defensive multiplier swing on a correct vs wrong read
# Disguise — how much each fake degrades recognition. This is the whole point of
# a fake, and until now they had nothing to beat but a static tendency.
PRESNAP_DISGUISE = {
    'playAction': 0.22,
    'rpo':        0.30,           # genuinely both plays until the QB decides
    'sneakLook':  0.28,
    'trick':      0.32,
}
# Run concepts that disguise against a RUN/PASS read specifically.
#
# Deliberately not "every concept, scaled by its `deception` value". What a
# concept deceives ABOUT decides whether it belongs here:
#   * draw    — a RUN that looks like a PASS. The exact mirror of play-action,
#               and it attacks precisely the question this layer asks. Belongs.
#   * counter — deceives about DIRECTION (misdirection vs over-pursuit).
#   * sweep   — deceives about direction/edge speed.
# The read only commits to run-or-pass, so counter and sweep have nothing here
# to fool; paying them would be rewarding them for beating a read that never
# happened. They already get their payoff in the concept-edge channel. If the
# layer ever grows a directional commit, this is where they'd earn one.
PRESNAP_CONCEPT_DISGUISE = {'draw': 0.24}
# ⚠️ THE NO-HUDDLE TELEGRAPH — a NEGATIVE disguise, and the thing that pays for the tempo.
# An offense standing at the line can only throw short or medium at the sideline (see
# `_applyNoHuddleMenu`), and a defense that knows this reads it. Without this, no-huddle
# is a free win: measured, it buys 12.0s -> 6.0s of pre-snap drain and 6.0 -> 9.5 snaps in
# a 110-second drill, and nothing charged for the predictability.
#
# Sized alongside the fakes it mirrors (playAction .22, sneakLook .28, rpo .30, trick .32)
# because it is the same quantity pointed the other way: a fake subtracts from the
# defense's accuracy, a telegraph adds to it. At this value a league-average defense reads
# a no-huddle snap right about 78% of the time instead of 50%.
#
# ⚠️ This is the ONE place the pre-snap read is deliberately NOT zero-sum. Everywhere else
# `PRESNAP_READ_BASE` 0.50 means an average defense nets nothing and the layer only
# redistributes between sharp and poor staffs. Here the offense has chosen a state that
# tells the defense what is coming, so the defense SHOULD net a gain — that gain is the
# price of the extra snaps.
NO_HUDDLE_TELEGRAPH = 0.28

# ── Audibles ──────────────────────────────────────────────────────────────
# ⚠️ THE OFFENSIVE MIRROR OF `_applyPreSnapRead`. The defense has committed run-or-pass
# before the snap since the pre-snap recognition layer shipped; the offense had no
# equivalent. Every deception in this sim is an offensive EXECUTION roll against the
# defense's standing numbers, and nothing let the quarterback look at what he sees and
# change it.
#
# What he reads is the box: `runStopFocus`, the defense's own run-vs-pass tilt, which
# measures 0.26-0.73 across generated defenses with a median near 0.46.
AUDIBLE_ENABLED = True
AUDIBLE_BOX_STACKED = 0.55        # above this the box is sold on the run; below, it is light
# Accuracy of the read. 0.5 would be a coin flip; a league-average QB should be better than
# that at simply seeing a stacked box, so the base sits above it and skill moves it.
AUDIBLE_READ_BASE = 0.62
AUDIBLE_READ_SKILL = 0.30         # swing across the attribute range
# ⚠️ THE QB DOMINATES, and that asymmetry is the point. The defense's read is coach 60 /
# players 40 (he installed the checks and the LB/S execute); the audible is the one place
# in the sim where the PLAYER, not the coach, makes the call.
AUDIBLE_QB_WEIGHT = 0.70
AUDIBLE_COACH_WEIGHT = 0.30
# ⚠️ WILLINGNESS IS `_undiscipline`, NOT `flairOf` (settled 2026-08-16 against 34 QBs).
# Every QB mental attribute correlates 0.65-0.77 with every other, and `flairOf` sits at
# +0.77 with `instinct` — so using it collapses the 2x2 onto its diagonal and the mind
# game degenerates into a rating check. Discipline correlates only +0.42 AND in the
# helpful direction: willingness is LOW discipline, so it runs NEGATIVELY against reading
# ability. Sharp QBs are disciplined and stand pat; blind QBs are gunslingers and check
# anyway. Measured, that takes the trap cell (bold + blind) from 6% of QBs to 26%.
AUDIBLE_WILLINGNESS_BASE = 0.30   # a fully disciplined QB still checks sometimes
AUDIBLE_WILLINGNESS_SWING = 0.55  # a gunslinger checks far more often

# ── Defensive disguise ────────────────────────────────────────────────────
# ⚠️ THE PIECE THAT MAKES THE OTHERS A SYSTEM. Without it the QB reads an honest defense
# and an audible is just a skill check the good QB always passes. With it, what the
# defense SHOWS and what it DOES come apart: a fooled quarterback checks into a trap and a
# sharp one sniffs it out.
#
# It also gives `defensiveMind` a genuine two-sided role — reading the offense's intent
# (shipped with the pre-snap read) and hiding its own (here). A staff strong in one and
# weak in the other should feel different to play against.
DEFENSIVE_DISGUISE_ENABLED = True
# How often a defense lies, before coaching. A sharp staff installs and calls disguises; a
# poor one plays what it lines up in.
DISGUISE_BASE_RATE = 0.18
DISGUISE_COACH_SWING = 0.30       # defensiveMind takes it roughly 0.03 -> 0.48
# ⚠️ HOLDING THE LOOK IS A SEPARATE CHECK, and a blown one is WORSE than never lying: the
# QB gets a free read AND the defense has committed late. Discipline and focus hold it.
DISGUISE_HOLD_BASE = 0.72
DISGUISE_HOLD_SWING = 0.24        # ~0.60 for a sloppy unit, ~0.84 for a disciplined one
# ⚠️ A DISGUISE MUST COST SOMETHING, OR EVERY DEFENSE DISGUISES EVERY PLAY. A defense
# showing blitz and dropping is, for that snap, slightly out of position against what it
# did not prepare for. Small on purpose — it is a tax on lying, not a reason never to.
DISGUISE_ALIGNMENT_COST = 0.06
# A tipped disguise pays the cost anyway AND hands over the read, which is what makes
# `discipline` worth having on a defense.
DISGUISE_TIPPED_EXTRA_COST = 0.04
# Scaled by how well this back sells it (_runConceptExecQ, deterministic from
# attributes): a shifty, cerebral back disguises a draw; a plodder telegraphs it.
# Range is this floor to 1.0 of the nominal value above.
PRESNAP_CONCEPT_DISGUISE_FLOOR = 0.5
# Leverage — the read only pays where the situation is genuinely ambiguous. On
# 3rd-and-15 both sides know it's a pass, so guessing right isn't skill; those
# spots are already handled by the situational branch in getDefensiveScheme.
# Scaling by leverage is also what stops this layer double-counting with it.
PRESNAP_LEVERAGE_FLOOR = 0.20     # obvious situations still leave a sliver
PRESNAP_OBVIOUS_SHORT = 2         # ytg at or under this reads run to everyone
PRESNAP_OBVIOUS_LONG = 12         # ytg at or over this reads pass to everyone

# ---------------------------------------------------------------------------
# QB sneak (short-yardage concept — see RUN_CONCEPTS['sneak'])
# ---------------------------------------------------------------------------
# The QB follows the interior surge for the yard. Mechanically unlike a tailback
# run: it is a leverage play with a HIGH floor and almost no ceiling, so it does
# NOT run the three-gate model (no second level, no breakaway — a sneak never
# goes 40 yards). It resolves on one push and rejoins the shared run tail, so
# stats/WPA/fumbles/PBP all flow through the existing paths.
QB_SNEAK_ENABLED = True           # flip off to remove sneaks entirely
QB_SNEAK_MAX_YTG = 2              # only with this many yards or fewer to go
QB_SNEAK_GOAL_LINE_YTE = 2        # ...or this close to the goal line (any down)
QB_SNEAK_MIN_DOWN = 3             # 3rd/4th down, unless it's goal-line
QB_SNEAK_WEIGHT = 1.30            # call propensity against power in sneak range
# Conversion odds. The pivot compares the QB's push (power/discipline, the same
# attributes as the concept's exec roll) against the defense's effective run
# defense. Real short-yardage sneaks convert at a very high rate, which is the
# point of the play — hence a high base and a generous ceiling.
QB_SNEAK_BASE_SUCCESS = 76.0      # % before the matchup term
QB_SNEAK_SUCCESS_SWING = 0.85     # % per point of (QB push - effective run D)
QB_SNEAK_SUCCESS_MIN = 42.0
QB_SNEAK_SUCCESS_MAX = 93.0
QB_SNEAK_GAIN_MEAN = 1.6          # yards when the push gets there
QB_SNEAK_GAIN_MAX = 4             # a sneak that "breaks" still only falls forward
QB_SNEAK_STUFF_MEAN = 0.2         # yards when stuffed (rarely a loss — it's a pile)

# ---------------------------------------------------------------------------
# Sneak-look trick (the fake off the sneak)
# ---------------------------------------------------------------------------
# Show the sneak, then don't run it. Only worth calling when the defense has
# actually committed to stopping the sneak — a stacked box vacates the edge and
# the flat, which is what the fake attacks. Same design rule as the other trick
# plays: match the gadget to the tendency, never gadget for its own sake.
SNEAK_LOOK_ENABLED = True
SNEAK_LOOK_BASE = 0.16            # chance in a qualifying spot, before gating
SNEAK_LOOK_MIN_RUNFOCUS = 0.52    # D must be leaning run for the fake to pay
SNEAK_LOOK_AGGR_PIVOT = 78        # coach aggressiveness where the call unlocks
SNEAK_LOOK_PITCH_SHARE = 0.55     # split between pitch-to-the-RB and quick pass
SNEAK_LOOK_PITCH_EDGE = 0.55      # run-def relief on the pitch (interior crashed down)
SNEAK_LOOK_PASS_OPENNESS = 26     # receiver openness on the quick throw off the fake

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
# ---- Tail knee ----
# ⚠️ THE TAPER WAS WORKING AND THE TAIL WAS STILL RUNNING AWAY. Measured over 2,221 real
# user-weeks (production, seasons 12+, which is post-card-rebalance): the power curve
# compresses an FP spread of 30.7x (p50 261 FP, p99 8,006 FP) down to 14.5x in Floobits —
# so the taper does its job — but the ABSOLUTE tail is still p99 1,219 F and a maximum of
# 5,165 F for a single week, against a median week of 84 F. A pack costs 40-100 F, so one
# outlier week bought 12-50 of them.
#
# ⚠️ SHARPENING THE EXPONENT IS THE WRONG LEVER, and it is the obvious one. The exponent
# applies from the very first point, so it cannot touch the tail without dragging typical
# play down with it: 0.78 -> 0.70 takes the MEDIAN week 84 F -> 54 F and total payout to
# 56%; 0.65 takes it to 41 F and 40%. That would undo the deliberate ~2.3x lift above,
# which exists because actually playing fantasy earned ~830 F/season against ~5k from
# parking Floobit-output cards. The median is the number that lift was bought for.
#
# ⚠️ A HARD CAP IS ALSO WRONG, AND WAS ALREADY TRIED — `2bf171b` ("replace cap with log
# curve") removed one. A cap makes every week past it pay identically, so a great week and
# an absurd week are indistinguishable and the incentive to keep playing dies at the cap.
# Modelled at 400 F it holds the median but flattens everything above p93 onto one value.
#
# So the taper gets a SECOND, harsher taper above a knee. Below the knee nothing changes
# at all (p25/p50/p75 are identical by construction); above it each doubling of FP pays
# 2^0.45 instead of 2^0.78. It is continuous at the knee and strictly monotonic, so a
# bigger week always pays more — the property the cap gave up.
#
# Measured effect, same 2,221 user-weeks:
#   p25/p50/p75   50 / 84 / 183 F   unchanged
#   p90          363 -> 349 F       (-4%)
#   p99        1,219 -> 702 F       (-42%)
#   max        5,165 -> 1,614 F     (-69%)
#   spread p99/p50  14.5x -> 8.4x ·  total payout 86% of current
#
# The knee sits just below p90 (1,696 FP), so it bites roughly the top decile of weeks and
# leaves everything a normal player experiences alone. Lower it toward 1,000 to bite the
# top fifth (p90 -16%, total 81%); raise it to leave more of the tail intact.
#
# ⚠️ THIS IS DOWNSTREAM OF CARD BALANCE. The FP tail is manufactured by FPx multipliers
# compounding, so an overtuned card shows up here as an economy problem. Prefer fixing the
# card (see Diversified) over steepening this; the knee is a backstop, not the cure.
WEEKLY_FP_FLOOBIT_KNEE = 1500.0      # FP at which the second taper starts
WEEKLY_FP_FLOOBIT_TAIL_EXPONENT = 0.45   # exponent applied to FP past the knee


def weeklyFpFloobits(weekFp: float) -> int:
    """Floobits for a week's fantasy points. THE single definition of the curve.

    Power curve up to `WEEKLY_FP_FLOOBIT_KNEE`, then a harsher one past it. Continuous at
    the knee (both branches agree there) and monotonic everywhere, so a bigger week is
    always worth more.
    """
    if weekFp <= 0:
        return 0
    if weekFp <= WEEKLY_FP_FLOOBIT_KNEE:
        return round(WEEKLY_FP_FLOOBIT_SCALE * (weekFp ** WEEKLY_FP_FLOOBIT_EXPONENT))
    atKnee = WEEKLY_FP_FLOOBIT_SCALE * (WEEKLY_FP_FLOOBIT_KNEE ** WEEKLY_FP_FLOOBIT_EXPONENT)
    return round(atKnee * ((weekFp / WEEKLY_FP_FLOOBIT_KNEE) ** WEEKLY_FP_FLOOBIT_TAIL_EXPONENT))
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

# ---- Team Form Oscillation ----
# A continuous per-team form multiplier so clubs run hot and cold ACROSS a season
# instead of playing at one fixed level all year. Before it existed, the sd of a
# club's wins across the four game days was 1.06 against a coin-flip line of 1.32
# — team form varied LESS than chance, and a season was legible from game one
# (corr(day-1 wins, final wins) = +0.750).
#
# THE KEY MEASUREMENT (FLOOS_FORM_FORCE, 16,128 team-games): a ±10% roster-wide
# rating multiplier is worth ±4.5 wins over a 28-game season — 1.619 win
# probability per 1.0 of multiplier. The transfer is STEEP. Measure this before
# tuning any rating-multiplier layer; it is easy to assume a lever is weak when
# what is actually happening is that its value never sits near its clamp.
#
# WHY MOMENTUM AND NOT MEAN REVERSION. The layer was first built mean-reverting
# (deviation from your own level pulls you back). It moved form variance 1.06 ->
# 1.11 and no amount of amplitude helped, because the failure is structural: an
# arc IS a sustained multi-week deviation, and negative feedback exists precisely
# to cancel sustained deviation. Momentum — a run feeds itself, bounded by an
# unconditional weekly FORM_DECAY rather than by a restoring force — is what
# actually produces arcs, and the decay keeps it from running away (measured
# win-sd is unchanged vs the reverting design).
#
# MEASURED (8 fresh 32-club leagues x 5 seasons per arm, ~1,275 team-seasons):
#
#   arm                        form var   flat (<1.0)   win spread   corr(day1,final)
#   control (no form)             1.06       45%           22.3          +0.750
#   mean-reverting (as specced)   1.11       39%           22.0          +0.752
#   momentum                      1.36       25%           21.5          +0.593
#   momentum + parity package     1.46       18%           19.4          +0.502
#
# Momentum clears the 1.32 coin-flip line, which was the plan's own bar for real
# oscillation. The plan's 1.6-1.9 target is retired as unreachable: at 7 games a
# block, binomial noise alone has sd 1.32 and dominates, so 1.75 would need a club
# to genuinely become a different-quality team for seven straight weeks.
#
# It does NOT replace FORM_STATE_RATING_MULT above, which stays the discrete
# badge/flavour layer with every positive state pinned at 1.00.
#
# Env switches for A/B sweeps (unset = shipped): FLOOS_FORM=off, FLOOS_FORM_FEEDBACK,
# FLOOS_FORM_PULL / _REVERSION / _NOISE / _MAX / _DECAY, FLOOS_FORM_PLAYOFFS=off,
# FLOOS_FORM_PLAYOFF_SCALE, and FLOOS_FORM_FORCE for the transfer calibration.
FORM_OSCILLATION_ENABLED = _os.environ.get('FLOOS_FORM') != 'off'
# Calibration only: pin even-id teams at +this and odd-id at -this all season, so
# the win-rate gap between the halves measures the rating-multiplier -> win-
# probability transfer directly. 0 = off (normal play). See Game._applyFormOffset.
FORM_FORCE = float(_os.environ.get('FLOOS_FORM_FORCE', '0'))

# Calibration only: multiply ONE roster slot's in-game attributes up on even-id
# teams and down on odd-id teams, to measure that position's CAUSAL impact on
# winning. Correlation between a position's rating and team wins cannot separate
# "this position barely matters" from "this rating poorly summarizes the position";
# forcing the attributes directly can. 0 = off. See Game._applyPositionForce.
POSITION_FORCE = float(_os.environ.get('FLOOS_POS_FORCE', '0'))
POSITION_FORCE_SLOT = _os.environ.get('FLOOS_POS_SLOT', 'qb')

# ---- Kicking: field goals ----
# FG success used to key off the kicker's OVERALL rating, which is
# (legStrength+accuracy)/2 * 3/5 + playMaking/5 + xFactor/5 -- so leg strength was
# ~30% of success and playmaking/xFactor together were 40%, neither of which
# should decide whether a kick goes through the uprights.
#
# The model now matches how kicking actually works: LEG STRENGTH sets RANGE (it
# already drives maxFgDistance), ACCURACY decides whether it is on line, and the
# existing pressure layer handles nerve. The margin term is the important part --
# what matters is not raw leg but how much leg you have TO SPARE at this distance.
# A kick at the edge of a kicker's range is a very different proposition from the
# same distance for someone with 10 yards in hand, which is why most kickers can
# hit 50-55 and only the elite-elite convert from 60+.
FG_CURVE_CENTER = 58.0      # distance at which the raw curve sits at 50%
FG_CURVE_SLOPE = 0.14       # how sharply make% falls with distance
FG_SKILL_BASE = 0.90        # multiplier at a neutral (80 accuracy, comfortable range) kick
FG_ACCURACY_WEIGHT = 0.30   # primary driver: (accuracy-80)/20 scaled by this
FG_MARGIN_WEIGHT = 0.26     # how much spare leg matters
FG_MARGIN_SCALE = 12.0      # yards of spare leg for a full +1 margin term
FG_MARGIN_FLOOR = -1.4      # at/over the range limit, the penalty bottoms out here
FG_MARGIN_CEILING = 0.35    # plenty of leg helps, but only so much -- accuracy still rules

# ---- Kicking: punts ----
# Punts were `randint(70*legStrength/100 - 20, 70*legStrength/100)` and nothing
# else: no accuracy, no placement, no touchback risk, no reason to punt any
# differently from your own 5 than from midfield. Leg strength is the RIGHT lever
# for a punt (unlike a field goal) -- but distance alone is not the whole job.
#
# Four types, chosen by field position and situation:
#   boomer  deep in your own end -- flip the field, low and long. Pure leg.
#   standard
#   pin     from around midfield -- shorter, higher, aim to down it inside the 20.
#   coffin  the audacious one -- aim at the sideline inside the 10. Big reward,
#           and a miss is a touchback that gives back ~20 yards of it.
#
# Ability is ACCURACY; willingness to try the coffin corner comes from _flair
# (creativity + xFactor), the same three-part model the sim uses for runner moves
# and diving catches.
PUNT_TYPES_ENABLED = _os.environ.get('FLOOS_PUNT_TYPES') != 'off'
# legStrength * this = a punter's ceiling. Raised from 0.70 when the shank and the
# missed-pin outcomes landed: those are correct behavior, but they cost ~2.5 yards
# of league gross average, so the base kick has to absorb them.
PUNT_MAX_YARDS_PER_LEG = 0.755
PUNT_BOOMER_YTE = 65            # own end: at/beyond this yards-to-endzone, boom it
PUNT_PIN_YTE = 58               # inside this, placement starts to matter
PUNT_COFFIN_MAX_YTE = 52        # coffin corner only makes sense this close in
PUNT_COFFIN_MIN_YTE = 38
PUNT_COFFIN_ELECT_BASE = 0.10   # baseline willingness to try it...
PUNT_COFFIN_ELECT_FLAIR = 0.45  # ...scaled by flair
PUNT_ACCURACY_PIVOT = 80.0
# Placement success: chance of downing it inside the 20 on a pin, or inside the 10
# on a coffin corner. Accuracy-driven, and a coffin miss is a touchback.
# The inside-20 rate is GEOMETRIC, not placement-driven: halving these barely moved
# it (52% -> 53%), because a 46-yard punt from your own 35 lands inside the 20 no
# matter how it was struck. What was actually missing was the RETURN -- see below.
PUNT_PIN_BASE = 0.48
PUNT_PIN_ACC_K = 0.32
PUNT_COFFIN_BASE = 0.34
PUNT_COFFIN_ACC_K = 0.40
PUNT_COFFIN_TOUCHBACK = 0.30    # a missed coffin corner sails through
# A missed PIN has degrees too -- it either sails too deep (touchback) or comes up
# short and hands the opponent a returnable ball around their own 25-30. Before
# this a failed pin silently landed at its distance draw, i.e. it was still a good
# punt: only the coffin corner had any downside, which is backwards.
PUNT_PIN_TOODEEP = 0.22         # share of missed pins that sail through
PUNT_PIN_SHORT_MIN = 17         # a pin that comes up short lands out this far
PUNT_PIN_SHORT_MAX = 25
# THE SHANK. Nothing modeled a punt simply coming off the foot badly, on ANY punt
# type -- so a routine punt could never cost you field position. Accuracy prevents
# it; it cancels whatever placement was intended.
PUNT_SHANK_BASE = 0.038         # ~4% of punts, in line with real sub-30-yard punts
PUNT_SHANK_ACC_K = 0.050        # accuracy swing
PUNT_SHANK_MIN = 14
PUNT_SHANK_MAX = 30
PUNT_TOUCHBACK_TO = 20          # touchback spots the ball here
# Punt clock. A punt burned only 4-6s (snap to kick) -- but the ball hangs and the
# return takes time, so the live-ball portion is far longer than that. The clock
# still STOPS after a punt regardless of whether the returner was tackled in
# bounds, because a punt is a change of possession.
PUNT_HANG_SECONDS = (3, 5)      # snap-to-catch hang on top of the kick itself
PUNT_RETURN_SECS_PER_YARD = 0.32
# Punt returns. Without these, gross average IS net average and the ball is downed
# inside the 20 on ~52% of punts against a real ~35%. Real football nets ~41 off a
# ~46 gross, and that missing ~5 yards is most of the difference. The returner is
# the receiving team's WR1 (the sim's WR->CB mapping makes them the coverage-unit
# athlete); speed and agility drive it.
PUNT_RETURN_ENABLED = _os.environ.get('FLOOS_PUNT_RETURNS') != 'off'
PUNT_RETURN_BASE = 7.0          # mean return yards at a neutral (80/80) returner
PUNT_RETURN_SPREAD = 4.5
PUNT_RETURN_ATTR_K = 6.0        # speed/agility swing on the mean
PUNT_RETURN_BREAK_CHANCE = 0.045    # a return that genuinely breaks open
PUNT_RETURN_BREAK_MEAN = 22.0
# The returner is whichever of WR1/WR2/RB is the most explosive (speed+agility) --
# a real team puts its best athlete back there, not a fixed slot.
# FAIR CATCH is a DECISION, not a distance rule: the returner weighs how deep he
# is and how fast the coverage is on him, with instinct deciding how well he reads
# it. A short, high (pin/coffin) punt hangs longer, so coverage arrives sooner.
PUNT_FAIRCATCH_BASE = 0.20          # baseline waving it off on a returnable ball
PUNT_FAIRCATCH_DEEP_INSIDE = 10     # this close to his own goal, almost always fair
PUNT_FAIRCATCH_HANG_BONUS = 0.34    # pin/coffin punts hang -> far likelier fair catch
PUNT_FAIRCATCH_INSTINCT_K = 0.22    # instinct shifts the read either way
# A MUFF is the swing play punting has and the sim did not model at all. Hands and
# focus prevent it; a hanging punt with coverage bearing down causes it.
PUNT_MUFF_BASE = 0.018
PUNT_MUFF_HANG_K = 0.020            # extra risk on a high, short punt
PUNT_MUFF_ATTR_K = 0.022            # hands/focus swing
PUNT_MUFF_RECOVER_KICKING = 0.50    # who comes up with a muffed ball

# ---- Passing: pressure and depth ----
# Sack rate was ~0.33 per team per game against a real-world ~2.4. Two
# multiplicative suppressors: the base rate at an even matchup was half of
# reality, and 45% of would-be sacks were dumped to the RB before a sack could
# register. A pass rush that never gets home also inflates completion % and
# attempts, so this distorts the whole passing picture, not just the sack column.
# NOTE this is a CURVE parameter, not the realized rate. Protection systematically
# outweighs the rush here (qbProtection = mobility + blocking*4), so the typical
# rushDifferential is negative and the logistic lands well below this number. 14.0
# yields ~6.0% of dropbacks, i.e. a real-world 2.48 sacks per team per game.
SACK_BASE_RATE = float(_os.environ.get('FLOOS_SACK_BASE', '14.0'))  # curve param, not the rate
# ⚠️ THE CAP AND THE STEEPNESS ARE WHAT SET THE SPREAD, and both were wrong while the
# base rate above was right. Reported as an explosion of sacks (19 by one team in a
# Floos Bowl) — but measured over 1,511 logged games the league AVERAGE was already on
# target at 2.85/team/game, 6.1% per dropback. The TAIL was the fault: p99 game rate
# 16.3%, top games 19%. At cap 30 with steepness 0.15 a 90 pass rush against a
# 70-mobility QB sat at 22.9% per dropback FOR THE WHOLE GAME (24.9% on a long
# dropback), so a 20-point attribute gap was worth a 4x sack rate against real
# football's ~2x, and ~42 dropbacks made the high teens an ordinary outcome rather
# than a freak one. Retuned by modelling the curve over the REAL 32-team roster (every
# team's derived pass rush against every other team's QB mobility and blocking) across
# the REAL 24-play pass playbook, so the blocker mix and the dropback depths are the
# ones the sim actually calls: expected team-game sacks p99 **10.6 -> 7.6**, max
# 11.3 -> 7.7, with the mean HELD at 3.47 -> 3.43 and the base rate UNCHANGED — nothing
# was ever wrong with it, and the league average was the one number already on target.
# ⚠️ THE PASS RUSH MUST STILL MATTER, so tune against the SPREAD, never the mean. The
# p90/p10 team-game ratio lands at 10.1x, halved from 19.4x and a long way from flat.
# Pushing the cap lower forces the base rate up to hold the mean, which parks most
# plays AT the ceiling and flattens the curve into "pass rush quality is irrelevant" —
# measured at cap 10 the spread collapses while the mean still reads fine.
# ⚠️ Do NOT tune this against a synthetic harness of uniformly-seeded teams. One was
# tried first and its matchup spread does not resemble a real league's (differentials
# spanning -72..+65 against the real -41..+31), so it reproduced neither the real mean
# nor the real tail and ranked candidates differently. Read real rosters out of a
# database — `player_attributes` plus the derivations in `floosball_player` is enough,
# no app boot required.
SACK_PROB_CAP = float(_os.environ.get('FLOOS_SACK_CAP', '16'))      # ceiling on a normal dropback
# Logistic steepness over the raw rush-vs-protection differential. Was hardcoded in
# `Game.calculateSackProbability`, which is why it was never a tuning candidate.
SACK_CURVE_STEEPNESS = float(_os.environ.get('FLOOS_SACK_STEEPNESS', '0.12'))
# Air-yard means per pass tier. The old bands were compressed -- "medium" at 6.5
# air yards is really a short throw -- which held league aDOT at 6.29 against a
# real-world ~7.8 and made every completion tiny.
PASS_DEPTH_MEANS = {
    'short': float(_os.environ.get('FLOOS_DEPTH_SHORT', '3.35')),
    'medium': float(_os.environ.get('FLOOS_DEPTH_MEDIUM', '8.25')),
    'long': float(_os.environ.get('FLOOS_DEPTH_LONG', '17.0')),
    'deep': float(_os.environ.get('FLOOS_DEPTH_DEEP', '27.0')),
}

# YAC shape. The sim is dink-and-dunk: it throws MORE than real football and
# completes MORE, but each completion is tiny (Y/C 8.3 vs ~11.2, YAC 33% vs ~50%).
# Two suppressors -- a receiver slips the first tackler only ~25-35% of the time
# (YAC_GATE_A_BASE / _CAP), and YAC_THROW_MULT then cuts everything again by 0.75
# for an average 66.6 throw. Fixing this ALONE would overshoot yards and scoring,
# so it is paired with fewer attempts (see FIRST_DOWN_RUN_WEIGHT) to keep total
# yardage flat: the same yards from fewer, longer completions.
# Per-tier YAC ceilings. These were nearly FLAT across tiers -- a short pass had
# almost the same explosive ceiling as a deep one (housecall mean 12 vs 14) -- so
# most big pass plays were short throws with a long run after, and a called "long"
# play could travel 10 yards through the air and still be the shorter gain. Big
# plays should come from genuine downfield throws. Tightening the short tiers and
# lengthening the deep air bands REDISTRIBUTES yardage rather than adding it.
YAC_TIER_CAPS = {
    'short':  {'pass': int(_os.environ.get('FLOOS_YACC_S_P', '4')),
               'bFail': int(_os.environ.get('FLOOS_YACC_S_B', '5')),
               'house': int(_os.environ.get('FLOOS_YACC_S_H', '7'))},
    'medium': {'pass': int(_os.environ.get('FLOOS_YACC_M_P', '6')),
               'bFail': int(_os.environ.get('FLOOS_YACC_M_B', '8')),
               'house': int(_os.environ.get('FLOOS_YACC_M_H', '10'))},
    'long':   {'pass': 6, 'bFail': 12, 'house': 14},
    'deep':   {'pass': 6, 'bFail': 15, 'house': 14},
}
YAC_GATE_A_BASE = float(_os.environ.get('FLOOS_YAC_BASE', '22'))
YAC_GATE_A_CAP = float(_os.environ.get('FLOOS_YAC_CAP', '45'))
YAC_GATE_A_FAIL_CAP = int(_os.environ.get('FLOOS_YAC_FAILCAP', '3'))
# throwQuality -> YAC multiplier. Average league throw quality is ~66.6, so the
# 60-79 band is the one that matters most for league-wide YAC.
YAC_THROW_MULT = {
    'elite': float(_os.environ.get('FLOOS_YACM_ELITE', '1.0')),   # >= 80
    'good': float(_os.environ.get('FLOOS_YACM_GOOD', '0.75')),    # 60-79
    'poor': float(_os.environ.get('FLOOS_YACM_POOR', '0.45')),    # 40-59
    'bad': float(_os.environ.get('FLOOS_YACM_BAD', '0.20')),      # < 40
}
# 1st-down run weight -- the single biggest lever on the league pass/run split
# (most plays happen on 1st down). 50 = the balanced base; raising it cuts pass
# attempts, which is what makes room for longer completions without inflating
# total yardage.
FIRST_DOWN_RUN_WEIGHT = float(_os.environ.get('FLOOS_FD_RUN', '50'))

# ---- Run Gate Model (three stages with carrier momentum) ----
# A carry is three contests: the line, the second level, the open field. What
# makes them mean something is that the runner's STATE carries between them --
# how you cleared one gate sets your odds at the next.
#   clean     : untouched, at full speed  -> edge to the runner
#   contacted : broke a tackle, slowed    -> roughly even, slight edge defender
#   fought    : forced through a plugged gap -> at a disadvantage
# At each contact the runner either powers through or elects a move; flair
# (creativity + xFactor) decides whether he tries something, the move's own
# physical attribute decides whether it works. See Game._resolveRunGates.
RUN_GATE_MODEL_V2 = _os.environ.get('FLOOS_RUN_GATES') != 'off'
RUN_GAP_OPEN = 74          # gap quality at/above this: clean release, no tackle attempt
RUN_GAP_PLUGGED = 38       # below this the gap is closed and the defender has the edge
# Winning the contact AT THE LINE is common -- it is "did I get past the front",
# not "did I break a tackle". Breaking one DOWNFIELD is genuinely rare, so it gets
# its own much lower base; without that split every run promoted to the open field
# and league ypc ran to 9.6.
RUN_CONTACT_BASE = 46      # line, partially open gap: roughly even, slight runner edge
RUN_CONTACT_PLUGGED = 16   # line, closed gap: only a genuinely elite back busts through
RUN_BREAK_BASE = 18       # second level / open field: an actual broken tackle
RUN_BLITZ_EDGE = 14        # blitzing LB is out of the run fit: easier clean second level
RUN_CONTACT_SWING = 0.30   # rating points -> percentage points in a contact contest
RUN_MOVE_ELECT_BASE = 0.18 # baseline chance of trying a move instead of lowering a shoulder
RUN_MOVE_ELECT_FLAIR = 0.55  # ...scaled by flair, so flashy backs try things plodders don't
RUN_MOVE_BONUS = 5         # a move that lands beats the tackler by this much
# Entry-state modifier on the gate-2 / gate-3 roll. The negatives are deliberately
# steep: breaking a tackle should keep a run ALIVE, not routinely convert it into a
# housecall. Without that, every broken tackle cascaded to the open field.
RUN_STATE_EDGE = {
    'clean': 9,            # full speed, hard to square up
    'contacted': -6,       # broke one but lost his legs
    'fought': -10,         # squeezed through a pile, no momentum at all
}
RUN_MAX_BREAKS = 2         # tackles a carrier may break on one carry
RUN_SECOND_BREAK_PENALTY = 18  # ...and the second is this much harder

# ---- Advanced Metrics ----
# Thresholds for the derived per-play metrics. These describe how a play is
# CLASSIFIED for the box score; they do not feed resolution.
BAD_THROW_THRESHOLD = 45        # throwQuality below this counts as a bad throw
# throwQuality at or above this counts as a GOOD throw — a genuinely well-placed ball,
# the stat the throw-quality card family keys off. The bad-throw bar cannot serve: only
# 4.1% of throws fall under 45, so "not bad" is 96% of throws and triggers nothing.
# Calibrated to land near a third of throws (~12-14 a game) so it has card-trigger volume
# comparable to receptions. Measured over 1,502 QB games on a fresh sim: at 78 the rate was
# 29.3% (11.1/game, slightly tight); at 76 it is 35.0% (13.4/game, p90 28, max 50), which
# is the target band. Do not reuse BAD_THROW_THRESHOLD's mirror for this — only 3-4% of
# throws fall below 45, so "not bad" is ~96% of throws and triggers nothing.
GOOD_THROW_THRESHOLD = 76
CONTESTED_OPENNESS_THRESHOLD = 40  # receiver openness below this counts as contested
# A dropped pass is mostly on the receiver, but drop probability scales with how
# poorly the ball was placed (dropProb derives from un-secured contact, which is
# throw-driven), so the QB keeps a share of the negative swing.
WPA_DROP_RECEIVER_SHARE = 0.7

# ---- Leading-Team Ease-Off ----
# The sim modeled the trailing team giving up (_isGarbageTime) but never the
# LEADING team easing off, so a club building a blowout pressed at full intensity
# for four quarters and the trailing side often finished with nothing. Real teams
# rush three and keep everything in front once the result is settled — that soft
# coverage is why a blowout still usually has the loser scoring at least once.
# Applied to the leading team's effective run D, pass D and pass rush in the
# second half when they are up more than two scores (Game.leadEaseOffFactor).
# NOTE this is DEFENSE-only. The leading offense is affected separately, and only
# through play-CALLING (the Q3 drain + Q4 lead-protection floor in
# _applySituationalMods lean run and suppress deep/long) — its execution quality is
# untouched, i.e. a leading team still runs the ball just as well, it runs it more.
# WHO eases off is coach-scaled: 0.5*(1-aggressiveness) + 0.5*clockManagement maps
# to a 0.4x (killer, keeps his foot down) .. 1.6x (professional, calls off the dogs)
# multiplier on the ease-off, centered at 1.0 for a neutral coach so league-average
# behavior stays the measured one and the spread is character.
LEAD_EASE_OFF_ENABLED = _os.environ.get('FLOOS_LEAD_EASE') != 'off'
LEAD_EASE_OFF_MAX = float(_os.environ.get('FLOOS_LEAD_EASE_MAX', '0.15'))

# ---- Defensive Modifiers ----
# Whether the pre-game modifier chain reaches the DEFENSE. Team defense ratings
# are derived from PROFILE attributes at roster setup and never recomputed, and
# the per-defender lookups in runPlay/passPlay read `.attributes` as well — so
# without this, league compression, fatigue, funding morale, team disposition and
# form oscillation were all offense-only. A cold team still defended at full
# strength, and a stacked roster's defensive edge was never compressed at all.
# FLOOS_DEF_MODS=off reverts to the old offense-only behavior.
# MEASURED (8 leagues x 5 seasons/arm): switching this ON made parity WORSE, not
# better. Win spread barely moved (22.3 -> 21.9) but the playoffs got far more
# deterministic — champions with the league's best record went 28% -> 45%, and the
# Cinderella rate (champion from outside the top 8 by record) collapsed 12% -> 5%.
# Compression does shrink defensive talent gaps, but the same change also hands the
# confidence / disposition / funding-morale boosts to defenders, and those all
# correlate with already being good, which more than cancels it. So this ships OFF:
# the offense-only behavior is now a documented deliberate choice rather than an
# accident. FLOOS_DEF_MODS=on to re-enable (and re-measure before trusting it).
DEFENSE_MODIFIERS_ENABLED = _os.environ.get('FLOOS_DEF_MODS') != 'off'
# 'momentum'  — a run feeds itself and a slump deepens, bounded by FORM_DECAY.
#               The only shape measured to actually sustain a season arc.
# 'reverting' — the originally specced negative feedback. Stable, and measured to
#               CANCEL arcs: it exists to erase sustained deviation, which is
#               exactly what an arc is. Kept for A/B, not recommended.
FORM_FEEDBACK = _os.environ.get('FLOOS_FORM_FEEDBACK', 'momentum')
# Unconditional weekly decay on the offset. This is what bounds momentum — a club
# cannot stay lifted without continuing to over-perform, so positive feedback
# cannot run away. Measured: win-sd is unchanged vs the reverting design.
FORM_DECAY = float(_os.environ.get('FLOOS_FORM_DECAY', '0.80'))
# Whether form carries into the playoffs. The offset stops UPDATING at the end of
# the regular season either way, so ON means a club takes whatever arc it ended on
# into the bracket — peaking at the right time is the canonical Cinderella story,
# and the alternative is that a late surge evaporates exactly when it matters.
FORM_PLAYOFFS_ENABLED = _os.environ.get('FLOOS_FORM_PLAYOFFS') != 'off'
# How much of the offset carries into the bracket. Full weight measured out at 40%
# of champions coming from outside the top 8 by record (and the best record winning
# only 8% of the time), which reads as the regular season not mattering; zero
# weight goes the other way at 8% / 35%. This scales between those two endpoints.
FORM_PLAYOFF_SCALE = float(_os.environ.get('FLOOS_FORM_PLAYOFF_SCALE', '0.5'))
# Asymmetry on the DOWN side only. Measured: the form layer causes essentially the
# whole shutout increase (7.0% -> 10.2% of team-games) while leaving mean scoring
# untouched (30.4 -> 30.2) — it is pure tail-widening, and the bottom tail is a
# slumping club getting blanked. Damping the negative half keeps the arcs (which
# are driven by the swing, not by the depth of the trough) while pulling the bad
# tail back in. 1.0 = symmetric.
FORM_DOWNSIDE_SCALE = float(_os.environ.get('FLOOS_FORM_DOWNSIDE', '0.6'))
FORM_WINDOW = 4        # games in the "recent form" window
FORM_PULL = float(_os.environ.get('FLOOS_FORM_PULL', '0.50'))   # how hard a deviation from your own baseline pulls back
# How fast formOffset chases its target each week (0-1). Doubles as the layer's
# MEMORY: a high value makes the offset flicker week to week and average out
# inside a game day, contributing nothing at the block scale form is measured on.
# Keep it slow enough that a hot spell lasts a few weeks.
FORM_REVERSION = float(_os.environ.get('FLOOS_FORM_REVERSION', '0.45'))
FORM_NOISE = float(_os.environ.get('FLOOS_FORM_NOISE', '0.050'))  # weekly gaussian wobble — the un-earned part of a slump
FORM_MAX = float(_os.environ.get('FLOOS_FORM_MAX', '0.14'))     # clamp on the multiplier; ±10% ≈ ±7-8 rating points

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
# ⚠️ FLOOR UNDER THE SHARE UNIT. A share is a team's cut of LAST season's Floobit
# faucet, so a league with no last season priced everything at zero: season 1 showed
# 0F upkeep and 0F to build anything, and every facility could be maxed for nothing.
# The old code called that "inert", which it is not — free is not the same as disabled.
#
# 300 is chosen against real numbers rather than invented: production's season 1 was
# already yielding ~359 per share PART-WAY through, so this sits just under a genuine
# season and reads as a modest one rather than a fake one. It gives a level-1 upgrade
# 15F, a max-level build 255F, and a max-level hold 120F a season — small enough that a
# new league can get moving, big enough that building means spending.
FACILITY_SHARE_UNIT_FLOOR = 300.0

# ⚠️ CLIP EACH USER'S CONTRIBUTION BEFORE AVERAGING THE FAUCET. A share unit is a mean,
# and a mean is exactly what one outlier breaks. Measured on the season-1 production
# database: one user earned 79,237F of a 212,614F faucet (37% of the league's season),
# 89% of it from a SINGLE week -- 1,453,601 FP in week 27, a Criticality week where Pyre's
# Equation and Amplify stacked. That one week raised every facility price for all 32 teams
# by 50% (a full L5 build 7,195F -> 10,764F) while giving the other 31 teams nothing to
# spend. Capping at the 95th percentile takes one user's influence on the unit from
# +59.4% to +10.2% and still SUMS everyone's real contribution, so the unit keeps tracking
# genuine league-wide growth -- unlike a median, which throws away the whole upper half.
FACILITY_SHARE_CAP_PERCENTILE = 95.0
# Below this many earning users a percentile is computed from too few points to mean
# anything, and clipping would just lower the unit rather than de-skew it.
FACILITY_SHARE_CAP_MIN_USERS = 8
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
# EACH position to fill every roster slot (numTeams × {QB1,RB1,WR2,TE1,K1}; 32 clubs today),
# else a position run (many retirements at one spot + a thin rookie class) could
# leave slots permanently empty. The supply check (playerManager.ensurePositionSupply)
# tops up only the per-position deficit into the FA pool — a no-op in the normal
# case where the pool is already deep. This buffer is the small cushion kept
# ABOVE exact slot demand so the FA draft has some choice and late FA retirements
# don't re-open a gap. Only matters when a position is genuinely short.
ROSTER_SUPPLY_BUFFER_PER_POSITION = 3

# ---- League realignment: REMOVED (owner, 2026-08-23) ----
# `realignByRecentPerformance` serpentine-split the two leagues by recent win% so
# neither stayed perpetually stronger. It predates divisions, and once league AND
# division membership are curated in config.json it works against them: it moves
# clubs between leagues, which invalidates `divisionDistribution` and forces
# `_assignDivisions` to fall back. Measured on a fresh league it moved 16 teams at
# season 2 and re-formed every division. Function, caller and window constant are
# gone. ⚠️ `_applyPersistedAlignment` and the `league_alignment` app_setting STAY —
# a database where the realignment already ran keeps the leagues it has, because
# reverting them would move half the league. `league_realigned` is now vestigial.

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
# Env overrides so the retention levers can be A/B'd without editing this file.
# FLOOS_RETENTION=off disables both. Default (unset) = the shipped behavior.
_RETENTION_OFF = _os.environ.get('FLOOS_RETENTION') == 'off'
# ⚠️ RE-SIGN-ONCE IS OFF (owner, 2026-08-13). At limit 1 a player was forced to
# walk after a single re-sign, capping any career at roughly two contracts with
# one club — so a career-long one-club player was IMPOSSIBLE, which cuts against
# "players are characters" (design pillar 2). It was built as a dynasty-breaker,
# but the parity package's other levers (star scarcity, the per-offseason re-sign
# cap, compression) already do that work.
# The machinery is intact — `playerManager.hasReachedResignLimit` still reads
# both of these and `players.team_resign_count` is still tracked and persisted —
# so re-enabling is flipping this one flag, not a rebuild.
RESIGN_ONCE_ENABLED = False
RESIGN_ONCE_LIMIT = 1             # re-signs allowed with the SAME team before a forced walk
                                  # (only consulted while RESIGN_ONCE_ENABLED)
RESIGN_LIMIT_ENABLED = not _RETENTION_OFF
RESIGN_LIMIT_PER_OFFSEASON = 2    # max players a team may re-sign per offseason

# ---- Fan sentiment (AFO plan Part D) ----
# Fans rate players 1-5. This is the quiet, PERSISTENT signal the GM brain
# reads — the valence axis, distinct from anomaly attention (magnitude).
# Free to cast, net one per fan per player.
SENTIMENT_ENABLED = True
SENTIMENT_RATING_MIN = 1
SENTIMENT_RATING_MAX = 5
SENTIMENT_NEUTRAL = 3.0           # midpoint; maps to 0.0 sentiment

# How many distinct raters a subject needs before their sentiment counts at all.
# Below it the subject reads neutral and the average is withheld, so one voice
# can't move a roster decision or manufacture a public number.
#
# ⚠️ SCALES WITH THAT CLUB'S OWN FANBASE, not with the league (owner,
# 2026-08-13). Only a club's own fans may rate its players (`_requireOwnClub`),
# so a league-wide bar is a bar some clubs CANNOT CLEAR: measured on production,
# 163 favoriters spread over 32 clubs left 5 teams with no fans at all and
# several with one or two, against a flat floor of 3 — those rosters could never
# register sentiment no matter how their fans felt.
#     required = max(SENTIMENT_MIN_RATERS, ceil(teamFans x FAN_FRACTION))
# Because the fraction is below 1, the bar is ALWAYS reachable by a club's own
# fanbase, which is the property the old formula lacked. A one-fan club needs
# that one fan; a 14-fan club needs 5, so a single voice never speaks for a
# crowd. At 0.34: 1 -> 1, 3 -> 2, 6 -> 2, 9 -> 4, 14 -> 5.
#
# ⚠️ Keyed on FAVORITERS, not "active" ones. `_countActiveUsers` reads
# `users.last_login_at`, which NOTHING IN THE APP EVER WRITES (only tests), so
# it returns 0 in production and every quorum scaling off it silently pins to
# its floor. Tighten this to active fans only once that column is populated.
SENTIMENT_MIN_RATERS = 1
SENTIMENT_QUORUM_FAN_FRACTION = 0.34
# Retained for the awards quorum, which IS a single league-wide vote and so is
# correctly scaled against the league rather than one club.
SENTIMENT_QUORUM_ACTIVE_FRACTION = 0.05

# How far sentiment can move a valuation, in perceivedValue points, at FULL
# fan trust and maximum love/hate. Deliberately small: the plan says sentiment
# TIPS CLOSE CALLS and must never force a clearly-bad move. A 5-star darling on
# a maximally populist GM is worth this much extra; a hated player this much less.
SENTIMENT_MAX_VALUE_SWING = 5.0

# Boards: how many to surface per leaderboard.
SENTIMENT_BOARD_SIZE = 10

# ---- Social feed: fan posts (AFO plan Part D, signal 2) ----
# The team page becomes a feed of PRE-MADE reactions. Pre-made is the whole
# point: no free text means no moderation problem, and it keeps the register
# consistent. Posts are the EMOTIONAL PULSE — fast, decaying, spammy-fun —
# as opposed to the 1-5 ratings, which are the slow standing stance.
FEED_ENABLED = True

# Rate limit: posts should feel cheap and loud, but bounded.
#
# ⚠️ Two limiters, and the COOLDOWN is the one that normally bites (owner, 2026-08-09).
# A flat 10-an-hour cap was the wrong shape for a live game: a fan watching a whole
# match is exactly the fan who wants to shout at it, and they ran out partway through
# and then sat silent through the finish. What the cap was really protecting against is
# a burst — twenty posts in ten seconds — which a few seconds between posts stops just
# as well while leaving someone who reacts to every drive completely unblocked.
#
# The hourly cap stays as a runaway backstop, raised to a level a real fan will not
# reach in one sitting. At a 10s cooldown the theoretical hour is 360 posts, so 90 is
# still a genuine ceiling without being the thing anyone runs into.
FEED_MAX_POSTS_PER_WINDOW = 90
FEED_RATE_WINDOW_HOURS = 1
FEED_POST_COOLDOWN_SECONDS = 10

# How long a post stays in the feed / counts toward the pulse. Ephemeral by
# design — the pulse is "how the fanbase feels RIGHT NOW", not a permanent record.
FEED_POST_TTL_HOURS = 72

# Pulse saturation: how many net decayed posts it takes to reach full intensity.
# Above this the pulse saturates rather than growing without bound, so a
# brigade of one target can't dominate the whole model.
FEED_PULSE_SATURATION = 12.0

# How much the (fast, noisy) post pulse can move a player's sentiment relative
# to their (slow, deliberate) star rating. Ratings lead; posts nudge.
FEED_PULSE_SENTIMENT_WEIGHT = 0.35

# Post catalog. Each entry: key -> (text, target, valence).
#   target : 'player' | 'gm' | 'team'
#   valence: +1 supportive, -1 angry, 0 neutral hype
#
# TWO kinds of entry, split by how they reach the feed:
#   - target 'team'  -> what a fan can POST manually. General support and
#     frustration only. Opinions about a specific player or the GM are not
#     posted directly; they come from rating that player / voting on that GM.
#   - target 'player' | 'gm' -> the AUTO-POST vocabulary. When you rate a player
#     or vote on the GM, one of these is generated on your behalf so your
#     opinion shows up in the feed. Never manually selectable.
#
# Naming: durable idiom, nothing that will read as dated. `{name}` is filled
# with the target's name at render time.
FEED_POST_CATALOG = {
    # -- manually postable: general support
    'our_season':    ('This is our season',           'team',    1),
    'believe':       ('Believe!',                     'team',    1),
    'all_the_way':   ('We\'re going all the way!',    'team',    1),
    'floosbowl':     ('The Floosbowl is ours',        'team',    1),
    # -- manually postable: general frustration
    'not_good':      ('Not good enough',              'team',   -1),
    'same_old':      ('Same story every season',      'team',   -1),
    'disappointing': ('Disappointing!',               'team',  -1),
    'terrible':      ('Absolutely terrible',          'team',   -1),

        # Vocabulary is limited to moves that EXIST in Floosball: cut, re-sign,
    # sign a free agent, fire the GM. Nothing may imply a trade — there are
    # none — so "Trade them" and "Untouchable" (i.e. trade-protected) are out.
    # -- AUTO from a 4-5 star rating
    'cornerstone':   ('Franchise cornerstone',        'player',  1),
    'indispensable': ('Indispensable',                'player',  1),
    'favorite':      ('Fan favorite',                 'player',  1),
    'carried_us':    ('Carried this team all season', 'player',  1),
    # -- AUTO from a 1-2 star rating
    'cut_them':      ('Cut them',                     'player', -1),
    'liability':     ('A liability out there',        'player', -1),
    'move_on':       ('Time to move on',              'player', -1),
    'get_out':       ("Get them out of here",         'player', -1),
    # -- AUTO from a GM like
    'in_trust':      ('In {name} we trust',           'gm',      1),
    'plan':          ('Trust the plan',               'gm',      1),
    'best_hire':     ('Best GM in the league',        'gm',      1),
    # -- AUTO from a GM dislike
    'fire_the_gm':   ('Fire the GM',                  'gm',     -1),
    'lost_the_room': ('{name} has lost the room',     'gm',     -1),
    'enough':        ('Enough excuses',               'gm',     -1),
}

# ---- The Bleachers: what a fan can shout AT A GAME ----
#
# Separate from FEED_POST_CATALOG on purpose. Those lines are about a CLUB over a
# season ("This is our season", "Same story every season") and read as nonsense
# shouted at a single snap. These are about a night: the run of play, the call
# that just happened, the scoreboard.
#
# Same contract as the club catalog — key -> (text, group, valence) — so text is
# never user-supplied and there is no moderation surface. Group is the heading
# the composer files it under.
#
# Naming follows the house rule: durable idiom, nothing that will read as dated.
# No slang, no chants that belong to a real club.
GAME_FEED_CATALOG = {
    # -- willing them on
    'thats_the_play': ("What a play!",                 'Positive',   1),
    'about_time':     ('About time!',                  'Positive',   1),
    'yes':            ('Yes!',                         'Positive',   1),
    'lets_go':        ("Let's go!",                    'Positive',   1),
    'believe':        ("Believe!",                    'Positive',   1),
    # -- displeasure
    'wake_up':        ('Wake up',                      'Negative',   -1),
    'welp':           ('Welp',                         'Negative',   -1),
    'bums':           ('Dangit!',                      'Negative',   -1),
    'not_like_this':  ('Not like this',                'Negative',   -1),
    'so_close':       ('So close!',                    'Negative',   -1),
    'we_must_be_cursed': ('We must be cursed',         'Negative',   -1),
    # -- the defense
    'get_a_stop':     ('Make a stop',                  'Defense',     1),
    'hold_them':      ('Hold them here',               'Defense',     1),
    'defense':        ('DEFENSE',                      'Defense',     1),
    'not_another_yard': ('Not another yard',           'Defense',     1),
}

# Which star ratings generate a post, and of which flavour. A 3 says nothing —
# a shrug isn't worth a post, and the feed stays signal.
FEED_AUTOPOST_BY_RATING = {5: 1, 4: 1, 3: None, 2: -1, 1: -1}

# GMs use the same fanbase-scaled quorum as players — one rating model, one
# floor. A GM is rated by the club's fans, so the same "a small club must still
# be able to speak" argument applies verbatim; see SENTIMENT_MIN_RATERS.
# (Kept as its own name so a GM-specific floor stays possible later.)
# ⚠️ A RATING GOES STALE. A fan casts one standing opinion per subject and can change it
# whenever they like, but nothing ever expired it — a 1-star cast in season 1 counted at
# full weight in season 5, against a GM who had since won two titles. Each season of age
# shrinks a rating's pull TOWARD NEUTRAL; re-rating restores it to full.
#
# ⚠️ IT SHRINKS THE DEVIATION, NOT THE WEIGHT IN AN AVERAGE. A weighted mean over voters
# who are all equally stale is identical to the plain mean — the weights cancel and decay
# does nothing. So each vote's normalized sentiment is scaled individually and the mean is
# taken over the RATER COUNT, which is what actually pulls an aged verdict back to 0.
SENTIMENT_DECAY_PER_SEASON = 0.6
# Never all the way to nothing: a fan who felt strongly and never came back still counts
# for something, and a hard 0 would make old clubs read as unanimously indifferent.
SENTIMENT_DECAY_FLOOR = 0.15

GM_SENTIMENT_MIN_VOTERS = 1

# ---- GM turnover: fired / retire / leave (AFO plan Part C) ----
# All three exits are sim decisions, each rolling the replacement gamble. Since
# coaches are specialists, a replacement is better-or-worse PER DIMENSION, so
# turnover is a real trade rather than a reroll on a quality number.
# Target: a few GM changes league-wide per season, NOT a carousel.
GM_TURNOVER_ENABLED = True

# Fire pressure comes only from falling BELOW this win rate — at or above it a
# GM is never rolled on, so competence is genuine job security.
GM_FIRE_BASELINE_WINPCT = 0.45
GM_FIRE_SENSITIVITY = 2.60    # fire chance per point of win-rate deficit.
                              # Tuned over 2.5k simulated seasons against a
                              # realistic 24-team record spread: yields ~2.9
                              # fire+leave exits/season, landing 3-4 once
                              # retirements are added (target 3-5).
GM_FIRE_GRACE_SEASONS = 1     # a GM isn't fired on their first season's record —
                              # they inherited the roster and haven't had an
                              # offseason to shape it
GM_FIRE_GOODWILL_MAX = 0.14   # max fire-chance reduction for a beloved leader.
                              # Kept BELOW a typical fire chance on purpose: at
                              # 0.18 goodwill could zero out the roll entirely,
                              # making a well-liked GM unfireable rather than
                              # merely harder to fire.
                              # (coach `attitude` 100). This is the plan's
                              # "threshold varies by GM", sourced from a visible
                              # attribute rather than a hidden per-coach roll.
GM_FIRE_MAX_CHANCE = 0.75     # even a catastrophe isn't a certainty

# Voluntary departure — independent of record, so a hostile fanbase can drive out
# a GM who is WINNING. Sentiment weights are dormant until plan Part D.
# ⚠️ TENURE PRESSURE — one bad season is not the only way to lose a job, and until this
# existed it was the ONLY way. `fireChance`'s deficit term reads the LATEST season alone,
# so a GM parked just above the 0.45 baseline generated exactly 0.0% risk forever: a club
# going 13-15 every year had an 86% chance of keeping the same GM across five seasons, and
# a reliably-slightly-below-average GM was the most secure in the league.
#
# These accumulate over a GM's tenure AT THIS CLUB and are added to the single-season
# deficit, then the whole thing is capped by GM_FIRE_MAX_CHANCE as before.
#
# ⚠️ A PLAYOFF WIN RESETS THE STALL CLOCK, nothing else does. That is what separates the
# two failure modes the owner named: missing the postseason entirely is worse per season
# than reaching it and going out immediately, but neither counts as getting anywhere.
GM_FIRE_STALL_GRACE = 2        # seasons without a playoff win before pressure starts
GM_FIRE_DROUGHT_STEP = 0.07    # per season MISSING the playoffs, past the grace
GM_FIRE_STAGNATION_STEP = 0.04 # per season reaching them and not winning a round
# Treading water on RECORD, a separate axis from the postseason. The band is deliberately
# centred on .500 and stops below the fire baseline (0.45), so a season bad enough to
# trigger the deficit term is not also counted here.
# ⚠️ The upper bound is a WINNING season's floor, not a nice round number. At 0.575 a
# 16-12 club sat inside the band, so a GM winning playoff rounds every year still accrued
# "treading water" pressure — caught by test_gm_tenure. 0.54 is 15-13 over 28 games: the
# top of the plateau, below which nobody would call the season a success.
GM_FIRE_MEDIOCRITY_BAND = (0.45, 0.54)
GM_FIRE_MEDIOCRITY_GRACE = 3   # three .500-ish seasons is a plateau, not yet a verdict
GM_FIRE_MEDIOCRITY_STEP = 0.03
# ⚠️ Ceiling on the whole tenure contribution. Accumulated mediocrity must never rival a
# catastrophic season -- 4-24 is a firing offence on its own, and a long grey tenure is a
# reason to be at risk, not a certainty.
GM_FIRE_TENURE_MAX = 0.30

GM_LEAVE_BASE_CHANCE = 0.03
GM_LEAVE_SENTIMENT_WEIGHT = 0.35
GM_FIRE_SENTIMENT_WEIGHT = 0.25

# ---- Unrostered (free-agent) self-development ----
# Development is coach-driven: devBias = round((coachDevRating - 60) / 10).
# Free agents used to fall to a default coachDevRating of 50, i.e. devBias -1 —
# WORSE than the worst possible coach (60 -> 0), so an unsigned player actively
# DECAYED. That was a latent oddity while most players were rostered; it becomes
# a real problem under AFO Part F, where every new player enters the FA pool and
# would take the penalty until signed.
#
# Unrostered players now train off their OWN mental makeup instead — the player
# who keeps themselves sharp without a staff. Never negative: sitting in the pool is
# stagnation at worst, never punishment.
FA_SELF_DEV_ATTRS = ('discipline', 'focus', 'resilience', 'selfBelief')
FA_SELF_DEV_SCALE = 0.7       # damping vs a coached player — self-training is
                              # real but less effective than actual coaching.
                              # League mean self-drive ~74 => devBias ~+1, vs a
                              # neutral coach's +2 and the worst coach's 0.
FA_SELF_DEV_MIN = 0           # floor: unsigned never decays

# ---- Coach generation: specialists, not uniformly good/bad (AFO plan Part B) ----
# Coaches used to draw every attribute from normal(center, 10) around ONE
# per-coach center, so a coach was uniformly strong or weak and the aggregate
# actually meant something. GMs should instead be SPECIALISTS — great offensive
# mind / weak defense / sharp scout / poor developer — so each attribute is drawn
# largely independently, with only a SMALL shared component so a rare all-around
# elite or bust still exists.
#   attr = clip(center + shared + N(0, INDEP_SIGMA), 60, 100),  shared ~ N(0, SHARED_SIGMA)
# SHARED_SIGMA << INDEP_SIGMA is the whole point: most coaches land near-average
# overall while differing sharply attribute to attribute.
COACH_ATTR_CENTER = 80
COACH_ATTR_SHARED_SIGMA = 4.5     # all-around quality component (rare tails).
                                  # Tuned over 4k draws: gives ~3.7% all-around
                                  # elites / ~4.8% busts (target 3-5% each) while
                                  # leaving the within-coach attribute spread at
                                  # ~24 pts. Raising it past ~5.5 starts making
                                  # coaches uniformly good/bad again.
COACH_ATTR_INDEP_SIGMA = 9.0      # per-attribute spread (the specialist signal)

# Scouting-report profile thresholds. A coach only earns a specialty/flaw tag
# when the attribute is genuinely notable — otherwise they read as a generalist,
# which is honest rather than forcing a label onto a flat spread.
COACH_PROFILE_SPECIALTY_MIN = 88  # top attribute must clear this to be a specialty
COACH_PROFILE_FLAW_MAX = 70       # bottom attribute must fall below this to be a flaw
COACH_FANTRUST_POPULIST_MIN = 90  # listens to the fans to a fault
COACH_FANTRUST_INDEPENDENT_MAX = 70   # ignores them entirely

# ---- Player intake: rookie draft vs FA trickle (AFO plan Part F) ----
# When False, no rookie class is generated and the rookie draft has nothing to
# draft: new players enter ONLY via playerManager.ensurePositionSupply, which
# generates the per-position DEFICIT into the free-agent pool. That deficit fill
# is the whole intake model — it produces nothing while the pool is above target
# (so an inflated pool drains), then replaces retirees one-for-one once at
# target. ROSTER_SUPPLY_BUFFER_PER_POSITION sets the steady-state pool depth.
# OFF (plan Part F). No rookie class is generated and the draft has nothing to
# draft: new players enter ONLY as the position-supply deficit fill — a trickle
# into the FA pool that produces nothing while the pool is above target, so it
# cannot inflate. Existing prospects drain through and are not replaced.
ROOKIE_DRAFT_ENABLED = False

# ---- Autonomous Front Office (docs/AUTONOMOUS_FRONT_OFFICE_PLAN.md) ----
# The sim's GM brain makes roster decisions; fans express sentiment that tips
# close calls.
# ⚠️ REMOVED 2026-08-13 — this was `AUTONOMOUS_FO_ENABLED`, and its comment said
# it was "kept as a flag so a bad offseason can be rolled back to fan votes".
# THAT ROLLBACK DID NOT EXIST. The binding-vote system was deleted and nothing
# has set `_gmResigned` since, so the fallback path kept nobody: measured on a
# played season, 22 expiring players and 0 re-signed — flipping the flag would
# have walked every walk-year player in the league in one offseason, in the name
# of safety. (CLAUDE.md separately called the flag "vestigial — read nowhere";
# it was read in two places and was live.) The brain is the only decider now.
# Deliberately not replaced with a working switch: there is nothing to switch TO.

# Positional value multiplier. Every fill/upgrade/re-sign decision ranks by
# perceivedValue = projectedRating x POSITION_VALUE, which is what stops
# "best available" handing a team a great kicker while the QB slot rots.
# Universal table for now; small per-GM biases are a later flavour option.
POSITION_VALUE = {
    'QB': 1.00,
    'RB': 0.72,
    'WR': 0.78,
    'TE': 0.60,
    'K':  0.35,
}

# Scouting -> career-arc vision. A GM's read of a player is a blend of the
# CURRENT rating and the true FORWARD projection, mixed by how good a scout
# they are: at FO_SCOUT_VISION_FLOOR scouting they see only today's number, at
# FO_SCOUT_VISION_CEILING they see the arc almost perfectly. What's left of the
# gap becomes random error, so a poor scout is genuinely WRONG (buys the fading
# vet, passes on the ascender), not merely noisy.
FO_SCOUT_VISION_FLOOR = 60        # scouting at/below this = current-number-only
FO_SCOUT_VISION_CEILING = 100     # scouting at this = near-perfect arc vision
# Rating points of error at zero vision (1 sigma). Raised from 6.0 once boards
# became per-team: at 6.0 the error was so small next to the gaps between free
# agents that all 21 clubs named the SAME top target, which defeats the point of
# each GM having their own board. Measured over the live pool, by noise level —
# "own #1" is where a club's top target sits on the true-rating board:
#
#     noise   distinct #1s   avg own #1   top-3 shared with consensus
#       6.0            16        1.48                        2.25/3
#       9.0            24        1.93                        2.02/3
#      12.0            29        2.50                        1.86/3
#      16.0            35        3.02                        1.74/3
#
# 12.0 puts a club's own top target around the consensus #2-3, so one team's
# man really is another's fifth choice, without making the whole league blind.
FO_SCOUT_NOISE_MAX = 12.0

# The Scouting Department facility adds to the GM's EFFECTIVE scouting, in the
# same attribute points the coach attribute uses. This is what finally consumes
# FACILITY_CATALOG['scouting']['effect'] = 'scouting_bonus' (levels 0/0/0/3/5/7):
# a maxed department is +7 points of vision on a 40-point span, so it buys a
# sharper read of the board without ever replacing the GM's own eye. Before
# this the facility had no reader anywhere in the codebase.
FO_SCOUT_FACILITY_ENABLED = True

# Correct the winner's curse when the GM prices "the best player I can get".
# Picking the highest of N noisy reads preferentially finds whoever this GM
# overrated, so the free agent market reads better than it is and reads better
# the DEEPER the pool. Measured with it OFF: an average scout saw a 20-man pool
# as +6.1 above its actual best player (a poor scout +16.2) and cut a clearly
# better incumbent 20% of the time (60% for the poor scout) — and across four
# simulated seasons the 66 resulting cuts landed a better player 52% of the time
# and a worse one 47%, moving roster quality +0.6 against the +6.0 every one of
# those decisions claimed. That is a coin flip dressed as judgement.
# ⚠️ This corrects the SCALAR compared against a threshold, never the per-player
# ordering — GMs reaching for different men is a design goal, not the bug.
# Off only for A/B; see frontOfficeBrain._deWinnersCurse.
FO_SCOUT_WINNERS_CURSE_CORRECTION = True

# ── Free agent destination preference ───────────────────────────────────────
# Players decide where they are willing to sign BEFORE the draft, so a team's
# board only ever holds players who would actually come, and a GM never plans a
# cut around an upgrade that was never available to them. `demand` is the
# minimum team Appeal (the weighted facility sum) a player will accept.
#
# AGE ONLY. Talent is deliberately NOT an input: if demand tracked rating, the
# best players would pool at the best-funded clubs and the league would stratify
# by treasury. Keyed on service time instead, a 95-rated second-year player will
# sign anywhere, and what a rich club buys is veterans, not talent.
#
# Measured against the live league when it held 24 teams: Appeal min 4, p25 4, median 11,
# p75 17, max 20. The curve is set against those numbers, not a 0-25 ideal.
#
#   rookie      demand 0            -> signs anywhere
#   4 seasons   demand ~2 to 6      -> nearly anywhere
#   8+ seasons  demand ~4 to 11     -> anywhere, or the top half, depending on
#                                      the player
#
# The jitter is scaled BY the veteran term, so young players have almost no
# spread (they all go anywhere) while veterans differ a lot from each other.
# That's what keeps preference wide rather than a hard tier gate.
FA_PREFERENCE_ENABLED = True
FA_PREF_MAX_DEMAND = 11.0         # Appeal a maximally-picky player demands
FA_PREF_VET_FULL_SEASONS = 8      # service seasons at which the veteran term maxes
FA_PREF_VET_WEIGHT = 0.75         # how much of the scale a full veteran uses
FA_PREF_JITTER = 0.35             # per-player swing, deterministic from player id

# Development-minded GMs credit part of a young player's CEILING (not just the
# trueSkill they'd reach on their own) because they back themselves to develop them.
FO_CEILING_CREDIT = 0.45          # fraction of the remaining (ceiling - current) gap a GM
                                  # expects to realise at max playerDevelopment; 0 at the floor

# Potential headroom required before a player reads as DEVELOPING rather than
# PRIME. Nearly every player carries a point or two of slack, so without a
# floor here 'developing' would describe the whole league.
FO_DEVELOPING_HEADROOM = 2

# Age decline. A player past their longevity clock is projected DOWN — this is
# the "sell high before the cliff" read that separates a sharp GM from a poor one.
FO_DECLINE_PER_YEAR_PAST = 0.06   # rating fraction shed per season past longevity
FO_DECLINE_MAX = 0.40             # cap so an ancient vet never projects to nothing

# Re-sign decision. A walk-year incumbent only takes one of the scarce re-sign
# slots if their perceived value beats the replacement the team can REALISTICALLY sign
# by this margin (in value points). Slots then go to the biggest surpluses
# first, so a team spends them where the incumbent genuinely wins.
FO_RESIGN_SURPLUS_MARGIN = 0.5

# Cut-for-upgrade. A GM cuts a player under contract only when the replacement
# it can REALISTICALLY sign beats them by this margin in value points. Bigger
# than the re-sign margin on purpose: letting a walk-year player leave is free,
# whereas cutting someone under contract opens a hole you may not fill.
#
# NOTE — the plan describes an upgrade threshold that scales with draft position
# as "the aggression dial". That dial is ALREADY expressed by FO_FA_CONTENTION
# below: an early picker is measured against the top of the board and a late
# picker against thin leftovers, which is the same early-aggressive /
# late-conservative behavior. Scaling the threshold by pick slot TOO would
# double-count it and, with a near-minimum pool, suppress cuts almost entirely.
# So the threshold is flat and the dial lives in one place.
FO_CUT_ENABLED = True
FO_CUT_UPGRADE_MARGIN = 6.0   # value points the replacement must beat the
                              # incumbent by. Raised from 4.0: at 4.0 a QB was
                              # cut for a 4-rating-point upgrade, which isn't
                              # worth the risk of a hole you may not refill.
# Soft per-team cap. The plan left cuts uncapped and expected churn to
# self-limit; a fresh-league sim produced 70 cuts in ONE offseason (half the
# league), because a brand-new FA pool is fat and every roster has an upgrade
# available. In an ongoing league cuts settle near zero, so this cap only ever
# binds on that transient — but 70 would read as absurd, so it is bounded.
# Mirrors the re-sign cap: a GM makes at most a couple of decisive moves a year.
FO_CUT_MAX_PER_TEAM = 2

# How sure a GM must be that it can come away with SOMEONE better before it cuts.
# ⚠️ THE CUT USED TO REST ON GETTING ONE PARTICULAR PLAYER, and measured, the club
# signed that exact man **8% of the time** — 92% went elsewhere, because deciding
# and acquiring are separate phases with a worst-first draft between them and
# `_leftThisTeamThisOffseason` blocks re-signing your own cut player, so there is
# no fallback. Cut results were consequently a coin flip (44% better / 46% worse)
# NO MATTER HOW HONEST THE VALUATION WAS: fixing the estimate cut volume 66 -> 50
# and moved the hit rate not at all.
# A club does not need the man it wants, it needs someone better than the man it
# has — so the gate is now P(at least one upgrade survives to my pick), from a
# Binomial over the clubs picking ahead. See frontOfficeBrain.upgradeConfidence.
# The behaviour falls out rather than being scripted: a club with a POOR starter
# can cut confidently (much of the pool beats him, so some of it survives a run
# on the position) while a club with a decent one cannot, because only the top of
# the board beats him and the top always goes.
FO_CUT_MIN_CONFIDENCE = 0.60

# How deep into the FA pool a team should look when judging its own incumbent.
# Benchmarking every team against the single league-best free agent is wrong:
# every club would conclude their starter is replaceable, yet only one can
# actually sign that player, so the whole league sheds its incumbents. Instead
# each team looks at the free agent it can expect to still be there at ITS slot
# in the worst-first FA order. Not every team ahead takes the same position, so
# only this fraction of them is assumed to.
#   effectiveDepth = floor(faOrderIndex x FO_FA_CONTENTION)
# This is also the plan's aggression dial in its natural home: a bad team
# picking early benchmarks against the best available and churns boldly, while
# a good team picking late sees thin leftovers and holds onto its own.
FO_FA_CONTENTION = 0.30

# Benefit of the doubt given to a prospect the team ALREADY owns when weighing
# promotion against signing a free agent. Promotion costs the team nothing and
# the prospect is under its own control, so a prospect within this fraction of
# the free agent it could otherwise land gets the roster spot. Below 1.0 or a
# prospect essentially never wins — a developing player's forward projection
# sits under a proven veteran's almost by definition, and the whole pipeline
# would wash out to free agency instead of ever reaching a roster.
FO_PROSPECT_PROMOTE_EDGE = 0.88

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
    # `requiresClock` withholds the candidate under formats whose game clock doesn't
    # actually run (innings / play_limit / chess_clock — see GameFormat.consumesRealTime).
    # A running-clock rule can't mean anything when nothing is driven by the clock.
    "clockStopsOnDeadBall":       {"label": "Clock stops on dead balls", "values": [False],
                                   "requiresClock": True},
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
                                "desc": "Throw at the sideline goals for a bonus point while driving down the field."},
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
# "No kick" mode (gameRules.conversionKickEnabled=False): every post-TD try is a forced
# go-for-it. When NOT in a Q4 comeback, a coach reaches for the highest-value rung whose
# make estimate clears a personal floor — aggressive coaches accept lower odds (reach
# higher up the ladder), conservative coaches stick to the safe 2-pt.
CONVERSION_FORCEGO_MAKE_FLOOR = 0.72     # a neutral coach's minimum make% to reach past the 2-pt
CONVERSION_FORCEGO_AGGR_SWING = 0.30     # +/- the floor across the coach-aggressiveness range
CONVERSION_FORCEGO_JITTER = 0.08         # per-attempt randomness on the floor (variety)

# ── Darts: take the dart, or bank the points? ────────────────────────────────
# In darts a rung that lands EXACTLY on the target wins outright, so at a need of 3, 4
# or 5 the ladder offers a try that ends the game — but the rung that lands is always
# the LONGEST one still legal, so winning now is always the least likely make. The
# alternative is to take a shorter non-busting rung, bank the points, and land the
# remainder on a later drive (a field goal covers 3, a hoop covers 1).
#
# ⚠️ NEITHER LINE IS STRICTLY BETTER, which is what makes this a coach call rather than
# a rule (owner, 2026-08-26: "an aggressive coach would go for the higher score to win,
# conservative will bank easy points"). Measured at the shipped rung distances, a need of
# 5 is a 0.34 shot at winning immediately against a 0.70 shot at reaching a need of 3 —
# and a failed try costs nothing either way, since the touchdown is already banked.
#
# Same shape as the CONVERSION_FORCEGO_* floor above: the landing rung is taken when its
# make estimate clears a floor that aggressiveness lowers.
DARTS_LAND_MAKE_FLOOR = 0.45   # a neutral coach's minimum make% to try to win it outright
DARTS_LAND_AGGR_SWING = 0.26   # +/- the floor across the coach-aggressiveness range
DARTS_LAND_JITTER     = 0.06   # per-attempt randomness on the floor (variety)
# Only defer to the coach when banking is MATERIALLY safer. Below this the landing rung
# is close enough in odds that declining a win is just leaving the game on the field.
DARTS_LAND_MIN_EDGE   = 0.06

# How boldly a TRAILING team reaches for a ladder rung (or the 2-pt) instead of the safe
# kick — the desire chart in _conversionDesire, now tuned aggressive so comebacks lean on
# the rungs. Each tier is the base go-for-it probability (before coach aggressiveness and
# the CONVERSION_GO_AGGRESSION master dial).
CONVERSION_DESIRE_TIE_OR_WIN = 0.92      # the try ties / takes the lead now; the kick leaves you behind
CONVERSION_DESIRE_SAVE_POSS  = 0.78      # the try saves a whole scoring possession vs kicking
CONVERSION_DESIRE_ONE_SCORE  = 0.50      # still a one-score game — real aggression (was a rare 0.25)
CONVERSION_DESIRE_LONGSHOT   = 0.20      # multi-score & doesn't save a possession — occasional reach (was 0)
CONVERSION_GO_AGGRESSION     = 1.3       # master multiplier on the whole chart — raise for even bolder teams
# Go-for-it is now considered in the whole SECOND HALF when trailing (was Q4 only); Q3 is
# dampened since it's earlier and a miss has more time to hurt.
CONVERSION_GO_Q3_DAMPEN      = 0.55

# ── Innings: conversion-gated continuation (docs/INNINGS_REDESIGN_PLAN.md) ──────
# In the innings format a TD whose TOP conversion (the max-value 'go' rung — the 2-pt
# when the ladder is off, the longest rung when it's on) is MADE keeps the at-bat alive
# WITHOUT consuming a try (baseball-style: scoring doesn't make an out). A kick, a lesser
# rung, or a miss all consume a try. Removes the old hard comeback ceiling; self-limiting
# because conversions miss. Master toggle for A/B validation:
INNINGS_CONTINUATION_ENABLED = True
INNINGS_MAX_CONTINUATIONS = 6            # safety cap: max free continuations per at-bat
                                         # (a freak no-miss streak can't hang the game;
                                         # rarely hit — probability ends most at-bats first)
# Innings post-TD go-for-the-top-rung eagerness (the ONLY way to continue the at-bat, so
# teams reach for it far more than in a clock game). desire = base (+trail / -lead) + aggr,
# then tempered by the top rung's make odds. Tunable against sim measurements.
INNINGS_CONVERSION_BASE_GO   = 0.55      # baseline eagerness to extend the at-bat
INNINGS_CONVERSION_TRAIL_STEP = 0.12     # + per point of deficit (trailing → chase harder)
INNINGS_CONVERSION_TRAIL_CAP  = 0.45     # cap on the trailing boost
INNINGS_CONVERSION_LEAD_STEP  = 0.12     # − per point of lead (ahead → bank the safe point,
INNINGS_CONVERSION_LEAD_CAP   = 0.55     #   don't run it up); a ~score-plus lead ≈ never gambles
INNINGS_CONVERSION_AGGR_SPAN  = 0.15     # ± across the coach-aggressiveness range
# Last try of the final at-bat: the conversion is weighed by expected OUTCOME, not by
# whether it buys another drive. Relative worth of where the try leaves you.
INNINGS_LASTCHANCE_WIN_VALUE  = 1.0      # the try takes the lead
INNINGS_LASTCHANCE_TIE_VALUE  = 0.5      # the try only ties (roughly a coin flip after)
INNINGS_LASTCHANCE_CONTINUE_BONUS = 0.15 # extra for a TYING top rung — it extends the at-bat
# Last try, already ahead, opponent still to bat: take the sure points by default. The
# spread is what separates coaches — a conservative one basically never gambles the safe
# point, an aggressive one reaches for the extra margin fairly often.
INNINGS_LASTCHANCE_LEAD_GO_BASE   = 0.10
INNINGS_LASTCHANCE_LEAD_AGGR_SPAN = 0.25

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
# ⚠️ EXPERIMENTAL THIRD PAIR (2026-08-18). With only the midfield (50) and end-zone (18-in)
# pairs there is a 31-yard DEAD ZONE between them, and measurement showed that is where a
# team one point short spends its time: 81% of snaps while stuck have no hoop in range at
# all. This pair sits between the two to give that stretch something to shoot at. Reached
# like the midfield pair — while APPROACHING it only, since once the ball is past, the
# hoops are behind the offense. Set `SIDELINE_GOAL_MIDRANGE_YARD = 0` to switch it off and
# get the shipped two-pair field back.
# Placement was measured over 170 games an arm against the two-pair field. At the 30 with a
# 20-yard reach it covers yte 30-50, meeting the midfield window exactly and leaving only
# yte 19-29 dead. Alternatives tried: 34/14 (covers 34-48, leaves two gaps) and 25/25
# (covers 25-49, but reaches so far back the shot is long and rarely makes).
#
# ⚠️ WHAT IT ACTUALLY BUYS IS CONVERSION, NOT SPEED. Across three seeds the time a team
# spends one or two short did NOT reliably shorten (7.4 -> 5.9, 6.0 -> 6.9, 7.4 -> 7.4
# minutes), because a third pair does not make possessions arrive faster. What it does
# reliably is end those spells in a LANDING instead of a fizzle: 68 -> 74%, 58 -> 70%,
# 62 -> 70%, and target finishes overall 67 -> 81%. Snaps-while-stuck with something to
# shoot at go 22% -> 30%. Game length is unchanged (~141 plays).
#
# The cost is a little comeback tension: the chaser closed the gap on 46% of stuck spells
# with two pairs and 40% with three.
SIDELINE_GOAL_MIDRANGE_YARD = 30         # the third pair sits at the 30
SIDELINE_GOAL_MIDRANGE_RANGE = 20        # in range this many yards BEFORE it

SIDELINE_GOAL_ENDZONE_MIN = 3            # end-zone pair reachable from the ... 3 ...
SIDELINE_GOAL_ENDZONE_RANGE = 18         # ... out to the 18 (the red zone; not from the goal line itself)
# Play-caller: attempt chance when a fresh pair is in range (a low-risk point-grab now).
SIDELINE_GOAL_ATTEMPT_INRANGE = 0.55     # base chance when in range of an unused pair (a
                                         # low-risk point — teams grab it readily when they can)
SIDELINE_GOAL_ATTEMPT_STALL_MULT = 1.4   # x when the drive is stalling (salvage a point)
SIDELINE_GOAL_ATTEMPT_AGGR_SPAN = 0.25   # + up to this for a max-aggressiveness coach
SIDELINE_GOAL_ATTEMPT_MAX = 0.90         # cap on the attempt chance
# Late-game deficit awareness: a hoop shot consumes the down with no yardage, so a MAKE
# or a MISS both push the offense to the next down. The play-caller therefore skips the
# PENULTIMATE down normally (a hoop there forces the final down regardless of the result)
# and never shoots on the FINAL down (it would forfeit the scoring play). BUT when the
# bonus point(s) are what bridge a FG/TD to a tie/lead late (see _hoopPointsNeeded), the
# offense goes out of its way to bank BOTH hoops — reliably, and (when the points are
# mandatory) even on the penultimate down / in hurry-up.
SIDELINE_GOAL_DESPERATION_SECS = 360     # "late": Q4 game clock at/under this (all of OT qualifies)
SIDELINE_GOAL_DESPERATION_CHANCE = 0.92  # attempt chance when the hoop point is needed to tie/win
# ⚠️ HOLD THE END-ZONE SHOT UNTIL IT IS MAKEABLE. That pair only gets easier as the drive
# advances (0.02 make prob per yard over an 18-yard window — 49% from the 18 against 79%
# from the 3 for a neutral QB), so firing it the moment it comes into range is dominated
# by driving one more snap. 0.60 sits at roughly the 12-13 yard line. ⚠️ It applies to the
# END-ZONE pair alone: the midfield and mid-range pairs are approach-only, so declining
# one loses it, and a 49% shot in hand beats no shot at all.
SIDELINE_GOAL_LATE_MIN_MAKE = 0.60

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
    {'key': 'dunk',        'label': 'DUNK',           'scorer': [('power', 0.7), ('xFactor', 0.3)],      'defender': [('power', 0.6), ('agility', 0.4)],      'solo': False, 'weight': 1.0},
    {'key': 'race',        'label': 'RACE',           'scorer': [('speed', 1.0)],                        'defender': [('speed', 1.0)],                        'solo': False, 'weight': 1.0},
    {'key': 'arm_wrestle', 'label': 'ARM WRESTLE',    'scorer': [('power', 1.0)],                        'defender': [('power', 1.0)],                        'solo': False, 'weight': 1.0},
    {'key': 'beauty',      'label': 'BEAUTY CONTEST', 'scorer': [('xFactor', 0.6), ('creativity', 0.4)], 'defender': [('xFactor', 0.6), ('creativity', 0.4)], 'solo': False, 'weight': 0.8},
    {'key': 'backflip',    'label': 'BACKFLIP',       'scorer': [('agility', 1.0)],                      'defender': None,                                    'solo': True,  'weight': 1.0},
    {'key': 'dance_off',   'label': 'DANCE-OFF',      'scorer': [('creativity', 0.6), ('agility', 0.4)], 'defender': [('creativity', 0.6), ('agility', 0.4)], 'solo': False, 'weight': 1.0},
    {'key': 'staredown',   'label': 'STARING CONTEST','scorer': [('xFactor', 1.0)],                      'defender': [('xFactor', 1.0)],                      'solo': False, 'weight': 0.8},
    {'key': 'goalpost',    'label': 'GOALPOST CLIMB', 'scorer': [('agility', 0.6), ('power', 0.4)],      'defender': None,                                    'solo': True,  'weight': 0.9},
    {'key': 'punt_catch',  'label': 'PUNT & CATCH',   'scorer': [('power', 0.4), ('speed', 0.4), ('xFactor', 0.2)], 'defender': None,                         'solo': True,  'weight': 0.9},
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
        'win':   ["{scorer} leaps and HAMMERS the ball over the crossbar. TOUCHDOWN!",
                  "{scorer} absolutely posterizes {defender} with the dunk over the crossbar. TOUCHDOWN!"],
        'stuff': ["{scorer} goes up for the slam but {defender} swats it away. No touchdown.",
                  "{defender} rises with {scorer} and stuffs the dunk. No points."],
    },
    'race': {
        'win':   ["{scorer} and {defender} line up on one sideline and race across the field to the other sideline. {scorer} wins by a nose. TOUCHDOWN!",
                  "{scorer} and {defender} race across the endzone. {scorer} leaves {defender} in the dust. TOUCHDOWN!"],
        'stuff': ["{scorer} and {defender} begin to race, but {scorer} trips and falls flat on their face. No score.",
                  "{scorer} and {defender} line up on one 10 yard line and race, but {defender} beats them to the endzone cleanly. No touchdown."],
    },
    'arm_wrestle': {
        'win':   ["{scorer} and {defender} set up a folding table in the endzone. {scorer} slams {defender}'s arm down as the crowd erupts. TOUCHDOWN!",
                  "{scorer} locks hands with {defender}, stares deep into their soul, and pins them immediately. TOUCHDOWN!"],
        'stuff': ["{scorer} grunts mightily for a full thirty seconds before {defender} casually pins them. No touchdown, only embarrassment.",
                  "{defender} slams {scorer}'s arm through the folding table. The table did not survive. No touchdown."],
    },
    'beauty': {
        'win':   ["{scorer} struts down an imaginary runway, hits a pose at the goal line, and blows a kiss to the judges, who begin weeping. TOUCHDOWN!",
                  "{scorer} serves a stone cold pose, their hair somehow flowing perfectly under their helmet. All 10's across the board. TOUCHDOWN!"],
        'stuff': ["{scorer} attempts a smolder but it reads more like indigestion. The judges do not approve. No touchdown.",
                  "{scorer} trips on the runway walk and takes out a judge's table. Rejected."],
    },
    'backflip': {
        'win':   ["{scorer} launches into a backflip and sticks the landing like they've been waiting their whole life for this. TOUCHDOWN!",
                  "{scorer} throws a full backflip in pads and helmet and lands it clean. TOUCHDOWN!"],
        'stuff': ["{scorer} gets about 40% of the way around a backflip and lands face-first in the endzone. No touchdown.",
                  "{scorer} attempts the backflip, panics mid-air, and absolutely beefs it. No points awarded."],
    },
    'dance_off': {
        'win':   ["{scorer} breaks into a routine so filthy that {defender} just walks off the field mid-song. TOUCHDOWN!",
                  "{scorer} hits a move that could be considered illegal in some jurisdictions. {defender} counters with something resembling a seizure. Judges side with {scorer}. TOUCHDOWN!"],
        'stuff': ["{scorer} opens with the sprinkler. Who do they think they are? {defender} wins by default. No touchdown.",
                  "{defender} unleashes footwork nobody knew they had while {scorer} is still doing warmup shoulder rolls. No points."],
    },
    'staredown': {
        'win':   ["{scorer} and {defender} lock eyes at midfield. Ninety seconds of pure silence later, {defender} blinks and immediately regrets everything. TOUCHDOWN!",
                  "{scorer} stares directly into {defender}'s soul and apparently finds nothing there worth fearing. {defender} looks away. TOUCHDOWN!"],
        'stuff': ["{scorer} lasts eleven seconds before a gnat flies into their eye. {defender} never even flinched. No touchdown.",
                  "{defender} stares back with the dead-eyed calm of someone who has seen things. {scorer} cracks immediately. No points."],
    },
    'goalpost': {
        'win':   ["{scorer} scales the goalpost like there's money at the top and perches on the crossbar, arms raised. TOUCHDOWN!",
                  "{scorer} shimmies up the upright, sits on top, and waves down at everyone like this is completely normal. TOUCHDOWN!"],
        'stuff': ["{scorer} gets about four feet up the post, loses grip, and slides down in embarrassment. No touchdown.",
                  "{scorer} jumps for the crossbar, misses it entirely, and lands in a heap of shattered confidence. No points."],
    },
    'punt_catch': {
        'win':   ["{scorer} booms a punt into the stratosphere, sprints fifty yards, and catches their own kick without breaking stride. TOUCHDOWN!",
                  "{scorer} punts it sky-high and sprints down the field to catch it. TOUCHDOWN!"],
        'stuff': ["{scorer} launches a beautiful punt, sprints after it and dives to try and catch it, but it lands a full ten yards further. No touchdown.",
                  "{scorer} shanks the punt directly sideways into the bench. Good luck catching that. No points."],
    },
}
CONTEST_TYPE_LABELS = {t['key']: t['label'] for t in CONTEST_TYPES}

# ── Card gate — the FP power bar (fantasy/cards fusion, docs/CARD_ONCARD_REBASE_PLAN.md) ──
# Every equipped card has a POWER BAR tied to the depicted player's weekly fantasy points.
# You always get the player's FP; the card's EFFECT is a bonus on top, unlocked by the bar.
# One stat (FP), one number per position, a pure on/off gate (no scaling):
#   * MOST cards fill the bar with FP — the effect unlocks once it's full (player clears the
#     threshold), and a bench-warmer never fills it.
#   * INVERSE / underdog cards (insurance, "reward a rough week") run the bar in REVERSE — it
#     starts full and DEPLETES as the player scores; the effect is disabled once it empties.
CARD_GATE_ENABLED = True
# Per-position FP threshold (1-based QB=1…K=5). This is the METALLIC (base effect tier) row —
# ~0.6-0.75 of each position's median weekly FP, so a decent game fills the bar (~70% of weeks).
# It is also the fallback used by gate-EXEMPT mechanics (chance FP-fill, metronome's grow check,
# the amplifier fallback) that read a position bar without a frozen edition gate. Rebalanced
# from the median-relative data: QB was the loosest (77% clear -> 8→9), RB the strictest
# (60% -> 9→7); WR/TE/K were on target.
CARD_GATE_FP_THRESHOLDS = {1: 9, 2: 7, 3: 8, 4: 4, 5: 6}
# Higher editions only mint on higher-rated players (holo ≥75, prismatic ≥80, diamond ≥90), who
# score ABOVE the position median — so a flat bar gets EASIER at higher rarity. To keep the gate
# a real gamble (and offset the higher ceilings), the threshold RISES with edition. Calibrated
# per (edition, position) from the FP distribution WITHIN each rarity's rating band, targeting a
# clear rate that falls with rarity (~70% metallic → ~55% diamond). buildGateSpec picks the row
# for the card's edition; frozen into gate.threshold at mint. The floor 'base' is gate-exempt.
CARD_GATE_FP_THRESHOLDS_BY_EDITION = {
    'metallic':    {1: 9,  2: 7,  3: 8,  4: 4, 5: 6},
    'holographic': {1: 11, 2: 9,  3: 10, 4: 5, 5: 7},
    'prismatic':   {1: 13, 2: 11, 3: 12, 4: 6, 5: 8},
    'diamond':     {1: 15, 2: 13, 3: 14, 4: 7, 5: 9},
}
# All-Pro classification (prior-season All-Pro selections, holo+ only) lowers ITS OWN card's
# gate threshold — an individual accolade, so it buys individual reliability ("the best
# players deliver even on an off day"). On-card only (each card's gate.threshold is
# independent in its effect_config); never touches the hand. Frozen at mint.
# e.g. 0.7 -> QB 8->6, RB 9->6, WR 8->6, TE 4->3, K 6->4. Floored at 1.
CARD_GATE_ALLPRO_MULT = 0.7

# Chance cards work differently from the on/off bar above. Their power bar IS the trigger
# probability for the enhanced payout, filled ADDITIVELY from two sources: the depicted
# player's own FP (toward their position threshold) plus the card's own condition (struggling
# roster, favorite-team losses, etc.). Each source maxes out at its weight below; the two sum
# (capped at 100%) so a big on-card week AND a maxed condition together guarantee the enhanced
# hit. Group-C chance cards whose condition already IS the on-card player's performance
# (crescendo/traverse/bonsai) skip the FP source and fill the whole bar from their condition.
CARD_CHANCE_FP_WEIGHT = 0.5         # max bar fill from the depicted player's FP
CARD_CHANCE_CONDITION_WEIGHT = 0.5  # max bar fill from the card's own condition
# How many struggling roster players (or failed cards) max out the condition source.
CARD_CHANCE_CONDITION_FULL_COUNT = 3

# Team stacking — the lineup-synergy mechanic. Fielding N cards whose depicted players share
# a real team grants a lineup-wide FPx that ESCALATES with the size of the largest such group
# (correlated upside: when a team's offense goes off, its players score together — and it's
# higher variance, trading against the FP meter's reward for consistency). Keyed by stack
# size, capped at the highest key; a lone same-team pair starts at 2.
CARD_TEAM_STACK_BONUS = {2: 0.05, 3: 0.12, 4: 0.22, 5: 0.35, 6: 0.50}
# Champion classification (prior-season title winners = one team) AMPLIFIES a stack: the
# stack bonus is multiplied by (1 + championFraction × premium), so a stack of the reigning
# champions ("Dynasty") pays more than the same-size stack of a random team. A team accolade
# → a team-synergy perk. Per-champion (championFraction = champions in the stack / stack
# size), so no cliff. e.g. 0.5 -> an all-champion stack pays 1.5× the base stack bonus.
CARD_CHAMPION_STACK_PREMIUM = 0.5
# The "Synergy" weekly modifier AMPLIFIES the team-stack bonus for that week (mirrors how
# Amplify doubles FPx portions). It scales the applied stack delta by this factor, so a
# stacked lineup is rewarded and a non-stacked one is unaffected (the old unique-position
# formula was dead under fusion — every equipped card is a different slot). e.g. 2.0 -> a
# 0.22 four-stack pays +0.44 FPx that week.
SYNERGY_MODIFIER_STACK_MULT = 2.0

# ── Drive Clock (dormant mechanic — docs/DRIVE_CLOCK_PLAN.md) ──
# A shot-clock for possessions. Two mode knobs: unit ('seconds' of game clock vs
# 'plays' per snap) × reset ('possession' = a hard cap on the whole drive,
# 'series' = refills on each first down). Expire before scoring (or a first down,
# in series mode) = turnover on downs. Off by default; a Cores vote picks a PRESET
# (each a full {enabled, unit, reset, limit} bundle — the compound-rule vote).
DRIVE_CLOCK_DEFAULT_LIMIT = {"seconds": 120, "plays": 8}
# Tuned against the clock-management behavior: when the drive clock is low the
# offense hurries up (~17s/play instead of ~40s), so the seconds limits are kept
# tight enough to still bite. plays/series is deliberately OMITTED — a snap counter
# that refills on each first down is just the down system (N tries to convert).
#
# Limits are set so the clock ends roughly 1 drive in 7 rather than dominating the
# down system. Measured on live games the original 6-plays and 45s/series presets
# ended 27% and 32% of all drives — at 45s/series the clock killed as many drives as
# PUNTS did. Both were structurally too tight: 6 snaps allows at most ONE first down
# before expiry, and 45s is barely two hurry-up snaps (DRIVE_CLOCK_SECS_PER_SNAP=18),
# so it forced permanent hurry-up and expired anyway. Re-measured with
# `tune_drive_clock.py`: 6 plays 26% -> 8 plays 10%, 45s/series 51% -> 70s 17%.
# 120s/possession is left alone — it already sits at/under target on both the local
# sweep (9%) and live games (19%), and loosening it to 150s made it nearly inert (5%).
DRIVE_CLOCK_PRESETS = [
    {"key": "dc_120s_possession", "label": "120 seconds, whole drive",
     "patch": {"driveClockEnabled": True, "driveClockUnit": "seconds",
               "driveClockReset": "possession", "driveClockLimit": 120}},
    {"key": "dc_70s_series", "label": "70 seconds, resets each first down",
     "patch": {"driveClockEnabled": True, "driveClockUnit": "seconds",
               "driveClockReset": "series", "driveClockLimit": 70}},
    {"key": "dc_8plays_possession", "label": "8 plays, whole drive",
     "patch": {"driveClockEnabled": True, "driveClockUnit": "plays",
               "driveClockReset": "possession", "driveClockLimit": 8}},
]
# Wire the presets into the vote candidate (declared above with presets=None to
# avoid a forward-reference).
RULE_VOTE_CANDIDATES["driveClock"]["presets"] = DRIVE_CLOCK_PRESETS

# Drive-clock SHOT SELECTION (play-caller awareness): as the possession clock winds
# down the offense must gain yards FAST, not just snap fast, so bias toward chunk
# plays. `_applyDriveClockMods` keys off yards-needed-per-remaining-snap.
DRIVE_CLOCK_SECS_PER_SNAP = 18.0        # est. seconds/snap in hurry-up (12s huddle + play)
DRIVE_CLOCK_PRESSURE_SNAPS = 3.0        # only bias once <= this many snaps of budget remain
DRIVE_CLOCK_CHUNK_THRESHOLD = 8.0       # yds/snap below which checkdowns/runs still suffice
DRIVE_CLOCK_CHUNK_CEILING = 20.0        # yds/snap at which urgency saturates (full bias)

# Drive-clock behavior thresholds are FRACTIONS of the configured seconds-limit, so
# they scale to any preset instead of being hardcoded for the 120s default. Under a
# 45s/series clock, a fixed `remaining <= 75` was ALWAYS true — the offense pinned in
# permanent hurry-up and never managed the game clock. Values reproduce the old 120s
# absolutes: 90→0.75, 75→0.625, 20→0.167, 15→0.125, 12→0.10.
DRIVE_CLOCK_OOB_FRAC = 0.75             # seek out-of-bounds (pause the clock) below this
DRIVE_CLOCK_HURRY_FRAC = 0.625          # 2-minute-drill tempo below this
DRIVE_CLOCK_TAKE_POINTS_FRAC = 0.167    # ~one snap left: take a makeable FG / heave a hail mary
DRIVE_CLOCK_LOW_FRAC = 0.125            # amber chip / spike-to-stop trigger
DRIVE_CLOCK_SPIKE_FRAC = 0.10           # critically low: spike to stop the game clock
# Last-snap PUNT (deep in own territory, can't convert, out of FG range): rather than
# hand the ball back on downs at your own spot, punt to flip field position.
DRIVE_CLOCK_PUNT_MIN_YTE = 60           # only "deep" — ball on your own side (>=60 yds to EZ)
DRIVE_CLOCK_PUNT_MIN_TOGO = 7           # only long yardage — can't realistically convert in one snap

# ── Game Formats / win conditions (docs/GAME_FORMATS_PLAN.md) ──
# Each preset is a full {gameFormat, ...config} bundle. One format at a time. ONLY the
# formats we've tested enough to ship are offerable here (a vote / Criticality can only
# pick from this list). The target / play_limit / bust FORMATS still exist in
# game_formats.py (dormant) — re-add their presets below to re-enable them (owner
# 2026-07-13: hold target/play_limit/bust until they're tested).
GAME_FORMAT_PRESETS = [
    {"key": "gf_chess_clock_30", "label": "Chess Clock (30:00 each)",
     "patch": {"gameFormat": "chess_clock", "offenseClockBudgetSeconds": 1800}},
    {"key": "gf_innings_3", "label": "Innings (3, try-driven)",
     "patch": {"gameFormat": "innings", "inningsPerGame": 3, "triesPerInning": 3}},
    {"key": "gf_frames_6", "label": "Frames (6, match play)",
     "patch": {"gameFormat": "frames", "framesPerGame": 6}},
    # HELD until tested (re-add to re-enable) — the formats themselves are still built:
    #   {"key": "gf_target_30",      "label": "First to 30",
    #    "patch": {"gameFormat": "target", "targetScore": 30}},
    #   {"key": "gf_play_limit_30",  "label": "30 Plays a Quarter",
    #    "patch": {"gameFormat": "play_limit", "playsPerQuarter": 30}},
    # Certified 2026-08-17 (test_darts_format.py): scores never exceed X, are always whole
    # numbers, 87% of games are decided by landing exactly on it, and ties are gone.
    #
    # ⚠️ THE TARGET HAS A USABLE RANGE, AND 30 IS OUTSIDE IT. Darts is only a game about
    # landing on a number while the number is reachable inside four quarters; above that
    # the clock decides it and the format is ordinary football with a ceiling. Measured
    # over 50 games at each target, share of games decided by LANDING on it:
    #
    #     X=10  98%   X=12  98%   X=15  88%   X=18  84%
    #     X=21  66%   X=24  58%   X=30  30%
    #
    # ⚠️ SHIPPED AT 24 (owner, 2026-08-23), the far end of the range they gave on
    # 2026-08-18 ("higher is better. 21-24"). It was 21 first, and the trade is stated
    # plainly rather than hidden: 58% of games are decided by LANDING on the number
    # against 21's 66%, so ~46% go to the clock instead — the owner raised it knowing
    # that ("I understand that less games will end with reaching the target"). What it
    # buys is a longer game and a later finish.
    # ⚠️ 24 IS THE CEILING, not a step on a ladder. Above it the clock decides most games
    # and darts stops being a game about landing on a number at all (30 lands only 30% of
    # the time). `test_darts_format.py` asserts the preset stays at or under it.
    #
    # ⚠️ `GameRules.targetScore` DEFAULTS to 30 — it belongs to the 'target' format ("first
    # to 30") — so darts activated without a patch inherits a target it plays badly at.
    # `BustFormat._target` documents its own fallback and cannot apply it, because the
    # field is always present. The preset is the supported way in; anything else needs the
    # target set deliberately.
    #
    # Scoring stays mixed at 18 rather than degenerating into dinking 1-pointers:
    # TD 38% / FG 33% / hoop 30% of all points banked.
    #
    # GAME LENGTH at the shipped 21: the target is reached at a median 73% of regulation
    # (~44 of 60 game-minutes, ~141 plays against a standard game's ~155, i.e. 91% of a
    # full game), split Q2 18% / Q3 38% / Q4 43% — none in Q1. 18% finish before halftime,
    # and ⚠️ THOSE ARE THE DECIDED GAMES, not truncated close ones: measured at 18, the
    # loser's median score in a pre-halftime finish was 6 of 18 and NOT ONE was within 4,
    # against a loser's median of 12 after halftime. The format mercy-rules itself.
    #
    # ⚠️ THE LAST POINT IS THE HARD ONE, AND THE WAIT IS FIELD POSITION RATHER THAN
    # MARKSMANSHIP. Measured over 90 games at 21: a team that gets within 2 of the target
    # sits there a median 30 plays / 8 game-minutes (p90 ~19 minutes), and 39% never land
    # at all. Per spell it gets only ~2 snaps with a hoop in range out of ~12 stuck, takes
    # ~2 shots and makes ~1, across ~2.6 drives.
    #
    # The diagnosis: 81% of stuck snaps have NO hoop in range. The pairs sit at the 50 and
    # inside the 18, so a team one point short spends most of its downs in the dead zone
    # between them with literally nothing to shoot at. It is not hesitancy (61% of in-range
    # chances are taken) and not accuracy (68% of those go in). If that wait is ever
    # judged too long, the lever is hoop GEOMETRY — a third pair, or a wider midfield
    # window — NOT the trigger rates, and darts already has precedent for its own geometry
    # (`_hoopTarget` lowers the end-zone pair's near edge to the 1 for this format alone).
    #
    # The wait is what makes the endgame a contest rather than a formality, and the numbers
    # say it is a real one: while a team is stuck the chaser scores 58% of the time, closes
    # the gap 45%, and draws level or goes ahead 10%, with the stuck team going on to lose
    # 10%. The hoop is the winning play in 56% of all target finishes (field goal 28%,
    # touchdown 15%), so it is the format's primary win condition and not a consolation.
    # ⚠️ Deliberately NOT covered by a test — these are emergent distributions with enough
    # run-to-run spread to make any threshold flaky (see the note in test_darts_format.py).
    #
    # A TIE AT THE END OF REGULATION GOES TO ORDINARY OVERTIME — `checkEarlyEnd` returns
    # None when nobody has landed, so the standard clock/OT path takes it, and darts
    # scoring still applies inside OT (a busting score is still void, so it is usually
    # decided by landing). Measured over 270 games at 18/21/24: OT is reached 0-2% of the
    # time, every OT game ended by landing on the target, and there were ZERO draws. The
    # engine's `MAX_OT_PERIODS` (5) backstop accepts a tie and was never reached.
    # ⚠️ `sidelineGoalsEnabled` is NOT listed here any more, and removing it was the fix
    # rather than an omission: the 1-point hoop is darts' prerequisite (without it the
    # smallest score is 3, so a team on X-1 can never land) and it now lives in
    # `BustFormat.bundledRules`, where every activation path gets it. It was here alone,
    # so darts switched on any other way was a different game — 8% of finishes landed on
    # X instead of 85%.
    # ⚠️ `chaosEligible: False` KEEPS DARTS OUT OF CRITICALITY CHAOS (owner, 2026-08-18)
    # while the format is still being worked on. Chaos picks a format per game at random,
    # hides it from users, and the results COUNT — which is the wrong place to debut a
    # format whose endgame is still being tuned. It stays a normal vote preset, so a league
    # can still choose it deliberately; this only stops it arriving by surprise.
    # ⚠️ THE KEY CARRIES THE TARGET, so it moves with it — `RuleVote.option_key` is
    # persisted, so renaming orphans any darts vote already cast in an OPEN window. Ship
    # a target change between windows, not during one.
    {"key": "gf_bust_24",        "label": "Darts (land on 24)", "chaosEligible": False,
     "patch": {"gameFormat": "bust", "targetScore": 24,
               "touchdownPoints": 6, "fieldGoalPoints": 3, "safetyPoints": 2,
               "extraPointPoints": 1, "twoPointConversionPoints": 2}},
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
    "bust":        "Land directly on the target score to win. Overshoot it and the points are voided. Auto-enables sideline targets.",
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
LEAGUE_COMPRESSION_FACTOR = float(_os.environ.get('FLOOS_COMPRESSION', '0.45'))  # 1.0 = none, 0.5 = aggressive
# Center of the compression curve — this is the effective baseline every player
# plays at, so it also sets the league's overall scoring level (higher = more
# offense). Raised 80 -> 84 to recover the scoring the attribute remap cost:
# the remap (skill-creep fix) lowered profile ratings and pulled total scoring
# from ~38 to ~33 pts/game; nudging the in-game baseline up restores ~35 without
# re-inflating any displayed rating (compression only touches the live
# gameAttributes copy). Measured: +1 mean ~= +0.2 pts/team. See _applyLeagueCompression.
LEAGUE_COMPRESSION_MEAN = 84        # Center of the curve

# ── End-game snap estimate ────────────────────────────────────────────────
# A play (or a FG) only needs to be SNAPPED before the clock hits 0:00 — it may finish
# after. So the closing-snap estimate (_estimateAvailablePlays) reserves only a snap's
# worth of time for the final kick/play, not a whole play's duration. Roughly the pre-snap
# time to get lined up and get the ball off. Was implicitly ~7s (a full play), which
# undercounted the last snap in tight windows.
FINAL_SNAP_SECS = 2

# "There is no snap after this one" — the window `_lastSnapBeforeBreak` uses to take a
# makeable end-of-half field goal on ANY down (`downsPerSeries` is mutable, 3 to 5, so
# "the final down" and "the last chance" are not the same question).
#
# ⚠️ IT IS NOT ONE NUMBER, because a stopped clock changes the cost of a snap entirely:
#
#   clock running, no timeout : huddle (~12s) + live ball (~5s) + the FG snap = ~19s
#   clock stopped or a timeout in hand : huddle skipped, live ball + FG snap  = ~7s
#
# A fixed value is wrong in both directions — 18 kicks while a well-managed offense
# could still fit a sideline throw AND the kick, and it is barely enough for one that
# cannot stop the clock at all. So the window is built from these two parts instead, and
# an offense that has managed its clock keeps the wider set of options it earned.
# Chess clock: punt on the last snap the budget allows when no field goal is available,
# rather than let the clock die and hand the opponent the ball AT THE SPOT (a lockout is
# `turnover(..., yardsToSafety)`). Off restores the old behaviour exactly.
CHESS_CLOCK_PUNT_ENABLED = True

# How close the end zone has to be for ONE desperation play to plausibly reach it — the
# only situation in which a TRAILING offense should spend its last snap going for it
# rather than punting. Beyond this a heave is not a chance, it is a giveaway: the drive
# ends either way and the only thing still on the table is where the opponent starts.
#
# ⚠️ This is now used ONLY to pick the DEPTH of the desperation throw (deep vs long). It
# used to also gate whether a TRAILING team punted, which is what let a losing team punt
# its last possession away — see the punt block in floosball_game for why that was wrong.
CHESS_CLOCK_STRIKE_YARDS = 45

# ---- Chess clock: the TIED punt decision ----
# Losing teams never punt (they cannot score again, so field position is worthless to
# them) and leading teams always do. Tied is the interesting case, and it comes down to
# what a giveaway actually hands the opponent (owner, 2026-08-13).
#
# `yardsToEndzone` is distance to the opponent's end zone, so a giveaway leaves them
# `100 - ytez` yards out and kicking from about 17 yards further back:
#     ytez 85 (own 15) -> a 32 yard chip shot
#     ytez 75 (own 25) -> a 42 yard kick, still very makeable
#     ytez 65 (own 35) -> a 52 yarder
#     ytez 50 (midfield) -> a 67 yarder, i.e. nothing
# At or beyond PIN_YARDS a turnover on downs is a gift of makeable field goal range, so a
# tied team always punts. Closer to midfield it is a genuine choice between pinning them
# and taking a shot — "probably more heavily weighted to punting though".
CHESS_CLOCK_TIED_PIN_YARDS = 72

# How much the tied near-midfield case DAMPENS the coach's punt decision. It multiplies
# the existing acceptance rather than adding a second roll, so there is still exactly one
# decision per snap. Net punt rate near midfield when tied: about 56% for an average staff
# and 80% for an elite one, against 70%/100% when pinned deep.
CHESS_CLOCK_TIED_MIDFIELD_PUNT = 0.8


LAST_SNAP_HUDDLE_SECS = 12   # hurry-up pre-snap; 9-15 across the coach clock-IQ range
LAST_SNAP_LIVE_SECS = 5      # snap to whistle on a run (4-6)

# ── No-huddle ─────────────────────────────────────────────────────────────
# ⚠️ THE OFFENSE HAD NO PRESENCE BETWEEN THE WHISTLE AND THE SNAP. Tempo was one
# coach-scaled number, so "hurry-up" meant a 12-second huddle instead of a 25-40 second
# one and the team ALWAYS huddled. There was no state in which they did not.
#
# The trigger is the CLOCK, not a coach preference (owner, 2026-08-12): if the clock did
# not stop on the last play and the offense is in hurry-up, they stay at the line. That
# falls straight out of state the engine already has — `clockRunning` and the `hurryUp`
# intent — so it needs no new attribute and no new decision.
#
# ⚠️ These numbers are the whole cost model, and the pre-snap drain nearly vanishing is
# the entire point of the state:
#     huddle, neutral   25-40s
#     huddle, hurry-up  ~12s   (LAST_SNAP_HUDDLE_SECS)
#     no-huddle         ~4-9s  (here)
# The tighter jitter is deliberate: a no-huddle snap is a repeated, rehearsed action, so
# it should not vary as much as a huddle call does.
NO_HUDDLE_ENABLED = True
NO_HUDDLE_PRESNAP_SECS = 6    # base; coach clock IQ moves it +/-2 and jitter +/-1
NO_HUDDLE_PRESNAP_FLOOR = 4   # below the 8s huddle floor on purpose — that floor IS a huddle
NO_HUDDLE_IQ_SPREAD = 4       # +/-2 across the clock-IQ range, half the huddle's spread
NO_HUDDLE_JITTER = 1          # +/-1, against the huddle's +/-3

# ⚠️ THE TIGHT END IS THE SECURITY BLANKET, and the menu restriction alone did not make
# him one. Restricting to short/medium moved TE involvement only 67.2% -> 64.8% of called
# plays, because most plays list all three receivers anyway — so which receiver the play
# NAMES was never the lever. The lever is who the quarterback LOOKS AT.
#
# A perceived-openness nudge, the same mechanism `AWAKENED_RECEIVER_OPENNESS_BONUS` uses
# to make a powered-up receiver draw the read. Sized well below it (22): this is a
# tendency, not a compulsion, and the TE should still lose a read to a genuinely wide-open
# receiver. It nudges the QB's PERCEPTION, so it never makes the throw safer than it is —
# a covered TE stays covered and the ball can still be broken up.
#
# ⚠️ It rides on the no-huddle state only. Outside a drill the TE's share should come from
# the playbook and the matchup, where it already does.
NO_HUDDLE_TE_OPENNESS_BONUS = 10

# ── Chess-clock timeouts ──────────────────────────────────────────────────
# In the Chess Clock format the offense's possession budget IS its real clock,
# and a timeout stops the pre-snap huddle drain — so a team preserves its budget
# by calling timeouts once it's GETTING low (not just at the final snap). When
# the offense's remaining budget drops to this many seconds and it's trailing or
# tied, it spends a timeout before the huddle to squeeze more plays out of what's
# left. ~2-3 plays of budget; bounded by the 3 timeouts a team holds.
CHESS_CLOCK_TIMEOUT_PRESERVE_SECS = 90
# Chess-clock huddle when the budget isn't yet low. Chess clock never burns clock
# (there's no shared clock to run out — burning only wastes the budget and hands
# over possession sooner), so this replaces the burn/neutral huddles there. This is
# the AVERAGE-coach huddle; the actual length is gated by the coach's clock
# management (below), so a team's budget efficiency is a coaching skill. Leaner than
# a standard neutral so teams conserve budget from the opening drive, not just late.
CHESS_CLOCK_NEUTRAL_HUDDLE = 20
# How much clock management swings the chess-clock huddle (total spread, seconds).
# A sharp clock manager (IQ~1.0) snaps ~half this faster to save budget; a poor one
# (IQ~0.0) lets that much extra time roll off each huddle. 20 → roughly 10s (great)
# to 30s (poor) around the 20s average.
CHESS_CLOCK_HUDDLE_IQ_SPREAD = 20
# Baseline chance a clock-conscious coach gets a pass out of bounds to stop the clock
# in chess clock BEFORE the budget is low — mixed into the normal play mix, not every
# play. Scaled by clock management: a sharp coach (IQ~1.0) hits this rate, a poor one
# (~0) rarely bothers and burns budget away. The rate ramps well above this once the
# budget is actually running low.
CHESS_CLOCK_BASE_SIDELINE_PROB = 0.30
# Huddle when a chess-clock team is UP BIG (more than two scores ahead). The game is
# in hand, so it stops actively saving budget and plays a relaxed, normal pace (still
# never burns — that only wastes budget). Roughly the standard neutral huddle.
CHESS_CLOCK_RELAXED_HUDDLE = 35
# Budget (seconds) at which a chess-clock team STARTS actively conserving — the lean
# huddle and the sideline clock-stopping only kick in once the offense is down to about
# this much of its budget ("a few minutes left"). Above it teams play a normal, relaxed
# pace and let the budget drain, so games don't drag on with 130+ plays of clock-milking.
CHESS_CLOCK_CONSERVE_SECS = 180
# Budget drained from a chess-clock possession on a snap where the game clock was
# already STOPPED (incompletion / out of bounds) and no timeout was called. Running
# a play still uses possession time, so these snaps aren't free — without this floor
# a pass-heavy defensive game stops the clock constantly and the play count explodes
# (200+ plays, very long games). A deliberate TIMEOUT still fully preserves the budget
# (drains nothing) — that's the intentional conservation tool; this is for the cheap,
# unchosen stops.
CHESS_CLOCK_STOPPED_HUDDLE_DRAIN = 25

# What a snap costs, as a fraction of the tempo's normal huddle, when the game clock is
# already STOPPED (an incompletion or a catch out of bounds). Stopping the clock has to be
# a STRATEGY — it must always save budget — but it must not be free, or a pass-heavy
# offense buys near-unlimited snaps and the play count explodes. 0.6 makes getting out of
# bounds worth roughly 40% of a snap, capped by CHESS_CLOCK_STOPPED_HUDDLE_DRAIN above so
# a slow offense cannot pay more for a stopped clock than a running one.
CHESS_CLOCK_STOPPED_HUDDLE_FRACTION = 0.6

# Budget at which a chess-clock offense hurries REGARDLESS of the score. The tempo logic
# otherwise relaxes when the game is in hand, which kept a 35s huddle on a nearly-empty
# budget — the offense then could not fit a snap at all and punted with ~37s still
# showing. Running out is not a scoreboard question: a lockout is a turnover at the spot
# whatever the lead. Sized at roughly two hurried snaps, so the last of the budget gets
# spent rather than strolled away.
CHESS_CLOCK_LAST_GASP_SECS = 60
# Budget a scoring drive costs, used to decide whether a TRAILING chess-clock team can
# still realistically catch up: it needs (scoresNeeded x TD-drive) of budget, OR just a
# short FG-drive when a field goal ties/wins. These are OPTIMISTIC — a well-executed
# hurry-up drive with a couple of chunk plays — because a team only "eases up" when even
# a great drive can't get there; otherwise it keeps preserving the clock to fight. So a
# ONE-score deficit stays catchable with ~a minute of budget; it's a MULTI-score deficit
# against little budget (e.g. two scores with under a minute left) that's out of reach.
CHESS_CLOCK_CATCHUP_DRIVE_SECS = 50   # one hurry-up touchdown drive
CHESS_CLOCK_CATCHUP_FG_SECS = 30      # a field-goal-to-tie drive (shorter)
# Game-winning FG (chess clock): when a FG would WIN and the opponent is locked out
# (can't answer), a team takes it the moment it's a short, high-confidence kick — on
# any down, no need to drain the budget first. These gate that: the kick must be within
# WIN_FG_MAX_YARDS and clear FG_CONFIDENCE make probability; a longer / lower-confidence
# look means keep driving for a chip shot.
CHESS_CLOCK_WIN_FG_MAX_YARDS = 30     # kick distance (yardsToEndzone + snap) ceiling
CHESS_CLOCK_FG_CONFIDENCE = 0.80      # minimum make probability to take the game-winner

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
RB_CHECKDOWN_PRESSURE_CHANCE = float(_os.environ.get('FLOOS_CHECKDOWN', '12'))   # % of would-be sacks dumped to the RB instead
RB_CHECKDOWN_OPEN_CHANCE = 55       # % of "no one open" dropbacks checked down to the RB
RB_CHECKDOWN_BASE_YAC = 3.5         # mean YAC on a dump-off at RB speed pivot 78
RB_CHECKDOWN_YAC_PER_SPEED = 0.12   # mean YAC added per RB speed point above 78
# Designed RB screen — a called play (not a pressure reaction) on clean dropbacks.
# Blockers set up out front, so screens carry more YAC upside than a dump-off.
RB_SCREEN_ENABLED = True
RB_SCREEN_CHANCE = 1                # % of clean (non-pressure) dropbacks that are a screen
RB_SCREEN_BASE_YAC = 5.5           # mean YAC on a screen at RB speed pivot 78

# Power-Up Shop
# RETIRED (fantasy/cards fusion): roster swaps are gone, so Dispensation has nothing
# to grant. Kept for display of any historical purchases; removed from POWERUP_CATALOG
# so it can't be bought.
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
# RETIRED (fantasy/cards fusion): the FLEX slot is now unlocked by Accession
# (temp_card_slot) or an MVP card, so Conscription is redundant. Kept for display of
# any historical purchases; removed from POWERUP_CATALOG so it can't be bought.
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
    "description": "Unlocks the FLEX lineup slot (any position) for 4 weeks.",
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

# extra_swap + temp_flex retired in the fantasy/cards fusion (see notes above) — not
# listed here so the shop never offers them; their defs remain for historical display.
POWERUP_CATALOG = {
    "modifier_nullifier": POWERUP_MODIFIER_NULLIFIER,
    "temp_card_slot": POWERUP_TEMP_CARD_SLOT,
    "fortunes_favor": POWERUP_FORTUNES_FAVOR,
    "income_boost": POWERUP_INCOME_BOOST,
}

# ⚠️ EDITION ELIGIBILITY: a strong previous season opens every edition, whatever the
# rating. Measured on season 20, diamond-eligible BY RATING was six players of 192 — QB 1
# / RB 1 / WR 3 / TE 0 / K 1 — and a one-player bucket mints that bucket's ENTIRE effect
# set onto that one man, so at diamond the card simply is the player. Diamond TE had
# nobody, making every TE-exclusive diamond effect unmintable.
#
# 90 is roughly the p90 of the previous-season performance distribution (median 80, p90
# 93). It takes diamond from 6 players to 37 while moving prismatic only 53 -> 66 — the
# change lands almost entirely on the tier whose scarcity is pathological.
#
# ⚠️ It cannot inflate diamond SUPPLY: `_weightedDraw` rolls the EDITION from packWeights
# first and only then picks a template within it, so rates are independent of pool size.
# It changes what a diamond DEPICTS — stage two weights by `120 - rating`, so a 65 is
# about twice as likely to be drawn within the tier as a 94.
EDITION_ELIGIBILITY_PERF_BAR = 90

# ─── Synth Components ────────────────────────────────────────────────────────
# The consumable that gates synthetic cards: graft any effect onto any player's base
# card. Named for the family it joins — the chrome plan already writes "chrome
# components" throughout, so this is synth joining an existing vocabulary rather than
# coining one.
#
# ⚠️ IT STACKS ON `TRANSPLANT_COST_BY_EDITION`, IT IS NOT A FEE. Floobits accumulate, so
# a price can never cap grinding; a per-day item makes the real constraint DAYS ELAPSED.
# A diamond build therefore costs SYNTH_COMPONENT_PRICE + 180.
#
# ⚠️ "2 PER DAY" IS 8 A SEASON, NOT 56, and the number wants choosing on purpose because
# it reads like an order of magnitude more than it is. The regular season is FOUR real
# calendar days (28 weeks at 7 rounds a day, cross-day boundaries at weeks 8/15/22) and
# `shop_repository._dailyResetBoundary` resets per calendar day. Against a seven-slot
# lineup that is one full lineup's worth a season, if you spend every day and miss none.
# Want a lineup plus room to iterate? The number is 3.
#
# ⚠️ EVERY BUILD ALSO BURNS A PULLED DONOR, so for a newer user donors bind long before
# the daily cap does and they will never see it. The gate lands on deep collections —
# the right shape, given the friction this feature answers was reported by new users, but
# it is also why the Floobit price stays modest. Measured against a median user-week of
# 84 F and Accession at 200 F (which buys a whole lineup slot for four weeks, where this
# buys one card).
SYNTH_COMPONENT_SLUG = 'synth_component'
# ⚠️ "SYNTHESIS", NOT "SYNTH" (owner). The family will hold Chrome Components too, so the
# user-facing name has to say WHICH kind it is and say it in full — "Synth" reads as an
# abbreviation of the card type ("a synth component" sounds like a part OF a synthetic)
# rather than as the process it pays for. The SLUG stays `synth_component`: it is a
# database key with rows already written against it, and renaming it would need a
# migration to buy nothing.
SYNTH_COMPONENT_NAME = 'Synthesis Component'
SYNTH_COMPONENT_PRICE = 80
SYNTH_COMPONENT_DAILY_LIMIT = 2
# ⚠️ ACHIEVEMENT GRANTS BYPASS THE DAILY CAP — a burst of completions arrives at once and
# the shop's day boundary cannot see it. Measured on production, an engaged user finishes
# ~2 of the 13 guidance capstones a season (36% finish none, and the tail reaches 9), so
# one per capstone is self-limiting; this caps the tail at 4 rather than 9 without
# touching the typical player. ⚠️ Widening the grant list later IS a change to this cap,
# whether or not it gets discussed as one.
SYNTH_COMPONENT_ACHIEVEMENT_CAP = 4
# ⚠️ ANTI-HOARD: A HOLDING CAP ON WHAT CAN BE BOUGHT, NOT ON WHAT CAN BE HELD.
# The shop refuses to sell while a user is already sitting on this many unspent
# components; achievement grants are NEVER refused, because a reward the game promised
# must not evaporate because the shop is full.
#
# ⚠️ HOARDING IS ALREADY EXPENSIVE, WHICH IS WHY THE CAP CAN BE GENEROUS. A synthetic
# only scores in the weeks it is EQUIPPED, so a component spent in week 1 buys 28 weeks
# of that card and one spent in week 22 buys 7. Sitting on components is paying full
# price for a card and then leaving it in the box. And the shop allowance does not
# accumulate on its own — `getPurchasesToday` counts purchases since the day boundary,
# so a user who skips a day does not get four the next.
#
# What the cap actually removes is the INFORMATION play: buy early, watch who is
# producing, then build a whole lineup at once late with hindsight the pacing was meant
# to deny. At 3 a user can still bank toward one expensive build; they cannot bank a
# lineup.
SYNTH_COMPONENT_HOLD_CAP = 3

# Shop reroll (not a powerup — lives in the Daily Selection section)
SHOP_REROLL_BASE_COST = 10
SHOP_REROLL_COST_INCREMENT = 5   # Each reroll costs 5 more than the last
SHOP_REROLL_FREE_PER_DAY = 1     # the first reroll of each shop day costs nothing


def shopRerollCost(rerollCount: int) -> int:
    """Cost of the NEXT featured-card reroll, given how many have been used today.

    ⚠️ THE FIRST REROLL OF THE DAY IS FREE, AND IT IS THE REPLACEMENT FOR THE DAILY
    AUTO-REFRESH, not a bonus on top of it. The shop used to repopulate its card slate on
    its own every day, which meant a user saving up for a specific single would find it
    simply gone the next morning — reported as the shop "making the card they're trying to
    buy disappear". The slate now persists until the user chooses to change it, and the
    free reroll is what lets them change it without paying to undo an unwanted refresh.

    The paid ladder is unchanged, just shifted one place right: free, then 10, 15, 20 ...
    So a user who rerolls once a day never pays, and someone churning the shelf inside a
    single day pays exactly what they used to from their second roll on.
    """
    paid = max(0, rerollCount - SHOP_REROLL_FREE_PER_DAY)
    if rerollCount < SHOP_REROLL_FREE_PER_DAY:
        return 0
    return SHOP_REROLL_BASE_COST + paid * SHOP_REROLL_COST_INCREMENT

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
    "metallic":        {1: 0, 2: 12, 3: 24, 4: 36},
    "holographic": {1: 0, 2: 18, 3: 34, 4: 52},
    "prismatic":   {1: 0, 2: 26, 3: 48, 4: 72},
    "diamond":     {1: 0, 2: 34, 3: 60, 4: 90},
}
CARD_TIER_DIVIDEND_FLOOBITS = {
    "metallic":        {1: 0, 2: 8,  3: 16, 4: 24},
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
    "metallic": 1.0, "holographic": 1.2, "prismatic": 1.4, "diamond": 1.6,
}

# ─── Effect Transplant ("The Transplant") ────────────────────────────────────
# Graft one card's effect onto another player card you own. Both cards must be the
# SAME edition and SAME position; the target keeps its identity + upgrade tier and
# takes on the donor's effect (re-scaled to the target's rating), the donor is
# consumed. Cost scales with edition — the pricier the effect, the pricier the move.
# ('metallic' slug = the Metallic display edition; the 'base' no-effect floor can't transplant.)
TRANSPLANT_COST_BY_EDITION = {
    "metallic": 40, "holographic": 70, "prismatic": 120, "diamond": 180,
}

# ─── Card Showcase (seasonal collection payout) ──────────────────────────────
# An 8-slot showcase filled from the permanent Vault. Scored each season into a
# letter grade (F→S) that pays out flat Floobits at season end, then clears.
# Scoring is hidden (grade + named sets only) — see showcaseManager. All values
# below are owner-approved starting points; tune via /simcheck before balancing.
SHOWCASE_SLOTS = 8
# Per-card base = EDITION_POINTS × recency + Σ CLASSIFICATION_POINTS, ×tier mult.
SHOWCASE_EDITION_POINTS = {"metallic": 1, "holographic": 4, "prismatic": 12, "diamond": 30}
# `enshrined` = a Hall of Fame showpiece. Highest classification points because
# induction is the terminal accolade and the card can never be fielded — the
# Showcase is the only place it earns anything.
# NOTE: the showcase SET named "Hall of Fame" (8 MVP/Champion/All-Pro cards)
# predates this and is a DIFFERENT thing. Key deliberately `enshrined` rather
# than `hall_of_fame` so the two never collide in code; the set's display name
# is the collision that remains and wants an owner call.
# Editions a Hall of Fame showpiece is minted in. Deliberately the top tiers
# only — an enshrined player does not get a common print.
SHOWPIECE_EDITIONS = ("prismatic", "diamond")

SHOWCASE_CLASSIFICATION_POINTS = {"rookie": 5, "all_pro": 10, "champion": 12, "mvp": 20,
                                  "enshrined": 26}
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
# Cap on stacked set bonuses. Lowered 1.5 -> 1.10 (owner, 2026-08-02) so no build
# holds S into a second season. At 1.5 the best real showcase (base 363) scored
# 908 fresh and 817 a week later, both S; at 1.10 it scores 762 then 686, so S
# lasts exactly one season and staying there means adding cards.
#
# 1.20 was tried first and is NOT enough — it still lands 719 at age 1, above the
# 700 S line. The curve is steep here, hence the precise value.
#
# Recency was deliberately NOT touched: the Collection Pack exists for collectors,
# and cutting old-card value would work against it. This dial does the job on its
# own without devaluing anything anyone owns.
#
# Trade-off, stated plainly: a typical 3-set stack is +105%, just under this cap,
# so a 4th set now adds almost nothing. Diminishing returns is the intent of
# having a cap at all, but if the 4-set diamond route should feel meaningfully
# better than three sets, the individual bonuses want scaling down rather than
# the cap coming further in.
SHOWCASE_MAX_SET_BONUS = 1.10
# Classification rarity ladder — how likely each accolade combination is to be
# DRAWN, relative to an undecorated card at 100. Owner's order, least to most
# rare: AP -> CH -> MVP -> AP/CH -> AP/MVP -> CH/MVP -> AP/CH/MVP.
#
# Before this, draw odds keyed on edition and player rating only, so a
# triple-crown card was exactly as likely as a plain All-Pro of the same
# edition — the pool's natural scarcity was the only thing making decorated
# cards rare, and in the collection pool that scarcity doesn't match the ladder
# (mvp_all_pro sits at 9.4% while all_pro_champion is 8.2%).
#
# Keyed by the SET of tags, not the joined string: the strings are ordered
# inconsistently ('mvp_all_pro' vs 'all_pro_champion') and matching them
# literally would silently miss combinations.
CLASSIFICATION_DRAW_WEIGHTS = {
    frozenset({'all_pro'}):                     100,
    frozenset({'champion'}):                     70,
    frozenset({'mvp'}):                          45,
    frozenset({'all_pro', 'champion'}):          25,
    frozenset({'mvp', 'all_pro'}):               14,
    frozenset({'mvp', 'champion'}):               8,
    frozenset({'mvp', 'all_pro', 'champion'}):    4,
}
CLASSIFICATION_TAGS = ('mvp', 'champion', 'all_pro')

# Rookie legacy premium — a rookie card is worth what the player BECAME.
#
# Real card collecting works this way round: a rookie card of a future great is
# the prize, precisely because nobody knew at the time. The scoring model had the
# opposite instinct (rookie = 5 points, the lowest classification, then decaying
# with age), so rookie cards meant nothing. This is applied ONLY to rookie cards —
# MVP / Champion / All-Pro keep exactly the values they already had.
#
# Counted from the player's career AFTER that rookie season, so the premium is
# genuinely "what they went on to do".
SHOWCASE_ROOKIE_LEGACY = {
    "hof": 30,        # inducted — the terminal accolade
    "mvp": 12,        # per MVP
    "all_pro": 5,     # per All-Pro season
}
SHOWCASE_ROOKIE_LEGACY_CAP = 60   # a rookie card can't outrun a full diamond MVP by much
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

# ⚠️ HOW SOON THE NEXT GAME DAY OPENS. A game day is 7 rounds on the hour, 12:00-18:00
# ET; the next day's first round is 12:00 ET, so a cross-day boundary is an 18-hour gap.
# This is the lead BEFORE that next kickoff at which the week rolls over — which is what
# publishes the next day's slate for pick-em and advances `shopDay` for the pack rotation.
#
# 1020 = 17h, i.e. 19:00 ET the evening before, roughly 15 minutes after the day's last
# game ends. It was 480 (8h), which lands at 04:00 ET on the game day itself — so the next
# slate stayed hidden for ~9 hours after the day's games finished, which is what users
# reported. ⚠️ Both this file and the engine comment described 480 as "the prior evening";
# it never was. Measured against the real schedule, 480 -> 04:00 ET, 1020 -> 19:00 ET.
#
# ⚠️ Do NOT raise this past ~1035 (18:45 ET). The lead is measured back from kickoff, and
# the day's last game starts at 18:00 ET; a round must finish inside 45 minutes because
# the intra-day rollover is 15 minutes before the next hourly round. Past that the rollover
# time lands while the final game is still being played. It is self-limiting rather than
# unsafe — the wait no-ops when its moment has already passed, so the rollover simply
# happens as soon as the slate finishes — but the intent is a real buffer, not a race.
#
# ⚠️ DST-STABLE, unlike a fixed UTC hour: the lead is subtracted from an ET-anchored
# kickoff, so 1020 is 19:00 ET in both EDT and EST.
CROSS_DAY_ROLLOVER_LEAD_MINUTES = 1020

# ⚠️ THERE IS NO `DAILY_RESET_HOUR_UTC` ANY MORE, AND REINTRODUCING ONE REOPENS A BUG.
# The shop's daily allowances (reroll costs, per-day buy limits) used to reset at a fixed
# UTC hour while the pack rotation followed the week rollover above — two boundaries for
# one "shop day". They drifted apart the moment the clocks changed: under EST the rollover
# lands at 12:00 + 5 - 17h = 00:00 UTC, exactly the old constant, so the two agreed and
# the fixed hour looked correct; under EDT the rollover is 23:00 UTC and the reset stayed
# at 00:00, leaving a ONE-HOUR WINDOW each game day, 19:00-20:00 ET, where the new day's
# packs were on sale beside yesterday's reroll prices. Reported by a user in exactly those
# terms.
#
# The boundary is now DERIVED from the lead above by `shop_repository._dailyResetBoundary`,
# so both halves of the shop refresh at one instant and move together if the lead moves.
# The old note here said a fixed UTC hour cannot track an ET-anchored schedule and
# concluded that the hour needed slack; the right conclusion was to stop using an hour.

# ─── GM Mode ────────────────────────────────────────────────────────────────────

# RETIRED (plan step 7). The binding fan votes are gone — the GM brain decides
# roster moves and gmTurnover decides coach changes. Kept as an empty set so any
# stray reader degrades to "no vote types" rather than an AttributeError.
GM_VOTE_TYPES: set = set()

# Cost per vote (Floobits)
# ── Discord name submissions (/name) ──────────────────────────────────────────
# Suggested names wait in `name_submissions` for admin approval; only Discord-LINKED
# users may submit. The cap is per user and counts only PENDING rows, so approving or
# rejecting frees a slot back up — it throttles a flood without punishing a regular
# contributor whose suggestions keep getting used.
NAME_SUBMISSION_PENDING_CAP = 10
NAME_SUBMISSION_MIN_LENGTH = 2
NAME_SUBMISSION_MAX_LENGTH = 60

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
# Points needed to make the BALLOT. Lowered 10 -> 6 (owner, 2026-08-02): being on
# the ballot only means fans get to consider you, and the approval floor is the
# real filter. A tight pre-filter just shrinks the electorate's choices, which is
# the opposite of what a fan vote wants.
AWARD_HOF_BALLOT_PREFILTER = 6
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

# ─── Glitch Cards (docs/GLITCH_CARDS.md) ─────────────────────────────────────
# A card marked during a Criticality. Each week it rolls ONCE for an extra payout on
# top of whatever it already does. It never degrades the printed effect and is never
# taken away — the locked no-wipe constraint names collections as never at risk.
# ─── Holding a go-ahead touchdown (Game._isTdDrainMode) ─────────────────────
# Scoring is not the goal late in a one-score game; scoring LAST is. An offense at the
# goal line, down 4-8 with under a minute, used to hurry — measured at 1st-and-goal from
# the 3 down 5 with 0:55, it took a 12-second huddle and handed the opponent ~45 seconds
# plus timeouts for a winning kick. `_isFgDrainMode` had covered the same idea for a
# deficit of 0-3 all along; this is the touchdown band it never reached.
#
# Both numbers are safety rails, not flavour: draining when you might NOT score is how a
# won game gets lost.
TD_DRAIN_MIN_SECONDS = 25   # below this there is no room to drain AND still snap the ball
TD_DRAIN_MAX_YARDS = 5      # close enough that the score is near-certain, not hoped for

# How close the offense must be before the DEFENSE treats a touchdown as the expected end
# of the drive and starts stopping the clock (Game._leadIsAboutToEvaporate). Wider than
# TD_DRAIN_MAX_YARDS on purpose: the offense only drains once a score is near-certain, but
# a defense that waits for that same certainty has already lost the clock it was trying to
# save. This is a threat, not a bet.
LEAD_THREAT_TD_YARDS = 10

GLITCH_CARDS_ENABLED = True

# Trigger base, by the on-card player's position on the attention ladder. Chosen over an
# event-led design (much lower bases, events doing the work) because 89% of player-weeks
# contain NO anomaly event at all — a low base would leave a glitched card dormant most
# weeks at current volumes, and the event rate for a larger user base is unknowable from
# the one league that exists. This degrades gracefully if events stay rare.
# 'awakened' keeps a real base deliberately: awakened players fire a power on only 37% of
# their weeks, LESS often than glitching, so keying the card solely to power use would
# make awakening quieten the card rather than upgrade it.
# ⚠️ RAISED after live testing showed the bonus almost never paying. Two things compound
# that the original numbers ignored:
#   1. 85% of players have NO anomaly row at all and default to 'stable', so most glitched
#      cards sat on the FLOOR rather than spread across the ladder;
#   2. a trigger only pays if the card itself produced something that week (the surge
#      scales the card's own output), and the FP power bar gates ~30% of weeks — so the
#      effective rate was base x 0.70.
# At the old 5% floor that was 3.5%, a median wait of TWENTY WEEKS to see one payout. The
# ladder still orders the odds; the floor is simply no longer a punishment.
# ⚠️ RAISED AGAIN (owner, 2026-08-07: "needs to trigger more"). Measured before: a blended
# 20.8% a week, i.e. a glitched card sat dormant for nearly FIVE weeks at a time. The lift
# has to come from the BOTTOM of the ladder, not the top: 85% of players are 'stable', so
# that one number sets the realized rate almost by itself, while the top is boxed in by the
# cap (rampant already reaches 0.83 of a 0.90 cap during a live Criticality — see
# GLITCH_DIAL_SHARE). Raising the floor to 0.28 takes the blended rate to ~31%, about once
# every three weeks.
# The cost is honest: the ladder's spread compresses from 0.16-0.46 to 0.28-0.46, so WHERE a
# player sits matters less than it did. That is the trade for the common case not being
# dormant, and it is the ceiling — not the design — that forces it.
GLITCH_TRIGGER_BASE = {
    'stable':   0.28,
    'stirring': 0.35,
    'erratic':  0.41,
    'rampant':  0.46,
    'awakened': 0.43,
    'cleansed': 0.28,
}

# Each anomaly event the player fired THIS WEEK raises the chance, escalating with the
# level of the anomaly. Stacks per event. A week where something actually happened roughly
# doubles the chance (rampant 35% -> 69%).
GLITCH_EVENT_BOOST = {
    'micro':       0.15,   # cosmetic flicker, generic
    'personality': 0.25,   # glitch keyed to who they are
    'signature':   0.40,   # an actual L4 power, real mechanical effect
}
GLITCH_TRIGGER_CAP = 0.90

# The instability dial (anomalyManager.getCriticalityMultiplier) already lifts a glitched
# card INDIRECTLY — a hot league fires more events. But only from ~37% to ~45%, so the
# event people spent a season building toward barely shows. Applying the dial to the base
# at FULL strength overcorrects the other way: both terms rise together, pinning a rampant
# card at the cap through a whole Criticality. This fraction splits the difference —
# a live Criticality moves a rampant card 35% -> ~59% instead of 90%.
# Lowered 0.30 -> 0.20 when the bases were raised. The two multiply: at a 0.46 rampant
# base a 0.30 share reached 1.01 during a live Criticality and clamped to the 0.90 cap,
# which is the exact pinning this fraction exists to prevent — a card that is reliably on
# is not wild magic. At 0.20 a Criticality takes rampant to 0.83, still a visible lift.
GLITCH_DIAL_SHARE = 0.20

# Magnitude, rolled on a trigger. Multiplies the CARD'S OWN output, so a surge scales with
# whatever it is attached to rather than being a flat FP number that trivialises metallic
# and vanishes on diamond. (weight, multiplier)
# Rebalanced upward with the trigger rate (owner, 2026-08-07: rewards "slightly better").
# EV moves 1.367x -> 1.603x of the card's own output. Weight shifts from the flicker tier
# into cascade/runaway as well as the multipliers rising, so the improvement lands on the
# MEMORABLE outcomes rather than making the small one less small — a glitch should be worth
# noticing when it hits, which is what a rare, cultivated card is for.
GLITCH_SURGE_TABLE = [
    ('flicker', 34, 0.40),
    ('surge',   34, 1.10),
    ('cascade', 23, 2.60),
    ('runaway',  9, 5.50),
]

# An FP surge is a FIXED amount; an FPx surge multiplies the whole lineup, so it grows with
# the rest of the hand. At the ~250 lineup the ladder is anchored to an undamped FPx surge
# is actually slightly WEAKER (0.88x) — the imbalance only appears in rich hands, reaching
# 1.59x at 450. 0.80 holds parity through a typical hand and clips only the top end.
# A deeper cut (0.55) was tried and halves FPx everywhere, fixing a problem that does not
# exist at normal lineup sizes.
GLITCH_FPX_DAMP = 0.80

# What a surge pays per 1.0 of multiplier when the card itself produced NOTHING that week.
# Without this a trigger on a gated-out card pays zero, which is indistinguishable from no
# trigger at all — the reported symptom was "I see the glitch line but never a score". A
# glitch is supposed to be something happening TO the card, so it should not be silently
# cancelled by the card having a quiet week. Deliberately modest: the surge still scales
# the card's own output when there IS output, and this is only the fallback.
GLITCH_SURGE_FLOOR_FP = 11.0

# How many surges a glitch survives before it fades and the card goes back to normal
# (owner, 2026-08-17). A glitch was PERMANENT — `user_cards.glitched` is a boolean nothing
# ever cleared — so a Criticality's marks accumulated forever. Measured on production after
# ONE season: 3 Criticalities (weeks 9, 14, 27), 48 glitched cards across 22 users, and 9
# users already holding three apiece. Over five seasons a regular would be carrying fifteen.
#
# ⚠️ COUNTED IN TRIGGERS, NOT WEEKS, so the lifespan is tied to value actually received: a
# card that never surges keeps its glitch rather than expiring having given nothing, and a
# hot card burns out fastest. At the ~0.28-0.46 trigger bases above, three surges is roughly
# eight or nine weeks of being fielded — a window inside a season rather than a ratchet
# across careers.
#
# ⚠️ The trigger is consumed WHERE THE WEEK IS BANKED, never in the calculator. The
# calculator re-runs on every projection and every page load, and its RNG is deliberately
# stable per (user, season, week, card) so a week's result never moves — counting there
# would burn a glitch's whole life on one week of refreshes.
GLITCH_MAX_TRIGGERS = 3

# ─── Darts (bust format) — hoop hunting and dead drives ─────────────────────────
# How often the offense throws at a sideline hoop when a hoop is the ONLY score that
# does not bust (remaining need below a field goal, so a TD is held up short and a FG is
# refused). Coach-scaled (owner, 2026-08-17): an aggressive coach hunts it, a cautious one
# plays field position and waits for a better spot, so the same position produces different
# football from different clubs. Aggressiveness runs 60-100 around a neutral 80, giving
# 0.20 at the cautious end, 0.55 neutral, 0.90 at the aggressive end.
#
# ⚠️ It applies on EVERY down including the last, which inverts the standing final-down
# guard on purpose — that guard exists because a hoop consumes the down without gaining
# yards, and under a target there is no scoring play it could be forfeiting.
# How deep into opponent territory counts as "losing the ball here costs little" when a
# busting field goal is refused on a final down (owner, 2026-08-23). Inside this, go for
# it — a failed try hands over poor field position anyway, and a hoop can still land the
# exact remainder. Outside it, punt.
DARTS_GO_FOR_IT_YARDS = 40.0

DARTS_HOOP_HUNT_BASE = 0.55
DARTS_HOOP_HUNT_AGGR_SPAN = 0.35

# ⚠️ THE MIDFIELD HOOP IS USE-IT-OR-LOSE-IT (owner, 2026-08-17): it is only reachable while
# APPROACHING the 50, and once the line of scrimmage crosses it that pair is behind the
# offense and gone for the drive. Driving forward is normally pure progress; here it
# destroys one of the two scoring options a team needing 1-2 points has. So within
# `DARTS_HOOP_CLOSING_YARDS` of the crossing the shot gets up to `_LAST_CHANCE_LIFT` added
# to the coach-scaled chance, ramping as the window shuts — an aggressive coach becomes
# near-certain and even a cautious one usually takes the last look.
#
# The END-ZONE pair needs no equivalent: it OPENS as the offense advances rather than
# closing, so there is never a last chance at it.
DARTS_HOOP_CLOSING_YARDS = 6.0
DARTS_HOOP_LAST_CHANCE_LIFT = 0.40

# ⚠️ A HOOP THE DRIVE CANNOT AFFORD TO LOSE IS SHOT, NOT WEIGHED (owner report, 2026-08-24:
# teams needing a single point were driving straight past the midfield goal).
#
# Declining a pair is normally fine — a shot costs a down and no yards, and the END-ZONE
# pair is always still ahead, so a team needing 1 with everything unused has two more
# chances and is right to keep driving. It stops being fine when the hoops that remain
# REACHABLE after this one can no longer cover the need: then driving on forfeits the only
# path the drive had. Measured over 300 games, of 26 snaps where a team needing 2 or fewer
# drove past the midfield pair, **12 were left unable to cover their need** — that is the
# half that is a mistake, and the other 14 are ordinary football.
#
# ⚠️ IT ALSO COVERS A CLOSING SHOT THAT SIMPLY WINS THE GAME (owner, 2026-08-24: needing one
# point, the midfield goals are the nearest score and driving past them risks the ball for
# nothing). That case is DOMINATED rather than merely risky, because crossing the pair loses
# it either way: declining loses it for nothing, shooting loses it only after a ~71% chance
# of ending the match, and a miss is an incompletion — the down is spent, the ball is kept,
# and the end-zone pair is still ahead. Measured over 400 games, drives that passed up an
# in-range midfield hoop needing 2 points or fewer went on to score AT ALL 11 times out of
# 22, so "there are chances left" was buying a coin flip with a 71% shot in hand.
#
# ⚠️ CLOSING pairs only, in both cases. The END-ZONE pair is not lost by driving on, so
# declining it costs a down rather than the chance, and forcing it would erase the coach dial
# across the whole red zone.
#
# Sits at the same height as `SIDELINE_GOAL_DESPERATION_CHANCE` (0.92), which is the
# standard game's "this point is needed to tie or win" rate; the reasoning is identical.
DARTS_HOOP_LOADBEARING_CHANCE = 0.92


# ⚠️ APPROACHING THE MIDFIELD HOOP, A DISCIPLINED SIDE STOPS TRYING TO GO DOWNFIELD (owner,
# 2026-08-17). It is the only scoring chance a drive can drive PAST: a chunk gain over the
# 50 is an ordinary good outcome that destroys the pair, and for a team needing 1-2 points
# that is one of only two ways left to score. So the deep and long tiers are damped, the
# controlled ones lifted, and the pass works the sideline the hoops stand on.
#
# Scaled by `_dartsHoopApproach`, which blends the COACH seeing it (`clockManagement`, the
# attribute the engine already uses for situational reads) with the TEAM holding the
# discipline to run short when a big play is there (`collectiveDiscipline`) — then by how
# little ROOM is left. Beyond the horizon there is no conflict at all: advancing IS what the
# offense wants, so the term goes to zero and normal football is played.
DARTS_APPROACH_HORIZON_YARDS = 25.0
DARTS_APPROACH_CONTROL_BIAS = 1.9      # run + short pass, at full discipline
DARTS_APPROACH_DOWNFIELD_DAMP = 0.25   # long + deep, at full discipline

# Run bias while LEADING on a darts drive that can no longer score (both hoop pairs spent,
# need under a field goal). The drive is worth nothing but clock, and if time expires the
# higher score wins — so a leader drains it. Runs keep the clock moving; an incompletion
# stops it and hands the time back. Not applied when trailing: that team wants the drive
# over so it can restock its hoops on the next possession.
DARTS_DEAD_DRIVE_RUN_BIAS = 2.5

# ⚠️ A DEAD DARTS DRIVE AT THE GOAL LINE KNEELS IT OUT (owner, 2026-08-24). Both hoop pairs
# are spent and the remaining need is under a field goal, so nothing this possession does
# can score — and because a would-bust touchdown is held up short, the offense cannot even
# cross the goal line. Every snap from there is PURE DOWNSIDE: it cannot gain a point, it
# can lose yards, and it can lose the ball on a fumble or a pick. A kneel gives up nothing
# the drive still had (the down is going anyway), removes that risk, drains the play clock,
# and hands the opponent the ball on their own doorstep.
#
# Inside this many yards there is nothing left to gain — `_holdUpShortCap` caps a carrier at
# `yardsToEndzone - 1`, so from the 3 the whole remaining prize is two yards of pin. Beyond
# it the offense plays on and works closer first, which is the "as close as possible" half.
DARTS_KNEEL_OUT_YARDS = 3

# ⚠️ THERE IS A POINT WHERE A TEAM STOPS TRYING TO LAND ON THE TARGET AND JUST ACCUMULATES
# POINTS, because the clock is going to decide it and the higher score wins (owner,
# 2026-08-24). Every darts read is deliberately blind to the opponent — what matters is
# distance to X, and a team leading 17-3 needs a hoop as badly as anyone — but that is only
# true while landing on X is still achievable. Once it is not, the blindness is the bug: it
# had teams spending their last downs on an exact landing they had no time to reach.
#
# The crossover is whether a plan that LANDS still fits, measured rather than picked:
#   * on THIS possession — the hoop shots the plan needs, plus a scoring drive. Over 3,475
#     darts possessions a scoring drive took a median 9 plays and a p25 of 7, so 7 is the
#     conservative floor (a plan needing more than that is not fitting into two snaps).
#   * or on a LATER one — a possession averaged 108 seconds, so a team needs roughly 216s
#     on the clock to expect the ball back.
# Neither fits -> the target is gone, and the decision reverts to the ordinary
# points-against-the-opponent logic every other format uses.
DARTS_PLAYS_TO_SCORE = 7
DARTS_NEXT_POSSESSION_SECS = 216


# ⚠️ A DARTS KICK THAT LANDS ON THE TARGET WINS THE GAME, SO IT IS NOT WORTH WAITING FOR
# FOURTH DOWN ONCE IT IS COMFORTABLE (owner, 2026-08-24). On an ordinary drive there is no
# rush — yards cannot bust, only scores can, so playing on improves the kick for free. That
# stops being true once the kick is already good: every further snap is a fumble, a sack or
# an interception standing between the team and a won game, and it cannot make a 96% kick
# meaningfully better.
#
# Expressed as a MAKE PROBABILITY rather than a yard line so it scales with the kicker, who
# is the one taking it. Measured against the live curve over 16 real kickers: 0.80 sits at
# roughly the opponent's 30 (a 47-yard attempt) for a median leg — inside the 30 the median
# kicker is at 0.82 or better, and by the 35 (52 yards) it has fallen to 0.69. A big-leg,
# accurate kicker earns the early kick from further out; a poor one has to get closer.
#
# On the FINAL down this does not apply — there the ordinary coach threshold governs, because
# the alternative is losing the ball rather than getting a better look at it.
DARTS_WINNING_KICK_COMFORT = 0.80



# Added trigger chance per ADDITIONAL glitched card in the same lineup (owner, 2026-08-17).
# Rewards FIELDING several at once rather than merely owning them, which is the half that
# pairs with expiry above: the stockpile is gone, so what is left to reward is assembling a
# window. Deliberately small against bases of 0.28-0.46 — at the full six-card lineup it is
# +0.25, enough to feel and not enough to reach `GLITCH_TRIGGER_CAP` on its own.
GLITCH_SWARM_STEP = 0.05


# ── League news feed ─────────────────────────────────────────────────────────
# ELO gap at which beating a club becomes an upset worth publishing. Set from the
# rating-to-win-probability curve: 120 points is roughly a 33% underdog, which is the
# point where a neutral watcher would call the result surprising rather than close.
UPSET_NEWS_ELO_GAP = 120

# ⚠️ Nothing is called an upset until the ELO has settled (owner, 2026-08-09). Every
# club's ELO REGRESSES HALFWAY TO 1500 at the season reset (`teamManager.updateEloRatings`),
# so the opening weeks of EVERY season — not just the league's first — price the whole
# league as roughly average, and a 120-point gap there is as likely to be last season's
# residue as this season's form. A quarter of the way in is where the games played
# outweigh the carried prior. 1-indexed, and the first week with a full quarter of
# results behind it, so at 28 weeks that is week 8. Gates BOTH the live UPSET badge
# (`floosball_game`) and the feed's upset story (`seasonManager._publishGameNewsInner`).
UPSET_MIN_WEEK = 8

# ── What the league news feed is FOR (owner, 2026-08-08) ────────────────────
# The feed is Cores/meta-simulation centric, not a box score. An individual player's big
# afternoon is not news here — it is on the Players page and the game board, and when it
# was in the feed it WAS the feed (measured: 48% of all rows, and with the per-category
# display cap that meant every visible row was box score).
#
# The machinery stays behind this flag rather than being deleted: `BIG_GAME_TESTS` records
# the measured p99 of this sim's player-game distribution, which is expensive to rederive
# and is the reference for any future "notable performance" surface.
BIG_GAME_NEWS_ENABLED = False

# How often the Cores speak into the feed, in week slots (a slot is one slate of games).
# Reactions are tied to results, so they land every slate; ambient banter has no
# triggering event and lands rarely enough to stay a pleasure rather than noise.
CORES_GAME_NEWS_EVERY_WEEKS = 1
CORES_AMBIENT_NEWS_EVERY_WEEKS = 3

# How many DISTINCT effects each player carries in every edition they are eligible for.
# A FLOOR, not a cap: a bucket still tops up to one template per effect where that would
# otherwise leave effects unminted (see cardManager._assignEffects).
#
# 1 reproduces the pre-2026-08-18 rule exactly. The knob exists because the two failure
# modes are opposite: a player in a THIN bucket (13 prismatic QBs against 26 effects)
# already collected ~2 cards from the top-up cycling, while a player in a DENSE one
# (43 eligible WRs against 36 holographic effects) got exactly ONE and never more.
#
# Measured against prod season 2 (749 templates today):
#   K=1  749     K=2  1,084     K=3  1,502     K=4  1,921     K=5  2,340
# The full player x effect cross-product would be 11,069 (14.8x) — rejected, it stops
# a pull being a chase.
#
# ⚠️ Templates mint ONCE PER SEASON, so a change here lands at the next season boundary.
CARD_EFFECTS_PER_PLAYER = 3

# ─── Venue-aware roster building ──────────────────────────────────────────────
# A GM knows their own stadium. Where the venue suppresses the passing game they
# should value the run (RB, and TE for its blocking) over QB and WR, and the inverse
# where passing is favored. Sign convention matches stadiumManager.phaseBias:
# +1 = run-side position, -1 = pass-side, 0 = unaffected.
VENUE_PHASE_POSITIONS = {'RB': 1, 'TE': 1, 'QB': -1, 'WR': -1, 'K': 0}

# ⚠️ DELIBERATELY MODEST. A team plays 14 home games and 14 away, so a roster fitted
# hard to one venue is paid for in the other half of the season. At 0.10 a max-bias
# venue moves RB from 0.72 to 0.79 and QB from 1.00 to 0.90 — enough to flip a close
# call between two comparable players, never enough to invert the position hierarchy.
# This is the same "tips close calls, never dictates" bar the sentiment tilt is held to.
VENUE_POSITION_WEIGHT = 0.10


# ─── Weather at its call sites ────────────────────────────────────────────────
# The venue's own effects and the weather rolled at kickoff arrive as one dict of
# multipliers (see managers/stadiumManager.py). This flag is the master switch for
# whether any of them REACH the sim — with it off the league plays in a neutral
# world and every call site below is a no-op, which is what an A/B arm needs.
#
# ⚠️ Weather is a PRE-GAME RATING-ADJACENT LAYER, and this codebase has a measured
# rule for those: rating-multiplier -> win-probability transfer is 1.619, i.e. a
# +/-10% roster-wide multiplier is worth +/-4.5 wins a season. A weather layer that
# looks like a few percent can be decisive. Measure with a forced-intensity arm
# before tuning.
# ⚠️ OFF FOR THIS SEASON (owner, 2026-08-30). Weather and the venues it reads from are
# built and tested but are not shipping yet. The flag returns from `_resolveWeather` BEFORE
# any roll, so with it off the game consumes no extra randomness and plays exactly as it
# does on main — it is a real no-op, not an approximate one.
WEATHER_ENABLED = False

# ⚠️ WEATHER IS SYMMETRIC (owner, 2026-08-19): a wet ball is wet for everyone. No
# key is ever applied to one side only, so nothing below reads home/away. The venue
# is only asymmetric in EXPOSURE — the home team plays 14 games a year in it — which
# is a fairness question handled in the authored severity bands, not here.

# How far a punt's DISTANCE key is allowed to move the gross kick, and how far the
# pre-snap key is allowed to move the huddle. Both clamp because they feed decisions
# downstream (the punt/kick tree reads distance; the clock tree reads pre-snap time),
# and an unclamped multiplier at Unreal could hand those trees a number outside
# anything they were tuned against.
WEATHER_PUNT_MIN = 0.55
WEATHER_PUNT_MAX = 1.30
WEATHER_PACE_MIN = 0.75
WEATHER_PACE_MAX = 1.45

# How hard a dark field pushes a returner into waving the punt off. ⚠️ This is the
# quiet half of `visibility`: the same darkness that hands a CARRIER yards (the
# tackler cannot see him) costs the RETURNER the chance to become one, so sight
# stays two-sided on special teams too rather than only helping the offense.
PUNT_FAIRCATCH_SIGHT_K = 0.45

# ─── Expected-points imminence (win probability) ──────────────────────────────
# ⚠️ Win probability damped EXPECTED points by 1/possessions-remaining while REALIZED
# points went undamped, so a drive in field-goal range banked ~1/24th of the points it
# was about to score and the kick banked the rest. That is the whole source of the
# kicker's inflated WPA: measured over 20 seasons, kickers ran 9.8x a QB's WPA per snap.
#
# Once a drive is in range the points are imminent rather than speculative, so EP is
# weighted by how close it is to converting instead. Only ever RAISES the weight, so
# nothing outside range changes and late-game drives (already near 1.0) are untouched.
#
# ⚠️ APPLIED TO THE CREDIT MODEL ONLY (`calculateWinProbability(forAttribution=True)`),
# never to the win probability fans see. WP is not just a readout — `isBigPlay` fires
# MOMENTUM_BIG_PLAY_BONUS, the one path from WP back into play outcomes — and applying
# this floor to the display model shifts that distribution. Unifying the two models
# means retuning the 7.0 big-play threshold to hold the big-play RATE, or accepting the
# resulting scoring move as a deliberate balance call.
#
# ⚠️ Do NOT try to size that scoring move by comparing two fresh sims: between-league
# variance is ~2.8 pts/game (two leagues with PROVABLY identical gameplay measured 36.06
# and 33.26), which is as large as the effect, and seasons within one league are not
# independent samples.
EP_IMMINENCE_MIN_FIELD_POS = 60          # opponent's 40 — the same line EP calls FG range
EP_IMMINENCE_POSITIONS = [60, 75, 90, 100]
EP_IMMINENCE_WEIGHTS = [0.45, 0.70, 0.85, 0.90]
