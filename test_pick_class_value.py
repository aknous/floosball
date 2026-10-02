"""A pick in the upcoming draft is priced off the real class, and a top one is never
bundle change.

Owner, 2026-10-01: a generational QB sits atop this season's class, and #1 is a pick the
holder should make, not trade away. The market priced every pick by what its slot USUALLY
yields (`trading.pickValue`), blind to the class that has been generated and scouted all
season, and offered every pick it owned as a piece inside other deals, cheapest first. A
contender holding #1 (which prices future assets low) could hand it over as change.

Run: .venv/bin/python -m pytest -q test_pick_class_value.py
"""
import trading
from managers.tradeManager import TradeMarket
from test_trade_market import FakeTeam, FakeTeamManager, StubBrain, FakePlayer
from floosball_player import Position

SEASON = 70


class Rookie:
    def __init__(self, name):
        self.name = name
        self.is_upcoming_rookie = True


class ClassPM:
    """A player manager holding an upcoming class, with the draft board's value and the
    believed ceiling per name (ceiling defaults to 95, a 5-star class)."""

    def __init__(self, values, ceilings=None):
        self.freeAgents = []
        self.activePlayers = [Rookie(n) for n in values]
        self._values = values
        self._ceilings = ceilings or {}

    def rookieBoardValue(self, brain, team, rookie):
        return self._values[rookie.name]

    def rookieCeiling(self, brain, team, rookie):
        return self._ceilings.get(rookie.name, 95.0)


def _teams():
    return [FakeTeam(i + 1, f"C{i + 1}", wins=20 - i, losses=8 + i) for i in range(4)]


def _market(values, teams=None, ceilings=None):
    teams = teams or _teams()
    return (TradeMarket(ClassPM(values, ceilings), FakeTeamManager(teams), StubBrain(), SEASON, None),
            teams)


PICK1 = {'id': 1, 'season': SEASON, 'round': 1, 'slot': 1, 'classSize': 32}
PICK9 = {'id': 2, 'season': SEASON, 'round': 1, 'slot': 9, 'classSize': 32}
FUTURE1 = {'id': 3, 'season': SEASON + 1, 'round': 1, 'slot': 1, 'classSize': 32}


def test_the_upcoming_pick_is_worth_the_class_it_drafts_from():
    strong, teams = _market({'Generational QB': 80.0, 'Solid': 20.0, 'Depth': 5.0})
    weak, _ = _market({'Solid': 20.0, 'Depth': 5.0, 'Filler': 1.0}, teams)
    holder = teams[0]
    assert strong._pickValueTo(holder, PICK1) > weak._pickValueTo(holder, PICK1) * 3, \
        "#1 in a class with a generational prospect priced like #1 in a weak one"
    # Slot k is the k-th best on the holder's own board.
    assert strong._pickValueTo(holder, {**PICK1, 'slot': 2}) < strong._pickValueTo(holder, PICK1)


def test_a_future_pick_keeps_the_generic_yield():
    """Its class does not exist yet, so there is nothing to look at."""
    strong, teams = _market({'Generational QB': 80.0})
    holder = teams[0]
    w = trading.laterWeight(strong.nowWeight(holder))
    assert abs(strong._pickValueTo(holder, FUTURE1) - trading.pickValue(1, 1, weight=w)) < 1e-9


def test_with_no_class_the_upcoming_pick_falls_back_to_the_generic_yield():
    m, teams = _market({})
    holder = teams[0]
    w = trading.laterWeight(m.nowWeight(holder))
    assert abs(m._pickValueTo(holder, PICK1) - trading.pickValue(1, 0, weight=w)) < 1e-9


def test_a_headline_pick_is_never_bundle_change():
    """#1 with a 5-star prospect there cannot be offered inside a deal for something else;
    a later slot and a future-draft pick still can."""
    m, teams = _market({'Generational QB': 80.0, 'Solid': 20.0},
                       ceilings={'Generational QB': 98.0, 'Solid': 85.0})
    m.picksOwnedBy = lambda team: [PICK1, PICK9, FUTURE1]
    ids = {a['id'] for a in m._tradeableAssets(teams[0]) if a['kind'] == 'pick'}
    assert 1 not in ids, "the #1 pick was offered as a bundle piece"
    assert {2, 3} <= ids, "an unprotected or future pick was dropped from the bundle pool"


def test_in_a_weak_class_a_top_pick_trades_like_any_other():
    """Owner, 2026-10-01: "if its a weak draft class then it could still be possible".
    The rule keys on the prospect at the slot: no 5-star there, no protection."""
    m, teams = _market({'Best Of A Weak Class': 20.0, 'Solid': 15.0},
                       ceilings={'Best Of A Weak Class': 88.0, 'Solid': 85.0})
    assert not m._isHeadlinePick(teams[0], PICK1)
    m.picksOwnedBy = lambda team: [PICK1]
    assert 1 in {a['id'] for a in m._tradeableAssets(teams[0])}


def test_the_headline_test_reads_the_prospect_at_the_slot():
    """In a class with three 5-star prospects (99, 97, 93), #1-#3 are headline picks and #4
    and #5 are not; nothing past the top five ever is."""
    ceil = {'A': 97.0, 'B': 93.0, 'C': 89.0, 'D': 86.0, 'E': 84.0, 'F': 99.0}
    m, teams = _market({n: 10.0 for n in ceil}, ceilings=ceil)
    head = lambda slot: m._isHeadlinePick(teams[0], {**PICK1, 'slot': slot})
    assert head(1) and head(2) and head(3), "the three 5-star prospects should protect #1-#3"
    assert not head(4) and not head(5)
    assert not head(6), "slot 6 is never a headline pick"
    assert not m._isHeadlinePick(teams[0], FUTURE1), "a future pick has no class to read"


def test_bundle_and_move_up_price_a_pick_the_same_way():
    m, teams = _market({'Generational QB': 80.0, 'Solid': 20.0, 'Depth': 5.0}
                       | {f'P{i}': 10.0 - i * 0.1 for i in range(10)})
    m.picksOwnedBy = lambda team: [PICK9]
    asset = next(a for a in m._tradeableAssets(teams[0]) if a['id'] == 2)
    assert abs(asset['value'] - m._pickValueTo(teams[0], PICK9)) < 1e-9


def test_quality_value_halves_each_further_piece():
    assert TradeMarket._qualityValue([10, 10, 10]) == 10 + 5 + 2.5
    assert TradeMarket._qualityValue([4, 30]) == 30 + 2, "the best piece counts in full"


def _assembleWith(assets, bar, quality):
    m, teams = _market({})
    m._tradeableAssets = lambda team, valuingTeam=None, swapPosition=None: [dict(a) for a in assets]
    return m._assemble(teams[0], teams[1], bar, gross=1000.0, displaced=0.0,
                       maxPieces=5, qualityOverVolume=quality)


def test_a_top_pick_is_not_bought_with_volume():
    """Owner, 2026-10-01: "a 'first' means nothing because there's only one round".
    Three ordinary pieces clear a plain-sum bar of 25; counted best-first they are worth
    17.5, and the same bar refuses them."""
    ordinary = [{'kind': 'pick', 'id': i, 'name': f'pick {i}', 'value': 10.0} for i in range(4)]
    assert _assembleWith(ordinary, 25.0, quality=False), "a plain sum should clear"
    assert _assembleWith(ordinary, 25.0, quality=True) == [], \
        "a pile of ordinary picks bought a top-3 pick"


def test_a_real_centerpiece_still_buys_a_top_pick():
    assets = [{'kind': 'prospect', 'id': 1, 'name': 'star prospect', 'value': 22.0},
              {'kind': 'pick', 'id': 2, 'name': 'pick', 'value': 8.0}]
    got = _assembleWith(assets, 25.0, quality=True)
    assert {a['id'] for a in got} == {1, 2}, got


class ArcBrain(StubBrain):
    def __init__(self, arcs):
        self.arcs = arcs

    def classifyArc(self, player):
        return self.arcs.get(player.name, 'prime')


def _starOf(roster, arcs=None):
    teams = _teams()
    teams[0].rosterDict = {f's{i}': p for i, p in enumerate(roster)}
    m = TradeMarket(ClassPM({}), FakeTeamManager(teams), ArcBrain(arcs or {}), SEASON, None)
    return m._starPaymentFor(teams[0], teams[1])


def test_a_top_pick_costs_a_prime_four_star_under_contract():
    """Owner, 2026-10-01: a top-3 pick costs "a 4-5 star rated roster player in their
    prime". Not a lesser player, not a declining one, not a rental."""
    star = FakePlayer(1, 90, Position.QB, termRemaining=3, name='Prime Star')
    assert _starOf([star])['name'] == 'Prime Star'
    assert _starOf([FakePlayer(2, 80, Position.QB, termRemaining=3)]) is None, "a 3-star qualified"
    assert _starOf([FakePlayer(3, 90, Position.QB, termRemaining=1)]) is None, "a rental qualified"
    assert _starOf([FakePlayer(4, 90, Position.QB, termRemaining=3, name='Old')],
                   arcs={'Old': 'regressing'}) is None, "a declining star qualified"
    assert _starOf([FakePlayer(5, 90, Position.QB, termRemaining=3, name='Kid')],
                   arcs={'Kid': 'developing'}) is None, "a still-developing player qualified"
    assert _starOf([FakePlayer(6, 95, Position.K, termRemaining=3)]) is None, \
        "a kicker qualified as the star (owner: never a kicker)"


def test_the_star_is_always_in_the_package():
    """The required star is counted first and never dropped as redundant, even when he
    alone clears the bar."""
    m, teams = _market({})
    m._tradeableAssets = lambda team, valuingTeam=None, swapPosition=None: [
        {'kind': 'pick', 'id': 9, 'name': 'pick', 'value': 4.0}]
    star = {'kind': 'player', 'id': 1, 'name': 'Star', 'value': 40.0, 'buyerValue': 30.0}
    got = m._assemble(teams[0], teams[1], 25.0, gross=1000.0, displaced=0.0, maxPieces=5,
                      qualityOverVolume=True, mandatory=[star])
    assert [p['id'] for p in got] == [1], got


if __name__ == '__main__':
    import sys, pytest
    sys.exit(pytest.main(['-q', __file__]))
