"""
Modern Floosball REST API
Uses refactored manager system with clean separation of concerns
"""

from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect, Header, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import asyncio
import json
from datetime import datetime

import os
from logger_config import get_logger
from api.websocket_manager import manager as ws_manager
from api.event_models import GameEvent, SeasonEvent, StandingsEvent, SystemEvent
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
    
    # The FloosballApplication will be injected by the main entry point
    # For now, log that we're ready
    logger.info("API server ready - waiting for FloosballApplication initialization")


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
            
    except WebSocketDisconnect:
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
                logger.debug(f"Received from season client: {data}")
            except asyncio.TimeoutError:
                # Send ping to keep connection alive
                try:
                    await websocket.send_json({"type": "ping", "timestamp": datetime.now().isoformat()})
                except:
                    break
            
    except WebSocketDisconnect:
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
            
    except WebSocketDisconnect:
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
        'seasonsCoached': coach.seasonsCoached,
    }


@app.get("/api/teams", response_model=Dict[str, Any])
async def get_teams(league: Optional[str] = None):
    """
    Get all teams, optionally filtered by league
    
    Returns:
        List of team objects with basic info and current season stats
    """
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
async def get_team(team_id: int):
    """
    Get detailed information about a specific team
    
    Returns:
        Full team object with ratings, roster, history, and stats
    """
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
        # Build history: current season stats + archived past seasons
        import copy as _copy
        currentStats = _copy.deepcopy(team.seasonTeamStats)
        # Ensure current season number is set (defaults to 0 in teamStatsDict)
        if currentStats.get('season', 0) == 0:
            sm = floosball_app.seasonManager if floosball_app else None
            currentStats['season'] = sm.currentSeason.seasonNumber if sm and hasattr(sm, 'currentSeason') and sm.currentSeason else 1
        team_dict['history'] = [currentStats] + (team.statArchive or [])
        team_dict['coach'] = _buildCoachDict(team)

        # Roster
        roster = {}
        for pos, player in team.rosterDict.items():
            if player is not None:
                roster[pos] = {
                    'id': player.id,
                    'name': player.name,
                    'position': player.position.name if hasattr(player.position, 'name') else str(player.position),
                    'rating': player.playerRating,
                    'ratingStars': PlayerResponseBuilder.calculateStarRating(player.playerRating),
                    'termRemaining': player.termRemaining,
                    'tier': player.playerTier.name if hasattr(player.playerTier, 'name') else str(player.playerTier),
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
            "Cache-Control": "public, max-age=3600",
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
            "Cache-Control": "public, max-age=3600",
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
    position: Optional[str] = None,
    team_id: Optional[int] = None,
    status: Optional[str] = None  # 'active', 'retired', 'fa', 'hof'
):
    """
    Get players with optional filters
    
    Args:
        position: Filter by position (QB, RB, WR, etc.)
        team_id: Filter by team ID
        status: Filter by status (active, retired, fa, hof)
    
    Returns:
        List of player objects
    """
    if floosball_app is None:
        raise HTTPException(status_code=503, detail="Application not initialized")
    
    try:
        # Determine which player list to use based on status
        if status == 'retired':
            players = floosball_app.playerManager.retiredPlayers
        elif status == 'hof':
            players = floosball_app.playerManager.hallOfFame
        elif status == 'fa':
            players = floosball_app.playerManager.freeAgents
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
async def get_player(player_id: int):
    """
    Get detailed information about a specific player
    
    Returns:
        Full player object with attributes, stats, and history
    """
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
        # Build current-season entry from live seasonStatsDict and prepend to archive
        sm = floosball_app.seasonManager
        currentSeasonNum = sm.currentSeason.seasonNumber if sm.currentSeason else None
        team = player.team
        hasTeamObj = team and not isinstance(team, str)
        teamName = team.name if hasTeamObj else (team if isinstance(team, str) else 'FA')
        teamColor = team.color if hasTeamObj else '#94a3b8'
        currentSeasonEntry = dict(player.seasonStatsDict)
        currentSeasonEntry['season'] = currentSeasonNum
        currentSeasonEntry['team'] = teamName
        currentSeasonEntry['color'] = teamColor
        currentSeasonEntry['gp'] = player.gamesPlayed
        player_dict['stats'] = [currentSeasonEntry] + list(player.seasonStatsArchive)
        player_dict['allTimeStats'] = player.careerStatsDict
        
        return build_success_response(player_dict)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting player {player_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# REST API - SEASON & GAMES
# ============================================================================

@app.get("/api/currentGames", response_model=List[Dict[str, Any]])
async def get_current_games():
    """
    Get all currently scheduled, active, and recently completed games
    
    Returns:
        List of games with real-time scores, status, and win probabilities
    """
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
            game_dict['startTime'] = datetime.timestamp(game.startTime)
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


@app.get("/api/games/{game_id}", response_model=Dict[str, Any])
async def get_game_by_id(game_id: int):
    """
    Get a specific game by ID
    
    Args:
        game_id: The game ID
        
    Returns:
        Game data with scores, status, win probabilities, and play info
    """
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
        game_dict['startTime'] = datetime.timestamp(game.startTime)
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
                            }
                    serializable_plays.append(play_data)
                elif 'event' in item:
                    serializable_plays.append(item['event'])
        
        # gameFeed is newest-first (insert(0, ...)), so serializable_plays is already newest-first
        game_dict['plays'] = serializable_plays

        # Add live game stats snapshot
        if hasattr(game, '_buildGameStatsSnapshot'):
            game_dict['gameStats'] = game._buildGameStatsSnapshot()

        return game_dict
    
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        logger.error(f"Error getting game {game_id}: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/gameStats", response_model=Dict[str, Any])
async def get_game_stats(id: int):
    """
    Get detailed statistics for a specific game
    
    Args:
        id: Game ID
    
    Returns:
        Full game statistics including player stats, team stats, and play-by-play
    """
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


@app.get("/api/highlights", response_model=List[Dict[str, Any]])
async def get_highlights(limit: int = Query(default=20, ge=1, le=100)):
    """
    Get recent highlight plays from active games
    
    Args:
        limit: Maximum number of highlights to return
    
    Returns:
        List of highlight plays (touchdowns, turnovers, big plays)
    """
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
async def get_season_info():
    """
    Get current season information
    
    Returns:
        Season number, current week, schedule, standings
    """
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
        
        # Include next game start time when games haven't started yet
        nextGameStartTime = None
        gamesStarted = _areGamesStarted()
        if not gamesStarted and not current_season.isComplete:
            nextStart = season_mgr._cachedNextGameStart
            if nextStart:
                nextGameStartTime = nextStart.isoformat() + 'Z'

        return build_success_response({
            'season_number': current_season.seasonNumber,
            'current_week': current_season.currentWeek,
            'current_week_text': current_season.currentWeekText,
            'is_complete': current_season.isComplete,
            'active_games': activeGameIds,
            'completed_games': completedGameIds,
            'champion': TeamResponseBuilder.buildBasicTeamDict(current_season.champion) if current_season.champion else None,
            'mvp': current_season.mvp if hasattr(current_season, 'mvp') and current_season.mvp else None,
            'next_game_start_time': nextGameStartTime,
        })
    
    except Exception as e:
        logger.error(f"Error getting season info: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/standings", response_model=List[Dict[str, Any]])
async def get_standings():
    """
    Get current league standings
    
    Returns:
        Standings for all leagues sorted by record
    """
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


# ============================================================================
# REST API - STATS & RECORDS
# ============================================================================

_VALID_STAT_CATEGORIES = {
    'fantasy_points', 'passing_yards', 'passing_tds', 'rushing_yards', 'rushing_tds',
    'receiving_yards', 'receiving_tds', 'receptions', 'fg_made', 'fg_pct',
    'performance_rating',
}
_VALID_POSITIONS = {'ALL', 'QB', 'RB', 'WR', 'TE', 'K'}


@app.get("/api/stats/leaders", response_model=Dict[str, Any])
async def get_stat_leaders(
    category: str = Query(default="fantasy_points"),
    position: str = Query(default="ALL"),
    limit: int = Query(default=10, ge=1, le=50),
):
    """Get statistical leaders filtered by position and category"""
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
            leaders.append(entry)

        return build_success_response({'category': category, 'position': position, 'leaders': leaders})

    except Exception as e:
        logger.error(f"Error getting stat leaders: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/stats/mvp-rankings", response_model=Dict[str, Any])
async def get_mvp_rankings(
    limit: int = Query(default=10, ge=1, le=50),
):
    """Get MVP race rankings — players ranked by z-score across all positions"""
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

def _check_admin_password(password: Optional[str]) -> None:
    """Raise 403 if the provided password doesn't match config"""
    try:
        from config_manager import get_config
        cfg = get_config()
        expected = cfg.get("adminPassword", "")
    except Exception:
        expected = ""
    if not expected or password != expected:
        raise HTTPException(status_code=403, detail="Forbidden")


@app.post("/api/admin/names")
async def admin_add_names(payload: Dict[str, Any], x_admin_password: Optional[str] = Header(default=None)):
    """Add names to the unused player name pool"""
    _check_admin_password(x_admin_password)
    if floosball_app is None:
        raise HTTPException(status_code=503, detail="Application not initialized")
    names = payload.get("names", [])
    if not isinstance(names, list) or not names:
        raise HTTPException(status_code=400, detail="'names' must be a non-empty list of strings")
    if len(names) > 500:
        raise HTTPException(status_code=400, detail="Too many names; maximum 500 per request")
    pm = floosball_app.playerManager
    pm.unusedNames.extend(names)
    if getattr(pm, 'name_repo', None):
        pm.name_repo.add_names_batch(names)
        pm.db_session.commit()
    return {"added": len(names), "total": len(pm.unusedNames)}


@app.post("/api/admin/players")
async def admin_create_player(payload: Dict[str, Any], x_admin_password: Optional[str] = Header(default=None)):
    """Create a player and add them to the free agent pool for next season"""
    _check_admin_password(x_admin_password)
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


@app.get("/api/admin/beta/allowlist")
async def admin_get_beta_allowlist(x_admin_password: Optional[str] = Header(default=None)):
    """List all emails on the beta allowlist."""
    _check_admin_password(x_admin_password)
    from database.connection import get_session
    from database.models import BetaAllowlist
    session = get_session()
    try:
        entries = session.query(BetaAllowlist).order_by(BetaAllowlist.added_at.desc()).all()
        return {
            "emails": [
                {
                    "email": e.email,
                    "addedAt": e.added_at.isoformat() if e.added_at else None,
                }
                for e in entries
            ]
        }
    finally:
        session.close()


@app.post("/api/admin/beta/allowlist")
async def admin_add_beta_emails(payload: Dict[str, Any], x_admin_password: Optional[str] = Header(default=None)):
    """Add email(s) to beta allowlist."""
    _check_admin_password(x_admin_password)
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
async def admin_remove_beta_email(email: str, x_admin_password: Optional[str] = Header(default=None)):
    """Remove an email from beta allowlist."""
    _check_admin_password(x_admin_password)
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


@app.get("/api/admin/users")
def admin_list_users(q: Optional[str] = Query(default=None),
                     x_admin_password: Optional[str] = Header(default=None)):
    """List registered users, optionally filtered by search query."""
    _check_admin_password(x_admin_password)
    from database.connection import get_session
    from database.models import User, UserCurrency, Team

    session = get_session()
    try:
        query = session.query(User)
        if q and q.strip():
            term = f"%{q.strip().lower()}%"
            query = query.filter(
                (User.email.ilike(term)) | (User.username.ilike(term))
            )
        users = query.order_by(User.created_at.desc()).limit(100).all()

        # Batch-load currencies and favorite teams
        userIds = [u.id for u in users]
        currencies = {c.user_id: c for c in session.query(UserCurrency).filter(UserCurrency.user_id.in_(userIds)).all()} if userIds else {}
        teamIds = {u.favorite_team_id for u in users if u.favorite_team_id}
        teams = {t.id: t for t in session.query(Team).filter(Team.id.in_(teamIds)).all()} if teamIds else {}

        result = []
        for u in users:
            currency = currencies.get(u.id)
            favTeam = teams.get(u.favorite_team_id) if u.favorite_team_id else None
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
                "createdAt": u.created_at.isoformat() if u.created_at else None,
                "isActive": u.is_active,
                "lastLoginAt": u.last_login_at.isoformat() if u.last_login_at else None,
            })
        return build_success_response({"users": result, "total": len(result)})
    finally:
        session.close()


@app.get("/api/admin/card-options")
def admin_card_options(x_admin_password: Optional[str] = Header(default=None)):
    """Return available editions, effects, and classifications for the card grant tool."""
    _check_admin_password(x_admin_password)
    from managers.cardEffects import (
        SHARED_EFFECT_POOL, POSITION_EXCLUSIVE_POOLS,
        EFFECT_DISPLAY_NAMES, EFFECT_CATEGORY, EDITION_POWER_SCALES,
    )
    editions = list(EDITION_POWER_SCALES.keys())
    # Build effects grouped by category from the shared + exclusive pools
    effects = {}
    allEffects = list(SHARED_EFFECT_POOL)
    for posPool in POSITION_EXCLUSIVE_POOLS.values():
        allEffects.extend(posPool)
    seen = set()
    for name, _w in allEffects:
        if name in seen:
            continue
        seen.add(name)
        cat = EFFECT_CATEGORY.get(name, "flat_fp")
        if cat not in effects:
            effects[cat] = []
        effects[cat].append({"name": name, "displayName": EFFECT_DISPLAY_NAMES.get(name, name)})
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
                         x_admin_password: Optional[str] = Header(default=None)):
    """Search players by name for the card grant tool."""
    _check_admin_password(x_admin_password)
    if floosball_app is None:
        raise HTTPException(status_code=503, detail="Application not initialized")
    pm = floosball_app.playerManager
    query = q.lower()
    results = []
    for team in pm.allTeams:
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
                     x_admin_password: Optional[str] = Header(default=None)):
    """Grant a card to a user with specific edition, effect, and classification."""
    _check_admin_password(x_admin_password)
    from database.connection import get_session
    from database.models import User, CardTemplate, UserCard
    from managers.cardEffects import buildEffectConfig, EDITION_POWER_SCALES
    from managers.cardManager import EDITION_SELL_VALUES

    email = payload.get("email", "").strip().lower()
    playerId = payload.get("playerId")
    edition = payload.get("edition", "base")
    effectName = payload.get("effectName")  # optional override
    categoryOverride = payload.get("category")  # optional category override
    classification = payload.get("classification")  # optional

    if not email:
        raise HTTPException(status_code=400, detail="email is required")
    if edition not in EDITION_POWER_SCALES:
        raise HTTPException(status_code=400, detail=f"Invalid edition: {edition}")
    if floosball_app is None:
        raise HTTPException(status_code=503, detail="Application not initialized")

    pm = floosball_app.playerManager

    if playerId:
        playerObj = pm.getPlayerById(playerId)
        if playerObj is None:
            raise HTTPException(status_code=404, detail=f"Player {playerId} not found")
    else:
        # Pick a random player eligible for this edition's rating threshold
        import random as _rand
        from managers.cardManager import EDITION_THRESHOLDS
        threshold = EDITION_THRESHOLDS.get(edition, 0)
        eligible = [p for p in pm.activePlayers if round(p.playerRating) >= threshold]
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
                         x_admin_password: Optional[str] = Header(default=None)):
    """Grant Floobits to a user."""
    _check_admin_password(x_admin_password)
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
def admin_reroll_username(userId: int, x_admin_password: Optional[str] = Header(None)):
    """Admin: re-roll a user's username."""
    _check_admin_password(x_admin_password)
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
        ]
    draftOrder = []
    if sm.currentSeason and hasattr(sm.currentSeason, 'freeAgencyOrder'):
        for t in sm.currentSeason.freeAgencyOrder:
            draftOrder.append({
                "name": t.name,
                "city": getattr(t, 'city', ''),
                "abbr": getattr(t, 'abbr', t.name[:3].upper()),
                "id": getattr(t, 'id', None),
                "color": getattr(t, 'color', None),
                "complete": getattr(t, 'freeAgencyComplete', False),
            })
    transactions = getattr(sm, '_offseasonTransactions', [])
    faWindowOpen = getattr(sm, '_faWindowOpen', False)
    faWindowEnd = getattr(sm, '_faWindowEnd', None)
    # Always include FA pool during offseason so ballot rank markers work after window closes
    faPool = [
        {"id": p.id, "name": p.name, "position": p.position.name,
         "rating": round(p.playerRating, 1), "tier": p.playerTier.name}
        for p in pm.freeAgents
    ] if isOffseason else []

    # Include user's existing ballot if logged in
    existingBallot = None
    if user and isOffseason:
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

    return {
        "isOffseason": isOffseason, "freeAgents": faList, "draftOrder": draftOrder,
        "transactions": transactions, "faWindowOpen": faWindowOpen,
        "faWindowEnd": faWindowEnd, "faPool": faPool,
        "existingBallot": existingBallot, "faDirectives": faDirectives,
    }


# ============================================================================
# AUTH & USER ENDPOINTS
# ============================================================================

from api.auth import getCurrentUser as _getCurrentUser, getOptionalUser as _getOptionalUser
from database.models import User as _User, Team as _Team


@app.get("/api/users/me")
def get_current_user_profile(user: _User = Depends(_getCurrentUser)):
    """Get current user profile. Requires Bearer token."""
    from database.models import UserCurrency
    from database.connection import get_session
    session = get_session()
    try:
        currency = session.query(UserCurrency).filter_by(user_id=user.id).first()
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
        }
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
        session.commit()
        return {"ok": True, "emailOptOut": dbUser.email_opt_out}
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
            dbUser.favorite_team_id = req.teamId
            dbUser.pending_favorite_team_id = None
            if currentSeasonNum is not None and not offseason:
                dbUser.favorite_team_locked_season = currentSeasonNum
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
                    "createdAt": n.created_at.isoformat() if n.created_at else None,
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

        # Fall back to the most recent roster if no current-season roster exists
        if roster is None:
            roster = session.query(FantasyRoster).filter_by(
                user_id=user.id
            ).order_by(FantasyRoster.season.desc()).first()

        displaySeason = currentSeasonNum or (roster.season if roster else None)

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

        # If roster already has a FLEX player, ensure hasFlexSlot stays true
        if not hasFlexSlot and any(rp.slot == "FLEX" for rp in roster.players):
            hasFlexSlot = True

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
                "pointsAtLock": rp.points_at_lock,
                "seasonFantasyPoints": round(seasonFp, 1),
                "currentFantasyPoints": currentFp,
                "earnedPoints": earnedPoints,
            }
            rosterPlayers.append(entry)

        totalEarned = sum(p["earnedPoints"] for p in rosterPlayers)

        # Build swap history
        swapHistory = []
        for swap in roster.swaps:
            oldPlayerObj = session.get(Player, swap.old_player_id)
            newPlayerObj = session.get(Player, swap.new_player_id)
            swapHistory.append({
                "slot": swap.slot,
                "oldPlayerName": oldPlayerObj.name if oldPlayerObj else "Unknown",
                "newPlayerName": newPlayerObj.name if newPlayerObj else "Unknown",
                "swapWeek": swap.swap_week,
                "bankedFP": round(swap.banked_fp, 1),
            })

        # Check if games are actually running (Active/Final, not just Scheduled)
        gamesActive = _areGamesStarted()

        cardBonus = roster.card_bonus_points or 0.0
        return build_success_response({
            "roster": {
                "id": roster.id,
                "season": roster.season,
                "isLocked": roster.is_locked,
                "lockedAt": roster.locked_at.isoformat() if roster.locked_at else None,
                "totalPoints": totalEarned,
                "cardBonusPoints": cardBonus,
                "swapsAvailable": roster.swaps_available,
                "purchasedSwaps": roster.purchased_swaps,
                "hasFlexSlot": hasFlexSlot,
                "players": rosterPlayers,
                "swapHistory": swapHistory,
            },
            "season": displaySeason,
            "gamesActive": gamesActive,
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
    from database.models import FantasyRoster, FantasyRosterPlayer

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

        # Validate all 6 slots are filled
        filledSlots = {rp.slot for rp in roster.players}
        missingSlots = _VALID_SLOTS - filledSlots
        if missingSlots:
            raise HTTPException(status_code=400, detail=f"Missing slots: {', '.join(sorted(missingSlots))}")

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
        session.commit()
        return build_success_response({"message": "Roster locked", "lockedAt": roster.locked_at.isoformat()})
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

    # Validate games not active
    sm = floosball_app.seasonManager
    if sm.currentSeason and sm.currentSeason.activeGames:
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
        totalSwaps = roster.swaps_available + roster.purchased_swaps
        if totalSwaps < 1:
            raise HTTPException(status_code=409, detail="No swaps available")

        # Find the current player in this slot
        rosterPlayer = None
        for rp in roster.players:
            if rp.slot == req.slot:
                rosterPlayer = rp
                break
        if rosterPlayer is None:
            raise HTTPException(status_code=400, detail=f"No player in slot {req.slot}")

        # Validate new player not already on roster
        for rp in roster.players:
            if rp.player_id == req.newPlayerId:
                raise HTTPException(status_code=409, detail=f"{newPlayerObj.name} is already on your roster")

        # Calculate old player's earned FP
        oldPlayerId = rosterPlayer.player_id
        totalSeasonFP = session.query(func.coalesce(func.sum(WeeklyPlayerFP.fantasy_points), 0.0)).filter_by(
            player_id=oldPlayerId, season=currentSeasonNum
        ).scalar()
        bankedFP = max(0.0, float(totalSeasonFP) - rosterPlayer.points_at_lock)

        # Deduct 1 Floobit
        currencyRepo = CurrencyRepository(session)
        result = currencyRepo.spendFunds(
            userId=user.id, amount=1, transactionType="roster_swap",
            description=f"Roster swap: {req.slot}", season=currentSeasonNum,
        )
        if result is None:
            raise HTTPException(status_code=402, detail="Insufficient Floobits (need 1)")

        currentWeek = sm.currentSeason.currentWeek if sm.currentSeason else 0

        # Record the swap
        session.add(FantasyRosterSwap(
            roster_id=roster.id,
            slot=req.slot,
            old_player_id=oldPlayerId,
            new_player_id=req.newPlayerId,
            swap_week=currentWeek,
            banked_fp=round(bankedFP, 1),
        ))

        # Update the roster player — new player starts at 0 earned FP
        import json as _json
        newPlayerSeasonFP = session.query(func.coalesce(func.sum(WeeklyPlayerFP.fantasy_points), 0.0)).filter_by(
            player_id=req.newPlayerId, season=currentSeasonNum
        ).scalar()
        rosterPlayer.player_id = req.newPlayerId
        rosterPlayer.points_at_lock = float(newPlayerSeasonFP)

        # Consume purchased swaps first, then organic
        if roster.purchased_swaps > 0:
            roster.purchased_swaps -= 1
        else:
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
def get_fantasy_snapshot(season: Optional[int] = Query(default=None),
                         user: Optional[_User] = Depends(_getOptionalUser)):
    """Get full fantasy snapshot — single source of truth for roster + leaderboard."""
    if not floosball_app:
        return build_success_response(
            {"season": None, "week": 0, "gamesActive": False, "entries": []}
        )
    snapshot = floosball_app.fantasyTracker.getSnapshot(season)
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
def get_weekly_modifier():
    """Get the active weekly modifier for the current season/week."""
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


@app.get("/api/fantasy/leaderboard")
def get_fantasy_leaderboard(season: Optional[int] = Query(default=None)):
    """Get fantasy leaderboard for a season (defaults to current)."""
    return build_success_response(_computeLeaderboardData(season))


@app.get("/api/fantasy/leaderboard/weekly")
def get_fantasy_weekly_leaderboard(season: Optional[int] = Query(default=None)):
    """Get fantasy leaderboard broken down by week."""
    from database.connection import get_session
    from database.models import FantasyRoster, FantasyRosterPlayer, User, Game, GamePlayerStats, WeeklyCardBonus

    seasonNum = season if season is not None else _getCurrentSeasonNumber()
    if seasonNum is None:
        return build_success_response({"weeks": [], "season": None})

    sm = floosball_app.seasonManager if floosball_app else None
    currentWeek = sm.currentSeason.currentWeek if sm and sm.currentSeason else 0
    isCurrentSeason = seasonNum == (sm.currentSeason.seasonNumber if sm and sm.currentSeason else -1)
    gamesActive = isCurrentSeason and _areGamesStarted()

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
        storedBonuses = {}
        rosterIds = [info["roster"].id for info in rostersByUser.values()]
        if rosterIds:
            bonusRows = session.query(WeeklyCardBonus).filter(
                WeeklyCardBonus.roster_id.in_(rosterIds),
                WeeklyCardBonus.season == seasonNum,
            ).all()
            for row in bonusRows:
                storedBonuses.setdefault(row.user_id, {})[row.week] = row.bonus_fp

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

        # Inject card bonus into weekData for each user/week
        for userId in rostersByUser:
            userStoredBonuses = storedBonuses.get(userId, {})
            for week, bonusFP in userStoredBonuses.items():
                if week not in weekData:
                    weekData[week] = {}
                if userId not in weekData[week]:
                    weekData[week][userId] = {"weekPoints": 0.0, "cardBonusPoints": 0.0, "playerPoints": {}}
                weekData[week][userId]["cardBonusPoints"] = bonusFP
                weekData[week][userId]["weekPoints"] += bonusFP

            # Live card bonus for current active week
            if userId in liveCardBonusByUser:
                week = currentWeek
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
                    "createdAt": tx.created_at.isoformat() if tx.created_at else None,
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


class PromotionRequest(BaseModel):
    subjectCardId: int
    offeringCardId: int


class BlendRequest(BaseModel):
    offeringCardIds: List[int]


class TransplantRequest(BaseModel):
    targetCardId: int
    offeringCardId: int


@app.post("/api/cards/promote")
def promoteCard(req: PromotionRequest, user: _User = Depends(_getCurrentUser)):
    """Promotion: Sacrifice a higher-edition card to promote the subject's edition."""
    from database.connection import get_session
    from managers.cardManager import CardManager

    sm = floosball_app.seasonManager if floosball_app else None
    currentSeason = sm.currentSeason.seasonNumber if sm and sm.currentSeason else 0
    currentWeek = sm.currentSeason.currentWeek if sm and sm.currentSeason else 0
    cardManager = CardManager(floosball_app.serviceContainer if floosball_app else None)

    session = get_session()
    try:
        result = cardManager.promoteCard(session, user.id, req.subjectCardId,
                                         req.offeringCardId, currentSeason, currentWeek)
        session.commit()
        return build_success_response(result)
    except ValueError as e:
        session.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        session.rollback()
        if "database is locked" in str(e).lower():
            raise HTTPException(status_code=409, detail="Games are in progress — try again in a moment")
        logger.error(f"Card promotion failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to promote card")
    finally:
        session.close()


@app.post("/api/cards/promote/preview")
def previewPromotion(req: PromotionRequest, user: _User = Depends(_getCurrentUser)):
    """Preview Promotion result."""
    from database.connection import get_session
    from managers.cardManager import CardManager

    sm = floosball_app.seasonManager if floosball_app else None
    currentSeason = sm.currentSeason.seasonNumber if sm and sm.currentSeason else 0
    currentWeek = sm.currentSeason.currentWeek if sm and sm.currentSeason else 0
    cardManager = CardManager(floosball_app.serviceContainer if floosball_app else None)

    session = get_session()
    try:
        result = cardManager.previewPromotion(session, user.id, req.subjectCardId,
                                              req.offeringCardId, currentSeason, currentWeek)
        return build_success_response(result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        session.close()


@app.post("/api/cards/blend")
def blendCards(req: BlendRequest, user: _User = Depends(_getCurrentUser)):
    """The Blender: Sacrifice multiple cards to create one new random card."""
    from database.connection import get_session
    from managers.cardManager import CardManager

    sm = floosball_app.seasonManager if floosball_app else None
    currentSeason = sm.currentSeason.seasonNumber if sm and sm.currentSeason else 0
    currentWeek = sm.currentSeason.currentWeek if sm and sm.currentSeason else 0
    cardManager = CardManager(floosball_app.serviceContainer if floosball_app else None)

    session = get_session()
    try:
        result = cardManager.blendCards(session, user.id, req.offeringCardIds, currentSeason, currentWeek)
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
    """Preview The Blender result (shows resulting edition based on total value)."""
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


@app.post("/api/cards/transplant")
def transplantCard(req: TransplantRequest, user: _User = Depends(_getCurrentUser)):
    """Transplant: Sacrifice offering to transfer its effect onto the target."""
    from database.connection import get_session
    from managers.cardManager import CardManager

    sm = floosball_app.seasonManager if floosball_app else None
    currentSeason = sm.currentSeason.seasonNumber if sm and sm.currentSeason else 0
    currentWeek = sm.currentSeason.currentWeek if sm and sm.currentSeason else 0
    cardManager = CardManager(floosball_app.serviceContainer if floosball_app else None)

    session = get_session()
    try:
        result = cardManager.transplantCard(session, user.id, req.targetCardId,
                                            req.offeringCardId, currentSeason, currentWeek)
        session.commit()
        return build_success_response(result)
    except ValueError as e:
        session.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        session.rollback()
        if "database is locked" in str(e).lower():
            raise HTTPException(status_code=409, detail="Games are in progress — try again in a moment")
        logger.error(f"Card transplant failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to transplant effect")
    finally:
        session.close()


@app.post("/api/cards/transplant/preview")
def previewTransplant(req: TransplantRequest, user: _User = Depends(_getCurrentUser)):
    """Preview Transplant result and cost."""
    from database.connection import get_session
    from managers.cardManager import CardManager

    sm = floosball_app.seasonManager if floosball_app else None
    currentSeason = sm.currentSeason.seasonNumber if sm and sm.currentSeason else 0
    currentWeek = sm.currentSeason.currentWeek if sm and sm.currentSeason else 0
    cardManager = CardManager(floosball_app.serviceContainer if floosball_app else None)

    session = get_session()
    try:
        result = cardManager.previewTransplant(session, user.id, req.targetCardId,
                                               req.offeringCardId, currentSeason, currentWeek)
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

        # Auto-carry forward: if no cards equipped this week, copy from previous week
        if not equipped and currentWeek > 1:
            # If games are active, lockWeek() already ran — auto-carried cards must also be locked
            gamesActive = _areGamesStarted()
            prevEquipped = equippedRepo.getByUserWeek(user.id, currentSeason, currentWeek - 1)
            for prev in prevEquipped:
                # Verify card still exists and is active season
                userCard = session.get(UserCard, prev.user_card_id)
                if not userCard:
                    continue
                template = session.get(CardTemplate, userCard.card_template_id)
                if not template or template.season_created != currentSeason:
                    continue
                # Carry forward existing streak count — actual increment happens at week end
                prevStreak = getattr(prev, 'streak_count', 1) or 1
                equippedRepo.save(EquippedCard(
                    user_id=user.id,
                    season=currentSeason,
                    week=currentWeek,
                    slot_number=prev.slot_number,
                    user_card_id=prev.user_card_id,
                    locked=gamesActive,
                    streak_count=prevStreak,
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
            result.append({
                "slotNumber": eq.slot_number,
                "card": cardData,
                "playerId": template.player_id,
                "isMatch": template.player_id in rosterPlayerIds,
                "locked": eq.locked,
                "streakCount": getattr(eq, 'streak_count', 1) or 1,
                "cardTeamId": template.team_id,
                "templatePosition": template.position,
            })

        # Check if user qualifies for 6th slot: MVP card owned OR active temp_card_slot power-up
        from database.repositories.shop_repository import ShopPurchaseRepository
        mvpOwned = (
            session.query(UserCard.id)
            .join(CardTemplate, UserCard.card_template_id == CardTemplate.id)
            .filter(
                UserCard.user_id == user.id,
                CardTemplate.season_created == currentSeason,
                CardTemplate.classification.isnot(None),
                CardTemplate.classification.contains("mvp"),
            )
            .first()
        ) is not None
        if not mvpOwned:
            shopRepo = ShopPurchaseRepository(session)
            activeSlot = shopRepo.getActiveTempCardSlot(user.id, currentSeason, currentWeek)
            hasExtraSlot = activeSlot is not None
        else:
            hasExtraSlot = True

        return build_success_response({
            "equippedCards": result,
            "season": currentSeason,
            "week": currentWeek,
            "gamesActive": _areGamesStarted(),
            "gamesScheduled": _areGamesScheduled(),
            "hasExtraSlot": hasExtraSlot,
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

        # Clear existing and set new
        equippedRepo.deleteByUserWeek(user.id, currentSeason, currentWeek)
        for c in req.cards:
            equippedRepo.save(EquippedCard(
                user_id=user.id,
                season=currentSeason,
                week=currentWeek,
                slot_number=c.slotNumber,
                user_card_id=c.userCardId,
                locked=False,
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

            # Cards being unequipped (were equipped, now aren't)
            unequippedAllPro = prevAllProIds - newAllProIds
            for ucId in unequippedAllPro:
                uc = cardUserCards.get(ucId) or session.get(UserCard, ucId)
                if uc and roster.swaps_available > 0:
                    roster.swaps_available -= 1
                    uc.last_swap_grant_cycle = 0
                # If swap was used (swaps_available == 0), keep exhaustion

            # Cards being newly equipped
            freshAllPro = newAllProIds - prevAllProIds
            for ucId in freshAllPro:
                uc = cardUserCards.get(ucId) or session.get(UserCard, ucId)
                if uc and uc.last_swap_grant_cycle < swapCycle:
                    roster.swaps_available += 1
                    uc.last_swap_grant_cycle = swapCycle
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


@app.get("/api/packs/types")
def getPackTypes():
    """Get available pack types with costs."""
    from database.connection import get_session
    from database.repositories.card_repositories import PackTypeRepository

    session = get_session()
    try:
        packRepo = PackTypeRepository(session)
        packs = packRepo.getAll()
        return build_success_response({
            "packs": [
                {
                    "id": p.id,
                    "name": p.name,
                    "displayName": p.display_name,
                    "cost": p.cost,
                    "cardsPerPack": p.cards_per_pack,
                    "guaranteedRarity": p.guaranteed_rarity,
                    "description": p.description,
                }
                for p in packs
            ]
        })
    finally:
        session.close()


class OpenPackRequest(BaseModel):
    packTypeId: int


@app.post("/api/packs/open")
def openPack(req: OpenPackRequest, user: _User = Depends(_getCurrentUser)):
    """Buy and open a card pack."""
    from database.connection import get_session
    from managers.cardManager import CardManager

    sm = floosball_app.seasonManager if floosball_app else None
    currentSeason = sm.currentSeason.seasonNumber if sm and sm.currentSeason else 0

    cardManager = CardManager(floosball_app.serviceContainer if floosball_app else None)

    session = get_session()
    try:
        result = cardManager.openPack(session, user.id, req.packTypeId, currentSeason)
        session.commit()
        return build_success_response(result)
    except ValueError as e:
        session.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        session.rollback()
        logger.error(f"Pack opening failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to open pack")
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
        return build_success_response({"cards": featured, "currentSeason": currentSeason})
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
    from database.connection import get_session
    from managers.cardManager import CardManager

    sm = floosball_app.seasonManager if floosball_app else None
    currentSeason = sm.currentSeason.seasonNumber if sm and sm.currentSeason else 0

    cardManager = CardManager(floosball_app.serviceContainer if floosball_app else None)

    session = get_session()
    try:
        card = cardManager.buyFeaturedCard(session, user.id, req.templateId, currentSeason)
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

            elif slug == "shop_reroll":
                # 1 per refresh cycle
                if isScheduledMode:
                    purchasedCount = shopRepo.getPurchasesToday(user.id, slug)
                else:
                    purchasedCount = shopRepo.getPurchasesForCycle(
                        user.id, currentSeasonNum, slug, cycleStartWeek, cycleEndWeek
                    )
                item["purchased"] = purchasedCount
                item["limit"] = 1
                item["limitLabel"] = "per refresh"
                item["available"] = purchasedCount < 1 and currentWeek > 0

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
                raise HTTPException(status_code=409, detail="You already have an active flex slot")
            seasonCount = shopRepo.getSeasonPurchaseCount(user.id, currentSeasonNum, slug)
            seasonLimit = itemInfo.get("seasonLimit", 2)
            if seasonCount >= seasonLimit:
                raise HTTPException(status_code=409, detail=f"Season limit reached ({seasonLimit})")
            durationWeeks = itemInfo.get("durationWeeks", 4)
            # If games are active, the current partial week doesn't count against the duration
            gamesRunning = bool(getattr(sm.currentSeason, 'activeGames', None))
            expiresAtWeek = currentWeek + durationWeeks if gamesRunning else currentWeek + durationWeeks - 1

        elif slug == "temp_card_slot":
            if currentWeek < 1:
                raise HTTPException(status_code=400, detail="No active week")
            activeSlot = shopRepo.getActiveTempCardSlot(user.id, currentSeasonNum, currentWeek)
            if activeSlot:
                raise HTTPException(status_code=409, detail="You already have an active 6th card slot")
            seasonCount = shopRepo.getSeasonPurchaseCount(user.id, currentSeasonNum, slug)
            seasonLimit = itemInfo.get("seasonLimit", 2)
            if seasonCount >= seasonLimit:
                raise HTTPException(status_code=409, detail=f"Season limit reached ({seasonLimit})")
            durationWeeks = itemInfo.get("durationWeeks", 4)
            gamesRunning = bool(getattr(sm.currentSeason, 'activeGames', None))
            expiresAtWeek = currentWeek + durationWeeks if gamesRunning else currentWeek + durationWeeks - 1

        elif slug == "fortunes_favor":
            if currentWeek < 1:
                raise HTTPException(status_code=400, detail="No active week")
            activeFavor = shopRepo.getActiveFortunesFavor(user.id, currentSeasonNum, currentWeek)
            if activeFavor:
                raise HTTPException(status_code=409, detail="You already have Patronage active")
            seasonCount = shopRepo.getSeasonPurchaseCount(user.id, currentSeasonNum, slug)
            seasonLimit = itemInfo.get("seasonLimit", 2)
            if seasonCount >= seasonLimit:
                raise HTTPException(status_code=409, detail=f"Season limit reached ({seasonLimit})")
            durationWeeks = itemInfo.get("durationWeeks", 3)
            gamesRunning = bool(getattr(sm.currentSeason, 'activeGames', None))
            expiresAtWeek = currentWeek + durationWeeks if gamesRunning else currentWeek + durationWeeks - 1

        elif slug == "shop_reroll":
            if currentWeek < 1:
                raise HTTPException(status_code=400, detail="No active week")
            if isScheduledMode:
                count = shopRepo.getPurchasesToday(user.id, slug)
            else:
                count = shopRepo.getPurchasesForCycle(user.id, currentSeasonNum, slug, cycleStartWeek, cycleEndWeek)
            if count >= 1:
                raise HTTPException(status_code=409, detail="Already rerolled this period")

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

        shopRepo.createPurchase(
            userId=user.id, itemSlug=slug, season=currentSeasonNum,
            week=currentWeek, pricePaid=price, expiresAtWeek=expiresAtWeek,
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

        elif slug == "shop_reroll":
            # Delete unpurchased featured cards and regenerate
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
            responseData["featuredCards"] = featured

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
            # If games are running, current is a partial week that doesn't count
            gamesRunning = bool(getattr(sm.currentSeason, 'activeGames', None))
            weeksRemaining = activeFlex.expires_at_week - currentWeek + (0 if gamesRunning else 1)
            active.append({
                "slug": "temp_flex",
                "displayName": "Conscription",
                "expiresAtWeek": activeFlex.expires_at_week,
                "weeksRemaining": max(0, weeksRemaining),
                "expiring": weeksRemaining <= 1,
            })

        # Temp card slot
        activeCardSlot = shopRepo.getActiveTempCardSlot(user.id, currentSeasonNum, currentWeek)
        if activeCardSlot:
            gamesRunning = bool(getattr(sm.currentSeason, 'activeGames', None))
            weeksRemaining = activeCardSlot.expires_at_week - currentWeek + (0 if gamesRunning else 1)
            active.append({
                "slug": "temp_card_slot",
                "displayName": "Accession",
                "expiresAtWeek": activeCardSlot.expires_at_week,
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


class GmFaBallotRequest(BaseModel):
    rankings: List[int]


@app.post("/api/gm/vote")
def cast_gm_vote(req: GmVoteRequest, user: _User = Depends(_getCurrentUser)):
    """Cast a GM Mode vote for user's favorite team."""
    from database.connection import get_session
    from database.repositories.gm_repository import GmVoteRepository
    from database.repositories.card_repositories import CurrencyRepository
    from database.models import User, Player, Coach
    from constants import (
        GM_VOTE_TYPES, GM_VOTE_COST, GM_VOTES_PER_SEASON,
        GM_VOTES_PER_TYPE, GM_VOTES_PER_TARGET,
    )
    from managers.gmManager import GmManager

    if req.voteType not in GM_VOTE_TYPES:
        raise HTTPException(400, f"Invalid vote type: {req.voteType}")

    if req.voteType == "sign_fa":
        raise HTTPException(400, "Use POST /api/gm/fa-ballot for free agent votes")

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
        elif req.voteType == "hire_coach":
            if not req.targetPlayerId:
                raise HTTPException(400, "targetPlayerId (coach ID) required for hire_coach")
            coach = session.query(Coach).filter_by(id=req.targetPlayerId).first()
            if not coach or coach.team_id is not None:
                raise HTTPException(400, "Coach not available in the hiring pool")

        # Check limits
        voteRepo = GmVoteRepository(session)
        sm = floosball_app.seasonManager if floosball_app else None
        currentSeason = sm.currentSeason.seasonNumber if sm and sm.currentSeason else 0
        counts = voteRepo.getUserVoteCounts(user.id, currentSeason)

        if counts["total"] >= GM_VOTES_PER_SEASON:
            raise HTTPException(400, f"Season vote limit reached ({GM_VOTES_PER_SEASON})")
        if counts["perType"].get(req.voteType, 0) >= GM_VOTES_PER_TYPE:
            raise HTTPException(400, f"Vote type limit reached ({GM_VOTES_PER_TYPE} per type)")
        targetKey = f"{req.voteType}:{req.targetPlayerId or 'none'}"
        if counts["perTarget"].get(targetKey, 0) >= GM_VOTES_PER_TARGET:
            raise HTTPException(400, f"Target vote limit reached ({GM_VOTES_PER_TARGET} per target)")

        # Escalating cost: base * 2^(votes already cast for this type)
        baseCost = GM_VOTE_COST[req.voteType]
        typeCount = counts["perType"].get(req.voteType, 0)
        cost = baseCost * (2 ** typeCount)
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
            targetPlayerId=req.targetPlayerId,
        )
        session.commit()

        # Get current tally for response (use per-team engaged fan count)
        engagedFans = voteRepo.getEngagedVoterCount(teamId, currentSeason)
        tallies = voteRepo.getVoteTallies(teamId, currentSeason)
        targetTally = next(
            (t for t in tallies
             if t["voteType"] == req.voteType
             and t["targetPlayerId"] == req.targetPlayerId),
            {"votes": 1}
        )
        threshold = GmManager.calculateThreshold(engagedFans, req.voteType)
        probability = GmManager.calculateProbability(targetTally["votes"], threshold)

        return build_success_response({
            "voteId": vote.id,
            "voteType": req.voteType,
            "targetPlayerId": req.targetPlayerId,
            "costPaid": cost,
            "currentVotes": targetTally["votes"],
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
        enriched = []
        for t in tallies:
            threshold = GmManager.calculateThreshold(engagedFans, t["voteType"])
            probability = GmManager.calculateProbability(t["votes"], threshold)
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
            }

        # Available coaches in pool
        availableCoaches = []
        coachPool = session.query(Coach).filter(Coach.team_id == None).all()
        for c in coachPool:
            availableCoaches.append({
                "id": c.id,
                "name": c.name,
                "overallRating": c.overall_rating,
                "offensiveMind": c.offensive_mind,
                "defensiveMind": c.defensive_mind,
                "adaptability": c.adaptability,
                "aggressiveness": c.aggressiveness,
                "clockManagement": c.clock_management,
                "playerDevelopment": c.player_development,
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
            })

        # Expiring contract players (for resign votes)
        expiringPlayers = [p for p in rosteredPlayers if p["termRemaining"] == 1]

        return build_success_response({
            "teamId": teamId,
            "coach": coachInfo,
            "availableCoaches": availableCoaches,
            "rosteredPlayers": rosteredPlayers,
            "expiringPlayers": expiringPlayers,
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

        openSlots = []
        slotPosMap = {'qb': 'QB', 'rb': 'RB', 'wr1': 'WR', 'wr2': 'WR', 'te': 'TE', 'k': 'K'}
        if favTeam:
            for slot, posName in slotPosMap.items():
                if favTeam.rosterDict.get(slot) is None:
                    openSlots.append({"slot": slot, "position": posName})

        # Get season number for stats lookup
        seasonNum = sm.currentSeason.seasonNumber if sm and sm.currentSeason else 1

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
            if not row:
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

        players = []
        for p in pm.freeAgents:
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
            })

        return build_success_response({"openSlots": openSlots, "players": players})
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

        # Check if FA window is open
        faWindowOpen = getattr(sm, '_faWindowOpen', False) if sm else False
        if not faWindowOpen:
            raise HTTPException(400, "FA voting window is not currently open")

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
            rankings=req.rankings, costPaid=costPaid,
        )
        session.commit()

        return build_success_response({
            "ballotId": ballot.id,
            "rankings": req.rankings,
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
                    "costPaid": v.cost_paid,
                    "createdAt": v.created_at.isoformat() if v.created_at else None,
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
    from database.connection import get_session
    from database.repositories.gm_repository import GmVoteRepository
    from database.models import User

    session = get_session()
    try:
        dbUser = session.query(User).filter_by(id=user.id).first()
        if not dbUser or not dbUser.favorite_team_id:
            return build_success_response({"results": []})

        sm = floosball_app.seasonManager if floosball_app else None
        currentSeason = sm.currentSeason.seasonNumber if sm and sm.currentSeason else 0
        voteRepo = GmVoteRepository(session)
        results = voteRepo.getResults(dbUser.favorite_team_id, currentSeason)

        return build_success_response({
            "teamId": dbUser.favorite_team_id,
            "season": currentSeason,
            "results": [
                {
                    "id": r.id,
                    "voteType": r.vote_type,
                    "targetPlayerId": r.target_player_id,
                    "totalVotes": r.total_votes,
                    "threshold": r.threshold,
                    "probability": r.success_probability,
                    "outcome": r.outcome,
                    "details": r.details,
                    "resolvedAt": r.resolved_at.isoformat() if r.resolved_at else None,
                }
                for r in results
            ],
        })
    finally:
        session.close()


# ============================================================================
# PICK-EM ("PROGNOSTICATIONS")
# ============================================================================


@app.get("/api/pickem/week")
def get_pickem_week(user: Optional[_User] = Depends(_getOptionalUser)):
    """Get this week's matchups with the user's existing picks (if any).
    Each game has per-game pickability and current multiplier based on quarter.
    """
    if floosball_app is None:
        raise HTTPException(503, "Application not initialized")

    from constants import PICKEM_QUARTER_MULTIPLIERS

    sm = floosball_app.seasonManager
    currentSeason = sm.currentSeason
    if currentSeason is None:
        return build_success_response({"season": 0, "week": 0, "games": [], "weekSummary": None})

    seasonNum = currentSeason.seasonNumber
    week = currentSeason.currentWeek
    schedule = currentSeason.schedule

    # Build matchups from schedule
    weekGames = []
    if isinstance(week, int) and 0 < week <= len(schedule):
        scheduleGames = schedule[week - 1].get('games', [])
        activeGames = currentSeason.activeGames
        for i, game in enumerate(scheduleGames):
            # Use active game object if available (has live status/quarter)
            liveGame = activeGames[i] if activeGames and i < len(activeGames) else game
            rawStatus = getattr(liveGame, 'status', None)
            # Compare by enum value to avoid identity issues across module reloads
            statusVal = rawStatus.value if hasattr(rawStatus, 'value') else None

            # Determine per-game pickability and current multiplier
            if statusVal == 3:  # Final
                pickable = False
                currentMultiplier = 0.0
            elif statusVal == 2:  # Active
                pickable = True
                quarter = getattr(liveGame, 'currentQuarter', 1)
                currentMultiplier = PICKEM_QUARTER_MULTIPLIERS.get(quarter, 0.2)
            else:
                # Scheduled (1) or not yet set
                pickable = True
                currentMultiplier = PICKEM_QUARTER_MULTIPLIERS.get(0, 1.0)

            matchup = {
                "gameIndex": i,
                "homeTeam": {
                    "id": liveGame.homeTeam.id,
                    "name": liveGame.homeTeam.name,
                    "abbr": liveGame.homeTeam.abbr,
                    "color": liveGame.homeTeam.color,
                    "record": f"{liveGame.homeTeam.seasonTeamStats.get('wins', 0)}-{liveGame.homeTeam.seasonTeamStats.get('losses', 0)}",
                    "elo": getattr(liveGame.homeTeam, 'elo', 1500),
                },
                "awayTeam": {
                    "id": liveGame.awayTeam.id,
                    "name": liveGame.awayTeam.name,
                    "abbr": liveGame.awayTeam.abbr,
                    "color": liveGame.awayTeam.color,
                    "record": f"{liveGame.awayTeam.seasonTeamStats.get('wins', 0)}-{liveGame.awayTeam.seasonTeamStats.get('losses', 0)}",
                    "elo": getattr(liveGame.awayTeam, 'elo', 1500),
                },
                "userPick": None,
                "pointsMultiplier": None,
                "pickable": pickable,
                "currentMultiplier": currentMultiplier,
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

    return build_success_response({
        "season": seasonNum,
        "week": week,
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

    from constants import PICKEM_QUARTER_MULTIPLIERS

    gameIndex = body.get("gameIndex")
    pickedTeamId = body.get("pickedTeamId")
    if gameIndex is None or pickedTeamId is None:
        raise HTTPException(400, "gameIndex and pickedTeamId required")

    sm = floosball_app.seasonManager
    currentSeason = sm.currentSeason
    if currentSeason is None:
        raise HTTPException(400, "No active season")

    seasonNum = currentSeason.seasonNumber
    week = currentSeason.currentWeek
    schedule = currentSeason.schedule

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

    # Per-game lock: only Final games are unpickable
    rawStatus = getattr(liveGame, 'status', None)
    statusVal = rawStatus.value if hasattr(rawStatus, 'value') else None
    if statusVal == 3:  # Final
        raise HTTPException(409, "This game has ended — pick cannot be changed")

    # Determine multiplier based on game quarter
    if statusVal == 2:  # Active
        quarter = getattr(liveGame, 'currentQuarter', 1)
        pointsMultiplier = PICKEM_QUARTER_MULTIPLIERS.get(quarter, 0.2)
    else:
        # Scheduled (pre-game) — full multiplier
        pointsMultiplier = PICKEM_QUARTER_MULTIPLIERS.get(0, 1.0)

    homeTeamId = game.homeTeam.id
    awayTeamId = game.awayTeam.id

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
        )
        session.commit()

        # Count how many picks user has made this week
        allPicks = pickemRepo.getUserPicks(user.id, seasonNum, week)
        return build_success_response({
            "pick": {
                "gameIndex": pick.game_index,
                "pickedTeamId": pick.picked_team_id,
                "pointsMultiplier": pick.points_multiplier,
            },
            "weekProgress": {"picked": len(allPicks), "total": len(scheduleGames)},
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
    week = currentSeason.currentWeek

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

    from database.connection import get_session
    from database.repositories.pickem_repository import PickEmRepository
    from database.models import User
    session = get_session()
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

        return build_success_response({
            "season": {"entries": seasonEntries},
            "week": {"week": weeklyWeek, "entries": _buildEntries(weekRows)},
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
# HEALTH CHECK
# ============================================================================

@app.get("/health")
async def health_check():
    """API health check endpoint"""
    return {
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'app_initialized': floosball_app is not None
    }


# ============================================================================
# HELPER FUNCTION TO SET APPLICATION REFERENCE
# ============================================================================

def set_floosball_app(app_instance):
    """Set the FloosballApplication instance for API access"""
    global floosball_app
    floosball_app = app_instance
    logger.info("FloosballApplication reference set in API")
