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


def loadGames(path: str, season: int = None, week: int = None,
              fromSeason: int = None, toSeason: int = None):
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
            s = row.get('season')
            if season is not None and s != season:
                continue
            if fromSeason is not None and (s is None or s < fromSeason):
                continue
            if toSeason is not None and (s is None or s > toSeason):
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
        # Net Yards Per Attempt: (pass yards - sack yards) / (attempts).
        # Matches NFL's NY/A stat. Pass yards include only completions; sack
        # losses subtract from team net.
        sackYds = total('sackYards')
        nya = (total('totalPassYards') - sackYds) / passAtt
        print(f'  Completion %:            {compPct:.1f}')
        print(f'  Yards per attempt:       {ypa:.2f}')
        print(f'  Net yds/attempt (NYA):   {nya:.2f}  (NFL ~6.5)')
        print(f'  Yards per completion:    {ypc:.2f}')
        print(f'  INT rate per attempt:    {intRate:.2f}%')
    if total('runPlays') > 0:
        print(f'  Yards per run:           {total("totalRushYards") / total("runPlays"):.2f}')

    print()
    print('PASS DISTRIBUTION BY TIER  (avg per game)')
    compTier = bytier('compByTier')
    dropTier = bytier('dropByTier')
    intTier = bytier('intByTier')
    sackTier = bytier('sackByTier')
    throwAwayTier = bytier('throwAwayByTier')
    incTier = bytier('incompleteByTier')
    thrownTier = bytier('thrownByTier')
    tqTier = bytier('tqSumByTier')
    opTier = bytier('opennessSumByTier')
    cpTier = bytier('catchProbSumByTier')
    contactTier = bytier('contactProbSumByTier')
    secureTier = bytier('secureProbSumByTier')
    covTier = bytier('covDefSumByTier')
    for tier, count in bytier('passByTier').items():
        share = (100 * count / passAtt) if passAtt else 0
        compPct = (100 * compTier.get(tier, 0) / count) if count else 0
        print(f'  {tier:10s}  {count/n:6.2f}/game   ({share:4.1f}% of att, {compPct:4.1f}% comp%)')

    print()
    print('PER-TIER OUTCOME BREAKDOWN  (% of attempts in that tier)')
    print(f'  {"tier":10s} {"comp%":>7s} {"drop%":>7s} {"int%":>7s} {"sack%":>7s} {"TA%":>6s} {"inc%":>7s}')
    for tier in ['short', 'medium', 'long', 'deep', 'hailMary']:
        att = bytier('passByTier').get(tier, 0)
        if att == 0:
            continue
        comp = compTier.get(tier, 0)
        drop = dropTier.get(tier, 0)
        intc = intTier.get(tier, 0)
        sack = sackTier.get(tier, 0)
        ta = throwAwayTier.get(tier, 0)
        inc = incTier.get(tier, 0)
        print(f'  {tier:10s} {100*comp/att:6.1f}% {100*drop/att:6.1f}% {100*intc/att:6.1f}% {100*sack/att:6.1f}% {100*ta/att:5.1f}% {100*inc/att:6.1f}%')

    print()
    print('PER-TIER MODEL DIAGNOSTICS  (avg over thrown balls — excludes sacks/throwaways)')
    print(f'  {"tier":10s} {"thrown":>7s} {"TQ":>6s} {"open":>6s} {"contact":>8s} {"secure":>7s} {"catchP":>7s} {"defCov":>7s}')
    for tier in ['short', 'medium', 'long', 'deep', 'hailMary']:
        thrown = thrownTier.get(tier, 0)
        if thrown == 0:
            continue
        avgTq = tqTier.get(tier, 0) / thrown
        avgOp = opTier.get(tier, 0) / thrown
        avgCp = cpTier.get(tier, 0) / thrown
        avgContact = contactTier.get(tier, 0) / thrown
        avgSecure = secureTier.get(tier, 0) / thrown
        avgCov = covTier.get(tier, 0) / thrown
        print(f'  {tier:10s} {thrown:>7d} {avgTq:6.1f} {avgOp:6.1f} {avgContact:8.1f} {avgSecure:7.1f} {avgCp:7.1f} {avgCov:7.1f}')

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

    # ── Call-vs-call matchup table ─────────────────────────────────────────
    callMatchup = {}
    for r in rows:
        cm = r.get('callMatchup') or {}
        for key, b in cm.items():
            slot = callMatchup.setdefault(key, {'plays': 0, 'yards': 0, 'tds': 0})
            slot['plays'] += b.get('plays', 0)
            slot['yards'] += b.get('yards', 0)
            slot['tds'] += b.get('tds', 0)
    if callMatchup:
        print()
        print('CALL vs CALL  (defensive call effectiveness by play type)')
        # Pretty labels
        covLabels = {'MAN': 'Man', 'ZONE': 'Zone', 'MATCH': 'Hybrid', 'NONE': '—'}
        blzLabels = {'LB_BLITZ': 'LB Blitz', 'SAFETY_BLITZ': 'S Blitz',
                     'ALL_OUT': 'All-Out', 'NONE': 'No Blitz'}
        # Split by playType (run vs pass) for separate tables
        for forPlay, header in [('run', 'vs RUN'), ('pass', 'vs PASS')]:
            entries = []
            for key, b in callMatchup.items():
                parts = key.split('|')
                if len(parts) != 3 or parts[2] != forPlay:
                    continue
                cov, blz, _ = parts
                if b['plays'] < 50:  # noise floor
                    continue
                entries.append((cov, blz, b))
            if not entries:
                continue
            # Sort by yards-per-play ascending (best defensive call first)
            entries.sort(key=lambda e: e[2]['yards'] / e[2]['plays'])
            print()
            print(f'  {header}  (min 50 plays per matchup)')
            print(f'    {"coverage":10s} {"blitz":10s} {"plays":>6s} {"yds/play":>9s} {"tds":>5s}')
            for cov, blz, b in entries:
                p = b['plays']
                print(f'    {covLabels.get(cov, cov):10s} {blzLabels.get(blz, blz):10s} '
                      f'{p:>6d} {b["yards"]/p:>9.2f} {b["tds"]:>5d}')

    # ── Key-down defensive stand ───────────────────────────────────────────
    totalKeyDown = total('keyDownPlays')
    if totalKeyDown > 0:
        print()
        print('KEY-DOWN STANDS  (3rd/4th & short, goal-line)')
        stops = total('keyDownStops')
        yds = total('keyDownYardsAllowed')
        print(f'  Key-down plays:          {totalKeyDown}  ({totalKeyDown/n:.2f}/game)')
        print(f'  Stops:                   {stops} ({100*stops/totalKeyDown:.1f}%)')
        print(f'  Avg yards allowed:       {yds/totalKeyDown:.2f}')
        # Per-defense table — top/bottom by stop rate (min 5 attempts)
        perTeam = {}
        for r in rows:
            byDef = r.get('keyDownByDefense') or {}
            for abbr, b in byDef.items():
                slot = perTeam.setdefault(abbr, {'plays': 0, 'stops': 0, 'yardsAllowed': 0, 'resolveSum': 0.0})
                slot['plays'] += b.get('plays', 0)
                slot['stops'] += b.get('stops', 0)
                slot['yardsAllowed'] += b.get('yardsAllowed', 0)
                slot['resolveSum'] += b.get('resolveSum', 0.0)
        teams = [(a, d) for a, d in perTeam.items() if d['plays'] >= 5]
        if teams:
            teams.sort(key=lambda kv: kv[1]['stops'] / kv[1]['plays'], reverse=True)
            print()
            print('  PER-DEFENSE (min 5 key-down attempts)')
            print(f'    {"team":6s} {"plays":>6s} {"stops":>6s} {"stop%":>7s} {"yds/play":>9s} {"resolve":>9s}')
            show = (teams[:5] + ['---'] + teams[-5:]) if len(teams) > 10 else teams
            for entry in show:
                if entry == '---':
                    print(f'    {"…":>6s}')
                    continue
                abbr, d = entry
                p = d['plays']
                resolve = d['resolveSum'] / p if p else 0
                print(f'    {abbr:6s} {p:>6d} {d["stops"]:>6d} '
                      f'{100*d["stops"]/p:>6.1f}% '
                      f'{d["yardsAllowed"]/p:>9.2f} '
                      f'{resolve:>9.3f}')

    # ── Defensive read mechanic ────────────────────────────────────────────
    totalReads = total('reads')
    if totalReads > 0:
        print()
        print('DEFENSIVE READ MECHANIC')
        correct = total('readsCorrect')
        neutral = total('readsNeutral')
        wrong = total('readsWrong')
        print(f'  Total reads:             {totalReads}')
        print(f'    correct:               {correct} ({100*correct/totalReads:.1f}%)')
        print(f'    neutral:               {neutral} ({100*neutral/totalReads:.1f}%)')
        print(f'    wrong:                 {wrong} ({100*wrong/totalReads:.1f}%)')
        print(f'  Avg pCorrect:            {total("pCorrectSum")/totalReads:.3f}')

        # Tendency usage
        tend = total('readsWithTendency')
        print(f'  Reads using tendency:    {tend} ({100*tend/totalReads:.1f}%)')

        # By play type
        runReads = sum((r.get('readsByPlayType', {}) or {}).get('run', {}).get('total', 0) for r in rows)
        passReads = sum((r.get('readsByPlayType', {}) or {}).get('pass', {}).get('total', 0) for r in rows)
        if runReads:
            runCorrect = sum((r.get('readsByPlayType', {}) or {}).get('run', {}).get('correct', 0) for r in rows)
            runNeutral = sum((r.get('readsByPlayType', {}) or {}).get('run', {}).get('neutral', 0) for r in rows)
            runWrong = sum((r.get('readsByPlayType', {}) or {}).get('run', {}).get('wrong', 0) for r in rows)
            print(f'  Run reads:               {runReads}  '
                  f'correct {100*runCorrect/runReads:.1f}%  '
                  f'neutral {100*runNeutral/runReads:.1f}%  '
                  f'wrong {100*runWrong/runReads:.1f}%')
        if passReads:
            passCorrect = sum((r.get('readsByPlayType', {}) or {}).get('pass', {}).get('correct', 0) for r in rows)
            passNeutral = sum((r.get('readsByPlayType', {}) or {}).get('pass', {}).get('neutral', 0) for r in rows)
            passWrong = sum((r.get('readsByPlayType', {}) or {}).get('pass', {}).get('wrong', 0) for r in rows)
            print(f'  Pass reads:              {passReads}  '
                  f'correct {100*passCorrect/passReads:.1f}%  '
                  f'neutral {100*passNeutral/passReads:.1f}%  '
                  f'wrong {100*passWrong/passReads:.1f}%')

        # Per-defense leaderboard — only show top/bottom 5 by correct rate (min sample)
        perTeam = {}
        for r in rows:
            byDef = r.get('readsByDefense') or {}
            for abbr, b in byDef.items():
                slot = perTeam.setdefault(abbr, {'correct': 0, 'neutral': 0, 'wrong': 0, 'total': 0, 'pCorrectSum': 0.0})
                for k in ('correct', 'neutral', 'wrong', 'total'):
                    slot[k] += b.get(k, 0)
                slot['pCorrectSum'] += b.get('pCorrectSum', 0.0)
        teams = [(a, d) for a, d in perTeam.items() if d['total'] >= 20]
        if teams:
            teams.sort(key=lambda kv: kv[1]['correct'] / kv[1]['total'], reverse=True)
            print()
            print('  PER-DEFENSE (min 20 reads)')
            print(f'    {"team":6s} {"reads":>6s} {"corr%":>6s} {"neut%":>6s} {"wrong%":>7s} {"avgPCor":>8s}')
            show = teams[:5] + (['---'] if len(teams) > 10 else []) + teams[-5:] if len(teams) > 10 else teams
            for entry in show:
                if entry == '---':
                    print(f'    {"…":>6s}')
                    continue
                abbr, d = entry
                t = d['total']
                print(f'    {abbr:6s} {t:>6d} '
                      f'{100*d["correct"]/t:>5.1f}% '
                      f'{100*d["neutral"]/t:>5.1f}% '
                      f'{100*d["wrong"]/t:>6.1f}% '
                      f'{d["pCorrectSum"]/t:>8.3f}')


def headlineMetrics(rows):
    """Reduce a row set to the headline offense / defense metrics we care
    about when comparing before/after a sim change. Returns a list of
    (label, value, formatter) tuples so the comparison printer can format
    each row consistently.
    """
    if not rows:
        return []
    n = len(rows)

    def total(k):
        return sum(r.get(k, 0) for r in rows)

    passAtt = total('passAttempts')
    passComp = total('passCompletions')
    passYds = total('totalPassYards')
    runPlays = total('runPlays')
    runYds = total('totalRushYards')
    sackYds = total('sackYards')
    ints = total('interceptions')
    sacks = total('sacks')
    fum = total('fumblesLost')
    plays = total('totalPlays')
    runTd = total('runTd')
    passTd = total('passTd')

    metrics = [
        ('games',                n,                                        '{:.0f}'),
        ('plays/game',           plays / n,                                 '{:.1f}'),
        ('run plays/game',       runPlays / n,                              '{:.1f}'),
        ('pass att/game',        passAtt / n,                               '{:.1f}'),
        ('completion %',         100 * passComp / passAtt if passAtt else 0, '{:.2f}'),
        ('YPA',                  passYds / passAtt if passAtt else 0,        '{:.2f}'),
        ('NYA',                  (passYds - sackYds) / passAtt if passAtt else 0, '{:.2f}'),
        ('Y/comp',               passYds / passComp if passComp else 0,      '{:.2f}'),
        ('Y/run',                runYds / runPlays if runPlays else 0,       '{:.2f}'),
        ('INT rate %',           100 * ints / passAtt if passAtt else 0,     '{:.2f}'),
        ('sack rate %',          100 * sacks / passAtt if passAtt else 0,    '{:.2f}'),
        ('run TDs/game',         runTd / n,                                  '{:.2f}'),
        ('pass TDs/game',        passTd / n,                                 '{:.2f}'),
        ('fumbles/game',         fum / n,                                    '{:.2f}'),
        ('runs 20+/game',        total('runs20plus') / n,                    '{:.2f}'),
        ('runs 30+/game',        total('runs30plus') / n,                    '{:.2f}'),
        ('passes 20+/game',      total('passes20plus') / n,                  '{:.2f}'),
        ('passes 30+/game',      total('passes30plus') / n,                  '{:.2f}'),
        ('passes 40+/game',      total('passes40plus') / n,                  '{:.2f}'),
        ('rush yds/game',        runYds / n,                                 '{:.1f}'),
        ('pass yds/game',        passYds / n,                                '{:.1f}'),
        ('air yds/game',         total('totalAirYards') / n,                 '{:.1f}'),
        ('YAC/game',             total('totalYac') / n,                      '{:.1f}'),
    ]
    kd = total('keyDownPlays')
    if kd > 0:
        metrics.append(('key-down plays/gm',   kd / n,                                  '{:.2f}'))
        metrics.append(('key-down stop %',     100 * total('keyDownStops') / kd,        '{:.1f}'))
    return metrics


def comparison(baselineRows, currentRows):
    """Print headline-metric deltas between baseline and current."""
    base = {k: (v, fmt) for k, v, fmt in headlineMetrics(baselineRows)}
    curr = {k: (v, fmt) for k, v, fmt in headlineMetrics(currentRows)}

    if not base or not curr:
        print('Comparison requires both baseline and current data.')
        return

    print()
    print('=== COMPARISON vs BASELINE ===')
    print(f'  {"metric":22s} {"baseline":>12s} {"current":>12s} {"delta":>10s} {"%chg":>8s}')
    for key in base:
        if key not in curr:
            continue
        bVal, fmt = base[key]
        cVal, _ = curr[key]
        delta = cVal - bVal
        pct = (100 * delta / bVal) if bVal else 0
        # Arrow for direction; suppress noise for tiny deltas
        arrow = '↑' if delta > 0.005 else ('↓' if delta < -0.005 else ' ')
        bStr = fmt.format(bVal)
        cStr = fmt.format(cVal)
        dStr = fmt.format(delta)
        print(f'  {key:22s} {bStr:>12s} {cStr:>12s} {arrow} {dStr:>8s} {pct:>+7.1f}%')


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('path', nargs='?', default='logs/sim_analytics.jsonl')
    ap.add_argument('--season', type=int, default=None)
    ap.add_argument('--week', type=int, default=None)
    ap.add_argument('--from-season', type=int, default=None,
                    help='Include only games from this season onward (inclusive).')
    ap.add_argument('--to-season', type=int, default=None,
                    help='Include only games up to this season (inclusive).')
    ap.add_argument('--baseline', type=str, default=None,
                    help='Compare current log against a baseline log file. '
                         'Prints headline-metric deltas (completion%, YPA, NYA, '
                         'sack rate, INT rate, big plays) after the main report.')
    args = ap.parse_args()
    rows = loadGames(args.path, season=args.season, week=args.week,
                     fromSeason=args.from_season, toSeason=args.to_season)
    report(rows)
    if args.baseline:
        baselineRows = loadGames(args.baseline, season=args.season, week=args.week,
                                 fromSeason=args.from_season, toSeason=args.to_season)
        # If the current log appended on top of the baseline (no truncation),
        # strip the baseline-length prefix off the current rows to isolate the
        # new games. gameId/season/week all collide on fresh starts so payload
        # identity isn't reliable — falling back to position is the only
        # consistent option until log entries carry timestamps.
        if len(rows) > len(baselineRows):
            newRows = rows[len(baselineRows):]
            print()
            print(f'(stripping {len(baselineRows)} baseline-prefix rows → '
                  f'comparing {len(newRows)} new games)')
        else:
            newRows = rows
        comparison(baselineRows, newRows)
