"""Card Manager - handles card template generation and card operations."""

import random
from typing import List, Dict, Any, Optional
from logger_config import get_logger
from managers.cardEffects import buildEffectConfig as _buildEffectConfig

logger = get_logger("floosball.cardManager")

# ─── Edition Configuration ────────────────────────────────────────────────────

# Rating thresholds for edition eligibility
EDITION_THRESHOLDS = {
    'base': 0,          # All players
    'holographic': 75,  # Rating >= 75
    'prismatic': 80,    # Rating >= 80
    'diamond': 90,      # Rating >= 90
}

# Base rarity weights (before player-rating adjustment)
EDITION_BASE_WEIGHTS = {
    'base': 100,
    'holographic': 25,
    'prismatic': 10,
    'diamond': 2,
}

# Sell values by edition (active season)
EDITION_SELL_VALUES = {
    'base': 5,
    'holographic': 30,
    'prismatic': 75,
    'diamond': 100,
}

EXPIRED_SELL_MULTIPLIER = 0.2  # Expired cards sell for 20%

# ─── The Combine (Card Upgrade System) ───────────────────────────────────────

EDITION_ORDER = ['base', 'holographic', 'prismatic', 'diamond']

# The Combine: total card value thresholds for resulting edition
BLENDER_THRESHOLDS = [
    (300, 'diamond'),       # 300+ total value → diamond (e.g. 4 prismatics, or 10 holos)
    (175, 'prismatic'),     # 175-499 → prismatic (e.g. 6 holos, or 1 holo + many bases)
    (50, 'holographic'),    # 50-174 → holographic (e.g. 10 base cards)
    (0, 'base'),            # 0-49 → base
]

# Daily pack purchase limits (resets on calendar day, same as featured shop refresh).
# Pack revamp (feature/pack-revamp): every rotated pack now caps at 1/day; the
# 2-packs-per-day intent is enforced by which packs the rotation surfaces in
# the shop on a given day. 'proper' is deprecated and not in the rotation.
DAILY_PACK_LIMITS = {
    'humble': 1,
    'grand': 1,
    'exquisite': 1,
}

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


def getActivePackNames(shopDay: int) -> list:
    """Pack tiers visible in the shop on the given shop day.

    Shop day 1 (weeks 1-7):    humble + grand           — two-pack starter
    Shop day 2 (weeks 8-14):   humble + grand           — same lineup
    Shop day 3 (weeks 15-21):  humble + grand + exquisite — top tier unlocks
    Shop day 4 (weeks 22-28):  humble + grand + exquisite — full lineup
    """
    if shopDay <= 2:
        return ['humble', 'grand']
    return ['humble', 'grand', 'exquisite']

# Classification value multipliers (stacking for compound classifications)
CLASSIFICATION_VALUE_MULTIPLIERS = {
    'rookie': 2.0,
    'mvp': 3.0,
    'champion': 2.0,
    'all_pro': 1.5,
}



def getCardValue(card, currentSeason: int) -> int:
    """Get classification-aware value for a card. Used by The Combine operations."""
    isActive = card.card_template.season_created == currentSeason
    baseValue = getSellValue(card.card_template.edition, isActive=isActive)
    classification = card.card_template.classification or ""
    multiplier = 1.0
    for tag, mult in CLASSIFICATION_VALUE_MULTIPLIERS.items():
        if tag in classification:
            multiplier *= mult
    return max(1, int(baseValue * multiplier))


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
    edition: str = "base",
) -> Optional[str]:
    """Build classification string for a player's card templates.

    Classifications are underscore-joined tags (e.g., "mvp_champion", "all_pro_champion").
    Rookie can appear on any edition. MVP, Champion, and All-Pro require holographic+.
    Rookie cannot stack with other classifications (rookies didn't play previous season).
    """
    if isRookie:
        return "rookie"

    # MVP, Champion, All-Pro only on holographic and above
    if edition == "base":
        return None

    tags = []
    if mvpPlayerId is not None and playerId == mvpPlayerId:
        tags.append("mvp")
    if playerId in allProPlayerIds:
        tags.append("all_pro")
    if playerId in championPlayerIds:
        tags.append("champion")

    return "_".join(tags) if tags else None


class CardManager:
    """Manages card template generation and card operations."""

    def __init__(self, serviceContainer):
        self.serviceContainer = serviceContainer

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

        for player in playerManager.activePlayers:
            # Cards are for rostered players only — exclude every off-roster
            # population:
            # - Free agents (player.team is None or a 'Free Agent' string)
            # - Prospects (is_prospect=True; player.team is the 'Prospect' string
            #   once routing runs, but flag-checking is more reliable than
            #   string comparison)
            # - Upcoming rookies (is_upcoming_rookie=True)
            # - Retired players (player.team == 'Retired' string)
            if getattr(player, 'is_prospect', False):
                continue
            if getattr(player, 'is_upcoming_rookie', False):
                continue
            teamObj = getattr(player, 'team', None)
            if teamObj is None or not hasattr(teamObj, 'id'):
                continue

            rating = getattr(player, 'playerRating', None)
            if rating is None:
                continue

            positionValue = player.position.value if hasattr(player.position, 'value') else int(player.position)
            isRookie = getattr(player, 'seasonsPlayed', 1) == 0

            teamId = teamObj.id

            for edition, threshold in EDITION_THRESHOLDS.items():
                if rating < threshold:
                    continue

                # Classification depends on edition (MVP/Champion/All-Pro require holo+)
                classification = _buildClassification(
                    playerId=player.id,
                    isRookie=isRookie,
                    mvpPlayerId=mvpPlayerId,
                    championPlayerIds=champIds,
                    allProPlayerIds=apIds,
                    edition=edition,
                )

                effectConfig = _buildEffectConfig(edition, rating, positionValue, teamId)
                rarityWeight = computeRarityWeight(edition, rating)
                sellValue = getSellValue(edition, isActive=True)

                template = CardTemplate(
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
                )
                templates.append(template)

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

        for player in playerManager.activePlayers:
            if player.id in existingPlayerIds:
                continue

            # Skip prospects, upcoming rookies, free agents — only rostered
            # players get card templates.
            if getattr(player, 'is_prospect', False):
                continue
            if getattr(player, 'is_upcoming_rookie', False):
                continue
            teamObj = getattr(player, 'team', None)
            if teamObj is None or not hasattr(teamObj, 'id'):
                continue

            # Only create rookie templates for actual rookies (just generated this offseason)
            if getattr(player, 'seasonsPlayed', 1) > 0:
                continue

            rating = getattr(player, 'playerRating', None)
            if rating is None:
                continue

            positionValue = player.position.value if hasattr(player.position, 'value') else int(player.position)
            teamId = teamObj.id

            for edition, threshold in EDITION_THRESHOLDS.items():
                if rating < threshold:
                    continue

                effectConfig = _buildEffectConfig(edition, rating, positionValue, teamId)
                rarityWeight = computeRarityWeight(edition, rating)
                sellValue = getSellValue(edition, isActive=True)

                template = CardTemplate(
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
                )
                templates.append(template)

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

        # Derive category from effect name if missing from effectConfig (legacy cards)
        from managers.cardEffects import EFFECT_CATEGORY
        effectName = effectConfig.get("effectName", "")
        category = effectConfig.get("category") or EFFECT_CATEGORY.get(effectName, "flat_fp")

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

        # Calculate total and sell (Rookie classification = 2x sell value)
        totalFloobits = 0
        for card in cards:
            isActive = card.card_template.season_created == currentSeason
            cardValue = getSellValue(card.card_template.edition, isActive=isActive)
            classification = card.card_template.classification or ""
            if "rookie" in classification:
                cardValue *= 2
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
                              currentSeason: int = 0, currentWeek: int = 0):
        """Validate cards for upgrade: owned by user and not equipped this week.
        Returns list of UserCard objects with templates loaded.
        """
        from database.repositories.card_repositories import UserCardRepository
        from database.models import EquippedCard

        cardRepo = UserCardRepository(session)
        cards = cardRepo.getByIds(cardIds, userId)
        if len(cards) != len(cardIds):
            foundIds = {c.id for c in cards}
            missingIds = [cid for cid in cardIds if cid not in foundIds]
            raise ValueError(f"Cards not found or not owned: {missingIds}")

        equippedRows = session.query(EquippedCard).filter(
            EquippedCard.user_card_id.in_(cardIds),
            EquippedCard.user_id == userId,
            EquippedCard.season == currentSeason,
            EquippedCard.week == currentWeek,
        ).all()
        equippedIds = {ec.user_card_id for ec in equippedRows}
        if equippedIds:
            # Log details for debugging
            for ec in equippedRows:
                logger.warning(f"Card {ec.user_card_id} equipped in S{ec.season}W{ec.week} slot={ec.slot_number} locked={ec.locked}")
            logger.warning(f"Blend blocked: season={currentSeason} week={currentWeek} equippedIds={equippedIds}")
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
        resultEdition = 'base'
        for threshold, edition in BLENDER_THRESHOLDS:
            if totalValue >= threshold:
                resultEdition = edition
                break

        # Pick random player meeting rating gate for result edition
        templateRepo = CardTemplateRepository(session)
        allTemplates = templateRepo.getBySeason(currentSeason)
        minRating = EDITION_THRESHOLDS.get(resultEdition, 0)

        # Get unique eligible players
        eligiblePlayers = {}
        for t in allTemplates:
            if t.player_rating >= minRating and t.player_id not in eligiblePlayers:
                eligiblePlayers[t.player_id] = t

        if not eligiblePlayers:
            raise ValueError(f"No eligible players for {resultEdition} edition")

        sourceTemplate = random.choice(list(eligiblePlayers.values()))

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
            classification=sourceTemplate.classification,
            player_name=sourceTemplate.player_name,
            team_id=sourceTemplate.team_id,
            player_rating=sourceTemplate.player_rating,
            position=sourceTemplate.position,
            effect_config=effectConfig,
            rarity_weight=computeRarityWeight(resultEdition, sourceTemplate.player_rating),
            sell_value=getSellValue(resultEdition, isActive=isActive),
            is_upgraded=True,
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

        resultEdition = 'base'
        for threshold, edition in BLENDER_THRESHOLDS:
            if totalValue >= threshold:
                resultEdition = edition
                break

        return {
            "totalValue": totalValue,
            "resultEdition": resultEdition,
            "cardCount": len(cards),
        }

    # ─── Pack Opening ─────────────────────────────────────────────────────────

    def openPack(self, session, userId: int, packTypeId: int, currentSeason: int,
                 skipCurrency: bool = False, source: str = "purchase") -> dict:
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

        # Enforce daily purchase limit (skipped for free grants)
        if not skipCurrency:
            dailyLimit = DAILY_PACK_LIMITS.get(packType.name)
            if dailyLimit is not None:
                from datetime import datetime
                from database.models import PackOpening
                now = datetime.utcnow()
                dayStart = now.replace(hour=0, minute=0, second=0, microsecond=0)
                todayCount = session.query(PackOpening).filter(
                    PackOpening.user_id == userId,
                    PackOpening.pack_type_id == packType.id,
                    PackOpening.opened_at >= dayStart,
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

        drawnTemplates = self._drawPackCards(session, packType, currentSeason)

        # Create UserCard instances
        newCards: List[UserCard] = []
        acquiredVia = f"pack_{packType.name}"
        for template in drawnTemplates:
            card = UserCard(
                user_id=userId,
                card_template_id=template.id,
                acquired_via=acquiredVia,
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

    def _drawPackCards(self, session, packType, currentSeason: int) -> list:
        """Shared draw routine: returns N templates per packType.cards_per_pack.

        guaranteed_rarity branch was removed in the pack revamp — rate weights
        on each pack carry the rarity guarantees probabilistically instead.
        """
        from database.repositories.card_repositories import CardTemplateRepository
        templateRepo = CardTemplateRepository(session)
        allTemplates = templateRepo.getBySeason(currentSeason)
        if not allTemplates:
            raise ValueError("No card templates available for the current season")

        packWeights = packType.rarity_weights or EDITION_BASE_WEIGHTS
        return self._weightedDraw(allTemplates, packWeights, count=packType.cards_per_pack)

    # ─── Reveal / Select flow (purchases) ─────────────────────────────────────

    def revealPack(self, session, userId: int, packTypeId: int, currentSeason: int,
                   shopDay: Optional[int] = None,
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
        from datetime import datetime

        packRepo = PackTypeRepository(session)
        currencyRepo = CurrencyRepository(session)

        packType = packRepo.getById(packTypeId)
        if not packType:
            raise ValueError("Invalid pack type")
        if packType.name == 'starter':
            raise ValueError("Starter pack uses claimStarterPack, not revealPack")

        if not skipCurrency:
            # Block out-of-rotation packs (deprecated tiers like 'proper' or
            # tiered packs not yet unlocked today). Can't trust the frontend
            # to filter — a crafted call would otherwise let a user buy any
            # pack at any time.
            if shopDay is not None:
                activeNames = set(getActivePackNames(shopDay))
                if packType.name not in activeNames:
                    raise ValueError(f"{packType.display_name} is not available in the shop right now")

            # Daily limit — counts both committed openings AND pending reveals
            # so a user can't open + abandon + open again for the same pack today.
            dailyLimit = DAILY_PACK_LIMITS.get(packType.name)
            if dailyLimit is not None:
                now = datetime.utcnow()
                dayStart = now.replace(hour=0, minute=0, second=0, microsecond=0)
                committedCount = session.query(PackOpening).filter(
                    PackOpening.user_id == userId,
                    PackOpening.pack_type_id == packType.id,
                    PackOpening.opened_at >= dayStart,
                ).count()
                pendingCount = session.query(PendingPackOpening).filter(
                    PendingPackOpening.user_id == userId,
                    PendingPackOpening.pack_type_id == packType.id,
                    PendingPackOpening.opened_at >= dayStart,
                ).count()
                if committedCount + pendingCount >= dailyLimit:
                    raise ValueError(f"Daily limit reached for {packType.display_name} ({dailyLimit}/day)")

            # Spend Floobits up-front. Selection step doesn't refund.
            result = currencyRepo.spendFunds(
                userId, packType.cost,
                transactionType='pack_purchase',
                description=f"Opened {packType.display_name}",
                season=currentSeason,
            )
            if result is None:
                raise ValueError("Insufficient Floobits")

        drawnTemplates = self._drawPackCards(session, packType, currentSeason)

        pending = PendingPackOpening(
            user_id=userId,
            pack_type_id=packType.id,
            revealed_template_ids=[t.id for t in drawnTemplates],
            cost_paid=0 if skipCurrency else packType.cost,
            season=currentSeason,
        )
        session.add(pending)
        session.flush()

        revealed = [self._serializeTemplate(t, currentSeason) for t in drawnTemplates]
        return {
            "pendingId": pending.id,
            "packName": packType.display_name,
            "cost": 0 if skipCurrency else packType.cost,
            "cardsPerPack": packType.cards_per_pack,
            "cardsKept": packType.cards_kept,
            "revealed": revealed,
        }

    def selectPackKeeps(self, session, userId: int, pendingId: int,
                        keptIndices: list, currentSeason: int) -> dict:
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
        for tid in keptTemplateIds:
            newCards.append(UserCard(
                user_id=userId,
                card_template_id=tid,
                acquired_via=acquiredVia,
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

    def cleanupStalePendingPacks(self, session, ageHours: int = 24) -> int:
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
                self.selectPackKeeps(
                    session, pending.user_id, pending.id, indices, pending.season,
                )
            except Exception:
                # Don't let one bad row block the sweep; just orphan it.
                session.rollback()
                continue

        session.commit()
        return len(stale)

    def _serializeTemplate(self, template, currentSeason: int) -> dict:
        """Template-only serialization for reveal payloads. Mirrors the
        rich shape of serializeCard so the reveal UI can render cards
        identically to a UserCard view, but without an `id` (no UserCard
        exists yet — those are written on selection).
        """
        # Build a transient stub UserCard so we can reuse serializeCard's
        # effect-rebuilding / sellValue / combineValue logic intact.
        from database.models import UserCard
        from datetime import datetime
        stub = UserCard(
            user_id=0,
            card_template_id=template.id,
            acquired_via='pack_reveal',
            acquired_at=datetime.utcnow(),
        )
        # Wire the relationship in-memory so serializeCard can read template
        stub.card_template = template
        result = self.serializeCard(stub, currentSeason)
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
            ratingWeights = [max(1, 120 - t.player_rating) for t in candidates]
            drawn.extend(random.choices(candidates, weights=ratingWeights, k=1))
        return drawn

    # ─── Featured Shop Cards ──────────────────────────────────────────────────

    FEATURED_CARD_COUNT = 5
    # Markup over sell value for shop singles
    SHOP_MARKUP = {
        'base': 5.0,
        'holographic': 3.34,
        'prismatic': 5.0,
        'diamond': 5.0,
    }

    def getFeaturedCards(self, session, userId: int, currentSeason: int,
                         currentWeek: int = 0, isScheduledMode: bool = False,
                         forceRegenerate: bool = False) -> List[dict]:
        """Return the user's persisted featured shop cards for this season.

        Supports daily refresh: in scheduled mode, refreshes if generated_at is
        before today.  In testing modes, refreshes every 7-week cycle.
        On first call per user per season, generates a random selection and
        persists it.  Subsequent calls return the same set (minus purchased).
        """
        from database.models import FeaturedShopCard
        from database.repositories.card_repositories import CardTemplateRepository
        from datetime import datetime, date, timedelta
        from constants import SWAP_CYCLE_WEEKS, DAILY_RESET_HOUR_UTC

        # Check for existing selection
        existing = (
            session.query(FeaturedShopCard)
            .filter_by(user_id=userId, season=currentSeason, purchased=False)
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

            if not allTemplates:
                return []

            # Flattened shop weights — rarer editions less common but still appear
            SHOP_EDITION_WEIGHTS = {
                'base': 50, 'holographic': 25, 'prismatic': 12, 'diamond': 5,
            }
            weights = []
            for t in allTemplates:
                weights.append(SHOP_EDITION_WEIGHTS.get(t.edition, 50))

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
                effectName = (choice.effect_config or {}).get('effect') if choice.effect_config else None
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
                    purchased=False,
                    generated_at=now,
                    generated_at_week=currentWeek,
                )
                session.add(featuredRow)
            session.flush()

            existing = (
                session.query(FeaturedShopCard)
                .filter_by(user_id=userId, season=currentSeason, purchased=False)
                .all()
            )

        # Build response from persisted rows
        result = []
        for row in existing:
            t = row.card_template
            markup = self.SHOP_MARKUP.get(t.edition, 3.0)
            buyPrice = max(10, int(t.sell_value * markup))
            result.append({
                "templateId": t.id,
                "playerId": t.player_id,
                "playerName": t.player_name,
                "teamId": t.team_id,
                "playerRating": t.player_rating,
                "position": t.position,
                "edition": t.edition,
                "seasonCreated": t.season_created,
                "isRookie": t.is_rookie,
                "effectConfig": t.effect_config,
                "sellValue": t.sell_value,
                "buyPrice": buyPrice,
                "isActive": True,
            })

        return result

    def buyFeaturedCard(self, session, userId: int, templateId: int, currentSeason: int) -> dict:
        """Buy a single card from the featured shop.

        Returns the serialized new card.
        Raises ValueError on invalid template, wrong season, or insufficient funds.
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

        markup = self.SHOP_MARKUP.get(template.edition, 3.0)
        buyPrice = max(10, int(template.sell_value * markup))

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

        card = UserCard(
            user_id=userId,
            card_template_id=template.id,
            acquired_via='shop',
        )
        cardRepo.save(card)
        session.refresh(card)

        return self.serializeCard(card, currentSeason)
