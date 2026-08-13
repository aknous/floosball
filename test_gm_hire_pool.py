"""Hiring a GM off the market must not take one another club is already using.

⚠️ THE BUG THIS EXISTS TO PREVENT, caught in a production-shaped dress rehearsal
of the first offseason. `getAvailableCoaches` asks only whether a coach row is
referenced by `Team.coach_id`. Two clubs were holding a coach IN MEMORY whose
link had never been persisted (coach_id NULL), so those rows read as unassigned
— and the next two clubs with a vacancy hired them, putting the same two GM
names on four clubs at once.

The NULL link is a pre-existing fault. What changed is that fired GMs now go
into the pool and the pool is actually HIRED FROM; before, every replacement was
freshly generated, so the rows were never touched and the inconsistency stayed
invisible. A latent data fault plus a new reader is the whole story.

⚠️ These are unit tests on purpose. The rehearsal that found the bug could not
prove the fix: GM turnover is probabilistic (~3% per club per season), the rerun
happened to produce ZERO exits, and "no duplicates" is meaningless when nothing
was hired. A test that only passes when a die rolls the right way is not a test.

Run: .venv/bin/python test_gm_hire_pool.py
"""

import logging

logging.disable(logging.CRITICAL)

from managers.teamManager import TeamManager


class Row:
    """A `coaches` row as getAvailableCoaches returns it."""

    def __init__(self, cid, name, overall=80):
        self.id = cid
        self.name = name
        self.seasons_coached = 2
        self.offensive_mind = 80
        self.defensive_mind = 80
        self.adaptability = 80
        self.aggressiveness = 80
        self.clock_management = 80
        self.player_development = 80
        self.scouting = 80
        self.attitude = 80
        self.fan_trust = 80
        self.overall_rating = overall


class LiveCoach:
    def __init__(self, cid, name):
        self.id = cid
        self.name = name


class Team:
    def __init__(self, name, coach=None):
        self.id = abs(hash(name)) % 1000
        self.name = name
        self.coach = coach


def _manager(teams, pool):
    """A TeamManager with only the collaborators this method touches.

    Built with __new__ so the test doesn't drag in a DB session, a service
    container, or a league.
    """
    tm = TeamManager.__new__(TeamManager)
    tm.teams = teams
    tm.logger = logging.getLogger('test')
    tm.getAvailableCoaches = lambda: pool
    tm.generateCoach = lambda: LiveCoach(999, 'Freshly Generated')
    return tm


def test_a_coach_another_club_is_using_is_not_available():
    """THE REGRESSION. The row looks free (no Team.coach_id points at it) but a
    club is holding it in memory, so hiring it would duplicate the GM."""
    inUse = LiveCoach(20, 'Bobbo Montblanc')
    holder = Team('Midnights', coach=inUse)
    vacancy = Team('Broads')
    # The pool offers the in-use coach AND a genuinely free one.
    tm = _manager([holder, vacancy], [Row(20, 'Bobbo Montblanc'), Row(21, 'Wet Kevin')])

    hired = tm._hireReplacementCoach(vacancy)
    assert hired.id != 20, "hired a GM another club is already using"
    assert hired.id == 21, hired.id
    print("PASS a GM in use elsewhere is not on the market")


def test_the_club_cannot_rehire_the_gm_it_just_lost():
    """They are on the market for everyone else, not for the club that fired them."""
    vacancy = Team('Broads')
    tm = _manager([vacancy], [Row(7, 'Just Fired'), Row(8, 'Someone Else')])

    hired = tm._hireReplacementCoach(vacancy, excludeCoachId=7)
    assert hired.id == 8, hired.id
    print("PASS a club does not re-hire the GM it just let go")


def test_an_empty_market_generates_rather_than_leaving_a_vacancy():
    """A club must never come out of this without a GM."""
    vacancy = Team('Broads')
    tm = _manager([vacancy], [])
    hired = tm._hireReplacementCoach(vacancy)
    assert hired is not None and hired.name == 'Freshly Generated'
    print("PASS an empty market generates a GM rather than leaving a hole")


def test_every_candidate_being_in_use_still_generates():
    """The guard must not be able to starve a club into a vacancy."""
    a = Team('A', coach=LiveCoach(1, 'One'))
    b = Team('B', coach=LiveCoach(2, 'Two'))
    vacancy = Team('C')
    tm = _manager([a, b, vacancy], [Row(1, 'One'), Row(2, 'Two')])
    hired = tm._hireReplacementCoach(vacancy)
    assert hired.name == 'Freshly Generated'
    print("PASS a fully-taken market falls back to generating")


def test_a_hired_gm_carries_their_record_across(  ):
    """The carousel is only interesting if a GM arrives with a history —
    otherwise it is a reroll wearing someone else's name."""
    vacancy = Team('Broads')
    row = Row(11, 'Veteran GM')
    row.seasons_coached = 6
    row.scouting = 93
    tm = _manager([vacancy], [row])
    hired = tm._hireReplacementCoach(vacancy)
    assert hired.seasonsCoached == 6, hired.seasonsCoached
    assert hired.scouting == 93, hired.scouting
    assert hired.name == 'Veteran GM'
    print("PASS a hired GM brings their tenure and attributes with them")


def test_a_broken_pool_query_does_not_leave_a_vacancy():
    vacancy = Team('Broads')
    tm = _manager([vacancy], [])

    def boom():
        raise RuntimeError('no db')
    tm.getAvailableCoaches = boom

    hired = tm._hireReplacementCoach(vacancy)
    assert hired.name == 'Freshly Generated'
    print("PASS an unavailable pool degrades to generating, not to a vacancy")


if __name__ == '__main__':
    tests = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    for fn in tests:
        fn()
    print(f"\nAll {len(tests)} GM hire-pool tests passed.")
