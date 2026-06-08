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

import json
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple

from sqlalchemy.orm import Session

from database.models import User, Game, TeamSeasonStats, SupporterDividend
from constants import (
    SUPPORTER_BASE_DIVIDEND,
    SUPPORTER_WIN_BONUS,
    SUPPORTER_SHUTOUT_BONUS,
    SUPPORTER_BLOWOUT_MARGIN,
    SUPPORTER_BLOWOUT_BONUS,
    SUPPORTER_COMEBACK_BONUS,
    SUPPORTER_STREAK_BONUS_PER_WIN,
    SUPPORTER_STREAK_BONUS_CAP,
    SUPPORTER_UNDERDOG_WIN_BONUS,
    SUPPORTER_PLAYOFF_WIN_BONUS,
    SUPPORTER_LOYALTY_TIERS,
    SUPPORTER_PATRON_TIERS,
    SUPPORTER_TEAM_CHANGE_TENURE_KEEP,
    SUPPORTER_ACTIVITY_WINDOW_DAYS,
    SUPPORTER_WEEKS_PER_SEASON,
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


def _winStreak(session: Session, teamId: int, season: int, week: int) -> int:
    """Consecutive wins for this team ending at (and including) this week's game.
    Counts regular-season + playoff games in order; resets on any loss/tie."""
    games = (
        session.query(Game)
        .filter(
            Game.season == season,
            Game.week <= week,
            ((Game.home_team_id == teamId) | (Game.away_team_id == teamId)),
        )
        .order_by(Game.week.asc())
        .all()
    )
    streak = 0
    for g in games:
        if (g.status or '').lower() != 'final':
            continue
        isHome = g.home_team_id == teamId
        winScore = g.home_score if isHome else g.away_score
        loseScore = g.away_score if isHome else g.home_score
        streak = streak + 1 if winScore > loseScore else 0
    return streak


def winBonusForGame(session: Session, game: Game, winnerId: int, season: int, week: int) -> Tuple[int, dict]:
    """Compute the full win bonus for `winnerId` winning `game`, with a per-part
    breakdown. Base win + win-quality add-ons (shutout / blowout / comeback /
    streak / playoff / upset). Read off the game row plus a couple of cheap
    lookups (streak from game history, ELO from TeamSeasonStats for the upset
    check — the same opponent-ELO-higher rule the live UPSET badge and the
    house_money card use)."""
    isHome = game.home_team_id == winnerId
    loserId = game.away_team_id if isHome else game.home_team_id
    winScore = (game.home_score if isHome else game.away_score) or 0
    loseScore = (game.away_score if isHome else game.home_score) or 0

    bd: Dict[str, int] = {'win': SUPPORTER_WIN_BONUS}
    if loseScore == 0:
        bd['shutout'] = SUPPORTER_SHUTOUT_BONUS
    if (winScore - loseScore) >= SUPPORTER_BLOWOUT_MARGIN:
        bd['blowout'] = SUPPORTER_BLOWOUT_BONUS
    # Comeback: trailing on cumulative score at the end of Q3, then won. (A
    # shutout can't be a comeback — the winner was never behind — so they never
    # both fire.) Quarter scores can be NULL on old/seed games → treat as 0.
    def _q(field):
        return getattr(game, field, 0) or 0
    if isHome:
        winQ3 = _q('home_score_q1') + _q('home_score_q2') + _q('home_score_q3')
        loseQ3 = _q('away_score_q1') + _q('away_score_q2') + _q('away_score_q3')
    else:
        winQ3 = _q('away_score_q1') + _q('away_score_q2') + _q('away_score_q3')
        loseQ3 = _q('home_score_q1') + _q('home_score_q2') + _q('home_score_q3')
    if winQ3 < loseQ3:
        bd['comeback'] = SUPPORTER_COMEBACK_BONUS
    # Win streak: rewards genuine streaks (2+ in a row), so a lone win adds
    # nothing — the bonus tracks the streak length beyond the first win.
    streak = _winStreak(session, winnerId, season, week)
    streakBonus = min(max(0, streak - 1) * SUPPORTER_STREAK_BONUS_PER_WIN, SUPPORTER_STREAK_BONUS_CAP)
    if streakBonus > 0:
        bd['streak'] = streakBonus
    # Playoff win, scaled by round (= week - 28, clamped to 1..4).
    if game.is_playoff:
        rnd = max(1, min(4, (game.week or 0) - 28))
        bd['playoff'] = SUPPORTER_PLAYOFF_WIN_BONUS.get(rnd, SUPPORTER_PLAYOFF_WIN_BONUS[1])
    # Upset: beat a higher-ELO opponent (current-season ELO at week end — same
    # rule cards/UI use; no threshold, matching favorite_team_upset_win).
    winnerElo = session.query(TeamSeasonStats.elo).filter_by(season=season, team_id=winnerId).scalar()
    loserElo = session.query(TeamSeasonStats.elo).filter_by(season=season, team_id=loserId).scalar()
    if winnerElo is not None and loserElo is not None and loserElo > winnerElo:
        bd['upset'] = SUPPORTER_UNDERDOG_WIN_BONUS

    return sum(bd.values()), bd


def _teamWeekOutcomes(session: Session, season: int, week: int) -> Dict[int, dict]:
    """team_id -> {'won': bool, 'winBonus': int, 'breakdown': dict} for FINAL
    games this week. Losers/ties get winBonus 0; absent teams didn't play."""
    outcomes: Dict[int, dict] = {}
    games = session.query(Game).filter_by(season=season, week=week).all()
    for g in games:
        if (g.status or '').lower() != 'final':
            continue
        if g.home_score == g.away_score:
            outcomes[g.home_team_id] = {'won': False, 'winBonus': 0, 'breakdown': {}}
            outcomes[g.away_team_id] = {'won': False, 'winBonus': 0, 'breakdown': {}}
            continue
        winnerId = g.home_team_id if g.home_score > g.away_score else g.away_team_id
        loserId = g.away_team_id if winnerId == g.home_team_id else g.home_team_id
        bonus, bd = winBonusForGame(session, g, winnerId, season, week)
        outcomes[winnerId] = {'won': True, 'winBonus': bonus, 'breakdown': bd}
        outcomes[loserId] = {'won': False, 'winBonus': 0, 'breakdown': {}}
    return outcomes


def accrueWeekly(session: Session, season: int, week: int, tickTenure: bool = True) -> int:
    """Accrue this week's Supporter dividend for every active fan.

    Ticks tenure for ALL fans (loyalty is duration, not games watched) and
    credits a dividend to those whose team played:

        dividend = (BASE + winBonus) × (tenure × funding)

    where winBonus is the base win bonus plus win-quality add-ons (upset,
    shutout, blowout, comeback, streak, playoff round) — so a great week for a
    long-haul patron pays big, and a flat win for a new fan pays a little.

    `tickTenure=False` pays the dividend without advancing tenure — used for
    PLAYOFF rounds, so a deep run keeps paying (incl. the playoff round bonus)
    but only full regular seasons build tenure.

    Each credited week also writes a `SupporterDividend` ledger row with the
    full breakdown, so the pool can be explained week-by-week (the rows are
    cleared on claim). Returns the number of users credited. Caller commits.
    """
    outcomes = _teamWeekOutcomes(session, season, week)
    patronRanks = computePatronRanks(session, season)
    # Already-credited fans this week — guards against a double-run (the ledger's
    # unique (user, season, week) would otherwise raise on the duplicate insert).
    alreadyCredited = {
        r[0] for r in session.query(SupporterDividend.user_id)
        .filter_by(season=season, week=week).all()
    }
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
        if tickTenure:
            user.supporter_weeks = (user.supporter_weeks or 0) + 1
        outcome = outcomes.get(user.favorite_team_id)
        if outcome is None:
            continue  # team didn't play this week — tenure ticks, no dividend
        if user.id in alreadyCredited:
            continue  # idempotent: already paid for this week
        mult, _l, _p = combinedMultiplier(user, patronRanks)  # loyalty × patron
        amount = SUPPORTER_BASE_DIVIDEND + outcome['winBonus']
        dividend = int(round(amount * mult))
        user.supporter_unclaimed = (user.supporter_unclaimed or 0) + dividend
        # Itemize: base + each win-quality part, the applied multiplier, and the
        # final amount — the breakdown of this week's slice of the pool.
        parts = {'base': SUPPORTER_BASE_DIVIDEND}
        parts.update(outcome['breakdown'])
        session.add(SupporterDividend(
            user_id=user.id, season=season, week=week, amount=dividend,
            breakdown_json=json.dumps({
                'parts': parts, 'mult': round(mult, 3),
                'amount': dividend, 'won': outcome['won'],
            }),
        ))
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
    # Clear the itemized pool — the ledger only holds what's currently unclaimed.
    session.query(SupporterDividend).filter_by(user_id=userId).delete()
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
    total = loyaltyMult * patronMult
    # Itemized breakdown of the current unclaimed pool, week by week (newest
    # first). Empty for a legacy pool accrued before the ledger existed.
    pendingRows = (
        session.query(SupporterDividend)
        .filter_by(user_id=userId)
        .order_by(SupporterDividend.season.desc(), SupporterDividend.week.desc())
        .all()
    )
    pending = [{
        'season': r.season, 'week': r.week, 'amount': r.amount,
        'breakdown': json.loads(r.breakdown_json) if r.breakdown_json else None,
    } for r in pendingRows]
    return {
        'favoriteTeamId': user.favorite_team_id,
        'supporterWeeks': weeks,
        'loyaltyTier': loyaltyLabel,
        'loyaltyMultiplier': loyaltyMult,
        'patronTier': patronLabel,
        'patronMultiplier': patronMult,
        'totalMultiplier': round(total, 3),
        'nextTier': nextTier(weeks),
        'unclaimed': int(user.supporter_unclaimed or 0),
        'pending': pending,
        # The weekly dividend the Boost multiplies: base every week your team
        # plays, base+win the weeks they win. Surfaced so the multiplier isn't
        # an abstract number.
        'weeklyBase': SUPPORTER_BASE_DIVIDEND,
        'weeklyWinBonus': SUPPORTER_WIN_BONUS,
        'weeklyMin': round(SUPPORTER_BASE_DIVIDEND * total),
        'weeklyMax': round((SUPPORTER_BASE_DIVIDEND + SUPPORTER_WIN_BONUS) * total),
        # False = income paused because the fan has been away (activity gate).
        'earning': isEarning(user),
    }


def backfillTenure(session: Session, currentSeason: int, apply: bool = False) -> dict:
    """One-time reconstruction of Supporter loyalty tenure.

    `supporter_weeks` defaults to 0, so without this every existing fan would
    start at New Fan. We estimate tenure from `favorite_team_locked_season` — the
    season a fan last set their favorite team (it's only reset on an actual team
    change), so for a fan who never switched it's the season they first picked.

        estimate = (currentSeason - lockedSeason) * SUPPORTER_WEEKS_PER_SEASON

    We only ever RAISE `supporter_weeks` to that estimate, never lower it, so the
    backfill is idempotent and never clobbers tenure already accrued or
    intentionally soft-reset by a team change. Fans with no `locked_season` have
    no signal and are left untouched (they stay wherever they are). Pass
    `apply=True` to write; otherwise it's a dry run. Caller-visible summary is
    returned for logging / the backfill script. Caller commits only on apply."""
    fans = (
        session.query(User)
        .filter(
            User.favorite_team_id.isnot(None),
            User.favorite_team_locked_season.isnot(None),
        )
        .all()
    )
    changes = []
    for u in fans:
        seasonsBacked = max(0, currentSeason - (u.favorite_team_locked_season or currentSeason))
        estimate = seasonsBacked * SUPPORTER_WEEKS_PER_SEASON
        current = u.supporter_weeks or 0
        if estimate > current:
            changes.append({
                'userId': u.id, 'from': current, 'to': estimate,
                'tier': loyaltyTier(estimate)[1],
            })
            if apply:
                u.supporter_weeks = estimate
    if apply:
        session.commit()
    logger.info(
        f"Supporter tenure backfill (season {currentSeason}, apply={apply}): "
        f"scanned {len(fans)}, {'updated' if apply else 'would update'} {len(changes)}"
    )
    return {'scanned': len(fans), 'updated': len(changes), 'changes': changes}


def onFavoriteTeamChange(user: User) -> None:
    """Soft-reset tenure when a user switches their favorite team — keep a
    fraction so a switch is a setback, not a wipe (anti-bandwagon). Call this
    BEFORE reassigning favorite_team_id, only on an actual change (not a
    first-time pick). Caller commits."""
    user.supporter_weeks = int((user.supporter_weeks or 0) * SUPPORTER_TEAM_CHANGE_TENURE_KEEP)
