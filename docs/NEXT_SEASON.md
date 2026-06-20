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
- **Payout method change (2026-06-20):** switch from the **end-of-season lump sum → a WEEKLY DIVIDEND** scaled by the showcase score. Also fixes the surfacing gap — the lump sum was invisible (buried a half-second before the season-end tax, no durable record); a weekly dividend is visible income all season. Implies the score is evaluated/paid each week (recompute cadence + a weekly currency grant), not once at season end.
- **Scoring transparency (2026-06-20):** users complain the score is **opaque** — no way to see *why* they got it or how points are derived (per-card contribution, recency decay, edition/classification weights, active set bonuses). Need a visible breakdown: each featured card's point contribution + the multipliers applied. The scoring math already exists (`showcaseManager.evaluate`); the gap is surfacing it (the API deliberately strips the raw score today — that needs to change to a transparent per-card breakdown).

### New prognostication feature — Survivor
A survivor-style contest layer on top of pick-em (last-one-standing elimination), part of the broader prognosticator progression direction.
- **Plan:** `docs/PICKEM_DEPTH_PLAN.md` (survivor contest section)
- **Status:** designed, not built. Build the engagement/progression layer GENERAL (reusable rank/XP hook), not a pick-em silo.

## Bugs / smaller fixes

### FA Requisition vote reads as "passed below threshold" (paradigm + threshold inconsistency)
Player-reported confusion: Front Office shows "RATIFIED FA Requisition <player> **1/2 votes 50%**" — it *passed* despite showing below the bar — while Renewal Endorsements pass at 1/1 100%. Two distinct root causes, both real:
- **Investigated (2026-06-20):**
  1. **FA resolves by a PROBABILITY ROLL, not a deterministic threshold.** `resolveSignFaVotes` (`gmManager.py:440`): `probability = totalBallots/threshold` (1/2 = 0.5), then `_rollSuccess(0.5)` — a 50% coin flip. The roll *hit*, so it ratified. Renewals/cut/fire are **deterministic** (`net ≥ threshold` passes, else fails); hire is **plurality**. Three paradigms, all rendered with the same "X/Y votes Z%" string, so a 50%-chance-that-happened-to-hit looks like "passed with half the votes."
  2. **Threshold floor mismatch.** `GM_VOTE_BASE_MIN` (constants.py:816) declares a floor of 2 for resign+FA, but only `sign_fa` (via `calculateBallotThreshold`) enforces it; resign/cut/fire (via `calculateThreshold`) ignore it and floor at `max(1, …)` = 1. So FA needs 2, renew needs 1.
- **Fix options (owner to decide):** the bigger fix is the *display/paradigm* — either (A) make FA deterministic too (sign the ranked leader iff ballots ≥ threshold; no roll) so "X/Y Z%" means the same everywhere; or (B) keep the roll but render FA's % unmistakably as a *chance* ("50% chance to sign"), visually distinct from the deterministic progress bars. Plus decide the floor (FA 2 vs 1) for consistency. `gmManager.py:35,58,440`.

## Shipped (this cycle)
- Card-effect tuning pass (Showoff base card OP) ✅
- Bracket achievement tiers unlock only at Floos-Bowl end (not incrementally) ✅
- Day-end site slowness (synchronous email sending off the hot path) ✅
- Playoffs: team streak/form keep moving; games-played tracks regular season only; round-1 bye fatigue reprieve ✅
- Reactions: pointerdown gesture-gate (phantom-reaction fix) ✅
