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
    'chrome': 70,       # Rating >= 70
    'holographic': 75,  # Rating >= 75
    'gold': 78,         # Rating >= 78
    'prismatic': 85,    # Rating >= 85
    'diamond': 90,      # Rating >= 90
}

# Base rarity weights (before player-rating adjustment)
EDITION_BASE_WEIGHTS = {
    'base': 100,
    'chrome': 30,
    'holographic': 20,
    'gold': 15,
    'prismatic': 5,
    'diamond': 1,
}

# Sell values by edition (active season)
EDITION_SELL_VALUES = {
    'base': 5,
    'chrome': 20,
    'holographic': 30,
    'gold': 40,
    'prismatic': 100,
    'diamond': 250,
}

EXPIRED_SELL_MULTIPLIER = 0.2  # Expired cards sell for 20%


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
) -> Optional[str]:
    """Build classification string for a player's card templates.

    Classifications are underscore-joined tags (e.g., "mvp_champion", "all_pro_champion").
    Rookie cannot stack with other classifications (rookies didn't play previous season).
    """
    if isRookie:
        return "rookie"

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
            rating = getattr(player, 'playerRating', None)
            if rating is None:
                continue

            positionValue = player.position.value if hasattr(player.position, 'value') else int(player.position)
            isRookie = getattr(player, 'seasonsPlayed', 1) == 0

            # Determine classification
            classification = _buildClassification(
                playerId=player.id,
                isRookie=isRookie,
                mvpPlayerId=mvpPlayerId,
                championPlayerIds=champIds,
                allProPlayerIds=apIds,
            )

            # Determine team info
            teamObj = getattr(player, 'team', None)
            teamId = None
            if teamObj and hasattr(teamObj, 'id'):
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

            rating = getattr(player, 'playerRating', None)
            if rating is None:
                continue

            positionValue = player.position.value if hasattr(player.position, 'value') else int(player.position)

            teamObj = getattr(player, 'team', None)
            teamId = None
            if teamObj and hasattr(teamObj, 'id'):
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

        # Derive category from position if missing from effectConfig (legacy cards)
        POSITION_CATEGORY = {1: "multiplier", 2: "floobits", 3: "flat_fp", 4: "conditional", 5: "streak"}
        category = effectConfig.get("category") or POSITION_CATEGORY.get(template.position, "flat_fp")

        # Derive outputType for frontend coloring (legacy fallback)
        outputType = effectConfig.get("outputType")
        if not outputType:
            from managers.cardEffects import _deriveOutputType
            primary = effectConfig.get("primary", {})
            effectName = effectConfig.get("effectName", "")
            outputType = _deriveOutputType(category, effectName, primary)

        return {
            "id": userCard.id,
            "templateId": template.id,
            "playerId": template.player_id,
            "playerName": template.player_name,
            "teamId": template.team_id,
            "playerRating": template.player_rating,
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
            "isActive": isActive,
            "acquiredAt": userCard.acquired_at.isoformat() if userCard.acquired_at else None,
            "acquiredVia": userCard.acquired_via,
        }

    def sellCards(self, session, userId: int, userCardIds: List[int], currentSeason: int) -> dict:
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

        # Check none are currently equipped
        equippedIds = {
            ec.user_card_id
            for ec in session.query(EquippedCard)
            .filter(EquippedCard.user_card_id.in_(userCardIds), EquippedCard.user_id == userId)
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

    # ─── Pack Opening ─────────────────────────────────────────────────────────

    def openPack(self, session, userId: int, packTypeId: int, currentSeason: int) -> dict:
        """Buy and open a card pack. Returns the list of new cards.

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

        # Spend Floobits
        result = currencyRepo.spendFunds(
            userId, packType.cost,
            transactionType='pack_purchase',
            description=f"Opened {packType.display_name}",
        )
        if result is None:
            raise ValueError("Insufficient Floobits")

        # Get current-season templates for drawing
        allTemplates = templateRepo.getBySeason(currentSeason)
        if not allTemplates:
            raise ValueError("No card templates available for the current season")

        # Build weighted pool by edition using pack's rarity_weights
        packWeights = packType.rarity_weights or EDITION_BASE_WEIGHTS

        drawnTemplates: List[CardTemplate] = []
        cardsNeeded = packType.cards_per_pack

        # Handle guaranteed rarity first
        if packType.guaranteed_rarity:
            guaranteedEditions = self._editionsAtOrAbove(packType.guaranteed_rarity)
            guaranteedPool = [t for t in allTemplates if t.edition in guaranteedEditions]
            if guaranteedPool:
                picked = self._weightedDraw(guaranteedPool, packWeights, count=1)
                drawnTemplates.extend(picked)
                cardsNeeded -= len(picked)

            # Grand packs also guarantee a holographic or better
            if packType.name == 'grand':
                holoPlus = self._editionsAtOrAbove('holographic')
                holoPool = [t for t in allTemplates if t.edition in holoPlus and t not in drawnTemplates]
                if holoPool:
                    picked = self._weightedDraw(holoPool, packWeights, count=1)
                    drawnTemplates.extend(picked)
                    cardsNeeded -= len(picked)

            # Exquisite packs guarantee a second prismatic+ and a gold+
            if packType.name == 'exquisite':
                prismaticPlus = self._editionsAtOrAbove('prismatic')
                prismPool = [t for t in allTemplates if t.edition in prismaticPlus and t not in drawnTemplates]
                if prismPool:
                    picked = self._weightedDraw(prismPool, packWeights, count=1)
                    drawnTemplates.extend(picked)
                    cardsNeeded -= len(picked)
                goldPlus = self._editionsAtOrAbove('gold')
                goldPool = [t for t in allTemplates if t.edition in goldPlus and t not in drawnTemplates]
                if goldPool:
                    picked = self._weightedDraw(goldPool, packWeights, count=1)
                    drawnTemplates.extend(picked)
                    cardsNeeded -= len(picked)

        # Fill remaining slots with weighted random
        if cardsNeeded > 0:
            remainingPool = [t for t in allTemplates if t not in drawnTemplates]
            if not remainingPool:
                remainingPool = allTemplates
            filled = self._weightedDraw(remainingPool, packWeights, count=cardsNeeded)
            drawnTemplates.extend(filled)

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

        # Record the opening
        openingRecord = PackOpening(
            user_id=userId,
            pack_type_id=packType.id,
            cards_received=[t.id for t in drawnTemplates],
            cost=packType.cost,
        )
        openingRepo.save(openingRecord)

        # Serialize the new cards for response
        serialized = []
        for card in newCards:
            # Eagerly load template relationship
            session.refresh(card)
            serialized.append(self.serializeCard(card, currentSeason))

        return {
            "packName": packType.display_name,
            "cost": packType.cost,
            "cards": serialized,
        }

    def _editionsAtOrAbove(self, minEdition: str) -> set:
        """Return set of editions at or above the given rarity tier."""
        order = ['base', 'chrome', 'holographic', 'gold', 'prismatic', 'diamond']
        try:
            idx = order.index(minEdition)
        except ValueError:
            return {minEdition}
        return set(order[idx:])

    def _weightedDraw(self, pool: list, packWeights: dict, count: int) -> list:
        """Draw `count` templates from pool using weighted random selection."""
        if not pool:
            return []

        weights = []
        for t in pool:
            editionWeight = packWeights.get(t.edition, EDITION_BASE_WEIGHTS.get(t.edition, 1))
            # Higher-rated players are rarer within each edition
            ratingPenalty = max(1, 120 - t.player_rating)
            weights.append(editionWeight * ratingPenalty)

        # random.choices allows duplicates — that's fine for packs
        drawn = random.choices(pool, weights=weights, k=count)
        return drawn

    # ─── Featured Shop Cards ──────────────────────────────────────────────────

    FEATURED_CARD_COUNT = 5
    # Markup over sell value for shop singles
    SHOP_MARKUP = {
        'chrome': 3.0,
        'holographic': 3.0,
        'gold': 3.5,
        'prismatic': 4.0,
        'diamond': 5.0,
    }

    def getFeaturedCards(self, session, userId: int, currentSeason: int,
                         currentWeek: int = 0, isScheduledMode: bool = False) -> List[dict]:
        """Return the user's persisted featured shop cards for this season.

        Supports daily refresh: in scheduled mode, refreshes if generated_at is
        before today.  In testing modes, refreshes every 7-week cycle.
        On first call per user per season, generates a random selection and
        persists it.  Subsequent calls return the same set (minus purchased).
        """
        from database.models import FeaturedShopCard
        from database.repositories.card_repositories import CardTemplateRepository
        from datetime import datetime, date
        from constants import SWAP_CYCLE_WEEKS

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
                    # Refresh if generated before today
                    needsRefresh = sampleRow.generated_at.date() < date.today()
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
            # Only skip generation if there are purchased rows AND no refresh happened
            if anyThisSeason and not needsRefresh:
                return []

            # Generate fresh selection for this user
            templateRepo = CardTemplateRepository(session)
            allTemplates = templateRepo.getBySeason(currentSeason)
            nonBase = [t for t in allTemplates if t.edition != 'base']

            if not nonBase:
                return []

            # Weight toward rarer editions (invert rarity for selection bias)
            weights = []
            for t in nonBase:
                edWeight = EDITION_BASE_WEIGHTS.get(t.edition, 1)
                invWeight = max(1, 110 - edWeight)
                weights.append(invWeight)

            count = min(self.FEATURED_CARD_COUNT, len(nonBase))
            picked = []
            poolCopy = list(nonBase)
            weightsCopy = list(weights)
            for _ in range(count):
                if not poolCopy:
                    break
                choice = random.choices(poolCopy, weights=weightsCopy, k=1)[0]
                picked.append(choice)
                idx = poolCopy.index(choice)
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
