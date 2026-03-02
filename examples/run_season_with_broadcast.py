"""
Run Full Season Simulation with WebSocket Broadcasting
Shows all games in sequential mode with real-time event streaming
"""

import asyncio
import uvicorn
from threading import Thread
import time
import websockets
import json
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from service_container import container, initializeServices
from managers.floosballApplication import FloosballApplication
from api.main import app, set_floosball_app
from api import websocket_manager, broadcaster
from config_manager import get_config
from logger_config import get_logger
from managers.timingManager import TimingMode

logger = get_logger("floosball.season_broadcast")


async def season_websocket_listener():
    """Listen to all season broadcasts"""
    uri = "ws://localhost:8000/ws/season"
    
    print(f"\n{'='*80}")
    print(f"🎧 WebSocket Client - Listening to Season Updates")
    print(f"{'='*80}\n")
    
    try:
        async with websockets.connect(uri) as websocket:
            print(f"✅ Connected to season WebSocket\n")
            
            play_count = 0
            game_count = 0
            games = {}  # Track multiple games by game_id
            
            while True:
                try:
                    message = await websocket.recv()
                    data = json.loads(message)
                    
                    event_type = data.get('event')
                    game_id = data.get('game_id')  # Get game_id from event
                    
                    # Season-level events
                    if event_type == 'season_start':
                        print(f"\n{'🏈 '*20}")
                        print(f"SEASON {data['season_number']} BEGINS")
                        print(f"{data['total_weeks']} weeks scheduled")
                        print(f"{'🏈 '*20}\n")
                    
                    elif event_type == 'week_start':
                        print(f"\n{'📅 '*15}")
                        print(f"WEEK {data['week_number']} - {data['games_count']} games")
                        print(f"{'📅 '*15}\n")
                        games.clear()  # Clear games at start of new week
                    
                    elif event_type == 'week_end':
                        print(f"\n✅ Week {data['week_number']} complete\n")
                    
                    elif event_type == 'season_end':
                        print(f"\n{'🏆 '*15}")
                        print(f"SEASON {data['season_number']} COMPLETE")
                        champion = data.get('champion', {})
                        print(f"Champion: {champion.get('name', 'TBD')}")
                        print(f"{'🏆 '*15}\n")
                        break
                    
                    # Game events - track by game_id
                    elif event_type == 'game_start':
                        game_count += 1
                        games[game_id] = {
                            'number': game_count,
                            'away': data['away_team']['abbr'],
                            'home': data['home_team']['abbr'],
                            'away_full': f"{data['away_team']['city']} {data['away_team']['name']}",
                            'home_full': f"{data['home_team']['city']} {data['home_team']['name']}"
                        }
                        print(f"\n{'─'*80}")
                        print(f"🏈 GAME {game_count}: {games[game_id]['away']} @ {games[game_id]['home']}")
                        print(f"   {games[game_id]['away_full']} @ {games[game_id]['home_full']}")
                        print(f"{'─'*80}\n")
                    
                    elif event_type == 'play_complete':
                        if game_id not in games:
                            continue  # Skip if we don't have game info yet
                            
                        play_count += 1
                        play = data['play']
                        game = games[game_id]
                        
                        # Store play for WPA display
                        if 'last_play' not in games[game_id]:
                            games[game_id]['last_play'] = {}
                        games[game_id]['last_play'] = play
                        
                        # Only show every 10th play to avoid spam, or important plays
                        if play_count % 10 == 0 or play['is_touchdown'] or play['is_turnover']:
                            # Show game matchup
                            game_info = f"[Game {game['number']}: {game['away']} @ {game['home']}]"
                            
                            # Show play details
                            desc = f"{game_info}\n  Play #{play['play_number']}: Q{play['quarter']} {play['time_remaining']} - "
                            desc += f"{play['down']} & {play['distance']} at {play['yard_line']} - "
                            desc += f"{play['offensive_team']} {play['play_type']}: {play['yards_gained']}yd"
                            
                            # Add flags
                            if play['is_touchdown']:
                                desc += " 🎯 TD!"
                            if play['is_turnover']:
                                desc += " ⚠️ TO!"
                            if play['is_sack']:
                                desc += " 💥 SACK!"
                            
                            print(desc)
                            
                            # Show play description text
                            if play.get('description'):
                                print(f"  📝 {play['description']}")
                    
                    elif event_type == 'win_probability_update':
                        if game_id not in games:
                            continue
                        
                        game = games[game_id]
                        homeWpa = data.get('homeWpa', 0)
                        awayWpa = data.get('awayWpa', 0)
                        
                        # Show high-impact plays (absolute WPA > 5%)
                        if abs(homeWpa) > 5.0 or abs(awayWpa) > 5.0:
                            gameInfo = f"[Game {game['number']}: {game['away']} @ {game['home']}]"
                            
                            # Determine which team gained
                            if homeWpa > 0:
                                impactTeam = game['home']
                                impactValue = homeWpa
                            else:
                                impactTeam = game['away']
                                impactValue = abs(awayWpa)
                            
                            # Get last play info if available
                            lastPlay = game.get('last_play', {})
                            playDesc = lastPlay.get('description', 'Big play!')
                            
                            print(f"{gameInfo}")
                            print(f"  ⚡ HIGH IMPACT PLAY! +{impactValue:.1f}% WP for {impactTeam}")
                            print(f"  📝 {playDesc}")
                            print(f"  📊 Win Prob: {game['away']} {data['awayWinProbability']:.1f}% - {data['homeWinProbability']:.1f}% {game['home']}\n")
                    
                    elif event_type == 'score_update':
                        if game_id not in games:
                            continue
                            
                        game = games[game_id]
                        home = data['home_score']
                        away = data['away_score']
                        play = data.get('scoring_play', {})
                        game_info = f"[Game {game['number']}: {game['away']} @ {game['home']}]"
                        print(f"  {game_info}\n  🎯 SCORE: {game['away']} {away} - {home} {game['home']} ({play.get('team', '')} {play.get('type', '')})\n")
                    
                    elif event_type == 'quarter_end':
                        if game_id not in games:
                            continue
                            
                        game = games[game_id]
                        game_info = f"[Game {game['number']}: {game['away']} @ {game['home']}]"
                        print(f"  {game_info}\n  ⏱️  End Q{data['quarter']}: {game['away']} {data['away_score']} - {data['home_score']} {game['home']}\n")
                    
                    elif event_type == 'halftime':
                        if game_id not in games:
                            continue
                            
                        game = games[game_id]
                        game_info = f"[Game {game['number']}: {game['away']} @ {game['home']}]"
                        print(f"  {game_info}\n  🏟️  HALFTIME: {game['away']} {data['away_score']} - {data['home_score']} {game['home']}\n")
                    
                    elif event_type == 'game_end':
                        if game_id not in games:
                            continue
                            
                        game = games[game_id]
                        final = data['final_score']
                        winner = data['winner']
                        stats = data.get('stats', {})
                        game_info = f"[Game {game['number']}: {game['away']} @ {game['home']}]"
                        print(f"\n  {game_info}")
                        print(f"  🏆 FINAL: {game['away']} {final['away']} - {final['home']} {game['home']}")
                        print(f"  Winner: {winner}")
                        print(f"  Plays: {stats.get('total_plays', 'N/A')}")
                        print(f"{'─'*80}\n")
                        play_count = 0  # Reset for next game
                    
                    elif event_type == 'info':
                        print(f"ℹ️  {data['message']}")
                    
                    elif event_type == 'error':
                        print(f"❌ Error: {data['message']}")
                
                except websockets.exceptions.ConnectionClosed:
                    print("\n❌ Connection closed")
                    break
                except json.JSONDecodeError as e:
                    print(f"❌ JSON decode error: {e}")
                    break
                except Exception as e:
                    print(f"❌ Error: {e}")
                    break
    
    except Exception as e:
        print(f"\n❌ Could not connect to WebSocket: {e}")
        print("Make sure the API server is running!")


async def run_season_simulation(floosball_app: FloosballApplication):
    """Run full season simulation"""
    print(f"\n{'='*80}")
    print(f"🎮 Starting Season Simulation")
    print(f"⏱️  Mode: SEQUENTIAL (slow with delays)")
    print(f"{'='*80}\n")
    
    await asyncio.sleep(2)
    
    # Start and run the season
    await floosball_app.seasonManager.startNewSeason()
    await floosball_app.seasonManager.runSeasonSimulation()
    
    print(f"\n{'='*80}")
    print(f"✅ Season Simulation Complete!")
    print(f"{'='*80}\n")


async def main():
    """Main function"""
    print(f"\n{'='*80}")
    print(f"Full Season WebSocket Broadcast Test")
    print(f"{'='*80}\n")
    
    # Start API server in background thread
    def run_api():
        uvicorn.run(app, host="127.0.0.1", port=8000, log_level="error")
    
    api_thread = Thread(target=run_api, daemon=True)
    api_thread.start()
    
    print("🚀 Starting API server...")
    await asyncio.sleep(2)
    
    # Initialize services
    print("🔧 Initializing service container...")
    initializeServices()
    
    # Initialize application with global container
    print("🔧 Initializing Floosball application...")
    floosball_app = FloosballApplication(container)
    
    # Load config and initialize
    config = get_config()
    await floosball_app.initializeLeague(config, force_fresh=True)
    
    # Set timing mode to SEQUENTIAL (slow mode with delays)
    floosball_app.seasonManager.setTimingMode(TimingMode.SEQUENTIAL)
    print("⏱️  Timing mode: SEQUENTIAL")
    
    # Set app reference in API
    set_floosball_app(floosball_app)
    
    # Enable broadcasting
    broadcaster.enable(websocket_manager)
    print("📡 Broadcasting ENABLED")
    
    print(f"\n{'='*80}\n")
    print("Starting in 2 seconds...\n")
    await asyncio.sleep(2)
    
    # Run WebSocket listener and season simulation concurrently
    await asyncio.gather(
        season_websocket_listener(),
        run_season_simulation(floosball_app)
    )
    
    print("\n✅ Season complete!\n")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
