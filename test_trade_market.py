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


def _congest(team, ratings=(84, 80, 76), position=Position.WR):
    """Put more walk-year players on a club than `RESIGN_LIMIT_PER_OFFSEASON` can keep.

    ⚠️ CONTRACT CONGESTION IS THE ENGINE OF THIS MARKET. A club with one expiring player
    re-signs him and sells nothing, so any fixture testing the expiring trigger has to be
    over the limit or it is testing the wrong league.
    """
    slots = ['wr1', 'wr2', 'te', 'qb', 'rb', 'k']
    for i, rating in enumerate(ratings):
        team.rosterDict[slots[i]] = FakePlayer(100 + team.id * 10 + i, rating,
                                               position, termRemaining=1)
    return team


def _withCore(team):
    """Give a club two untouchable stars, so the player under test is a real asset.

    ⚠️ WITHOUT THIS, EVERY FIXTURE'S BEST PLAYER IS THE FRANCHISE. A club's top two
    4-star-or-better players are not trade assets, so a lone 92 on a test roster is
    exempt from the value triggers and the fixture is testing the core rule by accident
    instead of the rule it names.
    """
    team.rosterDict['qb'] = FakePlayer(900 + team.id, 96, Position.QB, termRemaining=4)
    team.rosterDict['rb'] = FakePlayer(950 + team.id, 95, Position.RB, termRemaining=4)
    return team


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
    # ⚠️ CONGESTED ON PURPOSE. The trigger is "walk-year, OVER the re-sign limit, not
    # contending" — with only one expiring player a club just re-signs him, so a
    # single-walker fixture tests nothing the market should do.
    _congest(seller, ratings=(84, 80, 76))
    _congest(buyer, ratings=(84, 80, 76))
    market = _market([seller, buyer], freeAgents=[FakePlayer(99, 74)])

    assert [l.trigger for l in market.listingsFor(seller)] == ['expiring_surplus']
    assert 'expiring_surplus' not in [l.trigger for l in market.listingsFor(buyer)]
    print("PASS a rebuilder sells its walk-year surplus; a contender rents it")


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
    _congest(seller, ratings=(84, 80, 76))
    market = _market([seller, other], freeAgents=[FakePlayer(99, 74)], week=20)

    before = market.listingsFor(seller)
    assert before, "fixture is wrong — someone should be listable"
    # Stamp whoever the club actually posted, so the guard is tested on the real listing
    # rather than on a player the market had already passed over.
    tradeManager._stampAcquired(before[0].player, market.season)
    after = [l for l in market.listingsFor(seller) if l.player is before[0].player]
    assert after == [], "he was re-listed the season he arrived"
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


# --------------------------------- the re-sign cap is what makes a surplus

def test_a_club_does_not_sell_a_walk_year_player_it_can_simply_re_sign():
    """⚠️ "HE LEAVES FOR NOTHING" IS THE WHOLE PREMISE, AND IT IS FALSE FOR A PLAYER THE
    CLUB CAN KEEP. The plan's trigger is "walk-year, OVER THE RE-SIGN LIMIT, not
    contending"; the middle third was never built, so it fired on every expiring player
    and clubs sold their best men for scraps — a 1-14 club shipped a 93-rated kicker for
    one prospect at an ask of 0.3.

    ⚠️ The live constraint is the PER-OFFSEASON cap, not a per-player one:
    `RESIGN_ONCE_ENABLED` has been False since 2026-08-13."""
    other = FakeTeam(9, 'Other')
    pool = [FakePlayer(99, 74, Position.WR)]

    # ⚠️ One star on a walk year with a free re-sign slot is NOT surplus. He is still
    # available — a club can deem a highly rated player expendable if the return is worth
    # it — but under a different trigger and at a retention price, not a rental's.
    calm = _withCore(FakeTeam(1, 'Calm', wins=3, losses=11))
    calm.rosterDict['wr1'] = FakePlayer(10, 93, Position.WR, termRemaining=1)
    calmListings = _market([calm, other], freeAgents=pool, week=20).listingsFor(calm)
    assert [l.trigger for l in calmListings] == ['expiring_keeper'], calmListings

    # ⚠️ THREE expiring against a cap of two. Only now is one of them genuinely leaving.
    congested = _withCore(FakeTeam(2, 'Congested', wins=3, losses=11))
    _congest(congested, ratings=(93, 80, 76), position=Position.WR)
    listings = _market([congested, other], freeAgents=pool, week=20).listingsFor(congested)
    assert [l.trigger for l in listings] == ['expiring_surplus'], listings
    assert listings[0].player.playerRating != 93, \
        "the club put its BEST expiring player on the block as SURPLUS, not its spare"
    print(f"PASS the keepable star is a priced keeper; the surplus "
          f"({listings[0].player.playerRating:g}) is the one leaving for nothing")


def test_a_keeper_costs_far_more_than_a_surplus_walk_year():
    """⚠️ THE PRICE IS THE WHOLE MECHANISM (owner: a highly rated player can be expendable
    "as long as the return is worth it"). A club that can re-sign him is not selling a
    rental — a buyer is acquiring the contract that would follow — so he has to be valued
    on it. Priced as a rental, a 92 on a walk year is worth a few weeks of football and
    goes for scraps: measured, a 1-14 club shipped a 93-rated kicker for one prospect at
    an ask of 0.3."""
    other = FakeTeam(9, 'Other')
    pool = [FakePlayer(99, 74, Position.WR)]

    keeper = _withCore(FakeTeam(1, 'Keeper', wins=3, losses=11))
    keeper.rosterDict['wr1'] = FakePlayer(10, 92, Position.WR, termRemaining=1)
    keeperAsk = _market([keeper, other], freeAgents=pool,
                        week=20).listingsFor(keeper)[0].ask

    congested = _withCore(FakeTeam(2, 'Congested', wins=3, losses=11))
    _congest(congested, ratings=(92, 92, 92), position=Position.WR)
    surplusAsk = _market([congested, other], freeAgents=pool,
                         week=20).listingsFor(congested)[0].ask

    assert keeperAsk > surplusAsk * 3, (keeperAsk, surplusAsk)
    print(f"PASS the same 92 asks {keeperAsk:.1f} as a keeper against "
          f"{surplusAsk:.1f} as surplus — {keeperAsk / surplusAsk:.0f}x")


def test_the_best_expiring_players_are_the_ones_kept():
    """Ranked on the club's own `decisionValue` — the same number the offseason retention
    pass uses, so the market and the front office cannot disagree about who is keepable."""
    from constants import RESIGN_LIMIT_PER_OFFSEASON
    seller = FakeTeam(1, 'Rebuild', wins=2, losses=12)
    other = FakeTeam(2, 'Other')
    _congest(seller, ratings=(92, 88, 84, 80), position=Position.WR)
    market = _market([seller, other], freeAgents=[FakePlayer(99, 74)], week=20)

    surplus = market._cannotKeep(seller)
    expiring = [p for p in seller.rosterDict.values()
                if p is not None and p.termRemaining <= 1]
    kept = [p for p in expiring if id(p) not in surplus]
    assert len(kept) == RESIGN_LIMIT_PER_OFFSEASON, (len(kept), RESIGN_LIMIT_PER_OFFSEASON)
    assert min(p.playerRating for p in kept) > max(
        p.playerRating for p in expiring if id(p) in surplus)
    print(f"PASS the top {RESIGN_LIMIT_PER_OFFSEASON} are kept "
          f"({sorted((p.playerRating for p in kept), reverse=True)}), the rest are surplus")


def test_the_buyer_prices_a_walk_year_player_through_ITS_OWN_cap():
    """⚠️ ONE RULE, BOTH SIDES. The seller was pricing a keepable star on the contract that
    would follow while the buyer still priced him as a thirteen-week rental — ask 108
    against a bid of 3.5 — so NOT ONE keeper ever sold: measured, 245 listed and zero
    clearing bids.

    ⚠️ And whether he is keepable is a property of the CLUB, not the player. A contender
    with three mediocre walk-years can keep a 92 (he displaces one); a club already holding
    two better men cannot. That is what makes the same player genuinely expendable to one
    club and untouchable to another."""
    star = FakePlayer(10, 92, Position.WR, termRemaining=1)

    roomy = FakeTeam(1, 'Roomy', wins=11, losses=3)
    roomy.rosterDict['rb'] = FakePlayer(20, 70, Position.RB, termRemaining=1)
    market = _market([roomy, FakeTeam(9, 'Other')])
    assert market.retentionTerm(roomy, star, incoming=True) > 0, \
        "a club with a free re-sign slot valued him as a pure rental"

    crowded = FakeTeam(2, 'Crowded', wins=11, losses=3)
    for i, slot in enumerate(('qb', 'rb')):
        crowded.rosterDict[slot] = FakePlayer(30 + i, 97, Position.QB, termRemaining=1)
    market2 = _market([crowded, FakeTeam(9, 'Other')])
    assert market2.retentionTerm(crowded, star, incoming=True) == 0.0, \
        "a club already holding two better walk-years still priced in a re-sign"
    print("PASS the same 92 is a keeper to one club and a rental to another")


def test_surplus_and_keeper_come_from_ONE_rule():
    """`retentionTerm` returns 0 for a player over the club's cap, so the two triggers are
    the same rule seen from either side of the limit — not two code paths that could
    disagree about who is leaving."""
    other = FakeTeam(9, 'Other')
    congested = FakeTeam(1, 'Congested', wins=3, losses=11)
    _congest(congested, ratings=(92, 88, 84), position=Position.WR)
    market = _market([congested, other], freeAgents=[FakePlayer(99, 74, Position.WR)])

    expiring = sorted((p for p in congested.rosterDict.values()
                       if p is not None and p.termRemaining <= 1),
                      key=lambda p: -p.playerRating)
    assert market.retentionTerm(congested, expiring[0]) > 0      # kept
    assert market.retentionTerm(congested, expiring[1]) > 0      # kept
    assert market.retentionTerm(congested, expiring[2]) == 0.0   # surplus
    print("PASS one rule: the top two carry a re-sign, the third is a rental")


# ------------------------------------------- the core is not a trade asset

def test_a_club_does_not_put_its_franchise_player_on_the_block():
    """⚠️ BEING HIGHLY RATED IS NOT THE SAME AS BEING AVAILABLE (owner: "teams should also
    be identifying star players to build around and not consider every highly rated player
    as a trade asset"). Every value trigger priced a star as an asset with a big number on
    it, so a club's best man went on the block whenever the arithmetic said the return
    cleared — which is how a rebuilder sells the one player its rebuild is for."""
    other = FakeTeam(9, 'Other')
    pool = [FakePlayer(99, 74, Position.WR)]

    club = FakeTeam(1, 'Rebuild', wins=3, losses=11)
    club.rosterDict['wr1'] = FakePlayer(10, 95, Position.WR, termRemaining=1)
    market = _market([club, other], freeAgents=pool, week=20)
    assert market.listingsFor(club) == [], "the franchise player was listed"
    assert id(club.rosterDict['wr1']) in market._coreOf(club)
    print("PASS a club's best player is not an asset")


def test_the_core_must_actually_be_STARS():
    """⚠️ "The best two on a 2-14 club" as a rule would make the worst clubs untouchable
    and stop them trading at all — the opposite of what a rebuild does. It takes the
    game's own bar, 4-star or better."""
    from constants import TRADE_CORE_MIN_RATING
    weak = FakeTeam(1, 'Weak', wins=2, losses=12)
    weak.rosterDict['wr1'] = FakePlayer(10, TRADE_CORE_MIN_RATING - 5,
                                        Position.WR, termRemaining=1)
    market = _market([weak, FakeTeam(9, 'Other')], week=20)
    assert market._coreOf(weak) == set(), "a sub-star was treated as a franchise player"
    assert market.listingsFor(weak), "a weak club's best player should still be an asset"
    print(f"PASS below {TRADE_CORE_MIN_RATING:g} nobody is untouchable")


def test_a_declining_star_is_still_an_asset():
    """⚠️ SELLING HIGH ON A FADING VETERAN IS ONE OF THE FEW GENUINELY SMART THINGS A FRONT
    OFFICE CAN DO. The core is who you build AROUND, and a player on the way down is not
    that however good he still looks."""
    from managers.frontOfficeBrain import ARC_REGRESSING
    club = FakeTeam(1, 'Aging', wins=3, losses=11)
    fading = FakePlayer(10, 95, Position.WR, termRemaining=1)
    club.rosterDict['wr1'] = fading
    market = _market([club, FakeTeam(9, 'Other')], week=20)

    assert id(fading) in market._coreOf(club)          # prime, so untouchable
    market._coreCache.clear()
    market.brain.classifyArc = lambda p: ARC_REGRESSING
    assert market._coreOf(club) == set(), "a declining star was shielded as a cornerstone"
    print("PASS a fading star is a legitimate asset again")


def test_the_locker_room_trigger_still_reaches_the_core():
    """⚠️ EXEMPT FROM THE VALUE TRIGGERS, NOT FROM ALL OF THEM. A franchise player
    poisoning the room is a real decision a club has to make, and shielding him from it
    would make attitude unable to touch the players it matters most for."""
    club = FakeTeam(1, 'Toxic', wins=11, losses=3)
    star = FakePlayer(10, 95, Position.WR, termRemaining=3,
                      attitude=LOCKER_ROOM_ATTITUDE - 15)
    club.rosterDict['wr1'] = star
    market = _market([club, FakeTeam(9, 'Other')], freeAgents=[FakePlayer(99, 74, Position.WR)],
                     week=20)
    assert id(star) in market._coreOf(club)
    assert [l.trigger for l in market.listingsFor(club)] == ['locker_room']
    print("PASS a toxic franchise player is still movable, for that reason alone")


def test_deadline_urgency_raises_the_OFFER_not_just_the_ceiling():
    """⚠️ BOTH HALVES ARE NEEDED AND RAISING ONLY THE CEILING DOES NOTHING. The bundle is
    sized to the seller's bar, so a buyer willing to pay more still offers exactly the
    minimum unless its target rises too — and the sealed round then has every bidder
    offering the same package, which is a tie rather than an auction.

    Asserted behaviourally: a bar the buyer cannot reach when the market opens becomes
    reachable on the final day, because it is now bidding above the minimum."""
    from constants import GM_ACTIVE_WEEK
    seller, buyer = FakeTeam(1, 'Seller', wins=2, losses=12), FakeTeam(2, 'Buyer', wins=13, losses=1)
    teams = [seller, buyer]

    def assets(team, valuingTeam=None, swapPosition=None):
        return [{'kind': 'pick', 'id': 1, 'name': 'a pick', 'detail': {}, 'value': 10.0}]

    reached = {}
    for week in (15, GM_ACTIVE_WEEK):
        market = _market(teams, week=week)
        market._tradeableAssets = assets
        urgency = __import__('trading').deadlineUrgency(week, market.nowWeight(buyer))
        # A bar just out of reach of a single 10.0 piece at the open.
        reached[week] = market._assemble(buyer, seller, 11.0 * 1.0 / max(urgency, 1e-9)
                                         if False else 11.0,
                                         gross=9999.0, displaced=0.0) != []
    assert reached[15] is False, "the fixture's bar was reachable at the open"
    assert reached[GM_ACTIVE_WEEK] is False, \
        "_assemble should not know about urgency — the CALLER scales the bar"

    # And the caller does scale it: the same bar, pre-multiplied, is now cleared.
    market = _market(teams, week=GM_ACTIVE_WEEK)
    market._tradeableAssets = assets
    import inspect
    src = inspect.getsource(TradeMarket.bidFor)
    assert 'bar * urgency' in src and 'gross * urgency' in src, \
        "urgency reaches only one of the two, so it cannot change what is offered"
    print("PASS urgency scales both the offer and the ceiling")


# ---------------------------------- clubs trade for what they NEED

class TwoSided(FakePlayer):
    """A player whose two halves differ, which `playerRating` averages away."""

    def __init__(self, pid, off, dfn, **kw):
        super().__init__(pid, (off + dfn) / 2, **kw)
        self.offensiveRating = off
        self.defensiveRating = dfn


def _league(myOff, myDef, leagueOff=80, leagueDef=80):
    me = FakeTeam(1, 'Me', wins=8, losses=8)
    me.offenseRating, me.defenseRating = myOff, myDef
    rivals = []
    for i in range(2, 6):
        t = FakeTeam(i, f'R{i}', wins=8, losses=8)
        t.offenseRating, t.defenseRating = leagueOff, leagueDef
        rivals.append(t)
    return me, [me] + rivals


def test_a_club_short_of_defense_prefers_the_defensive_player():
    """⚠️ `playerRating` IS `(offensiveRating + defensiveRating) / 2`, so the two halves
    are averaged away before the market sees them and every player is the same KIND of
    asset to every club. A side with weapons and no defense had no reason to prefer a
    defender over an identically-rated attacker."""
    defender = TwoSided(10, off=70, dfn=90)      # playerRating 80
    attacker = TwoSided(11, off=90, dfn=70)      # playerRating 80
    assert defender.playerRating == attacker.playerRating

    needsD, teams = _league(myOff=90, myDef=70)
    market = _market(teams)
    assert market.ratingFor(needsD, defender) > market.ratingFor(needsD, attacker)

    needsO, teams2 = _league(myOff=70, myDef=90)
    market2 = _market(teams2)
    assert market2.ratingFor(needsO, attacker) > market2.ratingFor(needsO, defender)
    print(f"PASS the same 80 is worth {market.ratingFor(needsD, defender):.1f} to a club "
          f"needing defense and {market.ratingFor(needsD, attacker):.1f} needing offense")


def test_a_balanced_club_reads_the_plain_rating():
    """⚠️ NEUTRAL AT ZERO TILT, which is what keeps this a redistribution between clubs
    rather than a thumb on the whole market."""
    balanced, teams = _league(myOff=80, myDef=80)
    market = _market(teams)
    assert market.needTilt(balanced) == 0.0
    for p in (TwoSided(10, 70, 90), TwoSided(11, 90, 70), FakePlayer(12, 80)):
        assert abs(market.ratingFor(balanced, p) - p.playerRating) < 1e-9
    print("PASS a balanced club values every player at his plain rating")


def test_need_is_RELATIVE_to_the_league():
    """⚠️ A club that is simply bad at both has no particular NEED — it should take talent
    wherever it comes, not chase one half of the game.

    ⚠️ AND THE CASE THAT ACTUALLY SEPARATES RELATIVE FROM ABSOLUTE IS A LOPSIDED LEAGUE.
    A club bad at both reads neutral under EITHER formulation, because the two gaps cancel
    — so testing only that proves nothing. When the whole league scores more than it stops,
    a club matching the league exactly has no need at all, while an absolute reading would
    tell every single club it is short of defense.
    """
    bad, teams = _league(myOff=60, myDef=60, leagueOff=80, leagueDef=80)
    assert abs(_market(teams).needTilt(bad)) < 0.01

    # The whole league is offense-heavy; this club is exactly typical.
    typical, teams2 = _league(myOff=90, myDef=70, leagueOff=90, leagueDef=70)
    assert abs(_market(teams2).needTilt(typical)) < 0.01, \
        "a league-average club was told it needs defense because the LEAGUE is lopsided"

    # Genuinely lopsided AGAINST the league.
    lopsided, teams3 = _league(myOff=85, myDef=60, leagueOff=80, leagueDef=80)
    assert _market(teams3).needTilt(lopsided) > 0.2
    print("PASS need is measured against the league, not against a fixed ideal")


def test_a_player_with_no_split_is_unaffected():
    """Nothing to tilt toward, so the rule must be a no-op rather than an error."""
    needsD, teams = _league(myOff=90, myDef=70)
    market = _market(teams)
    plain = FakePlayer(10, 80)
    assert market.ratingFor(needsD, plain) == 80
    print("PASS a player with no offence/defence split reads his plain rating")
