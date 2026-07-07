# League Parity + Prospect True-Skill — Design & Build Plan

> Next-season roster-balance package. Combines three owner initiatives that all touch the same generation → development → rating → cap chain:
> **(1) league parity (skill redistribution)**, **(2) prospect ratings rework (enter-low, develop-into-true-skill)**, **(3) salary cap**.
> All changes are **between-season** (applied at the rollover), never in-season. Design locked 2026-07-07.

_Status: Phases 1, 2, 3, 4 done + validated. Phase 5 (salary cap) remains. Owner-agreed forks recorded below._

## Phase 3 — re-map: built + validated on a prod copy (2026-07-07)
`playerManager.remapPoolToTrueSkill()` + guarded one-time call `seasonManager._maybeRunParityRemap()` (fires in `startNewSeason` when `resumeFromWeek==0`, BEFORE card gen; persisted `AppSetting` marker `parity_remap_done`; auto-skips a pool already on-curve via `parityStarFraction() > 0.28`; persists players before marking done).
- **Scope = ALL non-retired players** (rostered + FA + prospects + upcoming), rank-preserving PER POSITION onto a freshly-generated mature reference curve.
- **Career-staged freeze/runway (final design):** rank places each player on the mature curve. **RISING** players (below their peak season) debut BELOW that rank (current lowered by a bounded runway, capped at `PROSPECT_ENTRY_DISCOUNT`) and develop UP into it — trueSkill = mature rank, potential a touch higher. **PEAK/DECLINING** players are FROZEN at their rank (trueSkill = potential = current). So genuinely-young players keep a real development arc while the pool still converges ON the curve at maturity (no re-inflation).
- **Two key findings from prod-copy boots (both fixed):**
  1. An early version re-mapped only the active pool + left `potential=trueSkill+headroom`; the excluded prospect cohort kept OLD inflated potentials and re-mapped players had overshoot room → **re-inflated 19%→25% over 4 seasons**. Fix: re-map ALL non-retired + freeze peak/declining.
  2. First runway attempt set rising players' trueSkill ABOVE their deflated current (runway added on top) → they developed ABOVE the curve → **re-inflated 18%→26%**. Fix: rising players debut BELOW the rank and grow UP into it (runway subtracts from current, not adds to trueSkill).
- **Validated (corrected runway):** prod-copy boot **44% → converges 12.6→16.5% and plateaus ~16-17% whole-pool (~19-20% active), no creep**. Owner forks: full re-map (no blend); rising keep runway, peak/declining frozen.
- **League-metrics side effect (owner ACCEPTED, 2026-07-07):** the deflation cools offense over the transition — pts/g ~20→17, passing yards ~280→234 (−15%), rushing steady ~96. Owner chose to accept it (fewer stars = less offense, more realistic); no compression compensation. NOTE: this was measured on the transitional prod-resume; fresh new-model steady-state scoring was not separately measured.
- Validated end-to-end on the WIRED path: raw prod copy boot → migration adds `true_skill_*` → re-map fires at cutover → marker set → holds. Minor edge: ~2% of frozen players drift 1pt past potential (dev-arc rounding); no aggregate effect.

## Validation results (Phases 1+2 via fresh 10-14 season fast sims, 2026-07-07)
- **No creep — confirmed.** A fresh league run 14 seasons at `(76,8)` held the whole-pool mean rating flat at ~74 with the 4-5★ % oscillating in a band (no upward trend). The rare-overshoot ceiling does NOT inflate the league — the dev arc's true-skill growth cap is the anchor. (Owner chose "rare overshoot ceiling" for the potential's role; `DEV_OVERSHOOT_BASE_CHANCE=0.12`.)
- **Career arc — confirmed.** Rookies reach true skill in ~2 seasons (median), career peak lands at true skill (mean −0.2), ~16% overshoot toward potential, then decline.
- **Star % calibrated to `(78,10)`** = `GEN_TRUESKILL_MEAN/STD`. Confirming 10-season sim settled steady-state **~16-17% 4-5★** (band 15.7-18.3, mean flat ~76.2-77.0) — in the 15-20% target. Whole active pool (rostered+FA) runs ~2pts below the mature-snapshot dist (FA scrub dilution).
- Entry discount `PROSPECT_ENTRY_DISCOUNT=11` → star rookies debut ~6.9 rating pts below true skill.

## Why

The league is top-heavy (Cranes ~26-2, ~80% titles in S13 sims, 3 of last 4 Floos Bowls). Two roots, measured on the S12 prod copy:
- **Star oversupply** — ~40% of ~245 live players are 4-5★ (healthy ≈ 15-20%); pool centered at rating 81.
- **Concentration** — the best 6 cluster on one roster; team-salary spread 15-27 / avg 22.

In-game skill compression (`LEAGUE_COMPRESSION_FACTOR`) was tested at 0.7/0.6/0.5 and **rejected** — barely moved the Cranes, only lowered scoring. Concentration, not per-player gap, drives dominance. So the fix is at the source (generation + development curve) plus a cap (concentration).

## The three-tier rating model (the core reframe)

Today the engine collapses "true skill" and "potential" into one ceiling: the *generated* attribute is the player's **entry** level, and the rise-to-peak arc climbs them toward the per-attribute `potential = attr + randint(0,30)`. There is no middle tier.

We introduce **true skill** as a distinct, persisted per-attribute layer:

| Tier | Meaning | Today | After |
|------|---------|-------|-------|
| `current` (live attrs) | what they play at now | the generated attr | generated **below** true skill for rookies |
| **`trueSkill`** | mature level they reliably develop into | — (does not exist) | **new** per-attribute cols, drawn from the parity distribution |
| `potential` | hard ceiling, rarely fully reached | `attr + randint(0,30)` | `trueSkill + randint(0,~15)` |

Invariant: `current ≤ trueSkill ≤ potential ≤ 100` at generation.

### Owner-agreed forks (2026-07-07)
- **Representation:** per-attribute true-skill columns (8, mirroring the existing `potentialX` set). Faithful; enables a later scouting/uncertainty feature.
- **Entry discount:** **moderate, ~6-9 rating points** below true skill. A future 5★ debuts looking like a solid 3-4★ and grows in over ~2-3 seasons.

## Phases & build order

### Phase 1 — Data model + generation (true-skill layer)
1. **Schema** (`/migrate` four-step): add `true_skill_speed / _power / _agility / _reach / _hands / _arm_strength / _accuracy / _leg_strength` to the players table (mirrors `potential_*`). Model field + inline migration + load/save plumbing in `playerManager`.
2. **Generation** (`floosball_player.py` `getPlayerAttributes` + per-position rating/potential blocks ~955-1180):
   - Draw the per-player seed from the **parity distribution** (lower/wider than today's `normal(78-80, 7-10)` — target so trueSkill matures to ~15-20% 4-5★). This seed defines **trueSkill**, not current.
   - `trueSkillX = normal(seed, 3)` clipped `[60,100]` (same spread the generated attrs use today).
   - `potentialX = min(100, trueSkillX + randint(0, POTENTIAL_HEADROOM))` — headroom narrowed from 30 → ~15 (true skill is now the target; potential is the occasional overshoot).
   - **Entry discount for rookies/prospects:** `currentX = max(60, trueSkillX − entryDiscount)` where `entryDiscount` calibrates to ~6-9 *rating* points (attribute-level ~8-11, measured). Veterans generated at league founding start at `current = trueSkill` (no discount — they're not rookies).
   - `potentialSkillRating` recomputed off trueSkill for continuity.
3. **Flatten development rise** (parity lever): `DEV_RISE_RANGE (-1,5) → (-2,3)` so climb is gentler and fewer players run past their true skill.

### Phase 2 — Development arc (climb to true skill, overshoot to potential)
Rework `player_development.py::developAttribute`:
- **Rising phase:** target is `trueSkill`, not `potential`. `change = min(change, max(0, trueSkill − current))` for the reliable climb; a **small** extra roll (gated by `devBias`/luck) allows pushing `current` past `trueSkill` toward `potential` (the overachiever). Coach/facility `devBias` accelerates the climb and improves overshoot odds.
- **Peak / decline:** unchanged (decline still pulls below true skill; uncapped down to `DEV_ATTRIBUTE_FLOOR=55`).
- Prospect boom/bust spread still widens the tails.

### Phase 3 — One-time percentile re-map of the live pool
- Existing players have no `trueSkill`. Backfill it **rank-preserving**: per position (QB / RB / WR / TE / K separately — QB uses a different rating weighting and K excludes defense, so a pooled remap would distort them), map each player's current `playerRating` onto the new target distribution's percentile, and set `trueSkill` accordingly. #1 stays #1; fewer qualify as 4-5★.
- For **veterans** past their peak, `current` tracks the remapped level; for **young/rising** players `current` sits below the remapped `trueSkill` per the entry model.
- Runs once at the cutover (idempotent guard marker). Owned cards are insulated (templates snapshot rating at season start — confirmed).

### Phase 4 — Multi-season sim validation
- Extend `s13_multisim.py` (resumes from `data/_s13_seed_src.db`) to report the **star distribution** (% 4-5★ at maturity) and **parity** (champion concentration, top-team win totals) across N seasons.
- Gate: ~15-20% mature 4-5★, Cranes-type dynasty broken up over a few seasons. Tune the generation center/width + entry discount here before touching the cap.

### Phase 5 — Salary cap (model B) — BACKEND BUILT + VALIDATED 2026-07-07
**Status:** backend logic done + validated on fresh sims. Cap UI (Front Office) remains (P5d). Implementation:
- **Freeze/ratchet:** `_getPlayerTerm` (playerManager, the single choke point all signings route through) stamps `capHit = tier.value` at every signing/promote/re-sign. Rostered = frozen by omission; re-sign re-prices (the ratchet).
- **Cap-aware re-sign** (`seasonManager._applyCapAwareResign`, STEP 2.7 before contract decrement): per team, keep highest-value expiring players within cap (fan votes first, then value), reserving MIN per open slot; rest WALK. Sets `_gmResigned`.
- **Budget gate** (`playerManager._attemptRosterFill`): filter candidates to affordable within `usableCapForSigning` (= CAP − salary − MIN×other-open-slots). **NEVER overspend or auto-cut** (owner directive) — if nothing affordable, sign nothing → last-resort mints a MIN-tier (cap-1) filler, which the reservation guarantees fits. `generateLastResortFreeAgent` now mints a D-tier (cap-1) replacement.
- **Short star contracts** (`_getPlayerTerm`): S/A veteran deals 4-6/3-4 → **2-3 yrs** so the ratchet re-prices a built core faster (the real dynasty-breaker for draft-and-develop teams).
- Helpers: `teamSalary` / `capSpace` / `usableCapForSigning` (on-demand from frozen cap_hits — no stored state, sidesteps the front-office marker/resume caveat).
- **Constants:** `SALARY_CAP=18`, `SALARY_FLOOR=14`, `MIN_CAP_HIT=1`, `SALARY_CAP_ENABLED` master switch.
- **Validated (fresh 12-season sim):** 7 distinct champions, top team 2 titles, longest streak 2 (vs original ~permanent Cranes dynasty, and vs cap-20/6-yr's 3 champions/7 titles). **0 teams over cap** (hard cap holds by construction, no auto-cuts), rosters 24/24 full, salaries 13-18 (biting), 2 under floor, min-filler fired 30× cleanly.
- **PROD MIGRATION (deploy onto a live over-cap league) — NO forced cuts.** (1) The re-map re-prices contracts (`cap_hit` = deflated tier) so most teams land near/under the cap at the cutover. (2) Teams still over cap are **grandfathered** — the budget gate fills their open slots with the cheapest player (never a hole, never a cut). (3) They converge to compliance over ~2 offseasons purely via contract expiry / non-renewal (the re-sign pass won't renew into an over-cap roster → the player walks). Validated on a prod copy: 6/24 over at cutover (max salary 23) → 0 over by season 15 (6→2→0), all 24 rosters full throughout.

#### Original design notes (refined 2026-07-07)
**Model B:** `cap_hit` **frozen at signing** (today recomputed live from tier = model A; enforcement dormant — `# TODO: capHit feature not fully developed`, `playerManager.py:4667`). Rookie signs cheap and stays cheap on that contract; re-signing re-prices to the player's *current* (developed) tier. The ratchet at re-sign is the dynasty-breaker.

**PROACTIVE budgeting, NOT reactive force-cuts (owner concern 2026-07-07).** The naive "sign freely then auto-cut over-cap teams" model is rejected — bad-feeling automated cuts + stuck loops (spend on 2 signings, no room for a 3rd, forced cut, still stuck). Instead every signing/re-signing reserves cap for the team's remaining open slots:
`usable cap for THIS signing = teamCap − current roster salary − (MIN_HIT × other open slots)` — so a team can **never sign itself into an unfillable corner**. Phases:
- **Re-sign** (primary pressure): expiring contracts re-price to current tier; team keeps the **highest-value set that fits** `cap − reserved-for-open-slots`, the rest **WALK to FA** (declining to renew, not a cut). Owner-chosen unmanaged auto keep-rule: **highest value within cap** (fixed 6-slot structure prevents positional gaps — a walked QB's slot fills cheaply in FA).
- **Fill**: open slots filled within the per-slot budget; always finishes a full roster.
- **Cut**: stays a **deliberate GM/fan vote** (existing `cut_player`), never automated from overspend.
- Managed teams: existing GM/fan votes made cap-aware (a vote that busts cap/reservation is surfaced as unaffordable, with the reason). Unmanaged: transparent value-based auto.

**UI (owner wants it):** surface each team's cap space / committed salary / open-slot reservations in the Front Office. Backend exposes cap data; frontend displays (floosball-react).

**⚠️ Recalibrate cap/floor.** The old **~24 / ~19** was for the OLD 40%-star spread (15-27 / avg 22). Parity dropped the league to ~16-19% stars → team salaries now run **lower** → those numbers would strand most teams under the floor. **Measure the new team-salary spread first, then set cap ≈ 1.1× avg, floor ≈ 0.85× avg.** Floor = yes (owner) — forces weak teams to spend, absorbing shed stars.

**Build order:** (1) freeze cap_hit at signing → (2) cap-aware re-sign + fill (proactive budgeting) → (3) expose cap data + FO UI → (4) measurement sim to set cap/floor + confirm dynasties break without gutting rosters.
- Separate phase — only after the distribution is validated, so the cap is calibrated against the new rating spread.

## Key anchors (from the code map)
- Generation: `floosball_player.py:743` (`getPlayerAttributes`), per-position rating+potential `:955-1180`; `playerManager.py:709` (`generatePlayersByPosition`), `:819` (`createPlayer`), `:3835` (`_generateRookieClass`).
- Development: `player_development.py` (whole file); constants `constants.py:35-62`.
- Potential persistence: `playerManager.py:1622-1630` (save), `:428-439` (load); model `models.py:242-250`.
- Tier + cap: `playerManager.py:1320-1341` (tiers + live cap_hit), `_calculateCapHit :4623`, dormant enforcement `:4512`.
- Card minting snapshot: `cardManager.py:317-412` (safe re-rate boundary).
- Quirks to respect in the remap: QB weighting `rating_cache.py:179`; kicker rating excludes defense `floosball_player.py:1180`.

## Design notes / risks
- **In-game compression stays** — the stored `playerRating` (tiers/cap/cards) is uncompressed; `gameAttributes` re-narrow toward 80 in-game. A distribution change won't move in-game strength one-for-one; measure via the sim, not the raw ratings.
- Two generation centers exist today (founding `normal(80,7)` vs rookie `normal(78,10)`) — unify onto the single parity distribution.
- Card blast radius: between-season timing insulates owned cards; re-confirm when Phase 3 runs.
