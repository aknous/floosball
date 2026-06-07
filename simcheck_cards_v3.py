"""Card-balance sim-check v3 — substrate-aware valuation + arbitrary-hand sim.

v2 measured each card's marginal contribution to 3 fixed reference hands, which
left synergy/cross/amplifier cards and Floobit cards mis-read: the 4-card hands
didn't give them the substrate they act on (full_roster wants 5 positions,
gold_rush wants other Floobit cards, doubler wants TD cards, etc.). v3 fixes
that and adds the thing we actually want: evaluate ANY hand.

Two modes:

  1. SURVEY (default): every effect is valued inside a SUBSTRATE hand chosen to
     give it what it acts on — flat-FP producers for copycat/conductor/anthem,
     TD/yard/FG producers for doubler/surveyor/sharpshooter, chance cards for
     high_roller/charmed, streak cards for fortitude, FPx cards for stacked_deck,
     Floobit cards for gold_rush, all-5-positions for full_roster, same-position
     for all_in, mixed output types for diversified. The score is the card's
     marginal: handValue(substrate + card) - handValue(substrate). Banded by
     category + edition. This is a BEST-CASE (right substrate present) read.

  2. EVAL (--eval "a,b,c,d,e"): simulate one specific hand. Reports the hand's
     total value and each card's LEAVE-ONE-OUT marginal (hand value minus the
     value of the hand without that card) — the honest "what is this card worth
     in THIS hand" number, synergies included. Force a card's position with
     "effect:POS" (POS 1-5 = QB/RB/WR/TE/K), e.g. --eval "full_roster:5,..."

All values at editionScale=1.0 (forward-looking). FPx is aggregated the way the
game does it (1 + sum(f-1)). Each handValue() gets a FRESH projection context —
streak/FPx multiplier state bleeds through a reused ctx (the v2 bug).

  .venv/bin/python simcheck_cards_v3.py
  .venv/bin/python simcheck_cards_v3.py --eval "touchdown_pinata,three_pointer,on_fire,fortitude"
  .venv/bin/python simcheck_cards_v3.py --eval "full_roster:5,freebie:1,scrappy:2,on_fire:3,piggy_bank:4" --users 4
"""
import argparse
import asyncio
import os
import shutil
import statistics
import sys
import tempfile

from simcheck_cards import boot, preloadSeason, applyWeekState

# ── Substrate building blocks (effect lists; positions forced where it matters)
SUB_FP = ['touchdown_pinata', 'three_pointer', 'expedition', 'freebie']  # TD/FG/yard/flat
SUB_CHANCE = ['scrappy', 'martyr', 'underdog', 'traverse']
SUB_STREAK = ['on_fire', 'snowball_fight', 'drought', 'quiet_storm']
SUB_FPX = ['cornerstone', 'eminence', 'vanguard', 'big_deal']
SUB_FLOOBIT = ['piggy_bank', 'cha_ching', 'industrious', 'air_raid']
SUB_DIVERSE = ['touchdown_pinata', 'eminence', 'piggy_bank']  # fp + mult + floobits
REP_STREAK_COUNT = 3  # representative mid-streak for streak cards in a hand

# effect -> (substrate effect list, position scheme). Position scheme:
#   None         = use each card's natural position
#   'distinct'   = force substrate to positions 1..N and the TEST card to N+1
#   'same'       = force substrate AND test card all to position 1
SUBSTRATE = {
    # act on flat-FP cards in the hand
    'copycat': (SUB_FP, None), 'conductor': (SUB_FP, None), 'anthem': (SUB_FP, None),
    'double_down': (SUB_FP, None), 'last_resort': (SUB_FP, None), 'spectacle': (SUB_FP, None),
    'chain_reaction': (SUB_FP, None), 'bonus_round': (SUB_FP, None),
    # act on the roster TD/yard/FG counts that other cards scale on
    'doubler': (SUB_FP, None), 'surveyor': (SUB_FP, None), 'sharpshooter': (SUB_FP, None),
    # act on a specific card type in the hand
    'fortitude': (SUB_STREAK, None),
    'high_roller': (SUB_CHANCE, None), 'charmed': (SUB_CHANCE, None),
    'stacked_deck': (SUB_FPX, None),
    'gold_rush': (SUB_FLOOBIT, None), 'indemnity': (SUB_FLOOBIT, None),
    'diversified': (SUB_DIVERSE, None),
    # position mechanics
    'full_roster': (SUB_FP, 'distinct'),
    'all_in': (SUB_FP, 'same'),
}
DEFAULT_SUB = (SUB_FP, None)  # FP/FPx/Floobit standalone cards: read against a plain FP hand

BANDS = {'FP': '~35 base / 50 holo / 70 prismatic', 'FPx': 'judged on its own',
         'Floobit': 'separate currency (margF)', 'Synergy/Amp': 'best-case marginal w/ substrate'}


def parseArgs():
    p = argparse.ArgumentParser()
    p.add_argument('--db', default='data/floosball_prod_latest.db')
    p.add_argument('--season', type=int, default=None)
    p.add_argument('--users', type=int, default=6)
    p.add_argument('--week', type=int, default=14, help='representative week to sample')
    p.add_argument('--eval', default=None,
                   help='comma-separated hand, e.g. "td_pinata,on_fire,fortitude"; '
                        'force position with "effect:POS" (1-5)')
    return p.parse_args()


def main():
    args = parseArgs()
    if not os.path.exists(args.db):
        print(f"DB not found: {args.db}"); sys.exit(1)
    tmp = tempfile.mkdtemp(prefix='floos_simcheck3_')
    shutil.copy(args.db, os.path.join(tmp, 'floosball.db'))
    os.environ['DATABASE_DIR'] = tmp
    print(f"Working copy: {tmp}/floosball.db  (source {args.db}, untouched)")

    container, app = asyncio.run(boot())

    from database.connection import get_session
    from database.models import CardTemplate, FantasyRoster
    from sqlalchemy import func
    from managers.cardProjection import (
        buildProjectionContext, _wrapTemplateAsUserCard, _wrapUserCardAsEquipped,
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

    def equip(ename, posOverride=None):
        import copy
        ft = copy.copy(byEffect[ename])           # don't mutate the shared template
        ft.effect_config = dict(byEffect[ename].effect_config)
        if posOverride is not None:
            ft.position = posOverride
        return _wrapUserCardAsEquipped(_wrapTemplateAsUserCard(ft))

    def setStreaks(ctx, eqs, enames):
        ctx.streakCounts = {}
        for eq, en in zip(eqs, enames):
            cfg = STREAK_CONFIGS.get(en)
            if cfg and not cfg.get('isWeekly', False):
                ctx.streakCounts[eq.id] = REP_STREAK_COUNT

    def freshCtx(uid):
        c = buildProjectionContext(session, uid, season, args.week, sm, pm)
        if c is None:
            return None
        applyWeekState(c, c.userFavoriteTeamId, args.week, teamGames, byWeek, eloByTeam)
        return c

    def handValue(uid, cards):
        """cards: list of either 'ename' or (ename, posOverride). Returns
        (FP-equiv value, floobits) for a FRESH ctx (no cross-call bleed)."""
        ctx = freshCtx(uid)
        if ctx is None:
            return 0.0, 0.0
        enames = [c[0] if isinstance(c, tuple) else c for c in cards]
        eqs = [equip(*(c if isinstance(c, tuple) else (c,))) for c in cards]
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

    # ── EVAL MODE ───────────────────────────────────────────────────────────
    if args.eval:
        cards = []
        for tok in args.eval.split(','):
            tok = tok.strip()
            if not tok:
                continue
            if ':' in tok:
                e, p = tok.split(':', 1)
                cards.append((e.strip(), int(p)))
            else:
                cards.append(tok)
        enames = [c[0] if isinstance(c, tuple) else c for c in cards]
        bad = [e for e in enames if e not in byEffect]
        if bad:
            print(f"Unknown effect(s): {', '.join(bad)}"); sys.exit(1)
        def label(c):
            return f"{c[0]}@pos{c[1]}" if isinstance(c, tuple) else c
        print(f"\nEVAL hand ({len(cards)} cards): " + ', '.join(label(c) for c in cards))
        print(f"Season {season} · week {args.week} · averaged over {len(userIds)} user contexts\n")
        fullV, fullF, looV, looF = [], [], {e: [] for e in enames}, {e: [] for e in enames}
        for uid in userIds:
            v, f = handValue(uid, cards)
            fullV.append(v); fullF.append(f)
            for i, e in enumerate(enames):
                wv, wf = handValue(uid, cards[:i] + cards[i + 1:])
                looV[e].append(v - wv); looF[e].append(f - wf)

        def mean(x):
            return statistics.mean(x) if x else 0.0
        print(f"{'card':22} {'edition':12} {'leave-1-out':>11} {'floobits':>9}")
        for e in enames:
            ed = EFFECT_EDITION_TIER.get(e, '?')
            print(f"{e:22} {ed:12} {mean(looV[e]):11.1f} {mean(looF[e]):9.1f}")
        print(f"\n{'HAND TOTAL':22} {'':12} {mean(fullV):11.1f} {mean(fullF):9.1f}")
        print("leave-1-out = hand value minus the value of the hand without that card "
              "(its real worth IN this hand). floobits column = its floobit share.")
        session.close()
        return

    # ── SURVEY MODE ─────────────────────────────────────────────────────────
    if skippedLegacy:
        print(f"Skipped {len(skippedLegacy)} legacy effect(s) (no handler).")
    print(f"Season {season} · week {args.week} · {len(byEffect)} effects · {len(userIds)} users "
          f"· substrate-aware marginal\n")

    def measure(uid, ename):
        """Marginal of ename inside its chosen substrate hand. Returns (fpVal, floobits)."""
        subEffects, scheme = SUBSTRATE.get(ename, DEFAULT_SUB)
        subEffects = [s for s in subEffects if s != ename]
        if scheme == 'distinct':
            sub = [(s, i + 1) for i, s in enumerate(subEffects[:4])]
            card = (ename, len(sub) + 1)
        elif scheme == 'same':
            sub = [(s, 1) for s in subEffects[:4]]
            card = (ename, 1)
        else:
            sub = list(subEffects)
            card = ename
        baseV, baseF = handValue(uid, sub)
        fullV, fullF = handValue(uid, sub + [card])
        return fullV - baseV, fullF - baseF

    acc = {e: {'cat': category(e), 'v': [], 'f': []} for e in byEffect}
    nctx = 0
    for ui, uid in enumerate(userIds):
        if freshCtx(uid) is None:
            continue
        nctx += 1
        for ename in byEffect:
            v, f = measure(uid, ename)
            acc[ename]['v'].append(v)
            acc[ename]['f'].append(f)
        print(f"  user {ui + 1}/{len(userIds)} done", flush=True)

    print(f"\nBuilt {nctx} contexts. Each card valued inside a substrate hand that gives it "
          f"what it acts on.\n")
    CATS = ['FP', 'FPx', 'Synergy/Amp', 'Floobit']
    for cat in CATS:
        rows = [(e, a) for e, a in acc.items() if a['cat'] == cat]
        if not rows:
            continue
        keyfn = (lambda x: statistics.mean(x[1]['f']) if x[1]['f'] else 0) if cat == 'Floobit' \
            else (lambda x: statistics.mean(x[1]['v']) if x[1]['v'] else 0)
        rows.sort(key=keyfn, reverse=True)
        print(f"━━ {cat}  ({BANDS[cat]}) " + "━" * 16)
        print(f"{'effect':22} {'edition':12} {'val':>8} {'max':>8} {'floob':>7}  substrate")
        for ename, a in rows:
            mv = statistics.mean(a['v']) if a['v'] else 0
            mx = max(a['v']) if a['v'] else 0
            mf = statistics.mean(a['f']) if a['f'] else 0
            ed = EFFECT_EDITION_TIER.get(ename) or getattr(byEffect[ename], 'edition', '?') or '?'
            subName = {id(SUB_FP): 'fp', id(SUB_CHANCE): 'chance', id(SUB_STREAK): 'streak',
                       id(SUB_FPX): 'fpx', id(SUB_FLOOBIT): 'floobit',
                       id(SUB_DIVERSE): 'diverse'}.get(id(SUBSTRATE.get(ename, DEFAULT_SUB)[0]), 'fp')
            sch = SUBSTRATE.get(ename, DEFAULT_SUB)[1]
            tag = subName + (f"/{sch}" if sch else '')
            print(f"{ename:22} {ed:12} {mv:8.1f} {mx:8.1f} {mf:7.1f}  {tag}")
        print()
    print("val = avg marginal added to its substrate hand. max = best context. floob = marginal floobits.")
    print("FP/FPx/Floobit standalone cards use a plain FP substrate; synergy cards use a tailored one.")
    session.close()


if __name__ == '__main__':
    main()
