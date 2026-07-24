"""Phase 9 retune measurement: per-edition mean card bonus as % of the lineup's own
player FP, on real 6-card fusion lineups.

Fusion fields a full 6-card slate, so aggregate card bonus is structurally higher than
the old ~5-card hand. Target (owner): ~100% MEAN per edition — cards roughly double a
lineup's raw player FP on average; rarity buys ceiling/variance, not a higher mean.

Boots against a COPY of the prod DB (real users/games), builds N random lineups per
edition (6 random distinct effects of that edition on 6 random real starters), rebuilds
each card's effect_config with the CURRENT builder (so the FP power-bar gate AND
EDITION_POWER_SCALE apply), and scores through the real two-pass calculator against real
week-14 stats.

  cardPct = (finalTotal - rawPlayerFP) / rawPlayerFP     (per lineup)
  finalTotal = (rawPlayerFP + sum bonus FP) * aggregate FPx

Env: PROBE_TRIALS (default 40), PROBE_WEEK (14), PROBE_DB (prod copy).
Run: .venv/bin/python simcheck_edition_power.py
"""
import asyncio, os, random, shutil, statistics, tempfile, logging

DB = os.environ.get('PROBE_DB', 'data/floosball_prod_latest.db')
WEEK = int(os.environ.get('PROBE_WEEK', '14'))
TRIALS = int(os.environ.get('PROBE_TRIALS', '40'))
SEED = 4242

tmp = tempfile.mkdtemp(prefix='floos_edpow_')
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
from managers.cardEffects import buildEffectConfig, EDITION_POWER_SCALE

sm = getattr(app, 'seasonManager', None) or container.getService('season_manager')
pm = getattr(app, 'playerManager', None) or container.getService('player_manager')
s = get_session()
season = s.query(func.max(FantasyRoster.season)).scalar()
teamGames, byWeek, eloByTeam = preloadSeason(s, season)

from managers.fantasyTracker import _dbStatsToCardFormat
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
    byPos[pos] = [p for p in byPos[pos] if (weekFP.get(p.id, 0) or 0) > 0]

SLOTS = [('QB', 1), ('RB', 2), ('WR1', 3), ('WR2', 3), ('TE', 4), ('K', 5)]
user = s.query(FantasyRoster).filter_by(season=season).first().user_id

# Distinct effect names available per edition (from the real template pool).
import json
effByEd = {}
for ed in ('base', 'holographic', 'prismatic', 'diamond'):
    names = set()
    for (cfg,) in s.query(CardTemplate.effect_config).filter(
            CardTemplate.season_created == season, CardTemplate.edition == ed):
        en = (cfg or {}).get('effectName')
        if en and en not in ('none', ''):
            names.add(en)
    effByEd[ed] = sorted(names)

_cols = {c.name for c in CardTemplate.__table__.columns} - {'id', 'created_at'}
_src = {}  # (effect, edition) -> a source template for the non-player columns

def synth(effectName, edition, player, pos):
    key = (effectName, edition)
    if key not in _src:
        _src[key] = (s.query(CardTemplate)
                     .filter(CardTemplate.edition == edition)
                     .filter(CardTemplate.effect_config.like(f'%"effectName": "{effectName}"%'))
                     .first())
    src = _src[key]
    data = {c: getattr(src, c) for c in _cols}
    rating = int(getattr(player, 'player_rating', 80) or 80)
    data.update(player_id=player.id, player_name=getattr(player, 'name', '') or 'Probe',
                team_id=getattr(player, 'team_id', None), player_rating=rating, position=pos,
                effect_config=buildEffectConfig(edition, rating, pos, forceEffect=effectName),
                classification=None)
    t = CardTemplate(**data); s.add(t); s.flush()
    return t

def scoreLineup(lineup, effects, edition):
    s.query(EquippedCard).filter_by(user_id=user, season=season, week=WEEK).delete(); s.flush()
    for (slot, pos, player), en in zip(lineup, effects):
        t = synth(en, edition, player, pos)
        uc = UserCard(user_id=user, card_template_id=t.id, acquired_via='probe', tier=1)
        s.add(uc); s.flush()
        s.add(EquippedCard(user_id=user, season=season, week=WEEK, slot=slot,
                           slot_number=SLOT_TO_ORDINAL.get(slot, 1), user_card_id=uc.id, streak_count=1))
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
    mult = aggregateMultFactors(res.multFactors or [])
    raw = ctx.weekRawFP
    if raw <= 0:
        return None
    total = (raw + res.totalBonusFP) * mult
    return (total - raw) / raw   # card contribution as a fraction of raw player FP

def randomLineup(rng):
    used, out = set(), []
    for slot, pos in SLOTS:
        pool = [p for p in byPos.get(pos, []) if p.id not in used]
        if not pool:
            return None
        p = rng.choice(pool); used.add(p.id); out.append((slot, pos, p))
    return out

rng = random.Random(SEED)
print(f"season {season} · week {WEEK} · {TRIALS} lineups/edition")
print(f"EDITION_POWER_SCALE = {EDITION_POWER_SCALE}\n")
print(f"  {'edition':12} {'mean':>7} {'median':>7} {'p90':>7}   (card bonus as % of own player FP)")
results = {}
for ed in ('base', 'holographic', 'prismatic', 'diamond'):
    names = effByEd[ed]
    pcts = []
    for _ in range(TRIALS):
        lineup = randomLineup(rng)
        if lineup is None:
            continue
        k = min(len(SLOTS), len(names))
        effects = rng.sample(names, k)
        while len(effects) < len(SLOTS):
            effects.append(rng.choice(names))
        r = scoreLineup(lineup, effects, ed)
        s.rollback()
        if r is not None:
            pcts.append(r)
    if pcts:
        pcts.sort()
        mean = statistics.mean(pcts)
        results[ed] = mean
        p90 = pcts[int(0.9 * (len(pcts) - 1))]
        print(f"  {ed:12} {100*mean:6.0f}% {100*statistics.median(pcts):6.0f}% {100*p90:6.0f}%")
print("\ntarget: mean ~100% every edition (rarity = ceiling/variance, not mean)")
shutil.rmtree(tmp, ignore_errors=True)
