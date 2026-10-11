"""Season replay for streak cards WITH their carried state (Bonsai, Metronome and peers).

`simcheck_streak_replay.py` covers only the stat-ladder streaks, whose whole state is the
count; a card that carries a peak (or, like Metronome, never resets, or like Bonsai grows
on a roll) needs the week-end machinery itself. This drives the REAL code each week:

  SeasonManager._prepareStreakContext   pre-scoring bump of the count this week pays at
  calculateWeekCardBonuses              the week's score
  SeasonManager._advanceStreaks         post-scoring count, carried peak, Bonsai's growth

over one real player's regular season of weekly stat lines, and reports what the card paid
per week on average and late in the season, as a MARGINAL value: the hand played with the
card against the same hand with a blank print of that player, side by side all season.

Non-streak prismatic cards are replayed the same way as a yardstick (REFERENCE), so the
comparison is like for like. The other five slots hold real cards (contender players, an
even edition mix) for the whole season. Two arms: those five drawn at random, and with two
of them forced to be streak cards, since every other streak card adds a growth tick to an
active streak (`peerBonus` in _computeStreakEffect).

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
# Hands per player: the season value swings with the five cards around the target (one
# draw holding Lemons or Captain moves a whole season), so each player is averaged over
# several held hands and the table reports a standard error.
HANDS = int(os.environ.get('PROBE_HANDS', '4'))
# Nose Picker's streak holds on a week the USER submitted every pick by hand. A replay
# cannot decide that, so it is drawn per week at this rate (prod: holders hand-submitted
# 85-100% of weeks in seasons 5-6).
MANUAL_PICK_RATE = float(os.environ.get('PROBE_MANUAL_PICK_RATE', '0.95'))
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


def replay(effect, edition, pos, pid, weeks, others, byWeek, meta, ctxArgs, sm):
    """One season of `effect` on player `pid` in a held hand, as a MARGINAL value.

    Two hands play the season side by side: one with the card, one with a blank print of
    the same player in its slot. `others` are the other five cards (real effects on real
    players, held all season) and each hand carries its own copy of their streak state. The
    week's value is total(with) - total(without), the same reading as
    simcheck_effect_marginal.py: FPx converts against the real lineup, and any streak tick
    the card adds to its neighbours (peerBonus) is counted."""
    target = H._card(pid, pos, None, effect, edition, meta, 1)
    blank = H._card(pid, pos, None, None, edition, meta, 1)
    hands = {'with': [target] + others, 'without': [blank] + others}
    equipped = {'with': None, 'without': None}
    paid = []
    for wk in sorted(byWeek):
        if wk not in weeks:
            continue
        rows = {x[0]: x[1] for p in byWeek[wk].values() for x in p}
        seed = hash((pid, wk, effect)) & 0xFFFFFFFF
        totals = {}
        for arm in ('with', 'without'):
            cards = [(c[0], c[1], rows.get(c[0], {"fantasyPoints": 0}), c[3], c[4], c[5], c[6], c[7])
                     for c in hands[arm]]
            eqs, ctx = H.buildContext(cards, wk, *ctxArgs, equipped=equipped[arm])
            equipped[arm] = eqs
            ctx.userManualPickSubmittedThisWeek = random.Random(seed ^ 0x5EED).random() < MANUAL_PICK_RATE
            random.seed(seed)
            sm._prepareStreakContext(eqs, ctx, '')
            res = calculateWeekCardBonuses(eqs, ctx)
            totals[arm] = (ctx.weekRawFP + res.totalBonusFP) * aggregateMultFactors(res.multFactors or [])
            random.seed(seed + 1)
            sm._advanceStreaks(eqs, ctx, '', None)
        paid.append(totals['with'] - totals['without'])
    return paid


def buildOthers(pos, pid, peers, byWeek, meta, rng, effect):
    """The other five cards: real effects on real contender players, held all season.
    `peers` of them are forced to be streak cards."""
    slots = [p for _, p in SLOTS]
    slots.remove(pos)
    rng.shuffle(slots)
    taken = {pid}
    others = []
    for i, p2 in enumerate(slots):
        if i < peers:
            opts = [(e2, ce.EFFECT_EDITION_TIER[e2]) for e2 in PEER_POOL
                    if e2 != effect and e2 in livePool(ce.EFFECT_EDITION_TIER[e2], p2)]
        else:
            opts = []
            for _ in range(20):
                ed2 = rng.choices([e for e, _ in H.PACK_WEIGHTS],
                                  weights=[w for _, w in H.PACK_WEIGHTS])[0]
                eff = livePool(ed2, p2)
                if eff:
                    opts = [(rng.choice(eff), ed2)]
                    break
        rng.shuffle(opts)
        for e2, ed2 in opts:
            cand = [c for c in sorted(seasonLines(byWeek, meta, p2, ed2)) if c not in taken]
            if cand:
                c = rng.choice(cand)
                taken.add(c)
                others.append(H._card(c, p2, None, e2, ed2, meta, 1))
                break
    return others


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
    print(f"  {'card':20}{'season ±se':>10}{'late':>5}{'+2 peers':>10}{'late':>7}   by position")
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
                    for _ in range(HANDS):
                        others = buildOthers(pos, pid, peers, byWeek, meta, rng, effect)
                        paid = replay(effect, edition, pos, pid, lines[pid], others,
                                      byWeek, meta, ctxArgs, sm)
                        if paid:
                            arms[peers].append(statistics.mean(paid))
                            late[peers].append(statistics.mean(paid[-7:]))
                            if peers == 0:
                                byPos[pos].append(statistics.mean(paid))
        if not arms[0]:
            continue
        tag = ' (ref)' if effect in REFERENCE else ''
        se = statistics.stdev(arms[0]) / len(arms[0]) ** 0.5 if len(arms[0]) > 1 else 0.0
        print(f"  {effect + tag:20}{statistics.mean(arms[0]):6.0f}±{se:<3.0f}{statistics.mean(late[0]):5.0f}"
              f"{statistics.mean(arms[2]):10.0f}{statistics.mean(late[2]):7.0f}   "
              + ' '.join(f"{H.POS_NAME[p]}{statistics.mean(v):.0f}" for p, v in byPos.items()))
        sys.stdout.flush()


if __name__ == '__main__':
    main()
