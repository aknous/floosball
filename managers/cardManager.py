"""Card Manager - handles card template generation and card operations."""

import random
from datetime import datetime
from typing import List, Dict, Any, Optional
from logger_config import get_logger
from managers.cardEffects import (buildEffectConfig as _buildEffectConfig, getEffectOutputType,
                                  effectValidPositions as _effectValidPositions,
                                  effectPoolFor as _effectPoolFor)

logger = get_logger("floosball.cardManager")

# ─── Edition Configuration ────────────────────────────────────────────────────

# Rating thresholds for edition eligibility.
# 'base' is the sub-base, NO-EFFECT floor print (fusion): every player gets one,
# it just fields the player for their FP. Kept OUT of paid pack pools (weight 0) — it's
# distributed as the starter/floor lineup, not a pack drop.
EDITION_THRESHOLDS = {
    'base': 0,      # All players (no-effect floor card)
    'metallic': 0,          # All players
    'holographic': 75,  # Rating >= 75
    'prismatic': 80,    # Rating >= 80
    'diamond': 90,      # Rating >= 90
}

# Base rarity weights (before player-rating adjustment). standard=0 keeps the floor
# card out of every pack roll (see _weightedDraw's fallback).
EDITION_BASE_WEIGHTS = {
    'base': 0,
    'metallic': 100,
    'holographic': 25,
    'prismatic': 10,
    'diamond': 2,
}

# Sell values by edition (active season)
EDITION_SELL_VALUES = {
    'base': 2,
    'metallic': 5,
    'holographic': 30,
    'prismatic': 75,
    'diamond': 100,
}

EXPIRED_SELL_MULTIPLIER = 0.2  # Expired cards sell for 20%

# ─── The Combine (Card Upgrade System) ───────────────────────────────────────

EDITION_ORDER = ['metallic', 'holographic', 'prismatic', 'diamond']

# The Combine: total card value thresholds for resulting edition
BLENDER_THRESHOLDS = [
    (300, 'diamond'),       # 300+ total value → diamond (e.g. 4 prismatics, or 10 holos)
    (175, 'prismatic'),     # 175-499 → prismatic (e.g. 6 holos, or 1 holo + many bases)
    (50, 'holographic'),    # 50-174 → holographic (e.g. 10 base cards)
    (0, 'metallic'),            # 0-49 → base
]

# Daily pack purchase limits — currently empty. After the unified-rotation
# rework, grand and exquisite are no longer guaranteed daily fixtures, so
# capping them at 1/day created the bad UX of a user rerolling into 3 packs
# they already bought today. Per-pack daily caps removed for all tiers.
# Per-pack daily caps, keyed by pack name. The window is a real UTC calendar day.
DAILY_PACK_LIMITS: Dict[str, int] = {
    # One Collection Pack a day (owner, 2026-08-02). It sits outside the cycle cap
    # below, so this is the only thing pacing it — and a daily cadence suits a
    # collection: something to come back for, rather than something to bulk-buy.
    'themed_collection': 1,
}

# Total purchased packs (any tier) a user can open in one 7-week shop cycle.
# Stops whales from buying dozens of packs and feeding the Combine to fabricate
# rare cards in bulk. Free / achievement-granted packs (skipCurrency=True) and
# the starter pack do NOT count toward this cap.
#
# The Collection Pack is ALSO exempt (see _countsTowardCycleCap). The cap exists
# to stop pack-churning into Combine fuel, and collection cards land vaulted —
# vaulted cards can't be combined — so the rationale doesn't apply. It also can't
# be allowed to consume the cycle allowance during the postseason, when it is the
# only pack on sale.
MAX_PACKS_PER_SHOP_CYCLE: int = 5


def _countsTowardCycleCap(packType) -> bool:
    """Whether a pack consumes the per-cycle allowance."""
    return not isAlwaysAvailablePack(packType)


def _shopCycleStartDate(session, currentSeason: int, currentWeek: int):
    """Datetime when the current shop cycle began, computed from
    Season.start_date. Returns None if the season's start date isn't set
    yet (caller should treat that as 'no cap enforced').

    A shop cycle spans 7 sim-weeks (one game-day in the schedule). The
    regular-season schedule packs 7 rounds into a single calendar day —
    sim-weeks 1-7 are Monday, 8-14 are Tuesday, 15-21 Wednesday, 22-28
    Thursday — so each shopDay rollover corresponds to a **one-day**
    advance in real time, not a 7-week one. Using timedelta(weeks=...)
    here would push cycleStart ~48 days into the future on day 2 and
    silently zero the counter.

    A late safety clamp guards against the start_date itself sitting in
    the future (e.g. scheduled mode anchoring to next Monday during the
    pre-start window).
    """
    import datetime as _dt
    from database.models import Season
    season = session.query(Season).filter(Season.season_number == currentSeason).first()
    if not season or not season.start_date:
        return None
    shopDay = shopDayOfSeason(currentWeek)
    cycleStart = season.start_date + _dt.timedelta(days=shopDay - 1)
    now = _dt.datetime.utcnow()
    if cycleStart > now:
        # Pre-start window — anchor far enough back that every recent
        # paid open still counts. A year is well beyond a single cycle's
        # span so it can't accidentally pull in prior-cycle opens.
        cycleStart = now - _dt.timedelta(days=365)
    return cycleStart


def _countPacksThisCycle(session, userId: int, currentSeason: int, currentWeek: int) -> int:
    """Count packs the user has *purchased* (cost > 0) in the current shop
    cycle. Counts both committed PackOpening rows and in-flight
    PendingPackOpening rows so a user mid-reveal can't open another.

    EXCLUDES always-available packs (the Collection Pack). Exempting it from the
    cap check alone would not be enough — if its opens still counted here, buying
    five of them would silently exhaust the allowance for every other pack, which
    is the opposite of exempt.
    """
    from database.models import PackOpening, PendingPackOpening, PackType
    cycleStart = _shopCycleStartDate(session, currentSeason, currentWeek)
    if cycleStart is None:
        return 0
    exemptIds = [pt.id for pt in session.query(PackType).all()
                 if isAlwaysAvailablePack(pt)]
    committed = session.query(PackOpening).filter(
        PackOpening.user_id == userId,
        PackOpening.opened_at >= cycleStart,
        PackOpening.cost > 0,
    )
    pending = session.query(PendingPackOpening).filter(
        PendingPackOpening.user_id == userId,
        PendingPackOpening.opened_at >= cycleStart,
        PendingPackOpening.cost_paid > 0,
    )
    if exemptIds:
        committed = committed.filter(~PackOpening.pack_type_id.in_(exemptIds))
        pending = pending.filter(~PendingPackOpening.pack_type_id.in_(exemptIds))
    return committed.count() + pending.count()

# Shop rotation: 4 "shop days" map to 7-week segments of the season,
# matching the existing featured-shop SWAP_CYCLE_WEEKS cycle.
#   Shop day 1 → weeks 1-7
#   Shop day 2 → weeks 8-14
#   Shop day 3 → weeks 15-21
#   Shop day 4 → weeks 22-28
def shopDayOfSeason(currentWeek: int) -> int:
    """Return the 1-indexed shop day (1-4) for the given season week.
    Clamps to [1, 4] for the regular-season range; postseason weeks fall
    in shop day 4 since that's the final cycle.
    """
    from constants import SWAP_CYCLE_WEEKS
    week = max(1, currentWeek or 1)
    return min(4, (week - 1) // SWAP_CYCLE_WEEKS + 1)


def isAlwaysAvailablePack(packType) -> bool:
    """Packs exempt from the daily rotation entirely.

    The Collection Pack never rotates: it is the only product on sale outside the
    regular season, so gating it on a rotation slot would make it unbuyable on
    most days and completely unbuyable in the postseason — exactly when it is the
    only thing to buy. The shop surfaces it outside the rotation, so the purchase
    path has to agree.
    """
    return getattr(packType, 'theme_type', None) == 'collection'


def getActivePackNames(shopDay: int) -> list:
    """Standard pack tiers always visible in the shop, regardless of shop_day.

    Empty after the disappear-on-buy rework — every pack tier now flows
    through FeaturedPackRotation so it can be marked purchased and removed
    from the shop until reroll/cycle refresh. Humble was previously here
    but moved into the rotation pool with a high category weight.
    """
    return []


# Map position code → position int for theme filtering
_POSITION_CODE_TO_INT = {'QB': 1, 'RB': 2, 'WR': 3, 'TE': 4, 'K': 5}

# ── Fantasy/Cards fusion: position-locked equipped-card slots ──────────────────
# Equipped cards ARE the fantasy roster, so each slot is tied to a position. Six base
# slots (one per position, mirroring the old FantasyRosterPlayer.slot) + FLEX (7th).
FUSION_BASE_SLOTS = ['QB', 'RB', 'WR1', 'WR2', 'TE', 'K']
FLEX_SLOT = 'FLEX'
FUSION_ALL_SLOTS = FUSION_BASE_SLOTS + [FLEX_SLOT]
# slot → 1-based position (matches CardTemplate.position / the Position enum); FLEX = any.
SLOT_TO_POSITION = {'QB': 1, 'RB': 2, 'WR1': 3, 'WR2': 3, 'TE': 4, 'K': 5, FLEX_SLOT: None}
# slot → stable display/order ordinal (EquippedCard.slot_number).
SLOT_TO_ORDINAL = {'QB': 1, 'RB': 2, 'WR1': 3, 'WR2': 4, 'TE': 5, 'K': 6, FLEX_SLOT: 7}


def _deriveStarterSlotCounts():
    """(position, count) pairs covering every base lineup slot, in slot order —
    e.g. QB/RB/WR1/WR2/TE/K → [(1,1),(2,1),(3,2),(4,1),(5,1)] (two WR cards)."""
    ordered: list = []
    seen: dict = {}
    for slot in FUSION_BASE_SLOTS:
        pos = SLOT_TO_POSITION[slot]
        if pos in seen:
            seen[pos][1] += 1
        else:
            entry = [pos, 1]
            seen[pos] = entry
            ordered.append(entry)
    return [(pos, count) for pos, count in ordered]


# Ordered (position, count) the starter pack draws — one card per base slot,
# so WR yields two (WR1 + WR2). Kept in sync with FUSION_BASE_SLOTS.
_STARTER_SLOT_COUNTS = _deriveStarterSlotCounts()


def cardFitsSlot(templatePosition, slot) -> bool:
    """Whether a card whose depicted player sits at `templatePosition` (1-based, matching
    CardTemplate.position / the Position enum) may fill `slot`. FLEX accepts any position;
    a base slot requires an exact position match. Unknown slot → False."""
    if slot == FLEX_SLOT:
        return True
    expected = SLOT_TO_POSITION.get(slot)
    return expected is not None and int(templatePosition) == expected

# Champion pack draws one card per player (dedup). After a title most of the winning
# roster can retire (season 11: 5 of 6 winners retired), leaving too few with current
# templates to fill the pack — below this many distinct champions, top up from the
# champion team's current roster (untagged) so the pack still fills.
CHAMPION_PACK_MIN_PLAYERS = 6


def _applyThemeFilter(templates: list, themeType: str, themeValue: str,
                      session=None, currentSeason: int = 0) -> list:
    """Filter a CardTemplate pool down to the rows matching a themed pack.

    Static themes (position/team/output) resolve from theme_value alone.
    Dynamic prestige themes (champion/allpro) resolve from prior-season
    Season state — caller must supply session + currentSeason. Returns
    an empty list if the prior season's data isn't yet recorded (e.g.
    season 1 before any season has completed).

    Mixed/contextual effects (output_type IS NULL on the template) are
    excluded from output-themed packs by design — themed packs deliver
    concrete output types only.
    """
    if themeType == 'position':
        posInt = _POSITION_CODE_TO_INT.get(themeValue)
        if posInt is None:
            return []
        return [t for t in templates if t.position == posInt]
    if themeType == 'team':
        try:
            teamIdInt = int(themeValue)
        except (TypeError, ValueError):
            return []
        return [t for t in templates if t.team_id == teamIdInt]
    if themeType == 'output':
        return [t for t in templates if getattr(t, 'output_type', None) == themeValue]
    if themeType == 'collection':
        # The pool handed in IS already the collection set (openPack swaps the
        # source for this theme), so there is nothing further to filter on.
        return list(templates)
    if themeType == 'rookie':
        # This season's rookie class. `templates` is already scoped to the
        # current season (getBySeason), and each season's veteran templates are
        # regenerated with is_rookie=False, so is_rookie==True here is exactly
        # the current draft class — no season/date math needed.
        return [t for t in templates if getattr(t, 'is_rookie', False)]
    if themeType in ('champion', 'allpro'):
        if session is None or currentSeason <= 1:
            return []
        from database.models import Season
        priorSeason = (
            session.query(Season)
            .filter(Season.season_number == currentSeason - 1)
            .first()
        )
        if priorSeason is None:
            return []
        if themeType == 'champion':
            champTeamId = priorSeason.champion_team_id
            # True champions: the Floos-Bowl roster SNAPSHOT (who actually won), NOT the
            # team's current roster — `team_id` drifts as players join/leave/retire.
            rawChampIds = getattr(priorSeason, 'champion_player_ids', None)
            champIds = set()
            if rawChampIds:
                try:
                    import json as _jsonCh
                    champIds = set(_jsonCh.loads(rawChampIds)) if isinstance(rawChampIds, str) else set(rawChampIds)
                except Exception:
                    champIds = set()
            if not champIds:
                # Pre-snapshot season (no roster captured): fall back to the champion
                # team's templates by team_id (the old, drift-prone behavior).
                return [t for t in templates if champTeamId and t.team_id == champTeamId]
            pool = [t for t in templates if t.player_id in champIds]
            # Safeguard: if too few winners are still active (most retired), top up with
            # the champion TEAM's current roster so the pack fills. These top-ups carry
            # NO champion tag — only true winners do, via the classification snapshot —
            # so this never re-tags a non-winner (the bug this whole fix addresses).
            if len({t.player_id for t in pool}) < CHAMPION_PACK_MIN_PLAYERS and champTeamId:
                have = {t.player_id for t in pool}
                pool += [t for t in templates
                         if t.team_id == champTeamId and t.player_id not in have]
            return pool
        # allpro
        rawIds = priorSeason.all_pro_player_ids
        if not rawIds:
            return []
        try:
            import json as _json
            allProIds = set(_json.loads(rawIds)) if isinstance(rawIds, str) else set(rawIds)
        except Exception:
            return []
        if not allProIds:
            return []
        return [t for t in templates if t.player_id in allProIds]
    return templates

# Classification value multipliers (stacking for compound classifications)
CLASSIFICATION_VALUE_MULTIPLIERS = {
    'rookie': 2.0,
    'mvp': 3.0,
    'champion': 2.0,
    'all_pro': 1.5,
}



def getCardValue(card, currentSeason: int) -> int:
    """Get classification- and tier-aware value for a card. Used by The Combine
    operations and sell value. A leveled-up card is worth more: its tier's WORTH
    is consumed when fed to the Combine (the tier isn't 'lost', it lifts the
    result edition) and lifts sell value too."""
    from constants import CARD_TIER_MULT
    isActive = card.card_template.season_created == currentSeason
    baseValue = getSellValue(card.card_template.edition, isActive=isActive)
    classification = card.card_template.classification or ""
    multiplier = 1.0
    for tag, mult in CLASSIFICATION_VALUE_MULTIPLIERS.items():
        if tag in classification:
            multiplier *= mult
    tierMult = CARD_TIER_MULT.get(getattr(card, "tier", 1) or 1, 1.0)
    return max(1, int(baseValue * multiplier * tierMult))


def computeRarityWeight(edition: str, playerRating: int) -> int:
    """Compute rarity weight for pack drops. Higher-rated players are rarer."""
    baseWeight = EDITION_BASE_WEIGHTS.get(edition, 100)
    ratingPenalty = max(1, 120 - playerRating)
    return baseWeight * ratingPenalty


def getSellValue(edition: str, isActive: bool = True) -> int:
    """Get sell value for a card edition. Expired cards sell for 20%."""
    baseValue = EDITION_SELL_VALUES.get(edition, 5)
    if not isActive:
        return max(1, int(baseValue * EXPIRED_SELL_MULTIPLIER))
    return baseValue


def _buildClassification(
    playerId: int,
    isRookie: bool,
    mvpPlayerId: Optional[int],
    championPlayerIds: set,
    allProPlayerIds: set,
    edition: str = "metallic",
) -> Optional[str]:
    """Build classification string for a player's card templates.

    Classifications are underscore-joined tags (e.g., "mvp_champion", "all_pro_champion").
    Rookie can appear on any edition. MVP, Champion, and All-Pro require holographic+.
    Rookie cannot stack with other classifications (rookies didn't play previous season).
    """
    if isRookie:
        return "rookie"

    # MVP, Champion, All-Pro only on holographic and above — the floor tiers
    # ('base' no-effect + 'metallic') never carry a prestige classification.
    if edition in ("base", "metallic"):
        return None

    tags = []
    if mvpPlayerId is not None and playerId == mvpPlayerId:
        tags.append("mvp")
    if playerId in allProPlayerIds:
        tags.append("all_pro")
    if playerId in championPlayerIds:
        tags.append("champion")

    return "_".join(tags) if tags else None


COLLECTION_CLASSIFICATIONS = ("mvp", "champion", "all_pro")


REGULAR_SEASON_WEEKS = 28


def regularSeasonOver(currentWeek: int) -> bool:
    """True once the regular season's games are done (playoffs / offseason)."""
    return bool(currentWeek and currentWeek > REGULAR_SEASON_WEEKS)


def getCollectionTemplates(session, currentSeason: int,
                           includeCurrentSeason: bool = False) -> list:
    """The collection pool: PAST-SEASON prestige prints — MVP, Champion, All-Pro.

    One pool, one pack (owner, 2026-08-02). An earlier revision had a separate
    Hall-of-Fame-only pack; that was both thinner and a second thing to explain.
    Hall of Fame players appear in this pool naturally — measured on the dev DB
    they are 140 of 328 prints, 43% — so the enshrined are the chase inside the
    collection pack rather than a pack of their own.

    Why past seasons only:
      * The card already carries the team the player was on and the rating they
        had THAT season, which is what makes a legacy print worth collecting —
        a card minted today would show an inductee years past their peak on no
        team at all.
      * A past-season template is ALREADY unequippable (equip rejects
        season_created != currentSeason), so the pool is collection-only by
        construction rather than by a flag.

    Nothing extra is stored to support this. Templates are minted per season
    carrying season_created / player_rating / team_id / classification, and are
    never pruned — the only delete is clear_db.
    """
    from database.models import CardTemplate
    from sqlalchemy import or_

    clsFilter = or_(*[CardTemplate.classification.contains(c)
                      for c in COLLECTION_CLASSIFICATIONS])
    # `includeCurrentSeason` opens the just-finished season once the regular
    # season is over. Without it there is a dead window: from the end of week 28
    # until the season number rolls, this season's cards are neither purchasable
    # (the shop sells collection only) nor in the collection pool (they aren't a
    # PAST season yet), so they'd be unobtainable for the whole postseason and
    # offseason. They are already unequippable by then — fantasy is done, and
    # next season needs next season's cards — so they are collectibles in every
    # sense that matters.
    seasonFilter = (CardTemplate.season_created <= currentSeason
                    if includeCurrentSeason
                    else CardTemplate.season_created < currentSeason)
    return (
        session.query(CardTemplate)
        .filter(seasonFilter)
        .filter(CardTemplate.classification.isnot(None))
        .filter(clsFilter)
        .filter(CardTemplate.is_upgraded == False)                        # noqa: E712
        .all()
    )


def classificationDrawWeight(classification) -> int:
    """Relative draw weight for a card's accolade combination (100 = undecorated).

    Multiplies the existing within-edition rating weight, so a triple-crown card
    becomes genuinely hard to pull rather than merely uncommon because few
    players earned it. Unknown or absent classifications return 100, which leaves
    rookie/base cards and every non-prestige pack exactly as they were.
    """
    from constants import CLASSIFICATION_DRAW_WEIGHTS, CLASSIFICATION_TAGS
    if not classification:
        return 100
    tags = frozenset(t for t in CLASSIFICATION_TAGS if t in classification)
    if not tags:
        return 100
    return CLASSIFICATION_DRAW_WEIGHTS.get(tags, 100)


def _vaultOnAcquire(template, currentSeason: int = None, currentWeek: int = 0) -> bool:
    """Should this card land straight in the Vault?

    Two kinds of card belong there. SHOWPIECES are purpose-built collectibles.
    LEGACY PRINTS are past-season templates, which can never be equipped anyway
    (equip rejects season_created != currentSeason) and would otherwise sit dead
    in the active collection.

    The Vault is the mechanism rather than the presentation: vaulted cards are
    rejected at equip, and ONLY vaulted cards can be featured in the Showcase.
    """
    if template is None:
        return False
    if bool(getattr(template, "is_showpiece", False)):
        return True
    season = getattr(template, "season_created", None)
    if currentSeason is None or season is None:
        return False
    if season < currentSeason:
        return True
    # This season's cards, bought after the regular season ended: fantasy is over
    # and next season needs next season's cards, so they can never be fielded.
    return season == currentSeason and regularSeasonOver(currentWeek)


class CardManager:
    """Manages card template generation and card operations."""

    def __init__(self, serviceContainer):
        self.serviceContainer = serviceContainer

    @staticmethod
    def _assignEffects(edition: str, position: int, players: list,
                       topUp: bool = True) -> list:
        """Plan one (edition, position) bucket: [(player, effectName), ...].

        Replaces `random.choice` per template, which both starved and clustered the pool.
        Measured on a live season: 31 of 143 effects had NO template anywhere (prismatic
        RB gave any one effect a 74% chance of not existing; diamond TE 92%) while 27
        effects held 5+ templates. A card could be built, seeded, and still be
        unobtainable — which is what made the pass-TD family need an admin grant.

        Two rules, and the second is the one that makes coverage a guarantee rather than
        a probability:

          1. Effects are DEALT from a shuffled pool, so every one is handed out before
             any repeats and counts differ by at most one.
          2. When a bucket has FEWER players than effects, it mints one template per
             EFFECT and cycles the players, instead of one per player. Dealing alone
             cannot help here: prismatic RB is 7 players against 27 effects, so 20 must
             be absent however you shuffle. This is the top-up that closes that gap.

        So a bucket mints max(len(players), len(effects)) templates, and every effect is
        minted wherever an eligible player exists.

        `topUp=False` keeps rule 1 and drops rule 2, minting exactly one template per
        player. That is what the ROOKIE path wants: it adds to a season pool whose
        coverage is already guaranteed, so topping up there would mint the entire effect
        set for a handful of rookies.

        ⚠️ It cannot conjure a player. Nothing has ever rated 90 at QB (max 87) or K (max
        88), so with diamond's threshold at 90 those two buckets are empty and their
        effects stay unmintable — a rating-distribution fact, not a minting one. Owner
        call 2026-08-07: left as is.
        """
        import random as _r
        if edition == 'base' or not players:
            return [(p, None) for p in players]
        pool = _effectPoolFor(edition, position)
        if not pool:
            return [(p, None) for p in players]

        effects = pool[:]
        _r.shuffle(effects)
        if not topUp and len(effects) > len(players):
            effects = effects[:len(players)]
        if len(players) > len(effects):
            # More players than effects: keep dealing fresh shuffled passes so the extra
            # templates spread evenly rather than piling onto whatever won the first roll.
            while len(effects) < len(players):
                nxt = pool[:]
                _r.shuffle(nxt)
                effects.extend(nxt)
            effects = effects[:len(players)]
        # Otherwise every effect gets its own template and players cycle to carry them.
        return [(players[i % len(players)], eff) for i, eff in enumerate(effects)]

    def generateSeasonTemplates(
        self, session, seasonNumber: int,
        mvpPlayerId: Optional[int] = None,
        championPlayerIds: Optional[set] = None,
        allProPlayerIds: Optional[set] = None,
    ) -> int:
        """Generate card templates for all active players for a season.

        Called at the start of each new season. Creates one template per
        eligible (player, edition) pair. Assigns classifications based on
        previous season awards.

        Args:
            session: DB session
            seasonNumber: The season to generate templates for
            mvpPlayerId: Player ID of previous season's MVP
            championPlayerIds: Set of player IDs on previous Floosbowl-winning team
            allProPlayerIds: Set of player IDs who were top at their position

        Returns the count of templates created.
        """
        from database.models import CardTemplate
        from database.repositories.card_repositories import CardTemplateRepository

        playerManager = self.serviceContainer.getService('player_manager')
        templateRepo = CardTemplateRepository(session)

        # Check if templates already exist for this season
        existingCount = templateRepo.countBySeason(seasonNumber)
        if existingCount > 0:
            logger.info(f"Card templates already exist for season {seasonNumber} ({existingCount} templates), skipping generation")
            return 0

        champIds = championPlayerIds or set()
        apIds = allProPlayerIds or set()

        templates: List[CardTemplate] = []

        # Bucket by (edition, position) FIRST, because the effect plan for a bucket
        # depends on how many players it holds — see _assignEffects.
        buckets: dict = {}
        for player in playerManager.activePlayers:
            # Cards are for rostered players only — exclude every off-roster population:
            # free agents, prospects (is_prospect OR drafting_team_id, since the flag has
            # gotten out of sync before), upcoming rookies and retirees.
            if getattr(player, 'is_prospect', False):
                continue
            if getattr(player, 'drafting_team_id', None):
                continue
            if getattr(player, 'is_upcoming_rookie', False):
                continue
            teamObj = getattr(player, 'team', None)
            teamId = getattr(teamObj, 'id', None) if teamObj is not None else None
            if not teamId:  # None or 0 — both invalid; rules out string-team values too
                continue
            rating = getattr(player, 'playerRating', None)
            if rating is None:
                continue
            positionValue = player.position.value if hasattr(player.position, 'value') else int(player.position)
            for edition, threshold in EDITION_THRESHOLDS.items():
                if rating < threshold:
                    continue
                buckets.setdefault((edition, positionValue), []).append((player, teamId))

        for (edition, positionValue), members in buckets.items():
            plan = self._assignEffects(edition, positionValue, [m[0] for m in members])
            teamById = {m[0].id: m[1] for m in members}
            for player, effectName in plan:
                rating = getattr(player, 'playerRating', None)
                teamId = teamById.get(player.id)
                isRookie = getattr(player, 'seasonsPlayed', 1) == 0

                # Classification depends on edition (MVP/Champion/All-Pro require holo+)
                classification = _buildClassification(
                    playerId=player.id,
                    isRookie=isRookie,
                    mvpPlayerId=mvpPlayerId,
                    championPlayerIds=champIds,
                    allProPlayerIds=apIds,
                    edition=edition,
                )

                # Pass classification so a Champion card mints a lower (on-card) gate
                # threshold. The effect is PLANNED rather than rolled — see _assignEffects.
                effectConfig = _buildEffectConfig(edition, rating, positionValue, teamId,
                                                  classification=classification,
                                                  forceEffect=effectName)
                rarityWeight = computeRarityWeight(edition, rating)
                sellValue = getSellValue(edition, isActive=True)

                templates.append(CardTemplate(
                    player_id=player.id,
                    edition=edition,
                    season_created=seasonNumber,
                    is_rookie=isRookie,
                    player_name=player.name,
                    team_id=teamId,
                    player_rating=rating,
                    position=positionValue,
                    effect_config=effectConfig,
                    rarity_weight=rarityWeight,
                    sell_value=sellValue,
                    classification=classification,
                    output_type=getEffectOutputType(effectConfig.get("effectName")),
                ))

        if templates:
            templateRepo.saveBatch(templates)
            classifiedCount = sum(1 for t in templates if t.classification)
            logger.info(f"Generated {len(templates)} card templates for season {seasonNumber} ({classifiedCount} classified)")
        else:
            logger.warning(f"No card templates generated for season {seasonNumber} — no active players?")

        return len(templates)

    def generateRookieTemplates(self, session, seasonNumber: int) -> int:
        """Generate card templates for newly drafted rookies (post-free-agency).

        Called after the draft/free agency during offseason. Only creates
        templates for players that don't already have templates this season.

        Returns the count of new templates created.
        """
        from database.models import CardTemplate
        from database.repositories.card_repositories import CardTemplateRepository

        playerManager = self.serviceContainer.getService('player_manager')
        templateRepo = CardTemplateRepository(session)

        # Find players with no templates this season (newly created rookies)
        existingPlayerIds = {
            t.player_id
            for t in templateRepo.getBySeason(seasonNumber)
        }

        templates: List[CardTemplate] = []
        buckets: dict = {}

        for player in playerManager.activePlayers:
            if player.id in existingPlayerIds:
                continue

            # Skip prospects, upcoming rookies, free agents — only rostered
            # players get card templates. Belt-and-suspenders on the prospect
            # check via drafting_team_id since the flag has gotten out of
            # sync before.
            if getattr(player, 'is_prospect', False):
                continue
            if getattr(player, 'drafting_team_id', None):
                continue
            if getattr(player, 'is_upcoming_rookie', False):
                continue
            teamObj = getattr(player, 'team', None)
            teamId = getattr(teamObj, 'id', None) if teamObj is not None else None
            if not teamId:
                continue

            # Only create rookie templates for actual rookies (just generated this offseason)
            if getattr(player, 'seasonsPlayed', 1) > 0:
                continue

            rating = getattr(player, 'playerRating', None)
            if rating is None:
                continue

            positionValue = player.position.value if hasattr(player.position, 'value') else int(player.position)

            for edition, threshold in EDITION_THRESHOLDS.items():
                if rating < threshold:
                    continue
                buckets.setdefault((edition, positionValue), []).append((player, teamId))

        for (edition, positionValue), members in buckets.items():
            # topUp=False — the season pool already covers every effect; topping up here
            # would mint the whole effect set for a handful of rookies.
            plan = self._assignEffects(edition, positionValue,
                                       [m[0] for m in members], topUp=False)
            teamById = {m[0].id: m[1] for m in members}
            for player, effectName in plan:
                rating = getattr(player, 'playerRating', None)
                teamId = teamById.get(player.id)
                effectConfig = _buildEffectConfig(edition, rating, positionValue, teamId,
                                                  forceEffect=effectName)
                rarityWeight = computeRarityWeight(edition, rating)
                sellValue = getSellValue(edition, isActive=True)

                templates.append(CardTemplate(
                    player_id=player.id,
                    edition=edition,
                    season_created=seasonNumber,
                    is_rookie=True,  # These are new rookies
                    player_name=player.name,
                    team_id=teamId,
                    player_rating=rating,
                    position=positionValue,
                    effect_config=effectConfig,
                    rarity_weight=rarityWeight,
                    sell_value=sellValue,
                    classification="rookie",
                    output_type=getEffectOutputType(effectConfig.get("effectName")),
                ))

        if templates:
            templateRepo.saveBatch(templates)
            logger.info(f"Generated {len(templates)} rookie card templates for season {seasonNumber}")

        return len(templates)

    def serializeCard(self, userCard, currentSeason: int) -> dict:
        """Serialize a UserCard + its template into an API-friendly dict."""
        template = userCard.card_template
        isActive = template.season_created == currentSeason
        sellValue = getSellValue(template.edition, isActive=isActive)

        effectConfig = template.effect_config or {}
        classification = template.classification

        # Rookie classification doubles sell value
        if classification and "rookie" in classification:
            sellValue *= 2
        # Upgraded cards are worth more to sell, matching their Combine value.
        from constants import CARD_TIER_MULT as _CTM
        sellValue = max(1, int(sellValue * _CTM.get(getattr(userCard, "tier", 1) or 1, 1.0)))

        # ⚠️ The LIVE map first, the stored value only for an effect it has never heard
        # of. Reading the stored category back meant the Conditional badge (and the
        # longshot doubling that rides the same field, see cardEffectCalculator) outlived
        # a re-categorisation on every card already minted — reported as Showoff still
        # showing the badge. Same rule the detail/tooltip below already follow.
        from managers.cardEffects import EFFECT_CATEGORY
        effectName = effectConfig.get("effectName", "")
        category = EFFECT_CATEGORY.get(effectName) or effectConfig.get("category") or "flat_fp"

        # Always re-derive outputType from current category (handles reclassified effects)
        from managers.cardEffects import _deriveOutputType
        outputType = _deriveOutputType(category, effectName, effectConfig.get("primary", {}))

        # Rebuild detail/tooltip/tagline from current templates + stored params
        # so template updates apply to existing cards without DB migration
        from managers.cardEffects import EFFECT_DETAIL_TEMPLATES, EFFECT_TOOLTIPS, EFFECT_TAGLINES, STAT_DISPLAY_NAMES, POSITION_LABELS
        import re as _re
        primary = effectConfig.get("primary", {})
        # Inject posLabel from card position if missing (legacy cards)
        if "posLabel" not in primary:
            primary["posLabel"] = POSITION_LABELS.get(template.position, "??")
        # Rebuild templates from current templates + stored primary params
        def _rebuildTemplates(params):
            for tField, tDict in [("detail", EFFECT_DETAIL_TEMPLATES), ("tooltip", EFFECT_TOOLTIPS), ("tagline", EFFECT_TAGLINES)]:
                tpl = tDict.get(effectName, "")
                if tpl:
                    for key, val in params.items():
                        tpl = tpl.replace("{" + key + "}", str(val))
                    statKey = params.get("stat", "")
                    if statKey:
                        tpl = tpl.replace("{statDisplay}", STAT_DISPLAY_NAMES.get(statKey, statKey))
                    tpl = _re.sub(r'\{[a-zA-Z_]+\}', '?', tpl)
                    effectConfig[tField] = tpl

        _rebuildTemplates(primary)

        # If detail still has unresolved '?' placeholders, stored params are stale —
        # regenerate from current builder
        if "?" in effectConfig.get("detail", ""):
            from managers.cardEffects import rebuildPrimaryParams
            edScale = effectConfig.get("editionScale", 1.0)
            freshPrimary = rebuildPrimaryParams(effectName, template.player_rating, edScale)
            freshPrimary["posLabel"] = primary.get("posLabel", POSITION_LABELS.get(template.position, "??"))
            primary = freshPrimary
            _rebuildTemplates(primary)
            # Re-derive output type with fresh params
            outputType = _deriveOutputType(category, effectName, primary)

        # Upgrade tier: make the DISPLAYED values reflect the card's tier (the
        # calc already scales the actual output). Rebuilding the primary at
        # editionScale x tierMult scales output params (they're editionScale-
        # multiplied in the builders) while leaving thresholds/counts/chances
        # untouched, so detail/tagline/tooltip show the tiered numbers.
        # Structural (no-own-output) cards instead append their flat dividend.
        tierNote = None  # distinct line shown under the description for tiered cards
        tier = getattr(userCard, "tier", 1) or 1
        if tier > 1:
            from constants import (
                CARD_TIER_MULT, CARD_TIER_DIVIDEND_FP, CARD_TIER_DIVIDEND_FLOOBITS,
            )
            from managers.cardEffects import rebuildPrimaryParams
            tierMult = CARD_TIER_MULT.get(tier, 1.0)
            tierRoman = {1: "I", 2: "II", 3: "III", 4: "IV"}.get(tier, str(tier))
            prim = effectConfig.get("primary") or {}
            # No flat dividend anymore — every amplifier/meta card scales a real
            # knob (advantage's roll count is handled in the strength merge below).
            isStructural = False
            baseDetail = effectConfig.get("detail") or ""
            if isStructural:
                # No own output — show the flat per-tier dividend (edition-banded).
                edition = template.edition or "metallic"
                divFloob = CARD_TIER_DIVIDEND_FLOOBITS.get(edition, {}).get(tier, 0)
                divFP = CARD_TIER_DIVIDEND_FP.get(edition, {}).get(tier, 0.0)
                if outputType == "floobits" and divFloob:
                    tierNote = f"Tier {tierRoman}: +{divFloob} Floobits"
                elif divFP:
                    fp = int(divFP) if float(divFP).is_integer() else divFP
                    tierNote = f"Tier {tierRoman}: +{fp} FP"
            else:
                # Scale the STORED params (drift-free) by the builder's own
                # per-key behavior. OUTPUT params are detected with a 2x probe
                # (a true threshold/count doesn't move with editionScale; an
                # output param does). Output params then scale:
                #   - mult-value keys -> scale the DELTA (keep the 1.0 base)
                #   - INVERSE params (fat_cat's floobitsPerFP, which goes DOWN as
                #     the card gets stronger) -> scale by their builder ratio
                #   - normal additive -> scale by tierMult directly and show a
                #     decimal, so small integers (e.g. 2 Floobits/reception) move
                #     visibly instead of int-rounding flat.
                edScale = effectConfig.get("editionScale", 1.0)
                baseR = rebuildPrimaryParams(effectName, template.player_rating, edScale) or {}
                tierR = rebuildPrimaryParams(effectName, template.player_rating, edScale * tierMult) or {}
                bigR = rebuildPrimaryParams(effectName, template.player_rating, edScale * 2.0) or {}
                MULT_VAL = {"xMultValue", "baseXMult", "baseMult", "enhancedMult", "maxMult", "q4MultFactor"}
                rewardIsMult = effectName in ("bandwagon", "stack", "backfield_buddies", "full_roster")

                def _fmt(v):
                    if float(v).is_integer():
                        return int(v)
                    a = abs(v)
                    # tiny per-unit FPx (e.g. vagabond ~0.02/swap) needs 3 dp so
                    # adjacent tiers don't round to the same 2-dp value
                    if a < 0.1:
                        return round(v, 3)
                    return round(v, 2) if a < 1 else round(v, 1)

                scaled = dict(primary)
                for k, bv in baseR.items():
                    bigv = bigR.get(k)
                    sv = scaled.get(k)
                    if k == "gates" and isinstance(bv, list) and isinstance(sv, list) and bigv != bv:
                        scaled[k] = [{**g, "fp": _fmt(g.get("fp", 0) * tierMult)} for g in sv]
                        continue
                    if not (isinstance(bv, (int, float)) and isinstance(sv, (int, float))):
                        continue
                    # Only scale params that respond to editionScale (output), not
                    # thresholds/counts (which the 2x probe leaves unchanged).
                    if not isinstance(bigv, (int, float)) or bv == bigv:
                        continue
                    if k in MULT_VAL or (k == "rewardValue" and rewardIsMult) \
                            or (k == "baseReward" and scaled.get("rewardType") == "mult" and sv >= 1.0):
                        scaled[k] = round(1 + (sv - 1) * tierMult, 2)  # scale the FPx delta
                    elif bigv < bv:                                     # inverse param
                        tv = tierR.get(k, bv)
                        scaled[k] = _fmt(sv * ((tv / bv) if bv else tierMult))
                    else:                                              # normal additive output
                        scaled[k] = _fmt(sv * tierMult)
                _FULL_MULT = {
                    "xMultValue": "xMultDelta", "baseXMult": "baseXDelta",
                    "baseMult": "baseDelta", "enhancedMult": "enhancedDelta",
                    "maxMult": "maxDelta", "q4MultFactor": "q4MultDelta",
                }
                for fk, dk in _FULL_MULT.items():
                    if isinstance(scaled.get(fk), (int, float)):
                        scaled[dk] = round(scaled[fk] - 1, 2)
                if rewardIsMult and isinstance(scaled.get("rewardValue"), (int, float)) and scaled["rewardValue"] >= 1.0:
                    scaled["rewardDelta"] = round(scaled["rewardValue"] - 1, 2)
                if scaled.get("rewardType") == "mult" and isinstance(scaled.get("baseReward"), (int, float)) \
                        and scaled["baseReward"] >= 1.0:
                    scaled["baseRewardDelta"] = round(scaled["baseReward"] - 1, 2)
                # Amplifier strength params (conductor %, doubler/surveyor/
                # sharpshooter mult, catalyst chance ramp) aren't editionScale-
                # driven, so the loop above misses them — overlay their tier-scaled
                # values so the description matches the calc.
                from managers.cardEffects import tierScaledStrength
                scaled.update(tierScaledStrength(effectName, primary, tierMult))
                if effectName == "advantage":  # roll count scales with tier (I=2, IV=5)
                    scaled["rollCount"] = tier + 1
                scaled["posLabel"] = primary.get("posLabel", POSITION_LABELS.get(template.position, "??"))
                _rebuildTemplates(scaled)
                # If nothing in the text changed (Copycat copies dynamically,
                # Odometer lists yard thresholds), spell out the multiplier.
                if (effectConfig.get("detail") or "") == baseDetail:
                    tierNote = f"Tier {tierRoman}: ×{tierMult:g} output"

        # Edition secondary bonuses removed — edition now determines effect tier only
        effectConfig.pop("secondary", None)

        teamColor = None
        if template.team and hasattr(template.team, 'color'):
            teamColor = template.team.color

        return {
            "id": userCard.id,
            "templateId": template.id,
            "playerId": template.player_id,
            "playerName": template.player_name,
            "teamId": template.team_id,
            "teamColor": teamColor,
            "playerRating": template.player_rating,
            "ratingStars": min(5, max(1, (template.player_rating - 60) // 8 + 1)),
            "position": template.position,
            "edition": template.edition,
            "tier": getattr(userCard, "tier", 1) or 1,
            "tierNote": tierNote,
            "vaulted": bool(getattr(userCard, "vaulted", False)),
            "vaultPosition": getattr(userCard, "vault_position", None),
            # Glitch (docs/GLITCH_CARDS.md) — per-INSTANCE, so it rides on the userCard
            # rather than the template. Drives the card's visual treatment.
            "glitched": bool(getattr(userCard, "glitched", False)),
            "glitchedSeason": getattr(userCard, "glitched_season", None),
            "glitchedWeek": getattr(userCard, "glitched_week", None),
            "seasonCreated": template.season_created,
            "isRookie": template.is_rookie,
            "classification": classification,
            "effectConfig": effectConfig,
            "effectName": effectConfig.get("effectName"),
            "displayName": effectConfig.get("displayName"),
            "category": category,
            "outputType": outputType,
            "tagline": effectConfig.get("tagline"),
            "tooltip": effectConfig.get("tooltip"),
            "detail": effectConfig.get("detail"),
            "gateText": effectConfig.get("gateText"),
            # Positions this effect can validly land on via a transplant (shared effects
            # span all five; position-specific ones only their own).
            "validPositions": sorted(_effectValidPositions(effectName)),
            "sellValue": sellValue,
            "combineValue": getCardValue(userCard, currentSeason),
            "isActive": isActive,
            "acquiredAt": userCard.acquired_at.isoformat() + 'Z' if userCard.acquired_at else None,
            "acquiredVia": userCard.acquired_via,
        }

    def sellCards(self, session, userId: int, userCardIds: List[int], currentSeason: int,
                  currentWeek: int = 0) -> dict:
        """Sell one or more cards from a user's collection.

        Returns dict with totalFloobits earned and count of cards sold.
        Raises ValueError if any card doesn't belong to the user or is currently equipped.
        """
        from database.repositories.card_repositories import (
            UserCardRepository, CurrencyRepository, EquippedCardRepository
        )
        from database.models import EquippedCard

        cardRepo = UserCardRepository(session)
        currencyRepo = CurrencyRepository(session)

        # Fetch all requested cards
        cards = cardRepo.getByIds(userCardIds, userId)
        if len(cards) != len(userCardIds):
            foundIds = {c.id for c in cards}
            missingIds = [cid for cid in userCardIds if cid not in foundIds]
            raise ValueError(f"Cards not found or not owned: {missingIds}")

        # Check none are currently equipped (this week only)
        equippedIds = {
            ec.user_card_id
            for ec in session.query(EquippedCard)
            .filter(
                EquippedCard.user_card_id.in_(userCardIds),
                EquippedCard.user_id == userId,
                EquippedCard.season == currentSeason,
                EquippedCard.week == currentWeek,
            )
            .all()
        }
        if equippedIds:
            raise ValueError(f"Cannot sell equipped cards: {list(equippedIds)}")

        # Vaulted cards are permanent — they can't be sold.
        vaultedIds = [c.id for c in cards if getattr(c, "vaulted", False)]
        if vaultedIds:
            raise ValueError(f"Cannot sell vaulted cards: {vaultedIds}")

        # Calculate total and sell (Rookie classification = 2x sell value)
        totalFloobits = 0
        for card in cards:
            isActive = card.card_template.season_created == currentSeason
            cardValue = getSellValue(card.card_template.edition, isActive=isActive)
            classification = card.card_template.classification or ""
            if "rookie" in classification:
                cardValue *= 2
            from constants import CARD_TIER_MULT as _CTM
            cardValue = max(1, int(cardValue * _CTM.get(getattr(card, "tier", 1) or 1, 1.0)))
            totalFloobits += cardValue

        currencyRepo.addFunds(
            userId, totalFloobits,
            transactionType='card_sell',
            description=f"Sold {len(cards)} card(s)",
        )

        cardRepo.deleteBatch(cards)

        return {"totalFloobits": totalFloobits, "cardsSold": len(cards)}

    # ─── The Combine (Card Upgrades) ──────────────────────────────────────────

    def _validateUpgradeCards(self, session, userId: int, cardIds: List[int],
                              currentSeason: int = 0, currentWeek: int = 0,
                              allowEquippedIds=None):
        """Validate cards for upgrade: owned by user and not equipped this week.
        `allowEquippedIds` exempts specific cards from the equipped check (Level
        Up exempts its target, so you can upgrade a card you're running).
        Returns list of UserCard objects with templates loaded.
        """
        allowEquippedIds = set(allowEquippedIds or ())
        from database.repositories.card_repositories import UserCardRepository
        from database.models import EquippedCard

        cardRepo = UserCardRepository(session)
        cards = cardRepo.getByIds(cardIds, userId)
        if len(cards) != len(cardIds):
            foundIds = {c.id for c in cards}
            missingIds = [cid for cid in cardIds if cid not in foundIds]
            raise ValueError(f"Cards not found or not owned: {missingIds}")

        # Vaulted cards are permanent — can't be Combined or fed to a Level Up.
        vaultedIds = [c.id for c in cards if getattr(c, "vaulted", False)]
        if vaultedIds:
            raise ValueError(f"Cannot use vaulted cards: {vaultedIds}")

        equippedRows = session.query(EquippedCard).filter(
            EquippedCard.user_card_id.in_(cardIds),
            EquippedCard.user_id == userId,
            EquippedCard.season == currentSeason,
            EquippedCard.week == currentWeek,
        ).all()
        equippedIds = {ec.user_card_id for ec in equippedRows} - allowEquippedIds
        if equippedIds:
            raise ValueError(f"Cannot use equipped cards: {list(equippedIds)}")

        return cards

    def _createUpgradedTemplate(self, session, sourceTemplate, newEdition: str,
                                 forceEffect: str = None, currentSeason: int = 0):
        """Create a new CardTemplate for an upgraded card."""
        from database.models import CardTemplate
        from database.repositories.card_repositories import CardTemplateRepository

        effectConfig = _buildEffectConfig(
            newEdition, sourceTemplate.player_rating,
            sourceTemplate.position, sourceTemplate.team_id,
            forceEffect=forceEffect,
        )
        isActive = sourceTemplate.season_created == currentSeason
        template = CardTemplate(
            player_id=sourceTemplate.player_id,
            edition=newEdition,
            season_created=sourceTemplate.season_created,
            is_rookie=sourceTemplate.is_rookie,
            classification=sourceTemplate.classification,
            player_name=sourceTemplate.player_name,
            team_id=sourceTemplate.team_id,
            player_rating=sourceTemplate.player_rating,
            position=sourceTemplate.position,
            effect_config=effectConfig,
            rarity_weight=computeRarityWeight(newEdition, sourceTemplate.player_rating),
            sell_value=getSellValue(newEdition, isActive=isActive),
            is_upgraded=True,
            output_type=getEffectOutputType(effectConfig.get("effectName")),
        )
        templateRepo = CardTemplateRepository(session)
        return templateRepo.save(template)

    def blendCards(self, session, userId: int, offeringCardIds: List[int],
                   currentSeason: int, currentWeek: int = 0) -> dict:
        """The Combine: Sacrifice multiple cards to create one new random card.

        The result edition is determined by total classification-aware value
        of the sacrificed cards.
        """
        from database.models import CardTemplate, UserCard, CardUpgradeLog
        from database.repositories.card_repositories import (
            UserCardRepository, CardTemplateRepository,
        )

        if len(offeringCardIds) < 2:
            raise ValueError("The Combine requires at least 2 cards")

        # Deduplicate
        offeringCardIds = list(set(offeringCardIds))

        cards = self._validateUpgradeCards(session, userId, offeringCardIds,
                                           currentSeason, currentWeek)

        # Sum classification-aware values
        totalValue = sum(getCardValue(card, currentSeason) for card in cards)

        # Determine result edition from thresholds
        resultEdition = 'metallic'
        for threshold, edition in BLENDER_THRESHOLDS:
            if totalValue >= threshold:
                resultEdition = edition
                break

        # Pick random player meeting rating gate for result edition
        templateRepo = CardTemplateRepository(session)
        allTemplates = templateRepo.getBySeason(currentSeason)
        minRating = EDITION_THRESHOLDS.get(resultEdition, 0)

        # Get unique eligible players. Skip templates with NULL team_id —
        # those are leftovers from past prospect/rookie pollution, and
        # picking one as a blend source would propagate the bad state.
        eligiblePlayers = {}
        for t in allTemplates:
            if t.team_id is None:
                continue
            if t.player_rating >= minRating and t.player_id not in eligiblePlayers:
                eligiblePlayers[t.player_id] = t

        if not eligiblePlayers:
            raise ValueError(f"No eligible players for {resultEdition} edition")

        sourceTemplate = random.choice(list(eligiblePlayers.values()))

        # Recompute the classification for the RESULT edition. sourceTemplate is
        # the first template found for the player (the base edition), whose
        # classification is empty because MVP / champion / all-pro require
        # holographic+ — copying it strips the CH/MVP/AP tag off a holo+ blend
        # result. Derive this season's accolade sets from the classified
        # templates and rebuild for resultEdition.
        mvpPlayerId = next((t.player_id for t in allTemplates
                            if t.classification and 'mvp' in t.classification), None)
        championPlayerIds = {t.player_id for t in allTemplates
                             if t.classification and 'champion' in t.classification}
        allProPlayerIds = {t.player_id for t in allTemplates
                           if t.classification and 'all_pro' in t.classification}
        resultClassification = _buildClassification(
            sourceTemplate.player_id, sourceTemplate.is_rookie,
            mvpPlayerId, championPlayerIds, allProPlayerIds, resultEdition,
        )

        # Create new template (random effect — no forceEffect)
        effectConfig = _buildEffectConfig(
            resultEdition, sourceTemplate.player_rating,
            sourceTemplate.position, sourceTemplate.team_id,
        )
        isActive = sourceTemplate.season_created == currentSeason
        newTemplate = CardTemplate(
            player_id=sourceTemplate.player_id,
            edition=resultEdition,
            season_created=currentSeason,
            is_rookie=sourceTemplate.is_rookie,
            classification=resultClassification,
            player_name=sourceTemplate.player_name,
            team_id=sourceTemplate.team_id,
            player_rating=sourceTemplate.player_rating,
            position=sourceTemplate.position,
            effect_config=effectConfig,
            rarity_weight=computeRarityWeight(resultEdition, sourceTemplate.player_rating),
            sell_value=getSellValue(resultEdition, isActive=isActive),
            is_upgraded=True,
            output_type=getEffectOutputType(effectConfig.get("effectName")),
        )
        templateRepo.save(newTemplate)

        # Create new UserCard
        newCard = UserCard(
            user_id=userId,
            card_template_id=newTemplate.id,
            acquired_via="blend",
        )
        session.add(newCard)
        session.flush()

        # Delete all offerings
        cardRepo = UserCardRepository(session)
        cardRepo.deleteBatch(cards)

        # Log
        session.add(CardUpgradeLog(
            user_id=userId,
            upgrade_type="blend",
            offering_user_card_ids=offeringCardIds,
            new_template_id=newTemplate.id,
            floobits_spent=0,
        ))
        session.flush()

        return self.serializeCard(newCard, currentSeason)

    def previewBlend(self, session, userId: int, offeringCardIds: List[int],
                     currentSeason: int, currentWeek: int = 0) -> dict:
        """Preview The Combine result (edition only — player/effect are random)."""
        if len(offeringCardIds) < 2:
            raise ValueError("The Combine requires at least 2 cards")

        offeringCardIds = list(set(offeringCardIds))
        cards = self._validateUpgradeCards(session, userId, offeringCardIds,
                                           currentSeason, currentWeek)

        totalValue = sum(getCardValue(card, currentSeason) for card in cards)

        resultEdition = 'metallic'
        for threshold, edition in BLENDER_THRESHOLDS:
            if totalValue >= threshold:
                resultEdition = edition
                break

        return {
            "totalValue": totalValue,
            "resultEdition": resultEdition,
            "cardCount": len(cards),
        }

    def _validateTransplantPair(self, session, userId: int, donorCardId: int,
                                targetCardId: int, currentSeason: int, currentWeek: int = 0):
        """Validate a donor/target pair for a transplant. Returns (donor, target)
        UserCards, or raises ValueError. Gate: same edition, both effect-bearing (not
        the no-effect floor), not already the same effect, and — for a position-specific
        donor effect — the target's position must be one the effect is valid for (shared
        effects go on any same-edition card)."""
        if donorCardId == targetCardId:
            raise ValueError("Pick two different cards")
        cards = self._validateUpgradeCards(session, userId, [donorCardId, targetCardId],
                                           currentSeason, currentWeek)
        byId = {c.id: c for c in cards}
        donor, target = byId[donorCardId], byId[targetCardId]
        dt, tt = donor.card_template, target.card_template
        if dt.edition == 'base' or tt.edition == 'base':
            raise ValueError("No-effect (Base) cards can't be transplanted")
        donorEffect = self._effectName(donor)
        if not donorEffect or donorEffect in ('none', ''):
            raise ValueError("The donor card has no effect to transplant")
        if dt.edition != tt.edition:
            raise ValueError("Both cards must be the same edition")
        # Position-specific effects can only land on a player whose position they're
        # valid for; shared effects go on any same-edition card.
        from managers.cardEffects import effectValidPositions
        valid = effectValidPositions(donorEffect)
        if valid and tt.position not in valid:
            posName = {1: 'QB', 2: 'RB', 3: 'WR', 4: 'TE', 5: 'K'}.get(tt.position, 'that')
            raise ValueError(f"{donorEffect} is position-specific and can't go on a {posName} card")
        if donorEffect == self._effectName(target):
            raise ValueError("Both cards already have that effect")
        return donor, target

    def previewTransplant(self, session, userId: int, donorCardId: int,
                          targetCardId: int, currentSeason: int, currentWeek: int = 0) -> dict:
        """Validate a transplant pairing and return its cost + summary (or raise)."""
        from constants import TRANSPLANT_COST_BY_EDITION
        donor, target = self._validateTransplantPair(session, userId, donorCardId,
                                                     targetCardId, currentSeason, currentWeek)
        edition = target.card_template.edition
        return {
            "cost": TRANSPLANT_COST_BY_EDITION.get(edition, 0),
            "edition": edition,
            "donorEffect": self._effectName(donor),
            "targetEffect": self._effectName(target),
            "donorPlayer": donor.card_template.player_name,
            "targetPlayer": target.card_template.player_name,
        }

    def transplantEffect(self, session, userId: int, donorCardId: int,
                         targetCardId: int, currentSeason: int, currentWeek: int = 0) -> dict:
        """Graft the donor card's effect onto the target player card (same edition +
        position). The target keeps its identity, upgrade tier and vault state and
        takes on the donor's effect (re-scaled to the target's rating, so a high-rating
        donor can't dump strong params on a weaker player); the donor is consumed.
        Costs Floobits scaling with edition."""
        from database.models import CardUpgradeLog
        from database.repositories.card_repositories import (
            UserCardRepository, CurrencyRepository,
        )
        from constants import TRANSPLANT_COST_BY_EDITION

        donor, target = self._validateTransplantPair(session, userId, donorCardId,
                                                     targetCardId, currentSeason, currentWeek)
        tt = target.card_template
        donorEffect = self._effectName(donor)
        edition = tt.edition
        cost = TRANSPLANT_COST_BY_EDITION.get(edition, 0)

        if cost > 0:
            currencyRepo = CurrencyRepository(session)
            result = currencyRepo.spendFunds(
                userId, cost,
                transactionType="card_transplant",
                description=f"Transplanted {donorEffect} onto {tt.player_name}",
                season=currentSeason,
            )
            if result is None:
                raise ValueError("Insufficient Floobits")

        oldTemplateId = target.card_template_id
        # Mint an upgraded template on the TARGET's identity/rating carrying the donor's
        # effect. Classification follows the target player (baked into _createUpgradedTemplate).
        newTemplate = self._createUpgradedTemplate(session, tt, edition,
                                                   forceEffect=donorEffect,
                                                   currentSeason=currentSeason)
        # Assign the relationship (not just the FK) so the in-session view + serialized
        # result reflect the new template immediately. Keeps tier + vault + identity.
        target.card_template = newTemplate
        UserCardRepository(session).deleteBatch([donor])
        session.add(CardUpgradeLog(
            user_id=userId,
            upgrade_type="transplant",
            subject_user_card_id=target.id,
            offering_user_card_ids=[donor.id],
            old_template_id=oldTemplateId,
            new_template_id=newTemplate.id,
            floobits_spent=cost,
        ))
        session.flush()
        return self.serializeCard(target, currentSeason)

    # ─── Card Upgrade Tiers (Level Up) ────────────────────────────────────────

    @staticmethod
    def _effectName(card) -> str:
        return ((card.card_template.effect_config or {}).get("effectName") or "")

    def _tierUpgradeCost(self, card, toTier: int) -> int:
        """Floobit cost to level a card INTO toTier (2-4), edition-scaled and
        rounded to the nearest 10 so costs read clean (not 94 / 312)."""
        from constants import CARD_TIER_UPGRADE_COST, CARD_TIER_EDITION_COST_MULT
        base = CARD_TIER_UPGRADE_COST.get(toTier)
        if base is None:
            return 0
        edMult = CARD_TIER_EDITION_COST_MULT.get(card.card_template.edition, 1.0)
        return int(round(base * edMult / 10.0)) * 10

    def getUpgradeInfo(self, session, userId: int, targetCardId: int,
                       currentSeason: int) -> dict:
        """Cost + eligible same-effect duplicates the UI can offer to feed."""
        from database.repositories.card_repositories import UserCardRepository
        from constants import CARD_TIER_MAX
        cardRepo = UserCardRepository(session)
        target = cardRepo.getByIds([targetCardId], userId)
        if not target:
            raise ValueError("Card not found or not owned")
        target = target[0]
        effect = self._effectName(target)
        atMax = target.tier >= CARD_TIER_MAX
        nextTier = target.tier + 1
        # A card is "expired" if it was created in a prior season.
        targetActive = target.card_template.season_created == currentSeason
        # Eligible offerings: any OTHER owned card with the same effect that
        # isn't vaulted (vaulted cards are permanent and can't be fed/consumed).
        # Expired cards cannot feed an ACTIVE card's upgrade — but if the target
        # is itself expired, that restriction lifts and any same-effect card works.
        offerings = [
            c for c in cardRepo.getByUser(userId)
            if c.id != target.id and not getattr(c, "vaulted", False)
            and self._effectName(c) == effect
            and (not targetActive or c.card_template.season_created == currentSeason)
        ]
        # Preview: serialize the card AS IF it were already at the next tier so
        # the UI can show what the upgrade buys (tiered detail / tagline /
        # tierNote / combineValue) before the user commits. Read-only — restore
        # the tier immediately; this method never commits.
        preview = None
        if not atMax:
            originalTier = target.tier
            try:
                target.tier = nextTier
                preview = self.serializeCard(target, currentSeason)
            finally:
                target.tier = originalTier
        return {
            "cardId": target.id,
            "effectName": effect,
            "tier": target.tier,
            "maxTier": CARD_TIER_MAX,
            "atMax": atMax,
            "nextTier": None if atMax else nextTier,
            "cost": None if atMax else self._tierUpgradeCost(target, nextTier),
            "eligibleOfferings": [self.serializeCard(c, currentSeason) for c in offerings],
            # Card serialized at nextTier (None at max). The UI diffs this against
            # the current card to show the increase.
            "preview": preview,
        }

    def levelUpCard(self, session, userId: int, targetCardId: int,
                    offeringCardId: int, currentSeason: int,
                    currentWeek: int = 0) -> dict:
        """Level a card I->IV by consuming ONE same-effect duplicate + Floobits.

        Same effect ⇒ same edition (effects are edition-locked), so the duplicate
        is a free rarity gate. The duplicate is destroyed; the target gains +1 tier.
        """
        from database.models import CardUpgradeLog
        from database.repositories.card_repositories import (
            UserCardRepository, CurrencyRepository,
        )
        from constants import CARD_TIER_MAX

        if targetCardId == offeringCardId:
            raise ValueError("Target and offering must be different cards")

        # Ownership + not-equipped-this-week (reuses Combine validation). The
        # target may be equipped — you can upgrade a card you're currently running;
        # only the consumed offering must be unequipped.
        cards = self._validateUpgradeCards(session, userId,
                                           [targetCardId, offeringCardId],
                                           currentSeason, currentWeek,
                                           allowEquippedIds={targetCardId})
        byId = {c.id: c for c in cards}
        target, offering = byId[targetCardId], byId[offeringCardId]

        if target.tier >= CARD_TIER_MAX:
            raise ValueError("Card is already at max tier")
        if self._effectName(target) != self._effectName(offering):
            raise ValueError("Offering must have the same effect as the target")
        # Expired cards (created a prior season) cannot feed an ACTIVE card's
        # upgrade. If the target is itself expired, the restriction lifts.
        targetActive = target.card_template.season_created == currentSeason
        offeringActive = offering.card_template.season_created == currentSeason
        if targetActive and not offeringActive:
            raise ValueError("An expired card cannot be used to upgrade an active card")

        toTier = target.tier + 1
        cost = self._tierUpgradeCost(target, toTier)

        currencyRepo = CurrencyRepository(session)
        result = currencyRepo.spendFunds(
            userId, cost,
            transactionType="card_level_up",
            description=f"Leveled {self._effectName(target)} to tier {toTier}",
            season=currentSeason,
        )
        if result is None:
            raise ValueError("Insufficient Floobits")

        target.tier = toTier
        UserCardRepository(session).deleteBatch([offering])
        session.add(CardUpgradeLog(
            user_id=userId,
            upgrade_type="level_up",
            subject_user_card_id=target.id,
            offering_user_card_ids=[offering.id],
            # Level Up keeps the same template (only the instance's tier changes);
            # point both at the target's template so the NOT NULL column is satisfied.
            old_template_id=target.card_template_id,
            new_template_id=target.card_template_id,
            floobits_spent=cost,
        ))
        session.flush()
        return self.serializeCard(target, currentSeason)

    # ─── Card Vault (permanent collection) ────────────────────────────────────

    def vaultCard(self, session, userId: int, cardId: int, currentSeason: int,
                  currentWeek: int = 0) -> dict:
        """Permanently move a card into the user's Vault. IRREVERSIBLE — vaulted
        cards can no longer be equipped, sold, or Combined; they persist forever
        and drive collection achievements. Can't vault an equipped card."""
        from database.repositories.card_repositories import UserCardRepository, EquippedCardRepository
        cardRepo = UserCardRepository(session)
        cards = cardRepo.getByIds([cardId], userId)
        if not cards:
            raise ValueError("Card not found or not owned")
        card = cards[0]
        if getattr(card, "vaulted", False):
            raise ValueError("Card is already vaulted")
        equippedIds = EquippedCardRepository(session).getEquippedCardIds(userId, currentSeason, currentWeek)
        if card.id in equippedIds:
            raise ValueError("Unequip the card before vaulting it")
        card.vaulted = True
        card.vaulted_at = datetime.utcnow()
        session.flush()
        return self.serializeCard(card, currentSeason)

    def trashVaultedCard(self, session, userId: int, cardId: int) -> dict:
        """Permanently remove (trash) a vaulted card. Unlike selling, there's no
        Floobit return — it's a delete. Only vaulted cards can be trashed this
        way (un-vaulted cards are sold instead). Cleans up any showcase/equipped
        rows that reference it first so the delete can't orphan FK rows."""
        from database.repositories.card_repositories import UserCardRepository
        from database.models import ShowcaseSlot, EquippedCard
        cardRepo = UserCardRepository(session)
        cards = cardRepo.getByIds([cardId], userId)
        if not cards:
            raise ValueError("Card not found or not owned")
        card = cards[0]
        if not getattr(card, "vaulted", False):
            raise ValueError("Only vaulted cards can be trashed here")
        session.query(ShowcaseSlot).filter(
            ShowcaseSlot.user_id == userId, ShowcaseSlot.user_card_id == cardId,
        ).delete(synchronize_session=False)
        session.query(EquippedCard).filter(
            EquippedCard.user_id == userId, EquippedCard.user_card_id == cardId,
        ).delete(synchronize_session=False)
        cardRepo.delete(card)
        session.flush()
        return {"trashed": True, "cardId": cardId}

    def reorderVault(self, session, userId: int, orderedCardIds: list) -> dict:
        """Set the manual sort order of vaulted cards. `orderedCardIds` is the
        full desired order; each card's vault_position becomes its index. Only
        the user's own vaulted cards are repositioned."""
        from database.repositories.card_repositories import UserCardRepository
        cardRepo = UserCardRepository(session)
        cards = cardRepo.getByIds(orderedCardIds, userId)
        byId = {c.id: c for c in cards}
        pos = 0
        for cardId in orderedCardIds:
            card = byId.get(cardId)
            if card and getattr(card, "vaulted", False):
                card.vault_position = pos
                pos += 1
        session.flush()
        return {"reordered": pos}

    def buildPlayerSeasonStats(self, session, playerId: int, season: int, position: int):
        """High-level stat line for a vaulted card's back — the player's numbers
        for the season the card is from. A vaulted card drops its effect and
        becomes a keepsake, so the back shows who the player actually was that
        year. Returns None if no stats were recorded that season."""
        from database.models import PlayerSeasonStats, Team
        row = session.query(PlayerSeasonStats).filter_by(
            player_id=playerId, season=season,
        ).first()
        if not row:
            return None
        # Team the player actually suited up for that season (can differ from the
        # card's current team after a trade / FA move).
        teamName = None
        teamColor = None
        if row.team_id:
            team = session.get(Team, row.team_id)
            if team:
                teamName = team.name
                teamColor = team.color
        lines = []
        def add(label, value):
            lines.append({"label": label, "value": value})
        if position == 1:  # QB
            add("Pass Yds", row.passing_yards or 0)
            add("Pass TD", row.passing_tds or 0)
            add("INT", row.passing_ints or 0)
            if (row.rushing_yards or 0) > 0:
                add("Rush Yds", row.rushing_yards)
        elif position == 2:  # RB — no receiving game in this sim
            add("Rush Yds", row.rushing_yards or 0)
            add("Rush TD", row.rushing_tds or 0)
            add("Rush Att", row.rushing_attempts or 0)
        elif position in (3, 4):  # WR / TE
            add("Rec", row.receptions or 0)
            add("Rec Yds", row.receiving_yards or 0)
            add("Rec TD", row.receiving_tds or 0)
        elif position == 5:  # K
            k = row.kicking_stats or {}
            add("FG", f"{k.get('fgs', 0)}/{k.get('fgAtt', 0)}")
            if k.get('fgPerc'):
                add("FG%", k.get('fgPerc'))
            if k.get('xps'):
                add("XP", k.get('xps'))
            if k.get('fgAvg'):
                add("Avg", f"{k.get('fgAvg')} yd")
        # ⚠️ PER GAME, alongside the total (users asked). A season total answers "how
        # much did this player produce" and hides "how good were they" — a 14-game
        # injury-shortened year and a full one are not comparable on the total, and the
        # card back is exactly where a reader is comparing two players. Sent computed
        # rather than as a games count for the client to divide by, so every surface
        # showing this line quotes the same number.
        gamesPlayed = row.games_played or 0
        fantasyPoints = row.fantasy_points or 0
        return {
            "season": season,
            "teamName": teamName,
            "teamColor": teamColor,
            "fantasyPoints": fantasyPoints,
            "gamesPlayed": gamesPlayed,
            "fantasyPointsPerGame": (round(fantasyPoints / gamesPlayed, 1)
                                     if gamesPlayed > 0 else None),
            "lines": lines,
        }

    # ─── Pack Opening ─────────────────────────────────────────────────────────

    def openPack(self, session, userId: int, packTypeId: int, currentSeason: int,
                 skipCurrency: bool = False, source: str = "purchase",
                 currentWeek: int = 0) -> dict:
        """Buy and open a card pack — IMMEDIATE-grant flow (no selection).

        Used for achievement rewards / starter grants / any path where the
        user doesn't pick which cards to keep. Purchase flow with selection
        goes through revealPack + selectPackKeeps instead.

        Raises ValueError if insufficient Floobits or invalid pack type.
        """
        from database.models import CardTemplate, UserCard, PackOpening
        from database.repositories.card_repositories import (
            PackTypeRepository, CurrencyRepository, UserCardRepository,
            CardTemplateRepository, PackOpeningRepository,
        )

        packRepo = PackTypeRepository(session)
        currencyRepo = CurrencyRepository(session)
        cardRepo = UserCardRepository(session)
        templateRepo = CardTemplateRepository(session)
        openingRepo = PackOpeningRepository(session)

        packType = packRepo.getById(packTypeId)
        if not packType:
            raise ValueError("Invalid pack type")

        # Enforce daily purchase limit (skipped for free grants).
        # Only count paid openings — free grants (cost=0) must not
        # consume the daily limit.
        if not skipCurrency:
            dailyLimit = DAILY_PACK_LIMITS.get(packType.name)
            if dailyLimit is not None:
                from database.models import PackOpening
                now = datetime.utcnow()
                dayStart = now.replace(hour=0, minute=0, second=0, microsecond=0)
                todayCount = session.query(PackOpening).filter(
                    PackOpening.user_id == userId,
                    PackOpening.pack_type_id == packType.id,
                    PackOpening.opened_at >= dayStart,
                    PackOpening.cost > 0,
                ).count()
                if todayCount >= dailyLimit:
                    raise ValueError(f"Daily limit reached for {packType.display_name} ({dailyLimit}/day)")

            # Spend Floobits
            result = currencyRepo.spendFunds(
                userId, packType.cost,
                transactionType='pack_purchase',
                description=f"Opened {packType.display_name}",
                season=currentSeason,
            )
            if result is None:
                raise ValueError("Insufficient Floobits")

        drawnTemplates = self._drawPackCards(session, packType, currentSeason, currentWeek)

        # Create UserCard instances
        newCards: List[UserCard] = []
        acquiredVia = f"pack_{packType.name}"
        for template in drawnTemplates:
            _vault = _vaultOnAcquire(template, currentSeason, currentWeek)
            card = UserCard(
                user_id=userId,
                card_template_id=template.id,
                acquired_via=acquiredVia,
                vaulted=_vault,
                vaulted_at=datetime.utcnow() if _vault else None,
            )
            newCards.append(card)

        cardRepo.saveBatch(newCards)

        openingRecord = PackOpening(
            user_id=userId,
            pack_type_id=packType.id,
            cards_received=[t.id for t in drawnTemplates],
            cost=0 if skipCurrency else packType.cost,
        )
        openingRepo.save(openingRecord)

        serialized = []
        for card in newCards:
            session.refresh(card)
            serialized.append(self.serializeCard(card, currentSeason))

        return {
            "packName": packType.display_name,
            "cost": packType.cost,
            "cards": serialized,
        }

    def _drawPackCards(self, session, packType, currentSeason: int,
                       currentWeek: int = 0) -> list:
        """Shared draw routine: returns N templates per packType.cards_per_pack.

        Two extensions for the themed-pack rework:
          - theme_type/theme_value filter the candidate pool before edition rolling
            (position/team are direct column filters; output uses the denormalized
            CardTemplate.output_type so NULL-typed effects are excluded by design).
          - guaranteed_rarity forces ONE drawn slot to land at that edition (or
            higher); remaining slots roll the normal weights.
        """
        from database.repositories.card_repositories import CardTemplateRepository
        templateRepo = CardTemplateRepository(session)
        # LEGACY packs draw from PAST seasons, so they bypass the current-season
        # pool entirely — the only pack type that does. Everything downstream
        # (weights, guarantee, dedup) works unchanged on this pool.
        if getattr(packType, 'theme_type', None) == 'collection':
            allTemplates = getCollectionTemplates(
                session, currentSeason,
                includeCurrentSeason=regularSeasonOver(currentWeek),
            )
        else:
            allTemplates = templateRepo.getBySeason(currentSeason)
            # Skip any templates with NULL team_id — defensive guard against legacy
            # prospect/rookie templates polluting fresh pack rolls.
            allTemplates = [t for t in allTemplates if t.team_id is not None]
        # The no-effect FLOOR print (edition 'base') is the STARTER lineup ONLY: the starter
        # pack draws exclusively from it, and every OTHER pack excludes it (packs deliver
        # effect cards). Before the fusion edition rename this filter dropped 'standard';
        # the floor is now 'base', so the starter must select it, not skip it.
        if packType.name == 'starter':
            allTemplates = [t for t in allTemplates if t.edition == 'base']
        else:
            allTemplates = [t for t in allTemplates if t.edition != 'base']
        if not allTemplates:
            raise ValueError("No card templates available for the current season")

        # ── Themed-pack pool filter ──
        themeType = getattr(packType, 'theme_type', None)
        themeValue = getattr(packType, 'theme_value', None)
        if themeType:
            pool = _applyThemeFilter(
                allTemplates, themeType, themeValue,
                session=session, currentSeason=currentSeason,
            )
            if not pool:
                raise ValueError(f"No templates match this themed pack ({themeType}={themeValue or ''})")
        else:
            pool = allTemplates

        packWeights = packType.rarity_weights or EDITION_BASE_WEIGHTS
        count = packType.cards_per_pack
        guaranteedRarity = getattr(packType, 'guaranteed_rarity', None)
        # Prestige themed packs (champion / all-pro) draw from a narrow
        # pool of specific players, each with 1-4 edition templates. Without
        # dedup, a 5-card pack could land 5 templates of the same player.
        # These packs explicitly promise classification breadth (one card
        # per qualifying player), so dedup by player_id.
        dedupByPlayer = getattr(packType, 'theme_type', None) in ('champion', 'allpro')
        # EVERY pack avoids repeating an effect, not just the starter. Opening a pack and
        # getting the same effect two or three times is the single most reported
        # frustration with packs, and it is not what a pack is for: you buy one to see
        # what is in the pool, and a repeat spends a slot telling you nothing. The pool
        # can no longer satisfy it (a themed pack over a thin position, say) and the
        # dedup falls through to whatever is left, so this can never return short.
        dedupByEffect = True

        # Starter pack: hand a full ONE-PER-POSITION lineup (QB/RB/WR/TE/K) with
        # distinct players and effects, so a new user can equip the entire pack as a
        # complete, legal lineup. Overrides the generic weighted draw below.
        if packType.name == 'starter':
            return self._drawStarterLineup(pool, packWeights)

        # ── Guaranteed-rarity slot ──
        # If the pack guarantees a minimum rarity, draw one slot constrained
        # to that rarity (or higher) and fill the rest with normal weights.
        if guaranteedRarity:
            qualifying = self._editionsAtOrAbove(guaranteedRarity)
            guaranteedPool = [t for t in pool if t.edition in qualifying]
            if guaranteedPool:
                guaranteedDraw = self._weightedDraw(
                    guaranteedPool, packWeights, count=1
                )
                # The rest of the pack must also avoid the guaranteed card's effect —
                # this branch used to drop to a plain weighted draw, so the pack most
                # likely to repeat itself was the one you paid extra for.
                excludedPlayerIds = (
                    {t.player_id for t in guaranteedDraw} if dedupByPlayer else set()
                )
                guaranteedEffects = {
                    (getattr(t, 'effect_config', None) or {}).get('effectName')
                    for t in guaranteedDraw
                } - {None, ''}
                restPool = [
                    t for t in pool
                    if t.player_id not in excludedPlayerIds
                    and (getattr(t, 'effect_config', None) or {}).get('effectName')
                    not in guaranteedEffects
                ]
                # Never let filtering empty the pool — a short pack is worse than a repeat.
                if not restPool:
                    restPool = pool
                rest = self._weightedDrawDedup(
                    restPool, packWeights, count=max(0, count - 1),
                    dedupByPlayer=dedupByPlayer,
                    dedupByEffect=dedupByEffect,
                )
                return guaranteedDraw + rest
            # Fallback to unconstrained draw if no eligible templates exist

        if dedupByPlayer or dedupByEffect:
            return self._weightedDrawDedup(
                pool, packWeights, count=count,
                dedupByPlayer=dedupByPlayer,
                dedupByEffect=dedupByEffect,
            )
        return self._weightedDraw(pool, packWeights, count=count)

    def _drawStarterLineup(self, pool: list, packWeights: dict) -> list:
        """Draw a full starter lineup covering every lineup slot — QB/RB/WR/WR/TE/K
        (two WR cards for the WR1 + WR2 slots) — with distinct players AND distinct
        effects so the whole pack is equippable at once. Restricted to the editions
        the pack allows (base-only for the starter)."""
        allowed = {e for e, w in (packWeights or {}).items() if w > 0} or {'base'}
        eligible = [t for t in pool if t.edition in allowed]

        def effName(t):
            e = (t.effect_config or {}).get('effectName') or ''
            return e if e and e != 'none' else None

        byPos: Dict[int, list] = {}
        for t in eligible:
            byPos.setdefault(t.position, []).append(t)

        picked: list = []
        usedPlayers: set = set()
        usedEffects: set = set()
        for pos, count in _STARTER_SLOT_COUNTS:  # (position, how many cards)
            candidates = list(byPos.get(pos, []))
            if not candidates:
                logger.warning(f"Starter pack: no card for position {pos}")
                continue
            random.shuffle(candidates)
            for _ in range(count):
                chosen = next(
                    (t for t in candidates
                     if t.player_id not in usedPlayers
                     and (effName(t) is None or effName(t) not in usedEffects)),
                    None,
                )
                if chosen is None:  # every candidate collided — take any unused player
                    chosen = next((t for t in candidates if t.player_id not in usedPlayers),
                                  candidates[0])
                picked.append(chosen)
                usedPlayers.add(chosen.player_id)
                if effName(chosen):
                    usedEffects.add(effName(chosen))
        return picked

    def _weightedDrawDedup(self, pool: list, packWeights: dict, count: int,
                           dedupByPlayer: bool = False,
                           dedupByEffect: bool = False) -> list:
        """Like _weightedDraw but ensures each drawn template is unique
        along the specified axis. Two modes:

          - dedupByPlayer: one card per player_id. Used by champion / all-pro
            prestige packs.
          - dedupByEffect: one card per effect_config.effectName. Used by
            the starter pack so users can equip every card in the pack
            without bumping into the no-duplicate-effects rule.

        Both modes can be enabled simultaneously. Draws one template at a
        time, filtering remaining pool after each pick. Falls through to
        whatever's available if the pool runs out.
        """
        if not pool or count <= 0:
            return []
        if not dedupByPlayer and not dedupByEffect:
            return self._weightedDraw(pool, packWeights, count=count)
        drawn = []
        seenPlayerIds: set = set()
        seenEffectNames: set = set()
        remaining = list(pool)

        def _effectName(t) -> str:
            cfg = getattr(t, 'effect_config', None) or {}
            return cfg.get('effectName') or ''

        for _ in range(count):
            if not remaining:
                break
            picked = self._weightedDraw(remaining, packWeights, count=1)
            if not picked:
                break
            card = picked[0]
            drawn.append(card)
            if dedupByPlayer:
                seenPlayerIds.add(card.player_id)
            if dedupByEffect:
                effName = _effectName(card)
                if effName:
                    seenEffectNames.add(effName)
            remaining = [
                t for t in remaining
                if (not dedupByPlayer or t.player_id not in seenPlayerIds)
                and (not dedupByEffect or _effectName(t) not in seenEffectNames)
            ]
        return drawn

    # ─── Reveal / Select flow (purchases) ─────────────────────────────────────

    def revealPack(self, session, userId: int, packTypeId: int, currentSeason: int,
                   shopDay: Optional[int] = None,
                   currentWeek: int = 0,
                   skipCurrency: bool = False) -> dict:
        """Reveal flow: draw cards into a PendingPackOpening without yet
        committing them. Returns a pendingId the user submits to
        selectPackKeeps once they've chosen which to keep.

        skipCurrency=False (default): user-purchase path. Spends Floobits,
            checks daily limit + rotation gate.
        skipCurrency=True: free-grant path (achievement rewards, etc.).
            Skips spend, daily limit, and rotation check — but the same
            reveal+select UX still applies so users always pick which
            cards to keep.
        """
        from database.models import PendingPackOpening, PackOpening
        from database.repositories.card_repositories import (
            PackTypeRepository, CurrencyRepository,
        )

        packRepo = PackTypeRepository(session)
        currencyRepo = CurrencyRepository(session)

        packType = packRepo.getById(packTypeId)
        if not packType:
            raise ValueError("Invalid pack type")
        if packType.name == 'starter':
            raise ValueError("Starter pack uses claimStarterPack, not revealPack")

        if not skipCurrency:
            # Block packs the user can't actually see right now. After the
            # rotation rework, only humble is "always available"; grand,
            # exquisite, and themed packs must be present in this user's
            # rotation. Crafted calls otherwise let a user buy any pack.
            if shopDay is not None and not isAlwaysAvailablePack(packType):
                activeNames = set(getActivePackNames(shopDay))
                if packType.name in activeNames:
                    pass  # always-available standard tier (humble)
                else:
                    from database.models import FeaturedPackRotation
                    inRotation = session.query(FeaturedPackRotation).filter(
                        FeaturedPackRotation.user_id == userId,
                        FeaturedPackRotation.season == currentSeason,
                        FeaturedPackRotation.shop_day == shopDay,
                        FeaturedPackRotation.pack_type_id == packType.id,
                        FeaturedPackRotation.purchased == False,
                    ).first()
                    if not inRotation:
                        raise ValueError(f"{packType.display_name} is not in this week's rotation")

            # Daily limit — empty by default since the unified-rotation
            # rework made per-pack caps a footgun (reroll into a 'sold-out'
            # pack). If we ever bring caps back, this block already handles
            # null skip via DAILY_PACK_LIMITS.get().
            dailyLimit = DAILY_PACK_LIMITS.get(packType.name)
            if dailyLimit is not None:
                now = datetime.utcnow()
                dayStart = now.replace(hour=0, minute=0, second=0, microsecond=0)
                committedCount = session.query(PackOpening).filter(
                    PackOpening.user_id == userId,
                    PackOpening.pack_type_id == packType.id,
                    PackOpening.opened_at >= dayStart,
                    PackOpening.cost > 0,
                ).count()
                pendingCount = session.query(PendingPackOpening).filter(
                    PendingPackOpening.user_id == userId,
                    PendingPackOpening.pack_type_id == packType.id,
                    PendingPackOpening.opened_at >= dayStart,
                    PendingPackOpening.cost_paid > 0,
                ).count()
                if committedCount + pendingCount >= dailyLimit:
                    raise ValueError(f"Daily limit reached for {packType.display_name} ({dailyLimit}/day)")

            # Shop-cycle cap — stops whales from churning packs into Combine fuel.
            # Free / achievement-granted packs (skipCurrency=True) skip this whole
            # block, so they don't trip the cap and don't count toward it.
            packsThisCycle = _countPacksThisCycle(
                session, userId, currentSeason, currentWeek or 1
            )
            if _countsTowardCycleCap(packType) and packsThisCycle >= MAX_PACKS_PER_SHOP_CYCLE:
                raise ValueError(
                    f"Shop cycle pack limit reached "
                    f"({MAX_PACKS_PER_SHOP_CYCLE} packs per 7-week cycle). "
                    f"Refreshes next cycle."
                )

            # Spend Floobits up-front. Selection step doesn't refund.
            result = currencyRepo.spendFunds(
                userId, packType.cost,
                transactionType='pack_purchase',
                description=f"Opened {packType.display_name}",
                season=currentSeason,
            )
            if result is None:
                raise ValueError("Insufficient Floobits")

        drawnTemplates = self._drawPackCards(session, packType, currentSeason, currentWeek)

        pending = PendingPackOpening(
            user_id=userId,
            pack_type_id=packType.id,
            revealed_template_ids=[t.id for t in drawnTemplates],
            cost_paid=0 if skipCurrency else packType.cost,
            season=currentSeason,
        )
        session.add(pending)
        session.flush()

        # Mark the rotation slot purchased so it disappears from the shop
        # for the rest of this cycle. Mirrors FeaturedShopCard.purchased.
        # Only rotation-driven packs (themed + grand + exquisite) are
        # affected; humble is always-available and free grants don't
        # consume rotation slots.
        cameFromRotation = (
            not skipCurrency
            and shopDay is not None
            and not isAlwaysAvailablePack(packType)
            and packType.name not in set(getActivePackNames(shopDay))
        )
        if cameFromRotation:
            from database.models import FeaturedPackRotation
            session.query(FeaturedPackRotation).filter(
                FeaturedPackRotation.user_id == userId,
                FeaturedPackRotation.season == currentSeason,
                FeaturedPackRotation.shop_day == shopDay,
                FeaturedPackRotation.pack_type_id == packType.id,
                FeaturedPackRotation.purchased == False,
            ).update({FeaturedPackRotation.purchased: True})
            session.flush()

        revealed = [self._serializeTemplate(t, currentSeason, currentWeek, session=session)
                    for t in drawnTemplates]

        # Annotate each revealed card with how many of that EFFECT the user
        # already owns — current-season, non-vaulted only. Expired (past-season)
        # and vaulted cards can't be fed or upgraded, so they aren't usable
        # duplicates and shouldn't inflate the "You own N" count. A same-effect
        # active duplicate is exactly what Level Up consumes.
        from collections import Counter
        from database.repositories.card_repositories import UserCardRepository
        ownedCounts: Counter = Counter()
        for c in UserCardRepository(session).getByUser(userId):
            if getattr(c, "vaulted", False):
                continue
            if getattr(getattr(c, "card_template", None), "season_created", None) != currentSeason:
                continue  # expired — can't be fed/upgraded
            en = self._effectName(c)
            if en:
                ownedCounts[en] += 1
        for r in revealed:
            r["ownedEffectCount"] = ownedCounts.get(r.get("effectName") or "", 0)

        return {
            "pendingId": pending.id,
            "packName": packType.display_name,
            "cost": 0 if skipCurrency else packType.cost,
            "cardsPerPack": packType.cards_per_pack,
            "cardsKept": packType.cards_kept,
            "revealed": revealed,
        }

    def selectPackKeeps(self, session, userId: int, pendingId: int,
                        keptIndices: list, currentSeason: int, currentWeek: int = 0) -> dict:
        """Commit the user's selection from a pending pack reveal.

        keptIndices: list of integer indices into the pendingPack.revealed_template_ids
        list. Length must match the pack's cards_kept value (or all of them
        for packs with no selection). Discarded cards are dropped — no refund
        for now.
        """
        from database.models import PendingPackOpening, UserCard, PackOpening, CardTemplate
        from database.repositories.card_repositories import (
            UserCardRepository, PackOpeningRepository,
        )

        pending = session.query(PendingPackOpening).filter_by(
            id=pendingId, user_id=userId,
        ).first()
        if not pending:
            raise ValueError("No pending pack with that id for this user")

        packType = pending.pack_type
        revealedIds = list(pending.revealed_template_ids or [])
        if not revealedIds:
            raise ValueError("Pending pack has no revealed cards")

        keepCount = packType.cards_kept or packType.cards_per_pack

        # Sanitize indices: dedupe, range-check, count-check
        indices = sorted({int(i) for i in keptIndices if 0 <= int(i) < len(revealedIds)})
        if len(indices) != keepCount:
            raise ValueError(f"Must select exactly {keepCount} of {len(revealedIds)} revealed cards")

        keptTemplateIds = [revealedIds[i] for i in indices]

        # Materialize UserCard rows for kept selections
        cardRepo = UserCardRepository(session)
        openingRepo = PackOpeningRepository(session)

        newCards: List[UserCard] = []
        acquiredVia = f"pack_{packType.name}"
        # Showpieces go straight to the Vault, so the kept templates have to be
        # loaded here — this path only carries ids.
        _keptTemplates = {
            t.id: t for t in session.query(CardTemplate)
            .filter(CardTemplate.id.in_(list(keptTemplateIds))).all()
        } if keptTemplateIds else {}
        for tid in keptTemplateIds:
            _vault = _vaultOnAcquire(_keptTemplates.get(tid), currentSeason, currentWeek)
            newCards.append(UserCard(
                user_id=userId,
                card_template_id=tid,
                acquired_via=acquiredVia,
                vaulted=_vault,
                vaulted_at=datetime.utcnow() if _vault else None,
            ))
        cardRepo.saveBatch(newCards)

        # Record the opening with the KEPT cards (not the revealed pool) for
        # historical accuracy of "what the user actually got".
        opening = PackOpening(
            user_id=userId,
            pack_type_id=packType.id,
            cards_received=keptTemplateIds,
            cost=pending.cost_paid,
        )
        openingRepo.save(opening)

        session.delete(pending)
        session.flush()

        serialized = []
        for card in newCards:
            session.refresh(card)
            serialized.append(self.serializeCard(card, currentSeason))

        return {
            "packName": packType.display_name,
            "kept": serialized,
            "discardedCount": len(revealedIds) - len(keptTemplateIds),
        }

    def claimStarterPack(self, session, userId: int, currentSeason: int) -> dict:
        """Free starter pack: 5 base cards, once per season per user.

        No selection — user keeps everything. Sets User.starter_pack_claimed_season
        so the offer disappears until the next season.
        """
        from database.models import User
        from database.repositories.card_repositories import PackTypeRepository

        user = session.query(User).filter_by(id=userId).first()
        if not user:
            raise ValueError("User not found")
        if user.starter_pack_claimed_season == currentSeason:
            raise ValueError("Starter pack already claimed this season")

        packRepo = PackTypeRepository(session)
        packType = packRepo.getByName('starter')
        if not packType:
            raise ValueError("Starter pack type not seeded — run migrations")

        # Use the immediate-grant flow with skipCurrency=True (no daily limit, no spend).
        result = self.openPack(session, userId, packType.id, currentSeason, skipCurrency=True)
        user.starter_pack_claimed_season = currentSeason
        session.flush()
        return result

    def cleanupStalePendingPacks(self, session, ageHours: int = 24,
                                 currentWeek: int = 0) -> int:
        """Auto-resolve pending pack reveals older than ageHours by random
        keep-selection. Run on app startup so users never lose paid packs to
        crashes / abandoned sessions.

        Returns the number of pending packs resolved.
        """
        from database.models import PendingPackOpening
        from datetime import datetime, timedelta
        import random as _random

        cutoff = datetime.utcnow() - timedelta(hours=ageHours)
        stale = session.query(PendingPackOpening).filter(
            PendingPackOpening.opened_at < cutoff,
        ).all()

        for pending in stale:
            try:
                packType = pending.pack_type
                revealedIds = list(pending.revealed_template_ids or [])
                if not revealedIds:
                    session.delete(pending)
                    continue
                keepCount = packType.cards_kept or packType.cards_per_pack
                keepCount = min(keepCount, len(revealedIds))
                indices = _random.sample(range(len(revealedIds)), keepCount)
                # currentWeek defaults to 0 here (startup sweep has no live week).
                # Past-season cards still vault on the season comparison; only the
                # "current season, but the season is over" case is missed, which
                # is acceptable for abandoned reveals.
                self.selectPackKeeps(
                    session, pending.user_id, pending.id, indices, pending.season,
                    currentWeek=currentWeek,
                )
            except Exception:
                # Don't let one bad row block the sweep; just orphan it.
                session.rollback()
                continue

        session.commit()
        return len(stale)

    def _serializeTemplate(self, template, currentSeason: int, currentWeek: int = 0,
                           session=None) -> dict:
        """Template-only serialization for reveal payloads. Mirrors the
        rich shape of serializeCard so the reveal UI can render cards
        identically to a UserCard view, but without an `id` (no UserCard
        exists yet — those are written on selection).
        """
        # Build a transient stub UserCard so we can reuse serializeCard's
        # effect-rebuilding / sellValue / combineValue logic intact.
        from database.models import UserCard
        from sqlalchemy.orm.attributes import set_committed_value
        stub = UserCard(
            user_id=0,
            card_template_id=template.id,
            acquired_via='pack_reveal',
            acquired_at=datetime.utcnow(),
            # Mark the stub with the vault state this card WILL have once kept.
            # Without it a collection card previews as an ordinary expired card:
            # the UI hides effects and the "Expired" badge on vaulted cards, and
            # a past-season template is neither active nor (without this) vaulted,
            # so it advertised an effect it can never use and called itself
            # expired when it is simply a collectible.
            vaulted=_vaultOnAcquire(template, currentSeason, currentWeek),
        )
        # Wire the relationship without triggering back-population —
        # a plain `stub.card_template = template` would append `stub`
        # into the (session-attached) template.user_cards collection and
        # SAWarning at commit ("Object of type <UserCard> not in session,
        # add operation along 'CardTemplate.user_cards' will not proceed").
        # set_committed_value sets the attribute as "already-loaded" so
        # the relationship event machinery doesn't fire.
        set_committed_value(stub, 'card_template', template)
        result = self.serializeCard(stub, currentSeason)
        # Attach the player's season stat line, same as the collection view and
        # the fantasy shop do. Without it every card rendered through this path —
        # pack reveals and the collection singles shelf — showed "No stats
        # recorded" on its back, which is especially wrong for a collection card
        # whose whole point is the season it came from.
        if session is not None and template.player_id:
            stats = self.buildPlayerSeasonStats(
                session, template.player_id, template.season_created, template.position,
            )
            if stats:
                result["playerStats"] = stats
        # Showcase value, on any card headed for the Vault. For a collection
        # card this is the only number that says what it's worth: it can't be
        # equipped, so the projection and the effect a fantasy card is judged on
        # don't apply to it. Same shape /api/cards attaches under `showcase`, so
        # the shop, the reveal and the Showcase picker all render it the same.
        #
        # No legacy lookup needed here: that premium is rookie-cards-only and
        # the collection pool is MVP / champion / all-pro prints, so it is
        # always zero on this path.
        if result.get('vaulted'):
            from managers.showcaseManager import _cardBreakdown
            result["showcase"] = _cardBreakdown(result, currentSeason)
        # Strip the fake id — the card doesn't exist yet
        result.pop('id', None)
        return result

    def _editionsAtOrAbove(self, minEdition: str) -> set:
        """Return set of editions at or above the given rarity tier."""
        order = EDITION_ORDER
        try:
            idx = order.index(minEdition)
        except ValueError:
            return {minEdition}
        return set(order[idx:])

    def _weightedDraw(self, pool: list, packWeights: dict, count: int) -> list:
        """Draw `count` templates from pool using weighted random selection.

        Two-stage selection so the stated edition rates actually hold:
          1. Roll the edition using packWeights (the per-pack rarity weights).
          2. Pick a template within that edition, weighted by player rating
             (higher-rated players are rarer within each edition).

        A naive single-stage weight (editionWeight × ratingPenalty per template)
        is wrong because there are far more base templates than diamond ones,
        so the summed base weight always dominates regardless of the stated
        per-edition weight. Splitting the roll fixes that.
        """
        if not pool:
            return []

        # Group templates by edition; skip editions absent from the pool.
        byEdition: Dict[str, list] = {}
        for t in pool:
            byEdition.setdefault(t.edition, []).append(t)

        editions = list(byEdition.keys())
        editionWeights = [
            packWeights.get(e, EDITION_BASE_WEIGHTS.get(e, 1))
            for e in editions
        ]

        # Defensive: if all weights are zero (misconfigured pack), fall back
        # to uniform-random across the pool so we never return empty.
        if sum(editionWeights) <= 0:
            return random.choices(pool, k=count)

        drawn: list = []
        for _ in range(count):
            edition = random.choices(editions, weights=editionWeights, k=1)[0]
            candidates = byEdition[edition]
            # Rating rarity x accolade rarity. /100 keeps undecorated cards at
            # their previous weight so nothing outside the prestige ladder moves.
            ratingWeights = [
                max(1, int((120 - t.player_rating)
                           * classificationDrawWeight(t.classification) / 100))
                for t in candidates
            ]
            drawn.extend(random.choices(candidates, weights=ratingWeights, k=1))
        return drawn

    # ─── Featured Shop Cards ──────────────────────────────────────────────────

    FEATURED_CARD_COUNT = 5
    # Markup over sell value for shop singles
    SHOP_MARKUP = {
        'metallic': 4.0,
        'holographic': 2.7,
        'prismatic': 4.0,
        'diamond': 4.0,
    }

    def _featuredBuyPrice(self, template) -> int:
        """Shop price for a featured card: sell value × edition markup, floored
        at 10 and rounded to the nearest 5. Single source of truth so the
        displayed price and the charged price can never drift."""
        markup = self.SHOP_MARKUP.get(template.edition, 2.7)
        return max(10, int(round(template.sell_value * markup / 5.0)) * 5)

    COLLECTION_CARD_COUNT = 4

    def getFeaturedCollectionCards(self, session, userId: int, currentSeason: int,
                                   currentWeek: int = 0) -> List[dict]:
        """The Collection tab's daily singles — individual past-season cards.

        Deliberately simpler than getFeaturedCards. That one dedupes by EFFECT and
        weights for lineup-building, neither of which means anything here: these
        cards can never be equipped, so there is no effect to collide and no
        lineup to build. What matters is edition spread and not repeating a
        player, so that is all this does.

        Shares the FeaturedShopCard table via `kind`, so purchase, the
        purchased flag and the daily refresh all reuse the existing plumbing.
        """
        from database.models import FeaturedShopCard
        from datetime import datetime, timedelta
        from constants import DAILY_RESET_HOUR_UTC

        rows = (
            session.query(FeaturedShopCard)
            .filter_by(user_id=userId, season=currentSeason, purchased=False,
                       kind='collection')
            .all()
        )

        # Daily refresh, anchored to the same reset hour the fantasy shop uses.
        now = datetime.utcnow()
        resetToday = now.replace(hour=DAILY_RESET_HOUR_UTC, minute=0, second=0, microsecond=0)
        lastReset = resetToday if now >= resetToday else resetToday - timedelta(days=1)
        stale = any((r.generated_at or datetime.min) < lastReset for r in rows)

        if not rows or stale:
            session.query(FeaturedShopCard).filter_by(
                user_id=userId, season=currentSeason, kind='collection',
                purchased=False,
            ).delete()
            pool = getCollectionTemplates(
                session, currentSeason,
                includeCurrentSeason=regularSeasonOver(currentWeek),
            )
            if not pool:
                session.flush()
                return []
            weights = {'holographic': 45, 'prismatic': 35, 'diamond': 20, 'metallic': 10}
            picked, seenPlayers = [], set()
            # Weighted sampling WITHOUT replacement (Efraimidis-Spirakis): key each
            # candidate as random() ** (1/weight) and take the largest. A naive
            # `weight * random()` sort is not this — it hands the heaviest edition
            # almost every slot, which produced four holographics out of four.
            poolCopy = sorted(
                pool,
                # Edition weight x accolade weight, so the classification ladder
                # applies to the singles shelf exactly as it does to packs. This
                # sampler is separate from _weightedDraw, so wiring the ladder
                # there alone left the shelf handing out triple-crowns freely.
                key=lambda t: random.random() ** (
                    1.0 / max(1, weights.get(t.edition, 5)
                              * classificationDrawWeight(t.classification) / 100)),
                reverse=True,
            )
            for t in poolCopy:
                if len(picked) >= self.COLLECTION_CARD_COUNT:
                    break
                if t.player_id in seenPlayers:
                    continue          # one card per player, so the shelf reads varied
                seenPlayers.add(t.player_id)
                picked.append(t)
            for t in picked:
                session.add(FeaturedShopCard(
                    user_id=userId, season=currentSeason, card_template_id=t.id,
                    kind='collection', purchased=False,
                    generated_at=now, generated_at_week=currentWeek,
                ))
            session.flush()
            rows = (
                session.query(FeaturedShopCard)
                .filter_by(user_id=userId, season=currentSeason, purchased=False,
                           kind='collection')
                .all()
            )

        out = []
        for r in rows:
            t = r.card_template
            if not t:
                continue
            d = self._serializeTemplate(t, currentSeason, currentWeek, session=session)
            d['templateId'] = t.id
            d['buyPrice'] = self._featuredBuyPrice(t)
            out.append(d)
        return out

    def getFeaturedCards(self, session, userId: int, currentSeason: int,
                         currentWeek: int = 0, isScheduledMode: bool = False,
                         forceRegenerate: bool = False) -> List[dict]:
        """Return the user's persisted featured shop cards for this season.

        Supports daily refresh: in scheduled mode, refreshes if generated_at is
        before today.  In testing modes, refreshes every 7-week cycle.
        On first call per user per season, generates a random selection and
        persists it.  Subsequent calls return the same set (minus purchased).
        """
        from database.models import FeaturedShopCard, CardTemplate
        from database.repositories.card_repositories import CardTemplateRepository
        from datetime import datetime, date, timedelta
        from constants import SWAP_CYCLE_WEEKS, DAILY_RESET_HOUR_UTC

        # Check for existing selection
        existing = (
            session.query(FeaturedShopCard)
            .filter_by(user_id=userId, season=currentSeason, purchased=False, kind='fantasy')
            .all()
        )

        # ── Daily refresh check ──
        needsRefresh = False
        if existing and currentWeek > 0:
            sampleRow = existing[0]
            if sampleRow.generated_at is not None:
                if isScheduledMode:
                    # Refresh if generated before the most recent daily reset boundary
                    now = datetime.utcnow()
                    todayReset = now.replace(hour=DAILY_RESET_HOUR_UTC, minute=0, second=0, microsecond=0)
                    boundary = todayReset if now >= todayReset else todayReset - timedelta(days=1)
                    needsRefresh = sampleRow.generated_at < boundary
                else:
                    # Refresh if generated in a previous 7-week cycle
                    currentCycle = (currentWeek - 1) // SWAP_CYCLE_WEEKS + 1
                    genWeek = sampleRow.generated_at_week or 0
                    genCycle = (genWeek - 1) // SWAP_CYCLE_WEEKS + 1 if genWeek > 0 else 0
                    needsRefresh = currentCycle > genCycle

        if needsRefresh:
            # Delete unpurchased and regenerate
            session.query(FeaturedShopCard).filter(
                FeaturedShopCard.user_id == userId,
                FeaturedShopCard.season == currentSeason,
                FeaturedShopCard.purchased == False,
            ).delete()
            session.flush()
            existing = []

        if not existing:
            # Check if user ever had featured cards this season (all purchased)
            anyThisSeason = (
                session.query(FeaturedShopCard)
                .filter_by(user_id=userId, season=currentSeason)
                .first()
            )
            # Only skip generation if there are purchased rows AND no refresh/reroll happened
            if anyThisSeason and not needsRefresh and not forceRegenerate:
                return []

            # Generate fresh selection for this user
            templateRepo = CardTemplateRepository(session)
            allTemplates = templateRepo.getBySeason(currentSeason)
            # Skip NULL-team templates so legacy prospect/rookie pollution
            # doesn't bleed into the shop's featured rotation, and drop the no-effect
            # floor print (edition 'base') — it's the starter lineup, not a shop single.
            allTemplates = [t for t in allTemplates if t.team_id is not None and t.edition != 'base']
            # Collection cards are deliberately NOT in the shop rotation — they
            # come from the Legacy Pack only (owner, 2026-08-02). The single-card
            # shop sells current-season fantasy singles.

            if not allTemplates:
                return []

            # Flattened shop weights — rarer editions less common but still appear
            SHOP_EDITION_WEIGHTS = {
                'metallic': 50, 'holographic': 25, 'prismatic': 12, 'diamond': 5,
            }
            weights = []
            for t in allTemplates:
                # Accolade rarity rides on top of edition rarity here as well, so
                # a decorated single is as hard to see in the shop as it is to
                # pull from a pack. Undecorated cards multiply by 1.0.
                weights.append(max(1, int(
                    SHOP_EDITION_WEIGHTS.get(t.edition, 50)
                    * classificationDrawWeight(t.classification) / 100)))

            count = min(self.FEATURED_CARD_COUNT, len(allTemplates))
            picked = []
            seenEffects = set()
            poolCopy = list(allTemplates)
            weightsCopy = list(weights)
            maxAttempts = count * 10
            attempts = 0
            while len(picked) < count and poolCopy and attempts < maxAttempts:
                attempts += 1
                choice = random.choices(poolCopy, weights=weightsCopy, k=1)[0]
                # KEY BUG: this read 'effect', but the config key is 'effectName' (the
                # FACILITY_CATALOG schema uses 'effect' — easy to cross over). It always
                # came back None, so seenEffects never filled and the shop's duplicate
                # guard below has never once run.
                effectName = (choice.effect_config or {}).get('effectName') if choice.effect_config else None
                idx = poolCopy.index(choice)
                if effectName and effectName in seenEffects:
                    # Duplicate effect — remove from pool and skip
                    poolCopy.pop(idx)
                    weightsCopy.pop(idx)
                    continue
                picked.append(choice)
                if effectName:
                    seenEffects.add(effectName)
                poolCopy.pop(idx)
                weightsCopy.pop(idx)

            # Persist the selection with generation timestamp
            now = datetime.now()
            for t in picked:
                featuredRow = FeaturedShopCard(
                    user_id=userId,
                    season=currentSeason,
                    card_template_id=t.id,
                    kind='fantasy',
                    purchased=False,
                    generated_at=now,
                    generated_at_week=currentWeek,
                )
                session.add(featuredRow)
            session.flush()

            existing = (
                session.query(FeaturedShopCard)
                .filter_by(user_id=userId, season=currentSeason, purchased=False, kind='fantasy')
                .all()
            )

        # Count how many of each EFFECT the user already owns — current-season,
        # non-vaulted only (expired and vaulted cards can't be fed/upgraded),
        # mirroring the pack-reveal flow so the shop flags duplicates the same way.
        from collections import Counter as _Counter
        from database.repositories.card_repositories import UserCardRepository as _UCRepo
        ownedCounts: _Counter = _Counter()
        for c in _UCRepo(session).getByUser(userId):
            if getattr(c, "vaulted", False):
                continue
            if getattr(getattr(c, "card_template", None), "season_created", None) != currentSeason:
                continue  # expired — can't be fed/upgraded
            en = self._effectName(c)
            if en:
                ownedCounts[en] += 1

        # Build response from persisted rows
        result = []
        for row in existing:
            t = row.card_template
            buyPrice = self._featuredBuyPrice(t)
            effName = (t.effect_config or {}).get("effectName") or ""
            card = {
                "templateId": t.id,
                "playerId": t.player_id,
                "playerName": t.player_name,
                "teamId": t.team_id,
                "playerRating": t.player_rating,
                "position": t.position,
                "edition": t.edition,
                "seasonCreated": t.season_created,
                "isRookie": t.is_rookie,
                "classification": t.classification,
                "effectConfig": t.effect_config,
                "sellValue": t.sell_value,
                "buyPrice": buyPrice,
                "ownedEffectCount": ownedCounts.get(effName, 0),
                "isActive": True,
            }
            # Attach the player's season stat line so the shop card back matches the
            # collection view (which builds playerStats the same way).
            if t.player_id:
                stats = self.buildPlayerSeasonStats(
                    session, t.player_id, t.season_created, t.position,
                )
                if stats:
                    card["playerStats"] = stats
            result.append(card)

        return result

    # ─── Themed Pack Rotation ────────────────────────────────────────────────

    THEMED_PACK_SLOT_COUNT = 3

    def getActiveThemedPacks(self, session, userId: int, currentSeason: int,
                              currentWeek: int = 0) -> list:
        """Return the themed packs visible to a user for the current
        (season, shop_day). Per-user rotation — generated lazily on first
        read of a cycle; regenerated when shop_day advances or the user rerolls.
        """
        from database.models import FeaturedPackRotation
        from sqlalchemy import and_

        shopDay = shopDayOfSeason(currentWeek)

        # Any rows for this user/cycle, including purchased ones — used to
        # detect whether the cycle has been generated yet. Featuring filters
        # purchased=False below so spent packs disappear from the shop.
        anyRows = (
            session.query(FeaturedPackRotation)
            .filter(and_(
                FeaturedPackRotation.user_id == userId,
                FeaturedPackRotation.season == currentSeason,
                FeaturedPackRotation.shop_day == shopDay,
            ))
            .order_by(FeaturedPackRotation.slot.asc())
            .all()
        )

        if not anyRows:
            anyRows = self._generateThemedPackRotation(session, userId, currentSeason, shopDay, currentWeek)

        return [
            row.pack_type for row in anyRows
            if row.pack_type is not None and not row.purchased
        ]

    def rerollThemedPacks(self, session, userId: int, currentSeason: int,
                           currentWeek: int = 0) -> list:
        """Force-regenerate this user's themed pack rotation for the current
        cycle. Caller is responsible for charging the floobit cost. Returns
        the new pack list.

        Purchased rows are deliberately preserved — they're how
        _generateThemedPackRotation tracks once-per-cycle lockouts on grand
        and exquisite (and once-per-season lockouts on champion/all-pro).
        Wiping them would silently re-eligible those tiers, which produced
        the 'bought grand then saw it again 2 rerolls later' bug.
        """
        from database.models import FeaturedPackRotation
        shopDay = shopDayOfSeason(currentWeek)
        session.query(FeaturedPackRotation).filter(
            FeaturedPackRotation.user_id == userId,
            FeaturedPackRotation.season == currentSeason,
            FeaturedPackRotation.shop_day == shopDay,
            FeaturedPackRotation.purchased == False,
        ).delete()
        session.flush()
        rows = self._generateThemedPackRotation(
            session, userId, currentSeason, shopDay, currentWeek, isReroll=True,
        )
        return [row.pack_type for row in rows if row.pack_type is not None]

    # Per-category base weight for the rotation's two-stage weighted pick.
    # Each slot first rolls a category, then picks a specific pack uniformly
    # within it. Humble has a high weight so it almost always shows up;
    # grand and exquisite start rare but climb each cycle via pity.
    # Base per-slot odds (total weight 136):
    #   humble ~37% · position 18% · team 18% · output 18% · grand 6% · exquisite 2%
    # Base per-cycle (any of 3 slots) odds:
    #   humble ~75% · grand ~17% · exquisite ~6%
    ROTATION_CATEGORY_WEIGHTS = {
        'humble':    50,
        'position':  25,
        'output':    25,
        # Rookie-class pack — always-available themed gamble on the new draft
        # class. Weighted a touch below position/output (narrower pool).
        'rookie':    20,
        # Grand and Exquisite cut down from 8/3 — testing showed they
        # appeared "pretty consistently" even early in the season,
        # which conflicts with the prestige framing. Combined with the
        # achievement rewards (Banner Week IV / Dedicated VI / etc.
        # grant Grand or Exquisite packs), the total exposure was way
        # too high. New base odds: ~10% per cycle Grand, ~2.5% Exquisite.
        'grand':      4,
        'exquisite':  1,
        # Prestige themed packs — once-per-season per user. Bumped to 8
        # each so they appear in roughly 1 of every 4-5 cycles — testing
        # showed users were running 5+ rerolls without ever seeing the
        # All-Pro pack. Still rare enough to feel like a treat, but
        # actually visible.
        'champion':   8,
        'allpro':     8,
    }
    # Weight bump for grand/exquisite per shop cycle elapsed in the season.
    # Pure monotonic ramp — purchases don't reset it. By cycle 4 (last shop
    # cycle of a 28-week season), pity is maxed:
    #   Grand:     4 → 4+(2×3)  = 10 weight, ~8% per slot,  ~21% per cycle
    #   Exquisite: 1 → 1+(1×3)  =  4 weight, ~3% per slot,  ~9% per cycle
    # Ramp step halved alongside the base cut so the pity slope feels
    # similar in shape but lands at lower absolute odds.
    PITY_STEP_PER_CYCLE = {
        'grand':     2,
        'exquisite': 1,
    }

    def _generateThemedPackRotation(self, session, userId: int, currentSeason: int,
                                     shopDay: int, currentWeek: int,
                                     isReroll: bool = False) -> list:
        """Pick THEMED_PACK_SLOT_COUNT packs for this user's rotation via the
        two-stage weighted scheme:
          1. Roll a category (humble/position/team/output/grand/exquisite) by weight.
          2. Pick a specific pack uniformly within the category.

        - Grand and Exquisite already purchased in this cycle are excluded
          from the pool so they can't reroll back in.
        - Pity ramp: grand/exquisite weight grows by PITY_STEP_PER_CYCLE
          for each shop_day elapsed (cycle 1 → 0, cycle 4 → +3). Pure
          monotonic — purchases do not reset it, so the rare tiers feel
          increasingly likely as the season closes.
        - Initial generation (isReroll=False) guarantees Humble in slot 0
          if viable, so every new cycle opens with the cheap entry tier.
          Rerolls don't guarantee humble.

        Skipped if a category's underlying template pool is empty for the
        current season — keeps unwinnable packs from being featured."""
        from database.models import FeaturedPackRotation, PackType, CardTemplate

        allPacks = session.query(PackType).all()
        if not allPacks:
            return []

        # Two-flavor lockout for already-purchased rare packs:
        #   Cycle-only (grand, exquisite): excluded within (season, shop_day)
        #     but eligible again next cycle.
        #   Season-only (themed_champion, themed_allpro): excluded for the
        #     entire season once purchased — one shot per user per season.
        cycleLockoutNames = {'grand', 'exquisite'}
        seasonLockoutNames = {'themed_champion', 'themed_allpro'}

        cycleLockedRows = (
            session.query(FeaturedPackRotation.pack_type_id)
            .join(PackType, PackType.id == FeaturedPackRotation.pack_type_id)
            .filter(
                FeaturedPackRotation.user_id == userId,
                FeaturedPackRotation.season == currentSeason,
                FeaturedPackRotation.shop_day == shopDay,
                FeaturedPackRotation.purchased == True,
                PackType.name.in_(cycleLockoutNames),
            )
            .all()
        )
        seasonLockedRows = (
            session.query(FeaturedPackRotation.pack_type_id)
            .join(PackType, PackType.id == FeaturedPackRotation.pack_type_id)
            .filter(
                FeaturedPackRotation.user_id == userId,
                FeaturedPackRotation.season == currentSeason,
                FeaturedPackRotation.purchased == True,
                PackType.name.in_(seasonLockoutNames),
            )
            .all()
        )
        purchasedIds = {row[0] for row in (cycleLockedRows + seasonLockedRows)}

        # Build season-aware viability check so we don't feature a pack
        # whose pool has no eligible templates this season.
        seasonTemplates = (
            session.query(CardTemplate)
            .filter(
                CardTemplate.season_created == currentSeason,
                CardTemplate.team_id.isnot(None),
            )
            .all()
        )

        def _categoryFor(pt) -> Optional[str]:
            # 'team' category dropped — Champion Team Pack (themed_champion)
            # is the only team-flavored pack and lives in the 'champion'
            # category. Legacy themed_team_* rows are pruned at seed time
            # so they don't show up here even if some still exist.
            if pt.theme_type in ('position', 'output', 'rookie', 'champion', 'allpro'):
                return pt.theme_type
            if pt.name in ('humble', 'grand', 'exquisite'):
                return pt.name
            return None

        def _viable(pt) -> bool:
            if pt.theme_type:
                pool = _applyThemeFilter(
                    seasonTemplates, pt.theme_type, pt.theme_value,
                    session=session, currentSeason=currentSeason,
                )
                return len(pool) >= pt.cards_per_pack
            # Grand/Exquisite draw from the full season pool — viable as
            # long as enough templates exist.
            return len(seasonTemplates) >= pt.cards_per_pack

        # Group viable packs by category. Grand/Exquisite already purchased
        # in this cycle are excluded so they can't be rerolled into again.
        byCategory: Dict[str, list] = {}
        for pt in allPacks:
            cat = _categoryFor(pt)
            if cat is None:
                continue
            if pt.id in purchasedIds:
                continue  # grand/exquisite already bought this cycle
            if not _viable(pt):
                continue
            byCategory.setdefault(cat, []).append(pt)

        if not byCategory:
            return []

        # Pity ramp: grand/exquisite weights grow by (shopDay - 1) × step.
        # Monotonic across the season — no reset on purchase. Cycle 1 uses
        # base weights; cycle 4 uses base + 3×step.
        pityFactor = max(0, shopDay - 1)
        effectiveWeights = dict(self.ROTATION_CATEGORY_WEIGHTS)
        for cat, step in self.PITY_STEP_PER_CYCLE.items():
            effectiveWeights[cat] = effectiveWeights.get(cat, 0) + step * pityFactor

        chosen: list = []
        chosenIds: set = set()
        availableCats = {c: list(packs) for c, packs in byCategory.items() if packs}

        # Initial generation: guarantee Humble in slot 0 (if viable) so every
        # new cycle opens with the cheap entry tier. Rerolls don't get this
        # guarantee — rerolling is a gamble that may lose the humble slot.
        if not isReroll and 'humble' in availableCats:
            humblePool = availableCats['humble']
            if humblePool:
                pt = humblePool[0]  # singleton category, one pack
                chosen.append(pt)
                chosenIds.add(pt.id)
                del availableCats['humble']

        # Sample remaining slots via weighted category rolls
        maxAttempts = self.THEMED_PACK_SLOT_COUNT * 20
        attempts = 0
        while len(chosen) < self.THEMED_PACK_SLOT_COUNT and availableCats and attempts < maxAttempts:
            attempts += 1
            categories = list(availableCats.keys())
            weights = [effectiveWeights.get(c, 1) for c in categories]
            if sum(weights) <= 0:
                break
            cat = random.choices(categories, weights=weights, k=1)[0]
            pickPool = availableCats[cat]
            pt = random.choice(pickPool)
            if pt.id in chosenIds:
                # Duplicate — remove and try again. Same-category multi-picks
                # within a single rotation are fine (e.g. two position packs),
                # but the same exact pack twice is not.
                pickPool.remove(pt)
                if not pickPool:
                    del availableCats[cat]
                continue
            chosen.append(pt)
            chosenIds.add(pt.id)
            pickPool.remove(pt)
            if not pickPool:
                del availableCats[cat]

        if not chosen:
            return []

        now = datetime.utcnow()
        rows = []
        for slot, pt in enumerate(chosen):
            row = FeaturedPackRotation(
                user_id=userId,
                season=currentSeason,
                shop_day=shopDay,
                slot=slot,
                pack_type_id=pt.id,
                generated_at=now,
                generated_at_week=currentWeek,
            )
            session.add(row)
            rows.append(row)
        session.flush()
        return rows

    def buyFeaturedCard(self, session, userId: int, templateId: int, currentSeason: int,
                        showpieceOnly: bool = False) -> dict:
        """Buy a single card from the featured shop.

        Returns the serialized new card.
        Raises ValueError on invalid template, wrong season, or insufficient funds.

        `showpieceOnly` is set by the API outside the regular season: a fantasy
        card bought then could never be equipped, so only showpieces are sold.
        Enforced HERE rather than at the endpoint so every caller inherits it.
        """
        from database.models import CardTemplate, UserCard, FeaturedShopCard
        from database.repositories.card_repositories import (
            CardTemplateRepository, CurrencyRepository, UserCardRepository,
        )

        templateRepo = CardTemplateRepository(session)
        currencyRepo = CurrencyRepository(session)
        cardRepo = UserCardRepository(session)

        # Verify the card is actually in this user's featured shop
        featuredRow = (
            session.query(FeaturedShopCard)
            .filter_by(user_id=userId, season=currentSeason,
                       card_template_id=templateId, purchased=False)
            .first()
        )
        if not featuredRow:
            raise ValueError("Card is not available in your shop")

        template = templateRepo.getById(templateId)
        if not template:
            raise ValueError("Card template not found")
        # Outside the regular season only COLLECTION cards sell: purpose-built
        # showpieces, or legacy prints (past-season templates, which can never be
        # equipped anyway). Selling a current-season fantasy card here would be
        # selling a brick — fantasy is over.
        if showpieceOnly:
            _isCollection = (bool(getattr(template, 'is_showpiece', False))
                             or (template.season_created or 0) < currentSeason)
            if not _isCollection:
                raise ValueError(
                    "Only collection cards are available outside the regular season")

        buyPrice = self._featuredBuyPrice(template)

        result = currencyRepo.spendFunds(
            userId, buyPrice,
            transactionType='card_purchase',
            description=f"Bought {template.edition} {template.player_name}",
            season=currentSeason,
        )
        if result is None:
            raise ValueError("Insufficient Floobits")

        # Mark as purchased
        featuredRow.purchased = True

        _vault = _vaultOnAcquire(template, currentSeason)
        card = UserCard(
            user_id=userId,
            card_template_id=template.id,
            acquired_via='shop',
            vaulted=_vault,
            vaulted_at=datetime.utcnow() if _vault else None,
        )
        cardRepo.save(card)
        session.refresh(card)

        return self.serializeCard(card, currentSeason)
