"""Analyze the score distribution of recent games against NFL norms.

Looks at games in the local DB (data/floosball.db) and reports:
- Margin-of-victory distribution
- How often the losing team scored ≤6, ≤10
- Average and median scores per team
- Distribution of "blowout" games

NFL reference (regular season):
  - Median margin of victory: ~10-11 points
  - Close games (margin ≤7):    ~30%
  - Blowouts (margin ≥22):      ~20%
  - Loser scored ≤6:            ~12%
  - Loser scored ≤10:           ~25%

Usage:
  python analyze_scores.py                  # all completed games
  python analyze_scores.py --from-season 4  # filter to season 4 onward
  python analyze_scores.py --season 8       # single season
  python analyze_scores.py --last 100       # last 100 games only
"""
import argparse
import sqlite3
import statistics
import sys
from collections import Counter


def loadGames(dbPath: str, season=None, fromSeason=None, last=None):
    conn = sqlite3.connect(dbPath)
    sql = """
        SELECT season, week, home_score, away_score
        FROM games
        WHERE home_score + away_score > 0
    """
    args = []
    if season is not None:
        sql += " AND season = ?"
        args.append(season)
    if fromSeason is not None:
        sql += " AND season >= ?"
        args.append(fromSeason)
    sql += " ORDER BY season, week, id"
    rows = conn.execute(sql, args).fetchall()
    conn.close()
    if last:
        rows = rows[-last:]
    return rows


def report(rows):
    if not rows:
        print("No games match the filter.")
        return

    n = len(rows)
    margins = []
    winnerScores = []
    loserScores = []
    teamScores = []

    for season, week, home, away in rows:
        margin = abs(home - away)
        margins.append(margin)
        winner = max(home, away)
        loser = min(home, away)
        winnerScores.append(winner)
        loserScores.append(loser)
        teamScores.append(home)
        teamScores.append(away)

    print()
    print(f"=== {n} games ===")
    print()

    # Margin distribution
    print(f"Margin of victory:")
    print(f"  mean:    {statistics.mean(margins):.1f}")
    print(f"  median:  {statistics.median(margins):.1f}")
    print(f"  stdev:   {statistics.stdev(margins):.1f}")
    print()

    # Buckets
    closeGames = sum(1 for m in margins if m <= 7)
    moderateGames = sum(1 for m in margins if 8 <= m <= 14)
    largeGames = sum(1 for m in margins if 15 <= m <= 21)
    blowouts = sum(1 for m in margins if m >= 22)
    print(f"Margin buckets  (NFL ref in parens):")
    print(f"  ≤7  (close):        {closeGames:>4d}  {100*closeGames/n:>5.1f}%  (NFL ~30%)")
    print(f"  8-14 (moderate):    {moderateGames:>4d}  {100*moderateGames/n:>5.1f}%  (NFL ~25%)")
    print(f"  15-21 (large):      {largeGames:>4d}  {100*largeGames/n:>5.1f}%  (NFL ~25%)")
    print(f"  ≥22 (blowouts):     {blowouts:>4d}  {100*blowouts/n:>5.1f}%  (NFL ~20%)")
    print()

    # Loser score buckets
    loser6 = sum(1 for s in loserScores if s <= 6)
    loser10 = sum(1 for s in loserScores if s <= 10)
    loser14 = sum(1 for s in loserScores if s <= 14)
    print(f"Losing team score:")
    print(f"  mean:  {statistics.mean(loserScores):.1f}   median: {statistics.median(loserScores):.1f}")
    print(f"  ≤6:   {loser6:>4d}  {100*loser6/n:>5.1f}%  (NFL ~12%)")
    print(f"  ≤10:  {loser10:>4d}  {100*loser10/n:>5.1f}%  (NFL ~25%)")
    print(f"  ≤14:  {loser14:>4d}  {100*loser14/n:>5.1f}%  (NFL ~45%)")
    print()

    # Winner score buckets
    print(f"Winning team score:")
    print(f"  mean:  {statistics.mean(winnerScores):.1f}   median: {statistics.median(winnerScores):.1f}")
    print()

    # Per-team
    print(f"Per-team scoring:")
    print(f"  mean:  {statistics.mean(teamScores):.1f}   median: {statistics.median(teamScores):.1f}   stdev: {statistics.stdev(teamScores):.1f}")
    print()

    # Score histogram (10-pt buckets)
    print(f"Per-team score histogram:")
    bucketCounts = Counter()
    for s in teamScores:
        bucketCounts[s // 7 * 7] += 1
    for bucket in sorted(bucketCounts):
        bar = "#" * int(bucketCounts[bucket] / max(bucketCounts.values()) * 50)
        print(f"  {bucket:>3d}-{bucket+6:>3d}:  {bucketCounts[bucket]:>4d}  {bar}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("path", nargs="?", default="data/floosball.db")
    ap.add_argument("--season", type=int, default=None)
    ap.add_argument("--from-season", type=int, default=None)
    ap.add_argument("--last", type=int, default=None,
                    help="Look at only the last N games.")
    args = ap.parse_args()
    rows = loadGames(args.path, season=args.season,
                     fromSeason=args.from_season, last=args.last)
    report(rows)
