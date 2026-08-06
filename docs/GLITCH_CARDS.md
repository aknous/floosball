# Glitch Cards — wild magic from a Criticality

**Branch:** `next-season`
**Status:** DESIGN — settled in conversation 2026-08-06. Nothing built.
**Reads with:** `docs/CRITICALITY_METAGAME_PLAN.md` (fans-vs-Cores, the locked no-wipe
constraint), `docs/AWAKENED_POWERS_PLAN.md` (the ladder, the charge meter, the L4 powers),
`docs/CHROME.md` (chrome supersedes the Vigil as the fan lever), `docs/CARD_STAT_LADDER.md`
(the card pool this attaches to).

## What it is

A **glitch card is a real card that caught something during a Criticality.** Not a new tier,
not a new effect pool — an existing card in someone's collection, marked, that now sometimes
pays an extra unpredictable bonus on top of what it already did.

The reference is wild magic: you keep everything the card was, and some weeks it also does
something else.

## The rule that shapes everything (owner)

> **A glitch never takes anything away.**

An earlier draft had the glitch corrupting the printed effect — misreads, damping, nulls. That
was wrong, for a reason worth recording: **people cultivate cards and lineups.** Degrading what
someone built punishes them for having built it. A card that sometimes pays less than it says
is a worse card wearing a costume.

So the surge is strictly **additive and non-negative**. The card always does its job. The
inconsistency lives in the UPSIDE — a quiet week means no bonus, never a penalty.

This also keeps it inside the locked constraint at `CRITICALITY_METAGAME_PLAN.md:107` — the
currency of the contest is CONTROL and ANOMALY, never RECORDS, and collections are named
explicitly as never at risk.

## Where it lives

**On `UserCard`, not `CardTemplate`.** `UserCard` already carries per-instance state (`tier`,
`vaulted`), and the same template must be able to exist clean in one collection and glitched in
another. The glitch happened to *your copy*, at a specific event.

## Acquisition — one card per Criticality

At a Criticality, **one of each user's equipped cards becomes glitched.** Everyone with cards
equipped is affected; exposure is the only qualification. Criticalities fire 2-3 times a season
in prod (season 15: 3, season 14: 2), so a lineup accumulates them slowly.

⚠️ **This is gameable and that is accepted (owner).** Equipping exactly one card during a
Criticality guarantees the glitch lands on it, where a full lineup gives any given card a 1-in-6
chance. Stripping your lineup costs you five cards' output for that week, so it is a real
trade rather than a free exploit — "just another layer."

## Operation — a weekly roll the anomaly layer drives

Each week a glitched card rolls **once** to see whether its surge triggers.

    triggerChance = base(on-card player's anomaly state)
                  + boost per anomaly event that player fired this week
                  (capped at 90%)

### Base, by the player's ladder position

| player state | base | effective (incl. events) |
|---|---|---|
| stable | 5% | 13% |
| stirring | 15% | 23% |
| erratic | 25% | 33% |
| rampant | 35% | **42%** |
| awakened | 30% | 38% |

Chosen over a low-base/event-led alternative because **89% of player-weeks contain no anomaly
event at all**. A design leaning on events would leave a glitched card dormant most weeks at
current volumes, and neither the event rate for a larger user base nor its floor is knowable
from the one league that exists. This degrades gracefully if events stay rare and improves if
they do not.

**Awakened keeps a real base (30%)**, deliberately. An earlier draft had awakened players'
cards convert to something permanent because the lore says they stop glitching. But measured on
prod, awakened players fire a power on only **37% of their weeks** (1.20 uses when they fire),
which is *less often* than glitching — so tying the card solely to power use would make
awakening quieten the card rather than upgrade it.

### Events escalate the chance, by level

| anomaly level | what it is | boost |
|---|---|---|
| `micro` | cosmetic flicker, generic | **+15%** |
| `personality` | glitch keyed to who they are | **+25%** |
| `signature` | an actual L4 power, real mechanical effect | **+40%** |

Stacking per event. On a week where something actually happened, the chance roughly doubles:

| state | quiet week | week with events |
|---|---|---|
| rampant | 35% | **69%** |
| awakened | 30% | **65%** |

That is the intended feel: you watch your player flicker in the play feed, and the card is now
favoured to pay. Across a season events lift the rate ~8 points; on the weeks they land they are
decisive.

**This is already logged.** `AnomalyEvent` persists every fired anomaly with `player_id`,
`season`, `week`, `layer` and (for signature) the `ability` slug. No new instrumentation needed
— prod season 15 has 14,047 events across 229 players.

### Magnitude — the surge table

On a trigger, roll for size. The multiplier applies to the **card's own output**, so a surge
scales with whatever it is attached to instead of being a flat FP number that trivialises
metallic and vanishes on diamond.

| outcome | x base | weight | on a 28.3 FP card |
|---|---|---|---|
| flicker | 0.35 | 39% | 9.9 |
| surge | 1.00 | 33% | 28.3 |
| cascade | 2.50 | 20% | 70.8 |
| runaway | 5.00 | 8% | 141.5 |

(The old `quiet` row is gone — not triggering IS the quiet outcome, so it should not also be a
table entry.) Names are placeholder and want an owner pass.

## The card looks glitched (owner)

A glitched card should carry the same visual language as a glitching play, not a new one. The
frontend already has the whole vocabulary built for the anomaly feed, and reusing it is what
makes a glitched card read as *the same phenomenon* rather than a card cosmetic.

**What exists** (`floosball-react`):

| piece | what it does |
|---|---|
| `GlitchedText.tsx` | periodic character substitution from `░▒▓█▌▐│┃▪◦◊◆▲△◢◣⌬⌭⌮`, at `low` (L1, stray artifact) or `high` (L2, actively breaking) |
| `.glitch-text-l1` / `-l1-a/b/c` | chroma aberration, vertical sway, drift — the subtle tier |
| `.glitch-text-l2` / `-l2-a/b/c` | chroma, slam, strobe — the loud tier |
| `.glitch-text-l3` | reserved for signature/awakened |
| `CriticalityGlitch.tsx` | site-wide mode during a live Criticality: violet wash, breathing edge glow, `criticality-active` on `<html>`, per-burst character corruption and discrete elements shifting a few px |

**Mapping it onto the card.** The existing L1/L2/L3 tiers already correspond to exactly the
three anomaly levels the trigger boost uses, so the card can key off the same thing:

| card state | treatment |
|---|---|
| glitched, player `stable`/`stirring` | `l1` — occasional chroma shimmer on the card frame, card name via `GlitchedText` at `low` |
| glitched, player `erratic`/`rampant` | `l2` — sway/slam on the frame, name at `high` |
| glitched, player `awakened` | `l3` — the reserved tier; steadier and more deliberate, matching a player in control |
| **the week a surge triggers** | a one-off burst on the card, scaled to the outcome — `flicker` barely registers, `runaway` should be unmistakable |

Two notes carried from `CriticalityGlitch.tsx`'s own tuning comments, which learned this the
hard way: keep element shifts small (it uses 4px) so layout and click targets barely move, and
pace bursts so the effect is *apparent but not annoying*. A card sitting in a collection view is
on screen far longer than a line in a play feed, so the persistent tier wants to be gentler than
the equivalent feed treatment — the loud version belongs on the trigger, not the idle state.

`?criticality=1` previews the site-wide mode without a real event; the card treatment should get
a similar preview hook.

## Season boundary (owner)

**A glitched card survives the season, but like every other previous-season card it cannot be
played.** It stays in the collection as a record of the event — the Vault and Showcase are its
natural home. It scores only in the season it was earned.

## Open questions

1. **FPx surges need their own damping.** Multiplying a `+0.10 FPx` card by 5 is ~150 FP across
   a full lineup versus ~140 for the equivalent FP card, and FPx compounds against everything
   else held. The table must be output-aware or FPx needs a gentler multiplier column.
2. **Names** for the four surge outcomes.
3. **Does the trigger resolve before or after the week scores?** Resolving early makes it
   plannable, which cuts against wild magic; resolving late makes checking the card the payoff.
4. **Do the base rates want the instability dial on top?** `getCriticalityMultiplier` already
   ramps as the league approaches a crossing. Applying it to the base would make every glitched
   card livelier during a hot stretch, which reinforces the deeper game — but it stacks with the
   event boost, which also rises then.

## What is NOT in scope

- **No confiscation.** Locked constraint; collections are never at risk.
- **No degradation of the printed effect.** Owner call.
- **Not a new edition.** It marks existing cards; it does not add a tier above diamond.

## Measurements this rests on (prod, season 15 unless noted)

| | |
|---|---|
| Criticalities fired | 3 (season 15), 2 (season 14) |
| anomaly events logged | 14,047 across 229 players |
| by layer | micro 6,524 · personality 5,131 · signature 2,392 |
| player-weeks with no event | 89% |
| glitches on a firing week | mean 1.16, max 3 |
| awakened weeks with a power use | 37% |
| power uses when they fire | mean 1.20, max 4 |
| glitches before awakening | median 13, mean 39.9, 17% awakened with none |
| players reaching awakened | 160 across 15 seasons |

⚠️ These come from a league with 14-28 engaged fans. Event frequency scales with attention, and
`AWAKENED_CRITICALITY_CHARGE_MULT = 4.0` means the charge meter fills four times faster during a
Criticality — so every rate here is a FLOOR for a larger user base, not a steady state.
