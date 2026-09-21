"""A pass play must be able to throw the tier it is filed under.

`_selectPassPlay` picks a concrete play from its tier's pool and the QB then reads that
play's OWN routes, so a play whose routes are all shallower than its pool silently
downgrades every call that draws it. Play20 was exactly that from its first commit
(460fe8b): filed under `long`, declaring `QbDropback.long`, carrying two medium routes
and nothing else.

⚠️ IT WAS STRICTLY DOMINATED, NOT MERELY MISLABELLED. `rushDifferential` charges
`(dropbackDepth - 1) * 2`, so a long dropback costs +6 against a medium play's +2 — the
play paid four points of extra sack exposure for routes the medium pool throws for less.

⚠️ SWEEP THE BOOK, DON'T ASSERT ON Play20. The defect is invisible in any single play
(medium routes on a long play look fine in isolation) and only shows up against the pool
it is filed in, so the test that catches the NEXT one has to be the invariant.
"""
import logging
import re
import sys
import types
import warnings

logging.disable(logging.CRITICAL)
warnings.filterwarnings('ignore')

if 'floosball_game' not in sys.modules:          # the circular-import dance the sim tests use
    _stub = types.ModuleType('floosball_game')
    _stub.Game = type('G', (), {})
    sys.modules['floosball_game'] = _stub
    import managers.timingManager                                        # noqa: F401
    del sys.modules['floosball_game']

import floosball_game as FG                                              # noqa: E402

TIER_DROPBACK = {'short': 'short', 'medium': 'medium', 'long': 'long', 'deep': 'extraLong'}


def _playbook():
    """The literal out of `passPlay`'s body — it is a local, so there is nothing to import."""
    src = open(FG.__file__.replace('.pyc', '.py')).read()
    start = src.index('{', re.search(r'passPlayBook\s*=\s*\{', src).start())
    depth = 0
    for i in range(start, len(src)):
        if src[i] == '{':
            depth += 1
        elif src[i] == '}':
            depth -= 1
            if depth == 0:
                return eval(src[start:i + 1],
                            {'QbDropback': FG.QbDropback, 'PassType': FG.PassType})
    raise AssertionError('passPlayBook literal not found')


def _pools():
    """The pools as `_selectPassPlay` declares them, read off the source for the same reason."""
    src = open(FG.__file__.replace('.pyc', '.py')).read()
    body = src[src.index('pools = {', src.index('def _selectPassPlay')):]
    return eval(body[body.index('{'):body.index('}') + 1])


def test_everyPlayCanThrowTheTierItIsFiledUnder():
    book, pools = _playbook(), _pools()
    offenders = []
    for tier, names in pools.items():
        for name in names:
            routes = [v.name for v in book[name]['targets'].values() if v is not None]
            if tier not in routes:
                offenders.append(f'{name} is in the {tier!r} pool but throws only {routes}')
    assert not offenders, 'plays that cannot throw their own tier: ' + '; '.join(offenders)


def test_aPlaysDropbackMatchesThePoolItIsFiledUnder():
    """The dropback is what the line is protecting for, and it is PRICED — a deeper drop
    buys more sack exposure, so a play carrying one has to be reaching for that depth."""
    book, pools = _playbook(), _pools()
    for tier, names in pools.items():
        for name in names:
            assert book[name]['dropback'].name == TIER_DROPBACK[tier], (
                f'{name} is in the {tier!r} pool on a {book[name]["dropback"].name} dropback')


def test_aDeeperDropbackCostsMoreSackExposure():
    """The premise of the two tests above: the depth ladder is not cosmetic."""
    depths = [FG.QbDropback.short, FG.QbDropback.medium,
              FG.QbDropback.long, FG.QbDropback.extraLong]
    charges = [(d.value - 1) * 2 for d in depths]
    assert charges == sorted(charges) and charges[0] < charges[-1], charges


def test_everyPoolOffersMoreThanOneShape():
    """A pool whose plays are all identical gives the matchup weighting nothing to pick
    between, which is how a gap in the long pool went unnoticed long enough to be filled
    by a play that could not throw long at all."""
    book, pools = _playbook(), _pools()
    for tier, names in pools.items():
        shapes = {tuple(sorted((k, v.name) for k, v in book[n]['targets'].items() if v))
                  for n in names}
        assert len(shapes) > 1, f'the {tier!r} pool offers a single shape'


if __name__ == '__main__':
    passed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith('test_'):
            fn()
            passed += 1
            print(f'  ok  {name}')
    print(f'\n{passed} passed')
