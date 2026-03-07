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
from datetime import datetime

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
    "http://floosball.com"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "x-admin-password"],
)

# Global reference to FloosballApplication (set during startup)
floosball_app = None


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
        team_dict['history'] = team.statArchive
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
async def get_team_avatar(team_id: int, size: int = Query(default=32, ge=16, le=256)):
    """
    Generate and return SVG avatar for a team
    Avatars are cached for performance and persisted to disk
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
        
        # Generate SVG (from cache if available)
        svg = avatarGen.generateTeamAvatar(
            team.name,
            primaryColor,
            secondaryColor,
            tertiaryColor,
            size,
            team.id
        )
        
        # Return as SVG with proper CORS headers
        return Response(
            content=svg,
            media_type="image/svg+xml",
            headers={
                "Cache-Control": "public, max-age=31536000, immutable",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, OPTIONS",
                "Access-Control-Allow-Headers": "*"
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating avatar for team {team_id}: {e}")
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
        
        if current_season is None or not hasattr(current_season, 'activeGames') or current_season.activeGames is None:
            return []
        
        # Compute isFeatured for each game: elite matchup (both ELO >= 1570)
        # OR playoff bubble battle (both teams near the 6-spot cutline, late season only)
        PLAYOFF_SPOTS = 6
        ELITE_ELO = 1570
        BUBBLE_WEEK_MIN = 18  # bubble battle only meaningful in the final stretch
        currentWeek = getattr(current_season, 'currentWeek', 0)
        isRegularSeason = 1 <= currentWeek <= 28
        lateRegularSeason = isRegularSeason and currentWeek >= BUBBLE_WEEK_MIN

        teamLeaguePos = {}   # {team_id: 1-indexed position in their league}
        teamLeagueName = {}  # {team_id: league name} for same-league check
        for league in floosball_app.leagueManager.leagues:
            sortedTeams = sorted(league.teamList,
                                 key=lambda t: (-t.seasonTeamStats['wins'], t.seasonTeamStats['losses']))
            for pos, team in enumerate(sortedTeams, 1):
                teamLeaguePos[team.id] = pos
                teamLeagueName[team.id] = league.name

        for game in current_season.activeGames:
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
        for game in current_season.activeGames:
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
        if hasattr(current_season, 'activeGames'):
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
        
        return build_success_response({
            'season_number': current_season.seasonNumber,
            'current_week': current_season.currentWeek,
            'current_week_text': current_season.currentWeekText,
            'is_complete': current_season.isComplete,
            'active_games': activeGameIds,
            'completed_games': completedGameIds,
            'champion': TeamResponseBuilder.buildBasicTeamDict(current_season.champion) if current_season.champion else None,
            'mvp': current_season.mvp if hasattr(current_season, 'mvp') and current_season.mvp else None
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


@app.get("/api/offseason")
async def get_offseason_info():
    """Offseason state: free agents, draft order"""
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
                "abbr": getattr(t, 'abbr', t.name[:3].upper()),
                "id": getattr(t, 'id', None),
            })
    transactions = getattr(sm, '_offseasonTransactions', [])
    return {"isOffseason": isOffseason, "freeAgents": faList, "draftOrder": draftOrder, "transactions": transactions}


# ============================================================================
# AUTH & USER ENDPOINTS
# ============================================================================

from api.auth import getCurrentUser as _getCurrentUser
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
        }
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
    from database.models import FantasyRoster, FantasyRosterPlayer

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

        if roster is None:
            return build_success_response({"roster": None, "season": displaySeason})

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

        cardBonus = roster.card_bonus_points or 0.0
        return build_success_response({
            "roster": {
                "id": roster.id,
                "season": roster.season,
                "isLocked": roster.is_locked,
                "lockedAt": roster.locked_at.isoformat() if roster.locked_at else None,
                "totalPoints": totalEarned,
                "cardBonusPoints": cardBonus,
                "players": rosterPlayers,
            },
            "season": displaySeason,
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
    from database.models import FantasyRoster, FantasyRosterPlayer

    currentSeasonNum = _getCurrentSeasonNumber()
    if currentSeasonNum is None:
        raise HTTPException(status_code=400, detail="No active season")

    # Validate slots
    slots = [p.slot for p in req.players]
    for slot in slots:
        if slot not in _VALID_SLOTS:
            raise HTTPException(status_code=400, detail=f"Invalid slot: {slot}. Must be one of: {', '.join(sorted(_VALID_SLOTS))}")
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
        expectedPos = _SLOT_POSITION_MAP[rp.slot]
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

        # Snapshot season fantasy points for each player (excluding in-progress game FP
        # so users earn all points from the current week's games regardless of lock timing)
        for rp in roster.players:
            playerObj = floosball_app.playerManager.getPlayerById(rp.player_id)
            if playerObj:
                rp.points_at_lock = playerObj.seasonStatsDict.get('fantasyPoints', 0)

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
    """Compute live card bonuses for the current active week. Returns {userId: bonusFP}."""
    from database.repositories.card_repositories import EquippedCardRepository
    from managers.cardEffectCalculator import (
        calculateWeekCardBonuses, CardCalcContext, _countPlayerTds
    )

    sm = floosball_app.seasonManager if floosball_app else None
    if not sm or not sm.currentSeason:
        return {}

    seasonNum = sm.currentSeason.seasonNumber
    currentWeek = sm.currentSeason.currentWeek

    equippedRepo = EquippedCardRepository(session)
    allEquipped = equippedRepo.getAllForWeek(seasonNum, currentWeek)
    equippedByUser = {}
    for eq in allEquipped:
        equippedByUser.setdefault(eq.user_id, []).append(eq)

    if not equippedByUser:
        return {}

    # Build winning team IDs from live active games
    winningTeamIds = set()
    if sm.currentSeason.activeGames:
        for game in sm.currentSeason.activeGames:
            homeScore = getattr(game, 'homeScore', 0) or 0
            awayScore = getattr(game, 'awayScore', 0) or 0
            if homeScore > awayScore:
                winningTeamIds.add(game.homeTeam.id if hasattr(game.homeTeam, 'id') else 0)
            elif awayScore > homeScore:
                winningTeamIds.add(game.awayTeam.id if hasattr(game.awayTeam, 'id') else 0)

    from database.models import User
    result = {}
    for roster in rosters:
        userId = roster.user_id
        if userId not in equippedByUser:
            continue
        userEquipped = equippedByUser[userId]

        rosterPlayerIds = {rp.player_id for rp in roster.players}

        # Build live player stats
        livePlayerStats = {}
        weekGameFP = 0.0
        rosterTotalTds = 0
        rosterPlayerRatings = {}

        for rp in roster.players:
            pObj = floosball_app.playerManager.getPlayerById(rp.player_id) if floosball_app else None
            if pObj:
                stats = _liveStatsToDbFormat(pObj.gameStatsDict)
                weeklyFP = max(0, _getPlayerLiveFantasyPoints(pObj) - rp.points_at_lock)
                stats["fantasyPoints"] = weeklyFP
                livePlayerStats[rp.player_id] = stats
                weekGameFP += weeklyFP
                rosterTotalTds += _countPlayerTds(stats)
                rosterPlayerRatings[rp.player_id] = getattr(pObj, 'playerRating', 60) or 60

        # Card player stats (if not on roster)
        for eq in userEquipped:
            cardPlayerId = eq.user_card.card_template.player_id
            if cardPlayerId not in livePlayerStats:
                cardPlayerObj = floosball_app.playerManager.getPlayerById(cardPlayerId) if floosball_app else None
                if cardPlayerObj:
                    livePlayerStats[cardPlayerId] = _liveStatsToDbFormat(cardPlayerObj.gameStatsDict)

        streakCounts = {eq.id: getattr(eq, 'streak_count', 1) for eq in userEquipped}
        allEquippedEditions = {eq.user_card.card_template.edition for eq in userEquipped}
        matchedCardCount = sum(
            1 for eq in userEquipped
            if eq.user_card.card_template.player_id in rosterPlayerIds
        )

        # Position average FP
        positionFPSums = {}
        positionFPCounts = {}
        for rp in roster.players:
            pObj = floosball_app.playerManager.getPlayerById(rp.player_id) if floosball_app else None
            if pObj:
                pos = pObj.position.value if hasattr(pObj.position, 'value') else int(pObj.position)
                fp = livePlayerStats.get(rp.player_id, {}).get("fantasyPoints", 0)
                positionFPSums[pos] = positionFPSums.get(pos, 0) + fp
                positionFPCounts[pos] = positionFPCounts.get(pos, 0) + 1

        positionAverageFP = {}
        for pid in livePlayerStats:
            pObj = floosball_app.playerManager.getPlayerById(pid) if floosball_app else None
            if pObj:
                pos = pObj.position.value if hasattr(pObj.position, 'value') else int(pObj.position)
                if positionFPCounts.get(pos, 0) > 0:
                    positionAverageFP[pid] = positionFPSums[pos] / positionFPCounts[pos]

        rosterUser = session.get(User, userId)
        calcCtx = CardCalcContext(
            rosterPlayerIds=rosterPlayerIds,
            weekPlayerStats=livePlayerStats,
            weekRawFP=weekGameFP,
            rosterPlayerRatings=rosterPlayerRatings,
            winningTeamIds=winningTeamIds,
            rosterTotalTds=rosterTotalTds,
            positionAverageFP=positionAverageFP,
            streakCounts=streakCounts,
            allEquippedEditions=allEquippedEditions,
            matchedCardCount=matchedCardCount,
            userFavoriteTeamId=rosterUser.favorite_team_id if rosterUser else None,
        )

        calcResult = calculateWeekCardBonuses(userEquipped, calcCtx)
        if calcResult.totalBonusFP > 0:
            result[userId] = calcResult.totalBonusFP

    return result


def _computeLeaderboardData(seasonNum: int = None) -> dict:
    """Compute leaderboard data for a season. Used by both the REST endpoint and WS broadcast."""
    from database.connection import get_session
    from database.models import FantasyRoster, User
    from database.repositories.card_repositories import EquippedCardRepository
    from managers.cardEffectCalculator import (
        calculateWeekCardBonuses, CardCalcContext, _countPlayerTds
    )

    if seasonNum is None:
        seasonNum = _getCurrentSeasonNumber()
    if seasonNum is None:
        return {"leaderboard": [], "season": None}

    sm = floosball_app.seasonManager if floosball_app else None
    currentWeek = sm.currentSeason.currentWeek if sm and sm.currentSeason else 0
    isCurrentSeason = seasonNum == (sm.currentSeason.seasonNumber if sm and sm.currentSeason else -1)
    gamesActive = isCurrentSeason and bool(sm and sm.currentSeason and sm.currentSeason.activeGames)

    session = get_session()
    try:
        rosters = session.query(FantasyRoster).filter_by(
            season=seasonNum, is_locked=True
        ).all()

        # Pre-fetch equipped cards for live card bonus during active games
        equippedByUser = {}
        if gamesActive:
            equippedRepo = EquippedCardRepository(session)
            allEquipped = equippedRepo.getAllForWeek(seasonNum, currentWeek)
            for eq in allEquipped:
                equippedByUser.setdefault(eq.user_id, []).append(eq)

        # Build winning team IDs from live active games
        winningTeamIds = set()
        if gamesActive and sm and sm.currentSeason and sm.currentSeason.activeGames:
            for game in sm.currentSeason.activeGames:
                homeScore = getattr(game, 'homeScore', 0) or 0
                awayScore = getattr(game, 'awayScore', 0) or 0
                if homeScore > awayScore:
                    winningTeamIds.add(game.homeTeam.id if hasattr(game.homeTeam, 'id') else 0)
                elif awayScore > homeScore:
                    winningTeamIds.add(game.awayTeam.id if hasattr(game.awayTeam, 'id') else 0)

        entries = []
        for roster in rosters:
            rosterUser = session.get(User, roster.user_id)
            rosterPlayers = []
            totalEarned = 0.0
            weekPlayerFP = 0.0
            rosterPlayerIds = set()

            for rp in roster.players:
                playerObj = floosball_app.playerManager.getPlayerById(rp.player_id) if floosball_app else None
                currentFp = _getPlayerLiveFantasyPoints(playerObj) if playerObj else 0
                earned = max(0, currentFp - rp.points_at_lock)
                totalEarned += earned
                rosterPlayerIds.add(rp.player_id)
                # Current week's live game FP (only meaningful during active games)
                gameFP = playerObj.gameStatsDict.get('fantasyPoints', 0) if playerObj else 0
                weekPlayerFP += gameFP
                rosterPlayers.append({
                    "slot": rp.slot,
                    "playerId": rp.player_id,
                    "playerName": playerObj.name if playerObj else "Unknown",
                    "position": playerObj.position.name if playerObj and hasattr(playerObj.position, 'name') else "",
                    "teamAbbr": getattr(playerObj.team, 'abbr', '') if playerObj and hasattr(playerObj.team, 'name') else "",
                    "earnedPoints": round(earned, 1),
                    "weekFP": round(gameFP, 1),
                })

            # Stored card bonus from completed weeks
            storedCardBonus = roster.card_bonus_points or 0.0

            # Compute live card bonus for current week during active games
            liveCardBonus = 0.0
            if gamesActive and roster.user_id in equippedByUser:
                userEquipped = equippedByUser[roster.user_id]

                # Build live weekPlayerStats from game data
                livePlayerStats = {}
                weekGameFP = 0.0
                rosterTotalTds = 0
                rosterPlayerRatings = {}

                for rp in roster.players:
                    pObj = floosball_app.playerManager.getPlayerById(rp.player_id) if floosball_app else None
                    if pObj:
                        stats = _liveStatsToDbFormat(pObj.gameStatsDict)
                        # Use totalFP - pointsAtLock for stable weekly FP
                        # (gameStatsDict.fantasyPoints gets zeroed by _accumulatePostgameStats)
                        weeklyFP = max(0, _getPlayerLiveFantasyPoints(pObj) - rp.points_at_lock)
                        stats["fantasyPoints"] = weeklyFP
                        livePlayerStats[rp.player_id] = stats
                        weekGameFP += weeklyFP
                        rosterTotalTds += _countPlayerTds(stats)
                        rosterPlayerRatings[rp.player_id] = getattr(pObj, 'playerRating', 60) or 60

                # Also add card player stats if not on roster
                for eq in userEquipped:
                    cardPlayerId = eq.user_card.card_template.player_id
                    if cardPlayerId not in livePlayerStats:
                        cardPlayerObj = floosball_app.playerManager.getPlayerById(cardPlayerId) if floosball_app else None
                        if cardPlayerObj:
                            livePlayerStats[cardPlayerId] = _liveStatsToDbFormat(cardPlayerObj.gameStatsDict)

                streakCounts = {eq.id: getattr(eq, 'streak_count', 1) for eq in userEquipped}
                allEquippedEditions = {eq.user_card.card_template.edition for eq in userEquipped}
                matchedCardCount = sum(
                    1 for eq in userEquipped
                    if eq.user_card.card_template.player_id in rosterPlayerIds
                )

                # Build position average FP (approximate from roster players)
                positionFPSums = {}
                positionFPCounts = {}
                for rp in roster.players:
                    pObj = floosball_app.playerManager.getPlayerById(rp.player_id) if floosball_app else None
                    if pObj:
                        pos = pObj.position.value if hasattr(pObj.position, 'value') else int(pObj.position)
                        fp = livePlayerStats.get(rp.player_id, {}).get("fantasyPoints", 0)
                        positionFPSums[pos] = positionFPSums.get(pos, 0) + fp
                        positionFPCounts[pos] = positionFPCounts.get(pos, 0) + 1

                positionAverageFP = {}
                for pid in livePlayerStats:
                    pObj = floosball_app.playerManager.getPlayerById(pid) if floosball_app else None
                    if pObj:
                        pos = pObj.position.value if hasattr(pObj.position, 'value') else int(pObj.position)
                        if positionFPCounts.get(pos, 0) > 0:
                            positionAverageFP[pid] = positionFPSums[pos] / positionFPCounts[pos]

                calcCtx = CardCalcContext(
                    rosterPlayerIds=rosterPlayerIds,
                    weekPlayerStats=livePlayerStats,
                    weekRawFP=weekGameFP,
                    rosterPlayerRatings=rosterPlayerRatings,
                    winningTeamIds=winningTeamIds,
                    rosterTotalTds=rosterTotalTds,
                    positionAverageFP=positionAverageFP,
                    streakCounts=streakCounts,
                    allEquippedEditions=allEquippedEditions,
                    matchedCardCount=matchedCardCount,
                    userFavoriteTeamId=rosterUser.favorite_team_id if rosterUser else None,
                )

                result = calculateWeekCardBonuses(userEquipped, calcCtx)
                liveCardBonus = result.totalBonusFP

            totalCardBonus = round(storedCardBonus + liveCardBonus, 1)
            entries.append({
                "userId": roster.user_id,
                "username": rosterUser.username or rosterUser.email if rosterUser else "Unknown",
                "totalPoints": round(totalEarned + totalCardBonus, 1),
                "rawPoints": round(totalEarned, 1),
                "cardBonusPoints": totalCardBonus,
                "weekPlayerFP": round(weekPlayerFP, 1),
                "weekCardBonus": round(liveCardBonus, 1),
                "lockedAt": roster.locked_at.isoformat() if roster.locked_at else None,
                "players": rosterPlayers,
            })

        # Sort by total points descending
        entries.sort(key=lambda e: e["totalPoints"], reverse=True)
        for i, entry in enumerate(entries, 1):
            entry["rank"] = i

        return {"leaderboard": entries, "season": seasonNum}
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
    gamesActive = isCurrentSeason and bool(sm and sm.currentSeason and sm.currentSeason.activeGames)

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
                entries.append({
                    "userId": userId,
                    "username": info["username"],
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

    cardManager = CardManager(floosball_app.serviceContainer if floosball_app else None)

    session = get_session()
    try:
        cardRepo = UserCardRepository(session)
        cards = cardRepo.getByUser(user.id)

        result = []
        for card in cards:
            tpl = card.card_template
            if edition and tpl.edition != edition:
                continue
            if position is not None and tpl.position != position:
                continue
            if activeOnly and tpl.season_created != currentSeason:
                continue
            result.append(cardManager.serializeCard(card, currentSeason))

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

    cardManager = CardManager(floosball_app.serviceContainer if floosball_app else None)

    session = get_session()
    try:
        result = cardManager.sellCards(session, user.id, req.userCardIds, currentSeason)
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
            gamesActive = bool(sm and sm.currentSeason and sm.currentSeason.activeGames)
            prevEquipped = equippedRepo.getByUserWeek(user.id, currentSeason, currentWeek - 1)
            for prev in prevEquipped:
                # Verify card still exists and is active season
                userCard = session.get(UserCard, prev.user_card_id)
                if not userCard:
                    continue
                template = session.get(CardTemplate, userCard.card_template_id)
                if not template or template.season_created != currentSeason:
                    continue
                # Streak tracking: if same card in same slot, increment streak
                prevStreak = getattr(prev, 'streak_count', 1) or 1
                newStreak = prevStreak + 1 if prev.user_card_id == prev.user_card_id else 1
                equippedRepo.save(EquippedCard(
                    user_id=user.id,
                    season=currentSeason,
                    week=currentWeek,
                    slot_number=prev.slot_number,
                    user_card_id=prev.user_card_id,
                    locked=gamesActive,
                    streak_count=newStreak,
                ))
            session.commit()
            equipped = equippedRepo.getByUserWeek(user.id, currentSeason, currentWeek)

        # Get roster player IDs for match detection
        roster = session.query(FantasyRoster).filter_by(
            user_id=user.id, season=currentSeason, is_locked=True
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

        gamesActive = bool(sm and sm.currentSeason and sm.currentSeason.activeGames)
        return build_success_response({
            "equippedCards": result,
            "season": currentSeason,
            "week": currentWeek,
            "gamesActive": gamesActive,
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
    confirm: bool = Query(default=False),
    user: _User = Depends(_getCurrentUser),
):
    """Set the user's equipped cards for the current week."""
    from database.connection import get_session
    from database.models import FantasyRoster, EquippedCard, UserCard, CardTemplate
    from database.repositories.card_repositories import EquippedCardRepository

    sm = floosball_app.seasonManager if floosball_app else None
    currentSeason = sm.currentSeason.seasonNumber if sm and sm.currentSeason else 0
    currentWeek = sm.currentSeason.currentWeek if sm and sm.currentSeason else 0

    # Validate slot numbers
    for c in req.cards:
        if c.slotNumber not in (1, 2, 3, 4, 5):
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
        # Verify roster is locked
        roster = session.query(FantasyRoster).filter_by(
            user_id=user.id, season=currentSeason, is_locked=True
        ).first()
        if not roster:
            raise HTTPException(status_code=400, detail="You must lock your roster before equipping cards")

        equippedRepo = EquippedCardRepository(session)

        # Check if games are active — require confirmation to equip (will be locked immediately)
        gamesActive = bool(sm and sm.currentSeason and sm.currentSeason.activeGames)
        if gamesActive:
            # If cards are already locked, no changes allowed at all
            existing = equippedRepo.getByUserWeek(user.id, currentSeason, currentWeek)
            if any(e.locked for e in existing):
                raise HTTPException(status_code=409, detail="Cards are locked for this week")
            # Otherwise require confirmation before locking
            if not confirm:
                raise HTTPException(status_code=409, detail="CONFIRM_LOCK_REQUIRED")

        # Check if cards are already locked for this week (non-active-game case)
        if not gamesActive:
            existing = equippedRepo.getByUserWeek(user.id, currentSeason, currentWeek)
            if any(e.locked for e in existing):
                raise HTTPException(status_code=409, detail="Cards are locked for this week")

        # Validate each card belongs to user and is active
        for c in req.cards:
            userCard = session.query(UserCard).filter_by(id=c.userCardId, user_id=user.id).first()
            if not userCard:
                raise HTTPException(status_code=400, detail=f"Card {c.userCardId} not found")
            template = session.query(CardTemplate).filter_by(id=userCard.card_template_id).first()
            if not template or template.season_created != currentSeason:
                raise HTTPException(status_code=400, detail=f"Card {c.userCardId} is not active this season")

        # Clear existing and set new (lock immediately if games are active)
        equippedRepo.deleteByUserWeek(user.id, currentSeason, currentWeek)
        for c in req.cards:
            equippedRepo.save(EquippedCard(
                user_id=user.id,
                season=currentSeason,
                week=currentWeek,
                slot_number=c.slotNumber,
                user_card_id=c.userCardId,
                locked=gamesActive,
            ))

        session.commit()
        return build_success_response({"message": "Cards equipped", "locked": gamesActive})
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

    sm = floosball_app.seasonManager if floosball_app else None
    currentSeason = sm.currentSeason.seasonNumber if sm and sm.currentSeason else 0

    cardManager = CardManager(floosball_app.serviceContainer if floosball_app else None)

    session = get_session()
    try:
        featured = cardManager.getFeaturedCards(session, user.id, currentSeason)
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
