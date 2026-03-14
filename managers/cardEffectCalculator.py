"""
Card Effect Calculator — computes weekly card bonuses for equipped cards.

Used by seasonManager._processWeekCardEffects() at week end for authoritative
persistence, and mirrored by fantasyTracker for live display.

Single-pass system: each card's named effect is computed via cardEffects.computeEffect(),
then match bonus and secondary effects are applied.
"""

import hashlib
import logging
import random as _random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

from managers.cardEffects import (
    computeEffect, checkStreakCondition, EffectResult,
    EDITION_SECONDARY, POSITION_CONDITIONALS,
)

logger = logging.getLogger(__name__)

# Maps conditional stat keys to (GamePlayerStats JSON column, sub-key)
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


@dataclass
class CardCalcContext:
    """Full context needed to compute card bonuses for one user for one week."""
    # Core roster data
    rosterPlayerIds: Set[int] = field(default_factory=set)
    weekPlayerStats: Dict[int, dict] = field(default_factory=dict)
    weekRawFP: float = 0.0
    rosterPlayerRatings: Dict[int, int] = field(default_factory=dict)
    rosterTotalTds: int = 0
    rosterPlayerPositions: Dict[int, int] = field(default_factory=dict)
    streakCounts: Dict[int, int] = field(default_factory=dict)

    # Favorite team data
    userFavoriteTeamId: Optional[int] = None
    favoriteTeamElo: float = 1500.0
    favoriteTeamStreak: int = 0  # Positive = win streak, negative = loss streak
    favoriteTeamPriorStreak: int = 0  # Streak value before this week's game result
    favoriteTeamSeasonLosses: int = 0
    favoriteTeamInPlayoffs: bool = False
    favoriteTeamWonThisWeek: bool = False
    favoriteTeamOpponentElo: float = 1500.0
    favoriteTeamOpponentName: str = ""
    favoriteTeamBigPlays: int = 0
    favoriteTeamGameFinal: bool = False
    favoriteTeamSeasonUpsetWins: int = 0

    # Roster tracking
    rosterUnchangedWeeks: int = 0

    # Cross-team data
    leagueAverageElo: float = 1500.0
    teamResults: Dict[int, bool] = field(default_factory=dict)  # teamId → won
    playerPerformanceRatings: Dict[int, float] = field(default_factory=dict)

    # Per-game performance ratings (single-week, same formula as season perf)
    gamePerformanceRatings: Dict[int, float] = field(default_factory=dict)

    # Card position — set per-card in the calculator loop
    cardPosition: int = 0

    # Roster player team IDs (for same-team stacking effects)
    rosterPlayerTeamIds: Dict[int, int] = field(default_factory=dict)  # playerId → teamId

    # Roster player names (for stat line display)
    rosterPlayerNames: Dict[int, str] = field(default_factory=dict)  # playerId → name

    # Favorite team game-outcome data
    favoriteTeamScoreMargin: int = 0
    favoriteTeamComebackWin: bool = False
    favoriteTeamLargestDeficit: int = 0
    favoriteTeamWalkOffWin: bool = False

    # Equipped hand composition (for card-to-card effects)
    equippedCardPositions: List[int] = field(default_factory=list)
    equippedCardOutputTypes: List[str] = field(default_factory=list)
    equippedCardEffectNames: List[str] = field(default_factory=list)

    # Weekly modifier
    activeModifier: str = ""  # e.g. "amplify", "grounded", ""

    # Swap data (for Stockpiler effect)
    unusedSwaps: int = 0

    # Chance card infrastructure
    userId: int = 0
    season: int = 0
    weekNumber: int = 0
    chanceBonus: float = 0.0  # Sum of Providence + innate synergy + Fortunate modifier
    chanceCardCount: int = 0  # Number of chance cards in hand (for synergy effects)
    kickerSeasonFgMisses: int = 0  # Season-long kicker FG misses (for Good Neighbor)

    # Streak card infrastructure
    streakCardCount: int = 0  # Number of streak cards in hand (for synergy effects)
    activeStreakCount: int = 0  # Number of season streak cards with active (non-zero) streaks
    liveStreakConditionsMet: Dict[int, bool] = field(default_factory=dict)  # eqId → conditionMet this game

    # Internal — set by computeEffect dispatcher, not by caller
    _currentEffectName: str = ""
    _firstPassBreakdowns: Optional[List] = None  # Set for second-pass effects


@dataclass
class CardBreakdown:
    """Per-card breakdown for display and persistence."""
    slotNumber: int = 0
    edition: str = ""
    playerId: int = 0
    playerName: str = ""

    # Effect identity
    effectName: str = ""
    displayName: str = ""
    detail: str = ""          # Human-readable effect description (e.g. "+2.5 FP per week")
    category: str = ""
    outputType: str = "fp"  # "fp", "mult", "floobits"

    # Primary effect
    primaryFP: float = 0.0
    primaryFloobits: int = 0
    primaryMult: float = 0.0   # FPx factor (e.g. 1.3 means ×1.3)

    # Match bonus
    matchMultiplied: bool = False
    matchMultiplier: float = DEFAULT_MATCH_MULTIPLIER
    preMatchFP: float = 0.0
    preMatchFloobits: int = 0
    preMatchMult: float = 0.0

    # Position conditional
    conditionalBonus: float = 0.0
    conditionalLabel: Optional[str] = None

    # Secondary effect (from edition)
    secondaryFP: float = 0.0
    secondaryFloobits: int = 0
    secondaryMult: float = 0.0   # FPx factor from edition

    # Totals
    totalFP: float = 0.0
    floobitsEarned: int = 0

    # Roster player stat line (for roster-position-based effects)
    playerStatLine: str = ""

    # Human-readable equation showing how primary output was derived
    equation: str = ""

    # Chance card metadata
    isChanceEffect: bool = False
    chanceRoll: float = 0.0
    chanceThreshold: float = 0.0
    chanceTriggered: bool = False


@dataclass
class CardBonusResult:
    totalBonusFP: float = 0.0
    multFactors: List[float] = field(default_factory=list)  # All FPx factors (each >1)
    floobitsEarned: int = 0
    cardBreakdowns: List[CardBreakdown] = field(default_factory=list)


# Effects that use the roster player's stats at the card's position
_ROSTER_POSITION_EFFECTS = {
    "luminary", "squire", "cha_ching", "ace_up_the_sleeve",
    "showoff", "flourish", "spotlight_moment", "schadenfreude", "hot_hand",
    # New position-based effects
    "gunslinger", "air_raid", "workhorse", "goal_line_vulture",
    "possession", "trebuchet", "double_trouble",
    "safety_blanket", "mismatch", "sniper",
    "game_ball", "spectacle", "indemnity",
}


def _buildPlayerStatLine(effectName: str, cardPlayerId: int, ctx) -> str:
    """Build a short stat summary for roster-position-based effects.

    Looks up the roster player(s) at the card's position (ctx.cardPosition)
    instead of the card player. For WR (pos 3), combines both WR1+WR2 stats.
    """
    if effectName not in _ROSTER_POSITION_EFFECTS:
        return ""

    # Find roster player(s) at the card's position
    rosterPids = [
        pid for pid, pos in ctx.rosterPlayerPositions.items()
        if pos == ctx.cardPosition and pid in ctx.rosterPlayerIds
    ]
    if not rosterPids:
        return ""

    # Build player name prefix
    names = [ctx.rosterPlayerNames.get(pid, "?") for pid in rosterPids]
    namePrefix = " + ".join(names)

    # Aggregate stats across all roster players at this position (handles WR1+WR2)
    totalFP = 0
    totalTds = 0
    totalPassYards = 0
    totalRushYards = 0
    totalRecYards = 0
    totalFgs = 0

    for pid in rosterPids:
        stats = ctx.weekPlayerStats.get(pid, {})
        if not stats:
            continue
        totalFP += stats.get("fantasyPoints", 0)
        passing = stats.get("passing_stats", {})
        rushing = stats.get("rushing_stats", {})
        receiving = stats.get("receiving_stats", {})
        kicking = stats.get("kicking_stats", {})
        totalTds += (passing.get("tds", 0) + rushing.get("runTds", 0) + receiving.get("rcvTds", 0))
        totalPassYards += passing.get("passYards", 0)
        totalRushYards += rushing.get("runYards", 0)
        totalRecYards += receiving.get("rcvYards", 0)
        totalFgs += kicking.get("fgs", 0)

    parts = []
    if totalFP:
        parts.append(f"{int(totalFP)} FP")
    if totalTds:
        parts.append(f"{totalTds} TD")
    if totalPassYards:
        parts.append(f"{totalPassYards} pass yds")
    if totalRushYards:
        parts.append(f"{totalRushYards} rush yds")
    if totalRecYards:
        parts.append(f"{totalRecYards} rec yds")
    if totalFgs:
        parts.append(f"{totalFgs} FG")

    if not parts:
        return namePrefix
    return f"{namePrefix}: {', '.join(parts)}"


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


def _checkConditional(conditional: Optional[dict], playerStats: dict) -> tuple:
    """Check if a position conditional bonus is triggered.

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

    actualValue = _getPlayerStat(playerStats, statKey)
    if actualValue >= threshold:
        return (bonus, label)

    return (0, None)


# Second-pass effects that need access to first-pass card results
_SECOND_PASS_EFFECTS = frozenset({
    "copycat", "chain_reaction", "bonus_round",
    "double_down", "last_resort",
    "high_roller", "jackpot",
    "fortitude", "immaculate",
})

# Tradeoff effects that modify the overall bonus aggregation
_TRADEOFF_EFFECTS = frozenset({
    "double_down", "last_resort",
})


def _chanceRoll(ctx: CardCalcContext, userCardId: int, seedExtra: str = "") -> _random.Random:
    """Create a deterministic RNG seeded by user+season+week+card.

    Same card in same week always produces the same roll.
    """
    seedStr = f"{ctx.userId}-{ctx.season}-{ctx.weekNumber}-{userCardId}-{seedExtra}"
    seedHash = int(hashlib.sha256(seedStr.encode()).hexdigest(), 16) % (2**32)
    return _random.Random(seedHash)


def _computeCardPass(
    eq, ctx: CardCalcContext, firstPassBreakdowns: Optional[List[CardBreakdown]] = None,
) -> CardBreakdown:
    """Compute a single card's bonus and return its breakdown.

    If firstPassBreakdowns is provided, second-pass effects can reference it.
    """
    template = eq.user_card.card_template
    effectConfig = template.effect_config or {}
    cardPlayerId = template.player_id
    cardEdition = template.edition
    position = template.position

    effectName = effectConfig.get("effectName", "")
    displayName = effectConfig.get("displayName", "")
    detail = effectConfig.get("detail", "")
    category = effectConfig.get("category", "")

    # Set card position on context for roster-position lookups
    ctx.cardPosition = position

    # 1. Compute primary effect
    primary = computeEffect(effectConfig, ctx, cardPlayerId, eq.id,
                            firstPassBreakdowns=firstPassBreakdowns)

    # 2. Apply match bonus and weekly modifier
    isMatch = cardPlayerId in ctx.rosterPlayerIds
    mod = ctx.activeModifier

    # Wildcard modifier: force all cards to be matched
    if mod == "wildcard":
        isMatch = True

    preMatchFP = primary.fpBonus
    preMatchFloobits = primary.floobits
    preMatchMult = primary.multBonus
    matchedFP = primary.fpBonus
    matchedFloobits = primary.floobits
    matchedMult = primary.multBonus

    # Overdrive: match multiplier is 2.5x instead of 1.5x
    matchMult = 2.5 if mod == "overdrive" else DEFAULT_MATCH_MULTIPLIER

    if isMatch:
        matchedFP *= matchMult
        matchedFloobits = int(matchedFloobits * matchMult)
        # FPx match bonus: scale the bonus portion above 1
        if matchedMult > 1:
            bonusPortion = (matchedMult - 1) * matchMult
            matchedMult = 1 + bonusPortion

    # Apply modifier effects to primary values
    if mod in ("amplify", "cascade"):
        # Double FPx bonus portion
        if matchedMult > 1:
            matchedMult = 1 + (matchedMult - 1) * 2
    elif mod == "frenzy":
        matchedFP *= 2  # Double +FP
    elif mod == "grounded":
        matchedMult = 0  # Disable all mult effects
    elif mod == "payday":
        matchedFloobits *= 3  # Triple Floobits
    # 3. Check position conditional if matched
    conditionalBonus = 0.0
    conditionalLabel = None
    if isMatch:
        conditionals = POSITION_CONDITIONALS.get(position, [])
        cardPlayerStats = ctx.weekPlayerStats.get(cardPlayerId, {})
        for cond in conditionals:
            # Longshot modifier: halve conditional thresholds
            checkCond = cond
            if mod == "longshot" and cond:
                checkCond = dict(cond)
                checkCond["threshold"] = checkCond.get("threshold", 0) / 2
            bonus, label = _checkConditional(checkCond, cardPlayerStats)
            if bonus > 0:
                conditionalBonus += bonus
                conditionalLabel = label
                break  # Only apply the first triggered conditional

    # 4. Add secondary effects (static, from edition, no match bonus)
    secondary = EDITION_SECONDARY.get(cardEdition)
    if secondary is None and cardEdition == 'prismatic':
        # Prismatic generates random secondary at card creation — check effect_config
        secondary = effectConfig.get("secondary")
    secondaryFP = 0.0
    secondaryFloobits = 0
    secondaryMult = 0.0   # FPx factor from edition
    if secondary:
        secondaryFP = secondary.get("flatFP", 0)
        secondaryFloobits = secondary.get("floobits", 0)
        secondaryMult = secondary.get("mult", 0)
        # Grounded disables ALL multiplier effects, including edition bonuses
        if mod == "grounded":
            secondaryMult = 0.0

    # 5. Total up
    totalCardFP = matchedFP + conditionalBonus + secondaryFP
    totalCardFloobits = matchedFloobits + secondaryFloobits

    # Determine primary output type
    if primary.multBonus > 0:
        outputType = "mult"
    elif primary.floobits > 0:
        outputType = "floobits"
    else:
        outputType = "fp"
    # When primary result is all zeros, infer from config
    if outputType == "fp" and primary.fpBonus == 0:
        _MULT_KEYS = {"xMultValue", "fpShareScale", "baseXMult", "eloPer100", "perSwapXMult",
                       "perTdMult", "perPlayerMult", "perLossMult", "baseMult", "enhancedMult",
                       "multPercent", "perTdXMult", "perHundredYards"}
        _FLOOBITS_KEYS = {"floobits", "perTdFloobits", "fpPercent", "perMissFloobits",
                          "perPlayerFloobits", "perStreakFloobits", "enhancedFloobits",
                          "baseFloobits"}
        rewardType = effectConfig.get("rewardType")
        if rewardType in ("mult", "floobits"):
            outputType = rewardType
        elif any(k in effectConfig for k in _MULT_KEYS):
            outputType = "mult"
        elif category == "floobits" or any(k in effectConfig for k in _FLOOBITS_KEYS):
            outputType = "floobits"

    return CardBreakdown(
        slotNumber=eq.slot_number,
        edition=cardEdition,
        playerId=cardPlayerId,
        playerName=template.player_name,
        effectName=effectName,
        displayName=displayName,
        detail=detail,
        category=category,
        outputType=outputType,
        primaryFP=round(matchedFP, 2),
        primaryFloobits=matchedFloobits,
        primaryMult=round(matchedMult, 2),
        matchMultiplied=isMatch,
        matchMultiplier=matchMult,
        preMatchFP=round(preMatchFP, 2),
        preMatchFloobits=preMatchFloobits,
        preMatchMult=round(preMatchMult, 2),
        conditionalBonus=conditionalBonus,
        conditionalLabel=conditionalLabel,
        secondaryFP=secondaryFP,
        secondaryFloobits=secondaryFloobits,
        secondaryMult=secondaryMult,
        totalFP=round(totalCardFP, 2),
        floobitsEarned=totalCardFloobits,
        playerStatLine=_buildPlayerStatLine(effectName, cardPlayerId, ctx),
        equation=primary.equation,
        isChanceEffect=bool(effectConfig.get("isChanceEffect") or effectConfig.get("primary", {}).get("isChanceEffect")),
        chanceRoll=primary.chanceRoll,
        chanceThreshold=primary.chanceThreshold,
        chanceTriggered=primary.chanceTriggered,
    )


def calculateWeekCardBonuses(
    equippedCards,
    ctx: CardCalcContext,
) -> CardBonusResult:
    """Calculate card bonuses for one user's equipped cards for a week.

    Two-pass flow:
    Pass 1: Compute all non-second-pass effects
    Pass 2: Compute second-pass effects (trigger-chain, tradeoff) with first-pass results
    Then: Apply tradeoff modifications and aggregate totals

    Args:
        equippedCards: list of EquippedCard ORM objects (with user_card.card_template loaded)
        ctx: CardCalcContext with all necessary context for computation

    Returns:
        CardBonusResult with total bonus FP, mult bonus, Floobits earned, and per-card breakdowns
    """
    result = CardBonusResult()

    if not equippedCards:
        return result

    # Build hand composition fields on ctx before the card loop
    ctx.equippedCardPositions = []
    ctx.equippedCardOutputTypes = []
    ctx.equippedCardEffectNames = []
    for eq in equippedCards:
        template = eq.user_card.card_template
        ec = template.effect_config or {}
        ctx.equippedCardPositions.append(template.position)
        ctx.equippedCardOutputTypes.append(ec.get("outputType", "fp"))
        ctx.equippedCardEffectNames.append(ec.get("effectName", ""))

    # Pre-scan for chance card synergy + Providence amplifier
    chanceCardCount = 0
    for eq in equippedCards:
        ec = eq.user_card.card_template.effect_config or {}
        if ec.get("isChanceAmplifier"):
            chanceAmp = ec.get("primary", {}).get("chanceBonus", 0)
            ctx.chanceBonus += chanceAmp
        if ec.get("isChanceEffect"):
            chanceCardCount += 1
    ctx.chanceCardCount = chanceCardCount
    # Innate chance synergy: each chance card boosts all others by +0.04
    if chanceCardCount > 1:
        ctx.chanceBonus += (chanceCardCount - 1) * 0.04

    # Pre-scan for streak card synergy
    from managers.cardEffects import STREAK_CONFIGS
    streakCardCount = 0
    activeStreakCount = 0
    for eq in equippedCards:
        ec = eq.user_card.card_template.effect_config or {}
        effectName = ec.get("effectName", "")
        if effectName in STREAK_CONFIGS:
            streakCardCount += 1
            # Season streaks with non-zero count are "active"
            if not STREAK_CONFIGS[effectName].get("isWeekly", False):
                if ctx.streakCounts.get(eq.id, 0) > 0:
                    activeStreakCount += 1
            else:
                # Weekly streaks are always considered active
                activeStreakCount += 1
    ctx.streakCardCount = streakCardCount
    ctx.activeStreakCount = activeStreakCount

    # Separate first-pass and second-pass cards
    firstPassCards = []
    secondPassCards = []
    for eq in equippedCards:
        effectName = (eq.user_card.card_template.effect_config or {}).get("effectName", "")
        if effectName in _SECOND_PASS_EFFECTS:
            secondPassCards.append(eq)
        else:
            firstPassCards.append(eq)

    # First pass: compute non-second-pass cards
    firstPassBreakdowns = []
    for eq in firstPassCards:
        breakdown = _computeCardPass(eq, ctx)
        firstPassBreakdowns.append(breakdown)

    # Second pass: compute second-pass cards with first-pass results
    secondPassBreakdowns = []
    for eq in secondPassCards:
        breakdown = _computeCardPass(eq, ctx, firstPassBreakdowns=firstPassBreakdowns)
        secondPassBreakdowns.append(breakdown)

    allBreakdowns = firstPassBreakdowns + secondPassBreakdowns

    # Apply tradeoff effects that modify other cards' bonuses
    _applyTradeoffEffects(allBreakdowns)

    # Aggregate totals from all breakdowns
    for breakdown in allBreakdowns:
        result.totalBonusFP += breakdown.totalFP
        if breakdown.primaryMult > 1:
            result.multFactors.append(round(breakdown.primaryMult, 2))
        if breakdown.secondaryMult > 1:
            result.multFactors.append(round(breakdown.secondaryMult, 2))
        result.floobitsEarned += breakdown.floobitsEarned
        result.cardBreakdowns.append(breakdown)

    # Synergy modifier: +0.1 FPx per unique position among equipped cards
    if ctx.activeModifier == "synergy":
        uniquePositions = len(set(ctx.equippedCardPositions))
        if uniquePositions > 1:
            synergyMult = 1 + uniquePositions * 0.1
            result.multFactors.append(round(synergyMult, 2))

    result.totalBonusFP = round(result.totalBonusFP, 2)
    return result


def _applyTradeoffEffects(breakdowns: List[CardBreakdown]) -> None:
    """Mutate breakdowns in-place for tradeoff effects like Double Down and Feast or Famine."""
    tradeoffNames = {b.effectName for b in breakdowns if b.effectName in _TRADEOFF_EFFECTS}
    if not tradeoffNames:
        return

    # Collect non-tradeoff breakdowns (the ones tradeoffs operate on)
    normalBreakdowns = [b for b in breakdowns if b.effectName not in _TRADEOFF_EFFECTS]

    if "double_down" in tradeoffNames and normalBreakdowns:
        # Large FPx applied to lowest non-zero bonus, zeroes highest bonus
        nonZero = [b for b in normalBreakdowns if b.totalFP > 0 or b.floobitsEarned > 0]
        if len(nonZero) >= 2:
            # Sort by total FP (using FP as primary metric)
            sorted_ = sorted(nonZero, key=lambda b: b.totalFP)
            highest = sorted_[-1]
            # Zero out the highest card
            highest.primaryFP = 0
            highest.primaryFloobits = 0
            highest.primaryMult = 0
            highest.totalFP = highest.conditionalBonus + highest.secondaryFP
            highest.floobitsEarned = highest.secondaryFloobits
            highest.equation = f"zeroed by Double Down (was {highest.equation})"


