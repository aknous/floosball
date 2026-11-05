"""Offense, defense and each attribute carry the same public projected range as the
overall (owner, 2026-11-04: they looked exact beside an approximate overall), and nothing
on the player payload gives away an attribute's true potential.

Run: .venv/bin/python -m pytest -q test_projection_detail.py
"""
import os
import random
from types import SimpleNamespace

import numpy as np

from managers.playerManager import PlayerManager

HERE = os.path.dirname(os.path.abspath(__file__))


def _class(n=1, seed=7):
    random.seed(seed)
    np.random.seed(seed)
    pm = PlayerManager.__new__(PlayerManager)
    pm.activePlayers = []
    pm.unusedNames = [f'Prospect {i}' for i in range(5000)]
    pm.db_session = None
    pm.serviceContainer = SimpleNamespace(
        getService=lambda name: SimpleNamespace(teams=[None] * 32))
    return pm._generateRookieClass(n)


def _snapshot(p):
    a = p.attributes
    return (p.playerRating, p.offensiveRating, p.defensiveRating,
            tuple(getattr(a, k) for k in ('speed', 'power', 'agility', 'reach', 'hands',
                                          'armStrength', 'accuracy', 'legStrength')))


def test_every_range_is_ordered_and_the_player_is_untouched():
    for p in _class(2):
        before = _snapshot(p)
        d = p.projectionDetail(0.0)
        assert _snapshot(p) == before, "projecting changed the player"
        for key in ('offense', 'defense'):
            lo, mid, hi = d[key]
            assert lo <= mid <= hi, (key, d[key])
        for group in ('attributes', 'defensive'):
            for k, (lo, mid, hi) in d[group].items():
                assert lo <= mid <= hi, (group, k, lo, mid, hi)


def test_the_offense_range_matches_the_overall_model():
    """Same three states as the overall's range, so a prospect whose overall has a range
    has one on offense too."""
    ranged = 0
    for p in _class(2):
        lo, mid, hi = p.projectionRange(0.0)
        olo, omid, ohi = p.projectionDetail(0.0)['offense']
        if hi > lo:
            ranged += 1
            assert ohi > olo, (p.name, (lo, hi), (olo, ohi))
    assert ranged, "no prospect had a range to compare"


def test_a_player_whose_talent_is_known_has_one_number():
    p = _class(1)[0]
    p.talentRevealed = lambda: 1.0
    d = p.projectionDetail(0.0)
    assert d['offense'][0] == d['offense'][2]
    assert all(lo == hi for lo, _m, hi in d['attributes'].values())


def test_the_payload_carries_no_true_potential():
    """`att1PotStars` was the star rating of each attribute's TRUE potential, hidden talent
    included, readable off the network response."""
    src = open(os.path.join(HERE, 'api_response_builders.py')).read()
    assert "PotStars':" not in src
