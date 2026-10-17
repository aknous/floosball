"""An open slot is filled in the FA draft, and the team weighs its prospect against the
free agents it can sign (owner, 2026-10-17).

"teams should be able to hold off on promoting until the free agent draft. when they're
looking to fill a slot that they have a prospect for, they should look and see if any of
the available players are currently better than their prospect, or if their prospect is
projecting to be as good as a player they could sign. they also could sign the FA to a
deal that covers the remaining amount of seasons on the prospects window so that the
prospect isnt blocked, and then when that contract is up make a decision"

Prod-snapshot sim before this: BUF promoted a 64 rookie WR into the slot an 83 had just
left, because the prospect and the free agent were compared on board value, which
credits the prospect's ceiling.

Run: .venv/bin/python -m pytest -q test_fa_draft_prospect_choice.py
"""
import logging
logging.disable(logging.WARNING)

from constants import PROSPECT_DEVELOPMENT_WINDOW
from managers.frontOfficeBrain import FrontOfficeBrain
from managers.playerManager import PlayerManager


class Pos:
    def __init__(s, v): s.value = v; s.name = {1: 'QB', 2: 'RB', 3: 'WR', 4: 'TE', 5: 'K'}[v]


class Tier:
    def __init__(s, v): s.value = v; s.name = v


class Attrs:
    def __init__(s, r): s.skillRating = r


class P:
    def __init__(s, pid, rating, season=None, prospect=False, seasons=0):
        s.id = pid; s.name = f"P{pid}"; s.position = Pos(3)
        s.playerRating = float(rating); s.attributes = Attrs(rating)
        s.season = float(season if season is not None else rating)
        s.willRetire = False; s.team = 'Free Agent'; s.freeAgentYears = 1
        s.is_prospect = prospect; s.prospect_seasons = seasons
        s.playerTier = Tier('B'); s.term = 2; s.termRemaining = 2; s.previousTeam = 'Rookie'
        s.seasonsPlayed = 0


class T:
    def __init__(s, prospects):
        s.id = 14; s.name = 'Slippers'; s.abbr = 'KCS'; s.coach = None
        s.prospects = list(prospects)
        s.rosterDict = {'qb': P(90, 80), 'rb': P(91, 80), 'wr1': P(92, 80), 'wr2': None,
                        'te': P(93, 80), 'k': P(94, 80)}
        s._draftFilledSlots = set(); s.playerNumbersList = []

    def assignPlayerNumber(s, p): pass


class Brain:
    """`seasonRating` is a knob on the player; the decision rule is the real one."""
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


def _fill(prospects, fas):
    team = T(prospects)
    pm = Stub(fas)
    PlayerManager._attemptRosterFill(pm, team, [team], [], [], list(fas), [], [], {}, [], [])
    return team, team.rosterDict['wr2']


def test_a_free_agent_better_now_and_this_season_signs_for_the_window():
    rookie = P(1, 64, season=66, prospect=True, seasons=0)
    fa = P(2, 78, season=77)
    team, got = _fill([rookie], [fa])
    assert got is fa and rookie in team.prospects and rookie.is_prospect
    assert fa.term == PROSPECT_DEVELOPMENT_WINDOW - 0 == fa.termRemaining


def test_the_deal_ends_when_the_prospects_window_does():
    lastLook = P(1, 70, prospect=True, seasons=PROSPECT_DEVELOPMENT_WINDOW - 1)
    fa = P(2, 80)
    _team, got = _fill([lastLook], [fa])
    assert got is fa and fa.term == 1


def test_a_prospect_projecting_as_good_this_season_is_promoted():
    prospect = P(1, 74, season=77, prospect=True, seasons=1)
    fa = P(2, 76, season=76)
    team, got = _fill([prospect], [fa])
    assert got is prospect and prospect not in team.prospects


def test_a_prospect_already_as_good_is_promoted():
    prospect = P(1, 80, season=80, prospect=True, seasons=0)
    fa = P(2, 78, season=79)
    _team, got = _fill([prospect], [fa])
    assert got is prospect


def test_the_better_of_two_prospects_this_season_is_the_one_weighed():
    rookie = P(1, 70, season=71, prospect=True, seasons=0)
    veteran = P(3, 75, season=76, prospect=True, seasons=PROSPECT_DEVELOPMENT_WINDOW - 1)
    fa = P(2, 72, season=72)
    team, got = _fill([rookie, veteran], [fa])
    assert got is veteran and rookie in team.prospects


def test_with_nobody_to_sign_the_prospect_is_promoted():
    prospect = P(1, 60, prospect=True, seasons=0)
    _team, got = _fill([prospect], [])
    assert got is prospect


def test_without_a_prospect_the_free_agent_signs_on_a_normal_deal():
    fa = P(2, 78)
    _team, got = _fill([], [fa])
    assert got is fa and fa.term == 3
