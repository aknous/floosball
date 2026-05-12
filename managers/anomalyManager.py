"""Anomaly tracker — user-attention-driven simulation-cracking layer.

Responsibilities:
  * Recompute every player's attention score weekly from engagement
    sources (equipped cards, fantasy rosters, follows, favorite-team
    fan presence). Decay 10%/week absent fresh input.
  * Soft-cap individual attention at 100; excess flows into a per-
    season league aggregate that drives the Cracking trigger.
  * Manage state-ladder transitions (stable → stirring → erratic →
    rampant → awakened). Awakened is sticky until a Reset purge.
  * Detect the Cracking when aggregate crosses the season's hidden
    threshold; tag the next 1–2 rounds for amplified anomaly rolls.
  * Fire the Reset post-Cracking: roll purge per awakened player,
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
from logger_config import get_logger


logger = get_logger("floosball.anomaly")


# ─── Tuning constants ───────────────────────────────────────────────────────

# Env-override for testing: set FLOOSBALL_ANOMALY_FAST=1 to compress
# every threshold so a fresh sim run can produce Awakenings + Crackings
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

# League aggregate threshold for Cracking trigger.
# Randomized per season in this range; the chosen value is hidden.
# Fast mode pulls it way down so any decently-engaged season triggers.
THRESHOLD_MIN = 80 if _ANOMALY_FAST else 600
THRESHOLD_MAX = 200 if _ANOMALY_FAST else 1200

# Suppression window length (weeks) post-Reset where anomaly rate
# is floored league-wide.
SUPPRESSION_WINDOW_WEEKS = 2

# Each subsequent Cracking in the same season triggers at a reduced
# threshold so engaged leagues get multiple events.
THRESHOLD_DECAY_AFTER_CRACKING = 0.75

# Cracking duration — number of rounds (weeks) the Cracking is active.
# 1 round for first Cracking, 2 rounds if the aggregate was 50%+ over
# the threshold when it fired (runaway league signal).
CRACKING_DURATION_DEFAULT = 1
CRACKING_DURATION_RUNAWAY = 2
CRACKING_RUNAWAY_OVER_THRESHOLD = 0.5  # 50% over → 2-round Cracking

# During a Cracking round, per-play anomaly probabilities multiply.
CRACKING_MULTIPLIER = 8.0 if _ANOMALY_FAST else 5.0

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
# enough that another Cracking is plausible later, low enough to give
# room for buildup.
RESET_AGGREGATE_SCALE = 0.2

# After a Reset, surviving (non-purged) Awakened players drop to Rampant
# state and have their attention halved. Their ability is retained.
RESET_SURVIVOR_ATTENTION_SCALE = 0.5

# Post-Reset suppression window — the Cores actively dampen anomaly
# rates league-wide for this many weeks. During suppression, no Cracking
# can fire even if aggregate climbs again.
RESET_SUPPRESSION_WEEKS = 2

# Pre-Cracking warning milestones — once the league aggregate crosses
# these fractions of the threshold, the Cores narrate a warning into
# the news feed. Each milestone fires once per Cracking cycle (the
# audit trail tracks which have already fired so we don't repeat).
WARNING_LOW_THRESHOLD = 0.40   # 40% of threshold — first vague warning
WARNING_HIGH_THRESHOLD = 0.65  # 65% — pointed, escalating warning

# Per-state ominous feed lines, broadcast when a player crosses to that
# state for the first time this season. No context, no documentation —
# just a line in the feed that something is happening to that player.
STATE_TRANSITION_LINES = {
    'stirring': [
        "{player} is stirring.",
        "{player} has not been seen this way before.",
        "The field is not reading {player} correctly.",
    ],
    'erratic': [
        "{player} is erratic.",
        "Something is moving in {player} that the field can't account for.",
        "{player}'s readings have stopped resolving.",
    ],
    'rampant': [
        "{player} is rampant.",
        "{player} has come unfixed.",
        "No one is offering an explanation for {player} anymore.",
    ],
    'awakened': [
        "{player} has awakened.",
        "Something has changed about {player}.",
        "{player} is no longer entirely within the simulation.",
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
         player, accumulates over the season toward the Cracking).
      4. Update state ladder (stable → ... → awakened).
      5. Recompute league aggregate; (Cracking trigger detection
         lands in a follow-up commit).
    """
    session = get_session()
    try:
        # If a Cracking window has just ended without a Reset, fire one
        # before this week's updates so the purge applies to current
        # attention values rather than this week's freshly-incremented
        # ones.
        _maybeFireReset(session, seasonNumber, week)
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


def isCrackingWeek(seasonNumber: int, week: int) -> bool:
    """Return True if the given week is currently inside a Cracking window.

    A Cracking lasts 1 or 2 consecutive rounds starting at
    ``last_thinning_week``. Outside the window, returns False.
    """
    session = get_session()
    try:
        state = session.query(LeagueAnomalyState).filter_by(season=seasonNumber).first()
        if state is None or state.last_thinning_week is None:
            return False
        start = state.last_thinning_week
        # Inspect the patch trail to figure out duration. The Cracking
        # trigger records its planned duration in the cores_patches_applied
        # list (see _triggerCracking); 1 by default.
        duration = CRACKING_DURATION_DEFAULT
        for entry in (state.cores_patches_applied or []):
            if entry.get('event') == 'thinning_trigger' and entry.get('start_week') == start:
                duration = entry.get('duration', CRACKING_DURATION_DEFAULT)
                break
        return start <= week < start + duration
    finally:
        session.close()


def getCrackingMultiplier(seasonNumber: int, week: int) -> float:
    """Per-play anomaly probability multiplier. 1.0 normally, 5.0 during Cracking."""
    return CRACKING_MULTIPLIER if isCrackingWeek(seasonNumber, week) else 1.0


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
            # Ability roll happens here. For v1 we record placeholder
            # values — the catalog roll lands in a follow-up commit.
            state.ability_tier = 'tremor'
            state.ability = 'placeholder'

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
        playerIds = [pid for pid, _ in transitionEvents]
        playerNames = {
            p.id: p.name for p in
            session.query(Player).filter(Player.id.in_(playerIds)).all()
        }
        for playerId, targetState in transitionEvents:
            playerName = playerNames.get(playerId)
            if not playerName:
                continue
            line = random.choice(STATE_TRANSITION_LINES[targetState]).format(player=playerName)
            _broadcastStateTransition(playerId, playerName, targetState, line, week)


def _broadcastStateTransition(playerId: int, playerName: str, state: str,
                              line: str, week: int) -> None:
    """Push a state-transition flavor line through the league news channel.

    Carries metadata so the frontend can render it differently from
    standard league news (no ELIMINATED tag, no team-event color).
    """
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


# ─── League aggregate + Cracking trigger ────────────────────────────────────


def _updateLeagueAggregate(session: Session, seasonNumber: int, week: int) -> None:
    """Recompute the league-wide aggregate and check Cracking threshold.

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

    # Pre-Cracking warnings. Cores notice when the aggregate climbs past
    # certain fractions of the threshold and fire flavor-only news
    # entries. Each milestone fires once per Cracking cycle — the audit
    # trail tracks which we've already broadcast.
    _maybeFireWarning(state)

    # Cracking trigger detection — if aggregate has crossed the hidden
    # threshold AND we're not already inside an active Cracking window
    # AND we're not in a post-Reset suppression window, fire the
    # Cracking for the next round.
    if state.aggregate_score >= state.threshold:
        inSuppression = (
            state.suppression_window_ends_week is not None
            and week < state.suppression_window_ends_week
        )
        # Block re-triggering inside an active Cracking window. The
        # Reset that follows clears last_thinning_week's "active" status
        # by setting last_reset_week, so subsequent crossings only fire
        # once the previous Cracking has been resolved.
        inActiveCracking = False
        if state.last_thinning_week is not None:
            # Pull duration from the audit trail.
            duration = CRACKING_DURATION_DEFAULT
            for entry in (state.cores_patches_applied or []):
                if (entry.get('event') == 'thinning_trigger'
                        and entry.get('start_week') == state.last_thinning_week):
                    duration = entry.get('duration', CRACKING_DURATION_DEFAULT)
            crackingEndWeek = state.last_thinning_week + duration - 1
            # Active window: between trigger and next-week Reset.
            if week <= crackingEndWeek:
                inActiveCracking = True
            elif state.last_reset_week is None or state.last_reset_week < crackingEndWeek + 1:
                # Cracking window has ended but Reset hasn't yet fired.
                inActiveCracking = True
        if not inSuppression and not inActiveCracking:
            _triggerCracking(state, week)


# ─── Pre-Cracking warnings ──────────────────────────────────────────────────


def _maybeFireWarning(state: LeagueAnomalyState) -> None:
    """Broadcast a Cores-attributed warning when aggregate crosses a
    milestone fraction of threshold. Each milestone fires once per
    Cracking cycle (audit trail tracks which we've already done)."""
    ratio = float(state.aggregate_score) / max(1, state.threshold)
    if ratio < WARNING_LOW_THRESHOLD:
        return  # Below the warning floor — no Cores attention yet.

    # Determine which milestone applies: high takes priority if crossed.
    if ratio >= WARNING_HIGH_THRESHOLD:
        milestone = 'warning_high'
    else:
        milestone = 'warning_low'

    # Find the start of the current Cracking cycle. Cores warnings reset
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

    # Compose the Cores news entry. Broadcast + record on audit trail.
    news = None
    try:
        from managers.coresManager import newsEntryFor
        news = newsEntryFor(milestone)
    except Exception as e:
        logger.warning(f"coresManager unavailable for warning news: {e}")

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
        f"aggregate={state.aggregate_score:.1f}, ratio={ratio:.2f})"
    )
    _broadcastCoreNews(news)


# ─── Reset + purge ──────────────────────────────────────────────────────────


def _maybeFireReset(session: Session, seasonNumber: int, week: int) -> None:
    """If a Cracking window just ended and no Reset has been issued for
    it yet, fire the Reset now."""
    state = session.query(LeagueAnomalyState).filter_by(season=seasonNumber).first()
    if state is None or state.last_thinning_week is None:
        return
    # Pull the Cracking duration from the audit trail.
    duration = CRACKING_DURATION_DEFAULT
    for entry in (state.cores_patches_applied or []):
        if entry.get('event') == 'thinning_trigger' and entry.get('start_week') == state.last_thinning_week:
            duration = entry.get('duration', CRACKING_DURATION_DEFAULT)
    crackingEndWeek = state.last_thinning_week + duration - 1
    # Reset fires on the week immediately after the Cracking window ends.
    if week <= crackingEndWeek:
        return  # Cracking still active
    if state.last_reset_week == crackingEndWeek + 1:
        return  # Already handled this Cracking
    _fireReset(session, state, week)


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
        _recordResetEvent(state, week, purged=[], survivors=[])
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

    # League aftermath: scale aggregate, set suppression window.
    state.aggregate_score = float(state.aggregate_score) * RESET_AGGREGATE_SCALE
    state.last_reset_week = week
    state.suppression_window_ends_week = week + RESET_SUPPRESSION_WEEKS

    _recordResetEvent(state, week, purged=purged, survivors=survivors)

    logger.warning(
        f"RESET FIRED (season={state.season}, week={week}): "
        f"{len(purged)} purged, {len(survivors)} survived; "
        f"aggregate scaled to {state.aggregate_score:.1f}; "
        f"suppression until week {state.suppression_window_ends_week}"
    )


def _recordResetEvent(state: LeagueAnomalyState, week: int,
                      purged: List[int], survivors: List[int]) -> None:
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
    _broadcastCoreNews(news)


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


def _triggerCracking(state: LeagueAnomalyState, currentWeek: int) -> None:
    """Fire a Cracking event for the upcoming round(s).

    Records the trigger event in cores_patches_applied (which doubles as
    the league's audit trail). Bumps the threshold for next time so a
    second Cracking in the same season requires fresh attention buildup.
    Broadcasts a Cores-attributed news entry to the league feed.
    """
    overRatio = state.aggregate_score / max(1, state.threshold)
    duration = (
        CRACKING_DURATION_RUNAWAY
        if overRatio >= (1.0 + CRACKING_RUNAWAY_OVER_THRESHOLD)
        else CRACKING_DURATION_DEFAULT
    )
    startWeek = currentWeek  # Cracking applies to the current/just-started round
    state.thinnings_this_season = (state.thinnings_this_season or 0) + 1
    state.last_thinning_week = startWeek
    # Reduce threshold for any subsequent Cracking in this season.
    state.threshold = max(THRESHOLD_MIN, int(state.threshold * THRESHOLD_DECAY_AFTER_CRACKING))

    # Compose the Cores' news entry and record it on the audit trail.
    news = None
    try:
        from managers.coresManager import newsEntryFor
        news = newsEntryFor('thinning')
    except Exception as e:
        logger.warning(f"coresManager unavailable for thinning news: {e}")

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
    })
    state.cores_patches_applied = patches

    logger.warning(
        f"THE CRACKING FIRED (#{state.thinnings_this_season}, season="
        f"{state.season}): start_week={startWeek}, duration={duration} round(s), "
        f"aggregate={state.aggregate_score:.1f} (×{overRatio:.2f} threshold)"
    )

    # Broadcast to the league news feed.
    _broadcastCoreNews(news)


def _broadcastCoreNews(news: Optional[Dict]) -> None:
    """Push a Cores news entry through the existing league-news channel."""
    if not news:
        return
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
        broadcaster.broadcast_sync('season', event)
    except Exception as e:
        logger.debug(f"Cores news broadcast skipped: {e}")
