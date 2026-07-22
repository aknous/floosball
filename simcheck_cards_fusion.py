"""Controlled test: does roster strength still matter, holding the CARDS fixed?

The uncontrolled runs are confounded — a CardTemplate is (player, edition,
effect), so strong and weak rosters necessarily hold different effects, and any
spread difference could just be which effects landed where.

This removes the confound: synthesize templates so the SAME effect set is played
by a STRONG lineup and a WEAK lineup (top vs bottom actual week-14 performers at
each position). Only player quality varies. Repeated over many random effect
sets so one lucky set can't carry the answer.

  playerRatio  = strong lineup's own FP / weak lineup's own FP   (the target)
  scoreRatio   = strong lineup's final score / weak lineup's     (what users see)

scoreRatio well below playerRatio = cards are flattening roster choice.
"""
import asyncio, os, random, shutil, statistics, tempfile, logging

DB = 'data/floosball_prod_latest.db'
WEEK = 14
EDITION = os.environ.get('PROBE_EDITION', 'prismatic')
TRIALS = int(os.environ.get('PROBE_TRIALS', '40'))
SEED = 12345

tmp = tempfile.mkdtemp(prefix='floos_ctrl_')
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

# real week stats
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

# players by position (0-based Player.position -> 1-based card position)
byPos = {}
for p in s.query(Player).all():
    # players.position in the DB is 1-BASED (QB=1..K=5), matching
    # CardTemplate.position. The model comment claiming 0-based is wrong —
    # verified against which stat blob is populated per position value.
    if p.position is None:
        continue
    byPos.setdefault(int(p.position), []).append(p)
# Only players who actually played that week. Picking the absolute top vs
# absolute bottom is degenerate — the bottom are non-players with 0/negative FP,
# which makes the ratio meaningless. Use realistic good-vs-poor STARTERS:
# the 20th percentile performer against the 80th.
for pos in byPos:
    played = [p for p in byPos[pos] if (weekFP.get(p.id, 0) or 0) > 0]
    played.sort(key=lambda p: weekFP.get(p.id, 0), reverse=True)
    byPos[pos] = played

SLOTS = [('QB', 1), ('RB', 2), ('WR1', 3), ('WR2', 3), ('TE', 4), ('K', 5)]

def pickLineup(strong):
    """Top (or bottom) actual performers at each slot, no duplicate player."""
    used, out = set(), []
    for slot, pos in SLOTS:
        pool = byPos.get(pos) or []
        if not pool:
            continue
        cut = max(1, int(len(pool) * 0.20))
        band = pool[:cut] if strong else pool[-cut:]
        ordered = band + (pool if strong else list(reversed(pool)))
        for p in ordered:
            if p.id in used:
                continue
            used.add(p.id); out.append((slot, pos, p)); break
    return out

STRONG, WEAK = pickLineup(True), pickLineup(False)

# effect pool: one template per distinct effect at this edition
tpls = s.query(CardTemplate).filter(CardTemplate.season_created == season,
                                    CardTemplate.edition == EDITION).all()
byEffect = {}
for t in tpls:
    en = (t.effect_config or {}).get('effectName')
    if en and en not in byEffect:
        byEffect[en] = t
effectNames = sorted(byEffect)
print(f"edition {EDITION}: {len(effectNames)} distinct effects available")

user = s.query(FantasyRoster).filter_by(season=season).first().user_id

def synthTemplate(effectName, player, pos):
    """A template carrying `effectName` but depicting `player`.

    Copies every column off the source template and overrides only the
    player-specific ones, so NOT NULL columns we don't care about (rarity_weight,
    sell_value, ...) carry through instead of having to be enumerated.
    """
    srcT = byEffect[effectName]
    cols = {c.name for c in CardTemplate.__table__.columns} - {'id', 'created_at'}
    data = {c: getattr(srcT, c) for c in cols}
    data.update(
        player_id=player.id,
        player_name=getattr(player, 'name', '') or 'Probe Player',
        team_id=getattr(player, 'team_id', None),
        player_rating=int(getattr(player, 'player_rating', 75) or 75),
        position=pos,
        effect_config=dict(srcT.effect_config or {}),
        classification=None,
    )
    t = CardTemplate(**data)
    s.add(t); s.flush()
    return t


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
    mult = aggregateMultFactors(res.multFactors or [])
    return {'raw': ctx.weekRawFP, 'bonus': res.totalBonusFP,
            'total': (ctx.weekRawFP + res.totalBonusFP) * mult}

rng = random.Random(SEED)
playerRatios, scoreRatios, bonusS, bonusW, rawS, rawW = [], [], [], [], [], []
for _ in range(TRIALS):
    effects = rng.sample(effectNames, len(SLOTS))
    a, b = score(STRONG, effects), score(WEAK, effects)
    s.rollback()
    if not a or not b or b['total'] <= 0:
        continue
    playerRatios.append(a['raw'] / max(b['raw'], .01))
    scoreRatios.append(a['total'] / b['total'])
    bonusS.append(a['bonus']); bonusW.append(b['bonus'])
    rawS.append(a['raw']); rawW.append(b['raw'])

m = statistics.mean
print(f"\nControlled · {EDITION} · {len(scoreRatios)} random 6-effect sets, "
      f"identical cards on both lineups")
print(f"  strong lineup player FP {m(rawS):.1f}   weak lineup player FP {m(rawW):.1f}")
print(f"  strong card bonus       {m(bonusS):.1f}   weak card bonus       {m(bonusW):.1f}")
print(f"\n  playerRatio (target) = {m(playerRatios):.2f}x")
print(f"  scoreRatio  (actual) = {m(scoreRatios):.2f}x   "
      f"median {statistics.median(scoreRatios):.2f}x")
frac = m(scoreRatios) / m(playerRatios)
print(f"\n  roster signal retained = {100*frac:.0f}%  "
      f"({'cards preserve roster choice' if frac > 0.8 else 'cards are flattening roster choice'})")
shutil.rmtree(tmp, ignore_errors=True)
