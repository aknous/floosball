"""Regression test for the offseason phase-rollback snapshot mechanism.

Covers the two behaviors that must hold for a mid-draft restart to recover
cleanly (see seasonManager._snapshotDbForPhase / run_api._restorePartial...):

  1. The snapshot is table-scoped — it omits the large in-season append-only
     tables (OFFSEASON_SNAPSHOT_EXCLUDE_TABLES) so it stays small and flat
     across seasons.
  2. Restore replaces ONLY the snapshotted (offseason-mutable) tables, rolling
     back partial draft picks while leaving the excluded history tables as-is,
     and is a no-op once the phase is marked complete.

Run standalone:  .venv/bin/python test_offseason_snapshot.py
Exits non-zero on failure. (The real writer's table-scoping is additionally
exercised by any fast offseason sim, which logs "N tables, X.XMB" per phase.)
"""
import os
import sqlite3
import tempfile


def _buildPhaseEntrySnapshot(dbPath, snapPath, excludeTables):
    """Mirror of seasonManager._snapshotDbForPhase's table-scoped copy."""
    src = sqlite3.connect(dbPath)
    try:
        tables = [r[0] for r in src.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%'")]
        included = [t for t in tables if t not in excludeTables]
        src.execute("ATTACH DATABASE ? AS snap", (snapPath,))
        try:
            for t in included:
                src.execute(f'CREATE TABLE snap."{t}" AS SELECT * FROM main."{t}"')
        finally:
            src.execute("DETACH DATABASE snap")
    finally:
        src.close()


def main():
    if os.path.exists('/data'):
        print("SKIP: /data exists on this host — restore would target it, not the temp DB")
        return

    from constants import OFFSEASON_SNAPSHOT_EXCLUDE_TABLES
    import run_api

    tmp = tempfile.mkdtemp(prefix='floos_snaptest_')
    os.environ['DATABASE_DIR'] = tmp
    dbPath = os.path.join(tmp, 'floosball.db')

    # Live DB frozen at fa_draft phase entry: rookies undrafted, history present.
    con = sqlite3.connect(dbPath)
    con.executescript("""
        CREATE TABLE players (id INTEGER PRIMARY KEY, name TEXT, team TEXT);
        CREATE TABLE game_player_stats (id INTEGER PRIMARY KEY, yards INTEGER);
        CREATE TABLE simulation_state (id INTEGER PRIMARY KEY, current_season INTEGER,
            in_offseason INTEGER, offseason_phase TEXT, offseason_completed_steps TEXT);
        INSERT INTO players VALUES (1,'Rook A',NULL),(2,'Rook B',NULL);
        INSERT INTO game_player_stats VALUES (1,100),(2,200);
        INSERT INTO simulation_state VALUES (1, 1, 1, 'fa_draft', '[]');
    """)
    con.commit(); con.close()

    snapPath = os.path.join(tmp, 'offseason_s1_fa_draft.db')
    _buildPhaseEntrySnapshot(dbPath, snapPath, OFFSEASON_SNAPSHOT_EXCLUDE_TABLES)

    # (1) snapshot excludes the big in-season tables.
    s = sqlite3.connect(snapPath)
    snapTables = set(r[0] for r in s.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"))
    s.close()
    assert 'game_player_stats' not in snapTables, f"excluded table leaked: {snapTables}"
    assert {'players', 'simulation_state'} <= snapTables, snapTables

    # Simulate a crash mid-draft: a partial pick + a stray history row after the snapshot.
    con = sqlite3.connect(dbPath)
    con.execute("UPDATE players SET team='Sharks' WHERE id=1")
    con.execute("INSERT INTO game_player_stats VALUES (3,300)")
    con.commit(); con.close()

    run_api._restorePartialPhaseSnapshotIfNeeded()

    # (2) mutable table rolled back; excluded table preserved; .preresume written.
    con = sqlite3.connect(dbPath)
    players = dict(con.execute("SELECT id, team FROM players").fetchall())
    stats = sorted(r[0] for r in con.execute("SELECT id FROM game_player_stats").fetchall())
    con.close()
    assert players[1] is None, f"mutable table NOT rolled back: {players}"
    assert stats == [1, 2, 3], f"excluded table was wrongly rolled back: {stats}"
    assert os.path.exists(dbPath + '.preresume'), ".preresume backup missing"

    # (3) no-op once the phase is complete.
    con = sqlite3.connect(dbPath)
    con.execute("UPDATE simulation_state SET offseason_completed_steps='[\"fa_draft\"]'")
    con.execute("UPDATE players SET team='Eels' WHERE id=2")
    con.commit(); con.close()
    run_api._restorePartialPhaseSnapshotIfNeeded()
    con = sqlite3.connect(dbPath)
    t2 = con.execute("SELECT team FROM players WHERE id=2").fetchone()[0]
    con.close()
    assert t2 == 'Eels', f"completed phase was wrongly rolled back: {t2}"

    import shutil as _sh
    _sh.rmtree(tmp, ignore_errors=True)
    print("PASS: snapshot table-scoping + partial-phase rollback + completed-phase guard")


if __name__ == '__main__':
    main()
