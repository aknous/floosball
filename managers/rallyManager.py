"""Live in-game rally system. Fans spend floobits during a game to push
their team's collective confidence (and determination if trailing). Each
rally writes a GameRally row and applies a real-time bump to every
rostered player's gameAttributes so the per-play mental-drift mechanic
starts working in the team's favor immediately.

Anti-spam without a hard cap:
  - 30-second cooldown between rallies per (user, game).
  - Cost escalation when rallying within a 2-minute window (10F → 15F → 20F).
  - Diminishing returns on the cumulative game-rally count for the team
    (log decay) so the 50th rally is mostly social signal, not mechanical.
"""
from __future__ import annotations
from datetime import datetime, timedelta
from math import log2
from typing import Optional, Tuple, Dict, Any

from sqlalchemy.orm import Session
from sqlalchemy import func

from database.models import GameRally, UserCurrency, Team as DBTeam
from database.repositories.card_repositories import CurrencyRepository


# ── Tunables ──────────────────────────────────────────────────────────────

# Base floobit cost per tier. Cheers are free — the 20s lockout and
# diminishing-returns curve are the only friction. Charging for the
# most basic engagement gesture was working against engagement;
# floobits stay meaningful for things like packs / shop / funding.
RALLY_TIER_COST: Dict[str, int] = {
    'small':  0,
    'medium': 0,
    'large':  0,
}

# Base confidence bump per tier, before diminishing-returns decay.
# All tiers fire at the strong magnitude — single-press parity with
# the previous Roar tier.
RALLY_TIER_BASE_CONF: Dict[str, float] = {
    'small':  0.30,
    'medium': 0.30,
    'large':  0.30,
}

# Cooldown between rallies for the same (user, game). After any rally
# fires, the user is locked out for this long. Anti-spam, no rally count.
RALLY_COOLDOWN_SECONDS = 20

# Comeback weighting — when the team is trailing by this many points,
# 50% of the bump shifts to determination instead of confidence.
COMEBACK_TRAIL_THRESHOLD = 7

# Surge-message thresholds — a feed message only fires when enough
# cheers land within a short window, so the feed isn't spammed by
# every single cheer. Once a surge message fires for a team, it
# can't fire again for that team until the cooldown elapses.
SURGE_WINDOW_SECONDS = 60
SURGE_RALLY_THRESHOLD = 3
SURGE_EMISSION_COOLDOWN_SECONDS = 90

# Diminishing-returns curve on cumulative team rally count. Output scales
# from 1.0 (first rally) toward an asymptote near 0.2 as N grows large.
# Tuned so first 10 rallies retain most of their potency; 50th rally is
# ~30% effective.
def _diminishingFactor(rallyCountBeforeThis: int) -> float:
    n = max(0, rallyCountBeforeThis)
    # log₂(2) / log₂(n+2) → 1.0 at n=0, ~0.39 at n=10, ~0.27 at n=20
    return max(0.2, 1.0 / log2(n + 2))


# ── Errors ────────────────────────────────────────────────────────────────

class RallyError(Exception):
    pass


# ── Core ──────────────────────────────────────────────────────────────────

def computeRallyCost(session: Session, userId: int, gameId: int, tier: str) -> int:
    """Floobit cost for a rally — flat per tier. The 20s lockout handles
    spam, so no per-rally escalation."""
    baseCost = RALLY_TIER_COST.get(tier)
    if baseCost is None:
        raise RallyError(f"Unknown rally tier: {tier}")
    return baseCost


def cooldownRemaining(session: Session, userId: int, gameId: int,
                      teamId: Optional[int] = None) -> int:
    """Seconds remaining on this user's rally cooldown. Scoped to a
    specific team when teamId is provided — users can rally each team
    in a game independently. Returns 0 if no cooldown active."""
    q = session.query(GameRally).filter(
        GameRally.user_id == userId,
        GameRally.game_id == gameId,
    )
    if teamId is not None:
        q = q.filter(GameRally.team_id == teamId)
    lastRally = q.order_by(GameRally.created_at.desc()).first()
    if not lastRally:
        return 0
    elapsed = (datetime.utcnow() - lastRally.created_at).total_seconds()
    return max(0, int(RALLY_COOLDOWN_SECONDS - elapsed))


def _scoreDiff(game, teamId: int) -> int:
    """Positive if `teamId` is leading; negative if trailing."""
    homeId = getattr(game.homeTeam, 'id', None)
    awayId = getattr(game.awayTeam, 'id', None)
    if teamId == homeId:
        return getattr(game, 'homeScore', 0) - getattr(game, 'awayScore', 0)
    if teamId == awayId:
        return getattr(game, 'awayScore', 0) - getattr(game, 'homeScore', 0)
    raise RallyError(f"Team {teamId} not playing in game {game.id}")


def _splitWeights(scoreDiff: int) -> Tuple[float, float]:
    """Return (confidenceWeight, determinationWeight) summing to 1.0.
    Trailing teams shift weight toward determination — the drive-to-win
    axis — so a comeback rally maps to comeback mental energy."""
    if scoreDiff <= -COMEBACK_TRAIL_THRESHOLD:
        return (0.5, 0.5)
    return (1.0, 0.0)


def castRally(session: Session, userId: int, game, teamId: int, tier: str) -> Dict[str, Any]:
    """Apply a rally: charge floobits, compute deltas, write GameRally row,
    and bump live player gameAttributes on the team's roster.

    Raises RallyError for cooldown / unknown-tier / invalid-team cases.
    Returns a dict describing the applied rally for WS broadcast.
    """
    if tier not in RALLY_TIER_COST:
        raise RallyError(f"Unknown rally tier: {tier}")

    # Cooldown check — scoped per-team so users can rally each team
    # independently in the same game.
    cdLeft = cooldownRemaining(session, userId, game.id, teamId)
    if cdLeft > 0:
        raise RallyError(f"Cooldown: {cdLeft}s remaining")

    # Validate team is in this game
    homeId = getattr(game.homeTeam, 'id', None)
    awayId = getattr(game.awayTeam, 'id', None)
    if teamId not in (homeId, awayId):
        raise RallyError(f"Team {teamId} not in game {game.id}")

    # Cost — currently free. If a tier ever has a non-zero cost again
    # we still route through CurrencyRepository for the audit log;
    # otherwise we skip the spend entirely so the CurrencyTransaction
    # table doesn't fill with zero-amount rows.
    cost = computeRallyCost(session, userId, game.id, tier)
    if cost > 0:
        repo = CurrencyRepository(session)
        seasonNum = getattr(game, 'seasonNumber', None)
        weekNum = getattr(game, 'gameWeek', None) or getattr(game, 'weekNumber', None)
        currency = repo.spendFunds(
            userId=userId,
            amount=cost,
            transactionType='rally',
            description=f"Rally g{game.id} {tier}",
            season=seasonNum,
            week=weekNum,
        )
        if currency is None:
            raise RallyError(f"Insufficient floobits ({cost} required)")
        balanceAfter = currency.balance
    else:
        # Free cheer — pull the current balance for the response without
        # mutating anything.
        from database.models import UserCurrency
        uc = session.query(UserCurrency).filter_by(user_id=userId).first()
        balanceAfter = uc.balance if uc else 0

    # Compute applied deltas — base × diminishing-returns factor based on
    # the team's cumulative rally count BEFORE this one.
    priorCount = session.query(func.count(GameRally.id)).filter(
        GameRally.game_id == game.id,
        GameRally.team_id == teamId,
    ).scalar() or 0
    factor = _diminishingFactor(int(priorCount))
    baseBump = RALLY_TIER_BASE_CONF[tier] * factor

    diff = _scoreDiff(game, teamId)
    cw, dw = _splitWeights(diff)
    confDelta = round(baseBump * cw, 3)
    detDelta = round(baseBump * dw, 3)

    # Record the rally row
    row = GameRally(
        game_id=game.id,
        user_id=userId,
        team_id=teamId,
        tier=tier,
        cost_paid=cost,
        confidence_delta=confDelta,
        determination_delta=detDelta,
    )
    session.add(row)
    session.flush()

    # Apply the bump to every rostered player's live gameAttributes so the
    # next play's _mentalDrift picks it up. Done in-place on the team object.
    _applyBumpToTeam(game, teamId, confDelta, detDelta)

    # Surge gate — only emit a feed message when enough cheers landed
    # for this team within SURGE_WINDOW_SECONDS, and only once every
    # SURGE_EMISSION_COOLDOWN_SECONDS. Individual cheers stay silent in
    # the feed; collective surges get one persistent line.
    feedMessage = _maybeEmitSurge(game, session, teamId)

    # Aggregate stats for the response / WS payload
    totals = session.query(
        func.count(GameRally.id),
        func.coalesce(func.sum(GameRally.confidence_delta), 0.0),
        func.coalesce(func.sum(GameRally.determination_delta), 0.0),
    ).filter(
        GameRally.game_id == game.id,
        GameRally.team_id == teamId,
    ).first()
    totalRallies = int(totals[0] or 0)
    totalConf = round(float(totals[1] or 0.0), 3)
    totalDet = round(float(totals[2] or 0.0), 3)

    return {
        'rallyId': row.id,
        'gameId': game.id,
        'teamId': teamId,
        'userId': userId,
        'tier': tier,
        'costPaid': cost,
        'confidenceDelta': confDelta,
        'determinationDelta': detDelta,
        'balanceAfter': balanceAfter,
        'teamTotals': {
            'rallies': totalRallies,
            'confidence': totalConf,
            'determination': totalDet,
        },
        'cooldownSeconds': RALLY_COOLDOWN_SECONDS,
        'nextCost': computeRallyCost(session, userId, game.id, tier),
        'feedMessage': feedMessage,
    }


def _maybeEmitSurge(game, session: Session, teamId: int) -> Optional[str]:
    """Decide whether this rally crosses the surge threshold and
    deserves a feed message. Returns the message text if so (and
    appends it to the game's gameFeed), or None.

    Rules:
      1. Count rallies for this team within SURGE_WINDOW_SECONDS.
      2. If count < SURGE_RALLY_THRESHOLD, return None.
      3. If a surge message was emitted for this team within
         SURGE_EMISSION_COOLDOWN_SECONDS, return None.
      4. Otherwise: insert into gameFeed, record emission time, return text.
    """
    try:
        windowStart = datetime.utcnow() - timedelta(seconds=SURGE_WINDOW_SECONDS)
        count = session.query(func.count(GameRally.id)).filter(
            GameRally.game_id == game.id,
            GameRally.team_id == teamId,
            GameRally.created_at >= windowStart,
        ).scalar() or 0
        if count < SURGE_RALLY_THRESHOLD:
            return None

        # Cooldown — only emit once per cooldown window per team.
        emitMap = getattr(game, '_rallySurgeLastEmit', None)
        if emitMap is None:
            emitMap = {}
            game._rallySurgeLastEmit = emitMap
        lastEmit = emitMap.get(teamId)
        if lastEmit is not None:
            elapsed = (datetime.utcnow() - lastEmit).total_seconds()
            if elapsed < SURGE_EMISSION_COOLDOWN_SECONDS:
                return None

        # Build the surge message — collective, no specific username.
        team = game.homeTeam if game.homeTeam.id == teamId else game.awayTeam
        teamName = getattr(team, 'name', '') or ''
        text = f"The fans are rallying behind the {teamName}"

        # Persist in gameFeed so REST /api/games/{id} replays it on
        # subsequent fetches. Same shape as other events.
        feed = getattr(game, 'gameFeed', None)
        if feed is not None:
            feed.insert(0, {'event': {'text': text, '_type': 'rally'}})

        emitMap[teamId] = datetime.utcnow()
        return text
    except Exception:
        return None


def _applyBumpToTeam(game, teamId: int, confDelta: float, detDelta: float):
    """Bump every rostered player's gameAttributes confidence/determination.
    No-op if the team isn't found or the game hasn't initialized gameAttributes
    (happens for scheduled games — rallies only apply to live ones)."""
    if confDelta == 0 and detDelta == 0:
        return
    team = game.homeTeam if game.homeTeam.id == teamId else game.awayTeam
    if team is None or not hasattr(team, 'rosterDict'):
        return
    for p in team.rosterDict.values():
        if p is None or getattr(p, 'gameAttributes', None) is None:
            continue
        try:
            p.gameAttributes.confidenceModifier = round(
                (p.gameAttributes.confidenceModifier or 0.0) + confDelta, 3)
            p.gameAttributes.determinationModifier = round(
                (p.gameAttributes.determinationModifier or 0.0) + detDelta, 3)
            # Cap at ±5 to match the postgame clamp.
            if p.gameAttributes.confidenceModifier > 5:
                p.gameAttributes.confidenceModifier = 5
            if p.gameAttributes.confidenceModifier < -5:
                p.gameAttributes.confidenceModifier = -5
            if p.gameAttributes.determinationModifier > 5:
                p.gameAttributes.determinationModifier = 5
            if p.gameAttributes.determinationModifier < -5:
                p.gameAttributes.determinationModifier = -5
        except Exception:
            pass


def getRallyStateForGame(session: Session, gameId: int, userId: Optional[int] = None) -> Dict[str, Any]:
    """Snapshot of all rally activity for a game — per-team totals,
    top contributors, plus the current user's cooldown / next-cost
    if userId is provided. Used by the frontend to render the rally
    meter + leaderboard."""
    perTeam = session.query(
        GameRally.team_id,
        func.count(GameRally.id),
        func.coalesce(func.sum(GameRally.confidence_delta), 0.0),
        func.coalesce(func.sum(GameRally.determination_delta), 0.0),
        func.coalesce(func.sum(GameRally.cost_paid), 0),
    ).filter(GameRally.game_id == gameId).group_by(GameRally.team_id).all()

    teamTotals = {}
    for row in perTeam:
        teamId, n, cTot, dTot, costTot = row
        teamTotals[int(teamId)] = {
            'rallies': int(n or 0),
            'confidence': round(float(cTot or 0.0), 3),
            'determination': round(float(dTot or 0.0), 3),
            'floobitsSpent': int(costTot or 0),
        }

    out: Dict[str, Any] = {'teamTotals': teamTotals}

    if userId is not None:
        # Per-team cooldown so each team's rally button hydrates its own
        # state on mount. Compute from the user's actual rally history,
        # not from teamTotals (which aggregates across all users).
        from sqlalchemy import func as _func
        recentByTeam = session.query(
            GameRally.team_id,
            _func.max(GameRally.created_at),
        ).filter(
            GameRally.user_id == userId,
            GameRally.game_id == gameId,
        ).group_by(GameRally.team_id).all()
        perTeamCooldown: Dict[int, int] = {}
        for tid, lastTs in recentByTeam:
            elapsed = (datetime.utcnow() - lastTs).total_seconds()
            remaining = max(0, int(RALLY_COOLDOWN_SECONDS - elapsed))
            if remaining > 0:
                perTeamCooldown[int(tid)] = remaining
        out['cooldownByTeam'] = perTeamCooldown
        out['nextCost'] = {
            tier: computeRallyCost(session, userId, gameId, tier)
            for tier in RALLY_TIER_COST.keys()
        }

    return out
