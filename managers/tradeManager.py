"""The trade market — a two-sided listing market, resolved as a weekly auction.

Any club may post an asset it will move; every other club prices what is posted; the
poster takes the best offer clearing its reserve. Two-sided rather than sellers-only
because it unifies both shapes without special-casing — a rebuilder posting "WR 80, want
picks" and a contender posting "QB 78 with 3 years, want a rental" are the same
operation, and the second IS the 1-for-1 swap.

⚠️ THE PASS RUNS AT THE WEEK ROLLOVER AND NOWHERE ELSE. `cardEffects` reads a depicted
player's club at scoring time and the lineup locks at kickoff, so a trade executed between
two slates moves a player BETWEEN THE LOCK AND THE BANK and a card equipped against club A
scores against club B's result. This project has had FOUR separate incidents in exactly
that seam (the lineup-snapshot drift, `equipped_cards` not being a historical record, the
leaderboard's second door, Veteran's backfill). A trade is a between-weeks event like every
other roster change, and `weekIsClosed` is the predicate the fantasy side already trusts.

⚠️ LISTINGS ARE REGENERATED FROM THE TRIGGERS EACH WEEK RATHER THAN PERSISTED. The plan
asks that an unsold listing stay on the block and be re-priced weekly, and that a club may
WITHDRAW when its situation changes — and it says the way to get the withdrawal is that
"triggers are evaluated every week rather than latched at listing time". Re-deriving is
that, exactly, and it is restart-safe by construction: there is no half-written block to
resume. The ask decays, contention sharpens, and a bubble team that wins six straight
simply stops listing.

See docs/TRADING_PLAN.md §3.
"""

import logging

import trading
from constants import (TRADING_ENABLED, GM_ACTIVE_WEEK, REPLACEMENT_RATING,
                       TRADE_LISTINGS_PER_TEAM, TRADE_BIDS_PER_TEAM_PER_WEEK,
                       TRADE_CANDIDATES_PER_LISTING, TRADE_MAX_PIECES,
                       TRADE_PICK_HORIZON_SEASONS, FO_CUT_UPGRADE_MARGIN,
                       TRADE_MIN_CERTAINTY, TRADE_INQUIRY_ENABLED,
                       RESIGN_LIMIT_PER_OFFSEASON,
                       TRADE_INQUIRIES_PER_TEAM, TRADE_HUMP_BAND,
                       TRADE_INQUIRY_PREMIUM, TRADE_CORE_PREMIUM,
                       TRADE_INQUIRY_MIN_UPGRADE, TRADE_INQUIRY_MAX_PIECES,
                       TRADE_HUMP_APPETITE, TRADE_INQUIRY_APPETITE, TRADE_BUYER_NEEDS,
                       TRADE_PICK_SWAP_ENABLED, TRADE_PICK_SWAP_MIN_GAIN,
                       TRADE_WINDOW_DECLINE_HIGH,
                       TRADE_WINDOW_ASCENT_HIGH, TRADE_WINDOW_NOW_CLOSING,
                       TRADE_WINDOW_NOW_OPENING,
                       TRADE_PICK_PREMIUM_TOP, TRADE_PICK_PREMIUM_TOP_SLOTS,
                       TRADE_POSITION_APPETITE, TRADE_KICKER_CRISIS_FG_PCT,
                       TRADE_KICKER_CRISIS_MIN_ATT, TRADE_LOW_APPETITE_MAX_PIECES)

logger = logging.getLogger(__name__)

# What a slot is called, per position value, so a trade can check legality.
POSITION_SLOTS = {1: ['qb'], 2: ['rb'], 3: ['wr1', 'wr2'], 4: ['te'], 5: ['k']}

LOCKER_ROOM_ATTITUDE = 55       # below this he is dragging the room down

# Which listing a club posts when it can only post one. Lower is more urgent.
# ⚠️ ORDERED BY WHAT IS LOST BY NOT ACTING, which is not the same as what the asset is
# worth. A walk-year player walks for nothing in a few weeks; a headcase is costing the
# room every week he stays; a blocked prospect is burning his development window; a
# horizon mismatch is merely suboptimal and will still be there next week.
TRIGGER_URGENCY = {
    'expiring_surplus': 0,
    'locker_room': 1,
    'blocked_prospect': 2,
    'horizon_mismatch': 3,
    # ⚠️ LAST, because the club is happy either way — it would simply re-sign him. He is
    # on the block at a price, not because anything is forcing the issue.
    'expiring_keeper': 4,
    # ⚠️ NOT REALLY ON THIS LADDER. An inquiry is buyer-initiated and never enters
    # `listingsFor`, so it never competes with a real listing for the per-club cap; the
    # entry exists only so a sort over a mixed list is total.
    'inquiry': 9,
    'pick_swap': 9,
}


class Listing:
    """One asset on the block, with the ask and the walk-away that price it."""

    def __init__(self, team, player, trigger, ask, floor, why=None):
        self.team = team
        self.player = player
        self.trigger = trigger
        self.ask = ask
        self.floor = floor
        # ⚠️ RECORDED WHERE THE DECISION IS MADE. Every fact in it was computed to REACH the
        # decision, and reconstructing it later means recomputing state that has since moved
        # on — a trade pass changes rosters underneath itself by design.
        self.why = why

    def __repr__(self):
        return (f"<Listing {self.team.name}: {self.player.name} "
                f"({self.trigger}, ask {self.ask:.1f}, floor {self.floor:.1f})>")


class PickListing:
    """A DRAFT SLOT on the block, rather than a player.

    ⚠️ IT IS NOT A `Listing` AND MUST NOT BE, even though the auction treats them alike.
    Everything downstream of a `Listing` reads `.player` — roster slots, the backfill, the
    cut to make room — and a pick has none of that. Sharing the class would mean threading
    "is this actually a player?" through every one of those, which is how the two paths
    quietly grow different rules. The auction only needs `.team`, `.ask` and `.floor`, so
    that is all this carries in common.
    """

    def __init__(self, team, pick, ask, floor, why=None):
        self.team = team
        self.pick = pick            # the dict from `picksOwnedBy`
        self.player = None          # explicit: nothing here has a player
        self.trigger = 'pick_swap'
        self.ask = ask
        self.floor = floor
        self.why = why

    def __repr__(self):
        return (f"<PickListing {self.team.name}: S{self.pick['season']} "
                f"slot {self.pick['slot']} ask {self.ask:.1f}>")


class Bid:
    """What one club offers for one listing, and what it is worth to the SELLER."""

    def __init__(self, team, pieces, value, why=None):
        self.team = team
        self.pieces = pieces        # [{kind, id, name, detail, value}]
        self.value = value
        # ⚠️ THE BUYER'S SIDE WAS NEVER RECORDED. The trigger is the SELLER's reason, so a
        # ledger carrying only that reads as half a conversation: a club is moved for a
        # locker-room problem and nothing says why anyone wanted him.
        self.why = why

    def __repr__(self):
        return f"<Bid {self.team.name}: {len(self.pieces)} piece(s) worth {self.value:.1f}>"


class TradeMarket:
    """Prices and runs one pass of the market.

    Constructed per pass rather than held, so it always reads live state — the same
    reason `_foBrainForOffseason` rebuilds each offseason.
    """

    def __init__(self, playerManager, teamManager, brain, season: int, week=None):
        self.playerManager = playerManager
        self.teamManager = teamManager
        self.brain = brain
        self.season = season
        self.week = week            # None = an offseason pass
        self._contention = {}
        self._leagueMean = 0.0
        # Cached per pass: the sweep asks for it once per listing and once per bid.
        self._cannotKeepCache = {}
        self._coreCache = {}
        self._needCache = {}
        self._playoffCut = None
        self._posMeanCache = {}
        self._needsCache = {}
        self._windowCache = {}
        # Why bundles fail, for the market harness. Three reasons, three different answers.
        self.assembleFail = {}
        # ⚠️ Why an INQUIRY never happened, which "0 trades" cannot distinguish between:
        # the club was not close enough, it had no gap worth filling, or nobody in the
        # league was a big enough upgrade on the man it already has.
        self.inquiryFail = {}
        self.pickFail = {}
        self._computeContention()

    # ------------------------------------------------------------ context

    def _computeContention(self):
        """Read each club's contention off the standings.

        ⚠️ ANY MONOTONE READ WILL DO, because only the RATIO to the league mean is used —
        which is what lets this work in week 2 (where wins are noise) and in the offseason
        (where there are none). The ramp in `trading.nowWeight` is what handles the
        uncertainty, not a cleverer statistic here.
        """
        for team in getattr(self.teamManager, 'teams', None) or []:
            # ⚠️ THE RECORD LIVES IN `seasonTeamStats`, NOT ON `team.wins`. There is no
            # `wins` attribute on a Team, so `getattr(team, 'wins', 0)` reads 0 for every
            # club in the league, forever — which made every club EXACTLY league-average
            # all season and flattened the one gradient this entire market runs on.
            #
            # It is the root cause of every symptom the market showed: `expiring_surplus`
            # could NEVER fire (it needs a non-contender and there were none),
            # `horizon_mismatch` fired for everybody (it needs "contending", and >= mean
            # is true when every value equals the mean), and trades clustered wherever
            # the gate happened to open rather than where the table separated. Measured
            # over six seasons before the fix: 0 expiring-surplus listings out of 1,468.
            #
            # Read through the same accessor the standings board uses, so the market and
            # the table a fan is looking at cannot disagree about who is contending.
            stats = getattr(team, 'seasonTeamStats', None) or {}
            wins = float(stats.get('wins', 0) or 0)
            losses = float(stats.get('losses', 0) or 0)
            ties = float(stats.get('ties', 0) or 0)
            played = wins + losses + ties
            # 0.5 with nothing played, so week 1 is parity rather than a divide by zero.
            self._contention[getattr(team, 'id', None)] = (
                (wins + 0.5 * ties) / played) if played else 0.5
        values = list(self._contention.values())
        self._leagueMean = (sum(values) / len(values)) if values else 0.0

    def teamWindow(self, team) -> str:
        """Where this club sits in its contention cycle: opening / open / closing / closed.

        ⚠️ THE MARKET READ THIS SEASON'S RECORD AND NOTHING ELSE (owner, 2026-09-16:
        "there's a contention cycle ... where a team is in this cycle should direct how they
        conduct trades"). Everything it turns on — contention, `nowWeight`, the hump — is
        wins and losses, and the only career arc in the system is per-PLAYER with nothing
        aggregating it. Measured over 224 club-seasons, **corr(win%, regressing share) =
        +0.000**: the record carries literally zero information about the cycle. Cranes went
        .893 with **60%** of their weighted starters in decline and were priced exactly like
        a club at .750 with none.

        ⚠️ TWO AXES, NOT ONE. The record says whether a club is winning; the arc mix says
        whether that is about to continue. A closing window is a club winning NOW on players
        who will not be here — which is the most interesting club in the league to trade
        with, and was indistinguishable from a young one.

        ⚠️ POSITION-WEIGHTED, so a fading quarterback counts for more than a fading kicker —
        the same weighting the valuation already uses. An unweighted head count says a club
        whose kicker is old is as compromised as one whose quarterback is.
        """
        cached = self._windowCache.get(id(team))
        if cached is not None:
            return cached
        window = self._computeWindow(team)
        self._windowCache[id(team)] = window
        return window

    def _computeWindow(self, team) -> str:
        # ⚠️ READ LAZILY, NOT BOUND AT IMPORT. `from constants import X` copies the value,
        # so flipping `constants.X` at runtime does nothing to it — the flag would have been
        # untestable and unusable as a kill switch. `_coreOf` already reads its constants
        # this way.
        from constants import TRADE_WINDOW_ENABLED
        from managers.frontOfficeBrain import positionValue
        if not TRADE_WINDOW_ENABLED:
            return 'open'
        decline = ascent = total = 0.0
        for player in (getattr(team, 'rosterDict', None) or {}).values():
            if player is None:
                continue
            try:
                weight = float(positionValue(player))
            except Exception:
                weight = 1.0
            try:
                arc = self.brain.classifyArc(player)
            except Exception:
                arc = 'prime'
            total += weight
            if arc == 'regressing':
                decline += weight
            elif arc == 'developing':
                ascent += weight
        if total <= 0:
            return 'open'
        decline /= total
        ascent /= total
        contending = self.isContending(team)
        if contending:
            return 'closing' if decline >= TRADE_WINDOW_DECLINE_HIGH else 'open'
        # ⚠️ NOT CONTENDING SPLITS TWO WAYS AND THE SPLIT IS THE POINT. A young club going
        # nowhere is BUILDING toward something and must not sell its core; an old one going
        # nowhere is finished and should sell everything. Both looked identical before.
        if decline >= TRADE_WINDOW_DECLINE_HIGH:
            return 'closed'
        if ascent >= TRADE_WINDOW_ASCENT_HIGH:
            return 'opening'
        # ⚠️ A FIFTH STATE, BECAUSE 'open' WAS DOING TWO JOBS. It meant both "contending
        # with the core intact" and "not contending, neither building nor finished", so a
        # 10-18 club came out badged *Window open*, which reads as the opposite of its
        # season. Same treatment as 'open' in the weighting — it is the absence of a
        # signal, not a signal — but it no longer claims something untrue.
        return 'middling'

    def nowWeight(self, team) -> float:
        # ⚠️ THE WINDOW RIDES THE ONE DIAL THE WHOLE MARKET ALREADY TURNS ON. A closing
        # contender pays up because next season is worse — its alternative to winning now is
        # not winning later, it is not winning at all. A club whose window has not opened
        # does the reverse and accumulates.
        base = trading.nowWeight(self._contention.get(getattr(team, 'id', None), 0.5),
                                 self._leagueMean, self.week)
        window = self.teamWindow(team)
        if window == 'closing':
            return base * TRADE_WINDOW_NOW_CLOSING
        if window == 'opening':
            return base * TRADE_WINDOW_NOW_OPENING
        return base

    def isContending(self, team) -> bool:
        """Is this club's season worth protecting?

        ⚠️ READ OFF THE RAW TABLE, NOT OFF `nowWeight`. The weight is blended toward parity
        by `contentionRamp`, so in week 1 it is EXACTLY 1.00 for all 32 clubs and a
        `>= 1.0` test answers TRUE LEAGUE-WIDE — which silences the expiring-surplus
        trigger correctly and fires the horizon trigger for everybody at once. Measured,
        that made week 1 the busiest week of the market on a confidence nobody had.
        Whether a club is contending is a question about the STANDINGS; whether it should
        act on the answer yet is `hasClarity`.
        """
        mean = self._leagueMean or 0.0
        if mean <= 0:
            return True
        return self._contention.get(getattr(team, 'id', None), 0.5) >= mean

    def hasClarity(self) -> bool:
        """Does anyone know their postseason position yet?

        ⚠️ THE MARKET DOES NOT OPEN UNTIL THIS IS TRUE (owner). A club that cannot read its
        own season should not be selling its walk-years or swapping its horizon — and
        without this the busiest trading week is week 1, which is precisely the week the
        table says nothing.

        ⚠️ THE OFFSEASON IS EXEMPT, and not by an oversight: there `contentionRamp` is 0.0
        by construction, because contention is unknown for a season that has not been
        played. Gating on it would shut the offseason market entirely, when that market is
        supposed to run on the other three triggers.
        """
        if self.week is None:
            return True
        return trading.contentionRamp(self.week) >= TRADE_MIN_CERTAINTY

    # ----------------------------------------------------------- triggers

    def listingsFor(self, team) -> list:
        """What this club would put on the block, best first, capped.

        Four triggers, and ⚠️ ONLY THE FIRST IS CONTENTION-GATED — so a contender already
        sells, for a locker-room problem or a blocked prospect, whether it is buying or
        not. Measured on the live league, seven contending clubs hold a sub-55 attitude
        player right now. No extra rule is needed to let a contender into the selling side.
        """
        if not self.hasClarity():
            return []           # nobody knows their season yet; nothing goes on the block
        out = []
        roster = getattr(team, 'rosterDict', None) or {}
        contending = self.isContending(team)
        prospects = list(getattr(team, 'prospects', None) or [])
        blocked = self._blockedPositions(team, prospects)
        cannotKeep = self._cannotKeep(team)
        core = self._coreOf(team)

        for slot, player in roster.items():
            if player is None or getattr(player, 'willRetire', False):
                continue
            if wasAcquiredThisSeason(player, self.season):
                continue        # pass-the-parcel: he only just got here
            trigger = None
            term = int(getattr(player, 'termRemaining', 0) or 0)
            attitude = self._attitudeOf(player)

            keepableWalker = (term <= 1 and id(player) not in cannotKeep
                              and not getattr(player, 'willRetire', False))
            if not contending and term <= 1 and id(player) in cannotKeep:
                # ⚠️ THE ENGINE OF THE WHOLE MARKET — but ONLY FOR A PLAYER THE CLUB
                # CANNOT KEEP. "He leaves for nothing" is the entire premise, and it is
                # simply false for a walk-year player the club can just re-sign. Without
                # the limit this fired on EVERY expiring player, and clubs sold their best
                # men for scraps: a 1-14 club shipped a 93-rated kicker for one prospect
                # at an ask of 0.3, and a 7-10 club a 96-rated back. Both would have been
                # the first name on their own re-sign list.
                trigger = 'expiring_surplus'
            elif attitude is not None and attitude < LOCKER_ROOM_ATTITUDE:
                trigger = 'locker_room'
            elif player.position.value in blocked:
                # ⚠️ CANNOT FIRE WITH AN EMPTY PIPELINE, which is one of the reasons the
                # draft lands first.
                trigger = 'blocked_prospect'
            elif self._horizonMismatch(team, player, contending):
                # ⚠️ WHAT MAKES A 1-FOR-1 A REAL TRADE RATHER THAN A COIN FLIP. QB-for-QB
                # is a TIME trade, not a talent trade: a rebuilder gives up now for term,
                # a contender term for now, and both are right. Rating barely enters.
                trigger = 'horizon_mismatch'
            elif keepableWalker:
                # ⚠️ A CLUB DECIDES WHO IS EXPENDABLE, AND A HIGHLY RATED PLAYER CAN BE —
                # "as long as the return is worth it" (owner, 2026-09-15). The re-sign cap
                # says who is DEFINITELY leaving; it does not say the rest are untouchable.
                # What changes is the PRICE, not the availability: this man is not a
                # rental, because the club holds the right to re-sign him, so what a buyer
                # is really acquiring is the contract that would follow. Priced that way
                # he costs several times what a surplus walk-year does, and only a return
                # that genuinely beats keeping him will clear it.
                trigger = 'expiring_keeper'
            if trigger is None:
                continue
            # ⚠️ THE CORE IS EXEMPT FROM THE VALUE TRIGGERS, NOT FROM ALL OF THEM.
            # `locker_room` still reaches him, because that is a reason to move a player
            # which has nothing to do with what he is worth — a franchise player poisoning
            # the room is a real decision a club has to make, and exempting him from it
            # would make attitude unable to touch the players it most matters for.
            if trigger != 'locker_room' and id(player) in core:
                continue

            ask, floor = self._priceListing(team, player, trigger)
            if ask <= 0:
                continue
            out.append(Listing(team, player, trigger, ask, floor,
                               why=self.sellerWhy(team, player, trigger)))

        # ⚠️ RANKED BY URGENCY, NOT BY ASK — a club posts the man it most needs to move,
        # not the one worth most. Sorting by ask looks sensible and is precisely wrong: a
        # walk-year rental has a TINY ask (a fraction of a season of control) while a
        # player with three years left has a large one, so the most valuable listing is
        # always the one the club is under no pressure to move. Measured with the ask
        # sort, `expiring_surplus` — the trigger the plan calls the engine of the whole
        # market — produced ZERO trades in three seasons and `horizon_mismatch` produced
        # 100%, because the urgent listing was never the one posted.
        #
        # A walk-year player leaves for NOTHING at season end, which is the whole reason
        # this market exists. He goes first.
        out.sort(key=lambda l: (TRIGGER_URGENCY.get(l.trigger, 99), -l.ask))
        return out[:TRADE_LISTINGS_PER_TEAM]

    # ------------------------------------------- the blockbuster (offseason)

    def _missedThePlayoffs(self, team) -> bool:
        stats = getattr(team, 'seasonTeamStats', None) or {}
        return not bool(stats.get('madePlayoffs', False))

    def _playoffCutWinPct(self) -> float:
        """The win% of the WORST club that qualified — the hump itself.

        ⚠️ READ OFF WHO ACTUALLY QUALIFIED rather than assumed from the league mean. With
        4 divisions a winner takes a top-four seed at any record, so the real cut sits
        BELOW the mean in a season with a weak division and above it in a tight one — the
        same fact the standings board's `clinchStatus` had to learn the hard way.
        """
        if self._playoffCut is not None:
            return self._playoffCut
        qualified = [self._contention.get(getattr(t, 'id', None), 0.5)
                     for t in (getattr(self.teamManager, 'teams', None) or [])
                     if not self._missedThePlayoffs(t)]
        self._playoffCut = min(qualified) if qualified else self._leagueMean
        return self._playoffCut

    def isOverTheHump(self, team) -> bool:
        """Is this club close enough for a blockbuster to be the right move?

        ⚠️ MISSED THE PLAYOFFS **AND** WAS CLOSE. Either half alone is the wrong club: a
        qualifier does not need to mortgage anything, and a club five games adrift buying a
        star is not getting over the hump, it is spending a rebuild on one season.
        """
        if not self._missedThePlayoffs(team):
            return False
        mine = self._contention.get(getattr(team, 'id', None), 0.5)
        return (self._playoffCutWinPct() - mine) <= TRADE_HUMP_BAND

    def topNeeds(self, team) -> set:
        """The positions this club is most short of, as position values.

        ⚠️ THE ONLY THING THAT MAKES POSITION VALUE AFFECT WHETHER A TRADE HAPPENS. It
        multiplies the ask and the buyer's worth alike, so it cancels out of every
        comparison — which is why kickers traded at their headcount (17% of trades, 17% of
        starters) while being worth 0.35 of a quarterback, and quarterbacks traded at 1%.
        A club spends picks on the problems that cost it most, and ranking the gaps is
        where that judgment lives.
        """
        cached = self._needsCache.get(id(team))
        if cached is not None:
            return cached
        # ⚠️ DISTINCT POSITIONS, NOT THE TOP N SLOTS. `_positionalGaps` is slot-wise and
        # WR owns two of the six, so taking the first three SLOTS routinely yielded a set
        # of two positions — measured, that collapsed running backs from 21% of trades to
        # 7% while leaving kickers untouched at 16%, which is neither the old distribution
        # nor the intended one.
        needs, ordered = set(), []
        for _slot, player in self._positionalGaps(team):
            posValue = getattr(getattr(player, 'position', None), 'value', None)
            if posValue in needs:
                continue        # the club's worse WR slot already put WR on the list
            needs.add(posValue)
            ordered.append(posValue)
            if len(ordered) >= TRADE_BUYER_NEEDS:
                break
        self._needsCache[id(team)] = needs
        return needs

    def _positionalGaps(self, team) -> list:
        """Where this club falls furthest behind the LEAGUE, worst first, as (slot, player).

        ⚠️ NOT "the lowest-valued starter", which is what a `rating x positionWeight` sort
        gives — and that is always the KICKER, because the position weight runs QB 1.00 to
        K 0.35 and a 90 kicker scores 31.5 against a 70 quarterback's 70.0. Measured with
        that sort, all 264 calls in six seasons were about kickers, exactly one bundle ever
        cleared, and the feature looked like a pricing problem when it was a targeting one.

        A hole is a deficit against what everyone ELSE has at the position — the same
        relative reading `needTilt` uses, and for the same reason: an absolute one hands
        every weak club a phantom need at its cheapest position. The deficit is then scaled
        by the position weight, so being 10 short at quarterback outranks being 10 short at
        kicker without the weight deciding the ranking on its own.
        """
        out = []
        for slot, player in (getattr(team, 'rosterDict', None) or {}).items():
            if player is None:
                continue
            posValue = getattr(getattr(player, 'position', None), 'value', None)
            deficit = self._leagueMeanAt(posValue) - self.ratingFor(team, player)
            out.append((deficit * self._positionWeight(player), slot, player))
        out.sort(key=lambda x: -x[0])
        return [(slot, player) for _, slot, player in out]

    def _leagueMeanAt(self, posValue) -> float:
        """Mean starter rating at this position across the league. Cached per pass."""
        cached = self._posMeanCache.get(posValue)
        if cached is not None:
            return cached
        ratings = [float(getattr(p, 'playerRating', 0) or 0)
                   for t in (getattr(self.teamManager, 'teams', None) or [])
                   for p in (getattr(t, 'rosterDict', None) or {}).values()
                   if p is not None
                   and getattr(getattr(p, 'position', None), 'value', None) == posValue]
        mean = (sum(ratings) / len(ratings)) if ratings else 0.0
        self._posMeanCache[posValue] = mean
        return mean

    def inquiriesFor(self, buyer) -> list:
        """Players this club would phone up about, priced by whoever holds them.

        ⚠️ THE ONLY BUYER-INITIATED PATH IN THE MARKET, and the reason it exists is that
        every other trigger fires on the SELLER's situation — so a star under contract was
        unreachable from both ends. Measured over six seasons before this: zero clubs below
        the playoff line bought anything in-season, and 37 of 44 in-season acquisitions
        were walk-year rentals.

        ⚠️ OFFSEASON ONLY (owner). In-season the market stays contract congestion; a club
        that wants to get over the hump does it between seasons, when it can see the table
        it finished on and a full season of the player it is buying still lies ahead.

        Returned as `Listing` objects so the bid, the auction and settlement are the SAME
        code — an inquiry differs in who starts it and what it costs, not in what a trade
        is. The holder is `listing.team`, exactly as for a posted player.
        """
        if not TRADE_INQUIRY_ENABLED:
            return []

        # ⚠️ TWO PHASES, TWO DIFFERENT BUYERS, AND THE GATE IS WHAT SEPARATES THEM.
        #   OFFSEASON — a club at the cut line mortgaging for a star (the blockbuster).
        #   IN-SEASON — a contender kicking the tires on clubs going nowhere (owner,
        #   2026-09-16: "in season trades should also be buyers kicking the tires on seller
        #   teams, not just sellers posting players they want to sell"). Before this, the
        #   only in-season path was a seller POSTING a player, so a contender could never
        #   go and ask about one it wanted.
        if self.week is None:
            if not self.isOverTheHump(buyer):
                self._noteInquiry('not_close_enough')
                return []
            sellersOnly = False
        else:
            if not self.hasClarity() or not self.isContending(buyer):
                self._noteInquiry('not_a_buyer_yet')
                return []
            # ⚠️ SELLERS ONLY, which is the owner's phrase and also the only version that
            # is not a free-for-all: a contender approaching another contender is asking a
            # club to damage its own season, and the whole in-season market already runs on
            # the contention gradient.
            sellersOnly = True

        out = []
        for slot, incumbent in self._positionalGaps(buyer)[:TRADE_INQUIRIES_PER_TEAM]:
            # ⚠️ A CLUB DOES NOT BUILD A BLOCKBUSTER AROUND A POSITION IT WILL NOT SPEND
            # AT (owner, 2026-09-15: "I wouldnt really consider trades for kickers
            # blockbusters"). The appetite already suppresses the bid, but a kicker's ask
            # is small enough that a cheap one still cleared it — and the objection is to
            # the KIND of trade, not its price, so the call is never made at all.
            if self._basePositionAppetite(incumbent) < 1.0:
                continue
            posValue = getattr(getattr(incumbent, 'position', None), 'value', None)
            mine = self.ratingFor(buyer, incumbent)
            best, bestSeen = None, 0.0
            for holder in (getattr(self.teamManager, 'teams', None) or []):
                if getattr(holder, 'id', None) == getattr(buyer, 'id', None):
                    continue
                if sellersOnly and self.isContending(holder):
                    continue
                for held in (getattr(holder, 'rosterDict', None) or {}).values():
                    if held is None or getattr(held, 'willRetire', False):
                        continue
                    if getattr(getattr(held, 'position', None), 'value', None) != posValue:
                        continue
                    if wasAcquiredThisSeason(held, self.season):
                        continue
                    # ⚠️ Rated on the BUYER's read, because the buyer is the one choosing
                    # who to call — its own scouting error is what makes two clubs chase
                    # different men, and reading ground truth here would make every club
                    # phone the same player.
                    seen = self.ratingFor(buyer, held)
                    if seen - mine < TRADE_INQUIRY_MIN_UPGRADE:
                        continue
                    if seen > bestSeen:
                        best, bestSeen = (holder, held), seen
            if best is None:
                self._noteInquiry('nobody_enough_better')
                continue
            holder, target = best
            ask, floor = self._priceInquiry(holder, target)
            if ask <= 0:
                self._noteInquiry('unpriceable')
                continue
            self._noteInquiry('called')
            out.append(Listing(holder, target, 'inquiry', ask, floor,
                               why=self.sellerWhy(holder, target, 'inquiry')))
        return out

    def pickInquiriesFor(self, buyer) -> list:
        """Draft slots this club would move UP for. Offseason only.

        ⚠️ THE MOVE COULD NOT BE EXPRESSED AT ALL BEFORE THIS. A `Listing` was always a
        player, so a pick could only ever be CHANGE inside somebody else's deal — measured
        over 8 seasons, of 86 picks that changed hands exactly ONE was a top-8 and 66% sat
        in the 17-24 band, because picks flow FROM buyers, buyers are contenders (median
        win% .641), and a contender's own pick lands late. The picks worth having belong to
        the clubs that never pay with them.

        ⚠️ THE BUYER PAYS WITH ITS OWN SLOT PLUS THE DIFFERENCE, which is what makes this a
        move UP rather than a purchase. Its own pick is an ordinary asset in
        `_tradeableAssets`, so `_assemble` will reach for it first when it is the cheapest
        thing that clears — no special casing needed.

        ⚠️ OFFSEASON ONLY: a slot is only known once the season has finished, and this is a
        buyer shopping for an upgrade (owner, 2026-09-16).
        """
        if not (TRADE_PICK_SWAP_ENABLED and TRADE_INQUIRY_ENABLED) or self.week is not None:
            return []
        self.pickFail['called'] = self.pickFail.get('called', 0) + 1
        mine = self.picksOwnedBy(buyer)
        if not mine:
            self.pickFail['no_pick_to_swap'] = self.pickFail.get('no_pick_to_swap', 0) + 1
            # ⚠️ A CLUB WITH NO PICK CANNOT MOVE UP — it has nothing to move up FROM, and
            # buying a slot outright is a different trade this market has no seller for.
            return []
        # ⚠️ THE PICK IT WOULD SWAP IN IS ITS BEST, not its cheapest: moving up means giving
        # up your place in the queue, and offering a worse pick than the one you hold makes
        # the deal strictly harder for the seller to accept.
        swapFor = max(mine, key=lambda p: self._pickValueTo(buyer, p))
        mineValue = self._pickValueTo(buyer, swapFor)

        out = []
        for holder in (getattr(self.teamManager, 'teams', None) or []):
            if getattr(holder, 'id', None) == getattr(buyer, 'id', None):
                continue
            for pick in self.picksOwnedBy(holder):
                if pick['season'] != swapFor['season']:
                    continue        # you move up WITHIN a draft, not across two
                if self._pickValueTo(buyer, pick) < mineValue * TRADE_PICK_SWAP_MIN_GAIN:
                    continue        # the two slots are interchangeable; moving is churn
                ask, floor = self._pricePick(holder, pick, swapFor=swapFor)
                if ask > 0:
                    listing = PickListing(
                        holder, pick, ask, floor,
                        why=(f"Paid to drop from slot {pick['slot']} to "
                             f"{swapFor['slot']}. The club does not need the very best "
                             f"player in this draft to fill the hole it has, so the "
                             f"distance is worth more to somebody else than to it."
                             + (" The window is shut, so what it needs is assets, not one "
                                "more good player."
                                if self.teamWindow(holder) == 'closed' else '')))
                    listing.swapFor = swapFor
                    out.append(listing)
        # ⚠️ THE BEST JUMP IT CAN AFFORD, NOT THE BIGGEST ONE AVAILABLE. Ranking by the
        # target's raw value always points a club at slot 1 — and the drop from slot 31 to
        # slot 1 is so large that no bundle in the league covers it, so every call was to
        # the one club that could never be paid. Measured: 2 inquiries a club, 0 bids.
        # Ranking by the buyer's own surplus finds the jump that is both worth making and
        # payable, which is what a real trade-up is.
        def surplus(l):
            gain = (self._pickValueTo(buyer, l.pick)
                    - self._pickValueTo(buyer, l.swapFor)) * TRADE_HUMP_APPETITE
            return gain - l.floor
        out.sort(key=lambda l: -surplus(l))
        if not out:
            self.pickFail['no_jump_worth_making'] = self.pickFail.get('no_jump_worth_making', 0) + 1
        else:
            self.pickFail['listed'] = self.pickFail.get('listed', 0) + 1
        return out[:TRADE_INQUIRIES_PER_TEAM]

    def _pickValueTo(self, team, pick) -> float:
        return trading.pickValue(pick['slot'], pick['season'] - self.season,
                                 weight=trading.laterWeight(self.nowWeight(team)))

    def _pricePick(self, holder, pick, swapFor=None):
        """What a club quotes to DROP from this slot to another — not to hand it over.

        ⚠️ PRICING THE SLOT ABSOLUTELY MAKES THE TRADE IMPOSSIBLE AND DESCRIBES THE WRONG
        DEAL. A club moving up swaps its own pick in, so the seller does not lose slot 1, it
        loses the DIFFERENCE between slot 1 and slot N — which is the same shape the rest of
        this market already uses (`_priceListing` prices surplus over the backfill;
        `bidFor` prices the upgrade over the man displaced). Measured on the absolute
        reading: a rebuilder holding slot 2 quoted **107** for it, against 31 for the
        slot-10 pick coming back, so nothing could ever clear.

        ⚠️ AND THE DIFFERENCE IS WHAT THE OWNER DESCRIBED: "the team with the top pick
        doesnt need the highest rated player in the draft and can afford to drop down a bit
        and still grab a good player, and by doing so can also get a good roster player at
        the same time." A club drops a few places and is paid for the drop.

        ⚠️ A TOP PICK IS STILL A CENTERPIECE and carries an extra premium on top of the
        ordinary unsolicited markup — but on the drop, not on the slot.
        """
        value = self._pickValueTo(holder, pick)
        if swapFor is not None:
            value -= self._pickValueTo(holder, swapFor)
        if value <= 0:
            return 0.0, 0.0
        premium = TRADE_INQUIRY_PREMIUM
        if int(pick.get('slot') or 99) <= TRADE_PICK_PREMIUM_TOP_SLOTS:
            premium *= TRADE_PICK_PREMIUM_TOP
        # ⚠️ BOTH ENDS, for the same reason as `_priceInquiry` — `settle` clears at the
        # FLOOR, so a premium on the ask alone is a number nobody pays.
        return value * premium, value * premium

    def bidForPick(self, listing, buyer):
        """What this club offers for a draft slot, or None.

        ⚠️ NO ROSTER MECHANICS AT ALL. Nobody is displaced, nothing is cut and no slot is
        backfilled — a pick trade touches `draft_picks` and the pipeline and stops there,
        which is why it gets its own path instead of a flag threaded through `bidFor`.
        """
        swapFor = getattr(listing, 'swapFor', None)
        if swapFor is None:
            return None
        # ⚠️ THE GAIN IS THE JUMP, NOT THE SLOT. The buyer keeps a pick either way; what it
        # is buying is the distance between the two, which is why the seller's bar is
        # priced the same way (see `_pricePick`).
        gain = (self._pickValueTo(buyer, listing.pick)
                - self._pickValueTo(buyer, swapFor)) * TRADE_HUMP_APPETITE
        if gain <= 0 or gain < listing.floor:
            self.pickFail['gain_under_bar'] = self.pickFail.get('gain_under_bar', 0) + 1
            return None

        # ⚠️ THE SWAP PICK GOES OVER SEPARATELY AND IS NOT PART OF THE ASSEMBLED BUNDLE.
        # `_assemble` takes the CHEAPEST assets that clear, so left to itself it would
        # happily pay with prospects and keep the pick — which is not a move up, it is
        # buying a second pick. Excluded from the pool so it cannot be offered twice.
        extras = self._assemble(buyer, listing.team, listing.floor, gain, 0.0,
                                maxPieces=TRADE_INQUIRY_MAX_PIECES,
                                excludeIds={('pick', swapFor['id'])})
        if not extras:
            self.pickFail['cannot_cover'] = self.pickFail.get('cannot_cover', 0) + 1
            return None
        self.pickFail['bid'] = self.pickFail.get('bid', 0) + 1
        swapPiece = {
            'kind': 'pick', 'id': swapFor['id'],
            'name': f"S{swapFor['season']} R{swapFor['round']} pick",
            'detail': swapFor,
            'value': self._pickValueTo(listing.team, swapFor),
        }
        pieces = [swapPiece] + extras
        why = (f"Moving up to slot {listing.pick['slot']} from "
               f"{swapFor['slot']} \u2014 the jump is worth more to this club than the "
               f"distance it gives up, and it keeps a pick either way.")
        window = self.teamWindow(buyer)
        if window == 'opening':
            why += " It is building, and this is the kind of asset it is building with."
        elif window == 'closing':
            why += " The window is closing, so the player has to arrive now."
        return Bid(buyer, pieces, sum(p['value'] for p in pieces), why=why)

    def _noteInquiry(self, reason: str) -> None:
        self.inquiryFail[reason] = self.inquiryFail.get(reason, 0) + 1

    def _priceInquiry(self, holder, player):
        """What the holder quotes an unsolicited caller.

        ⚠️ BOTH ENDS ARE MULTIPLIED, not just the ask. `settle` takes the best bid ABOVE
        THE FLOOR, so the floor is the real bar and a premium applied to the ask alone
        would be a number nobody pays.
        """
        ask, floor = self._priceListing(holder, player, trigger='inquiry')
        premium = TRADE_INQUIRY_PREMIUM
        if id(player) in self._coreOf(holder):
            premium *= TRADE_CORE_PREMIUM
        return ask * premium, floor * premium

    def needTilt(self, team) -> float:
        """How badly this club needs DEFENSE rather than offense. -1 .. +1.

        ⚠️ `playerRating` IS `(offensiveRating + defensiveRating) / 2`, so the market was
        blind to the distinction entirely: every player was the same kind of asset to every
        club, and a side with weapons and no defense had no reason to prefer a defender.
        Positive means defense lags; negative means offense does.

        ⚠️ MEASURED RELATIVE TO THE LEAGUE, not in absolute terms. A club that is simply
        bad at both has no particular NEED — it should take talent wherever it comes — and
        an absolute reading would hand every weak club a phantom defensive need.

        ⚠️ AND IT IS ZERO FOR A BALANCED CLUB, which is what keeps this a redistribution
        between clubs rather than a thumb on the whole market.
        """
        from constants import TRADE_NEED_SENSITIVITY, TRADE_NEED_MAX_TILT
        cached = self._needCache.get(id(team))
        if cached is not None:
            return cached
        teams = list(getattr(self.teamManager, 'teams', None) or [])
        offs = [float(getattr(t, 'offenseRating', 0) or 0) for t in teams]
        defs = [float(getattr(t, 'defenseRating', 0) or 0) for t in teams]
        offs = [o for o in offs if o > 0]
        defs = [dv for dv in defs if dv > 0]
        tilt = 0.0
        if offs and defs:
            meanOff, meanDef = sum(offs) / len(offs), sum(defs) / len(defs)
            myOff = float(getattr(team, 'offenseRating', 0) or 0)
            myDef = float(getattr(team, 'defenseRating', 0) or 0)
            if meanOff > 0 and meanDef > 0 and myOff > 0 and myDef > 0:
                offGap = (meanOff - myOff) / meanOff
                defGap = (meanDef - myDef) / meanDef
                tilt = max(-TRADE_NEED_MAX_TILT,
                           min(TRADE_NEED_MAX_TILT,
                               (defGap - offGap) * TRADE_NEED_SENSITIVITY))
        self._needCache[id(team)] = tilt
        return tilt

    def ratingFor(self, team, player, believed: float = None) -> float:
        """What this player is worth TO THIS CLUB, in rating points.

        A club short of defense values the defensive half of a player more, and vice
        versa. ⚠️ Centred so a balanced club reads exactly `playerRating` — the tilt
        redistributes, it does not inflate.

        `believed` lets a caller pass the GM's scouting-gated read of the overall rating;
        the need adjustment then rides on top of that rather than replacing it.
        """
        base = float(believed if believed is not None
                     else (getattr(player, 'playerRating', 0) or 0))
        off = float(getattr(player, 'offensiveRating', 0) or 0)
        dfn = float(getattr(player, 'defensiveRating', 0) or 0)
        if off <= 0 or dfn <= 0:
            return base             # nothing to tilt toward
        return base + self.needTilt(team) * (dfn - off) / 2.0

    def _coreOf(self, team) -> set:
        """The players this club is building around. Not trade assets.

        ⚠️ BEING HIGHLY RATED IS NOT THE SAME AS BEING AVAILABLE. Every value trigger
        priced a star as an asset with a big number on it, so a club's best man went on the
        block whenever the arithmetic said the return cleared — which is how a rebuilder
        ends up selling the one player its rebuild is supposed to be for.

        ⚠️ A CORE PLAYER MUST ACTUALLY BE A STAR. "The best two on a 2-14 club" as a rule
        would make the worst clubs untouchable and stop them trading at all, which is the
        opposite of what a rebuild does — so it takes the game's own bar, 4-star or better.

        ⚠️ AND A DECLINING STAR IS A LEGITIMATE ASSET. Selling high on a fading veteran is
        one of the few genuinely smart things a front office can do; the core is who you
        build AROUND, and a player on the way down is not that however good he still looks.
        """
        from constants import (TRADE_CORE_SIZE, TRADE_CORE_MIN_RATING,
                               TRADE_CORE_EXCLUDES_DECLINING)
        cached = self._coreCache.get(id(team))
        if cached is not None:
            return cached
        from managers.frontOfficeBrain import ARC_REGRESSING
        coach = getattr(team, 'coach', None)
        roster = [p for p in (getattr(team, 'rosterDict', None) or {}).values()
                  if p is not None]
        try:
            roster.sort(key=lambda p: -self.brain.decisionValue(p, coach=coach, team=team))
        except Exception:
            roster.sort(key=lambda p: -(getattr(p, 'playerRating', 0) or 0))
        # ⚠️ A CLUB WHOSE WINDOW HAS CLOSED HAS NOTHING TO BUILD AROUND. The core rule
        # protects the players a rebuild is FOR — and on a finished roster the best two are
        # not that, they are the last assets of the team that just ended. Before the window
        # existed, a young club going nowhere and an old one going nowhere were
        # indistinguishable, so both sat on their stars while one of them should have been
        # selling. ⚠️ The declining-player exclusion below already catches the individual
        # case; this catches the club-level one, where a still-prime star is stranded on a
        # roster that is finished around him.
        if self.teamWindow(team) == 'closed':
            self._coreCache[id(team)] = set()
            return set()

        core = set()
        for p in roster[:int(TRADE_CORE_SIZE)]:
            if (getattr(p, 'playerRating', 0) or 0) < TRADE_CORE_MIN_RATING:
                continue
            if TRADE_CORE_EXCLUDES_DECLINING:
                try:
                    if self.brain.classifyArc(p) == ARC_REGRESSING:
                        continue
                except Exception:
                    pass
            core.add(id(p))
        self._coreCache[id(team)] = core
        return core

    def retentionTerm(self, team, player, incoming: bool = False) -> float:
        """Extra seasons of control a walk-year player carries FOR THIS CLUB.

        ⚠️ ONE RULE, BOTH SIDES. The seller was pricing a keepable star on the contract
        that would follow while the buyer still priced him as a thirteen-week rental, so
        the ask sat around 108 against a bid of 3.5 and NOT ONE keeper ever sold —
        measured, 245 listed and zero clearing bids. A club acquiring him inherits the same
        right to re-sign him, so it has to value the same thing.

        ⚠️ AND WHETHER HE IS KEEPABLE IS A PROPERTY OF THE CLUB, NOT THE PLAYER.
        `RESIGN_LIMIT_PER_OFFSEASON` is 2, so it depends on who else that club has
        expiring: a contender with three mediocre walk-years can keep a 92 (he displaces
        one of them), while a club already holding two better men cannot. That is what
        makes a highly rated player genuinely expendable to one club and untouchable to
        another — and it is the whole reason a keeper trade can clear at all.

        `incoming=True` asks the hypothetical: if this club acquired him, would he make its
        own re-sign cut?
        """
        if (getattr(player, 'termRemaining', 99) or 99) > 1:
            return 0.0          # not a walk-year player; his term speaks for itself
        if getattr(player, 'willRetire', False):
            return 0.0
        if not incoming and id(player) in self._cannotKeep(team):
            return 0.0          # over this club's cap — he is leaving for nothing
        if incoming and not self._wouldMakeTheCut(team, player):
            return 0.0
        try:
            return float(self.playerManager.expectedPlayerTerm(player))
        except Exception:
            return 1.0

    def _wouldMakeTheCut(self, team, player) -> bool:
        """If this club acquired him, would he be one of the walk-years it re-signs?"""
        from constants import RESIGN_LIMIT_PER_OFFSEASON
        coach = getattr(team, 'coach', None)
        rivals = [p for p in (getattr(team, 'rosterDict', None) or {}).values()
                  if p is not None and p is not player
                  and not getattr(p, 'willRetire', False)
                  and (getattr(p, 'termRemaining', 99) or 99) <= 1]
        try:
            mine = self.brain.decisionValue(player, coach=coach, team=team)
            better = sum(1 for p in rivals
                         if self.brain.decisionValue(p, coach=coach, team=team) > mine)
        except Exception:
            mine = getattr(player, 'playerRating', 0) or 0
            better = sum(1 for p in rivals if (getattr(p, 'playerRating', 0) or 0) > mine)
        return better < int(RESIGN_LIMIT_PER_OFFSEASON)

    def _cannotKeep(self, team) -> set:
        """Which of this club's walk-year players are genuinely leaving.

        ⚠️ THE ONLY LIVE RETENTION CONSTRAINT IS THE PER-OFFSEASON CAP (owner, 2026-09-15:
        "theres no longer a re-sign limit for players, only the amount of players that can
        be re-signed every off season"). `RESIGN_LIMIT_PER_OFFSEASON` is 2 — a club with
        three expiring players loses one for nothing whatever it wants, and a club with one
        simply re-signs him, however good he is. There is no per-PLAYER cap:
        `RESIGN_ONCE_ENABLED` has been False since 2026-08-13, because at a limit of 1 a
        career-long one-club player was impossible.

        ⚠️ LEAVING THAT CLAUSE OUT TURNED "HE LEAVES FOR NOTHING" FROM A FACT INTO AN
        ASSUMPTION THAT WAS USUALLY FALSE. The plan states the trigger as "walk-year, OVER
        THE RE-SIGN LIMIT, not contending" and the middle third was never built, so it
        fired on EVERY expiring player: measured, a 1-14 club shipped a 93-rated kicker for
        one prospect at an ask of 0.3, and a 7-10 club a 96-rated back — both of them the
        first name on their own re-sign list.

        Ranked by the club's OWN `decisionValue`, the same number the offseason retention
        pass uses, so the market and the front office cannot disagree about who is
        keepable. The best two are kept; everyone past the cap is the surplus.

        ⚠️ `hasReachedResignLimit` is consulted anyway and is INERT BY DESIGN — it returns
        False while the per-player rule is off. It is the single source of truth for
        re-sign eligibility, so the market reads it rather than growing a second opinion
        that would have to be found and updated if that rule ever came back.
        """
        from constants import RESIGN_LIMIT_PER_OFFSEASON
        cached = self._cannotKeepCache.get(id(team))
        if cached is not None:
            return cached
        coach = getattr(team, 'coach', None)
        expiring = [p for p in (getattr(team, 'rosterDict', None) or {}).values()
                    if p is not None and not getattr(p, 'willRetire', False)
                    and (getattr(p, 'termRemaining', 99) or 99) <= 1]
        forced, keepable = set(), []
        pm = self.playerManager
        for p in expiring:
            try:
                if pm is not None and pm.hasReachedResignLimit(p):
                    forced.add(id(p))
                    continue
            except Exception:
                pass
            keepable.append(p)
        try:
            keepable.sort(key=lambda p: -self.brain.decisionValue(p, coach=coach, team=team))
        except Exception:
            keepable.sort(key=lambda p: -(getattr(p, 'playerRating', 0) or 0))
        result = forced | {id(p) for p in keepable[int(RESIGN_LIMIT_PER_OFFSEASON):]}
        self._cannotKeepCache[id(team)] = result
        return result

    @staticmethod
    def _attitudeOf(player):
        attrs = getattr(player, 'attributes', None)
        value = getattr(attrs, 'attitude', None) if attrs is not None else None
        return value or None

    def _blockedPositions(self, team, prospects) -> set:
        """Positions where a pipeline prospect the GM rates above the incumbent is stuck
        behind him."""
        blocked = set()
        coach = getattr(team, 'coach', None)
        roster = getattr(team, 'rosterDict', None) or {}
        for prospect in prospects:
            posValue = getattr(getattr(prospect, 'position', None), 'value', None)
            if posValue is None:
                continue
            incumbents = [roster.get(s) for s in POSITION_SLOTS.get(posValue, [])]
            incumbents = [p for p in incumbents if p is not None]
            if not incumbents:
                continue            # there is already a hole; nothing is blocking him
            try:
                pv = self.brain.decisionValue(prospect, coach=coach, team=team)
                worst = min(self.brain.decisionValue(p, coach=coach, team=team)
                            for p in incumbents)
            except Exception:
                continue
            if pv > worst:
                blocked.add(posValue)
        return blocked

    def _horizonMismatch(self, team, player, contending: bool) -> bool:
        """A contender holding long term it would swap for now, or the reverse."""
        term = int(getattr(player, 'termRemaining', 0) or 0)
        if contending:
            return term >= 3        # years it will not be around to use
        return False                # a rebuilder's long deals are exactly what it wants

    def sellerWhy(self, team, player, trigger) -> str:
        """Why this club is willing to move him, in its own terms.

        ⚠️ WRITTEN AT THE MOMENT THE DECISION IS MADE, not reconstructed afterwards. Every
        fact here is already computed to REACH the decision — the trigger, the re-sign cap,
        the prospect behind him, the attitude, the window — so recording it costs a string
        and reconstructing it later would mean recomputing state that has since moved on.
        """
        window = self.teamWindow(team)
        name = getattr(player, 'name', 'him')
        pos = getattr(getattr(player, 'position', None), 'name', '')

        if trigger == 'expiring_surplus':
            why = (f"Cannot re-sign {name} \u2014 he is past the club's "
                   f"{int(RESIGN_LIMIT_PER_OFFSEASON)}-player re-sign limit and walks for "
                   f"nothing at season end. Anything beats that.")
        elif trigger == 'expiring_keeper':
            why = (f"Could keep {name}, so he is priced on the contract that would follow "
                   f"rather than the weeks left. Available only to a return that beats "
                   f"re-signing him.")
        elif trigger == 'blocked_prospect':
            prospect = next((p for p in (getattr(team, 'prospects', None) or [])
                             if getattr(getattr(p, 'position', None), 'name', '') == pos),
                            None)
            who = getattr(prospect, 'name', 'a prospect')
            why = (f"{who} is ready at {pos} and stuck behind {name}. Moving him opens the "
                   f"slot rather than letting the pipeline rot.")
        elif trigger == 'locker_room':
            att = self._attitudeOf(player)
            why = (f"{name}'s attitude ({int(att)}) is dragging the room down every week he "
                   f"stays." if att else f"{name} is a locker-room problem.")
        elif trigger == 'horizon_mismatch':
            why = ("Holding term this club cannot use." if not self.isContending(team)
                   else "Holding a rental this club cannot keep.")
        elif trigger == 'inquiry':
            why = f"Nobody put {name} on the block \u2014 another club called and asked."
        else:
            why = f"{name} is available."

        if window == 'closed':
            why += (" The window is shut and the core is fading, so there is nothing here "
                    "to build around.")
        elif window == 'opening':
            why += " The club is still building, so the return matters more than the man."
        elif window == 'closing':
            why += " Selling from a side that is still winning, which is the hard call."
        return why

    def buyerWhy(self, buyer, listing) -> str:
        """Why this club wants him, in its own terms.

        ⚠️ THE BUYER'S SIDE WAS NEVER RECORDED AT ALL. The trigger is the SELLER's reason,
        and a ledger showing only that reads as half a conversation — a club is moved for a
        locker-room problem and nothing says why anyone wanted him.
        """
        player = listing.player
        pos = getattr(getattr(player, 'position', None), 'name', '')
        bits = []

        needs = self.topNeeds(buyer)
        posValue = getattr(getattr(player, 'position', None), 'value', None)
        if posValue in needs:
            gaps = [getattr(getattr(p, 'position', None), 'name', '')
                    for _s, p in self._positionalGaps(buyer)]
            rank = (gaps.index(pos) + 1) if pos in gaps else None
            bits.append(f"{pos} is this club's "
                        f"{'biggest' if rank == 1 else 'number ' + str(rank)} hole against "
                        f"the rest of the league" if rank else
                        f"{pos} is one of this club's holes")

        tilt = self.needTilt(buyer)
        if abs(tilt) > 0.25:
            side = 'defense' if tilt > 0 else 'offense'
            bits.append(f"it is short on {side} relative to the league, and he helps there")

        window = self.teamWindow(buyer)
        if window == 'closing':
            bits.append("the window is closing \u2014 its alternative to winning now is not "
                        "winning later, it is not winning")
        elif window == 'open':
            bits.append("the window is open and the core is intact")
        elif window == 'opening':
            bits.append("it is still building, so this has to be worth more than the assets")

        # ⚠️ THE CUT IS DELIBERATELY NOT NAMED HERE. This is written when the BID is made
        # and settlement may still take a different path — a same-position swap needs no cut
        # at all — so predicting it would put a second, guessing source of truth beside the
        # aftermath strip, which records what actually happened. Two sources for one fact is
        # the failure this codebase keeps repeating.
        if not bits:
            return "An upgrade the club could afford."
        return bits[0][0].upper() + bits[0][1:] + (
            ('; ' + '; '.join(bits[1:]) + '.') if len(bits) > 1 else '.')

    def _priceListing(self, team, player, trigger=None):
        # ⚠️ NOT A RENTAL IF THE CLUB CAN RE-SIGN HIM. `retentionTerm` is the single rule,
        # and it returns 0 for a player over the club's cap — so `expiring_surplus` prices
        # as a rental and `expiring_keeper` on the contract that would follow, without two
        # code paths that could disagree.
        term = (int(getattr(player, 'termRemaining', 0) or 0)
                + self.retentionTerm(team, player))
        ask, floor = trading.askAndFloor(
            self.ratingFor(team, player),
            self._backfillRating(team, player),
            term,
            self.week,
            self.nowWeight(team),
            self._positionWeight(player))
        return ask, floor

    def _bestAvailableAt(self, team, player, week=None):
        """The best man this club could put in that slot WITHOUT trading — a ready
        prospect of its own, or the best free agent anybody could sign.

        ⚠️ USED BY BOTH SIDES AND THAT IS THE POINT. For the seller it sets the walk-away
        (`_backfillRating`); for the buyer it is the alternative to trading at all
        (`_displacedBy`). Two clubs looking at the same pool is exactly right — it is the
        same pool.

        ⚠️ THE POOL COUNTS IN THE OFFSEASON TOO, and gating it out was an over-correction.
        The seller does not sign anybody at settlement any more (see `_findBackfill`) — the
        hole waits for the FA draft, and `playerManager._attemptRosterFill` fills it with
        the best player available across BOTH the pool and the club's own pipeline,
        signing over a prospect where the free agent is better (owner, 2026-09-16: "the
        team can decide to promote their prospects during that draft, or sign a better FA
        even if it blocks their prospect. the goal is to build a better team from a skill
        standpoint"). So the pool IS what replaces him, just later — and pricing the floor
        against the club's own prospect alone made a weak pipeline a reason not to sell a
        player the draft would have replaced perfectly well.

        ⚠️ The real defect it was fixing lived in `_findBackfill`, which promoted a prospect
        on the spot: Midnights sold a 77 TE and installed a **62** immediately, so the
        floor's optimism was never tested against the draft. Leaving the hole fixes that at
        the source, and the floor can go back to pricing the whole board.
        """
        posValue = getattr(getattr(player, 'position', None), 'value', None)
        best = None
        for prospect in getattr(team, 'prospects', None) or []:
            if getattr(getattr(prospect, 'position', None), 'value', None) != posValue:
                continue
            if best is None or (getattr(prospect, 'playerRating', 0) or 0) > (
                    getattr(best, 'playerRating', 0) or 0):
                best = prospect
        for fa in getattr(self.playerManager, 'freeAgents', None) or []:
            if getattr(fa, 'willRetire', False):
                continue
            # ⚠️ Same reason as `_findBackfill`: a rostered player left in the pool would
            # price against a backfill the club cannot actually sign, and on the sell side
            # the floor is what decides whether it is a seller at all.
            if not _isTrulyUnrostered(fa):
                continue
            if getattr(getattr(fa, 'position', None), 'value', None) != posValue:
                continue
            if best is None or (getattr(fa, 'playerRating', 0) or 0) > (
                    getattr(best, 'playerRating', 0) or 0):
                best = fa
        return best

    def _backfillRating(self, team, player) -> float:
        """Who actually replaces him — `max(readyProspect, bestAvailableFreeAgent)`.

        ⚠️ THE QUALITY OF THE BACKFILL IS WHAT MAKES A CLUB A SELLER, because `floor < ask`
        requires `backfill > REPLACEMENT`. With mid-season signing every club can sell, but
        one with a good prospect sells far more readily than one drawing on the pool.
        """
        best = self._bestAvailableAt(team, player, week=self.week)
        return float(getattr(best, 'playerRating', 0) or 0) if best is not None else 0.0

    # -------------------------------------------------------- the auction

    def counterpartiesFor(self, listing) -> list:
        """Who to approach, ranked on PUBLIC INFORMATION ONLY.

        ⚠️ WHAT A LISTER CANNOT SEE IS THE OTHER GM'S SCOUTING ERROR AND ITS FANS'
        SENTIMENT — which is precisely why an offer can be declined. Remove that and every
        trade is pre-agreed and the market is theatre.

        Approached in contention order and capped, so a weekly pass stays legible in the
        news feed rather than being 31 conversations.
        """
        others = [t for t in (getattr(self.teamManager, 'teams', None) or [])
                  if getattr(t, 'id', None) != getattr(listing.team, 'id', None)]
        others.sort(key=lambda t: -self.nowWeight(t))
        return others[:TRADE_CANDIDATES_PER_LISTING]

    def bidFor(self, listing, buyer):
        """What this club offers, or None if it will not clear the bar.

        ⚠️ THE BAR IS THE SELLER'S ASK WITH EVERY MODIFIER ON IT — sentiment, the division
        premium — because the modifiers are a PRICE and never a VETO, and they belong on
        the bar rather than on either side's valuation.
        """
        player = listing.player
        coach = getattr(buyer, 'coach', None)
        buyerWeight = self.nowWeight(buyer)

        # ⚠️ A CLUB BIDS ON ITS OWN PROBLEMS, NOT ON WHATEVER IS ON THE BLOCK. See
        # `topNeeds`: without this, position value cancels out of the decision entirely and
        # the market trades what is cheap rather than what matters.
        if getattr(getattr(player, 'position', None), 'value', None) not in self.topNeeds(buyer):
            return None

        # What he is worth TO THE BUYER, on the buyer's own read of him.
        try:
            seen = self.brain.perceivedValue(player, coach, team=buyer)
        except Exception:
            seen = float(getattr(player, 'playerRating', 0) or 0)
        # perceivedValue is position-weighted board currency; the trade scale is raw
        # surplus x time, so price him on the rating the buyer BELIEVES he has.
        posW = self._positionWeight(player)
        believed = self.ratingFor(buyer, player, seen / max(0.01, posW))
        # ⚠️ AND PUT THE POSITION WEIGHT BACK. Dividing it out recovers the RATING this GM
        # believes he has, which is what the surplus-over-replacement scale needs — but
        # nothing re-applied it, so a kicker priced exactly like a quarterback and a club
        # paid three first-round picks for a 78-rated K on a walk year.
        # ⚠️ THE BUYER INHERITS THE RIGHT TO RE-SIGN HIM, so it prices the same quantity —
        # through ITS OWN cap. A club already holding two better walk-years gets a rental;
        # one with room gets the contract that follows, and only then can a keeper clear.
        buyerTerm = (int(getattr(player, 'termRemaining', 0) or 0)
                     + self.retentionTerm(buyer, player, incoming=True))
        gross = trading.playerValue(believed, buyerTerm, self.week, buyerWeight, posW)
        if gross <= 0:
            return None

        # ⚠️ THE BUYER IS BUYING AN UPGRADE, NOT A PLAYER — AND THIS IS THE FOURTH
        # INSTANCE OF THE ERROR THE PLAN NAMES THREE TIMES: a decision written for one
        # context, reused where the ALTERNATIVE CHANGED and the comparison did not.
        #
        # There are six position-locked slots and no bench, so every roster is complete by
        # construction and a buyer must DISPLACE someone to take him. Its alternative is
        # therefore not "nothing", it is "keep the man I would have to cut" — and pricing
        # the incoming player gross makes a contender bid the full value of an 84 to
        # replace the 88 it already has.
        #
        # Measured with the gross reading: 801 listings, 772 "clearing" bids and ONE
        # settled trade all season, because settlement then refused almost every one of
        # them as not an upgrade. The bids were never real.
        # ⚠️ THE ONE TERM THAT MAKES A BLOCKBUSTER POSSIBLE, AND IT HAS TO SIT ABOVE THE
        # GATE BELOW. Everywhere else the buyer's ceiling is the player's linear worth to
        # it, which is under every premium a holder quotes on an unsolicited call, so the
        # two ranges never overlap and no inquiry can clear at any piece cap. A club on the
        # cusp genuinely values him above linear: the win he brings converts a near-miss
        # into a berth, which is what "getting over the hump" means. `deadlineUrgency` is
        # this same idea in-season and returns parity in the offseason — the exact window
        # this path runs in.
        #
        # ⚠️ Applied to WILLINGNESS, never to the bundle. The package is still sized to the
        # seller's bar, so this buys a club the right to say yes, not a bigger haul.
        # ⚠️ TWO APPETITES, ONE PER PHASE. The offseason case is a club at the cut line
        # mortgaging for a star; the in-season case is a contender approaching a club going
        # nowhere. Both pay above linear worth — an unsolicited quote is unpayable
        # otherwise — but the hump club pays more, because the marginal win is worth most
        # exactly at the cut line.
        appetite = 1.0
        if listing.trigger == 'inquiry':
            appetite = TRADE_HUMP_APPETITE if self.week is None else TRADE_INQUIRY_APPETITE

        displaced, fee = self._displacedBy(buyer, player)
        net = gross - displaced
        if net <= 0:
            return None             # he does not improve this roster
        # ⚠️ The cut fee is part of the price. A club that must pay 4,350F to open the slot
        # is buying something more expensive than the same player into an empty one.
        # ⚠️ HOW WILLING THIS CLUB IS TO SPEND ASSETS AT THIS POSITION AT ALL — see
        # `TRADE_POSITION_APPETITE`. It is the only place position value decides WHETHER a
        # trade happens rather than only what it costs, because the weight multiplies the
        # ask and the buyer's worth alike and cancels out of every ratio.
        worthToBuyer = net * appetite * self._positionAppetite(player, buyer)

        bar = trading.requiredSurplus(
            listing.ask,
            sentiment=self._sentimentOf(player),
            fanTrust01=self._fanTrust(getattr(listing.team, 'coach', None)),
            sameDivision=self._sameDivision(listing.team, buyer),
            sameLeague=self._sameLeague(listing.team, buyer),
            buyerNowWeight=buyerWeight)
        if worthToBuyer < bar:
            return None             # he is not worth what this would cost

        # ⚠️ TWO VALUATIONS OF THE SAME BUNDLE, AND BOTH ARE LOAD-BEARING. What must clear
        # the seller's bar is what the bundle is worth TO THE SELLER; what the buyer is
        # deciding to part with is what the same bundle is worth TO THE BUYER. Those are
        # different numbers precisely because the two clubs discount the future
        # differently — and that difference is the only reason either of them agrees.
        # Pricing both sides at one club's rate collapses them and there is no trade.
        # ⚠️ A DESPERATE CLUB BIDS ABOVE THE MINIMUM, AND THAT IS THE WHOLE EFFECT. The
        # round is sealed, so a buyer that really needs him cannot rely on the seller's
        # floor being enough to win — it pads the offer. That is what "overpaying at the
        # deadline" IS, and it is also what gives the auction any dispersion at all:
        # sized to the bar alone every bidder offers the same package and the highest bid
        # is a tie.
        urgency = trading.deadlineUrgency(self.week, buyerWeight)
        # ⚠️ A BLOCKBUSTER IS ALLOWED TO BE A PARAGRAPH. The 3-piece cap exists so an
        # ordinary trade "reads as a sentence", and that is right for a walk-year rental —
        # but the whole shape being bought here is a haul, and measured at three pieces the
        # typical bundle reached only 0.78 of the bar, so the cap and not the price was
        # what refused most calls.
        pieces = self._assemble(buyer, listing.team, bar * urgency,
                                gross * urgency * appetite,
                                displaced,
                                swapPosition=getattr(getattr(player, 'position', None),
                                                     'value', None),
                                maxPieces=self._maxPiecesFor(listing, player))
        if not pieces:
            return None
        return Bid(buyer, pieces, sum(p['value'] for p in pieces),
                   why=self.buyerWhy(buyer, listing))

    def _displacedBy(self, buyer, incoming):
        """(value of the man this club must cut, the fee to cut him).

        Zero when the slot is already empty — the only case where a buyer's alternative
        really is nothing.
        """
        from managers.frontOfficeBrain import cutFeeFor
        posValue = getattr(getattr(incoming, 'position', None), 'value', None)
        roster = getattr(buyer, 'rosterDict', None) or {}
        weakest, weakestRating = None, None
        for slot in POSITION_SLOTS.get(posValue, []):
            held = roster.get(slot)
            if held is None:
                return 0.0, 0
            rating = self.ratingFor(buyer, held)
            if weakestRating is None or rating < weakestRating:
                weakest, weakestRating = held, rating
        if weakest is None:
            return 0.0, 0
        value = trading.playerValue(weakestRating,
                                    getattr(weakest, 'termRemaining', 0),
                                    self.week, self.nowWeight(buyer),
                                    self._positionWeight(weakest))

        return value, cutFeeFor(weakest)

    @staticmethod
    def _basePositionAppetite(player) -> float:
        """How willing a club is to spend trade assets at this position.

        ⚠️ NOT THE SAME QUANTITY AS `_positionWeight`, and keeping them separate is the
        point: the weight says what a player is WORTH and is used everywhere, while this
        says what a front office is prepared to TRADE for and is used here alone.
        """
        name = getattr(getattr(player, 'position', None), 'name', None)
        return float(TRADE_POSITION_APPETITE.get(name, 1.0))

    def _positionAppetite(self, player, buyer=None) -> float:
        """The base appetite, LIFTED in-season when the buyer's own man is failing.

        ⚠️ A RATING GAP CANNOT SEE A BLOWN KICK (owner, 2026-09-15: "if a team actually
        needs a K (their own K is underperforming, has blown games) then it makes sense to
        look for one at the trade deadline"). A kicker can rate 82 and be 9 for 17, and
        `_positionalGaps` compares him to the league on RATING — so the club least able to
        trust its kicker is exactly the club this gate was silencing. "Has blown games" is
        a claim about what he has done, so it is read off what he has done.

        ⚠️ OFFSEASON IS NEVER LIFTED. There are no blown kicks to react to yet, and the
        offseason is the case the owner objected to.
        """
        base = self._basePositionAppetite(player)
        if base >= 1.0 or buyer is None or self.week is None:
            return base
        return 1.0 if self._incumbentIsFailing(buyer, player) else base

    def _incumbentIsFailing(self, team, incoming) -> bool:
        """Is this club's own man at that position actually costing it games?

        Kickers only for now — the one position with a clean, universally-understood
        conversion rate. Another low-appetite position would need its own read.
        """
        if getattr(getattr(incoming, 'position', None), 'name', None) != 'K':
            return False
        for slot in POSITION_SLOTS.get(
                getattr(getattr(incoming, 'position', None), 'value', None), []):
            held = (getattr(team, 'rosterDict', None) or {}).get(slot)
            if held is None:
                continue
            kicking = (getattr(held, 'seasonStatsDict', None) or {}).get('kicking') or {}
            att = float(kicking.get('fgAtt', 0) or 0)
            made = float(kicking.get('fgs', 0) or 0)
            # ⚠️ DERIVED, NOT READ FROM `fgPerc` — that key is only written on the GAME
            # dict (`floosball_game.py:1266`), so on a season line it is 0 and every
            # kicker in the league would read as failing.
            if att >= TRADE_KICKER_CRISIS_MIN_ATT and \
                    (100.0 * made / att) < TRADE_KICKER_CRISIS_FG_PCT:
                return True
        return False

    @staticmethod
    def _positionWeight(player) -> float:
        from managers.frontOfficeBrain import positionValue
        try:
            return positionValue(player)
        except Exception:
            return 1.0

    def _sentimentOf(self, player) -> float:
        pid = getattr(player, 'id', None)
        return (getattr(self.brain, 'sentimentMap', None) or {}).get(pid, 0.0)

    def _fanTrust(self, coach) -> float:
        try:
            return self.brain._attrLean(coach, 'fanTrust')
        except Exception:
            return 0.0

    @staticmethod
    def _sameDivision(a, b) -> bool:
        da, db = getattr(a, 'division', None), getattr(b, 'division', None)
        return bool(da) and da == db

    @staticmethod
    def _sameLeague(a, b) -> bool:
        la, lb = getattr(a, 'league', None), getattr(b, 'league', None)
        la = getattr(la, 'name', la)
        lb = getattr(lb, 'name', lb)
        return bool(la) and la == lb

    def _maxPiecesFor(self, listing, player):
        """How many assets this particular trade may involve.

        ⚠️ THE OFFSEASON CAP ON A LOW-APPETITE POSITION IS A HARD CAP, NOT A DISCOUNT
        (owner: "I just dont think it makes sense for teams to unload mulitple assets for
        one in the offseason"). The complaint is about the SHAPE of the deal, and a price
        rule can always be cleared by a club that wants him enough — so this limits the
        bundle rather than the bar.
        """
        if self.week is None and self._basePositionAppetite(player) < 1.0:
            return TRADE_LOW_APPETITE_MAX_PIECES
        if listing.trigger == 'inquiry':
            return TRADE_INQUIRY_MAX_PIECES
        return None

    def _assemble(self, buyer, seller, bar: float, gross: float, displaced: float,
                  swapPosition=None, maxPieces=None, excludeIds=None) -> list:
        """The CHEAPEST combination of the buyer's assets that clears the SELLER's bar.

        ⚠️ CHEAPEST, NOT LARGEST, and capped at `TRADE_MAX_PIECES` so a trade reads as a
        sentence rather than a spreadsheet. A buyer that hands over everything it owns to
        clear a bar by four times is not negotiating.

        ⚠️ AND THE BUYER STILL HAS TO WANT TO. The bundle is sized against what the SELLER
        thinks it is worth, because that is the bar; the buyer then refuses if what it is
        giving up, ON ITS OWN SCALE, costs more than the upgrade is worth to it. A
        contender hands over picks cheaply BECAUSE it prices the future low, which is the
        trade working rather than a club being fleeced.

        ⚠️ `bar` AND `gross` ARRIVE ALREADY SCALED BY DEADLINE URGENCY, so a club with a
        closing window both offers more than it must and tolerates paying above plain
        value. Both halves are needed: raising only the ceiling changes nothing, because
        the bundle is sized to the bar.
        """
        sellerValue = {(a['kind'], a['id']): a['value'] for a in self._tradeableAssets(
            buyer, valuingTeam=seller, swapPosition=swapPosition)}
        buyerAssets = self._tradeableAssets(buyer, valuingTeam=buyer,
                                            swapPosition=swapPosition)
        # Cheapest FOR THE BUYER first, so it parts with what it minds least.
        if excludeIds:
            buyerAssets = [a for a in buyerAssets
                           if (a['kind'], a['id']) not in excludeIds]
        buyerAssets.sort(key=lambda a: a['value'])
        pieces, toSeller, toBuyer = [], 0.0, 0.0
        usedPlayer = False
        for asset in buyerAssets:
            if toSeller >= bar:
                break
            if len(pieces) >= (maxPieces or TRADE_MAX_PIECES):
                break
            if asset['kind'] == 'player':
                # ⚠️ AT MOST ONE STARTER, and only at the listing's own position. A second
                # would empty the position the incoming player is meant to fill.
                if usedPlayer:
                    continue
                usedPlayer = True
            worthToSeller = sellerValue.get((asset['kind'], asset['id']), 0.0)
            if worthToSeller <= 0:
                if asset['kind'] == 'player':
                    usedPlayer = False
                continue
            pieces.append(dict(asset, value=worthToSeller))
            toSeller += worthToSeller
            toBuyer += asset['value']
        if toSeller < bar:
            self.assembleFail['barNotCleared'] = self.assembleFail.get('barNotCleared', 0) + 1
            if not buyerAssets:
                self.assembleFail['noAssets'] = self.assembleFail.get('noAssets', 0) + 1
            return []

        # ⚠️ DROP WHAT THE BAR NO LONGER NEEDS. Cheapest-first is greedy and the assets are
        # LUMPY, so the last piece added can overshoot badly and carry earlier pieces that
        # are now redundant — and the buyer is then refused for a package it never had to
        # offer. Measured on a trade-up: cheapest-first took 7.5 + 10.3 + 27.0 = 44.8 to
        # clear a bar of 35.3, which exceeded the buyer's own ceiling of 44.4 by a hair;
        # dropping the redundant 7.5 leaves 37.3, still clearing, comfortably under.
        #
        # ⚠️ Most expensive FOR THE BUYER first, because that is what it minds losing most —
        # the same reason the accumulation runs cheapest-first.
        for piece in sorted(pieces, key=lambda p: -p['value']):
            if len(pieces) <= 1:
                break
            if toSeller - piece['value'] < bar:
                continue
            if piece['kind'] == 'player':
                continue        # the swap is structural, not change
            pieces.remove(piece)
            toSeller -= piece['value']
            toBuyer -= next((a['value'] for a in buyerAssets
                             if (a['kind'], a['id']) == (piece['kind'], piece['id'])), 0.0)
        # ⚠️ THE DISPLACED PLAYER IS COUNTED ONCE, NOT TWICE. When the buyer pays WITH the
        # man it would otherwise have had to cut, the displacement and the payment are the
        # same event — charging both makes a swap look twice as expensive as it is and
        # refuses almost every one of them. When it pays in picks instead, the displaced
        # player is a real additional cost (and a cut fee on top).
        costToBuyer = toBuyer if usedPlayer else toBuyer + displaced
        if costToBuyer >= gross:
            self.assembleFail['tooExpensive'] = self.assembleFail.get('tooExpensive', 0) + 1
            return []           # it costs the buyer more than the player is worth to it
        self.assembleFail['built'] = self.assembleFail.get('built', 0) + 1
        return pieces

    def _tradeableAssets(self, team, valuingTeam=None, swapPosition=None) -> list:
        """This club's picks, pipeline prospects, and — at `swapPosition` — a starter.

        ⚠️ A ROSTER PLAYER AT THE LISTING'S OWN POSITION IS THE ONE TRADE THAT NEEDS NO
        BACKFILL AND NO CUT ON EITHER SIDE, and leaving it out made every trade in the
        league the same shape: one player out, picks and prospects back, 35 times in 35.
        A same-position swap refills both holes by construction — the seller gives a
        quarterback and receives a quarterback — so there is no free agent to sign, no
        prospect to promote, and no cut fee to pay. `docs/TRADING_PLAN.md` §5 lists
        "position-for-position" FIRST in its legality table for exactly that reason.

        ⚠️ AND IT IS HOW THE TIME TRADE BECOMES VISIBLE. QB-for-QB is the plan's example of
        a trade where "rating barely enters and `seasonsOfControl` does" — a rebuilder
        gives up now for term and a contender term for now. With picks as the only
        currency that trade cannot be expressed at all.

        ⚠️ ONLY AT THE LISTING'S POSITION, and `_assemble` takes at most ONE. Two would
        empty the position; a different position would open a hole the seller cannot fill.
        """
        out = []
        # ⚠️ PRICED ON WHOEVER IS BEING ASKED TO VALUE THEM, and for a FUTURE asset that
        # is `laterWeight` — the inverse of the now-weight. A contender parting with a
        # pick gives up something IT prices low; the rebuilder receiving it prices the
        # same pick high. That gap is the entire reason the two trade, and pricing both
        # sides at the holder's now-weight cancels it.
        valuer = valuingTeam if valuingTeam is not None else team
        weight = trading.laterWeight(self.nowWeight(valuer))
        for pick in self.picksOwnedBy(team):
            out.append({
                'kind': 'pick',
                'id': pick['id'],
                'name': f"S{pick['season']} R{pick['round']} pick",
                'detail': pick,
                'value': trading.pickValue(
                    pick['slot'], pick['season'] - self.season,
                    pick['classSize'], weight=weight),
            })
        for prospect in getattr(team, 'prospects', None) or []:
            if wasAcquiredThisSeason(prospect, self.season):
                continue        # pass-the-parcel, one asset class down
            ceiling = self._believedCeiling(team, prospect)
            out.append({
                'kind': 'prospect',
                'id': getattr(prospect, 'id', None),
                'name': getattr(prospect, 'name', '?'),
                'detail': {'prospectSeasons': getattr(prospect, 'prospect_seasons', 0)},
                'value': trading.prospectValue(
                    ceiling, getattr(prospect, 'prospect_seasons', 0), weight=weight,
                    positionWeight=self._positionWeight(prospect)),
            })
        if swapPosition is not None:
            # ⚠️ PRESENT VALUE, so `nowWeight` rather than `laterWeight` — a starter plays
            # this season. That is what makes a contender price an incoming rental high
            # and a rebuilder price the same man low, and it is the whole reason a
            # same-position swap of two similar players is ever worth making.
            nowW = self.nowWeight(valuer)
            roster = getattr(team, 'rosterDict', None) or {}
            for slot in POSITION_SLOTS.get(swapPosition, []):
                held = roster.get(slot)
                if held is None or getattr(held, 'willRetire', False):
                    continue
                if wasAcquiredThisSeason(held, self.season):
                    continue
                out.append({
                    'kind': 'player',
                    'id': getattr(held, 'id', None),
                    'name': getattr(held, 'name', '?'),
                    'detail': {'slot': slot},
                    'value': trading.playerValue(
                        getattr(held, 'playerRating', 0),
                        getattr(held, 'termRemaining', 0), self.week, nowW,
                        self._positionWeight(held)),
                })
        return out

    def _believedCeiling(self, team, prospect) -> float:
        try:
            return float(self.brain._ceilingRating(prospect, team))
        except Exception:
            return float(getattr(prospect, 'playerRating', 0) or 0)

    def picksOwnedBy(self, team) -> list:
        """Picks this club currently owns, within the tradeable horizon.

        ⚠️ THE SLOT COMES FROM THE ORIGINAL TEAM'S STANDING, NOT THE OWNER'S — which is
        what makes "trade your pick, finish worst, and the receiver gets #1" true. The
        plausible wrong implementation gives the receiver its own slot, which is a
        different and much duller feature.
        """
        from database.connection import get_session
        from database.models import DraftPick
        teamId = getattr(team, 'id', None)
        if teamId is None:
            return []
        order = self._draftOrderPositions()
        classSize = len(getattr(self.teamManager, 'teams', None) or []) or 32
        session = get_session()
        try:
            rows = session.query(DraftPick).filter(
                DraftPick.current_owner_id == teamId,
                DraftPick.used == False,                      # noqa: E712
                DraftPick.season >= self.season,
                DraftPick.season <= self.season + TRADE_PICK_HORIZON_SEASONS,
            ).all()
            return [{
                'id': r.id, 'season': r.season, 'round': r.round_number,
                'originalTeamId': r.original_team_id,
                'slot': order.get(r.original_team_id, classSize),
                'classSize': classSize,
            } for r in rows]
        except Exception as e:
            logger.warning(f"Could not read picks for {getattr(team, 'name', '?')}: {e}")
            return []
        finally:
            session.close()

    def _draftOrderPositions(self) -> dict:
        """{teamId: slot}, worst record first — the order the draft will use."""
        teams = list(getattr(self.teamManager, 'teams', None) or [])
        ranked = sorted(teams, key=lambda t: self._contention.get(getattr(t, 'id', None), 0.5))
        return {getattr(t, 'id', None): i + 1 for i, t in enumerate(ranked)}

    # -------------------------------------------------------- settlement

    def settle(self, listing, bids: list):
        """The lister takes the HIGHEST bid above its reserve; the rest lapse.

        ⚠️ AN AUCTION RATHER THAN FIRST-COME, because sixteen contenders will want the same
        rental and the auction turns competition into a PRICE instead of a race.

        ⚠️ NO SECOND ROUND WITHIN A WEEK, AND NO RULE IS NEEDED TO PREVENT ONE. A sealed
        round where each buyer bids its private value is already optimal discovery. An
        ASCENDING second round is WORSE FOR THE SELLER: the winner only has to top the
        runner-up, so the seller captures the second-best valuation instead of the best.
        "Let me shop this around" feels like leverage and is a discount.
        """
        clearing = [b for b in bids if b is not None and b.value >= listing.floor]
        if not clearing:
            return None
        return max(clearing, key=lambda b: b.value)


def runWeeklyPass(playerManager, teamManager, brain, season: int, week=None) -> list:
    """One pass of the market. Returns the settled trades as manifests.

    ⚠️ SETTLED SEQUENTIALLY, RE-VALIDATING EACH REMAINING ACCEPTED TRADE AGAINST THE NEW
    STATE. Within one pass trades interact: a club may promote a prospect to cover a sale
    and that prospect may himself be the asset another club is buying, two accepted trades
    can target the same roster slot, and A -> B -> A dependencies are possible. Cheaper
    than a batch solver and it matches how the FA draft already runs one pick at a time.
    """
    if not TRADING_ENABLED:
        return []
    if week is not None and int(week) > int(GM_ACTIVE_WEEK):
        return []               # rosters are frozen from the deadline to the offseason

    market = TradeMarket(playerManager, teamManager, brain, season, week)
    settled = []
    bidsUsed = {}

    for team in list(getattr(teamManager, 'teams', None) or []):
        for listing in market.listingsFor(team):
            # ⚠️ RE-CHECK LEGALITY AT SETTLEMENT, not at listing time. An earlier trade in
            # this same pass may have taken the backfill this one was counting on.
            if not _stillListable(listing):
                continue
            bids = []
            for buyer in market.counterpartiesFor(listing):
                if bidsUsed.get(getattr(buyer, 'id', None), 0) >= TRADE_BIDS_PER_TEAM_PER_WEEK:
                    continue
                bid = market.bidFor(listing, buyer)
                if bid is not None:
                    bids.append(bid)
            winner = market.settle(listing, bids)
            if winner is None:
                continue
            bidsUsed[getattr(winner.team, 'id', None)] = \
                bidsUsed.get(getattr(winner.team, 'id', None), 0) + 1
            settled.append({
                'listing': listing,
                'winner': winner,
            })

    # ── trading UP the draft: offseason only ─────────────────────────────────
    # ⚠️ RUN BEFORE THE PLAYER INQUIRIES so a club that moves up has spent its picks before
    # it starts shopping for bodies with them. The other order lets it promise the same
    # pick to two different deals in one pass.
    if week is None:
        for buyer in list(getattr(teamManager, 'teams', None) or []):
            if bidsUsed.get(getattr(buyer, 'id', None), 0) >= TRADE_BIDS_PER_TEAM_PER_WEEK:
                continue
            for listing in market.pickInquiriesFor(buyer):
                bid = market.bidForPick(listing, buyer)
                if bid is None:
                    continue
                winner = market.settle(listing, [bid])
                if winner is None:
                    continue
                bidsUsed[getattr(buyer, 'id', None)] = \
                    bidsUsed.get(getattr(buyer, 'id', None), 0) + 1
                settled.append({'listing': listing, 'winner': winner, 'kind': 'pick'})
                break

    # ── the blockbuster: buyer-initiated, offseason only ─────────────────────
    # ⚠️ NOT AN AUCTION. A club posting a player wants the best offer in the league, so
    # `counterpartiesFor` canvasses several. An inquiry is one club phoning another about a
    # man nobody put on the block, so ONLY THE CALLER BIDS — canvassing here would turn a
    # private approach into an auction the holder never asked for, and would let a third
    # club win a player the buyer went and found.
    for buyer in list(getattr(teamManager, 'teams', None) or []):
        if bidsUsed.get(getattr(buyer, 'id', None), 0) >= TRADE_BIDS_PER_TEAM_PER_WEEK:
            continue
        for inquiry in market.inquiriesFor(buyer):
            if not _stillListable(inquiry):
                continue
            # ⚠️ Re-checked inside the loop, not only above it: a club is allowed one
            # acquisition a pass, and the first inquiry may already have used it.
            if bidsUsed.get(getattr(buyer, 'id', None), 0) >= TRADE_BIDS_PER_TEAM_PER_WEEK:
                break
            bid = market.bidFor(inquiry, buyer)
            if bid is None:
                continue
            winner = market.settle(inquiry, [bid])
            if winner is None:
                continue
            bidsUsed[getattr(buyer, 'id', None)] = \
                bidsUsed.get(getattr(buyer, 'id', None), 0) + 1
            settled.append({'listing': inquiry, 'winner': winner})
    return settled


def settlePickTrade(seasonManager, listing, winner, season: int) -> dict:
    """Execute a trade-up. Returns the manifest, or None.

    ⚠️ DELIBERATELY SHORT, AND THAT IS THE WHOLE ARGUMENT FOR A SEPARATE PATH. Nobody is
    displaced, nothing is cut, no slot is backfilled and no card is minted — the pick moves
    and the bundle moves. `settleTrade`'s ordering comments are all about roster
    consistency, none of which applies, and threading "is this a pick?" through it would
    put a branch in every one of those steps.
    """
    from database.connection import get_session
    from database.models import DraftPick

    seller, buyer = listing.team, winner.team
    pickId = listing.pick.get('id')

    # ⚠️ RE-CHECK OWNERSHIP AT SETTLEMENT. An earlier trade in this same pass may already
    # have moved it — the pass settles sequentially for exactly this reason.
    session = get_session()
    try:
        row = session.get(DraftPick, pickId)
        if row is None or row.used or row.current_owner_id != getattr(seller, 'id', None):
            return None
        row.current_owner_id = getattr(buyer, 'id', None)
        session.commit()
    except Exception as e:
        logger.warning(f"Pick trade failed: {e}")
        try:
            session.rollback()
        except Exception:
            pass
        return None
    finally:
        session.close()

    given = _handOverPieces(seasonManager, winner.pieces, buyer, seller, season,
                            sellerSlot=None, phase='offseason')

    manifest = {
        'season': season, 'week': 0, 'phase': 'offseason',
        'teamAId': getattr(seller, 'id', None), 'teamBId': getattr(buyer, 'id', None),
        'teamAName': seller.name, 'teamBName': buyer.name,
        'aGave': [{'kind': 'pick', 'id': pickId,
                   'name': f"S{listing.pick['season']} R{listing.pick['round']} pick",
                   'detail': f"slot {listing.pick['slot']}"}],
        'bGave': given,
        'price': winner.value,
        # ⚠️ `_persistTrade` READS `reserve`, and a manifest missing it fails INSIDE its own
        # try/except — which logs a warning and returns 0, so the trade half-happens: the
        # pick has already moved and no `trades` row records it. Every key that function
        # touches has to be present.
        'reserve': listing.floor,
        'trigger': 'pick_swap',
        # ⚠️ BOTH SIDES OF THE CONVERSATION. The trigger is the SELLER's reason and was
        # all the ledger ever carried, so a trade read as half an exchange: a club moves a
        # man for a locker-room problem and nothing says why anyone wanted him.
        'sellerWhy': getattr(listing, 'why', None),
        'buyerWhy': getattr(winner, 'why', None),
    }
    tradeId = _persistTrade(manifest)
    _recordTrade(seasonManager, manifest, tradeId)
    _publishTrade(seasonManager, manifest)
    logger.info(f"TRADE UP: {buyer.name} moved up to S{listing.pick['season']} "
                f"slot {listing.pick['slot']} from {seller.name}")
    return manifest


def _stillListable(listing) -> bool:
    """Is this listing's player still where the listing says he is?"""
    team = listing.team
    roster = getattr(team, 'rosterDict', None) or {}
    return any(p is listing.player for p in roster.values())


# ============================================================================
# SETTLEMENT
# ============================================================================

def settleTrade(seasonManager, listing, winner, season: int, week=None) -> dict:
    """Execute one accepted trade, in order. Returns the manifest, or None.

    The order is not arbitrary — each step depends on the one before:

      1. verify both rosters CAN be complete
      2. move the assets, stamping `previousTeam`
      3. backfill the seller's hole
      4. re-scope the traded player's fan sentiment
      5. mint his card at his new club
      6. publish, and write the recap rows

    ⚠️ STEP 1 IS NOT OPTIONAL AND NEVER RELIES ON THE ENGINE TOLERATING `None`. An empty
    roster slot rates 50 — worse than any free agent — so a trade that cannot be backfilled
    is a trade that must not happen.
    """
    seller, buyer = listing.team, winner.team
    player = listing.player
    slot = _slotOf(seller, player)
    if slot is None:
        return None

    # ⚠️ A SAME-POSITION SWAP REFILLS BOTH HOLES BY CONSTRUCTION, so it needs neither a
    # backfill nor a cut nor a fee — the seller gives a quarterback and receives a
    # quarterback. Every other shape needs both halves arranged separately.
    swap = _swapPieceOf(winner.pieces, buyer, player)

    if swap is None:
        backfill = _findBackfill(seasonManager, seller, player, week=week)
        if backfill is None and week is not None:
            # ⚠️ IN-SEASON ONLY. The seller would be left with a hole and there is no
            # signing path to close it, so declining is correct; the listing goes unsold
            # this week and is re-derived next week. In the OFFSEASON a hole is fine —
            # `_processFreeAgency` fills every empty slot and both trade passes run before
            # it, so refusing there would refuse a trade over a problem that resolves
            # itself a few steps later.
            logger.info(f"Trade declined: {seller.name} cannot backfill {player.name}")
            return None
        buyerSlot = _openSlotFor(buyer, player)
        if buyerSlot is None:
            # ⚠️ WITHOUT CUT-TO-MAKE-ROOM THERE IS NO DEMAND SIDE AT ALL. Every roster is
            # complete by construction — six position-locked slots, no bench — so a buyer
            # NEVER has an open slot, and a settlement that requires one shuts every
            # contender out of the market. Measured before this existed: 728 listings and
            # 709 clearing bids across a season, and ZERO trades.
            buyerSlot = _cutToMakeRoom(seasonManager, buyer, player, week=week)
            if buyerSlot is None:
                return None
    else:
        backfill = None
        buyerSlot = _slotOf(buyer, swap)
        if buyerSlot is None:
            return None         # he moved since the bid was priced

    # ---- 2. move ----------------------------------------------------------
    # ⚠️ RESOLVE EVERY OUTGOING PLAYER BEFORE ANY SLOT IS WRITTEN. The move below puts the
    # incoming player into `buyerSlot`, which in a same-position swap is the slot the swap
    # player is standing in — so by the time `_handOverPieces` ran its own
    # `_findRostered(buyer, ...)` the man it was looking for had already been overwritten
    # out of the roster dict. It found None, did nothing, and returned quietly: the seller
    # kept the hole from giving up his own starter, the swap player ended up on NEITHER
    # roster, and `player.team` pointed at a club with no slot holding him. Measured over
    # two seasons, that was 216 games crashing at kickoff on a None in `rosterDict` —
    # caught by `_simulateGame`'s except, so the league played on around the wreckage.
    resolved = {}
    for piece in winner.pieces:
        if piece.get('kind') == 'player':
            held = _findRostered(buyer, piece.get('id'))
            if held is not None:
                resolved[piece.get('id')] = held

    seller.rosterDict[slot] = None
    player.previousTeam = seller.name
    player.team = buyer
    # ⚠️ RESETS ON A TRADE. The limit is about ONE CLUB re-signing the same player
    # repeatedly, and the new club has re-signed him zero times. (Currently inert anyway —
    # `RESIGN_ONCE_ENABLED` is False.)
    player.teamResignCount = 0
    buyer.rosterDict[buyerSlot] = player
    _stampAcquired(player, season, phase='season' if week is not None else 'offseason')
    try:
        buyer.assignPlayerNumber(player)
    except Exception:
        pass

    given = _handOverPieces(seasonManager, winner.pieces, buyer, seller, season,
                            sellerSlot=slot, resolved=resolved,
                            phase='season' if week is not None else 'offseason')

    # ---- 3. backfill ------------------------------------------------------
    # ⚠️ Only when nobody came back the other way. A swap already filled the slot.
    if backfill is not None:
        _installBackfill(seasonManager, seller, slot, backfill)

    # ---- 4. sentiment -----------------------------------------------------
    # ⚠️ NOTHING IS DELETED. "His sentiment does not follow him" is expressed by scoping
    # the AGGREGATE to the current club's fans (`SentimentRepository._ownClubRatings`),
    # which needs no action here at all — the rows are things real users wrote, and traded
    # back, his old ratings correctly reactivate.

    # ---- 5. his card at the new club -------------------------------------
    _mintTradedCard(seasonManager, player, buyer, season)

    manifest = {
        'season': season,
        'week': int(week or 0),
        'phase': 'in_season' if week is not None else 'offseason',
        'teamAId': getattr(seller, 'id', None),
        'teamBId': getattr(buyer, 'id', None),
        'teamAName': seller.name,
        'teamBName': buyer.name,
        'aGave': [{'kind': 'player', 'id': getattr(player, 'id', None),
                   'name': player.name, 'detail': player.position.name}],
        'bGave': given,
        'price': winner.value,
        'reserve': listing.floor,
        'trigger': listing.trigger,
        # ⚠️ BOTH SIDES OF THE CONVERSATION. The trigger is the SELLER's reason and was
        # all the ledger ever carried, so a trade read as half an exchange: a club moves a
        # man for a locker-room problem and nothing says why anyone wanted him.
        'sellerWhy': getattr(listing, 'why', None),
        'buyerWhy': getattr(winner, 'why', None),
    }
    tradeId = _persistTrade(manifest)
    manifest['tradeId'] = tradeId
    _recordTrade(seasonManager, manifest, tradeId)
    _publishTrade(seasonManager, manifest)
    return manifest


def _stampAcquired(player, season: int, asPiece: bool = False,
                   phase: str = 'season') -> None:
    """Mark that this club got him in a trade THIS season.

    ⚠️ `asPiece` SEPARATES THE TWO WAYS A PLAYER ARRIVES, and the difference decides
    whether cutting him wastes anything (owner, 2026-09-16). The HEADLINE player is the man
    a club went out and bought. A PIECE is the roster player a seller took back inside a
    bundle whose real return was picks and prospects — "the roster player was just someone
    to fill a gap" — and moving on from him later wastes nothing, because he was never what
    the trade was for.

    ⚠️ IN MEMORY ONLY, DELIBERATELY. The rule it feeds is a within-season one and the
    stamp is worthless the moment the season turns, so persisting it would add a column
    whose only job is to be ignored. A restart clears it, which fails in the permissive
    direction: the worst case is one extra legal-looking move, not a lost player.
    """
    try:
        player._tradedInSeason = int(season or 0)
        player._acquiredAsPiece = bool(asPiece)
        # ⚠️ THE PHASE, NOT JUST THE SEASON. "You may cut him next offseason" and "you may
        # cut him ten minutes later in the SAME offseason" are different rules, and a
        # season-only stamp cannot tell them apart — the offseason runs under the season
        # number it follows. Measured in the ledger: Strangers took a 76 TE from Pinecones
        # in a swap, then later in that SAME offseason bought a 77 TE from Midnights and
        # cut the 76 to make room, paying 450F. Net, they gave up a 77, two picks and the
        # fee to end up with a 77.
        player._acquiredInPhase = str(phase or 'season')
    except Exception:
        pass


def wasAcquiredThisSeason(player, season: int) -> bool:
    """⚠️ STOPS PASS-THE-PARCEL, and the ledger showed it happening. A club may not move a
    player it acquired this season — measured over six seasons, prospects were being
    flipped twice inside one season (Slippers -> Strangers in week 15 and Strangers ->
    Cranes in the same offseason), which turns an asset into a token being passed around
    rather than a player a club decided it wanted.

    ⚠️ It covers BUNDLE PIECES, not just the listed player. Every trade in the measured
    ledger paid in prospects and picks, so a rule that only guarded the headline player
    would have guarded the one asset class that was never being flipped.
    """
    stamped = getattr(player, '_tradedInSeason', None)
    return stamped is not None and int(stamped) == int(season or 0)


def wasHeadlineAcquisition(player, season: int, phase: str = None) -> bool:
    """Did this club go out and BUY him this season, as the point of the trade?

    ⚠️ NARROWER THAN `wasAcquiredThisSeason` ON PURPOSE — the two guard different rules and
    conflating them was the mistake. That one stops a player being passed around and must
    cover every bundle piece. This one stops a club treating an acquisition as disposable
    packaging, and a gap-filling piece is not that (owner, 2026-09-16: *"if the player
    received in the trade was just a gap fill piece on a selling team, then its not out of
    the question that they could be cut"*).
    """
    if not wasAcquiredThisSeason(player, season):
        return False
    if getattr(player, '_acquiredAsPiece', False):
        return False
    # ⚠️ SAME PHASE, NOT MERELY SAME SEASON. An in-season acquisition may be cut once the
    # offseason arrives (owner) — but a man acquired IN an offseason may not be cut later
    # in that same offseason, which is where the churn moved to when the exemption was
    # phase-blind.
    if phase is None:
        return True
    return str(getattr(player, '_acquiredInPhase', 'season')) == str(phase)


def _slotOf(team, player):
    for slot, rostered in (getattr(team, 'rosterDict', None) or {}).items():
        if rostered is player:
            return slot
    return None


def _openSlotFor(team, player):
    posValue = getattr(getattr(player, 'position', None), 'value', None)
    for slot in POSITION_SLOTS.get(posValue, []):
        if (getattr(team, 'rosterDict', None) or {}).get(slot) is None:
            return slot
    return None


def _cutToMakeRoom(seasonManager, buyer, incoming, week=None):
    """Cut the weakest incumbent at the incoming player's position. Returns the freed
    slot, or None.

    ⚠️ CUTTING A PLAYER WITH TERM LEFT COSTS TREASURY, and that is the SAFE use of a
    currency with a 227x spread across the league. Treasury was rejected as a trade ASSET
    precisely because that spread let the richest club fund the whole market; as a COST
    the same spread constrains the poor instead of empowering the rich — a club cannot buy
    a PLAYER with Treasury, only ROSTER SPACE, and the club that hoards talent pays to
    keep churning it.

    ⚠️ It reconnects the two economies deliberately: Treasury's other claim is facility
    upkeep, and `resolveSeasonEnd` spends it at season end. A club that cuts freely
    in-season loses a facility level in the offseason. No extra rule needed.

    ⚠️ AND A CLUB THAT CANNOT PAY CANNOT CUT — floored at zero, never a debt, because a
    broke club with a debt line has unlimited roster churn.

    A walk-year or retiring incumbent is free to cut: he is leaving anyway, so there is no
    control being thrown away and `cutFeeFor` prices him at nothing.
    """
    from managers.frontOfficeBrain import cutFeeFor
    posValue = getattr(getattr(incoming, 'position', None), 'value', None)
    worstSlot, worst, worstRating = None, None, None
    for slot in POSITION_SLOTS.get(posValue, []):
        incumbent = (getattr(buyer, 'rosterDict', None) or {}).get(slot)
        if incumbent is None:
            return slot
        rating = float(getattr(incumbent, 'playerRating', 0) or 0)
        if worstRating is None or rating < worstRating:
            worstSlot, worst, worstRating = slot, incumbent, rating
    if worst is None:
        return None
    # ⚠️ YOU MAY NOT CUT, IN-SEASON, A MAN YOU WENT OUT AND BOUGHT THIS SEASON (owner,
    # 2026-09-15: "a team trading for a player and then cutting them immediately ... it was
    # just a waste of assets and no real team would do that"). Reported from the ledger:
    # Phones traded for a quarterback, then a week later traded for a second and CUT the
    # first to make room.
    #
    # ⚠️ TWO CARVE-OUTS, BOTH OWNER-SPECIFIED, AND A SEASON-LONG BAN GOT BOTH WRONG:
    #
    #   * THE OFFSEASON IS EXEMPT — "players that were signed to fill gaps during the
    #     season can be cut in the offseason ... to make way for a better player". The
    #     offseason runs under the SAME season number, so a season-matched stamp silently
    #     protected every in-season acquisition right through it. And the blockbuster path
    #     is offseason-only and needs `_cutToMakeRoom` to make room, so the ban was
    #     throttling the one feature built to produce a star trade.
    #   * A BUNDLE PIECE IS EXEMPT — "the seller got a roster player in return for sending
    #     out a star player, but theyd also would have had to get prospects or picks, which
    #     was the real return and the roster player was just someone to fill a gap". He was
    #     never the point of the trade, so moving on from him wastes nothing.
    #
    # ⚠️ IT REFUSES RATHER THAN LOOKING FURTHER. There is at most one other slot at any
    # position (only WR has two), so "cut somebody else instead" is nearly always no option
    # at all — and where it is one, the club is discarding a BETTER incumbent to protect a
    # man it just bought, which is not an improvement on the thing being prevented.
    phase = 'season' if week is not None else 'offseason'
    if wasHeadlineAcquisition(worst, getattr(
            getattr(seasonManager, 'currentSeason', None), 'seasonNumber', 0), phase):
        logger.info(f"Trade declined: {buyer.name} would have to cut "
                    f"{worst.name}, bought in this same {phase}")
        return None
    # ⚠️ NO SECOND UPGRADE TEST HERE. `bidFor` already established that the incoming
    # player beats this exact man — on the buyer's own BELIEVED, position-weighted read —
    # and re-deriving it from raw rating is two copies of one rule that disagree. They
    # did: the bid used the brain's value and this used `playerRating`, and settlement
    # refused 35 of 38 accepted trades that the market had correctly cleared. The only
    # thing left to check here is whether the club can pay.
    fee = cutFeeFor(worst)
    if not seasonManager._chargeCutFee(buyer, fee):
        return None
    try:
        seasonManager.playerManager.releasePlayerToFreeAgency(worst, buyer, {})
        worst.teamResignCount = 0
    except Exception as e:
        logger.warning(f"Could not release {getattr(worst, 'name', '?')}: {e}")
        return None
    logger.info(f"{buyer.name} cut {worst.name} ({fee}F) to make room for {incoming.name}")
    return worstSlot


def _isTrulyUnrostered(player) -> bool:
    """Is this "free agent" actually free?

    ⚠️ `playerManager.freeAgents` IS NOT ALWAYS CLEAN, AND TRUSTING IT PUT PLAYERS ON TWO
    ROSTERS AT ONCE. On a fresh league every one of the 192 rostered players is ALSO in
    that list until `_validateRosterIntegrity` runs in the offseason — measured, 192 of
    192 at season 1 week 1 — so a backfill search would happily sign a man who is somebody
    else's starter, leaving him in two `rosterDict`s with a `.team` pointing at whichever
    was written last. Five such players survived into season 2 before this check existed.

    ⚠️ The test is `.team`, NOT membership in the pool, because the pool is the thing that
    is wrong. Every release path — `releasePlayerToFreeAgency`, contract expiry,
    `_advanceProspectWindow` — stamps the literal string `'Free Agent'`, while a rostered
    player carries the Team OBJECT. `_validateRosterIntegrity` exists because this drift
    is a known hazard; trading must not rely on it having run.
    """
    team = getattr(player, 'team', None)
    return team is None or isinstance(team, str)


def _findBackfill(seasonManager, team, player, week=None):
    """Who replaces him — a ready prospect, else the best signable free agent.

    ⚠️ `max(readyProspect, bestAvailableFreeAgent)`, and mid-season free-agent signing is
    what makes player-for-picks available to EVERY club rather than only to those with a
    pipeline. A signing is available when a slot is EMPTY — after a trade, and nowhere
    else. Letting clubs sign over a filled slot would be a second, continuous free-agency
    market and would undo the position-lock logic the rest of this rests on.

    ⚠️ AND IT IS MID-SEASON ONLY, WHICH THE DOCSTRING ABOVE ASSERTED AND NOTHING ENFORCED
    (owner, 2026-09-15: *"teams are signing free agents as part of the trade ... this
    shouldnt be happening in the offseason if its before the free agent draft"*). Both
    offseason passes run BEFORE `_processFreeAgency`, so a club selling a starter was
    reaching into the pool and helping itself to the best man in it — ahead of the
    worst-first draft whose entire purpose is to decide who gets him. A contender could
    sell a player and sign a better free agent than the club picking first ever saw.

    ⚠️ IN THE OFFSEASON THE SELLER SIMPLY LEAVES THE HOLE. That is not a compromise, it is
    what the FA draft is for: `_processFreeAgency` fills every empty slot in order, and
    both trade passes precede it. So the offseason needs no backfill at all, and refusing
    the trade for want of one was refusing it for a problem that resolves itself.
    """
    posValue = getattr(getattr(player, 'position', None), 'value', None)
    best, bestRating = None, -1.0
    for prospect in getattr(team, 'prospects', None) or []:
        if getattr(getattr(prospect, 'position', None), 'value', None) != posValue:
            continue
        rating = float(getattr(prospect, 'playerRating', 0) or 0)
        if rating > bestRating:
            best, bestRating = ('prospect', prospect), rating
    if week is None:
        # ⚠️ NOTHING AT ALL IN THE OFFSEASON — not a signing, and not a promotion either
        # (owner, 2026-09-16: "positions slots on the roster that are emptied due to a
        # trade dont need to be filled right away, because the FA draft is coming up. the
        # team can decide to promote their prospects during that draft, or sign a better FA
        # even if it blocks their prospect"). Promoting on the spot pre-empts that choice
        # and measurably made it badly: Midnights sold a 77 TE and installed its own 62.
        # `playerManager._attemptRosterFill` already picks the best player available across
        # the pool AND the pipeline, which is exactly the decision being deferred to.
        return None
    pm = seasonManager.playerManager
    for fa in getattr(pm, 'freeAgents', None) or []:
        if getattr(fa, 'willRetire', False):
            continue
        if not _isTrulyUnrostered(fa):
            continue            # somebody's starter, wrongly left in the pool
        if getattr(getattr(fa, 'position', None), 'value', None) != posValue:
            continue
        rating = float(getattr(fa, 'playerRating', 0) or 0)
        if rating > bestRating:
            best, bestRating = ('freeAgent', fa), rating
    return best


def _installBackfill(seasonManager, team, slot, backfill) -> None:
    """Put the replacement in the vacated slot.

    ⚠️ THE PROMOTION BAR DROPS TO NEAR ZERO IN-SEASON, and this is the second of the three
    places the same structural error appears. `_promoteProspectsAutonomously` promotes only
    when the prospect beats the FREE AGENT the club could sign — correct in the offseason,
    where signing is a real alternative. MID-SEASON THERE IS NO OFFSEASON SIGNING PATH AT
    ALL, so the real alternative is an EMPTY SLOT RATING 50, and the bar has to reflect
    that. Here the comparison has already been made in `_findBackfill`, which simply takes
    the better of the two available bodies.
    """
    from constants import TRADE_MIDSEASON_SIGNING_TERM
    kind, person = backfill
    if kind == 'prospect':
        person.is_prospect = False
        person.prospect_seasons = 0
        person.drafting_team_id = None
        person.team = team
        if person in (getattr(team, 'prospects', None) or []):
            team.prospects.remove(person)
        try:
            person.term = seasonManager.playerManager._getPlayerTerm(person)
            person.termRemaining = person.term
        except Exception:
            person.termRemaining = 1
    else:
        pm = seasonManager.playerManager
        if person in getattr(pm, 'freeAgents', []):
            pm.freeAgents.remove(person)
        person.team = team
        person.freeAgentYears = 0
        # ⚠️ A MID-SEASON SIGNING RUNS TO THE END OF THIS SEASON, OR ONE MORE — never a
        # full `_getPlayerTerm` deal. Anything longer makes hole-filling a cheap way to
        # ACQUIRE TERM: a club could trade a player away in week 15 and sign a three-year
        # replacement, converting a roster hole into an asset.
        person.term = int(TRADE_MIDSEASON_SIGNING_TERM)
        person.termRemaining = person.term
    team.rosterDict[slot] = person
    # ⚠️ DELIBERATELY NOT STAMPED `wasAcquiredThisSeason`. Signing a free agent and trading
    # him on is legitimate if somebody wants him (owner, 2026-09-15: "I dont think its an
    # issue for teams to sign a free agent and then trade them again if here's a willing
    # partner"). The churn that WAS wrong is on the other side of that deal — a club
    # acquiring a player and cutting him immediately to make room for the next one — and
    # that is guarded in `_cutToMakeRoom`, not here. Stamping the signing was tried and
    # reverted: it blocks the honest half of the loop and leaves the dishonest half intact.
    try:
        team.assignPlayerNumber(person)
    except Exception:
        pass


def _handOverPieces(seasonManager, pieces, fromTeam, toTeam, season: int = 0,
                    sellerSlot=None, resolved=None, phase: str = 'season') -> list:
    """Move the bought side of the bundle — picks change owner, prospects change pipeline."""
    from database.connection import get_session
    from database.models import DraftPick
    given = []
    session = get_session()
    try:
        for piece in pieces:
            if piece['kind'] == 'pick':
                row = session.get(DraftPick, piece['id'])
                if row is not None:
                    # ⚠️ ONLY THE OWNER MOVES. `original_team_id` is what resolves the
                    # SLOT, so rewriting it here would hand the receiver the buyer's own
                    # draft position instead of the seller's — the duller feature.
                    row.current_owner_id = getattr(toTeam, 'id', None)
            elif piece['kind'] == 'player':
                # ⚠️ STRAIGHT INTO THE SLOT THE LISTED PLAYER JUST LEFT. Same position, so
                # it is the same slot kind — which is precisely why this shape needs no
                # backfill and no cut.
                # ⚠️ `resolved` is read FIRST and the lookup is only a fallback — see the
                # note at the resolve site. The caller has already written the incoming
                # player into this man's slot, so the lookup cannot find him.
                swapped = (resolved or {}).get(piece['id'])
                if swapped is None:
                    swapped = _findRostered(fromTeam, piece['id'])
                if swapped is not None:
                    # ⚠️ Only clears a slot he is STILL standing in. In a swap the
                    # caller has already replaced him, so this finds nothing — and must
                    # not, or it would blank the slot the incoming player now holds.
                    for sl, held in list((getattr(fromTeam, 'rosterDict', None) or {}).items()):
                        if held is swapped:
                            fromTeam.rosterDict[sl] = None
                    swapped.previousTeam = fromTeam.name
                    swapped.team = toTeam
                    swapped.teamResignCount = 0
                    if sellerSlot is not None:
                        toTeam.rosterDict[sellerSlot] = swapped
                    _stampAcquired(swapped, season, asPiece=True, phase=phase)
                    try:
                        toTeam.assignPlayerNumber(swapped)
                    except Exception:
                        pass
            elif piece['kind'] == 'prospect':
                prospect = _findProspect(fromTeam, piece['id'])
                if prospect is not None:
                    _stampAcquired(prospect, season, asPiece=True, phase=phase)
                if prospect is None:
                    logger.warning(
                        f"TRADE PIECE MISSING: {fromTeam.name} does not hold prospect "
                        f"{piece['id']} ({piece.get('name')}) — recorded but not moved")
                if prospect is not None:
                    fromTeam.prospects.remove(prospect)
                    if not hasattr(toTeam, 'prospects') or toTeam.prospects is None:
                        toTeam.prospects = []
                    toTeam.prospects.append(prospect)
                    prospect.drafting_team_id = getattr(toTeam, 'id', None)
                    # ⚠️ `prospect_seasons` TRAVELS WITH HIM — deliberately not reset. The
                    # window is a DEADLINE, so a distressed prospect is worth buying only
                    # if you have the slot the seller does not, and passing him around
                    # cannot refresh the clock.
            given.append({k: piece[k] for k in ('kind', 'id', 'name')})
        session.commit()
    except Exception as e:
        logger.warning(f"Trade piece hand-over failed: {e}")
        try:
            session.rollback()
        except Exception:
            pass
    finally:
        session.close()
    return given


def _swapPieceOf(pieces, buyer, incoming):
    """The buyer's own starter in this bundle, if it is paying with one.

    ⚠️ MUST BE AT THE INCOMING PLAYER'S POSITION, re-checked here rather than trusted from
    the bid. A bundle priced a week ago against a different roster is exactly the kind of
    thing settlement is supposed to re-validate.
    """
    wanted = getattr(getattr(incoming, 'position', None), 'value', None)
    for piece in pieces:
        if piece.get('kind') != 'player':
            continue
        held = _findRostered(buyer, piece.get('id'))
        if held is None:
            continue
        if getattr(getattr(held, 'position', None), 'value', None) != wanted:
            continue
        return held
    return None


def _findRostered(team, playerId):
    for p in (getattr(team, 'rosterDict', None) or {}).values():
        if p is not None and getattr(p, 'id', None) == playerId:
            return p
    return None


def _findProspect(team, prospectId):
    for p in getattr(team, 'prospects', None) or []:
        if getattr(p, 'id', None) == prospectId:
            return p
    return None


def _mintTradedCard(seasonManager, player, team, season: int) -> None:
    """Mint this player a card in his NEW club's colours.

    ⚠️ TEMPLATES MINT ONCE PER SEASON AND RETURN EARLY (`generateSeasonTemplates` bails on
    `countBySeason > 0`), so this cannot ride the season-start path and needs its own.

    ✅ It also fixes the themed-pack drift: `card_templates.team_id` is frozen at mint, so
    without this a traded player would linger in his OLD club's team pack all season. The
    old card keeps the old club, which is correct — that card depicts him as he was.

    ⚠️ Two scoreable cards of one player then exist. That is FINE (owner): the equip
    handler enforces no duplicate PLAYER across slots, so both can be owned and collected
    and only one can ever be fielded. "His Bees card and his Pinecones card" is a
    collectible idea rather than an exploit.
    """
    try:
        from managers.cardManager import CardManager
        from database.connection import get_session
        session = get_session()
        try:
            CardManager(session).mintTradedPlayerCard(player, team, season)
            session.commit()
        finally:
            session.close()
    except AttributeError:
        # Not built yet — a missing card is cosmetic and must never block a trade.
        logger.info(f"Traded-card mint skipped for {player.name} (no mint path)")
    except Exception as e:
        logger.warning(f"Traded-card mint failed for {player.name}: {e}")


def _persistTrade(manifest) -> int:
    from database.connection import get_session
    from database.models import Trade
    session = get_session()
    try:
        row = Trade(season=manifest['season'], week=manifest['week'],
                    phase=manifest['phase'],
                    team_a_id=manifest['teamAId'], team_b_id=manifest['teamBId'],
                    assets_json={'aGave': manifest['aGave'], 'bGave': manifest['bGave']},
                    price=float(manifest['price']), reserve=float(manifest['reserve']))
        session.add(row)
        session.commit()
        return row.id
    except Exception as e:
        logger.warning(f"Could not persist trade: {e}")
        try:
            session.rollback()
        except Exception:
            pass
        return 0
    finally:
        session.close()


def _recordTrade(seasonManager, manifest, tradeId: int) -> None:
    """One recap row per side.

    ⚠️ BOTH CARRY THE TRADE ID. `SeasonRecapEvent`'s idempotency key is
    `(season, event_type, player_id|team_id)` — one player, one club — which a two-sided
    trade does not fit, so without it the resume dedupe silently drops half of every swap.
    """
    for side, other in (('teamA', 'teamB'), ('teamB', 'teamA')):
        gave = manifest['aGave'] if side == 'teamA' else manifest['bGave']
        names = ', '.join(p['name'] for p in gave) or 'nothing'
        seasonManager._recordOffseasonEvent(
            'trade',
            teamId=manifest[f'{side}Id'], teamName=manifest[f'{side}Name'],
            detail=f"sent {names} to {manifest[f'{other}Name']}",
            tradeId=tradeId)


def _publishTrade(seasonManager, manifest) -> None:
    """League news. ⚠️ `league_news.publish` IS KEYWORD-ONLY AND camelCase, and a
    snake_case typo has caused two incidents, one of them a production outage —
    `test_publish_kwargs.py` sweeps every call site against the live signature."""
    try:
        import league_news
        from database.connection import get_session
        aNames = ', '.join(p['name'] for p in manifest['aGave']) or 'nothing'
        bNames = ', '.join(p['name'] for p in manifest['bGave']) or 'nothing'
        text = (f"{manifest['teamAName']} send {aNames} to {manifest['teamBName']} "
                f"for {bNames}")
        league_news.publishSafe(
            get_session,
            season=manifest['season'],
            week=manifest['week'],
            category='trade',
            text=text,
            eventType='trade',
            teamId=manifest['teamAId'],
        )
    except Exception as e:
        logger.warning(f"Could not publish trade news: {e}")
