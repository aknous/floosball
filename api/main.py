"""
Modern Floosball REST API
Uses refactored manager system with clean separation of concerns
"""

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
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
    allow_methods=["*"],
    allow_headers=["*"],
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

@app.get("/api/teams", response_model=List[Dict[str, Any]])
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
async def get_team_avatar(team_id: int, size: int = 32):
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
                "Cache-Control": "no-cache, no-store",
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
                'gamesPlayed': sd.get('gamesPlayed', 0),
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
        # Build current-season entry from live seasonStatsDict and prepend to archive
        sm = floosball_app.seasonManager
        currentSeasonNum = sm.currentSeason.seasonNumber if sm.currentSeason else None
        teamName = player.team.name if hasattr(player.team, 'name') else 'FA'
        teamColor = getattr(player.team, 'color', '#94a3b8') if hasattr(player.team, 'name') else '#94a3b8'
        currentSeasonEntry = dict(player.seasonStatsDict)
        currentSeasonEntry['season'] = currentSeasonNum
        currentSeasonEntry['team'] = teamName
        currentSeasonEntry['color'] = teamColor
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
                                'defensiveTeam': play_data.defense.abbr if hasattr(play_data, 'defense') else ''
                            }
                    # Include WP and WPA data stored alongside the play entry
                    if 'homeWinProbability' in item:
                        play_data['homeWinProbability'] = item['homeWinProbability']
                        play_data['awayWinProbability'] = item.get('awayWinProbability', round(100 - item['homeWinProbability'], 1))
                        play_data['homeWpa'] = item.get('homeWpa', 0.0)
                        play_data['awayWpa'] = item.get('awayWpa', 0.0)
                        play_data['isBigPlay'] = item.get('isBigPlay', False)
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
async def get_highlights(limit: int = 20):
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
            'champion': TeamResponseBuilder.buildBasicTeamDict(current_season.champion) if current_season.champion else None
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

@app.get("/api/stats/leaders", response_model=Dict[str, Any])
async def get_stat_leaders(category: str = "fantasy_points", position: str = "ALL", limit: int = 10):
    """Get statistical leaders filtered by position and category"""
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
            return 0

        players = floosball_app.playerManager.activePlayers
        posFilter = position.upper()
        filtered = [
            p for p in players
            if (posFilter == 'ALL' or (hasattr(p.position, 'name') and p.position.name == posFilter))
            and isinstance(p.team, object) and hasattr(p.team, 'name')
        ]
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
    if not names:
        raise HTTPException(status_code=400, detail="No names provided")
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
