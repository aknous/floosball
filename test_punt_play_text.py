"""Punt play-by-play text.

Before this, every punt read "X punts" and stopped — a fair catch, a touchback, a
40-yard return and a shank all produced identical text. These pin the phrasing for
each outcome the punt model can produce.
"""
import sys, os, types
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Same circular-import dance the other sim tests use: seasonManager annotates with
# FloosGame.Game at class-definition time, so managers must load against a stub.
_stub = types.ModuleType('floosball_game')
class _GameStub: pass
_stub.Game = _GameStub
sys.modules['floosball_game'] = _stub
import managers.timingManager   # noqa: F401
del sys.modules['floosball_game']
import floosball_game as fg     # noqa: E402


class _Team:
    name = 'Rockets'


def _play(**kw):
    p = type('P', (), {})()
    p.puntGross = kw.get('gross', 45)
    p.yardage = p.puntGross
    p.puntAction = kw.get('action')
    p.puntResult = kw.get('result')
    p.puntLanding = kw.get('landing')
    p.returnYardage = kw.get('ret', 0)
    p.puntTouchback = kw.get('tb', False)
    p.puntMuffRecoveredBy = kw.get('muffBy')
    p.returner = (type('R', (), {'name': 'Cass Whitlow'})()
                  if kw.get('returner', True) else None)
    p.offense = _Team()
    return p


def _text(**kw):
    g = fg.Game.__new__(fg.Game)
    g.play = _play(**kw)
    return g._puntPlayText('Dane Fulcher')


def testReturnNamesTheReturnerAndYards():
    t = _text(gross=48, action='return', landing=32, ret=11)
    assert t == 'Dane Fulcher punts 48 yards, Cass Whitlow returns it 11 yards'


def testTouchbackIsCalledOut():
    assert _text(gross=52, action='fairCatch', tb=True, landing=0).endswith('touchback')


def testFairCatchNamesTheSpotOnce():
    """A fair catch already states where it happened, so the 'pinned at' suffix
    must not repeat it — that read 'fair catch at the 18, pinned at the 18'."""
    t = _text(gross=41, action='fairCatch', landing=18)
    assert t == 'Dane Fulcher punts 41 yards, fair catch by Cass Whitlow at the 18'
    assert t.count('18') == 1


def testInsideTenIsDownedNotFairCaught():
    """A ball coming down inside the 10 is run down by the coverage team, not
    waved off by a returner standing under it."""
    t = _text(gross=38, action='fairCatch', landing=6)
    assert 'downed at the 6' in t
    assert 'fair catch' not in t


def testPinnedSuffixOnlyAfterARealReturn():
    t = _text(gross=44, action='return', landing=14, ret=4)
    assert t.endswith('pinned at the 18')


def testShankReadsAsAShank():
    t = _text(gross=17, result='shank', action='return', landing=48, ret=6)
    assert t == 'Dane Fulcher shanks the punt, 17 yards'


def testMuffNamesWhoRecovered():
    kicking = _text(gross=45, action='muff', landing=25, muffBy='kicking')
    assert 'muffs it and Rockets recover' in kicking
    receiving = _text(gross=45, action='muff', landing=25, muffBy='receiving')
    assert 'muffs it but recovers' in receiving


def testReturnTouchdown():
    t = _text(gross=47, action='touchdown', landing=22, ret=78)
    assert 'returns it 78 yards for a TOUCHDOWN' in t


def testMissingReturnerDoesNotBreakIt():
    t = _text(gross=45, action='fairCatch', landing=30, returner=False)
    assert t.startswith('Dane Fulcher punts 45 yards')
