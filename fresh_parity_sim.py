"""Fresh-league parity check under the autonomous Front Office.

Spins up N independent FRESH leagues (no prod history), runs each for M seasons under
current code with AUTONOMOUS_FO_ENABLED, and measures whether talent concentrates into
super-teams over time.

The question this answers: on prod today, one roster (Dry Heat, 27-1) runs away with the
league. Does a fresh league under the auto-GM stay competitive, or does it re-converge on
the same dynasty shape after a few seasons?

Metrics per season: win spread, win std dev, best team's wins, team-talent spread (avg
roster rating, best vs worst), champion. Across seasons: distinct champions, repeat
titles, and season-over-season win persistence (the real super-team tell — does a team's
record this season predict its record next season?).

Usage:
  run:      fresh_parity_sim.py run <leagues> <seasons> <port_base> <out_json>
  report:   fresh_parity_sim.py report <out_json>
  baseline: fresh_parity_sim.py baseline <prod_db> <first_season> <last_season>
"""
import os, sys, time, json, shutil, subprocess, sqlite3, statistics
from collections import Counter, defaultdict

REPO = os.path.dirname(os.path.abspath(__file__))
VENV_PY = os.path.join(REPO, '.venv', 'bin', 'python')
WORKROOT_BASE = os.environ.get('CLAUDE_JOB_DIR') or '/tmp'
LEAGUE_TIMEOUT_SECS = 5400


def _seasonsDone(db):
    try:
        c = sqlite3.connect(f'file:{db}?mode=ro', uri=True)
        n = c.execute('select count(*) from seasons where champion_team_id is not null').fetchone()[0]
        c.close()
        return n
    except Exception:
        return 0


def _readLeague(db, maxSeason):
    """Per-season team records + reconstructed per-season roster talent."""
    c = sqlite3.connect(f'file:{db}?mode=ro', uri=True)
    names = {r[0]: r[1] for r in c.execute('select id, name from teams')}
    out = []
    champs = {s: t for s, t in
              c.execute('select season_number, champion_team_id from seasons '
                        'where champion_team_id is not null')}
    for season in sorted(champs)[:maxSeason]:
        wins = {names[t]: w for t, w in
                c.execute('select team_id, wins from team_season_stats where season=?', (season,))}
        if not wins:
            continue
        # Team talent that season: average rating of the players who actually played for it.
        talent = defaultdict(list)
        for tid, rating in c.execute(
                """select s.team_id, h.rating
                     from player_season_stats s
                     join player_rating_history h
                       on h.player_id = s.player_id and h.season = s.season
                    where s.season = ? and s.team_id is not null""", (season,)):
            if tid in names:
                talent[names[tid]].append(rating)
        talentAvg = {t: sum(v) / len(v) for t, v in talent.items() if v}
        rec = {'season': season, 'wins': wins, 'talent': talentAvg,
               'champion': names.get(champs[season])}
        # Champion's playoff seed, reconstructed from the bracket (see champion_seeds.py).
        try:
            from champion_seeds import seedTable
            res = seedTable(c, season)
            if res:
                leagues_, championId, nm, recs = res
                seed = next((s for lg in leagues_ for t, s in lg if t == championId), None)
                if seed is not None:
                    allW = {t: v[2] for t, v in recs.items()}
                    bestW = max(allW.values())
                    rec.update({'champSeed': seed, 'champName': nm.get(championId, '?'),
                                'champWins': allW.get(championId, 0),
                                'bestRecordWins': bestW,
                                'champOverallBest': allW.get(championId, 0) == bestW})
        except Exception as e:
            print(f"    seed calc failed S{season}: {e}", flush=True)
        out.append(rec)
    c.close()
    return out


def runBatch(leagues, seasons, portBase, outJson):
    workroot = os.path.join(WORKROOT_BASE, f'floo_parity_{portBase}')
    shutil.rmtree(workroot, ignore_errors=True); os.makedirs(workroot, exist_ok=True)
    active, done = {}, []

    def launch(idx):
        port = portBase + idx
        dbdir = os.path.join(workroot, f'lg{idx}'); os.makedirs(dbdir, exist_ok=True)
        env = dict(os.environ, DATABASE_DIR=dbdir, PORT=str(port), TIMING_MODE='fast')
        logf = open(os.path.join(dbdir, 'sim.log'), 'w')
        proc = subprocess.Popen([VENV_PY, 'run_api.py', '--fresh', '--timing=fast'],
                                cwd=REPO, env=env, stdout=logf, stderr=logf)
        active[port] = (proc, dbdir, idx, time.time())

    print(f"Fresh-league parity: {leagues} leagues x {seasons} seasons (auto-GM)", flush=True)
    for i in range(leagues):
        launch(i)
    t0 = time.time()
    lastReport = {}
    while active:
        time.sleep(10)
        for port in list(active):
            proc, dbdir, idx, started = active[port]
            db = os.path.join(dbdir, 'floosball.db')
            n = _seasonsDone(db)
            if lastReport.get(idx) != n:
                lastReport[idx] = n
                print(f"  league {idx}: {n}/{seasons} seasons ({time.time()-t0:.0f}s)", flush=True)
            finished = n >= seasons
            dead = proc.poll() is not None
            timedout = time.time() - started > LEAGUE_TIMEOUT_SECS
            if not (finished or dead or timedout):
                continue
            if finished:
                try:
                    done.append(_readLeague(db, seasons))
                    print(f"  league {idx} COMPLETE ({time.time()-t0:.0f}s)", flush=True)
                except Exception as e:
                    print(f"  league {idx} read error: {e}", flush=True)
            else:
                print(f"  league {idx} {'DIED' if dead else 'TIMED OUT'} at {n} seasons "
                      f"(log: {dbdir}/sim.log)", flush=True)
                if n >= 2:  # salvage whatever seasons it managed
                    try: done.append(_readLeague(db, n))
                    except Exception: pass
            proc.kill()
            try: proc.wait(timeout=10)
            except Exception: pass
            del active[port]
            shutil.rmtree(dbdir, ignore_errors=True)
    shutil.rmtree(workroot, ignore_errors=True)
    json.dump(done, open(outJson, 'w'))
    print(f"Wrote {len(done)} leagues -> {outJson}", flush=True)


def _seasonMetrics(rec):
    w = list(rec['wins'].values())
    tal = list(rec['talent'].values())
    m = {'season': rec['season'], 'maxW': max(w), 'minW': min(w),
         'spread': max(w) - min(w), 'sd': statistics.pstdev(w),
         'champion': rec['champion'],
         'super': sum(1 for x in w if x >= 24), 'tank': sum(1 for x in w if x <= 4)}
    if tal:
        m['talSpread'] = max(tal) - min(tal)
        m['talSd'] = statistics.pstdev(tal)
    return m


def _persistence(league):
    """Correlation between a team's wins in season N and N+1, pooled over the league.
    High = the same teams stay on top (dynasties). ~0 = the table reshuffles."""
    pairs = []
    byS = {r['season']: r['wins'] for r in league}
    for s in sorted(byS):
        if s + 1 in byS:
            for t, w in byS[s].items():
                if t in byS[s + 1]:
                    pairs.append((w, byS[s + 1][t]))
    if len(pairs) < 8:
        return None
    xs, ys = [p[0] for p in pairs], [p[1] for p in pairs]
    try:
        return statistics.correlation(xs, ys)
    except Exception:
        return None


def report(outJson):
    leagues = json.load(open(outJson))
    print(f"\n=== FRESH LEAGUES UNDER AUTONOMOUS FRONT OFFICE ===")
    print(f"{len(leagues)} independent leagues, "
          f"{sum(len(l) for l in leagues)} season-observations total\n")

    print(f"{'Lg':>3}{'Sn':>4}{'BestW':>7}{'WorstW':>7}{'Spread':>7}{'WinSD':>7}"
          f"{'TalSpr':>8}{'24W+':>6}{'<=4W':>6}  Champion")
    allM = []
    for i, lg in enumerate(leagues):
        for rec in lg:
            m = _seasonMetrics(rec); m['league'] = i; allM.append(m)
            print(f"{i:>3}{m['season']:>4}{m['maxW']:>7}{m['minW']:>7}{m['spread']:>7}"
                  f"{m['sd']:>7.1f}{m.get('talSpread', 0):>8.1f}{m['super']:>6}{m['tank']:>6}"
                  f"  {m['champion']}")

    print(f"\n--- PARITY (pooled across all leagues/seasons) ---")
    def avg(k): return sum(m[k] for m in allM) / len(allM)
    print(f"Avg best-team wins: {avg('maxW'):.1f} / 28      avg worst-team wins: {avg('minW'):.1f}")
    print(f"Avg win spread: {avg('spread'):.1f}          avg win std dev: {avg('sd'):.1f}")
    talM = [m for m in allM if 'talSpread' in m]
    if talM:
        print(f"Avg team-talent spread (best-worst avg roster rating): "
              f"{sum(m['talSpread'] for m in talM)/len(talM):.1f}")
    print(f"Super-teams (24+ wins): {sum(m['super'] for m in allM)} "
          f"({sum(m['super'] for m in allM)/len(allM):.2f} per season)")
    print(f"Doormats (<=4 wins):    {sum(m['tank'] for m in allM)} "
          f"({sum(m['tank'] for m in allM)/len(allM):.2f} per season)")

    print(f"\n--- DYNASTIES ---")
    for i, lg in enumerate(leagues):
        champs = Counter(r['champion'] for r in lg)
        p = _persistence(lg)
        rep = sum(c - 1 for c in champs.values() if c > 1)
        print(f"  league {i}: {len(champs)} distinct champs in {len(lg)} seasons, "
              f"{rep} repeat title(s), win-persistence r={p if p is None else round(p,2)}"
              f"   {dict(champs.most_common(3))}")
    ps = [x for x in (_persistence(l) for l in leagues) if x is not None]
    if ps:
        print(f"\n  Mean season-over-season win persistence: r={sum(ps)/len(ps):.2f}")
        print(f"  (r near 0 = table reshuffles each year; r above ~0.6 = entrenched order)")


def baseline(prodDb, first, last):
    """Same metrics computed on REAL prod seasons, for comparison."""
    c = sqlite3.connect(f'file:{prodDb}?mode=ro', uri=True)
    names = {r[0]: r[1] for r in c.execute('select id, name from teams')}
    league = []
    for season in range(int(first), int(last) + 1):
        wins = {names[t]: w for t, w in
                c.execute('select team_id, wins from team_season_stats where season=?', (season,))}
        if not wins:
            continue
        talent = defaultdict(list)
        for tid, rating in c.execute(
                """select s.team_id, h.rating from player_season_stats s
                     join player_rating_history h
                       on h.player_id = s.player_id and h.season = s.season
                    where s.season = ? and s.team_id is not null""", (season,)):
            if tid in names:
                talent[names[tid]].append(rating)
        ch = c.execute('select champion_team_id from seasons where season_number=?', (season,)).fetchone()
        league.append({'season': season, 'wins': wins,
                       'talent': {t: sum(v)/len(v) for t, v in talent.items() if v},
                       'champion': names.get(ch[0]) if ch else None})
    c.close()
    json.dump([league], open('/dev/stdout', 'w')) if False else None
    print(f"\n=== PROD BASELINE (seasons {first}-{last}, binding fan votes, no auto-GM) ===")
    print(f"{'Sn':>4}{'BestW':>7}{'WorstW':>7}{'Spread':>7}{'WinSD':>7}{'TalSpr':>8}"
          f"{'24W+':>6}{'<=4W':>6}  Champion")
    ms = []
    for rec in league:
        m = _seasonMetrics(rec); ms.append(m)
        print(f"{m['season']:>4}{m['maxW']:>7}{m['minW']:>7}{m['spread']:>7}{m['sd']:>7.1f}"
              f"{m.get('talSpread',0):>8.1f}{m['super']:>6}{m['tank']:>6}  {m['champion']}")
    if ms:
        def avg(k): return sum(m[k] for m in ms) / len(ms)
        talM = [m for m in ms if 'talSpread' in m]
        print(f"\nAvg best-team wins {avg('maxW'):.1f}   avg spread {avg('spread'):.1f}   "
              f"avg win SD {avg('sd'):.1f}   " +
              (f"avg talent spread {sum(m['talSpread'] for m in talM)/len(talM):.1f}" if talM else ""))
        print(f"Super-teams (24+ W): {sum(m['super'] for m in ms)/len(ms):.2f}/season   "
              f"Doormats (<=4 W): {sum(m['tank'] for m in ms)/len(ms):.2f}/season")
        champs = Counter(m['champion'] for m in ms)
        print(f"Distinct champions: {len(champs)} in {len(ms)} seasons  {dict(champs.most_common())}")
        p = _persistence(league)
        print(f"Season-over-season win persistence: r={p if p is None else round(p,2)}")


if __name__ == '__main__':
    if sys.argv[1] == 'run':
        runBatch(int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]), sys.argv[5])
    elif sys.argv[1] == 'report':
        report(sys.argv[2])
    elif sys.argv[1] == 'baseline':
        baseline(sys.argv[2], sys.argv[3], sys.argv[4])
