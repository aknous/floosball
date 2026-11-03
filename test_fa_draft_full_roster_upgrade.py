"""A full roster can cut to sign a better free agent (owner, 2026-11-01).

"a team should be able to cut a roster player (that wasnt just signed that offseason) to
sign a better player"

A team that started the FA draft with a full roster was marked done before the first
round, so it never reached `_upgradeCandidates`; only teams still filling a hole could
upgrade, and each team left the draft at the turn that filled its last slot. Measured on a
synthetic-fan run: rich teams sat on 80,000F Treasuries while 90-rated free agents went
unsigned. Now every team gets turns and is done once its roster is full and a turn makes
no move (`PlayerManager._draftTeamIsDone`). The upgrade rules are unchanged: nobody signed
or re-signed this offseason, nobody filled earlier in this draft, no protected player.

Run: .venv/bin/python -m pytest -q test_fa_draft_full_roster_upgrade.py
"""
import logging
logging.disable(logging.WARNING)

import pytest

from managers.playerManager import PlayerManager


@pytest.fixture(autouse=True)
def _treasuryCoversTheFee(monkeypatch):
    # The upgrade charges a cut fee from the team's Treasury. These tests are about who gets
    # a turn, not the fee, so the fee is always covered rather than read from whatever
    # database the run happens to point at (an empty one refused it and failed the test).
    from managers import facilitiesManager
    monkeypatch.setattr(facilitiesManager, 'chargeCutFee', lambda teamId, fee: True)
    monkeypatch.setattr(facilitiesManager, 'canPayCutFee', lambda teamId, fee: True)


class Pos:
    def __init__(s, v): s.value = v; s.name = {1: 'QB', 2: 'RB', 3: 'WR', 4: 'TE', 5: 'K'}[v]


class Tier:
    def __init__(s, v): s.value = v; s.name = v


class Attrs:
    def __init__(s, r): s.skillRating = r


class P:
    def __init__(s, pid, rating, pos=3, term=2, remaining=1):
        s.id = pid; s.name = f"P{pid}"; s.position = Pos(pos)
        s.playerRating = float(rating); s.attributes = Attrs(rating)
        s.willRetire = False; s.team = 'Free Agent'; s.freeAgentYears = 1
        s.is_prospect = False; s.prospect_seasons = 0
        s.playerTier = Tier('B'); s.term = term; s.termRemaining = remaining
        s.previousTeam = 'Elsewhere'; s.seasonsPlayed = 3; s.onProspectContract = False


class T:
    def __init__(s, roster):
        s.id = 7; s.name = 'Midnights'; s.abbr = 'CHI'; s.coach = None
        s.prospects = []
        s.rosterDict = roster
        s._draftFilledSlots = set(); s.playerNumbersList = []
        s.freeAgencyComplete = False

    def assignPlayerNumber(s, p): pass


class Stub:
    def __init__(s, fas, board):
        s.freeAgents = list(fas); s._faDraftBoards = {7: board}; s._faBrain = None
        s._faCutBars = {7: 6.0}
    def _leftThisTeamThisOffseason(s, p, t): return False
    def _getPlayerTerm(s, p): return 3
    def promotionTerm(s, p): return 2
    def _currentSeasonNumber(s): return 0
    releasePlayerToFreeAgency = PlayerManager.releasePlayerToFreeAgency


def _roster(wr1):
    return {'qb': P(90, 80, 1), 'rb': P(91, 80, 2), 'wr1': wr1,
            'wr2': P(95, 80, 3), 'te': P(93, 80, 4), 'k': P(94, 80, 5)}


def _turn(pm, team, wrs):
    events = []
    full = PlayerManager._attemptRosterFill(pm, team, [team], [], [], wrs, [], [], {}, [], eventLog=events)
    return full, events


def test_aFullRosterUpgradesThenLeavesTheDraft():
    weak = P(92, 72, 3)
    star, depth = P(1, 90, 3), P(2, 74, 3)
    team = T(_roster(weak))
    board = {p.id: p.playerRating for p in list(team.rosterDict.values()) + [star, depth]}
    wrs = [star, depth]
    pm = Stub(wrs, board)

    full, events = _turn(pm, team, wrs)
    assert team.rosterDict['wr1'] is star
    assert weak in pm.freeAgents
    assert [e['type'] for e in events if e['type'] in ('cut', 'pick')] == ['cut', 'pick']
    assert not PlayerManager._draftTeamIsDone(full, events)     # it moved: another turn

    full, events = _turn(pm, team, wrs)                        # nothing left clears the bar
    assert PlayerManager._draftTeamIsDone(full, events)


def test_aPlayerSignedThisOffseasonIsNotTheOneCut():
    justSigned = P(92, 72, 3, term=3, remaining=3)            # contract not yet counting down
    star = P(1, 90, 3)
    team = T(_roster(justSigned))
    team.rosterDict['wr2'] = P(95, 86, 3)                     # 90 beats him by less than the bar
    board = {p.id: p.playerRating for p in list(team.rosterDict.values()) + [star]}
    pm = Stub([star], board)
    full, events = _turn(pm, team, [star])
    assert team.rosterDict['wr1'] is justSigned
    assert team.rosterDict['wr2'].id == 95
    assert PlayerManager._draftTeamIsDone(full, events)


def test_aTeamFillingItsLastHoleGetsAnotherTurn():
    assert not PlayerManager._draftTeamIsDone(True, [{'type': 'pick'}])
    assert not PlayerManager._draftTeamIsDone(False, [])
    assert PlayerManager._draftTeamIsDone(True, [{'type': 'declined'}])


def test_anUpgradeItCannotPayForDoesNotBlockAnOpenSlot(monkeypatch):
    """2026-11-03: fills and upgrades compete for one pick, and a best-rated upgrade the team
    could not pay for ended every turn with nothing signed, so the draft force-ended with
    the team's open slot still empty and its games crashed all season."""
    from managers import facilitiesManager
    monkeypatch.setattr(facilitiesManager, 'canPayCutFee', lambda teamId, fee: False)
    monkeypatch.setattr(facilitiesManager, 'chargeCutFee', lambda teamId, fee: False)
    weak = P(92, 72, 3, term=3, remaining=2)
    star = P(1, 95, 3)                       # the upgrade: far better than the open-slot fill
    kicker = P(3, 70, 5)
    team = T(_roster(weak))
    team.rosterDict['k'] = None
    board = {p.id: p.playerRating for p in list(team.rosterDict.values()) if p} | {
        star.id: star.playerRating, kicker.id: kicker.playerRating}
    pm = Stub([star, kicker], board)
    PlayerManager._attemptRosterFill(
        pm, team, [team], [], [], [star], [], [kicker], {}, [], eventLog=[])
    assert team.rosterDict['k'] is kicker, "the open slot was left empty"
    assert team.rosterDict['wr1'] is weak, "an unaffordable cut went through"
