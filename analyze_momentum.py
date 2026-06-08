"""Read logs/sim_analytics.jsonl and print momentum-system diagnostics.

Companion to analyze_sim.py — focuses on the metrics you'd watch when
tuning the momentum system: margin distribution, Q4 scoring share,
big-play / shift frequency, comeback rate, and outcome lift from
sustained momentum vs. the pre-game win-probability baseline.

  python analyze_momentum.py                    # reads logs/sim_analytics.jsonl
  python analyze_momentum.py path/to/log.jsonl  # custom path
  python analyze_momentum.py --season 1         # filter to a single season
  python analyze_momentum.py --week 5           # filter to a single week
"""
import argparse
import json
import os
import sys


def loadGames(path, season=None, week=None):
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
            # Only count games that actually have momentum fields. Old
            # rows pre-instrumentation get skipped silently rather than
            # poisoning the averages with zeros.
            if 'finalAbsMomentum' not in row:
                continue
            rows.append(row)
    return rows


def marginBucket(margin):
    """Group games by final-margin tier so blowout vs close splits are visible."""
    if margin <= 3:
        return '0-3'
    if margin <= 7:
        return '4-7'
    if margin <= 14:
        return '8-14'
    if margin <= 21:
        return '15-21'
    return '22+'


def report(rows):
    if not rows:
        print('No games match the filter (or none have momentum fields — rerun a season after the latest sim build).')
        return

    n = len(rows)

    # ─── Margin distribution ────────────────────────────────────────────
    buckets = {'0-3': 0, '4-7': 0, '8-14': 0, '15-21': 0, '22+': 0}
    marginSum = 0
    for r in rows:
        m = abs(r['homeScore'] - r['awayScore'])
        marginSum += m
        buckets[marginBucket(m)] += 1

    print()
    print(f'=== {n} game{"s" if n != 1 else ""} ===')
    print()
    print('FINAL MARGIN DISTRIBUTION')
    print(f'  Avg margin:           {marginSum / n:.2f} points')
    for label in ('0-3', '4-7', '8-14', '15-21', '22+'):
        share = 100 * buckets[label] / n
        bar = '█' * int(share / 2)
        print(f'  {label:6s}  {buckets[label]:4d}  ({share:5.1f}%)  {bar}')

    # ─── Q4 scoring share ───────────────────────────────────────────────
    q1Pts = sum(r['homeQ1'] + r['awayQ1'] for r in rows)
    q2Pts = sum(r['homeQ2'] + r['awayQ2'] for r in rows)
    q3Pts = sum(r['homeQ3'] + r['awayQ3'] for r in rows)
    q4Pts = sum(r['homeQ4'] + r['awayQ4'] for r in rows)
    otPts = sum(r.get('homeOT', 0) + r.get('awayOT', 0) for r in rows)
    totalPts = q1Pts + q2Pts + q3Pts + q4Pts + otPts

    print()
    print('SCORING BY QUARTER  (share of total points)')
    if totalPts:
        for label, pts in (('Q1', q1Pts), ('Q2', q2Pts), ('Q3', q3Pts), ('Q4', q4Pts), ('OT', otPts)):
            share = 100 * pts / totalPts
            avg = pts / n
            bar = '█' * int(share / 2)
            print(f'  {label:3s}  {avg:5.2f} pts/game  ({share:5.1f}%)  {bar}')

    # ─── Big plays & momentum shifts ────────────────────────────────────
    bigPlays = sum(r.get('bigPlays', 0) for r in rows)
    shifts = sum(r.get('momentumShifts', 0) for r in rows)
    print()
    print('MOMENTUM EVENTS')
    print(f'  Big plays (WPA >=7%):       {bigPlays / n:.2f} / game  ({bigPlays} total)')
    print(f'  Momentum shift highlights:  {shifts / n:.2f} / game  ({shifts} total)')

    # ─── Momentum reach ─────────────────────────────────────────────────
    finalMomSum = sum(r['finalAbsMomentum'] for r in rows)
    peakMomSum = sum(r['peakAbsMomentum'] for r in rows)
    framesSum = sum(r['playsAbove30Mom'] for r in rows)
    playsSum = sum(r['totalPlays'] for r in rows)
    print()
    print('MOMENTUM REACH')
    print(f'  Avg final |momentum|:        {finalMomSum / n:.1f}')
    print(f'  Avg peak  |momentum|:        {peakMomSum / n:.1f}')
    print(f'  Plays with |momentum| >=30:  {framesSum / n:.1f} / game  ({100 * framesSum / max(1, playsSum):.1f}% of plays)')

    # ─── Final margin × peak momentum ───────────────────────────────────
    # Are blowouts also high-peak-momentum games? Should be a positive
    # correlation — sustained dominance means both wider margin and
    # higher peak momentum.
    print()
    print('PEAK |MOMENTUM| BY FINAL MARGIN')
    byBucket = {b: [] for b in ('0-3', '4-7', '8-14', '15-21', '22+')}
    for r in rows:
        m = abs(r['homeScore'] - r['awayScore'])
        byBucket[marginBucket(m)].append(r['peakAbsMomentum'])
    for label in ('0-3', '4-7', '8-14', '15-21', '22+'):
        vals = byBucket[label]
        if vals:
            print(f'  {label:6s}  n={len(vals):4d}   avg peak {sum(vals)/len(vals):5.1f}')

    # ─── Comeback rate ──────────────────────────────────────────────────
    # "Comeback" = team trailing at half (after Q1+Q2) wins the game.
    # Games tied at half don't count for either side; games tied at end
    # are ignored.
    trailWins = 0
    trailableGames = 0
    for r in rows:
        homeHalf = r['homeQ1'] + r['homeQ2']
        awayHalf = r['awayQ1'] + r['awayQ2']
        if homeHalf == awayHalf:
            continue
        if r['homeScore'] == r['awayScore']:
            continue
        trailableGames += 1
        homeTrailed = homeHalf < awayHalf
        homeWon = r['homeScore'] > r['awayScore']
        if (homeTrailed and homeWon) or (not homeTrailed and not homeWon):
            trailWins += 1
    print()
    print('COMEBACK RATE')
    if trailableGames:
        rate = 100 * trailWins / trailableGames
        print(f'  Trailing-at-half team wins: {trailWins}/{trailableGames}  ({rate:.1f}%)')
    else:
        print('  No qualifying games (all tied at half or finished tied).')

    # ─── Pre-game WP baseline lift ──────────────────────────────────────
    # Compare actual home-win-rate against the average pre-game home WP.
    # If the home team wins more often than their pre-game WP suggests,
    # something other than ELO (momentum?) is shifting outcomes. Stratify
    # by pre-game WP tier so we don't drown the signal in coin-flip games.
    print()
    print('OUTCOME vs PRE-GAME WIN PROBABILITY')
    tiers = [
        ('Underdog (<35%)', lambda p: p < 0.35),
        ('Toss-up 35-65%',  lambda p: 0.35 <= p <= 0.65),
        ('Favorite (>65%)', lambda p: p > 0.65),
    ]
    totalsByTier = {label: {'n': 0, 'wp': 0.0, 'wins': 0} for label, _ in tiers}
    for r in rows:
        wp = r.get('preGameHomeWinProb', 0.5)
        homeWon = r['homeScore'] > r['awayScore']
        if r['homeScore'] == r['awayScore']:
            continue
        for label, fn in tiers:
            if fn(wp):
                t = totalsByTier[label]
                t['n'] += 1
                t['wp'] += wp
                t['wins'] += 1 if homeWon else 0
                break
    for label, _ in tiers:
        t = totalsByTier[label]
        if t['n'] == 0:
            print(f'  {label:18s}  n=0')
            continue
        avgWp = 100 * t['wp'] / t['n']
        actualWp = 100 * t['wins'] / t['n']
        delta = actualWp - avgWp
        sign = '+' if delta >= 0 else ''
        print(f'  {label:18s}  n={t["n"]:4d}   pre-game home WP avg {avgWp:5.1f}%   actual {actualWp:5.1f}%   delta {sign}{delta:5.1f}pp')

    # ─── Sustained-momentum lift ────────────────────────────────────────
    # Split games into two buckets: low-reach (peak < 30) vs high-reach
    # (peak >= 30). In each bucket, does the team that hit high momentum
    # actually win more than the pre-game favorite would predict?
    print()
    print('PEAK MOMENTUM SPLIT')
    low = [r for r in rows if r['peakAbsMomentum'] < 30]
    high = [r for r in rows if r['peakAbsMomentum'] >= 30]
    print(f'  Games where peak |mom| <30:  {len(low):4d}  ({100*len(low)/n:.1f}%)')
    print(f'  Games where peak |mom| >=30: {len(high):4d}  ({100*len(high)/n:.1f}%)')
    if low:
        avgMargin = sum(abs(r['homeScore'] - r['awayScore']) for r in low) / len(low)
        print(f'    avg margin (low):  {avgMargin:.2f}')
    if high:
        avgMargin = sum(abs(r['homeScore'] - r['awayScore']) for r in high) / len(high)
        print(f'    avg margin (high): {avgMargin:.2f}')

    print()


def main():
    parser = argparse.ArgumentParser(description='Aggregate momentum diagnostics from sim_analytics.jsonl.')
    parser.add_argument('path', nargs='?', default='logs/sim_analytics.jsonl')
    parser.add_argument('--season', type=int, help='Filter to a single season')
    parser.add_argument('--week', type=int, help='Filter to a single week')
    args = parser.parse_args()

    rows = loadGames(args.path, season=args.season, week=args.week)
    report(rows)


if __name__ == '__main__':
    main()
