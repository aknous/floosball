"""
Test WebSocket Broadcasting with Slow Simulation
Runs a single game with real-time broadcasts to see all events
"""

import asyncio
import uvicorn
from threading import Thread
import time
import websockets
import json
from service_container import ServiceContainer
from managers.floosballApplication import FloosballApplication
from api.main import app, set_floosball_app
from api import websocket_manager, broadcaster
from config_manager import loadConfigJson
from logger_config import get_logger
from managers.timingManager import TimingManager, TimingMode

logger = get_logger("floosball.test_broadcast")


async def websocket_listener(game_id: int):
    """Listen to game broadcasts and print them"""
    uri = f"ws://localhost:8000/ws/game/{game_id}"
    
    print(f"\n{'='*80}")
    print(f"🎧 WebSocket Client - Listening to Game {game_id}")
    print(f"{'='*80}\n")
    
    try:
        async with websockets.connect(uri) as websocket:
            print(f"✅ Connected to game {game_id} WebSocket\n")
            
            while True:
                try:
                    message = await websocket.recv()
                    data = json.loads(message)
                    
                    event_type = data.get('event')
                    timestamp = data.get('timestamp', '')
                    
                    # Pretty print based on event type
                    if event_type == 'game_start':
                        print(f"\n{'🏈 '*20}")
                        print(f"GAME START")
                        print(f"{data['away_team']['city']} {data['away_team']['name']} @ {data['home_team']['city']} {data['home_team']['name']}")
                        print(f"{'🏈 '*20}\n")
                    
                    elif event_type == 'play_complete':
                        play = data['play']
                        print(f"▶️  Play #{play['play_number']}: Q{play['quarter']} {play['time_remaining']}")
                        print(f"   {play['down']} & {play['distance']} at {play['yard_line']}")
                        print(f"   {play['play_type']}: {play['yards_gained']} yards")
                        if play['description']:
                            print(f"   📝 {play['description']}")
                        if play['is_touchdown']:
                            print(f"   🎯 TOUCHDOWN!")
                        if play['is_turnover']:
                            print(f"   ⚠️  TURNOVER!")
                        if play['is_sack']:
                            print(f"   💥 SACK!")
                        print()
                    
                    elif event_type == 'win_probability_update':
                        home = data['home_win_probability']
                        away = data['away_win_probability']
                        # Show probability bar
                        bar_width = 40
                        home_bar = int((home / 100) * bar_width)
                        away_bar = bar_width - home_bar
                        print(f"📊 Win Prob: [{'█'*home_bar}{' '*away_bar}] {home:.1f}% - {away:.1f}%")
                    
                    elif event_type == 'score_update':
                        home = data['home_score']
                        away = data['away_score']
                        play = data.get('scoring_play', {})
                        print(f"\n{'🎯 '*15}")
                        print(f"SCORE UPDATE: {away} - {home}")
                        if play:
                            print(f"{play.get('team')} scores! ({play.get('type')})")
                        print(f"{'🎯 '*15}\n")
                    
                    elif event_type == 'quarter_end':
                        print(f"\n⏱️  End of Q{data['quarter']}: {data['away_score']} - {data['home_score']}\n")
                    
                    elif event_type == 'halftime':
                        print(f"\n{'🏟️  '*10}")
                        print(f"HALFTIME: {data['away_score']} - {data['home_score']}")
                        print(f"{'🏟️  '*10}\n")
                    
                    elif event_type == 'game_end':
                        final = data['final_score']
                        winner = data['winner']
                        stats = data.get('stats', {})
                        print(f"\n{'🏆 '*15}")
                        print(f"FINAL SCORE: {final['away']} - {final['home']}")
                        print(f"Winner: {winner}")
                        print(f"Total plays: {stats.get('total_plays', 'N/A')}")
                        print(f"{'🏆 '*15}\n")
                        break
                    
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


async def run_single_game_simulation(floosball_app: FloosballApplication):
    """Run a single game with slow timing"""
    print(f"\n{'='*80}")
    print(f"🎮 Starting Slow Game Simulation")
    print(f"{'='*80}\n")
    
    # Get first scheduled game
    season_mgr = floosball_app.seasonManager
    
    if not season_mgr.currentSeason or not season_mgr.currentSeason.schedule:
        print("❌ No games scheduled. Creating season first...")
        await floosball_app.initializeLeague(loadConfigJson(), force_fresh=True)
        season_mgr.createNewSeason(1)
    
    # Get first game from schedule
    first_week = season_mgr.currentSeason.schedule[0]
    first_game = list(first_week.values())[0]
    
    print(f"🎮 Game {first_game.id}: {first_game.awayTeam.city} {first_game.awayTeam.name} @ {first_game.homeTeam.city} {first_game.homeTeam.name}")
    print(f"   Away ELO: {first_game.awayTeam.elo:.0f}")
    print(f"   Home ELO: {first_game.homeTeam.elo:.0f}")
    print(f"\n⏱️  Timing Mode: SLOW (sequential delays for visibility)")
    print(f"\nStarting game in 3 seconds...\n")
    
    await asyncio.sleep(3)
    
    # Simulate the game
    await season_mgr._simulateGame(first_game, season_number=1, game_idx=0, verbose=False)
    
    print(f"\n{'='*80}")
    print(f"✅ Game Complete!")
    print(f"{'='*80}\n")


async def main():
    """Main test function"""
    print(f"\n{'='*80}")
    print(f"WebSocket Broadcast Test - Slow Mode")
    print(f"{'='*80}\n")
    
    # Start API server in background thread
    def run_api():
        uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")
    
    api_thread = Thread(target=run_api, daemon=True)
    api_thread.start()
    
    print("🚀 Starting API server...")
    await asyncio.sleep(2)  # Give server time to start
    
    # Initialize application
    print("🔧 Initializing Floosball application...")
    service_container = ServiceContainer()
    floosball_app = FloosballApplication(service_container)
    
    # Load config and initialize
    config = loadConfigJson()
    await floosball_app.initializeLeague(config, force_fresh=True)
    
    # Set timing mode to SEQUENTIAL (slow mode with delays)
    floosball_app.seasonManager.setTimingMode(TimingMode.SEQUENTIAL)
    print("⏱️  Timing mode set to: SEQUENTIAL (slow with delays)")
    
    # Set app reference in API
    set_floosball_app(floosball_app)
    
    # Enable broadcasting
    broadcaster.enable(websocket_manager)
    print("📡 Broadcasting ENABLED\n")
    
    # Create season and get first game
    season_mgr = floosball_app.seasonManager
    season_mgr.createNewSeason(1)
    first_week = season_mgr.currentSeason.schedule[0]
    first_game = list(first_week.values())[0]
    game_id = first_game.id
    
    print(f"🎮 Game ID: {game_id}")
    print(f"   {first_game.awayTeam.abbr} @ {first_game.homeTeam.abbr}")
    print(f"\n{'='*80}\n")
    
    # Run WebSocket listener and game simulation concurrently
    await asyncio.gather(
        websocket_listener(game_id),
        run_single_game_simulation(floosball_app)
    )
    
    print("\n✅ Test complete! Check the output above for all broadcasted events.\n")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
