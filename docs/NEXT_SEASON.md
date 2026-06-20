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

### FA Requisition needs 2 votes but Renewal needs 1 (inconsistent threshold)
Player-reported confusion: Front Office shows "RATIFIED FA Requisition <player> 1/2 votes 50%" while Renewal Endorsements pass at 1/1 100%.
- **Investigated (2026-06-20) — root cause:** `GM_VOTE_BASE_MIN` (constants.py:816) sets a floor of **2** for both `resign_player` and `sign_fa`, but only `sign_fa` actually enforces it. `sign_fa` resolves via `calculateBallotThreshold` (honors the base-min → floor 2); `resign_player`/`cut_player`/`fire_coach` resolve via `calculateThreshold`, which **ignores** `GM_VOTE_BASE_MIN` and hardcodes `max(1, ceil(fanCount × GM_PASS_FRACTION))` → floor **1**. So those vote types' base-mins (resign 2, cut 2, fire 3) are effectively dead, and FA is the lone type that needs 2.
- **Fix options (owner to decide):** (A) make FA consistent — floor `calculateBallotThreshold` at 1 so a small fanbase signs an FA on 1 vote like a re-sign; (B) make them all honor `GM_VOTE_BASE_MIN` (so resign/cut also need 2 — but that makes more things confusing-to-pass, probably not it); (C) keep FA's higher bar (FA signings need broader consensus than re-signing your own guy) and surface a UI note explaining why. Likely **A** or **C**. `gmManager.py:35,58`.

## Shipped (this cycle)
- Card-effect tuning pass (Showoff base card OP) ✅
- Bracket achievement tiers unlock only at Floos-Bowl end (not incrementally) ✅
- Day-end site slowness (synchronous email sending off the hot path) ✅
- Playoffs: team streak/form keep moving; games-played tracks regular season only; round-1 bye fatigue reprieve ✅
- Reactions: pointerdown gesture-gate (phantom-reaction fix) ✅
