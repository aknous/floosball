# Card Gate Assignment — working list

Effects that do NOT already key off the card's own player, and therefore need a
GATE (the card player must clear a stat threshold before the effect fires).
See `docs/CARD_ONCARD_REBASE_PLAN.md` for the design and the calibrated
thresholds.

**21 effects are already card-player-specific and need nothing:** `ace_up_the_sleeve`, `air_raid`, `cha_ching`, `crescendo`, `expedition`, `goal_line_vulture`, `gunslinger`, `indemnity`, `jailbreak`, `luminary`, `mismatch`, `possession`, `safety_blanket`, `slippery`, `spectacle`, `spotlight_moment`, `squire`, `stampede`, `traverse`, `trebuchet`, `workhorse`

**105 effects need a gate**, grouped by what they currently key off.

`scale?` marks effects whose payout is already continuous, where a RAMP may read better than a hard cliff.

## Suggested default treatment per group

The grouping implies the treatment, so only the **gate stat** needs per-effect judgement
in most cases.

| group | n | default treatment |
|---|---|---|
| **A. Roster production** | 42 | **Re-base to the card player** where the premise survives — that makes them card-specific and they need no gate at all (they join the 21). Gate only the ones whose premise is genuinely whole-lineup. |
| **B. Roster traits** | 22 | **Keep roster-scoped, add a gate.** This is the deckbuilding layer worth preserving; the gate stops it paying out behind a dud lineup. |
| **C. Favourite team** | 9 | **Gate.** The purest roster-irrelevant cards — they pay identically no matter who is fielded. Biggest single win. |
| **D. Hand composition** | 9 | **Gate.** `full_roster` and `all_in` still need the Phase 5c premise redesign on top (both still mintable). |
| **E. Economy** | 1 | **Gate.** |
| **F. Flat / chance / external** | 22 | **Gate.** `freebie`, `allowance`, `rng`, `surplus`, `big_deal` are pure flat payouts and are the core of the carry. |

**Two already dead — skip them:** `stockpiler` and `vagabond` are swap-based and swaps are
retired in fusion. Confirmed not in `SHARED_EFFECT_POOL`, so they can no longer be minted;
handlers survive only so existing copies still render. Do not spend gate design on them.

**Group A is the interesting choice.** Re-basing an effect onto the card player removes
the need to gate it, and many read better that way (`avalanche`, `cornucopia`,
`feeding_frenzy` → that player's TDs; `honor_roll`, `closer` → that player's line). But
re-basing costs the whole-lineup premise, which for a few (`garbage_time` "every roster
player with 0 TDs", `hedge` "FP earned by your roster") IS the effect. Decide per effect
in the table above.


## A. Roster PRODUCTION (whole-lineup stats/TDs/FP)  [42]

| effect | edition | what it does | gate stat | keep / scale / retire |
|---|---|---|---|---|
| `alchemy` | diamond | +<perFgBonusFP> bonus FP per FG by your roster's K. FGs also count as roster TDs for oth |  |  |
| `automatic` | prismatic | +<baseReward> FP base, +<growthPerTick> per consecutive week your K makes all FG attempt |  |  |
| `avalanche` | prismatic | Roster TDs pay escalating FP: 1st=<td1>, 2nd=<td2>, 3rd=<td3>, 4th=<td4> then diminishin |  |  |
| `babysitter` | prismatic | +<baseFP> FP guaranteed, chance at <enhancedFP> FP. 20% with 1 underperformer (under <fp |  |  |
| `bandwagon_express` | prismatic | +<baseReward> FP base, +<growthPerTick> per consecutive favorite-team win. |  |  |
| `bonsai` | prismatic | +<baseFP> FP guaranteed. Roster <triggerLabel> scales the chance to grow base by +<growt |  |  |
| `buy_low` | base | <perPlayerFloobits> Floobits per underperforming roster player |  |  |
| `catalyst` | diamond | +1% chance boost per <fpPer1Pct> roster FP above <baseline>. Max +<maxBoostDisplay>%. Al |  |  |
| `closer` | holographic | Q4/OT FP earned by your roster is multiplied by <q4MultFactor>x |  |  |
| `complacency` | prismatic | +<baseReward> FP, +<growthPerTick> per week roster is unchanged. |  |  |
| `consolation_prize` | base | +<baseFloobits>F guaranteed, chance at <enhancedFloobits>F. 20% with 1 underperformer (u |  |  |
| `cornucopia` | prismatic | FPx that grows as your roster scores TDs. |  |  |
| `double_trouble` | holographic | +<singleWrFP> FP when a WR scores, +<rewardValue> bonus FP when both WRs score |  |  |
| `drought` | prismatic | +<baseReward> FP, +<growthPerTick> per consecutive week your roster scored under 35 FP.  |  |  |
| `fairweather_fan` | prismatic | <baseReward> Floobits base, +<growthPerTick> per consecutive favorite-team win. |  |  |
| `feeding_frenzy` | holographic | <perTdFloobits>F per roster TD, +<bonusFloobits>F jackpot at <tdThreshold>+ roster TDs |  |  |
| `garbage_time` | base | +<perPlayerFP> FP for every roster player with 0 TDs |  |  |
| `good_neighbor` | holographic | +<baseFloobits>F base + <perMissFloobits>F per missed FG this week |  |  |
| `hedge` | holographic | Starts with a <floorFP> FP pool. FP earned by your roster is subtracted from the pool. P |  |  |
| `honor_roll` | base | +<perPlayerMult> FPx per roster player with <fpThreshold>+ FP this week. Max +<maxDelta> |  |  |
| `industrious` | base | <perReceptionFloobits> Floobits per reception by your roster's TE in a game |  |  |
| `lead_blocker` | holographic | +<perTdFP> FP per TE TD in a game. Rushing touchdowns by the TE team's RB count as TE TD |  |  |
| `leg_day` | prismatic | +<baseReward> FP base, +<growthPerTick> per consecutive game with a 35+ yd FG by your K. |  |  |
| `momentum` | prismatic | +<baseRewardDelta> FPx base, +<growthPerTick> per consecutive week your roster scores 10 |  |  |
| `nose_picker` | holographic | +<baseReward> FP base. Grows every week you submit manual picks. Growth starts at +<firs |  |  |
| `odometer` | prismatic | Escalating FP at 200, 400, 600, and 800+ total roster yards. Resets weekly |  |  |
| `on_fire` | prismatic | +<baseRewardDelta> FPx base, +<growthPerTick> per consecutive week with a FG made by you |  |  |
| `piggy_bank` | base | <fpPercent>% of roster FP → Floobits |  |  |
| `quiet_storm` | prismatic | +<baseReward> FP, +<growthPerTick> per consecutive week no roster player scored 15 or mo |  |  |
| `range` | holographic | +<perYardFP> FP per yard of FG kicked by your roster's K this week. |  |  |
| `reclamation` | base | +<rewardValue> FP when majority of roster is underperforming |  |  |
| `resplendent` | base | +<perPlayerFP> FP per overperforming roster player |  |  |
| `rising_tide` | holographic | +<perPlayerMult> FPx per overperforming roster player (max +<maxDelta>) |  |  |
| `sandbagger` | prismatic | +<baseReward> FP, +<growthPerTick> per consecutive week any roster slot scored 5 FP or l |  |  |
| `snake_eyes` | diamond | FPx based on lowest roster FP: 0 FP=+0.75 · 1-4 FP=+0.53 · 5-9 FP=+0.35 · 10-14 FP=+0.20 |  |  |
| `sniper` | base | +<perFgFP> FP per 40+ yard FG by your roster's K in a game |  |  |
| `snowball_fight` | prismatic | +<baseReward> FP base, +<growthPerTick> per consecutive week at least one player on your |  |  |
| `three_pointer` | base | +<perFgFP> FP for every FG your roster's K makes |  |  |
| `touchdown_jackpot` | prismatic | <baseReward> Floobits on 1st roster TD, +<growthPerTick> for every subsequent roster TD. |  |  |
| `touchdown_pinata` | base | +<perTdFP> FP for every TD your roster scores |  |  |
| `walk_off` | holographic | +<perScoreFP> FP per Q4 or OT TD or FG by a roster player, +<floobitsOnTrigger>F if your |  |  |
| `windfall` | base | +<perPlayerFloobits>F per overperforming roster player |  |  |

## B. Roster TRAITS (ratings, teams, composition)  [22]

| effect | edition | what it does | gate stat | keep / scale / retire |
|---|---|---|---|---|
| `backfield_buddies` | holographic | +<rewardValue> FPx when your roster's QB and RB share a team |  |  |
| `castaway` | holographic | +<rewardFP> FP when at least one roster player is on a sub-.500 team |  |  |
| `comeback_kid` | holographic | +<perPlayerFP> FP per roster player whose team missed playoffs last season, +<floobitsOn |  |  |
| `cornerstone` | prismatic | +<perPlayerMult> FPx per roster player ranked #1 at their position. Max +<maxDelta> FPx. |  |  |
| `dark_horse` | prismatic | +<perStarMult> FPx per star under 5 of your rostered <posLabel> |  |  |
| `domination` | holographic | +<perPlayerFP> FP per roster player whose team is top-6 in their league, +<floobitsOnTri |  |  |
| `eminence` | holographic | +<perPlayerMult> FPx per roster player ranked top-10 at their position. Max +<maxDelta>  |  |  |
| `entourage` | base | +<perPlayerFP> FP for every roster player with <minStars>★+ |  |  |
| `home_alone` | prismatic | +<perSlotMult> FPx per empty roster slot |  |  |
| `homer` | base | +<perPlayerMult> FPx per roster player on your favorite team. Max +<maxDelta> FPx. |  |  |
| `hometown_hero` | holographic | +<rewardFloobits> Floobits when 3+ roster players share a team |  |  |
| `loyalty` | holographic | +<perPlayerFP> FP per player still equipped from your first lineup this season. |  |  |
| `patient` | holographic | +<baseFP> FP per week a sub-3-star roster slot stays unchanged |  |  |
| `rookie_hype` | holographic | +<perRookieFP> FP per rookie on your roster |  |  |
| `scrappy` | prismatic | +<baseFP> FP guaranteed, chance at <enhancedFP> FP. 25% with 1 low-rated player (<maxSta |  |  |
| `showoff` | base | +<perStarFP> FP per 5-star roster player |  |  |
| `sleeper` | prismatic | +<baseFP> FP guaranteed, chance at <enhancedFP> FP. Base 15% chance, +<chancePerLow>% pe |  |  |
| `stack` | holographic | +<rewardDelta> FPx when your roster's QB and WR share a team |  |  |
| `synergy` | holographic | +<perPairMult> FPx per pair of roster players on the same actual team. Max +<maxDelta> F |  |  |
| `trust_fund` | base | <baseFloobits> Floobits base, +<growthPerWeek> per week your roster stays unchanged |  |  |
| `vanguard` | holographic | +<perVetMult> FPx per roster player with 5+ seasons played. Max +<maxDelta> FPx. |  |  |
| `wanderer` | holographic | +<perTeamFP> FP per unique team represented across your roster |  |  |

## C. FAVOURITE TEAM (real-team results)  [9]

| effect | edition | what it does | gate stat | keep / scale / retire |
|---|---|---|---|---|
| `bandwagon` | base | +<rewardDelta> FPx when your favorite team wins |  |  |
| `believe` | base | +<perWinFP> FP per favorite-team season win, +<floobitsOnTrigger>F when they win this we |  |  |
| `highlight_reel` | holographic | <rewardValue> Floobits per your favorite team's big plays |  |  |
| `juggernaut` | prismatic | +<baseXDelta> FPx base, grows with your favorite team's win streak. |  |  |
| `loyalty_bonus` | holographic | +<perStreakFP> FP per win in your favorite team's win streak |  |  |
| `martyr` | prismatic | +<baseFP> FP guaranteed, chance at <enhancedFP> FP. 10% at 1 loss, grows with your favor |  |  |
| `pedigree` | holographic | +<baseFP> FP base, +<rewardValue> FP when your favorite team's ELO ≥ <eloThreshold> |  |  |
| `rock_bottom` | base | +<baseFloobits>F guaranteed, chance at <enhancedFloobits>F. 20% at 1-game losing streak, |  |  |
| `underdog` | prismatic | +<baseFP> FP guaranteed, chance at <enhancedFP> FP. Chance grows the lower your favorite |  |  |

## D. HAND composition (other cards)  [9]

| effect | edition | what it does | gate stat | keep / scale / retire |
|---|---|---|---|---|
| `advantage` | diamond | All chance cards roll <rollCount>x for their bonus, keeping the best result |  |  |
| `all_in` | prismatic | +<baseXDelta> FPx base, plus +<perDuplicateXMult> FPx for each card of your most-equippe |  |  |
| `anthem` | prismatic | +<tier3FP> FP with 3 flat-FP cards equipped, +<tier4FP> with 4, +<tier5FP> with 5 |  |  |
| `diversified` | holographic | +<perTypeFP> FP per unique output type in your hand (FP, FPx, Floobits) |  |  |
| `full_roster` | diamond | +<rewardDelta> FPx when hand has all 5 positions |  |  |
| `gold_rush` | base | <perCardFloobits> Floobits per other Floobits card in your hand |  |  |
| `house_money` | prismatic | +<baseFP> FP base, +<perUpsetFP> per your favorite team's upset wins this season |  |  |
| `last_resort` | prismatic | +<baseFP> FP guaranteed, chance at <enhancedFP> FP. 15% per card that produced no bonus  |  |  |
| `stacked_deck` | diamond | Self-compounds: each other FPx card in your hand stacks +<perCardMult> on this card's ow |  |  |

## E. ECONOMY (Floobit balance)  [1]

| effect | edition | what it does | gate stat | keep / scale / retire |
|---|---|---|---|---|
| `fat_cat` | holographic | +1 FP per <floobitsPerFP> Floobits in your balance (max <maxFP> FP) |  |  |

## F. FLAT / chance / external only  [22]

| effect | edition | what it does | gate stat | keep / scale / retire |
|---|---|---|---|---|
| `allowance` | base | <floobits> Floobits per week |  |  |
| `big_deal` | base | +<xMultDelta> FPx |  |  |
| `bonus_round` | holographic | +<rewardValue> FP when 6 or more of your other cards produced a non-zero bonus this week |  |  |
| `chain_reaction` | prismatic | +<perCardXMult> FPx for every card in your hand that produced a non-zero bonus this week |  |  |
| `charmed` | prismatic | +<perTriggerFP> FP per chance card that triggered this week. |  |  |
| `conductor` | diamond | Boosts each other flat-FP card's output by +<boostPct>% |  |  |
| `copycat` | prismatic | +FP equal to highest flat FP bonus from your other cards |  |  |
| `double_down` | diamond | Multiplies your lowest-earning card's FP by <rewardValue> this week |  |  |
| `doubler` | diamond | Roster TDs count <tdMult>x for every other card's effect this week. |  |  |
| `fortitude` | diamond | +<perCardMult> FPx per active streak card in your hand |  |  |
| `freebie` | base | +<baseFP> FP per week |  |  |
| `gone_streaking` | holographic | +<baseFP> FP base, +<perStreakFP> per game in longest streak (winning or losing) by your |  |  |
| `high_roller` | diamond | +<perCardMult> FPx per chance card that triggered enhanced bonuses this week |  |  |
| `medium` | holographic | +<lowFP> FP at 50%+ Prognostication accuracy, +<midFP> FP at 65%+, +<highFP> FP at 85%+. |  |  |
| `parlay` | holographic | FPx that grows with your weekly Prognostication points. Counts auto-picks |  |  |
| `providence` | holographic | +<baseDelta> FPx + boosts all chance card odds by <chanceBonus> |  |  |
| `rng` | base | Random +<minFP>–<maxFP> FP each week |  |  |
| `sharpshooter` | diamond | Roster FGs count <fgMult>x for every other card's effect this week. |  |  |
| `stockpiler` | prismatic | +<perSwapXMult> FPx per unused roster swap |  |  |
| `surplus` | holographic | +<flatBonus>F added to weekly earnings while equipped |  |  |
| `surveyor` | diamond | Roster yards count <yardMult>x for every other card's effect this week. |  |  |
| `vagabond` | holographic | +<perSwapXMult> FPx per roster swap used this season |  |  |
