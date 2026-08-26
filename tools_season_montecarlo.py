"""Monte Carlo one SEASON: replay it from its start N independent times.

Answers "who is actually favoured", which a single run cannot — measured on season 3, the
mean within-team spread is 2.1 wins, so any two teams inside ~2 wins of each other are
indistinguishable in one playthrough. Produces the favorites board in
`docs/SEASONn_PREDICTIONS.md`.

    mkdir -p /tmp/mc/pristine && cd /tmp/mc/pristine
    fly ssh sftp get /data/floosball.db ./floosball.db -a floosball-api
    python tools_season_montecarlo.py --base /tmp/mc --season 3 --runs 20 --parallel 5

⚠️ START FROM A SEASON THAT IS SCHEDULED BUT UNPLAYED, or the runs share history: every
game already `final` in the snapshot is identical in all of them and the spread collapses.
Check with `SELECT COUNT(*) FROM games WHERE season=? AND status='final'` before trusting a
board.

⚠️ EACH RUN NEEDS ITS OWN DATABASE **AND** ITS OWN PORT. `run_api.py` reads `DATABASE_DIR`
and `PORT` from the environment; sharing either makes the second run fail to bind or, worse,
write into the first one's league.

⚠️ Runs are killed as soon as a floosbowl row exists for the season, and their 171MB
database is deleted immediately after extraction, so disk stays flat regardless of N.

⚠️ 20 runs puts the standard error on a mean win total near ±0.5 and on a title share near
±10 points. Report win averages confidently; report titles as "who is live".
"""
import argparse

import json, os, shutil, sqlite3, subprocess, time

_p = argparse.ArgumentParser(description=__doc__)
_p.add_argument('--base', required=True, help='working dir holding pristine/floosball.db')
_p.add_argument('--season', type=int, required=True)
_p.add_argument('--runs', type=int, default=20)
_p.add_argument('--parallel', type=int, default=5)
_p.add_argument('--repo', default=os.path.dirname(os.path.abspath(__file__)))
_p.add_argument('--port-base', type=int, default=8100)
_a = _p.parse_args()

BASE, SEASON, RUNS, PARALLEL, REPO = _a.base, _a.season, _a.runs, _a.parallel, _a.repo
PRISTINE = os.path.join(BASE, 'pristine', 'floosball.db')
RESULTS = os.path.join(BASE, 'results.json')
TIMEOUT = 900   # per run


def champion(db):
    try:
        c = sqlite3.connect(db)
        row = c.execute("SELECT team_id FROM championships WHERE season=? "
                        "AND championship_type='floosbowl'", (SEASON,)).fetchone()
        c.close()
        return row[0] if row else None
    except Exception:
        return None


def extract(db, runId):
    c = sqlite3.connect(db)
    c.row_factory = sqlite3.Row
    champ = c.execute("SELECT team_id FROM championships WHERE season=? "
                      "AND championship_type='floosbowl'", (SEASON,)).fetchone()
    wins = {r['team_id']: r['wins'] for r in c.execute(
        "SELECT team_id, wins FROM team_season_stats WHERE season=?", (SEASON,))}
    made = [r['team_id'] for r in c.execute(
        "SELECT DISTINCT home_team_id team_id FROM games WHERE season=? AND is_playoff=1 "
        "UNION SELECT DISTINCT away_team_id FROM games WHERE season=? AND is_playoff=1",
        (SEASON, SEASON))]
    c.close()
    return {'run': runId, 'champion': champ[0] if champ else None,
            'wins': wins, 'playoffs': made}


def launch(runId):
    d = os.path.join(BASE, f'run{runId}')
    os.makedirs(os.path.join(d, 'data'), exist_ok=True)
    db = os.path.join(d, 'data', 'floosball.db')
    shutil.copyfile(PRISTINE, db)
    env = dict(os.environ, DATABASE_DIR=os.path.join(d, 'data'),
               PORT=str(_a.port_base + runId))
    log = open(os.path.join(d, 'sim.log'), 'w')
    p = subprocess.Popen([os.path.join(REPO, '.venv/bin/python'), 'run_api.py', '--timing=fast'],
                         cwd=REPO, env=env, stdout=log, stderr=subprocess.STDOUT)
    return {'id': runId, 'proc': p, 'db': db, 'dir': d, 'log': log, 'start': time.time()}


results = []
if os.path.exists(RESULTS):
    results = json.load(open(RESULTS))
done = {r['run'] for r in results}

pending = [i for i in range(RUNS) if i not in done]
active = []
while pending or active:
    while pending and len(active) < PARALLEL:
        active.append(launch(pending.pop(0)))
        time.sleep(3)          # stagger the boots so they do not fight over the CPU
    time.sleep(10)
    for run in list(active):
        finished = champion(run['db']) is not None
        timedout = time.time() - run['start'] > TIMEOUT
        if not (finished or timedout):
            continue
        if finished:
            results.append(extract(run['db'], run['id']))
            json.dump(results, open(RESULTS, 'w'))
        run['proc'].terminate()
        try:
            run['proc'].wait(timeout=20)
        except Exception:
            run['proc'].kill()
        run['log'].close()
        shutil.rmtree(run['dir'], ignore_errors=True)
        active.remove(run)
        print(f"run {run['id']}: {'done' if finished else 'TIMED OUT'} "
              f"({time.time()-run['start']:.0f}s)  [{len(results)}/{RUNS}]", flush=True)

print(f"complete: {len(results)} runs -> {RESULTS}", flush=True)
