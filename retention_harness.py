"""Retention harness — model what fans would do each offseason (re-sign the best
players you're allowed to, let the rest walk) and show it working.

Runs a fresh fast sim with RETENTION_DEBUG on so every team's re-sign decision is
logged, then reports:
  1. Sample re-sign decisions — which players (by rating) each team KEPT as its
     best-N-eligible, and who walked (roster/count limit vs re-signed-max limit).
  2. A correctness check that no walked-for-space player out-rated a kept one
     (i.e. teams really did keep their best eligible).
  3. The resulting league parity + churn (champion spread, roster fullness,
     re-sign vs walk volume, average tenure).

Usage:  python retention_harness.py [seasons=12] [port=8790]
"""
import os, sys, time, subprocess, shutil, sqlite3, re
from collections import Counter

REPO = os.path.dirname(os.path.abspath(__file__))
VENV = os.path.join(REPO, '.venv', 'bin', 'python')
if not os.path.exists(VENV):
    VENV = 'python3'


def _ratings(s):
    return [int(x) for x in re.findall(r'\((\d+)\)', s)] if s and s != '-' else []


def report(work, db):
    # Skip the duplicate `INFO:`-prefixed lines (the sim logs to two handlers).
    log = "\n".join(ln for ln in open(os.path.join(work, 'sim.log')).read().splitlines()
                    if not ln.startswith('INFO:'))
    decisions = re.findall(
        r'RESIGN\[(.+?)\] kept: (.+?) \| walk\(not-resigned\): (.+?) \| walk\(re-sign-limit\): (.+)',
        log)

    print("\n=== SAMPLE RE-SIGN DECISIONS (kept the best eligible, let the rest walk) ===")
    shown = 0
    for team, kept, cwalk, rwalk in decisions:
        if (cwalk != '-' or rwalk != '-') and shown < 12:   # only the interesting ones (someone walked)
            print(f"  {team}: re-signed {kept}")
            if cwalk != '-':
                print(f"      let walk (not re-signed): {cwalk}")
            if rwalk != '-':
                print(f"      let walk (already re-signed max): {rwalk}")
            shown += 1

    # Correctness: a player walked for SPACE should never out-rate a kept player.
    # (re-sign-limit walks are excluded — those are forced out regardless of rating.)
    checks = viol = 0
    for team, kept, cwalk, rwalk in decisions:
        kr, cw = _ratings(kept), _ratings(cwalk)
        if kr and cw:
            checks += 1
            if min(kr) < max(cw):
                viol += 1
                print(f"  [!] {team}: kept {kept} but let {cwalk} walk — a better player walked")
    print(f"\n  best-eligible correctness: {checks - viol}/{checks} space decisions kept the top-rated "
          f"(violations={viol})")
    totalKept = sum(len(_ratings(d[1])) for d in decisions)
    totalWalk = sum(len(_ratings(d[2])) + len(_ratings(d[3])) for d in decisions)
    print(f"  total across sim: {totalKept} re-signs, {totalWalk} walks")

    c = sqlite3.connect(f'file:{db}?mode=ro', uri=True, timeout=6)
    names = {r[0]: r[1] for r in c.execute('SELECT id,name FROM teams')}
    champs = [ch for s, ch in c.execute(
        'SELECT season_number,champion_team_id FROM seasons WHERE champion_team_id IS NOT NULL ORDER BY season_number')]
    cc = Counter(champs)
    streak = cur = 1
    for i in range(1, len(champs)):
        cur = cur + 1 if champs[i] == champs[i-1] else 1
        streak = max(streak, cur)
    rows = c.execute("SELECT COUNT(p.id) n FROM teams t LEFT JOIN players p ON p.team_id=t.id "
                     "AND p.is_prospect=0 AND p.is_upcoming_rookie=0 AND (p.service_time IS NULL OR "
                     "p.service_time!='Retired') GROUP BY t.id").fetchall()
    tenure = c.execute("SELECT AVG(team_resign_count) FROM players WHERE is_prospect=0 AND "
                       "is_upcoming_rookie=0 AND (service_time IS NULL OR service_time!='Retired')").fetchone()[0]
    print(f"\n=== LEAGUE RESULT ({len(champs)} seasons) ===")
    print(f"  parity: {len(cc)} distinct champions, top team {cc.most_common(1)[0][1] if cc else 0} titles, "
          f"longest streak {streak}")
    print(f"  champions: {' '.join(names.get(ch, '?')[:8] for ch in champs)}")
    print(f"  rosters full: {sum(1 for r in rows if r[0]==6)}/{len(rows)}")
    print(f"  avg re-signs per player with current team: {tenure:.2f}")
    c.close()


def run(seasons, port):
    work = f'/tmp/floo_retention_{port}'
    shutil.rmtree(work, ignore_errors=True)
    os.makedirs(work)
    env = dict(os.environ, DATABASE_DIR=work, PORT=str(port), TIMING_MODE='fast',
               RETENTION_DEBUG='1', SIMULATE_FAN_RESIGNS='1')
    logf = open(os.path.join(work, 'sim.log'), 'w')
    proc = subprocess.Popen([VENV, 'run_api.py', '--fresh', '--timing=fast'],
                            cwd=REPO, env=env, stdout=logf, stderr=logf)
    db = os.path.join(work, 'floosball.db')
    print(f"Running fresh sim to season {seasons} (RETENTION_DEBUG on)...", flush=True)
    t0 = time.time()
    try:
        while True:
            time.sleep(8)
            if proc.poll() is not None:
                print("  sim process exited early", flush=True)
                break
            try:
                c = sqlite3.connect(f'file:{db}?mode=ro', uri=True, timeout=4)
                s = c.execute('SELECT MAX(season_number) FROM seasons').fetchone()[0] or 0
                c.close()
            except Exception:
                s = 0
            if s >= seasons:
                break
            if time.time() - t0 > 1200:
                print("  20min cap hit", flush=True)
                break
    finally:
        proc.kill()
        try:
            proc.wait(timeout=10)
        except Exception:
            pass
    report(work, db)
    shutil.rmtree(work, ignore_errors=True)


if __name__ == '__main__':
    seasons = int(sys.argv[1]) if len(sys.argv) > 1 else 12
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 8790
    run(seasons, port)
