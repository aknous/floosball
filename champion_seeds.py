"""Who actually wins the Floos Bowl — and what seed were they?

Seeds are reconstructed per season rather than read from a column:
  * Playoff rounds 1-3 (weeks 29-31) are WITHIN-league, the Floos Bowl (week 32) is
    cross-league. So the teams connected by weeks 29-31 games form that season's two
    leagues — accurate even for seasons before a realignment.
  * Within each league's playoff field, seed = rank by (win_percentage, score_differential)
    descending, which is the sim's own seeding rule.

Usage:
  champion_seeds.py db <sqlite_db> <first_season> <last_season>
  champion_seeds.py json <parity_json>        # leagues captured by fresh_parity_sim
"""
import sys, sqlite3, json
from collections import Counter, defaultdict

PLAYOFF_FIRST_WEEK = 29
BOWL_WEEK = 32


def seedTable(conn, season):
    """-> (list of (team_id, seed) per league, championId) for one season, or None."""
    names = {r[0]: r[1] for r in conn.execute('select id, name from teams')}
    champ = conn.execute('select champion_team_id from seasons where season_number=?',
                         (season,)).fetchone()
    if not champ or champ[0] is None:
        return None
    championId = champ[0]

    # Within-league playoff games only (exclude the cross-league Floos Bowl).
    edges = list(conn.execute(
        "select home_team_id, away_team_id from games "
        "where season=? and week>=? and week<? and status='final'",
        (season, PLAYOFF_FIRST_WEEK, BOWL_WEEK)))
    if not edges:
        return None

    # Connected components over those games = the two leagues' playoff fields.
    adj = defaultdict(set)
    for h, a in edges:
        adj[h].add(a); adj[a].add(h)
    seen, comps = set(), []
    for t in adj:
        if t in seen:
            continue
        stack, comp = [t], []
        while stack:
            x = stack.pop()
            if x in seen:
                continue
            seen.add(x); comp.append(x)
            stack.extend(adj[x] - seen)
        comps.append(comp)

    rec = {t: (wp, sd, w) for t, wp, sd, w in conn.execute(
        'select team_id, win_percentage, score_differential, wins '
        'from team_season_stats where season=?', (season,))}

    leagues = []
    for comp in comps:
        ranked = sorted(comp, key=lambda t: (-(rec.get(t, (0, 0, 0))[0] or 0),
                                             -(rec.get(t, (0, 0, 0))[1] or 0)))
        leagues.append([(t, i + 1) for i, t in enumerate(ranked)])
    return leagues, championId, names, rec


def analyze(rows, label):
    """rows: list of dicts {season, champSeed, champName, champWins, bestRecordWins,
    champHadBestRecord, fieldSize}"""
    n = len(rows)
    if not n:
        print("no seasons resolved"); return
    print(f"\n=== {label} ===")
    print(f"{'Season':>7}{'Seed':>6}{'W':>4}  {'Champion':<16}{'BestRec':>8}  Note")
    for r in rows:
        note = 'top record in league' if r['champSeed'] == 1 else ''
        if r['champOverallBest']:
            note = 'best record in LEAGUE-WIDE'
        print(f"{r['season']:>7}{r['champSeed']:>6}{r['champWins']:>4}  {r['champName']:<16}"
              f"{r['bestRecordWins']:>8}  {note}")
    seeds = Counter(r['champSeed'] for r in rows)
    print(f"\nChampion seed distribution ({n} seasons):")
    for s in sorted(seeds):
        bar = '#' * seeds[s]
        print(f"   seed {s}: {seeds[s]:>3} ({seeds[s]/n*100:>4.0f}%)  {bar}")
    top2 = sum(v for k, v in seeds.items() if k <= 2)
    lower = sum(v for k, v in seeds.items() if k >= 3)
    print(f"\n  Seeds 1-2 (the bye teams): {top2}/{n} ({top2/n*100:.0f}%)")
    print(f"  Seeds 3-6 (no bye):        {lower}/{n} ({lower/n*100:.0f}%)")
    bestRec = sum(1 for r in rows if r['champOverallBest'])
    print(f"  Champion had the league's outright best record: {bestRec}/{n} ({bestRec/n*100:.0f}%)")


def fromDb(db, first, last, label=None):
    c = sqlite3.connect(f'file:{db}?mode=ro', uri=True)
    rows = []
    for season in range(int(first), int(last) + 1):
        res = seedTable(c, season)
        if not res:
            continue
        leagues, championId, names, rec = res
        seed = next((s for lg in leagues for t, s in lg if t == championId), None)
        if seed is None:
            continue
        allWins = {t: v[2] for t, v in rec.items()}
        bestW = max(allWins.values())
        rows.append({'season': season, 'champSeed': seed,
                     'champName': names.get(championId, '?'),
                     'champWins': allWins.get(championId, 0),
                     'bestRecordWins': bestW,
                     'champOverallBest': allWins.get(championId, 0) == bestW})
    c.close()
    analyze(rows, label or f"{db} seasons {first}-{last}")
    return rows


if __name__ == '__main__':
    if sys.argv[1] == 'db':
        fromDb(sys.argv[2], sys.argv[3], sys.argv[4])
    elif sys.argv[1] == 'json':
        data = json.load(open(sys.argv[2]))
        rows = []
        for lg in data:
            for r in lg:
                if r.get('champSeed'):
                    rows.append(r)
        analyze(rows, "Fresh leagues under autonomous FO")
