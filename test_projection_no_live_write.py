"""A projection never writes to the live player, not even for a moment (fixed 2026-11-05).

The projections used to raise the live player's attributes, recompute his rating and
restore it. API endpoints read projections from request threads while the sim runs on the
event loop, so a thread switch between the write and the restore let the sim read or save a
projected value. Projections now work on a private copy (`Player._ratingTwin`).

The test wraps the rating recompute: every time it runs, the LIVE player's attributes and
ratings must still be exactly what they were before the projection started.

Run: .venv/bin/python -m pytest -q test_projection_no_live_write.py
"""
import random
from types import SimpleNamespace

import numpy as np

from managers.playerManager import PlayerManager


def _class(n=3, seed=11):
    random.seed(seed)
    np.random.seed(seed)
    pm = PlayerManager.__new__(PlayerManager)
    pm.activePlayers = []
    pm.unusedNames = [f'Prospect {i}' for i in range(5000)]
    pm.db_session = None
    pm.serviceContainer = SimpleNamespace(
        getService=lambda name: SimpleNamespace(teams=[None] * 32))
    return pm._generateRookieClass(n)


def _state(p):
    return (dict(vars(p.attributes)), p.playerRating, p.offensiveRating, p.defensiveRating)


def test_projections_never_touch_the_live_player():
    players = _class(3)
    for live in players:
        before = _state(live)
        cls = type(live)
        original = cls.updateRating
        calls = []

        def guarded(self, _orig=original, _live=live, _before=before):
            calls.append(self is _live)
            assert _state(_live) == _before, 'a projection wrote to the live player'
            return _orig(self)

        cls.updateRating = guarded
        try:
            live.projectionDetail(0.0)
            live.projectionRange(0.0)
            live.projectionFor(0.0)
            live.computeExpectedRating()
            live.computeCeilingRating()
            live.computeNextSeasonRating(2)
        finally:
            cls.updateRating = original
        assert calls, 'the projections never recomputed a rating, so nothing was tested'
        assert not any(calls), 'a projection recomputed the live player instead of a copy'
        assert _state(live) == before
