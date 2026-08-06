# Card Stat Ladder — offensive stats

**Status:** draft for owner review. Nothing here is built.
**Branch:** `next-season`

The foundation card set, rebuilt so every card keys off a real box-score stat. Same
stat appears at three rarities with a rising mechanic, so a player can collect the
progression for a stat they like watching.

    metallic      flat, always on      "+X FP per reception"
    holographic   thresholded/tiered   "+X per reception, doubled on 20+ yard catches"
    prismatic     compounding          "streak grows each week they clear 8 catches"

Rarity buys **shape**, not a bigger mean — the edition power dial already targets ~100%
mean per edition. A prismatic version of a stat should be swingier than the metallic
one, not simply larger.

## Measured volumes (this is what sizes every rate)

Per game, players at that position, from a session sim DB (945 player-games):

| pos | stat | mean | p90 | max |
|---|---|---|---|---|
| QB | completions | 27.7 | 38 | 46 |
| QB | attempts | 38.8 | 51 | 67 |
| QB | pass yards | 229.9 | 332 | 427 |
| QB | pass TDs | 1.07 | 2 | 4 |
| QB | 20+ throws | 1.75 | 4 | 7 |
| QB | longest | 24.9 | 36 | 67 |
| QB | air yards | 256.6 | 354 | 492 |
| QB | bad throws | 1.56 | 5 | 13 |
| RB | carries | 25.9 | 37 | 52 |
| RB | rush yards | 110.5 | 209 | 341 |
| RB | rush TDs | 0.69 | 2 | 4 |
| RB | 20+ runs | 0.88 | 2 | 7 |
| RB | yards after contact | 87.5 | 160 | 294 |
| RB | broken tackles | 0.64 | 2 | 4 |
| WR | targets | 9.9 | 15 | 23 |
| WR | receptions | 9.35 | 14 | 23 |
| WR | rec yards | 83.5 | 143 | 272 |
| WR | YAC | 23.0 | 48 | 102 |
| WR | rec TDs | 0.40 | 1 | 4 |
| WR | 20+ receptions | 0.82 | 2 | 4 |
| WR | contested catches | 1.02 | 3 | 6 |
| WR | bailouts | 0.31 | 1 | 5 |
| TE | receptions | 8.22 | 13 | 17 |
| TE | rec yards | 59.0 | 94 | 122 |
| TE | YAC | 17.6 | 37 | 58 |
| TE | contested catches | 0.98 | 2 | 8 |
| K | FGs made | 1.98 | 4 | 5 |
| K | FG yards | 76.3 | 135 | 207 |
| K | 45+ FGs | 0.71 | 2 | 3 |
| K | punts | 5.14 | 8 | 11 |
| K | punts inside 20 | 2.03 | 4 | 6 |
| K | punt longest | 59.5 | 65 | 72 |

**Anchor:** a metallic flat card should mean ~26 FP/week, matching Freebie (26.0
measured live). Divide 26 by the volume above to get the per-unit rate.

> **TE receptions are 88% of WR receptions (8.22 vs 9.35).** Safety Blanket pays
> **5.3/reception** and Possession pays **2.7** — the TE card pays 96% more per catch for
> 12% less volume. Safety Blanket measures 47.0 FP/week, the highest of any metallic card;
> Possession measures 21.4 and is correctly sized. **Fix Safety Blanket to ~3.2/reception
> as part of this work** — it is the single clearest balance defect in the tier.

## Two stats that do not exist yet

- **`goodThrows`** — there is no "well-placed ball" counter. `throws − badThrows` is 96%
  of throws (bad-throw rate is 4.1% at the bar of 45), which is far too common to trigger
  a card. Needs its own counter at a higher bar, calibrated to ~1/3 of throws so a QB
  posts 12-14 a game. One line in the recording block at `floosball_game.py:15317`, plus
  the `PassingStats` dataclass and `to_legacy_dict` (a stat missing from either silently
  never appears — `add_stat` skips unknown keys without erroring).
- **Extra points** — `xps` records nothing in the sim data. No XP card is possible until
  that is tracked.

## Blocker

`_dbStatsToCardFormat` (`fantasyTracker.py:60`) exposes **15 of 92** recorded stat keys to
the card layer, and does not take `returning_stats` as a parameter at all. Every NEW card
below is blocked on widening it. No design risk; do this first.

---

## How a family works

A **family** is one stat, three cards, one motif. The stat never changes as you climb —
only what the card does with it, and the names read as a set so the chain is visible.

    metallic      flat            every unit pays the same
    holographic   thresholded     units past a line pay more, or a shape of game doubles it
    prismatic     compounding     a streak across weeks, or odds that fill from the stat

**Universal cards are not rungs.** Odometer (sums pass + rush + receiving yards) and the
position-adaptive set (Crescendo, Squire, Spotlight Moment, Luminary, Traverse) key off a
GENERIC concept that changes meaning by position. They keep their own identity outside the
families — an earlier draft used Odometer as the top rung of three families at once, which
is exactly what the evolution idea rules out.

### Output type is part of the ladder

Metallic mints **15 FP / 4 FPx / 9 Floobits** today, and two of the four FPx cards measure
near-dead (Homer 1.5 FP at a 15% hit rate, Honor Roll 5.4 at 45%). In practice the base
FPx pool is Big Deal and Bandwagon, which is why every metallic multiplier feels like the
same two cards.

Three rules fix it without inventing premises:

1. **A family's three rungs are FP and FPx only, and not all the same type.** Floobits
   cards live outside the families entirely (owner call 2026-08-06), so a ladder is always
   a fantasy-points ladder and never changes currency partway up.
2. **Lumpy stats take FPx, not flat FP.** A stat under ~1/game (TDs) pays nothing most
   weeks as a flat card. As a multiplier the dead week costs you nothing and the live week
   compounds with the rest of the hand.
3. **Any metallic rung may mint as an FP *or* FPx print of the same stat.** Same rate
   basis, two prints. This is the cheapest way to widen the FPx pool — no new premise, no
   new stat, no new mechanic.

Rule 3 is what actually moves the number. Six FPx siblings takes metallic to roughly
**48% FP / 32% FPx / 20% Floobits**, against 54/14/32 today.

### Rare stats live OUTSIDE the families (owner call 2026-08-06)

Five stats are too rare to carry a family. To reach the ~26 FP metallic anchor each needs
an enormous per-unit value, so a typical week pays nothing and a p90 week pays double —
the wrong shape for a tier meant to be dependable, and there is not enough room above a
one-a-game stat to build three distinct rungs on it.

They are still good cards. They become **one-offs**: a single card at the tier whose shape
already is high-variance, with no ladder above or below.

| stat | mean/game | p90 | card | tier | why there |
|---|---|---|---|---|---|
| 20+ throws | 1.75 | 4 | *Haymaker* | holographic | ~1-2 a game, so it lands most weeks |
| contested catches | 1.02 | 3 | *Highpoint* | holographic | about one a game |
| 20+ runs | 0.88 | 2 | *Breakaway* | holographic | about one a game |
| broken tackles | 0.64 | 2 | *Houdini* | prismatic | chance card — odds fill from breaks |
| bailouts | 0.31 | 1 | *Custodian* | prismatic | rarest; belongs where variance is the point |

These share a character without being a family: each is a **single highlight moment**
rather than accumulated volume. That is exactly what the upper tiers are for — rarity buys
variance, and a card that pays on the one play you remember from the game is a better
prismatic than a better metallic.

**Bailout** = the receiver caught a ball thrown below the bad-throw bar (quality < 45),
credited only on the completion. The mirror of the QB's `badThrows`: bad throws run
1.56/game against 0.31 bailouts, so about one bad ball in five is caught anyway. It is the
stat that separates a receiver's contribution from the quality of throw he was given.

> **Touchdowns are lumpier still and stay in families anyway.** Rush TDs run 0.69/game and
> receiving TDs 0.40 — rarer than contested catches. They keep their ladders because they
> are the most legible event in football and the pool already supports them (Piñata,
> Squire, Spotlight Moment, Crescendo, Avalanche, Lead Blocker, Goal Line Vulture). Rule 2
> handles the lumpiness: **the TD families take FPx at metallic**, so a scoreless week
> costs nothing instead of reading as a dead card.

---

## QB

| family / motif | metallic | holographic | prismatic |
|---|---|---|---|
| **completions** — timekeeping | *Cadence* **FP** · 0.9/comp | *Rhythm* **FPx** past 20 | *Clockwork* **FP** streak at 25+ |
| **pass yards** — flight | *Slipstream* **FPx** per 100 | *Updraft* **FP** gates 200/300/400 | *Stratosphere* **FPx** streak at 300 |
| **pass TDs** — ordnance | *Bombardier* **FPx** | *Salvo* **FP** doubled at 3+ | *Barrage* **FP** escalating odds |
| **throw quality** — marksmanship | **Gunslinger** **FP** *(re-pointed)* | *Marksman* **FPx** on a clean sheet | *Dead Eye* **FP** streak |

One-offs: *Attention* **FPx** (targets), *Altitude* (holo, aDOT above 8), *Haymaker*
(holo, 20+ throws), **Air Raid** (shipped, Floobits on pass TDs).
Blocked: throw quality needs the new `goodThrows` counter.

## RB

| family / motif | metallic | holographic | prismatic |
|---|---|---|---|
| **carries** — labour | **Workhorse** **FP** | *Beast of Burden* **FPx** at 25+ | *Iron Man* **FP** streak at 20 |
| **rush yards** — journey | **Expedition** **FP** | **Trailblazer** **FPx** *(was Stampede)* | *Odyssey* **FP** streak at 100 |
| **rush TDs** — force | *Battering Ram* **FPx** | **Lead Blocker** **FP** | — |
| **yards after contact** — mass | *Freight* **FP** · 0.3/yd | *Grinder* **FPx** when YAC > half | *Landslide* **FP** streak at 100 |

One-offs: *Breakaway* (holo, 20+ runs), *Houdini* (prismatic, chance filling from broken
tackles), **Goal Line Vulture** (shipped, Floobits on rush TDs).

Yards after contact only became a real stat this session (80% of rush yards, 87.5/game).

## WR / TE

| family / motif | metallic | holographic | prismatic |
|---|---|---|---|
| **receptions** — custody | **Possession** (WR) **FP** · **Safety Blanket** (TE) **FP** | *Custody* **FPx** past 8 | *Tenure* **FP** streak at 8 |
| **receiving yards** — territory | *Frontier* **FP** · 0.31/yd | *Territory* **FPx** gates 75/125/175 | *Dominion* **FP** streak at 100 |
| **receiving TDs** — the end zone | *Paydirt* **FPx** | *End Zone* **FP** doubled at 2+ | *Promised Land* **FP** escalating odds |
| **YAC** — escape | **Slippery** **FP** | **Jailbreak** **FPx** | *Getaway* **FP** streak at 40 |

One-offs: **Trebuchet** (shipped, longest catch), *Highpoint* (holo, contested catches),
*Custodian* (prismatic, bailouts), **Industrious** (shipped, Floobits on TE receptions).
**Receiving yards is the biggest hole in the pool** — 83.5/game, the most-produced skill
stat in the game, and no card below prismatic today.

## K

| family / motif | metallic | holographic | prismatic |
|---|---|---|---|
| **punting** — burial | *Pinpoint* **FP** · 13/punt inside 20 | *Coffin Corner* **FPx** inside the 10 | *Undertaker* **FP** streak |
| **returns** — the runback | *Runback* **FP** per return yard | — | *House Call* **FP** odds on return TDs |

**Field goals need pruning, not building.** The kicker already carries six cards —
Three Pointer, Good Neighbor, Range, Sniper, On Fire, Leg Day — on a stat line of 1.98
FGs a game, and Three Pointer alone measures 39.0 FP/week.

Returns are unblocked as of this session's `returning_stats` fix; punt placement only
became measurable this session.

---

## Build order

1. **Widen `_dbStatsToCardFormat`** — 15 of 92 stat keys reach the card layer and
   `returning_stats` is not a parameter at all. Everything is blocked on this.
2. **Add the `goodThrows` counter**, calibrated to ~1/3 of throws (~12-14/game).
3. **Re-point Gunslinger** onto it, add *Slipstream* for pass yards. Must follow step 2 or
   the card reads zero.
4. **The four unconstrained families** — receiving yards, yards after contact, punting,
   receiving TDs. Nothing shipped limits them and receiving yards is the biggest gap.
5. **Retune the two outliers** — Safety Blanket 5.3 → ~3.2 per reception, Three Pointer
   down from 39.0 FP/week.

Counts: **12 families + 11 one-offs, ~31 new cards** including the FPx siblings.
Three shipped Floobits cards (Air Raid, Goal Line Vulture, Industrious) moved OUT of
families into the one-off pool; no new cards were needed to replace them, because the
TD families take FPx at metallic under rule 2 regardless.

One-offs in full: *Haymaker*, *Highpoint*, *Breakaway*, *Houdini*, *Custodian* (the five
rare-stat cards), *Attention* (targets, FPx), *Altitude* (holo, aDOT), plus shipped
**Trebuchet**, **Air Raid**, **Goal Line Vulture** and **Industrious**.

## Renames (owner-approved 2026-08-06)

Renaming is **display-only**: `displayName`, `tagline` and `detail` live in the stored
`effect_config`, so the effect KEY is untouched — no compute or registry churn, and no
risk to how an existing card scores. Like the numeric params, the name is frozen at mint,
so a rename only reaches newly-minted templates. Shipping on `next-season` lands it
uniformly at the season cutover with no migration; a mid-season deploy would split the
name across two cohorts of the same card.

### 1. Gunslinger moves to throw quality; pass yards gets a new name

Gunslinger reads as marksmanship but measured YARDAGE — that mismatch was the real
problem, not the name. Firearms were also overloaded three ways (**Sniper** on the
kicker, **Sharpshooter** on the diamond amplifier, **Gunslinger** on the QB) while only
one of them keyed off accuracy. Moving Gunslinger onto throw quality fixes both at once:
the motif lands on the stat it describes, and firearms now cluster on accuracy.

**Throw quality — marksmanship** (blocked on the new `goodThrows` stat)

| | card |
|---|---|
| metallic | **Gunslinger** (name kept, re-pointed) |
| holographic | *Marksman* |
| prismatic | *Dead Eye* |

**Pass yards — flight** (new family, new effect)

| | card | why |
|---|---|---|
| metallic | *Slipstream* | pass yards travel through the air |
| holographic | *Updraft* | |
| prismatic | *Stratosphere* | escalating altitude |

> **This one is not display-only.** Every other rename here changes a string; this moves
> Gunslinger from `passYards` to `goodThrows`, which means a new compute path, a new param
> builder (per good throw, not per 100 yards) and a rate resized against ~12-14 good throws
> a game instead of 229.9 yards. Pass yards needs its own new effect key for *Slipstream*.
> Both are safe **only at the season boundary** — params and names are frozen at mint, so
> a mid-season deploy leaves the old Gunslinger scoring pass yards under the same name.
>
> **Ordering constraint:** the `goodThrows` counter must land BEFORE Gunslinger is
> re-pointed, or the card reads zero.

**Considered and rejected:** Gunslinger on completions. Semantically the better fit — the
term connotes volume and fearlessness more than precision — but completions already carries
*Cadence → Rhythm → Clockwork*, and Gunslinger cannot head that family without breaking
the motif that made the evolution idea click.

### 2. Rush yards — Stampede is a herd in a journey family

| | old | new | why |
|---|---|---|---|
| metallic | **Expedition** | *(keep)* | sets the journey motif |
| holographic | **Stampede** | *Trailblazer* | joins the journey |
| prismatic | — | *Odyssey* | the long haul |

### 3. Receptions — two shipped cards set the motif

The metallic rung here is TWO position-exclusive cards (Possession on WR, Safety Blanket
on TE), so it is one family with two entry points rather than a conflict. Motif is
custody and reliability.

| | old | new | why |
|---|---|---|---|
| metallic (WR) | **Possession** | *(keep)* | sets the motif |
| metallic (TE) | **Safety Blanket** | *(keep)* | best-known TE term in football; reads as reliability |
| holographic | — | *Custody* | |
| prismatic | — | *Tenure* | held the longest |

**Industrious is no longer renamed.** The *Steward* rename existed only to pull it into the
custody motif; with Floobits cards living outside the families it keeps its own name and
its own identity. Two renames, not three.

Safety Blanket keeps its name and still needs its **rate cut from 5.3 to ~3.2 per
reception** — that is a balance fix, independent of naming.

## Settled

- **Offense only** (owner call 2026-08-06). Defensive stats are recorded for every player
  through their defensive position — sacks, tackles, INTs, TFL, forced fumbles, pass
  breakups — and remain the largest surface no card reads. Deferred, not rejected:
  offensive stats are the ones a user actually sees.
- **Floobits cards are one-offs** (owner call 2026-08-06). No Floobits card sits in a
  family. This removes the sibling problem entirely — a family's rungs are FP and FPx only,
  and the nine shipped Floobits cards keep their own identities outside the ladder.

## Open questions for the owner

1. **Names.** All *italic* names are candidates.
2. **Field goals.** The kicker carries six shipped cards on 1.98 FGs a game and Three
   Pointer alone measures 39.0 FP/week. This wants pruning, which is a separate pass from
   the ladder build.
