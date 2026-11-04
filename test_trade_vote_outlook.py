"""What a trade vote shows fans about each piece (owner, 2026-11-04): what a pick is likely
to fetch, a prospect's projection and window, a roster player's career stage.

Run: .venv/bin/python -m pytest -q test_trade_vote_outlook.py
"""
import os
import sys
import tempfile
from types import SimpleNamespace

HERE = os.path.dirname(os.path.abspath(__file__))
os.environ['DATABASE_DIR'] = tempfile.mkdtemp(prefix='floo_voteoutlook_')
sys.path.insert(0, HERE)
import logging
logging.disable(logging.CRITICAL)

from database.connection import init_db, get_session
from database.models import DraftPick

init_db()
import api.main as api  # noqa: E402

SEASON = 10
# Team ids worst-first: team 1 picks first.
ORDER = list(range(1, 33))


class _Rookie:
    def __init__(self, pid, mid, spread):
        self.id, self.is_upcoming_rookie = pid, True
        self._r = (mid - spread, mid, mid + spread)

    def projectionRange(self, vision):
        return self._r


def _setup():
    s = get_session()
    picks = [DraftPick(season=SEASON, round_number=1, original_team_id=5, current_owner_id=9),
             DraftPick(season=SEASON + 1, round_number=1, original_team_id=30, current_owner_id=9)]
    for p in picks:
        s.add(p)
    s.commit()
    ids = [p.id for p in picks]
    s.close()
    klass = [_Rookie(5000 + i, 90 - i, 6) for i in range(40)]
    api.floosball_app = SimpleNamespace(
        playerManager=SimpleNamespace(activePlayers=klass),
        teamManager=SimpleNamespace(teams=[]),
        seasonManager=SimpleNamespace(currentSeason=SimpleNamespace(seasonNumber=SEASON)))
    api._rookieDraftOrder = lambda: (ORDER, False, 17)
    return ids


UPCOMING, NEXT = _setup()


def _trade():
    return SimpleNamespace(assets_json={'aGave': [], 'bGave': [
        {'kind': 'pick', 'id': UPCOMING}, {'kind': 'pick', 'id': NEXT}]})


def test_theTypicalOutcomeComesFromTheCurrentModelTable():
    """Not the league's own drafts, which ran under the old prospect model (owner)."""
    import constants
    t = api._pickTypical(20.4)
    assert t['band'] == [17, 24]
    row = next(r for r in constants.PICK_OUTCOME_BY_SLOT if r[0] == (17, 24))
    assert (t['medianBest'], t['threeStarShare'], t['fourStarShare']) == row[1:]
    assert api._pickTypical(40) is None
    assert not hasattr(api, '_draftHistory')


def test_anUpcomingPickShowsItsSlotAndTheProspectThere():
    s = get_session()
    try:
        out = api._pickOutlooks(s, [_trade()], SEASON)
    finally:
        s.close()
    o = out[UPCOMING]
    assert o['draftsOut'] == 0 and o['slot'] == 5 and o['slotFinal'] is False
    # The 5th best prospect by consensus: 90, 89, 88, 87, 86.
    assert o['classProspect']['rank'] == 5 and o['classProspect']['expected'] == 86.0
    assert o['typical']['band'] == [4, 8]


def test_aLaterPickIsExpectedNearerTheMiddleAndHasNoClassYet():
    s = get_session()
    try:
        out = api._pickOutlooks(s, [_trade()], SEASON)
    finally:
        s.close()
    o = out[NEXT]
    assert o['draftsOut'] == 1 and 'slot' not in o and 'classProspect' not in o
    assert 16 < o['expectedSlot'] < 30
    assert o['typical']['band'][0] <= o['expectedSlot'] <= o['typical']['band'][1]


def test_aRosterPlayerCarriesHisCareerStageAndNextSeason():
    player = SimpleNamespace(id=7, is_prospect=False, termRemaining=2, seasonsPlayed=9,
                             computeNextSeasonRating=lambda bias: 77)
    pm = SimpleNamespace(activePlayers=[], computeCareerStage=lambda p: 'aging')
    api.floosball_app.playerManager = pm
    try:
        a = api._withContractInfo([{'kind': 'player', 'id': 7}], {7: player})[0]
    finally:
        api.floosball_app.playerManager = SimpleNamespace(activePlayers=[])
    assert (a['careerStage'], a['nextSeason'], a['termRemaining'], a['seasonsPlayed']) == \
        ('aging', 77, 2, 9)
    assert 'projection' not in a


def test_aProspectCarriesHisWindow():
    prospect = SimpleNamespace(id=8, is_prospect=True, prospect_seasons=2,
                               projectionRange=lambda v: (70, 76, 84))
    a = api._withContractInfo([{'kind': 'prospect', 'id': 8}], {8: prospect})[0]
    assert a['projection'] == {'low': 70.0, 'high': 84.0}
    assert a['windowLeft'] == 1
