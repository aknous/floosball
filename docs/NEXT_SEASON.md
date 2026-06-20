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

### Card Vault / Showcase — retuning + documentation
The Showcase shipped (payouts fire). Retune the grade/payout curves + set bonuses, build/finish the permanent **Vault**, and write proper documentation (no canonical doc yet beyond the plan).
- **Plan:** `docs/COLLECTIBLE_CARDS_PLAN.md` (+ memory: card_collection_vault_showcase)
- **Status:** Showcase live; Vault + retune + docs pending. Also surfacing gap — players don't see their season-end Showcase payout (buried by the season-end tax).

### New prognostication feature — Survivor
A survivor-style contest layer on top of pick-em (last-one-standing elimination), part of the broader prognosticator progression direction.
- **Plan:** `docs/PICKEM_DEPTH_PLAN.md` (survivor contest section)
- **Status:** designed, not built. Build the engagement/progression layer GENERAL (reusable rank/XP hook), not a pick-em silo.

## Shipped (this cycle)
- Card-effect tuning pass (Showoff base card OP) ✅
- Bracket achievement tiers unlock only at Floos-Bowl end (not incrementally) ✅
- Day-end site slowness (synchronous email sending off the hot path) ✅
- Playoffs: team streak/form keep moving; games-played tracks regular season only; round-1 bye fatigue reprieve ✅
- Reactions: pointerdown gesture-gate (phantom-reaction fix) ✅
