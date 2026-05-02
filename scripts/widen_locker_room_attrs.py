"""One-off migration: widen existing players' locker-room attributes
(attitude, resilience, selfBelief) from the old 60-100 range into the
new 30-100 range used by the post-split generation in
floosball_player.py.

Strategy:
  - attitude, resilience: linear remap from 60-100 → 30-100 with a
    small Gaussian perturbation. Preserves rank ordering AND matches
    the new generation's distribution shape — old-floor players (60)
    become real head cases (~30), old-median (80) becomes new-median
    (~65), top stays top.
  - selfBelief: every existing player has the column default (80, set
    by the inline migration when self_belief was added). No meaningful
    pre-existing value to preserve, so fully resample using the
    player's mental level (avg of unchanged game-pool attrs) as the
    Gaussian center.

After this runs:
  - Existing players span the full 30-100 range proportional to their
    old position
  - ~7% per attr sit below 50 (real head cases, fragile players)
  - ~22% sit below 60 (concerning), ~22% above 85 (clear leaders /
    tough / steady)
  - selfBelief becomes a real per-player attribute rather than a flat 80

Idempotent gate via marker file: re-running no-ops. To force a re-run,
delete the marker file.

Usage:
  fly ssh sftp shell
  put scripts/widen_locker_room_attrs.py /data/widen_locker_room_attrs.py
  exit
  fly ssh console
  python3 -c "import sqlite3; src=sqlite3.connect('/data/floosball.db'); dst=sqlite3.connect('/data/floosball.db.prelrwiden'); src.backup(dst); src.close(); dst.close()"
  python3 /data/widen_locker_room_attrs.py
"""

import os
import random
import sqlite3
import sys
from datetime import datetime, timezone

DB_PATH = '/data/floosball.db' if os.path.exists('/data/floosball.db') else 'data/floosball.db'
MARKER_PATH = '/data/widen_lr_attrs.consumed' if os.path.isdir('/data') else 'data/widen_lr_attrs.consumed'


def clip(value: int, lo: int = 30, hi: int = 100) -> int:
    return max(lo, min(hi, value))


def scaledValue(current: int, noise: float = 3.0) -> int:
    """Percentile-preserving remap from the old population (center ~80,
    stdDev ~10) to the new lr-pool population (center ~72, stdDev ~12).

    Formula: treat current as a sample from the old normal distribution,
    compute its z-score, then translate to the equivalent z-score in the
    new distribution:
        z_old = (current - 80) / 10
        new = 72 + z_old * 12 = 72 + (current - 80) * 1.2

    So old=60 → 48, old=80 → 72, old=100 → 96. Preserves rank ordering
    and produces a distribution shape matching the new generation:
    median ~72, ~7% below 50, tail to 30.

    A small Gaussian perturbation (stdDev=3) adds variance so identical
    old values don't all map to identical new ones.
    """
    if current is None:
        return 72  # new median
    # Defensive: pre-existing values should be 60-100 but be safe
    if current < 60:
        return clip(current)
    remapped = 72 + (current - 80) * 1.2
    return clip(round(remapped + random.gauss(0, noise)))


def resampledValue(mentalLevel: float, stdDev: float = 10.0) -> int:
    """Fully resample from the new lr-pool distribution.
    Used for selfBelief where existing values are all the column default
    (80 from the migration), with no meaningful per-player signal to
    preserve. Mirrors the lrPool generation in floosball_player.py.
    """
    lrCenter = max(55, mentalLevel - 7)
    return clip(round(random.gauss(lrCenter, stdDev)))


def main() -> int:
    if not os.path.exists(DB_PATH):
        print(f"DB not found at {DB_PATH}", file=sys.stderr)
        return 1

    if os.path.exists(MARKER_PATH):
        print(f"Marker file at {MARKER_PATH} — already widened. "
              f"Delete the marker file to re-run.", file=sys.stderr)
        return 0

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("""
        SELECT player_id, attitude, resilience, self_belief,
               focus, instinct, creativity, discipline
        FROM player_attributes
    """)
    rows = cur.fetchall()
    print(f"Loaded {len(rows)} players")

    updates = []
    for pid, att, res, sb, foc, ins, cre, dis in rows:
        # Estimate mental level from the unchanged game-pool attrs
        gamePool = [v for v in (foc, ins, cre, dis) if v is not None]
        mentalLevel = sum(gamePool) / len(gamePool) if gamePool else 80

        newAtt = scaledValue(att)
        newRes = scaledValue(res)
        # selfBelief: existing values are the column default 80. Resample.
        newSb = resampledValue(mentalLevel)

        updates.append((newAtt, newRes, newSb, pid))

    cur.executemany("""
        UPDATE player_attributes
        SET attitude = ?, resilience = ?, self_belief = ?
        WHERE player_id = ?
    """, updates)

    conn.commit()

    # Sample summary
    cur.execute("SELECT MIN(attitude), AVG(attitude), MAX(attitude) FROM player_attributes")
    aMin, aAvg, aMax = cur.fetchone()
    cur.execute("SELECT MIN(resilience), AVG(resilience), MAX(resilience) FROM player_attributes")
    rMin, rAvg, rMax = cur.fetchone()
    cur.execute("SELECT MIN(self_belief), AVG(self_belief), MAX(self_belief) FROM player_attributes")
    sMin, sAvg, sMax = cur.fetchone()
    cur.execute("SELECT COUNT(*) FROM player_attributes WHERE attitude < 50")
    aLow = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM player_attributes WHERE resilience < 50")
    rLow = cur.fetchone()[0]
    conn.close()

    # Drop marker so re-runs no-op
    with open(MARKER_PATH, 'w') as f:
        f.write(f"widened {len(rows)} players at {datetime.now(timezone.utc).isoformat()}\n")

    print(f"\nUpdated {len(updates)} player_attributes rows.")
    print(f"\nNew distributions:")
    print(f"  attitude:    min={aMin:.0f}  avg={aAvg:.1f}  max={aMax:.0f}  ({aLow} below 50)")
    print(f"  resilience:  min={rMin:.0f}  avg={rAvg:.1f}  max={rMax:.0f}  ({rLow} below 50)")
    print(f"  selfBelief:  min={sMin:.0f}  avg={sAvg:.1f}  max={sMax:.0f}")
    print(f"\nMarker file written: {MARKER_PATH}")
    print(f"To force a re-run, delete the marker file first.")
    return 0


if __name__ == '__main__':
    sys.exit(main())
