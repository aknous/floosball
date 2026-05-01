"""One-off patch: assign a coach to any team in the DB without one.

Background: a bug in the GM hire-coach flow could leave a team without a
coach if the fire-coach vote passed but every hire-coach candidate fell
through (vote-tied coach already taken, or no votes met threshold and the
fallback hire ran in-memory only without persisting). This script finds
those teams in the DB and inserts a freshly-generated Coach row for each.

Idempotent: re-running is safe — teams that already have a coach are
skipped. Self-contained (no project imports) so it runs fine via
`fly ssh console` against the production /data/floosball.db.

Usage (production):
    fly ssh console
    cd /data
    # If you want to back up first:
    python3 -c "import sqlite3; src=sqlite3.connect('/data/floosball.db'); dst=sqlite3.connect('/data/floosball.db.precoachpatch'); src.backup(dst); src.close(); dst.close()"
    # Paste-and-run this script:
    python3 < /path/to/patch_coachless_teams.py
    # Or copy via sftp first then run by path.

After running:
- DB is correct.
- The running app's in-memory team.coach for affected teams stays None
  until the next process restart (the API will keep reporting no coach
  for those teams in the meantime). On next boot, _loadCoachFromDatabase
  picks up the new rows and hydrates team.coach.
- Training (during offseason) tolerates None coach via getattr defaults.
"""

import os
import random
import sqlite3
import sys
from datetime import datetime

DB_PATH = '/data/floosball.db' if os.path.exists('/data/floosball.db') else 'data/floosball.db'

COACH_FIRST_NAMES = [
    "Bill", "Tom", "Andy", "Mike", "Sean", "Kyle", "Matt", "John", "Dan", "Greg",
    "Ron", "Pete", "Dave", "Steve", "Frank", "Gary", "Rick", "Joe", "Jim", "Bob",
    "Ray", "Art", "Lou", "Hank", "Vince", "Wade", "Marty", "Rex", "Norm", "Buddy",
    "Chuck", "Chip", "Curt", "Dean", "Earl", "Fran", "Glen", "Hal", "Ivan", "Jack",
    "Karl", "Lane", "Marc", "Nick", "Otto", "Paul", "Quinn", "Rob", "Sam", "Ted",
    "Vic", "Walt", "Zach", "Alan", "Bret", "Clyde", "Don", "Eric", "Fred", "Gus",
]

COACH_LAST_NAMES = [
    "Walsh", "Belichick", "Noll", "Shula", "Halas", "Lombardi", "Landry", "Brown",
    "Parcells", "Gibbs", "Johnson", "Reid", "Payton", "Carroll", "Rivera", "Taylor",
    "Smith", "Jones", "Davis", "Wilson", "Moore", "Thomas", "Jackson", "White",
    "Harris", "Martin", "Thompson", "Garcia", "Martinez", "Anderson", "Robinson",
    "Clark", "Lewis", "Lee", "Walker", "Hall", "Allen", "Young", "King", "Wright",
    "Scott", "Green", "Baker", "Adams", "Nelson", "Hill", "Ramirez", "Campbell",
    "Mitchell", "Roberts", "Carter", "Phillips", "Evans", "Turner", "Torres",
    "Parker", "Collins", "Edwards", "Stewart", "Flores", "Morris", "Nguyen",
]


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

    # Snapshot current taken-name set so we don't collide
    cur.execute("SELECT name FROM coaches")
    takenNames = {r['name'] for r in cur.fetchall()}

    print(f"\nGenerating coaches and inserting rows...")
    nameSeed = random.Random(datetime.utcnow().isoformat())
    inserted = []
    for row in coachless:
        teamId = row['id']
        teamName = row['name']
        # Pick a unique name (try up to 50 times before falling through)
        name = None
        for _ in range(50):
            candidate = (
                f"{nameSeed.choice(COACH_FIRST_NAMES)} "
                f"{nameSeed.choice(COACH_LAST_NAMES)}"
            )
            if candidate not in takenNames:
                name = candidate
                takenNames.add(candidate)
                break
        if name is None:
            name = f"Coach #{teamId}"

        attrs = {
            'offensive_mind':    generateAttribute(),
            'defensive_mind':    generateAttribute(),
            'adaptability':      generateAttribute(),
            'aggressiveness':    generateAttribute(),
            'clock_management':  generateAttribute(),
            'player_development': generateAttribute(),
            'scouting':          generateAttribute(),
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
            attrs['scouting'], overall, datetime.utcnow().isoformat(),
        ))
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
