# Wildcard Transplant — every player, any effect

**Status:** design settled, not started
**Owner direction:** 2026-08-16

## The problem

A card is one atom: **player × effect**, and a pack pull has to win both at once. A user
who wants Battering Ram on *their* running back has to pull that exact pair. Transplant
helps — it moves an effect between cards — but it requires **same edition** and both cards
must already bear an effect, so it only rearranges what you already hold. Reported as: it
is hard to get the players you want with the effects you want.

The two axes of scarcity are welded together, and only one of them is interesting. Effect
scarcity is the game. Player scarcity is friction.

## The mechanic

1. **Every player's base card is available from the start of the season.** Users build a
   roster the way the original fantasy implementation worked — pick the players, field
   them for their raw FP.
2. **A base card is a wildcard in the transplant.** It can receive any effect, from any
   edition, regardless of the depicted player's rating.
3. **The effect is copied onto the base card. No new card is minted at the donor's
   edition.** The card stays `base`; the donor is consumed as it is today.
4. **The power bar comes with the effect.** A prismatic effect brings prismatic strength
   and the prismatic bar wherever it lands — you get a *simulated* effect, identical in
   play to the real card.
5. **Gated by a consumable**, purchasable from the shop with limited daily availability,
   and also granted as an achievement reward.
6. **No `champion` / `all_pro` / `mvp` classification is ever applied** to a card built
   this way.

## What the codebase already gives us

⚠️ **Half of this already exists and is simply not distributed.** `_assignEffects` mints
one `base` template per player every season — measured on a fresh database, **192 base
templates against 192 non-prospect players**. Floor prints already equip and already score
the depicted player's raw FP; `_provisionStarterPack` just hands out five of them.

So "every player's base card from season start" is a **distribution** change, not a minting
one. The templates are there.

Transplant is likewise built (`cardManager.transplantEffect`, `POST /api/cards/transplant`,
`TRANSPLANT_COST_BY_EDITION`, `test_transplant.py`). The rules it currently enforces, and
what a wildcard does to each:

| current rule | wildcard |
|---|---|
| same edition | **lifted** for a base target |
| both cards effect-bearing | **lifted** — the base card is the point |
| not already the same effect | keep |
| position-valid for the effect | **keep** — a WR-only effect still needs a WR |
| donor must be current-season | **keep** — this is what stops a retired effect re-entering play |

## ⚠️ The one real design decision: edition is doing two jobs

Edition is not a label. It is simultaneously:

- the card's **collectible identity** — sell value, Showcase points, rating eligibility;
- the effect's **balance tier** — `EDITION_POWER_SCALE` and the height of the power bar.

Minting a pulled effect onto a base card naively takes BOTH from `base`, and base sits in
the wrong place on both dials. Measured:

| effect | home edition | strength if minted at base | bar |
|---|---|---|---|
| Anthem | prismatic | **1.93x** | 13 → 9 |
| Stacked Deck | diamond | **1.91x** | 15 → 9 |
| All In | prismatic | **1.79x** | 13 → 9 |
| Metronome | prismatic | **1.74x** | 13 → 9 |
| Diversified | holographic | 0.72x | 10 → 8 |
| Freebie | metallic | 0.91x | 9 → 9 |

`EDITION_POWER_SCALE` is `base 1.0 · metallic 1.10 · holographic 1.70 · prismatic 0.70 ·
diamond 1.0` — prismatic is the **lowest dial in the set**, so minting a prismatic effect
at base scale nearly doubles it. And `CARD_GATE_FP_THRESHOLDS_BY_EDITION` has **no base
row**, so it falls back to the metallic bar, the lowest: a diamond effect would unlock at
9 FP instead of 15.

Left alone, the wildcard is **strictly stronger than a real prismatic or diamond pull** —
roughly double output on an easier bar — and weaker than a real holographic one. The
convenience path becomes the power path for exactly the two tiers that should be hardest
to reach.

### The split

**The card's edition and the effect's tier are separate inputs.**

- The **card** stays `base`. Sell value 2, **0 Showcase points** (base is absent from
  `SHOWCASE_EDITION_POINTS`, so this needs no new rule), no classifications, no rating
  gate to collapse.
- The **effect** keeps its own tier for `EDITION_POWER_SCALE` and `buildGateSpec`.

⚠️ **The donor's edition never needs to be tracked.** `EFFECT_EDITION_TIER[effectName]`
already declares where an effect belongs. A prismatic effect is prismatic wherever it
lands, and that single lookup drives both the strength and the bar.

The resulting relationship is the one we want:

> A wildcard build is **exactly equal in play** and **strictly worse in collection** than
> the real pull. You pay a consumable for convenience, never for power.

Genuine pulls keep a permanent edge that has nothing to do with strength: they are the
only cards worth collecting, the only ones that can carry an accolade, and the only ones
that score in the Vault.

### ⚠️ The stat-ladder family is already immune

The ~27 stat-ladder cards are anchored per rung by construction and bypass
`EDITION_POWER_SCALE` entirely — Dominion measures 1.00x at base. Only the bar needs
handling for them. Do not "fix" their scale; there is nothing to fix.

## What this does NOT open

⚠️ **This is a path to any PLAYER, not to any EFFECT.** The transplant still consumes a
donor you had to pull, so effect scarcity is untouched. Concretely: nothing rates 90 at QB
or K, so no diamond QB or K card can be minted, so no such donor can exist, so those 27
diamond effects stay unreachable. That is consistent with the stated goal and worth being
explicit about — a user who reads "any effect on any player" will otherwise go looking.

## The consumable

Not free, not unlimited. Shop-purchasable with **1-3 available per day**, plus achievement
grants.

Pricing anchors, measured on production user-weeks (seasons 12+):

| | Floobits |
|---|---|
| median user-week | **84** |
| p90 user-week | **363** |
| p99 user-week (post-knee) | **702** |
| existing transplant cost | 40 / 70 / 120 / 180 by edition |
| Accession, the priciest powerup | 200, limit 2/season |

At 1-3/day availability, a consumable much above **~200 F** is roughly one build a week
for a typical player. **Open:** does the consumable replace the existing
`TRANSPLANT_COST_BY_EDITION` charge or stack on top of it? Stacking makes a diamond
wildcard 380 F, which is more than four median weeks.

It should live in `POWERUP_CATALOG` beside Accession and Annulment, and the daily
availability wants its own rotation slot rather than riding
`ROTATION_CATEGORY_WEIGHTS`, which rotates *pack* categories.

## Second-order effects to decide before building

1. **Hand-composition cards get more reliable.** Assembling a specific seven-effect hand
   becomes much easier, which strengthens Diversified, Anthem, Stacked Deck, Chain
   Reaction and Fortitude. ⚠️ Diversified was resized on **2026-08-16** against a
   semi-random hand — measured 63% of hands holding all three output types, mean 2.61 —
   and it pays a COUNT, so wildcards push it toward its ceiling every week. Re-measure the
   cross family once wildcards exist; that resize is the first thing this invalidates.
2. **Effect-supply guarantees get routed around.** `_assignEffects` deliberately mints one
   template per effect where a bucket has fewer players than effects, so every effect
   exists somewhere. Wildcards let a user ignore bucket scarcity entirely. Not a bug —
   but the coverage guarantee stops being what limits access.
3. **The no-duplicate-effect equip rule becomes the real constraint** on hand building,
   where today it is player availability. Worth confirming that is the intended shape.
4. **Visual identity.** A base-edition card carrying a diamond effect renders with floor
   print styling. Is that the desired read ("this is a build, not a pull") or does the
   wildcard want a mark of its own? Leaning toward the former — it is honest and free.
5. **Vault.** A wildcard can be vaulted like anything else, and scores 0 edition points.
   Confirm that is intended rather than a bug someone reports later.

## Build order

1. Distribute base cards — grant or make acquirable all 192. Templates already exist.
2. Split edition-as-identity from effect-tier in `buildEffectConfig` / `buildGateSpec`,
   driven by `EFFECT_EDITION_TIER`. **This is the load-bearing change**; do it first and
   measure it against the table above before any UI exists.
3. Lift the transplant's same-edition and both-effect-bearing rules for a base target.
   Keep position validity and the current-season donor gate.
4. The consumable: catalog entry, daily shop availability, achievement reward hook.
5. Suppress classifications on the wildcard path.
6. Re-measure the cross-card family (item 1 above).

## Regression targets

- A wildcard-built prismatic effect scores **identically** to the real prismatic card, same
  bar, same params. This is the whole design in one assertion.
- A wildcard card sells for 2 and scores 0 Showcase points.
- No wildcard card ever carries `champion` / `all_pro` / `mvp`.
- Position validity still refused (no WR-only effect on a QB base card).
- An expired donor is still refused.
