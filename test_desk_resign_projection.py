"""The Front Office desk projects re-signings with the GM's own decision.

Reported (season 11): the desk showed the Strangers keeping their QB (96) and kicker (91)
and losing both receivers and the tight end. It kept each team's two highest-rated
walk-year players, ignoring position; the GM values a kicker at 0.35 of a quarterback and
a receiver at 0.72, so an 80 receiver is worth nearly twice a 91 kicker to it. The desk
now asks `SeasonManager.projectedResigns`, which runs the offseason's own per-team
decision (`_resignDecision`), and calls the rest possible departures, not certain ones.

Run: .venv/bin/python -m pytest -q test_desk_resign_projection.py
"""
import types

from constants import POSITION_VALUE
from floosball_player import Position
from managers.frontOfficeBrain import FrontOfficeBrain
from managers.seasonManager import SeasonManager


class Brain(FrontOfficeBrain):
    """Values are rating x position weight; nobody is replaceable from the market."""

    def __init__(self):
        self._scoutBeliefs = {}

    def decisionValue(self, player, coach=None, rng=None, team=None, **kw):
        return float(player.playerRating) * POSITION_VALUE[player.position.name]

    def upgradeConfidence(self, *a, **kw):
        return 0.0

    def starterStanding(self, *a, **kw):
        return 0.0


def _p(pid, name, rating, pos):
    return types.SimpleNamespace(id=pid, name=name, playerRating=rating, position=pos,
                                 termRemaining=1, willRetire=False)


def _strangers():
    roster = {
        'qb': _p(312, 'Wispy July', 96, Position.QB),
        'rb': types.SimpleNamespace(id=140, name='Bitmap Forte', playerRating=79,
                                    position=Position.RB, termRemaining=2, willRetire=False),
        'wr1': _p(69, 'Stalae Warlock', 69, Position.WR),
        'wr2': _p(256, 'Humberto Endzone', 80, Position.WR),
        'te': _p(137, 'Azazel Wonderbeak', 79, Position.TE),
        'k': _p(333, 'Guv Branson', 91, Position.K),
    }
    return types.SimpleNamespace(id=1, name='Strangers', rosterDict=roster, prospects=[],
                                 coach=None,
                                 seasonTeamStats={'wins': 18, 'losses': 6, 'winPerc': 0.75,
                                                  'scoreDiff': 200})


def _seasonManager(team, brain):
    sm = SeasonManager.__new__(SeasonManager)
    sm.currentSeason = types.SimpleNamespace(seasonNumber=11, freeAgencyOrder=None)
    sm.serviceContainer = types.SimpleNamespace(
        getService=lambda name: types.SimpleNamespace(teams=[team]))
    sm.leagueManager = types.SimpleNamespace(leagues=[])
    sm.playerManager = types.SimpleNamespace(hasReachedResignLimit=lambda p: False,
                                             expectedDraftees=lambda *a: [])
    sm._foBrainForDesk = lambda: brain
    return sm


def test_theStrangersKeepTheReceiverNotTheKicker():
    team = _strangers()
    projected = _seasonManager(team, Brain()).projectedResigns()
    assert projected[312] is True                 # Wispy July, QB 96
    assert projected[256] is True                 # Humberto Endzone, WR 80
    assert projected[333] is False                # Guv Branson, K 91
    assert projected[137] is False                # Azazel Wonderbeak, TE 79
    assert projected[69] is False                 # Stalae Warlock, WR 69 (under 3 stars)
    assert 140 not in projected                   # not in a walk year


def test_aFailedProjectionIsEmptySoTheDeskCanFallBack():
    sm = _seasonManager(_strangers(), Brain())

    def broken():
        raise RuntimeError('no brain')
    sm._foBrainForDesk = broken
    assert sm.projectedResigns() == {}


def test_theOffseasonBrainStartsFromTheDesksScoutingReads(monkeypatch):
    sm = SeasonManager.__new__(SeasonManager)
    sm.currentSeason = types.SimpleNamespace(seasonNumber=11)
    sm.playerManager = None
    desk = Brain()
    desk._scoutBeliefs[('gm', 333)] = 1.7
    sm._foDeskBrain = (11, 0.0, desk)
    monkeypatch.setattr(SeasonManager, '_buildPerformanceMap', lambda self: {})
    import constants
    monkeypatch.setattr(constants, 'SENTIMENT_ENABLED', False)
    brain = sm._foBrainForOffseason()
    assert brain._scoutBeliefs.get(('gm', 333)) == 1.7
    # The desk now reuses the offseason brain rather than building its own.
    assert sm._foBrainForDesk() is brain


def test_aNewWeekIsANewProjection():
    """A time-only cache carried one season's projection into the next, so the desk
    fell back to the rating guess for every walk-year player it could not find."""
    team = _strangers()
    sm = _seasonManager(team, Brain())
    sm.currentSeason.currentWeek = 5
    assert 999 not in sm.projectedResigns()
    team.rosterDict['rb'] = _p(999, 'New Walker', 85, Position.RB)
    assert 999 not in sm.projectedResigns()       # same week: cached
    sm.currentSeason.currentWeek = 6
    assert 999 in sm.projectedResigns()
