"""Season replay for streak cards — the thing a per-week harness structurally cannot do.

`simcheck_effect_spread.py` scores one week in isolation, so every streak card it measures
reads at week one, on its lowest rung. That is not a small understatement: a streak card's
whole proposition is a path through a season, and its value depends on how often the
depicted player actually clears the bar week after week.

This replays a REAL player's real weekly stat lines through the streak state machine and
sums what the card would have paid across the season, then compares that against the flat
metallic card on the same stat. The decision it answers is the one a user actually faces:
over a whole season, is the prismatic rung worth playing over the metallic one?

  seasonFP      total the card paid across every week it was equipped
  vsMetallic    that total as a share of the metallic sibling's
  rampWeeks     weeks before the card first out-earns its metallic sibling
  holdRate      share of weeks the player cleared the streak bar
  peakStreak    longest run achieved

SCOPE: the stat-ladder streak cards only. Those carry no `baseReward`, so the peak-decay
and restart-penalty machinery in `seasonManager` is inert for them and `streak_count` is
the entire state. A card WITH a carried peak (Bonsai, Complacency, the older streaks) needs
that machinery replayed too and is deliberately not covered here — measuring it with this
replica would quietly report the wrong number.

  PROBE_DB=data/floosball.db .venv/bin/python simcheck_streak_replay.py
"""
import os, json, sqlite3, statistics, collections

DB = os.environ.get('PROBE_DB', 'data/floosball.db')
SEASON = os.environ.get('PROBE_SEASON')
MIN_WEEKS = int(os.environ.get('PROBE_MIN_WEEKS', '12'))
TOP_N = int(os.environ.get('PROBE_PLAYERS', '40'))

os.environ.setdefault('DATABASE_DIR', os.path.dirname(os.path.abspath(DB)) or '.')
import logging
logging.disable(logging.WARNING)

import managers.cardEffects as ce
from managers.cardEffectCalculator import CardCalcContext
from managers.fantasyTracker import _dbStatsToCardFormat

# Each ladder streak card, its metallic sibling on the same stat, and the position to
# mint both on. The sibling is the comparison that matters: rarity has to earn its slot.
FAMILIES = [
    ('clockwork',    'cadence',        1, 'completions'),
    ('stratosphere', 'slipstream',     1, 'pass yards'),
    ('dead_eye',     'gunslinger',     1, 'throw quality'),
    ('iron_man',     'workhorse',      2, 'carries'),
    ('odyssey',      'expedition',     2, 'rush yards'),
    ('landslide',    'freight',        2, 'yards after contact'),
    ('dominion',     'frontier',       3, 'receiving yards'),
    ('tenure',       'possession',     3, 'receptions'),
    ('getaway',      'slippery',       3, 'YAC'),
    ('undertaker',   'pinpoint',       5, 'punts inside 20'),
]


def _rows(conn, season):
    """(playerId, position) -> {week: cardFormatStats}, from real game rows."""
    q = """select g.player_id, p.position, g.week, g.passing_stats, g.rushing_stats,
                  g.receiving_stats, g.kicking_stats, g.returning_stats, g.fantasy_points
           from game_player_stats g
           join games gm on gm.id = g.game_id
           join players p on p.id = g.player_id
           where gm.season = ? and gm.status = 'final' and gm.is_playoff = 0"""
    # game_player_stats has no week column in every schema; fall back to the game's.
    try:
        cur = conn.execute(q.replace('g.week', 'gm.week'), (season,))
    except sqlite3.OperationalError:
        return {}
    out = collections.defaultdict(dict)
    for pid, pos, week, pa, ru, rc, ki, re_, fp in cur:
        if pos is None:
            continue
        J = lambda x: (json.loads(x) if isinstance(x, str) else (x or {})) or {}
        out[(pid, int(pos))][week] = _dbStatsToCardFormat(
            J(pa), J(ru), J(rc), J(ki), fp or 0, teamId=0, returningStats=J(re_))
    return out


def _ctx(stats, pid, streak):
    c = CardCalcContext()
    c.weekPlayerStats = {pid: stats}
    c.rosterPlayerIds = {pid}
    c.streakCounts = {99: streak}
    c.season, c.weekNumber = 15, 14
    c.chanceBonus = 0.0
    return c


def _payout(result, lineupFP):
    """One card's week in FP terms.

    An FPx card multiplies `rawPlayerFP + every card's flat FP bonus`, NOT raw player FP
    alone. Converting at the raw total (~120) reads every multiplier at half its real
    worth and makes FPx cards look strictly worse than FP ones. A six-card lineup whose
    other slots each add ~26 FP multiplies ~276, where +0.10 FPx is ~28 FP — the same as
    the flat anchor, which is what the FPx target was calibrated against.
    """
    fp = result.fpBonus or 0.0
    if result.multBonus and result.multBonus > 1.0:
        fp += (result.multBonus - 1.0) * lineupFP
    return fp


# rawPlayerFP (~120) plus five sibling cards at the ~26 FP anchor.
LINEUP_FP = float(os.environ.get('PROBE_LINEUP_FP', '250'))


def replay(effect, sibling, position, weeks, pid):
    """Walk a player's season, advancing streak state exactly as week-end banking does.

    seasonManager: condition met -> count+1 (or 2 restarting from 0); not met -> 0.
    """
    cfgS = ce.buildEffectConfig(ce.EFFECT_EDITION_TIER[effect], 82, position,
                                forceEffect=effect)
    cfgM = ce.buildEffectConfig(ce.EFFECT_EDITION_TIER[sibling], 82, position,
                                forceEffect=sibling)
    count, peak, held = 1, 0, 0
    streakTotal = flatTotal = 0.0
    ramp = None
    cumS = cumM = 0.0
    for i, wk in enumerate(sorted(weeks), start=1):
        stats = weeks[wk]
        ctx = _ctx(stats, pid, count)
        ctx._currentEffectName = effect
        s = _payout(ce.computeEffect(cfgS, ctx, pid, 99), LINEUP_FP)
        m = _payout(ce.computeEffect(cfgM, _ctx(stats, pid, 1), pid, 98), LINEUP_FP)
        streakTotal += s
        flatTotal += m
        cumS += s
        cumM += m
        if ramp is None and cumS > cumM:
            ramp = i
        met = ce.checkStreakCondition(effect, _ctx(stats, pid, count), pid)
        if met:
            held += 1
            count = 2 if count == 0 else count + 1
            peak = max(peak, count - 1)
        else:
            count = 0
    n = len(weeks)
    return dict(seasonFP=streakTotal, flatFP=flatTotal, weeks=n,
                holdRate=held / n if n else 0, peakStreak=peak, ramp=ramp)


def main():
    conn = sqlite3.connect(f'file:{DB}?mode=ro', uri=True)
    season = int(SEASON) if SEASON else conn.execute(
        "select max(season) from games where status='final'").fetchone()[0]
    data = _rows(conn, season)
    if not data:
        print(f"no completed games in season {season} of {DB}")
        return
    byPos = collections.defaultdict(list)
    for (pid, pos), weeks in data.items():
        if len(weeks) >= MIN_WEEKS:
            byPos[pos].append((pid, weeks))
    print(f"{DB} season {season} · {sum(len(v) for v in byPos.values())} players "
          f"with {MIN_WEEKS}+ weeks · lineup base {LINEUP_FP:.0f} FP\n")
    print(f"  {'streak card':14} {'vs sibling':>11} {'seasonFP':>9} {'flatFP':>8} "
          f"{'hold%':>7} {'peak':>6} {'ramp':>6}")
    for effect, sibling, pos, label in FAMILIES:
        pool = byPos.get(pos, [])[:TOP_N]
        if not pool:
            print(f"  {effect:14}   no players at position {pos}")
            continue
        runs = [replay(effect, sibling, pos, w, pid) for pid, w in pool]
        s = statistics.mean(r['seasonFP'] for r in runs)
        f = statistics.mean(r['flatFP'] for r in runs)
        hold = statistics.mean(r['holdRate'] for r in runs)
        peak = statistics.mean(r['peakStreak'] for r in runs)
        ramps = [r['ramp'] for r in runs if r['ramp']]
        rampStr = f"{statistics.median(ramps):.0f}" if ramps else "never"
        ratio = (s / f) if f else float('nan')
        print(f"  {effect:14} {ratio:10.2f}x {s:9.0f} {f:8.0f} {100*hold:6.0f}% "
              f"{peak:6.1f} {rampStr:>6}")
    print("\n  vs sibling  season total against the metallic card on the same stat")
    print("  ramp        weeks before the streak card's CUMULATIVE total overtakes it")
    print("  hold%       share of weeks the player cleared the streak bar")
    print("\nA ratio under 1.0 means the prismatic rung loses to its own base tier over a")
    print("full season, which no amount of ceiling justifies.")


if __name__ == '__main__':
    main()
