"""Trade valuation — `trading.py`.

    Value = how much better than freely available, multiplied by how long you keep it.

Every number here is pinned against a measurement in docs/TRADING_PLAN.md §2, so a
retune has to disagree with the measurement on purpose rather than by accident.
"""

import trading
from constants import (REPLACEMENT_RATING, TRADE_CONTENTION_EXPONENT,
                       PROSPECT_DEVELOPMENT_WINDOW)


# ------------------------------------------------------------ time

def test_a_contract_is_a_4x_spread_on_identical_talent():
    """⚠️ THE HALF OF THE MODEL THAT IS EASY TO DROP. A walk-year player traded in week 10
    is 0.64 seasons of control against 2.64 for the same player with three years left —
    identical talent, four times the value. Without it a rental and a franchise player
    price the same and there is nothing to trade about."""
    walk = trading.seasonsOfControl(1, 10)
    three = trading.seasonsOfControl(3, 10)
    assert abs(walk - 0.64) < 0.02, walk
    assert abs(three - 2.64) < 0.02, three
    assert three / walk > 3.9

    # ⚠️ AND ASSERTED THROUGH `playerValue`, WHICH IS WHAT EVERY CALLER ACTUALLY USES.
    # Testing `seasonsOfControl` alone does not prove the valuation CONSULTS it: deleting
    # the control term from `playerValue` outright left this whole file green until this
    # pair was added.
    rentalValue = trading.playerValue(80, 1, 10)
    contractValue = trading.playerValue(80, 3, 10)
    assert contractValue / rentalValue > 3.9, (rentalValue, contractValue)
    print(f"PASS walk-year {walk:.2f} vs 3-year {three:.2f} — {three / walk:.1f}x, "
          f"and {rentalValue:.1f} vs {contractValue:.1f} in value")


def test_the_current_season_is_a_fraction_in_season():
    """A walk-year player is not one season of control in week 20 — he is two games."""
    assert trading.seasonsOfControl(1, 3) > trading.seasonsOfControl(1, 20)
    assert trading.playerValue(80, 1, 3) > trading.playerValue(80, 1, 20)
    print("PASS a rental is worth less the later it is bought")


def test_the_offseason_deals_in_whole_seasons():
    """⚠️ IN THE OFFSEASON THE WALK-YEARS ARE ALREADY GONE — the front office resolved
    them — so everyone remaining has WHOLE seasons of term and the rental market does not
    exist there at all."""
    assert trading.seasonsOfControl(3, None) == 3.0
    assert trading.seasonsOfControl(1, None) == 1.0
    print("PASS the offseason prices assets, not rentals")


def test_remaining_football_is_measured_against_the_SEASON_not_the_deadline():
    """⚠️ `GM_ACTIVE_WEEK` SAYS WHEN A TRADE MAY BE MADE, NOT HOW LONG THE PLAYER PLAYS.
    A player acquired at the deadline still plays weeks 22-28 and the playoffs; pricing
    him at zero because the window shut behind him would make the last trade of every
    season free."""
    from constants import GM_ACTIVE_WEEK
    assert trading.seasonRemainingFraction(GM_ACTIVE_WEEK) > 0.15
    print(f"PASS a deadline acquisition is still worth "
          f"{trading.seasonRemainingFraction(GM_ACTIVE_WEEK):.0%} of a season")


# --------------------------------------------------------- contention

def test_week_1_is_parity_and_nothing_clears():
    """⚠️ THE PROPERTY THAT PRODUCES A DEADLINE WITH NO DEADLINE RULE. In week 1 every
    club sits at 1.00, so buyer and seller price the future IDENTICALLY, there is no gap
    to trade across, and nothing fires. The market opens as the table separates."""
    best = trading.nowWeight(0.90, 0.50, week=1)
    worst = trading.nowWeight(0.10, 0.50, week=1)
    assert best == 1.0 and worst == 1.0, (best, worst)
    assert best - worst == 0.0
    print("PASS the week-1 gap is exactly 0.00")


def test_the_gap_opens_as_the_season_runs():
    gaps = [trading.nowWeight(0.80, 0.50, w) - trading.nowWeight(0.25, 0.50, w)
            for w in (1, 8, 12, 15)]
    assert gaps == sorted(gaps), gaps
    assert gaps[0] == 0.0 and gaps[-1] > 1.0
    print(f"PASS the buyer/seller gap opens 0.00 -> {gaps[-1]:.2f} over weeks 1-15")


def test_certainty_arrives_before_the_deadline():
    """Certainty at week 15 against a week-22 deadline leaves a seven-week window where
    clubs KNOW and must act."""
    assert trading.contentionRamp(15) == 1.0
    assert trading.contentionRamp(22) == 1.0
    assert trading.contentionRamp(14) < 1.0
    print("PASS clubs are certain from week 15, with seven weeks left to act")


def test_a_bubble_club_stands_pat_by_arithmetic():
    """⚠️ NO RULE SAYS SO. Near the league mean a club values now and later almost
    equally, so it neither buys nor sells — its next few results push it one way."""
    weight = trading.nowWeight(0.50, 0.50, week=20)
    assert abs(weight - 1.0) < 0.01
    print("PASS a league-average club sits at 1.00 even at the deadline")


def test_the_exponent_is_1_25():
    """⚠️ AT 2.0 THE BEST CLUB IN THE LEAGUE PAYS A TOP-TWO PICK FOR A SIX-WEEK RENTAL,
    which no real club does; linear compresses the whole market into six pick slots."""
    assert TRADE_CONTENTION_EXPONENT == 1.25
    superior = trading.nowWeight(1.0, 0.5, week=22)
    assert 2.0 < superior < 2.6, superior
    print(f"PASS a doubly-dominant club weighs the present {superior:.2f}x")


# ------------------------------------------------------------ assets

def test_value_is_zero_at_or_below_replacement():
    """⚠️ NOT NEGATIVE. A player the pool can replace is worth nothing in a trade, not a
    liability — the alternative to holding him is signing his equal for free."""
    assert trading.playerValue(REPLACEMENT_RATING, 3, 10) == 0.0
    assert trading.playerValue(REPLACEMENT_RATING - 20, 3, 10) == 0.0
    assert trading.playerValue(REPLACEMENT_RATING + 1, 3, 10) > 0.0
    print("PASS replacement level is the zero of the scale")


def test_an_80_is_worth_13_of_surplus_not_80():
    """Replacement is not zero: a club can always sign from the pool."""
    value = trading.playerValue(80, 1, None)
    assert abs(value - 13.0) < 0.01, value
    # Two years of the same player is two years of the same surplus.
    assert abs(trading.playerValue(80, 2, None) - 26.0) < 0.01
    print("PASS an 80 on a one-year deal is 13, not 80; on two years, 26")


def test_the_pick_curve_is_steep_and_monotone():
    """⚠️ THE STEEPNESS IS WHAT MAKES AN EARLY PICK A REAL ASSET and gives the market
    denominations to settle a gap with. Fitted to 4,000 simulated classes."""
    measured = {1: 98.6, 3: 92.0, 8: 85.2, 12: 81.6, 16: 78.4, 24: 71.8, 32: 57.2}
    for slot, want in measured.items():
        got = trading.pickSlotSkill(slot)
        assert abs(got - want) < 1.0, (slot, got, want)
    skills = [trading.pickSlotSkill(s) for s in range(1, 33)]
    assert skills == sorted(skills, reverse=True)
    print("PASS the pick curve reproduces the measured order statistics")


def test_a_future_pick_is_discounted_BY_SLOT():
    """⚠️ A FLAT HAIRCUT MUST FAIL THIS. Measured over 6,000 classes, class-to-class
    variation as a fraction of what the slot delivers runs 0.15 at pick 1 and 50.3 at
    pick 32 — so not knowing the class costs a LATE pick most and a TOP pick least."""
    top = trading.futurePickDiscount(1)
    mid = trading.futurePickDiscount(16)
    late = trading.futurePickDiscount(32)
    assert top > mid > late, (top, mid, late)
    assert top > 0.9, "a top-5 pick should barely be discounted"
    assert late < 0.65, "a late pick should be discounted steeply"
    assert len({round(top, 3), round(mid, 3), round(late, 3)}) == 3, "the discount is flat"
    print(f"PASS slot-scaled discount: {top:.2f} / {mid:.2f} / {late:.2f}")


def test_a_future_pick_is_worth_less_than_the_same_slot_this_year():
    """⚠️ FOR TIME AND RISK, NOT EXPECTATION. Every class is drawn from the same
    distribution, so a future pick's EXPECTED class is identical to this year's — what is
    worse is that it pays later and less predictably."""
    for slot in (1, 8, 16, 32):
        now = trading.pickValue(slot, 0)
        later = trading.pickValue(slot, 1)
        further = trading.pickValue(slot, 2)
        assert now > later > further or now == 0, (slot, now, later, further)
    print("PASS a pick loses value for each season out")


def test_a_pick_is_priced_on_the_MATURE_player():
    """⚠️ A draftee debuts `PROSPECT_ENTRY_DISCOUNT` below his true skill and grows into
    it, so pricing the pick at the debut rating undervalues every pick in the draft and
    ranks them by how little they were discounted."""
    from constants import PROSPECT_ENTRY_DISCOUNT
    matureSurplus = trading.pickSlotSkill(1) - REPLACEMENT_RATING
    debutSurplus = matureSurplus - PROSPECT_ENTRY_DISCOUNT
    assert trading.pickValue(1, 0, rookieTerm=1) > debutSurplus
    print("PASS pick 1 prices the 98.6, not the 87.6 he debuts at")


# ---------------------------------------------------------- prospects

def test_a_prospect_window_is_a_DEADLINE_not_a_term():
    """⚠️ `seasonsOfControl` measures seasons of CONTRIBUTION off `termRemaining`, and a
    prospect has neither. He contributes nothing in the pipeline, and
    `PROSPECT_DEVELOPMENT_WINDOW` is the time his club has to promote him or LOSE HIM."""
    odds = [trading.prospectPromotionOdds(n) for n in range(0, PROSPECT_DEVELOPMENT_WINDOW + 1)]
    assert abs(odds[0] - 0.83) < 0.02, odds
    assert abs(odds[1] - 0.70) < 0.02, odds
    assert abs(odds[2] - 0.45) < 0.02, odds
    assert odds[PROSPECT_DEVELOPMENT_WINDOW] == 0.0
    print(f"PASS p(promoted) by window used: {[round(o, 2) for o in odds]}")


def test_a_prospect_at_two_thirds_is_distressed():
    """His holder must find him a slot this offseason or lose him for nothing — the
    walk-year squeeze one level down, with urgency built in rather than bolted on."""
    fresh = trading.prospectValue(94, 0)
    mid = trading.prospectValue(94, 1)
    distressed = trading.prospectValue(94, 2)
    assert fresh > mid > distressed > 0
    assert distressed < fresh * 0.6
    print(f"PASS value falls {fresh:.0f} -> {mid:.0f} -> {distressed:.0f} as the window closes")


def test_the_deadline_travels_with_him():
    """✅ `prospect_seasons` moves with the player, so a buyer inherits the same clock. A
    distressed prospect is worth buying only if you have the slot the seller does not —
    exactly the trade that should happen — and passing him around cannot refresh it."""
    assert trading.prospectValue(94, 2) == trading.prospectValue(94, 2)
    assert trading.prospectValue(94, 2) < trading.prospectValue(94, 0)
    print("PASS a traded prospect carries his window, not a fresh one")


def test_a_prospect_is_priced_on_the_BUYERS_read():
    """Two clubs valuing the same prospect differently is not noise — it is a real
    difference in what each can DO with him."""
    optimist = trading.prospectValue(97, 1)
    pessimist = trading.prospectValue(85, 1)
    assert optimist > pessimist
    print(f"PASS the same prospect prices {pessimist:.0f} vs {optimist:.0f} on two reads")


# ------------------------------------------------- ask, floor and the bar

def test_the_floor_is_set_by_the_BACKFILL_not_a_constant():
    """⚠️ `floor < ask` REQUIRES `backfill > REPLACEMENT`, which is what makes the quality
    of the backfill decide whether a club is a seller at all."""
    ask, poor = trading.askAndFloor(80, 62, 1, 10)
    _, ok = trading.askAndFloor(80, 70, 1, 10)
    _, good = trading.askAndFloor(80, 79, 1, 10)
    assert poor >= ask, "a club with no replacement should refuse to sell"
    assert ok < ask and good < ok
    print(f"PASS ask {ask:.1f}; floor {poor:.1f} / {ok:.1f} / {good:.1f} "
          f"as the backfill improves")


def test_both_ends_decay_together_and_never_invert():
    """✅ So a late seller is never squeezed into a giveaway."""
    prev = None
    for week in range(1, 23):
        ask, floor = trading.askAndFloor(80, 72, 2, week)
        assert floor <= ask + 1e-9, (week, ask, floor)
        if prev is not None:
            assert ask <= prev + 1e-9
        prev = ask
    print("PASS the ask decays monotonically and the floor never crosses it")


def test_the_reserve_decay_matches_the_plan():
    table = {1: 1.00, 10: 0.67, 15: 0.48, 20: 0.30, 22: 0.22}
    for week, want in table.items():
        got = trading.reserveDecay(week)
        assert abs(got - want) < 0.02, (week, got, want)
    print("PASS reserve decay: 100% / 67% / 48% / 30% / 22%")


def test_a_division_rival_pays_a_premium_scaled_by_its_threat():
    """⚠️ DERIVED FROM THE SCHEDULE — 4 games against a division rival to 1 against
    anybody else — and SCALED BY THREAT: selling a rental to a 3-9 rival costs nothing,
    selling to the club you are chasing is self-harm."""
    weak = trading.counterpartyPremium(True, True, buyerNowWeight=0.3)
    strong = trading.counterpartyPremium(True, True, buyerNowWeight=2.1)
    league = trading.counterpartyPremium(False, True, buyerNowWeight=2.1)
    crossLeague = trading.counterpartyPremium(False, False, buyerNowWeight=2.1)
    assert strong > weak > 1.0
    assert strong > league > crossLeague
    assert crossLeague == 1.0, "a cross-league buyer should pay no premium at all"
    print(f"PASS rival premium {weak:.2f}x (weak) -> {strong:.2f}x (strong); "
          f"same league {league:.2f}x; cross-league {crossLeague:.2f}x")


def test_sentiment_raises_the_BAR_not_the_valuation():
    """⚠️ THE FINDING. Letting a favourite's tilt raise his own club's VALUATION left
    every buyer's clearing price IDENTICAL across the full tilt range, because the
    seller's constraint never binds: it is losing him for nothing, so any offer beats
    keeping him and only the BUYER can refuse."""
    plain = trading.requiredSurplus(10.0)
    darling = trading.requiredSurplus(10.0, sentiment=1.0, fanTrust01=1.0)
    hated = trading.requiredSurplus(10.0, sentiment=-1.0, fanTrust01=1.0)
    assert darling > plain > hated > 0
    assert abs(darling - 20.0) < 0.01, "a full favourite should double the bar"
    print(f"PASS required surplus {hated:.1f} / {plain:.1f} / {darling:.1f}")


def test_a_gm_who_ignores_fans_pays_no_sentiment_premium():
    assert trading.requiredSurplus(10.0, sentiment=1.0, fanTrust01=0.0) == 10.0
    print("PASS fanTrust gates the premium")


def test_every_modifier_is_a_price_never_a_veto():
    """The rule that governs all of them: they tip close calls, they never dictate. A bar
    is always a finite number a big enough offer can clear."""
    worst = trading.requiredSurplus(10.0, sentiment=1.0, fanTrust01=1.0,
                                    sameDivision=True, sameLeague=True,
                                    buyerNowWeight=3.0)
    assert 0 < worst < float('inf')
    assert worst < 10.0 * 10, "the modifiers stacked into a de facto veto"
    print(f"PASS the harshest bar is {worst:.1f} against a base of 10.0 — steep, not infinite")


# --------------------------------- present vs future: the currency gap

def test_a_pick_prices_on_laterWeight_not_nowWeight():
    """⚠️ THE WHOLE PREMISE CANCELS WITHOUT THIS. The plan's one idea is that clubs do not
    share a discount rate — "a contender prices THIS season high and the future low, a
    club going nowhere does the reverse, both are right, and that gap is the trade".
    Applying `nowWeight` to EVERY asset does not express that: it scales a club's whole
    valuation uniformly, so it drops out of every comparison and no gap remains.

    Measured with the uniform reading at week 20, a contender priced a mid first-round
    pick at 98.1 and a rebuilder at 22.9 — the club that wants to win NOW valuing a payoff
    two seasons out FOUR TIMES higher than the club rebuilding for exactly that moment.
    """
    contender = trading.nowWeight(0.80, 0.50, 20)
    rebuilder = trading.nowWeight(0.25, 0.50, 20)
    assert contender > 1.0 > rebuilder

    # A pick pays LATER.
    contenderPick = trading.pickValue(8, 0, weight=trading.laterWeight(contender))
    rebuilderPick = trading.pickValue(8, 0, weight=trading.laterWeight(rebuilder))
    assert rebuilderPick > contenderPick, (rebuilderPick, contenderPick)

    # A rental pays NOW.
    contenderRental = trading.playerValue(84, 1, 20, contender)
    rebuilderRental = trading.playerValue(84, 1, 20, rebuilder)
    assert contenderRental > rebuilderRental

    print(f"PASS the rebuilder prices the pick {rebuilderPick / contenderPick:.1f}x the "
          f"contender's, and the contender prices the rental "
          f"{contenderRental / rebuilderRental:.1f}x the rebuilder's")


def test_laterWeight_is_the_inverse_and_is_neutral_at_parity():
    """A club with nothing to play for and a club with everything must disagree, but a
    league-average club prices now and later the same — which is what makes a bubble team
    stand pat by arithmetic."""
    assert trading.laterWeight(1.0) == 1.0
    assert trading.laterWeight(2.0) < 1.0
    assert trading.laterWeight(0.5) > 1.0
    assert abs(trading.laterWeight(trading.laterWeight(1.7)) - 1.7) < 1e-9
    print("PASS laterWeight is the inverse of nowWeight, neutral at 1.0")


def test_a_prospect_is_a_FUTURE_asset_too():
    """He contributes nothing until promoted, so he prices like a pick, not a starter."""
    contender = trading.laterWeight(trading.nowWeight(0.80, 0.50, 20))
    rebuilder = trading.laterWeight(trading.nowWeight(0.25, 0.50, 20))
    assert (trading.prospectValue(92, 1, weight=rebuilder)
            > trading.prospectValue(92, 1, weight=contender))
    print("PASS a rebuilder outbids a contender for a prospect")
