# Floosball Backend

Football simulation engine with FastAPI REST/WebSocket API, SQLAlchemy ORM, and SQLite storage.

## Quick Start
```bash
python run_api.py --fresh --timing=fast        # Fresh DB, instant sim
python run_api.py --timing=fast-catchup --fresh # Fresh, backdate to last Monday, catch up instantly then go scheduled
python run_api.py                               # Resume existing season (default: scheduled)
```
Frontend repo is at `../floosball-react/` — `npm start` on port 3000, connects to backend on port 8000.

## Coding Conventions
- Python methods/functions/variables: **camelCase** (not snake_case). No exceptions for locals.
- SQLAlchemy column names: snake_case (DB convention)
- Class names: PascalCase. Constants: UPPER_SNAKE_CASE. Private methods: `_prefix`
- No emojis in UI — use SVG icons instead

## Naming Philosophy
Ridiculously formal/pompous tone. Timeless vocabulary, no trendy internet slang. One-word names preferred. Should sound good with suffixes (e.g., "-Pack"). Examples: Humble / Proper / Grand / Exquisite.

## Architecture

```
run_api.py                        # Entry point — starts FastAPI + background sim
api/
  main.py                         # All REST + WebSocket endpoints (60+)
  auth.py                         # Clerk auth, username generation, starter packs
  event_models.py                 # WebSocket event factories
  game_broadcaster.py             # Broadcasts events to WS clients
  websocket_manager.py            # WS connection management
managers/
  floosballApplication.py         # Main coordinator, owns all managers
  seasonManager.py                # Season loop, scheduling, week progression, playoffs, offseason
  timingManager.py                # Timing modes (SCHEDULED, FAST, CATCHUP, etc.)
  playerManager.py                # Player generation, contracts, free agency, stats
  teamManager.py                  # Team rosters, ratings, ELO
  leagueManager.py                # League structure, divisions
  recordManager.py                # Historical records
  cardManager.py                  # Card templates, packs, collection operations
  cardEffects.py / cardEffectCalculator.py  # Card effect logic during games
  fantasyTracker.py               # Fantasy scoring during live games
  gmManager.py                    # GM voting system (hire/fire/sign/cut)
  emailManager.py                 # Transactional emails (SES)
database/
  models.py                       # All SQLAlchemy models (~45 classes)
  connection.py                   # DB init, clear_db(), seeding
  repositories/                   # Repository pattern for DB access
    card_repositories.py, game_repository.py, gm_repository.py,
    notification_repository.py, pickem_repository.py, shop_repository.py
floosball_game.py                 # Core game simulation engine (3400+ lines)
floosball_player.py               # Player class and position attributes
floosball_team.py                 # Team class, roster management
floosball_coach.py                # Coach class
avatar_generator.py               # SVG team avatar generation + disk caching
```

## Key Systems

### Timing Modes (`timingManager.py`)
| Mode | Behavior |
|------|----------|
| `scheduled` | Production — games at real-time schedule, polls until start |
| `fast` | No delays, instant sim |
| `fast-catchup` | Backdate to last Monday, instant catch-up, then switch to scheduled |
| `catchup` | Like fast-catchup but with play-by-play delays during catch-up |
| `sequential` | Games with in-game delays but no real-time scheduling |
| `turbo` | Short pauses between games/weeks, no in-game delays |
| `demo` | Fast but with visible offseason pick delays |
| `test-scheduled` | Compressed scheduled (minutes apart, fast polling) |

### Season Structure
- 28 regular season weeks across 4 game days (7 rounds/day), anchored to season start date
- Games start on the hour; week rollover happens 15 min before game time
- Schedule: Mon-Wed game days, Thu off, then playoffs
- Playoffs: Wild Card → Divisional → Conference → Floosbowl
- Offseason: Free agency draft with visible pick broadcasting

### Game Simulation (`floosball_game.py`)
- `playGame()` — main game loop
- `playCaller()` → `_computePlayWeights()` → `_executeWeightedPlay()`
- Clock management: kneel, spike, timeout logic
- Win probability: logistic regression with time-scaled sensitivity and ELO

### Card System
- Cards have effects that modify game outcomes (stat boosts, special triggers)
- Rarity tiers: Common → Uncommon → Rare → Epic → Legendary
- Operations: open packs, sell, promote (upgrade rarity), blend, transplant effects
- Cards are equipped per-week and locked when games start

### Fantasy System
- Users draft rosters of sim players
- Weekly scoring based on player performance
- Weekly modifiers change scoring emphasis
- Leaderboards: season-long and per-week

### Pick-Em System
- Users predict game winners each week
- Points awarded for correct picks
- Leaderboard tracking

### GM / Front Office
- Users vote on team decisions: hire/fire coaches, sign/cut players
- Vote budget system limits influence
- FA ballots for free agency priority

### User Economy
- Currency: Floobits
- Earned from: fantasy performance, pick-em, weekly rewards
- Spent on: card packs, shop cards, powerups

## WebSocket Events
Primary channel: `/ws/season` — all game + season events flow here.

Key events:
- `game_state` — comprehensive per-play update (primary game event)
- `week_start` / `week_end` — week lifecycle
- `game_start` / `game_end` — game lifecycle
- `season_start` / `season_end` — season lifecycle
- Legacy: `play_complete`, `score_update`, `game_state_update` (still emitted)

## Database
- SQLite at `data/floosball.db`
- Alembic migrations in `alembic/versions/` (28 migrations)
- `clear_db()` preserves `users` and `beta_allowlist` tables on fresh start
- After fresh start, existing users get re-provisioned starter packs in `seasonManager.startNewSeason()`

## Deployment (Fly.io)
```bash
fly deploy                                    # Normal deploy (resumes season)
fly ssh console -C "touch /data/.fresh" && fly deploy  # Fresh start
```
- `TIMING_MODE` in `fly.toml` [env] — normally `scheduled`, use `fast-catchup` to recover missed games
- Fresh start uses one-shot flag file `/data/.fresh` (auto-deletes)
- Never use `FRESH_START` env var in prod — survives restarts

## Git Workflow
- `feature/*` → `development` → `main`
- Always merge (no rebase) into development and main
- Tags: `vX.Y.Z` on both repos
- Backend feature branch: `feature/card-game`
- Frontend feature branch: `feature/typescript-websocket-refactor`

## Files Not to Touch
- `legacy/` folder (reference only)
- `.vscode/launch.json` (unless necessary)
