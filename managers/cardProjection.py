"""Card payout projections — estimates what each equipped (or candidate)
card will output this week given the user's roster and hand composition.

Two flavors of projection payload:

  • Output cards (the majority) — show the card's own projected FP, FPx,
    or Floobits output. We run the live calculator in projection mode
    (chance cards scaled by trigger probability, outcome booleans set
    to the most-likely path) and return its per-card breakdown.

  • Amplifier cards (Bonus Round, Providence, Catalyst, Advantage,
    Cascade, Lemons, Chain Reaction, Copycat) — these don't
    produce meaningful output in isolation; their value comes from
    what OTHER equipped cards do. For these we emit a descriptive
    status that checks whether the required companion cards are
    actually in the hand — e.g., "Boosts chance cards" when a
    chance card is equipped alongside, "No effect — no chance cards
    equipped" when not.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional, Tuple

from managers.cardEffectCalculator import CardCalcContext, calculateWeekCardBonuses

logger = logging.getLogger("floosball")


# Effects whose projected output is fully derived from known state —
# balances, swap counts, ELO thresholds, streak counts, season tallies,
# roster composition. For these, the projected number IS exact.
# Anything not in this set and not an amplifier is treated as an
# estimate (chance roll or per-player season average).
_EXACT_EFFECTS = frozenset({
    # Fixed-value reward, ignores context
    "freebie", "big_deal", "allowance",
    # Balance / currency based (balance is known)
    "opulence", "fat_cat", "surplus",
    # Swap counts
    "vagabond", "stockpiler",
    # Team ELO / record based (ELO is known)
    "pedigree", "underdog", "martyr", "juggernaut",
    # Roster composition / hand composition (known)
    "dark_horse", "home_alone", "diversified",
    # Season-tally based
    "good_neighbor",
    # Streak / week-counter based (known state)
    "bonsai", "trust_fund",
    # New roster-trait effects — all deterministic from current roster
    # state (no RNG, no per-player stat scaling). Adding so the UI shows
    # the value without an "est." prefix and dead states render as a
    # clean red "+0 FP" rather than a misleading "est. +X" placeholder.
    "patient", "wanderer", "castaway", "rookie_hype",
    # Reworked roster-trait cards (read off prior-season standings and
    # current top-6 — both deterministic at lock time).
    "comeback_kid", "domination", "walk_off",
    # Fav-team-wins accumulator + per-5★-roster-player — both visible at lock.
    # Eminence reads the position leaderboard which is also visible at lock.
    "believe", "showoff", "eminence",
    # FPx-converted "per roster player" cards — counts known at lock (Homer)
    # or known at week-end (Honor Roll).
    "homer", "honor_roll",
    # Roster-construction-driven new cards — counts determinable at lock
    # (Synergy/Vanguard/Loyalty/Cornerstone) or from per-player weekly stats (Range).
    "synergy", "vanguard", "range", "loyalty", "cornerstone",
    # Hand-composition effects (count of flat-FP cards in hand)
    "anthem",
    # Inverse-streak / streak effects with known streak counts
    "sandbagger", "quiet_storm", "drought", "nose_picker",
    # Pickem-driven (deterministic once weekly pickem totals are known;
    # show 0 with explanatory equation during the games window)
    "medium", "parlay",
})


# ── Amplifier registry ────────────────────────────────────────────────

def _effectName(eq) -> str:
    try:
        return (eq.user_card.card_template.effect_config or {}).get("effectName", "")
    except Exception:
        return ""


def _effectConfig(eq) -> dict:
    try:
        return eq.user_card.card_template.effect_config or {}
    except Exception:
        return {}


def _outputTypeOf(eq) -> str:
    ec = _effectConfig(eq)
    return ec.get("outputType") or "fp"


def _isChanceEffect(eq) -> bool:
    ec = _effectConfig(eq)
    primary = ec.get("primary", {}) or {}
    return bool(ec.get("isChanceEffect") or primary.get("isChanceEffect"))


def _hasOther(hand, self_eq, predicate: Callable[[Any], bool]) -> bool:
    return any(predicate(eq) for eq in hand if eq is not self_eq)


# Dependency checks — evaluated against the full equipped hand so the
# amplifier knows whether its companions are actually present.
_AMPLIFIER_DEPENDS = {
    "bonus_round":   lambda hand, self_eq: len(hand) - (1 if self_eq in hand else 0) >= 1,
    "copycat":       lambda hand, self_eq: len(hand) - (1 if self_eq in hand else 0) >= 1,
    "chain_reaction": lambda hand, self_eq: len(hand) - (1 if self_eq in hand else 0) >= 1,
    "double_down":   lambda hand, self_eq: len(hand) - (1 if self_eq in hand else 0) >= 1,
    "providence":    lambda hand, self_eq: _hasOther(hand, self_eq, _isChanceEffect),
    "catalyst":      lambda hand, self_eq: _hasOther(hand, self_eq, _isChanceEffect),
    "advantage":     lambda hand, self_eq: _hasOther(hand, self_eq, _isChanceEffect),
    "conductor":     lambda hand, self_eq: _hasOther(hand, self_eq, lambda e: _outputTypeOf(e) == "fp"),
    # Diamond stat amplifiers — always "active" if any other card is equipped
    # (the multiplier propagates through ctx mutation regardless of which
    # other cards happen to read TDs/yards/FGs).
    "doubler":       lambda hand, self_eq: len(hand) - (1 if self_eq in hand else 0) >= 1,
    "surveyor":      lambda hand, self_eq: len(hand) - (1 if self_eq in hand else 0) >= 1,
    "sharpshooter":  lambda hand, self_eq: len(hand) - (1 if self_eq in hand else 0) >= 1,
}


def _lemonsBoostFP(primary: dict, breakdowns) -> float:
    """Compute the actual FP boost Lemons added this week. The calculator's
    second pass marks the mutated card by appending '(Lemons)' to its
    equation, so we identify it by that marker (the original-lowest card may
    no longer be the post-mutation lowest)."""
    if not breakdowns:
        return 0.0
    multValue = float(primary.get("rewardValue", 0) or 0)
    if multValue <= 1:
        return 0.0
    target = next(
        (b for b in breakdowns
         if getattr(b, 'effectName', '') != 'double_down'
         and '(Lemons)' in (getattr(b, 'equation', '') or '')),
        None,
    )
    if target is None:
        return 0.0
    postFP = float(target.totalFP)
    # postFP = originalFP × multValue → bonus = postFP × (multValue-1)/multValue
    return round(postFP * (multValue - 1) / multValue, 1)


def _amplifierDescription(effectName: str, primary: dict, active: bool, breakdowns=None) -> str:
    """Short status string for amplifier pills. When active, describes
    what the card is doing right now given the hand. When inactive,
    names the missing companion type so the user knows how to fix it.
    """
    if effectName == "bonus_round":
        reward = primary.get("rewardValue", 0)
        return f"+{reward} FP at 4+ triggers" if active else "Needs 4+ triggers"
    if effectName == "copycat":
        return "Copies best card" if active else "Nothing to copy"
    if effectName == "chain_reaction":
        return "Chains triggered cards" if active else "Needs triggers"
    if effectName == "double_down":
        if not active:
            return "Needs another card"
        boost = _lemonsBoostFP(primary, breakdowns)
        if boost > 0:
            return f"+{boost} FP on lowest card"
        # Fallback when we can't compute a boost (no breakdowns yet)
        reward = primary.get("rewardValue", 0)
        return f"{reward}x lowest-earning card"
    if effectName == "providence":
        bonus = int(round((primary.get("chanceBonus", 0) or 0) * 100))
        return f"+{bonus}% to chance cards" if active else "Needs chance card"
    if effectName == "catalyst":
        return "Roster-FP chance boost" if active else "Needs chance card"
    if effectName == "advantage":
        return "Chance rolls twice" if active else "Needs chance card"
    if effectName == "conductor":
        boost = primary.get("boostPct", 20)
        return f"+{boost}% to flat-FP cards" if active else "Needs flat-FP card"
    if effectName == "doubler":
        return "TDs count 2x for other cards" if active else "Needs another card"
    if effectName == "surveyor":
        return "Yards count 1.5x for other cards" if active else "Needs another card"
    if effectName == "sharpshooter":
        return "FGs count 2x for other cards" if active else "Needs another card"
    return ""


def _amplifierStatus(eq, hand, breakdowns=None) -> Optional[Dict[str, Any]]:
    """If this card is an amplifier, return its descriptive status. Otherwise None.

    Pass `breakdowns` (list of CardBreakdown) to let amplifiers like Lemons
    compute their actual FP impact based on the equipped hand's projected
    output, rather than just showing the static multiplier.
    """
    effectName = _effectName(eq)
    check = _AMPLIFIER_DEPENDS.get(effectName)
    if not check:
        return None
    primary = (_effectConfig(eq).get("primary", {}) or {})
    active = bool(check(hand, eq))
    return {
        "description": _amplifierDescription(effectName, primary, active, breakdowns),
        "active": active,
    }


# ── Stat / context helpers ────────────────────────────────────────────

def _perGameAverageStats(row) -> Optional[dict]:
    from managers.fantasyTracker import _dbStatsToCardFormat
    if not row or (getattr(row, 'games_played', 0) or 0) == 0:
        return None
    gp = max(row.games_played, 1)

    def _avg(d):
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


def _lookupPriorSeasonMissedPlayoffTeams(session, season: int) -> set:
    """Set of team_ids that missed playoffs in the previous season. Used by
    Comeback Kid. Empty for season 1."""
    if season <= 1:
        return set()
    try:
        from database.models import TeamSeasonStats
        rows = session.query(TeamSeasonStats.team_id).filter(
            TeamSeasonStats.season == season - 1,
            TeamSeasonStats.made_playoffs == False,  # noqa: E712
        ).all()
        return {r.team_id for r in rows}
    except Exception:
        return set()


def _lookupCurrentTop6Teams(session, season: int) -> set:
    """Set of team_ids currently top-6 by record *within their league*. Used
    by Domination. Both leagues' top-6 are unioned together — the playoff
    cut, basically."""
    try:
        from database.models import TeamSeasonStats, Team as _Team
        from collections import defaultdict
        rows = (
            session.query(_Team.league_id, TeamSeasonStats.team_id,
                          TeamSeasonStats.wins, TeamSeasonStats.win_percentage)
            .join(_Team, _Team.id == TeamSeasonStats.team_id)
            .filter(TeamSeasonStats.season == season)
            .all()
        )
        byLeague = defaultdict(list)
        for leagueId, teamId, wins, wp in rows:
            byLeague[leagueId].append((wp or 0.0, wins or 0, teamId))
        result = set()
        for entries in byLeague.values():
            entries.sort(key=lambda x: (x[0], x[1]), reverse=True)
            for _wp, _w, tid in entries[:6]:
                result.add(tid)
        return result
    except Exception:
        return set()


def _winProbabilityFromElo(favElo: float, oppElo: float) -> float:
    try:
        return 1.0 / (1.0 + 10 ** ((oppElo - favElo) / 400.0))
    except Exception:
        return 0.5


def _findUpcomingOpponent(session, favTeamId, season, week, teamManager) -> Tuple[float, str]:
    from database.models import Game
    if not favTeamId:
        return 1500.0, ""
    upcoming = (
        session.query(Game).filter(
            Game.season == season, Game.week >= week, Game.status != 'final',
        ).filter(
            (Game.home_team_id == favTeamId) | (Game.away_team_id == favTeamId)
        ).order_by(Game.week, Game.id).first()
    )
    if upcoming is None or not teamManager:
        return 1500.0, ""
    oppId = (upcoming.away_team_id if upcoming.home_team_id == favTeamId else upcoming.home_team_id)
    opp = teamManager.getTeamById(oppId)
    if not opp:
        return 1500.0, ""
    return getattr(opp, 'elo', 1500.0), getattr(opp, 'abbr', '') or getattr(opp, 'name', '')


def buildProjectionContext(session, userId, season, week, seasonManager, playerManager) -> Optional[CardCalcContext]:
    from database.models import (
        FantasyRoster, PlayerSeasonStats,
        User, UserCurrency, WeeklyModifier, FantasyRosterSwap,
        EquippedCard,
    )
    from managers.cardEffectCalculator import computeEminenceData

    roster = session.query(FantasyRoster).filter_by(user_id=userId, season=season).first()
    if not roster:
        return None
    # Fusion: the roster IS the equipped cards, so the projected lineup = the
    # players DEPICTED by the equipped cards for the week (not FantasyRosterPlayer
    # rows). Keep a per-card list so a player depicted by two cards is counted
    # per-card, matching the live/week-end paths.
    equipped = (session.query(EquippedCard)
                .filter(EquippedCard.user_id == userId,
                        EquippedCard.season == season,
                        EquippedCard.week == week)
                .all())
    depictedPairs = [(eq, eq.user_card.card_template.player_id) for eq in equipped]
    rosterPlayerIds = {pid for _eq, pid in depictedPairs}
    if not rosterPlayerIds:
        return None
    # Loyalty snapshot — original roster from first save.
    initialRosterPlayerIds = set()
    if roster.initial_player_ids:
        try:
            import json as _json
            initialRosterPlayerIds = {int(pid) for pid in _json.loads(roster.initial_player_ids)}
        except Exception:
            initialRosterPlayerIds = set()

    statRows = (session.query(PlayerSeasonStats)
                .filter(PlayerSeasonStats.season == season,
                        PlayerSeasonStats.player_id.in_(rosterPlayerIds))
                .all())
    rowByPlayer = {r.player_id: r for r in statRows}

    weekPlayerStats = {}
    weekRawFP = 0.0
    rosterTotalTds = 0.0
    rosterPlayerNames = {}
    rosterPlayerRatings = {}
    rosterPlayerPositions = {}
    rosterPlayerTeamIds = {}
    playerSeasonFPPerGame = {}

    for _eq, pid in depictedPairs:
        dbPlayer = playerManager.getPlayerById(pid) if playerManager else None
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
        avg = _perGameAverageStats(row) or {
            "teamId": rosterPlayerTeamIds.get(pid, 0),
            "fantasyPoints": 0,
            "passing_stats": {"passYards": 0, "tds": 0},
            "rushing_stats": {"runYards": 0, "runTds": 0, "carries": 0},
            "receiving_stats": {"rcvYards": 0, "rcvTds": 0, "receptions": 0, "yac": 0, "longest": 0},
            "kicking_stats": {"fgs": 0, "fgAtt": 0, "fgYards": 0, "longest": 0, "fg40plus": 0},
        }
        weekPlayerStats[pid] = avg
        weekRawFP += avg.get("fantasyPoints", 0)
        rosterTotalTds += (
            (avg.get("passing_stats", {}) or {}).get("tds", 0)
            + (avg.get("rushing_stats", {}) or {}).get("runTds", 0)
            + (avg.get("receiving_stats", {}) or {}).get("rcvTds", 0)
        )
        if row:
            playerSeasonFPPerGame[pid] = (row.fantasy_points or 0) / max(row.games_played, 1)

    dbUser = session.get(User, userId)
    favTeamId = dbUser.favorite_team_id if dbUser else None

    teamManager = None
    try:
        teamManager = seasonManager.serviceContainer.getService('team_manager')
    except Exception:
        pass

    favElo = 1500.0
    favStreak = favPriorStreak = favPeakStreak = 0
    favSeasonLosses = favSeasonUpsetWins = favSeasonWins = 0
    favAvgBigPlays = 0.0
    favInPlayoffs = False
    if favTeamId and teamManager:
        favTeam = teamManager.getTeamById(favTeamId)
        if favTeam:
            favElo = getattr(favTeam, 'elo', 1500.0)
            favStats = getattr(favTeam, 'seasonTeamStats', {}) or {}
            favStreak = favStats.get('streak', 0)
            favPriorStreak = favStats.get('priorStreak', favStreak)
            favPeakStreak = favStats.get('peakStreak', abs(favStreak))
            favSeasonLosses = favStats.get('losses', 0)
            favSeasonWins = favStats.get('wins', 0)
            favSeasonUpsetWins = favStats.get('upsetWins', 0)
            gp = favStats.get('wins', 0) + favStats.get('losses', 0)
            if gp > 0:
                favAvgBigPlays = favStats.get('bigPlays', 0) / gp
            # Playoff position — top half of the team's league by the
            # same seeding used in the live fantasy calc.
            try:
                if seasonManager and getattr(seasonManager, 'leagueManager', None):
                    teamLeague = seasonManager.leagueManager.getTeamLeague(favTeam)
                    if teamLeague:
                        standings = teamLeague.getStandings()
                        cutoff = max(1, len(standings) // 2)
                        for idx, entry in enumerate(standings):
                            if entry.get('team') == favTeam:
                                favInPlayoffs = idx < cutoff
                                break
            except Exception:
                pass

    oppElo, oppName = _findUpcomingOpponent(session, favTeamId, season, week, teamManager)
    winProb = _winProbabilityFromElo(favElo, oppElo)

    leagueAverageElo = 1500.0
    if teamManager and teamManager.teams:
        leagueAverageElo = sum(getattr(t, 'elo', 1500.0) for t in teamManager.teams) / len(teamManager.teams)

    teamResults = {favTeamId: winProb > 0.5} if favTeamId else {}

    # FLEX slot detection — mirrors the fantasyTracker logic. Fusion: a card
    # equipped in the FLEX slot means the slot is in play; the entitlement checks
    # below (champion card / temp_flex powerup) cover the unlocked-but-empty case.
    hasFlexSlot = any(getattr(eq, 'slot', '') == 'FLEX' for eq in equipped)
    if not hasFlexSlot:
        try:
            from database.models import ShopPurchase as _SP
            for eq in equipped:
                uc = getattr(eq, 'user_card', None)
                tmpl = getattr(uc, 'card_template', None) if uc else None
                cls = getattr(tmpl, 'classification', None) or ''
                if 'champion' in cls:
                    hasFlexSlot = True
                    break
            if not hasFlexSlot:
                activeFlex = session.query(_SP).filter(
                    _SP.user_id == userId,
                    _SP.season == season,
                    _SP.item_slug == 'temp_flex',
                    _SP.expires_at_week >= week,
                ).first()
                if activeFlex:
                    hasFlexSlot = True
        except Exception:
            pass
    streakCounts = {eq.id: getattr(eq, 'streak_count', 1) for eq in equipped}
    # Peak-decay state — projection mirrors the live computation so the
    # pill shows the decaying tail when a streak's broken, not just base.
    streakPeakOutputs = {
        eq.id: float(eq.peak_output) for eq in equipped
        if getattr(eq, 'peak_output', None) is not None
    }
    streakWeeksSinceBreak = {
        eq.id: int(getattr(eq, 'weeks_since_break', 0) or 0) for eq in equipped
    }
    # Roster-trait card data (Castaway, Rookie Hype) — projection uses the
    # same lookups as live calc so the pill reflects what they'll pay.
    teamRecords = {}
    if teamManager:
        for team in teamManager.teams:
            stats = getattr(team, 'seasonTeamStats', {}) or {}
            wp = stats.get('winPerc')
            if wp is None:
                w = stats.get('wins', 0) or 0
                l = stats.get('losses', 0) or 0
                wp = w / (w + l) if (w + l) > 0 else 0.5
            teamRecords[team.id] = float(wp)
    rosterRookieFlags = {}
    rosterSeasonsPlayed = {}
    if playerManager:
        for pid in rosterPlayerIds:
            player = playerManager.getPlayerById(pid)
            if player:
                # Rookie = canonical "Rookie" service tier, which the game
                # applies for the first 2 seasons of play (seasonsPlayed
                # 0 or 1). Matches what shows on the player card and what
                # users see as "Rookie".
                svc = getattr(player, 'serviceTime', None)
                isRookieSvc = bool(svc and getattr(svc, 'name', '') == 'Rookie')
                sp = getattr(player, 'seasonsPlayed', 0) or 0
                rosterSeasonsPlayed[pid] = sp
                rosterRookieFlags[pid] = bool(isRookieSvc or sp <= 1)

    # Pick-em stats — drives Nose Picker (Conviction), Medium (Augur),
    # Parlay (Tipster). Projection mode estimates forward:
    #   - Current week (live or already resolved): use those rows directly.
    #   - Otherwise: average the user's historical resolved weeks this
    #     season. New users with no history fall back to plausible
    #     defaults (70% accuracy, ~60 weekly pts, manual submission).
    userManualPickSubmittedThisWeek = True
    userWeeklyPickemCorrect = 0
    userWeeklyPickemTotal = 0
    userWeeklyPickemPoints = 0
    try:
        from database.models import PickEmPick
        weekPicks = session.query(PickEmPick).filter_by(
            user_id=userId, season=season, week=week,
        ).all()
        hasLiveData = bool(weekPicks) and any(p.correct is not None for p in weekPicks)
        if hasLiveData:
            userManualPickSubmittedThisWeek = any(not p.is_auto for p in weekPicks)
            for p in weekPicks:
                if p.correct is True:
                    userWeeklyPickemCorrect += 1
                    userWeeklyPickemTotal += 1
                elif p.correct is False:
                    userWeeklyPickemTotal += 1
                userWeeklyPickemPoints += int(p.points_earned or 0)
        else:
            # Use historical averages from prior weeks this season
            priorPicks = session.query(PickEmPick).filter(
                PickEmPick.user_id == userId,
                PickEmPick.season == season,
                PickEmPick.week < week,
                PickEmPick.correct.isnot(None),
            ).all()
            if priorPicks:
                # Manual-submit projection: extend prior behavior unless
                # the user has switched to auto-pick lately
                weeksByNum: Dict[int, list] = {}
                for p in priorPicks:
                    weeksByNum.setdefault(p.week, []).append(p)
                manualWeeks = sum(
                    1 for wk_picks in weeksByNum.values()
                    if any(not p.is_auto for p in wk_picks)
                )
                userManualPickSubmittedThisWeek = manualWeeks >= max(1, len(weeksByNum) // 2)

                correct = sum(1 for p in priorPicks if p.correct is True)
                total = len(priorPicks)
                # Project current-week values by scaling accuracy to the
                # number of games this week (assume same picks-per-week
                # the user has been getting on average).
                avgPicksPerWeek = total / max(1, len(weeksByNum))
                projectedTotal = round(avgPicksPerWeek)
                projectedAccuracy = correct / total if total else 0.7
                userWeeklyPickemCorrect = round(projectedAccuracy * projectedTotal)
                userWeeklyPickemTotal = projectedTotal
                avgPoints = sum(int(p.points_earned or 0) for p in priorPicks) / max(1, len(weeksByNum))
                userWeeklyPickemPoints = round(avgPoints)
            else:
                # No history: fall back to league-typical estimates so the
                # projection isn't pinned to 0.
                userWeeklyPickemCorrect = 8
                userWeeklyPickemTotal = 12
                userWeeklyPickemPoints = 60
    except Exception:
        pass

    lastSwap = (session.query(FantasyRosterSwap.swap_week)
                .filter_by(roster_id=roster.id)
                .order_by(FantasyRosterSwap.swap_week.desc()).first())
    rosterUnchangedWeeks = week if not lastSwap else max(0, week - lastSwap[0])
    seasonSwapsUsed = session.query(FantasyRosterSwap).filter_by(roster_id=roster.id).count()

    activeModifier = ""
    try:
        modRow = session.query(WeeklyModifier).filter_by(season=season, week=week).first()
        if modRow:
            activeModifier = modRow.modifier_type or ""
    except Exception:
        pass

    userFloobitsBalance = 0
    try:
        cc = session.query(UserCurrency).filter_by(user_id=userId).first()
        if cc:
            userFloobitsBalance = cc.balance or 0
    except Exception:
        pass

    playerPerfRatings = {}
    if playerManager:
        for p in playerManager.activePlayers:
            pr = getattr(p, 'seasonPerformanceRating', 0) or 0
            if pr > 0:
                playerPerfRatings[p.id] = pr

    try:
        positionAvgFPs, _, top10PerPosition, top1PerPosition = computeEminenceData(session, season, week)
    except Exception:
        positionAvgFPs = {}
        top10PerPosition = {}
        top1PerPosition = {}

    kickerSeasonFgMisses = 0
    for pid in rosterPlayerIds:
        row = rowByPlayer.get(pid)
        if not row:
            continue
        ks = row.kicking_stats or {}
        fgAtt, fgs = ks.get('fgAtt', 0) or 0, ks.get('fgs', 0) or 0
        if fgAtt > fgs:
            kickerSeasonFgMisses += (fgAtt - fgs)
            break

    return CardCalcContext(
        isProjection=True,
        favoriteTeamWinProb=winProb,
        projectionVariant='expected',
        userId=userId, season=season, weekNumber=week,
        gamesActive=False,
        chanceBonus=0.0,
        kickerSeasonFgMisses=kickerSeasonFgMisses,
        rosterPlayerIds=rosterPlayerIds,
        weekPlayerStats=weekPlayerStats,
        weekRawFP=weekRawFP,
        rosterPlayerRatings=rosterPlayerRatings,
        rosterTotalTds=int(round(rosterTotalTds)),
        rosterPlayerPositions=rosterPlayerPositions,
        streakCounts=streakCounts,
        streakPeakOutputs=streakPeakOutputs,
        streakWeeksSinceBreak=streakWeeksSinceBreak,
        _teamRecords=teamRecords,
        _rosterRookieFlags=rosterRookieFlags,
        _rosterSeasonsPlayed=rosterSeasonsPlayed,
        initialRosterPlayerIds=initialRosterPlayerIds,
        userManualPickSubmittedThisWeek=userManualPickSubmittedThisWeek,
        userWeeklyPickemCorrect=userWeeklyPickemCorrect,
        userWeeklyPickemTotal=userWeeklyPickemTotal,
        userWeeklyPickemPoints=userWeeklyPickemPoints,
        userFavoriteTeamId=favTeamId,
        favoriteTeamElo=favElo,
        leagueAverageElo=leagueAverageElo,
        favoriteTeamStreak=favStreak,
        favoriteTeamPriorStreak=favPriorStreak,
        favoriteTeamPeakStreak=favPeakStreak,
        favoriteTeamSeasonLosses=favSeasonLosses,
        favoriteTeamSeasonWins=favSeasonWins,
        favoriteTeamInPlayoffs=favInPlayoffs,
        favoriteTeamWonThisWeek=(winProb > 0.5),
        favoriteTeamOpponentElo=oppElo,
        favoriteTeamOpponentName=oppName,
        favoriteTeamBigPlays=int(favAvgBigPlays),
        favoriteTeamGameFinal=True,
        favoriteTeamSeasonUpsetWins=favSeasonUpsetWins,
        rosterUnchangedWeeks=rosterUnchangedWeeks,
        teamResults=teamResults,
        playerPerformanceRatings=playerPerfRatings,
        # Use season performance ratings as the per-game projection —
        # gives outcome-sensitive cards (Indemnity, Showoff, Closer)
        # a sensible stand-in so they don't bail at the
        # "Waiting for games to complete" guard.
        gamePerformanceRatings=dict(playerPerfRatings),
        rosterPlayerTeamIds=rosterPlayerTeamIds,
        rosterPlayerNames=rosterPlayerNames,
        favoriteTeamScoreMargin=0,
        favoriteTeamComebackWin=False,
        favoriteTeamLargestDeficit=0,
        favoriteTeamWalkOffWin=False,
        priorSeasonMissedPlayoffTeamIds=_lookupPriorSeasonMissedPlayoffTeams(session, season),
        currentTop6TeamIds=_lookupCurrentTop6Teams(session, season),
        activeModifier=activeModifier,
        unusedSwaps=(roster.swaps_available or 0) + (roster.purchased_swaps or 0),
        seasonSwapsUsed=seasonSwapsUsed,
        hasFlexSlot=hasFlexSlot,
        userFloobitsBalance=userFloobitsBalance,
        liveStreakConditionsMet={},
        positionAvgFPs=positionAvgFPs,
        playerSeasonFPPerGame=playerSeasonFPPerGame,
        top10PerPosition=top10PerPosition,
        top1PerPosition=top1PerPosition,
    )


# "Hot week" inflation factor applied to per-player stats to simulate a
# realistic top-quartile week. Picked by eye — typical real-world
# variance tends to land around 1.5–2× the season average on good weeks.
_PEAK_STAT_INFLATION = 1.75


def _peakContext(ctx: CardCalcContext) -> CardCalcContext:
    """Clone the projection context with every dial flipped to a
    realistic best-case: chance cards return their enhanced value (no
    EV scaling), per-player stats inflated to represent a hot week,
    favorite team wins with a blowout + comeback + walk-off. Used to
    derive the 'up to +Y FP' ceiling alongside the expected value.
    """
    from dataclasses import replace

    # Inflate per-player stats. Copy deep enough so we don't mutate
    # the expected-case ctx dicts.
    peakPlayerStats: Dict[int, dict] = {}
    for pid, stats in (ctx.weekPlayerStats or {}).items():
        newStats = dict(stats)
        for key in ("passing_stats", "rushing_stats", "receiving_stats", "kicking_stats"):
            block = newStats.get(key)
            if isinstance(block, dict):
                newBlock = {}
                for k, v in block.items():
                    if isinstance(v, (int, float)) and k != 'longest':
                        newBlock[k] = v * _PEAK_STAT_INFLATION
                    else:
                        newBlock[k] = v
                newStats[key] = newBlock
        if "fantasyPoints" in newStats and isinstance(newStats["fantasyPoints"], (int, float)):
            newStats["fantasyPoints"] = newStats["fantasyPoints"] * _PEAK_STAT_INFLATION
        peakPlayerStats[pid] = newStats

    peak = replace(
        ctx,
        projectionVariant='optimistic',
        weekPlayerStats=peakPlayerStats,
        weekRawFP=ctx.weekRawFP * _PEAK_STAT_INFLATION,
        rosterTotalTds=int(round(ctx.rosterTotalTds * _PEAK_STAT_INFLATION)),
        favoriteTeamWonThisWeek=True,
        favoriteTeamScoreMargin=max(ctx.favoriteTeamScoreMargin, 21),
        favoriteTeamComebackWin=True,
        favoriteTeamLargestDeficit=max(ctx.favoriteTeamLargestDeficit, 14),
        favoriteTeamWalkOffWin=True,
        favoriteTeamBigPlays=max(ctx.favoriteTeamBigPlays, 2),
        favoriteTeamGameFinal=True,
    )
    if ctx.userFavoriteTeamId:
        peak.teamResults = dict(ctx.teamResults or {})
        peak.teamResults[ctx.userFavoriteTeamId] = True
    return peak


# ── Payload shaping ────────────────────────────────────────────────────

def _shapeCardPayload(breakdown, amplifier: Optional[Dict[str, Any]], effectConfig: Optional[dict] = None,
                      peakBreakdown=None) -> Dict[str, Any]:
    """Convert a CardBreakdown + amplifier status into the UI payload.
    'kind' tells the UI how to render: 'output' = show FP/FPx/F number;
    'amplifier' = show descriptive status with active/inactive color.

    Start from the card's pre-match primary output (what the card
    description says) and apply the 1.5× match bonus when the card's
    player is on the roster. Match-multiplied numbers reflect what
    the card will actually produce given the current lineup.
    """
    kind = "amplifier" if amplifier is not None else "output"
    # Output cards are 'exact' when their formula reads only known
    # state (Vagabond swaps, Opulence balance, Pedigree ELO). Anything
    # else — chance rolls, per-player season averages — is an estimate
    # and gets an "est." prefix in the UI.
    estimated = (
        kind == "output"
        and breakdown.effectName not in _EXACT_EFFECTS
    )

    projectedFP = float(breakdown.preMatchFP)
    projectedFloobits = int(breakdown.preMatchFloobits)
    projectedMult = float(breakdown.preMatchMult) if breakdown.preMatchMult > 0 else 0.0

    primary = (effectConfig.get("primary", {}) or {}) if effectConfig else {}

    # For flat-output cards, read the number straight from the stored
    # primary config — the same source the card's description template
    # substitutes from. This guarantees the pill number equals what
    # the card text says, independent of any calc-time transformation.
    _FLAT_FP_PRIMARY_KEYS = {
        "freebie": "baseFP",
        "big_deal": "xMultValue",
        "allowance": "floobits",
    }
    flatKey = _FLAT_FP_PRIMARY_KEYS.get(breakdown.effectName)
    if flatKey and flatKey in primary:
        try:
            val = float(primary[flatKey])
            if breakdown.effectName == "big_deal":
                projectedMult = round(val, 2)
            elif breakdown.effectName == "allowance":
                projectedFloobits = int(round(val))
            else:
                projectedFP = round(val, 2)
        except Exception:
            pass

    # RNG cards use an effect-local seeded RNG (not the projection RNG),
    # so their breakdown number is whatever the seed produced this
    # week — often near the floor. Override with the expected value
    # (midpoint of the declared min/max range) so the pill reads as
    # the typical roll rather than this week's specific random hit.
    if breakdown.effectName == "rng" and primary:
        try:
            minFP = float(primary.get("minFP", 0))
            maxFP = float(primary.get("maxFP", 0))
            if maxFP > minFP:
                projectedFP = round((minFP + maxFP) / 2, 1)
        except Exception:
            pass

    # Snake Eyes outputs an FPx whose size is inverse to the lowest-FP
    # roster player's weekly score. Projection uses the actual mult the
    # compute produced (from real stats); otherwise estimates a typical
    # middle-tier multiplier assuming lowest ~5-9 FP.
    if breakdown.effectName == "snake_eyes" and primary:
        try:
            if float(breakdown.preMatchMult) > 1.0:
                projectedMult = round(float(breakdown.preMatchMult), 2)
            else:
                projectedMult = 1.5  # typical mid-tier (5-9 FP lowest)
        except Exception:
            pass

    # Chance cards: recompute as a proper expected-value blend of
    # base-floor × (1 - trigger_chance) + enhanced × trigger_chance.
    # The calculator's per-card scaling previously used `enhanced ×
    # threshold`, which can fall BELOW the guaranteed floor and makes
    # prismatic chance cards look weak. Reading base / enhanced /
    # effective-threshold straight from the breakdown + primary so
    # the pill reflects what you actually earn on average, accounting
    # for escalation modifiers (Providence, Catalyst, conditions).
    threshold = float(getattr(breakdown, 'chanceThreshold', 0) or 0)
    isChance = (
        bool(primary.get("isChanceEffect"))
        or (effectConfig or {}).get("isChanceEffect")
        or threshold > 0
    )
    if isChance and threshold > 0:
        try:
            if breakdown.outputType == "fp":
                base = float(primary.get("baseFP", 0))
                enh = float(primary.get("enhancedFP", base))
                projectedFP = round(base * (1 - threshold) + enh * threshold, 2)
            elif breakdown.outputType == "floobits":
                base = float(primary.get("baseFloobits", 0))
                enh = float(primary.get("enhancedFloobits", base))
                projectedFloobits = int(round(base * (1 - threshold) + enh * threshold))
            elif breakdown.outputType == "mult":
                base = float(primary.get("baseMult", 1))
                enh = float(primary.get("enhancedMult", base))
                projectedMult = round(base * (1 - threshold) + enh * threshold, 2)
        except Exception:
            pass

    # Peak / "hot week" ceiling — calc run against inflated stats +
    # optimistic variant (chance cards return enhanced value, team wins,
    # comeback/walk-off happen). For stats-scaling cards like Odometer
    # and Avalanche this rises well above expected; for flat / deter-
    # ministic cards it matches expected (no range shown).
    bestCaseFP = projectedFP
    bestCaseFloobits = projectedFloobits
    bestCaseMult = projectedMult
    if peakBreakdown is not None:
        bestCaseFP = max(projectedFP, round(float(peakBreakdown.preMatchFP), 2))
        bestCaseFloobits = max(projectedFloobits, int(peakBreakdown.preMatchFloobits))
        if peakBreakdown.preMatchMult > 0:
            bestCaseMult = max(projectedMult, round(float(peakBreakdown.preMatchMult), 2))
        # Chance cards: bestCase is the enhanced value from primary
        # (guaranteed ceiling when the roll hits).
        if isChance:
            try:
                if breakdown.outputType == "fp":
                    bestCaseFP = max(bestCaseFP, float(primary.get("enhancedFP", bestCaseFP)))
                elif breakdown.outputType == "floobits":
                    bestCaseFloobits = max(bestCaseFloobits, int(primary.get("enhancedFloobits", bestCaseFloobits)))
                elif breakdown.outputType == "mult":
                    bestCaseMult = max(bestCaseMult, float(primary.get("enhancedMult", bestCaseMult)))
            except Exception:
                pass

    # Match bonus — when the card's player is on the roster, the card
    # is worth its multiplier-applied value, not the raw description.
    # Apply the same way _computeCardPass does: FP and Floobits scaled
    # directly; mult's bonus portion (above 1) scaled to preserve the
    # "×1 means no effect" baseline.
    if breakdown.matchMultiplied:
        matchMult = getattr(breakdown, 'matchMultiplier', 1.5) or 1.5
        projectedFP = projectedFP * matchMult
        projectedFloobits = int(round(projectedFloobits * matchMult))
        if projectedMult > 1:
            projectedMult = 1 + (projectedMult - 1) * matchMult
        bestCaseFP = bestCaseFP * matchMult
        bestCaseFloobits = int(round(bestCaseFloobits * matchMult))
        if bestCaseMult > 1:
            bestCaseMult = 1 + (bestCaseMult - 1) * matchMult

    return {
        "slotNumber": breakdown.slotNumber,
        "effectName": breakdown.effectName,
        "displayName": breakdown.displayName,
        "kind": kind,
        "outputType": breakdown.outputType,
        "projectedFP": round(projectedFP, 2),
        "projectedFloobits": projectedFloobits,
        "projectedMult": round(projectedMult, 2),
        "bestCaseFP": round(bestCaseFP, 2),
        "bestCaseFloobits": int(bestCaseFloobits),
        "bestCaseMult": round(bestCaseMult, 2),
        "isMatch": bool(breakdown.matchMultiplied),
        "amplifier": amplifier,
        "estimated": estimated,
    }


def computeEquippedProjections(session, userId, season, week, seasonManager, playerManager) -> Dict[str, Any]:
    """Per-equipped-card projections: direct output for most cards,
    descriptive status for amplifiers. Plus roster totals for the
    Projected This Week block.
    """
    from database.models import FantasyRoster, EquippedCard

    roster = session.query(FantasyRoster).filter_by(user_id=userId, season=season).first()
    if not roster:
        return _emptyPayload()
    ctx = buildProjectionContext(session, userId, season, week, seasonManager, playerManager)
    if ctx is None:
        return _emptyPayload()

    equipped = (session.query(EquippedCard)
                .filter(EquippedCard.user_id == userId,
                        EquippedCard.season == season,
                        EquippedCard.week == week)
                .all())
    result = calculateWeekCardBonuses(equipped, ctx)
    peakResult = calculateWeekCardBonuses(equipped, _peakContext(ctx))
    peakBySlot = {b.slotNumber: b for b in peakResult.cardBreakdowns}
    eqBySlot = {eq.slot_number: eq for eq in equipped}

    cards = []
    for b in result.cardBreakdowns:
        eq = eqBySlot.get(b.slotNumber)
        amplifier = _amplifierStatus(eq, equipped, result.cardBreakdowns) if eq else None
        cards.append(_shapeCardPayload(
            b, amplifier,
            _effectConfig(eq) if eq else None,
            peakBySlot.get(b.slotNumber),
        ))

    # Projection uses the Core's signature equation when a Criticality is
    # active so the projected total previews what the user will actually
    # see on their breakdown that week. With no Criticality active,
    # computeFinalOutput falls through to the standard bonus-additive
    # aggregation (next-season's formula).
    try:
        from managers.anomalyManager import getActiveCriticalityCore
        criticalityCore = getActiveCriticalityCore(ctx.season, ctx.weekNumber)
    except Exception:
        criticalityCore = None
    from managers.coreEquations import computeFinalOutput, equationTemplate
    projectedTotalFP, projectedEquation = computeFinalOutput(
        ctx.weekRawFP, result.totalBonusFP, result.multFactors,
        coreKey=criticalityCore,
    )

    # Ceiling total — same formula applied to the peak (hot-week) calc
    # with inflated stats. Gives a realistic "up to" number for the
    # Projected This Week block.
    peakCtx = _peakContext(ctx)
    bestCaseTotalFP, _ = computeFinalOutput(
        peakCtx.weekRawFP, peakResult.totalBonusFP, peakResult.multFactors,
        coreKey=criticalityCore,
    )

    return {
        "cards": cards,
        "totalBonusFP": round(result.totalBonusFP, 2),
        "totalFloobits": result.floobitsEarned,
        "multFactors": [round(m, 2) for m in result.multFactors],
        "projectedRosterFP": round(ctx.weekRawFP, 2),
        "projectedTotalFP": round(projectedTotalFP, 2),
        "bestCaseTotalFP": round(max(projectedTotalFP, bestCaseTotalFP), 2),
        "opponent": ctx.favoriteTeamOpponentName,
        "winProbability": round(ctx.favoriteTeamWinProb, 2),
        "criticalityCore": criticalityCore,
        "criticalityEquation": projectedEquation if criticalityCore else None,
        "criticalityEquationTemplate": equationTemplate(criticalityCore) if criticalityCore else None,
    }


def computeCandidateProjection(userCard, session, userId, season, week,
                                seasonManager, playerManager,
                                replaceSlot: Optional[int] = None) -> Optional[Dict[str, Any]]:
    """Per-candidate projection: what would this card output if equipped.
    Amplifier cards check dependencies against the POST-SWAP hand so
    they reflect whether the required companions will be there after
    you equip the candidate.
    """
    from database.models import FantasyRoster, EquippedCard

    ctx = buildProjectionContext(session, userId, season, week, seasonManager, playerManager)
    if ctx is None:
        return None

    roster = session.query(FantasyRoster).filter_by(user_id=userId, season=season).first()
    if not roster:
        return None

    equipped = (session.query(EquippedCard)
                .filter(EquippedCard.user_id == userId,
                        EquippedCard.season == season,
                        EquippedCard.week == week)
                .all())

    # Build the post-swap hand so amplifier dependency checks reflect
    # reality (incumbent card replaced by the candidate).
    incumbent = None
    if replaceSlot is not None:
        incumbent = next((e for e in equipped if e.slot_number == replaceSlot), None)

    wrapped = _wrapUserCardAsEquipped(userCard)
    wrapped.slot_number = replaceSlot if replaceSlot is not None else (
        incumbent.slot_number if incumbent else 1
    )
    baseHand = [e for e in equipped if incumbent is None or e.id != incumbent.id]
    postSwap = baseHand + [wrapped]

    # Run the calc on the post-swap hand, but only the candidate's
    # own breakdown matters for the output pill.
    result = calculateWeekCardBonuses(postSwap, ctx)
    peakResult = calculateWeekCardBonuses(postSwap, _peakContext(ctx))
    own = next((b for b in result.cardBreakdowns
                if b.slotNumber == wrapped.slot_number and
                b.effectName == _effectName(wrapped)),
               None)
    if own is None:
        return None
    peakOwn = next((b for b in peakResult.cardBreakdowns
                    if b.slotNumber == wrapped.slot_number and
                    b.effectName == _effectName(wrapped)),
                   None)

    amplifier = _amplifierStatus(wrapped, postSwap, result.cardBreakdowns)
    payload = _shapeCardPayload(
        own, amplifier, userCard.card_template.effect_config or {}, peakOwn,
    )
    payload["userCardId"] = userCard.id
    if incumbent is not None:
        payload["replacesSlot"] = incumbent.slot_number
        payload["replacesEffect"] = (
            (incumbent.user_card.card_template.effect_config or {}).get("displayName", "")
        )
    return payload


# ── Helpers ────────────────────────────────────────────────────────────

def _emptyPayload() -> Dict[str, Any]:
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


def _wrapUserCardAsEquipped(userCard):
    class _FauxEquipped:
        __slots__ = ('id', 'slot_number', 'streak_count', 'user_card')
        def __init__(self, uc):
            self.id = -abs(uc.id)
            self.slot_number = 0
            self.streak_count = 1
            self.user_card = uc
    return _FauxEquipped(userCard)


def _wrapTemplateAsUserCard(template, fauxId: int = -1, tier: int = 1):
    """Wrap a CardTemplate in a UserCard-shaped object so projection logic
    that expects userCard.card_template / userCard.id / userCard.tier can run
    against not-yet-owned templates (pack reveal, shop preview). `tier` defaults
    to 1 (not-yet-owned cards are tier I); pass a value to project an upgrade."""
    class _FauxUserCard:
        __slots__ = ('id', 'card_template', 'tier')
        def __init__(self, tpl):
            self.id = fauxId
            self.card_template = tpl
            self.tier = tier
    return _FauxUserCard(template)


def computeTemplateProjection(template, session, userId, season, week,
                              seasonManager, playerManager) -> Optional[Dict[str, Any]]:
    """Project what a CardTemplate would output if equipped, using the
    user's current roster + recent stats. Used for not-yet-owned cards
    (pack reveal-then-select flow, shop preview). Solo projection — the
    template gets evaluated against the user's existing equipped hand
    plus the candidate, but only the candidate's own breakdown is
    returned for the UI pill.
    """
    fauxUserCard = _wrapTemplateAsUserCard(template, fauxId=-(template.id or 1))
    return computeCandidateProjection(
        fauxUserCard, session, userId, season, week,
        seasonManager, playerManager, replaceSlot=None,
    )
