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

## The consumable — **Synth Component** (owner direction 2026-08-26)

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
therefore **donors, not Synth Components** — they will never see the daily cap. For a user with
a deep collection, 8 is the wall.

⚠️ That is the right shape and worth stating out loud: the friction report this feature
answers came from newer users, and the gate lands on the users who were never the problem.
It also means **the Floobit price should stay modest** — availability is already the
constraint, and pricing it high punishes the same behavior twice.

### Price

The plan's existing anchor holds: the Synth Component **stacks on**
`TRANSPLANT_COST_BY_EDITION` (40 / 70 / 120 / 180). Against a median user-week of 84 F and
Accession at 200 F, something in the **60-100 F** band makes a diamond build cost
`~80 + 180 = 260 F` — three median weeks — while a metallic build stays reachable at
~120 F. Deliberately below Accession, because Accession buys a whole extra lineup slot for
four weeks and this buys one card.

### ⚠️ It is a CHARGE, and the powerup machinery has no concept of one

This is the one place the existing plumbing does not already fit. `POWERUP_CATALOG` items
are **timed effects** — bought, stamped with `expires_at_week`, and read as "is one active
right now". A Synth Component is a **charge**: bought, held, and later *spent* on a specific
transplant. `ShopPurchase` records that a purchase happened; nothing records that it was
consumed.

Options, in order of preference:

1. **`ShopPurchase.consumed_at`** (nullable timestamp) — a user's balance is the count of
   their unconsumed rows. Smallest change, keeps one table, and gives a free audit trail of
   which build spent which purchase.
2. A counter column on `users`. Cheaper to read, but loses the trail and needs its own
   backfill story.

⚠️ **Decide whether unspent Synth Components carry over.** Across DAYS they must — otherwise
the cap becomes "log in every single day" rather than 8 a season, which punishes schedule
rather than spending. Across **SEASONS** is a real call: templates are season-scoped and a
synthetic expires with its season, so a stockpile carried into a new season is a burst of
8+ builds on day one. Leaning **expire at the season boundary**, matching how everything
else card-side is season-scoped.

### Naming — **Component**, borrowed from chrome (owner, 2026-08-26)

⚠️ **The chrome plan already speaks this vocabulary, and it is the mature half.**
`WEATHER_AND_CHROME_PLAN.md` writes "chrome components" throughout — earned by play,
earmarked at gift time, possibly rarity-tiered — so this is synth **joining** an existing
family rather than a term being coined for it. Two members: **Synth Components** and
**Chrome Components**.

That settles the naming search recorded below. `Synth Key` was the pick a moment before
this, and its one argument — the tie to the card's own **SNTH** label — largely survives,
since `Synth Component` still carries the word. What it buys instead is a family a user
can learn once.

⚠️ **A SHARED WORD ONLY PAYS OFF IF THE PLUMBING IS SHARED.** Two things that sound alike
and behave differently are worse than two things with different names. Which makes the
next part the real content of this decision, not the name.

### ⚠️ This CORRECTS the `ShopPurchase.consumed_at` recommendation above

That was right for a shop-only item and is **wrong for a family whose other member is
never bought**. Chrome components are **earned, never purchased** — a locked owner ruling
(2026-07-31) — so they will never have a `ShopPurchase` row to hang a `consumed_at` on.

Build a **component ledger** instead: one row per component, carrying `user_id`, `type`
(`synth` / `chrome`), `source` (shop / achievement / fantasy / pick-em), `granted_at` and
`consumed_at`. A balance is a count of unconsumed rows of a type; spending is one path.
Chrome needs this table regardless, so building it here means **priority 3 inherits it
finished** rather than growing a parallel one.

⚠️ Chrome additionally earmarks a component to a specific player and augment at gift time
("a funding race, not an election"), so leave room for a nullable target — but do not
build the earmark now; a synth component is spent the instant it is used and has nothing
to point at.

### ⚠️ Three ways the two members DIVERGE, and one of them is load-bearing

| | Synth Component | Chrome Component |
|---|---|---|
| acquisition | **shop, 2/day** + achievements | **earned only, never bought** |
| rarity | uniform | possibly tiered (common nudges, rare jumps) |
| targeting | spent immediately at synthesis | earmarked to a player + augment |

⚠️ **THE ACQUISITION DIVERGENCE MUST STAY VISIBLE, because the chrome plan's best argument
depends on it.** Chrome being earned is what makes *supply the master dial*: it turns R₀ —
the one load-bearing number in the contagion design — from something emergent out of
Floobit income × price × spending appetite into a schedule we set directly. A shared noun
invites a later, reasonable-sounding "unify the acquisition too", and that would silently
undo the only thing making the hardest calibration in that plan tractable.

⚠️ The tension is smaller than it reads, and saying why keeps it from being re-litigated:
at 2/day with a modest price the synth cap is **days elapsed, not Floobits banked**, which
is nearly an earned model wearing a shop front. It is still a purchase, and chrome's must
not become one.

⚠️ **It also brushes an open question in the chrome plan.** That plan recommends *generic*
components (one type feeds any augment) and leaves "do components have classes?" open. Two
family members means the inventory reads as `Components: 3 Chrome, 2 Synth` — which is a
class system presentationally whether or not it is one mechanically. Worth deciding on
purpose there rather than inheriting it from here.

### Achievement grants — where they come from and how many

⚠️ **GRANT DIRECTLY TO THE LEDGER, NOT AS A `PendingReward`.** `_applyReward` splits its
config three ways: floobits credit **immediately**, packs and powerups queue as
`PendingReward` rows the user claims later. A component belongs with the floobits, and the
reason is structural rather than convenience:

- **`PendingReward` exists because packs and powerups have a DECISION at claim time.** You
  open a pack (reveal, then keep), and you activate a powerup (which starts a four-week
  timer, so *when* matters). A component has no such moment — it sits in a balance until
  it is spent. A claim step here is pure friction.
- ⚠️ **And it is friction that can DESTROY things.** `sweepExpiredRewards()` drops every
  unclaimed, unstashed `PendingReward` at season start. Route components through it and a
  user who never noticed the claim button silently loses them at the boundary.

So `reward_config` gains `components: {synth: N}`, applied beside the `floobits` branch.
⚠️ **This needs no migration** — `_seedAchievements` upserts `reward_config` on every boot
(it is in `refreshFields`), so the grants land on an existing production database at the
next restart.

⚠️ It is also the path **chrome** needs. Chrome components are earned from achievements,
fantasy and pick-em, and none of those have a claim moment either — so the direct-grant
branch is shared, exactly like the ledger.

### ⚠️ Measured: the capstone rungs are already the right scarcity

The live achievement set is **106**, and its shape does the sizing work for us:

| | |
|---|---|
| `guidance` | **59**, and all of them `per_season` |
| `onboarding` / `collection` / `secret` | 5 / 9 / 33, all `once` |
| already grant a pack | 24 |
| already grant a powerup | **1** |

⚠️ The guidance set is almost entirely **tiered ladders** — `_i / _ii / _iii / _iv` — and
the **tier-IV rung is already the slot where the non-Floobit reward lives** (a `grand` pack
in ten of them). That is the natural home: already per-season, already capstone, already
understood by a user as "this one is a real reward".

**Measured completion rate: an engaged user finishes 2-3 of the 14 capstones in a season**
(median 2, max 3), against a median of 14 achievement completions overall. So **one
component per capstone is self-limiting** — no subset needs picking, the difficulty already
does it.

⚠️ **Sample caveat, stated because it matters:** that is measured on a development database
with **two** users across 21 seasons. The targets are fixed and that player's engagement is
realistic, so the ~2-3 rate is indicative — but re-measure against production before
committing the number.

### The supply picture

| source | per season |
|---|---|
| shop, 2/day × 4 game days | **8** |
| guidance capstones, 1 each | **~2-3** |
| onboarding, once ever | 1 |
| **total, engaged user** | **~10-11** against a 7-slot lineup |

**Recommend: 1 per guidance capstone, plus 1 on an onboarding achievement.**

⚠️ **The onboarding grant is the one that earns its place**, and it is worth more than its
size. Under the new starter pack a first-day user holds five or six **metallic** cards —
real effects, on players the game picked. One component turns that into *your* effects on
*your* players immediately, instead of waiting for shop days to accumulate. That is
precisely the complaint this whole feature answers, and it lands in the first session
rather than the second week.

⚠️ **The risk to keep named: achievement grants BYPASS the daily cap.** The shop's whole
design is that the constraint is *days elapsed*, not Floobits banked — and a burst of
completions hands over several components at once, which the cap cannot see. At 2-3 a
season that is a rounding error. If components were later added to all 14 capstones **and**
the 33 secrets, the gate would stop being the gate. Any future widening of the grant list
is a change to the cap, whether or not it is discussed as one.

### Where it lives in the shop

⚠️ Its daily availability wants **its own slot**, not `ROTATION_CATEGORY_WEIGHTS`, which
rotates *pack* categories. It should be a fixed fixture of the Daily Selection alongside
the reroll — a consumable that only appears on some days makes lineup planning a lottery,
which is the opposite of what this feature is for.

Achievement grants ride the existing path unchanged: `reward_config` already queues packs
and powerups as `PendingReward`.

## The surfaces this changes (owner, 2026-08-26)

Three UI/plumbing consequences, all of them following from "every player's base card is
available" rather than being separate features.

### A. The card picker — base cards are a POOL, not inventory

⚠️ **They must not go into anyone's collection.** 192 base cards handed to every user
would bury the cards they actually pulled under a wall of floor prints. So the picker gets
a **second section** — your collection, and every player — and the base half is a
*universal pool* nobody owns.

⚠️ **But `equipped_cards.user_card_id` is `NOT NULL` and FKs to `user_cards`**, so
something has to exist to equip. The answer is to **materialize the `UserCard` lazily at
equip time** rather than granting 192 rows up front, and to **filter `edition == 'base'`
out of the collection view**. One filter, one get-or-create.

⚠️ **That filter covers the synthetic case for free.** A synthetic is no longer `base`
(ruling 8), so the moment a base card is synthesized it leaves the pool and appears in the
collection on its own. No second rule.

⚠️ **It also retires the existing base cards with no migration.** Users hold base cards
today from the current starter pack; filtering `base` out of the collection quietly folds
them into the pool. Nothing of value is hidden — they sell for 2.

⚠️ **Check the same-player-twice case.** WR1 and WR2 both accept a WR, so the pool makes
it newly easy to field one player in both — the base card and a real card of the same
receiver, or two base cards. Today player scarcity prevented it by accident. Decide
whether it is refused; the no-duplicate-EFFECT rule will not catch it, because no-effect
cards are exempt from that rule by design.

### B. The synthesis menu — every player, every edition

The same pool appears in the synthesis screen as the choice of *target*. And per the
owner: **the rating gate does not apply here.** `EDITION_THRESHOLDS` exists to make a
diamond card mean something as a collectible; a synthetic is not a collectible, so any
player can carry any effect from any edition.

⚠️ **This means item D below is about PULLS, not about synthesis.** Once synthesis exists,
a 65-rated player can already wear a diamond effect — so expanding who is *eligible to be
minted* at high editions changes what appears in packs and in the collection, and changes
nothing at all about what a user can field. Worth keeping separate, or the two get argued
as if they were the same lever.

### C. The starter pack goes back to metallic

⚠️ **The current starter grants a floor lineup, and this plan makes that gift worthless.**
`_provisionStarterPack` hands out `base` cards for one stated reason — "so every user can
field a legal lineup on day one" — and the universal pool now does that for everyone, for
free, forever. Granting base cards after this ships is granting nothing.

⚠️ **The branch already exists.** The function already falls back to metallic when no
floor templates are found (written for a partially-migrated database), so this inverts a
condition rather than adding a path.

⚠️ **Count mismatch to resolve while touching it:** the docstring says "5 random base
cards" and CLAUDE.md says "5 base cards, one per position", but the inline comment says
one per lineup SLOT — "QB/RB/WR/WR/TE/K — two WR cards for WR1 + WR2" — which is **6**.
Five positions, six slots. Read the code, then fix whichever of the three is wrong.

## D. Expanding who is eligible for the top editions (do last)

**Owner, 2026-08-26:** a player normally gated out of prismatic and diamond should become
eligible if they had a strong previous season, or hold an AP / CH / MVP tag. The goal is
card diversity.

### ⚠️ Measured: SIX players hold the entire diamond pool, and diamond TE is EMPTY

Season 20, 192 rostered players (the exact population that gets cards):

| pos | n | holo ≥75 | prism ≥80 | **diamond ≥90** |
|---|---|---|---|---|
| QB | 32 | 17 | 10 | **1** |
| RB | 32 | 14 | 7 | **1** |
| WR | 64 | 30 | 21 | **3** |
| TE | 32 | 14 | 5 | **0** |
| K | 32 | 20 | 10 | **1** |

⚠️ **A one-player bucket mints that bucket's ENTIRE effect set onto that one player.**
`_assignEffects` sets `total = max(len(players) * k, len(pool))` when topping up and then
splits it across the players present — so with a single eligible QB, `counts = [26]` and
one man wears all 26 diamond QB effects. That is the diversity problem stated exactly: at
diamond, the card *is* the player, and there is only one of him.

⚠️ **Diamond TE has nobody at all**, so every TE-exclusive diamond effect is unmintable
this season. That is the same failure CLAUDE.md already records for QB and K in an earlier
season — it has simply moved position. It recurs because it is structural, not a one-off.

### What the two rules would do

| | prismatic | diamond |
|---|---|---|
| rating gate only | 53 | **6** |
| \+ prev-season perf ≥ 85 | 91 | 72 |
| \+ prev-season perf ≥ **90** | 66 | **37** |
| \+ prev-season perf ≥ 92 | 64 | 29 |

**SETTLED (owner, 2026-08-26): perf ≥ 90, and CHAMPION IS EXCLUDED.** The bar is the ~p90
of the distribution (median 80, p90 93); it takes diamond from 6 players to 37 while moving
prismatic only 53 → 66, and it fills diamond TE. The change lands almost entirely on the
tier whose scarcity is pathological.

**The eligibility rule, in full:** a player is eligible for an edition if
`playerRating >= EDITION_THRESHOLDS[edition]` **OR** their previous season's
`PlayerSeasonStats.performance_rating >= 90` **OR** they hold an **All-Pro** or **MVP** tag
from the previous season. Champion does not qualify anyone.

### ⚠️ It does NOT make diamonds more common — only more varied

`_weightedDraw` is explicitly two-stage: *"roll the edition using packWeights, then pick a
template within that edition"*. **Edition rates are set by `packWeights` and are
independent of how many templates exist per edition**, so widening eligibility cannot
inflate diamond supply. This is the reassurance the change needs, and it is verified in
the code rather than assumed.

⚠️ **But it does change what a diamond DEPICTS.** Stage two weights by
`max(1, 120 - playerRating)`, so a 65-rated player is ~2x as likely to be drawn as a
94-rated one *within* the diamond pool. Add 31 lower-rated players to a pool of 6 elite
ones and most diamonds pulled will depict merely-good players. ⚠️ Power self-corrects —
`buildEffectConfig` scales params by rating, so a diamond on a 65 pays less than a diamond
on a 94 — but the elite diamond becomes rarer relative to its own tier. Decide whether
that is the intent (it arguably IS the diversity being asked for) or whether stage two
wants a floor.

### The accolade half is free; the performance half is nearly free

⚠️ **`generateSeasonTemplates` ALREADY receives `mvpPlayerId`, `championPlayerIds` and
`allProPlayerIds`** and uses them for `_buildClassification`. They sit in scope above the
bucket loop. The accolade rule is therefore a gate change with **zero new plumbing**.

`PlayerSeasonStats.performance_rating` is persisted and — measured — populated for exactly
**192 of 480** season rows, which is precisely the rostered population that gets cards. The
other 288 are free agents and non-rostered players, who are excluded from minting anyway.
So the performance rule is one join.

⚠️ **AP AND MVP ARE INDIVIDUAL; CHAMPION IS NOT — SO CHAMPION IS EXCLUDED** (owner,
2026-08-26). The Floos Bowl winner's roster is six players, and *five of season 20's six
were below the diamond gate*, including whoever happened to be at kicker. Granting full
edition eligibility for having been on the winning team is a far weaker claim than a 90
performance rating, and it hands the top tier to a whole roster regardless of how any of
them played.

⚠️ **`championPlayerIds` STILL FEEDS `_buildClassification` — do not remove it, only stop
it feeding the GATE.** The two uses sit a few lines apart and read alike: a champion card
must keep wearing its CH tag, it just does not become mintable at an edition its player's
rating and production did not earn. Deleting the set to implement this ruling would strip
the tag off every champion card in the league.

⚠️ **The sharpest single case for this change:** season 20's All-Pro **Tanuki Batman rates
65** — the league recognized him as the best at his position, and the card system will not
mint him above metallic, because 65 is below even the *holographic* bar of 75. Six All-Pros
that season, **five of them below the diamond gate and two below prismatic**.

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
2. The base pool — filter `edition == 'base'` out of the collection, add the picker's
   second section, materialize the `UserCard` lazily at equip. Templates already exist.
2b. Starter pack back to metallic (surface C) — it must land with step 2, not after: the
   moment the pool exists the current starter grants nothing.
3. ~~Split edition-as-identity from effect-tier.~~ **STRUCK by ruling 8.** Replaced by:
   stamp the minted template's `edition` from `EFFECT_EDITION_TIER[donorEffect]` instead
   of from the target, and verify against the measurement table above that power scale
   and gate threshold land on the effect's own rung.
4. The value guards: sell 1 (one branch in `getSellValue`), Combine refusal, vault
   refusal.
5. Transplant rules — lift same-edition and both-effect-bearing **for a base target
   only**; refuse a synthetic target (ruling 6); keep position validity and the
   current-season donor gate.
6. The Synth Component: the shared component ledger, catalog entry, fixed daily shop
   slot, achievement reward hook.
7. Suppress classifications on the synthetic path.
8. Frontend: the picker's second section, the synthesis target list (no rating gate
   there), and the muted edition color + SNTH label off the serialized flag.
9. Re-measure the cross-card family (second-order item 1 above).
10. **Last, and separable:** expanded edition eligibility (section D). It touches the
   MINT side only and nothing else here depends on it, so it can ship a season later
   without stranding anything.

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
