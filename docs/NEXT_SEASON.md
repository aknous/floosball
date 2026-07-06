# Next-Season Feature Tracker

> Living list of features targeted for the next season cutover. **Keep this updated as features land** — move items to "Shipped" with the commit/version, and link each in-flight item to its design doc. Owner-curated.

_Last updated: 2026-07-06_

## In progress

_(nothing in flight)_

## Planned

### League parity package — star scarcity + salary cap (design locked 2026-07-06)
The league is top-heavy (Cranes ~26-2, 80% titles in S13 sims, 3 of last 4 Floos Bowls). Two roots: **star oversupply** (of ~245 live players, **40% are 4-5★** vs a healthy ~15-20%; pool centered at rating 81) and **concentration** (Cranes hold the best 6). In-game compression (`LEAGUE_COMPRESSION_FACTOR`) was tested at 0.7/0.6/0.5 and **rejected** — barely moved the Cranes, only lowered scoring; concentration, not per-player gap, is the driver. Three complementary levers, all **between-season (at the rollover), never in-season**:
1. **Fix the creep at the source** — generation seed `normal(78,7)` → ~`normal(74,8)` (lower/wider; rookies avg 79.5 is too high) + flatten development rise `DEV_RISE_RANGE (-1,5)` → `(-2,3)`. Target ~15-20% 4-5★.
2. **One-time rank-preserving percentile re-map** of the current pool onto the target distribution (#1 stays #1, fewer qualify as 4-5★) so there's no multi-season two-era transition. Owner-agreed. Between-season timing insulates owned cards (templates mint rating at season creation).
3. **Salary cap — model B**: salary = star tier **locked at signing** (`cap_hit` column already exists/populated; today it's recomputed live = model A). Cheap rookies → expensive at re-sign. Cap **~24** / floor **~19** (calibrated to the 15-27/avg-22 team-salary spread). Offseason-enforced; unmanaged teams auto-shed/sign via the existing FA logic.
- **Build order:** distribution (1+2) first + multi-season sim to confirm the star %, then the cap (3) on top. Full design + measurements: memory `league-parity-rebalance`.
- **Status:** design locked, not built.

### New prognostication feature — Survivor
A survivor-style contest layer on top of pick-em (last-one-standing elimination), part of the broader prognosticator progression direction.
- **Plan:** `docs/PICKEM_DEPTH_PLAN.md` (survivor contest section)
- **Status:** designed, not built. Build the engagement/progression layer GENERAL (reusable rank/XP hook), not a pick-em silo.

### Idea (undefined) — Awakened / glitched player cards
Tie the anomaly/awakening theme into the card system: when a player awakens (or during a Criticality), some special card variant of them exists. Not yet specced — what it is, how you get one, what it does, cosmetic vs mechanical. Flesh out before building.

## Backlog (owner notes, unspecced — 2026-07-02)
Rough capture; each needs a design pass before building.

- **First iteration of rule changes** — take the rule-mutation layer from tooling to an actual live, Cores-driven rule change in a season. The mutable-rule plumbing already exists (data-driven scoring rules + persisted override layer; mutable `firstDownDistance`/`downsPerSeries`; clock/FG knobs; running-clock rule) — see `docs/SIM_EVOLUTION.md` and the `Rule mutation:` commits. Pick the FIRST rule to actually change, how it's triggered (Cores?), and how it's surfaced to players (the "current rules" UI foreshadowing).
- **New attention sources** — expand what feeds player "attention" beyond the current four (equipped cards, fantasy roster slots, follows, favorite-team fans; all in `anomalyManager._applyWeeklyContributions`). Brainstorm additional user-driven signals so attention concentration has more inputs (keeps it user-generated, not sim-driven).

## Bugs / smaller fixes
- **Showcase dividend rate balance pass** — `SHOWCASE_DIVIDEND_RATE` (0.13) was a calibrated starting point (sustained S ≈ the old ~3000 lump/season, top end uncapped); still wants an owner balance pass.

## Shipped (this cycle)
- **Playbook diversification** ✅ — a real offensive playbook layered on the sim: run concepts (power/draw/counter/sweep) with deception + execution rolls, gap coherence, and defensive counter-adaptation; play-action; route concepts (mesh/flood/screen vs coverage); RPO (QB reads the box pre-snap); trick plays (flea flicker / statue / reverse) as rare called shots. Coach-gated (aggressiveness = experimental adoption / offensiveMind = standard sophistication), situationally aware, balance-measured (concept ON/OFF for inflation), self-describing PBP with the scheme detail in the Play Insights "Play Design" row. Commits `a3e92ef`…`5c7d077`. Plan: `docs/PLAYBOOK_PLAN.md`. (Tuning `5c7d077`: flood out of PBP → insights only; trick plays cut to ~3.4/team/season from ~42.)
- **Coaching / play-calling depth** ✅ — gameplan wiring made real: `runPassRatio` + a master gameplan switch, situational pass-depth quick-game lever, adaptable coaches re-plan mid-game (not just at halftime), and a Q4 lead-protection floor so every team runs the clock better with a lead. Commits `67e60f3`/`dd03fef`/`6d93c2f`/`20b75ea`.
- **Clock / kneel / FG fixes** ✅ — score before the half + never let a scoring snap die with timeouts; kneel rules (no 4th-down kneel, no draining a stopped clock); cap awakened-kicker range; PBP: a diving catch no longer also stretches for the marker. Commits `deb11ee`/`26328c9`/`6c69afb`/`0c5cb25`/`1cab194`.
- **HoF: never induct an active player** ✅ — a ballot candidate whose `willRetire` was cleared after seeding (longevity retune / re-signed in FA) can no longer be enshrined while rostered; induction guards on actual retirement and drops stale candidates, with reactivation if they later retire for real. Regression `test_hof_active_guard.py`. Commit `445350d`. (Prod records for Chili Arthur / Briam Flumpton repaired.)
- **Rookie Pack** ✅ — a themed card pack for the current draft class (`is_rookie` templates), rotating in the shop. Commit `d9c3819`.
- **Rulebook backend** ✅ — `GET /api/rules` surfacing the current ruleset (foreshadowing the rule-mutation layer). Merged `a8844ce`.
- **Team Markets → Facilities rework** ✅ — fan-funded, fan-voted Facilities (Market = fanbase / Treasury = money / Facilities = built perks driving Appeal → FA order); live-wired funding, contribution achievements (Patron/Benefactor/Underwriter), fully-funded projects build immediately mid-season. Merged via `03bb474`. Plan: `docs/MARKETS_FACILITIES_PLAN.md`.
- **Sim Evolution — Layer 4 (Criticality)** ✅ — awakened powers + the league-wide Criticality fire framework; event paced to ~1/season, uncapped suppressions, `criticality_enabled` admin toggle drives the whole event. Merged via `a690f87`/`6e1e1d1`. Plan: `docs/AWAKENED_POWERS_PLAN.md`.
- **Card Vault + Showcase** ✅ — permanent Vault (trash/reorder/team-sort, vault-aware Level Up + equip exclusion), Showcase weekly-dividend payout + per-card scoring transparency + sets paytable. Merged via `fdc8a6f`/`763daf8`. (Dividend rate balance pass still open — see Bugs.)
- Card-effect tuning pass (Showoff base card OP) ✅
- Bracket achievement tiers unlock only at Floos-Bowl end (not incrementally) ✅
- Day-end site slowness (synchronous email sending off the hot path) ✅
- Playoffs: team streak/form keep moving; games-played tracks regular season only; round-1 bye fatigue reprieve ✅
- Reactions: pointerdown gesture-gate (phantom-reaction fix) ✅
- Front Office: FA Requisition reworked — **thresholdless ranked-choice** (any ballots resolve via IRV to the most-wanted available targets; no probability roll, no pass/fail). Front Office shows the ranked **priority target list**, not a "RATIFIED X/Y votes %" tally. Makes the old floor-2-vs-1 concern moot (no threshold at all). ✅ (backend `ac36be7`, frontend `afebc8a`)
- FA Requisition — **position fill-priority** ✅ (committed `ee47fdc`): new optional `position_priority` on the FA ballot — fans drag-rank all 5 positions (QB/RB/WR/TE/K) for which slot to fill FIRST once voted players run out. Borda-aggregated per team (`gmManager._aggregatePositionPriorities`), consumed by `playerManager._attemptRosterFill` to OVERRIDE best-rated in the fallback (so a team that ranked QB/WR above K won't auto-grab a higher-rated kicker). New `gm_fa_ballots.position_priority` column + migration; `resolveSignFaVotes` now returns a 3-tuple; resolved order surfaced as `faPositionPriority`. UI: a "Set fill priority" toggle + reorder rows in `FaBallotModal`. Full ranked voted list already shown ("Free Agent Vote Tallies" in the FO). Validated via simcheck (rosters 6/6, best-available fallback unchanged with no ballots). ✅
