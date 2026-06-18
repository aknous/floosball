#!/usr/bin/env python3
"""Migrate existing players to the quality-weighted longevity model.

Recomputes each non-enshrined player's longevity = max(current, quality-weighted
target) so the new floor (LONGEVITY_BASE_MIN) and the talent bonus apply
retroactively. RAISE-ONLY: it never shortens a career. Deterministic per player
(the random base is seeded by player id), so the dry-run preview exactly matches
what --apply writes, and re-running is idempotent.

Mirrors the formula in playerManager.createPlayer, but keys the talent bonus off
each player's current rating instead of the generation seed.

Dry-run (default):  fly ssh console -C "python3 /app/migrate_longevity.py"
Apply:              fly ssh console -C "python3 /app/migrate_longevity.py --apply"
"""
import os
import sys
import random
import sqlite3
from collections import Counter

from constants import (
    LONGEVITY_BASE_MIN, LONGEVITY_BASE_MAX, LONGEVITY_QUALITY_PIVOT,
    LONGEVITY_QUALITY_DIVISOR, LONGEVITY_QUALITY_MAX_BONUS, LONGEVITY_CEILING,
)

apply = '--apply' in sys.argv
dbDir = os.environ.get('DATABASE_DIR', 'data')
dbPath = os.path.join(dbDir, 'floosball.db')
print(f"DB: {dbPath} | mode: {'APPLY' if apply else 'DRY-RUN'}")


def qualityLongevity(playerId, rating):
    """Quality-weighted target longevity for a player (deterministic per id)."""
    r = rating if rating is not None else 78
    bonus = min(LONGEVITY_QUALITY_MAX_BONUS,
                max(0, (r - LONGEVITY_QUALITY_PIVOT) / LONGEVITY_QUALITY_DIVISOR))
    base = random.Random(playerId).randint(LONGEVITY_BASE_MIN, LONGEVITY_BASE_MAX)
    return int(min(LONGEVITY_CEILING, base + bonus))


conn = sqlite3.connect(dbPath)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

rows = cur.execute("""
    SELECT p.id, p.name, p.player_rating AS rating, pa.longevity AS cur
    FROM players p JOIN player_attributes pa ON pa.player_id = p.id
    WHERE COALESCE(p.is_hof, 0) = 0
""").fetchall()

changes = []
beforeDist = Counter()
afterDist = Counter()
for r in rows:
    curLong = r['cur'] or 0
    target = qualityLongevity(r['id'], r['rating'])
    newLong = max(curLong, target)
    beforeDist[curLong] += 1
    afterDist[newLong] += 1
    if newLong != curLong:
        changes.append((r['id'], r['name'], curLong, newLong, r['rating']))

print(f"{len(rows)} non-enshrined players | {len(changes)} would be raised")
print("longevity BEFORE:", dict(sorted(beforeDist.items())))
print("longevity AFTER :", dict(sorted(afterDist.items())))
print("sample raises:")
for pid, name, curLong, newLong, rating in sorted(changes, key=lambda c: c[3], reverse=True)[:12]:
    print(f"  {name}: {curLong} -> {newLong}  (rating {rating})")

if apply:
    for pid, name, curLong, newLong, rating in changes:
        cur.execute("UPDATE player_attributes SET longevity=? WHERE player_id=?", (newLong, pid))
    conn.commit()
    print(f"APPLIED: raised longevity for {len(changes)} players.")
else:
    print("DRY-RUN: nothing written. Re-run with --apply to commit.")
conn.close()
