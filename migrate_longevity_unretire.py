#!/usr/bin/env python3
"""Raise existing players to the quality-weighted longevity model AND clear the
will_retire flag for any player the new longevity makes no longer retirement-
eligible this offseason.

Two coordinated changes:
  1. Longevity (raise-only) — same deterministic, quality-weighted formula as
     migrate_longevity.py / playerManager.createPlayer. Never shortens a career.
  2. will_retire — for every CURRENTLY-flagged player, re-run the exact
     computeRetirementOdds eligibility gate against the NEW longevity; if they're
     no longer eligible (e.g. a 5-season player whose longevity rose from 4 -> 8),
     clear the flag so they don't retire. Genuinely-old players still past their
     new (higher) longevity keep the flag and retire as normal.

Safe to run mid-season (week 22): retirements were only ANNOUNCED (flagged), not
yet executed, so clearing the flag fully un-announces them. RAISE-ONLY longevity,
targeted un-retire, deterministic, idempotent. Dry-run by default.

Dry-run:  fly ssh console -C "python3 /app/migrate_longevity_unretire.py"
Apply:    fly ssh console -C "python3 /app/migrate_longevity_unretire.py --apply"
"""
import os, sys, random, sqlite3
from collections import Counter
from constants import (
    LONGEVITY_BASE_MIN, LONGEVITY_BASE_MAX, LONGEVITY_QUALITY_PIVOT,
    LONGEVITY_QUALITY_DIVISOR, LONGEVITY_QUALITY_MAX_BONUS, LONGEVITY_CEILING,
    RETIREMENT_YEARS_PAST_EARLY, RETIREMENT_MIDCONTRACT_YEARS_PAST,
)

apply = '--apply' in sys.argv
dbDir = os.environ.get('DATABASE_DIR', 'data')
dbPath = os.path.join(dbDir, 'floosball.db')
print(f"DB: {dbPath} | mode: {'APPLY' if apply else 'DRY-RUN'}\n")

def qualityLongevity(playerId, rating):
    """Quality-weighted target longevity (deterministic per id) — mirrors createPlayer."""
    r = rating if rating is not None else 78
    bonus = min(LONGEVITY_QUALITY_MAX_BONUS,
                max(0, (r - LONGEVITY_QUALITY_PIVOT) / LONGEVITY_QUALITY_DIVISOR))
    base = random.Random(playerId).randint(LONGEVITY_BASE_MIN, LONGEVITY_BASE_MAX)
    return int(min(LONGEVITY_CEILING, base + bonus))

def isEligible(seasons, longevity, termRemaining):
    """Exact replica of playerManager.computeRetirementOdds' eligibility gate."""
    yearsPast = seasons - longevity
    if yearsPast < RETIREMENT_YEARS_PAST_EARLY:
        return False, yearsPast
    isWalkSeason = (termRemaining == 1)
    midContractOk = yearsPast >= RETIREMENT_MIDCONTRACT_YEARS_PAST
    if not isWalkSeason and not midContractOk:
        return False, yearsPast
    return True, yearsPast

conn = sqlite3.connect(dbPath)
conn.row_factory = sqlite3.Row
cur = conn.cursor()
rows = cur.execute("""
    SELECT p.id, p.name, p.player_rating AS rating, p.seasons_played AS seasons,
           p.term_remaining AS termRem, COALESCE(p.will_retire, 0) AS willRetire,
           pa.longevity AS cur
    FROM players p JOIN player_attributes pa ON pa.player_id = p.id
    WHERE COALESCE(p.is_hof, 0) = 0
""").fetchall()

longChanges = []           # (pid, newLong)
beforeDist, afterDist = Counter(), Counter()
unretire = []              # players to clear: (name, seasons, curLong, newLong, newYearsPast)
stillRetiring = []         # flagged players who remain eligible
for r in rows:
    curLong = r['cur'] or 0
    newLong = max(curLong, qualityLongevity(r['id'], r['rating']))
    beforeDist[curLong] += 1
    afterDist[newLong] += 1
    if newLong != curLong:
        longChanges.append((r['id'], newLong))
    if r['willRetire']:
        elig, yp = isEligible(r['seasons'] or 0, newLong, r['termRem'] or 0)
        if not elig:
            unretire.append((r['id'], r['name'], r['seasons'], curLong, newLong, yp, r['termRem']))
        else:
            stillRetiring.append((r['name'], r['seasons'], curLong, newLong, yp, r['termRem']))

print(f"=== LONGEVITY ===  {len(rows)} non-enshrined players | {len(longChanges)} raised")
print("  BEFORE:", dict(sorted(beforeDist.items())))
print("  AFTER :", dict(sorted(afterDist.items())))

flagged = len(unretire) + len(stillRetiring)
print(f"\n=== RETIREMENT FLAGS ===  {flagged} players currently flagged will_retire")
print(f"  -> UN-RETIRE (new longevity makes them ineligible): {len(unretire)}")
for pid, name, seasons, curLong, newLong, yp, termRem in sorted(unretire, key=lambda x: x[2]):
    print(f"     {name}: {seasons} seasons, longevity {curLong}->{newLong} "
          f"(yearsPast now {yp}, termRem {termRem})  [CLEARED]")
print(f"  -> STILL RETIRING (still past new longevity / walk season): {len(stillRetiring)}")
for name, seasons, curLong, newLong, yp, termRem in sorted(stillRetiring, key=lambda x: -x[1]):
    print(f"     {name}: {seasons} seasons, longevity {curLong}->{newLong} (yearsPast {yp}, termRem {termRem})")

if apply:
    for pid, newLong in longChanges:
        cur.execute("UPDATE player_attributes SET longevity=? WHERE player_id=?", (newLong, pid))
    for pid, name, *_ in unretire:
        cur.execute("UPDATE players SET will_retire=0 WHERE id=?", (pid,))
    conn.commit()
    print(f"\nAPPLIED: raised {len(longChanges)} longevities, cleared {len(unretire)} retirement flags.")
else:
    print("\nDRY-RUN: nothing written. Re-run with --apply to commit.")
