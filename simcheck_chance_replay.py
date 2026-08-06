"""Season replay for chance cards, swept across hand composition.

A chance card is a build-around: half its trigger bar comes from the depicted player's FP
(`CARD_CHANCE_FP_WEIGHT`) and the rest from its own condition, and on top of that sits
`ctx.chanceBonus`, fed ENTIRELY by what else you are holding — other chance cards
(+0.04 each), Providence, Catalyst, the Patronage powerup.

That makes both existing harnesses blind to it in opposite ways. `simcheck_effect_spread.py`
puts the card in a hand of no-effect floor prints, which is the exact zero-synergy case, so
every chance card reads at its floor. `simcheck_streak_replay.py` replays a season but holds
the hand fixed. Neither answers the question the card is actually asking, which is: how much
does building around this thing pay?

So this sweeps hand composition across a real player's real season, sampling the roll many
times per week (the live RNG is deterministic per user+season+week+card, so one replay is a
single draw, not a distribution).

  seasonFP     mean season total at that hand strength
  trigger%     share of weeks the jackpot actually landed
  buildGain    season total at full synergy vs the same card played alone

  PROBE_DB=... PROBE_SEASON=3 .venv/bin/python simcheck_chance_replay.py
"""
import os, json, sqlite3, statistics, collections

DB = os.environ.get('PROBE_DB', 'data/floosball.db')
SEASON = os.environ.get('PROBE_SEASON')
MIN_WEEKS = int(os.environ.get('PROBE_MIN_WEEKS', '12'))
TOP_N = int(os.environ.get('PROBE_PLAYERS', '25'))
SEEDS = int(os.environ.get('PROBE_SEEDS', '24'))
LINEUP_FP = float(os.environ.get('PROBE_LINEUP_FP', '250'))

os.environ.setdefault('DATABASE_DIR', os.path.dirname(os.path.abspath(DB)) or '.')
import logging
logging.disable(logging.WARNING)

import managers.cardEffects as ce
from managers.cardEffectCalculator import CardCalcContext
from managers.fantasyTracker import _dbStatsToCardFormat

# Hand strengths, as the chanceBonus each composition contributes. Derived from the
# additive stack in cardEffectCalculator: +0.04 per OTHER chance card, plus Providence's
# own amplifier, plus Catalyst scaling with roster FP, plus the Patronage powerup.
HANDS = [
    ('alone',              0.00),
    ('2 chance cards',     0.04),
    ('4 chance cards',     0.12),
    ('4 + Providence',     0.20),
    ('+ Catalyst at cap',  0.30),
    ('+ Patronage',        0.40),
]

# card, metallic sibling on the same stat (or None), position
CARDS = [
    ('houdini',       'expedition', 2),
    ('promised_land', 'paydirt',    3),
    ('crescendo',     'expedition', 2),
    ('traverse',      None,         3),
]


def _rows(conn, season):
    q = """select g.player_id, p.position, gm.week, g.passing_stats, g.rushing_stats,
                  g.receiving_stats, g.kicking_stats, g.returning_stats, g.fantasy_points
           from game_player_stats g
           join games gm on gm.id = g.game_id
           join players p on p.id = g.player_id
           where gm.season = ? and gm.status = 'final' and gm.is_playoff = 0"""
    out = collections.defaultdict(dict)
    for pid, pos, week, pa, ru, rc, ki, re_, fp in conn.execute(q, (season,)):
        if pos is None:
            continue
        J = lambda x: (json.loads(x) if isinstance(x, str) else (x or {})) or {}
        out[(pid, int(pos))][week] = _dbStatsToCardFormat(
            J(pa), J(ru), J(rc), J(ki), fp or 0, teamId=0, returningStats=J(re_))
    return out


def _ctx(stats, pid, week, chanceBonus, userId, effect, position=0):
    c = CardCalcContext()
    c.weekPlayerStats = {pid: stats}
    c.rosterPlayerIds = {pid}
    c.rosterPlayerPositions = {pid: 0}
    c.streakCounts = {99: 1}
    c.season, c.weekNumber = 15, week
    c.userId = userId
    c.chanceBonus = chanceBonus
    # Position-adaptive cards (Crescendo, Traverse, Squire) read this to decide WHICH
    # stat they key off. Leaving it 0 made Crescendo count nothing and read 0% triggers.
    c.cardPosition = position
    c._currentEffectName = effect
    return c


def _payout(result):
    fp = result.fpBonus or 0.0
    if result.multBonus and result.multBonus > 1.0:
        fp += (result.multBonus - 1.0) * LINEUP_FP
    return fp


def replay(effect, position, weeks, pid, chanceBonus):
    """Season total, averaged over many roll seeds.

    The live RNG keys off userId, so varying it samples the roll distribution the way a
    population of users would experience it rather than one lucky or unlucky season.
    """
    cfg = ce.buildEffectConfig(ce.EFFECT_EDITION_TIER[effect], 82, position,
                               forceEffect=effect)
    totals, triggers = [], []
    for seed in range(SEEDS):
        total = hit = 0.0
        for wk in sorted(weeks):
            ctx = _ctx(weeks[wk], pid, wk, chanceBonus, 1000 + seed, effect, position)
            try:
                r = ce.computeEffect(cfg, ctx, pid, 99)
            except Exception:
                return None
            total += _payout(r)
            if getattr(r, 'chanceTriggered', False):
                hit += 1
        totals.append(total)
        triggers.append(hit / max(1, len(weeks)))
    return statistics.mean(totals), statistics.mean(triggers)


def siblingSeason(sibling, position, weeks, pid):
    if not sibling:
        return None
    cfg = ce.buildEffectConfig(ce.EFFECT_EDITION_TIER[sibling], 82, position,
                               forceEffect=sibling)
    total = 0.0
    for wk in sorted(weeks):
        total += _payout(ce.computeEffect(
            cfg, _ctx(weeks[wk], pid, wk, 0.0, 1, sibling, position), pid, 98))
    return total


def main():
    conn = sqlite3.connect(f'file:{DB}?mode=ro', uri=True)
    season = int(SEASON) if SEASON else conn.execute(
        "select max(season) from games where status='final'").fetchone()[0]
    data = _rows(conn, season)
    byPos = collections.defaultdict(list)
    for (pid, pos), weeks in data.items():
        if len(weeks) >= MIN_WEEKS:
            byPos[pos].append((pid, weeks))
    if not byPos:
        print(f"no completed season {season} data in {DB}")
        return
    print(f"{DB} season {season} · {SEEDS} roll seeds/player · lineup base {LINEUP_FP:.0f} FP\n")
    for effect, sibling, pos in CARDS:
        pool = byPos.get(pos, [])[:TOP_N]
        if not pool:
            print(f"{effect}: no players at position {pos}\n")
            continue
        sib = [siblingSeason(sibling, pos, w, pid) for pid, w in pool] if sibling else None
        sibMean = statistics.mean(sib) if sib else None
        head = f"{effect}" + (f"  (sibling {sibling}: {sibMean:.0f} FP/season)" if sibMean else "")
        print(head)
        print(f"    {'hand':20}{'seasonFP':>10}{'trigger%':>10}{'vs sibling':>12}")
        base = None
        for label, bonus in HANDS:
            runs = [replay(effect, pos, w, pid, bonus) for pid, w in pool]
            runs = [r for r in runs if r]
            if not runs:
                print(f"    {label:20}   error")
                continue
            s = statistics.mean(r[0] for r in runs)
            t = statistics.mean(r[1] for r in runs)
            if base is None:
                base = s
            vs = f"{s / sibMean:11.2f}x" if sibMean else " " * 12
            print(f"    {label:20}{s:10.0f}{100*t:9.0f}%{vs}")
        if base:
            print(f"    build gain (alone -> full synergy): {s / base:.2f}x\n")


if __name__ == '__main__':
    main()
