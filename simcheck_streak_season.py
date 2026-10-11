"""Season replay for streak cards WITH their carried state (Bonsai, Metronome and peers).

`simcheck_streak_replay.py` covers only the stat-ladder streaks, whose whole state is the
count; a card that carries a peak (or, like Metronome, never resets, or like Bonsai grows
on a roll) needs the week-end machinery itself. This drives the REAL code each week:

  SeasonManager._prepareStreakContext   pre-scoring bump of the count this week pays at
  calculateWeekCardBonuses              the week's score
  SeasonManager._advanceStreaks         post-scoring count, carried peak, Bonsai's growth

over one real player's regular season of weekly stat lines, and reports what the card paid
per week on average and late in the season. FPx output is converted to FP through the hand
it sits in: value = FP + (FPx - 1) x (roster FP + flat card FP).

Non-streak prismatic cards are replayed the same way as a yardstick (REFERENCE), so the
comparison is like for like. The other slots hold blank cards on real contender players for
the whole season. Two arms: the card alone (the rest of the hand blank), and
with PEERS other streak cards in the hand, since every other streak card adds a growth
tick to an active streak (`peerBonus` in _computeStreakEffect).

  PROBE_DB=... PROBE_SEASON=1 .venv/bin/python simcheck_streak_season.py
"""
import collections
import os
import random
import sqlite3
import statistics
import sys

DB = os.environ.get('PROBE_DB', 'data/floosball.db')
SEASON = int(os.environ.get('PROBE_SEASON', '1'))
PLAYERS = int(os.environ.get('PROBE_PLAYERS', '40'))
SEED = int(os.environ.get('PROBE_SEED', '3'))
os.environ.setdefault('DATABASE_DIR', os.path.dirname(os.path.abspath(DB)) or '.')
os.environ.setdefault('PROBE_ARM', 'contender')

import logging
logging.disable(logging.WARNING)

import managers.cardEffects as ce
from managers.cardEffectCalculator import calculateWeekCardBonuses, aggregateMultFactors
from managers.seasonManager import SeasonManager
import simcheck_effect_marginal as H
from simcheck_pool_power import livePool, SLOTS

TARGETS = os.environ.get('PROBE_ONLY', '').split(',') if os.environ.get('PROBE_ONLY') else None
REFERENCE = ['odometer', 'avalanche', 'traverse', 'houdini', 'promised_land']
PEER_POOL = sorted(n for n, cfg in ce.STREAK_CONFIGS.items()
                   if not cfg.get('isWeekly') and cfg.get('resetCondition') != 'equipped'
                   and n in ce.EFFECT_EDITION_TIER)


def seasonLines(byWeek, meta, pos, edition):
    """{pid: {week: stats}} for eligible stars with a nearly full season."""
    lines = collections.defaultdict(dict)
    for wk, byPos in byWeek.items():
        for pid, stats in byPos.get(pos, []):
            if meta.get(pid, ('', 0))[1] >= H.MIN_RATING[edition] and H.starOk(pid, pos, meta):
                lines[pid][wk] = stats
    return {pid: w for pid, w in lines.items() if len(w) >= 24}


def replay(effect, edition, pos, pid, weeks, peerPicks, fillers, byWeek, meta, ctxArgs, sm):
    """One season of `effect` on player `pid`, optionally beside streak peers. `fillers`
    are blank cards on real players for the remaining slots, held all season, so an FPx
    card converts against a full lineup's FP rather than one player's."""
    hand = [H._card(pid, pos, None, effect, edition, meta, 1)]
    for p2, e2, ed2, pid2 in peerPicks:
        hand.append(H._card(pid2, p2, None, e2, ed2, meta, 1))
    for p2, pid2 in fillers:
        hand.append(H._card(pid2, p2, None, None, 'metallic', meta, 1))
    equipped = None
    paid = []
    for wk in sorted(byWeek):
        if wk not in weeks:
            continue
        rows = {x[0]: x[1] for p in byWeek[wk].values() for x in p}
        cards = [(c[0], c[1], rows.get(c[0], {"fantasyPoints": 0}), c[3], c[4], c[5], c[6], c[7])
                 for c in hand]
        equipped, ctx = H.buildContext(cards, wk, *ctxArgs, equipped=equipped)
        if equipped and getattr(equipped[0], 'peak_output', None) is None:
            pass
        sm._prepareStreakContext(equipped, ctx, '')
        res = calculateWeekCardBonuses(equipped, ctx)
        b = next(x for x in res.cardBreakdowns if x.slotNumber == equipped[0].slot_number)
        base = ctx.weekRawFP + res.totalBonusFP
        paid.append(b.totalFP + max(0.0, (b.primaryMult or 0) - 1) * base)
        sm._advanceStreaks(equipped, ctx, '', None)
    return paid


def main():
    conn = sqlite3.connect(f'file:{DB}?mode=ro', uri=True)
    byWeek, meta = H.loadWeeks(conn, SEASON)
    seasonsPlayed = dict(conn.execute("select id, seasons_played from players"))
    seasonInfo = H.seasonContext(byWeek, meta)
    ratingsByPos = collections.defaultdict(set)
    for bp in byWeek.values():
        for p, rows in bp.items():
            for pid, _ in rows:
                ratingsByPos[p].add((meta.get(pid, ('', 0))[1], pid))
    for p, L in ratingsByPos.items():
        r = sorted(x[0] for x in L)
        H.STAR_FLOOR[p] = r[int(0.75 * (len(r) - 1))]
    extras = H.loadExtras(conn, SEASON)
    _, _, bal, pk, res = extras
    wk0 = sorted(res)[len(res) // 2]
    ctxArgs = (seasonInfo, seasonsPlayed, extras,
               (statistics.median(bal), pk[0] if pk else None, sorted(res[wk0])[0]))
    sm = SeasonManager.__new__(SeasonManager)
    rng = random.Random(SEED)
    random.seed(SEED)

    targets = TARGETS or (['metronome', 'bonsai'] +
                          [n for n in PEER_POOL if ce.EFFECT_EDITION_TIER[n] == 'prismatic'
                           and n not in ('metronome', 'bonsai')] + REFERENCE)
    print(f"{DB} season {SEASON}: per-week value over a season, contender players\n")
    print(f"  {'card':20}{'alone':>8}{'late':>7}{'+2 peers':>10}{'late':>7}   by position (alone)")
    for effect in targets:
        edition = ce.EFFECT_EDITION_TIER[effect]
        positions = [p for p in (1, 2, 3, 4, 5) if effect in livePool(edition, p)]
        arms = {0: [], 2: []}
        late = {0: [], 2: []}
        byPos = collections.defaultdict(list)
        for pos in positions:
            lines = seasonLines(byWeek, meta, pos, edition)
            pids = sorted(lines)
            rng.shuffle(pids)
            for pid in pids[:max(1, PLAYERS // len(positions))]:
                for peers in (0, 2):
                    picks = []
                    if peers:
                        free = [p for _, p in SLOTS if p != pos]
                        rng.shuffle(free)
                        for p2 in free:
                            if len(picks) == peers:
                                break
                            opts = [(e2, ce.EFFECT_EDITION_TIER[e2]) for e2 in PEER_POOL
                                    if e2 != effect and e2 in livePool(ce.EFFECT_EDITION_TIER[e2], p2)]
                            if not opts:
                                continue
                            e2, ed2 = rng.choice(opts)
                            cand = seasonLines(byWeek, meta, p2, ed2)
                            cand.pop(pid, None)
                            if cand:
                                picks.append((p2, e2, ed2, rng.choice(sorted(cand))))
                    taken = {pid} | {x[3] for x in picks}
                    open_ = [p for _, p in SLOTS]
                    open_.remove(pos)
                    for x in picks:
                        open_.remove(x[0])
                    fillers = []
                    for p2 in open_:
                        cand = [c for c in sorted(seasonLines(byWeek, meta, p2, 'metallic'))
                                if c not in taken]
                        if cand:
                            c = rng.choice(cand)
                            taken.add(c)
                            fillers.append((p2, c))
                    paid = replay(effect, edition, pos, pid, lines[pid], picks, fillers,
                                  byWeek, meta, ctxArgs, sm)
                    if paid:
                        arms[peers].append(statistics.mean(paid))
                        late[peers].append(statistics.mean(paid[-7:]))
                        if peers == 0:
                            byPos[pos].append(statistics.mean(paid))
        if not arms[0]:
            continue
        tag = ' (ref)' if effect in REFERENCE else ''
        print(f"  {effect + tag:20}{statistics.mean(arms[0]):8.0f}{statistics.mean(late[0]):7.0f}"
              f"{statistics.mean(arms[2]):10.0f}{statistics.mean(late[2]):7.0f}   "
              + ' '.join(f"{H.POS_NAME[p]}{statistics.mean(v):.0f}" for p, v in byPos.items()))
        sys.stdout.flush()


if __name__ == '__main__':
    main()
