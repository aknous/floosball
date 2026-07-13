# Rule Changes — Cores-Driven Live Rule Mutation (Workstream B)

> Design + build plan. Turns the dormant rule-mutation layer into a live, user-voted
> mechanic: **Aris** opens a vote to CHANGE a game rule, **Pyre** opens a vote to
> REVERT changed rules. Owner-specced 2026-07-08. Canonical tracker: `docs/NEXT_SEASON.md`.
> Background: `docs/SIM_EVOLUTION.md`, memory `rule-mutation-future-ideas`.

## Overview

Each game day there's a chance a Core calls a vote. Users vote from a modal on the
dashboard (with a live countdown + running totals). The most-voted option wins — no
quorum. The winning rule is applied immediately to the rest of the season, and the
change persists (drifts) into future seasons until a revert vote restores it.

The engine is already built for this (`game_rules.py`): `GameRules.applyOverrides()`
mutates fields, `saveRuleOverrides()` persists to `app_settings`, the season holds one
shared `gameRules` every game reads live, and `GET /api/rules` already reflects
overrides. **Blast radius is contained**: only `floosball_game.py` reads the mutable
fields — the win-probability model (hardcoded EP brackets), pick-em (own constant), and
MVP scoring (stat z-scores) do NOT read `gameRules`, so a rule change can't destabilize
them. It only changes on-field scores/flow.

## The mechanic

### Season day structure (existing)
Regular season = 28 weeks = 4 game days × 7 weeks. Day `d = (week-1)//7`:
- Day 0 = weeks 1–7 (real Mon), Day 1 = 8–14 (Tue), Day 2 = 15–21 (Wed), Day 3 = 22–28 (Thu).
- The first week of each day = **week 1, 8, 15, 22** — our trigger points.
- Cross-day rollovers (wk 8/15/22) already happen ~8h early (prior evening); wk 1 is season start.

### Trigger + escalation (per season)
At the start of each game day (week 1/8/15/22) we roll whether a vote fires. The chance
ramps with each consecutive prior game-day this season that did NOT fire, and is
guaranteed once three in a row have missed:

| Consecutive prior misses | Fire chance |
|---|---|
| 0 | 25% |
| 1 | 50% |
| 2 | 75% |
| 3 | 100% (guaranteed) |

Firing resets the streak (the next day is back to 25%). Because there are exactly 4 game
days, this guarantees **at least one vote per season** (day 3 is forced if days 0–2 all
missed) and at most four. `RAMP` values are tunable constants.

> **No separate counter needed.** We record a `RuleVoteWindow` row for every day we
> process (fired or not). `missedDays = dayIndex − (max fired dayIndex this season, else −1) − 1`.
> This derives the ramp from persisted rows, so a mid-day restart never re-rolls (idempotent).

### Change vs revert (Aris vs Pyre)
When a vote fires, pick which kind:
- If fewer than `REVERT_GATE` (default **3**) rules are currently changed → always an **Aris CHANGE** vote.
- Once `≥ REVERT_GATE` rules are changed → **50/50** Aris CHANGE vs **Pyre REVERT** vote.
- Guards: a CHANGE vote with no default candidates left → falls back to REVERT; a REVERT
  vote with nothing changed → falls back to CHANGE (can't happen past the gate, but safe).

### The ballot
- **Candidate pool** = the 7 curated fields (`RULE_VOTE_CANDIDATES`). Each declares its
  alternate space: a discrete **`values`** list (structural rules stay integer) or a numeric
  **`range`** (scoring values, `float: True` → one-decimal values allowed, e.g. a touchdown
  worth 6.4). A specific proposed value is chosen when the vote opens — always different from
  the current value AND the default — and stored on the window, so the ballot shows exactly
  what a win applies.
- **CHANGE ballot** (Aris) = a random **4** of the fields that have an available new value,
  each `current → proposed`, **plus "None"**. This **includes already-changed fields** — a
  rule can be changed to a NEW value before it is ever reverted (e.g. Touchdown 6 → 7, later
  7 → 5.5).
- **REVERT ballot** (Pyre) = a random **4** of the currently-changed fields, each
  `current → default`, **plus "None"**. Revert is the only path back to default.
- Fewer than 4 available → show what exists (+ None). One rule changes per vote.

Candidate fields + alternate spaces (all tunable):

| Field | Default | Alternate space |
|---|---|---|
| `downsPerSeries` | 4 | values `[3, 5]` |
| `firstDownDistance` | 10 | values `[5, 8, 12, 15]` |
| `touchdownPoints` | 6 | range `4–9` (float) |
| `fieldGoalPoints` | 3 | range `1–5` (float) |
| `safetyPoints` | 2 | range `1–5` (float) |
| `clockStopsOnIncompletePass` | true | values `[false]` |
| `clockStopsOnOutOfBounds` | true | values `[false]` |

### Window lifecycle (same-day, applies immediately)
1. **Opens** at the game-day start hook (when the day's slate rolls in). `opensAt = now`,
   `closesAt = 15 minutes before the first game of that day` (games start on the hour at
   12:00 ET, so ~11:45 ET).
2. Users vote from the dashboard modal, framed as **a conversation with the Core**. The
   Core opens in-voice asking what to do (Aris: gleeful "which rule shall we break?"; Pyre:
   put-upon "please, put one back"). The user picks one option (or None), changeable until
   close, and the Core **reacts in-voice to the live selection**:
   - **Aris (change):** picked a rule → delighted ("this'll be fun!"); picked None →
     disappointed ("you're no fun!").
   - **Pyre (revert):** picked a rule → relieved / grateful; picked None → upset / dismayed.
   The reaction bubble updates immediately as the pick changes. **Live totals shown** for
   every option (NOT hidden like awards — bandwagoning is fine/fun here) and a **countdown
   timer** ticks to `closesAt`.
3. **Resolves** at `closesAt`: the option with the most votes wins. Ties, or "None" winning
   / tying for the lead → **no change**. No quorum.
4. **Applies immediately**: `season.gameRules.applyPatch(field, value, source='cores_vote')`
   on the live shared object (all of that day's games read the new value), and the persisted
   `rule_overrides` map is updated (`saveRuleOverrides`). Revert = patch the field back to
   default + drop the key from the map.
5. **Drift**: the persisted map is applied at every `Season.__init__`, so changes carry into
   future seasons until reverted. Nothing is cleared at the rollover.

> **Fast/headless sims** have no voters → resolve to "None" (no change) by default. An
> optional `RULE_VOTE_SIM_AUTOPICK` env can random-pick for engine testing without
> affecting prod.

## Cores voicing (`coresManager.py`)

New event types, wired through the existing `entriesForEvent → _broadcastCoreEntries` path
(broadcasts `cores`-category `league_news`, already rendered with per-Core icons):
- `rule_vote_open_change` — **Aris** calls the change vote (impish, wants the chaos). Solo
  lines + optional multi-Core exchange (Aris proposing, Cassian/Pyre wary).
- `rule_vote_open_revert` — **Pyre** calls the revert vote (put-upon curmudgeon dragging the
  rules back to normal, grumbling but doing the work).
- `rule_change_applied` — announces the winning change (Aris gloats / Vera notes it dryly).
- `rule_reverted` — announces a restored rule (Pyre satisfied; Aris pouts).
- `rule_vote_none` — the fans chose None / it tied (a beat: Aris disappointed, or relief).

Add lines to `_VOICE` (Aris/Pyre primary) and `pickCoreForEvent` weights. Keep the dry,
faintly-amused register; no em-dashes in any user-facing line.

**Conversational modal lines (separate from the news-feed events).** The vote modal is an
in-voice exchange, so `coresManager` also owns short line pools for the modal itself, picked
once at window open and stored on the `RuleVoteWindow` (stable across polls/reloads, served
with the ballot):
- `rule_vote_prompt` — the Core's opening ask (Aris for change, Pyre for revert).
- `rule_vote_react_pick` — reaction when the user selects a **rule** (Aris delighted / Pyre grateful).
- `rule_vote_react_none` — reaction when the user selects **None** (Aris let down / Pyre upset).

A helper like `coresManager.ruleVoteConversation(kind)` returns `{core, prompt, reactPick,
reactNone}` for storage. One line each per window keeps a single Core "voice" consistent for
that vote.

> **Persona note:** CLAUDE.md's Cores section calls Halverson "benevolent" — that's stale;
> the code persona is the nonsense Fact-Core. We're using **Pyre** for reverts, so this
> doesn't block us, but fix the CLAUDE.md Halverson line in this change.

## Data model (`database/models.py` + inline migration)

- **`RuleVoteWindow`** — one row per (season, day) we process. Fields: `season`,
  `day_index` (0–3), `fired` (bool), `kind` ('change'|'revert'|null), `core`, `option_keys`
  (JSON list of `{field, value}` — the specific proposed value per candidate), `prompt_line`,
  `react_pick_line`, `react_none_line` (the Core's stored conversation lines), `opened_at`,
  `closes_at`, `resolved` (bool), `winner_key` (field key | 'none' | null), `winner_prev` /
  `winner_value` (JSON from→to of the applied change), `applied` (bool). Unique
  (`season`, `day_index`).
- **`RuleVote`** — one row per (user, window). Fields: `user_id`, `window_id`, `option_key`
  ('none' or a field key), `created_at`. Unique (`user_id`, `window_id`). Changeable (upsert).
- Repository: `RuleVoteRepository` (create/close windows, cast/withdraw votes, tally).
- Reuses the existing `app_settings` `rule_overrides` key for the applied ruleset (no new
  persistence for the rules themselves).

## API (`api/main.py`)

- `GET /api/rules/vote/status` — is a window open, its `kind`, `closesAt` (for the nav badge
  + popup trigger). Cheap, pollable.
- `GET /api/rules/vote/ballot` — the open window's `core` + conversation lines (`prompt`,
  `reactPick`, `reactNone`), options (each `field`, `current`, `proposed`, label), **live
  totals** per option, the user's current pick, and `closesAt`.
- `POST /api/rules/vote` — cast/change a vote (`{optionKey}`); free. Rejected once closed.
- `POST /api/rules/vote/withdraw` — clear the user's pick (optional; or POST 'none').
- `GET /api/rules` — already returns `changed` + `patchHistory`; add the last change's
  `{field, from, to, core}` for the pill's "what changed" line (derive from patchHistory).

## Frontend (`floosball-react`)

- **`useRuleVote` hook** (mirrors `useAwards`): polls `/api/rules/vote/status`, fetches the
  ballot, casts votes, exposes `open/kind/options/totals/myPick/closesAt`.
- **`RuleVoteModal`**: framed as a **conversation** with the Core (Aris violet / Pyre red per
  `coresVisual`, with the Core's icon/avatar). The Core's `prompt` sits at the top; the
  options render as `current → proposed` cards with a radio pick + None; selecting one swaps
  in the Core's `reactPick`/`reactNone` bubble live. A **live countdown** to `closesAt` and
  **running vote totals** per option round it out. Auto-opens once per window on first
  dashboard visit (localStorage `lastSeenRuleVote_{season}_{day}`, the SurveyModal pattern);
  re-openable from the sidebar/pill while open.
- **Sidebar badge**: a dot when a window is open (mirrors the Awards badge), labeled by kind
  (Aris change / Pyre revert).
- **`RulebookIndicator` badge + popover**: a notification dot when the ruleset changed since
  the user last viewed it (localStorage `rulesSeenPatchCount`); the popover shows a strip:
  "Aris changed Downs per series 4 → 3" / "Pyre restored Field goal 2 → 3", from patchHistory.
- **WS**: a `rule_vote_opened` signal (or detect the `cores` news `eventType`) in
  `useSeasonUpdates` flips the hook to open state so the popup can appear without a poll wait.

## Blast radius / safety
- Confirmed readers of mutable fields are all in `floosball_game.py`. Applying a change
  before the day's kickoff means no in-progress game is touched.
- **Win probability** now reads the rules: `calculateExpectedPoints` keys its down factor
  off `downsPerSeries` (the LAST down is the turnover down, not a hardcoded 4th) and scales
  EP by the current `touchdownPoints`/`fieldGoalPoints`; `calculateWinProbability`'s
  blowout dampener measures the gap in "scores" via the current TD+XP value. All reduce to
  today's behavior at the default rules. The score-margin term already used real scores.
- **Pick-em** underdog multiplier uses pre-game ELO (rule-agnostic); **MVP/WPA** attribution
  is symmetric across both teams. So the fairness-sensitive consumers stay sound.
- **TD > FG invariant:** the value sampler (`ruleVoteManager._respectsScoreOrder`) never
  proposes a field goal worth ≥ the current touchdown, nor a touchdown worth ≤ the current
  field goal; reverts move toward the 6/3 defaults, which already satisfy it given the
  candidate ranges (FG 1–5, TD 4–9). So a FG can never out-value a TD, and the "teams should
  chase the higher-value FG" scenario simply can't arise.
- **Decision-tree rule-awareness (full pass):** the play-caller reads the live values via
  `_fgValue()`/`_oneScore()`/`_maxPossession()` everywhere a scoring assumption drove a
  choice — the 4th-down caller, OT caller, catch-up/lead weighting, Hail Mary, desperation-FG
  "win vs tie", one-score checks, garbage-time tiers, hurry-up/timeout timing, momentum-decay
  buckets, comeback urgency, and the down-based pressure gauge (`downsPerSeries`). The
  two-point decision is now computed from the live extra-point / two-point / touchdown values
  (possessions-to-erase) instead of a fixed chart. Scalar bands reduce to today's behavior at
  the default rules; the 2-pt logic is close to the old chart at default and smarter off it.
  The only remaining literals are the labeled 3rd/4th-down **stat counters** (display, not
  decisions).
- `applyOverrides`/`applyPatch` already filter to `MUTABLE_RULE_FIELDS` and audit-log every
  patch (`patchHistory`), so an out-of-set key is a no-op, and every change is traceable.
- Same-day/immediate is the owner's chosen v1 ("let's see how that works first"); the window
  model makes moving to a next-day apply a one-line change if we revisit.

## Build phases
1. **Engine + persistence** — `saveRuleOverrides` wiring, live `applyPatch`/revert helper on
   the season, the candidate-alternate table + constants (RAMP, REVERT_GATE, ballot size).
2. **Data model + repo** — `RuleVoteWindow`/`RuleVote` + migration + `RuleVoteRepository`.
3. **Trigger + resolution in the season loop** — day-start hook (weeks 1/8/15/22), escalation
   roll, window open/close, resolve + apply, Cores broadcast. Idempotent/resumable.
4. **API** — status/ballot/vote/withdraw + `/api/rules` last-change enrichment.
5. **Frontend** — `useRuleVote`, `RuleVoteModal` (countdown + totals), sidebar badge, pill
   notification + popover strip, WS wiring.
6. **Validation** — a fast sim to confirm the trigger fires ≥1×/season, windows resolve,
   rules apply + drift + revert, and nothing crashes the engine; manual UI pass on the modal.

## Tunable constants (all in `constants.py`)
`RULE_VOTE_RAMP = [0.25, 0.50, 0.75, 1.0]` · `RULE_VOTE_REVERT_GATE = 3` ·
`RULE_VOTE_BALLOT_SIZE = 4` · `RULE_VOTE_CLOSE_LEAD_MINUTES = 15` · candidate field→alternate
table · `RULE_VOTE_SIM_AUTOPICK` (env, testing only).

## Open / revisit later
- Next-day apply vs same-day (revisit after seeing v1).
- Widening the candidate pool to more of the 14 mutable fields (clock knobs) once WP is swept.
- Whether float score values need scoreboard/tiebreaker formatting polish once live.
