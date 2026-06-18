#!/usr/bin/env python3
"""One-time recovery for a wiped week-22 retirement roll.

Background: the Front Office open block (week GM_ACTIVE_WEEK) commits its
fan-count snapshot (the once-per-season marker) immediately, but historically
left willRetire only in memory until the week-end checkpoint. A redeploy in that
gap reloaded will_retire=False for everyone while the committed marker survived
and then blocked the block from re-rolling -- leaving the season with no
retirements and no way to re-decide them. (The block now persists willRetire
before the marker, so this can't recur.)

This clears the marker for the CURRENT season so the block re-runs on the next
week transition (or the next deploy) and re-rolls + persists retirements and
re-seeds the HoF ballot. Safe: it changes nothing unless the stuck signature
holds -- marker set, zero retirees, and we're in the back half of the regular
season.

NOTE: seasons.current_week is only written at season start/end, so it reads a
stale 0 mid-season. We derive the real week from the last completed game instead.

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
dbWeek = row["current_week"]
markerSet = bool(row["front_office_fan_snapshot"])
willRetire = cur.execute(
    "SELECT COUNT(*) FROM players WHERE will_retire=1"
).fetchone()[0]
# Real week = last completed game's week (seasons.current_week is stale mid-season).
gw = cur.execute(
    "SELECT MAX(week) FROM games WHERE season=? AND status='final'", (season,)
).fetchone()[0]
gamesWeek = gw if gw is not None else 0
vets = cur.execute(
    "SELECT COUNT(*) FROM players WHERE seasons_played >= 10"
).fetchone()[0]
print(f"Season {season} | stale db_week={dbWeek} | real week~{gamesWeek} (last final game) "
      f"| marker set={markerSet} | will_retire={willRetire} | vets(10+ seasons)={vets}")

# 20..27: we're past the week-22 Front Office open (marker would be set) with at
# least one more regular-season week left for the block to re-run.
stuck = (markerSet and willRetire == 0 and 20 <= gamesWeek <= 27)
if stuck:
    cur.execute(
        "UPDATE seasons SET front_office_fan_snapshot = NULL WHERE season_number = ?",
        (season,),
    )
    conn.commit()
    print(f"CLEARED the week-22 marker for season {season}. Redeploy (or wait for the "
          f"next week) and the Front Office block re-runs: retirements re-roll and "
          f"persist, and the HoF ballot re-seeds.")
else:
    print("Stuck signature NOT met (need marker set, zero retirees, real week 20-27). "
          "No changes made -- paste me this line.")
conn.close()
