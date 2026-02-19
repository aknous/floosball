# Simulation Resume Feature

## Overview
The Floosball simulation now supports automatic resumption after interruptions. If the application restarts while a simulation is running, it will detect the saved state and resume from the last completed week.

## How It Works

### State Tracking
The system tracks simulation progress in the `simulation_state` database table with the following information:
- **current_season**: Which season is being simulated
- **current_week**: Last completed week in the regular season
- **in_playoffs**: Whether we're in the playoff phase
- **playoff_round**: Which playoff round if applicable  
- **total_seasons**: Total number of seasons to simulate
- **is_active**: Whether a simulation is currently running
- **last_saved**: Timestamp of the last state save

### Automatic Saving
State is automatically saved after:
- Each week of regular season games completes
- Each playoff round completes
- Each full season completes
- Simulation starts and ends

### Resume Behavior
When you start the simulation:

1. **Fresh Start** (`--fresh` flag):
   - Clears all data including simulation state
   - Starts from Season 1

2. **Normal Start** (no flag):
   - Checks for existing simulation state
   - If state is marked as `active`:
     - Resumes from the last completed season
     - Restarts the current week (in-progress games are lost)
   - If no active state or state is complete:
     - Starts new simulation

### Week-Level Granularity
If the application crashes mid-week:
- The week's games in progress are lost
- When resumed, that week will be re-simulated from the beginning
- All previous weeks and seasons remain intact

## Usage Examples

### Check Current State
```bash
python3 test_resume.py show
```

Output:
```
Simulation State:
  Season: 5
  Week: 14
  In Playoffs: False
  Playoff Round: None
  Total Seasons: 20
  Active: True
  Last Saved: 2026-02-12 15:30:45
```

### Start/Resume Simulation
```bash
# Normal start - will resume if interrupted
python3 floosball.py --refactored --timing=fast

# Fresh start - clears everything
python3 floosball.py --refactored --timing=fast --fresh
```

### Clear State (if needed)
```bash
python3 test_resume.py clear
```

## Database Schema

The `simulation_state` table structure:
```sql
CREATE TABLE simulation_state (
    id INTEGER PRIMARY KEY DEFAULT 1,
    current_season INTEGER DEFAULT 0,
    current_week INTEGER DEFAULT 0,
    in_playoffs BOOLEAN DEFAULT 0,
    playoff_round VARCHAR(50),
    total_seasons INTEGER DEFAULT 20,
    is_active BOOLEAN DEFAULT 0,
    last_saved DATETIME,
    created_at DATETIME
)
```

## Production Deployment

For production environments where the machine might restart:

1. **Automatic Restart**: Configure your process manager (systemd, supervisor, etc.) to automatically restart the Python process if it crashes

2. **Monitoring**: Check `simulation_state.is_active` to see if a simulation is running

3. **Graceful Shutdown**: The state is saved after each week, so even ungraceful shutdowns only lose one week of games

4. **Recovery**: Simply restart the application - it will automatically detect and resume from the saved state

## Technical Details

### State Save Points
- **After each week**: Season X, Week Y completed
- **After regular season**: Before playoffs start
- **After playoffs**: Season complete, before offseason
- **After offseason**: Moving to next season

### Implementation Files
- `database/models.py`: `SimulationState` model definition  
- `managers/floosballApplication.py`: State loading, saving, and resume logic
- `managers/seasonManager.py`: State update callbacks after each week
- `test_resume.py`: Utility script for inspecting/managing state

### Callback Flow
```
SeasonManager completes week
    ↓
Calls _onWeekComplete()
    ↓
Triggers stateUpdateCallback
    ↓
FloosballApplication._onSeasonStateUpdate()
    ↓
Saves to database via _saveSimulationState()
```

## Limitations

1. **Week Granularity**: Mid-week interruptions require re-simulating that week's games
2. **Database Locking**: Uses retry logic (3 attempts with exponential backoff) to handle concurrent database access
3. **Single Simulation**: Designed for one simulation at a time (uses id=1 for state)

## Future Enhancements

Potential improvements:
- Game-level resumption (save after each game instead of each week)
- Multiple concurrent simulations (different state IDs)
- State snapshots/checkpoints for rolling back
- Progress percentage tracking
- Estimated time remaining calculations
