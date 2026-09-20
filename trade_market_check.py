"""Trade-market harness — is this a good market?

Regression tests cannot answer that. Modelled on `form_oscillation_check.py` and
`prospect_draft_check.py`: boots the real managers headless and runs the season with
trading ON, reporting the three numbers the plan says it exists to produce.

  * TRADE VOLUME        — ~32 listings against 16 buyers today, but the horizon trigger
                          is not countable from a snapshot
  * WHERE TRADES CLUSTER — ⚠️ the contention ramp should push them past week 12. Firing
                          in week 3 means the ramp is too fast
  * WHO BUYS AND WHO SELLS — by contention, which is the whole premise

⚠️ COMPARE ARMS WITHIN ONE LEAGUE. Two fresh leagues with provably identical gameplay
measured 2.8 points a game apart, so a cross-league A/B would report a difference trading
did not cause. This runs the SAME league with the flag on and off.

  .venv/bin/python trade_market_check.py --seasons 2
"""
import argparse
import asyncio
import logging
import os
import shutil
import sys
import tempfile

tmp = tempfile.mkdtemp(prefix='floos_trade_')
os.environ['DATABASE_DIR'] = tmp
os.environ.setdefault('TIMING_MODE', 'fast')
logging.disable(logging.INFO)


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


async def main(seasons, enabled, treasury=0):
    import constants
    from managers import tradeManager
    constants.TRADING_ENABLED = enabled

    container, app = await boot()
    sm, pm = app.seasonManager, app.playerManager
    tm = container.getService('team_manager')

    # ⚠️ A FRESH LEAGUE HAS NO TREASURY, AND THE CUT FEE IS SIZED FOR A MATURE ONE.
    # Measured on a fresh league: 44 of 44 accepted trades died because the buyer could
    # not pay a mean 661F fee against a mean balance of 150F — while production's MEDIAN
    # club holds 1,896F. That is the fee working as designed (a cost that constrains the
    # poor rather than a purchase that empowers the rich), not a defect, but it means a
    # fresh league cannot measure the MARKET at all — only the economy in front of it.
    # `--treasury` seeds a production-like balance so the two can be measured separately.
    if treasury:
        from managers.facilitiesManager import setTreasury
        from database.connection import get_session as _gs
        _s = _gs()
        try:
            for t in tm.teams:
                setTreasury(_s, t.id, treasury)
            _s.commit()
        finally:
            _s.close()
    from database.connection import get_session
    from database.models import Trade

    # ⚠️ INSTRUMENTED, BECAUSE "0 trades" IS INDISTINGUISHABLE BETWEEN a quiet market, a
    # gate that never opens, triggers that never fire, and bids that never clear — and
    # those need four different responses.
    tally = {'weeks': 0, 'banked': 0, 'listings': 0, 'bids': 0, 'settled': 0,
             'accepted': 0, 'noBackfill': 0, 'mustCut': 0, 'cannotAffordTheCut': 0,
             'feeTotal': 0, 'balanceTotal': 0}
    tally['byTrigger'] = {}
    realPass = sm._runTradePass
    realBanked = sm._weekIsBanked

    def probePass(week):
        tally['weeks'] += 1
        banked = realBanked(week)
        tally['banked'] += 1 if banked else 0
        out = realPass(week)
        tally['settled'] += len(out)
        return out

    def probeSettle(week):
        """WHERE the funnel narrows. ⚠️ "0 trades" is indistinguishable between a quiet
        market, a gate that never opens, triggers that never fire, bids that never clear
        and a buyer that cannot pay — and those need five different responses. Every one
        of them was the answer at some point while this was being built."""
        from managers.tradeManager import runWeeklyPass
        import managers.tradeManager as TMod
        from managers.frontOfficeBrain import cutFeeFor
        from managers.facilitiesManager import getTreasury
        from database.connection import get_session as _gs
        brain = sm._foBrainForOffseason()
        brain.season, brain.week = sm.currentSeason.seasonNumber, week
        for entry in runWeeklyPass(pm, tm, brain, sm.currentSeason.seasonNumber, week):
            listing, winner = entry['listing'], entry['winner']
            tally['accepted'] += 1
            if TMod._findBackfill(sm, listing.team, listing.player) is None:
                tally['noBackfill'] += 1
                continue
            if TMod._openSlotFor(winner.team, listing.player) is not None:
                continue                    # the buyer had room
            posV = listing.player.position.value
            held = [winner.team.rosterDict.get(sl)
                    for sl in TMod.POSITION_SLOTS.get(posV, [])]
            held = [h for h in held if h is not None]
            if not held:
                continue
            fee = cutFeeFor(min(held, key=lambda h: h.playerRating))
            session = _gs()
            try:
                balance = getTreasury(session, winner.team.id)
            finally:
                session.close()
            tally['feeTotal'] += fee
            tally['balanceTotal'] += balance
            tally['mustCut'] += 1
            if fee > balance:
                tally['cannotAffordTheCut'] += 1

    tally['byTrigger'] = {}
    realPass = sm._runTradePass
    realBanked = sm._weekIsBanked

    def instrumented(week):
        tally['weeks'] += 1
        tally['banked'] += 1 if realBanked(week) else 0
        # Count what the market OFFERS before settlement consumes it — the two numbers
        # only mean something next to each other.
        try:
            from managers.tradeManager import TradeMarket
            brain = sm._foBrainForOffseason()
            brain.season, brain.week = sm.currentSeason.seasonNumber, week
            market = TradeMarket(pm, tm, brain, sm.currentSeason.seasonNumber, week)
            for team in tm.teams:
                window = market.teamWindow(team)
                for listing in market.listingsFor(team):
                    tally['listings'] += 1
                    # ⚠️ BY TRIGGER AND BY WINDOW, because "32 listings" says nothing about
                    # whether the market is doing what each trigger was written for. The
                    # horizon trigger fires on "contending + 3 years" alone, so this is
                    # what shows whether it is a fading contender cashing in or a champion
                    # selling a player it has every reason to keep.
                    key = f"{listing.trigger}/{window}"
                    tally['byTrigger'][key] = tally['byTrigger'].get(key, 0) + 1
                    for buyer in market.counterpartiesFor(listing):
                        if market.bidFor(listing, buyer) is not None:
                            tally['bids'] += 1
            probeSettle(week)
        except Exception as e:
            print('   probe failed:', e)
        out = realPass(week)
        tally['settled'] += len(out)
        return out

    sm._runTradePass = instrumented

    label = 'ON ' if enabled else 'OFF'
    for season in range(1, seasons + 1):
        await sm.startNewSeason()
        await sm.runSeasonSimulation()
        await sm.handleOffseason()
        sm.currentSeason.seasonNumber = season + 1

    session = get_session()
    try:
        trades = session.query(Trade).all()
        byWeek = {}
        for t in trades:
            byWeek[t.week] = byWeek.get(t.week, 0) + 1
        print(f"\n  trading {label} — {len(trades)} trade(s) over {seasons} season(s)")
        print(f"    passes {tally['weeks']}, banked {tally['banked']}, "
              f"listings {tally['listings']}, clearing bids {tally['bids']}, "
              f"settled {tally['settled']}")
        if tally['accepted']:
            print(f"    funnel: {tally['listings']} listings -> {tally['bids']} clearing "
                  f"bids -> {tally['accepted']} accepted -> {tally['settled']} settled")
            if tally['noBackfill']:
                print(f"    dropped, seller could not backfill: {tally['noBackfill']}")
            if tally['mustCut']:
                meanFee = tally['feeTotal'] / tally['mustCut']
                meanBal = tally['balanceTotal'] / tally['mustCut']
                print(f"    buyer had to cut in {tally['mustCut']} case(s); "
                      f"mean fee {meanFee:.0f}F against mean Treasury {meanBal:.0f}F; "
                      f"{tally['cannotAffordTheCut']} could not pay")
        if tally['byTrigger']:
            print('    listings by trigger/window: ' + ', '.join(
                f'{k} x{v}' for k, v in sorted(tally['byTrigger'].items(), key=lambda kv: -kv[1])))
        if trades:
            byTrigger = {}
            for t in trades:
                byTrigger[t.trigger] = byTrigger.get(t.trigger, 0) + 1
            print('    trades by trigger:   ' + ', '.join(
                f'{k} x{v}' for k, v in sorted(byTrigger.items(), key=lambda kv: -kv[1])))
            weeks = sorted(byWeek)
            print(f"    weeks:   {', '.join(f'w{w}x{byWeek[w]}' for w in weeks)}")
            early = sum(n for w, n in byWeek.items() if w < 12)
            print(f"    before week 12: {early}/{len(trades)} "
                  f"({'⚠️ the ramp is too fast' if early > len(trades) * 0.4 else 'ok'})")
            prices = sorted(t.price for t in trades)
            print(f"    price: min {prices[0]:.1f} median "
                  f"{prices[len(prices) // 2]:.1f} max {prices[-1]:.1f}")
            sellers = {}
            for t in trades:
                sellers[t.team_a_id] = sellers.get(t.team_a_id, 0) + 1
            print(f"    distinct sellers: {len(sellers)} of {len(tm.teams)}")
        holes = [(t.name, s) for t in tm.teams
                 for s, p in (t.rosterDict or {}).items() if p is None]
        print(f"    roster holes after everything: {len(holes)}")
        return len(trades), holes
    finally:
        session.close()


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--seasons', type=int, default=1)
    ap.add_argument('--arm', choices=['on', 'off'], default='on')
    ap.add_argument('--treasury', type=int, default=0,
                    help='seed every club this many Floobits (prod median ~1900)')
    args = ap.parse_args()
    try:
        count, holes = asyncio.run(main(args.seasons, args.arm == 'on', args.treasury))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    sys.exit(1 if holes else 0)
