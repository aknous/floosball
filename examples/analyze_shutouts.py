#!/usr/bin/env python3
"""Analyze shutouts from game stats file"""

import re
from collections import defaultdict

def analyze_game_stats(filename):
    shutout_games = []
    all_games = []
    
    with open(filename, 'r') as f:
        content = f.read()
    
    # Split by game separators
    games = content.split('=' * 80)
    
    for game in games:
        if 'FINAL SCORE:' not in game:
            continue
            
        # Extract game info
        score_match = re.search(r'FINAL SCORE: (\w+) (\d+) - (\w+) (\d+)', game)
        if not score_match:
            continue
            
        away_team = score_match.group(1)
        away_score = int(score_match.group(2))
        home_team = score_match.group(3)
        home_score = int(score_match.group(4))
        
        # Extract offensive ratings
        ratings = re.findall(r'Offense Rating\s+(\d+)\s+(\d+)', game)
        if not ratings:
            continue
        
        away_off = int(ratings[0][0])
        home_off = int(ratings[0][1])
        
        # Extract total yards
        yards = re.findall(r'Total Yards\s+(\d+)\s+(\d+)', game)
        if yards:
            away_yards = int(yards[0][0])
            home_yards = int(yards[0][1])
        else:
            away_yards = home_yards = 0
        
        game_data = {
            'away_team': away_team,
            'home_team': home_team,
            'away_score': away_score,
            'home_score': home_score,
            'away_off': away_off,
            'home_off': home_off,
            'away_yards': away_yards,
            'home_yards': home_yards,
        }
        
        all_games.append(game_data)
        
        if away_score == 0 or home_score == 0:
            shutout_games.append(game_data)
    
    print(f"\n{'='*80}")
    print(f"SHUTOUT ANALYSIS - {filename}")
    print(f"{'='*80}\n")
    
    print(f"Total Games: {len(all_games)}")
    print(f"Shutouts: {len(shutout_games)} ({len(shutout_games)/len(all_games)*100:.1f}%)")
    
    # Analyze offensive ratings
    shutout_off_ratings = []
    scoring_off_ratings = []
    
    for game in shutout_games:
        if game['away_score'] == 0:
            shutout_off_ratings.append(game['away_off'])
        if game['home_score'] == 0:
            shutout_off_ratings.append(game['home_off'])
    
    for game in all_games:
        if game['away_score'] > 0:
            scoring_off_ratings.append(game['away_off'])
        if game['home_score'] > 0:
            scoring_off_ratings.append(game['home_off'])
    
    print(f"\nOffensive Rating Analysis:")
    print(f"Teams that got shut out: Avg {sum(shutout_off_ratings)/len(shutout_off_ratings):.1f}, Min {min(shutout_off_ratings)}, Max {max(shutout_off_ratings)}")
    print(f"Teams that scored: Avg {sum(scoring_off_ratings)/len(scoring_off_ratings):.1f}, Min {min(scoring_off_ratings)}, Max {max(scoring_off_ratings)}")
    
    # Breakdown by offensive rating ranges
    print(f"\nShutout rate by Offensive Rating:")
    for rating_min in [65, 70, 75, 80, 85, 90]:
        rating_max = rating_min + 4
        shutouts_in_range = sum(1 for r in shutout_off_ratings if rating_min <= r <= rating_max)
        total_in_range = sum(1 for g in all_games for r in [g['away_off'], g['home_off']] if rating_min <= r <= rating_max)
        if total_in_range > 0:
            pct = shutouts_in_range / total_in_range * 100
            print(f"  {rating_min}-{rating_max}: {shutouts_in_range}/{total_in_range} ({pct:.1f}%)")
    
    # Average yards per game
    shutout_yards = []
    scoring_yards = []
    
    for game in shutout_games:
        if game['away_score'] == 0:
            shutout_yards.append(game['away_yards'])
        if game['home_score'] == 0:
            shutout_yards.append(game['home_yards'])
    
    for game in all_games:
        if game['away_score'] > 0:
            scoring_yards.append(game['away_yards'])
        if game['home_score'] > 0:
            scoring_yards.append(game['home_yards'])
    
    print(f"\nYardage Analysis:")
    print(f"Teams that got shut out: Avg {sum(shutout_yards)/len(shutout_yards):.0f} yards")
    print(f"Teams that scored: Avg {sum(scoring_yards)/len(scoring_yards):.0f} yards")
    
    # Examples of high-offense shutouts
    print(f"\nHigh-rated offenses that got shut out (>= 80 rating):")
    count = 0
    for game in shutout_games:
        if game['away_score'] == 0 and game['away_off'] >= 80 and count < 5:
            print(f"  {game['away_team']} ({game['away_off']} off) scored 0 vs {game['home_team']}, {game['away_yards']} yards")
            count += 1
        if game['home_score'] == 0 and game['home_off'] >= 80 and count < 5:
            print(f"  {game['home_team']} ({game['home_off']} off) scored 0 vs {game['away_team']}, {game['home_yards']} yards")
            count += 1

if __name__ == '__main__':
    analyze_game_stats('logs/game_stats_season_1.txt')
