"""Promoting a prospect in the FA draft does not use the team's pick (owner, 2026-10-24).

"it does feel a bit counterintuitive that a team will just promote a prospect instead of
signing a FA on their turn, feels like they should still be able to sign a player on that
turn"

Before: each turn made ONE move, so a team with open RB and WR slots that promoted its RB
prospect signed nobody that round, and its WR slot waited while the free agents it wanted
went elsewhere. Now every prospect who wins his slot (`prospectTakesSlot`, unchanged) is
promoted first and the team still makes its ordinary pick.

Run: .venv/bin/python -m pytest -q test_fa_draft_free_promotion.py
"""
import logging
logging.disable(logging.WARNING)

from managers.frontOfficeBrain import FrontOfficeBrain
from managers.playerManager import PlayerManager


class Pos:
    def __init__(s, v): s.value = v; s.name = {1: 'QB', 2: 'RB', 3: 'WR', 4: 'TE', 5: 'K'}[v]


class Tier:
    def __init__(s, v): s.value = v; s.name = v


class Attrs:
    def __init__(s, r): s.skillRating = r


class P:
    def __init__(s, pid, rating, pos=3, prospect=False, seasons=0):
        s.id = pid; s.name = f"P{pid}"; s.position = Pos(pos)
        s.playerRating = float(rating); s.attributes = Attrs(rating)
        s.season = float(rating)
        s.willRetire = False; s.team = 'Free Agent'; s.freeAgentYears = 1
        s.is_prospect = prospect; s.prospect_seasons = seasons
        s.playerTier = Tier('B'); s.term = 2; s.termRemaining = 2; s.previousTeam = 'Rookie'
        s.seasonsPlayed = 0


class T:
    def __init__(s, prospects, open_):
        s.id = 14; s.name = 'Slippers'; s.abbr = 'KCS'; s.coach = None
        s.prospects = list(prospects)
        s.rosterDict = {'qb': P(90, 80, 1), 'rb': P(91, 80, 2), 'wr1': P(92, 80, 3),
                        'wr2': P(95, 80, 3), 'te': P(93, 80, 4), 'k': P(94, 80, 5)}
        for slot in open_:
            s.rosterDict[slot] = None
        s._draftFilledSlots = set(); s.playerNumbersList = []

    def assignPlayerNumber(s, p): pass


class Brain:
    def seasonRating(self, player, coach=None, team=None):
        return player.season
    prospectTakesSlot = FrontOfficeBrain.prospectTakesSlot


class Stub:
    def __init__(s, fas):
        s.freeAgents = list(fas); s._faDraftBoards = {}; s._faBrain = Brain()
    def _leftThisTeamThisOffseason(s, p, t): return False
    def _getPlayerTerm(s, p): return 3
    def promotionTerm(s, p): return 2
    def _currentSeasonNumber(s): return 0
    # getattr so the file still imports against the old engine, where these tests fail.
    _promoteProspectIntoSlot = getattr(PlayerManager, '_promoteProspectIntoSlot', None)


def _turn(prospects, open_, rbs=(), wrs=()):
    """One FA-draft turn: a single `_attemptRosterFill` call."""
    team = T(prospects, open_)
    pm = Stub(list(rbs) + list(wrs))
    events = []
    complete = PlayerManager._attemptRosterFill(
        pm, team, [team], [], list(rbs), list(wrs), [], [], {}, [], eventLog=events)
    return team, complete, events


def test_a_promotion_and_a_signing_in_one_turn():
    rbProspect = P(1, 82, pos=2, prospect=True, seasons=1)
    rbFa = P(2, 75, pos=2)
    wrFa = P(3, 78, pos=3)
    team, complete, events = _turn([rbProspect], ['rb', 'wr2'], rbs=[rbFa], wrs=[wrFa])
    assert team.rosterDict['rb'] is rbProspect and rbProspect not in team.prospects
    assert team.rosterDict['wr2'] is wrFa
    assert complete
    assert [e.get('isPromotion', False) for e in events if e['type'] == 'pick'] == [True, False]


def test_two_prospects_fill_both_receiver_slots_in_one_turn():
    a = P(1, 84, pos=3, prospect=True, seasons=0)
    b = P(2, 80, pos=3, prospect=True, seasons=2)
    fa = P(3, 76, pos=3)
    team, complete, _ = _turn([a, b], ['wr1', 'wr2'], wrs=[fa])
    assert {team.rosterDict['wr1'], team.rosterDict['wr2']} == {a, b}
    assert complete and fa.team == 'Free Agent'


def test_a_prospect_who_loses_his_slot_still_leaves_one_move():
    rbProspect = P(1, 64, pos=2, prospect=True, seasons=0)
    rbFa = P(2, 80, pos=2)
    wrFa = P(3, 78, pos=3)
    team, complete, events = _turn([rbProspect], ['rb', 'wr2'], rbs=[rbFa], wrs=[wrFa])
    picks = [e for e in events if e['type'] == 'pick']
    assert len(picks) == 1 and not picks[0].get('isPromotion')
    assert rbProspect in team.prospects and not complete


def test_a_promotion_into_the_last_slot_completes_the_roster():
    rbProspect = P(1, 82, pos=2, prospect=True, seasons=1)
    rbFa = P(2, 75, pos=2)
    team, complete, events = _turn([rbProspect], ['rb'], rbs=[rbFa])
    assert team.rosterDict['rb'] is rbProspect and complete
    assert rbFa.team == 'Free Agent'
