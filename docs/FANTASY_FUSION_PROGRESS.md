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
| 4. Remove match bonus + Wildcard/Overdrive | ✅ DONE (unit-validated) | (this commit) |
| 5. Effects (retire stockpiler/vagabond, loyalty snapshot, retune) | ⬜ NEXT | — |
| 6. FLEX unlock + retire temp_flex/extra_swap + no-dup-player rule | ⬜ | — |
| 7. Collapse fantasy-roster API into equipped-cards endpoints | ⬜ | — |
| 8. Frontend unified lineup page (floosball-react) | ⬜ | — |
| 9. Tuning pass + `simcheck` | ⬜ | — |

## START HERE — Phase 5 (effects: retire stockpiler/vagabond, loyalty snapshot, retune)
Phases 2+3 and 4 are closed. Next: Phase 5.
- **RETIRE** `stockpiler` (`cardEffects.py:~2431`, reads unused swaps) and `vagabond`
  (`cardEffects.py:~4246`, reads swaps used) — both swap-dependent, swaps are gone.
- **`loyalty`**: replace the `initial_player_ids` snapshot (first-saved *fantasy roster*)
  with an "initial equipped set this season" snapshot. `_buildCardCalcContext` +
  `_processWeekCardEffects` + `cardProjection` all still read `roster.initial_player_ids`
  for `ctx.initialRosterPlayerIds` — repoint the *source* of that snapshot to the equipped
  cards (where/when it's captured), keep the ctx field.
- **RETUNE batch** (trivially-true / composition-shifted under position-locked slots):
  `full_roster`, `home_alone`, `bonus_round`, `diversified`, `anthem`, `gold_rush`,
  `stacked_deck`, `all_in`, `chain_reaction`, `copycat`. See the plan's "Effect verdict".
- Deep retune magnitude (absorb the lost ×1.5) is the **Phase 9** tuning pass, not here.

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
