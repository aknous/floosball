"""Card payout projections — estimates what each equipped (and candidate)
card will output this week, given season-to-date averages + ELO forecasts.

Reuses the live `calculateWeekCardBonuses` calculator with a projection-
flagged context so the same effect functions produce expected values
instead of actual game-result values. Chance cards resolve to expected
value (trigger prob × reward) rather than a roll, and outcome-dependent
booleans take their most-likely path.

Entry points:
  - buildProjectionContext(...) — populate a CardCalcContext
  - computeEquippedProjections(...) — projections for the locked hand
  - computeCandidateProjection(...) — solo projection for one unequipped card
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from managers.cardEffectCalculator import CardCalcContext, calculateWeekCardBonuses

logger = logging.getLogger("floosball")


# Effectiveness tier thresholds — score combines FP, Floobits (weight 0.3),
# and mult bonus (weight 10 per +1.0). Chosen to feel reasonable given
# typical base-card output ranges (2–10 FP).
_TIER_STRONG = 8.0
_TIER_GOOD = 3.0
_TIER_MODERATE = 0.5


def _classifyEffectiveness(
    projectedFP: float,
    projectedFloobits: float,
    projectedMult: float,
    isContingent: bool,
    nullified: bool,
) -> str:
    """Map a projection to a tier label.

    Tiers (used by the UI for ++/+/=/⚠/✗ indicators):
      'strong'    — projected output is high
      'good'      — projected output is meaningful
      'moderate'  — projected output is small but non-zero
      'variable'  — output is zero but the effect can still trigger
                    (chance cards, contingent events)
      'nullified' — output is zero and the trigger is structurally
                    unreachable this week (e.g. streak card with no
                    active streak going in)
    """
    if nullified:
        return "nullified"
    score = projectedFP + (projectedFloobits * 0.3) + max(projectedMult - 1.0, 0.0) * 10
    if score >= _TIER_STRONG:
        return "strong"
    if score >= _TIER_GOOD:
        return "good"
    if score >= _TIER_MODERATE:
        return "moderate"
    return "variable" if isContingent else "nullified"


def _perGameAverageStats(row) -> dict:
    """Convert a PlayerSeasonStats row into a per-game-average card-calc
    stats dict. Returns None for rows with zero games played."""
    from managers.fantasyTracker import _dbStatsToCardFormat

    if not row or (getattr(row, 'games_played', 0) or 0) == 0:
        return None
    gp = max(row.games_played, 1)

    # Average each stat category across games played. Stored JSON uses the
    # raw engine keys ("yards", "tds", etc.) — _dbStatsToCardFormat maps
    # them to the "passYards"/"runYards"/"rcvYards" shape card effects read.
    def _avg(d: Optional[dict]) -> dict:
        if not d:
            return {}
        return {k: (v / gp if isinstance(v, (int, float)) else v) for k, v in d.items()}

    return _dbStatsToCardFormat(
        passingStats=_avg(row.passing_stats),
        rushingStats=_avg(row.rushing_stats),
        receivingStats=_avg(row.receiving_stats),
        kickingStats=_avg(row.kicking_stats),
        fantasyPoints=(row.fantasy_points or 0) / gp,
        teamId=row.team_id or 0,
    )


def _winProbabilityFromElo(favElo: float, oppElo: float) -> float:
    """Standard ELO win probability: P(A beats B) = 1 / (1 + 10^((B-A)/400))."""
    try:
        return 1.0 / (1.0 + 10 ** ((oppElo - favElo) / 400.0))
    except Exception:
        return 0.5


def _findUpcomingOpponent(session, favTeamId: int, season: int, week: int,
                          teamManager) -> Tuple[float, str]:
    """Return (opponentElo, opponentAbbr) for the favorite team's next game
    this season. Falls back to (1500, '') if no game is scheduled."""
    from database.models import Game

    if not favTeamId:
        return 1500.0, ""

    # Look at the next non-final scheduled game for this team (this week first,
    # then forward). If all games are in the past, fall back to the most
    # recent opponent so the context isn't blank at week 0.
    upcoming = (
        session.query(Game).filter(
            Game.season == season,
            Game.week >= week,
            Game.status != 'final',
        ).filter(
            (Game.home_team_id == favTeamId) | (Game.away_team_id == favTeamId)
        ).order_by(Game.week, Game.id).first()
    )
    if upcoming is None:
        return 1500.0, ""
    oppId = (upcoming.away_team_id
             if upcoming.home_team_id == favTeamId
             else upcoming.home_team_id)
    if not teamManager:
        return 1500.0, ""
    opp = teamManager.getTeamById(oppId)
    if not opp:
        return 1500.0, ""
    return getattr(opp, 'elo', 1500.0), getattr(opp, 'abbr', '') or getattr(opp, 'name', '')


def buildProjectionContext(
    session,
    userId: int,
    season: int,
    week: int,
    seasonManager,
    playerManager,
) -> Optional[CardCalcContext]:
    """Build a CardCalcContext populated with projected values suitable for
    running the standard card calculator in projection mode.

    Returns None if the user has no fantasy roster yet.
    """
    from database.models import (
        FantasyRoster, FantasyRosterPlayer, PlayerSeasonStats,
        User, UserCurrency, WeeklyModifier, FantasyRosterSwap,
    )
    from managers.cardEffectCalculator import computeEminenceData

    roster = session.query(FantasyRoster).filter_by(
        user_id=userId, season=season
    ).first()
    if not roster:
        return None

    rosterPlayerIds = {rp.player_id for rp in roster.players}
    if not rosterPlayerIds:
        return None

    # Build per-player projected stats from season-to-date averages
    statRows = (
        session.query(PlayerSeasonStats)
        .filter(
            PlayerSeasonStats.season == season,
            PlayerSeasonStats.player_id.in_(rosterPlayerIds),
        )
        .all()
    )
    rowByPlayer = {r.player_id: r for r in statRows}

    weekPlayerStats: Dict[int, dict] = {}
    weekRawFP = 0.0
    rosterTotalTds = 0.0
    rosterPlayerNames: Dict[int, str] = {}
    rosterPlayerRatings: Dict[int, int] = {}
    rosterPlayerPositions: Dict[int, int] = {}
    rosterPlayerTeamIds: Dict[int, int] = {}
    playerSeasonFPPerGame: Dict[int, float] = {}

    for rp in roster.players:
        pid = rp.player_id
        dbPlayer = None
        if playerManager:
            dbPlayer = playerManager.getPlayerById(pid)
        # Populate identity fields regardless of stats
        if dbPlayer:
            rosterPlayerNames[pid] = getattr(dbPlayer, 'name', '')
            rosterPlayerRatings[pid] = int(getattr(dbPlayer, 'playerRating', 0))
            try:
                rosterPlayerPositions[pid] = dbPlayer.position.value
            except Exception:
                rosterPlayerPositions[pid] = 0
            team = getattr(dbPlayer, 'team', None)
            rosterPlayerTeamIds[pid] = getattr(team, 'id', 0) if team else 0

        row = rowByPlayer.get(pid)
        avgStats = _perGameAverageStats(row)
        if avgStats is None:
            # No stats yet — default to zeros so cards gracefully report
            # variable/nullified rather than crashing on missing keys.
            avgStats = {
                "teamId": rosterPlayerTeamIds.get(pid, 0),
                "fantasyPoints": 0,
                "passing_stats": {"passYards": 0, "tds": 0},
                "rushing_stats": {"runYards": 0, "runTds": 0, "carries": 0},
                "receiving_stats": {"rcvYards": 0, "rcvTds": 0, "receptions": 0, "yac": 0, "longest": 0},
                "kicking_stats": {"fgs": 0, "fgAtt": 0, "longest": 0, "fg40plus": 0},
            }

        weekPlayerStats[pid] = avgStats
        weekRawFP += avgStats.get("fantasyPoints", 0)
        # Sum projected TDs across all categories for effects like Piñata
        pst = avgStats.get("passing_stats", {}) or {}
        rst = avgStats.get("rushing_stats", {}) or {}
        recSt = avgStats.get("receiving_stats", {}) or {}
        rosterTotalTds += (pst.get("tds", 0) + rst.get("runTds", 0) + recSt.get("rcvTds", 0))
        if row:
            playerSeasonFPPerGame[pid] = (row.fantasy_points or 0) / max(row.games_played, 1)

    # Favorite team + opponent + win probability
    dbUser = session.get(User, userId)
    favTeamId = dbUser.favorite_team_id if dbUser else None

    teamManager = None
    try:
        teamManager = seasonManager.serviceContainer.getService('team_manager')
    except Exception:
        pass

    favElo = 1500.0
    favStreak = 0
    favPriorStreak = 0
    favPeakStreak = 0
    favSeasonLosses = 0
    favSeasonUpsetWins = 0
    favInPlayoffs = False
    favTeam = None
    if favTeamId and teamManager:
        favTeam = teamManager.getTeamById(favTeamId)
        if favTeam:
            favElo = getattr(favTeam, 'elo', 1500.0)
            favStats = getattr(favTeam, 'seasonTeamStats', {}) or {}
            favStreak = favStats.get('streak', 0)
            favPriorStreak = favStats.get('priorStreak', favStreak)
            favPeakStreak = favStats.get('peakStreak', abs(favStreak))
            favSeasonLosses = favStats.get('losses', 0)
            favSeasonUpsetWins = favStats.get('upsetWins', 0)

    oppElo, oppName = _findUpcomingOpponent(session, favTeamId, season, week, teamManager)
    winProb = _winProbabilityFromElo(favElo, oppElo)

    # League average ELO (for effects that compare vs league)
    leagueAverageElo = 1500.0
    if teamManager:
        allTeams = teamManager.teams
        if allTeams:
            leagueAverageElo = sum(getattr(t, 'elo', 1500.0) for t in allTeams) / len(allTeams)

    # Team results — projection: fav wins if winProb > 0.5
    teamResults: Dict[int, bool] = {}
    if favTeamId:
        teamResults[favTeamId] = winProb > 0.5

    # Streak counts per equipped card
    equipped = roster.equipped_cards or []
    streakCounts = {
        eq.id: getattr(eq, 'streak_count', 1) for eq in equipped
    }

    # Roster unchanged weeks
    lastSwap = (
        session.query(FantasyRosterSwap.swap_week)
        .filter_by(roster_id=roster.id)
        .order_by(FantasyRosterSwap.swap_week.desc())
        .first()
    )
    rosterUnchangedWeeks = week if not lastSwap else max(0, week - lastSwap[0])

    # Season swaps used
    seasonSwapsUsed = (
        session.query(FantasyRosterSwap)
        .filter_by(roster_id=roster.id)
        .count()
    )

    # Modifier
    activeModifier = ""
    try:
        modRow = session.query(WeeklyModifier).filter_by(
            season=season, week=week
        ).first()
        if modRow:
            activeModifier = modRow.modifier_type or ""
    except Exception:
        pass

    # Balance (Fat Cat etc.)
    userFloobitsBalance = 0
    try:
        currency = session.query(UserCurrency).filter_by(user_id=userId).first()
        if currency:
            userFloobitsBalance = currency.balance or 0
    except Exception:
        pass

    # Season performance ratings (snapshot)
    playerPerfRatings: Dict[int, float] = {}
    if playerManager:
        for p in playerManager.activePlayers:
            perfRating = getattr(p, 'seasonPerformanceRating', 0) or 0
            if perfRating > 0:
                playerPerfRatings[p.id] = perfRating

    # Eminence data (position-pace averages) — reuses existing helper
    try:
        positionAvgFPs, _ = computeEminenceData(session, season, week)
    except Exception:
        positionAvgFPs = {}

    # Kicker season FG misses
    kickerSeasonFgMisses = 0
    for pid in rosterPlayerIds:
        row = rowByPlayer.get(pid)
        if not row:
            continue
        ks = row.kicking_stats or {}
        fgAtt = ks.get('fgAtt', 0) or 0
        fgs = ks.get('fgs', 0) or 0
        if fgAtt > fgs:
            kickerSeasonFgMisses += (fgAtt - fgs)
            break  # Only one kicker per roster

    return CardCalcContext(
        isProjection=True,
        favoriteTeamWinProb=winProb,
        userId=userId,
        season=season,
        weekNumber=week,
        gamesActive=False,
        chanceBonus=0.0,  # Pre-scan in calculator fills this from hand composition
        kickerSeasonFgMisses=kickerSeasonFgMisses,
        rosterPlayerIds=rosterPlayerIds,
        weekPlayerStats=weekPlayerStats,
        weekRawFP=weekRawFP,
        rosterPlayerRatings=rosterPlayerRatings,
        rosterTotalTds=int(round(rosterTotalTds)),
        rosterPlayerPositions=rosterPlayerPositions,
        streakCounts=streakCounts,
        userFavoriteTeamId=favTeamId,
        favoriteTeamElo=favElo,
        leagueAverageElo=leagueAverageElo,
        favoriteTeamStreak=favStreak,
        favoriteTeamPriorStreak=favPriorStreak,
        favoriteTeamPeakStreak=favPeakStreak,
        favoriteTeamSeasonLosses=favSeasonLosses,
        favoriteTeamInPlayoffs=favInPlayoffs,
        favoriteTeamWonThisWeek=(winProb > 0.5),
        favoriteTeamOpponentElo=oppElo,
        favoriteTeamOpponentName=oppName,
        favoriteTeamBigPlays=0,  # Unknowable pre-game
        favoriteTeamGameFinal=False,
        favoriteTeamSeasonUpsetWins=favSeasonUpsetWins,
        rosterUnchangedWeeks=rosterUnchangedWeeks,
        teamResults=teamResults,
        playerPerformanceRatings=playerPerfRatings,
        gamePerformanceRatings={},
        rosterPlayerTeamIds=rosterPlayerTeamIds,
        rosterPlayerNames=rosterPlayerNames,
        favoriteTeamScoreMargin=0,  # Projection doesn't forecast margin
        favoriteTeamComebackWin=False,
        favoriteTeamLargestDeficit=0,
        favoriteTeamWalkOffWin=False,
        activeModifier=activeModifier,
        unusedSwaps=(roster.swaps_available or 0) + (roster.purchased_swaps or 0),
        seasonSwapsUsed=seasonSwapsUsed,
        userFloobitsBalance=userFloobitsBalance,
        liveStreakConditionsMet={},
        positionAvgFPs=positionAvgFPs,
        playerSeasonFPPerGame=playerSeasonFPPerGame,
    )


@dataclass
class CardProjection:
    """A per-card projection result, shaped for the UI."""
    userCardId: int
    effectName: str
    displayName: str
    projectedFP: float = 0.0
    projectedFloobits: float = 0.0
    projectedMult: float = 0.0
    isMatch: bool = False
    tier: str = "variable"  # strong | good | moderate | variable | nullified
    equation: str = ""
    note: str = ""


def computeEquippedProjections(
    session,
    userId: int,
    season: int,
    week: int,
    seasonManager,
    playerManager,
) -> Dict[str, Any]:
    """Project the current week for each equipped card on the user's roster.

    Returns:
        {
            "cards": [CardProjection as dict],
            "totalBonusFP": float,
            "totalFloobits": int,
            "multFactors": [float],
            "projectedRosterFP": float,  # sum of per-game avg FP
            "projectedTotalFP": float,   # rosterFP + card bonus FP
        }
    """
    from database.models import FantasyRoster

    roster = session.query(FantasyRoster).filter_by(
        user_id=userId, season=season
    ).first()
    if not roster:
        return _emptyProjectionPayload()

    ctx = buildProjectionContext(
        session, userId, season, week, seasonManager, playerManager,
    )
    if ctx is None:
        return _emptyProjectionPayload()

    equipped = roster.equipped_cards or []
    result = calculateWeekCardBonuses(equipped, ctx)

    cards: List[Dict[str, Any]] = []
    for b in result.cardBreakdowns:
        contingent = b.isChanceEffect or _isOutcomeSensitive(b.effectName)
        nullified = _detectNullified(b, ctx)
        tier = _classifyEffectiveness(
            b.totalFP, b.floobitsEarned, b.primaryMult,
            isContingent=contingent, nullified=nullified,
        )
        cards.append({
            "slotNumber": b.slotNumber,
            "effectName": b.effectName,
            "displayName": b.displayName,
            "projectedFP": round(b.totalFP, 2),
            "projectedFloobits": b.floobitsEarned,
            "projectedMult": round(b.primaryMult, 2) if b.primaryMult > 0 else 0.0,
            "isMatch": bool(b.matchMultiplied),
            "tier": tier,
            "equation": b.equation,
            "outputType": b.outputType,
        })

    return {
        "cards": cards,
        "totalBonusFP": round(result.totalBonusFP, 2),
        "totalFloobits": result.floobitsEarned,
        "multFactors": [round(m, 2) for m in result.multFactors],
        "projectedRosterFP": round(ctx.weekRawFP, 2),
        "projectedTotalFP": round(ctx.weekRawFP + result.totalBonusFP, 2),
        "opponent": ctx.favoriteTeamOpponentName,
        "winProbability": round(ctx.favoriteTeamWinProb, 2),
    }


def computeCandidateProjection(
    userCard,
    session,
    userId: int,
    season: int,
    week: int,
    seasonManager,
    playerManager,
) -> Optional[Dict[str, Any]]:
    """Solo projection for one unequipped card, answering "if I equipped this,
    what would it contribute?" Cheaper than full hand simulation — skips
    synergy effects (Catalyst, chance hand composition, etc.). Good enough
    for relative comparison in the equip modal.
    """
    ctx = buildProjectionContext(
        session, userId, season, week, seasonManager, playerManager,
    )
    if ctx is None:
        return None

    wrapped = _wrapUserCardAsEquipped(userCard)
    result = calculateWeekCardBonuses([wrapped], ctx)
    if not result.cardBreakdowns:
        return None

    b = result.cardBreakdowns[0]
    contingent = b.isChanceEffect or _isOutcomeSensitive(b.effectName)
    nullified = _detectNullified(b, ctx)
    tier = _classifyEffectiveness(
        b.totalFP, b.floobitsEarned, b.primaryMult,
        isContingent=contingent, nullified=nullified,
    )
    return {
        "userCardId": userCard.id,
        "effectName": b.effectName,
        "displayName": b.displayName,
        "projectedFP": round(b.totalFP, 2),
        "projectedFloobits": b.floobitsEarned,
        "projectedMult": round(b.primaryMult, 2) if b.primaryMult > 0 else 0.0,
        "isMatch": bool(b.matchMultiplied),
        "tier": tier,
        "outputType": b.outputType,
        "equation": b.equation,
    }


# ── Helpers ─────────────────────────────────────────────────────────────

def _emptyProjectionPayload() -> Dict[str, Any]:
    return {
        "cards": [],
        "totalBonusFP": 0.0,
        "totalFloobits": 0,
        "multFactors": [],
        "projectedRosterFP": 0.0,
        "projectedTotalFP": 0.0,
        "opponent": "",
        "winProbability": 0.5,
    }


# Effect names whose output depends on live-game events that the projection
# can't directly forecast (big plays, comeback wins, walk-off wins, etc.).
# These are treated as "variable" rather than "nullified" when they
# project to zero.
_OUTCOME_SENSITIVE_EFFECTS = frozenset({
    "comeback_kid", "walk_off", "upset_win", "bombs_away", "underdog",
    "big_play", "good_neighbor", "showoff", "domination", "gone_streaking",
    "closer",
})


def _isOutcomeSensitive(effectName: str) -> bool:
    return effectName in _OUTCOME_SENSITIVE_EFFECTS


def _detectNullified(breakdown, ctx: CardCalcContext) -> bool:
    """Return True when the card produced zero AND its trigger is structurally
    unreachable this week — as opposed to 'might trigger'. Used to draw the
    ✗ icon for streak cards with no streak, etc.

    Conservative: only returns True when we're confident. Ambiguous cases
    fall through to 'variable'.
    """
    if breakdown.totalFP > 0 or breakdown.floobitsEarned > 0 or breakdown.primaryMult > 0:
        return False
    # Streak cards with streak count of 0 or 1 are effectively no-ops this
    # week if their condition isn't being met.
    effectName = breakdown.effectName
    try:
        from managers.cardEffects import STREAK_CONFIGS
        if effectName in STREAK_CONFIGS:
            count = ctx.streakCounts.get(breakdown.slotNumber, 0)  # slot is a proxy; real check is per-eq
            if count <= 1 and breakdown.totalFP == 0:
                return True
    except Exception:
        pass
    return False


def _wrapUserCardAsEquipped(userCard):
    """Wrap a UserCard as a temporary EquippedCard-shaped object so the
    calculator can consume it without DB writes. The calculator only
    accesses .id, .slot_number, .streak_count, and .user_card.card_template.
    """
    class _FauxEquipped:
        __slots__ = ('id', 'slot_number', 'streak_count', 'user_card')

        def __init__(self, uc):
            self.id = -abs(uc.id)  # negative so it can't clash with real equipped ids
            self.slot_number = 0
            self.streak_count = 1
            self.user_card = uc

    return _FauxEquipped(userCard)
