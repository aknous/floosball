"""A draft slot nobody can use is TRADED, not burned.

⚠️ A SKIPPED PICK IS A DESTROYED ASSET, AND THE CLUB COULD NOT HAVE SEEN IT COMING. Owner,
2026-09-15: "the issue probably comes up when teams only have prospect spots for 1 or two
positions but there's no prospects left at those positions, which teams won't be able to
predict ahead of time. ideally, teams should be able to trade their pick in the moment if
they cant pick anyone, or get some kind of compensation."

⚠️ MEASURED, AND IT IS EXACTLY THAT CASE: over six seasons the skip fired twice, both
`no_eligible_rookies` and ZERO `pipeline_full`. The `PROSPECT_SLOT_CAP_PER_POSITION`
ceiling never binds, so nobody forfeits through a choice they made.
"""

import os
import tempfile

os.environ['DATABASE_DIR'] = tempfile.mkdtemp(prefix='floos_pt_')

from database.connection import init_db, get_session                 # noqa: E402
from database.models import DraftPick                                # noqa: E402
from floosball_player import Position                                # noqa: E402
from managers.playerManager import PlayerManager                     # noqa: E402

init_db()

SEASON = 60


class FakeRookie:
    def __init__(self, rid, position, rating=80):
        self.id, self.position, self.playerRating = rid, position, rating
        self.name = f"R{rid}"
        self.is_prospect = False
        self.is_upcoming_rookie = True
        self.prospect_seasons = 0
        self.drafting_team_id = None
        self.team = None

    @property
    def playerTier(self):
        return type('T', (), {'name': 'TierB'})()


class FakeTeam:
    def __init__(self, tid, name):
        self.id, self.name = tid, name
        self.abbr = name[:3].upper()
        self.coach = None
        self.prospects = []
        self.rosterDict = {}

    def assignPlayerNumber(self, p):
        pass


def _pm():
    """A PlayerManager with only the pieces these helpers touch."""
    pm = PlayerManager.__new__(PlayerManager)
    pm.activePlayers = []
    pm.freeAgents = []
    pm._draftBrain = None
    pm.db_session = None            # __del__ reads it
    for attr in ('activeQbs', 'activeRbs', 'activeWrs', 'activeTes', 'activeKs'):
        setattr(pm, attr, [])
    pm.sortPlayersByPosition = lambda: None
    return pm


def _seedPicks(teamIds, season):
    session = get_session()
    try:
        session.query(DraftPick).filter(DraftPick.season.in_([season, season + 1])).delete(
            synchronize_session=False)
        for s in (season, season + 1):
            for tid in teamIds:
                session.add(DraftPick(season=s, round_number=1,
                                      original_team_id=tid, current_owner_id=tid))
        session.commit()
    finally:
        session.close()


def test_a_slot_nobody_can_use_finds_a_buyer():
    pm = _pm()
    skipper, buyer = FakeTeam(1, 'Skippers'), FakeTeam(2, 'Buyers')
    _seedPicks([1, 2], SEASON)

    # The skipper has room only at kicker; the board holds only receivers.
    skipper.prospects = [FakeRookie(90 + i, p) for i, p in enumerate(
        [Position.QB, Position.QB, Position.RB, Position.RB,
         Position.WR, Position.WR, Position.TE, Position.TE])]
    available = [FakeRookie(1, Position.WR), FakeRookie(2, Position.WR)]

    assert pm.hasOpenProspectSlot(skipper, Position.K)
    assert not pm.hasOpenProspectSlot(skipper, Position.WR)

    found, eligible = pm.findPickBuyer(skipper, available, [skipper, buyer], SEASON)
    assert found is buyer, found
    assert eligible, "the buyer was offered the slot with nobody to take"
    print("PASS a club with room at a live position picks the slot up")


def test_a_buyer_that_has_already_traded_next_years_pick_cannot_pay():
    """⚠️ THE BUYER MUST STILL OWN ITS OWN NEXT-SEASON PICK. A club that has already dealt
    it has nothing to pay with, and taking one it merely HOLDS would let a club launder a
    third party's pick through a slot nobody could use."""
    pm = _pm()
    skipper, buyer = FakeTeam(1, 'Skippers'), FakeTeam(2, 'Buyers')
    _seedPicks([1, 2], SEASON)
    session = get_session()
    try:
        row = session.query(DraftPick).filter_by(
            season=SEASON + 1, original_team_id=2).first()
        row.current_owner_id = 99            # already sold elsewhere
        session.commit()
    finally:
        session.close()

    skipper.prospects = [FakeRookie(90 + i, p) for i, p in enumerate(
        [Position.QB, Position.QB, Position.RB, Position.RB,
         Position.WR, Position.WR, Position.TE, Position.TE])]
    found, _ = pm.findPickBuyer(skipper, [FakeRookie(1, Position.WR)],
                                [skipper, buyer], SEASON)
    assert found is None, "a club with nothing to pay with still bought the slot"
    print("PASS a club that already dealt next year's pick cannot buy this one")


def test_the_handover_moves_ONLY_the_owner():
    """⚠️ ONLY `current_owner_id` MOVES, ON A ROW THAT ALREADY EXISTS. The slot resolves off
    `original_team_id`, so rewriting that would hand the receiver the buyer's own draft
    position instead — and a new row would collide with `_ensureDraftPicks`, which keeps
    exactly one per club per season."""
    pm = _pm()
    skipper, buyer = FakeTeam(1, 'Skippers'), FakeTeam(2, 'Buyers')
    _seedPicks([1, 2], SEASON)

    assert pm.handOverNextSeasonPick(buyer, skipper, SEASON) is True
    session = get_session()
    try:
        rows = session.query(DraftPick).filter_by(season=SEASON + 1).all()
        assert len(rows) == 2, f"a row was created or destroyed: {len(rows)}"
        moved = [r for r in rows if r.original_team_id == 2][0]
        assert moved.current_owner_id == 1, "the owner did not move"
        assert moved.original_team_id == 2, "the ORIGINAL club was rewritten"
        mine = [r for r in rows if r.original_team_id == 1][0]
        assert mine.current_owner_id == 1, "the skipper's own pick was touched"
    finally:
        session.close()
    print("PASS the handover moves the owner and nothing else")


def test_the_draft_TRADES_the_slot_instead_of_yielding_a_skip():
    """End to end: the generator must stop emitting `skip` where a buyer exists, and the
    buyer must actually select."""
    pm = _pm()
    skipper, buyer = FakeTeam(1, 'Skippers'), FakeTeam(2, 'Buyers')
    _seedPicks([1, 2], SEASON)
    skipper.prospects = [FakeRookie(90 + i, p) for i, p in enumerate(
        [Position.QB, Position.QB, Position.RB, Position.RB,
         Position.WR, Position.WR, Position.TE, Position.TE])]
    rookies = [FakeRookie(1, Position.WR, 84)]

    events = list(pm.rookieDraftPickGenerator(
        rookies, [skipper], leagueHighlights=None, season=SEASON,
        leagueTeams=[skipper, buyer]))
    kinds = [e['type'] for e in events]

    assert 'skip' not in kinds, f"the slot was burned: {kinds}"
    assert 'pick_traded' in kinds, kinds
    traded = next(e for e in events if e['type'] == 'pick_traded')
    assert traded['team'] == 'Skippers' and traded['to'] == 'Buyers'
    assert traded['forSeason'] == SEASON + 1

    made = [e for e in events if e['type'] == 'pick']
    assert len(made) == 1 and made[0]['teamName'] == 'Buyers', made
    assert rookies[0].drafting_team_id == 2, "the player went to the wrong club"
    print("PASS the slot is traded and the buyer drafts in it")


def test_it_still_skips_when_NOBODY_can_use_the_slot():
    """⚠️ The trade is an improvement on the forfeit, not a replacement for it — if no club
    in the league has room at a position with a rookie left, the pick really is dead and
    must still resolve rather than hang."""
    pm = _pm()
    skipper = FakeTeam(1, 'Skippers')
    _seedPicks([1], SEASON)
    full = [FakeRookie(90 + i, p) for i, p in enumerate(
        [Position.QB, Position.QB, Position.RB, Position.RB,
         Position.WR, Position.WR, Position.TE, Position.TE,
         Position.K, Position.K])]
    skipper.prospects = full
    events = list(pm.rookieDraftPickGenerator(
        [FakeRookie(1, Position.WR)], [skipper], leagueHighlights=None, season=SEASON,
        leagueTeams=[skipper]))
    kinds = [e['type'] for e in events]
    assert 'skip' in kinds and 'pick_traded' not in kinds, kinds
    print("PASS a genuinely dead pick still resolves as a skip")


def test_the_buyer_pool_is_the_LEAGUE_not_the_draft_order():
    """⚠️ THE ORDER IS A LIST OF OWNERS. A club that sold its own pick does not appear in it
    at all — and that is precisely a club that might want back into this draft. Sourcing
    buyers from the order excludes the most motivated ones and silently shrinks the market
    to whoever already had a selection."""
    pm = _pm()
    skipper = FakeTeam(1, 'Skippers')
    soldTheirs = FakeTeam(2, 'Sellers')          # not in the order: no selection of its own
    _seedPicks([1, 2], SEASON)
    skipper.prospects = [FakeRookie(90 + i, p) for i, p in enumerate(
        [Position.QB, Position.QB, Position.RB, Position.RB,
         Position.WR, Position.WR, Position.TE, Position.TE])]
    available = [FakeRookie(1, Position.WR)]

    fromOrder, _ = pm.findPickBuyer(skipper, available, [skipper], SEASON)
    fromLeague, _ = pm.findPickBuyer(skipper, available, [skipper, soldTheirs], SEASON)
    assert fromOrder is None
    assert fromLeague is soldTheirs, "a club outside the order could not buy back in"
    print("PASS a club with no selection of its own can still buy one")
