# Next-Season Feature Tracker

> Living list of features targeted for the next season cutover. **Keep this updated as features land** — move items to "Shipped" with the commit/version, and link each in-flight item to its design doc. Owner-curated.

_Last updated: 2026-06-19_

## In progress

### Team Markets rework (Markets → Facilities)
Replace the passive market-tier perks with a fan-funded, fan-voted **Facilities** system (Market = fanbase / Treasury = money / Facilities = what's built, driving Appeal → FA order).
- **Plan:** `docs/MARKETS_FACILITIES_PLAN.md`
- **Branch:** `feature/facilities` (off `next-season`)
- **Status:** Phase 1 (data model + grandfather migration + repointed sim effects) ✅; Appeal→FA-order (preserves tier order) ✅; Phase 2 engine (treasury, share costs, waterfall) built + harness-validated, **not yet live-wired**.
- **Remaining:** funding wiring (Treasury seed from 50% carry + contributions + live season-end waterfall) → voting (Phase 3) → Market-from-fan-count → UI (Facilities page, vote panel, recap).

## Planned

### Sim Evolution — Layer 4 (Criticality) completion
Finish the awakened-powers / league-wide Criticality event (the gated "Cores lose control" payoff). The buildup + lower layers exist; L4 is the actual fire.
- **Plan:** `docs/AWAKENED_POWERS_PLAN.md` (+ memory: criticality event design, sim_evolution_anomaly)
- **Status:** designed/locked, gated; L4 fire framework to build in `floosball_game.py`.
- **Idea (undefined, 2026-06-19):** *Awakened / glitched player cards* — tie the anomaly/awakening theme into the card system. When a player awakens (or during a Criticality), some special card variant of them exists. Not yet specced — what it is, how you get one, what it does, whether it's cosmetic vs mechanical. Flesh out before building.

### Card Vault / Showcase — retuning + documentation
The Showcase shipped (payouts fire). Retune the grade/payout curves + set bonuses, build/finish the permanent **Vault**, and write proper documentation (no canonical doc yet beyond the plan).
- **Plan:** `docs/COLLECTIBLE_CARDS_PLAN.md` (+ memory: card_collection_vault_showcase)
- **Status:** Showcase live; Vault + retune + docs pending.
- **Payout method change (2026-06-20):** ✅ DONE (branch `next-season`, in worktree). The lump sum is gone — the showcase now pays a **weekly dividend** = `round(SHOWCASE_DIVIDEND_RATE × finalScore)` every regular-season week, re-graded live off the current showcase. New `showcase_dividend` transaction type (durable record + a weekly notification, parity with the FP earnings), idempotent per (season, week). Paid in `seasonManager._awardShowcaseDividends` from `_onWeekComplete`; the season-end `_awardShowcasePayouts` call is removed. `showcaseManager.awardWeeklyDividends` replaces `awardSeasonPayouts`. Rate `0.13` is a STARTING point calibrated so a sustained S ≈ the old 3000 lump across a season (top end now uncapped) — **needs an owner balance pass** (note: an F-grade token showcase now pays ~1F/wk instead of a hard 0). `test_showcase_payout.py` updated + green.
- **Scoring transparency (2026-06-20):** ✅ DONE (same branch). `showcaseManager.evaluate` now returns a per-card breakdown (edition pts, classification pts, recency ×, tier ×, base points, and each card's **Floobit share** of the weekly dividend) + the set-bonus multiplier + base/final score. The API surfaces it (no longer strips the score): `_buildShowcasePayload` attaches each card's breakdown to its slot; payloads return `weeklyDividend` + `setBonus`. Frontend `ShowcaseView` shows a `+X/wk` pill under each featured card with a hover breakdown, plus a "sets +N%" header line; the season-end result modal became a "earned X across N weeks" wrap (`showcase/last-result` now sums the latest completed season's dividends). **Sets paytable:** `evaluate` returns the full `sets` catalog (every set with live active/almost/locked status, base bonus, requirement, realized bonus) + `maxSetBonus`; a `SetsPaytable` panel on the showcase lists all 7 sets and how each scores.

### New prognostication feature — Survivor
A survivor-style contest layer on top of pick-em (last-one-standing elimination), part of the broader prognosticator progression direction.
- **Plan:** `docs/PICKEM_DEPTH_PLAN.md` (survivor contest section)
- **Status:** designed, not built. Build the engagement/progression layer GENERAL (reusable rank/XP hook), not a pick-em silo.

## Bugs / smaller fixes

## Shipped (this cycle)
- Card-effect tuning pass (Showoff base card OP) ✅
- Bracket achievement tiers unlock only at Floos-Bowl end (not incrementally) ✅
- Day-end site slowness (synchronous email sending off the hot path) ✅
- Playoffs: team streak/form keep moving; games-played tracks regular season only; round-1 bye fatigue reprieve ✅
- Reactions: pointerdown gesture-gate (phantom-reaction fix) ✅
- Front Office: FA Requisition reworked — **thresholdless ranked-choice** (any ballots resolve via IRV to the most-wanted available targets; no probability roll, no pass/fail). Front Office shows the ranked **priority target list**, not a "RATIFIED X/Y votes %" tally. Makes the old floor-2-vs-1 concern moot (no threshold at all). ✅ (backend `ac36be7`, frontend `afebc8a`)
- FA Requisition — **position fill-priority** (next-season worktree, uncommitted): new optional `position_priority` on the FA ballot — fans drag-rank all 5 positions (QB/RB/WR/TE/K) for which slot to fill FIRST once voted players run out. Borda-aggregated per team (`gmManager._aggregatePositionPriorities`), consumed by `playerManager._attemptRosterFill` to OVERRIDE best-rated in the fallback (so a team that ranked QB/WR above K won't auto-grab a higher-rated kicker). New `gm_fa_ballots.position_priority` column + migration; `resolveSignFaVotes` now returns a 3-tuple; resolved order surfaced as `faPositionPriority`. UI: a "Set fill priority" toggle + reorder rows in `FaBallotModal`. Full ranked voted list already shown ("Free Agent Vote Tallies" in the FO). Validated via simcheck (rosters 6/6, best-available fallback unchanged with no ballots). ✅
