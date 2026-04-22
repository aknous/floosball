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
# and mult bonus (weight 40 per +1.0). Calibrated so:
#   strong   = +20 FP or ×1.50 (or ~+67 F)
#   good     = +8  FP or ×1.20 (or ~+27 F)
#   moderate = +2  FP or ×1.05 (or ~+7  F)
# High bars — 'strong' should only fire for cards genuinely producing
# top-tier output, not every playable card.
_TIER_STRONG = 20.0
_TIER_GOOD = 8.0
_TIER_MODERATE = 2.0
_MULT_SCORE_COEFFICIENT = 40.0


def _classifyEffectiveness(
    projectedFP: float,
    projectedFloobits: float,
    projectedMult: float,
    nullified: bool,
    isDeterministic: bool,
) -> str:
    """Map a projection to a tier label.

    Tiers (used by the UI for ++/+/=/?/× indicators):
      'strong'    — projected output is high
      'good'      — projected output is meaningful
      'moderate'  — projected output is small but non-zero, OR the
                    card is deterministic and its current state
                    produces a baseline no-bonus result (e.g.
                    Vagabond with 0 swaps, Opulence with 0 floobits).
                    Those cards know their output exactly — they just
                    don't contribute anything right now.
      'variable'  — output is zero and the effect might still trigger
                    (chance cards, cards keyed to team/game outcomes
                    that could still break the other way).
      'nullified' — output is zero AND the trigger is structurally
                    unreachable this week — proven dead, not just
                    uncertain.
    """
    if nullified:
        return "nullified"
    score = projectedFP + (projectedFloobits * 0.3) + max(projectedMult - 1.0, 0.0) * _MULT_SCORE_COEFFICIENT
    if score >= _TIER_STRONG:
        return "strong"
    if score >= _TIER_GOOD:
        return "good"
    if score >= _TIER_MODERATE:
        return "moderate"
    # Zero-score branch — if the card isn't contingent on anything we
    # haven't already projected, call it 'moderate' so the UI shows the
    # actual baseline number instead of pretending there's uncertainty.
    if isDeterministic:
        return "moderate"
    return "variable"


# Effects whose output hinges on live game outcomes the projection can't
# directly forecast (comebacks, walk-offs, the final team outcome when
# win prob is ambiguous, etc.). Cards in this set are classified as
# 'variable' rather than 'moderate' when they project to zero.
_OUTCOME_SENSITIVE_EFFECTS = frozenset({
    # Team-outcome gated
    "bandwagon", "fairweather_fan", "bandwagon_express",
    "upset_special", "comeback_kid", "walk_off", "gone_streaking",
    # Game-event gated
    "highlight_reel", "closer", "big_deal", "spectacle", "showoff",
    # Player-threshold / conditional
    "domination", "deep_threat", "bombs_away", "workhorse",
    "target_share", "good_neighbor",
})


def _isDeterministicGivenProjection(effectName: str, effectConfig: Optional[dict]) -> bool:
    """True if this card's output is fully determined by current state +
    projected roster averages — no hidden dice, no game-outcome sensitivity.
    """
    ec = effectConfig or {}
    if ec.get("isChanceEffect") or (ec.get("primary", {}) or {}).get("isChanceEffect"):
        return False
    return effectName not in _OUTCOME_SENSITIVE_EFFECTS


# Effects whose output is fully determined by state we already know for
# certain — balances, swap counts, season tallies, ELO thresholds, roster
# composition. For these the projected number IS the number. Everything
# else that isn't chance/outcome-sensitive is 'estimated' — based on
# per-player stat averages that naturally vary game-to-game.
_EXACT_EFFECTS = frozenset({
    # Fixed-value
    "freebie",
    # Balance / currency based
    "opulence", "fat_cat", "surplus",
    # Swap counts
    "vagabond", "stockpiler",
    # Team ELO / record based
    "pedigree", "underdog", "martyr",
    # Roster composition based
    "dark_horse", "home_alone",
    # Kicker season tally
    "good_neighbor",
    # Streak-counter based (use streak_count from equip, not stats)
    "bonsai",
})


def _certaintyOf(effectName: str, effectConfig: Optional[dict], hasOdds: bool) -> str:
    """Classify how confident the projected number is:
      'contingent' — has odds (chance / outcome-sensitive), already
                     rendered as "X% · Y" so certainty is redundant.
      'exact'      — number is derived from fully-known state.
      'estimated'  — number is derived from season averages that will
                     vary game-to-game (per-player yards, TDs, etc.).
    """
    if hasOdds:
        return "contingent"
    if effectName in _EXACT_EFFECTS:
        return "exact"
    ec = effectConfig or {}
    if ec.get("isChanceEffect") or (ec.get("primary", {}) or {}).get("isChanceEffect"):
        return "contingent"
    return "estimated"


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
        EquippedCard, UserCard, CardTemplate,
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
    favAvgBigPlays = 0.0  # per-game average, used as Highlight Reel forecast
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
            gamesPlayed = favStats.get('wins', 0) + favStats.get('losses', 0)
            if gamesPlayed > 0:
                favAvgBigPlays = favStats.get('bigPlays', 0) / gamesPlayed

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

    # Streak counts per equipped card — EquippedCard is keyed by
    # (user_id, season, week) in the DB, not a FantasyRoster relation.
    equipped = (
        session.query(EquippedCard)
        .filter(
            EquippedCard.user_id == userId,
            EquippedCard.season == season,
            EquippedCard.week == week,
        )
        .all()
    )
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
        # Projected per-game big plays for Highlight Reel — avg across
        # games the favorite team has played this season. Integer floor
        # so the card shows zero output if the team has yet to generate
        # a big play (rather than a confusing 0.3-weighted preview).
        favoriteTeamBigPlays=int(favAvgBigPlays),
        # Projection treats the game as "final" with the projected outcome
        # so effects like Pedigree / Comeback Kid / Upset Win don't bail
        # at the "waiting for game to end" guard. This is internally
        # consistent with favoriteTeamWonThisWeek above.
        favoriteTeamGameFinal=True,
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
    from database.models import FantasyRoster, EquippedCard

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

    equipped = (
        session.query(EquippedCard)
        .filter(
            EquippedCard.user_id == userId,
            EquippedCard.season == season,
            EquippedCard.week == week,
        )
        .all()
    )
    result = calculateWeekCardBonuses(equipped, ctx)
    # Happy-path run — every trigger fires, team wins, comeback happens.
    # Used to derive "if it hits" upside for odds display.
    optimisticResult = calculateWeekCardBonuses(equipped, _optimisticContext(ctx))
    optBySlot = {b.slotNumber: b for b in optimisticResult.cardBreakdowns}

    # Build a lookup: slotNumber → effect_config so we can pull chance
    # min/max ranges back out for the UI.
    configBySlot: Dict[int, dict] = {}
    for eq in equipped:
        ec = eq.user_card.card_template.effect_config or {}
        configBySlot[eq.slot_number] = ec

    cards: List[Dict[str, Any]] = []
    for b in result.cardBreakdowns:
        effectConfig = configBySlot.get(b.slotNumber)
        nullified = _detectNullified(b, ctx, effectConfig)
        isDeterministic = _isDeterministicGivenProjection(b.effectName, effectConfig)
        tier = _classifyEffectiveness(
            b.totalFP, b.floobitsEarned, b.primaryMult,
            nullified=nullified, isDeterministic=isDeterministic,
        )
        oddsInfo = _deriveOdds(b, effectConfig, optBySlot.get(b.slotNumber), ctx)
        certainty = _certaintyOf(b.effectName, effectConfig, oddsInfo is not None)
        rangeInfo = _computeRange(b, effectConfig, certainty)
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
            # Range describes the spread between a "cold" result (no
            # triggers) and a "hot" result (everything fires). None if
            # the card is deterministic given current projection inputs.
            "range": rangeInfo,
            # Odds replaces the generic "might trigger" label with a
            # concrete "X% chance · +Y FP if it hits" payload.
            "odds": oddsInfo,
            # 'exact' | 'estimated' | 'contingent' — how confident the
            # UI can be in the projected number (drives ~ prefix).
            "certainty": certainty,
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
    optimisticResult = calculateWeekCardBonuses([wrapped], _optimisticContext(ctx))
    if not result.cardBreakdowns:
        return None

    b = result.cardBreakdowns[0]
    optB = optimisticResult.cardBreakdowns[0] if optimisticResult.cardBreakdowns else None
    effectConfig = userCard.card_template.effect_config or {}
    nullified = _detectNullified(b, ctx, effectConfig)
    isDeterministic = _isDeterministicGivenProjection(b.effectName, effectConfig)
    tier = _classifyEffectiveness(
        b.totalFP, b.floobitsEarned, b.primaryMult,
        nullified=nullified, isDeterministic=isDeterministic,
    )
    oddsInfo = _deriveOdds(b, effectConfig, optB, ctx)
    certainty = _certaintyOf(b.effectName, effectConfig, oddsInfo is not None)
    rangeInfo = _computeRange(b, effectConfig, certainty)
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
        "range": rangeInfo,
        "odds": oddsInfo,
        "certainty": certainty,
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


def _detectNullified(breakdown, ctx: CardCalcContext, effectConfig: Optional[dict]) -> bool:
    """Return True when the card is proven dead this week — the trigger is
    structurally unreachable given current state, not merely uncertain.

    Conservative by design: if anything could still break the right way
    (team could win, random roll could hit, conditional event could
    happen), we prefer 'variable' over 'nullified'. Cards that return
    positive output are never nullified.
    """
    if breakdown.totalFP > 0 or breakdown.floobitsEarned > 0 or breakdown.primaryMult > 0:
        return False

    # Chance cards can always break the other way — never nullified.
    ec = effectConfig or {}
    if ec.get("isChanceEffect") or (ec.get("primary", {}) or {}).get("isChanceEffect"):
        return False

    # Streak cards are only nullified when the reset condition can't be
    # met this week AND the current streak is worthless. For weekly
    # accumulators the count is meaningful, so don't null those.
    effectName = breakdown.effectName
    try:
        from managers.cardEffects import STREAK_CONFIGS
        if effectName in STREAK_CONFIGS:
            cfg = STREAK_CONFIGS.get(effectName, {})
            if cfg.get("isWeekly"):
                return False
            # Reset conditions that are already resolvable pre-game and
            # would clearly fail this week.
            resetCondition = cfg.get("resetCondition", "equipped")
            if resetCondition == "favorite_team_wins" and ctx.favoriteTeamWinProb < 0.25:
                return True
    except Exception:
        pass

    return False


def _optimisticContext(ctx: CardCalcContext) -> CardCalcContext:
    """Clone a projection context and flip every game-outcome knob to its
    happy path — team wins, comeback happens, walk-off happens, every
    chance card triggers. Used to compute 'if it hits' upside for the
    odds display. Leaves deterministic fields (roster stats, ELOs)
    untouched.
    """
    # dataclasses.replace keeps references to the same dicts — fine since
    # we don't mutate the deterministic fields here.
    from dataclasses import replace
    opt = replace(
        ctx,
        projectionVariant='optimistic',
        favoriteTeamWonThisWeek=True,
        favoriteTeamScoreMargin=max(ctx.favoriteTeamScoreMargin, 21),
        favoriteTeamComebackWin=True,
        favoriteTeamLargestDeficit=max(ctx.favoriteTeamLargestDeficit, 14),
        favoriteTeamWalkOffWin=True,
        favoriteTeamBigPlays=max(ctx.favoriteTeamBigPlays, 2),
        favoriteTeamGameFinal=True,
    )
    # teamResults needs the favorite team flipped to 'won'. Copy the map
    # so the original expected-path dict isn't mutated.
    if ctx.userFavoriteTeamId:
        opt.teamResults = dict(ctx.teamResults or {})
        opt.teamResults[ctx.userFavoriteTeamId] = True
    return opt


def _deriveOdds(
    breakdown, effectConfig: Optional[dict],
    optimisticBreakdown, ctx: CardCalcContext,
) -> Optional[Dict[str, Any]]:
    """Produce odds metadata the UI can render as 'X% · +Y FP'.

    Returns None for deterministic cards (expected output already tells
    the full story). Non-None payload includes the probability the card
    hits its upside and what the output looks like on that path.
    """
    if optimisticBreakdown is None:
        return None

    ec = effectConfig or {}
    primary = ec.get("primary", {}) or {}
    isChance = ec.get("isChanceEffect") or primary.get("isChanceEffect")

    # Probability of the upside path
    if isChance:
        probability = breakdown.chanceThreshold or 0.0
    elif breakdown.effectName in _OUTCOME_SENSITIVE_EFFECTS:
        probability = ctx.favoriteTeamWinProb
    else:
        return None

    ifHitsFP = round(float(optimisticBreakdown.totalFP), 2)
    ifHitsFloobits = int(optimisticBreakdown.floobitsEarned)
    ifHitsMult = round(float(optimisticBreakdown.primaryMult), 2) if optimisticBreakdown.primaryMult > 0 else 0.0
    hasUpside = (
        ifHitsFP > (breakdown.totalFP or 0) + 0.01
        or ifHitsFloobits > (breakdown.floobitsEarned or 0)
        or ifHitsMult > (breakdown.primaryMult or 0) + 0.01
    )
    if not hasUpside:
        return None

    return {
        "probability": round(float(probability), 3),
        "ifHitsFP": ifHitsFP,
        "ifHitsFloobits": ifHitsFloobits,
        "ifHitsMult": ifHitsMult,
        "outputType": optimisticBreakdown.outputType,
    }


_STATS_ESTIMATE_BAND = 0.25  # ±25% band applied to projected FP values


def _computeRange(breakdown, effectConfig: Optional[dict], certainty: str) -> Optional[Dict[str, Any]]:
    """Return range metadata for the UI when the card's output genuinely
    swings. Three sources:
      'random_roll'     — RNG-style cards with explicit min/max bounds
      'chance'          — chance cards with base/enhanced split
      'stats_estimate'  — estimated-from-averages FP cards; ±25% band
                          around the projected value
    Returns None for exact deterministic cards so the UI shows a single
    number.
    """
    ec = effectConfig or {}
    primary = ec.get("primary", {}) or {}
    outputType = breakdown.outputType

    # 1. RNG-style cards — range is declared right on the primary
    if breakdown.effectName == "rng":
        lo = float(primary.get("minFP", 0))
        hi = float(primary.get("maxFP", 0))
        if hi > lo:
            return {
                "min": round(lo, 2), "max": round(hi, 2),
                "triggerChance": None,
                "outputType": "fp",
                "source": "random_roll",
            }

    # 2. Chance cards — base vs. enhanced outputs on trigger
    isChance = ec.get("isChanceEffect") or primary.get("isChanceEffect")
    if isChance:
        if outputType == "fp":
            lo = primary.get("baseFP", 0)
            hi = primary.get("enhancedFP", lo)
        elif outputType == "floobits":
            lo = primary.get("baseFloobits", 0)
            hi = primary.get("enhancedFloobits", lo)
        elif outputType == "mult":
            lo = primary.get("baseMult", 1)
            hi = primary.get("enhancedMult", lo)
        else:
            lo, hi = 0, 0
        if hi != lo:
            triggerChance = (
                round(float(breakdown.chanceThreshold), 3)
                if breakdown.chanceThreshold > 0 else None
            )
            return {
                "min": round(float(lo), 2),
                "max": round(float(hi), 2),
                "triggerChance": triggerChance,
                "outputType": outputType,
                "source": "chance",
            }

    # 3. Stat-estimated cards — band the projected FP value since season
    # averages smooth over real week-to-week variance. Only for FP cards
    # with meaningful output; mult/floobit estimates show the point value.
    if certainty == "estimated" and outputType == "fp" and breakdown.totalFP > 0.5:
        center = float(breakdown.totalFP)
        lo = round(center * (1 - _STATS_ESTIMATE_BAND), 1)
        hi = round(center * (1 + _STATS_ESTIMATE_BAND), 1)
        return {
            "min": lo, "max": hi,
            "triggerChance": None,
            "outputType": "fp",
            "source": "stats_estimate",
        }

    return None


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
