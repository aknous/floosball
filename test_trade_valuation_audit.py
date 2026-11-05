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


# ------------------------------------------------------------ 7. the pick cupboard

def _cupboard(picksByTeam, window=(SEASON + 1, SEASON + 2), week=None, teams=None):
    teams = teams or [FakeTeam(1, 'Short', 6, 22), FakeTeam(2, 'Stocked', 20, 8)]
    m = TradeMarket(MarketPlayerManager([]), FakeTeamManager(teams), StubBrain(), SEASON, week)
    m._draftWindow = list(window)
    m._windowHasPicks = True
    m.picksOwnedBy = lambda team: [dict(p) for p in picksByTeam.get(team.id, [])]
    return m, teams


def _pick(pid, season, slot=16, owner=1):
    return {'id': pid, 'season': season, 'round': 1, 'slot': slot,
            'originalTeamId': owner, 'classSize': 32}


def test_short_means_no_pick_in_the_next_two_drafts():
    m, (short, stocked) = _cupboard({1: [_pick(1, SEASON)], 2: [_pick(2, SEASON + 1, owner=2)]})
    assert m.isShortOfPicks(short), "this season's pick is about to be spent"
    assert not m.isShortOfPicks(stocked)


def test_the_cupboard_loads_its_window_before_reading_it():
    """The window flag is set by the first window read. Every reader used to test the flag
    BEFORE that read, so outside the tests (which set it by hand) nobody was ever short."""
    teams = [FakeTeam(1, 'Short', 6, 22), FakeTeam(2, 'Stocked', 20, 8)]
    m = TradeMarket(MarketPlayerManager([]), FakeTeamManager(teams), StubBrain(), SEASON, None)
    assert m._windowHasPicks is False and m._draftWindow is None

    def load():
        m._windowHasPicks = True        # what the DB read finds
        m._draftWindow = [SEASON + 1, SEASON + 2]
        return m._draftWindow
    m._draftWindowSeasons = load
    m.picksOwnedBy = lambda team: [] if team.id == 1 else [_pick(9, SEASON + 1, owner=2)]
    assert m.isShortOfPicks(teams[0])


def test_a_short_team_puts_no_premium_on_an_offered_pick():
    """Owner, 2026-11-04: the shortage premium is gone. A short team values a window pick
    exactly as a stocked one would, apart from its own contention weight."""
    window = _pick(1, SEASON + 1, owner=2)
    m, (short, stocked) = _cupboard({2: [window, _pick(4, SEASON + 2, owner=2)]})
    assert m.isShortOfPicks(short)
    assert abs(m._pickValueTo(short, window) / m._pickValueTo(stocked, window)
               - m.nowWeight(stocked) / m.nowWeight(short)) < 1e-9


def test_a_short_team_going_nowhere_lists_a_player_for_a_pick():
    m, (short, stocked) = _cupboard({2: [_pick(5, SEASON + 1, owner=2)]})
    vet = FakePlayer(30, 82, Position.RB, termRemaining=2)
    vet.team = short
    short.rosterDict['rb'] = vet
    m._coreOf = lambda team: set()
    m.brain.classifyArc = lambda p: 'prime'
    listing = m._restockListing(short, set())
    assert listing is not None and listing.trigger == 'pick_restock' and listing.player is vet
    # A stocked team does not.
    assert m._restockListing(stocked, set()) is None
    # Nor does it sell its future.
    m.brain.classifyArc = lambda p: 'developing'
    assert m._restockListing(short, set()) is None


def test_a_short_contender_restocks_in_the_offseason_only():
    """Short teams are nearly always contenders that spent picks moving up. In the
    offseason the FA draft fills the slot, so a contender sells; in season it does not."""
    def build(week):
        m, (_, contender) = _cupboard({1: [_pick(5, SEASON + 1, owner=1)]}, week=week)
        vet = FakePlayer(40, 82, Position.RB, termRemaining=2)
        vet.team = contender
        contender.rosterDict['rb'] = vet
        m._coreOf = lambda team: set()
        m.brain.classifyArc = lambda p: 'prime'
        return m, contender, vet
    m, contender, vet = build(None)
    assert m.isContending(contender) and m.isShortOfPicks(contender)
    listing = m._restockListing(contender, set())
    assert listing is not None and listing.player is vet
    m, contender, _ = build(20)
    assert m.isContending(contender) and m._restockListing(contender, set()) is None


def test_the_restock_pick_is_the_buyers_cheapest_window_pick():
    near, far, out = _pick(7, SEASON + 1, slot=30, owner=2), _pick(8, SEASON + 2, slot=3, owner=2), \
        _pick(9, SEASON, slot=31, owner=2)
    m, (short, buyer) = _cupboard({2: [near, far, out]})
    piece = m._restockPickFor(buyer, short)
    assert piece['id'] == 7, "cheapest on the buyer's scale, inside the seller's window"
    assert abs(piece['value'] - m._pickValueTo(short, near)) < 1e-9
    m2, (short2, bare) = _cupboard({2: [out]})
    assert m2._restockPickFor(bare, short2) is None


def test_no_pick_rows_means_nobody_is_short():
    m, (short, stocked) = _cupboard({})
    m._windowHasPicks = False
    assert not m.isShortOfPicks(short) and not m.isShortOfPicks(stocked)


def test_a_bundle_never_takes_a_teams_last_window_pick():
    """Owner, 2026-11-04: a team may trade one of its next two drafts' picks, never both.
    Teams emptied the cupboard paying for trade-ups with both later picks at once."""
    a, b = _pick(1, SEASON + 1, slot=10), _pick(2, SEASON + 2, slot=20)
    now = _pick(3, SEASON, slot=5)
    m, (buyer, seller) = _cupboard({1: [a, b, now]})
    assets = [{'kind': 'pick', 'id': 1, 'value': 10.0, 'detail': a},
              {'kind': 'pick', 'id': 2, 'value': 6.0, 'detail': b}]
    m._tradeableAssets = lambda team, valuingTeam=None, swapPosition=None, **kw: [dict(x) for x in assets]
    # One window pick clears the bar: fine.
    got = m._assemble(buyer, seller, bar=5.0, gross=100.0, displaced=0.0)
    assert [p['id'] for p in got] == [2]
    # Only both would clear it: refused rather than emptying the window.
    assert m._assemble(buyer, seller, bar=12.0, gross=100.0, displaced=0.0) == []
    # This season's pick is outside the window and can go with one window pick.
    assets.append({'kind': 'pick', 'id': 3, 'value': 9.0, 'detail': now})
    got = m._assemble(buyer, seller, bar=12.0, gross=100.0, displaced=0.0)
    assert {p['id'] for p in got} & {1, 2} and not {1, 2} <= {p['id'] for p in got}


def test_the_window_is_the_two_drafts_after_this_seasons():
    m = TradeMarket(MarketPlayerManager([]), FakeTeamManager([FakeTeam(1, 'A')]), StubBrain(),
                    SEASON, None)
    assert m._draftWindowSeasons() == [SEASON + 1, SEASON + 2]


def test_restock_lists_a_veteran_not_a_long_contract():
    m, (short, _) = _cupboard({2: [_pick(5, SEASON + 1, owner=2)]})
    m._coreOf = lambda team: set()
    long = FakePlayer(31, 88, Position.QB, termRemaining=4)
    old = FakePlayer(32, 80, Position.WR, termRemaining=3)
    for slot, p in (('qb', long), ('wr1', old)):
        p.team = short
        short.rosterDict[slot] = p
    m.brain.classifyArc = lambda p: 'regressing' if p is old else 'prime'
    listing = m._restockListing(short, set())
    assert listing is not None and listing.player is old


def test_the_offseason_reads_as_the_season_that_just_ended():
    """Owner, 2026-11-04: in the offseason a walk-year player has the coming season left,
    so the copy must not say the contract is up or that he leaves at season end."""
    def why(week, trigger):
        m, (team, _) = _cupboard({}, week=week)
        p = FakePlayer(50, 80, Position.WR, termRemaining=1)
        p.team = team
        kept = FakePlayer(51, 85, Position.QB, termRemaining=1)
        m._resignPriority = lambda t: [kept]
        return m.sellerWhy(team, p, trigger)
    off = why(None, 'expiring_surplus')
    assert 'one season left' in off and 'after next season' in off
    assert 'ends this season' not in off and 'season end' not in off
    assert 'ends this season' in why(20, 'expiring_surplus')
    assert 'could re-sign' in why(None, 'expiring_keeper')



def test_an_incoming_prospect_is_priced_above_what_the_receiver_has_there():
    """The Jetskis took two kicker prospects for one kicker slot (owner, 2026-11-04)."""
    m, (receiver, holder) = _cupboard({})
    k1 = FakePlayer(60, 70, Position.K)
    k2 = FakePlayer(61, 68, Position.K)
    holder.prospects = [k1, k2]
    for p in (k1, k2):
        p.prospect_seasons = 1
    ceilings = {id(k1): 82.0, id(k2): 76.0}
    m._believedCeiling = lambda team, p: ceilings[id(p)]
    m._needBar = lambda team, p, leaving=None: 72.0          # the receiver's kicker
    w = trading.laterWeight(m.nowWeight(receiver))
    posW = m._positionWeight(k1)
    got = {a['id']: a for a in m._tradeableAssets(holder, valuingTeam=receiver)
           if a['kind'] == 'prospect'}
    assert abs(got[60]['value'] - trading.prospectValue(67 + 10, 1, weight=w, positionWeight=posW)) < 1e-9
    assert abs(got[61]['value'] - trading.prospectValue(67 + 4, 1, weight=w, positionWeight=posW)) < 1e-9
    # Both in one package: the second has to beat the first, and cannot.
    counted = m._countProspectsOnce([dict(got[60]), dict(got[61])])
    assert counted[0]['value'] == got[60]['value'] and counted[1]['value'] == 0.0
    # The holder's own price is unchanged.
    own = {a['id']: a for a in m._tradeableAssets(holder) if a['kind'] == 'prospect'}
    assert '_need' not in own[60]
    assert abs(own[60]['value'] - trading.prospectValue(
        82.0, 1, weight=trading.laterWeight(m.nowWeight(holder)), positionWeight=posW)) < 1e-9
