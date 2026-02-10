# Game Clock System Design

## Overview
Implement realistic game clock mechanics without slowing down actual game simulation time. Clock is **logical** (instant time consumption) while timingManager handles real-world display pacing.

## Core Principles

1. **Game clock is instant** - Each play immediately consumes game time (no waiting)
2. **TimingManager is separate** - Still controls real-world delays for streaming/display
3. **Realistic mechanics** - Proper clock stop/run rules, timeouts, two-minute warning
4. **Situational awareness** - Teams adjust pace based on score/time

## Clock Structure

### Game State
```python
class Game:
    # Time tracking
    gameClockSeconds: int  # Seconds remaining in current quarter (900 to 0)
    currentQuarter: int    # 1-4 (5 for OT)
    
    # Timeouts
    homeTimeoutsRemaining: int  # 3 per half
    awayTimeoutsRemaining: int  # 3 per half
    
    # Game flow
    twoMinuteWarning: bool  # Triggered once per half
    clockRunning: bool      # Is clock currently running?
```

### Quarter Time
- Q1-Q4: 900 seconds (15 minutes) each
- Overtime: 600 seconds (10 minutes) - sudden death
- Halftime: Reset timeouts to 3 per team

## Time Consumption Per Play

### Pre-Snap Time (Huddle to Snap)
Time consumed **before** play execution:

```python
def calculatePreSnapTime():
    baseTime = 35  # Default huddle/snap time
    
    # Situation modifiers
    if trailingByMore(8) and quarterTime < 300:  # Losing, under 5 min
        baseTime = 15  # Hurry-up offense
    elif leadingByMore(8) and quarterTime < 300:  # Winning, under 5 min
        baseTime = 40  # Burn clock
    elif quarterTime < 120:  # Under 2 minutes
        if trailing:
            baseTime = 12  # Fast tempo
        else:
            baseTime = 38  # Milk clock
    
    # Add small variance
    return baseTime + randint(-3, 3)
```

**Spike Play**: Special case consuming only 3 seconds (stop clock, lose down)

### Play Duration (Snap to Whistle)
Time consumed **during** play execution:

```python
def calculatePlayDuration(playType, outcome):
    if playType == Run:
        if inBounds:
            return randint(4, 6)  # Clock runs
        else:
            return randint(3, 5)  # Out of bounds stops clock
    
    elif playType == Pass:
        if isCompletion and inBounds:
            return randint(3, 6)  # Completion in bounds, clock runs
        elif isCompletion and outOfBounds:
            return randint(3, 5)  # Out of bounds stops clock
        elif isSack:
            return randint(3, 5)  # Sack, clock runs
        else:  # Incomplete
            return randint(2, 3)  # Incomplete stops clock
    
    elif playType == FieldGoal or playType == Punt:
        return 5  # Special teams, clock stops
```

## Clock Stop/Run Rules

### Clock STOPS After
- Incomplete pass
- Out of bounds (ball carrier goes out)
- Timeout called
- Score (TD, FG, safety)
- Turnover (until ball is set)
- End of quarter
- Two-minute warning (once per half)
- Change of possession
- Penalty (simplified - just stop briefly)

### Clock RUNS After
- Complete pass in bounds
- Run in bounds
- Sack
- Quarterback kneel

### Special Rule: First Down
- Clock stops briefly to set ball (~2 seconds)
- Then resumes if it was running

## Timeout System

### Timeout Usage
```python
def callTimeout(team):
    if team.timeoutsRemaining > 0:
        team.timeoutsRemaining -= 1
        clockRunning = False
        # Consume 30 seconds for timeout duration
        # (Team huddles, discusses strategy)
```

### Timeout Strategy (AI Decisions)
Teams automatically call timeout when:
1. **Preserve time** - Trailing late, clock running, no timeouts used
2. **Prevent delay of game** - Close to play clock expiration (rare)
3. **Ice the kicker** - Opponent attempting FG in final 2 minutes (defensive timeout)

```python
def shouldCallTimeout():
    if timeoutsRemaining == 0:
        return False
    
    # Preserve clock when trailing late
    if trailing and quarterTime < 120 and clockRunning:
        if yardLineValue < 30:  # Not in great field position
            return True
    
    # Save timeouts for final drive
    if timeoutsRemaining >= 2 and quarterTime < 30:
        return True  # Aggressive time management
    
    return False
```

## Two-Minute Warning

```python
def checkTwoMinuteWarning():
    if not twoMinuteWarning and quarterTime <= 120:
        if currentQuarter == 2 or currentQuarter == 4:
            twoMinuteWarning = True
            clockRunning = False
            # Automatic stoppage, like a timeout
            # Consume ~30 seconds for TV timeout simulation
```

## Out of Bounds Detection

Need to add out-of-bounds outcome to plays:

```python
def determineOutOfBounds(playType, yardage):
    if playType == Run:
        # Outside runs more likely to go OOB
        if selectedGap == 'C-gap' or selectedGap == 'bounce':
            oobChance = 25  # 25% for outside runs
        else:
            oobChance = 5   # 5% for inside runs
    
    elif playType == Pass:
        if passType == PassType.short:
            oobChance = 10
        elif passType == PassType.medium:
            oobChance = 20
        elif passType == PassType.long:
            oobChance = 30  # Sideline shots
    
    return randint(1, 100) <= oobChance
```

## Clock Management Flow

### Play Execution Flow
```python
async def executePlay():
    # 1. Pre-snap: Consume huddle time
    if clockRunning:
        preSnapTime = calculatePreSnapTime()
        gameClockSeconds -= preSnapTime
        checkForQuarterEnd()
    
    # 2. Execute play (existing logic)
    runPlay() or passPlay()
    
    # 3. Post-play: Consume play duration
    playDuration = calculatePlayDuration(playType, outcome)
    if clockRunning:
        gameClockSeconds -= playDuration
    
    # 4. Determine if clock stops
    clockRunning = shouldClockRun(playType, outcome)
    
    # 5. Check for automatic events
    checkTwoMinuteWarning()
    checkForQuarterEnd()
    
    # 6. AI timeout decision
    if shouldCallTimeout():
        callTimeout()
```

### Quarter Transitions
```python
def checkForQuarterEnd():
    if gameClockSeconds <= 0:
        if currentQuarter == 1:
            currentQuarter = 2
            gameClockSeconds = 900
        elif currentQuarter == 2:
            # Halftime
            currentQuarter = 3
            gameClockSeconds = 900
            resetTimeouts()  # Each team gets 3 new timeouts
            twoMinuteWarning = False
        elif currentQuarter == 3:
            currentQuarter = 4
            gameClockSeconds = 900
            twoMinuteWarning = False
        elif currentQuarter == 4:
            if homeScore == awayScore:
                # Overtime
                currentQuarter = 5
                gameClockSeconds = 600  # 10 min OT
            else:
                # Game over
                endGame()
```

## Spike Play Implementation

Special play to stop clock at cost of a down:

```python
def spikePlay():
    """
    QB spikes ball to stop clock
    - Costs a down
    - Consumes only 3 seconds
    - Stops clock
    - Only used when trailing late
    """
    playType = PlayType.Spike
    gameClockSeconds -= 3
    clockRunning = False
    down += 1  # Lose the down
    yardage = 0
```

**When to spike**: Offense automatically spikes if:
- Trailing or tied
- Under 2 minutes
- Just completed pass in bounds (clock running)
- Not on 4th down
- Plenty of time for next play (not final seconds)

## Kneel Play Implementation

```python
def kneelPlay():
    """
    QB kneels to run out clock
    - Consumes 40 seconds (max time)
    - Loses 1-2 yards
    - Clock keeps running
    - Only used when winning late
    """
    playType = PlayType.Kneel
    gameClockSeconds -= 40
    yardage = -randint(1, 2)
    clockRunning = True  # Clock never stops
```

**When to kneel**: Offense automatically kneels if:
- Leading by any amount
- Under 2 minutes in 4th quarter
- Opponent has 0 timeouts
- Can run out entire clock by kneeling each down

## Integration Points

### Files to Modify

**floosball_game.py** - Main game loop
- Add clock properties to `Game.__init__()`
- Add `calculatePreSnapTime()` method
- Add `calculatePlayDuration()` method
- Add `shouldClockRun()` method
- Add `callTimeout()` method
- Add `checkTwoMinuteWarning()` method
- Modify `playGame()` loop to use clock instead of play count
- Add clock consumption before/after each play

**Play class**
- Add `isOutOfBounds` property
- Add `determineOutOfBounds()` method
- Call it after yardage is calculated

**constants.py**
- Remove or deprecate `GAME_MAX_PLAYS`
- Add clock-related constants

**floosball_team.py**
- Add `timeoutsRemaining` property
- Add timeout management methods

### New Play Types
Add to enum:
```python
class PlayType(Enum):
    Run = 1
    Pass = 2
    FieldGoal = 3
    Punt = 4
    Spike = 5      # NEW
    Kneel = 6      # NEW
```

## Display/UI Changes

### Game Feed Updates
Need to show clock information:
```python
gameFeed.insert(0, {
    'play': self.play,
    'quarter': currentQuarter,
    'timeRemaining': formatTime(gameClockSeconds),  # "12:45"
    'clockRunning': clockRunning
})
```

### Format Time Helper
```python
def formatTime(seconds):
    minutes = seconds // 60
    secs = seconds % 60
    return f"{minutes}:{secs:02d}"
```

## Testing Strategy

### Test Scenarios
1. **Normal game flow** - Does clock run down properly?
2. **Trailing team hurry-up** - Do they go faster when behind?
3. **Leading team clock burn** - Do they slow down when ahead?
4. **Two-minute drill** - Proper timeout usage, spike plays
5. **Victory formation** - Kneel downs to end game
6. **Overtime** - Sudden death mechanics

### Validation Checks
- Average game: 120-140 plays (realistic)
- Final 2 minutes with timeouts: ~8-12 plays possible
- Team can't kneel if they're losing
- Timeouts reset at halftime
- Clock stops on incomplete passes

## Phased Implementation

### Phase 1: Basic Clock
- Add clock properties
- Time consumption on each play (fixed times)
- Simple stop/run rules
- Quarter transitions

### Phase 2: Situational Pace
- Hurry-up when trailing
- Clock burning when leading
- Variance in time consumption

### Phase 3: Timeouts & Two-Minute Warning
- Timeout system
- AI timeout decisions
- Two-minute warning
- Halftime timeout reset

### Phase 4: Advanced Plays
- Spike plays
- Kneel plays
- Out of bounds detection
- Strategic clock management

### Phase 5: Polish
- Better AI decision making
- Edge case handling
- End-of-half/game scenarios
- Display improvements

## Benefits

1. **Realistic game flow** - Games feel like real football
2. **Strategic depth** - Clock management matters
3. **Dramatic moments** - Two-minute drills, final drives
4. **Varied game lengths** - Fast-paced games vs grind-it-out games
5. **No performance impact** - Clock is instant, games still simulate quickly

## Next Steps

1. Implement Phase 1 (basic clock)
2. Test thoroughly
3. Iterate through phases 2-5
4. Integrate with coaching system later (coaches affect pace decisions)
