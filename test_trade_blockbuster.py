"""The blockbuster — a buyer-initiated approach, in the offseason only.

⚠️ EVERY OTHER TRIGGER IS SELLER-INITIATED, which left a star under contract unreachable
from BOTH ends: his club had no reason to post him, and no buyer could ask. Measured over
six seasons before this existed: all 44 in-season buyers were already contenders (win%
.611 to .867, median .733), 37 of their 44 acquisitions had exactly one season left, and
not one club below the playoff line bought anything mid-season.

Owner direction, 2026-09-15: "it makes sense that these trades would only happen in the
offseason. but its definitely buyer initiated. a team would 'kick the tires' on players
theyre interested in."
"""

import constants
from managers import tradeManager
from floosball_player import Position
from test_trade_market import (FakePlayer, FakeTeam, FakeTeamManager,      # noqa: F401
                               FakePlayerManager, StubBrain, _market)


def _league(n=8):
    """Half qualify at 15-13, half miss at 14-14 — so the non-qualifiers are ONE GAME out.

    ⚠️ The gap to the cut is what `isOverTheHump` tests, and `TRADE_HUMP_BAND` is 0.09. A
    fixture with qualifiers at 20-8 puts every other club 0.286 adrift and the gate
    correctly refuses all of them, which reads as the feature being broken.
    """
    teams = []
    for i in range(n):
        made = i < n // 2
        wins = 15 if made else 14
        t = FakeTeam(i + 1, f"Club{i + 1}", wins=wins, losses=28 - wins)
        t.seasonTeamStats['madePlayoffs'] = made
        teams.append(t)
    return teams


def _fill(team, ratings):
    """ratings: {slot: (rating, position)}"""
    for slot, (rating, pos) in ratings.items():
        team.rosterDict[slot] = FakePlayer(team.id * 100 + hash(slot) % 50, rating, pos,
                                           termRemaining=3, name=f"{team.name}-{slot}")
    return team


STARTERS = {'qb': (80, Position.QB), 'rb': (80, Position.RB),
            'wr1': (80, Position.WR), 'wr2': (80, Position.WR),
            'te': (80, Position.TE), 'k': (80, Position.K)}


# -------------------------------------------------- 1. when it may happen

def test_no_inquiry_during_the_season():
    """⚠️ OFFSEASON ONLY (owner). In-season the market stays contract congestion — a
    contender buying the present from clubs that cannot keep it."""
    teams = _league()
    for t in teams:
        _fill(t, STARTERS)
    buyer = teams[-1]
    buyer.rosterDict['qb'] = FakePlayer(777, 60, Position.QB, termRemaining=3)
    teams[0].rosterDict['qb'] = FakePlayer(778, 95, Position.QB, termRemaining=3)

    inSeason = _market(teams, week=20)
    offseason = _market(teams, week=None)
    assert inSeason.inquiriesFor(buyer) == [], "a blockbuster fired during the season"
    assert offseason.inquiriesFor(buyer), "the offseason produced no inquiry at all"
    print("PASS a club kicks tires between seasons, never during one")


def test_a_qualifier_does_not_need_a_blockbuster():
    teams = _league()
    for t in teams:
        _fill(t, STARTERS)
    made = teams[0]
    made.rosterDict['qb'] = FakePlayer(779, 60, Position.QB, termRemaining=3)
    teams[1].rosterDict['qb'] = FakePlayer(780, 95, Position.QB, termRemaining=3)
    market = _market(teams, week=None)
    assert market.isOverTheHump(made) is False
    assert market.inquiriesFor(made) == []
    print("PASS a club that made the playoffs does not mortgage anything")


def test_a_club_far_adrift_does_not_buy():
    """⚠️ MEASURED AT `TRADE_HUMP_BAND` 0.18 THE BUYERS WERE 9-19 AND 10-18 CLUBS. With 16
    of 32 qualifying the cut sits near .500, and five games is 0.179 of win% — so the whole
    band was spent on teams nobody would call middling, and every blockbuster it produced
    was bought by a club five games adrift. That is a rebuild, not a hump."""
    teams = _league()
    for t in teams:
        _fill(t, STARTERS)
    adrift = teams[-1]
    adrift.seasonTeamStats.update({'wins': 6, 'losses': 22})
    adrift.rosterDict['qb'] = FakePlayer(781, 60, Position.QB, termRemaining=3)
    teams[0].rosterDict['qb'] = FakePlayer(782, 95, Position.QB, termRemaining=3)
    market = _market(teams, week=None)
    assert market.isOverTheHump(adrift) is False, \
        "a 6-22 club was treated as one player short of the playoffs"
    print("PASS a club five games out is rebuilding, not pushing")


# -------------------------------------------------- 2. what it shops for

def test_the_hole_is_measured_against_the_LEAGUE_not_by_position_value():
    """⚠️ RANKING SLOTS BY `rating x positionWeight` ALWAYS PICKS THE KICKER, because the
    weights run QB 1.00 to K 0.35 — a 90 kicker scores 31.5 against a 70 quarterback's
    70.0. Measured with that sort, all 264 calls across six seasons were about kickers,
    exactly one bundle ever cleared, and the feature read as a pricing problem when it was
    a targeting one. A hole is a deficit against what the rest of the league HAS.
    """
    teams = _league()
    for t in teams:
        _fill(t, STARTERS)
    buyer = teams[-1]
    # An excellent kicker and a dreadful quarterback. The QB is the hole.
    buyer.rosterDict['k'] = FakePlayer(783, 95, Position.K, termRemaining=3, name='Great K')
    buyer.rosterDict['qb'] = FakePlayer(784, 58, Position.QB, termRemaining=3, name='Poor QB')
    market = _market(teams, week=None)
    worst = market._positionalGaps(buyer)[0]
    assert worst[0] == 'qb', f"went shopping at {worst[0]} with a 58 at quarterback"
    print("PASS the club shops where it trails the league, not where value is cheapest")


def test_nobody_is_called_without_a_real_upgrade():
    teams = _league()
    for t in teams:
        _fill(t, STARTERS)          # every club identical
    buyer = teams[-1]
    market = _market(teams, week=None)
    assert market.inquiriesFor(buyer) == [], \
        "a club phoned around about players no better than the ones it has"
    print("PASS no call without a gap worth filling")


# -------------------------------------------------- 3. what it costs

def test_an_unsolicited_approach_costs_more_than_a_listing():
    """⚠️ AND THE FLOOR HAS TO RISE WITH THE ASK. `settle` clears at the FLOOR, so a
    premium applied to the ask alone is a number nobody ever pays."""
    teams = _league()
    for t in teams:
        _fill(t, STARTERS)
    holder = teams[0]
    target = FakePlayer(785, 88, Position.QB, termRemaining=3)
    holder.rosterDict['qb'] = target
    market = _market(teams, week=None)

    listAsk, listFloor = market._priceListing(holder, target)
    inqAsk, inqFloor = market._priceInquiry(holder, target)
    assert inqAsk > listAsk, (inqAsk, listAsk)
    assert inqFloor > listFloor, \
        f"the ask carried the premium and the floor did not ({inqFloor} vs {listFloor})"
    print(f"PASS an unsolicited call costs more on both ends "
          f"(ask {listAsk:.1f} -> {inqAsk:.1f}, floor {listFloor:.1f} -> {inqFloor:.1f})")


def test_a_core_player_costs_more_than_an_ordinary_star():
    """⚠️ A CORE PLAYER CAN BE PRISED AWAY, AND HAS TO BE, OR THERE IS NO BLOCKBUSTER. The
    core rule stops a club SHOPPING its franchise player; it was never meant to make him
    non-existent to the rest of the league, and the players worth a blockbuster are exactly
    the ones it covers."""
    # ⚠️ THE SAME PLAYER IS PRICED TWICE, and only the roster around him changes. Pricing
    # two DIFFERENT players and comparing invites the rating, the position weight and the
    # term into a test that is about none of them.
    def priceHim(teammates):
        teams = _league()
        for t in teams:
            _fill(t, STARTERS)
        holder = teams[0]
        him = FakePlayer(786, 90, Position.TE, termRemaining=3)
        holder.rosterDict['te'] = him
        for slot, rating, pos in teammates:
            holder.rosterDict[slot] = FakePlayer(800 + rating, rating, pos, termRemaining=3)
        market = _market(teams, week=None)
        return market._priceInquiry(holder, him)[0], id(him) in market._coreOf(holder)

    asCore, wasCore = priceHim([('qb', 70, Position.QB), ('rb', 70, Position.RB)])
    asPlain, wasPlain = priceHim([('qb', 97, Position.QB), ('rb', 96, Position.RB)])
    assert wasCore, "he was not the franchise on a roster of 70s"
    assert not wasPlain, "he was still core behind a 97 and a 96"
    assert asCore > asPlain * 1.1, (asCore, asPlain)
    print(f"PASS the same 90 costs {asCore:.1f} as the franchise and {asPlain:.1f} "
          f"as the third-best man on the roster")


def test_without_the_hump_appetite_no_inquiry_can_EVER_clear():
    """⚠️ THE ARITHMETIC THAT DEFEATED TWO EARLIER ATTEMPTS AT THIS FEATURE.

    `bidFor` refuses once the player is worth less to the buyer than the seller's bar, and
    the buyer's worth is his LINEAR value — so the buyer's ceiling is exactly 1.0x while
    the holder is quoting `TRADE_INQUIRY_PREMIUM`. The two ranges do not overlap at any
    piece cap and at any premium above 1.0. Retargeting the hole and raising the bundle
    cap each moved the measured rate between 0 and 1 trade in six seasons, because neither
    touched this. The overpay belongs on the BUYER — a club on the cusp values the player
    above his parts because the win converts a near-miss into a berth.
    """
    assert constants.TRADE_HUMP_APPETITE > constants.TRADE_INQUIRY_PREMIUM, (
        "the buyer's ceiling sits below the seller's quote, so no inquiry can clear")
    print(f"PASS appetite {constants.TRADE_HUMP_APPETITE} clears the "
          f"{constants.TRADE_INQUIRY_PREMIUM} quote a holder puts on an unsolicited call")


# -------------------------------------------------- 4. it is not an auction

def test_an_inquiry_is_a_private_approach_not_an_auction():
    """⚠️ ONLY THE CALLER BIDS. A club posting a player wants the best offer in the league,
    so `counterpartiesFor` canvasses several — but an inquiry is one club phoning another
    about a man nobody put on the block. Canvassing here would turn a private approach into
    an auction the holder never asked for, and could hand the player to a third club that
    never went looking for him."""
    import inspect
    src = inspect.getsource(tradeManager.runWeeklyPass)
    head, _, tail = src.partition('for inquiry in market.inquiriesFor(buyer)')
    assert tail, "the inquiry pass is gone from runWeeklyPass"
    assert 'counterpartiesFor' not in tail, \
        "the inquiry pass canvasses other clubs — it is an auction, not a phone call"
    assert 'counterpartiesFor' in head, "the listing pass stopped canvassing"
    print("PASS an inquiry is settled between the two clubs on the call")
