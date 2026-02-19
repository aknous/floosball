# Win Probability Feature - Implementation Summary

## Overview
Implemented a formula-based win probability calculator that tracks the likelihood of each team winning throughout the game based on:
- Score differential
- Time remaining
- Possession
- Field position  
- Down & distance

## Implementation Details

### Core Calculation (`calculateWinProbability()`)
Located in `floosball_game.py` (lines ~2320-2400)

**Formula**: Logistic regression approach
```
WinProb(home) = 100 / (1 + e^(-k * adjusted_score_diff))
```

Where:
- `k` = sensitivity factor (0.15 * time_factor)
- `adjusted_score_diff` = actual score diff + expected points from current situation

### Expected Points Model (`calculateExpectedPoints()`)
Estimates points offense will score from current field position and down/distance.

**Field Position Values:**
- Own 5 or worse: -1.0 pts (safety risk)
- Own 20: 0.0 pts
- Own 40: 1.0 pts  
- Midfield: 2.0 pts
- Opponent 40: 2.5 pts
- Opponent 30: 3.0 pts
- Opponent 20 (FG range): 3.5 pts
- Red zone: 4.5 pts
- Inside 10: 5.5 pts

**Down Adjustments:**
- 1st down: 100% of base EP
- 2nd & short: 95%, 2nd & medium: 85%, 2nd & long: 70%
- 3rd & short: 80%, 3rd & medium: 50%, 3rd & long: 20%
- 4th down: 70% (if in FG range), 10% (otherwise, likely punt)

### Time Sensitivity
Win probability becomes more sensitive to score as time decreases:

| Time Remaining | Time Factor | Effect |
|---|---|---|
| > 30 minutes (2+ quarters) | 0.6x | Score matters less |
| 15-30 min (1-2 quarters) | 1.0x | Normal sensitivity |
| 5-15 min | 1.5x | Score matters more |
| 2-5 min | 2.5x | Critical period |
| < 2 min | 4.0x | Score dominates |

### Integration Points

1. **Initialization** (`playGame()` line ~1515):
   - Start at 50/50

2. **Every Play** (before play execution, line ~1695):
   - Calculate and store in `self.homeTeamWinProbability` / `self.awayTeamWinProbability`

3. **Verbose Logging** (line ~1725):
   - Logged with play-by-play details

4. **Game End**:
   - Sets to 100/0 for winner

## Usage

### In Game Simulation
Win probability is automatically calculated before each play and stored in game object:
```python
game.homeTeamWinProbability  # e.g., 67.3
game.awayTeamWinProbability  # e.g., 32.7
```

### In Verbose Logs
Appears in play-by-play logs:
```
--- PLAY #45 ---
Quarter 4, 2:34 - Score: AWAY 21, HOME 24
Win Probability: HOME 78.5%, AWAY 21.5%
3rd & 7 at AWAY 35
```

## Example Scenarios

### Early Game (Q1, 10:00)
- Tied 0-0, home has ball at midfield, 1st & 10
- **Result**: HOME 52%, AWAY 48%
- *Score barely matters, possession gives slight edge*

### Mid Game (Q2, 5:00)  
- Tied 14-14, home in red zone (15 yard line), 1st & 10
- **Result**: HOME 60%, AWAY 40%
- *Red zone position worth ~4.5 expected points*

### Late Game (Q4, 2:00)
- HOME up 24-21, away has ball at own 20, 1st & 10
- **Result**: HOME 77%, AWAY 23%
- *3-point lead with 2 min left = big advantage*

### Critical Moment (Q4, 0:30)
- HOME up 24-21, away at home 35, 4th & 2
- **Result**: HOME 85%, AWAY 15%
- *4th down kills expected points, time almost expired*

### Comeback Scenario (Q4, 1:00)
- HOME down 20-24, at opponent 25 (FG range), 2nd & 7
- **Result**: HOME 28%, AWAY 72%
- *In FG range but still need TD, little time*

## Files Created

1. **`floosball_game.py`** - Core implementation
   - `calculateWinProbability()` method
   - `calculateExpectedPoints()` method
   - Integration into game loop

2. **`demo_win_probability.py`** - Demonstration script
   - Shows 7 realistic game scenarios
   - Explains how different factors affect win probability

3. **`test_win_probability.py`** - Test script (WIP)
   - Runs full game simulation
   - Extracts win probability swings from logs

## Future Enhancements

Potential improvements:
1. **Team strength adjustment**: Factor in team ratings for pre-game probabilities
2. **Timeout consideration**: Account for timeouts remaining in late-game scenarios
3. **Weather/conditions**: Adjust for environmental factors
4. **Historical calibration**: Tune parameters based on actual game outcomes
5. **Visualization**: Graph win probability throughout game
6. **Leverage index**: Show how much each play could swing probability

## Testing

Run the demo to see how it works:
```bash
python3 demo_win_probability.py
```

The calculator provides realistic win probabilities that:
- Start at 50/50
- Account for game situation (score, time, field position)
- Become more decisive as time runs out
- Never show 0% or 100% until game is actually over (capped at 0.1%-99.9%)
