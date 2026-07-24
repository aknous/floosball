"""Season-13 multi-sim: resume from the end-of-S12 prod snapshot N times, capture
each run's S13 regular-season wins per team + Floos Bowl champion + awakened count.
Attention/awakenings are carried from the real prod state (sticky across seasons).

Usage:
  run:    s13_multisim.py run <n> <parallel> <port_base> <out_json>
  report: s13_multisim.py report <out_json>
"""
import os, sys, time, json, shutil, subprocess, sqlite3
from collections import Counter

REPO = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(REPO, 'data', '_s13_seed_src.db')
VENV_PY = os.path.join(REPO, '.venv', 'bin', 'python')
SEASON = 13

def _done(db):
    try:
        c = sqlite3.connect(db)
        r = c.execute('select champion_team_id from seasons where season_number=?', (SEASON,)).fetchone()
        c.close()
        return bool(r and r[0] is not None)
    except Exception:
        return False

def _readResult(db):
    c = sqlite3.connect(db)
    names = {r[0]: r[1] for r in c.execute('select id, name from teams')}
    wins = {names[t]: w for t, w in c.execute('select team_id, wins from team_season_stats where season=?', (SEASON,))}
    losses = {names[t]: l for t, l in c.execute('select team_id, losses from team_season_stats where season=?', (SEASON,))}
    pf = {names[t]: p for t, p in c.execute('select team_id, points from team_season_stats where season=?', (SEASON,))}
    pa = {names[t]: p for t, p in c.execute('select team_id, points_allowed from team_season_stats where season=?', (SEASON,))}
    champId = c.execute('select champion_team_id from seasons where season_number=?', (SEASON,)).fetchone()[0]
    awk = c.execute("select count(*) from anomaly_state where season=? and state='awakened'", (SEASON,)).fetchone()[0]
    ramp = c.execute("select count(*) from anomaly_state where season=? and state='rampant'", (SEASON,)).fetchone()[0]
    c.close()
    return {'wins': wins, 'losses': losses, 'pf': pf, 'pa': pa,
            'champion': names.get(champId), 'awakened': awk, 'rampant': ramp}

def runBatch(n, parallel, portBase, outJson):
    workroot = f'/tmp/floo_s13_{portBase}'
    shutil.rmtree(workroot, ignore_errors=True); os.makedirs(workroot, exist_ok=True)
    results, active, launched = [], {}, 0
    def launch(idx):
        port = portBase + idx
        dbdir = os.path.join(workroot, f'run{idx}'); os.makedirs(dbdir, exist_ok=True)
        shutil.copy(SRC, os.path.join(dbdir, 'floosball.db'))
        env = dict(os.environ, DATABASE_DIR=dbdir, PORT=str(port), TIMING_MODE='fast')
        logf = open(os.path.join(dbdir, 'sim.log'), 'w')
        proc = subprocess.Popen([VENV_PY, 'run_api.py', '--timing=fast'], cwd=REPO, env=env, stdout=logf, stderr=logf)
        active[port] = (proc, dbdir, idx)
    print(f"Batch: n={n} parallel={parallel} portBase={portBase}", flush=True)
    while launched < min(parallel, n):
        launch(launched); launched += 1
    t0 = time.time()
    while active:
        time.sleep(4)
        for port in list(active):
            proc, dbdir, idx = active[port]
            db = os.path.join(dbdir, 'floosball.db')
            if _done(db):
                try:
                    res = _readResult(db); results.append(res)
                    print(f"  run {len(results)}/{n} done ({time.time()-t0:.0f}s): champ {res['champion']}  awakened {res['awakened']} rampant {res['rampant']}", flush=True)
                except Exception as e:
                    print(f"  run idx{idx} read error: {e}", flush=True)
                proc.kill()
                try: proc.wait(timeout=10)
                except Exception: pass
                del active[port]; shutil.rmtree(dbdir, ignore_errors=True)
                if launched < n:
                    launch(launched); launched += 1
    shutil.rmtree(workroot, ignore_errors=True)
    json.dump(results, open(outJson, 'w'))
    print(f"Wrote {len(results)} runs -> {outJson}", flush=True)

def report(outJson):
    results = json.load(open(outJson))
    n = len(results)
    teams = set().union(*[r['wins'].keys() for r in results])
    avgW = {t: sum(r['wins'].get(t, 0) for r in results)/n for t in teams}
    G = 28.0  # regular-season games per team
    pfg = {t: sum(r.get('pf', {}).get(t, 0) for r in results)/n/G for t in teams}   # points for / game
    pag = {t: sum(r.get('pa', {}).get(t, 0) for r in results)/n/G for t in teams}   # points against / game
    champ = Counter(r['champion'] for r in results)
    print(f"\n=== SEASON 13 — {n} runs ===")
    print(f"{'Team':<15}{'Avg W':>7}{'Avg L':>7}{'Titles':>8}{'Title%':>7}{'PF/g':>7}{'PA/g':>7}")
    for t in sorted(teams, key=lambda x: -avgW[x]):
        w = avgW[t]; titles = champ.get(t, 0)
        print(f"{t:<15}{w:>7.1f}{28-w:>7.1f}{titles:>8}{titles/n*100:>6.0f}%{pfg[t]:>7.1f}{pag[t]:>7.1f}")
    fav = max(teams, key=lambda x: avgW[x])
    topT = champ.most_common(1)[0]
    print(f"\nFavorite (record): {fav} ({avgW[fav]:.1f}-{28-avgW[fav]:.1f})")
    print(f"Most titles: {topT[0]} ({topT[1]}/{n} = {topT[1]/n*100:.0f}%)")
    # League scoring
    leaguePFg = sum(pfg.values())/len(teams)
    print(f"\nLEAGUE SCORING: {leaguePFg:.1f} pts/team/game   ({2*leaguePFg:.1f} combined/game)")
    print(f"  highest-scoring: {max(teams,key=lambda x:pfg[x])} ({max(pfg.values()):.1f}/g)   "
          f"best defense: {min(teams,key=lambda x:pag[x])} ({min(pag.values()):.1f} allowed/g)")
    aw = sum(r['awakened'] for r in results)/n; rm = sum(r['rampant'] for r in results)/n
    print(f"Avg awakened players/run: {aw:.1f}   rampant: {rm:.1f}")
    print(f"\nFloos Bowl winners by run: {dict(champ)}")

if __name__ == '__main__':
    if sys.argv[1] == 'run':
        runBatch(int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]), sys.argv[5])
    elif sys.argv[1] == 'report':
        report(sys.argv[2])
