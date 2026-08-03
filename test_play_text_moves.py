#!/usr/bin/env python3
"""Ball-carrier move text — one clause, in the order it happened.

The move used to be appended AFTER the tackle clause, which told the story
backwards and left a run-on with no subject:

    ... for 9 yards, tackled by Ginger Belcher, spins and is dragged down anyway

`_tackleClause` merges the two instead. These tests pin the two things that
went wrong: the tackle must not be reported before the move that preceded it,
and the defender must be named exactly once.
"""

import sys, os, types
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Same circular-import dance as test_qb_sneak.py: seasonManager annotates with
# FloosGame.Game at class-definition time.
_stub = types.ModuleType('floosball_game')
class _GameStub: pass
_stub.Game = _GameStub
sys.modules['floosball_game'] = _stub
import managers.timingManager   # noqa: F401  (loads managers/__init__ against the stub)
del sys.modules['floosball_game']
import floosball_game as FloosGame   # noqa: E402

from types import SimpleNamespace    # noqa: E402

TACKLER = 'Ginger Belcher'
MOVES = ['stiff arm', 'spin', 'hurdle']


def _game(move, tackler=TACKLER, fumble=False):
    """The minimum `_tackleClause` reads off self.play."""
    play = SimpleNamespace(
        tackledBy=SimpleNamespace(name=tackler) if tackler else None,
        runnerMove=move,
        isFumble=fumble,
        _moveClauseUsed=False,
    )
    return SimpleNamespace(play=play)


def _clause(move, **kw):
    g = _game(move, **kw)
    return FloosGame.Game._tackleClause(g), g.play


def testNoMoveGivesThePlainTackleClause():
    text, play = _clause(None)
    assert text == ', tackled by {}'.format(TACKLER)
    assert play._moveClauseUsed is False


def testNoTacklerGivesNoClauseAtAll():
    text, _ = _clause('spin', tackler=None)
    assert text == ''


def testEveryMoveOutcomeReplacesTheTackleClause():
    """The bug: 'tackled by X' and then the move, as two clauses.

    Whichever move fired and whether it worked, there is now ONE clause and it
    is not the bare tackle report."""
    for move in MOVES:
        for mv in (move, move + '_miss'):
            text, play = _clause(mv)
            assert ', tackled by' not in text, (mv, text)
            assert play._moveClauseUsed is True, mv
            assert text.startswith(', '), (mv, text)


def testTheDefenderIsNamedExactlyOnce():
    for move in MOVES:
        for mv in (move, move + '_miss'):
            text, _ = _clause(mv)
            assert text.count(TACKLER) == 1, (mv, text)


def testAMadeMoveDoesNotAlsoCreditThatManWithTheTackle():
    """He beat this defender and took bonus yards for it, so the same clause
    can't turn round and say the defender brought him down."""
    for move in MOVES:
        text, _ = _clause(move)
        after = text.split(TACKLER, 1)[1]
        for credit in ('is dragged down by', 'wrapped up by', 'tackled by'):
            assert credit not in text, (move, text)
        # It still ends with him going down — just not by that man's hand.
        assert after.strip(), (move, text)


def testAMissedMoveCreditsTheTacklerWhoStoppedIt():
    for move in MOVES:
        text, _ = _clause(move + '_miss')
        assert TACKLER in text
        # The attempt comes before the defender who ended it, which is the
        # ordering the old text got backwards.
        verbs = [v for v in ('tries', 'spins', 'hurdle') if v in text]
        assert verbs, text
        assert min(text.index(v) for v in verbs) < text.index(TACKLER), text


def testAFumbleKeepsThePlainClause():
    """The fumble text tells the story of the loose ball; the move mustn't
    claim the carrier beat anyone on the way to coughing it up."""
    text, play = _clause('spin', fumble=True)
    assert text == ', tackled by {}'.format(TACKLER)
    assert play._moveClauseUsed is False


def testAnUnknownMoveNameFallsBackRatherThanDroppingTheTackle():
    text, play = _clause('cartwheel')
    assert text == ', tackled by {}'.format(TACKLER)
    assert play._moveClauseUsed is False


def testMadeAndMissedReadDifferently():
    for move in MOVES:
        made, _ = _clause(move)
        missed, _ = _clause(move + '_miss')
        assert made != missed, move


if __name__ == '__main__':
    import traceback
    fns = [v for k, v in sorted(globals().items()) if k.startswith('test') and callable(v)]
    failed = 0
    for fn in fns:
        try:
            fn()
            print('  ok   {}'.format(fn.__name__))
        except Exception:
            failed += 1
            print('  FAIL {}'.format(fn.__name__))
            traceback.print_exc()
    print('\n{}/{} passed'.format(len(fns) - failed, len(fns)))
    sys.exit(1 if failed else 0)
