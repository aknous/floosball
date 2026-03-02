# API Migration Guide

## Overview

We've migrated from the legacy `floosball_api.py` to the modern `api/main.py` implementation. This guide explains the changes and how to use the new API.

## What Changed

### Old API (`floosball_api.py`)
- ❌ No error handling (no HTTPException)
- ❌ Inconsistent parameter naming (`id` for both path and query)
- ❌ No type hints or response models
- ❌ Poor RESTful design (`/players?id=FA`)
- ❌ Direct access to `floosball` global variables
- ❌ Mixed presentation logic with data access

### New API (`api/main.py`)
- ✅ Proper error handling with HTTPException
- ✅ Type hints and response models
- ✅ RESTful paths (`/api/teams/{team_id}`)
- ✅ Manager-based architecture
- ✅ Consistent response format
- ✅ WebSocket support built-in
- ✅ Separation of concerns

## Running the New API

### Start the API Server

```bash
# Basic start (fast mode)
python run_api.py

# With timing mode
python run_api.py --timing=fast
python run_api.py --timing=sequential
python run_api.py --timing=scheduled

# Fresh start (clears existing data)
python run_api.py --fresh --timing=fast
```

The server will start on: `http://localhost:8000`

API Documentation: `http://localhost:8000/docs` (FastAPI auto-generated)

## API Endpoints

### Teams

**Get all teams**
```http
GET /api/teams
GET /api/teams?league=AFC
```

**Get specific team**
```http
GET /api/teams/{team_id}
```

Response includes: ratings, roster, championships, stats, history

### Players

**Get all players**
```http
GET /api/players
GET /api/players?position=QB
GET /api/players?team_id=5
GET /api/players?status=active    # active, fa, retired, hof
```

**Get specific player**
```http
GET /api/players/{player_id}
```

Response includes: attributes, stats, history, championships

### Games

**Get current games**
```http
GET /api/currentGames
```

Returns all scheduled, active, and recently completed games with:
- Real-time scores
- Win probabilities
- Game status
- Possession info
- Down & distance

**Get game statistics**
```http
GET /api/gameStats?id={game_id}
```

Returns full game data including player stats and team stats.

**Get highlights**
```http
GET /api/highlights
GET /api/highlights?limit=50
```

Returns recent highlight plays (TDs, turnovers, big plays).

### Season & Standings

**Get season info**
```http
GET /api/season
```

**Get standings**
```http
GET /api/standings
```

### WebSocket Channels

**Game-specific updates**
```
ws://localhost:8000/ws/game/{game_id}
```

Streams:
- Play-by-play
- Score changes
- Win probability updates
- Quarter transitions

**Season-wide updates**
```
ws://localhost:8000/ws/season
```

Streams:
- Week start/end
- Game completions
- Season progression

**Standings updates**
```
ws://localhost:8000/ws/standings
```

Streams:
- Real-time standings changes
- Playoff picture updates

### Health Check

```http
GET /health
```

## Frontend Integration

The frontend is already configured to use the new API:

```typescript
// services/api.ts already uses correct endpoints
import { api } from '@/services/api'

// Get current games
const games = await api.games.getCurrentGames()

// Get team
const team = await api.teams.getById(teamId)

// Get players
const qbs = await api.players.getAll({ position: 'QB' })
```

WebSocket integration:
```typescript
// contexts/FloosballContext already connected
const { seasonState } = useFloosball()

// Hooks already use WebSocket
const { games } = useCurrentGames()
const gameState = useGameUpdates(gameId)
```

## Migration Checklist

- [x] Created modern API endpoints in `api/main.py`
- [x] Added missing endpoints (`/currentGames`, `/gameStats`, `/highlights`)
- [x] Created `run_api.py` entry point
- [x] Updated response builders for proper nested structures
- [x] Fixed frontend API service paths
- [x] Added proper TypeScript types
- [x] WebSocket infrastructure ready
- [ ] Test all endpoints with real data
- [ ] Update any remaining frontend components
- [ ] Remove old `floosball_api.py` after verification

## Testing

### Test REST Endpoints
```bash
# Health check
curl http://localhost:8000/health

# Get teams
curl http://localhost:8000/api/teams

# Get current games
curl http://localhost:8000/api/currentGames

# Get specific team
curl http://localhost:8000/api/teams/1
```

### Test WebSocket
```javascript
const ws = new WebSocket('ws://localhost:8000/ws/season')
ws.onmessage = (event) => {
  console.log('Event:', JSON.parse(event.data))
}
```

## Error Handling

The new API returns proper HTTP status codes:

- `200` - Success
- `404` - Resource not found
- `500` - Server error
- `503` - Service unavailable (app not initialized)

All responses use consistent format:
```json
{
  "success": true,
  "data": { ... },
  "message": "Success"
}
```

Errors:
```json
{
  "detail": "Error message"
}
```

## Next Steps

1. **Start the new API**: `python run_api.py --timing=fast`
2. **Start the frontend**: `cd floosball-react && npm start`
3. **Verify all endpoints work** with frontend components
4. **Remove old API** once fully verified

## Rollback Plan

If you need to rollback to the old API:

1. Stop `run_api.py`
2. Run: `python floosball_api.py`
3. The old API still has the `/api` prefix from our earlier change

Note: Frontend should work with either API (though old one has limitations).
