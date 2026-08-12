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

At a Criticality, **one of each user's equipped cards becomes glitched** — if any of them can
catch it. Criticalities fire 2-3 times a season in prod (season 15: 3, season 14: 2), so a
lineup accumulates them slowly.

**Eligibility (owner, 2026-08-07): a player at the very bottom of the ladder cannot catch a
glitch.** `stable` with no anomaly events this week is excluded outright. A Criticality is the
anomaly reaching THROUGH players who are already unsettled, so a card whose player never
flickered has nothing for it to reach through. Firing an event qualifies on its own, because
`state` is a slow accumulator and someone who glitched this week but has not yet climbed off
`stable` is visibly unsettled. `cleansed` stays eligible — the power is gone but the history is
not.

**Selection: the eligible player highest on the ladder**, ranked by `GLITCH_TRIGGER_BASE` rather
than a separate ordering so it cannot drift from what drives the payout. That also settles two
cases a hand-written order gets wrong: `cleansed` sits at the floor (the power is gone, so it
should not be hunted) and `rampant` outranks `awakened` (an awakened player is in control; a
rampant one is coming apart). Ties break on a deterministic per-user shuffle.

**Why gate acquisition rather than tune the trigger.** Measured across a realistic population,
the per-player terms in `triggerChance` were nearly inert: the ladder was worth **+1.7 points**
of trigger chance and events **+2.2**, while the league dial — which moves every glitched card
at once — did all the work. 85% of players carry no anomaly row and sit at `stable`, drowning
the signal. Gating acquisition moves the decision somewhere the stable majority cannot dilute
it. Measured after: a full lineup catches a glitch **81%** of the time and the card it lands on
fires **37.3%** of weeks against the 31.9% population blend.

⚠️ **The old exploit is now a trap.** Stripping down to one card used to guarantee the glitch
landed on it; now it is one roll at having anybody unsettled at all, so a single-card lineup
catches a glitch only **24%** of the time against a full lineup's 81%. The strategy that
replaces it is better: field a player who is actually climbing the ladder. That is aiming
rather than starving, and it points at the anomaly system instead of away from it.

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
table entry.)

### FPx surges are damped to 0.80 (owner)

An FP surge is a FIXED amount. An FPx surge multiplies the whole lineup, so it grows with the
rest of your hand — a strong hand should not also make your glitch stronger.

⚠️ The size of that problem was overstated in an earlier note. At the ~250 lineup the ladder is
anchored to, an undamped FPx surge is actually slightly WEAKER than the FP one (0.88x). The
imbalance only appears in rich hands:

| lineup total | undamped | damped 0.80 |
|---|---|---|
| 220 | 0.78x | 0.62x |
| 250 | 0.88x | 0.71x |
| 300 | 1.06x | 0.85x |
| 350 | 1.24x | 0.99x |
| 450 | **1.59x** | 1.27x |

**0.80** holds near parity through a typical hand and clips only the top end. A deeper cut
(0.55 was tried) halves FPx everywhere and fixes a problem that does not exist at normal lineup
sizes.

| outcome | FP mult | FPx mult | FPx pays at a 250 lineup |
|---|---|---|---|
| flicker | 0.35 | 0.28 | 7 FP |
| surge | 1.00 | 0.80 | 20 FP |
| cascade | 2.50 | 2.00 | 50 FP |
| runaway | 5.00 | 4.00 | 100 FP |

### Naming — deliberately cryptic (owner)

The four outcomes are not surfaced as clean labels. In the card's score breakdown a glitch adds
**its own line item, rendered in glitched text** — you can see the card did something and how
much it paid, but WHAT it was stays corrupted and unreadable.

**Unless the player is awakened**, in which case it reads clearly. That is the payoff of the arc
and it needs no separate mechanic: a player in control produces a legible readout, a player
cracking produces noise. It also means the internal names never have to be good, because most of
the time nobody sees them.

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

**Use the AWAKENED treatment, not the glitch one, for the card itself (owner).** The card sits
on screen for minutes in a collection view, where a line in the play feed is gone in seconds.
The `l1`/`l2` glitch animations sway, drift, slam and strobe — fine for a passing line, actively
unpleasant on something you are reading.

The awakened treatment is built for exactly this and says so in its own comment:

> A brilliant gold glow that only breathes in INTENSITY (box-shadow), **never moves position** —
> so it stays perfectly smooth as new plays push the row down the feed (the old position-swept
> shimmer janked on every reflow).

So: `.awakened-row`'s shape — a static wash plus a slow box-shadow breath, **no movement, no
character corruption** — for every glitched card. Only the color varies:

| card state | treatment |
|---|---|
| glitched, player not awakened | the awakened glow SHAPE in a Criticality hue (the violet of `CriticalityGlitch`'s wash) rather than gold |
| glitched, player awakened | the gold `.awakened-row` treatment as-is — the two states have converged |
| **the week a surge triggers** | a brief one-off intensity burst, scaled to the outcome. This is the only moment anything moves |

Character corruption is reserved for the **score-detail line item** (see Naming), where it is
read once rather than stared at.

`?criticality=1` previews the site-wide mode without a real event; the card treatment should get
a similar preview hook.

## Season boundary (owner)

**A glitched card survives the season, but like every other previous-season card it cannot be
played.** It stays in the collection as a record of the event — the Vault and Showcase are its
natural home. It scores only in the season it was earned.

## Resolution — end of week, and the line item scrambles until then (owner)

**The trigger resolves at WEEK END, and this is forced rather than chosen.** The chance is
`base + boosts from anomaly events that player fired this week`, and those events fire during
the week's games. There is no correct answer available before the games are done.

That is also exactly how chance cards already behave, so it needs no new machinery:

    cardEffects.py:2969
    triggered = roll <= odds and not getattr(ctx, 'gamesActive', False)

Chance cards refuse to resolve while `gamesActive`, and `_processWeekCardEffects` persists
`WeeklyCardBonus` at week end.

**During the week the line item shows nothing but noise.** The glitch's score-detail line renders
as random glitch characters — not a number, not a name, not a percentage. The card is visibly
computing something it will not tell you yet.

**The scramble should get louder as the odds climb.** The trigger chance genuinely rises through
the week as events fire, so `GlitchedText`'s intensity can track it: a quiet week stays at `low`
and barely flickers, a week where the player has already glitched twice runs at `high` and is
obviously agitated. That turns the line into a **live readout of pressure without ever showing a
number** — you can tell your card is getting interested, which is the cryptic version of watching
the odds build.

At week end it resolves: the line becomes the payout, and the OUTCOME name stays corrupted unless
the player is awakened (see Naming).

## The instability dial lifts the base, at a fraction (owner)

`getCriticalityMultiplier` scales per-play glitch probability with how close the league is to a
crossing: 0.45 in a suppression window, 1.0 quiet, 1.8 building, 2.6 pre-criticality, 5.0 during
a live one.

It ALREADY lifts a glitched card indirectly — a hot league fires more anomaly events, and events
boost the trigger. But only slightly, because one player's event count stays small however the
dial scales it:

| league state | dial | as designed | full dial on base |
|---|---|---|---|
| suppressed | 0.45 | 36% | 17% |
| quiet | 1.00 | 37% | 37% |
| building | 1.80 | 39% | **67%** |
| pre-criticality | 2.60 | 40% | **90%** (cap) |
| live Criticality | 5.00 | 45% | **90%** (cap) |

Neither extreme works. The indirect-only column barely moves (37% to 45%), so the event people
have been building toward does not visibly change their cards. The full-dial column compounds —
both terms rise together, so a rampant card sits pinned at the cap through an entire Criticality
and at 67% during mere buildup, which is most of a hot season. A card that is reliably on is the
opposite of wild magic.

**So apply the dial to the base at a fraction:**

    effectiveBase = base * (1 + (dial - 1) * 0.3)

A live Criticality takes a rampant card from 35% to ~59% rather than pinning it at 90%. The
buildup is felt without becoming a certainty.

This also makes the design robust to something no measurement can settle: the event rate for a
real user base is unknown, and prod's is a floor. A partial dial on the base delivers the
hot-stretch feel whether events stay rare or not.

## ⚠️ Chrome will move the ground under this (owner)

`docs/CHROME.md`'s 2026-07-31 revision promotes chrome to **the input layer of the anomaly
system**, and this spec keys off two things it changes:

| this spec assumes | chrome changes it to |
|---|---|
| ladder position is driven by user ATTENTION | **chrome IS how players awaken** — "a specific augment drives it; attention no longer does" |
| awakened powers come from the L4 catalog | **powers are chrome too** — fans gift them |
| a player's state is their own | awakening **spreads like a virus** through teammates and on-field contact; cleansed players spread the inverse |

**What survives.** The card keys off *how anomalous its player is* and *what that player did this
week*. Both remain true under chrome — only the mechanism producing the state changes. The
`AnomalyEvent` log, the micro/personality/signature layers, the awakened distinction and the
instability dial are all upstream of chrome rather than replaced by it.

**What needs revisiting when chrome lands.** The five base rates are calibrated against today's
ladder distribution. If chrome makes awakening common (contagion spreads it) or rare (supply is
the master dial), that distribution shifts and the bases want re-measuring. The 30% awakened base
in particular was set from a measured 37% power-use rate that chrome will change outright.

Build against today's system; expect to re-tune the five numbers, not the design.

## Open questions
2. ~~**Do the base rates want the instability dial on top?**~~ RESOLVED (owner) — see below.

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
