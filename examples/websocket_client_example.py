"""
Example: WebSocket Client for Floosball API
Demonstrates connecting to game updates and handling events
"""

import asyncio
import websockets
import json
from datetime import datetime

async def listen_to_game(game_id: int):
    """Listen to a specific game's updates"""
    uri = f"ws://localhost:8000/ws/game/{game_id}"
    
    print(f"Connecting to game {game_id}...")
    
    async with websockets.connect(uri) as websocket:
        print(f"Connected! Listening for game {game_id} events...\n")
        
        while True:
            try:
                message = await websocket.recv()
                data = json.loads(message)
                
                # Handle different event types
                event_type = data.get('event')
                timestamp = data.get('timestamp', datetime.now().isoformat())
                
                if event_type == 'game_start':
                    print(f"\n🏈 GAME START")
                    print(f"   {data['away_team']['city']} {data['away_team']['name']}")
                    print(f"   @ {data['home_team']['city']} {data['home_team']['name']}")
                    print(f"   Start time: {data['start_time']}\n")
                
                elif event_type == 'win_probability_update':
                    home = data['home_win_probability']
                    away = data['away_win_probability']
                    print(f"📊 Win Probability: {home}% - {away}%")
                
                elif event_type == 'score_update':
                    home = data['home_score']
                    away = data['away_score']
                    play = data.get('scoring_play', {})
                    print(f"\n🎯 SCORE UPDATE: {away} - {home}")
                    if play:
                        print(f"   {play.get('team')} scores {play.get('points')} (Q{play.get('quarter')})")
                    print()
                
                elif event_type == 'quarter_end':
                    quarter = data['quarter']
                    home = data['home_score']
                    away = data['away_score']
                    print(f"\n⏱️  End of Q{quarter}: {away} - {home}\n")
                
                elif event_type == 'halftime':
                    home = data['home_score']
                    away = data['away_score']
                    print(f"\n🏟️  HALFTIME: {away} - {home}\n")
                
                elif event_type == 'game_end':
                    final = data['final_score']
                    winner = data['winner']
                    stats = data.get('stats', {})
                    print(f"\n🏆 FINAL: {final['away']} - {final['home']}")
                    print(f"   Winner: {winner}")
                    print(f"   Total plays: {stats.get('total_plays', 'N/A')}")
                    print("\nGame complete! Disconnecting...\n")
                    break
                
                elif event_type == 'info':
                    print(f"ℹ️  {data['message']}")
                
                elif event_type == 'error':
                    print(f"❌ Error: {data['message']}")
                
                else:
                    print(f"📨 {event_type}: {data.get('message', 'No message')}")
            
            except websockets.exceptions.ConnectionClosed:
                print("Connection closed")
                break
            except Exception as e:
                print(f"Error: {e}")
                break


async def listen_to_season():
    """Listen to season-wide updates"""
    uri = "ws://localhost:8000/ws/season"
    
    print("Connecting to season updates...")
    
    async with websockets.connect(uri) as websocket:
        print("Connected! Listening for season events...\n")
        
        while True:
            try:
                message = await websocket.recv()
                data = json.loads(message)
                
                event_type = data.get('event')
                
                if event_type == 'season_start':
                    print(f"\n🏈 SEASON {data['season_number']} BEGINS")
                    print(f"   {data['total_weeks']} weeks scheduled\n")
                
                elif event_type == 'week_start':
                    print(f"\n📅 Week {data['week_number']} - {data['games_count']} games")
                
                elif event_type == 'week_end':
                    print(f"✅ Week {data['week_number']} complete\n")
                
                elif event_type == 'season_end':
                    print(f"\n🏆 SEASON {data['season_number']} COMPLETE")
                    print(f"   Champion: {data['champion'].get('name', 'TBD')}\n")
                
                elif event_type == 'game_end':
                    final = data['final_score']
                    print(f"   Game {data['game_id']} final: {final['away']} - {final['home']}")
                
                # Don't spam with win probability updates
                elif event_type != 'win_probability_update':
                    print(f"📨 {event_type}")
            
            except websockets.exceptions.ConnectionClosed:
                print("Connection closed")
                break
            except KeyboardInterrupt:
                print("\nStopping...")
                break
            except Exception as e:
                print(f"Error: {e}")
                break


async def listen_to_standings():
    """Listen to standings updates"""
    uri = "ws://localhost:8000/ws/standings"
    
    print("Connecting to standings updates...")
    
    async with websockets.connect(uri) as websocket:
        print("Connected! Listening for standings changes...\n")
        
        while True:
            try:
                message = await websocket.recv()
                data = json.loads(message)
                
                event_type = data.get('event')
                
                if event_type == 'standings_update':
                    print("📊 Standings updated")
                    # Could display full standings here
                
                elif event_type == 'info':
                    print(f"ℹ️  {data['message']}")
            
            except websockets.exceptions.ConnectionClosed:
                print("Connection closed")
                break
            except KeyboardInterrupt:
                print("\nStopping...")
                break
            except Exception as e:
                print(f"Error: {e}")
                break


if __name__ == "__main__":
    import sys
    
    print("Floosball WebSocket Client Example")
    print("=" * 50)
    
    # Parse command line arguments
    if len(sys.argv) > 1:
        if sys.argv[1] == "game" and len(sys.argv) > 2:
            game_id = int(sys.argv[2])
            print(f"\nListening to game {game_id}...\n")
            asyncio.run(listen_to_game(game_id))
        elif sys.argv[1] == "season":
            print("\nListening to season updates...\n")
            asyncio.run(listen_to_season())
        elif sys.argv[1] == "standings":
            print("\nListening to standings updates...\n")
            asyncio.run(listen_to_standings())
        else:
            print("\nUsage:")
            print("  python examples/websocket_client_example.py game <game_id>")
            print("  python examples/websocket_client_example.py season")
            print("  python examples/websocket_client_example.py standings")
    else:
        print("\nUsage:")
        print("  python examples/websocket_client_example.py game <game_id>")
        print("  python examples/websocket_client_example.py season")
        print("  python examples/websocket_client_example.py standings")
        print("\nExample: python examples/websocket_client_example.py game 1")
