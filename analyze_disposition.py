"""Read logs/sim_analytics.jsonl and print disposition / form / mental-stack
diagnostics.

Companion to analyze_momentum.py — focuses on whether the disposition
(form state + matchup context) and end-game rating drift are compounding
the favorite's advantage past what ELO predicts.

  python analyze_disposition.py                    # reads logs/sim_analytics.jsonl
  python analyze_disposition.py path/to/log.jsonl  # custom path
  python analyze_disposition.py --season 1         # filter to a single season
  python analyze_disposition.py --week 5           # filter to a single week
"""
import argparse
import json
import os
import sys
from collections import Counter


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
            # Skip rows from before the disposition instrumentation landed.
            if 'home_avgBaseline' not in row:
                continue
            rows.append(row)
    return rows


def tier(wp):
    if wp < 0.35:
        return 'Underdog'
    if wp > 0.65:
        return 'Favorite'
    return 'Toss-up'


def report(rows):
    if not rows:
        print('No games match the filter (or none have disposition fields — rerun a season after the latest sim build).')
        return

    n = len(rows)
    print()
    print(f'=== {n} game{"s" if n != 1 else ""} ===')

    # ─── Rating-gap amplification ────────────────────────────────────────
    # Compare the home-vs-away rating gap at each phase. If the gap widens
    # from baseline → afterDisposition, the stack is amplifying ELO. If it
    # widens again from afterDisposition → endGame, in-game drift
    # (momentum / clutch / choke / per-play fatigue) is doing it.
    print()
    print('AVG RATING GAP (home - away) BY PHASE')
    print('  How much does each modifier stage widen or close the')
    print('  pre-game skill gap?')
    print()
    phases = [
        ('baseline',         'home_avgBaseline',         'away_avgBaseline'),
        ('afterFatigue',     'home_avgAfterFatigue',     'away_avgAfterFatigue'),
        ('afterDisposition', 'home_avgAfterDisposition', 'away_avgAfterDisposition'),
        ('afterCap',         'home_avgAfterCap',         'away_avgAfterCap'),
        ('endGame',          'home_avgEndGame',          'away_avgEndGame'),
    ]
    for label, hk, ak in phases:
        gaps = [r[hk] - r[ak] for r in rows]
        avgGap = sum(gaps) / len(gaps)
        absGaps = [abs(g) for g in gaps]
        avgAbsGap = sum(absGaps) / len(absGaps)
        print(f'  {label:18s}  signed gap {avgGap:+6.2f}   avg |gap| {avgAbsGap:5.2f}')

    # ─── Gap evolution (amplification ratio) ─────────────────────────────
    # For each game, compute |afterCap - baseline| / |afterCap baseline|
    # gap to see if the stack expands or compresses the skill gap.
    print()
    print('PRE-GAME GAP vs EFFECTIVE GAP')
    print('  If "effective / baseline" > 1.0, the disposition stack is')
    print('  amplifying the skill gap; if < 1.0, it is compressing it.')
    print()
    ratios = []
    for r in rows:
        baseGap = abs(r['home_avgBaseline'] - r['away_avgBaseline'])
        effGap = abs(r['home_avgAfterCap'] - r['away_avgAfterCap'])
        if baseGap >= 0.5:  # skip games where teams are essentially even
            ratios.append(effGap / baseGap)
    if ratios:
        avg = sum(ratios) / len(ratios)
        amp = [r for r in ratios if r > 1.05]
        comp = [r for r in ratios if r < 0.95]
        same = len(ratios) - len(amp) - len(comp)
        print(f'  Avg effective/baseline ratio: {avg:.2f}  (1.00 = neutral)')
        print(f'  Games where stack amplified (ratio > 1.05): {len(amp)} ({100*len(amp)/len(ratios):.1f}%)')
        print(f'  Games where stack compressed (ratio < 0.95): {len(comp)} ({100*len(comp)/len(ratios):.1f}%)')
        print(f'  Games where stack neutral (0.95-1.05):       {same} ({100*same/len(ratios):.1f}%)')

    # ─── Disposition by WP tier ──────────────────────────────────────────
    # Are favorites systematically getting positive multipliers and
    # underdogs negative ones? If yes, the disposition system is just
    # re-encoding ELO and double-counting the favorite signal.
    print()
    print('DISPOSITION MULTIPLIER BY PRE-GAME WP TIER  (home-team perspective)')
    byTier = {'Underdog': [], 'Toss-up': [], 'Favorite': []}
    for r in rows:
        wp = r.get('preGameHomeWinProb', 0.5)
        byTier[tier(wp)].append(r['home_dispositionMult'])
    for t in ('Underdog', 'Toss-up', 'Favorite'):
        vals = byTier[t]
        if not vals:
            continue
        avg = sum(vals) / len(vals)
        pos = sum(1 for v in vals if v > 1.005)
        neg = sum(1 for v in vals if v < 0.995)
        print(f'  {t:10s}  n={len(vals):4d}   avg mult {avg:.3f}   positive: {100*pos/len(vals):4.1f}%   negative: {100*neg/len(vals):4.1f}%')

    # ─── End-game drift ──────────────────────────────────────────────────
    # Does the average roster rating drift up or down during the game?
    # Trailing teams typically drift down (fatigue + mental drag);
    # leading teams may drift up (momentum boost). Quantify.
    print()
    print('END-GAME RATING DRIFT  (endGame - afterCap)  by outcome')
    winnerDrifts = []
    loserDrifts = []
    for r in rows:
        if r['homeScore'] == r['awayScore']:
            continue
        homeWon = r['homeScore'] > r['awayScore']
        homeDrift = r['home_avgEndGame'] - r['home_avgAfterCap']
        awayDrift = r['away_avgEndGame'] - r['away_avgAfterCap']
        if homeWon:
            winnerDrifts.append(homeDrift)
            loserDrifts.append(awayDrift)
        else:
            winnerDrifts.append(awayDrift)
            loserDrifts.append(homeDrift)
    if winnerDrifts:
        wAvg = sum(winnerDrifts) / len(winnerDrifts)
        lAvg = sum(loserDrifts) / len(loserDrifts)
        print(f'  Winner avg drift:  {wAvg:+5.2f}')
        print(f'  Loser  avg drift:  {lAvg:+5.2f}')
        print(f'  Drift gap (winner - loser): {wAvg - lAvg:+.2f}')
        print('  A large positive gap means leading teams ride high and')
        print('  trailing teams collapse — exactly the spiral that pushes')
        print('  favorites past their pre-game WP.')

    # ─── Form-state distribution ─────────────────────────────────────────
    print()
    print('FORM STATE DISTRIBUTION  (across both teams in every game)')
    formCounter = Counter()
    for r in rows:
        for k in ('home_formState', 'away_formState'):
            v = r.get(k)
            if v:
                formCounter[v] += 1
    totalTeams = 2 * n
    for state, count in formCounter.most_common():
        share = 100 * count / totalTeams
        bar = '█' * int(share / 2)
        print(f'  {state:14s}  {count:5d}  ({share:5.1f}%)  {bar}')

    # ─── Form-state by WP tier ───────────────────────────────────────────
    # Confirm whether favorites disproportionately get HOT_STREAK /
    # RESOLUTE and underdogs disproportionately get SPIRALING / COMPLACENT.
    print()
    print('FORM STATE BY PRE-GAME WP TIER  (home-team perspective)')
    tierForms = {'Underdog': Counter(), 'Toss-up': Counter(), 'Favorite': Counter()}
    tierTotals = {'Underdog': 0, 'Toss-up': 0, 'Favorite': 0}
    for r in rows:
        wp = r.get('preGameHomeWinProb', 0.5)
        t = tier(wp)
        fs = r.get('home_formState')
        if fs:
            tierForms[t][fs] += 1
            tierTotals[t] += 1
    for t in ('Underdog', 'Toss-up', 'Favorite'):
        if tierTotals[t] == 0:
            continue
        print(f'  {t}  (n={tierTotals[t]})')
        for state, count in tierForms[t].most_common():
            share = 100 * count / tierTotals[t]
            print(f'    {state:14s}  {share:4.1f}%')

    # ─── Disposition label distribution ──────────────────────────────────
    print()
    print('TOP DISPOSITION LABELS  (across both teams)')
    labelCounter = Counter()
    for r in rows:
        for k in ('home_dispositionLabel', 'away_dispositionLabel'):
            v = r.get(k)
            if v:
                labelCounter[v] += 1
    for label, count in labelCounter.most_common(12):
        share = 100 * count / totalTeams
        print(f'  {label:30s}  {count:5d}  ({share:5.1f}%)')

    print()


def main():
    parser = argparse.ArgumentParser(description='Aggregate disposition diagnostics from sim_analytics.jsonl.')
    parser.add_argument('path', nargs='?', default='logs/sim_analytics.jsonl')
    parser.add_argument('--season', type=int, help='Filter to a single season')
    parser.add_argument('--week', type=int, help='Filter to a single week')
    args = parser.parse_args()

    rows = loadGames(args.path, season=args.season, week=args.week)
    report(rows)


if __name__ == '__main__':
    main()
