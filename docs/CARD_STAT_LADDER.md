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
only what the card does with it, and the names should read as a set so the chain is
visible on the shelf.

    metallic      flat            every unit pays the same
    holographic   thresholded     units past a line pay more, or a shape of game doubles it
    prismatic     compounding     a streak across weeks, or odds that fill from the stat

**Universal cards are not rungs.** Odometer (sums pass + rush + receiving yards) and the
position-adaptive set (Crescendo, Squire, Spotlight Moment, Luminary, Traverse) key off a
GENERIC concept that changes meaning by position. They keep their own identity and sit
outside the families — an earlier draft used Odometer as the prismatic rung for three
different families at once, which is exactly what the evolution idea rules out.

Where a family already contains a shipped card, the other two rungs are built around
**that card's** motif, or the shipped card gets renamed. Mixed families
(`Gunslinger → Aerialist → Odometer`) read as three unrelated ideas and defeat the point.

All names below are candidates.

---

## QB

**Completions — timekeeping.** The metronomic passer. *(the shape this whole idea came from)*

| | card | mechanic |
|---|---|---|
| metallic | *Cadence* | +0.9 FP per completion |
| holographic | *Rhythm* | +FPx per completion past 20 |
| prismatic | *Clockwork* | streak, grows each week they clear 25 completions |

**Pass yards — flight.** New family. **Gunslinger** moves out of it onto throw quality
(see Renames), so the shipped effect is renamed and the family is built fresh.

| | card | mechanic |
|---|---|---|
| metallic | *Slipstream* | +FP per 100 pass yards |
| holographic | *Updraft* | tiered gates at 200 / 300 / 400 |
| prismatic | *Stratosphere* | streak on 300-yard weeks |

**Pass TDs — ordnance.** Contains **Air Raid** (shipped, pays Floobits), which fits the
motif cleanly. Needs an FP sibling since the metallic rung currently pays the wrong currency.

| | card | mechanic |
|---|---|---|
| metallic | **Air Raid** (shipped, Floobits) · *Bombardier* (FP) | flat per pass TD |
| holographic | *Salvo* | flat, doubled at 3+ TDs |
| prismatic | *Barrage* | escalating odds per TD |

**Throw quality — marksmanship.** Blocked on the new `goodThrows` stat. Takes the
**Gunslinger** name, which finally sits on a stat it describes.

| | card | mechanic |
|---|---|---|
| metallic | **Gunslinger** (re-pointed) | +FP per well-placed ball (~12-14/game) |
| holographic | *Marksman* | bonus when the bad-throw count stays at zero |
| prismatic | *Dead Eye* | streak on clean-sheet weeks |

**Unfamilied QB one-offs:** *Haymaker* (+15 FP per 20+ throw, 1.75/game),
*Altitude* (holo, scales with aDOT above 8).

## RB

**Carries — labour.** Contains **Workhorse** (shipped), motif fits.

| | card | mechanic |
|---|---|---|
| metallic | **Workhorse** (shipped) | +FP per carry |
| holographic | *Beast of Burden* | flat, bonus at 25+ carries |
| prismatic | *Iron Man* | streak on 20-carry weeks |

**Rush yards — journey.** Contains **Expedition** and **Stampede** (both shipped).
Expedition is a journey, Stampede is a herd — already mixed. One should move.

| | card | mechanic |
|---|---|---|
| metallic | **Expedition** (shipped) | +FP per rush yard |
| holographic | **Stampede** (shipped) | FPx on rush yardage |
| prismatic | *Odyssey* | streak on 100-yard weeks |

**Yards after contact — mass.** Wholly new; the stat only became real this session
(80% of rush yards, mean 87.5/game).

| | card | mechanic |
|---|---|---|
| metallic | *Freight* | +0.3 FP per yard after contact |
| holographic | *Grinder* | +FPx when YAC exceeds half of rush yards |
| prismatic | *Landslide* | streak on 100-yard-after-contact weeks |

**Rush TDs — force.** Contains **Goal Line Vulture** (Floobits) and **Lead Blocker**.

| | card | mechanic |
|---|---|---|
| metallic | **Goal Line Vulture** (shipped, Floobits) · *Battering Ram* (FP) | flat per rush TD |
| holographic | **Lead Blocker** (shipped) | flat per rush TD |
| prismatic | — | |

**Broken tackles — escape.** Rare stat (0.64/game) — see the variance note below.

| | card | mechanic |
|---|---|---|
| metallic | — | too rare for a dependable tier |
| holographic | *Houdini* | +18 FP per break |
| prismatic | *Vanishing Act* | chance whose odds fill from breaks |

**Unfamilied RB one-off:** *Breakaway* (+28 FP per 20+ run, 0.88/game).

## WR / TE

**Receptions — custody.** Contains **Possession** (WR), **Safety Blanket** (TE, *retune to
3.2/rec*) and **Industrious** (TE, Floobits). Possession's motif carries the family.

| | card | mechanic |
|---|---|---|
| metallic | **Possession** (WR) · **Safety Blanket** (TE) | +FP per reception |
| holographic | *Custody* | +FPx per catch past 8 |
| prismatic | *Tenure* | streak on 8-catch weeks |

**Receiving yards — territory.** **Entirely absent below prismatic today — the biggest
hole in the pool.** Most-produced skill stat in the game at 83.5 yards a game.

| | card | mechanic |
|---|---|---|
| metallic | *Frontier* | +0.31 FP per receiving yard |
| holographic | *Territory* | tiered gates at 75 / 125 / 175 |
| prismatic | *Dominion* | streak on 100-yard weeks |

**Receiving TDs — the end zone.** No card anywhere today.

| | card | mechanic |
|---|---|---|
| metallic | *Paydirt* | +55 FP per receiving TD |
| holographic | *End Zone* | flat, doubled at 2+ |
| prismatic | *Promised Land* | escalating odds per TD |

**YAC — escape.** Contains **Slippery** and **Jailbreak** (both shipped); the motifs
already agree.

| | card | mechanic |
|---|---|---|
| metallic | **Slippery** (shipped) | +FP per YAC yard |
| holographic | **Jailbreak** (shipped) | FPx on YAC |
| prismatic | *Getaway* | streak on 40-YAC weeks |

**Contested catches — the aerial contest.** Nothing today (1.02/game).

| | card | mechanic |
|---|---|---|
| metallic | — | too rare for a dependable tier |
| holographic | *Highpoint* | +25 FP per contested catch |
| prismatic | *Larceny* | chance filling from contested rate |

**Unfamilied WR one-offs:** *Attention* (FPx on targets, pays without the catch),
*Custodian* (holo, +80 FP per bailout, 0.31/game), **Trebuchet** (shipped, longest catch).

## K

**Field goals — the kick itself.** Contains **Three Pointer** (*measures 39.0 FP, retune
down*), **Good Neighbor**, **Range**, **Sniper**, **On Fire**, **Leg Day**. The kicker is
already the best-served position; it needs pruning, not additions.

**Punting — burial.** Wholly new; punt placement only became a real stat this session.

| | card | mechanic |
|---|---|---|
| metallic | *Pinpoint* | +13 FP per punt inside the 20 (2.03/game) |
| holographic | *Coffin Corner* | bonus for inside the 10 |
| prismatic | *Undertaker* | streak on multi-pin weeks |

**Returns — the runback.** Any skill player. Unblocked as of this session's
`returning_stats` fix.

| | card | mechanic |
|---|---|---|
| metallic | *Runback* | +FP per return yard |
| holographic | — | |
| prismatic | *House Call* | chance on return TDs |


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

### 3. Receptions — three shipped cards, three motifs

The metallic rung here is TWO position-exclusive cards (Possession on WR, Safety Blanket
on TE), so it is one family with two entry points rather than a conflict. Motif is
custody and reliability.

| | old | new | why |
|---|---|---|---|
| metallic (WR) | **Possession** | *(keep)* | sets the motif |
| metallic (TE) | **Safety Blanket** | *(keep)* | best-known TE term in football; reads as reliability |
| metallic (TE, Floobits) | **Industrious** | *Steward* | labour → custody |
| holographic | — | *Custody* | |
| prismatic | — | *Tenure* | held the longest |

Safety Blanket keeps its name and still needs its **rate cut from 5.3 to ~3.2 per
reception** — that is a balance fix, independent of naming.

## Output-type balance

Metallic currently mints **17 FP / 4 FPx / 13 Floobits**, and two of the four FPx cards
measure near-dead (Homer 1.5 FP at 15% hit, Honor Roll 5.4 at 45%). The NEW metallic
cards above are deliberately weighted toward FPx — *Draftsman*, *Attention*,
*Surveyor's Mark* — and any of the flat FP cards can also mint as an FPx variant on the
same stat, which is the cheapest way to widen the pool without inventing premises.

Target after the build: roughly **half FP, a third FPx, the rest Floobits** at metallic.

## Open questions for the owner

1. **Names.** All *italic* names are candidates only.
2. **Scope.** 14 families plus 6 one-offs. Trim by dropping the rare-stat families
   (broken tackles 0.64/game, contested catches 1.02, bailouts 0.31) — to reach the ~26 FP
   anchor they need large per-unit values, so a typical week pays nothing and a p90 week
   pays double. That is a fine shape at prismatic and the wrong shape at metallic, which
   is why those families start at holographic above.
3. **Mixed families.** RESOLVED — see Renames. Three shipped cards get new display
   names (Gunslinger, Stampede, Industrious); Possession and Safety Blanket keep theirs.
4. **Defense.** Excluded here per the "offensive stats" scope, but every rostered player
   produces sacks, tackles, INTs, TFL, forced fumbles and pass breakups through their
   defensive position, and no card reads any of it. Largest untouched surface in the game.
5. **Floobits share.** 13 of 28 metallic cards pay Floobits — a larger share than any
   tier above it. Worth deciding whether that is intended.
