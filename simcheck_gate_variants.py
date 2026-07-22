"""Owner design (2026-07-22): gate the card on its own player's production.

  * effect already keys off the CARD PLAYER's production  -> leave alone (21)
  * anything else (roster totals, favourite team, economy, chance, flat boosts)
    -> the card player must CLEAR A THRESHOLD before the effect fires  (105)

A gate, not a multiplier: below the bar the card pays nothing, so a weak lineup
stops collecting. Tested against the controlled substrate (same effect set on a
strong and a weak lineup, only player quality varies) so the confound of
effects being tied to players is removed.

Variants: threshold vs the player's OWN season average, and vs the LEAGUE
average at their position. Plus a scaled variant (ramp instead of a cliff).
"""
import asyncio, os, random, shutil, statistics, tempfile, logging

DB = 'data/floosball_prod_latest.db'
WEEK = 14
EDITION = os.environ.get('PROBE_EDITION', 'prismatic')
TRIALS = int(os.environ.get('PROBE_TRIALS', '40'))
SEED = 12345

def _onCardEffects():
    """Effects that already key off the card's own player (Stage 1 re-based).

    Derived from the source rather than a checked-in list, so it stays correct as
    more effects are re-based."""
    import ast as _ast, re as _re
    _src = open('managers/cardEffects.py').read()
    _tree = _ast.parse(_src)
    calls, uses = {}, {}
    for n in _tree.body:
        if not isinstance(n, _ast.FunctionDef):
            continue
        c, u = set(), False
        for sub in _ast.walk(n):
            if isinstance(sub, _ast.Name) and sub.id == 'cardPlayerId':
                u = True
            if isinstance(sub, _ast.Call) and isinstance(sub.func, _ast.Name):
                c.add(sub.func.id)
        calls[n.name], uses[n.name] = c, u

    def flag(fn, seen=None):
        seen = seen or set()
        if fn in seen or fn not in uses:
            return False
        seen.add(fn)
        return uses[fn] or any(flag(x, seen) for x in calls.get(fn, ()))

    reg = _src[_src.index('EFFECT_REGISTRY'):]
    return {e for e, fn in
            _re.findall(r"""['"]([a-z_]+)['"]\s*:\s*(_compute[A-Za-z0-9_]+)""", reg)
            if flag(fn)}


ONCARD = _onCardEffects()

tmp = tempfile.mkdtemp(prefix='floos_gate_')
shutil.copy(DB, os.path.join(tmp, 'floosball.db'))
os.environ['DATABASE_DIR'] = tmp
logging.disable(logging.WARNING)

from simcheck_cards import boot, preloadSeason, applyWeekState
container, app = asyncio.run(boot())
from database.connection import get_session
from database.models import (FantasyRoster, EquippedCard, UserCard, CardTemplate,
                             Game, GamePlayerStats, WeeklyPlayerFP, Player)
from sqlalchemy import func
from managers.cardProjection import buildProjectionContext
from managers.cardEffectCalculator import calculateWeekCardBonuses, aggregateMultFactors
from managers.cardManager import SLOT_TO_ORDINAL
from managers.fantasyTracker import _dbStatsToCardFormat

sm = getattr(app, 'seasonManager', None) or container.getService('season_manager')
pm = getattr(app, 'playerManager', None) or container.getService('player_manager')
s = get_session()
season = s.query(func.max(FantasyRoster.season)).scalar()
teamGames, byWeek, eloByTeam = preloadSeason(s, season)

weekFP = {r.player_id: r.fantasy_points
          for r in s.query(WeeklyPlayerFP).filter_by(season=season, week=WEEK).all()}
REAL = {}
for gps in (s.query(GamePlayerStats).join(Game, GamePlayerStats.game_id == Game.id)
            .filter(Game.season == season, Game.week == WEEK).all()):
    REAL[gps.player_id] = _dbStatsToCardFormat(
        gps.passing_stats, gps.rushing_stats, gps.receiving_stats, gps.kicking_stats,
        weekFP.get(gps.player_id, 0), teamId=gps.team_id)
    if gps.q4_fantasy_points:
        REAL[gps.player_id]["q4FantasyPoints"] = gps.q4_fantasy_points
for pid, fp in weekFP.items():
    REAL.setdefault(pid, _dbStatsToCardFormat({}, {}, {}, {}, fp))

byPos = {}
for p in s.query(Player).all():
    if p.position is None:
        continue
    byPos.setdefault(int(p.position), []).append(p)
for pos in byPos:
    played = [p for p in byPos[pos] if (weekFP.get(p.id, 0) or 0) > 0]
    played.sort(key=lambda p: weekFP.get(p.id, 0), reverse=True)
    byPos[pos] = played

SLOTS = [('QB', 1), ('RB', 2), ('WR1', 3), ('WR2', 3), ('TE', 4), ('K', 5)]

def pickLineup(strong):
    used, out = set(), []
    for slot, pos in SLOTS:
        pool = byPos.get(pos) or []
        if not pool:
            continue
        cut = max(1, int(len(pool) * 0.20))
        band = pool[:cut] if strong else pool[-cut:]
        for p in band + (pool if strong else list(reversed(pool))):
            if p.id in used:
                continue
            used.add(p.id); out.append((slot, pos, p)); break
    return out

STRONG, WEAK = pickLineup(True), pickLineup(False)

tpls = s.query(CardTemplate).filter(CardTemplate.season_created == season,
                                    CardTemplate.edition == EDITION).all()
byEffect = {}
for t in tpls:
    en = (t.effect_config or {}).get('effectName')
    if en and en not in byEffect:
        byEffect[en] = t
effectNames = sorted(byEffect)
user = s.query(FantasyRoster).filter_by(season=season).first().user_id


def synthTemplate(effectName, player, pos):
    srcT = byEffect[effectName]
    cols = {c.name for c in CardTemplate.__table__.columns} - {'id', 'created_at'}
    data = {c: getattr(srcT, c) for c in cols}
    data.update(player_id=player.id,
                player_name=getattr(player, 'name', '') or 'Probe Player',
                team_id=getattr(player, 'team_id', None),
                player_rating=int(getattr(player, 'player_rating', 75) or 75),
                position=pos, effect_config=dict(srcT.effect_config or {}),
                classification=None)
    t = CardTemplate(**data); s.add(t); s.flush()
    return t


# gate variants: name -> fn(weekFP, ownAvg, posAvg) -> multiplier in [0,1]
VARIANTS = {
    'none (current)':      lambda fp, own, pos: 1.0,
    'own avg x0.75 gate':  lambda fp, own, pos: 1.0 if own <= 0 or fp >= 0.75 * own else 0.0,
    'pos avg x0.75 gate':  lambda fp, own, pos: 1.0 if pos <= 0 or fp >= 0.75 * pos else 0.0,
    'pos avg x1.00 gate':  lambda fp, own, pos: 1.0 if pos <= 0 or fp >= pos else 0.0,
    'pos avg ramp 0->1':   lambda fp, own, pos: 1.0 if pos <= 0 else max(0.0, min(1.0, fp / pos)),
}


def score(lineup, effects):
    s.query(EquippedCard).filter_by(user_id=user, season=season, week=WEEK).delete()
    s.flush()
    for (slot, pos, player), en in zip(lineup, effects):
        t = synthTemplate(en, player, pos)
        uc = UserCard(user_id=user, card_template_id=t.id, acquired_via='probe', tier=1)
        s.add(uc); s.flush()
        s.add(EquippedCard(user_id=user, season=season, week=WEEK, slot=slot,
                           slot_number=SLOT_TO_ORDINAL.get(slot, 1),
                           user_card_id=uc.id, streak_count=1))
    s.flush()
    ctx = buildProjectionContext(s, user, season, WEEK, sm, pm)
    if ctx is None:
        return None
    applyWeekState(ctx, ctx.userFavoriteTeamId, WEEK, teamGames, byWeek, eloByTeam)
    ctx.weekPlayerStats = {pid: REAL.get(pid, {}) for pid in ctx.rosterPlayerIds}
    ctx.weekRawFP = sum((st or {}).get('fantasyPoints', 0) for st in ctx.weekPlayerStats.values())
    ctx.rosterTotalTds = sum(
        (st or {}).get('passing_stats', {}).get('tds', 0)
        + (st or {}).get('rushing_stats', {}).get('runTds', 0)
        + (st or {}).get('receiving_stats', {}).get('rcvTds', 0)
        for st in ctx.weekPlayerStats.values())
    eqs = s.query(EquippedCard).filter_by(user_id=user, season=season, week=WEEK).all()
    res = calculateWeekCardBonuses(eqs, ctx)

    out = {'raw': ctx.weekRawFP}
    for vname, fn in VARIANTS.items():
        fp, mults = 0.0, []
        for b in (res.cardBreakdowns or []):
            pid = b.playerId
            wfp = (ctx.weekPlayerStats.get(pid) or {}).get('fantasyPoints', 0) or 0
            own = (ctx.playerSeasonFPPerGame or {}).get(pid) or 0
            pav = (ctx.positionAvgFPs or {}).get((ctx.rosterPlayerPositions or {}).get(pid, 0)) or 0
            k = 1.0 if b.effectName in ONCARD else fn(wfp, own, pav)
            fp += (b.totalFP or 0.0) * k
            if b.primaryMult:
                mults.append(1.0 + (b.primaryMult - 1.0) * k)
        out[vname] = {'bonus': fp,
                      'total': (ctx.weekRawFP + fp) * aggregateMultFactors(mults)}
    return out


rng = random.Random(SEED)
acc = {v: {'sT': [], 'wT': [], 'sB': [], 'wB': []} for v in VARIANTS}
rawS, rawW = [], []
for _ in range(TRIALS):
    effects = rng.sample(effectNames, len(SLOTS))
    a, b = score(STRONG, effects), score(WEAK, effects)
    s.rollback()
    if not a or not b:
        continue
    rawS.append(a['raw']); rawW.append(b['raw'])
    for v in VARIANTS:
        if b[v]['total'] <= 0:
            continue
        acc[v]['sT'].append(a[v]['total']); acc[v]['wT'].append(b[v]['total'])
        acc[v]['sB'].append(a[v]['bonus']); acc[v]['wB'].append(b[v]['bonus'])

m = statistics.mean
playerRatio = m(rawS) / max(m(rawW), .01)
print(f"\n━━ {EDITION} · {TRIALS} effect sets · gate applies to {len(effectNames) - len([e for e in effectNames if e in ONCARD])} of {len(effectNames)} effects at this edition")
print(f"   strong lineup player FP {m(rawS):.1f}   weak {m(rawW):.1f}   "
      f"playerRatio {playerRatio:.2f}x  <- target\n")
print(f"{'variant':22} {'strongBonus':>11} {'weakBonus':>10} {'scoreRatio':>11} {'signal':>8}")
for v in VARIANTS:
    d = acc[v]
    if not d['sT']:
        print(f"{v:22}  (no data)"); continue
    sr = m(d['sT']) / max(m(d['wT']), .01)
    print(f"{v:22} {m(d['sB']):>11.1f} {m(d['wB']):>10.1f} {sr:>10.2f}x "
          f"{100*sr/playerRatio:>7.0f}%")
print("\nsignal = scoreRatio / playerRatio. 100% = cards fully preserve roster choice.")
shutil.rmtree(tmp, ignore_errors=True)
