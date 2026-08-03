"""GM turnover — fired / leave / retire (AFO plan Part C).

Asserts the behaviours the design promises: competence is real job security,
a first-year GM isn't fired for an inherited roster, goodwill softens but never
nullifies, departure is record-independent, and the unbuilt sentiment layer is a
neutral no-op rather than a hidden term.
"""

from random import Random

import constants
from managers.gmTurnover import GmTurnover, teamWinPct, EXIT_FIRED, EXIT_LEFT
from floosball_coach import Coach


class FakeTeam:
    def __init__(self, wins, losses, name='Testers'):
        self.name = name
        self.seasonTeamStats = {'wins': wins, 'losses': losses}


def _coach(seasons=5, attitude=80):
    c = Coach().generateAttributes()
    c.seasonsCoached = seasons
    c.attitude = attitude
    return c


def test_competence_is_job_security():
    """At or above the baseline win rate there is NO fire roll at all — a
    winning GM can't be unlucky."""
    t = GmTurnover()
    for wins, losses in [(14, 14), (17, 11), (22, 6)]:
        assert t.fireChance(FakeTeam(wins, losses), _coach()) == 0.0, (wins, losses)
    print("PASS a .500-or-better GM is never rolled on")


def test_disaster_seasons_are_dangerous():
    t = GmTurnover()
    bad = t.fireChance(FakeTeam(4, 24), _coach())
    poor = t.fireChance(FakeTeam(11, 17), _coach())
    assert bad > poor > 0, (bad, poor)
    assert bad >= 0.5, bad
    print(f"PASS bad seasons are dangerous (4-24 {bad:.0%}, 11-17 {poor:.0%})")


def test_tenure_grace_protects_a_new_gm():
    """A GM inherited the roster and hasn't had an offseason to shape it."""
    t = GmTurnover()
    rookieGm = _coach(seasons=constants.GM_FIRE_GRACE_SEASONS)
    veteranGm = _coach(seasons=constants.GM_FIRE_GRACE_SEASONS + 1)
    assert t.fireChance(FakeTeam(4, 24), rookieGm) == 0.0
    assert t.fireChance(FakeTeam(4, 24), veteranGm) > 0
    print("PASS a first-season GM isn't fired for an inherited roster")


def test_goodwill_softens_but_never_nullifies():
    """Locker-room standing buys rope — it must not make a GM unfireable."""
    t = GmTurnover()
    beloved = t.fireChance(FakeTeam(4, 24), _coach(attitude=100))
    disliked = t.fireChance(FakeTeam(4, 24), _coach(attitude=60))
    assert disliked > beloved > 0, (disliked, beloved)
    print(f"PASS goodwill softens without nullifying "
          f"(attitude 100 {beloved:.0%} vs attitude 60 {disliked:.0%})")


def test_departure_is_independent_of_record():
    """The plan wants a hostile fanbase able to drive out a WINNING GM."""
    t = GmTurnover()
    winning = t.leaveChance(FakeTeam(22, 6), _coach())
    losing = t.leaveChance(FakeTeam(4, 24), _coach())
    assert winning == losing > 0, (winning, losing)
    print(f"PASS departure ignores record (both {winning:.0%})")


def test_sentiment_is_a_neutral_noop_until_part_d():
    """Sentiment isn't built. Neutral must change nothing, and the seam must
    already respond so Part D is a wiring job, not a restructure."""
    t = GmTurnover()
    team, coach = FakeTeam(11, 17), _coach()

    assert t.fireChance(team, coach, sentiment=0.0) == t.fireChance(team, coach)
    assert t.fireChance(team, coach, sentiment=-1.0) > t.fireChance(team, coach, 0.0)
    assert t.leaveChance(team, coach, sentiment=-1.0) > t.leaveChance(team, coach, 0.0)
    # Supportive fans must not manufacture a firing out of nothing.
    assert t.fireChance(FakeTeam(22, 6), coach, sentiment=1.0) == 0.0
    print("PASS sentiment is neutral today and already wired for Part D")


def test_fire_takes_precedence_over_leave():
    """Rolling both would double the exit rate; a fired GM's story is firing."""
    class AlwaysFire(GmTurnover):
        def fireChance(self, *a, **k): return 1.0
        def leaveChance(self, *a, **k): return 1.0

    assert AlwaysFire().evaluateExit(FakeTeam(4, 24), _coach()) == EXIT_FIRED
    print("PASS fire is resolved before leave")


def test_disabled_flag_stops_all_exits():
    original = constants.GM_TURNOVER_ENABLED
    try:
        constants.GM_TURNOVER_ENABLED = False
        import importlib, managers.gmTurnover as m
        importlib.reload(m)
        t = m.GmTurnover()
        assert all(t.evaluateExit(FakeTeam(0, 28), _coach()) is None for _ in range(50))
        print("PASS GM_TURNOVER_ENABLED=False stops every exit")
    finally:
        constants.GM_TURNOVER_ENABLED = original
        import importlib, managers.gmTurnover as m
        importlib.reload(m)


def test_league_turnover_lands_in_target_band():
    """The tuning target: a few changes league-wide per season, not a carousel.
    Retirements are extra on top of this."""
    records = [(22, 6), (20, 8), (19, 9), (18, 10), (18, 10), (17, 11), (17, 11),
               (16, 12), (16, 12), (15, 13), (15, 13), (14, 14), (14, 14),
               (13, 15), (13, 15), (12, 16), (12, 16), (11, 17), (11, 17),
               (10, 18), (9, 19), (8, 20), (6, 22), (4, 24)]
    rng = Random(99)
    trials, exits = 800, 0
    for _ in range(trials):
        t = GmTurnover(rng=rng)
        for w, l in records:
            if t.evaluateExit(FakeTeam(w, l), _coach(seasons=rng.randint(2, 9))):
                exits += 1
    perSeason = exits / trials
    assert 2.0 <= perSeason <= 5.0, perSeason
    print(f"PASS league turnover {perSeason:.2f}/season (target 3-5 incl. retirements)")


def test_win_pct_handles_an_unplayed_season():
    """A team with no games must not read as a catastrophe."""
    assert teamWinPct(FakeTeam(0, 0)) == 0.5
    assert teamWinPct(FakeTeam(14, 14)) == 0.5

    class NoStats:
        name = 'X'
    assert teamWinPct(NoStats()) == 0.5
    print("PASS an unplayed season reads as neutral, not a disaster")


def test_exit_descriptions_read_naturally():
    t = GmTurnover()
    coach = _coach(seasons=3)
    coach.name = 'Vince Lombardi'
    team = FakeTeam(4, 24, name='Broads')

    assert t.describeExit(EXIT_FIRED, coach, team) == 'Broads fire Vince Lombardi after 3 seasons'
    assert t.describeExit(EXIT_LEFT, coach, team) == 'Vince Lombardi steps down as Broads GM after 3 seasons'

    solo = _coach(seasons=1)
    solo.name = 'Solo'
    assert 'after 1 season' in t.describeExit(EXIT_FIRED, solo, team)
    print("PASS exit lines read naturally and pluralise correctly")


if __name__ == '__main__':
    tests = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    for fn in tests:
        fn()
    print(f"\nAll {len(tests)} GM turnover tests passed.")
