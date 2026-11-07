"""The team plan's commitments (docs/TEAM_PLAN.md, stage 3).

When the re-sign step lets a starter walk because a prospect (or a top-pick rookie) takes
over, the FA draft and the washout last look honor it while the prospect is still the
team's. On the season-13 prod snapshot, in 2 of 4 runs, the Melons let TeeTee Moonshine
(86 QB) walk for Comicbook Connery, then signed Catface Martins (84) over Connery in the
FA draft: Moonshine was gone for nothing and Connery sat another season.

Run: .venv/bin/python -m pytest -q test_team_plan_commitments.py
"""
import logging
logging.disable(logging.WARNING)
import types

from floosball_player import Position
from managers.frontOfficeBrain import FrontOfficeBrain
from managers.playerManager import PlayerManager
import test_fa_draft_prospect_choice as fx


def _fill(prospects, fas, commitments=None):
    team = fx.T(prospects)
    pm = fx.Stub(fas)
    pm._prospectCommitments = commitments or {}
    pm.committedProspect = types.MethodType(PlayerManager.committedProspect, pm)
    PlayerManager._attemptRosterFill(pm, team, [team], [], [], list(fas), [], [], {}, [], [])
    return team, team.rosterDict['wr2']


def test_a_committed_prospect_takes_the_slot_over_a_better_free_agent():
    kid = fx.P(1, 82, season=82, prospect=True, seasons=2)
    fa = fx.P(2, 84, season=84)
    _team, filled = _fill([kid], [fa])
    assert filled is fa, "without a commitment the better free agent signs"
    kid = fx.P(1, 82, season=82, prospect=True, seasons=2)
    fa = fx.P(2, 84, season=84)
    _team, filled = _fill([kid], [fa], commitments={14: {1: 3}})
    assert filled is kid, "the plan let a starter go for him, so he takes the slot"
    print("PASS a committed prospect takes the slot over a better free agent")


def test_a_commitment_to_a_player_no_longer_a_prospect_is_ignored():
    kid = fx.P(1, 82, season=82, prospect=True, seasons=2)
    other = fx.P(3, 80, season=80, prospect=True, seasons=1)
    fa = fx.P(2, 84, season=84)
    # Committed to player 9, who is not among this team's prospects (traded, say).
    _team, filled = _fill([kid, other], [fa], commitments={14: {9: 3}})
    assert filled is fa
    print("PASS a commitment to someone no longer here changes nothing")


def test_the_re_sign_step_records_who_covers_a_walking_starter():
    """`rankResignCandidates` records the internal alternative that covers an incumbent
    (`lastCoverage`), which the re-sign step turns into a commitment."""
    class Brain(FrontOfficeBrain):
        def __init__(self):
            pass

        def decisionValue(self, player, coach=None, rng=None, team=None, **kw):
            return float(player.playerRating)

        def upgradeConfidence(self, *a, **kw):
            return 0.0

        def starterStanding(self, *a, **kw):
            return 0.0

        def _ceilingRating(self, player, team=None):
            return float(player.playerRating)

        def _growthBeyondNextSeason(self, *a, **kw):
            return 0.0

    starter = types.SimpleNamespace(id=10, name='Walker', playerRating=78, position=Position.QB)
    rookie = types.SimpleNamespace(id=11, name='Rookie', playerRating=93, position=Position.QB,
                                   is_upcoming_rookie=True)
    brain = Brain()
    assert brain.chooseResigns([starter], 2, internal=[rookie]) == []
    assert brain.lastCoverage == {10: rookie}
    print("PASS the re-sign step records who covers a walking starter")


def test_the_draft_takes_a_committed_rookie_if_he_is_still_there():
    """The re-sign step let a starter go because this team expected to draft him: the
    draft takes him if he is still on the board, whatever the plan now prefers."""
    from test_rookie_draft import FakePlayer, FakeTeam, Harness, StubBrain
    rookies = [FakePlayer(1, 80, Position.QB, 'Planned'), FakePlayer(2, 85, Position.RB, 'Better')]
    ceilings = {'Planned': 84, 'Better': 95}
    team = FakeTeam(1, 'Club')
    h = Harness(rookies)
    h._prospectCommitments = {1: {1: 1}}
    events = list(h.rookieDraftPickGenerator(rookies, [team],
                                             brain=StubBrain(lambda p, t: ceilings[p.name])))
    assert next(e for e in events if e['type'] == 'pick')['playerName'] == 'Planned'
    h = Harness([FakePlayer(1, 80, Position.QB, 'Planned'), FakePlayer(2, 85, Position.RB, 'Better')])
    events = list(h.rookieDraftPickGenerator(h.activePlayers, [team],
                                             brain=StubBrain(lambda p, t: ceilings[p.name])))
    assert next(e for e in events if e['type'] == 'pick')['playerName'] == 'Better'
    print("PASS the draft takes a committed rookie if he is still there")
