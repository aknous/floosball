"""Capture-time marker: record which teams have team.coach=None RIGHT NOW.

Background: a bug in the GM hire-coach flow leaves some teams with
team.coach=None in memory after the offseason fire/hire phase, even
though the DB has a coach row pointing at them. STEP 7 training reads
team.coach (default 50 when None), so those teams' players develop at
the default rate instead of their actual coach's rating.

This script hits the running app's API, finds teams whose coach field is
null, and saves the list to /data/coachless_at_training.json. The
companion script `compensate_coachless_training.py` reads that list
post-deploy and applies a flat dev-bias bonus to each affected player.

Run this BEFORE training (offseason STEP 7) fires — typically Saturday
during the rookie/FA draft window. Once training runs, the data is
locked and we can no longer correct it from the DB alone.

Idempotent: re-running overwrites the file with current state.

Usage (production):
    fly ssh console
    python3 /data/capture_coachless_teams.py
"""

import json
import os
import sqlite3
import sys
import urllib.request
from datetime import datetime, timezone

DB_PATH = '/data/floosball.db' if os.path.exists('/data/floosball.db') else 'data/floosball.db'
# Fly production listens on 8080 (set via fly.toml internal_port). Local dev
# uses 8000 (run_api.py default). Honor $PORT first if set; otherwise auto-
# detect by trying 8080 then 8000.
_PORT = os.environ.get('PORT')
API_BASE = f'http://localhost:{_PORT}/api' if _PORT else None
OUTPUT_PATH = '/data/coachless_at_training.json' if os.path.isdir('/data') else 'data/coachless_at_training.json'


def detectApiBase() -> str:
    if API_BASE:
        return API_BASE
    for port in (8080, 8000):
        try:
            with urllib.request.urlopen(f'http://localhost:{port}/api/teams', timeout=2) as resp:
                if resp.status == 200:
                    return f'http://localhost:{port}/api'
        except Exception:
            continue
    raise RuntimeError("Could not reach API on port 8080 or 8000")


def main() -> int:
    if not os.path.exists(DB_PATH):
        print(f"DB not found at {DB_PATH}", file=sys.stderr)
        return 1

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("SELECT id, name, abbr FROM teams ORDER BY id")
    teams = cur.fetchall()

    cur.execute("SELECT MAX(season) FROM team_funding")
    seasonRow = cur.fetchone()
    season = seasonRow[0] if seasonRow else None
    conn.close()

    apiBase = detectApiBase()
    affected = []
    print(f"Polling {len(teams)} teams from {apiBase} ...")
    for t in teams:
        try:
            with urllib.request.urlopen(f"{apiBase}/teams/{t['id']}", timeout=5) as resp:
                envelope = json.loads(resp.read().decode('utf-8'))
        except Exception as e:
            print(f"  team_id={t['id']:>3} {t['name']:<24}  API error: {e}")
            continue
        # Response shape: {success, message, data: {...team_dict...}}.
        # Tolerate the unwrapped shape too in case the format changes.
        teamData = envelope.get('data') if isinstance(envelope.get('data'), dict) else envelope
        coach = teamData.get('coach')
        if coach is None:
            affected.append({'team_id': t['id'], 'name': t['name'], 'abbr': t['abbr']})
            print(f"  team_id={t['id']:>3} {t['name']:<24}  NO COACH (memory)")
        else:
            coachName = coach.get('name', '?') if isinstance(coach, dict) else '?'
            print(f"  team_id={t['id']:>3} {t['name']:<24}  ok ({coachName})")

    payload = {
        'captured_at': datetime.now(timezone.utc).isoformat(),
        'season': season,
        'team_ids': [a['team_id'] for a in affected],
        'teams': affected,
    }
    with open(OUTPUT_PATH, 'w') as f:
        json.dump(payload, f, indent=2)

    print(f"\nSaved {len(affected)} affected team(s) to {OUTPUT_PATH}")
    if not affected:
        print("(No coachless teams found — nothing to compensate.)")
    return 0


if __name__ == '__main__':
    sys.exit(main())
