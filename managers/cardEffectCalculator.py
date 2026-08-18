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
import re as _re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

from managers.cardEffects import (
    computeEffect, checkStreakCondition, EffectResult,
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


@dataclass
class CardCalcContext:
    """Full context needed to compute card bonuses for one user for one week."""
    # Core roster data
    rosterPlayerIds: Set[int] = field(default_factory=set)
    weekPlayerStats: Dict[int, dict] = field(default_factory=dict)
    # Projection only: each depicted player's per-week FP history this season, so the
    # expected-value projection can weight a gated card by P(player clears the bar) instead
    # of hard-gating on the season average. Empty in the live/week-end paths.
    playerWeeklyFP: Dict[int, list] = field(default_factory=dict)
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
    favoriteTeamPeakStreak: int = 0  # Longest win or loss streak this season (abs value)
    favoriteTeamSeasonLosses: int = 0
    favoriteTeamSeasonWins: int = 0
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

    # League-state lookups for roster-trait cards
    # Comeback Kid: team_ids that missed playoffs last season
    priorSeasonMissedPlayoffTeamIds: Set[int] = field(default_factory=set)
    # Domination: team_ids currently in top-6 league standings
    currentTop6TeamIds: Set[int] = field(default_factory=set)

    # Equipped hand composition (for card-to-card effects)
    equippedCardPositions: List[int] = field(default_factory=list)
    equippedCardOutputTypes: List[str] = field(default_factory=list)
    equippedCardEffectNames: List[str] = field(default_factory=list)

    # Weekly modifier
    activeModifier: str = ""  # e.g. "amplify", "grounded", ""

    # Swap data (for Stockpiler / swap-based effects)
    unusedSwaps: int = 0
    seasonSwapsUsed: int = 0
    # True when the user currently has a 7th roster slot (FLEX) available —
    # either from an equipped Champion-classified card or an active
    # temp_flex powerup. Used by Home Alone so an empty FLEX slot counts
    # as a vacancy.
    hasFlexSlot: bool = False

    # Economy data (for balance-based effects)
    userFloobitsBalance: int = 0

    # Chance card infrastructure
    userId: int = 0
    season: int = 0
    weekNumber: int = 0
    gamesActive: bool = False  # True during live games, False at week end
    chanceBonus: float = 0.0  # Sum of Providence + Catalyst + innate synergy + Fortunate modifier
    chanceCardCount: int = 0  # Number of chance cards in hand (for synergy effects)
    hasAdvantage: bool = False  # Advantage card present
    advantageRolls: int = 2     # Advantage rolls N times (tier+1), keeps the best
    kickerSeasonFgMisses: int = 0  # Season-long kicker FG misses (for Good Neighbor)

    # Streak card infrastructure
    streakCardCount: int = 0  # Number of streak cards in hand (for synergy effects)
    activeStreakCount: int = 0  # Number of season streak cards whose condition is met this week
    liveStreakConditionsMet: Dict[int, bool] = field(default_factory=dict)  # eqId → conditionMet this game
    # Peak-decay state for streak cards. peakOutput is the in-streak output of
    # the card the last week the streak was active; weeksSinceBreak counts cold
    # weeks since then. Together they let _computeStreakEffect compute a decay
    # tail when the streak isn't met this week, instead of dropping straight
    # to base. Loaded from EquippedCard.peak_output / weeks_since_break;
    # persistence updates both after each week's calc.
    streakPeakOutputs: Dict[int, float] = field(default_factory=dict)  # eqId → peakOutput
    streakWeeksSinceBreak: Dict[int, int] = field(default_factory=dict)  # eqId → cold weeks since break

    # Roster-trait card lookups (FP/FPx rebalance)
    # _teamRecords: teamId → win pct (0.0-1.0). Used by Castaway to detect
    # sub-.500 team players on the roster.
    _teamRecords: Dict[int, float] = field(default_factory=dict)
    # _rosterRookieFlags: playerId → True if rookie. Used by Rookie Hype.
    _rosterRookieFlags: Dict[int, bool] = field(default_factory=dict)
    # _rosterSeasonsPlayed: playerId → int. Used by Vanguard (5+ veterans).
    _rosterSeasonsPlayed: Dict[int, int] = field(default_factory=dict)
    # Snapshot of player IDs the user committed to on their first roster save.
    # Used by Loyalty (rewards keeping originals).
    initialRosterPlayerIds: Set[int] = field(default_factory=set)

    # Pick-em stats for the displayed week. Used by Conviction (streak on
    # manual submit), Augur (accuracy bonus), Tipster (FPx scaling with
    # weekly points).
    userManualPickSubmittedThisWeek: bool = False
    userWeeklyPickemCorrect: int = 0
    userWeeklyPickemTotal: int = 0
    userWeeklyPickemPoints: int = 0

    # Eminence: per-position league avg FP/game and per-player season FP/game
    positionAvgFPs: Dict[int, float] = field(default_factory=dict)  # pos → avg FP/game
    top10PerPosition: Dict[int, Set[int]] = field(default_factory=dict)  # pos → set of top-10 player IDs by season FP/game
    top1PerPosition: Dict[int, Set[int]] = field(default_factory=dict)   # pos → set with the #1 player at that position
    playerSeasonFPPerGame: Dict[int, float] = field(default_factory=dict)  # playerId → FP/game

    # Projection mode — when True, the calc is running against expected values
    # (season averages, ELO forecasts) instead of live game outcomes. Chance
    # cards resolve to expected value (trigger prob × reward) rather than a
    # coin-flip, and outcome-dependent booleans are filled with most-likely
    # values. favoriteTeamWinProb is set alongside it for chance weighting.
    isProjection: bool = False
    favoriteTeamWinProb: float = 0.5
    # Which projection variant is this run building:
    #   'expected'   — most-likely path, chance cards scaled by threshold
    #   'optimistic' — all triggers fire, chance cards return enhanced values
    #                  without threshold scaling. Used to compute the "if it
    #                  hits" upside for the odds display.
    projectionVariant: str = 'expected'
    # Flipped for one extra pass over a chance card, to read what it pays when the roll
    # MISSES — its guaranteed floor. The expected value interpolates from there rather
    # than scaling the triggered payout down through it. See _ProjectionMissRNG.
    projectionForceMiss: bool = False

    # Internal — set by computeEffect dispatcher, not by caller
    _currentEffectName: str = ""
    _firstPassBreakdowns: Optional[List] = None  # Set for second-pass effects
    # Map of eq.id → bool: would this second-pass card produce non-zero output
    # given only first-pass results? Used by trigger-chain effects (Chain
    # Reaction, Bonus Round, Last Resort) to count other second-pass cards
    # without circularity — the boolean is determined from first-pass data so
    # CR-A counting CR-B (and vice-versa) resolves cleanly.
    _secondPassPreTriggers: Dict[int, bool] = field(default_factory=dict)
    # Set during the convergence pass so effects (Copycat, High Roller) can
    # scan other second-pass cards' actual breakdowns. Index-aligned with
    # _secondPassEqIds.
    _secondPassBreakdowns: Optional[List] = None
    _secondPassEqIds: Optional[List[int]] = None


@dataclass
class CardBreakdown:
    """Per-card breakdown for display and persistence."""
    slotNumber: int = 0
    edition: str = ""
    tier: int = 1            # Upgrade tier (1-4 / I-IV); display as "Showoff III"
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

    # Match bonus — RETIRED in the fantasy/cards fusion (every equipped card's
    # player is trivially rostered, so the ×1.5/×2.5 multiplier was flat
    # inflation). Fields kept for breakdowns_json / recap schema stability;
    # matchMultiplied is always False and matchMultiplier always 1.0 now.
    matchMultiplied: bool = False
    matchMultiplier: float = 1.0
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

    # Streak card metadata
    streakActive: Optional[bool] = None  # None = not a streak card, True/False = condition met this week
    streakCount: int = 0  # Current streak count

    # FP power-bar gate: None = ungated (no-effect floor card), True = the depicted
    # player cleared the bar this week (effect fired), False = bar not met (effect
    # scored nothing). Drives the "gate not met" marker in the scoring breakdown.
    gateActive: Optional[bool] = None
    gateThreshold: float = 0.0  # the position FP threshold this card's bar needs
    gateInverse: bool = False   # inverse gate — the effect is active WHILE under the threshold
    gateAllPro: bool = False    # All-Pro card: its bar is lowered 30% (CARD_GATE_ALLPRO_MULT)

    # ── Glitch (docs/GLITCH_CARDS.md) ──
    # `glitched` marks the card; the rest describe THIS week's roll. `glitchOutcome` is the
    # surge name and stays hidden from the user unless the on-card player is awakened —
    # the score line renders it as corrupted characters otherwise.
    glitched: bool = False
    glitchChance: float = 0.0        # this week's trigger odds, for the in-week scramble intensity
    glitchTriggered: bool = False
    glitchOutcome: Optional[str] = None
    glitchFp: float = 0.0            # extra FP the surge added (additive, never replacing)
    glitchMultDelta: float = 0.0     # extra FPx delta the surge added
    glitchReadable: bool = False     # True only when the player is awakened
    # Which owned card the glitch sits on, so the week-end bank can spend a trigger
    # against it. Set only when the card is glitched; the breakdown otherwise carries no
    # equipped-card id at all and callers key on (slot, player), which is unique within a
    # lineup but useless for finding the row to update.
    glitchUserCardId: Optional[int] = None


@dataclass
class CardBonusResult:
    totalBonusFP: float = 0.0
    multFactors: List[float] = field(default_factory=list)  # All FPx factors (each >1)
    floobitsEarned: int = 0
    cardBreakdowns: List[CardBreakdown] = field(default_factory=list)
    # Team stacking: the size of the largest same-team group fielded, how many of those are
    # Champion-classified (which amplifies the stack), and the lineup-wide FPx delta granted
    # (0 below a 2-stack). For the hand-synergy display.
    stackSize: int = 0
    stackChampions: int = 0
    stackBonus: float = 0.0
    # The portion of stackBonus contributed by the Synergy weekly modifier's amplification
    # (0 when Synergy isn't active). Excluded from the card-stacking achievement so a "free"
    # modifier boost doesn't inflate it.
    stackModifierBonus: float = 0.0


# Effects that use the roster player's stats at the card's position
_ROSTER_POSITION_EFFECTS = {
    "luminary", "squire", "cha_ching", "ace_up_the_sleeve",
    "showoff", "spotlight_moment",
    # New position-based effects
    "gunslinger", "air_raid", "workhorse", "goal_line_vulture",
    "possession", "trebuchet", "double_trouble",
    "safety_blanket", "mismatch", "sniper",
    "spectacle", "indemnity",
}


# Effects still scored against the roster slot rather than the card's own
# player, so their stat line must keep the old position lookup or it would
# advertise stats the card didn't actually score on. Everything else in
# _ROSTER_POSITION_EFFECTS was re-based in Stage 1 of the on-card re-base
# (docs/CARD_ONCARD_REBASE_PLAN.md) and reads the card player directly.
_ROSTER_SCOPED_STAT_LINE = {"showoff", "double_trouble", "sniper"}


def _buildPlayerStatLine(effectName: str, cardPlayerId: int, ctx) -> str:
    """Build a short stat summary for position-based effects.

    Re-based effects report the CARD'S OWN player. The few still roster-scoped
    (see _ROSTER_SCOPED_STAT_LINE) keep the old lookup of whoever occupies the
    card's position, combining WR1+WR2 for pos 3.
    """
    # Stat-ladder cards report THE STAT THEY READ, not a generic summary. A card paying
    # on YAC showing "3 rec · 32 yd · 0 TD" hides the only number that explains the
    # payout, which makes a working card look broken.
    try:
        from managers.cardEffects import ladderStatLine
        line = ladderStatLine(effectName, (ctx.weekPlayerStats or {}).get(cardPlayerId, {}))
        if line:
            return line
    except Exception:
        pass

    if effectName not in _ROSTER_POSITION_EFFECTS:
        return ""

    if effectName in _ROSTER_SCOPED_STAT_LINE:
        rosterPids = [
            pid for pid, pos in ctx.rosterPlayerPositions.items()
            if pos == ctx.cardPosition and pid in ctx.rosterPlayerIds
        ]
    else:
        rosterPids = [cardPlayerId] if cardPlayerId else []
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
    "high_roller",
    "fortitude",
    "charmed",  # FP per chance card trigger this week
    # Full House (Diamond): fires only if EVERY first-pass card cleared its power
    # bar this week, so it must run after every first-pass gate is resolved. It
    # reads the snapshot taken right after the first pass (ctx._firstPassGatedCount
    # / _firstPassGatedOn), not per-card breakdowns.
    "full_roster",
})

# Tradeoff effects that modify the overall bonus aggregation
_TRADEOFF_EFFECTS = frozenset({
    "double_down", "last_resort",
})

# Pure marker / structural cards: they produce no FP of their own — they only
# amplify or modify OTHER cards. They must never accrue a position-conditional
# match bonus (which would fabricate a phantom FP row), and Lemons / Conductor
# must never select or amplify them.
_NO_OUTPUT_MARKERS = frozenset({
    "doubler", "surveyor", "sharpshooter", "conductor", "double_down",
})


def _wouldSecondPassTrigger(eq, firstPassBreakdowns: List, ctx) -> bool:
    """Heuristic: would this second-pass card produce non-zero output given
    only first-pass results? Used to let trigger-chain effects count each
    other without circularity. The actual-trigger correction happens later
    in the convergence pass.
    """
    template = eq.user_card.card_template
    ec = template.effect_config or {}
    effectName = ec.get("effectName", "")
    primary = ec.get("primary", {}) or {}
    fpTriggered = sum(1 for b in firstPassBreakdowns
                      if b.totalFP > 0 or b.floobitsEarned > 0 or b.primaryMult > 0)
    if effectName == "chain_reaction":
        return fpTriggered > 0
    if effectName == "bonus_round":
        return fpTriggered >= 4
    if effectName == "last_resort":
        # Modern config (baseFP) always pays out → triggered.
        # Legacy config (rewardValue only) fires only when nothing else
        # triggered → inverse condition.
        if "baseFP" in primary:
            return True
        if "rewardValue" in primary and "baseFP" not in primary:
            return fpTriggered == 0
        return True
    if effectName == "copycat":
        return any(b.totalFP > 0 for b in firstPassBreakdowns)
    if effectName == "double_down":
        return any(b.totalFP > 0 and b.effectName != "double_down" for b in firstPassBreakdowns)
    if effectName == "high_roller":
        return any(b.chanceTriggered for b in firstPassBreakdowns)
    if effectName == "charmed":
        return any(b.chanceTriggered for b in firstPassBreakdowns)
    if effectName == "fortitude":
        # Heat Check fires whenever there's at least one active streak card.
        return getattr(ctx, 'activeStreakCount', 0) > 0
    return False


def computeEminenceData(session, season: int, currentWeek: int) -> tuple:
    """Compute per-position league avg FP/game, per-player FP/game, top-10
    set per position (Eminence), and top-1 set per position (Cornerstone).

    Returns (positionAvgFPs, playerSeasonFPPerGame, top10PerPosition, top1PerPosition):
        positionAvgFPs:        {pos(1-5) → float}
        playerSeasonFPPerGame: {playerId → float}
        top10PerPosition:      {pos(1-5) → Set[playerId]}
        top1PerPosition:       {pos(1-5) → Set[playerId]}  (1 player per position)

    Only uses completed games (final status) from weeks prior to currentWeek.
    Player.position is 1-based (QB=1, RB=2, WR=3, TE=4, K=5).
    """
    from database.models import GamePlayerStats as GPSModel, Game, Player
    from collections import defaultdict

    if currentWeek < 3:
        return {}, {}, {}, {}

    # Get all player stats from completed games this season (prior weeks)
    rows = (
        session.query(GPSModel.player_id, GPSModel.fantasy_points, Player.position)
        .join(Game, GPSModel.game_id == Game.id)
        .join(Player, GPSModel.player_id == Player.id)
        .filter(Game.season == season, Game.week < currentWeek, Game.status == 'final')
        .all()
    )

    # Accumulate per-player and per-position
    playerTotals = defaultdict(lambda: [0.0, 0])  # playerId → [totalFP, gameCount]
    posTotals = defaultdict(lambda: [0.0, 0])  # pos(1-based) → [totalFP, playerGames]
    playerPositions: Dict[int, int] = {}
    for playerId, fp, pos in rows:
        # Player.position is 1-based (QB=1, RB=2, WR=3, TE=4, K=5)
        playerTotals[playerId][0] += (fp or 0)
        playerTotals[playerId][1] += 1
        if pos:
            playerPositions[playerId] = pos
            posTotals[pos][0] += (fp or 0)
            posTotals[pos][1] += 1

    playerSeasonFPPerGame = {
        pid: round(total / count, 2)
        for pid, (total, count) in playerTotals.items() if count > 0
    }
    positionAvgFPs = {
        pos: round(total / count, 2)
        for pos, (total, count) in posTotals.items() if count > 0
    }

    # Top-10 + top-1 player IDs per position by season FP/game
    byPosition: Dict[int, list] = defaultdict(list)
    for pid, fpPerGame in playerSeasonFPPerGame.items():
        pos = playerPositions.get(pid)
        if pos:
            byPosition[pos].append((pid, fpPerGame))
    top10PerPosition: Dict[int, Set[int]] = {}
    top1PerPosition: Dict[int, Set[int]] = {}
    for pos, players in byPosition.items():
        players.sort(key=lambda x: x[1], reverse=True)
        top10PerPosition[pos] = {pid for pid, _ in players[:10]}
        top1PerPosition[pos] = {pid for pid, _ in players[:1]}

    return positionAvgFPs, playerSeasonFPPerGame, top10PerPosition, top1PerPosition


class _AdvantageRNG:
    """Wraps an RNG so .random() returns the best of N rolls (lower = better for
    chance cards). N = Advantage's roll count, which scales with its tier."""
    def __init__(self, rng: _random.Random, rolls: int = 2):
        self._rng = rng
        self._rolls = max(2, int(rolls))

    def random(self) -> float:
        return min(self._rng.random() for _ in range(self._rolls))


class _ProjectionRNG:
    """Deterministic RNG used when building a payout projection.

    Always returns 0.0 so every chance-card trigger path evaluates as
    'triggered'. The calculator then interpolates between this and the
    missed outcome in _computeCardPass, producing an expected-value
    estimate without the effect functions needing to branch on
    projection mode themselves.
    """
    def random(self) -> float:
        return 0.0


class _ProjectionMissRNG:
    """The other half of the projection: every chance path evaluates as MISSED.

    ⚠️ A CHANCE CARD'S MISS IS NOT ZERO. Most of them pay a guaranteed floor and roll
    for an enhanced payout on top — `fp = enhancedFP if triggered else baseFP` — so
    scaling the triggered value by the odds projected BELOW the floor the card always
    pays. Reported from production: a card guaranteeing a base projecting under it.
    With base 5 / enhanced 18 at 25%, the old pass showed 4.5 against a floor of 5;
    the honest estimate is 5 + (18 - 5) x 0.25 = 8.25.

    Asking the effect what it pays on a miss beats teaching twelve compute functions
    to declare a floor: the answer comes from the same code that pays it, so an effect
    with no floor still yields 0 and projects exactly as before. Safe to run twice —
    no chance compute mutates the context.
    """
    def random(self) -> float:
        return 1.0


def _chanceRoll(ctx: CardCalcContext, userCardId: int, seedExtra: str = "") -> _random.Random:
    """Create a deterministic RNG seeded by user+season+week+card.

    Same card in same week always produces the same roll.
    When Advantage is active, returns a wrapper that rolls twice and takes the better result.
    In projection mode, returns a zero-roll RNG so chance cards always
    take the triggered path — the caller scales by the threshold to
    produce expected value.
    """
    if getattr(ctx, 'isProjection', False):
        return _ProjectionMissRNG() if getattr(ctx, 'projectionForceMiss', False) else _ProjectionRNG()
    seedStr = f"{ctx.userId}-{ctx.season}-{ctx.weekNumber}-{userCardId}-{seedExtra}"
    seedHash = int(hashlib.sha256(seedStr.encode()).hexdigest(), 16) % (2**32)
    rng = _random.Random(seedHash)
    if getattr(ctx, 'hasAdvantage', False):
        return _AdvantageRNG(rng, getattr(ctx, 'advantageRolls', 2))
    return rng


# An output value in an equation is a number that's either a decimal (rates,
# deltas, maxes, FP amounts) or an integer immediately followed by an output unit
# (FP / FPx / Floobits / F). Plain integers like counts ("× 3 overperforming")
# and percentages ("85%") are NOT output values and must not scale with tier.
_EQ_OUTPUT_UNIT = _re.compile(r'^\s*(FPx|FP|Floobits|F)\b')
_EQ_NUMBER = _re.compile(r'(?<![\d.])\d+(?:\.\d+)?(?![\d])')


def _rescaleEquationValue(equation, tierMult):
    """Scale every OUTPUT value in an equation string by tierMult so an upgraded
    card's equation reads with its real tier values throughout (e.g. Rising Tide
    "+0.06/player × 3 = +0.18 FPx (max +0.35)" → "+0.09/player × 3 = +0.27 FPx
    (max +0.52)"). Counts and percentages are left untouched."""
    if not equation or tierMult == 1.0:
        return equation

    def _repl(mt):
        numStr = mt.group(0)
        after = equation[mt.end():mt.end() + 12]
        isDecimal = '.' in numStr
        if after[:1] == '%':                       # percentage / accuracy — context
            return numStr
        if _EQ_OUTPUT_UNIT.match(after):           # number + FP/FPx/Floobits/F → output
            scale = True
        elif not isDecimal:                        # bare integer (a count) → leave
            scale = False
        else:
            # Decimal: an output value (rate/delta/max) unless it's followed by a
            # plain word (e.g. "150.0 yards", "3.5 players") which is context.
            stripped = after.lstrip()
            scale = not (stripped[:1].isalpha())
        if not scale:
            return numStr
        scaled = float(numStr) * tierMult
        if isDecimal:
            decimals = len(numStr.split('.')[1])
            return f"{scaled:.{decimals}f}"
        return str(int(round(scaled)))

    return _EQ_NUMBER.sub(_repl, equation)


def _computeMissedOutcome(effectConfig, ctx, cardPlayerId, eqId, firstPassBreakdowns):
    """What this chance effect pays when the roll MISSES — its guaranteed floor.

    Runs the same compute a second time with the RNG forced to miss. Cheap (projection
    only, chance cards only) and side-effect free: no chance compute mutates the context.
    Returns None if anything goes wrong, which puts the floor at zero — the old
    behavior, so a bad answer here can never inflate a projection.
    """
    forceMissWas = getattr(ctx, 'projectionForceMiss', False)
    try:
        ctx.projectionForceMiss = True
        return computeEffect(effectConfig, ctx, cardPlayerId, eqId,
                             firstPassBreakdowns=firstPassBreakdowns)
    except Exception:
        logger.debug("projection: missed-outcome pass failed for %s",
                     effectConfig.get('effectName'), exc_info=True)
        return None
    finally:
        ctx.projectionForceMiss = forceMissWas


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
    # ⚠️ THE LIVE MAP WINS OVER THE STORED CATEGORY. The category is written into
    # effect_config at mint, and reading it back meant a RE-CATEGORISATION only reached
    # cards minted after it — so five effects that stopped being conditional would have
    # kept collecting the `longshot` doubling all season on 23 already-minted templates.
    # Same rule the detail and tooltip already follow (rebuilt from the current templates
    # rather than migrated), and it needs no migration for the next one either. The
    # stored value survives only for an effect this map has never heard of.
    from managers.cardEffects import EFFECT_CATEGORY as _LIVE_CATEGORY
    category = _LIVE_CATEGORY.get(effectName) or effectConfig.get("category", "")

    # Rebuild stale primary params — test stored primary against current template
    # to detect missing keys, regardless of whether detail was already patched.
    if effectName:
        import re as _re
        from managers.cardEffects import (
            rebuildPrimaryParams, EFFECT_DETAIL_TEMPLATES, STAT_DISPLAY_NAMES,
            POSITION_LABELS,
        )
        storedPrimary = effectConfig.get("primary", {})
        detailTpl = EFFECT_DETAIL_TEMPLATES.get(effectName, "")
        if detailTpl:
            testDetail = detailTpl
            for key, val in storedPrimary.items():
                testDetail = testDetail.replace("{" + key + "}", str(val))
            statKey = storedPrimary.get("stat", "")
            if statKey:
                testDetail = testDetail.replace("{statDisplay}", STAT_DISPLAY_NAMES.get(statKey, statKey))
            if _re.search(r'\{[a-zA-Z_]+\}', testDetail):
                # Stored primary is missing keys — rebuild from current builder
                edScale = effectConfig.get("editionScale", 1.0)
                freshPrimary = rebuildPrimaryParams(effectName, template.player_rating, edScale)
                freshPrimary["posLabel"] = storedPrimary.get(
                    "posLabel", POSITION_LABELS.get(position, "??"))
                effectConfig["primary"] = freshPrimary
                # Rebuild detail with fresh params
                detail = detailTpl
                for key, val in freshPrimary.items():
                    detail = detail.replace("{" + key + "}", str(val))
                if statKey:
                    detail = detail.replace("{statDisplay}", STAT_DISPLAY_NAMES.get(statKey, statKey))
                detail = _re.sub(r'\{[a-zA-Z_]+\}', '?', detail)

    # Set card position on context for roster-position lookups
    ctx.cardPosition = position

    # 1. Compute primary effect
    primary = computeEffect(effectConfig, ctx, cardPlayerId, eq.id,
                            firstPassBreakdowns=firstPassBreakdowns)

    # Projection mode: if this was a chance effect, the _ProjectionRNG forced
    # it onto the 'triggered' path. For the 'expected' variant, scale the
    # output by the trigger probability to get an expected-value estimate
    # the UI can show as a single number. For 'optimistic' variant, leave
    # the enhanced value as-is so the UI can show the "if it hits" upside.
    if (getattr(ctx, 'isProjection', False)
            and getattr(ctx, 'projectionVariant', 'expected') == 'expected'
            and primary.chanceThreshold > 0
            and not getattr(primary, 'chanceMetaGrowth', False)):
        # chanceMetaGrowth (Bonsai): fpBonus is the guaranteed base and the odds gate
        # future growth, so the projected value is the base as-is, not base × odds.
        #
        # ⚠️ EXPECTED VALUE IS INTERPOLATED FROM THE MISS, NOT SCALED FROM THE HIT.
        # Most chance cards pay a guaranteed floor and roll for an enhanced payout on
        # top (`fp = enhancedFP if triggered else baseFP`), so scaling the triggered
        # value by the odds produced a projection BELOW the floor the card always pays
        # — which is how it was reported. The miss run is what the effect itself pays
        # when the roll fails, so a card with no floor still projects at hit × odds.
        threshold = primary.chanceThreshold
        missed = _computeMissedOutcome(effectConfig, ctx, cardPlayerId, eq.id,
                                       firstPassBreakdowns)
        floorFP = missed.fpBonus if missed else 0.0
        floorFloobits = missed.floobits if missed else 0
        floorMult = missed.multBonus if (missed and missed.multBonus > 1) else 1.0
        primary.fpBonus = floorFP + (primary.fpBonus - floorFP) * threshold
        primary.floobits = int(round(floorFloobits + (primary.floobits - floorFloobits) * threshold))
        if primary.multBonus > 1:
            primary.multBonus = floorMult + (primary.multBonus - floorMult) * threshold

    # 1b. Card upgrade tier. Self-reporting cards scale their own output by
    # CARD_TIER_MULT; structural cards (amplifiers / meta — no own output) get a
    # flat per-tier dividend instead, since scaling zero does nothing. Tier lives
    # on the UserCard instance (defaults to 1 = no change). Applied before the
    # match/modifier pass so the bonus composes with them like any other output.
    tier = getattr(getattr(eq, "user_card", None), "tier", 1) or 1
    if tier > 1:
        from constants import (
            CARD_TIER_MULT, CARD_TIER_DIVIDEND_FP, CARD_TIER_DIVIDEND_FLOOBITS,
        )
        prim = effectConfig.get("primary") or {}
        # No card uses a flat dividend anymore — every amplifier/meta card scales
        # a real knob: conductor's %, doubler/surveyor/sharpshooter's mult, catalyst's
        # chance ramp, advantage's roll count (all handled where they're applied).
        isStructural = False
        if isStructural:
            edition = template.edition or "base"
            if effectConfig.get("outputType") == "floobits":
                primary.floobits += CARD_TIER_DIVIDEND_FLOOBITS.get(edition, {}).get(tier, 0)
            else:
                primary.fpBonus += CARD_TIER_DIVIDEND_FP.get(edition, {}).get(tier, 0.0)
        else:
            m = CARD_TIER_MULT.get(tier, 1.0)
            primary.fpBonus *= m
            primary.floobits = int(round(primary.floobits * m))
            if primary.multBonus > 1:
                primary.multBonus = 1 + (primary.multBonus - 1) * m
            # Reflect the scaling across the whole equation (rate, total, max) so
            # the breakdown shows real tier values. Only for cards with their own
            # output — amplifiers carry no output and set their equation elsewhere.
            if m != 1.0 and primary.equation and (
                primary.fpBonus or primary.floobits or primary.multBonus > 1
            ):
                primary.equation = _rescaleEquationValue(primary.equation, m)

    # 2. Weekly modifier. Fusion: the match multiplier (×1.5 / ×2.5) is REMOVED —
    # every equipped card's player is trivially "on the roster," so a match bonus
    # would be flat inflation. The Wildcard ("force all matched") and Overdrive
    # ("×2.5 match") modifiers are retired alongside it, as is the position conditional.
    mod = ctx.activeModifier

    preMatchFP = primary.fpBonus
    preMatchFloobits = primary.floobits
    preMatchMult = primary.multBonus
    matchedFP = primary.fpBonus
    matchedFloobits = primary.floobits
    matchedMult = primary.multBonus

    # Apply modifier effects to primary values
    if mod in ("amplify", "cascade"):
        # Double FPx bonus portion. Skip tradeoff effects (Lemons) — their
        # multBonus is a structural marker the post-pass uses to multiply
        # a single card's flat FP, not a global FPx that should stack with
        # weekly amplifiers. Without this skip Lemons doubled from ×2.5 to
        # ×4.0 under Amplify, then post-pass multiplied a flat-FP card by
        # the inflated value.
        if matchedMult > 1 and effectName not in _TRADEOFF_EFFECTS:
            matchedMult = 1 + (matchedMult - 1) * 2
    elif mod == "frenzy":
        matchedFP *= 2  # Double +FP
    elif mod == "grounded":
        matchedMult = 0  # Disable all mult effects
    elif mod == "payday":
        matchedFloobits *= 3  # Triple Floobits
    elif mod == "longshot" and category == "conditional":
        # Double conditional card rewards
        matchedFP *= 2
        matchedFloobits *= 2
        if matchedMult > 1:
            matchedMult = 1 + (matchedMult - 1) * 2
    # 3. Position conditional — RETIRED in the fusion cleanup (owner call 2026-07-25).
    #    It was the last remnant of the match-bonus system (Phase 4 removed the ×1.5/×2.5
    #    multiplier; this flat "player hit a stat milestone" bonus lingered). It fired on
    #    EVERY card (isMatch is always true in fusion) — including no-effect floor cards —
    #    and double-counted the player's performance, which their FP (the base) already
    #    rewards. The card's gated effect is now the only value-add. Fields kept at 0/None
    #    for breakdowns_json / recap schema stability.
    conditionalBonus = 0.0
    conditionalLabel = None

    # 4. Secondary effects removed — edition determines effect tier only
    secondaryFP = 0.0
    secondaryFloobits = 0
    secondaryMult = 0.0

    # 5. Total up
    totalCardFP = matchedFP + conditionalBonus
    totalCardFloobits = matchedFloobits

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
        rewardType = effectConfig.get("rewardType") or effectConfig.get("primary", {}).get("rewardType")
        configAndPrimary = set(effectConfig.keys()) | set(effectConfig.get("primary", {}).keys())
        if rewardType in ("mult", "floobits"):
            outputType = rewardType
        elif any(k in configAndPrimary for k in _MULT_KEYS):
            outputType = "mult"
        elif category == "floobits" or any(k in configAndPrimary for k in _FLOOBITS_KEYS):
            outputType = "floobits"

    # FP power-bar gate outcome for this card — computeEffect (above) stashed the
    # on/off ratio on ctx._gateRatios[eq.id] for gated cards.
    _gate = effectConfig.get("gate") or {}
    _gateThreshold = _gate.get("threshold", 0) or 0
    _gateInverse = bool(_gate.get("inverse"))
    _gateAllPro = bool(_gate.get("allPro"))
    _gateActive = None
    if _gateThreshold:
        _ratio = (getattr(ctx, "_gateRatios", None) or {}).get(eq.id)
        if _ratio is not None:
            _gateActive = _ratio >= 1.0

    return CardBreakdown(
        slotNumber=eq.slot_number,
        edition=cardEdition,
        tier=tier,
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
        matchMultiplied=False,
        matchMultiplier=1.0,
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
        streakActive=ctx.liveStreakConditionsMet.get(eq.id) if category == "streak" and not (effectConfig.get("streakConfig") or {}).get("noReset") else None,
        streakCount=ctx.streakCounts.get(eq.id, 0) if category == "streak" and not (effectConfig.get("streakConfig") or {}).get("noReset") else 0,
        gateActive=_gateActive,
        gateThreshold=_gateThreshold,
        gateInverse=_gateInverse,
        gateAllPro=_gateAllPro,
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

    # Pre-scan for chance card synergy, Providence amplifier, Advantage, and Catalyst
    chanceCardCount = 0
    for eq in equippedCards:
        ec = eq.user_card.card_template.effect_config or {}
        effectName = ec.get("effectName", "")
        if ec.get("isChanceAmplifier"):
            chanceAmp = ec.get("primary", {}).get("chanceBonus", 0)
            # Tier scales the odds boost (Providence) too, matching its display.
            t = getattr(getattr(eq, "user_card", None), "tier", 1) or 1
            if t > 1 and chanceAmp:
                from constants import CARD_TIER_MULT
                chanceAmp = round(chanceAmp * CARD_TIER_MULT.get(t, 1.0), 3)
            ctx.chanceBonus += chanceAmp
        if ec.get("isChanceEffect"):
            chanceCardCount += 1
        if effectName == "advantage":
            ctx.hasAdvantage = True
            # Roll count scales with Advantage's tier: tier I = 2, IV = 5.
            _at = getattr(eq.user_card, "tier", 1) or 1
            ctx.advantageRolls = max(ctx.advantageRolls, _at + 1)
        if effectName == "catalyst":
            primary = ec.get("primary", {})
            from managers.cardEffects import tierScaledStrength
            from constants import CARD_TIER_MULT
            _t = getattr(eq.user_card, "tier", 1) or 1
            _scaled = tierScaledStrength("catalyst", primary, CARD_TIER_MULT.get(_t, 1.0))
            # Reads the CARD's own player, matching _computeCatalyst and the card text.
            # This ran on ctx.weekRawFP (a whole roster, ~120 FP) against a baseline of
            # 25 sized for ONE player, so it sat near its cap every week. Falls back to
            # the roster-era keys so a card minted before the rebase still behaves.
            fpPer1Pct = _scaled.get("fpPer1PctSolo",
                                    primary.get("fpPer1PctSolo",
                                                primary.get("fpPer1Pct", 5)))
            baseline = primary.get("baselineSolo", primary.get("baseline", 12))
            maxBoost = _scaled.get("maxBoost", primary.get("maxBoost", 0.10))
            _cardPid = getattr(eq.user_card.card_template, "player_id", None)
            playerFP = float(((ctx.weekPlayerStats or {}).get(_cardPid) or {})
                             .get("fantasyPoints", 0) or 0)
            if playerFP > baseline:
                boost = min(maxBoost, (playerFP - baseline) / fpPer1Pct / 100)
            else:
                boost = 0.0
            ctx.chanceBonus += boost
    ctx.chanceCardCount = chanceCardCount
    # Innate chance synergy: each chance card boosts all others by +0.04
    if chanceCardCount > 1:
        ctx.chanceBonus += (chanceCardCount - 1) * 0.04

    # Pre-scan for streak card synergy (season streaks only — weekly accumulators excluded)
    # A streak is "active" only if its condition is being met THIS week,
    # not merely because streak_count > 0 from a prior week.
    from managers.cardEffects import STREAK_CONFIGS, checkStreakCondition
    streakCardCount = 0
    activeStreakCount = 0
    for eq in equippedCards:
        ec = eq.user_card.card_template.effect_config or {}
        effectName = ec.get("effectName", "")
        if effectName in STREAK_CONFIGS:
            cfg = STREAK_CONFIGS[effectName]
            # Weekly accumulators don't participate in streak synergy
            if cfg.get("isWeekly", False):
                continue
            # Growth/chance cards that borrow the streak-count machinery for
            # their level storage (resetCondition='equipped' = always active)
            # aren't true streak cards. Excluding them from the synergy count
            # prevents Heat Check / Fortitude / etc. from double-counting
            # cards like Bonsai alongside actual streaks.
            if cfg.get("resetCondition") == "equipped":
                continue
            streakCardCount += 1
            cardPlayerId = eq.user_card.card_template.player_id
            if checkStreakCondition(effectName, ctx, cardPlayerId):
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

    # Diamond stat-amplifier pre-pass — Surveyor (yards 1.5x), Sharpshooter
    # (FGs 2x), Doubler (TDs 2x). Must run before Alchemy so Alchemy reads
    # already-doubled FG counts when converting to TDs.
    equippedNames = {
        (eq.user_card.card_template.effect_config or {}).get("effectName")
        for eq in firstPassCards
    }

    # The amplifier pre-passes below mutate per-player stat dicts in place.
    # ctx.weekPlayerStats holds references to caller-owned, shared stat dicts
    # (built once per snapshot and reused across the live overlay pass and the
    # week-end banking pass). Mutating them in place leaked the amped values
    # into the *next* re-derivation of the count — e.g. Doubler stacking 2x
    # onto an already-doubled count (6 TDs -> 12 live -> 24 at week end).
    # Deep-copy before amplifying so we only ever mutate our own private copy;
    # downstream cards still read the amplified values within this calculation.
    if {"surveyor", "sharpshooter", "doubler"} & equippedNames:
        import copy
        ctx.weekPlayerStats = copy.deepcopy(ctx.weekPlayerStats or {})

    # Each amplifier's multiplier scales with its upgrade tier (strength, not a
    # flat dividend) — read the base mult from the card's primary, scale by tier.
    def _ampFactor(name, baseMult, paramKey):
        from constants import CARD_TIER_MULT
        from managers.cardEffects import tierScaledStrength
        eq = next((e for e in firstPassCards
                   if (e.user_card.card_template.effect_config or {}).get("effectName") == name), None)
        if eq is None:
            return baseMult
        prim = (eq.user_card.card_template.effect_config or {}).get("primary", {}) or {}
        tier = getattr(eq.user_card, "tier", 1) or 1
        scaled = tierScaledStrength(name, prim, CARD_TIER_MULT.get(tier, 1.0))
        return scaled.get(paramKey, prim.get(paramKey, baseMult))

    # An amplifier only fires if its OWN depicted player cleared their power bar this week
    # (it has to show up to lead). Uses the card's frozen gate threshold (All-Pro-aware).
    def _amplifierActive(name):
        from constants import CARD_GATE_FP_THRESHOLDS
        eq = next((e for e in firstPassCards
                   if (e.user_card.card_template.effect_config or {}).get("effectName") == name), None)
        if eq is None:
            return False
        tmpl = eq.user_card.card_template
        ec = tmpl.effect_config or {}
        thr = (ec.get("gate") or {}).get("threshold", CARD_GATE_FP_THRESHOLDS.get(tmpl.position, 0))
        fp = ((ctx.weekPlayerStats or {}).get(tmpl.player_id, {}) or {}).get("fantasyPoints", 0) or 0
        return fp >= thr

    if "surveyor" in equippedNames and _amplifierActive("surveyor"):
        yardMult = _ampFactor("surveyor", 1.5, "yardMult")
        for ps in (ctx.weekPlayerStats or {}).values():
            for catKey, fields in [
                ("passing_stats", ("passYards",)),
                ("rushing_stats", ("runYards",)),
                ("receiving_stats", ("rcvYards", "yac")),
                ("kicking_stats", ("fgYards",)),
            ]:
                stats = ps.get(catKey)
                if not isinstance(stats, dict):
                    continue
                for f in fields:
                    if f in stats and isinstance(stats[f], (int, float)):
                        stats[f] = int(round(stats[f] * yardMult))

    if "sharpshooter" in equippedNames and _amplifierActive("sharpshooter"):
        fgMult = _ampFactor("sharpshooter", 2.0, "fgMult")
        for ps in (ctx.weekPlayerStats or {}).values():
            kStats = ps.get("kicking_stats")
            if not isinstance(kStats, dict):
                continue
            for f in ("fgs", "fgYards"):
                if f in kStats and isinstance(kStats[f], (int, float)):
                    kStats[f] = int(round(kStats[f] * fgMult))

    # Pre-pass: Alchemy converts roster K FGs into TDs for other cards' tallies
    # (Cornucopia, Touchdown Piñata, etc.). Must run before any card computes, or cards in
    # lower slot numbers miss the bumped count. Bumps ctx.rosterTotalTds; _computeAlchemy no
    # longer mutates it.
    #
    # ⚠️ IT ALSO HAS TO RUN BEFORE DOUBLER, and used to sit AFTER it. Alchemy's own text says
    # those field goals "count as TDs" and Doubler's says "roster TDs count 2x", so a reader
    # applying both sentences expects the converted scores to double — they did not, purely
    # because Doubler multiplied the pool one block earlier and Alchemy then added to it.
    # Measured with 2 real TDs and 3 made FGs: (2 x 2) + 3 = 7, where the cards promise
    # (2 + 3) x 2 = 10. Reported by a user; owner confirmed Doubler should double them.
    #
    # ⚠️ It still sits AFTER Sharpshooter, which is deliberate and was already the behaviour:
    # Sharpshooter multiplies the kicker's `fgs` above, so Alchemy converts the amplified
    # count. That asymmetry is exactly what made the bug visible — one amplifier fed Alchemy
    # and the other did not, by line order alone.
    alchemyEquipped = any(
        (eq.user_card.card_template.effect_config or {}).get("effectName") == "alchemy"
        for eq in firstPassCards
    )
    if alchemyEquipped and (ctx.gamesActive or ctx.teamResults):
        fgsMade = 0
        for pid in ctx.rosterPlayerIds:
            if ctx.rosterPlayerPositions.get(pid) == 5:
                kickStats = ctx.weekPlayerStats.get(pid, {}).get("kicking_stats", {}) or {}
                fgsMade += kickStats.get("fgs", 0)
        if fgsMade:
            ctx.rosterTotalTds += fgsMade

    if "doubler" in equippedNames and _amplifierActive("doubler"):
        tdMult = _ampFactor("doubler", 2.0, "tdMult")
        ctx.rosterTotalTds = int(round((ctx.rosterTotalTds or 0) * tdMult))
        for ps in (ctx.weekPlayerStats or {}).values():
            for catKey, tdKey in [
                ("passing_stats", "tds"),
                ("rushing_stats", "runTds"),
                ("receiving_stats", "rcvTds"),
            ]:
                stats = ps.get(catKey)
                if isinstance(stats, dict) and tdKey in stats and isinstance(stats[tdKey], (int, float)):
                    stats[tdKey] = int(round(stats[tdKey] * tdMult))
        # Walk Off reads q4ScoringPlays — keep the amp consistent there too.
        for ps in (ctx.weekPlayerStats or {}).values():
            if "q4ScoringPlays" in ps and isinstance(ps["q4ScoringPlays"], (int, float)):
                ps["q4ScoringPlays"] = int(round(ps["q4ScoringPlays"] * tdMult))

    # First pass: compute non-second-pass cards
    firstPassBreakdowns = []
    for eq in firstPassCards:
        breakdown = _computeCardPass(eq, ctx)
        firstPassBreakdowns.append(breakdown)

    # Snapshot first-pass gate outcomes for Full House (full_roster). Its gate is
    # applied per-card inside computeEffect, which stashes each first-pass card's
    # ratio (1.0 on / 0.0 off) into ctx._gateRatios. Freeze the tally here, before
    # any second-pass card computes and adds its own ratio, so Full House reads a
    # clean, order-independent count of the first-pass value cards only. Cards with
    # no gate (the no-effect floor cards) aren't in _gateRatios and so don't count.
    _fpGate = getattr(ctx, "_gateRatios", None) or {}
    ctx._firstPassGatedCount = len(_fpGate)
    ctx._firstPassGatedOn = sum(1 for r in _fpGate.values() if r >= 1.0)
    # Product of the first-pass gate ratios — Full House scales its reward by it. Live
    # ratios are 1.0/0.0 so this is 1.0 iff every first-pass card cleared (else 0.0), an
    # exact fire/no-fire. In the expected projection the ratios are fractional clear
    # probabilities, so the product is the JOINT chance all of them clear (its true EV).
    _prod = 1.0
    for _r in _fpGate.values():
        _prod *= _r
    ctx._firstPassGateProduct = _prod

    # Pre-trigger pass: for each second-pass card, determine whether it would
    # produce non-zero output given only first-pass results. Stash on ctx so
    # trigger-chain effects (Chain Reaction, Bonus Round, Last Resort) can
    # count other second-pass cards in their tallies.
    ctx._secondPassPreTriggers = {
        eq.id: _wouldSecondPassTrigger(eq, firstPassBreakdowns, ctx)
        for eq in secondPassCards
    }

    # Second pass: compute second-pass cards with first-pass results
    secondPassBreakdowns = []
    for eq in secondPassCards:
        breakdown = _computeCardPass(eq, ctx, firstPassBreakdowns=firstPassBreakdowns)
        secondPassBreakdowns.append(breakdown)

    # Convergence: re-run effects that depend on other second-pass cards using
    # *actual* second-pass results instead of pre-trigger heuristics. Closes
    # asymmetries — e.g. CR pushing BR over its threshold without getting
    # credit, or Copycat missing a higher FP value coming from Bonus Round.
    # Last Resort is excluded (its chance roll would destabilize on re-run);
    # Lemons / fortitude don't depend on cross-second-pass info.
    if secondPassCards:
        actualTriggers = {
            eq.id: (b.totalFP > 0 or b.floobitsEarned > 0 or b.primaryMult > 0)
            for eq, b in zip(secondPassCards, secondPassBreakdowns)
        }
        savedPreTriggers = ctx._secondPassPreTriggers
        ctx._secondPassPreTriggers = actualTriggers
        ctx._secondPassBreakdowns = secondPassBreakdowns
        ctx._secondPassEqIds = [eq.id for eq in secondPassCards]
        try:
            for idx, eq in enumerate(secondPassCards):
                effectName = (eq.user_card.card_template.effect_config or {}).get("effectName", "")
                if effectName in {"chain_reaction", "bonus_round", "copycat", "high_roller"}:
                    secondPassBreakdowns[idx] = _computeCardPass(
                        eq, ctx, firstPassBreakdowns=firstPassBreakdowns,
                    )
        finally:
            ctx._secondPassPreTriggers = savedPreTriggers
            ctx._secondPassBreakdowns = None
            ctx._secondPassEqIds = None

    allBreakdowns = firstPassBreakdowns + secondPassBreakdowns

    # Apply tradeoff effects that modify other cards' bonuses
    _applyTradeoffEffects(allBreakdowns)

    # Conductor amplifier — if a Conductor card is in the hand, every other
    # flat-FP card gets a percentage boost on its primary FP output. Mirrors
    # the Lemons/double_down marker pattern: Conductor's own breakdown carries
    # no FP, but its presence amplifies neighbors.
    _applyConductorBoost(allBreakdowns, equippedCards)
    # Captain (Diamond): lift every other card's output by how far its player overshot
    # its power bar. Runs BEFORE aggregation so boosted FPx factors get picked up below.
    _applyCaptainBoost(allBreakdowns, equippedCards, ctx)

    # Glitch surges (docs/GLITCH_CARDS.md). Runs AFTER every effect has computed and after
    # the amplifiers, so a surge scales the card's FINAL output, and BEFORE aggregation so
    # the extra FP and FPx are picked up below. Strictly additive — a glitch never reduces
    # what the card already produced.
    _applyGlitchSurges(allBreakdowns, equippedCards, ctx)

    # Aggregate totals from all breakdowns
    for breakdown in allBreakdowns:
        result.totalBonusFP += breakdown.totalFP
        if breakdown.primaryMult > 1:
            result.multFactors.append(round(breakdown.primaryMult, 2))
        if breakdown.secondaryMult > 1:
            result.multFactors.append(round(breakdown.secondaryMult, 2))
        result.floobitsEarned += breakdown.floobitsEarned
        result.cardBreakdowns.append(breakdown)

    # Team stacking — fielding multiple cards whose depicted players share a real team grants
    # a lineup-wide FPx that escalates with the largest same-team group. Champion cards in the
    # stack AMPLIFY it (the reigning champs are one team, so a champ stack is the premium
    # "Dynasty" stack). Pick the best-paying group so ties resolve toward the champion one.
    # The "Synergy" weekly modifier DOUBLES the applied stack bonus this week (SYNERGY_MODIFIER
    # _STACK_MULT) — the fusion-native repurpose of the old unique-position formula, which is
    # dead now that every equipped card is a different slot. A non-stacked lineup is unaffected.
    from constants import (CARD_TEAM_STACK_BONUS, CARD_CHAMPION_STACK_PREMIUM,
                           SYNERGY_MODIFIER_STACK_MULT)
    if CARD_TEAM_STACK_BONUS:
        byTeam = {}
        for eq in equippedCards:
            tmpl = eq.user_card.card_template
            tid = getattr(tmpl, 'team_id', None)
            if not tid:
                continue
            isChamp = 'champion' in (getattr(tmpl, 'classification', None) or '')
            grp = byTeam.setdefault(tid, [0, 0])  # [size, champions]
            grp[0] += 1
            if isChamp:
                grp[1] += 1
        _maxKey = max(CARD_TEAM_STACK_BONUS)
        best = None  # (delta, size, champions)
        for size, champs in byTeam.values():
            if size < 2:
                continue
            base = CARD_TEAM_STACK_BONUS.get(min(size, _maxKey), 0.0)
            delta = base * (1.0 + (champs / size) * CARD_CHAMPION_STACK_PREMIUM)
            if best is None or delta > best[0]:
                best = (delta, size, champs)
        if best and best[0] > 0:
            baseDelta = best[0]
            synergyMult = SYNERGY_MODIFIER_STACK_MULT if ctx.activeModifier == "synergy" else 1.0
            appliedDelta = baseDelta * synergyMult
            result.multFactors.append(round(1.0 + appliedDelta, 3))
            result.stackSize = best[1]
            result.stackChampions = best[2]
            result.stackBonus = round(appliedDelta, 3)
            # The modifier's extra (0 when Synergy inactive) — excluded from the achievement.
            result.stackModifierBonus = round(appliedDelta - baseDelta, 3)

    result.totalBonusFP = round(result.totalBonusFP, 2)
    return result


def aggregateMultFactors(multFactors: List[float]) -> float:
    """Combine FPx factors into a single multiplier using bonus-additive math.

    Each factor's contribution above 1.0 is summed rather than multiplied.
    Two 1.5x factors give 1 + 0.5 + 0.5 = 2.0x (not 2.25x).
    Empty list / no FPx cards = 1.0x (no effect).

    Replaces the prior multiplicative compounding so stacked FPx hands grow
    linearly instead of geometrically. Single-FPx behavior is unchanged
    (1.3 stays 1.3).
    """
    return 1.0 + sum(max(0.0, f - 1.0) for f in multFactors)


def _applyGlitchSurges(breakdowns: List[CardBreakdown], equippedCards, ctx) -> None:
    """Roll each glitched card's weekly surge and add it on top of what the card produced.

    Resolves at WEEK END and cannot resolve earlier: the trigger chance depends on anomaly
    events that fire during the week's games. While games are live this only records the
    running CHANCE, so the UI can scramble its line item with an intensity that tracks the
    odds — the card is visibly computing something it will not tell you yet.
    """
    from constants import GLITCH_CARDS_ENABLED
    if not GLITCH_CARDS_ENABLED or not breakdowns:
        return
    # CardBreakdown carries no equipped-card id, so key on (slot, player) — under fusion
    # each slot holds a distinct rostered player, so the pair is unique within a lineup.
    glitchedIds = {}
    for eq in equippedCards:
        uc = getattr(eq, 'user_card', None)
        if uc is None or not getattr(uc, 'glitched', False):
            continue
        pid = getattr(getattr(uc, 'card_template', None), 'player_id', None)
        glitchedIds[(getattr(eq, 'slot_number', 0), pid)] = (uc.id, pid)
    if not glitchedIds:
        return

    from managers.glitchCards import (triggerChance, rollSurge, surgePayout,
                                      anomalyContextFor)
    season = getattr(ctx, 'season', 0) or 0
    week = getattr(ctx, 'weekNumber', 0) or 0
    dial = 1.0
    try:
        from managers.anomalyManager import getCriticalityMultiplier
        dial = getCriticalityMultiplier(season, week)
    except Exception:
        pass

    anomalyCtx = anomalyContextFor([pid for _, pid in glitchedIds.values()], season, week)

    for b in breakdowns:
        entry = glitchedIds.get((b.slotNumber, b.playerId))
        if entry is None:
            continue
        userCardId, playerId = entry
        state, events = anomalyCtx.get(playerId, ('stable', {}))
        # Every glitched card in THIS lineup raises every other one's odds — the swarm
        # term. `glitchedIds` is exactly the equipped glitched set, so it is already the
        # right count; owning more elsewhere does nothing.
        chance = triggerChance(state, events, dial, glitchedEquipped=len(glitchedIds))
        b.glitched = True
        b.glitchChance = round(chance, 3)
        b.glitchUserCardId = userCardId
        b.glitchReadable = (state == 'awakened')
        # Unresolved while the week is still running AND in any projection. gamesActive
        # alone is not enough: a projection has gamesActive False, so guarding on it only
        # would RESOLVE a week that has not happened and show a settled payout in the
        # forward-looking panel. The roll depends on anomaly events that have not fired.
        if getattr(ctx, 'gamesActive', False) or getattr(ctx, 'isProjection', False):
            continue
        triggered, outcome, mult = rollSurge(
            getattr(ctx, 'userId', 0) or 0, season, week, userCardId, chance)
        if not triggered:
            continue
        extraFp, extraMult = surgePayout(mult, b.totalFP, b.primaryMult)
        b.glitchTriggered = True
        b.glitchOutcome = outcome
        b.glitchFp = extraFp
        b.glitchMultDelta = extraMult
        b.totalFP = round(b.totalFP + extraFp, 2)
        if extraMult and b.primaryMult > 1:
            b.primaryMult = round(b.primaryMult + extraMult, 3)


def _applyTradeoffEffects(breakdowns: List[CardBreakdown]) -> None:
    """Mutate breakdowns in-place for tradeoff effects like Lemons and Feast or Famine."""
    tradeoffNames = {b.effectName for b in breakdowns if b.effectName in _TRADEOFF_EFFECTS}
    if not tradeoffNames:
        return

    # Collect non-tradeoff breakdowns (the ones tradeoffs operate on)
    normalBreakdowns = [b for b in breakdowns if b.effectName not in _TRADEOFF_EFFECTS]

    if "double_down" in tradeoffNames and normalBreakdowns:
        # Multiply the lowest-earning card's OWN effect output (primaryFP), not
        # totalFP. The position-conditional match bonus is a reward for the
        # depicted player's real-game performance, not part of the card's effect,
        # so Lemons neither counts it when picking the lowest earner nor
        # amplifies it. This also excludes pure markers (0 effect output) for
        # free, and keeps flat-FP only so FPx/floobits cards aren't mistreated.
        ddBreakdown = next((b for b in breakdowns if b.effectName == "double_down"), None)
        multValue = float(ddBreakdown.primaryMult) if ddBreakdown and ddBreakdown.primaryMult else 2.5
        nonZeroFP = [b for b in normalBreakdowns if b.primaryFP > 0 and b.outputType == "fp"]
        if nonZeroFP:
            lowest = min(nonZeroFP, key=lambda b: b.primaryFP)
            originalFP = lowest.primaryFP
            bonusFP = round(originalFP * (multValue - 1), 1)
            lowest.primaryFP = round(lowest.primaryFP + bonusFP, 1)
            lowest.totalFP = round(lowest.totalFP + bonusFP, 1)
            lowest.equation = f"{lowest.equation} × {multValue} (Lemons)"
        # Clear the marker mult so it doesn't stack on the global FPx aggregation
        if ddBreakdown:
            ddBreakdown.primaryMult = 0


def _applyConductorBoost(breakdowns: List[CardBreakdown], equippedCards) -> None:
    """Conductor diamond amplifier: when present in the hand, every other
    flat-FP card's primary output is multiplied by (1 + boostPct/100).
    Conductor's own breakdown produces no output. Reads boostPct from
    Conductor's effectConfig.primary so seeded variance is honored.

    (The old match-bonus scale-up of the boost percentage is retired with the
    match multiplier in the fantasy/cards fusion.)
    """
    conductorBreakdown = next(
        (b for b in breakdowns if b.effectName == "conductor"), None,
    )
    if conductorBreakdown is None:
        return
    # The Conductor has to show up to conduct — no boost if their own player was cold.
    if conductorBreakdown.gateActive is False:
        conductorBreakdown.equation = "Conductor didn't clear their bar"
        return
    boostPct = 20
    for eq in (equippedCards or []):
        ec = (eq.user_card.card_template.effect_config or {})
        if ec.get("effectName") == "conductor":
            prim = ec.get("primary", {}) or {}
            boostPct = prim.get("boostPct", 20)
            # Boost % scales with the Conductor card's upgrade tier.
            from constants import CARD_TIER_MULT
            from managers.cardEffects import tierScaledStrength
            tier = getattr(eq.user_card, "tier", 1) or 1
            boostPct = tierScaledStrength("conductor", prim, CARD_TIER_MULT.get(tier, 1.0)).get("boostPct", boostPct)
            break
    factor = 1.0 + (boostPct / 100.0)
    boosted = 0
    for b in breakdowns:
        if b.effectName == "conductor":
            continue
        if b.outputType != "fp":
            continue
        # Boost the card's own effect output (primaryFP), not totalFP — the
        # position-conditional performance bonus isn't part of the effect, and
        # this skips pure markers (0 effect output) for free.
        if b.primaryFP <= 0:
            continue
        bonus = round(b.primaryFP * (factor - 1.0), 1)
        b.primaryFP = round(b.primaryFP + bonus, 1)
        b.totalFP = round(b.totalFP + bonus, 1)
        b.equation = f"{b.equation} +{boostPct}% (Conductor)"
        boosted += 1
    if boosted > 0:
        # Match multiplier was removed in the fusion Phase 4 retune, so there's no
        # "(matched)" tag any more (the old `matched` reference was left dangling and
        # crashed any lineup with a Conductor + a flat-FP card).
        conductorBreakdown.equation = f"+{boostPct}% on {boosted} flat-FP card{'s' if boosted != 1 else ''}"
    else:
        conductorBreakdown.equation = "No flat-FP cards to amplify"


def _applyCaptainBoost(breakdowns: List[CardBreakdown], equippedCards, ctx) -> None:
    """Captain diamond amplifier: each OTHER card's output is lifted by how far its
    depicted player scored OVER its power bar this week — +perOvershootPct per FP of
    overshoot, capped at +100% (2x). Captain's own breakdown produces nothing. Boosts
    FP, Floobits, and FPx outputs alike (FPx by scaling the delta above 1.0)."""
    captainBd = next((b for b in breakdowns if b.effectName == "captain"), None)
    if captainBd is None:
        return
    # The Captain has to show up to lead — no boost if their own player was under the bar.
    if captainBd.gateActive is False:
        captainBd.equation = "Captain didn't clear their bar"
        return
    perPct = 0.0
    for eq in (equippedCards or []):
        ec = (eq.user_card.card_template.effect_config or {})
        if ec.get("effectName") == "captain":
            prim = ec.get("primary", {}) or {}
            perPct = prim.get("perOvershootPct", 0.0)
            from constants import CARD_TIER_MULT
            from managers.cardEffects import tierScaledStrength
            tier = getattr(eq.user_card, "tier", 1) or 1
            perPct = tierScaledStrength("captain", prim, CARD_TIER_MULT.get(tier, 1.0)).get("perOvershootPct", perPct)
            break
    if perPct <= 0:
        return
    stats = getattr(ctx, "weekPlayerStats", None) or {}
    boosted = 0
    for b in breakdowns:
        if b.effectName == "captain":
            continue
        thr = b.gateThreshold or 0
        playerFP = (stats.get(b.playerId, {}) or {}).get("fantasyPoints", 0) or 0
        overshoot = max(0.0, playerFP - thr)
        if overshoot <= 0:
            continue
        factor = min(overshoot * perPct, 1.0)  # cap at +100% (2x)
        if factor <= 0:
            continue
        if b.outputType == "fp" and b.primaryFP > 0:
            bonus = round(b.primaryFP * factor, 1)
            b.primaryFP = round(b.primaryFP + bonus, 1)
            b.totalFP = round(b.totalFP + bonus, 1)
            boosted += 1
        elif b.outputType == "floobits" and b.floobitsEarned > 0:
            b.floobitsEarned = int(round(b.floobitsEarned * (1.0 + factor)))
            boosted += 1
        elif b.outputType == "mult" and b.primaryMult > 1.0:
            delta = b.primaryMult - 1.0
            b.primaryMult = round(1.0 + delta * (1.0 + factor), 3)
            boosted += 1
    captainBd.equation = (f"amplified {boosted} card{'s' if boosted != 1 else ''} on overshoot"
                          if boosted else "no card cleared its bar to amplify")


