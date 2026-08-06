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

## QB

| stat | metallic | holographic | prismatic |
|---|---|---|---|
| pass yards | **Gunslinger** (exists) | NEW *Aerialist* — tiered gates at 200/300/400 | **Odometer** (exists) |
| pass TDs | **Air Raid** (exists, Floobits) · NEW *Bombardier* (FP) | NEW *Salvo* — flat, doubled at 3+ TDs | **Crescendo** (exists) |
| completions | NEW *Cadence* — +0.9 FP/completion | NEW *Rhythm* — +FPx per completion past 20 | NEW *Clockwork* — streak on 25+ completions |
| 20+ throws | NEW *Haymaker* — +15 FP per 20+ throw | — | — |
| good throws | NEW *Draftsman* (FPx) — needs the new stat | — | — |
| air yards | — | NEW *Altitude* — scales with aDOT above 8 | — |

## RB

| stat | metallic | holographic | prismatic |
|---|---|---|---|
| carries | **Workhorse** (exists) | NEW *Anvil* — flat, bonus at 25+ carries | NEW *Relentless* — streak on 20+ carries |
| rush yards | **Expedition** (exists) | **Stampede** (exists) | **Odometer** (exists) |
| rush TDs | **Goal Line Vulture** (exists, Floobits) · NEW *Battering Ram* (FP) | **Lead Blocker** (exists) | — |
| yards after contact | NEW *Freight* — +0.3 FP/yard | NEW *Grinder* — +FPx when YAC exceeds half of rush yards | — |
| broken tackles | — | NEW *Houdini* — +18 FP per break (0.64/game) | NEW *Escape Artist* — chance fills from breaks |
| 20+ runs | NEW *Breakaway* — +28 FP per 20+ run | — | — |

## WR / TE

| stat | metallic | holographic | prismatic |
|---|---|---|---|
| receptions | **Possession** (WR, exists) · **Safety Blanket** (TE, exists — *retune to 3.2*) · **Industrious** (TE, Floobits) | NEW *Chainmover* — +FPx per catch past 8 | NEW *Sure Thing* — streak on 8+ catches |
| rec yards | **NEW *Frontier*** — +0.31 FP/yard · **the biggest gap in the pool** | NEW *Territory* — tiered gates at 75/125/175 | **Odometer** (exists) |
| rec TDs | NEW *Paydirt* — +55 FP per rec TD | NEW *End Zone* — flat, doubled at 2+ | — |
| YAC | **Slippery** (exists) | **Jailbreak** (exists) | — |
| targets | NEW *Attention* (FPx) — pays on volume even without the catch | — | — |
| contested catches | — | NEW *Highpoint* — +25 FP per contested catch | NEW *Contortionist* — chance fills from contested rate |
| bailouts | — | NEW *Custodian* — +80 FP per bailout (0.31/game) | — |
| longest catch | — | **Trebuchet** (exists) | — |

## K

| stat | metallic | holographic | prismatic |
|---|---|---|---|
| FGs made | **Three Pointer** (exists — measures 39.0 FP, *retune down*) | **Good Neighbor** (exists, Floobits) | **On Fire** (exists, streak) |
| FG yards | NEW *Surveyor's Mark* (FPx) | **Range** (exists) | — |
| 45+ FGs | **Sniper** (exists) | — | **Leg Day** (exists, streak) |
| punts inside 20 | NEW *Pinpoint* — +13 FP each | NEW *Coffin Corner* — bonus for inside-10 | — |
| punt longest | — | NEW *Cannon* — scales past 60 yards | — |
| punt returns | NEW *Runback* — return yards, any skill player | — | NEW *House Call* — chance on return TDs |

---

## Output-type balance

Metallic currently mints **17 FP / 4 FPx / 13 Floobits**, and two of the four FPx cards
measure near-dead (Homer 1.5 FP at 15% hit, Honor Roll 5.4 at 45%). The NEW metallic
cards above are deliberately weighted toward FPx — *Draftsman*, *Attention*,
*Surveyor's Mark* — and any of the flat FP cards can also mint as an FPx variant on the
same stat, which is the cheapest way to widen the pool without inventing premises.

Target after the build: roughly **half FP, a third FPx, the rest Floobits** at metallic.

## Open questions for the owner

1. **Names.** All *italic* names are candidates only.
2. **Scope.** 24 new cards as drafted. Trim by dropping the rarer-stat cards (bailouts,
   broken tackles, 20+ plays) which need large per-unit values to reach the anchor and so
   land as high-variance cards at a tier meant to be dependable.
3. **Defense.** Excluded here per the "offensive stats" scope, but every rostered player
   produces sacks, tackles, INTs, TFL, forced fumbles and pass breakups through their
   defensive position, and no card reads any of it. Largest untouched surface in the game.
4. **Floobits share.** 13 of 28 metallic cards pay Floobits — a larger share than any
   tier above it. Worth deciding whether that is intended.
