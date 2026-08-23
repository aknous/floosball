"""Compare config.json's `divisionDistribution` against a live database, BEFORE deploying.

⚠️ RUN THIS AGAINST PRODUCTION FIRST. Divisions now come from config by name, which is what
makes them stable — but it also means that if the config map disagrees with the clubs a
live league actually holds, the deploy MOVES teams. That is a one-time reshuffle of exactly
the kind the config map exists to prevent, and it would land silently.

Three things can differ, and they are not the same problem:

  LEAGUE MISMATCH  a club config places in a division of league X is really in league Y.
                   `_assignDivisions` REFUSES a map like this and falls back to the old
                   positional split, so the deploy changes nothing — but the config map is
                   then decorative and the instability is still there. Usually means the
                   one-time `realignByRecentPerformance` moved clubs before it was
                   removed (2026-08-23), and config never caught up. Nothing will move
                   them back — `_applyPersistedAlignment` keeps the alignment a database
                   already has — so --emit is the fix.

  DIVISION MOVE    leagues agree, but a club sits in a different division than config says.
                   The deploy WILL move it. Accept it, or freeze what is live with --emit.

  CLEAN            config and the database agree. Deploying changes nothing.

Usage:
    .venv/bin/python tools_check_divisions.py                  # local data/floosball.db
    DATABASE_DIR=/data .venv/bin/python tools_check_divisions.py
    .venv/bin/python tools_check_divisions.py --emit           # print a map matching the DB

On production there is no sqlite3 binary, so run it through the app's own python:
    fly ssh console -C "python3 /app/tools_check_divisions.py"
"""
import json
import os
import sqlite3
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(os.environ.get('DATABASE_DIR', os.path.join(HERE, 'data')), 'floosball.db')


def main() -> int:
    emit = '--emit' in sys.argv

    with open(os.path.join(HERE, 'config.json')) as fh:
        cfg = json.load(fh)
    configDivisions = cfg.get('divisionDistribution') or {}
    divisionsByLeague = cfg.get('divisions') or {}
    leagueOfDivision = {d: lg for lg, names in divisionsByLeague.items() for d in names}

    if not os.path.exists(DB):
        print(f"No database at {DB}")
        return 2
    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    rows = conn.execute(
        "SELECT t.name, t.division, l.name FROM teams t "
        "LEFT JOIN leagues l ON l.id = t.league_id").fetchall()
    conn.close()
    if not rows:
        print("No teams in the database.")
        return 2

    liveDivision = {name: div for name, div, _lg in rows}
    liveLeague = {name: lg for name, _div, lg in rows}

    if emit:
        out = defaultdict(list)
        for name, div, _lg in rows:
            out[div].append(name)
        print(json.dumps({d: sorted(v) for d, v in sorted(out.items())}, indent=2))
        return 0

    if not configDivisions:
        print("config.json has no divisionDistribution — nothing to compare.")
        return 1

    leagueMismatch, divisionMove, missing = [], [], []
    for div, teams in configDivisions.items():
        wantLeague = leagueOfDivision.get(div)
        for name in teams:
            if name not in liveDivision:
                missing.append(name)
                continue
            if wantLeague and liveLeague.get(name) and liveLeague[name] != wantLeague:
                leagueMismatch.append((name, liveLeague[name], div, wantLeague))
            elif liveDivision[name] != div:
                divisionMove.append((name, liveDivision[name], div))

    unlisted = sorted(set(liveDivision) - {t for v in configDivisions.values() for t in v})

    if leagueMismatch:
        print(f"LEAGUE MISMATCH ({len(leagueMismatch)}) — the map will be REFUSED and the "
              "positional split used instead:")
        for name, isIn, div, wants in leagueMismatch:
            print(f"  {name:16s} is in {isIn}, config puts it in {div} ({wants})")
    if divisionMove:
        print(f"\nDIVISION MOVE ({len(divisionMove)}) — deploying WILL move these:")
        for name, was, becomes in divisionMove:
            print(f"  {name:16s} {was} -> {becomes}")
    if missing:
        print(f"\nIN CONFIG, NOT IN THE DATABASE ({len(missing)}): {sorted(missing)}")
    if unlisted:
        print(f"\nIN THE DATABASE, NOT IN CONFIG ({len(unlisted)}): {unlisted}")

    if not (leagueMismatch or divisionMove or missing or unlisted):
        print("CLEAN — config and the database agree. Deploying moves nobody.")
        return 0

    print("\nTo freeze what is LIVE instead of moving anyone, run with --emit and paste "
          "the result into config.json as divisionDistribution.")
    return 1


if __name__ == '__main__':
    sys.exit(main())
