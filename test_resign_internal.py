"""A walk-year player is not re-signed when the team already has his replacement.

Reported (owner, 2026-10-02): the Strangers held the #1 pick with two top QBs in the class
(89 and 93 today) and re-signed a 74 QB for three seasons, which then left the rookie no
slot to be promoted into. Re-sign decisions now count the team's own prospects and, for a
top-2 pick, the rookie it expects to draft (owner: "when you have a top 3-5 pick, you
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
    bolt = _p(1, 78)    # above the star floor, so only the internal option decides
    assert Brain().chooseResigns([bolt], 2) == [bolt]
    assert Brain().chooseResigns([bolt], 2, internal=[_p(2, 93, rookie=True)]) == []


def test_a_weaker_internal_option_changes_nothing():
    bolt = _p(1, 78)
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

    def projectedRating(self, player, seasonsAhead, coach=None, team=None):
        # A rookie is read at his ceiling every season, anyone else at today's rating.
        if getattr(player, 'is_upcoming_rookie', False):
            return self._ceilingRating(player, team)
        return float(player.playerRating)


def test_the_teams_ahead_pick_off_their_own_boards():
    """The Bees pick 2nd (the predicted slots are the top 2). On their own read the WR is
    the pick, but the club ahead takes the WR on ITS read, so the Bees get the QB, not
    the WR they want. Each team picks by need (owner, 2026-11-06); with empty rosters
    that is each read's ceiling above replacement, position weighted."""
    qbA = _p(1, 80, Position.QB, ceiling=85, rookie=True)
    wr = _p(3, 80, Position.WR, ceiling=97, rookie=True)
    rb = _p(4, 70, Position.RB, ceiling=72, rookie=True)
    pm = _pm([qbA, wr, rb])
    first = _team(1, reads={1: 70, 3: 100})             # loves the WR, not the QB
    bees = _team(3, reads={3: 100})                     # also wants the WR first
    assert pm.expectedDraftees(Boards(), bees, [bees]) == [wr], "the Bees' own pick"
    got = pm.expectedDraftees(Boards(), bees, [first, bees])
    assert got == [qbA], [r.id for r in got]
    # A third pick is past the predicted slots and plans on nobody.
    third = _team(4)
    assert pm.expectedDraftees(Boards(), third, [first, bees, third]) == []


def test_a_walk_year_starter_is_assumed_to_stay_in_the_prediction():
    """The prediction feeds the decision on whether the walk-year starters stay, so it
    assumes they do: a team with a walk-year 90 QB is not predicted to take a 92 QB over
    a 85 RB it has nobody at, which would be planning to let him walk for a rookie it
    only drafts because he walks."""
    qb = _p(1, 80, Position.QB, ceiling=92, rookie=True)
    rbR = _p(2, 75, Position.RB, ceiling=85, rookie=True)
    starter = _p(9, 90, Position.QB); starter.termRemaining = 1; starter.willRetire = False
    team = _team(1)
    team.rosterDict = {'qb': starter}
    assert _pm([qb, rbR]).expectedDraftees(Boards(), team, [team]) == [rbR]


def test_a_later_pick_plans_on_nobody():
    rookies = [_p(10 + i, 80, Position.QB, ceiling=99 - i, rookie=True) for i in range(10)]
    owners = [_team(i) for i in range(1, 11)]
    assert _pm(rookies).expectedDraftees(Boards(), owners[7], owners) == []


if __name__ == '__main__':
    import sys, pytest
    sys.exit(pytest.main(['-q', __file__]))
