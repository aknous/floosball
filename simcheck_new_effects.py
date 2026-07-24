"""Focused demo: equip Full House (full_roster) + Bet Big (all_in) on REAL players
and watch them score against a real season's week-14 stats.

Answers "does the fusion 5c redesign actually fire end-to-end?" — the fresh-sim
simcheck can't, because a fresh DB has no users/equipped cards. This boots the app
against a COPY of the prod DB (real users, real played games) and runs the real
two-pass calculator, exactly like week-end banking does.

  Full House: a Diamond that fires ONLY if every first-pass card cleared its FP power
              bar this week — one cold player kills it.
  Bet Big:    a Prismatic that scales with how far the on-card player's FP beats a
              per-position stud line; nothing on an average week.

Run: .venv/bin/python simcheck_new_effects.py
"""
import asyncio, shutil, tempfile, os, logging

# PROBE_DB: which DB copy to boot against (default: the prod snapshot, which PREDATES the
#   fusion gate). Point it at a fresh fusion-sim DB to test against gate-native templates.
# PROBE_REBUILD: '1' (default) rebuilds each synth card's effect_config via buildEffectConfig
#   so it carries the current gate + params (needed for the stale prod copy). '0' clones the
#   DB's OWN stored config untouched — the honest native-gate test on a gate-native DB.
DB = os.environ.get('PROBE_DB', 'data/floosball_prod_latest.db')
REBUILD = os.environ.get('PROBE_REBUILD', '1') != '0'
WEEK = int(os.environ.get('PROBE_WEEK', '14'))

tmp = tempfile.mkdtemp(prefix='floos_neweff_')
shutil.copy(DB, os.path.join(tmp, 'floosball.db'))
os.environ['DATABASE_DIR'] = tmp
logging.disable(logging.WARNING)

from simcheck_cards import boot, preloadSeason, applyWeekState
container, app = asyncio.run(boot())
from database.connection import get_session
from database.models import (FantasyRoster, EquippedCard, UserCard, CardTemplate,
                             Game, GamePlayerStats, WeeklyPlayerFP, Player, User)
from sqlalchemy import func
from managers.cardProjection import buildProjectionContext
from managers.cardEffectCalculator import calculateWeekCardBonuses, aggregateMultFactors
from managers.cardManager import SLOT_TO_ORDINAL
from managers.cardEffects import buildEffectConfig
from managers.fantasyTracker import _dbStatsToCardFormat

print(f"DB={DB}  rebuildConfigs={REBUILD}  week={WEEK}")
sm = getattr(app, 'seasonManager', None) or container.getService('season_manager')
pm = getattr(app, 'playerManager', None) or container.getService('player_manager')
s = get_session()
# Season: prefer a fantasy-roster season; else the latest season with played WEEK games
# (a fresh fusion-sim DB has no rosters/users yet — seed a probe user + roster below).
season = s.query(func.max(FantasyRoster.season)).scalar()
if season is None:
    row = (s.query(Game.season).filter(Game.week == WEEK, Game.status == 'final')
           .order_by(Game.season.desc()).first())
    season = row[0] if row else 1
if s.query(FantasyRoster).filter_by(season=season).first() is None:
    u = s.query(User).first()
    if u is None:
        u = User(email='probe@floos.test', username='probe'); s.add(u); s.flush()
    s.add(FantasyRoster(user_id=u.id, season=season)); s.commit()
    print(f"seeded probe user {u.id} + roster for season {season}")
teamGames, byWeek, eloByTeam = preloadSeason(s, season)

# Real week-14 stats keyed by player id
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

user = s.query(FantasyRoster).filter_by(season=season).first().user_id

# One source template per (effect, edition) to clone the non-player columns from
# (edition, season_created, output_type, ...). Any season — we only need the columns.
def srcTemplate(effectName, edition):
    return (s.query(CardTemplate)
            .filter(CardTemplate.edition == edition)
            .filter(CardTemplate.effect_config.like(f'%"effectName": "{effectName}"%'))
            .first())

_configSrc = {}  # effectName -> 'native (stored)' | 'rebuilt' — for the honesty summary

def synthTemplate(effectName, edition, player, pos):
    src = srcTemplate(effectName, edition)
    cols = {c.name for c in CardTemplate.__table__.columns} - {'id', 'created_at'}
    data = {c: getattr(src, c) for c in cols} if src else {}
    rating = int(getattr(player, 'player_rating', 80) or 80)
    # REBUILD off + the DB already carries this effect's config -> clone the DB's OWN stored
    # config untouched (the native-gate test). Otherwise rebuild via the current builder so
    # the card carries the current gate + params (needed for the pre-gate prod copy, or when
    # this effect didn't happen to mint into the DB).
    if not REBUILD and src and (src.effect_config or {}).get('effectName') == effectName:
        cfg = dict(src.effect_config); _configSrc[effectName] = 'native (stored)'
    else:
        cfg = buildEffectConfig(edition, rating, pos, forceEffect=effectName)
        _configSrc[effectName] = 'rebuilt' + ('' if src else ' (not minted in DB)')
    assert cfg, f"no config for {effectName}"
    data.update(player_id=player.id, player_name=getattr(player, 'name', '') or 'Probe',
                team_id=getattr(player, 'team_id', None), player_rating=rating,
                position=pos, effect_config=cfg, classification=None)
    t = CardTemplate(**data); s.add(t); s.flush()
    return t

def runLineup(spec):
    """spec = [(slot, pos, player, effectName, edition)]; returns (breakdowns, ctx, res)."""
    s.query(EquippedCard).filter_by(user_id=user, season=season, week=WEEK).delete(); s.flush()
    for slot, pos, player, en, ed in spec:
        t = synthTemplate(en, ed, player, pos)
        uc = UserCard(user_id=user, card_template_id=t.id, acquired_via='probe', tier=1)
        s.add(uc); s.flush()
        s.add(EquippedCard(user_id=user, season=season, week=WEEK, slot=slot,
                           slot_number=SLOT_TO_ORDINAL.get(slot, 1), user_card_id=uc.id,
                           streak_count=1))
    s.flush()
    ctx = buildProjectionContext(s, user, season, WEEK, sm, pm)
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
    return res, ctx

def out(b):
    if b.primaryMult and b.primaryMult > 1: return f"x{b.primaryMult:.2f} FPx"
    if b.primaryFP: return f"+{b.primaryFP:.1f} FP"
    if b.floobitsEarned: return f"+{b.floobitsEarned}F"
    return "— (no payout)"

def report(title, res, ctx):
    print(f"\n{'='*74}\n{title}\n{'='*74}")
    print(f" first-pass gated cards: {getattr(ctx,'_firstPassGatedCount',0)} present, "
          f"{getattr(ctx,'_firstPassGatedOn',0)} cleared their bar")
    print(f" {'slot':5} {'effect':12} {'player':22} {'wkFP':>5}  {'result':>16}")
    for b in res.cardBreakdowns:
        fp = round((ctx.weekPlayerStats.get(b.playerId, {}) or {}).get('fantasyPoints', 0) or 0, 1)
        print(f" {'':5} {b.effectName:12} {b.playerName[:22]:22} {fp:5.1f}  {out(b):>16}")
    print(f" -> total bonus FP {res.totalBonusFP:.1f} | mult {aggregateMultFactors(res.multFactors or []):.2f}x")

topQB, topRB = byPos[1][0], byPos[2][0]
wr = byPos[3]; te, k = byPos[4][0], byPos[5][0]
# a clearly-cold WR (near the bottom of the played band) to break Full House
coldWR = byPos[3][-1]

# ── Scenario A: full clean lineup -> Full House FIRES ──
specA = [('QB', 1, topQB, 'all_in', 'prismatic'),
         ('RB', 2, topRB, 'freebie', 'base'),
         ('WR1', 3, wr[0], 'freebie', 'base'),
         ('WR2', 3, wr[1], 'freebie', 'base'),
         ('TE', 4, te, 'freebie', 'base'),
         ('K', 5, k, 'full_roster', 'diamond')]
res, ctx = runLineup(specA)
report("A. Strong lineup — all 5 first-pass cards clear -> Full House FIRES; "
       "Bet Big rides the top QB", res, ctx); s.rollback()

# ── Scenario B: one cold WR -> Full House GATES OFF ──
specB = [('QB', 1, topQB, 'all_in', 'prismatic'),
         ('RB', 2, topRB, 'freebie', 'base'),
         ('WR1', 3, coldWR, 'freebie', 'base'),        # cold player -> its bar stays empty
         ('WR2', 3, wr[1], 'freebie', 'base'),
         ('TE', 4, te, 'freebie', 'base'),
         ('K', 5, k, 'full_roster', 'diamond')]
res, ctx = runLineup(specB)
report("B. One cold WR — its power bar stays empty -> Full House pays NOTHING", res, ctx); s.rollback()

# ── Scenario C: Bet Big on a modest QB -> under the stud line, nothing ──
modestQB = byPos[1][len(byPos[1])//2]   # median QB performer that week
specC = [('QB', 1, modestQB, 'all_in', 'prismatic'),
         ('RB', 2, topRB, 'freebie', 'base'),
         ('WR1', 3, wr[0], 'freebie', 'base'),
         ('WR2', 3, wr[1], 'freebie', 'base'),
         ('TE', 4, te, 'freebie', 'base'),
         ('K', 5, k, 'freebie', 'base')]
res, ctx = runLineup(specC)
report("C. Bet Big on a MEDIAN-week QB — under the stud line -> no payout", res, ctx); s.rollback()

print(f"\nconfig source per effect: {_configSrc}")
shutil.rmtree(tmp, ignore_errors=True)
print("(scratch dir cleaned up)")
