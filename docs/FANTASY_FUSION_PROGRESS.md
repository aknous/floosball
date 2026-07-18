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
| 2+3. Remaining repoint sites | ⬜ NEXT | — |
| 4. Remove match bonus + Wildcard/Overdrive | ⬜ | — |
| 5. Effects (retire stockpiler/vagabond, loyalty snapshot, retune) | ⬜ | — |
| 6. FLEX unlock + retire temp_flex/extra_swap + no-dup-player rule | ⬜ | — |
| 7. Collapse fantasy-roster API into equipped-cards endpoints | ⬜ | — |
| 8. Frontend unified lineup page (floosball-react) | ⬜ | — |
| 9. Tuning pass + `simcheck` | ⬜ | — |

## START HERE — remaining Phase 2+3 repoint sites
`getSnapshot` (live leaderboard) is done. Repoint these to compute off the **depicted
players of the equipped cards** for the relevant week, NOT `roster.players`
(FantasyRosterPlayer). Use `_equippedRostersByWeek` / the same pattern as the committed
`getSnapshot` rewrite.

1. **`seasonManager._processWeekCardEffects`** (`managers/seasonManager.py:1778`) — the
   week-end `WeeklyCardBonus` banking. **Most important** (getSnapshot reads these banked
   bonuses for historical weeks). `roster.players` at `:1876, 1962, 1967, 2171, 2214`;
   FLEX detect at `:2214`; `_buildCardCalcContext`-mirroring context built here.
2. **`managers/cardProjection.py:315, 615`** — projected weekly payout.
3. **`api/main.py:9886, 9979`** — endpoints reading roster player ids.
4. Minor: `seasonManager.py:850,854` (filledSlots), `:5844`.

After these: the current-week AND historical scoring both run off equipped cards → Phase
2+3 fully closed. Then Phase 4.

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
