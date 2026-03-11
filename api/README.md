# Floosball API

Modern REST + WebSocket API for the Floosball football simulation engine.

## Architecture

```
api/
├── main.py                # FastAPI app with REST endpoints
├── websocket_manager.py   # WebSocket connection management
├── game_broadcaster.py    # Real-time game event broadcasting
├── event_models.py        # Standardized event formats
└── __init__.py           # Package exports
```

## Features

### REST API Endpoints

**Teams**
- `GET /api/teams` - List all teams (optional `?league=` filter)
- `GET /api/teams/{team_id}` - Get team details, ratings, roster, history

**Players**
- `GET /api/players` - List players (filters: `?position=`, `?team_id=`, `?status=`)
- `GET /api/players/{player_id}` - Get player details, stats, attributes

**Season & Games**
- `GET /api/season` - Current season info, week, standings
- `GET /api/standings` - League standings sorted by record

**Stats**
- `GET /api/stats/leaders` - Stat leaders by category (coming soon)

**System**
- `GET /health` - API health check
- `GET /api/ws/stats` - WebSocket connection statistics

### WebSocket Channels

**Game-Specific Updates** (`/ws/game/{game_id}`)
- Play-by-play events
- Score changes
- Win probability updates (every play!)
- Quarter/half transitions
- Game start/end

**Season-Wide Updates** (`/ws/season`)
- Week start/end
- Game completions
- Season progression
- All game events (consolidated)

**Standings Updates** (`/ws/standings`)
- Real-time standings changes as games complete
- Playoff picture updates

## Usage

### Starting the API Server

**Option 1: With Main Application**
```python
from api.main import app, set_floosball_app
from managers.floosballApplication import FloosballApplication
import uvicorn

# Initialize application
floosball_app = FloosballApplication(serviceContainer)
set_floosball_app(floosball_app)

# Run server
uvicorn.run(app, host="0.0.0.0", port=8000)
```

**Option 2: Standalone Development**
```bash
uvicorn api.main:app --reload --port 8000
```

### Enabling Game Broadcasting

Broadcasting must be explicitly enabled to avoid overhead when not needed:

```python
from api import websocket_manager, broadcaster

# Enable broadcasting (call at startup)
broadcaster.enable(websocket_manager)

# Broadcasting will now work during game simulation

# Disable when not needed
broadcaster.disable()
```

### Frontend Integration

**REST API Example (React)**
```javascript
// Fetch teams
const response = await fetch('http://localhost:8000/api/teams');
const teams = await response.json();

// Get specific team
const team = await fetch('http://localhost:8000/api/teams/1');
const teamData = await team.json();
```

**WebSocket Example (React)**
```javascript
// Connect to game updates
const ws = new WebSocket('ws://localhost:8000/ws/game/123');

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  
  switch(data.event) {
    case 'win_probability_update':
      updateWinProb(data.home_win_probability, data.away_win_probability);
      break;
    case 'score_update':
      updateScore(data.home_score, data.away_score);
      break;
    case 'game_end':
      showFinalScore(data.final_score);
      break;
  }
};

// Connect to season updates
const seasonWs = new WebSocket('ws://localhost:8000/ws/season');
seasonWs.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Season event:', data.event, data);
};
```

## Event Types

All events include a `timestamp` field automatically.

### Game Events

**`game_start`**
```json
{
  "event": "game_start",
  "game_id": 123,
  "home_team": {"name": "Wizards", "city": "Washington", "abbr": "WAS"},
  "away_team": {"name": "Giants", "city": "New York", "abbr": "NYG"},
  "start_time": "2026-02-19T14:00:00",
  "timestamp": "2026-02-19T14:00:01"
}
```

**`win_probability_update`**
```json
{
  "event": "win_probability_update",
  "game_id": 123,
  "home_win_probability": 67.3,
  "away_win_probability": 32.7,
  "factors": {},
  "timestamp": "2026-02-19T14:05:23"
}
```

**`score_update`**
```json
{
  "event": "score_update",
  "game_id": 123,
  "home_score": 14,
  "away_score": 7,
  "scoring_play": {"team": "WAS", "points": 6, "quarter": 2},
  "timestamp": "2026-02-19T14:15:42"
}
```

**`game_end`**
```json
{
  "event": "game_end",
  "game_id": 123,
  "final_score": {"home": 28, "away": 21},
  "winner": "Washington Wizards",
  "stats": {"total_plays": 145, "home_plays": 73, "away_plays": 72},
  "timestamp": "2026-02-19T17:23:11"
}
```

### Season Events

**`week_start`**, **`week_end`**, **`season_start`**, **`season_end`**

See [event_models.py](event_models.py) for full event schemas.

## Configuration

### CORS Origins

Edit `api/main.py` to add allowed origins:

```python
origins = [
    "http://localhost:3000",      # React dev server
    "http://localhost:5173",      # Vite dev server
    "https://yourdomain.com"      # Production
]
```

### Broadcasting Control

Broadcasting is **disabled by default** to avoid overhead. Enable only when:
- Running API server
- Frontend is connected
- Real-time updates are needed

## Integration with Refactored System

The API uses the manager-based architecture:

```python
# Access managers through FloosballApplication
floosball_app.teamManager.teams          # All teams
floosball_app.playerManager.activePlayers  # Active players
floosball_app.seasonManager.currentSeason  # Current season
floosball_app.leagueManager.leagues        # All leagues
```

**Response builders** (from `api_response_builders.py`) handle data formatting:
- `TeamResponseBuilder` - Team data
- `PlayerResponseBuilder` - Player data
- `GameResponseBuilder` - Game data
- `LeagueResponseBuilder` - League/standings data

## Performance Notes

- **WebSocket overhead**: Minimal when no clients connected
- **Broadcasting**: Only enabled when explicitly activated
- **Event filtering**: Subscribe to specific channels to reduce traffic
- **Connection limits**: Monitor via `/api/ws/stats`

## Development

**Run in development mode:**
```bash
uvicorn api.main:app --reload --port 8000
```

**Test WebSocket connections:**
```bash
# Using websocat
websocat ws://localhost:8000/ws/game/1

# Using Python websockets library
python examples/test_websocket.py
```

**Monitor connections:**
```bash
curl http://localhost:8000/api/ws/stats
```

## Future Enhancements

- [ ] Play-by-play text streaming
- [ ] Player stat leader endpoints
- [ ] Historical game data queries
- [ ] Real-time draft updates
- [ ] Coaching decisions API
- [ ] Fantasy points calculations
- [ ] Authentication/rate limiting

---

**Version**: 2.0.0
**Last Updated**: March 10, 2026
