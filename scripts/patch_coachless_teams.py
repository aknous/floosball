"""One-off patch: assign a coach to any team in the DB without one.

Background: a bug in the GM hire-coach flow could leave a team without a
coach if the fire-coach vote passed but every hire-coach candidate fell
through (vote-tied coach already taken, or no votes met threshold and the
fallback hire ran in-memory only without persisting). This script finds
those teams in the DB and inserts a freshly-generated Coach row for each.

Names are pulled from the `unused_names` table — the same pool
teamManager.generateCoach() uses — and removed from that pool so a
future player generation won't reuse them.

Idempotent: re-running is safe — teams that already have a coach are
skipped. Self-contained (no project imports) so it runs fine via
`fly ssh console` against the production /data/floosball.db.

Usage (production):
    fly ssh sftp shell
    put scripts/patch_coachless_teams.py /data/patch_coachless_teams.py
    exit
    fly ssh console
    cd /data
    # Optional backup:
    python3 -c "import sqlite3; src=sqlite3.connect('/data/floosball.db'); dst=sqlite3.connect('/data/floosball.db.precoachpatch'); src.backup(dst); src.close(); dst.close()"
    python3 /data/patch_coachless_teams.py

After running:
- DB is correct.
- The running app's in-memory team.coach for affected teams stays None
  until the next process restart. On next boot, _loadCoachFromDatabase
  picks up the new rows and hydrates team.coach.
- Training (during offseason) tolerates None coach via getattr defaults.
"""

import os
import random
import sqlite3
import sys
from datetime import datetime, timezone

DB_PATH = '/data/floosball.db' if os.path.exists('/data/floosball.db') else 'data/floosball.db'


def generateAttribute(center: int = 80) -> int:
    """Approximation of np.clip(np.random.normal(center, 10), 60, 100)."""
    val = int(round(random.gauss(center, 10)))
    return max(60, min(100, val))


def main() -> int:
    if not os.path.exists(DB_PATH):
        print(f"DB not found at {DB_PATH}", file=sys.stderr)
        return 1

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Identify teams without a coach row tied to them
    cur.execute("""
        SELECT t.id, t.name
        FROM teams t
        LEFT JOIN coaches c ON c.team_id = t.id
        WHERE c.id IS NULL
        ORDER BY t.id
    """)
    coachless = cur.fetchall()

    if not coachless:
        print("All teams already have coaches in the DB — nothing to patch.")
        conn.close()
        return 0

    print(f"Found {len(coachless)} coachless team(s):")
    for row in coachless:
        print(f"  - team_id={row['id']:>3}  {row['name']}")

    # Pull from the same name pool generateCoach() uses.
    cur.execute("SELECT id, name FROM unused_names ORDER BY id")
    namePool = [(r['id'], r['name']) for r in cur.fetchall()]
    if len(namePool) < len(coachless):
        print(
            f"\nERROR: only {len(namePool)} names left in unused_names but "
            f"{len(coachless)} coaches needed. Aborting — would leave teams "
            f"unnamed. Refill the pool first.",
            file=sys.stderr,
        )
        conn.close()
        return 1

    # Don't reuse names already worn by an existing coach (defensive — the
    # unused_names pool should already be disjoint, but cheap to enforce).
    cur.execute("SELECT name FROM coaches")
    takenNames = {r['name'] for r in cur.fetchall()}
    namePool = [(nid, n) for (nid, n) in namePool if n not in takenNames]
    if len(namePool) < len(coachless):
        print(
            f"\nERROR: after removing already-taken names, pool is too small "
            f"({len(namePool)} available, {len(coachless)} needed).",
            file=sys.stderr,
        )
        conn.close()
        return 1

    rng = random.Random(datetime.now(timezone.utc).isoformat())
    rng.shuffle(namePool)

    print(f"\nGenerating coaches from unused_names pool and inserting rows...")
    inserted = []
    for row in coachless:
        teamId = row['id']
        teamName = row['name']

        nameId, name = namePool.pop()

        attrs = {
            'offensive_mind':     generateAttribute(),
            'defensive_mind':     generateAttribute(),
            'adaptability':       generateAttribute(),
            'aggressiveness':     generateAttribute(),
            'clock_management':   generateAttribute(),
            'player_development': generateAttribute(),
            'scouting':           generateAttribute(),
        }
        overall = round(sum(v for k, v in attrs.items() if k != 'scouting') / 6)

        cur.execute("""
            INSERT INTO coaches (
                name, team_id, seasons_coached,
                offensive_mind, defensive_mind, adaptability,
                aggressiveness, clock_management, player_development,
                scouting, overall_rating, created_at
            ) VALUES (
                ?, ?, 0,
                ?, ?, ?,
                ?, ?, ?,
                ?, ?, ?
            )
        """, (
            name, teamId,
            attrs['offensive_mind'], attrs['defensive_mind'], attrs['adaptability'],
            attrs['aggressiveness'], attrs['clock_management'], attrs['player_development'],
            attrs['scouting'], overall, datetime.now(timezone.utc).isoformat(),
        ))
        # Remove the name from the unused pool — same pattern as generateCoach
        cur.execute("DELETE FROM unused_names WHERE id = ?", (nameId,))
        inserted.append({
            'team': teamName, 'team_id': teamId,
            'coach': name, 'overall': overall, **attrs
        })

    conn.commit()
    conn.close()

    print(f"\nInserted {len(inserted)} coach row(s):")
    for c in inserted:
        print(
            f"  {c['team']:<20} ← {c['coach']:<22} "
            f"OVR {c['overall']}  "
            f"OM {c['offensive_mind']} DM {c['defensive_mind']} "
            f"ADP {c['adaptability']} AGG {c['aggressiveness']} "
            f"CLK {c['clock_management']} DEV {c['player_development']} "
            f"SCT {c['scouting']}"
        )
    print("\nDone. The new coaches will hydrate into in-memory team.coach on next app restart.")
    return 0


if __name__ == '__main__':
    sys.exit(main())
