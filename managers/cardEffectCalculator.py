"""
Card Effect Calculator — computes weekly card bonuses for equipped cards.

Used by seasonManager._processWeekCardEffects() at week end for authoritative
persistence, and mirrored by frontend useFantasyLivePoints for live display.

Supports a two-pass system where modifier cards (amplifier, double_match, etc.)
affect other cards' bonuses rather than producing FP directly.
"""

import logging
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

logger = logging.getLogger(__name__)

# Maps conditional stat keys (from card effect_config) to
# (GamePlayerStats JSON column, sub-key within that JSON)
CONDITIONAL_STAT_MAP = {
    "passYards": ("passing_stats", "passYards"),
    "passTds":   ("passing_stats", "tds"),
    "rushYards": ("rushing_stats", "runYards"),
    "rushTds":   ("rushing_stats", "runTds"),
    "recYards":  ("receiving_stats", "rcvYards"),
    "recTds":    ("receiving_stats", "rcvTds"),
    "fgMade":    ("kicking_stats", "fgs"),
    "longFg":    ("kicking_stats", "longest"),
}

DEFAULT_MATCH_MULTIPLIER = 1.5

# Effect types that are modifiers (modify other cards, don't produce FP themselves)
MODIFIER_TYPES = {'amplifier', 'double_match', 'easy_threshold', 'base_amplifier', 'floobits_amplifier'}


@dataclass
class CardCalcContext:
    """Full context needed to compute card bonuses for one user for one week."""
    rosterPlayerIds: Set[int]
    weekPlayerStats: Dict[int, dict]
    weekRawFP: float
    rosterPlayerRatings: Dict[int, int] = field(default_factory=dict)
    winningTeamIds: Set[int] = field(default_factory=set)
    rosterTotalTds: int = 0
    positionAverageFP: Dict[int, float] = field(default_factory=dict)
    streakCounts: Dict[int, int] = field(default_factory=dict)  # keyed by equipped card id
    allEquippedEditions: Set[str] = field(default_factory=set)
    matchedCardCount: int = 0
    userFavoriteTeamId: Optional[int] = None


@dataclass
class CardBreakdown:
    slotNumber: int
    edition: str
    playerId: int
    playerName: str
    effectType: str
    baseFP: float
    matchMultiplied: bool
    conditionalBonus: float
    conditionalLabel: Optional[str]
    totalFP: float
    floobitsEarned: int


@dataclass
class CardBonusResult:
    totalBonusFP: float = 0.0
    floobitsEarned: int = 0
    cardBreakdowns: List[CardBreakdown] = field(default_factory=list)


def _playerStars(rating: int) -> int:
    """Convert a player rating to a 1-5 star rating."""
    return max(1, min(5, round(((rating - 60) / 35) * 5 + 1)))


def _countPlayerTds(playerStats: dict) -> int:
    """Count total TDs from a player's weekly game stats."""
    tds = 0
    passingStats = playerStats.get("passing_stats")
    if isinstance(passingStats, dict):
        tds += passingStats.get("tds", 0)
    rushingStats = playerStats.get("rushing_stats")
    if isinstance(rushingStats, dict):
        tds += rushingStats.get("runTds", 0)
    receivingStats = playerStats.get("receiving_stats")
    if isinstance(receivingStats, dict):
        tds += receivingStats.get("rcvTds", 0)
    return tds


def _getPlayerStat(playerStats: dict, statKey: str) -> float:
    """Look up a conditional stat value from a player's weekly game stats."""
    mapping = CONDITIONAL_STAT_MAP.get(statKey)
    if not mapping:
        return 0
    column, subKey = mapping
    statsJson = playerStats.get(column)
    if not statsJson or not isinstance(statsJson, dict):
        return 0
    return statsJson.get(subKey, 0)


def _computeCardEffect(
    effectConfig: dict,
    ctx: CardCalcContext,
    cardPlayerWeekFP: float,
    cardPlayerId: int,
    equippedCardId: int,
    cardEdition: str,
) -> tuple:
    """Compute base FP bonus and Floobits for a single card's effect.

    Returns (fpBonus: float, floobits: int)
    """
    effectType = effectConfig.get("type", "flat")

    # ─── Legacy types (backward compat) ──────────────────────────────────
    if effectType == "flat":
        return (effectConfig.get("baseFP", 0), 0)

    if effectType == "floor":
        return (effectConfig.get("guaranteedFP", 0), 0)

    if effectType == "multiplier":
        percent = effectConfig.get("percent", 0)
        return (ctx.weekRawFP * percent, 0)

    if effectType == "scaling":
        factor = effectConfig.get("factor", 0)
        return (cardPlayerWeekFP * factor, 0)

    if effectType == "currency":
        floobits = effectConfig.get("floobitsPerWeek", 0)
        return (0, int(floobits))

    if effectType == "dual":
        multiplierPercent = effectConfig.get("multiplierPercent", 0)
        floobits = effectConfig.get("floobitsPerWeek", 0)
        return (ctx.weekRawFP * multiplierPercent, int(floobits))

    # ─── New Base types ──────────────────────────────────────────────────
    if effectType == "win_bonus":
        if ctx.userFavoriteTeamId is not None and ctx.userFavoriteTeamId in ctx.winningTeamIds:
            return (effectConfig.get("bonusFP", 0), 0)
        return (0, 0)

    if effectType == "td_bonus":
        perTdFP = effectConfig.get("perTdFP", 0)
        return (perTdFP * ctx.rosterTotalTds, 0)

    # ─── New Chrome types ────────────────────────────────────────────────
    if effectType == "roster_stars":
        perStarPlayerFP = effectConfig.get("perStarPlayerFP", 0)
        minStars = effectConfig.get("minStars", 3)
        count = sum(
            1 for pid in ctx.rosterPlayerIds
            if _playerStars(ctx.rosterPlayerRatings.get(pid, 60)) >= minStars
        )
        return (perStarPlayerFP * count, 0)

    if effectType == "underdog":
        perUnderdogFP = effectConfig.get("perUnderdogFP", 0)
        maxStars = effectConfig.get("maxStars", 2)
        count = sum(
            1 for pid in ctx.rosterPlayerIds
            if _playerStars(ctx.rosterPlayerRatings.get(pid, 60)) <= maxStars
        )
        return (perUnderdogFP * count, 0)

    if effectType == "outperform":
        bonusFP = effectConfig.get("bonusFP", 0)
        # Check if card player outperformed the position average
        posAvg = ctx.positionAverageFP.get(cardPlayerId, 0)
        if cardPlayerWeekFP > posAvg > 0:
            return (bonusFP, 0)
        return (0, 0)

    if effectType == "streak":
        baseFP = effectConfig.get("baseFP", 0)
        growthPerWeek = effectConfig.get("growthPerWeek", 0)
        streakCount = ctx.streakCounts.get(equippedCardId, 1)
        # FP = baseFP + growthPerWeek * (streakCount - 1)
        return (baseFP + growthPerWeek * (streakCount - 1), 0)

    # ─── New Holo types ──────────────────────────────────────────────────
    if effectType == "top_performer":
        percent = effectConfig.get("percent", 0)
        # Find the best roster player's FP this week
        bestFP = 0
        for pid in ctx.rosterPlayerIds:
            pStats = ctx.weekPlayerStats.get(pid, {})
            pFP = pStats.get("fantasyPoints", 0)
            if pFP > bestFP:
                bestFP = pFP
        return (bestFP * percent, 0)

    # ─── New Gold types ──────────────────────────────────────────────────
    if effectType == "td_currency":
        floobitsPerTd = effectConfig.get("floobitsPerTd", 0)
        cardPlayerTds = _countPlayerTds(ctx.weekPlayerStats.get(cardPlayerId, {}))
        return (0, int(floobitsPerTd * cardPlayerTds))

    if effectType == "hot_roster_currency":
        floobitsPerHotPlayer = effectConfig.get("floobitsPerHotPlayer", 0)
        fpThreshold = effectConfig.get("fpThreshold", 10)
        count = sum(
            1 for pid in ctx.rosterPlayerIds
            if ctx.weekPlayerStats.get(pid, {}).get("fantasyPoints", 0) >= fpThreshold
        )
        return (0, int(floobitsPerHotPlayer * count))

    if effectType == "threshold_currency":
        # Floobits if card player hits their conditional
        # (conditional check handled separately, just return the floobits amount)
        return (0, 0)  # Floobits awarded via conditional check path

    # ─── New Prismatic types (non-modifier) ──────────────────────────────
    if effectType == "edition_diversity":
        perEditionFP = effectConfig.get("perEditionFP", 0)
        uniqueEditions = len(ctx.allEquippedEditions)
        return (perEditionFP * uniqueEditions, 0)

    # ─── New Diamond types ───────────────────────────────────────────────
    if effectType == "scaling_currency":
        scalingPercent = effectConfig.get("scalingPercent", 0)
        baseFloobits = effectConfig.get("baseFloobits", 0)
        fpBonus = cardPlayerWeekFP * scalingPercent
        return (fpBonus, int(baseFloobits))

    if effectType == "mirror":
        factor = effectConfig.get("factor", 0)
        fpBonus = cardPlayerWeekFP * factor
        floobits = int(cardPlayerWeekFP * factor)
        return (fpBonus, floobits)

    if effectType == "scaling_roster":
        basePercent = effectConfig.get("basePercent", 0)
        matchedBonus = effectConfig.get("matchedBonus", 0)
        effectivePercent = basePercent + matchedBonus * ctx.matchedCardCount
        return (cardPlayerWeekFP * effectivePercent, 0)

    return (0, 0)


def _checkConditional(
    conditional: Optional[dict],
    playerStats: dict,
    thresholdDivisor: float = 1.0,
) -> tuple:
    """Check if a conditional bonus is triggered.

    Returns (bonusFP: float, label: str or None)
    """
    if not conditional:
        return (0, None)

    statKey = conditional.get("stat")
    threshold = conditional.get("threshold", 0)
    bonus = conditional.get("bonus", 0)
    label = conditional.get("label")

    if not statKey:
        return (0, None)

    # Apply threshold divisor (from easy_threshold modifier)
    effectiveThreshold = threshold / thresholdDivisor if thresholdDivisor > 0 else threshold

    actualValue = _getPlayerStat(playerStats, statKey)
    if actualValue >= effectiveThreshold:
        return (bonus, label)

    return (0, None)


def _checkThresholdCurrency(
    conditional: Optional[dict],
    playerStats: dict,
    floobitsAmount: int,
    thresholdDivisor: float = 1.0,
) -> int:
    """Check if threshold_currency conditional is met, return Floobits if so."""
    if not conditional:
        return 0

    statKey = conditional.get("stat")
    threshold = conditional.get("threshold", 0)

    if not statKey:
        return 0

    effectiveThreshold = threshold / thresholdDivisor if thresholdDivisor > 0 else threshold
    actualValue = _getPlayerStat(playerStats, statKey)
    if actualValue >= effectiveThreshold:
        return floobitsAmount
    return 0


def calculateWeekCardBonuses(
    equippedCards,
    ctx: CardCalcContext,
) -> CardBonusResult:
    """Calculate card bonuses for one user's equipped cards for a week.

    Uses a two-pass system:
    1. Detect modifiers → extract effective match multiplier, threshold divisor, etc.
    2. Pass 1: Compute all non-modifier cards using effective modifiers
    3. Pass 2: Apply amplifier/base_amplifier bonuses to pass-1 results
    4. Sum everything

    Args:
        equippedCards: list of EquippedCard ORM objects (with user_card.card_template loaded)
        ctx: CardCalcContext with all necessary context for computation

    Returns:
        CardBonusResult with total bonus FP, Floobits earned, and per-card breakdowns
    """
    result = CardBonusResult()

    if not equippedCards:
        return result

    # ─── Detect modifiers ────────────────────────────────────────────────
    effectiveMatchMultiplier = DEFAULT_MATCH_MULTIPLIER
    thresholdDivisor = 1.0
    amplifierPercent = 0.0
    baseAmplifierFactor = 0.0
    floobitsAmplifierPercent = 0.0

    modifierCards = []
    regularCards = []

    for eq in equippedCards:
        template = eq.user_card.card_template
        effectConfig = template.effect_config or {}
        effectType = effectConfig.get("type", "flat")

        if effectType in MODIFIER_TYPES:
            modifierCards.append(eq)
            if effectType == "double_match":
                effectiveMatchMultiplier = effectConfig.get("newMatchMultiplier", 3.0)
            elif effectType == "easy_threshold":
                thresholdDivisor = effectConfig.get("thresholdDivisor", 2.0)
            elif effectType == "amplifier":
                amplifierPercent += effectConfig.get("amplifyPercent", 0) / 100.0
            elif effectType == "base_amplifier":
                baseAmplifierFactor = max(baseAmplifierFactor, effectConfig.get("amplifyFactor", 2.0))
            elif effectType == "floobits_amplifier":
                floobitsAmplifierPercent += effectConfig.get("amplifyPercent", 0) / 100.0
        else:
            regularCards.append(eq)

    # ─── Pass 1: Compute all non-modifier cards ─────────────────────────
    pass1Results = []  # (eq, baseFP, floobits, conditionalBonus, conditionalLabel, isMatch, effectType, edition)

    for eq in regularCards:
        template = eq.user_card.card_template
        effectConfig = template.effect_config or {}
        effectType = effectConfig.get("type", "flat")
        cardPlayerId = template.player_id
        cardEdition = template.edition

        # Get card player's weekly stats
        cardPlayerStats = ctx.weekPlayerStats.get(cardPlayerId, {})
        cardPlayerWeekFP = cardPlayerStats.get("fantasyPoints", 0)

        # Compute base effect
        baseFP, floobits = _computeCardEffect(
            effectConfig, ctx, cardPlayerWeekFP, cardPlayerId, eq.id, cardEdition
        )

        # Check roster match
        isMatch = cardPlayerId in ctx.rosterPlayerIds
        conditionalBonus = 0.0
        conditionalLabel = None

        if isMatch:
            # Amplify FP bonus with effective match multiplier
            baseFP *= effectiveMatchMultiplier
            floobits = int(floobits * effectiveMatchMultiplier)

            # Check conditional
            conditional = effectConfig.get("conditional")
            conditionalBonus, conditionalLabel = _checkConditional(
                conditional, cardPlayerStats, thresholdDivisor
            )

        # Handle threshold_currency special case (Floobits from conditional)
        if effectType == "threshold_currency":
            conditional = effectConfig.get("conditional")
            thresholdFloobits = effectConfig.get("floobits", 0)
            if isMatch:
                thresholdFloobits = int(thresholdFloobits * effectiveMatchMultiplier)
            floobits += _checkThresholdCurrency(
                conditional, cardPlayerStats, thresholdFloobits, thresholdDivisor
            )

        pass1Results.append((eq, baseFP, floobits, conditionalBonus, conditionalLabel, isMatch, effectType, cardEdition))

    # ─── Pass 2: Apply amplifiers ────────────────────────────────────────
    for eq, baseFP, floobits, conditionalBonus, conditionalLabel, isMatch, effectType, cardEdition in pass1Results:
        template = eq.user_card.card_template
        finalFP = baseFP

        # Apply base_amplifier (doubles base-edition card FP)
        if baseAmplifierFactor > 0 and cardEdition == 'base':
            finalFP *= baseAmplifierFactor

        # Apply general amplifier
        if amplifierPercent > 0:
            finalFP *= (1 + amplifierPercent)

        totalFP = finalFP + conditionalBonus

        # Apply floobits amplifier
        finalFloobits = floobits
        if floobitsAmplifierPercent > 0 and floobits > 0:
            finalFloobits = int(floobits * (1 + floobitsAmplifierPercent))

        breakdown = CardBreakdown(
            slotNumber=eq.slot_number,
            edition=cardEdition,
            playerId=template.player_id,
            playerName=template.player_name,
            effectType=effectType,
            baseFP=round(finalFP, 2),
            matchMultiplied=isMatch,
            conditionalBonus=conditionalBonus,
            conditionalLabel=conditionalLabel,
            totalFP=round(totalFP, 2),
            floobitsEarned=finalFloobits,
        )

        result.totalBonusFP += totalFP
        result.floobitsEarned += finalFloobits
        result.cardBreakdowns.append(breakdown)

    # ─── Add modifier card breakdowns (they produce 0 FP but show in UI) ─
    for eq in modifierCards:
        template = eq.user_card.card_template
        effectConfig = template.effect_config or {}
        effectType = effectConfig.get("type", "flat")
        cardPlayerId = template.player_id

        # Modifiers can still have conditionals if matched
        isMatch = cardPlayerId in ctx.rosterPlayerIds
        conditionalBonus = 0.0
        conditionalLabel = None

        if isMatch:
            conditional = effectConfig.get("conditional")
            cardPlayerStats = ctx.weekPlayerStats.get(cardPlayerId, {})
            conditionalBonus, conditionalLabel = _checkConditional(
                conditional, cardPlayerStats, thresholdDivisor
            )

        breakdown = CardBreakdown(
            slotNumber=eq.slot_number,
            edition=template.edition,
            playerId=cardPlayerId,
            playerName=template.player_name,
            effectType=effectType,
            baseFP=0,
            matchMultiplied=isMatch,
            conditionalBonus=conditionalBonus,
            conditionalLabel=conditionalLabel,
            totalFP=round(conditionalBonus, 2),
            floobitsEarned=0,
        )

        result.totalBonusFP += conditionalBonus
        result.cardBreakdowns.append(breakdown)

    result.totalBonusFP = round(result.totalBonusFP, 2)
    return result
