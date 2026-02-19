# Coaching System Design Plan

## Overview
Major enhancement to play calling intelligence by adding coaches with attributes, game planning, and in-game adaptation.

## Coach Architecture

### Coach Attributes (0-100 scale)
- **Offensive Mind**: Ability to evaluate offensive matchups and create effective game plans
- **Defensive Mind**: Ability to evaluate defensive matchups and scheme against opponents
- **Adaptability**: Speed of adjusting to what's working/not working in-game
- **Aggressiveness**: Risk tolerance (4th down decisions, deep shots, blitzes)
- **Clock Management**: Late-game situational awareness
- **Player Development**: Affects player progression (long-term impact)

### Coach Tendencies (Personality Traits)
- Run/pass balance preference
- Gap distribution preference (power vs finesse running)
- Risk tolerance (conservative vs aggressive)
- Defensive scheme preference (man vs zone coverage, blitz frequency)

### Coach Lifecycle
- Teams hire/fire coaches
- Coaches retire after some seasons
- New coaches generated with random attributes/tendencies

## Gameplan System

### Gameplan Structure
```python
class Gameplan:
    # Offensive strategy
    runPassRatio: float  # 0.0-1.0
    gapDistribution: dict  # {'A-gap': 0.4, 'B-gap': 0.35, 'C-gap': 0.25}
    passDepthDistribution: dict  # {'short': 0.5, 'medium': 0.35, 'long': 0.15}
    
    # Situational tendencies
    thirdDownAggression: float
    redZoneStrategy: str  # 'power', 'balanced', 'finesse'
    goalLineGapPreference: str
    
    # Defensive strategy
    blitzFrequency: float
    coverageStyle: str  # 'man', 'zone', 'mixed'
```

### Pre-Game Gameplan Generation
1. Coach evaluates own team strengths (Offensive Mind attribute affects accuracy)
2. Coach scouts opponent weaknesses (higher attribute = better reads)
3. Generates distributions that exploit matchups
4. **Example**: Elite RB power + poor opponent run defense = 65% run, 50% A-gap calls

**Gap Distribution Logic**:
- Evaluate RB archetype (power vs speed vs balanced)
- Evaluate opponent run defense strength
- Coach's Offensive Mind determines accuracy of evaluation
- Generate weighted gap distribution:
  - Power back vs weak run D → More A-gap calls
  - Speed back vs weak coverage → More C-gap/bounce calls
  - Balanced approach → Even B-gap distribution

### In-Game Adaptation
```python
# Track what's working
runningSuccess: float  # YPC vs expected
passingSuccess: float  # Completion % vs expected
gapSuccessRates: dict  # {'A-gap': 4.2 YPC, 'B-gap': 2.1 YPC, ...}

# Adjust every quarter based on Adaptability
if runningSuccess < 0.8:  # 20% below expected
    adjustment = coachAdaptability / 100
    gameplan.runPassRatio -= 0.1 * adjustment

# Gap distribution adjustment
if gapSuccessRates['A-gap'] > 5.0 and gapSuccessRates['B-gap'] < 2.0:
    # Shift more weight to successful gaps
    gameplan.gapDistribution['A-gap'] += 0.1 * adaptability
    gameplan.gapDistribution['B-gap'] -= 0.1 * adaptability
```

**Game Script Awareness**:
- Winning by 14+ in 4th quarter → More conservative, run-heavy
- Losing by 10+ in 4th quarter → More aggressive, pass-heavy
- Close game → Stick to gameplan strengths

## Implementation Phases

### Phase 1: Coach Entity
**Files**: Create `floosball_coach.py`
- Create Coach class with attributes
- Name generation
- Coach rating calculation (overall)
- Hire/fire logic
- Retirement system (age-based)

**Files Modified**:
- `floosball_team.py` - Add coach reference
- `managers/teamManager.py` - Coach management methods
- Data JSON - Store coach data

### Phase 2: Basic Gameplan & Gap Distribution
**Files**: Create `gameplan.py`
- Create Gameplan class
- Pre-game gap distribution generation
- Simple strength/weakness evaluation
- Use coach attributes to affect accuracy

**Files Modified**:
- `floosball_game.py`:
  - Generate gameplan in `__init__`
  - Update `playCaller()` to use gameplan gap distribution
  - Update `runPlay()` to receive designated gap from play caller
  - Add `designatedGap` property to Play class

**Strategic Gap Selection Examples**:
- 3rd & short → More A-gap (power)
- 3rd & long → More C-gap (stretch play, force pursuit)
- Goal line → A-gap preference
- Open field → B-gap/C-gap distribution
- RB archetype affects distribution

### Phase 3: Advanced Scouting
- Coach evaluates RB archetype (power vs speed)
- Coach identifies opponent run defense rating
- Gameplan adjusts gap distribution accordingly
- Pass depth distribution based on QB/WR vs coverage
- Accuracy of evaluation scales with coach attributes

### Phase 4: In-Game Adaptation
- Track play success rates by type/gap
- Quarterly gameplan adjustments
- Game script awareness (winning/losing affects risk)
- Adaptability attribute determines adjustment speed
- Conservative vs aggressive coaching styles

### Phase 5: Defensive Coaching
- Defensive gameplan generation
- Blitz frequency decisions
- Coverage scheme selection (man vs zone)
- Defensive adjustments to offensive tendencies
- Counter-strategy based on what offense is doing

## Files Affected Summary

### New Files
- `floosball_coach.py` - Coach class and attributes
- `gameplan.py` - Gameplan generation and adaptation logic

### Modified Files
- `floosball_team.py` - Add coach reference, hire/fire methods
- `floosball_game.py` - Generate gameplans, use in playCaller()
- `managers/teamManager.py` - Coach hiring/firing/retirement
- Data JSON files - Store coach data

## Integration with Current Running System

The new gap distribution system will enhance the running mechanics:
- Currently: Random gap designation in `runPlay()`
- After Phase 2: Strategic gap calls from `playCaller()` based on gameplan
- Gap quality calculation remains unchanged
- RB vision/discipline mechanics remain unchanged
- Just changes **which gap is designated**, not how gaps work

## Benefits

1. **More realistic play calling** - Coaches attack weaknesses
2. **Strategic depth** - Different coaching styles create variety
3. **In-game drama** - Watch coaches adjust and counter-adjust
4. **Team identity** - Power running teams vs finesse teams
5. **Long-term strategy** - Hiring right coach for your personnel

## Next Steps

1. Complete other planned changes first
2. Return to implement Phase 1 & 2 for immediate value
3. Iterate on phases 3-5 based on testing and feedback
