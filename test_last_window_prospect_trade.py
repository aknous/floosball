"""A prospect on his last window, who will not make his team's roster, is sold in season
rather than lost for nothing (owner, 2026-11-06). Season-13 snapshot: 10-11 drafted
prospects washed out each offseason, and the best (the Pops' Screendoor Windup, QB 78)
went to another team in the FA draft for nothing.

Run: .venv/bin/python -m pytest -q test_last_window_prospect_trade.py
"""
import logging
logging.disable(logging.WARNING)

from constants import PROSPECT_DEVELOPMENT_WINDOW
from floosball_player import Position
from managers import tradeManager, tradeVotes
from managers.tradeManager import TradeMarket, ProspectListing
from test_trade_market import FakePlayer, FakeTeam, FakeTeamManager, FakePlayerManager, StubBrain

LAST = PROSPECT_DEVELOPMENT_WINDOW - 1


class Brain(StubBrain):
    def prospectReplacesStarter(self, prospect, starter, team=None, coach=None, finalWindow=False):
        return prospect.playerRating >= starter.playerRating - 4


class PM(FakePlayerManager):
    def __init__(self, room=True):
        super().__init__()
        self.room = room

    def hasOpenProspectSlot(self, team, position):
        return self.room


def _setup(week=15, room=True):
    seller = FakeTeam(1, 'Seller', wins=10, losses=5)
    buyer = FakeTeam(2, 'Buyer', wins=6, losses=9)
    seller.rosterDict['qb'] = FakePlayer(10, 90, Position.QB, termRemaining=3)
    kid = FakePlayer(11, 78, Position.QB, isProspect=True, prospectSeasons=LAST, name='Kid')
    seller.prospects = [kid]
    buyer.rosterDict['qb'] = FakePlayer(20, 72, Position.QB, termRemaining=3)
    buyer.prospects = [FakePlayer(21, 70, Position.RB, isProspect=True, prospectSeasons=0)]
    market = TradeMarket(PM(room), FakeTeamManager([seller, buyer]), Brain(), 3, week)
    return market, seller, buyer, kid


def test_a_blocked_last_window_prospect_goes_on_the_block():
    market, seller, _b, kid = _setup()
    listings = market.prospectListingsFor(seller)
    assert len(listings) == 1 and listings[0].prospect is kid
    assert isinstance(listings[0], ProspectListing) and listings[0].floor == 0.0
    print("PASS a blocked last-window prospect goes on the block")


def test_a_prospect_who_will_make_the_roster_is_not_listed():
    market, seller, _b, kid = _setup()
    seller.rosterDict['qb'] = None                       # an open slot: he is promoted
    assert market.prospectListingsFor(seller) == []
    market, seller, _b, kid = _setup()
    kid.prospect_seasons = LAST - 1                      # not his last window yet
    assert market.prospectListingsFor(seller) == []
    market, seller, _b, kid = _setup(week=None)          # offseason: no listings
    assert market.prospectListingsFor(seller) == []
    print("PASS a prospect with a way onto the roster is not listed")


def test_a_team_where_he_would_play_bids_and_one_where_he_would_not_does_not():
    market, seller, buyer, kid = _setup()
    listing = market.prospectListingsFor(seller)[0]
    bid = market.bidForProspect(listing, buyer)       # he beats the buyer's 72 QB
    assert bid is not None and bid.pieces, bid
    buyer.rosterDict['qb'] = FakePlayer(22, 92, Position.QB, termRemaining=3)
    assert market.bidForProspect(listing, buyer) is None   # blocked there too
    market, seller, buyer, kid = _setup(room=False)
    listing = market.prospectListingsFor(seller)[0]
    assert market.bidForProspect(listing, buyer) is None   # no room in its pipeline
    print("PASS only a team with a place for him bids")


def test_a_proposal_round_trips_through_the_vote():
    market, seller, buyer, kid = _setup()
    listing = market.prospectListingsFor(seller)[0]
    bid = market.bidForProspect(listing, buyer)
    entry = {'listing': listing, 'winner': bid, 'kind': 'prospect'}
    kind, lj, bj = tradeVotes._serialize(entry)
    assert kind == 'prospect' and lj['prospectId'] == kid.id
    assert tradeVotes._assetsOf(entry)['aGave'][0]['kind'] == 'prospect'

    class Row:
        pass
    row = Row()
    row.team_a_id, row.team_b_id, row.kind = seller.id, buyer.id, kind
    row.listing_json, row.bid_json = lj, bj
    rebuilt = tradeVotes._rebuild(row, FakeTeamManager([seller, buyer]))
    assert rebuilt['kind'] == 'prospect' and rebuilt['listing'].prospect is kid
    print("PASS a prospect sale round-trips through the vote")


def test_settlement_moves_the_prospect_and_the_payment(monkeypatch):
    market, seller, buyer, kid = _setup()
    listing = market.prospectListingsFor(seller)[0]
    bid = market.bidForProspect(listing, buyer)
    moved = []
    monkeypatch.setattr(tradeManager, '_persistTrade', lambda m: 1)
    monkeypatch.setattr(tradeManager, '_recordTrade', lambda *a, **k: None)
    monkeypatch.setattr(tradeManager, '_publishTrade', lambda *a, **k: None)

    def handOver(sm, pieces, fromTeam, toTeam, season=0, **kw):
        moved.append(([p['id'] for p in pieces], fromTeam.name, toTeam.name))
        for p in pieces:
            if p['kind'] == 'prospect':
                pr = tradeManager._findProspect(fromTeam, p['id'])
                fromTeam.prospects.remove(pr)
                toTeam.prospects.append(pr)
        return [{k: p[k] for k in ('kind', 'id', 'name')} for p in pieces]
    monkeypatch.setattr(tradeManager, '_handOverPieces', handOver)

    class SM:
        playerManager = PM()
    assert tradeManager.settleProspectTrade(SM(), listing, bid, 3, 15, dryRun=True) is True
    manifest = tradeManager.settleProspectTrade(SM(), listing, bid, 3, 15)
    assert manifest and manifest['aGave'][0]['id'] == kid.id
    assert kid in buyer.prospects and kid not in seller.prospects
    print("PASS settlement moves the prospect and the payment")


def test_an_open_slot_a_better_free_agent_will_take_is_no_place_for_him():
    """The last look promotes him into an open slot only if no free agent the team can
    expect is better, so the market asks the same: on the season-13 snapshot a looser
    test sent 4 of 6 bought prospects to wash out at their new team."""
    from managers.frontOfficeBrain import FrontOfficeBrain

    class MarketBrain(Brain):
        prospectTakesSlot = FrontOfficeBrain.prospectTakesSlot

        def seasonRating(self, player, coach=None, team=None):
            return float(player.playerRating)

    class MarketPM(PM):
        def __init__(self, fa):
            super().__init__()
            self.fa = fa

        def _planMarket(self, brain, team, position, faOrder, k=1, shift=0, intent=None, count=1):
            return [self.fa]

    market, seller, buyer, kid = _setup()
    buyer.rosterDict['qb'] = None
    good = FakePlayer(30, 84, Position.QB, termRemaining=0)
    market = TradeMarket(MarketPM(good), FakeTeamManager([seller, buyer]), MarketBrain(), 3, 15)
    assert not market._prospectMakesRoster(buyer, kid)
    market = TradeMarket(MarketPM(FakePlayer(31, 70, Position.QB, termRemaining=0)),
                         FakeTeamManager([seller, buyer]), MarketBrain(), 3, 15)
    assert market._prospectMakesRoster(buyer, kid)
    print("PASS an open slot a better free agent will take is no place for him")
