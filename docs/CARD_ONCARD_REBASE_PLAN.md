# Card Effects — On-Card Player Re-base

**Branch:** `feature/fantasy-cards-fusion`
**Status:** Stage 1 in progress
**Owner decision (2026-07-22):** "We need to look at every effect and see what still
makes sense. It's a big rework but necessary. In the interim we can just work on the
current position-specific cards, then move to the roster-aggregate cards and think
about what to do with them."

## Goal

Under fusion each equipped card **is** a rostered player, so there's a natural 1:1
card → player link. Today effects don't use it: they read either the **roster
aggregate** (`rosterTotalTds`, `rosterPlayerRatings`, …) or the roster player **at the
card's position** (`_getRosterStatsAtPosition(ctx, ctx.cardPosition)`). Re-base them
onto the player actually depicted on the card.

## Why this blocks the Phase 9 tuning

Magnitude tuning to the ~100% parity target (owner, 2026-07-22 — card bonus ≈ the
lineup's own player FP) must happen **after** the re-base: re-basing changes every
number. Measured baseline on the current model, full 6-card lineups converted from
real season-13 rosters:

| lineup edition | n | player FP | card bonus | FPx | bonus as % of player FP |
|---|---|---|---|---|---|
| base | 16 | 100.6 | 123.4 | 1.21 | 123% |
| holographic | 16 | 100.6 | 180.3 | 1.26 | 179% |
| prismatic | 8 | 106.7 | 232.9 | 1.15 | 218% |
| diamond | — | — | — | — | no full lineup possible (45 templates / 144 players) |

Parity target = **100%**, on the AVERAGE lineup. Higher editions reach it through
ceiling and variance, not a higher mean — per the tier philosophy (base = dependable,
diamond = swingy). Flattening every edition to 100% average would delete the rarity
ladder.

## Effect census (helper-aware, all 126 registered effects)

Counted by static analysis with call-graph propagation — a first pass that only looked
at direct `ctx.field` reads misfiled ~30 effects as "external", because their roster
reads hide inside `_getRosterStatsAtPosition` / `_getRosterPlayersByPosition`.

| bucket | n | disposition |
|---|---|---|
| **1. Position-indirect** | 23 | Mechanical re-base → the card's own player. **Stage 1.** |
| **2. True roster-aggregate** | 62 | Needs a new premise or retirement. **Stage 2**, effect by effect. |
| **3. Card-to-card** (hand composition) | 12 | Orthogonal — the hand is still a hand. Unaffected. |
| **4. External** (team / league / economy / chance) | 29 | Unaffected. |

### The WR double-count (live bug, fixed by Stage 1)

`_getRosterStatsAtPosition(ctx, 3)` **sums WR1 + WR2** (it predates position-locked
slots, where "the roster's WR" was genuinely two players). Under fusion both WR cards
each score off the combined output of both receivers, so every position-specific stat
effect landing on a WR pays roughly double. This is part of the measured inflation
above. Re-basing to the card's own player fixes it as a side effect.

## Stage 1 — position-indirect (23) — DONE

Mechanical: replace the position lookup with the card's own player. These are the
"RB carries / QB completions / receiver yards" family — re-basing IS the position gate,
since a card in the WR1 slot depicts a WR.

- New helper `cardEffects._getCardPlayerStats(ctx, cardPlayerId)` replaces
  `_getRosterStatsAtPosition(ctx, ctx.cardPosition or N)` at all 16 self-referential
  call sites.
- `_getPositionTds` / `_getPositionYards` take an optional `cardPlayerId`
  (position selects WHICH stat counts, the card player selects WHOSE) — used by
  `crescendo` and `traverse`, which derive their position from `ctx.cardPosition`.
- `trebuchet`, `spectacle`, `indemnity` re-based off their `_getRosterPlayersByPosition`
  loops to read the card player directly.
- Display: `_buildPlayerStatLine` reports the card's own player, except for the
  still-roster-scoped `_ROSTER_SCOPED_STAT_LINE = {showoff, double_trouble, sniper}`,
  which keep the old lookup so the stat line matches what they actually score on.

**Deliberately NOT re-based** (premise is genuinely multi-player → Stage 2):
`double_trouble` (tiered "one WR scores" vs "BOTH WRs score" — a mechanical re-base
would delete the effect), `showoff`, `sniper` (reads the roster's K regardless of the
card's own position).

**Regression:** `test_oncard_rebase.py` — two WR cards depicting different receivers
must each score off their own line. Verified to FAIL against the pre-change code
(both cards scored the combined 12 receptions; WR2's trebuchet inherited WR1's 44-yd
catch) and PASS after.

### Measured impact

| lineup edition | before | after |
|---|---|---|
| base | 123% | **116%** |
| holographic | 179% | **169%** |
| prismatic | 218% | 224% (n=8, noise) |

Smaller than the correctness of the fix suggests — only a subset of effects are both
position-specific and landing on a WR. The bulk of the gap to the 100% parity target
lives in the 62 roster-aggregate effects (Stage 2) and in raw magnitudes (Stage 3).

## Stage 2 — true roster-aggregate (62)

Not mechanical; each needs a judgement call. They sort roughly into:

- **Trivial translations that read BETTER on-card** — `touchdown_pinata`, `avalanche`,
  `cornucopia`, `feeding_frenzy` (roster TDs → that player's TDs); `windfall`,
  `reclamation`, `resplendent`, `rising_tide`, `buy_low` (→ that player over/under
  performing their own rating); `honor_roll`, `closer`, `walk_off`, `odometer`
  (→ that player's stats); `showoff`, `entourage`, `scrappy`, `sleeper`, `patient`
  (→ that player's rating).
- **Inherently multi-player — would die** — `stack`, `backfield_buddies`, `synergy`,
  `lead_blocker`, `hometown_hero` (same-team-across-positions).
- **Roster-composition premises — the deckbuilding layer** — `vanguard` (5+ veterans),
  `rookie_hype`, `home_alone`, `loyalty`, `eminence`, `cornerstone`, `dark_horse`.
- **Scale on total roster FP** — `catalyst`, `piggy_bank`, `hedge`, `luminary`.
- **Other** — `trust_fund` (`rosterUnchangedWeeks`).

**Open design tension (settle before starting Stage 2):** the roster-aggregate effects
ARE the deckbuilding layer. A full re-base makes every card self-contained and legible
but removes the reason to think about the lineup as a whole. Options: re-base
everything and accept the loss; keep a deliberate minority as roster-scoped
"composition" effects; or give the dying ones new on-card premises.

Folds in the deferred **Phase 5c** (`full_roster`, `all_in`) — both fire free under
position-locked slots and need new premises, not patches.

## The real problem: cards CARRY weak rosters (measured 2026-07-22)

Owner framing: *"what I want to reduce is the ability for users to equip a full hand of
cards that make the actual roster irrelevant, which is the meta in the current roster +
cards iteration."*

**Controlled experiment** (`scratchpad/probe_controlled.py`): synthesize templates so the
SAME 6 effects are played by a strong lineup and a weak one (20th vs 80th percentile of
actual week-14 performers, players who actually played), 40 random effect sets each.
Only player quality varies, so the confound below is removed.

| edition | strong player FP | weak player FP | strong card bonus | weak card bonus | roster signal retained |
|---|---|---|---|---|---|
| base | 243.0 | 19.0 | 52.7 | 29.8 | **68%** |
| holographic | 243.0 | 19.0 | 114.0 | 71.3 | **46%** |
| prismatic | 243.0 | 19.0 | 126.3 | 90.4 | **44%** |

"Roster signal retained" = scoreRatio / playerRatio. The lineups differ **12.8x** in
their own production; final scores differ only 5.6x at prismatic.

**The smoking gun:** a weak lineup producing 19 FP still collects **90 FP of card bonus**
at prismatic — 4.8x its own player output, and 72% of what the strong lineup's cards pay.
Cards don't merely add to your score, they SUBSTITUTE for having a good roster. And it
scales with edition: base keeps two thirds of the roster signal, holo/prismatic under half.

### Two methodology traps (both hit, both cost a wrong answer)

1. **Projection contexts have no variance.** `buildProjectionContext` feeds per-game
   season AVERAGES, so any factor defined as `weekFP / seasonAvgFP` is identically 1.0
   and the mechanic is invisible. Real week stats must be loaded from `GamePlayerStats`
   + `WeeklyPlayerFP` (mirror `seasonManager`'s week-end build via
   `_dbStatsToCardFormat`). The whole existing harness lineage feeds averages.
2. **Effects are tied to players.** A `CardTemplate` is (player, edition, effect), so
   strong and weak rosters necessarily hold DIFFERENT effects. Any per-effect
   "this one levels the field" reading off real rosters is confounded — it is measuring
   which players happen to hold which effects. Synthesize templates to control it.

### Result: the performance-factor idea does NOT fix this

Tested both shapes against real week stats, applied only to the 63 not-yet-coupled
effects (per the owner's scoping call, to avoid squaring the coupling):

| lineup | roster spread (target) | current | A season-avg | B positional |
|---|---|---|---|---|
| base | 1.61x | 1.68x | 1.62x | 1.65x |
| holographic | 1.61x | 1.16x | 1.25x | 1.29x |
| prismatic | 1.57x | 1.09x | 0.96x | 0.97x |

It barely moves holo, makes prismatic worse, and inflates the aggregate everywhere
(prismatic 183% → 195%). It aims at the wrong target: at prismatic 71% of bonus is
ALREADY production-coupled and the spread is flat regardless.

**Working hypothesis for the real cause** — effects carry a FLAT base component
alongside their production component (e.g. `trebuchet` = "3.0 base + 8 bonus", every
chance card has a `baseFP`/`baseFloobits` floor). The flat floor pays out identically
no matter who's in the slot, and there are 6-7 of them per lineup. That is what a weak
roster is collecting. Levers to test next, in order:
1. Cut or proportionalize the flat floors (`baseFP` / `baseFloobits` / `baseChance`).
2. Scale magnitude down specifically at holographic+, where the signal loss concentrates.
3. Re-shape the factor as a GATE on the whole card rather than a multiplier on part of it.

## The fix: gate the card on its own player (owner design, 2026-07-22)

Owner: *"if a card already keys off the card player's performance, then we don't need to
do anything to it. if the card keys off a different metric or is just a boost like some
diamond cards, then the card player needs to clear a threshold first before the effect
on the card actually goes into effect. some can even scale to the card player's
production."*

- **21 effects** already key off the card player (the Stage 1 re-based set) — leave alone.
- **105 effects** key off something else (roster totals, favourite team, economy, chance)
  or are flat boosts — these get a **gate**: below the bar the card pays NOTHING.

A gate, not a multiplier. The multiplier experiment failed because a 0.25x floor still
paid weak rosters; a gate zeroes them.

Measured on the controlled substrate (same effect set on a strong and a weak lineup,
40 random sets per edition, only player quality varying). *signal* = scoreRatio /
playerRatio; 100% = cards fully preserve roster choice.

| variant | base | holographic | prismatic |
|---|---|---|---|
| none (current) | 49% | 32% | 31% |
| **own avg x0.75 gate** | **88%** | **87%** | **88%** |
| pos avg x0.75 gate | 109% | 145% | 134% |
| pos avg ramp 0->1 | 79% | 71% | 69% |

**Own-average x0.75 is the standout** — ~88% signal, and near-identical across all three
editions, so the fix is not edition-dependent (the problem was). Weak-lineup card bonus
drops from 90.4 to 23.2 at prismatic.

The positional gate OVERSHOOTS (134-145%): it strips weak lineups to ~2 FP of bonus,
which over-punishes and would feel dead in the hand. The ramp is gentler but leaves
too much carry.

### Open questions before building

- **`pos avg x0.75` and `x1.00` returned identical numbers** — with a 12.8x lineup gap
  both thresholds partition the same way, so this substrate cannot distinguish them.
  Needs a mid-strength lineup to separate.
- **Single week (14).** The "weak lineup" is the bottom 20% of performers THAT WEEK,
  which conflates *bad players* with *good players having a bad week*. The two gate
  bases punish different things: own-average punishes a bad week (a consistently poor
  player still clears their own low bar ~half the time), positional punishes bad
  players outright. Re-run across several weeks before committing to a base.
- **Which effects should SCALE rather than gate** (owner: "some can even scale") — a
  ramp reads better for continuous effects (FPx, per-TD payouts) than a cliff.

## Stage 3 — magnitude tuning

Rebuild the harness first (see below), then tune to the parity target.

## Harness state

`simcheck_cards_v3.py` is **non-functional under fusion** and silently reported `0.0`
for every effect. Root cause: `buildProjectionContext` sources the lineup from
`EquippedCard` rows, and the prod DB is pre-fusion (25 equipped rows, none in the
sampled week), so the context returned `None`; a bare `except Exception: return 0.0`
turned that into "every card is worthless". The swallow now reports (`_CALC_FAILED`).

Still needed — a fusion substrate builder. The approach validated by the baseline probe:
convert a real user's `FantasyRosterPlayer` rows into `EquippedCard` rows on a temp DB
copy (the old `FantasyRosterPlayer.slot` vocabulary — QB/RB/WR1/WR2/TE/K — is identical
to fusion's, so it maps 1:1), then run the real context + calculator over them.

Two modelling changes v3 needs for fusion:
- **Marginal = replace-a-standard-card, not add-a-card.** Lineups are fixed-size, so a
  card's value is what it adds over the no-effect `standard` card in the same slot —
  not over an empty slot.
- **Position is forced by slot**, so v3's `distinct`/`same` position schemes are
  obsolete. An effect can only be tested in slots matching its template position.

Use strict edition matching in any lineup builder — season 13 has no `standard`
templates and only 45 diamonds for 144 players, so a cross-edition fallback silently
substitutes and produces meaningless per-edition rows.
