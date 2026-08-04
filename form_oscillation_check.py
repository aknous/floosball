"""Day-level form-variance harness for the team form oscillation layer.

The question: does a club's level MOVE across a season, or does it play at one
fixed strength for 28 weeks? Splits each team's regular season into four equal
blocks (the four game days) and measures the sd of its wins across them.

  baseline before the layer existed   1.13
  pure coin-flip reference            1.32  (computed per-run below)
  target                              1.6-1.9

Also reports corr(block-1 wins, final wins), win spread and champion
concentration — the guardrails. This is a VARIANCE change, not a parity change:
if the win spread collapses, the amplitude is too high.

  form_oscillation_check.py run <leagues> <seasons> <portBase> <outJson>
  form_oscillation_check.py report <outJson> [<outJson> ...]

FLOOS_FORM=off in the environment runs the control arm.
"""
import os, sys, time, json, shutil, subprocess, sqlite3, statistics
from collections import defaultdict, Counter

REPO = os.path.dirname(os.path.abspath(__file__))
VENV_PY = os.path.join(REPO, '.venv', 'bin', 'python')
WORKROOT_BASE = os.environ.get('CLAUDE_JOB_DIR') or '/tmp'
LEAGUE_TIMEOUT_SECS = 5400
NBLOCKS = 4


def _seasonsDone(db):
    try:
        c = sqlite3.connect(f'file:{db}?mode=ro', uri=True)
        n = c.execute('select count(*) from seasons '
                      'where champion_team_id is not null').fetchone()[0]
        c.close()
        return n
    except Exception:
        return 0


def _readLeague(db, maxSeason):
    """Per (season, team): wins in each of the four game-day blocks."""
    c = sqlite3.connect(f'file:{db}?mode=ro', uri=True)
    champs = {s: t for s, t in c.execute(
        'select season_number, champion_team_id from seasons '
        'where champion_team_id is not null')}
    scoring = []               # every team-game's points, for distribution checks
    games = defaultdict(list)  # season -> [(week, home, away, hs, as)]
    for season, week, h, a, hs, ascore in c.execute(
            'select season, week, home_team_id, away_team_id, home_score, away_score '
            'from games where status="final" and is_playoff=0'):
        if hs is None or ascore is None:
            continue
        games[season].append((week, h, a, hs, ascore))
        scoring += [hs, ascore]
    c.close()

    out = []
    for season in sorted(games):
        if season not in champs or season > maxSeason:
            continue
        rows = games[season]
        weeks = sorted({r[0] for r in rows})
        if len(weeks) < NBLOCKS * 2:
            continue
        # Split the regular season's weeks into NBLOCKS contiguous blocks.
        size = len(weeks) / NBLOCKS
        blockOf = {w: min(NBLOCKS - 1, int(i // size)) for i, w in enumerate(weeks)}
        blockWins = defaultdict(lambda: [0] * NBLOCKS)
        blockGames = defaultdict(lambda: [0] * NBLOCKS)
        seq = defaultdict(list)  # team -> [(week, 1|0)] for streak / swing analysis
        for week, h, a, hs, ascore in rows:
            b = blockOf[week]
            blockGames[h][b] += 1
            blockGames[a][b] += 1
            if hs > ascore:
                blockWins[h][b] += 1
            else:
                blockWins[a][b] += 1
            seq[h].append((week, 1 if hs > ascore else 0))
            seq[a].append((week, 1 if ascore > hs else 0))
        out.append({
            'season': season,
            'champion': champs[season],
            'scoring': scoring if season == sorted(games)[0] else [],
            'teams': {str(t): {'wins': blockWins[t], 'games': blockGames[t],
                               'seq': [r for _, r in sorted(seq[t])]}
                      for t in blockWins},
        })
    return out


def runBatch(leagues, seasons, portBase, outJson):
    workroot = os.path.join(WORKROOT_BASE, f'floo_form_{portBase}')
    shutil.rmtree(workroot, ignore_errors=True)
    os.makedirs(workroot, exist_ok=True)
    active, done = {}, []

    def launch(idx):
        port = portBase + idx
        dbdir = os.path.join(workroot, f'lg{idx}')
        os.makedirs(dbdir, exist_ok=True)
        env = dict(os.environ, DATABASE_DIR=dbdir, PORT=str(port), TIMING_MODE='fast')
        logf = open(os.path.join(dbdir, 'sim.log'), 'w')
        proc = subprocess.Popen([VENV_PY, 'run_api.py', '--fresh', '--timing=fast'],
                                cwd=REPO, env=env, stdout=logf, stderr=logf)
        active[port] = (proc, dbdir, idx, time.time())

    arm = 'CONTROL (form off)' if os.environ.get('FLOOS_FORM') == 'off' else 'FORM ON'
    print(f"form check [{arm}]: {leagues} leagues x {seasons} seasons", flush=True)
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
                print(f"  league {idx}: {n}/{seasons} ({time.time()-t0:.0f}s)", flush=True)
            if not (n >= seasons or proc.poll() is not None
                    or time.time() - started > LEAGUE_TIMEOUT_SECS):
                continue
            if n >= 1:
                try:
                    done.append(_readLeague(db, min(n, seasons)))
                    print(f"  league {idx} read at {n} seasons "
                          f"({time.time()-t0:.0f}s)", flush=True)
                except Exception as e:
                    print(f"  league {idx} read error: {e}", flush=True)
            proc.kill()
            try:
                proc.wait(timeout=10)
            except Exception:
                pass
            del active[port]
            shutil.rmtree(dbdir, ignore_errors=True)
    shutil.rmtree(workroot, ignore_errors=True)
    json.dump(done, open(outJson, 'w'))
    print(f"Wrote {len(done)} leagues -> {outJson}", flush=True)


def _coinFlipReference(blockGames):
    """Expected sd-across-blocks if every game were a coin flip, for the actual
    block sizes seen. sd of a Binomial(n, .5) count is sqrt(n)/2; the sd across
    four such blocks is dominated by that per-block spread."""
    import math
    sims = []
    for games in blockGames:
        # analytic: population sd of 4 independent Binomial(n_b, .5) draws
        var = sum((g / 4.0) for g in games) / len(games)
        sims.append(math.sqrt(var))
    return statistics.mean(sims) if sims else float('nan')


def report(paths):
    for path in paths:
        leagues = json.load(open(path))
        seasonRows = [s for lg in leagues for s in lg]
        formSds, block1, finals, spreads, champs, allBlockGames = [], [], [], [], [], []
        for s in seasonRows:
            wins = {}
            for tid, d in s['teams'].items():
                bw = d['wins']
                wins[tid] = sum(bw)
                formSds.append(statistics.pstdev(bw))
                allBlockGames.append(d['games'])
                block1.append(bw[0])
                finals.append(sum(bw))
            if wins:
                spreads.append(max(wins.values()) - min(wins.values()))
            champs.append(s['champion'])

        arm = os.path.basename(path)
        print(f"\n=== {arm} ===")
        print(f"{len(leagues)} leagues, {len(seasonRows)} seasons, "
              f"{len(formSds)} team-seasons")
        if not formSds:
            print("  no data")
            continue
        ref = _coinFlipReference(allBlockGames)
        print(f"  form variance (sd of wins across the 4 game days): "
              f"{statistics.mean(formSds):.2f}")
        print(f"  coin-flip reference for these block sizes:         {ref:.2f}")
        print(f"  teams flatter than sd 1.0: "
              f"{100*sum(1 for x in formSds if x < 1.0)/len(formSds):.0f}%")
        try:
            print(f"  corr(block-1 wins, final wins):                   "
                  f"{statistics.correlation(block1, finals):+.3f}")
        except Exception:
            pass
        print(f"  avg win spread:                                   "
              f"{statistics.mean(spreads):.1f}")
        pts = [p for s in seasonRows for p in (s.get('scoring') or [])]
        if pts:
            n = len(pts)
            print(f"  scoring: {2*statistics.mean(pts):.1f} combined/game   "
                  f"shutouts {100*sum(1 for p in pts if p==0)/n:.1f}%   "
                  f"<=3pts {100*sum(1 for p in pts if p<=3)/n:.1f}%   "
                  f"40+ {100*sum(1 for p in pts if p>=40)/n:.1f}%   "
                  f"({n} team-games)")
        cc = Counter(champs)
        print(f"  distinct champions: {len(cc)} over {len(champs)} seasons "
              f"(most titles by one club: {max(cc.values())})")
        _narrative(seasonRows)


def _longestRun(seq, value):
    best = cur = 0
    for r in seq:
        cur = cur + 1 if r == value else 0
        best = max(best, cur)
    return best


def _narrative(seasonRows):
    """Does the variance actually take the SHAPE of an arc? Block-win sd is only a
    proxy — it rises for week-to-week jitter too. These are the things a user would
    actually narrate: long runs, a big swing between phases of the season, and
    teams that genuinely turned a season around or threw one away."""
    winRuns, lossRuns, swings = [], [], []
    turnarounds = collapses = teamSeasons = 0
    for s in seasonRows:
        totals = {t: sum(d['wins']) for t, d in s['teams'].items()}
        order = sorted(totals, key=lambda t: -totals[t])
        rank = {t: i for i, t in enumerate(order)}
        n = len(order)
        early = sorted(s['teams'], key=lambda t: -s['teams'][t]['wins'][0])
        earlyRank = {t: i for i, t in enumerate(early)}
        for t, d in s['teams'].items():
            seq = d.get('seq') or []
            if not seq:
                continue
            teamSeasons += 1
            winRuns.append(_longestRun(seq, 1))
            lossRuns.append(_longestRun(seq, 0))
            rates = [w / g for w, g in zip(d['wins'], d['games']) if g]
            if rates:
                swings.append(max(rates) - min(rates))
            # bottom half after the opening block -> top quarter by season end
            if earlyRank[t] >= n / 2 and rank[t] < n / 4:
                turnarounds += 1
            # top quarter after the opening block -> bottom half by season end
            if earlyRank[t] < n / 4 and rank[t] >= n / 2:
                collapses += 1
    if not teamSeasons:
        return
    print(f"  --- arc shape (is the variance actually a STORY?) ---")
    print(f"  longest win streak (avg / max):   "
          f"{statistics.mean(winRuns):.2f} / {max(winRuns)}   "
          f"[coin-flip ~4.7 for 28 games]")
    print(f"  longest losing streak (avg):      {statistics.mean(lossRuns):.2f}")
    print(f"  best-to-worst game-day win% swing:{statistics.mean(swings):.3f}")
    print(f"  turnarounds (bottom half after day 1 -> top quarter): "
          f"{100*turnarounds/teamSeasons:.1f}% of team-seasons")
    print(f"  collapses  (top quarter after day 1 -> bottom half): "
          f"{100*collapses/teamSeasons:.1f}%")


if __name__ == '__main__':
    if sys.argv[1] == 'run':
        runBatch(int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]), sys.argv[5])
    else:
        report(sys.argv[2:])
