"""Play-calling harness — does this league call plays like football?

Boots the real engine headless over a fixed pool of synthetic teams, records the pre-snap
state and the call on EVERY snap, and compares the result with NFL play-by-play
(nflverse, 2021-25) bucket by bucket. Modelled on `trade_market_check.py`.

⚠️ THE HOOK IS `Game.playCaller`, NOT THE PLAY FEED. The whole play resolves inside it, so
a wrapper there sees the true pre-snap state. `Play`'s own fields are post-play in places
(`timeRemaining`, the scores on a scoring play) and turn yards-to-go into the string
'Goal' inside the 10, so a feed-based harvest measures the wrong situation.

⚠️ SEED THE ROSTERS. Player generation draws from the global random/numpy streams, so two
arms otherwise identical play different leagues: measured, that alone moved scoring by
1.6 points a game and buried every effect worth reading.

⚠️ `Team.getAverages` IS STUBBED. It queries the games table after every game and only
feeds the API's display stats, so the harness would otherwise need a database.

Usage:
    .venv/bin/python playcall_nfl_check.py --games 2000 --nfl /path/to/nflverse
    .venv/bin/python playcall_nfl_check.py --games 500 --out arm.csv     # keep the rows
    .venv/bin/python playcall_nfl_check.py --compare a.csv b.csv         # two saved arms

`--nfl` is a directory of nflverse season files (pbp_YYYY.csv.gz), from
https://github.com/nflverse/nflverse-data/releases/tag/pbp — the NFL half is skipped
when it is absent, so the sim numbers still print.
"""
import argparse
import asyncio
import csv
import logging
import os
import random
import sys
import types
import warnings

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
logging.disable(logging.CRITICAL)
warnings.filterwarnings('ignore')

if 'floosball_game' not in sys.modules:          # the circular-import dance the sim tests use
    _stub = types.ModuleType('floosball_game')
    _stub.Game = type('G', (), {})
    sys.modules['floosball_game'] = _stub
    import managers.timingManager                                        # noqa: F401
    del sys.modules['floosball_game']

import numpy as np                                                       # noqa: E402
import floosball_game as FG                                              # noqa: E402
import floosball_team as FT                                              # noqa: E402
from managers.timingManager import TimingManager, TimingMode             # noqa: E402
from game_rules import GameRules                                         # noqa: E402
from scenario import _makeTeam                                           # noqa: E402

FT.Team.getAverages = lambda self, season=None: None
PT, PassType = FG.PlayType, FG.PassType
FIELDS = ['game', 'team', 'down', 'ytg', 'yte', 'qtr', 'qsecs', 'scoreDiff', 'offTo', 'defTo',
          'kind', 'called', 'thrown', 'scramble', 'sack', 'complete', 'intercepted', 'yards',
          # the pass model's own inputs, so a completion or a pick can be explained rather
          # than only counted. `open` is the ACTUAL gap the QB threw into (not perceived)
          # BEFORE `_depthClosing` is applied inside calculateCatchProbability; `bestOpen`
          # is the most open man on the field, so the two together measure how much the
          # read's take-the-open-man rule is doing.
          'openN', 'throwQ', 'nTgt', 'bestOpen']


def harvest(games: int, seed: int = 20260914):
    """Play `games` matchups and return (snap rows, final scores)."""
    rng = random.Random(424242)
    random.seed(seed)
    np.random.seed(seed)
    teams = []
    for t in range(32):
        team = _makeTeam(f'T{t}', f'T{t:02d}', 10000 + t * 100,
                         phys=rng.randint(74, 92), ment=rng.randint(74, 92),
                         defRun=rng.randint(70, 88), defPass=rng.randint(70, 88))
        team.id = t
        np.random.seed(900 + t)          # `seed` on generateAttributes is the CENTER, not an RNG seed
        team.coach.generateAttributes()
        teams.append(team)

    rows, scores, current = [], [], {'game': None}
    original = FG.Game.playCaller

    def hooked(game):
        off = game.offensiveTeam
        isHome = off is game.homeTeam
        pre = dict(game=current['game'], team=off.id, down=game.down, ytg=game.yardsToFirstDown,
                   yte=game.yardsToEndzone, qtr=game.currentQuarter, qsecs=game.gameClockSeconds,
                   scoreDiff=((game.homeScore - game.awayScore) * (1 if isHome else -1)),
                   offTo=(game.homeTimeoutsRemaining if isHome else game.awayTimeoutsRemaining),
                   defTo=(game.awayTimeoutsRemaining if isHome else game.homeTimeoutsRemaining))
        original(game)
        p = game.play
        pt = getattr(p, 'playType', None)
        scramble, sack = bool(getattr(p, 'isScramble', False)), bool(getattr(p, 'isSack', False))
        kind = ('pass' if (pt is PT.Pass or scramble or sack) else
                'run' if pt is PT.Run else 'fg' if pt is PT.FieldGoal else
                'punt' if pt is PT.Punt else 'kneel' if pt is PT.Kneel else
                'spike' if pt is PT.Spike else str(pt))
        passT = getattr(p, 'passType', None)
        pre.update(kind=kind, called=(getattr(p, 'insights', {}) or {}).get('playCall', ''),
                   thrown=(passT.name if isinstance(passT, PassType) and kind == 'pass'
                           and not scramble and not sack else ''),
                   scramble=int(scramble), sack=int(sack),
                   complete=int(bool(getattr(p, 'isPassCompletion', False))),
                   intercepted=int(bool(getattr(p, 'isInterception', False))),
                   yards=getattr(p, 'yardage', 0))
        ins = ((getattr(p, 'insights', {}) or {}).get('pass') or {})
        tgts = ins.get('targets') or []
        pre.update(openN=ins.get('rcvActualOpenness', ''), throwQ=ins.get('throwQuality', ''),
                   nTgt=len(tgts),
                   bestOpen=(max((t.get('openness', 0) for t in tgts), default='')))
        rows.append(pre)

    FG.Game.playCaller = hooked
    try:
        for g in range(games):
            home, away = rng.sample(teams, 2)
            game = FG.Game(home, away, gameRules=GameRules(),
                           timingManager=TimingManager(TimingMode.FAST))
            game.id = g
            current['game'] = g
            asyncio.run(asyncio.wait_for(game.playGame(), timeout=120))
            scores.append(game.homeScore + game.awayScore)
    finally:
        FG.Game.playCaller = original
    return rows, scores


# ── the comparison ──────────────────────────────────────────────────────────
YTG_EDGES = [0, 1, 3, 6, 9, 10, 15, 99]
YTG_LABELS = ['1', '2-3', '4-6', '7-9', '10', '11-15', '16+']


def _late(r):
    return r['qtr'] in (2, 4) and r['qsecs'] <= 120


def _scrim(rows):
    return [r for r in rows if r['kind'] in ('run', 'pass')]


def _rate(rows):
    rows = _scrim(rows)
    return (100.0 * sum(r['kind'] == 'pass' for r in rows) / len(rows)) if rows else None


def _bucket(v, edges, labels):
    for edge, label in zip(edges[1:], labels):
        if v <= edge:
            return label
    return labels[-1]


def _downDistance(rows):
    out = {}
    for r in _scrim(rows):
        if r['down'] > 3 or abs(r['scoreDiff']) > 7 or _late(r):
            continue
        out.setdefault((r['down'], _bucket(r['ytg'], YTG_EDGES, YTG_LABELS)), []).append(r)
    return out


def _margins(rows):
    edges = [-99, -15, -9, -4, -1, 0, 3, 8, 14, 99]
    labels = ['<=-15', '-14..-9', '-8..-4', '-3..-1', '0', '+1..+3', '+4..+8', '+9..+14', '>=+15']
    out = {}
    for r in _scrim(rows):
        if r['qtr'] not in (3, 4) or _late(r) or r['down'] > 3:
            continue
        out.setdefault(_bucket(r['scoreDiff'], edges, labels), []).append(r)
    return out


def _lateLead(rows):
    return _rate([r for r in rows if r['qtr'] == 4 and r['qsecs'] <= 120
                  and r['scoreDiff'] > 0 and r['down'] <= 3])


def _depthMix(rows):
    tiers = ['short', 'medium', 'long', 'deep']
    thrown = [r['thrown'] for r in rows if r['thrown'] in tiers]
    return ({t: 100.0 * thrown.count(t) / len(thrown) for t in tiers} if thrown else None)


def loadNfl(directory):
    """Flatten nflverse seasons into the same row shape. A 'pass' is any DROPBACK, so
    sacks and scrambles count as the pass calls they were — the same rule the sim side
    uses. Depth bins sit at the midpoints between the sim's tier means."""
    import gzip
    rows = []
    files = sorted(f for f in os.listdir(directory) if f.startswith('pbp_') and f.endswith('.csv.gz'))
    for name in files:
        with gzip.open(os.path.join(directory, name), 'rt') as fh:
            for rec in csv.DictReader(fh):
                kind = {'punt': 'punt', 'field_goal': 'fg', 'qb_kneel': 'kneel',
                        'qb_spike': 'spike'}.get(rec['play_type'])
                if kind is None:
                    if rec['play_type'] == 'pass' or rec.get('qb_dropback') == '1':
                        kind = 'pass'
                    elif rec['play_type'] == 'run':
                        kind = 'run'
                    else:
                        continue
                try:
                    down = int(float(rec['down'] or 0))
                    if not down:
                        continue
                    air = rec.get('air_yards')
                    thrown = ''
                    if rec.get('pass_attempt') == '1' and rec.get('sack') != '1' \
                            and rec.get('qb_scramble') != '1' and air not in (None, '', 'NA'):
                        a = float(air)
                        thrown = ('short' if a < 6 else 'medium' if a < 13 else
                                  'long' if a < 22 else 'deep')
                    rows.append(dict(
                        game=rec['game_id'], team=rec['posteam'], down=down,
                        ytg=int(float(rec['ydstogo'] or 0)), yte=float(rec['yardline_100'] or 0),
                        qtr=int(float(rec['qtr'] or 0)),
                        qsecs=float(rec['quarter_seconds_remaining'] or 0),
                        scoreDiff=float(rec['score_differential'] or 0), offTo=0, defTo=0,
                        kind=kind, called='', thrown=thrown,
                        scramble=int(rec.get('qb_scramble') == '1'),
                        sack=int(rec.get('sack') == '1'),
                        complete=int(rec.get('complete_pass') == '1'),
                        intercepted=int(rec.get('interception') == '1'),
                        yards=float(rec['yards_gained'] or 0)))
                except (ValueError, KeyError):
                    continue
    return rows


DOWN = {1: '1st', 2: '2nd', 3: '3rd'}


def report(arms, nfl):
    """arms: [(label, rows, scores)]. Gaps are the mean absolute difference from the NFL
    in percentage points, over buckets both sides hold."""
    labels = [a[0] for a in arms]
    width = max(9, max(len(l) for l in labels) + 1)
    head = lambda name: f'{name:<34}' + ''.join(f'{l:>{width}}' for l in labels) + ('       NFL' if nfl else '')

    def line(name, values, nflValue=None, fmt='{:.1f}'):
        cells = ''.join(f'{(fmt.format(v) if v is not None else "--"):>{width}}' for v in values)
        tail = f'{(fmt.format(nflValue) if nflValue is not None else "--"):>10}' if nfl else ''
        print(f'{name:<34}{cells}{tail}')

    nflDD = _downDistance(nfl) if nfl else {}
    nflMargin = _margins(nfl) if nfl else {}
    print(head('measure'))
    if nfl:
        for key, label in (('dd', 'GAP down & distance (pts)'), ('margin', 'GAP score margin (pts)')):
            gaps = []
            for _l, rows, _s in arms:
                mine = _downDistance(rows) if key == 'dd' else _margins(rows)
                theirs = nflDD if key == 'dd' else nflMargin
                diffs = [abs(_rate(mine[k]) - _rate(theirs[k])) for k in mine
                         if k in theirs and len(mine[k]) >= 250 and len(theirs[k]) >= 100]
                gaps.append(sum(diffs) / len(diffs) if diffs else None)
            line(label, gaps)
    line('pass rate, all snaps %', [_rate(r) for _l, r, _s in arms], _rate(nfl) if nfl else None)
    line('leading, final 2:00, pass %', [_lateLead(r) for _l, r, _s in arms],
         _lateLead(nfl) if nfl else None)
    for down in (1, 2, 3):
        for ytg in YTG_LABELS:
            vals, nflVal = [], None
            for _l, rows, _s in arms:
                cell = _downDistance(rows).get((down, ytg), [])
                vals.append(_rate(cell) if len(cell) >= 250 else None)
            cell = nflDD.get((down, ytg), [])
            nflVal = _rate(cell) if len(cell) >= 100 else None
            if any(v is not None for v in vals):
                line(f'  {DOWN[down]} & {ytg} pass %', vals, nflVal)
    tiers = ['short', 'medium', 'long', 'deep']
    for tier in tiers:
        mixes = [(_depthMix(r) or {}).get(tier) for _l, r, _s in arms]
        line(f'  thrown {tier} %', mixes, (_depthMix(nfl) or {}).get(tier) if nfl else None)
    # Counted off the rows, never off `scores` — a saved arm reloaded with --compare has no
    # scores, and dividing by a placeholder silently prints volumes in the thousands.
    teamGames = lambda rows: len({(r['game'], r['team']) for r in rows}) or 1
    for name, kind in (('runs', 'run'), ('passes', 'pass'), ('punts', 'punt'), ('FG tries', 'fg')):
        vals = [sum(r['kind'] == kind for r in rows) / teamGames(rows) for _l, rows, _s in arms]
        nflVal = (sum(r['kind'] == kind for r in nfl) / teamGames(nfl)) if nfl else None
        line(f'OUT {name} / team-game', vals, nflVal, fmt='{:.2f}')
    if any(len(s) > 1 for _l, _r, s in arms):
        line('OUT points / game',
             [(sum(s) / len(s)) if len(s) > 1 else None for _l, _r, s in arms], None)


def save(rows, path):
    with open(path, 'w', newline='') as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def load(path):
    ints = {'game', 'down', 'ytg', 'qtr', 'scramble', 'sack', 'complete', 'intercepted'}
    out = []
    with open(path) as fh:
        for rec in csv.DictReader(fh):
            row = {k: (int(v) if k in ints and v not in ('', None) else v) for k, v in rec.items()}
            for k in ('yte', 'qsecs', 'scoreDiff', 'yards'):
                row[k] = float(row[k] or 0)
            for k in ('openN', 'throwQ', 'nTgt', 'bestOpen'):   # absent on an NFL row
                if k in row:
                    row[k] = float(row[k]) if row[k] not in ('', None) else None
            out.append(row)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--games', type=int, default=2000)
    ap.add_argument('--nfl', default=os.environ.get('FLOOS_NFL_PBP', ''),
                    help='directory of nflverse pbp_YYYY.csv.gz files')
    ap.add_argument('--out', default='', help='save the harvested rows here')
    ap.add_argument('--compare', nargs='+', default=[], help='report saved arms instead of playing')
    args = ap.parse_args()

    nfl = loadNfl(args.nfl) if args.nfl and os.path.isdir(args.nfl) else []
    if nfl:
        print(f'NFL reference: {len(nfl):,} snaps')
    else:
        print('NFL reference: none (pass --nfl to compare)')

    if args.compare:
        arms = [(os.path.basename(p).replace('.csv', ''), load(p), [0]) for p in args.compare]
        report([(l, r, [1]) for l, r, _s in arms], nfl)
        return 0

    rows, scores = harvest(args.games)
    print(f'{args.games} games, {len(rows):,} snaps\n')
    if args.out:
        save(rows, args.out)
    report([('this build', rows, scores)], nfl)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
