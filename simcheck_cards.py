"""Card-balance sim-check — full-season replay.

Boots the real managers against a COPY of a backed-up DB, then REPLAYS a
completed season week-by-week for a sample of real users, running every card
through the real card calculator each week. Unlike a single-week snapshot this:

  * reconstructs each week's team state as-of-week-W (wins/losses/win-streak/
    won-this-week/margin/comeback) from the game history, so streak ODDS and
    favorite-team effects see the season evolve;
  * CARRIES a per-card streak counter across weeks (incremented when the
    effect's streak condition holds, reset when it breaks — via the real
    `checkStreakCondition`), so streak cards accumulate + decay like live;
  * Monte-Carlos chance cards (the calculator rolls `random` internally) by
    averaging R rolls per week → real EV that reflects evolving odds.

Roster player stats use per-game season averages (fixed across weeks).
APPROXIMATIONS (flagged): ELO is the season-end value (pre-game ELO isn't
stored per week); walk-off / Q4 / pick-em streak conditions aren't reconstructed.

Read-only on the source DB (runs on a temp copy). Does not run the sim loop.

  .venv/bin/python simcheck_cards.py
  .venv/bin/python simcheck_cards.py --db data/floosball_prod_latest.db --season 8 --users 15 --runs 20
"""
import argparse
import asyncio
import os
import shutil
import statistics
import sys
import tempfile
import time

TARGETS = {
    'base':        'avg ~7.6  ceil 12',
    'holographic': 'avg ~6.6  ceil 20',
    'prismatic':   'avg ~12.3 ceil 42',
    'diamond':     'avg ~9.9  ceil 21',
}
EDITION_ORDER = ['base', 'holographic', 'prismatic', 'diamond']
REG_WEEKS = list(range(1, 29))  # 28-week regular season
# Static cards (not streak/chance) only need a sample of weeks for their average;
# streak + chance cards run every week (they need the season to evolve).
SAMPLE_WEEKS = {4, 8, 12, 16, 20, 24, 28}


def parseArgs():
    p = argparse.ArgumentParser()
    p.add_argument('--db', default='data/floosball_prod_latest.db')
    p.add_argument('--season', type=int, default=None)
    p.add_argument('--users', type=int, default=8)
    p.add_argument('--runs', type=int, default=8, help='Monte-Carlo rolls per chance card per week')
    return p.parse_args()


async def boot():
    from database.connection import init_db
    from service_container import container
    from config_manager import get_config
    from managers.floosballApplication import FloosballApplication
    init_db()
    config = get_config()
    config['timingMode'] = 'fast'
    config['scheduleGap'] = 0
    app = FloosballApplication(container)
    await app.initializeLeague(config, force_fresh=False)
    return container, app


def _cum3(g, isHome):
    h = (g.home_score_q1 or 0) + (g.home_score_q2 or 0) + (g.home_score_q3 or 0)
    a = (g.away_score_q1 or 0) + (g.away_score_q2 or 0) + (g.away_score_q3 or 0)
    return (h, a) if isHome else (a, h)


def preloadSeason(session, season):
    """teamGames[teamId] = [{week, won, margin, oppId, comeback}], byWeek[w] =
    {teamId: won}, eloByTeam[teamId] = season-end ELO."""
    from database.models import Game, TeamSeasonStats
    games = (session.query(Game)
             .filter(Game.season == season, Game.week.in_(REG_WEEKS))
             .all())
    teamGames, byWeek = {}, {}
    for g in games:
        if (g.status or '').lower() != 'final':
            continue
        if g.home_score == g.away_score:
            continue
        homeWon = g.home_score > g.away_score
        for teamId, oppId, isHome, won in (
            (g.home_team_id, g.away_team_id, True, homeWon),
            (g.away_team_id, g.home_team_id, False, not homeWon),
        ):
            myc3, oppc3 = _cum3(g, isHome)
            myScore = g.home_score if isHome else g.away_score
            oppScore = g.away_score if isHome else g.home_score
            teamGames.setdefault(teamId, []).append({
                'week': g.week, 'won': won, 'margin': myScore - oppScore,
                'oppId': oppId, 'comeback': bool(won and myc3 < oppc3),
            })
            byWeek.setdefault(g.week, {})[teamId] = won
    for lst in teamGames.values():
        lst.sort(key=lambda x: x['week'])
    eloByTeam = {r.team_id: (r.elo or 1500)
                 for r in session.query(TeamSeasonStats).filter_by(season=season).all()}
    return teamGames, byWeek, eloByTeam


def _streakAt(games, w):
    streak = peak = 0
    for g in games:
        if g['week'] > w:
            break
        if g['won']:
            streak = streak + 1 if streak > 0 else 1
        else:
            streak = streak - 1 if streak < 0 else -1
        peak = max(peak, abs(streak))
    return streak, peak


def applyWeekState(ctx, favTeamId, w, teamGames, byWeek, eloByTeam):
    games = teamGames.get(favTeamId, [])
    upTo = [g for g in games if g['week'] <= w]
    wins = sum(1 for g in upTo if g['won'])
    losses = len(upTo) - wins
    streak, peak = _streakAt(games, w)
    priorStreak, _ = _streakAt(games, w - 1)
    favElo = eloByTeam.get(favTeamId, 1500)
    thisGame = next((g for g in upTo if g['week'] == w), None)
    upsetWins = sum(1 for g in upTo if g['won'] and eloByTeam.get(g['oppId'], 1500) > favElo)

    ctx.favoriteTeamSeasonWins = wins
    ctx.favoriteTeamSeasonLosses = losses
    ctx.favoriteTeamStreak = streak
    ctx.favoriteTeamPriorStreak = priorStreak
    ctx.favoriteTeamPeakStreak = peak
    ctx.favoriteTeamSeasonUpsetWins = upsetWins
    ctx.favoriteTeamInPlayoffs = False
    ctx.favoriteTeamElo = favElo
    ctx.leagueAverageElo = sum(eloByTeam.values()) / len(eloByTeam) if eloByTeam else 1500
    ctx.teamResults = dict(byWeek.get(w, {}))
    if thisGame:
        ctx.favoriteTeamWonThisWeek = thisGame['won']
        ctx.favoriteTeamGameFinal = True
        ctx.favoriteTeamScoreMargin = thisGame['margin']
        ctx.favoriteTeamComebackWin = thisGame['comeback']
        ctx.favoriteTeamOpponentElo = eloByTeam.get(thisGame['oppId'], 1500)
    else:
        ctx.favoriteTeamWonThisWeek = False
        ctx.favoriteTeamGameFinal = False
        ctx.favoriteTeamScoreMargin = 0
        ctx.favoriteTeamComebackWin = False


def main():
    args = parseArgs()
    if not os.path.exists(args.db):
        print(f"DB not found: {args.db}"); sys.exit(1)
    tmp = tempfile.mkdtemp(prefix='floos_simcheck_')
    shutil.copy(args.db, os.path.join(tmp, 'floosball.db'))
    os.environ['DATABASE_DIR'] = tmp
    print(f"Working copy: {tmp}/floosball.db  (source {args.db}, untouched)")

    container, app = asyncio.run(boot())

    from database.connection import get_session
    from database.models import CardTemplate, FantasyRoster
    from sqlalchemy import func
    from managers.cardProjection import (
        buildProjectionContext, _wrapTemplateAsUserCard, _wrapUserCardAsEquipped,
        _isChanceEffect,
    )
    from managers.cardEffectCalculator import calculateWeekCardBonuses
    from managers.cardEffects import STREAK_CONFIGS, checkStreakCondition

    sm = getattr(app, 'seasonManager', None) or container.getService('season_manager')
    pm = getattr(app, 'playerManager', None) or container.getService('player_manager')

    session = get_session()
    season = args.season or session.query(func.max(FantasyRoster.season)).scalar()
    teamGames, byWeek, eloByTeam = preloadSeason(session, season)

    # Rebuild each template's primary params from the CURRENT builders, so the
    # tool evaluates the live card definitions (what next season's cards
    # regenerate with) — not last season's values baked into the DB.
    from managers.cardEffects import rebuildPrimaryParams

    class _FauxTpl:
        pass

    def freshTemplate(t):
        ft = _FauxTpl()
        for a in ('id', 'player_rating', 'position', 'edition', 'player_id',
                  'player_name', 'classification'):
            setattr(ft, a, getattr(t, a, None))
        ec = dict(t.effect_config or {})
        ename = ec.get('effectName')
        try:
            fresh = rebuildPrimaryParams(ename, getattr(t, 'player_rating', 75) or 75,
                                         ec.get('editionScale', 1.0))
            if isinstance(fresh, dict):
                posLabel = (ec.get('primary') or {}).get('posLabel')
                if posLabel:
                    fresh['posLabel'] = posLabel
                ec['primary'] = fresh
        except Exception:
            pass
        ft.effect_config = ec
        return ft

    byEffect = {}
    for t in session.query(CardTemplate).all():
        ename = (t.effect_config or {}).get('effectName')
        if ename and ename not in byEffect:
            byEffect[ename] = freshTemplate(t)

    userIds = [r.user_id for r in session.query(FantasyRoster).filter_by(season=season).all() if r.players]
    userIds = userIds[:args.users]

    # Classify effects once (chance/streak run every week; static ones sampled).
    kind = {}
    for ename, tpl in byEffect.items():
        eq = _wrapUserCardAsEquipped(_wrapTemplateAsUserCard(tpl))
        cfg = STREAK_CONFIGS.get(ename)
        if _isChanceEffect(eq):
            kind[ename] = 'chance'
        elif bool(cfg) and not cfg.get('isWeekly', False):
            kind[ename] = 'streak'
        else:
            kind[ename] = 'static'
    nChance = sum(1 for k in kind.values() if k == 'chance')
    nStreak = sum(1 for k in kind.values() if k == 'streak')
    print(f"Season {season} · {len(byEffect)} effects ({nChance} chance, {nStreak} streak) · "
          f"{len(userIds)} users · {args.runs} MC rolls/chance")
    print(f"streak/chance: all {len(REG_WEEKS)} weeks · static: {len(SAMPLE_WEEKS)}-week sample\n")

    # acc[ename] = {'edition', 'fp':[per user-week], 'fpx':[], 'fl':[], 'season':{uid: total}}
    acc = {}
    for ui, uid in enumerate(userIds):
        t0 = time.monotonic()
        streakCarry = {}  # effectName -> current streak count
        skipped = False
        for w in REG_WEEKS:
            # Fresh context per (user, week) — the calculator mutates cumulative
            # fields on ctx, so reusing one object across weeks/cards inflates
            # values. Rebuild, then override the team state to as-of-week-W.
            ctx = buildProjectionContext(session, uid, season, w, sm, pm)
            if ctx is None:
                skipped = True
                break
            applyWeekState(ctx, ctx.userFavoriteTeamId, w, teamGames, byWeek, eloByTeam)
            for ename, tpl in byEffect.items():
                k = kind[ename]
                isStreak = k == 'streak'
                isChance = k == 'chance'
                if k == 'static' and w not in SAMPLE_WEEKS:
                    continue  # static cards: sample weeks only
                eq = _wrapUserCardAsEquipped(_wrapTemplateAsUserCard(tpl))
                ctx.cardPosition = tpl.position or 0
                ctx.streakCounts = {eq.id: streakCarry.get(ename, 0)} if isStreak else {}
                runs = args.runs if isChance else 1
                base = getattr(ctx, 'weekRawFP', 0) or 0  # FP the multiplier applies to
                fp = fpx = fpeq = fl = 0.0
                for _ in range(runs):
                    try:
                        res = calculateWeekCardBonuses([eq], ctx)
                    except Exception:
                        continue
                    pf = 1.0
                    for f in (res.multFactors or []):
                        pf *= f
                    d = pf - 1.0
                    fp += res.totalBonusFP; fpx += d; fpeq += d * base; fl += res.floobitsEarned
                fp /= runs; fpx /= runs; fpeq /= runs; fl /= runs
                val = fp + fpeq  # combined value: flat FP + FP-equivalent of the FPx
                a = acc.setdefault(ename, {'edition': tpl.edition, 'val': [], 'fp': [], 'fpx': [], 'fl': [], 'season': {}})
                a['val'].append(val); a['fp'].append(fp); a['fpx'].append(fpx); a['fl'].append(fl)
                a['season'][uid] = a['season'].get(uid, 0.0) + val
                if isStreak:
                    met = False
                    try:
                        met = checkStreakCondition(ename, ctx, tpl.player_id)
                    except Exception:
                        met = False
                    streakCarry[ename] = streakCarry.get(ename, 0) + 1 if met else 0
        status = 'skipped (no roster)' if skipped else f'done in {time.monotonic()-t0:.1f}s'
        print(f"  user {ui+1}/{len(userIds)} (id {uid}) {status}", flush=True)

    chanceSet = {e for e, k in kind.items() if k == 'chance'}
    streakSet = {e for e, k in kind.items() if k == 'streak'}
    print()

    # wkVal = combined per-week value (flat FP + FP-equivalent of FPx). This is
    # the band metric — it makes FPx-primary cards comparable to FP cards.
    hdr = f"{'effect':22} {'wkVal':>7} {'wkMax':>7} {'seasVal':>8} {'fp':>6} {'fpx':>6} {'wkF':>6}"
    for ed in EDITION_ORDER:
        rows = [(e, a) for e, a in acc.items() if a['edition'] == ed]
        if not rows:
            continue
        rows.sort(key=lambda x: statistics.mean(x[1]['val']) if x[1]['val'] else 0, reverse=True)
        print(f"━━ {ed.upper()}  (target {TARGETS.get(ed,'')}) " + "━" * 18)
        print(hdr)
        for ename, a in rows:
            wkVal = statistics.mean(a['val']) if a['val'] else 0
            wkMax = max(a['val']) if a['val'] else 0
            seasVal = statistics.mean(a['season'].values()) if a['season'] else 0
            fp = statistics.mean(a['fp']) if a['fp'] else 0
            fpx = statistics.mean(a['fpx']) if a['fpx'] else 0
            fl = statistics.mean(a['fl']) if a['fl'] else 0
            tag = ''
            if ename == 'showoff':
                tag = '  <-- OP?'
            elif ename in chanceSet:
                tag = '  (chance)'
            elif ename in streakSet:
                tag = '  (streak)'
            print(f"{ename:22} {wkVal:7.1f} {wkMax:7.1f} {seasVal:8.0f} {fp:6.1f} {fpx:+6.2f} {fl:6.1f}{tag}")
        print()
    print("wkVal = flat FP + FP-equivalent of FPx (multiplier x roster FP base). The band metric.")
    print("seasVal = avg per-user season total. wkMax exposes streak/chance peaks. wkF = floobits (separate currency).")
    session.close()


if __name__ == '__main__':
    main()
