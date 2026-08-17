"""Season-2 multi-sim: resume from the prod snapshot N times under CURRENT code.

Captures each run's S2 regular-season record, Floos Bowl champion, scoring, and the
per-team-game SACK DISTRIBUTION.

The seed snapshot has season 1 final (champion: Strangers) and every offseason step
marked complete, with `simulation_state.current_season = 2, current_week = 0`. So each
run starts season 2 from the SAME rosters prod has — only game outcomes vary between runs.

⚠️ SACKS ARE REPORTED AS A DISTRIBUTION, NOT A MEAN. The 2026-08-14 retune
(`SACK_PROB_CAP` 30 -> 16, `SACK_CURVE_STEEPNESS` 0.12) left the league average alone on
purpose — the average was already on target and the TAIL was the fault. Reading a mean
back would say nothing about whether that landed, and a mean can be held while the spread
is broken in either direction. p90/p99/max and the p90:p10 ratio are the numbers to watch.

Usage:
  run:    s2_multisim.py run <n> <parallel> <port_base> <out_json>
  report: s2_multisim.py report <out_json>
"""
import os, sys, time, json, shutil, subprocess, sqlite3
from collections import Counter

REPO = os.path.dirname(os.path.abspath(__file__))
SRC = os.environ.get('S2_SEED') or os.path.join(REPO, 'data', 'prod-pull', 'season2-seed.db')
VENV_PY = os.path.join(REPO, '.venv', 'bin', 'python')
SEASON = 2
REG_GAMES = 28
RUN_TIMEOUT_SECS = 3600
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

    # Per-team-game sacks. Each game yields two team-games; keep regular season and
    # playoffs separate so a 15-game playoff tail cannot skew the season distribution.
    reg = c.execute("select home_sacks, away_sacks from games "
                    "where status='final' and season=? and coalesce(is_playoff,0)=0", (SEASON,)).fetchall()
    post = c.execute("select home_sacks, away_sacks from games "
                     "where status='final' and season=? and is_playoff=1", (SEASON,)).fetchall()
    grows = c.execute("select home_score, away_score from games where status='final' and season=?",
                      (SEASON,)).fetchall()
    champId = c.execute('select champion_team_id from seasons where season_number=?', (SEASON,)).fetchone()[0]
    c.close()

    sackTeamGames = [s for pair in reg for s in pair if s is not None]
    postSacks = [s for pair in post for s in pair if s is not None]
    teampts = [h for h, a in grows] + [a for h, a in grows]
    return {'wins': wins, 'losses': losses, 'pf': pf, 'pa': pa, 'made': made,
            'champion': names.get(champId),
            'sackTeamGames': sackTeamGames, 'postSackTeamGames': postSacks,
            'avgTeamPts': sum(teampts) / len(teampts) if teampts else 0,
            'nGames': len(grows)}


def runBatch(n, parallel, portBase, outJson):
    if not os.path.exists(SRC):
        sys.exit(f'seed db not found: {SRC}  (set S2_SEED=/path/to/seed.db)')
    workroot = os.path.join(WORKROOT_BASE, f'floo_s2_{portBase}')
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
                    sk = res['sackTeamGames']
                    print(f"  run {len(results)}/{n} done ({time.time()-t0:.0f}s): "
                          f"champ {res['champion']}  avgPts {res['avgTeamPts']:.1f}  "
                          f"games {res['nGames']}  sacks/team {sum(sk)/len(sk):.2f}", flush=True)
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


def _pct(sortedVals, p):
    if not sortedVals:
        return 0.0
    k = (len(sortedVals) - 1) * (p / 100.0)
    lo, hi = int(k), min(int(k) + 1, len(sortedVals) - 1)
    return sortedVals[lo] + (sortedVals[hi] - sortedVals[lo]) * (k - lo)


def report(outJson):
    import statistics
    results = json.load(open(outJson))
    n = len(results)
    teams = set().union(*[r['wins'].keys() for r in results])
    nTeams = len(teams)
    avgW = {t: sum(r['wins'].get(t, 0) for r in results) / n for t in teams}
    sdW = {t: statistics.pstdev([r['wins'].get(t, 0) for r in results]) for t in teams}
    rngW = {t: (min(r['wins'].get(t, 0) for r in results),
                max(r['wins'].get(t, 0) for r in results)) for t in teams}
    pfg = {t: sum(r['pf'].get(t, 0) for r in results) / n / REG_GAMES for t in teams}
    pag = {t: sum(r['pa'].get(t, 0) for r in results) / n / REG_GAMES for t in teams}
    playoff = {t: sum(1 for r in results if r['made'].get(t)) / n for t in teams}
    champ = Counter(r['champion'] for r in results)

    print(f"\n=== SEASON {SEASON} — {n} runs from the prod snapshot, current code ===")
    print(f"{'Team':<18}{'AvgW':>6}{'SD':>5}{'Range':>9}{'Plyf%':>7}{'Titles':>8}{'Ttl%':>6}{'PF/g':>7}{'PA/g':>7}")
    for t in sorted(teams, key=lambda x: -avgW[x]):
        lo, hi = rngW[t]
        titles = champ.get(t, 0)
        print(f"{t:<18}{avgW[t]:>6.1f}{sdW[t]:>5.1f}{f'{lo}-{hi}':>9}{playoff[t]*100:>6.0f}%"
              f"{titles:>8}{titles/n*100:>5.0f}%{pfg[t]:>7.1f}{pag[t]:>7.1f}")

    winvals = list(avgW.values())
    print(f"\n--- PARITY ---")
    print(f"Avg-win spread (best-worst): {max(winvals)-min(winvals):.1f} wins   "
          f"std dev across teams: {statistics.pstdev(winvals):.1f}")
    print(f"Distinct Floos Bowl champions: {len(champ)}/{nTeams} teams over {n} runs")
    print(f"Title favorites: " + ", ".join(f"{t} {c/n*100:.0f}%" for t, c in champ.most_common(5)))

    print(f"\n--- FLOOS BOWL WINNERS ---")
    for t, c in champ.most_common():
        print(f"  {t:<18}{c:>4}  ({c/n*100:.0f}%)")

    allSacks = sorted(s for r in results for s in r['sackTeamGames'])
    post = sorted(s for r in results for s in r['postSackTeamGames'])
    print(f"\n--- SACKS (regular season, {len(allSacks)} team-games) ---")
    print(f"per team per game   mean {sum(allSacks)/len(allSacks):.2f}   "
          f"combined/game {2*sum(allSacks)/len(allSacks):.2f}")
    p10, p50, p90, p99 = (_pct(allSacks, p) for p in (10, 50, 90, 99))
    print(f"p10 {p10:.0f}   p50 {p50:.0f}   p90 {p90:.0f}   p99 {p99:.0f}   max {allSacks[-1]}")
    print(f"p90:p10 spread {(p90/p10 if p10 else float('inf')):.1f}x")
    hi = sum(1 for s in allSacks if s >= 8)
    print(f"team-games at 8+ sacks: {hi} ({hi/len(allSacks)*100:.2f}%)   "
          f"at 10+: {sum(1 for s in allSacks if s >= 10)}")
    if post:
        print(f"playoffs ({len(post)} team-games): mean {sum(post)/len(post):.2f}  max {max(post)}")

    avgPts = sum(r['avgTeamPts'] for r in results) / n
    print(f"\n--- SCORING ---")
    print(f"Avg team points/game: {avgPts:.1f}   combined/game: {2*avgPts:.1f}")


if __name__ == '__main__':
    if sys.argv[1] == 'run':
        runBatch(int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]), sys.argv[5])
    elif sys.argv[1] == 'report':
        report(sys.argv[2])
