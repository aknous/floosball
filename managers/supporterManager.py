"""Supporter income — the non-fantasy, IDLE Floobit path (feature/fan-income).

Back a team, earn passively, claim on login. Tenure (weeks supporting the
current favorite team) drives a loyalty multiplier; team performance nudges the
weekly dividend. Accrual runs once per week from the season loop's week-complete
hook; users collect what's accrued via POST /api/supporter/claim.

The guaranteed weekly base is small by design — the real money lives in the
contingent milestone payouts (clinch / Floos Bowl, scaled by loyalty in a later
phase), so only long-tenure fans of great teams come out ahead of what they put
in. Patron-rank multipliers and underdog bonuses land in later phases.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple

from sqlalchemy.orm import Session

from database.models import User, Game
from constants import (
    SUPPORTER_BASE_DIVIDEND,
    SUPPORTER_WIN_BONUS,
    SUPPORTER_LOYALTY_TIERS,
    SUPPORTER_PATRON_TIERS,
    SUPPORTER_TEAM_CHANGE_TENURE_KEEP,
    SUPPORTER_ACTIVITY_WINDOW_DAYS,
)
from logger_config import get_logger

logger = get_logger("floosball.supporter")


def loyaltyTier(weeks: int) -> Tuple[float, str]:
    """Return (multiplier, label) for a tenure of `weeks` supporter-weeks.
    SUPPORTER_LOYALTY_TIERS is descending, so the first match from the top wins."""
    for minWeeks, mult, label in SUPPORTER_LOYALTY_TIERS:
        if weeks >= minWeeks:
            return mult, label
    return 1.0, SUPPORTER_LOYALTY_TIERS[-1][2]


def nextTier(weeks: int) -> Optional[dict]:
    """The next loyalty tier above the current tenure, or None if at the top."""
    for minWeeks, mult, label in reversed(SUPPORTER_LOYALTY_TIERS):  # ascending
        if minWeeks > weeks:
            return {'label': label, 'multiplier': mult, 'weeksAway': minWeeks - weeks}
    return None


def _activityCutoff() -> datetime:
    """Fans must have logged in since this instant to keep earning (the activity
    gate — idle income still requires you to exist, just not to be on right now)."""
    return datetime.utcnow() - timedelta(days=SUPPORTER_ACTIVITY_WINDOW_DAYS)


def isEarning(user: User) -> bool:
    """Whether a fan currently passes the activity gate."""
    return bool(user.last_login_at and user.last_login_at >= _activityCutoff())


# ── Patron rank (share of your team's funding) ────────────────────────────────


def _patronTier(rankIndex: int, total: int) -> Optional[Tuple[float, str]]:
    """Map a contributor's 0-based rank within their team to a patron tier.
    The single biggest backer (rank 0) is always the Patron; everyone else is
    bucketed by percentile. Returns None below the lowest tier."""
    if total <= 0:
        return None
    if rankIndex == 0:
        mult, label = SUPPORTER_PATRON_TIERS[0][1], SUPPORTER_PATRON_TIERS[0][2]
        return mult, label
    pct = rankIndex / total
    for maxPct, mult, label in SUPPORTER_PATRON_TIERS:  # ascending percentile
        if pct < maxPct:
            return mult, label
    return None


def computePatronRanks(session: Session, season: int) -> Dict[int, Tuple[float, str]]:
    """Return {userId: (multiplier, label)} for every contributor this season,
    ranked by their share of their (favorite) team's funding. Non-contributors
    and those below the lowest tier are absent (callers treat as ×1.0 / None).

    Contributions are derived from CurrencyTransaction (type 'team_contribution',
    amount stored negative on spend) — no separate ledger needed, and a user can
    only contribute to their favorite team, so each total belongs to that team."""
    from database.models import CurrencyTransaction
    from sqlalchemy import func

    rows = (
        session.query(
            CurrencyTransaction.user_id,
            func.coalesce(func.sum(-CurrencyTransaction.amount), 0),
        )
        .filter(
            CurrencyTransaction.season == season,
            CurrencyTransaction.transaction_type == 'team_contribution',
        )
        .group_by(CurrencyTransaction.user_id)
        .all()
    )
    contrib = {uid: float(amt) for uid, amt in rows if amt and amt > 0}
    if not contrib:
        return {}

    userTeams = dict(
        session.query(User.id, User.favorite_team_id)
        .filter(User.id.in_(list(contrib.keys())))
        .all()
    )
    byTeam: Dict[int, list] = {}
    for uid, amt in contrib.items():
        team = userTeams.get(uid)
        if team is not None:
            byTeam.setdefault(team, []).append((uid, amt))

    result: Dict[int, Tuple[float, str]] = {}
    for members in byTeam.values():
        members.sort(key=lambda x: x[1], reverse=True)  # biggest backer first
        n = len(members)
        for idx, (uid, _amt) in enumerate(members):
            tier = _patronTier(idx, n)
            if tier:
                result[uid] = tier
    return result


def combinedMultiplier(user: User, patronRanks: Dict[int, Tuple[float, str]]) -> Tuple[float, str, Optional[str]]:
    """Total Supporter multiplier for a fan: loyalty × patron. Returns
    (multiplier, loyaltyLabel, patronLabel)."""
    loyaltyMult, loyaltyLabel = loyaltyTier(int(user.supporter_weeks or 0))
    patronMult, patronLabel = patronRanks.get(user.id, (1.0, None))
    return loyaltyMult * patronMult, loyaltyLabel, patronLabel


def _teamResultsForWeek(session: Session, season: int, week: int) -> Dict[int, bool]:
    """Map team_id -> won? for FINAL games in this season+week. A team absent
    from the map didn't play (bye / eliminated)."""
    results: Dict[int, bool] = {}
    games = session.query(Game).filter_by(season=season, week=week).all()
    for g in games:
        if (g.status or '').lower() != 'final':
            continue
        if g.home_score == g.away_score:
            results[g.home_team_id] = False
            results[g.away_team_id] = False
            continue
        homeWon = g.home_score > g.away_score
        results[g.home_team_id] = homeWon
        results[g.away_team_id] = not homeWon
    return results


def accrueWeekly(session: Session, season: int, week: int) -> int:
    """Accrue this week's Supporter dividend for every active fan.

    Ticks tenure for ALL fans (loyalty is duration, not games watched) and
    credits a dividend to those whose team actually played, scaled by their
    loyalty multiplier. Returns the number of users credited. Caller commits.
    """
    teamResults = _teamResultsForWeek(session, season, week)
    patronRanks = computePatronRanks(session, season)
    # Activity gate: only fans who have signed in recently keep earning. Dormant
    # accounts are frozen — no tenure tick, no dividend — until they return, so
    # users who never log in don't silently rack up Floobits.
    fans = (
        session.query(User)
        .filter(
            User.is_active.is_(True),
            User.favorite_team_id.isnot(None),
            User.last_login_at.isnot(None),
            User.last_login_at >= _activityCutoff(),
        )
        .all()
    )
    credited = 0
    for user in fans:
        user.supporter_weeks = (user.supporter_weeks or 0) + 1
        won = teamResults.get(user.favorite_team_id)
        if won is None:
            continue  # team didn't play this week — tenure ticks, no dividend
        mult, _l, _p = combinedMultiplier(user, patronRanks)  # loyalty × patron
        amount = SUPPORTER_BASE_DIVIDEND + (SUPPORTER_WIN_BONUS if won else 0)
        # (underdog bonus deferred — needs pre-game ELO plumbing)
        dividend = int(round(amount * mult))
        user.supporter_unclaimed = (user.supporter_unclaimed or 0) + dividend
        credited += 1
    logger.info(
        f"Supporter accrual s{season} w{week}: {credited}/{len(fans)} fans credited"
    )
    return credited


def claim(session: Session, userId: int, season: int, week: int) -> int:
    """Move a user's accrued Supporter pool into their balance. Returns the
    amount claimed (0 if nothing to claim). Atomic: the zero-out and the credit
    commit together so a claim can't be lost or double-counted."""
    from database.repositories.card_repositories import CurrencyRepository

    user = session.query(User).filter_by(id=userId).first()
    if not user or not user.supporter_unclaimed:
        return 0
    amount = int(user.supporter_unclaimed)
    user.supporter_unclaimed = 0
    CurrencyRepository(session).addFunds(
        userId, amount, 'supporter_dividend',
        description='Supporter dividend claimed', season=season, week=week,
    )
    session.commit()
    return amount


def getStatus(session: Session, userId: int, season: Optional[int] = None) -> Optional[dict]:
    """Supporter status for the /api/supporter/me surface. Pass the current
    season to include the fan's patron tier (their share of team funding)."""
    user = session.query(User).filter_by(id=userId).first()
    if not user:
        return None
    weeks = int(user.supporter_weeks or 0)
    loyaltyMult, loyaltyLabel = loyaltyTier(weeks)
    patronMult, patronLabel = 1.0, None
    if season is not None:
        patronMult, patronLabel = computePatronRanks(session, season).get(userId, (1.0, None))
    return {
        'favoriteTeamId': user.favorite_team_id,
        'supporterWeeks': weeks,
        'loyaltyTier': loyaltyLabel,
        'loyaltyMultiplier': loyaltyMult,
        'patronTier': patronLabel,
        'patronMultiplier': patronMult,
        'totalMultiplier': round(loyaltyMult * patronMult, 3),
        'nextTier': nextTier(weeks),
        'unclaimed': int(user.supporter_unclaimed or 0),
        # False = income paused because the fan has been away (activity gate).
        'earning': isEarning(user),
    }


def onFavoriteTeamChange(user: User) -> None:
    """Soft-reset tenure when a user switches their favorite team — keep a
    fraction so a switch is a setback, not a wipe (anti-bandwagon). Call this
    BEFORE reassigning favorite_team_id, only on an actual change (not a
    first-time pick). Caller commits."""
    user.supporter_weeks = int((user.supporter_weeks or 0) * SUPPORTER_TEAM_CHANGE_TENURE_KEEP)
