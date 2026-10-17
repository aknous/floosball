"""Admin name tools: view the unused pool, and check a new name against every name in the
league before adding it, so the pool does not fill with near-duplicates (owner, 2026-10-16).

Run: .venv/bin/python -m pytest -q test_name_similarity.py
"""
import logging
import sys
import types

logging.disable(logging.CRITICAL)

if 'floosball_game' not in sys.modules:
    _stub = types.ModuleType('floosball_game')
    _stub.Game = type('G', (), {})
    sys.modules['floosball_game'] = _stub
    import managers.timingManager  # noqa: F401
    del sys.modules['floosball_game']

import pytest
from fastapi.testclient import TestClient

import api.main as M
from name_similarity import NameIndex, nameSimilarity, normalizeName


def test_normalizing_reads_the_lineage_not_the_spelling():
    assert normalizeName('  Freed   Marinara Jr. ') == 'freed marinara'
    assert normalizeName('José Pérez III') == 'jose perez'


def test_the_threshold_catches_near_names_and_leaves_shared_surnames():
    assert nameSimilarity('Bob Smith', 'Rob Smith') >= 0.8
    assert nameSimilarity('Smith John', 'John Smith') == 1.0
    assert nameSimilarity('Bob Smith', 'Al Smith') < 0.8
    assert nameSimilarity('Bob Smith', 'Tom Jones') < 0.8


def test_the_index_ranks_and_tags_matches():
    idx = NameIndex([('Thunder Princess', 'pool'), ('Thunder Prince', 'player'),
                     ('Onions Rodger', 'coach')])
    out = idx.similarTo('Thunder Princes')
    assert sorted(m['source'] for m in out) == ['player', 'pool']
    assert idx.similarTo('Onions Rodger')[0]['sameLineage'] is True
    assert idx.similarTo('Onions Rodger', exclude={'Onions Rodger'}) == []


class _FakePM:
    def __init__(self):
        self.unusedNames = ['Thunder Princess', 'Bleeb Refurb Jr.']
        self.pendingNames = [('Scorch Jumpman', 12)]
        self.name_repo = None
        self.db_session = None

    def isNameInUse(self, name):
        return name == 'Torque Manderlay'


@pytest.fixture
def client(monkeypatch):
    pm = _FakePM()
    monkeypatch.setattr(M, 'floosball_app', types.SimpleNamespace(playerManager=pm))
    monkeypatch.setattr(M, '_leagueNames', lambda pm, includeSuggested=False: (
        [(n, 'pool') for n in pm.unusedNames] + [(n, 'held') for n, _ in pm.pendingNames]
        + [('Torque Manderlay', 'player'), ('Subray Wizzbang II', 'player'),
           ('August Jerrica', 'retired')]))
    monkeypatch.setattr(M, '_recordCuratedNames', lambda *a, **k: None)
    M.app.dependency_overrides[M._checkAdminAuth] = lambda: None
    yield TestClient(M.app), pm
    M.app.dependency_overrides.pop(M._checkAdminAuth, None)


def test_the_pool_is_listed_alphabetically_with_held_names(client):
    c, _ = client
    d = c.get('/api/admin/names/pool').json()
    assert d['names'] == ['Bleeb Refurb Jr.', 'Thunder Princess']
    assert d['held'] == [{'name': 'Scorch Jumpman', 'availableSeason': 12}]


def test_check_reports_each_name_without_adding_it(client):
    c, pm = client
    res = {r['name']: r for r in c.post('/api/admin/names/check', json={'names': [
        'Tounder Princess', 'Bleeb Refurb', 'Torque Manderlay', 'Subray Wizzbang',
        'Auguste Jerrica', 'Wholly Novel', 'Wholly Novell']}).json()['results']}
    assert res['Tounder Princess']['status'] == 'similar'
    assert res['Bleeb Refurb']['status'] == 'blocked'       # same lineage as a pooled name
    assert res['Torque Manderlay']['status'] == 'blocked'   # worn by a live player
    assert res['Subray Wizzbang']['status'] == 'blocked'    # a live player's lineage
    assert res['Auguste Jerrica']['matches'][0]['source'] == 'retired'
    assert res['Wholly Novel']['matches'][0]['source'] == 'batch'
    assert pm.unusedNames == ['Thunder Princess', 'Bleeb Refurb Jr.']


def test_adding_refuses_a_lineage_already_in_the_pool_or_on_the_field(client):
    c, pm = client
    d = c.post('/api/admin/names', json={'names': [
        'Bleeb Refurb', 'Scorch Jumpman Jr.', 'Subray Wizzbang', 'Brand New']}).json()
    assert d['rejectedInPool'] == ['Bleeb Refurb', 'Scorch Jumpman Jr.']
    assert d['rejectedInUse'] == ['Subray Wizzbang']
    assert pm.unusedNames[-1] == 'Brand New' and d['added'] == 1
