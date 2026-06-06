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


def testPatronRanks(session):
    """Share-based patron tiers from team_contribution transactions."""
    import managers.supporterManager as s
    from database.models import User, CurrencyTransaction
    now = datetime.utcnow()
    # Team 5: three contributors (40 > 41 > 42). Team 6: a sole contributor.
    for uid, fav in [(40, 5), (41, 5), (42, 5), (60, 6)]:
        session.add(User(id=uid, email=f'{uid}@x.com', is_active=True, favorite_team_id=fav,
                         supporter_weeks=0, supporter_unclaimed=0, last_login_at=now))
    for uid, amt in [(40, 400), (41, 200), (42, 100), (60, 50)]:
        session.add(CurrencyTransaction(user_id=uid, amount=-amt, balance_after=0,
                                        transaction_type='team_contribution', season=2))
    session.commit()
    ranks = s.computePatronRanks(session, season=2)
    assert ranks[40] == (1.5, 'Patron'), ranks.get(40)     # biggest backer
    assert ranks[41] == (1.15, 'Backer'), ranks.get(41)    # middle, top-half
    assert 42 not in ranks, "smallest backer below the lowest tier"
    assert ranks[60] == (1.5, 'Patron'), ranks.get(60)     # sole backer → Patron
    # getStatus surfaces the tier + combined multiplier.
    st = s.getStatus(session, 40, season=2)
    assert st['patronTier'] == 'Patron' and st['patronMultiplier'] == 1.5
    print("  ok: patron ranks (biggest + sole = Patron; combined surfaced in status)")


def testCombinedScaling(session):
    """A Lifer who is also a Patron earns the dividend at loyalty × patron."""
    import managers.supporterManager as s
    from constants import SUPPORTER_BASE_DIVIDEND, SUPPORTER_WIN_BONUS
    from database.models import User, Game, CurrencyTransaction
    now = datetime.utcnow()
    session.add(Game(season=3, week=1, home_team_id=7, away_team_id=8,
                     home_score=21, away_score=14, status='final'))
    session.add(User(id=70, email='70@x.com', is_active=True, favorite_team_id=7,
                     supporter_weeks=200, supporter_unclaimed=0, last_login_at=now))  # Lifer ×2.0
    session.add(CurrencyTransaction(user_id=70, amount=-500, balance_after=0,
                                    transaction_type='team_contribution', season=3))  # sole Patron ×1.5
    session.commit()
    s.accrueWeekly(session, season=3, week=1)
    session.commit()
    u = session.get(User, 70)
    expected = round((SUPPORTER_BASE_DIVIDEND + SUPPORTER_WIN_BONUS) * 2.0 * 1.5)  # ×3.0
    assert u.supporter_unclaimed == expected, (u.supporter_unclaimed, expected)
    print(f"  ok: combined scaling (Lifer ×2.0 × Patron ×1.5 → {expected}F)")


def testWinQualityBonuses(session):
    import managers.supporterManager as s
    from constants import (
        SUPPORTER_WIN_BONUS, SUPPORTER_SHUTOUT_BONUS, SUPPORTER_BLOWOUT_BONUS,
        SUPPORTER_COMEBACK_BONUS, SUPPORTER_PLAYOFF_WIN_BONUS,
    )
    from database.models import Game

    # Shutout blowout: team 40 wins 35-0 (margin 35 >= 21, opponent 0).
    g1 = Game(season=5, week=1, home_team_id=40, away_team_id=41,
              home_score=35, away_score=0, status='final')
    session.add(g1); session.commit()
    bonus, bd = s.winBonusForGame(session, g1, 40, 5, 1)
    assert bd.get('shutout') == SUPPORTER_SHUTOUT_BONUS
    assert bd.get('blowout') == SUPPORTER_BLOWOUT_BONUS
    assert 'comeback' not in bd, "a shutout can't be a comeback"
    assert bonus == SUPPORTER_WIN_BONUS + SUPPORTER_SHUTOUT_BONUS + SUPPORTER_BLOWOUT_BONUS

    # Comeback: trailing 0-14 after Q3, wins 21-14 in Q4.
    g2 = Game(season=5, week=2, home_team_id=42, away_team_id=43,
              home_score=21, away_score=14, status='final',
              home_score_q1=0, home_score_q2=0, home_score_q3=0, home_score_q4=21,
              away_score_q1=7, away_score_q2=7, away_score_q3=0, away_score_q4=0)
    session.add(g2); session.commit()
    bonus, bd = s.winBonusForGame(session, g2, 42, 5, 2)
    assert bd.get('comeback') == SUPPORTER_COMEBACK_BONUS, bd
    assert 'blowout' not in bd  # margin 7

    # Win streak: team 44 wins weeks 1,2,3 → streak 3 → +2 (length beyond first).
    for wk in (1, 2, 3):
        session.add(Game(season=6, week=wk, home_team_id=44, away_team_id=45 + wk,
                         home_score=20, away_score=10, status='final'))
    session.commit()
    _, bd = s.winBonusForGame(session, session.query(Game).filter_by(season=6, week=3).first(), 44, 6, 3)
    assert bd.get('streak') == 2, bd  # 3-win streak, bonus = 3 - 1

    # Playoff win (Floos Bowl = round 4 = week 32) pays the round bonus.
    g4 = Game(season=5, week=32, home_team_id=46, away_team_id=47,
              home_score=17, away_score=13, status='final', is_playoff=True)
    session.add(g4); session.commit()
    _, bd = s.winBonusForGame(session, g4, 46, 5, 32)
    assert bd.get('playoff') == SUPPORTER_PLAYOFF_WIN_BONUS[4], bd

    # Upset: lower-ELO team 48 beats higher-ELO team 49 → upset bonus.
    from constants import SUPPORTER_UNDERDOG_WIN_BONUS
    from database.models import TeamSeasonStats
    session.add(TeamSeasonStats(team_id=48, season=5, elo=1400))
    session.add(TeamSeasonStats(team_id=49, season=5, elo=1650))
    g5 = Game(season=5, week=3, home_team_id=48, away_team_id=49,
              home_score=20, away_score=17, status='final')
    session.add(g5); session.commit()
    _, bd = s.winBonusForGame(session, g5, 48, 5, 3)
    assert bd.get('upset') == SUPPORTER_UNDERDOG_WIN_BONUS, bd
    # Favorite (higher ELO) winning → no upset.
    _, bd2 = s.winBonusForGame(session, g5, 48, 5, 3) if False else s.winBonusForGame(
        session, Game(season=5, week=4, home_team_id=49, away_team_id=48,
                      home_score=30, away_score=3, status='final'), 49, 5, 4)
    assert 'upset' not in bd2, bd2
    print("  ok: win-quality bonuses (shutout/blowout/comeback/streak/playoff/upset)")


def testDividendLedger(session):
    import managers.supporterManager as s
    from database.models import User, Game, SupporterDividend
    now = datetime.utcnow()
    session.add(Game(season=7, week=1, home_team_id=50, away_team_id=51,
                     home_score=21, away_score=20, status='final'))
    session.add(Game(season=7, week=2, home_team_id=50, away_team_id=52,
                     home_score=30, away_score=0, status='final'))  # shutout + blowout
    session.add(User(id=90, email='90@x.com', is_active=True, favorite_team_id=50,
                     supporter_weeks=84, supporter_unclaimed=0, last_login_at=now))
    session.commit()

    s.accrueWeekly(session, 7, 1); session.commit()
    s.accrueWeekly(session, 7, 2); session.commit()

    rows = session.query(SupporterDividend).filter_by(user_id=90).all()
    assert len(rows) == 2, rows
    st = s.getStatus(session, 90, season=7)
    assert len(st['pending']) == 2
    assert st['unclaimed'] == sum(r.amount for r in rows)
    assert st['pending'][0]['week'] == 2, "newest first"
    assert 'shutout' in st['pending'][0]['breakdown']['parts'], st['pending'][0]

    # Idempotent re-run: no duplicate rows, no extra pay.
    before = st['unclaimed']
    s.accrueWeekly(session, 7, 2); session.commit()
    assert session.query(SupporterDividend).filter_by(user_id=90).count() == 2
    assert s.getStatus(session, 90, season=7)['unclaimed'] == before

    # Claim clears the ledger (it only ever holds the current pool).
    s.claim(session, 90, 7, 2)
    assert session.query(SupporterDividend).filter_by(user_id=90).count() == 0
    assert s.getStatus(session, 90, season=7)['pending'] == []
    print("  ok: dividend ledger (per-week rows, pending in status, idempotent, cleared on claim)")


def testPlayoffAccrualNoTenure(session):
    import managers.supporterManager as s
    from database.models import User, Game
    now = datetime.utcnow()
    # Floos Bowl (week 32 = playoff round 4) win.
    session.add(Game(season=8, week=32, home_team_id=60, away_team_id=61,
                     home_score=24, away_score=20, status='final', is_playoff=True))
    session.add(User(id=95, email='95@x.com', is_active=True, favorite_team_id=60,
                     supporter_weeks=50, supporter_unclaimed=0, last_login_at=now))
    session.commit()
    s.accrueWeekly(session, 8, 32, tickTenure=False); session.commit()
    u = session.get(User, 95)
    assert u.supporter_weeks == 50, "playoff accrual must NOT tick tenure"
    assert u.supporter_unclaimed > 0, "but it should still pay the dividend"
    st = s.getStatus(session, 95, season=8)
    assert 'playoff' in st['pending'][0]['breakdown']['parts'], st['pending'][0]
    print("  ok: playoff accrual pays (incl. playoff bonus) without ticking tenure")


def testTenureBackfill(session):
    import managers.supporterManager as s
    from database.models import User
    # Picked team in season 3, never switched → going into s9, ~6 seasons backed.
    session.add(User(id=80, email='80@x.com', is_active=True, favorite_team_id=1,
                     favorite_team_locked_season=3, supporter_weeks=0))
    # Switched team last season (locked s8) → ~1 season on the new team.
    session.add(User(id=81, email='81@x.com', is_active=True, favorite_team_id=2,
                     favorite_team_locked_season=8, supporter_weeks=0))
    # Already has accrued tenure higher than the estimate → must NOT be lowered.
    session.add(User(id=82, email='82@x.com', is_active=True, favorite_team_id=3,
                     favorite_team_locked_season=8, supporter_weeks=200))
    # No locked_season → no signal → left untouched.
    session.add(User(id=83, email='83@x.com', is_active=True, favorite_team_id=4,
                     favorite_team_locked_season=None, supporter_weeks=0))
    session.commit()

    dry = s.backfillTenure(session, currentSeason=9, apply=False)
    assert session.query(User).get(80).supporter_weeks == 0, "dry run must not write"

    res = s.backfillTenure(session, currentSeason=9, apply=True)
    assert session.query(User).get(80).supporter_weeks == 6 * 28  # Lifer
    assert s.loyaltyTier(session.query(User).get(80).supporter_weeks)[1] == 'Lifer'
    assert session.query(User).get(81).supporter_weeks == 1 * 28  # Regular
    assert session.query(User).get(82).supporter_weeks == 200      # not lowered
    assert session.query(User).get(83).supporter_weeks == 0        # no signal

    # Idempotent: a second apply changes nothing.
    again = s.backfillTenure(session, currentSeason=9, apply=True)
    assert again['updated'] == 0, "re-run should be a no-op"
    print("  ok: tenure backfill (locked_season → weeks, only-raises, idempotent)")


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
        testPatronRanks(session)
        testCombinedScaling(session)
        testWinQualityBonuses(session)
        testDividendLedger(session)
        testPlayoffAccrualNoTenure(session)
        testTenureBackfill(session)
    finally:
        session.close()
    print("ALL PASSED")


if __name__ == '__main__':
    main()
