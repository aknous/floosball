"""What does a trade actually LOOK like? — the shape of the market, not its size.

Two questions this exists to answer, both of which theory gets wrong:

  1. ⚠️ HOW OFTEN DOES A BUYER HAVE TO CUT SOMEONE? With six position-locked slots and no
     bench, every roster is complete by construction, so the answer may be "always" — in
     which case a trade is not "player for picks", it is "player for picks AND the buyer
     discards a man into the pool". That is a churn engine, not a market, and it would be
     a design consequence nobody chose.

  2. ⚠️ WHEN DO TRADES HAPPEN, AND ON WHICH TRIGGER? The intent is that clubs wait for
     clarity on their postseason position. If they fire in week 1 instead, the question is
     WHICH trigger is firing — the contention-gated one cannot, so an early market is
     evidence about the other three.

Reports both, plus what happens to the cut player and what the fee actually costs.

  .venv/bin/python trade_shape_check.py --seasons 2 --treasury 1900
"""
import argparse
import asyncio
import logging
import os
import shutil
import sys
import tempfile
from collections import Counter

tmp = tempfile.mkdtemp(prefix='floos_shape_')
os.environ['DATABASE_DIR'] = tmp
os.environ.setdefault('TIMING_MODE', 'fast')
logging.disable(logging.INFO)
_TM_LOG = logging.getLogger('managers.tradeManager')


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
    await app.initializeLeague(config, force_fresh=True)
    return container, app


async def main(seasons, treasury):
    import constants
    from managers import tradeManager
    enabled = os.environ.get('SHAPE_ARM', 'on') == 'on'
    constants.TRADING_ENABLED = enabled
    tradeManager.TRADING_ENABLED = enabled

    logging.disable(logging.NOTSET)
    logging.getLogger().setLevel(logging.ERROR)
    _TM_LOG.setLevel(logging.WARNING)
    _h = logging.StreamHandler(sys.stdout)
    _h.setFormatter(logging.Formatter('    !! %(message)s'))
    _h.addFilter(lambda r: 'TRADE PIECE MISSING' in r.getMessage())
    _TM_LOG.addHandler(_h)

    container, app = await boot()
    sm, pm = app.seasonManager, app.playerManager
    tm = container.getService('team_manager')

    if treasury:
        from managers.facilitiesManager import setTreasury
        from database.connection import get_session as _gs
        s = _gs()
        try:
            for t in tm.teams:
                setTreasury(s, t.id, treasury)
            s.commit()
        finally:
            s.close()

    shape = {'trades': 0, 'neededCut': 0, 'hadEmptySlot': 0, 'feePaid': 0,
             'feeTotal': 0, 'byWeek': Counter(), 'byTrigger': Counter(),
             'cutRatings': [], 'inRatings': [], 'backfillKind': Counter()}

    # Wrap the two functions that KNOW the answer, rather than inferring it afterwards.
    realListings = tradeManager.TradeMarket.listingsFor
    realBid = tradeManager.TradeMarket.bidFor

    def spyListings(self, team):
        out = realListings(self, team)
        for l in out:
            shape.setdefault('listedBy', Counter())[l.trigger] += 1
        return out

    def spyBid(self, listing, buyer):
        """⚠️ IS VOLUME LIMITED BY ASSETS, OR BY APPETITE? Those need opposite answers —
        one is a supply problem to fix, the other is the market correctly declining. The
        counters live on the market instance and accumulate, so this takes the DELTA per
        call rather than the running total."""
        before = dict(getattr(self, 'assembleFail', {}))
        out = realBid(self, listing, buyer)
        after = getattr(self, 'assembleFail', {})
        why = shape.setdefault('why', Counter())
        for k, v in after.items():
            why[k] += v - before.get(k, 0)
        if out is not None:
            shape.setdefault('bidBy', Counter())[listing.trigger] += 1
        return out

    realInq = tradeManager.TradeMarket.inquiriesFor

    def spyInquiries(self, buyer):
        """⚠️ WHY DID NOBODY CALL? "0 blockbusters" has three different causes and they
        want opposite fixes: no club was close enough to the cut, the club had no gap worth
        filling, or nobody in the league was enough of an upgrade to be worth the phone
        call. The counter lives on the market instance, so take the DELTA."""
        before = dict(getattr(self, 'inquiryFail', {}))
        out = realInq(self, buyer)
        after = getattr(self, 'inquiryFail', {})
        why = shape.setdefault('inqWhy', Counter())
        for k, v in after.items():
            why[k] += v - before.get(k, 0)
        return out

    tradeManager.TradeMarket.listingsFor = spyListings
    tradeManager.TradeMarket.bidFor = spyBid
    tradeManager.TradeMarket.inquiriesFor = spyInquiries

    realCut = tradeManager._cutToMakeRoom
    realOpen = tradeManager._openSlotFor
    realBackfill = tradeManager._findBackfill
    realSettle = tradeManager.settleTrade

    def spyOpen(team, player):
        return realOpen(team, player)

    pending = {}

    def spyCut(seasonManager, buyer, incoming):
        from managers.frontOfficeBrain import cutFeeFor
        posValue = getattr(getattr(incoming, 'position', None), 'value', None)
        held = [buyer.rosterDict.get(sl)
                for sl in tradeManager.POSITION_SLOTS.get(posValue, [])]
        held = [h for h in held if h is not None]
        worst = min(held, key=lambda h: h.playerRating) if held else None
        out = realCut(seasonManager, buyer, incoming)
        if out is not None and worst is not None:
            pending['cut'] = {'name': worst.name,
                              'position': getattr(worst.position, 'name', None),
                              'rating': round(worst.playerRating, 1),
                              'term': int(getattr(worst, 'termRemaining', 0) or 0),
                              'fee': cutFeeFor(worst)}
            shape['neededCut'] += 1
            # ⚠️ A RATING DELTA IS THE WRONG LENS ON ITS OWN. A club can take a player of
            # similar rating and gain three years of control, which is the plan's TIME
            # trade and a good deal — measured on ratings alone it reads as churn.
            shape.setdefault('termIn', []).append(
                int(getattr(incoming, 'termRemaining', 0) or 0))
            shape.setdefault('termOut', []).append(
                int(getattr(worst, 'termRemaining', 0) or 0))
            fee = cutFeeFor(worst)
            shape['feeTotal'] += fee
            shape['feePaid'] += 1 if fee > 0 else 0
            shape['cutRatings'].append(round(worst.playerRating, 1))
            shape['inRatings'].append(round(incoming.playerRating, 1))
        return out

    def spyBackfill(*a, **kw):
        """⚠️ FORWARD EVERYTHING. A fixed 3-arg wrapper silently broke the moment
        `_findBackfill` grew a `week=` parameter: every in-season settle raised TypeError
        into `_runTradePass`'s best-effort except, trades fell from ~10 a season to 2, and
        the run LOOKED like a clean measurement of a regression that did not exist."""
        out = realBackfill(*a, **kw)
        if out is not None:
            shape['backfillKind'][out[0]] += 1
            kind, person = out
            pending['backfill'] = {
                'kind': kind, 'name': getattr(person, 'name', '?'),
                'position': getattr(getattr(person, 'position', None), 'name', None),
                'rating': round(getattr(person, 'playerRating', 0) or 0, 1),
                'prospectSeasons': getattr(person, 'prospect_seasons', None)}
        return out

    def scanMismatch(label):
        bad = []
        for t in tm.teams:
            for slot, p in (t.rosterDict or {}).items():
                if p is None:
                    continue
                owner = getattr(p, 'team', None)
                ownerName = getattr(owner, 'name', owner)
                if ownerName != t.name:
                    bad.append(f"{p.name} in {t.name}.{slot} but team={ownerName!r}")
                if p in pm.freeAgents:
                    bad.append(f"{p.name} is BOTH in {t.name}.{slot} and the FA pool")
        if bad:
            print(f"  !! mismatch after {label}: {bad[:3]}")
        return bad

    def assetDetail(market, piece, seller, buyer):
        """⚠️ BOTH SIDES' VALUATIONS OF THE SAME PIECE, which is the only interesting
        number in a trade and the one nothing persists. They differ because the two clubs
        discount the future differently — that difference IS the trade."""
        def valueFor(team):
            for a in market._tradeableAssets(buyer, valuingTeam=team,
                                             swapPosition=swapPos):
                if a['kind'] == piece['kind'] and a['id'] == piece['id']:
                    return round(a['value'], 1)
            return None
        swapPos = None
        return {'toSeller': valueFor(seller), 'toBuyer': valueFor(buyer)}

    def spySettle(seasonManager, listing, winner, season, week=None):
        before = tradeManager._openSlotFor(winner.team, listing.player) is not None
        preexisting = set(scanMismatch('BEFORE'))
        from managers.tradeManager import TradeMarket
        brain = sm._foBrainForOffseason()
        brain.season, brain.week = season, week or 22
        mkt = TradeMarket(pm, tm, brain, season, week)
        seller, buyer = listing.team, winner.team
        swapPos = getattr(getattr(listing.player, 'position', None), 'value', None)
        sellerVals = {(a['kind'], a['id']): round(a['value'], 1)
                      for a in mkt._tradeableAssets(buyer, valuingTeam=seller,
                                                    swapPosition=swapPos)}
        buyerVals = {(a['kind'], a['id']): round(a['value'], 1)
                     for a in mkt._tradeableAssets(buyer, valuingTeam=buyer,
                                                   swapPosition=swapPos)}

        def describe(obj):
            return {
                'name': getattr(obj, 'name', '?'),
                'position': getattr(getattr(obj, 'position', None), 'name', None),
                'rating': round(getattr(obj, 'playerRating', 0) or 0, 1),
                'term': int(getattr(obj, 'termRemaining', 0) or 0),
                'ceiling': (obj.computeCeilingRating()
                            if hasattr(obj, 'computeCeilingRating') else None),
                'prospectSeasons': getattr(obj, 'prospect_seasons', None),
            }

        record = {
            'season': season, 'week': week,
            'trigger': listing.trigger,
            'ask': round(listing.ask, 1), 'floor': round(listing.floor, 1),
            'bid': round(winner.value, 1),
            'seller': {'name': seller.name,
                       'nowWeight': round(mkt.nowWeight(seller), 2),
                       'record': dict(getattr(seller, 'seasonTeamStats', {}) or {})},
            'buyer': {'name': buyer.name,
                      'nowWeight': round(mkt.nowWeight(buyer), 2),
                      'record': dict(getattr(buyer, 'seasonTeamStats', {}) or {})},
            'out': [dict(describe(listing.player), kind='player')],
            'back': [],
        }
        for piece in winner.pieces:
            key = (piece['kind'], piece['id'])
            entry = {'kind': piece['kind'], 'name': piece['name'],
                     'toSeller': sellerVals.get(key), 'toBuyer': buyerVals.get(key)}
            if piece['kind'] == 'pick':
                d = piece.get('detail') or {}
                out_ = (d.get('season') or season) - season
                # ⚠️ THE EXPECTED slot, which is what it was actually VALUED on. The raw
                # standings slot is what a future pick is NOT worth being priced at — a
                # contender's own late pick regresses toward the middle because nobody
                # knows where that club finishes two seasons out.
                import trading as _t
                entry.update({'pickSeason': d.get('season'), 'slot': d.get('slot'),
                              'originalTeam': next(
                                  (t.name for t in tm.teams
                                   if getattr(t, 'id', None) == d.get('originalTeamId')),
                                  None),
                              'expectedSlot': round(_t.expectedPickSlot(
                                  d.get('slot') or 16, out_), 1),
                              'seasonsOut': out_})
            else:
                obj = (tradeManager._findRostered(buyer, piece['id'])
                       or tradeManager._findProspect(buyer, piece['id']))
                if obj is not None:
                    entry.update(describe(obj))
            record['back'].append(entry)

        pending.clear()
        out = realSettle(seasonManager, listing, winner, season, week)
        if out is not None:
            # ⚠️ ONLY WHAT THIS SETTLEMENT DID. `pending` is cleared immediately before the
            # call, so a cut or a promotion from an earlier trade in the same weekly pass
            # cannot be attributed to this one.
            record['buyerCut'] = pending.get('cut')
            record['sellerBackfill'] = pending.get('backfill')
            shape.setdefault('ledger', []).append(record)
        fresh = [m for m in scanMismatch('settle') if m not in preexisting]
        if fresh:
            print(f"     ^ caused by: {listing.team.name} sent {listing.player.name} "
                  f"({listing.player.position.name}) to {winner.team.name}, "
                  f"trigger={listing.trigger}, week={week}")
        if out is not None:
            shape['trades'] += 1
            shape['byWeek'][week if week is not None else 'offseason'] += 1
            shape['byTrigger'][listing.trigger] += 1
            if before:
                shape['hadEmptySlot'] += 1
        return out

    tradeManager._cutToMakeRoom = spyCut
    tradeManager._findBackfill = spyBackfill
    tradeManager.settleTrade = spySettle
    # seasonManager imports the module, so patching the module attributes is enough.

    for season in range(1, seasons + 1):
        await sm.startNewSeason()
        both = [f"{p.name}@{t.name}.{slot}" for t in tm.teams
                for slot, p in (t.rosterDict or {}).items()
                if p is not None and p in pm.freeAgents]
        wrong = [f"{p.name}@{t.name}.{slot}->{getattr(getattr(p,'team',None),'name',getattr(p,'team',None))!r}"
                 for t in tm.teams for slot, p in (t.rosterDict or {}).items()
                 if p is not None and getattr(getattr(p, 'team', None), 'name',
                                              getattr(p, 'team', None)) != t.name]
        try:
            from managers.tradeManager import TradeMarket
            _b = sm._foBrainForOffseason()
            _b.season, _b.week = season, 20
            _mkt = TradeMarket(pm, tm, _b, season, 20)
            shape.setdefault('inventory', []).append(
                (sum(len(_mkt.picksOwnedBy(t)) for t in tm.teams),
                 sum(len(getattr(t, 'prospects', None) or []) for t in tm.teams)))
        except Exception as e:
            print('   inventory probe failed:', e)
        print(f"  [season {season} start, BEFORE any trade] "
              f"rostered-and-in-pool: {len(both)}, wrong-team-ref: {len(wrong)}")
        if both[:2]:
            print(f"      e.g. {both[:2]}")
        if wrong[:2]:
            print(f"      e.g. {wrong[:2]}")
        await sm.runSeasonSimulation()
        await sm.handleOffseason()
        sm.currentSeason.seasonNumber = season + 1

    n = shape['trades']
    print(f"\n  {n} trade(s) over {seasons} season(s)")
    if not n:
        print("  nothing to describe")
        return shape

    print(f"\n  ── did the buyer have to CUT someone? ──")
    print(f"    buyer already had an empty slot : {shape['hadEmptySlot']:>3} "
          f"({shape['hadEmptySlot'] / n:.0%})")
    print(f"    buyer had to cut to make room   : {shape['neededCut']:>3} "
          f"({shape['neededCut'] / n:.0%})")
    if shape['neededCut']:
        print(f"    of those, a FEE was actually due: {shape['feePaid']:>3} "
              f"({shape['feePaid'] / shape['neededCut']:.0%}) — "
              f"total {shape['feeTotal']}F, mean "
              f"{shape['feeTotal'] / shape['neededCut']:.0f}F")
        pairs = list(zip(shape['inRatings'], shape['cutRatings']))
        gaps = [a - b for a, b in pairs]
        tin, tout = shape.get('termIn', []), shape.get('termOut', [])
        if tin:
            dt = [a - b for a, b in zip(tin, tout)]
            print(f"    control gained: mean {sum(dt) / len(dt):+.2f} seasons "
                  f"(in {sum(tin) / len(tin):.1f}yr vs cut {sum(tout) / len(tout):.1f}yr)")
        print(f"    upgrade taken: mean {sum(gaps) / len(gaps):+.1f} rating points "
              f"(in {sum(shape['inRatings']) / len(pairs):.0f} vs "
              f"cut {sum(shape['cutRatings']) / len(pairs):.0f})")

    print(f"\n  ── when, and on what trigger? ──")
    weeks = sorted(w for w in shape['byWeek'] if isinstance(w, int))
    if weeks:
        early = sum(shape['byWeek'][w] for w in weeks if w <= 7)
        mid = sum(shape['byWeek'][w] for w in weeks if 8 <= w <= 14)
        late = sum(shape['byWeek'][w] for w in weeks if w >= 15)
        print(f"    weeks 1-7 {early}  |  8-14 {mid}  |  15-21 {late}"
              f"  |  offseason {shape['byWeek'].get('offseason', 0)}")
        detail = ', '.join(f"w{w}x{shape['byWeek'][w]}" for w in weeks)
        print(f"    detail: {detail}")
    inq = shape.get('inqWhy') or Counter()
    if inq:
        print("\n  \u2500\u2500 the blockbuster: who picked up the phone? \u2500\u2500")
        labels = {'called': 'made the call',
                  'not_close_enough': 'not close enough to the cut',
                  'nobody_enough_better': 'no upgrade worth calling about',
                  'unpriceable': 'holder would not put a price on him'}
        for k in ('called', 'not_close_enough', 'nobody_enough_better', 'unpriceable'):
            if inq.get(k):
                print(f"    {labels[k]:<38} {inq[k]:>4}")

    for trigger, count in shape['byTrigger'].most_common():
        print(f"    {trigger:<20} {count:>3} ({count / n:.0%})")

    inv = shape.get('inventory', [])
    why = shape.get('why', Counter())
    if inv:
        print(f"\n  ── is volume limited by ASSETS or by APPETITE? ──")
        print(f"    league inventory, mean per pass: {sum(p for p,_ in inv)/len(inv):.0f} "
              f"tradeable picks, {sum(x for _,x in inv)/len(inv):.0f} prospects "
              f"across {len(tm.teams)} clubs")
        total = sum(why.values()) or 1
        for k, label in (('built', 'bundle built (a real bid)'),
                         ('barNotCleared', "could not reach the seller's price"),
                         ('noAssets', '  ...of those, held NOTHING to offer'),
                         ('tooExpensive', 'buyer refused: cost exceeded the gain')):
            print(f"    {label:<42} {why.get(k,0):>6}  {why.get(k,0)/total:>5.0%}")

    print(f"\n  ── the funnel, by trigger ──")
    listed = shape.get('listedBy', Counter())
    bid = shape.get('bidBy', Counter())
    for trigger in sorted(set(listed) | set(bid) | set(shape['byTrigger'])):
        print(f"    {trigger:<20} listed {listed.get(trigger, 0):>4}  "
              f"clearing bids {bid.get(trigger, 0):>4}  "
              f"settled {shape['byTrigger'].get(trigger, 0):>3}")

    # ⚠️ THE FULL LEDGER, read back from the persisted `trades` rows rather than from
    # anything the harness held in memory — so what is printed is what a fan would be
    # shown on the transactions page, not what the market thought it was doing.
    from database.connection import get_session as _gs
    from database.models import Trade
    names = {t.id: t.name for t in tm.teams}
    session = _gs()
    try:
        # ⚠️ `week` IS 0 FOR AN OFFSEASON TRADE, so a naive sort puts the offseason
        # BEFORE the season it follows — which makes a perfectly consistent chain of
        # custody read as a player being traded by a club that never had him. Sort the
        # offseason last within its season.
        rows = sorted(session.query(Trade).all(),
                      key=lambda r: (r.season, r.week or 99, r.id))
        print(f"\n  ── every trade ──")
        kinds = Counter()
        for r in rows:
            a = (r.assets_json or {}).get('aGave', [])
            b = (r.assets_json or {}).get('bGave', [])
            for piece in b:
                kinds[piece.get('kind')] += 1
            for piece in a:
                kinds[piece.get('kind')] += 1
            when = f"S{r.season} " + (f"w{r.week}" if r.week else "offseason")
            def label(pieces):
                return ', '.join(f"{p['name']}#{p.get('id')}[{p['kind'][:4]}]"
                                 for p in pieces) or 'nothing'
            print(f"    {when:<14} {names.get(r.team_a_id, '?'):<12} "
                  f"send {label(a):<30} to {names.get(r.team_b_id, '?'):<12} "
                  f"for {label(b)}")
        print(f"\n    assets by kind: {dict(kinds)}")
        withPieces = sum(1 for r in rows if (r.assets_json or {}).get('bGave'))
        print(f"    trades where the buyer gave something back: {withPieces}/{len(rows)}")
    finally:
        session.close()

    # ⚠️ DUPLICATE LIVE NAMES ARE A DOCUMENTED INCIDENT CLASS HERE — "at most one form of
    # a lineage is in circulation at a time". The cull returns a culled player's name to
    # the pool with NO reuse hold, so if it ever returned a name whose holder is still
    # alive, two live players would wear it.
    live = {}
    for p in pm.activePlayers:
        live.setdefault(p.name, []).append(getattr(p, 'id', None))
    dupes = {n: ids for n, ids in live.items() if len(ids) > 1}
    print(f"\n  ── duplicate live names: {len(dupes)} ──")
    for n, ids in list(dupes.items())[:5]:
        print(f"    {n}: ids {ids}")

    holes = [(t.name, sl) for t in tm.teams
             for sl, p in (t.rosterDict or {}).items() if p is None]
    onTwo = []
    for t in tm.teams:
        for sl, p in (t.rosterDict or {}).items():
            if p is None:
                continue
            owner = getattr(getattr(p, 'team', None), 'name', getattr(p, 'team', None))
            if owner != t.name:
                onTwo.append(f"{p.name}@{t.name}.{sl}->{owner!r}")
    print(f"\n  ── roster integrity: {len(holes)} hole(s), {len(onTwo)} wrong-team ref(s) ──")
    if holes[:3]:
        print(f"    {holes[:3]}")
    if onTwo[:3]:
        print(f"    {onTwo[:3]}")

    import json
    with open('/tmp/trade_ledger.json', 'w') as fh:
        json.dump(shape.get('ledger', []), fh, indent=1)
    print(f"\n  wrote {len(shape.get('ledger', []))} detailed trade records to "
          f"/tmp/trade_ledger.json")

    print(f"\n  ── who replaced the SOLD player? ──")
    for kind, count in shape['backfillKind'].most_common():
        print(f"    {kind:<20} {count:>3}")
    return shape


def _seedEverything(seed: int) -> None:
    """Make a run reproducible, so two arms are actually comparable.

    ⚠️ THIS HARNESS WAS NEVER SEEDED, AND EVERY COMPARISON MADE WITH IT CARRIED THE NOISE.
    Each run boots a fresh league with `force_fresh=True` and player generation goes
    through `np.random.normal`, so back-to-back runs of IDENTICAL code produced different
    leagues — measured, 61 trades over 8 seasons on one run and 23 on the next. Any
    before/after read from single unseeded runs is mostly sampling, and two of this
    project's test files had the same defect (see the numpy note in
    `test_darts_format._seedAll`).

    ⚠️ SEED BOTH GENERATORS. `random.seed` alone does not pin player generation, which is
    what decides the league you are measuring.

    ⚠️ AND IT STILL DOES NOT MAKE A RUN REPRODUCIBLE — measured, the same seed gave 9
    trades and then 5, and pinning `PYTHONHASHSEED=0` as well did not fix it either. Some
    ordering in the engine is keyed on object identity rather than on anything a seed
    reaches. So this removes ONE source of variance and no more: **a single run is a
    sample, not a measurement**, and an A/B needs several runs an arm. Every before/after
    in this session's notes taken from one run each carries that noise.
    """
    import random as _r
    _r.seed(seed)
    try:
        import numpy as _np
        _np.random.seed(seed)
    except Exception:
        pass


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--seasons', type=int, default=2)
    ap.add_argument('--treasury', type=int, default=1900)
    ap.add_argument('--seed', type=int, default=20260916,
                    help='fixed by default so arms are comparable; vary it to sample')
    args = ap.parse_args()
    _seedEverything(args.seed)
    try:
        asyncio.run(main(args.seasons, args.treasury))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    sys.exit(0)
