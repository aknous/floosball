# Card Effects — On-Card Player Re-base

**Branch:** `feature/fantasy-cards-fusion`
**Status:** Stage 1 DONE · gate design validated · Stage 2 not started

## WHERE WE ARE (paused 2026-07-22)

Committed on `feature/fantasy-cards-fusion`, pushed through `081cb86`; the five
commits below are local-only unless pushed since:

| commit | what |
|---|---|
| `023c0ef` | Stage 1 — 23 position-specific effects re-based onto the card player (code) |
| `cebbcc2` | measured how much cards carry weak rosters |
| `8135e08` | gate design measured |
| `511a333` | corrected results + position-encoding fix |
| `e1c3cb8` | `docs/CARD_GATE_ASSIGNMENT.md`, the 105-effect worklist |

**Settled:**
- Effects trigger off the card's own player. 21 already do; 105 need a **gate** — the
  card player must clear a stat threshold before the effect fires (a gate, NOT a
  multiplier; the multiplier's 0.25x floor still paid weak rosters and failed).
- Gate base: **card player's week FP >= 0.75 x their own season average**. Takes roster
  signal from 64/33/33% (base/holo/prismatic) to 121/102/113%. Passes 58% of all
  player-weeks. The `0.75` is the dial for the overshoot.
- The gate STAT should VARY per card (FP, yards, completions, YAC) for diversity,
  authored as percentiles calibrated to that same 58% pass rate so the stat is flavour
  not power. Calibration table below.
- Roster-aggregate effects are KEPT (they're the deckbuilding layer) — they get gates,
  not deletion.

**NEXT UP — pick one:**
1. **Group A re-base-or-gate calls** (42 effects). Re-basing onto the card player removes
   the need for a gate; but `garbage_time` and `hedge` lose their premise if re-based.
2. **Assign gate stats to groups C + F** (31 effects) — the purest carry, easiest calls,
   biggest win.
Then: build the gate mechanism itself (constants + calculator hook + card text), then
Stage 3 magnitude tuning.

**Still open:** whether gate stats are hand-authored per effect (reads better) or
generated from a position->stat table (stays calibrated automatically); and Phase 5c
(`full_roster`, `all_in` — both still mintable, both need new premises on top of a gate).

**Harness (now in the repo):**
- `simcheck_cards_fusion.py` — the confound-free instrument. Synthesizes templates so the
  SAME effect set is played by a strong and a weak lineup; only player quality varies.
- `simcheck_gate_variants.py` — compares gate variants. Derives the already-on-card
  effect set from source, so it stays correct as more effects are re-based.
- `simcheck_gate_calibration.py` — per-stat gate thresholds at a target pass rate.

Run as `PROBE_EDITION=prismatic PROBE_TRIALS=40 PYTHONPATH=. .venv/bin/python <script>`.
`simcheck_cards_v3.py` is superseded — it is non-functional under fusion.
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
playerRatio; 100% = cards exactly preserve roster choice, below = cards carry weak
rosters, above = cards amplify roster choice.

| variant | base | holographic | prismatic |
|---|---|---|---|
| none (current) | 64% | 33% | 33% |
| **own avg x0.75 gate** | **121%** | **102%** | **113%** |
| pos avg x0.75 gate | 148% | 192% | 190% |
| pos avg ramp 0->1 | 106% | 77% | 79% |

**Own-average x0.75 is the pick.** It takes holographic and prismatic from 33% to
102-113%, and weak-lineup card bonus at prismatic falls from 143.6 to 32.8. It lands
slightly ABOVE parity, i.e. cards now mildly amplify roster choice instead of erasing
it, which is the right side of 100% to sit on. The `0.75` ratio is the dial to trim the
overshoot (lower ratio = more cards fire = closer to 100%).

The positional gate overshoots wildly (148-192%), stripping a weak lineup to ~2 FP of
bonus across six cards. That reads as dead, not challenging.

**Multi-week validation:** across EVERY player-week of the season (not just week 14),
`weekFP >= 0.75 x own season average` passes **58%** of the time. So the gate is
genuinely selective rather than a rubber stamp, and it holds up beyond the single week
the lineup experiment samples.

### DECISION — edition-scaled STATIC bars (owner, 2026-07-22, session 2)

Owner chose simplicity over the self-relative gate: a STATIC stat threshold per card,
"low enough the player clears it most weeks, high enough a bad game gates it", with the
bar EASIER for lower rarities (base clears almost always) and HARDER for higher ones.

This drops the self-relative machinery AND the cold-start blend below — a static number
works from week 1, no per-player averages needed. The thresholds are league percentiles
per position per edition, computed from the season distribution (stable season to
season; can be frozen from the prior season).

Measured (bars: base 85% / holo 72% / prismatic 60% / diamond 50% league pass rate):

FUN — pass rate = how often the card fires, by the CARD PLAYER's quality:
| edition | on a STRONG player | MID | WEAK |
|---|---|---|---|
| base | 97% | 90% | 70% |
| holographic | 92% | 79% | 50% |
| prismatic | 85% | 66% | 37% |
| diamond | 79% | 53% | 28% |
A diamond on a star still fires 79% (reliable, not punishing); on a scrub 28% (the
intended punishment for bad deployment). Base is dependable everywhere.

BALANCE — signal (100% = cards track roster): base 91% (good), holo/prismatic overshoot
to ~195%/182% AGAINST THE EXTREME weak lineup (single-week bottom-20%, ~0 output). Against
a normal weak-AVERAGE player those cards fire 37-50%, so the real overshoot is milder.
Overshoot = "powerful cards strongly reward good rosters", arguably intended for the
rarest cards. The exact per-edition bar is a DIAL; Stage 3 magnitude tuning is a second
lever. Not chasing exactly 100%.

**Superseded:** the self-relative gate and the cold-start blend (both below) are NOT the
chosen model — kept as the record of why the simpler static bar is acceptable (it improves
on 35% massively and the overshoot is tunable). The per-stat percentile calibration IS
reused, now per EDITION.

Probes: `scratchpad/probe_statgate.py`, `probe_edition_bar.py` (session-local).

### COLD START — the early-season average (measured 2026-07-22, session 2)

The self-relative gate divides by the player's own season average, which is undefined
in week 1 and noisy on 1-2 games. Measured pass rate by week (target ~58%):

| week | current-only | prior-only | blend |
|---|---|---|---|
| 1 | 100% | 70% | 70% |
| 2 | 65% | 65% | 66% |
| 3 | 64% | 70% | 66% |
| 4-7 | 55-65% | 58-70% | 62-65% |

Current-season-ONLY fails open in week 1 (no average → the gate does nothing) and is
noisy for a few weeks after. **Use a shrinkage blend**: the player's PRIOR-season
average as a prior, pulled toward the current-season average as games accumulate
(`w = gamesSoFar / (gamesSoFar + K)`, K≈3). Week 1 leans entirely on last season, so no
dead week and no swing — the first eight weeks stay in a tight 62-66% band.
`PlayerSeasonStats` is season-keyed, so the prior is already available.

Edges:
- **Rookies have no prior season** → fail-open in week 1 (their card fires their first
  game), then build their own average within a game or two. Optionally seed from a
  rating/positional baseline instead. Minor.
- The blend runs slightly HOT (62-66% vs 58%), so the 0.75 ratio tightens a touch at
  tuning time — a calibration note, not a cold-start issue.

Probe: `scratchpad/probe_coldstart.py` (session-local).

### GATE MODEL CORRECTED (measured 2026-07-22, session 2)

The earlier calibration below assumed a FIXED LEAGUE THRESHOLD per stat (e.g. "74+ rec
yards"). Measured on the controlled substrate, that OVERSHOOTS badly — 149% / 195% /
182% signal (base/holo/prismatic), stripping weak lineups to ~1-13 FP of bonus. A fixed
league bar cleared 58% of the time league-wide is cleared FAR less than 58% by a
consistently-weak player, so weak lineups almost never fire. Same failure as the
positional-average gate.

**The gate must be SELF-RELATIVE**: the card player's week stat vs THAT PLAYER'S OWN
season average of that stat (>= 0.75x), NOT a league threshold. Measured signal
118% / 103% / 113% — matches the own-average-FP gate and keeps balance, because even a
weak player clears their own average ~half the time.

This keeps BOTH goals:
- the gate STAT still varies per card (rush yards / receptions / YAC / completions / FP)
  → diversity, the owner's vision;
- self-relative normalisation → ~100-115% roster signal → balance.

Card text becomes "activates on a strong rushing game" / "when they beat their receiving
average", NOT a fixed number. So the per-stat percentile calibration table below is the
WRONG model and is retained only as a record of what was tried. The live data needed is
each player's per-stat SEASON AVERAGE (like eminence's playerSeasonFPPerGame, but
per-stat), computed live at calc time — thresholds are never frozen at mint.

Probe: `scratchpad/probe_statgate.py` (session-local).

### Varying the gate STAT (owner, 2026-07-22)

*"the stat that gates the effect should vary, like one card it could be FP production,
others could be total yards, or completions, or YAC. this instantly diversifies the
available cards."*

Hazard: uneven difficulty makes two cards unequal for reasons unrelated to their
effect. Fix — author gates as PERCENTILES of the real stat distribution, calibrated to
the same 58% pass rate. The stat becomes flavour, not power. Season-13 values:

| position | gate stat @ 58-60% pass |
|---|---|
| QB | 217 pass yards · 28 completions · 43 attempts · 1 pass TD |
| RB | 77 rush yards · 21 carries · 19 longest run |
| WR | 74 rec yards · 9 receptions · 23 YAC · 10 targets · 18 longest catch |
| TE | 45 rec yards · 7 receptions · 15 YAC |
| K | 2 FGs made · 55 FG yards · 41 longest FG |

**TD-count and 20+-play stats cannot be calibrated to 58%** — the distribution is too
coarse (median 0, so any "1+" bar sits well under the target rate). They make good
HIGH-difficulty gates for big-ceiling effects, not standard ones. Thresholds are
season-relative and want recomputing per season, like the eminence data.

### Harness bug found (cost one wrong answer)

`players.position` is **1-BASED** (QB=1..K=5), matching `floosball_player.Position` and
`CardTemplate.position`. The `database/models.py` comment claimed 0-based and
`FANTASY_CARDS_FUSION_PLAN.md` repeated it; both are now corrected.
`FANTASY_FUSION_PROGRESS.md` had it right all along ("uniformly 1-based"). The probes
trusted the stale comment and added 1, so every player landed in the wrong slot. The
pre-fix numbers (49/32/31% current, 88% gated) are superseded by the table above.

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
