"""The cull — `playerManager.cullUnsignedPool`.

⚠️ IT SHIPS WITH THE DRAFT, NOT AFTER IT. 192 roster spots are FIXED, so growing the
candidate population raises the bar through pure selection pressure with no change to
how players are generated: resampling the live rating distribution, a pool of 400 puts
63% of rosters at four stars against today's 35%. Every team ending up with four-star
players is the one outcome the draft must not produce. "After" means the pool grows
~13 a season until it arrives.

Two of its rules are counted in blood:

  ⚠️ IT MUST NOT EAT THE CLASS IT JUST DRAFTED. Prospects and upcoming rookies carry
     `seasonsPlayed == 0` BY DEFINITION.
  ⚠️ IT MUST NOT REMOVE ANYONE WITH A RECORD. Removal is hard — no retirement, no row —
     and today's free agents hold 2,782 game-stat rows and 253 user-owned cards between
     them.

See docs/PROSPECT_DRAFT_PLAN.md §3.

⚠️ `DATABASE_DIR` IS SET BEFORE THE FIRST IMPORT, AND THAT ORDERING IS NOT COSMETIC.
`database/connection.py` reads it at IMPORT time, so a `setdefault` further down the file
binds the engine to the REAL `data/floosball.db` first and the DB-backed cases below then
write fixture rows straight into the developer's live database. That happened while this
file was being written — five players, two season rows and a game line landed in the dev
DB and had to be deleted by hand. `test_anomaly_suppression.py` already carries the same
warning; this is what it is warning about.
"""

import os
import tempfile

os.environ['DATABASE_DIR'] = tempfile.mkdtemp(prefix='floos_cull_')

from constants import CULL_MIN_POOL_SEASONS, CULL_RATING_FRACTION_OF_MEAN
from managers.playerManager import PlayerManager
from floosball_player import Position


class FakePlayer:
    def __init__(self, pid, rating, freeAgentYears=5, seasonsPlayed=0,
                 isProspect=False, isUpcoming=False, draftingTeamId=None,
                 position=Position.QB, name=None):
        self.id = pid
        self.name = name or f"Player {pid}"
        self.playerRating = rating
        self.freeAgentYears = freeAgentYears
        self.seasonsPlayed = seasonsPlayed
        self.is_prospect = isProspect
        self.is_upcoming_rookie = isUpcoming
        self.drafting_team_id = draftingTeamId
        self.position = position


class FakeTeam:
    def __init__(self, ratings):
        self.rosterDict = {f"s{i}": FakePlayer(900 + i, r) for i, r in enumerate(ratings)}


class FakeTeamManager:
    def __init__(self, teams):
        self.teams = teams


class FakeContainer:
    def __init__(self, tm):
        self._tm = tm

    def getService(self, name):
        return self._tm if name == 'team_manager' else None


class Harness:
    """`cullUnsignedPool` off a real PlayerManager's own methods, with the record
    lookup stubbed — the DB half has its own test below."""

    def __init__(self, pool, rosterRatings=None, withRecord=()):
        ratings = rosterRatings or [80] * 32
        self.freeAgents = list(pool)
        self.activePlayers = list(pool)
        self.unusedNames = []
        self.serviceContainer = FakeContainer(FakeTeamManager([FakeTeam(ratings)]))
        self._withRecord = set(withRecord)
        self.removedFromPositionList = []

    def removeFromPositionList(self, player):
        self.removedFromPositionList.append(player)

    def _playersWithARecord(self, playerIds):
        return {pid for pid in playerIds if pid in self._withRecord}

    _removeUnsignedPlayer = PlayerManager._removeUnsignedPlayer
    cullUnsignedPool = PlayerManager.cullUnsignedPool


def _bar(rosterRatings):
    return (sum(rosterRatings) / len(rosterRatings)) * CULL_RATING_FRACTION_OF_MEAN


# ------------------------------------------------------- what it removes

def test_it_removes_the_never_rostered_and_long_unsigned():
    ratings = [80] * 32
    weak = FakePlayer(1, _bar(ratings) - 10, freeAgentYears=CULL_MIN_POOL_SEASONS)
    h = Harness([weak], ratings)
    result = h.cullUnsignedPool(5)
    assert [r['playerId'] for r in result['removed']] == [1]
    assert weak not in h.freeAgents and weak not in h.activePlayers
    print(f"PASS a {weak.playerRating:.0f} below the {result['bar']} bar is removed")


def test_the_bar_is_relative_to_the_leagues_own_mean():
    """⚠️ NOT AN ABSOLUTE NUMBER — the same self-normalising argument as the anomaly
    threshold. An absolute bar written against today's curve silently stops culling the
    moment the curve moves, which is exactly what this exists to prevent it doing."""
    low = Harness([], [70] * 32).cullUnsignedPool(5)['bar']
    high = Harness([], [90] * 32).cullUnsignedPool(5)['bar']
    assert high > low
    assert abs(low - 70 * CULL_RATING_FRACTION_OF_MEAN) < 0.1
    print(f"PASS the bar tracks the league: {low} in a weak league, {high} in a strong one")


def test_a_good_player_keeps_waiting():
    ratings = [80] * 32
    good = FakePlayer(1, _bar(ratings) + 5, freeAgentYears=9)
    h = Harness([good], ratings)
    assert h.cullUnsignedPool(5)['removed'] == []
    assert good in h.freeAgents
    print("PASS a player above the bar is never culled, however long he waits")


def test_the_grace_window_is_real():
    """One offseason of going unpicked says more about the draft order than about the
    player."""
    ratings = [80] * 32
    for years in range(0, CULL_MIN_POOL_SEASONS):
        h = Harness([FakePlayer(1, 40, freeAgentYears=years)], ratings)
        assert h.cullUnsignedPool(5)['removed'] == [], years
    h = Harness([FakePlayer(1, 40, freeAgentYears=CULL_MIN_POOL_SEASONS)], ratings)
    assert len(h.cullUnsignedPool(5)['removed']) == 1
    print(f"PASS nothing is culled before {CULL_MIN_POOL_SEASONS} seasons in the pool")


# ------------------------------------------------ what it must NOT touch

def test_it_does_not_eat_the_class_it_just_drafted():
    """⚠️ THE ONE THAT DELETES THE FEATURE. A prospect and an upcoming rookie both carry
    `seasonsPlayed == 0` by definition, so the naive predicate removes the class the
    draft has just placed — and the one it is about to."""
    ratings = [80] * 32
    prospect = FakePlayer(1, 40, isProspect=True, draftingTeamId=7)
    upcoming = FakePlayer(2, 40, isUpcoming=True)
    pipelined = FakePlayer(3, 40, draftingTeamId=7)
    h = Harness([prospect, upcoming, pipelined], ratings)
    assert h.cullUnsignedPool(5)['removed'] == []
    assert all(p in h.freeAgents for p in (prospect, upcoming, pipelined))
    print("PASS prospects, upcoming rookies and pipelined players are all exempt")


def test_it_never_removes_a_player_with_a_record():
    """⚠️ REMOVAL IS HARD — no retirement row, nothing left behind. A player who has
    PLAYED keeps his record: today's free agents hold 2,782 game-stat rows and 253
    user-owned cards between them, and hard-removing one tears a card out of somebody's
    collection. Never played -> remove. Played -> retire."""
    ratings = [80] * 32
    played = FakePlayer(1, 40, freeAgentYears=9)
    never = FakePlayer(2, 40, freeAgentYears=9)
    h = Harness([played, never], ratings, withRecord={1})
    removed = [r['playerId'] for r in h.cullUnsignedPool(5)['removed']]
    assert removed == [2], removed
    assert played in h.freeAgents
    print("PASS a player with a game row, a played season or an owned card is spared")


# ----------------------------------------------------------- the name

def test_the_name_comes_back_as_the_base():
    """⚠️ NO Jr. `_recyclePlayerName` always advances the ladder, and a rung is earned
    precisely BECAUSE the holder is gone — minting a Junior for a man who never played
    invents a father nobody ever saw, which is the fault that left 39 orphaned variants
    on the season-1 production database.

    ⚠️ And it skips the `NAME_REUSE_DELAY_SEASONS` hold: that hold exists so a FAMILIAR
    name does not reappear, and nobody is familiar with a player who never played."""
    ratings = [80] * 32
    h = Harness([FakePlayer(1, 40, freeAgentYears=9, name='Freed Marinara')], ratings)
    h.cullUnsignedPool(5)
    assert h.unusedNames == ['Freed Marinara'], h.unusedNames
    assert not any('Jr' in n or 'III' in n for n in h.unusedNames)
    print("PASS the name returns as the base, straight into the pool")


def test_a_name_is_not_returned_twice():
    ratings = [80] * 32
    h = Harness([FakePlayer(1, 40, freeAgentYears=9, name='Dup')], ratings)
    h.unusedNames.append('Dup')
    h.cullUnsignedPool(5)
    assert h.unusedNames.count('Dup') == 1
    print("PASS a name already in the pool is not duplicated")


# --------------------------------------------------------- the switch

def test_the_flag_disables_it_entirely():
    import constants
    ratings = [80] * 32
    original = constants.CULL_ENABLED
    try:
        constants.CULL_ENABLED = False
        h = Harness([FakePlayer(1, 40, freeAgentYears=9)], ratings)
        assert h.cullUnsignedPool(5) == {"removed": [], "bar": None}
        assert len(h.freeAgents) == 1
    finally:
        constants.CULL_ENABLED = original
    print("PASS CULL_ENABLED=False removes nobody")


def test_it_refuses_to_guess_a_bar_from_a_tiny_league():
    """A bar derived from three rostered players is noise, and culling on noise is worse
    than not culling."""
    h = Harness([FakePlayer(1, 10, freeAgentYears=9)], [80, 80, 80])
    assert h.cullUnsignedPool(5)['removed'] == []
    print("PASS no bar, no cull")


# ------------------------------ the record lookup, against a real database
#
# ⚠️ THE STUB ABOVE CANNOT CATCH THE BUG THAT MADE THIS CULL INERT FOR NINE SEASONS.
# The predicate was `seasonsPlayed == 0`, and `_handlePlayerSeasonProgression` increments
# that for EVERY active non-prospect — including an unsigned free agent who never took a
# snap. Then, with the proxy replaced by a real record test, a bare "has a season row"
# check read 100% of candidates as having a record, because the SAME archiver writes a
# zero-filled `PlayerSeasonStats` row for a pooled player every season. Both failures
# look exactly like a healthy pool from the outside. These run against real rows.

from database.connection import init_db, get_session            # noqa: E402
from database.models import (Player as DBPlayer, GamePlayerStats,      # noqa: E402
                             PlayerSeasonStats, CardTemplate, UserCard, User)

init_db()


def _seedPlayers(session, ids):
    for pid in ids:
        if not session.get(DBPlayer, pid):
            session.add(DBPlayer(id=pid, name=f"Cull {pid}", position=1))
    session.commit()


def test_a_zero_filled_season_row_is_not_a_record():
    """⚠️ THE SECOND FALSE NEGATIVE, AND THE SUBTLER ONE. `_handlePlayerSeasonProgression`
    archives a stat line for every active non-prospect at season end, so a washout
    collects a zero-filled `PlayerSeasonStats` row for every year he sits in the pool.
    Measured with a bare has-a-row test: 100% of cull candidates read as having a record
    and the cull removed nobody — indistinguishable from a healthy pool."""
    session = get_session()
    try:
        _seedPlayers(session, [7001, 7002])
        session.add(PlayerSeasonStats(player_id=7001, season=1, games_played=0))
        session.add(PlayerSeasonStats(player_id=7002, season=1, games_played=4))
        session.commit()
        marked = PlayerManager._playersWithARecord([7001, 7002])
        assert 7001 not in marked, "a 0-game season row was counted as a record"
        assert 7002 in marked, "a played season was not counted as a record"
    finally:
        session.close()
    print("PASS a 0-game season row is an archiver artifact, not a record")


def test_a_game_line_is_a_record():
    session = get_session()
    try:
        _seedPlayers(session, [7003])
        session.add(GamePlayerStats(game_id=999001, player_id=7003, team_id=1))
        session.commit()
        assert 7003 in PlayerManager._playersWithARecord([7003])
    finally:
        session.close()
    print("PASS a game line is a record")


def test_an_owned_card_is_a_record_but_a_bare_template_is_not():
    """⚠️ THE DISTINCTION MATTERS. A template nobody has pulled is mintable and
    disposable; a card in somebody's COLLECTION is the thing that must never be torn
    out — today's free agents hold 253 of those between them."""
    session = get_session()
    try:
        _seedPlayers(session, [7004, 7005])
        def _tpl(pid):
            return CardTemplate(player_id=pid, edition='base', season_created=1,
                                player_name=f'Cull {pid}', team_id=1, player_rating=70,
                                position='QB', rarity_weight=1, sell_value=1,
                                effect_config={})

        bare, owned = _tpl(7004), _tpl(7005)
        session.add_all([bare, owned])
        session.commit()
        user = session.query(User).first()
        if user is None:
            user = User(clerk_id='cull-test', username='cullTest',
                        email='cull-test@example.invalid')
            session.add(user)
            session.commit()
        session.add(UserCard(user_id=user.id, card_template_id=owned.id,
                             acquired_via='test'))
        session.commit()
        marked = PlayerManager._playersWithARecord([7004, 7005])
        assert 7004 not in marked, "an unpulled template blocked a cull"
        assert 7005 in marked, "an owned card did not protect its player"
    finally:
        session.close()
    print("PASS an owned card protects a player; an unpulled template does not")


def test_it_fails_closed():
    """⚠️ An inflated pool is a balance problem; a card torn out of somebody's collection
    is not recoverable. If the record cannot be checked, nothing is culled."""
    import managers.playerManager as pmModule
    original = pmModule.logger

    class Boom:
        def warning(self, *a, **kw):
            pass

    try:
        pmModule.logger = Boom()
        # An id type the query cannot handle forces the except path.
        marked = PlayerManager._playersWithARecord([object()])
        assert len(marked) == 1, "a failed lookup must report EVERY candidate as marked"
    finally:
        pmModule.logger = original
    print("PASS an unreachable database culls nobody")
