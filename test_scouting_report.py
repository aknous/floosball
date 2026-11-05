"""Prospect scouting reports (owner, 2026-11-04): judged against the starters at the
prospect's own position, from the public projection, prospects only, no numbers in text.

Run: .venv/bin/python -m pytest -q test_scouting_report.py
"""
import logging
import random
import re
from types import SimpleNamespace

import numpy as np

import scouting_report as sr
from managers.playerManager import PlayerManager

logging.disable(logging.CRITICAL)


def _players(n, seed):
    random.seed(seed)
    np.random.seed(seed)
    pm = PlayerManager.__new__(PlayerManager)
    pm.activePlayers = []
    pm.unusedNames = [f'P{i}' for i in range(5000)]
    pm.db_session = None
    pm.serviceContainer = SimpleNamespace(getService=lambda name: SimpleNamespace(teams=[None] * 32))
    return pm._generateRookieClass(n)


def _league():
    starters = _players(3, 11)
    for s in starters:
        s.is_upcoming_rookie = False
        s.is_prospect = False
        s.team = SimpleNamespace(name='Team')
    prospects = _players(1, 12)
    for p in prospects:
        p.is_upcoming_rookie = True
    return starters, prospects


def test_only_prospects_get_a_report():
    starters, prospects = _league()
    tables = sr.buildPeerTables(starters + prospects)
    assert sr.scoutingReport(starters[0], tables) is None
    assert sr.scoutingReport(prospects[0], tables) is not None


def test_prospects_are_not_their_own_peers():
    starters, prospects = _league()
    with_prospects = sr.buildPeerTables(starters + prospects)
    assert with_prospects == sr.buildPeerTables(starters)


def test_no_numbers_and_the_same_report_every_time():
    starters, prospects = _league()
    tables = sr.buildPeerTables(starters)
    for p in prospects:
        rep = sr.scoutingReport(p, tables)
        text = ' '.join([t['phrase'] for t in rep['strengths'] + rep['weaknesses']]
                        + [rep['growth'] or ''])
        # Star counts are words in a range ("a 3 to 4-star"); no rating number appears.
        assert not re.search(r'\d{2}', text), text
        assert sr.scoutingReport(p, tables) == rep


def test_strengths_lead_with_the_position_and_cap_each_side():
    starters, prospects = _league()
    tables = sr.buildPeerTables(starters)
    for p in prospects:
        rep = sr.scoutingReport(p, tables)
        sides = [t['side'] for t in rep['strengths']]
        assert sides == sorted(sides, key=['offense', 'defense', 'mental'].index), sides
        for side, cap in sr.STRENGTHS_PER_SIDE.items():
            assert sides.count(side) <= cap
        assert all([t['side'] for t in rep['weaknesses']].count(s) <= 1 for s in sr.STRENGTHS_PER_SIDE)


def test_a_strength_is_judged_against_the_players_own_position():
    """The same arm reads differently against weak and strong starters."""
    starters, prospects = _league()
    qb = next(p for p in prospects if p.position.name == 'QB')
    weak = {('QB', 'armStrength'): [50.0] * 20}
    strong = {('QB', 'armStrength'): [99.0] * 20}
    top = sr.scoutingReport(qb, weak)
    bottom = sr.scoutingReport(qb, strong)
    assert any(t['trait'] == 'armStrength' for t in top['strengths'])
    assert any(t['trait'] == 'armStrength' for t in bottom['weaknesses'])


def test_the_lean_follows_the_projected_sides():
    """Owner, 2026-11-04: say whether a prospect projects to help most on offense, on
    defense, or both. Kickers have no defense and no lean."""
    starters, prospects = _league()
    tables = sr.buildPeerTables(starters)
    for p in prospects:
        rep = sr.scoutingReport(p, tables)
        if p.position.name == 'K':
            assert rep['lean'] is None
            continue
        d = p.projectionDetail(0.0)
        gap = d['offense'][1] - d['defense'][1]
        want = 'offense' if gap >= sr.LEAN_GAP else 'defense' if gap <= -sr.LEAN_GAP else 'two_way'
        assert rep['lean'] == want, (p.name, gap, rep['lean'])


def test_stars_per_side():
    """Owner, 2026-11-04: projected stars for overall, offense and defense. Kickers have no
    defense."""
    starters, prospects = _league()
    tables = sr.buildPeerTables(starters)
    for p in prospects:
        rep = sr.scoutingReport(p, tables)
        for side in ('overall', 'offense'):
            lo, hi = rep['stars'][side]
            assert 1 <= lo <= hi <= 5, (side, lo, hi)
        if p.position.name == 'K':
            assert rep['stars']['defense'] is None
        else:
            lo, hi = rep['stars']['defense']
            assert 1 <= lo <= hi <= 5
