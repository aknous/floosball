"""Backfill weekly-FP achievements undercounted by the stale-snapshot-cache bug.

The week-end achievement hook read a cached fantasy snapshot that could predate
that week's card-bonus FP, so users who cleared a Banner Week / Dynamo tier on a
card-boosted week were never credited (e.g. true weekly total 5105, hook saw
3229). The cache bug is fixed going forward (cb48988); this script repairs the
already-affected progress.

It recomputes each user's TRUE weekly total from authoritative stored data:

    weeklyTotal(user, week) = WeeklyCardBonus.equationSummary.weekRawFP   (base)
                            + WeeklyCardBonus.bonus_fp                    (card)

(weekRawFP + bonus_fp == the raw total the user saw on the fantasy page.) Then it
re-runs the same production hooks the live path uses, so rewards + progress are
written exactly as a real unlock would. Progress is only ever raised (max), never
lowered, so re-running is safe and idempotent.

Note: a user with NO cards equipped in a week has no WeeklyCardBonus row, so that
week contributes only ~base FP and is invisible here — but such weeks were never
undercounted (no card bonus to drop), and base-only weeks never approach the
tiers, so this is exactly the affected population. Dynamo (season cumulative) is
exact for users who equipped cards every week and a safe lower bound otherwise.

    python backfill_weekly_fp_achievements.py                  # dry run, current season
    python backfill_weekly_fp_achievements.py --apply          # grant, current season
    python backfill_weekly_fp_achievements.py --season 3 --apply
    python backfill_weekly_fp_achievements.py --all-seasons --apply

Run it when the sim is idle if possible — it writes UserAchievement / rewards and
can briefly contend with the running simulation for the SQLite write lock.
"""
import argparse
import json

from database.connection import get_session
from database.models import (
    WeeklyCardBonus, SimulationState, Achievement, UserAchievement, User,
)
from managers import achievementManager as am


def trueWeeklyTotals(session, season):
    """{userId: {week: total}} from stored WeeklyCardBonus rows for a season."""
    rows = session.query(WeeklyCardBonus).filter(WeeklyCardBonus.season == season).all()
    byUser = {}
    missingBase = 0
    for r in rows:
        base = 0.0
        if r.breakdowns_json:
            try:
                summary = (json.loads(r.breakdowns_json).get('equationSummary') or {})
                base = float(summary.get('weekRawFP', 0) or 0)
            except Exception:
                base = 0.0
        if base == 0.0:
            # base unavailable (older row) — bonus_fp alone is within ~base FP
            # (a couple hundred) of the true total, negligible vs the tiers.
            missingBase += 1
        byUser.setdefault(r.user_id, {})[r.week] = base + float(r.bonus_fp or 0)
    return byUser, missingBase


def tierRows(session, prefix):
    rows = session.query(Achievement).filter(Achievement.key.like(f"{prefix}%")).all()
    return sorted(rows, key=lambda a: a.target)


def completed(session, userId, ach, season):
    ua = session.query(UserAchievement).filter_by(
        user_id=userId, achievement_id=ach.id, season=season,
    ).first()
    return ua is not None and ua.completed_at is not None, (ua.progress if ua else 0)


def runSeason(session, season, apply):
    byUser, missingBase = trueWeeklyTotals(session, season)
    if not byUser:
        print(f"  season {season}: no WeeklyCardBonus rows — nothing to backfill.")
        return 0

    bannerTiers = tierRows(session, "banner_week_")
    dynamoTiers = tierRows(session, "dynamo_")
    userNames = {u.id: (u.username or f"user#{u.id}")
                 for u in session.query(User).filter(User.id.in_(byUser.keys())).all()}

    print(f"\n=== Season {season} — {len(byUser)} users with card data"
          f"{f' ({missingBase} rows missing weekRawFP, base treated as 0)' if missingBase else ''} ===")
    grantedCount = 0
    for userId, weeks in sorted(byUser.items()):
        bannerMax = max(weeks.values()) if weeks else 0.0
        dynamoSum = sum(weeks.values())
        name = userNames.get(userId, f"user#{userId}")

        # What would newly unlock?
        newBanner = [t for t in bannerTiers
                     if round(bannerMax) >= t.target and not completed(session, userId, t, season)[0]]
        newDynamo = [t for t in dynamoTiers
                     if round(dynamoSum) >= t.target and not completed(session, userId, t, season)[0]]
        if not newBanner and not newDynamo:
            continue

        tags = [t.name for t in newBanner] + [t.name for t in newDynamo]
        print(f"  {name:<22} bannerMax={bannerMax:8.1f}  seasonTotal={dynamoSum:9.1f}"
              f"  -> {'GRANT' if apply else 'would grant'}: {', '.join(tags)}")

        if apply:
            unlocked = am.onWeeklyFantasyPoints(session, userId, round(bannerMax), season)
            unlocked += am.onSeasonFantasyPointsTotal(session, userId, round(dynamoSum), season)
            # recordProgress only commits when something unlocks; commit anyway so
            # the raised progress (corrected "highest total") is persisted too.
            session.commit()
            grantedCount += len(unlocked)
    return grantedCount


def main():
    ap = argparse.ArgumentParser(description="Backfill weekly-FP achievements")
    ap.add_argument("--apply", action="store_true", help="actually grant (default: dry run)")
    ap.add_argument("--season", type=int, default=None, help="season to backfill (default: current)")
    ap.add_argument("--all-seasons", action="store_true", help="backfill every season")
    args = ap.parse_args()

    session = get_session()
    try:
        if args.all_seasons:
            seasons = [s for (s,) in session.query(WeeklyCardBonus.season).distinct().all()]
            seasons = sorted(s for s in seasons if s is not None)
        elif args.season is not None:
            seasons = [args.season]
        else:
            st = session.query(SimulationState).filter_by(id=1).first()
            seasons = [st.current_season if st else 1]

        mode = "APPLY" if args.apply else "DRY RUN"
        print(f"Weekly-FP achievement backfill [{mode}] — seasons: {seasons}")
        total = 0
        for s in seasons:
            total += runSeason(session, s, args.apply)
        if args.apply:
            print(f"\nDone. {total} achievement tier(s) newly unlocked.")
        else:
            print("\nDry run complete — no changes written. Re-run with --apply to grant.")
    finally:
        session.close()


if __name__ == "__main__":
    main()
