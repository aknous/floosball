#!/usr/bin/env python3
"""QB sneak — situational gating and concept selection.

The sneak's risk is that it leaks OUT of short yardage: it's a run concept, and
run concepts are picked by a weighted draw, so a bug that lets it into the normal
mix would have QBs sneaking on 1st-and-10 from their own 20. These tests pin the
gate and pin the selection.

The yardage shape (high floor, no breakaway) is verified separately against sim
data — see docs/PLAYBOOK_PLAN.md; a full Play object is too heavy to stub here.
"""

import sys, os, types
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Same circular-import dance as test_play_calling.py: seasonManager annotates
# with FloosGame.Game at class-definition time.
_stub = types.ModuleType('floosball_game')
class _GameStub: pass
_stub.Game = _GameStub
sys.modules['floosball_game'] = _stub
import managers.timingManager   # noqa: F401  (loads managers/__init__ against the stub)
del sys.modules['floosball_game']
import floosball_game as FloosGame   # noqa: E402

from types import SimpleNamespace    # noqa: E402
from game_rules import GameRules     # noqa: E402
from constants import (              # noqa: E402
    QB_SNEAK_MAX_YTG, QB_SNEAK_GOAL_LINE_YTE, QB_SNEAK_MIN_DOWN,
    QB_SNEAK_GAIN_MAX, QB_SNEAK_SUCCESS_MIN, QB_SNEAK_SUCCESS_MAX,
    RUN_CONCEPTS,
)


def _attrs(**kw):
    base = dict(power=80, discipline=80, speed=80, agility=80, vision=80,
                creativity=80, focus=80, blocking=80, playMakingAbility=80)
    base.update(kw)
    return SimpleNamespace(**base)


def _player(name='P', **kw):
    a = _attrs(**kw)
    return SimpleNamespace(name=name, attributes=a, gameAttributes=a)


def _team(name='OFF', qb=True, rb=True):
    roster = {'qb': _player('QB') if qb else None,
              'rb': _player('RB') if rb else None,
              'te': _player('TE'), 'wr1': _player('W1'),
              'wr2': _player('W2'), 'k': _player('K')}
    return SimpleNamespace(
        name=name, teamName=name, abbr=name[:3],
        coach=SimpleNamespace(aggressiveness=80, offensiveMind=80, adaptability=80,
                              clockManagement=80, scouting=80),
        rosterDict=roster,
        defenseRunCoverageRating=75, defensePassRating=75,
        defensePassCoverageRating=75, elo=1500,
    )


def _game(down=3, ytg=1, yte=50, quarter=1, clock=600, qb=True, rb=True):
    g = object.__new__(FloosGame.Game)
    off, dfn = _team('OFF', qb=qb, rb=rb), _team('DEF')
    g.homeTeam, g.awayTeam = off, dfn
    g.offensiveTeam, g.defensiveTeam = off, dfn
    g.homeScore = g.awayScore = 0
    g.homeTimeoutsRemaining = g.awayTimeoutsRemaining = 3
    g.down, g.yardsToFirstDown, g.yardsToEndzone = down, ytg, yte
    g.yardsToSafety = 100 - yte
    g.currentQuarter, g.gameClockSeconds, g.clockRunning = quarter, clock, True
    g.twoMinuteWarningShown, g._clockStoppedByWarning = True, False
    g.gamePressure, g.momentum = 50, 0.0
    g.gameRules = GameRules()
    g.totalPlays = 1
    g.gameFeed = g.highlights = g.leagueHighlights = []
    g.homeOffGameplan = g.awayOffGameplan = None
    g.homeDefGameplan = g.awayDefGameplan = None
    g.timingManager = None
    g.isRegularSeasonGame = False
    g.isTwoPtConv = False
    g.play = None
    return g


# ── The gate ────────────────────────────────────────────────────────────────

def testShortYardageLateDownQualifies():
    assert _game(down=3, ytg=1, yte=50)._isSneakSituation()
    assert _game(down=4, ytg=QB_SNEAK_MAX_YTG, yte=50)._isSneakSituation()


def testEarlyDownDoesNot():
    """The failure mode this whole file exists for: sneaking on 1st-and-10."""
    assert not _game(down=1, ytg=10, yte=50)._isSneakSituation()
    assert not _game(down=2, ytg=1, yte=50)._isSneakSituation()


def testLongYardageDoesNot():
    assert not _game(down=3, ytg=QB_SNEAK_MAX_YTG + 1, yte=50)._isSneakSituation()
    assert not _game(down=4, ytg=8, yte=50)._isSneakSituation()


def testGoalLineQualifiesOnAnyDown():
    """1st-and-goal from the 1 is a sneak spot, down notwithstanding."""
    assert _game(down=1, ytg=10, yte=QB_SNEAK_GOAL_LINE_YTE)._isSneakSituation()
    assert not _game(down=1, ytg=10, yte=QB_SNEAK_GOAL_LINE_YTE + 3)._isSneakSituation()


def testNoQbNoSneak():
    assert not _game(down=3, ytg=1, qb=False)._isSneakSituation()


def testHurryUpSuppressesIt():
    """A sneak burns clock and stays in bounds — the opposite of a 2-minute drill."""
    g = _game(down=3, ytg=1, quarter=4, clock=90)
    assert g._isHurryUp(), 'harness should be in hurry-up for this to mean anything'
    assert not g._isSneakSituation()


# ── Concept selection ───────────────────────────────────────────────────────

def testSneakNeverSelectedOutsideItsSituation():
    g = _game(down=1, ytg=10, yte=50)
    picks = {g._selectRunConcept() for _ in range(400)}
    assert 'sneak' not in picks, f'sneak leaked into the normal mix: {picks}'


def testSneakIsSelectableInItsSituation():
    g = _game(down=4, ytg=1, yte=50)
    picks = [g._selectRunConcept() for _ in range(400)]
    assert 'sneak' in picks, 'sneak never called on 4th-and-1'
    # It competes rather than dominating — a bruising back still gets carries.
    share = picks.count('sneak') / len(picks)
    assert 0.10 < share < 0.85, f'sneak share {share:.0%} is not a competing call'


def testOtherConceptsSurviveShortYardage():
    g = _game(down=3, ytg=1, yte=50)
    picks = {g._selectRunConcept() for _ in range(400)}
    assert 'power' in picks, 'power should still be the staple in short yardage'


# ── Shape guards ────────────────────────────────────────────────────────────

def testSneakConceptIsConfiguredAsInteriorAndUndeceptive():
    c = RUN_CONCEPTS['sneak']
    assert c['base'] == 0.0, 'base must stay 0 — selection is injected situationally'
    assert c['deception'] == 0.0, 'everyone knows a sneak is coming'
    assert c['gaps'] == {'A-gap': 1.00}, 'a sneak goes straight ahead'
    assert c['edge']['runFocus'] < RUN_CONCEPTS['power']['edge']['runFocus'], \
        'a stacked box should punish the sneak harder than it punishes power'


def testSneakCannotBreakLong():
    """The ceiling is the point: a sneak falls forward, it does not house-call."""
    assert QB_SNEAK_GAIN_MAX <= 5
    assert 0 < QB_SNEAK_SUCCESS_MIN < QB_SNEAK_SUCCESS_MAX <= 100
