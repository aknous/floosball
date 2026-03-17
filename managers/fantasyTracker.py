"""FantasyTracker — Single source of truth for fantasy roster points.

Owns the entire FP lifecycle from generation to display:
  1. During games: addPlayerPoints() accumulates FP in _weekFP (in-memory)
     and also updates player.gameStatsDict for broadcasts
  2. At week end: bankWeek() persists _weekFP to WeeklyPlayerFP DB table
     and zeros the accumulator
  3. getSnapshot() reads from _weekFP (current week) + WeeklyPlayerFP (past weeks)

This completely decouples fantasy from the gameStatsDict zeroing that happens
inside _accumulatePostgameStats(). Fantasy never reads from game/season stat dicts.
"""

import json as _json
import logging
from typing import Dict, Set

logger = logging.getLogger(__name__)


def _liveStatsToDbFormat(gameStatsDict: dict, teamId: int = 0) -> dict:
    """Translate a live gameStatsDict to card-calc weekPlayerStats format.

    Used to build CardCalcContext from live game data during active games.
    """
    passing = gameStatsDict.get("passing", {})
    rushing = gameStatsDict.get("rushing", {})
    receiving = gameStatsDict.get("receiving", {})
    kicking = gameStatsDict.get("kicking", {})
    return {
        "teamId": teamId,
        "fantasyPoints": gameStatsDict.get("fantasyPoints", 0),
        "passing_stats": {
            "passYards": passing.get("yards", 0),
            "tds": passing.get("tds", 0),
        },
        "rushing_stats": {
            "runYards": rushing.get("yards", 0),
            "runTds": rushing.get("tds", 0),
            "carries": rushing.get("carries", 0),
        },
        "receiving_stats": {
            "rcvYards": receiving.get("yards", 0),
            "rcvTds": receiving.get("tds", 0),
            "receptions": receiving.get("receptions", 0),
            "yac": receiving.get("yac", 0),
            "longest": receiving.get("longest", 0),
        },
        "kicking_stats": {
            "fgs": kicking.get("fgs", 0),
            "fgAtt": kicking.get("fgAtt", 0),
            "longest": kicking.get("longest", 0),
            "fg40plus": kicking.get("fg40+", 0),
        },
    }


def _dbStatsToCardFormat(passingStats: dict, rushingStats: dict,
                         receivingStats: dict, kickingStats: dict,
                         fantasyPoints: float = 0, teamId: int = 0) -> dict:
    """Convert raw DB GamePlayerStats JSON to card-calc weekPlayerStats format.

    DB stores raw gameStatsDict sub-dicts (e.g. passing_stats = {"yards": 100, "tds": 2}).
    Card effects expect the converted format (e.g. passing_stats = {"passYards": 100, "tds": 2}).
    """
    return {
        "teamId": teamId,
        "fantasyPoints": fantasyPoints,
        "passing_stats": {
            "passYards": (passingStats or {}).get("yards", 0),
            "tds": (passingStats or {}).get("tds", 0),
        },
        "rushing_stats": {
            "runYards": (rushingStats or {}).get("yards", 0),
            "runTds": (rushingStats or {}).get("tds", 0),
            "carries": (rushingStats or {}).get("carries", 0),
        },
        "receiving_stats": {
            "rcvYards": (receivingStats or {}).get("yards", 0),
            "rcvTds": (receivingStats or {}).get("tds", 0),
            "receptions": (receivingStats or {}).get("receptions", 0),
            "yac": (receivingStats or {}).get("yac", 0),
            "longest": (receivingStats or {}).get("longest", 0),
        },
        "kicking_stats": {
            "fgs": (kickingStats or {}).get("fgs", 0),
            "fgAtt": (kickingStats or {}).get("fgAtt", 0),
            "longest": (kickingStats or {}).get("longest", 0),
            "fg40plus": (kickingStats or {}).get("fg40+", (kickingStats or {}).get("fg40plus", 0)),
        },
    }



class FantasyTracker:
    """Single source of truth for fantasy roster points.

    Produces a snapshot consumed by both the REST API (/api/fantasy/snapshot)
    and the WebSocket broadcast (leaderboard_update).
    """

    def __init__(self, serviceContainer):
        self.serviceContainer = serviceContainer
        # In-memory FP accumulator: {playerId: float}
        # Tracks current week's FP, banked to DB at week end
        self._weekFP: Dict[int, float] = {}

    def addPlayerPoints(self, playerId: int, points: int):
        """Called when a player earns fantasy points during a game.

        Updates both the in-memory accumulator (source of truth for fantasy)
        and the player's gameStatsDict (for game broadcasts/player profiles).
        """
        self._weekFP[playerId] = self._weekFP.get(playerId, 0) + points
        # Also update gameStatsDict for game broadcasts and player profiles
        player = self._playerManager.getPlayerById(playerId)
        if player and 'fantasyPoints' in player.gameStatsDict:
            player.gameStatsDict['fantasyPoints'] += points

    def getPlayerWeekFP(self, playerId: int) -> float:
        """Get accumulated FP for a player this week (from in-memory tracker)."""
        return self._weekFP.get(playerId, 0)

    def getPlayerSeasonFP(self, playerId: int, season: int) -> float:
        """Get total tracked FP for a player this season (banked weeks + current week).

        Uses the same data sources as the snapshot so points_at_lock values
        are consistent with earned FP calculations.
        """
        from database.connection import get_session
        from database.models import WeeklyPlayerFP

        session = get_session()
        try:
            rows = session.query(WeeklyPlayerFP).filter_by(
                player_id=playerId, season=season
            ).all()
            bankedTotal = sum(r.fantasy_points for r in rows)
        finally:
            session.close()
        # Add current week's in-memory FP (not yet banked)
        return bankedTotal + self._weekFP.get(playerId, 0)

    def restoreWeekFP(self, season: int, week: int):
        """Reconstruct _weekFP from GamePlayerStats for a partially-completed week.

        Called on mid-season resume so the in-memory accumulator reflects
        FP from games already saved to the database before the restart.
        """
        from database.connection import get_session
        from database.models import Game, GamePlayerStats

        session = get_session()
        try:
            rows = (
                session.query(
                    GamePlayerStats.player_id,
                    GamePlayerStats.fantasy_points,
                )
                .join(Game, GamePlayerStats.game_id == Game.id)
                .filter(Game.season == season, Game.week == week)
                .all()
            )
            if not rows:
                return
            restored = {}
            for playerId, fp in rows:
                if fp:
                    restored[playerId] = restored.get(playerId, 0) + fp
            self._weekFP = restored
            logger.info(
                f"Restored week {week} FP for {len(restored)} players from GamePlayerStats"
            )
        finally:
            session.close()

    def bankWeek(self, season: int, week: int):
        """Persist current week's FP to DB and reset accumulator.

        Called by seasonManager at week end, before card effect processing.
        """
        from database.connection import get_session
        from database.models import WeeklyPlayerFP

        if not self._weekFP:
            return

        session = get_session()
        try:
            for playerId, fp in self._weekFP.items():
                if fp == 0:
                    continue
                # Upsert: update if exists, insert if not
                existing = session.query(WeeklyPlayerFP).filter_by(
                    player_id=playerId, season=season, week=week
                ).first()
                if existing:
                    existing.fantasy_points = round(fp, 1)
                else:
                    session.add(WeeklyPlayerFP(
                        player_id=playerId,
                        season=season,
                        week=week,
                        fantasy_points=round(fp, 1),
                    ))
            session.commit()
            logger.info(
                f"Banked week {week} FP for {len(self._weekFP)} players"
            )
        except Exception as e:
            session.rollback()
            logger.error(f"Error banking week FP: {e}")
        finally:
            session.close()

        self._weekFP.clear()

    @property
    def _playerManager(self):
        return self.serviceContainer.getService('player_manager')

    @property
    def _seasonManager(self):
        return self.serviceContainer.getService('season_manager')

    def getSnapshot(self, seasonNum: int = None) -> dict:
        """Build a complete fantasy snapshot for all users.

        Returns a dict with season, week, gamesActive flag, and ranked entries.
        Each entry includes season totals, weekly totals, per-player breakdowns,
        and card bonus breakdowns for the current week.
        """
        from database.connection import get_session
        from database.models import (
            FantasyRoster, FantasyRosterSwap, Game, GamePlayerStats,
            Player, User, WeeklyCardBonus, WeeklyPlayerFP, WeeklyModifier
        )
        from database.repositories.card_repositories import EquippedCardRepository
        from managers.cardEffectCalculator import calculateWeekCardBonuses
        from managers.cardEffects import _countPlayerTds

        sm = self._seasonManager
        if seasonNum is None:
            if sm and sm.currentSeason:
                seasonNum = sm.currentSeason.seasonNumber
            else:
                return {"season": None, "week": 0, "gamesActive": False, "entries": []}

        currentWeek = sm.currentSeason.currentWeek if sm and sm.currentSeason else 0
        isCurrentSeason = seasonNum == (sm.currentSeason.seasonNumber if sm and sm.currentSeason else -1)
        # Only treat games as active when at least one game has actually started
        # (not just Scheduled) — prevents stale gameStatsDict between week_start and game_start
        gamesActive = False
        if isCurrentSeason and sm and sm.currentSeason and sm.currentSeason.activeGames:
            from floosball_game import GameStatus
            gamesActive = any(
                getattr(g, 'status', None) in (GameStatus.Active, GameStatus.Final)
                for g in sm.currentSeason.activeGames
            )

        session = get_session()
        try:
            # ── 1. Get all locked rosters ──
            rosters = session.query(FantasyRoster).filter_by(
                season=seasonNum, is_locked=True
            ).all()
            if not rosters:
                return {
                    "season": seasonNum, "week": currentWeek,
                    "gamesActive": gamesActive, "entries": [],
                }

            # ── 2. Collect all roster player IDs ──
            allRosterPlayerIds = set()
            for roster in rosters:
                for rp in roster.players:
                    allRosterPlayerIds.add(rp.player_id)

            # ── 3. Per-player per-week FP from WeeklyPlayerFP (banked) + _weekFP (live) ──
            weekPlayerFPMap = self._getWeekPlayerFPFromDB(
                session, seasonNum, allRosterPlayerIds
            )
            # Overlay current week's in-memory accumulator (not yet banked)
            if isCurrentSeason and self._weekFP:
                for pid in allRosterPlayerIds:
                    liveFP = self._weekFP.get(pid, 0)
                    if liveFP:
                        weekPlayerFPMap.setdefault(pid, {})[currentWeek] = liveFP

            # ── 4. Stored card bonuses per user per week ──
            weekCardBonusMap = self._getWeekCardBonusesFromDB(session, seasonNum)

            # ── 5. Equipped cards for current week ──
            equippedByUser = {}
            if isCurrentSeason:
                equippedRepo = EquippedCardRepository(session)
                allEquipped = equippedRepo.getAllForWeek(seasonNum, currentWeek)
                for eq in allEquipped:
                    # During active games, only locked cards produce output
                    if gamesActive and not eq.locked:
                        continue
                    equippedByUser.setdefault(eq.user_id, []).append(eq)

            # ── 6. Player ratings and positions ──
            allCardPlayerIds = set()
            for userEquipped in equippedByUser.values():
                for eq in userEquipped:
                    allCardPlayerIds.add(eq.user_card.card_template.player_id)
            allRelevantPlayerIds = allRosterPlayerIds | allCardPlayerIds

            playerRatingsMap = {}
            playerPositionMap = {}
            if allRelevantPlayerIds:
                playerRows = session.query(
                    Player.id, Player.player_rating, Player.position
                ).filter(Player.id.in_(allRelevantPlayerIds)).all()
                for pid, rating, pos in playerRows:
                    playerRatingsMap[pid] = rating or 60
                    playerPositionMap[pid] = pos

            # ── 8. Full week stats from DB (for card calc when games not active) ──
            dbCurrentWeekFullStats = {}
            if not gamesActive and isCurrentSeason:
                dbCurrentWeekFullStats = self._getFullWeekPlayerStats(
                    session, seasonNum, currentWeek
                )

            # ── 9a. Week games + team results (shared across entries) ──
            teamManager = self.serviceContainer.getService('team_manager')
            weekFinalGames = session.query(Game).filter_by(
                season=seasonNum, week=currentWeek, status='final'
            ).all() if isCurrentSeason else []
            weekTeamResults = {}   # teamId → True (won) / False (lost)
            weekTeamGameMap = {}   # teamId → Game
            for g in weekFinalGames:
                weekTeamGameMap[g.home_team_id] = g
                weekTeamGameMap[g.away_team_id] = g
                if g.home_score > g.away_score:
                    weekTeamResults[g.home_team_id] = True
                    weekTeamResults[g.away_team_id] = False
                elif g.away_score > g.home_score:
                    weekTeamResults[g.away_team_id] = True
                    weekTeamResults[g.home_team_id] = False

            # ── 9b. Raw player game stats for display (full stats, no lock offsets) ──
            allPlayerRawStats = {}  # playerId → {passing:{}, rushing:{}, ...}
            if isCurrentSeason:
                if gamesActive:
                    pm = self._playerManager
                    if pm:
                        for pid in allRosterPlayerIds:
                            pObj = pm.getPlayerById(pid)
                            if pObj and pObj.gameStatsDict:
                                rawStats = pObj.gameStatsDict
                                allPlayerRawStats[pid] = {
                                    "passing": dict(rawStats.get("passing", {})),
                                    "rushing": dict(rawStats.get("rushing", {})),
                                    "receiving": dict(rawStats.get("receiving", {})),
                                    "kicking": dict(rawStats.get("kicking", {})),
                                    "fantasyPoints": rawStats.get("fantasyPoints", 0),
                                }
                else:
                    # From DB: query GamePlayerStats for this week
                    weekGameRows = session.query(Game.id).filter_by(
                        season=seasonNum, week=currentWeek
                    ).all()
                    weekGameIds = [r[0] for r in weekGameRows]
                    if weekGameIds:
                        gpsRows = session.query(GamePlayerStats).filter(
                            GamePlayerStats.game_id.in_(weekGameIds)
                        ).all()
                        for gps in gpsRows:
                            allPlayerRawStats[gps.player_id] = {
                                "passing": dict(gps.passing_stats or {}),
                                "rushing": dict(gps.rushing_stats or {}),
                                "receiving": dict(gps.receiving_stats or {}),
                                "kicking": dict(gps.kicking_stats or {}),
                                "fantasyPoints": gps.fantasy_points or 0,
                            }

            # ── 10. Assemble entries ──
            entries = []
            for roster in rosters:
                userId = roster.user_id
                rosterUser = session.get(User, userId)
                rosterPlayerIds = {rp.player_id for rp in roster.players}

                # Per-player weekly FP (banked + live from _weekFP overlay)
                perPlayerWeekFP = {}
                for rp in roster.players:
                    perPlayerWeekFP[rp.player_id] = dict(
                        weekPlayerFPMap.get(rp.player_id, {})
                    )

                # Build player entries + season/week totals
                rosterPlayers = []
                seasonEarnedFP = 0.0
                currentWeekPlayerFP = 0.0
                playerLockOffsets = {}   # playerId -> FP offset for current week
                for rp in roster.players:
                    pObj = self._playerManager.getPlayerById(rp.player_id)
                    playerWeeks = perPlayerWeekFP.get(rp.player_id, {})
                    playerSeasonFP = sum(playerWeeks.values())
                    playerWeekFP = playerWeeks.get(currentWeek, 0)
                    # Only count FP earned after locking (offset by points_at_lock)
                    playerEarnedFP = max(0, playerSeasonFP - rp.points_at_lock)
                    seasonEarnedFP += playerEarnedFP
                    # Adjust weekly FP for mid-week lock: subtract the portion
                    # of points_at_lock that falls within the current week
                    priorWeeksFP = sum(
                        fp for w, fp in playerWeeks.items() if w < currentWeek
                    )
                    lockWeekOffset = max(0, rp.points_at_lock - priorWeeksFP)
                    adjustedWeekFP = max(0, playerWeekFP - lockWeekOffset)
                    currentWeekPlayerFP += adjustedWeekFP
                    playerLockOffsets[rp.player_id] = lockWeekOffset

                    rosterPlayers.append({
                        "slot": rp.slot,
                        "playerId": rp.player_id,
                        "playerName": pObj.name if pObj else "Unknown",
                        "position": (
                            pObj.position.name
                            if pObj and hasattr(pObj.position, 'name')
                            else ""
                        ),
                        "teamAbbr": (
                            getattr(pObj.team, 'abbr', '')
                            if pObj and hasattr(pObj, 'team') and pObj.team
                            else ""
                        ),
                        "earnedPoints": round(playerEarnedFP, 1),
                        "weekFP": round(adjustedWeekFP, 1),
                    })

                # ── Previous players (swapped out) ──
                swaps = session.query(FantasyRosterSwap).filter_by(
                    roster_id=roster.id
                ).all()
                previousPlayersFP = sum(s.banked_fp for s in swaps)
                if previousPlayersFP > 0:
                    seasonEarnedFP += previousPlayersFP
                    rosterPlayers.append({
                        "slot": "PREV",
                        "playerId": 0,
                        "playerName": "Previous Players",
                        "position": "",
                        "teamAbbr": "",
                        "earnedPoints": round(previousPlayersFP, 1),
                        "weekFP": 0,
                    })

                # ── Favorite team data ──
                favoriteTeamData = None
                userFavTeamId = getattr(rosterUser, 'favorite_team_id', None) if rosterUser else None
                if userFavTeamId and teamManager:
                    favTeam = teamManager.getTeamById(userFavTeamId)
                    if favTeam:
                        favStats = getattr(favTeam, 'seasonTeamStats', {})
                        wins = favStats.get('wins', 0)
                        losses = favStats.get('losses', 0)
                        streak = favStats.get('streak', 0)
                        wonThisWeek = weekTeamResults.get(userFavTeamId)

                        # Game score
                        gameScore = None
                        favGame = weekTeamGameMap.get(userFavTeamId)
                        if favGame:
                            isHome = favGame.home_team_id == userFavTeamId
                            teamScore = favGame.home_score if isHome else favGame.away_score
                            oppScore = favGame.away_score if isHome else favGame.home_score
                            result = "W" if wonThisWeek else ("L" if wonThisWeek is False else "T")
                            gameScore = f"{result} {teamScore}-{oppScore}"

                        # Playoff status (top 6 in league)
                        inPlayoffs = False
                        if sm and hasattr(sm, 'leagueManager') and sm.leagueManager:
                            teamLeague = sm.leagueManager.getTeamLeague(favTeam)
                            if teamLeague:
                                standings = teamLeague.getStandings()
                                for idx, sEntry in enumerate(standings):
                                    if sEntry['team'] == favTeam:
                                        inPlayoffs = idx < 6
                                        break

                        favoriteTeamData = {
                            "teamId": userFavTeamId,
                            "teamName": getattr(favTeam, 'name', ''),
                            "teamAbbr": getattr(favTeam, 'abbr', ''),
                            "teamColor": getattr(favTeam, 'color', '#666'),
                            "elo": round(getattr(favTeam, 'elo', 1500.0), 1),
                            "record": f"{wins}-{losses}",
                            "streak": streak,
                            "inPlayoffs": inPlayoffs,
                            "wonThisWeek": wonThisWeek,
                            "gameScore": gameScore,
                        }

                # ── Player game stats for display ──
                playerGameStats = {}
                for rp in roster.players:
                    rawStats = allPlayerRawStats.get(rp.player_id)
                    if rawStats:
                        playerGameStats[rp.player_id] = rawStats

                # ── Card bonuses ──
                userWeekBonuses = weekCardBonusMap.get(userId, {})
                storedSeasonCardBonus = sum(
                    wb["fp"] for wb in userWeekBonuses.values()
                )
                hasStoredCurrentWeekBonus = currentWeek in userWeekBonuses

                weekCardBonus = 0.0
                cardBreakdowns = []
                eqSummary = {}

                if not hasStoredCurrentWeekBonus and userId in equippedByUser:
                    # Need to compute current week card bonus
                    userEquipped = equippedByUser[userId]
                    cardCalcStats = {}
                    weekRawFP = 0.0
                    rosterTotalTds = 0
                    rosterPlayerRatings = {}

                    if gamesActive:
                        # Build from live game data
                        for rp in roster.players:
                            pObj = self._playerManager.getPlayerById(rp.player_id)
                            if pObj:
                                pTeamId = getattr(pObj.team, 'id', 0) if hasattr(pObj, 'team') else 0
                                stats = _liveStatsToDbFormat(pObj.gameStatsDict, teamId=pTeamId)
                                # Use post-lock FP (adjusted for lock offset)
                                offset = playerLockOffsets.get(rp.player_id, 0)
                                effectiveFP = perPlayerWeekFP.get(
                                    rp.player_id, {}
                                ).get(currentWeek, 0)
                                adjustedFP = max(0, effectiveFP - offset)
                                stats["fantasyPoints"] = adjustedFP
                                cardCalcStats[rp.player_id] = stats
                                weekRawFP += adjustedFP
                                rosterTotalTds += _countPlayerTds(stats)
                                rosterPlayerRatings[rp.player_id] = (
                                    getattr(pObj, 'playerRating', 60) or 60
                                )
                    else:
                        # Build from DB (games ended, week not yet processed)
                        for rp in roster.players:
                            pStats = dbCurrentWeekFullStats.get(
                                rp.player_id, {}
                            )
                            if pStats:
                                # Adjust FP for lock offset
                                offset = playerLockOffsets.get(rp.player_id, 0)
                                pStats["fantasyPoints"] = max(
                                    0, pStats.get("fantasyPoints", 0) - offset
                                )
                                cardCalcStats[rp.player_id] = pStats
                                weekRawFP += pStats.get("fantasyPoints", 0)
                                rosterTotalTds += _countPlayerTds(pStats)
                            rosterPlayerRatings[rp.player_id] = (
                                playerRatingsMap.get(rp.player_id, 60)
                            )

                    # Add depicted player stats if not already in cardCalcStats
                    for eq in userEquipped:
                        cardPlayerId = eq.user_card.card_template.player_id
                        if cardPlayerId not in cardCalcStats:
                            if gamesActive:
                                cardPlayerObj = self._playerManager.getPlayerById(
                                    cardPlayerId
                                )
                                if cardPlayerObj:
                                    cardCalcStats[cardPlayerId] = (
                                        _liveStatsToDbFormat(
                                            cardPlayerObj.gameStatsDict
                                        )
                                    )
                            else:
                                pStats = dbCurrentWeekFullStats.get(
                                    cardPlayerId, {}
                                )
                                if pStats:
                                    cardCalcStats[cardPlayerId] = pStats

                    calcCtx = self._buildCardCalcContext(
                        session, roster, rosterPlayerIds, userEquipped,
                        cardCalcStats, weekRawFP, rosterPlayerRatings,
                        rosterTotalTds, playerPositionMap, userId,
                        gamesActive=gamesActive,
                    )
                    calcResult = calculateWeekCardBonuses(userEquipped, calcCtx)
                    # Formula: (rosterFP + Σ flat FP) × FPx₁ × FPx₂ × ...
                    baseFP = weekRawFP + calcResult.totalBonusFP
                    multProduct = 1.0
                    for f in calcResult.multFactors:
                        multProduct *= f
                    weekCardBonus = round(baseFP * multProduct - weekRawFP, 2)
                    if weekCardBonus < 0:
                        weekCardBonus = 0.0
                    cardBreakdowns = [
                        self._breakdownToDict(b)
                        for b in calcResult.cardBreakdowns
                    ]
                    eqSummary = {
                        "weekRawFP": round(weekRawFP, 1),
                        "totalBonusFP": round(calcResult.totalBonusFP, 2),
                        "multFactors": [round(f, 2) for f in calcResult.multFactors],
                    }
                elif hasStoredCurrentWeekBonus:
                    stored = userWeekBonuses[currentWeek]
                    weekCardBonus = stored["fp"]
                    cardBreakdowns = stored.get("breakdowns", [])
                    eqSummary = stored.get("equationSummary", {})

                # Season card bonus = stored weeks + live current week
                seasonCardBonus = storedSeasonCardBonus
                if not hasStoredCurrentWeekBonus:
                    seasonCardBonus += weekCardBonus

                seasonTotal = round(seasonEarnedFP + seasonCardBonus, 1)
                weekTotal = round(currentWeekPlayerFP + weekCardBonus, 1)

                entries.append({
                    "rank": 0,
                    "userId": userId,
                    "username": (
                        rosterUser.username or rosterUser.email
                        if rosterUser else "Unknown"
                    ),
                    "seasonEarnedFP": round(seasonEarnedFP, 1),
                    "seasonCardBonus": round(seasonCardBonus, 1),
                    "seasonTotal": seasonTotal,
                    "weekPlayerFP": round(currentWeekPlayerFP, 1),
                    "weekCardBonus": round(weekCardBonus, 1),
                    "weekTotal": weekTotal,
                    "lockedAt": (
                        roster.locked_at.isoformat()
                        if roster.locked_at else None
                    ),
                    "players": rosterPlayers,
                    "cardBreakdowns": cardBreakdowns,
                    "equationSummary": eqSummary,
                    "favoriteTeamData": favoriteTeamData,
                    "playerGameStats": playerGameStats,
                })

            # Sort and rank by season total
            entries.sort(key=lambda e: e["seasonTotal"], reverse=True)
            for i, entry in enumerate(entries, 1):
                entry["rank"] = i

            # ── Modifier info ──
            modifierInfo = None
            if isCurrentSeason and currentWeek >= 1:
                modRow = session.query(WeeklyModifier).filter_by(
                    season=seasonNum, week=currentWeek
                ).first()
                if modRow:
                    modName = modRow.modifier
                    modifierInfo = {
                        "name": modName,
                        "displayName": sm.MODIFIER_DISPLAY.get(modName, modName.title()),
                        "description": sm.MODIFIER_DESCRIPTIONS.get(modName, ""),
                    }

            return {
                "season": seasonNum,
                "week": currentWeek,
                "gamesActive": gamesActive,
                "entries": entries,
                "modifier": modifierInfo,
            }
        finally:
            session.close()

    # ── Helper methods ──────────────────────────────────────────────────────

    def _getWeekPlayerFPFromDB(
        self, session, seasonNum: int, playerIds: Set[int]
    ) -> Dict[int, Dict[int, float]]:
        """Query WeeklyPlayerFP → {playerId: {week: fp}} for all banked weeks."""
        from database.models import WeeklyPlayerFP

        if not playerIds:
            return {}

        rows = (
            session.query(WeeklyPlayerFP)
            .filter(
                WeeklyPlayerFP.season == seasonNum,
                WeeklyPlayerFP.player_id.in_(playerIds),
            )
            .all()
        )

        result = {}
        for row in rows:
            result.setdefault(row.player_id, {})[row.week] = row.fantasy_points or 0
        return result

    def _getWeekCardBonusesFromDB(
        self, session, seasonNum: int
    ) -> Dict[int, Dict[int, dict]]:
        """Query WeeklyCardBonus → {userId: {week: {fp, breakdowns}}} for the season."""
        from database.models import WeeklyCardBonus

        rows = session.query(WeeklyCardBonus).filter_by(season=seasonNum).all()
        result = {}
        for row in rows:
            breakdowns = []
            eqSummary = {}
            if row.breakdowns_json:
                try:
                    parsed = _json.loads(row.breakdowns_json)
                    if isinstance(parsed, list):
                        # Old format: bare list of breakdowns
                        breakdowns = parsed
                    elif isinstance(parsed, dict):
                        # New format: {breakdowns: [...], equationSummary: {...}}
                        breakdowns = parsed.get("breakdowns", [])
                        eqSummary = parsed.get("equationSummary", {})
                except Exception:
                    pass
            result.setdefault(row.user_id, {})[row.week] = {
                "fp": row.bonus_fp or 0,
                "breakdowns": breakdowns,
                "equationSummary": eqSummary,
            }
        return result

    def _getFullWeekPlayerStats(
        self, session, seasonNum: int, week: int
    ) -> Dict[int, dict]:
        """Get full player stats for a week from DB (for card calc conditionals).

        FP comes from WeeklyPlayerFP; sub-stats (yards, TDs) from GamePlayerStats.
        """
        from database.models import GamePlayerStats, Game, WeeklyPlayerFP

        # Get FP from WeeklyPlayerFP
        fpRows = session.query(WeeklyPlayerFP).filter_by(
            season=seasonNum, week=week
        ).all()
        fpByPlayer = {row.player_id: row.fantasy_points for row in fpRows}

        # Get sub-stats from GamePlayerStats
        rows = (
            session.query(GamePlayerStats)
            .join(Game, GamePlayerStats.game_id == Game.id)
            .filter(Game.season == seasonNum, Game.week == week)
            .all()
        )
        result = {}
        for gps in rows:
            result[gps.player_id] = _dbStatsToCardFormat(
                gps.passing_stats, gps.rushing_stats,
                gps.receiving_stats, gps.kicking_stats,
                fpByPlayer.get(gps.player_id, 0),
                teamId=gps.team_id,
            )
        return result

    def _buildCardCalcContext(
        self, session, roster, rosterPlayerIds, userEquipped,
        weekPlayerStats, weekRawFP, rosterPlayerRatings,
        rosterTotalTds, playerPositionMap, userId,
        gamesActive=False,
    ):
        """Build a CardCalcContext for card bonus computation."""
        from database.models import FantasyRosterSwap, Game, User
        from managers.cardEffectCalculator import CardCalcContext

        sm = self._seasonManager
        season = sm.currentSeason.seasonNumber if sm and sm.currentSeason else 0
        currentWeek = sm.currentSeason.currentWeek if sm and sm.currentSeason else 0

        streakCounts = {
            eq.id: getattr(eq, 'streak_count', 1) for eq in userEquipped
        }

        rosterPlayerPositions = {
            pid: playerPositionMap.get(pid, 0) for pid in rosterPlayerIds
        }

        rosterUser = session.get(User, userId)
        userFavoriteTeamId = rosterUser.favorite_team_id if rosterUser else None

        # Favorite team data from live objects
        favoriteTeamElo = 1500.0
        favoriteTeamStreak = 0
        favoriteTeamPriorStreak = 0
        favoriteTeamSeasonLosses = 0
        favoriteTeamInPlayoffs = False
        favoriteTeamWonThisWeek = False
        favoriteTeamOpponentElo = 1500.0
        favoriteTeamOpponentName = ""
        favoriteTeamBigPlays = 0
        favoriteTeamGameFinal = False
        teamResults = {}

        teamManager = self.serviceContainer.getService('team_manager')

        # Build team results from final DB games this week
        weekGames = session.query(Game).filter_by(
            season=season, week=currentWeek, status='final'
        ).all()
        for g in weekGames:
            if g.home_score > g.away_score:
                teamResults[g.home_team_id] = True
                teamResults[g.away_team_id] = False
            elif g.away_score > g.home_score:
                teamResults[g.away_team_id] = True
                teamResults[g.home_team_id] = False

        teamGameMap = {}
        for g in weekGames:
            teamGameMap[g.home_team_id] = g
            teamGameMap[g.away_team_id] = g

        if userFavoriteTeamId and teamManager:
            favTeam = teamManager.getTeamById(userFavoriteTeamId)
            if favTeam:
                favoriteTeamElo = getattr(favTeam, 'elo', 1500.0)
                favStats = getattr(favTeam, 'seasonTeamStats', {})
                favoriteTeamStreak = favStats.get('streak', 0)
                favoriteTeamPriorStreak = favStats.get('priorStreak', 0)
                favoriteTeamSeasonLosses = favStats.get('losses', 0)
                favoriteTeamWonThisWeek = teamResults.get(userFavoriteTeamId, False)

                # Big plays + opponent info from live games
                if sm and sm.currentSeason and sm.currentSeason.activeGames:
                    for game in sm.currentSeason.activeGames:
                        homeTeam = getattr(game, 'homeTeam', None)
                        awayTeam = getattr(game, 'awayTeam', None)
                        hId = getattr(homeTeam, 'id', None)
                        aId = getattr(awayTeam, 'id', None)
                        if userFavoriteTeamId in (hId, aId):
                            oppTeamLive = awayTeam if userFavoriteTeamId == hId else homeTeam
                            if oppTeamLive and not favoriteTeamOpponentName:
                                favoriteTeamOpponentElo = getattr(oppTeamLive, 'elo', 1500.0)
                                favoriteTeamOpponentName = getattr(oppTeamLive, 'abbr', '') or getattr(oppTeamLive, 'name', '')
                            for entry in getattr(game, 'gameFeed', []):
                                if entry.get('isBigPlay'):
                                    favoriteTeamBigPlays += 1

                # Playoff status
                if sm and hasattr(sm, 'leagueManager') and sm.leagueManager:
                    teamLeague = sm.leagueManager.getTeamLeague(favTeam)
                    if teamLeague:
                        standings = teamLeague.getStandings()
                        for idx, entry in enumerate(standings):
                            if entry['team'] == favTeam:
                                favoriteTeamInPlayoffs = idx < 6
                                break

                # Opponent ELO and game final status
                favGame = teamGameMap.get(userFavoriteTeamId)
                if favGame:
                    oppId = favGame.away_team_id if favGame.home_team_id == userFavoriteTeamId else favGame.home_team_id
                    oppTeam = teamManager.getTeamById(oppId)
                    if oppTeam:
                        favoriteTeamOpponentElo = getattr(oppTeam, 'elo', 1500.0)
                        favoriteTeamOpponentName = getattr(oppTeam, 'abbr', '') or getattr(oppTeam, 'name', '')
                    # teamGameMap only contains final games, so presence = final
                    favoriteTeamGameFinal = True

        # League average ELO
        leagueAverageElo = 1500.0
        if teamManager:
            allTeams = teamManager.teams
            if allTeams:
                leagueAverageElo = sum(getattr(t, 'elo', 1500.0) for t in allTeams) / len(allTeams)

        # Player performance ratings from live objects
        playerPerfRatings = {}
        pm = self._playerManager
        if pm:
            for p in pm.activePlayers:
                perfRating = getattr(p, 'seasonPerformanceRating', 0)
                if perfRating > 0:
                    playerPerfRatings[p.id] = perfRating

        # Roster unchanged weeks
        lastSwap = (
            session.query(FantasyRosterSwap.swap_week)
            .filter_by(roster_id=roster.id)
            .order_by(FantasyRosterSwap.swap_week.desc())
            .first()
        )
        rosterUnchangedWeeks = currentWeek if not lastSwap else max(0, currentWeek - lastSwap[0])

        # Weekly modifier
        activeModifier = ""
        try:
            from database.models import WeeklyModifier
            modRow = session.query(WeeklyModifier).filter_by(
                season=season, week=currentWeek
            ).first()
            if modRow:
                activeModifier = modRow.modifier
        except Exception:
            pass

        # Check for user-level modifier override (Modifier Nullifier power-up)
        try:
            from database.models import UserModifierOverride
            modOverride = session.query(UserModifierOverride).filter_by(
                user_id=userId, season=season, week=currentWeek
            ).first()
            if modOverride:
                activeModifier = modOverride.override_modifier
        except Exception:
            pass

        # Game performance ratings (per-game, same formula as season perf)
        gamePerformanceRatings = {}
        if pm:
            from database.models import GamePlayerStats as GPSModel
            weekGameIds = [g.id for g in weekGames]
            if weekGameIds:
                gpsList = session.query(GPSModel).filter(
                    GPSModel.game_id.in_(weekGameIds)
                ).all()
                gamePerformanceRatings = pm.calculateGamePerformanceRatings(gpsList)

        # Roster player team IDs and names (for same-team stacking and stat line display)
        rosterPlayerTeamIds = {}
        rosterPlayerNames = {}
        for pid in rosterPlayerIds:
            ps = weekPlayerStats.get(pid, {})
            teamId = ps.get("teamId")
            if teamId:
                rosterPlayerTeamIds[pid] = teamId
            if pm:
                player = pm.getPlayerById(pid)
                if player:
                    rosterPlayerNames[pid] = player.name
                    if not teamId and hasattr(player, 'team') and hasattr(player.team, 'id'):
                        rosterPlayerTeamIds[pid] = player.team.id

        # Favorite team game-outcome fields (score margin, comeback, walk-off)
        favoriteTeamScoreMargin = 0
        favoriteTeamComebackWin = False
        favoriteTeamLargestDeficit = 0
        favoriteTeamWalkOffWin = False

        favGame = teamGameMap.get(userFavoriteTeamId) if userFavoriteTeamId else None
        if favGame and favoriteTeamWonThisWeek:
            favoriteTeamScoreMargin = abs(favGame.home_score - favGame.away_score)

            # Scan gameFeed for comeback and walk-off detection
            isHome = (favGame.home_team_id == userFavoriteTeamId)
            if sm and sm.currentSeason and sm.currentSeason.activeGames:
                for game in sm.currentSeason.activeGames:
                    hTeam = getattr(game, 'homeTeam', None)
                    aTeam = getattr(game, 'awayTeam', None)
                    hId = getattr(hTeam, 'id', None)
                    aId = getattr(aTeam, 'id', None)
                    if userFavoriteTeamId not in (hId, aId):
                        continue
                    isHomeGame = (hId == userFavoriteTeamId)

                    maxDeficit = 0
                    lastGoAheadPlay = None
                    prevDiff = 0  # start tied (0-0)
                    # gameFeed is newest-first; reverse for chronological order
                    for entry in reversed(getattr(game, 'gameFeed', [])):
                        playObj = entry.get('play')
                        if not playObj or not getattr(playObj, 'scoreChange', False):
                            continue
                        hScore = getattr(playObj, 'homeTeamScore', 0)
                        aScore = getattr(playObj, 'awayTeamScore', 0)
                        # Positive = favorite team leading, negative = trailing
                        diff = (hScore - aScore) if isHomeGame else (aScore - hScore)
                        if diff < 0:
                            maxDeficit = max(maxDeficit, abs(diff))

                        # Track go-ahead plays (team goes from tied/behind to ahead)
                        if diff > 0 and prevDiff <= 0:
                            lastGoAheadPlay = playObj
                        prevDiff = diff

                    if maxDeficit > 0:
                        favoriteTeamComebackWin = True
                        favoriteTeamLargestDeficit = maxDeficit

                    # Walk-off: go-ahead in last 60 sec of Q4 or during OT
                    if lastGoAheadPlay:
                        q = getattr(lastGoAheadPlay, 'quarter', 0)
                        timeStr = getattr(lastGoAheadPlay, 'timeRemaining', '15:00')
                        # Parse "M:SS" to seconds
                        try:
                            parts = timeStr.split(':')
                            clock = int(parts[0]) * 60 + int(parts[1])
                        except (ValueError, IndexError):
                            clock = 999
                        if q >= 5 or (q == 4 and clock <= 60):
                            favoriteTeamWalkOffWin = True
                    break  # Only process the matching game

        # Compute kicker season FG misses for Good Neighbor
        kickerSeasonFgMisses = 0
        kickerPids = [pid for pid in rosterPlayerIds
                      if playerPositionMap.get(pid) == 5]
        if kickerPids:
            from database.models import GamePlayerStats as GPSModel2
            seasonKickerStats = (
                session.query(GPSModel2)
                .join(Game, GPSModel2.game_id == Game.id)
                .filter(Game.season == season, Game.week < currentWeek,
                        GPSModel2.player_id.in_(kickerPids))
                .all()
            )
            for ks in seasonKickerStats:
                kStats = ks.kicking_stats or {}
                if isinstance(kStats, str):
                    import json as _jsonk
                    kStats = _jsonk.loads(kStats)
                kickerSeasonFgMisses += kStats.get("fg_missed", 0)

        # Compute chanceBonus from Fortune's Favor + fortunate modifier
        chanceBonus = 0.0
        if activeModifier == "fortunate":
            chanceBonus += 0.15
        try:
            from database.repositories.shop_repository import ShopPurchaseRepository
            shopRepo = ShopPurchaseRepository(session)
            if hasattr(shopRepo, 'getActiveFortunesFavor') and shopRepo.getActiveFortunesFavor(userId, season, currentWeek):
                chanceBonus += 0.10
        except Exception:
            pass

        # Live streak condition evaluation (during active games)
        liveStreakConditionsMet = {}
        if gamesActive:
            liveStreakConditionsMet = self._evaluateLiveStreakConditions(
                userEquipped, weekPlayerStats, rosterPlayerIds,
                rosterTotalTds, weekRawFP, playerPositionMap,
                streakCounts, teamResults,
                userFavoriteTeamId, favoriteTeamWonThisWeek,
                favoriteTeamOpponentElo, favoriteTeamElo,
            )
        elif not teamResults:
            # Between weeks (no final games yet) — streak conditions unknown,
            # default to False so cards don't show stale output from prior week
            from managers.cardEffects import STREAK_CONFIGS
            for eq in userEquipped:
                ec = eq.user_card.card_template.effect_config or {}
                effectName = ec.get("effectName", "")
                if effectName in STREAK_CONFIGS and not STREAK_CONFIGS[effectName].get("isWeekly", False):
                    liveStreakConditionsMet[eq.id] = False

        return CardCalcContext(
            userId=userId,
            season=season,
            weekNumber=currentWeek,
            gamesActive=gamesActive,
            chanceBonus=chanceBonus,
            kickerSeasonFgMisses=kickerSeasonFgMisses,
            rosterPlayerIds=rosterPlayerIds,
            weekPlayerStats=weekPlayerStats,
            weekRawFP=weekRawFP,
            rosterPlayerRatings=rosterPlayerRatings,
            rosterTotalTds=rosterTotalTds,
            rosterPlayerPositions=rosterPlayerPositions,
            streakCounts=streakCounts,
            userFavoriteTeamId=userFavoriteTeamId,
            favoriteTeamElo=favoriteTeamElo,
            leagueAverageElo=leagueAverageElo,
            favoriteTeamStreak=favoriteTeamStreak,
            favoriteTeamPriorStreak=favoriteTeamPriorStreak,
            favoriteTeamSeasonLosses=favoriteTeamSeasonLosses,
            favoriteTeamInPlayoffs=favoriteTeamInPlayoffs,
            favoriteTeamWonThisWeek=favoriteTeamWonThisWeek,
            favoriteTeamOpponentElo=favoriteTeamOpponentElo,
            favoriteTeamOpponentName=favoriteTeamOpponentName,
            favoriteTeamBigPlays=favoriteTeamBigPlays,
            favoriteTeamGameFinal=favoriteTeamGameFinal,
            rosterUnchangedWeeks=rosterUnchangedWeeks,
            teamResults=teamResults,
            playerPerformanceRatings=playerPerfRatings,
            gamePerformanceRatings=gamePerformanceRatings,
            rosterPlayerTeamIds=rosterPlayerTeamIds,
            rosterPlayerNames=rosterPlayerNames,
            favoriteTeamScoreMargin=favoriteTeamScoreMargin,
            favoriteTeamComebackWin=favoriteTeamComebackWin,
            favoriteTeamLargestDeficit=favoriteTeamLargestDeficit,
            favoriteTeamWalkOffWin=favoriteTeamWalkOffWin,
            activeModifier=activeModifier,
            unusedSwaps=(roster.swaps_available or 0) + (roster.purchased_swaps or 0),
            liveStreakConditionsMet=liveStreakConditionsMet,
        )

    def _evaluateLiveStreakConditions(
        self, userEquipped, weekPlayerStats, rosterPlayerIds,
        rosterTotalTds, weekRawFP, playerPositionMap,
        streakCounts, teamResults,
        userFavoriteTeamId, favoriteTeamWonThisWeek,
        favoriteTeamOpponentElo, favoriteTeamElo,
    ) -> dict:
        """Evaluate streak conditions from live game data.

        Returns {eqId: bool} for each season-streak card.
        If condition is met, also increments streakCounts[eqId] in-place.
        """
        from managers.cardEffects import STREAK_CONFIGS

        result = {}
        # Find kicker stats once (position 5)
        kickerStats = None
        for pid in rosterPlayerIds:
            if playerPositionMap.get(pid) == 5:
                kickerStats = weekPlayerStats.get(pid, {}).get("kicking_stats", {})
                break

        for eq in userEquipped:
            ec = eq.user_card.card_template.effect_config or {}
            effectName = ec.get("effectName", "")
            category = ec.get("category", "")
            if category != "streak":
                continue
            config = STREAK_CONFIGS.get(effectName, {})
            if config.get("isWeekly"):
                continue

            condition = config.get("resetCondition", "equipped")
            conditionMet = False

            if condition == "equipped":
                conditionMet = True
            elif condition == "roster_unchanged":
                conditionMet = True  # Already locked
            elif condition == "kicker_fg":
                conditionMet = (kickerStats or {}).get("fgs", 0) > 0
            elif condition == "kicker_35plus":
                conditionMet = (kickerStats or {}).get("longest", 0) >= 35
            elif condition == "kicker_no_miss":
                # Can't confirm "no miss" until game ends — defer
                fgAtt = (kickerStats or {}).get("fgAtt", 0)
                fgMade = (kickerStats or {}).get("fgs", 0)
                if fgAtt > 0 and fgMade < fgAtt:
                    conditionMet = False  # Already missed one
                else:
                    conditionMet = False  # Can't confirm yet, show base
            elif condition == "roster_td":
                conditionMet = rosterTotalTds > 0
            elif condition == "roster_75fp":
                conditionMet = weekRawFP >= 75
            elif condition == "card_player_team_wins":
                cardPlayerId = eq.user_card.card_template.player_id
                cardPlayerStats = weekPlayerStats.get(cardPlayerId, {})
                teamId = cardPlayerStats.get("teamId")
                conditionMet = teamResults.get(teamId, False) if teamId else False
            elif condition == "favorite_team_wins":
                conditionMet = favoriteTeamWonThisWeek
            elif condition == "favorite_team_upset_win":
                conditionMet = (
                    favoriteTeamWonThisWeek
                    and favoriteTeamOpponentElo > favoriteTeamElo
                )

            result[eq.id] = conditionMet
            if conditionMet:
                # Increment streak count for this computation
                streakCounts[eq.id] = getattr(eq, 'streak_count', 0) + 1

        return result

    @staticmethod
    def _breakdownToDict(b) -> dict:
        """Convert a CardBreakdown dataclass to a serializable dict."""
        return {
            "slotNumber": b.slotNumber,
            "edition": b.edition,
            "playerId": b.playerId,
            "playerName": b.playerName,
            "effectName": b.effectName,
            "displayName": b.displayName,
            "detail": b.detail,
            "category": b.category,
            "outputType": b.outputType,
            "primaryFP": b.primaryFP,
            "primaryMult": b.primaryMult,
            "matchMultiplied": b.matchMultiplied,
            "matchMultiplier": b.matchMultiplier,
            "preMatchFP": b.preMatchFP,
            "preMatchFloobits": b.preMatchFloobits,
            "preMatchMult": b.preMatchMult,
            "conditionalBonus": b.conditionalBonus,
            "conditionalLabel": b.conditionalLabel,
            "secondaryFP": b.secondaryFP,
            "secondaryFloobits": b.secondaryFloobits,
            "secondaryMult": b.secondaryMult,
            "totalFP": b.totalFP,
            "floobitsEarned": b.floobitsEarned,
            "playerStatLine": b.playerStatLine,
            "equation": b.equation,
            "isChanceEffect": b.isChanceEffect,
            "chanceRoll": b.chanceRoll,
            "chanceThreshold": b.chanceThreshold,
            "chanceTriggered": b.chanceTriggered,
            "streakActive": b.streakActive,
            "streakCount": b.streakCount,
        }
