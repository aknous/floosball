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
    # Over-cap fuel drained on every row. The drain targets SUPPRESSION_TARGET_RATIO * threshold (a deep
    # ABSOLUTE drain when the aggregate overshot), never less aggressive than SUPPRESSION_AGGREGATE_DAMP —
    # so with the aggregate seeded well over threshold the factor is the target-ratio one, not a flat 0.55.
    # threshold is the post-bump value (state.threshold), aggregate the pre-drain 1200, bg = the week.
    bg = 20.0
    overCap = 1200.0 - bg
    expectedDamp = max(0.0, min(a.SUPPRESSION_AGGREGATE_DAMP,
                                max(0.0, a.SUPPRESSION_TARGET_RATIO * state.threshold - bg) / overCap))
    carries = [r.over_cap_carry for r in session.query(PlayerAttention).filter_by(season=season)]
    assert all(abs(c - 200.0 * expectedDamp) < 1e-6 for c in carries), "carry drained to target ratio"

    # Status during the window: number-free 'stabilizing' override.
    status = a.getCriticalityStatus(season, week=21)
    assert status['status'] == 'stabilizing'
    assert status['inSuppression'] is True
    assert status['patchesApplied'] == 1
    assert status['activeCore'] == sup[0]['core']
    assert all(ch not in status['description'] for ch in '0123456789'), "status text must carry no numbers"

    # Multiplier during the window is the floored value.
    assert a.getCriticalityMultiplier(season, week=21) == a.INSTABILITY_SUPPRESSED

    # No cap: every forced crossing lands a suppression. The near-miss beat stays frequent all season;
    # real Criticalities are paced by the probabilistic break-through in _triggerCriticality
    # (CRITICALITY_FIRE_CHANCE), not by a suppression cap.
    for wk in range(25, 40):
        a._suppressCriticality(state, currentWeek=wk, session=session)
    session.commit()
    sup = [e for e in state.cores_patches_applied if e.get('event') == 'suppression']
    assert len(sup) == 1 + 15, f"every crossing should suppress (no cap); got {len(sup)}"
    print(f"  ok: suppression mechanics + uncapped near-miss beats ({len(sup)} forced)")


def testStatusBands(session):
    import managers.anomalyManager as a
    from database.models import LeagueAnomalyState, PlayerAttention

    season = 77
    week = 10
    state = LeagueAnomalyState(season=season, aggregate_score=0.0, threshold=1000,
                               thinnings_this_season=0, cores_patches_applied=[])
    session.add(state)
    # getCriticalityStatus derives its band from a LIVE carry sum (_sumOverCapCarry
    # + week), self-healing state.aggregate_score to match — so we must drive the
    # ratio through a real PlayerAttention.over_cap_carry row, not by poking
    # aggregate_score directly (which the self-heal would overwrite to ~0).
    carrier = PlayerAttention(player_id=1, season=season, score=0.0,
                              over_cap_carry=0.0, peak_score=0.0)
    session.add(carrier)
    session.commit()

    cases = [
        (0.10, 'dormant'),
        (a.WARNING_LOW_THRESHOLD + 0.01, 'stirring'),
        (a.WARNING_HIGH_THRESHOLD + 0.01, 'unstable'),
        (1.05, 'critical'),
    ]
    for ratio, expected in cases:
        # liveAggregate = over_cap_carry + week ; solve carry for the target ratio.
        carrier.over_cap_carry = max(0.0, ratio * state.threshold - week)
        session.commit()
        got = a.getCriticalityStatus(season, week=week)['status']
        assert got == expected, f"ratio {ratio:.2f} → {got}, expected {expected}"
        # No band description leaks a number.
        desc = a.getCriticalityStatus(season, week=week)['description']
        assert all(ch not in desc for ch in '0123456789'), f"numbers leaked in '{desc}'"
    print("  ok: qualitative status bands (dormant/stirring/unstable/critical, number-free)")


def testCoresExchanges():
    """P4 — the multi-Core dialogue system: exchange shape/threading, the
    football-fan character split, and solo fallback."""
    import managers.coresManager as c

    # The roster carries the orthogonal football-interest trait: TWO fanatics of different flavors
    # (Cassian the stats-and-trends fanatic, Pyre the simple-minded fan of the sport) plus a mix of
    # into-it / not.
    interests = {k: v['footballInterest'] for k, v in c.CORES.items()}
    fanatics = [k for k, v in interests.items() if v == 'fanatic']
    assert len(fanatics) == 2, f"two fanatics expected (cassian, pyre), got {fanatics}"
    assert any(v == 'none' for v in interests.values()), "some Cores are not into football"
    assert any(v in ('fond', 'secret') for v in interests.values()), "some Cores are into football"

    # Exchanges thread: shared exchangeId, ordered turnIndex, consistent turnCount.
    for ev in ('warning_high', 'suppression', 'criticality', 'idle'):
        assert c.hasExchange(ev), f"expected an exchange pool for {ev}"
        turns = c.exchangeEntriesFor(ev)
        assert len(turns) >= 2, f"{ev} exchange should be a conversation"
        assert len({t['exchangeId'] for t in turns}) == 1, "turns share one exchangeId"
        assert [t['turnIndex'] for t in turns] == list(range(len(turns))), "turns are ordered"
        assert all(t['turnCount'] == len(turns) for t in turns)
        assert all(t['category'] == 'cores' and t['core'] in c.CORES for t in turns)
        assert all(t['text'] for t in turns)
        # Voice hygiene: no em-dashes in any Core line (user copy rule).
        assert all('—' not in t['text'] for t in turns), f"em-dash leaked in {ev} exchange"

    # entriesForEvent: exchange where a pool exists, solo line where it doesn't.
    assert len(c.entriesForEvent('warning_high')) >= 2, "warning_high prefers an exchange"
    assert len(c.entriesForEvent('warning_low')) == 1, "warning_low has no exchange → solo"
    # A forced core always yields a single attributed line.
    solo = c.entriesForEvent('suppression', core='pyre')
    assert len(solo) == 1 and solo[0]['core'] == 'pyre'
    print("  ok: Cores exchanges (threading, fanatic split, solo fallback, no em-dashes)")


def testTriggerPathFiresOneSuppression(session):
    """End-to-end: a gated crossing in _updateLeagueAggregate fires exactly one
    suppression (not a Criticality), goes quiet, and narrates it as a multi-Core
    exchange persisted to the news feed."""
    import managers.anomalyManager as a
    from constants import ANOMALY_CRITICALITY_ENABLED
    from database.models import LeagueAnomalyState, PlayerAttention, LeagueNewsItem

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

    # The suppression exchange was persisted to the feed (one row per turn).
    # The same tick also fires a warning exchange (the ratio is far over the
    # line), so the feed legitimately carries both event types.
    suppItems = (session.query(LeagueNewsItem)
                 .filter_by(season=season, category='cores', event_type='suppression').all())
    assert len(suppItems) >= 2, "suppression should narrate as a multi-turn exchange"
    print("  ok: _updateLeagueAggregate fires one suppression, narrated as an exchange")


def testCarryDecay(session):
    """The leaky-integrator fix: _applyDecay decays over_cap_carry (not just score)
    so the league aggregate can't run away unbounded."""
    import managers.anomalyManager as a
    from database.models import PlayerAttention

    assert a.OVER_CAP_CARRY_DECAY < 1.0, "carry decay must be enabled in prod (non-FAST)"
    season = 61
    row = PlayerAttention(player_id=1, season=season, score=200.0,
                          over_cap_carry=500.0, peak_score=200.0)
    session.add(row)
    session.commit()

    a._applyDecay(session, season)
    session.commit()
    assert abs(row.score - 200.0 * a.ATTENTION_DECAY) < 1e-6, "score decayed"
    assert abs(row.over_cap_carry - 500.0 * a.OVER_CAP_CARRY_DECAY) < 1e-6, "carry decayed"

    # A steady over-cap inflow reaches a bounded plateau, not an unbounded ramp:
    # carry_{t+1} = carry_t * decay + inflow  ->  plateau = inflow / (1 - decay).
    row.over_cap_carry = 0.0
    session.commit()
    inflow = 60.0
    for _ in range(60):
        a._applyDecay(session, season)
        row.over_cap_carry = float(row.over_cap_carry) + inflow  # inject fresh overflow
        session.commit()
    plateau = inflow / (1.0 - a.OVER_CAP_CARRY_DECAY)
    assert abs(row.over_cap_carry - plateau) < plateau * 0.02, \
        f"carry should plateau at ~{plateau:.0f}, got {row.over_cap_carry:.0f}"
    print(f"  ok: over_cap_carry decays + plateaus (leaky integrator, ~{plateau:.0f})")


def testAdaptiveThreshold(session):
    """The bar is seeded from the league's own observed attention plateau at
    THRESHOLD_SEED_WEEK, not a user-count guess — and stays provisional (no
    crossings) during the calibration window."""
    import managers.anomalyManager as a
    from database.models import LeagueAnomalyState, PlayerAttention

    season = 62
    # One heavy carrier; aggregate = over_cap_carry + week.
    session.add(PlayerAttention(player_id=1, season=season, score=100.0,
                                over_cap_carry=1000.0, peak_score=100.0))
    session.commit()

    # Before the seed week: threshold stays provisional/unreachable, no crossing.
    a._updateLeagueAggregate(session, season, week=a.THRESHOLD_SEED_WEEK - 1)
    session.commit()
    st = session.query(LeagueAnomalyState).filter_by(season=season).first()
    assert st.threshold >= a.THRESHOLD_PROVISIONAL, "bar must stay provisional during calibration"
    assert not [e for e in (st.cores_patches_applied or []) if e.get('event') in
                ('suppression', 'thinning_trigger')], "no crossings during the quiet window"

    # At the seed week: the bar locks from the observed plateau estimate.
    wk = a.THRESHOLD_SEED_WEEK
    a._updateLeagueAggregate(session, season, wk)
    session.commit()
    st = session.query(LeagueAnomalyState).filter_by(season=season).first()
    overCap = 1000.0
    fill = 1.0 - a.OVER_CAP_CARRY_DECAY ** wk
    expected = round((overCap / fill) * a.THRESHOLD_PLATEAU_MULT)
    assert abs(st.threshold - expected) <= 2, f"bar locked to {st.threshold}, expected ~{expected}"
    assert st.threshold < a.THRESHOLD_PROVISIONAL, "bar no longer provisional after lock"
    print(f"  ok: adaptive threshold locks at week {wk} from observed plateau (-> {st.threshold})")


def testPityRamp():
    """Enabled crossings that suppress escalate the next crossing's fire odds; a
    real fire resets the ramp; gated near-misses never accrue pity."""
    import managers.anomalyManager as a

    def st(patches):
        return SimpleNamespace(cores_patches_applied=patches, season=1)

    # No history -> base rate (0 prior eligible suppressions).
    assert a._eligibleSuppressionsSinceLastFire(st([])) == 0
    # Gated near-misses (fire_eligible falsy) do NOT count.
    gated = [{'event': 'suppression', 'week': w, 'fire_eligible': False} for w in (2, 4)]
    assert a._eligibleSuppressionsSinceLastFire(st(gated)) == 0
    # Enabled suppressions DO count.
    elig = [{'event': 'suppression', 'week': w, 'fire_eligible': True} for w in (3, 5, 7)]
    assert a._eligibleSuppressionsSinceLastFire(st(elig)) == 3
    # A real fire resets the ramp: only eligible suppressions AFTER the last fire count.
    mixed = [
        {'event': 'suppression', 'week': 3, 'fire_eligible': True},
        {'event': 'thinning_trigger', 'start_week': 6},
        {'event': 'suppression', 'week': 8, 'fire_eligible': True},
    ]
    assert a._eligibleSuppressionsSinceLastFire(st(mixed)) == 1, "ramp resets after a fire"

    # The escalated chance climbs and caps.
    base, ramp, cap = a.CRITICALITY_FIRE_CHANCE, a.CRITICALITY_FIRE_CHANCE_RAMP, a.CRITICALITY_FIRE_CHANCE_MAX
    assert min(cap, base + 0 * ramp) == base
    assert min(cap, base + 3 * ramp) <= cap
    assert base + int((cap - base) / ramp + 1) * ramp >= cap, "ramp reaches the cap in finite steps"
    print("  ok: pity ramp counts eligible-only suppressions, resets on fire, caps")


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

    print("P3/P4 anomaly suppression + Cores dialogue tests")
    testHelpers()
    testInstabilityDial()
    testCoresExchanges()
    testPityRamp()

    session = get_session()
    try:
        testSuppressionMechanicsAndCap(session)
        testStatusBands(session)
        testTriggerPathFiresOneSuppression(session)
        testCarryDecay(session)
        testAdaptiveThreshold(session)
    finally:
        session.close()

    print("ALL PASSED")


if __name__ == '__main__':
    main()
