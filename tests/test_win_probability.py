#!/usr/bin/env python3
"""
Test script to run a game and extract win probability swings.
"""

import asyncio
import sys
from managers.floosballApplication import FloosballApplication
from managers.seasonManager import SeasonManager
from managers.leagueManager import LeagueManager

async def test_win_probability():
    """Run a single game and track win probability."""
    
    # Initialize service container and app properly
    from service_container import initializeServices, container
    from database.connection import clear_db, init_db
    
    # Clear and init database
    clear_db()
    init_db()
    
    # Initialize services
    initializeServices()
    
    # Create app with container
    app = FloosballApplication(container)
    
    # Initialize league
    from config_manager import get_config
    config = get_config()
    config['timingMode'] = 'fast'
    await app.initializeLeague(config, force_fresh=True)
    
    # Get managers from container
    season_mgr: SeasonManager = container.get('season_manager')
    
    # Create a season
    await season_mgr.createNewSeason()
    
    # Simulate first game with verbose logging
    print("\n" + "="*80)
    print("SIMULATING GAME WITH WIN PROBABILITY TRACKING")
    print("="*80 + "\n")
    
    game = await season_mgr._simulateGame(0, 0, verbose=True)
    
    # Extract win probability swings from play-by-play log
    print("\n" + "="*80)
    print("WIN PROBABILITY SUMMARY")
    print("="*80 + "\n")
    
    print(f"Final Score: {game.awayTeam.abbr} {game.awayScore} - {game.homeTeam.abbr} {game.homeScore}")
    print(f"Final Win Probability: {game.awayTeam.abbr} {game.awayTeamWinProbability}%, {game.homeTeam.abbr} {game.homeTeamWinProbability}%")
    
    # Parse play-by-play log for key win probability swings
    log_file = f"logs/play_by_play_season_1_game_1_{game.awayTeam.abbr}_at_{game.homeTeam.abbr}.txt"
    try:
        with open(log_file, 'r') as f:
            content = f.read()
        
        # Find lines with win probability
        print("\n--- KEY WIN PROBABILITY CHANGES ---\n")
        
        lines = content.split('\n')
        prev_home_wp = 50.0
        
        for i, line in enumerate(lines):
            if 'Win Probability:' in line:
                # Extract win probability values
                try:
                    parts = line.split('Win Probability:')[1].strip()
                    # Format: "TEAM XX.X%, TEAM YY.Y%"
                    team1_part, team2_part = parts.split(',')
                    
                    team1 = team1_part.split()[0]
                    wp1 = float(team1_part.split()[1].rstrip('%'))
                    
                    team2 = team2_part.strip().split()[0]
                    wp2 = float(team2_part.strip().split()[1].rstrip('%'))
                    
                    # Determine which is home team
                    if team1 == game.homeTeam.abbr:
                        home_wp = wp1
                    else:
                        home_wp = wp2
                    
                    # Track big swings (>10% change)
                    swing = abs(home_wp - prev_home_wp)
                    if swing > 10:
                        # Look back a few lines for context
                        context_start = max(0, i - 5)
                        context = '\n'.join(lines[context_start:i+1])
                        print(f"BIG SWING: {prev_home_wp:.1f}% → {home_wp:.1f}% ({swing:+.1f}%)")
                        print(context)
                        print()
                    
                    prev_home_wp = home_wp
                    
                except:
                    continue
        
    except FileNotFoundError:
        print(f"Note: Play-by-play log not found at {log_file}")
        print("(Verbose logging may not be enabled for this game)")

if __name__ == '__main__':
    asyncio.run(test_win_probability())
