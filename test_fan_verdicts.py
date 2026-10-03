"""Clear fan ratings decide re-signs and cuts (owner, 2026-10-03), and no ratings is no
verdict ("if a player has no ratings, that cant be interpreted as a 0 rating").

Sentiment is the player's own team's fans' average rating on -1..+1 (3 is 0), so 0.5 is
an average of 4 and -0.5 an average of 2.

Run: .venv/bin/python -m pytest -q test_fan_verdicts.py
"""
import types

import managers.playerManager as PM
from managers.frontOfficeBrain import FrontOfficeBrain
from floosball_player import Position


class Brain(FrontOfficeBrain):
    """Values are ratings; the free-agent market never replaces anyone."""

    def __init__(self, sentiment):
        self.sentimentMap = sentiment
        self.season = 9

    def decisionValue(self, player, coach=None, rng=None, team=None, **kw):
        return float(player.playerRating)

    def upgradeConfidence(self, *a, **kw):
        return 0.0

    def classifyArc(self, player):
        return 'prime'


def _p(pid, rating):
    return types.SimpleNamespace(id=pid, name=f'P{pid}', playerRating=rating,
                                 position=Position.WR, onProspectContract=False)


def test_no_ratings_is_no_verdict():
    assert PM.fanVerdict(_p(1, 70), {}) is None
    assert PM.fanVerdict(_p(1, 70), {1: 0.2}) is None      # rated, but not clearly
    assert PM.fanVerdict(_p(1, 70), {1: 0.5}) == 'keep'
    assert PM.fanVerdict(_p(1, 70), {1: -0.5}) == 'walk'


def test_an_unrated_two_star_still_walks_on_stars():
    twoStar = _p(1, 72)
    assert Brain({}).chooseResigns([twoStar], 2) == []


def test_fans_keep_a_two_star_and_push_out_a_four_star():
    loved, disliked = _p(1, 72), _p(2, 86)
    kept = Brain({1: 0.6, 2: -0.6}).chooseResigns([loved, disliked], 2)
    assert kept == [loved]


def test_a_fan_favorite_is_kept_first_under_the_cap():
    loved, better = _p(1, 72), _p(2, 90)
    assert Brain({1: 0.6}).chooseResigns([better, loved], 1) == [loved]


def test_a_fan_favorite_cannot_be_cut():
    PM.setFanSentiment({1: 0.7})
    try:
        assert PM.isCutProtected(_p(1, 70), 9)
        assert not PM.isCutProtected(_p(2, 70), 9)
    finally:
        PM.setFanSentiment({})


if __name__ == '__main__':
    import sys, pytest
    sys.exit(pytest.main(['-q', __file__]))
