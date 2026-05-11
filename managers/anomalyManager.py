"""Anomaly tracker — user-attention-driven simulation-cracking layer.

Responsibilities:
  * Recompute every player's attention score weekly from engagement
    sources (equipped cards, fantasy rosters, follows, favorite-team
    fan presence). Decay 10%/week absent fresh input.
  * Soft-cap individual attention at 100; excess flows into a per-
    season league aggregate that drives the Thinning trigger.
  * Manage state-ladder transitions (stable → stirring → erratic →
    rampant → awakened). Awakened is sticky until a Reset purge.
  * Detect the Thinning when aggregate crosses the season's hidden
    threshold; tag the next 1–2 rounds for amplified anomaly rolls.
  * Fire the Reset post-Thinning: roll purge per awakened player,
    cleanse losers, scale survivors back, open suppression window.

The manager is called once per week from the season loop's
week-start hook. It writes to PlayerAttention, AnomalyState, and
LeagueAnomalyState; it never reads from in-flight game state.
Per-play anomaly rolls happen in the game sim using the state
values written here.
"""

from __future__ import annotations

import random
import logging
from datetime import datetime
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


logger = logging.getLogger("floosball.anomaly")


# ─── Tuning constants ───────────────────────────────────────────────────────

# Attention contributions per source, applied each weekly tick.
ATTENTION_PER_CARD_EQUIPPED = 10.0
ATTENTION_PER_FANTASY_ROSTER = 8.0
ATTENTION_PER_FOLLOWER = 2.0
ATTENTION_PER_FAVORITE_TEAM_FAN = 0.5

# Weekly decay multiplier applied BEFORE this week's contributions.
# 0.9 = 10% decay; attention naturally settles toward zero absent input.
ATTENTION_DECAY = 0.9

# Soft cap per player. Over-cap excess feeds the league aggregate
# instead of further boosting that one player's per-play roll.
ATTENTION_SOFT_CAP = 100.0

# State ladder thresholds. Once a player crosses the higher tier
# they advance; once they cross AWAKEN_THRESHOLD they are awakened
# and the transition is sticky (only Reset purge can undo it).
STATE_THRESHOLDS = [
    ('stable',    0.0),
    ('stirring', 10.0),
    ('erratic',  30.0),
    ('rampant',  60.0),
]
AWAKEN_THRESHOLD = 90.0

# League aggregate threshold for Thinning trigger.
# Randomized per season in this range; the chosen value is hidden.
THRESHOLD_MIN = 600
THRESHOLD_MAX = 1200

# Suppression window length (weeks) post-Reset where anomaly rate
# is floored league-wide.
SUPPRESSION_WINDOW_WEEKS = 2

# Each subsequent Thinning in the same season triggers at a reduced
# threshold so engaged leagues get multiple events.
THRESHOLD_DECAY_AFTER_THINNING = 0.75

# Thinning duration — number of rounds (weeks) the Thinning is active.
# 1 round for first Thinning, 2 rounds if the aggregate was 50%+ over
# the threshold when it fired (runaway league signal).
THINNING_DURATION_DEFAULT = 1
THINNING_DURATION_RUNAWAY = 2
THINNING_RUNAWAY_OVER_THRESHOLD = 0.5  # 50% over → 2-round Thinning

# During a Thinning round, per-play anomaly probabilities multiply.
THINNING_MULTIPLIER = 5.0


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
         player, accumulates over the season toward the Thinning).
      4. Update state ladder (stable → ... → awakened).
      5. Recompute league aggregate; (Thinning trigger detection
         lands in a follow-up commit).
    """
    session = get_session()
    try:
        _applyDecay(session, seasonNumber)
        _applyWeeklyContributions(session, seasonNumber, week)
        _enforceCapAndTrack(session, seasonNumber)
        _updateStateLadder(session, seasonNumber, week)
        _updateLeagueAggregate(session, seasonNumber, week)
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


def isThinningWeek(seasonNumber: int, week: int) -> bool:
    """Return True if the given week is currently inside a Thinning window.

    A Thinning lasts 1 or 2 consecutive rounds starting at
    ``last_thinning_week``. Outside the window, returns False.
    """
    session = get_session()
    try:
        state = session.query(LeagueAnomalyState).filter_by(season=seasonNumber).first()
        if state is None or state.last_thinning_week is None:
            return False
        start = state.last_thinning_week
        # Inspect the patch trail to figure out duration. The Thinning
        # trigger records its planned duration in the cores_patches_applied
        # list (see _triggerThinning); 1 by default.
        duration = THINNING_DURATION_DEFAULT
        for entry in (state.cores_patches_applied or []):
            if entry.get('event') == 'thinning_trigger' and entry.get('start_week') == start:
                duration = entry.get('duration', THINNING_DURATION_DEFAULT)
                break
        return start <= week < start + duration
    finally:
        session.close()


def getThinningMultiplier(seasonNumber: int, week: int) -> float:
    """Per-play anomaly probability multiplier. 1.0 normally, 5.0 during Thinning."""
    return THINNING_MULTIPLIER if isThinningWeek(seasonNumber, week) else 1.0


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

        if targetState == currentState:
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
            # Ability roll happens here. For v1 we record placeholder
            # values — the catalog roll lands in a follow-up commit.
            state.ability_tier = 'tremor'
            state.ability = 'placeholder'

        transitions += 1

    if transitions:
        logger.info(
            f"State transitions: {transitions} (incl. {awakenings} awakenings)"
        )


# ─── League aggregate + Thinning trigger ────────────────────────────────────


def _updateLeagueAggregate(session: Session, seasonNumber: int, week: int) -> None:
    """Recompute the league-wide aggregate and check Thinning threshold.

    Aggregate inputs (v1):
      * Sum of over_cap_carry across all PlayerAttention rows.
      * Background pressure that grows ~1/week over the season.
      * (Future: weighted recent anomaly count; deferred to v2.)
    """
    state = session.query(LeagueAnomalyState).filter_by(season=seasonNumber).first()
    if state is None:
        # First tick of the season — seed the row with a hidden threshold.
        threshold = random.randint(THRESHOLD_MIN, THRESHOLD_MAX)
        state = LeagueAnomalyState(
            season=seasonNumber,
            aggregate_score=0.0,
            threshold=threshold,
            thinnings_this_season=0,
            cores_patches_applied=[],
        )
        session.add(state)
        logger.info(f"Seeded LeagueAnomalyState season={seasonNumber} threshold={threshold} (hidden)")

    # Sum over-cap carry across all players.
    rows = (
        session.query(PlayerAttention.over_cap_carry)
        .filter_by(season=seasonNumber)
        .all()
    )
    overCapSum = sum(float(r[0]) for r in rows)
    backgroundPressure = float(week) * 1.0

    state.aggregate_score = overCapSum + backgroundPressure
    state.updated_at = datetime.utcnow()

    logger.debug(
        f"League aggregate: {state.aggregate_score:.1f} / threshold {state.threshold} "
        f"(over-cap sum={overCapSum:.1f}, pressure={backgroundPressure:.1f})"
    )

    # Thinning trigger detection — if aggregate has crossed the hidden
    # threshold AND we're not currently in a suppression window from a
    # recent Reset, fire the Thinning for the next round.
    if state.aggregate_score >= state.threshold:
        inSuppression = (
            state.suppression_window_ends_week is not None
            and week < state.suppression_window_ends_week
        )
        if not inSuppression:
            _triggerThinning(state, week)


def _triggerThinning(state: LeagueAnomalyState, currentWeek: int) -> None:
    """Fire a Thinning event for the upcoming round(s).

    Records the trigger event in cores_patches_applied (which doubles as
    the league's audit trail). Bumps the threshold for next time so a
    second Thinning in the same season requires fresh attention buildup.
    """
    overRatio = state.aggregate_score / max(1, state.threshold)
    duration = (
        THINNING_DURATION_RUNAWAY
        if overRatio >= (1.0 + THINNING_RUNAWAY_OVER_THRESHOLD)
        else THINNING_DURATION_DEFAULT
    )
    startWeek = currentWeek  # Thinning applies to the current/just-started round
    state.thinnings_this_season = (state.thinnings_this_season or 0) + 1
    state.last_thinning_week = startWeek
    # Reduce threshold for any subsequent Thinning in this season.
    state.threshold = max(THRESHOLD_MIN, int(state.threshold * THRESHOLD_DECAY_AFTER_THINNING))

    patches = list(state.cores_patches_applied or [])
    patches.append({
        'event': 'thinning_trigger',
        'start_week': startWeek,
        'duration': duration,
        'aggregate_at_trigger': float(state.aggregate_score),
        'over_ratio': float(overRatio),
        'thinning_number': state.thinnings_this_season,
        'fired_at': datetime.utcnow().isoformat() + 'Z',
    })
    state.cores_patches_applied = patches

    logger.warning(
        f"THINNING TRIGGERED (#{state.thinnings_this_season}, season="
        f"{state.season}): start_week={startWeek}, duration={duration} round(s), "
        f"aggregate={state.aggregate_score:.1f} (×{overRatio:.2f} threshold)"
    )
