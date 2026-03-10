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

import logging
from typing import Dict, Set

logger = logging.getLogger(__name__)


def _liveStatsToDbFormat(gameStatsDict: dict) -> dict:
    """Translate a live gameStatsDict to card-calc weekPlayerStats format.

    Used to build CardCalcContext from live game data during active games.
    """
    passing = gameStatsDict.get("passing", {})
    rushing = gameStatsDict.get("rushing", {})
    receiving = gameStatsDict.get("receiving", {})
    kicking = gameStatsDict.get("kicking", {})
    return {
        "fantasyPoints": gameStatsDict.get("fantasyPoints", 0),
        "passing_stats": {
            "passYards": passing.get("yards", 0),
            "tds": passing.get("tds", 0),
        },
        "rushing_stats": {
            "runYards": rushing.get("yards", 0),
            "runTds": rushing.get("tds", 0),
        },
        "receiving_stats": {
            "rcvYards": receiving.get("yards", 0),
            "rcvTds": receiving.get("tds", 0),
        },
        "kicking_stats": {
            "fgs": kicking.get("fgs", 0),
            "longest": kicking.get("longest", 0),
        },
    }


def _dbStatsToCardFormat(passingStats: dict, rushingStats: dict,
                         receivingStats: dict, kickingStats: dict,
                         fantasyPoints: float = 0) -> dict:
    """Convert raw DB GamePlayerStats JSON to card-calc weekPlayerStats format.

    DB stores raw gameStatsDict sub-dicts (e.g. passing_stats = {"yards": 100, "tds": 2}).
    Card effects expect the converted format (e.g. passing_stats = {"passYards": 100, "tds": 2}).
    """
    return {
        "fantasyPoints": fantasyPoints,
        "passing_stats": {
            "passYards": (passingStats or {}).get("yards", 0),
            "tds": (passingStats or {}).get("tds", 0),
        },
        "rushing_stats": {
            "runYards": (rushingStats or {}).get("yards", 0),
            "runTds": (rushingStats or {}).get("tds", 0),
        },
        "receiving_stats": {
            "rcvYards": (receivingStats or {}).get("yards", 0),
            "rcvTds": (receivingStats or {}).get("tds", 0),
        },
        "kicking_stats": {
            "fgs": (kickingStats or {}).get("fgs", 0),
            "longest": (kickingStats or {}).get("longest", 0),
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
            FantasyRoster, FantasyRosterSwap, Player, User,
            WeeklyCardBonus, WeeklyPlayerFP, WeeklyModifier
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

            # ── 9. Assemble entries ──
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
                for rp in roster.players:
                    pObj = self._playerManager.getPlayerById(rp.player_id)
                    playerWeeks = perPlayerWeekFP.get(rp.player_id, {})
                    playerSeasonFP = sum(playerWeeks.values())
                    playerWeekFP = playerWeeks.get(currentWeek, 0)
                    # Only count FP earned after locking (offset by points_at_lock)
                    playerEarnedFP = max(0, playerSeasonFP - rp.points_at_lock)
                    seasonEarnedFP += playerEarnedFP
                    currentWeekPlayerFP += playerWeekFP

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
                        "weekFP": round(playerWeekFP, 1),
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
                                stats = _liveStatsToDbFormat(pObj.gameStatsDict)
                                effectiveFP = perPlayerWeekFP.get(
                                    rp.player_id, {}
                                ).get(currentWeek, 0)
                                stats["fantasyPoints"] = effectiveFP
                                cardCalcStats[rp.player_id] = stats
                                weekRawFP += effectiveFP
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
                                cardCalcStats[rp.player_id] = pStats
                                weekRawFP += pStats.get("fantasyPoints", 0)
                                rosterTotalTds += _countPlayerTds(pStats)
                            rosterPlayerRatings[rp.player_id] = (
                                playerRatingsMap.get(rp.player_id, 60)
                            )

                    # Add card player stats if not already in cardCalcStats
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
                    )
                    calcResult = calculateWeekCardBonuses(userEquipped, calcCtx)
                    # New formula: (rosterFP + Σ+FP) × (1 + Σ+FPx) × xFPx₁ × xFPx₂ × ...
                    baseFP = weekRawFP + calcResult.totalBonusFP
                    addMultPool = 1 + calcResult.totalMultBonus
                    xMultProduct = 1.0
                    for xm in calcResult.xMultFactors:
                        xMultProduct *= xm
                    weekCardBonus = round(baseFP * addMultPool * xMultProduct - weekRawFP, 2)
                    # Subtract pre-lock card bonus (if cards were locked mid-game)
                    bonusAtLock = getattr(userEquipped[0], 'card_bonus_at_lock', 0) or 0
                    if bonusAtLock > 0:
                        weekCardBonus = round(weekCardBonus - bonusAtLock, 2)
                    if weekCardBonus < 0:
                        weekCardBonus = 0.0
                    cardBreakdowns = [
                        self._breakdownToDict(b)
                        for b in calcResult.cardBreakdowns
                    ]
                    eqSummary = {
                        "weekRawFP": round(weekRawFP, 1),
                        "totalBonusFP": round(calcResult.totalBonusFP, 2),
                        "totalMultBonus": round(calcResult.totalMultBonus, 2),
                        "xMultFactors": [round(x, 2) for x in calcResult.xMultFactors],
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
        import json as _json

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
            )
        return result

    def _buildCardCalcContext(
        self, session, roster, rosterPlayerIds, userEquipped,
        weekPlayerStats, weekRawFP, rosterPlayerRatings,
        rosterTotalTds, playerPositionMap, userId,
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
        favoriteTeamSeasonLosses = 0
        favoriteTeamInPlayoffs = False
        favoriteTeamWonThisWeek = False
        favoriteTeamOpponentElo = 1500.0
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
                favoriteTeamSeasonLosses = favStats.get('losses', 0)
                favoriteTeamWonThisWeek = teamResults.get(userFavoriteTeamId, False)

                # Big plays from live games
                if sm and sm.currentSeason and sm.currentSeason.activeGames:
                    for game in sm.currentSeason.activeGames:
                        homeTeam = getattr(game, 'homeTeam', None)
                        awayTeam = getattr(game, 'awayTeam', None)
                        hId = getattr(homeTeam, 'id', None)
                        aId = getattr(awayTeam, 'id', None)
                        if userFavoriteTeamId in (hId, aId):
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

        return CardCalcContext(
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
            favoriteTeamSeasonLosses=favoriteTeamSeasonLosses,
            favoriteTeamInPlayoffs=favoriteTeamInPlayoffs,
            favoriteTeamWonThisWeek=favoriteTeamWonThisWeek,
            favoriteTeamOpponentElo=favoriteTeamOpponentElo,
            favoriteTeamBigPlays=favoriteTeamBigPlays,
            favoriteTeamGameFinal=favoriteTeamGameFinal,
            rosterUnchangedWeeks=rosterUnchangedWeeks,
            teamResults=teamResults,
            playerPerformanceRatings=playerPerfRatings,
            activeModifier=activeModifier,
            unusedSwaps=roster.swaps_available or 0,
        )

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
            "primaryXMult": b.primaryXMult,
            "matchMultiplied": b.matchMultiplied,
            "matchMultiplier": b.matchMultiplier,
            "preMatchFP": b.preMatchFP,
            "preMatchMult": b.preMatchMult,
            "preMatchXMult": b.preMatchXMult,
            "conditionalBonus": b.conditionalBonus,
            "conditionalLabel": b.conditionalLabel,
            "secondaryFP": b.secondaryFP,
            "secondaryFloobits": b.secondaryFloobits,
            "secondaryMult": b.secondaryMult,
            "secondaryXMult": b.secondaryXMult,
            "totalFP": b.totalFP,
            "floobitsEarned": b.floobitsEarned,
            "playerStatLine": b.playerStatLine,
            "equation": b.equation,
        }
