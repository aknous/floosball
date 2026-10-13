"""Replay a real user's equipped lineup, week by week, through the CURRENT card calculator.

For card reports from a specific user ("all my cards cleared their bar but X didn't
fire"): boots against a COPY of a prod snapshot, and for each week of a season takes that
user's equipped cards and that week's real player stats, scores them through the real
two-pass calculator, and prints every card's power bar and result beside what was BANKED
for the week. A difference between the two columns is a change in the code since the week
banked (or a bug).

The lineup is read from `equipped_cards` for that week. ⚠️ Those rows can be rewritten by
an equip made after the week banked (see CLAUDE.md, Fantasy System), so a week whose banked
players differ from the replayed ones is flagged rather than trusted.

  PROBE_DB=path/to/prod.db PROBE_USER=Asca PROBE_SEASON=10 .venv/bin/python simcheck_replay_lineup.py
  PROBE_WEEKS=4,5,6   limit to some weeks (default: every banked week)
"""
import asyncio
import json
import logging
import os
import shutil
import tempfile

DB = os.environ.get('PROBE_DB', 'data/floosball.db')
USER = os.environ.get('PROBE_USER')
SEASON = os.environ.get('PROBE_SEASON')
WEEKS = os.environ.get('PROBE_WEEKS')
if not USER:
    raise SystemExit("set PROBE_USER (username or id)")

tmp = tempfile.mkdtemp(prefix='floos_replay_')
shutil.copy(DB, os.path.join(tmp, 'floosball.db'))
os.environ['DATABASE_DIR'] = tmp
logging.disable(logging.WARNING)

from simcheck_cards import boot, preloadSeason, applyWeekState
container, app = asyncio.run(boot())
from sqlalchemy import func
from database.connection import get_session
from database.models import (EquippedCard, Game, GamePlayerStats, WeeklyPlayerFP,
                             WeeklyCardBonus, User)
from managers.cardProjection import buildProjectionContext
from managers.cardEffectCalculator import (calculateWeekCardBonuses, aggregateMultFactors,
                                           _SECOND_PASS_EFFECTS)
from managers.fantasyTracker import _dbStatsToCardFormat
from managers.coreEquations import computeFinalOutput
from managers.anomalyManager import getActiveCriticalityCore

sm = getattr(app, 'seasonManager', None) or container.getService('season_manager')
pm = getattr(app, 'playerManager', None) or container.getService('player_manager')
s = get_session()

user = (s.query(User).filter(User.id == int(USER)).first() if USER.isdigit()
        else s.query(User).filter(func.lower(User.username) == USER.lower()).first())
if user is None:
    raise SystemExit(f"no user {USER!r}")
season = int(SEASON) if SEASON else s.query(func.max(WeeklyCardBonus.season)).scalar()
banked = {r.week: r for r in s.query(WeeklyCardBonus).filter_by(user_id=user.id, season=season)}
weeks = sorted(int(w) for w in WEEKS.split(',')) if WEEKS else sorted(banked)
print(f"DB={DB}  user={user.username} ({user.id})  season={season}  weeks={weeks}")
teamGames, byWeek, eloByTeam = preloadSeason(s, season)


def realStats(week):
    weekFP = {r.player_id: r.fantasy_points
              for r in s.query(WeeklyPlayerFP).filter_by(season=season, week=week)}
    out = {}
    for gps in (s.query(GamePlayerStats).join(Game, GamePlayerStats.game_id == Game.id)
                .filter(Game.season == season, Game.week == week)):
        out[gps.player_id] = _dbStatsToCardFormat(
            gps.passing_stats, gps.rushing_stats, gps.receiving_stats, gps.kicking_stats,
            weekFP.get(gps.player_id, 0), teamId=gps.team_id)
        if gps.q4_fantasy_points:
            out[gps.player_id]["q4FantasyPoints"] = gps.q4_fantasy_points
    for pid, fp in weekFP.items():
        out.setdefault(pid, _dbStatsToCardFormat({}, {}, {}, {}, fp))
    return out


def result(b):
    parts = []
    if b.totalFP:
        parts.append(f"+{b.totalFP:.1f} FP")
    if b.primaryMult and b.primaryMult > 1:
        parts.append(f"x{b.primaryMult:.2f}")
    if b.floobitsEarned:
        parts.append(f"+{b.floobitsEarned}F")
    return ", ".join(parts) or "-"


def bar(b, fp):
    if not b.gateThreshold:
        return "no bar"
    state = "ON " if b.gateActive else ("off" if b.gateActive is False else "?  ")
    return f"{state} {fp:5.1f}/{b.gateThreshold:g}"


for week in weeks:
    eqs = s.query(EquippedCard).filter_by(user_id=user.id, season=season, week=week).all()
    if not eqs:
        print(f"\n--- week {week}: no equipped rows"); continue
    stats = realStats(week)
    ctx = buildProjectionContext(s, user.id, season, week, sm, pm)
    applyWeekState(ctx, ctx.userFavoriteTeamId, week, teamGames, byWeek, eloByTeam)
    # buildProjectionContext builds an EXPECTED projection (EV-scaled bars, chance cards at
    # their odds); score it LIVE, as week-end banking does.
    ctx.isProjection = False
    ctx.projectionVariant = None
    ctx.gamesActive = False
    ctx.weekPlayerStats = {pid: stats.get(pid, {}) for pid in ctx.rosterPlayerIds}
    ctx.weekRawFP = sum((st or {}).get('fantasyPoints', 0) for st in ctx.weekPlayerStats.values())
    res = calculateWeekCardBonuses(eqs, ctx)
    # The banked figure is the WHOLE card bonus (FPx converted through the lineup's raw FP),
    # computed the way week-end banking does, so the two columns compare like for like.
    try:
        core = getActiveCriticalityCore(season, week)
    except Exception:
        core = None
    grand, _ = computeFinalOutput(ctx.weekRawFP, res.totalBonusFP, res.multFactors, coreKey=core)
    replayedBonus = max(0.0, round(grand - ctx.weekRawFP, 2))

    bankRow = banked.get(week)
    bankBds = {}
    if bankRow and bankRow.breakdowns_json:
        for bb in (json.loads(bankRow.breakdowns_json) or {}).get('breakdowns', []):
            bankBds[bb.get('slotNumber')] = bb
    print(f"\n{'=' * 100}\nweek {week}  modifier={ctx.activeModifier or '-'}  "
          f"banked bonus={bankRow.bonus_fp if bankRow else '-'}  replayed bonus={replayedBonus:.2f}"
          f"  FPx={aggregateMultFactors(res.multFactors or []):.2f}")
    print(f" {'slot':>4} {'effect':16} {'player':22} {'bar':>14}  {'replayed':>16}  banked")
    for b in sorted(res.cardBreakdowns, key=lambda b: b.slotNumber):
        fp = (ctx.weekPlayerStats.get(b.playerId, {}) or {}).get('fantasyPoints', 0) or 0
        bb = bankBds.get(b.slotNumber, {})
        flag = "" if not bb or bb.get('playerId') == b.playerId else "  [LINEUP DIFFERS FROM BANKED]"
        pas = "2p" if b.effectName in _SECOND_PASS_EFFECTS else "1p"
        print(f" {b.slotNumber:>4} {b.effectName[:13]:13} {pas} {b.playerName[:22]:22} {bar(b, fp):>14}"
              f"  {result(b):>16}  {bb.get('equation', '')[:60]}{flag}")
        print(f" {'':4} {'':16} {'':22} {'':14}  {'':16}  now: {b.equation[:60]}")
    if any(b.effectName == 'full_roster' for b in res.cardBreakdowns):
        firstPass = [b for b in res.cardBreakdowns
                     if b.gateThreshold and b.effectName not in _SECOND_PASS_EFFECTS]
        print(f" Full House tally: {getattr(ctx, '_fullHouseGatedOn', 0)}/"
              f"{getattr(ctx, '_fullHouseGatedCount', 0)} cards cleared (all passes); "
              f"first-pass only (old rule) would read "
              f"{sum(1 for b in firstPass if b.gateActive)}/{len(firstPass)}")

s.rollback()
shutil.rmtree(tmp, ignore_errors=True)
