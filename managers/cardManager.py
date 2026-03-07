"""Card Manager - handles card template generation and card operations."""

import math
import random
from typing import List, Dict, Any, Optional
from logger_config import get_logger

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

# ─── Effect Pools by Edition ────────────────────────────────────────────────
# Each edition draws randomly from its pool of possible effects.
# Weights control how often each effect type appears within that edition.

EDITION_EFFECT_POOLS = {
    'base': [
        # (type_key, weight)
        ('flat', 3),
        ('win_bonus', 2),
        ('td_bonus', 2),
    ],
    'chrome': [
        ('roster_stars', 2),
        ('underdog', 2),
        ('outperform', 2),
        ('streak', 2),
    ],
    'holographic': [
        ('multiplier', 3),
        ('top_performer', 3),
        ('base_amplifier', 1),
    ],
    'gold': [
        ('currency', 3),
        ('td_currency', 2),
        ('hot_roster_currency', 2),
        ('threshold_currency', 2),
    ],
    'prismatic': [
        ('amplifier', 2),
        ('double_match', 1),
        ('easy_threshold', 1),
        ('floobits_amplifier', 1),
        ('edition_diversity', 2),
    ],
    'diamond': [
        ('scaling_currency', 2),
        ('mirror', 2),
        ('scaling_roster', 2),
    ],
}

# Position value mapping for conditional bonuses
POSITION_CONDITIONALS = {
    1: [  # QB
        {"stat": "passYards", "threshold": 300, "bonus": 5, "label": "300+ pass yards"},
        {"stat": "passTds", "threshold": 3, "bonus": 8, "label": "3+ pass TDs"},
    ],
    2: [  # RB
        {"stat": "rushYards", "threshold": 100, "bonus": 5, "label": "100+ rush yards"},
        {"stat": "rushTds", "threshold": 2, "bonus": 8, "label": "2+ rush TDs"},
    ],
    3: [  # WR
        {"stat": "recYards", "threshold": 100, "bonus": 5, "label": "100+ rec yards"},
        {"stat": "recTds", "threshold": 2, "bonus": 8, "label": "2+ rec TDs"},
    ],
    4: [  # TE
        {"stat": "recYards", "threshold": 75, "bonus": 4, "label": "75+ rec yards"},
        {"stat": "recTds", "threshold": 1, "bonus": 5, "label": "1+ rec TD"},
    ],
    5: [  # K
        {"stat": "fgMade", "threshold": 3, "bonus": 4, "label": "3+ FGs made"},
        {"stat": "longFg", "threshold": 50, "bonus": 5, "label": "50+ yard FG"},
    ],
}


def buildEffectConfig(edition: str, playerRating: int, position: int) -> dict:
    """Build the effect_config JSON for a card template based on edition and player rating."""
    ratingNorm = playerRating - 60  # Normalize: 60-rated → 0, 95-rated → 35

    # Pick one conditional for the position
    conditionals = POSITION_CONDITIONALS.get(position, [])
    conditional = conditionals[0] if conditionals else None

    if edition == 'base':
        return {
            "type": "flat",
            "baseFP": round(2 + ratingNorm * 0.075, 2),
            "conditional": conditional,
        }

    elif edition == 'holographic':
        return {
            "type": "multiplier",
            "percent": round((playerRating / 100) * 0.05, 4),
            "conditional": conditional,
        }

    elif edition == 'prismatic':
        return {
            "type": "scaling",
            "factor": round((playerRating / 100) * 0.08, 4),
            "conditional": conditional,
        }

    elif edition == 'gold':
        return {
            "type": "currency",
            "floobitsPerWeek": int(round(5 + ratingNorm * 0.3)),
            "conditional": conditional,
        }

    elif edition == 'chrome':
        return {
            "type": "floor",
            "guaranteedFP": round(3 + ratingNorm * 0.15, 2),
            "conditional": conditional,
        }

    elif edition == 'diamond':
        holoPercent = round((playerRating / 100) * 0.05, 4)
        goldFloobits = int(round(5 + ratingNorm * 0.3))
        return {
            "type": "dual",
            "multiplierPercent": round(holoPercent * 0.6, 4),
            "floobitsPerWeek": int(round(goldFloobits * 0.6)),
            "conditional": conditional,
        }

    return {"type": "flat", "baseFP": 2, "conditional": conditional}


def buildEffectConfigFromPool(
    edition: str, playerRating: int, position: int, teamId: int | None
) -> dict:
    """Build effect_config by randomly selecting from the edition's effect pool.

    Each edition has multiple possible effect types with weighted selection.
    This replaces the old 1:1 edition→effect mapping for newly generated cards.
    """
    ratingNorm = playerRating - 60  # 60-rated → 0, 95-rated → 35

    # Pick a conditional for position-aware effects
    conditionals = POSITION_CONDITIONALS.get(position, [])
    conditional = conditionals[0] if conditionals else None

    # Select effect type from pool
    pool = EDITION_EFFECT_POOLS.get(edition)
    if not pool:
        return {"type": "flat", "baseFP": 2, "conditional": conditional}

    types, weights = zip(*pool)
    effectType = random.choices(types, weights=weights, k=1)[0]

    # ─── Base edition ────────────────────────────────────────────────────
    if effectType == 'flat':
        baseFP = round(2 + ratingNorm * 0.075, 1)
        return {
            "type": "flat",
            "baseFP": baseFP,
            "conditional": conditional,
            "description": f"+{baseFP} FP per week",
        }

    if effectType == 'win_bonus':
        bonusFP = round(4 + ratingNorm * 0.15, 1)
        return {
            "type": "win_bonus",
            "bonusFP": bonusFP,
            "conditional": conditional,
            "description": f"+{bonusFP} FP when your team wins",
        }

    if effectType == 'td_bonus':
        perTdFP = round(0.8 + ratingNorm * 0.03, 1)
        return {
            "type": "td_bonus",
            "perTdFP": perTdFP,
            "conditional": conditional,
            "description": f"+{perTdFP} FP per roster TD",
        }

    # ─── Chrome edition ──────────────────────────────────────────────────
    if effectType == 'roster_stars':
        perStarPlayerFP = round(0.6 + ratingNorm * 0.025, 1)
        return {
            "type": "roster_stars",
            "perStarPlayerFP": perStarPlayerFP,
            "minStars": 3,
            "conditional": conditional,
            "description": f"+{perStarPlayerFP} FP per 3★+ roster player",
        }

    if effectType == 'underdog':
        perUnderdogFP = round(1.5 + ratingNorm * 0.04, 1)
        return {
            "type": "underdog",
            "perUnderdogFP": perUnderdogFP,
            "maxStars": 2,
            "conditional": conditional,
            "description": f"+{perUnderdogFP} FP per 2★ or below roster player",
        }

    if effectType == 'outperform':
        bonusFP = round(3.0 + ratingNorm * 0.1, 1)
        return {
            "type": "outperform",
            "bonusFP": bonusFP,
            "conditional": conditional,
            "description": f"+{bonusFP} FP if player beats the league avg for their position",
        }

    if effectType == 'streak':
        baseFP = round(1.0 + ratingNorm * 0.04, 1)
        growthPerWeek = round(0.3 + ratingNorm * 0.01, 1)
        return {
            "type": "streak",
            "baseFP": baseFP,
            "growthPerWeek": growthPerWeek,
            "conditional": conditional,
            "description": f"+{baseFP} FP, +{growthPerWeek} per consecutive week",
        }

    # ─── Holographic edition ─────────────────────────────────────────────
    if effectType == 'multiplier':
        percent = round((playerRating / 100) * 0.05, 3)
        return {
            "type": "multiplier",
            "percent": percent,
            "conditional": conditional,
            "description": f"+{round(percent * 100, 1)}% of roster's weekly FP",
        }

    if effectType == 'top_performer':
        percent = round((playerRating / 100) * 0.20, 3)
        return {
            "type": "top_performer",
            "percent": percent,
            "conditional": conditional,
            "description": f"+{round(percent * 100, 1)}% of top roster player's FP",
        }

    if effectType == 'base_amplifier':
        return {
            "type": "base_amplifier",
            "amplifyFactor": 2.0,
            "conditional": conditional,
            "description": "Doubles FP from your Base cards",
        }

    # ─── Gold edition ────────────────────────────────────────────────────
    if effectType == 'currency':
        floobitsPerWeek = int(round(5 + ratingNorm * 0.3))
        return {
            "type": "currency",
            "floobitsPerWeek": floobitsPerWeek,
            "conditional": conditional,
            "description": f"+{floobitsPerWeek} Floobits per week",
        }

    if effectType == 'td_currency':
        floobitsPerTd = int(round(3 + ratingNorm * 0.15))
        return {
            "type": "td_currency",
            "floobitsPerTd": floobitsPerTd,
            "conditional": conditional,
            "description": f"+{floobitsPerTd} Floobits per player TD",
        }

    if effectType == 'hot_roster_currency':
        floobitsPerHotPlayer = int(round(2 + ratingNorm * 0.1))
        return {
            "type": "hot_roster_currency",
            "floobitsPerHotPlayer": floobitsPerHotPlayer,
            "fpThreshold": 10,
            "conditional": conditional,
            "description": f"+{floobitsPerHotPlayer} Floobits per roster player with 10+ FP",
        }

    if effectType == 'threshold_currency':
        floobits = int(round(15 + ratingNorm * 0.5))
        return {
            "type": "threshold_currency",
            "floobits": floobits,
            "conditional": conditional,
            "description": f"+{floobits} Floobits if conditional met",
        }

    # ─── Prismatic edition ───────────────────────────────────────────────
    if effectType == 'amplifier':
        amplifyPercent = round(15 + max(0, ratingNorm - 25) * 1.0, 1)
        return {
            "type": "amplifier",
            "amplifyPercent": amplifyPercent,
            "conditional": conditional,
            "description": f"+{round(amplifyPercent)}% to all other card bonuses",
        }

    if effectType == 'double_match':
        return {
            "type": "double_match",
            "newMatchMultiplier": 3.0,
            "conditional": conditional,
            "description": "Match bonus 3.0x for all cards",
        }

    if effectType == 'easy_threshold':
        return {
            "type": "easy_threshold",
            "thresholdDivisor": 2.0,
            "conditional": conditional,
            "description": "Conditional thresholds halved",
        }

    if effectType == 'floobits_amplifier':
        amplifyPercent = round(30 + max(0, ratingNorm - 25) * 1.5, 1)
        return {
            "type": "floobits_amplifier",
            "amplifyPercent": amplifyPercent,
            "conditional": conditional,
            "description": f"+{round(amplifyPercent)}% to all Floobits earnings",
        }

    if effectType == 'edition_diversity':
        perEditionFP = round(2.0 + max(0, ratingNorm - 25) * 0.15, 1)
        return {
            "type": "edition_diversity",
            "perEditionFP": perEditionFP,
            "conditional": conditional,
            "description": f"+{perEditionFP} FP per unique edition equipped",
        }

    # ─── Diamond edition ─────────────────────────────────────────────────
    if effectType == 'scaling_currency':
        scalingPercent = round((playerRating / 100) * 0.04, 3)
        baseFloobits = int(round(8 + max(0, ratingNorm - 30) * 0.5))
        return {
            "type": "scaling_currency",
            "scalingPercent": scalingPercent,
            "baseFloobits": baseFloobits,
            "conditional": conditional,
            "description": f"+{round(scalingPercent * 100, 1)}% of player's FP + {baseFloobits} Floobits",
        }

    if effectType == 'mirror':
        factor = round((playerRating / 100) * 0.06, 3)
        return {
            "type": "mirror",
            "factor": factor,
            "conditional": conditional,
            "description": f"+{round(factor * 100, 1)}% of player's FP as FP and Floobits",
        }

    if effectType == 'scaling_roster':
        basePercent = round((playerRating / 100) * 0.05, 3)
        matchedBonus = 0.01
        return {
            "type": "scaling_roster",
            "basePercent": basePercent,
            "matchedBonus": matchedBonus,
            "conditional": conditional,
            "description": f"+{round(basePercent * 100, 1)}% of player's FP (+{round(matchedBonus * 100)}% per matched card)",
        }

    # Fallback
    return {"type": "flat", "baseFP": 2, "conditional": conditional}


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


class CardManager:
    """Manages card template generation and card operations."""

    def __init__(self, serviceContainer):
        self.serviceContainer = serviceContainer

    def generateSeasonTemplates(self, session, seasonNumber: int) -> int:
        """Generate card templates for all active players for a season.

        Called at the start of each new season. Creates one template per
        eligible (player, edition) pair.

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

        templates: List[CardTemplate] = []

        for player in playerManager.activePlayers:
            rating = getattr(player, 'playerRating', None)
            if rating is None:
                continue

            positionValue = player.position.value if hasattr(player.position, 'value') else int(player.position)
            isRookie = getattr(player, 'seasonsPlayed', 1) == 0

            # Determine team info
            teamObj = getattr(player, 'team', None)
            teamId = None
            if teamObj and hasattr(teamObj, 'id'):
                teamId = teamObj.id

            for edition, threshold in EDITION_THRESHOLDS.items():
                if rating < threshold:
                    continue

                effectConfig = buildEffectConfigFromPool(edition, rating, positionValue, teamId)
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
                )
                templates.append(template)

        if templates:
            templateRepo.saveBatch(templates)
            logger.info(f"Generated {len(templates)} card templates for season {seasonNumber}")
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

                effectConfig = buildEffectConfigFromPool(edition, rating, positionValue, teamId)
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
            "effectConfig": template.effect_config,
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

        # Calculate total and sell
        totalFloobits = 0
        for card in cards:
            isActive = card.card_template.season_created == currentSeason
            totalFloobits += getSellValue(card.card_template.edition, isActive=isActive)

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

            # Elite packs also guarantee a holographic or better
            if packType.name == 'elite':
                holoPlus = self._editionsAtOrAbove('holographic')
                holoPool = [t for t in allTemplates if t.edition in holoPlus and t not in drawnTemplates]
                if holoPool:
                    picked = self._weightedDraw(holoPool, packWeights, count=1)
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

    def getFeaturedCards(self, session, userId: int, currentSeason: int) -> List[dict]:
        """Return the user's persisted featured shop cards for this season.

        On first call per user per season, generates a random selection and
        persists it.  Subsequent calls return the same set (minus purchased).
        """
        from database.models import FeaturedShopCard
        from database.repositories.card_repositories import CardTemplateRepository

        # Check for existing selection
        existing = (
            session.query(FeaturedShopCard)
            .filter_by(user_id=userId, season=currentSeason, purchased=False)
            .all()
        )

        if not existing:
            # Check if user ever had featured cards this season (all purchased)
            anyThisSeason = (
                session.query(FeaturedShopCard)
                .filter_by(user_id=userId, season=currentSeason)
                .first()
            )
            if anyThisSeason:
                # All purchased, nothing left
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

            # Persist the selection
            for t in picked:
                featuredRow = FeaturedShopCard(
                    user_id=userId,
                    season=currentSeason,
                    card_template_id=t.id,
                    purchased=False,
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
