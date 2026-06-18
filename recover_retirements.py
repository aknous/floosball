#!/usr/bin/env python3
"""One-time recovery for a wiped week-22 retirement roll.

Background: the Front Office open block (week GM_ACTIVE_WEEK) commits its
fan-count snapshot (the once-per-season marker) immediately, but historically
left willRetire only in memory until the week-end checkpoint. A redeploy in that
gap reloaded will_retire=False for everyone while the committed marker survived
and then blocked the block from re-rolling — leaving the season with no
retirements and no way to re-decide them. (The block now persists willRetire
before the marker, so this can't recur.)

This script clears the marker for the CURRENT season so the block re-runs on the
next week transition (or the next deploy) and re-rolls + persists retirements and
re-seeds the HoF ballot. It is safe: it changes nothing unless the stuck
signature holds — regular season (weeks 22-28), marker set, and zero retirees.

Run on prod:  fly ssh console -C "python3 /app/recover_retirements.py"
"""
import os
import sqlite3

dbDir = os.environ.get('DATABASE_DIR', 'data')
dbPath = os.path.join(dbDir, 'floosball.db')
print(f"DB: {dbPath}")

conn = sqlite3.connect(dbPath)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

row = cur.execute(
    "SELECT season_number, current_week, front_office_fan_snapshot "
    "FROM seasons ORDER BY season_number DESC LIMIT 1"
).fetchone()
if row is None:
    print("No season row found; nothing to do.")
    conn.close()
    raise SystemExit(0)

season = row["season_number"]
week = row["current_week"]
markerSet = bool(row["front_office_fan_snapshot"])
willRetire = cur.execute(
    "SELECT COUNT(*) FROM players WHERE will_retire=1"
).fetchone()[0]
print(f"Season {season}, week {week} | marker set: {markerSet} | "
      f"will_retire players: {willRetire}")

stuck = (week is not None and 22 <= week <= 28 and markerSet and willRetire == 0)
if stuck:
    cur.execute(
        "UPDATE seasons SET front_office_fan_snapshot = NULL WHERE season_number = ?",
        (season,),
    )
    conn.commit()
    print(f"CLEARED the week-22 marker for season {season}. On the next week "
          f"transition (or a redeploy) the retirement roll re-runs and persists, "
          f"and the HoF ballot re-seeds.")
else:
    print("Stuck signature NOT met (need weeks 22-28, marker set, zero retirees). "
          "No changes made.")
conn.close()
