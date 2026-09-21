"""The deep ball is a coverage decision, not a distance decision.

The base table used to treat DEEP as the tier you reach for when you need yards: hard
0.0 on 2nd & 1-3 and 3rd & 1-6, scaling up with yards to go. Real football is the
opposite — measured over NFL 2021-25, deep is FLAT at 7-11% of throws in every down and
distance bucket (2nd & 1 is 9.1%, 3rd & 1 is 8.5%), because a shot is available when the
coverage allows it and a defense squatting on the sticks is when it allows it most. The
tier that chases distance is LONG (13.2% at 3rd & 1 up to 21.1% at 3rd & 10).

⚠️ A ZERO IS THE FAILURE MODE THAT HIDES. The previous correction was multiplicative
(deep x2.8) and 2.8 x 0 is 0, so it was a no-op in precisely the five rows with the worst
deficit while landing every other row — long hit its target and deep stalled at less than
half of the NFL's rate. Assert against zero explicitly.

⚠️ FIELD POSITION IS THE ONE REAL LIMIT AND IT BELONGS TO THE GATE, NOT THE ROWS. These
tests therefore check the rows are field-BLIND (same shape goal-to-go as anywhere) and
that `_applyFieldDepthGate` supplies the geometry.
"""
import logging
import sys
import types
import warnings

logging.disable(logging.CRITICAL)
warnings.filterwarnings('ignore')

if 'floosball_game' not in sys.modules:
    _stub = types.ModuleType('floosball_game')
    _stub.Game = type('G', (), {})
    sys.modules['floosball_game'] = _stub
    import managers.timingManager                                        # noqa: F401
    del sys.modules['floosball_game']

import floosball_game as FG                                              # noqa: E402
from constants import (PLAY_CALL_BASE_ROWS, PASS_DEPTH_MEANS,            # noqa: E402
                       FIELD_DEPTH_GATE_FLOOR)

TIERS = ('short', 'medium', 'long', 'deep')


def _rows():
    for down, rows in PLAY_CALL_BASE_ROWS.items():
        for cap, run, shape in rows:
            yield down, cap, run, dict(zip(TIERS, shape))


def test_noRowForbidsTheDeepBall():
    dead = [f'{d} & <={cap}' for d, cap, _r, s in _rows() if s['deep'] <= 0]
    assert not dead, 'rows that can never throw deep: ' + ', '.join(dead)


def test_theDeepShareIsFlatAcrossDownAndDistance():
    """Not equal — the NFL does lean on it slightly more on 3rd and long (11-13% of throws
    against a 9.3% league rate) — but nothing like proportional to yards needed. These are
    MENU shares, which run above the realized throw shares because a called deep ball is
    thrown deep only ~73% of the time; what is pinned is the narrow SPREAD, since a table
    that scales deep with distance has a min near zero and fails the ratio outright."""
    shares = {f'{d} & <={cap}': 100.0 * s['deep'] / sum(s.values()) for d, cap, _r, s in _rows()}
    out = {k: round(v, 1) for k, v in shares.items() if not 8.0 <= v <= 27.0}
    assert not out, f'deep share of the pass menu outside the flat band: {out}'
    spread = max(shares.values()) / min(shares.values())
    assert spread < 2.0, f'deep varies {spread:.1f}x across rows: {shares}'


def test_longIsTheTierThatChasesDistance():
    """The job the table used to give deep. Third and long must lean on long more than
    third and short does."""
    byCap = {cap: s for d, cap, _r, s in _rows() if d == 3}
    shortYardage = byCap[1]['long'] / sum(byCap[1].values())
    longYardage = byCap[9]['long'] / sum(byCap[9].values())
    assert longYardage > shortYardage, (
        f'3rd & 7-9 leans on long {longYardage:.3f} vs 3rd & 1 {shortYardage:.3f}')


def test_theRowsAreFieldBlind():
    """Goal-to-go rows carry the same shape as open-field ones — geometry is the gate's
    job, stated once, or the two rules drift apart."""
    firstDown = [s for d, cap, _r, s in _rows() if d == 1]
    goalToGo, openField = firstDown[0], firstDown[-1]
    for tier in TIERS:
        a = goalToGo[tier] / sum(goalToGo.values())
        b = openField[tier] / sum(openField.values())
        assert abs(a - b) < 0.02, f'{tier}: goal-to-go {a:.3f} vs open field {b:.3f}'


class _Gate:
    """Bare enough to call the gate unbound — it reads one attribute."""
    def __init__(self, yte):
        self.yardsToEndzone = yte


def _gated(yte):
    return FG.Game._applyFieldDepthGate(_Gate(yte), {'run': 50.0, 'short': 25.0,
                                                     'medium': 15.0, 'long': 20.0,
                                                     'deep': 10.0})


def test_theFieldGateBitesOnlyInsideTheTiersBand():
    """A 27-yard route needs the field to hold it. The threshold is the SHALLOW EDGE of
    the band, not the mean — the NFL throws long 18.3% from the 11-15 and 27.7% from the
    16-20, both ABOVE its league average, because that is where a 17-yard route scores.
    Gating long at its 17-yard mean measurably cost the long game 15.4% -> 12.1%."""
    deepEdge = (PASS_DEPTH_MEANS['long'] + PASS_DEPTH_MEANS['deep']) / 2.0
    longEdge = (PASS_DEPTH_MEANS['medium'] + PASS_DEPTH_MEANS['long']) / 2.0
    assert _gated(60)['deep'] == 10.0, 'deep gated in open field'
    assert _gated(60)['long'] == 20.0, 'long gated in open field'
    assert _gated(int(deepEdge) + 2)['deep'] == 10.0, 'deep gated outside its band'
    assert _gated(int(deepEdge) - 4)['deep'] < 10.0, 'deep not gated inside its band'
    # the mean sits well above the edge, and long must NOT be gated between the two
    assert longEdge < PASS_DEPTH_MEANS['long']
    assert _gated(15)['long'] == 20.0, 'long gated from the 15, where the NFL throws it most'


def test_theFieldGateScalesRatherThanCliffs():
    deep = [_gated(y)['deep'] for y in (1, 6, 12, 18, 22)]
    assert deep == sorted(deep), f'gate is not monotonic in field position: {deep}'
    assert deep[0] > 0, 'a tier is scaled down, never switched off — some of the band fits'
    assert abs(deep[0] - 10.0 * FIELD_DEPTH_GATE_FLOOR) < 0.5, \
        f'no field left should leave the floor, got {deep[0]}'


def test_theGateLeavesTheRunGameAlone():
    for yte in (3, 10, 25, 70):
        assert _gated(yte)['run'] == 50.0
        assert _gated(yte)['short'] == 25.0


if __name__ == '__main__':
    passed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith('test_'):
            fn()
            passed += 1
            print(f'  ok  {name}')
    print(f'\n{passed} passed')
