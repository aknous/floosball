#!/usr/bin/env python3
"""Test hybrid sudden death overtime rules"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import floosball_game as FloosGame
from managers.leagueManager import LeagueManager

def test_overtime_games():
    """Run games until we get OT and analyze the rules"""
    
    lm = LeagueManager()
    lm.readFiles()
    
    ot_count = 0
    games_played = 0
    max_games = 50
    
    while ot_count < 3 and games_played < max_games:
        games_played += 1
        game = FloosGame.Game(lm.league.teams[games_played % len(lm.league.teams)], 
                   lm.league.teams[(games_played + 1) % len(lm.league.teams)])
        game.playGame()
        
        if game.currentQuarter == 5:  # OT
            ot_count += 1
            print(f"\n{'='*80}")
            print(f"OVERTIME GAME #{ot_count} - Game {games_played}")
            print(f"{'='*80}")
            print(f"Final Score: {game.homeTeam.abbr} {game.homeScore} - {game.awayTeam.abbr} {game.awayScore}")
            print(f"Home had possession: {game.otHomeHadPos}")
            print(f"Away had possession: {game.otAwayHadPos}")
            print(f"Both teams had possession: {game.firstOtPossessionComplete}")
            print(f"Clock remaining: {game.formatTime(game.gameClockSeconds)}")
            print(f"\nOT PLAYS (chronological - oldest first):")
            
            # Get OT plays in chronological order (oldest first)
            ot_plays = [p for p in reversed(game.gameFeed) if hasattr(p, 'quarter') and p['play'].quarter == 5]
            
            for i, entry in enumerate(ot_plays[:30], 1):  # Show first 30 OT plays
                play = entry['play']
                down_str = f"{play.down}"
                if play.down == 1:
                    down_str = "1st"
                elif play.down == 2:
                    down_str = "2nd"
                elif play.down == 3:
                    down_str = "3rd"
                elif play.down == 4:
                    down_str = "4th"
                
                yards_str = str(play.yardsTo1st) if play.yardsTo1st != 'Goal' else 'Goal'
                
                print(f"{i:2d}. {play.timeRemaining:>5} | {down_str} & {yards_str:<4} | {play.offense.abbr:3} | {play.playDescription}")
                
                # Show score changes
                if hasattr(play, 'scoreChange') and play.scoreChange:
                    print(f"    *** SCORE: {game.homeTeam.abbr} {play.homeTeamScore} - {game.awayTeam.abbr} {play.awayTeamScore} ***")
            
            print(f"\nTotal plays in OT: {len(ot_plays)}")
            
    print(f"\n{'='*80}")
    print(f"Summary: Found {ot_count} OT games in {games_played} games played")
    print(f"{'='*80}")

if __name__ == "__main__":
    test_overtime_games()
