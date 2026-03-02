# Confidence Impact Adjustment - Feb 20, 2026

## Changes Made

### 1. Increased Confidence Weight in xFactor
**File**: `floosball_player.py`
- **Before**: `confidenceModifier * 1.8`
- **After**: `confidenceModifier * 2.2`
- **Impact**: ~22% increase in confidence's contribution to xFactor

### 2. Tripled In-Game Confidence Updates
**File**: `floosball_game.py`

#### Successful Plays
| Event | Old Value | New Value | Multiplier |
|-------|-----------|-----------|------------|
| Touchdown (Run) | +0.01 | +0.03 | 3x |
| Touchdown (Pass, QB) | +0.01 | +0.03 | 3x |
| Touchdown (Pass, WR) | +0.01 | +0.03 | 3x |
| Good breakaway run | +0.005 | +0.015 | 3x |
| FG 20-30 yards | +0.005 | +0.015 | 3x |
| FG 30-40 yards | +0.01 | +0.03 | 3x |
| FG 40-45 yards | +0.015 | +0.045 | 3x |
| FG 45-50 yards | +0.015 | +0.045 | 3x |
| FG 50-55 yards | +0.015 | +0.045 | 3x |
| FG 55-60 yards | +0.02 | +0.06 | 3x |
| FG 60+ yards | +0.025 | +0.075 | 3x |

#### Failed Plays
| Event | Old Value | New Value | Multiplier |
|-------|-----------|-----------|------------|
| Fumble lost | -0.02 | -0.05 | 2.5x |
| Missed FG <30 yd | -0.02 | -0.05 | 2.5x |
| Missed FG 30-40 yd | -0.015 | -0.04 | ~2.7x |
| Missed FG 40-50 yd | -0.01 | -0.03 | 3x |
| Missed FG 50-55 yd | -0.01 | -0.03 | 3x |
| Missed FG 55-60 yd | -0.005 | -0.015 | 3x |
| Missed FG 60+ yd | -0.005 | -0.015 | 3x |

## Expected Impact

### Before Changes
**Typical game (QB with 30 completions)**:
- In-game confidence gain: +0.30
- Post-game average: +0.15 (averaged with season value)
- xFactor impact: +0.27 points
- **Performance boost: ~0.3%**

**Maximum (+5 confidence)**:
- xFactor: +9 points
- **Performance boost: ~5%**

### After Changes
**Typical game (QB with 30 completions)**:
- In-game confidence gain: +0.90
- Post-game average: +0.45 (averaged with season value)
- xFactor impact: +0.99 points
- **Performance boost: ~1.0%** (3.3x improvement)

**Maximum (+5 confidence)**:
- xFactor: +11 points
- **Performance boost: ~6.1%** (1.22x improvement)

## Net Result
- **Typical game impact**: 0.3% → 1.0% (3.3x more noticeable)
- **Maximum impact**: 5% → 6.1% (1.22x stronger)
- **Confidence accumulates ~3x faster** during games
- Still bounded by ±5 limit to prevent extreme swings

## Rationale
These moderate increases make confidence more impactful in individual games while maintaining reasonable bounds. Players will see more noticeable momentum swings during hot/cold streaks, but the post-game averaging still prevents single-game extremes from dominating season-long trends.

**Impact level**: Moderate increase - noticeable but not game-breaking
**Status**: Ready for playtesting and evaluation
