# Getting Started with Floosball API

Quick guide to get the API running with your React frontend.

## Prerequisites

```bash
# Install Python dependencies (if not already installed)
pip install fastapi uvicorn websockets

# Or from requirements.txt
pip install -r requirements.txt
```

## Quick Start

### 1. Start the API Server

**Option A: With automatic simulation**
```bash
python examples/run_api_server.py --simulate
```

**Option B: Just the API (no simulation yet)**
```bash
python examples/run_api_server.py
```

**Option C: Fresh database + simulation**
```bash
python examples/run_api_server.py --fresh --simulate
```

The server will start on http://localhost:8000

### 2. Test the API

**Check if it's running:**
```bash
curl http://localhost:8000/health
```

**Get all teams:**
```bash
curl http://localhost:8000/api/teams
```

**Interactive API docs:**
Open http://localhost:8000/docs in your browser

### 3. Test WebSocket Connection

```bash
# In a new terminal, run the example client
python examples/websocket_client_example.py season

# Or watch a specific game
python examples/websocket_client_example.py game 1
```

## Frontend Integration (React)

### Install WebSocket client

```bash
npm install
# WebSocket is built into browsers, no package needed!
```

### Example React Hook

```javascript
// hooks/useGameWebSocket.js
import { useEffect, useState } from 'react';

export function useGameWebSocket(gameId) {
  const [gameState, setGameState] = useState({
    homeScore: 0,
    awayScore: 0,
    homeWinProb: 50,
    awayWinProb: 50,
    isLive: false
  });

  useEffect(() => {
    const ws = new WebSocket(`ws://localhost:8000/ws/game/${gameId}`);

    ws.onopen = () => {
      console.log('Connected to game', gameId);
      setGameState(prev => ({ ...prev, isLive: true }));
    };

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);

      switch(data.event) {
        case 'game_start':
          console.log('Game starting:', data);
          break;

        case 'score_update':
          setGameState(prev => ({
            ...prev,
            homeScore: data.home_score,
            awayScore: data.away_score
          }));
          break;

        case 'win_probability_update':
          setGameState(prev => ({
            ...prev,
            homeWinProb: data.home_win_probability,
            awayWinProb: data.away_win_probability
          }));
          break;

        case 'game_end':
          console.log('Game ended:', data);
          setGameState(prev => ({ ...prev, isLive: false }));
          break;
      }
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
    };

    ws.onclose = () => {
      console.log('Disconnected from game', gameId);
      setGameState(prev => ({ ...prev, isLive: false }));
    };

    return () => ws.close();
  }, [gameId]);

  return gameState;
}
```

### Example Component

```javascript
// components/LiveGame.jsx
import React from 'react';
import { useGameWebSocket } from '../hooks/useGameWebSocket';

export function LiveGame({ gameId }) {
  const { homeScore, awayScore, homeWinProb, awayWinProb, isLive } = 
    useGameWebSocket(gameId);

  return (
    <div className="live-game">
      <div className="status">
        {isLive ? '🔴 LIVE' : '⚫ Not Started'}
      </div>

      <div className="score">
        <div>Home: {homeScore}</div>
        <div>Away: {awayScore}</div>
      </div>

      <div className="win-probability">
        <div className="home-prob" style={{ width: `${homeWinProb}%` }}>
          {homeWinProb.toFixed(1)}%
        </div>
        <div className="away-prob" style={{ width: `${awayWinProb}%` }}>
          {awayWinProb.toFixed(1)}%
        </div>
      </div>
    </div>
  );
}
```

### Fetch Teams (REST API)

```javascript
// api/teams.js
export async function getTeams() {
  const response = await fetch('http://localhost:8000/api/teams');
  return response.json();
}

export async function getTeam(teamId) {
  const response = await fetch(`http://localhost:8000/api/teams/${teamId}`);
  return response.json();
}

// In your component
import { useEffect, useState } from 'react';
import { getTeams } from './api/teams';

function TeamList() {
  const [teams, setTeams] = useState([]);

  useEffect(() => {
    getTeams().then(data => setTeams(data.data || data));
  }, []);

  return (
    <ul>
      {teams.map(team => (
        <li key={team.id}>
          {team.city} {team.name} ({team.wins}-{team.losses})
        </li>
      ))}
    </ul>
  );
}
```

## API Endpoints Reference

### Teams
- `GET /api/teams` - All teams
- `GET /api/teams?league=NFC` - Teams in specific league
- `GET /api/teams/{id}` - Team details

### Players
- `GET /api/players` - All active players
- `GET /api/players?position=QB` - Filter by position
- `GET /api/players?status=retired` - Retired players
- `GET /api/players/{id}` - Player details

### Season
- `GET /api/season` - Current season info
- `GET /api/standings` - League standings

### WebSocket
- `WS /ws/game/{id}` - Game updates
- `WS /ws/season` - Season updates
- `WS /ws/standings` - Standings updates

## CORS Configuration

By default, the API allows connections from:
- http://localhost:3000 (Create React App)
- http://localhost:5173 (Vite)
- http://localhost:3001

To add more origins, edit `api/main.py`:

```python
origins = [
    "http://localhost:3000",
    "https://your-production-domain.com"
]
```

## Troubleshooting

**API won't start:**
- Check if port 8000 is already in use: `lsof -i :8000`
- Try a different port: `python examples/run_api_server.py --port 8001`

**WebSocket connection fails:**
- Make sure API server is running
- Check browser console for CORS errors
- Verify the URL format: `ws://localhost:8000/ws/game/1`

**No game updates:**
- Broadcasting might be disabled - check server logs
- Make sure `--simulate` flag was used or simulation started manually
- Verify game ID exists: `curl http://localhost:8000/api/season`

**CORS errors:**
- Add your frontend URL to the origins list in `api/main.py`
- Restart the API server after changes

## Next Steps

1. ✅ Start API server
2. ✅ Test REST endpoints
3. ✅ Test WebSocket connection
4. 🔄 Connect your React frontend
5. 🔄 Build live game UI
6. 🔄 Add standings displays
7. 🔄 Create player stat pages

For full API documentation, see [api/README.md](../api/README.md)
