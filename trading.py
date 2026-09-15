"""Trade valuation — one scale for three asset classes.

    Value = how much better than freely available, multiplied by how long you keep it.

Replacement is not zero: a club can always sign from the free-agent pool, so an 80 is
worth 13 of surplus and not 80. Time is the other half, and `termRemaining` already
carries it — a walk-year player traded in week 10 is 0.64 seasons of control against 2.64
for the same player with three years left. A 4x spread on identical talent, which is what
makes a contract an asset rather than a detail.

⚠️ THE CONTENTION WEIGHT IS WHAT MAKES A MARKET EXIST AT ALL. On the raw surplus-times-
time scale picks dominate rentals about ten to one and nothing would ever clear. The
missing term is that clubs do not share a discount rate:

    A contender prices THIS season high and the future low. A club going nowhere does
    the reverse. Both are right. They want different currencies, and that gap is the
    trade.

Everything here is a pure function of state that is passed in, so it can be measured
without booting the sim. The market that consumes it is `managers/tradeManager.py`.

See docs/TRADING_PLAN.md §2.
"""

from constants import (REPLACEMENT_RATING, GM_ACTIVE_WEEK,
                       TRADE_CONTENTION_EXPONENT, TRADE_CONTENTION_RAMP_WEEKS,
                       TRADE_RESERVE_DECAY_FLOOR,
                       TRADE_DIVISION_PREMIUM, TRADE_LEAGUE_PREMIUM,
                       TRADE_FUTURE_PICK_DISCOUNT_TOP,
                       TRADE_FUTURE_PICK_DISCOUNT_LATE,
                       TRADE_PROSPECT_SLOT_OPENS_CHANCE,
                       PROSPECT_DEVELOPMENT_WINDOW,
                       SENTIMENT_MAX_VALUE_SWING)


def _clamp(value, low, high):
    return max(low, min(high, value))


# ----------------------------------------------------------------- time

def seasonRemainingFraction(week: int) -> float:
    """How much of THIS season a buyer is actually buying.

    ⚠️ MEASURED AGAINST THE FULL REGULAR SEASON, NOT AGAINST THE TRADE DEADLINE, and the
    difference is not cosmetic. `GM_ACTIVE_WEEK` says when a trade may be MADE; it says
    nothing about how long the player then plays. A player acquired in week 22 still
    plays weeks 22-28 and the playoffs — pricing him at zero because the window shut
    behind him would make the last trade of every season free.

    Anchored here, the plan's reserve table reproduces exactly once read as a ratio to
    week 1 (0.67 / 0.48 / 0.30 / 0.22 at weeks 10 / 15 / 20 / 22), and a walk-year player
    in week 10 is the 0.64 seasons of control the plan quotes.
    """
    from seeding import REGULAR_SEASON_WEEKS
    week = _clamp(int(week or 1), 1, int(REGULAR_SEASON_WEEKS))
    return (REGULAR_SEASON_WEEKS - week) / float(REGULAR_SEASON_WEEKS)


def seasonsOfControl(termRemaining: int, week: int = None) -> float:
    """Seasons of CONTRIBUTION a buyer gets. `week=None` means the offseason.

    ⚠️ IN-SEASON, THE CURRENT SEASON IS A FRACTION. A walk-year player is not one season
    of control in week 20 — he is two games and then he is gone, which is why a rental
    and a contract price so differently on the same rating.

    ⚠️ IN THE OFFSEASON THE WALK-YEARS ARE ALREADY GONE (the front office resolved them)
    and everyone remaining has WHOLE seasons of term, so offseason trades are about
    ASSETS and the rental market does not exist there at all.
    """
    term = max(0, int(termRemaining or 0))
    if week is None:
        return float(term)
    if term <= 0:
        return 0.0
    return (term - 1) + seasonRemainingFraction(week)


def contentionRamp(week: int = None) -> float:
    """How much of this season's evidence has arrived. 0.0 in week 1, 1.0 from week 15.

    ⚠️ IN WEEK 1 EVERY CLUB READS THE SAME, so buyer and seller price the future
    identically, there is no gap to trade across, and nothing fires. The market opens as
    the table separates — a deadline without a deadline rule.

    The offseason (`week=None`) returns 0.0 for the same reason it is true there:
    contention is unknown for a season that has not been played, so every club is back at
    parity. ⚠️ That removes the buyer/seller asymmetry entirely, which is why the
    offseason market cannot run on contention and runs on the other three triggers.
    """
    if week is None:
        return 0.0
    return _clamp((int(week or 1) - 1) / float(TRADE_CONTENTION_RAMP_WEEKS), 0.0, 1.0)


def nowWeight(contention: float, leagueMeanContention: float, week: int = None) -> float:
    """How much THIS club values the present relative to the league.

    `contention` is any monotone read of how well the club is doing — projected wins,
    win percentage, ELO. Only its ratio to the league mean is used, so the caller may
    supply whatever it has.

    Blended against parity by `contentionRamp`, because a club does not know in week 2
    whether it is a contender.
    """
    mean = float(leagueMeanContention or 0.0)
    if mean <= 0:
        return 1.0
    raw = (max(0.0, float(contention or 0.0)) / mean) ** TRADE_CONTENTION_EXPONENT
    ramp = contentionRamp(week)
    return 1.0 + (raw - 1.0) * ramp


# ---------------------------------------------------------------- assets

def playerValue(rating: float, termRemaining: int, week: int = None,
                weight: float = 1.0) -> float:
    """Surplus over replacement x seasons of control x the holder's now-weight.

    ⚠️ ZERO AT OR BELOW REPLACEMENT, never negative. A player the pool can replace is
    worth nothing in a trade — not a liability — because the alternative to holding him
    is signing his equal for free.
    """
    surplus = float(rating or 0.0) - REPLACEMENT_RATING
    if surplus <= 0:
        return 0.0
    control = seasonsOfControl(termRemaining, week)
    if control <= 0:
        return 0.0
    return surplus * control * max(0.0, float(weight))


def pickSlotSkill(slot: int, classSize: int = 32) -> float:
    """Expected true skill of the player taken at this slot.

    Fitted to the measured order statistics of `classSize` draws from the live generation
    constants (4,000 simulated classes):

        pick     1     3     8    12    16    24    32
        skill  98.6  92.0  85.2  81.6  78.4  71.8  57.2

    ⚠️ THE STEEPNESS IS THE POINT. Pick 1 is a future superstar, pick 16 league-average
    and pick 32 a token — which is what makes an early pick a real asset and gives the
    market denominations to settle a gap with.
    """
    n = max(1, int(classSize))
    k = _clamp(int(slot or 1), 1, n)
    # The order statistic of a normal falls off slowly through the middle and collapses
    # at the tail; a shifted log in the quantile reproduces the measured curve closely
    # (max error ~1.5 rating points against the table above).
    import math
    q = (k - 0.375) / (n + 0.25)            # Blom plotting position
    z = -_normalQuantile(q)                 # k=1 is the HIGHEST draw
    from constants import GEN_TRUESKILL_MEAN, GEN_TRUESKILL_STD
    return GEN_TRUESKILL_MEAN + z * GEN_TRUESKILL_STD


def _normalQuantile(p: float) -> float:
    """Inverse standard normal CDF (Acklam's rational approximation, ~1e-9 absolute).

    Written out because the codebase has no scipy, and the order-statistic curve above is
    the only thing that needs it.
    """
    import math
    p = _clamp(float(p), 1e-12, 1 - 1e-12)
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
         3.754408661907416e+00]
    pLow, pHigh = 0.02425, 1 - 0.02425
    if p < pLow:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / \
               ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)
    if p > pHigh:
        q = math.sqrt(-2 * math.log(1 - p))
        return -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / \
               ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)
    q = p - 0.5
    r = q * q
    return (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q / \
           (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1)


def futurePickDiscount(slot: int, classSize: int = 32) -> float:
    """How much a pick loses for being NEXT season's rather than this one's.

    ⚠️ IT SCALES WITH SLOT, AND A FLAT HAIRCUT IS WRONG. Measured over 6,000 simulated
    classes, class-to-class variation as a fraction of the surplus that slot delivers:

        pick      1     3     5    16    24     32
        sd/surp  0.15  0.13  0.13  0.19  0.49  50.3

    A top-5 pick's variation is a small fraction of what it delivers — the worst class in
    6,000 still gave pick 1 an 86 — while a late pick's variation is comparable to its
    entire value. So not knowing the class costs a LATE pick most and a TOP pick least.

    ⚠️ And the discount is for TIME AND RISK, NOT EXPECTATION: every class is drawn from
    the same distribution, so a future pick's expected class is identical to this year's.
    What is worse is that it pays later and it pays less predictably.
    """
    n = max(1, int(classSize))
    position = _clamp((int(slot or 1) - 1) / max(1.0, n - 1.0), 0.0, 1.0)
    return (TRADE_FUTURE_PICK_DISCOUNT_TOP
            - (TRADE_FUTURE_PICK_DISCOUNT_TOP - TRADE_FUTURE_PICK_DISCOUNT_LATE) * position)


def pickValue(slot: int, seasonsOut: int = 0, classSize: int = 32,
              rookieTerm: int = 3, weight: float = 1.0) -> float:
    """What a rookie pick is worth on the same surplus-times-time scale as a player.

    ⚠️ PRICED ON THE MATURE PLAYER, NOT THE DEBUT ONE. A draftee debuts
    `PROSPECT_ENTRY_DISCOUNT` below his true skill and grows into it, so pricing the pick
    at the debut rating undervalues every pick in the draft by about that much and ranks
    them by how little they were discounted.

    `seasonsOut` 0 is this year's pick; 1 and 2 are future drafts.
    """
    surplus = pickSlotSkill(slot, classSize) - REPLACEMENT_RATING
    if surplus <= 0:
        return 0.0
    value = surplus * max(0, int(rookieTerm)) * max(0.0, float(weight))
    for _ in range(max(0, int(seasonsOut))):
        value *= futurePickDiscount(slot, classSize)
    return value


def prospectPromotionOdds(prospectSeasons: int) -> float:
    """P(a slot opens at his position before his window closes).

    ⚠️ A PROSPECT'S CONTROL IS A DEADLINE, NOT A TERM. He contributes nothing while in the
    pipeline, and `PROSPECT_DEVELOPMENT_WINDOW` is the number of offseasons his club has
    to promote him or lose him for nothing.
    """
    left = max(0, int(PROSPECT_DEVELOPMENT_WINDOW) - int(prospectSeasons or 0))
    if left <= 0:
        return 0.0
    return 1.0 - (1.0 - TRADE_PROSPECT_SLOT_OPENS_CHANCE) ** left


def prospectValue(believedCeiling: float, prospectSeasons: int,
                  rookieTerm: int = 3, weight: float = 1.0) -> float:
    """Projected mature surplus x post-promotion term x p(he ever gets promoted).

    ⚠️ `believedCeiling` IS THE BUYER'S OWN READ, not the truth — see
    `prospect_scouting.believedPotential`. Two clubs valuing the same prospect differently
    is not noise here, it is a real difference in what each can DO with him.

    ⚠️ HIS POST-PROMOTION TERM IS NOT YET KNOWN (it comes from `_getPlayerTerm` at
    promotion), so this assumes a tier-typical rookie deal rather than reading one.

    ✅ THE DEADLINE TRAVELS with `prospect_seasons`, so a buyer inherits the same clock. A
    distressed prospect is worth buying only if you have the slot the seller does not —
    exactly the trade that should happen — and it cannot be gamed by passing him around,
    because each pass burns the same window.
    """
    surplus = float(believedCeiling or 0.0) - REPLACEMENT_RATING
    if surplus <= 0:
        return 0.0
    return (surplus * max(0, int(rookieTerm)) * prospectPromotionOdds(prospectSeasons)
            * max(0.0, float(weight)))


# ------------------------------------------------------ ask, floor, price

def reserveDecay(week: int = None) -> float:
    """How far the ask has come down. 1.0 in week 1, its floor at the deadline.

    ✅ DEADLINE PRESSURE FALLS OUT OF THE VALUE MODEL WITH NO NEW TERM, because the ask is
    surplus x REMAINING control and the remaining control is what shrinks:

        week      1    10    15    20    22
        reserve  100%  67%   48%   30%   22%

    Hold out early, take what you can get late — exactly how a real deadline behaves.
    """
    if week is None:
        return 1.0
    # Relative to week 1, which is what the plan's table quotes. The floor guards the
    # playoffs, where the regular season has run out but a pick still has value.
    base = seasonRemainingFraction(1)
    if base <= 0:
        return 1.0
    return max(TRADE_RESERVE_DECAY_FLOOR, seasonRemainingFraction(week) / base)


def askAndFloor(rating: float, backfillRating: float, termRemaining: int,
                week: int = None, weight: float = 1.0) -> tuple:
    """(ask, floor) — and ⚠️ CONFLATING THESE IS THE MISTAKE.

        ask     what the seller currently demands. Measured against REPLACEMENT.
        floor   the walk-away. Below it, keeping him beats trading him. Measured
                against WHO ACTUALLY REPLACES HIM.
        price   neither of these — it is the highest bid clearing the ask, set by the
                market.

    ⚠️ `floor < ask` REQUIRES `backfill > REPLACEMENT`, which is what makes the quality of
    the backfill the thing that decides whether a club is a seller at all. Bees' WR 80 at
    week 10, ask 5.7:

        backfill 62 -> floor 7.9   ABOVE the ask: will not sell
        backfill 70 -> floor 4.4   can discount
        backfill 79 -> floor 0.4   can go very low if it must

    ⚠️ A READY PROSPECT MAKES A CLUB WILLING, NOT CHEAP. A low floor buys room to hold out
    LATER, not a discount now — and because settlement is an auction, a seller with three
    interested contenders gets the best of the three whatever its floor is.

    ✅ Both ends decay together, so a late seller is never squeezed into a giveaway.
    """
    ask = playerValue(rating, termRemaining, week, weight)
    floor = playerValue(rating, termRemaining, week, weight)
    backfill = max(float(backfillRating or 0.0), REPLACEMENT_RATING)
    surplus = float(rating or 0.0) - REPLACEMENT_RATING
    if surplus > 0:
        overBackfill = float(rating or 0.0) - backfill
        floor = ask * max(0.0, overBackfill) / surplus
    return ask, floor


# ------------------------------------------------------------- modifiers

def counterpartyPremium(sameDivision: bool, sameLeague: bool,
                        buyerNowWeight: float = 1.0) -> float:
    """How much MORE a rival has to pay. A multiplier on the required surplus.

    ⚠️ DERIVED FROM THE SCHEDULE, NOT CHOSEN. 12 division games across 3 rivals is 4
    apiece; the other 12 league games spread over 12 clubs and the 4 interleague over 4.
    A division rival is faced FOUR TIMES as often as anybody else, and they are the only
    clubs that can take a division title — which at 8 divisions is what most of the league
    is playing for.

    ⚠️ SCALED BY THE RIVAL'S THREAT. Selling a rental to a 3-9 rival costs nothing;
    selling to the club you are chasing is self-harm.

    ⚠️ The seller is by definition not contending, so "why care who wins the division" is
    fair. Two answers hold: they play that rival four more times NEXT season, and their
    own fans care now.
    """
    if sameDivision:
        base = TRADE_DIVISION_PREMIUM
    elif sameLeague:
        base = TRADE_LEAGUE_PREMIUM
    else:
        return 1.0          # different league, one game a year, no shared title
    return 1.0 + base * max(0.0, float(buyerNowWeight))


def sentimentPremium(sentiment: float, fanTrust01: float) -> float:
    """How much more a FAVOURITE has to fetch. A multiplier on the required surplus.

    ⚠️ THE OBVIOUS WIRING MEASURABLY DOES NOTHING. Letting a beloved player's
    `sentimentTilt` raise his own club's VALUATION left every buyer's clearing pick
    identical across the full tilt range, because the seller's constraint never binds: it
    is losing him for nothing at season end, so every offer already beats keeping him and
    only the BUYER can refuse. Sentiment has to raise the bar the trade must clear.

        required surplus   +0%   +30%   +100%
        Pinecones           17    20      24
        Waffles             26    27      27

    At +30% a favourite costs a contender about three extra picks of value; at +100% he is
    only movable to the strongest buyer in the league.

    Shares `frontOfficeBrain.sentimentBarScale`'s shape and its reasoning; kept here as a
    pure function so the market can be priced without a brain.
    """
    from constants import SENTIMENT_BAR_MAX_RAISE, SENTIMENT_BAR_MIN_SCALE
    strength = _clamp(float(sentiment or 0.0), -1.0, 1.0) * _clamp(float(fanTrust01 or 0.0), 0.0, 1.0)
    return max(SENTIMENT_BAR_MIN_SCALE, 1.0 + strength * SENTIMENT_BAR_MAX_RAISE)


def requiredSurplus(ask: float, sentiment: float = 0.0, fanTrust01: float = 0.0,
                    sameDivision: bool = False, sameLeague: bool = False,
                    buyerNowWeight: float = 1.0) -> float:
    """What a bid from THIS counterparty must clear.

    One bar, every modifier on it — which is the whole finding: the modifiers are a PRICE,
    never a VETO, and they belong on the bar rather than on either side's valuation.
    """
    return (max(0.0, float(ask))
            * sentimentPremium(sentiment, fanTrust01)
            * counterpartyPremium(sameDivision, sameLeague, buyerNowWeight))
