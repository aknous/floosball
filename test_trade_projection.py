"""The trade market prices a player's future at his projection, not today's rating, and a
club's projected stars are part of its core.

Reported on production (owner, 2026-10-02): Broads sent Norman Slithers (two seasons in,
rated 74, projected expected 88 / ceiling 90) to Waffles for Martha Fright (nine seasons
in, 81 -> 74, one season left) plus a mid first. The market priced every season at
today's rating, so the two were the same asset to the seller and the pick tipped it; and
the core only counted CURRENT stars, so Norman was on the block at all.

Run: .venv/bin/python -m pytest -q test_trade_projection.py
"""
import trading
from managers.tradeManager import TradeMarket
from floosball_player import Position
from test_trade_market import FakeTeam, FakePlayer, FakeTeamManager, FakePlayerManager, StubBrain

SEASON = 70


# ------------------------------------------------------------- the valuation itself

def test_no_projection_is_the_old_flat_reading():
    for term in (1, 2, 4):
        flat = trading.playerValue(80, term, None, 1.0, 1.0)
        assert abs(trading.playerValue(80, term, None, 1.0, 1.0, futureRating=None) - flat) < 1e-9
        ask, floor = trading.askAndFloor(80, 72, term, None, 1.0, 1.0)
        a2, f2 = trading.askAndFloor(80, 72, term, None, 1.0, 1.0, futureRating=80)
        assert abs(ask - a2) < 1e-9 and abs(floor - f2) < 1e-9


def test_a_rising_player_is_worth_more_than_a_fading_one_at_the_same_rating():
    rising = trading.playerValue(74, 3, None, 1.0, 1.0, futureRating=84)
    fading = trading.playerValue(74, 3, None, 1.0, 1.0, futureRating=65)
    flat = trading.playerValue(74, 3, None, 1.0, 1.0)
    assert rising > flat > fading


def test_one_season_of_control_is_only_the_present():
    """Offseason, one season left: there is no future to project."""
    assert abs(trading.playerValue(74, 1, None, 1.0, 1.0, futureRating=95)
               - trading.playerValue(74, 1, None, 1.0, 1.0)) < 1e-9


def test_a_fading_veterans_future_below_replacement_is_worth_nothing():
    present = trading.playerValue(74, 1, None, 1.0, 1.0)
    assert abs(trading.playerValue(74, 3, None, 1.0, 1.0, futureRating=60) - present) < 1e-9


# ------------------------------------------------------------- the market

class ProjectingBrain(StubBrain):
    """Forward ratings, arcs and ceilings by name; perfect scouting."""

    def __init__(self, forward=None, arcs=None, ceilings=None):
        self.forward = forward or {}
        self.arcs = arcs or {}
        self.ceilings = ceilings or {}

    def trueForwardRating(self, player, coach=None, team=None):
        return self.forward.get(player.name, player.playerRating)

    def scoutingVision(self, coach, team=None):
        return 1.0

    def classifyArc(self, player):
        return self.arcs.get(player.name, 'prime')

    def _ceilingRating(self, player, team=None):
        return self.ceilings.get(player.name, player.playerRating)


def _market(brain, roster):
    teams = [FakeTeam(1, 'Sellers', wins=19, losses=9), FakeTeam(2, 'Other', wins=14, losses=14)]
    teams[0].rosterDict = {f'wr{i + 1}': p for i, p in enumerate(roster)}
    for p in roster:
        p.team = teams[0]
    return TradeMarket(FakePlayerManager([]), FakeTeamManager(teams), brain, SEASON, None), teams


def test_the_seller_prices_a_rising_player_above_a_fading_one():
    """Norman's shape against Martha's: same rating today, three seasons of control."""
    rising = FakePlayer(1, 74, Position.WR, termRemaining=3, name='Rising')
    fading = FakePlayer(2, 74, Position.WR, termRemaining=3, name='Fading')
    brain = ProjectingBrain(forward={'Rising': 80, 'Fading': 65},
                            arcs={'Rising': 'developing', 'Fading': 'regressing'})
    m, teams = _market(brain, [rising, fading])
    askRising, _ = m._priceListing(teams[0], rising)
    askFading, _ = m._priceListing(teams[0], fading)
    assert askRising > askFading, (askRising, askFading)


def test_a_projected_star_is_core_and_never_listed():
    """A developing player whose ceiling is at the 4-star line is part of the core."""
    norman = FakePlayer(1, 74, Position.WR, termRemaining=1, name='Norman')
    plain = FakePlayer(2, 74, Position.WR, termRemaining=1, name='Plain')
    brain = ProjectingBrain(arcs={'Norman': 'developing', 'Plain': 'developing'},
                            ceilings={'Norman': 90, 'Plain': 79})
    m, teams = _market(brain, [norman, plain])
    core = m._coreOf(teams[0])
    assert id(norman) in core, "a projected 4-star was not protected"
    assert id(plain) not in core, "a modest ceiling was protected"


def test_projected_stars_are_capped():
    from constants import TRADE_CORE_SIZE
    kids = [FakePlayer(i, 70, Position.WR, termRemaining=2, name=f'Kid{i}') for i in range(4)]
    brain = ProjectingBrain(arcs={k.name: 'developing' for k in kids},
                            ceilings={k.name: 85 + i for i, k in enumerate(kids)})
    m, teams = _market(brain, kids)
    assert len(m._projectedStarsOf(teams[0])) == int(TRADE_CORE_SIZE)


if __name__ == '__main__':
    import sys, pytest
    sys.exit(pytest.main(['-q', __file__]))
