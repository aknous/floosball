"""A free agent's age counts when he is weighed against a team's own player.

Owner, 2026-11-06: "teams do need to take player age into account". The incumbent's
side has carried his decline through `starterStanding` since 2026-10-10; the free agent
was priced on next season alone. Prod snapshot, season 13: the Melons planned to let
TeeTee Moonshine (86 QB, fourth season) walk for Riverdale Dreamcast, an 81 in his 13th,
who led by under a point before his own decline was counted.

Run: .venv/bin/python -m pytest -q test_free_agent_aging.py
"""
import types

from managers.frontOfficeBrain import FrontOfficeBrain, positionValue
from floosball_player import Position


class Brain(FrontOfficeBrain):
    """Values are ratings; aging drag comes from a per-player `drag` field."""

    def __init__(self):
        self.preferenceNotes = {}

    def decisionValue(self, player, coach=None, rng=None, team=None, **kw):
        return float(player.playerRating)

    def _agingDrag(self, starter, coach=None, team=None):
        return float(getattr(starter, 'drag', 0.0))

    def willSignWith(self, fa, team):
        return True


def _p(pid, rating, drag=0.0):
    return types.SimpleNamespace(id=pid, name=f'P{pid}', playerRating=rating,
                                 position=Position.QB, willRetire=False, drag=drag)


def test_an_aging_free_agent_is_priced_with_his_decline():
    old = _p(1, 81, drag=-1.4)
    assert Brain().freeAgentValue(old) == 81 - 1.4 * positionValue(old, 0.0)
    young = _p(2, 81)
    assert Brain().freeAgentValue(young) == 81


def test_an_aging_free_agent_a_hair_better_is_no_longer_an_upgrade():
    """The Moonshine case: the incumbent nets 80.3 after his standing, the free agent
    reads 80.7 before his own decline. With it counted he is not an upgrade, so the
    team has no reason to let the incumbent walk."""
    incumbent = _p(10, 80.3)
    assert Brain().upgradeConfidence(incumbent, pool=[_p(11, 80.7)], margin=0.2) == 1.0
    assert Brain().upgradeConfidence(incumbent, pool=[_p(12, 80.7, drag=-1.4)], margin=0.2) == 0.0


def test_the_draft_board_carries_the_same_price():
    team = types.SimpleNamespace(id=1, name='Melons')

    class B(Brain):
        def teamAppeal(self, team):
            return 99.0

        def appealDemand(self, player):
            return 0.0

    old = _p(20, 81, drag=-1.4)
    board = B().buildDraftBoard(team, [old])
    assert board[20] == B().freeAgentValue(old, team=team) < 81
