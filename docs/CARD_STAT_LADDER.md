# Card Stat Ladder — offensive stats

**Status:** draft for owner review. Nothing here is built.
**Branch:** `next-season`

The foundation card set, rebuilt so every card keys off a real box-score stat. Same
stat appears at three rarities with a rising mechanic, so a player can collect the
progression for a stat they like watching.

    metallic      flat, always on      "+X FP per reception"
    holographic   thresholded/tiered   "+X per reception, doubled on 20+ yard catches"
    prismatic     compounding          "streak grows each week they clear 8 catches"

Rarity buys **ceiling**. Every tier scores about the same on a typical week; holographic
and prismatic score far more on a big one. Median holds flat while p90 rises ~1.3x and
~1.5x and p99 ~1.4x and ~1.7x. See *Same typical week, bigger tail*.

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

## What this replaces

Six cards were retired to make room (commit `a66af81`). All keyed off
`playerPerformanceRatings`, a percentile-of-production score computed weekly in memory and
surfaced nowhere a user can see, so "is my roster overperforming?" was unanswerable while
setting a lineup:

**Hot Stove** (resplendent) · **Windfall** · **Buy Low** · **Reclamation** ·
**Rising Tide** · **Spectacle**

Retirement pattern: dropped from `SHARED_EFFECT_POOL` so nothing new mints; compute
functions and `EFFECT_EDITION_TIER` entries stay so any card already carrying them still
scores. Metallic went 32 → 28 mintable, holographic 44 → 42. Twelve effects were already
out of circulation the same way before this (drought, home_alone, house_money, indemnity,
martyr, quiet_storm, rock_bottom, sandbagger, stockpiler, surplus, underdog, vagabond).

### Still rating-keyed — NOT yet resolved

The audit found **17** effects reading a rating or performance-rating proxy. Six are
retired above. **Ten remain live**, in two groups:

| group | effects | note |
|---|---|---|
| star count | Entourage, Showoff, Patient, Dark Horse | reads a rating band; legible but static — cannot change during a week, so the card has no game-day story |
| chance fill | Scrappy, Babysitter, Last Resort, Sleeper, Consolation Prize | **already half fixed** — `CARD_CHANCE_FP_WEIGHT` is 0.5, so half the trigger bar comes from the on-card player's FP. Only the other half (counting low-rated roster players) is a proxy |

The chance-fill group is the cheaper fix by far: swap the `conditionFill` input for a
stat-based one and the mechanic is untouched. Neither group is addressed by this plan.

## How the numbers here were measured

Harness: **`simcheck_effect_spread.py`** (committed). It isolates ONE effect at a time —
five slots hold no-effect floor prints, the sixth holds the card under test on a real
player — and differences against the same lineup scored with no live card at all.

    PROBE_EDITION=metallic PROBE_TRIALS=40 .venv/bin/python simcheck_effect_spread.py

Three caveats that matter when re-running:

- **Isolation understates hand-synergy cards.** Gold Rush pays per OTHER Floobits card in
  hand, so in a lineup of floor prints it is structurally zero. Same for Diversified,
  Stack, Backfield Buddies, Rookie Hype. Metallic is mostly standalone cards and
  holographic mostly synergy cards, so tier maxima are NOT comparable across editions.
- **FP and Floobits are different currencies** and do not belong in one column. Trust Fund
  reads 0 FP and pays 57 Floobits.
- **Measure the LIVE path.** `buildProjectionContext` leaves the context in projection
  mode, where the FP power bar returns a fractional clear PROBABILITY and every payout
  comes out EV-scaled. Week-end banking is pure on/off. The harness forces
  `ctx.isProjection = False`; without it hit rates read 100% and payouts are smoothed.

Two earlier instrument traps, both fixed, both of which would have been reported as
balance findings: a booted snapshot has no season performance ratings (so every
over/underperformer effect counted zero players and looked dead), and the filler cards'
own team-stacking FPx leaks into an undifferenced measurement, giving every dead effect a
phantom 1-2 FP.

### Metallic, live path, marginal FP per week (40 trials each)

| card | FP | hit% | p90 | | card | FP | hit% | p90 |
|---|---|---|---|---|---|---|---|---|
| Safety Blanket | 47.0 | 58% | 112.0 | | Bandwagon | 9.1 | 70% | 16.6 |
| Three Pointer | 39.0 | 68% | 90.8 | | Honor Roll | 5.4 | 45% | 18.2 |
| RNG | 33.9 | 68% | 65.9 | | Big Deal | 4.5 | 58% | 9.2 |
| Workhorse | 30.7 | 60% | 87.0 | | Showoff | 2.6 | 22% | 10.5 |
| Believe | 27.7 | 62% | 46.8 | | Slippery | 2.5 | 62% | 5.3 |
| Gunslinger | 26.5 | 70% | 58.3 | | Homer | 1.5 | 15% | 6.5 |
| Freebie | 26.0 | 65% | 43.6 | | | | | |
| Garbage Time | 24.9 | 60% | 60.4 | | *Floobits cards* | | | |
| Entourage | 23.9 | 65% | 46.6 | | Trust Fund | — | 78% | 57.4F |
| Possession | 21.4 | 65% | 42.2 | | Consolation Prize | — | 100% | 32.0F |
| Sniper | 13.1 | 52% | 29.2 | | Industrious | — | 62% | 26.9F |
| Expedition | 10.5 | 68% | 22.3 | | Allowance | — | 60% | 13.4F |
| Touchdown Piñata | 10.4 | 48% | 30.5 | | Air Raid | — | 58% | 16.7F |

Freebie at 26.0 is the anchor the metallic rates in this plan are sized against. The
19× spread between Safety Blanket and Homer is the problem this plan exists to fix.

---


### Retired this session

Ten cards dropped from the minting pool. Compute functions and `EFFECT_EDITION_TIER`
entries stay so any card already owned still scores.

| card | edition | keyed off | why |
|---|---|---|---|
| **Hot Stove** (resplendent) | metallic | overperforming roster players | `playerPerformanceRatings` is computed weekly in memory and shown nowhere; unanswerable while setting a lineup |
| **Windfall** | metallic | overperforming roster players | as above |
| **Buy Low** | metallic | underperforming roster players | as above |
| **Reclamation** | metallic | underperforming roster players | as above |
| **Rising Tide** | holographic | overperforming roster players | as above |
| **Spectacle** | holographic | points overperformed by | as above |
| **Scrappy** | prismatic | 2★-or-lower roster players | pays for fielding weak players; under fusion an equipped card IS a rostered player, so almost nobody does |
| **Sleeper** | prismatic | sub-3★ roster players | as above |
| **Patient** | holographic | a sub-3★ slot left unchanged | as above |
| **Dark Horse** | prismatic | stars UNDER 5 on the card player | as above |

**Entourage** (3★+) and **Showoff** (5★) are KEPT. The objection is to rewarding weakness,
not to reading a rating.

### Also retired — the standings-lookup cards

| card | edition | keyed off |
|---|---|---|
| **Castaway** | holographic | a roster player on a sub-.500 team |
| **Domination** | holographic | a roster player on a top-6 team |
| **Comeback Kid** | holographic | a roster player whose team missed the playoffs LAST season |

Each paid off a fact about a roster player's TEAM rather than anything the player did.
Playing them well meant leaving the fantasy page to read the standings, or in Comeback
Kid's case last season's final table, for a modest per-player bonus — and the answer moved
under you as the season went on. **Walk Off is KEPT**: it pays on this player's own Q4 and
OT scores, which is a stat.

**Still live and unresolved:** *Babysitter* and *Consolation Prize* fill their chance bar
from roster players under an FP threshold. That is low PRODUCTION, not low rating, so a
high-rated player still triggers them on a cold week and they are not structurally dead
the way the four above were. They are the last survivors of the "worse is better" class
the fusion rework retired (martyr, underdog, rock_bottom, indemnity), so consistency argues
for retiring them too, but that is a separate call.

## Full card catalogue

Every mintable effect, by rarity then output type, with the exact tagline, back-of-card
text and detail line. Existing entries are pulled verbatim from `cardEffects.py`; **`NEW`**
marks a card this plan adds, and a note in the detail column marks a card this plan
changes.

Detail lines use `{placeholder}` tokens that resolve at mint from the card player's rating.

### Metallic — 38 cards

*FP 20  ·  FPx 9  ·  Floobits 9*


#### Metallic · FP

| card | tagline | back of card | detail |
|---|---|---|---|
| **Believe** | Reward the faithful | Your faith rewarded. FP scaling with your favorite team's season wins. Bonus floobits when they win this week. | +{perWinFP} FP per favorite-team season win, +{floobitsOnTrigger}F when they win this week |
| **Cadence** **`NEW`** | Keep the chains moving | Tick, tick, tick. FP for every completion this player makes. | +{perCompletionFP} FP for every completion by this player |
| **Entourage** | Seeing stars | Seeing stars. Bonus FP for each high-rated player on your roster. | +{perPlayerFP} FP for every roster player with {minStars}★+ |
| **Expedition** | Marching downfield | Yards are yards. FP that scales with how many rushing yards this player gains. | +{perFiftyYardsFP} FP for every 50 rushing yards in one game by this player |
| **Freebie** | Free real estate | It's free. Bonus FP every week. | +{baseFP} FP per week |
| **Freight** **`NEW`** | Hard to stop | The first hit never finishes the job. FP for every yard gained after contact. | +{perYardFP} FP per yard after contact by this player |
| **Frontier** **`NEW`** | Always pushing out | Every yard is new ground. FP for every receiving yard. | +{perYardFP} FP per receiving yard by this player |
| **Garbage Time** | Participation trophies | Hey, they showed up. Bonus FP for each roster player who doesn't score a TD. | +{perPlayerFP} FP for every roster player with 0 TDs |
| **Gunslinger** | Puts it on a dime | Placement, not power. FP for every well-placed ball this player throws. | +{perGoodThrowFP} FP for every well-placed throw by this player<br>*CHANGED — re-pointed from pass yards to throw quality; needs the new `goodThrows` counter. New copy below.* |
| **Pinpoint** **`NEW`** | Drop it on a dime | Placement over power. FP for every punt downed inside the 20. | +{perPuntFP} FP per punt downed inside the 20 |
| **Possession** | Catch everything | Chain-mover. FP that scales with how many catches this player hauls in. | +{perReceptionFP} FP for every reception by this player in a game |
| **RNG** | Feeling lucky? | Feeling lucky? Random FP rolled each week. | Random +{minFP}–{maxFP} FP each week |
| **Runback** **`NEW`** | Bring it out | The play starts on the catch. FP for every punt return yard. | +{perYardFP} FP per punt return yard by this player |
| **Safety Blanket** | Reliable target | Every QB needs one. FP scaling with receptions by this player. | +{perReceptionFP} FP per reception by this player in a game<br>*RETUNED — 5.3 to ~3.2 FP per reception. Measured 47.0 FP/week, highest of any metallic card.* |
| **Showoff** | Star power | Stack the studs. FP per 5-star player on your roster. | +{perStarFP} FP per 5-star roster player |
| **Slippery** | Can't bring me down | Yards after the catch turn into points. FP that scales with this player's YAC. | +{perYacFP} FP per 10 yards after catch by this player in a game |
| **Sniper** | From downtown | From long range. FP for each field goal this player makes from 40+ yards out. | +{perFgFP} FP per 40+ yard FG by this player in a game |
| **Three Pointer** | Count it | Three points for them, bonus for you. FP for every kicker FG. | +{perFgFP} FP for every FG this player makes<br>*RETUNED down — measured 39.0 FP/week, second highest at metallic.* |
| **Touchdown Piñata** | Smash for points | Every house call fills the piñata. Bonus FP per roster TD. | +{perTdFP} FP for every TD your roster scores |
| **Workhorse** | Feed the beast | Pound the rock. FP scaling with rushing attempts by this player. | +{perAttemptFP} FP for every rushing attempt in one game by this player |

#### Metallic · FPx

| card | tagline | back of card | detail |
|---|---|---|---|
| **Attention** **`NEW`** | Feed the target | The ball is coming down there, caught or not. FPx for every target. | +{perTargetMult} FPx for every target by this player |
| **Bandwagon** | Get in, loser | Hop on the bandwagon. FPx whenever your favorite team wins. | +{rewardDelta} FPx when your favorite team wins |
| **Battering Ram** **`NEW`** | Straight through | No finesse required. FPx for every rushing touchdown. | +{perTdMult} FPx for every rushing TD by this player |
| **Big Deal** | Kind of a big deal | Don't you know who I am? Flat FPx on your total score. | +{xMultDelta} FPx |
| **Bombardier** **`NEW`** | Target acquired | Precision from altitude. FPx for every passing touchdown. | +{perTdMult} FPx for every passing TD by this player |
| **Homer** | Hometown discount | The home crowd lifts everyone. FPx per roster player on your favorite team. | +{perPlayerMult} FPx per roster player on your favorite team. Max +{maxDelta} FPx. |
| **Honor Roll** | Straight A's | Make the grade. FPx per roster player putting up 15+ FP this week. | +FPx when this player clears {fpThreshold}+ FP this week, up to +{maxDelta} FPx on a big game. |
| **Paydirt** **`NEW`** | Cash in | Cross the line, collect. FPx for every receiving touchdown. | +{perTdMult} FPx for every receiving TD by this player |
| **Slipstream** **`NEW`** | Riding the air | The ball hangs and the yards pile up. FPx scaling with passing yards. | +{perHundredMult} FPx for every 100 passing yards by this player |

#### Metallic · Floobits

| card | tagline | back of card | detail |
|---|---|---|---|
| **Air Raid** | Bombs away | Death from above. Floobits for each passing TD this player throws. | {perTdFloobits} Floobits for every passing TD in one game by this player |
| **Allowance** | Weekly pocket money | Don't spend it all in one place. Free Floobits every week just for existing. | {floobits} Floobits per week |
| **Consolation Prize** | Better luck next time | Here's a little something for your troubles. Guaranteed Floobits floor plus a chance at enhanced Floobits. The trigger bar fills from this player's own FP and from each roster player who has a bad week. | +{baseFloobits}F guaranteed, chance at {enhancedFloobits}F. Trigger odds fill from this player's FP plus each roster player under {fpThreshold} FP. |
| **Goal Line Vulture** | Opportunistic scavenging | Vulture season. Floobits for every rushing TD this player punches in. | {perTdFloobits} Floobits for every rushing TD by this player in a game |
| **Gold Rush** | Floobits love company | Floobits cards amplify each other. Floobits bonus for each other floobits card in your hand. | {perCardFloobits} Floobits per other Floobits card in your hand |
| **Industrious** | Honest work | Honest work deserves honest pay. Floobits scaling with receptions by this player. | {perReceptionFloobits} Floobits per reception by this player in a game |
| **Piggy Bank** | Points into coins | Automatic savings plan. Converts a chunk of this player's total FP into Floobits. | {fpPercent}% of this player's FP → Floobits |
| **Trust Fund** | Set it and collect | The lazy investor strategy. Floobits that grow each week your roster stays unchanged. | {baseFloobits} Floobits base, +{growthPerWeek} per week your roster stays unchanged |
| **Winner's Circle** | Ride the winners | Back the winners. Floobits whenever this player's real team wins their game this week. | {winFloobits} Floobits when this player's team wins this week |

### Holographic — 52 cards

*FP 29  ·  FPx 18  ·  Floobits 5*


#### Holographic · FP

| card | tagline | back of card | detail |
|---|---|---|---|
| **Altitude** **`NEW`** | Throwing it deep | Nothing underneath. FP scaling with average depth of target above 8 yards. | +{perYardFP} FP per yard of average target depth above {threshold} |
| **Blue Ribbon** | Pedigree | Prize winner. FP with a bonus when your favorite team's ELO reaches elite status (1600+). | +{baseFP} FP base, +{rewardValue} FP when your favorite team's ELO ≥ {eloThreshold} |
| **Breakaway** **`NEW`** | Gone in a blink | One crease is all it takes. FP for rushing yards, and a bonus every time this player breaks one for 20. | +{perYardFP} FP per rushing yard, +{bonusFP} for every 20+ yard run by this player |
| **Diversified** | Variety pack | Don't put all your eggs in one basket. FP per unique output type (FP, FPx, Floobits) across your equipped cards. | +{perTypeFP} FP per unique output type in your hand (FP, FPx, Floobits) |
| **Double Trouble** | Both WRs deliver | Two is better than one. FP when either WR scores a TD, bonus when both WRs score. | +{singleWrFP} FP when a WR scores, +{rewardValue} bonus FP when both WRs score |
| **End Zone** **`NEW`** | Where it counts | One is good. Two is somebody else's problem. FP on every receiving TD, with a bonus at two. | +{perTdFP} FP per receiving TD, +{bonusFP} bonus at {threshold}+ |
| **Fat Cat** | Rolling in it | Money talks. FP that scales with your Floobits balance. Excludes current week earnings. | +1 FP per {floobitsPerFP} Floobits in your balance (max {maxFP} FP) |
| **Gone Streaking** | CENSORED | Don't look away. FP based on your favorite team's longest streak (wins or losses). | +{baseFP} FP base, +{perStreakFP} per game in longest streak (winning or losing) by your favorite team this season. Streak does not need to be active. |
| **Group Project** | Everyone showed up | Everyone chipped in. FP if 4 or more of your other cards triggered a non-zero bonus this week. | +{rewardValue} FP when 4 or more of your other cards produced a non-zero bonus this week |
| **Haymaker** **`NEW`** | Swinging big | Twenty yards at a time. FP for passing yards, and a bonus on every throw that goes 20. | +{perYardFP} FP per passing yard, +{bonusFP} for every 20+ yard completion by this player |
| **Hedge** | Downside protection | Insurance policy. Tops this player up to an FP floor on a quiet week. | Tops this player up to a {floorSoloFP} FP floor if they have a quiet week. |
| **Highpoint** **`NEW`** | Above the crowd | Two defenders on the ball and it still comes down. FP per catch, and a bonus for the ones taken in traffic. | +{perReceptionFP} FP per reception, +{bonusFP} per contested catch by this player |
| **Hype Man** | Your {posLabel}'s biggest fan | The crowd goes wild. FP that stacks with each TD this player scores. | +{perTdFP} FP per TD by this player |
| **Jailbreak** | Breaking out | Can't catch them. Base FP every week, plus bonus FP when this player racks up enough yards after catch. | +{baseFP} FP base, +{rewardValue} bonus if this player racks up {threshold}+ yards after catch in a game |
| **Lead Blocker** | Paving the way | Clearing the path. FP per TD by your TE. RB TDs count as TE TDs if they are on the same team. | +{perTdFP} FP per TE TD in a game. Rushing touchdowns by the TE team's RB count as TE TDs |
| **Loyalty** | Stick with your guys | Keep the band together. FP per player still equipped from your first lineup this season. | +{perPlayerFP} FP per player still equipped from your first lineup this season. |
| **Loyalty Bonus** | Faithful fan rewards | Bandwagoning encouraged. Bonus FP based on your favorite team's win streak. | +{perStreakFP} FP per win in your favorite team's win streak |
| **Medium** | Crystal clear | Bonus FP when your weekly Prognostication accuracy is high. | +{lowFP} FP at 50%+ Prognostication accuracy, +{midFP} FP at 65%+, +{highFP} FP at 85%+. Counts auto-picks |
| **Mismatch** | Too big, too fast | They can't cover this guy. FP per TD by this player, plus a bonus when they score multiple TDs. | +{perTdFP} FP per TD by this player, +{bonusFP} bonus at {tdThreshold}+ TDs |
| **Nose Picker** | Pick it yourself | Streak grows each week you submit picks yourself instead of letting auto-pick fill them in. | +{baseReward} FP base. Grows every week you submit manual picks. Growth starts at +{firstWeekGrowth} FP and tapers off as the streak continues. |
| **Pocket Aces** | AA | Pocket Rockets. Base FP every week, plus bonus FP when this player hits a combined stat threshold. | +{baseFP} FP base, +{rewardValue} bonus if this player combines for {threshold}+ {statDisplay} |
| **Range** | Boot it through | Distance is the reward. FP scaling with the total FG yardage this player kicked this week. | +{perYardFP} FP per yard of FG kicked by this player this week. |
| **Rookie Hype** | Trust the kids | Believe in the new class. Bonus FP per rookie on your roster. | +{perRookieFP} FP per rookie on your roster |
| **Salvo** **`NEW`** | All at once | One is a shot. Three is a salvo. FP on every passing TD, with a bonus at three. | +{perTdFP} FP per passing TD, +{bonusFP} bonus at {threshold}+ |
| **Spotlight Moment** | Lights please | Lights, camera, action. FP whenever this player scores a TD. For WR, either counts. | +{rewardValue} FP when this player scores a TD. WR counts either WR scoring a TD. |
| **Trebuchet** | Siege engine | Send it deep. Base FP every week, plus bonus FP when this player catches a pass of 25+ yards. | +{baseFP} FP base, +{rewardValue} bonus if this player catches a {threshold}+ yard pass |
| **Updraft** **`NEW`** | Catching a lift | Some days the ball just carries. FP on every passing yard, with more at 200, 300 and 400. | +{perYardFP} FP per passing yard, +{gate1}/{gate2}/{gate3} bonus at 200, 300 and 400 |
| **Walk Off** | Show up when it counts | Built for the late game. FP per Q4 or OT TD or field goal scored by a roster player. Bonus floobits if your favorite team wins on a walk-off. | +{perScoreFP} FP per Q4/OT TD or FG by this player, +{floobitsOnTrigger}F when your favorite team wins with a walk-off |
| **Wanderer** | Spread thin | A bit of everywhere. Output scales with how many different teams your roster players come from. Max payout when no two share a team. | +{perTeamFP} FP per unique team represented across your roster |

#### Holographic · FPx

| card | tagline | back of card | detail |
|---|---|---|---|
| **Backfield Buddies** | Same backfield | Same backfield, double the payoff. FPx when this player and your rostered RB play on the same team. | +{rewardValue} FPx when this player and your rostered RB share a team |
| **Beast of Burden** **`NEW`** | Carrying the load | FPx on every carry, and more once the workload passes 25. | +{perCarryMult} FPx per carry, +{bonusMult} more once past {threshold} |
| **Closers** | See this watch? | Always be closing. Bonus FP from this player's Q4 and OT production. | This player's Q4/OT fantasy points are multiplied by {q4MultFactor}x |
| **Coffin Corner** **`NEW`** | Nowhere to go | FPx on every punt downed inside the 20, and more for the ones inside the 10. | +{perPuntMult} FPx per punt inside the 20, +{bonusMult} more for inside the 10 |
| **Custody** **`NEW`** | Safe hands | FPx on every catch, and more once the count passes eight. | +{perReceptionMult} FPx per reception, +{bonusMult} more once past {threshold} |
| **Eminence** | Stack the leaderboard | Top of the heap. FPx per roster player ranked top-10 at their position by season FP/game. | +{perPlayerMult} FPx per roster player ranked top-10 at their position. Max +{maxDelta} FPx. Active from week 3. |
| **Grinder** **`NEW`** | Earning every inch | FPx on every yard after contact, and more when those yards clear half the total. | +{perYardMult} FPx per yard after contact, +{ratioMult} more when they exceed half the total |
| **Luminary** | Your {posLabel} runs the show | Your {posLabel} runs the offense. FPx that increases the more FP this player earns. | FPx that grows the more FP this player earns compared to teammates |
| **Marksman** **`NEW`** | Nothing wasted | FPx on every well-placed ball, and more for a week without a single bad throw. | +{perGoodThrowMult} FPx per well-placed throw, +{cleanSheetMult} more on 0 bad throws |
| **No Passengers** | No free rides | Depth pays. FPx that scales with your lowest-scoring roster player, so a lineup with no weak link earns more. | +{perFloorFP} FPx per FP scored by your lowest roster player (max +{maxDelta}) |
| **Parlay** | Let it ride | FPx that grows with your weekly Prognostication points. | FPx that grows with your weekly Prognostication points. Counts auto-picks |
| **Providence** | A little something extra | Fortune favors the prepared. FPx bonus plus chance boost to all chance cards in your hand. | +{baseDelta} FPx, plus +{chanceBonusPct}% trigger odds to every chance card in your hand |
| **Rhythm** **`NEW`** | Finding a groove | Once the rhythm arrives, everything comes easier. FPx on every completion, and more once past 20. | +{perCompletionMult} FPx per completion, +{bonusMult} more once past {threshold} |
| **Stack** | QB-WR stack | Stack attack. FPx when this player and any rostered WR play on the same team. | +{rewardDelta} FPx when this player and a rostered WR share a team |
| **Synergy** | Stack the depth chart | Two heads, one team. FPx per pair of roster players on the same actual team. | +{perPairMult} FPx per pair of roster players on the same actual team. Max +{maxDelta} FPx. |
| **Territory** **`NEW`** | Claiming ground | FPx on every receiving yard, with more at 75, 125 and 175. | +{perYardMult} FPx per receiving yard, +{gate1}/{gate2}/{gate3} more at 75, 125 and 175 |
| **Trailblazer** | Unstoppable force | Get rolling. Base FPx, enhanced FPx when this player hits 75+ rushing yards. | +{baseDelta} FPx base, +{enhancedDelta} FPx when this player hits {yardThreshold}+ rush yards in a game<br>*RENAMED to **Trailblazer** — joins the rush-yards journey motif.* |
| **Vanguard** | Old guard | The old guard endures. FPx per roster player with 5 or more seasons played. | +{perVetMult} FPx per roster player with 5+ seasons played. Max +{maxDelta} FPx. |

#### Holographic · Floobits

| card | tagline | back of card | detail |
|---|---|---|---|
| **Cha-Ching** | Cash out | The endzone is your cash register. Floobits for every TD this player scores. | {perTdFloobits} Floobits per TD by this player |
| **Clique** | BFFs | Always together. Floobits when 3 or more of your roster players share the same team. | +{rewardFloobits} Floobits when 3+ roster players share a team |
| **Feeding Frenzy** | Eat up | Dinner is served. Floobits per roster TD, plus a jackpot bonus when your roster hits the TD threshold. | {perTdFloobits}F per roster TD, +{bonusFloobits}F jackpot at {tdThreshold}+ roster TDs |
| **Good Neighbor** | You're covered | Worry free. Guaranteed Floobits plus a bonus for each FG your kicker misses. | +{baseFloobits}F base + {perMissFloobits}F per missed FG this week |
| **Highlight Reel** | Did you see that? | Highlight reel material. Floobits for every big play your favorite team pulls off. | {rewardValue} Floobits per your favorite team's big plays |

### Prismatic — 41 cards

*FP 29  ·  FPx 9  ·  Floobits 2  ·  Other 1*


#### Prismatic · FP

| card | tagline | back of card | detail |
|---|---|---|---|
| **Anthem** | All together now | Power in numbers. Flat FP that fires when your hand is heavy on flat-FP cards. 3 or more pays a bonus, 4 raises it, 5 maxes it out. | +{tier3FP} FP with 3 flat-FP cards equipped, +{tier4FP} with 4, +{tier5FP} with 5 |
| **Automatic** | Perfect kicks only | Perfection pays. FP growing each consecutive week this player goes perfect on FGs. Stacking streak cards accelerates growth. | +{baseReward} FP base, +{growthPerTick} per consecutive week your K makes all FG attempts. A week with no FG attempts will not break the streak. |
| **Avalanche** | Bury them | Momentum builds with every score. Each roster TD pays more FP than the last. | Roster TDs pay escalating FP: 1st={td1}, 2nd={td2}, 3rd={td3}, 4th={td4} then diminishing |
| **Babysitter** | Carrying the team | Someone has to do the heavy lifting. Guaranteed FP floor plus a chance at enhanced FP. The trigger bar fills from this player's own FP and from each roster player who underperforms. | +{baseFP} FP guaranteed, chance at {enhancedFP} FP. Trigger odds fill from this player's FP plus each roster player under {fpThreshold} FP. |
| **Bandwagon Express** | Choo choo! | Next stop: more points. FP growing each week your favorite team wins. Stacking streak cards accelerates growth. | +{baseReward} FP base, +{growthPerTick} per consecutive favorite-team win. |
| **Barrage** **`NEW`** | Keep firing | FP on every passing TD, and each one raises the odds the next pays out. | +{perTdFP} FP per passing TD, plus escalating odds at {bonusFP} FP on each one |
| **Bonsai** | Snip snip | Grown, not gifted. Roster performance earns permanent FP growth each week. Higher levels demand bigger weeks. Resets if unequipped. | +{baseFP} FP guaranteed. This player's {triggerLabel} scale the chance to grow the base by +{growthFP} FP at week's end. Every grow slows the next. |
| **Charmed** | The dice love you | Pays out every time luck breaks your way. FP per chance card that triggered this week. | +{perTriggerFP} FP per chance card that triggered this week. |
| **Clockwork** **`NEW`** | Never misses a beat | Same time every week. FP on every completion, plus a streak for every week past 25. | +{perCompletionFP} FP per completion, plus a streak growing {growthPerTick} per week this player clears {threshold} |
| **Complacency** | Stop tinkering | Put the phone down. FP that grows each week you don't touch your roster. Stacking streak cards accelerates growth. | +{baseReward} FP, +{growthPerTick} per week roster is unchanged. |
| **Crescendo** | Keep missing, it only gets easier | Miss enough and eventually you can't miss. Each TD by this player rolls for a bonus. Miss and the odds go up. For K, triggers on FGs. | +{baseFP} FP guaranteed. {baseChance}% chance at {bonusFP} FP on this player's first {scoreNoun}, chance increases by +{chanceStep}% if bonus doesn't trigger. |
| **Custodian** **`NEW`** | Cleaning up | The throw was bad. The catch was made anyway. FP per catch, and a bonus for rescuing a bad ball. | +{perReceptionFP} FP per reception, +{bonusFP} per bailout by this player |
| **Dead Eye** **`NEW`** | Never off target | FP on every well-placed ball, plus a streak for every week with nothing off target. | +{perGoodThrowFP} FP per well-placed throw, plus a streak growing {growthPerTick} per clean sheet |
| **Dominion** **`NEW`** | The whole field | FP on every receiving yard, plus a streak for every hundred-yard week. | +{perYardFP} FP per receiving yard, plus a streak growing {growthPerTick} per week past {threshold} |
| **Getaway** **`NEW`** | Gone | FP on every yard after the catch, plus a streak for every forty-yard week. | +{perYardFP} FP per YAC yard, plus a streak growing {growthPerTick} per week past {threshold} |
| **Houdini** **`NEW`** | Impossible to corner | FP on every rushing yard, and a shot at more every time a tackle gets broken. | +{perYardFP} FP per rushing yard, plus a chance at {bonusFP} FP filling from broken tackles |
| **House Call** **`NEW`** | All the way | FP on every return yard, and sometimes nobody gets a hand on it at all. | +{perYardFP} FP per punt return yard, plus a chance at {bonusFP} FP on a return TD |
| **Iron Man** **`NEW`** | Never comes off the field | FP on every carry, plus a streak for every week the load passes twenty. | +{perCarryFP} FP per carry, plus a streak growing {growthPerTick} per week past {threshold} |
| **Landslide** **`NEW`** | Gathering weight | FP on every yard after contact, plus a streak for every hundred-yard week. | +{perYardFP} FP per yard after contact, plus a streak growing {growthPerTick} per week past {threshold} |
| **Last Resort** | The ultimate insurance | When nothing else works. Guaranteed FP floor plus a chance at enhanced FP. The trigger bar fills from this player's own FP and from each of your other cards that fails to produce a bonus. | +{baseFP} FP guaranteed, chance at {enhancedFP} FP. Trigger odds fill from this player's FP plus each of your other cards that produced no bonus. |
| **Leg Day** | Never skip leg day | Never skip it. FP growing each week this player nails a 35+ yard FG. Stacking streak cards accelerates growth. | +{baseReward} FP base, +{growthPerTick} per consecutive game with a 35+ yd FG by your K. A week with no FG attempts will not break the streak. |
| **Metronome** | Never misses a beat | FP that grows each week this player clears their power bar. A cold week holds the streak rather than resetting it. | +{baseReward} FP, +{growthPerTick} per consecutive week this player clears their power bar. Streak does not reset on cold weeks. |
| **Odometer** | Every milestone pays | Hit the milestones. Escalating FP at each yardage gate this player hits. Resets weekly. | Escalating FP as this player piles up yards this week (40 / 80 / 120 / 160+). |
| **Odyssey** **`NEW`** | The long road | FP on every rushing yard, plus a streak for every hundred-yard week. | +{perYardFP} FP per rushing yard, plus a streak growing {growthPerTick} per week past {threshold} |
| **Promised Land** **`NEW`** | Getting there | FP on every receiving TD, and each one raises the odds the next pays out. | +{perTdFP} FP per receiving TD, plus escalating odds at {bonusFP} FP on each one |
| **Snowball Fight** | Getting bigger | It just keeps getting bigger. FP growing each week your roster scores a TD. Stacking streak cards accelerates growth. | +{baseReward} FP base, +{growthPerTick} per consecutive week at least one player on your roster scores a TD. |
| **Tenure** **`NEW`** | Long service | FP on every catch, plus a streak for every week the count passes eight. | +{perReceptionFP} FP per reception, plus a streak growing {growthPerTick} per week past {threshold} |
| **Traverse** | Take the long way | High stakes yardage gamble. FP floor plus a jackpot chance based on yardage by this player. | +{baseFP} FP floor + {bonusFP} FP jackpot. Jackpot chance starts at {baseChance}%, +{chancePerStep}% per {yardStep} {yardType} yards |
| **Undertaker** **`NEW`** | Bury them | FP on every punt downed inside the 20, plus a streak for every multi-pin week. | +{perPuntFP} FP per punt inside the 20, plus a streak growing {growthPerTick} per week past {threshold} |

#### Prismatic · FPx

| card | tagline | back of card | detail |
|---|---|---|---|
| **All In** | Eggs + basket | Adds FPx for each fantasy point this player scores past a high FP line, up to a cap. No bonus below the line. | +{perFPxShown} FPx for every fantasy point this player scores past {studLine} FP. |
| **Chain Reaction** | Cards feeding cards | Cards feeding cards. FPx that scales with how many of your other 4 cards produced a non-zero bonus. | +{perCardXMult} FPx for every card in your hand that produced a non-zero bonus this week |
| **Cornerstone** | Build around the best | Roster the position leaders. FPx per roster player ranked #1 at their position by season FP. | +{perPlayerMult} FPx per roster player ranked #1 at their position. Max +{maxDelta} FPx. Active from week 3. |
| **Cornucopia** | Every touchdown compounds | Every touchdown compounds, but each one matters a little less. FPx that stacks per roster TD with diminishing returns. | FPx that grows as your roster scores TDs. |
| **Franchise** | The centerpiece | Build around your guy. FPx when this player is your single highest scorer this week. | +{topScorerDelta} FPx when this player is your top scorer this week |
| **Juggernaut** | I'M THE JUGGERNAUT | Momentum is a beautiful thing. FPx grows with every win in your favorite team's streak, with diminishing returns past long runs. | +{baseXDelta} FPx base, grows with your favorite team's win streak. |
| **Momentum** | Rolling | Can't stop won't stop. FPx grows each week your roster breaks 100 FP. Stacking streak cards accelerates growth. | +{baseRewardDelta} FPx base, +{growthPerTick} per consecutive week your roster scores 100+ FP. |
| **On Fire** | Keep the flame alive | Don't let the flame die. FPx that grows each week this player makes a FG. Stacking streak cards accelerates growth. | +{baseRewardDelta} FPx base, +{growthPerTick} per consecutive week with a FG made by your K. |
| **Stratosphere** **`NEW`** | Thin air up here | Territory most passers never see. FPx on passing yards, plus a streak for every 300-yard week. | +{perHundredMult} FPx per 100 passing yards, plus a streak growing {growthPerTick} per week past {threshold} |

#### Prismatic · Floobits

| card | tagline | back of card | detail |
|---|---|---|---|
| **Fairweather Fan** | Only here for the wins | Fair-weather fandom has its perks. Floobits growing each week your favorite team wins. Stacking streak cards accelerates growth. | {baseReward} Floobits base, +{growthPerTick} per consecutive favorite-team win. |
| **Touchdown Jackpot** | Weekly TD lottery | Fresh lottery every week. Floobits stacking per roster TD, resets weekly. | {baseReward} Floobits on 1st roster TD, +{growthPerTick} for every subsequent roster TD. Resets weekly. |

#### Prismatic · Other

| card | tagline | back of card | detail |
|---|---|---|---|
| **Copycat** | Imitation is flattery | Copies the best. FP equal to the highest flat FP bonus from your other cards. | +FP equal to highest flat FP bonus from your other cards |

### Diamond — 14 cards

*FP 1  ·  FPx 6  ·  Floobits 1  ·  Other 6*


#### Diamond · FP

| card | tagline | back of card | detail |
|---|---|---|---|
| **Alchemy** | Lead into gold | Transmutation complete. Each FG by this player counts as a TD for fantasy scoring and other card effects. | +{perFgBonusFP} bonus FP per FG by this player. FGs also count as roster TDs for other cards in your hand. |

#### Diamond · FPx

| card | tagline | back of card | detail |
|---|---|---|---|
| **Bizarro** | Down is up | Bad is good. The lower your lowest-scoring roster player's FP this week, the bigger the FPx on your total. | FPx that grows the WORSE this player's game is. A blank stat line pays the most. |
| **Full House** | Whole squad shows up | Cover all your bases. Big FPx, but only in a week where every performing card in your lineup clears its FP power bar. One cold player and it pays nothing. | +{rewardDelta} FPx when every card in your lineup clears its power bar |
| **Heat Check** | Staying hot | Are you feeling the heat? FPx that scales with how many of your streak cards have active streaks. | +{perCardMult} FPx per active streak card in your hand |
| **High Roller** | Degenerate strategy | Built for the gamble. FPx that scales with how many of your chance cards hit enhanced this week. | +{perCardMult} FPx per chance card that triggered enhanced bonuses this week |
| **Lemons** | Burn the house down | With the lemons. Multiplies your lowest-earning card's FP this week. | Multiplies your lowest-earning card's FP by {rewardValue} this week |
| **Stacked Deck** | Let's get exponential | Multiply the multipliers. FPx for each FPx card in your hand. | Self-compounds: each other FPx card in your hand stacks +{perCardMult} on this card's own delta |

#### Diamond · Floobits

| card | tagline | back of card | detail |
|---|---|---|---|
| **Catalyst** | Points in, luck out | Compound interest. Roster FP boosts odds on all your chance cards. Also pays Floobits. | +1% chance boost per {fpPer1PctSolo} of this player's FP above {baselineSolo}. Max +{maxBoostDisplay}%. Also pays {baseFloobits} Floobits |

#### Diamond · Other

| card | tagline | back of card | detail |
|---|---|---|---|
| **Advantage** | Double or nothing (minus the nothing) | Loaded dice. Every chance card in your hand rolls twice, keeping the better result. | All chance cards roll {rollCount}x for their bonus, keeping the best result |
| **Captain** | Set the tone | Leads by example. Every other card is amplified by how far its player blows past their power bar this week (up to 2x). Produces nothing on its own. | +{perOvershootShown}% output to each other card per FP its player scores over their power bar (max +100%) |
| **Conductor** | Wave the baton | Orchestrates the rest of your hand. Every other flat-FP card you have equipped outputs more. Produces nothing on its own. | Boosts each other flat-FP card's output by +{boostPct}% |
| **Doubler** | Twice the score | Doubles down on the scoreboard. Roster TDs count 2x for every other card. Produces nothing on its own. | Roster TDs count {tdMult}x for every other card's effect this week. |
| **Sharpshooter** | Boots that pay double | Kicks land harder. Roster FGs count 2x for every other card. Produces nothing on its own. | Roster FGs count {fgMult}x for every other card's effect this week. |
| **Surveyor** | Every yard counts more | Measures every yard twice. Roster yards count 1.5x for every other card. Produces nothing on its own. | Roster yards count {yardMult}x for every other card's effect this week. |

**Totals: 145 cards (39 new).**

---

## How a family works

A **family** is one stat, three cards, one motif. The stat never changes as you climb, and
**each tier contains the one below it**. A holographic card still pays the flat rate its
metallic sibling pays; it just adds a conditional bonus on top. A prismatic card still pays
a flat rate too, with a streak or a chance built on the same stat.

    metallic      output per stat
    holographic   output per stat  +  conditional bonus
    prismatic     output per stat  +  streak or chance on that stat

That is what makes a chain feel like an upgrade path rather than three unrelated cards
that happen to share a number.

### Same typical week, bigger tail (owner call 2026-08-06)

**Hold the typical week constant and add to the upper tail.** On an ordinary week every
tier scores about the same; on a big week holographic and prismatic score far more.

The distinction that makes this work is **typical week (median) versus mean**. They are
not the same number, and only the first is held flat. A fatter tail necessarily lifts the
mean, so the mean rises as a CONSEQUENCE, never as the design target.

Modelled on receptions (measured mean 9.35, p50 9, p90 14), 60,000 weeks per tier:

| tier | typical (p50) | mean | p75 | p90 | p99 | max |
|---|---|---|---|---|---|---|
| metallic | 25.2 | 26.1 | 33.6 | 39.2 | 58.8 | 67.2 |
| holographic | 25.2 | 30.4 | 41.4 | 52.2 | 84.6 | 106.2 |
| prismatic | 28.0 | 32.7 | 39.2 | 58.8 | 102.0 | 144.0 |

| tier | typical | mean | p90 | p99 |
|---|---|---|---|---|
| holographic | **1.00x** | 1.16x | 1.33x | 1.44x |
| prismatic | **1.11x** | 1.25x | 1.50x | **1.73x** |

The typical week is flat and the tail roughly doubles. That is the shape.

**How each tier gets there:**

    metallic      rate x stat
    holographic   rate x stat  +  bonus on the PART OF THE STAT ABOVE A TYPICAL WEEK
    prismatic     rate x stat  +  a chance or streak whose payout SCALES WITH THE WEEK

The holographic bonus keys off the excess (`max(0, stat - typical)`), so it pays nothing
on an ordinary week by construction. That is what keeps the median flat without any
tuning.

> ⚠️ **The prismatic payout must scale with the stat, not be a flat number.** A first pass
> gave prismatic a fixed bonus on a chance roll, and its p99 came out BELOW holographic's
> (78.8 vs 84.6) — a flat bonus cannot out-ceiling a bonus that grows with the week, no
> matter how often it fires. Making the prismatic payout proportional (`~3.2 x stat` on a
> ~22% trigger) restores the ordering: metallic < holo < prismatic at every upper
> percentile.

**Diamond is excluded from this ladder.** It is mostly modifier and amplifier cards
(1 FP / 6 FPx / 6 cross-effect of 14), so it does not have a per-stat curve to shape.

### What this does NOT fix

At an equal typical week the extra mean is small (1.16x / 1.25x), and the two payoff
surfaces that matter barely notice a fatter tail:

- the fantasy leaderboard sorts on `seasonTotal`, a cumulative SUM, which responds only
  to the mean;
- Floobits convert at `0.43 x FP^0.78`, which is concave, so a spike is worth slightly
  LESS than the same total spread evenly.

Measured over 400 simulated seasons at strictly equal means, a rising ceiling moved season
FP not at all and Floobit income slightly DOWN. The modest mean lift above is what makes
rarity worth playing at all; the ceiling itself pays off only in **Banner Week** (a
one-time achievement ladder). If rarity should be about shape rather than power, the game
needs a recurring surface that rewards a peak week. Recorded as an open question.

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

As drafted, the catalogue below takes metallic from **54% FP / 14% FPx / 32% Floobits**
to **53% / 24% / 24%** — the FPx pool more than doubles, from 4 cards to 9, and Floobits
drops from a third of the tier to a quarter.

That is still short of a third FPx. Closing it needs roughly six more FPx prints under
rule 3, on the high-volume stats where a small delta is stable: completions, receiving
yards, yards after contact, carries, rush yards and receptions. **Those are not drafted
below** — each needs its own name, and the naming pass is the owner's. Flagged rather than
invented.

### Rare stats live OUTSIDE the families — as base + bonus (owner call 2026-08-06)

Five stats are too rare to carry a family. A card paying only on a sub-2-per-game event
needs an enormous per-unit value to reach the ~26 FP anchor, so a typical week pays nothing
and a p90 week pays double. There is also not enough room above a one-a-game stat to build
three distinct rungs on it.

The fix is **base + bonus**: a modest rate on the PARENT stat as a floor, with the rare
event as the kicker. The card is still about the highlight play, it just stops being dead
in the weeks the highlight does not come. Sized to the same ~26 FP anchor:

| card | base | rate | bonus on | mean | bonus | floor | p90 |
|---|---|---|---|---|---|---|---|
| *Breakaway* | rush yards | 0.14/yd | 20+ runs (0.88/g) | 12.0 | 26.0 | 15.5 | 53.3 |
| *Haymaker* | pass yards | 0.055/yd | 20+ throws (1.75/g) | 7.5 | 25.8 | 12.6 | 48.3 |
| *Highpoint* | receptions | 1.7/rec | contested catches (1.02/g) | 10.0 | 26.1 | 15.9 | 53.8 |
| *Custodian* | receptions | 1.7/rec | bailouts (0.31/g) | 33.0 | 26.1 | 15.9 | 56.8 |

**Floor** is what a week with none of the rare event still pays. Roughly 60% of the mean
comes from the base and 40% from the bonus, and the p90 is about double the mean — the
variance that earns the holographic slot, now sitting on a floor instead of a hole.

*Houdini* is excluded: it is a chance card filling its odds from broken tackles, so its
shape is already floor-plus-jackpot by construction.

**These borrow the parent stat as a floor, which is deliberate.** Breakaway pays rushing
yards, the same stat as the Expedition family. It is not competing with that family's
premise — its identity is still the explosive run, and the yards only stop it reading as a
dead card. A one-off standing on a family's stat is fine; a one-off standing on nothing is
what got these cut in the first draft.

| card | tier | why there |
|---|---|---|
| *Haymaker* | holographic | base + bonus, ~1-2 events a game |
| *Highpoint* | holographic | base + bonus, about one a game |
| *Breakaway* | holographic | base + bonus, about one a game |
| *Houdini* | prismatic | chance card, odds fill from broken tackles |
| *Custodian* | prismatic | rarest event; belongs where variance is the point |

**Bailout** = the receiver caught a ball thrown below the bad-throw bar (quality < 45),
credited only on the completion. The mirror of the QB's `badThrows`: bad throws run
1.56/game against 0.31 bailouts, so about one bad ball in five is caught anyway. It is the
stat that separates a receiver's contribution from the quality of throw they were given.

> **Touchdowns are lumpier still and stay in families anyway.** Rush TDs run 0.69/game and
> receiving TDs 0.40 — rarer than contested catches. They keep their ladders because they
> are the most legible event in football and the pool already supports them (Piñata,
> Squire, Spotlight Moment, Crescendo, Avalanche, Lead Blocker, Goal Line Vulture). Rule 2
> handles the lumpiness: **the TD families take FPx at metallic**, so a scoreless week
> costs nothing instead of reading as a dead card.

---

## QB

| family / motif | metallic — per stat | holographic — + conditional bonus | prismatic — + streak or chance |
|---|---|---|---|
| **completions** — timekeeping | *Cadence* **FP** per completion | *Rhythm* **FPx** per completion, more past 20 | *Clockwork* **FP** per completion + streak at 25+ |
| **pass yards** — flight | *Slipstream* **FPx** per 100 yards | *Updraft* **FP** per yard, + bonus at 200/300/400 | *Stratosphere* **FPx** per 100 + streak at 300 |
| **pass TDs** — ordnance | *Bombardier* **FPx** per pass TD | *Salvo* **FP** per TD, + bonus at 3+ | *Barrage* **FP** per TD + escalating odds |
| **throw quality** — marksmanship | **Gunslinger** **FP** per good throw *(re-pointed)* | *Marksman* **FPx** per good throw, + bonus on a clean sheet | *Dead Eye* **FP** per good throw + clean-sheet streak |

One-offs: *Attention* **FPx** (targets), *Altitude* (holo, aDOT above 8), *Haymaker*
(holo, pass yards + bonus per 20+ throw), **Air Raid** (shipped, Floobits on pass TDs).
Blocked: throw quality needs the new `goodThrows` counter.

## RB

| family / motif | metallic — per stat | holographic — + conditional bonus | prismatic — + streak or chance |
|---|---|---|---|
| **carries** — labour | **Workhorse** **FP** per carry | *Beast of Burden* **FPx** per carry, more past 25 | *Iron Man* **FP** per carry + streak at 20 |
| **rush yards** — journey | **Expedition** **FP** per yard | **Trailblazer** **FPx** per yard, + bonus on the big game *(was Stampede)* | *Odyssey* **FP** per yard + streak at 100 |
| **rush TDs** — force | *Battering Ram* **FPx** per rush TD | **Lead Blocker** **FP** per rush TD, + bonus | — |
| **yards after contact** — mass | *Freight* **FP** per contact yard | *Grinder* **FPx** per contact yard, + bonus past half | *Landslide* **FP** per contact yard + streak at 100 |

One-offs: *Breakaway* (holo, rush yards + bonus per 20+ run), *Houdini* (prismatic, chance
filling from broken tackles), **Goal Line Vulture** (shipped, Floobits on rush TDs).

Yards after contact only became a real stat this session (80% of rush yards, 87.5/game).

## WR / TE

| family / motif | metallic — per stat | holographic — + conditional bonus | prismatic — + streak or chance |
|---|---|---|---|
| **receptions** — custody | **Possession** (WR) · **Safety Blanket** (TE) **FP** per catch | *Custody* **FPx** per catch, more past 8 | *Tenure* **FP** per catch + streak at 8 |
| **receiving yards** — territory | *Frontier* **FP** per yard | *Territory* **FPx** per yard, + bonus at 75/125/175 | *Dominion* **FP** per yard + streak at 100 |
| **receiving TDs** — the end zone | *Paydirt* **FPx** per rec TD | *End Zone* **FP** per TD, + bonus at 2+ | *Promised Land* **FP** per TD + escalating odds |
| **YAC** — escape | **Slippery** **FP** per YAC yard | **Jailbreak** **FPx** per YAC yard, + bonus | *Getaway* **FP** per YAC yard + streak at 40 |

One-offs: **Trebuchet** (shipped, longest catch), *Highpoint* (holo, receptions + bonus per
contested catch), *Custodian* (prismatic, receptions + bonus per bailout), **Industrious**
(shipped, Floobits on TE receptions).

**Receiving yards is the biggest hole in the pool** — 83.5/game, the most-produced skill
stat in the game, and no card below prismatic today.

## K

| family / motif | metallic — per stat | holographic — + conditional bonus | prismatic — + streak or chance |
|---|---|---|---|
| **punting** — burial | *Pinpoint* **FP** per punt inside the 20 | *Coffin Corner* **FPx** per pin, + bonus inside the 10 | *Undertaker* **FP** per pin + multi-pin streak |
| **returns** — the runback | *Runback* **FP** per return yard | — | *House Call* **FP** per return yard + odds on a return TD |

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
6. **Shape the tail, not the dial.** `EDITION_POWER_SCALE` stays roughly where it is —
   the lift comes from HOW the holo and prismatic bonuses are written (excess-of-typical
   and scales-with-the-week), not from a global multiplier. Measure the resulting
   percentile curve per tier rather than the mean alone; `simcheck_effect_spread.py`
   already reports p10/p90 per card.

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
3. **Good Neighbor is multi-position but reads the roster's kicker.** Every other
   "your roster's K" card is K-LOCKED, so under fusion the roster slot and the card player
   are the same person and the wording was just stale framing (now fixed). Good Neighbor
   mints on ANY position while paying off the roster kicker's missed FGs, so a QB card's
   depicted player is decorative. Lock it to K, or re-base it. Text left accurate until
   the behaviour is settled.
4. **The remaining rating-keyed cards** (see *Still rating-keyed*). The chance-fill
   group is half stat-driven already and needs only its `conditionFill` input swapped; the
   star-count group needs a decision on whether a static rating band is acceptable at all
   given the direction this plan sets.
