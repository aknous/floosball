"""Tests for Spectator income (the cheer bar, feature/fan-income).

Covers play-validated fill, segment payouts + the weekly cap, the supported-team
multiplier, the weekly reset, and presence-gated rally fill.

Run standalone:  .venv/bin/python test_spectator_income.py
Exits non-zero on failure.
"""
import os
import tempfile


def _mkUser(session, uid):
    from database.models import User
    session.add(User(id=uid, email=f'{uid}@x.com', is_active=True))
    session.commit()


def testFillAndSegment(session):
    import managers.spectatorManager as sp
    from constants import SPECTATOR_SEGMENT_PAYOUT
    _mkUser(session, 1)
    # First beat = baseline (no retroactive credit).
    s = sp.heartbeat(session, 1, gameId=100, currentPlayCount=0, supportedTeam=False, season=1, week=1)
    assert s['barFill'] == 0 and s['weeklyFloobits'] == 0
    # +10 plays → 10 fill (segment size 18, no payout yet).
    s = sp.heartbeat(session, 1, 100, 10, False, 1, 1)
    assert abs(s['barFill'] - 10) < 1e-6, s['barFill']
    # +12 plays (capped per beat) → 22 total → 1 segment pays, 4 left over.
    s = sp.heartbeat(session, 1, 100, 30, False, 1, 1)
    assert s['weeklySegments'] == 1 and s['weeklyFloobits'] == SPECTATOR_SEGMENT_PAYOUT
    assert abs(s['barFill'] - 4) < 1e-6, s['barFill']
    print("  ok: play-validated fill + segment payout (per-beat play cap honored)")


def testScoringBonus(session):
    import managers.spectatorManager as sp
    from constants import SPECTATOR_FILL_PER_PLAY, SPECTATOR_FILL_PER_POINT
    _mkUser(session, 6)
    sp.heartbeat(session, 6, 600, 0, False, 1, 1, currentScore=0)  # baseline
    # +5 plays and +7 points (a TD) → base play fill + scoring bonus.
    s = sp.heartbeat(session, 6, 600, 5, False, 1, 1, currentScore=7)
    expected = 5 * SPECTATOR_FILL_PER_PLAY + 7 * SPECTATOR_FILL_PER_POINT
    assert abs(s['barFill'] - expected) < 1e-6, (s['barFill'], expected)
    print(f"  ok: scoring bonus (+7 pts adds {7 * SPECTATOR_FILL_PER_POINT:.1f} fill)")


def testWeeklyCap(session):
    import managers.spectatorManager as sp
    from constants import SPECTATOR_WEEKLY_PAYOUT_CAP
    _mkUser(session, 2)
    sp.heartbeat(session, 2, 200, 0, False, 1, 1)  # baseline
    pc = 0
    for _ in range(80):  # pump plenty of plays
        pc += 12
        s = sp.heartbeat(session, 2, 200, pc, False, 1, 1)
    assert s['weeklyFloobits'] == SPECTATOR_WEEKLY_PAYOUT_CAP, s['weeklyFloobits']
    assert s['cappedOut'] is True
    print(f"  ok: weekly payout cap enforced ({SPECTATOR_WEEKLY_PAYOUT_CAP}F)")


def testSupportedMult(session):
    import managers.spectatorManager as sp
    from constants import SPECTATOR_SUPPORTED_TEAM_MULT
    _mkUser(session, 3)
    sp.heartbeat(session, 3, 300, 0, True, 1, 1)  # baseline, supported team
    s = sp.heartbeat(session, 3, 300, 10, True, 1, 1)
    assert abs(s['barFill'] - 10 * SPECTATOR_SUPPORTED_TEAM_MULT) < 1e-6, s['barFill']
    print(f"  ok: supported-team multiplier (×{SPECTATOR_SUPPORTED_TEAM_MULT})")


def testWeeklyReset(session):
    import managers.spectatorManager as sp
    _mkUser(session, 4)
    sp.heartbeat(session, 4, 400, 0, False, 1, 1)
    for pc in (12, 24, 36, 48):
        sp.heartbeat(session, 4, 400, pc, False, 1, 1)
    s1 = sp.getStatus(session, 4, 1, 1)
    assert s1['weeklySegments'] >= 1, "earned something in week 1"
    # New week → weekly counters reset.
    s2 = sp.getStatus(session, 4, 1, 2)
    assert s2['weeklyFloobits'] == 0 and s2['weeklySegments'] == 0
    print("  ok: weekly counters reset on week rollover")


def testRallyPresenceGate(session):
    import managers.spectatorManager as sp
    from constants import SPECTATOR_RALLY_FILL
    _mkUser(session, 5)
    # No heartbeat → not present → rally fill is a no-op.
    sp.addRallyFill(session, 5, 1, 1)
    assert sp.getStatus(session, 5, 1, 1)['barFill'] == 0, "rally ignored when absent"
    # After a heartbeat → present → rally adds fill.
    sp.heartbeat(session, 5, 500, 0, False, 1, 1)
    sp.addRallyFill(session, 5, 1, 1)
    assert abs(sp.getStatus(session, 5, 1, 1)['barFill'] - SPECTATOR_RALLY_FILL) < 1e-6
    print("  ok: rally fill is presence-gated")


def main():
    if os.path.exists('/data'):
        print("SKIP: /data exists on this host — would target the prod volume")
        return
    tmp = tempfile.mkdtemp(prefix='floos_spectest_')
    os.environ['DATABASE_DIR'] = tmp
    from database.connection import engine, get_session
    from database.models import Base
    Base.metadata.create_all(bind=engine)

    print("Spectator income (cheer bar) tests")
    session = get_session()
    try:
        testFillAndSegment(session)
        testScoringBonus(session)
        testWeeklyCap(session)
        testSupportedMult(session)
        testWeeklyReset(session)
        testRallyPresenceGate(session)
    finally:
        session.close()
    print("ALL PASSED")


if __name__ == '__main__':
    main()
