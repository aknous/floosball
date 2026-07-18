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
| 7a. Equip endpoint owns the FantasyRoster row + drop All-Pro swap machinery | ✅ DONE | (this commit) |
| 7b. Delete old fantasy-roster endpoints + swap web (co-dev w/ frontend) | ⬜ → Phase 8 | — |
| 8. Frontend unified lineup page (floosball-react) + 7b API retirement | ⬜ NEXT | — |
| 9. Tuning pass + `simcheck` | ⬜ | — |

## START HERE — Phase 8 (frontend unified lineup page) + Phase 7b (retire the old API)
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
