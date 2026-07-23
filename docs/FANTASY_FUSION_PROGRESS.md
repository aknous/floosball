# Fantasy / Cards Fusion — Build Progress & Handoff

> **Read this first**, then `docs/FANTASY_CARDS_FUSION_PLAN.md` (the design) and the task
> list. This note is the source of truth for *where the build is* and *what's next*.
> Update it as phases land.

**Branch:** `feature/fantasy-cards-fusion` (off `next-season`). Clean tree, pushed.
**Goal:** equipped cards ARE the fantasy roster — one position-locked card lineup, no
separate roster / match bonus / swaps / temp_flex.

## Settled decisions (don't re-litigate)
- **Slot model:** `EquippedCard.slot` STRING (`QB/RB/WR1/WR2/TE/K/FLEX`) — chosen over
  repurposing `slot_number` (kept as a display ordinal). Unique index
  `(user,season,week,slot)`; pre-fusion rows keep `slot=NULL` (SQLite NULLs distinct).
- **Base slots = 6** (one per position) **+ FLEX 7th** (was 5+MVP/powerup). FLEX unlock:
  MVP-classified card equipped (permanent) OR Accession (`temp_card_slot`) powerup.
- **Scoring = weekly-sum, no season lock snapshot.** Season total = Σ over weeks of that
  week's equipped lineup's per-player `WeeklyPlayerFP` + that week's `WeeklyCardBonus`.
  Reconstruct past lineups from the persisted per-week `EquippedCard` rows. NO
  `points_at_lock` / lock-offset (a week's FP is all post-lock — cards lock at game start).
- **No swaps.** `FantasyRosterSwap` / `banked_fp` / "Previous Players" retired.
- **Match bonus (×1.5/×2.5) is removed** in Phase 4 (every equipped card's player is
  trivially "on the roster" → flat inflation). Retire Wildcard/Overdrive modifiers.
- **NEW RULE — no duplicate PLAYER across slots.** Two different cards can depict the same
  player; equipping both would field that player twice. Reject at equip time (alongside the
  existing no-dup-card-id + no-dup-effect checks). Belongs to Phase 6. (On task #12.)
- **Powerups:** KEEP `temp_card_slot` (Accession) as THE FLEX powerup; RETIRE `temp_flex`
  (Conscription) + `extra_swap` (Dispensation).
- **Keep** the `FantasyRoster` row (leaderboard anchor + `WeeklyCardBonus.roster_id` FK) and
  the equip-lock-while-games-run behavior.

## Key facts / anchors
- Position encoding is uniformly **1-based** at the domain layer: `CardTemplate.position`,
  the `Position` enum, `_SLOT_POSITION_MAP` (`api/main.py:~7741`), `_POSITION_CODE_TO_INT`
  (`cardManager.py:144`) all agree. Validate a card into a slot via
  `cardManager.cardFitsSlot(template.position, slot)`.
- Fusion slot helpers added in `cardManager.py`: `FUSION_BASE_SLOTS`, `FLEX_SLOT`,
  `FUSION_ALL_SLOTS`, `SLOT_TO_POSITION`, `SLOT_TO_ORDINAL`, `cardFitsSlot()`.
- New helper `FantasyTracker._equippedRostersByWeek(session, season)` →
  `{(user_id, week): [(EquippedCard, depicted_player_id), ...]}` (all weeks).
- Migration pattern: idempotent `ALTER TABLE ... ADD COLUMN` in
  `database/connection.py::_runPendingMigrations()`. SQLite can't ADD a UNIQUE column via
  ALTER → create the unique index separately (already done for the slot index).

## Phase status
| Phase | Status | Commit |
|---|---|---|
| 1. EquippedCard slot model + migration | ✅ DONE | `269c804` |
| 2+3. Scoring/context from equipped (weekly-sum) — **getSnapshot** | ✅ DONE (math-validated) | `5a56c80` |
| 2+3. Remaining repoint sites | ✅ DONE (math-validated) | `0b8ffbe` |
| 4. Remove match bonus + Wildcard/Overdrive | ✅ DONE (unit-validated) | `1061150` |
| 5a. Effects: retire stockpiler/vagabond + loyalty snapshot | ✅ DONE (unit-validated) | `850ddda` |
| 5b. Effects: bonus_round threshold 4→6 | ✅ DONE (unit-validated) | `ea0f154` |
| 5c. OVERHAUL full_roster + all_in (design TBD) | ⬜ TODO (deferred) | — |
| 6. FLEX unlock + slot wiring + retire temp_flex/extra_swap + no-dup-player | ✅ DONE (unit-validated) | `a12e906` |
| 7a. Equip endpoint owns the FantasyRoster row + drop All-Pro swap machinery | ✅ DONE | `2721c12` |
| 7b-i. Delete old fantasy-roster endpoints + migrate achievements | ✅ DONE | `4973eb3` |
| 7b-ii. Backend swap-web teardown + FantasyRosterPlayer reader repoints | ✅ DONE (sim-validated) | (this commit) |
| 7b-iii. Frontend-facing leaderboard/history repoints + residual no-ops | ⬜ → Phase 8 | — |
| 8. Frontend: TradingCard redesign + sub-base tier + unified lineup page | ✅ DONE (tsc-clean; live QA pending) | FE `0e8a7d2`/`15d232a`, BE `e612e8c` |
| 8b. Frontend 7b-iii (leaderboard/history) + retire shop swap UI | ⬜ | — |
| 9. Tuning pass + `simcheck` — incl. **card power rebalance for full lineups** | ⬜ blocked on the on-card re-base | — |
| R1. On-card re-base Stage 1 — position-specific effects (21) | ✅ DONE | `023c0ef` |
| R2. On-card re-base Stage 2 — 9 roster aggregates | ✅ DONE | `232d439` |
| G1. Card gate — FP POWER BAR (replaced the varied-stat ramp) | ✅ DONE, validated end-to-end | `d1fb64c` |
| G2. Descriptions say "this player" + show the gate | ✅ DONE | `d1d56ae` |
| G3. Position-stat guardrail test | ✅ DONE | `792d4fc` |

## CARD DESIGN — where it stands + backlog (2026-07-23)

**The gate is the FP power bar** (docs/CARD_ONCARD_REBASE_PLAN.md, redesign note at top):
every effect-bearing card unlocks once the depicted player fills a position FP threshold
(QB 8 / RB 9 / WR 8 / TE 4 / K 6); inverse/underdog cards run the bar in reverse. Pure
on/off, no scaling, no exempt set. Validated on real full lineups through the two-pass
calc: 0 errors, ~24-35% of cards gate off each week (the roster-irrelevance fix working).
Aggregate baseline for the retune: base 89% / holo 107% / prismatic 143% of the lineup's
own player FP.

**Open card backlog (DECIDED, not built):**
1. **Inverse set 11 → 7.** Move `rock_bottom`, `martyr`, `underdog`, `home_alone` OUT of
   `_INVERSE_GATE_EFFECTS` to normal gates — their payoff is team/slot-based, not tied to
   the player's performance. Keep the 7 that track performance down (snake_eyes, hedge,
   buy_low, reclamation, babysitter, consolation_prize, drought).
2. **Chance cards → "luck bar" (middle option).** The bar aggregates ALL odds sources:
   the player's FP (SMALL base contributor) + the card's unique trigger + innate synergy +
   amplifiers + Patronage. Fuller bar = better odds, CAPPED below 100% (never a lock).
   Chance cards need a HIGHER total fill than reliable cards (their payoff is a jackpot,
   so it must hit less often for fair EV, and stay a gamble). A lone chance card sits at a
   low bar (correctly weak). Keeps every unique trigger relevant.
3. **Chance rarity on-ramp** (docs/CHANCE_SYNERGY_AUDIT.md). Today the archetype is only
   buildable at prismatic (9 prismatic / 3 base / 0 holo chance cards; all 3 base output
   floobits; only 2 amplifiers, both holo/diamond). Seed holo chance cards + an FP-output
   base chance card + an accessible (base/holo) amplifier so a low-rarity chance build is
   possible.
4. **Repurpose the AP / CH classifications.** Under fusion MVP took over the FLEX
   unlock; Champion's old FLEX-slot job and All-Pro's old roster-swap grant both
   evaporated, so those two classifications have NO gameplay effect now (they still get
   stamped, still drive the Champion/All-Pro themed packs, and still boost sell/combine
   value — champion 2.0x / all_pro 1.5x — but do nothing during scoring). Give them an
   in-game purpose. Options, in the power-bar world:
   - **Lower the FP threshold** — a prestige card unlocks its bar at a lower FP ("proven
     players deliver"). Fits the power bar with no new mechanic. Cleanest.
   - **A gate floor** — prestige cards never fully gate off; even a bad game leaves a small
     partial effect (they're never dead).
   - **Self-boost** — the prestige card's effect is a flat % stronger (the plan's original
     "elite cards boost their own effect" candidate). Adds a multiplier layer.
   - **Set bonus** — equipping N prestige cards grants a "dream team" bonus (deckbuilding
     incentive; more complex). NEEDS an owner design call.

5. **Stage 3 — retune card power for the 6-card lineup.** Now that lineups are a full
   6-7 cards (was ~5) and the gate zeros ~30%, recalibrate per-edition magnitudes against
   the parity target using the baseline above. Harnesses in repo: `simcheck_cards_fusion`,
   `simcheck_gate_variants`, `simcheck_gate_calibration`.

**Priority note (owner, 2026-07-23):** with ~11 fantasy players, the real lever for card
engagement is SHIPPING fusion, not deeper roster surgery. Do the finish-line frontend/API
work first; the backlog above is polish for after.
| R2. On-card re-base Stage 2 — roster-aggregate effects (62) | ⬜ NEXT — needs per-effect design | — |

## On-card re-base (owner, 2026-07-22) — Phase 9 now runs AFTER it
Effects should trigger off the player depicted on the card, not the whole roster.
Owner: *"We need to look at every effect and see what still makes sense. It's a big
rework but necessary. In the interim we can just work on the current position-specific
cards, then move to the roster-aggregate cards and think about what to do with them."*
Magnitude tuning waits until the re-base lands — re-basing changes every number.
**Full census, staging, measured baselines: `docs/CARD_ONCARD_REBASE_PLAN.md`.**
Parity target set the same day: card bonus ≈ 100% of the lineup's own player FP, on
the AVERAGE lineup (higher editions get there via ceiling/variance, not a higher mean).

## Phase 9 tuning — MUST rebalance card power for full lineups (owner note, 2026-07-18)
Fusion means **every user fields a full 6–7 card lineup** (cards ARE the roster), so the
aggregate card bonus per user is structurally higher than the old ~5-card hand → **cards
need to be less powerful per-card overall.** The tuning sweep must weigh the competing
forces together, not in isolation:
- **−** the ×1.5/×2.5 match bonus is gone (≈ −33% per card).
- **+** more effect cards can be equipped by default (up to 7 vs ~5), and everyone always
  fields a full slate (no partial hands).
- **0** the sub-base `standard` floor cards contribute nothing (they gate, don't score).
Do a holistic `simcheck`-driven sweep against the card-tier targets (Base ~7.6/ceil 12,
Holo ~6.6/20, Prismatic ~12.3/42, Diamond ~9.9/21) under the full-lineup reality; fold in
the deferred **5c** (`full_roster`/`all_in` redesign) + the composition-shifted retune batch.

## Phase 7b-i (delete write endpoints + migrate achievements) — DONE
- Deleted the five old fantasy-roster endpoints + their 4 request models (`api/main.py`,
  ~758 lines): `GET/PUT /api/fantasy/roster`, `POST /api/fantasy/roster/{lock,remove,swap}`.
  (Shared helper `_getPlayerLiveFantasyPoints` + the `_liveStatsToDbFormat` /
  `_computeLeaderboardData` snapshot helpers were preserved.)
- Migrated the achievement hooks into `setEquippedCards`, computed off the equipped
  lineup's DEPICTED players: `onFantasyRosterSet`, and the composition secrets **Shoestring**
  (all ≤3-star), **Homer** (all fav-team), **Greenhorn** (all rookies), keyed on a full
  lineup (≥6 base slots). **Validated:** parse OK.
- Frontend impact (expected, fixed in Phase 8): `AuthContext.tsx:99` + `FantasyRoster.tsx`
  calls to `/fantasy/roster` now 404. That's the point — the new lineup page uses the
  equipped-cards endpoints.

## Phase 7b-ii (backend swap-web teardown + reader repoints) — DONE (sim-validated)
- **Retired-player fantasy autofill removed:** deleted `_handleRetiredPlayerRosters` +
  its offseason STEP 8 caller (`seasonManager`). A retired player's card just isn't
  re-minted next season; there's no bare-player slot to autofill.
- **Swap-granting removed:** deleted `_grantRosterSwaps` + its weekly call. The three
  card-calc context sites (`fantasyTracker._buildCardCalcContext`,
  `seasonManager._processWeekCardEffects`, `cardProjection`) now pass
  `unusedSwaps=0` / `seasonSwapsUsed=0` / `rosterUnchangedWeeks=<week>` instead of
  querying `FantasyRosterSwap` (zero behavior change — those degraded to the same values
  once swaps stopped). Dropped the orphaned `FantasyRosterSwap` imports.
- **Readers repointed to the equipped lineup:** `GET /api/bot/roster`, the personality/
  quote player-scope builder, the admin-stats top-rostered query (now top-EQUIPPED), and
  the season-end "engaged user" query (now ≥6 distinct equipped slots). Dropped the admin
  swap counters (`totalSwapsUsed`/`totalPurchasedSwaps`).
- **Swap/roster secrets retired** (would misfire in fusion): **Stalwart** ("no swaps" →
  everyone), **Purist** ("full roster, zero cards" → impossible). Auto-grants removed;
  existing holders keep them. (**Arsenal** already died with the swap block in 7a.)
- **Validated:** fresh fast 2-season simcheck — 0 errors/tracebacks, full season →
  playoffs → offseason (all gates, no Step 8) → season 2, rosters full (24/24), scores
  sane, removed code paths silent.
- **Left as residual (dead code, unreachable):** the `extra_swap` shop-buy + reward-grant
  branches (`main.py` — the buy handler rejects any non-`POWERUP_CATALOG` slug first) and
  the FLEX-roster-player sweeps / distinct-roster reads on now-empty `FantasyRosterPlayer`
  (harmless no-ops). These go with the final table-drop cleanup.

## START HERE — Phase 8 (frontend) + Phase 7b-iii (last reader repoints)
> **Full frontend scope: `../floosball-react/FANTASY_FUSION_FRONTEND_PLAN.md`.**

**7b-iii** — finish alongside Phase 8 so the leaderboard numbers are integration-tested:
- **`GET /api/fantasy/leaderboard/weekly`** (`roster.players`) — repoint to the equipped
  lineup, or DELETE if `getSnapshot` supersedes it (check `FantasyLeaderboard.tsx` first).
- **`GET /api/history/user-records`** — raw SQL joins `fantasy_roster_players`; repoint to
  the equipped lineup or accept as legacy/frozen.
- Then the final cleanup: drop the residual dead `extra_swap` branches + FLEX-sweep no-ops,
  and (once nothing references them) the `fantasy_roster_players` / `fantasy_roster_swaps`
  tables. Keep the `FantasyRoster` row + `WeeklyCardBonus.roster_id` FK.

Also still OPEN: **Phase 5c** (redesign `full_roster` + `all_in`) and **AP/CH reuse**.

## Sub-base "no-effect" card tier — DONE (backend, sim-validated)
New floor edition `standard` (below base): a NO-EFFECT print that just fields the player
for their FP. Everyone can always ice a legal lineup; effect cards become the upgrade.
- `cardEffects.buildEffectConfig('standard', …)` returns a no-effect config
  (`effectName:'none'`, empty primary); `computeEffect` no-ops silently on `none`/blank
  (no "unknown effect" warning); it scores 0 bonus.
- `cardManager`: `EDITION_THRESHOLDS['standard']=0` (one per player, like base),
  `EDITION_BASE_WEIGHTS['standard']=0`, `EDITION_SELL_VALUES['standard']=2`; the openPack
  pool excludes `edition=='standard'` so it's never a pack drop.
- `auth._provisionStarterPack` grants one `standard` card per position (the floor lineup),
  base fallback if no standard templates exist yet.
- Equip endpoint no-dup-effect rule exempts `none`/blank so a lineup can field several
  standard cards.
- Frontend `TradingCard` renders the `standard` edition (matte, no foil, "No Effect"
  rarity, blank effect footer) — already committed on the frontend branch.
- **Validated:** fresh fast boot generated 144 standard templates (one per player), all
  `effectName:'none'`, no errors/warnings; unit test confirms a standard card scores 0.
- **Open (deferred):** can standard upgrade/blend INTO an effect card, or stay effect-less
  forever? Left as a permanent floor for now (blends never produce `standard`).

Phase 7a made the equip endpoint self-sufficient (it owns the FantasyRoster row now).
Phase 7b (delete the old fantasy-roster API + the swap web) is intentionally folded into
Phase 8 so the endpoint removal and the new frontend land together and can be
integration-tested. Concretely, to retire in 7b/8 (all `api/main.py` unless noted):
- **Endpoints to delete** (replaced by the equipped-cards endpoints): `GET/PUT
  /api/fantasy/roster` (7762/7932), `POST /api/fantasy/roster/{lock,remove,swap}`
  (8082/8180/8276). Migrate their still-wanted achievement hooks to the equip endpoint:
  `onFantasyRosterSet` + the composition secrets **Shoestring** (all ≤3-star), **Homer**
  (all fav-team), **Greenhorn** (all rookies) — recompute off the equipped lineup's
  depicted players. (**Arsenal**, a 3+-swaps secret, dies with swaps — already unreachable.)
- **Swap web to remove:** `_grantRosterSwaps` (seasonManager, called ~:1399), the
  `swaps_available`/`purchased_swaps` reads/writes, the `extra_swap` shop-buy (11268) +
  reward-grant (14469) branches, admin-stats swap counters (5820), and the CardCalcContext
  `unusedSwaps` field (only fed the retired stockpiler).
- **Repoint reads:** `GET /api/bot/roster` (14181) and the admin-stats top-rostered query
  (5831) still read `FantasyRosterPlayer` — repoint to the equipped lineup or drop.
- Keep the `FantasyRoster` row (leaderboard anchor + `WeeklyCardBonus.roster_id` FK) — only
  its `players`/`swaps` children retire. Don't DROP the tables until nothing references them.

Also still OPEN: **Phase 5c** — full redesign of `full_roster` + `all_in` (owner: "completely
overhaul"). And **AP/CH classification reuse** (plan open question): FLEX is now MVP/Accession
-gated, so Champion no longer unlocks FLEX and All-Pro no longer grants swaps — both FREED.

## Phase 7a (equip endpoint owns the roster lifecycle) — DONE
- **The linchpin:** the only creator of the `FantasyRoster` row was the old fantasy-roster
  PUT, so an equip-only user would never get a leaderboard row. The equip endpoint
  (`setEquippedCards`) now **get-or-creates** the row (previously it only looked up a
  *locked* one for All-Pro logic). Auto-lock + snapshot + `WeeklyCardBonus` FK all key off it.
- **Removed the (now-inert) All-Pro swap-grant block** from the equip endpoint — swaps are
  retired, and with the roster row always present it would have started misfiring for every
  user. Removed the orphaned `_grantAllProSwapsForRoster` method + its auto-lock call, and
  the dead `points_at_lock` loop in the auto-lock (weekly-sum scoring has no lock offset).
- Loyalty-snapshot capture simplified (roster always exists now). Removed the orphaned
  `cardUserCards` map.
- Deferred the rest of the swap web + endpoint deletion to 7b/Phase 8 (see above) — those
  are frontend-coupled and want an integration test.
- **Validated:** parse + import of both modules. Full equip→lock→score e2e in the Phase 9 simcheck.

## Phase 6 (FLEX unlock + slot wiring + retire powerups + no-dup-player) — DONE
- **Slot wiring:** the equip endpoint (`PUT /api/cards/equipped`) now takes a position `slot`
  string per card (`EquipCardSlot.slot`), validates it against `FUSION_ALL_SLOTS`, checks
  `cardManager.cardFitsSlot(template.position, slot)` (FLEX = any), and persists both
  `EquippedCard.slot` and `slot_number` (from `SLOT_TO_ORDINAL`). Both carry-forward paths
  (`seasonManager._carryForwardEquippedCards` + the GET-endpoint carry-forward) now copy
  `slot` too. Both equipped GETs expose `slot` in the response.
- **FLEX unlock consolidated:** placing a card in the FLEX slot requires an **MVP card
  equipped OR an active Accession (`temp_card_slot`) powerup** — replaces the old
  slot-6/maxSlots gate. The three calc-site FLEX detections (`_buildCardCalcContext`,
  `_processWeekCardEffects`, `cardProjection`) had their fallback repointed from the old
  champion-card / `temp_flex` signals to `mvp` / `temp_card_slot`.
- **No-duplicate-player rule:** the equip endpoint rejects two cards depicting the same
  player (alongside the existing no-dup-card-id + no-dup-effect checks).
- **Powerups retired:** `extra_swap` (Dispensation) + `temp_flex` (Conscription) removed from
  `POWERUP_CATALOG` (can't be bought; defs kept for historical display). `temp_card_slot`
  (Accession) reworded to "Unlocks the FLEX lineup slot".
- **Validated:** unit tests — `cardFitsSlot` / `SLOT_TO_ORDINAL` / `FUSION_ALL_SLOTS`; catalog
  no longer offers the retired slugs. Full equip-flow e2e deferred to Phase 9 simcheck.
- Note: the pre-fusion **fantasy-roster** endpoints still read `temp_flex` / `roster.players`
  — untouched here, collapsed in Phase 7.

## Phase 5c: OVERHAUL full_roster + all_in (owner: "completely overhaul")
Owner decision (2026-07-18): `bonus_round` got the threshold fix (done); `full_roster` and
`all_in` are NOT to be patched — they need a **complete redesign** for fusion, deferred to
a dedicated effort (likely alongside the Phase 9 tuning / a fresh design pass). Do NOT ship
the quick condition-patches that were proposed for them. Why each is broken under fusion:
- **`full_roster` (Diamond)** — currently ×1.4 FPx when the hand has all 5 positions. The 6
  base slots (QB/RB/WR1/WR2/TE/K) always span all 5 positions, so it fires free every week —
  wrong for a Diamond (should be conditional / useless-if-misdeployed). Its whole "collect
  every position" premise is dead when the lineup is position-locked. Needs a new premise.
- **`all_in` (Prismatic)** — FPx scaling with max duplicate position count. WR1 + WR2 are
  both position 3, so a standard lineup always shows ≥1 duplicate → it always fires for free.
  Needs a new premise (the "stack the same position" idea barely survives, since only the
  FLEX slot can add a genuine extra of a position).

The rest of the plan's "retune" list is a **magnitude** concern folded into Phase 9:
- Composition-shifted (still a real choice, just easier/higher): `anthem`, `diversified`,
  `gold_rush`, `stacked_deck`, `chain_reaction`, `copycat`.
- Fine / more interesting in fusion: `home_alone` (austerity) rewards a lean lineup now.
- Deep magnitude retune (absorb the lost ×1.5) is the Phase 9 tuning pass.

## Phase 5b (bonus_round threshold) — DONE
- `_computeBonusRound`: raised the trigger from **4 → 6** other cards (new module const
  `_BONUS_ROUND_THRESHOLD`), since 4+ was ~guaranteed with a 6–7 card fusion lineup. Value
  (`rewardValue`) untouched (magnitude → Phase 9). Description + detail text updated to
  "6 or more". **Validated:** unit test — fires at 6/7 triggered, not at 5.

## Phase 5a (retire stockpiler/vagabond + loyalty snapshot) — DONE
- **Retired** `stockpiler` (FPx per UNUSED swap) and `vagabond` (FPx per swap USED) — both
  swap-dependent, swaps are gone. Removed from `SHARED_EFFECT_POOL` (mint pool) following
  the existing `surplus` precedent; handler + display + payout reader kept so any existing
  owned copies still render (they compute 0 with no swaps).
- **Loyalty snapshot** repointed to the fusion source: the initial EQUIPPED set this season
  is captured on the first non-empty equip (`setEquippedCards`, from the depicted players),
  stored on `roster.initial_player_ids`. The old first-fantasy-roster-save capture is
  removed from the fantasy PUT. All read sites (`_buildCardCalcContext`,
  `_processWeekCardEffects`, `cardProjection`, `_computeLoyalty`) already read
  `initial_player_ids` / `ctx.initialRosterPlayerIds` — unchanged; only the source moved.
  Display/detail/docstring text updated ("first lineup this season").
- **Validated:** unit tests — loyalty pays per original still equipped (2 originals × 12 =
  24) and no-ops with no snapshot; retired effects confirmed out of the mint pool with
  handlers intact.

> **Watch-out (found during Phase 5):** the equip endpoint (`setEquippedCards`) still writes
> only `slot_number` (1–6), NOT the fusion `slot` string — that wiring is Phase 6/7. So
> `EquippedCard.slot` is currently NULL. The Phase 2+3 auto-lock gate was therefore keyed
> off `slot_number` (distinct slot_numbers = distinct filled slots), which is robust now and
> after Phase 6. FLEX detection via `eq.slot == 'FLEX'` currently falls back to the
> entitlement check (champion/temp_flex) until Phase 6 wires the slot string + FLEX unlock.

## Phase 4 (match bonus + Wildcard/Overdrive) — DONE
- `cardEffectCalculator._computeCardPass`: removed the ×1.5/×2.5 match multiplier entirely
  (the `isMatch`-gated `matchedFP *= matchMult` block, the `wildcard` force-match, the
  `overdrive` ×2.5). `isMatch` is still computed and gates the **position conditional**
  (always true in fusion; robust for transitional edge cases). Retired the
  `DEFAULT_MATCH_MULTIPLIER` constant.
- `CardBreakdown`: `matchMultiplied` is now always `False`, `matchMultiplier` always `1.0`
  (fields kept for breakdowns_json / recap schema stability; frontend cleanup is Phase 8).
- `_applyConductorBoost`: dropped the dead match-scale-up of the boost % (rode
  `matchMultiplied`, now always False).
- `seasonManager`: `overdrive` + `wildcard` dropped from `MODIFIER_WEIGHTS` (never rolled);
  kept in `MODIFIER_DISPLAY`/`_DESCRIPTIONS` as legacy labels for any historical rows.
- **Validated:** unit test (SimpleNamespace fixture, like `test_doubler_double_count.py`) —
  flat-FP card scores its primary with no ×1.5; overdrive/wildcard are no-ops; the position
  conditional still fires. Existing `test_doubler_double_count` + `test_lemons_marker_leak`
  still pass (doubler pinata FP dropped from the ×1.5-inflated value to primary+conditional,
  as intended).

## Phase 2+3 repoint sites — DONE
All scoring/context now computes off the **depicted players of the equipped cards** for the
relevant week (not `roster.players`). Each repoint keeps the per-card list so a player
depicted by two cards is counted per-card, matching the committed `getSnapshot` rewrite.

1. ✅ **`seasonManager._processWeekCardEffects`** — week-end `WeeklyCardBonus` banking.
   `allPlayerIds`, `rosterPlayerIds`, `weekRawFP`/`rosterTotalTds`, `kickerPids`, and FLEX
   detect all derive from `depictedPairs = [(eq, eq.user_card.card_template.player_id) …]`.
2. ✅ **`cardProjection.buildProjectionContext`** — equipped query moved to the top;
   `rosterPlayerIds` + the per-player stat loop + FLEX detect all off `depictedPairs`.
3. ✅ **`api/main.py`** equipped-cards GET + public GET — `isMatch` derivation off the
   equipped cards' depicted players (match multiplier itself removed in Phase 4).
4. ✅ Minor: `seasonManager` auto-lock gate (`:850`, now off equipped-card filled slots,
   batched via `getAllForWeek`); season finalization `_processUserSeasonTransitions`
   (weekly-sum: Σ over weeks of that week's lineup's `WeeklyPlayerFP`, no `points_at_lock`
   offset); Discord day-FP report (per-week equipped lineup, not a fixed roster).
5. ✅ Consistency: `fantasyTracker._buildCardCalcContext` FLEX detect repointed to
   `userEquipped` so the live path matches the banked path.

**Validated:** parse + runtime-import of all four modules; a constructed in-memory-SQLite
test of the weekly-sum finalization math + `_equippedRostersByWeek` (per-card double-count
of a duplicated player confirmed). Full `simcheck` deferred to Phase 9.

**Left for later phases (still reading `roster.players`, intentionally):**
- `seasonManager.py:863` — `points_at_lock` loop in auto-lock. Dead under weekly-sum but
  harmless during transition (operates on existing FantasyRosterPlayer rows). Cleanup ~P7.
- `api/main.py` fantasy-roster endpoints (7827, 7877, 8116, 8127, 8225, 8374, 8829, 8906,
  14173) + admin stats (5831) — collapse into equipped-cards endpoints in **Phase 7**.
- Loyalty `initial_player_ids` snapshot — **Phase 5**.

## Validation approach
- Per-edit: parse-check + a constructed-scenario unit test of the math (see the weekly-sum
  test used for `getSnapshot`).
- Phase 9: full `simcheck` (fresh fast sim) for scoring/economy/roster health.
- Full integration test of `_computeSnapshot` was deferred to Phase 9 (needs the app
  bootstrap / `get_session` monkeypatch); the core math is unit-validated.

## Watch-outs
- `FantasyRosterSwap` still imported + used in non-scoring methods of `fantasyTracker.py`
  (`:1019,1160,1162,1306`) and `seasonManager` — those retire in Phase 5/7, not now.
- `_buildCardCalcContext` still takes `roster` (for `roster.initial_player_ids` = Loyalty
  snapshot). Loyalty repoint is Phase 5.
- Don't drop `FantasyRosterPlayer`/`FantasyRosterSwap` tables until nothing references them
  (final cleanup, ~Phase 7). Retiring = stop using, then remove.
