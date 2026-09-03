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

Both sim layouts are accepted: `<simdir>/data/floosball.db` (a default sim) and
`<simdir>/floosball.db` (one started with `DATABASE_DIR=<dir>`).

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


def currentSeason(con) -> int:
    """The season the sim will start when it next boots.

    `startNewSeason` computes `seasonsPlayed + 1`, and a RESUMING sim sets
    `seasonsPlayed = current_season - 1` so it re-enters the season in progress — so the
    number to stamp is `simulation_state.current_season`. Falls back to the highest season
    row, then to 1.
    """
    for sql in ("SELECT current_season FROM simulation_state ORDER BY id DESC LIMIT 1",
                "SELECT MAX(season_number) FROM seasons"):
        try:
            row = con.execute(sql).fetchone()
        except sqlite3.Error:
            continue
        if row and row[0]:
            return int(row[0])
    return 1


def forceFormat(dbPath: str, fmt: str) -> tuple:
    patch = {'gameFormat': fmt, **PRESETS[fmt]}
    con = sqlite3.connect(dbPath, timeout=20)
    try:
        season = currentSeason(con)
        con.execute(
            'INSERT INTO app_settings (key, value, updated_at) VALUES (?,?,?) '
            'ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at',
            (RULE_OVERRIDES_KEY, json.dumps(patch), datetime.utcnow()))
        # ⚠️ STAMP THE SEASON, DO NOT DELETE THE STAMP. Deleting it looks equivalent --
        # `maybeResetRuleOverridesForSeason` treats an unstamped-but-present override as
        # belonging to the season being started, so it stamps rather than wipes, and the
        # override does survive. But it survives by making the APP do the write, and that
        # write DEADLOCKS: `startNewSeason` is inside the shared session's write
        # transaction, `_writeAppSetting` opens a SECOND connection for it, and the second
        # can never win because the first will not commit until `startNewSeason` returns.
        # The engine has a 30s `busy_timeout`, so it waits the full thirty seconds and then
        # kills the boot -- the sim died before a single game ran, every time, and the only
        # symptom was "database is locked" on a key nobody was looking at.
        #
        # Stamping it here with the season the app is about to start takes the early-return
        # branch instead, so the app makes no write at all. It is also what the stamp MEANS:
        # a forced format belongs to the season now in progress. And if the sim later rolls
        # into a genuinely new season the numbers differ, the override is wiped, and the
        # rulebook resets exactly as it should -- which deleting the stamp would also have
        # done, just after a deadlock.
        con.execute(
            'INSERT INTO app_settings (key, value, updated_at) VALUES (?,?,?) '
            'ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at',
            (RULE_OVERRIDES_SEASON_KEY, str(season), datetime.utcnow()))
        con.commit()
    finally:
        con.close()
    return patch, season


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

    # ⚠️ TWO LAYOUTS ARE BOTH NORMAL AND POINTING AT THE WRONG ONE FAILS SILENTLY. A default
    # sim keeps the database at `<simdir>/data/floosball.db`; one started with
    # `DATABASE_DIR=<dir>` keeps it at `<dir>/floosball.db`. Accepting only the first means
    # a DATABASE_DIR user either gets "no database" or -- worse, if a stale copy happens to
    # be there -- writes the format into a file the sim never reads, and then watches every
    # game come out standard with nothing to explain it.
    candidates = [os.path.join(args.simdir, 'data', 'floosball.db'),
                  os.path.join(args.simdir, 'floosball.db')]
    db = next((c for c in candidates if os.path.exists(c)), None)
    if db is None:
        print('no database found — looked in:', file=sys.stderr)
        for c in candidates:
            print(f'  {c}', file=sys.stderr)
        print('start the sim once with --fresh first', file=sys.stderr)
        return 1
    if '/data/' in os.path.abspath(db) and os.path.abspath(db).startswith('/data'):
        print('refusing to write to what looks like a production database', file=sys.stderr)
        return 1

    patch, season = forceFormat(db, args.format)
    print(f'database  {db}')
    print(f'wrote     {patch}')
    print(f'read      {readBack(db)}')
    print(f'stamped   season {season}')
    print('\nnow restart the sim WITHOUT --fresh; games from here use the new format.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
