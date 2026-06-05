"""Tests for Supporter income (feature/fan-income) Phase 1.

Covers loyalty tiering, weekly accrual (tenure tick + win/loss dividend scaled
by loyalty), claim (atomic move into balance), and the anti-bandwagon soft-reset.

Run standalone:  .venv/bin/python test_supporter_income.py
Exits non-zero on failure.
"""
import os
import tempfile
from datetime import datetime, timedelta
from types import SimpleNamespace


def testLoyaltyTier():
    import managers.supporterManager as s
    # Boundaries of the default ladder (0 / 28 / 84 / 168).
    assert s.loyaltyTier(0) == (1.0, 'New Fan')
    assert s.loyaltyTier(27)[1] == 'New Fan'
    assert s.loyaltyTier(28) == (1.25, 'Regular')
    assert s.loyaltyTier(83)[1] == 'Regular'
    assert s.loyaltyTier(84) == (1.5, 'Faithful')
    assert s.loyaltyTier(168) == (2.0, 'Lifer')
    assert s.loyaltyTier(9999)[1] == 'Lifer'
    # next-tier helper
    assert s.nextTier(0)['label'] == 'Regular' and s.nextTier(0)['weeksAway'] == 28
    assert s.nextTier(9999) is None
    # soft-reset keeps a fraction
    u = SimpleNamespace(supporter_weeks=100)
    s.onFavoriteTeamChange(u)
    assert u.supporter_weeks == 50, u.supporter_weeks
    print("  ok: loyalty tiers, next-tier, soft-reset")


def testAccrualAndClaim(session):
    import managers.supporterManager as s
    from constants import SUPPORTER_BASE_DIVIDEND, SUPPORTER_WIN_BONUS
    from database.models import User, Game

    # One game where team 1 beats team 2 (accrual reads Game + User only).
    session.add(Game(season=1, week=5, home_team_id=1, away_team_id=2,
                     home_score=24, away_score=17, status='final'))
    # Fan of the winner (Lifer), fan of the loser (New Fan), fan of a team that
    # didn't play (tenure should still tick, no dividend). All recently active.
    now = datetime.utcnow()
    session.add(User(id=10, email='w@x.com', is_active=True, favorite_team_id=1,
                     supporter_weeks=200, supporter_unclaimed=0, last_login_at=now))
    session.add(User(id=11, email='l@x.com', is_active=True, favorite_team_id=2,
                     supporter_weeks=0, supporter_unclaimed=0, last_login_at=now))
    session.add(User(id=12, email='n@x.com', is_active=True, favorite_team_id=99,
                     supporter_weeks=10, supporter_unclaimed=0, last_login_at=now))
    session.commit()

    credited = s.accrueWeekly(session, season=1, week=5)
    session.commit()
    assert credited == 2, credited  # winner + loser fans; the non-player fan isn't credited

    winner = session.get(User, 10)
    loser = session.get(User, 11)
    bystander = session.get(User, 12)
    # Winner: Lifer ×2.0 over (base + win)
    assert winner.supporter_weeks == 201
    assert winner.supporter_unclaimed == round((SUPPORTER_BASE_DIVIDEND + SUPPORTER_WIN_BONUS) * 2.0), winner.supporter_unclaimed
    # Loser: New Fan ×1.0 over base only
    assert loser.supporter_weeks == 1
    assert loser.supporter_unclaimed == round(SUPPORTER_BASE_DIVIDEND * 1.0), loser.supporter_unclaimed
    # Bystander: tenure ticks, no dividend
    assert bystander.supporter_weeks == 11 and bystander.supporter_unclaimed == 0

    # Claim moves the pool into balance and zeroes it.
    from database.repositories.card_repositories import CurrencyRepository
    before = CurrencyRepository(session).getOrCreate(10).balance
    claimed = s.claim(session, 10, season=1, week=5)
    assert claimed == winner.supporter_unclaimed or claimed == round((SUPPORTER_BASE_DIVIDEND + SUPPORTER_WIN_BONUS) * 2.0)
    session.refresh(winner)
    assert winner.supporter_unclaimed == 0, "pool zeroed after claim"
    after = CurrencyRepository(session).getOrCreate(10).balance
    assert after - before == claimed, (after, before, claimed)
    # Re-claim is a no-op.
    assert s.claim(session, 10, season=1, week=5) == 0
    print(f"  ok: accrual (winner x2.0={winner_unclaimed_str(claimed)}), claim atomic, re-claim no-op")


def winner_unclaimed_str(c):
    return str(c)


def testIdleNoTeam(session):
    """A fan with no favorite team is untouched by accrual."""
    import managers.supporterManager as s
    from database.models import User
    session.add(User(id=20, email='not@x.com', is_active=True, favorite_team_id=None,
                     supporter_weeks=5, supporter_unclaimed=0, last_login_at=datetime.utcnow()))
    session.commit()
    s.accrueWeekly(session, season=1, week=6)
    session.commit()
    u = session.get(User, 20)
    assert u.supporter_weeks == 5 and u.supporter_unclaimed == 0
    print("  ok: no-favorite-team fans untouched")


def testDormantFrozen(session):
    """A fan who hasn't logged in within the window is frozen: no tenure tick,
    no dividend — even if their team played and won."""
    import managers.supporterManager as s
    from constants import SUPPORTER_ACTIVITY_WINDOW_DAYS
    from database.models import User, Game
    session.add(Game(season=1, week=7, home_team_id=1, away_team_id=2,
                     home_score=30, away_score=10, status='final'))
    stale = datetime.utcnow() - timedelta(days=SUPPORTER_ACTIVITY_WINDOW_DAYS + 5)
    session.add(User(id=30, email='gone@x.com', is_active=True, favorite_team_id=1,
                     supporter_weeks=200, supporter_unclaimed=0, last_login_at=stale))
    # And one who never logged in at all (NULL).
    session.add(User(id=31, email='never@x.com', is_active=True, favorite_team_id=1,
                     supporter_weeks=50, supporter_unclaimed=0, last_login_at=None))
    session.commit()
    s.accrueWeekly(session, season=1, week=7)
    session.commit()
    dormant = session.get(User, 30)
    never = session.get(User, 31)
    assert dormant.supporter_weeks == 200 and dormant.supporter_unclaimed == 0, "dormant frozen"
    assert never.supporter_weeks == 50 and never.supporter_unclaimed == 0, "never-logged-in frozen"
    assert s.isEarning(dormant) is False and s.isEarning(never) is False
    print("  ok: dormant + never-logged-in fans frozen (activity gate)")


def main():
    if os.path.exists('/data'):
        print("SKIP: /data exists on this host — would target the prod volume")
        return
    tmp = tempfile.mkdtemp(prefix='floos_supptest_')
    os.environ['DATABASE_DIR'] = tmp
    from database.connection import engine, get_session
    from database.models import Base
    Base.metadata.create_all(bind=engine)

    print("Supporter income tests")
    testLoyaltyTier()
    session = get_session()
    try:
        testAccrualAndClaim(session)
        testIdleNoTeam(session)
        testDormantFrozen(session)
    finally:
        session.close()
    print("ALL PASSED")


if __name__ == '__main__':
    main()
