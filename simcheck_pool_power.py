"""Whole-pool power by edition, on real six-card lineups.

`simcheck_edition_power.py` cannot answer this any more. It boots a PROD snapshot for its
users and rosters, and that snapshot predates every stat the ladder keys off — yards after
contact, good throws, contested catches, punt placement, returns — so every new card reads
zero there. It also still queries `edition == 'base'` for effects, which is now the
NO-EFFECT floor print rather than the base effect tier.

This drops the DB-user machinery entirely. It reads real weekly stat lines from a fresh sim
(which has the full stat surface), builds six-card lineups out of stub ORM objects, and
scores them through the real two-pass calculator. No users, no rosters, no projection
context — which also sidesteps the two traps that bit the other harnesses: projection mode
silently EV-scaling the FP power bar, and a booted snapshot having no season performance
ratings.

  cardPct = (finalTotal - rawPlayerFP) / rawPlayerFP
  finalTotal = (rawPlayerFP + sum bonusFP) * aggregate FPx

Target: comparable MEAN across editions, with the spread widening as rarity rises.

  PROBE_DB=... PROBE_SEASON=2 .venv/bin/python simcheck_pool_power.py
"""
import os, json, random, sqlite3, statistics, collections

DB = os.environ.get('PROBE_DB', 'data/floosball.db')
SEASON = os.environ.get('PROBE_SEASON')
TRIALS = int(os.environ.get('PROBE_TRIALS', '120'))
SEED = int(os.environ.get('PROBE_SEED', '4242'))

os.environ.setdefault('DATABASE_DIR', os.path.dirname(os.path.abspath(DB)) or '.')
import logging
logging.disable(logging.WARNING)

import managers.cardEffects as ce
from managers.cardEffectCalculator import (CardCalcContext, calculateWeekCardBonuses,
                                           aggregateMultFactors)
from managers.fantasyTracker import _dbStatsToCardFormat

SLOTS = [('QB', 1), ('RB', 2), ('WR1', 3), ('WR2', 3), ('TE', 4), ('K', 5)]
EDITIONS = ['metallic', 'holographic', 'prismatic', 'diamond']


class _Template:
    """Only the fields the calculator actually reads off a CardTemplate."""
    def __init__(self, effect_config, player_id, position, edition, rating, name):
        self.effect_config = effect_config
        self.player_id = player_id
        self.position = position
        self.edition = edition
        self.player_rating = rating
        self.player_name = name
        self.classification = None
        self.team_id = None


class _UserCard:
    def __init__(self, cid, template):
        self.id = cid
        self.card_template = template
        self.tier = 1


class _Equipped:
    def __init__(self, eid, slotNumber, userCard):
        self.id = eid
        self.slot_number = slotNumber
        self.streak_count = 1
        self.user_card = userCard
        self.peak_output = None
        self.weeks_since_break = 0


def livePool(edition, position):
    """Effects of this edition that can actually mint on this position."""
    return [n for n, ed in ce.EFFECT_EDITION_TIER.items()
            if ed == edition and position in (ce.effectValidPositions(n) or set())]


def loadWeeks(conn, season):
    q = """select g.player_id, p.position, gm.week, p.name, p.player_rating,
                  g.passing_stats, g.rushing_stats, g.receiving_stats,
                  g.kicking_stats, g.returning_stats, g.fantasy_points
           from game_player_stats g
           join games gm on gm.id = g.game_id
           join players p on p.id = g.player_id
           where gm.season = ? and gm.status = 'final' and gm.is_playoff = 0"""
    byWeek = collections.defaultdict(lambda: collections.defaultdict(list))
    meta = {}
    for pid, pos, week, name, rating, pa, ru, rc, ki, re_, fp in conn.execute(q, (season,)):
        if pos is None or not fp:
            continue
        J = lambda x: (json.loads(x) if isinstance(x, str) else (x or {})) or {}
        stats = _dbStatsToCardFormat(J(pa), J(ru), J(rc), J(ki), fp, teamId=0,
                                     returningStats=J(re_))
        byWeek[week][int(pos)].append((pid, stats))
        meta[pid] = (name or 'Probe', int(rating or 80))
    return byWeek, meta


def scoreLineup(edition, week, byPos, meta, rng, mixWith=None, mixCount=0):
    """One six-card lineup, scored through the real calculator.

    `mixWith` fills the remaining slots from another edition. Diamond needs this: six of
    its fourteen cards are AMPLIFIERS that produce no output of their own, so a pure
    diamond lineup has nothing to amplify and reads a 0% median. Nobody holds one either.
    """
    equipped, weekStats, positions = [], {}, {}
    used = set()
    for i, (slot, pos) in enumerate(SLOTS):
        thisEd = edition if (mixWith is None or i < mixCount) else mixWith
        pool = [x for x in byPos.get(pos, []) if x[0] not in used]
        effects = livePool(thisEd, pos)
        if not pool or not effects:
            return None
        pid, stats = rng.choice(pool)
        used.add(pid)
        name, rating = meta.get(pid, ('Probe', 80))
        cfg = ce.buildEffectConfig(thisEd, rating, pos, forceEffect=rng.choice(effects))
        tpl = _Template(cfg, pid, pos, thisEd, rating, name)
        equipped.append(_Equipped(1000 + i, i + 1, _UserCard(2000 + i, tpl)))
        weekStats[pid] = stats
        positions[pid] = pos

    ctx = CardCalcContext()
    ctx.userId = 1
    ctx.season, ctx.weekNumber = 15, week
    ctx.weekPlayerStats = weekStats
    ctx.rosterPlayerIds = set(weekStats)
    ctx.rosterPlayerPositions = positions
    ctx.rosterPlayerRatings = {p: meta.get(p, ('', 80))[1] for p in weekStats}
    ctx.rosterPlayerNames = {p: meta.get(p, ('Probe', 0))[0] for p in weekStats}
    ctx.rosterPlayerTeamIds = {p: 0 for p in weekStats}
    ctx.streakCounts = {e.id: 1 for e in equipped}
    ctx.weekRawFP = sum(s.get('fantasyPoints', 0) for s in weekStats.values())
    ctx.rosterTotalTds = sum(
        (s.get('passing_stats', {}) or {}).get('tds', 0)
        + (s.get('rushing_stats', {}) or {}).get('runTds', 0)
        + (s.get('receiving_stats', {}) or {}).get('rcvTds', 0)
        for s in weekStats.values())
    ctx.isProjection = False       # live path: the FP power bar is on/off, not EV-scaled
    if ctx.weekRawFP <= 0:
        return None
    try:
        res = calculateWeekCardBonuses(equipped, ctx)
    except Exception as e:
        return ('ERROR', repr(e))
    mult = aggregateMultFactors(res.multFactors or [])
    total = (ctx.weekRawFP + res.totalBonusFP) * mult
    return (total - ctx.weekRawFP) / ctx.weekRawFP


def scoreMixed(week, byPos, meta, rng, weightsRaw):
    """A lineup whose editions are drawn at the real pack rates."""
    eds = [e for e, _ in weightsRaw]
    ws = [w for _, w in weightsRaw]
    equipped, weekStats, positions = [], {}, {}
    used = set()
    for i, (slot, pos) in enumerate(SLOTS):
        pool = [x for x in byPos.get(pos, []) if x[0] not in used]
        if not pool:
            return None
        for _ in range(12):
            ed = rng.choices(eds, weights=ws)[0]
            effects = livePool(ed, pos)
            if effects:
                break
        else:
            return None
        pid, stats = rng.choice(pool)
        used.add(pid)
        name, rating = meta.get(pid, ('Probe', 80))
        cfg = ce.buildEffectConfig(ed, rating, pos, forceEffect=rng.choice(effects))
        tpl = _Template(cfg, pid, pos, ed, rating, name)
        equipped.append(_Equipped(1000 + i, i + 1, _UserCard(2000 + i, tpl)))
        weekStats[pid] = stats
        positions[pid] = pos
    ctx = CardCalcContext()
    ctx.userId = 1
    ctx.season, ctx.weekNumber = 15, week
    ctx.weekPlayerStats = weekStats
    ctx.rosterPlayerIds = set(weekStats)
    ctx.rosterPlayerPositions = positions
    ctx.rosterPlayerRatings = {p: meta.get(p, ('', 80))[1] for p in weekStats}
    ctx.rosterPlayerNames = {p: meta.get(p, ('Probe', 0))[0] for p in weekStats}
    ctx.rosterPlayerTeamIds = {p: 0 for p in weekStats}
    ctx.streakCounts = {e.id: 1 for e in equipped}
    ctx.weekRawFP = sum(s.get('fantasyPoints', 0) for s in weekStats.values())
    ctx.rosterTotalTds = 0
    ctx.isProjection = False
    if ctx.weekRawFP <= 0:
        return None
    try:
        res = calculateWeekCardBonuses(equipped, ctx)
    except Exception:
        return None
    mult = aggregateMultFactors(res.multFactors or [])
    total = (ctx.weekRawFP + res.totalBonusFP) * mult
    globals().setdefault('_RAW', []).append(ctx.weekRawFP)
    globals().setdefault('_TOT', []).append(total)
    return (total - ctx.weekRawFP) / ctx.weekRawFP


def main():
    conn = sqlite3.connect(f'file:{DB}?mode=ro', uri=True)
    season = int(SEASON) if SEASON else conn.execute(
        "select max(season) from games where status='final'").fetchone()[0]
    byWeek, meta = loadWeeks(conn, season)
    if not byWeek:
        print(f"no completed season {season} data in {DB}")
        return
    weeks = sorted(byWeek)
    rng = random.Random(SEED)
    print(f"{DB} season {season} · {len(weeks)} weeks · {TRIALS} lineups/edition\n")
    print(f"  {'edition':13}{'mean':>8}{'median':>8}{'p10':>8}{'p90':>8}{'spread':>9}"
          f"{'pool':>6}")
    errors = collections.Counter()
    # A REALISTIC hand, weighted by the actual pack drop rates (cardManager
    # EDITION_BASE_WEIGHTS). This is the arm that answers "what will users actually
    # score?", since nobody fields six cards of one edition.
    print()
    weightsRaw = [('metallic', 100), ('holographic', 25), ('prismatic', 10), ('diamond', 2)]
    tot = sum(w for _, w in weightsRaw)
    pcts = []
    for _ in range(TRIALS * 3):
        wk = rng.choice(weeks)
        r = scoreMixed(wk, byWeek[wk], meta, rng, weightsRaw)
        if isinstance(r, float):
            pcts.append(r)
    if pcts:
        pcts.sort()
        print(f"  {'REALISTIC':13}{100*statistics.mean(pcts):7.0f}%"
              f"{100*statistics.median(pcts):7.0f}%"
              f"{100*pcts[int(0.10*(len(pcts)-1))]:7.0f}%"
              f"{100*pcts[int(0.90*(len(pcts)-1))]:7.0f}%"
              f"   (pack-weighted: "
              + ", ".join(f"{e} {100*w//tot}%" for e, w in weightsRaw) + ")")
    print()
    ARMS = [(ed, None, 0) for ed in EDITIONS] + [
        ('diamond', 'metallic', 2),   # 2 diamonds in an otherwise metallic hand
        ('diamond', 'metallic', 1),   # the realistic case: one diamond pull
    ]
    for ed, mixWith, mixCount in ARMS:
        pcts = []
        label = ed if not mixWith else f"{mixCount}x {ed}+{mixWith}"
        for _ in range(TRIALS):
            wk = rng.choice(weeks)
            r = scoreLineup(ed, wk, byWeek[wk], meta, rng, mixWith, mixCount)
            if isinstance(r, tuple):
                errors[r[1]] += 1
            elif r is not None:
                pcts.append(r)
        if not pcts:
            print(f"  {label:13}   no data")
            continue
        pcts.sort()
        p10 = pcts[int(0.10 * (len(pcts) - 1))]
        p90 = pcts[int(0.90 * (len(pcts) - 1))]
        poolSize = len({n for n, e in ce.EFFECT_EDITION_TIER.items()
                        if e == ed and ce.effectValidPositions(n)})
        print(f"  {label:13}{100*statistics.mean(pcts):7.0f}%"
              f"{100*statistics.median(pcts):7.0f}%{100*p10:7.0f}%{100*p90:7.0f}%"
              f"{p90/max(p10, 0.01):8.1f}x{poolSize:6}")
    if errors:
        print("\n  errors:")
        for msg, n in errors.most_common(5):
            print(f"    {n:4} x {msg[:88]}")
    raw, tot = globals().get('_RAW', []), globals().get('_TOT', [])
    if raw:
        print(f"\n  realistic weekly TOTALS: raw player FP {statistics.mean(raw):.0f} "
              f"-> final {statistics.mean(tot):.0f}   "
              f"(p10 {sorted(tot)[int(.1*(len(tot)-1))]:.0f}, "
              f"p90 {sorted(tot)[int(.9*(len(tot)-1))]:.0f})")
    print("\n  cardPct = how much the six cards add on top of the lineup's own player FP.")
    print("  Want comparable MEANS with the p10-p90 spread widening as rarity rises.")


if __name__ == '__main__':
    main()
