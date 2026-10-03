"""The trade market prices a pick at the draft's real slot, and a traded pick is named by
its original team.

Prod, season 8 offseason: the Rocks' pick (12-16) was priced and labeled "slot 8" when
the real draft order, already final, had it at #10 (the market sorted by win% alone,
ignoring the playoffs and the point-differential tiebreak). And every pick in a trade was
named "S8 R1 pick", so the Melons appeared to receive a pick the Strangers never sent:
it was the Rocks' pick the Strangers had bought a season earlier.

Run: .venv/bin/python -m pytest -q test_trade_pick_order_and_names.py
"""
import types

from managers.tradeManager import TradeMarket
from test_trade_market import FakeTeam, FakeTeamManager, FakePlayerManager, StubBrain


def _teams():
    # By win% alone: 3, 1, 2. The real order (non-qualifier 2 first) is 2, 3, 1.
    return [FakeTeam(1, 'One', wins=10, losses=18), FakeTeam(2, 'Two', wins=12, losses=16),
            FakeTeam(3, 'Three', wins=8, losses=20)]


def test_the_market_uses_the_draft_order_it_is_given():
    teams = _teams()
    m = TradeMarket(FakePlayerManager([]), FakeTeamManager(teams), StubBrain(), 70, None,
                    draftOrder=[2, 3, 1])
    assert m._draftOrderPositions() == {2: 1, 3: 2, 1: 3}


def test_without_an_order_it_falls_back_to_win_percentage():
    teams = _teams()
    m = TradeMarket(FakePlayerManager([]), FakeTeamManager(teams), StubBrain(), 70, None)
    m._computeContention()
    assert m._draftOrderPositions() == {3: 1, 1: 2, 2: 3}


def test_the_projection_keeps_the_real_order_and_projects_the_rest():
    from standings_view import projectedDraftOrder
    teams = _teams()
    for t in teams:
        t.seasonTeamStats.update(winPerc=t.seasonTeamStats['wins'] / 28, scoreDiff=0)
    ids, final = projectedDraftOrder(teams, [], [teams[1]])
    assert ids[0] == 2 and set(ids[1:]) == {1, 3} and not final
    ids, final = projectedDraftOrder(teams, [], [teams[1], teams[2], teams[0]])
    assert ids == [2, 3, 1] and final


def test_a_pick_is_labeled_with_its_original_team():
    from api.main import _tradeAssetsWithRatings
    rocks = {'id': 9, 'name': 'Rocks'}
    out = _tradeAssetsWithRatings(
        [{'kind': 'pick', 'id': 70, 'name': 'S8 R1 pick'},
         {'kind': 'player', 'id': 5, 'name': 'Somebody'}],
        {5: 80}, {70: rocks})
    assert out[0]['originalTeam'] == rocks and 'originalTeam' not in out[1]
    assert out[1]['rating'] == 80


if __name__ == '__main__':
    import sys, pytest
    sys.exit(pytest.main(['-q', __file__]))
