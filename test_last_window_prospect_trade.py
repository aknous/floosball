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


class PlanPM(PM):
    """A player manager whose team plan holds the given prospect ids."""
    def __init__(self, promotes=(), committed=(), buyerTakes=True):
        super().__init__()
        self.promotes = set(promotes)
        self.committed = set(committed)
        self.buyerTakes = buyerTakes      # does a buyer's plan promote the added prospect
        self.calls = []

    def positionPlan(self, brain, team, position, intent=None, contractShift=0,
                     extra=None, faOrder=None, settled=False):
        if extra is not None:
            return [[{'player': extra, 'source': 'rookie', 'rating': 0}]] if self.buyerTakes else [[]]
        self.calls.append((contractShift, settled))
        holders = [p for p in team.prospects if p.id in self.promotes]
        return [[{'player': p, 'source': 'prospect', 'rating': p.playerRating}]
                for p in holders] or [[], [], []]

    def committedProspect(self, team, prospects):
        return next((p for p in prospects if p.id in self.committed), None)


def _earlySetup(week=15, afterFaDraft=False, **pmKw):
    """The Strangers' case: the slot went to a rookie, and an earlier-window prospect
    at the position sits behind him."""
    seller = FakeTeam(1, 'Strangers', wins=10, losses=5)
    buyer = FakeTeam(2, 'Buyer', wins=6, losses=9)
    seller.rosterDict['rb'] = FakePlayer(10, 84, Position.RB, termRemaining=3)
    kid = FakePlayer(11, 74, Position.RB, isProspect=True, prospectSeasons=LAST - 1,
                     name='Cockatoo')
    seller.prospects = [kid]
    buyer.rosterDict['rb'] = FakePlayer(20, 68, Position.RB, termRemaining=3)
    # a cheap piece: anything worth more than the RB is to the buyer, it will not pay
    buyer.prospects = [FakePlayer(21, 80, Position.K, isProspect=True, prospectSeasons=0)]
    pm = PlanPM(**pmKw)
    market = TradeMarket(pm, FakeTeamManager([seller, buyer]), Brain(), 3, week,
                         afterFaDraft=afterFaDraft)
    return market, seller, buyer, kid, pm


def test_an_earlier_prospect_the_plan_never_promotes_goes_on_the_block():
    market, seller, _b, kid, pm = _earlySetup()
    listings = market.prospectListingsFor(seller)
    assert len(listings) == 1 and listings[0].prospect is kid
    assert listings[0].trigger == 'surplus_prospect' and listings[0].ask == 0.0
    assert pm.calls == [(1, False)]          # in season: next offseason's countdown ahead
    market, seller, _b, kid, _pm = _earlySetup(promotes={11})
    assert market.prospectListingsFor(seller) == []      # the plan has him taking over
    market, seller, _b, kid, _pm = _earlySetup(committed={11})
    assert market.prospectListingsFor(seller) == []      # a commitment is never sold
    print("PASS an earlier-window prospect the plan never promotes goes on the block")


def test_the_pass_after_the_fa_draft_sells_too_but_not_the_one_before_it():
    market, seller, _b, kid, pm = _earlySetup(week=None, afterFaDraft=True)
    listings = market.prospectListingsFor(seller)
    assert len(listings) == 1 and listings[0].prospect is kid
    assert pm.calls == [(0, True)]           # countdown done, season 1 decided
    market, seller, _b, kid, _pm = _earlySetup(week=None, afterFaDraft=False)
    assert market.prospectListingsFor(seller) == []      # before the draft: no
    print("PASS the pass after the FA draft sells a blocked prospect")


def test_the_kind_of_sale_survives_the_vote():
    market, seller, buyer, kid, _pm = _earlySetup()
    listing = market.prospectListingsFor(seller)[0]
    bid = market.bidForProspect(listing, buyer)
    assert bid is not None, 'a team with a place for him bids'
    kind, lj, bj = tradeVotes._serialize({'listing': listing, 'winner': bid, 'kind': 'prospect'})

    class Row:
        pass
    row = Row()
    row.team_a_id, row.team_b_id, row.kind = seller.id, buyer.id, kind
    row.listing_json, row.bid_json = lj, bj
    rebuilt = tradeVotes._rebuild(row, FakeTeamManager([seller, buyer]))
    assert rebuilt['listing'].trigger == 'surplus_prospect'
    print("PASS the sale's kind survives the vote")


def test_a_buyer_whose_plan_would_not_promote_him_does_not_bid():
    """Uber Whitcomb was bought into a slot whose starter the buyer kept, and a team
    bought two QB prospects for one slot: an earlier-window prospect is bought only if
    the buyer's own plan, with him in it, promotes him."""
    market, seller, buyer, kid, _pm = _earlySetup(buyerTakes=False)
    listing = market.prospectListingsFor(seller)[0]
    assert market.bidForProspect(listing, buyer) is None
    market, seller, buyer, kid, _pm = _earlySetup(buyerTakes=True)
    listing = market.prospectListingsFor(seller)[0]
    assert market.bidForProspect(listing, buyer) is not None
    print("PASS a buyer whose plan would not promote him does not bid")


def test_a_prospect_bought_in_a_sale_is_not_sold_on():
    market, seller, _b, kid, _pm = _earlySetup()
    market._prospectBuys = {(seller.id, kid.id)}
    assert market.prospectListingsFor(seller) == []
    print("PASS a prospect bought in a sale is not sold on")


def test_a_committed_prospect_is_not_used_as_payment():
    """A team that let a starter walk at step 3 because a prospect covers the slot must
    not pay with that prospect before the draft: the slot would be empty and the starter
    already gone."""
    market, _s, buyer, _kid, _pm = _earlySetup(week=None)
    assert 21 in [a['id'] for a in market._tradeableAssets(buyer) if a['kind'] == 'prospect']
    market, _s, buyer, _kid, _pm = _earlySetup(week=None, committed={21})
    assert 21 not in [a['id'] for a in market._tradeableAssets(buyer) if a['kind'] == 'prospect']
    print("PASS a committed prospect is not used as payment")

