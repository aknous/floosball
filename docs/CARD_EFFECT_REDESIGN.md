# Card Effect System Redesign

## Overview

Shift from edition-gated effects to position-based effects. Edition becomes a power scaler + secondary effect provider (Balatro-inspired). Modifiers are removed entirely.

## Core Principles

1. **Position determines effect category** — every card of a given position always gives the same type of reward
2. **Edition scales power** — rarer editions make the primary effect stronger (1.0x–4.0x)
3. **Edition adds secondary effects** — Holo+ editions get a fixed bonus type on top of primary (like Balatro's holographic/polychrome)
4. **Match bonus (1.5x) applies to primary only** — secondary effects are flat and unaffected
5. **Each category has a pool of named variants** — random selection within the pool when a card is generated

## Position → Effect Category

| Position | Category | Description |
|----------|----------|-------------|
| WR | Flat FP | Always awards FP, no conditions |
| QB | Multiplier | Always multiplies FP |
| RB | Floobits | Always earns currency |
| TE | Conditional | If/when gate — can award FP, mult, or floobits |
| K | Streak | Grows over time, resets on broken condition |

## Edition Power Scaling

| Edition | Power Scale | Secondary Effect |
|---------|------------|-----------------|
| Base | 1.0x | — |
| Chrome | 1.5x | — |
| Holographic | 2.0x | +flat FP bonus |
| Gold | 2.5x | +floobits bonus |
| Prismatic | 3.0x | ×mult on total card bonus |
| Diamond | 4.0x | +flat FP, ×mult, and +floobits |

Secondary effects are static per edition — they do not scale with player rating.

## Match Bonus

- 1.5x multiplier when the card player is on your fantasy roster
- Applies to primary effect only
- Secondary effects are unaffected by match bonus

## Named Effects — Full Pool (53 effects)

### Flat FP — WR Cards (11 effects)

| Name | Description |
|------|-------------|
| Freebie | +FP every week, no strings attached |
| Entourage | +FP for each 3★+ player on your roster |
| Touchdown Piñata | +FP for each TD your roster scores |
| Scrappy | +FP for each 2★ or lower player on your roster |
| Honor Roll | +FP for each roster player scoring over X FP |
| Three Pointer | +FP for every FG your kicker makes |
| Garbage Time | +FP for each roster player who scores 0 TDs |
| Loyalty Bonus | +FP that scales with your favorite team's current winning streak |
| Diamond in the Rough | +FP for each roster player who is overperforming their rating |
| Ride or Die | +FP that grows each consecutive week your roster stays unchanged |
| Top Dog | +FP that scales with your favorite team's ELO |

### Multiplier — QB Cards (10 effects)

| Name | Description |
|------|-------------|
| Big Deal | ×mult on total roster FP |
| Trigger Happy | ×mult for each TD your roster scores |
| Main Character | ×mult scaling with card player's weekly FP |
| Hype Man | ×mult on your highest-scoring roster player's FP |
| Babysitter | ×mult for each roster player scoring under X FP |
| Tank Commander | ×mult that scales with how many games your favorite team has lost this season |
| Juggernaut | ×mult that scales with your favorite team's current winning streak |
| Hot Roster | ×mult for each roster player who is overperforming their rating |
| Loyalty Program | ×mult that grows each consecutive week your roster stays unchanged |
| Underdog | ×mult that scales inversely with your favorite team's ELO (worse team = bigger mult) |

### Floobits — RB Cards (9 effects)

| Name | Description |
|------|-------------|
| Allowance | Floobits every week, just for showing up |
| Cha-Ching | Floobits for each TD by the card player |
| Piggy Bank | Floobits based on your roster's total FP |
| Insurance | Floobits for every missed FG by your kicker |
| Consolation Prize | Floobits for each roster player who scores under X FP |
| Rock Bottom | Floobits that scale with your favorite team's current losing streak |
| Buy Low | Floobits for each roster player who is underperforming their rating |
| Trust Fund | Floobits that grow each consecutive week your roster stays unchanged |
| Rags to Riches | Floobits that scale inversely with your favorite team's ELO |

### Conditional — TE Cards (13 effects)

| Name | Description |
|------|-------------|
| Ace Up the Sleeve | +FP if card player hits a stat threshold |
| Showoff | +FP when card player is overperforming their rating |
| Glow Up | ×mult when card player is overperforming their rating |
| Bandwagon | ×mult if your favorite team wins |
| Upset Special | ×mult if your favorite team beats a higher-ELO opponent |
| Believe | +FP if your favorite team is currently in a playoff spot (top 6) |
| Feeding Frenzy | Floobits if your roster scores X+ TDs |
| Spotlight Moment | +FP if the card player scores a TD |
| Highlight Reel | Floobits when your favorite team has a big play (10%+ WPA swing) |
| Schadenfreude | +FP if the card player's team loses |
| Due | ×mult if your favorite team snaps a 3+ game losing streak |
| Fixer Upper | +FP if the majority of your roster is underperforming |
| Pedigree | ×mult if your favorite team's ELO is above X |

### Streak — K Cards (10 effects)

| Name | Description |
|------|-------------|
| Couch Potato | +FP that grows each week this card stays equipped |
| On Fire | ×mult that grows each week the card player makes a FG |
| Gravy Train | Floobits that grow each week the card player's team wins |
| Snowball Fight | +FP that grows each week your roster scores a TD |
| Fairweather Fan | Floobits that grow each week your favorite team wins |
| Bandwagon Express | +FP that grows each consecutive week your favorite team wins (more powerful than Fairweather) |
| Touchdown Jackpot | Floobits that grow for each TD your roster scores (resets weekly) |
| Odometer | +FP that grows for every X yards gained by roster players (resets weekly) |
| Leg Day | +FP that grows each week the card player makes a 45+ yard FG |
| Automatic | ×mult that grows each consecutive week the card player doesn't miss a FG |

## Example Cards

**Base WR Justin Jefferson — Freebie**
- Primary: +3 FP per week (1.0x)
- Secondary: none
- Total: +3 FP

**Holographic WR Justin Jefferson — Freebie**
- Primary: +6 FP per week (2.0x)
- Secondary: +2 FP (holo bonus)
- Total: +8 FP

**Holographic WR Justin Jefferson — Freebie (matched)**
- Primary: +6 FP × 1.5 match = +9 FP
- Secondary: +2 FP (unaffected by match)
- Total: +11 FP

**Prismatic QB Patrick Mahomes — Trigger Happy**
- Primary: ×mult per roster TD at 3.0x power
- Secondary: ×1.05 mult on total card bonus

**Diamond RB Derrick Henry — Allowance**
- Primary: Floobits every week at 4.0x power
- Secondary: +3 FP, ×1.05 mult, +5 floobits

## Systems Removed

- All modifier effects (amplifier, double_match, easy_threshold, base_amplifier, floobits_amplifier)
- Per-edition effect pools (effects no longer gated by edition)
- Random effect type selection within edition (now deterministic by position)

## Systems Preserved

- Match bonus (1.5x on primary when card player is on roster)
- Position-specific conditionals (300+ pass yards, etc.)
- Pack system, shop, sell values
- Player rating scaling within each effect
- Card template generation per (player, edition) pair

## Data Requirements

Effects that need specific data at calculation time:
- **Player stats**: TDs, yards, FGs, FG misses, fantasy points (already tracked)
- **Team ELO**: `team.elo` (already tracked)
- **Team win/loss streaks**: already tracked
- **Playoff standings**: top 6 per league check (already available via league standings)
- **Season performance rating**: `player.seasonPerformanceRating` (already tracked)
- **WPA big plays**: win probability delta per play (WP calculated per play, need to compute deltas at week end)
- **Roster change tracking**: need to track whether roster was unchanged week-over-week (new)
