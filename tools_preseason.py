"""Preseason forecast: simulate one upcoming season N times and report the spread.

Copies a season-start database once per run, plays that season to its Floos Bowl in
`fast` timing, and aggregates champions and win totals across the runs. Every run
starts from the identical schedule and rosters, so the spread is the sim's own
variance rather than a difference in setup.

    .venv/bin/python tools_preseason.py --db /tmp/prod.db --season 4 --runs 25

⚠️ THE SIM DOES NOT STOP AT A SEASON BOUNDARY. Left alone `run_api.py` plays the
offseason and rolls straight into the next season, and the one after. Each run is
therefore killed the moment its Floos Bowl goes final.

⚠️ AND DO NOT GATE THAT ON A GAME COUNT. A season-N game count stops changing when
season N ends AND when the sim has moved on to season N+1 — the two are
indistinguishable, so a count-based poll reports a finished season while the process
keeps running for another ten minutes. Gate on the Floos Bowl ROW. Measured: a run
polled by count reached season 6 before anyone noticed.

⚠️ THE SNAPSHOT MUST BE AT WEEK 0 WITH THE SCHEDULE ALREADY GENERATED. That is the
state prod sits in between the offseason finishing and the first kickoff. Taken
earlier, each run plays its own offseason and the rosters diverge before week 1, so
the runs are no longer forecasting the same season. `--allow-any-state` overrides.

⚠️ Nothing seeds the RNG globally, which is what makes independent processes diverge.
If a global seed is ever added, every run returns the identical season and the report
will look suspiciously clean rather than failing.
"""

import argparse
import json
import os
import shutil
import signal
import sqlite3
import statistics
import subprocess
import sys
import time
from collections import Counter

REPO = os.path.dirname(os.path.abspath(__file__))
# 8000 is the dev server and 8080 is often taken; leave both alone.
BASE_PORT = 8100


def readOnly(path):
    return sqlite3.connect(f'file:{path}?mode=ro', uri=True)


def inspectSnapshot(path, season):
    """What state is this database in, and is it a fair starting line?"""
    c = readOnly(path)
    q = c.execute
    out = {}
    out['integrity'] = q("PRAGMA quick_check").fetchone()[0]
    row = q("SELECT current_season, current_week FROM simulation_state ORDER BY id LIMIT 1").fetchone()
    out['simSeason'], out['simWeek'] = (row or (None, None))
    out['scheduled'] = q("SELECT COUNT(*) FROM games WHERE season=? AND is_playoff=0", (season,)).fetchone()[0]
    out['played'] = q("SELECT COUNT(*) FROM games WHERE season=? AND status='final'", (season,)).fetchone()[0]
    out['teams'] = q("SELECT COUNT(*) FROM teams").fetchone()[0]
    out['rostered'] = q("SELECT COUNT(*) FROM players WHERE team_id IS NOT NULL").fetchone()[0]
    c.close()
    return out


def bowlIsFinal(path, season):
    """The one true completion signal. Returns False on any read error: a run mid-write
    is a normal thing to observe, not a failure."""
    try:
        c = readOnly(path)
        r = c.execute("SELECT status FROM games WHERE season=? AND is_playoff=1 "
                      "AND playoff_round='4'", (season,)).fetchone()
        c.close()
        return bool(r and r[0] == 'final')
    except Exception:
        return False


def runOne(runId, snapshot, season, workDir, timeoutSecs):
    """Play `season` once. Returns the run's directory, or None if it timed out."""
    d = os.path.join(workDir, f'run{runId}')
    shutil.rmtree(d, ignore_errors=True)
    os.makedirs(d)
    shutil.copy(snapshot, os.path.join(d, 'floosball.db'))
    db = os.path.join(d, 'floosball.db')

    env = dict(os.environ, DATABASE_DIR=d, PORT=str(BASE_PORT + runId))
    log = open(os.path.join(d, 'log.txt'), 'w')
    proc = subprocess.Popen([sys.executable, 'run_api.py', '--timing=fast'],
                            cwd=REPO, env=env, stdout=log, stderr=subprocess.STDOUT,
                            start_new_session=True)

    deadline = time.time() + timeoutSecs
    try:
        while time.time() < deadline:
            if proc.poll() is not None:
                break                     # died on its own; extract whatever landed
            if bowlIsFinal(db, season):
                return d
            time.sleep(3)
        return None
    finally:
        # ⚠️ Kill the PROCESS GROUP. run_api's season loop is an asyncio task that
        # survives a plain terminate on the parent often enough to leave orphans
        # holding CPU for the rest of the suite.
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            time.sleep(1)
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
        log.close()


def extract(dbPath, season):
    c = readOnly(dbPath)
    q = c.execute
    teams = {t: n for t, n in q("SELECT id, name FROM teams")}
    wins = Counter(); losses = Counter(); ties = Counter()
    for h, a, hs, asc in q("SELECT home_team_id, away_team_id, home_score, away_score "
                           "FROM games WHERE season=? AND is_playoff=0 AND status='final'", (season,)):
        if hs > asc:
            wins[h] += 1; losses[a] += 1
        elif asc > hs:
            wins[a] += 1; losses[h] += 1
        else:
            ties[h] += 1; ties[a] += 1

    bowl = q("SELECT home_team_id, away_team_id, home_score, away_score FROM games "
             "WHERE season=? AND is_playoff=1 AND playoff_round='4' AND status='final'",
             (season,)).fetchone()
    c.close()
    if not bowl:
        return None
    h, a, hs, asc = bowl
    homeWon = hs > asc
    return {
        'champion': teams[h] if homeWon else teams[a],
        'runnerUp': teams[a] if homeWon else teams[h],
        'score': f"{max(hs, asc)}-{min(hs, asc)}",
        'wins': {teams[t]: wins[t] for t in teams},
        'gamesPerTeam': sorted({wins[t] + losses[t] + ties[t] for t in teams}),
    }


def report(results, season, out=sys.stdout):
    p = lambda s='': print(s, file=out)
    n = len(results)
    p(f"SEASON {season} PRESEASON FORECAST — {n} runs\n")

    p("FLOOS BOWL BY RUN")
    for i, r in enumerate(results, 1):
        p(f"  {i:3d}  {r['champion']:16s} def. {r['runnerUp']:16s} {r['score']}")

    p("\nTITLE ODDS")
    champs = Counter(r['champion'] for r in results)
    for t, c in champs.most_common():
        p(f"  {t:16s} {c:3d}  {100 * c / n:5.1f}%")

    p("\nREACHED THE BOWL")
    apps = Counter()
    for r in results:
        apps[r['champion']] += 1
        apps[r['runnerUp']] += 1
    for t, c in apps.most_common(10):
        p(f"  {t:16s} {c:3d}  {100 * c / n:5.1f}%")

    p(f"\nAVERAGE WINS ({n} runs)")
    teams = sorted(results[0]['wins'])
    rows = []
    for t in teams:
        w = [r['wins'][t] for r in results]
        rows.append((t, statistics.mean(w), statistics.pstdev(w), min(w), max(w),
                     champs.get(t, 0)))
    rows.sort(key=lambda r: -r[1])
    p(f"  {'TEAM':17s} {'AVG':>5s} {'SD':>5s} {'MIN':>4s} {'MAX':>4s} {'TITLES':>7s}")
    for t, m, s, lo, hi, ch in rows:
        p(f"  {t:17s} {m:5.1f} {s:5.2f} {lo:4d} {hi:4d} {ch:7d}")

    allWins = [w for r in results for w in r['wins'].values()]
    p(f"\n  league mean {statistics.mean(allWins):.2f} "
      f"(a sanity check: every game has one winner, so this is fixed by the schedule)")
    p(f"  team averages span {rows[0][1]:.1f} to {rows[-1][1]:.1f}")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--db', required=True, help='season-start snapshot (a COPY of prod)')
    ap.add_argument('--season', type=int, required=True, help='season number to forecast')
    ap.add_argument('--runs', type=int, default=25)
    ap.add_argument('--parallel', type=int, default=5,
                    help='concurrent sims; each pins about one core')
    ap.add_argument('--work', default='/tmp/floo_preseason')
    ap.add_argument('--timeout', type=int, default=600, help='seconds per run')
    ap.add_argument('--json', help='also write the raw per-run results here')
    ap.add_argument('--allow-any-state', action='store_true')
    ap.add_argument('--keep', action='store_true', help='keep each run database')
    args = ap.parse_args()

    info = inspectSnapshot(args.db, args.season)
    print(f"snapshot: integrity={info['integrity']} sim=season {info['simSeason']} "
          f"week {info['simWeek']} | {info['teams']} teams, {info['rostered']} rostered")
    print(f"season {args.season}: {info['scheduled']} scheduled, {info['played']} already played")

    problems = []
    if info['integrity'] != 'ok':
        problems.append("the database fails its integrity check")
    if info['played']:
        problems.append(f"season {args.season} already has {info['played']} finished games, "
                        "so the runs would not start level")
    if not info['scheduled']:
        problems.append(f"season {args.season} has no schedule yet; the runs would each "
                        "generate their own and diverge before week 1")
    if problems and not args.allow_any_state:
        for p in problems:
            print(f"  REFUSING: {p}")
        print("  (--allow-any-state to override)")
        return 2

    os.makedirs(args.work, exist_ok=True)
    results, failed = [], []
    pending = list(range(1, args.runs + 1))
    started = time.time()

    while pending:
        batch, pending = pending[:args.parallel], pending[args.parallel:]
        import concurrent.futures as cf
        with cf.ThreadPoolExecutor(max_workers=len(batch)) as ex:
            futures = {ex.submit(runOne, r, args.db, args.season, args.work, args.timeout): r
                       for r in batch}
            for fut in cf.as_completed(futures):
                r = futures[fut]
                d = fut.result()
                res = extract(os.path.join(d, 'floosball.db'), args.season) if d else None
                if res:
                    results.append(res)
                    print(f"  run {r:3d}: {res['champion']} def. {res['runnerUp']} {res['score']}")
                else:
                    failed.append(r)
                    print(f"  run {r:3d}: FAILED (timeout or no Floos Bowl)")
                if d and not args.keep:
                    shutil.rmtree(d, ignore_errors=True)
        print(f"  -- {len(results)}/{args.runs} complete, {time.time() - started:.0f}s elapsed")

    if not results:
        print("no runs produced a Floos Bowl")
        return 1

    # A run whose teams did not all play the same number of games did not simulate a
    # whole season, and averaging it in would quietly drag every total down.
    expected = results[0]['gamesPerTeam']
    odd = [i for i, r in enumerate(results, 1) if r['gamesPerTeam'] != expected]
    if odd:
        print(f"WARNING: runs with an irregular game count: {odd} (expected {expected})")

    print()
    report(results, args.season)
    if failed:
        print(f"\n{len(failed)} run(s) failed: {failed}")
    if args.json:
        with open(args.json, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"\nraw results: {args.json}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
