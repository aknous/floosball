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
    """⚠️ THE RECORD GOES IN `seasonTeamStats`, WHICH IS WHERE A REAL TEAM KEEPS IT.

    This fake used to set `self.wins` / `self.losses`, mirroring the accessor the market
    code was using — so the trigger tests below passed while PRODUCTION read zero wins for
    every club in the league, forever. A fake built on the same mistaken assumption as the
    code under test certifies the assumption rather than the behaviour. `standings_view`
    is the reference: `getattr(team, 'seasonTeamStats', {}).get('wins')`.
    """

    def __init__(self, tid, name, wins=7, losses=7, division='North', league='Alpha'):
        self.id = tid
        self.name = name
        self.abbr = name[:3].upper()
        self.seasonTeamStats = {'wins': wins, 'losses': losses, 'ties': 0}
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

def test_the_record_is_read_from_seasonTeamStats():
    """⚠️ THE ROOT CAUSE OF EVERY SYMPTOM THIS MARKET SHOWED. There is no `wins` attribute
    on a Team, so reading `team.wins` gives 0 for all 32 clubs all season — every club
    exactly league-average, the contention gradient flat, `expiring_surplus` unable to
    fire (it needs a non-contender and there were none) and `horizon_mismatch` firing for
    everybody. Measured before the fix: 0 expiring-surplus listings out of 1,468."""
    strong = FakeTeam(1, 'Strong', wins=12, losses=2)
    weak = FakeTeam(2, 'Weak', wins=2, losses=12)
    market = _market([strong, weak])
    assert market.isContending(strong) is True
    assert market.isContending(weak) is False, \
        "every club reads as league-average — the record is not being found"
    assert market.nowWeight(strong) > market.nowWeight(weak)
    print(f"PASS contention separates: {market.nowWeight(strong):.2f} vs "
          f"{market.nowWeight(weak):.2f}")


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


def _assets(values):
    return [{'kind': 'pick', 'id': i, 'name': f'p{i}', 'detail': {}, 'value': v}
            for i, v in enumerate(values)]


def test_a_bundle_reads_as_a_sentence():
    """⚠️ CHEAPEST COMBINATION, NOT LARGEST. A buyer that hands over everything it owns to
    clear a bar by four times is not negotiating."""
    market = _market([FakeTeam(1, 'A'), FakeTeam(2, 'B')])
    seller, buyer = FakeTeam(1, 'A'), FakeTeam(2, 'B')
    market._tradeableAssets = (lambda team, valuingTeam=None, swapPosition=None:
                               _assets([2.0, 3.0, 9.0, 12.0]))
    pieces = market._assemble(buyer, seller, bar=4.0, gross=30.0, displaced=0.0)
    assert 0 < len(pieces) <= constants.TRADE_MAX_PIECES
    assert sum(p['value'] for p in pieces) >= 4.0
    assert sum(p['value'] for p in pieces) < 9.0, "it overpaid rather than assembling"
    print(f"PASS cleared a 4.0 bar with {len(pieces)} piece(s) worth "
          f"{sum(p['value'] for p in pieces):.1f}")


def test_the_bundle_is_valued_on_BOTH_sides():
    """⚠️ TWO VALUATIONS OF ONE BUNDLE, AND BOTH ARE LOAD-BEARING. What clears the seller's
    bar is what the pieces are worth TO THE SELLER; what the buyer is deciding to part
    with is what the same pieces are worth TO IT. They are different numbers precisely
    because the two clubs discount the future differently — and pricing both sides at one
    club's rate collapses the gap that makes either of them agree."""
    market = _market([FakeTeam(1, 'A'), FakeTeam(2, 'B')])
    seller, buyer = FakeTeam(1, 'A'), FakeTeam(2, 'B')

    # The seller prizes these picks; the buyer barely minds losing them.
    def assets(team, valuingTeam=None, swapPosition=None):
        high = valuingTeam is seller
        return _assets([10.0, 10.0] if high else [1.0, 1.0])

    market._tradeableAssets = assets
    pieces = market._assemble(buyer, seller, bar=15.0, gross=5.0, displaced=0.0)
    assert pieces, "a bundle the seller values at 20 did not clear its bar of 15"
    assert sum(p['value'] for p in pieces) >= 15.0, \
        "the bundle was sized on the BUYER's valuation, not the seller's"
    print("PASS a bundle the buyer prices cheap can still clear a high seller bar")


def test_a_buyer_refuses_a_bundle_that_costs_more_than_the_upgrade():
    """The other half: the seller's bar being cleared is not enough if parting with the
    pieces costs the buyer more than it gains."""
    market = _market([FakeTeam(1, 'A'), FakeTeam(2, 'B')])
    seller, buyer = FakeTeam(1, 'A'), FakeTeam(2, 'B')
    market._tradeableAssets = (lambda team, valuingTeam=None, swapPosition=None:
                               _assets([50.0, 50.0]))
    assert market._assemble(buyer, seller, bar=40.0, gross=5.0, displaced=0.0) == []
    assert market._assemble(buyer, seller, bar=40.0, gross=500.0, displaced=0.0) != []
    print("PASS a buyer walks away when the price exceeds the upgrade")


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


# ------------------------------------------------ pass-the-parcel

def test_a_player_acquired_this_season_cannot_be_moved_again():
    """⚠️ THE LEDGER SHOWED THIS HAPPENING. Over six measured seasons, prospects were being
    flipped twice inside one season — Slippers -> Strangers in week 15 and Strangers ->
    Cranes in the same offseason — which turns an asset into a token being passed around
    rather than a player a club decided it wanted. `docs/TRADING_PLAN.md` §5 lists the
    rule; it was never implemented."""
    seller = FakeTeam(1, 'Rebuild', wins=3, losses=11)
    other = FakeTeam(2, 'Other')
    justArrived = FakePlayer(10, 84, termRemaining=1)
    seller.rosterDict['wr1'] = justArrived
    market = _market([seller, other], freeAgents=[FakePlayer(99, 74)], week=20)

    assert market.listingsFor(seller), "fixture is wrong — he should be listable"
    tradeManager._stampAcquired(justArrived, market.season)
    assert market.listingsFor(seller) == [], "he was re-listed the season he arrived"
    print("PASS a player cannot be flipped in the season he arrived")


def test_the_rule_covers_BUNDLE_PIECES_too():
    """⚠️ Every trade in the measured ledger paid in prospects and picks, so a rule that
    only guarded the headline player would guard the one asset class that was never
    actually being flipped."""
    team = FakeTeam(1, 'Deep')
    other = FakeTeam(2, 'Other')
    prospect = FakePlayer(20, 80, isProspect=True, prospectSeasons=0)
    team.prospects.append(prospect)
    market = _market([team, other], week=20)
    market.picksOwnedBy = lambda t: []

    assert any(a['id'] == 20 for a in market._tradeableAssets(team)), \
        "fixture is wrong — he should be offerable"
    tradeManager._stampAcquired(prospect, market.season)
    assert not any(a['id'] == 20 for a in market._tradeableAssets(team))
    print("PASS a just-acquired prospect cannot be re-bundled")


def test_the_stamp_is_scoped_to_ITS_season():
    """Next season he is a normal asset again — the rule is about churn within a season,
    not a permanent freeze."""
    player = FakePlayer(10, 84)
    tradeManager._stampAcquired(player, 5)
    assert tradeManager.wasAcquiredThisSeason(player, 5) is True
    assert tradeManager.wasAcquiredThisSeason(player, 6) is False
    assert tradeManager.wasAcquiredThisSeason(FakePlayer(11, 84), 5) is False
    print("PASS the stamp expires with the season")


# --------------------------------------- the same-position swap

def test_a_starter_at_the_listings_position_is_offerable():
    """⚠️ WITHOUT THIS EVERY TRADE IN THE LEAGUE IS THE SAME SHAPE — one player out, picks
    and prospects back, measured 35 times in 35. `docs/TRADING_PLAN.md` §5 lists
    "position-for-position" FIRST in its legality table, because a same-position swap
    refills both holes by construction: no free agent to sign, no prospect to promote, no
    cut fee."""
    buyer = FakeTeam(2, 'Buyer')
    buyer.rosterDict['qb'] = FakePlayer(30, 82, Position.QB, termRemaining=3)
    market = _market([FakeTeam(1, 'A'), buyer])
    market.picksOwnedBy = lambda t: []

    assert market._tradeableAssets(buyer) == [], "a starter leaked in with no swap position"
    offered = market._tradeableAssets(buyer, swapPosition=Position.QB.value)
    assert [a['kind'] for a in offered] == ['player']
    assert offered[0]['id'] == 30
    print("PASS a starter is offerable only at the listing's own position")


def test_only_one_starter_per_bundle():
    """⚠️ Two would EMPTY the position the incoming player is meant to fill — the hole the
    whole swap exists to avoid."""
    buyer = FakeTeam(2, 'Buyer')
    buyer.rosterDict['wr1'] = FakePlayer(30, 80, Position.WR, termRemaining=3)
    buyer.rosterDict['wr2'] = FakePlayer(31, 80, Position.WR, termRemaining=3)
    seller = FakeTeam(1, 'Seller')
    market = _market([seller, buyer])
    market.picksOwnedBy = lambda t: []

    # ⚠️ THE BAR HAS TO BE HIGH ENOUGH THAT THE BUNDLE WANTS MORE THAN ONE PIECE. At a low
    # bar `_assemble` stops after the first piece whatever the cap says, so the test
    # passes without ever exercising it — which is exactly what happened first time.
    both = market._tradeableAssets(buyer, valuingTeam=seller,
                                   swapPosition=Position.WR.value)
    assert len(both) == 2, both
    greedyBar = sum(a['value'] for a in both)

    pieces = market._assemble(buyer, seller, bar=greedyBar, gross=9999.0, displaced=0.0,
                              swapPosition=Position.WR.value)
    assert sum(1 for p in pieces if p['kind'] == 'player') <= 1, pieces
    print("PASS at most one starter leaves, even when the bundle wants two")


def test_the_displaced_player_is_counted_ONCE_in_a_swap():
    """⚠️ WHEN THE BUYER PAYS WITH THE MAN IT WOULD OTHERWISE HAVE CUT, the displacement
    and the payment are THE SAME EVENT. Charging both makes a swap look twice as expensive
    as it is and refuses nearly every one — while paying in picks really does cost the
    club both the picks and the displaced player (plus a cut fee)."""
    seller, buyer = FakeTeam(1, 'Seller'), FakeTeam(2, 'Buyer')
    market = _market([seller, buyer])

    # The only thing the buyer can offer is the very man it would have to cut, worth 6.
    def assets(team, valuingTeam=None, swapPosition=None):
        if swapPosition is None:
            return []
        return [{'kind': 'player', 'id': 30, 'name': 'Incumbent',
                 'detail': {'slot': 'qb'}, 'value': 6.0}]

    market._tradeableAssets = assets

    # Incoming is worth 10; the displaced man is worth 6. Paying WITH him costs 6 once,
    # so 10 - 6 = +4 and the trade is on.
    swap = market._assemble(buyer, seller, bar=1.0, gross=10.0, displaced=6.0,
                            swapPosition=Position.QB.value)
    assert swap, "a swap was refused by double-charging the displaced player"
    assert swap[0]['kind'] == 'player'

    # ⚠️ The mirror: paying in PICKS really does cost both the picks and the displaced
    # man, so an identically-priced picks bundle must be refused at the same numbers.
    def picksOnly(team, valuingTeam=None, swapPosition=None):
        return [{'kind': 'pick', 'id': 7, 'name': 'a pick', 'detail': {}, 'value': 6.0}]

    market._tradeableAssets = picksOnly
    assert market._assemble(buyer, seller, bar=1.0, gross=10.0, displaced=6.0,
                            swapPosition=Position.QB.value) == [], \
        "a picks bundle escaped being charged for the displaced player"
    print("PASS a swap is charged once for the man, a picks bundle twice")


def test_a_swap_needs_no_backfill_and_no_cut():
    """The structural payoff, asserted on the settlement path: with a player coming back
    the seller's slot is filled by him, so neither `_findBackfill` nor `_cutToMakeRoom`
    is consulted at all."""
    import inspect
    src = inspect.getsource(tradeManager.settleTrade)
    swapBranch = src[src.index('swap = _swapPieceOf'):]
    head = swapBranch[:swapBranch.index('# ---- 2. move')]
    assert 'if swap is None:' in head
    assert head.index('if swap is None:') < head.index('_findBackfill'), \
        "the backfill is looked up before checking for a swap"
    assert 'else:' in head and '_slotOf(buyer, swap)' in head
    print("PASS a swap skips the backfill and the cut entirely")
