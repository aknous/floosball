"""Fans see a projection only for a player still rising (fixed 2026-11-05).

Aging lowers a veteran's attributes but never his true skill, so projecting every player
toward true skill showed 94 of 98 veterans with 8+ seasons (season-11 snapshot) heading back
UP on their profile: a 77 offense projected to 88. `_stillRising` gates the overall, offense,
defense and attribute projections, and a rising player's trade-vote "next season" reads the
public projection, not the true skill behind it.

Run: .venv/bin/python -m pytest -q test_projection_rising_only.py
"""
import os
import random
import sys
import tempfile
from types import SimpleNamespace

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
os.environ['DATABASE_DIR'] = tempfile.mkdtemp(prefix='floo_risingonly_')
sys.path.insert(0, HERE)
import logging
logging.disable(logging.CRITICAL)

from database.connection import init_db

init_db()
import api.main as api  # noqa: E402
from managers.playerManager import PlayerManager  # noqa: E402
from player_development import PlayerDevelopment, CareerPhase  # noqa: E402


def _player(seed=5):
    random.seed(seed)
    np.random.seed(seed)
    pm = PlayerManager.__new__(PlayerManager)
    pm.activePlayers = []
    pm.unusedNames = [f'Prospect {i}' for i in range(5000)]
    pm.db_session = None
    pm.serviceContainer = SimpleNamespace(
        getService=lambda name: SimpleNamespace(teams=[None] * 32))
    p = pm._generateRookieClass(1)[0]
    p.is_prospect = False
    p.is_upcoming_rookie = False
    return p


def _agedVeteran():
    """A long-serving player whose skills have aged below their true skill."""
    p = _player()
    p.seasonsPlayed = 14
    p.prospect_seasons = 0
    a = p.attributes
    for base in ('speed', 'power', 'agility', 'reach', 'hands', 'armStrength', 'accuracy', 'legStrength'):
        tru = getattr(a, 'trueSkill' + base[0].upper() + base[1:], None)
        if tru:
            setattr(a, base, max(60, int(tru) - 10))
    p.updateRating()
    assert PlayerDevelopment.careerContext(p, 0).phase != CareerPhase.RISING
    return p


def test_a_declining_veteran_gets_no_projection():
    vet = _agedVeteran()
    assert vet.computeExpectedRating() > vet.playerRating, 'fixture: true skill sits above today'
    assert api._prospectProjection(vet) is None
    assert api._projectionDetail(vet) is None


def test_a_rising_player_keeps_his_projection():
    young = _player(seed=9)
    young.seasonsPlayed = 0
    assert PlayerDevelopment.careerContext(young, 0).phase == CareerPhase.RISING
    assert api._prospectProjection(young) is not None
    assert api._projectionDetail(young) is not None


def test_a_prospect_always_keeps_his_projection():
    p = _player(seed=13)
    p.is_prospect = True
    assert api._prospectProjection(p) is not None
