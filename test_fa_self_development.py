"""Unrostered players train off their own mental makeup, never decay.

Regression for the free-agent development penalty: unrostered players fell to a
default coachDevRating of 50, giving devBias -1 — worse than the worst possible
coach (60 -> 0), so an unsigned player actively decayed. Harmless while most
players were rostered; a real problem under AFO Part F where every new player
enters the FA pool. See docs/AUTONOMOUS_FRONT_OFFICE_PLAN.md Part F.
"""

from player_development import PlayerDevelopment as PD
from constants import FA_SELF_DEV_ATTRS


class _Attrs:
    def __init__(self, discipline=78, focus=78, resilience=70, selfBelief=70):
        self.discipline = discipline
        self.focus = focus
        self.resilience = resilience
        self.selfBelief = selfBelief


class _Player:
    def __init__(self, **kw):
        self.attributes = _Attrs(**kw)


def _coachBias(rating):
    """The coached formula, for comparison."""
    return round((rating - 60) / 10)


def test_unrostered_never_decays():
    """The actual bug: no makeup, however poor, may produce a negative bias."""
    worst = _Player(discipline=1, focus=1, resilience=1, selfBelief=1)
    assert PD.selfDevelopmentBias(worst) >= 0
    # and the old -1 default is unreachable now
    assert PD.selfDevelopmentBias(worst) > -1
    print("PASS an unsigned player never decays (was devBias -1)")


def test_self_drive_scales_with_mentals():
    lazy = _Player(discipline=60, focus=60, resilience=60, selfBelief=60)
    driven = _Player(discipline=95, focus=95, resilience=95, selfBelief=95)
    assert PD.selfDevelopmentBias(driven) > PD.selfDevelopmentBias(lazy)
    print(f"PASS self-drive scales with mentals "
          f"(lazy {PD.selfDevelopmentBias(lazy):+d}, driven {PD.selfDevelopmentBias(driven):+d})")


def test_self_training_is_damped_vs_coaching():
    """Training alone must not beat being coached by an equivalent staff, or
    there'd be no reason to want a good developer."""
    for level in (70, 80, 90, 100):
        player = _Player(discipline=level, focus=level, resilience=level, selfBelief=level)
        assert PD.selfDevelopmentBias(player) <= _coachBias(level), level
    print("PASS self-training never beats an equivalently-rated coach")


def test_league_average_lands_around_plus_one():
    """Sanity on the tuning: the typical free agent should improve slightly,
    sitting between the worst coach (0) and a neutral one (+2)."""
    avg = _Player()   # league means: 78/78/70/70
    bias = PD.selfDevelopmentBias(avg)
    assert 0 <= bias <= 2, bias
    print(f"PASS league-average free agent develops at {bias:+d} (worst coach 0, neutral coach +2)")


def test_missing_attributes_are_safe():
    class NoAttrs:
        attributes = None

    class Empty:
        class attributes:
            pass

    assert PD.selfDevelopmentBias(NoAttrs()) == 0
    assert PD.selfDevelopmentBias(Empty()) == 0
    print("PASS missing/empty attributes degrade to 0, not a crash")


def test_uses_the_documented_attribute_set():
    """Guard the constant against silent drift — these four are the makeup that
    plausibly drives solo training."""
    assert set(FA_SELF_DEV_ATTRS) == {'discipline', 'focus', 'resilience', 'selfBelief'}
    print(f"PASS self-development reads {', '.join(FA_SELF_DEV_ATTRS)}")


if __name__ == '__main__':
    tests = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    for fn in tests:
        fn()
    print(f"\nAll {len(tests)} FA self-development tests passed.")
