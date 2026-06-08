"""Card-balance sim-check v2 — full-hand MARGINAL contribution.

v1 tested each card alone, so synergy/amplifier/cross cards (which act on the
REST of a hand) read ~0 and FPx got mashed in with FP. v2 fixes both:

  * MARGINAL value: each card's score = handValue(reference hand + card) -
    handValue(reference hand), where handValue = (rosterFP + flatBonus) x FPx.
    So an amplifier shows up as the boost it gives the rest of the hand, a
    cross-card as what it copies/triggers, an FPx card as its multiply on the
    whole hand.
  * 3 REFERENCE HANDS so every synergy type has something to act on: an FP hand
    (TD/FG/yard/flat -> amplifiers, copycat, double_down, conductor), a chance
    hand (-> high_roller, providence, catalyst, advantage, charmed), and a
    streak hand (-> fortitude). Each card's score = best marginal across the 3.
  * SEPARATE categories: FP / FPx / Floobits / Synergy-Amplifier, each banded
    on its own (FPx is never compared against FP).

Single-week contexts (sampled real rosters); chance cards Monte-Carlo'd; streak
cards held at a representative mid-streak. Boots real managers against a copy of
a backup DB (read-only on source). Reuses v1's boot + context machinery.

  .venv/bin/python simcheck_cards_v2.py
  .venv/bin/python simcheck_cards_v2.py --db data/floosball_prod_latest.db --users 6 --runs 5 --week 14
"""
import argparse
import asyncio
import os
import shutil
import statistics
import sys
import tempfile

from simcheck_cards import boot, preloadSeason, applyWeekState

REF_FP = ['touchdown_pinata', 'three_pointer', 'expedition', 'freebie']
REF_CHANCE = ['scrappy', 'martyr', 'underdog', 'traverse']
REF_STREAK = ['on_fire', 'snowball_fight', 'drought', 'quiet_storm']
REP_STREAK_COUNT = 3  # representative mid-streak for streak cards in a hand
BANDS = {'FP': '~35 base / 50 holo / 70 prismatic', 'FPx': 'judged on its own',
         'Floobit': 'separate currency', 'Synergy/Amp': 'marginal boost to a hand'}


def parseArgs():
    p = argparse.ArgumentParser()
    p.add_argument('--db', default='data/floosball_prod_latest.db')
    p.add_argument('--season', type=int, default=None)
    p.add_argument('--users', type=int, default=6)
    p.add_argument('--runs', type=int, default=1, help='deterministic (projection EV); 1 is enough')
    p.add_argument('--week', type=int, default=14, help='representative week to sample')
    return p.parse_args()


def main():
    args = parseArgs()
    if not os.path.exists(args.db):
        print(f"DB not found: {args.db}"); sys.exit(1)
    tmp = tempfile.mkdtemp(prefix='floos_simcheck2_')
    shutil.copy(args.db, os.path.join(tmp, 'floosball.db'))
    os.environ['DATABASE_DIR'] = tmp
    print(f"Working copy: {tmp}/floosball.db  (source {args.db}, untouched)")

    container, app = asyncio.run(boot())

    from database.connection import get_session
    from database.models import CardTemplate, FantasyRoster
    from sqlalchemy import func
    from managers.cardProjection import (
        buildProjectionContext, _wrapTemplateAsUserCard, _wrapUserCardAsEquipped, _isChanceEffect,
    )
    from managers.cardEffectCalculator import calculateWeekCardBonuses, aggregateMultFactors
    from managers.cardEffects import (
        rebuildPrimaryParams, STREAK_CONFIGS, EFFECT_CATEGORY, EFFECT_REGISTRY, EFFECT_EDITION_TIER,
    )

    sm = getattr(app, 'seasonManager', None) or container.getService('season_manager')
    pm = getattr(app, 'playerManager', None) or container.getService('player_manager')
    session = get_session()
    season = args.season or session.query(func.max(FantasyRoster.season)).scalar()
    teamGames, byWeek, eloByTeam = preloadSeason(session, season)

    def freshTemplate(t):
        class _F: pass
        ft = _F()
        for a in ('id', 'player_rating', 'position', 'edition', 'player_id', 'player_name', 'classification'):
            setattr(ft, a, getattr(t, a, None))
        ec = dict(t.effect_config or {})
        ec['editionScale'] = 1.0
        ename = ec.get('effectName')
        try:
            fresh = rebuildPrimaryParams(ename, getattr(t, 'player_rating', 75) or 75, 1.0)
            if isinstance(fresh, dict):
                pl = (ec.get('primary') or {}).get('posLabel')
                if pl:
                    fresh['posLabel'] = pl
                ec['primary'] = fresh
        except Exception:
            pass
        ft.effect_config = ec
        return ft

    # Only effects with a live compute handler — legacy/removed effects (in old
    # stored templates but absent from EFFECT_REGISTRY) contribute a phantom
    # ~42 baseline and are excluded so the zero line is clean.
    byEffect, primaryByEffect = {}, {}
    skippedLegacy = set()
    for t in session.query(CardTemplate).all():
        ename = (t.effect_config or {}).get('effectName')
        if not ename or ename in byEffect:
            continue
        if ename not in EFFECT_REGISTRY:
            skippedLegacy.add(ename)
            continue
        byEffect[ename] = freshTemplate(t)
        primaryByEffect[ename] = (byEffect[ename].effect_config.get('primary') or {})
    if skippedLegacy:
        print(f"Skipped {len(skippedLegacy)} legacy effect(s) (no handler): "
              f"{', '.join(sorted(skippedLegacy))}\n")

    def category(ename):
        ec = byEffect[ename].effect_config
        prim = primaryByEffect[ename]
        if prim.get('isAmplifier'):
            return 'Synergy/Amp'
        if EFFECT_CATEGORY.get(ename) == 'cross':
            return 'Synergy/Amp'
        ot = ec.get('outputType', 'fp')
        if ot == 'mult':
            return 'FPx'
        if ot == 'floobits':
            return 'Floobit'
        return 'FP'

    def equip(ename):
        return _wrapUserCardAsEquipped(_wrapTemplateAsUserCard(byEffect[ename]))

    def setStreaks(ctx, eqs, enames):
        ctx.streakCounts = {}
        for eq, en in zip(eqs, enames):
            cfg = STREAK_CONFIGS.get(en)
            if cfg and not cfg.get('isWeekly', False):
                ctx.streakCounts[eq.id] = REP_STREAK_COUNT

    def freshCtx(uid):
        """A clean projection context per measurement. Streak/multiplier state
        bleeds through a reused ctx (computing one streak/FPx hand leaves mult
        state that inflates the NEXT hand), so every handValue() gets its own."""
        c = buildProjectionContext(session, uid, season, args.week, sm, pm)
        if c is None:
            return None
        applyWeekState(c, c.userFavoriteTeamId, args.week, teamGames, byWeek, eloByTeam)
        return c

    def handValue(uid, enames, runs):
        """(rosterFP + flatBonus) x aggregated FPx, and floobits. Builds its own
        fresh ctx so no prior hand can contaminate it. Deterministic
        (ctx.isProjection => chance cards return EV), so runs=1 suffices. FPx is
        aggregated the way the game does it: 1 + sum(f-1), NOT a product."""
        ctx = freshCtx(uid)
        if ctx is None:
            return 0.0, 0.0
        eqs = [equip(e) for e in enames]
        base = getattr(ctx, 'weekRawFP', 0) or 0
        setStreaks(ctx, eqs, enames)
        try:
            res = calculateWeekCardBonuses(eqs, ctx)
        except Exception:
            return 0.0, 0.0
        mult = aggregateMultFactors(res.multFactors or [])
        return (base + res.totalBonusFP) * mult, float(res.floobitsEarned)

    userIds = [r.user_id for r in session.query(FantasyRoster).filter_by(season=season).all() if r.players]
    userIds = userIds[:args.users]
    refs = {'FP': REF_FP, 'CHANCE': REF_CHANCE, 'STREAK': REF_STREAK}
    print(f"Season {season} · week {args.week} · {len(byEffect)} effects · {len(userIds)} users · "
          f"{args.runs} MC · 3 reference hands\n")

    # Each category is judged in the reference hand that isolates it cleanly:
    #   FP / FPx -> REF_FP (no baseline multiplier, so an FP card reads its raw FP
    #               and an FPx card reads its multiply on a known FP base);
    #   Synergy/Amp / Floobit -> best across all 3 (they need the right substrate).
    # Judging FP cards in a multiplier-bearing hand (REF_STREAK has on_fire) is what
    # produced the phantom ~42 floor — every small-FP card looked amplified.
    CLEAN_FP = {'FP', 'FPx'}
    # acc[ename] = {'cat', 'marg':[chosen marginal per context], 'fl':[]}
    acc = {e: {'cat': category(e), 'marg': [], 'fl': []} for e in byEffect}
    nctx = 0
    for ui, uid in enumerate(userIds):
        if freshCtx(uid) is None:
            continue
        nctx += 1
        baseVal = {name: handValue(uid, hand, args.runs) for name, hand in refs.items()}
        for ename in byEffect:
            cat = acc[ename]['cat']
            if cat in CLEAN_FP:
                v, fl = handValue(uid, refs['FP'] + [ename], args.runs)
                best = v - baseVal['FP'][0]
                bestFl = fl - baseVal['FP'][1]
            else:
                best, bestFl = None, 0.0
                for name, hand in refs.items():
                    v, fl = handValue(uid, hand + [ename], args.runs)
                    m = v - baseVal[name][0]
                    mfl = fl - baseVal[name][1]
                    if best is None or m > best:
                        best, bestFl = m, mfl
            acc[ename]['marg'].append(best)
            acc[ename]['fl'].append(bestFl)
        print(f"  user {ui+1}/{len(userIds)} done", flush=True)

    print(f"\nBuilt {nctx} contexts. Marginal value = best contribution across the 3 reference hands.\n")
    CATS = ['FP', 'FPx', 'Synergy/Amp', 'Floobit']
    for cat in CATS:
        rows = [(e, a) for e, a in acc.items() if a['cat'] == cat]
        if not rows:
            continue
        keyfn = (lambda x: statistics.mean(x[1]['fl']) if x[1]['fl'] else 0) if cat == 'Floobit' \
            else (lambda x: statistics.mean(x[1]['marg']) if x[1]['marg'] else 0)
        rows.sort(key=keyfn, reverse=True)
        print(f"━━ {cat}  ({BANDS[cat]}) " + "━" * 16)
        print(f"{'effect':22} {'edition':12} {'margVal':>8} {'margMax':>8} {'margF':>7}")
        for ename, a in rows:
            mv = statistics.mean(a['marg']) if a['marg'] else 0
            mx = max(a['marg']) if a['marg'] else 0
            mf = statistics.mean(a['fl']) if a['fl'] else 0
            ed = EFFECT_EDITION_TIER.get(ename) or getattr(byEffect[ename], 'edition', '?') or '?'
            print(f"{ename:22} {ed:12} {mv:8.1f} {mx:8.1f} {mf:7.1f}")
        print()
    print("margVal = avg marginal value added to a hand. margMax = best-case context. margF = marginal floobits.")
    session.close()


if __name__ == '__main__':
    main()
