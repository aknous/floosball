"""The trade valuation audit (2026-11-02), one test per fix.

  1/2. A player at or past his peak season is never "developing", so a seller projects
       him with the sim's aging rather than toward his ceiling, and only a young roster
       opens a window.
  3.   The offseason prices the future off next season's ELO prior, not parity.
  4.   A prospect offered in a trade is valued with the RECEIVING team's scouting read.
  5.   Scouting is charged once: growth as projected, aging half public plus scouting.
  6.   A buyer prices an incoming player's later seasons at its own projection of him.

Run with pytest (pytest-style file).
"""

import constants
import trading
from managers.frontOfficeBrain import FrontOfficeBrain, ARC_DEVELOPING, ARC_PRIME
from managers.tradeManager import TradeMarket
from test_front_office_brain import FakePlayer as BrainPlayer, FakeCoach, FakePlayerManager
from test_trade_market import (FakePlayer, FakeTeam, FakeTeamManager, StubBrain,
                               FakePlayerManager as MarketPlayerManager)
from floosball_player import Position

SEASON = 11


# ------------------------------------------------------------ 1/2. the arc label

def test_a_past_peak_player_with_headroom_is_prime_not_developing():
    """Measured on the season-11 prod snapshot: 62 of 146 'developing' starters were at or
    past their peak, because a declining player's headroom grows as he ages."""
    brain = FrontOfficeBrain(FakePlayerManager())
    rising = BrainPlayer('Kid', 76, ceiling=94)
    fading = BrainPlayer('Vet', 76, ceiling=94, pastPeak=74)
    assert brain.classifyArc(rising) == ARC_DEVELOPING
    assert brain.classifyArc(fading) == ARC_PRIME


def test_a_past_peak_player_is_projected_with_the_sims_aging():
    """Frig Lagotis' shape: rated 90, sim projection 87, ceiling well above. The forward
    read must go down, not toward the ceiling."""
    brain = FrontOfficeBrain(FakePlayerManager())
    vet = BrainPlayer('Vet', 90, expected=94, ceiling=97, pastPeak=87)
    coach = FakeCoach(scouting=100)
    assert brain.trueForwardRating(vet, coach) == 87
    assert brain.seenForward(vet, brain.trueForwardRating(vet, coach), coach) < 90


# ------------------------------------------------------------ 3. offseason contention

def _market(week, teams):
    return TradeMarket(MarketPlayerManager([]), FakeTeamManager(teams), StubBrain(), SEASON, week)


def test_the_offseason_prices_the_future_off_next_seasons_prior():
    good, bad = FakeTeam(1, 'Good', 20, 8), FakeTeam(2, 'Bad', 6, 22)
    good.elo, bad.elo = 1700, 1300
    m = _market(None, [good, bad])
    assert m.nowWeight(good) > 1.0 > m.nowWeight(bad)
    # The regression is the uncertainty: weaker than the in-season record would be.
    inSeason = _market(20, [good, bad])
    assert inSeason.nowWeight(bad) < m.nowWeight(bad)


def test_the_prior_regresses_like_the_season_reset():
    e = 1700
    regressed = 1500 + (e - 1500) * (1 - constants.ELO_SEASON_REGRESSION)
    assert abs(trading.priorContention(e)
               - 1 / (1 + 10 ** ((1500 - regressed) / 400))) < 1e-12
    assert trading.priorContention(None) == 0.5
    assert abs(trading.priorContention(1600) + trading.priorContention(1400) - 1.0) < 1e-12


def test_the_hump_still_reads_the_record_in_the_offseason():
    """isContending asks how the season went; only the future weight moved to the prior."""
    good, bad = FakeTeam(1, 'Good', 20, 8), FakeTeam(2, 'Bad', 6, 22)
    good.elo, bad.elo = 1300, 1700          # deliberately backwards
    m = _market(None, [good, bad])
    assert m.isContending(good) and not m.isContending(bad)


# ------------------------------------------------------------ 4. incoming prospects

class ReadsByTeam(StubBrain):
    def _ceilingRating(self, player, team=None):
        return {1: 90, 2: 75}[team.id]


def test_a_prospect_in_a_bundle_is_read_by_the_team_valuing_him():
    buyer, seller = FakeTeam(1, 'Buyer'), FakeTeam(2, 'Seller')
    kid = FakePlayer(50, 70, Position.WR, isProspect=True)
    buyer.prospects = [kid]
    m = TradeMarket(MarketPlayerManager([]), FakeTeamManager([buyer, seller]),
                    ReadsByTeam(), SEASON, None)
    m.picksOwnedBy = lambda team: []
    toBuyer = next(a['value'] for a in m._tradeableAssets(buyer, valuingTeam=buyer)
                   if a['kind'] == 'prospect')
    toSeller = next(a['value'] for a in m._tradeableAssets(buyer, valuingTeam=seller)
                    if a['kind'] == 'prospect')
    assert toSeller < toBuyer, "the seller priced him through the buyer's scouting"


# ------------------------------------------------------------ 5. one scouting charge

def test_a_known_rise_reads_the_same_for_a_poor_and_a_sharp_scout():
    brain = FrontOfficeBrain(FakePlayerManager())
    kid = BrainPlayer('Kid', 76, ceiling=92)
    poor, sharp = FakeCoach(scouting=60), FakeCoach(scouting=100)
    assert brain.seasonRating(kid, poor) == brain.seasonRating(kid, sharp) > 76


def test_aging_is_half_public():
    brain = FrontOfficeBrain(FakePlayerManager())
    vet = BrainPlayer('Vet', 90, pastPeak=86)
    blind, sharp = FakeCoach(scouting=60), FakeCoach(scouting=100)
    assert abs(brain.seasonRating(vet, blind) - 88.0) < 1e-9
    assert abs(brain.seasonRating(vet, sharp) - 86.0) < 1e-9


# ------------------------------------------------------------ 6. the buyer looks forward

def test_the_buyer_prices_later_seasons_at_its_projection():
    """The seller priced a rising player's later seasons at his projection and the buyer
    priced every season at one rating, so the ask ran over anything a buyer could see."""
    from test_trade_projection import ProjectingBrain, _market, _player
    from constants import FO_CEILING_CREDIT
    norman = _player(1, 74, 'Norman', 3, expected=88)
    prime = _player(2, 85, 'Prime', 3)
    brain = ProjectingBrain(forward={'Norman': 79}, arcs={'Norman': 'developing'},
                            ceilings={'Norman': 90})
    m, teams = _market(brain, [norman, prime])
    buyer = teams[1]
    # A scouting error of +2 on this season carries onto the later ones.
    assert abs(m._buyerFutureRating(buyer, norman, 81.0) - (88 + 2 * FO_CEILING_CREDIT + 2)) < 1e-6
    # A prime player's later seasons price exactly as this one, as before.
    assert abs(m._buyerFutureRating(buyer, prime, 86.0) - 86.0) < 1e-6
