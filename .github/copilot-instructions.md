# Floosball - Copilot Instructions

## Project Overview
Floosball is a football simulation game with detailed play-by-play mechanics, player stats tracking, ELO ratings, and season management. The project is undergoing migration from a monolithic JSON-based architecture to a clean manager-based system with SQLite database storage.

**Version**: 0.9.0_alpha  
**Language**: Python 3.9+  
**Database**: SQLite (via SQLAlchemy)  
**Entry Point**: `run_api.py --timing=fast`

## Architecture

### Manager-Based System
The refactored architecture uses specialized managers coordinated through a service container:

```
floosball.py
├── managers/
│   ├── floosballApplication.py    # Main application coordinator
│   ├── seasonManager.py            # Season simulation, scheduling
│   ├── leagueManager.py            # League structure, divisions
│   ├── teamManager.py              # Team rosters, ratings, ELO
│   ├── playerManager.py            # Player generation, contracts, stats
│   ├── recordManager.py            # Historical records tracking
│   └── timingManager.py            # Game pacing control
├── floosball_game.py               # Core game simulation engine
├── floosball_player.py             # Player class, attributes, stats
├── floosball_team.py               # Team class, rosters
├── database/
│   ├── models.py                   # SQLAlchemy ORM models
│   ├── connection.py               # Database initialization
│   └── repositories/               # Data access layer
└── service_container.py            # Dependency injection
```

### Key Design Patterns
- **Service Container**: Central dependency injection (`service_container.py`)
- **Repository Pattern**: Database access abstracted in `database/repositories/`
- **Manager Pattern**: Business logic separated by domain
- **Legacy Compatibility**: Old JSON system in `legacy/` folder for reference

## Core Systems

### 1. Game Simulation (`floosball_game.py`)
The heart of the simulation - executes play-by-play football games.

**Key Classes**:
- `Game`: Main game controller, manages quarters, possession, scoring
- `Play`: Individual play execution (run, pass, FG, punt)

**Important Methods**:
- `playGame()`: Main game loop (lines ~1505-1900)
- `playCaller()`: Determines play type based on situation (lines ~750-1200)
- `runPlay()`: Execute rushing plays (lines ~2650-2750)
- `passPlay()`: Execute passing plays (lines ~3025-3200)
- `calculateWinProbability()`: Real-time win probability using ELO + game state (lines ~2328-2420)

**Recent Gameplay Balance Changes** (Feb 2026):
- **Sack rates reduced**: 9.4 → 1.49 per team (base 2%, max 15%, blocking ×12)
- **Offensive production boosted**: Run divisor 3.5→2.5, pass yards +25-33%, YAC enhanced
- **Current balance**: 20.2 ppg, 5.39 ypp, 4.8% shutouts (NFL-realistic)
- **4th down logic**: Conservative punt logic, proper FG range checks, situational awareness

### 2. Win Probability System
**Status**: ✅ Active (Feb 18, 2026)  
**Method**: `calculateWinProbability()` in `floosball_game.py` (line ~2328)

**Factors**:
- ELO ratings (100% influence at kickoff → 20% at end of regulation)
- Score differential
- Field position → Expected points model
- Down & distance
- Time remaining (sensitivity increases 0.6x → 4.0x in final 2 min)

**Formula**: Logistic regression with time-scaled sensitivity
```python
elo_advantage = (home_elo - away_elo) / 25.0  # 25 ELO ≈ 1 point
adjusted_diff = score + expected_points + (elo_advantage * elo_influence)
win_prob = 100 / (1 + e^(-k * adjusted_diff))
```

**Updates**: Before every play, logged in verbose mode
**Demo**: Run `python3 demo_win_probability.py` to see scenarios

### 3. Player System (`floosball_player.py`)
**Key Classes**:
- `Player`: Base player with attributes, stats, contracts
- `PlayerQB`, `PlayerRB`, `PlayerWR`, etc.: Position-specific subclasses
- `PlayerAttributes`: Skill ratings (speed, accuracy, strength, etc.)

**Attributes by Position**:
- QB: accuracy, awareness, decisionMaking, armStrength, mobility
- RB: speed, agility, carrying, vision, power
- WR/TE: speed, hands, routeRunning, catching
- K: legStrength, accuracy

**Stats System**:
- `GameStats`: Optimized game statistics (passing, rushing, receiving)
- `reset_game_stats()`: Clears stats between games (syncs to stat_tracker)
- Stats tracked: yards, TDs, receptions, completions, sacks, etc.

### 4. Team System (`floosball_team.py`)
**Attributes**:
- `elo`: Rating for matchup predictions (starts ~1500)
- `offenseRating`, `defenseRating`: Calculated from player attributes
- `rosterDict`: Dict of players by position key ('qb', 'rb1', 'wr1', etc.)

**Rating Calculation**: Weighted average of player skills by position importance

### 5. Season Simulation (`managers/seasonManager.py`)
**Key Methods**:
- `createNewSeason()`: Initialize season schedule
- `_simulateGame()`: Run single game (with optional verbose logging)
- `simulateSeason()`: Execute full season with all games

**Verbose Logging**: First 10 games of season 1 create detailed play-by-play logs in `logs/play_by_play_season_X_game_Y_AWAY_at_HOME.txt`

### 6. Database Layer
**ORM Models** (`database/models.py`):
- `PlayerModel`: Player data, contracts, stats
- `TeamModel`: Team info, roster relationships
- `LeagueModel`: League structure
- `SeasonModel`: Season schedules, results

**Migration Status**:
- ✅ Player management
- ✅ Team management  
- ✅ League structure
- ✅ Season simulation
- ⚠️ Historical records (in progress)

**Connection**: SQLite at `data/floosball.db` (auto-created)

## File Organization

### Core Game Files
- `floosball_game.py`: Game simulation engine (3400+ lines)
- `floosball_player.py`: Player classes and attributes
- `floosball_team.py`: Team class and roster management
- `floosball_methods.py`: Utility functions (ELO, probability calculations)

### Manager Files (`managers/`)
All business logic separated by domain responsibility.

### Configuration
- `config.json`: Team names, league structure, game settings
- `config_manager.py`: Configuration loading utilities
- `constants.py`: Game constants (field length, pressure calculations, etc.)

### Data Storage
- `data/floosball.db`: SQLite database (primary storage)
- `data/playerData/`: Legacy JSON files (being phased out)
- `logs/`: Game logs, play-by-play output, simulation logs

### Analysis Scripts
- `analyze_season.py`: Parse game stats, compare to NFL benchmarks
- `analyze_upsets.py`: Favorite win rates by rating differential
- `analyze_team_ratings.py`: Team rating distributions
- `demo_win_probability.py`: Win probability scenarios demo

## Development Workflow

### Running Simulations
```bash
# Fresh simulation (clears database)
python run_api.py --fresh --timing=fast

# Continue existing season
python run_api.py --timing=fast
```

### Timing Modes
- `fast`: No delays (simulation only)
- `sequential`: Fixed delays between events
- `scheduled`: Real-time pacing

### Enabling Verbose Logging
Edit `managers/seasonManager.py` line ~285:
```python
verbose = (season_number == 1 and game_idx < 10)  # First 10 games of season 1
```

### Analyzing Results
```bash
python3 analyze_season.py        # Overall stats vs NFL
python3 analyze_upsets.py        # Competitive balance
python3 analyze_team_ratings.py  # Rating distribution
```

## Recent Major Changes

### February 18-19, 2026: Win Probability System
- Implemented comprehensive win probability calculator
- Integrates ELO ratings with time-decay (100% → 20%)
- Expected points model from field position
- Updates every play, logged with verbose mode
- Replaced simple pre-game ELO-only calculation

### February 18, 2026: Gameplay Balance Overhaul
- Reduced excessive sack rates (was 9.4/team, now 1.49/team)
- Boosted offensive production across run/pass/YAC
- Achieved NFL-realistic stats: 20.2 ppg, 5.39 ypp, 369 ypg
- Lowered shutout rate from 70% → 4.8%
- Fixed 4th down decision logic (safety zone, FG range checks)

### Earlier: Database Migration
- Migrated from JSON to SQLite/SQLAlchemy
- Implemented manager-based architecture
- Added service container for dependency injection
- Created repository pattern for data access

## Coding Conventions

### File Editing
- Use `multi_replace_string_in_file` for multiple independent edits
- Include 3-5 lines of context before/after changes
- Never use placeholder comments like "...existing code..."
- Use absolute file paths

### Python Style
- **ALWAYS use camelCase for methods, functions, variables, and parameters** (never snake_case)
- Class names: PascalCase (`PlayerManager`, `GameStats`)
- Methods/functions: camelCase (`calculateWinProbability`, `runPlay`, `gameStart`)
- Variables/parameters: camelCase (`gameId`, `homeTeam`, `playData`, `homeScore`)
- Constants: UPPER_SNAKE_CASE (`GAME_MAX_PLAYS`, `FIELD_LENGTH`)
- Private methods: leading underscore (`_simulateGame`)
- Dictionary keys (especially for WebSocket events): camelCase (`gameId`, `playNumber`, `isTouchdown`)
- **Exception**: Only use snake_case for SQLAlchemy column names and database-specific code

### Testing
- Manual validation preferred over unit tests currently
- Use analysis scripts to validate game balance
- Demo scripts for feature showcasing (`demo_win_probability.py`)

## Common Tasks

### Adjusting Game Balance
**Location**: `floosball_game.py`

Sack rates (line ~2796):
```python
baseSackRate = 2.0          # Base probability
blockingModifier * 12       # Blocking impact
max(0.5, min(15, probability))  # Clamp 0.5-15%
```

Offensive production (lines ~2700-2720, ~3000-3020):
```python
# Run plays
mean_stage1 = ((offense - defense) / 2.5) + 2.5

# Pass plays
PassType.short: {'mean': 6.0, 'stdDev': 2.5}
PassType.medium: {'mean': 14, 'stdDev': 4.0}
PassType.long: {'mean': 25, 'stdDev': 6}
```

### Modifying Win Probability
**Location**: `floosball_game.py` line ~2328

ELO conversion: `elo_diff / 25.0`  (25 ELO ≈ 1 point)
Time factors: 0.6x early → 4.0x final 2 min
Expected points: Field position bins (line ~2430)

### Adding New Stats
1. Update `PlayerAttributes` in `floosball_player.py`
2. Add to `GameStats` class for tracking
3. Update `database/models.py` if persisting
4. Modify stat tracking in relevant play methods

## Important Notes

### Do NOT
- Modify files in `legacy/` folder (reference only)
- Use old JSON loading/saving functions (use managers instead)
- Edit `.vscode/launch.json` unnecessarily
- Create documentation files unless specifically requested
- Use the old `startLeagueLegacy()` entry point

### DO
- Use manager classes for all business logic
- Access database through service container
- Run analysis scripts to validate game balance changes
- Check verbose logs for play-by-play debugging
- Test game balance with full season simulations

## Quick Reference

| Task | Location |
|------|----------|
| Game simulation logic | `floosball_game.py` |
| Win probability | `floosball_game.py` line ~2328 |
| Play-by-play execution | `floosball_game.py` lines 1700-1900 |
| 4th down decisions | `floosball_game.py` lines 750-1200 |
| Offensive calculations | `floosball_game.py` lines 2650-3200 |
| Season management | `managers/seasonManager.py` |
| Player generation | `managers/playerManager.py` |
| Team ratings/ELO | `managers/teamManager.py` |
| Database models | `database/models.py` |
| Service container | `service_container.py` |
| Configuration | `config.json`, `config_manager.py` |
| Game balance analysis | `analyze_*.py` scripts |

## Current Project Status

**Stable & Complete**:
- ✅ Game simulation engine
- ✅ Win probability system
- ✅ Player/team management
- ✅ Season simulation
- ✅ Database migration
- ✅ Game balance (NFL-realistic stats)

**In Progress**:
- 🔄 Historical records database migration
- 🔄 Advanced analytics

**Future Enhancements**:
- 🔮 Player development system
- 🔮 Draft mechanics
- 🔮 Coaching impacts
- 🔮 Weather effects

---

Last Updated: February 19, 2026
