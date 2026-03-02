# Confidence Mechanics Analysis

## Overview
Confidence is a dynamic stat that changes during games and across the season, affecting player performance through the `xFactor` attribute.

## How Confidence Works

### 1. Confidence Range
- **Starting value**: Random between -2 and +2
- **In-game range**: Unbounded during the game (updated incrementally)
- **Season range**: Clamped between -5 and +5 after each game
- **Precision**: Rounded to 3 decimal places

### 2. Impact on Performance

#### Confidence → xFactor Calculation
```python
xFactor = round(
    (((focus*1.8) + (discipline*1.2))/3) +           # Mental skills (60%)
    ((confidenceModifier*1.8) + (determinationModifier*1.2)/3) +  # Modifiers (60%)
    (luckModifier)                                    # Random luck
)
```

**Confidence weight**: `confidenceModifier * 1.8`

**Example impact**:
- confidenceModifier = +5: xFactor increases by +9 points
- confidenceModifier = -5: xFactor decreases by -9 points
- confidenceModifier = +2.5: xFactor increases by +4.5 points

#### xFactor → Game Performance

**For Quarterbacks (Pass plays)**:
```python
baseAccuracy = (qbAccuracy + qbXFactor) / 2 + pressureMod
```
- xFactor weighted equally with accuracy
- High confidence QB: Better throw quality, fewer interceptions
- Low confidence QB: Worse throw quality, more turnovers

**For Running Backs (Run plays)**:
```python
# Initial burst
rbPowerRating = (power*1.5 + agility*1.2 + playMakingAbility*0.8 + xFactor*0.5) / 4

# Breakaway speed
stage2Offense = (speed*1.5 + agility*1.2 + playMakingAbility*0.8 + xFactor*0.5) / 4
```
- xFactor has 0.5 weight in both stages
- Affects both initial yardage and breakaway potential

**For Kickers**:
- xFactor included in overall rating calculation
- Affects field goal success probability

## In-Game Confidence Updates

### Positive Changes (Gain Confidence)
- **Good run play** (+0.005): Initial burst ≥ 50% of max yards
- **Pass completion** (+0.01): QB and receiver both gain
- **Good run** (+0.01): Overall successful run
- **Field goal range**:
  - 20-29 yards: +0.005 (good) / -0.02 (miss)
  - 30-34 yards: +0.01 (good) / -0.015 (miss)
  - 35-39 yards: +0.01 (good) / -0.015 (miss)
  - 40-44 yards: +0.015 (good) / -0.01 (miss)
  - 45-49 yards: +0.015 (good) / -0.01 (miss)
  - 50-54 yards: +0.015 (good) / -0.01 (miss)
  - 55-59 yards: +0.02 (good) / -0.005 (miss)
  - 60+ yards: +0.025 (good) / -0.005 (miss)

### Negative Changes (Lose Confidence)
- **Fumble lost** (-0.02): Runner loses confidence
- **Missed field goals**: See table above

## Post-Game Confidence Adjustments

After each game, in-game confidence is averaged with season confidence:
```python
attributes.confidenceModifier = (attributes.confidenceModifier + gameAttributes.confidenceModifier) / 2
```

### Team Performance Impact
**Winning streak**:
- +0 to +0.25 confidence boost (random)

**Losing streak (3+ losses)**:
- Depends on player attitude:
  - Low attitude (<70): -0.20 to 0 confidence
  - Medium attitude (70-79): -0.10 to 0 confidence
  - High attitude (80-89): -0.05 to 0 confidence
  - Very high attitude (90+): No confidence loss (determination boost instead)

**After adjustment, clamped to [-5, +5]**

## Actual Impact Analysis

### Maximum Possible Impact

**Best Case (+5 confidence)**:
- xFactor increase: +9 points
- For QB with 85 accuracy: baseAccuracy increases from 85 → 89.5
- ~5% improvement in throw quality

**Worst Case (-5 confidence)**:
- xFactor decrease: -9 points  
- For QB with 85 accuracy: baseAccuracy decreases from 85 → 80.5
- ~5% reduction in throw quality

### Typical In-Game Swing
- After 60 plays with 75% success rate: ~+0.45 confidence
- xFactor change: +0.81 points
- Practical impact: ~0.4 points on baseAccuracy (~0.5% improvement)

### Season-Long Impact
- Hot streak (5+ wins): Up to +2.5 confidence from team performance
- Cold streak (5+ losses, low attitude): Down to -2.5 confidence
- Combined with in-game changes: Can reach ±5 limit
- Total xFactor swing: ±9 points (±4-5% performance)

## Current Assessment

### Strengths
✅ Dynamic system that responds to performance  
✅ Affects all aspects of play (passing, running, kicking)  
✅ Team performance integration creates realistic morale effects  
✅ Bounded limits prevent extreme swings

### Potential Issues
⚠️ **In-game updates are very small**: Most plays give +0.01 confidence  
⚠️ **Slow accumulation**: Would need 100+ successful plays to gain +1 confidence  
⚠️ **Gets reset post-game**: In-game confidence is averaged with season value, dampening effect  
⚠️ **Real impact is moderate**: ±5 confidence = ±9 xFactor = ~±5% performance  

### Impact Scale
- **Minimal** (0-0.5 confidence): <1% performance change
- **Noticeable** (0.5-2 confidence): 1-3% performance change  
- **Significant** (2-4 confidence): 3-7% performance change
- **Major** (4-5 confidence): 7-9% performance change

## Recommendations

If you want confidence to have **more impact**:

1. **Increase in-game update magnitudes**:
   - Change +0.01 → +0.05 for successful plays
   - Change -0.02 → -0.05 for failures
   - Allows confidence to meaningfully change during a single game

2. **Increase xFactor weighting**:
   - Change `confidenceModifier * 1.8` → `confidenceModifier * 3.0`
   - +5 confidence would give +15 xFactor instead of +9

3. **Don't average post-game**:
   - Replace with `attributes.confidenceModifier += (gameAttributes.confidenceModifier * 0.5)`
   - Preserves more of the in-game momentum

4. **Add momentum multipliers**:
   - Back-to-back successful plays: multiply confidence gain by 1.5x
   - Clutch situations (4th quarter, close game): double confidence impact

If you want confidence to have **less impact**:

1. **Reduce range**: Change [-5, 5] → [-3, 3]
2. **Reduce weight**: Change `* 1.8` → `* 1.0`
3. **Remove team performance effects**: Only use in-game updates
