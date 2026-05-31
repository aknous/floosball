---
description: Add a new DB column following the project's four-step inline-migration pattern (model + ALTER TABLE + optional backfill + load/save plumbing)
argument-hint: [<table> <column> <sql_type> — e.g. "fantasy_rosters foo_field INTEGER"]
---

Add a new column following the project's four-step migration pattern. Arguments: $ARGUMENTS

Parse the arguments as `<table> <column> <sql_type>`. If the arguments are incomplete or ambiguous, ask the user what data this field represents and whether existing rows need a backfill from authoritative data (typically `games`, `game_player_stats`, or `weekly_player_fp`).

## Execute these steps in order. Do not skip step 4.

### Step 1: Model
Find the matching SQLAlchemy class in `database/models.py`. Add the column with the appropriate Mapped[…] type, a sensible default, and a one-line comment explaining what it stores and *why it needs persistence* (i.e. what reads it across restarts). Place it near related fields, not just at the end.

### Step 2: Inline migration
In `database/connection.py::_runPendingMigrations()`, add a new `try` block following the existing pattern:

```python
try:
    conn.execute(text("ALTER TABLE <table> ADD COLUMN <column> <sql_type> DEFAULT <default>"))
    conn.commit()
    logger.info("  Migration: added <table>.<column>")
except Exception:
    conn.rollback()
```

Put it next to thematically related migrations (e.g. fantasy-system columns near other fantasy migrations). The `except Exception: conn.rollback()` is the idempotency guard — re-running on a DB that already has the column will silently no-op.

### Step 3: Backfill (only if needed)
If existing rows need values derived from other data, write `def _backfill<DescriptiveName>():` in `database/connection.py`. The function must:

- Open its own connection: `conn = engine.connect()`
- Wrap in `try/except/finally`, rollback on error, log success/warning
- Use `UPDATE ... WHERE COALESCE(<column>, 0) < :computed` (or equivalent) to be **idempotent** — re-running must not corrupt already-correct rows
- Walk authoritative source data (e.g. `games` chronologically, `game_player_stats`, etc.) — don't trust other denormalized fields
- Log `f"  Backfill: ..."` with row count when something was changed

Then call it from `init_database()` after the existing backfill block (next to `_backfillPlayerCareerStatsFromGames()` etc.) — NOT inside `_runPendingMigrations()`.

### Step 4: Load/save plumbing
**This is the step that bites.** If the value is mutated in-memory at runtime, find the manager that hydrates it on boot and persists it on game/week end. Wire BOTH sides.

Common locations:
- **Team stats**: `managers/teamManager.py` (the `loadTeamSeasonStats`-style restore loop) + `managers/seasonManager.py::_saveTeamSeasonStatsToDatabase`
- **Equipped cards**: live snapshot in `managers/fantasyTracker.py::_buildCardCalcContext`, persisted in `managers/seasonManager.py` week-end card processing, carry-forward in `api/main.py` `/api/cards/equipped` GET + PUT
- **Roster swaps**: `api/main.py` `/api/fantasy/roster/swap` endpoint sets the field at swap time

Without step 4, the column will exist in the DB but the live in-memory dict resets to its default on every boot — the bug that hid Gone Streaking's peak streak at 0 for the entire season.

### Step 5: Verify
- `python -c "import ast; [ast.parse(open(f).read()) for f in ['database/models.py', 'database/connection.py', '<manager files touched>']]"` — syntax check
- Read the four touched files back to confirm the column appears in: model class, migration block, backfill (if any), load path, save path

After implementation, summarize what was changed and call out explicitly which load/save path was wired so a reviewer can verify step 4 wasn't skipped.
