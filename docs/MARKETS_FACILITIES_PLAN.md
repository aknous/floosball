# Markets → Facilities Plan

> **Status:** Design locked, not built. Replaces the passive "team funding / market tier" system with a fan-funded, fan-voted **Facilities** system. This doc is the source of truth for the build; update it as the implementation lands (mirror the AWARDS_VOTING / WPA_MVP plan-doc convention).

## 1. Why replace the current system

The current markets feature (`TeamFunding` + `funding_tier`) is mechanically fine but **illegible**. An audit (backend + frontend) found the core problems are structural, not cosmetic:

- **The timing model fights intuition.** Tiers are inherited from last season and frozen all regular season; contributions only affect *next* season's tier. "I'm funding my team to help them win now" is just wrong, and the UI reinforces the wrong model.
- **Three competing funding numbers** (`current_funding`, `effective_funding`, `tier_locked_funding`) the user can't disentangle.
- **Contradictory in-app copy** (a Help modal still cites fixed 500/1000/2000F thresholds that don't exist; the real system is a relative fair-share ratio).
- **The whole season-end flow is invisible** — the tax fires, the tier locks, and the user is shown none of it.

The fix isn't more tooltips. Replacing the abstract relative tier with **a visible treasury that fans vote to spend on concrete facilities** makes every benefit traceable to a decision a fan made. That is the design below.

## 2. The model — three separate concepts

Today's "market tier" secretly conflates *market size* and *investment*. The new model splits them into three legible things:

| Concept | What it is | What it drives | Fan control |
|---|---|---|---|
| **Market** (Fanbase) | How many users favorite the team — a fanbase-size band | Expectation-pressure / spotlight scaling | None (it's popularity) |
| **Treasury** | Floobits fans contribute (in-season + season-end deposit) | Funds upkeep + projects | Direct (contribute) |
| **Facilities** (Appeal) | What's been built (leveled) | Player dev / morale / fatigue / scouting **+** FA-draft order | Vote + fund |

So "how big is our following" and "what have we built" stop being one muddy number.

**Labels:** keep the familiar **MEGA / LARGE / MID / SMALL_MARKET** names, but repoint them at **Market = fanbase size** (relative fan-count band) — which is what "market" literally means in sports, so it's now *more* accurate than today's usage. It's a mostly-decorative badge that also drives expectation-pressure scaling (genuinely a market-size effect — see `EXPECTATION_SCALE_BY_TIER`). The new **Appeal** signal (facilities-derived, §6) is a *separate* thing that drives FA order. A few-fan whale club is then a "SMALL_MARKET, high-Appeal" overachiever — the labels stay meaningful instead of redundant.

## 3. The seasonal cycle

The whole lifecycle rides the **Front Office** cadence players already know (GM/MVP/HoF votes open ~week 22 `GM_ACTIVE_WEEK`, resolve in the offseason). One mental model for "when decisions happen."

```
WEEKS 1–21    FUNDRAISING + DIRECT FUNDING
              Fans contribute Floobits straight to any facility's UPKEEP bar or any
              OPEN PROJECT bar, anytime. Bars have fixed costs + visible progress.

WEEK 22       VOTE OPENS  (with the rest of the Front Office)
              Fans vote on the NEXT project to start — an upgrade to an existing
              facility OR a brand-new facility. One vote per fan, changeable
              (the GM single-vote model). Plurality wins. Tally hidden until close.

WEEKS 22–32   Vote runs through the playoffs. Direct funding continues.

SEASON END    VOTE RESOLVES → winner appended to the back of the OPEN PROJECTS queue.
              SEASON-END DEPOSIT (passive team_funding_pct of unspent Floobits) applies
              as a WATERFALL:
                1. Top up any facility upkeep still short.
                2. Remainder flows to the OLDEST open project.

OFFSEASON     RESOLUTION (new gated offseason step)
              - Upkeep still unmet → facility slips a level (decay).
              - Any open project now fully funded → BUILDS, leaves the queue,
                takes effect NEXT season.
              - Partially-funded projects stay open, progress intact, carry forward.

NEXT SEASON   New facility levels drive their effects all season. Repeat.
```

**The three funding roles, cleanly separated:**
- **Voting = direction** — what the club chases next.
- **Direct funding = acceleration / queue-jump** — push *your* pick now, ahead of the FIFO waterfall; also how upkeep stays covered mid-season.
- **Season-end deposit = steady FIFO progress** — upkeep first, then the oldest open project.

**Dynamics:** a rich, engaged club clears its queue fast and keeps it short; an ambitious-but-poor club builds a backlog and finishes oldest-first. Upkeep is the honest recurring tax that stops anyone from over-building and coasting.

### Confirmed edges
- **Backlog allowed** — fans vote a new project every season even if older ones are still open; the queue can grow, cleared oldest-first (direct funding can jump it).
- **Decay on unmet upkeep** — a facility that ends the season with upkeep short slips a level. (The season-end deposit covers upkeep *first*, so a fan running a non-zero `team_funding_pct` passively keeps the lights on.)
- **Direct funding can target *any* open project**, not just the newest.

## 4. The facility catalog

Each facility maps onto an effect the sim **already applies today**, so the mechanical hooks exist — facilities just become the new source of the per-team bonus value (replacing the tier lookup).

| Facility | Effect | Existing hook to repoint |
|---|---|---|
| **Training Facility** | Player development bonus | `FUNDING_DEV_BONUS` → `offseasonTraining` (`player_development.py`) |
| **Locker Room** | In-game morale nudge | `FUNDING_MORALE_MODIFIER` (`floosball_game.py` pregame) |
| **Recovery Center** | Fatigue accumulation reduction | `FUNDING_FATIGUE_REDUCTION` (`_accumulateFatigue`) |
| **Scouting Department** | Rookie evaluation accuracy | `FUNDING_SCOUTING_BONUS` (rookie scouting) |
| **Stadium** | Home-crowd morale / fanbase-ceiling (new, small) | new — starts unbuilt for everyone |

Levels **0–5** (0 = unbuilt = neutral baseline; effects scale with level). The per-level effect curves are **redesigned finer-grained** than today's coarse 3–4-value tier perks, anchored so the migration (§9) reproduces current perks. `defensiveMind`-style read-only context unaffected.

> Effect-per-level curves are a tuning task — calibrate so a migrated MEGA team is **≥** its current perks (no nerf) and Lv5 is a new above-MEGA ceiling to build toward. Validate with `/simcheck`.

## 5. The economy — share-denominated, self-scaling costs

Fixed Floobit prices go trivial as the game grows. So **every cost and upkeep is denominated in *shares*, not absolute Floobits**, where:

> **1 share = (total Floobits *distributed* to users last season) ÷ number of teams**

"Distributed" = the **faucet**: the sum of every *positive* currency grant in the season (weekly FP→Floobit, fantasy/pick-em leaderboard prizes, pick-em payouts, showcase payouts, bracket prizes, supporter dividends, spectator cheer, achievements). It explicitly **excludes spending** (packs, contributions, the season-end tax) — those are money moving around, not the economy growing. Computed as `SUM(amount) WHERE amount > 0 AND season = N`.

**Why income (faucet), not balances (bucket):** scaling off balances held creates a destabilizing loop — spending on facilities drains balances → denominator drops → costs get cheaper → encourages more spending. Income is exogenous to facility spending and stable across the season.

**Why last season:** this season's faucet isn't known until it ends, so season N prices off season N−1's completed total (set once at season start; first season uses the migration-seeded value).

This is the same self-scaling spirit as the old fair-share tier and the anomaly/awards active-user thresholds — using *earning power* instead of headcount, because we verified headcount ≠ wealth (a 4-fan whale team was the richest in the league).

### Cost & upkeep curve (share fractions — starting values, tune via sim)

| Level | Upgrade cost | Upkeep / season |
|---|---|---|
| 1 | 0.05 share | 0.005 share |
| 2 | 0.10 share | 0.015 share |
| 3 | 0.20 share | 0.040 share |
| 4 | 0.42 share | 0.115 share |
| 5 | 0.85 share | 0.300 share |

At S10's faucet (~6,000F/team share) these read as: Lv5 upgrade ≈ 5,100F, Lv5 upkeep ≈ 1,800F/season. Full-max (5 facilities × Lv5) ≈ **1.5 shares ≈ 9,000F/season** in upkeep.

### The plateau (answers "does upkeep choke building? is maxing feasible?")

A team builds until **total upkeep ≈ its income**, then it's at its sustainable plateau; pushing further means decay or growing fan income. Grounded in real S10 income (per-team `fan_contributions`, ~700× spread):

- **Whale** (~15k/season): can *approach* full-max over ~10+ seasons, but then 9k/season upkeep means **engage or decay** — a real ongoing achievement, not a default.
- **Mid** (~6k): sustains ~2 maxed facilities + a few mid ones → **specializes**.
- **Bottom** (~200–800, near the 200F baseline): holds a Lv1–2 floor off the baseline until its fans engage.

Maxing everything is intentionally *not* feasible for most — so clubs build an **identity** (a Recovery+Training grind team, a Scouting+Stadium draft factory). Bounded inequality (engaged fanbases build more, capped at Lv5), not runaway.

**Balancers:** flat share-fractions for all teams (no per-team cost scaling — headcount is a bad proxy), the **200F baseline floor** (everyone holds a minimal set), the **Lv5 benefit cap**, and the **upkeep plateau**.

## 6. Appeal → FA draft order

FA draft order currently keys off `tier_rank`. Replace with a continuous **Appeal** score = weighted sum of a team's facility levels. Order the FA draft by Appeal (highest picks first) — a clean narrative: **free agents prefer clubs with better facilities.** Appeal is its own surfaced rating, **distinct from the Market label** (which is fanbase size, §2) — so a small-market club that's built great facilities still drafts high.

**Preserves tier order at launch (locked):** because the grandfather migration seeds facility levels from tier, Appeal at activation = 16 (MEGA) / 12 (LARGE) / 8 (MID) / 4 (SMALL), reproducing the exact current FA order; `effective_funding` is the within-Appeal tiebreaker so within-tier order is identical too. No team loses a draft slot in the transition season. (Shipped: `seasonManager._buildFaDraftOrder`.)

## 7. Data model

New tables / columns (follow the `/migrate` inline-migration pattern: model → ALTER TABLE → backfill → load/save):

- **`TeamFacility`** — one row per (team, season, facility_type): `level`, `upkeep_funded` (this season), and a denormalized `effect_value` cache. Or persist current levels on a per-team row and track funding separately (impl detail).
- **`FacilityProject`** (the open-projects queue) — `team_id`, `facility_type`, `kind` (`upgrade`|`new`), `target_level`, `cost_shares`, `funded` (Floobits), `opened_season`, `status` (`open`|`built`), `built_season`. FIFO by `opened_season`/id.
- **`FacilityVote`** — `team_id`, `user_id`, `project_key` (which candidate they back), `season`. Single-vote, changeable (mirror `AwardVote` / GM vote repos).
- **`FacilityContribution`** — log of direct earmark contributions (or reuse `CurrencyTransaction` with a `facility_contribution` type + a target ref). Needed for progress bars + "you contributed" surfacing.
- Retain **`TeamFunding`** as the Treasury ledger (Treasury balance = carried + contributions − spent), but `funding_tier` becomes the **derived Market label** (fanbase band — it already holds the MEGA_MARKET names), no longer a gate. **Appeal** is a separate computed value (from facility levels).
- **`Season`** (or `app_settings`): cache last season's faucet total → the share unit.

## 8. Voting

Reuse the GM Front Office voting primitive: **one vote per fan per team, changeable, plurality wins.** Candidates = every available upgrade (each facility's next level) + every unbuilt new facility. Window opens week 22, closes at season end; tally hidden until close (anti-bandwagon, like awards). Winner → back of the open-projects queue. Quorum: if turnout is below the active-user floor, default to the highest-Appeal-value upgrade (a sensible auto-pick), mirroring the awards below-quorum fallback.

## 9. Migration plan — current tiers → starting facilities

**Goal:** no team wakes up nerfed. A team's current tier perks must be reproduced by its starting facility levels, with headroom to grow.

**Mapping (starting level for each of the four perk facilities):**

| Current `funding_tier` | Training / Locker / Recovery / Scouting | Stadium |
|---|---|---|
| `MEGA_MARKET` | **Lv 4** | Lv 0 |
| `LARGE_MARKET` | **Lv 3** | Lv 0 |
| `MID_MARKET` | **Lv 2** | Lv 0 |
| `SMALL_MARKET` | **Lv 1** | Lv 0 |

**Calibration constraint:** design the per-level effect curves so that **Lv4 ≥ current MEGA perks** and **Lv3 ≥ current LARGE perks**. Then:
- MEGA/LARGE teams land on facilities that reproduce (or slightly exceed) what they have today.
- **Lv0 = neutral baseline.** This means today's **SMALL-market penalties disappear** — a migrated SMALL team starts at Lv1 (a small *positive*), not penalized. This is a deliberate, constructive change ("you just haven't built much yet" beats "you're penalized for being small"), and a mild buff to the bottom that the relative-cost economy then governs. **Flag for sim validation** — confirm it doesn't over-flatten competitive spread.
- **Stadium starts unbuilt for everyone** — a new shared aspiration no current team has.

**Migration steps (one-time, inline-migration + backfill, gated by an `app_settings` flag):**
1. Create the `TeamFacility` rows from each team's current `funding_tier` per the table above.
2. Seed each team's **Treasury** from `carried_funding` **only** — the 50% decay-carry, NOT the full accumulated funding. Rationale (locked): this past season's contributions already *bought* the current tier perks, which are now grandfathered into facility levels; letting them *also* seed a full Treasury would double-dip (you'd get both the perks and the money that paid for them). Only the normal 50% carry rolls into the starting Treasury, mirroring what the old system already carries season-to-season.
3. Open-projects queue starts **empty**; the first facility vote runs in season 1's Front Office window.
4. Compute initial **Appeal** from the seeded levels → MEGA teams highest → preserves current FA draft ordering at launch.
5. Seed the **share unit** from the just-completed season's faucet (or a sensible constant for the very first run).
6. `funding_tier` is recomputed as a derived **Market** label (fanbase band) thereafter; it no longer gates anything.

**Deploy-resilience:** idempotent (gated flag, skip if `TeamFacility` already seeded), so a redeploy can't double-seed.

## 10. API surface

- Repoint the sim's per-team effect reads (`FUNDING_DEV_BONUS` etc.) from tier-lookup to facility-level-lookup.
- `GET /api/teams/{id}/facilities` — levels, effects, upkeep status, open projects + progress, this-team Appeal.
- `GET /api/league/facilities` — league view (replaces `/api/league/markets`): Appeal ordering, each team's headline facilities.
- `POST /api/teams/{id}/facilities/contribute` — earmark to a specific upkeep bar or open project (replaces/extends the current `/contribute`).
- `GET/POST /api/teams/{id}/facilities/vote` — facility vote ballot + cast (mirror awards/GM endpoints).
- Keep `team_funding_pct` preference (now "season-end deposit %") and surface the season-end waterfall result in the **Season Recap** (closes the original invisibility gap).

## 11. UI surfaces

- **Facilities page** (the mockup: `/tmp/facilities_mockup_v2.html`) — your facilities with upkeep + upgrade progress bars + direct-contribute; available/voted projects with build bars; Season Outlook panel. Costs shown as **progress to next level**, never raw cross-team Floobit totals (so fanbase/income asymmetry stays invisible-but-fair).
- **Vote panel** — Front Office, alongside GM/awards: pick the next project.
- **Season Recap** — "Your team built X / Recovery Center → Lv3 / you contributed Y" so the offseason resolution is finally visible.
- Kill the stale fixed-threshold Help copy; rewrite About/Help around facilities.

## 12. Constants (new, in `constants.py`)

- `FACILITY_TYPES` (catalog + which effect-constant each repoints).
- `FACILITY_LEVEL_COST_SHARES`, `FACILITY_LEVEL_UPKEEP_SHARES` (the §5 curves).
- `FACILITY_EFFECT_BY_LEVEL` per facility (the redesigned finer curves; anchored to current tier perks at the migration levels).
- `FACILITY_MAX_LEVEL = 5`.
- `MIGRATION_TIER_START_LEVEL = {MEGA:4, LARGE:3, MID:2, SMALL:1}`.
- `APPEAL_LEVEL_WEIGHTS` (FA-order weighting).
- Retain `FUNDING_BASELINE_PER_TEAM` (the floor), `team_funding_pct` default.

## 13. Phased build

1. **Data + migration** — tables, the tier→facilities seed, repoint sim effect-reads to facility levels (behavior identical to today at launch since levels reproduce tiers). Ship dark; validate parity with `/simcheck`.
2. **Treasury + direct funding** — earmark contributions to upkeep/projects, progress bars, the season-end waterfall, decay. Validate the economy over N seasons (do whales plateau? mids specialize? bottoms hold the floor?).
3. **Voting** — Front Office facility vote → open-projects queue → offseason construction.
4. **Appeal → FA order** — swap FA draft ordering from `tier_rank` to Appeal.
5. **UI + Recap surfacing** — the Facilities page, vote panel, recap beat; retire the old markets UI + stale copy.

## 14. Decisions & open validation

**Decided:**
- **Upkeep inflation — KEEP.** Share-denominated upkeep on an already-built facility drifts up as the league economy grows; that's intended (keeps the plateau honest). Needs one line of UI explanation.
- **Whale influence — ACCEPT.** Direct funding lets a big spender solo a bar; fine, bounded by the Lv5 ceiling. No per-fan cap.
- **Labels — RESOLVED.** Keep MEGA/LARGE/MID/SMALL_MARKET, repointed at **Market = fanbase size** (§2). **Appeal** is the separate facilities-derived FA-order signal (§6).

**Still to validate (tuning, via `/simcheck`):**
- Effect-per-level curves (anchor to current perks).
- Cost/upkeep share-fractions — where teams plateau over a multi-season sim.
- Does removing the SMALL-market penalty (Lv0 = neutral) over-flatten the competitive spread?
