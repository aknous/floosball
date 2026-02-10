# Floosball Game Mechanics Audit
*Comprehensive audit of floosball_game.py following passing system improvements*

## Executive Summary

After implementing sophisticated 5-stage probability-based passing mechanics, this audit identifies opportunities to apply similar improvements across other game systems. The passing system now uses:
- Gaussian distributions for receiver openness and air yardage
- Logistic curves for sack probability and pressure impact
- Exponential decay for sack yardage and YAC
- Vision-based perception errors for QB decision-making
- Mental attributes (vision, discipline, pressure handling) affecting physical performance

**Key Findings:**
1. ✅ **Passing mechanics**: Excellent - sophisticated probability-based system
2. ⚠️ **Running mechanics**: Good foundation, but inconsistent with passing approach
3. ⚠️ **Play calling**: Overly deterministic, could use situational AI
4. ⚠️ **Field goal mechanics**: Recently improved, good
5. ⚠️ **Code quality**: Significant duplication in stat tracking
6. ⚠️ **Mental attributes**: Only used in passing, should extend to other plays

---

## 1. Running Play Mechanics (runPlay method)

### Current Implementation (Lines 2297-2429)
**Strengths:**
- Already uses 2-stage probability system (initial burst + breakaway)
- Gaussian distribution for stage 1 yardage
- Exponential decay for stage 2 (breakaway runs)
- Includes blocker contribution (TE blocking)
- Pressure modifier applied to runner performance
- Fumble probability with resistance modifiers

**Issues Identified:**

#### 1.1 Missing Mental Attributes
```python
# Current: Only uses physical attributes
stage1Offense = (((self.runner.attributes.power*1.5) + 
                  (self.runner.attributes.agility*1.2) + 
                  (self.runner.attributes.playMakingAbility*.8) + 
                  (self.runner.attributes.xFactor*.5))/4)
```

**Recommendation:** Add RB vision and discipline to running plays
- **Vision**: Should affect hole identification (which gap to hit)
  - High vision (85+): Consistently finds best gap (±5% accuracy)
  - Medium vision (70-84): Sometimes misreads holes (±15% accuracy)
  - Low vision (<70): Often chooses wrong gap (±25% accuracy)
- **Discipline**: Should affect decision to cut back vs hit assigned hole
  - High discipline: Follows blocking scheme, consistent gains
  - Low discipline: Freelances, higher variance (bigger gains OR losses)
- **Pressure Handling**: Already applied but could be more nuanced

**Implementation Approach:**
```python
# Similar to passing target selection:
# 1. Calculate multiple gaps' effectiveness (like receiver openness)
# 2. RB's vision determines how accurately they perceive best gap
# 3. Discipline determines if they stick to perceived best gap or take risks
```

#### 1.2 No Fatigue or Workload Modeling
**Issue:** RB performance doesn't degrade with heavy usage
- No carry count affecting fumble rate
- No stamina affecting breakaway speed
- No injury risk increase with workload

**Recommendation:** Add workload tracking (low priority)

---

## 2. Pass Play Mechanics (passPlay method)

### Current Implementation (Lines 2653-2863)
**Status:** ✅ **EXCELLENT** - Recently redesigned with probability curves

**Strengths:**
- 5-stage probability system (openness → selection → sack/throw → catch → YAC)
- Vision-based perception errors for target selection
- Discipline-based decision making (throwaway vs forcing)
- Logistic sack probability (1-35% based on matchup)
- Exponential pressure degradation (60-100% throw quality)
- Gaussian air yardage distribution
- Exponential YAC decay
- Pressure handling integrated throughout

**No major issues identified** - this is the gold standard for other mechanics

---

## 3. Play Calling Logic (playCaller method)

### Current Implementation (Lines 717-1200+)
**Status:** ⚠️ **NEEDS IMPROVEMENT** - Overly deterministic

#### 3.1 Deterministic Play Selection
```python
# Current: Hard-coded situational logic
if self.down <= 2:
    if self.yardsToEndzone <= 10:
        x = batched_randint(1,10)
        if x <= 5:
            self.play.runPlay()
        else:
            # Pass logic
```

**Issues:**
- Random number decides run vs pass (not team tendency)
- Doesn't consider QB/RB skill differential
- No offensive coordinator "intelligence"
- No adaptation to what's working
- No consideration of defense's weaknesses

**Recommendation:** Implement tendency-based play calling

```python
# Suggested approach:
class PlayCallTendencies:
    def __init__(self, team):
        self.baseRunPercentage = 40-60  # Based on QB vs RB ratings
        self.passRatioShort = 30-40%     # Based on QB accuracy
        self.passRatioMedium = 40-50%
        self.passRatioLong = 10-30%      # Based on WR speed, QB arm
        self.aggressiveness = 40-70      # Based on coach? team style?
        
    def getPlayCall(self, down, distance, fieldPos, scoreDiff, timeLeft):
        # Calculate run/pass probability based on situation
        # Adjust for team strengths vs defense weaknesses
        # Add variance but maintain team identity
```

**Benefits:**
- Teams would have identifiable styles (pass-heavy vs run-heavy)
- Better matchup exploitation (throw on bad secondaries)
- More realistic play distribution
- Could track "what's working" and adjust in-game

#### 3.2 Success Probability Calculations Not Used
```python
# Lines 718-740: Calculates success probabilities but rarely uses them
runSuccessProbability = round(max(0, min(1, runSuccessProbability)) * 100)
shortPassSuccessProbability = ...
medPassSuccessProbability = ...
longPassSuccessProbability = ...

# But then play calling ignores these and uses random rolls!
```

**Recommendation:** Use calculated probabilities to inform decisions
- High-discipline coaches choose higher probability plays
- Low-discipline coaches take more risks
- Trailing teams shift toward higher variance plays
- Leading teams play more conservatively

---

## 4. Field Goal Mechanics

### Current Implementation (Lines 2234-2296)
**Status:** ✅ **GOOD** - Recently improved with pressure modifier

**Strengths:**
- Logistic probability curve based on distance
- Kicker skill affects success rate
- Pressure modifier integrated
- Confidence updates based on difficulty
- Tracks longest FG

**Minor Enhancement Opportunity:**
```python
# Could add weather/conditions modifier
# Could add clutch factor (end of game FGs)
# Could add "icing the kicker" mechanic (timeout before FG)
```

---

## 5. Code Quality Issues

### 5.1 MASSIVE CODE DUPLICATION in getGameData() and saveGameData()

**Lines 325-520 (getGameData) and Lines 524-719 (saveGameData)**
- These methods are **99% identical**
- ~200 lines duplicated with only minor differences
- Violates DRY principle
- Makes maintenance error-prone

**Current Pattern:**
```python
def getGameData(self):
    # 200 lines of stat processing
    return gameStatsDict

def saveGameData(self):
    # EXACT SAME 200 lines
    # Returns None instead of dict
    self.gameDict = gameStatsDict
```

**Recommendation:** Consolidate immediately

```python
def _buildGameStatsDict(self):
    """Internal method to build game stats dictionary"""
    # All the stat processing logic (single source of truth)
    return gameStatsDict

def getGameData(self):
    """Get current game state for API/display"""
    return self._buildGameStatsDict()

def saveGameData(self):
    """Save game state to gameDict"""
    self.gameDict = self._buildGameStatsDict()
```

**Impact:**
- Reduces code from ~440 lines → ~240 lines
- Eliminates risk of divergent implementations
- Makes future changes easier
- Improves maintainability

### 5.2 Down Text Conversion Duplicated
**Lines 500-509 and Lines 707-715**
```python
# Appears twice identically:
if self.down == 1:
    down = '1st'
elif self.down == 2:
    down = '2nd'
# etc...
```

**Recommendation:** Extract to helper method
```python
def _getDownText(self, downNumber: int) -> str:
    return {1: '1st', 2: '2nd', 3: '3rd', 4: '4th'}.get(downNumber, '1st')
```

### 5.3 Score Update Pattern Repeated ~40 Times
**Throughout Lines 1700-2200**

Every touchdown/FG/safety has this repeated 10+ times:
```python
if self.offensiveTeam == self.homeTeam:
    self.homeScore += points
    if self.currentQuarter == 1:
        self.homeScoreQ1 += points
    elif self.currentQuarter == 2:
        self.homeScoreQ2 += points
    # ... 5 more elif blocks
```

**Recommendation:** Extract to method
```python
def _addScore(self, team: FloosTeam.Team, points: int):
    """Add points to team's score and quarter-specific score"""
    if team == self.homeTeam:
        self.homeScore += points
        scoreAttr = f'homeScoreQ{self.currentQuarter}' if self.currentQuarter <= 4 else 'homeScoreOT'
    else:
        self.awayScore += points
        scoreAttr = f'awayScoreQ{self.currentQuarter}' if self.currentQuarter <= 4 else 'awayScoreOT'
    
    currentValue = getattr(self, scoreAttr)
    setattr(self, scoreAttr, currentValue + points)
```

**Impact:**
- Reduces ~400 lines of score updating → ~40 lines
- Single source of truth for score logic
- Easier to add new features (overtime periods, scoring rules)

---

## 6. Mental Attributes Usage Gaps

### Current State
**Passing plays:**
- ✅ Vision: Affects perceived receiver openness
- ✅ Discipline: Affects throwaway decisions
- ✅ Pressure handling: Affects performance under pressure

**Running plays:**
- ❌ Vision: NOT USED (should affect hole selection)
- ❌ Discipline: NOT USED (should affect patience/freelancing)
- ✅ Pressure handling: Applied to runner performance

**Field goals:**
- ❌ Vision: Not applicable
- ❌ Discipline: Could affect routine consistency
- ✅ Pressure handling: Applied to kicker

**Recommendation:** Extend mental attributes to running plays (detailed in section 1.1)

---

## 7. Potential New Features

### 7.1 Defensive Play Calling
**Currently:** Defense is passive (just rating numbers)
**Opportunity:** Add defensive play selection
- Blitz probability based on down/distance
- Coverage schemes (man vs zone) affecting receiver openness
- Run stuffing focus reducing run yards but weakening pass D

### 7.2 Game Script Awareness
**Currently:** Each play is mostly independent
**Opportunity:** Track game flow and adjust
- "What's working" tracker (recent success rates by play type)
- Defensive adjustments to offensive tendencies
- Offensive counter-adjustments

### 7.3 Weather/Conditions
**Currently:** Not implemented
**Opportunity:** Environmental factors
- Wind affecting pass distance and FG accuracy
- Rain affecting fumble rates and catching
- Dome vs outdoor stadium differences

### 7.4 Two-Minute Drill Logic
**Currently:** Basic end-game logic exists
**Opportunity:** More sophisticated clock management
- Timeout usage strategy
- Sideline awareness (stopping clock)
- Hurry-up offense mechanics

---

## 8. Performance Opportunities

### 8.1 Batch Random Number Generation
**Current:** Using batched_randint efficiently ✅
**Status:** Good - no changes needed

### 8.2 NumPy Usage
**Current:** Using numpy for probability distributions ✅
**Status:** Good - efficient implementation

---

## Priority Recommendations

### HIGH PRIORITY (Do Soon)
1. **Consolidate getGameData/saveGameData duplication** (Section 5.1)
   - Immediate code quality win
   - Low risk, high maintainability benefit
   - Estimated: 2-3 hours

2. **Extract score update logic** (Section 5.3)
   - Significant code reduction
   - Makes future scoring features easier
   - Estimated: 1-2 hours

### MEDIUM PRIORITY (Next Phase)
3. **Add RB vision/discipline to running plays** (Section 1.1)
   - Consistency with passing system
   - Makes RB mental attributes meaningful
   - Estimated: 4-6 hours (with testing)

4. **Improve play calling logic** (Section 3.1)
   - More realistic team identities
   - Better matchup exploitation
   - Estimated: 6-8 hours

### LOW PRIORITY (Future Enhancement)
5. **Add defensive play calling** (Section 7.1)
6. **Implement game script awareness** (Section 7.2)
7. **Add weather/conditions** (Section 7.3)

---

## Testing Recommendations

After implementing improvements:

1. **Create test_running_system.py** (similar to test_passing_system.py)
   - Test RB vision affecting hole selection
   - Test discipline affecting consistency vs variance
   - Compare different RB archetypes (power back, speedster, all-arounder)

2. **Create test_play_calling.py**
   - Validate tendency-based play selection
   - Ensure teams maintain identity across games
   - Test situational awareness (score, time, field position)

3. **Validate statistical realism**
   - Run 1000-game simulations
   - Check if run/pass ratios match expectations
   - Verify yardage distributions are realistic

---

## Conclusion

The passing system represents a **gold standard** for probability-based game mechanics. The main opportunities are:

1. **Code quality:** Eliminate duplication (HIGH impact, LOW risk)
2. **Consistency:** Apply mental attributes to running plays (MEDIUM impact, MEDIUM effort)
3. **Intelligence:** Improve play calling AI (HIGH impact, MEDIUM-HIGH effort)
4. **Features:** Add defensive play calling and game script awareness (MEDIUM impact, HIGH effort)

The codebase is in good shape overall. The passing improvements set a clear direction for other systems. Focus on code quality wins first, then extend the probability-based approach to running plays and play calling.
