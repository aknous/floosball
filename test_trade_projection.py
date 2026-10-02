"""The trade market prices a player's future at his projection, not today's rating — a
developing player at what he becomes.

Reported on production (owner, 2026-10-02): Broads sent Norman Slithers (two seasons in,
rated 74, projected expected 88 / ceiling 90) to Waffles for Martha Fright (nine seasons
in, 81 -> 74, one season left) plus a mid first. The market priced every season at
today's rating, so the two were the same asset to the seller and the pick tipped it.
Owner: such players stay tradeable, "but the GM should value them at their possible future
skill, so the return would just need to be more valuable".

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
    """Forward ratings, arcs and ceilings by name; perfect scouting, full development."""

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

    def _attrLean(self, coach, attr, bonus=0.0):
        return 1.0


def _player(pid, rating, name, term, expected=None):
    p = FakePlayer(pid, rating, Position.WR, termRemaining=term, name=name)
    p.computeExpectedRating = lambda: expected if expected is not None else rating
    return p


def _market(brain, roster):
    teams = [FakeTeam(1, 'Sellers', wins=19, losses=9), FakeTeam(2, 'Other', wins=14, losses=14)]
    teams[0].rosterDict = {f'wr{i + 1}': p for i, p in enumerate(roster)}
    for p in roster:
        p.team = teams[0]
    return TradeMarket(FakePlayerManager([]), FakeTeamManager(teams), brain, SEASON, None), teams


def test_a_developing_player_is_priced_at_what_he_becomes():
    """Norman's shape: 74 today, expected 88, ceiling 90. His later seasons are read at
    his mature skill (expected + the credited share of the ceiling gap), not at today's
    74 and not at next season's small step."""
    norman = _player(1, 74, 'Norman', 3, expected=88)
    brain = ProjectingBrain(forward={'Norman': 79}, arcs={'Norman': 'developing'},
                            ceilings={'Norman': 90})
    m, teams = _market(brain, [norman])
    from constants import FO_CEILING_CREDIT
    assert abs(m._futureRatingFor(teams[0], norman) - (88 + 2 * FO_CEILING_CREDIT)) < 1e-6


def test_the_seller_prices_a_rising_player_above_a_fading_one():
    """Norman's shape against Martha's: same rating today, three seasons of control."""
    rising = _player(1, 74, 'Rising', 3, expected=88)
    fading = _player(2, 74, 'Fading', 3)
    brain = ProjectingBrain(forward={'Fading': 65},
                            arcs={'Rising': 'developing', 'Fading': 'regressing'},
                            ceilings={'Rising': 90})
    m, teams = _market(brain, [rising, fading])
    askRising, _ = m._priceListing(teams[0], rising)
    askFading, _ = m._priceListing(teams[0], fading)
    assert askRising > 2 * askFading, (askRising, askFading)


def test_a_projected_star_is_still_tradeable():
    """Not untouchable: priced higher, still on the market."""
    norman = _player(1, 74, 'Norman', 2, expected=88)
    brain = ProjectingBrain(arcs={'Norman': 'developing'}, ceilings={'Norman': 90})
    m, teams = _market(brain, [norman])
    assert id(norman) not in m._coreOf(teams[0])


def test_a_poor_scout_sees_less_of_the_future():
    norman = _player(1, 74, 'Norman', 3, expected=88)

    class Blind(ProjectingBrain):
        def scoutingVision(self, coach, team=None):
            return 0.0

    m, teams = _market(Blind(arcs={'Norman': 'developing'}, ceilings={'Norman': 90}), [norman])
    assert abs(m._futureRatingFor(teams[0], norman) - 74) < 1e-6


def test_a_rising_star_is_judged_on_his_projection_not_the_blended_read():
    """Owner, 2026-10-02: a rising star is bought with quality, not volume. Norman reads 83
    through a 0.6-vision scout, a point under the line; the test is his projection (88)."""
    norman = _player(1, 74, 'Norman', 2, expected=88)
    modest = _player(2, 74, 'Modest', 2, expected=78)
    prime = _player(3, 86, 'Prime', 2)

    class GoodScout(ProjectingBrain):
        def scoutingVision(self, coach, team=None):
            return 0.6

    brain = GoodScout(arcs={'Norman': 'developing', 'Modest': 'developing'},
                      ceilings={'Norman': 90, 'Modest': 80})
    m, teams = _market(brain, [norman, modest, prime])
    assert m._futureRatingFor(teams[0], norman) < 84 <= m._projectedRatingFor(teams[0], norman)
    assert m._isRisingStar(teams[0], norman)
    assert not m._isRisingStar(teams[0], modest), "a modest ceiling counted as a rising star"
    assert not m._isRisingStar(teams[0], prime), "a prime star is not a RISING star"


if __name__ == '__main__':
    import sys, pytest
    sys.exit(pytest.main(['-q', __file__]))
