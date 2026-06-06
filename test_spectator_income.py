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


def testClaimCapsToRealProgress(session):
    import managers.spectatorManager as sp
    from constants import SPECTATOR_FILL_PER_PLAY
    _mkUser(session, 7)
    # First claim = baseline at real play 0, no retro credit.
    s = sp.claim(session, 7, gameId=700, witnessedPlays=0, witnessedPoints=0,
                 supportedTeam=False, season=1, week=1, realPlayCount=0, realScore=0)
    assert s['barFill'] == 0
    # Client claims it witnessed 10 plays; the game really advanced 8 → credit 8.
    s = sp.claim(session, 7, 700, witnessedPlays=10, witnessedPoints=0,
                 supportedTeam=False, season=1, week=1, realPlayCount=8, realScore=0)
    assert abs(s['barFill'] - 8 * SPECTATOR_FILL_PER_PLAY) < 1e-6, s['barFill']
    print("  ok: claim credits min(witnessed, real progress) — can't outrun the game")


def testClaimGapNotCredited(session):
    import managers.spectatorManager as sp
    from constants import SPECTATOR_FILL_PER_PLAY
    _mkUser(session, 8)
    sp.claim(session, 8, 800, 0, 0, False, 1, 1, realPlayCount=0, realScore=0)  # baseline
    sp.claim(session, 8, 800, 5, 0, False, 1, 1, realPlayCount=5, realScore=0)  # watched 5
    # Modal closed: game ran to play 40 while away. On reopen the client's
    # witnessed resets to 0, then it witnesses 3 new plays (game now at 43).
    s = sp.claim(session, 8, 800, witnessedPlays=3, witnessedPoints=0,
                 supportedTeam=False, season=1, week=1, realPlayCount=43, realScore=0)
    # Only the 3 witnessed-while-watching plays credit — not the 35-play gap.
    assert abs(s['barFill'] - 8 * SPECTATOR_FILL_PER_PLAY) < 1e-6, s['barFill']
    print("  ok: plays while modal was closed are not credited (witnessed is the cap)")


def testBigPlayBonus(session):
    import managers.spectatorManager as sp
    from constants import (SPECTATOR_FILL_PER_PLAY, SPECTATOR_BIG_PLAY_FILL,
                           SPECTATOR_OWN_BIG_PLAY_MULT)
    _mkUser(session, 9)
    # Baseline at play 0, no big plays yet.
    sp.claim(session, 9, gameId=900, witnessedPlays=0, witnessedPoints=0,
             supportedTeam=True, season=1, week=1, realPlayCount=0, realScore=0,
             witnessedBigPlays=0, realBigMine=0, realBigOther=0)
    # +2 plays, of which 1 was a big play BY my team and 1 by the opponent.
    # (kept under the segment size so barFill == credited fill, no payout)
    s = sp.claim(session, 9, 900, witnessedPlays=2, witnessedPoints=0,
                 supportedTeam=False, season=1, week=1, realPlayCount=2, realScore=0,
                 witnessedBigPlays=2, realBigMine=1, realBigOther=1)
    # plays: 2 × 1; big: mine 4×2 + other 4 = 12.
    expected = 2 * SPECTATOR_FILL_PER_PLAY \
        + SPECTATOR_BIG_PLAY_FILL * SPECTATOR_OWN_BIG_PLAY_MULT + SPECTATOR_BIG_PLAY_FILL
    assert abs(s['barFill'] - expected) < 1e-6, (s['barFill'], expected)

    # Anti-cheat: claim more big plays than really happened → capped to real.
    _mkUser(session, 10)
    sp.claim(session, 10, 1000, 0, 0, False, 1, 1, realPlayCount=0, realScore=0,
             witnessedBigPlays=0, realBigMine=0, realBigOther=0)
    s2 = sp.claim(session, 10, 1000, witnessedPlays=0, witnessedPoints=0,
                  supportedTeam=False, season=1, week=1, realPlayCount=0, realScore=0,
                  witnessedBigPlays=9, realBigMine=0, realBigOther=1)
    # Only 1 real big play happened (other) → 1 × base fill, the rest uncredited.
    assert abs(s2['barFill'] - SPECTATOR_BIG_PLAY_FILL) < 1e-6, s2['barFill']
    print(f"  ok: big-play bonus (own ×{SPECTATOR_OWN_BIG_PLAY_MULT}, capped to real)")


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
        testClaimCapsToRealProgress(session)
        testClaimGapNotCredited(session)
        testBigPlayBonus(session)
        testWeeklyCap(session)
        testSupportedMult(session)
        testWeeklyReset(session)
        testRallyPresenceGate(session)
    finally:
        session.close()
    print("ALL PASSED")


if __name__ == '__main__':
    main()
