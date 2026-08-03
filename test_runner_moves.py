#!/usr/bin/env python3
"""Ball-carrier moves, and the flair/determination terms they share with the
existing audacious plays (stretch-for-the-marker, diving catch).

The point of this feature is that `creativity` and `xFactor` were nearly inert
in play resolution. These tests pin that they now decide whether a player TRIES
something, while the physical attribute decides whether it WORKS — the split
that keeps flair from quietly becoming a generic yardage buff.
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
from constants import RUNNER_MOVES   # noqa: E402


def _carrier(creativity=80, xFactor=80, power=80, agility=80, speed=80,
             discipline=80, confidence=0.0, determination=0.0):
    a = SimpleNamespace(creativity=creativity, xFactor=xFactor, power=power,
                        agility=agility, speed=speed, discipline=discipline,
                        confidenceModifier=confidence * 5.0,
                        determinationModifier=determination * 5.0)
    return SimpleNamespace(name='C', attributes=a, gameAttributes=a)


def _play(defRun=75):
    p = object.__new__(FloosGame.Play)
    p.game = SimpleNamespace(yardsToFirstDown=10, gamePressure=50)
    p.defense = SimpleNamespace(name='D', abbr='D', defenseRunCoverageRating=defRun)
    p.insights = {}
    p.isTd = False
    p.yardsToEndzone = 60
    p.yardage = 4
    p.runnerMove = None
    return p


def _attemptRate(carrier, n=6000, defRun=75):
    p = _play(defRun)
    tries = sum(1 for _ in range(n) if p._runnerMove(carrier, None)[1] is not None)
    return tries / n


# ── Flair, the shared willingness term ──────────────────────────────────────

def testFlairIsNeutralAtTheHousePivot():
    p = _play()
    assert abs(p._flair(_carrier(creativity=80, xFactor=80)) - 0.5) < 1e-9


def testFlairRespondsToBothInputs():
    p = _play()
    assert p._flair(_carrier(creativity=100, xFactor=100)) > 0.95
    assert p._flair(_carrier(creativity=60, xFactor=60)) < 0.05
    # Each input carries real weight on its own.
    assert p._flair(_carrier(creativity=100, xFactor=80)) > 0.6
    assert p._flair(_carrier(creativity=80, xFactor=100)) > 0.6


def testDeterminationStateMirrorsConfidence():
    p = _play()
    assert abs(p._determinationState(_carrier(determination=0.0))) < 1e-9
    assert p._determinationState(_carrier(determination=1.0)) == 1.0
    assert p._determinationState(_carrier(determination=-1.0)) == -1.0


# ── Attempts ────────────────────────────────────────────────────────────────

def testFlashyCarriersTryMovesFarMoreOften():
    """The headline behaviour: xFactor and creativity decide who goes for it."""
    flashy = _attemptRate(_carrier(creativity=100, xFactor=100))
    plodder = _attemptRate(_carrier(creativity=60, xFactor=60))
    assert flashy > plodder * 2.5, f'flashy {flashy:.3f} vs plodder {plodder:.3f}'


def testMentalStateNudgesAttemptsButDoesNotDominate():
    hi = _attemptRate(_carrier(confidence=1.0, determination=1.0))
    lo = _attemptRate(_carrier(confidence=-1.0, determination=-1.0))
    assert hi > lo
    # Flair should matter more than mood — a timid star still tries things.
    flairGap = (_attemptRate(_carrier(creativity=100, xFactor=100))
                - _attemptRate(_carrier(creativity=60, xFactor=60)))
    assert flairGap > (hi - lo)


def testAttemptsStayRare():
    """This is texture, not a yardage faucet. An average carrier should try a
    move on a smallish minority of touches."""
    assert _attemptRate(_carrier()) < 0.25


def testNoMoveOnATouchdown():
    p = _play()
    p.isTd = True
    assert p._runnerMove(_carrier(creativity=100, xFactor=100), None) == (0, None, 0)


# ── The move fits the carrier ───────────────────────────────────────────────

def testCarrierPicksTheMoveTheyAreBuiltFor():
    p = _play()
    def moveFor(**kw):
        c = _carrier(creativity=100, xFactor=100, **kw)
        for _ in range(200):
            _, name, _ = p._runnerMove(c, None)
            if name:
                return name.replace('_miss', '')
        return None
    assert moveFor(power=100, agility=60, speed=60) == 'stiff arm'
    assert moveFor(power=60, agility=100, speed=60) == 'spin'


# ── Success is physical, not flair ──────────────────────────────────────────

def testFlairDoesNotDecideWhetherTheMoveWorks():
    """Two carriers with identical physicals but opposite flair should convert
    attempts at the same rate — flair only changes how OFTEN they try."""
    p = _play(defRun=75)
    # Large n because the LOW-flair carrier rarely attempts a move at all, so its
    # hit rate is computed from a small denominator; at n=6000 that denominator
    # was thin enough to fail this occasionally on noise alone.
    def hitRate(c, n=40000):
        made = tried = 0
        for _ in range(n):
            _, name, _ = p._runnerMove(c, None)
            if name:
                tried += 1
                if not name.endswith('_miss'):
                    made += 1
        return made / max(1, tried)
    flashy = hitRate(_carrier(creativity=100, xFactor=100, power=90, agility=90))
    plain = hitRate(_carrier(creativity=60, xFactor=60, power=90, agility=90))
    assert abs(flashy - plain) < 0.06, f'{flashy:.3f} vs {plain:.3f} — flair leaked into success'


def testStrongerCarrierBeatsWeakerDefense():
    p_weak, p_strong = _play(defRun=95), _play(defRun=55)
    c = _carrier(creativity=100, xFactor=100, power=95, agility=95)
    def hits(p, n=4000):
        made = tried = 0
        for _ in range(n):
            _, name, _ = p._runnerMove(c, None)
            if name:
                tried += 1
                made += 0 if name.endswith('_miss') else 1
        return made / max(1, tried)
    assert hits(p_strong) > hits(p_weak) + 0.15


# ── Risk ────────────────────────────────────────────────────────────────────

def testAMissedMoveStillCostsExposure():
    """Reaching for the extra yard exposes the ball whether or not it comes off."""
    p = _play(defRun=99)
    c = _carrier(creativity=100, xFactor=100, discipline=60, power=60, agility=60)
    for _ in range(400):
        gain, name, bump = p._runnerMove(c, None)
        if name and name.endswith('_miss'):
            assert gain == 0
            assert bump > 0, 'an undisciplined miss should still expose the ball'
            return
    raise AssertionError('no missed move sampled')


def testDisciplinedCarriersRiskLess():
    p = _play()
    c_loose = _carrier(creativity=100, xFactor=100, discipline=60)
    c_tight = _carrier(creativity=100, xFactor=100, discipline=100)
    def avgBump(c, n=3000):
        bumps = [b for _ in range(n) for g, nm, b in [c and p._runnerMove(c, None)] if nm]
        return sum(bumps) / max(1, len(bumps))
    assert avgBump(c_loose) > avgBump(c_tight)


def testEveryMoveIsConfiguredCoherently():
    for name, spec in RUNNER_MOVES.items():
        lo, hi = spec['gain']
        assert 0 < lo < hi <= 8, f'{name} gain band {spec["gain"]} is out of range'
        assert spec['risk'] > 0
        assert abs(sum(spec['attrs'].values()) - 1.0) < 1e-9, f'{name} attrs must sum to 1'


# ── The defender gets a say ─────────────────────────────────────────────────

def _tackler(tackling=80, discipline=80):
    a = SimpleNamespace(tackling=tackling, discipline=discipline)
    t = SimpleNamespace(name='T', position=2, gameAttributes=a)
    t.attributes = SimpleNamespace(
        discipline=discipline,
        getDefensiveAttributes=lambda pos: {'tackling': tackling})
    return t


def _hitRate(p, carrier, tackler, n=5000):
    made = tried = 0
    for _ in range(n):
        _, name, _ = p._runnerMove(carrier, tackler)
        if name:
            tried += 1
            made += 0 if name.endswith('_miss') else 1
    return made / max(1, tried)


def testDisciplinedDefenderNullifiesFlairMoves():
    """The owner's ask: a well-disciplined defender should take these away."""
    p = _play()
    c = _carrier(creativity=100, xFactor=100, power=90, agility=90, speed=90)
    loose = _hitRate(p, c, _tackler(tackling=80, discipline=60))
    square = _hitRate(p, c, _tackler(tackling=80, discipline=100))
    assert loose - square > 0.15, f'discipline barely mattered ({loose:.3f} vs {square:.3f})'


def testSkilledTacklerAlsoResists():
    p = _play()
    c = _carrier(creativity=100, xFactor=100, power=90, agility=90, speed=90)
    weak = _hitRate(p, c, _tackler(tackling=60, discipline=80))
    strong = _hitRate(p, c, _tackler(tackling=100, discipline=80))
    assert weak - strong > 0.15


def testDisciplineBitesHardestOnTheRiskiestMove():
    """A hurdle against a squared-up defender should be a worse idea than a

    Compares two DIFFERENCES of sampled rates, so it needs a big n - at
    n=5000 it failed about one run in five on sampling noise alone.
    stiff arm against the same defender."""
    p = _play()
    hurdler = _carrier(creativity=100, xFactor=100, agility=100, speed=100, power=50)
    armer = _carrier(creativity=100, xFactor=100, power=100, agility=50, speed=50)
    square, loose = _tackler(discipline=100), _tackler(discipline=60)
    hurdleDrop = _hitRate(p, hurdler, loose, 30000) - _hitRate(p, hurdler, square, 30000)
    armDrop = _hitRate(p, armer, loose, 30000) - _hitRate(p, armer, square, 30000)
    assert hurdleDrop > armDrop, f'hurdle {hurdleDrop:.3f} should fall further than stiff arm {armDrop:.3f}'


# ── Contact gate ────────────────────────────────────────────────────────────

def testNoMoveOnceIntoOpenField():
    """You cannot stiff-arm someone on a 40-yard housecall — nobody is there."""
    from constants import RUNNER_MOVE_MAX_CONTACT_YARDS
    p = _play()
    p.yardage = RUNNER_MOVE_MAX_CONTACT_YARDS + 1
    c = _carrier(creativity=100, xFactor=100)
    assert all(p._runnerMove(c, None)[1] is None for _ in range(300))


def testMovesStillFireAtThePointOfContact():
    from constants import RUNNER_MOVE_MAX_CONTACT_YARDS
    p = _play()
    p.yardage = RUNNER_MOVE_MAX_CONTACT_YARDS
    c = _carrier(creativity=100, xFactor=100)
    assert any(p._runnerMove(c, None)[1] is not None for _ in range(300))
