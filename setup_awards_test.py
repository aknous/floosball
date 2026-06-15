"""Local test setup for fan-voted Awards (feature/awards-voting).

Puts a DB into a state where BOTH voting windows are open with a populated HoF
ballot, so you can exercise the /awards page without racing the sim:
  - sets current_week = 28  -> MVP window opens (and HoF stays open, wk >= 22)
  - seeds hof_ballot_entries from the will_retire players (this season's
    retiring set) so the HoF ballot has candidates immediately

Pure SQL — no app context. Run against a COPY, then boot the backend on it.

Usage (the DB is ALWAYS named floosball.db; isolate by DIRECTORY via
DATABASE_DIR — there is no DB_FILENAME env var):
    mkdir -p data/awardstest
    cp data/floosball.db data/awardstest/floosball.db
    .venv/bin/python setup_awards_test.py data/awardstest/floosball.db
    DATABASE_DIR=data/awardstest .venv/bin/python run_api.py --timing=scheduled
    # then open the frontend (feature/awards-voting) and visit /awards
"""
import sys
import sqlite3
from datetime import datetime

HOF_BALLOT_TENURE = 5  # mirror constants.AWARD_HOF_BALLOT_TENURE


def main(path: str) -> None:
    con = sqlite3.connect(path)
    cur = con.cursor()

    season = cur.execute("SELECT current_season FROM simulation_state").fetchone()[0]
    print(f"DB season {season}")

    # 1. Open the MVP window (regular-season end). HoF is already open at wk>=22.
    cur.execute("UPDATE simulation_state SET current_week = 28")
    print("set current_week = 28 (MVP + HoF windows open)")

    # 2. Seed the HoF ballot from this season's retiring set (will_retire = 1).
    #    For a test we seed ALL of them (skip the points pre-filter) so the
    #    ballot is full enough to vote on. Idempotent on player_id.
    # will_retire and NOT already enshrined (mirrors the production seed, which
    # skips is_hof players).
    retirees = cur.execute(
        "SELECT id FROM players WHERE will_retire = 1 AND COALESCE(is_hof, 0) = 0"
    ).fetchall()
    now = datetime.utcnow().isoformat()
    seeded = 0
    for (pid,) in retirees:
        exists = cur.execute(
            "SELECT 1 FROM hof_ballot_entries WHERE player_id = ?", (pid,)
        ).fetchone()
        if exists:
            continue
        cur.execute(
            "INSERT INTO hof_ballot_entries "
            "(player_id, first_eligible_season, seasons_remaining, status, created_at, updated_at) "
            "VALUES (?, ?, ?, 'on_ballot', ?, ?)",
            (pid, season, HOF_BALLOT_TENURE, now, now),
        )
        seeded += 1
    con.commit()
    print(f"seeded {seeded} HoF ballot candidates (from {len(retirees)} will_retire players)")
    print("done — boot the backend on this DB and open /awards")
    con.close()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: python setup_awards_test.py <path-to-db>")
        sys.exit(1)
    main(sys.argv[1])
