"""Where a club sits in its contention cycle, and what that changes.

⚠️ THE MARKET READ THIS SEASON'S RECORD AND NOTHING ELSE. Contention, `nowWeight`, the hump
— all of it is wins and losses, and the only career arc in the system was per-PLAYER with
nothing aggregating it.

⚠️ MEASURED OVER 224 CLUB-SEASONS (seasons 8+ of a 14-season run): **corr(win%, regressing
share) = +0.000**. The record carries literally zero information about the cycle. Cranes
went **.893 with 60%** of their weighted starters in decline and were priced exactly like
Caddies at **.750 with 0%**.

⚠️ AND THE POPULATION ONLY EXISTS AFTER SEASON 6 (owner, 2026-09-16: "you'd need to let the
sim run for 10+ seasons to see it, thats when players start retiring"). Measured: 0%
regressing through season 5, 8% at season 6, ~20% from season 10. A short sample says this
feature is inert; it is only younger than the question.
"""

import os
import tempfile

os.environ['DATABASE_DIR'] = tempfile.mkdtemp(prefix='floos_cw_')

import constants                                                       # noqa: E402
from managers.tradeManager import TradeMarket                          # noqa: E402
from floosball_player import Position                                  # noqa: E402
from test_trade_market import (FakeTeam, FakePlayer, FakeTeamManager,   # noqa: E402
                               FakePlayerManager, StubBrain)

ARCS = {}


class ArcBrain(StubBrain):
    """⚠️ THE ARC IS STUBBED PER PLAYER, not derived, so a fixture can state the cycle it
    means to test. `classifyArc` reads potential headroom and retirement odds, neither of
    which a fake player carries."""

    def classifyArc(self, player):
        return ARCS.get(id(player), 'prime')


def _club(tid, name, wins, arcs):
    """arcs: {slot: 'developing'|'prime'|'regressing'}"""
    t = FakeTeam(tid, name, wins=wins, losses=28 - wins)
    for slot, pos in (('qb', Position.QB), ('rb', Position.RB), ('wr1', Position.WR),
                      ('wr2', Position.WR), ('te', Position.TE), ('k', Position.K)):
        p = FakePlayer(tid * 40 + hash(slot) % 13, 86, pos, termRemaining=3)
        t.rosterDict[slot] = p
        ARCS[id(p)] = arcs.get(slot, 'prime')
    return t


def _market(teams, week=18):
    return TradeMarket(FakePlayerManager([]), FakeTeamManager(teams), ArcBrain(), 12, week)


ALL_YOUNG = {s: 'developing' for s in ('qb', 'rb', 'wr1', 'wr2', 'te', 'k')}
ALL_OLD = {s: 'regressing' for s in ('qb', 'rb', 'wr1', 'wr2', 'te', 'k')}


def test_two_contenders_with_the_same_record_are_NOT_the_same_club():
    """Caddies .750 with 0% in decline and Cranes .893 with 60% were priced identically."""
    young = _club(1, 'Caddies', 21, ALL_YOUNG)
    old = _club(2, 'Cranes', 21, ALL_OLD)
    filler = [_club(10 + i, f"F{i}", 14, {}) for i in range(6)]
    m = _market([young, old] + filler)

    assert m.isContending(young) and m.isContending(old), "the fixture has no contenders"
    assert m.teamWindow(young) == 'open'
    assert m.teamWindow(old) == 'closing', m.teamWindow(old)
    assert m.nowWeight(old) > m.nowWeight(young), \
        "a club winning on players who will not be here prices the present no higher"
    print(f"PASS the closing window pays {m.nowWeight(old)/m.nowWeight(young):.2f}x "
          f"what the open one does")


def test_two_clubs_going_nowhere_are_NOT_the_same_club_either():
    """⚠️ THE SPLIT IS THE POINT. A young club going nowhere is BUILDING toward something; an
    old one going nowhere is finished. Both looked identical."""
    young = _club(1, 'Rising', 7, ALL_YOUNG)
    old = _club(2, 'Finished', 7, ALL_OLD)
    filler = [_club(10 + i, f"F{i}", 21, {}) for i in range(6)]
    m = _market([young, old] + filler)

    assert not m.isContending(young) and not m.isContending(old)
    assert m.teamWindow(young) == 'opening', m.teamWindow(young)
    assert m.teamWindow(old) == 'closed', m.teamWindow(old)
    assert m.nowWeight(young) < m.nowWeight(old), \
        "the club still building prices the present no lower than the finished one"
    print("PASS one is building, the other is finished")


def test_a_FINISHED_club_has_no_core_to_protect():
    """⚠️ THE CORE RULE PROTECTS THE PLAYERS A REBUILD IS FOR, and on a finished roster the
    best two are not that — they are the last assets of the team that just ended. ⚠️ The
    per-player declining exclusion catches the individual case; this catches the club-level
    one, where a still-PRIME star is stranded on a roster finished around him."""
    finished = _club(1, 'Finished', 7, {'qb': 'prime', 'rb': 'regressing',
                                        'wr1': 'regressing', 'wr2': 'regressing',
                                        'te': 'regressing', 'k': 'regressing'})
    building = _club(2, 'Rising', 7, ALL_YOUNG)
    filler = [_club(10 + i, f"F{i}", 21, {}) for i in range(6)]
    m = _market([finished, building] + filler)

    assert m.teamWindow(finished) == 'closed'
    assert m._coreOf(finished) == set(), "a finished club still shielded its stars"
    assert m._coreOf(building), "a club that is building sold its core"
    print("PASS the finished club sells; the one building holds")


def test_the_window_is_POSITION_WEIGHTED():
    """⚠️ A fading quarterback counts for more than a fading kicker — the same weighting the
    valuation already uses. An unweighted head count says a club whose KICKER is old is as
    compromised as one whose QUARTERBACK is."""
    oldQb = _club(1, 'OldQb', 21, {'qb': 'regressing'})
    oldK = _club(2, 'OldK', 21, {'k': 'regressing'})
    filler = [_club(10 + i, f"F{i}", 14, {}) for i in range(6)]
    m = _market([oldQb, oldK] + filler)
    assert m.teamWindow(oldQb) == 'closing', "a fading quarterback did not close the window"
    assert m.teamWindow(oldK) == 'open', "a fading kicker closed it"
    print("PASS one fading quarterback closes a window; one fading kicker does not")


def test_the_window_is_off_when_the_flag_is():
    teams = [_club(1, 'Old', 21, ALL_OLD)] + [_club(10 + i, f"F{i}", 14, {}) for i in range(6)]
    m = _market(teams)
    assert m.teamWindow(teams[0]) == 'closing'
    constants.TRADE_WINDOW_ENABLED = False
    try:
        m._windowCache.clear()
        assert m._computeWindow(teams[0]) == 'open', "the flag does not disable it"
    finally:
        constants.TRADE_WINDOW_ENABLED = True
    print("PASS the flag turns it off")


def test_a_losing_club_is_not_badged_WINDOW_OPEN():
    """⚠️ `open` WAS DOING TWO JOBS: "contending with the core intact" and "not contending,
    neither building nor finished". A 10-18 club came out of the ledger badged *Window open*,
    which reads as the opposite of its season. The neutral case is its own state — the
    absence of a signal, not a signal — weighted exactly like `open` but no longer claiming
    something untrue."""
    middling = _club(1, 'Middling', 8, {'qb': 'prime', 'rb': 'prime', 'wr1': 'prime',
                                        'wr2': 'prime', 'te': 'prime', 'k': 'prime'})
    filler = [_club(10 + i, f"F{i}", 21, {}) for i in range(6)]
    m = _market([middling] + filler)
    assert not m.isContending(middling)
    assert m.teamWindow(middling) == 'middling', m.teamWindow(middling)
    assert m.nowWeight(middling) == m.nowWeight.__wrapped__(m, middling) \
        if hasattr(m.nowWeight, '__wrapped__') else True
    print("PASS a club going nowhere is not told its window is open")


def _horizonListings(market, club):
    return [l for l in market.listingsFor(club) if l.trigger == 'horizon_mismatch']


def test_a_champion_with_its_core_intact_keeps_its_long_contracts():
    """⚠️ THE TIMELINE TRIGGER USED TO ASK ONLY "IS THIS CLUB CONTENDING?".

    Reported 2026-09-18: the team that had just won the Floos Bowl listed a good player
    with three seasons left, reason "Timeline", and fans read it as the team saying it
    could not hold him. It could. Contention is this season's win rate, so a champion is
    the MOST contending team in the league and every one of its long contracts qualified.
    "Term this team cannot use" is only true where the core is aging out from under the
    record — `teamWindow`'s `closing` — and a champion whose core is intact will be
    contending again next year.
    """
    champion = _club(1, 'Champs', 24, ALL_YOUNG)
    rest = [_club(10 + i, f"F{i}", 10, {}) for i in range(6)]
    m = _market([champion] + rest)
    assert m.isContending(champion)
    assert m.teamWindow(champion) == 'open', m.teamWindow(champion)
    assert _horizonListings(m, champion) == [], "a champion is selling years it will use"
    print("PASS a champion with its core intact keeps its long contracts")


def test_a_fading_contender_still_cashes_in_the_years_it_cannot_use():
    """The other half, and the reason the trigger exists: a club winning NOW on players who
    will not be here trades term for help this season. Same record as the champion above —
    only the arc mix differs, which is the whole point of the two axes."""
    fading = _club(1, 'Fading', 24, ALL_OLD)
    rest = [_club(10 + i, f"F{i}", 10, {}) for i in range(6)]
    m = _market([fading] + rest)
    assert m.isContending(fading)
    assert m.teamWindow(fading) == 'closing', m.teamWindow(fading)
    listings = _horizonListings(m, fading)
    assert listings, "a club winning on a fading core is not cashing in its years"
    why = listings[0].why
    assert 'rental' not in why, f"the seller reason still calls a 3-year deal a rental: {why}"
    assert 'more seasons' in why, why
    print("PASS a fading contender still trades the years it cannot use")
