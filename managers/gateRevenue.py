"""Gate revenue and the league donation match (docs/TREASURY_PAYROLL_PLAN.md §4).

Two streams of LEAGUE money into a team's Treasury. Neither spends a user's Floobits.

GATE REVENUE, every regular-season week, for each team's active fans:

    gate = GATE_SHARES_PER_WEEK x shareUnit x (sum of fan weights) ** GATE_FAN_EXPONENT
           x GATE_STADIUM_MULT[stadium level]

  - ACTIVE is the Supporter rule (logged in within SUPPORTER_ACTIVITY_WINDOW_DAYS), so a
    fan who only visits still counts. Gate revenue is meant to be a team's main income,
    reachable without playing fantasy (G3).
  - A fan's WEIGHT is 1.0 plus a participation boost for the site's games that week,
    indexed by how many they did: manual pick-em picks (auto-picks don't count), a fielded
    fantasy lineup, cards in the Showcase. It tops out at two activities.
  - CONCAVE in the weights, so the first fan is worth the most and 17 fans don't earn 17x.

THE DONATION MATCH: the league adds DONATION_MATCH_RATE x each fan's donation (direct
facility contributions and the season-end deposit) on the first DONATION_MATCH_CAP_SHARES
of a share unit that fan gives each season. Small donors get the biggest boost.

Every payment is a `TreasuryIncome` row. A gate row is unique per team per week, so a
re-run of a week (a restart) pays nothing twice.
"""
import json
from datetime import datetime, timedelta
from logging import getLogger

from constants import (GATE_REVENUE_ENABLED, GATE_SHARES_PER_WEEK, GATE_FAN_EXPONENT,
                       GATE_PARTICIPATION_BOOST, GATE_STADIUM_MULT, DONATION_MATCH_ENABLED,
                       DONATION_MATCH_RATE, DONATION_MATCH_CAP_SHARES,
                       SUPPORTER_ACTIVITY_WINDOW_DAYS)

logger = getLogger("floosball.gate")


# ─── Pure pieces ─────────────────────────────────────────────────────────────

def fanWeight(activities: int) -> float:
    """1.0 for an active fan, plus the participation boost for `activities` games played."""
    boosts = GATE_PARTICIPATION_BOOST
    return 1.0 + boosts[max(0, min(int(activities), len(boosts) - 1))]


def stadiumMultiplier(level: int) -> float:
    return GATE_STADIUM_MULT[max(0, min(int(level or 0), len(GATE_STADIUM_MULT) - 1))]


def gateAmount(weights: list, stadiumLevel: int, shareUnit: float) -> int:
    """One team's gate for one week, in Floobits. No active fans, no gate."""
    total = sum(weights or [])
    if total <= 0:
        return 0
    return int(round(GATE_SHARES_PER_WEEK * shareUnit * (total ** GATE_FAN_EXPONENT)
                     * stadiumMultiplier(stadiumLevel)))


def matchFor(amount: int, alreadyMatchedBasis: int, shareUnit: float):
    """(basis, match) for a donation of `amount` from a fan who has already had
    `alreadyMatchedBasis` of this season's donations matched."""
    cap = int(round(DONATION_MATCH_CAP_SHARES * shareUnit))
    basis = max(0, min(int(amount), cap - int(alreadyMatchedBasis)))
    return basis, int(round(basis * DONATION_MATCH_RATE))


# ─── Gate revenue (DB) ───────────────────────────────────────────────────────

def activityCutoff() -> datetime:
    return datetime.utcnow() - timedelta(days=SUPPORTER_ACTIVITY_WINDOW_DAYS)


def activeFansByTeam(session) -> dict:
    """{teamId: [userId, ...]} of each team's active fans (the Supporter rule)."""
    from database.models import User
    out = {}
    for uid, tid in (session.query(User.id, User.favorite_team_id)
                     .filter(User.is_active.is_(True), User.favorite_team_id.isnot(None),
                             User.last_login_at.isnot(None),
                             User.last_login_at >= activityCutoff()).all()):
        out.setdefault(tid, []).append(uid)
    return out


def participationByUser(session, userIds, season: int, week: int) -> dict:
    """{userId: number of the site's games they took part in this week}."""
    from database.models import PickEmPick, WeeklyCardBonus, ShowcaseSlot
    ids = list(userIds)
    if not ids:
        return {}
    counts = {u: 0 for u in ids}
    pickers = {r[0] for r in session.query(PickEmPick.user_id).filter(
        PickEmPick.user_id.in_(ids), PickEmPick.season == season, PickEmPick.week == week,
        PickEmPick.is_auto.is_(False)).distinct().all()}
    lineups = {r[0] for r in session.query(WeeklyCardBonus.user_id).filter(
        WeeklyCardBonus.user_id.in_(ids), WeeklyCardBonus.season == season,
        WeeklyCardBonus.week == week).distinct().all()}
    showcases = {r[0] for r in session.query(ShowcaseSlot.user_id).filter(
        ShowcaseSlot.user_id.in_(ids), ShowcaseSlot.season == season).distinct().all()}
    for u in ids:
        counts[u] = (u in pickers) + (u in lineups) + (u in showcases)
    return counts


def accrueWeeklyGate(session, season: int, week: int, shareUnit: float, teamIds: list) -> dict:
    """Pay every team its gate for this regular-season week and credit its Treasury.
    Idempotent: a team already paid for this week is skipped. Returns {teamId: amount}.
    Caller commits."""
    if not GATE_REVENUE_ENABLED:
        return {}
    from database.models import TreasuryIncome, TeamFacility
    from managers.facilitiesManager import addTreasury
    paid = {r[0] for r in session.query(TreasuryIncome.team_id).filter_by(
        season=season, week=week, kind='gate').all()}
    fans = activeFansByTeam(session)
    allFans = [u for us in fans.values() for u in us]
    activity = participationByUser(session, allFans, season, week)
    stadium = {r[0]: r[1] for r in session.query(TeamFacility.team_id, TeamFacility.level)
               .filter_by(facility_key='stadium').all()}
    out = {}
    for tid in teamIds:
        if tid in paid:
            continue
        us = fans.get(tid, [])
        weights = [fanWeight(activity.get(u, 0)) for u in us]
        amount = gateAmount(weights, stadium.get(tid, 0), shareUnit)
        if amount <= 0:
            continue
        addTreasury(session, tid, amount)
        session.add(TreasuryIncome(
            team_id=tid, season=season, week=week, kind='gate', amount=amount,
            detail_json=json.dumps({'fans': len(us), 'weight': round(sum(weights), 2),
                                    'stadium': stadium.get(tid, 0)})))
        out[tid] = amount
    return out


def gateThisSeason(session, teamId: int, season: int) -> int:
    from database.models import TreasuryIncome
    from sqlalchemy import func
    return int(session.query(func.coalesce(func.sum(TreasuryIncome.amount), 0)).filter_by(
        team_id=teamId, season=season, kind='gate').scalar() or 0)


# ─── The donation match (DB) ─────────────────────────────────────────────────

def matchedBasisThisSeason(session, userId: int, season: int) -> int:
    from database.models import TreasuryIncome
    from sqlalchemy import func
    return int(session.query(func.coalesce(func.sum(TreasuryIncome.basis), 0)).filter_by(
        user_id=userId, season=season, kind='match').scalar() or 0)


def matchDonation(session, userId: int, teamId: int, season: int, amount: int,
                  shareUnit: float, source: str) -> int:
    """Credit the league's match on a fan's donation to their team's Treasury and record
    it. Returns the match paid (0 once the fan's season cap is used). Caller commits."""
    if not DONATION_MATCH_ENABLED or amount <= 0:
        return 0
    from database.models import TreasuryIncome
    from managers.facilitiesManager import addTreasury
    basis, match = matchFor(amount, matchedBasisThisSeason(session, userId, season), shareUnit)
    if match <= 0:
        return 0
    addTreasury(session, teamId, match)
    session.add(TreasuryIncome(team_id=teamId, season=season, week=0, kind='match',
                               user_id=userId, basis=basis, amount=match,
                               detail_json=json.dumps({'source': source, 'donation': int(amount)})))
    session.flush()
    return match


def matchRemaining(session, userId: int, season: int, shareUnit: float) -> int:
    """How much more of this fan's donations the league will match this season."""
    cap = int(round(DONATION_MATCH_CAP_SHARES * shareUnit))
    return max(0, cap - matchedBasisThisSeason(session, userId, season))
