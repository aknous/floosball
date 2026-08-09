#!/usr/bin/env python3
"""Force a game format on a local sim, so all seven can actually be looked at.

⚠️ WHY THIS EXISTS. The formats change what a period, a clock and a score MEAN, so any
surface that renders a game — the board cards, the game page — has to be seen in each one.
They are normally reached only by winning a Cores rule vote on a Game Format day, which is
not something a test can wait for. This writes the `rule_overrides` app_setting directly,
which `Season.__init__` re-applies on every boot.

    # 1. let a sim create the database, then stop it
    python run_api.py --fresh --timing=fast     # ctrl-c once it is up

    # 2. force the format
    python tools_force_format.py <simdir> innings

    # 3. start again WITHOUT --fresh; games from here use the new format
    python run_api.py --timing=fast

Formats: standard target play_limit chess_clock innings frames bust

⚠️ LOCAL ONLY. This writes rules straight into app_settings with no vote behind it. Never
point it at prod — rule changes there are supposed to be something fans did.

Verify it took by reading `data.rules.gameFormat` from `GET /api/rules`. Note that the
response ALSO carries a `defaults` block with its own `gameFormat`, so a naive search for
the last occurrence reads `standard` and looks like a failure. Ask for `rules`, not
`defaults`.
"""
import argparse
import json
import os
import sqlite3
import sys
from datetime import datetime

# The extra config each format needs to be coherent, lifted from the rule-vote presets in
# constants.RULE_VOTE_CANDIDATES so a forced format matches what a real vote produces
# rather than a half-configured variant.
PRESETS = {
    'standard':    {},
    'target':      {'targetScore': 45},
    'play_limit':  {'playsPerQuarter': 20},
    'chess_clock': {'offenseClockBudgetSeconds': 1800},
    'innings':     {'inningsPerGame': 3, 'triesPerInning': 3},
    'frames':      {'framesPerGame': 6},
    'bust':        {'bustThreshold': 45},
}

RULE_OVERRIDES_KEY = 'rule_overrides'
RULE_OVERRIDES_SEASON_KEY = 'rule_overrides_season'


def forceFormat(dbPath: str, fmt: str) -> dict:
    patch = {'gameFormat': fmt, **PRESETS[fmt]}
    con = sqlite3.connect(dbPath)
    try:
        con.execute(
            'INSERT INTO app_settings (key, value, updated_at) VALUES (?,?,?) '
            'ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at',
            (RULE_OVERRIDES_KEY, json.dumps(patch), datetime.utcnow()))
        # Clearing the season stamp is what makes the override take on the NEXT boot.
        # `maybeResetRuleOverridesForSeason` treats an unstamped-but-present override as
        # belonging to the season being started, so it stamps rather than wipes.
        con.execute(f"DELETE FROM app_settings WHERE key = '{RULE_OVERRIDES_SEASON_KEY}'")
        con.commit()
    finally:
        con.close()
    return patch


def readBack(dbPath: str) -> dict:
    con = sqlite3.connect(dbPath)
    try:
        row = con.execute('SELECT value FROM app_settings WHERE key=?',
                          (RULE_OVERRIDES_KEY,)).fetchone()
    finally:
        con.close()
    return json.loads(row[0]) if row else {}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('simdir', help='the sim directory (the one holding data/floosball.db)')
    ap.add_argument('format', choices=sorted(PRESETS), help='which format to force')
    args = ap.parse_args()

    db = os.path.join(args.simdir, 'data', 'floosball.db')
    if not os.path.exists(db):
        print(f'no database at {db} — start the sim once with --fresh first', file=sys.stderr)
        return 1
    if '/data/' in os.path.abspath(db) and os.path.abspath(db).startswith('/data'):
        print('refusing to write to what looks like a production database', file=sys.stderr)
        return 1

    patch = forceFormat(db, args.format)
    print(f'wrote  {patch}')
    print(f'read   {readBack(db)}')
    print('\nnow restart the sim WITHOUT --fresh; games from here use the new format.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
