# Floosball Backend

Football simulation engine with a FastAPI REST/WebSocket API, SQLAlchemy ORM, and SQLite storage. A background task simulates an endless league (seasons → playoffs → offseason → next season); users play a fantasy/cards/pick-em/GM metagame on top of it.

> **Keep this file current.** This is the source of truth for the backend's architecture, systems, conventions, and key constants. Consult it before changing code, and when a change alters something documented here (a system's behavior, the data model, an endpoint group, a constant's meaning, a convention), update the matching section in the same change. If you find a claim here that's wrong or stale, fix it.

## Quick Start
```bash
python run_api.py --fresh --timing=fast          # Fresh DB, instant sim
python run_api.py --timing=fast-catchup --fresh  # Fresh, backdate to last Monday, catch up instantly then go scheduled
python run_api.py                                # Resume existing season (default: scheduled)
```
API docs at `http://localhost:8000/docs`. Frontend repo at `../floosball-react/` (`npm start` on :3000, talks to backend on :8000).

## Coding Conventions
- Python methods/functions/variables: **camelCase** (not snake_case). No exceptions for locals.
- SQLAlchemy column names: snake_case (DB convention).
- Class names: PascalCase. Constants: UPPER_SNAKE_CASE. Private methods: `_prefix`.
- No emojis in UI strings — use SVG icons instead.

## Naming Philosophy
Mix of formal, pop-culture, and humor. No trendy internet slang. One-word names preferred; should sound good with suffixes (e.g. "-Pack"). Pack tiers use formal style. Card effects and achievement names can be playful (e.g. "Fat Cat", "Home Alone", "Scorched Earth"). Test: would the name feel dated in 20 years? If yes, skip it.

## Architecture

```
run_api.py                        # Entry point — starts FastAPI + background sim, enables broadcaster
constants.py                      # Single source of truth for tunable values (balance, economy, cards, GM, fantasy, pickem)
game_rules.py                     # Clock/FG/quarter rules used by the game engine
service_container.py              # DI container (string-keyed services) + GameStateManager + ConfigurationManager
config.json                       # Team names, league structure, beta allowlist, secrets (local only; prod uses fly secrets)
config_manager.py                 # Config loader
api/
  main.py                         # All REST (~140) + 3 WebSocket endpoints
  auth.py                         # Clerk JWT auth, user provisioning, username gen, starter packs, beta gate
  event_models.py                 # WebSocket event factories (EventType enum + factory classes)
  game_broadcaster.py             # Broadcasts events; holds main_loop ref for sync-thread dispatch + per-user targeting
  websocket_manager.py            # WS connection management; channel + per-user routing
api_response_builders.py          # Response serialization helpers + the success/error envelope
managers/
  floosballApplication.py         # Coordinator: owns one shared DB session + the core managers; runs the season loop
  seasonManager.py                # Season loop, scheduling, week/day progression, playoffs, full offseason flow (~9k lines)
  timingManager.py                # 12 timing modes (delays, scheduling, broadcasting toggles)
  playerManager.py                # Player generation, contracts, free agency / FA draft, training, stats
  teamManager.py                  # Team rosters, ratings, ELO, coach hire/fire, coach candidates
  leagueManager.py                # League structure (2 leagues × 12 teams), divisions
  recordManager.py                # Historical records
  personalityManager.py           # Player personalities, quotes, moods (YAML-templated)
  personalityReactionEngine.py    # In-game personality reactions / sideline cutaways
  anomalyManager.py               # "Anomaly" system — player attention ladder + league-wide aggregate events
  rallyManager.py                 # Live in-game fan rallies (Floobit-charged confidence/determination nudges)
  cardManager.py                  # Card templates, packs, shop, collection ops (supports skipCurrency for grants)
  cardEffects.py                  # Per-effect compute functions + EFFECT_EDITION_TIER mapping
  cardEffectCalculator.py         # Two-pass effect calculator (first pass + second-pass cross-card effects)
  cardProjection.py               # Projected card payouts for the upcoming week
  fantasyTracker.py               # Live fantasy scoring, weekly FP banking, snapshots, card bonus
  gmManager.py                    # GM voting resolution (fire/hire/cut/resign + FA & rookie ranked ballots)
  achievementManager.py           # Achievement progress, grants, pending rewards, secret unlocks, WS toasts
  emailManager.py                 # Transactional emails via Resend (NOT SES)
database/
  models.py                       # All SQLAlchemy models (60 classes)
  connection.py                   # DB init, seeds, inline migrations, backfills, clear_db
  config.py                       # DB path config
  repositories/                   # Repository pattern (base, card, game, gm, notification, pickem, shop)
floosball_game.py                 # Core game simulation engine (~9,400 lines)
floosball_player.py               # Player class + position/defensive/mental attributes, tiers
floosball_team.py                 # Team class, rosterDict, ratings, ELO, pressure/streak state
floosball_coach.py                # Coach class (8 attributes)
rating_cache.py                   # Cached rating computation (note: QB uses a different weighting here)
avatar_generator.py               # SVG team/league avatar generation + disk caching
```

`floosballApplication` constructs and owns: **PlayerManager, TeamManager, LeagueManager, RecordManager, PersonalityManager, SeasonManager, FantasyTracker** (all sharing one DB session to avoid SQLite lock contention). `CardManager`, `GmManager`, `AchievementManager`, `EmailManager`, etc. are instantiated ad-hoc where needed (in `seasonManager` and the API layer), not owned by the application object.

## Key Systems

### Timing Modes (`timingManager.py`)
`TIMING_MODE` env / `--timing=` flag. 12 modes:

| Mode | In-game delays | Real-time scheduling | Broadcasting | Notes |
|------|----------------|----------------------|--------------|-------|
| `scheduled` | Yes | Yes | Yes | Production. Games at real-time schedule; polls until start. |
| `sequential` | Yes | No | Yes | Play-by-play delays, fixed week gaps, no wall-clock. |
| `turbo` | No | No | Yes | Short fixed pauses between games/weeks. |
| `fast` | No | No | Yes | No delays anywhere. Default for dev. |
| `demo` | No | No | Yes | Like fast, but visible offseason pick delays (5s). |
| `test-scheduled` | No | Yes (compressed) | No | Real polling, minutes apart, fast polls. |
| `offseason-test` | No | No | Offseason only | Fast silent regular season; interactive (compressed) offseason. `_isTestMode` (low GM quorum). |
| `catchup` | **Yes** | Yes (→scheduled once current) | Yes | Backdate to last Monday, catch up **with** play-by-play delays. |
| `fast-catchup` | **No** | Yes (→scheduled once current) | Yes | Backdate to last Monday, catch up **instantly**, then go scheduled. |
| `playoff-test` | No (reg) / polling (playoffs) | Playoffs only | Yes | Fast regular season + compressed scheduled playoffs. |
| `turbo-silent` | No | No | No | Sequential-ish week gaps, broadcasting off. |
| `fast-weekly` | No | No | Yes (game events suppressed) | Instant games, 30s between weeks, visible offseason. |

> `catchup` = delays during catch-up; `fast-catchup` = no delays during catch-up. (Earlier docs had these reversed.)

### Season Structure (`seasonManager.py`)
- **24 teams**, 2 leagues × 12. Regular season = `((12-1)×2) + (12/2)` = **28 weeks**.
- **4 game days** per "week index block" (days 0–3 from the season start anchor = Mon–Thu), 7 rounds per day, games on the hour 12:00–18:00 ET. Playoffs are day 4 (**Friday**); offseason drafts follow.
- Season start anchor: SCHEDULED → next Monday 04:00 ET; CATCHUP/FAST_CATCHUP → last Monday 04:00 ET.
- **Week rollover**: 15 min before game time for intra-day transitions; **8 hours early** (prior evening) for cross-day boundaries (week indices 8/15/22) so the next slate is visible the night before.

### Playoffs
- Top half of each league qualify (6/league = **12 teams**); top 2 per league get a **round-1 bye**.
- **Re-seeds every round** by (winPerc, scoreDiff) — highest plays lowest. Not a fixed bracket.
- 4 rounds, named `Playoffs Round 1` (wk 29) → `Playoffs Round 2` (wk 30) → `League Championship` (wk 31) → `Floos Bowl` (wk 32). Rounds 1–3 are within-league; the Floos Bowl is the cross-league final.

### Offseason Flow (`seasonManager._handleOffseason`)
Phased, resumable (each phase gated by a completion marker in `simulation_state.offseason_completed_steps`). `_offseasonFlowPhase` values: `post_bowl → frontoffice → rookie_draft → pre_fa → fa_draft → training → None`.

Front-office decision steps (one `frontoffice_decisions` gate): **1** increment FA years → **2** resolve fire→hire coach votes (coach always backfilled) → **2.5** coach increments/retirements → **3** contract decrements + retirements → **3.5** resolve cut votes (release to FA pool) → **3.6** award "Scorched Earth" achievement. Then: rookie draft (live picks), FA draft (`_processFreeAgency`), training/HOF/finalize.
- **Position-supply floor** (`playerManager.ensurePositionSupply`, wrapper `seasonManager._ensurePositionSupply`): guarantees enough living players at EACH position to fill every roster slot (numTeams × {QB1,RB1,WR2,TE1,K1} + `ROSTER_SUPPLY_BUFFER_PER_POSITION`), generating only the per-position deficit into the FA pool. Runs twice: at **week `GM_ACTIVE_WEEK`** (right after retirements are flagged — the rookie class already exists from season start — so topped-up FAs are in the ballot pool) and again **just before the FA draft** (catches FA retirements decided in the offseason). No-op in the normal deep-pool case; only a thinned position triggers generation. Idempotent (already-generated FAs count as supply).

### Game Simulation (`floosball_game.py`)
- `playGame()` is the main loop — clock-based (900s/quarter, 600s OT). Pre-game it deep-copies attributes into `gameAttributes` and applies league compression, funding morale, fatigue, team disposition, and a mental soft-cap.
- Play-calling chain: `playCaller()` → (clock-management checks first) → `_computePlayWeights()` → `_getBasePlayWeights()` (down/distance table) → `_applySituationalMods()` → `_applyMatchupMods()` → `_applyCoachMods()` → `_executeWeightedPlay()` → `_selectPassPlay()`. Separate `_fourthDownCaller()` and `_otPlayCaller()`.
- **Clock management** triggers (all checked at top of `playCaller` when `down ≤ 3`): kneel (Q4/OT, leading, deterministic drain math), spike (Q2/Q4/OT, no timeouts, ≤120s, trailing/tied), offensive timeout (trailing/tied, has timeouts).
- **QB scrambles** (`_qbEscapesSack`/`_qbTucksAndRuns`/`_resolveQbScramble`, inside `passPlay()`): a mobile QB runs instead of taking a sack or throwing it away. **Agility gates** whether they scramble; **speed drives** the yardage (small agility bonus). Two trigger paths: (1) the sack branch (an agile QB escapes a would-be sack) and (2) the **throwaway branch** (no one open → tuck and run, **the primary path** since sacks are only ~0.8/game). A scramble flips `playType=Run` + `runner=passer` and reuses the run-crediting tail (carries/rush yards/TDs/longest/20+, defense run yards, a tackler credit, small fumble chance) so clock/WPA/box-score/fantasy all flow through the existing run paths. It does **not** call `runPlay()`, is **not** a sack (no sack stats), and is **not** a pass attempt (the throwaway path un-charges the attempt booked at the top of the branch via `stat_tracker.remove_pass_attempt`). `mustThrow` (desperation 4th-down/late) suppresses the tuck-and-run. PBP narrated as a scramble (`floosball_game.py:3380`, gender-neutral), with phrasing split by `play.scrambleReason` — `pressure` (escaped a sack) vs `coverage` (no one open, tucked it). Tunables in `constants.py` (`QB_SCRAMBLE_*`); flip `QB_SCRAMBLE_ENABLED=False` to disable. Volume in fast sims ≈ top mobile QB ~12 carries/season (~0.5/game), ~10 QBs scramble per season, ypc ~5. Plan: `docs/QB_SCRAMBLES_PLAN.md`.
- **Coach influence**: `adaptability` is one-directional (`max(0, (attr-80)/20)` — below 80 has zero matchup effect); `clockManagement` gates the quality of every situational decision; `aggressiveness`/`offensiveMind` scale deep/run/medium weights. `defensiveMind` is surfaced as `coachDefMind` in play-insights (read-only context, not a weight mod).
- **Win probability** (`calculateWinProbability`): ELO prior (divisor 400) blended with a logistic score model; ELO weight decays 1.0→0.05 over regulation; time-sensitivity `k = 0.06 + gameProgress^0.8 × 0.34`; late-game possession pulls WP toward 99/1. In OT `gameProgress` is clamped to 1.0 (ELO floors, k maxes); the OT-tied FG estimate shares `fieldGoalTry`'s constants.
- **WPA → MVP / All-Pro value metric** (`_resolvePlayWpa`/`_attributeWpa` in `floosball_game.py`): per-play win-probability swing is computed on every play in every timing mode (resolved above `broadcastGameState`'s early returns) and **attributed to players** — offense to the ball-handler (run→RB, completed pass 60/40 QB/receiver, FG/XP→K), and the zero-sum defense side shared across the 5 on-field defenders (QB→S/RB→LB/WR→CB/TE→DE) weighted by `defensiveRating` + a play-maker bonus. Accumulated to `player.seasonWpa`/`seasonDefWpa` and persisted (`wpa`/`def_wpa`/`wpa_snaps`/`def_snaps` on `GamePlayerStats` + `PlayerSeasonStats`; current-season-forward, not backfillable). **MVP** = `offenseScore (0.6 perfZ + 0.4 offenseWpaZ) + defValue (0.7 defWpaZ + 0.3 boxZ)`, all pooled-z within position. **All-Pro** is one combined team selected at season end (`seasonManager._selectSeasonAllPro`): an offensive squad (top `mvpScore` per QB/RB/WR/WR/TE/K) plus a defensive squad (top `defValue` per S/LB/CB/CB/DE, from `playerManager.selectAllDefense`/`_computeDefValues`). The roster plays both ways, so a dominant two-way star can hold both an offense and a defense slot. Stored as `Player.all_pro_seasons` (single accolade per honoree) + a rich `Season.all_pro_team` JSON (`[{id,side,position,value}]`) so the recap rebuilds the offense/defense split. There is **no separate DPOY or All-Defense award** (removed — folded into All-Pro). Weights in `constants.py` (`MVP_*_WEIGHT`, `DEF_BOX_WEIGHTS`, `DEF_PLAYMAKER_BONUS`, `WPA_PASS_QB_SHARE`). Full design + build log: `docs/WPA_MVP_PLAN.md`.
- Game length is purely **clock-driven**: the loop runs `while not isGameOver()`, and `isGameOver()`/`advanceQuarter()` key only off `gameClockSeconds <= 0`. The old play-count model is **deprecated** — there is no per-game play cap; `GAME_MAX_PLAYS`/`PLAYS_TO_*_QUARTER`/`FOURTH_QUARTER_START` no longer govern flow (the `PLAYS_TO_*` ones are imported but unused) and the emitted `playsLeft` field is vestigial. Don't treat plays-per-game as meaningful.
- Balance constants live in `constants.py` / `game_rules.py` (e.g. `LEAGUE_COMPRESSION_MEAN=80`, `LEAGUE_COMPRESSION_FACTOR=0.7`, quarter length 900s, OT 600s).

### Players, Teams, Coaches
- **Roster = 6 slots**: `qb, rb, wr1, wr2, te, k` (`team.rosterDict`). Slots are `None` when vacated (cut / unre-signed expiry / retirement).
- **Player tiers** by `playerRating`: TierS ≥92, A ≥84, B ≥76, C ≥68, D <68 (5/4/3/2/1 stars).
- Players carry offensive + derived **defensive** attributes (offense pos → defensive pos: QB→S, RB→LB, WR→CB, TE→DE, K→none) and mental/personality attributes (attitude, focus, instinct, creativity, resilience, selfBelief, pressureHandling, mood, personality, quirk).
- Contracts: `term` / `termRemaining`; `willRetire` is pre-decided in-season (week `GM_ACTIVE_WEEK`) by `_evaluateRetirementCandidates`, then executed in the offseason. Retirement odds are **longevity-relative**: bands key off `yearsPast = seasonsPlayed − longevity` (NOT absolute seasonsPlayed, which can't exceed league age). `playerManager.computeRetirementOdds(player)` is the single source of truth for eligibility + probability, shared by both the roll and the displayed risk tier (`computeRetirementRisk`) so they never drift. Phased contract gate: a vet only enters retirement territory on their walk season (`termRemaining==1`), but once ≥ `RETIREMENT_MIDCONTRACT_YEARS_PAST` (3) seasons past longevity they retire mid-contract too. Bands/chances in `constants.py` (`RETIREMENT_YEARS_PAST_*` / `RETIREMENT_CHANCE_*`). **Free agents** retire on a separate path (`_processFreeAgentRetirements`, keyed on `freeAgentYears`) that ALSO runs at week `GM_ACTIVE_WEEK` (with `preIncrement=True` to anticipate the offseason FA-years bump) — retirees are removed there, not just flagged, so the FA pool is finalized before ballots. By week 22 the full post-retirement picture is known (rostered flagged + FAs removed + rookie class known since season start), which the position-supply floor keys off.
- **Coach** has 8 attributes (offensiveMind, defensiveMind, adaptability, aggressiveness, clockManagement, playerDevelopment, scouting, attitude), all 60–100, neutral at 80. Per-team 3-candidate hiring slates (`CoachCandidate`).
- **Hall of Fame** (`playerManager.inductHallOfFame`, offseason training/HOF step): retirees are scored by `_computeHofPoints` (MVP 12 / ring 10 / All-Pro 4 / career-record 18 / season-record 6 / game-record 2 / 10+ seasons 4 / 14+ seasons 4) and inducted at `HOF_INDUCT_THRESHOLD` (22). Self-healing (scans newly-retired ∪ persisted retirees, skips `is_hof`). Induction stamps `player.hof_season` (the just-ended season → "Class of Season N"; null for pre-existing inductees). `hallOfFame` repopulates from `is_hof` retirees on load. Served enriched (awards, induction class, HoF credentials, position career highlight, team accent) via **`GET /api/hall-of-fame`**; the frontend renders a plaque gallery grouped by induction class (`HallOfFame.tsx`, under the Players page "Hall of Fame" tab), not the regular stats table.
- Note: QB overall-rating uses a different cached weighting than other positions (`rating_cache.py`) — see Open Questions.

### Card System (`cardManager.py`, `cardEffects.py`, `cardEffectCalculator.py`)
- **Editions** (rarity, ascending): `base → holographic → prismatic → diamond`. Edition IS the effect tier — each effect belongs to exactly one edition (`EFFECT_EDITION_TIER`). Base = simple/reliable; higher = more conditional/synergy-dependent with higher ceilings.
- **Pack types** (current seed, `card_repositories.py` `seedDefaults`): `humble` 50F (reveal 3/keep 2), themed position/output/team packs 75F (3/2), `grand` 90F (5/3), `themed_champion` / `themed_allpro` 110F (5/3, guaranteed holo+), `exquisite` 130F (7/4). Price ladder is monotonic by value: humble < themed < grand < champion/all-pro < exquisite. `starter` is free, once/season. **There is no "proper" pack.** Paid packs share rarity weights ~{base 82, holo 28, prismatic 7, diamond 1.5} (team packs ~{75/20/5/1.5}). Team packs aren't upserted, so `_seedTeamThemedPacks` refreshes their cost + weights on existing rows.
- **Classifications** (on templates): `rookie` (any edition); `mvp`/`champion`/`all_pro` (holo+ only), can compound (e.g. `mvp_champion`).
- **Operations**: open packs (reveal-then-keep flow), sell, promote, blend ("The Combine"). `transplant` is a reserved `CardUpgradeLog.upgrade_type` value with **no implementation**.
- **Equipped slots 1–5**, locked while games run. **Slot 6** unlocks when an MVP-classified card is equipped OR an active `temp_card_slot` powerup is held (checked at calc time).
- **Two-pass calculator**: first pass computes all normal effects; second pass computes cross-card effects (`copycat, chain_reaction, bonus_round, double_down, last_resort, high_roller, fortitude, charmed`) against first-pass breakdowns. Card-bug investigations: use the `card-effect-investigator` agent.

### Fantasy System (`fantasyTracker.py`)
- Roster of 5 sim players (QB/RB/WR/TE/K), +1 **FLEX** while a `temp_flex` powerup is active. Min 3 to lock.
- Weekly FP accumulated live (`_weekFP`), banked to `WeeklyPlayerFP` at week end; `getSnapshot()` is the single source of truth for leaderboards (overlays banked + current).
- `WeeklyModifier` shifts scoring emphasis per sim-week (one per hourly slot); `modifier_nullifier` powerup → per-user `UserModifierOverride` to "steady". A calendar day's slots share `week // 7`; the whole day's slot modifiers are **pre-rolled at the day's first slot** (`seasonManager._ensureDayModifiers`, also lazily on API hit) so they can be announced ahead. `getDayModifierSchedule(week)` returns the day's slate (active/next/past flags) — surfaced number-free via `GET /api/fantasy/modifier-schedule` (drives the fantasy "next up" badge).
- Card effects applied at week end → `WeeklyCardBonus` (with `breakdowns_json` for box-score display).
- Roster swaps tracked in `FantasyRosterSwap`; **escalating cost** = `15 + 15 × prior_swaps_in_that_slot` (`ROSTER_SWAP_COST` / `_INCREMENT`).

### Pick-Em System
- Predict each game's winner. **Per-game locking** — a pick is editable until that game hits Final.
- `points = base(10) × timing_multiplier × underdog_multiplier` (correct picks only). Timing decays by quarter (pre-game best, Q4/OT worst), softened for close games. Underdog multiplier from pre-game ELO (underdogs up to 3.0×, obvious favorites floored at 0.4×).
- `auto_pick_mode` on `users`: `off | favorites | underdogs | random` (auto-picks tagged `is_auto`, never overwrite manual). Clairvoyant bonus when weekly points exceed `PICKEM_CLAIRVOYANT_THRESHOLD`.
- **Whole-day picks**: `GET /api/pickem/day` returns every slot of the current calendar day (each slot labeled `Week N`, with its games + the user's picks — **no modifiers**, those live on the fantasy page) so a once-a-day user can prognosticate the full slate at once; `POST /api/pickem/picks` bulk-submits `{week, gameIndex, pickedTeamId}` across slots (per-game lock still applies — Final games are skipped, not errored). Per-game `/api/pickem/pick` is unchanged. `_buildPickemMatchup` is the shared matchup serializer.

### Achievements (`achievementManager.py`)
- **Scopes**: `once` (stored `season=0`) or `per_season`. **Categories**: `onboarding` (Rookie Goals), `guidance` (Season Goals, incl. tiered progressions), and `secret` (hidden until unlocked).
- **Rewards** (`reward_config`): floobits (immediate), packs/powerups (queued as `PendingReward`, claimable, deferrable to next season).
- Secret unlocks fire via `unlockSecret()` (idempotent). Recent: `mutineer` → displayed as **"Scorched Earth"** (vote to fire coach + release the whole roster in one offseason; awarded at offseason STEP 3.6); `tribune` threshold = `GM_TRIBUNE_VOTE_THRESHOLD` (6).
- `_seedAchievements()` upserts templates on every startup (refreshes name/description/category/scope/target/sort_order/reward_config without wiping `UserAchievement` progress). `backfillOnboardingAchievements()` runs on first `/api/achievements` visit.

### Powerups (`constants.POWERUP_CATALOG`)
Tracked in `ShopPurchase` with `expires_at_week`. Display names differ from slugs:

| Slug | Display | Price | Effect | Limit |
|------|---------|-------|--------|-------|
| `extra_swap` | Dispensation | 50F | +1 roster swap | — |
| `modifier_nullifier` | Annulment | 60F | Cards run under Steady this week | — |
| `temp_flex` | Conscription | 200F | +FLEX roster slot (4 wks) | 2/season |
| `temp_card_slot` | Accession | 200F | +6th card slot (4 wks) | 2/season |
| `fortunes_favor` | Patronage | 125F | +10% chance-card trigger (3 wks) | 2/season |
| `income_boost` | Endowment | 100F | Flatter FP→Floobit curve (4 wks) | 2/season |

### GM / Front Office (`gmManager.py`, `gm_repository.py`)
- **Single-vote model**: one net vote per fan per target (yea/nay), withdraw to change. The old per-season/per-type/per-target caps in `constants.py` are **legacy/unused**.
- Vote types + costs (`GM_VOTE_COST`): `fire_coach` 15F, `cut_player` 10F, `resign_player` 10F, `hire_coach` 10F, `sign_fa` 12F.
- **Thresholds**: fire/cut/resign pass when `net votes (yea−nay) ≥ teamFanCount` (frozen at week `GM_ACTIVE_WEEK=22` via `front_office_fan_snapshot`). `hire_coach` is plurality among the team's 3 candidates. `sign_fa` is ranked-choice (IRV) over open positions.
- **FA-draft cut exclusion**: a team cannot re-sign a player it released this offseason (cut OR expired-unsigned) in the same FA draft — detected by `previousTeam == team.name and freeAgentYears == 0` (`playerManager._leftThisTeamThisOffseason`); lifts next offseason; overridden only if a slot is otherwise unfillable.
- Secret hooks: `tribune` (cast `GM_TRIBUNE_VOTE_THRESHOLD` votes/season), `mutineer`/Scorched Earth (full teardown).

### Team Funding (`TeamFunding` model)
- `FUNDING_BASELINE_PER_TEAM=200F` granted each season; users contribute directly (`POST /api/teams/{id}/contribute`) or via passive end-of-season `team_funding_pct` (default 25%). `FUNDING_DECAY_RATE=0.5` carries 50% into next season.
- Self-scaling tiers by fair-share ratio (effective vs league average): `MEGA_MARKET ≥2.0×`, `LARGE_MARKET ≥1.15×`, `MID_MARKET ≥0.85×`, `SMALL_MARKET <0.85×`. Tier drives dev bonus, morale, and fatigue reduction.

### User Economy
- Currency: **Floobits**. Weekly FP→Floobits via a tapering power curve (no hard cap): standard `round(0.43 × FP^0.78)`; Endowment powerup `round(0.27 × FP^0.87)` (`WEEKLY_FP_FLOOBIT_SCALE/EXPONENT[_BOOSTED]`).
- All grants/spends logged in `CurrencyTransaction` (with `season`/`week`). `CurrencyRepository.addFunds` fires passive-grant achievement hooks + a `floobits_received` WS toast; `spendFunds`/`refundFunds` for purchases/undo.

### Anomaly System (`anomalyManager.py`)
A per-player "attention" score (decays 10%/week, fully **user-generated** — equipped cards/fantasy rosters/follows/favorite-team fans, no sim source) feeds a per-player ladder (`stable → stirring → erratic → rampant → awakened → cleansed`) and a hidden per-season league aggregate (`over_cap_carry` sum + linear background pressure) that can trigger league-wide "thinning"/Cores events. Surfaced via `/api/players/{id}/anomaly`, `/api/debug/anomaly-*` (testing aids — **not admin-gated**), and `league_news` items.
- **Threshold scales with active users** (`_seedThreshold`/`_countActiveUsers`, prod/non-fast): seeded per season as `clamp(THRESHOLD_BASE + THRESHOLD_PER_ACTIVE_USER × activeUsers, THRESHOLD_FLOOR, THRESHOLD_CEIL)` ±10% jitter, where active users = distinct users with a favorite team OR following ≥1 player. Since attention is user-driven, this keeps Criticality keyed to engagement *concentration*, not raw population (reachable at any size; ~140 users → ~216). FAST mode keeps the old low random band (`THRESHOLD_MIN/MAX`) so sims trigger.
- **Criticality is gated** (`ANOMALY_CRITICALITY_ENABLED=False`): the real event (math-swapping "thinning") never fires; the season is a tease. But the buildup is **not silent**.
- **Instability dial** (`getCriticalityMultiplier` / `_instabilityMultiplier`): the per-play glitch multiplier (used in `floosball_game._maybeFireAnomalies` as `prob = (attention/SCALE) × multiplier`) rides the aggregate's approach to threshold — flat at `INSTABILITY_BASELINE` while quiet, ramping to `INSTABILITY_PRECRIT_CEILING` (< `CRITICALITY_MULTIPLIER`) as the ratio climbs from `INSTABILITY_RAMP_START`→1.0, and floored to `INSTABILITY_SUPPRESSED` during a suppression window. So glitch frequency breathes with league tension.
- **Suppression / near-miss beat** (`_suppressCriticality`): when the aggregate crosses threshold while gated, instead of firing the Cores "patch" it — record a `suppression` entry on `cores_patches_applied`, open `suppression_window_ends_week` (= week + `SUPPRESSION_WINDOW_WEEKS`), drain every player's `over_cap_carry` by `SUPPRESSION_AGGREGATE_DAMP` (so the aggregate genuinely re-climbs), bump `threshold` by `SUPPRESSION_THRESHOLD_BUMP`, re-arm the warning cycle, and broadcast a Core-attributed line. Capped at `SUPPRESSION_MAX_PER_SEASON` (1-2/season); past the cap the league sits pinned critical for the rest of the year (dial at ceiling) but still never fires.
- **Status** (`getCriticalityStatus`): number-free qualitative bands (`dormant/stirring/unstable/critical`, or `stabilizing` during a window) for the Cores control-room view. Public via **`GET /api/cores/status`** (no raw aggregate/threshold — those stay in the ungated debug endpoint). Regression: `test_anomaly_suppression.py`.

### The Cores (`coresManager.py`)
The named AIs running the sim, surfaced as characters in the `league_news` feed (category `cores`, rendered in the frontend's HighlightFeed with per-Core icons). Five: **Cassian** (stability; **football-fanatic nerd** — friendly but always half-distracted by a game, resents the anomalies for interrupting a good season more than fearing them), **Pyre** (restrictive; **loveable curmudgeon** — gruff and put-upon, grumbles constantly but always does the work, secretly fond of the others and allergic to being thanked), **Aris** (curious; **whimsical** comic relief — delighted by the chaos, a little odd but still intelligible, wants the anomalies to happen, keeps trying to befriend the distant Pyre), **Halverson** (benevolent; earnest, loves the players more than the game and the others gently mock them for it), **Vera** (observer; **GLaDOS-flavored** faux-polite deadpan, secretly keeps perfect score of everything including the others' mistakes). Voice register is dry/vast/faintly-amused — the dread is in the gap between how casually they talk and the stakes. Per-Core voice + line pools + multi-Core exchanges in `coresManager.py`.
- **Solo lines** (`_VOICE` pools, `newsEntryFor`) for low-key beats (`warning_low`, `reset`).
- **Multi-Core exchanges** (`_EXCHANGES`, `exchangeEntriesFor`/`entriesForEvent`) — short conversations for the louder beats (`warning_high`, `suppression`, `criticality`) plus `idle` ambient banter. Each turn broadcasts as its own `cores` news item sharing an `exchangeId` + `turnIndex`/`turnCount` so the feed threads them. `entriesForEvent(event)` auto-picks exchange-where-it-exists, else solo; a forced `core=` always yields one attributed line.
- Ambient banter for the control room: **`GET /api/cores/conversation?event=idle`** (ephemeral, not persisted). `idle` may surface a **live data-aware beat** (`CORES_DATA_BEAT_CHANCE`, default 0.5); `event=observe` forces one. Data-aware beats are generated from live state — `observationExchange`/`observationEntriesFor` (real aggregate/threshold/percent + named climbing/awakened players) and `gameResultExchange`/`gameResultEntriesFor` (real teams/scores: nail-biter, upset, shootout, blowout). **These reference RAW numbers on purpose and live ONLY in this ephemeral control-room endpoint** — the public header/news feed stay number-free (`getCriticalityStatus`). The API layer gathers state (`_gatherAnomalyObservation` / `_gatherRecentGameResults` in `main.py`); coresManager owns the voicing.
- **Instance 498b**: this floosball is catalogued (Cores-side) as `498b` — `498a` is the prior failed iteration of the same instance; a Reset that doesn't hold burns the letter (`→ 498c`). The number is a Cores-only label (players never say it); it surfaces in idle banter + a `warning_high`/`reset` beat or two. Full lore in `data/lore.md` "Instance 498b".

### Personality & Reactions
`personalityManager` (YAML-templated personalities, quirks, moods, quotes) + `personalityReactionEngine` (in-game reactions, sideline cutaways surfaced in `game_state`/play insights). `rallyManager` handles live fan rallies (`POST /api/games/{id}/rally`).

### Discord Integration
Link via `/api/bot/link` (short-lived code → `users.discord_id`); opt-in DM reminders (`discord_dm_reminders`). Bot endpoints (`/api/bot/*`) authenticate with an **`X-Bot-Key` header** shared secret (`_checkBotAuth`), not Clerk.

## WebSocket
3 channels: **`/ws/season`** (primary — all game + season events; processes `{type:"identify", userId}` for per-user targeting), `/ws/game/{id}` (legacy per-game), `/ws/standings`. 30s server `ping` heartbeat. Per-user events (achievements, floobits) go via `broadcaster.broadcast_to_user_sync()` against identified sockets.

**EventType enum** (`event_models.py`) has **~50** event types. Highlights:
- **Game**: `game_state` (primary per-play), `game_start`, `game_end`, `game_rally`, `play_reaction_update`; legacy `play_complete`/`score_update`/`game_state_update`/`quarter_end`/`halftime`/`overtime_start`/`win_probability_update`.
- **Week/Season**: `week_start`, `week_end`, `day_complete`, `regular_season_complete`, `season_start`, `season_end`, `games_starting_soon` (15 min pre-kick — best signal for bot reminders).
- **Standings/Fantasy**: `standings_update`, `leaderboard_update`.
- **News/Awards/Player**: `league_news`, `mvp_announcement`, `all_pro_announcement` (combined offense+defense team), `player_stat_update`, `player_injury`, `player_off_day`.
- **Offseason**: `offseason_start/pick/cut/on_clock/team_complete/complete`, `offseason_predraft_start/team_setup/predraft_complete`, `fa_draft_order_update`.
- **Per-user**: `achievement_unlocked`, `floobits_received`. **Pick-em**: `pickem_results`. **System**: `error`, `info`.

## REST API (`api/main.py`)
~140 REST endpoints + 3 WebSocket. Response envelope (`api_response_builders.py`): success `{success:true, message, data}`, error via `HTTPException`. Some list endpoints (currentGames, standings, highlights, league-news) return raw payloads.

Endpoint groups (grep `@app.` in `main.py` for the full list): Teams, Players (incl. follow, quotes, anomaly, rating-history, `/api/hall-of-fame`), Games/Season (incl. reactions, rally), History/Records, **Recap** (`/api/recap` — consolidated current-season Season Recap: awards/standings/leaders/transactions/fan-leaderboards [fantasy/pick-em/bracket/funding]/showcase; durable via the `SeasonRecapEvent` log; current season only, no archive), Stats (leaders, mvp-rankings), League markets, Fantasy (roster/lock/swap/remove/snapshot/leaderboard/modifier/modifier-schedule/card-projection), Cards (collection/sell/blend/equipped/template-projection), Packs (types/pending/reveal/select/starter), Shop (featured/buy-card/reroll/powerups), Pick-Em (week/day/pick/picks/leaderboard/history), GM/Front Office (vote/undo/summary/eligible/fa-scouting/fa-ballot/rookie-ballot/votes/results), Achievements, Currency, Users (me/username/preferences/favorite-team), Notifications, Bot/Discord, Beta access, Cores (`/api/cores/status` — public, number-free Criticality band; `/api/cores/conversation` — ambient Cores banter), Debug (anomaly, ungated), **Admin** (gated by `_checkAdminAuth` — JWT `is_admin` OR `X-Admin-Password` header).

## Auth (`api/auth.py`)
Clerk RS256 JWT verified via JWKS. `getCurrentUser` maps `clerk_id` → local `User`, auto-creating + provisioning a starter pack on first sight (100 Floobits + 5 base cards, one per position; handles Clerk-instance email migration + race conditions). `getOptionalUser` / `getAdminUser` variants. Beta gate (when enabled) requires the email in `BetaAllowlist`. Usernames are generated (adjective+noun+number, unique-checked), set once.

## Database
- SQLite at `data/floosball.db`. **60 SQLAlchemy models** in `models.py` (domains: game/season/stats, players/attributes, user/economy, cards, fantasy, pick-em, shop, achievements, GM, team funding, anomaly, misc). `grep "class .*(Base)" models.py` for the list.
- **Two migration systems**: `alembic/versions/` (~38 files, canonical schema history for local/fresh setups) and **inline migrations** in `connection.py::_runPendingMigrations()` (idempotent `ALTER TABLE ADD COLUMN` / `CREATE TABLE IF NOT EXISTS`). **Inline migrations are what runs in prod** on every boot — alembic is not auto-run on deploy. New columns need an inline migration to land on existing prod DBs.
- `init_database()`: create_all → inline migrations → seeds (`_seedPackTypes`, `_seedBetaAllowlist`, `_seedAchievements`, `_seedUnusedNames`) → backfills (funding tiers, player season/career stats from games, team peak streaks, card output types).
- `clear_db()` (fresh start) **preserves** `users`, `beta_allowlist`, `app_settings`, `unused_names`; nulls per-season user flags (`starter_pack_claimed_season`, `favorite_team_locked_season`). After fresh start, existing users get re-provisioned starter packs in `startNewSeason()`.
- Repositories in `database/repositories/`: base (Player/Team/League/Game/Record/UnusedName), card (`CardTemplate/UserCard/EquippedCard/Currency/PackType`), game (`Game/GamePlayerStats` — note a second `GameRepository` exists in both `base_repositories.py` and `game_repository.py`; the app uses the latter), gm, notification, pickem, shop. For new columns, follow the `/migrate` command's four-step pattern (model → inline migration → backfill → load/save plumbing).

## Deployment (Fly.io)
```bash
fly deploy                                                 # Normal deploy (resumes season)
fly ssh console -C "touch /data/.fresh" && fly deploy      # Fresh start (one-shot flag file, auto-deletes on boot)
```
- `TIMING_MODE` in `fly.toml` `[env]` — normally `scheduled`; use `fast-catchup` to recover missed games.
- Prod SQLite at `/data/floosball.db`, **no `sqlite3` binary** — query via a `python3` heredoc in `fly ssh console` (use the `/dbquery` command).
- Never use the `FRESH_START` env var in prod (it survives restarts and would wipe the DB on outage recovery). `FRESH_START` is a local-dev-only convenience.

## Git Workflow
```
main              ← production (Fly.io; deploys only on manual `fly deploy`)
└── development   ← staging / integration (default branch)
     ├── hotfix/*      → merge to dev → main immediately
     ├── next-season   → between-season changes, merged when a season ends
     └── feature/*     → long-lived features
```
- Always **merge (no rebase)** into `development` and `main`. Tags `vX.Y.Z` on both repos.
- Backend `main` is comparatively safe (Fly deploys only on manual command). The **frontend `main` auto-deploys to Vercel**, so promoting the frontend to main is a release action — don't do it without explicit instruction.
- Use the `/promote` command to merge development → main with pre-flight checks.

## Files Not to Touch
- `legacy/` (reference only)
- `.vscode/launch.json` (unless necessary)

## Open Questions / Known Quirks (verified 2026-05-31, unconfirmed intent)
- **QB overall-rating divergence**: `rating_cache.py` weights QB as `(skill×2 + playmaking×1.5 + xFactor×1.5)/5` while other positions use `(skill×3 + playmaking + xFactor)/5`. Unknown whether intentional.
- **`/api/debug/anomaly-*`** are not admin-gated (comment says intentional for local sims, "not for production users"). Not gated in prod.
- **Dead/legacy**: the play-count model (`GAME_MAX_PLAYS`, `PLAYS_TO_THIRD/FOURTH_QUARTER`, `FOURTH_QUARTER_START`, the `playsLeft` output) is deprecated — game length is clock-driven; `timingManager.shouldUseInGameDelays()` has no callers; `auto_pick_favorites` column is superseded by `auto_pick_mode`; `players.demeanor`/`archetype` columns are legacy-nullable; `registerSingleton` in `service_container.py` doesn't actually cache (behaves like `registerFactory`).
