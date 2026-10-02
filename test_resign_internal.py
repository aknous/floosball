"""A walk-year player is not re-signed when the team already has his replacement.

Reported (owner, 2026-10-02): the Strangers held the #1 pick with two top QBs in the class
(89 and 93 today) and re-signed a 74 QB for three seasons, which then left the rookie no
slot to be promoted into. Re-sign decisions now count the team's own prospects and, for a
top-5 pick, the rookie it expects to draft (owner: "when you have a top 3-5 pick, you
should have a good idea of which players will be available to you").

Run: .venv/bin/python -m pytest -q test_resign_internal.py
"""
import types

import managers.playerManager as PM
from managers.frontOfficeBrain import FrontOfficeBrain
from floosball_player import Position


class Brain(FrontOfficeBrain):
    """Values are ratings; the free-agent market never replaces anyone."""

    def __init__(self):
        pass

    def decisionValue(self, player, coach=None, rng=None, team=None, **kw):
        return float(player.playerRating)

    def upgradeConfidence(self, *a, **kw):
        return 0.0

    def _ceilingRating(self, player, team=None):
        return float(player.ceiling)


def _p(pid, rating, pos=Position.QB, ceiling=None, rookie=False):
    return types.SimpleNamespace(id=pid, name=f'P{pid}', playerRating=rating, position=pos,
                                 ceiling=ceiling or rating, is_upcoming_rookie=rookie)


def test_a_better_internal_replacement_lets_the_incumbent_walk():
    bolt = _p(1, 74)
    assert Brain().chooseResigns([bolt], 2) == [bolt]
    assert Brain().chooseResigns([bolt], 2, internal=[_p(2, 93, rookie=True)]) == []


def test_a_weaker_internal_option_changes_nothing():
    bolt = _p(1, 74)
    assert Brain().chooseResigns([bolt], 2, internal=[_p(2, 70, rookie=True)]) == [bolt]


def test_one_replacement_covers_one_player_the_weakest():
    wr1, wr2 = _p(1, 72, Position.WR), _p(2, 78, Position.WR)
    kept = Brain().chooseResigns([wr1, wr2], 2, internal=[_p(3, 90, Position.WR)])
    assert kept == [wr2]


def test_a_prospect_projected_higher_but_worse_today_does_not_replace_him():
    """The Sodas let a 76 QB walk for a 66 prospect they projected higher."""
    malibu = _p(1, 76)
    kid = _p(2, 66)

    class Projecting(Brain):
        def decisionValue(self, player, coach=None, rng=None, team=None, **kw):
            return 90.0 if player is kid else float(player.playerRating)

    assert Projecting().chooseResigns([malibu], 2, internal=[kid]) == [malibu]


def _pm(rookies):
    pm = PM.PlayerManager.__new__(PM.PlayerManager)
    pm.activePlayers = rookies
    pm.db_session = None
    return pm


def _team(tid, reads=None):
    return types.SimpleNamespace(id=tid, prospects=[], reads=reads or {})


class Boards(Brain):
    """Each team reads ceilings off its own `reads` map (fallback: the true ceiling)."""

    def _ceilingRating(self, player, team=None):
        return float((getattr(team, 'reads', None) or {}).get(player.id, player.ceiling))


def test_the_teams_ahead_pick_off_their_own_boards():
    """The Bees pick 3rd. On their board the third-best is a QB, but the clubs ahead
    take a WR and a QB on THEIR boards, so the Bees get the other QB, not a WR."""
    qbA, qbB = _p(1, 80, Position.QB, ceiling=99, rookie=True), _p(2, 80, Position.QB, ceiling=96, rookie=True)
    wr = _p(3, 80, Position.WR, ceiling=97, rookie=True)
    rb = _p(4, 80, Position.RB, ceiling=90, rookie=True)
    pm = _pm([qbA, qbB, wr, rb])
    first = _team(1)                                    # true reads: qbA
    second = _team(2, reads={3: 100})                   # loves the WR
    bees = _team(3, reads={4: 98})                      # rates the RB above qbB
    got = pm.expectedDraftees(Boards(), bees, [first, second, bees])
    assert got == [rb], [r.id for r in got]


def test_a_later_pick_plans_on_nobody():
    rookies = [_p(10 + i, 80, Position.QB, ceiling=99 - i, rookie=True) for i in range(10)]
    owners = [_team(i) for i in range(1, 11)]
    assert _pm(rookies).expectedDraftees(Boards(), owners[7], owners) == []


if __name__ == '__main__':
    import sys, pytest
    sys.exit(pytest.main(['-q', __file__]))
