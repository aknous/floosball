"""What each card ADDS to a normal week, measured inside a realistic lineup.

For every mintable (effect, edition, position) this drops the card into a lineup whose
other five cards are drawn at the real pack rates, scores the week through the real
two-pass calculator, then scores it again with the card swapped for a no-effect print of
the SAME player. The difference is the card's marginal value in FP, FPx converted to FP
through the lineup it is actually in:

  total = (rawPlayerFP + sum bonusFP) * aggregate FPx
  marginal = total(with card) - total(with a blank print of the same player)

Normal weeks only (no weekly modifier, no Criticality), tier 1, live path (the FP power
bar is on/off, not EV-scaled), at the CURRENT constants, so it reads whatever the gate
table and builders say now. Players are drawn from those eligible for the edition
(holo >= 75, prismatic >= 80, diamond >= 90), as minting does.

Context filled from the same database: real team ids and Q4 FP on each stat line, a
Floobit balance drawn from real users, a real user-week of pick-em results, and a
favorite team drawn at random with that week's real result and season record.

⚠️ BLIND SPOTS, so a low number is a finding only after checking it is not one of these:
  * streak cards are scored at a streak drawn 1-6, not grown over a season;
  * favorite-team STREAK cards see no streak;
  * the other five cards are random, so synergy cards (Stacked Deck, Gold Rush) see a
    pack-weighted hand rather than one built for them; see the BUILT arm.

  PROBE_DB=path/to/prod.db PROBE_SEASON=8 .venv/bin/python simcheck_effect_marginal.py
"""
import collections
import json
import os
import random
import sqlite3
import statistics
import sys

DB = os.environ.get('PROBE_DB', 'data/floosball.db')
SEASON = os.environ.get('PROBE_SEASON')
TRIALS = int(os.environ.get('PROBE_TRIALS', '60'))
SEED = int(os.environ.get('PROBE_SEED', '7'))
ONLY = set(filter(None, os.environ.get('PROBE_ONLY', '').split(',')))

os.environ.setdefault('DATABASE_DIR', os.path.dirname(os.path.abspath(DB)) or '.')
import logging
logging.disable(logging.WARNING)

import managers.cardEffects as ce
from managers.cardEffectCalculator import (CardCalcContext, calculateWeekCardBonuses,
                                           aggregateMultFactors)
from simcheck_pool_power import _Template, _UserCard, _Equipped, livePool, loadWeeks, SLOTS

EDITIONS = ['metallic', 'holographic', 'prismatic', 'diamond']
MIN_RATING = {'metallic': 0, 'holographic': 75, 'prismatic': 80, 'diamond': 90}
PACK_WEIGHTS = [('metallic', 100), ('holographic', 25), ('prismatic', 10), ('diamond', 2)]
# PROBE_ARM=contender: the lineup a leaderboard contender fields. Every player is from the
# top quarter by rating at his position, and the other five cards are drawn evenly across
# editions (a deep collection), not at pack rates. Cards that pay off stars or a built hand
# (Eminence, Stacked Deck, Lemons, Captain) only show their real value here.
ARM = os.environ.get('PROBE_ARM', 'pack')
# PROBE_ARM=built: each target card in a contender hand BUILT for it. Its partners are found
# empirically (companionPool): a card is a partner when pairing it with the target scores
# differently from the two apart. Amplifiers (Doubler, Conductor, Captain, ...) produce
# nothing of their own, so a random hand rarely holds what they act on; this is the arm that
# says what they are worth when deployed as intended.
if ARM in ('contender', 'built'):
    PACK_WEIGHTS = [('metallic', 1), ('holographic', 1), ('prismatic', 1), ('diamond', 1)]
STAR_FLOOR = {}
POS_NAME = {1: 'QB', 2: 'RB', 3: 'WR', 4: 'TE', 5: 'K'}


def blankConfig():
    return {'effectName': 'none', 'primary': {}, 'category': '', 'outputType': ''}


def loadExtras(conn, season):
    """Everything the card context reads that a stat line does not carry."""
    teamOf, q4 = {}, {}
    for pid, week, tid, q4fp in conn.execute(
            """select g.player_id, gm.week, g.team_id, g.q4_fantasy_points
               from game_player_stats g join games gm on gm.id = g.game_id
               where gm.season = ? and gm.is_playoff = 0""", (season,)):
        teamOf[(pid, week)] = tid or 0
        q4[(pid, week)] = q4fp or 0
    balances = [b for (b,) in conn.execute(
        "select balance from user_currency where balance > 0")] or [0]
    pickem = [r for r in conn.execute(
        """select sum(case when correct = 1 then 1 else 0 end), count(*),
                  coalesce(sum(points_earned), 0)
           from pick_em_picks where season = ? group by user_id, week""", (season,))]
    results = collections.defaultdict(dict)   # week -> team -> (won, oppTeam)
    for week, h, a, hs, as_ in conn.execute(
            """select week, home_team_id, away_team_id, home_score, away_score from games
               where season = ? and status = 'final' and is_playoff = 0""", (season,)):
        results[week][h] = (hs > as_, a)
        results[week][a] = (as_ > hs, h)
    return teamOf, q4, balances, pickem, results


def seasonContext(byWeek, meta):
    """Top-10 / top-1 per position and FP per game over the loaded season."""
    tot = collections.defaultdict(lambda: [0.0, 0])
    pos = {}
    for wk, byPos in byWeek.items():
        for p, rows in byPos.items():
            for pid, stats in rows:
                t = tot[pid]
                t[0] += stats.get('fantasyPoints', 0) or 0
                t[1] += 1
                pos[pid] = p
    fpg = {pid: t[0] / t[1] for pid, t in tot.items() if t[1]}
    byPosRank = collections.defaultdict(list)
    for pid, v in fpg.items():
        byPosRank[pos[pid]].append((v, pid))
    top10 = {p: {pid for _, pid in sorted(L, reverse=True)[:10]} for p, L in byPosRank.items()}
    top1 = {p: {sorted(L, reverse=True)[0][1]} for p, L in byPosRank.items() if L}
    avg = {p: statistics.mean(v for v, _ in L) for p, L in byPosRank.items()}
    return fpg, top10, top1, avg


def score(cards, week, seasonInfo, seasonsPlayed, extras, user):
    """cards: [(pid, pos, stats, cfg, edition, rating, name, streak)] -> final total.
    `user` is this trial's (balance, pickem row, favorite team) so both arms see one user."""
    fpg, top10, top1, avg = seasonInfo
    teamOf, q4, _, _, results = extras
    balance, pick, favTeam = user
    equipped, weekStats, positions = [], {}, {}
    for i, (pid, pos, stats, cfg, ed, rating, name, streak) in enumerate(cards):
        tpl = _Template(cfg, pid, pos, ed, rating, name)
        eq = _Equipped(1000 + i, i + 1, _UserCard(2000 + i, tpl))
        eq.streak_count = streak
        equipped.append(eq)
        stats = dict(stats)
        stats['q4FantasyPoints'] = q4.get((pid, week), 0)
        weekStats[pid] = stats
        positions[pid] = pos
    ctx = CardCalcContext()
    ctx.userId = 1
    ctx.season, ctx.weekNumber = 15, week
    ctx.weekPlayerStats = weekStats
    ctx.userFloobitsBalance = balance
    if pick:
        ctx.userWeeklyPickemCorrect, ctx.userWeeklyPickemTotal, ctx.userWeeklyPickemPoints = pick
    ctx.userFavoriteTeamId = favTeam
    won, _ = results.get(week, {}).get(favTeam, (False, None))
    ctx.favoriteTeamGameFinal = True
    ctx.favoriteTeamWonThisWeek = won
    ctx.favoriteTeamSeasonWins = sum(1 for w in results if w <= week
                                     and results[w].get(favTeam, (False,))[0])
    ctx.favoriteTeamSeasonLosses = sum(1 for w in results if w <= week
                                       and favTeam in results[w] and not results[w][favTeam][0])
    ctx.rosterPlayerIds = set(weekStats)
    ctx.rosterPlayerPositions = positions
    ctx.rosterPlayerRatings = {c[0]: c[5] for c in cards}
    ctx.rosterPlayerNames = {c[0]: c[6] for c in cards}
    ctx.rosterPlayerTeamIds = {p: teamOf.get((p, week), 0) for p in weekStats}
    ctx._rosterSeasonsPlayed = {p: seasonsPlayed.get(p, 0) for p in weekStats}
    ctx.streakCounts = {e.id: e.streak_count for e in equipped}
    ctx.playerSeasonFPPerGame = fpg
    ctx.top10PerPosition = top10
    ctx.top1PerPosition = top1
    ctx.positionAvgFPs = avg
    ctx.weekRawFP = sum(s.get('fantasyPoints', 0) for s in weekStats.values())
    ctx.rosterTotalTds = sum(
        (s.get('passing_stats', {}) or {}).get('tds', 0)
        + (s.get('rushing_stats', {}) or {}).get('runTds', 0)
        + (s.get('receiving_stats', {}) or {}).get('rcvTds', 0)
        for s in weekStats.values())
    ctx.isProjection = False
    res = calculateWeekCardBonuses(equipped, ctx)
    mult = aggregateMultFactors(res.multFactors or [])
    return (ctx.weekRawFP + res.totalBonusFP) * mult


def starOk(pid, pos, meta):
    return ARM not in ('contender', 'built') or meta.get(pid, ('', 0))[1] >= STAR_FLOOR.get(pos, 0)


def drawFiller(pos, byPos, meta, used, rng):
    for _ in range(20):
        ed = rng.choices([e for e, _ in PACK_WEIGHTS], weights=[w for _, w in PACK_WEIGHTS])[0]
        pool = [x for x in byPos.get(pos, []) if x[0] not in used
                and meta.get(x[0], ('', 80))[1] >= MIN_RATING[ed] and starOk(x[0], pos, meta)]
        effects = livePool(ed, pos)
        if pool and effects:
            pid, stats = rng.choice(pool)
            name, rating = meta.get(pid, ('Probe', 80))
            cfg = ce.buildEffectConfig(ed, rating, pos, forceEffect=rng.choice(effects))
            return (pid, pos, stats, cfg, ed, rating, name, rng.randint(1, 6))
    return None


def marginal(effect, edition, targetPos, byWeek, meta, seasonInfo, seasonsPlayed, extras, rng):
    weeks = sorted(w for w in byWeek if w >= 3)
    deltas = []
    for _ in range(TRIALS):
        wk = rng.choice(weeks)
        byPos = byWeek[wk]
        pool = [x for x in byPos.get(targetPos, [])
                if meta.get(x[0], ('', 80))[1] >= MIN_RATING[edition] and starOk(x[0], targetPos, meta)]
        if not pool:
            return None
        pid, stats = rng.choice(pool)
        name, rating = meta.get(pid, ('Probe', 80))
        streak = rng.randint(1, 6)
        cfg = ce.buildEffectConfig(edition, rating, targetPos, forceEffect=effect)
        target = (pid, targetPos, stats, cfg, edition, rating, name, streak)
        blank = (pid, targetPos, stats, blankConfig(), 'base', rating, name, streak)
        used = {pid}
        others = []
        slots = [p for _, p in SLOTS]
        slots.remove(targetPos)
        for p in slots:
            f = drawFiller(p, byPos, meta, used, rng)
            if f is None:
                break
            used.add(f[0])
            others.append(f)
        else:
            _, _, balances, pickem, results = extras
            user = (rng.choice(balances), rng.choice(pickem) if pickem else None,
                    rng.choice(sorted(results[wk])) if results.get(wk) else 0)
            seed = rng.random()
            random.seed(seed)
            withCard = score(others + [target], wk, seasonInfo, seasonsPlayed, extras, user)
            random.seed(seed)
            without = score(others + [blank], wk, seasonInfo, seasonsPlayed, extras, user)
            deltas.append(withCard - without)
    return deltas


def _pickPlayer(byPos, pos, edition, meta, used, rng):
    pool = [x for x in byPos.get(pos, []) if x[0] not in used
            and meta.get(x[0], ('', 80))[1] >= MIN_RATING[edition] and starOk(x[0], pos, meta)]
    return rng.choice(pool) if pool else None


def _card(pid, pos, stats, effect, edition, meta, streak):
    name, rating = meta.get(pid, ('Probe', 80))
    cfg = (ce.buildEffectConfig(edition, rating, pos, forceEffect=effect) if effect
           else blankConfig())
    return (pid, pos, stats, cfg, edition if effect else 'base', rating, name, streak)


def companionPool(effect, edition, byWeek, meta, ctxArgs, rng, weeks=8, minSwing=0.5):
    """Effects that interact with `effect`: T(A,B) - T(A,-) - T(-,B) + T(-,-) is not ~0."""
    targetPositions = [p for p in (1, 2, 3, 4, 5) if effect in livePool(edition, p)]
    weekList = sorted(w for w in byWeek if w >= 3)
    pool = []
    for ed2 in EDITIONS:
        for e2 in sorted({n for n, e in ce.EFFECT_EDITION_TIER.items() if e == ed2}):
            if e2 == effect:
                continue
            # The CANDIDATE's position first, then a target slot that does not collide
            # with it: a target pinned to its first position (QB) could never be tested
            # against a QB-only partner, which hid every QB card from Sharpshooter.
            pair = next(((cp, tp) for cp in (1, 2, 3, 4, 5) if e2 in livePool(ed2, cp)
                         for tp in targetPositions if tp != cp or cp == 3), None)
            if pair is None:
                continue
            cpos, tpos = pair
            swings = []
            for _ in range(weeks):
                wk = rng.choice(weekList)
                byPos = byWeek[wk]
                t = _pickPlayer(byPos, tpos, edition, meta, set(), rng)
                c = _pickPlayer(byPos, cpos, ed2, meta, {t[0]} if t else set(), rng)
                if not t or not c:
                    break
                used = {t[0], c[0]}
                rest = []
                slots = [p for _, p in SLOTS]
                slots.remove(tpos)
                slots.remove(cpos)
                for p in slots:
                    x = _pickPlayer(byPos, p, 'metallic', meta, used, rng)
                    if x:
                        used.add(x[0])
                        rest.append(_card(x[0], p, x[1], None, 'metallic', meta, 1))
                streak = rng.randint(1, 6)
                T = {}
                seed = rng.random()
                for a in (True, False):
                    for b in (True, False):
                        hand = rest + [_card(t[0], tpos, t[1], effect if a else None, edition, meta, streak),
                                       _card(c[0], cpos, c[1], e2 if b else None, ed2, meta, streak)]
                        random.seed(seed)
                        T[(a, b)] = score(hand, wk, *ctxArgs)
                swings.append(abs(T[(True, True)] - T[(True, False)]
                                  - T[(False, True)] + T[(False, False)]))
            if swings and statistics.mean(swings) > minSwing:
                pool.append((e2, ed2, statistics.mean(swings)))
    return pool


# Hand SHAPES the partner rule cannot express. Lemons multiplies your LOWEST flat-FP card,
# so five flat partners hand it a small one; the way it is played is one big flat-FP card
# with the other slots on FPx (reported by a player, and the shape that maximizes it).
BUILT_SHAPE = {'double_down': 'one_partner_rest_fpx'}


def _fpxPool():
    return [(e, ed, 0.0) for e, ed in ce.EFFECT_EDITION_TIER.items()
            if ce.EFFECT_OUTPUT_TYPE.get(e) == 'fpx' and ed in EDITIONS]


def builtMarginal(effect, edition, targetPos, pool, byWeek, meta, ctxArgs, rng):
    """The target's marginal value in a contender hand whose other slots are its partners."""
    shape = BUILT_SHAPE.get(effect)
    weekList = sorted(w for w in byWeek if w >= 3)
    deltas = []
    for _ in range(TRIALS):
        wk = rng.choice(weekList)
        byPos = byWeek[wk]
        t = _pickPlayer(byPos, targetPos, edition, meta, set(), rng)
        if not t:
            return None
        used = {t[0]}
        others = []
        slots = [p for _, p in SLOTS]
        slots.remove(targetPos)
        rng.shuffle(slots)
        for i, p in enumerate(slots):
            slotPool = pool if (shape is None or i == 0) else _fpxPool()
            choices = [(e2, ed2) for e2, ed2, _ in slotPool if e2 in livePool(ed2, p)
                       and e2 not in {o[3].get('effectName') for o in others}]
            rng.shuffle(choices)
            placed = False
            for e2, ed2 in choices:
                x = _pickPlayer(byPos, p, ed2, meta, used, rng)
                if x:
                    used.add(x[0])
                    others.append(_card(x[0], p, x[1], e2, ed2, meta, rng.randint(1, 6)))
                    placed = True
                    break
            if not placed:
                f = drawFiller(p, byPos, meta, used, rng)
                if f is None:
                    break
                used.add(f[0])
                others.append(f)
        else:
            streak = rng.randint(1, 6)
            seed = rng.random()
            random.seed(seed)
            withCard = score(others + [_card(t[0], targetPos, t[1], effect, edition, meta, streak)],
                             wk, *ctxArgs)
            random.seed(seed)
            without = score(others + [_card(t[0], targetPos, t[1], None, edition, meta, streak)],
                            wk, *ctxArgs)
            deltas.append(withCard - without)
    return deltas


def builtMain(byWeek, meta, seasonInfo, seasonsPlayed, extras, rng):
    names = sorted(ONLY) if ONLY else sorted(
        n for n, e in ce.EFFECT_EDITION_TIER.items() if e == 'diamond')
    _, _, balances, pickem, results = extras
    out = []
    for effect in names:
        edition = ce.EFFECT_EDITION_TIER[effect]
        wk0 = sorted(results)[len(results) // 2] if results else 0
        user = (statistics.median(balances), pickem[0] if pickem else None,
                sorted(results.get(wk0, {0: 0}))[0])
        ctxArgs = (seasonInfo, seasonsPlayed, extras, user)
        pool = companionPool(effect, edition, byWeek, meta, ctxArgs, rng)
        pool.sort(key=lambda x: -x[2])
        per = {}
        for pos in (1, 2, 3, 4, 5):
            if effect not in livePool(edition, pos):
                continue
            d = builtMarginal(effect, edition, pos, pool, byWeek, meta, ctxArgs, rng) if pool else None
            if d:
                per[pos] = (statistics.mean(d), sorted(d)[int(0.9 * (len(d) - 1))])
        out.append((effect, edition, per, [(e, round(sw, 1)) for e, _, sw in pool]))
        mean = statistics.mean(v[0] for v in per.values()) if per else float('nan')
        print(f"  {effect:16}{mean:7.0f}   " + ' '.join(
            f"{POS_NAME[p]}{v[0]:.0f}(p90 {v[1]:.0f})" for p, v in per.items())
            + f"   partners {len(pool)}: " + ', '.join(e for e, _, _ in pool[:8]))
        sys.stdout.flush()
    return out


def main():
    conn = sqlite3.connect(f'file:{DB}?mode=ro', uri=True)
    season = int(SEASON) if SEASON else conn.execute(
        "select max(season) from games where status='final'").fetchone()[0]
    byWeek, meta = loadWeeks(conn, season)
    seasonsPlayed = dict(conn.execute("select id, seasons_played from players"))
    seasonInfo = seasonContext(byWeek, meta)
    if ARM in ('contender', 'built'):
        ratingsByPos = collections.defaultdict(set)
        for byPos in byWeek.values():
            for p, rows in byPos.items():
                for pid, _ in rows:
                    ratingsByPos[p].add((meta.get(pid, ('', 0))[1], pid))
        for p, L in ratingsByPos.items():
            r = sorted(x[0] for x in L)
            STAR_FLOOR[p] = r[int(0.75 * (len(r) - 1))]
    extras = loadExtras(conn, season)
    rng = random.Random(SEED)
    print(f"{DB} season {season}, {TRIALS} lineups per card, normal weeks, tier 1, arm={ARM}\n")
    if ARM == 'built':
        out = builtMain(byWeek, meta, seasonInfo, seasonsPlayed, extras, rng)
        if os.environ.get('PROBE_OUT'):
            with open(os.environ['PROBE_OUT'], 'w') as fh:
                json.dump(out, fh)
        return
    rows = []
    for edition in EDITIONS:
        names = sorted({n for n, ed in ce.EFFECT_EDITION_TIER.items() if ed == edition})
        for effect in names:
            if ONLY and effect not in ONLY:
                continue
            for pos in (1, 2, 3, 4, 5):
                if effect not in livePool(edition, pos):
                    continue
                d = marginal(effect, edition, pos, byWeek, meta, seasonInfo, seasonsPlayed,
                             extras, rng)
                if not d:
                    continue
                rows.append((edition, effect, pos, statistics.mean(d), statistics.median(d),
                             sorted(d)[int(0.9 * (len(d) - 1))]))
        print(f"  {edition} done", file=sys.stderr)
    out = os.environ.get('PROBE_OUT')
    if out:
        with open(out, 'w') as fh:
            json.dump(rows, fh)
    for edition in EDITIONS:
        sub = [r for r in rows if r[0] == edition]
        if not sub:
            continue
        byEffect = collections.defaultdict(list)
        for r in sub:
            byEffect[r[1]].append(r)
        agg = sorted(((statistics.mean(x[3] for x in L), e, L) for e, L in byEffect.items()),
                     reverse=True)
        means = [a for a, _, _ in agg]
        print(f"\n{edition.upper()}  median card {statistics.median(means):.0f} FP  "
              f"(p25 {sorted(means)[len(means)//4]:.0f}, p75 {sorted(means)[3*len(means)//4]:.0f})")
        for m, e, L in agg:
            pos = ' '.join(f"{POS_NAME[x[2]]}{x[3]:.0f}" for x in L)
            print(f"  {e:22}{m:7.0f}   {pos}")


if __name__ == '__main__':
    main()
