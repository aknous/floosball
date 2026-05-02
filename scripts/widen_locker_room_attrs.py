"""One-off migration: widen existing players' locker-room attributes
(attitude, resilience, selfBelief) from the old 60-100 range into the
new 30-100 range used by the post-split generation in
floosball_player.py.

Strategy:
  - attitude, resilience: shift current value down by 7 with small
    Gaussian noise. Preserves rank ordering — high-attitude players
    stay high, low stays low — but stretches the floor down to match
    the new distribution shape.
  - selfBelief: every existing player has the column default (80, set
    by the inline migration when self_belief was added). No meaningful
    pre-existing value to preserve, so fully resample using the
    player's mental level (avg of unchanged game-pool attrs) as the
    center.

After this runs:
  - Most players' attitude/resilience are 8-15 points lower
  - A meaningful tail (~7% per attr) sits below 50 — real head cases,
    fragile players exist
  - selfBelief becomes a real per-player attribute rather than a flat 80

Idempotent gate via SHIFT_MARKER: re-running just no-ops. To force a
re-run, delete the marker file.

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


def shiftedValue(current: int, shift: int = 7, noise: float = 4.0) -> int:
    """Map an old 60-100 attr to the new 30-100 distribution while
    preserving rank ordering. Subtracts shift with small Gaussian noise.
    """
    if current is None:
        return 70  # safe default
    return clip(round(current - shift + random.gauss(0, noise)))


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

        newAtt = shiftedValue(att)
        newRes = shiftedValue(res)
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
