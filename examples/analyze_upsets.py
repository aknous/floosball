#!/usr/bin/env python3
"""
Analyze game outcomes vs team ratings to see if better teams are winning.
"""

import re
from collections import defaultdict

def parse_game_stats(filename):
    """Parse game stats file and extract game results with ratings."""
    games = []
    
    with open(filename, 'r') as f:
        content = f.read()
    
    # Split by game separators
    game_blocks = content.split('GAME COMPLETE:')
    
    for block in game_blocks[1:]:  # Skip header
        try:
            # Extract teams and scores
            match_line = block.split('\n')[0].strip()
            # Format: "AWAY @ HOME"
            teams_match = re.search(r'(\w+)\s+@\s+(\w+)', match_line)
            if not teams_match:
                continue
            away_team = teams_match.group(1)
            home_team = teams_match.group(2)
            
            # Extract final score
            score_line = [l for l in block.split('\n') if 'FINAL SCORE:' in l][0]
            score_match = re.search(r'(\w+)\s+(\d+)\s+-\s+(\w+)\s+(\d+)', score_line)
            if not score_match:
                continue
            
            score_away = int(score_match.group(2))
            score_home = int(score_match.group(4))
            
            # Extract overall ratings
            rating_section = block.split('Overall Rating')[1].split('\n')[0].strip()
            ratings = re.findall(r'(\d+)', rating_section)
            if len(ratings) < 2:
                continue
            
            away_rating = int(ratings[0])
            home_rating = int(ratings[1])
            
            games.append({
                'away_team': away_team,
                'home_team': home_team,
                'away_score': score_away,
                'home_score': score_home,
                'away_rating': away_rating,
                'home_rating': home_rating,
                'winner': away_team if score_away > score_home else (home_team if score_home > score_away else 'TIE'),
                'favorite': away_team if away_rating > home_rating else (home_team if home_rating > away_rating else 'EVEN'),
                'rating_diff': abs(away_rating - home_rating),
                'score_diff': abs(score_away - score_home)
            })
        except Exception as e:
            continue
    
    return games

def analyze_upsets(games):
    """Analyze how often favorites win by rating differential."""
    
    # Group by rating differential buckets
    buckets = {
        '0-2 pts': [],   # Very close
        '3-5 pts': [],   # Close
        '6-9 pts': [],   # Moderate
        '10-14 pts': [], # Significant
        '15+ pts': []    # Large
    }
    
    for game in games:
        diff = game['rating_diff']
        if diff <= 2:
            bucket = '0-2 pts'
        elif diff <= 5:
            bucket = '3-5 pts'
        elif diff <= 9:
            bucket = '6-9 pts'
        elif diff <= 14:
            bucket = '10-14 pts'
        else:
            bucket = '15+ pts'
        
        buckets[bucket].append(game)
    
    print("=== FAVORITES WIN RATE BY RATING DIFFERENTIAL ===\n")
    
    total_games = 0
    total_favorite_wins = 0
    total_upsets = 0
    
    for bucket_name in ['0-2 pts', '3-5 pts', '6-9 pts', '10-14 pts', '15+ pts']:
        bucket_games = buckets[bucket_name]
        if not bucket_games:
            continue
        
        favorite_wins = sum(1 for g in bucket_games if g['winner'] == g['favorite'])
        upsets = sum(1 for g in bucket_games if g['winner'] != g['favorite'] and g['winner'] != 'TIE')
        ties = sum(1 for g in bucket_games if g['winner'] == 'TIE')
        
        total_games += len(bucket_games)
        total_favorite_wins += favorite_wins
        total_upsets += upsets
        
        win_pct = (favorite_wins / len(bucket_games)) * 100 if bucket_games else 0
        
        print(f"Rating Diff {bucket_name}:")
        print(f"  Games: {len(bucket_games)}")
        print(f"  Favorite Wins: {favorite_wins} ({win_pct:.1f}%)")
        print(f"  Upsets: {upsets} ({(upsets/len(bucket_games)*100):.1f}%)")
        if ties > 0:
            print(f"  Ties: {ties}")
        print()
    
    print(f"OVERALL:")
    print(f"  Total Games: {total_games}")
    print(f"  Favorite Wins: {total_favorite_wins} ({(total_favorite_wins/total_games*100):.1f}%)")
    print(f"  Upsets: {total_upsets} ({(total_upsets/total_games*100):.1f}%)")
    print()
    
    # Analyze blowouts
    print("=== BLOWOUT ANALYSIS ===\n")
    
    blowout_threshold = 21  # 3+ TDs
    blowouts = [g for g in games if g['score_diff'] >= blowout_threshold]
    
    # How many blowouts were expected (large rating diff)?
    expected_blowouts = sum(1 for g in blowouts if g['rating_diff'] >= 10)
    unexpected_blowouts = len(blowouts) - expected_blowouts
    
    print(f"Total Blowouts (21+ pts): {len(blowouts)} ({(len(blowouts)/len(games)*100):.1f}%)")
    print(f"  Expected (10+ rating diff): {expected_blowouts}")
    print(f"  Unexpected (<10 rating diff): {unexpected_blowouts}")
    print()
    
    # Close games
    close_threshold = 7  # One score game
    close_games = [g for g in games if g['score_diff'] <= close_threshold]
    print(f"Close Games (≤7 pts): {len(close_games)} ({(len(close_games)/len(games)*100):.1f}%)")
    
    # Of close games, how many had close ratings?
    close_and_close = sum(1 for g in close_games if g['rating_diff'] <= 5)
    print(f"  Close ratings (≤5): {close_and_close} ({(close_and_close/len(close_games)*100):.1f}%)")

if __name__ == '__main__':
    games = parse_game_stats('logs/game_stats_season_1.txt')
    print(f"Loaded {len(games)} games\n")
    analyze_upsets(games)
