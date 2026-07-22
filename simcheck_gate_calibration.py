"""Calibrate per-card gate stats to a common difficulty.

Owner design: the stat that gates a card should VARY (FP, total yards,
completions, YAC, ...) so cards diversify. The hazard is uneven difficulty — a
gate clearing 80% of weeks and one clearing 30% make two cards unequal for
reasons unrelated to their effect.

Fix: author gates as PERCENTILES of the real stat distribution. Pick the pass
rate once, let each stat's displayed threshold fall out of the data.

Step 1 measures the pass rate of the gate that tested best (card player's week
FP >= 75% of their own season average) across EVERY player-week in the season,
not just week 14. Step 2 finds, for each position and candidate stat, the
threshold hitting that same rate.

Read-only, straight SQL — no app boot needed.
"""
import json, sqlite3, statistics
from collections import defaultdict

DB = 'data/floosball_prod_latest.db'
db = sqlite3.connect(DB)
db.row_factory = sqlite3.Row
cur = db.cursor()

season = cur.execute("select max(season) s from weekly_player_fp").fetchone()['s']
POS_NAMES = {1: 'QB', 2: 'RB', 3: 'WR', 4: 'TE', 5: 'K'}  # DB is 1-based
pos = {r['id']: r['position'] for r in cur.execute("select id, position from players")}

# ── weekly FP per player-week
fp = defaultdict(dict)   # pid -> {week: fp}
for r in cur.execute("select player_id, week, fantasy_points from weekly_player_fp "
                     "where season=?", (season,)):
    fp[r['player_id']][r['week']] = r['fantasy_points'] or 0.0

# ── STEP 1: pass rate of the own-average gate, all weeks
RATIO = 0.75
passes = total = 0
for pid, weeks in fp.items():
    played = [v for v in weeks.values() if v > 0]
    if len(played) < 4:
        continue
    avg = statistics.mean(played)
    for w, v in weeks.items():
        if v <= 0:
            continue           # did not play; gate is moot
        total += 1
        if v >= RATIO * avg:
            passes += 1
targetRate = passes / max(total, 1)
print(f"season {season} · {total} player-weeks with production")
print(f"gate 'week FP >= {RATIO} x own season average' passes "
      f"{passes}/{total} = {100*targetRate:.1f}% of the time")
print(f"\nCalibrating every other gate stat to that same {100*targetRate:.0f}% pass rate.\n")

# ── STEP 2: per-position stat distributions
STATS = {   # keys are 1-BASED DB positions
    1: [('passing', 'yards', 'pass yards'), ('passing', 'comp', 'completions'),
        ('passing', 'att', 'attempts'), ('passing', 'tds', 'pass TDs'),
        ('passing', 'longest', 'longest pass'), ('passing', '20+', '20+ yd passes')],
    2: [('rushing', 'yards', 'rush yards'), ('rushing', 'carries', 'carries'),
        ('rushing', 'tds', 'rush TDs'), ('rushing', 'longest', 'longest run'),
        ('rushing', '20+', '20+ yd runs')],
    3: [('receiving', 'yards', 'rec yards'), ('receiving', 'receptions', 'receptions'),
        ('receiving', 'yac', 'YAC'), ('receiving', 'targets', 'targets'),
        ('receiving', 'tds', 'rec TDs'), ('receiving', 'longest', 'longest catch')],
    4: [('receiving', 'yards', 'rec yards'), ('receiving', 'receptions', 'receptions'),
        ('receiving', 'yac', 'YAC'), ('receiving', 'tds', 'rec TDs')],
    5: [('kicking', 'fgs', 'FGs made'), ('kicking', 'fgAtt', 'FG attempts'),
        ('kicking', 'fgYards', 'FG yards'), ('kicking', 'longest', 'longest FG'),
        ('kicking', 'fg40+', 'FGs 40+')],
}
COL = {'passing': 'passing_stats', 'rushing': 'rushing_stats',
       'receiving': 'receiving_stats', 'kicking': 'kicking_stats'}

vals = defaultdict(list)   # (pos, group, key) -> [values over player-weeks]
q = ("select gps.player_id pid, gps.passing_stats p, gps.rushing_stats r, "
     "gps.receiving_stats c, gps.kicking_stats k "
     "from game_player_stats gps join games g on g.id = gps.game_id "
     "where g.season = ?")
for row in cur.execute(q, (season,)):
    p = pos.get(row['pid'])
    if p is None or p not in STATS:
        continue
    if (fp.get(row['pid'], {}) or {}) == {}:
        continue
    blobs = {'passing': row['p'], 'rushing': row['r'],
             'receiving': row['c'], 'kicking': row['k']}
    for group, key, _label in STATS[p]:
        raw = blobs[group]
        if not raw:
            continue
        try:
            d = json.loads(raw) if isinstance(raw, str) else raw
        except Exception:
            continue
        if not isinstance(d, dict):
            continue
        v = d.get(key)
        if isinstance(v, (int, float)):
            vals[(p, group, key)].append(float(v))

def thresholdFor(series, rate):
    """Smallest whole threshold T where >= `rate` of the series is >= T."""
    if not series:
        return None
    s = sorted(series, reverse=True)
    idx = min(len(s) - 1, int(rate * len(s)))
    return s[idx]

for p in sorted(STATS):
    print(f"━━ {POS_NAMES[p]}")
    print(f"   {'gate stat':18} {'threshold':>10} {'actual pass':>12} {'median':>8} {'max':>7}")
    for group, key, label in STATS[p]:
        series = vals.get((p, group, key)) or []
        if len(series) < 30:
            print(f"   {label:18} {'(thin data)':>10}")
            continue
        t = thresholdFor(series, targetRate)
        # round to something a card can print
        t = int(t) if t >= 10 else round(t, 1)
        actual = sum(1 for v in series if v >= t) / len(series)
        print(f"   {label:18} {t:>10} {100*actual:>11.0f}% "
              f"{statistics.median(series):>8.0f} {max(series):>7.0f}")
    print()
print("Each row is a DIFFERENT gate with the SAME difficulty, so the stat is flavour\n"
      "rather than power. Thresholds are season-13 values and want recomputing per season.")
