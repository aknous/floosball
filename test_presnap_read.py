#!/usr/bin/env python3
"""Pre-snap recognition — the defense's run/pass commit.

The risk with this layer is that it quietly becomes a league-wide tax on
offense. It is built to be zero-sum: a correct read helps the defense by exactly
as much as a wrong one hurts it, and a league-average defense reads a coin flip.
These tests pin that, plus the leverage gate that keeps it from double-counting
with getDefensiveScheme's situational branch.
"""

import sys, os, types
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

_stub = types.ModuleType('floosball_game')
class _GameStub: pass
_stub.Game = _GameStub
sys.modules['floosball_game'] = _stub
import managers.timingManager   # noqa: F401
del sys.modules['floosball_game']
import floosball_game as FloosGame   # noqa: E402

from types import SimpleNamespace    # noqa: E402
from constants import (              # noqa: E402
    PRESNAP_READ_BASE, PRESNAP_READ_SKILL, PRESNAP_READ_EDGE,
    PRESNAP_LEVERAGE_FLOOR, PRESNAP_OBVIOUS_SHORT, PRESNAP_OBVIOUS_LONG,
    PRESNAP_DISGUISE,
)


def _defender(instinct=80, focus=80):
    a = SimpleNamespace(instinct=instinct, focus=focus)
    return SimpleNamespace(name='D', attributes=a, gameAttributes=a)


def _defTeam(defMind=80, instinct=80, focus=80):
    return SimpleNamespace(
        name='DEF', abbr='DEF',
        coach=SimpleNamespace(defensiveMind=defMind),
        rosterDict={'rb': _defender(instinct, focus), 'qb': _defender(instinct, focus)},
    )


def _play(ytg=7, defMind=80, instinct=80, focus=80, **flags):
    """A Play stubbed down to exactly what _applyPreSnapRead touches."""
    p = object.__new__(FloosGame.Play)
    p.game = SimpleNamespace(yardsToFirstDown=ytg)
    p.defense = _defTeam(defMind, instinct, focus)
    p.insights = {}
    p.preSnapRead = None
    for k in ('isRpo', 'playAction', 'isSneakLook'):
        setattr(p, k, flags.get(k, False))
    p.trickPlay = flags.get('trickPlay', None)
    return p


def _accuracyOf(p, isRun=True, n=4000):
    """Empirical accuracy — the method rolls internally, so sample it."""
    hits = 0
    for _ in range(n):
        scheme = {'runDefMult': 1.0, 'passDefMult': 1.0}
        p.insights = {}
        p._applyPreSnapRead(scheme, isRun=isRun)
        hits += 1 if p.preSnapRead['correct'] else 0
    return hits / n


# ── Leverage (the double-counting guard) ────────────────────────────────────

def testObviousDistancesGiveAlmostNoLeverage():
    """3rd-and-15 is a pass to everyone; being right there isn't recognition,
    and getDefensiveScheme already handles those spots."""
    assert _play(ytg=PRESNAP_OBVIOUS_SHORT)._preSnapLeverage() == PRESNAP_LEVERAGE_FLOOR
    assert _play(ytg=PRESNAP_OBVIOUS_LONG)._preSnapLeverage() == PRESNAP_LEVERAGE_FLOOR
    assert _play(ytg=1)._preSnapLeverage() == PRESNAP_LEVERAGE_FLOOR
    assert _play(ytg=20)._preSnapLeverage() == PRESNAP_LEVERAGE_FLOOR


def testAmbiguousDistanceGivesFullLeverage():
    mid = (PRESNAP_OBVIOUS_SHORT + PRESNAP_OBVIOUS_LONG) / 2
    assert _play(ytg=int(mid))._preSnapLeverage() > 0.9


# ── Zero-sum ────────────────────────────────────────────────────────────────

def testAverageDefenseReadsACoinFlip():
    """The whole neutrality argument rests on this."""
    acc = _accuracyOf(_play(defMind=80, instinct=80, focus=80))
    assert abs(acc - 0.50) < 0.03, f'neutral defense read {acc:.3f}, expected ~0.50'


def testPayoffsAreEqualAndOpposite():
    """Correct and wrong must move the multiplier by the same magnitude, or the
    layer nets a bias even at 50% accuracy."""
    p = _play(ytg=7)
    lev = p._preSnapLeverage()
    swing = PRESNAP_READ_EDGE * lev
    up, down = [], []
    for _ in range(400):
        scheme = {'runDefMult': 1.0, 'passDefMult': 1.0}
        p.insights = {}
        p._applyPreSnapRead(scheme, isRun=True)
        (up if p.preSnapRead['correct'] else down).append(scheme['runDefMult'])
    assert up and down, 'sample should contain both outcomes'
    assert abs(up[0] - (1 + swing)) < 1e-9
    assert abs(down[0] - (1 - swing)) < 1e-9


# ── Skill actually matters ──────────────────────────────────────────────────

def testSharpDefenseReadsBetterThanPoorOne():
    sharp = _accuracyOf(_play(defMind=100, instinct=100, focus=100))
    poor = _accuracyOf(_play(defMind=60, instinct=60, focus=60))
    assert sharp > 0.60, f'elite defense only read {sharp:.3f}'
    assert poor < 0.40, f'poor defense read {poor:.3f} — too good'
    assert sharp - poor > 0.20


def testDefensiveMindHasAPerPlayJob():
    """It previously did nothing after the pre-game plan — this layer is the
    reason it now matters at the snap."""
    hi = _accuracyOf(_play(defMind=100, instinct=80, focus=80))
    lo = _accuracyOf(_play(defMind=60, instinct=80, focus=80))
    assert hi - lo > 0.10


# ── Disguise ────────────────────────────────────────────────────────────────

def testFakesBeatRecognition():
    plain = _accuracyOf(_play(defMind=100, instinct=100, focus=100))
    for flag, key in (('playAction', 'playAction'), ('isRpo', 'rpo'),
                      ('isSneakLook', 'sneakLook')):
        faked = _accuracyOf(_play(defMind=100, instinct=100, focus=100, **{flag: True}))
        assert plain - faked > PRESNAP_DISGUISE[key] * 0.7, \
            f'{key} barely degraded the read ({plain:.3f} -> {faked:.3f})'


def testTrickPlayIsTheBestDisguise():
    plain = _accuracyOf(_play(defMind=100, instinct=100, focus=100))
    trick = _accuracyOf(_play(defMind=100, instinct=100, focus=100, trickPlay='reverse'))
    assert plain - trick > PRESNAP_DISGUISE['trick'] * 0.7


# ── It only touches the multiplier for the play that happened ───────────────

def testRunPlayOnlyMovesRunDefMult():
    p = _play(ytg=7)
    scheme = {'runDefMult': 1.0, 'passDefMult': 1.0}
    p._applyPreSnapRead(scheme, isRun=True)
    assert scheme['passDefMult'] == 1.0
    assert scheme['runDefMult'] != 1.0


def testPassPlayOnlyMovesPassDefMult():
    p = _play(ytg=7)
    scheme = {'runDefMult': 1.0, 'passDefMult': 1.0}
    p._applyPreSnapRead(scheme, isRun=False)
    assert scheme['runDefMult'] == 1.0
    assert scheme['passDefMult'] != 1.0
