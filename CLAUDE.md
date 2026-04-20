# Floosball Backend

Football simulation engine with FastAPI REST/WebSocket API, SQLAlchemy ORM, and SQLite storage.

## Quick Start
```bash
python run_api.py --fresh --timing=fast          # Fresh DB, instant sim
python run_api.py --timing=fast-catchup --fresh  # Fresh, backdate to last Monday, catch up instantly then go scheduled
python run_api.py                                # Resume existing season (default: scheduled)
```
Frontend repo is at `../floosball-react/` — `npm start` on port 3000, connects to backend on port 8000.

## Coding Conventions
- Python methods/functions/variables: **camelCase** (not snake_case). No exceptions for locals.
- SQLAlchemy column names: snake_case (DB convention)
- Class names: PascalCase. Constants: UPPER_SNAKE_CASE. Private methods: `_prefix`
- No emojis in UI — use SVG icons instead

## Naming Philosophy
Mix of formal, pop-culture, and humor. No trendy internet slang. One-word names preferred. Should sound good with suffixes (e.g. "-Pack"). Pack tiers use formal style: **Humble / Proper / Grand / Exquisite**. Card effects and achievement names can be playful (e.g. "Fat Cat", "Home Alone", "Sparkler", "Patron").

## Architecture

```
run_api.py                        # Entry point — starts FastAPI + background sim
api/
  main.py                         # REST + WebSocket endpoints (~100)
  auth.py                         # Clerk auth, username generation, starter packs
  event_models.py                 # WebSocket event factories (32 event types)
  game_broadcaster.py             # Broadcasts events; holds main_loop ref for sync-thread dispatch
  websocket_manager.py            # WS connection management + per-user targeting
managers/
  floosballApplication.py         # Main coordinator, owns all managers
  seasonManager.py                # Season loop, scheduling, week progression, playoffs, offseason
  timingManager.py                # Timing modes (SCHEDULED, FAST, CATCHUP, etc.)
  playerManager.py                # Player generation, contracts, free agency, stats
  teamManager.py                  # Team rosters, ratings, ELO
  leagueManager.py                # League structure, divisions
  recordManager.py                # Historical records
  cardManager.py                  # Card templates, packs, collection ops (supports skipCurrency=True for grants)
  cardEffects.py / cardEffectCalculator.py  # Card effect logic during games
  fantasyTracker.py               # Fantasy scoring during live games
  gmManager.py                    # GM voting system (hire/fire/sign/cut)
  achievementManager.py           # Achievement progress, grants, pending rewards, WS unlock events
  emailManager.py                 # Transactional emails (SES)
database/
  models.py                       # All SQLAlchemy models (46 classes)
  connection.py                   # DB init, seeds (pack types, beta allowlist, achievements), inline migrations
  repositories/                   # Repository pattern for DB access
    base_repositories.py, card_repositories.py, game_repository.py, gm_repository.py,
    notification_repository.py, pickem_repository.py, shop_repository.py
floosball_game.py                 # Core game simulation engine (3400+ lines)
floosball_player.py               # Player class + position attributes (two-way / defensive attrs)
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
| `turbo-silent` | Sequential delays between games/weeks, no broadcasting |
| `fast-weekly` | FAST games (no delays, no broadcast), 30s pause between weeks |
| `playoff-test` | Fast regular season + compressed scheduled playoffs |
| `offseason-test` | Fast regular season (no broadcast), interactive offseason |

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
- Defensive stats tracked alongside offensive (tackles, sacks, INTs)

### Card System
- **Editions** (rarity tiers stored in DB): `base` → `holographic` → `prismatic` → `diamond`
- **Pack types** (ordered cheapest → rarest): `humble` (50F), `proper` (150F), `grand` (350F), `exquisite` (750F)
- **Classifications** (optional on templates): `rookie`, `mvp`, `champion`, `all_pro`, or compound (e.g. `mvp_champion`)
- Operations: open packs, sell, promote (rarity upgrade), blend, transplant effects — all logged via `CardUpgradeLog`
- Cards are equipped per-week in slots 1–5, locked when games start
- **Slot 6** unlocks when user has an MVP-classified card equipped OR an active `temp_card_slot` powerup
- Free grants (achievements, starter packs): `cardManager.openPack(skipCurrency=True)`

### Fantasy System
- Users draft roster of 5 sim players (QB/RB/WR/TE/K), one each
- Weekly FP from player performance, banked via `WeeklyPlayerFP`
- Weekly modifiers shift scoring emphasis (`WeeklyModifier` + `UserModifierOverride`)
- Card effects applied at week-end (`WeeklyCardBonus`), can output FP, floobits, or multipliers
- Leaderboards: season-long and per-week
- Roster swaps tracked in `FantasyRosterSwap` with escalating costs

### Pick-Em System
- Users predict game winners each week
- Per-game locking — a pick can be changed until that specific game hits Final
- Points per pick = base × timing_multiplier × underdog_multiplier
- Timing multiplier decays by quarter (pre-game gets max, Q4 gets min)
- Underdog multiplier boosts underdog picks (by ELO delta) and penalizes obvious favorites
- Auto-pick opt-in via `users.auto_pick_favorites`: auto-picks tagged `pick_em_picks.is_auto=True`
- Clairvoyant bonus when weekly points exceed `PICKEM_CLAIRVOYANT_THRESHOLD`

### Achievements
- **Scope**: `once` (one-time milestones) or `per_season` (re-earnable each year)
- **Categories**: `onboarding` (Rookie Goals) or `guidance` (Season Goals, including tiered progressions like Banner Week I–IV, Dedicated I–VI)
- **Rewards**: floobits (immediate), packs/powerups (queued as `PendingReward`)
- **Deferral**: user can defer late-season pack claims via `defer_until_season` — blocks claim until target season arrives
- **Backfill**: `backfillOnboardingAchievements()` runs on first `/api/achievements` visit, retro-credits completed milestones
- **WS event**: `achievement_unlocked` sent per-user on unlock (uses `broadcaster.broadcast_to_user_sync`)
- **Seed refresh**: `_seedAchievements()` upserts templates on every startup (names/descriptions/targets/rewards update without wiping user progress)

### Powerups (`constants.POWERUP_CATALOG`)
Purchased from shop, tracked in `ShopPurchase` with `expires_at_week`:
- `extra_swap` — +1 roster swap (50F)
- `modifier_nullifier` — cards operate under Steady this week (60F)
- `temp_flex` — adds FLEX roster slot for 4 weeks (200F)
- `temp_card_slot` — adds 6th card slot for 4 weeks (200F)
- `fortunes_favor` — +10% chance-card trigger rate for 3 weeks (125F)
- `income_boost` — raises weekly FP cap to 65F for 4 weeks (100F)

### GM / Front Office
- Users vote on team decisions: hire/fire coaches, sign/cut players
- Vote budget system limits influence
- FA ballots for free agency priority

### Team Funding
- Users contribute floobits directly to their favorite team (`POST /api/teams/{id}/contribute`)
- Passive end-of-season auto-contribution driven by `users.team_funding_pct`
- `TeamFunding` tracks `baseline_funding`, `fan_contributions`, effective funding, tier, and tier rank
- Funding carries 50% into the next season with decay

### User Economy
- Currency: **Floobits** (F)
- Earned from: fantasy performance, pick-em, weekly rewards, achievements, card effects
- Spent on: card packs, shop cards, powerups, team contributions
- All grants/spends logged in `CurrencyTransaction` (includes `season`/`week` for analytics)

### Discord Integration
- Users link with `/link <username>` (short-lived code flow) → stored in `users.discord_id`
- Opt-in DM reminders via `users.discord_dm_reminders`
- Bot endpoints: `/api/bot/link`, `/api/bot/unsubmitted`, `/api/bot/cards`, `/api/bot/roster`

## WebSocket Events
Primary channel: `/ws/season` — all game + season events flow here. Per-user events use `send_to_user()` against sockets that sent `{type:"identify", userId}`.

**Event categories** (32 total in `EventType`):
- **Game**: `game_start`, `game_end`, `game_state` (primary per-play), legacy `play_complete`/`score_update`/`game_state_update`
- **Week**: `week_start`, `week_end`, `day_complete`, `regular_season_complete`
- **Season**: `season_start`, `season_end`
- **Standings / Fantasy**: `standings_update`, `leaderboard_update`
- **News / Awards**: `league_news`, `mvp_announcement`, `all_pro_announcement`
- **Pick-Em**: `pickem_results`
- **Offseason**: `offseason_start`, `offseason_pick`, `offseason_cut`, `offseason_on_clock`, `offseason_team_complete`, `offseason_complete`
- **GM**: `gm_vote_resolved`, `gm_fa_window_open`, `gm_fa_window_close`, `gm_fa_directives`
- **Achievements**: `achievement_unlocked` (per-user)
- **System**: `error`, `info`

## REST API
~100 endpoints in `api/main.py`. Rough groups:
- `/api/teams`, `/api/players`, `/api/games`, `/api/standings`, `/api/power-rankings`, `/api/playoffs`, `/api/champion`, `/api/highlights`, `/api/season`, `/api/schedule`
- `/api/fantasy/roster`, `/api/fantasy/roster/lock`
- `/api/cards/equipped`, `/api/cards/blend/preview`
- `/api/packs/types`, `/api/packs/open`
- `/api/shop/featured`, `/api/shop/buy-card`, `/api/shop/reroll*`, `/api/shop/powerups*`
- `/api/pickem/week`, `/api/pickem/pick`, `/api/pickem/leaderboard`, `/api/pickem/history`
- `/api/gm/vote`, `/api/gm/team/{id}/...`, `/api/gm/fa-*`, `/api/gm/votes`, `/api/gm/results`
- `/api/achievements`, `/api/achievements/pending-rewards`, `/api/achievements/claim-reward/{id}`, `/api/achievements/reward/{id}/defer`
- `/api/bot/*` (Discord)
- `/api/users/me`, `/api/currency/balance`, `/api/teams/{id}/contribute`, `/api/teams/{id}/projected-funding`
- `/api/admin/*` (gated by `users.is_admin`)

## Database
- SQLite at `data/floosball.db`
- 46 models in `models.py`
- **Alembic migrations** in `alembic/versions/` (37 files) — canonical history
- **Inline migrations** in `connection.py::_runPendingMigrations()` — idempotent `ALTER TABLE ADD COLUMN` for columns added after initial deploy (survives prod redeploys without alembic upgrade)
- Seed functions: `_seedPackTypes`, `_seedBetaAllowlist`, `_seedAchievements` (refresh-on-startup)
- `clear_db()` preserves `users` and `beta_allowlist` tables on fresh start
- After fresh start, existing users get re-provisioned starter packs in `seasonManager.startNewSeason()`

## Deployment (Fly.io)
```bash
fly deploy                                                 # Normal deploy (resumes season)
fly ssh console -C "touch /data/.fresh" && fly deploy      # Fresh start
```
- `TIMING_MODE` in `fly.toml` [env] — normally `scheduled`, use `fast-catchup` to recover missed games
- Fresh start uses one-shot flag file `/data/.fresh` (auto-deletes on boot)
- Never use `FRESH_START` env var in prod — survives restarts and would wipe DB on outage recovery

## Git Workflow
Three-tier branch strategy with seasonal cadence:

```
main              ← production (Fly.io)
└── development   ← staging / integration
     ├── hotfix/*      → merge to dev → main immediately (in-season fixes)
     ├── next-season   → merge to dev when season ends (between-season changes)
     └── feature/*     → long-term features, merge when ready
```

- Always merge (no rebase) into development and main
- Tags: `vX.Y.Z` on both repos
- Current feature branch: `feature/achievements`

## Files Not to Touch
- `legacy/` folder (reference only)
- `.vscode/launch.json` (unless necessary)
