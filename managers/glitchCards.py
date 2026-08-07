"""Glitch cards — the extra payout a card carries after a Criticality.

Full design: `docs/GLITCH_CARDS.md`.

A glitched card is a REAL card that caught something during a Criticality. It keeps
everything it already did; some weeks it also pays an unpredictable bonus on top. The load
bearing rule is that a glitch **never takes anything away** — people cultivate cards and
lineups, and degrading what someone built punishes them for having built it. It also keeps
the feature inside the locked constraint in `CRITICALITY_METAGAME_PLAN.md`, which names
collections as never at risk.

Two halves:

  ACQUISITION  one equipped card per user is marked when a Criticality fires
  OPERATION    each week a marked card rolls once; base from the on-card player's ladder
               position, raised by the anomaly events that player actually fired

The roll resolves at WEEK END and cannot resolve earlier — the chance depends on events
that fire during the week's games. That matches how chance cards already behave
(`cardEffects` refuses to resolve while `ctx.gamesActive`).
"""
from __future__ import annotations

import hashlib
import random as _random
from typing import Dict, Optional, Tuple

from constants import (GLITCH_CARDS_ENABLED, GLITCH_TRIGGER_BASE, GLITCH_EVENT_BOOST,
                       GLITCH_TRIGGER_CAP, GLITCH_DIAL_SHARE, GLITCH_SURGE_TABLE,
                       GLITCH_FPX_DAMP, GLITCH_SURGE_FLOOR_FP)
from logger_config import get_logger

logger = get_logger("floosball.glitchCards")


def triggerChance(playerState: Optional[str], eventCounts: Optional[Dict[str, int]] = None,
                  instabilityDial: float = 1.0) -> float:
    """Odds a glitched card's surge fires this week.

        base(ladder state) scaled by a FRACTION of the instability dial,
        plus a boost per anomaly event the player fired, escalating with its level.

    The dial is applied at `GLITCH_DIAL_SHARE` rather than in full because it ALSO drives
    how many events fire — applying it at full strength to both terms compounds and pins a
    rampant card at the cap through an entire Criticality.
    """
    base = GLITCH_TRIGGER_BASE.get(playerState or 'stable', GLITCH_TRIGGER_BASE['stable'])
    # dial 1.0 is quiet and leaves the base untouched; 5.0 is a live Criticality.
    scaled = base * (1.0 + (float(instabilityDial) - 1.0) * GLITCH_DIAL_SHARE)
    boost = sum(GLITCH_EVENT_BOOST.get(layer, 0.0) * count
                for layer, count in (eventCounts or {}).items())
    return max(0.0, min(GLITCH_TRIGGER_CAP, scaled + boost))


def _rng(userId: int, season: int, week: int, userCardId: int) -> _random.Random:
    """Deterministic per (user, season, week, card), mirroring the chance-card RNG so a
    week's result is stable no matter how many times it is recomputed."""
    seed = f"glitch-{userId}-{season}-{week}-{userCardId}"
    return _random.Random(int(hashlib.sha256(seed.encode()).hexdigest(), 16) % (2 ** 32))


def rollSurge(userId: int, season: int, week: int, userCardId: int,
              chance: float) -> Tuple[bool, Optional[str], float]:
    """Resolve a glitched card's week. Returns (triggered, outcomeName, multiplier).

    Two draws off the same stream: whether it fires, then how big.
    """
    rng = _rng(userId, season, week, userCardId)
    if rng.random() >= chance:
        return (False, None, 0.0)
    total = sum(w for _, w, _ in GLITCH_SURGE_TABLE)
    pick = rng.uniform(0, total)
    upto = 0.0
    for name, weight, mult in GLITCH_SURGE_TABLE:
        upto += weight
        if pick <= upto:
            return (True, name, mult)
    name, _, mult = GLITCH_SURGE_TABLE[-1]
    return (True, name, mult)


def surgePayout(multiplier: float, cardFp: float, cardMultBonus: float) -> Tuple[float, float]:
    """The extra FP / FPx delta a surge adds, given what the card itself produced.

    Returns (extraFp, extraMultDelta) — ADDITIVE, never replacing.

    A card that produced nothing this week still pays a FLOOR. An earlier version returned
    zero here, on the reasoning that the surge scales the card's own output so there was
    nothing to amplify. That is tidy and wrong in practice: the FP power bar gates ~30% of
    weeks, so roughly a third of triggers paid nothing and were indistinguishable from no
    trigger at all. The reported symptom was seeing the glitch line every week and never a
    score. A glitch happens TO the card; a quiet week should not silently cancel it.

    FPx is damped (`GLITCH_FPX_DAMP`) because an FP surge is a fixed amount while an FPx
    surge multiplies the whole lineup, so it grows with the rest of the hand — a strong
    hand should not also make the glitch stronger.
    """
    delta = max(0.0, (cardMultBonus or 0.0) - 1.0)
    extraMult = round(delta * multiplier * GLITCH_FPX_DAMP, 3)
    scaled = max(0.0, cardFp) * multiplier
    if scaled <= 0 and extraMult <= 0:
        # Nothing to scale — pay the floor so the trigger is visible.
        return (round(GLITCH_SURGE_FLOOR_FP * multiplier, 2), 0.0)
    return (round(scaled, 2), extraMult)


def anomalyContextFor(playerIds, season: int, week: int) -> Dict[int, Tuple[str, Dict[str, int]]]:
    """{playerId: (ladderState, {layer: count})} for a set of players, in ONE round trip.

    Batched on purpose. The card calculator runs per user per week, and a per-player query
    for state plus another for events would be two round trips per glitched card. Both
    sources already exist — `AnomalyState` holds the ladder position and `AnomalyEvent`
    persists every fired anomaly with player, season, week and layer — so this needs no new
    instrumentation, only care about how often it is asked.

    Opens its own session: `CardCalcContext` carries none, and threading one through every
    call site buys nothing here.
    """
    ids = [p for p in (playerIds or []) if p]
    if not ids:
        return {}
    out: Dict[int, Tuple[str, Dict[str, int]]] = {p: ('stable', {}) for p in ids}
    try:
        from database.connection import get_session
        from database.models import AnomalyEvent, AnomalyState
    except Exception:
        return out
    session = None
    try:
        session = get_session()
        for pid, state in session.query(AnomalyState.player_id, AnomalyState.state).filter(
                AnomalyState.player_id.in_(ids), AnomalyState.season == season):
            out[pid] = (state or 'stable', out[pid][1])
        for pid, layer in session.query(AnomalyEvent.player_id, AnomalyEvent.layer).filter(
                AnomalyEvent.player_id.in_(ids), AnomalyEvent.season == season,
                AnomalyEvent.week == week):
            counts = out[pid][1]
            counts[layer] = counts.get(layer, 0) + 1
    except Exception as e:
        logger.debug("glitch: anomaly context lookup failed: %s", e)
    finally:
        if session is not None:
            try:
                session.close()
            except Exception:
                pass
    return out


def markCardsForCriticality(session, season: int, week: int) -> int:
    """ACQUISITION. Mark one equipped card per user when a Criticality fires.

    Everyone with cards equipped is affected — a Criticality hits the whole league and
    exposure is the only qualification. Returns how many cards were marked.

    ⚠️ Deliberately gameable (owner call): equipping exactly ONE card during a Criticality
    guarantees the glitch lands on it, where a full lineup gives any card a 1-in-6 chance.
    Stripping a lineup costs five cards' output for the week, so it is a real trade rather
    than a free exploit.

    Idempotent per (season, week): re-running will not mark a second card, so a replayed or
    resumed week cannot double-dip.
    """
    if not GLITCH_CARDS_ENABLED:
        return 0
    try:
        from database.models import EquippedCard, UserCard
    except Exception:
        return 0
    try:
        already = {uid for (uid,) in session.query(UserCard.user_id)
                   .filter(UserCard.glitched_season == season,
                           UserCard.glitched_week == week).distinct()}

        # ⚠️ Look BACK for the most recent equipped snapshot, do not demand one for this
        # exact week. The anomaly weekly tick (which fires the Criticality) runs at
        # seasonManager:667, but equipped cards are only carried forward into the new week
        # at :850 — so at the moment a Criticality fires, this week's rows do not exist yet
        # and an exact-week query marks nothing at all. That is not a hypothetical: a live
        # sim fired a Criticality and glitched zero cards.
        #
        # Looking back also matches what "equipped during the Criticality" means to a user:
        # whatever lineup they had standing. It mirrors the same lookback
        # _carryForwardEquippedCards already does for exactly this reason.
        rows = []
        for lookback in range(week, 0, -1):
            rows = (session.query(EquippedCard)
                    .filter(EquippedCard.season == season,
                            EquippedCard.week == lookback).all())
            if rows:
                if lookback != week:
                    logger.info(f"glitch: no equipped rows at S{season}W{week} yet, "
                                f"using the W{lookback} lineup")
                break
        if not rows:
            logger.info(f"glitch: nobody had cards equipped at S{season}W{week}")
            return 0

        byUser: Dict[int, list] = {}
        for eq in rows:
            if eq.user_id in already:
                continue
            byUser.setdefault(eq.user_id, []).append(eq)
        marked = 0
        for userId, equipped in byUser.items():
            # Deterministic per user+event, so a retry picks the same card.
            rng = _rng(userId, season, week, 0)
            chosen = rng.choice(equipped)
            card = session.get(UserCard, chosen.user_card_id)
            if card is None or card.glitched:
                continue
            card.glitched = True
            card.glitched_season = season
            card.glitched_week = week
            marked += 1
        if marked:
            session.commit()
            logger.info(f"Criticality S{season}W{week}: glitched {marked} cards")
        return marked
    except Exception as e:
        session.rollback()
        logger.error(f"Failed to mark glitch cards for S{season}W{week}: {e}")
        return 0


def displayFlagsFor(session, equipped, season: int, week: int) -> Dict[int, Dict[str, bool]]:
    """{userCardId: {"awakened": bool, "surged": bool}} for a user's equipped cards.

    The two flags the card's VISUAL treatment needs, which the card row itself cannot
    know: whether the depicted player is awakened (the treatment converges on gold), and
    whether this card's glitch actually fired in the settled week (the one moment the card
    is allowed to move).

    Computed server-side because the lineup view has no access to score breakdowns — it
    renders from the equipped-cards endpoint alone. Batched for the same reason
    `anomalyContextFor` is: this runs on every lineup render.

    `surged` reads the BANKED breakdown, so it is only ever true for a settled week. A
    live week has not resolved, which is correct — the burst belongs to the resolution.
    """
    out: Dict[int, Dict[str, bool]] = {}
    glitched = [eq for eq in equipped
                if getattr(getattr(eq, 'user_card', None), 'glitched', False)]
    if not glitched:
        return out
    for eq in glitched:
        out[eq.user_card_id] = {"awakened": False, "surged": False}

    # awakened — one query for every depicted player
    try:
        from database.models import AnomalyState
        byPlayer = {eq.user_card.card_template.player_id: eq.user_card_id
                    for eq in glitched}
        rows = session.query(AnomalyState.player_id, AnomalyState.state).filter(
            AnomalyState.player_id.in_(list(byPlayer)), AnomalyState.season == season)
        for pid, state in rows:
            if state == 'awakened' and pid in byPlayer:
                out[byPlayer[pid]]["awakened"] = True
    except Exception as e:
        logger.debug("glitch: awakened flag lookup failed: %s", e)

    # surged — did this card's glitch fire in the settled week
    try:
        import json as _json
        from database.models import WeeklyCardBonus
        row = (session.query(WeeklyCardBonus)
               .filter_by(user_id=glitched[0].user_id, season=season, week=week)
               .first())
        if row and row.breakdowns_json:
            bySlot = {eq.slot_number: eq.user_card_id for eq in glitched}
            for bd in (_json.loads(row.breakdowns_json) or []):
                if not bd.get('glitchTriggered'):
                    continue
                ucId = bySlot.get(bd.get('slotNumber'))
                if ucId in out:
                    out[ucId]["surged"] = True
    except Exception as e:
        logger.debug("glitch: surge flag lookup failed: %s", e)
    return out
