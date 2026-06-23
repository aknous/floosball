# Sim Evolution — Cores-driven, fan-shaped mutation

> Status: **idea capture / design**, not built. Lives on `next-season`.
>
> Unifying concept: at special moments (chiefly the aftermath of a **Criticality**), the
> **Cores** hand the fans real power to reshape the simulation — its **rules** and its
> **rosters**. Each Core does it in character. The sim drifts away from "football" over many
> seasons, steered by the fanbase. This is the payoff layer the gated Criticality has been
> teasing.
>
> **Read alongside `docs/AWAKENED_POWERS_PLAN.md`** — the canonical **L4 awakened-powers +
> Criticality** spec (signature abilities, the per-game charge meter, Criticality as the
> *overdrive*). That doc defines the anomaly/Criticality machinery these ideas hang off of; the
> `criticality_event_design` and `sim_evolution_anomaly` memories carry the surrounding event /
> ladder / Cores design. The ideas below are the **Criticality aftermath**: once it fires, what
> do the Cores let the fans reshape next?
>
> All of these reuse three things that already exist:
> - **`GameRules`** (`game_rules.py`) — one dataclass holding every tunable rule (field length,
>   downs, first-down distance, scoring values, clock…), with a serializer and an existing
>   `patchHistory` field. The mutation target.
> - **The Cores** (`coresManager.py`) — Aris (curious, wants the chaos), Pyre (restrictive
>   curmudgeon), Vera (GLaDOS archivist), Cassian (distracted superfan), Halverson (earnest).
> - **Fan-voting infra** (`AwardsManager` / `gmManager`) — ballots, windows, quorum scaled to
>   active users, per-user and per-team scoping.

---

## Idea 1 — Rule mutation (Aris) + reversion (Pyre)

The game's **rules** evolve. Aris pushes them outward; Pyre pulls them back; fans steer both.
With a wide-enough rule set and enough seasons, floosball could mutate into a different game
entirely. That's the goal, not a side effect.

### Aris's mutation (post-Criticality)
**Trigger:** a Criticality fires and Aris is ascendant (she *welcomes* the anomalies). This is a
reason to let the gated Criticality actually resolve — at minimum into a rule mutation rather
than the full haywire event. Rule-mutation could even *be* the softer Criticality payoff.

**Flow:**
1. Aris announces (Cores feed) that she's "tuning the rules" and opens a **mutation ballot**.
2. The ballot offers a slate of candidate changes — each a single rule nudged within a vetted
   range, so the change stays legible ("Touchdowns are now worth 7").
3. Fans vote (free, like awards). Top vote wins; below quorum → Aris picks her favorite.
4. The winner is **persisted** and takes effect **next season** (a clean rule-era boundary).

**Starter set of mutable rules** (`GameRules` fields — each default + an allowed range/step):

| Rule | Field | Default | Example range |
|---|---|---|---|
| Touchdown points | `touchdownPoints` | 6 | 4–8 |
| Field-goal points | `fieldGoalPoints` | 3 | 1–5 |
| Extra-point points | `extraPointPoints` | 1 | 0–2 |
| Downs per series | `downsPerSeries` | 4 | 3–5 |
| Yards to a first down | `firstDownDistance` | 10 | 7–15 |
| Field length | `fieldLength` | 100 | 80–120 |

Extensible later: quarter length, OT format, 2-pt value, safety value, kickoff position, and
eventually structural rules (scoring zones, player counts, new play types) so the ceiling on
"a different game" stays high.

### Pyre's reversion
**Trigger:** every N seasons, or once cumulative drift crosses a threshold (X active mutations),
Pyre — exasperated — opens a **reversion ballot**.

**Flow:**
1. Pyre grumbles ("This has gone far enough.") and lists Aris's active mutations.
2. Fans vote on **which** rule(s) to revert (approval-style; revert the top vote-getters, capped).
3. Reverted rules snap back to their `GameRules` defaults next season.

The tug-of-war keeps the game wandering without running away — unless the fans let it.

### Data model
- **`rule_overrides`** (persisted, per-instance): current value of each mutated rule; absent →
  default. The engine builds `GameRules` from defaults overlaid with overrides.
- **`rule_change_log`**: Core (Aris/Pyre), season, rule, from→to, winning tally — for the recap,
  a Rulebook page, and lore. The existing `patchHistory` field can carry the Core-patch framing.
- Ballots reuse the voting tables/machinery (a new vote type or dedicated table).

---

## Idea 2 — Player resurrection (Vera / Cassian)

Fans grieve when a beloved player retires. A Core offers to bring one back — **per team,
fan-chosen**. Pulling a "saved" player back into the live sim is exactly the eerie, god-like act
the Cores' register is built for.

**Which Core:** **Vera** (the archivist who keeps perfect records — "The file was never deleted.
Merely… archived. Shall I restore it?") leans eerie/powerful; **Cassian** (the superfan who
misses the greats — "Best player this team ever had. Want them back? I won't tell Pyre.") leans
wistful. Could alternate, or pick per the tone wanted.

**Trigger / cadence:** an **occasional offseason event** (not every season — keep it special), or
a Criticality aftermath. Could gate to seasons where enough decorated players retired.

**Flow:**
1. The Core announces a resurrection window (Cores feed).
2. **Per team**, that team's fans (favorite-team fans) get a ballot of that team's **retired,
   well-decorated** former players.
3. Fans vote; the top vote-getter **per team** is resurrected onto that team (roster slot, or the
   FA pool if no slot).

**Eligibility:** retired **and** decorated — gate on the existing `_computeHofPoints` (or
accolades: MVP / rings / All-Pro / records), and on having played for *that* team.

**Price (the tradeoff):** resurrection is **not free** — the team **sacrifices a facility level
or two** to pull it off. So bringing back a legend genuinely costs the franchise (weaker
facilities = worse dev/morale/fatigue/scouting next season). The fans aren't just picking a
player; they're deciding the legend is worth the downgrade. Hooks straight into the **Facilities
treasury/levels** system (`facilitiesManager`) — knock the chosen facility(ies) down a level (or
spend a treasury equivalent). Could even let fans choose *which* facility to sacrifice.

**Return state (open question):** the key balance lever.
- *Peak* rating → a true return, but decorated players at peak could be overpowered.
- ***Revenant / echo*** → returns below peak (~80–85%) with a short longevity (a few seasons of
  decline). Bittersweet swan song, not a dynasty restart. **Leaning here** — balanced + on-theme.
- Fresh longevity but a capped ceiling.

**Anomaly tie-in:** resurrection is literally re-instantiating an archived player into the live
sim — deeply on-theme for the anomaly/awakening layer. The returnee could even carry a faint
"glitch"/awakened quality as a nod to it.

**Data/infra:** reuse retired-player records + HoF; reuse **per-team** fan voting (like GM votes).
Resurrect = un-retire + reinstate with the chosen return-state. Watch the position-supply floor
and roster-fill logic so a resurrection doesn't double-fill or strand a slot.

---

## Shared threads & open questions
- **One fan-voting system** powers all of it (windows, quorum, per-user/per-team scoping).
- **Sim safety:** every rule override needs a vetted range, ideally a fast sim-validation before
  it goes live — a 1-down or 200-yard field could break play-calling/balance. Resurrections need
  roster-integrity checks.
- **Criticality gating:** these give the gated Criticality something real to resolve *into*.
  Decide which beats are Criticality-driven vs. standalone offseason events.
- **Records across eras:** stats under a 7-point-TD / 3-down ruleset aren't comparable to
  default-era records. Tag records/seasons with their rule-era, or embrace the drift as flavor.
- **Pace:** tie mutation frequency to Criticality frequency; tie reversion to a drift threshold so
  it self-corrects. Keep resurrection rare.
- **Per-instance, league-wide** ruleset (matches the single-sim model).

## Rough phasing
1. **Rules-from-overrides infra** — `rule_overrides` store + the engine reading `GameRules`
   through it, with range validation. (Data-driven rules, no UI/vote yet.)
2. **Aris mutation** ballot + apply.
3. **Pyre reversion** ballot.
4. **Player resurrection** (per-team ballot + reinstate).
5. **Rulebook page** (current vs. default + change log) + recap + Cores voicing polish.

---

## Feasibility (assessed against the codebase, 2026-06-22 — design only)

Both ideas are **~M effort each**, built largely on existing infra — finish-the-wiring jobs, not
ground-up builds. The fan-**voting** layer is cheaply reusable for both; the effort lives *outside*
the voting, in the application mechanics.

### Rule mutation / reversion
**Foundation already there.** `GameRules` is **one shared per-season instance**
(`seasonManager.py:90`), read consistently in ~40 sim sites, and already has `applyPatch()` + a
`patchHistory` audit trail + `toDict()`. The override store plugs into a single seam
(`SeasonManager.__init__`); because every game references that one object, a mid-season patch
propagates automatically.

**Gaps (the work):**
- **Persistence — not built.** `GameRules` lives only in memory and is recreated as defaults on
  every boot, so a change is lost on restart. Needs a `rule_overrides` JSON column on `Season`
  (inline migration) + hydrate on season start. A persisted sibling exists
  (`LeagueAnomalyState.cores_patches_applied`, "mirrors patchHistory but persisted") but nothing
  writes rule overrides yet. **[S]**
- **Hardcoded-value leaks.** ~12 scoring/PAT/2-pt/FG literals (`_addScore(team, 6/3/2/1)` call
  sites), ~15 `down == 4` sites (the core possession loop), field-position anchors (80/60/20), and
  clock literals (`*900`, `600`, `120`) that won't respect a mutated rule. Mechanical, but real. **[S–M]**
- **Sim-safety.** Drastic *structural* values (3 downs, 80-yard field, 7-point TD) stress heuristics
  that assume the defaults — the WP model's `*900` time math, play-calling deficit/aggression
  tables, "one-/two-possession game" inference. The genuinely hard part. **[L for structural rules]**

**Recommendation:** ship a **bounded first cut** — persistence + de-hardcode the scoring/FG
literals + restrict mutations to *low-blast-radius* rules (scoring values, FG attempt prob, clock
thresholds, kneel drain). That delivers the full Aris-mutates / Pyre-reverts loop end-to-end with
contained sim risk; defer downs/field-length/TD-points until heuristic-safety is scoped.
**Overall: M (bounded) → L (structural).**

### Player resurrection
**Feasible, ~M.** Retiree data is **fully retained** (Player row + attributes + accolades survive
retirement — nothing is purged), the "decorated" gate **reuses `_computeHofPoints` verbatim**, and
roster reinstatement **reuses the FA-signing state machine** + an un-retire prelude.

**Gaps:**
- **"This team's retired greats" query.** `previousTeam` is in-memory only (not persisted). The
  durable hook exists — accolade JSON (MVP/All-Pro/championship) embeds a team abbr, and the HoF
  gallery already derives team this way — but a *records-only* decorated retiree has no durable team
  link. Clean fix: a small additive `previous_team_id` column backfilled from
  `PlayerSeasonStats.team_id`. **[S]**
- **Offseason ordering / supply floor (the careful part).** Insert the resurrection *after*
  retirements resolve and *before* the final pre-FA `ensurePositionSupply` check (≈ offseason STEP
  3.3–3.4) so the player is rostered *and* counted as supply — otherwise the supply floor desyncs
  and the FA draft can strand/over-fill slots. Needs a `/simcheck` pass.
- **Facility cost.** Treasury debit (`addTreasury` negative) is a clean *existing* price primitive.
  **Knocking down a level has no path today** (levels only go up or passively decay), so a small new
  `spendFacilityLevel` helper (~5 lines) + endpoint is needed if the price is literal levels. **[S]**
- The "revenant" diminishment (return below peak, short longevity/term) is new but localized
  (reuses `_getPlayerTerm` for the short contract).

**Overall: M** — assembly + two small additions + the un-retire mechanics + a per-team vote
surface. No engine/scheduling/playoff changes.

### Voting (shared)
- **Rule ballot (league-wide, single pick)** → clone the **Awards/MVP** pattern (derived windows,
  engagement-scaled quorum, plurality + fallback). Needs a **small new `RuleVote` table** (target is
  a rule key, not a player FK, so `AwardVote` can't be reused as-is) — ~40 lines. **[S]**
- **Resurrection ballot (per-team)** → extend **`GmVote`** with a new `vote_type`
  (`resurrect_player`). **No schema change** — retirees are still `Player` rows; drops straight into
  the existing offseason GM-resolution batch + the fan-count threshold. **[S]**
- For *both*, the effort-determining work is **outside the voting** (rule application; un-retirement).

### Bottom line
Both are **M-effort, infra-reuse** features. Do the voting cheaply on the existing systems; spend
the real effort on (1) rule **persistence + de-hardcoding** (bounded rule set first), and (2) the
resurrection **un-retire mechanics + offseason ordering** (with a sim-check). **Structural** rule
mutations (downs, field length, TD points) are the only **L-tier** risk — gate them behind the safe
scalar mutations. Resurrection's voting is the lightest first win; rule-mutation's *persistence
layer* is the highest-leverage piece to build first.

## Build log — mutable rule layer (2026-06-23)

The rule-mutation persistence layer (`GameRules.applyOverrides` + `loadRuleOverrides`/
`saveRuleOverrides` → `app_settings`, hydrated in `Season.__init__`) is live and the
`MUTABLE_RULE_FIELDS` allowlist gates what may be mutated. Proven mutable so far:

- **Scoring values** (`touchdownPoints`, `fieldGoalPoints`, `extraPointPoints`,
  `twoPointConversionPoints`, `safetyPoints`) — proven via a "rainbow" override (each value
  distinct from every old literal) + instrumenting `_addScore`: across 4,082 scoring events the
  only point values emitted were the override values, zero of the old literals (6/3/1/2). Every
  scoring site reads `self.gameRules.*`. (`fgMinAttemptProb` is allowlisted too — a play-calling
  input, not a score value; matters once powered-up kickers need extended FG range.)
- **Structural #1 `firstDownDistance`** — core mechanic already read `gameRules`; fixed the three
  goal-to-go `10` literals (one mechanic at the conversion site, two display) to `firstDownDistance`.
  Proven at `firstDownDistance=15`: 789/789 fresh non-goal-to-go first downs measured exactly 15
  yards (zero at 10), scoring fell 14.3→12.5 ppg, no crashes.
- **Structural #2 `downsPerSeries`** — generalized every "final down / advance-vs-turnover /
  possession-loop bound / kneel count / spike availability / clock-management gate" from the
  literal 4 to `gameRules.downsPerSeries`; replaced the by-down ordinal text + `PlayResult` chains
  with `downOrdinal()`/`downPlayResult()` helpers (now support up to 6 downs via `FifthDown`/
  `SixthDown`). Named-stat counters (`3rd/4thDownAtt`), pressure-by-down, and `down_factor` stay
  as graceful-degradation heuristics. Proven at 3 and 5: the per-play down distribution bounds
  exactly at `downsPerSeries` (dp=3 never reaches down 4; dp=5 produces 8,468 fifth-down plays),
  scoring is monotonic (9.6 / 12.5 / 17.8 ppg at 3/4/5 downs), two offseasons completed cleanly.
  No code outside `floosball_game.py` assumes a fixed 4 downs.

**Deferred: field geometry.** `fieldLength` (and `kickoffPosition`, to be wired in the same pass)
stay gated. They touch the field-position model *and* the win-probability EP table, which feeds
MVP/All-Pro/pick-em — so they need an exhaustive field-position sweep (touchback spot = fieldLength−20,
midfield = fieldLength/2, yardLine display, punt flip, onside spots, WP `field_position` normalization)
plus a WP-regression check. FG range correctly stays absolute (a 35-yard kick is 35 yards on any field).

## Build log — clock knobs + running clock (2026-06-23)

Promoted out of the gated set:

- **Clock / FG scalars** (`overtimeLengthSeconds`, `timeoutClockThreshold`, `spikeClockThreshold`,
  `kneelDrainSeconds`, `fgSnapDistance`) — already read from `gameRules`; one consistency fix
  (`kneelDrainSeconds` was the AI's drain *prediction* only, the actual post-play drain was a
  hardcoded `min(36,…)` → now `kneelDrainSeconds - 4`). Proven: kneel post-play drain is exactly
  `kneelDrainSeconds-4`; `fgSnapDistance` 17→7 raised FG output 1.64→1.78 per team-game.
- **Running clock** — new booleans `clockStopsOnIncompletePass` / `clockStopsOnOutOfBounds`
  (default True = standard football), gated in `shouldClockRun()` (the single per-play clock
  decision; none of the 14 explicit `clockRunning=False` stops touch incompletion/OOB). With both
  off: plays/game 162.9→117.9 (−28%), ppg 12.2→9.3. The clock-management play-calling heuristics
  still assume incompletions stop the clock, so they degrade gracefully — a later pass can make
  them rule-aware (e.g. don't favor sideline/incomplete throws to "stop the clock" when it won't).

Still gated: field geometry (`fieldLength` + `kickoffPosition`), `quartersPerGame` (67 sites assume
Q4 = final / halftime at Q2), and the remaining placement scalars (`patSnapDistance`,
`twoPointConversionDistance`, `twoMinuteWarningSeconds`).
