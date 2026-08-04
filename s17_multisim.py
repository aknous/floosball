"""Season-17 multi-sim: resume from the prod snapshot N times under CURRENT code,
capture each run's S17 regular-season record, Floos Bowl champion, scoring, playoff
berths, awakened counts.

The seed snapshot (data/prod-pull/floosball.db) has season 16 final and every
offseason step already marked complete, so each run starts season 17 with the SAME
rosters prod has — only game outcomes vary between runs.

Usage:
  run:    s17_multisim.py run <n> <parallel> <port_base> <out_json>
  report: s17_multisim.py report <out_json>
"""
import os, sys, time, json, shutil, subprocess, sqlite3
from collections import Counter, defaultdict

REPO = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(REPO, 'data', 'prod-pull', 'floosball.db')  # prod copy, post-offseason
VENV_PY = os.path.join(REPO, '.venv', 'bin', 'python')
SEASON = 17
RUN_TIMEOUT_SECS = 3600  # a single season should never take this long; kill stragglers
WORKROOT_BASE = os.environ.get('CLAUDE_JOB_DIR') or '/tmp'


def _done(db):
    try:
        c = sqlite3.connect(f'file:{db}?mode=ro', uri=True)
        r = c.execute('select champion_team_id from seasons where season_number=?', (SEASON,)).fetchone()
        c.close()
        return bool(r and r[0] is not None)
    except Exception:
        return False


def _readResult(db):
    c = sqlite3.connect(f'file:{db}?mode=ro', uri=True)
    names = {r[0]: r[1] for r in c.execute('select id, name from teams')}
    def col(name):
        return {names[t]: v for t, v in
                c.execute(f'select team_id, {name} from team_season_stats where season=?', (SEASON,))}
    wins, losses = col('wins'), col('losses')
    pf, pa = col('points'), col('points_allowed')
    made = {k: bool(v) for k, v in col('made_playoffs').items()}
    leagueChamp = {k: bool(v) for k, v in col('league_champion').items()}
    grows = c.execute("select home_score, away_score from games where status='final' and season=?",
                      (SEASON,)).fetchall()
    champId = c.execute('select champion_team_id from seasons where season_number=?', (SEASON,)).fetchone()[0]
    awk = c.execute("select count(*) from anomaly_state where season=? and state='awakened'", (SEASON,)).fetchone()[0]
    ramp = c.execute("select count(*) from anomaly_state where season=? and state='rampant'", (SEASON,)).fetchone()[0]
    c.close()
    teampts = [h for h, a in grows] + [a for h, a in grows]
    return {'wins': wins, 'losses': losses, 'pf': pf, 'pa': pa, 'made': made,
            'leagueChamp': leagueChamp, 'champion': names.get(champId),
            'awakened': awk, 'rampant': ramp,
            'avgTeamPts': sum(teampts) / len(teampts) if teampts else 0,
            'nGames': len(grows)}


def runBatch(n, parallel, portBase, outJson):
    workroot = os.path.join(WORKROOT_BASE, f'floo_s17_{portBase}')
    shutil.rmtree(workroot, ignore_errors=True); os.makedirs(workroot, exist_ok=True)
    results, active, launched = [], {}, 0

    def launch(idx):
        port = portBase + idx
        dbdir = os.path.join(workroot, f'run{idx}'); os.makedirs(dbdir, exist_ok=True)
        shutil.copy(SRC, os.path.join(dbdir, 'floosball.db'))
        env = dict(os.environ, DATABASE_DIR=dbdir, PORT=str(port), TIMING_MODE='fast')
        logf = open(os.path.join(dbdir, 'sim.log'), 'w')
        proc = subprocess.Popen([VENV_PY, 'run_api.py', '--timing=fast'],
                                cwd=REPO, env=env, stdout=logf, stderr=logf)
        active[port] = (proc, dbdir, idx, time.time())

    def retire(port, note=None):
        proc, dbdir, idx, _ = active.pop(port)
        proc.kill()
        try: proc.wait(timeout=10)
        except Exception: pass
        if note:
            print(f"  run idx{idx} {note}", flush=True)
        shutil.rmtree(dbdir, ignore_errors=True)

    print(f"Batch: n={n} parallel={parallel} portBase={portBase} src={os.path.basename(SRC)}", flush=True)
    while launched < min(parallel, n):
        launch(launched); launched += 1
    t0 = time.time()
    while active:
        time.sleep(5)
        for port in list(active):
            proc, dbdir, idx, started = active[port]
            db = os.path.join(dbdir, 'floosball.db')
            if _done(db):
                try:
                    res = _readResult(db); results.append(res)
                    print(f"  run {len(results)}/{n} done ({time.time()-t0:.0f}s): "
                          f"champ {res['champion']}  avgPts {res['avgTeamPts']:.1f}  "
                          f"games {res['nGames']}  awakened {res['awakened']}", flush=True)
                except Exception as e:
                    print(f"  run idx{idx} read error: {e}", flush=True)
                retire(port)
            elif proc.poll() is not None:
                retire(port, f"DIED before champion (log kept: {dbdir}/sim.log)")
            elif time.time() - started > RUN_TIMEOUT_SECS:
                retire(port, "TIMED OUT")
            else:
                continue
            if launched < n:
                launch(launched); launched += 1
    shutil.rmtree(workroot, ignore_errors=True)
    json.dump(results, open(outJson, 'w'))
    print(f"Wrote {len(results)} runs -> {outJson}", flush=True)


def report(outJson):
    import statistics
    results = json.load(open(outJson))
    n = len(results)
    teams = set().union(*[r['wins'].keys() for r in results])
    G = 28.0
    avgW = {t: sum(r['wins'].get(t, 0) for r in results) / n for t in teams}
    sdW = {t: statistics.pstdev([r['wins'].get(t, 0) for r in results]) for t in teams}
    rngW = {t: (min(r['wins'].get(t, 0) for r in results),
                max(r['wins'].get(t, 0) for r in results)) for t in teams}
    pfg = {t: sum(r['pf'].get(t, 0) for r in results) / n / G for t in teams}
    pag = {t: sum(r['pa'].get(t, 0) for r in results) / n / G for t in teams}
    playoff = {t: sum(1 for r in results if r['made'].get(t)) / n for t in teams}
    lgFinal = {t: sum(1 for r in results if r.get('leagueChamp', {}).get(t)) / n for t in teams}
    champ = Counter(r['champion'] for r in results)

    print(f"\n=== SEASON {SEASON} — {n} runs (prod snapshot, current code, default rules) ===")
    print(f"{'Team':<16}{'AvgW':>6}{'SD':>5}{'Range':>9}{'Plyf%':>7}{'LgF%':>6}"
          f"{'Titles':>7}{'Ttl%':>6}{'PF/g':>7}{'PA/g':>7}")
    for t in sorted(teams, key=lambda x: -avgW[x]):
        w, titles = avgW[t], champ.get(t, 0)
        lo, hi = rngW[t]
        print(f"{t:<16}{w:>6.1f}{sdW[t]:>5.1f}{f'{lo}-{hi}':>9}{playoff[t]*100:>6.0f}%"
              f"{lgFinal[t]*100:>5.0f}%{titles:>7}{titles/n*100:>5.0f}%{pfg[t]:>7.1f}{pag[t]:>7.1f}")

    winvals = list(avgW.values())
    print(f"\n--- PARITY ---")
    print(f"Avg-win spread (best-worst): {max(winvals)-min(winvals):.1f} wins   "
          f"std dev across teams: {statistics.pstdev(winvals):.1f}")
    print(f"Distinct Floos Bowl champions: {len(champ)}/24 teams over {n} runs")
    print(f"Title favorites: " + ", ".join(f"{t} {c/n*100:.0f}%" for t, c in champ.most_common(5)))

    avgPts = sum(r['avgTeamPts'] for r in results) / n
    print(f"\n--- SCORING ---")
    print(f"Avg team points/game: {avgPts:.1f}   combined/game: {2*avgPts:.1f}")
    print(f"Best offense: {max(teams,key=lambda x:pfg[x])} ({max(pfg.values()):.1f}/g)   "
          f"best defense: {min(teams,key=lambda x:pag[x])} ({min(pag.values()):.1f} allowed/g)")

    aw = sum(r['awakened'] for r in results) / n
    rm = sum(r['rampant'] for r in results) / n
    print(f"\n--- ANOMALY ---")
    print(f"Avg awakened players/run: {aw:.1f}   rampant: {rm:.1f}")
    print(f"\nFloos Bowl winners tally: {dict(champ.most_common())}")


if __name__ == '__main__':
    if sys.argv[1] == 'run':
        runBatch(int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]), sys.argv[5])
    elif sys.argv[1] == 'report':
        report(sys.argv[2])
