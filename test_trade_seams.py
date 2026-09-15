"""The seams this project actually breaks in.

⚠️ THESE MATTER MORE THAN THE ARITHMETIC. Every one is a repeat of a real incident.

  * a mid-week trade landing inside a live fantasy week — FOUR separate incidents
  * a pick resolving off the wrong club's finish
  * a two-sided trade half-dropped by an idempotency key built for one player
  * fan ratings deleted to express a rule
  * an offseason pass re-running on a restart

See docs/TRADING_PLAN.md §12.4.
"""

import inspect
import os
import tempfile

os.environ['DATABASE_DIR'] = tempfile.mkdtemp(prefix='floos_seam_')

import constants                                                    # noqa: E402
from managers import tradeManager                                   # noqa: E402
from managers.seasonManager import SeasonManager                     # noqa: E402
from database.connection import init_db, get_session                 # noqa: E402
from database.models import (DraftPick, Trade, SeasonRecapEvent,     # noqa: E402
                             PlayerSentimentRating, Player as DBPlayer, User)

init_db()


# ------------------------------------- 1. the fantasy seam (four incidents)

def test_a_trade_can_only_land_at_the_week_rollover():
    """⚠️ `cardEffects` READS A DEPICTED PLAYER'S CLUB AT SCORING TIME and the lineup locks
    at kickoff, so a trade executed BETWEEN TWO SLATES moves a player between the lock and
    the bank and a card equipped against club A scores against club B's result.

    This project has had FOUR separate incidents in exactly this seam: the lineup-snapshot
    drift, `equipped_cards` not being a historical record, the leaderboard's second door,
    and Veteran's backfill.

    Asserted on the call site, because the safety is POSITIONAL: the pass must sit after
    `_onWeekComplete`, which is what banks the week.
    """
    src = inspect.getsource(SeasonManager._simulateRegularSeason)
    bank = src.index('await self._onWeekComplete(self.currentSeason.currentWeek')
    trade = src.index('self._runTradePass(')
    assert bank < trade, "the trade pass runs BEFORE the week is banked"
    print("PASS the trade pass sits after the week banks")


def test_the_pass_refuses_to_run_inside_an_unbanked_week():
    """⚠️ THE GUARD IS IN THE CODE, NOT IN A COMMENT. The caller places it correctly today;
    a future caller might not, and a comment does not stop that."""
    src = inspect.getsource(SeasonManager._runTradePass)
    assert '_weekIsBanked' in src
    gateSrc = inspect.getsource(SeasonManager._weekIsBanked)
    assert 'WeeklyPlayerFP' in gateSrc, \
        "the gate does not read the banked record"
    assert 'return False' in gateSrc.split('except')[-1], \
        "the gate fails OPEN — an unconfirmable week must not permit a trade"
    print("PASS the pass gates on the banked week and fails closed")


def test_the_pass_is_shut_from_the_deadline():
    src = inspect.getsource(SeasonManager._runTradePass)
    assert 'GM_ACTIVE_WEEK' in src
    print("PASS the deadline is enforced at the call site too")


# ------------------------------------------------ 2. pick identity

def test_a_pick_resolves_off_the_ORIGINAL_teams_finish():
    """⚠️ TRADE YOUR PICK, FINISH WORST, AND THE RECEIVER GETS #1.

    That is correct and dramatic — but only if a pick is identified by
    `(season, round, ORIGINAL team)` and resolved to a slot at derivation time. The
    plausible wrong implementation gives the RECEIVER its own slot, which is a different
    and much duller feature.
    """
    from managers.tradeManager import TradeMarket

    class T:
        def __init__(self, tid, wins, losses):
            self.id, self.wins, self.losses = tid, wins, losses
            self.name = f"T{tid}"
            self.rosterDict, self.prospects, self.coach = {}, [], None

    # Club 1 finishes WORST; club 2 finishes best and owns club 1's pick.
    worst, best = T(1, 1, 13), T(2, 13, 1)

    class TM:
        teams = [worst, best]

    class PM:
        freeAgents = []

    class Brain:
        sentimentMap = {}

        def decisionValue(self, *a, **kw):
            return 0.0

    session = get_session()
    try:
        session.query(DraftPick).delete()
        session.add(DraftPick(season=9, round_number=1,
                              original_team_id=1, current_owner_id=2))
        session.commit()
    finally:
        session.close()

    market = TradeMarket(PM(), TM(), Brain(), season=9, week=20)
    picks = market.picksOwnedBy(best)
    assert len(picks) == 1, picks
    assert picks[0]['originalTeamId'] == 1
    assert picks[0]['slot'] == 1, \
        f"the receiver got slot {picks[0]['slot']} — resolved off ITS OWN finish"
    assert market.picksOwnedBy(worst) == [], \
        "the club that traded its pick still holds it"
    print("PASS the receiver of the worst club's pick gets the #1 selection")


def test_a_trade_moves_only_the_OWNER_not_the_origin():
    """⚠️ Rewriting `original_team_id` on a trade hands the receiver the BUYER's draft
    position instead of the seller's — the duller feature, arrived at by one wrong line."""
    src = inspect.getsource(tradeManager._handOverPieces)
    assert 'current_owner_id' in src
    assert 'original_team_id =' not in src, \
        "the hand-over rewrites the pick's ORIGIN"
    print("PASS only ownership moves")


# --------------------------------------- 3. the recap idempotency key

def test_a_two_sided_trade_writes_both_sides():
    """⚠️ `SeasonRecapEvent`'s KEY IS `(season, event_type, player_id|team_id)` — ONE
    PLAYER, ONE CLUB — WHICH A TWO-SIDED TRADE DOES NOT FIT. Both sides are 'trade' rows in
    the same season, so without a trade id the resume dedupe SILENTLY DROPS HALF OF EVERY
    SWAP."""
    sm = SeasonManager.__new__(SeasonManager)

    class S:
        seasonNumber = 11

    sm.currentSeason = S()
    session = get_session()
    try:
        session.query(SeasonRecapEvent).filter_by(season=11).delete()
        session.commit()
    finally:
        session.close()

    manifest = {
        'season': 11, 'teamAId': 1, 'teamBId': 2,
        'teamAName': 'Alpha', 'teamBName': 'Beta',
        'aGave': [{'kind': 'player', 'id': 5, 'name': 'Someone'}],
        'bGave': [{'kind': 'pick', 'id': 9, 'name': 'S11 R1 pick'}],
    }
    tradeManager._recordTrade(sm, manifest, tradeId=77)

    session = get_session()
    try:
        rows = session.query(SeasonRecapEvent).filter_by(season=11, event_type='trade').all()
        assert len(rows) == 2, f"only {len(rows)} side(s) recorded"
        assert {r.team_id for r in rows} == {1, 2}
        assert all(r.trade_id == 77 for r in rows)
    finally:
        session.close()
    print("PASS both sides recorded, both carrying the trade id")


def test_two_trades_between_the_same_clubs_both_survive():
    """The sharper version: without the trade id in the key, the SECOND swap between the
    same two clubs in one season is deduped away entirely."""
    sm = SeasonManager.__new__(SeasonManager)

    class S:
        seasonNumber = 12

    sm.currentSeason = S()
    session = get_session()
    try:
        session.query(SeasonRecapEvent).filter_by(season=12).delete()
        session.commit()
    finally:
        session.close()

    base = {'season': 12, 'teamAId': 1, 'teamBId': 2,
            'teamAName': 'Alpha', 'teamBName': 'Beta',
            'aGave': [{'kind': 'player', 'id': 5, 'name': 'First'}],
            'bGave': [{'kind': 'pick', 'id': 9, 'name': 'A pick'}]}
    tradeManager._recordTrade(sm, base, tradeId=101)
    second = dict(base, aGave=[{'kind': 'player', 'id': 6, 'name': 'Second'}])
    tradeManager._recordTrade(sm, second, tradeId=102)

    session = get_session()
    try:
        rows = session.query(SeasonRecapEvent).filter_by(season=12, event_type='trade').all()
        assert len(rows) == 4, f"{len(rows)} rows — a swap was deduped away"
        assert {r.trade_id for r in rows} == {101, 102}
    finally:
        session.close()
    print("PASS two swaps between the same clubs keep all four rows")


# ----------------------------------------- 4. fan ratings are not deleted

def test_a_trade_does_not_delete_fan_ratings():
    """⚠️ THOSE ROWS ARE THINGS REAL USERS WROTE — production holds 153 of them across 107
    players. "His sentiment does not follow him" is expressed by re-scoping the AGGREGATE
    to the current club's fans, not by deleting the row: the same rating cannot be
    recovered if he is traded back, and nothing else in this system deletes a fan's
    opinion to express a rule."""
    src = inspect.getsource(tradeManager.settleTrade)
    assert 'PlayerSentimentRating' not in src
    # ⚠️ Comments are allowed to say "delete"; CODE is not. Strip them before looking,
    # because the comment explaining WHY nothing is deleted would otherwise fail this.
    code = '\n'.join(line.split('#')[0] for line in src.splitlines())
    assert 'delete' not in code.lower(), "settlement deletes something"
    assert 'sentiment' in src.lower(), "the settlement does not even mention sentiment"
    print("PASS settlement destroys no fan data")


def test_the_aggregate_re_scopes_to_the_current_club():
    """The behaviour the owner ruled, with nothing destroyed. ⚠️ Traded back, his old
    ratings reactivate — which is correct, because those fans are his fans again."""
    from database.repositories.sentiment_repository import SentimentRepository
    session = get_session()
    try:
        session.query(PlayerSentimentRating).filter(
            PlayerSentimentRating.player_id == 8001).delete()
        if not session.get(DBPlayer, 8001):
            session.add(DBPlayer(id=8001, name='Traded', position=3, team_id=1))
        fans = []
        for i, (uid, favourite) in enumerate([(8101, 1), (8102, 1), (8103, 1)]):
            user = session.get(User, uid)
            if user is None:
                user = User(id=uid, clerk_id=f'seam-{uid}', username=f'seam{uid}',
                            email=f'seam{uid}@example.invalid')
                session.add(user)
            user.favorite_team_id = favourite
            fans.append(uid)
        session.commit()
        for uid in fans:
            session.merge(PlayerSentimentRating(user_id=uid, player_id=8001, rating=5,
                                                season=1))
        session.commit()

        repo = SentimentRepository(session)
        before = repo.getSentimentMap([8001]).get(8001)

        # He is traded to club 2. Nothing is deleted.
        session.get(DBPlayer, 8001).team_id = 2
        session.commit()
        after = repo.getSentimentMap([8001]).get(8001)
        rowsLeft = session.query(PlayerSentimentRating).filter_by(player_id=8001).count()

        assert rowsLeft == 3, "ratings were destroyed"
        assert before is not None, "his own club's fans were not counted before the trade"
        assert after != before, "his old club's fans still speak for his new one"

        # Traded back, his old ratings reactivate.
        session.get(DBPlayer, 8001).team_id = 1
        session.commit()
        assert repo.getSentimentMap([8001]).get(8001) == before
    finally:
        session.close()
    print("PASS the aggregate re-scopes, the rows survive, and a return restores them")


# --------------------------------------------- 5. picks are seeded once

def test_pick_seeding_is_idempotent():
    """A pick must EXIST before it can be traded, and a future pick belongs to a draft
    that has not happened. Seeded lazily — and seeded TWICE must not double the league's
    draft capital."""
    sm = SeasonManager.__new__(SeasonManager)

    class T:
        def __init__(self, tid):
            self.id = tid
            self.name = f"T{tid}"

    class TM:
        teams = [T(1), T(2), T(3)]

    class Container:
        def getService(self, name):
            return TM() if name == 'team_manager' else None

    sm.serviceContainer = Container()
    session = get_session()
    try:
        session.query(DraftPick).delete()
        session.commit()
    finally:
        session.close()

    sm._ensureDraftPicks(20)
    session = get_session()
    try:
        first = session.query(DraftPick).count()
    finally:
        session.close()
    sm._ensureDraftPicks(20)
    session = get_session()
    try:
        second = session.query(DraftPick).count()
    finally:
        session.close()

    horizon = constants.TRADE_PICK_HORIZON_SEASONS + 1
    assert first == 3 * horizon, (first, horizon)
    assert second == first, f"a second pass created {second - first} phantom picks"
    print(f"PASS {first} picks seeded across {horizon} seasons, idempotently")


# --------------------------------- 6. the offseason passes are step-gated

def test_the_offseason_passes_are_step_gated():
    """⚠️ NON-NEGOTIABLE. Every other offseason phase guards on
    `_isOffseasonStepComplete` and marks itself done. A deploy landing mid-pass would
    otherwise re-run it and trade AGAIN from an already-changed roster — and the offseason
    is exactly where this project's restarts land."""
    src = inspect.getsource(SeasonManager._runOffseasonTradePass)
    assert "_isOffseasonStepComplete(step)" in src
    assert "_markOffseasonStepComplete(step)" in src
    assert "f'trade_{passName}'" in src, "both passes share one marker — one would skip the other"
    print("PASS both offseason passes gate and mark themselves, under distinct keys")


def test_running_an_offseason_pass_twice_trades_once():
    """The property the gate exists for, exercised rather than read."""
    sm = SeasonManager.__new__(SeasonManager)

    class S:
        seasonNumber = 30

    sm.currentSeason = S()
    sm._offseasonTransactions = []
    done = set()
    sm._isOffseasonStepComplete = lambda step: step in done
    sm._markOffseasonStepComplete = lambda step: done.add(step)

    calls = []
    original = tradeManager.runWeeklyPass
    originalFlag = constants.TRADING_ENABLED
    try:
        constants.TRADING_ENABLED = True
        tradeManager.TRADING_ENABLED = True

        def spy(*a, **kw):
            calls.append(kw.get('week', a[-1] if a else None))
            return []

        tradeManager.runWeeklyPass = spy
        sm.playerManager = None
        sm.serviceContainer = type('C', (), {'getService': lambda self, n: None})()
        sm._ensureDraftPicks = lambda season: None
        sm._foBrainForOffseason = lambda: None

        sm._runOffseasonTradePass('pre_draft')
        sm._runOffseasonTradePass('pre_draft')
        assert len(calls) == 1, f"the pass ran {len(calls)} times"
        # ⚠️ And the two passes must not share a marker, or running A would skip B.
        sm._runOffseasonTradePass('pre_fa')
        assert len(calls) == 2, "the second window was skipped by the first one's marker"
    finally:
        tradeManager.runWeeklyPass = original
        constants.TRADING_ENABLED = originalFlag
        tradeManager.TRADING_ENABLED = originalFlag
    print("PASS a re-run trades once, and the two windows are independent")


def test_the_offseason_pass_prices_in_OFFSEASON_terms():
    """⚠️ `week=None` IS WHAT TELLS THE VALUATION IT IS THE OFFSEASON, and both halves
    matter. `seasonsOfControl` JUMPS — the walk-years are gone, so everyone remaining has
    WHOLE seasons of term and the rental market does not exist here at all. And
    `nowWeight` RESETS to parity, which removes the buyer/seller asymmetry entirely — so
    the offseason market cannot run on contention and runs on the other three triggers."""
    src = inspect.getsource(SeasonManager._runOffseasonTradePass)
    assert 'season, None)' in src, "the offseason pass is priced with an in-season week"

    import trading
    assert trading.seasonsOfControl(1, None) == 1.0
    assert trading.seasonsOfControl(1, 20) < 0.5
    assert trading.nowWeight(0.9, 0.5, None) == 1.0, \
        "contention still separates clubs in the offseason"
    print("PASS the offseason prices whole seasons at parity")


# ------------------------------- 7. a traded pick must change who picks

def test_a_traded_pick_actually_changes_the_draft_order():
    """⚠️ EVERY TRADED PICK WAS COSMETIC. The draft read `freeAgencyOrder` straight
    through and never consulted `DraftPick` at all, so a club could trade for the first
    selection, watch the transactions page say so, and then not get it. A quarter of every
    bundle in the measured ledger was picks — all of it paying for nothing.

    ⚠️ And the slot stays the ORIGINAL club's: trade your pick, finish worst, and the
    buyer takes number one."""
    sm = SeasonManager.__new__(SeasonManager)

    class S:
        seasonNumber = 40

    sm.currentSeason = S()

    class T:
        def __init__(self, tid):
            self.id, self.name = tid, f"T{tid}"

    worst, mid, best = T(1), T(2), T(3)
    session = get_session()
    try:
        session.query(DraftPick).filter_by(season=40).delete()
        for tid in (1, 2, 3):
            session.add(DraftPick(season=40, round_number=1,
                                  original_team_id=tid, current_owner_id=tid))
        # The worst club traded its own pick to the best club.
        session.commit()
        row = session.query(DraftPick).filter_by(season=40, original_team_id=1).first()
        row.current_owner_id = 3
        session.commit()
    finally:
        session.close()

    order = sm._applyPickOwnership([worst, mid, best])
    assert [t.id for t in order] == [3, 2, 3], [t.id for t in order]
    print("PASS the club that bought the worst team's pick selects first — and twice")


def test_a_spent_pick_cannot_be_traded_again():
    """Stamped `used` as the draft consumes it, or last year's pick stays on the market."""
    sm = SeasonManager.__new__(SeasonManager)

    class S:
        seasonNumber = 41

    sm.currentSeason = S()

    class T:
        def __init__(self, tid):
            self.id, self.name = tid, f"T{tid}"

    session = get_session()
    try:
        session.query(DraftPick).filter_by(season=41).delete()
        session.add(DraftPick(season=41, round_number=1,
                              original_team_id=1, current_owner_id=1))
        session.commit()
    finally:
        session.close()

    sm._applyPickOwnership([T(1)])
    session = get_session()
    try:
        row = session.query(DraftPick).filter_by(season=41, original_team_id=1).first()
        assert row.used is True, "the pick survived the draft unspent"
    finally:
        session.close()
    print("PASS a used pick leaves the market")


# ---------------------- 6. a swap must not swallow the player it swaps -------

def test_a_same_position_swap_leaves_NO_roster_hole():
    """⚠️ THE HAND-BACK LOOKED THE PLAYER UP AFTER HIS SLOT WAS ALREADY OVERWRITTEN.

    `settleTrade` writes the incoming player into `buyerSlot`, which in a same-position
    swap is the very slot the outgoing swap player is standing in. `_handOverPieces` then
    ran its own `_findRostered(buyer, ...)`, found nothing, and returned QUIETLY — so the
    seller kept the hole from giving up his starter, the swap player ended up on neither
    roster, and `player.team` pointed at a club with no slot holding him.

    Measured over two seasons: **216 games crashed at kickoff** on a None in `rosterDict`
    (`player.gameAttributes = copy.deepcopy(player.attributes)`), every one swallowed by
    `_simulateGame`'s except — so the league played on around the wreckage and the
    end-of-season integrity check came back clean, because the FA draft refills holes.
    """
    class P:
        def __init__(self, pid, name, pos, team):
            self.id, self.name = pid, name
            self.position = type('Pos', (), {'value': pos, 'name': pos})()
            self.team, self.previousTeam = team, None
            self.playerRating, self.termRemaining = 80, 2
            self.teamResignCount, self.willRetire = 0, False

    class T:
        def __init__(self, tid, name):
            self.id, self.name = tid, name
            self.rosterDict, self.prospects = {}, []

        def assignPlayerNumber(self, p):
            pass

    seller, buyer = T(1, 'Sellers'), T(2, 'Buyers')
    sold = P(101, 'Sold Man', 'WR', seller)
    swap = P(102, 'Swap Man', 'WR', buyer)
    seller.rosterDict = {'qb': P(103, 'S QB', 'QB', seller), 'wr1': sold}
    buyer.rosterDict = {'qb': P(104, 'B QB', 'QB', buyer), 'wr1': swap}

    class Winner:
        pieces = [{'kind': 'player', 'id': 102, 'name': 'Swap Man'}]
        value = 10.0
        team = buyer

    class SM:
        currentSeason = type('S', (), {'seasonNumber': 1})()

        def _recordOffseasonEvent(self, *a, **kw):
            pass

    listing = type('L', (), {'team': seller, 'player': sold, 'trigger': 'x',
                             'ask': 1.0, 'floor': 1.0})()

    manifest = tradeManager.settleTrade(SM(), listing, Winner(), season=1, week=16)
    assert manifest is not None, "the swap did not settle at all"

    holes = [f"{t.name}.{sl}" for t in (seller, buyer)
             for sl, h in t.rosterDict.items() if h is None]
    assert not holes, f"roster hole(s) left behind: {holes}"
    assert seller.rosterDict['wr1'] is swap, "the swap player never reached the seller"
    assert buyer.rosterDict['wr1'] is sold, "the sold player never reached the buyer"
    assert swap.team is seller and sold.team is buyer
    print("PASS a same-position swap fills both slots and leaves no hole")
