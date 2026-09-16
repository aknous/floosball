"""Both clubs say why, in their own terms.

⚠️ THE TRIGGER IS THE SELLER'S REASON AND WAS ALL THE LEDGER EVER CARRIED, so a trade read
as half a conversation: a club moves a man for a locker-room problem and nothing says why
anybody wanted him. Owner, 2026-09-16: "what drove them to make this trade? need to upgrade
at a certain position or on defense, need to make way for a prospect, needing to load up on
picks."
"""

import os
import tempfile

os.environ['DATABASE_DIR'] = tempfile.mkdtemp(prefix='floos_tr_')

import inspect                                                        # noqa: E402
from managers import tradeManager                                     # noqa: E402
from managers.tradeManager import TradeMarket, Listing                 # noqa: E402
from floosball_player import Position                                  # noqa: E402
from test_trade_market import (FakeTeam, FakePlayer, FakeTeamManager,   # noqa: E402
                               FakePlayerManager, StubBrain, _congest)


def _teams(n=8):
    out = []
    for i in range(n):
        wins = 20 if i < n // 2 else 8
        t = FakeTeam(i + 1, f"C{i+1}", wins=wins, losses=28 - wins)
        for slot, pos in (('qb', Position.QB), ('rb', Position.RB), ('wr1', Position.WR),
                          ('wr2', Position.WR), ('te', Position.TE), ('k', Position.K)):
            t.rosterDict[slot] = FakePlayer(i * 30 + hash(slot) % 17, 78, pos,
                                            termRemaining=3)
        out.append(t)
    return out


def _market(teams, week=18):
    return TradeMarket(FakePlayerManager([]), FakeTeamManager(teams), StubBrain(), 5, week)


def test_the_seller_names_the_PROSPECT_it_is_unblocking():
    """⚠️ "Blocked" IS A CATEGORY; THE REASON IS WHO IS BLOCKED. A reader came for the
    second."""
    teams = _teams()
    club = teams[-1]
    blocked = FakePlayer(701, 74, Position.WR, termRemaining=3, isProspect=True,
                         prospectSeasons=2)
    blocked.name = 'Ready Kid'
    club.prospects = [blocked]
    m = _market(teams)
    why = m.sellerWhy(club, club.rosterDict['wr1'], 'blocked_prospect')
    assert 'Ready Kid' in why, why
    assert 'WR' in why
    print(f"PASS  {why}")


def test_the_seller_names_the_ATTITUDE_dragging_the_room():
    teams = _teams()
    club = teams[-1]
    sour = FakePlayer(702, 80, Position.TE, termRemaining=3, attitude=41)
    sour.name = 'Sour Man'
    club.rosterDict['te'] = sour
    why = _market(teams).sellerWhy(club, sour, 'locker_room')
    assert 'Sour Man' in why and '41' in why, why
    print(f"PASS  {why}")


def test_the_seller_explains_the_RE_SIGN_CAP_not_just_the_word_surplus():
    teams = _teams()
    club = _congest(teams[-1])
    player = club.rosterDict['wr1']
    why = _market(teams).sellerWhy(club, player, 'expiring_surplus')
    assert 'walks for nothing' in why, why
    assert getattr(player, 'name', '') in why
    print(f"PASS  {why}")


def test_the_BUYER_says_which_hole_it_is_filling():
    """⚠️ THE BUYER'S SIDE WAS NEVER RECORDED AT ALL."""
    teams = _teams()
    buyer = teams[0]
    buyer.rosterDict['qb'] = FakePlayer(703, 52, Position.QB, termRemaining=3)
    seller = teams[-1]
    target = FakePlayer(704, 90, Position.QB, termRemaining=3)
    seller.rosterDict['qb'] = target
    m = _market(teams)
    why = m.buyerWhy(buyer, Listing(seller, target, 'expiring_surplus', 1.0, 1.0))
    assert 'QB' in why and 'hole' in why, why
    print(f"PASS  {why}")


def test_the_BUYER_says_when_it_is_short_on_DEFENSE():
    """Owner asked for exactly this case: "need to upgrade ... on defense"."""
    teams = _teams()
    for t in teams:
        t.offenseRating, t.defenseRating = 85.0, 85.0
    buyer = teams[0]
    buyer.offenseRating, buyer.defenseRating = 92.0, 68.0      # lopsided on purpose
    seller = teams[-1]
    target = FakePlayer(705, 88, Position.WR, termRemaining=3)
    seller.rosterDict['wr1'] = target
    m = _market(teams)
    why = m.buyerWhy(buyer, Listing(seller, target, 'expiring_surplus', 1.0, 1.0))
    assert 'defense' in why, why
    print(f"PASS  {why}")


def test_the_buyer_does_NOT_name_who_gets_cut():
    """⚠️ IT IS WRITTEN WHEN THE BID IS MADE AND SETTLEMENT MAY TAKE ANOTHER PATH — a
    same-position swap needs no cut at all. Naming it here would put a second, GUESSING
    source of truth beside the aftermath strip, which records what actually happened. Two
    sources for one fact is the failure this codebase keeps repeating."""
    src = inspect.getsource(TradeMarket.buyerWhy)
    assert 'cut to make room' not in src, \
        "the buyer's note predicts a cut the aftermath strip reports for real"
    assert 'THE CUT IS DELIBERATELY NOT NAMED HERE' in src
    print("PASS the cut is reported once, by the side that observed it")


def test_both_reasons_ride_the_MANIFEST_not_just_the_harness():
    """⚠️ THE LEDGER IS A MEASUREMENT TOOL AND THE MANIFEST IS THE PRODUCT. Recording the
    reasoning only in `trade_shape_check` would leave the league news, the recap and the
    persisted trade with nothing to say."""
    for fn in (tradeManager.settleTrade, tradeManager.settlePickTrade):
        src = inspect.getsource(fn)
        assert "'sellerWhy'" in src and "'buyerWhy'" in src, fn.__name__
    print("PASS both settlement paths carry both reasons")


def test_a_TRADE_UP_explains_both_sides_of_the_slot():
    """⚠️ MATCHED ON A FRAGMENT THAT IS CONTIGUOUS IN THE SOURCE. The sentence is split
    across two string literals, so asserting on the rendered wording fails against source
    that is perfectly correct — the first version of this test did exactly that."""
    src = inspect.getsource(TradeMarket.pickInquiriesFor)
    assert 'does not need the very best' in src, "the seller does not say why it drops"
    assert 'Paid to drop from slot' in src
    src2 = inspect.getsource(TradeMarket.bidForPick)
    assert 'Moving up to slot' in src2, "the buyer does not say it is moving up"
    print("PASS a trade-up explains the drop and the jump")
