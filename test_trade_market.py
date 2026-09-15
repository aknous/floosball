"""The trade market — triggers, the auction, legality, and the seams.

⚠️ THE SEAM TESTS MATTER MORE THAN THE ARITHMETIC. Every one of them is a repeat of a
real incident in this codebase.

See docs/TRADING_PLAN.md §3, §5, §11.
"""

import inspect

import constants
from managers import tradeManager
from managers.tradeManager import TradeMarket, Listing, Bid
from floosball_player import Position

LOCKER_ROOM_ATTITUDE = tradeManager.LOCKER_ROOM_ATTITUDE


class FakeAttrs:
    def __init__(self, attitude=80):
        self.attitude = attitude


class FakePlayer:
    def __init__(self, pid, rating, position=Position.WR, termRemaining=3,
                 attitude=80, name=None, isProspect=False, prospectSeasons=0):
        self.id = pid
        self.name = name or f"P{pid}"
        self.playerRating = rating
        self.position = position
        self.termRemaining = termRemaining
        self.attributes = FakeAttrs(attitude)
        self.willRetire = False
        self.is_prospect = isProspect
        self.is_upcoming_rookie = False
        self.prospect_seasons = prospectSeasons
        self.drafting_team_id = None
        self.team = None
        self.previousTeam = None
        self.teamResignCount = 0

    def computeCeilingRating(self):
        return self.playerRating + 8

    def computeExpectedRating(self):
        return self.playerRating

    @property
    def playerTier(self):
        class T:
            name = 'TierB'
        return T()


class FakeTeam:
    def __init__(self, tid, name, wins=7, losses=7, division='North', league='Alpha'):
        self.id = tid
        self.name = name
        self.abbr = name[:3].upper()
        self.wins = wins
        self.losses = losses
        self.division = division
        self.league = league
        self.coach = None
        self.rosterDict = {'qb': None, 'rb': None, 'wr1': None, 'wr2': None,
                           'te': None, 'k': None}
        self.prospects = []

    def assignPlayerNumber(self, player):
        pass


class FakeTeamManager:
    def __init__(self, teams):
        self.teams = teams


class FakePlayerManager:
    def __init__(self, freeAgents=None):
        self.freeAgents = freeAgents or []


class StubBrain:
    sentimentMap = {}

    def decisionValue(self, player, coach=None, rng=None, team=None):
        return float(getattr(player, 'playerRating', 0))

    def perceivedValue(self, player, coach=None, rng=None, team=None):
        return float(getattr(player, 'playerRating', 0))

    def _ceilingRating(self, player, team=None):
        return player.computeCeilingRating()

    def _attrLean(self, coach, attr):
        return 0.5


def _market(teams, freeAgents=None, week=15, season=3):
    return TradeMarket(FakePlayerManager(freeAgents), FakeTeamManager(teams),
                       StubBrain(), season, week)


# ---------------------------------------------------------- the triggers

def test_expiring_surplus_fires_only_for_a_non_contender():
    """⚠️ CONGESTION ALONE DOES NOT MAKE A SELLER. The most congested club in the league
    is also the best one — it RENTS its walk-years for the playoff run and loses them at
    season end, exactly as a real contender does. Selling needs congestion AND no run to
    protect."""
    seller = FakeTeam(1, 'Rebuild', wins=3, losses=11)
    buyer = FakeTeam(2, 'Contend', wins=11, losses=3)
    walkYear = FakePlayer(10, 84, termRemaining=1)
    seller.rosterDict['wr1'] = walkYear
    buyer.rosterDict['wr1'] = FakePlayer(11, 84, termRemaining=1)
    market = _market([seller, buyer], freeAgents=[FakePlayer(99, 74)])

    assert [l.trigger for l in market.listingsFor(seller)] == ['expiring_surplus']
    assert 'expiring_surplus' not in [l.trigger for l in market.listingsFor(buyer)]
    print("PASS a rebuilder sells its walk-year; a contender rents it")


def test_a_contender_still_sells_a_locker_room_problem():
    """✅ ONLY THE FIRST TRIGGER IS CONTENTION-GATED, so no extra rule is needed to let a
    contender into the selling side. Measured, seven contending clubs hold a sub-55
    attitude player on the live league right now."""
    contender = FakeTeam(1, 'Contend', wins=12, losses=2)
    other = FakeTeam(2, 'Other', wins=7, losses=7)
    contender.rosterDict['wr1'] = FakePlayer(10, 84, termRemaining=3,
                                             attitude=LOCKER_ROOM_ATTITUDE - 10)
    market = _market([contender, other], freeAgents=[FakePlayer(99, 74)])
    assert 'locker_room' in [l.trigger for l in market.listingsFor(contender)]
    print("PASS a contender lists a headcase")


def test_a_blocked_prospect_lists_the_INCUMBENT():
    """⚠️ AND IT CANNOT FIRE WITH AN EMPTY PIPELINE, which is one of the reasons the draft
    lands first."""
    team = FakeTeam(1, 'Deep', wins=12, losses=2)
    other = FakeTeam(2, 'Other')
    incumbent = FakePlayer(10, 78, termRemaining=2)
    team.rosterDict['wr1'] = incumbent
    market = _market([team, other], freeAgents=[FakePlayer(99, 74)])
    assert 'blocked_prospect' not in [l.trigger for l in market.listingsFor(team)]

    team.prospects.append(FakePlayer(20, 88, isProspect=True))
    listings = market.listingsFor(team)
    assert [l.trigger for l in listings] == ['blocked_prospect']
    assert listings[0].player is incumbent, "it must list the incumbent, not the prospect"
    print("PASS the blocked-prospect trigger lists the man in the way")


def test_a_club_lists_at_most_its_cap():
    team = FakeTeam(1, 'Rebuild', wins=2, losses=12)
    other = FakeTeam(2, 'Other')
    for i, slot in enumerate(('qb', 'rb', 'wr1', 'wr2', 'te', 'k')):
        team.rosterDict[slot] = FakePlayer(10 + i, 84, termRemaining=1)
    market = _market([team, other], freeAgents=[FakePlayer(99, 74)])
    assert len(market.listingsFor(team)) <= constants.TRADE_LISTINGS_PER_TEAM
    print(f"PASS a club posts at most {constants.TRADE_LISTINGS_PER_TEAM}")


def test_nothing_lists_in_week_1():
    """⚠️ THE DEADLINE WITH NO DEADLINE RULE. In week 1 every club reads as league-average,
    so nobody is a non-contender and the expiring-surplus trigger cannot fire."""
    seller = FakeTeam(1, 'Rebuild', wins=0, losses=0)
    buyer = FakeTeam(2, 'Contend', wins=0, losses=0)
    seller.rosterDict['wr1'] = FakePlayer(10, 84, termRemaining=1)
    market = _market([seller, buyer], freeAgents=[FakePlayer(99, 74)], week=1)
    assert market.listingsFor(seller) == []
    print("PASS the market is silent in week 1")


# ---------------------------------------------------------- the auction

def test_the_highest_bid_above_the_reserve_wins():
    listing = Listing(FakeTeam(1, 'Seller'), FakePlayer(10, 84), 'expiring_surplus',
                      ask=10.0, floor=6.0)
    low = Bid(FakeTeam(2, 'Low'), [], 7.0)
    high = Bid(FakeTeam(3, 'High'), [], 9.0)
    under = Bid(FakeTeam(4, 'Under'), [], 3.0)
    market = _market([FakeTeam(1, 'A'), FakeTeam(2, 'B')])
    assert market.settle(listing, [low, high, under]) is high
    print("PASS the best clearing bid wins")


def test_a_bid_below_the_floor_never_wins():
    """The floor is the walk-away: below it, keeping him beats trading him."""
    listing = Listing(FakeTeam(1, 'Seller'), FakePlayer(10, 84), 'expiring_surplus',
                      ask=10.0, floor=6.0)
    market = _market([FakeTeam(1, 'A'), FakeTeam(2, 'B')])
    assert market.settle(listing, [Bid(FakeTeam(2, 'Low'), [], 5.9)]) is None
    print("PASS a bid under the reserve lapses")


def test_there_is_no_second_round():
    """⚠️ AND NO RULE IS NEEDED TO PREVENT ONE. A sealed round where each buyer bids its
    private value is already optimal discovery; an ASCENDING second round is WORSE FOR THE
    SELLER, because the winner only has to top the runner-up, so the seller captures the
    second-best valuation instead of the best. "Let me shop this around" feels like
    leverage and is a discount.

    Asserted structurally: settlement takes the bids it is given and returns one winner.
    """
    # ⚠️ Structurally: settlement must never ASK FOR ANOTHER BID. A re-bid call inside
    # `settle` is what an ascending round looks like, and it would silently convert the
    # seller's take from the best valuation to the runner-up's.
    src = inspect.getsource(TradeMarket.settle)
    assert 'bidFor' not in src, "settle() re-bids — an ascending round crept in"
    winner = _market([FakeTeam(1, 'A'), FakeTeam(2, 'B')]).settle(
        Listing(FakeTeam(1, 'S'), FakePlayer(10, 84), 't', 5.0, 2.0),
        [Bid(FakeTeam(2, 'B'), [], 9.0), Bid(FakeTeam(3, 'C'), [], 8.0)])
    assert winner.value == 9.0, "the seller captured the runner-up's valuation"
    print("PASS one sealed round; the seller captures the BEST valuation")


def test_only_a_few_counterparties_are_approached():
    """So a weekly pass stays legible in the news feed rather than being 31 conversations."""
    teams = [FakeTeam(i, f"T{i}", wins=i, losses=14 - i) for i in range(1, 15)]
    market = _market(teams)
    listing = Listing(teams[0], FakePlayer(10, 84), 'expiring_surplus', 5.0, 2.0)
    approached = market.counterpartiesFor(listing)
    assert len(approached) <= constants.TRADE_CANDIDATES_PER_LISTING
    assert teams[0] not in approached, "a club was approached about its own listing"
    # The strongest clubs first — contention is public information.
    weights = [market.nowWeight(t) for t in approached]
    assert weights == sorted(weights, reverse=True)
    print(f"PASS {len(approached)} counterparties, strongest first")


def test_a_bundle_reads_as_a_sentence():
    """⚠️ CHEAPEST COMBINATION, NOT LARGEST. A buyer that hands over everything it owns to
    clear a bar by four times is not negotiating."""
    market = _market([FakeTeam(1, 'A'), FakeTeam(2, 'B')])
    buyer = FakeTeam(2, 'B')
    market._tradeableAssets = lambda team: [
        {'kind': 'pick', 'id': i, 'name': f'p{i}', 'detail': {}, 'value': v}
        for i, v in enumerate([2.0, 3.0, 9.0, 12.0])]
    pieces = market._assemble(buyer, bar=4.0, ceiling=30.0)
    assert 0 < len(pieces) <= constants.TRADE_MAX_PIECES
    assert sum(p['value'] for p in pieces) >= 4.0
    assert sum(p['value'] for p in pieces) < 9.0, "it overpaid rather than assembling"
    print(f"PASS cleared a 4.0 bar with {len(pieces)} piece(s) worth "
          f"{sum(p['value'] for p in pieces):.1f}")


# ---------------------------------------------------------- legality

def test_the_market_is_shut_after_the_deadline():
    """⚠️ CUT / SIGN / TRADE ARE LIVE TO WEEK 22, THEN ROSTERS FREEZE until the offseason —
    a club must play what it has through the run-in and the playoffs."""
    original = constants.TRADING_ENABLED
    try:
        constants.TRADING_ENABLED = True
        tradeManager.TRADING_ENABLED = True
        seller = FakeTeam(1, 'Rebuild', wins=2, losses=20)
        buyer = FakeTeam(2, 'Contend', wins=20, losses=2)
        seller.rosterDict['wr1'] = FakePlayer(10, 84, termRemaining=1)
        out = tradeManager.runWeeklyPass(
            FakePlayerManager([FakePlayer(99, 74)]), FakeTeamManager([seller, buyer]),
            StubBrain(), 3, week=constants.GM_ACTIVE_WEEK + 1)
        assert out == []
    finally:
        constants.TRADING_ENABLED = original
        tradeManager.TRADING_ENABLED = original
    print(f"PASS nothing trades after week {constants.GM_ACTIVE_WEEK}")


def test_the_flag_shuts_the_whole_market():
    """⚠️ EVERY RISKY SYSTEM HERE SHIPPED BEHIND A FLAG — RULE_VOTE_ENABLED,
    WEATHER_ENABLED, RUNNER_MOVE_ENABLED. Trading is off until measured."""
    assert constants.TRADING_ENABLED is False, \
        "TRADING_ENABLED defaults ON — it must stay off until the market is measured"
    seller = FakeTeam(1, 'Rebuild', wins=2, losses=20)
    buyer = FakeTeam(2, 'Contend', wins=20, losses=2)
    seller.rosterDict['wr1'] = FakePlayer(10, 84, termRemaining=1)
    assert tradeManager.runWeeklyPass(
        FakePlayerManager([FakePlayer(99, 74)]), FakeTeamManager([seller, buyer]),
        StubBrain(), 3, week=15) == []
    print("PASS TRADING_ENABLED is False and the pass is a no-op")
