"""Anomaly tracker — user-attention-driven simulation-criticality layer.

Responsibilities:
  * Recompute every player's attention score weekly from engagement
    sources (equipped cards, fantasy rosters, follows, favorite-team
    fan presence). Decay 10%/week absent fresh input.
  * Soft-cap individual attention at 100; excess flows into a per-
    season league aggregate that drives the Criticality trigger.
  * Manage state-ladder transitions (stable → stirring → erratic →
    rampant → awakened). Awakened is sticky until a Reset purge.
  * Detect the Criticality when aggregate crosses the season's hidden
    threshold; tag the next 1–2 rounds for amplified anomaly rolls.
  * Fire the Reset post-Criticality: roll purge per awakened player,
    cleanse losers, scale survivors back, open suppression window.

The manager is called once per week from the season loop's
week-start hook. It writes to PlayerAttention, AnomalyState, and
LeagueAnomalyState; it never reads from in-flight game state.
Per-play anomaly rolls happen in the game sim using the state
values written here.
"""

from __future__ import annotations

import os
import random
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple

from sqlalchemy.orm import Session

from database.connection import get_session
from database.models import (
    PlayerAttention,
    AnomalyState,
    LeagueAnomalyState,
    EquippedCard,
    FantasyRoster,
    FantasyRosterPlayer,
    FollowedPlayer,
    User,
    Player,
)
from logger_config import get_logger
from managers import awakenedPowers


logger = get_logger("floosball.anomaly")

# Player.position enum value (QB=1, RB=2, WR=3, TE=4, K=5 — see floosball_player.Position)
# -> catalog position string. NOTE: the enum is 1-indexed; a 0-indexed map here shifted
# every player to the NEXT position's power pool (QB drew RB powers, TE drew K powers,
# kickers drew nothing), so a player could be handed a power that never covers their
# primary situation and thus could never fire.
_POSITION_ENUM = {1: 'QB', 2: 'RB', 3: 'WR', 4: 'TE', 5: 'K'}


def getAnomalySetting(session, key, default):
    """Read an app_settings override for an anomaly knob, coerced to the default's type, with the
    constant `default` as fallback. Pass the caller's session to avoid new-session lock contention."""
    try:
        from database.models import AppSetting
        row = session.query(AppSetting).filter_by(key=key).first()
        if row is None or row.value is None:
            return default
        v = row.value
        if isinstance(default, bool):
            return str(v).lower() == 'true'
        if isinstance(default, (int, float)):
            try:
                return type(default)(v)
            except (TypeError, ValueError):
                return default
        return v  # strings (e.g. the intensity preset name) returned as-is
    except Exception:
        return default


def getAnomalyIntensityMultiplier(session):
    """Map the 'anomaly_intensity' preset to a numeric multiplier."""
    from constants import ANOMALY_INTENSITY_PRESETS
    preset = getAnomalySetting(session, 'anomaly_intensity', 'normal')
    return ANOMALY_INTENSITY_PRESETS.get(str(preset).lower(), 1.0)


def assignSignaturePower(session, player_id):
    """Assign the player's ONE career signature power at first awakening and store it on the Player.
    The power is kept for their whole career (their identity) — idempotent, so a re-awakening keeps
    the existing power. Returns the power key (or None). Caller gates on ANOMALY_AWAKENED_POWERS_ENABLED.
    """
    player = session.query(Player).filter_by(id=player_id).first()
    if player is None:
        return None
    if player.signature_power:
        return player.signature_power  # career identity already set — never re-rolled
    # Spread the catalog: roll only among the least-held eligible powers (assigned ones go to the back).
    from collections import Counter
    rows = session.query(Player.signature_power).filter(Player.signature_power.isnot(None)).all()
    usedCounts = Counter(r[0] for r in rows if r[0])
    power = awakenedPowers.assignPower(
        _POSITION_ENUM.get(player.position, ''), usedCounts=usedCounts)
    if power:
        player.signature_power = power
    return power


# ─── Tuning constants ───────────────────────────────────────────────────────

# Env-override for testing: set FLOOSBALL_ANOMALY_FAST=1 to compress
# every threshold so a fresh sim run can produce Awakenings + Criticalitys
# within a single fast-mode season. Boosts contributions, slashes
# thresholds, and raises per-play roll caps.
_ANOMALY_FAST = os.environ.get('FLOOSBALL_ANOMALY_FAST', '').lower() in ('1', 'true', 'yes')

# Attention contributions per source, applied each weekly tick.
ATTENTION_PER_CARD_EQUIPPED = 40.0 if _ANOMALY_FAST else 10.0
ATTENTION_PER_FANTASY_ROSTER = 32.0 if _ANOMALY_FAST else 8.0
ATTENTION_PER_FOLLOWER = 8.0 if _ANOMALY_FAST else 2.0
ATTENTION_PER_FAVORITE_TEAM_FAN = 2.0 if _ANOMALY_FAST else 0.5

# Weekly decay multiplier applied BEFORE this week's contributions.
# 0.9 = 10% decay; attention naturally settles toward zero absent input.
ATTENTION_DECAY = 0.95 if _ANOMALY_FAST else 0.9  # slower decay in fast mode

# Soft cap per player. Over-cap excess feeds the league aggregate
# instead of further boosting that one player's per-play roll.
ATTENTION_SOFT_CAP = 100.0

# State ladder thresholds. Once a player crosses the higher tier
# they advance; once they cross AWAKEN_THRESHOLD they are awakened
# and the transition is sticky (only Reset purge can undo it).
# Fast mode lowers these so a single locked roster + a few equipped
# cards is enough to awaken in 1-2 weeks.
if _ANOMALY_FAST:
    STATE_THRESHOLDS = [
        ('stable',    0.0),
        ('stirring',  5.0),
        ('erratic',  15.0),
        ('rampant',  30.0),
    ]
    AWAKEN_THRESHOLD = 50.0
else:
    STATE_THRESHOLDS = [
        ('stable',    0.0),
        ('stirring', 10.0),
        ('erratic',  30.0),
        ('rampant',  60.0),
    ]
    AWAKEN_THRESHOLD = 90.0

# League aggregate threshold for Criticality trigger.
# FAST mode: randomized in this low band so any sim triggers (no real users).
# PROD (non-fast): seeded from active-user engagement instead — see below.
THRESHOLD_MIN = 80 if _ANOMALY_FAST else 600
THRESHOLD_MAX = 200 if _ANOMALY_FAST else 1200

# ── Active-user threshold scaling (prod, non-fast) ──
# Attention is entirely user-generated (cards/rosters/follows/fav-team fans), so
# the buildup scales with the active population. A flat threshold is therefore
# population-blind: unreachable for a small base, trivial at scale. Instead we
# seed the per-season threshold from the active-user count, so Criticality fires
# on the CONCENTRATION of engagement, not raw volume — and the crossing week
# stays roughly constant as the game grows.
#   threshold = clamp(BASE + PER_USER * activeUsers, FLOOR, CEIL) * jitter
# "Active users" = users who logged in within the project's activity window
# (the SAME window supporterManager uses, SUPPORTER_ACTIVITY_WINDOW_DAYS) AND
# engage with players (favorite team OR
# following >=1). Recency matters: a user who set a favorite team a year ago and
# never returned generates no attention, so counting all-time registrations
# badly overstates the live population. Calibrated against the owner's chosen
# value: the current prod base (~42 active+engaged) seeds ~180 — the threshold
# hand-picked for a reliable mid-season near-miss. FLOOR sits above max
# background pressure (~32/season) so a dead league never trips on time alone
# (leagues under ~26 active all floor at 120, effectively unreachable). +-10%
# jitter keeps the exact value hidden.
THRESHOLD_BASE = 20.0
THRESHOLD_PER_ACTIVE_USER = 3.8
THRESHOLD_FLOOR = 120
THRESHOLD_CEIL = 6000
THRESHOLD_JITTER = 0.10

# Suppression window length (weeks) post-Reset where anomaly rate
# is floored league-wide.
SUPPRESSION_WINDOW_WEEKS = 2

# Threshold change applied after a Criticality fires. Held at 1.0 (no change): the old <1.0 value
# LOWERED the bar after each event, making repeats progressively EASIER — backwards for pacing a rare
# event (the aggregate already re-crosses every ~2-3 weeks). Pacing now lives in CRITICALITY_FIRE_CHANCE.
THRESHOLD_DECAY_AFTER_CRITICALITY = 1.0

# With the feature enabled, a threshold crossing does NOT automatically fire a Criticality. The
# aggregate hits the bar roughly every 2-3 weeks, so firing on every crossing yields ~7-12/season —
# far too many for a "rare league event". Instead each crossing fires with THIS probability and
# otherwise SUPPRESSES (the Cores catch it — the common near-miss beat). Tuned against a realistic-
# attention harness: 0.30 lands real prod at ~1.3 Criticalities/season (inside the target 1-2 band) with
# ~85% odds of at least one, and still leaves ~6 near-miss suppressions a season for the Cores tension.
CRITICALITY_FIRE_CHANCE = 0.30

# Criticality duration — number of rounds (weeks) the Criticality is active.
# 1 round for first Criticality, 2 rounds if the aggregate was 50%+ over
# the threshold when it fired (runaway league signal).
CRITICALITY_DURATION_DEFAULT = 1
CRITICALITY_DURATION_RUNAWAY = 2
CRITICALITY_RUNAWAY_OVER_THRESHOLD = 0.5  # 50% over → 2-round Criticality

# During a Criticality round, per-play anomaly probabilities multiply.
CRITICALITY_MULTIPLIER = 8.0 if _ANOMALY_FAST else 5.0

# ── Instability dial (P3) ─────────────────────────────────────────────────────
# While Criticality is gated off (ANOMALY_CRITICALITY_ENABLED=False) the league
# never actually fires — but the buildup is no longer silent. The per-play glitch
# multiplier (getCriticalityMultiplier) rides this dial instead of sitting flat at
# 1.0: it ramps with the aggregate's approach to threshold, so glitches grow more
# frequent as a season tenses, then drop during the post-near-miss suppression
# window. The full CRITICALITY_MULTIPLIER above is reserved for an actually-fired
# Criticality (enabled seasons only); the gated dial tops out lower.
INSTABILITY_BASELINE = 1.0           # multiplier when the league is quiet
INSTABILITY_PRECRIT_CEILING = 2.6    # max multiplier from buildup alone (gated)
INSTABILITY_RAMP_START = 0.40        # ratio below which the dial stays at baseline (matches WARNING_LOW)
INSTABILITY_SUPPRESSED = 0.45        # multiplier during a suppression window — pointedly quiet

# ── Near-miss / patch beat (P3) ───────────────────────────────────────────────
# When the aggregate crosses threshold the Cores scramble and force it back rather
# than letting the event fire — the dramatized "near-miss" tease beat.
#
# There is NO per-season cap on suppressions, gated OR enabled: the Cores catch the
# league on (almost) every crossing, so the near-miss beat stays frequent all
# season — it's the common Cores-dialogue moment. What makes a real Criticality
# RARE is the probabilistic break-through in _triggerCriticality
# (CRITICALITY_FIRE_CHANCE): most crossings suppress, only ~1-2/season fire instead.
SUPPRESSION_AGGREGATE_DAMP = 0.55    # minimum drain on a patch (knock off at least 45%)
SUPPRESSION_TARGET_RATIO = 0.30      # but always drain down to AT LEAST this fraction of threshold
                                     # — below the warning floor, so a patch visibly stabilizes even
                                     # when the aggregate has badly overshot the threshold
SUPPRESSION_THRESHOLD_BUMP = 1.10    # each patch reinforces containment: threshold ×= this

# Reset purge dodge multipliers, keyed by personality meta-awareness tier.
# Aware-tier players resist purges better — they perceive the Cores'
# intervention coming and adapt. Unaware-tier players roll full odds.
PURGE_DODGE_FULLY_AWARE = 0.5      # prophet / alien / android / ghost / fossil
PURGE_DODGE_PARTIALLY_AWARE = 0.75 # paranoid / mystic
PURGE_DODGE_UNAWARE = 1.0          # everyone else

FULLY_AWARE_PERSONALITIES = {'prophet', 'alien', 'android', 'ghost', 'fossil'}
PARTIALLY_AWARE_PERSONALITIES = {'paranoid', 'mystic'}

# Post-Reset aftermath scaling. league aggregate is multiplied by this to
# leave a partial baseline (the Cores didn't fully zero things) — high
# enough that another Criticality is plausible later, low enough to give
# room for buildup.
RESET_AGGREGATE_SCALE = 0.2

# After a Reset, surviving (non-purged) Awakened players drop to Rampant
# state and have their attention halved. Their ability is retained.
RESET_SURVIVOR_ATTENTION_SCALE = 0.5

# Post-Reset suppression window — the Cores actively dampen anomaly
# rates league-wide for this many weeks. During suppression, no Criticality
# can fire even if aggregate climbs again.
RESET_SUPPRESSION_WEEKS = 2

# Pre-Criticality warning milestones — once the league aggregate crosses
# these fractions of the threshold, the Cores narrate a warning into
# the news feed. Each milestone fires once per Criticality cycle (the
# audit trail tracks which have already fired so we don't repeat).
WARNING_LOW_THRESHOLD = 0.40   # 40% of threshold — first vague warning
WARNING_HIGH_THRESHOLD = 0.65  # 65% — pointed, escalating warning

# How many player state-transitions we NARRATE to the feed per tick. Every
# crossing is still recorded in the DB; we just broadcast the most significant
# few (highest state first) with distinct lines, so a big week does not flood
# the feed with the same handful of repeated transition lines.
MAX_TRANSITION_NEWS_PER_TICK = 3

# Per-state ominous feed lines, broadcast when a player crosses to that
# state for the first time this season. No context, no documentation —
# just a line in the feed that something is happening to that player.
STATE_TRANSITION_LINES = {
    'stirring': [
        "{player} is stirring.",
        "{player} has not been seen this way before.",
        "The field is not reading {player} correctly.",
        "Something about {player} has begun to drift.",
        "{player} is no longer where the field expects them to be.",
        "A faint irregularity has settled over {player}.",
    ],
    'erratic': [
        "{player} is erratic.",
        "Something is moving in {player} that the field can't account for.",
        "{player}'s readings have stopped resolving.",
        "{player} is slipping between states faster than the field can track.",
        "The field has stopped trying to predict {player}.",
        "Whatever {player} is doing, it was not in the rules.",
        "{player} is shedding frames the simulation can't recover.",
        "The pattern of {player} has broken and nothing has replaced it.",
    ],
    'rampant': [
        "{player} is rampant.",
        "{player} has come unfixed.",
        "Nobody can explain what is happening to {player} anymore.",
        "The simulation has stopped resisting {player}.",
        "There is no longer a version of {player} the field can hold.",
        "{player} has slipped every constraint that was meant to contain them.",
    ],
    'awakened': [
        "{player} has awakened.",
        "Something has changed about {player}.",
        "{player} is no longer entirely within the simulation.",
        "Whatever {player} was, they have evolved into something else.",
        "{player} moves now as though the rules were only ever a suggestion.",
    ],
    # Cleansing — the Cores reassert control during a Reset and scrub the
    # anomaly out of a player, returning them to the ruleset (ability lost).
    'cleansed': [
        "{player} has been cleansed.",
        "The Cores have scrubbed whatever {player} became.",
        "{player} has been returned to the rules.",
        "Whatever {player} was, it has been resolved.",
        "{player} no longer registers as an anomaly.",
        "The simulation has reclaimed {player}.",
        "{player} is contained. The field reads them cleanly again.",
    ],
}


# ─── Public API ─────────────────────────────────────────────────────────────


def weeklyTick(seasonNumber: int, week: int) -> None:
    """Run the anomaly system's weekly aggregation.

    Called from seasonManager at week start (after currentWeek has
    advanced). NOT idempotent — callers must ensure they only fire
    once per (season, week).

    Order of operations:
      1. Apply weekly decay to every player_attention row.
      2. Compute this week's attention contributions from each
         engagement source and add them in.
      3. Enforce soft cap; excess flows into over_cap_carry (per
         player, accumulates over the season toward the Criticality).
      4. Update state ladder (stable → ... → awakened).
      5. Recompute league aggregate; (Criticality trigger detection
         lands in a follow-up commit).
    """
    session = get_session()
    try:
        # Idempotency guard: this tick is NOT safe to run twice for the same
        # (season, week) — it re-adds the week's attention contributions on each
        # call. A mid-week restart re-entering the season loop would otherwise
        # double-count. Skip if we've already processed this week.
        existing = session.query(LeagueAnomalyState).filter_by(season=seasonNumber).first()
        if existing is not None and existing.last_tick_week == week:
            logger.info(f"Anomaly weekly tick skipped — season {seasonNumber}, week {week} already processed")
            return

        # If a Criticality window has just ended without a Reset, fire one
        # before this week's updates so the purge applies to current
        # attention values rather than this week's freshly-incremented
        # ones.
        _maybeFireReset(session, seasonNumber, week)
        _applyDecay(session, seasonNumber)
        _applyWeeklyContributions(session, seasonNumber, week)
        _enforceCapAndTrack(session, seasonNumber)
        _updateStateLadder(session, seasonNumber, week)
        _updateLeagueAggregate(session, seasonNumber, week)
        # Mark this week processed (the row exists now — _updateLeagueAggregate
        # seeds it on the first tick of the season).
        state = session.query(LeagueAnomalyState).filter_by(season=seasonNumber).first()
        if state is not None:
            state.last_tick_week = week
        session.commit()
        logger.info(f"Anomaly weekly tick complete — season {seasonNumber}, week {week}")
    except Exception as e:
        session.rollback()
        logger.exception(f"Anomaly weekly tick failed: {e}")
        raise
    finally:
        session.close()


def getAttentionScore(playerId: int, seasonNumber: int) -> float:
    """Read current attention score for a player. Returns 0.0 if no row."""
    session = get_session()
    try:
        row = session.query(PlayerAttention).filter_by(
            player_id=playerId, season=seasonNumber,
        ).first()
        return float(row.score) if row else 0.0
    finally:
        session.close()


def getAnomalyState(playerId: int, seasonNumber: int) -> Optional[AnomalyState]:
    """Read current anomaly state row for a player. None if no row."""
    session = get_session()
    try:
        return session.query(AnomalyState).filter_by(
            player_id=playerId, season=seasonNumber,
        ).first()
    finally:
        session.close()


def isCriticalityWeek(seasonNumber: int, week: int) -> bool:
    """Return True if the given week is currently inside a Criticality window.

    A Criticality lasts 1 or 2 consecutive rounds starting at
    ``last_thinning_week``. Outside the window, returns False.
    """
    import os as _os
    if _os.environ.get('CRITICALITY_TEST'):
        return True   # test hook: force every week to be a Criticality (exercise overdrive + event)
    from constants import ANOMALY_CRITICALITY_ENABLED
    session = get_session()
    try:
        if not getAnomalySetting(session, 'criticality_enabled', ANOMALY_CRITICALITY_ENABLED):
            return False
        state = session.query(LeagueAnomalyState).filter_by(season=seasonNumber).first()
        if state is None or state.last_thinning_week is None:
            return False
        start = state.last_thinning_week
        # Inspect the patch trail to figure out duration. The Criticality
        # trigger records its planned duration in the cores_patches_applied
        # list (see _triggerCriticality); 1 by default.
        duration = CRITICALITY_DURATION_DEFAULT
        for entry in (state.cores_patches_applied or []):
            if entry.get('event') == 'thinning_trigger' and entry.get('start_week') == start:
                duration = entry.get('duration', CRITICALITY_DURATION_DEFAULT)
                break
        return start <= week < start + duration
    finally:
        session.close()


def _sumOverCapCarry(session: Session, seasonNumber: int) -> float:
    """Sum every player's over-cap carry for the season — the live fuel behind
    the league aggregate. Shared by the weekly recompute (_updateLeagueAggregate)
    and the status read (getCriticalityStatus) so both see the same number. The
    status MUST NOT trust the stored aggregate_score alone: it's only rewritten
    on the weekly tick, so after a Criticality resolves (a Reset drains the carry
    but leaves the pre-drain aggregate persisted) the stored value stays high and
    pins the status on 'critical' until the next tick. Summing carry live keeps
    the displayed band honest between ticks."""
    rows = session.query(PlayerAttention.over_cap_carry).filter_by(season=seasonNumber).all()
    return sum(float(r[0] or 0.0) for r in rows)


def _bandRatio(state: Optional[LeagueAnomalyState]) -> float:
    """How close the league is to its hidden Criticality threshold (aggregate /
    threshold). 0 = quiet, 1.0 = at the line, >1.0 = over. Internal only — this
    number never surfaces to users; it drives the dial and the qualitative band."""
    if state is None:
        return 0.0
    return float(state.aggregate_score or 0.0) / max(1, state.threshold or 1)


def _inSuppressionWindow(state: Optional[LeagueAnomalyState], week: Optional[int]) -> bool:
    """True while a post-near-miss suppression window is still open — the Cores
    have just forced the anomaly back and the league is pointedly quiet."""
    return (state is not None
            and state.suppression_window_ends_week is not None
            and week is not None
            and week < state.suppression_window_ends_week)


def _instabilityMultiplier(state: Optional[LeagueAnomalyState], week: Optional[int]) -> float:
    """Gated per-play glitch multiplier (the 'instability dial').

    Rides the league aggregate's approach to threshold: flat at baseline while
    quiet, ramping toward INSTABILITY_PRECRIT_CEILING as the ratio climbs from
    INSTABILITY_RAMP_START to 1.0, and floored low during a suppression window
    (the post-patch lull). Always strictly below CRITICALITY_MULTIPLIER — the
    gated league tenses but never reaches a real Criticality's intensity."""
    if _inSuppressionWindow(state, week):
        return INSTABILITY_SUPPRESSED
    ratio = _bandRatio(state)
    if ratio <= INSTABILITY_RAMP_START:
        return INSTABILITY_BASELINE
    span = max(1e-6, 1.0 - INSTABILITY_RAMP_START)
    frac = min(1.0, (ratio - INSTABILITY_RAMP_START) / span)
    return INSTABILITY_BASELINE + (INSTABILITY_PRECRIT_CEILING - INSTABILITY_BASELINE) * frac


def getCriticalityMultiplier(seasonNumber: int, week: int) -> float:
    """Per-play anomaly probability multiplier.

    - Inside an actually-fired Criticality window (enabled seasons only): the
      full CRITICALITY_MULTIPLIER.
    - Otherwise: the gated instability dial, which ramps with the league
      aggregate's approach to its hidden threshold and drops during a
      post-near-miss suppression window.
    """
    if isCriticalityWeek(seasonNumber, week):
        return CRITICALITY_MULTIPLIER
    session = get_session()
    try:
        state = session.query(LeagueAnomalyState).filter_by(season=seasonNumber).first()
        return _instabilityMultiplier(state, week)
    finally:
        session.close()


# Qualitative status bands for the Cores control room (P5). NO numbers ever
# surface — the dread is in not having a gauge to game. Ordered low → high.
CRITICALITY_STATUS_BANDS = [
    ('dormant',  'Dormant',  'All readings nominal.'),
    ('stirring', 'Stirring', 'Irregularities are accumulating faster than they decay.'),
    ('unstable', 'Unstable', 'The Cores are working to hold the simulation together.'),
    ('critical', 'Critical', 'Containment is failing. The Cores cannot hold this much longer.'),
]
SUPPRESSION_STATUS = (
    'stabilizing', 'Stabilizing',
    'The Cores have forced the anomaly back. The simulation is quiet. For now.',
)


def getCriticalityStatus(seasonNumber: int, week: int) -> Dict:
    """Ominous, number-free status for the Cores control room (P5).

    Returns a qualitative band derived from how close the hidden aggregate is to
    its hidden threshold, plus suppression state. Deliberately exposes no raw
    numbers — users feel the pressure without a meter to optimize against.
    """
    if isCriticalityWeek(seasonNumber, week):
        # An actually-fired Criticality (enabled seasons) reads as full breach.
        key, label, desc = CRITICALITY_STATUS_BANDS[3]
        activeCore = getActiveCriticalityCore(seasonNumber, week)
        return {
            'status': key, 'label': label, 'description': desc,
            'inSuppression': False, 'patchesApplied': 0, 'activeCore': activeCore,
            'criticalityActive': True, 'progressPct': 100.0,
        }

    session = get_session()
    try:
        state = session.query(LeagueAnomalyState).filter_by(season=seasonNumber).first()
        # Band ratio comes from a LIVE carry sum, not the stored aggregate_score,
        # which can lag reality between weekly ticks (see _sumOverCapCarry). If
        # the stored value has drifted from the live one (the usual cause of a
        # "stuck critical" status after a Reset), self-heal it here so the glitch
        # dial and future reads recover too — a cheap, idempotent correction.
        liveAggregate = 0.0
        if state is not None:
            liveAggregate = _sumOverCapCarry(session, seasonNumber) + float(week or 0)
            if abs(float(state.aggregate_score or 0.0) - liveAggregate) > 1.0:
                state.aggregate_score = liveAggregate
                session.commit()
                # commit expires attributes; reload so the reads below (which run
                # after session.close(), on the now-detached instance) don't trip
                # a lazy refresh.
                session.refresh(state)
    finally:
        session.close()

    suppressionEntries = [
        e for e in (state.cores_patches_applied or [])
        if e.get('event') == 'suppression'
    ] if state is not None else []
    inSuppression = _inSuppressionWindow(state, week)

    ratio = liveAggregate / max(1, (state.threshold if state is not None else 1))
    # Show 'stabilizing' only while the patch has actually quieted things (ratio
    # below the warning floor). If the aggregate has already re-climbed into a
    # warning band during the suppression window, reflect that band instead —
    # otherwise the status looks stuck on 'stabilizing' while it is clearly
    # building back up.
    if inSuppression and ratio < WARNING_LOW_THRESHOLD:
        key, label, desc = SUPPRESSION_STATUS
        # Surface the Core that led the most recent patch, for the control room.
        activeCore = suppressionEntries[-1].get('core') if suppressionEntries else None
    else:
        if ratio >= 1.0:
            key, label, desc = CRITICALITY_STATUS_BANDS[3]
        elif ratio >= WARNING_HIGH_THRESHOLD:
            key, label, desc = CRITICALITY_STATUS_BANDS[2]
        elif ratio >= WARNING_LOW_THRESHOLD:
            key, label, desc = CRITICALITY_STATUS_BANDS[1]
        else:
            key, label, desc = CRITICALITY_STATUS_BANDS[0]
        activeCore = None

    return {
        'status': key, 'label': label, 'description': desc,
        'inSuppression': inSuppression,
        'patchesApplied': len(suppressionEntries),
        'activeCore': activeCore,
        'criticalityActive': False,
        # Progress toward Criticality (0-100, clamped). Flavor for the control
        # room — the raw aggregate/threshold still stay in the debug endpoint.
        'progressPct': round(min(max(ratio, 0.0), 1.0) * 100, 1),
    }


def getActiveCriticalityCore(seasonNumber: int, week: int) -> Optional[str]:
    """Return the controlling Core's key for the active Criticality, or None.

    Scans the LeagueAnomalyState's audit trail for a thinning_trigger entry
    whose [start_week, start_week + duration) span contains `week`. Returns
    the `core` field on that entry — selected once at Criticality trigger time
    via `_pickControllingCore` and pinned for the duration.

    Feature-flagged: when ANOMALY_CRITICALITY_ENABLED is False (the season-long
    tease state), this always returns None. The Layer 1/2 cosmetic glitches
    + Core news/warnings keep firing; only the math-swapping Criticality event
    is gated off until we flip the flag for the next season's payoff.
    """
    from constants import ANOMALY_CRITICALITY_ENABLED
    session = get_session()
    try:
        if not getAnomalySetting(session, 'criticality_enabled', ANOMALY_CRITICALITY_ENABLED):
            return None
        state = session.query(LeagueAnomalyState).filter_by(season=seasonNumber).first()
        if state is None:
            return None
        for entry in (state.cores_patches_applied or []):
            if entry.get('event') != 'thinning_trigger':
                continue
            start = entry.get('start_week')
            duration = entry.get('duration', CRITICALITY_DURATION_DEFAULT)
            if start is None:
                continue
            if start <= week < start + duration:
                return entry.get('core')
        return None
    finally:
        session.close()


def _pickControllingCore(state: LeagueAnomalyState) -> str:
    """Weighted-random pick from the 4 active Cores. Stenographer never
    takes control. Cores used more recently this season get less weight,
    so each Criticality tends to rotate. If a Core hasn't been used this
    season, it gets the heaviest weight."""
    from managers.coreEquations import CONTROLLING_CORES

    # Count how recently each Core has taken control. Most recent = lowest score.
    seen: Dict[str, int] = {}
    for idx, entry in enumerate(state.cores_patches_applied or []):
        if entry.get('event') != 'thinning_trigger':
            continue
        core = entry.get('core')
        if core in CONTROLLING_CORES:
            seen[core] = idx  # later index = more recent

    # Weight: never-used Cores get the highest weight; recently-used get the
    # lowest. We use position-from-end as the "recency penalty" — Cores seen
    # in the most recent slot get weight 1, never-seen get weight (n+1).
    trail = state.cores_patches_applied or []
    weights: List[Tuple[str, float]] = []
    for core in CONTROLLING_CORES:
        if core not in seen:
            weights.append((core, float(len(trail) + 2)))
        else:
            weights.append((core, float(max(1, len(trail) - seen[core]))))
    total = sum(w for _, w in weights)
    pick = random.uniform(0, total)
    running = 0.0
    for core, w in weights:
        running += w
        if pick <= running:
            return core
    return CONTROLLING_CORES[0]  # defensive fallback


# ─── Decay ──────────────────────────────────────────────────────────────────


def _applyDecay(session: Session, seasonNumber: int) -> None:
    """Multiply every existing attention score by ATTENTION_DECAY."""
    rows = session.query(PlayerAttention).filter_by(season=seasonNumber).all()
    for row in rows:
        row.score = float(row.score) * ATTENTION_DECAY
    logger.debug(f"Decayed {len(rows)} attention rows by {ATTENTION_DECAY}")


# ─── Weekly contributions ───────────────────────────────────────────────────


def _applyWeeklyContributions(session: Session, seasonNumber: int, week: int) -> None:
    """Accumulate this week's attention deltas from engagement sources.

    For each player who shows up in ANY source, add the appropriate
    contribution to their PlayerAttention.score, creating the row if
    necessary. We compute all deltas in memory first, then write.
    """
    deltas: Dict[int, float] = {}

    # ── Equipped cards this week ──
    # Scope to cards equipped for the current week. Each card targets
    # one player via card_template.player_id; grant +10 attention.
    equippedQuery = (
        session.query(EquippedCard)
        .filter_by(season=seasonNumber, week=week, locked=True)
    )
    for ec in equippedQuery.all():
        try:
            playerId = ec.user_card.card_template.player_id
        except AttributeError:
            continue
        if playerId is None:
            continue
        deltas[playerId] = deltas.get(playerId, 0.0) + ATTENTION_PER_CARD_EQUIPPED

    # ── Fantasy roster slots (locked rosters this season) ──
    rosters = session.query(FantasyRoster).filter_by(
        season=seasonNumber, is_locked=True,
    ).all()
    for r in rosters:
        for rp in r.players:
            if rp.player_id is not None:
                deltas[rp.player_id] = deltas.get(rp.player_id, 0.0) + ATTENTION_PER_FANTASY_ROSTER

    # ── Followed players ──
    follows = session.query(FollowedPlayer).all()
    for f in follows:
        deltas[f.player_id] = deltas.get(f.player_id, 0.0) + ATTENTION_PER_FOLLOWER

    # ── Favorite-team fan presence ──
    # Each user with a favorite team contributes a small drip to every
    # active player on that team. Diffuse but accumulates.
    favTeamCounts: Dict[int, int] = {}
    for u in session.query(User).filter(User.favorite_team_id.isnot(None)).all():
        favTeamCounts[u.favorite_team_id] = favTeamCounts.get(u.favorite_team_id, 0) + 1
    if favTeamCounts:
        # Find players on those teams.
        rosterPlayers = session.query(Player).filter(
            Player.team_id.in_(list(favTeamCounts.keys()))
        ).all()
        for p in rosterPlayers:
            fanCount = favTeamCounts.get(p.team_id, 0)
            if fanCount > 0:
                deltas[p.id] = deltas.get(p.id, 0.0) + (ATTENTION_PER_FAVORITE_TEAM_FAN * fanCount)

    if not deltas:
        return

    # Materialize.
    existing = {
        row.player_id: row
        for row in session.query(PlayerAttention)
        .filter_by(season=seasonNumber)
        .filter(PlayerAttention.player_id.in_(list(deltas.keys())))
        .all()
    }
    now = datetime.utcnow()
    for playerId, delta in deltas.items():
        row = existing.get(playerId)
        if row is None:
            row = PlayerAttention(
                player_id=playerId, season=seasonNumber,
                score=0.0, over_cap_carry=0.0, peak_score=0.0,
            )
            session.add(row)
            existing[playerId] = row
        row.score = float(row.score) + delta
        row.last_updated = now
    logger.debug(f"Applied weekly contributions to {len(deltas)} players")


# ─── Cap enforcement + over-cap carry ───────────────────────────────────────


def _enforceCapAndTrack(session: Session, seasonNumber: int) -> None:
    """Cap score at ATTENTION_SOFT_CAP; overflow flows into over_cap_carry.

    Also updates peak_score (high-water mark for the season).
    """
    rows = session.query(PlayerAttention).filter_by(season=seasonNumber).all()
    for row in rows:
        if row.score > ATTENTION_SOFT_CAP:
            overflow = float(row.score) - ATTENTION_SOFT_CAP
            row.score = ATTENTION_SOFT_CAP
            row.over_cap_carry = float(row.over_cap_carry) + overflow
        if row.score > float(row.peak_score):
            row.peak_score = float(row.score)


# ─── State ladder transitions ───────────────────────────────────────────────


def _scoreToState(score: float) -> str:
    """Map a raw attention score to a state-ladder label (pre-awakened)."""
    bestState = 'stable'
    for state, threshold in STATE_THRESHOLDS:
        if score >= threshold:
            bestState = state
    return bestState


# Numeric rank for forward-only state progression. State in the DB is
# the season high-water mark; per-play anomaly probability still tracks
# raw attention via the score field, so glitches naturally taper when
# attention decays. But the BADGE / TRANSITION LINE only ever advances.
_STATE_RANK = {
    'stable':    0,
    'stirring':  1,
    'erratic':   2,
    'rampant':   3,
    'awakened':  4,
    'cleansed': -1,  # post-purge sentinel; treated as terminal-down
}


def _updateStateLadder(session: Session, seasonNumber: int, week: int) -> None:
    """Advance/regress every player's anomaly state based on current score.

    Rules:
      * Awakened is sticky — once a player reaches awakened, they stay
        there even if their score later drops. Only a Reset purge can
        clear it.
      * Cleansed (post-purge) is also sticky for the rest of the season
        — these players cannot re-awaken until next season.
      * Otherwise, state tracks the score-to-state mapping each week.
      * Crossing the awaken threshold for the first time triggers an
        ability roll which is recorded in AnomalyState.
    """
    rows = session.query(PlayerAttention).filter_by(season=seasonNumber).all()
    if not rows:
        return

    # Pull state rows for the same players in one round trip.
    playerIds = [r.player_id for r in rows]
    stateRows = {
        s.player_id: s for s in
        session.query(AnomalyState)
        .filter_by(season=seasonNumber)
        .filter(AnomalyState.player_id.in_(playerIds))
        .all()
    }

    now = datetime.utcnow()
    transitions = 0
    awakenings = 0
    # Collect transition events for broadcast after the loop so we don't
    # interleave WS sends with DB iteration.
    transitionEvents: List[Tuple[int, str]] = []

    for attn in rows:
        state = stateRows.get(attn.player_id)
        currentState = state.state if state else 'stable'

        # Sticky terminal states — leave alone.
        if currentState in ('awakened', 'cleansed'):
            continue

        targetState = _scoreToState(float(attn.score))

        # Check for awakening: crossing AWAKEN_THRESHOLD for the first time.
        if float(attn.score) >= AWAKEN_THRESHOLD:
            targetState = 'awakened'

        # Forward-only progression. State stored in the DB is the
        # season high-water mark; per-play anomaly probability still
        # tracks raw attention via the score field, so glitches taper
        # naturally when attention decays. But the badge / transition
        # line only ever advances — prevents oscillation re-firing
        # ("X is rampant" should fire once per season per player,
        # not every time score crosses 60 from below).
        currentRank = _STATE_RANK.get(currentState, 0)
        targetRank = _STATE_RANK.get(targetState, 0)
        if targetRank <= currentRank:
            continue

        if state is None:
            state = AnomalyState(
                player_id=attn.player_id,
                season=seasonNumber,
                state=targetState,
            )
            session.add(state)
        else:
            state.state = targetState
        state.updated_at = now

        if targetState == 'awakened':
            state.awakened_at_week = week
            awakenings += 1
            # L4 signature abilities — gated. When the powers feature is on, assign one fixed
            # offensive ability (best offensive attribute) + defensive takeaway (position) at
            # awakening. When off, nothing is assigned (feature invisible).
            from constants import ANOMALY_AWAKENED_POWERS_ENABLED
            if getAnomalySetting(session, 'awakened_powers_enabled', ANOMALY_AWAKENED_POWERS_ENABLED):
                power = assignSignaturePower(session, attn.player_id)
                if power:
                    logger.info(f"Awakened: player {attn.player_id} signature power = {power}")

        transitions += 1
        # Only narrate transitions to non-stable states.
        if targetState in STATE_TRANSITION_LINES:
            transitionEvents.append((attn.player_id, targetState))

    if transitions:
        logger.info(
            f"State transitions: {transitions} (incl. {awakenings} awakenings)"
        )

    # Broadcast feed lines for each new transition. Done after the
    # DB writes so the session commit's atomicity isn't entangled with
    # the broadcast layer.
    if transitionEvents:
        # Narrate only the most significant few per tick (every transition is
        # still recorded in the DB above). Prefer higher states (awakened >
        # rampant > ...) and pick distinct line text so a big week does not
        # spam the feed with the same repeated transition lines.
        ranked = sorted(
            transitionEvents,
            key=lambda e: _STATE_RANK.get(e[1], 0),
            reverse=True,
        )[:MAX_TRANSITION_NEWS_PER_TICK]
        playerIds = [pid for pid, _ in ranked]
        playerNames = {
            p.id: p.name for p in
            session.query(Player).filter(Player.id.in_(playerIds)).all()
        }
        usedLines: set = set()
        for playerId, targetState in ranked:
            playerName = playerNames.get(playerId)
            if not playerName:
                continue
            pool = STATE_TRANSITION_LINES[targetState]
            fresh = [ln for ln in pool if ln not in usedLines] or pool
            template = random.choice(fresh)
            usedLines.add(template)
            line = template.format(player=playerName)
            _broadcastStateTransition(playerId, playerName, targetState, line, week,
                                       session=session, seasonNumber=seasonNumber)


def _broadcastStateTransition(playerId: int, playerName: str, state: str,
                              line: str, week: int, session: Optional[Session] = None,
                              seasonNumber: Optional[int] = None) -> None:
    """Push a state-transition flavor line through the league news channel
    and persist it so users who weren't online still see it on next load.

    Carries metadata so the frontend can render it differently from
    standard league news (no ELIMINATED tag, no team-event color).
    """
    # Persist first — if the broadcast fails the row still survives.
    if session is not None and seasonNumber is not None:
        try:
            from database.models import LeagueNewsItem
            session.add(LeagueNewsItem(
                season=seasonNumber,
                week=week,
                category='anomaly_transition',
                event_type=state,
                text=line,
                player_id=playerId,
                player_name=playerName,
                anomaly_state=state,
            ))
        except Exception as e:
            logger.debug(f"State-transition persist skipped: {e}")

    try:
        from api.game_broadcaster import broadcaster
        from api.event_models import LeagueNewsEvent
        if broadcaster is None or LeagueNewsEvent is None or not broadcaster.is_enabled():
            return
        event = LeagueNewsEvent.leagueNews(text=line)
        event['category'] = 'anomaly_transition'
        event['anomalyState'] = state
        event['playerId'] = playerId
        event['playerName'] = playerName
        event['week'] = week
        broadcaster.broadcast_sync('season', event)
    except Exception as e:
        logger.debug(f"State-transition broadcast skipped: {e}")


# ─── League aggregate + Criticality trigger ────────────────────────────────────


def _countActiveUsers(session: Session) -> int:
    """The live, engaged population: users who logged in within the project's
    activity window (SUPPORTER_ACTIVITY_WINDOW_DAYS, the same window
    supporterManager uses) AND engage with players (favorite team OR following
    >=1). Recency is the point — counting all-time registrations would include
    long-departed users who generate no attention and badly overstate the base.
    """
    from constants import SUPPORTER_ACTIVITY_WINDOW_DAYS
    cutoff = datetime.utcnow() - timedelta(days=SUPPORTER_ACTIVITY_WINDOW_DAYS)
    recent = {
        r[0] for r in session.query(User.id)
        .filter(User.last_login_at.isnot(None), User.last_login_at >= cutoff).all()
    }
    if not recent:
        return 0
    favUsers = {
        r[0] for r in session.query(User.id)
        .filter(User.favorite_team_id.isnot(None)).all()
    }
    folUsers = {r[0] for r in session.query(FollowedPlayer.user_id).distinct().all()}
    return len(recent & (favUsers | folUsers))


def _seedThreshold(session: Session) -> int:
    """Seed a season's Criticality threshold. FAST mode keeps the old low random
    band (sims trigger reliably); prod scales it with the active-user count."""
    if _ANOMALY_FAST:
        return random.randint(THRESHOLD_MIN, THRESHOLD_MAX)
    activeUsers = _countActiveUsers(session)
    raw = THRESHOLD_BASE + THRESHOLD_PER_ACTIVE_USER * activeUsers
    jittered = raw * random.uniform(1.0 - THRESHOLD_JITTER, 1.0 + THRESHOLD_JITTER)
    threshold = int(max(THRESHOLD_FLOOR, min(THRESHOLD_CEIL, round(jittered))))
    logger.info(
        f"Seeded threshold from {activeUsers} active users: "
        f"base+perUser={raw:.0f}, jittered -> {threshold} (hidden)"
    )
    return threshold


def _updateLeagueAggregate(session: Session, seasonNumber: int, week: int) -> None:
    """Recompute the league-wide aggregate and check Criticality threshold.

    Aggregate inputs (v1):
      * Sum of over_cap_carry across all PlayerAttention rows.
      * Background pressure that grows ~1/week over the season.
      * (Future: weighted recent anomaly count; deferred to v2.)
    """
    state = session.query(LeagueAnomalyState).filter_by(season=seasonNumber).first()
    if state is None:
        # First tick of the season — seed the row with a hidden threshold scaled
        # to the active-user population (see _seedThreshold).
        threshold = _seedThreshold(session)
        state = LeagueAnomalyState(
            season=seasonNumber,
            aggregate_score=0.0,
            threshold=threshold,
            thinnings_this_season=0,
            cores_patches_applied=[],
        )
        session.add(state)
        logger.info(f"Seeded LeagueAnomalyState season={seasonNumber} threshold={threshold} (hidden)")

    # Sum over-cap carry across all players (shared with the status read).
    overCapSum = _sumOverCapCarry(session, seasonNumber)
    backgroundPressure = float(week) * 1.0

    state.aggregate_score = overCapSum + backgroundPressure
    state.updated_at = datetime.utcnow()

    logger.debug(
        f"League aggregate: {state.aggregate_score:.1f} / threshold {state.threshold} "
        f"(over-cap sum={overCapSum:.1f}, pressure={backgroundPressure:.1f})"
    )

    # Pre-Criticality warnings. Cores notice when the aggregate climbs past
    # certain fractions of the threshold and fire flavor-only news
    # entries. Each milestone fires once per Criticality cycle — the audit
    # trail tracks which we've already broadcast.
    _maybeFireWarning(state, session=session, week=week)

    # Criticality trigger detection — if aggregate has crossed the hidden
    # threshold AND we're not already inside an active Criticality window
    # AND we're not in a post-Reset suppression window, fire the
    # Criticality for the next round.
    if state.aggregate_score >= state.threshold:
        inSuppression = (
            state.suppression_window_ends_week is not None
            and week < state.suppression_window_ends_week
        )
        # Block re-triggering inside an active Criticality window. The
        # Reset that follows clears last_thinning_week's "active" status
        # by setting last_reset_week, so subsequent crossings only fire
        # once the previous Criticality has been resolved.
        inActiveCriticality = False
        if state.last_thinning_week is not None:
            # Pull duration from the audit trail.
            duration = CRITICALITY_DURATION_DEFAULT
            for entry in (state.cores_patches_applied or []):
                if (entry.get('event') == 'thinning_trigger'
                        and entry.get('start_week') == state.last_thinning_week):
                    duration = entry.get('duration', CRITICALITY_DURATION_DEFAULT)
            criticalityEndWeek = state.last_thinning_week + duration - 1
            # Active window: between trigger and next-week Reset.
            if week <= criticalityEndWeek:
                inActiveCriticality = True
            elif state.last_reset_week is None or state.last_reset_week < criticalityEndWeek + 1:
                # Criticality window has ended but Reset hasn't yet fired.
                inActiveCriticality = True
        if not inSuppression and not inActiveCriticality:
            _triggerCriticality(state, week, session=session)


# ─── Pre-Criticality warnings ──────────────────────────────────────────────────


def _maybeFireWarning(state: LeagueAnomalyState,
                      session: Optional[Session] = None,
                      week: Optional[int] = None) -> None:
    """Broadcast a Cores-attributed warning when aggregate crosses a
    milestone fraction of threshold. Each milestone fires once per
    Criticality cycle (audit trail tracks which we've already done)."""
    ratio = float(state.aggregate_score) / max(1, state.threshold)
    if ratio < WARNING_LOW_THRESHOLD:
        return  # Below the warning floor — no Cores attention yet.

    # Determine which milestone applies: high takes priority if crossed.
    if ratio >= WARNING_HIGH_THRESHOLD:
        milestone = 'warning_high'
    else:
        milestone = 'warning_low'

    # Find the start of the current Criticality cycle. Cores warnings reset
    # each time a Reset fires — so any warning fired since the last reset
    # counts as "this cycle."
    cycleStart = state.last_reset_week if state.last_reset_week is not None else 0
    alreadyFired = False
    for entry in (state.cores_patches_applied or []):
        if entry.get('event') != 'cores_warning':
            continue
        if entry.get('week', 0) < cycleStart:
            continue
        if entry.get('milestone') == milestone:
            alreadyFired = True
            break
        # If we already fired warning_low this cycle, only escalate to
        # warning_high (don't re-fire warning_low after).
        if milestone == 'warning_low' and entry.get('milestone') == 'warning_high':
            alreadyFired = True
            break

    if alreadyFired:
        return

    # Compose the Cores narration. warning_high prefers a multi-Core exchange;
    # warning_low has no exchange pool and falls back to a single line.
    entries = []
    try:
        from managers.coresManager import entriesForEvent
        entries = entriesForEvent(milestone)
    except Exception as e:
        logger.warning(f"coresManager unavailable for warning news: {e}")
    news = entries[0] if entries else None  # representative entry for the audit trail

    patches = list(state.cores_patches_applied or [])
    patches.append({
        'event': 'cores_warning',
        'milestone': milestone,
        'aggregate_at_warning': float(state.aggregate_score),
        'ratio': float(ratio),
        'fired_at': datetime.utcnow().isoformat() + 'Z',
        'news': news,
    })
    state.cores_patches_applied = patches

    logger.info(
        f"Cores {milestone} fired (season={state.season}, "
        f"aggregate={state.aggregate_score:.1f}, ratio={ratio:.2f}, "
        f"{len(entries)} turn(s))"
    )
    _broadcastCoreEntries(entries, session=session, seasonNumber=state.season, week=week)


# ─── Reset + purge ──────────────────────────────────────────────────────────


def _maybeFireReset(session: Session, seasonNumber: int, week: int) -> None:
    """If a Criticality window just ended and no Reset has been issued for
    it yet, fire the Reset now."""
    state = session.query(LeagueAnomalyState).filter_by(season=seasonNumber).first()
    if state is None or state.last_thinning_week is None:
        return
    # Pull the Criticality duration from the audit trail.
    duration = CRITICALITY_DURATION_DEFAULT
    for entry in (state.cores_patches_applied or []):
        if entry.get('event') == 'thinning_trigger' and entry.get('start_week') == state.last_thinning_week:
            duration = entry.get('duration', CRITICALITY_DURATION_DEFAULT)
    criticalityEndWeek = state.last_thinning_week + duration - 1
    # Reset fires on the week immediately after the Criticality window ends.
    if week <= criticalityEndWeek:
        return  # Criticality still active
    _fireReset(session, state, week)
    # The Criticality is fully resolved (event fired + Reset issued) — clear the active flag so this
    # Reset fires exactly ONCE. (The old dedup keyed off last_reset_week, but _suppressCriticality
    # re-arms that field on every later suppression; with suppressions now uncapped a post-fire
    # suppression would un-dedup the Reset and make it re-fire every week for the rest of the season.)
    state.last_thinning_week = None


def _fireReset(session: Session, state: LeagueAnomalyState, week: int) -> None:
    """Roll purges for every Awakened player, apply aftermath suppression.

    Per-player purge probability:
        (attention - AWAKEN_THRESHOLD) / 100 × personalityDodge
    Awakened players at exactly 90 attention have 0% purge chance even
    without dodge. Players who climbed to 200+ before the Reset are
    overwhelmingly likely to be cleansed.
    """
    awakeneds = (
        session.query(AnomalyState)
        .filter_by(season=state.season, state='awakened')
        .all()
    )
    if not awakeneds:
        # No Awakened players to purge — just record the Reset event.
        _recordResetEvent(state, week, purged=[], survivors=[], session=session)
        return

    # Pull attention scores in one round trip.
    attentionRows = (
        session.query(PlayerAttention)
        .filter_by(season=state.season)
        .filter(PlayerAttention.player_id.in_([s.player_id for s in awakeneds]))
        .all()
    )
    attentionMap = {r.player_id: r for r in attentionRows}

    # Pull personality info for dodge calculation. Look up via Player
    # → PlayerAttributes (if your schema has personality there, otherwise
    # skip dodge and use full odds).
    purged: List[int] = []
    survivors: List[int] = []

    for st in awakeneds:
        attn = attentionMap.get(st.player_id)
        attention = float(attn.score) if attn else 0.0
        personality = _getPlayerPersonality(session, st.player_id)
        dodge = _purgeDodgeFor(personality)

        rawProb = max(0.0, (attention - AWAKEN_THRESHOLD) / 100.0)
        purgeProb = min(1.0, rawProb * dodge)

        if random.random() < purgeProb:
            # Purged: state → cleansed, ability lost, attention zeroed.
            st.state = 'cleansed'
            st.ability = None
            st.ability_tier = None
            st.last_purged_season = state.season
            if attn:
                attn.score = 0.0
                attn.over_cap_carry = 0.0
            purged.append(st.player_id)
        else:
            # Survived: drop to Rampant, attention halved, keep ability.
            st.state = 'rampant'
            if attn:
                attn.score = float(attn.score) * RESET_SURVIVOR_ATTENTION_SCALE
                attn.over_cap_carry = float(attn.over_cap_carry) * RESET_SURVIVOR_ATTENTION_SCALE
            survivors.append(st.player_id)

    # Drain the WHOLE league's over-cap carry — not just the awakened players
    # purged above. The aggregate is rebuilt from over_cap_carry every tick
    # (_updateLeagueAggregate, which runs right after the Reset), so leaving the
    # untouched rampant/erratic/stirring carry intact snaps the aggregate right
    # back to critical the same week the Cores "regain control". The suppression
    # path drains all carry for exactly this reason; the Reset must too.
    allAttn = session.query(PlayerAttention).filter_by(season=state.season).all()
    for row in allAttn:
        if row.over_cap_carry:
            row.over_cap_carry = float(row.over_cap_carry) * RESET_AGGREGATE_SCALE

    # League aftermath: scale aggregate, set suppression window. (The aggregate is
    # recomputed from the now-drained carry below; this keeps it low pre-recompute.)
    state.aggregate_score = float(state.aggregate_score) * RESET_AGGREGATE_SCALE
    state.last_reset_week = week
    state.suppression_window_ends_week = week + RESET_SUPPRESSION_WEEKS

    # Announce each cleansed player to the league feed so fans see who the Cores
    # purged (mirrors the climb transitions; the feed renders these as CLEANSED).
    if purged:
        names = {
            p.id: p.name for p in
            session.query(Player).filter(Player.id.in_(purged)).all()
        }
        usedLines: set = set()
        for pid in purged:
            nm = names.get(pid)
            if not nm:
                continue
            pool = STATE_TRANSITION_LINES.get('cleansed') or ["{player} has been cleansed."]
            fresh = [ln for ln in pool if ln not in usedLines] or pool
            template = random.choice(fresh)
            usedLines.add(template)
            _broadcastStateTransition(pid, nm, 'cleansed', template.format(player=nm), week,
                                      session=session, seasonNumber=state.season)

    _recordResetEvent(state, week, purged=purged, survivors=survivors, session=session)

    logger.warning(
        f"RESET FIRED (season={state.season}, week={week}): "
        f"{len(purged)} purged, {len(survivors)} survived; "
        f"aggregate scaled to {state.aggregate_score:.1f}; "
        f"suppression until week {state.suppression_window_ends_week}"
    )


def _recordResetEvent(state: LeagueAnomalyState, week: int,
                      purged: List[int], survivors: List[int],
                      session: Optional[Session] = None) -> None:
    """Append a Reset record to the league audit trail and broadcast
    the Cores' attributed news entry."""
    news = None
    try:
        from managers.coresManager import newsEntryFor
        news = newsEntryFor('reset')
    except Exception as e:
        logger.warning(f"coresManager unavailable for reset news: {e}")

    patches = list(state.cores_patches_applied or [])
    patches.append({
        'event': 'reset',
        'week': week,
        'purged_player_ids': list(purged),
        'survivor_player_ids': list(survivors),
        'fired_at': datetime.utcnow().isoformat() + 'Z',
        'news': news,
    })
    state.cores_patches_applied = patches
    _broadcastCoreNews(news, session=session, seasonNumber=state.season, week=week)


def _purgeDodgeFor(personality: Optional[str]) -> float:
    """Return the purge-probability multiplier for a given personality."""
    if personality is None:
        return PURGE_DODGE_UNAWARE
    p = personality.lower()
    if p in FULLY_AWARE_PERSONALITIES:
        return PURGE_DODGE_FULLY_AWARE
    if p in PARTIALLY_AWARE_PERSONALITIES:
        return PURGE_DODGE_PARTIALLY_AWARE
    return PURGE_DODGE_UNAWARE


def _getPlayerPersonality(session: Session, playerId: int) -> Optional[str]:
    """Look up a player's personality string. Returns None if unavailable."""
    try:
        from database.models import PlayerAttributes
        row = session.query(PlayerAttributes).filter_by(player_id=playerId).first()
        if row is None:
            return None
        return getattr(row, 'personality', None)
    except Exception:
        return None


def _triggerCriticality(state: LeagueAnomalyState, currentWeek: int,
                     session: Optional[Session] = None) -> None:
    """Fire a Criticality event for the upcoming round(s).

    Records the trigger event in cores_patches_applied (which doubles as
    the league's audit trail). Bumps the threshold for next time so a
    second Criticality in the same season requires fresh attention buildup.
    Broadcasts a Cores-attributed news entry to the league feed.

    Feature-flagged: when ANOMALY_CRITICALITY_ENABLED is False, the event does
    not fire — instead the crossing is dramatized as a near-miss/patch beat
    (_suppressCriticality): the Cores scramble and force the aggregate back. The
    league still never reaches a real Criticality, but the buildup is no longer
    silent. This is the season-long tease.
    """
    from constants import ANOMALY_CRITICALITY_ENABLED
    if not getAnomalySetting(session, 'criticality_enabled', ANOMALY_CRITICALITY_ENABLED):
        _suppressCriticality(state, currentWeek, session=session)
        return
    # Even with the feature ON, a crossing MOSTLY suppresses (the Cores catch it — the common near-miss
    # beat, and the Cores dialogue it surfaces). Only occasionally does it break through and a
    # Criticality actually FIRES, keeping it the rare ~1-2/season event it's meant to be (the aggregate
    # re-crosses every ~2-3 weeks, so firing every time would mean ~7-12/season).
    if random.random() >= CRITICALITY_FIRE_CHANCE:
        _suppressCriticality(state, currentWeek, session=session)
        return
    overRatio = state.aggregate_score / max(1, state.threshold)
    duration = (
        CRITICALITY_DURATION_RUNAWAY
        if overRatio >= (1.0 + CRITICALITY_RUNAWAY_OVER_THRESHOLD)
        else CRITICALITY_DURATION_DEFAULT
    )
    startWeek = currentWeek  # Criticality applies to the current/just-started round
    state.thinnings_this_season = (state.thinnings_this_season or 0) + 1
    state.last_thinning_week = startWeek
    # Reduce threshold for any subsequent Criticality in this season. Floor at
    # THRESHOLD_FLOOR (not THRESHOLD_MIN) so it stays consistent with the
    # active-user-scaled seeding rather than snapping back up to the old band.
    state.threshold = max(THRESHOLD_FLOOR, int(state.threshold * THRESHOLD_DECAY_AFTER_CRITICALITY))

    # Compose the Cores' narration (multi-Core exchange) and record a
    # representative entry on the audit trail. Event type 'criticality' matches
    # the coresManager pools (the old 'thinning' key had no pool).
    entries = []
    try:
        from managers.coresManager import entriesForEvent
        entries = entriesForEvent('criticality')
    except Exception as e:
        logger.warning(f"coresManager unavailable for criticality news: {e}")
    news = entries[0] if entries else None

    # Pick the Core that controls the equation for this Criticality. Weighted
    # toward Cores that haven't been active this season so the four active
    # Cores rotate naturally. Pinned for the Criticality duration via the
    # audit-trail entry below; `getActiveCriticalityCore` reads it back out.
    controllingCore = _pickControllingCore(state)

    patches = list(state.cores_patches_applied or [])
    patches.append({
        'event': 'thinning_trigger',
        'start_week': startWeek,
        'duration': duration,
        'aggregate_at_trigger': float(state.aggregate_score),
        'over_ratio': float(overRatio),
        'thinning_number': state.thinnings_this_season,
        'fired_at': datetime.utcnow().isoformat() + 'Z',
        'news': news,
        'core': controllingCore,
    })
    state.cores_patches_applied = patches

    logger.warning(
        f"THE CRITICALITY FIRED (#{state.thinnings_this_season}, season="
        f"{state.season}): start_week={startWeek}, duration={duration} round(s), "
        f"core={controllingCore}, aggregate={state.aggregate_score:.1f} "
        f"(×{overRatio:.2f} threshold)"
    )

    # Broadcast to the league news feed.
    _broadcastCoreEntries(entries, session=session, seasonNumber=state.season, week=currentWeek)


def _suppressCriticality(state: LeagueAnomalyState, currentWeek: int,
                         session: Optional[Session] = None) -> None:
    """Gated near-miss: the aggregate crossed threshold but Criticality is off.

    Rather than firing, the Cores scramble and force the buildup back — a
    dramatized "we caught it this time" patch beat. Capped per season; once the
    cap is reached the Cores can no longer push it back and the league sits
    pinned at critical instability (the dial stays high) for the rest of the
    year, though the event still cannot fire while gated.

    Each patch:
      * records a `suppression` audit entry (controlling Core + week),
      * opens a suppression window (instability dial goes quiet),
      * drains the accumulated over-cap fuel so the aggregate must genuinely
        re-climb (the weekly recompute reads from over_cap_carry),
      * reinforces the threshold a little (each save is harder to need again),
      * re-arms the Cores' warning cycle for the next buildup,
      * broadcasts a Cores-attributed patch line to the league feed.
    """
    priorPatches = sum(
        1 for e in (state.cores_patches_applied or [])
        if e.get('event') == 'suppression'
    )
    # No cap while Criticality is gated — the Cores keep catching it all season,
    # so the league never gets stuck pinned at 100%. The cap only bites once the
    # real event is enabled.
    from constants import ANOMALY_CRITICALITY_ENABLED
    patchNumber = priorPatches + 1
    # The Core that mechanically led the patch (recorded for getCriticalityStatus
    # / the control room). The narration below is a multi-Core scramble exchange
    # and is intentionally decoupled from this — the conversation reads better
    # than a single attributed line.
    controllingCore = _pickControllingCore(state)

    entries = []
    try:
        from managers.coresManager import entriesForEvent
        entries = entriesForEvent('suppression')
    except Exception as e:
        logger.warning(f"coresManager unavailable for suppression news: {e}")
    news = entries[0] if entries else None

    overRatio = float(state.aggregate_score) / max(1, state.threshold)
    patches = list(state.cores_patches_applied or [])
    patches.append({
        'event': 'suppression',
        'patch_number': patchNumber,
        'week': currentWeek,
        'aggregate_at_patch': float(state.aggregate_score),
        'over_ratio': overRatio,
        'core': controllingCore,
        'fired_at': datetime.utcnow().isoformat() + 'Z',
        'news': news,
    })
    state.cores_patches_applied = patches

    # Open the quiet window and reinforce containment.
    state.suppression_window_ends_week = currentWeek + SUPPRESSION_WINDOW_WEEKS
    state.threshold = int(state.threshold * SUPPRESSION_THRESHOLD_BUMP)
    state.last_reset_week = currentWeek  # warnings re-arm for the next buildup
    state.updated_at = datetime.utcnow()

    # Drain the accumulated over-cap fuel so the weekly recompute genuinely
    # restarts lower (the aggregate is rebuilt from over_cap_carry every tick, so
    # damping the stored aggregate alone wouldn't survive next week). Target an
    # ABSOLUTE level — SUPPRESSION_TARGET_RATIO * threshold, below the warning
    # floor — rather than a flat fraction. A flat fraction leaves a badly-
    # overshot aggregate still critical, so the patch never visibly stabilizes;
    # the absolute target guarantees the climb actually restarts low. Never
    # drains LESS than SUPPRESSION_AGGREGATE_DAMP.
    backgroundPressure = float(currentWeek)
    currentOverCap = max(0.0, float(state.aggregate_score) - backgroundPressure)
    targetOverCap = max(0.0, SUPPRESSION_TARGET_RATIO * state.threshold - backgroundPressure)
    dampFactor = SUPPRESSION_AGGREGATE_DAMP
    if currentOverCap > 0:
        dampFactor = max(0.0, min(SUPPRESSION_AGGREGATE_DAMP, targetOverCap / currentOverCap))
    drainedFrom = 0
    if session is not None:
        carryRows = session.query(PlayerAttention).filter_by(season=state.season).all()
        for row in carryRows:
            if row.over_cap_carry:
                row.over_cap_carry = float(row.over_cap_carry) * dampFactor
                drainedFrom += 1
    # Reflect the drain immediately for any in-tick reads (recomputed next week).
    state.aggregate_score = backgroundPressure + currentOverCap * dampFactor

    logger.warning(
        f"CRITICALITY SUPPRESSED (patch #{patchNumber}, "
        f"season={state.season}, week={currentWeek}): core={controllingCore}, "
        f"aggregate forced to {state.aggregate_score:.1f}, threshold reinforced to "
        f"{state.threshold}, quiet until week {state.suppression_window_ends_week} "
        f"(drained {drainedFrom} carry rows)."
    )

    _broadcastCoreEntries(entries, session=session, seasonNumber=state.season, week=currentWeek)


def _broadcastCoreNews(news: Optional[Dict], session: Optional[Session] = None,
                       seasonNumber: Optional[int] = None,
                       week: Optional[int] = None) -> None:
    """Push a Cores news entry through the existing league-news channel
    and persist it so refresh / reconnect users still see it.
    """
    if not news:
        return

    if session is not None and seasonNumber is not None and week is not None:
        try:
            from database.models import LeagueNewsItem
            session.add(LeagueNewsItem(
                season=seasonNumber,
                week=week,
                category='cores',
                event_type=news.get('eventType'),
                text=news.get('text', ''),
                core=news.get('core'),
                core_display_name=news.get('coreDisplayName'),
                exchange_id=news.get('exchangeId'),
                turn_index=news.get('turnIndex'),
                turn_count=news.get('turnCount'),
            ))
        except Exception as e:
            logger.debug(f"Cores news persist skipped: {e}")

    try:
        from api.game_broadcaster import broadcaster
        from api.event_models import LeagueNewsEvent
        if broadcaster is None or LeagueNewsEvent is None:
            return
        if not broadcaster.is_enabled():
            return
        event = LeagueNewsEvent.leagueNews(text=news.get('text', ''))
        # Carry the extra Cores metadata so the frontend can render the
        # entry with a Core-specific accent / icon.
        event['core'] = news.get('core')
        event['coreDisplayName'] = news.get('coreDisplayName')
        event['category'] = 'cores'
        event['eventType'] = news.get('eventType')
        # Exchange threading (P4) — present only when this entry is one turn of
        # a multi-Core conversation. Lets the feed group the turns together.
        for k in ('exchangeId', 'turnIndex', 'turnCount'):
            if news.get(k) is not None:
                event[k] = news.get(k)
        broadcaster.broadcast_sync('season', event)
    except Exception as e:
        logger.debug(f"Cores news broadcast skipped: {e}")


def _broadcastCoreEntries(entries: Optional[List[Dict]], session: Optional[Session] = None,
                          seasonNumber: Optional[int] = None,
                          week: Optional[int] = None) -> None:
    """Broadcast a list of Cores feed entries in order — a solo line (length 1)
    or every turn of a multi-Core exchange. Each turn is persisted + broadcast
    via _broadcastCoreNews, preserving its exchange threading fields."""
    for entry in (entries or []):
        _broadcastCoreNews(entry, session=session, seasonNumber=seasonNumber, week=week)
