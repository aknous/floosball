"""Flat FP against FPx: how a lineup's split between the two decides its week.

Holds everything fixed except the split. For each k = 0..6, draws contender lineups (every
player from the top quarter at his position, cards drawn evenly across editions, as
`simcheck_effect_marginal.py`'s contender arm does) in which k slots hold flat-FP effects
and 6-k hold FPx effects, and scores each over real weeks through the real two-pass
calculator. Floobit cards are left out: they pay no FP.

Every lineup is also scored under alternative ways of combining FPx, off the same
(raw FP, flat FP, FPx) the calculator produced, so the arms differ only in the formula:

  current     (R + F) x M          M = 1 + sum(f - 1)
  roster      R x M + F            FPx multiplies the players' own FP, not other cards'
  half        R x M + F x (1 + (M - 1) / 2)

`mean` is the average lineup at that split; `top10` the mean of its best tenth, a proxy for
what a deep collection fields at that split. Normal weeks only, tier 1.

  PROBE_DB=path/to/prod.db PROBE_SEASON=9 .venv/bin/python simcheck_archetype.py
  PROBE_LINEUPS=300 lineups per split (default 200), PROBE_WEEKS=4 weeks each
"""
import collections
import os
import random
import sqlite3
import statistics
import sys

os.environ.setdefault('PROBE_ARM', 'contender')
import simcheck_effect_marginal as sm
import managers.cardEffects as ce
from managers.cardEffectCalculator import calculateWeekCardBonuses, aggregateMultFactors
from simcheck_pool_power import livePool, loadWeeks, SLOTS

LINEUPS = int(os.environ.get('PROBE_LINEUPS', '200'))
WEEKS = int(os.environ.get('PROBE_WEEKS', '4'))

FORMULAS = {
    'current': lambda R, F, M: (R + F) * M,
    'roster': lambda R, F, M: R * M + F,
    'half': lambda R, F, M: R * M + F * (1 + (M - 1) / 2),
}


def typedPool(edition, pos, kind):
    return [e for e in livePool(edition, pos) if ce.EFFECT_OUTPUT_TYPE.get(e) == kind]


def drawLineup(k, byPos, meta, rng):
    """Six cards, k of them flat FP, the rest FPx; None if a slot cannot be filled."""
    kinds = ['fp'] * k + ['fpx'] * (6 - k)
    rng.shuffle(kinds)
    used, cards = set(), []
    for (_, pos), kind in zip(SLOTS, kinds):
        for _ in range(30):
            ed = rng.choice(sm.EDITIONS)
            effects = typedPool(ed, pos, kind)
            pool = [x for x in byPos.get(pos, []) if x[0] not in used
                    and meta.get(x[0], ('', 80))[1] >= sm.MIN_RATING[ed] and sm.starOk(x[0], pos, meta)]
            if effects and pool:
                pid, _ = rng.choice(pool)
                name, rating = meta.get(pid, ('Probe', 80))
                cfg = ce.buildEffectConfig(ed, rating, pos, forceEffect=rng.choice(effects))
                cards.append([pid, pos, cfg, ed, rating, name, rng.randint(1, 6)])
                used.add(pid)
                break
        else:
            return None
    return cards


def scoreWeek(cards, wk, byWeek, seasonInfo, seasonsPlayed, extras, user):
    """(R, F, M) for this lineup's players' real week `wk`; None if one did not play."""
    byPid = {pid: stats for rows in byWeek[wk].values() for pid, stats in rows}
    full = []
    for pid, pos, cfg, ed, rating, name, streak in cards:
        if pid not in byPid:
            return None
        full.append((pid, pos, byPid[pid], cfg, ed, rating, name, streak))
    equipped, ctx = sm.buildContext(full, wk, seasonInfo, seasonsPlayed, extras, user)
    res = calculateWeekCardBonuses(equipped, ctx)
    return ctx.weekRawFP, res.totalBonusFP, aggregateMultFactors(res.multFactors or [])


def main():
    conn = sqlite3.connect(f'file:{sm.DB}?mode=ro', uri=True)
    season = int(sm.SEASON) if sm.SEASON else conn.execute(
        "select max(season) from games where status='final'").fetchone()[0]
    byWeek, meta = loadWeeks(conn, season)
    seasonsPlayed = dict(conn.execute("select id, seasons_played from players"))
    seasonInfo = sm.seasonContext(byWeek, meta)
    ratingsByPos = collections.defaultdict(set)
    for byPos in byWeek.values():
        for p, rows in byPos.items():
            for pid, _ in rows:
                ratingsByPos[p].add((meta.get(pid, ('', 0))[1], pid))
    for p, L in ratingsByPos.items():
        r = sorted(x[0] for x in L)
        sm.STAR_FLOOR[p] = r[int(0.75 * (len(r) - 1))]
    extras = sm.loadExtras(conn, season)
    _, _, balances, pickem, results = extras
    weeks = sorted(w for w in byWeek if w >= 3)
    rng = random.Random(sm.SEED)
    print(f"{sm.DB} season {season}: {LINEUPS} contender lineups per split, {WEEKS} weeks each, "
          f"bonus = total - raw FP\n")
    table = {}
    for k in range(7):
        perLineup = {f: [] for f in FORMULAS}
        parts = []
        for _ in range(LINEUPS):
            cards = None
            while cards is None:
                cards = drawLineup(k, byWeek[rng.choice(weeks)], meta, rng)
            sums = {f: [] for f in FORMULAS}
            for wk in rng.sample(weeks, len(weeks)):
                user = (rng.choice(balances), rng.choice(pickem) if pickem else None,
                        rng.choice(sorted(results[wk])) if results.get(wk) else 0)
                seed = rng.random()
                random.seed(seed)
                got = scoreWeek(cards, wk, byWeek, seasonInfo, seasonsPlayed, extras, user)
                if got is None:
                    continue
                R, F, M = got
                parts.append((R, F, M))
                for f, fn in FORMULAS.items():
                    sums[f].append(fn(R, F, M) - R)
                if len(sums['current']) >= WEEKS:
                    break
            if sums['current']:
                for f in FORMULAS:
                    perLineup[f].append(statistics.mean(sums[f]))
        row = {}
        for f, vals in perLineup.items():
            s = sorted(vals)
            row[f] = (statistics.mean(s), statistics.mean(s[-max(1, len(s) // 10):]))
        table[k] = (row, statistics.mean(p[0] for p in parts), statistics.mean(p[1] for p in parts),
                    statistics.mean(p[2] for p in parts))
        print(f"  split {k} FP / {6 - k} FPx done", file=sys.stderr)
    print(f" {'FP/FPx':7} {'raw':>5} {'flat':>6} {'FPx':>5}   " +
          '   '.join(f"{f:>8} mean/top10" for f in FORMULAS))
    for k, (row, R, F, M) in table.items():
        print(f"  {k}/{6 - k}   {R:5.0f} {F:6.0f} {M:5.2f}   " +
              '   '.join(f"{row[f][0]:8.0f} /{row[f][1]:6.0f}" for f in FORMULAS))


if __name__ == '__main__':
    main()
