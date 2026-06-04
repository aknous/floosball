"""Regression tests for the P3 anomaly suppression cycle + instability dial.

Covers the gated-Criticality behavior (ANOMALY_CRITICALITY_ENABLED=False), where
a threshold crossing no longer fires the event but is dramatized as a near-miss
"patch" and the per-play glitch multiplier rides an instability dial:

  1. The instability dial (_instabilityMultiplier): flat at baseline while quiet,
     ramps with the aggregate's approach to threshold, floored during a
     suppression window, always strictly below CRITICALITY_MULTIPLIER.
  2. The suppression beat (_suppressCriticality): records an audit entry, opens a
     window, drains the over-cap fuel, reinforces the threshold, and is capped
     per season.
  3. getCriticalityStatus: number-free qualitative bands + 'stabilizing' override
     during a window.
  4. End-to-end through _updateLeagueAggregate: a gated crossing fires exactly one
     suppression and goes quiet.

Run standalone:  .venv/bin/python test_anomaly_suppression.py
Exits non-zero on failure.
"""
import os
import tempfile
from types import SimpleNamespace


def _fakeState(aggregate, threshold, suppressionEnds=None, patches=None):
    """Lightweight stand-in for a LeagueAnomalyState row (pure-helper tests)."""
    return SimpleNamespace(
        aggregate_score=float(aggregate),
        threshold=int(threshold),
        suppression_window_ends_week=suppressionEnds,
        cores_patches_applied=patches or [],
        season=99,
    )


def testInstabilityDial():
    import managers.anomalyManager as a

    base = a.INSTABILITY_BASELINE
    ceil = a.INSTABILITY_PRECRIT_CEILING
    start = a.INSTABILITY_RAMP_START

    # Quiet league → baseline.
    assert a._instabilityMultiplier(None, 5) == base
    assert a._instabilityMultiplier(_fakeState(0, 1000), 5) == base
    # At/below the ramp floor → still baseline.
    assert a._instabilityMultiplier(_fakeState(int(start * 1000), 1000), 5) == base
    # At the threshold → the pre-Criticality ceiling.
    assert abs(a._instabilityMultiplier(_fakeState(1000, 1000), 5) - ceil) < 1e-6
    # Over the threshold → clamped to the ceiling (never higher while gated).
    assert abs(a._instabilityMultiplier(_fakeState(1500, 1000), 5) - ceil) < 1e-6

    # Monotonic non-decreasing as the ratio climbs from floor to threshold.
    prev = -1.0
    for agg in range(int(start * 1000), 1001, 50):
        m = a._instabilityMultiplier(_fakeState(agg, 1000), 5)
        assert m >= prev - 1e-9, f"dial dipped at agg={agg}"
        prev = m

    # The gated dial never reaches a real Criticality's intensity.
    assert ceil < a.CRITICALITY_MULTIPLIER

    # Inside a suppression window → floored low regardless of how hot the ratio is.
    hot = _fakeState(2000, 1000, suppressionEnds=10)
    assert a._instabilityMultiplier(hot, week=8) == a.INSTABILITY_SUPPRESSED
    # Window expired → back to riding the ratio.
    assert a._instabilityMultiplier(hot, week=10) == ceil  # week >= ends → not suppressed
    print("  ok: instability dial (baseline / ramp / ceiling / suppression / sub-Criticality)")


def testHelpers():
    import managers.anomalyManager as a
    assert a._bandRatio(None) == 0.0
    assert abs(a._bandRatio(_fakeState(500, 1000)) - 0.5) < 1e-9
    assert a._inSuppressionWindow(_fakeState(0, 1, suppressionEnds=10), 9) is True
    assert a._inSuppressionWindow(_fakeState(0, 1, suppressionEnds=10), 10) is False
    assert a._inSuppressionWindow(_fakeState(0, 1, suppressionEnds=None), 9) is False
    print("  ok: _bandRatio / _inSuppressionWindow")


def testSuppressionMechanicsAndCap(session):
    import managers.anomalyManager as a
    from database.models import LeagueAnomalyState, PlayerAttention

    season = 99
    state = LeagueAnomalyState(
        season=season, aggregate_score=1200.0, threshold=1000,
        thinnings_this_season=0, cores_patches_applied=[],
    )
    session.add(state)
    # Seed over-cap fuel across a few players.
    for pid in (1, 2, 3):
        session.add(PlayerAttention(player_id=pid, season=season,
                                    score=150.0, over_cap_carry=200.0, peak_score=150.0))
    session.commit()

    threshBefore = state.threshold
    a._suppressCriticality(state, currentWeek=20, session=session)
    session.commit()

    sup = [e for e in state.cores_patches_applied if e.get('event') == 'suppression']
    assert len(sup) == 1, "first patch should record one suppression entry"
    assert sup[0]['patch_number'] == 1
    assert sup[0]['core'] in {'cassian', 'pyre', 'aris', 'halverson'}
    assert state.suppression_window_ends_week == 20 + a.SUPPRESSION_WINDOW_WEEKS
    assert state.threshold == int(threshBefore * a.SUPPRESSION_THRESHOLD_BUMP), "threshold reinforced"
    assert state.last_reset_week == 20, "warning cycle re-armed"
    # Over-cap fuel drained on every row.
    carries = [r.over_cap_carry for r in session.query(PlayerAttention).filter_by(season=season)]
    assert all(abs(c - 200.0 * a.SUPPRESSION_AGGREGATE_DAMP) < 1e-6 for c in carries), "carry drained"

    # Status during the window: number-free 'stabilizing' override.
    status = a.getCriticalityStatus(season, week=21)
    assert status['status'] == 'stabilizing'
    assert status['inSuppression'] is True
    assert status['patchesApplied'] == 1
    assert status['activeCore'] == sup[0]['core']
    assert all(ch not in status['description'] for ch in '0123456789'), "status text must carry no numbers"

    # Multiplier during the window is the floored value.
    assert a.getCriticalityMultiplier(season, week=21) == a.INSTABILITY_SUPPRESSED

    # Cap: keep forcing crossings. Only SUPPRESSION_MAX_PER_SEASON patches land.
    for wk in range(25, 40):
        a._suppressCriticality(state, currentWeek=wk, session=session)
    session.commit()
    sup = [e for e in state.cores_patches_applied if e.get('event') == 'suppression']
    assert len(sup) == a.SUPPRESSION_MAX_PER_SEASON, \
        f"cap not enforced: {len(sup)} patches vs cap {a.SUPPRESSION_MAX_PER_SEASON}"
    print(f"  ok: suppression mechanics + cap ({a.SUPPRESSION_MAX_PER_SEASON}/season)")


def testStatusBands(session):
    import managers.anomalyManager as a
    from database.models import LeagueAnomalyState

    season = 77
    state = LeagueAnomalyState(season=season, aggregate_score=0.0, threshold=1000,
                               thinnings_this_season=0, cores_patches_applied=[])
    session.add(state)
    session.commit()

    cases = [
        (0.10, 'dormant'),
        (a.WARNING_LOW_THRESHOLD + 0.01, 'stirring'),
        (a.WARNING_HIGH_THRESHOLD + 0.01, 'unstable'),
        (1.05, 'critical'),
    ]
    for ratio, expected in cases:
        state.aggregate_score = ratio * state.threshold
        session.commit()
        got = a.getCriticalityStatus(season, week=10)['status']
        assert got == expected, f"ratio {ratio:.2f} → {got}, expected {expected}"
        # No band description leaks a number.
        desc = a.getCriticalityStatus(season, week=10)['description']
        assert all(ch not in desc for ch in '0123456789'), f"numbers leaked in '{desc}'"
    print("  ok: qualitative status bands (dormant/stirring/unstable/critical, number-free)")


def testTriggerPathFiresOneSuppression(session):
    """End-to-end: a gated crossing in _updateLeagueAggregate fires exactly one
    suppression (not a Criticality) and goes quiet."""
    import managers.anomalyManager as a
    from constants import ANOMALY_CRITICALITY_ENABLED
    from database.models import LeagueAnomalyState, PlayerAttention

    assert ANOMALY_CRITICALITY_ENABLED is False, "test assumes the gated tease state"
    season = 55
    state = LeagueAnomalyState(season=season, aggregate_score=0.0, threshold=100,
                               thinnings_this_season=0, cores_patches_applied=[])
    session.add(state)
    # Carry that recomputes well over the small threshold.
    session.add(PlayerAttention(player_id=10, season=season,
                                score=150.0, over_cap_carry=300.0, peak_score=150.0))
    session.commit()

    a._updateLeagueAggregate(session, season, week=20)
    session.commit()

    refreshed = session.query(LeagueAnomalyState).filter_by(season=season).first()
    assert refreshed.thinnings_this_season == 0, "no real Criticality should fire while gated"
    sup = [e for e in (refreshed.cores_patches_applied or []) if e.get('event') == 'suppression']
    assert len(sup) == 1, "exactly one suppression beat from the crossing"
    assert refreshed.suppression_window_ends_week == 20 + a.SUPPRESSION_WINDOW_WEEKS
    print("  ok: _updateLeagueAggregate fires one suppression (no Criticality) while gated")


def main():
    if os.path.exists('/data'):
        print("SKIP: /data exists on this host — would target the prod volume, not a temp DB")
        return

    tmp = tempfile.mkdtemp(prefix='floos_anomtest_')
    os.environ['DATABASE_DIR'] = tmp

    # Import AFTER DATABASE_DIR is set so the engine points at the temp DB.
    from database.connection import engine, get_session
    from database.models import Base
    Base.metadata.create_all(bind=engine)

    print("P3 anomaly suppression tests")
    testHelpers()
    testInstabilityDial()

    session = get_session()
    try:
        testSuppressionMechanicsAndCap(session)
        testStatusBands(session)
        testTriggerPathFiresOneSuppression(session)
    finally:
        session.close()

    print("ALL PASSED")


if __name__ == '__main__':
    main()
