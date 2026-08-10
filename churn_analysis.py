"""League churn: how long does it take to climb from the cellar to contention, and to
fall from the top back to the bottom?

Tiers are assigned per season by win rank among the 24 teams:
    TOP    = ranks 1-6    (contender)
    MIDDLE = ranks 7-18
    BOTTOM = ranks 19-24  (cellar)

Two first-passage questions:
    * A team is BOTTOM in season S. How many seasons until it is first TOP?
    * A team is TOP in season S. How many seasons until it is first BOTTOM?

Spells that never complete inside the observation window are CENSORED and reported
separately — ignoring them would badly understate the true time (the slowest climbers
are exactly the ones that run off the end of the data).

Usage:
  churn_analysis.py db <sqlite_db> <first_season> <last_season>
  churn_analysis.py json <parity_json> [skip_first_n_seasons]
"""
import sys, sqlite3, json, statistics
from collections import defaultdict, Counter

TIER_SIZE = None  # None = quartile of the league (8 at 32 clubs, 6 at 24)


def tiersFor(wins):
    """wins: {team: wins} -> {team: 'TOP'|'MID'|'BOT'}. Tier = top/bottom quartile."""
    ranked = sorted(wins, key=lambda t: -wins[t])
    n = TIER_SIZE or max(2, len(ranked) // 4)
    out = {}
    for i, t in enumerate(ranked):
        out[t] = 'TOP' if i < n else ('BOT' if i >= len(ranked) - n else 'MID')
    return out


def _firstPassage(seasonTiers, fromTier, toTier):
    """-> (completed_durations, censored_count).

    A spell starts the FIRST season a team is in fromTier (after having been elsewhere,
    or at the start of observation) and ends the first season it reaches toTier.
    """
    seasons = sorted(seasonTiers)
    teams = set().union(*[set(seasonTiers[s]) for s in seasons])
    durations, censored = [], 0
    for team in teams:
        path = [(s, seasonTiers[s].get(team)) for s in seasons if team in seasonTiers[s]]
        i = 0
        while i < len(path):
            if path[i][1] != fromTier:
                i += 1
                continue
            # Found a spell start; walk forward to the first toTier season.
            hit = None
            for j in range(i + 1, len(path)):
                if path[j][1] == toTier:
                    hit = j
                    break
            if hit is None:
                censored += 1
                break  # nothing later can complete either; move to next team
            durations.append(path[hit][0] - path[i][0])
            # Continue searching after the arrival, so a team can churn repeatedly.
            i = hit + 1
            while i < len(path) and path[i][1] == toTier:
                i += 1
        # (loop ends naturally)
    return durations, censored


def _transitionMatrix(seasonTiers):
    seasons = sorted(seasonTiers)
    counts = defaultdict(Counter)
    for a, b in zip(seasons, seasons[1:]):
        if b - a != 1:
            continue
        for team, tier in seasonTiers[a].items():
            if team in seasonTiers[b]:
                counts[tier][seasonTiers[b][team]] += 1
    return counts


def analyze(datasets, label, skipFirst=0):
    """datasets: list of {season: {team: wins}} — one per independent league."""
    allDur = {('BOT', 'TOP'): [], ('TOP', 'BOT'): []}
    allCens = {('BOT', 'TOP'): 0, ('TOP', 'BOT'): 0}
    matrix = defaultdict(Counter)
    windows = []

    for wins_by_season in datasets:
        seasons = sorted(wins_by_season)[skipFirst:]
        if len(seasons) < 3:
            continue
        windows.append(len(seasons))
        seasonTiers = {s: tiersFor(wins_by_season[s]) for s in seasons}
        for pair in allDur:
            d, c = _firstPassage(seasonTiers, pair[0], pair[1])
            allDur[pair].extend(d); allCens[pair] += c
        for a, row in _transitionMatrix(seasonTiers).items():
            matrix[a].update(row)

    print(f"\n=== CHURN — {label} ===")
    print(f"{len(datasets)} league(s), observation window {min(windows)}-{max(windows)} seasons"
          + (f" (first {skipFirst} season(s) skipped)" if skipFirst else ""))
    print(f"Tiers: TOP = best 6 of 24, BOT = worst 6 of 24\n")

    for pair, name in [(('BOT', 'TOP'), 'CELLAR -> CONTENDER  (bottom 6 -> top 6)'),
                       (('TOP', 'BOT'), 'CONTENDER -> CELLAR  (top 6 -> bottom 6)')]:
        d, c = allDur[pair], allCens[pair]
        print(f"{name}")
        if d:
            d_sorted = sorted(d)
            print(f"  completed climbs/falls: {len(d)}    never made it in window: {c}"
                  f"  ({c/(len(d)+c)*100:.0f}% censored)")
            print(f"  median {statistics.median(d_sorted):.0f} seasons   "
                  f"mean {statistics.mean(d_sorted):.1f}   "
                  f"fastest {min(d_sorted)}   slowest {max(d_sorted)}")
            dist = Counter(d_sorted)
            line = "   ".join(f"{k}yr:{v}" for k, v in sorted(dist.items()))
            print(f"  distribution: {line}")
            within = lambda n: sum(1 for x in d if x <= n)
            tot = len(d) + c
            print(f"  within 1 season: {within(1)/tot*100:.0f}%   "
                  f"within 2: {within(2)/tot*100:.0f}%   "
                  f"within 3: {within(3)/tot*100:.0f}%   "
                  f"within 5: {within(5)/tot*100:.0f}%   (of all spells incl. censored)")
        else:
            print(f"  no completed transitions ({c} censored)")
        print()

    print("Season-to-season tier transitions (row = this season, col = next):")
    print(f"{'':>8}{'TOP':>8}{'MID':>8}{'BOT':>8}")
    for a in ('TOP', 'MID', 'BOT'):
        row = matrix.get(a, Counter())
        tot = sum(row.values()) or 1
        print(f"{a:>8}" + "".join(f"{row.get(b,0)/tot*100:>7.0f}%" for b in ('TOP', 'MID', 'BOT')))
    top = matrix.get('TOP', Counter()); bot = matrix.get('BOT', Counter())
    if sum(top.values()):
        print(f"\n  A top-6 team stays top-6 next season {top['TOP']/sum(top.values())*100:.0f}% of the time.")
    if sum(bot.values()):
        print(f"  A bottom-6 team stays bottom-6 next season {bot['BOT']/sum(bot.values())*100:.0f}% of the time.")


def _topSpells(seasonTiers):
    """Consecutive-season runs in TOP — the direct measure of a dynasty."""
    seasons = sorted(seasonTiers)
    teams = set().union(*[set(seasonTiers[s]) for s in seasons])
    spells = []
    for team in teams:
        run = 0
        for s in seasons:
            if seasonTiers[s].get(team) == 'TOP':
                run += 1
            else:
                if run: spells.append(run)
                run = 0
        if run: spells.append(run)
    return spells


def dynasties(datasets, champsPerLeague, label, skipFirst=0):
    """datasets: [{season: {team: wins}}]; champsPerLeague: [{season: championName}]"""
    print(f"\n=== DYNASTY MEASURES — {label} ===")
    allSpells, topOccupancy, allChampCounters, streaks = [], [], [], []
    for wins_by_season, champs in zip(datasets, champsPerLeague):
        seasons = sorted(wins_by_season)[skipFirst:]
        if len(seasons) < 3:
            continue
        seasonTiers = {s: tiersFor(wins_by_season[s]) for s in seasons}
        allSpells.extend(_topSpells(seasonTiers))
        seen = Counter()
        for s in seasons:
            for t, tier in seasonTiers[s].items():
                if tier == 'TOP':
                    seen[t] += 1
        topOccupancy.append(seen)
        cs = [champs[s] for s in seasons if s in champs and champs[s]]
        allChampCounters.append(Counter(cs))
        # longest consecutive title streak
        best = cur = 0
        prev = None
        for c in cs:
            cur = cur + 1 if c == prev else 1
            best = max(best, cur); prev = c
        streaks.append(best)

    if allSpells:
        dist = Counter(allSpells)
        print(f"\nConsecutive seasons in the top 6 (dynasty runs), {len(allSpells)} spells:")
        print("  " + "   ".join(f"{k}yr:{v}" for k, v in sorted(dist.items())))
        print(f"  median {statistics.median(allSpells):.0f}   mean {statistics.mean(allSpells):.1f}"
              f"   longest {max(allSpells)}")
        long = sum(v for k, v in dist.items() if k >= 4)
        print(f"  runs of 4+ straight contending seasons: {long}/{len(allSpells)} "
              f"({long/len(allSpells)*100:.0f}%)")

    if topOccupancy:
        ns = [len(o) for o in topOccupancy]
        mx = [max(o.values()) for o in topOccupancy]
        print(f"\nHow many DIFFERENT teams touch the top 6 across the window:")
        print(f"  mean {sum(ns)/len(ns):.1f} of 24 teams   (range {min(ns)}-{max(ns)})")
        print(f"  most contending seasons by a single team: mean {sum(mx)/len(mx):.1f}  "
              f"(max {max(mx)})")

    if allChampCounters:
        nd = [len(c) for c in allChampCounters]
        mx = [max(c.values()) for c in allChampCounters]
        rep = [sum(v - 1 for v in c.values() if v > 1) for c in allChampCounters]
        print(f"\nTitles:")
        print(f"  distinct champions per league: mean {sum(nd)/len(nd):.1f}  (range {min(nd)}-{max(nd)})")
        print(f"  most titles by one team: mean {sum(mx)/len(mx):.1f}  (max {max(mx)})")
        print(f"  repeat titles per league: mean {sum(rep)/len(rep):.1f}")
        print(f"  longest back-to-back title streak: max {max(streaks)}  "
              f"(mean {sum(streaks)/len(streaks):.1f})")


def fromDb(db, first, last):
    c = sqlite3.connect(f'file:{db}?mode=ro', uri=True)
    names = {r[0]: r[1] for r in c.execute('select id, name from teams')}
    data = {}
    for season in range(int(first), int(last) + 1):
        wins = {names[t]: w for t, w in
                c.execute('select team_id, wins from team_season_stats where season=?', (season,))}
        if len(wins) >= 20:
            data[season] = wins
    c.close()
    analyze([data], f"PROD seasons {first}-{last} (fan-managed)")


if __name__ == '__main__':
    if sys.argv[1] == 'db':
        fromDb(sys.argv[2], sys.argv[3], sys.argv[4])
    elif sys.argv[1] == 'json':
        raw = json.load(open(sys.argv[2]))
        skip = int(sys.argv[3]) if len(sys.argv) > 3 else 0
        datasets = [{r['season']: r['wins'] for r in lg} for lg in raw]
        champs = [{r['season']: r.get('champion') for r in lg} for lg in raw]
        analyze(datasets, "FRESH LEAGUES under autonomous FO", skipFirst=skip)
        dynasties(datasets, champs, "FRESH LEAGUES under autonomous FO", skipFirst=skip)
