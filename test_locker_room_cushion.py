"""
THE LOCKER ROOM ABSORBS SETBACKS, NEVER GAINS, AND NEVER MOMENTUM.

Owner, 2026-10-30: the flat rating edge alone "doesn't move the needle". The Locker Room's
second job is LOCKER_ROOM_SETBACK_CUSHION, the share of every confidence / determination
LOSS its players take that it absorbs: an in-game mistake, a losing streak's post-game hit,
a hot team's complacency drift, a toxic room's pull, and a cold stretch of the form layer.

Two things must hold for that to be safe:
  - a GAIN is never cushioned, or the facility would slow a team's hot streak too;
  - momentum (source='momentum') is never cushioned, because its offset is re-targeted every
    play and taken back out before postgame by applying the difference. A cushioned removal
    would leave confidence behind that momentum put there.

Run with pytest.
"""
from types import SimpleNamespace

import pytest

from constants import LOCKER_ROOM_SETBACK_CUSHION, FACILITY_MAX_LEVEL
from floosball_player import Player  # before floosball_team: the two import each other
from floosball_team import Team


def _team(level, teamId=2):
    t = Team.__new__(Team)
    t.id = teamId
    t.facilities = {'locker_room': level}
    return t


def _player(team):
    p = Player.__new__(Player)
    p.team = team
    p.gameAttributes = SimpleNamespace(confidenceModifier=0.0, determinationModifier=0.0,
                                       resilience=80, selfBelief=80)
    p.updateInGameRating = lambda: None
    return p


@pytest.fixture(autouse=True)
def _noForce(monkeypatch):
    monkeypatch.delenv('FLOOS_FACILITY_FORCE', raising=False)


def testTheCushionRisesWithEveryLevel():
    vals = [_team(l).setbackCushion() for l in range(FACILITY_MAX_LEVEL + 1)]
    assert vals == LOCKER_ROOM_SETBACK_CUSHION
    assert vals[0] == 0.0
    assert all(b > a for a, b in zip(vals, vals[1:]))


def testALossIsCushionedAndAGainIsNot():
    top = LOCKER_ROOM_SETBACK_CUSHION[FACILITY_MAX_LEVEL]
    p = _player(_team(FACILITY_MAX_LEVEL))
    p.updateInGameConfidence(-0.10, source='mistake')
    assert p.gameAttributes.confidenceModifier == pytest.approx(-0.10 * (1 - top))
    p.updateInGameDetermination(-0.10)
    assert p.gameAttributes.determinationModifier == pytest.approx(-0.10 * (1 - top))

    q = _player(_team(FACILITY_MAX_LEVEL))
    q.updateInGameConfidence(0.10)
    q.updateInGameDetermination(0.10)
    assert q.gameAttributes.confidenceModifier == pytest.approx(0.10)
    assert q.gameAttributes.determinationModifier == pytest.approx(0.10)


def testNoLockerRoomChangesNothing():
    p = _player(_team(0))
    p.updateInGameConfidence(-0.10)
    assert p.gameAttributes.confidenceModifier == pytest.approx(-0.10)


def testMomentumComesBackOutExactly():
    p = _player(_team(FACILITY_MAX_LEVEL))
    for target in (0.12, -0.20, 0.05, 0.0):
        cur = p.gameAttributes.confidenceModifier
        p.updateInGameConfidence(target - cur, source='momentum')
        p.updateInGameDetermination(target - p.gameAttributes.determinationModifier, source='momentum')
    assert p.gameAttributes.confidenceModifier == pytest.approx(0.0)
    assert p.gameAttributes.determinationModifier == pytest.approx(0.0)


def testAFreeAgentHasNoCushion():
    p = _player('Free Agent')
    p.updateInGameConfidence(-0.10)
    assert p.gameAttributes.confidenceModifier == pytest.approx(-0.10)


def testTheForceSwitchReadsTheLockerRoomToo(monkeypatch):
    monkeypatch.setenv('FLOOS_FACILITY_FORCE', 'locker_room')
    assert _team(0, teamId=4).setbackCushion() == LOCKER_ROOM_SETBACK_CUSHION[FACILITY_MAX_LEVEL]
    assert _team(5, teamId=5).setbackCushion() == 0.0
