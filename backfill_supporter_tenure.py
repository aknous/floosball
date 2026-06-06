"""Backfill Supporter loyalty tenure from favorite-team history.

`supporter_weeks` starts at 0, so without this every existing fan begins at
New Fan. This reconstructs tenure from `favorite_team_locked_season` (the season
a fan last set their favorite team). Idempotent and only-raises, so it's safe to
re-run; it never lowers tenure already accrued or soft-reset by a team change.

Fans with no `favorite_team_locked_season` have no signal and are left as-is.

  .venv/bin/python backfill_supporter_tenure.py            # dry run (no writes)
  .venv/bin/python backfill_supporter_tenure.py --apply    # write the changes
  .venv/bin/python backfill_supporter_tenure.py --season 9 # override the season

Run the dry run first, eyeball the diff, then re-run with --apply.
"""
import sys

from database.connection import get_session
from database.models import SimulationState
from managers import supporterManager


def main():
    apply = '--apply' in sys.argv
    season = None
    if '--season' in sys.argv:
        season = int(sys.argv[sys.argv.index('--season') + 1])

    session = get_session()
    try:
        if season is None:
            st = session.query(SimulationState).first()
            season = st.current_season if st else None
        if not season:
            print("No current season found in simulation_state; pass --season N.")
            return

        result = supporterManager.backfillTenure(session, season, apply=apply)
        verb = 'updated' if apply else 'would update'
        print(f"Season {season}: scanned {result['scanned']} fans, {verb} {result['updated']}.")
        for c in sorted(result['changes'], key=lambda c: -c['to'])[:50]:
            print(f"  user {c['userId']}: {c['from']} -> {c['to']} wks ({c['tier']})")
        if result['updated'] > 50:
            print(f"  ... and {result['updated'] - 50} more")
        if not apply and result['updated']:
            print("\nDry run only — no changes written. Re-run with --apply to commit.")
    finally:
        session.close()


if __name__ == '__main__':
    main()
