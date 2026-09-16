"""Trading UP the draft.

⚠️ A PICK COULD ONLY EVER BE CHANGE, NEVER THE THING BEING BOUGHT. A `Listing` was always a
player, so there was no pick-for-pick trade in the system at all. Measured over 8 seasons
before this: of 86 picks that changed hands, exactly ONE was a top-8 and 66% sat in the
17-24 band — because picks flow FROM buyers, buyers are contenders (median win% .641), and
a contender's own pick lands late. The picks worth having belonged to clubs that never paid
with them.

Owner, 2026-09-16: "offseason is buyers looking for ways to upgrade, which can include
jumping up in the draft ... a pick in the 1-3 zone would be considered a centerpiece just
because of what kind of player comes with a pick that high."
"""

import os
import tempfile

os.environ['DATABASE_DIR'] = tempfile.mkdtemp(prefix='floos_ps_')

import inspect                                                        # noqa: E402
import constants                                                      # noqa: E402
import trading                                                        # noqa: E402
from managers import tradeManager                                     # noqa: E402
from managers.tradeManager import TradeMarket, PickListing            # noqa: E402
from database.connection import init_db, get_session                  # noqa: E402
from database.models import DraftPick                                 # noqa: E402
from floosball_player import Position                                 # noqa: E402
from test_trade_market import (FakeTeam, FakePlayer, FakeTeamManager,  # noqa: E402
                               FakePlayerManager, StubBrain)

init_db()
SEASON = 70


def _league(n=32):
    teams = []
    for i in range(n):
        wins = 24 - (i * 16 // n)
        t = FakeTeam(i + 1, f"C{i + 1}", wins=wins, losses=28 - wins)
        for slot, pos in (('qb', Position.QB), ('rb', Position.RB), ('wr1', Position.WR),
                          ('wr2', Position.WR), ('te', Position.TE), ('k', Position.K)):
            t.rosterDict[slot] = FakePlayer(i * 20 + hash(slot) % 11, 78, pos,
                                            termRemaining=3)
        t.prospects = [FakePlayer(900 + i, 74, Position.WR, termRemaining=3,
                                  isProspect=True)]
        teams.append(t)
    session = get_session()
    try:
        for yr in (SEASON, SEASON + 1, SEASON + 2):
            session.query(DraftPick).filter_by(season=yr).delete()
            for t in teams:
                session.add(DraftPick(season=yr, round_number=1,
                                      original_team_id=t.id, current_owner_id=t.id))
        session.commit()
    finally:
        session.close()
    return teams


def _market(teams, week=None):
    return TradeMarket(FakePlayerManager([]), FakeTeamManager(teams), StubBrain(),
                       SEASON, week)


def test_trading_up_is_OFFSEASON_only():
    """A slot is only known once the season has finished, and this is a buyer shopping for
    an upgrade."""
    teams = _league()
    assert _market(teams, week=18).pickInquiriesFor(teams[16]) == []
    assert _market(teams, week=None).pickInquiriesFor(teams[16]), \
        "no club would move up even in the offseason"
    print("PASS you move up between seasons, not during one")


def test_a_club_with_no_pick_cannot_move_UP():
    """⚠️ IT HAS NOTHING TO MOVE UP FROM. Buying a slot outright is a different trade and
    one this market has no seller for."""
    teams = _league()
    session = get_session()
    try:
        for r in session.query(DraftPick).filter_by(current_owner_id=teams[16].id).all():
            r.current_owner_id = teams[0].id
        session.commit()
    finally:
        session.close()
    assert _market(teams).pickInquiriesFor(teams[16]) == []
    print("PASS a club with no pick has nothing to trade up from")


def test_the_price_is_THE_DROP_not_the_slot():
    """⚠️ PRICING THE SLOT ABSOLUTELY MAKES THE TRADE IMPOSSIBLE AND DESCRIBES THE WRONG
    DEAL. A club moving up swaps its own pick in, so the seller does not lose slot 1 — it
    loses the DIFFERENCE between slot 1 and slot N. Measured on the absolute reading: a
    rebuilder quoted **107** for slot 2 against 31 for the slot-10 pick coming back, so
    nothing could ever clear."""
    teams = _league()
    m = _market(teams)
    holder = teams[-1]
    top = m.picksOwnedBy(holder)[0]
    # ⚠️ A MID-TABLE PICK, deliberately. The best club's pick is slot ~32 and worth
    # essentially nothing, so the "drop" from slot 1 to it IS the whole slot and the test
    # cannot tell the two models apart — which is how the first version of it failed.
    swapFor = m.picksOwnedBy(teams[16])[0]

    absolute, _ = m._pricePick(holder, top)
    drop, _ = m._pricePick(holder, top, swapFor=swapFor)
    assert 0 < drop < absolute, (drop, absolute)
    print(f"PASS the quote is {drop:.1f} for the drop, not {absolute:.1f} for the slot")


def test_a_top_pick_carries_a_premium_that_STAYS_UNDER_the_buyers_ceiling():
    """⚠️ THE SAME ARITHMETIC THAT DEFEATED THE BLOCKBUSTER TWICE, FOR THE THIRD TIME. At a
    1.30 top premium the quote came to 1.35 x 1.30 = 1.755 against a buyer ceiling of 1.70,
    so the only picks the feature exists for were the ones it could never move. The
    relationship is pinned here rather than the number."""
    quote = constants.TRADE_INQUIRY_PREMIUM * constants.TRADE_PICK_PREMIUM_TOP
    assert constants.TRADE_PICK_PREMIUM_TOP > 1.0, "a top pick is not a centerpiece"
    assert quote < constants.TRADE_HUMP_APPETITE, (
        f"a top-3 quote of x{quote:.3f} is above the buyer's x"
        f"{constants.TRADE_HUMP_APPETITE} ceiling — it can never clear")
    print(f"PASS a top-3 quote of x{quote:.3f} sits under the x"
          f"{constants.TRADE_HUMP_APPETITE} ceiling")


def test_the_swap_pick_goes_over_and_is_not_offered_TWICE():
    """⚠️ `_assemble` TAKES THE CHEAPEST ASSETS THAT CLEAR, so left to itself it would
    happily pay with prospects and KEEP the pick — which is not a move up, it is buying a
    second pick. The swap rides separately and is excluded from the assembled pool."""
    teams = _league()
    m = _market(teams)
    buyer = teams[16]
    listings = m.pickInquiriesFor(buyer)
    assert listings, "the fixture produced no jump worth making"
    listing = listings[0]
    bid = m.bidForPick(listing, buyer)
    assert bid is not None, "the fixture could not cover the drop"

    ids = [(p['kind'], p['id']) for p in bid.pieces]
    assert ('pick', listing.swapFor['id']) in ids, "the buyer kept its own pick"
    assert ids.count(('pick', listing.swapFor['id'])) == 1, "the swap pick was offered twice"

    # ⚠️ THE EXCLUSION IS DEFENSIVE TODAY, NOT LOAD-BEARING, AND SAYING SO IS THE POINT.
    # `swapFor` is the buyer's MOST valuable pick and `_assemble` accumulates cheapest-first,
    # so the bar clears before it would ever be reached — removing `excludeIds` changes
    # nothing right now. It matters the moment the choice of swap pick stops being "the
    # best one", so it is asserted at the call site rather than claimed as behaviour.
    assert "excludeIds={('pick', swapFor['id'])}" in inspect.getsource(
        TradeMarket.bidForPick), "the swap pick is no longer excluded from the pool"
    print(f"PASS the swap pick goes over exactly once, in a bundle of {len(bid.pieces)}")


def test_the_manifest_carries_every_key_the_PERSISTER_reads():
    """⚠️ A MISSING KEY FAILS INSIDE `_persistTrade`'S OWN try/except, which logs a warning
    and returns 0 — so the pick has already moved and no `trades` row records it. Shipped
    twice in one sitting: first `_persistTrade(seasonManager, manifest)` against a
    one-argument function, then a manifest with no `reserve`. Both were announced in the log
    the whole time while a grep for the SUCCESS line reported zero."""
    src = inspect.getsource(tradeManager._persistTrade)
    needed = {k for k in ('season', 'week', 'phase', 'teamAId', 'teamBId',
                          'aGave', 'bGave', 'price', 'reserve')
              if f"manifest['{k}']" in src}
    built = inspect.getsource(tradeManager.settlePickTrade)
    missing = [k for k in needed if f"'{k}'" not in built]
    assert not missing, f"the pick manifest omits {missing}, which _persistTrade reads"
    assert 'reserve' in needed, "the guard no longer covers the key that actually broke"
    print(f"PASS the pick manifest carries all {len(needed)} keys the persister reads")


def test_assembly_DROPS_a_piece_the_bar_no_longer_needs():
    """⚠️ CHEAPEST-FIRST IS GREEDY AND THE ASSETS ARE LUMPY, so the last piece added can
    overshoot badly and carry earlier pieces that are now redundant — and the buyer is then
    refused for a package it never had to offer. Measured on a trade-up: 7.5 + 10.3 + 27.0 =
    44.8 to clear a bar of 35.3, which exceeded the buyer's own ceiling of 44.4 by a hair;
    dropping the redundant 7.5 leaves 37.3, still clearing, comfortably under.

    This one helps every trade in the market, not only a trade-up."""
    src = inspect.getsource(TradeMarket._assemble)
    assert 'DROP WHAT THE BAR NO LONGER NEEDS' in src
    teams = _league()
    m = _market(teams)
    buyer = teams[16]
    listing = m.pickInquiriesFor(buyer)[0]
    bid = m.bidForPick(listing, buyer)
    extras = [p for p in bid.pieces if p['id'] != listing.swapFor['id']]
    total = sum(p['value'] for p in extras)
    for p in extras:
        assert total - p['value'] < listing.floor, \
            f"the bundle still carries {p['name']}, which the bar does not need"
    print(f"PASS every one of the {len(extras)} extras is load-bearing")
