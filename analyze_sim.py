"""Read logs/sim_analytics.jsonl and print aggregate stats.

Each line in the log is one game (written by `Game._logPlayAnalytics`).
Run a season (any timing mode) to populate, then run this script to get
per-game aggregates by tier:

  python analyze_sim.py                    # reads logs/sim_analytics.jsonl
  python analyze_sim.py path/to/log.jsonl  # custom path
  python analyze_sim.py --week 5           # filter to a single week
  python analyze_sim.py --season 1         # filter to a single season
"""
import argparse
import json
import os
import sys


def loadGames(path: str, season: int = None, week: int = None):
    if not os.path.exists(path):
        print(f'No log at {path}. Run a season first to populate it.')
        sys.exit(1)
    rows = []
    with open(path) as f:
        for line in f:
            try:
                row = json.loads(line)
            except Exception:
                continue
            if season is not None and row.get('season') != season:
                continue
            if week is not None and row.get('week') != week:
                continue
            rows.append(row)
    return rows


def report(rows):
    if not rows:
        print('No games match the filter.')
        return
    n = len(rows)

    def total(k):
        return sum(r.get(k, 0) for r in rows)

    def avg(k):
        return total(k) / n

    def bytier(k):
        out = {'short': 0, 'medium': 0, 'long': 0, 'deep': 0, 'hailMary': 0}
        for r in rows:
            sub = r.get(k, {}) or {}
            for tier in out:
                out[tier] += sub.get(tier, 0)
        return out

    print()
    print(f'=== {n} game{"s" if n != 1 else ""} ===')
    print()
    print(f'Avg plays per game:        {avg("totalPlays"):.1f}')
    print(f'Avg run plays:             {avg("runPlays"):.1f}')
    print(f'Avg pass attempts:         {avg("passAttempts"):.1f}')

    passAtt = total('passAttempts')
    if passAtt > 0:
        compPct = 100 * total('passCompletions') / passAtt
        ypa = total('totalPassYards') / passAtt
        ypc = total('totalPassYards') / max(1, total('passCompletions'))
        intRate = 100 * total('interceptions') / passAtt
        print(f'  Completion %:            {compPct:.1f}')
        print(f'  Yards per attempt:       {ypa:.2f}')
        print(f'  Yards per completion:    {ypc:.2f}')
        print(f'  INT rate per attempt:    {intRate:.2f}%')
    if total('runPlays') > 0:
        print(f'  Yards per run:           {total("totalRushYards") / total("runPlays"):.2f}')

    print()
    print('PASS DISTRIBUTION BY TIER  (avg per game)')
    for tier, count in bytier('passByTier').items():
        share = (100 * count / passAtt) if passAtt else 0
        print(f'  {tier:10s}  {count/n:6.2f}/game   ({share:4.1f}% of attempts)')

    print()
    print('TOUCHDOWNS  (per game avg)')
    print(f'  Run TDs:                 {avg("runTd"):.2f}/game  ({total("runTd")} total)')
    print(f'    of which 30+ yds:      {avg("runTd30plus"):.2f}/game  ({total("runTd30plus")} total)')
    print(f'  Pass TDs:                {avg("passTd"):.2f}/game  ({total("passTd")} total)')
    print(f'    of which 30+ yds:      {avg("passTd30plus"):.2f}/game  ({total("passTd30plus")} total)')
    print('  Pass TDs by tier:')
    for tier, count in bytier('passTdByTier').items():
        print(f'    {tier:10s}            {count/n:6.2f}/game   ({count} total)')

    print()
    print('BIG PLAYS  (per game avg)')
    print(f'  Runs 20+ yds:            {avg("runs20plus"):.2f}')
    print(f'  Runs 30+ yds:            {avg("runs30plus"):.2f}')
    print(f'  Passes 20+ yds:          {avg("passes20plus"):.2f}')
    print(f'  Passes 30+ yds:          {avg("passes30plus"):.2f}')
    print(f'  Passes 40+ yds:          {avg("passes40plus"):.2f}')

    print()
    print('YARDAGE  (per game avg)')
    print(f'  Rush yards:              {avg("totalRushYards"):.1f}')
    print(f'  Pass yards (caught):     {avg("totalPassYards"):.1f}')
    print(f'    Air yards:             {avg("totalAirYards"):.1f}')
    print(f'    YAC:                   {avg("totalYac"):.1f}')
    if total('passCompletions') > 0:
        print(f'  Avg YAC per completion:  {total("totalYac") / total("passCompletions"):.2f}')
    print(f'  Longest run (max):       {max(r.get("longestRun", 0) for r in rows)}')
    print(f'  Longest pass (max):      {max(r.get("longestPass", 0) for r in rows)}')

    print()
    print('TURNOVERS  (per game avg)')
    print(f'  Interceptions:           {avg("interceptions"):.2f}')
    print(f'  Fumbles lost:            {avg("fumblesLost"):.2f}')
    print('  INTs by pass tier:')
    for tier, count in bytier('intByTier').items():
        attempts = bytier('passByTier').get(tier, 0)
        rate = (100 * count / attempts) if attempts else 0
        print(f'    {tier:10s}            {count/n:6.3f}/game   ({rate:.2f}% per {tier} attempt)')

    print()
    print('SACKS  (per game avg)')
    print(f'  Total sacks:             {avg("sacks"):.2f}')
    print('  Sacks by pass tier:')
    for tier, count in bytier('sackByTier').items():
        attempts = bytier('passByTier').get(tier, 0)
        rate = (100 * count / attempts) if attempts else 0
        print(f'    {tier:10s}            {count/n:6.3f}/game   ({rate:.2f}% sack rate on {tier})')


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('path', nargs='?', default='logs/sim_analytics.jsonl')
    ap.add_argument('--season', type=int, default=None)
    ap.add_argument('--week', type=int, default=None)
    args = ap.parse_args()
    rows = loadGames(args.path, season=args.season, week=args.week)
    report(rows)
