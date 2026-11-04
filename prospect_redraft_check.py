"""Prospect redraft check (docs/PROSPECT_UNCERTAINTY_PLAN.md §4).

Generates rookie classes with the real generator (`PlayerManager._generateRookieClass`),
develops them offseason by offseason with the real training code, and asks the owner's
question: redraft each class five seasons later, does the draft order hold?

A class is "drafted" by a board: the top N (one per team) by that board's expected rating.
Boards: the public CONSENSUS (vision 0, what fans see), an ELITE scout (vision 1), and an
average scout (vision 0.5). The drafted players are then redrafted by the best rating they
reached. NFL reference (2000-15 drafts, nflverse career value, 32-player classes sampled
across each draft): #1 holds 26%, a last-5 pick rises into 5-15 in 67% of classes, 8% of
top-5 picks fall below 16th, rank correlation 0.56, 6.4 slots moved on average.

    .venv/bin/python prospect_redraft_check.py --classes 40
    .venv/bin/python prospect_redraft_check.py --classes 40 --off     # the old model
    .venv/bin/python prospect_redraft_check.py --classes 100 --quick --by-slot   # what picks become

⚠️ Boards here rank by rating alone, not position value, so this measures how predictable
a prospect is, not how a real team drafts. Development runs under one environment per arm
(average, best, worst), so the environment rows show how far apart the same kind of class
ends up.
"""
import argparse
import logging
import os
import random
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
logging.disable(logging.CRITICAL)
os.environ.setdefault('DATABASE_DIR', '/tmp/floo_redraft_check')

import numpy as np
from scipy.stats import spearmanr

import constants
import player_development
from managers.playerManager import PlayerManager

NFL = dict(redraft1_is_pick1=0.26, pick1_redraft_slot_median=4.0, last5_into_5to15=0.67,
           top5_below_16=0.08, rank_corr=0.56, slots_moved=6.4)

ENVIRONMENTS = {
    # (coach playerDevelopment, Training Facility level)
    'average': (83, 3),
    'best': (100, 5),
    'worst': (60, 0),
}


def makeManager(numTeams):
    pm = PlayerManager.__new__(PlayerManager)
    pm.activePlayers = []
    pm.unusedNames = [f'Prospect {i}' for i in range(200000)]
    pm.db_session = None
    pm.serviceContainer = SimpleNamespace(
        getService=lambda name: SimpleNamespace(teams=[None] * numTeams))
    return pm


def developClass(rookies, env, seasons):
    coachDev, level = env
    bonus = constants.FACILITY_CATALOG['training']['levels'][level]
    best = {}
    for p in rookies:
        p.seasonsPlayed = 0
        p.prospect_seasons = 0
    for _ in range(seasons):
        for p in rookies:
            p.offseasonTraining(coachDevRating=coachDev, fundingDevBonus=bonus)
            p.seasonsPlayed += 1
            best[id(p)] = max(best.get(id(p), 0), p.playerRating)
    return best


def redraftStats(classes):
    """`classes`: per class, outcomes in draft order (index 0 = the first pick)."""
    same1, r1, late, topBust, rho, moved = [], [], [], [], [], []
    for c in classes:
        c = np.array(c, float)
        n = len(c)
        order = sorted(range(n), key=lambda i: (-c[i], i))
        rr = np.empty(n, int)
        rr[order] = np.arange(1, n + 1)
        same1.append(rr[0] == 1)
        r1.append(rr[0])
        late.append(any(5 <= rr[i] <= 15 for i in range(n - 5, n)))
        topBust.append(np.mean([rr[i] > 16 for i in range(5)]))
        rho.append(spearmanr(np.arange(n), -c)[0])
        moved.append(np.mean(np.abs(rr - np.arange(1, n + 1))))
    return dict(redraft1_is_pick1=np.mean(same1), pick1_redraft_slot_median=np.median(r1),
                last5_into_5to15=np.mean(late), top5_below_16=np.mean(topBust),
                rank_corr=np.nanmean(rho), slots_moved=np.mean(moved))


# Slot bands for --by-slot: the top three, the rest of the top eight, the middle, the back
# two eighths. 3 stars is the line the front office re-signs at, 4 stars a rising star.
SLOT_BANDS = ((1, 3), (4, 8), (9, 16), (17, 24), (25, 32))


def slotOutcomes(classes):
    """What each slot band became: (band, n, median best, share 3+ stars, share 4+ stars)."""
    out = []
    for lo, hi in SLOT_BANDS:
        vals = [c[k - 1] for c in classes for k in range(lo, hi + 1) if k <= len(c)]
        if not vals:
            continue
        out.append(((lo, hi), len(vals), float(np.median(vals)),
                    float(np.mean([v >= constants.FO_RESIGN_MIN_RATING for v in vals])),
                    float(np.mean([v >= constants.TRADE_RISING_STAR_RATING for v in vals]))))
    return out


def run(args):
    if args.off:
        constants.PROSPECT_TALENT_SHIFT_ENABLED = False
        constants.ROOKIE_CLASS_PER_TEAM = 1.0
        player_development.DEV_LUCK_ENABLED = False
    pm = makeManager(args.teams)
    boards = {'consensus': 0.0, 'average scout': 0.5, 'elite scout': 1.0}
    results = {}
    for envName in (['average'] if args.quick else list(ENVIRONMENTS)):
        env = ENVIRONMENTS[envName]
        perBoard = {b: [] for b in boards}
        missed, shifts, entry, finals = [], [], [], []
        for k in range(args.classes):
            rookies = pm._generateRookieClass(1)
            views = {b: {id(p): p.projectionFor(v)[0] for p in rookies} for b, v in boards.items()}
            best = developClass(rookies, env, args.seasons)
            finals += list(best.values())
            shifts += [p.talentShift for p in rookies]
            for b in boards:
                ranked = sorted(rookies, key=lambda p: -views[b][id(p)])
                drafted = ranked[:args.teams]
                perBoard[b].append([best[id(p)] for p in drafted])
                if b == 'consensus':
                    cut = sorted(best.values(), reverse=True)[args.teams - 1]
                    undrafted = ranked[args.teams:]
                    missed.append(sum(1 for p in undrafted if best[id(p)] > cut))
        results[envName] = {b: redraftStats(v) for b, v in perBoard.items()}
        results[envName]['_bySlot'] = {b: slotOutcomes(v) for b, v in perBoard.items()}
        results[envName]['_extra'] = dict(
            mean_best=np.mean(finals), undrafted_better_than_32nd=np.mean(missed),
            shift_sd=np.std(shifts))
    return results


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--classes', type=int, default=40)
    ap.add_argument('--seasons', type=int, default=5)
    ap.add_argument('--teams', type=int, default=32)
    ap.add_argument('--off', action='store_true', help='the old model: no hidden talent, no luck, one per team')
    ap.add_argument('--quick', action='store_true', help='average environment only')
    ap.add_argument('--seed', type=int, default=None)
    ap.add_argument('--consensus-by-slot', action='store_true',
                    help='the consensus projection at each class rank (no development)')
    ap.add_argument('--by-slot', action='store_true',
                    help='what each slot band became (median best rating, 3- and 4-star shares)')
    args = ap.parse_args()
    if args.seed is not None:
        random.seed(args.seed)
        np.random.seed(args.seed)
    if args.consensus_by_slot:
        pm = makeManager(args.teams)
        ranks = [[] for _ in range(args.teams)]
        for _ in range(args.classes):
            mids = sorted((p.projectionRange(0)[1] for p in pm._generateRookieClass(1)),
                          reverse=True)
            for k in range(args.teams):
                ranks[k].append(mids[k])
        print(tuple(round(float(np.mean(r))) for r in ranks))
        return
    res = run(args)
    keys = list(NFL)
    print(f"{'':28s}" + ''.join(f"{k[:16]:>18s}" for k in keys))
    print(f"{'NFL reference':28s}" + ''.join(f"{NFL[k]:>18.2f}" for k in keys))
    for env, rows in res.items():
        for b, st in rows.items():
            if b in ('_extra', '_bySlot'):
                continue
            print(f"{(env + ' / ' + b):28s}" + ''.join(f"{st[k]:>18.2f}" for k in keys))
        ex = rows['_extra']
        print(f"  {env}: mean best rating {ex['mean_best']:.1f}, undrafted who beat the "
              f"32nd-best drafted {ex['undrafted_better_than_32nd']:.1f}/class, "
              f"talent shift sd {ex['shift_sd']:.1f}")
        if args.by_slot:
            for b, bands in rows['_bySlot'].items():
                print(f"  {env} / {b}: best rating within {args.seasons} seasons, by draft slot")
                for (lo, hi), n, med, three, four in bands:
                    print(f"    picks {lo:2d}-{hi:2d}  n={n:4d}  median {med:5.1f}  "
                          f"3+ stars {three:4.0%}  4+ stars {four:4.0%}")


if __name__ == '__main__':
    main()
