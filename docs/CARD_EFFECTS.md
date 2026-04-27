# Card Effects Reference

Complete catalog of every card effect organized by tier. For each card:

- **Effect name** — rendered in large type on both card faces (front + back).
- **Tagline** — short flavor phrase rendered in smaller type directly below the effect name on the card front. Always visible.
- **Hover tooltip** — full description that appears when the user hovers over the effect name. Not visible by default.
- **Card-back description** — the mechanic explanation rendered on the flipped (back) side of the card. Uses `{placeholder}` params that get filled with the card's stored numeric values at runtime.
- **Breakdown equation(s)** — sample output strings the calculator emits when the card triggers each week. Shown in the weekly breakdown UI next to the earned FP/Floobits. `{curly}` segments are live values; conditional branches may render different strings depending on whether the effect triggered.


## Base (29)

*Solid foundation effects. Dependable output, low ceiling.*

### Air Raid

- **Tagline:** *Bombs away*
- **Hover tooltip:** Death from above. Floobits for each passing TD your roster's QB throws.
- **Card back:** `{perTdFloobits} Floobits per passing TD by your roster's QB`
- **Breakdown equations:**
    - `{perTdF}F/TD × {tds} QB pass TD{`

### Allowance

- **Tagline:** *Weekly pocket money*
- **Hover tooltip:** Don't spend it all in one place. Free Floobits every week just for existing.
- **Card back:** `{floobits} Floobits per week`
- **Breakdown equations:** _none extracted_

### Bandwagon

- **Tagline:** *Get in, loser*
- **Hover tooltip:** Hop on the bandwagon. FPx whenever your favorite team wins.
- **Card back:** `+{rewardValue} FPx when your favorite team wins`
- **Breakdown equations:**
    - `waiting for game to end`
    - `team won this week`
    - `waiting for team win`

### Believe

- **Tagline:** *Playoffs or bust*
- **Hover tooltip:** Keep the dream alive. FP as long as your favorite team holds a playoff spot.
- **Card back:** `+{rewardValue} FP while your favorite team is in a playoff spot`
- **Breakdown equations:**
    - `waiting for game to end`
    - `team in playoffs`
    - `team not in playoffs`

### Big Deal

- **Tagline:** *Kind of a big deal*
- **Hover tooltip:** Don't you know who I am? Flat FPx on your total score.
- **Card back:** `{xMultValue}x FPx`
- **Breakdown equations:** _none extracted_

### Buy Low

- **Tagline:** *Buy the dip*
- **Hover tooltip:** Buy low, sell... whenever. Floobits for every underperforming roster player.
- **Card back:** `{perPlayerFloobits} Floobits per underperforming roster player`
- **Breakdown equations:**
    - `{perPlayer}F/player × {count} underperforming`

### Entourage

- **Tagline:** *Seeing stars*
- **Hover tooltip:** Seeing stars. Bonus FP for each high-rated player on your roster.
- **Card back:** `+{perPlayerFP} FP for every roster player with {minStars}★+`
- **Breakdown equations:**
    - `{perPlayer}/player × {count} ({minStars}★+)`

### Expedition

- **Tagline:** *Marching downfield*
- **Hover tooltip:** Yards are yards. FP that scales with how many rushing yards your roster's RB gains.
- **Card back:** `+{perFiftyYardsFP} FP per 50 rushing yards by your roster's RB`
- **Breakdown equations:**
    - `{perFiftyFP} FP/50yds × {rushYards} rush yds = +{fp} FP`

### Freebie

- **Tagline:** *Free real estate*
- **Hover tooltip:** It's free. Bonus FP every week.
- **Card back:** `+{baseFP} FP per week`
- **Breakdown equations:** _none extracted_

### Garbage Time

- **Tagline:** *Participation trophies*
- **Hover tooltip:** Hey, they showed up. Bonus FP for each roster player who doesn't score a TD.
- **Card back:** `+{perPlayerFP} FP for every roster player with 0 TDs`
- **Breakdown equations:**
    - `{perPlayer}/player × {count} (0 TD players)`

### Goal Line Vulture

- **Tagline:** *Opportunistic scavenging*
- **Hover tooltip:** Vulture season. Floobits for every rushing TD your roster's RB punches in.
- **Card back:** `{perTdFloobits} Floobits per rushing TD by your roster's RB`
- **Breakdown equations:**
    - `{perTd}/TD × {tds} RB rush TDs`

### Gunslinger

- **Tagline:** *Slinging it*
- **Hover tooltip:** Let it fly. FP that scales with how many passing yards your roster's QB racks up.
- **Card back:** `+{perHundredYardsFP} FP per 100 passing yards by your roster's QB`
- **Breakdown equations:**
    - `{perHundredFP} FP/100yds × {passYards} pass yds = +{fp} FP`

### Homer

- **Tagline:** *Hometown discount*
- **Hover tooltip:** Loyalty has its perks. FP scaling with how many of your roster players play on your favorite team.
- **Card back:** `+{perPlayerFP} FP per roster player on your favorite team`
- **Breakdown equations:**
    - `{perPlayer}/player × {count} on your favorite team`

### Honor Roll

- **Tagline:** *Straight A's*
- **Hover tooltip:** Good grades get rewarded. Bonus FP for each roster player putting up a solid score.
- **Card back:** `+{perPlayerFP} FP per roster player with {fpThreshold}+ FP`
- **Breakdown equations:**
    - `{perPlayer}/player × {count} ({threshold}+ FP)`

### Hot Stove

- **Tagline:** *Everyone's cooking*
- **Hover tooltip:** When they're hot, they're HOT. FP per overperforming roster player.
- **Card back:** `+{perPlayerFP} FP per overperforming roster player`
- **Breakdown equations:**
    - `{perPlayerFP}/player × {count} overperforming`
    - `1 + ({perPlayer}/player × {count} overperforming) = {1 + bonus:.2f}x`

### Industrious

- **Tagline:** *Honest work*
- **Hover tooltip:** Honest work deserves honest pay. Floobits scaling with receptions by your roster's TE.
- **Card back:** `{perReceptionFloobits} Floobits per reception by your roster's TE`
- **Breakdown equations:**
    - `{perRec}F/rec × {recs} TE receptions`

### Piggy Bank

- **Tagline:** *Points into coins*
- **Hover tooltip:** Automatic savings plan. Converts a chunk of your roster's total FP into Floobits.
- **Card back:** `{fpPercent}% of roster FP → Floobits`
- **Breakdown equations:**
    - `{pct}% × {round(ctx.weekRawFP, 1)} roster FP`

### Possession

- **Tagline:** *Catch everything*
- **Hover tooltip:** Chain-mover. FP that scales with how many catches your roster's WRs haul in combined.
- **Card back:** `+{perReceptionFP} FP per reception by your roster's WRs (combined)`
- **Breakdown equations:**
    - `{perRec}/rec × {recs} WR receptions`

### RNG

- **Tagline:** *Feeling lucky?*
- **Hover tooltip:** Feeling lucky? Random FP rolled each week.
- **Card back:** `Random +{minFP}–{maxFP} FP each week`
- **Breakdown equations:**
    - `Rolled +{rolledFP} FP (range {minFP}–{maxFP})`

### Reclamation

- **Tagline:** *Fixer's bonus*
- **Hover tooltip:** Someone has to fix this mess. FP when most of your roster is underperforming.
- **Card back:** `+{rewardValue} FP when majority of roster is underperforming`
- **Breakdown equations:**
    - `waiting for game to end`
    - `{underperforming}/{total} underperforming`
    - `{underperforming} / {needed} needed underperforming`

### Safety Blanket

- **Tagline:** *Reliable target*
- **Hover tooltip:** Every QB needs one. FP scaling with receptions by your roster's TE.
- **Card back:** `+{perReceptionFP} FP per reception by your roster's TE`
- **Breakdown equations:**
    - `{perRec}/rec × {recs} TE receptions`

### Showoff

- **Tagline:** *Your {posLabel} showed up*
- **Hover tooltip:** Your {posLabel} had a good day. FP when your roster's {posLabel} overperforms expectations in a single game.
- **Card back:** `+{rewardValue} FP when your roster's {posLabel} has a strong game`
- **Breakdown equations:**
    - `Waiting for games to complete`
    - `no roster player at position`
    - `{playerName} overperformed`

### Slippery

- **Tagline:** *Can't bring me down*
- **Hover tooltip:** Yards after the catch turn into points. FP that scales with your roster's WRs' combined YAC.
- **Card back:** `+{perYacFP} FP per 10 YAC by your roster's WRs`
- **Breakdown equations:**
    - `{perYac}/10yac × {yac} YAC`

### Sniper

- **Tagline:** *From downtown*
- **Hover tooltip:** From long range. FP for each field goal your roster's K makes from 40+ yards out.
- **Card back:** `+{perFgFP} FP per 40+ yard FG by your roster's K`
- **Breakdown equations:**
    - `{perFg}/FG × {fg40plus} FGs 40+ yds`

### Three Pointer

- **Tagline:** *Count it*
- **Hover tooltip:** Three points for them, bonus for you. FP for every kicker FG.
- **Card back:** `+{perFgFP} FP for every FG your roster's K makes`
- **Breakdown equations:**
    - `{perFg}/FG × {fgMade} FGs made`

### Touchdown Piñata

- **Tagline:** *Smash for points*
- **Hover tooltip:** Every house call fills the piñata. Bonus FP per roster TD.
- **Card back:** `+{perTdFP} FP for every TD your roster scores`
- **Breakdown equations:**
    - `{perTd}/TD × {tds} roster TDs`

### Trust Fund

- **Tagline:** *Set it and collect*
- **Hover tooltip:** The lazy investor strategy. Floobits that grow each week your roster stays unchanged.
- **Card back:** `{baseFloobits} Floobits base, +{growthPerWeek} per unchanged week`
- **Breakdown equations:**
    - `{baseFloobits}F base + ({growth}F × {weeks} wks unchanged)`

### Windfall

- **Tagline:** *Cashing in*
- **Hover tooltip:** When your players ball out, you get paid. Floobits per overperforming roster player.
- **Card back:** `+{perPlayerFloobits}F per overperforming roster player`
- **Breakdown equations:**
    - `{perPlayer}F/player × {count} overperforming = +{bonus}F`

### Workhorse

- **Tagline:** *Feed the beast*
- **Hover tooltip:** Pound the rock. FP scaling with rushing attempts by your roster's RB.
- **Card back:** `+{perAttemptFP} FP per rushing attempt by your roster's RB`
- **Breakdown equations:**
    - `{perAttFP} FP/att × {attempts} rush attempts = +{fp} FP`


## Holographic (28)

*Dependable cards with higher ceiling than base. Most have a flat floor plus a bonus on a trigger condition.*

### Backfield Buddies

- **Tagline:** *Same backfield*
- **Hover tooltip:** Same backfield, double the payoff. FPx when your roster's QB and RB play on the same team.
- **Card back:** `+{rewardValue} FPx when your roster's QB and RB share a team`
- **Breakdown equations:**
    - `{1 + rewardValue:.2f}x FPx (QB + RB on same team)`
    - `QB and RB not on same team`

### Blue Ribbon

- **Tagline:** *Pedigree*
- **Hover tooltip:** Prize winner. FP with a bonus when your favorite team's ELO reaches elite status (1600+).
- **Card back:** `+{baseFP} FP base, +{rewardValue} FP when your favorite team's ELO ≥ {eloThreshold}`
- **Breakdown equations:**
    - `waiting for game to end`
    - `{mult}x (legacy, ELO {teamElo})`
    - `{baseMult}x (legacy, ELO {teamElo})`
    - `+{rewardValue} FP (team ELO {teamElo} >= {eloThreshold})`
    - `+{baseFP} FP (team ELO {teamElo}, need {eloThreshold} for full bonus)`

### Cha-Ching

- **Tagline:** *Cash out*
- **Hover tooltip:** The endzone is your cash register. Floobits for every TD your roster's {posLabel} scores.
- **Card back:** `{perTdFloobits} Floobits per TD by your roster's {posLabel}`
- **Breakdown equations:**
    - `{perTd}F/TD × {rosterTds} roster {posLabel} TDs`

### Clique

- **Tagline:** *BFFs*
- **Hover tooltip:** Always together. Floobits when 3 or more of your roster players share the same team.
- **Card back:** `+{rewardFloobits} Floobits when 3+ roster players share a team`
- **Breakdown equations:**
    - `+{rewardFloobits}F ({len(pids)} players on same team)`
    - `{rewardValue}x (legacy)`
    - `Max {maxGroup} on same team (need 3+)`

### Closers

- **Tagline:** *See this watch?*
- **Hover tooltip:** Always be closing. Bonus FP from your roster's Q4 and OT production.
- **Card back:** `+{q4MultFactor}x bonus on all Q4/OT FP earned by your roster`
- **Breakdown equations:**
    - `Waiting for games to complete`
    - `No Q4/OT fantasy points`
    - `{q4MultFactor}x × {round(totalQ4FP, 1)} Q4/OT FP = +{bonus}`

### Diversified

- **Tagline:** *Variety pack*
- **Hover tooltip:** Don't put all your eggs in one basket. FP per unique output type (FP, FPx, Floobits) across your equipped cards.
- **Card back:** `+{perTypeFP} FP per unique output type in your hand`
- **Breakdown equations:**
    - `{perType}/type × {count} unique output types`

### Double Trouble

- **Tagline:** *Both WRs deliver*
- **Hover tooltip:** Two is better than one. FP when either WR scores a TD, bonus when both WRs score.
- **Card back:** `+{singleWrFP} FP when a WR scores, +{rewardValue} bonus FP when both WRs score`
- **Breakdown equations:**
    - `+{singleFP} FP (1st WR TD) + {bothFP} FP (2nd WR TD) = +{total} FP`
    - `+{singleFP} FP (1 WR scored — need both for +{bothFP} bonus)`
    - `No WR TDs this week`

### Fat Cat

- **Tagline:** *Rolling in it*
- **Hover tooltip:** Money talks. FP that scales with your Floobits balance. Excludes current week earnings.
- **Card back:** `+1 FP per {floobitsPerFP} Floobits in your balance (max {maxFP} FP)`
- **Breakdown equations:**
    - `No Floobits in balance`
    - `{balance}F ÷ {floobitsPerFP} = {rawFP:.1f} FP (cap {maxFP}) = +{bonus}`

### Feeding Frenzy

- **Tagline:** *Eat up*
- **Hover tooltip:** Dinner is served. Floobits per roster TD, plus a jackpot bonus when your roster hits the TD threshold.
- **Card back:** `{perTdFloobits}F per roster TD, +{bonusFloobits}F jackpot at {tdThreshold}+ TDs`
- **Breakdown equations:**
    - `{perTd}F × {tds} TDs + {bonus}F bonus = {total}F`
    - `{perTd}F × {tds} TDs = {perTdPayout}F ({tdThreshold - tds} more for +{bonus}F bonus)`
    - `no roster TDs yet ({tdThreshold} for bonus)`

### Gone Streaking

- **Tagline:** *CENSORED*
- **Hover tooltip:** Don't look away. FP based on your favorite team's longest streak (wins or losses).
- **Card back:** `+{baseFP} FP base, +{perStreakFP} per game in longest streak`
- **Breakdown equations:**
    - `{baseFP} base + ({perStreakFP} × {peakStreak} peak streak)`

### Good Neighbor

- **Tagline:** *You're covered*
- **Hover tooltip:** Worry free. Guaranteed Floobits plus a bonus for each FG your kicker misses.
- **Card back:** `+{baseFloobits}F base + {perMissFloobits}F per missed FG this week`
- **Breakdown equations:**
    - `+{baseFloobits}F base + {perMissFloobits}F × {weekMisses} missed FG{`
    - `+{baseFloobits}F base (no missed FGs this week)`

### Group Project

- **Tagline:** *Everyone showed up*
- **Hover tooltip:** Everyone chipped in. FP if 4 or more of your other cards triggered a non-zero bonus this week.
- **Card back:** `+{rewardValue} FP when 4+ of your other cards triggered`
- **Breakdown equations:**
    - `+{rewardValue} FP ({triggeredCount}/4+ cards triggered)`
    - `{triggeredCount}/4 cards triggered (need 4+)`

### Hedge

- **Tagline:** *Downside protection*
- **Hover tooltip:** Insurance policy. Starts with an FP pool. Roster FP subtracts from it, and whatever remains is your payout.
- **Card back:** `Starts with a {floorFP} FP pool. FP earned by your roster is subtracted from the pool. Pays out whatever remains`
- **Breakdown equations:**
    - `{floorFP} floor − {rosterFP} roster FP = +{bonus} FP`
    - `Roster scored {rosterFP} FP (above {floorFP} floor — no hedge needed)`

### Highlight Reel

- **Tagline:** *Did you see that?*
- **Hover tooltip:** Highlight reel material. Floobits for every big play your favorite team pulls off.
- **Card back:** `{rewardValue} Floobits per your favorite team's big plays`
- **Breakdown equations:**
    - `{perPlay}F/play × {plays} big plays`
    - `waiting for big plays`

### Hype Man

- **Tagline:** *Your {posLabel}'s biggest fan*
- **Hover tooltip:** The crowd goes wild. FP that stacks with each TD your roster's {posLabel} scores.
- **Card back:** `+{perTdFP} FP per TD by your roster's {posLabel}`
- **Breakdown equations:**
    - `{perTdFP}/TD × {rosterTds} roster {posLabel} TD{`
    - `{perTdFP} FP/TD × 0 roster {posLabel} TDs`

### Jailbreak

- **Tagline:** *Breaking out*
- **Hover tooltip:** Can't catch them. Base FP every week, plus bonus FP when your roster's WRs combine for enough yards after catch.
- **Card back:** `+{baseFP} FP base, +{rewardValue} bonus if your roster's WRs combine for {threshold}+ YAC`
- **Breakdown equations:**
    - `{baseFP} base + {bonusFP} bonus ({yac} YAC >= {threshold})`
    - `{baseFP} base ({yac}/{threshold} YAC)`

### Lead Blocker

- **Tagline:** *Paving the way*
- **Hover tooltip:** Clearing the path. FP per TD by your TE. RB TDs count as TE TDs if they are on the same team.
- **Card back:** `+{perTdFP} FP per TE TD (same-team RB TDs count as TE TDs)`
- **Breakdown equations:**
    - `{perTd}/TD × {totalTds} TDs ({`
    - `No TDs by TE or same-team RBs`

### Loyalty Bonus

- **Tagline:** *Faithful fan rewards*
- **Hover tooltip:** Bandwagoning encouraged. Bonus FP based on your favorite team's win streak.
- **Card back:** `+{perStreakFP} FP per win in your favorite team's streak`
- **Breakdown equations:**
    - `{perStreak}/win × {streak} win streak`

### Luminary

- **Tagline:** *Your {posLabel} runs the show*
- **Hover tooltip:** Your {posLabel} runs the offense. FPx that increases the more FP your roster's {posLabel} earns.
- **Card back:** `FPx that grows the more FP your roster's {posLabel} earns compared to teammates`
- **Breakdown equations:**
    - `1 + ({scale} × {round(fpShare * 100)}% roster {posLabel} FP share)`

### Mismatch

- **Tagline:** *Too big, too fast*
- **Hover tooltip:** They can't cover this guy. FP per TD by your roster's {posLabel}, plus a bonus when they score multiple TDs.
- **Card back:** `+{perTdFP} FP per TD by your roster's {posLabel}, +{bonusFP} bonus at {tdThreshold}+ TDs`
- **Breakdown equations:**
    - `{perTdFP}/TD × {tds} {posLabel} TDs + {bonusFP} bonus = +{total} FP`
    - `{perTdFP}/TD × {tds} {posLabel} TDs = +{perTdPayout} FP ({tdThreshold - tds} more for +{bonusFP} bonus)`
    - `no {posLabel} TDs ({tdThreshold} for bonus)`

### Pocket Aces

- **Tagline:** *AA*
- **Hover tooltip:** Pocket Rockets. Base FP every week, plus bonus FP when your roster's WRs hit a combined stat threshold.
- **Card back:** `+{baseFP} FP base, +{rewardValue} bonus if your roster's WRs combine for {threshold}+ {statDisplay}`
- **Breakdown equations:**
    - `{baseFP} base + {bonusFP} bonus (WR {stat}: {round(actualValue)} >= {threshold})`
    - `{baseFP} base (WR {stat}: {round(actualValue)} / {threshold})`

### Spectacle

- **Tagline:** *Career day*
- **Hover tooltip:** Going off. FP that scales with how much your roster's {posLabel} overperforms expectations this week.
- **Card back:** `+{perPointFP} FP per point your roster's {posLabel} overperforms by`
- **Breakdown equations:**
    - `Waiting for games to complete`
    - `Did not overperform`
    - `Overperformed — +{bonus} FP`
    - `Overperformed — {bonus}x FP`

### Spotlight Moment

- **Tagline:** *Lights please*
- **Hover tooltip:** Lights, camera, action. FP whenever your roster's {posLabel} scores a TD. For WR, either counts.
- **Card back:** `+{rewardValue} FP when your roster's {posLabel} scores a TD. WR counts both combined`
- **Breakdown equations:**
    - `roster {posLabel} scored {rosterTds} TD{`
    - `waiting for roster {posLabel} TD`

### Stack

- **Tagline:** *QB-WR stack*
- **Hover tooltip:** Stack attack. FPx when your roster's QB and any WR play on the same team.
- **Card back:** `{rewardValue} FPx when your roster's QB and WR share a team`
- **Breakdown equations:**
    - `{rewardValue} (QB + WR on same team)`
    - `QB and WR not on same team`

### Stampede

- **Tagline:** *Unstoppable force*
- **Hover tooltip:** Get rolling. Base FPx, enhanced FPx when your roster's RB hits 75+ rushing yards.
- **Card back:** `{baseMult}x FPx normally, {enhancedMult}x FPx when your RB hits {yardThreshold}+ rush yards`
- **Breakdown equations:**
    - `{enhancedMult:.2f}x FPx ({rushYards} rush yds >= {threshold})`
    - `{baseMult:.2f}x FPx (base — {rushYards} rush yds < {threshold})`

### Surplus

- **Tagline:** *More where that came from*
- **Hover tooltip:** Raise the ceiling. Increases the maximum Floobits you can earn per week while equipped.
- **Card back:** `Weekly Floobits cap raised by +{ceilingBonus} while equipped`
- **Breakdown equations:**
    - `+{ceilingBonus} cap raise (effective cap: {newCap}F)`

### Trebuchet

- **Tagline:** *Siege engine*
- **Hover tooltip:** Send it deep. Base FP every week, plus bonus FP when either of your roster's WRs catches a pass of 25+ yards.
- **Card back:** `+{baseFP} FP base, +{rewardValue} bonus if your roster's WR catches a {threshold}+ yard pass`
- **Breakdown equations:**
    - `{baseFP} base + {bonusFP} bonus (WR longest: {bestCatch} yd)`
    - `{baseFP} base (WR longest: {bestCatch}/{threshold} yd)`

### Upset Special

- **Tagline:** *Giant slayer*
- **Hover tooltip:** Giant killer. FP when your favorite team beats a higher-rated opponent.
- **Card back:** `+{rewardValue} FP when your favorite team beats a higher-ELO team`
- **Breakdown equations:**
    - `waiting for game to end ({matchupTag})`
    - `waiting for game to end`
    - `upset win {matchupTag}`
    - `no upset win ({matchupTag})`
    - `no upset win`


## Prismatic (39)

*Powerful cards: chance rolls, streak growth, and game-outcome payouts. Higher ceilings and more variance.*

### All In

- **Tagline:** *Eggs + basket*
- **Hover tooltip:** Bet big on one position. FPx that grows with how many of your equipped cards share the same position.
- **Card back:** `{baseXMult} FPx + {perDuplicateXMult} per duplicate position card`
- **Breakdown equations:**
    - `No cards equipped`
    - `No duplicate positions`
    - `{baseXMult} base + ({perDupe} × {dupes} dupes) = {bonus}`

### Automatic

- **Tagline:** *Perfect kicks only*
- **Hover tooltip:** Perfection pays. FP growing each consecutive week your roster's K goes perfect on FGs. Resets on a miss. Stacking streak cards accelerates growth.
- **Card back:** `+{baseReward} FP, +{growthPerTick} per consecutive perfect FG week. Resets on a miss. Each other streak card adds +1 bonus tick`
- **Breakdown equations:**
    - `{baseReward} base + ({growthPerTick}/TD × {ticks} TDs)`
    - `{baseReward} base`
    - `{baseReward} base + ({growthPerTick}/streak × {growthTicks} [{max(0, streakCount - 1)} wk + {peerBonus} synergy])`
    - `{baseReward} base + ({growthPerTick}/streak × {max(0, streakCount - 1)})`

### Avalanche

- **Tagline:** *Bury them*
- **Hover tooltip:** Momentum builds with every score. Each roster TD pays more FP than the last.
- **Card back:** `Roster TDs pay escalating FP: 1st={td1}, 2nd={td2}, 3rd={td3}, 4th={td4} then diminishing`
- **Breakdown equations:**
    - `No roster TDs this week`
    - `{tds} roster TD{`

### Babysitter

- **Tagline:** *Carrying the team*
- **Hover tooltip:** Someone has to do the heavy lifting. Guaranteed FP floor plus a chance at enhanced FP. Odds increase the more roster players underperform.
- **Card back:** `+{baseFP} FP guaranteed, chance at {enhancedFP} FP. 20% with 1 underperformer (under {fpThreshold} FP), up to 70%`
- **Breakdown equations:**
    - `+{baseFP} FP. No players under {threshold} FP`

### Bandwagon Express

- **Tagline:** *Choo choo!*
- **Hover tooltip:** Next stop: more points. FP growing each week your favorite team wins. Resets on a loss. Stacking streak cards accelerates growth.
- **Card back:** `+{baseReward} FP, +{growthPerTick} per consecutive your favorite team's wins. Resets on loss. Each other streak card adds +1 bonus tick`
- **Breakdown equations:**
    - `{baseReward} base + ({growthPerTick}/TD × {ticks} TDs)`
    - `{baseReward} base`
    - `{baseReward} base + ({growthPerTick}/streak × {growthTicks} [{max(0, streakCount - 1)} wk + {peerBonus} synergy])`
    - `{baseReward} base + ({growthPerTick}/streak × {max(0, streakCount - 1)})`

### Bonsai

- **Tagline:** *Snip snip*
- **Hover tooltip:** Grown, not gifted. Roster performance earns permanent FP growth each week. Higher levels demand bigger weeks. Resets if unequipped.
- **Card back:** `+{baseFP} FP base. Each week {triggerLabel} earn a chance to permanently grow by {growthFP} FP. Higher levels need bigger weeks to keep growing.`
- **Breakdown equations:**
    - `+{currentFP} FP. {growthChance}% chance{triggerNote} to grow to +{nextFP} FP`

### Chain Reaction

- **Tagline:** *Cards feeding cards*
- **Hover tooltip:** Cards feeding cards. FPx that scales with how many of your other 4 cards produced a non-zero bonus.
- **Card back:** `{perCardXMult} FPx per other card that produced a bonus`
- **Breakdown equations:**
    - `1 + ({perCard} × {triggeredCount} triggered cards) = {bonus}`
    - `No other cards triggered`

### Comeback Kid

- **Tagline:** *Never count them out*
- **Hover tooltip:** Down but never out. Base FP every week, plus a big bonus when your favorite team comes back from a deficit to win.
- **Card back:** `+{baseFP} FP base, +{perPointFP} FP per point of deficit overcome on a favorite-team comeback win`
- **Breakdown equations:**
    - `Waiting for games to complete`
    - `{baseFP} base + {perPoint}/pt × {deficit} pt deficit = +{total} FP`
    - `{baseFP} base (no comeback win)`

### Complacency

- **Tagline:** *Stop tinkering*
- **Hover tooltip:** Put the phone down. FP that grows each week you don't touch your roster. Resets if you make a swap. Stacking streak cards accelerates growth.
- **Card back:** `+{baseReward} FP, +{growthPerTick} per week roster is unchanged. Resets on swap`
- **Breakdown equations:**
    - `{baseReward} base + ({growthPerTick}/TD × {ticks} TDs)`
    - `{baseReward} base`
    - `{baseReward} base + ({growthPerTick}/streak × {growthTicks} [{max(0, streakCount - 1)} wk + {peerBonus} synergy])`
    - `{baseReward} base + ({growthPerTick}/streak × {max(0, streakCount - 1)})`

### Consolation Prize

- **Tagline:** *Better luck next time*
- **Hover tooltip:** Here's a little something for your troubles. Guaranteed Floobits floor plus a chance at enhanced Floobits. Odds increase the more roster players have a bad week.
- **Card back:** `+{baseFloobits}F guaranteed, chance at {enhancedFloobits}F. 20% with 1 underperformer (under {fpThreshold} FP), up to 70%`
- **Breakdown equations:**
    - `{perPlayer}F/player × {count} (under {threshold} FP)`
    - `+{baseFloobits}F. No players under {threshold} FP`

### Copycat

- **Tagline:** *Imitation is flattery*
- **Hover tooltip:** Copies the best. FP equal to the highest flat FP bonus from your other cards.
- **Card back:** `+FP equal to highest flat FP bonus from your other cards`
- **Breakdown equations:**
    - `+{bestFP:.1f} FP (copied from best card)`
    - `No other cards produced FP`

### Cornucopia

- **Tagline:** *Every touchdown compounds*
- **Hover tooltip:** Every touchdown compounds. FPx that stacks per roster TD.
- **Card back:** `+{perTdMult} FPx per roster TD`
- **Breakdown equations:**
    - `1 + ({perTd}/TD × {tds} roster TDs) = {1 + bonus:.2f}x`

### Crescendo

- **Tagline:** *Keep missing, it only gets easier*
- **Hover tooltip:** Miss enough and eventually you can't miss. Each TD by your roster's {posLabel} rolls for a bonus. Miss and the odds go up. For K, triggers on FGs.
- **Card back:** `+{baseFP} FP guaranteed, chance at {bonusFP} FP. Your roster's {posLabel} rolls {baseChance}% per TD, +{chanceStep}% each miss`
- **Breakdown equations:**
    - `+{baseFP} FP. 0 {triggerLabel}`
    - `+{bonusFP} FP. Hit on {triggerLabel[:-1]} #{hitOnTrigger} of {triggers} ({pctStr})`
    - `+{baseFP} FP. {triggers} {triggerLabel}, maxed at {pctStr}, missed`

### Dark Horse

- **Tagline:** *Nobody saw them coming*
- **Hover tooltip:** The stars shine brightest from below. FPx that scales inversely with the star rating of your roster's {posLabel}.
- **Card back:** `+{perStarMult} FPx per star under 5 of your rostered {posLabel}`
- **Breakdown equations:**
    - `No rostered player at position`
    - `Rostered player is 5★ (no bonus)`
    - `1.0 + {perStarMult}/star × {avgStarsUnder:.1f} stars under 5 ({posLabel}) = {mult}x`

### Domination

- **Tagline:** *Total destruction*
- **Hover tooltip:** Run up the score. Floor FP on a loss, more on a win, and a big bonus for blowout victories.
- **Card back:** `+{lossFP} FP floor on loss, +{baseFP} FP on favorite-team win, +{rewardValue} FP on blowout ({marginThreshold}+ pt margin)`
- **Breakdown equations:**
    - `Waiting for games to complete`
    - `+{rewardValue} FP (your favorite team won by {margin}, blowout!)`
    - `+{baseFP} FP (your favorite team won by {margin})`
    - `+{lossFP} FP floor (your favorite team lost)`

### Eminence

- **Tagline:** *Stats don't lie*
- **Hover tooltip:** Good players get paid more. FPx that scales with how far above position average your player performs. Active from week 3.
- **Card back:** `+{bonusPerFP} FPx for each FP/game your {posLabel} scores above the league average at that position. Max {maxMult}x. Active from week 3.`
- **Breakdown equations:**
    - `1.00x FPx — inactive until week 3`
    - `1.00x FPx — no position data yet`
    - `1.00x FPx — {abovePace:+.1f} below pace ({playerAvg:.1f} vs {posAvg:.1f} avg)`
    - `{mult:.2f}x FPx — {abovePace:+.1f} above pace ({playerAvg:.1f} vs {posAvg:.1f} avg)`

### Fairweather Fan

- **Tagline:** *Only here for the wins*
- **Hover tooltip:** Fair-weather fandom has its perks. Floobits growing each week your favorite team wins. Resets on a loss. Stacking streak cards accelerates growth.
- **Card back:** `{baseReward} Floobits, +{growthPerTick} per consecutive your favorite team's wins. Resets on loss. Each other streak card adds +1 bonus tick`
- **Breakdown equations:**
    - `{baseReward} base + ({growthPerTick}/TD × {ticks} TDs)`
    - `{baseReward} base`
    - `{baseReward} base + ({growthPerTick}/streak × {growthTicks} [{max(0, streakCount - 1)} wk + {peerBonus} synergy])`
    - `{baseReward} base + ({growthPerTick}/streak × {max(0, streakCount - 1)})`

### Gold Rush

- **Tagline:** *Floobits love company*
- **Hover tooltip:** Floobits cards amplify each other. Floobits bonus for each other floobits card in your hand.
- **Card back:** `{perCardFloobits} Floobits per other floobits card in your hand`
- **Breakdown equations:**
    - `{perCard}/card × {otherFloobits} other floobits cards`

### Home Alone

- **Tagline:** *Keep the change, ya filthy animal*
- **Hover tooltip:** Embrace the void. FPx that grows with each empty roster slot.
- **Card back:** `+{perSlotMult} FPx per empty roster slot`
- **Breakdown equations:**
    - `No empty roster slots`
    - `1.0 + {perSlotMult}/slot × {emptySlots} empty = {mult}x`

### House Money

- **Tagline:** *Playing with profit*
- **Hover tooltip:** Upset city. FP that builds every time your favorite team wins as an underdog.
- **Card back:** `+{baseFP} FP base, +{perUpsetFP} per your favorite team's upset wins this season`
- **Breakdown equations:**
    - `{baseFP} base + {perUpsetFP}/upset × {upsetWins} upset wins = +{bonus} FP`
    - `{baseXMult} base + ({perUpset}x × {upsetWins} upset wins)`

### Indemnity

- **Tagline:** *Consolation floobits*
- **Hover tooltip:** At least you got floobits. Guaranteed Floobits floor plus a chance at enhanced Floobits. Odds increase the more your roster's {posLabel} underperforms.
- **Card back:** `+{baseFloobits}F guaranteed, chance at {enhancedFloobits}F. Chance grows with {posLabel} underperformance, up to 70%`
- **Breakdown equations:**
    - `Waiting for games to complete`
    - `Underperformed — +{floobits} Floobits`
    - `Did not underperform`
    - `+{baseFloobits}F. Did not underperform`

### Juggernaut

- **Tagline:** *I'M THE JUGGERNAUT*
- **Hover tooltip:** Momentum is a beautiful thing. FPx grows with every win in your favorite team's win streak.
- **Card back:** `{baseXMult} FPx, grows by {growthPerWin} per your favorite team's win streak`
- **Breakdown equations:**
    - `Waiting for win to extend streak`
    - `{baseX}x base + ({growth}x × {streak} win streak)`

### Last Resort

- **Tagline:** *The ultimate insurance*
- **Hover tooltip:** When nothing else works. Guaranteed FP floor plus a chance at enhanced FP. Odds increase the more of your other cards fail to produce a bonus.
- **Card back:** `+{baseFP} FP guaranteed, chance at {enhancedFP} FP. 15% per card that didn't trigger, up to 70%`
- **Breakdown equations:**
    - `{rewardValue} (no other cards produced a bonus)`
    - `{triggeredCount} other card(s) produced a bonus`
    - `{baseMult}x FPx (legacy)`
    - `+{baseFP} FP. All cards triggered`

### Leg Day

- **Tagline:** *Never skip leg day*
- **Hover tooltip:** Never skip it. FP growing each week your roster's K nails a 35+ yard FG. Stacking streak cards accelerates growth.
- **Card back:** `+{baseReward} FP, +{growthPerTick} per consecutive 35+ yd FG week. Each other streak card adds +1 bonus tick`
- **Breakdown equations:**
    - `{baseReward} base + ({growthPerTick}/TD × {ticks} TDs)`
    - `{baseReward} base`
    - `{baseReward} base + ({growthPerTick}/streak × {growthTicks} [{max(0, streakCount - 1)} wk + {peerBonus} synergy])`
    - `{baseReward} base + ({growthPerTick}/streak × {max(0, streakCount - 1)})`

### Martyr

- **Tagline:** *Embrace the tank*
- **Hover tooltip:** Pain builds character. FP floor plus a chance at enhanced FP. Odds scale with your favorite team's season losses.
- **Card back:** `+{baseFP} FP guaranteed, chance at {enhancedFP} FP. 10% at 1 loss, grows with your favorite team's season losses, up to 60%`
- **Breakdown equations:**
    - `1 + ({perLoss}/loss × {losses} team losses) = {1 + bonus:.2f}x`
    - `{baseMult:.2f}x FPx (legacy base)`
    - `{enhancedMult:.2f}x FPx (legacy enhanced)`
    - `+{baseFP} FP. Game not final`

### Momentum

- **Tagline:** *Rolling*
- **Hover tooltip:** Can't stop won't stop. FPx grows each week your roster breaks 75 FP. Resets if they don't. Stacking streak cards accelerates growth.
- **Card back:** `{baseReward} FPx, +{growthPerTick} per consecutive week roster scores 75+ FP. Resets if under 75. Each other streak card adds +1 bonus tick`
- **Breakdown equations:**
    - `{baseReward} base + ({growthPerTick}/TD × {ticks} TDs)`
    - `{baseReward} base`
    - `{baseReward} base + ({growthPerTick}/streak × {growthTicks} [{max(0, streakCount - 1)} wk + {peerBonus} synergy])`
    - `{baseReward} base + ({growthPerTick}/streak × {max(0, streakCount - 1)})`

### Odometer

- **Tagline:** *Every milestone pays*
- **Hover tooltip:** Hit the milestones. Escalating FP at each yardage gate your roster hits. Resets weekly.
- **Card back:** `Escalating FP at 200, 400, 600, and 800+ total roster yards. Resets weekly`
- **Breakdown equations:**
    - `{totalYards} roster yds — next gate at {nextGate[`
    - `{totalYards} roster yds: {`

### On Fire

- **Tagline:** *Keep the flame alive*
- **Hover tooltip:** Don't let the flame die. FPx that grows each week your roster's K makes a FG. Resets if they don't. Stacking streak cards accelerates growth.
- **Card back:** `{baseReward} FPx, +{growthPerTick} per consecutive FG week. Resets if no FG. Each other streak card adds +1 bonus tick`
- **Breakdown equations:**
    - `{baseReward} base + ({growthPerTick}/TD × {ticks} TDs)`
    - `{baseReward} base`
    - `{baseReward} base + ({growthPerTick}/streak × {growthTicks} [{max(0, streakCount - 1)} wk + {peerBonus} synergy])`
    - `{baseReward} base + ({growthPerTick}/streak × {max(0, streakCount - 1)})`

### Providence

- **Tagline:** *A little something extra*
- **Hover tooltip:** Fortune favors the prepared. FPx bonus plus chance boost to all chance cards in your hand.
- **Card back:** `{baseMult}x FPx + boosts all chance card odds by {chanceBonus}`
- **Breakdown equations:**
    - `{baseMult}x + {chanceBonus:.0%} chance boost`

### Rising Tide

- **Tagline:** *Lifts all boats*
- **Hover tooltip:** A rising tide lifts all boats. FPx that grows with each roster player outperforming their rating.
- **Card back:** `+{perPlayerMult} FPx per overperforming roster player (max {maxMult}x)`
- **Breakdown equations:**
    - `1 + ({perPlayer}/player × {count} overperforming) = {mult:.2f}x (max {maxMult}x)`

### Rock Bottom

- **Tagline:** *Silver lining*
- **Hover tooltip:** Rock bottom has a cash reward. Guaranteed Floobits floor plus a chance at enhanced Floobits. Odds increase the longer your favorite team's losing streak.
- **Card back:** `+{baseFloobits}F guaranteed, chance at {enhancedFloobits}F. 20% at 1-game losing streak, up to 65%`
- **Breakdown equations:**
    - `{perStreak}F/loss × {lossStreak} loss streak`
    - `+{baseFloobits}F. No losing streak`

### Scrappy

- **Tagline:** *Root for the little guy*
- **Hover tooltip:** Somebody has to believe in them. Guaranteed FP floor plus a chance at enhanced FP. Odds increase the more low-rated players are on your roster.
- **Card back:** `+{baseFP} FP guaranteed, chance at {enhancedFP} FP. 25% with 1 low-rated player ({maxStars}★ or below), up to 75%`
- **Breakdown equations:**
    - `{perPlayer}/player × {count} ({maxStars}★ or lower)`
    - `+{baseFP} FP. No {maxStars}★ or lower players`

### Snowball Fight

- **Tagline:** *Getting bigger*
- **Hover tooltip:** It just keeps getting bigger. FP growing each week your roster scores a TD. Resets if they don't. Stacking streak cards accelerates growth.
- **Card back:** `+{baseReward} FP, +{growthPerTick} per consecutive roster TD week. Resets if no TD. Each other streak card adds +1 bonus tick`
- **Breakdown equations:**
    - `{baseReward} base + ({growthPerTick}/TD × {ticks} TDs)`
    - `{baseReward} base`
    - `{baseReward} base + ({growthPerTick}/streak × {growthTicks} [{max(0, streakCount - 1)} wk + {peerBonus} synergy])`
    - `{baseReward} base + ({growthPerTick}/streak × {max(0, streakCount - 1)})`

### Stockpiler

- **Tagline:** *Saving for a rainy day*
- **Hover tooltip:** Patience pays. FPx that grows with each unused roster swap.
- **Card back:** `{perSwapXMult} FPx per unused roster swap`
- **Breakdown equations:**
    - `no unused swaps`
    - `1 + ({perSwap}x × {unusedSwaps} unused swaps)`

### Touchdown Jackpot

- **Tagline:** *Weekly TD lottery*
- **Hover tooltip:** Fresh lottery every week. Floobits stacking per roster TD, resets weekly.
- **Card back:** `{baseReward} Floobits on 1st TD, +{growthPerTick} more per TD after. Resets weekly`
- **Breakdown equations:**
    - `{baseReward} base + ({growthPerTick}/TD × {ticks} TDs)`
    - `{baseReward} base`
    - `{baseReward} base + ({growthPerTick}/streak × {growthTicks} [{max(0, streakCount - 1)} wk + {peerBonus} synergy])`
    - `{baseReward} base + ({growthPerTick}/streak × {max(0, streakCount - 1)})`

### Traverse

- **Tagline:** *Take the long way*
- **Hover tooltip:** High stakes yardage gamble. FP floor plus a jackpot chance based on yardage by your roster's {posLabel}.
- **Card back:** `+{baseFP} FP floor + {bonusFP} FP jackpot. Jackpot chance starts at {baseChance}%, +{chancePerStep}% per {yardStep} {yardType} yards`
- **Breakdown equations:** _none extracted_

### Underdog

- **Tagline:** *Nothing to lose*
- **Hover tooltip:** The worse they are, the better the odds. Guaranteed FP floor plus a chance at enhanced FP. Odds increase with each loss on your favorite team's record.
- **Card back:** `+{baseFP} FP guaranteed, chance at {enhancedFP} FP. Chance grows the worse your favorite team's rating is, up to 75%`
- **Breakdown equations:**
    - `team not below avg ELO`
    - `1 + ({eloPer100}x × {eloDiff} ELO below avg)`
    - `{baseMult:.2f}x FPx (legacy)`
    - `+{baseFP} FP. Team not below avg ELO`

### Vagabond

- **Tagline:** *A restless spirit*
- **Hover tooltip:** Never settle. FPx that grows with each roster swap you've made this season.
- **Card back:** `+{perSwapXMult} FPx per roster swap used this season`
- **Breakdown equations:**
    - `No swaps used this season`
    - `1.0 + {perSwap}/swap × {swapsUsed} swaps used = {mult}x`

### Walk Off

- **Tagline:** *Buzzer beater*
- **Hover tooltip:** The best kind of finish. Floor FP on a loss, more on a win, and a big bonus for walk-off victories.
- **Card back:** `+{lossFP} FP floor on loss, +{baseFP} FP on favorite-team win, +{rewardValue} FP on walk-off victory`
- **Breakdown equations:**
    - `Waiting for games to complete`
    - `+{rewardValue} FP (walk-off win!)`
    - `+{baseFP} FP (your favorite team won, no walk-off)`
    - `+{lossFP} FP floor (your favorite team lost)`


## Diamond (9)

*Game-changing cornerstones. Rule-benders, hand-composition amplifiers, and strategy enablers.*

### Advantage

- **Tagline:** *Double or nothing (minus the nothing)*
- **Hover tooltip:** Loaded dice. Every chance card in your hand rolls twice, keeping the better result.
- **Card back:** `All chance cards roll twice, keep the better result`
- **Breakdown equations:**
    - `Active · {chanceCount} chance card{`
    - `No chance cards equipped — dormant`

### Alchemy

- **Tagline:** *Lead into gold*
- **Hover tooltip:** Transmutation complete. Each FG by your roster's K counts as a TD for fantasy scoring and other card effects.
- **Card back:** `+{perFgBonusFP} bonus FP per FG by your roster's K. FGs count as TDs for other effects`
- **Breakdown equations:**
    - `Waiting for games`
    - `No FGs made by roster K`
    - `{perFgBonusFP}/FG × {fgsMade} FGs (counted as TDs)`

### Bizarro

- **Tagline:** *Down is up*
- **Hover tooltip:** Bad is good. The lower your lowest-scoring roster player's FP this week, the bigger the FPx on your total.
- **Card back:** `FPx based on lowest roster FP: 0 FP=3x · 1-4 FP=2.5x · 5-9 FP=2x · 10-14 FP=1.5x · 15-19 FP=1.2x`
- **Breakdown equations:**
    - `Waiting for games to complete`
    - `No roster players`
    - `{name} had {lowestFP} FP → no bonus (everyone scored well)`
    - `{name} had {lowestFP} FP → {mult}x FPx`

### Catalyst

- **Tagline:** *Points in, luck out*
- **Hover tooltip:** Compound interest. Roster FP boosts odds on all your chance cards. Also pays Floobits.
- **Card back:** `+1% chance boost per {fpPer1Pct} roster FP above {baseline}. Max +{maxBoostDisplay}%. Also pays {baseFloobits} Floobits`
- **Breakdown equations:**
    - `{rosterFP:.1f} roster FP · +{boost:.1%} chance boost · {baseFloobits}F`

### Heat Check

- **Tagline:** *Staying hot*
- **Hover tooltip:** Are you feeling the heat? FPx that scales with how many of your streak cards have active streaks.
- **Card back:** `{perCardMult} FPx per active streak card in your hand`
- **Breakdown equations:**
    - `1 + ({perCardMult} × {activeStreaks} active streaks) = {bonus}x`
    - `No active streak cards`

### High Roller

- **Tagline:** *Degenerate strategy*
- **Hover tooltip:** Built for the gamble. FPx that scales with how many of your chance cards hit enhanced this week.
- **Card back:** `{perCardMult} FPx per chance card that hits`
- **Breakdown equations:**
    - `1 + ({perCardMult} x {chanceTriggered} chance hit{`
    - `No chance cards hit`

### Lemons

- **Tagline:** *Burn the house down*
- **Hover tooltip:** With the lemons. Multiplies the FP output of your lowest-earning card this week.
- **Card back:** `{rewardValue}x FP on your lowest-earning card this week`
- **Breakdown equations:**
    - `{rewardValue}x FP on your lowest-earning card`
    - `No FP-earning cards to amplify`

### Second String

- **Tagline:** *Backup team*
- **Hover tooltip:** Cover all your bases. FPx when your equipped hand has cards from all 5 positions (QB, RB, WR, TE, K).
- **Card back:** `{rewardValue} FPx when hand has all 5 positions`
- **Breakdown equations:**
    - `{rewardValue} (all 5 positions in hand)`
    - `{len(positions)}/5 positions ({missing} missing)`

### Stacked Deck

- **Tagline:** *Let's get exponential*
- **Hover tooltip:** Multiply the multipliers. FPx for each FPx card in your hand.
- **Card back:** `Compounds (1 + {perCardMult})x per other FPx card in your hand`
- **Breakdown equations:**
    - `(1 + {perCard})^{otherMults} other FPx cards = {mult:.2f}x`
