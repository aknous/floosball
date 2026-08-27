# Synthetic Cards — every player, any effect

**Status:** design settled, not started. **Priority 1 for next season** (owner, 2026-08-26).
**Owner direction:** 2026-08-16, extended 2026-08-26.

> **Renamed 2026-08-26** from "Wildcard Transplant" (owner's word is **synthetic card**).
> The old name described the mechanism; this one describes the object, which is what a
> user sees. A synthetic card is a real player, a real effect, and a manufactured pairing.

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
2. **A base card is a wildcard in the transplant** — the mechanism that mints a synthetic. It can receive any effect, from any
   edition, regardless of the depicted player's rating.
3. **The effect is copied onto the base card and the donor is consumed**, as transplant
   already works. ⚠️ ~~The card stays `base`.~~ **Ruling 8 (below) overrides this**: the
   minted card takes the EFFECT's edition. It is not a card at the donor's edition — it
   is a card at the effect's — and the difference is that no collectible identity comes
   with it.
4. **The power bar comes with the effect.** A prismatic effect brings prismatic strength
   and the prismatic bar wherever it lands — you get a *simulated* effect, identical in
   play to the real card.
5. **Gated by a consumable**, purchasable from the shop with limited daily availability,
   and also granted as an achievement reward.
6. **No `champion` / `all_pro` / `mvp` classification is ever applied** to a card built
   this way.

## ⚠️ Owner rulings, 2026-08-26 — a synthetic card is FANTASY ONLY

1. **Every player is available as a base card** to equip in a card roster. As below, this
   is distribution, not minting.
2. **Any effect can be grafted onto one**, at the price of the existing transplant cost
   PLUS a new consumable.
3. **A synthetic cannot be vaulted, and sells for 1.** Usable in fantasy and nowhere else.
   (0 was the original ruling; 1 was allowed as the simpler build, and turns out to be
   safer too — see below.)
4. **It cannot be used in the Combine**, because its value is nil.
5. **It CAN donate its effect** in a transplant.
6. **It can never RECEIVE an effect.** A base card takes an effect exactly once, at the
   moment it becomes synthetic; after that the pairing is fixed. So a synthetic is a
   transplant **donor only, never a target**.
7. **It can be tier-upgraded.**
8. ⚠️ **It behaves as the edition the EFFECT came from** — that edition's power scale and
   that edition's gate threshold. Visually it wears that edition's color, **muted** to set
   it apart from the real print, and is labeled **SNTH**.

### ⚠️ Ruling 8 DELETES the load-bearing change this plan was built around

The section below spends its length on "edition is doing two jobs, and they must be
split." **Ruling 8 dissolves that problem instead of solving it.** Stamp the template's
`edition` as the EFFECT's home edition (`EFFECT_EDITION_TIER[effectName]`, which already
declares it) and four separate things come out right with no new code at all:

| reads `template.edition` | outcome |
|---|---|
| `EDITION_POWER_SCALE` (`cardEffectCalculator:709`) | prismatic effect gets prismatic strength ✓ |
| `CARD_GATE_FP_THRESHOLDS_BY_EDITION` (`:809`) | the missing-base-row fallback never happens ✓ |
| `_tierUpgradeCost` (`cardManager:1491`) | ruling 7 is priced off the effect, not off base ✓ |
| `serializeCard` → the client (`:1026`) | the frontend colors it by edition already ✓ |

⚠️ **This also closes the cheapest-tier-bonus hole on its own.** The earlier draft flagged
tier upgrades as a discount on power, because base is the cheapest rung in
`CARD_TIER_EDITION_COST_MULT`. Under ruling 8 there is no base rung involved — a synthetic
prismatic is charged the prismatic tier price. Ruling 7 needs no separate guard.

**So build step 2 (splitting edition-as-identity from effect-tier) is struck.** What
replaces it is one assignment at the mint site plus the value guards below.

### ⚠️ But it INVERTS which side needs guarding, and the flag is now MANDATORY

The old design was safe on value (base is worth nothing) and wrong on power. Ruling 8 is
right on power and now **over-values a synthetic everywhere value is read from edition**:

| site | what it now does | guard |
|---|---|---|
| `getSellValue` via `sellCards:1113` | sells at the effect edition's price | force 1 |
| `getSellValue` via `serializeCard:842` | displays that price to the user | force 1 (same branch) |
| `getCardValue:379` (Combine fuel) | worth a real prismatic as fuel | ruling 4's refusal, **plus** the forced 1 as a backstop |
| `SHOWCASE_EDITION_POINTS` (`showcaseManager:99`) | 12 points for a prismatic | ruling 3's vault refusal |

⚠️ **`is_synthetic` IS NO LONGER OPTIONAL.** The earlier draft noted the predicate was
derivable — `edition == 'base'` plus a non-empty effect — and recommended a column anyway
for safety. **Ruling 8 kills the predicate outright**, because a synthetic is not `base`
any more. Nothing whatsoever distinguishes a synthetic prismatic from a pulled prismatic
except a stored flag. `card_templates.is_showpiece` is the precedent and the exact mirror:

| | can be equipped | can be collected |
|---|---|---|
| `is_showpiece` | **no** | yes |
| `is_synthetic` | yes | **no** |

⚠️ **RULING 4'S REFUSAL IS LOAD-BEARING, NOT COSMETIC.** "It can't be used in the Combine
since its value is 0" is the intent; under ruling 8 the code would say its value is 12 or
30. Without an explicit refusal in `blendCards` the synthetic becomes the cheapest
Combine fuel in the game — build a synthetic diamond, feed it as diamond-grade fuel. The
refusal is what makes the stated reason true.

### Selling for 1, and why 1 is better than 0 (owner, 2026-08-26)

Ruling 3 gives disposal for free — no new trash endpoint, `sellCards` already deletes the
row. The owner allowed **1** rather than 0 if it is simpler, and it is, in two ways.

**It is two lines instead of a branch.** Selling for 0 hits two traps: `getCardValue` ends
in `max(1, …)` so 0 is unreachable through the normal path, and a 0-Floobit payout must
skip `addFunds` entirely (this codebase already paid for that once — the free daily shop
reroll had to branch on `cost > 0`, because granting 0 still writes a ledger row and fires
the Magnate achievement for a purchase that never happened). At 1 both traps vanish:
`getSellValue(edition, isActive, isSynthetic=False)` returns 1 for a synthetic, and every
existing caller is already correct.

⚠️ Return **1 directly**, not 0-and-let-the-floor-round-it-up. The floor lives in
`sellCards:1113` and in `getCardValue`, but **`serializeCard:842` has no floor** — so a 0
would display "sells for 0" beside a sale that actually pays 1.

**⚠️ AND IT MAKES THE COMBINE REFUSAL FAIL-SAFE INSTEAD OF FAIL-OPEN.** This is the better
reason. `getCardValue` derives Combine fuel value from `getSellValue`, so under ruling 8 a
synthetic diamond would be worth **30** as fuel if the refusal were ever missed or removed.
At a sell value of 1 it is worth 1. The explicit refusal in `blendCards` still ships — it
is what makes the stated reason ("its value is 0") true to a user — but the economic damage
if it lapses goes from *cheapest diamond fuel in the game* to *nothing*. One number is now
doing the guarding as well as the refusal.

⚠️ 1 Floobit is a rounding error against a median user-week of **84 F** and a build cost of
`consumable + 40-180 F`, so it reopens nothing on the laundering side. It is a delete
button that happens to hand back a coin.

### ⚠️ Donor-only (ruling 6) fits the existing rules unchanged

Ruling 5 plus ruling 8 land somewhere neat: because a synthetic already **is** its
effect's edition, donating it to a real card of that edition satisfies the existing
same-edition rule with no exemption written. The only new gate is ruling 6 — **refuse a
synthetic as a TARGET** — which is one check beside the existing base-card check in
`_validateTransplantPair`.

⚠️ The two must land together. Allowing a synthetic to receive would make a single
consumable purchase into a **permanently re-editable effect socket**: pay once, then
re-graft whatever you pull for the plain transplant fee ever after, which is precisely the
grinding the daily availability exists to cap.

⚠️ There is a real asymmetry worth being explicit about: a synthetic effect can move onto
a genuine card, so a user CAN promote a manufactured pairing into a collectible one — but
only by consuming the synthetic and spending a real card of the right edition to receive
it. That is a trade, not a loophole, and the collection ends up holding a real card.

### The visual (ruling 8)

The card wears **the effect's edition color, muted**, and is labeled **SNTH**. This is the
honest read — it says "prismatic strength, manufactured" in one glance — and it is the
answer to open question 4 below, which had been leaning toward no mark at all. That
leaning was written when the card was going to render as a floor print and therefore
already looked different. Under ruling 8 it does not, so it needs the mark.

⚠️ The muting must be a **treatment applied to the edition's own color**, not a separate
palette — a synthetic diamond has to read as diamond-and-manufactured, never as a sixth
edition. `serializeCard` already emits `edition`; it needs to emit the flag beside it and
let the client do the rest.

## What the codebase already gives us

⚠️ **Half of this already exists and is simply not distributed.** `_assignEffects` mints
one `base` template per player every season — measured on a fresh database, **192 base
templates against 192 non-prospect players**. Floor prints already equip and already score
the depicted player's raw FP; `_provisionStarterPack` just hands out five of them.

So "every player's base card from season start" is a **distribution** change, not a minting
one. The templates are there.

Transplant is likewise built (`cardManager.transplantEffect`, `POST /api/cards/transplant`,
`TRANSPLANT_COST_BY_EDITION`, `test_transplant.py`). The rules it currently enforces, and
what a synthetic target does to each:

| current rule | synthetic |
|---|---|
| same edition | **lifted** for a base target |
| both cards effect-bearing | **lifted** — the base card is the point |
| not already the same effect | keep |
| position-valid for the effect | **keep** — a WR-only effect still needs a WR |
| donor must be current-season | **keep** — this is what stops a retired effect re-entering play |

## ~~The one real design decision: edition is doing two jobs~~ — SUPERSEDED

> ⚠️ **Kept for the measurements only.** Ruling 8 (2026-08-26) stamps the template with
> the EFFECT's edition, so the two jobs never come apart and there is nothing to split.
> The table below still matters as the record of *why* minting at base scale was wrong —
> it is the evidence that produced the ruling. Do not implement the split.

## The original problem: edition is doing two jobs

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

Left alone, the synthetic is **strictly stronger than a real prismatic or diamond pull** —
roughly double output on an easier bar — and weaker than a real holographic one. The
convenience path becomes the power path for exactly the two tiers that should be hardest
to reach.

### ~~The split~~ (superseded by ruling 8 — recorded as the reasoning that led there)

**The card's edition and the effect's tier are separate inputs.**

- ~~The **card** stays `base`~~ — **under ruling 8 the card IS the effect's edition.**
  It is still worth nothing outside fantasy: not vaultable, sells for 0, no Combine, no
  classifications. What changed is that those are now enforced by the `is_synthetic`
  flag rather than falling out of the card being `base`.
- The **effect** keeps its own tier for `EDITION_POWER_SCALE` and `buildGateSpec`.

⚠️ **The donor's edition never needs to be tracked.** `EFFECT_EDITION_TIER[effectName]`
already declares where an effect belongs. A prismatic effect is prismatic wherever it
lands, and that single lookup drives both the strength and the bar.

The resulting relationship is the one we want:

> A synthetic build is **exactly equal in play** and **worth nothing in collection**
> against the real pull. You pay a consumable for convenience, never for power.

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

## The consumable — **Requisition** (owner direction 2026-08-26)

**Acquisition: 2 available each day in the shop, plus achievement rewards.**

### ⚠️ "2 per day" is 8 a season, not 56 — and that is the whole cap

The regular season is **four real calendar days**. 28 weeks at 7 rounds a day across days
0-3 (Mon-Thu), with the cross-day boundaries at weeks 8 / 15 / 22. And the shop's daily
allowance resets per **calendar** day: `shop_repository._dailyResetBoundary` takes the most
recent `_rolloverMomentUtc(date)` that has passed, one moment per date.

So the arithmetic that matters is **2 × 4 = 8 per regular season**, against a lineup of
**7 slots** (six base + FLEX). Friday's playoffs and Saturday's drafts add days, but a
synthetic minted then is minted into a season whose cards can no longer be equipped, so
they do not count.

That is a good cap and it is almost exactly the right size — **one full lineup's worth per
season, if you spend every day's allowance and never miss a day.** But it must be chosen
deliberately, because "2 per day" reads like an order of magnitude more than it is. If the
intent were a whole lineup plus room to iterate, the number is 3.

### ⚠️ The consumable caps the top and does nothing for the bottom

Every synthetic also consumes a **pulled donor card**, so a user needs seven real
effect-bearing cards to burn to fill a lineup. For a newer user the binding constraint is
therefore **donors, not Requisitions** — they will never see the daily cap. For a user with
a deep collection, 8 is the wall.

⚠️ That is the right shape and worth stating out loud: the friction report this feature
answers came from newer users, and the gate lands on the users who were never the problem.
It also means **the Floobit price should stay modest** — availability is already the
constraint, and pricing it high punishes the same behavior twice.

### Price

The plan's existing anchor holds: the Requisition **stacks on**
`TRANSPLANT_COST_BY_EDITION` (40 / 70 / 120 / 180). Against a median user-week of 84 F and
Accession at 200 F, something in the **60-100 F** band makes a diamond build cost
`~80 + 180 = 260 F` — three median weeks — while a metallic build stays reachable at
~120 F. Deliberately below Accession, because Accession buys a whole extra lineup slot for
four weeks and this buys one card.

### ⚠️ It is a CHARGE, and the powerup machinery has no concept of one

This is the one place the existing plumbing does not already fit. `POWERUP_CATALOG` items
are **timed effects** — bought, stamped with `expires_at_week`, and read as "is one active
right now". A Requisition is a **charge**: bought, held, and later *spent* on a specific
transplant. `ShopPurchase` records that a purchase happened; nothing records that it was
consumed.

Options, in order of preference:

1. **`ShopPurchase.consumed_at`** (nullable timestamp) — a user's balance is the count of
   their unconsumed rows. Smallest change, keeps one table, and gives a free audit trail of
   which build spent which purchase.
2. A counter column on `users`. Cheaper to read, but loses the trail and needs its own
   backfill story.

⚠️ **Decide whether unspent Requisitions carry over.** Across DAYS they must — otherwise
the cap becomes "log in every single day" rather than 8 a season, which punishes schedule
rather than spending. Across **SEASONS** is a real call: templates are season-scoped and a
synthetic expires with its season, so a stockpile carried into a new season is a burst of
8+ builds on day one. Leaning **expire at the season boundary**, matching how everything
else card-side is season-scoped.

### Naming

**Requisition** — a formal order for a thing to be produced, which is exactly the
transaction. It sits in the same register as the existing catalog (Dispensation, Annulment,
Conscription, Accession, Patronage, Endowment: all abstract Latinate nouns of permission or
provision), shares the `-tion` shape with three of them, counts naturally ("2 Requisitions
today"), and has no football collision.

Runner-up **Commission**, which is arguably a better fit for the meaning — you commission a
made thing — but in a league game it reads toward *the commissioner*, and that ambiguity is
not worth the small gain.

⚠️ Rejected: *Synthesis* (does not count as a noun — "2 Syntheses" is ugly), *Catalyst* and
*Reagent* (generic game-item register, and this catalog is deliberately formal), *Patent*
(precise — a licence to manufacture — but reads modern-corporate against the rest).

### Where it lives in the shop

⚠️ Its daily availability wants **its own slot**, not `ROTATION_CATEGORY_WEIGHTS`, which
rotates *pack* categories. It should be a fixed fixture of the Daily Selection alongside
the reroll — a consumable that only appears on some days makes lineup planning a lottery,
which is the opposite of what this feature is for.

Achievement grants ride the existing path unchanged: `reward_config` already queues packs
and powerups as `PendingReward`.

## Second-order effects to decide before building

1. **Hand-composition cards reach their ceiling more often.** Assembling a specific
   seven-effect hand becomes easier, which lifts Diversified, Anthem, Stacked Deck, Chain
   Reaction and Fortitude toward the top of their range.

   ⚠️ **This does NOT invalidate the Diversified resize** (an earlier draft of this doc
   claimed it did — wrong). Diversified pays a count of distinct output types, max three.
   Synthetics move it from 48.8 FP expected to **56.1 FP**, which is +15% and is exactly
   the ceiling the resize was sized against and deliberately kept inside the peer band
   (best mintable holographic ~47; prismatic Anthem 28.4 mean / 76.5 max). The sizing
   holds, and `test_diversified_sizing.py` already pins the CEILING rather than the mean —
   precisely because 63% of hands reached it even without synthetics.

   ⚠️ The real caveat is against the measurement, not the card. The 2.61 mean was sampled
   from **random pulls at pack weights**, which was never the population that matters: a
   user who owns Diversified curates their lineup and was probably already near 2.9.
   Synthetics make the ceiling the TYPICAL case rather than the COMMON one. Re-measure the
   cross family against curated hands once this exists; expect a modest lift, not a
   re-break.
2. **Effect-supply guarantees get routed around.** `_assignEffects` deliberately mints one
   template per effect where a bucket has fewer players than effects, so every effect
   exists somewhere. Synthetics let a user ignore bucket scarcity entirely. Not a bug —
   but the coverage guarantee stops being what limits access.
3. **The no-duplicate-effect equip rule becomes the real constraint** on hand building,
   where today it is player availability. Worth confirming that is the intended shape.
4. ~~**Visual identity.**~~ **ANSWERED 2026-08-26 (ruling 8): the effect's edition color,
   muted, labeled SNTH.** The old leaning — no mark, let it render as a floor print — was
   reasoning from a card that would have looked different anyway. Under ruling 8 it does
   not, so it needs the mark.
5. ~~**Vault.**~~ **ANSWERED 2026-08-26: a synthetic can never be vaulted or sold.**
   See the rulings section — this collapsed the Vault, Showcase and sell questions into
   one refusal, and raised three new ones (disposal, donating, tier upgrades) recorded
   there.

## Build order

1. `card_templates.is_synthetic` — model, inline migration, stamped in
   `_createUpgradedTemplate`. **This comes first now**: under ruling 8 nothing else can
   tell a synthetic from a real card, so every later step depends on it existing.
2. Distribute base cards — grant or make acquirable all 192. Templates already exist.
3. ~~Split edition-as-identity from effect-tier.~~ **STRUCK by ruling 8.** Replaced by:
   stamp the minted template's `edition` from `EFFECT_EDITION_TIER[donorEffect]` instead
   of from the target, and verify against the measurement table above that power scale
   and gate threshold land on the effect's own rung.
4. The value guards: sell 1 (one branch in `getSellValue`), Combine refusal, vault
   refusal.
5. Transplant rules — lift same-edition and both-effect-bearing **for a base target
   only**; refuse a synthetic target (ruling 6); keep position validity and the
   current-season donor gate.
6. The Requisition: catalog entry, `consumed_at` charge tracking, fixed daily shop slot,
   achievement reward hook.
7. Suppress classifications on the synthetic path.
8. Frontend: muted edition color + SNTH label off the serialized flag.
9. Re-measure the cross-card family (second-order item 1 above).

## Regression targets

- A synthetic prismatic effect scores **identically** to the real prismatic card, same
  bar, same params. This is the whole design in one assertion — and under ruling 8 it
  should hold by construction rather than by arithmetic, which is worth asserting anyway
  precisely because it now looks free.
- A synthetic sells for **1** — assert the DISPLAYED value and the PAID value agree,
  since they come from different call sites and only one of them has a floor.
- A synthetic's Combine fuel value is **1**, asserted independently of the refusal, so the
  refusal lapsing can never be expensive.
- A synthetic is refused by `vaultCard` and by `blendCards`, and therefore never reaches
  the Showcase. Assert the Showcase consequence too: it holds only by the vault gate and
  would break silently if Showcase ever gained its own path.
- A synthetic is accepted as a transplant **donor** and refused as a **target**.
- A synthetic's tier upgrade costs the **effect edition's** price, not base's.
- No synthetic ever carries `champion` / `all_pro` / `mvp`.
- ⚠️ A synthetic and a real card of the same edition are **distinguishable only by the
  flag** — assert that too, since it is the assumption every guard above rests on.
- Position validity still refused (no WR-only effect on a QB base card).
- An expired donor is still refused.
