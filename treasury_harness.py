"""Treasury harness: what does a team's money buy? (docs/TREASURY_PAYROLL_PLAN.md §8)

Two modes, both on a COPY of a prod snapshot.

  project   No sim. Applies the offseason payment run to the snapshot's real treasuries
            (plus a projected season-end deposit) and prints what every team would build,
            beside what the old one-project-a-season rule would have built.

  arms      Plays several seasons from the snapshot, once per run, in `fast` timing, with
            extra treasury income handed to the even-id half of the league before every
            payment run (FLOOS_TREASURY_INJECT). The control arm hands out nothing. The
            even-minus-odd win gap in an arm, less the same gap in the control, is what that
            money buys. Each run is its own process; arms are compared within one league.

    .venv/bin/python treasury_harness.py project --db data/floosball_prod_latest.db
    .venv/bin/python treasury_harness.py arms --db data/floosball_prod_latest.db \\
        --seasons 3 --runs 6 --inject 0,10000,30000

⚠️ COMPARE ARMS ON THE SAME LEAGUE, NEVER ACROSS TEAMS. Roster quality leaves +-3-8 wins of
residual per team a season, so a regression of wins on treasury finds nothing even where
facilities are worth several wins (CLAUDE.md, Facilities Economy). The even/odd split is the
experiment; the real treasuries are background shared by every arm.

⚠️ THE SIM DOES NOT STOP AT A SEASON BOUNDARY, so each run is killed once the last season's
Floos Bowl is final, gated on the Floos Bowl ROW (see tools_preseason.py for why not a count).

⚠️ Payroll and gate revenue do not exist yet. Today this measures facilities alone; the plan's
G1-G6 checks are added here as those phases land.
"""
import argparse
import json
import math
import os
import shutil
import signal
import sqlite3
import statistics
import subprocess
import sys
import tempfile
import time
from collections import defaultdict

REPO = os.path.dirname(os.path.abspath(__file__))
# 8000 is the dev server, 8099 the simcheck, 8100+ the preseason tool.
BASE_PORT = 8200
SCRATCH = os.environ.get('TREASURY_HARNESS_WORK') or os.path.join(tempfile.gettempdir(), 'floo_treasury')


def readOnly(path):
    return sqlite3.connect(f'file:{path}?mode=ro', uri=True)


# ─── project ──────────────────────────────────────────────────────────────────

def projectedDeposits(c):
    """What `_applySeasonEndTax` would collect per team if the season ended now."""
    from constants import DEFAULT_FUNDING_PCT
    out = defaultdict(int)
    for fav, pct, bal in c.execute(
            "SELECT u.favorite_team_id, u.team_funding_pct, COALESCE(c.balance, 0) "
            "FROM users u LEFT JOIN user_currency c ON c.user_id = u.id "
            "WHERE u.favorite_team_id IS NOT NULL"):
        pct = DEFAULT_FUNDING_PCT if pct is None else max(0, min(100, pct))
        if pct and bal > 0:
            out[fav] += math.floor(bal * pct / 100.0)
    return out


def cmdProject(args):
    work = os.path.join(SCRATCH, 'project')
    shutil.rmtree(work, ignore_errors=True)
    os.makedirs(work)
    shutil.copy(args.db, os.path.join(work, 'floosball.db'))
    os.environ['DATABASE_DIR'] = work
    import logging
    logging.disable(logging.INFO)
    sys.path.insert(0, REPO)
    from database.connection import init_db, get_session
    init_db()          # inline migrations + the one-shot ranking backfill, on the copy only
    from database.models import TeamFacility, FacilityProject, TeamTreasury, Team
    from managers import facilitiesManager as FM
    from constants import FACILITY_CATALOG, FACILITY_UPGRADE_COST_SHARES

    c = sqlite3.connect(os.path.join(work, 'floosball.db'))
    season = c.execute("SELECT current_season FROM simulation_state").fetchone()[0]
    try:
        deposits = projectedDeposits(c)
    except sqlite3.Error as e:
        print(f"(no deposit projection: {e})")
        deposits = {}
    c.close()

    s = get_session()
    teams = {t.id: t.name for t in s.query(Team).all()}
    shareUnit = FM.computeShareUnit(s, season - 1)
    keys = list(FACILITY_CATALOG)
    short = {'training': 'TRN', 'locker_room': 'LCK', 'recovery': 'REC', 'scouting': 'SCT', 'stadium': 'STD'}
    print(f"Season {season} offseason payment run, share unit {shareUnit:,.0f}F "
          f"(full level-5 set from zero costs "
          f"{sum(FM.projectCostFloobits(FACILITY_UPGRADE_COST_SHARES[l], shareUnit) for l in range(1, 6)) * len(keys):,}F)\n")
    print(f"  {'TEAM':14s} {'TREASURY':>9s} {'DEPOSIT':>8s}  {'NOW':15s} {'OLD RULE':15s} {'NEW RULE':15s} {'LEFT':>8s} BUILT")
    rows = []
    for tid in sorted(teams):
        facRows = s.query(TeamFacility).filter_by(team_id=tid).all()
        if not facRows:
            continue
        levels = {f.facility_key: f.level for f in facRows}
        fac = [{'key': f.facility_key, 'level': f.level, 'upkeep_funded': f.upkeep_funded or 0} for f in facRows]
        treasury = (s.query(TeamTreasury).filter_by(team_id=tid).first().balance or 0) + deposits.get(tid, 0)
        # The old rule: upkeep, then only the projects fans voted open, oldest first, and an
        # open project's facility had its upkeep waived.
        voted = s.query(FacilityProject).filter_by(team_id=tid, status='open').order_by(
            FacilityProject.opened_season, FacilityProject.id).all()
        oldProj = [{'id': p.id, 'facility_key': p.facility_key, 'target_level': p.target_level,
                    'cost_shares': p.cost_shares, 'funded': p.funded or 0} for p in voted]
        old = FM.resolvePaymentRun(fac, oldProj, treasury, shareUnit,
                                   order=[p['facility_key'] for p in oldProj],
                                   waivedKeys={p['facility_key'] for p in oldProj})
        # The new rule: every facility open, the fans' ranked order.
        funded = {p.facility_key: p.funded or 0 for p in voted}
        newProj = [{'id': i, 'facility_key': k, 'target_level': levels.get(k, 0) + 1,
                    'cost_shares': FACILITY_UPGRADE_COST_SHARES[min(5, levels.get(k, 0) + 1)],
                    'funded': funded.get(k, 0)}
                   for i, k in enumerate(keys) if levels.get(k, 0) < 5]
        order = FM.teamOrder(s, tid, levels)
        new = FM.resolvePaymentRun(fac, newProj, treasury, shareUnit, order=order)
        lv = lambda res: {f['key']: f['level'] for f in res['facilities']}
        fmt = lambda d: ' '.join(str(d.get(k, 0)) for k in keys)
        built = [short[p['facility_key']] for p in new['projects'] if p['built']]
        rows.append((tid, sum(lv(new).values()) - sum(levels.values())))
        print(f"  {teams[tid][:14]:14s} {treasury - deposits.get(tid, 0):9,d} {deposits.get(tid, 0):8,d}  "
              f"{fmt(levels):15s} {fmt(lv(old)):15s} {fmt(lv(new)):15s} {new['leftover']:8,d} {' '.join(built)}")
    print(f"\n  levels listed as {' '.join(short[k] for k in keys)}")
    gained = [g for _, g in rows]
    print(f"  net levels gained this offseason: total {sum(gained)}, "
          f"teams gaining 3+: {sum(g >= 3 for g in gained)}, gaining 0 or less: {sum(g <= 0 for g in gained)}")
    s.close()
    if not args.keep:
        shutil.rmtree(work, ignore_errors=True)


# ─── arms ─────────────────────────────────────────────────────────────────────

def snapshotState(db):
    c = readOnly(db)
    row = c.execute("SELECT current_season, current_week, in_offseason FROM simulation_state").fetchone()
    c.close()
    return row


def bowlIsFinal(db, season):
    try:
        c = readOnly(db)
        r = c.execute("SELECT status FROM games WHERE season=? AND is_playoff=1 "
                      "AND playoff_round='4'", (season,)).fetchone()
        c.close()
        return bool(r and r[0] == 'final')
    except Exception:
        return False


def readLevels(db):
    """{teamId: {facility: level}} and {teamId: treasury}, or None mid-write."""
    try:
        c = readOnly(db)
        lv = defaultdict(dict)
        for t, k, l in c.execute("SELECT team_id, facility_key, level FROM team_facilities"):
            lv[t][k] = l
        tr = dict(c.execute("SELECT team_id, balance FROM team_treasury").fetchall())
        season = c.execute("SELECT current_season FROM simulation_state").fetchone()[0]
        c.close()
        return season, dict(lv), tr
    except Exception:
        return None


def runOne(label, runId, port, snapshot, lastSeason, inject, timeoutSecs):
    d = os.path.join(SCRATCH, f'{label}_run{runId}')
    shutil.rmtree(d, ignore_errors=True)
    os.makedirs(d)
    db = os.path.join(d, 'floosball.db')
    shutil.copy(snapshot, db)
    env = dict(os.environ, DATABASE_DIR=d, PORT=str(port), FLOOS_TREASURY_INJECT=inject)
    log = open(os.path.join(d, 'log.txt'), 'w')
    proc = subprocess.Popen([sys.executable, 'run_api.py', '--timing=fast'], cwd=REPO, env=env,
                            stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    levelsBySeason = {}
    deadline = time.time() + timeoutSecs
    ok = False
    try:
        while time.time() < deadline:
            if proc.poll() is not None:
                break
            snap = readLevels(db)
            if snap and snap[0] not in levelsBySeason:
                # The FIRST view of each season: the payment run happens in that season's
                # offseason (which runs under the same number), so a later view would show
                # levels the season was not played at.
                levelsBySeason[snap[0]] = (snap[1], snap[2])
            if bowlIsFinal(db, lastSeason):
                ok = True
                break
            time.sleep(3)
    finally:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            time.sleep(1)
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
        log.close()
    if not ok:
        return None, d
    c = readOnly(db)
    wins = defaultdict(lambda: defaultdict(int))
    playoffs = defaultdict(set)
    for season, h, a, hs, asc, po in c.execute(
            "SELECT season, home_team_id, away_team_id, home_score, away_score, is_playoff "
            "FROM games WHERE status='final' AND season>=?", (min(levelsBySeason) if levelsBySeason else 0,)):
        if po:
            playoffs[season].update((h, a))
            continue
        if hs > asc:
            wins[season][h] += 1
        elif asc > hs:
            wins[season][a] += 1
        else:
            wins[season][h] += 0.5
            wins[season][a] += 0.5
    errors = sum(1 for line in open(os.path.join(d, 'log.txt'), errors='ignore')
                 if ' - ERROR - ' in line or 'Traceback' in line)
    c.close()
    return {
        'wins': {s: dict(w) for s, w in wins.items()},
        'playoffs': {s: sorted(p) for s, p in playoffs.items()},
        'levels': {s: lv for s, (lv, tr) in levelsBySeason.items()},
        'treasury': {s: tr for s, (lv, tr) in levelsBySeason.items()},
        'errors': errors,
    }, d


def cmdArms(args):
    state = snapshotState(args.db)
    startSeason = state[0]
    lastSeason = startSeason + args.seasons - 1
    print(f"snapshot: season {state[0]} week {state[1]} offseason={bool(state[2])}; "
          f"playing through season {lastSeason}")
    arms = [int(x) for x in args.inject.split(',')]
    jobs = [(amt, r) for amt in arms for r in range(1, args.runs + 1)]
    results = defaultdict(list)
    os.makedirs(SCRATCH, exist_ok=True)
    started = time.time()
    import concurrent.futures as cf
    with cf.ThreadPoolExecutor(max_workers=args.parallel) as ex:
        futs = {}
        for i, (amt, r) in enumerate(jobs):
            inject = f"even={amt},odd=0" if amt else ''
            futs[ex.submit(runOne, f"inj{amt}", r, BASE_PORT + i, args.db, lastSeason, inject,
                           args.timeout * args.seasons)] = (amt, r)
        for fut in cf.as_completed(futs):
            amt, r = futs[fut]
            res, d = fut.result()
            if res:
                results[amt].append(res)
                print(f"  arm {amt:>6}F run {r}: done, {res['errors']} error lines "
                      f"({time.time() - started:.0f}s)")
            else:
                print(f"  arm {amt:>6}F run {r}: FAILED (timeout or died), log kept at {d}")
                continue
            if not args.keep:
                shutil.rmtree(d, ignore_errors=True)
    if args.json:
        with open(args.json, 'w') as f:
            json.dump({str(k): v for k, v in results.items()}, f)
    reportArms(results, startSeason, lastSeason)


def _gap(res, season):
    """Even-minus-odd mean regular-season wins in one run's season."""
    w = res['wins'].get(season) or res['wins'].get(str(season)) or {}
    w = {int(k): v for k, v in w.items()}
    ev = [v for t, v in w.items() if t % 2 == 0]
    od = [v for t, v in w.items() if t % 2 == 1]
    if not ev or not od:
        return None
    return statistics.mean(ev) - statistics.mean(od)


def _levelGap(res, season):
    lv = res['levels'].get(season) or res['levels'].get(str(season)) or {}
    tot = {int(t): sum(v.values()) for t, v in lv.items()}
    ev = [v for t, v in tot.items() if t % 2 == 0]
    od = [v for t, v in tot.items() if t % 2 == 1]
    if not ev or not od:
        return None, None
    return statistics.mean(ev), statistics.mean(od)


def _ms(xs):
    xs = [x for x in xs if x is not None]
    if not xs:
        return float('nan'), float('nan')
    m = statistics.mean(xs)
    se = statistics.stdev(xs) / math.sqrt(len(xs)) if len(xs) > 1 else float('nan')
    return m, se


def reportArms(results, startSeason, lastSeason):
    seasons = list(range(startSeason, lastSeason + 1))
    control = results.get(0, [])
    print("\nEVEN-MINUS-ODD REGULAR-SEASON WINS (mean +- standard error over runs)")
    print("  The control arm's gap is the league's own even/odd difference; an arm's effect is "
          "its gap minus the control's.\n")
    hdr = ''.join(f"{'S' + str(s):>22s}" for s in seasons)
    print(f"  {'ARM':>8s} {'RUNS':>4s}{hdr}")
    base = {s: _ms([_gap(r, s) for r in control])[0] for s in seasons}
    for amt in sorted(results):
        cells = ''
        for s in seasons:
            m, se = _ms([_gap(r, s) for r in results[amt]])
            eff = m - base[s] if amt and not math.isnan(base[s]) else None
            cells += f"{m:+7.2f}+-{se:4.2f}" + (f" ({eff:+5.2f})" if eff is not None else ' ' * 8)
        print(f"  {amt:>7}F {len(results[amt]):>4d}{cells}")
    print("\n  (in parentheses: the effect over control, in wins per 28-game season)")

    print("\nTOTAL FACILITY LEVELS, EVEN vs ODD (out of 25, season it was played at)")
    for amt in sorted(results):
        cells = ''
        for s in seasons:
            pairs = [_levelGap(r, s) for r in results[amt]]
            ev = [p[0] for p in pairs if p[0] is not None]
            od = [p[1] for p in pairs if p[1] is not None]
            cells += (f"{statistics.mean(ev):10.1f} vs {statistics.mean(od):4.1f}  " if ev and od else ' ' * 22)
        print(f"  {amt:>7}F     {cells}")

    print("\nMEAN TREASURY, EVEN vs ODD (at the start of each season)")
    for amt in sorted(results):
        cells = ''
        for s in seasons:
            ev, od = [], []
            for r in results[amt]:
                tr = r['treasury'].get(s) or r['treasury'].get(str(s)) or {}
                for t, b in tr.items():
                    (ev if int(t) % 2 == 0 else od).append(b)
            cells += (f"{statistics.mean(ev):10,.0f} vs {statistics.mean(od):6,.0f}" if ev and od else ' ' * 20)
        print(f"  {amt:>7}F     {cells}")

    errs = sum(r['errors'] for rs in results.values() for r in rs)
    print(f"\n  error lines across all runs: {errs}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('project')
    p.add_argument('--db', required=True)
    p.add_argument('--keep', action='store_true')
    a = sub.add_parser('arms')
    a.add_argument('--db', required=True)
    a.add_argument('--seasons', type=int, default=3, help='seasons to play, counting the current one')
    a.add_argument('--runs', type=int, default=6, help='runs per arm')
    a.add_argument('--inject', default='0,10000,30000',
                   help='comma-separated Floobits handed to each even-id team before every payment run; 0 is the control')
    a.add_argument('--parallel', type=int, default=8)
    a.add_argument('--timeout', type=int, default=900, help='seconds per season per run')
    a.add_argument('--json')
    a.add_argument('--keep', action='store_true')
    args = ap.parse_args()
    return cmdProject(args) if args.cmd == 'project' else cmdArms(args)


if __name__ == '__main__':
    sys.exit(main() or 0)
