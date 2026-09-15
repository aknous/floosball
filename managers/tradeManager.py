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
                       TRADE_MIN_CERTAINTY)

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
}


class Listing:
    """One asset on the block, with the ask and the walk-away that price it."""

    def __init__(self, team, player, trigger, ask, floor):
        self.team = team
        self.player = player
        self.trigger = trigger
        self.ask = ask
        self.floor = floor

    def __repr__(self):
        return (f"<Listing {self.team.name}: {self.player.name} "
                f"({self.trigger}, ask {self.ask:.1f}, floor {self.floor:.1f})>")


class Bid:
    """What one club offers for one listing, and what it is worth to the SELLER."""

    def __init__(self, team, pieces, value):
        self.team = team
        self.pieces = pieces        # [{kind, id, name, detail, value}]
        self.value = value

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

    def nowWeight(self, team) -> float:
        return trading.nowWeight(self._contention.get(getattr(team, 'id', None), 0.5),
                                 self._leagueMean, self.week)

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

        for slot, player in roster.items():
            if player is None or getattr(player, 'willRetire', False):
                continue
            if wasAcquiredThisSeason(player, self.season):
                continue        # pass-the-parcel: he only just got here
            trigger = None
            term = int(getattr(player, 'termRemaining', 0) or 0)
            attitude = self._attitudeOf(player)

            if not contending and term <= 1:
                # ⚠️ THE ENGINE OF THE WHOLE MARKET. He leaves for nothing at season end;
                # anything at all beats that.
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
            if trigger is None:
                continue

            ask, floor = self._priceListing(team, player)
            if ask <= 0:
                continue
            out.append(Listing(team, player, trigger, ask, floor))

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

    def _priceListing(self, team, player):
        ask, floor = trading.askAndFloor(
            getattr(player, 'playerRating', 0),
            self._backfillRating(team, player),
            getattr(player, 'termRemaining', 0),
            self.week,
            self.nowWeight(team))
        return ask, floor

    def _backfillRating(self, team, player) -> float:
        """Who actually replaces him — `max(readyProspect, bestAvailableFreeAgent)`.

        ⚠️ THE QUALITY OF THE BACKFILL IS WHAT MAKES A CLUB A SELLER, because `floor < ask`
        requires `backfill > REPLACEMENT`. With mid-season signing every club can sell, but
        one with a good prospect sells far more readily than one drawing on the pool.
        """
        posValue = getattr(getattr(player, 'position', None), 'value', None)
        best = 0.0
        for prospect in getattr(team, 'prospects', None) or []:
            if getattr(getattr(prospect, 'position', None), 'value', None) == posValue:
                best = max(best, float(getattr(prospect, 'playerRating', 0) or 0))
        for fa in getattr(self.playerManager, 'freeAgents', None) or []:
            if getattr(fa, 'willRetire', False):
                continue
            # ⚠️ Same reason as `_findBackfill`: a rostered player left in the pool would
            # price the floor against a backfill the club cannot actually sign, and the
            # floor is what decides whether it is a seller at all.
            if not _isTrulyUnrostered(fa):
                continue
            if getattr(getattr(fa, 'position', None), 'value', None) == posValue:
                best = max(best, float(getattr(fa, 'playerRating', 0) or 0))
        return best

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

        # What he is worth TO THE BUYER, on the buyer's own read of him.
        try:
            seen = self.brain.perceivedValue(player, coach, team=buyer)
        except Exception:
            seen = float(getattr(player, 'playerRating', 0) or 0)
        # perceivedValue is position-weighted board currency; the trade scale is raw
        # surplus x time, so price him on the rating the buyer BELIEVES he has.
        believed = seen / max(0.01, self._positionWeight(player))
        gross = trading.playerValue(
            believed, getattr(player, 'termRemaining', 0), self.week, buyerWeight)
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
        displaced, fee = self._displacedBy(buyer, player)
        net = gross - displaced
        if net <= 0:
            return None             # he does not improve this roster
        # ⚠️ The cut fee is part of the price. A club that must pay 4,350F to open the slot
        # is buying something more expensive than the same player into an empty one.
        worthToBuyer = net

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
        pieces = self._assemble(buyer, listing.team, bar, worthToBuyer)
        if not pieces:
            return None
        return Bid(buyer, pieces, sum(p['value'] for p in pieces))

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
            rating = float(getattr(held, 'playerRating', 0) or 0)
            if weakestRating is None or rating < weakestRating:
                weakest, weakestRating = held, rating
        if weakest is None:
            return 0.0, 0
        value = trading.playerValue(weakestRating,
                                    getattr(weakest, 'termRemaining', 0),
                                    self.week, self.nowWeight(buyer))
        return value, cutFeeFor(weakest)

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

    def _assemble(self, buyer, seller, bar: float, gain: float) -> list:
        """The CHEAPEST combination of the buyer's assets that clears the SELLER's bar.

        ⚠️ CHEAPEST, NOT LARGEST, and capped at `TRADE_MAX_PIECES` so a trade reads as a
        sentence rather than a spreadsheet. A buyer that hands over everything it owns to
        clear a bar by four times is not negotiating.

        ⚠️ AND THE BUYER STILL HAS TO WANT TO. The bundle is sized against what the SELLER
        thinks it is worth, because that is the bar; the buyer then refuses if what it is
        giving up, ON ITS OWN SCALE, costs more than the upgrade is worth to it. A
        contender hands over picks cheaply BECAUSE it prices the future low, which is the
        trade working rather than a club being fleeced.
        """
        sellerValue = {a['id']: a['value']
                       for a in self._tradeableAssets(buyer, valuingTeam=seller)}
        buyerAssets = self._tradeableAssets(buyer, valuingTeam=buyer)
        # Cheapest FOR THE BUYER first, so it parts with what it minds least.
        buyerAssets.sort(key=lambda a: a['value'])
        pieces, toSeller, toBuyer = [], 0.0, 0.0
        for asset in buyerAssets:
            if toSeller >= bar:
                break
            if len(pieces) >= TRADE_MAX_PIECES:
                break
            worthToSeller = sellerValue.get(asset['id'], 0.0)
            if worthToSeller <= 0:
                continue
            pieces.append(dict(asset, value=worthToSeller))
            toSeller += worthToSeller
            toBuyer += asset['value']
        if toSeller < bar:
            return []
        if toBuyer > gain:
            return []           # it costs the buyer more than the upgrade is worth
        return pieces

    def _tradeableAssets(self, team, valuingTeam=None) -> list:
        """This club's picks and pipeline prospects, priced on the shared scale.

        ⚠️ ROSTER PLAYERS ARE DELIBERATELY NOT HERE. A club paying with a starter opens a
        hole that has to be legal at settlement, which is a different and much larger
        operation — the plan's player-for-player case is a LISTING on each side meeting in
        the middle, not a bundle piece. Picks and prospects are the currencies.
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
                    ceiling, getattr(prospect, 'prospect_seasons', 0), weight=weight),
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
    return settled


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
    backfill = _findBackfill(seasonManager, seller, player)
    if backfill is None:
        # ⚠️ The seller would be left with a hole. Declining is correct; the listing
        # simply goes unsold this week and is re-derived next week.
        logger.info(f"Trade declined: {seller.name} cannot backfill {player.name}")
        return None
    buyerSlot = _openSlotFor(buyer, player)
    if buyerSlot is None:
        # ⚠️ WITHOUT CUT-TO-MAKE-ROOM THERE IS NO DEMAND SIDE AT ALL. Every roster is
        # complete by construction — six position-locked slots, no bench — so a buyer
        # NEVER has an open slot, and a settlement that requires one shuts every
        # contender out of the market. Measured before this existed: 728 listings and 709
        # clearing bids across a season, and ZERO trades.
        buyerSlot = _cutToMakeRoom(seasonManager, buyer, player)
        if buyerSlot is None:
            return None

    # ---- 2. move ----------------------------------------------------------
    seller.rosterDict[slot] = None
    player.previousTeam = seller.name
    player.team = buyer
    # ⚠️ RESETS ON A TRADE. The limit is about ONE CLUB re-signing the same player
    # repeatedly, and the new club has re-signed him zero times. (Currently inert anyway —
    # `RESIGN_ONCE_ENABLED` is False.)
    player.teamResignCount = 0
    buyer.rosterDict[buyerSlot] = player
    _stampAcquired(player, season)
    try:
        buyer.assignPlayerNumber(player)
    except Exception:
        pass

    given = _handOverPieces(seasonManager, winner.pieces, buyer, seller, season)

    # ---- 3. backfill ------------------------------------------------------
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
    }
    tradeId = _persistTrade(manifest)
    manifest['tradeId'] = tradeId
    _recordTrade(seasonManager, manifest, tradeId)
    _publishTrade(seasonManager, manifest)
    return manifest


def _stampAcquired(player, season: int) -> None:
    """Mark that this club got him in a trade THIS season.

    ⚠️ IN MEMORY ONLY, DELIBERATELY. The rule it feeds is a within-season one and the
    stamp is worthless the moment the season turns, so persisting it would add a column
    whose only job is to be ignored. A restart clears it, which fails in the permissive
    direction: the worst case is one extra legal-looking move, not a lost player.
    """
    try:
        player._tradedInSeason = int(season or 0)
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


def _cutToMakeRoom(seasonManager, buyer, incoming):
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


def _findBackfill(seasonManager, team, player):
    """Who replaces him — a ready prospect, else the best signable free agent.

    ⚠️ `max(readyProspect, bestAvailableFreeAgent)`, and mid-season free-agent signing is
    what makes player-for-picks available to EVERY club rather than only to those with a
    pipeline. A signing is available when a slot is EMPTY — after a trade, and nowhere
    else. Letting clubs sign over a filled slot would be a second, continuous free-agency
    market and would undo the position-lock logic the rest of this rests on.
    """
    posValue = getattr(getattr(player, 'position', None), 'value', None)
    best, bestRating = None, -1.0
    for prospect in getattr(team, 'prospects', None) or []:
        if getattr(getattr(prospect, 'position', None), 'value', None) != posValue:
            continue
        rating = float(getattr(prospect, 'playerRating', 0) or 0)
        if rating > bestRating:
            best, bestRating = ('prospect', prospect), rating
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
    try:
        team.assignPlayerNumber(person)
    except Exception:
        pass


def _handOverPieces(seasonManager, pieces, fromTeam, toTeam, season: int = 0) -> list:
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
            elif piece['kind'] == 'prospect':
                prospect = _findProspect(fromTeam, piece['id'])
                if prospect is not None:
                    _stampAcquired(prospect, season)
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
