"""Autonomous Front Office — the GM brain.

The sim decides; fans express sentiment; sentiment tips the GM's hand in
proportion to that GM's own `fanTrust`. This module owns the VALUATION half of
that idea plus the re-sign decision built on top of it.

See docs/AUTONOMOUS_FRONT_OFFICE_PLAN.md (Part A).

The one idea everything here rests on:

    perceivedValue(player) = a scouting-gated, arc-aware, FORWARD-LOOKING
                             projection x POSITION_VALUE

"Forward-looking" is what makes a GM good or bad at their job. A player's value
is what they will be worth NEXT season, not what the rating says today:

  - developing — young, real headroom left below POTENTIAL, about to rise.
    Worth MORE than today's number, and worth more still to a GM who can
    actually coach them up.
  - prime      — at or near the ceiling, not yet declining. Worth today's number.
  - regressing — past the longevity clock, falling off next season. Worth LESS
    than today's number.

Growth is coach-driven and only happens on a roster, so the old
debut-below-trueSkill tier was retired (plan Part F): players enter at their
real ability and climb toward potential only once signed.

`scouting` gates how much of that arc a GM actually SEES. A sharp scout reads
the projection; a poor one judges on the current number and eats the error —
so they overpay to keep a fading vet and let an ascender walk. Those are
genuinely bad personnel decisions that fall out of the attribute rather than
being scripted.

Phase 1 scope: valuation + the re-sign decider. Cut-for-upgrade and the
best-first assessment sweep land in the next pass; fan sentiment (Part D) wires
into `sentimentTilt` once the ratings layer exists.
"""

import logging
from random import gauss

import os as _os
# A/B: soften destination preference from a hard veto into a ranking penalty.
# FLOOS_SOFT_APPEAL=1 lets any player sign anywhere, but a club below the player's
# Appeal demand values them lower, so they go to a club that suits them when one
# exists and still get signed when none does. Off by default.
_SOFT_APPEAL = _os.environ.get('FLOOS_SOFT_APPEAL') == '1'
_SOFT_APPEAL_PENALTY = float(_os.environ.get('FLOOS_SOFT_APPEAL_PENALTY', '0.75'))

from constants import (
    POSITION_VALUE,
    FO_SCOUT_VISION_FLOOR, FO_SCOUT_VISION_CEILING, FO_SCOUT_NOISE_MAX,
    FO_CEILING_CREDIT, FO_DEVELOPING_HEADROOM,
    FO_DECLINE_PER_YEAR_PAST, FO_DECLINE_MAX,
    FO_RESIGN_SURPLUS_MARGIN, FO_FA_CONTENTION,
    FO_CUT_ENABLED, FO_CUT_UPGRADE_MARGIN, FO_CUT_MAX_PER_TEAM,
    SENTIMENT_MAX_VALUE_SWING,
    FO_SCOUT_FACILITY_ENABLED,
    FA_PREFERENCE_ENABLED, FA_PREF_MAX_DEMAND, FA_PREF_VET_FULL_SEASONS,
    FA_PREF_VET_WEIGHT, FA_PREF_JITTER,
)

logger = logging.getLogger(__name__)

# Career-arc labels. Also surfaced for logging / future UI so a GM's reasoning
# is legible ("let them walk — regressing") rather than an opaque number.
ARC_DEVELOPING = 'developing'
ARC_PRIME = 'prime'
ARC_REGRESSING = 'regressing'


def _clamp(value, low, high):
    return max(low, min(high, value))


def positionValue(player) -> float:
    """POSITION_VALUE multiplier for a player's position. Unknown/missing
    positions fall back to 1.0 so a valuation never silently zeroes out."""
    pos = getattr(player, 'position', None)
    name = getattr(pos, 'name', None) or str(pos or '')
    return POSITION_VALUE.get(name.upper(), 1.0)


class FrontOfficeBrain:
    """Per-league GM brain. Stateless between calls except for the injected
    playerManager, so it can be constructed cheaply wherever it's needed."""

    def __init__(self, playerManager, sentimentMap=None):
        self.playerManager = playerManager
        # {playerId: -1.0..+1.0}, already rater-gated. Injected (not queried
        # per player) because the sweep values every roster on every team and
        # per-player lookups would be an N+1 in the offseason hot path. Absent
        # or unknown players read neutral, so the brain works unchanged with no
        # sentiment layer at all.
        self.sentimentMap = sentimentMap or {}

    # ---------------------------------------------------------------- arc

    def classifyArc(self, player) -> str:
        """Where the player sits on their career curve. Reads POTENTIAL headroom
        for the rise and `computeRetirementOdds` for the fall — the same age
        clock the sim already retires players on, so the GM and the sim agree
        about who is old. Decline wins ties: a vet with headroom left is still
        fading, not developing.

        Keyed on potential, NOT the retired `trueSkill` tier (Part F removed it:
        players now enter at their real ability and climb toward potential only
        while rostered, under a coach). Requires FO_DEVELOPING_HEADROOM of real
        room, since nearly every player carries a point or two of slack and
        "developing" should mean a genuine climb ahead."""
        current = int(getattr(player, 'playerRating', 0) or 0)

        yearsPast = self._yearsPastLongevity(player)
        if yearsPast >= 0:
            return ARC_REGRESSING

        if self._ceilingRating(player) - current >= FO_DEVELOPING_HEADROOM:
            return ARC_DEVELOPING
        return ARC_PRIME

    def _yearsPastLongevity(self, player) -> int:
        """Seasons past the player's personal longevity clock (negative = still
        short of it). Sourced from computeRetirementOdds so there is exactly one
        definition of "old" in the codebase."""
        try:
            _chance, _eligible, yearsPast = self.playerManager.computeRetirementOdds(player)
            return int(yearsPast)
        except Exception:
            # A player with no attributes (or a stub in a test) is treated as
            # mid-career rather than ancient — the safe default.
            return -99

    def _expectedRating(self, player) -> int:
        """Rating the player naturally grows into (trueSkill level)."""
        fn = getattr(player, 'computeExpectedRating', None)
        if not callable(fn):
            return int(getattr(player, 'playerRating', 0) or 0)
        try:
            return int(fn())
        except Exception:
            return int(getattr(player, 'playerRating', 0) or 0)

    def _ceilingRating(self, player) -> int:
        """Rating the player reaches only with good development (potential)."""
        fn = getattr(player, 'computeCeilingRating', None)
        if not callable(fn):
            return int(getattr(player, 'playerRating', 0) or 0)
        try:
            return int(fn())
        except Exception:
            return int(getattr(player, 'playerRating', 0) or 0)

    # ---------------------------------------------------------- projection

    def trueForwardRating(self, player, coach=None) -> float:
        """What the player is ACTUALLY worth next season, before the GM's own
        scouting error is applied. This is ground truth — `perceivedValue` is
        what a given GM manages to see of it."""
        current = float(getattr(player, 'playerRating', 0) or 0)
        arc = self.classifyArc(player)

        if arc == ARC_REGRESSING:
            yearsPast = self._yearsPastLongevity(player)
            # +1 because a player who just hit longevity (yearsPast 0) is
            # already declining into next season, not holding steady.
            decline = _clamp(FO_DECLINE_PER_YEAR_PAST * (yearsPast + 1),
                             0.0, FO_DECLINE_MAX)
            return current * (1.0 - decline)

        if arc == ARC_DEVELOPING:
            ceiling = float(self._ceilingRating(player))
            # How much of the remaining ceiling gap this GM expects to realise.
            # Growth is coach-driven, so a strong developer rationally values
            # raw talent higher than a weak one does — the plan's second-order
            # effect (sharp scout + good developer takes on the project player).
            devLean = self._attrLean(coach, 'playerDevelopment')
            return current + (ceiling - current) * FO_CEILING_CREDIT * devLean

        return current

    def _attrLean(self, coach, attr: str, bonus: float = 0.0) -> float:
        """Normalise a 60-100 coach attribute to 0.0-1.0. A missing coach reads
        as neutral-average rather than incompetent, so an unmanaged team still
        makes middling-sane decisions.

        `bonus` is added to the raw attribute BEFORE normalising — that's how
        the Scouting Department buys vision (see scoutingVision). A coach with
        no bonus behaves exactly as before."""
        if coach is None and not bonus:
            return 0.5
        raw = float(getattr(coach, attr, 80) or 80) + float(bonus or 0.0)
        span = FO_SCOUT_VISION_CEILING - FO_SCOUT_VISION_FLOOR
        if span <= 0:
            return 0.5
        return _clamp((raw - FO_SCOUT_VISION_FLOOR) / span, 0.0, 1.0)

    def scoutingVision(self, coach, team=None) -> float:
        """How much of a player's forward arc this front office actually sees.

        The GM's own `scouting` plus whatever their Scouting Department buys
        them. The facility is worth up to +7 attribute points at level 5, which
        on the 40-point vision span is about +17% of the arc — enough to matter
        on a close call, never enough to turn a bad evaluator into a good one.
        """
        bonus = 0.0
        if FO_SCOUT_FACILITY_ENABLED and team is not None:
            try:
                bonus = float(team.facilityEffect('scouting_bonus') or 0.0)
            except Exception:
                bonus = 0.0
        return self._attrLean(coach, 'scouting', bonus=bonus)

    # ------------------------------------------------------------- value

    def perceivedValue(self, player, coach=None, rng=None, team=None) -> float:
        """What THIS GM believes the player is worth, position-weighted.

        The GM's read is a blend of today's number and the true forward
        projection, mixed by `scouting`: no vision = the current rating only,
        full vision = the projection. Whatever vision is missing becomes random
        error, so a poor scout is wrong in a direction rather than just fuzzy.

        `rng` is injectable so tests can make a valuation deterministic.
        """
        if player is None:
            return 0.0
        current = float(getattr(player, 'playerRating', 0) or 0)
        forward = self.trueForwardRating(player, coach)

        vision = self.scoutingVision(coach, team)
        seen = current + (forward - current) * vision

        # Error shrinks to zero as vision approaches 1.
        noiseSigma = FO_SCOUT_NOISE_MAX * (1.0 - vision)
        if noiseSigma > 0:
            draw = rng.gauss(0, noiseSigma) if rng is not None else gauss(0, noiseSigma)
            seen += draw

        return max(0.0, seen) * positionValue(player)

    def sentimentTilt(self, player, coach=None) -> float:
        """Fan sentiment x this GM's `fanTrust`, in perceivedValue points.

        The plan's core constraint: sentiment TIPS CLOSE CALLS and must never
        force a clearly-bad move. So the swing is capped at
        SENTIMENT_MAX_VALUE_SWING and scaled by BOTH how strongly fans feel
        (-1..+1) and how much this GM listens (`fanTrust` 60-100 -> 0..1).

        The two extremes are the design's whole point:
          - fanTrust 60  -> tilt 0. This GM ignores the fans entirely and
            trusts their own read.
          - fanTrust 100 -> full swing. A populist who churns fan-villains and
            keeps darlings, and regrets it.
        """
        pid = getattr(player, 'id', None)
        sentiment = self.sentimentMap.get(pid, 0.0) if pid is not None else 0.0
        if not sentiment:
            return 0.0
        trust = self._attrLean(coach, 'fanTrust')
        return sentiment * trust * SENTIMENT_MAX_VALUE_SWING

    def decisionValue(self, player, coach=None, rng=None, team=None) -> float:
        """perceivedValue plus the sentiment tilt — the number decisions use."""
        value = (self.perceivedValue(player, coach, rng=rng, team=team)
                 + self.sentimentTilt(player, coach))
        if _SOFT_APPEAL and team is not None and player is not None:
            # Below the player's Appeal demand this club is a worse fit, so it ranks
            # them lower — it does NOT lose the right to sign them. Under the hard
            # gate a low-Appeal club simply could not sign any veteran at all.
            try:
                if self.teamAppeal(team) < self.appealDemand(player):
                    value *= _SOFT_APPEAL_PENALTY
            except Exception:
                pass
        return value

    # ---------------------------------------------------------- re-sign

    def bestReplacementValue(self, player, coach=None, pool=None, rng=None,
                             pickDepth=0, team=None) -> float:
        """Value of the replacement this team can REALISTICALLY sign at the
        player's position.

        Deliberately NOT the league-best free agent. The FA draft is worst-first
        and only one team can sign any given player, so if every team measured
        its incumbent against the same top free agent, all 24 would conclude
        their starter was replaceable and the entire league would let its
        incumbents walk. Instead a team looks `pickDepth` players down the board
        — how far depends on its own slot in the worst-first order — which makes
        cutting a genuine gamble for a good team and cheap for a bad one.

        Retiring free agents are excluded: they cannot actually be signed. So
        are players who wouldn't sign HERE — that's the point of settling
        destination preference before the draft rather than during it. A club
        with no facilities must not cut its veteran on the strength of an
        upgrade who was never going to take the call.

        Returns 0.0 when the position is picked clean before this team's turn,
        which correctly means "nobody to replace them with, keep them".
        """
        if pool is None:
            pool = getattr(self.playerManager, 'freeAgents', None) or []
        pos = getattr(player, 'position', None)
        values = []
        for fa in pool:
            if fa is None or fa is player:
                continue
            if getattr(fa, 'position', None) != pos:
                continue
            if getattr(fa, 'willRetire', False):
                continue
            if team is not None and not self.willSignWith(fa, team):
                continue
            values.append(self.decisionValue(fa, coach, rng=rng, team=team))
        if not values:
            return 0.0
        values.sort(reverse=True)
        depth = max(0, int(pickDepth))
        if depth >= len(values):
            return 0.0      # position picked clean before this team's turn
        return values[depth]

    # ------------------------------------------------- destination preference

    def appealDemand(self, player) -> float:
        """The minimum team Appeal this player will sign for.

        AGE ONLY, by design. Rating is deliberately not an input: if demand
        tracked talent then the best players would pool at the best-funded
        clubs and the league would stratify by treasury. Keyed on service time,
        what money buys you is veterans, not talent.

        The per-player jitter is scaled by the veteran term, so rookies cluster
        at zero (they go anywhere for a shot) while two equally old players can
        want quite different things. Deterministic in the player id so a
        player's preference doesn't change between calls, or between a
        pre-draft board and the pick that acts on it.
        """
        seasons = float(getattr(player, 'seasonsPlayed', 0) or 0)
        vet = _clamp(seasons / max(1.0, FA_PREF_VET_FULL_SEASONS), 0.0, 1.0)

        # Stable per-player draw in -1..+1. hash() is salted per process, so
        # the id is folded by hand to keep this reproducible across runs.
        pid = int(getattr(player, 'id', 0) or 0)
        spread = (((pid * 2654435761) % 1000) / 1000.0 - 0.5) * 2.0

        base = vet * FA_PREF_VET_WEIGHT + spread * FA_PREF_JITTER * vet
        return FA_PREF_MAX_DEMAND * _clamp(base, 0.0, 1.0)

    def teamAppeal(self, team) -> float:
        """This team's Appeal — the weighted facility sum. One definition,
        shared with the Front Office readout."""
        try:
            from managers.facilitiesManager import computeAppeal
            return float(computeAppeal(getattr(team, 'facilities', None) or {}))
        except Exception:
            return 0.0

    def willSignWith(self, player, team) -> bool:
        """Would this player join this team at all?

        Checked ONCE, before the draft, so a GM never ranks or plans a cut
        around a player who was never going to come. Nothing downstream asks a
        player to reconsider mid-draft."""
        if not FA_PREFERENCE_ENABLED or team is None or player is None:
            return True
        if _SOFT_APPEAL:
            # Preference, not veto: a player would rather play than sit out, so
            # nobody is excluded from a board. The cost of a poor fit is applied
            # in decisionValue instead.
            return True
        return self.teamAppeal(team) >= self.appealDemand(player)

    def buildDraftBoard(self, team, pool, coach=None, rng=None, alsoValue=None):
        """This team's own ranking of the free agents who would sign here.

        Two teams see two different boards: the order is `decisionValue`, which
        is scouting-gated and carries that GM's own error, so one club's top
        target is another's fifth choice. The scouting error is drawn ONCE here
        rather than per pick, so a team's board doesn't reshuffle underneath it
        between rounds.

        `alsoValue` (the team's own prospects) is priced onto the SAME board
        without the willingness check — they're already here, so there's nothing
        to agree to. They have to share the board's currency: decisionValue is
        position-weighted and a raw playerRating is not, so scoring prospects
        the old way would have made every cross-position comparison at pick time
        a unit mismatch.

        Returns {playerId: value}. Free agents who won't sign here are absent,
        which is what keeps them out of both the ranking and the
        cut-for-upgrade math.
        """
        board = {}
        for fa in pool or []:
            if fa is None or getattr(fa, 'willRetire', False):
                continue
            if not self.willSignWith(fa, team):
                continue
            pid = getattr(fa, 'id', None)
            if pid is None:
                continue
            board[pid] = self.decisionValue(fa, coach, rng=rng, team=team)
        for p in alsoValue or []:
            pid = getattr(p, 'id', None)
            if p is None or pid is None:
                continue
            board[pid] = self.decisionValue(p, coach, rng=rng, team=team)
        return board

    def faPickDepth(self, team, faOrder=None) -> int:
        """How far down the FA board this team should expect to be shopping.

        Derived from its index in the worst-first FA order, discounted by
        FO_FA_CONTENTION because not every team ahead needs the same position.
        A missing/short order degrades to 0 (shop the top of the board), which
        is the pre-existing behaviour rather than a silent surprise.
        """
        if not faOrder or team is None:
            return 0
        try:
            index = list(faOrder).index(team)
        except ValueError:
            return 0
        return int(index * FO_FA_CONTENTION)

    def rankResignCandidates(self, expiring, coach=None, pool=None, rng=None,
                             pickDepth=0):
        """Rank walk-year incumbents by how much they beat the best replacement
        at their own position ("surplus").

        This is the comparative test from the plan: a scarce re-sign slot is
        only worth spending when keeping the incumbent genuinely beats going to
        the market. A player the market can replace is allowed to walk even if
        they are good, and a modest player with no replacement behind them is worth
        keeping.

        Returns [(player, surplus)] sorted best-first, already filtered to
        those clearing FO_RESIGN_SURPLUS_MARGIN.
        """
        ranked = []
        for player in expiring:
            incumbent = self.decisionValue(player, coach, rng=rng)
            replacement = self.bestReplacementValue(player, coach, pool=pool, rng=rng,
                                                    pickDepth=pickDepth)
            surplus = incumbent - replacement
            if surplus >= FO_RESIGN_SURPLUS_MARGIN:
                ranked.append((player, surplus))
        ranked.sort(key=lambda pair: -pair[1])
        return ranked

    def chooseResigns(self, expiring, limit, coach=None, pool=None, rng=None,
                      pickDepth=0):
        """The re-sign decision: at most `limit` keepers, best surplus first.

        `limit` is the caller's — RESIGN_LIMIT_PER_OFFSEASON is a parity
        guardrail this brain deliberately does NOT relitigate. The brain only
        changes WHO fills the slots, never how many there are.
        """
        if limit <= 0:
            return []
        return [p for p, _surplus in self.rankResignCandidates(
            expiring, coach=coach, pool=pool, rng=rng, pickDepth=pickDepth)[:limit]]

    # -------------------------------------------------------------- cuts

    def rankCutCandidates(self, team, coach=None, pool=None, rng=None, pickDepth=0):
        """Rank players worth CUTTING, biggest upgrade first.

        Only players still UNDER CONTRACT are considered. A walk-year player who
        loses the re-sign comparison already leaves on their own, so cutting them
        would be redundant churn — and a retiring player vacates anyway.

        The comparison is the same one re-sign uses (incumbent vs the
        replacement realistically available at this team's FA slot), just with a
        larger margin: letting someone walk is free, cutting someone under
        contract opens a hole the worst-first draft may not let you fill.

        Returns [(player, slot, upgrade)] sorted best-upgrade-first.
        """
        ranked = []
        roster = getattr(team, 'rosterDict', None) or {}
        for slot, player in roster.items():
            if player is None:
                continue
            if getattr(player, 'willRetire', False):
                continue                      # vacates on its own
            if (getattr(player, 'termRemaining', 0) or 0) <= 1:
                continue                      # walk-year: retention decides them
            incumbent = self.decisionValue(player, coach, rng=rng)
            replacement = self.bestReplacementValue(player, coach, pool=pool,
                                                    rng=rng, pickDepth=pickDepth)
            upgrade = replacement - incumbent
            if upgrade >= FO_CUT_UPGRADE_MARGIN:
                ranked.append((player, slot, upgrade))
        ranked.sort(key=lambda r: -r[2])
        return ranked

    def chooseCuts(self, team, coach=None, pool=None, rng=None, pickDepth=0):
        """Players this GM cuts in anticipation of signing an upgrade.

        Uncapped by design (plan Part A): real upgrades are scarce, every team
        fishes the same finite pool, and worst-first FA order means a cut may
        not be replaced — so churn is expected to self-limit. Add a soft cap
        only if a sim shows thrash.
        """
        if not FO_CUT_ENABLED:
            return []
        ranked = self.rankCutCandidates(team, coach=coach, pool=pool,
                                        rng=rng, pickDepth=pickDepth)
        if FO_CUT_MAX_PER_TEAM is not None:
            ranked = ranked[:FO_CUT_MAX_PER_TEAM]   # biggest upgrades first
        return [(p, slot) for p, slot, _u in ranked]
