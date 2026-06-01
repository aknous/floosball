"""
Modern Floosball REST API
Uses refactored manager system with clean separation of concerns
"""

from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect, Header, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.gzip import GZipMiddleware
from fastapi.responses import Response, JSONResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import asyncio
import json
from datetime import datetime, timezone

import os
from logger_config import get_logger
from api.websocket_manager import manager as ws_manager
from api.event_models import GameEvent, SeasonEvent, StandingsEvent, SystemEvent, PlayerOffDayEvent
from api_response_builders import (
    TeamResponseBuilder, 
    PlayerResponseBuilder, 
    GameResponseBuilder,
    LeagueResponseBuilder,
    build_success_response,
    build_error_response
)
from avatar_generator import getAvatarGenerator
import floosball_game as FloosGame
# Auth deps used by handlers defined early in the file (e.g. /api/players
# with the 'followed' status filter). Later sections re-import these
# closer to their use; that's fine — module-level imports are idempotent.
from api.auth import getOptionalUser as _getOptionalUser, getCurrentUser as _getCurrentUser
from database.models import User as _User

logger = get_logger("floosball.api")

# Create FastAPI app
app = FastAPI(
    title="Floosball API",
    description="Real-time football simulation with WebSocket support",
    version="2.0.0"
)

# CORS configuration
origins = [
    "http://localhost",
    "http://localhost:3000",
    "http://localhost:3001",
    "http://localhost:5173",  # Vite default
    "https://floosball.com",
    "https://www.floosball.com",
]
# Allow additional origins via env var (comma-separated)
_extraOrigins = os.environ.get('CORS_ORIGINS', '')
if _extraOrigins:
    origins.extend([o.strip() for o in _extraOrigins.split(',') if o.strip()])

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "x-admin-password"],
)
app.add_middleware(GZipMiddleware, minimum_size=500)

@app.get("/health")
async def health_check():
    # Report simulation liveness, not just "the HTTP server is up", so the
    # platform health check and uptime monitors can catch a dead/crashed sim
    # task. During startup floosball_app / simTask may be unset — treat as OK.
    task = getattr(floosball_app, 'simTask', None) if floosball_app is not None else None
    if task is not None and task.done() and not task.cancelled():
        return JSONResponse(status_code=503, content={"status": "degraded", "simRunning": False})
    return {"status": "ok", "simRunning": bool(task is not None and not task.done())}

# Global reference to FloosballApplication (set during startup)
floosball_app = None


def _areGamesStarted() -> bool:
    """True only when at least one game is Active or Final (not just Scheduled).

    Multiple endpoints use this to determine whether roster swaps and card
    equips should be locked.  ``bool(currentSeason.activeGames)`` returns
    True as soon as Scheduled games are created (at week setup), which is
    too early — users should still be able to make changes until the first
    game actually kicks off.
    """
    sm = floosball_app.seasonManager if floosball_app else None
    if not sm or not sm.currentSeason or not sm.currentSeason.activeGames:
        return False
    return any(
        getattr(g, 'status', None) in (FloosGame.GameStatus.Active, FloosGame.GameStatus.Final)
        for g in sm.currentSeason.activeGames
    )


def _areGamesCompleted() -> bool:
    """True when the week's games have finished but the next week hasn't started.

    After all games end, activeGames is cleared and completedWeekGames holds
    the finished games.  Use this to keep fantasy scoring visible between weeks
    (while _areGamesStarted returns False so rosters can be swapped).
    """
    sm = floosball_app.seasonManager if floosball_app else None
    if not sm or not sm.currentSeason:
        return False
    return sm.currentSeason.completedWeekGames is not None


def _areGamesScheduled() -> bool:
    """True when games exist for the current week (Scheduled, Active, or Final).

    This is True from week setup through game completion — covers the pre-game
    window where users should see the card lock banner but games haven't started.
    """
    sm = floosball_app.seasonManager if floosball_app else None
    if not sm or not sm.currentSeason or not sm.currentSeason.activeGames:
        return False
    return len(sm.currentSeason.activeGames) > 0


# ============================================================================
# STARTUP & SHUTDOWN
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """Initialize the application on startup"""
    logger.info("Starting Floosball API server")

    # Register the running event loop so sync code (REST threadpool) can dispatch
    # WebSocket broadcasts via run_coroutine_threadsafe.
    import asyncio as _asyncio
    from api.game_broadcaster import broadcaster as _broadcaster
    _broadcaster.set_main_loop(_asyncio.get_running_loop())

    # Background task: periodic off-day flavor broadcasts. Fires only when
    # no games are live so it surfaces personality between rounds without
    # competing with live play feed.
    _asyncio.create_task(_offDayFlavorLoop())

    # Sweep stale pending pack reveals — users who paid for a pack but never
    # confirmed selection (crash / abandoned tab) get auto-resolved with a
    # random keep-pick so they don't lose the cards they paid for.
    try:
        from database.connection import get_session
        from managers.cardManager import CardManager
        sweepSession = get_session()
        try:
            cm = CardManager(None)
            resolved = cm.cleanupStalePendingPacks(sweepSession, ageHours=24)
            if resolved:
                logger.info(f"Resolved {resolved} stale pending pack opening(s) on startup")
        finally:
            sweepSession.close()
    except Exception as e:
        logger.warning(f"Stale pending-pack sweep failed on startup: {e}")

    # The FloosballApplication will be injected by the main entry point
    # For now, log that we're ready
    logger.info("API server ready - waiting for FloosballApplication initialization")


# Tunables for between-games personality broadcasts.
# Env-override for testing: set FLOOSBALL_OFF_DAY_FAST=1 to speed up
# broadcasts to one every 8s for live debugging. Default cadence (90s,
# 60% chance) is what we want in production.
import os as _os
from collections import deque as _deque
_OFF_DAY_FAST = _os.environ.get('FLOOSBALL_OFF_DAY_FAST', '').lower() in ('1', 'true', 'yes')
OFF_DAY_INTERVAL_SECONDS = 8 if _OFF_DAY_FAST else 90  # how often to consider firing
OFF_DAY_FIRE_CHANCE = 1.0 if _OFF_DAY_FAST else 0.6    # not every tick fires — keeps feed slow
OFF_DAY_QUIET_AFTER_GAME = 60                          # wait this long after last live play

# Ring buffer of recent off-day events for the highlights-feed backfill.
# Frontend reads this on page load so the feed isn't empty until the next
# tick fires. In-memory only — fine since these are flavor.
RECENT_OFF_DAY_LIMIT = 12
_recentOffDayEvents: _deque = _deque(maxlen=RECENT_OFF_DAY_LIMIT)

async def _offDayFlavorLoop():
    """Periodically broadcast a player_off_day event when no games are live.
    Slow drip — feeds the highlights ticker between rounds with personality.

    Per off-day window:
    - Tracks recently-quoted player IDs in `_recentlyQuotedPlayers` so the
      same player doesn't speak twice in a row. The set resets when all
      eligible players have been picked, OR when games start (new window).
    - Clears the recent-events ring buffer once at the moment games start,
      so the next off-day window begins with a fresh feed.
    """
    import asyncio as _asyncio
    import random as _random
    from api.game_broadcaster import broadcaster as _broadcaster

    recentlyQuoted: set[int] = set()
    prevGamesActive = False

    while True:
        try:
            await _asyncio.sleep(OFF_DAY_INTERVAL_SECONDS)
            if not _broadcaster.is_enabled():
                continue
            gamesActive = _areGamesStarted()
            # Transition: idle → active. Wipe the off-day feed and recent set
            # so the next idle window starts fresh.
            if gamesActive and not prevGamesActive:
                _recentOffDayEvents.clear()
                recentlyQuoted.clear()
            prevGamesActive = gamesActive
            if gamesActive:
                continue
            if not floosball_app:
                continue
            if _random.random() > OFF_DAY_FIRE_CHANCE:
                continue
            personalityMgr = getattr(floosball_app, 'personalityManager', None)
            if personalityMgr is None:
                continue
            players = getattr(floosball_app.playerManager, 'activePlayers', None) or []
            # Only rostered players — exclude free agents, prospects, and
            # upcoming rookies. player.team is a team OBJECT for rostered
            # players and the STRING markers 'Free Agent' / 'Prospect' /
            # 'Upcoming Rookie' for everyone else.
            def _isRostered(p):
                if getattr(p, 'is_prospect', False):
                    return False
                team = getattr(p, 'team', None)
                return getattr(team, 'id', None) is not None
            eligible = [p for p in players
                        if getattr(getattr(p, 'attributes', None), 'personality', None)
                        and _isRostered(p)]
            # During playoffs, restrict eligible players to those on teams
            # actually playing this week (or just played). Eliminated teams
            # shouldn't speak. Regular season — everyone is eligible.
            sm = floosball_app.seasonManager if floosball_app else None
            cs = sm.currentSeason if sm else None
            weekGames = (getattr(cs, 'activeGames', None)
                         or getattr(cs, 'completedWeekGames', None) or []) if cs else []
            inPlayoffs = any(getattr(g, 'gameType', '') == 'playoff' for g in weekGames)
            if inPlayoffs:
                playoffTeamIds = set()
                for g in weekGames:
                    if getattr(g, 'gameType', '') == 'playoff':
                        h = getattr(g, 'homeTeam', None)
                        a = getattr(g, 'awayTeam', None)
                        if h is not None: playoffTeamIds.add(getattr(h, 'id', None))
                        if a is not None: playoffTeamIds.add(getattr(a, 'id', None))
                eligible = [p for p in eligible
                            if getattr(getattr(p, 'team', None), 'id', None) in playoffTeamIds]
            if not eligible:
                continue
            # Avoid the same player speaking twice in one off-day window.
            # If everyone has had a turn, recycle.
            unspoken = [p for p in eligible if p.id not in recentlyQuoted]
            if not unspoken:
                recentlyQuoted.clear()
                unspoken = eligible
            player = _random.choice(unspoken)
            payload = personalityMgr.composeOffDay(player)
            if not payload:
                continue
            recentlyQuoted.add(player.id)
            event = PlayerOffDayEvent.offDay(
                playerId=payload.get('playerId'),
                playerName=payload.get('playerName'),
                teamId=payload.get('teamId'),
                teamAbbr=payload.get('teamAbbr'),
                personality=payload.get('personality'),
                text=payload.get('text'),
            )
            # Push into the recent ring buffer so the highlights feed can
            # backfill on page load. Most recent at the LEFT (index 0).
            _recentOffDayEvents.appendleft(event)
            await _broadcaster.broadcast_season_event(event)
        except Exception as e:
            logger.warning(f"off-day flavor loop error: {e}")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("Shutting down Floosball API server")
    
    # Close all WebSocket connections
    stats = ws_manager.get_stats()
    logger.info(f"Closing {stats['total_connections']} WebSocket connections")
    
    # Service container shutdown is handled by main application
    logger.info("API server shutdown complete")


# ============================================================================
# WEBSOCKET ENDPOINTS
# ============================================================================

@app.websocket("/ws/game/{game_id}")
async def game_websocket(websocket: WebSocket, game_id: int):
    """
    WebSocket endpoint for real-time game updates
    
    Streams:
    - Play-by-play updates
    - Score changes
    - Win probability updates
    - Quarter/half transitions
    """
    channel = f"game_{game_id}"
    await ws_manager.connect(websocket, channel, {"game_id": game_id})
    
    try:
        # Send initial connection confirmation
        await ws_manager.send_personal_message(
            SystemEvent.info(f"Connected to game {game_id} updates"),
            websocket
        )
        
        # Keep connection alive with heartbeat
        while True:
            try:
                # Wait for client message or timeout after 30 seconds
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                logger.debug(f"Received from client on game {game_id}: {data}")
            except asyncio.TimeoutError:
                # Send ping to keep connection alive
                try:
                    await websocket.send_json({"type": "ping", "timestamp": datetime.now().isoformat()})
                except:
                    break
            
    except (WebSocketDisconnect, RuntimeError):
        ws_manager.disconnect(websocket, channel)
        logger.info(f"Client disconnected from game {game_id}")


@app.websocket("/ws/season")
async def season_websocket(websocket: WebSocket):
    """
    WebSocket endpoint for season-wide updates
    
    Streams:
    - Week start/end
    - Game completions
    - Standings changes
    - Season progression
    """
    channel = "season"
    await ws_manager.connect(websocket, channel, {"scope": "season"})
    
    try:
        await ws_manager.send_personal_message(
            SystemEvent.info("Connected to season updates"),
            websocket
        )
        
        while True:
            try:
                # Wait for client message or timeout after 30 seconds
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                try:
                    import json as _json
                    msg = _json.loads(data)
                    if msg.get("type") == "identify" and msg.get("userId"):
                        ws_manager.identify(websocket, msg["userId"])
                except Exception:
                    pass
                logger.debug(f"Received from season client: {data}")
            except asyncio.TimeoutError:
                # Send ping to keep connection alive
                try:
                    await websocket.send_json({"type": "ping", "timestamp": datetime.now().isoformat()})
                except:
                    break
            
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        ws_manager.disconnect(websocket, channel)
        logger.info("Client disconnected from season updates")


@app.websocket("/ws/standings")
async def standings_websocket(websocket: WebSocket):
    """
    WebSocket endpoint for live standings updates
    
    Streams:
    - Real-time standings changes as games complete
    - Playoff picture updates
    """
    channel = "standings"
    await ws_manager.connect(websocket, channel, {"scope": "standings"})
    
    try:
        await ws_manager.send_personal_message(
            SystemEvent.info("Connected to standings updates"),
            websocket
        )
        
        while True:
            try:
                # Wait for client message or timeout after 30 seconds
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                logger.debug(f"Received from standings client: {data}")
            except asyncio.TimeoutError:
                # Send ping to keep connection alive
                try:
                    await websocket.send_json({"type": "ping", "timestamp": datetime.now().isoformat()})
                except:
                    break
            
    except (WebSocketDisconnect, RuntimeError):
        ws_manager.disconnect(websocket, channel)
        logger.info("Client disconnected from standings updates")


# ============================================================================
# REST API - TEAMS
# ============================================================================

def _buildCoachDict(team) -> Optional[dict]:
    """Return a coach payload dict for a team, or None if no coach is assigned."""
    coach = getattr(team, 'coach', None)
    if coach is None:
        return None
    return {
        'name': coach.name,
        'overallRating': coach.overallRating,
        'offensiveMind': coach.offensiveMind,
        'defensiveMind': coach.defensiveMind,
        'adaptability': coach.adaptability,
        'aggressiveness': coach.aggressiveness,
        'clockManagement': coach.clockManagement,
        'playerDevelopment': coach.playerDevelopment,
        'scouting': getattr(coach, 'scouting', 80),
        'attitude': getattr(coach, 'attitude', 80),
        'seasonsCoached': coach.seasonsCoached,
    }


@app.get("/api/teams", response_model=Dict[str, Any])
async def get_teams(response: Response, league: Optional[str] = None):
    """
    Get all teams, optionally filtered by league

    Returns:
        List of team objects with basic info and current season stats
    """
    response.headers["Cache-Control"] = "public, max-age=120"
    if floosball_app is None:
        raise HTTPException(status_code=503, detail="Application not initialized")
    
    try:
        teams = floosball_app.teamManager.teams
        
        # Filter by league if specified
        if league:
            teams = [t for t in teams if t.league == league]
        
        # Build response using existing builders
        team_list = []
        for team in teams:
            team_dict = TeamResponseBuilder.buildBasicTeamDict(team)

            # Add standings info
            if team.seasonTeamStats['scoreDiff'] >= 0:
                team_dict['pointDiff'] = f"+{team.seasonTeamStats['scoreDiff']}"
            else:
                team_dict['pointDiff'] = str(team.seasonTeamStats['scoreDiff'])

            team_dict['coach'] = _buildCoachDict(team)
            team_list.append(team_dict)
        
        return build_success_response(team_list)
    
    except Exception as e:
        logger.error(f"Error getting teams: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/teams/{team_id}", response_model=Dict[str, Any])
async def get_team(team_id: int, response: Response):
    """
    Get detailed information about a specific team

    Returns:
        Full team object with ratings, roster, history, and stats
    """
    response.headers["Cache-Control"] = "public, max-age=120"
    if floosball_app is None:
        raise HTTPException(status_code=503, detail="Application not initialized")
    
    try:
        # Find team
        team = next((t for t in floosball_app.teamManager.teams if t.id == team_id), None)
        
        if team is None:
            raise HTTPException(status_code=404, detail=f"Team {team_id} not found")
        
        # Build detailed response
        team_dict = TeamResponseBuilder.buildTeamWithRatings(team)
        team_dict['abbr'] = getattr(team, 'abbr', team.name[:3].upper())
        team_dict['league'] = team.league
        team_dict['leagueChampionships'] = team.leagueChampionships
        team_dict['regularSeasonChampions'] = getattr(team, 'regularSeasonChampions', [])
        team_dict['floosbowlChampionships'] = team.floosbowlChampionships
        team_dict['allTimeStats'] = team.allTimeTeamStats
        # Build history: current season stats + past seasons from DB
        import copy as _copy
        currentStats = _copy.deepcopy(team.seasonTeamStats)
        # Ensure current season number is set (defaults to 0 in teamStatsDict)
        sm = floosball_app.seasonManager if floosball_app else None
        currentSeasonNum = sm.currentSeason.seasonNumber if sm and hasattr(sm, 'currentSeason') and sm.currentSeason else 1
        if currentStats.get('season', 0) == 0:
            currentStats['season'] = currentSeasonNum

        # Load past season history from DB (statArchive is runtime-only)
        pastSeasons = []
        try:
            from database.connection import get_session
            from database.models import TeamSeasonStats as DBTeamSeasonStats
            dbSession = get_session()
            pastRows = dbSession.query(DBTeamSeasonStats).filter(
                DBTeamSeasonStats.team_id == team.id,
                DBTeamSeasonStats.season < currentSeasonNum
            ).order_by(DBTeamSeasonStats.season.desc()).all()
            for row in pastRows:
                pastEntry = {
                    'season': row.season,
                    'elo': row.elo or 1500,
                    'overallRating': 0,
                    'wins': row.wins,
                    'losses': row.losses,
                    'winPerc': row.win_percentage or 0.0,
                    'streak': row.streak or 0,
                    'scoreDiff': row.score_differential or 0,
                    'madePlayoffs': row.made_playoffs,
                    'leagueChamp': row.league_champion,
                    'floosbowlChamp': row.floosball_champion,
                    'topSeed': row.top_seed,
                    'Offense': row.offense_stats or {},
                    'Defense': row.defense_stats or {},
                }
                pastSeasons.append(pastEntry)
            dbSession.close()
        except Exception:
            # Fallback to runtime archive if DB query fails
            pastSeasons = team.statArchive or []

        team_dict['history'] = [currentStats] + pastSeasons
        team_dict['coach'] = _buildCoachDict(team)

        # Roster
        # Pre-fetch rating history for all roster players in one query so the
        # response can inline sparkline data without N round-trips.
        rosterPlayerIds = [p.id for p in team.rosterDict.values() if p is not None]
        rosterHistoryByPlayer: Dict[int, List[Dict[str, int]]] = {}
        if rosterPlayerIds:
            try:
                from database.connection import get_session as _rs_gs
                from database.models import PlayerRatingHistory as _RH
                _rs = _rs_gs()
                try:
                    _rows = _rs.query(_RH).filter(
                        _RH.player_id.in_(rosterPlayerIds)
                    ).order_by(_RH.player_id, _RH.season).all()
                    for r in _rows:
                        rosterHistoryByPlayer.setdefault(r.player_id, []).append({
                            "season": r.season, "rating": r.rating,
                        })
                finally:
                    _rs.close()
            except Exception:
                pass  # history is optional — skip on error

        sm = floosball_app.seasonManager if floosball_app else None
        currentSeasonNum = sm.currentSeason.seasonNumber if sm and sm.currentSeason else 0

        roster = {}
        for pos, player in team.rosterDict.items():
            if player is not None:
                # Append current live rating as the latest point so sparklines
                # reflect in-season state even before the next snapshot fires
                history = list(rosterHistoryByPlayer.get(player.id, []))
                liveRating = int(round(player.playerRating or 0))
                if currentSeasonNum and (not history or history[-1]["season"] != currentSeasonNum):
                    history.append({"season": currentSeasonNum, "rating": liveRating})

                # Pull mood / personality / attitude — surfaced in the
                # team-page roster dropdown so users can see why a high-rated
                # player might underperform (form state, fatigue, mood). These
                # fields already exist on player.attributes; just plumbing them
                # to the roster response.
                playerMood = None
                playerMoodTier = None
                try:
                    if getattr(player.attributes, 'personality', None):
                        playerMood, playerMoodTier = player.attributes.getMood()
                except Exception:
                    pass

                roster[pos] = {
                    'id': player.id,
                    'name': player.name,
                    'position': player.position.name if hasattr(player.position, 'name') else str(player.position),
                    'rating': player.playerRating,
                    'ratingStars': PlayerResponseBuilder.calculateStarRating(player.playerRating),
                    'offensiveRating': player.offensiveRating,
                    'offensiveRatingStars': PlayerResponseBuilder.calculateStarRating(player.offensiveRating),
                    'defensiveRating': player.defensiveRating,
                    'defensiveRatingStars': PlayerResponseBuilder.calculateStarRating(player.defensiveRating),
                    'defensivePosition': player.defensivePosition.value if player.defensivePosition else None,
                    'termRemaining': player.termRemaining,
                    'tier': player.playerTier.name if hasattr(player.playerTier, 'name') else str(player.playerTier),
                    'serviceTime': player.serviceTime.value if hasattr(player.serviceTime, 'value') else str(player.serviceTime),
                    'fatigue': round((getattr(player.attributes, 'fatigue', 0.0) or 0.0) * 100, 1),
                    'resilience': getattr(player.attributes, 'resilience', 80),
                    'mood': playerMood,
                    'moodTier': playerMoodTier,
                    'personality': getattr(player.attributes, 'personality', None),
                    'attitude': getattr(player.attributes, 'attitude', None),
                    'ratingHistory': history,
                }
            else:
                roster[pos] = None
        team_dict['roster'] = roster

        # Schedule (regular season games assigned to this team)
        teamSchedule = []
        for game in getattr(team, 'schedule', []):
            try:
                if not hasattr(game, 'homeTeam'):
                    continue
                isHome = game.homeTeam.id == team_id
                opponent = game.awayTeam if isHome else game.homeTeam
                teamScore = game.homeScore if isHome else game.awayScore
                oppScore = game.awayScore if isHome else game.homeScore
                status = game.status.name if hasattr(game.status, 'name') else str(game.status)
                result = None
                if status == 'Final':
                    result = 'W' if teamScore > oppScore else 'L'
                teamSchedule.append({
                    'gameId': game.id,
                    'isHome': isHome,
                    'week': getattr(game, 'week', None),
                    'opponent': {
                        'id': opponent.id,
                        'name': opponent.name,
                        'city': opponent.city,
                        'abbr': getattr(opponent, 'abbr', opponent.name[:3].upper()),
                    },
                    'teamScore': teamScore,
                    'oppScore': oppScore,
                    'status': status,
                    'result': result,
                })
            except Exception:
                continue
        team_dict['schedule'] = teamSchedule

        # Funding details (current season) — tiers are relative quartiles across
        # the league, so "next-tier threshold" is computed from live standings
        # rather than a fixed Floobit amount.
        try:
            from database.connection import get_session as _gs
            from database.models import TeamFunding
            from constants import FUNDING_TIER_NAMES
            fundSession = _gs()
            try:
                # Get the latest funding record for this team
                latestFunding = fundSession.query(TeamFunding).filter_by(
                    team_id=team_id
                ).order_by(TeamFunding.season.desc()).first()
                if latestFunding:
                    effectiveFunding = latestFunding.effective_funding or 0
                    currentTier = latestFunding.funding_tier or 'SMALL_MARKET'
                    currentRank = latestFunding.tier_rank or 4

                    # Threshold to climb one tier — computed from the current
                    # league's fair-share (total funding / team count) and the
                    # ratio required by the tier above this team. Matches the
                    # share-of-league logic used in _assignFundingTiers.
                    from constants import FUNDING_TIER_THRESHOLDS as _TT
                    seasonRecs = fundSession.query(TeamFunding).filter_by(
                        season=latestFunding.season
                    ).all()
                    totalLeague = sum((r.effective_funding or 0) for r in seasonRecs)
                    fairShare = max(1, totalLeague / max(1, len(seasonRecs)))
                    nextTierThreshold = None
                    nextTierName = None
                    progressToNextTier = None
                    if currentRank > 1:
                        nextTierName = FUNDING_TIER_NAMES[currentRank - 2]
                        nextTierRatio = _TT[nextTierName]
                        # Funding value that clears the next-tier threshold today
                        nextTierThreshold = int(round(nextTierRatio * fairShare))
                        if nextTierThreshold > effectiveFunding:
                            # Progress fraction across this tier's band (from
                            # current-tier threshold up to next-tier threshold)
                            currentTierRatio = _TT[FUNDING_TIER_NAMES[currentRank - 1]]
                            currentTierThreshold = currentTierRatio * fairShare
                            tierRange = max(1, nextTierThreshold - currentTierThreshold)
                            gap = nextTierThreshold - effectiveFunding
                            progressToNextTier = round(min(1.0, max(0.0, 1.0 - gap / tierRange)), 2)
                        else:
                            progressToNextTier = 1.0

                    # Per-tier thresholds — lets the frontend price any tier's
                    # entry cost without a second round-trip. Used when the
                    # displayed "next threshold" needs to follow where the
                    # team's projected funding lands (vs. the locked current
                    # tier), e.g. a team currently MID but projected MEGA
                    # should show the MEGA threshold, not the LARGE one.
                    tierThresholds = {
                        name: int(round(_TT[name] * fairShare))
                        for name in FUNDING_TIER_NAMES
                    }

                    team_dict['funding'] = {
                        'season': latestFunding.season,
                        'baselineFunding': latestFunding.baseline_funding or 0,
                        'fanContributions': latestFunding.fan_contributions or 0,
                        'currentFunding': latestFunding.current_funding or 0,
                        'carriedFunding': latestFunding.carried_funding or 0,
                        'effectiveFunding': effectiveFunding,
                        'tier': currentTier,
                        'tierRank': currentRank,
                        'nextTierThreshold': nextTierThreshold,
                        'nextTierName': nextTierName,
                        'progressToNextTier': progressToNextTier,
                        'fairShare': int(round(fairShare)),
                        'tierThresholds': tierThresholds,
                    }
            finally:
                fundSession.close()
        except Exception:
            pass  # Funding data is optional — skip if unavailable

        return build_success_response(team_dict)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting team {team_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.options("/api/teams/{team_id}/avatar")
async def avatar_options(team_id: int):
    """Handle CORS preflight requests for avatar endpoint"""
    return Response(
        content="",
        status_code=200,
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, OPTIONS",
            "Access-Control-Allow-Headers": "*",
            "Access-Control-Max-Age": "86400"
        }
    )


@app.get("/api/teams/{team_id}/avatar")
async def get_team_avatar(team_id: int, size: int = Query(default=32, ge=16, le=1024), format: str = Query(default="svg", regex="^(svg|png)$")):
    """
    Generate and return avatar for a team.
    Supports SVG (default) and PNG formats.
    """
    if floosball_app is None:
        raise HTTPException(status_code=503, detail="Application not initialized")

    try:
        # Find team
        team = next((t for t in floosball_app.teamManager.teams if t.id == team_id), None)

        if team is None:
            raise HTTPException(status_code=404, detail=f"Team {team_id} not found")

        # Get avatar generator
        avatarGen = getAvatarGenerator()

        # Get team colors with fallbacks
        primaryColor = team.color
        secondaryColor = getattr(team, 'secondaryColor', team.color)
        tertiaryColor = getattr(team, 'tertiaryColor', team.color)

        cacheHeaders = {
            "Cache-Control": "public, max-age=86400, immutable",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, OPTIONS",
            "Access-Control-Allow-Headers": "*"
        }

        if format == "png":
            pngBytes = avatarGen.getPng(
                team.name, primaryColor, secondaryColor, tertiaryColor, size, team.id
            )
            return Response(content=pngBytes, media_type="image/png", headers=cacheHeaders)

        # Default: SVG
        svg = avatarGen.generateTeamAvatar(
            team.name, primaryColor, secondaryColor, tertiaryColor, size, team.id
        )
        return Response(content=svg, media_type="image/svg+xml", headers=cacheHeaders)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating avatar for team {team_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/logo")
async def get_league_logo(size: int = Query(default=256, ge=16, le=1024), format: str = Query(default="svg", regex="^(svg|png)$")):
    """Return the Floosball league logo as SVG or PNG."""
    try:
        avatarGen = getAvatarGenerator()
        teamColors = None
        if floosball_app and hasattr(floosball_app, 'teamManager'):
            teamColors = [t.color for t in floosball_app.teamManager.teams if t.color]
        cacheHeaders = {
            "Cache-Control": "public, max-age=86400, immutable",
            "Content-Disposition": "inline",
            "Access-Control-Allow-Origin": "*",
        }
        if format == "png":
            pngBytes = avatarGen.getLeagueLogoPng(size, teamColors)
            return Response(content=pngBytes, media_type="image/png", headers=cacheHeaders)
        svg = avatarGen.generateLeagueLogo(size, teamColors)
        return Response(content=svg, media_type="image/svg+xml", headers=cacheHeaders)
    except Exception as e:
        logger.error(f"Error generating league logo: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# REST API - PLAYERS
# ============================================================================

@app.get("/api/players", response_model=Dict[str, Any])
async def get_players(
    response: Response,
    position: Optional[str] = None,
    team_id: Optional[int] = None,
    status: Optional[str] = None,  # 'active', 'retired', 'fa', 'hof', 'followed'
    user: Optional[_User] = Depends(_getOptionalUser),
):
    """
    Get players with optional filters

    Args:
        position: Filter by position (QB, RB, WR, etc.)
        team_id: Filter by team ID
        status: Filter by status (active, retired, fa, hof, followed)

    Returns:
        List of player objects
    """
    # 'followed' is per-user, so it can't share the public cache.
    response.headers["Cache-Control"] = "no-store" if status == 'followed' else "public, max-age=120"
    if floosball_app is None:
        raise HTTPException(status_code=503, detail="Application not initialized")

    try:
        # Determine which player list to use based on status
        if status == 'retired':
            players = floosball_app.playerManager.retiredPlayers
        elif status == 'hof':
            players = floosball_app.playerManager.hallOfFame
        elif status == 'fa':
            # Active FA pool excludes prospects — they're in team pipelines.
            players = [p for p in floosball_app.playerManager.freeAgents
                       if not getattr(p, 'is_prospect', False)]
        elif status == 'prospects':
            players = [p for p in floosball_app.playerManager.activePlayers
                       if getattr(p, 'is_prospect', False)]
        elif status == 'followed':
            if user is None:
                raise HTTPException(status_code=401, detail="Sign in to view followed players")
            from database.models import FollowedPlayer
            from database.connection import get_session
            _session = get_session()
            try:
                followedIds = {
                    r[0] for r in _session.query(FollowedPlayer.player_id)
                    .filter_by(user_id=user.id).all()
                }
            finally:
                _session.close()
            # Pull from every pool — followed players can be active, FA, or
            # retired. Dedupe by id since pools may overlap transiently.
            pools = (
                floosball_app.playerManager.activePlayers
                + floosball_app.playerManager.freeAgents
                + floosball_app.playerManager.retiredPlayers
            )
            seen = set()
            players = []
            for p in pools:
                if p.id in followedIds and p.id not in seen:
                    seen.add(p.id)
                    players.append(p)
        else:  # 'active' or None
            players = floosball_app.playerManager.activePlayers
        
        # Apply filters
        if position:
            players = [p for p in players if p.position.name == position.upper()]
        
        if team_id is not None:
            players = [p for p in players if hasattr(p.team, 'id') and p.team.id == team_id]
        
        # Build response
        player_list = []
        for player in players:
            player_dict = PlayerResponseBuilder.buildBasicPlayerDict(player)
            player_dict['rank'] = player.serviceTime.value if hasattr(player.serviceTime, 'value') else player.serviceTime
            player_dict['seasons'] = player.seasonsPlayed

            # Merge season + in-game stats for live accuracy
            sd = player.seasonStatsDict
            gd = player.gameStatsDict
            fantasyPts = round(sd.get('fantasyPoints', 0) + gd.get('fantasyPoints', 0), 1)

            passing = sd.get('passing', {})
            rushing = sd.get('rushing', {})
            receiving = sd.get('receiving', {})
            kicking = sd.get('kicking', {})

            passAtt = passing.get('att', 0)
            passComp = passing.get('comp', 0)
            rushCarries = rushing.get('carries', 0)
            rcvTargets = receiving.get('targets', 0)
            fgAtt = kicking.get('fgAtt', 0)
            fgMade = kicking.get('fgs', 0)

            player_dict['currentStats'] = {
                'fantasyPoints': fantasyPts,
                'gamesPlayed': player.gamesPlayed,
                'passing': {
                    'comp': passComp,
                    'att': passAtt,
                    'compPerc': round(passComp / passAtt * 100, 1) if passAtt > 0 else 0,
                    'yards': passing.get('yards', 0),
                    'tds': passing.get('tds', 0),
                    'ints': passing.get('ints', 0),
                    'ypc': passing.get('ypc', 0),
                },
                'rushing': {
                    'carries': rushCarries,
                    'yards': rushing.get('yards', 0),
                    'ypc': rushing.get('ypc', 0),
                    'tds': rushing.get('tds', 0),
                    'fumblesLost': rushing.get('fumblesLost', 0),
                },
                'receiving': {
                    'receptions': receiving.get('receptions', 0),
                    'targets': rcvTargets,
                    'rcvPerc': round(receiving.get('receptions', 0) / rcvTargets * 100, 1) if rcvTargets > 0 else 0,
                    'yards': receiving.get('yards', 0),
                    'ypr': receiving.get('ypr', 0),
                    'tds': receiving.get('tds', 0),
                },
                'kicking': {
                    'fgs': fgMade,
                    'fgAtt': fgAtt,
                    'fgPerc': round(fgMade / fgAtt * 100, 1) if fgAtt > 0 else 0,
                },
            }
            player_list.append(player_dict)
        
        return build_success_response(player_list)
    
    except Exception as e:
        logger.error(f"Error getting players: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/players/{player_id}", response_model=Dict[str, Any])
async def get_player(player_id: int, response: Response):
    """
    Get detailed information about a specific player

    Returns:
        Full player object with attributes, stats, and history
    """
    response.headers["Cache-Control"] = "public, max-age=120"
    if floosball_app is None:
        raise HTTPException(status_code=503, detail="Application not initialized")
    
    try:
        # Search all player lists
        player = None
        for player_list in [
            floosball_app.playerManager.activePlayers,
            floosball_app.playerManager.retiredPlayers,
            floosball_app.playerManager.hallOfFame
        ]:
            player = next((p for p in player_list if p.id == player_id), None)
            if player:
                break
        
        if player is None:
            raise HTTPException(status_code=404, detail=f"Player {player_id} not found")
        
        # Build detailed response
        player_dict = PlayerResponseBuilder.buildPlayerWithAttributes(player)

        player_dict['rank'] = player.serviceTime.value if hasattr(player.serviceTime, 'value') else player.serviceTime
        player_dict['number'] = player.currentNumber
        player_dict['ratingValue'] = player.playerRating
        player_dict['championships'] = player.leagueChampionships
        player_dict['mvpAwards'] = getattr(player, 'mvpAwards', [])
        player_dict['fatigue'] = round((getattr(player.attributes, 'fatigue', 0.0) or 0.0) * 100, 1)
        # Build stats history: current live season + past seasons from DB
        sm = floosball_app.seasonManager
        currentSeasonNum = sm.currentSeason.seasonNumber if sm.currentSeason else None
        seasonIsComplete = sm.currentSeason.isComplete if sm.currentSeason else True
        team = player.team
        hasTeamObj = team and not isinstance(team, str)
        teamName = team.name if hasTeamObj else (team if isinstance(team, str) else 'FA')
        teamColor = team.color if hasTeamObj else '#94a3b8'

        # Load seasons from DB
        allSeasons = []
        try:
            from database.connection import get_session
            from database.models import PlayerSeasonStats as DBPlayerSeasonStats, Team as DBTeam
            dbSession = get_session()
            # If season is complete (offseason), load ALL seasons from DB
            # If season is in progress, load only past seasons (current comes from live stats)
            if seasonIsComplete and currentSeasonNum:
                seasonFilter = DBPlayerSeasonStats.season <= currentSeasonNum
            else:
                seasonFilter = DBPlayerSeasonStats.season < currentSeasonNum if currentSeasonNum else True
            pastRows = dbSession.query(DBPlayerSeasonStats).filter(
                DBPlayerSeasonStats.player_id == player.id,
                seasonFilter
            ).order_by(DBPlayerSeasonStats.season.desc()).all()
            for row in pastRows:
                # Look up team name/color
                rowTeamName = 'FA'
                rowTeamColor = '#94a3b8'
                if row.team_id:
                    dbTeam = dbSession.get(DBTeam, row.team_id)
                    if dbTeam:
                        rowTeamName = dbTeam.name
                        rowTeamColor = dbTeam.color or '#94a3b8'
                pastEntry = {
                    'season': row.season,
                    'team': rowTeamName,
                    'color': rowTeamColor,
                    'gp': row.games_played or 0,
                    'fantasyPoints': row.fantasy_points or 0,
                    'passing': row.passing_stats or {},
                    'rushing': row.rushing_stats or {},
                    'receiving': row.receiving_stats or {},
                    'kicking': row.kicking_stats or {},
                    'defense': row.defense_stats or {},
                }
                allSeasons.append(pastEntry)
            dbSession.close()
        except Exception:
            allSeasons = list(player.seasonStatsArchive) if player.seasonStatsArchive else []

        # Only prepend live current-season entry if the season is still in progress
        if not seasonIsComplete and currentSeasonNum:
            currentSeasonEntry = dict(player.seasonStatsDict)
            currentSeasonEntry['season'] = currentSeasonNum
            currentSeasonEntry['team'] = teamName
            currentSeasonEntry['color'] = teamColor
            currentSeasonEntry['gp'] = player.gamesPlayed
            player_dict['stats'] = [currentSeasonEntry] + allSeasons
        else:
            player_dict['stats'] = allSeasons
        player_dict['allTimeStats'] = player.careerStatsDict

        # Personality quotes — latest one for the hover tooltip,
        # full list shown on the player profile page via /quotes endpoint.
        pm = floosball_app.personalityManager
        if pm:
            player_dict['latestQuote'] = pm.getLatestQuote(player.id)

        return build_success_response(player_dict)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting player {player_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/players/{player_id}/quotes", response_model=Dict[str, Any])
async def get_player_quotes(player_id: int, limit: int = 10):
    """Recent personality quotes for a player. Powers the Recent Moments
    box on the player profile page. In-memory ring buffer; lost on
    server restart since these are flavor, not authoritative."""
    if floosball_app is None:
        raise HTTPException(status_code=503, detail="Application not initialized")
    pm = floosball_app.personalityManager
    if pm is None:
        return build_success_response([])
    quotes = pm.getRecentQuotes(player_id, limit=max(1, min(limit, 50)))
    return build_success_response(quotes)


@app.get("/api/debug/anomaly-state", response_model=Dict[str, Any])
async def debug_anomaly_state():
    """Testing aid — dump current league anomaly state + top-attention
    players. NOT for production users; intentionally not gated on admin
    so local sims can poke at it freely. Includes the hidden Cracking
    threshold — use only for testing."""
    if floosball_app is None:
        raise HTTPException(status_code=503, detail="Application not initialized")
    sm = floosball_app.seasonManager
    seasonNumber = sm.currentSeason.seasonNumber if sm and sm.currentSeason else 0
    currentWeek = sm.currentSeason.currentWeek if sm and sm.currentSeason else 0
    from database.connection import get_session
    from database.models import LeagueAnomalyState, PlayerAttention, AnomalyState, Player
    from managers.anomalyManager import isCrackingWeek, getCrackingMultiplier
    session = get_session()
    try:
        state = session.query(LeagueAnomalyState).filter_by(season=seasonNumber).first()
        topAttn = (
            session.query(PlayerAttention, Player.name)
            .join(Player, Player.id == PlayerAttention.player_id)
            .filter(PlayerAttention.season == seasonNumber)
            .order_by(PlayerAttention.score.desc())
            .limit(20)
            .all()
        )
        awakeneds = (
            session.query(AnomalyState, Player.name)
            .join(Player, Player.id == AnomalyState.player_id)
            .filter(AnomalyState.season == seasonNumber)
            .filter(AnomalyState.state.in_(['rampant', 'awakened', 'cleansed']))
            .all()
        )
        return build_success_response({
            'season': seasonNumber,
            'currentWeek': currentWeek,
            'isCrackingWeek': isCrackingWeek(seasonNumber, currentWeek),
            'crackingMultiplier': getCrackingMultiplier(seasonNumber, currentWeek),
            'league': ({
                'aggregateScore': float(state.aggregate_score),
                'threshold': state.threshold,
                'progressPct': round(float(state.aggregate_score) / max(1, state.threshold) * 100, 1),
                'crackingsThisSeason': state.thinnings_this_season,
                'lastCrackingWeek': state.last_thinning_week,
                'lastResetWeek': state.last_reset_week,
                'suppressionWindowEndsWeek': state.suppression_window_ends_week,
                'recentPatches': (state.cores_patches_applied or [])[-5:],
            } if state else None),
            'topAttention': [
                {
                    'playerId': r[0].player_id,
                    'playerName': r[1],
                    'score': round(float(r[0].score), 1),
                    'overCapCarry': round(float(r[0].over_cap_carry), 1),
                    'peakScore': round(float(r[0].peak_score), 1),
                }
                for r in topAttn
            ],
            'elevatedPlayers': [
                {
                    'playerId': r[0].player_id,
                    'playerName': r[1],
                    'state': r[0].state,
                    'ability': r[0].ability,
                    'abilityTier': r[0].ability_tier,
                    'awakenedAtWeek': r[0].awakened_at_week,
                }
                for r in awakeneds
            ],
        })
    finally:
        session.close()


@app.post("/api/debug/anomaly-bump", response_model=Dict[str, Any])
async def debug_anomaly_bump(player_id: int, amount: float = 50.0):
    """Testing aid — force-add attention to a specific player. Skips
    the weekly tick / engagement-source aggregation. Useful for jumping
    a player past Awakening on demand. NOT gated on admin."""
    if floosball_app is None:
        raise HTTPException(status_code=503, detail="Application not initialized")
    sm = floosball_app.seasonManager
    seasonNumber = sm.currentSeason.seasonNumber if sm and sm.currentSeason else 0
    from database.connection import get_session
    from database.models import PlayerAttention
    session = get_session()
    try:
        row = session.query(PlayerAttention).filter_by(
            player_id=player_id, season=seasonNumber,
        ).first()
        if row is None:
            row = PlayerAttention(
                player_id=player_id, season=seasonNumber,
                score=0.0, over_cap_carry=0.0, peak_score=0.0,
            )
            session.add(row)
        row.score = float(row.score) + amount
        if row.score > float(row.peak_score):
            row.peak_score = float(row.score)
        session.commit()
        return build_success_response({
            'playerId': player_id,
            'newScore': float(row.score),
        })
    finally:
        session.close()


@app.post("/api/debug/anomaly-tick", response_model=Dict[str, Any])
async def debug_anomaly_tick():
    """Testing aid — fire the weekly anomaly aggregation NOW instead of
    waiting for the next week_start. Useful in fast modes where the
    week loop already finished by the time you want to poke at state."""
    if floosball_app is None:
        raise HTTPException(status_code=503, detail="Application not initialized")
    sm = floosball_app.seasonManager
    seasonNumber = sm.currentSeason.seasonNumber if sm and sm.currentSeason else 0
    currentWeek = sm.currentSeason.currentWeek if sm and sm.currentSeason else 0
    from managers.anomalyManager import weeklyTick
    weeklyTick(seasonNumber, currentWeek)
    return build_success_response({'fired': True, 'season': seasonNumber, 'week': currentWeek})


@app.get("/api/players/{player_id}/anomaly", response_model=Dict[str, Any])
async def get_player_anomaly(player_id: int):
    """Anomaly state for a player in the current season.

    Returns the state ladder label (stable / stirring / erratic /
    rampant / awakened / cleansed) and, for awakened players, the
    rolled ability + tier. Intentionally does NOT expose the raw
    attention score — users see symptoms (the badge label, the
    occasional glitch line in plays) but not the underlying cause.

    Returns null if the player has no anomaly record this season
    (i.e., still Stable — never crossed Stirring threshold).
    """
    if floosball_app is None:
        raise HTTPException(status_code=503, detail="Application not initialized")
    sm = floosball_app.seasonManager
    seasonNumber = sm.currentSeason.seasonNumber if sm and sm.currentSeason else 0
    from database.connection import get_session
    from database.models import AnomalyState
    session = get_session()
    try:
        row = session.query(AnomalyState).filter_by(
            player_id=player_id, season=seasonNumber,
        ).first()
        if row is None or row.state in (None, 'stable'):
            return build_success_response(None)
        return build_success_response({
            'state': row.state,
            'ability': row.ability,
            'abilityTier': row.ability_tier,
            'awakenedAtWeek': row.awakened_at_week,
            'seasonsCarried': row.seasons_carried,
        })
    finally:
        session.close()


@app.get("/api/recent-off-day", response_model=Dict[str, Any])
async def get_recent_off_day(limit: int = 30):
    """Recent off-day broadcast events for the highlights feed backfill.
    Frontend reads this on mount so the feed isn't empty before the next
    tick fires. In-memory ring buffer."""
    capped = max(1, min(limit, RECENT_OFF_DAY_LIMIT))
    return build_success_response(list(_recentOffDayEvents)[:capped])


@app.get("/api/quotes/offday", response_model=Dict[str, Any])
async def get_personalized_off_day_quotes(
    count: int = 1,
    user: Optional[_User] = Depends(_getOptionalUser),
):
    """Compose off-day quotes for players the calling user cares about
    (favorite team roster, fantasy roster, followed players). Frontend
    polls this when no games are live so the feed always surfaces
    relevant content instead of broadcast-and-filter.

    Returns the same payload shape as the WS `player_off_day` event.
    Falls back to an empty array when the user has no scope (anon,
    no favorite team / fantasy roster / followed players) or when
    no eligible player happens to be rostered right now.
    """
    if floosball_app is None:
        raise HTTPException(status_code=503, detail="Application not initialized")
    personalityMgr = getattr(floosball_app, 'personalityManager', None)
    if personalityMgr is None or user is None:
        return build_success_response([])

    capped = max(1, min(count, 5))

    # Build the user's player scope: favorite-team roster + fantasy
    # roster + followed players. We resolve through the in-memory
    # activePlayers list so personality data is already attached.
    from database.models import FollowedPlayer, FantasyRoster, FantasyRosterPlayer, User as _UserModel
    from database.connection import get_session as _getSession

    scopedIds: set[int] = set()
    sm = floosball_app.seasonManager
    currentSeason = sm.currentSeason.seasonNumber if sm and sm.currentSeason else 1

    _s = _getSession()
    try:
        dbUser = _s.query(_UserModel).filter_by(id=user.id).first()
        if dbUser and dbUser.favorite_team_id:
            for p in floosball_app.playerManager.activePlayers:
                team = getattr(p, 'team', None)
                if getattr(team, 'id', None) == dbUser.favorite_team_id:
                    scopedIds.add(p.id)
        # Fantasy roster — current season's rostered player ids
        roster = _s.query(FantasyRoster).filter_by(
            user_id=user.id, season=currentSeason,
        ).first()
        if roster:
            for rp in _s.query(FantasyRosterPlayer).filter_by(roster_id=roster.id).all():
                if rp.player_id is not None:
                    scopedIds.add(rp.player_id)
        for fid, in _s.query(FollowedPlayer.player_id).filter_by(user_id=user.id).all():
            scopedIds.add(fid)
    finally:
        _s.close()

    if not scopedIds:
        return build_success_response([])

    def _isRostered(p):
        if getattr(p, 'is_prospect', False):
            return False
        team = getattr(p, 'team', None)
        return getattr(team, 'id', None) is not None

    eligible = [
        p for p in floosball_app.playerManager.activePlayers
        if p.id in scopedIds
        and getattr(getattr(p, 'attributes', None), 'personality', None)
        and _isRostered(p)
    ]
    if not eligible:
        return build_success_response([])

    import random as _random
    pickN = min(capped, len(eligible))
    chosen = _random.sample(eligible, pickN)

    out = []
    for pl in chosen:
        payload = personalityMgr.composeOffDay(pl)
        if not payload:
            continue
        out.append(PlayerOffDayEvent.offDay(
            playerId=payload.get('playerId'),
            playerName=payload.get('playerName'),
            teamId=payload.get('teamId'),
            teamAbbr=payload.get('teamAbbr'),
            personality=payload.get('personality'),
            text=payload.get('text'),
        ))
    return build_success_response(out)


# ============================================================================
# REST API - SEASON & GAMES
# ============================================================================

@app.get("/api/currentGames", response_model=List[Dict[str, Any]])
async def get_current_games(response: Response):
    """
    Get all currently scheduled, active, and recently completed games

    Returns:
        List of games with real-time scores, status, and win probabilities
    """
    response.headers["Cache-Control"] = "public, max-age=3"
    if floosball_app is None:
        raise HTTPException(status_code=503, detail="Application not initialized")
    
    try:
        season_mgr = floosball_app.seasonManager
        current_season = season_mgr.currentSeason
        
        if current_season is None or not hasattr(current_season, 'activeGames'):
            return []

        # Use activeGames if available, otherwise fall back to completed games
        # so finished games remain visible until the next week starts
        displayGames = current_season.activeGames
        if not displayGames:
            displayGames = getattr(current_season, 'completedWeekGames', None)
        if not displayGames:
            return []
        
        # Compute isFeatured for each game: elite matchup (both ELO >= 1570)
        # OR playoff bubble battle (both teams near the 6-spot cutline, late season only)
        PLAYOFF_SPOTS = 6
        ELITE_ELO = 1570
        BUBBLE_WEEK_MIN = 18  # bubble battle only meaningful in the final stretch
        currentWeek = getattr(current_season, 'currentWeek', 0)
        isRegularSeason = isinstance(currentWeek, int) and 1 <= currentWeek <= 28
        lateRegularSeason = isRegularSeason and currentWeek >= BUBBLE_WEEK_MIN

        teamLeaguePos = {}   # {team_id: 1-indexed position in their league}
        teamLeagueName = {}  # {team_id: league name} for same-league check
        for league in floosball_app.leagueManager.leagues:
            sortedTeams = sorted(league.teamList,
                                 key=lambda t: (-t.seasonTeamStats['wins'], t.seasonTeamStats['losses']))
            for pos, team in enumerate(sortedTeams, 1):
                teamLeaguePos[team.id] = pos
                teamLeagueName[team.id] = league.name

        for game in displayGames:
            # All playoff games are inherently featured — skip the designation
            if getattr(game, 'gameType', '') == 'playoff':
                game.isFeatured = False
                continue
            homeElo = getattr(game, 'homeTeamElo', getattr(game.homeTeam, 'elo', 1500))
            awayElo = getattr(game, 'awayTeamElo', getattr(game.awayTeam, 'elo', 1500))
            homePos = teamLeaguePos.get(game.homeTeam.id, 99)
            awayPos = teamLeaguePos.get(game.awayTeam.id, 99)
            eliteMatchup = isRegularSeason and homeElo >= ELITE_ELO and awayElo >= ELITE_ELO
            sameLeague = (teamLeagueName.get(game.homeTeam.id) is not None
                          and teamLeagueName.get(game.homeTeam.id) == teamLeagueName.get(game.awayTeam.id))
            bothInHunt = (not getattr(game.homeTeam, 'eliminated', False)
                          and not getattr(game.awayTeam, 'eliminated', False))
            bubbleBattle = (lateRegularSeason and sameLeague and bothInHunt
                            and (PLAYOFF_SPOTS - 2) <= homePos <= (PLAYOFF_SPOTS + 3)
                            and (PLAYOFF_SPOTS - 2) <= awayPos <= (PLAYOFF_SPOTS + 3))
            game.isFeatured = eliteMatchup or bubbleBattle

        game_list = []
        for game in displayGames:
            game_dict = GameResponseBuilder.buildGameWithProbabilities(game)
            
            # Add current game state fields
            game_dict['startTime'] = game.startTime.replace(tzinfo=timezone.utc).timestamp()
            game_dict['status'] = game.status.name
            game_dict['isHalftime'] = game.isHalftime
            game_dict['isOvertime'] = game.isOvertime
            
            # Add possession info
            if hasattr(game, 'offensiveTeam'):
                game_dict['homeTeamPoss'] = (game.offensiveTeam == game.homeTeam)
                game_dict['awayTeamPoss'] = (game.offensiveTeam == game.awayTeam)
            
            # Add down and distance
            if hasattr(game, 'down'):
                down_text = {1: '1st', 2: '2nd', 3: '3rd', 4: '4th'}.get(game.down, '1st')
                if hasattr(game, 'yardsToEndzone') and game.yardsToEndzone < 10:
                    game_dict['downText'] = f'{down_text} & Goal'
                elif hasattr(game, 'yardsToFirstDown'):
                    game_dict['downText'] = f'{down_text} & {game.yardsToFirstDown}'

            # Add timeouts remaining
            game_dict['homeTimeouts'] = getattr(game, 'homeTimeoutsRemaining', 3)
            game_dict['awayTimeouts'] = getattr(game, 'awayTimeoutsRemaining', 3)

            game_list.append(game_dict)
        
        # Sort: status first (Active → Scheduled → Final),
        # then within each group: upset alert → featured → rest
        status_order = {'Active': 0, 'Scheduled': 1, 'Final': 2}
        def interestRank(g):
            if g.get('isUpsetAlert'): return 0
            if g.get('isFeatured'):   return 1
            return 2
        game_list.sort(key=lambda g: (status_order.get(g.get('status'), 3), interestRank(g)))
        
        return game_list
    
    except Exception as e:
        logger.error(f"Error getting current games: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _buildMatchupPreview(game) -> dict:
    """Build pre-game matchup comparison from season team stats."""
    def _teamStats(team):
        off = team.seasonTeamStats.get('Offense', {})
        dfn = team.seasonTeamStats.get('Defense', {})
        return {
            'avgPts': off.get('avgPts', 0),
            'avgPtsAlwd': dfn.get('avgPtsAlwd', 0),
            'avgPassYards': off.get('avgPassYards', 0),
            'avgPassTds': off.get('avgPassTds', 0),
            'avgRunYards': off.get('avgRunYards', 0),
            'avgRunTds': off.get('avgRunTds', 0),
            'avgYards': off.get('avgYards', 0),
            'avgYardsAlwd': dfn.get('avgYardsAlwd', 0),
            'avgPassYardsAlwd': dfn.get('avgPassYardsAlwd', 0),
            'avgRunYardsAlwd': dfn.get('avgRunYardsAlwd', 0),
            'avgSacks': dfn.get('avgSacks', 0),
            'avgInts': dfn.get('avgInts', 0),
        }
    return {
        'home': _teamStats(game.homeTeam),
        'away': _teamStats(game.awayTeam),
    }


@app.get("/api/games/{game_id}", response_model=Dict[str, Any])
async def get_game_by_id(game_id: int, response: Response):
    """
    Get a specific game by ID

    Args:
        game_id: The game ID

    Returns:
        Game data with scores, status, win probabilities, and play info
    """
    response.headers["Cache-Control"] = "public, max-age=3"
    if floosball_app is None:
        raise HTTPException(status_code=503, detail="Application not initialized")

    try:
        season_mgr = floosball_app.seasonManager
        current_season = season_mgr.currentSeason
        
        if current_season is None:
            raise HTTPException(status_code=404, detail="No active season")
        
        # Find the game in active games list
        game = None
        if getattr(current_season, 'activeGames', None):
            for g in current_season.activeGames:
                if g.id == game_id:
                    game = g
                    break
        
        # If not found in active games, search all games in schedule
        if game is None and hasattr(current_season, 'schedule'):
            for week_dict in current_season.schedule:
                week_games = week_dict.get('games', []) if isinstance(week_dict, dict) else []
                for g in week_games:
                    if hasattr(g, 'id') and g.id == game_id:
                        game = g
                        break
                if game:
                    break
        
        if game is None:
            raise HTTPException(status_code=404, detail=f"Game {game_id} not found")
        
        game_dict = GameResponseBuilder.buildGameWithProbabilities(game)
        
        # Add current game state fields
        game_dict['startTime'] = game.startTime.replace(tzinfo=timezone.utc).timestamp()
        game_dict['status'] = game.status.name
        game_dict['isHalftime'] = game.isHalftime
        game_dict['isOvertime'] = game.isOvertime
        
        # Add possession info
        if hasattr(game, 'offensiveTeam'):
            game_dict['homeTeamPoss'] = (game.offensiveTeam == game.homeTeam)
        
        # Add play history (filter out Play objects, only include serializable dicts)
        # gameFeed stores items as {'play': playData} or {'event': eventData}
        gameFeed = getattr(game, 'gameFeed', [])
        serializable_plays = []
        for item in gameFeed:
            if isinstance(item, dict):
                if 'play' in item:
                    play_data = item['play']
                    # If it's a Play object, serialize it
                    if hasattr(play_data, '__dict__') and hasattr(play_data, 'playText'):
                        from floosball_game import Play
                        if isinstance(play_data, Play):
                            # Serialize Play object to dict
                            play_data = {
                                'playNumber': getattr(play_data, 'playNumber', 0),
                                'quarter': getattr(play_data, 'quarter', 0),
                                'timeRemaining': getattr(play_data, 'timeRemaining', '0:00'),
                                'down': getattr(play_data, 'down', 0),
                                'distance': getattr(play_data, 'yardsTo1st', 0),
                                'yardLine': getattr(play_data, 'yardLine', ''),
                                'playType': play_data.playType.name if hasattr(play_data, 'playType') and hasattr(play_data.playType, 'name') else 'Unknown',
                                'yardsGained': getattr(play_data, 'yardage', 0),
                                'description': getattr(play_data, 'playText', ''),
                                'playResult': play_data.playResult.value if hasattr(play_data, 'playResult') and play_data.playResult else None,
                                'isTouchdown': getattr(play_data, 'isTd', False),
                                'isTurnover': (getattr(play_data, 'isFumbleLost', False) or getattr(play_data, 'isInterception', False)),
                                'isSack': getattr(play_data, 'isSack', False),
                                'scoreChange': getattr(play_data, 'scoreChange', False),
                                'homeTeamScore': getattr(play_data, 'homeTeamScore', None),
                                'awayTeamScore': getattr(play_data, 'awayTeamScore', None),
                                'offensiveTeam': play_data.offense.abbr if hasattr(play_data, 'offense') else '',
                                'defensiveTeam': play_data.defense.abbr if hasattr(play_data, 'defense') else '',
                                'homeWinProbability': getattr(play_data, 'homeWinProbability', None),
                                'awayWinProbability': getattr(play_data, 'awayWinProbability', None),
                                'homeWpa': getattr(play_data, 'homeWpa', None),
                                'awayWpa': getattr(play_data, 'awayWpa', None),
                                'isBigPlay': getattr(play_data, 'isBigPlay', False),
                                'isClutchPlay': getattr(play_data, 'isClutchPlay', False),
                                'isChokePlay': getattr(play_data, 'isChokePlay', False),
                                'isMomentumShift': getattr(play_data, 'isMomentumShift', False),
                                'clockStopped': getattr(play_data, 'clockStopped', False),
                                'clutchPerformers': list(getattr(play_data, 'clutchPerformers', []) or []),
                                'chokePerformers': list(getattr(play_data, 'chokePerformers', []) or []),
                                'insights': getattr(play_data, 'insights', None),
                                'personalityEvent': getattr(play_data, 'personalityEvent', None),
                                'glitchText': getattr(play_data, 'glitchText', None),
                                'glitchPlayerId': getattr(play_data, 'glitchPlayerId', None),
                                'glitchPlayerName': getattr(play_data, 'glitchPlayerName', None),
                                'glitchLayer': getattr(play_data, 'glitchLayer', None),
                            }
                    serializable_plays.append(play_data)
                elif 'event' in item:
                    serializable_plays.append(item['event'])
        
        # gameFeed is newest-first (insert(0, ...)), so serializable_plays is already newest-first
        game_dict['plays'] = serializable_plays

        # Add live game stats snapshot (skip for Scheduled — player gameStatsDict
        # still holds data from their previous game until playGame() resets it)
        if hasattr(game, '_buildGameStatsSnapshot') and game.status.name != 'Scheduled':
            game_dict['gameStats'] = game._buildGameStatsSnapshot()
        else:
            game_dict['gameStats'] = None

        # Clear plays/feed for scheduled games (same reason — no data yet)
        if game.status.name == 'Scheduled':
            game_dict['plays'] = []
            game_dict['matchupPreview'] = _buildMatchupPreview(game)

        # Attach the reaction aggregate for this game so the modal renders
        # the existing reactions when it first opens. Live updates flow over
        # the play_reaction_update WS event after that.
        game_dict['reactions'] = _loadGameReactions(game_id)

        return game_dict

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        logger.error(f"Error getting game {game_id}: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


# ─── Play reactions ────────────────────────────────────────────────────────
#
# Users react to plays (and the sideline-quote personality events attached
# to plays) within games in the current week. One reaction per user per
# target — clicking the same icon removes; clicking a different icon swaps.
# Aggregated counts are public, with usernames attributed.

def _loadGameReactions(gameId: int) -> Dict[str, Any]:
    """Return all reactions on a game, shaped as:
        { "<playNumber>": { "<targetType>": { "<reactionType>": {count, users}, ... }, ... }, ... }
    Only types with count > 0 are included. Used by GET /api/games/{id}.
    """
    from database.connection import get_session
    from database.models import PlayReaction, User as _UserModel

    out: Dict[str, Any] = {}
    session = get_session()
    try:
        rows = (
            session.query(PlayReaction, _UserModel.username)
            .join(_UserModel, _UserModel.id == PlayReaction.user_id)
            .filter(PlayReaction.game_id == gameId)
            .all()
        )
        for r, username in rows:
            playKey = str(r.play_number)
            playBucket = out.setdefault(playKey, {})
            targetBucket = playBucket.setdefault(r.target_type, {})
            typeBucket = targetBucket.setdefault(r.reaction_type, {"count": 0, "users": []})
            typeBucket["count"] += 1
            typeBucket["users"].append({"id": r.user_id, "username": username})
    finally:
        session.close()
    return out


def _buildReactionAggregate(session, gameId: int, playNumber: int, targetType: str) -> Dict[str, Any]:
    """Build the {reactionType: {count, users}} aggregate for a single
    (play, targetType) pair. Used both by the API response and the WS
    broadcast payload."""
    from database.models import PlayReaction, User as _UserModel
    rows = (
        session.query(PlayReaction, _UserModel.username)
        .join(_UserModel, _UserModel.id == PlayReaction.user_id)
        .filter(PlayReaction.game_id == gameId,
                PlayReaction.play_number == playNumber,
                PlayReaction.target_type == targetType)
        .all()
    )
    agg: Dict[str, Any] = {}
    for r, username in rows:
        bucket = agg.setdefault(r.reaction_type, {"count": 0, "users": []})
        bucket["count"] += 1
        bucket["users"].append({"id": r.user_id, "username": username})
    return agg


def _broadcastReactionUpdate(gameId: int, playNumber: int, targetType: str,
                             aggregate: Dict[str, Any]) -> None:
    """Fire a play_reaction_update event on the season channel so any open
    game modal updates without a refetch."""
    try:
        from api.game_broadcaster import broadcaster as _broadcaster
        if not _broadcaster.is_enabled():
            return
        event = GameEvent.playReactionUpdate(
            gameId=gameId,
            playNumber=playNumber,
            targetType=targetType,
            reactions=aggregate,
        )
        _broadcaster.broadcast_sync(gameId, event)
    except Exception as e:
        logger.warning(f"reaction broadcast failed: {e}")


def _validateLiveGameForReaction(gameId: int):
    """Reactions are allowed on games from the current week — both still-live
    games and ones that just completed (users may still be viewing the modal
    after the game ends). Once the week rolls over, completedWeekGames stays
    populated until the next week's games kick off; we still honor reactions
    on those. Older weeks return 409.
    """
    if floosball_app is None:
        raise HTTPException(status_code=503, detail="Application not initialized")
    sm = floosball_app.seasonManager
    currentSeason = sm.currentSeason if sm else None
    if currentSeason is None:
        raise HTTPException(status_code=404, detail="No active season")
    currentWeek = currentSeason.currentWeek
    activeGames = getattr(currentSeason, 'activeGames', None) or []
    completedThisWeek = getattr(currentSeason, 'completedWeekGames', None) or []
    game = next(
        (g for g in list(activeGames) + list(completedThisWeek) if g.id == gameId),
        None,
    )
    if game is None:
        raise HTTPException(status_code=409, detail="Reactions only on current-week games")
    gameWeek = getattr(game, 'week', None) or getattr(game, 'weekNumber', None)
    # Games from prior weeks fall through here (completedWeekGames is single-
    # week; older games never re-enter the list). Defensive check anyway.
    if gameWeek is not None and gameWeek != currentWeek and gameWeek != currentWeek - 1:
        raise HTTPException(status_code=409, detail="Reactions only on current-week games")
    return game


class _ReactionRequest(BaseModel):
    playNumber: int
    targetType: str = 'play'
    reactionType: str


@app.post("/api/games/{game_id}/reactions")
def post_play_reaction(game_id: int, req: _ReactionRequest, user: _User = Depends(_getCurrentUser)):
    """Upsert a reaction. If the user already reacted to this target with
    the SAME type, the reaction is removed (toggle off). If they reacted
    with a DIFFERENT type, the type is swapped. Otherwise inserted fresh."""
    from constants import REACTION_TYPES, REACTION_TARGET_TYPES
    from database.connection import get_session
    from database.models import PlayReaction

    if req.reactionType not in REACTION_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid reactionType: {req.reactionType}")
    if req.targetType not in REACTION_TARGET_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid targetType: {req.targetType}")
    if req.playNumber < 1:
        raise HTTPException(status_code=400, detail="playNumber must be >= 1")
    # Cutaways use fractional playNumbers (X.5/X.9) to sort between real
    # plays; the DB column is Integer and would truncate, causing the
    # reaction to land on the wrong adjacent play. Reject fractional values.
    if req.playNumber != int(req.playNumber):
        raise HTTPException(status_code=400, detail="playNumber must be an integer (cutaways aren't reactable)")

    _validateLiveGameForReaction(game_id)

    session = get_session()
    try:
        existing = session.query(PlayReaction).filter(
            PlayReaction.game_id == game_id,
            PlayReaction.play_number == req.playNumber,
            PlayReaction.target_type == req.targetType,
            PlayReaction.user_id == user.id,
        ).first()
        if existing and existing.reaction_type == req.reactionType:
            session.delete(existing)
            action = 'removed'
        elif existing:
            existing.reaction_type = req.reactionType
            action = 'swapped'
        else:
            session.add(PlayReaction(
                game_id=game_id,
                play_number=req.playNumber,
                target_type=req.targetType,
                user_id=user.id,
                reaction_type=req.reactionType,
            ))
            action = 'added'
        session.commit()
        aggregate = _buildReactionAggregate(session, game_id, req.playNumber, req.targetType)
    finally:
        session.close()

    _broadcastReactionUpdate(game_id, req.playNumber, req.targetType, aggregate)
    return build_success_response({"action": action, "reactions": aggregate})


# ── Game rally ─────────────────────────────────────────────────────────
class _RallyRequest(BaseModel):
    teamId: int
    tier: str   # 'small' | 'medium' | 'large'


def _findLiveGame(gameId: int):
    """Return the in-memory game object iff it's currently in progress
    (status == Active). Rallies only fire on live games — Scheduled and
    Final games are rejected."""
    if floosball_app is None:
        return None
    sm = floosball_app.seasonManager
    currentSeason = sm.currentSeason if sm else None
    if currentSeason is None:
        return None
    activeGames = getattr(currentSeason, 'activeGames', None) or []
    return next((g for g in activeGames if g.id == gameId
                 and getattr(g.status, 'name', '') == 'Active'), None)


@app.post("/api/games/{game_id}/rally")
def post_game_rally(game_id: int, req: _RallyRequest, user: _User = Depends(_getCurrentUser)):
    """Cast a live in-game rally. Charges floobits, applies a confidence
    (and determination if trailing) bump to the team's roster, and
    broadcasts the rally to all viewers."""
    from database.connection import get_session
    from managers import rallyManager
    from database.models import User as _DBUser

    game = _findLiveGame(game_id)
    if game is None:
        raise HTTPException(status_code=409, detail="Rallies only on live games")

    session = get_session()
    try:
        try:
            result = rallyManager.castRally(
                session=session,
                userId=user.id,
                game=game,
                teamId=req.teamId,
                tier=req.tier,
            )
        except rallyManager.RallyError as e:
            session.rollback()
            raise HTTPException(status_code=400, detail=str(e))

        # Username for the broadcast payload (small flash on screen)
        dbUser = session.query(_DBUser).get(user.id)
        username = dbUser.username if dbUser else 'fan'
        session.commit()
    finally:
        session.close()

    # Broadcast to all viewers so meters tick live.
    try:
        from api.game_broadcaster import broadcaster as _broadcaster
        if _broadcaster.is_enabled():
            event = GameEvent.gameRally(
                gameId=game_id,
                teamId=req.teamId,
                userId=user.id,
                username=username,
                tier=req.tier,
                costPaid=result['costPaid'],
                confidenceDelta=result['confidenceDelta'],
                determinationDelta=result['determinationDelta'],
                teamTotals=result['teamTotals'],
                feedMessage=result.get('feedMessage'),
            )
            _broadcaster.broadcast_sync(game_id, event)
    except Exception as e:
        logger.warning(f"rally broadcast failed: {e}")

    return build_success_response(result)


@app.get("/api/games/{game_id}/rally")
def get_game_rally_state(game_id: int, user: Optional[_User] = Depends(_getOptionalUser)):
    """Snapshot of rally activity for a game — per-team totals, plus the
    current user's cooldown / next-cost if authenticated."""
    from database.connection import get_session
    from managers import rallyManager

    session = get_session()
    try:
        state = rallyManager.getRallyStateForGame(
            session=session,
            gameId=game_id,
            userId=(user.id if user else None),
        )
    finally:
        session.close()
    return build_success_response(state)


@app.get("/api/gameStats", response_model=Dict[str, Any])
async def get_game_stats(id: int, response: Response):
    """
    Get detailed statistics for a specific game

    Args:
        id: Game ID

    Returns:
        Full game statistics including player stats, team stats, and play-by-play
    """
    response.headers["Cache-Control"] = "public, max-age=3"
    if floosball_app is None:
        raise HTTPException(status_code=503, detail="Application not initialized")

    try:
        season_mgr = floosball_app.seasonManager
        current_season = season_mgr.currentSeason
        
        if current_season is None:
            raise HTTPException(status_code=404, detail="No active season")
        
        # Find the game
        game = None
        for g in current_season.activeGames:
            if g.id == id:
                game = g
                break
        
        if game is None:
            raise HTTPException(status_code=404, detail=f"Game {id} not found")
        
        # Return game data based on status
        if game.status.name == 'Active':
            return game.getGameData()
        else:
            return game.gameDict.get('gameStats', {})
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting game stats for game {id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/league-news/recent", response_model=List[Dict[str, Any]])
async def get_league_news_recent(
    response: Response,
    limit: int = Query(default=30, ge=1, le=200),
    season: Optional[int] = Query(default=None),
    week: Optional[int] = Query(default=None),
):
    """Recent persisted league-news items (Cores voice lines, anomaly state
    transitions). Default scope is the *current* season+week so the
    highlight feed naturally rolls over with the schedule. Pass ?week=0
    to ignore the week filter and pull a longer history.
    """
    response.headers["Cache-Control"] = "public, max-age=15"
    if floosball_app is None:
        raise HTTPException(status_code=503, detail="Application not initialized")

    try:
        from database.connection import get_session
        from database.models import LeagueNewsItem
        session = get_session()
        try:
            q = session.query(LeagueNewsItem)
            seasonMgr = floosball_app.seasonManager
            cs = seasonMgr.currentSeason
            if season is not None:
                q = q.filter(LeagueNewsItem.season == season)
            elif cs is not None and hasattr(cs, 'seasonNumber'):
                q = q.filter(LeagueNewsItem.season == cs.seasonNumber)
            # Week filter: explicit param wins; otherwise default to the
            # current sim week. Pass week=0 to opt out entirely.
            if week is not None:
                if week > 0:
                    q = q.filter(LeagueNewsItem.week == week)
            elif cs is not None and hasattr(cs, 'currentWeek'):
                q = q.filter(LeagueNewsItem.week == cs.currentWeek)
            rows = q.order_by(LeagueNewsItem.created_at.desc()).limit(limit).all()
            return [{
                'id': r.id,
                'season': r.season,
                'week': r.week,
                'category': r.category,
                'eventType': r.event_type,
                'text': r.text,
                'core': r.core,
                'coreDisplayName': r.core_display_name,
                'playerId': r.player_id,
                'playerName': r.player_name,
                'anomalyState': r.anomaly_state,
                'createdAt': r.created_at.isoformat() + 'Z' if r.created_at else None,
            } for r in rows]
        finally:
            session.close()
    except Exception as e:
        logger.exception(f"Failed to fetch league news: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch league news")


@app.get("/api/highlights", response_model=List[Dict[str, Any]])
async def get_highlights(response: Response, limit: int = Query(default=20, ge=1, le=100)):
    """
    Get recent highlight plays from active games

    Args:
        limit: Maximum number of highlights to return

    Returns:
        List of highlight plays (touchdowns, turnovers, big plays)
    """
    response.headers["Cache-Control"] = "public, max-age=10"
    if floosball_app is None:
        raise HTTPException(status_code=503, detail="Application not initialized")
    
    try:
        season_mgr = floosball_app.seasonManager
        current_season = season_mgr.currentSeason
        
        if current_season is None or not hasattr(current_season, 'activeGames'):
            return []
        
        highlight_list = []
        
        for game in current_season.activeGames:
            if not hasattr(game, 'eventList') or game.status.name != 'Active':
                continue
            
            # Get recent plays from game
            for event in reversed(game.eventList[-50:]):  # Last 50 events
                if event.get('type') == 'play':
                    play = event
                    
                    # Filter for highlights
                    is_highlight = (
                        play.get('isTouchdown') or
                        play.get('isInterception') or
                        play.get('isFumble') or
                        play.get('isSack') or
                        (play.get('yardage', 0) > 20)
                    )
                    
                    if is_highlight:
                        highlight_dict = {
                            'gameId': game.id,
                            'homeTeam': game.homeTeam.name,
                            'awayTeam': game.awayTeam.name,
                            'homeScore': game.homeScore,
                            'awayScore': game.awayScore,
                            'quarter': game.currentQuarter,
                            'playText': play.get('playText', ''),
                            'isTouchdown': play.get('isTouchdown', False),
                            'isInterception': play.get('isInterception', False),
                            'isFumble': play.get('isFumble', False),
                            'isSack': play.get('isSack', False),
                            'yardage': play.get('yardage', 0)
                        }
                        highlight_list.append(highlight_dict)
                        
                        if len(highlight_list) >= limit:
                            break
                
                if len(highlight_list) >= limit:
                    break
        
        return highlight_list[:limit]
    
    except Exception as e:
        logger.error(f"Error getting highlights: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/season", response_model=Dict[str, Any])
async def get_season_info(response: Response):
    """
    Get current season information

    Returns:
        Season number, current week, schedule, standings
    """
    response.headers["Cache-Control"] = "public, max-age=10"
    if floosball_app is None:
        raise HTTPException(status_code=503, detail="Application not initialized")
    
    try:
        season_mgr = floosball_app.seasonManager
        current_season = season_mgr.currentSeason
        
        if current_season is None:
            return build_success_response({
                'season_number': 0,
                'current_week': 0,
                'status': 'not_started',
                'active_games': [],
                'completed_games': []
            })
        
        # Get active and completed game IDs
        activeGameIds = []
        completedGameIds = []
        
        if hasattr(current_season, 'activeGames') and current_season.activeGames is not None:
            for game in current_season.activeGames:
                if hasattr(game, 'status'):
                    if game.status.name == 'Active':
                        activeGameIds.append(game.id)
                    elif game.status.name == 'Final':
                        completedGameIds.append(game.id)
                    else:
                        # Scheduled games count as active for display purposes
                        activeGameIds.append(game.id)
        
        # Include next game start time when no games are actively running
        nextGameStartTime = None
        hasActiveGames = any(
            getattr(g, 'status', None) == FloosGame.GameStatus.Active
            for g in (current_season.activeGames or [])
        )
        if not hasActiveGames and not current_season.isComplete:
            # Prefer cached value: correctly set to current week's start (before games)
            # or next week's start (after games complete)
            nextStart = season_mgr._cachedNextGameStart
            if not nextStart:
                nextStart = season_mgr.getNextGameStartTime(current_season.currentWeek)
            if nextStart:
                nextGameStartTime = nextStart.isoformat() + 'Z'

        # Compute next season start time during offseason (SCHEDULED modes only)
        nextSeasonStartTime = None
        if current_season.isComplete and season_mgr.timingManager._isScheduledMode:
            from managers.timingManager import TimingManager
            nextSeasonStart = TimingManager._nextMondayUtc(hour=4)
            nextSeasonStartTime = nextSeasonStart.isoformat() + 'Z'

        # Phased offseason — current top-level flow phase + ISO target time
        # for the next phase. Phases: post_bowl, frontoffice, rookie_draft,
        # pre_fa, fa_draft, training. Target is set during wait gates so the
        # UI can render "<NextPhase> in Xh Ym" countdowns. Cleared during
        # active phases. (Distinct from _offseasonPhase, which the draft
        # generators use for OffseasonPanel sub-phase rendering.)
        offseasonPhase = getattr(season_mgr, '_offseasonFlowPhase', None)
        offseasonPhaseTargetTime = None
        offseasonPhaseTarget = getattr(season_mgr, '_offseasonFlowTarget', None)
        if offseasonPhaseTarget is not None:
            offseasonPhaseTargetTime = offseasonPhaseTarget.isoformat() + 'Z'

        # Playoff bracket challenge: are the seeds frozen yet? Drives the Bracket
        # nav item (only shown once the playoffs are seeded). DB-backed so it
        # survives a mid-playoffs restart; cheap single-row read on a 10s-cached
        # endpoint. Never let it break the season response.
        bracketAvailable = False
        try:
            from database.connection import get_session as _gsBracket
            from database.repositories.playoff_bracket_repository import PlayoffBracketRepository as _PBRepo
            _bracketSess = _gsBracket()
            try:
                bracketAvailable = _PBRepo(_bracketSess).getFrozenSeeds(current_season.seasonNumber) is not None
            finally:
                _bracketSess.close()
        except Exception:
            bracketAvailable = False

        return build_success_response({
            'season_number': current_season.seasonNumber,
            'current_week': current_season.currentWeek,
            'current_week_text': current_season.currentWeekText,
            'is_complete': current_season.isComplete,
            'active_games': activeGameIds,
            'completed_games': completedGameIds,
            'champion': TeamResponseBuilder.buildBasicTeamDict(current_season.champion) if current_season.champion else None,
            'mvp': current_season.mvp if hasattr(current_season, 'mvp') and current_season.mvp else None,
            'allPro': current_season.allPro if hasattr(current_season, 'allPro') and current_season.allPro else None,
            'next_game_start_time': nextGameStartTime,
            'next_season_start_time': nextSeasonStartTime,
            'offseason_phase': offseasonPhase,
            'offseason_phase_target_time': offseasonPhaseTargetTime,
            'bracket_available': bracketAvailable,
            'regular_season_over': current_season.currentWeek > 28 or (
                current_season.currentWeek == 28 and current_season.completedWeekGames is not None
            ),
        })
    
    except Exception as e:
        logger.error(f"Error getting season info: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/standings", response_model=List[Dict[str, Any]])
async def get_standings(response: Response):
    """
    Get current league standings

    Returns:
        Standings for all leagues sorted by record
    """
    response.headers["Cache-Control"] = "public, max-age=10"
    if floosball_app is None:
        raise HTTPException(status_code=503, detail="Application not initialized")
    
    try:
        standings_list = []

        for league in floosball_app.leagueManager.leagues:
            league_dict = {
                'name': league.name,
                'standings': LeagueResponseBuilder.buildStandingsResponse(league.teamList)['standings']
            }
            standings_list.append(league_dict)

        return standings_list
    
    except Exception as e:
        logger.error(f"Error getting standings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/cards/effects")
async def get_card_effects(response: Response):
    """Public listing of all card effects with display name, tooltip, and tier."""
    response.headers["Cache-Control"] = "public, max-age=3600"
    from managers.cardEffects import EFFECT_DISPLAY_NAMES, EFFECT_TOOLTIPS, EFFECT_EDITION_TIER
    effects = []
    for key, displayName in EFFECT_DISPLAY_NAMES.items():
        effects.append({
            "effectName": key,
            "displayName": displayName,
            "tooltip": EFFECT_TOOLTIPS.get(key, ""),
            "tier": EFFECT_EDITION_TIER.get(key, "base"),
        })
    return effects


# ─── History (past seasons + record book) ──────────────────────────────────


@app.get("/api/history/seasons")
async def get_history_seasons(response: Response):
    """List completed past seasons with champion + MVP for the History page."""
    response.headers["Cache-Control"] = "public, max-age=300"
    if floosball_app is None:
        raise HTTPException(status_code=503, detail="Application not initialized")
    from database.connection import get_session
    from database.models import (
        Season as DBSeason, Team as DBTeam, Player as DBPlayer,
        PlayerSeasonStats as DBPlayerSeasonStats,
    )
    session = get_session()
    try:
        sm = floosball_app.seasonManager
        currentSeasonNum = sm.currentSeason.seasonNumber if sm and sm.currentSeason else 0
        rows = (
            session.query(DBSeason)
            .filter(DBSeason.champion_team_id.isnot(None))
            .filter(DBSeason.season_number < currentSeasonNum)
            .order_by(DBSeason.season_number.desc())
            .all()
        )
        seasons = []
        for s in rows:
            team = session.get(DBTeam, s.champion_team_id) if s.champion_team_id else None
            mvp = session.get(DBPlayer, s.mvp_player_id) if s.mvp_player_id else None
            # MVP team for that season — pulled from player_season_stats so it
            # reflects who they played for at the time, not who they're on now.
            mvpTeamId: Optional[int] = None
            mvpTeamAbbr: Optional[str] = None
            if s.mvp_player_id:
                pss = session.query(DBPlayerSeasonStats).filter_by(
                    player_id=s.mvp_player_id, season=s.season_number,
                ).first()
                if pss and pss.team_id:
                    mvpTeamId = pss.team_id
                    mvpTeam = session.get(DBTeam, pss.team_id)
                    if mvpTeam:
                        mvpTeamAbbr = mvpTeam.abbr
            # Player.position is stored as the FloosPlayer.Position enum value
            # (1=QB, 2=RB, 3=WR, 4=TE, 5=K). Surface the readable name.
            _POS_NAMES = {1: 'QB', 2: 'RB', 3: 'WR', 4: 'TE', 5: 'K'}
            mvpPositionName = _POS_NAMES.get(getattr(mvp, 'position', None)) if mvp else None
            seasons.append({
                "seasonNumber": s.season_number,
                "championTeamId": s.champion_team_id,
                "championTeamName": getattr(team, 'name', None),
                "championTeamAbbr": getattr(team, 'abbr', None),
                "championTeamColor": getattr(team, 'color', None),
                "mvpPlayerId": s.mvp_player_id,
                "mvpPlayerName": getattr(mvp, 'name', None),
                "mvpPosition": mvpPositionName,
                "mvpTeamId": mvpTeamId,
                "mvpTeamAbbr": mvpTeamAbbr,
            })
        return build_success_response({"seasons": seasons})
    finally:
        session.close()


@app.get("/api/history/standings")
async def get_history_standings(season: int, response: Response):
    """Final regular-season standings for a past season."""
    response.headers["Cache-Control"] = "public, max-age=300"
    if floosball_app is None:
        raise HTTPException(status_code=503, detail="Application not initialized")
    from database.connection import get_session
    from database.models import Game as DBGame, Team as DBTeam, TeamSeasonStats as DBTeamSeasonStats
    session = get_session()
    try:
        games = session.query(DBGame).filter(
            DBGame.season == season,
            DBGame.is_playoff == False,
            DBGame.status == 'final',
        ).all()
        # Aggregate per team
        records: Dict[int, Dict[str, int]] = {}
        for g in games:
            for tid in (g.home_team_id, g.away_team_id):
                records.setdefault(tid, {
                    "wins": 0, "losses": 0, "ties": 0,
                    "pointsFor": 0, "pointsAgainst": 0,
                })
            home = records[g.home_team_id]
            away = records[g.away_team_id]
            home["pointsFor"] += g.home_score
            home["pointsAgainst"] += g.away_score
            away["pointsFor"] += g.away_score
            away["pointsAgainst"] += g.home_score
            if g.home_score > g.away_score:
                home["wins"] += 1
                away["losses"] += 1
            elif g.away_score > g.home_score:
                away["wins"] += 1
                home["losses"] += 1
            else:
                home["ties"] += 1
                away["ties"] += 1
        # End-of-season ELO from team_season_stats (keyed by team + season)
        eloRows = session.query(
            DBTeamSeasonStats.team_id, DBTeamSeasonStats.elo,
        ).filter(DBTeamSeasonStats.season == season).all()
        eloByTeam: Dict[int, Optional[int]] = {r.team_id: r.elo for r in eloRows}
        teams = []
        for tid, rec in records.items():
            team = session.get(DBTeam, tid)
            if not team:
                continue
            gp = rec["wins"] + rec["losses"] + rec["ties"]
            winPct = (rec["wins"] + 0.5 * rec["ties"]) / gp if gp else 0
            teams.append({
                "teamId": tid,
                "teamName": team.name,
                "teamCity": team.city,
                "teamAbbr": team.abbr,
                "teamColor": team.color,
                "wins": rec["wins"],
                "losses": rec["losses"],
                "ties": rec["ties"],
                "pointsFor": rec["pointsFor"],
                "pointsAgainst": rec["pointsAgainst"],
                "winPct": round(winPct, 3),
                "elo": eloByTeam.get(tid),
            })
        teams.sort(key=lambda t: (-t["winPct"], -(t["pointsFor"] - t["pointsAgainst"]), -t["pointsFor"]))
        return build_success_response({"season": season, "teams": teams})
    finally:
        session.close()


# Stat category → (label, source field for record book queries)
_RECORD_STATS = {
    "passingYards":   {"label": "Passing Yards",   "json_key": "yards",     "json_field": "passing_stats",   "season_col": "passing_yards"},
    "passingTds":     {"label": "Passing TDs",     "json_key": "tds",       "json_field": "passing_stats",   "season_col": "passing_tds"},
    "rushingYards":   {"label": "Rushing Yards",   "json_key": "yards",     "json_field": "rushing_stats",   "season_col": "rushing_yards"},
    "rushingTds":     {"label": "Rushing TDs",     "json_key": "tds",       "json_field": "rushing_stats",   "season_col": "rushing_tds"},
    "receivingYards": {"label": "Receiving Yards", "json_key": "yards",     "json_field": "receiving_stats", "season_col": "receiving_yards"},
    "receivingTds":   {"label": "Receiving TDs",   "json_key": "tds",       "json_field": "receiving_stats", "season_col": "receiving_tds"},
    "receptions":     {"label": "Receptions",      "json_key": "receptions","json_field": "receiving_stats", "season_col": "receptions"},
    "fgMade":         {"label": "FGs Made",        "json_key": "fgs",       "json_field": "kicking_stats",   "season_col": None},
    "fantasyPoints":  {"label": "Fantasy Points",  "json_key": None,        "json_field": None,              "season_col": "fantasy_points"},
}


@app.get("/api/history/records")
async def get_history_records(response: Response, limit: int = Query(default=10, ge=1, le=50)):
    """Top-N record book across single-game / single-season / career timeframes.

    Returns top entries per stat category for each timeframe. Stats with no
    denormalized season column (e.g. FG made) only return game records.
    """
    response.headers["Cache-Control"] = "public, max-age=300"
    if floosball_app is None:
        raise HTTPException(status_code=503, detail="Application not initialized")
    from database.connection import get_session
    from database.models import (
        GamePlayerStats as DBGamePlayerStats,
        PlayerSeasonStats as DBPlayerSeasonStats,
        Game as DBGame,
        Player as DBPlayer,
        Team as DBTeam,
    )
    from sqlalchemy import func, desc
    session = get_session()
    try:
        result: Dict[str, Dict[str, list]] = {"game": {}, "season": {}, "career": {}}

        for stat_key, meta in _RECORD_STATS.items():
            # ── Single-game records ──────────────────────────────────────
            game_rows = []
            if stat_key == "fantasyPoints":
                rows = (
                    session.query(
                        DBGamePlayerStats.player_id,
                        DBGamePlayerStats.team_id,
                        DBGamePlayerStats.fantasy_points,
                        DBGame.season, DBGame.week,
                    )
                    .join(DBGame, DBGamePlayerStats.game_id == DBGame.id)
                    .order_by(desc(DBGamePlayerStats.fantasy_points))
                    .limit(limit).all()
                )
                game_rows = [(r.player_id, r.team_id, r.fantasy_points, r.season, r.week) for r in rows]
            elif meta["json_field"]:
                field_expr = func.json_extract(getattr(DBGamePlayerStats, meta["json_field"]), f'$.{meta["json_key"]}')
                rows = (
                    session.query(
                        DBGamePlayerStats.player_id,
                        DBGamePlayerStats.team_id,
                        field_expr.label("v"),
                        DBGame.season, DBGame.week,
                    )
                    .join(DBGame, DBGamePlayerStats.game_id == DBGame.id)
                    .filter(field_expr.isnot(None))
                    .order_by(desc(field_expr))
                    .limit(limit).all()
                )
                game_rows = [(r.player_id, r.team_id, r.v, r.season, r.week) for r in rows if r.v is not None]
            entries = []
            for pid, tid, v, season, week in game_rows:
                p = session.get(DBPlayer, pid)
                t = session.get(DBTeam, tid) if tid else None
                entries.append({
                    "playerId": pid,
                    "playerName": p.name if p else "Unknown",
                    "teamAbbr": t.abbr if t else None,
                    "value": int(v) if v is not None else 0,
                    "season": season,
                    "week": week,
                })
            result["game"][stat_key] = entries

            # ── Single-season records (only stats with a denormalized col) ──
            if meta["season_col"]:
                col = getattr(DBPlayerSeasonStats, meta["season_col"])
                rows = (
                    session.query(
                        DBPlayerSeasonStats.player_id,
                        DBPlayerSeasonStats.team_id,
                        col.label("v"),
                        DBPlayerSeasonStats.season,
                    )
                    .order_by(desc(col))
                    .limit(limit).all()
                )
                entries = []
                for r in rows:
                    if not r.v:
                        continue
                    p = session.get(DBPlayer, r.player_id)
                    t = session.get(DBTeam, r.team_id) if r.team_id else None
                    entries.append({
                        "playerId": r.player_id,
                        "playerName": p.name if p else "Unknown",
                        "teamAbbr": t.abbr if t else None,
                        "value": int(r.v),
                        "season": r.season,
                    })
                result["season"][stat_key] = entries

                # ── Career records ──────────────────────────────────────────
                rows = (
                    session.query(
                        DBPlayerSeasonStats.player_id,
                        func.sum(col).label("total"),
                        func.count(DBPlayerSeasonStats.season).label("seasons_count"),
                    )
                    .group_by(DBPlayerSeasonStats.player_id)
                    .order_by(desc("total"))
                    .limit(limit).all()
                )
                entries = []
                for r in rows:
                    if not r.total:
                        continue
                    p = session.get(DBPlayer, r.player_id)
                    entries.append({
                        "playerId": r.player_id,
                        "playerName": p.name if p else "Unknown",
                        "value": int(r.total),
                        "seasons": int(r.seasons_count),
                    })
                result["career"][stat_key] = entries

        # Labels for the frontend so it doesn't have to hardcode them
        labels = {k: v["label"] for k, v in _RECORD_STATS.items()}
        return build_success_response({"records": result, "labels": labels})
    finally:
        session.close()


@app.get("/api/history/user-records")
async def get_history_user_records(response: Response, limit: int = Query(default=10, ge=1, le=50)):
    """Top-N fantasy records across users.

    weeklyFP — best single-week FP total (roster player FP + card bonus)
    seasonFP — best single-season FP total
    Both pull from WeeklyPlayerFP (per player per week) joined to a user's
    locked FantasyRoster, summed with WeeklyCardBonus. Swap nuance is
    ignored for record-book purposes; the order is dominated by
    consistent-roster users either way.
    """
    response.headers["Cache-Control"] = "public, max-age=300"
    if floosball_app is None:
        raise HTTPException(status_code=503, detail="Application not initialized")
    from sqlalchemy import text
    from database.connection import get_session
    from database.models import User
    session = get_session()
    try:
        # Weekly per-user player FP totals (sum across the user's roster).
        weeklyPlayerRows = session.execute(text("""
            SELECT fr.user_id AS user_id, fr.season AS season, wpf.week AS week,
                   SUM(wpf.fantasy_points) AS player_fp
            FROM fantasy_rosters fr
            JOIN fantasy_roster_players frp ON frp.roster_id = fr.id
            JOIN weekly_player_fp wpf ON wpf.player_id = frp.player_id AND wpf.season = fr.season
            GROUP BY fr.user_id, fr.season, wpf.week
        """)).fetchall()
        # Weekly card bonuses keyed by (user, season, week).
        cardWeekRows = session.execute(text("""
            SELECT user_id, season, week, bonus_fp FROM weekly_card_bonuses
        """)).fetchall()
        cardByWeek: Dict[tuple, float] = {
            (r.user_id, r.season, r.week): float(r.bonus_fp or 0) for r in cardWeekRows
        }

        weeklyTotals = []
        for r in weeklyPlayerRows:
            cb = cardByWeek.get((r.user_id, r.season, r.week), 0.0)
            weeklyTotals.append((r.user_id, r.season, r.week, float(r.player_fp or 0) + cb))
        weeklyTotals.sort(key=lambda t: t[3], reverse=True)
        weeklyTotals = weeklyTotals[:limit]

        # Season totals: sum across weeks.
        seasonPlayerRows = session.execute(text("""
            SELECT fr.user_id AS user_id, fr.season AS season,
                   SUM(wpf.fantasy_points) AS player_fp
            FROM fantasy_rosters fr
            JOIN fantasy_roster_players frp ON frp.roster_id = fr.id
            JOIN weekly_player_fp wpf ON wpf.player_id = frp.player_id AND wpf.season = fr.season
            GROUP BY fr.user_id, fr.season
        """)).fetchall()
        cardSeasonRows = session.execute(text("""
            SELECT user_id, season, SUM(bonus_fp) AS bonus_fp
            FROM weekly_card_bonuses
            GROUP BY user_id, season
        """)).fetchall()
        cardBySeason: Dict[tuple, float] = {
            (r.user_id, r.season): float(r.bonus_fp or 0) for r in cardSeasonRows
        }
        seasonTotals = []
        for r in seasonPlayerRows:
            cb = cardBySeason.get((r.user_id, r.season), 0.0)
            seasonTotals.append((r.user_id, r.season, float(r.player_fp or 0) + cb))
        seasonTotals.sort(key=lambda t: t[2], reverse=True)
        seasonTotals = seasonTotals[:limit]

        # Resolve usernames in one batch
        userIds = {uid for (uid, *_rest) in weeklyTotals} | {uid for (uid, *_rest) in seasonTotals}
        users = session.query(User).filter(User.id.in_(userIds)).all() if userIds else []
        nameByUser = {u.id: (u.username or u.email or f"User {u.id}") for u in users}

        return build_success_response({
            "weeklyFP": [
                {"userId": uid, "username": nameByUser.get(uid, f"User {uid}"),
                 "value": round(v, 1), "season": s, "week": w}
                for uid, s, w, v in weeklyTotals
            ],
            "seasonFP": [
                {"userId": uid, "username": nameByUser.get(uid, f"User {uid}"),
                 "value": round(v, 1), "season": s}
                for uid, s, v in seasonTotals
            ],
        })
    finally:
        session.close()


@app.get("/api/reigning-champion")
async def get_reigning_champion(response: Response):
    """Return the previous season's Floosbowl champion (for navbar display)."""
    # Short TTL — when the bowl ends and the champion changes, clients need
    # to see the new value within seconds, not minutes. Was 600s.
    response.headers["Cache-Control"] = "public, max-age=30"
    if floosball_app is None:
        raise HTTPException(status_code=503, detail="Application not initialized")
    try:
        from database.connection import get_session
        from database.models import Season as DBSeason, Team as DBTeam
        session = get_session()
        seasonManager = floosball_app.seasonManager
        currentSeason = seasonManager.currentSeason if seasonManager else None
        if not currentSeason:
            return build_success_response(None)
        teamManager = floosball_app.teamManager

        # If the current season is complete and has a champion, use it directly
        # (handles the window between Floosbowl ending and next season starting)
        if currentSeason.isComplete and getattr(currentSeason, 'champion', None):
            champTeam = teamManager.getTeamById(currentSeason.champion.id) if teamManager else None
            if champTeam:
                return build_success_response(TeamResponseBuilder.buildBasicTeamDict(champTeam))

        # Otherwise look at the previous season
        seasonNum = currentSeason.seasonNumber
        if seasonNum < 2:
            return build_success_response(None)
        prevSeason = session.query(DBSeason).filter_by(season_number=seasonNum - 1).first()
        if not prevSeason or not prevSeason.champion_team_id:
            return build_success_response(None)
        champTeam = teamManager.getTeamById(prevSeason.champion_team_id) if teamManager else None
        if not champTeam:
            return build_success_response(None)
        return build_success_response(TeamResponseBuilder.buildBasicTeamDict(champTeam))
    except Exception as e:
        logger.error(f"Error getting reigning champion: {e}")
        return build_success_response(None)


# ============================================================================
# REST API - STATS & RECORDS
# ============================================================================

_VALID_STAT_CATEGORIES = {
    'fantasy_points', 'passing_yards', 'passing_tds', 'rushing_yards', 'rushing_tds',
    'receiving_yards', 'receiving_tds', 'receptions', 'fg_made', 'fg_pct',
    'performance_rating',
    'def_sacks', 'def_ints', 'def_tackles', 'def_tfl', 'def_forced_fumbles', 'def_pass_breakups',
}
_VALID_POSITIONS = {'ALL', 'QB', 'RB', 'WR', 'TE', 'K'}


# ============================================================================
# PLAYOFF BRACKET CHALLENGE
# ============================================================================

class PlayoffBracketSubmit(BaseModel):
    # {round1:[...], round2:[...], league_championship:[...], floosbowl:[...]}
    predictions: Dict[str, List[int]]


def _playoffBracketTemplate(season: int, repo) -> Optional[Dict[str, Any]]:
    """Frozen field + projected Round 1 (fixed) matchups for the fill-out UI."""
    import playoff_bracket as pb
    seeds = repo.getFrozenSeeds(season)
    if not seeds:
        return None
    confs = seeds.get('conferences', {})
    field = [
        {"teamId": t["teamId"], "winPct": t.get("winPct", 0),
         "scoreDiff": t.get("scoreDiff", 0), "conference": conf, "seed": t.get("seed", 0)}
        for conf, teams in confs.items() for t in teams
    ]
    survivors = {c: [t["teamId"] for t in teams if not t.get("bye")] for c, teams in confs.items()}
    r1 = pb.projectRound(field, pb.ROUND_1, survivors)
    round1 = {conf: [{"higherSeed": hi["teamId"], "lowerSeed": lo["teamId"]} for hi, lo in pairs]
              for conf, pairs in r1.items()}
    return {"conferences": confs, "round1Matchups": round1, "roundLabels": pb.ROUND_LABELS}


@app.get("/api/playoffs/bracket/template")
def get_playoff_bracket_template(user: _User = Depends(_getCurrentUser)):
    """Frozen seeds + fixed Round 1 matchups + the user's current picks."""
    import json as _json
    from database.connection import get_session
    from database.repositories.playoff_bracket_repository import PlayoffBracketRepository
    sm = floosball_app.seasonManager if floosball_app else None
    season = sm.currentSeason.seasonNumber if sm and sm.currentSeason else 0
    session = get_session()
    try:
        repo = PlayoffBracketRepository(session)
        tmpl = _playoffBracketTemplate(season, repo)
        if tmpl is None:
            return build_success_response({"season": season, "available": False})
        existing = repo.getUserBracket(user.id, season)
        myPreds = _json.loads(existing.predictions) if (existing and existing.predictions) else None
        return build_success_response({
            "season": season, "available": True, "open": repo.isOpen(season),
            "myPredictions": myPreds, **tmpl,
        })
    finally:
        session.close()


@app.post("/api/playoffs/bracket")
def submit_playoff_bracket(req: PlayoffBracketSubmit, user: _User = Depends(_getCurrentUser)):
    """Submit/update the user's bracket (rejected once Round 1 kicks off)."""
    import playoff_bracket as pb
    from database.connection import get_session
    from database.repositories.playoff_bracket_repository import PlayoffBracketRepository
    sm = floosball_app.seasonManager if floosball_app else None
    season = sm.currentSeason.seasonNumber if sm and sm.currentSeason else 0
    session = get_session()
    try:
        repo = PlayoffBracketRepository(session)
        if not repo.isOpen(season):
            raise HTTPException(400, "The bracket is locked — playoffs have started")
        seeds = repo.getFrozenSeeds(season) or {}
        validIds = {t["teamId"] for teams in seeds.get("conferences", {}).values() for t in teams}
        preds = {}
        for key in pb.ROUND_KEYS.values():
            picks = req.predictions.get(key, []) or []
            if not isinstance(picks, list) or any(p not in validIds for p in picks):
                raise HTTPException(400, f"Invalid picks for {key}")
            preds[key] = picks
        b = repo.submitPredictions(user.id, season, preds)
        session.commit()
        return build_success_response({"bracketId": b.id, "season": season, "predictions": preds})
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        logger.error(f"Playoff bracket submit error: {e}")
        raise HTTPException(500, "Failed to submit bracket")
    finally:
        session.close()


@app.get("/api/playoffs/bracket/me")
def get_my_playoff_bracket(user: _User = Depends(_getCurrentUser)):
    """The user's bracket + live score breakdown."""
    import json as _json
    import playoff_bracket as pb
    from database.connection import get_session
    from database.repositories.playoff_bracket_repository import PlayoffBracketRepository
    sm = floosball_app.seasonManager if floosball_app else None
    season = sm.currentSeason.seasonNumber if sm and sm.currentSeason else 0
    session = get_session()
    try:
        repo = PlayoffBracketRepository(session)
        b = repo.getUserBracket(user.id, season)
        if b is None:
            return build_success_response({"season": season, "hasBracket": False})
        preds = _json.loads(b.predictions or '{}')
        advancers, championId = repo.computeActualAdvancers(season)
        breakdown = pb.scoreBracket(preds, advancers, championId)
        return build_success_response({
            "season": season, "hasBracket": True, "predictions": preds,
            "points": b.points, "correctCount": b.correct_count, "locked": b.locked,
            "perRound": breakdown["perRound"], "actualAdvancers": advancers,
            "gameResults": repo.getPlayoffGameResults(season),
        })
    finally:
        session.close()


@app.get("/api/playoffs/bracket/leaderboard")
def get_playoff_bracket_leaderboard(user: _User = Depends(_getCurrentUser)):
    """Ranked brackets (points desc). Public — only points/username, not picks."""
    from database.connection import get_session
    from database.repositories.playoff_bracket_repository import PlayoffBracketRepository
    from database.models import User as _U
    sm = floosball_app.seasonManager if floosball_app else None
    season = sm.currentSeason.seasonNumber if sm and sm.currentSeason else 0
    session = get_session()
    try:
        repo = PlayoffBracketRepository(session)
        board = repo.getLeaderboard(season)
        userIds = [b.user_id for b in board]
        names = ({u.id: (u.username or f"User{u.id}")
                  for u in session.query(_U).filter(_U.id.in_(userIds)).all()}
                 if userIds else {})
        rows = [{"rank": i + 1, "userId": b.user_id,
                 "username": names.get(b.user_id, f"User{b.user_id}"),
                 "points": b.points, "correctCount": b.correct_count,
                 "isMe": b.user_id == user.id}
                for i, b in enumerate(board)]
        return build_success_response({"season": season, "leaderboard": rows})
    finally:
        session.close()


@app.get("/api/stats/leaders", response_model=Dict[str, Any])
async def get_stat_leaders(
    response: Response,
    category: str = Query(default="fantasy_points"),
    position: str = Query(default="ALL"),
    limit: int = Query(default=10, ge=1, le=300),
):
    """Get statistical leaders filtered by position and category"""
    response.headers["Cache-Control"] = "public, max-age=120"
    if category not in _VALID_STAT_CATEGORIES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid category. Must be one of: {', '.join(sorted(_VALID_STAT_CATEGORIES))}",
        )
    if position.upper() not in _VALID_POSITIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid position. Must be one of: {', '.join(sorted(_VALID_POSITIONS))}",
        )
    if floosball_app is None:
        raise HTTPException(status_code=503, detail="Application not initialized")

    try:
        def extractStat(player, cat: str) -> float:
            sd = player.seasonStatsDict
            # fantasyPoints is only flushed to seasonStatsDict at game end;
            # add the current game's running total so the leaderboard stays live
            if cat == 'fantasy_points':
                return sd.get('fantasyPoints', 0) + player.gameStatsDict.get('fantasyPoints', 0)
            if cat == 'passing_yards':    return sd.get('passing', {}).get('yards', 0)
            if cat == 'passing_tds':      return sd.get('passing', {}).get('tds', 0)
            if cat == 'rushing_yards':    return sd.get('rushing', {}).get('yards', 0)
            if cat == 'rushing_tds':      return sd.get('rushing', {}).get('tds', 0)
            if cat == 'receiving_yards':  return sd.get('receiving', {}).get('yards', 0)
            if cat == 'receiving_tds':    return sd.get('receiving', {}).get('tds', 0)
            if cat == 'receptions':       return sd.get('receiving', {}).get('receptions', 0)
            if cat == 'fg_made':          return sd.get('kicking', {}).get('fgs', 0)
            if cat == 'fg_pct':
                k = sd.get('kicking', {})
                att = k.get('fgAtt', 0)
                return round(k.get('fgs', 0) / att * 100, 1) if att > 0 else 0.0
            if cat == 'performance_rating':
                return getattr(player, 'seasonPerformanceRating', 0)
            if cat == 'def_sacks':         return sd.get('defense', {}).get('sacks', 0)
            if cat == 'def_ints':          return sd.get('defense', {}).get('ints', 0)
            if cat == 'def_tackles':       return sd.get('defense', {}).get('tackles', 0)
            if cat == 'def_tfl':           return sd.get('defense', {}).get('tfl', 0)
            if cat == 'def_forced_fumbles': return sd.get('defense', {}).get('forcedFumbles', 0)
            if cat == 'def_pass_breakups': return sd.get('defense', {}).get('passBreakups', 0)
            return 0

        players = floosball_app.playerManager.activePlayers
        posFilter = position.upper()
        filtered = [
            p for p in players
            if (posFilter == 'ALL' or (hasattr(p.position, 'name') and p.position.name == posFilter))
            and isinstance(p.team, object) and hasattr(p.team, 'name')
        ]
        # For performance rating, filter out players with no rating or too few games
        if category == 'performance_rating':
            filtered = [p for p in filtered if getattr(p, 'seasonPerformanceRating', 0) > 0 and getattr(p, 'gamesPlayed', 0) >= 1]
        filtered.sort(key=lambda p: extractStat(p, category), reverse=True)

        leaders = []
        for rank, player in enumerate(filtered[:limit], 1):
            sd = player.seasonStatsDict
            entry = {
                'rank': rank,
                'id': player.id,
                'name': player.name,
                'position': player.position.name if hasattr(player.position, 'name') else str(player.position),
                'team': player.team.name if hasattr(player.team, 'name') else str(player.team),
                'teamCity': player.team.city if hasattr(player.team, 'city') else '',
                'teamAbbr': getattr(player.team, 'abbr', player.team.name[:3].upper()),
                'teamColor': getattr(player.team, 'color', '#334155'),
                'teamId': player.team.id if hasattr(player.team, 'id') else None,
                'ratingStars': PlayerResponseBuilder.calculateStarRating(player.playerRating),
                'gamesPlayed': player.gamesPlayed,
                'statValue': extractStat(player, category),
                'fantasyPoints': sd.get('fantasyPoints', 0) + player.gameStatsDict.get('fantasyPoints', 0),
            }
            # Include relevant secondary stats per position
            pos = entry['position']
            if pos == 'QB':
                entry['passing'] = {k: sd.get('passing', {}).get(k, 0) for k in ('yards', 'tds', 'ints', 'comp', 'att')}
                entry['rushing'] = {k: sd.get('rushing', {}).get(k, 0) for k in ('yards', 'tds', 'carries')}
            elif pos == 'RB':
                entry['rushing'] = {k: sd.get('rushing', {}).get(k, 0) for k in ('yards', 'tds', 'carries', 'ypc')}
                entry['receiving'] = {k: sd.get('receiving', {}).get(k, 0) for k in ('yards', 'tds', 'receptions')}
            elif pos in ('WR', 'TE'):
                entry['receiving'] = {k: sd.get('receiving', {}).get(k, 0) for k in ('yards', 'tds', 'receptions', 'targets', 'ypr')}
            elif pos == 'K':
                entry['kicking'] = {k: sd.get('kicking', {}).get(k, 0) for k in ('fgs', 'fgAtt', 'fgPerc', 'longest')}
            # Include defensive stats for all non-K players
            if pos != 'K':
                entry['defense'] = {k: sd.get('defense', {}).get(k, 0) for k in ('sacks', 'ints', 'tackles', 'tfl', 'forcedFumbles', 'passBreakups')}
            leaders.append(entry)

        return build_success_response({'category': category, 'position': position, 'leaders': leaders})

    except Exception as e:
        logger.error(f"Error getting stat leaders: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/stats/mvp-rankings", response_model=Dict[str, Any])
async def get_mvp_rankings(
    response: Response,
    limit: int = Query(default=10, ge=1, le=50),
):
    """Get MVP race rankings — players ranked by z-score across all positions"""
    response.headers["Cache-Control"] = "public, max-age=120"
    if floosball_app is None:
        raise HTTPException(status_code=503, detail="Application not initialized")

    try:
        rankings = floosball_app.playerManager.getMvpRankings(limit=limit)
        return build_success_response({'rankings': rankings})
    except Exception as e:
        logger.error(f"Error getting MVP rankings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# REST API - WEBSOCKET INFO
# ============================================================================

@app.get("/api/ws/stats", response_model=Dict[str, Any])
async def get_websocket_stats():
    """
    Get WebSocket connection statistics
    
    Returns:
        Active connections, channels, and usage info
    """
    stats = ws_manager.get_stats()
    return build_success_response(stats)


# ============================================================================
# ADMIN ENDPOINTS
# ============================================================================

from api.auth import getAdminUser as _getAdminUser
from database.models import User as _AdminUser

def _checkAdminAuth(
    adminUser: Optional[_AdminUser] = Depends(_getAdminUser),
    x_admin_password: Optional[str] = Header(default=None),
) -> None:
    """Authorize admin access via admin-user JWT OR legacy password.

    Checks:
    1. If Authorization header has a valid JWT for a user with is_admin=True, allow.
    2. If X-Admin-Password header matches config adminPassword, allow.
    3. Raise 403.
    """
    if adminUser is not None:
        return
    try:
        from config_manager import get_config
        cfg = get_config()
        expected = cfg.get("adminPassword", "")
    except Exception:
        expected = ""
    if expected and x_admin_password == expected:
        return
    raise HTTPException(status_code=403, detail="Forbidden")


@app.post("/api/admin/names")
async def admin_add_names(payload: Dict[str, Any], _auth: None = Depends(_checkAdminAuth)):
    """Add names to the unused player name pool.

    Filters out names already in use by an active player or coach (and any
    duplicates within the submitted batch) so unused_names can't shadow a
    live entity. Returns the accepted count plus rejected lists so the
    admin sees what was skipped and why.
    """
    if floosball_app is None:
        raise HTTPException(status_code=503, detail="Application not initialized")
    names = payload.get("names", [])
    if not isinstance(names, list) or not names:
        raise HTTPException(status_code=400, detail="'names' must be a non-empty list of strings")
    if len(names) > 500:
        raise HTTPException(status_code=400, detail="Too many names; maximum 500 per request")

    pm = floosball_app.playerManager

    # Dedupe the submitted batch first (preserves order)
    seen: set = set()
    deduped: list = []
    duplicatesInBatch: list = []
    for n in names:
        if not isinstance(n, str):
            continue
        n = n.strip()
        if not n:
            continue
        if n in seen:
            duplicatesInBatch.append(n)
            continue
        seen.add(n)
        deduped.append(n)

    # Reject anything already attached to a live player or coach.
    rejectedInUse: list = []
    accepted: list = []
    for n in deduped:
        if hasattr(pm, 'isNameInUse') and pm.isNameInUse(n):
            rejectedInUse.append(n)
        else:
            accepted.append(n)

    if accepted:
        pm.unusedNames.extend(accepted)
        if getattr(pm, 'name_repo', None):
            pm.name_repo.add_names_batch(accepted)
            pm.db_session.commit()

    return {
        "added": len(accepted),
        "total": len(pm.unusedNames),
        "rejectedInUse": rejectedInUse,
        "duplicatesInBatch": duplicatesInBatch,
    }


@app.get("/api/app-settings")
async def get_app_settings():
    """Public — returns runtime-editable settings (feedback URL/visibility,
    survey URL). Frontend fetches on mount to render the footer + survey
    modal correctly without a redeploy."""
    from database.connection import get_session
    from database.models import AppSetting
    session = get_session()
    try:
        rows = session.query(AppSetting).all()
        settings = {row.key: row.value for row in rows}
        # Coerce booleans for keys we know are boolean
        for boolKey in ('feedback_visible', 'survey_visible'):
            if boolKey in settings:
                settings[boolKey] = str(settings[boolKey]).lower() == 'true'
        return settings
    finally:
        session.close()


@app.put("/api/admin/app-settings")
async def admin_update_app_settings(payload: Dict[str, Any], _auth: None = Depends(_checkAdminAuth)):
    """Admin — bulk update app settings. Pass any subset of keys; only those
    keys are updated. Booleans are coerced to lowercase strings on the way in."""
    from database.connection import get_session
    from database.models import AppSetting
    if not isinstance(payload, dict) or not payload:
        raise HTTPException(status_code=400, detail="payload must be a non-empty object")
    allowed = {'feedback_url', 'feedback_visible', 'survey_url', 'survey_visible', 'survey_text'}
    session = get_session()
    try:
        updated = []
        for key, value in payload.items():
            if key not in allowed:
                continue
            if isinstance(value, bool):
                value = 'true' if value else 'false'
            elif value is None:
                value = ''
            else:
                value = str(value)
            row = session.query(AppSetting).filter_by(key=key).first()
            if row is None:
                row = AppSetting(key=key, value=value)
                session.add(row)
            else:
                row.value = value
                row.updated_at = datetime.utcnow()
            updated.append(key)
        session.commit()
        return {"updated": updated}
    finally:
        session.close()


@app.post("/api/admin/personality/reload")
async def admin_reload_personality_templates(_auth: None = Depends(_checkAdminAuth)):
    """Hot-reload personality content from disk:
      - vibe_reactions.yaml
      - quirk_reactions.yaml
      - player_flavor.yaml

    Use after uploading new template files (e.g. via `fly ssh sftp`) to apply
    changes without restarting the app. Clears the shuffled-deck cache so the
    next reaction draw uses the updated pools.
    """
    if floosball_app is None:
        raise HTTPException(status_code=503, detail="Application not initialized")
    floosball_app.personalityManager.reloadTemplates()
    eng = floosball_app.personalityManager.engine
    return {
        "ok": True,
        "personalities": len(eng.personalities),
        "quirks": len(eng.quirks),
        "hometowns": len((eng.flavor or {}).get('hometowns', []) or []),
        "favoriteCategories": len(((eng.flavor or {}).get('favorites') or {}).keys()),
    }


@app.post("/api/admin/players")
async def admin_create_player(payload: Dict[str, Any], _auth: None = Depends(_checkAdminAuth)):
    """Create a player and add them to the free agent pool for next season"""

    if floosball_app is None:
        raise HTTPException(status_code=503, detail="Application not initialized")
    from random import randint
    import floosball_player as FloosPlayer

    TIER_SEEDS = {
        "S": (93, 100), "A": (87, 92), "B": (77, 86),
        "C": (69, 76),  "D": (50, 68),
    }
    tier = payload.get("tier", "random").upper()
    seedRange = TIER_SEEDS.get(tier)  # None → fully random

    posMap = {
        "QB": FloosPlayer.Position.QB, "RB": FloosPlayer.Position.RB,
        "WR": FloosPlayer.Position.WR, "TE": FloosPlayer.Position.TE,
        "K":  FloosPlayer.Position.K,
    }
    pos = posMap.get(payload.get("position", "QB").upper())
    if not pos:
        raise HTTPException(status_code=400, detail=f"Unknown position: {payload.get('position')}")

    pm = floosball_app.playerManager
    created = []
    for _ in range(min(int(payload.get("count", 1)), 10)):
        physSeed   = randint(*seedRange) if seedRange else None
        mentalSeed = randint(70, 95)     if seedRange else None
        player = pm.createPlayer(pos, physSeed, mentalSeed)
        if player:
            pm.freeAgents.append(player)
            created.append({
                "name": player.name,
                "position": pos.name,
                "rating": round(player.playerRating, 1),
                "tier": player.playerTier.name,
            })
    return {"created": created, "unusedNamesRemaining": len(pm.unusedNames)}


@app.get("/api/beta/access-mode")
async def get_beta_access_mode():
    """Public endpoint — returns the current access mode (request or waitlist)."""
    try:
        from config_manager import get_config
        mode = get_config().get("accessMode", "request")
    except Exception:
        mode = "request"
    return {"mode": mode}


@app.post("/api/beta/request-access")
async def request_beta_access(payload: Dict[str, Any]):
    """Public endpoint — submit a request to join the closed beta."""
    import re
    email = (payload.get("email") or "").lower().strip()
    if not email or not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', email):
        raise HTTPException(status_code=400, detail="Valid email required")

    from database.connection import get_session
    from database.models import BetaAllowlist, BetaAccessRequest

    session = get_session()
    try:
        # Already on allowlist
        if session.query(BetaAllowlist).filter_by(email=email).first():
            return {"status": "already_approved", "message": "This email already has access."}

        # Already requested
        existing = session.query(BetaAccessRequest).filter_by(email=email).first()
        if existing:
            return {"status": existing.status, "message": "Access request already submitted."}

        request = BetaAccessRequest(email=email)
        session.add(request)
        session.commit()
        logger.info(f"Beta access request from {email}")
        return {"status": "pending", "message": "Request submitted."}
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@app.get("/api/admin/beta/allowlist")
async def admin_get_beta_allowlist(_auth: None = Depends(_checkAdminAuth)):
    """List all emails on the beta allowlist."""

    from database.connection import get_session
    from database.models import BetaAllowlist
    session = get_session()
    try:
        entries = session.query(BetaAllowlist).order_by(BetaAllowlist.added_at.desc()).all()
        return {
            "emails": [
                {
                    "email": e.email,
                    "addedAt": e.added_at.isoformat() + 'Z' if e.added_at else None,
                }
                for e in entries
            ]
        }
    finally:
        session.close()


@app.post("/api/admin/beta/allowlist")
async def admin_add_beta_emails(payload: Dict[str, Any], _auth: None = Depends(_checkAdminAuth)):
    """Add email(s) to beta allowlist."""

    rawEmails = payload.get("emails", [])
    if isinstance(rawEmails, str):
        rawEmails = [e.strip() for e in rawEmails.split(",") if e.strip()]
    if not rawEmails:
        raise HTTPException(status_code=400, detail="No emails provided")

    from database.connection import get_session
    from database.models import BetaAllowlist

    session = get_session()
    added = []
    try:
        for email in rawEmails:
            email = email.lower().strip()
            existing = session.query(BetaAllowlist).filter_by(email=email).first()
            if existing:
                continue

            entry = BetaAllowlist(email=email)
            session.add(entry)
            added.append(email)

        session.commit()
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()

    return {"added": added, "count": len(added)}


@app.delete("/api/admin/beta/allowlist/{email}")
async def admin_remove_beta_email(email: str, _auth: None = Depends(_checkAdminAuth)):
    """Remove an email from beta allowlist."""

    from database.connection import get_session
    from database.models import BetaAllowlist

    email = email.lower().strip()

    session = get_session()
    try:
        entry = session.query(BetaAllowlist).filter_by(email=email).first()
        if not entry:
            raise HTTPException(status_code=404, detail="Email not found in allowlist")

        session.delete(entry)
        session.commit()
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()

    return {"removed": email}


@app.get("/api/admin/beta/requests")
async def admin_get_beta_requests(_auth: None = Depends(_checkAdminAuth)):
    """List pending beta access requests."""

    from database.connection import get_session
    from database.models import BetaAccessRequest

    session = get_session()
    try:
        requests = session.query(BetaAccessRequest).filter_by(
            status='pending'
        ).order_by(BetaAccessRequest.requested_at.asc()).all()
        return {
            "requests": [
                {
                    "id": r.id,
                    "email": r.email,
                    "status": r.status,
                    "requestedAt": r.requested_at.isoformat() + 'Z' if r.requested_at else None,
                }
                for r in requests
            ]
        }
    finally:
        session.close()


@app.post("/api/admin/beta/requests/{requestId}/approve")
async def admin_approve_beta_request(requestId: int, _auth: None = Depends(_checkAdminAuth)):
    """Approve a beta access request — adds email to allowlist and sends notification."""

    from database.connection import get_session
    from database.models import BetaAccessRequest, BetaAllowlist
    from managers.emailManager import sendAccessApprovedEmail

    session = get_session()
    try:
        request = session.query(BetaAccessRequest).filter_by(id=requestId).first()
        if not request:
            raise HTTPException(status_code=404, detail="Request not found")
        if request.status != 'pending':
            raise HTTPException(status_code=400, detail=f"Request already {request.status}")

        request.status = 'approved'
        request.reviewed_at = datetime.utcnow()

        # Add to allowlist if not already there
        if not session.query(BetaAllowlist).filter_by(email=request.email).first():
            session.add(BetaAllowlist(email=request.email))

        session.commit()
        logger.info(f"Beta access approved for {request.email}")

        # Send notification email (non-blocking, failures are logged)
        sendAccessApprovedEmail(request.email)

        return {"email": request.email, "status": "approved"}
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@app.post("/api/admin/beta/requests/{requestId}/deny")
async def admin_deny_beta_request(requestId: int, _auth: None = Depends(_checkAdminAuth)):
    """Deny a beta access request."""

    from database.connection import get_session
    from database.models import BetaAccessRequest

    session = get_session()
    try:
        request = session.query(BetaAccessRequest).filter_by(id=requestId).first()
        if not request:
            raise HTTPException(status_code=404, detail="Request not found")
        if request.status != 'pending':
            raise HTTPException(status_code=400, detail=f"Request already {request.status}")

        request.status = 'denied'
        request.reviewed_at = datetime.utcnow()
        session.commit()
        logger.info(f"Beta access denied for {request.email}")

        return {"email": request.email, "status": "denied"}
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@app.get("/api/admin/beta/access-mode")
async def admin_get_access_mode(_auth: None = Depends(_checkAdminAuth)):
    """Get current access mode."""

    try:
        from config_manager import get_config
        mode = get_config().get("accessMode", "request")
    except Exception:
        mode = "request"
    return {"mode": mode}


@app.post("/api/admin/beta/access-mode")
async def admin_set_access_mode(payload: Dict[str, Any],
                                _auth: None = Depends(_checkAdminAuth)):
    """Toggle access mode between 'request' and 'waitlist'."""

    mode = payload.get("mode", "").lower().strip()
    if mode not in ("request", "waitlist"):
        raise HTTPException(status_code=400, detail="Mode must be 'request' or 'waitlist'")
    from config_manager import save_config_value
    save_config_value(mode, "accessMode")
    logger.info(f"Access mode changed to '{mode}'")
    return {"mode": mode}


@app.get("/api/admin/users")
def admin_list_users(q: Optional[str] = Query(default=None),
                     sort: Optional[str] = Query(default=None),
                     filter: Optional[str] = Query(default=None),
                     _auth: None = Depends(_checkAdminAuth)):
    """List registered users, optionally filtered by search query."""

    from database.connection import get_session
    from database.models import User, UserCurrency, Team, BetaAllowlist, BetaAccessRequest

    session = get_session()
    try:
        query = session.query(User)
        if q and q.strip():
            term = f"%{q.strip().lower()}%"
            query = query.filter(
                (User.email.ilike(term)) | (User.username.ilike(term))
            )
        # Status filter
        if filter == 'active':
            query = query.filter(User.has_completed_onboarding == True, User.is_active == True)
        elif filter == 'pending':
            query = query.filter(User.has_completed_onboarding == False, User.is_active == True)
        elif filter == 'inactive':
            query = query.filter(User.is_active == False)

        # Sort order
        if sort == 'last_login':
            query = query.order_by(User.last_login_at.desc().nullslast())
        elif sort == 'username':
            query = query.order_by(User.username.asc().nullslast())
        elif sort == 'oldest':
            query = query.order_by(User.created_at.asc())
        else:
            query = query.order_by(User.created_at.desc())

        users = query.limit(200).all()

        # Batch-load currencies and favorite teams
        userIds = [u.id for u in users]
        currencies = {c.user_id: c for c in session.query(UserCurrency).filter(UserCurrency.user_id.in_(userIds)).all()} if userIds else {}
        teamIds = {u.favorite_team_id for u in users if u.favorite_team_id}
        teams = {t.id: t for t in session.query(Team).filter(Team.id.in_(teamIds)).all()} if teamIds else {}

        # Batch-load beta status: allowlist + requests
        userEmails = [u.email.lower().strip() for u in users]
        allowedEmails = set()
        requestStatuses = {}
        if userEmails:
            from sqlalchemy import func
            for row in session.query(BetaAllowlist.email).all():
                allowedEmails.add(row.email.lower().strip())
            for row in session.query(BetaAccessRequest.email, BetaAccessRequest.status).all():
                requestStatuses[row.email.lower().strip()] = row.status

        result = []
        for u in users:
            currency = currencies.get(u.id)
            favTeam = teams.get(u.favorite_team_id) if u.favorite_team_id else None
            email = u.email.lower().strip()
            if email in allowedEmails:
                betaStatus = "approved"
            elif email in requestStatuses:
                betaStatus = requestStatuses[email]  # pending or denied
            else:
                betaStatus = "no_request"
            result.append({
                "id": u.id,
                "email": u.email,
                "username": u.username,
                "floobits": currency.balance if currency else 0,
                "lifetimeEarned": currency.lifetime_earned if currency else 0,
                "lifetimeSpent": currency.lifetime_spent if currency else 0,
                "favoriteTeam": f"{favTeam.city} {favTeam.name}" if favTeam else None,
                "favoriteTeamId": u.favorite_team_id,
                "onboarded": u.has_completed_onboarding,
                "createdAt": u.created_at.isoformat() + 'Z' if u.created_at else None,
                "isActive": u.is_active,
                "lastLoginAt": u.last_login_at.isoformat() + 'Z' if u.last_login_at else None,
                "betaStatus": betaStatus,
                "isAdmin": getattr(u, 'is_admin', False),
            })
        return build_success_response({"users": result, "total": len(result)})
    finally:
        session.close()


@app.post("/api/admin/users/send-onboarding-reminders")
def admin_send_onboarding_reminders(_auth: None = Depends(_checkAdminAuth)):
    """Send reminder emails to users who haven't completed onboarding."""

    from database.connection import get_session
    from database.models import User
    from managers.emailManager import sendOnboardingReminderEmail

    session = get_session()
    try:
        pendingUsers = session.query(User).filter(
            User.has_completed_onboarding == False,
            User.is_active == True,
            User.email.isnot(None),
        ).all()

        import time
        sent = 0
        failed = 0
        for u in pendingUsers:
            if u.email and u.email.strip():
                if sendOnboardingReminderEmail(u.email.strip()):
                    sent += 1
                else:
                    failed += 1
                # Rate limit: max ~4 per second to stay under provider limits
                time.sleep(0.3)

        logger.info(f"Onboarding reminders: {sent} sent, {failed} failed, {len(pendingUsers)} total pending")
        return build_success_response({
            "sent": sent,
            "failed": failed,
            "totalPending": len(pendingUsers),
        })
    finally:
        session.close()


@app.get("/api/admin/card-options")
def admin_card_options(_auth: None = Depends(_checkAdminAuth)):
    """Return available editions, effects, and classifications for the card grant tool."""

    from managers.cardEffects import (
        SHARED_EFFECT_POOL, POSITION_EXCLUSIVE_POOLS,
        EFFECT_DISPLAY_NAMES, EFFECT_CATEGORY, EFFECT_EDITION_TIER,
    )
    from managers.cardManager import EDITION_ORDER
    editions = list(EDITION_ORDER)
    # Build effects grouped by category from the shared + exclusive pools
    effects = {}
    allEffects = list(SHARED_EFFECT_POOL)
    for posPool in POSITION_EXCLUSIVE_POOLS.values():
        allEffects.extend(posPool)
    seen = set()
    for name in allEffects:
        if name in seen:
            continue
        seen.add(name)
        cat = EFFECT_CATEGORY.get(name, "flat_fp")
        if cat not in effects:
            effects[cat] = []
        effects[cat].append({"name": name, "displayName": EFFECT_DISPLAY_NAMES.get(name, name), "edition": EFFECT_EDITION_TIER.get(name, "base")})
    classifications = ["rookie", "mvp", "champion", "all_pro",
                        "mvp_champion", "all_pro_champion", "mvp_all_pro_champion"]
    return build_success_response({
        "editions": editions,
        "effects": effects,
        "classifications": classifications,
        "categories": list(effects.keys()),
    })


@app.get("/api/admin/players/search")
def admin_search_players(q: str = Query(..., min_length=1),
                         _auth: None = Depends(_checkAdminAuth)):
    """Search players by name for the card grant tool."""

    if floosball_app is None:
        raise HTTPException(status_code=503, detail="Application not initialized")
    query = q.lower()
    results = []
    for team in floosball_app.teamManager.teams:
        for p in team.roster:
            if query in p.name.lower():
                results.append({
                    "id": p.id, "name": p.name,
                    "position": p.position.value if hasattr(p.position, 'value') else p.position,
                    "positionNum": p.position.value if hasattr(p.position, 'value') else p.position,
                    "rating": round(p.playerRating),
                    "teamId": team.id, "teamName": team.name,
                })
    results.sort(key=lambda x: -x["rating"])
    return build_success_response({"players": results[:20]})


@app.post("/api/admin/grant-card")
def admin_grant_card(payload: Dict[str, Any],
                     _auth: None = Depends(_checkAdminAuth)):
    """Grant a card to a user with specific edition, effect, and classification."""

    from database.connection import get_session
    from database.models import User, CardTemplate, UserCard
    from managers.cardEffects import buildEffectConfig
    from managers.cardManager import EDITION_SELL_VALUES, EDITION_ORDER

    email = payload.get("email", "").strip().lower()
    playerId = payload.get("playerId")
    edition = payload.get("edition", "base")
    effectName = payload.get("effectName")  # optional override
    categoryOverride = payload.get("category")  # optional category override
    classification = payload.get("classification")  # optional

    if not email:
        raise HTTPException(status_code=400, detail="email is required")
    if edition not in EDITION_ORDER:
        raise HTTPException(status_code=400, detail=f"Invalid edition: {edition}")
    if floosball_app is None:
        raise HTTPException(status_code=503, detail="Application not initialized")

    pm = floosball_app.playerManager

    def _isCardEligiblePlayer(p) -> bool:
        """Same eligibility rules as season-template generation: no prospects,
        no upcoming rookies, must have a real team. Prevents admin grants
        from leaving NULL-team_id templates that pollute pack rolls + blend
        eligibility downstream."""
        if getattr(p, 'is_prospect', False):
            return False
        if getattr(p, 'drafting_team_id', None):
            return False
        if getattr(p, 'is_upcoming_rookie', False):
            return False
        teamObj = getattr(p, 'team', None)
        teamId = getattr(teamObj, 'id', None) if teamObj is not None else None
        return bool(teamId)

    if playerId:
        playerObj = pm.getPlayerById(playerId)
        if playerObj is None:
            raise HTTPException(status_code=404, detail=f"Player {playerId} not found")
        if not _isCardEligiblePlayer(playerObj):
            raise HTTPException(
                status_code=400,
                detail=f"Player {playerObj.name} is a prospect / upcoming rookie / unrostered — cards require a rostered player",
            )
    else:
        # Pick a random player eligible for this edition's rating threshold
        import random as _rand
        from managers.cardManager import EDITION_THRESHOLDS
        threshold = EDITION_THRESHOLDS.get(edition, 0)
        eligible = [p for p in pm.activePlayers
                    if round(p.playerRating) >= threshold and _isCardEligiblePlayer(p)]
        if not eligible:
            raise HTTPException(status_code=400, detail=f"No players eligible for {edition} edition")
        playerObj = _rand.choice(eligible)
        playerId = playerObj.id

    sm = floosball_app.seasonManager
    currentSeason = sm.currentSeason.seasonNumber if sm.currentSeason else 1

    posNum = playerObj.position.value if hasattr(playerObj.position, 'value') else playerObj.position
    rating = round(playerObj.playerRating)

    # Build effect config (with optional forced effect/category)
    effectConfig = buildEffectConfig(
        edition, rating, posNum, teamId=getattr(playerObj.team, 'id', None) if hasattr(playerObj, 'team') else None,
        forceEffect=effectName,
        forceCategory=categoryOverride,
    )

    sellValue = EDITION_SELL_VALUES.get(edition, 5)
    if classification and "rookie" in classification:
        sellValue *= 2

    session = get_session()
    try:
        user = session.query(User).filter_by(email=email).first()
        if not user:
            raise HTTPException(status_code=404, detail=f"No user with email: {email}")

        # Reuse existing template if one exists, otherwise create new
        template = session.query(CardTemplate).filter_by(
            player_id=playerId, edition=edition, season_created=currentSeason,
        ).first()
        if template:
            # Update effect/classification if admin specified overrides
            if effectName or categoryOverride:
                template.effect_config = effectConfig
            if classification:
                template.classification = classification
        else:
            teamId = getattr(playerObj.team, 'id', None) if hasattr(playerObj, 'team') else None
            template = CardTemplate(
                player_id=playerId,
                edition=edition,
                season_created=currentSeason,
                is_rookie=bool(classification and "rookie" in classification),
                classification=classification,
                player_name=playerObj.name,
                team_id=teamId,
                player_rating=rating,
                position=posNum,
                effect_config=effectConfig,
                rarity_weight=1,
                sell_value=sellValue,
            )
            session.add(template)
        session.flush()

        # Create user card
        userCard = UserCard(
            user_id=user.id,
            card_template_id=template.id,
            acquired_via="admin_grant",
        )
        session.add(userCard)
        session.commit()

        return build_success_response({
            "message": f"Granted {edition} card to {email}",
            "cardId": userCard.id,
            "templateId": template.id,
            "playerName": playerObj.name,
            "edition": edition,
            "effectName": effectConfig.get("effectName"),
            "displayName": effectConfig.get("displayName"),
            "classification": classification,
        })
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        logger.error(f"Error granting card: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@app.post("/api/admin/grant-floobits")
def admin_grant_floobits(payload: Dict[str, Any],
                         _auth: None = Depends(_checkAdminAuth)):
    """Grant Floobits to a user."""

    from database.connection import get_session
    from database.models import User
    from database.repositories.card_repositories import CurrencyRepository

    email = payload.get("email", "").strip().lower()
    amount = payload.get("amount", 0)

    if not email:
        raise HTTPException(status_code=400, detail="email is required")
    if not isinstance(amount, int) or amount <= 0:
        raise HTTPException(status_code=400, detail="amount must be a positive integer")

    session = get_session()
    try:
        user = session.query(User).filter_by(email=email).first()
        if not user:
            raise HTTPException(status_code=404, detail=f"No user with email: {email}")

        currencyRepo = CurrencyRepository(session)
        currency = currencyRepo.addFunds(
            userId=user.id, amount=amount,
            transactionType="admin_grant",
            description=f"Admin grant: {amount} Floobits",
        )
        session.commit()

        return build_success_response({
            "message": f"Granted {amount} Floobits to {email}",
            "newBalance": currency.balance,
        })
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        logger.error(f"Error granting floobits: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@app.post("/api/admin/users/{userId}/reroll-username")
def admin_reroll_username(userId: int, _auth: None = Depends(_checkAdminAuth)):
    """Admin: re-roll a user's username."""

    from database.connection import get_session
    from database.models import User as _UserModel
    from api.auth import _generateUsernameCandidate
    session = get_session()
    try:
        dbUser = session.query(_UserModel).filter(_UserModel.id == userId).first()
        if not dbUser:
            raise HTTPException(status_code=404, detail="User not found")
        oldUsername = dbUser.username
        newUsername = _generateUsernameCandidate(session)
        dbUser.username = newUsername
        session.commit()
        return build_success_response({
            "userId": userId,
            "oldUsername": oldUsername,
            "newUsername": newUsername,
        })
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@app.delete("/api/admin/users/{userId}")
def admin_delete_user(userId: int, _auth: None = Depends(_checkAdminAuth)):
    """Admin: permanently delete a user and all related data."""

    from database.connection import get_session
    from database.models import (
        User as _UserModel, UserCurrency, CurrencyTransaction, UserCard,
        EquippedCard, CardUpgradeLog, WeeklyCardBonus, PackOpening,
        FeaturedShopCard, ShopPurchase, UserModifierOverride,
        FantasyRoster, FantasyRosterPlayer, FantasyRosterSwap,
        UserNotification, GmVote, GmFaBallot, PickEmPick,
    )
    session = get_session()
    try:
        dbUser = session.query(_UserModel).filter(_UserModel.id == userId).first()
        if not dbUser:
            raise HTTPException(status_code=404, detail="User not found")
        email = dbUser.email
        username = dbUser.username

        # Delete child records in dependency order
        rosterIds = [r.id for r in session.query(FantasyRoster.id).filter_by(user_id=userId).all()]
        if rosterIds:
            session.query(FantasyRosterSwap).filter(FantasyRosterSwap.roster_id.in_(rosterIds)).delete(synchronize_session=False)
            session.query(FantasyRosterPlayer).filter(FantasyRosterPlayer.roster_id.in_(rosterIds)).delete(synchronize_session=False)
            session.query(WeeklyCardBonus).filter(WeeklyCardBonus.roster_id.in_(rosterIds)).delete(synchronize_session=False)
        session.query(FantasyRoster).filter_by(user_id=userId).delete(synchronize_session=False)

        session.query(EquippedCard).filter_by(user_id=userId).delete(synchronize_session=False)
        session.query(CardUpgradeLog).filter_by(user_id=userId).delete(synchronize_session=False)
        session.query(UserCard).filter_by(user_id=userId).delete(synchronize_session=False)

        session.query(PackOpening).filter_by(user_id=userId).delete(synchronize_session=False)
        session.query(FeaturedShopCard).filter_by(user_id=userId).delete(synchronize_session=False)
        session.query(ShopPurchase).filter_by(user_id=userId).delete(synchronize_session=False)
        session.query(UserModifierOverride).filter_by(user_id=userId).delete(synchronize_session=False)
        session.query(CurrencyTransaction).filter_by(user_id=userId).delete(synchronize_session=False)
        session.query(UserCurrency).filter_by(user_id=userId).delete(synchronize_session=False)

        session.query(UserNotification).filter_by(user_id=userId).delete(synchronize_session=False)
        session.query(GmVote).filter_by(user_id=userId).delete(synchronize_session=False)
        session.query(GmFaBallot).filter_by(user_id=userId).delete(synchronize_session=False)
        session.query(PickEmPick).filter_by(user_id=userId).delete(synchronize_session=False)

        session.delete(dbUser)
        session.commit()
        logger.info(f"Admin deleted user {userId} ({email})")
        return build_success_response({"userId": userId, "email": email, "username": username})
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        logger.error(f"Error deleting user {userId}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@app.post("/api/admin/users/{userId}/toggle-admin")
def admin_toggle_admin(userId: int, _auth: None = Depends(_checkAdminAuth)):
    """Toggle is_admin for a user."""
    from database.connection import get_session
    from database.models import User as _UserModel
    session = get_session()
    try:
        user = session.query(_UserModel).filter(_UserModel.id == userId).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        user.is_admin = not getattr(user, 'is_admin', False)
        session.commit()
        return build_success_response({
            "userId": user.id,
            "isAdmin": user.is_admin,
        })
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@app.get("/api/admin/monitor")
async def admin_monitor(_auth: None = Depends(_checkAdminAuth)):
    """Admin: comprehensive monitoring dashboard data"""

    if floosball_app is None:
        raise HTTPException(status_code=503, detail="Application not initialized")

    sm = floosball_app.seasonManager
    pm = floosball_app.playerManager
    tm = floosball_app.teamManager
    season = sm.currentSeason
    timing = sm.timingManager

    # Load simulation state from DB (for lastSaved timestamp)
    simState = floosball_app._loadSimulationState()

    # Use LIVE runtime state for phase detection (DB state can be stale)
    liveWeek = getattr(season, 'currentWeek', 0) if season else 0
    liveWeekText = getattr(season, 'currentWeekText', None) if season else None
    liveSeasonNum = getattr(season, 'seasonNumber', 0) if season else 0
    liveComplete = getattr(season, 'isComplete', False) if season else False

    # Check for active games in progress
    from floosball_game import GameStatus as _GameStatus
    activeCount = 0
    scheduledCount = 0
    finalCount = 0
    if season and season.activeGames:
        for g in season.activeGames:
            if g.status == _GameStatus.Active:
                activeCount += 1
            elif g.status == _GameStatus.Final:
                finalCount += 1
            else:
                scheduledCount += 1

    hasLiveGames = activeCount > 0 or scheduledCount > 0

    # Determine phase from live state
    phase = "unknown"
    if not season:
        phase = "inactive"
    elif liveComplete and not hasLiveGames:
        phase = "between_seasons"
    elif liveWeekText == 'Offseason':
        phase = "offseason"
    elif hasLiveGames or (liveWeek > 0 and not liveComplete):
        # Check playoffs from live season state
        inPlayoffs = bool(season.playoffBracket)
        if inPlayoffs:
            phase = "playoffs"
        else:
            phase = "regular_season"
    elif liveWeek == 0 and not hasLiveGames:
        phase = "between_seasons"
    else:
        phase = "regular_season"

    # Deploy safety — only safe when truly between seasons with no activity
    deploySafe = phase in ("between_seasons", "inactive")
    if deploySafe:
        deployReason = "Safe to deploy — simulation is between seasons" if phase == "between_seasons" else "Safe to deploy — simulation is inactive"
    elif phase == "offseason":
        deployReason = "Not safe — offseason in progress (FA draft / training)"
    elif phase == "playoffs":
        playoffRound = simState.get('playoff_round', 'unknown') if simState else 'unknown'
        deployReason = f"Not safe — playoffs in progress ({playoffRound} round)"
    elif phase == "regular_season":
        deployReason = f"Not safe — regular season in progress ({liveWeekText or 'Week ' + str(liveWeek)})"
    else:
        deployReason = "Not safe — simulation state unknown"

    # Total / completed game counts from schedule
    totalGames = 0
    completedGames = 0
    if season and season.schedule:
        for roundEntry in season.schedule:
            games = roundEntry.get('games', [])
            for game in games:
                totalGames += 1
                if game.status == _GameStatus.Final:
                    completedGames += 1

    # Champion info
    championName = None
    if season and season.champion:
        championName = getattr(season.champion, 'name', None)

    # MVP info
    mvpName = None
    if season and season.mvp:
        mvpName = season.mvp.get('name', None)

    # Memory usage
    import resource, os
    rusage = resource.getrusage(resource.RUSAGE_SELF)
    rssMb = round(rusage.ru_maxrss / (1024 * 1024), 1)  # macOS reports bytes
    # Linux reports KB — detect platform
    import platform
    if platform.system() == 'Linux':
        rssMb = round(rusage.ru_maxrss / 1024, 1)

    # Count in-memory game objects and their play data
    scheduleGames = 0
    gamesWithPlays = 0
    totalPlays = 0
    if season and season.schedule:
        for weekEntry in season.schedule:
            for g in weekEntry.get('games', []):
                scheduleGames += 1
                feedLen = len(getattr(g, 'gameFeed', []))
                if feedLen > 0:
                    gamesWithPlays += 1
                    totalPlays += feedLen

    # Personality distribution across all players
    personality = {
        'total': 0,
        'baseVibes': 0,
        'commonVariants': 0,
        'rareVariants': 0,
        'unassigned': 0,
        'quirked': 0,
        'rareVariantList': [],
        'personalityCounts': {},
        'quirkCounts': {},
    }
    try:
        from collections import Counter
        from managers.personalityReactionEngine import (
            BASE_VIBES, COMMON_VARIANTS, RARE_VARIANTS,
        )
        allPlayers = (
            pm.activePlayers + pm.freeAgents + pm.rookieDraftList
        ) if pm else []
        pCounts: Counter = Counter()
        qCounts: Counter = Counter()
        for p in allPlayers:
            attrs = getattr(p, 'attributes', None)
            if attrs is None:
                continue
            pers = getattr(attrs, 'personality', None)
            quirk = getattr(attrs, 'quirk', None)
            if pers:
                pCounts[pers] += 1
            else:
                personality['unassigned'] += 1
            if quirk:
                qCounts[quirk] += 1
        personality['total'] = len(allPlayers)
        personality['baseVibes'] = sum(c for p, c in pCounts.items() if p in BASE_VIBES)
        personality['commonVariants'] = sum(c for p, c in pCounts.items() if p in COMMON_VARIANTS)
        personality['rareVariants'] = sum(c for p, c in pCounts.items() if p in RARE_VARIANTS)
        personality['rareVariantList'] = sorted(p for p in pCounts if p in RARE_VARIANTS)
        personality['quirked'] = sum(qCounts.values())
        personality['personalityCounts'] = dict(pCounts.most_common())
        personality['quirkCounts'] = dict(qCounts.most_common())
    except Exception as _e:
        # Don't fail the dashboard if personality system isn't loaded
        pass

    return build_success_response({
        "deploySafety": {
            "safe": deploySafe,
            "reason": deployReason,
        },
        "simulation": {
            "isActive": simState.get('is_active', False) if simState else False,
            "phase": phase,
            "lastSaved": simState.get('last_saved').isoformat() + 'Z' if simState and simState.get('last_saved') else None,
        },
        "season": {
            "seasonNumber": liveSeasonNum,
            "currentWeek": liveWeek,
            "currentWeekText": liveWeekText,
            "inPlayoffs": phase == "playoffs",
            "playoffRound": simState.get('playoff_round', None) if simState else None,
            "isComplete": liveComplete,
            "champion": championName,
            "mvp": mvpName,
            "totalGames": totalGames,
            "completedGames": completedGames,
        },
        "liveGames": {
            "active": activeCount,
            "scheduled": scheduledCount,
            "final": finalCount,
        },
        "timing": {
            "mode": timing.mode.value if timing else None,
            "catchingUp": getattr(timing, 'catchingUp', False) if timing else False,
        },
        "counts": {
            "teams": len(tm.teams) if tm else 0,
            "activePlayers": len(pm.activePlayers) if pm else 0,
            "freeAgents": len(pm.freeAgents) if pm else 0,
            "retiredPlayers": len(pm.retiredPlayers) if pm else 0,
            "hallOfFame": len(pm.hallOfFame) if pm else 0,
        },
        "memory": {
            "rssMb": rssMb,
            "totalMb": round(os.sysconf('SC_PAGE_SIZE') * os.sysconf('SC_PHYS_PAGES') / (1024 * 1024)),
            "scheduleGames": scheduleGames,
            "gamesWithPlays": gamesWithPlays,
            "totalPlaysInMemory": totalPlays,
            "pid": os.getpid(),
        },
        "websockets": ws_manager.get_stats(),
        "personality": personality,
    })


@app.get("/api/admin/analytics")
async def admin_analytics(_auth: None = Depends(_checkAdminAuth)):
    """Admin: analytics dashboard — economy, cards, fantasy, users, funding, pick-em."""

    if floosball_app is None:
        raise HTTPException(status_code=503, detail="Application not initialized")

    from database.connection import get_session
    from database.models import (
        User, UserCurrency, CurrencyTransaction, CardTemplate, UserCard,
        EquippedCard, PackOpening, PackType, FantasyRoster, FantasyRosterPlayer,
        FantasyRosterSwap, PickEmPick, TeamFunding, Team, Player,
        BetaAccessRequest, BetaAllowlist, CardUpgradeLog,
    )
    from sqlalchemy import func, case
    from datetime import timedelta

    sm = floosball_app.seasonManager
    season = sm.currentSeason
    seasonNum = getattr(season, 'seasonNumber', 1) if season else 1

    session = get_session()
    try:
        now = datetime.utcnow()
        sevenDaysAgo = now - timedelta(days=7)
        thirtyDaysAgo = now - timedelta(days=30)

        # ── Economy Health ──────────────────────────────────────────────
        circulationRow = session.query(
            func.coalesce(func.sum(UserCurrency.balance), 0),
            func.coalesce(func.sum(UserCurrency.lifetime_earned), 0),
            func.coalesce(func.sum(UserCurrency.lifetime_spent), 0),
        ).first()
        totalCirculation = circulationRow[0]
        totalEarned = circulationRow[1]
        totalSpent = circulationRow[2]

        earningsRows = session.query(
            CurrencyTransaction.transaction_type,
            func.sum(CurrencyTransaction.amount),
        ).filter(
            CurrencyTransaction.season == seasonNum,
            CurrencyTransaction.amount > 0,
        ).group_by(CurrencyTransaction.transaction_type).all()
        earningsBreakdown = {t: int(v) for t, v in earningsRows}

        spendingRows = session.query(
            CurrencyTransaction.transaction_type,
            func.sum(func.abs(CurrencyTransaction.amount)),
        ).filter(
            CurrencyTransaction.season == seasonNum,
            CurrencyTransaction.amount < 0,
        ).group_by(CurrencyTransaction.transaction_type).all()
        spendingBreakdown = {t: int(v) for t, v in spendingRows}

        seasonEarnings = session.query(
            func.coalesce(func.sum(CurrencyTransaction.amount), 0),
        ).filter(
            CurrencyTransaction.season == seasonNum,
            CurrencyTransaction.amount > 0,
        ).scalar()

        seasonSpending = session.query(
            func.coalesce(func.sum(func.abs(CurrencyTransaction.amount)), 0),
        ).filter(
            CurrencyTransaction.season == seasonNum,
            CurrencyTransaction.amount < 0,
        ).scalar()

        # Average & median balance
        avgBalanceRow = session.query(
            func.coalesce(func.avg(UserCurrency.balance), 0),
        ).first()
        avgBalance = round(float(avgBalanceRow[0]), 1)

        allBalances = [
            b for (b,) in session.query(UserCurrency.balance).order_by(UserCurrency.balance).all()
        ]
        if allBalances:
            midIdx = len(allBalances) // 2
            medianBalance = (allBalances[midIdx] if len(allBalances) % 2 == 1
                             else round((allBalances[midIdx - 1] + allBalances[midIdx]) / 2, 1))
        else:
            medianBalance = 0

        # Weekly FP→F payout summary (curve-based, no cap)
        lastPaidWeek = session.query(func.max(CurrencyTransaction.week)).filter(
            CurrencyTransaction.season == seasonNum,
            CurrencyTransaction.transaction_type == 'weekly_fp_bonus',
        ).scalar()
        if lastPaidWeek:
            weekPayouts = session.query(CurrencyTransaction.amount).filter(
                CurrencyTransaction.season == seasonNum,
                CurrencyTransaction.week == lastPaidWeek,
                CurrencyTransaction.transaction_type == 'weekly_fp_bonus',
            ).all()
            amounts = [int(p[0]) for p in weekPayouts]
            totalFpRecipients = len(amounts)
            avgWeeklyPayout = round(sum(amounts) / totalFpRecipients, 1) if totalFpRecipients else 0
            maxWeeklyPayout = max(amounts) if amounts else 0
            capHitWeek = lastPaidWeek
        else:
            totalFpRecipients = 0
            avgWeeklyPayout = 0
            maxWeeklyPayout = 0
            capHitWeek = None

        # Richest users (top 5)
        richestRows = session.query(
            User.username, UserCurrency.balance,
        ).join(User, UserCurrency.user_id == User.id
        ).order_by(UserCurrency.balance.desc()).limit(5).all()
        richestUsers = [{"username": u or "(no name)", "balance": int(b)} for u, b in richestRows]

        # ── Card Analytics ──────────────────────────────────────────────
        totalCards = session.query(func.count(UserCard.id)).scalar()

        cardsByEdition = session.query(
            CardTemplate.edition, func.count(UserCard.id),
        ).join(CardTemplate, UserCard.card_template_id == CardTemplate.id
        ).group_by(CardTemplate.edition).all()

        cardsBySource = session.query(
            UserCard.acquired_via, func.count(UserCard.id),
        ).group_by(UserCard.acquired_via).all()

        # Top equipped effects this season — use Python Counter as safe fallback
        from collections import Counter
        from sqlalchemy.orm import joinedload
        equippedRows = session.query(EquippedCard).filter(
            EquippedCard.season == seasonNum,
        ).options(
            joinedload(EquippedCard.user_card).joinedload(UserCard.card_template)
        ).all()
        effectCounts = Counter()
        effectTooltips = {}
        for eq in equippedRows:
            if eq.user_card and eq.user_card.card_template:
                cfg = eq.user_card.card_template.effect_config or {}
                eName = cfg.get("effectName", "")
                if eName:
                    effectCounts[eName] += 1
                    if eName not in effectTooltips:
                        effectTooltips[eName] = cfg.get("tooltip", "")
        topEffects = [{"effectName": n, "count": c, "tooltip": effectTooltips.get(n, "")} for n, c in effectCounts.most_common(5)]
        allEffects = effectCounts.most_common()
        allEffects.reverse()
        bottomEffects = [{"effectName": n, "count": c, "tooltip": effectTooltips.get(n, "")} for n, c in allEffects[:5]] if len(allEffects) >= 5 else []

        packRows = session.query(
            PackType.name, func.count(PackOpening.id),
        ).join(PackType, PackOpening.pack_type_id == PackType.id
        ).group_by(PackType.name).all()
        packOpenings = {n: c for n, c in packRows}

        # Combine / upgrade usage
        combineRows = session.query(
            CardUpgradeLog.upgrade_type, func.count(CardUpgradeLog.id),
        ).group_by(CardUpgradeLog.upgrade_type).all()
        combineUsage = {t: c for t, c in combineRows}
        totalCombineUses = sum(c for _, c in combineRows)

        # Users who equipped cards this season
        usersWhoEquipped = session.query(
            func.count(func.distinct(EquippedCard.user_id)),
        ).filter(EquippedCard.season == seasonNum).scalar()

        # ── Fantasy Engagement ──────────────────────────────────────────
        rosterRow = session.query(
            func.count(FantasyRoster.id),
            func.coalesce(func.avg(FantasyRoster.total_points), 0),
            func.coalesce(func.avg(FantasyRoster.card_bonus_points), 0),
            func.coalesce(func.sum(FantasyRoster.purchased_swaps), 0),
        ).filter(FantasyRoster.season == seasonNum).first()
        totalRosters = rosterRow[0]
        avgTotalPoints = round(float(rosterRow[1]), 1)
        avgCardBonus = round(float(rosterRow[2]), 1)
        totalPurchasedSwaps = rosterRow[3]

        totalSwapsUsed = session.query(func.count(FantasyRosterSwap.id)).join(
            FantasyRoster, FantasyRosterSwap.roster_id == FantasyRoster.id,
        ).filter(FantasyRoster.season == seasonNum).scalar()

        topRosteredRows = session.query(
            Player.name, func.count(FantasyRosterPlayer.id).label('cnt'),
        ).join(
            FantasyRosterPlayer, FantasyRosterPlayer.player_id == Player.id,
        ).join(
            FantasyRoster, FantasyRosterPlayer.roster_id == FantasyRoster.id,
        ).filter(
            FantasyRoster.season == seasonNum,
        ).group_by(Player.id, Player.name).order_by(
            func.count(FantasyRosterPlayer.id).desc(),
        ).limit(5).all()
        topRosteredPlayers = [{"name": n, "count": c} for n, c in topRosteredRows]

        # ── User Engagement ─────────────────────────────────────────────
        totalUsers = session.query(func.count(User.id)).scalar()
        active7d = session.query(func.count(User.id)).filter(User.last_login_at >= sevenDaysAgo).scalar()
        active30d = session.query(func.count(User.id)).filter(User.last_login_at >= thirtyDaysAgo).scalar()
        onboardedCount = session.query(func.count(User.id)).filter(User.has_completed_onboarding == True).scalar()
        onboardingRate = round((onboardedCount / totalUsers * 100), 1) if totalUsers > 0 else 0

        favTeamRows = session.query(
            Team.name, func.count(User.id).label('cnt'),
        ).join(Team, User.favorite_team_id == Team.id
        ).group_by(Team.id, Team.name
        ).order_by(func.count(User.id).desc()).limit(10).all()
        favoriteTeams = [{"team": n, "count": c} for n, c in favTeamRows]

        usersWithRoster = session.query(func.count(func.distinct(FantasyRoster.user_id))).filter(
            FantasyRoster.season == seasonNum).scalar()
        usersWithCards = session.query(func.count(func.distinct(UserCard.user_id))).scalar()
        usersWithPicks = session.query(func.count(func.distinct(PickEmPick.user_id))).filter(
            PickEmPick.season == seasonNum).scalar()
        usersWhoFunded = session.query(func.count(func.distinct(CurrencyTransaction.user_id))).filter(
            CurrencyTransaction.season == seasonNum,
            CurrencyTransaction.transaction_type == 'team_contribution',
        ).scalar()

        # Beta funnel: users who signed up but never requested access
        allUserEmails = set(
            e.lower().strip() for (e,) in session.query(User.email).all()
        )
        requestedEmails = set(
            e.lower().strip() for (e,) in session.query(BetaAccessRequest.email).all()
        )
        allowedEmails = set(
            e.lower().strip() for (e,) in session.query(BetaAllowlist.email).all()
        )
        signupOnlyCount = len(allUserEmails - requestedEmails - allowedEmails)

        # Churn risk — onboarded users inactive 14+ days
        fourteenDaysAgo = now - timedelta(days=14)
        churnRiskCount = session.query(func.count(User.id)).filter(
            User.has_completed_onboarding == True,
            User.last_login_at < fourteenDaysAgo,
        ).scalar()

        # Daily active users (last 28 days). Driven by UserLoginDay so the
        # historical numbers stay stable — last_login_at-based queries
        # silently shrunk past-day counts every time a returning user
        # logged in again (their date moved forward, leaving older days
        # with a smaller "users whose most recent login was that day"
        # count). UserLoginDay records every distinct (user, calendar
        # date) login, so DAU counts only grow as more users return on
        # any given day.
        from database.models import UserLoginDay
        twentyEightDaysAgo = (now - timedelta(days=28)).date()
        dailyActiveRows = session.query(
            UserLoginDay.login_date,
            func.count(func.distinct(UserLoginDay.user_id)),
        ).filter(
            UserLoginDay.login_date >= twentyEightDaysAgo,
        ).group_by(UserLoginDay.login_date).order_by(UserLoginDay.login_date).all()
        dailyActiveUsers = [{"date": str(d), "count": c} for d, c in dailyActiveRows if d]

        # Onboarding funnel
        funnelPickedUsername = session.query(func.count(User.id)).filter(
            User.username.isnot(None),
        ).scalar()
        funnelChoseFavTeam = session.query(func.count(User.id)).filter(
            User.favorite_team_id.isnot(None),
        ).scalar()
        funnelDraftedRoster = session.query(
            func.count(func.distinct(FantasyRoster.user_id)),
        ).scalar()

        # ── Team Funding ────────────────────────────────────────────────
        totalFanContributions = session.query(
            func.coalesce(func.sum(TeamFunding.fan_contributions), 0),
        ).filter(TeamFunding.season == seasonNum).scalar()

        tierRows = session.query(
            TeamFunding.funding_tier, func.count(TeamFunding.id),
        ).filter(TeamFunding.season == seasonNum
        ).group_by(TeamFunding.funding_tier).all()
        tierDistribution = {(t or "none"): c for t, c in tierRows}

        topFundedRows = session.query(
            Team.name, TeamFunding.fan_contributions, TeamFunding.funding_tier,
        ).join(Team, TeamFunding.team_id == Team.id).filter(
            TeamFunding.season == seasonNum,
        ).order_by(TeamFunding.fan_contributions.desc()).limit(5).all()
        topFundedTeams = [{"team": n, "contributions": int(c), "tier": t} for n, c, t in topFundedRows]

        # ── Pick-Em ─────────────────────────────────────────────────────
        pickEmRow = session.query(
            func.count(PickEmPick.id),
            func.count(case((PickEmPick.correct == True, 1))),
            func.count(case((PickEmPick.correct.isnot(None), 1))),
            func.count(func.distinct(PickEmPick.user_id)),
        ).filter(PickEmPick.season == seasonNum).first()
        totalPicks = pickEmRow[0]
        correctPicks = pickEmRow[1]
        resolvedPicks = pickEmRow[2]
        pickEmParticipants = pickEmRow[3]
        pickEmAccuracy = round((correctPicks / resolvedPicks * 100), 1) if resolvedPicks > 0 else 0

        # Pick-em participation trend by week
        pickEmTrendRows = session.query(
            PickEmPick.week,
            func.count(func.distinct(PickEmPick.user_id)),
            func.count(PickEmPick.id),
        ).filter(
            PickEmPick.season == seasonNum,
        ).group_by(PickEmPick.week).order_by(PickEmPick.week).all()
        pickEmTrend = [{"week": w, "participants": p, "picks": pk} for w, p, pk in pickEmTrendRows]

        return build_success_response({
            "seasonNumber": seasonNum,
            "economy": {
                "totalCirculation": int(totalCirculation),
                "totalEarned": int(totalEarned),
                "totalSpent": int(totalSpent),
                "earningsBreakdown": earningsBreakdown,
                "spendingBreakdown": spendingBreakdown,
                "seasonEarnings": int(seasonEarnings),
                "seasonSpending": int(seasonSpending),
                "avgBalance": avgBalance,
                "medianBalance": medianBalance,
                "avgWeeklyPayout": avgWeeklyPayout,
                "maxWeeklyPayout": maxWeeklyPayout,
                "weeklyPayoutRecipients": totalFpRecipients,
                "lastPayoutWeek": capHitWeek,
                "richestUsers": richestUsers,
            },
            "cards": {
                "totalCards": totalCards,
                "byEdition": {e: c for e, c in cardsByEdition},
                "bySource": {s: c for s, c in cardsBySource},
                "topEffects": topEffects,
                "bottomEffects": bottomEffects,
                "packOpenings": packOpenings,
                "combineUsage": combineUsage,
                "totalCombineUses": totalCombineUses,
                "usersWhoEquipped": usersWhoEquipped,
            },
            "fantasy": {
                "totalRosters": totalRosters,
                "avgTotalPoints": avgTotalPoints,
                "avgCardBonus": avgCardBonus,
                "totalSwapsUsed": totalSwapsUsed,
                "totalPurchasedSwaps": totalPurchasedSwaps,
                "topRosteredPlayers": topRosteredPlayers,
            },
            "users": {
                "totalUsers": totalUsers,
                "active7d": active7d,
                "active30d": active30d,
                "onboardingRate": onboardingRate,
                "onboardedCount": onboardedCount,
                "favoriteTeams": favoriteTeams,
                "adoption": {
                    "fantasy": usersWithRoster,
                    "cards": usersWithCards,
                    "pickEm": usersWithPicks,
                    "funding": usersWhoFunded,
                },
                "signupOnly": signupOnlyCount,
                "churnRiskCount": churnRiskCount,
                "dailyActiveUsers": dailyActiveUsers,
                "onboardingFunnel": {
                    "hasAccount": totalUsers,
                    "pickedUsername": funnelPickedUsername,
                    "choseFavTeam": funnelChoseFavTeam,
                    "draftedRoster": funnelDraftedRoster,
                    "hasCards": usersWithCards,
                },
            },
            "funding": {
                "totalFanContributions": int(totalFanContributions),
                "tierDistribution": tierDistribution,
                "topTeams": topFundedTeams,
            },
            "pickEm": {
                "totalPicks": totalPicks,
                "accuracy": pickEmAccuracy,
                "participants": pickEmParticipants,
                "trend": pickEmTrend,
            },
        })
    except Exception as e:
        logger.error(f"Error fetching analytics: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@app.get("/api/admin/achievements")
async def admin_achievements(_auth: None = Depends(_checkAdminAuth)):
    """Admin: per-achievement unlock counts and completion rates.

    For `per_season` achievements, counts are scoped to the current season.
    For `once` achievements, counts are all-time.
    """
    if floosball_app is None:
        raise HTTPException(status_code=503, detail="Application not initialized")

    from database.connection import get_session
    from database.models import Achievement, UserAchievement, User
    from sqlalchemy import func

    sm = floosball_app.seasonManager
    seasonNum = sm.currentSeason.seasonNumber if sm and sm.currentSeason else 0

    session = get_session()
    try:
        totalUsers = session.query(func.count(User.id)).scalar() or 0

        # Count distinct users who completed each achievement, season-scoped for per_season
        rows = (
            session.query(
                Achievement.id,
                Achievement.key,
                Achievement.name,
                Achievement.category,
                Achievement.scope,
                Achievement.target,
                Achievement.sort_order,
                func.count(func.distinct(UserAchievement.user_id)).label("unlocks"),
                func.coalesce(func.avg(UserAchievement.progress), 0).label("avgProgress"),
            )
            .outerjoin(
                UserAchievement,
                (UserAchievement.achievement_id == Achievement.id)
                & (UserAchievement.completed_at.isnot(None))
                & (
                    ((Achievement.scope == "once") & (UserAchievement.season == 0))
                    | ((Achievement.scope == "per_season") & (UserAchievement.season == seasonNum))
                ),
            )
            .group_by(Achievement.id)
            .order_by(Achievement.sort_order.asc())
            .all()
        )

        achievements = [{
            "id": r.id,
            "key": r.key,
            "name": r.name,
            "category": r.category,
            "scope": r.scope,
            "target": r.target,
            "unlocks": int(r.unlocks or 0),
            "totalUsers": int(totalUsers),
            "unlockPct": round(100.0 * (r.unlocks or 0) / totalUsers, 1) if totalUsers else 0.0,
            "avgProgress": round(float(r.avgProgress or 0), 1),
        } for r in rows]

        return build_success_response({
            "achievements": achievements,
            "totalUsers": int(totalUsers),
            "season": seasonNum,
        })
    finally:
        session.close()


from api.auth import getOptionalUser as _getOptionalUser
from database.models import User as _User

@app.get("/api/offseason")
async def get_offseason_info(user: _User = Depends(_getOptionalUser)):
    """Offseason state: free agents, draft order, user's ballot"""
    if floosball_app is None:
        raise HTTPException(status_code=503, detail="Application not initialized")
    sm = floosball_app.seasonManager
    pm = floosball_app.playerManager
    isOffseason = getattr(sm.currentSeason, 'currentWeekText', '') == 'Offseason'
    # During replay, _freeAgentSnapshot holds the full pre-signing pool (expired contracts + replacements).
    # Once replay completes, snapshot is cleared and we fall back to the live leftover pool.
    snapshot = getattr(pm, '_freeAgentSnapshot', None)
    if snapshot is not None:
        faList = snapshot
    else:
        faList = [
            {
                "id": p.id,
                "name": p.name,
                "position": p.position.name,
                "rating": round(p.playerRating, 1),
                "tier": p.playerTier.name,
            }
            for p in sorted(pm.freeAgents, key=lambda p: -p.playerRating)
            if isinstance(getattr(p, 'team', None), str)
        ]
    draftOrder = []
    # Once the FA draft preview has run (pre_fa phase onward), prefer the
    # tier-sorted order it computed and stored. Falls back to the rookie
    # draft order (worst-first) for earlier phases. Without this fallback,
    # a refresh during pre_fa wipes the tier groupings the frontend just
    # rendered, since the rookie order is the only one currently in
    # currentSeason.freeAgencyOrder.
    flowPhase = getattr(sm, '_offseasonFlowPhase', None)
    pendingFaOrder = getattr(sm, '_pendingFaDraftOrder', None)
    if flowPhase in ('pre_fa', 'fa_draft') and pendingFaOrder:
        sourceOrder = pendingFaOrder
    elif sm.currentSeason and hasattr(sm.currentSeason, 'freeAgencyOrder'):
        sourceOrder = sm.currentSeason.freeAgencyOrder
    else:
        sourceOrder = []
    for t in sourceOrder:
        draftOrder.append({
            "name": t.name,
            "city": getattr(t, 'city', ''),
            "abbr": getattr(t, 'abbr', t.name[:3].upper()),
            "id": getattr(t, 'id', None),
            "color": getattr(t, 'color', None),
            "complete": getattr(t, 'freeAgencyComplete', False),
            "fundingTier": getattr(t, 'fundingTier', 'MID_MARKET'),
            "fundingTierRank": getattr(t, 'fundingTierRank', 3),
        })
    transactions = getattr(sm, '_offseasonTransactions', [])
    faWindowOpen = getattr(sm, '_faWindowOpen', False)
    faWindowEnd = getattr(sm, '_faWindowEnd', None)
    # Always include FA pool during offseason so ballot rank markers work after window closes
    # Defensive: only include players whose .team is actually 'Free Agent' (not a team object)
    faPool = [
        {"id": p.id, "name": p.name, "position": p.position.name,
         "rating": round(p.playerRating, 1), "tier": p.playerTier.name}
        for p in pm.freeAgents
        if isinstance(getattr(p, 'team', None), str)
    ] if isOffseason else []

    # Include user's existing ballot if logged in. FA ballots can be submitted
    # year-round from the Front Office tab (not just during the offseason
    # window), so return the latest saved ballot whenever a user is
    # authenticated and has a favorite team set.
    existingBallot = None
    if user:
        try:
            from database.connection import get_session
            from database.repositories.gm_repository import GmFaBallotRepository
            from database.models import User
            session = get_session()
            try:
                dbUser = session.query(User).filter_by(id=user.id).first()
                if dbUser and dbUser.favorite_team_id:
                    currentSeason = sm.currentSeason.seasonNumber if sm and sm.currentSeason else 0
                    ballotRepo = GmFaBallotRepository(session)
                    ballot = ballotRepo.getUserBallot(user.id, dbUser.favorite_team_id, currentSeason)
                    if ballot:
                        existingBallot = json.loads(ballot.rankings)
            finally:
                session.close()
        except Exception:
            pass

    # Include resolved FA directives for user's favorite team (if any)
    faDirectives = []
    if user and isOffseason:
        try:
            gmDirectives = getattr(pm, '_gmFaDirectives', {}) or {}
            from database.models import User as _UserModel
            session2 = get_session()
            try:
                dbUser2 = session2.query(_UserModel).filter_by(id=user.id).first()
                favTeamId = dbUser2.favorite_team_id if dbUser2 else None
            finally:
                session2.close()
            if favTeamId and favTeamId in gmDirectives:
                faLookup = {p.id: p for p in pm.activePlayers}
                for pid in gmDirectives[favTeamId]:
                    p = faLookup.get(pid)
                    if p:
                        faDirectives.append({
                            "id": p.id, "name": p.name,
                            "position": p.position.name,
                            "rating": round(p.playerRating, 1),
                        })
        except Exception:
            pass

    draftComplete = len(draftOrder) > 0 and all(t.get("complete") for t in draftOrder)
    # GM vote resolutions for the Directives tab — survives refresh.
    gmResolutions = getattr(sm, '_offseasonGmResults', []) or []
    # Active phase — lets the frontend restore tier grouping + rookie list on refresh.
    phase = getattr(sm, '_offseasonPhase', None)
    # Per-team per-position fan vote rankings (after FA ballot resolution).
    faVoteResults = getattr(sm, '_offseasonFaVoteResults', {}) or {}

    # Per-team aggregated fan rookie ballot rankings (Borda-count tally),
    # keyed by team abbr → list of ranked players with id/name/position/rating
    # and post-draft drafted-by team info. Mirrors faVoteResults so the FO
    # page can render the same kind of resolved-rankings panel for rookies.
    rookieBallotResultsRaw = getattr(sm, '_offseasonRookieBallotResults', {}) or {}
    rookieBallotResults: Dict[str, List[Dict[str, Any]]] = {}
    if rookieBallotResultsRaw:
        playerLookup = {p.id: p for p in pm.activePlayers}
        teamManager = floosball_app.teamManager if floosball_app else None
        for teamId, rankedIds in rookieBallotResultsRaw.items():
            t = teamManager.getTeamById(teamId) if teamManager else None
            if not t:
                continue
            abbr = getattr(t, 'abbr', t.name[:3].upper())
            ranked = []
            for pid in rankedIds:
                pp = playerLookup.get(pid)
                if not pp:
                    continue
                draftingTeamId = getattr(pp, 'drafting_team_id', None)
                draftingAbbr = None
                if draftingTeamId and teamManager:
                    dt = teamManager.getTeamById(draftingTeamId)
                    if dt:
                        draftingAbbr = getattr(dt, 'abbr', None)
                ranked.append({
                    "id": pp.id, "name": pp.name,
                    "position": pp.position.name,
                    "rating": round(getattr(pp, 'playerRating', 0), 1),
                    "tier": getattr(pp, 'playerTier', None).name if getattr(pp, 'playerTier', None) else None,
                    "draftedByTeamId": draftingTeamId,
                    "draftedByTeamAbbr": draftingAbbr,
                })
            if ranked:
                rookieBallotResults[abbr] = ranked

    # Upcoming rookies that haven't yet been consumed by the draft. Surfacing
    # these on /api/offseason means a mid-draft refresh restores the right-
    # panel rookie list — without this, refreshing during the rookie draft
    # leaves rookies=[] and the panel reads "All prospects drafted".
    upcomingRookies = [
        {
            'id': getattr(r, 'id', 0),
            'name': r.name,
            'position': r.position.name,
            'rating': round(getattr(r, 'playerRating', 0), 1),
            'tier': getattr(r, 'playerTier', None).name if getattr(r, 'playerTier', None) else 'TierC',
        }
        for r in pm.activePlayers
        if getattr(r, 'is_upcoming_rookie', False)
    ]

    return {
        "isOffseason": isOffseason, "freeAgents": faList, "draftOrder": draftOrder,
        "transactions": transactions, "faWindowOpen": faWindowOpen,
        "faWindowEnd": faWindowEnd, "faPool": faPool,
        "existingBallot": existingBallot, "faDirectives": faDirectives,
        "gmResolutions": gmResolutions,
        "faVoteResults": faVoteResults,
        "rookieBallotResults": rookieBallotResults,
        "rookies": upcomingRookies,
        "phase": phase,
        "draftComplete": draftComplete,
    }


# ============================================================================
# AUTH & USER ENDPOINTS
# ============================================================================

from api.auth import getCurrentUser as _getCurrentUser, getOptionalUser as _getOptionalUser
from database.models import User as _User, Team as _Team


@app.post("/api/teams/{team_id}/contribute")
def contribute_to_team(team_id: int, payload: Dict[str, Any], user: _User = Depends(_getCurrentUser)):
    """Contribute Floobits to a team's funding pool mid-season. Requires auth."""
    if floosball_app is None:
        raise HTTPException(status_code=503, detail="Application not initialized")

    amount = payload.get("amount")
    if not isinstance(amount, int) or amount <= 0:
        raise HTTPException(status_code=400, detail="'amount' must be a positive integer")

    try:
        result = floosball_app.seasonManager.contributeToTeam(user.id, team_id, amount)
        # Achievement hook — first team contribution
        from database.connection import get_session as _getSessionPatron
        from managers import achievementManager as _am
        _s = _getSessionPatron()
        try:
            _am.onTeamContribution(_s, user.id)
            _s.commit()
        except Exception as _e:
            _s.rollback()
            logger.warning(f"Achievement hook failed (patron): {_e}")
        finally:
            _s.close()
        return build_success_response(result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error contributing to team {team_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/teams/{team_id}/projected-funding")
def get_projected_funding(team_id: int):
    """Estimate end-of-season auto-contribution funding for a team.
    Calculates what each fan would contribute if the season ended now,
    based on their current balance and funding percentage.
    Also projects next season's tier after carry-forward decay."""
    import math
    from constants import DEFAULT_FUNDING_PCT, FUNDING_DECAY_RATE, FUNDING_BASELINE_PER_TEAM, FUNDING_TIER_NAMES
    from database.connection import get_session
    from database.models import User, UserCurrency, TeamFunding
    session = get_session()
    try:
        fans = session.query(User).filter(User.favorite_team_id == team_id).all()
        totalProjected = 0
        fanCount = 0
        for fan in fans:
            pct = getattr(fan, 'team_funding_pct', DEFAULT_FUNDING_PCT)
            if pct is None:
                pct = DEFAULT_FUNDING_PCT
            pct = max(0, min(100, pct))
            if pct <= 0:
                continue
            currency = session.query(UserCurrency).filter_by(user_id=fan.id).first()
            balance = currency.balance if currency else 0
            if balance <= 0:
                continue
            contribution = math.floor(balance * pct / 100.0)
            if contribution > 0:
                totalProjected += contribution
                fanCount += 1

        # Compute next-season projected effective funding after decay
        sm = floosball_app.seasonManager if floosball_app else None
        currentSeasonNum = sm.currentSeason.seasonNumber if sm and sm.currentSeason else 1
        currentRec = session.query(TeamFunding).filter_by(
            team_id=team_id, season=currentSeasonNum).first()
        # Next-season projection: decay this season's effective funding + reset
        # baseline. This is what locks in the tier the team starts NEXT season
        # under. Tiers are computed as share-of-league on the same basis.
        currentEffective = (currentRec.effective_funding or 0) if currentRec else 0
        endOfSeasonEffective = currentEffective + totalProjected
        nextSeasonCarried = math.floor(endOfSeasonEffective * FUNDING_DECAY_RATE)
        nextSeasonEffective = FUNDING_BASELINE_PER_TEAM + nextSeasonCarried

        import math as _math
        currentFundingByTeam = {
            r.team_id: r for r in
            session.query(TeamFunding).filter_by(season=currentSeasonNum).all()
        }
        # Fan auto-contributions per team
        projectedByTeam: dict = {}
        allFans = session.query(User).filter(User.favorite_team_id.isnot(None)).all()
        balancesByUser = {
            uc.user_id: uc.balance for uc in
            session.query(UserCurrency).filter(UserCurrency.user_id.in_([f.id for f in allFans])).all()
        }
        for fan in allFans:
            tid = fan.favorite_team_id
            pct = getattr(fan, 'team_funding_pct', DEFAULT_FUNDING_PCT)
            if pct is None:
                pct = DEFAULT_FUNDING_PCT
            pct = max(0, min(100, pct))
            bal = balancesByUser.get(fan.id, 0) or 0
            if pct > 0 and bal > 0:
                projectedByTeam[tid] = projectedByTeam.get(tid, 0) + _math.floor(bal * pct / 100.0)

        # Build every team's NEXT-season projected effective funding for the
        # share-of-league tier calc.
        allTeamIds = [t.id for t in floosball_app.teamManager.teams] if (floosball_app and floosball_app.teamManager) else []
        teamProjections = []
        for tid in allTeamIds:
            rec = currentFundingByTeam.get(tid)
            teamEndOfSeason = (rec.effective_funding or 0) if rec else 0
            teamEndOfSeason += projectedByTeam.get(tid, 0)
            teamCarried = _math.floor(teamEndOfSeason * FUNDING_DECAY_RATE)
            teamProjections.append((tid, FUNDING_BASELINE_PER_TEAM + teamCarried))

        from constants import FUNDING_TIER_THRESHOLDS as _TIER_THRESH
        totalProjLeague = sum(p for _, p in teamProjections)
        fairShareProj = max(1, totalProjLeague / max(1, len(teamProjections)))
        nextSeasonTier = FUNDING_TIER_NAMES[-1]
        for tid, projected in teamProjections:
            if tid == team_id:
                ratio = projected / fairShareProj
                for name in FUNDING_TIER_NAMES:
                    if ratio >= _TIER_THRESH[name]:
                        nextSeasonTier = name
                        break
                break

        return build_success_response({
            "teamId": team_id,
            "projectedAutoContributions": totalProjected,
            "contributingFans": fanCount,
            "totalFans": len(fans),
            "nextSeasonProjectedFunding": nextSeasonEffective,
            "nextSeasonProjectedTier": nextSeasonTier,
            "decayRate": FUNDING_DECAY_RATE,
        })
    except Exception as e:
        logger.error(f"Error calculating projected funding for team {team_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@app.get("/api/league/markets/history")
def get_league_markets_history():
    """Per-season tier/funding history for every team, all seasons.

    Powers the tier-trajectory chart on the Markets section — shows which
    teams have been climbing and which have been sliding. Returns sparse data
    (teams only appear in seasons where they have a TeamFunding record).
    """
    if floosball_app is None:
        raise HTTPException(503, "Application not initialized")
    from database.connection import get_session
    from database.models import TeamFunding

    tm = floosball_app.teamManager
    if not tm:
        return build_success_response({"seasons": [], "teams": []})

    session = get_session()
    try:
        # Pull every funding record across all seasons, group by team
        rows = session.query(TeamFunding).order_by(
            TeamFunding.team_id, TeamFunding.season
        ).all()

        historyByTeam: Dict[int, List[Dict[str, Any]]] = {}
        seasonSet = set()
        for r in rows:
            seasonSet.add(r.season)
            historyByTeam.setdefault(r.team_id, []).append({
                "season": r.season,
                "tier": r.funding_tier or 'MID_MARKET',
                "tierRank": r.tier_rank or 3,
                "effectiveFunding": r.effective_funding or 0,
            })

        teamsPayload = []
        for team in tm.teams:
            hist = historyByTeam.get(team.id, [])
            teamsPayload.append({
                "id": team.id,
                "name": team.name,
                "city": getattr(team, 'city', ''),
                "abbr": getattr(team, 'abbr', team.name[:3].upper()),
                "color": getattr(team, 'color', '#64748b'),
                "history": hist,
            })

        return build_success_response({
            "seasons": sorted(seasonSet),
            "teams": teamsPayload,
        })
    finally:
        session.close()


@app.get("/api/league/markets")
def get_league_markets():
    """League-wide market & funding view.

    Returns every team with current tier, effective funding, contributing fan
    count, and top patrons (highest-contributing users this season). Used by
    the Markets page to surface tier rankings and social/economic pressure.
    """
    if floosball_app is None:
        raise HTTPException(503, "Application not initialized")
    from database.connection import get_session
    from database.models import User, TeamFunding, CurrencyTransaction, UserCurrency
    from sqlalchemy import func

    tm = floosball_app.teamManager
    sm = floosball_app.seasonManager
    if not tm or not sm or not sm.currentSeason:
        return build_success_response({"season": 0, "teams": []})
    currentSeason = sm.currentSeason.seasonNumber

    session = get_session()
    try:
        # Map: team_id → TeamFunding row
        fundingByTeam = {
            r.team_id: r for r in
            session.query(TeamFunding).filter_by(season=currentSeason).all()
        }

        # Contributing fans per team — users who favorite the team AND
        # contributed floobits at least once this season.
        contributorRows = (
            session.query(
                User.favorite_team_id.label('team_id'),
                func.count(func.distinct(User.id)).label('fan_count'),
            )
            .join(CurrencyTransaction, CurrencyTransaction.user_id == User.id)
            .filter(
                CurrencyTransaction.transaction_type == 'team_contribution',
                CurrencyTransaction.season == currentSeason,
                User.favorite_team_id.isnot(None),
            )
            .group_by(User.favorite_team_id)
            .all()
        )
        fanCountByTeam = {r.team_id: r.fan_count for r in contributorRows}

        # Total fans per team — every user with favorite_team_id set,
        # whether they've contributed this season or not.
        totalFansRows = (
            session.query(
                User.favorite_team_id.label('team_id'),
                func.count(User.id).label('total_fans'),
            )
            .filter(User.favorite_team_id.isnot(None))
            .group_by(User.favorite_team_id)
            .all()
        )
        totalFansByTeam = {r.team_id: r.total_fans for r in totalFansRows}

        # Top patrons per team — up to 3, by total contributed this season
        patronRows = (
            session.query(
                User.id.label('user_id'),
                User.username.label('username'),
                User.favorite_team_id.label('team_id'),
                func.coalesce(func.sum(-CurrencyTransaction.amount), 0).label('total'),
            )
            .join(CurrencyTransaction, CurrencyTransaction.user_id == User.id)
            .filter(
                CurrencyTransaction.transaction_type == 'team_contribution',
                CurrencyTransaction.season == currentSeason,
                User.favorite_team_id.isnot(None),
            )
            .group_by(User.id, User.username, User.favorite_team_id)
            .order_by(func.sum(-CurrencyTransaction.amount).desc())
            .all()
        )
        patronsByTeam: Dict[int, List[Dict[str, Any]]] = {}
        for row in patronRows:
            existing = patronsByTeam.setdefault(row.team_id, [])
            if len(existing) < 3 and row.total and row.total > 0:
                existing.append({
                    "userId": row.user_id,
                    "username": row.username or f"User #{row.user_id}",
                    "totalContributed": int(row.total),
                })

        # Previous season tier for movement indicator
        prevTiers: Dict[int, str] = {}
        if currentSeason > 1:
            prevRows = session.query(TeamFunding).filter_by(season=currentSeason - 1).all()
            for r in prevRows:
                if r.funding_tier:
                    prevTiers[r.team_id] = r.funding_tier

        # Project each team's next-season effective funding using the same
        # logic as /api/teams/{id}/projected-funding, but batched for all
        # teams in one pass. Result: projectedTier per team so the markets
        # view can show "where everyone is heading" alongside current tier.
        from constants import (
            DEFAULT_FUNDING_PCT as _DEF_PCT,
            FUNDING_DECAY_RATE as _DECAY,
            FUNDING_BASELINE_PER_TEAM as _BASE,
            FUNDING_TIER_NAMES as _TIER_NAMES,
        )
        import math as _math
        allFans = session.query(User).filter(User.favorite_team_id.isnot(None)).all()
        balancesByUser = {
            uc.user_id: uc.balance for uc in
            session.query(UserCurrency).filter(
                UserCurrency.user_id.in_([f.id for f in allFans] or [0])
            ).all()
        } if allFans else {}
        projectedContribByTeam: Dict[int, int] = {}
        for fan in allFans:
            tid = fan.favorite_team_id
            pct = getattr(fan, 'team_funding_pct', _DEF_PCT)
            if pct is None:
                pct = _DEF_PCT
            pct = max(0, min(100, pct))
            bal = balancesByUser.get(fan.id, 0) or 0
            if pct > 0 and bal > 0:
                projectedContribByTeam[tid] = projectedContribByTeam.get(tid, 0) + _math.floor(bal * pct / 100.0)
        from constants import FUNDING_TIER_THRESHOLDS as _TIER_THRESH
        projectedTierByTeam: Dict[int, str] = {}
        projectedFundingByTeam: Dict[int, int] = {}
        # Projection = NEXT season's effective funding after decay + fresh
        # baseline. This is what locks in the tier for the next season.
        # Decay compresses heavy-funded teams' shares (50% carry + flat
        # baseline helps low teams relatively more), so projected share can
        # be lower than current share even when absolute funding grows.
        for team in tm.teams:
            rec = fundingByTeam.get(team.id)
            endOfSeason = (rec.effective_funding or 0) if rec else 0
            endOfSeason += projectedContribByTeam.get(team.id, 0)
            carried = _math.floor(endOfSeason * _DECAY)
            projectedFundingByTeam[team.id] = _BASE + carried
        totalProjLeague = sum(projectedFundingByTeam.values())
        fairShareProj = max(1, totalProjLeague / max(1, len(projectedFundingByTeam)))
        for tid, projFunding in projectedFundingByTeam.items():
            ratio = projFunding / fairShareProj
            tier = _TIER_NAMES[-1]
            for name in _TIER_NAMES:
                if ratio >= _TIER_THRESH[name]:
                    tier = name
                    break
            projectedTierByTeam[tid] = tier

        # Build per-team payload
        tierOrderMap = {'MEGA_MARKET': 1, 'LARGE_MARKET': 2, 'MID_MARKET': 3, 'SMALL_MARKET': 4}
        teamsPayload = []
        for team in tm.teams:
            fundingRec = fundingByTeam.get(team.id)
            tier = fundingRec.funding_tier if fundingRec else 'MID_MARKET'
            prevTier = prevTiers.get(team.id)
            movement = 0
            if prevTier and prevTier in tierOrderMap and tier in tierOrderMap:
                # Lower rank = higher tier, so movement = prev_rank - current_rank
                # Positive = climbed, negative = dropped
                movement = tierOrderMap[prevTier] - tierOrderMap[tier]

            teamsPayload.append({
                "id": team.id,
                "name": team.name,
                "city": getattr(team, 'city', ''),
                "abbr": getattr(team, 'abbr', team.name[:3].upper()),
                "color": getattr(team, 'color', '#64748b'),
                "tier": tier,
                "tierRank": fundingRec.tier_rank if fundingRec else 3,
                "effectiveFunding": fundingRec.effective_funding if fundingRec else 0,
                "baselineFunding": fundingRec.baseline_funding if fundingRec else 0,
                "fanContributions": fundingRec.fan_contributions if fundingRec else 0,
                "carriedFunding": fundingRec.carried_funding if fundingRec else 0,
                # Funding value the current tier was computed from — chart's
                # filled "locked" dot lands here so it always sits inside the
                # band the tier badge displays.
                "tierLockedFunding": (
                    getattr(fundingRec, 'tier_locked_funding', None)
                    or (fundingRec.effective_funding if fundingRec else 0)
                ),
                "fanCount": fanCountByTeam.get(team.id, 0),
                "totalFans": totalFansByTeam.get(team.id, 0),
                "topPatrons": patronsByTeam.get(team.id, []),
                "tierMovement": movement,  # +1 = climbed one tier, -1 = dropped, 0 = held
                "projectedTier": projectedTierByTeam.get(team.id, tier),
                "projectedFunding": projectedFundingByTeam.get(team.id, fundingRec.effective_funding if fundingRec else 0),
                "record": {
                    "wins": team.seasonTeamStats.get('wins', 0) if hasattr(team, 'seasonTeamStats') else 0,
                    "losses": team.seasonTeamStats.get('losses', 0) if hasattr(team, 'seasonTeamStats') else 0,
                },
            })

        # Sort by tier rank then effective funding desc
        teamsPayload.sort(key=lambda t: (t['tierRank'], -t['effectiveFunding']))

        return build_success_response({
            "season": currentSeason,
            "teams": teamsPayload,
        })
    finally:
        session.close()


@app.get("/api/teams/{team_id}/prospects")
def get_team_prospects(team_id: int):
    """Prospects stashed in this team's pipeline.

    Surfaces the full list with development context so the UI can show progress,
    window remaining, and promotion readiness. Ordered by rating desc.
    """
    if floosball_app is None:
        raise HTTPException(503, "Application not initialized")
    tm = floosball_app.teamManager
    team = tm.getTeamById(team_id) if tm else None
    if not team:
        raise HTTPException(404, "Team not found")

    from constants import PROSPECT_DEVELOPMENT_WINDOW, PROSPECT_PROMOTION_RATING_THRESHOLD
    from database.connection import get_session
    from database.models import PlayerRatingHistory

    # Pull every prospect's rating history in one batched query so the UI can
    # render a sparkline without N extra fetches.
    prospectList = list(getattr(team, 'prospects', []))
    historyByPlayer: Dict[int, List[Dict[str, int]]] = {}
    if prospectList:
        session = get_session()
        try:
            rows = session.query(PlayerRatingHistory).filter(
                PlayerRatingHistory.player_id.in_([p.id for p in prospectList])
            ).order_by(PlayerRatingHistory.player_id, PlayerRatingHistory.season).all()
            for r in rows:
                historyByPlayer.setdefault(r.player_id, []).append({
                    "season": r.season,
                    "rating": r.rating,
                })
        finally:
            session.close()

    prospects = []
    for p in prospectList:
        rating = round(getattr(p, 'playerRating', 0), 1)
        posName = p.position.name if hasattr(p.position, 'name') else str(p.position)
        # Build a series including the current (live) rating as the latest
        # point, tagged with the current season. For rookies with no prior
        # history, this produces a single-point series.
        history = list(historyByPlayer.get(p.id, []))
        sm = floosball_app.seasonManager
        currentSeasonNum = sm.currentSeason.seasonNumber if sm and sm.currentSeason else 0
        if currentSeasonNum and (not history or history[-1]["season"] != currentSeasonNum):
            history.append({"season": currentSeasonNum, "rating": int(round(rating))})
        prospectSeasonsElapsed = getattr(p, 'prospect_seasons', 0) or 0
        # draftSeason = the season the prospect entered the pipeline.
        # prospect_seasons increments at each offseason, so during season N a
        # prospect with prospect_seasons=0 was drafted into season N.
        draftSeason = currentSeasonNum - prospectSeasonsElapsed if currentSeasonNum else None
        prospects.append({
            "playerId": p.id,
            "name": p.name,
            "position": posName,
            "rating": rating,
            "tier": p.playerTier.name if hasattr(p, 'playerTier') else None,
            "prospectSeasons": prospectSeasonsElapsed,
            "seasonsRemaining": max(0, PROSPECT_DEVELOPMENT_WINDOW - prospectSeasonsElapsed),
            "draftSeason": draftSeason,
            "isUndrafted": bool(getattr(p, 'is_undrafted', False)),
            "ratingHistory": history,
        })
    prospects.sort(key=lambda x: -x['rating'])
    return build_success_response({
        "teamId": team_id,
        "prospects": prospects,
        "slotCapPerPosition": 2,  # mirrors constants.PROSPECT_SLOT_CAP_PER_POSITION
        "developmentWindow": PROSPECT_DEVELOPMENT_WINDOW,
        "promotionThreshold": PROSPECT_PROMOTION_RATING_THRESHOLD,
    })


@app.get("/api/players/{player_id}/rating-history")
def get_player_rating_history(player_id: int):
    """Rating trajectory for a single player across every season played.

    Returns an ordered list of {season, rating} points — one per season where
    a snapshot exists. The current season's live rating is appended as the
    latest point if not yet snapshotted.
    """
    if floosball_app is None:
        raise HTTPException(503, "Application not initialized")
    from database.connection import get_session
    from database.models import PlayerRatingHistory

    session = get_session()
    try:
        rows = session.query(PlayerRatingHistory).filter_by(
            player_id=player_id
        ).order_by(PlayerRatingHistory.season).all()
        history = [
            {"season": r.season, "rating": r.rating,
             "offensiveRating": r.offensive_rating, "defensiveRating": r.defensive_rating}
            for r in rows
        ]
    finally:
        session.close()

    # Append the current live rating as the latest point so the sparkline
    # reflects in-season state even before the next snapshot fires
    sm = floosball_app.seasonManager
    pm = floosball_app.playerManager
    currentSeasonNum = sm.currentSeason.seasonNumber if sm and sm.currentSeason else 0
    player = pm.getPlayerById(player_id) if hasattr(pm, 'getPlayerById') else None
    if player is None:
        # fallback — scan activePlayers
        player = next((p for p in pm.activePlayers if p.id == player_id), None)
    if player is not None and currentSeasonNum:
        currentRating = int(round(getattr(player, 'playerRating', 0) or 0))
        if not history or history[-1]["season"] != currentSeasonNum:
            history.append({
                "season": currentSeasonNum, "rating": currentRating,
                "offensiveRating": getattr(player, 'offensiveRating', None),
                "defensiveRating": getattr(player, 'defensiveRating', None),
            })

    return build_success_response({
        "playerId": player_id,
        "history": history,
    })


@app.get("/api/teams/{team_id}/retirement-watch")
def get_team_retirement_watch(team_id: int):
    """Players on this team's roster flagged by retirement risk.

    Surfaces the same tiers used at offseason time so fans can see farewell-tour
    candidates all season and pre-vote replacements. Returns only players with
    non-'safe' risk (plus 'safe' vets close to the bubble are filtered out).
    """
    if floosball_app is None:
        raise HTTPException(503, "Application not initialized")
    tm = floosball_app.teamManager
    pm = floosball_app.playerManager
    team = tm.getTeamById(team_id) if tm else None
    if not team:
        raise HTTPException(404, "Team not found")

    watch = []
    for position, player in team.rosterDict.items():
        if player is None:
            continue
        risk = pm.computeRetirementRisk(player)
        if risk == 'safe':
            continue
        watch.append({
            "playerId": player.id,
            "name": player.name,
            "position": player.position.name if hasattr(player.position, 'name') else str(player.position),
            "rosterSlot": position,
            "rating": round(getattr(player, 'playerRating', 0), 1),
            "seasonsPlayed": getattr(player, 'seasonsPlayed', 0),
            "longevity": getattr(getattr(player, 'attributes', None), 'longevity', 0),
            "termRemaining": getattr(player, 'termRemaining', 0),
            "risk": risk,
        })

    # Sort by risk severity (most at-risk first), then by rating (higher = more impactful loss)
    riskOrder = {'retiring': 0, 'very_likely': 1, 'likely': 2, 'possible': 3}
    watch.sort(key=lambda w: (riskOrder.get(w['risk'], 9), -w['rating']))

    return build_success_response({
        "teamId": team_id,
        "watch": watch,
    })


@app.get("/api/users/me")
def get_current_user_profile(user: _User = Depends(_getCurrentUser)):
    """Get current user profile. Requires Bearer token."""
    from database.models import UserCurrency, FollowedPlayer
    from database.connection import get_session
    session = get_session()
    try:
        currency = session.query(UserCurrency).filter_by(user_id=user.id).first()
        followedRows = session.query(FollowedPlayer.player_id).filter_by(user_id=user.id).all()
        followedPlayerIds = [r[0] for r in followedRows]
        return {
            "id": user.id,
            "email": user.email,
            "username": user.username,
            "favoriteTeamId": user.favorite_team_id,
            "pendingFavoriteTeamId": user.pending_favorite_team_id,
            "favoriteTeamLockedSeason": user.favorite_team_locked_season,
            "floobits": currency.balance if currency else 0,
            "hasCompletedOnboarding": user.has_completed_onboarding,
            "emailOptOut": user.email_opt_out,
            "emailDayReport": user.email_day_report,
            "emailSeasonReport": user.email_season_report,
            "teamFundingPct": 25 if getattr(user, 'team_funding_pct', 25) is None else user.team_funding_pct,
            "autoPickMode": getattr(user, 'auto_pick_mode', 'off') or 'off',
            "isAdmin": getattr(user, 'is_admin', False),
            "followedPlayerIds": followedPlayerIds,
        }
    finally:
        session.close()


@app.post("/api/players/{player_id}/follow")
def follow_player(player_id: int, user: _User = Depends(_getCurrentUser)):
    """Add a player to the user's followed list. Idempotent."""
    from database.models import FollowedPlayer, Player as DBPlayer
    from database.connection import get_session
    session = get_session()
    try:
        if not session.query(DBPlayer.id).filter_by(id=player_id).first():
            raise HTTPException(status_code=404, detail=f"Player {player_id} not found")
        existing = session.query(FollowedPlayer).filter_by(
            user_id=user.id, player_id=player_id,
        ).first()
        if not existing:
            session.add(FollowedPlayer(user_id=user.id, player_id=player_id))
            session.commit()
        return build_success_response({"playerId": player_id, "following": True})
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        logger.error(f"follow_player error: {e}")
        raise HTTPException(500, "Failed to follow player")
    finally:
        session.close()


@app.delete("/api/players/{player_id}/follow")
def unfollow_player(player_id: int, user: _User = Depends(_getCurrentUser)):
    """Remove a player from the user's followed list. Idempotent."""
    from database.models import FollowedPlayer
    from database.connection import get_session
    session = get_session()
    try:
        session.query(FollowedPlayer).filter_by(
            user_id=user.id, player_id=player_id,
        ).delete()
        session.commit()
        return build_success_response({"playerId": player_id, "following": False})
    except Exception as e:
        session.rollback()
        logger.error(f"unfollow_player error: {e}")
        raise HTTPException(500, "Failed to unfollow player")
    finally:
        session.close()


@app.post("/api/users/me/onboarding-complete")
def complete_onboarding(user: _User = Depends(_getCurrentUser)):
    """Mark the current user as having completed onboarding."""
    from database.connection import get_session
    session = get_session()
    try:
        dbUser = session.get(_User, user.id)
        dbUser.has_completed_onboarding = True
        session.commit()
        return {"ok": True}
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@app.get("/api/users/me/username-options")
def get_username_options(user: _User = Depends(_getCurrentUser)):
    """Return 4 unique username candidates for the user to choose from."""
    from database.connection import get_session
    from api.auth import generateUsernameCandidates
    session = get_session()
    try:
        options = generateUsernameCandidates(session, count=4)
        return {"options": options}
    finally:
        session.close()


@app.post("/api/users/me/username")
def set_username(payload: Dict[str, Any], user: _User = Depends(_getCurrentUser)):
    """Set the current user's username (only if not already set)."""
    from database.connection import get_session
    chosen = payload.get("username", "").strip()
    if not chosen:
        raise HTTPException(status_code=400, detail="Username is required")

    session = get_session()
    try:
        dbUser = session.get(_User, user.id)
        if dbUser.username is not None:
            raise HTTPException(status_code=400, detail="Username already set")

        # Check uniqueness
        existing = session.query(_User).filter(_User.username == chosen).first()
        if existing:
            raise HTTPException(status_code=409, detail="Username already taken")

        dbUser.username = chosen
        session.commit()
        return {"ok": True, "username": chosen}
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@app.patch("/api/users/me/preferences")
def update_user_preferences(payload: Dict[str, Any], user: _User = Depends(_getCurrentUser)):
    """Update user preferences (email opt-out, etc.)."""
    from database.connection import get_session
    session = get_session()
    try:
        dbUser = session.get(_User, user.id)
        if "emailOptOut" in payload:
            dbUser.email_opt_out = bool(payload["emailOptOut"])
        if "emailDayReport" in payload:
            dbUser.email_day_report = bool(payload["emailDayReport"])
        if "emailSeasonReport" in payload:
            dbUser.email_season_report = bool(payload["emailSeasonReport"])
        if "teamFundingPct" in payload:
            pct = int(payload["teamFundingPct"])
            dbUser.team_funding_pct = max(0, min(100, pct))
        if "autoPickMode" in payload:
            mode = str(payload["autoPickMode"] or "off").lower()
            if mode not in ("off", "favorites", "underdogs", "random"):
                raise HTTPException(status_code=400, detail=f"Invalid autoPickMode: {mode}")
            dbUser.auto_pick_mode = mode
        session.commit()
        return {
            "ok": True,
            "emailOptOut": dbUser.email_opt_out,
            "emailDayReport": dbUser.email_day_report,
            "emailSeasonReport": dbUser.email_season_report,
            "teamFundingPct": dbUser.team_funding_pct,
            "autoPickMode": dbUser.auto_pick_mode,
        }
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@app.get("/api/user/favorite-team")
def get_favorite_team(user: _User = Depends(_getCurrentUser)):
    """Get the current user's favorite team."""
    from database.connection import get_session
    session = get_session()
    try:
        result = {}
        if user.favorite_team_id is not None:
            team = session.get(_Team, user.favorite_team_id)
            if team:
                result = {"id": team.id, "name": team.name, "city": team.city, "abbr": team.abbr, "color": team.color}
        if user.pending_favorite_team_id is not None:
            pendingTeam = session.get(_Team, user.pending_favorite_team_id)
            if pendingTeam:
                result["pendingTeam"] = {"id": pendingTeam.id, "name": pendingTeam.name, "city": pendingTeam.city, "abbr": pendingTeam.abbr, "color": pendingTeam.color}
        return result or None
    finally:
        session.close()


class FavoriteTeamRequest(BaseModel):
    teamId: int


def _isOffseason() -> bool:
    """Check if the simulation is in offseason (no active season or between seasons)."""
    if floosball_app is None:
        return True
    sm = floosball_app.seasonManager
    if sm.currentSeason is None:
        return True
    return sm.currentSeason.currentWeekText == 'Offseason'

def _getCurrentSeasonNumber() -> Optional[int]:
    """Get the current season number from the season manager."""
    if floosball_app is None:
        return None
    sm = floosball_app.seasonManager
    if sm.currentSeason is None:
        return None
    return sm.currentSeason.seasonNumber


@app.patch("/api/user/favorite-team")
def set_favorite_team(req: FavoriteTeamRequest, user: _User = Depends(_getCurrentUser)):
    """Set the current user's favorite team with season-lock logic."""
    from database.connection import get_session
    session = get_session()
    try:
        team = session.get(_Team, req.teamId)
        if team is None:
            raise HTTPException(status_code=404, detail="Team not found")
        dbUser = session.get(_User, user.id)
        offseason = _isOffseason()
        currentSeasonNum = _getCurrentSeasonNumber()

        # If same team as current, no-op
        if dbUser.favorite_team_id == req.teamId:
            # Clear any pending if they switch back
            if dbUser.pending_favorite_team_id is not None:
                dbUser.pending_favorite_team_id = None
                session.commit()
            return {"favoriteTeamId": req.teamId, "isPending": False, "favoriteTeamLockedSeason": dbUser.favorite_team_locked_season}

        if offseason or dbUser.favorite_team_id is None:
            # Offseason or first-time pick: apply immediately
            wasFirstTime = dbUser.favorite_team_id is None
            dbUser.favorite_team_id = req.teamId
            dbUser.pending_favorite_team_id = None
            if currentSeasonNum is not None and not offseason:
                dbUser.favorite_team_locked_season = currentSeasonNum
            if wasFirstTime:
                from managers import achievementManager as _am
                _am.onFavoriteTeamChosen(session, user.id)
            session.commit()
            return {"favoriteTeamId": req.teamId, "isPending": False, "favoriteTeamLockedSeason": dbUser.favorite_team_locked_season}

        # Mid-season with existing favorite: set as pending
        if currentSeasonNum is not None and dbUser.favorite_team_locked_season == currentSeasonNum:
            # Already changed once this season — update pending
            dbUser.pending_favorite_team_id = req.teamId
            session.commit()
            return {"favoriteTeamId": dbUser.favorite_team_id, "pendingFavoriteTeamId": req.teamId, "isPending": True}

        # First change this season: lock current and set pending
        dbUser.favorite_team_locked_season = currentSeasonNum
        dbUser.pending_favorite_team_id = req.teamId
        session.commit()
        return {"favoriteTeamId": dbUser.favorite_team_id, "pendingFavoriteTeamId": req.teamId, "isPending": True}
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        logger.error(f"Error setting favorite team: {e}")
        raise HTTPException(status_code=500, detail="Failed to update favorite team")
    finally:
        session.close()


# ============================================================================
# NOTIFICATION ENDPOINTS
# ============================================================================

@app.get("/api/notifications")
def get_notifications(user: _User = Depends(_getCurrentUser)):
    """Get recent notifications for the current user."""
    import json as _json
    from database.connection import get_session
    from database.repositories.notification_repository import NotificationRepository
    session = get_session()
    try:
        repo = NotificationRepository(session)
        notifs = repo.getRecent(user.id, limit=20)
        return {
            "notifications": [
                {
                    "id": n.id,
                    "type": n.type,
                    "title": n.title,
                    "message": n.message,
                    "data": _json.loads(n.data) if n.data else None,
                    "isRead": n.is_read,
                    "createdAt": n.created_at.isoformat() + 'Z' if n.created_at else None,
                }
                for n in notifs
            ]
        }
    finally:
        session.close()


@app.get("/api/notifications/count")
def get_notification_count(user: _User = Depends(_getCurrentUser)):
    """Get unread notification count for polling."""
    from database.connection import get_session
    from database.repositories.notification_repository import NotificationRepository
    session = get_session()
    try:
        repo = NotificationRepository(session)
        return {"unread": repo.getUnreadCount(user.id)}
    finally:
        session.close()


@app.post("/api/notifications/read")
def mark_notifications_read(payload: Dict[str, Any], user: _User = Depends(_getCurrentUser)):
    """Mark notification(s) as read. Send {id: N} for one, or {all: true} for all."""
    from database.connection import get_session
    from database.repositories.notification_repository import NotificationRepository
    session = get_session()
    try:
        repo = NotificationRepository(session)
        if payload.get("all"):
            count = repo.markAllRead(user.id)
        elif payload.get("id"):
            repo.markRead(user.id, payload["id"])
            count = 1
        else:
            raise HTTPException(status_code=400, detail="Provide 'id' or 'all: true'")
        session.commit()
        return {"marked": count}
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


# ============================================================================
# FANTASY ROSTER ENDPOINTS
# ============================================================================

# Valid fantasy roster slots and their required player positions (enum int values)
_SLOT_POSITION_MAP = {
    'QB': 1,   # Position.QB
    'RB': 2,   # Position.RB
    'WR1': 3,  # Position.WR
    'WR2': 3,  # Position.WR
    'TE': 4,   # Position.TE
    'K': 5,    # Position.K
}
_VALID_SLOTS = set(_SLOT_POSITION_MAP.keys())

# Minimum player count to lock a roster (also enforced by /remove).
# Shared with seasonManager's auto-lock via constants.py.
from constants import ROSTER_MIN_PLAYERS


def _getPlayerLiveFantasyPoints(player) -> float:
    """Get a player's current live fantasy points (season + in-game)."""
    sd = player.seasonStatsDict
    return sd.get('fantasyPoints', 0) + player.gameStatsDict.get('fantasyPoints', 0)


@app.get("/api/fantasy/roster")
def get_fantasy_roster(user: _User = Depends(_getCurrentUser)):
    """Get the current user's fantasy roster for the current season."""
    from database.connection import get_session
    from database.models import FantasyRoster, FantasyRosterPlayer, FantasyRosterSwap, Player

    currentSeasonNum = _getCurrentSeasonNumber()

    session = get_session()
    try:
        roster = None
        if currentSeasonNum is not None:
            roster = session.query(FantasyRoster).filter_by(
                user_id=user.id, season=currentSeasonNum
            ).first()

        displaySeason = currentSeasonNum

        # Check if user has FLEX slot (champion card or temp_flex power-up)
        # Must run before the early return so users building a new roster see the slot
        hasFlexSlot = False
        try:
            from database.models import EquippedCard, UserCard, CardTemplate, ShopPurchase
            sm = floosball_app.seasonManager if floosball_app else None
            currentWeek = sm.currentSeason.currentWeek if sm and sm.currentSeason else 0
            flexSeason = (roster.season if roster else displaySeason) or 0
            if flexSeason:
                championCount = (
                    session.query(EquippedCard.id)
                    .join(UserCard, EquippedCard.user_card_id == UserCard.id)
                    .join(CardTemplate, UserCard.card_template_id == CardTemplate.id)
                    .filter(
                        EquippedCard.user_id == user.id,
                        EquippedCard.season == flexSeason,
                        EquippedCard.week == currentWeek,
                        CardTemplate.classification.isnot(None),
                        CardTemplate.classification.contains("champion"),
                    )
                    .limit(1).count()
                )
                if championCount > 0:
                    hasFlexSlot = True
                else:
                    activeFlex = session.query(ShopPurchase).filter(
                        ShopPurchase.user_id == user.id,
                        ShopPurchase.season == flexSeason,
                        ShopPurchase.item_slug == "temp_flex",
                        ShopPurchase.expires_at_week >= currentWeek,
                    ).first()
                    if activeFlex:
                        hasFlexSlot = True
        except Exception:
            pass

        if roster is None:
            return build_success_response({"roster": None, "season": displaySeason, "hasFlexSlot": hasFlexSlot})

        # Note: hasFlexSlot reflects only the user's current entitlement
        # (active temp_flex powerup OR equipped Champion card). A stale FLEX
        # rosterPlayer left behind from an expired powerup does NOT keep
        # hasFlexSlot true — the seasonManager sweeps those at week start so
        # this should rarely matter, but the swap endpoint also re-validates
        # before any add/swap action.

        rosterPlayers = []
        for rp in roster.players:
            playerObj = floosball_app.playerManager.getPlayerById(rp.player_id) if floosball_app else None
            seasonFp = playerObj.seasonStatsDict.get('fantasyPoints', 0) if playerObj else 0
            currentFp = _getPlayerLiveFantasyPoints(playerObj) if playerObj else 0
            earnedPoints = max(0, currentFp - rp.points_at_lock) if roster.is_locked else 0

            entry = {
                "slot": rp.slot,
                "playerId": rp.player_id,
                "playerName": playerObj.name if playerObj else "Unknown",
                "position": playerObj.position.name if playerObj and hasattr(playerObj.position, 'name') else "",
                "teamId": playerObj.team.id if playerObj and hasattr(playerObj.team, 'id') else None,
                "teamName": playerObj.team.name if playerObj and hasattr(playerObj.team, 'name') else "",
                "teamAbbr": getattr(playerObj.team, 'abbr', '') if playerObj and hasattr(playerObj.team, 'name') else "",
                "teamColor": getattr(playerObj.team, 'color', '#334155') if playerObj and hasattr(playerObj.team, 'name') else "#334155",
                "ratingStars": PlayerResponseBuilder.calculateStarRating(playerObj.playerRating) if playerObj else 0,
                "fatigue": round((getattr(playerObj.attributes, 'fatigue', 0.0) or 0.0) * 100, 1) if playerObj else 0,
                "pointsAtLock": rp.points_at_lock,
                "seasonFantasyPoints": round(seasonFp, 1),
                "currentFantasyPoints": currentFp,
                "earnedPoints": earnedPoints,
            }
            rosterPlayers.append(entry)

        totalEarned = sum(p["earnedPoints"] for p in rosterPlayers)

        # Build swap history. old/new player_id may be NULL for remove/fill rows.
        swapHistory = []
        for swap in roster.swaps:
            oldPlayerObj = session.get(Player, swap.old_player_id) if swap.old_player_id else None
            newPlayerObj = session.get(Player, swap.new_player_id) if swap.new_player_id else None
            swapHistory.append({
                "slot": swap.slot,
                "oldPlayerName": oldPlayerObj.name if oldPlayerObj else None,
                "newPlayerName": newPlayerObj.name if newPlayerObj else None,
                "swapWeek": swap.swap_week,
                "bankedFP": round(swap.banked_fp, 1),
            })

        # Per-slot swap cost preview. Escalation counts only paid actions —
        # rows with a non-null new_player_id (regular swaps + fills of empty
        # slots). /remove rows (new_player_id NULL) don't escalate the price.
        # Empty slots with no swap history at all get a free first fill —
        # covers both initial temp_flex fill AND partial-roster locks where
        # the user saved with empty slots. Surface as cost=0 so the UI
        # can say "Free".
        from constants import ROSTER_SWAP_COST, ROSTER_SWAP_COST_INCREMENT
        from collections import Counter
        slotSwapCounts = Counter(swap.slot for swap in roster.swaps if swap.new_player_id is not None)
        anyMovementBySlot = Counter(swap.slot for swap in roster.swaps)
        filledSlotKeys = {rp.slot for rp in roster.players}
        allSlots = ["QB", "RB", "WR1", "WR2", "TE", "K", "FLEX"]
        swapCosts = {}
        for slot in allSlots:
            slotEmpty = slot not in filledSlotKeys
            slotUntouched = anyMovementBySlot.get(slot, 0) == 0
            if slotEmpty and slotUntouched:
                swapCosts[slot] = 0
            else:
                swapCosts[slot] = ROSTER_SWAP_COST + ROSTER_SWAP_COST_INCREMENT * slotSwapCounts.get(slot, 0)

        # gamesActive: scoring visible (in progress or just finished between weeks)
        # gamesInProgress: blocks roster swaps (only while a game is actively being played)
        gamesActive = _areGamesStarted() or _areGamesCompleted()
        sm = floosball_app.seasonManager if floosball_app else None
        gamesInProgress = False
        if sm and sm.currentSeason and sm.currentSeason.activeGames:
            gamesInProgress = any(
                getattr(g, 'status', None) == FloosGame.GameStatus.Active
                for g in sm.currentSeason.activeGames
            )

        cardBonus = roster.card_bonus_points or 0.0
        return build_success_response({
            "roster": {
                "id": roster.id,
                "season": roster.season,
                "isLocked": roster.is_locked,
                "lockedAt": roster.locked_at.isoformat() + 'Z' if roster.locked_at else None,
                "totalPoints": totalEarned,
                "cardBonusPoints": cardBonus,
                "swapsAvailable": roster.swaps_available,
                "purchasedSwaps": roster.purchased_swaps,
                "hasFlexSlot": hasFlexSlot,
                "players": rosterPlayers,
                "swapHistory": swapHistory,
                "swapCosts": swapCosts,
            },
            "season": displaySeason,
            "gamesActive": gamesActive,
            "gamesInProgress": gamesInProgress,
        })
    finally:
        session.close()


class FantasyRosterPlayerRequest(BaseModel):
    playerId: int
    slot: str


class FantasyRosterRequest(BaseModel):
    players: List[FantasyRosterPlayerRequest]


@app.put("/api/fantasy/roster")
def set_fantasy_roster(req: FantasyRosterRequest, user: _User = Depends(_getCurrentUser)):
    """Set/update the user's fantasy roster (only when unlocked)."""
    from database.connection import get_session
    from database.models import FantasyRoster, FantasyRosterPlayer, UserCard, CardTemplate

    currentSeasonNum = _getCurrentSeasonNumber()
    if currentSeasonNum is None:
        raise HTTPException(status_code=400, detail="No active season")

    # Check if user has a Champion-classified card equipped (allows FLEX slot)
    from database.models import EquippedCard, ShopPurchase
    hasChampion = False
    hasTempFlex = False
    sm = floosball_app.seasonManager if floosball_app else None
    currentWeek = sm.currentSeason.currentWeek if sm and sm.currentSeason else 0
    checkSession = get_session()
    try:
        championCount = (
            checkSession.query(EquippedCard.id)
            .join(UserCard, EquippedCard.user_card_id == UserCard.id)
            .join(CardTemplate, UserCard.card_template_id == CardTemplate.id)
            .filter(
                EquippedCard.user_id == user.id,
                EquippedCard.season == currentSeasonNum,
                EquippedCard.week == currentWeek,
                CardTemplate.classification.isnot(None),
                CardTemplate.classification.contains("champion"),
            )
            .limit(1)
            .count()
        )
        hasChampion = championCount > 0

        # Check for active Temporary Flex Slot power-up
        activeFlex = checkSession.query(ShopPurchase).filter(
            ShopPurchase.user_id == user.id,
            ShopPurchase.season == currentSeasonNum,
            ShopPurchase.item_slug == "temp_flex",
            ShopPurchase.expires_at_week >= currentWeek,
        ).first()
        hasTempFlex = activeFlex is not None
    finally:
        checkSession.close()

    hasFlexSlot = hasChampion or hasTempFlex

    # Build valid slots — add FLEX if user has a champion card or temp flex power-up
    validSlots = set(_VALID_SLOTS)
    slotPositionMap = dict(_SLOT_POSITION_MAP)
    if hasFlexSlot:
        validSlots.add("FLEX")
        # FLEX accepts any position (validated separately below)

    # Validate slots
    slots = [p.slot for p in req.players]
    for slot in slots:
        if slot not in validSlots:
            detail = f"Invalid slot: {slot}. Must be one of: {', '.join(sorted(validSlots))}"
            if slot == "FLEX" and not hasFlexSlot:
                detail = "FLEX slot requires a Champion card or Flex Slot power-up"
            raise HTTPException(status_code=400, detail=detail)
    if len(slots) != len(set(slots)):
        raise HTTPException(status_code=400, detail="Duplicate slots in roster")

    # Validate no duplicate players
    playerIds = [p.playerId for p in req.players]
    if len(playerIds) != len(set(playerIds)):
        raise HTTPException(status_code=400, detail="Duplicate players in roster")

    # Validate each player exists and position matches slot
    if floosball_app is None:
        raise HTTPException(status_code=503, detail="Application not initialized")

    for rp in req.players:
        playerObj = floosball_app.playerManager.getPlayerById(rp.playerId)
        if playerObj is None:
            raise HTTPException(status_code=404, detail=f"Player {rp.playerId} not found")
        if rp.slot == "FLEX":
            continue  # FLEX accepts any position
        expectedPos = slotPositionMap[rp.slot]
        playerPos = playerObj.position.value if hasattr(playerObj.position, 'value') else playerObj.position
        if playerPos != expectedPos:
            raise HTTPException(status_code=400, detail=f"Player {playerObj.name} is not eligible for slot {rp.slot}")

    session = get_session()
    try:
        roster = session.query(FantasyRoster).filter_by(
            user_id=user.id, season=currentSeasonNum
        ).first()

        if roster and roster.is_locked:
            raise HTTPException(status_code=409, detail="Roster is locked for this season")

        if roster is None:
            roster = FantasyRoster(user_id=user.id, season=currentSeasonNum)
            session.add(roster)
            session.flush()

        # Clear existing players and insert new
        session.query(FantasyRosterPlayer).filter_by(roster_id=roster.id).delete()
        for rp in req.players:
            session.add(FantasyRosterPlayer(
                roster_id=roster.id,
                player_id=rp.playerId,
                slot=rp.slot,
            ))

        # Snapshot the initial roster on the FIRST save only. The Loyalty card
        # pays per player still on roster from this snapshot, so we never
        # overwrite it after the first commit.
        if not roster.initial_player_ids:
            import json as _json
            roster.initial_player_ids = _json.dumps(
                [int(rp.playerId) for rp in req.players]
            )
        # Achievement hooks — first-time roster set + secrets (Shoestring, Homer)
        from managers import achievementManager as _am
        _am.onFantasyRosterSet(session, user.id)

        # Inspect the submitted roster for secret conditions.
        # Rosters have 6 default slots (QB/RB/WR1/WR2/TE/K); temp_flex powerup adds a 7th FLEX.
        if req.players and len(req.players) >= 6:
            from database.models import Player
            from api_response_builders import PlayerResponseBuilder
            playerIds = [rp.playerId for rp in req.players]
            players = session.query(Player).filter(Player.id.in_(playerIds)).all()
            if len(players) == len(req.players):
                # Shoestring — every roster player rated 3 stars or lower
                allLowStar = all(
                    PlayerResponseBuilder.calculateStarRating(p.player_rating) <= 3
                    for p in players
                )
                if allLowStar:
                    _am.unlockSecret(session, user.id, "shoestring")
                # Homer — every roster player on your favorite team
                favTeamId = getattr(user, "favorite_team_id", None)
                if favTeamId and all(p.team_id == favTeamId for p in players):
                    _am.unlockSecret(session, user.id, "homer")

        session.commit()
        return build_success_response({"message": "Roster updated", "rosterId": roster.id})
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        logger.error(f"Error setting fantasy roster: {e}")
        raise HTTPException(status_code=500, detail="Failed to update roster")
    finally:
        session.close()


@app.post("/api/fantasy/roster/lock")
def lock_fantasy_roster(user: _User = Depends(_getCurrentUser)):
    """Lock the user's fantasy roster for the current season."""
    from database.connection import get_session
    from database.models import (
        FantasyRoster, FantasyRosterPlayer, EquippedCard, UserCard, CardTemplate,
    )

    currentSeasonNum = _getCurrentSeasonNumber()
    if currentSeasonNum is None:
        raise HTTPException(status_code=400, detail="No active season")
    if floosball_app is None:
        raise HTTPException(status_code=503, detail="Application not initialized")

    session = get_session()
    try:
        roster = session.query(FantasyRoster).filter_by(
            user_id=user.id, season=currentSeasonNum
        ).first()

        if roster is None:
            raise HTTPException(status_code=404, detail="No roster found for this season")
        if roster.is_locked:
            raise HTTPException(status_code=409, detail="Roster is already locked")

        # Minimum 3 players required to lock. Empty slots are allowed —
        # they just don't contribute to weekly FP. The floor exists so a
        # user can't gut their roster to ride card-streak exploits like
        # Drought + Hedge + Home Alone unbounded.
        filledCount = sum(1 for rp in roster.players if rp.slot in _VALID_SLOTS or rp.slot == "FLEX")
        if filledCount < ROSTER_MIN_PLAYERS:
            raise HTTPException(
                status_code=400,
                detail=f"Roster needs at least {ROSTER_MIN_PLAYERS} players to lock (have {filledCount})",
            )

        # Snapshot each player's tracked FP at lock time (banked weeks + current week).
        # Uses the same data source as the snapshot so earned FP = seasonFP - points_at_lock
        # correctly excludes all FP gained before the roster was locked.
        fantasyTracker = floosball_app.fantasyTracker
        for rp in roster.players:
            rp.points_at_lock = fantasyTracker.getPlayerSeasonFP(
                rp.player_id, currentSeasonNum
            ) if fantasyTracker else 0

        roster.is_locked = True
        roster.locked_at = datetime.utcnow()

        # Retroactively grant All-Pro swap bonuses for any equipped AP cards.
        # The equip endpoint only grants when the roster is already locked, so
        # equipping before locking — the natural flow when a user fills slots
        # then equips cards, then locks — silently skipped the grant. Replay
        # it here so the swap_bonus_active flag and last_swap_grant_cycle
        # markers reflect reality.
        sm = floosball_app.seasonManager
        currentWeek = sm.currentSeason.currentWeek if sm.currentSeason else 0
        if currentWeek > 0:
            swapCycle = (currentWeek - 1) // 7 + 1
            equippedAP = (
                session.query(EquippedCard, UserCard, CardTemplate)
                .join(UserCard, EquippedCard.user_card_id == UserCard.id)
                .join(CardTemplate, UserCard.card_template_id == CardTemplate.id)
                .filter(
                    EquippedCard.user_id == user.id,
                    EquippedCard.season == currentSeasonNum,
                    EquippedCard.week == currentWeek,
                    CardTemplate.classification.isnot(None),
                    CardTemplate.classification.contains("all_pro"),
                )
                .all()
            )
            for eqCard, uc, _tmpl in equippedAP:
                if uc.last_swap_grant_cycle < swapCycle:
                    roster.swaps_available += 1
                    uc.last_swap_grant_cycle = swapCycle
                    eqCard.swap_bonus_active = True

        session.commit()
        return build_success_response({"message": "Roster locked", "lockedAt": roster.locked_at.isoformat() + 'Z'})
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        logger.error(f"Error locking fantasy roster: {e}")
        raise HTTPException(status_code=500, detail="Failed to lock roster")
    finally:
        session.close()


class FantasySwapRequest(BaseModel):
    slot: str
    newPlayerId: int


class FantasyRemoveRequest(BaseModel):
    slot: str


@app.post("/api/fantasy/roster/remove")
def remove_fantasy_roster_player(req: FantasyRemoveRequest, user: _User = Depends(_getCurrentUser)):
    """Empty a roster slot. Free (no swap consumed, no Floobits charged).

    Re-filling the empty slot later via /swap requires a paid swap — see
    the empty-slot branch in swap_fantasy_roster_player. This prevents a
    "remove then re-add for free" exploit.
    """
    from database.connection import get_session
    from database.models import FantasyRoster, FantasyRosterSwap, FantasyRosterPlayer, WeeklyPlayerFP
    from sqlalchemy import func

    currentSeasonNum = _getCurrentSeasonNumber()
    if currentSeasonNum is None:
        raise HTTPException(status_code=400, detail="No active season")
    if floosball_app is None:
        raise HTTPException(status_code=503, detail="Application not initialized")

    # Same gate as /swap: only available while the swap window is open
    # (roster locked + no games actively in progress).
    sm = floosball_app.seasonManager
    if sm.currentSeason and sm.currentSeason.activeGames:
        gamesInProgress = any(
            hasattr(g, 'status') and hasattr(g.status, 'name') and g.status.name == 'Active'
            for g in sm.currentSeason.activeGames
        )
        if gamesInProgress:
            raise HTTPException(status_code=409, detail="Cannot remove while games are active")

    session = get_session()
    try:
        roster = session.query(FantasyRoster).filter_by(
            user_id=user.id, season=currentSeasonNum
        ).first()
        if roster is None:
            raise HTTPException(status_code=404, detail="No roster found")
        if not roster.is_locked:
            raise HTTPException(status_code=400, detail="Roster is not locked — edit it directly instead")

        rosterPlayer = None
        for rp in roster.players:
            if rp.slot == req.slot:
                rosterPlayer = rp
                break
        if rosterPlayer is None:
            raise HTTPException(status_code=400, detail=f"No player in slot {req.slot}")

        # Enforce the roster minimum — can't drop below the floor.
        if len(roster.players) <= ROSTER_MIN_PLAYERS:
            raise HTTPException(
                status_code=409,
                detail=f"Roster minimum is {ROSTER_MIN_PLAYERS} players. Swap instead of removing.",
            )

        oldPlayerId = rosterPlayer.player_id
        currentWeek = sm.currentSeason.currentWeek if sm.currentSeason else 0

        # Preserve post-lock FP earned by the removed player so it stays
        # banked into the user's season + week totals (same accounting as
        # a swap — but with new_player_id=NULL marking it as a remove).
        totalSeasonFP = session.query(func.coalesce(func.sum(WeeklyPlayerFP.fantasy_points), 0.0)).filter_by(
            player_id=oldPlayerId, season=currentSeasonNum
        ).scalar()
        bankedFP = max(0.0, float(totalSeasonFP) - rosterPlayer.points_at_lock)
        oldPlayerWeekFPRow = session.query(WeeklyPlayerFP.fantasy_points).filter_by(
            player_id=oldPlayerId, season=currentSeasonNum, week=currentWeek
        ).scalar()
        bankedWeekFP = float(oldPlayerWeekFPRow or 0.0)

        session.add(FantasyRosterSwap(
            roster_id=roster.id,
            slot=req.slot,
            old_player_id=oldPlayerId,
            new_player_id=None,
            swap_week=currentWeek,
            banked_fp=round(bankedFP, 1),
            banked_week_fp=round(bankedWeekFP, 1),
        ))
        session.delete(rosterPlayer)
        session.commit()

        return build_success_response({
            "message": f"Removed player from {req.slot}",
            "slot": req.slot,
            "bankedFP": round(bankedFP, 1),
        })
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        logger.error(f"Error removing roster player: {e}")
        raise HTTPException(status_code=500, detail="Failed to remove player")
    finally:
        session.close()


@app.post("/api/fantasy/roster/swap")
def swap_fantasy_roster_player(req: FantasySwapRequest, user: _User = Depends(_getCurrentUser)):
    """Swap a single player in a locked roster (costs 1 Floobit)."""
    from database.connection import get_session
    from database.models import FantasyRoster, FantasyRosterSwap, WeeklyPlayerFP
    from database.repositories.card_repositories import CurrencyRepository
    from sqlalchemy import func

    currentSeasonNum = _getCurrentSeasonNumber()
    if currentSeasonNum is None:
        raise HTTPException(status_code=400, detail="No active season")
    if floosball_app is None:
        raise HTTPException(status_code=503, detail="Application not initialized")

    # Validate games not actively in progress (Scheduled games during countdown are OK)
    sm = floosball_app.seasonManager
    if sm.currentSeason and sm.currentSeason.activeGames:
        gamesInProgress = any(
            hasattr(g, 'status') and hasattr(g.status, 'name') and g.status.name == 'Active'
            for g in sm.currentSeason.activeGames
        )
        if gamesInProgress:
            raise HTTPException(status_code=409, detail="Cannot swap while games are active")

    # Build valid slots — include FLEX if user has champion card or temp_flex power-up
    validSlots = set(_VALID_SLOTS)
    hasFlexSlot = False
    if req.slot == "FLEX":
        from database.models import EquippedCard, UserCard, CardTemplate, ShopPurchase
        currentWeek = sm.currentSeason.currentWeek if sm.currentSeason else 0
        checkSession = get_session()
        try:
            championCount = (
                checkSession.query(EquippedCard.id)
                .join(UserCard, EquippedCard.user_card_id == UserCard.id)
                .join(CardTemplate, UserCard.card_template_id == CardTemplate.id)
                .filter(
                    EquippedCard.user_id == user.id,
                    EquippedCard.season == currentSeasonNum,
                    EquippedCard.week == currentWeek,
                    CardTemplate.classification.isnot(None),
                    CardTemplate.classification.contains("champion"),
                )
                .limit(1).count()
            )
            if championCount > 0:
                hasFlexSlot = True
            else:
                activeFlex = checkSession.query(ShopPurchase).filter(
                    ShopPurchase.user_id == user.id,
                    ShopPurchase.season == currentSeasonNum,
                    ShopPurchase.item_slug == "temp_flex",
                    ShopPurchase.expires_at_week >= currentWeek,
                ).first()
                if activeFlex:
                    hasFlexSlot = True
        finally:
            checkSession.close()
        if hasFlexSlot:
            validSlots.add("FLEX")

    # Validate slot
    if req.slot not in validSlots:
        detail = f"Invalid slot: {req.slot}"
        if req.slot == "FLEX":
            detail = "FLEX slot requires a Champion card or Flex Slot power-up"
        raise HTTPException(status_code=400, detail=detail)

    # Validate new player exists and position matches
    newPlayerObj = floosball_app.playerManager.getPlayerById(req.newPlayerId)
    if newPlayerObj is None:
        raise HTTPException(status_code=404, detail=f"Player {req.newPlayerId} not found")
    if req.slot == "FLEX":
        # FLEX accepts any position — no position check needed
        pass
    else:
        expectedPos = _SLOT_POSITION_MAP[req.slot]
        playerPos = newPlayerObj.position.value if hasattr(newPlayerObj.position, 'value') else newPlayerObj.position
        if playerPos != expectedPos:
            raise HTTPException(status_code=400, detail=f"Player {newPlayerObj.name} is not eligible for slot {req.slot}")

    session = get_session()
    try:
        roster = session.query(FantasyRoster).filter_by(
            user_id=user.id, season=currentSeasonNum
        ).first()
        if roster is None:
            raise HTTPException(status_code=404, detail="No roster found")
        if not roster.is_locked:
            raise HTTPException(status_code=400, detail="Roster is not locked — edit it directly instead")

        # Find the current player in this slot
        rosterPlayer = None
        for rp in roster.players:
            if rp.slot == req.slot:
                rosterPlayer = rp
                break

        # Validate new player not already on roster
        for rp in roster.players:
            if rp.player_id == req.newPlayerId:
                raise HTTPException(status_code=409, detail=f"{newPlayerObj.name} is already on your roster")

        currentWeek = sm.currentSeason.currentWeek if sm.currentSeason else 0

        # Empty slot. Two cases:
        #   1. Free first fill — slot has no swap history at all. Covers
        #      both the initial temp_flex fill AND a slot the user left
        #      empty when they saved their original roster (partial-lock
        #      flow). No swap consumed.
        #   2. Re-filling a slot that was emptied via /remove or swapped
        #      out earlier — paid swap. Both leave a FantasyRosterSwap row
        #      on the slot, so any swap-history row flags case 2.
        isFreshFirstFill = False
        if rosterPlayer is None:
            priorSlotHistory = session.query(func.count(FantasyRosterSwap.id)).filter_by(
                roster_id=roster.id, slot=req.slot,
            ).scalar() or 0
            if priorSlotHistory == 0:
                isFreshFirstFill = True

        if isFreshFirstFill:
            from database.models import FantasyRosterPlayer
            newPlayerSeasonFP = session.query(func.coalesce(func.sum(WeeklyPlayerFP.fantasy_points), 0.0)).filter_by(
                player_id=req.newPlayerId, season=currentSeasonNum
            ).scalar()
            session.add(FantasyRosterPlayer(
                roster_id=roster.id,
                player_id=req.newPlayerId,
                slot=req.slot,
                points_at_lock=float(newPlayerSeasonFP),
            ))
            session.commit()
            return build_success_response({"message": f"Player added to {req.slot}", "slot": req.slot})

        # Paid path — covers both regular swaps (slot was filled) and
        # re-fills of slots emptied via /remove.
        if rosterPlayer is not None:
            oldPlayerId = rosterPlayer.player_id
            totalSeasonFP = session.query(func.coalesce(func.sum(WeeklyPlayerFP.fantasy_points), 0.0)).filter_by(
                player_id=oldPlayerId, season=currentSeasonNum
            ).scalar()
            bankedFP = max(0.0, float(totalSeasonFP) - rosterPlayer.points_at_lock)
            # Snapshot the old player's swap-week FP at the moment of swap so
            # the leaderboard's weekly FP doesn't drop when a user swaps
            # post-games-end. Without this, the old player's FP for the
            # current week vanishes when they leave roster.players.
            oldPlayerWeekFPRow = session.query(WeeklyPlayerFP.fantasy_points).filter_by(
                player_id=oldPlayerId, season=currentSeasonNum, week=currentWeek
            ).scalar()
            bankedWeekFP = float(oldPlayerWeekFPRow or 0.0)
        else:
            # Re-filling an empty slot. Banked FP for the prior occupant was
            # already recorded when /remove fired — nothing to bank here.
            oldPlayerId = None
            bankedFP = 0.0
            bankedWeekFP = 0.0

        totalSwaps = roster.swaps_available + roster.purchased_swaps
        if totalSwaps < 1:
            raise HTTPException(status_code=409, detail="No swaps available")

        # Escalating swap cost — count only the actual swaps and paid fills
        # (rows with a non-null new_player_id). /remove rows don't escalate.
        from constants import ROSTER_SWAP_COST, ROSTER_SWAP_COST_INCREMENT
        priorSlotSwaps = session.query(func.count(FantasyRosterSwap.id)).filter(
            FantasyRosterSwap.roster_id == roster.id,
            FantasyRosterSwap.slot == req.slot,
            FantasyRosterSwap.new_player_id.isnot(None),
        ).scalar() or 0
        swapCost = ROSTER_SWAP_COST + ROSTER_SWAP_COST_INCREMENT * priorSlotSwaps

        currencyRepo = CurrencyRepository(session)
        result = currencyRepo.spendFunds(
            userId=user.id, amount=swapCost, transactionType="roster_swap",
            description=f"Roster swap: {req.slot} ({swapCost} Floobits)", season=currentSeasonNum,
        )
        if result is None:
            raise HTTPException(status_code=402, detail=f"Insufficient Floobits (need {swapCost})")

        # Record the swap (old_player_id=NULL means "fill empty slot")
        session.add(FantasyRosterSwap(
            roster_id=roster.id,
            slot=req.slot,
            old_player_id=oldPlayerId,
            new_player_id=req.newPlayerId,
            swap_week=currentWeek,
            banked_fp=round(bankedFP, 1),
            banked_week_fp=round(bankedWeekFP, 1),
        ))

        # Update the roster player — new player starts at 0 earned FP
        newPlayerSeasonFP = session.query(func.coalesce(func.sum(WeeklyPlayerFP.fantasy_points), 0.0)).filter_by(
            player_id=req.newPlayerId, season=currentSeasonNum
        ).scalar()
        if rosterPlayer is not None:
            rosterPlayer.player_id = req.newPlayerId
            rosterPlayer.points_at_lock = float(newPlayerSeasonFP)
        else:
            # Filling a previously-emptied slot — create a new row.
            from database.models import FantasyRosterPlayer
            session.add(FantasyRosterPlayer(
                roster_id=roster.id,
                player_id=req.newPlayerId,
                slot=req.slot,
                points_at_lock=float(newPlayerSeasonFP),
            ))

        # Consume purchased swaps first, then organic.
        # When consuming from swaps_available, mark one equipped All-Pro card's
        # grant as used (swap_bonus_active=False). Without this, the card's
        # grant looks "still active" — letting users equip an All-Pro card,
        # use the granted swap, unequip the card (which would otherwise refund
        # because swap_bonus_active was True), and re-equip later for another
        # grant. Marking the grant as used keeps last_swap_grant_cycle pinned
        # at the current cycle on the UserCard, preventing re-grant.
        if roster.purchased_swaps > 0:
            roster.purchased_swaps -= 1
        else:
            from database.models import EquippedCard
            cardGrantRow = session.query(EquippedCard).filter_by(
                user_id=user.id, season=currentSeasonNum, week=currentWeek,
                swap_bonus_active=True,
            ).first()
            if cardGrantRow:
                cardGrantRow.swap_bonus_active = False
            roster.swaps_available -= 1
        session.commit()

        return build_success_response({
            "message": f"Swapped {req.slot} successfully",
            "bankedFP": round(bankedFP, 1),
            "swapsAvailable": roster.swaps_available,
            "purchasedSwaps": roster.purchased_swaps,
        })
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        logger.error(f"Error performing roster swap: {e}")
        raise HTTPException(status_code=500, detail="Failed to perform swap")
    finally:
        session.close()


def _liveStatsToDbFormat(gameStatsDict: dict) -> dict:
    """Translate a live gameStatsDict to DB-style weekPlayerStats format."""
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
            "fgYards": kicking.get("fgYards", 0),
            "longest": kicking.get("longest", 0),
        },
    }


def _computeLiveWeekCardBonuses(session, rosters, rostersByUser) -> dict:
    """Compute live card bonuses for the current active week. Returns {userId: bonusFP}.

    Delegates to FantasyTracker for consistent computation.
    """
    if not floosball_app:
        return {}

    snapshot = floosball_app.fantasyTracker.getSnapshot()
    result = {}
    for entry in snapshot.get("entries", []):
        weekCardBonus = entry.get("weekCardBonus", 0)
        if weekCardBonus > 0:
            result[entry["userId"]] = weekCardBonus
    return result


def _computeLeaderboardData(seasonNum: int = None) -> dict:
    """Compute leaderboard data for a season. Delegates to FantasyTracker."""
    if not floosball_app:
        return {"leaderboard": [], "season": None}

    snapshot = floosball_app.fantasyTracker.getSnapshot(seasonNum)
    if not snapshot.get("entries"):
        return {"leaderboard": [], "season": snapshot.get("season")}

    # Convert snapshot format to legacy leaderboard format for backward compat
    leaderboard = []
    for entry in snapshot["entries"]:
        leaderboard.append({
            "rank": entry["rank"],
            "userId": entry["userId"],
            "username": entry["username"],
            "totalPoints": entry["seasonTotal"],
            "rawPoints": entry["seasonEarnedFP"],
            "cardBonusPoints": entry["seasonCardBonus"],
            "weekPlayerFP": entry["weekPlayerFP"],
            "weekCardBonus": entry["weekCardBonus"],
            "lockedAt": entry["lockedAt"],
            "players": entry["players"],
            "cardBreakdowns": entry.get("cardBreakdowns", []),
            "equationSummary": entry.get("equationSummary"),
        })

    return {"leaderboard": leaderboard, "season": snapshot["season"]}


@app.get("/api/fantasy/snapshot")
def get_fantasy_snapshot(response: Response, season: Optional[int] = Query(default=None),
                         user: Optional[_User] = Depends(_getOptionalUser)):
    """Get full fantasy snapshot — single source of truth for roster + leaderboard."""
    response.headers["Cache-Control"] = "public, max-age=10"
    if not floosball_app:
        return build_success_response(
            {"season": None, "week": 0, "gamesActive": False, "entries": []}
        )
    snapshot = floosball_app.fantasyTracker.getSnapshot(season)
    # Flag: once a season hits playoffs, fantasy is archived — the bot/UI can
    # use this to skip rendering weekly leaderboard blocks during playoff rounds.
    sm = floosball_app.seasonManager if floosball_app else None
    inPlayoffs = bool(sm and sm.currentSeason and getattr(sm.currentSeason, 'currentPlayoffRound', None))
    snapshot["fantasyActive"] = not inPlayoffs
    # If authenticated user has a modifier override, return their effective modifier
    if user and snapshot.get("modifier"):
        try:
            from database.connection import get_session as _gs
            from database.repositories.shop_repository import ModifierOverrideRepository
            _s = _gs()
            override = ModifierOverrideRepository(_s).getOverride(
                user.id, snapshot["season"], snapshot["week"]
            )
            if override:
                sm = floosball_app.seasonManager
                overrideName = override.override_modifier
                snapshot["modifier"] = {
                    "name": overrideName,
                    "displayName": sm.MODIFIER_DISPLAY.get(overrideName, overrideName.title()),
                    "description": sm.MODIFIER_DESCRIPTIONS.get(overrideName, ""),
                }
            _s.close()
        except Exception:
            pass
    return build_success_response(snapshot)


@app.get("/api/fantasy/weekly-modifier")
def get_weekly_modifier(response: Response):
    """Get the active weekly modifier for the current season/week."""
    response.headers["Cache-Control"] = "public, max-age=120"
    from database.connection import get_session
    from database.models import WeeklyModifier

    sm = floosball_app.seasonManager if floosball_app else None
    if not sm or not sm.currentSeason:
        return build_success_response({"modifier": None})

    currentSeason = sm.currentSeason.seasonNumber
    currentWeek = sm.currentSeason.currentWeek
    if not isinstance(currentWeek, int) or currentWeek < 1:
        return build_success_response({"modifier": None})

    session = get_session()
    try:
        row = session.query(WeeklyModifier).filter_by(
            season=currentSeason, week=currentWeek
        ).first()
        if not row:
            return build_success_response({"modifier": None})

        modName = row.modifier
        displayInfo = sm.MODIFIER_DISPLAY.get(modName, modName.title())
        description = sm.MODIFIER_DESCRIPTIONS.get(modName, "")
        return build_success_response({
            "modifier": modName,
            "displayName": displayInfo,
            "description": description,
            "season": currentSeason,
            "week": currentWeek,
        })
    finally:
        session.close()


@app.get("/api/fantasy/card-projection")
def get_card_projection(user: _User = Depends(_getCurrentUser),
                        include_candidates: bool = Query(default=False),
                        replace_slot: Optional[int] = Query(default=None)):
    """Projected card payouts for the upcoming week based on season-to-date
    averages + ELO forecasts.

    Response:
        equipped: projection per currently-equipped card (full-hand calc)
        totals:   roster FP + card bonus FP projections
        candidates: per-user-card solo projection, only included when
                    include_candidates=true (used by the card picker modal)
    """
    if floosball_app is None:
        raise HTTPException(503, "Application not initialized")

    from database.connection import get_session
    from database.models import UserCard
    from managers.cardProjection import (
        computeEquippedProjections, computeCandidateProjection,
    )

    sm = floosball_app.seasonManager
    pm = floosball_app.playerManager
    season = sm.currentSeason.seasonNumber if sm and sm.currentSeason else 0
    week = sm.currentSeason.currentWeek if sm and sm.currentSeason else 0
    if not season:
        return build_success_response({
            "equipped": {
                "cards": [], "totalBonusFP": 0.0, "totalFloobits": 0,
                "multFactors": [], "projectedRosterFP": 0.0,
                "projectedTotalFP": 0.0, "opponent": "", "winProbability": 0.5,
            },
            "candidates": [],
        })

    session = get_session()
    try:
        equipped = computeEquippedProjections(
            session, user.id, season, week, sm, pm,
        )
        candidates: list = []
        if include_candidates:
            userCards = (
                session.query(UserCard)
                .filter_by(user_id=user.id)
                .all()
            )
            for uc in userCards:
                proj = computeCandidateProjection(
                    uc, session, user.id, season, week, sm, pm,
                    replaceSlot=replace_slot,
                )
                if proj is not None:
                    candidates.append(proj)
        return build_success_response({
            "equipped": equipped,
            "candidates": candidates,
        })
    finally:
        session.close()


@app.post("/api/cards/template-projection")
def post_template_projection(payload: Dict[str, Any], user: _User = Depends(_getCurrentUser)):
    """Batch-project unowned CardTemplates against the requesting user's
    roster + season-to-date stats. Used by the pack reveal-then-select
    flow and the shop preview to surface expected weekly output before
    the user commits to a card.

    Request: {"templateIds": [int, int, ...]}
    Response.data.projections: list of payloads (same shape as
        computeCandidateProjection) keyed by templateId.
    """
    if floosball_app is None:
        raise HTTPException(503, "Application not initialized")
    templateIds = payload.get("templateIds") or []
    if not isinstance(templateIds, list) or not templateIds:
        return build_success_response({"projections": []})
    # Cap the batch to keep the calc bounded
    templateIds = [int(t) for t in templateIds[:20] if isinstance(t, (int, float))]

    from database.connection import get_session
    from database.models import CardTemplate
    from managers.cardProjection import computeTemplateProjection

    sm = floosball_app.seasonManager
    pm = floosball_app.playerManager
    season = sm.currentSeason.seasonNumber if sm and sm.currentSeason else 0
    week = sm.currentSeason.currentWeek if sm and sm.currentSeason else 0
    if not season:
        return build_success_response({"projections": []})

    session = get_session()
    try:
        templates = (
            session.query(CardTemplate)
            .filter(CardTemplate.id.in_(templateIds))
            .all()
        )
        projections = []
        for tpl in templates:
            proj = computeTemplateProjection(
                tpl, session, user.id, season, week, sm, pm,
            )
            if proj is None:
                continue
            proj["templateId"] = tpl.id
            projections.append(proj)
        return build_success_response({"projections": projections})
    finally:
        session.close()


@app.get("/api/fantasy/leaderboard")
def get_fantasy_leaderboard(response: Response, season: Optional[int] = Query(default=None)):
    """Get fantasy leaderboard for a season (defaults to current)."""
    response.headers["Cache-Control"] = "public, max-age=10"
    return build_success_response(_computeLeaderboardData(season))


@app.get("/api/fantasy/leaderboard/weekly")
def get_fantasy_weekly_leaderboard(response: Response, season: Optional[int] = Query(default=None)):
    """Get fantasy leaderboard broken down by week."""
    response.headers["Cache-Control"] = "public, max-age=10"
    from database.connection import get_session
    from database.models import FantasyRoster, FantasyRosterPlayer, FantasyRosterSwap, User, Game, GamePlayerStats, WeeklyCardBonus

    seasonNum = season if season is not None else _getCurrentSeasonNumber()
    if seasonNum is None:
        return build_success_response({"weeks": [], "season": None})

    sm = floosball_app.seasonManager if floosball_app else None
    currentWeek = sm.currentSeason.currentWeek if sm and sm.currentSeason else 0
    isCurrentSeason = seasonNum == (sm.currentSeason.seasonNumber if sm and sm.currentSeason else -1)
    gamesActive = isCurrentSeason and (_areGamesStarted() or _areGamesCompleted())

    session = get_session()
    try:
        rosters = session.query(FantasyRoster).filter_by(
            season=seasonNum, is_locked=True
        ).all()

        if not rosters:
            return build_success_response({"weeks": [], "season": seasonNum})

        # Collect all roster player IDs and build lookup maps
        rostersByUser = {}  # userId -> { roster, playerSlots: {playerId -> slot} }
        allPlayerIds = set()
        for roster in rosters:
            rosterUser = session.get(User, roster.user_id)
            playerSlots = {}
            for rp in roster.players:
                playerSlots[rp.player_id] = rp.slot
                allPlayerIds.add(rp.player_id)
            rostersByUser[roster.user_id] = {
                "roster": roster,
                "username": rosterUser.username or rosterUser.email if rosterUser else "Unknown",
                "playerSlots": playerSlots,
            }

        # Query all game stats for these players in this season, joined with Game for week info
        gameStats = (
            session.query(GamePlayerStats, Game.week, Game.game_date)
            .join(Game, GamePlayerStats.game_id == Game.id)
            .filter(
                Game.season == seasonNum,
                Game.is_playoff == False,
                GamePlayerStats.player_id.in_(allPlayerIds),
            )
            .all()
        )

        # Build raw per-player per-week FP totals (no lock filtering yet)
        # rawWeekFP[playerId][week] = total FP from games that week
        rawWeekFP = {}  # playerId -> {week -> fp}
        allWeeks = set()
        for gps, week, _ in gameStats:
            allWeeks.add(week)
            if gps.player_id not in rawWeekFP:
                rawWeekFP[gps.player_id] = {}
            rawWeekFP[gps.player_id][week] = rawWeekFP[gps.player_id].get(week, 0) + (gps.fantasy_points or 0)

        # Overlay current week with live in-memory data when games are active
        # DB values may be 0 during active games since stats haven't been saved yet
        # Only overlay when liveFP > 0 — after a game ends, gameStatsDict.fantasyPoints
        # is zeroed by _accumulatePostgameStats but the DB already has the correct value
        if gamesActive and isCurrentSeason and floosball_app:
            allWeeks.add(currentWeek)
            for playerId in allPlayerIds:
                playerObj = floosball_app.playerManager.getPlayerById(playerId)
                if playerObj:
                    liveFP = playerObj.gameStatsDict.get('fantasyPoints', 0)
                    if liveFP > 0:
                        if playerId not in rawWeekFP:
                            rawWeekFP[playerId] = {}
                        rawWeekFP[playerId][currentWeek] = liveFP

        sortedWeeks = sorted(allWeeks)

        # ─── Card bonus per week ───────────────────────────────────────
        # storedBonuses[userId][week] = bonus_fp  (from completed weeks)
        # storedBreakdowns[userId][week] = parsed breakdowns_json list
        storedBonuses = {}
        storedBreakdowns: Dict[int, Dict[int, list]] = {}
        rosterIds = [info["roster"].id for info in rostersByUser.values()]
        if rosterIds:
            bonusRows = session.query(WeeklyCardBonus).filter(
                WeeklyCardBonus.roster_id.in_(rosterIds),
                WeeklyCardBonus.season == seasonNum,
            ).all()
            import json as _json
            for row in bonusRows:
                storedBonuses.setdefault(row.user_id, {})[row.week] = row.bonus_fp
                if row.breakdowns_json:
                    try:
                        storedBreakdowns.setdefault(row.user_id, {})[row.week] = _json.loads(row.breakdowns_json)
                    except (ValueError, TypeError):
                        pass

        # Compute live card bonus for the current week when games are active
        liveCardBonusByUser = {}
        if gamesActive and isCurrentSeason and floosball_app:
            liveCardBonusByUser = _computeLiveWeekCardBonuses(session, rosters, rostersByUser)

        # For each user, compute earned FP per player per week using points_at_lock
        # earned = max(0, cumulativeAfterWeek - max(cumulativeBeforeWeek, pointsAtLock))
        weekData = {}  # week -> userId -> { weekPoints, cardBonusPoints, playerPoints: { playerId -> fp } }
        for userId, info in rostersByUser.items():
            rosterPlayers = {rp.player_id: rp.points_at_lock for rp in info["roster"].players}

            for playerId, pointsAtLock in rosterPlayers.items():
                playerWeekFP = rawWeekFP.get(playerId, {})
                cumulativeBefore = 0.0
                for week in sortedWeeks:
                    weekFP = playerWeekFP.get(week, 0)
                    cumulativeAfter = cumulativeBefore + weekFP
                    earned = max(0, cumulativeAfter - max(cumulativeBefore, pointsAtLock))
                    cumulativeBefore = cumulativeAfter

                    if earned <= 0:
                        continue

                    if week not in weekData:
                        weekData[week] = {}
                    if userId not in weekData[week]:
                        weekData[week][userId] = {"weekPoints": 0.0, "cardBonusPoints": 0.0, "playerPoints": {}}

                    weekData[week][userId]["weekPoints"] += earned
                    weekData[week][userId]["playerPoints"][playerId] = (
                        weekData[week][userId]["playerPoints"].get(playerId, 0) + earned
                    )

        # Add swapped-out players' contribution per swap_week. Without this
        # the weekly view drops the old player's FP the moment a user swaps
        # them out, even though the week's games already played out with
        # the old player on the roster. banked_week_fp is the snapshot
        # captured at swap time.
        if rosterIds:
            swapRows = session.query(FantasyRosterSwap).filter(
                FantasyRosterSwap.roster_id.in_(rosterIds),
            ).all()
            rosterIdToUserId = {info["roster"].id: uId for uId, info in rostersByUser.items()}
            for swap in swapRows:
                userId = rosterIdToUserId.get(swap.roster_id)
                if userId is None:
                    continue
                bankedWeek = float(getattr(swap, 'banked_week_fp', 0) or 0)
                if bankedWeek <= 0:
                    continue
                week = swap.swap_week
                if week not in weekData:
                    weekData[week] = {}
                if userId not in weekData[week]:
                    weekData[week][userId] = {"weekPoints": 0.0, "cardBonusPoints": 0.0, "playerPoints": {}}
                weekData[week][userId]["weekPoints"] += bankedWeek

        # Inject card bonus into weekData for each user/week. Stored bonuses
        # (from WeeklyCardBonus) win over the live recomputation — at week-end
        # both can exist simultaneously for the same week (stored was just
        # written by _processWeekCardEffects, and gamesActive is still True
        # because activeGames hasn't been cleared yet). Without this guard
        # the current-week bonus gets counted twice, inflating weekPoints by
        # roughly the card bonus amount — visible to anyone hitting the
        # endpoint right when week_end fires (e.g. the Discord bot).
        for userId in rostersByUser:
            userStoredBonuses = storedBonuses.get(userId, {})
            for week, bonusFP in userStoredBonuses.items():
                if week not in weekData:
                    weekData[week] = {}
                if userId not in weekData[week]:
                    weekData[week][userId] = {"weekPoints": 0.0, "cardBonusPoints": 0.0, "playerPoints": {}}
                weekData[week][userId]["cardBonusPoints"] = bonusFP
                weekData[week][userId]["weekPoints"] += bonusFP

            # Live card bonus for current active week — only used when there's
            # no stored bonus yet for this week.
            if userId in liveCardBonusByUser:
                week = currentWeek
                hasStoredThisWeek = week in userStoredBonuses
                if hasStoredThisWeek:
                    continue
                if week not in weekData:
                    weekData[week] = {}
                if userId not in weekData[week]:
                    weekData[week][userId] = {"weekPoints": 0.0, "cardBonusPoints": 0.0, "playerPoints": {}}
                weekData[week][userId]["cardBonusPoints"] = liveCardBonusByUser[userId]
                weekData[week][userId]["weekPoints"] += liveCardBonusByUser[userId]

        # Build response
        weeks = []
        for week in sorted(weekData.keys()):
            entries = []
            for userId, data in weekData[week].items():
                info = rostersByUser[userId]
                players = []
                for playerId, fp in data["playerPoints"].items():
                    playerObj = floosball_app.playerManager.getPlayerById(playerId) if floosball_app else None
                    players.append({
                        "slot": info["playerSlots"].get(playerId, "?"),
                        "playerName": playerObj.name if playerObj else "Unknown",
                        "teamAbbr": getattr(playerObj.team, 'abbr', '') if playerObj and hasattr(playerObj.team, 'name') else "",
                        "teamId": getattr(playerObj.team, 'id', None) if playerObj and hasattr(playerObj.team, 'name') else None,
                        "weekPoints": round(fp, 1),
                    })
                players.sort(key=lambda p: p["weekPoints"], reverse=True)
                rosterUser = session.get(User, userId)
                entries.append({
                    "userId": userId,
                    "username": info["username"],
                    "favoriteTeamId": rosterUser.favorite_team_id if rosterUser else None,
                    "weekPoints": round(data["weekPoints"], 1),
                    "cardBonusPoints": round(data.get("cardBonusPoints", 0), 1),
                    "players": players,
                    "cardBreakdowns": storedBreakdowns.get(userId, {}).get(week, []),
                })
            entries.sort(key=lambda e: e["weekPoints"], reverse=True)
            for i, entry in enumerate(entries, 1):
                entry["rank"] = i
            weeks.append({"week": week, "entries": entries})

        return build_success_response({"weeks": weeks, "season": seasonNum})
    finally:
        session.close()


# ============================================================================
# CURRENCY (FLOOBITS)
# ============================================================================


@app.get("/api/currency/balance")
def getCurrencyBalance(user: _User = Depends(_getCurrentUser)):
    """Get user's Floobit balance."""
    from database.models import UserCurrency
    from database.connection import get_session
    session = get_session()
    try:
        currency = session.query(UserCurrency).filter_by(user_id=user.id).first()
        if not currency:
            return build_success_response({
                "balance": 0,
                "lifetimeEarned": 0,
                "lifetimeSpent": 0,
            })
        return build_success_response({
            "balance": currency.balance,
            "lifetimeEarned": currency.lifetime_earned,
            "lifetimeSpent": currency.lifetime_spent,
        })
    finally:
        session.close()


@app.get("/api/currency/history")
def getCurrencyHistory(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: _User = Depends(_getCurrentUser),
):
    """Get user's Floobit transaction history."""
    from database.models import CurrencyTransaction
    from database.connection import get_session
    session = get_session()
    try:
        transactions = (
            session.query(CurrencyTransaction)
            .filter_by(user_id=user.id)
            .order_by(CurrencyTransaction.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        return build_success_response({
            "transactions": [
                {
                    "id": tx.id,
                    "amount": tx.amount,
                    "balanceAfter": tx.balance_after,
                    "type": tx.transaction_type,
                    "description": tx.description,
                    "season": tx.season,
                    "week": tx.week,
                    "createdAt": tx.created_at.isoformat() + 'Z' if tx.created_at else None,
                }
                for tx in transactions
            ]
        })
    finally:
        session.close()


# ============================================================================
# CARDS
# ============================================================================


@app.get("/api/cards/collection")
def getCardCollection(
    edition: Optional[str] = Query(default=None),
    position: Optional[int] = Query(default=None),
    activeOnly: bool = Query(default=False),
    user: _User = Depends(_getCurrentUser),
):
    """Get user's card collection with optional filters."""
    from database.connection import get_session
    from database.repositories.card_repositories import UserCardRepository
    from managers.cardManager import CardManager

    sm = floosball_app.seasonManager if floosball_app else None
    currentSeason = sm.currentSeason.seasonNumber if sm and sm.currentSeason else 0
    currentWeek = sm.currentSeason.currentWeek if sm and sm.currentSeason else 0

    cardManager = CardManager(floosball_app.serviceContainer if floosball_app else None)

    session = get_session()
    try:
        from database.repositories.card_repositories import EquippedCardRepository
        cardRepo = UserCardRepository(session)
        equippedRepo = EquippedCardRepository(session)
        cards = cardRepo.getByUser(user.id)

        # Get equipped card IDs for current week only
        equippedCardIds = equippedRepo.getEquippedCardIds(user.id, currentSeason, currentWeek)

        result = []
        for card in cards:
            tpl = card.card_template
            if edition and tpl.edition != edition:
                continue
            if position is not None and tpl.position != position:
                continue
            if activeOnly and tpl.season_created != currentSeason:
                continue
            data = cardManager.serializeCard(card, currentSeason)
            data["isEquipped"] = card.id in equippedCardIds
            result.append(data)

        return build_success_response({"cards": result, "currentSeason": currentSeason})
    finally:
        session.close()


class SellCardsRequest(BaseModel):
    userCardIds: List[int]


@app.post("/api/cards/sell")
def sellCards(req: SellCardsRequest, user: _User = Depends(_getCurrentUser)):
    """Sell one or more cards for Floobits."""
    from database.connection import get_session
    from managers.cardManager import CardManager

    if not req.userCardIds:
        raise HTTPException(status_code=400, detail="No card IDs provided")

    sm = floosball_app.seasonManager if floosball_app else None
    currentSeason = sm.currentSeason.seasonNumber if sm and sm.currentSeason else 0
    currentWeek = sm.currentSeason.currentWeek if sm and sm.currentSeason else 0

    cardManager = CardManager(floosball_app.serviceContainer if floosball_app else None)

    session = get_session()
    try:
        result = cardManager.sellCards(session, user.id, req.userCardIds, currentSeason, currentWeek)
        session.commit()
        return build_success_response(result)
    except ValueError as e:
        session.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        session.rollback()
        logger.error(f"Card sell failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to sell cards")
    finally:
        session.close()


# ============================================================================
# THE COMBINE (CARD UPGRADES)
# ============================================================================


class BlendRequest(BaseModel):
    offeringCardIds: List[int]


@app.post("/api/cards/blend")
def blendCards(req: BlendRequest, user: _User = Depends(_getCurrentUser)):
    """The Combine: Sacrifice multiple cards to create one new random card."""
    from database.connection import get_session
    from managers.cardManager import CardManager

    sm = floosball_app.seasonManager if floosball_app else None
    currentSeason = sm.currentSeason.seasonNumber if sm and sm.currentSeason else 0
    currentWeek = sm.currentSeason.currentWeek if sm and sm.currentSeason else 0
    cardManager = CardManager(floosball_app.serviceContainer if floosball_app else None)

    session = get_session()
    try:
        result = cardManager.blendCards(session, user.id, req.offeringCardIds, currentSeason, currentWeek)
        # Curator reflects unique templates in the collection — a blend replaces
        # several sacrificed templates with one new one, so the count may change.
        from managers import achievementManager as _am
        _am.syncCuratorProgress(session, user.id, currentSeason)
        session.commit()
        return build_success_response(result)
    except ValueError as e:
        session.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        session.rollback()
        isDbLocked = "database is locked" in str(e).lower()
        if isDbLocked:
            logger.warning(f"Card blend blocked by DB lock for user {user.id}")
            raise HTTPException(status_code=409, detail="Games are in progress — try again in a moment")
        logger.error(f"Card blend failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to blend cards")
    finally:
        session.close()


@app.post("/api/cards/blend/preview")
def previewBlend(req: BlendRequest, user: _User = Depends(_getCurrentUser)):
    """Preview The Combine result (shows resulting edition based on total value)."""
    from database.connection import get_session
    from managers.cardManager import CardManager

    sm = floosball_app.seasonManager if floosball_app else None
    currentSeason = sm.currentSeason.seasonNumber if sm and sm.currentSeason else 0
    currentWeek = sm.currentSeason.currentWeek if sm and sm.currentSeason else 0
    cardManager = CardManager(floosball_app.serviceContainer if floosball_app else None)

    session = get_session()
    try:
        result = cardManager.previewBlend(session, user.id, req.offeringCardIds, currentSeason, currentWeek)
        return build_success_response(result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        session.close()


# ============================================================================
# EQUIPPED CARDS
# ============================================================================


@app.get("/api/cards/equipped")
def getEquippedCards(user: _User = Depends(_getCurrentUser)):
    """Get the user's equipped cards for the current week."""
    from database.connection import get_session
    from database.models import FantasyRoster, EquippedCard, UserCard, CardTemplate
    from database.repositories.card_repositories import EquippedCardRepository
    from managers.cardManager import CardManager

    sm = floosball_app.seasonManager if floosball_app else None
    currentSeason = sm.currentSeason.seasonNumber if sm and sm.currentSeason else 0
    currentWeek = sm.currentSeason.currentWeek if sm and sm.currentSeason else 0

    cardManager = CardManager(floosball_app.serviceContainer if floosball_app else None)
    session = get_session()
    try:
        equippedRepo = EquippedCardRepository(session)
        equipped = equippedRepo.getByUserWeek(user.id, currentSeason, currentWeek)

        # Has the user explicitly set (possibly empty) equipped cards for this week?
        # If so, skip the auto-carry-forward so unequipping everything actually sticks.
        _rosterForMarker = session.query(FantasyRoster).filter_by(
            user_id=user.id, season=currentSeason,
        ).first()
        _explicitlySetThisWeek = bool(
            _rosterForMarker and _rosterForMarker.last_equipped_set_week == currentWeek
        )

        # Auto-carry forward: if no cards equipped this week, find the most recent week that has them
        if not equipped and currentWeek > 1 and not _explicitlySetThisWeek:
            # If games are active, lockWeek() already ran — auto-carried cards must also be locked
            gamesActive = _areGamesStarted()
            prevEquipped = []
            for lookback in range(currentWeek - 1, 0, -1):
                prevEquipped = equippedRepo.getByUserWeek(user.id, currentSeason, lookback)
                if prevEquipped:
                    break
            # Check if user qualifies for slot 6 this week (MVP or active powerup)
            hasExtraSlotForCarry = False
            if any(prev.slot_number == 6 for prev in prevEquipped):
                from database.repositories.shop_repository import ShopPurchaseRepository
                # Check for MVP card in the carry-forward set
                for prev in prevEquipped:
                    uc = session.get(UserCard, prev.user_card_id)
                    if uc:
                        tmpl = session.get(CardTemplate, uc.card_template_id)
                        if tmpl and tmpl.classification and "mvp" in tmpl.classification:
                            hasExtraSlotForCarry = True
                            break
                if not hasExtraSlotForCarry:
                    shopRepo = ShopPurchaseRepository(session)
                    activeSlot = shopRepo.getActiveTempCardSlot(user.id, currentSeason, currentWeek)
                    hasExtraSlotForCarry = activeSlot is not None

            for prev in prevEquipped:
                # Skip slot 6 if user no longer qualifies for extra slot
                if prev.slot_number == 6 and not hasExtraSlotForCarry:
                    continue
                # Verify card still exists and is active season
                userCard = session.get(UserCard, prev.user_card_id)
                if not userCard:
                    continue
                template = session.get(CardTemplate, userCard.card_template_id)
                if not template or template.season_created != currentSeason:
                    continue
                # Carry forward existing streak count — actual increment happens at week end.
                # Preserve a 0 (just-broken) — `or 1` would clobber the restart-penalty signal.
                prevStreak = getattr(prev, 'streak_count', 1)
                if prevStreak is None:
                    prevStreak = 1
                # Carry forward the All-Pro swap-bonus flag too. Without this,
                # a card that granted a swap last week looks like a fresh equip
                # this week, and unequipping it skips the refund — letting users
                # accumulate swaps by equip/unequip cycles.
                prevSwapBonus = bool(getattr(prev, 'swap_bonus_active', False))
                # Carry forward streak peak-decay state. Without this, the
                # new week's EquippedCard row has peak_output=NULL, and a
                # cold-week compute falls back to base instead of holding
                # the prior peak / decaying from it.
                prevPeakOutput = getattr(prev, 'peak_output', None)
                prevWeeksSinceBreak = getattr(prev, 'weeks_since_break', 0) or 0
                equippedRepo.save(EquippedCard(
                    user_id=user.id,
                    season=currentSeason,
                    week=currentWeek,
                    slot_number=prev.slot_number,
                    user_card_id=prev.user_card_id,
                    locked=gamesActive,
                    streak_count=prevStreak,
                    swap_bonus_active=prevSwapBonus,
                    peak_output=prevPeakOutput,
                    weeks_since_break=prevWeeksSinceBreak,
                ))
            session.commit()
            equipped = equippedRepo.getByUserWeek(user.id, currentSeason, currentWeek)

        # Get roster player IDs for match detection
        roster = session.query(FantasyRoster).filter_by(
            user_id=user.id, season=currentSeason
        ).first()
        rosterPlayerIds = set()
        if roster:
            rosterPlayerIds = {rp.player_id for rp in roster.players}

        result = []
        for eq in equipped:
            cardData = cardManager.serializeCard(eq.user_card, currentSeason)
            template = eq.user_card.card_template
            # All-Pro cards carry a swap-grant state per equipped instance:
            # True = grant unused (refundable on unequip), False = grant used.
            # Non-All-Pro cards return None (UI shows the badge normally).
            isAllPro = bool(template.classification and "all_pro" in template.classification)
            swapBonusActive = bool(getattr(eq, 'swap_bonus_active', False)) if isAllPro else None
            result.append({
                "slotNumber": eq.slot_number,
                "card": cardData,
                "playerId": template.player_id,
                "isMatch": template.player_id in rosterPlayerIds,
                "locked": eq.locked,
                "streakCount": getattr(eq, 'streak_count', 1) or 1,
                "cardTeamId": template.team_id,
                "templatePosition": template.position,
                "swapBonusActive": swapBonusActive,
            })

        # Check if user qualifies for 6th slot: MVP card equipped OR active temp_card_slot power-up
        from database.repositories.shop_repository import ShopPurchaseRepository
        mvpEquipped = (
            session.query(EquippedCard.id)
            .join(UserCard, EquippedCard.user_card_id == UserCard.id)
            .join(CardTemplate, UserCard.card_template_id == CardTemplate.id)
            .filter(
                EquippedCard.user_id == user.id,
                EquippedCard.season == currentSeason,
                EquippedCard.week == currentWeek,
                CardTemplate.classification.isnot(None),
                CardTemplate.classification.contains("mvp"),
            )
            .first()
        ) is not None
        extraSlotSource = None  # "mvp" | "temp_card_slot"
        extraSlotInfo = None
        if mvpEquipped:
            hasExtraSlot = True
            extraSlotSource = "mvp"
        else:
            shopRepo = ShopPurchaseRepository(session)
            activeSlot = shopRepo.getActiveTempCardSlot(user.id, currentSeason, currentWeek)
            hasExtraSlot = activeSlot is not None
            if activeSlot is not None:
                extraSlotSource = "temp_card_slot"
                deferred = activeSlot.week > currentWeek
                weeksRemaining = activeSlot.expires_at_week - currentWeek + (0 if deferred else 1)
                extraSlotInfo = {
                    "slug": "temp_card_slot",
                    "displayName": "Accession",
                    "expiresAtWeek": activeSlot.expires_at_week,
                    "weeksRemaining": max(0, weeksRemaining),
                    "expiring": weeksRemaining == 1,
                    "pending": deferred,
                }

        return build_success_response({
            "equippedCards": result,
            "season": currentSeason,
            "week": currentWeek,
            "gamesActive": _areGamesStarted(),
            "gamesScheduled": _areGamesScheduled(),
            "hasExtraSlot": hasExtraSlot,
            "extraSlotSource": extraSlotSource,
            "extraSlotPowerup": extraSlotInfo,
        })
    finally:
        session.close()


@app.get("/api/cards/equipped/public/{user_id}")
def getEquippedCardsPublic(user_id: int, season: int, week: int):
    """Public read of a user's equipped cards for a given (season, week).

    Used by the fantasy leaderboard expand to show each user's equipped
    hand alongside their roster. No auth — leaderboards are public.
    """
    from database.connection import get_session
    from database.models import EquippedCard, UserCard, CardTemplate, FantasyRoster
    from database.repositories.card_repositories import EquippedCardRepository
    from managers.cardManager import CardManager

    cardManager = CardManager(floosball_app.serviceContainer if floosball_app else None)
    session = get_session()
    try:
        equippedRepo = EquippedCardRepository(session)
        equipped = equippedRepo.getByUserWeek(user_id, season, week)

        roster = session.query(FantasyRoster).filter_by(user_id=user_id, season=season).first()
        rosterPlayerIds = set()
        if roster:
            for rp in roster.players:
                rosterPlayerIds.add(rp.player_id)

        result = []
        for eq in equipped:
            cardData = cardManager.serializeCard(eq.user_card, season)
            template = eq.user_card.card_template
            result.append({
                "slotNumber": eq.slot_number,
                "card": cardData,
                "playerId": template.player_id,
                "isMatch": template.player_id in rosterPlayerIds,
                "streakCount": getattr(eq, 'streak_count', 1) or 1,
                "cardTeamId": template.team_id,
                "templatePosition": template.position,
            })
        return build_success_response({
            "equippedCards": result,
            "userId": user_id,
            "season": season,
            "week": week,
        })
    finally:
        session.close()


class EquipCardSlot(BaseModel):
    slotNumber: int
    userCardId: int

class EquipCardsRequest(BaseModel):
    cards: List[EquipCardSlot]


@app.put("/api/cards/equipped")
def setEquippedCards(
    req: EquipCardsRequest,
    user: _User = Depends(_getCurrentUser),
):
    """Set the user's equipped cards for the current week."""
    from database.connection import get_session
    from database.models import FantasyRoster, EquippedCard, UserCard, CardTemplate
    from database.repositories.card_repositories import EquippedCardRepository

    sm = floosball_app.seasonManager if floosball_app else None
    currentSeason = sm.currentSeason.seasonNumber if sm and sm.currentSeason else 0
    currentWeek = sm.currentSeason.currentWeek if sm and sm.currentSeason else 0

    # Pre-validate slot range loosely (detailed check after MVP classification lookup)
    for c in req.cards:
        if c.slotNumber not in (1, 2, 3, 4, 5, 6):
            raise HTTPException(status_code=400, detail=f"Invalid slot number: {c.slotNumber}")

    # Check for duplicate slots
    slots = [c.slotNumber for c in req.cards]
    if len(slots) != len(set(slots)):
        raise HTTPException(status_code=400, detail="Duplicate slot numbers")

    # Check for duplicate card IDs
    cardIds = [c.userCardId for c in req.cards]
    if len(cardIds) != len(set(cardIds)):
        raise HTTPException(status_code=400, detail="Cannot equip the same card in multiple slots")

    session = get_session()
    try:
        # Look up locked roster (needed for All-Pro swap logic, but not required to equip)
        roster = session.query(FantasyRoster).filter_by(
            user_id=user.id, season=currentSeason, is_locked=True
        ).first()

        equippedRepo = EquippedCardRepository(session)

        # Check lock state: once locked, no changes allowed
        existing = equippedRepo.getByUserWeek(user.id, currentSeason, currentWeek)
        if any(e.locked for e in existing):
            raise HTTPException(status_code=409, detail="Cards are locked for this week")

        # Validate each card belongs to user and is active; collect classifications
        hasMvp = False
        cardTemplates = {}  # userCardId → template
        cardUserCards = {}  # userCardId → userCard
        for c in req.cards:
            userCard = session.query(UserCard).filter_by(id=c.userCardId, user_id=user.id).first()
            if not userCard:
                raise HTTPException(status_code=400, detail=f"Card {c.userCardId} not found")
            template = session.query(CardTemplate).filter_by(id=userCard.card_template_id).first()
            if not template or template.season_created != currentSeason:
                raise HTTPException(status_code=400, detail=f"Card {c.userCardId} is not active this season")
            cardTemplates[c.userCardId] = template
            cardUserCards[c.userCardId] = userCard
            if template.classification and "mvp" in template.classification:
                hasMvp = True

        # No-duplicate-effects rule: a user can equip at most one card with
        # each effectName. Two of the same effect stacked too hard under
        # bonus-additive math (two Droughts both growing their streak, two
        # Hedges adding 500 FP floor, etc.). A future "stack" powerup /
        # card may relax this — for now, reject at equip time.
        effectCounts: Dict[str, str] = {}
        for c in req.cards:
            cfg = cardTemplates[c.userCardId].effect_config or {}
            effectName = cfg.get("effectName") or ""
            if not effectName:
                continue
            if effectName in effectCounts:
                displayName = cfg.get("displayName") or effectName
                raise HTTPException(
                    status_code=400,
                    detail=f"Can't equip two of the same effect ({displayName}). Pick a different card.",
                )
            effectCounts[effectName] = effectName

        # Enforce slot limits: 5 base, 6 if MVP card equipped OR temp_card_slot active
        hasExtraSlot = hasMvp
        if not hasExtraSlot:
            from database.repositories.shop_repository import ShopPurchaseRepository
            shopRepo = ShopPurchaseRepository(session)
            activeSlot = shopRepo.getActiveTempCardSlot(user.id, currentSeason, currentWeek)
            hasExtraSlot = activeSlot is not None
        maxSlots = 6 if hasExtraSlot else 5
        for c in req.cards:
            if c.slotNumber > maxSlots:
                raise HTTPException(
                    status_code=400,
                    detail=f"Slot 6 requires an MVP card or Accession power-up"
                    if not hasExtraSlot else f"Invalid slot number: {c.slotNumber}"
                )

        # Track previously equipped cards before clearing
        previousEquipped = equippedRepo.getByUserWeek(user.id, currentSeason, currentWeek)

        # Streaks need to inherit from the LAST WEEK the card was equipped,
        # not just the current week's prior row. Without this, every PUT to
        # the equipped set on a new week resets streak_count to default 1,
        # because previousEquipped (current week) is empty on a first-equip
        # of the week. Build a lookup by user_card_id from the most recent
        # week the card appeared, falling back to current-week prior row,
        # then default 1.
        priorWeekEquipped = []
        try:
            from database.models import EquippedCard as _EC
            priorRows = (
                session.query(_EC)
                .filter(
                    _EC.user_id == user.id,
                    _EC.season == currentSeason,
                    _EC.week < currentWeek,
                )
                .order_by(_EC.week.desc())
                .all()
            )
            # First (most recent) row per user_card_id wins.
            seen = set()
            for r in priorRows:
                if r.user_card_id in seen:
                    continue
                seen.add(r.user_card_id)
                priorWeekEquipped.append(r)
        except Exception:
            pass

        # Merge: current-week rows take precedence (already-active streaks
        # on a re-PUT this same week), then fall back to prior-week.
        def _buildLookup(field, default):
            out: dict = {}
            for prev in priorWeekEquipped:
                v = getattr(prev, field, default)
                out[prev.user_card_id] = v if v is not None else default
            for prev in previousEquipped:
                v = getattr(prev, field, default)
                out[prev.user_card_id] = v if v is not None else default
            return out

        prevStreakByCardId = _buildLookup('streak_count', 1)
        prevPeakByCardId = {}
        for prev in priorWeekEquipped + list(previousEquipped):
            v = getattr(prev, 'peak_output', None)
            if v is not None:
                prevPeakByCardId[prev.user_card_id] = v
        prevWeeksSinceByCardId = _buildLookup('weeks_since_break', 0)

        # Clear existing and set new. Mark the roster so the GET auto-carry-forward
        # doesn't un-do an intentional empty equip set.
        if roster:
            roster.last_equipped_set_week = currentWeek
        equippedRepo.deleteByUserWeek(user.id, currentSeason, currentWeek)
        for c in req.cards:
            equippedRepo.save(EquippedCard(
                user_id=user.id,
                season=currentSeason,
                week=currentWeek,
                slot_number=c.slotNumber,
                user_card_id=c.userCardId,
                locked=False,
                streak_count=prevStreakByCardId.get(c.userCardId, 1),
                peak_output=prevPeakByCardId.get(c.userCardId),
                weeks_since_break=prevWeeksSinceByCardId.get(c.userCardId, 0),
            ))

        # All-Pro swap bonuses — only apply when roster is locked
        if roster:
            swapCycle = ((currentWeek - 1) // 7 + 1) if isinstance(currentWeek, int) and currentWeek > 0 else 1

            prevAllProIds = set()
            for prev in previousEquipped:
                if prev.swap_bonus_active:
                    prevAllProIds.add(prev.user_card_id)

            newAllProIds = set()
            for c in req.cards:
                template = cardTemplates[c.userCardId]
                if template.classification and "all_pro" in template.classification:
                    newAllProIds.add(c.userCardId)

            # Cards being unequipped (were equipped with their grant unused —
            # prevAllProIds is filtered on swap_bonus_active=True, so a card
            # whose grant was already consumed via a swap won't be in this
            # set and won't be refunded here).
            unequippedAllPro = prevAllProIds - newAllProIds
            for ucId in unequippedAllPro:
                uc = cardUserCards.get(ucId) or session.get(UserCard, ucId)
                if uc and roster.swaps_available > 0:
                    roster.swaps_available -= 1
                    # Reset the cycle marker so re-equipping later in the same
                    # cycle re-grants. (If the swap had been used we'd never
                    # reach this branch — the card's swap_bonus_active would
                    # already be False, excluding it from prevAllProIds.)
                    uc.last_swap_grant_cycle = 0

            # Cards being newly equipped
            freshAllPro = newAllProIds - prevAllProIds
            for ucId in freshAllPro:
                uc = cardUserCards.get(ucId) or session.get(UserCard, ucId)
                if uc and uc.last_swap_grant_cycle < swapCycle:
                    roster.swaps_available += 1
                    uc.last_swap_grant_cycle = swapCycle
                    # Secret — Arsenal (3+ swaps available at once)
                    if (roster.swaps_available or 0) + (roster.purchased_swaps or 0) >= 3:
                        try:
                            from managers import achievementManager as _amArs
                            _amArs.unlockSecret(session, user.id, "arsenal")
                        except Exception:
                            pass
                    eqCard = session.query(EquippedCard).filter_by(
                        user_id=user.id, season=currentSeason, week=currentWeek,
                        user_card_id=ucId,
                    ).first()
                    if eqCard:
                        eqCard.swap_bonus_active = True

            # Cards staying equipped — preserve swap_bonus_active
            stayingAllPro = prevAllProIds & newAllProIds
            for ucId in stayingAllPro:
                eqCard = session.query(EquippedCard).filter_by(
                    user_id=user.id, season=currentSeason, week=currentWeek,
                    user_card_id=ucId,
                ).first()
                if eqCard:
                    eqCard.swap_bonus_active = True

        # Achievement hooks — first card equipped + Gilded (all Prismatic/Diamond full set)
        if req.cards:
            from managers import achievementManager as _am
            _am.onCardEquipped(session, user.id)
            # Gilded — full equipped set (5 or 6 slots, no empties) of Prismatic/Diamond cards
            GILDED_EDITIONS = {"prismatic", "diamond"}
            if len(req.cards) >= 5:
                allGilded = all(
                    (cardTemplates.get(c.userCardId) and cardTemplates[c.userCardId].edition in GILDED_EDITIONS)
                    for c in req.cards
                )
                if allGilded:
                    _am.unlockSecret(session, user.id, "gilded")

        session.commit()

        return build_success_response({"message": "Cards equipped"})
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        logger.error(f"Equip cards failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to equip cards")
    finally:
        session.close()


# ============================================================================
# PACKS & SHOP
# ============================================================================


def _isShopOpen() -> bool:
    """Check if the shop is open (regular season only, before week 28 games finish)."""
    sm = floosball_app.seasonManager if floosball_app else None
    if not sm or not sm.currentSeason:
        return False
    cs = sm.currentSeason
    if cs.isComplete or cs.currentWeek > 28:
        return False
    if cs.currentWeek == 28 and cs.completedWeekGames is not None:
        return False
    return True


def _requireShopOpen():
    """Raise 403 if shop is closed (playoffs/offseason)."""
    if not _isShopOpen():
        raise HTTPException(status_code=403, detail="Shop is closed for the season")


@app.get("/api/packs/types")
def getPackTypes(response: Response, user: Optional[_User] = Depends(_getOptionalUser)):
    """Get available pack types with costs and daily purchase limits.

    Three slices in the response:
      - packs: standard tiers in the current shop_day rotation (humble/grand/exquisite)
      - themedPacks: 4 themed packs from this cycle's FeaturedPackRotation
      - starter: free starter pack (returned separately, special UX)
    """
    # No public cache — response is user-specific (starter claim status +
    # per-pack daily-limit counters). A shared cache here would mix users.
    response.headers["Cache-Control"] = "private, no-store"
    from database.connection import get_session
    from database.models import PackOpening, PendingPackOpening, User
    from database.repositories.card_repositories import PackTypeRepository
    from managers.cardManager import (
        DAILY_PACK_LIMITS, MAX_PACKS_PER_SHOP_CYCLE,
        getActivePackNames, shopDayOfSeason, _countPacksThisCycle,
    )
    from datetime import datetime

    sm = floosball_app.seasonManager if floosball_app else None
    currentSeason = sm.currentSeason.seasonNumber if sm and sm.currentSeason else 0
    currentWeek = sm.currentSeason.currentWeek if sm and sm.currentSeason else 1
    shopDay = shopDayOfSeason(currentWeek)
    activeNames = set(getActivePackNames(shopDay))

    session = get_session()
    try:
        packRepo = PackTypeRepository(session)
        packs = packRepo.getAll()
        rotated = [p for p in packs if p.name in activeNames]
        starterPack = next((p for p in packs if p.name == 'starter'), None)

        # Themed packs come from the rotation table. Pull (or lazily generate)
        # via cardManager. Rotation is per-user so each player sees their own
        # set; the reroll endpoint regenerates it.
        themedPacks = []
        if user is not None and currentSeason > 0:
            try:
                from managers.cardManager import CardManager
                cm = CardManager(floosball_app.serviceContainer if floosball_app else None)
                themedPacks = cm.getActiveThemedPacks(
                    session, user.id, currentSeason, currentWeek
                )
                # Commit the rotation rows that getActiveThemedPacks may have
                # inserted; otherwise they vanish when the session closes.
                session.commit()
            except Exception as e:
                logger.warning(f"Themed pack rotation fetch failed: {e}")
                session.rollback()
                themedPacks = []

        # Count today's purchases per pack type (committed + pending) if authed
        todayCounts = {}
        starterClaimed = False
        if user:
            dayStart = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            for p in list(rotated) + list(themedPacks):
                # Only paid openings count toward the daily shop limit.
                # Free grants (achievement rewards, starter packs) have
                # cost=0 and must not consume the shop allowance.
                committed = session.query(PackOpening).filter(
                    PackOpening.user_id == user.id,
                    PackOpening.pack_type_id == p.id,
                    PackOpening.opened_at >= dayStart,
                    PackOpening.cost > 0,
                ).count()
                pending = session.query(PendingPackOpening).filter(
                    PendingPackOpening.user_id == user.id,
                    PendingPackOpening.pack_type_id == p.id,
                    PendingPackOpening.opened_at >= dayStart,
                    PendingPackOpening.cost_paid > 0,
                ).count()
                todayCounts[p.id] = committed + pending
            dbUser = session.query(User).filter_by(id=user.id).first()
            starterClaimed = (dbUser and dbUser.starter_pack_claimed_season == currentSeason)

        def _packDict(p):
            dailyLimit = DAILY_PACK_LIMITS.get(p.name)
            base = {
                "id": p.id,
                "name": p.name,
                "displayName": p.display_name,
                "cost": p.cost,
                "cardsPerPack": p.cards_per_pack,
                "cardsKept": p.cards_kept,
                "description": p.description,
                "guaranteedRarity": p.guaranteed_rarity,
                "dailyLimit": dailyLimit,
                "remainingToday": max(0, (dailyLimit or 99) - todayCounts.get(p.id, 0)) if (user and dailyLimit is not None) else None,
            }
            if p.theme_type:
                base["themeType"] = p.theme_type
                base["themeValue"] = p.theme_value
            return base

        cyclePacksOpened = _countPacksThisCycle(session, user.id, currentSeason, currentWeek) if user else 0
        cycleRemaining = max(0, MAX_PACKS_PER_SHOP_CYCLE - cyclePacksOpened)
        return build_success_response({
            "packs": [_packDict(p) for p in rotated],
            "themedPacks": [_packDict(p) for p in themedPacks],
            "starter": ({
                **_packDict(starterPack),
                "claimedThisSeason": starterClaimed,
            } if starterPack else None),
            "shopDay": shopDay,
            "shopOpen": _isShopOpen(),
            "cycleLimit": MAX_PACKS_PER_SHOP_CYCLE,
            "cyclePacksOpened": cyclePacksOpened,
            "cycleRemaining": cycleRemaining,
        })
    finally:
        session.close()


@app.get("/api/packs/pending")
def getPendingPack(user: _User = Depends(_getCurrentUser)):
    """Return the user's most recent un-selected pack reveal, if any.

    The reveal+select purchase flow creates a PendingPackOpening row when
    the user pays/claims a pack, and only deletes it when they confirm
    their card picks via /api/packs/select. If the page refreshes between
    those two steps, the modal disappears from the UI but the row stays
    in the DB — the user has effectively paid (or claimed an achievement
    reward) but can't complete the selection. This endpoint lets the
    frontend re-open the picker on next page load.

    Returns `null` data when no pending pack exists.
    """
    from database.connection import get_session
    from database.models import PendingPackOpening, CardTemplate
    from managers.cardManager import CardManager

    session = get_session()
    try:
        pending = (
            session.query(PendingPackOpening)
            .filter(PendingPackOpening.user_id == user.id)
            .order_by(PendingPackOpening.opened_at.desc())
            .first()
        )
        if pending is None:
            return build_success_response(None)

        revealedIds = list(pending.revealed_template_ids or [])
        if not revealedIds:
            return build_success_response(None)

        sm = floosball_app.seasonManager if floosball_app else None
        currentSeason = sm.currentSeason.seasonNumber if sm and sm.currentSeason else pending.season
        cardManager = CardManager(floosball_app.serviceContainer if floosball_app else None)

        # Re-serialize the templates the same way revealPack did originally.
        templates = (
            session.query(CardTemplate)
            .filter(CardTemplate.id.in_(revealedIds))
            .all()
        )
        # Preserve the original draw order — DB query returns them
        # arbitrarily; we want indices to match what selectPackKeeps expects.
        byId = {t.id: t for t in templates}
        ordered = [byId[tid] for tid in revealedIds if tid in byId]
        revealed = [cardManager._serializeTemplate(t, currentSeason) for t in ordered]

        packType = pending.pack_type
        return build_success_response({
            "pendingId": pending.id,
            "packName": packType.display_name if packType else "Pack",
            "cost": pending.cost_paid or 0,
            "cardsPerPack": packType.cards_per_pack if packType else len(revealed),
            "cardsKept": packType.cards_kept if packType else len(revealed),
            "revealed": revealed,
        })
    finally:
        session.close()


class RevealPackRequest(BaseModel):
    packTypeId: int


@app.post("/api/packs/reveal")
def revealPack(req: RevealPackRequest, user: _User = Depends(_getCurrentUser)):
    """Step 1 of the user purchase flow: spend Floobits + reveal cards.

    Cards are NOT yet committed to the user's collection — they're held in
    a PendingPackOpening row until /api/packs/select confirms which to keep.
    """
    _requireShopOpen()
    from database.connection import get_session
    from managers.cardManager import CardManager

    from managers.cardManager import shopDayOfSeason
    sm = floosball_app.seasonManager if floosball_app else None
    currentSeason = sm.currentSeason.seasonNumber if sm and sm.currentSeason else 0
    currentWeek = sm.currentSeason.currentWeek if sm and sm.currentSeason else 1
    shopDay = shopDayOfSeason(currentWeek)
    cardManager = CardManager(floosball_app.serviceContainer if floosball_app else None)

    session = get_session()
    try:
        result = cardManager.revealPack(session, user.id, req.packTypeId, currentSeason, shopDay=shopDay, currentWeek=currentWeek)
        session.commit()
        return build_success_response(result)
    except ValueError as e:
        session.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        session.rollback()
        logger.error(f"Pack reveal failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to reveal pack")
    finally:
        session.close()


class SelectPackRequest(BaseModel):
    pendingId: int
    keptIndices: List[int]


@app.post("/api/packs/select")
def selectPack(req: SelectPackRequest, user: _User = Depends(_getCurrentUser)):
    """Step 2 of the user purchase flow: commit which revealed cards to keep.

    Discarded cards are dropped (no refund). Daily limit was already debited
    on /reveal, so this endpoint is the side-effecting one that creates the
    UserCard rows + records the PackOpening + fires achievement hooks.
    """
    from database.connection import get_session
    from managers.cardManager import CardManager

    sm = floosball_app.seasonManager if floosball_app else None
    currentSeason = sm.currentSeason.seasonNumber if sm and sm.currentSeason else 0
    cardManager = CardManager(floosball_app.serviceContainer if floosball_app else None)

    session = get_session()
    try:
        result = cardManager.selectPackKeeps(
            session, user.id, req.pendingId, req.keptIndices, currentSeason,
        )
        # Achievement hooks fire on the kept cards (matches old single-step behavior)
        from managers import achievementManager as _am
        _am.onPackOpened(session, user.id)
        _am.syncCuratorProgress(session, user.id, currentSeason)
        if any(c.get("edition") == "diamond" for c in (result.get("kept") or [])):
            _am.onDiamondOpened(session, user.id, currentSeason)
        # Secret: Completist (all 4 editions of the same player this season)
        try:
            from database.models import UserCard as _UC, CardTemplate as _CT
            from sqlalchemy import func
            editionRows = (
                session.query(_CT.player_id, func.count(func.distinct(_CT.edition)).label("editionCount"))
                .join(_UC, _UC.card_template_id == _CT.id)
                .filter(_UC.user_id == user.id, _CT.season_created == currentSeason)
                .group_by(_CT.player_id)
                .having(func.count(func.distinct(_CT.edition)) >= 4)
                .first()
            )
            if editionRows:
                _am.unlockSecret(session, user.id, "completist")
        except Exception as _e:
            logger.warning(f"Completist hook failed: {_e}")
        # Secret: Anthology (one of every paid pack type in a single season)
        try:
            _am.checkAnthology(session, user.id, currentSeason)
        except Exception as _e:
            logger.warning(f"Anthology hook failed: {_e}")

        session.commit()
        return build_success_response(result)
    except ValueError as e:
        session.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        session.rollback()
        logger.error(f"Pack selection failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to commit pack selection")
    finally:
        session.close()


@app.post("/api/packs/starter")
def claimStarterPack(user: _User = Depends(_getCurrentUser)):
    """Claim the free once-per-season starter pack (5 base cards, no selection).

    Sets User.starter_pack_claimed_season so the offer disappears until
    the next season. Achievement hooks still fire.
    """
    from database.connection import get_session
    from managers.cardManager import CardManager

    sm = floosball_app.seasonManager if floosball_app else None
    currentSeason = sm.currentSeason.seasonNumber if sm and sm.currentSeason else 0
    cardManager = CardManager(floosball_app.serviceContainer if floosball_app else None)

    session = get_session()
    try:
        result = cardManager.claimStarterPack(session, user.id, currentSeason)
        from managers import achievementManager as _am
        _am.onPackOpened(session, user.id)
        _am.syncCuratorProgress(session, user.id, currentSeason)
        session.commit()
        return build_success_response(result)
    except ValueError as e:
        session.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        session.rollback()
        logger.error(f"Starter pack claim failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to claim starter pack")
    finally:
        session.close()


@app.get("/api/shop/featured")
def getShopFeatured(user: _User = Depends(_getCurrentUser)):
    """Get featured individual cards for sale (persisted per user per season)."""
    from database.connection import get_session
    from managers.cardManager import CardManager
    from managers.timingManager import TimingMode

    sm = floosball_app.seasonManager if floosball_app else None
    currentSeason = sm.currentSeason.seasonNumber if sm and sm.currentSeason else 0
    currentWeek = sm.currentSeason.currentWeek if sm and sm.currentSeason else 0
    isScheduledMode = sm.timingManager.mode in (TimingMode.SCHEDULED, TimingMode.TEST_SCHEDULED) if sm else False

    cardManager = CardManager(floosball_app.serviceContainer if floosball_app else None)

    session = get_session()
    try:
        featured = cardManager.getFeaturedCards(
            session, user.id, currentSeason,
            currentWeek=currentWeek, isScheduledMode=isScheduledMode,
        )
        session.commit()
        return build_success_response({"cards": featured, "currentSeason": currentSeason, "shopOpen": _isShopOpen()})
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


class BuyCardRequest(BaseModel):
    templateId: int


@app.post("/api/shop/buy-card")
def buyFeaturedCard(req: BuyCardRequest, user: _User = Depends(_getCurrentUser)):
    """Buy a single featured card from the shop."""
    _requireShopOpen()
    from database.connection import get_session
    from managers.cardManager import CardManager

    sm = floosball_app.seasonManager if floosball_app else None
    currentSeason = sm.currentSeason.seasonNumber if sm and sm.currentSeason else 0

    cardManager = CardManager(floosball_app.serviceContainer if floosball_app else None)

    session = get_session()
    try:
        card = cardManager.buyFeaturedCard(session, user.id, req.templateId, currentSeason)

        # Keep Curator progress in sync — shop buys add to the collection but
        # weren't previously counted because the sync only ran on pack opens.
        from managers import achievementManager as _am
        _am.syncCuratorProgress(session, user.id, currentSeason)

        # Secret — Sweep (bought every card in the current day's featured shop).
        # Shop refreshes daily; the current batch shares the most recent generated_at.
        try:
            from database.models import FeaturedShopCard
            from sqlalchemy import func
            latestBatch = session.query(func.max(FeaturedShopCard.generated_at)).filter(
                FeaturedShopCard.user_id == user.id,
                FeaturedShopCard.season == currentSeason,
            ).scalar()
            if latestBatch:
                total = session.query(func.count(FeaturedShopCard.id)).filter(
                    FeaturedShopCard.user_id == user.id,
                    FeaturedShopCard.season == currentSeason,
                    FeaturedShopCard.generated_at == latestBatch,
                ).scalar() or 0
                purchased = session.query(func.count(FeaturedShopCard.id)).filter(
                    FeaturedShopCard.user_id == user.id,
                    FeaturedShopCard.season == currentSeason,
                    FeaturedShopCard.generated_at == latestBatch,
                    FeaturedShopCard.purchased == True,  # noqa: E712
                ).scalar() or 0
                if total >= 5 and purchased >= total:
                    from managers import achievementManager as _am
                    _am.unlockSecret(session, user.id, "sweep")
        except Exception as _e:
            logger.warning(f"Sweep hook failed: {_e}")

        session.commit()
        return build_success_response(card)
    except ValueError as e:
        session.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        session.rollback()
        logger.error(f"Card purchase failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to buy card")
    finally:
        session.close()


# ============================================================================
# SHOP REROLL
# ============================================================================


@app.get("/api/shop/reroll-cost")
def getRerollCost(user: _User = Depends(_getCurrentUser)):
    """Get the current reroll cost (escalates with each reroll today)."""
    from database.connection import get_session
    from database.repositories.shop_repository import ShopPurchaseRepository
    from constants import SHOP_REROLL_BASE_COST, SHOP_REROLL_COST_INCREMENT

    session = get_session()
    try:
        shopRepo = ShopPurchaseRepository(session)
        sm = floosball_app.seasonManager if floosball_app else None
        isScheduledMode = sm and sm.timingManager and sm.timingManager._isScheduledMode
        if isScheduledMode:
            rerollCount = shopRepo.getPurchasesToday(user.id, "shop_reroll")
        else:
            currentSeasonNum = sm.currentSeason.seasonNumber if sm and sm.currentSeason else 0
            currentWeek = sm.currentSeason.currentWeek if sm and sm.currentSeason else 0
            cycleLen = 7
            cycleStartWeek = max(1, ((currentWeek - 1) // cycleLen) * cycleLen + 1)
            cycleEndWeek = cycleStartWeek + cycleLen - 1
            rerollCount = shopRepo.getPurchasesForCycle(
                user.id, currentSeasonNum, "shop_reroll", cycleStartWeek, cycleEndWeek
            )
        cost = SHOP_REROLL_BASE_COST + (rerollCount * SHOP_REROLL_COST_INCREMENT)
        return build_success_response({"cost": cost, "rerollCount": rerollCount})
    finally:
        session.close()


@app.post("/api/shop/reroll")
def rerollFeaturedCards(user: _User = Depends(_getCurrentUser)):
    """Reroll the daily selection. Cost escalates with each reroll."""
    _requireShopOpen()
    from database.connection import get_session
    from database.repositories.card_repositories import CurrencyRepository
    from database.repositories.shop_repository import ShopPurchaseRepository
    from database.models import FeaturedShopCard
    from managers.cardManager import CardManager
    from constants import SHOP_REROLL_BASE_COST, SHOP_REROLL_COST_INCREMENT

    sm = floosball_app.seasonManager if floosball_app else None
    currentSeasonNum = sm.currentSeason.seasonNumber if sm and sm.currentSeason else 0
    currentWeek = sm.currentSeason.currentWeek if sm and sm.currentSeason else 0
    isScheduledMode = sm and sm.timingManager and sm.timingManager._isScheduledMode

    if currentWeek < 1:
        raise HTTPException(status_code=400, detail="No active week")

    session = get_session()
    try:
        shopRepo = ShopPurchaseRepository(session)
        currencyRepo = CurrencyRepository(session)

        # Calculate escalating cost
        if isScheduledMode:
            rerollCount = shopRepo.getPurchasesToday(user.id, "shop_reroll")
        else:
            cycleLen = 7
            cycleStartWeek = max(1, ((currentWeek - 1) // cycleLen) * cycleLen + 1)
            cycleEndWeek = cycleStartWeek + cycleLen - 1
            rerollCount = shopRepo.getPurchasesForCycle(
                user.id, currentSeasonNum, "shop_reroll", cycleStartWeek, cycleEndWeek
            )
        cost = SHOP_REROLL_BASE_COST + (rerollCount * SHOP_REROLL_COST_INCREMENT)

        # Deduct
        result = currencyRepo.spendFunds(
            userId=user.id, amount=cost,
            transactionType="shop_reroll",
            description=f"Daily Selection reroll #{rerollCount + 1}",
            season=currentSeasonNum, week=currentWeek,
        )
        if result is None:
            raise HTTPException(status_code=402, detail=f"Insufficient Floobits (need {cost})")

        # Record purchase so next reroll costs more
        shopRepo.createPurchase(
            userId=user.id, itemSlug="shop_reroll", season=currentSeasonNum,
            week=currentWeek, pricePaid=cost,
        )

        # Secret — Finicky (5 consecutive rerolls with no featured-card buys in between).
        # We approximate "in a row" as 5 rerolls since the last card purchase.
        try:
            from database.models import ShopPurchase, CurrencyTransaction
            lastCardBuy = session.query(CurrencyTransaction.created_at).filter(
                CurrencyTransaction.user_id == user.id,
                CurrencyTransaction.transaction_type == "card_purchase",
            ).order_by(CurrencyTransaction.created_at.desc()).first()
            rerollsQuery = session.query(ShopPurchase).filter(
                ShopPurchase.user_id == user.id,
                ShopPurchase.item_slug == "shop_reroll",
            )
            if lastCardBuy:
                rerollsQuery = rerollsQuery.filter(ShopPurchase.created_at > lastCardBuy[0])
            consecutive = rerollsQuery.count()
            if consecutive >= 5:
                from managers import achievementManager as _am
                _am.unlockSecret(session, user.id, "finicky")
        except Exception as _e:
            logger.warning(f"Finicky hook failed: {_e}")

        # Regenerate featured cards
        cardManager = CardManager(floosball_app.serviceContainer if floosball_app else None)
        session.query(FeaturedShopCard).filter(
            FeaturedShopCard.user_id == user.id,
            FeaturedShopCard.season == currentSeasonNum,
            FeaturedShopCard.purchased == False,
        ).delete()
        session.flush()
        featured = cardManager.getFeaturedCards(
            session, user.id, currentSeasonNum,
            currentWeek=currentWeek, isScheduledMode=isScheduledMode,
            forceRegenerate=True,
        )

        nextCost = cost + SHOP_REROLL_COST_INCREMENT
        session.commit()
        return build_success_response({
            "featuredCards": featured,
            "newBalance": result.balance,
            "nextRerollCost": nextCost,
        })
    except HTTPException:
        session.rollback()
        raise
    except Exception as e:
        session.rollback()
        logger.error(f"Shop reroll failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to reroll")
    finally:
        session.close()


# ============================================================================
# THEMED PACK REROLL
# ============================================================================


def _computeThemedPackRerollContext(session, userId: int):
    """Shared helper for cost endpoint + reroll endpoint. Returns
    (rerollCount, cost, currentSeasonNum, currentWeek, isScheduledMode)."""
    from database.repositories.shop_repository import ShopPurchaseRepository
    from constants import (
        THEMED_PACK_REROLL_BASE_COST, THEMED_PACK_REROLL_COST_INCREMENT,
    )

    shopRepo = ShopPurchaseRepository(session)
    sm = floosball_app.seasonManager if floosball_app else None
    currentSeasonNum = sm.currentSeason.seasonNumber if sm and sm.currentSeason else 0
    currentWeek = sm.currentSeason.currentWeek if sm and sm.currentSeason else 0
    isScheduledMode = sm and sm.timingManager and sm.timingManager._isScheduledMode

    if isScheduledMode:
        rerollCount = shopRepo.getPurchasesToday(userId, "themed_pack_reroll")
    else:
        cycleLen = 7
        cycleStartWeek = max(1, ((currentWeek - 1) // cycleLen) * cycleLen + 1)
        cycleEndWeek = cycleStartWeek + cycleLen - 1
        rerollCount = shopRepo.getPurchasesForCycle(
            userId, currentSeasonNum, "themed_pack_reroll", cycleStartWeek, cycleEndWeek
        )
    cost = THEMED_PACK_REROLL_BASE_COST + (rerollCount * THEMED_PACK_REROLL_COST_INCREMENT)
    return rerollCount, cost, currentSeasonNum, currentWeek, isScheduledMode


@app.get("/api/shop/themed-pack-reroll-cost")
def getThemedPackRerollCost(user: _User = Depends(_getCurrentUser)):
    """Get the current themed pack reroll cost (escalates per cycle)."""
    from database.connection import get_session

    session = get_session()
    try:
        rerollCount, cost, *_ = _computeThemedPackRerollContext(session, user.id)
        return build_success_response({"cost": cost, "rerollCount": rerollCount})
    finally:
        session.close()


@app.post("/api/shop/reroll-themed-packs")
def rerollThemedPacks(user: _User = Depends(_getCurrentUser)):
    """Reroll the user's themed pack rotation. Cost escalates per cycle."""
    _requireShopOpen()
    from database.connection import get_session
    from database.repositories.card_repositories import CurrencyRepository
    from database.repositories.shop_repository import ShopPurchaseRepository
    from managers.cardManager import CardManager

    session = get_session()
    try:
        rerollCount, cost, currentSeasonNum, currentWeek, _ = _computeThemedPackRerollContext(session, user.id)

        if currentWeek < 1 or currentSeasonNum < 1:
            raise HTTPException(status_code=400, detail="No active week")

        currencyRepo = CurrencyRepository(session)
        result = currencyRepo.spendFunds(
            userId=user.id, amount=cost,
            transactionType="themed_pack_reroll",
            description=f"Themed pack reroll #{rerollCount + 1}",
            season=currentSeasonNum, week=currentWeek,
        )
        if result is None:
            raise HTTPException(status_code=402, detail=f"Insufficient Floobits (need {cost})")

        shopRepo = ShopPurchaseRepository(session)
        shopRepo.createPurchase(
            userId=user.id, itemSlug="themed_pack_reroll", season=currentSeasonNum,
            week=currentWeek, pricePaid=cost,
        )

        cardManager = CardManager(floosball_app.serviceContainer if floosball_app else None)
        newPacks = cardManager.rerollThemedPacks(session, user.id, currentSeasonNum, currentWeek)

        from constants import THEMED_PACK_REROLL_COST_INCREMENT
        nextCost = cost + THEMED_PACK_REROLL_COST_INCREMENT

        def _packDict(p):
            return {
                "id": p.id,
                "name": p.name,
                "displayName": p.display_name,
                "cost": p.cost,
                "cardsPerPack": p.cards_per_pack,
                "cardsKept": p.cards_kept,
                "description": p.description,
                "guaranteedRarity": p.guaranteed_rarity,
                "dailyLimit": None,
                "remainingToday": None,
                "themeType": p.theme_type,
                "themeValue": p.theme_value,
            }

        session.commit()
        return build_success_response({
            "themedPacks": [_packDict(p) for p in newPacks],
            "newBalance": result.balance,
            "nextRerollCost": nextCost,
        })
    except HTTPException:
        session.rollback()
        raise
    except Exception as e:
        session.rollback()
        logger.error(f"Themed pack reroll failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to reroll themed packs")
    finally:
        session.close()


# ============================================================================
# POWER-UPS
# ============================================================================


@app.get("/api/shop/powerups")
def getShopPowerups(user: _User = Depends(_getCurrentUser)):
    """Get power-up catalog with prices, limits, and user's current purchase state."""
    from database.connection import get_session
    from database.models import FantasyRoster
    from database.repositories.shop_repository import ShopPurchaseRepository, ModifierOverrideRepository
    from constants import POWERUP_CATALOG, SWAP_CYCLE_WEEKS
    from managers.timingManager import TimingMode
    from datetime import date

    currentSeasonNum = _getCurrentSeasonNumber()
    if currentSeasonNum is None:
        raise HTTPException(status_code=400, detail="No active season")
    if floosball_app is None:
        raise HTTPException(status_code=503, detail="Application not initialized")

    sm = floosball_app.seasonManager
    currentWeek = sm.currentSeason.currentWeek if sm.currentSeason else 0
    timingMode = sm.timingManager.mode
    isScheduledMode = timingMode in (TimingMode.SCHEDULED, TimingMode.TEST_SCHEDULED)

    session = get_session()
    try:
        shopRepo = ShopPurchaseRepository(session)
        modRepo = ModifierOverrideRepository(session)

        # Current swap cycle for testing modes
        swapCycle = ((currentWeek - 1) // SWAP_CYCLE_WEEKS + 1) if currentWeek > 0 else 1
        cycleStartWeek = (swapCycle - 1) * SWAP_CYCLE_WEEKS + 1
        cycleEndWeek = swapCycle * SWAP_CYCLE_WEEKS

        # Get roster for swap info
        roster = session.query(FantasyRoster).filter_by(
            user_id=user.id, season=currentSeasonNum
        ).first()
        isLocked = roster.is_locked if roster else False

        items = []
        for slug, info in POWERUP_CATALOG.items():
            item = {
                "slug": slug,
                "displayName": info["displayName"],
                "description": info["description"],
                "price": info["price"],
            }

            if slug == "extra_swap":
                # Daily limit: 1 per day (production) or 1 per cycle (testing)
                if isScheduledMode:
                    purchasedCount = shopRepo.getPurchasesToday(user.id, slug)
                else:
                    purchasedCount = shopRepo.getPurchasesForCycle(
                        user.id, currentSeasonNum, slug, cycleStartWeek, cycleEndWeek
                    )
                item["purchased"] = purchasedCount
                item["limit"] = 1
                item["limitLabel"] = "per day" if isScheduledMode else "per cycle"
                item["available"] = purchasedCount < 1 and currentWeek > 0

            elif slug == "modifier_nullifier":
                # 1 per user per week
                existingOverride = modRepo.getOverride(user.id, currentSeasonNum, currentWeek)
                item["purchased"] = 1 if existingOverride else 0
                item["limit"] = 1
                item["limitLabel"] = "per week"
                item["available"] = not existingOverride and currentWeek > 0

            elif slug == "temp_flex":
                # 1 active at a time, 2 per season
                activeFlex = shopRepo.getActiveTempFlex(user.id, currentSeasonNum, currentWeek)
                seasonCount = shopRepo.getSeasonPurchaseCount(user.id, currentSeasonNum, slug)
                item["purchased"] = seasonCount
                item["limit"] = info.get("seasonLimit", 2)
                item["limitLabel"] = "per season"
                item["durationWeeks"] = info.get("durationWeeks", 4)
                item["activeUntilWeek"] = activeFlex.expires_at_week if activeFlex else None
                item["available"] = (
                    activeFlex is None
                    and seasonCount < info.get("seasonLimit", 2) and currentWeek > 0
                )

            elif slug == "temp_card_slot":
                # 1 active at a time, 2 per season (mirrors temp_flex)
                activeSlot = shopRepo.getActiveTempCardSlot(user.id, currentSeasonNum, currentWeek)
                seasonCount = shopRepo.getSeasonPurchaseCount(user.id, currentSeasonNum, slug)
                item["purchased"] = seasonCount
                item["limit"] = info.get("seasonLimit", 2)
                item["limitLabel"] = "per season"
                item["durationWeeks"] = info.get("durationWeeks", 4)
                item["activeUntilWeek"] = activeSlot.expires_at_week if activeSlot else None
                item["available"] = (
                    activeSlot is None
                    and seasonCount < info.get("seasonLimit", 2) and currentWeek > 0
                )

            elif slug == "fortunes_favor":
                # 1 active at a time, 2 per season (mirrors temp_flex)
                activeFavor = shopRepo.getActiveFortunesFavor(user.id, currentSeasonNum, currentWeek)
                seasonCount = shopRepo.getSeasonPurchaseCount(user.id, currentSeasonNum, slug)
                item["purchased"] = seasonCount
                item["limit"] = info.get("seasonLimit", 2)
                item["limitLabel"] = "per season"
                item["durationWeeks"] = info.get("durationWeeks", 3)
                item["activeUntilWeek"] = activeFavor.expires_at_week if activeFavor else None
                item["available"] = (
                    activeFavor is None
                    and seasonCount < info.get("seasonLimit", 2) and currentWeek > 0
                )

            elif slug == "income_boost":
                activeBoost = shopRepo.getActiveIncomeBoost(user.id, currentSeasonNum, currentWeek)
                seasonCount = shopRepo.getSeasonPurchaseCount(user.id, currentSeasonNum, slug)
                item["purchased"] = seasonCount
                item["limit"] = info.get("seasonLimit", 2)
                item["limitLabel"] = "per season"
                item["durationWeeks"] = info.get("durationWeeks", 4)
                item["activeUntilWeek"] = activeBoost.expires_at_week if activeBoost else None
                item["available"] = (
                    activeBoost is None
                    and seasonCount < info.get("seasonLimit", 2) and currentWeek > 0
                )

            items.append(item)

        return build_success_response({
            "items": items,
            "currentWeek": currentWeek,
            "currentSeason": currentSeasonNum,
        })
    finally:
        session.close()


class BuyPowerupRequest(BaseModel):
    itemSlug: str


@app.post("/api/shop/powerups/buy")
def buyPowerup(req: BuyPowerupRequest, user: _User = Depends(_getCurrentUser)):
    """Purchase a power-up. Validates eligibility, deducts Floobits, executes effect."""
    _requireShopOpen()
    from database.connection import get_session
    from database.models import FantasyRoster, FeaturedShopCard
    from database.repositories.shop_repository import ShopPurchaseRepository, ModifierOverrideRepository
    from database.repositories.card_repositories import CurrencyRepository
    from constants import POWERUP_CATALOG, SWAP_CYCLE_WEEKS
    from managers.timingManager import TimingMode
    from managers.cardManager import CardManager
    from datetime import date

    currentSeasonNum = _getCurrentSeasonNumber()
    if currentSeasonNum is None:
        raise HTTPException(status_code=400, detail="No active season")
    if floosball_app is None:
        raise HTTPException(status_code=503, detail="Application not initialized")

    itemInfo = POWERUP_CATALOG.get(req.itemSlug)
    if not itemInfo:
        raise HTTPException(status_code=400, detail=f"Unknown power-up: {req.itemSlug}")

    sm = floosball_app.seasonManager
    currentWeek = sm.currentSeason.currentWeek if sm.currentSeason else 0
    timingMode = sm.timingManager.mode
    isScheduledMode = timingMode in (TimingMode.SCHEDULED, TimingMode.TEST_SCHEDULED)

    session = get_session()
    try:
        shopRepo = ShopPurchaseRepository(session)
        modRepo = ModifierOverrideRepository(session)
        currencyRepo = CurrencyRepository(session)

        swapCycle = ((currentWeek - 1) // SWAP_CYCLE_WEEKS + 1) if currentWeek > 0 else 1
        cycleStartWeek = (swapCycle - 1) * SWAP_CYCLE_WEEKS + 1
        cycleEndWeek = swapCycle * SWAP_CYCLE_WEEKS

        price = itemInfo["price"]
        expiresAtWeek = None
        slug = req.itemSlug

        # ── Item-specific validation ──

        if slug == "extra_swap":
            if currentWeek < 1:
                raise HTTPException(status_code=400, detail="No active week")
            # Daily/cycle limit
            if isScheduledMode:
                count = shopRepo.getPurchasesToday(user.id, slug)
            else:
                count = shopRepo.getPurchasesForCycle(user.id, currentSeasonNum, slug, cycleStartWeek, cycleEndWeek)
            if count >= 1:
                raise HTTPException(status_code=409, detail="Extra swap already purchased this period")

        elif slug == "modifier_nullifier":
            if currentWeek < 1:
                raise HTTPException(status_code=400, detail="No active week")
            existing = modRepo.getOverride(user.id, currentSeasonNum, currentWeek)
            if existing:
                raise HTTPException(status_code=409, detail="Nullifier already active this week")

        elif slug == "temp_flex":
            if currentWeek < 1:
                raise HTTPException(status_code=400, detail="No active week")
            activeFlex = shopRepo.getActiveTempFlex(user.id, currentSeasonNum, currentWeek)
            if activeFlex:
                if activeFlex.week > currentWeek:
                    raise HTTPException(status_code=409, detail="You already have Conscription starting next week")
                raise HTTPException(status_code=409, detail="You already have an active flex slot")
            seasonCount = shopRepo.getSeasonPurchaseCount(user.id, currentSeasonNum, slug)
            seasonLimit = itemInfo.get("seasonLimit", 2)
            if seasonCount >= seasonLimit:
                raise HTTPException(status_code=409, detail=f"Season limit reached ({seasonLimit})")
            durationWeeks = itemInfo.get("durationWeeks", 4)
            # Defer effective start to next week if the current week's games
            # are in progress OR already complete (week hasn't rolled). In
            # both states the user can't actually benefit from the powerup
            # this week — rosters/cards are locked during play, and after
            # games end the week-end card calc has already run. Charging
            # the user a week of duration they can't use is the bug.
            deferStart = _areGamesStarted() or _areGamesCompleted()
            effectiveStartWeek = currentWeek + 1 if deferStart else currentWeek
            expiresAtWeek = effectiveStartWeek + durationWeeks - 1

        elif slug == "temp_card_slot":
            if currentWeek < 1:
                raise HTTPException(status_code=400, detail="No active week")
            activeSlot = shopRepo.getActiveTempCardSlot(user.id, currentSeasonNum, currentWeek)
            if activeSlot:
                if activeSlot.week > currentWeek:
                    raise HTTPException(status_code=409, detail="You already have Accession starting next week")
                raise HTTPException(status_code=409, detail="You already have an active 6th card slot")
            seasonCount = shopRepo.getSeasonPurchaseCount(user.id, currentSeasonNum, slug)
            seasonLimit = itemInfo.get("seasonLimit", 2)
            if seasonCount >= seasonLimit:
                raise HTTPException(status_code=409, detail=f"Season limit reached ({seasonLimit})")
            durationWeeks = itemInfo.get("durationWeeks", 4)
            # See temp_flex branch for the deferral rationale — the same
            # in-progress-or-completed-this-week guard applies here.
            deferStart = _areGamesStarted() or _areGamesCompleted()
            effectiveStartWeek = currentWeek + 1 if deferStart else currentWeek
            expiresAtWeek = effectiveStartWeek + durationWeeks - 1

        elif slug == "fortunes_favor":
            if currentWeek < 1:
                raise HTTPException(status_code=400, detail="No active week")
            activeFavor = shopRepo.getActiveFortunesFavor(user.id, currentSeasonNum, currentWeek)
            if activeFavor:
                if activeFavor.week > currentWeek:
                    raise HTTPException(status_code=409, detail="You already have Patronage starting next week")
                raise HTTPException(status_code=409, detail="You already have Patronage active")
            seasonCount = shopRepo.getSeasonPurchaseCount(user.id, currentSeasonNum, slug)
            seasonLimit = itemInfo.get("seasonLimit", 2)
            if seasonCount >= seasonLimit:
                raise HTTPException(status_code=409, detail=f"Season limit reached ({seasonLimit})")
            durationWeeks = itemInfo.get("durationWeeks", 3)
            # See temp_flex branch for the deferral rationale — the same
            # in-progress-or-completed-this-week guard applies here.
            deferStart = _areGamesStarted() or _areGamesCompleted()
            effectiveStartWeek = currentWeek + 1 if deferStart else currentWeek
            expiresAtWeek = effectiveStartWeek + durationWeeks - 1

        elif slug == "income_boost":
            if currentWeek < 1:
                raise HTTPException(status_code=400, detail="No active week")
            activeBoost = shopRepo.getActiveIncomeBoost(user.id, currentSeasonNum, currentWeek)
            if activeBoost:
                if activeBoost.week > currentWeek:
                    raise HTTPException(status_code=409, detail="You already have Endowment starting next week")
                raise HTTPException(status_code=409, detail="You already have Endowment active")
            seasonCount = shopRepo.getSeasonPurchaseCount(user.id, currentSeasonNum, slug)
            seasonLimit = itemInfo.get("seasonLimit", 2)
            if seasonCount >= seasonLimit:
                raise HTTPException(status_code=409, detail=f"Season limit reached ({seasonLimit})")
            durationWeeks = itemInfo.get("durationWeeks", 4)
            # See temp_flex branch for the deferral rationale — the same
            # in-progress-or-completed-this-week guard applies here.
            deferStart = _areGamesStarted() or _areGamesCompleted()
            effectiveStartWeek = currentWeek + 1 if deferStart else currentWeek
            expiresAtWeek = effectiveStartWeek + durationWeeks - 1

        # ── Deduct Floobits ──

        result = currencyRepo.spendFunds(
            userId=user.id, amount=price,
            transactionType=f"powerup_{slug}",
            description=f"Power-up: {itemInfo['displayName']}",
            season=currentSeasonNum, week=currentWeek,
        )
        if result is None:
            raise HTTPException(status_code=402, detail=f"Insufficient Floobits (need {price})")

        # ── Record purchase ──
        # For duration-based powerups, `week` represents the EFFECTIVE start
        # week (deferred one week when bought mid-games). For one-shot
        # powerups (no expiresAtWeek), it's still the purchase week.
        try:
            purchaseWeek = effectiveStartWeek  # set by duration-based branches above
        except NameError:
            purchaseWeek = currentWeek
        shopRepo.createPurchase(
            userId=user.id, itemSlug=slug, season=currentSeasonNum,
            week=purchaseWeek, pricePaid=price, expiresAtWeek=expiresAtWeek,
        )

        # ── Execute item effect ──

        responseData = {"message": f"Purchased {itemInfo['displayName']}", "newBalance": result.balance}

        if slug == "extra_swap":
            roster = session.query(FantasyRoster).filter_by(
                user_id=user.id, season=currentSeasonNum
            ).first()
            if not roster:
                raise HTTPException(status_code=400, detail="No roster found for this season")
            roster.purchased_swaps += 1
            responseData["purchasedSwaps"] = roster.purchased_swaps
            responseData["totalSwapsAvailable"] = roster.swaps_available + roster.purchased_swaps
            # Secret — Arsenal (3+ swaps available at once)
            if (roster.swaps_available or 0) + (roster.purchased_swaps or 0) >= 3:
                try:
                    from managers import achievementManager as _amArs
                    _amArs.unlockSecret(session, user.id, "arsenal")
                except Exception:
                    pass

        elif slug == "modifier_nullifier":
            modRepo.createOverride(
                userId=user.id, season=currentSeasonNum,
                week=currentWeek, modifier="steady",
            )
            responseData["overrideModifier"] = "steady"

        elif slug == "temp_flex":
            responseData["expiresAtWeek"] = expiresAtWeek
            responseData["durationWeeks"] = itemInfo.get("durationWeeks", 4)

        elif slug == "temp_card_slot":
            responseData["expiresAtWeek"] = expiresAtWeek
            responseData["durationWeeks"] = itemInfo.get("durationWeeks", 4)

        elif slug == "fortunes_favor":
            responseData["expiresAtWeek"] = expiresAtWeek
            responseData["durationWeeks"] = itemInfo.get("durationWeeks", 3)

        elif slug == "income_boost":
            responseData["expiresAtWeek"] = expiresAtWeek
            responseData["durationWeeks"] = itemInfo.get("durationWeeks", 4)

        # Secret — Dabbler (purchased every type of power-up at least once, lifetime)
        try:
            from database.models import ShopPurchase
            from sqlalchemy import func, distinct
            powerupSlugs = set(POWERUP_CATALOG.keys())
            distinctBought = session.query(func.count(distinct(ShopPurchase.item_slug))).filter(
                ShopPurchase.user_id == user.id,
                ShopPurchase.item_slug.in_(list(powerupSlugs)),
            ).scalar() or 0
            if distinctBought >= len(powerupSlugs):
                from managers import achievementManager as _am
                _am.unlockSecret(session, user.id, "dabbler")
        except Exception as _e:
            logger.warning(f"Dabbler hook failed: {_e}")

        session.commit()
        return build_success_response(responseData)
    except HTTPException:
        session.rollback()
        raise
    except Exception as e:
        session.rollback()
        logger.error(f"Power-up purchase failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to purchase power-up")
    finally:
        session.close()


@app.get("/api/shop/powerups/active")
def getActivePowerups(user: _User = Depends(_getCurrentUser)):
    """Get user's currently active power-ups."""
    from database.connection import get_session
    from database.models import FantasyRoster
    from database.repositories.shop_repository import ShopPurchaseRepository, ModifierOverrideRepository

    currentSeasonNum = _getCurrentSeasonNumber()
    if currentSeasonNum is None:
        raise HTTPException(status_code=400, detail="No active season")
    if floosball_app is None:
        raise HTTPException(status_code=503, detail="Application not initialized")

    sm = floosball_app.seasonManager
    currentWeek = sm.currentSeason.currentWeek if sm.currentSeason else 0

    session = get_session()
    try:
        shopRepo = ShopPurchaseRepository(session)
        modRepo = ModifierOverrideRepository(session)

        active = []

        # Temp flex
        activeFlex = shopRepo.getActiveTempFlex(user.id, currentSeasonNum, currentWeek)
        if activeFlex:
            # ShopPurchase.week is the EFFECTIVE start week. A purchase made
            # mid-games has week = currentWeek + 1, so during the purchase
            # week we shouldn't count the partial week against the duration.
            deferred = activeFlex.week > currentWeek
            weeksRemaining = activeFlex.expires_at_week - currentWeek + (0 if deferred else 1)
            active.append({
                "slug": "temp_flex",
                "displayName": "Conscription",
                "expiresAtWeek": activeFlex.expires_at_week,
                "weeksRemaining": max(0, weeksRemaining),
                "expiring": weeksRemaining == 1,
                "pending": deferred,
            })

        # Temp card slot
        activeCardSlot = shopRepo.getActiveTempCardSlot(user.id, currentSeasonNum, currentWeek)
        if activeCardSlot:
            deferred = activeCardSlot.week > currentWeek
            weeksRemaining = activeCardSlot.expires_at_week - currentWeek + (0 if deferred else 1)
            active.append({
                "slug": "temp_card_slot",
                "displayName": "Accession",
                "expiresAtWeek": activeCardSlot.expires_at_week,
                "weeksRemaining": max(0, weeksRemaining),
                "expiring": weeksRemaining == 1,
                "pending": deferred,
            })

        # Income boost (Endowment) — flatter FP→F curve while active
        activeBoost = shopRepo.getActiveIncomeBoost(user.id, currentSeasonNum, currentWeek)
        if activeBoost:
            # If games are in progress OR done-but-week-hasn't-rolled, the
            # current week is already "spent" — don't count it as remaining.
            weekConsumed = _areGamesStarted() or _areGamesCompleted()
            weeksRemaining = activeBoost.expires_at_week - currentWeek + (0 if weekConsumed else 1)
            from constants import (
                WEEKLY_FP_FLOOBIT_SCALE, WEEKLY_FP_FLOOBIT_EXPONENT,
                WEEKLY_FP_FLOOBIT_BOOSTED_SCALE, WEEKLY_FP_FLOOBIT_BOOSTED_EXPONENT,
            )
            active.append({
                "slug": "income_boost",
                "displayName": "Endowment",
                "expiresAtWeek": activeBoost.expires_at_week,
                "weeksRemaining": max(0, weeksRemaining),
                "expiring": weeksRemaining <= 1,
                "scale": WEEKLY_FP_FLOOBIT_SCALE,
                "exponent": WEEKLY_FP_FLOOBIT_EXPONENT,
                "boostedScale": WEEKLY_FP_FLOOBIT_BOOSTED_SCALE,
                "boostedExponent": WEEKLY_FP_FLOOBIT_BOOSTED_EXPONENT,
            })

        # Fortune's Favor (Patronage) — boosts chance card trigger rates
        activeFavor = shopRepo.getActiveFortunesFavor(user.id, currentSeasonNum, currentWeek)
        if activeFavor:
            # If games are in progress OR done-but-week-hasn't-rolled, the
            # current week is already "spent" — don't count it as remaining.
            weekConsumed = _areGamesStarted() or _areGamesCompleted()
            weeksRemaining = activeFavor.expires_at_week - currentWeek + (0 if weekConsumed else 1)
            active.append({
                "slug": "fortunes_favor",
                "displayName": "Patronage",
                "expiresAtWeek": activeFavor.expires_at_week,
                "weeksRemaining": max(0, weeksRemaining),
                "expiring": weeksRemaining <= 1,
            })

        # Modifier nullifier (current week)
        override = modRepo.getOverride(user.id, currentSeasonNum, currentWeek)
        if override:
            active.append({
                "slug": "modifier_nullifier",
                "displayName": "Annulment",
                "overrideModifier": override.override_modifier,
                "week": currentWeek,
            })

        # Extra swaps (show if user has any banked)
        roster = session.query(FantasyRoster).filter_by(
            user_id=user.id, season=currentSeasonNum
        ).first()
        if roster and roster.purchased_swaps > 0:
            active.append({
                "slug": "extra_swap",
                "displayName": "Dispensation",
                "count": roster.purchased_swaps,
            })

        return build_success_response({
            "active": active,
            "currentWeek": currentWeek,
        })
    finally:
        session.close()


# ============================================================================
# GM MODE
# ============================================================================


class GmVoteRequest(BaseModel):
    voteType: str
    targetPlayerId: Optional[int] = None
    direction: str = "yea"  # 'yea' (support) or 'nay' (oppose)


class GmVoteUndoRequest(BaseModel):
    voteType: str
    targetPlayerId: Optional[int] = None


class GmFaBallotRequest(BaseModel):
    rankings: List[int]


@app.post("/api/gm/vote")
def cast_gm_vote(req: GmVoteRequest, user: _User = Depends(_getCurrentUser)):
    """Cast a GM Mode vote for user's favorite team."""
    from database.connection import get_session
    from database.repositories.gm_repository import GmVoteRepository
    from database.repositories.card_repositories import CurrencyRepository
    from database.models import User, Player, Coach
    from constants import GM_VOTE_TYPES, GM_VOTE_COST, GM_TRIBUNE_VOTE_THRESHOLD
    from managers.gmManager import GmManager

    if req.voteType not in GM_VOTE_TYPES:
        raise HTTPException(400, f"Invalid vote type: {req.voteType}")

    if req.voteType == "sign_fa":
        raise HTTPException(400, "Use POST /api/gm/fa-ballot for free agent votes")

    # Yea/nay only applies to the binary threshold directives; hire_coach is a
    # selection (oppose by backing someone else) and ranked ballots are support.
    direction = "nay" if req.direction == "nay" else "yea"
    if direction == "nay" and req.voteType not in ("fire_coach", "resign_player", "cut_player"):
        raise HTTPException(400, "Only fire, cut, and re-sign votes can be opposed")

    # Block votes during offseason
    sm = floosball_app.seasonManager if floosball_app else None
    if sm and sm.currentSeason and sm.currentSeason.currentWeek == 'Offseason':
        raise HTTPException(400, "The Board has adjourned for the offseason")

    session = get_session()
    try:
        dbUser = session.query(User).filter_by(id=user.id).first()
        if not dbUser or not dbUser.favorite_team_id:
            raise HTTPException(400, "You must have a favorite team to vote")

        teamId = dbUser.favorite_team_id

        # Validate target
        if req.voteType in ("cut_player", "resign_player"):
            if not req.targetPlayerId:
                raise HTTPException(400, "targetPlayerId required for this vote type")
            player = session.query(Player).filter_by(id=req.targetPlayerId).first()
            if not player or player.team_id != teamId:
                raise HTTPException(400, "Target player not on your favorite team")
            if req.voteType == "resign_player" and player.term_remaining != 1:
                raise HTTPException(400, "Player does not have an expiring contract")
            if req.voteType == "resign_player" and getattr(player, 'will_retire', False):
                raise HTTPException(400, "Player has announced retirement and cannot be re-signed")
        elif req.voteType == "hire_coach":
            if not req.targetPlayerId:
                raise HTTPException(400, "targetPlayerId (coach ID) required for hire_coach")
            coach = session.query(Coach).filter_by(id=req.targetPlayerId).first()
            if not coach:
                raise HTTPException(400, "Coach not available in the hiring pool")
            # Coach is "available" if no team has them as coach_id.
            from database.models import Team as DBTeam
            assignedAt = session.query(DBTeam).filter_by(coach_id=coach.id).first()
            if assignedAt is not None:
                raise HTTPException(400, "Coach not available in the hiring pool")

        voteRepo = GmVoteRepository(session)
        sm = floosball_app.seasonManager if floosball_app else None
        currentSeason = sm.currentSeason.seasonNumber if sm and sm.currentSeason else 0

        # One vote per fan per target. To change your mind (or switch sides),
        # withdraw first — no stacking, so the cost is flat (no escalation).
        existingDir = voteRepo.getUserDirectionOnTarget(
            user.id, teamId, currentSeason, req.voteType, req.targetPlayerId
        )
        if existingDir:
            raise HTTPException(
                400,
                "You've already voted on this. Withdraw your vote to change it.",
            )

        cost = GM_VOTE_COST[req.voteType]
        currencyRepo = CurrencyRepository(session)
        result = currencyRepo.spendFunds(
            user.id, cost, "gm_vote",
            f"GM vote: {req.voteType}", currentSeason,
        )
        if result is None:
            raise HTTPException(400, "Insufficient Floobits")

        # Cast vote
        vote = voteRepo.castVote(
            userId=user.id, teamId=teamId, season=currentSeason,
            voteType=req.voteType, costPaid=cost,
            targetPlayerId=req.targetPlayerId, direction=direction,
        )

        # Tribune — cast GM_TRIBUNE_VOTE_THRESHOLD votes in a season (any mix of
        # targets). The other GM secret, Scorched Earth (key "mutineer"), now
        # fires at offseason resolution on a full team teardown — see
        # seasonManager._awardCleanHouseAchievements — not on vote cast.
        try:
            updatedCounts = voteRepo.getUserVoteCounts(user.id, currentSeason)
            if updatedCounts.get("total", 0) >= GM_TRIBUNE_VOTE_THRESHOLD:
                from managers import achievementManager as _am
                _am.unlockSecret(session, user.id, "tribune")
        except Exception as _e:
            logger.warning(f"Tribune hook failed: {_e}")

        session.commit()

        # Get current tally for response (use per-team engaged fan count)
        engagedFans = voteRepo.getEngagedVoterCount(teamId, currentSeason)
        tallies = voteRepo.getVoteTallies(teamId, currentSeason)
        targetTally = next(
            (t for t in tallies
             if t["voteType"] == req.voteType
             and t["targetPlayerId"] == req.targetPlayerId),
            {"votes": 0, "votesFor": 0, "votesAgainst": 0}
        )
        gm = GmManager(session)
        if req.voteType == "hire_coach":
            hireVoteCounts = [
                t["votes"] for t in tallies
                if t["voteType"] == "hire_coach" and t.get("targetPlayerId")
            ]
            hireLeaderVotes = max(hireVoteCounts) if hireVoteCounts else 0
            hireLeaderCount = (
                sum(1 for v in hireVoteCounts if v == hireLeaderVotes)
                if hireLeaderVotes > 0 else 0
            )
            threshold, probability = gm.hireCoachDisplay(
                targetTally["votes"], hireLeaderVotes, hireLeaderCount
            )
        elif req.voteType == "sign_fa":
            threshold = gm.calculateBallotThreshold(engagedFans)
            probability = gm.calculateProbability(targetTally["votes"], threshold)
        else:
            teamFanCount = voteRepo.getTeamFanCount(teamId, season=currentSeason)
            threshold = gm.calculateThreshold(teamFanCount)
            probability = gm.calculateProbability(targetTally["votes"], threshold)

        return build_success_response({
            "voteId": vote.id,
            "voteType": req.voteType,
            "direction": direction,
            "targetPlayerId": req.targetPlayerId,
            "costPaid": cost,
            "currentVotes": targetTally["votes"],
            "votesFor": targetTally.get("votesFor", 0),
            "votesAgainst": targetTally.get("votesAgainst", 0),
            "threshold": threshold,
            "probability": round(probability, 3),
            "remainingBalance": result.balance,
        })
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        logger.error(f"GM vote error: {e}")
        raise HTTPException(500, "Failed to cast vote")
    finally:
        session.close()


@app.post("/api/gm/vote/undo")
def undo_gm_vote(req: GmVoteUndoRequest, user: _User = Depends(_getCurrentUser)):
    """Withdraw the user's most-recent vote on a target and refund its cost.

    Lets a fan flip sides (withdraw, then cast the other way) or simply take
    back a misclick — the affordance the UI already exposed but had no backend
    for. Refund reverses the spend cleanly (no lifetime-earned inflation)."""
    from database.connection import get_session
    from database.repositories.gm_repository import GmVoteRepository
    from database.repositories.card_repositories import CurrencyRepository
    from database.models import User
    from managers.gmManager import GmManager

    sm = floosball_app.seasonManager if floosball_app else None
    if sm and sm.currentSeason and sm.currentSeason.currentWeek == 'Offseason':
        raise HTTPException(400, "The Board has adjourned for the offseason")

    session = get_session()
    try:
        dbUser = session.query(User).filter_by(id=user.id).first()
        if not dbUser or not dbUser.favorite_team_id:
            raise HTTPException(400, "You must have a favorite team to vote")
        teamId = dbUser.favorite_team_id
        currentSeason = sm.currentSeason.seasonNumber if sm and sm.currentSeason else 0

        voteRepo = GmVoteRepository(session)
        vote = voteRepo.withdrawMostRecentVote(
            user.id, teamId, currentSeason, req.voteType, req.targetPlayerId
        )
        if vote is None:
            raise HTTPException(400, "You have no vote to withdraw on this")
        refund = vote.cost_paid  # read before commit — the row is now deleted

        currencyRepo = CurrencyRepository(session)
        currency = currencyRepo.refundFunds(
            user.id, refund, "gm_vote_refund",
            f"GM vote withdrawn: {req.voteType}", currentSeason,
        )
        session.commit()

        # Updated net tally for the response. The frontend also refetches the
        # team summary, which carries the authoritative per-type thresholds.
        tallies = voteRepo.getVoteTallies(teamId, currentSeason)
        targetTally = next(
            (t for t in tallies
             if t["voteType"] == req.voteType
             and t["targetPlayerId"] == req.targetPlayerId),
            {"votes": 0, "votesFor": 0, "votesAgainst": 0}
        )
        gm = GmManager(session)
        teamFanCount = voteRepo.getTeamFanCount(teamId, season=currentSeason)
        threshold = gm.calculateThreshold(teamFanCount)
        probability = gm.calculateProbability(targetTally["votes"], threshold)

        return build_success_response({
            "voteType": req.voteType,
            "targetPlayerId": req.targetPlayerId,
            "refunded": refund,
            "currentVotes": targetTally["votes"],
            "votesFor": targetTally.get("votesFor", 0),
            "votesAgainst": targetTally.get("votesAgainst", 0),
            "threshold": threshold,
            "probability": round(probability, 3),
            "remainingBalance": currency.balance,
        })
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        logger.error(f"GM vote undo error: {e}")
        raise HTTPException(500, "Failed to withdraw vote")
    finally:
        session.close()


@app.get("/api/gm/team/{teamId}/summary")
def get_gm_team_summary(teamId: int, user: _User = Depends(_getCurrentUser)):
    """Get aggregated GM vote tallies for a team this season."""
    from database.connection import get_session
    from database.repositories.gm_repository import GmVoteRepository
    from managers.gmManager import GmManager

    session = get_session()
    try:
        sm = floosball_app.seasonManager if floosball_app else None
        currentSeason = sm.currentSeason.seasonNumber if sm and sm.currentSeason else 0
        voteRepo = GmVoteRepository(session)
        tallies = voteRepo.getVoteTallies(teamId, currentSeason)

        engagedFans = voteRepo.getEngagedVoterCount(teamId, currentSeason)

        # Enrich with threshold/probability
        gm = GmManager(session)
        # Hire-coach is plurality-wins. Display threshold + probability so
        # the meter shows: sole leader at 100% ("Will pass"), tied leaders
        # at <100% (no "Will pass" until tie breaks), trailing at fraction
        # of leader. Tie detection lives in hireCoachDisplay.
        hireVoteCounts = [
            t["votes"] for t in tallies
            if t["voteType"] == "hire_coach" and t.get("targetPlayerId")
        ]
        hireLeaderVotes = max(hireVoteCounts) if hireVoteCounts else 0
        hireLeaderCount = (
            sum(1 for v in hireVoteCounts if v == hireLeaderVotes)
            if hireLeaderVotes > 0 else 0
        )
        # Threshold for fire/resign/cut: votes must meet or exceed the
        # team's active fan count (favorite_team_id == teamId AND logged
        # in this season).
        teamFanCount = voteRepo.getTeamFanCount(teamId, season=currentSeason)
        majorityThreshold = gm.calculateThreshold(teamFanCount)
        enriched = []
        for t in tallies:
            if t["voteType"] == "hire_coach":
                threshold, probability = gm.hireCoachDisplay(
                    t["votes"], hireLeaderVotes, hireLeaderCount
                )
            elif t["voteType"] == "sign_fa":
                threshold = gm.calculateBallotThreshold(engagedFans)
                probability = gm.calculateProbability(t["votes"], threshold)
            else:
                threshold = majorityThreshold
                probability = gm.calculateProbability(t["votes"], threshold)
            enriched.append({
                **t,
                "threshold": threshold,
                "probability": round(probability, 3),
            })

        return build_success_response({
            "teamId": teamId,
            "season": currentSeason,
            "tallies": enriched,
        })
    finally:
        session.close()


@app.get("/api/gm/team/{teamId}/eligible")
def get_gm_eligible_targets(teamId: int, user: _User = Depends(_getCurrentUser)):
    """Get eligible targets per vote type for a team."""
    from database.connection import get_session
    from database.models import Player, Coach

    session = get_session()
    try:
        # Coach info
        sm = floosball_app.seasonManager if floosball_app else None
        teamManager = floosball_app.serviceContainer.getService('team_manager') if floosball_app else None
        team = None
        if teamManager:
            for t in teamManager.teams:
                if t.id == teamId:
                    team = t
                    break

        coachInfo = None
        if team and team.coach:
            c = team.coach
            coachInfo = {
                "id": getattr(c, 'id', None),
                "name": c.name,
                "overallRating": c.overallRating,
                "offensiveMind": c.offensiveMind,
                "defensiveMind": c.defensiveMind,
                "adaptability": c.adaptability,
                "aggressiveness": c.aggressiveness,
                "clockManagement": c.clockManagement,
                "playerDevelopment": c.playerDevelopment,
                "scouting": getattr(c, 'scouting', 80),
                "attitude": getattr(c, 'attitude', 80),
            }

        # Per-team coach candidates (per-team hiring rework).
        # Candidates are pre-generated for every team at FA window open so
        # users can vote on them during the same window as the fire vote.
        # If FA hasn't opened yet (pre-week-22), the read returns whatever
        # exists — typically empty until the front office opens.
        from database.models import CoachCandidate
        coachCandidates = []
        if team and teamManager is not None and sm and sm.currentSeason:
            try:
                cands = (
                    session.query(CoachCandidate)
                    .filter(
                        CoachCandidate.team_id == team.id,
                        CoachCandidate.season == sm.currentSeason.seasonNumber,
                    )
                    .order_by(CoachCandidate.slot.asc())
                    .all()
                )
            except Exception as e:
                logger.warning(f"Coach candidate fetch failed for team {teamId}: {e}")
                cands = []
            for cand in cands:
                c = cand.coach
                if c is None:
                    continue
                coachCandidates.append({
                    "id": c.id,
                    "slot": cand.slot,
                    "name": c.name,
                    "overallRating": c.overall_rating,
                    "offensiveMind": c.offensive_mind,
                    "defensiveMind": c.defensive_mind,
                    "adaptability": c.adaptability,
                    "aggressiveness": c.aggressiveness,
                    "clockManagement": c.clock_management,
                    "playerDevelopment": c.player_development,
                    "scouting": getattr(c, 'scouting', 80),
                    "attitude": getattr(c, 'attitude', 80),
                })

        # Rostered players (for cut votes — all players eligible)
        from floosball_player import Position as _Pos
        rosteredPlayers = []
        players = session.query(Player).filter_by(team_id=teamId).all()
        for p in players:
            try:
                posLabel = _Pos(p.position).name
            except (ValueError, KeyError):
                posLabel = str(p.position)
            rosteredPlayers.append({
                "id": p.id,
                "name": p.name,
                "position": posLabel,
                "rating": p.player_rating,
                "tier": p.tier,
                "termRemaining": p.term_remaining,
                "willRetire": bool(getattr(p, 'will_retire', False)),
            })

        # Expiring contract players that haven't announced retirement —
        # those are the only ones eligible for a resign vote.
        expiringPlayers = [
            p for p in rosteredPlayers
            if p["termRemaining"] == 1 and not p["willRetire"]
        ]
        retiringPlayers = [p for p in rosteredPlayers if p["willRetire"]]

        return build_success_response({
            "teamId": teamId,
            "coach": coachInfo,
            "coachCandidates": coachCandidates,
            "rosteredPlayers": rosteredPlayers,
            "expiringPlayers": expiringPlayers,
            "retiringPlayers": retiringPlayers,
        })
    finally:
        session.close()


@app.get("/api/gm/fa-scouting")
def get_fa_scouting(user: _User = Depends(_getCurrentUser)):
    """Get FA pool with scouting data (stats, over/underperformance) and user's team open positions."""
    from database.connection import get_session
    from database.models import PlayerSeasonStats, User

    if floosball_app is None:
        raise HTTPException(503, "Application not initialized")

    sm = floosball_app.seasonManager
    pm = floosball_app.playerManager

    session = get_session()
    try:
        dbUser = session.query(User).filter_by(id=user.id).first()
        if not dbUser or not dbUser.favorite_team_id:
            raise HTTPException(400, "You must have a favorite team")

        # Find user's favorite team and its open roster slots
        teamManager = floosball_app.serviceContainer.getService('team_manager')
        favTeam = None
        for t in teamManager.teams:
            if t.id == dbUser.favorite_team_id:
                favTeam = t
                break

        # Build GM vote tallies so we can factor cut/resign sentiment into the
        # "projected open slots" and "projected FA pool" calculations. A player
        # with enough cut_player votes to meet quorum is likely leaving even
        # if not in their walk year. A walk-year player with enough
        # resign_player votes to meet quorum is likely staying.
        from database.models import GmVote
        from sqlalchemy import func as _func
        from managers.gmManager import GmManager as _GmManager
        _gm = _GmManager(session)

        seasonNum = sm.currentSeason.seasonNumber if sm and sm.currentSeason else 1

        # Vote tallies per (team_id, vote_type, target_player_id)
        voteRows = session.query(
            GmVote.team_id, GmVote.vote_type, GmVote.target_player_id,
            _func.count(GmVote.id).label('n'),
        ).filter(
            GmVote.season == seasonNum,
            GmVote.vote_type.in_(['cut_player', 'resign_player']),
        ).group_by(GmVote.team_id, GmVote.vote_type, GmVote.target_player_id).all()

        # {(teamId, voteType, targetPlayerId): voteCount}
        voteTally: Dict[tuple, int] = {
            (r.team_id, r.vote_type, r.target_player_id): r.n
            for r in voteRows
        }

        # Engaged-fan count per team for threshold calc
        engagedPerTeam: Dict[int, int] = {}
        engagedRows = session.query(
            User.favorite_team_id,
            _func.count(_func.distinct(GmVote.user_id)).label('n'),
        ).join(GmVote, GmVote.user_id == User.id).filter(
            GmVote.season == seasonNum,
            User.favorite_team_id.isnot(None),
        ).group_by(User.favorite_team_id).all()
        for r in engagedRows:
            engagedPerTeam[r.favorite_team_id] = r.n

        def likelyCut(teamId: int, playerId: int) -> bool:
            votes = voteTally.get((teamId, 'cut_player', playerId), 0)
            if votes == 0: return False
            threshold = _gm.calculateThreshold(engagedPerTeam.get(teamId, 0), 'cut_player')
            return votes >= threshold

        def likelyResigned(teamId: int, playerId: int) -> bool:
            votes = voteTally.get((teamId, 'resign_player', playerId), 0)
            if votes == 0: return False
            threshold = _gm.calculateThreshold(engagedPerTeam.get(teamId, 0), 'resign_player')
            return votes >= threshold

        openSlots = []
        slotPosMap = {'qb': 'QB', 'rb': 'RB', 'wr1': 'WR', 'wr2': 'WR', 'te': 'TE', 'k': 'K'}
        if favTeam:
            for slot, posName in slotPosMap.items():
                rosterPlayer = favTeam.rosterDict.get(slot)
                if rosterPlayer is None:
                    # Slot is actually open right now
                    openSlots.append({"slot": slot, "position": posName, "projected": False, "reason": "vacant"})
                    continue

                termRem = getattr(rosterPlayer, 'termRemaining', 99)
                cutLikely = likelyCut(favTeam.id, rosterPlayer.id)
                resignLikely = likelyResigned(favTeam.id, rosterPlayer.id)
                # Retirement risk — an aging veteran projected to retire at
                # season end creates an opening even with multi-year contract.
                retireRisk = pm.computeRetirementRisk(rosterPlayer)
                retireLikely = retireRisk in ('retiring', 'very_likely', 'likely')

                # Slot opens if ANY of: cut-vote at quorum, walk-year without
                # resign backing, or high retirement risk.
                if cutLikely:
                    openSlots.append({
                        "slot": slot, "position": posName, "projected": True,
                        "reason": "cut_vote_likely",
                        "incumbent": {
                            "id": rosterPlayer.id, "name": rosterPlayer.name,
                            "rating": round(rosterPlayer.playerRating, 1),
                            "termRemaining": termRem,
                        },
                    })
                elif termRem <= 1 and not resignLikely:
                    openSlots.append({
                        "slot": slot, "position": posName, "projected": True,
                        "reason": "walk_year",
                        "incumbent": {
                            "id": rosterPlayer.id, "name": rosterPlayer.name,
                            "rating": round(rosterPlayer.playerRating, 1),
                            "termRemaining": termRem,
                        },
                    })
                elif retireLikely:
                    openSlots.append({
                        "slot": slot, "position": posName, "projected": True,
                        "reason": "retirement_risk",
                        "incumbent": {
                            "id": rosterPlayer.id, "name": rosterPlayer.name,
                            "rating": round(rosterPlayer.playerRating, 1),
                            "termRemaining": termRem,
                            "retirementRisk": retireRisk,
                        },
                    })
                # else: slot stays filled — safe contract, no cut/retire pressure

        # seasonNum was computed above alongside the vote tallies

        # Build stats lookup for all FA player IDs
        faPlayerIds = [p.id for p in pm.freeAgents]
        statsRows = {}
        rookieIds = set()
        if faPlayerIds:
            rows = session.query(PlayerSeasonStats).filter(
                PlayerSeasonStats.player_id.in_(faPlayerIds),
                PlayerSeasonStats.season == seasonNum,
            ).all()
            for r in rows:
                statsRows[r.player_id] = r
            # Players with zero season stats rows across all seasons are rookies
            playersWithStats = set(
                r[0] for r in session.query(PlayerSeasonStats.player_id).filter(
                    PlayerSeasonStats.player_id.in_(faPlayerIds)
                ).distinct().all()
            )
            rookieIds = set(faPlayerIds) - playersWithStats

        def formatStats(row, posName):
            # Rows with zero games played = player was on the books but never
            # saw the field (FA who sat out, injured, buried on depth chart).
            # Treat these as no-stats so the UI falls through to the
            # "No stats this season" label instead of rendering a line of 0s.
            if not row or (getattr(row, 'games_played', 0) or 0) == 0:
                return None
            base = {"gamesPlayed": row.games_played, "fantasyPoints": row.fantasy_points}
            if posName == 'QB':
                base.update({"passingYards": row.passing_yards, "passingTds": row.passing_tds, "passingInts": row.passing_ints})
            elif posName == 'RB':
                base.update({"rushingYards": row.rushing_yards, "rushingTds": row.rushing_tds})
            elif posName in ('WR', 'TE'):
                base.update({"receivingYards": row.receiving_yards, "receivingTds": row.receiving_tds, "receptions": row.receptions})
            elif posName == 'K':
                ks = row.kicking_stats or {}
                base.update({"fgMade": ks.get('fgs', 0), "fgAttempted": ks.get('fgAtt', 0), "fgPct": round(ks.get('fgPerc', 0), 1)})
            return base

        # Mental snapshot helper — attitude + mood + key intangibles for
        # the ballot row. Users care about toxicity (attitude) and
        # current state (mood) when deciding who to sign; resilience and
        # pressure-handling matter on the margin. Skips missing fields
        # so generated rookies/prospects without personalities don't break.
        def _mental(pl):
            attrs = getattr(pl, 'attributes', None)
            if attrs is None:
                return {}
            out = {}
            att = getattr(attrs, 'attitude', None)
            if att is not None:
                out['attitude'] = int(att)
            personality = getattr(attrs, 'personality', None)
            if personality and hasattr(attrs, 'getMood'):
                try:
                    moodLabel, moodTier = attrs.getMood()
                    out['mood'] = moodLabel
                    out['moodTier'] = moodTier
                except Exception:
                    pass
            res = getattr(attrs, 'resilience', None)
            if res is not None:
                out['resilience'] = int(res)
            ph = getattr(attrs, 'pressureHandling', None)
            if ph is not None:
                out['pressureHandling'] = int(ph)
            return out

        players = []
        # Track emitted player IDs so the same player doesn't appear in
        # multiple categories (FA + projected FA, or rostered + prospects)
        # if underlying state is inconsistent. Frontend dedups too but we
        # want a clean feed regardless.
        seenPlayerIds: set = set()
        for p in pm.freeAgents:
            if p.id in seenPlayerIds:
                continue
            seenPlayerIds.add(p.id)
            posName = p.position.name
            row = statsRows.get(p.id)
            perfRating = getattr(p, 'seasonPerformanceRating', 0) or 0
            overallRating = round(p.playerRating)
            players.append({
                "id": p.id,
                "name": p.name,
                "position": posName,
                "rating": round(p.playerRating, 1),
                "tier": p.playerTier.name,
                "performanceRating": perfRating,
                "ratingDelta": perfRating - overallRating,
                "stats": formatStats(row, posName),
                "isRookie": p.id in rookieIds,
                "isProspect": False,
                "isProjected": False,
                **_mental(p),
            })

        # Projected FAs: rostered players on OTHER teams whose contracts are
        # ending OR who have enough cut votes to likely be cut. Walk-year
        # players whose board is likely to re-sign them are excluded — they
        # probably won't hit FA.
        def isProjectedFa(teamId: int, rp) -> tuple:
            """Returns (include, reason) — include=True means put them in the pool.
            reason is 'walk_year' or 'cut_vote' for UI context.
            """
            termRem = getattr(rp, 'termRemaining', 99)
            pid = rp.id
            if likelyCut(teamId, pid):
                return (True, 'cut_vote')
            if termRem <= 1 and not likelyResigned(teamId, pid):
                return (True, 'walk_year')
            return (False, None)

        if teamManager:
            # Pre-collect eligible projected IDs so we can batch-fetch stats
            projectedEntries = []  # (team, rp, reason)
            for team in teamManager.teams:
                if favTeam and team.id == favTeam.id:
                    continue  # Fans can't draft their own roster
                for pos, rp in team.rosterDict.items():
                    if rp is None:
                        continue
                    include, reason = isProjectedFa(team.id, rp)
                    if include:
                        projectedEntries.append((team, rp, reason))

            projStatsRows = {}
            if projectedEntries:
                projIds = [rp.id for _t, rp, _r in projectedEntries]
                rows = session.query(PlayerSeasonStats).filter(
                    PlayerSeasonStats.player_id.in_(projIds),
                    PlayerSeasonStats.season == seasonNum,
                ).all()
                for r in rows:
                    projStatsRows[r.player_id] = r

            for team, rp, reason in projectedEntries:
                if rp.id in seenPlayerIds:
                    continue
                seenPlayerIds.add(rp.id)
                posName = rp.position.name
                perfRating = getattr(rp, 'seasonPerformanceRating', 0) or 0
                overallRating = round(rp.playerRating)
                players.append({
                    "id": rp.id,
                    "name": rp.name,
                    "position": posName,
                    "rating": round(rp.playerRating, 1),
                    "tier": rp.playerTier.name,
                    "performanceRating": perfRating,
                    "ratingDelta": perfRating - overallRating,
                    "stats": formatStats(projStatsRows.get(rp.id), posName),
                    "isRookie": False,
                    "isProspect": False,
                    "isProjected": True,
                    "projectedReason": reason,  # 'walk_year' or 'cut_vote'
                    "currentTeam": team.abbr,
                    **_mental(rp),
                })

        # Include the favorite team's prospects as ballot candidates too, so fans
        # can rank "promote this prospect" alongside "sign this FA" in a single
        # ranked vote. Resolution treats prospect IDs as promote directives, FA
        # IDs as sign directives. Both share the same ranked-choice space.
        if favTeam:
            for p in getattr(favTeam, 'prospects', []):
                if p.id in seenPlayerIds:
                    continue
                seenPlayerIds.add(p.id)
                posName = p.position.name
                perfRating = getattr(p, 'seasonPerformanceRating', 0) or 0
                overallRating = round(p.playerRating)
                players.append({
                    "id": p.id,
                    "name": p.name,
                    "position": posName,
                    "rating": round(p.playerRating, 1),
                    "tier": p.playerTier.name,
                    "performanceRating": perfRating,
                    "ratingDelta": perfRating - overallRating,
                    "stats": None,  # prospects haven't played — no season stats
                    "isRookie": False,
                    "isProspect": True,
                    **_mental(p),
                })

        # Live ballot tally — runs the same instant-runoff (IRV) tally the
        # offseason resolver uses, so the order shown matches the order the
        # FA draft would actually pull. With one ballot, IRV produces that
        # ballot's exact ranking. With multiple, it resolves through
        # elimination rounds — a candidate who's nobody's #1 still climbs
        # if they're consistently ranked high.
        from database.repositories.gm_repository import GmFaBallotRepository
        from managers.gmManager import GmManager
        ballotRepo = GmFaBallotRepository(session)
        ballots = ballotRepo.getRankingsForTeam(favTeam.id, seasonNum) if favTeam else []

        mentionCount: Dict[int, int] = {}
        firstChoiceCount: Dict[int, int] = {}
        for ballot in ballots:
            for rank, pid in enumerate(ballot):
                mentionCount[pid] = mentionCount.get(pid, 0) + 1
                if rank == 0:
                    firstChoiceCount[pid] = firstChoiceCount.get(pid, 0) + 1

        # Build candidate lookup. Ballots can rank:
        #   - current FAs (pm.freeAgents)
        #   - fan team's prospects (pipeline promotions)
        #   - projected FAs from OTHER teams (walk-year / cut-vote candidates
        #     who are still rostered). Must sweep every team's roster +
        #     prospect pool so these IDs resolve, otherwise whole positions
        #     silently drop out of the tally.
        playerLookup = {p.id: p for p in pm.freeAgents}
        if teamManager:
            for t in teamManager.teams:
                for p in getattr(t, 'prospects', []):
                    playerLookup[p.id] = p
                for _slot, p in t.rosterDict.items():
                    if p is not None:
                        playerLookup[p.id] = p

        # Eligible candidates for the IRV: every player at an open position
        # (open right now OR projected to open). Mirrors the resolver's
        # eligibility logic so the live tally matches what would resolve.
        POS_NAME_TO_VAL = {'QB': 1, 'RB': 2, 'WR': 3, 'TE': 4, 'K': 5}
        openPosVals = {POS_NAME_TO_VAL[s['position']] for s in openSlots
                       if s.get('position') in POS_NAME_TO_VAL}
        eligibleCandidates: set = set()
        for pid, p in playerLookup.items():
            posVal = getattr(getattr(p, 'position', None), 'value', None)
            if posVal in openPosVals:
                eligibleCandidates.add(pid)

        gmTally = GmManager(session)
        rankedIds = gmTally._tallyFullRankingOverall(ballots, eligibleCandidates)

        ballotTally: List[Dict] = []
        for pid in rankedIds:
            p = playerLookup.get(pid)
            if not p:
                continue
            ballotTally.append({
                "id": p.id,
                "name": p.name,
                "position": p.position.name,
                "rating": round(getattr(p, 'playerRating', 0), 1),
                "votes": mentionCount.get(pid, 0),
                "firstChoice": firstChoiceCount.get(pid, 0),
                "isProspect": bool(getattr(p, 'is_prospect', False)),
            })

        return build_success_response({
            "openSlots": openSlots,
            "players": players,
            "ballotTally": ballotTally,
            "totalBallots": len(ballots),
        })
    finally:
        session.close()


@app.post("/api/gm/fa-ballot")
def submit_fa_ballot(req: GmFaBallotRequest, user: _User = Depends(_getCurrentUser)):
    """Submit or update a ranked FA ballot during the voting window."""
    from database.connection import get_session
    from database.repositories.gm_repository import GmFaBallotRepository
    from database.repositories.card_repositories import CurrencyRepository
    from database.models import User
    from constants import GM_FA_BALLOT_COST, GM_FA_BALLOT_MAX_RANKINGS

    if not req.rankings or len(req.rankings) > GM_FA_BALLOT_MAX_RANKINGS:
        raise HTTPException(400, f"Provide 1-{GM_FA_BALLOT_MAX_RANKINGS} ranked player IDs")

    session = get_session()
    try:
        dbUser = session.query(User).filter_by(id=user.id).first()
        if not dbUser or not dbUser.favorite_team_id:
            raise HTTPException(400, "You must have a favorite team to vote")

        teamId = dbUser.favorite_team_id
        sm = floosball_app.seasonManager if floosball_app else None
        currentSeason = sm.currentSeason.seasonNumber if sm and sm.currentSeason else 0

        # Accept ballots whenever the Board is convened: week 22+, the offseason
        # FA window, or any point during the offseason itself. Fans can draft
        # and revise a ranked list well before the offseason opens.
        from constants import GM_ACTIVE_WEEK
        faWindowOpen = getattr(sm, '_faWindowOpen', False) if sm else False
        currentWeek = sm.currentSeason.currentWeek if sm and sm.currentSeason else 0
        isOffseason = (sm.currentSeason.currentWeekText == 'Offseason') if sm and sm.currentSeason else False
        boardActive = currentWeek >= GM_ACTIVE_WEEK or isOffseason or faWindowOpen
        if not boardActive:
            raise HTTPException(400, f"FA requisitions open in Week {GM_ACTIVE_WEEK}")

        # Sanity-check: every ranked player ID must resolve to a known
        # candidate (FA, prospect, or rostered player). The frontend modal
        # already restricts the picker to candidates at open positions, so
        # this is mainly to keep stale or malformed submissions from
        # filling the ballot with unresolvable IDs that would silently
        # drop out at resolution time.
        pm = floosball_app.playerManager if floosball_app else None
        teamManager = floosball_app.serviceContainer.getService('team_manager') if floosball_app else None
        knownIds: set = set()
        if pm:
            knownIds.update(p.id for p in pm.freeAgents)
        if teamManager:
            for t in teamManager.teams:
                for p in getattr(t, 'prospects', []):
                    knownIds.add(p.id)
                for _slot, p in t.rosterDict.items():
                    if p is not None:
                        knownIds.add(p.id)
        cleanedRankings = [pid for pid in req.rankings if pid in knownIds]
        if not cleanedRankings:
            raise HTTPException(400, "No valid candidates in ballot")

        ballotRepo = GmFaBallotRepository(session)
        existing = ballotRepo.getUserBallot(user.id, teamId, currentSeason)

        costPaid = 0
        if not existing:
            # First submission — charge ballot cost
            currencyRepo = CurrencyRepository(session)
            result = currencyRepo.spendFunds(
                user.id, GM_FA_BALLOT_COST, "gm_fa_ballot",
                "GM FA ballot submission", currentSeason,
            )
            if result is None:
                raise HTTPException(400, "Insufficient Floobits")
            costPaid = GM_FA_BALLOT_COST

        ballot = ballotRepo.submitBallot(
            userId=user.id, teamId=teamId, season=currentSeason,
            rankings=cleanedRankings, costPaid=costPaid,
        )
        session.commit()

        return build_success_response({
            "ballotId": ballot.id,
            "rankings": cleanedRankings,
            "costPaid": costPaid,
            "isUpdate": existing is not None,
        })
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        logger.error(f"FA ballot error: {e}")
        raise HTTPException(500, "Failed to submit ballot")
    finally:
        session.close()


@app.get("/api/rookies/upcoming")
def get_upcoming_rookies(user: Optional[_User] = Depends(_getOptionalUser)):
    """The season's rookie class, with scouting-blurred potentials.

    Generated at season start, visible all season. Potentials are revealed
    according to the viewer's favorite team's effective scouting (coach
    scouting + funding tier bonus). Unauthenticated visitors get the widest
    blur band.
    """
    if floosball_app is None:
        raise HTTPException(503, "Application not initialized")
    from constants import FUNDING_SCOUTING_BONUS, GM_ACTIVE_WEEK
    pm = floosball_app.playerManager
    sm = floosball_app.seasonManager
    tm = floosball_app.teamManager

    upcoming = [p for p in pm.activePlayers if getattr(p, 'is_upcoming_rookie', False)]

    # Determine viewer's effective scouting
    effectiveScouting = 60  # default: worst-band blur
    scoutTeam = None
    if user and getattr(user, 'favorite_team_id', None):
        scoutTeam = tm.getTeamById(user.favorite_team_id) if tm else None
        if scoutTeam:
            coachScouting = getattr(getattr(scoutTeam, 'coach', None), 'scouting', 80) or 80
            tierBonus = FUNDING_SCOUTING_BONUS.get(getattr(scoutTeam, 'fundingTier', 'MID_MARKET'), 0)
            effectiveScouting = max(0, min(100, coachScouting + tierBonus))

    currentWeek = sm.currentSeason.currentWeek if sm and sm.currentSeason else 0
    seasonNumber = sm.currentSeason.seasonNumber if sm and sm.currentSeason else 0

    rookies = [pm.scoutRookie(r, effectiveScouting) for r in upcoming]
    rookies.sort(key=lambda r: (-r['rating'], r['position'], r['name']))

    # Voting window matches the submit endpoint exactly:
    #   Opens when Front Office opens (week >= GM_ACTIVE_WEEK) OR the season
    #   is complete (covers the 15+ hour post_bowl + frontoffice gap when
    #   currentWeek resets to 0 but the user can still legitimately vote).
    #   Closes the moment the rookie draft phase actually begins.
    # The previous gate of `currentWeek >= GM_ACTIVE_WEEK` alone silently
    # closed the UI at offseason start (currentWeek=0) even though the
    # backend submit would still accept ballots.
    flowPhase = getattr(sm, '_offseasonFlowPhase', None)
    seasonComplete = getattr(sm.currentSeason, 'isComplete', False) if sm and sm.currentSeason else False
    weekOpen = isinstance(currentWeek, int) and currentWeek >= GM_ACTIVE_WEEK
    draftStartedOrLater = flowPhase in ('rookie_draft', 'pre_fa', 'fa_draft', 'training')
    votingOpen = (seasonComplete or weekOpen) and not draftStartedOrLater

    return build_success_response({
        "season": seasonNumber,
        "currentWeek": currentWeek,
        "votingOpensWeek": GM_ACTIVE_WEEK,
        "votingOpen": votingOpen,
        "effectiveScouting": effectiveScouting,
        "scoutingTeamId": scoutTeam.id if scoutTeam else None,
        "rookies": rookies,
    })


class RookieBallotRequest(BaseModel):
    rankings: List[int]


@app.post("/api/gm/rookie-ballot")
def submit_rookie_ballot(req: RookieBallotRequest, user: _User = Depends(_getCurrentUser)):
    """Submit or update a ranked rookie-draft ballot.

    Window: opens when the Front Office opens (week >= GM_ACTIVE_WEEK) and
    closes when the regular season ends (start of offseason). Flat
    GM_ROOKIE_BALLOT_COST — first submission charges once; updates are free.
    """
    import json as _json
    from database.connection import get_session
    from database.models import User, GmVote
    from database.repositories.card_repositories import CurrencyRepository
    from constants import GM_ROOKIE_BALLOT_COST, GM_ROOKIE_DRAFT_MAX_RANKINGS, GM_ACTIVE_WEEK

    if floosball_app is None:
        raise HTTPException(503, "Application not initialized")
    sm = floosball_app.seasonManager

    if not req.rankings:
        raise HTTPException(400, "Provide at least one ranked rookie ID")
    if len(req.rankings) > GM_ROOKIE_DRAFT_MAX_RANKINGS:
        raise HTTPException(400, f"Max {GM_ROOKIE_DRAFT_MAX_RANKINGS} rookies per ballot")

    # Gate: Front Office opens at GM_ACTIVE_WEEK. Voting stays open through
    # playoffs, the post-bowl quiet, the front-office phase, AND the long
    # noon-ET wait — fans can revise their ballots up until the moment the
    # rookie draft actually kicks off. The flow phase is the canonical signal:
    # closed once we hit rookie_draft or any later phase (pre_fa, fa_draft,
    # training). Pre-flow weeks (regular season Week 22+) are still gated by
    # week number alone since the flow phase isn't set yet.
    currentWeek = sm.currentSeason.currentWeek if sm and sm.currentSeason else 0
    flowPhase = getattr(sm, '_offseasonFlowPhase', None)
    seasonComplete = getattr(sm.currentSeason, 'isComplete', False) if sm and sm.currentSeason else False
    # Pre-offseason gate: must be ≥ Week 22 unless we're already past playoffs
    if not seasonComplete and (not isinstance(currentWeek, int) or currentWeek < GM_ACTIVE_WEEK):
        raise HTTPException(400, f"Rookie draft voting opens in Week {GM_ACTIVE_WEEK}")
    if flowPhase in ('rookie_draft', 'pre_fa', 'fa_draft', 'training'):
        raise HTTPException(400, "Rookie draft voting is closed; the draft is underway")

    session = get_session()
    try:
        dbUser = session.query(User).filter_by(id=user.id).first()
        if not dbUser or not dbUser.favorite_team_id:
            raise HTTPException(400, "You must have a favorite team to vote")

        teamId = dbUser.favorite_team_id
        currentSeason = sm.currentSeason.seasonNumber if sm and sm.currentSeason else 0

        # Validate that every ID in rankings is an actual upcoming rookie
        pm = floosball_app.playerManager
        upcomingIds = {p.id for p in pm.activePlayers if getattr(p, 'is_upcoming_rookie', False)}
        rankings = [int(r) for r in req.rankings if int(r) in upcomingIds]
        if not rankings:
            raise HTTPException(400, "None of the submitted IDs are upcoming rookies")

        # Upsert: one draft_rookie vote per user per season
        existing = session.query(GmVote).filter_by(
            user_id=user.id, team_id=teamId, season=currentSeason,
            vote_type='draft_rookie',
        ).first()

        costPaid = 0
        if existing is None:
            currencyRepo = CurrencyRepository(session)
            result = currencyRepo.spendFunds(
                user.id, GM_ROOKIE_BALLOT_COST, "gm_rookie_ballot",
                "Rookie draft ballot", currentSeason,
            )
            if result is None:
                raise HTTPException(400, "Insufficient Floobits")
            costPaid = GM_ROOKIE_BALLOT_COST
            vote = GmVote(
                user_id=user.id, team_id=teamId, season=currentSeason,
                vote_type='draft_rookie', cost_paid=costPaid,
                details=_json.dumps(rankings),
            )
            session.add(vote)
        else:
            existing.details = _json.dumps(rankings)
        session.commit()

        return build_success_response({
            "rankings": rankings,
            "costPaid": costPaid,
            "isUpdate": existing is not None,
        })
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        logger.error(f"Rookie ballot error: {e}")
        raise HTTPException(500, "Failed to submit rookie ballot")
    finally:
        session.close()


@app.get("/api/gm/rookie-ballot")
def get_my_rookie_ballot(user: _User = Depends(_getCurrentUser)):
    """Return the user's current rookie-draft ballot for this season.

    Includes enriched ranked-player info (name, position, rating, draftedBy)
    so the Front Office page can show how each ballot pick resolved without
    extra client-side lookups. After the rookie draft has happened, ranked
    players have an `is_prospect=True` flag and a `drafting_team_id` —
    those drive the `draftedByTeamAbbr` field below.
    """
    import json as _json
    from database.connection import get_session
    from database.models import User, GmVote

    if floosball_app is None:
        raise HTTPException(503, "Application not initialized")
    sm = floosball_app.seasonManager
    pm = floosball_app.playerManager
    tm = floosball_app.teamManager

    session = get_session()
    try:
        dbUser = session.query(User).filter_by(id=user.id).first()
        teamId = dbUser.favorite_team_id if dbUser else None
        currentSeason = sm.currentSeason.seasonNumber if sm and sm.currentSeason else 0
        if not teamId:
            return build_success_response({"rankings": [], "hasBallot": False, "rankedPlayers": []})

        existing = session.query(GmVote).filter_by(
            user_id=user.id, team_id=teamId, season=currentSeason,
            vote_type='draft_rookie',
        ).first()

        rankings: List[int] = []
        if existing and existing.details:
            try:
                parsed = _json.loads(existing.details)
                if isinstance(parsed, list):
                    rankings = [int(x) for x in parsed if isinstance(x, (int, str)) and str(x).lstrip('-').isdigit()]
            except Exception:
                pass

        # Enrich each ranked player with current state (drafted by which team,
        # rating, position). Pre-draft they're still upcoming rookies; post-
        # draft they've been promoted to prospects on a team's pipeline.
        rankedPlayers = []
        playerLookup = {p.id: p for p in pm.activePlayers}
        for pid in rankings:
            p = playerLookup.get(pid)
            if not p:
                continue
            draftingTeamId = getattr(p, 'drafting_team_id', None)
            draftingAbbr = None
            if draftingTeamId and tm:
                t = tm.getTeamById(draftingTeamId)
                if t:
                    draftingAbbr = getattr(t, 'abbr', None)
            rankedPlayers.append({
                "id": p.id,
                "name": p.name,
                "position": p.position.name,
                "rating": round(getattr(p, 'playerRating', 0), 1),
                "tier": getattr(p, 'playerTier', None).name if getattr(p, 'playerTier', None) else None,
                "draftedByTeamId": draftingTeamId,
                "draftedByTeamAbbr": draftingAbbr,
                "isStillUpcoming": bool(getattr(p, 'is_upcoming_rookie', False)),
            })

        return build_success_response({
            "rankings": rankings,
            "hasBallot": existing is not None,
            "rankedPlayers": rankedPlayers,
        })
    finally:
        session.close()


@app.get("/api/gm/votes")
def get_my_gm_votes(user: _User = Depends(_getCurrentUser)):
    """Get current user's GM votes this season."""
    from database.connection import get_session
    from database.repositories.gm_repository import GmVoteRepository

    session = get_session()
    try:
        sm = floosball_app.seasonManager if floosball_app else None
        currentSeason = sm.currentSeason.seasonNumber if sm and sm.currentSeason else 0
        voteRepo = GmVoteRepository(session)
        votes = voteRepo.getUserVotes(user.id, currentSeason)
        counts = voteRepo.getUserVoteCounts(user.id, currentSeason)

        return build_success_response({
            "season": currentSeason,
            "votes": [
                {
                    "id": v.id,
                    "voteType": v.vote_type,
                    "targetPlayerId": v.target_player_id,
                    "direction": getattr(v, 'direction', 'yea') or 'yea',
                    "costPaid": v.cost_paid,
                    "createdAt": v.created_at.isoformat() + 'Z' if v.created_at else None,
                }
                for v in votes
            ],
            "counts": counts,
        })
    finally:
        session.close()


@app.get("/api/gm/results")
def get_gm_results(user: _User = Depends(_getCurrentUser)):
    """Get GM vote resolution results for user's favorite team."""
    import json as _json
    from database.connection import get_session
    from database.repositories.gm_repository import GmVoteRepository
    from database.models import User, Player, Coach

    session = get_session()
    try:
        dbUser = session.query(User).filter_by(id=user.id).first()
        if not dbUser or not dbUser.favorite_team_id:
            return build_success_response({"results": []})

        sm = floosball_app.seasonManager if floosball_app else None
        currentSeason = sm.currentSeason.seasonNumber if sm and sm.currentSeason else 0
        voteRepo = GmVoteRepository(session)
        results = voteRepo.getResults(dbUser.favorite_team_id, currentSeason)

        # Collect referenced player / coach IDs so we can resolve display names in two batched queries.
        # target_player_id stores a Player.id for cut_player/resign_player and a Coach.id for hire_coach.
        # sign_fa rows have no target_player_id but stash a list of player IDs in details.directives.
        playerIds: set[int] = set()
        coachIds: set[int] = set()
        for r in results:
            if r.vote_type == "hire_coach" and r.target_player_id:
                coachIds.add(r.target_player_id)
            elif r.target_player_id:
                playerIds.add(r.target_player_id)
            if r.vote_type == "sign_fa" and r.details:
                try:
                    d = _json.loads(r.details)
                    for pid in d.get("directives") or []:
                        if isinstance(pid, int):
                            playerIds.add(pid)
                except Exception:
                    pass

        playerNames: Dict[int, str] = {}
        if playerIds:
            for p in session.query(Player.id, Player.name).filter(Player.id.in_(playerIds)).all():
                playerNames[p.id] = p.name
        coachNames: Dict[int, str] = {}
        if coachIds:
            for c in session.query(Coach.id, Coach.name).filter(Coach.id.in_(coachIds)).all():
                coachNames[c.id] = c.name

        payload = []
        for r in results:
            # Resolve the primary target name based on vote type.
            targetName: Optional[str] = None
            if r.vote_type == "hire_coach" and r.target_player_id:
                targetName = coachNames.get(r.target_player_id)
            elif r.target_player_id:
                targetName = playerNames.get(r.target_player_id)

            # sign_fa: expand directives (ordered list of player IDs) into ordered names.
            directiveNames: List[str] = []
            if r.vote_type == "sign_fa" and r.details:
                try:
                    d = _json.loads(r.details)
                    for pid in d.get("directives") or []:
                        nm = playerNames.get(pid)
                        if nm:
                            directiveNames.append(nm)
                except Exception:
                    pass

            payload.append({
                "id": r.id,
                "voteType": r.vote_type,
                "targetPlayerId": r.target_player_id,
                "targetName": targetName,
                "directiveNames": directiveNames,
                "totalVotes": r.total_votes,
                "threshold": r.threshold,
                "probability": r.success_probability,
                "outcome": r.outcome,
                "details": r.details,
                "resolvedAt": r.resolved_at.isoformat() + 'Z' if r.resolved_at else None,
            })

        return build_success_response({
            "teamId": dbUser.favorite_team_id,
            "season": currentSeason,
            "results": payload,
        })
    finally:
        session.close()


# ============================================================================
# PICK-EM ("PROGNOSTICATIONS")
# ============================================================================


@app.get("/api/pickem/week")
def get_pickem_week(response: Response, user: Optional[_User] = Depends(_getOptionalUser)):
    """Get this week's matchups with the user's existing picks (if any).
    Each game has per-game pickability and current multiplier based on quarter.
    """
    response.headers["Cache-Control"] = "public, max-age=10"
    if floosball_app is None:
        raise HTTPException(503, "Application not initialized")

    from constants import (PICKEM_QUARTER_MULTIPLIERS, calculateUnderdogMultiplier,
                           calculateCertaintyMultiplier, calculateWinProbMultiplier)

    sm = floosball_app.seasonManager
    currentSeason = sm.currentSeason
    if currentSeason is None:
        return build_success_response({"season": 0, "week": 0, "games": [], "weekSummary": None})

    seasonNum = currentSeason.seasonNumber
    week = sm._getPickemWeek()
    schedule = currentSeason.schedule
    playoffRound = getattr(currentSeason, 'currentPlayoffRound', None)

    # Build matchups — during playoffs use activeGames/completedWeekGames directly
    weekGames = []
    if playoffRound:
        displayGames = currentSeason.activeGames or currentSeason.completedWeekGames or []
        for i, liveGame in enumerate(displayGames):
            rawStatus = getattr(liveGame, 'status', None)
            statusVal = rawStatus.value if hasattr(rawStatus, 'value') else None

            homeElo = getattr(liveGame.homeTeam, 'elo', 1500)
            awayElo = getattr(liveGame.awayTeam, 'elo', 1500)

            if statusVal == 3:
                pickable = False
                currentMultiplier = 0.0
            elif statusVal == 2:
                pickable = True
                quarter = getattr(liveGame, 'currentQuarter', 1)
                homeWinProb = getattr(liveGame, 'homeTeamWinProbability', 50.0) or 50.0
                currentMultiplier = calculateCertaintyMultiplier(quarter, homeWinProb)
            else:
                pickable = True
                currentMultiplier = PICKEM_QUARTER_MULTIPLIERS.get(0, 1.0)

            # Win-prob multiplier info: use live win prob for active, ELO for pre-game
            if statusVal == 2:
                liveWp = (getattr(liveGame, 'homeTeamWinProbability', 50.0) or 50.0) / 100.0
                underdogInfo = {
                    "homeMultiplier": calculateWinProbMultiplier(liveWp),
                    "awayMultiplier": calculateWinProbMultiplier(1.0 - liveWp),
                }
            else:
                underdogInfo = {
                    "homeMultiplier": calculateUnderdogMultiplier(homeElo, awayElo, True),
                    "awayMultiplier": calculateUnderdogMultiplier(homeElo, awayElo, False),
                }

            matchup = {
                "gameIndex": i,
                "homeTeam": {
                    "id": liveGame.homeTeam.id,
                    "name": liveGame.homeTeam.name,
                    "abbr": liveGame.homeTeam.abbr,
                    "color": liveGame.homeTeam.color,
                    "record": f"{liveGame.homeTeam.seasonTeamStats.get('wins', 0)}-{liveGame.homeTeam.seasonTeamStats.get('losses', 0)}",
                    "elo": homeElo,
                },
                "awayTeam": {
                    "id": liveGame.awayTeam.id,
                    "name": liveGame.awayTeam.name,
                    "abbr": liveGame.awayTeam.abbr,
                    "color": liveGame.awayTeam.color,
                    "record": f"{liveGame.awayTeam.seasonTeamStats.get('wins', 0)}-{liveGame.awayTeam.seasonTeamStats.get('losses', 0)}",
                    "elo": awayElo,
                },
                "userPick": None,
                "pointsMultiplier": None,
                "underdogMultiplier": None,
                "pickable": pickable,
                "currentMultiplier": currentMultiplier,
                "underdogInfo": underdogInfo,
                "result": None,
            }
            if statusVal == 3 and getattr(liveGame, 'winningTeam', None):
                matchup["result"] = {"winnerId": liveGame.winningTeam.id}
            weekGames.append(matchup)
    elif isinstance(week, int) and 0 < week <= len(schedule):
        # Between weeks: show just-completed results instead of blank next-week matchups.
        # currentWeek still points at the completed week (advances at rollover),
        # so no adjustment needed — just use completedWeekGames for display.
        completedGames = currentSeason.completedWeekGames
        activeGames = currentSeason.activeGames

        scheduleGames = schedule[week - 1].get('games', [])
        for i, game in enumerate(scheduleGames):
            # Use active game object if available (has live status/quarter),
            # then completed games, then fall back to schedule object
            if activeGames and i < len(activeGames):
                liveGame = activeGames[i]
            elif completedGames and i < len(completedGames):
                liveGame = completedGames[i]
            else:
                liveGame = game
            rawStatus = getattr(liveGame, 'status', None)
            # Compare by enum value to avoid identity issues across module reloads
            statusVal = rawStatus.value if hasattr(rawStatus, 'value') else None

            homeElo = getattr(liveGame.homeTeam, 'elo', 1500)
            awayElo = getattr(liveGame.awayTeam, 'elo', 1500)

            # Determine per-game pickability and current multiplier
            if statusVal == 3:  # Final
                pickable = False
                currentMultiplier = 0.0
            elif statusVal == 2:  # Active
                pickable = True
                quarter = getattr(liveGame, 'currentQuarter', 1)
                homeWinProb = getattr(liveGame, 'homeTeamWinProbability', 50.0) or 50.0
                currentMultiplier = calculateCertaintyMultiplier(quarter, homeWinProb)
            else:
                # Scheduled (1) or not yet set
                pickable = True
                currentMultiplier = PICKEM_QUARTER_MULTIPLIERS.get(0, 1.0)

            # Win-prob multiplier info: use live win prob for active, ELO for pre-game
            if statusVal == 2:
                liveWp = (getattr(liveGame, 'homeTeamWinProbability', 50.0) or 50.0) / 100.0
                underdogInfo = {
                    "homeMultiplier": calculateWinProbMultiplier(liveWp),
                    "awayMultiplier": calculateWinProbMultiplier(1.0 - liveWp),
                }
            else:
                underdogInfo = {
                    "homeMultiplier": calculateUnderdogMultiplier(homeElo, awayElo, True),
                    "awayMultiplier": calculateUnderdogMultiplier(homeElo, awayElo, False),
                }

            matchup = {
                "gameIndex": i,
                "homeTeam": {
                    "id": liveGame.homeTeam.id,
                    "name": liveGame.homeTeam.name,
                    "abbr": liveGame.homeTeam.abbr,
                    "color": liveGame.homeTeam.color,
                    "record": f"{liveGame.homeTeam.seasonTeamStats.get('wins', 0)}-{liveGame.homeTeam.seasonTeamStats.get('losses', 0)}",
                    "elo": homeElo,
                },
                "awayTeam": {
                    "id": liveGame.awayTeam.id,
                    "name": liveGame.awayTeam.name,
                    "abbr": liveGame.awayTeam.abbr,
                    "color": liveGame.awayTeam.color,
                    "record": f"{liveGame.awayTeam.seasonTeamStats.get('wins', 0)}-{liveGame.awayTeam.seasonTeamStats.get('losses', 0)}",
                    "elo": awayElo,
                },
                "userPick": None,
                "pointsMultiplier": None,
                "underdogMultiplier": None,
                "pickable": pickable,
                "currentMultiplier": currentMultiplier,
                "underdogInfo": underdogInfo,
                "result": None,
            }
            # Attach result if game is final
            if statusVal == 3 and getattr(liveGame, 'winningTeam', None):
                matchup["result"] = {"winnerId": liveGame.winningTeam.id}
            weekGames.append(matchup)

    # Overlay user picks if authenticated
    weekSummary = None
    if user and weekGames:
        from database.connection import get_session
        from database.repositories.pickem_repository import PickEmRepository
        session = get_session()
        try:
            pickemRepo = PickEmRepository(session)
            picks = pickemRepo.getUserPicks(user.id, seasonNum, week)
            pickMap = {p.game_index: p for p in picks}
            correctCount = 0
            totalResolved = 0
            totalPoints = 0
            for g in weekGames:
                pick = pickMap.get(g["gameIndex"])
                if pick:
                    g["userPick"] = pick.picked_team_id
                    g["pointsMultiplier"] = pick.points_multiplier
                    g["underdogMultiplier"] = pick.underdog_multiplier
                    if pick.correct is not None:
                        g["result"] = g.get("result") or {}
                        g["result"]["correct"] = pick.correct
                        g["result"]["pointsEarned"] = pick.points_earned or 0
                        totalResolved += 1
                        totalPoints += pick.points_earned or 0
                        if pick.correct:
                            correctCount += 1
            if totalResolved > 0:
                from constants import PICKEM_CLAIRVOYANT_THRESHOLD
                weekSummary = {
                    "correct": correctCount,
                    "total": totalResolved,
                    "totalPoints": totalPoints,
                    "clairvoyant": totalPoints >= PICKEM_CLAIRVOYANT_THRESHOLD,
                }

        finally:
            session.close()

    weekText = currentSeason.currentWeekText if playoffRound else f'Week {week}'

    return build_success_response({
        "season": seasonNum,
        "week": week,
        "weekText": weekText,
        "games": weekGames,
        "weekSummary": weekSummary,
    })


@app.post("/api/pickem/pick")
def submit_pickem_pick(body: dict, user: _User = Depends(_getCurrentUser)):
    """Submit or update a single pick. Per-game pickability — games can be picked
    until they reach Final status. Multiplier is based on game quarter at pick time.
    """
    if floosball_app is None:
        raise HTTPException(503, "Application not initialized")

    from constants import (PICKEM_QUARTER_MULTIPLIERS, calculateUnderdogMultiplier,
                           calculateCertaintyMultiplier, calculateWinProbMultiplier)

    gameIndex = body.get("gameIndex")
    pickedTeamId = body.get("pickedTeamId")
    if gameIndex is None or pickedTeamId is None:
        raise HTTPException(400, "gameIndex and pickedTeamId required")

    sm = floosball_app.seasonManager
    currentSeason = sm.currentSeason
    if currentSeason is None:
        raise HTTPException(400, "No active season")

    seasonNum = currentSeason.seasonNumber
    week = sm._getPickemWeek()
    schedule = currentSeason.schedule
    playoffRound = getattr(currentSeason, 'currentPlayoffRound', None)

    # Determine the list of games for validation
    if playoffRound:
        displayGames = currentSeason.activeGames or currentSeason.completedWeekGames or []
        if gameIndex < 0 or gameIndex >= len(displayGames):
            raise HTTPException(400, f"Invalid gameIndex: {gameIndex}")
        liveGame = displayGames[gameIndex]
        totalGames = len(displayGames)
    else:
        # If current week is done, accept picks for next week
        if (currentSeason.completedWeekGames is not None
                and isinstance(week, int)
                and week + 1 <= len(schedule)):
            week = week + 1

        # Validate gameIndex
        if week < 1 or week > len(schedule):
            raise HTTPException(400, "No games this week")
        scheduleGames = schedule[week - 1].get('games', [])
        if gameIndex < 0 or gameIndex >= len(scheduleGames):
            raise HTTPException(400, f"Invalid gameIndex: {gameIndex}")

        game = scheduleGames[gameIndex]
        # Also check activeGames for live state
        activeGames = currentSeason.activeGames
        liveGame = activeGames[gameIndex] if activeGames and gameIndex < len(activeGames) else game
        totalGames = len(scheduleGames)

    # Per-game lock: only Final games are unpickable
    rawStatus = getattr(liveGame, 'status', None)
    statusVal = rawStatus.value if hasattr(rawStatus, 'value') else None
    if statusVal == 3:  # Final
        raise HTTPException(409, "This game has ended — pick cannot be changed")

    # Determine timing multiplier based on game quarter
    homeTeamId = liveGame.homeTeam.id
    awayTeamId = liveGame.awayTeam.id
    isPreGame = (statusVal != 2)

    if statusVal == 2:  # Active
        quarter = getattr(liveGame, 'currentQuarter', 1)
        homeWinProb = getattr(liveGame, 'homeTeamWinProbability', 50.0) or 50.0
        pointsMultiplier = calculateCertaintyMultiplier(quarter, homeWinProb)
    else:
        # Scheduled (pre-game) — full multiplier
        pointsMultiplier = PICKEM_QUARTER_MULTIPLIERS.get(0, 1.0)

    # Win-prob multiplier: underdogs get bonus, favorites get penalty
    homeElo = getattr(liveGame.homeTeam, 'elo', 1500)
    awayElo = getattr(liveGame.awayTeam, 'elo', 1500)
    pickedIsHome = (pickedTeamId == homeTeamId)

    if statusVal == 2:  # Active — use live win probability
        homeWinProbLive = getattr(liveGame, 'homeTeamWinProbability', 50.0) or 50.0
        pickedWp = (homeWinProbLive / 100.0) if pickedIsHome else (1.0 - homeWinProbLive / 100.0)
        underdogMultiplier = calculateWinProbMultiplier(pickedWp)
    else:
        # Pre-game — use ELO
        underdogMultiplier = calculateUnderdogMultiplier(homeElo, awayElo, pickedIsHome)

    if pickedTeamId not in (homeTeamId, awayTeamId):
        raise HTTPException(400, "pickedTeamId must be home or away team")

    from database.connection import get_session
    from database.repositories.pickem_repository import PickEmRepository
    session = get_session()
    try:
        pickemRepo = PickEmRepository(session)
        pick = pickemRepo.submitPick(
            user.id, seasonNum, week, gameIndex,
            homeTeamId, awayTeamId, pickedTeamId,
            pointsMultiplier=pointsMultiplier,
            underdogMultiplier=underdogMultiplier,
        )

        # Achievement hooks — manual pick endpoint, so always counts as non-auto.
        from managers import achievementManager as _am
        from database.models import PickEmPick as _PickEmPick
        from sqlalchemy import func, distinct
        _am.onPickEmSubmitted(session, user.id, isAutoPick=False)
        # Dedicated tiers: count distinct weeks (this season) with at least one manual pick.
        manualWeeks = session.query(func.count(distinct(_PickEmPick.week))).filter(
            _PickEmPick.user_id == user.id,
            _PickEmPick.season == seasonNum,
            _PickEmPick.is_auto.is_(False),
        ).scalar() or 0
        for _key in ("dedicated_i", "dedicated_ii", "dedicated_iii", "dedicated_iv", "dedicated_v", "dedicated_vi"):
            _am.recordProgress(session, user.id, _key, absolute=manualWeeks, currentSeason=seasonNum)

        # Cold-Blooded — picked against favorite team 5+ times this season
        favTeamId = getattr(user, "favorite_team_id", None)
        if favTeamId:
            againstFav = session.query(func.count(_PickEmPick.id)).filter(
                _PickEmPick.user_id == user.id,
                _PickEmPick.season == seasonNum,
                _PickEmPick.is_auto.is_(False),
                ((_PickEmPick.home_team_id == favTeamId) | (_PickEmPick.away_team_id == favTeamId)),
                _PickEmPick.picked_team_id != favTeamId,
            ).scalar() or 0
            if againstFav >= 5:
                _am.unlockSecret(session, user.id, "cold_blooded")

        session.commit()

        # Compute current underdogInfo so frontend can refresh display
        if statusVal == 2:
            liveWp = (getattr(liveGame, 'homeTeamWinProbability', 50.0) or 50.0) / 100.0
            currentUnderdogInfo = {
                "homeMultiplier": calculateWinProbMultiplier(liveWp),
                "awayMultiplier": calculateWinProbMultiplier(1.0 - liveWp),
            }
        else:
            currentUnderdogInfo = {
                "homeMultiplier": calculateUnderdogMultiplier(homeElo, awayElo, True),
                "awayMultiplier": calculateUnderdogMultiplier(homeElo, awayElo, False),
            }

        # Count how many picks user has made this week
        allPicks = pickemRepo.getUserPicks(user.id, seasonNum, week)
        return build_success_response({
            "pick": {
                "gameIndex": pick.game_index,
                "pickedTeamId": pick.picked_team_id,
                "pointsMultiplier": pick.points_multiplier,
                "underdogMultiplier": pick.underdog_multiplier,
            },
            "underdogInfo": currentUnderdogInfo,
            "weekProgress": {"picked": len(allPicks), "total": totalGames},
        })
    except ValueError as e:
        session.rollback()
        raise HTTPException(409, str(e))
    except Exception as e:
        session.rollback()
        logger.error(f"Pick-em submit error: {e}")
        raise HTTPException(500, "Failed to submit pick")
    finally:
        session.close()


@app.get("/api/pickem/leaderboard")
def get_pickem_leaderboard(season: Optional[int] = None):
    """Get pick-em leaderboard (season + current week)."""
    if floosball_app is None:
        raise HTTPException(503, "Application not initialized")

    sm = floosball_app.seasonManager
    currentSeason = sm.currentSeason
    if currentSeason is None:
        return build_success_response({"season": {"entries": []}, "week": {"week": 0, "entries": []}})

    seasonNum = season if season is not None else currentSeason.seasonNumber
    week = sm._getPickemWeek()

    from sqlalchemy import func
    from database.connection import get_session
    from database.repositories.pickem_repository import PickEmRepository
    from database.models import User, PickEmPick
    session = get_session()

    # For the weekly leaderboard: if games aren't active AND the current week
    # has no resolved picks, show the most recent completed week so results
    # don't disappear between weeks. (When games just finished but the week
    # hasn't advanced yet, the current week WILL have resolved picks.)
    weeklyWeek = week
    if currentSeason.activeGames is None and week > 1:
        currentWeekResolved = session.query(func.count(PickEmPick.id)).filter(
            PickEmPick.season == seasonNum,
            PickEmPick.week == week,
            PickEmPick.correct.isnot(None),
        ).scalar()
        if currentWeekResolved == 0:
            weeklyWeek = week - 1
    try:
        pickemRepo = PickEmRepository(session)

        def _buildEntries(rows):
            entries = []
            for rank, (userId, correctCount, totalPicks, totalPoints) in enumerate(rows, 1):
                dbUser = session.query(User).filter_by(id=userId).first()
                username = dbUser.username if dbUser and dbUser.username else f"User {userId}"
                accuracy = round(correctCount / totalPicks * 100, 1) if totalPicks > 0 else 0
                entries.append({
                    "rank": rank,
                    "userId": userId,
                    "username": username,
                    "correctCount": correctCount,
                    "totalPicks": totalPicks,
                    "totalPoints": totalPoints,
                    "accuracy": accuracy,
                })
            return entries

        seasonRows = pickemRepo.getSeasonLeaderboard(seasonNum)
        weekRows = pickemRepo.getWeekLeaderboard(seasonNum, weeklyWeek)

        # Enrich season entries with Clairvoyant weeks
        seasonEntries = _buildEntries(seasonRows)
        for entry in seasonEntries:
            stats = pickemRepo.getUserSeasonStats(entry["userId"], seasonNum)
            entry["clairvoyantWeeks"] = stats["clairvoyantWeeks"]

        # Enrich weekly entries with allAuto flag — True iff every pick this
        # week was auto-picked. Drives an AUTO badge on the UI so users can
        # tell who actually showed up to set their picks.
        weekEntries = _buildEntries(weekRows)
        if weekEntries:
            autoRows = session.query(
                PickEmPick.user_id,
                func.min(PickEmPick.is_auto).label("min_auto"),
                func.max(PickEmPick.is_auto).label("max_auto"),
            ).filter(
                PickEmPick.season == seasonNum,
                PickEmPick.week == weeklyWeek,
            ).group_by(PickEmPick.user_id).all()
            autoFlagByUser = {r.user_id: bool(r.min_auto) for r in autoRows}
            for entry in weekEntries:
                entry["allAuto"] = autoFlagByUser.get(entry["userId"], False)

        return build_success_response({
            "season": {"entries": seasonEntries},
            "week": {"week": weeklyWeek, "entries": weekEntries},
        })
    finally:
        session.close()


@app.get("/api/pickem/history")
def get_pickem_history(user: _User = Depends(_getCurrentUser)):
    """Get user's full pick history for the current season."""
    if floosball_app is None:
        raise HTTPException(503, "Application not initialized")

    sm = floosball_app.seasonManager
    currentSeason = sm.currentSeason
    if currentSeason is None:
        return build_success_response({"weeks": []})

    seasonNum = currentSeason.seasonNumber

    from database.connection import get_session
    from database.repositories.pickem_repository import PickEmRepository
    session = get_session()
    try:
        pickemRepo = PickEmRepository(session)
        allPicks = pickemRepo.getUserHistory(user.id, seasonNum)

        # Group by week
        weekMap = {}
        for pick in allPicks:
            if pick.week not in weekMap:
                weekMap[pick.week] = []
            weekMap[pick.week].append({
                "gameIndex": pick.game_index,
                "homeTeamId": pick.home_team_id,
                "awayTeamId": pick.away_team_id,
                "pickedTeamId": pick.picked_team_id,
                "correct": pick.correct,
                "pointsMultiplier": pick.points_multiplier,
                "pointsEarned": pick.points_earned,
            })

        weeks = []
        for w in sorted(weekMap.keys()):
            picks = weekMap[w]
            correctCount = sum(1 for p in picks if p["correct"] is True)
            totalResolved = sum(1 for p in picks if p["correct"] is not None)
            totalPoints = sum(p["pointsEarned"] or 0 for p in picks if p["correct"] is not None)
            weeks.append({
                "week": w,
                "picks": picks,
                "correct": correctCount,
                "total": totalResolved,
                "totalPoints": totalPoints,
                "clairvoyant": totalPoints >= 96,  # matches PICKEM_CLAIRVOYANT_THRESHOLD
            })

        return build_success_response({"weeks": weeks})
    finally:
        session.close()


# ============================================================================
# BOT API (Discord bot ↔ backend)
# ============================================================================

def _checkBotAuth(x_bot_key: str = Header(...)):
    """Authorize Discord bot via shared API key."""
    from config_manager import get_config
    expected = get_config().get("botApiKey", "")
    if not expected or x_bot_key != expected:
        raise HTTPException(status_code=403, detail="Invalid bot key")


class _BotLinkBody(BaseModel):
    discordId: str
    username: str

class _BotUnlinkBody(BaseModel):
    discordId: str

class _BotRemindersBody(BaseModel):
    discordId: str
    enabled: bool


@app.post("/api/bot/link")
def bot_link_user(body: _BotLinkBody, _auth: None = Depends(_checkBotAuth)):
    """Link a Discord user to a Floosball account by username."""
    from database.connection import get_session
    from database.models import User
    session = get_session()
    try:
        # Find user by username (case-insensitive)
        user = session.query(User).filter(User.username.ilike(body.username)).first()
        if not user:
            raise HTTPException(404, "Username not found")

        # Clear discord_id from any other user that has it (re-link)
        existing = session.query(User).filter(User.discord_id == body.discordId).first()
        if existing and existing.id != user.id:
            existing.discord_id = None
            existing.discord_dm_reminders = False

        user.discord_id = body.discordId
        session.commit()
        return build_success_response({"username": user.username})
    finally:
        session.close()


@app.delete("/api/bot/link")
def bot_unlink_user(body: _BotUnlinkBody, _auth: None = Depends(_checkBotAuth)):
    """Unlink a Discord user from their Floosball account."""
    from database.connection import get_session
    from database.models import User
    session = get_session()
    try:
        user = session.query(User).filter(User.discord_id == body.discordId).first()
        if user:
            user.discord_id = None
            user.discord_dm_reminders = False
            session.commit()
        return build_success_response({"unlinked": True})
    finally:
        session.close()


@app.post("/api/bot/reminders")
def bot_set_reminders(body: _BotRemindersBody, _auth: None = Depends(_checkBotAuth)):
    """Toggle DM reminders for a linked Discord user."""
    from database.connection import get_session
    from database.models import User
    session = get_session()
    try:
        user = session.query(User).filter(User.discord_id == body.discordId).first()
        if not user:
            raise HTTPException(404, "Account not linked — use /link first")
        user.discord_dm_reminders = body.enabled
        session.commit()
        return build_success_response({"enabled": body.enabled})
    finally:
        session.close()


@app.get("/api/bot/unsubmitted")
def bot_get_unsubmitted(_auth: None = Depends(_checkBotAuth)):
    """Get Discord IDs of users who opted into reminders but haven't submitted roster/picks."""
    from database.connection import get_session
    from database.models import User, FantasyRoster, PickEmPick
    from sqlalchemy import func

    if floosball_app is None:
        raise HTTPException(503, "Application not initialized")

    sm = floosball_app.seasonManager
    currentSeason = sm.currentSeason
    if currentSeason is None:
        return build_success_response({"rosterMissing": [], "picksMissing": [], "week": 0, "nextGameStart": None})

    seasonNum = currentSeason.seasonNumber
    pickemWeek = sm._getPickemWeek()

    session = get_session()
    try:
        # All users with reminders enabled
        reminderUsers = session.query(User).filter(
            User.discord_dm_reminders == True,
            User.discord_id.isnot(None),
        ).all()

        if not reminderUsers:
            return build_success_response({"rosterMissing": [], "picksMissing": [], "week": pickemWeek, "nextGameStart": None})

        userIds = [u.id for u in reminderUsers]
        discordMap = {u.id: u.discord_id for u in reminderUsers}

        # Users missing locked roster for this season
        lockedUserIds = set(
            uid for (uid,) in session.query(FantasyRoster.user_id).filter(
                FantasyRoster.season == seasonNum,
                FantasyRoster.is_locked == True,
                FantasyRoster.user_id.in_(userIds),
            ).all()
        )
        rosterMissing = [discordMap[uid] for uid in userIds if uid not in lockedUserIds]

        # Users missing picks for this week
        pickedUserIds = set(
            uid for (uid,) in session.query(func.distinct(PickEmPick.user_id)).filter(
                PickEmPick.season == seasonNum,
                PickEmPick.week == pickemWeek,
                PickEmPick.user_id.in_(userIds),
            ).all()
        )
        picksMissing = [discordMap[uid] for uid in userIds if uid not in pickedUserIds]

        # Next game start time
        nextGameStart = None
        schedule = currentSeason.schedule
        currentWeek = currentSeason.currentWeek
        if schedule and currentWeek and isinstance(currentWeek, int):
            weekIdx = currentWeek - 1
            if 0 <= weekIdx < len(schedule):
                weekEntry = schedule[weekIdx]
                startTime = weekEntry.get('startTime') if isinstance(weekEntry, dict) else None
                if startTime:
                    nextGameStart = startTime.isoformat() + 'Z' if hasattr(startTime, 'isoformat') else str(startTime)

        return build_success_response({
            "rosterMissing": rosterMissing,
            "picksMissing": picksMissing,
            "week": pickemWeek,
            "nextGameStart": nextGameStart,
        })
    finally:
        session.close()


@app.get("/api/bot/cards")
def bot_get_cards(discordId: str = Query(...), _auth: None = Depends(_checkBotAuth)):
    """Get equipped cards for a linked Discord user."""
    from database.connection import get_session
    from database.models import User, EquippedCard

    if floosball_app is None:
        raise HTTPException(503, "Application not initialized")

    sm = floosball_app.seasonManager
    currentSeason = sm.currentSeason.seasonNumber if sm and sm.currentSeason else 0
    currentWeek = sm.currentSeason.currentWeek if sm and sm.currentSeason else 0

    session = get_session()
    try:
        user = session.query(User).filter(User.discord_id == discordId).first()
        if not user:
            raise HTTPException(404, "Account not linked — use /link first")

        from database.repositories.card_repositories import EquippedCardRepository
        equippedRepo = EquippedCardRepository(session)
        equipped = equippedRepo.getByUserWeek(user.id, currentSeason, currentWeek)

        posLabels = {1: "QB", 2: "RB", 3: "WR", 4: "TE", 5: "K"}
        cards = []
        for eq in equipped:
            template = eq.user_card.card_template
            effectConfig = template.effect_config or {}
            cards.append({
                "slotNumber": eq.slot_number,
                "displayName": effectConfig.get("displayName", "Unknown"),
                "edition": template.edition,
                "position": posLabels.get(template.position, "??"),
                "playerName": template.player_name,
                "teamAbbr": getattr(template.team, 'abbr', '') if template.team else "",
                "teamName": getattr(template.team, 'name', '') if template.team else "",
                "streakCount": getattr(eq, 'streak_count', 1) or 1,
                "locked": eq.locked,
            })
        cards.sort(key=lambda c: c["slotNumber"])

        return build_success_response({
            "username": user.username,
            "equippedCards": cards,
            "season": currentSeason,
            "week": currentWeek,
        })
    finally:
        session.close()


@app.get("/api/bot/roster")
def bot_get_roster(discordId: str = Query(...), _auth: None = Depends(_checkBotAuth)):
    """Get fantasy roster for a linked Discord user."""
    from database.connection import get_session
    from database.models import User, FantasyRoster

    if floosball_app is None:
        raise HTTPException(503, "Application not initialized")

    sm = floosball_app.seasonManager
    currentSeasonNum = sm.currentSeason.seasonNumber if sm and sm.currentSeason else None

    session = get_session()
    try:
        user = session.query(User).filter(User.discord_id == discordId).first()
        if not user:
            raise HTTPException(404, "Account not linked — use /link first")

        if currentSeasonNum is None:
            return build_success_response({"username": user.username, "roster": None, "season": None})

        roster = session.query(FantasyRoster).filter_by(
            user_id=user.id, season=currentSeasonNum
        ).first()

        if roster is None:
            return build_success_response({"username": user.username, "roster": None, "season": currentSeasonNum})

        players = []
        for rp in roster.players:
            playerObj = floosball_app.playerManager.getPlayerById(rp.player_id) if floosball_app else None
            currentFp = _getPlayerLiveFantasyPoints(playerObj) if playerObj else 0
            earnedPoints = max(0, currentFp - rp.points_at_lock) if roster.is_locked else 0
            players.append({
                "slot": rp.slot,
                "playerName": playerObj.name if playerObj else "Unknown",
                "position": playerObj.position.name if playerObj and hasattr(playerObj.position, 'name') else "",
                "teamAbbr": getattr(playerObj.team, 'abbr', '') if playerObj and hasattr(playerObj.team, 'name') else "",
                "teamName": getattr(playerObj.team, 'name', '') if playerObj and hasattr(playerObj.team, 'name') else "",
                "earnedPoints": round(earnedPoints, 1),
            })

        # Sort by slot order
        slotOrder = {"QB": 0, "RB": 1, "WR1": 2, "WR2": 3, "TE": 4, "K": 5, "FLEX": 6}
        players.sort(key=lambda p: slotOrder.get(p["slot"], 99))

        totalEarned = sum(p["earnedPoints"] for p in players)
        cardBonus = roster.card_bonus_points or 0.0

        return build_success_response({
            "username": user.username,
            "roster": {
                "isLocked": roster.is_locked,
                "totalPoints": round(totalEarned, 1),
                "cardBonusPoints": round(cardBonus, 1),
                "players": players,
            },
            "season": currentSeasonNum,
        })
    finally:
        session.close()


# ============================================================================
# HEALTH CHECK
# ============================================================================
# ACHIEVEMENT ENDPOINTS
# ============================================================================

@app.get("/api/achievements")
def listAchievements(user: _User = Depends(_getCurrentUser)):
    """Return all achievements with the user's progress and completion state.
    Lazily backfills onboarding achievements for existing users on first visit."""
    from database.connection import get_session
    from managers import achievementManager
    sm = floosball_app.seasonManager if floosball_app else None
    currentSeason = sm.currentSeason.seasonNumber if sm and sm.currentSeason else 0
    session = get_session()
    try:
        try:
            achievementManager.backfillOnboardingAchievements(session, user.id)
            # Curator's progress was historically only updated on pack-open and
            # missed card-acquisition paths (blend, shop buy, achievement reward
            # claim). Re-sync from the authoritative UserCard count here so users
            # whose progress got stuck catch up the next time they check.
            if currentSeason:
                achievementManager.syncCuratorProgress(session, user.id, currentSeason)
            session.commit()
        except Exception as e:
            session.rollback()
            logger.warning(f"Onboarding backfill failed for user {user.id}: {e}")
        achievements = achievementManager.getUserAchievements(session, user.id, currentSeason)
        unclaimed = achievementManager.getUnclaimedRewardCount(session, user.id, currentSeason)
        return build_success_response({"achievements": achievements, "unclaimedRewards": unclaimed, "season": currentSeason})
    finally:
        session.close()


@app.get("/api/achievements/pending-rewards")
def listPendingRewards(user: _User = Depends(_getCurrentUser)):
    """List unclaimed pack/powerup rewards the user has earned. Includes canDefer
    flag for pack rewards when late-season or offseason deferral is offered."""
    from database.connection import get_session
    from managers import achievementManager
    sm = floosball_app.seasonManager if floosball_app else None
    currentSeason = sm.currentSeason.seasonNumber if sm and sm.currentSeason else 0
    currentWeek = sm.currentSeason.currentWeek if sm and sm.currentSeason else 0
    isOffseason = (getattr(sm.currentSeason, 'currentWeekText', '') == 'Offseason') if sm and sm.currentSeason else False
    session = get_session()
    try:
        rewards = achievementManager.getPendingRewards(
            session, user.id, currentSeason, currentWeek, isOffseason=isOffseason,
        )
        return build_success_response({"rewards": rewards, "currentWeek": currentWeek, "season": currentSeason})
    finally:
        session.close()


@app.post("/api/achievements/reward/{rewardId}/defer")
def deferPendingReward(rewardId: int, user: _User = Depends(_getCurrentUser)):
    """Hold an unclaimed reward (pack or powerup) until next season. Allowed
    once per reward, and only while defer is currently offered (late regular
    season or offseason)."""
    from database.connection import get_session
    from database.models import PendingReward
    from managers import achievementManager
    sm = floosball_app.seasonManager if floosball_app else None
    currentSeason = sm.currentSeason.seasonNumber if sm and sm.currentSeason else 0
    currentWeek = sm.currentSeason.currentWeek if sm and sm.currentSeason else 0
    if not currentSeason:
        raise HTTPException(status_code=400, detail="No active season")
    isOffseason = (getattr(sm.currentSeason, 'currentWeekText', '') == 'Offseason') if sm and sm.currentSeason else False
    weeksLeft = max(0, achievementManager.REGULAR_SEASON_WEEKS - currentWeek) if currentWeek else achievementManager.REGULAR_SEASON_WEEKS
    lateSeason = weeksLeft <= achievementManager.DEFER_OFFER_WEEKS_REMAINING and currentWeek > 0
    if not (lateSeason or isOffseason):
        raise HTTPException(status_code=400, detail="Deferral only available late in the regular season or during offseason")

    session = get_session()
    try:
        reward = session.query(PendingReward).filter(
            PendingReward.id == rewardId,
            PendingReward.user_id == user.id,
        ).first()
        if not reward:
            raise HTTPException(status_code=404, detail="Reward not found")
        if reward.claimed_at is not None:
            raise HTTPException(status_code=400, detail="Reward already claimed")
        if reward.defer_until_season is not None:
            raise HTTPException(status_code=400, detail="Reward already deferred")
        reward.defer_until_season = currentSeason + 1
        session.commit()
        return build_success_response({
            "id": reward.id,
            "deferUntilSeason": reward.defer_until_season,
        })
    except HTTPException:
        session.rollback()
        raise
    except Exception as e:
        session.rollback()
        logger.error(f"Defer reward failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to defer reward")
    finally:
        session.close()


@app.post("/api/achievements/reward/{rewardId}/convert")
def convertPendingPackReward(rewardId: int, user: _User = Depends(_getCurrentUser)):
    """Convert a pending pack reward to Floobits at the pack's shop cost.

    Pack-only. Powerup rewards aren't convertible. Used when the user
    would rather take the cash than open the pack — typically because
    their stash is already full and they don't want to clear the
    queued one yet. Marks the reward as claimed_at the conversion
    moment so it disappears from the pending panel.
    """
    from database.connection import get_session
    from database.models import PendingReward, PackType
    from database.repositories.card_repositories import CurrencyRepository

    sm = floosball_app.seasonManager if floosball_app else None
    currentSeason = sm.currentSeason.seasonNumber if sm and sm.currentSeason else 0

    session = get_session()
    try:
        reward = session.query(PendingReward).filter(
            PendingReward.id == rewardId,
            PendingReward.user_id == user.id,
        ).first()
        if not reward:
            raise HTTPException(status_code=404, detail="Reward not found")
        if reward.claimed_at is not None:
            raise HTTPException(status_code=400, detail="Reward already claimed")
        if reward.kind != "pack":
            raise HTTPException(status_code=400, detail="Only pack rewards can be converted")
        if reward.defer_until_season is not None and currentSeason < reward.defer_until_season:
            raise HTTPException(
                status_code=400,
                detail=f"Reward deferred until season {reward.defer_until_season}",
            )

        packType = session.query(PackType).filter(PackType.name == reward.slug).first()
        if not packType:
            raise HTTPException(status_code=500, detail=f"Unknown pack type: {reward.slug}")
        conversionValue = int(packType.cost or 0)
        if conversionValue <= 0:
            raise HTTPException(status_code=400, detail="This pack has no shop value to convert")

        currencyRepo = CurrencyRepository(session)
        currencyRepo.addFunds(
            userId=user.id, amount=conversionValue,
            transactionType="achievement",
            description=f"{reward.source} (converted to Floobits)",
            season=currentSeason,
        )
        reward.claimed_at = datetime.utcnow()
        session.commit()
        return build_success_response({
            "id": reward.id,
            "kind": "floobits",
            "floobits": conversionValue,
            "packName": packType.display_name or packType.name,
        })
    except HTTPException:
        session.rollback()
        raise
    except Exception as e:
        session.rollback()
        logger.error(f"Convert reward failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to convert reward")
    finally:
        session.close()


@app.post("/api/achievements/claim-reward/{rewardId}")
def claimPendingReward(rewardId: int, user: _User = Depends(_getCurrentUser)):
    """Claim a pending pack or powerup earned via achievement.

    Pack claims open the pack server-side and return the drawn cards.
    Powerup claims are deferred to v2 (will return 501 for now).
    """
    from datetime import datetime
    from database.connection import get_session
    from database.models import PendingReward, PackType
    from managers.cardManager import CardManager

    session = get_session()
    try:
        reward = session.query(PendingReward).filter(
            PendingReward.id == rewardId,
            PendingReward.user_id == user.id,
        ).first()
        if not reward:
            raise HTTPException(status_code=404, detail="Reward not found")
        if reward.claimed_at is not None:
            raise HTTPException(status_code=400, detail="Reward already claimed")
        if reward.available_at > datetime.utcnow():
            raise HTTPException(status_code=400, detail="Reward not yet available")

        sm = floosball_app.seasonManager if floosball_app else None
        currentSeason = sm.currentSeason.seasonNumber if sm and sm.currentSeason else 0

        # Respect user-selected deferral — blocks claim until the target season arrives.
        if reward.defer_until_season is not None and currentSeason < reward.defer_until_season:
            raise HTTPException(
                status_code=400,
                detail=f"Reward deferred until season {reward.defer_until_season}",
            )

        if reward.kind == "pack":
            packType = session.query(PackType).filter(PackType.name == reward.slug).first()
            if not packType:
                raise HTTPException(status_code=500, detail=f"Unknown pack type: {reward.slug}")
            cardManager = CardManager(floosball_app.serviceContainer if floosball_app else None)
            # Achievement-granted packs go through the same reveal+select
            # flow as purchased packs — the user picks which cards to keep
            # rather than the system auto-granting everything. Daily limit
            # and rotation guards are skipped (skipCurrency=True).
            # Achievement hooks fire on /api/packs/select after the user
            # confirms their selection, not here.
            result = cardManager.revealPack(
                session, user.id, packType.id, currentSeason,
                skipCurrency=True,
            )
            reward.claimed_at = datetime.utcnow()
            session.commit()
            return build_success_response({"kind": "pack", **result})

        if reward.kind == "powerup":
            # Grant the powerup as a ShopPurchase with price_paid=0. Expiry
            # follows the catalog's duration when the powerup has one
            # (temp_flex, income_boost, etc.); one-shot slugs (extra_swap,
            # modifier_nullifier) get expires_at_week=None.
            from database.models import ShopPurchase
            from constants import POWERUP_CATALOG
            powerupInfo = POWERUP_CATALOG.get(reward.slug)
            if not powerupInfo:
                raise HTTPException(status_code=500, detail=f"Unknown powerup: {reward.slug}")
            sm = floosball_app.seasonManager if floosball_app else None
            currentWeek = sm.currentSeason.currentWeek if sm and sm.currentSeason else 1
            currentWeek = max(1, currentWeek)
            durationWeeks = powerupInfo.get("durationWeeks")
            if durationWeeks:
                # Defer start to next week if the current week is already
                # "spent" — either games are running, or they've ended but
                # the week hasn't rolled. Either way the powerup can't
                # affect what's already happened.
                deferStart = _areGamesStarted() or _areGamesCompleted()
                effectiveStartWeek = currentWeek + 1 if deferStart else currentWeek
                expiresAtWeek = effectiveStartWeek + durationWeeks - 1
                purchaseWeek = effectiveStartWeek
            else:
                expiresAtWeek = None
                purchaseWeek = currentWeek
            purchase = ShopPurchase(
                user_id=user.id,
                item_slug=reward.slug,
                season=currentSeason,
                week=purchaseWeek,
                price_paid=0,
                expires_at_week=expiresAtWeek,
            )
            session.add(purchase)
            reward.claimed_at = datetime.utcnow()
            session.commit()
            return build_success_response({
                "kind": "powerup",
                "slug": reward.slug,
                "name": powerupInfo.get("name", reward.slug),
                "expiresAtWeek": expiresAtWeek,
            })

        raise HTTPException(status_code=500, detail=f"Unknown reward kind: {reward.kind}")
    except HTTPException:
        session.rollback()
        raise
    except ValueError as e:
        session.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        session.rollback()
        logger.error(f"Claim reward failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to claim reward")
    finally:
        session.close()


# ============================================================================

# /health is defined near the top of this file (with sim-liveness reporting).


# ============================================================================
# HELPER FUNCTION TO SET APPLICATION REFERENCE
# ============================================================================

def set_floosball_app(app_instance):
    """Set the FloosballApplication instance for API access"""
    global floosball_app
    floosball_app = app_instance
    logger.info("FloosballApplication reference set in API")
