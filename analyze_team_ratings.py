#!/usr/bin/env python3
"""
Analyze team rating distributions to understand competitive balance.
"""

import re
from collections import defaultdict

def parse_team_ratings(filename):
    """Extract all team ratings from game stats."""
    teams = defaultdict(lambda: {'offense': [], 'defense': [], 'overall': []})
    
    with open(filename, 'r') as f:
        content = f.read()
    
    # Split by game separators
    game_blocks = content.split('GAME COMPLETE:')
    
    for block in game_blocks[1:]:  # Skip header
        try:
            # Extract teams
            match_line = block.split('\n')[0].strip()
            teams_match = re.search(r'(\w+)\s+@\s+(\w+)', match_line)
            if not teams_match:
                continue
            away_team = teams_match.group(1)
            home_team = teams_match.group(2)
            
            # Extract ratings section
            ratings_section = block.split('TEAM RATINGS:')[1].split('================================================================================')[0]
            
            # Parse offense ratings
            offense_line = [l for l in ratings_section.split('\n') if 'Offense Rating' in l][0]
            offense_vals = re.findall(r'(\d+)', offense_line)
            if len(offense_vals) >= 2:
                teams[away_team]['offense'].append(int(offense_vals[0]))
                teams[home_team]['offense'].append(int(offense_vals[1]))
            
            # Parse defense ratings
            defense_line = [l for l in ratings_section.split('\n') if 'Defense Rating' in l][0]
            defense_vals = re.findall(r'(\d+)', defense_line)
            if len(defense_vals) >= 2:
                teams[away_team]['defense'].append(int(defense_vals[0]))
                teams[home_team]['defense'].append(int(defense_vals[1]))
            
            # Parse overall ratings
            overall_line = [l for l in ratings_section.split('\n') if 'Overall Rating' in l][0]
            overall_vals = re.findall(r'(\d+)', overall_line)
            if len(overall_vals) >= 2:
                teams[away_team]['overall'].append(int(overall_vals[0]))
                teams[home_team]['overall'].append(int(overall_vals[1]))
                
        except Exception as e:
            continue
    
    # Average ratings for each team
    team_ratings = {}
    for team, ratings in teams.items():
        if ratings['overall']:
            team_ratings[team] = {
                'offense': sum(ratings['offense']) / len(ratings['offense']),
                'defense': sum(ratings['defense']) / len(ratings['defense']),
                'overall': sum(ratings['overall']) / len(ratings['overall']),
                'games': len(ratings['overall'])
            }
    
    return team_ratings

def analyze_ratings(team_ratings):
    """Analyze rating distributions."""
    
    print(f"=== TEAM RATING DISTRIBUTION ({len(team_ratings)} teams) ===\n")
    
    # Overall ratings
    overall_ratings = [t['overall'] for t in team_ratings.values()]
    offense_ratings = [t['offense'] for t in team_ratings.values()]
    defense_ratings = [t['defense'] for t in team_ratings.values()]
    
    print("OVERALL RATINGS:")
    print(f"  Min: {min(overall_ratings):.1f}")
    print(f"  Max: {max(overall_ratings):.1f}")
    print(f"  Range: {max(overall_ratings) - min(overall_ratings):.1f}")
    print(f"  Average: {sum(overall_ratings)/len(overall_ratings):.1f}")
    print(f"  Std Dev: {(sum((x - sum(overall_ratings)/len(overall_ratings))**2 for x in overall_ratings) / len(overall_ratings))**0.5:.1f}")
    print()
    
    print("OFFENSE RATINGS:")
    print(f"  Min: {min(offense_ratings):.1f}")
    print(f"  Max: {max(offense_ratings):.1f}")
    print(f"  Range: {max(offense_ratings) - min(offense_ratings):.1f}")
    print(f"  Average: {sum(offense_ratings)/len(offense_ratings):.1f}")
    print(f"  Std Dev: {(sum((x - sum(offense_ratings)/len(offense_ratings))**2 for x in offense_ratings) / len(offense_ratings))**0.5:.1f}")
    print()
    
    print("DEFENSE RATINGS:")
    print(f"  Min: {min(defense_ratings):.1f}")
    print(f"  Max: {max(defense_ratings):.1f}")
    print(f"  Range: {max(defense_ratings) - min(defense_ratings):.1f}")
    print(f"  Average: {sum(defense_ratings)/len(defense_ratings):.1f}")
    print(f"  Std Dev: {(sum((x - sum(defense_ratings)/len(defense_ratings))**2 for x in defense_ratings) / len(defense_ratings))**0.5:.1f}")
    print()
    
    # Find teams with biggest splits
    print("=== TEAMS WITH BIGGEST OFFENSE/DEFENSE IMBALANCE ===\n")
    imbalances = []
    for team, ratings in team_ratings.items():
        split = abs(ratings['offense'] - ratings['defense'])
        imbalances.append((team, ratings['offense'], ratings['defense'], ratings['overall'], split))
    
    imbalances.sort(key=lambda x: x[4], reverse=True)
    
    print("Top 10 Most Imbalanced Teams:")
    for i, (team, off, def_, ovr, split) in enumerate(imbalances[:10], 1):
        if off > def_:
            print(f"{i:2}. {team}: Offense {off:.1f}, Defense {def_:.1f} (Overall {ovr:.1f}) - Offense-heavy by {split:.1f}")
        else:
            print(f"{i:2}. {team}: Offense {off:.1f}, Defense {def_:.1f} (Overall {ovr:.1f}) - Defense-heavy by {split:.1f}")
    print()
    
    # Show distribution buckets
    print("=== OVERALL RATING DISTRIBUTION ===\n")
    buckets = {
        '50-59': 0,
        '60-69': 0,
        '70-79': 0,
        '80-89': 0,
        '90-99': 0
    }
    
    for rating in overall_ratings:
        if rating < 60:
            buckets['50-59'] += 1
        elif rating < 70:
            buckets['60-69'] += 1
        elif rating < 80:
            buckets['70-79'] += 1
        elif rating < 90:
            buckets['80-89'] += 1
        else:
            buckets['90-99'] += 1
    
    for bucket, count in buckets.items():
        pct = (count / len(overall_ratings)) * 100
        bar = '#' * int(pct / 2)
        print(f"{bucket}: {count:2} ({pct:5.1f}%) {bar}")

if __name__ == '__main__':
    team_ratings = parse_team_ratings('logs/game_stats_season_1.txt')
    analyze_ratings(team_ratings)
