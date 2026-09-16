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


# ------------- 7. the free-agent pool is not an unlimited asset faucet -------

class _FakePos:
    def __init__(self, name, value):
        self.name, self.value = name, value


class _FakeGuy:
    def __init__(self, pid, name, pos=('QB', 1), rating=70):
        self.id, self.name = pid, name
        self.position = _FakePos(*pos)
        self.playerRating, self.termRemaining, self.term = rating, 2, 2
        self.team, self.previousTeam = None, None
        self.willRetire = False
        self.freeAgentYears = 0
        self.is_prospect = False
        self.prospect_seasons = 0
        self.drafting_team_id = None
        self.teamResignCount = 0


class _FakeClub:
    def __init__(self, tid, name):
        self.id, self.name = tid, name
        self.rosterDict, self.prospects = {}, []

    def assignPlayerNumber(self, p):
        pass


class _FakeSM:
    def __init__(self, pm):
        self.playerManager = pm
        self.currentSeason = type('S', (), {'seasonNumber': 7})()

    def _chargeCutFee(self, team, fee):
        return True                 # the economy is not what these seams are testing


class _FakePM:
    def __init__(self, freeAgents):
        self.freeAgents = list(freeAgents)

    def _getPlayerTerm(self, p):
        return 2

    def releasePlayerToFreeAgency(self, player, team, _highlights):
        self.freeAgents.append(player)
        player.team = 'Free Agent'


def test_a_club_may_not_CUT_a_player_it_BOUGHT_this_season():
    """⚠️ AN ACQUISITION IS NOT DISPOSABLE PACKAGING FOR THE NEXT DEAL (owner, 2026-09-15:
    "a team trading for a player and then cutting them immediately ... it was just a waste
    of assets and no real team would do that").

    Reported from the ledger: Phones traded for a quarterback, then a week later traded for
    a second and CUT the first to make room.
    """
    pm = _FakePM([])
    sm = _FakeSM(pm)
    buyer = _FakeClub(2, 'Phones')
    bought = _FakeGuy(510, 'Week Old')
    buyer.rosterDict = {'qb': bought}
    incoming = _FakeGuy(511, 'Next Man', rating=80)

    tradeManager._stampAcquired(bought, 7)                 # the headline of a trade
    assert tradeManager._cutToMakeRoom(sm, buyer, incoming, week=21) is None, \
        "a club cut the man it bought last week to make room for another"

    settled = _FakeGuy(512, 'Been Here A While')
    buyer.rosterDict = {'qb': settled}
    assert tradeManager._cutToMakeRoom(sm, buyer, incoming, week=21) == 'qb', \
        "a club could no longer cut a long-standing incumbent"
    print("PASS a player a club bought is not packaging for the next trade")


def test_a_GAP_FILL_PIECE_may_be_cut():
    """⚠️ HE WAS NEVER THE POINT OF THE TRADE (owner, 2026-09-16: "the seller got a roster
    player in return for sending out a star player, but theyd also would have had to get
    prospects or picks, which was the real return and the roster player was just someone to
    fill a gap").

    ⚠️ THIS IS WHY `wasHeadlineAcquisition` IS NARROWER THAN `wasAcquiredThisSeason`. The
    wide predicate still guards re-TRADING, where a piece must be covered; using it for the
    cut rule too blocked a move a real club would obviously make."""
    pm = _FakePM([])
    sm = _FakeSM(pm)
    club = _FakeClub(1, 'Sellers')
    filler = _FakeGuy(520, 'Gap Filler')
    club.rosterDict = {'qb': filler}
    tradeManager._stampAcquired(filler, 7, asPiece=True)

    assert tradeManager.wasAcquiredThisSeason(filler, 7), "the re-trade guard lost him"
    assert not tradeManager.wasHeadlineAcquisition(filler, 7)
    assert tradeManager._cutToMakeRoom(
        sm, club, _FakeGuy(521, 'Upgrade', rating=85), week=21) == 'qb', \
        "a gap-filling piece could not be moved on from"
    print("PASS a gap-filling piece is not protected like a purchase")


def test_the_cut_rule_does_not_reach_into_the_OFFSEASON():
    """⚠️ THE OFFSEASON RUNS UNDER THE SAME SEASON NUMBER, so a season-matched stamp
    silently protected every in-season acquisition right through it (owner, 2026-09-16:
    "players that were signed to fill gaps during the season can be cut in the offseason").

    ⚠️ AND IT WAS THROTTLING THE BLOCKBUSTER: that path is offseason-only and needs
    `_cutToMakeRoom` to make room, so the season-long ban suppressed the one feature built
    to produce a star trade."""
    pm = _FakePM([])
    sm = _FakeSM(pm)
    club = _FakeClub(2, 'Phones')
    bought = _FakeGuy(530, 'Bought In May')
    club.rosterDict = {'qb': bought}
    tradeManager._stampAcquired(bought, 7)
    incoming = _FakeGuy(531, 'Star', rating=92)

    assert tradeManager._cutToMakeRoom(sm, club, incoming, week=21) is None
    club.rosterDict = {'qb': bought}
    assert tradeManager._cutToMakeRoom(sm, club, incoming, week=None) == 'qb', \
        "the offseason still protected an in-season acquisition"
    print("PASS the rule is in-season; the offseason may reshape the roster")


def test_a_signed_backfill_may_still_be_traded_on():
    """⚠️ EXPLICITLY ALLOWED (owner: "I dont think its an issue for teams to sign a free
    agent and then trade them again if here's a willing partner"). The faucet worry is
    handled on the other side — a buyer cannot churn him straight back out."""
    signed = _FakeGuy(513, 'Just Signed')
    pm = _FakePM([signed])
    sm = _FakeSM(pm)
    club = _FakeClub(1, 'Residents')
    club.rosterDict = {'qb': None}
    tradeManager._installBackfill(sm, club, 'qb', ('freeAgent', signed))
    assert club.rosterDict['qb'] is signed
    assert not tradeManager.wasAcquiredThisSeason(signed, 7), \
        "a signed replacement was frozen out of the market"
    print("PASS a club may sign a replacement and trade him on")


def test_the_OFFSEASON_cannot_sign_a_free_agent_as_a_backfill():
    """Owner, 2026-09-15: "teams are signing free agents as part of the trade ... this
    shouldnt be happening in the offseason if its before the free agent draft."

    ⚠️ `_findBackfill`'s OWN DOCSTRING ASSERTED THIS AND NOTHING ENFORCED IT. Both offseason
    passes run BEFORE `_processFreeAgency`, so a club selling a starter was helping itself
    to the best man in the pool ahead of the worst-first draft whose whole purpose is to
    decide who gets him — a contender could sign a better free agent than the club picking
    first ever saw."""
    fa = _FakeGuy(502, 'Pool Man', rating=88)
    pm = _FakePM([fa])
    sm = _FakeSM(pm)
    club = _FakeClub(1, 'Sellers')
    club.rosterDict = {'qb': _FakeGuy(503, 'Starter')}
    outgoing = _FakeGuy(504, 'Outgoing')

    inSeason = tradeManager._findBackfill(sm, club, outgoing, week=18)
    offseason = tradeManager._findBackfill(sm, club, outgoing, week=None)
    assert inSeason is not None and inSeason[0] == 'freeAgent'
    assert offseason is None, f"the offseason reached into the pool: {offseason}"
    print("PASS the pool is closed until the draft opens it")


def test_the_offseason_still_trades_with_NO_backfill():
    """⚠️ AND LEAVING THE HOLE IS THE POINT, NOT A COMPROMISE. `_processFreeAgency` fills
    every empty slot in worst-first order and both trade passes run before it, so refusing
    an offseason trade for want of a backfill refuses it over a problem that resolves
    itself a few steps later."""
    src = inspect.getsource(tradeManager.settleTrade)
    assert 'if backfill is None and week is not None:' in src, \
        "the offseason still declines a trade it cannot backfill"
    print("PASS an offseason seller may leave the slot for the draft")


def test_the_offseason_fills_NOTHING_at_settlement_not_even_a_promotion():
    """⚠️ THE HOLE WAITS FOR THE DRAFT, AND PROMOTING ON THE SPOT PRE-EMPTS A DECISION THE
    CLUB SHOULD MAKE THERE (owner, 2026-09-16: "positions slots on the roster that are
    emptied due to a trade dont need to be filled right away, because the FA draft is
    coming up. the team can decide to promote their prospects during that draft, or sign a
    better FA even if it blocks their prospect").

    Measured: promoting immediately made that choice badly — Midnights sold a 77 TE and
    installed its own 62. `playerManager._attemptRosterFill` already picks the best player
    available across the pool AND the pipeline, which is the decision being deferred to."""
    prospect = _FakeGuy(505, 'Ready Kid', rating=76)
    prospect.is_prospect = True
    pm = _FakePM([])
    sm = _FakeSM(pm)
    club = _FakeClub(1, 'Sellers')
    club.prospects = [prospect]
    outgoing = _FakeGuy(506, 'Outgoing')

    assert tradeManager._findBackfill(sm, club, outgoing, week=None) is None, \
        "the offseason promoted a prospect instead of leaving the slot for the draft"
    # in-season there IS no draft coming, so the club must still fill the hole
    found = tradeManager._findBackfill(sm, club, outgoing, week=18)
    assert found is not None and found[0] == 'prospect', found
    print("PASS the offseason defers the slot; the season still fills it")


def test_the_FLOOR_prices_the_whole_board_in_the_offseason_too():
    """⚠️ GATING THE POOL OUT OF THE OFFSEASON FLOOR WAS AN OVER-CORRECTION, and it is worth
    recording because the first version of this test asserted the opposite.

    The seller signs nobody at settlement now, so the pool IS what replaces him — just at
    the draft, where `_attemptRosterFill` will sign over a prospect if the free agent is
    better. Pricing the floor against the club's own prospect alone made a weak pipeline a
    reason not to sell a player the draft would have replaced perfectly well."""
    from test_trade_market import (FakeTeam, FakePlayer, FakeTeamManager,
                                   FakePlayerManager, StubBrain)
    from managers.tradeManager import TradeMarket
    from floosball_player import Position

    club = FakeTeam(1, 'Midnights')
    star = FakePlayer(600, 77, Position.TE, termRemaining=3)
    club.rosterDict['te'] = star
    club.prospects = [FakePlayer(601, 62, Position.TE, termRemaining=3, isProspect=True)]
    strongFA = FakePlayer(602, 80, Position.TE, termRemaining=2)
    strongFA.team = 'Free Agent'

    def market(week):
        return TradeMarket(FakePlayerManager([strongFA]), FakeTeamManager([club]),
                           StubBrain(), 3, week)

    assert market(18)._backfillRating(club, star) == 80
    assert market(None)._backfillRating(club, star) == 80, \
        "the offseason floor ignored the pool the draft will actually draw from"
    print("PASS both phases price the floor against the whole board")


def test_handOverPieces_STAMPS_them_as_pieces():
    """⚠️ TESTING THE PREDICATE IS NOT TESTING THE CALL SITE. A first version of the
    gap-filler test stamped `asPiece=True` by hand, so flipping the real `_handOverPieces`
    call back to a headline stamp changed nothing and the check passed regardless. The
    distinction only exists if the code that moves a piece actually records it."""
    fromTeam, toTeam = _FakeClub(1, 'Buyers'), _FakeClub(2, 'Sellers')
    piece = _FakeGuy(540, 'Coming Back')
    fromTeam.rosterDict = {'qb': piece}
    toTeam.rosterDict = {'qb': None}
    pm = _FakePM([])
    sm = _FakeSM(pm)

    tradeManager._handOverPieces(
        sm, [{'kind': 'player', 'id': 540, 'name': 'Coming Back'}],
        fromTeam, toTeam, season=7, sellerSlot='qb')

    assert toTeam.rosterDict['qb'] is piece, "the piece never arrived"
    assert tradeManager.wasAcquiredThisSeason(piece, 7), "the re-trade guard lost him"
    assert not tradeManager.wasHeadlineAcquisition(piece, 7), \
        "a bundle piece was recorded as a purchase, so it is protected like one"
    print("PASS the hand-over records a piece AS a piece")


def test_a_man_acquired_IN_an_offseason_cannot_be_cut_in_that_same_offseason():
    """⚠️ THE EXEMPTION WAS PHASE-BLIND AND THE CHURN JUST MOVED INTO THE OFFSEASON.

    Reported from the ledger: Strangers took a 76 TE from Pinecones in a swap, then later
    in the SAME offseason bought a 77 TE from Midnights and cut the 76 to make room, paying
    450F. Net they gave up a 77, two picks and the fee to end with a 77.

    "You may cut him next offseason" and "you may cut him ten minutes later in the same
    offseason" are different rules, and a season-only stamp cannot tell them apart because
    the offseason runs under the season number it follows."""
    pm = _FakePM([])
    sm = _FakeSM(pm)
    club = _FakeClub(1, 'Strangers')
    justTraded = _FakeGuy(560, 'Arrived In The Offseason')
    club.rosterDict = {'qb': justTraded}
    incoming = _FakeGuy(561, 'Better Man', rating=85)

    tradeManager._stampAcquired(justTraded, 7, phase='offseason')
    assert tradeManager._cutToMakeRoom(sm, club, incoming, week=None) is None, \
        "a club cut the man it acquired earlier in this same offseason"

    # ...but an IN-SEASON acquisition may still be moved on from once the offseason comes.
    club.rosterDict = {'qb': justTraded}
    tradeManager._stampAcquired(justTraded, 7, phase='season')
    assert tradeManager._cutToMakeRoom(sm, club, incoming, week=None) == 'qb', \
        "the in-season gap-fill exemption was lost"
    print("PASS an offseason arrival survives that offseason; an in-season one may go")


