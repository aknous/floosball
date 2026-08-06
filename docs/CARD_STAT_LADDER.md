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

### Holographic — 55 cards

*FP 32  ·  FPx 18  ·  Floobits 5*


#### Holographic · FP

| card | tagline | back of card | detail |
|---|---|---|---|
| **Altitude** **`NEW`** | Throwing it deep | Nothing underneath. FP scaling with average depth of target above 8 yards. | +{perYardFP} FP per yard of average target depth above {threshold} |
| **Blue Ribbon** | Pedigree | Prize winner. FP with a bonus when your favorite team's ELO reaches elite status (1600+). | +{baseFP} FP base, +{rewardValue} FP when your favorite team's ELO ≥ {eloThreshold} |
| **Breakaway** **`NEW`** | Gone in a blink | One crease is all it takes. FP for every run of 20 or more. | +{perRunFP} FP for every 20+ yard run by this player |
| **Castaway** | Diamond in the basement | Find the gem on a bad team and they pay you. Bonus FP when your roster includes any player whose team is below .500. | +{rewardFP} FP when at least one roster player is on a sub-.500 team |
| **Comeback Kid** | Bet on the bounce-back | Find the rising teams. FP per roster player whose team missed playoffs last season. Bonus floobits if your favorite team pulls off a comeback win. | +{perPlayerFP} FP per roster player whose team missed playoffs last season, +{floobitsOnTrigger}F if your favorite team wins a comeback this week |
| **Diversified** | Variety pack | Don't put all your eggs in one basket. FP per unique output type (FP, FPx, Floobits) across your equipped cards. | +{perTypeFP} FP per unique output type in your hand (FP, FPx, Floobits) |
| **Domination** | Ride the contenders | Ride with the leaders. FP per roster player whose team is currently top-6 in their league. Bonus floobits if your favorite team wins by 21+. | +{perPlayerFP} FP per roster player whose team is top-6 in their league, +{floobitsOnTrigger}F if your favorite team wins by {marginThreshold}+ this week |
| **Double Trouble** | Both WRs deliver | Two is better than one. FP when either WR scores a TD, bonus when both WRs score. | +{singleWrFP} FP when a WR scores, +{rewardValue} bonus FP when both WRs score |
| **End Zone** **`NEW`** | Where it counts | One is good. Two is somebody else's problem. FP per receiving TD, doubled at two. | +{perTdFP} FP per receiving TD, doubled at {threshold}+ |
| **Fat Cat** | Rolling in it | Money talks. FP that scales with your Floobits balance. Excludes current week earnings. | +1 FP per {floobitsPerFP} Floobits in your balance (max {maxFP} FP) |
| **Gone Streaking** | CENSORED | Don't look away. FP based on your favorite team's longest streak (wins or losses). | +{baseFP} FP base, +{perStreakFP} per game in longest streak (winning or losing) by your favorite team this season. Streak does not need to be active. |
| **Group Project** | Everyone showed up | Everyone chipped in. FP if 4 or more of your other cards triggered a non-zero bonus this week. | +{rewardValue} FP when 4 or more of your other cards produced a non-zero bonus this week |
| **Haymaker** **`NEW`** | Swinging big | Twenty yards at a time. FP for every throw of 20 or more. | +{perThrowFP} FP for every 20+ yard completion by this player |
| **Hedge** | Downside protection | Insurance policy. Tops this player up to an FP floor on a quiet week. | Tops this player up to a {floorSoloFP} FP floor if they have a quiet week. |
| **Highpoint** **`NEW`** | Above the crowd | Two defenders on the ball and it still comes down. FP per contested catch. | +{perCatchFP} FP per contested catch by this player |
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
| **Salvo** **`NEW`** | All at once | One is a shot. Three is a salvo. FP per passing TD, doubled at three. | +{perTdFP} FP per passing TD, doubled at {threshold}+ |
| **Spotlight Moment** | Lights please | Lights, camera, action. FP whenever this player scores a TD. For WR, either counts. | +{rewardValue} FP when this player scores a TD. WR counts either WR scoring a TD. |
| **Trebuchet** | Siege engine | Send it deep. Base FP every week, plus bonus FP when this player catches a pass of 25+ yards. | +{baseFP} FP base, +{rewardValue} bonus if this player catches a {threshold}+ yard pass |
| **Updraft** **`NEW`** | Catching a lift | Some days the ball just carries. Escalating FP past 200, 300 and 400 yards. | +{gate1}/{gate2}/{gate3} FP at 200, 300 and 400 passing yards |
| **Walk Off** | Show up when it counts | Built for the late game. FP per Q4 or OT TD or field goal scored by a roster player. Bonus floobits if your favorite team wins on a walk-off. | +{perScoreFP} FP per Q4/OT TD or FG by this player, +{floobitsOnTrigger}F when your favorite team wins with a walk-off |
| **Wanderer** | Spread thin | A bit of everywhere. Output scales with how many different teams your roster players come from. Max payout when no two share a team. | +{perTeamFP} FP per unique team represented across your roster |

#### Holographic · FPx

| card | tagline | back of card | detail |
|---|---|---|---|
| **Backfield Buddies** | Same backfield | Same backfield, double the payoff. FPx when this player and your rostered RB play on the same team. | +{rewardValue} FPx when this player and your rostered RB share a team |
| **Beast of Burden** **`NEW`** | Carrying the load | Keep feeding the ball until the legs give out. FPx once this player clears 25 carries. | +{perCarryMult} FPx per carry past {threshold} |
| **Closers** | See this watch? | Always be closing. Bonus FP from this player's Q4 and OT production. | This player's Q4/OT fantasy points are multiplied by {q4MultFactor}x |
| **Coffin Corner** **`NEW`** | Nowhere to go | Inside the ten and pinned against the sideline. FPx per punt downed inside the 10. | +{perPuntMult} FPx per punt downed inside the 10 |
| **Custody** **`NEW`** | Safe hands | Everything thrown that way comes down. FPx per catch past eight. | +{perReceptionMult} FPx per reception past {threshold} |
| **Eminence** | Stack the leaderboard | Top of the heap. FPx per roster player ranked top-10 at their position by season FP/game. | +{perPlayerMult} FPx per roster player ranked top-10 at their position. Max +{maxDelta} FPx. Active from week 3. |
| **Grinder** **`NEW`** | Earning every inch | More yards after the hit than before it. FPx when contact yards clear half the total. | +{ratioMult} FPx when yards after contact exceed half of rushing yards |
| **Luminary** | Your {posLabel} runs the show | Your {posLabel} runs the offense. FPx that increases the more FP this player earns. | FPx that grows the more FP this player earns compared to teammates |
| **Marksman** **`NEW`** | Nothing wasted | Not one ball off target. FPx when this player finishes the week without a bad throw. | +{cleanSheetMult} FPx when this player records 0 bad throws |
| **No Passengers** | No free rides | Depth pays. FPx that scales with your lowest-scoring roster player, so a lineup with no weak link earns more. | +{perFloorFP} FPx per FP scored by your lowest roster player (max +{maxDelta}) |
| **Parlay** | Let it ride | FPx that grows with your weekly Prognostication points. | FPx that grows with your weekly Prognostication points. Counts auto-picks |
| **Providence** | A little something extra | Fortune favors the prepared. FPx bonus plus chance boost to all chance cards in your hand. | +{baseDelta} FPx, plus +{chanceBonusPct}% trigger odds to every chance card in your hand |
| **Rhythm** **`NEW`** | Finding a groove | Once the rhythm arrives, everything comes easier. FPx growing with every completion past 20. | +{perCompletionMult} FPx per completion past {threshold} |
| **Stack** | QB-WR stack | Stack attack. FPx when this player and any rostered WR play on the same team. | +{rewardDelta} FPx when this player and a rostered WR share a team |
| **Synergy** | Stack the depth chart | Two heads, one team. FPx per pair of roster players on the same actual team. | +{perPairMult} FPx per pair of roster players on the same actual team. Max +{maxDelta} FPx. |
| **Territory** **`NEW`** | Claiming ground | Escalating FPx as this player passes 75, 125 and 175 receiving yards. | +{gate1}/{gate2}/{gate3} FPx at 75, 125 and 175 receiving yards |
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
| **Barrage** **`NEW`** | Keep firing | Each score raises the odds the next one pays. Escalating chance per passing TD. | +{baseFP} FP, escalating chance at {bonusFP} FP per passing TD |
| **Bonsai** | Snip snip | Grown, not gifted. Roster performance earns permanent FP growth each week. Higher levels demand bigger weeks. Resets if unequipped. | +{baseFP} FP guaranteed. This player's {triggerLabel} scale the chance to grow the base by +{growthFP} FP at week's end. Every grow slows the next. |
| **Charmed** | The dice love you | Pays out every time luck breaks your way. FP per chance card that triggered this week. | +{perTriggerFP} FP per chance card that triggered this week. |
| **Clockwork** **`NEW`** | Never misses a beat | Same time every week. Streak grows each week this player clears 25 completions. | +{baseFP} FP, +{growthPerTick} per week this player clears {threshold} completions |
| **Complacency** | Stop tinkering | Put the phone down. FP that grows each week you don't touch your roster. Stacking streak cards accelerates growth. | +{baseReward} FP, +{growthPerTick} per week roster is unchanged. |
| **Crescendo** | Keep missing, it only gets easier | Miss enough and eventually you can't miss. Each TD by this player rolls for a bonus. Miss and the odds go up. For K, triggers on FGs. | +{baseFP} FP guaranteed. {baseChance}% chance at {bonusFP} FP on this player's first {scoreNoun}, chance increases by +{chanceStep}% if bonus doesn't trigger. |
| **Custodian** **`NEW`** | Cleaning up | The throw was bad. The catch was made anyway. FP for every bailout. | +{perBailoutFP} FP per bailout by this player |
| **Dead Eye** **`NEW`** | Never off target | Week after week, right on the numbers. Streak grows with every clean sheet. | +{baseFP} FP, +{growthPerTick} per week this player records 0 bad throws |
| **Dominion** **`NEW`** | The whole field | A hundred yards a week and nobody takes it back. Streak grows each time. | +{baseFP} FP, +{growthPerTick} per week this player clears {threshold} receiving yards |
| **Getaway** **`NEW`** | Gone | Forty yards after the catch, every week. Streak grows each time. | +{baseFP} FP, +{growthPerTick} per week this player clears {threshold} YAC |
| **Houdini** **`NEW`** | Impossible to corner | The tackle was there and then it wasn't. Chance filling from broken tackles. | +{baseFP} FP guaranteed, chance at {bonusFP} FP filling from broken tackles |
| **House Call** **`NEW`** | All the way | Sometimes nobody gets a hand on it. Chance paying out on a return touchdown. | +{baseFP} FP, chance at {bonusFP} FP on a punt return TD |
| **Iron Man** **`NEW`** | Never comes off the field | Twenty carries, every single week. Streak grows each week the bar is cleared. | +{baseFP} FP, +{growthPerTick} per week this player clears {threshold} carries |
| **Landslide** **`NEW`** | Gathering weight | A hundred yards after contact, every week. Streak grows each time. | +{baseFP} FP, +{growthPerTick} per week this player clears {threshold} yards after contact |
| **Last Resort** | The ultimate insurance | When nothing else works. Guaranteed FP floor plus a chance at enhanced FP. The trigger bar fills from this player's own FP and from each of your other cards that fails to produce a bonus. | +{baseFP} FP guaranteed, chance at {enhancedFP} FP. Trigger odds fill from this player's FP plus each of your other cards that produced no bonus. |
| **Leg Day** | Never skip leg day | Never skip it. FP growing each week this player nails a 35+ yard FG. Stacking streak cards accelerates growth. | +{baseReward} FP base, +{growthPerTick} per consecutive game with a 35+ yd FG by your K. A week with no FG attempts will not break the streak. |
| **Metronome** | Never misses a beat | FP that grows each week this player clears their power bar. A cold week holds the streak rather than resetting it. | +{baseReward} FP, +{growthPerTick} per consecutive week this player clears their power bar. Streak does not reset on cold weeks. |
| **Odometer** | Every milestone pays | Hit the milestones. Escalating FP at each yardage gate this player hits. Resets weekly. | Escalating FP as this player piles up yards this week (40 / 80 / 120 / 160+). |
| **Odyssey** **`NEW`** | The long road | A hundred yards a week, week after week. Streak grows each time the mark is reached. | +{baseFP} FP, +{growthPerTick} per week this player clears {threshold} rushing yards |
| **Promised Land** **`NEW`** | Getting there | Each score raises the odds the next one pays. | +{baseFP} FP, escalating chance at {bonusFP} FP per receiving TD |
| **Snowball Fight** | Getting bigger | It just keeps getting bigger. FP growing each week your roster scores a TD. Stacking streak cards accelerates growth. | +{baseReward} FP base, +{growthPerTick} per consecutive week at least one player on your roster scores a TD. |
| **Tenure** **`NEW`** | Long service | Eight catches a week, without fail. Streak grows each week the bar is cleared. | +{baseFP} FP, +{growthPerTick} per week this player clears {threshold} receptions |
| **Traverse** | Take the long way | High stakes yardage gamble. FP floor plus a jackpot chance based on yardage by this player. | +{baseFP} FP floor + {bonusFP} FP jackpot. Jackpot chance starts at {baseChance}%, +{chancePerStep}% per {yardStep} {yardType} yards |
| **Undertaker** **`NEW`** | Bury them | Week after week the opponent starts in a hole. Streak grows with multi-pin weeks. | +{baseFP} FP, +{growthPerTick} per week this player pins {threshold}+ punts inside the 20 |

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
| **Stratosphere** **`NEW`** | Thin air up here | Territory most passers never see. Streak grows each week this player clears 300 yards. | +{baseMult} FPx, +{growthPerTick} per week this player clears {threshold} passing yards |

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

**Totals: 148 cards (39 new).**

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

As drafted, the catalogue below takes metallic from **54% FP / 14% FPx / 32% Floobits**
to **53% / 24% / 24%** — the FPx pool more than doubles, from 4 cards to 9, and Floobits
drops from a third of the tier to a quarter.

That is still short of a third FPx. Closing it needs roughly six more FPx prints under
rule 3, on the high-volume stats where a small delta is stable: completions, receiving
yards, yards after contact, carries, rush yards and receptions. **Those are not drafted
below** — each needs its own name, and the naming pass is the owner's. Flagged rather than
invented.

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
stat that separates a receiver's contribution from the quality of throw they were given.

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
