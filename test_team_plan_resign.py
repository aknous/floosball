"""The re-sign step reads the team plan (docs/TEAM_PLAN.md, stage 2): a walk-year
starter's priority is what keeping him adds to his position's plan over the horizon, so
the team's prospects (and when they take over), an expected rookie and the free agent
left at its pick are all weighed in one comparison.

Run: .venv/bin/python -m pytest -q test_team_plan_resign.py
"""
import logging
logging.disable(logging.WARNING)

from floosball_player import Position
from managers.frontOfficeBrain import FrontOfficeBrain
from test_rookie_draft import FakePlayer, FakeTeam, Harness


class Brain(FrontOfficeBrain):
    def __init__(self, harness, ratings, teams):
        self.playerManager = harness
        self.ratings = ratings
        self.leagueTeams = teams
        self.sentimentMap = {}
        self.preferenceNotes = {}

    def decisionValue(self, player, coach=None, rng=None, team=None, **kw):
        return float(player.playerRating)

    def projectedRating(self, player, seasonsAhead, coach=None, team=None):
        r = self.ratings.get(player.name, player.playerRating)
        return float(r[min(len(r), seasonsAhead) - 1] if isinstance(r, list) else r)

    def _ceilingRating(self, player, team=None):
        return self.projectedRating(player, 3)

    def sideTilt(self, team, coach=None):
        return 0.0

    def willSignWith(self, fa, team):
        return True

    def worthResigningOnStars(self, player, coach=None, team=None):
        return True

    def _resultsCredit(self, starter, team=None, coach=None):
        return 0.0

    def classifyArc(self, player):
        return 'prime'

    def _leagueTeams(self):
        return self.leagueTeams


def _starter(pid, rating, position=Position.QB, name='Starter', term=1):
    p = FakePlayer(pid, rating, position, name)
    p.termRemaining, p.willRetire = term, False
    return p


def _freeAgent(pid, rating, position, name):
    fa = FakePlayer(pid, rating, position, name)
    fa.team, fa.willRetire = 'Free Agent', False
    return fa


def _decide(team, ratings, pool=(), prospects=()):
    h = Harness([])
    h.freeAgents = list(pool)
    team.prospects = list(prospects)
    brain = Brain(h, ratings, [team])
    brain.planContext = {'faOrder': [team], 'intent': {}, 'draftees': [], 'shift': 1}
    walkers = [p for p in team.rosterDict.values() if p is not None]
    ranked = brain.rankResignCandidates(walkers, team=team)
    return [p.name for p, _v in ranked], brain.lastCoverage


def test_a_starter_better_than_the_market_and_the_pipeline_is_kept():
    team = FakeTeam(1, 'Club')
    team.rosterDict = {'qb': _starter(10, 86, name='Moonshine')}
    kept, _cov = _decide(team, {}, pool=[_freeAgent(800, 79, Position.QB, 'FA 79')])
    assert kept == ['Moonshine']
    print("PASS a starter better than the market and the pipeline is kept")


def test_a_starter_the_market_beats_at_the_pick_walks():
    team = FakeTeam(1, 'Club')
    team.rosterDict = {'qb': _starter(10, 76, name='Average QB')}
    kept, _cov = _decide(team, {}, pool=[_freeAgent(800, 84, Position.QB, 'FA 84')])
    assert kept == []
    print("PASS a starter the market beats at the pick walks")


def test_a_starter_a_prospect_takes_over_from_walks_and_the_prospect_is_the_coverage():
    """The Melons' case the plan was built for: the starter walks because the prospect
    takes over, and that is recorded so the FA draft honors it."""
    from constants import PROSPECT_DEVELOPMENT_WINDOW
    team = FakeTeam(1, 'Club')
    team.rosterDict = {'qb': _starter(10, 80, name='Walker')}
    kid = FakePlayer(950, 78, Position.QB, 'Kid'); kid.prospect_seasons = PROSPECT_DEVELOPMENT_WINDOW - 2
    kept, cov = _decide(team, {'Kid': [81, 84, 86]}, pool=[_freeAgent(800, 70, Position.QB, 'FA 70')],
                        prospects=[kid])
    assert kept == [] and cov.get(10) is kid, (kept, cov)
    print("PASS a starter his prospect takes over from walks, with the coverage recorded")


def test_with_no_plan_context_the_old_comparison_runs():
    team = FakeTeam(1, 'Club')
    team.rosterDict = {'qb': _starter(10, 86, name='Moonshine')}
    h = Harness([])
    brain = Brain(h, {}, [team])
    brain.upgradeConfidence = lambda *a, **k: 0.0
    brain.starterStanding = lambda *a, **k: 0.0
    ranked = brain.rankResignCandidates([team.rosterDict['qb']], team=team)
    assert [p.name for p, _v in ranked] == ['Moonshine']
    print("PASS without a plan context the old comparison runs")
