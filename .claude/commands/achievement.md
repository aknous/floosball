---
description: Add a new achievement end-to-end (seed template + unlock/progress hook at the trigger site + frontend hint for onboarding goals)
argument-hint: [name + trigger + reward, e.g. "Iron Man: full roster, no swaps, all 28 weeks → 100F"]
---

Add a new achievement: $ARGUMENTS

Templates are seeded in `database/connection.py::_seedAchievements()`; progress/unlock logic lives in `managers/achievementManager.py`; the trigger hook is called from wherever the triggering event happens (an API endpoint in `api/main.py` or a step in `managers/seasonManager.py`). If the category, scope, target, or reward isn't clear from the request, ask — these are baked into the seed and user progress. Honor the naming philosophy and the no-em-dash voice rule for the name/description.

## Decide first
- **Category**: `onboarding` (Rookie Goals — one-time hand-holding milestones, floobit-only rewards, get a frontend hint card), `guidance` (Season Goals — the main set, often tiered), or `secret` (hidden until unlocked).
- **Scope**: `once` (lifetime; `UserAchievement` stored with `season=0`) or `per_season` (re-earnable; stored with `currentSeason`).
- **Target**: the numeric goal (`1` for binary/secret unlocks; N for "do X N times").
- **Reward** (`reward_config`): `{"floobits": N, "packs": [slug], "powerups": [slug], "deferred": false}`. Floobits grant immediately; packs/powerups queue as `PendingReward`.

## Steps

### 1. Seed the template
In `_seedAchievements()` add a dict to the seed list:
```python
{"key": "iron_man", "name": "Iron Man", "category": "guidance", "scope": "per_season",
 "sort_order": <next in its group>, "target": 1,
 "description": "Play all 28 weeks with a full roster and zero swaps.",
 "reward_config": {"floobits": 100, "packs": [], "powerups": [], "deferred": False}},
```
`_seedAchievements()` upserts on every startup (refreshes name/description/category/scope/target/sort_order/reward_config without wiping `UserAchievement` progress), so the template updates on the next boot — no migration needed.

### 2. Wire the trigger
Pick the right hook function in `achievementManager.py` and call it where the event occurs:
- **Binary secret** → `unlockSecret(session, userId, "key")` (idempotent no-op if already unlocked).
- **Counter / threshold** → `recordProgress(session, userId, "key", increment=1)` or `recordProgress(..., absolute=value, currentSeason=season)`.
- **Themed events** already have `on*` hooks (e.g. `onPackOpened`, `onWeeklyFantasyPoints`, `onSeasonFloobitsSpent`, `onClairvoyant`, `onWeeklyFantasyPodium`). If your trigger fits an existing event, extend that hook; otherwise add a new `on<Event>()` and call it from the trigger site.
- Per-user grants flow through `_grantReward()`, which **commits before broadcasting** the `achievement_unlocked` WS toast (so a crash can't produce a toast without a row). Call hooks where a DB session is available.
- Trigger sites: API endpoints in `api/main.py` (e.g. pack open, roster set, vote cast); season/offseason milestones in `seasonManager.py` (e.g. season-end leaderboard finishes, the offseason STEP block).

### 3. Onboarding hint (onboarding category only)
If `category == "onboarding"`, add a hint entry in the frontend `AchievementsPage` Rookie Goals hints map (`floosball-react/src/Views/.../AchievementsPage`): a step-by-step list + an action button that either dispatches a `floosball:*` window event or navigates to a route (+ optional `afterEvent`/`afterScrollTo`). Without this the goal renders but has no guidance.

### 4. Verify
- `python -c "import ast; ast.parse(open('database/connection.py').read()); ast.parse(open('managers/achievementManager.py').read()); print('OK')"`
- Confirm the `key` is unique and the trigger hook is actually reached (grep for the call site).
- For tiered progressions, confirm `sort_order` slots it correctly within its group and the tier thresholds line up.

Report the key, where the trigger fires, and whether a frontend hint was needed. To see it unlock live, drive the trigger in an isolated sim (`/simcheck`).
