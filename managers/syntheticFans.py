"""Synthetic fans, for sims only (FLOOS_SYNTH_FANS=1).

A sim started from a prod snapshot has no fans after the snapshot: nobody logs in, picks,
buys or donates, so the Floobit faucet collapses (measured 2026-11-01: ~185,000F in the
snapshot's season, ~33,000F the next) and with it the share unit that prices facilities,
the league baseline and every salary. Anything measured on the economy after the first
season is then measuring that collapse.

This replays a REFERENCE season's real fan economy every regular-season week instead:

  - activity: the reference season's EARNERS (fans with Floobit income that season)
    stay logged in, so they count toward gate revenue (participation boosts are not faked: auto-picks never count, and banked
    lineups carry on by themselves);
  - income: the league's Floobit grants are topped up to the reference season's weekly
    rate, shared among its earners in proportion to what they earned, so the share unit
    holds steady;
  - direct facility funding: each fan's reference-season `facility_contribution` total,
    a 28th a week, into their team's Treasury through `contributeToFacilities` (so the
    league match applies);
  - season-end deposits: each fan's balance is pinned at the level whose
    `team_funding_pct` reproduces their reference-season deposit.

The reference season defaults to the season before the first one the hook sees
(`FLOOS_SYNTH_FANS_SEASON` to choose). Off unless the env var is set; nothing in a real
league calls into this with it unset.
"""
import logging
import math
import os
from datetime import datetime

from logger_config import get_logger
logger = get_logger('floosball.syntheticFans')

WEEKS = 28
_profile = None


def enabled() -> bool:
    return os.environ.get('FLOOS_SYNTH_FANS', '').lower() in ('1', 'true', 'on', 'yes')


def _buildProfile(session, refSeason: int) -> dict:
    from sqlalchemy import text
    rows = session.execute(text("""
        SELECT user_id,
               SUM(CASE WHEN amount > 0 THEN amount ELSE 0 END),
               -SUM(CASE WHEN transaction_type = 'facility_contribution' THEN amount ELSE 0 END),
               -SUM(CASE WHEN transaction_type = 'season_end_tax' THEN amount ELSE 0 END)
        FROM currency_transactions WHERE season = :s GROUP BY user_id"""), {'s': refSeason}).fetchall()
    users = {uid: {'income': int(inc or 0), 'contrib': int(con or 0), 'deposit': int(dep or 0)}
             for uid, inc, con, dep in rows}
    total = sum(u['income'] for u in users.values())
    logger.info(f"Synthetic fans: replaying season {refSeason}: {len(users)} fans, "
                f"{total}F income ({total // WEEKS}F a week), "
                f"{sum(u['contrib'] for u in users.values())}F direct funding, "
                f"{sum(u['deposit'] for u in users.values())}F season-end deposits")
    return {'season': refSeason, 'users': users, 'weeklyIncome': total / WEEKS,
            'earners': {uid: u['income'] for uid, u in users.items() if u['income'] > 0}}


def runWeek(seasonManager, season: int, week: int) -> None:
    """One regular-season week of synthetic fans. Called at the end of the week, after
    every real payout, so the top-up sees the week's full grants."""
    global _profile
    if not enabled():
        return
    from sqlalchemy import text
    from database.connection import get_session
    from database.models import User, UserCurrency, CurrencyTransaction
    from constants import DEFAULT_FUNDING_PCT
    session = get_session()
    try:
        if _profile is None:
            ref = int(os.environ.get('FLOOS_SYNTH_FANS_SEASON') or (season - 1))
            _profile = _buildProfile(session, ref)
        users = _profile['users']
        fans = {u.id: u for u in session.query(User).filter(User.id.in_(list(users))).all()}
        # ⚠️ ONLY THE REFERENCE SEASON'S EARNERS PLAY. Every fan with any transaction
        # that season includes ~150 dormant accounts whose leftover Floobits the
        # season-end deposit sweeps (median deposit 9F); keeping them logged in paid gate
        # revenue for ~160 active fans against a real 25-45 (first synthetic run).
        now = datetime.utcnow()
        for uid in _profile['earners']:
            if uid in fans:
                fans[uid].last_login_at = now

        def _wallet(uid):
            w = session.query(UserCurrency).filter_by(user_id=uid).first()
            if w is None:
                w = UserCurrency(user_id=uid, balance=0, lifetime_earned=0, lifetime_spent=0)
                session.add(w)
            return w

        # Income: top the week's grants up to the reference rate.
        already = session.execute(text(
            "SELECT COALESCE(SUM(amount), 0) FROM currency_transactions "
            "WHERE season = :s AND week = :w AND amount > 0"), {'s': season, 'w': week}).scalar() or 0
        deficit = _profile['weeklyIncome'] - float(already)
        earners = _profile['earners']
        totalShare = float(sum(earners.values())) or 1.0
        granted = 0
        if deficit > 0:
            for uid, share in earners.items():
                if uid not in fans:
                    continue
                amt = int(round(deficit * share / totalShare))
                if amt <= 0:
                    continue
                w = _wallet(uid)
                w.balance += amt
                w.lifetime_earned += amt
                session.add(CurrencyTransaction(user_id=uid, amount=amt, balance_after=w.balance,
                                                transaction_type='synthetic_income',
                                                description='Synthetic fan income',
                                                season=season, week=week))
                granted += amt
        session.commit()

        # Direct facility funding, through the real path (spend + league match).
        funded = 0
        for uid, prof in users.items():
            u = fans.get(uid)
            amt = int(round(prof['contrib'] / WEEKS))
            if amt <= 0 or u is None or u.favorite_team_id is None:
                continue
            w = _wallet(uid)
            if w.balance < amt:
                w.balance = amt          # a fan who funds every week has it to give
                session.commit()
            try:
                seasonManager.contributeToFacilities(uid, u.favorite_team_id, amt, target='treasury')
                funded += amt
            except Exception as e:
                logger.debug(f"Synthetic fans: contribution failed for user {uid}: {e}")
        session.expire_all()

        # Pin balances so the season-end deposit reproduces the reference season's.
        for uid, prof in users.items():
            u = fans.get(uid)
            if u is None or u.favorite_team_id is None:
                continue
            pct = getattr(u, 'team_funding_pct', DEFAULT_FUNDING_PCT)
            pct = DEFAULT_FUNDING_PCT if pct is None else max(0, min(100, pct))
            target = int(math.ceil(prof['deposit'] * 100.0 / pct)) if (pct > 0 and prof['deposit'] > 0) else 0
            _wallet(uid).balance = target
        session.commit()
        if week in (1, WEEKS):
            logger.info(f"Synthetic fans s{season} w{week}: topped income up by {granted}F "
                        f"(real grants {int(already)}F), funded {funded}F directly")
    except Exception as e:
        session.rollback()
        logger.error(f"Synthetic fans failed (s{season} w{week}): {e}")
    finally:
        session.close()
