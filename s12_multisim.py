"""Season-12 multi-sim: resume from the end-of-S11 prod snapshot N times, capture
each run's S12 regular-season wins per team + Floos Bowl champion.

Each run copies the prod DB to its own throwaway dir and runs `run_api --timing=fast`
(resume) from the given ENGINE DIRECTORY (so we can A/B the current engine vs a
baseline git worktree), polling until S12's champion is set, then killing it.

Usage:
  run:     s12_multisim.py run <engine_dir> <n> <parallel> <port_base> <out_json>
  compare: s12_multisim.py compare <baseline_json> <current_json>
"""
import os, sys, time, json, shutil, subprocess, sqlite3

REPO = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(REPO, 'data', 'floosball_prod_latest.db')
VENV_PY = os.path.join(REPO, '.venv', 'bin', 'python')

# Stored preseason predictions (docs/SEASON12_PREDICTIONS.md, 2026-06-28, old engine)
PREDICTED = {
    'Strangers': 25.0, 'Pinecones': 20.9, 'Oysters': 20.5, 'Sand Dollars': 20.3,
    'Caddies': 20.0, 'Phones': 18.4, 'Cranes': 18.3, 'Bachelorettes': 17.7,
    'Classics': 17.7, 'Rhyme': 17.3, 'Babies': 15.9, 'Slippers': 14.7,
    'Melons': 14.3, 'Drivers': 13.9, 'Broads': 13.9, 'Beans': 12.9,
    'Moonlight': 12.6, 'Blouses': 10.3, 'Normals': 9.8, 'Dry Heat': 8.5,
    'Residents': 6.3, 'Jetskis': 2.9, 'Lattes': 2.7, 'Rocks': 0.9,
}
ACTUAL = {  # actual prod S12 (old engine)
    'Strangers': 26, 'Oysters': 22, 'Sand Dollars': 22, 'Pinecones': 20, 'Phones': 20,
    'Caddies': 19, 'Bachelorettes': 19, 'Rhyme': 18, 'Classics': 17, 'Broads': 17,
    'Cranes': 16, 'Babies': 16, 'Melons': 16, 'Drivers': 15, 'Blouses': 13, 'Moonlight': 12,
    'Slippers': 11, 'Beans': 9, 'Normals': 9, 'Dry Heat': 5, 'Lattes': 5, 'Residents': 4,
    'Jetskis': 3, 'Rocks': 2,
}


def _s12Done(dbpath):
    try:
        c = sqlite3.connect(dbpath)
        r = c.execute('select champion_team_id from seasons where season_number=12').fetchone()
        c.close()
        return bool(r and r[0] is not None)
    except Exception:
        return False


def _readResult(dbpath):
    c = sqlite3.connect(dbpath)
    names = {r[0]: r[1] for r in c.execute('select id, name from teams')}
    wins = {names[t]: w for t, w in c.execute('select team_id, wins from team_season_stats where season=12')}
    champId = c.execute('select champion_team_id from seasons where season_number=12').fetchone()[0]
    # League scoring aggregates (per team-game; a full season = 28 games/team).
    row = c.execute("""select count(*), sum(points), sum(passing_yards), sum(rushing_yards),
                              sum(passing_tds), sum(rushing_tds), sum(field_goals),
                              sum(sacks), sum(interceptions)
                       from team_season_stats where season=12""").fetchone()
    nteams = row[0] or 24
    tg = nteams * 28.0  # team-games
    agg = {
        'ptsPerTeamGame': (row[1] or 0) / tg,
        'passYdsPerTeamGame': (row[2] or 0) / tg,
        'rushYdsPerTeamGame': (row[3] or 0) / tg,
        'passTD': row[4] or 0, 'rushTD': row[5] or 0,
        'fgPerTeamGame': (row[6] or 0) / tg,
        'sackPerTeamGame': (row[7] or 0) / tg,
        'intPerTeamGame': (row[8] or 0) / tg,
    }
    c.close()
    return {'wins': wins, 'champion': names.get(champId), 'agg': agg}


def runBatch(engineDir, n, parallel, portBase, outJson):
    workroot = f'/tmp/floo_s12_{portBase}'
    shutil.rmtree(workroot, ignore_errors=True)
    os.makedirs(workroot, exist_ok=True)
    results, active, launched = [], {}, 0

    def launch(idx):
        port = portBase + idx
        dbdir = os.path.join(workroot, f'run{idx}')
        os.makedirs(dbdir, exist_ok=True)
        shutil.copy(SRC, os.path.join(dbdir, 'floosball.db'))
        for ext in ('wal', 'shm'):
            s = SRC + '-' + ext
            if os.path.exists(s):
                shutil.copy(s, os.path.join(dbdir, 'floosball.db-' + ext))
        env = dict(os.environ, DATABASE_DIR=dbdir, PORT=str(port), TIMING_MODE='fast')
        logf = open(os.path.join(dbdir, 'sim.log'), 'w')
        proc = subprocess.Popen([VENV_PY, 'run_api.py', '--timing=fast'],
                                cwd=engineDir, env=env, stdout=logf, stderr=logf)
        active[port] = (proc, dbdir, idx)

    print(f"Batch: engine={engineDir}  n={n} parallel={parallel}", flush=True)
    while launched < min(parallel, n):
        launch(launched); launched += 1
    while active:
        time.sleep(4)
        for port in list(active):
            proc, dbdir, idx = active[port]
            dbpath = os.path.join(dbdir, 'floosball.db')
            if _s12Done(dbpath):
                try:
                    res = _readResult(dbpath); results.append(res)
                    print(f"  run {len(results)}/{n} done: champ {res['champion']}", flush=True)
                except Exception as e:
                    print(f"  run idx{idx} read error: {e}", flush=True)
                proc.kill()
                try: proc.wait(timeout=10)
                except Exception: pass
                del active[port]
                shutil.rmtree(dbdir, ignore_errors=True)
                if launched < n:
                    launch(launched); launched += 1
    shutil.rmtree(workroot, ignore_errors=True)
    with open(outJson, 'w') as f:
        json.dump(results, f)
    print(f"Wrote {len(results)} runs -> {outJson}", flush=True)


def _avg(results):
    teams = set().union(*[r['wins'].keys() for r in results])
    return {t: sum(r['wins'].get(t, 0) for r in results) / len(results) for t in teams}


def _champCounts(results):
    from collections import Counter
    return Counter(r['champion'] for r in results)


def compare(baselineJson, currentJson):
    base = json.load(open(baselineJson))
    curr = json.load(open(currentJson))
    aBase, aCurr = _avg(base), _avg(curr)
    order = sorted(PREDICTED, key=lambda t: -PREDICTED[t])
    print(f"\nSEASON 12 — predicted vs re-run avg regular-season wins (of 28)")
    print(f"baseline engine = pre-coaching (67e60f3~1), {len(base)} runs; "
          f"current engine = next-season w/ coaching, {len(curr)} runs.\n")
    print(f"  {'Team':<14}{'Pred':>6}{'Actual':>7}{'Base':>7}{'Curr':>7}   {'Curr-Base':>9}{'Curr-Pred':>10}")
    tb = tc = 0.0
    for t in order:
        p = PREDICTED[t]; a = ACTUAL.get(t, float('nan'))
        b = aBase.get(t, float('nan')); c = aCurr.get(t, float('nan'))
        tb += abs(c - b); tc += abs(c - p)
        print(f"  {t:<14}{p:>6.1f}{a:>7.0f}{b:>7.1f}{c:>7.1f}   {c-b:>+9.1f}{c-p:>+10.1f}")
    print(f"\n  Mean |current - baseline| = {tb/len(order):.2f} wins  (coaching-change impact)")
    print(f"  Mean |current - predicted| = {tc/len(order):.2f} wins  (vs stored predictions)")
    baseMAEpred = sum(abs(aBase.get(t, 0) - PREDICTED[t]) for t in order) / len(order)
    print(f"  Mean |baseline - predicted| = {baseMAEpred:.2f} wins  (variance-only: same-era engine vs predictions)")
    print(f"\n  Champions — baseline: {dict(_champCounts(base))}")
    print(f"  Champions — current:  {dict(_champCounts(curr))}")

    # --- Scoring / play-style aggregates ---
    def meanAgg(results, key):
        xs = [r['agg'][key] for r in results if 'agg' in r]
        m = sum(xs) / len(xs)
        se = (sum((x - m) ** 2 for x in xs) / (len(xs) - 1) / len(xs)) ** 0.5 if len(xs) > 1 else 0.0
        return m, se
    print(f"\nSCORING / PLAY-STYLE (per team-game, avg across runs):")
    print(f"  {'metric':<26}{'baseline':>12}{'current':>12}{'Δ (cur-base)':>14}")
    metrics = [
        ('points', 'ptsPerTeamGame', '{:.2f}'), ('pass yards', 'passYdsPerTeamGame', '{:.1f}'),
        ('rush yards', 'rushYdsPerTeamGame', '{:.1f}'), ('field goals', 'fgPerTeamGame', '{:.2f}'),
        ('sacks', 'sackPerTeamGame', '{:.2f}'), ('interceptions', 'intPerTeamGame', '{:.2f}'),
    ]
    for label, key, fmt in metrics:
        mb, sb = meanAgg(base, key); mc, sc = meanAgg(curr, key)
        print(f"  {label:<26}{fmt.format(mb):>12}{fmt.format(mc):>12}{('%+.2f' % (mc - mb)):>14}")
    # run/pass TD mix
    def tdmix(results):
        pt = sum(r['agg']['passTD'] for r in results); rt = sum(r['agg']['rushTD'] for r in results)
        return pt / (pt + rt) * 100, rt / (pt + rt) * 100
    bp, br = tdmix(base); cp, cr = tdmix(curr)
    print(f"  {'TD mix (pass/rush %)':<26}{('%.0f/%.0f' % (bp, br)):>12}{('%.0f/%.0f' % (cp, cr)):>12}")
    # combined points/game for readability
    mb, _ = meanAgg(base, 'ptsPerTeamGame'); mc, _ = meanAgg(curr, 'ptsPerTeamGame')
    print(f"\n  Combined points/game:  baseline {2*mb:.1f}   current {2*mc:.1f}   Δ {2*(mc-mb):+.2f}")


if __name__ == '__main__':
    if sys.argv[1] == 'run':
        _, _, engineDir, n, parallel, portBase, outJson = sys.argv
        runBatch(engineDir, int(n), int(parallel), int(portBase), outJson)
    elif sys.argv[1] == 'compare':
        compare(sys.argv[2], sys.argv[3])
