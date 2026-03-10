"""
Card Effect Calculator — computes weekly card bonuses for equipped cards.

Used by seasonManager._processWeekCardEffects() at week end for authoritative
persistence, and mirrored by fantasyTracker for live display.

Single-pass system: each card's named effect is computed via cardEffects.computeEffect(),
then match bonus and secondary effects are applied.
"""

import logging
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
    favoriteTeamSeasonLosses: int = 0
    favoriteTeamInPlayoffs: bool = False
    favoriteTeamWonThisWeek: bool = False
    favoriteTeamOpponentElo: float = 1500.0
    favoriteTeamBigPlays: int = 0
    favoriteTeamGameFinal: bool = False
    favoriteTeamSeasonUpsetWins: int = 0

    # Roster tracking
    rosterUnchangedWeeks: int = 0

    # Cross-team data
    leagueAverageElo: float = 1500.0
    teamResults: Dict[int, bool] = field(default_factory=dict)  # teamId → won
    playerPerformanceRatings: Dict[int, float] = field(default_factory=dict)

    # Weekly modifier
    activeModifier: str = ""  # e.g. "amplify", "grounded", ""

    # Swap data (for Stockpiler effect)
    unusedSwaps: int = 0

    # Internal — set by computeEffect dispatcher, not by caller
    _currentEffectName: str = ""


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
    outputType: str = "fp"  # "fp", "mult", "xmult", "floobits"

    # Primary effect
    primaryFP: float = 0.0
    primaryFloobits: int = 0
    primaryMult: float = 0.0   # +FPx value
    primaryXMult: float = 0.0  # xFPx value (>1 when active)

    # Match bonus
    matchMultiplied: bool = False
    matchMultiplier: float = DEFAULT_MATCH_MULTIPLIER
    preMatchFP: float = 0.0
    preMatchFloobits: int = 0
    preMatchMult: float = 0.0
    preMatchXMult: float = 0.0

    # Position conditional
    conditionalBonus: float = 0.0
    conditionalLabel: Optional[str] = None

    # Secondary effect (from edition)
    secondaryFP: float = 0.0
    secondaryFloobits: int = 0
    secondaryMult: float = 0.0   # +FPx from edition (e.g. holo)
    secondaryXMult: float = 0.0  # xFPx from edition (e.g. prismatic)

    # Totals
    totalFP: float = 0.0
    floobitsEarned: int = 0

    # Card player stat line (for card-player-specific effects)
    playerStatLine: str = ""

    # Human-readable equation showing how primary output was derived
    equation: str = ""


@dataclass
class CardBonusResult:
    totalBonusFP: float = 0.0
    totalMultBonus: float = 0.0    # Sum of +FPx values
    xMultFactors: List[float] = field(default_factory=list)  # Individual xFPx values (>1)
    floobitsEarned: int = 0
    cardBreakdowns: List[CardBreakdown] = field(default_factory=list)


# Effects that use the card player's individual stats
_CARD_PLAYER_EFFECTS = {
    "main_character", "hype_man", "cha_ching", "ace_up_the_sleeve",
    "showoff", "glow_up", "spotlight_moment", "schadenfreude", "hot_hand",
}


def _buildPlayerStatLine(effectName: str, cardPlayerId: int, ctx) -> str:
    """Build a short stat summary for card-player-specific effects."""
    if effectName not in _CARD_PLAYER_EFFECTS:
        return ""

    stats = ctx.weekPlayerStats.get(cardPlayerId, {})
    if not stats:
        return ""

    fp = stats.get("fantasyPoints", 0)
    passing = stats.get("passing_stats", {})
    rushing = stats.get("rushing_stats", {})
    receiving = stats.get("receiving_stats", {})
    kicking = stats.get("kicking_stats", {})

    # Count TDs across all stat groups
    tds = (passing.get("tds", 0)
           + rushing.get("runTds", 0)
           + receiving.get("rcvTds", 0))

    # Build position-appropriate stat line
    parts = []
    if fp:
        parts.append(f"{int(fp)} FP")
    if tds:
        parts.append(f"{tds} TD")
    if passing.get("passYards", 0):
        parts.append(f"{passing['passYards']} pass yds")
    if rushing.get("runYards", 0):
        parts.append(f"{rushing['runYards']} rush yds")
    if receiving.get("rcvYards", 0):
        parts.append(f"{receiving['rcvYards']} rec yds")
    if kicking.get("fgs", 0):
        parts.append(f"{kicking['fgs']} FG")

    return ", ".join(parts)


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


def calculateWeekCardBonuses(
    equippedCards,
    ctx: CardCalcContext,
) -> CardBonusResult:
    """Calculate card bonuses for one user's equipped cards for a week.

    Single-pass flow:
    1. Compute primary effect via cardEffects.computeEffect()
    2. Apply match bonus (1.5x) to primary FP and floobits only
    3. For multiplier effects: accumulate mult bonus
    4. Add secondary effects (static, from edition, no match bonus)
    5. Check position conditional if matched
    6. Build breakdown, sum totals

    Args:
        equippedCards: list of EquippedCard ORM objects (with user_card.card_template loaded)
        ctx: CardCalcContext with all necessary context for computation

    Returns:
        CardBonusResult with total bonus FP, mult bonus, Floobits earned, and per-card breakdowns
    """
    result = CardBonusResult()

    if not equippedCards:
        return result

    for eq in equippedCards:
        template = eq.user_card.card_template
        effectConfig = template.effect_config or {}
        cardPlayerId = template.player_id
        cardEdition = template.edition
        position = template.position

        effectName = effectConfig.get("effectName", "")
        displayName = effectConfig.get("displayName", "")
        detail = effectConfig.get("detail", "")
        category = effectConfig.get("category", "")

        # 1. Compute primary effect
        primary = computeEffect(effectConfig, ctx, cardPlayerId, eq.id)

        # 2. Apply match bonus and weekly modifier
        isMatch = cardPlayerId in ctx.rosterPlayerIds
        mod = ctx.activeModifier

        # Wildcard modifier: force all cards to be matched
        if mod == "wildcard":
            isMatch = True

        preMatchFP = primary.fpBonus
        preMatchFloobits = primary.floobits
        preMatchMult = primary.multBonus
        preMatchXMult = primary.xMultBonus
        matchedFP = primary.fpBonus
        matchedFloobits = primary.floobits
        matchedMult = primary.multBonus
        matchedXMult = primary.xMultBonus

        # Overdrive: match multiplier is 2.5x instead of 1.5x
        matchMult = 2.5 if mod == "overdrive" else DEFAULT_MATCH_MULTIPLIER

        if isMatch:
            matchedFP *= matchMult
            matchedFloobits = int(matchedFloobits * matchMult)
            matchedMult *= matchMult
            # xFPx match bonus: scale the bonus portion above 1
            if matchedXMult > 0:
                bonusPortion = (matchedXMult - 1) * matchMult
                matchedXMult = 1 + bonusPortion

        # Apply modifier effects to primary values
        if mod == "amplify":
            matchedMult *= 2  # Double +FPx
        elif mod == "cascade":
            # Double xFPx bonus portion
            if matchedXMult > 1:
                matchedXMult = 1 + (matchedXMult - 1) * 2
        elif mod == "frenzy":
            matchedFP *= 2  # Double +FP
        elif mod == "grounded":
            matchedMult = 0  # Disable all mult effects
            matchedXMult = 0
        elif mod == "payday":
            matchedFloobits *= 3  # Triple Floobits
        elif mod == "spotlight":
            if effectName in _CARD_PLAYER_EFFECTS:
                matchedFP *= 1.5  # +50% FP for card-player-specific effects

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
        if secondary is None and cardEdition == 'diamond':
            # Diamond generates random secondary at equip time — check effect_config
            secondary = effectConfig.get("secondary")
        secondaryFP = 0.0
        secondaryFloobits = 0
        secondaryMult = 0.0   # +FPx from edition
        secondaryXMult = 0.0  # xFPx from edition
        if secondary:
            secondaryFP = secondary.get("flatFP", 0)
            secondaryFloobits = secondary.get("floobits", 0)
            secondaryMult = secondary.get("mult", 0)
            secondaryXMult = secondary.get("xMult", 0)
            # Grounded disables ALL multiplier effects, including edition bonuses
            if mod == "grounded":
                secondaryMult = 0.0
                secondaryXMult = 0.0

        # 5. Total up
        totalCardFP = matchedFP + conditionalBonus + secondaryFP
        totalCardFloobits = matchedFloobits + secondaryFloobits

        # Determine primary output type
        if primary.xMultBonus > 0:
            outputType = "xmult"
        elif primary.multBonus > 0:
            outputType = "mult"
        elif primary.floobits > 0:
            outputType = "floobits"
        else:
            outputType = "fp"
        # When primary result is all zeros, infer from config
        if outputType == "fp" and primary.fpBonus == 0:
            _XMULT_KEYS = {"xMultValue", "fpShareScale", "baseXMult", "eloPer100", "perSwapXMult"}
            _MULT_KEYS = {"perTdMult", "perPlayerMult", "perLossMult", "baseMult", "multPercent"}
            _FLOOBITS_KEYS = {"floobits", "perTdFloobits", "fpPercent", "perMissFloobits",
                              "perPlayerFloobits", "perStreakFloobits"}
            rewardType = effectConfig.get("rewardType")
            if rewardType in ("xmult", "mult", "floobits"):
                outputType = rewardType
            elif any(k in effectConfig for k in _XMULT_KEYS):
                outputType = "xmult"
            elif any(k in effectConfig for k in _MULT_KEYS):
                outputType = "mult"
            elif category == "floobits" or any(k in effectConfig for k in _FLOOBITS_KEYS):
                outputType = "floobits"

        # Build breakdown
        breakdown = CardBreakdown(
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
            primaryMult=round(matchedMult, 1),
            primaryXMult=round(matchedXMult, 1),
            matchMultiplied=isMatch,
            matchMultiplier=matchMult,
            preMatchFP=round(preMatchFP, 2),
            preMatchFloobits=preMatchFloobits,
            preMatchMult=round(preMatchMult, 1),
            preMatchXMult=round(preMatchXMult, 1),
            conditionalBonus=conditionalBonus,
            conditionalLabel=conditionalLabel,
            secondaryFP=secondaryFP,
            secondaryFloobits=secondaryFloobits,
            secondaryMult=secondaryMult,
            secondaryXMult=secondaryXMult,
            totalFP=round(totalCardFP, 2),
            floobitsEarned=totalCardFloobits,
            playerStatLine=_buildPlayerStatLine(effectName, cardPlayerId, ctx),
            equation=primary.equation,
        )

        result.totalBonusFP += totalCardFP
        result.totalMultBonus += matchedMult + secondaryMult  # Primary +FPx + edition +FPx
        if matchedXMult > 1:
            result.xMultFactors.append(round(matchedXMult, 1))
        if secondaryXMult > 1:
            result.xMultFactors.append(round(secondaryXMult, 1))
        result.floobitsEarned += totalCardFloobits
        result.cardBreakdowns.append(breakdown)

    result.totalBonusFP = round(result.totalBonusFP, 2)
    result.totalMultBonus = round(result.totalMultBonus, 1)
    return result
