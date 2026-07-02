# Next-Season Feature Tracker

> Living list of features targeted for the next season cutover. **Keep this updated as features land** — move items to "Shipped" with the commit/version, and link each in-flight item to its design doc. Owner-curated.

_Last updated: 2026-07-02_

## In progress

_(nothing in flight)_

## Planned

### New prognostication feature — Survivor
A survivor-style contest layer on top of pick-em (last-one-standing elimination), part of the broader prognosticator progression direction.
- **Plan:** `docs/PICKEM_DEPTH_PLAN.md` (survivor contest section)
- **Status:** designed, not built. Build the engagement/progression layer GENERAL (reusable rank/XP hook), not a pick-em silo.

### Idea (undefined) — Awakened / glitched player cards
Tie the anomaly/awakening theme into the card system: when a player awakens (or during a Criticality), some special card variant of them exists. Not yet specced — what it is, how you get one, what it does, cosmetic vs mechanical. Flesh out before building.

## Backlog (owner notes, unspecced — 2026-07-02)
Rough capture; each needs a design pass before building.

- **Rookie card packs** — a pack type themed to the incoming rookie class. The `rookie` classification already exists on card templates; pack types seed in `database/repositories/card_repositories.py::seedDefaults`. Decide name/price/odds and how rookie card supply is scoped (draft class only? tie to the rookie draft?).
- **First iteration of rule changes** — take the rule-mutation layer from tooling to an actual live, Cores-driven rule change in a season. The mutable-rule plumbing already exists (data-driven scoring rules + persisted override layer; mutable `firstDownDistance`/`downsPerSeries`; clock/FG knobs; running-clock rule) — see `docs/SIM_EVOLUTION.md` and the `Rule mutation:` commits. Pick the FIRST rule to actually change, how it's triggered (Cores?), and how it's surfaced to players (the "current rules" UI foreshadowing).
- **New attention sources** — expand what feeds player "attention" beyond the current four (equipped cards, fantasy roster slots, follows, favorite-team fans; all in `anomalyManager._applyWeeklyContributions`). Brainstorm additional user-driven signals so attention concentration has more inputs (keeps it user-generated, not sim-driven).

## Bugs / smaller fixes
- **Showcase dividend rate balance pass** — `SHOWCASE_DIVIDEND_RATE` (0.13) was a calibrated starting point (sustained S ≈ the old ~3000 lump/season, top end uncapped); still wants an owner balance pass.

## Shipped (this cycle)
- **Team Markets → Facilities rework** ✅ — fan-funded, fan-voted Facilities (Market = fanbase / Treasury = money / Facilities = built perks driving Appeal → FA order); live-wired funding, contribution achievements (Patron/Benefactor/Underwriter), fully-funded projects build immediately mid-season. Merged via `03bb474`. Plan: `docs/MARKETS_FACILITIES_PLAN.md`.
- **Sim Evolution — Layer 4 (Criticality)** ✅ — awakened powers + the league-wide Criticality fire framework; event paced to ~1/season, uncapped suppressions, `criticality_enabled` admin toggle drives the whole event. Merged via `a690f87`/`6e1e1d1`. Plan: `docs/AWAKENED_POWERS_PLAN.md`.
- **Card Vault + Showcase** ✅ — permanent Vault (trash/reorder/team-sort, vault-aware Level Up + equip exclusion), Showcase weekly-dividend payout + per-card scoring transparency + sets paytable. Merged via `fdc8a6f`/`763daf8`. (Dividend rate balance pass still open — see Bugs.)
- Card-effect tuning pass (Showoff base card OP) ✅
- Bracket achievement tiers unlock only at Floos-Bowl end (not incrementally) ✅
- Day-end site slowness (synchronous email sending off the hot path) ✅
- Playoffs: team streak/form keep moving; games-played tracks regular season only; round-1 bye fatigue reprieve ✅
- Reactions: pointerdown gesture-gate (phantom-reaction fix) ✅
- Front Office: FA Requisition reworked — **thresholdless ranked-choice** (any ballots resolve via IRV to the most-wanted available targets; no probability roll, no pass/fail). Front Office shows the ranked **priority target list**, not a "RATIFIED X/Y votes %" tally. Makes the old floor-2-vs-1 concern moot (no threshold at all). ✅ (backend `ac36be7`, frontend `afebc8a`)
- FA Requisition — **position fill-priority** (next-season worktree, uncommitted): new optional `position_priority` on the FA ballot — fans drag-rank all 5 positions (QB/RB/WR/TE/K) for which slot to fill FIRST once voted players run out. Borda-aggregated per team (`gmManager._aggregatePositionPriorities`), consumed by `playerManager._attemptRosterFill` to OVERRIDE best-rated in the fallback (so a team that ranked QB/WR above K won't auto-grab a higher-rated kicker). New `gm_fa_ballots.position_priority` column + migration; `resolveSignFaVotes` now returns a 3-tuple; resolved order surfaced as `faPositionPriority`. UI: a "Set fill priority" toggle + reorder rows in `FaBallotModal`. Full ranked voted list already shown ("Free Agent Vote Tallies" in the FO). Validated via simcheck (rosters 6/6, best-available fallback unchanged with no ballots). ✅
