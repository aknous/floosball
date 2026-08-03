"""Coach specialist generation + scouting-report profiles (AFO plan Part B).

Asserts the properties the design actually promises: coaches vary sharply
attribute-to-attribute while landing near-average overall, rare all-around
tails still exist, and the profile is an honest summary rather than a label
forced onto a flat spread.
"""

import numpy as np

from floosball_coach import Coach, buildCoachProfile, profileFromDbRow

ATTRS = Coach._PROFILE_ATTRS


def _sample(n=3000, seed=None):
    return [Coach().generateAttributes(seed=seed) for _ in range(n)]


def _spread(c):
    vals = [getattr(c, a) for a in ATTRS]
    return max(vals) - min(vals)


def test_coaches_are_specialists_not_uniformly_good():
    """The core promise: WIDE variation within a coach, TIGHT variation between
    coaches' aggregates. If these invert, we're back to the old model."""
    coaches = _sample()
    overallSd = np.std([c.overallRating for c in coaches])
    meanSpread = np.mean([_spread(c) for c in coaches])

    assert meanSpread > 15, f"within-coach spread too flat: {meanSpread:.1f}"
    assert overallSd < 8, f"aggregates too spread — coaches still uniform: {overallSd:.1f}"
    assert meanSpread > overallSd * 2, (meanSpread, overallSd)
    print(f"PASS specialists (within-coach spread {meanSpread:.1f} >> overall sd {overallSd:.1f})")


def test_rare_all_around_tails_exist():
    """A small shared component must keep genuine elites and busts possible."""
    overalls = [c.overallRating for c in _sample(4000)]
    elite = sum(1 for o in overalls if o >= 90) / len(overalls)
    bust = sum(1 for o in overalls if o <= 70) / len(overalls)

    assert 0.01 < elite < 0.10, f"elite tail {elite:.1%} outside 1-10%"
    assert 0.01 < bust < 0.12, f"bust tail {bust:.1%} outside 1-12%"
    print(f"PASS rare tails exist (elite {elite:.1%}, bust {bust:.1%})")


def test_attributes_are_largely_independent():
    """Offensive and defensive mind must not move together — that correlation
    is exactly what made the old aggregate meaningful."""
    coaches = _sample()
    off = np.array([c.offensiveMind for c in coaches], dtype=float)
    dfn = np.array([c.defensiveMind for c in coaches], dtype=float)
    r = float(np.corrcoef(off, dfn)[0, 1])

    assert r < 0.35, f"attributes too correlated (r={r:.2f}) — not specialists"
    print(f"PASS offensive/defensive mind largely independent (r={r:.2f})")


def test_seed_still_tiers_the_hire_slate():
    """The hire slate offers premium/mid/budget. Seeding must still shift the
    whole profile, or the vote has nothing to choose between."""
    premium = np.mean([c.overallRating for c in _sample(800, seed=90)])
    budget = np.mean([c.overallRating for c in _sample(800, seed=72)])

    assert premium > budget + 8, (premium, budget)
    print(f"PASS seed still tiers candidates (90 -> {premium:.1f}, 72 -> {budget:.1f})")


def test_fantrust_independent_of_quality():
    """A great coach is as likely to be a populist as a poor one."""
    elite = np.mean([c.fanTrust for c in _sample(1500, seed=95)])
    poor = np.mean([c.fanTrust for c in _sample(1500, seed=65)])

    assert abs(elite - poor) < 4, f"fanTrust tracks quality: {elite:.1f} vs {poor:.1f}"
    print(f"PASS fanTrust independent of quality ({elite:.1f} vs {poor:.1f})")


def test_profile_labels_the_actual_extremes():
    coach = Coach()
    for a in ATTRS:
        setattr(coach, a, 80)
    coach.scouting = 97          # standout
    coach.playerDevelopment = 63  # weakness
    coach.fanTrust = 95           # populist

    p = coach.profile()
    assert p['specialty'] == 'Sharp Eye', p
    assert p['flaw'] == 'Poor Developer', p
    assert p['fanTrustLabel'] == 'Populist', p
    assert set(p['tags']) == {'Sharp Eye', 'Poor Developer', 'Populist'}, p
    print("PASS profile names the real standout, weakness, and fan-trust axis")


def test_flat_coach_reads_as_generalist():
    """No forcing a dramatic label onto an unremarkable coach."""
    coach = Coach()
    for a in ATTRS:
        setattr(coach, a, 80)
    coach.fanTrust = 80

    p = coach.profile()
    assert p['specialty'] is None and p['flaw'] is None, p
    assert p['tags'] == ['Generalist'], p
    print("PASS a flat coach reads as Generalist, not a forced label")


def test_db_row_profile_matches_live_object():
    """The hire slate reads DB rows; it must not drift from the live version."""
    class Row:
        offensive_mind, defensive_mind, adaptability = 97, 80, 80
        aggressiveness, clock_management, player_development = 80, 80, 64
        scouting, attitude, fan_trust = 80, 80, 62

    coach = Coach()
    coach.offensiveMind, coach.defensiveMind, coach.adaptability = 97, 80, 80
    coach.aggressiveness, coach.clockManagement, coach.playerDevelopment = 80, 80, 64
    coach.scouting, coach.attitude, coach.fanTrust = 80, 80, 62

    assert profileFromDbRow(Row()) == coach.profile()
    print("PASS DB-row profile matches the live Coach profile exactly")


def test_every_attribute_can_be_named():
    """No attribute may be missing a label, or a coach gets an empty report."""
    for a in ATTRS:
        assert a in Coach._SPECIALTY_LABELS, a
        assert a in Coach._FLAW_LABELS, a
    print(f"PASS all {len(ATTRS)} attributes have specialty + flaw labels")




def test_profile_leaks_no_rating_numbers():
    """Coach/GM rating values must never reach the client — the profile is the
    entire public surface, so it must be numeral-free."""
    coach = Coach().generateAttributes()
    p = coach.profile()

    numeric = [k for k, v in p.items() if isinstance(v, (int, float))]
    assert not numeric, f"profile leaks raw numbers: {numeric}"
    for t in p['traits']:
        assert set(t.keys()) == {'attr', 'label', 'band'}, t
        assert isinstance(t['band'], str), t
        assert t['band'] in ('Elite', 'Sharp', 'Capable', 'Limited'), t
    print("PASS profile exposes archetypes + bands only, no rating numbers")


def test_bands_match_play_insights_vocabulary():
    """Bands mirror PlayInsightsPanel.coachMindLabel (90/80/70) so a coach can't
    read 'Elite' in one place and 'Sharp' in another."""
    from floosball_coach import attributeBand
    assert attributeBand(95) == 'Elite'
    assert attributeBand(90) == 'Elite'
    assert attributeBand(89) == 'Sharp'
    assert attributeBand(80) == 'Sharp'
    assert attributeBand(79) == 'Capable'
    assert attributeBand(70) == 'Capable'
    assert attributeBand(69) == 'Limited'
    print("PASS bands match the play-insights coach vocabulary exactly")


if __name__ == '__main__':
    tests = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    for fn in tests:
        fn()
    print(f"\nAll {len(tests)} coach profile tests passed.")
