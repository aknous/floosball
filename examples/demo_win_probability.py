#!/usr/bin/env python3
"""
Win Probability Demo - Shows how the calculation works with different game scenarios
"""

import numpy as np

def calculate_win_probability_demo(home_score, away_score, quarter, seconds_in_quarter, 
                                   possession, yards_to_endzone, down, yards_to_first,
                                   home_elo=1500, away_elo=1500):
    """
    Demo version of win probability calculator with detailed output.
    Includes ELO ratings for pre-game expectations.
    """
    # Calculate total seconds remaining
    if quarter == 1:
        total_seconds = seconds_in_quarter + (3 * 900)
    elif quarter == 2:
        total_seconds = seconds_in_quarter + (2 * 900)
    elif quarter == 3:
        total_seconds = seconds_in_quarter + 900
    else:  # Q4
        total_seconds = seconds_in_quarter
    
    # ELO-based adjustment
    elo_diff = home_elo - away_elo
    elo_point_advantage = elo_diff / 25.0  # 25 ELO ≈ 1 point
    
    # ELO influence decreases as game progresses
    total_game_time = 3600
    time_elapsed = total_game_time - total_seconds
    elo_influence = max(0.2, 1.0 - (time_elapsed / total_game_time) * 0.8)
    elo_adjusted_advantage = elo_point_advantage * elo_influence
    
    score_diff = home_score - away_score
    
    # Calculate expected points from field position
    field_position = 100 - yards_to_endzone
    
    if field_position < 5:
        base_ep = -1.0
    elif field_position < 20:
        base_ep = 0.0
    elif field_position < 40:
        base_ep = 1.0
    elif field_position < 50:
        base_ep = 2.0
    elif field_position < 60:
        base_ep = 2.5
    elif field_position < 70:
        base_ep = 3.0
    elif field_position < 80:
        base_ep = 3.5
    elif field_position < 90:
        base_ep = 4.5
    else:
        base_ep = 5.5
    
    # Down factor
    if down == 1:
        down_factor = 1.0
    elif down == 2:
        down_factor = 0.9 if yards_to_first <= 5 else 0.7
    elif down == 3:
        down_factor = 0.8 if yards_to_first <= 3 else 0.4
    else:
        down_factor = 0.3 if field_position >= 60 else 0.1
    
    expected_points = base_ep * down_factor
    
    # Adjust by possession
    if possession == 'home':
        home_exp = expected_points
        away_exp = 0
    else:
        home_exp = 0
        away_exp = expected_points
    
    adjusted_score_diff = score_diff + home_exp - away_exp + elo_adjusted_advantage
    
    # Time scaling
    if total_seconds > 1800:
        time_factor = 0.6
    elif total_seconds > 900:
        time_factor = 1.0
    elif total_seconds > 300:
        time_factor = 1.5
    elif total_seconds > 120:
        time_factor = 2.5
    else:
        time_factor = 4.0
    
    k = 0.15 * time_factor
    home_win_prob = 100 / (1 + np.exp(-k * adjusted_score_diff))
    away_win_prob = 100 - home_win_prob
    
    return {
        'home_wp': round(home_win_prob, 1),
        'away_wp': round(away_win_prob, 1),
        'expected_points': round(expected_points, 2),
        'elo_advantage': round(elo_adjusted_advantage, 2),
        'elo_influence': round(elo_influence * 100, 1),
        'time_factor': time_factor,
        'adjusted_diff': round(adjusted_score_diff, 2)
    }

def format_time(seconds):
    minutes = seconds // 60
    secs = seconds % 60
    return f"{minutes}:{secs:02d}"

print("="*80)
print("WIN PROBABILITY CALCULATOR DEMO (with ELO)")
print("="*80)
print()

# Demo Scenarios
scenarios = [
    {
        'desc': "Start of game - Opening kickoff (Even teams)",
        'home_score': 0, 'away_score': 0,
        'quarter': 1, 'seconds': 900,
        'possession': 'home', 'yards_to_endzone': 75,
        'down': 1, 'yards_to_first': 10,
        'home_elo': 1500, 'away_elo': 1500
    },
    {
        'desc': "Start of game - Elite vs Average (1600 ELO vs 1500)",
        'home_score': 0, 'away_score': 0,
        'quarter': 1, 'seconds': 900,
        'possession': 'home', 'yards_to_endzone': 75,
        'down': 1, 'yards_to_first': 10,
        'home_elo': 1600, 'away_elo': 1500
    },
    {
        'desc': "Q1: Underdog up 7-0 (1400 ELO vs 1550)",
        'home_score': 7, 'away_score': 0,
        'quarter': 1, 'seconds': 600,
        'possession': 'away', 'yards_to_endzone': 50,
        'down': 1, 'yards_to_first': 10,
        'home_elo': 1400, 'away_elo': 1550
    },
    {
        'desc': "Q2: Tied 14-14, home has ball in red zone (Even teams)",
        'home_score': 14, 'away_score': 14,
        'quarter': 2, 'seconds': 300,
        'possession': 'home', 'yards_to_endzone': 15,
        'down': 1, 'yards_to_first': 10,
        'home_elo': 1500, 'away_elo': 1500
    },
    {
        'desc': "Q4: Tied with 2 min, favorite has ball (1580 ELO vs 1480)",
        'home_score': 21, 'away_score': 21,
        'quarter': 4, 'seconds': 120,
        'possession': 'home', 'yards_to_endzone': 70,
        'down': 1, 'yards_to_first': 10,
        'home_elo': 1580, 'away_elo': 1480
    },
    {
        'desc': "Q4: Home up 3, 2 min left, away has ball (Underdog winning)",
        'home_score': 24, 'away_score': 21,
        'quarter': 4, 'seconds': 120,
        'possession': 'away', 'yards_to_endzone': 80,
        'down': 1, 'yards_to_first': 10,
        'home_elo': 1450, 'away_elo': 1550
    },
    {
        'desc': "Q4: Home up 3, away at home 35, 4th & 2, 30 sec left",
        'home_score': 24, 'away_score': 21,
        'quarter': 4, 'seconds': 30,
        'possession': 'away', 'yards_to_endzone': 65,
        'down': 4, 'yards_to_first': 2
    },
    {
        'desc': "Q4: Home down 4, at opp 25 (FG range), 1 min left",
        'home_score': 20, 'away_score': 24,
        'quarter': 4, 'seconds': 60,
        'possession': 'home', 'yards_to_endzone': 25,
        'down': 2, 'yards_to_first': 7
    },
    {
        'desc': "Q4: Home up 10, away at own 10, 3rd & 15, 45 sec",
        'home_score': 27, 'away_score': 17,
        'quarter': 4, 'seconds': 45,
        'possession': 'away', 'yards_to_endzone': 90,
        'down': 3, 'yards_to_first': 15
    },
]

for i, scenario in enumerate(scenarios, 1):
    result = calculate_win_probability_demo(
        scenario['home_score'], scenario['away_score'],
        scenario['quarter'], scenario['seconds'],
        scenario['possession'], scenario['yards_to_endzone'],
        scenario['down'], scenario['yards_to_first'],
        scenario.get('home_elo', 1500), scenario.get('away_elo', 1500)
    )
    
    print(f"Scenario {i}: {scenario['desc']}")
    print(f"  Score: HOME {scenario['home_score']} - AWAY {scenario['away_score']}")
    print(f"  ELO: HOME {scenario.get('home_elo', 1500)} - AWAY {scenario.get('away_elo', 1500)}")
    print(f"  Time: Q{scenario['quarter']} {format_time(scenario['seconds'])}")
    print(f"  Situation: {scenario['possession'].upper()} ball, {scenario['down']}{['st','nd','rd','th'][min(scenario['down']-1,3)]} & {scenario['yards_to_first']}, {100-scenario['yards_to_endzone']} yard line")
    print(f"  Expected Points: {result['expected_points']} | ELO Advantage: {result['elo_advantage']} ({result['elo_influence']}% influence)")
    print(f"  Adjusted Score Diff: {result['adjusted_diff']}")
    print(f"  → HOME Win Prob: {result['home_wp']}%")
    print(f"  → AWAY Win Prob: {result['away_wp']}%")
    print()

print("="*80)
print("NOTES:")
print("- ELO difference: ~25 ELO points ≈ 1 point advantage")
print("- ELO influence: 100% at kickoff → 20% at end of regulation")
print("- Early game: ELO + field position matter most")
print("- Late game: Actual score dominates")  
print("="*80)
