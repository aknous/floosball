# Fantasy / Cards Fusion Plan

**Branch:** `feature/fantasy-cards-fusion` (off `next-season`)
**Status:** Design — not yet built
**Ships:** next-season boundary (season cutover, so no mid-season card migration)

## Goal

Collapse the two parallel structures that both reference sim players — the **fantasy
roster** (`FantasyRoster` → `FantasyRosterPlayer`) and **equipped cards**
(`EquippedCard`) — into a single system. **Your equipped cards ARE your fantasy roster.**
The player depicted by each card is the player you're fielding at that position.

This eliminates the "set a roster AND equip cards" double-management, the **match bonus**,
**roster swaps**, and the **temp_flex** powerup — folding all of it into one
position-locked card lineup.

## The core insight

The **match bonus** (`cardEffectCalculator.py:696`,
`isMatch = cardPlayerId in ctx.rosterPlayerIds`, ×1.5 / ×2.5 overdrive) is the bridge
between the two systems today. When they fuse, the context field the effects read —
`ctx.rosterPlayerIds` — simply becomes **"the players depicted by your equipped cards."**
Almost every roster-trait effect keeps working by repointing that one derivation; only the
match multiplier itself and the swap-based effects genuinely go away.

## Confirmed design decisions (owner, 2026-07-14)

1. **Scoring source:** each equipped card scores its depicted player's **real weekly FP**,
   then the card **effect** stacks on top. Weekly score = Σ(playerFP + effectBonus) across
   equipped cards.
2. **Collection gates lineup + weekly-fluid lineup:** yes to both. You can only field
   players you own a card for; lineups swap freely between game days (not season-locked).
   Starter pack already grants one card per position (`auth.py`) so every user can field a
   legal lineup on day one.
3. **FLEX unlock — both paths:** MVP-classified card equipped (permanent, that season) OR
   Accession powerup (temporary).
4. **AP/CH classification reuse:** DEFERRED (see Open Questions). Leading candidate:
   self-multipliers (elite cards boost their own effect), inheriting the match bonus's
   "reward premium cards" role.
5. **Stockpiler + Vagabond:** both RETIRED (swap-dependent, swaps are gone).

## Slot layout

Position-locked slots. Base = 6 (mirrors the current fantasy roster's 6), + FLEX (7th).

| Slot | Accepts | Unlock |
|------|---------|--------|
| QB / RB / WR1 / WR2 / TE / K | that position only | base |
| **FLEX** | any position | **MVP card equipped** (permanent, season) **OR Accession powerup** (temp) |

- Validation: a card's `template.position` must match the slot (FLEX accepts any).
  Position encoding is **uniformly 1-based** (QB=1…K=5): `CardTemplate.position`, the
  `floosball_player.Position` enum, and the `players.position` DB column all agree.
  (An earlier draft of this line claimed `Player.position` was 0-based — it is not, and
  the stale `database/models.py` comment saying so has been corrected.)
  Reuse `_SLOT_POSITION_MAP` (`main.py:7706`) and
  `_POSITION_CODE_TO_INT` (`cardManager.py:143`).
- Keep the existing **no-duplicate-effect** rule (`main.py:10041`, max 1 card per
  `effectName`) — still sensible with 6–7 cards.

## Scoring model

- Base weekly FP now = Σ of each equipped card's **depicted player's** `WeeklyPlayerFP`.
  (Today this comes from `FantasyRosterPlayer`; repoint to equipped-card players.)
- Card effect bonus stacks on top, unchanged in structure (`WeeklyCardBonus`).
- Season total = Σ weekly scores — leans on the existing weekly-banking machinery
  (`WeeklyPlayerFP` + `WeeklyCardBonus`); no season-long locked-roster snapshot needed.

## Locking / swaps

- **Keep** the equip-lock-while-games-run behavior (`lockAllForWeek` / `unlockWeek`,
  `card_repositories.py:254`). Swap freely between game days, frozen during live games.
- **Delete** the FantasyRoster swap/cost machinery: `ROSTER_SWAP_COST`,
  `ROSTER_SWAP_COST_INCREMENT`, `swaps_available`, `purchased_swaps`, `banked_fp` /
  `banked_week_fp` mid-week preservation. With cards only swappable between games there is
  no mid-game swap to preserve.

## Data model changes

- **Keep** `FantasyRoster` row (per user/season) as the leaderboard anchor + points holder
  (`total_points`, `card_bonus_points`, FLEX-unlock state, `WeeklyCardBonus.roster_id` FK).
- **Retire** `FantasyRosterPlayer` (roster players now derived from `EquippedCard`) and
  `FantasyRosterSwap`.
- `EquippedCard`: give slots position semantics (either fix `slot_number`→position mapping
  1=QB…6=K, 7=FLEX, or add a `slot` string mirroring `FantasyRosterPlayer.slot`). Adjust the
  `uq_equipped_card_slot` constraint accordingly.
- **Loyalty** effect: replace `initial_player_ids` (first-saved fantasy roster) with an
  "initial equipped set this season" snapshot.

## Match bonus removal

- Remove the ×1.5 / ×2.5 match path in `_computeCardPass` (`cardEffectCalculator.py:696–720`)
  — every equipped card's player is trivially "on the roster," so it would be flat inflation.
- Retune base effect values to absorb the lost ×1.5 (tuning pass — see below).
- The **Wildcard** ("force all matched") and **Overdrive** ("×2.5 match") WeeklyModifiers
  (`cardEffectCalculator.py:699–711`) lose meaning → retire or repurpose those two modifier
  variants.

## Powerups affected (`constants.POWERUP_CATALOG`)

| Slug | Display | Fate |
|------|---------|------|
| `temp_card_slot` | Accession | **KEEP** — becomes THE FLEX-slot powerup |
| `temp_flex` | Conscription | **RETIRE** — folded into Accession/FLEX |
| `extra_swap` | Dispensation | **RETIRE** — swaps are gone |
| `modifier_nullifier` / `fortunes_favor` / `income_boost` | Annulment / Patronage / Endowment | unaffected |

## Classifications after fusion

| Classification | Old use | New use |
|----------------|---------|---------|
| **MVP** | unlocks 6th card slot | unlocks **FLEX** (permanent path) |
| **Champion (CH)** | unlocks FLEX fantasy slot (`main.py:7914`) | **FREED** — reuse TBD |
| **All-Pro (AP)** | grants roster swaps at lock (`main.py:8100`) | **FREED** — reuse TBD |
| **Rookie** | ×2 sell value, rookie packs | unchanged |

Themed pack pools (champion/allpro/rookie) filter by prior-season **player IDs**, not the
classification tag (`cardManager.py:198–234`), so packs are unaffected.

## Effect verdict (tuning pass)

**RETIRE (2):** `stockpiler` (`cardEffects.py:2431`, unused swaps), `vagabond`
(`cardEffects.py:4246`, swaps used).

**REPOINT only** (read `rosterPlayerIds`/`weekRawFP`/traits — just source from equipped-card
players; no logic change): `rookie_hype`, `synergy`, `wanderer`, `vanguard`, `cornerstone`,
`eminence`, `homer`, `castaway`, `entourage`, `showoff`, `honor_roll`, `garbage_time`,
`windfall`, `resplendent`, `snake_eyes`, `closer`, `sandbagger`, `quiet_storm`, `odometer`,
`reclamation`, `scrappy`, `babysitter`, `sleeper`, `consolation_prize`, `buy_low`,
`spectacle`, `cornucopia`, `feeding_frenzy`, `touchdown_pinata`, `touchdown_jackpot`,
`piggy_bank`, `hedge`, `catalyst`, `drought`, `complacency`. **`loyalty`** needs the new
initial-equipped-set snapshot.

**RETUNE** (trivially-true or composition-shifted under full position-locked slots):
`full_roster` (all positions ≈ always true), `home_alone` (rarely empty), `bonus_round`
(4+ fire ≈ guaranteed), `diversified`, `anthem`, `gold_rush`, `stacked_deck`, `all_in`,
`chain_reaction`, `copycat`.

**KEEP / MORE INTERESTING** (same-team-across-positions becomes real deckbuilding tension):
`stack`, `backfield_buddies`, `double_trouble`, `lead_blocker`, `hometown_hero`, `synergy`.

**SAFE as-is:** all position-locked stat cards (gunslinger, workhorse, possession, sniper,
etc.), favorite-team effects, chance/streak effects, pick-em effects, `fat_cat` (Floobits
economy persists).

## Frontend implications (floosball-react)

- Merge the Fantasy page + Card-equipping page into one **lineup** view: position-locked
  slots, each showing the card art + the depicted player's live weekly FP + effect bonus.
- Remove roster-swap UI and swap-cost UI.
- Card collection: filter by position when filling a slot.
- FLEX slot shows its unlock source (MVP card vs Accession).

## Build sequencing (proposed)

1. **Data model:** EquippedCard position slots + migration; retire FantasyRosterPlayer/Swap;
   keep FantasyRoster row.
2. **Context:** repoint `ctx.rosterPlayerIds` (+ derived traits, `weekRawFP`) to equipped-card
   players in `cardEffectCalculator` / `seasonManager._processWeekCardEffects`.
3. **Scoring:** base FP from equipped players; getSnapshot/leaderboard source swap.
4. **Match bonus removal** + retire Wildcard/Overdrive modifiers.
5. **Effects:** retire stockpiler/vagabond; loyalty snapshot; retune batch.
6. **FLEX unlock** consolidation (MVP card OR Accession); retire temp_flex + extra_swap.
7. **API:** collapse fantasy-roster endpoints into the equipped-cards endpoints.
8. **Frontend:** unified lineup page.
9. **Tuning pass** + `simcheck` validation.
10. **AP/CH reuse** (once decided).

## Open questions

- **AP/CH reuse** — self-multiplier (elite cards boost own effect) vs cosmetic/pack-only vs
  other. Deferred.
- **Retune magnitude** — how much of the lost ×1.5 match bonus to fold back into base values
  vs. accept a lower baseline and retune holistically against the card-tier targets
  (Base ~7.6 / Holo ~6.6 / Prismatic ~12.3 / Diamond ~9.9 avg).
- **Wildcard/Overdrive modifiers** — retire or repurpose the two match-based WeeklyModifiers.
- **Season-total identity** — confirm weekly-sum season total is the desired leaderboard
  (vs. any season-long continuity bonus).
