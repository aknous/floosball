"""A re-sign runs as long as the team plan wants the player (owner, 2026-11-13: "teams
should re-sign players for the amount of time that fits their plans").

The Beans re-signed Dew Stone (RB, 79) for two seasons, a tier roll, while their plan had
their prospect Zeal Fletcher taking the slot after one: promoting Fletcher would have meant
cutting Stone a year into the deal and paying the fee. The re-sign read now records how
many seasons the plan keeps him in his slot, and `payroll.contractTerm` signs for that.

Run: .venv/bin/python -m pytest -q test_plan_resign_term.py
"""
import logging
logging.disable(logging.WARNING)

from types import SimpleNamespace

from floosball_player import Position
from managers import payroll
from test_rookie_draft import FakePlayer, FakeTeam, Harness
from test_team_plan_resign import Brain, _freeAgent, _starter


class CreditBrain(Brain):
    """The plan-read test brain, with a results credit for named players."""
    credit = {}

    def _resultsCredit(self, starter, team=None, coach=None):
        return float(self.credit.get(starter.name, 0.0))


def _read(team, ratings, pool=(), prospects=(), credit=None):
    h = Harness([])
    h.freeAgents = list(pool)
    team.prospects = list(prospects)
    brain = CreditBrain(h, ratings, [team])
    brain.credit = dict(credit or {})
    brain.planContext = {'faOrder': [team], 'intent': {}, 'draftees': [], 'shift': 1}
    walkers = [p for p in team.rosterDict.values() if p is not None]
    ranked = brain.rankResignCandidates(walkers, team=team)
    return [p.name for p, _v in ranked], brain.planResignTerms


def _pm(entries):
    return SimpleNamespace(_planResignTerms=entries)


def _player(pid=1, longevity=12, seasonsPlayed=5):
    return SimpleNamespace(id=pid, seasonsPlayed=seasonsPlayed,
                           attributes=SimpleNamespace(longevity=longevity))


def test_the_beans_case_a_starter_kept_until_his_prospect_takes_over_signs_for_one_season():
    team = FakeTeam(7, 'Beans')
    team.rosterDict = {'rb': _starter(241, 79, Position.RB, name='Dew Stone')}
    kid = FakePlayer(499, 76, Position.RB, 'Zeal Fletcher'); kid.prospect_seasons = 0
    kept, terms = _read(team, {'Dew Stone': 77.5, 'Zeal Fletcher': [79.0, 80.9, 82.0]},
                        pool=[_freeAgent(800, 70, Position.RB, 'FA 70')], prospects=[kid],
                        credit={'Dew Stone': 4.1})
    assert kept == ['Dew Stone'], kept
    assert terms.get(241) == (1, 3, 4.1), terms
    print("PASS the plan keeps him one season, then his prospect takes the slot")


def test_a_starter_the_plan_keeps_through_the_horizon_is_recorded_for_all_of_it():
    team = FakeTeam(1, 'Club')
    team.rosterDict = {'qb': _starter(10, 86, name='Moonshine')}
    kept, terms = _read(team, {}, pool=[_freeAgent(800, 79, Position.QB, 'FA 79')])
    assert kept == ['Moonshine'] and terms.get(10) == (3, 3, 0.0), (kept, terms)
    print("PASS a starter held for the whole horizon is recorded as such")


def test_the_term_is_the_smaller_of_the_roll_and_the_plan():
    p = _player()
    assert payroll.planFittedTerm(_pm({1: (14, 1, 3)}), p, 14, roll=2) == 1
    assert payroll.planFittedTerm(_pm({1: (14, 2, 3)}), p, 14, roll=5) == 2
    # the plan never lengthens a deal: kept for the whole horizon, the roll stands
    assert payroll.planFittedTerm(_pm({1: (14, 3, 3)}), p, 14, roll=1) == 1
    # held through the horizon: the plan sees no replacement, so a long star deal stands
    assert payroll.planFittedTerm(_pm({1: (14, 3, 3)}), p, 14, roll=5) == 5
    print("PASS the term is min(roll, the seasons the plan keeps him)")


def test_no_plan_record_or_another_seasons_keeps_the_tier_roll():
    p = _player()
    assert payroll.planFittedTerm(_pm({}), p, 14, roll=2) == 2
    assert payroll.planFittedTerm(_pm({1: (13, 1, 3)}), p, 14, roll=2) == 2
    # kept against the plan (a fan verdict): the plan has no length for him
    assert payroll.planFittedTerm(_pm({1: (14, 0, 3)}), p, 14, roll=2) == 2
    print("PASS no record, a stale season or no plan run keeps the roll")


def test_a_re_sign_is_sized_on_rating_plus_results_credit():
    """The Waffles' case: Tuck Marberry, QB rated 76 (3 stars, a 1-3 season roll) who
    performed 94-98 four seasons running. Read with his credit he is a 4-star (3-4)."""
    from managers.playerManager import PlayerManager

    class PM:
        _getPlayerTerm = PlayerManager._getPlayerTerm
        tierForRating = staticmethod(PlayerManager.tierForRating)

        def __init__(self, credit):
            self._planResignTerms = {345: (14, 3, 3, credit)}
    from floosball_player import PlayerTier
    qb = SimpleNamespace(id=345, playerRating=76, playerTier=PlayerTier.TierB, seasonsPlayed=4,
                         attributes=SimpleNamespace(longevity=10))
    assert payroll.contractTerm(PM(0.0), qb, 14) == 1      # his seeded 3-star roll
    assert payroll.contractTerm(PM(9.0), qb, 14) >= 3      # read as 85: a 4-star deal
    print("PASS the deal's tier reads the GM's read of him")


def test_contract_term_reads_the_plan():
    class PM:
        _planResignTerms = {1: (14, 1, 3)}

        def _getPlayerTerm(self, player, rng=None):
            return 3
    assert payroll.contractTerm(PM(), _player(), 14) == 1
    assert payroll.contractTerm(PM(), _player(), 15) == 3
    print("PASS contractTerm signs the plan's term")
