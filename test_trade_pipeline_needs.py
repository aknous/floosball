"""A club's own prospects count as its plan at their position (owner, 2026-10-02:
"needs should consider current prospects").

The market ranked holes and priced upgrades off the rostered starter alone, so a club with
a weak starter and a strong prospect about to be promoted read the position as a hole and
could trade for a player who blocks him. Offseason only: that is when a prospect can be
promoted, and in-season the starter plays the rest of the year regardless.

Run: .venv/bin/python -m pytest -q test_trade_pipeline_needs.py
"""
from floosball_player import Position
from managers.tradeManager import TradeMarket
from test_trade_market import FakeTeam, FakePlayer, FakeTeamManager, FakePlayerManager
from test_trade_projection import ProjectingBrain

SEASON = 70


def _p(pid, rating, pos, expected=None, prospect=False, name=None):
    p = FakePlayer(pid, rating, pos, termRemaining=2, name=name or f'P{pid}',
                   isProspect=prospect, prospectSeasons=2 if prospect else 0)
    p.computeExpectedRating = lambda: expected if expected is not None else rating
    return p


def _league(week=None, prospects=()):
    beans, other = FakeTeam(1, 'Beans'), FakeTeam(2, 'Other')
    beans.rosterDict = {'qb': _p(1, 80, Position.QB), 'rb': _p(2, 60, Position.RB),
                        'wr1': _p(3, 80, Position.WR), 'wr2': _p(4, 62, Position.WR),
                        'te': _p(5, 80, Position.TE), 'k': None}
    other.rosterDict = {'qb': _p(11, 80, Position.QB), 'rb': _p(12, 84, Position.RB),
                        'wr1': _p(13, 80, Position.WR), 'wr2': _p(14, 80, Position.WR),
                        'te': _p(15, 80, Position.TE), 'k': None}
    beans.prospects = list(prospects)
    for t in (beans, other):
        for pl in t.rosterDict.values():
            if pl is not None:
                pl.team = t
    arcs = {p.name: 'developing' for p in prospects}
    ceilings = {p.name: p.computeExpectedRating() + 3 for p in prospects}
    m = TradeMarket(FakePlayerManager([]), FakeTeamManager([beans, other]),
                    ProjectingBrain(arcs=arcs, ceilings=ceilings), SEASON, week)
    return m, beans


STAR_RB = lambda: _p(90, 74, Position.RB, expected=90, prospect=True, name='Dew Stone')


def test_a_weak_starter_is_a_hole_until_a_prospect_covers_it():
    m, beans = _league()
    assert Position.RB.value in m.topNeeds(beans)
    m, beans = _league(prospects=[STAR_RB()])
    assert Position.RB.value not in m.topNeeds(beans), "a covered position still read as a hole"


def test_in_season_the_prospect_does_not_cover_this_seasons_need():
    m, beans = _league(week=20, prospects=[STAR_RB()])
    assert m._pipelineAt(beans, Position.RB.value) is None
    assert Position.RB.value in m.topNeeds(beans)


def test_an_upgrade_is_priced_against_the_prospect_when_he_is_better():
    incoming = _p(99, 86, Position.RB)
    m, beans = _league()
    plain, fee = m._displacedBy(beans, incoming)
    m, beans = _league(prospects=[STAR_RB()])
    withPipe, fee2 = m._displacedBy(beans, incoming)
    assert withPipe > plain and fee2 == fee, (plain, withPipe)
    assert abs(withPipe - m._pipelineValue(beans, incoming)) < 1e-9


def test_a_weak_prospect_changes_nothing():
    m, beans = _league()
    plain = m._displacedBy(beans, _p(99, 86, Position.RB))[0]
    m, beans = _league(prospects=[_p(91, 55, Position.RB, expected=58, prospect=True, name='Meh')])
    assert m._displacedBy(beans, _p(99, 86, Position.RB))[0] == plain
    assert Position.RB.value in m.topNeeds(beans)


def test_a_prospect_covers_one_receiver_slot_not_both():
    wr = _p(92, 74, Position.WR, expected=90, prospect=True, name='Wide Kid')
    m, beans = _league(prospects=[wr])
    gaps = {slot: p for slot, p in m._positionalGaps(beans, deficitOnly=True)}
    assert 'wr2' not in gaps, "the weaker receiver slot is covered by the prospect"
    m2, beans2 = _league()
    assert 'wr2' in {slot for slot, _ in m2._positionalGaps(beans2, deficitOnly=True)}


if __name__ == '__main__':
    import sys, pytest
    sys.exit(pytest.main(['-q', __file__]))
