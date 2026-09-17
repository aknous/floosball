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


def test_the_seller_says_it_CHOSE_OTHERS_not_that_a_limit_was_hit():
    """⚠️ "He is past the club's 2-player re-sign limit" DESCRIBES A MECHANISM AND READS AS
    JARGON (owner, 2026-09-16: "what does it mean 'past the 2 player re-sign limit'? is the
    team deciding that they wont resign this player?"). Yes, it is — the club ranked its
    expiring players, can keep two, and chose other men. The sentence has to say that, and
    naming them answers the question it raises."""
    teams = _teams()
    club = _congest(teams[-1], ratings=(88, 84, 80))
    m = _market(teams)
    order = m._resignPriority(club)
    surplus = order[-1]                      # last in line, so genuinely leaving
    why = m.sellerWhy(club, surplus, 'expiring_surplus')

    assert 'not renewing' in why, why
    assert 'leaves for nothing' in why
    assert 'limit' not in why, "the sentence still explains itself by naming the rule"
    for kept in order[:2]:
        assert getattr(kept, 'name', '') in why, f"{kept.name} was kept but not named"
    print(f"PASS  {why}")


def test_the_re_sign_ORDER_has_exactly_one_implementation():
    """⚠️ `_cannotKeep` DECIDES WHO IS LEAVING AND `sellerWhy` NAMES WHO WAS CHOSEN INSTEAD.
    A second sort would let the ledger explain a decision the market did not make — and the
    two would drift silently, since nothing compares them."""
    teams = _teams()
    club = _congest(teams[-1], ratings=(88, 84, 80, 76))
    m = _market(teams)
    order = m._resignPriority(club)
    leaving = m._cannotKeep(club)
    keptIds = {id(p) for p in order[:2]}
    assert not (keptIds & leaving), "a man the club chose to keep is listed as leaving"
    for p in order[2:]:
        assert id(p) in leaving, f"{p.name} is past the cap but not marked as leaving"
    src = inspect.getsource(TradeMarket._cannotKeep)
    assert 'self._resignPriority(team)' in src, "_cannotKeep sorts the list a second time"
    print("PASS one ranking decides it and explains it")


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
    assert 'Paid to drop from' in src
    src2 = inspect.getsource(TradeMarket.bidForPick)
    assert 'Moving up to' in src2, "the buyer does not say it is moving up"

    # ⚠️ AND BOTH DESCRIBE THE PICK THE SAME WAY THE LEDGER DOES. `slot` is the original
    # club's standing TODAY, so a pick two drafts out is "slot 2" for a club that is bad
    # right now while its expected slot is nearer 10 — the reasoning quoted the raw number
    # and the pick line quoted the expectation, so a trade-up read "Moving up to slot 2"
    # above a row saying "~10". One fact, two sources, disagreeing in public.
    # ⚠️ ASSERTED AS THE ABSENCE OF THE RAW SLOT, NOT THE PRESENCE OF THE HELPER. A first
    # version checked `_pickLabel` appeared somewhere in each function — but each mentions a
    # pick twice, so reverting ONE of them back to the raw slot left the assertion happy and
    # the sentence wrong again.
    for fn, body in (('bidForPick', src2), ('pickInquiriesFor', src)):
        prose = [ln for ln in body.splitlines() if 'f"' in ln and 'slot' in ln
                 and '_pickLabel' not in ln and '#' not in ln.split('f"')[0]]
        assert not prose, f"{fn} still quotes a raw slot in prose: {prose}"
    print("PASS a trade-up explains the drop and the jump")


def test_a_position_the_club_is_GOOD_AT_is_not_a_hole():
    """⚠️ WITHOUT THIS EVERY CLUB HAS THREE HOLES. `_positionalGaps` ranks by deficit but
    nothing required the deficit to be POSITIVE, so a club above the league mean everywhere
    still had a "weakest" position and went shopping there.

    Reported from the ledger: Broads held an **85** tight end, were told TE was their
    "number 3 hole", and traded a pick for a **76**. The reasoning and the purchase were
    both wrong, from this one missing check."""
    teams = _teams()
    strong = teams[0]
    # above the league mean at every position, by a lot
    for slot, pos in (('qb', Position.QB), ('rb', Position.RB), ('wr1', Position.WR),
                      ('wr2', Position.WR), ('te', Position.TE), ('k', Position.K)):
        strong.rosterDict[slot] = FakePlayer(800 + hash(slot) % 23, 92, pos, termRemaining=3)
    m = _market(teams)
    assert m.topNeeds(strong) == set(), \
        f"a club strong everywhere still has holes: {m.topNeeds(strong)}"

    # ...and one genuine weakness is still found
    strong.rosterDict['te'] = FakePlayer(801, 55, Position.TE, termRemaining=3)
    m._needsCache.clear(); m._posMeanCache.clear()
    assert Position.TE.value in m.topNeeds(strong), "a real hole went unnoticed"
    print("PASS a club only shops where it is actually behind the league")


def test_the_CUT_FEE_is_charged_against_the_buyer():
    """⚠️ `fee` WAS COMPUTED, DESCRIBED IN A COMMENT AS "part of the price", AND NEVER
    SUBTRACTED. Reported from the ledger: Broads gave up a pick, paid **1,800F**, and
    downgraded from an 85 tight end to a 76 — a loss on every axis at once."""
    import inspect as _i
    src = _i.getsource(TradeMarket.bidFor)
    assert 'gross -= feeCost' in src, "the cut fee still does not reach the decision"
    assert src.index('feeCost') < src.index('net = gross - displaced'), \
        "the fee is subtracted after the comparison that should feel it"
    print("PASS the fee is paid before the club decides it is worth it")


def test_the_club_checks_whether_the_ROSTER_actually_improves():
    """Owner, 2026-09-16: "the team has to look at what their team looks like with the
    player they might get back and see if that new player actually makes their team better."

    ⚠️ A BACKSTOP, NOT THE VALUATION. `bidFor` already prices the upgrade, but that runs
    through believed ratings, position weights, retention terms and a cut fee — five places
    for a yes to come out of a roster that plainly gets worse. It did: Broads gave up a
    pick, paid 1,800F, and went from an 85 tight end to a 76."""
    teams = _teams()
    buyer = teams[0]
    good = FakePlayer(810, 85, Position.TE, termRemaining=2)
    buyer.rosterDict['te'] = good
    m = _market(teams)

    worse = FakePlayer(811, 76, Position.TE, termRemaining=1)
    assert not m.rosterWouldImprove(buyer, worse, good), \
        "a 76 on one year replaced an 85 on two"

    better = FakePlayer(812, 90, Position.TE, termRemaining=1)
    assert m.rosterWouldImprove(buyer, better, good)
    print("PASS a club will not make itself worse on every axis at once")


def test_the_backstop_does_NOT_block_a_TIME_trade():
    """⚠️ TAKING A SLIGHTLY WORSE PLAYER FOR MORE SEASONS IS THE PLAN'S HORIZON TRADE and a
    good deal — measured on ratings alone it reads as churn. A blunt "rating must not fall"
    would delete it, so a downgrade is refused only when the club gains NO control by it."""
    teams = _teams()
    buyer = teams[0]
    incumbent = FakePlayer(813, 82, Position.TE, termRemaining=1)
    buyer.rosterDict['te'] = incumbent
    m = _market(teams)
    younger = FakePlayer(814, 78, Position.TE, termRemaining=4)
    assert m.rosterWouldImprove(buyer, younger, incumbent), \
        "a four-year 78 for a walk-year 82 was refused — that is the horizon trade"
    print("PASS a worse player with real term is still a trade worth making")


def test_ONE_finder_decides_who_is_displaced():
    """⚠️ Two searches for "who gets displaced" would let the price and the sanity check
    disagree about who is leaving."""
    import inspect as _i
    src = _i.getsource(TradeMarket._displacedBy)
    assert 'self._weakestAt(' in src or '_weakestAt' in src, \
        "_displacedBy finds the displaced player a second way"
    print("PASS the price and the check agree on who goes")


def test_the_buyer_does_not_SEND_a_better_player_at_the_position_it_is_fixing():
    """⚠️ THE MAN ACTUALLY LEAVING IS NOT ALWAYS THE WEAKEST ONE, AND THE PRICE ASSUMED HE
    WAS. `_displacedBy` runs BEFORE the bundle exists and takes the club's weakest at the
    position — right when the slot is opened by a cut, wrong when the bundle pays with a
    same-position starter, because `_assemble` picks whatever is cheapest on the BUYER's
    scale and a high-rated walk-year player is cheap.

    Measured: **15 trades in 206** where the buyer shipped out a same-position player rated
    HIGHER than the one arriving — "got 74 QB term 1 / sent 79 QB term 1".

    ⚠️ It has to be re-checked AFTER assembly: which man goes is a property of the bundle,
    and the bundle is sized using `displaced`. Checking early is what produced the wrong
    answer to begin with."""
    import inspect as _i
    src = _i.getsource(TradeMarket.bidFor)
    assert 'swap = _swapPieceOf(pieces, buyer, player)' in src, \
        "nothing re-checks who the bundle actually sends"
    assert src.index('_assemble') < src.index('_swapPieceOf(pieces'), \
        "the check runs before the bundle exists, which is the bug it exists to fix"

    teams = _teams()
    buyer = teams[0]
    strong = FakePlayer(820, 79, Position.QB, termRemaining=1)
    buyer.rosterDict['qb'] = strong
    m = _market(teams)
    weaker = FakePlayer(821, 74, Position.QB, termRemaining=1)
    assert not m.rosterWouldImprove(buyer, weaker, strong), \
        "sending a 79 to receive a 74 counted as an improvement"
    print("PASS a club will not pay for an upgrade with a better player at that position")


def test_theRosterBackstopIsNotFooledByTheNeedTilt():
    """⚠️ A BACKSTOP THAT SHARES THE MODEL'S BIAS CANNOT CATCH THE MODEL'S ERROR.

    `rosterWouldImprove` asked its question through `ratingFor`, which adds
    `needTilt x (defensive - offensive) / 2` — so for a club short of defense a lopsided
    70 reads as 80 and an offense-heavy 79 reads as 68, and the check waved the downgrade
    through. Measured over 14 seasons that let 12 trades cut a higher-rated man than the
    one bought, 11 at the SAME position and SAME contract term.

    Bite check: with `ratingFor` in the comparison this returns True.
    """
    teams = _teams()
    market = _market(teams)
    market.needTilt = lambda team: 1.0          # a club that badly wants defense

    incoming = FakePlayer(901, 70, Position.WR, termRemaining=1)
    incoming.offensiveRating, incoming.defensiveRating = 60, 80   # tilts UP to 80
    held = FakePlayer(902, 79, Position.WR, termRemaining=1)
    held.offensiveRating, held.defensiveRating = 90, 68           # tilts DOWN to 68

    buyer = teams[0]
    assert market.ratingFor(buyer, incoming) > market.ratingFor(buyer, held), \
        'fixture must actually invert under the tilt, or this proves nothing'

    assert market.rosterWouldImprove(buyer, incoming, held) is False, \
        'cutting a 79 to install a 70 on the same term is worse on every axis'


def test_theBackstopStillAllowsAHorizonTrade():
    """The rule is worse on the field AND no control gained. Gaining control still passes,
    which is what stops the blunt reading killing the plan's horizon trade."""
    teams = _teams()
    market = _market(teams)
    market.needTilt = lambda team: 0.0
    incoming = FakePlayer(903, 74, Position.WR, termRemaining=3)
    incoming.offensiveRating = incoming.defensiveRating = 74
    held = FakePlayer(904, 78, Position.WR, termRemaining=1)
    held.offensiveRating = held.defensiveRating = 78
    assert market.rosterWouldImprove(teams[0], incoming, held) is True


def test_theBackstopWillNotCountAProjectedResignAsControlGained():
    """⚠️ PROJECT ONE SIDE AND NOT THE OTHER AND EVERY COMPARISON TILTS TOWARD THE DEAL.

    `bidFor` passes `buyerTerm` = actual term PLUS `retentionTerm` — what the buyer expects
    if it re-signs him. That was compared against the displaced man's ACTUAL term, so a
    walk-year-for-walk-year swap read as control gained and the downgrade was allowed. The
    incumbent could be re-signed just as easily. Measured, this let nine downgrades through
    even after the backstop stopped using the need-tilted rating, the worst cutting an 84
    back to install a 78.

    Bite check: passing a projected `incomingTerm` of 3 here returned True.
    """
    teams = _teams()
    buyer = teams[0]
    incumbent = FakePlayer(830, 84, Position.RB, termRemaining=1)
    buyer.rosterDict['rb'] = incumbent
    m = _market(teams)
    m.needTilt = lambda team: 0.0

    worse = FakePlayer(831, 78, Position.RB, termRemaining=1)
    assert m.rosterWouldImprove(buyer, worse, incumbent) is False, \
        'a 78 on a walk year replaced an 84 on a walk year — no control was gained'

    # and the signature gives a caller no way to supply a term at all
    import inspect
    params = list(inspect.signature(m.rosterWouldImprove).parameters)
    assert 'incomingTerm' not in params, \
        'the term must be read off the players, or a caller can pass the wrong currency'
