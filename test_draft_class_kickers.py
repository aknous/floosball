"""The prospect ranking leaves kickers unranked (owner, 2026-11-20).

No rookie-draft pick takes a kicker while another rookie is left, and every undrafted
kicker becomes a free agent, so a numbered spot would promise a pick that never comes.
`/api/draft/class` lists kickers after everyone else with `rank` None and
`headedToFreeAgency` True; everyone else keeps the ranking order, numbered from 1.

Run: .venv/bin/python -m pytest -q test_draft_class_kickers.py
"""
import os
import sys
import tempfile
from types import SimpleNamespace

HERE = os.path.dirname(os.path.abspath(__file__))
os.environ['DATABASE_DIR'] = tempfile.mkdtemp(prefix='floo_classk_')
sys.path.insert(0, HERE)
import logging
logging.disable(logging.CRITICAL)

from database.connection import init_db
init_db()
import api.main as api  # noqa: E402
from fastapi import Response  # noqa: E402


def _prospect(pid, pos, rating):
    return SimpleNamespace(id=pid, name=f'P{pid}', position=SimpleNamespace(name=pos),
                           playerRating=rating)


def test_kickersFollowEveryoneElseUnranked(monkeypatch):
    # The public ranking as prospectRanking would return it, a kicker 2nd.
    ranked = [_prospect(1, 'WR', 90), _prospect(2, 'K', 85), _prospect(3, 'QB', 80),
              _prospect(4, 'K', 70), _prospect(5, 'RB', 72)]
    api.floosball_app = SimpleNamespace(
        playerManager=SimpleNamespace(prospectRanking=lambda: ranked, activePlayers=[]),
        seasonManager=SimpleNamespace(currentSeason=SimpleNamespace(seasonNumber=15, currentWeek=0)))
    monkeypatch.setattr(api, '_prospectProjection', lambda p: None)
    monkeypatch.setattr(api, '_viewingClubFor', lambda user: None)
    out = api.get_draft_class(Response(), user=None)
    rows = out['data']['prospects'] if 'data' in out else out['prospects']
    assert [r['playerId'] for r in rows] == [1, 3, 5, 2, 4]
    assert [r['rank'] for r in rows] == [1, 2, 3, None, None]
    assert [r['headedToFreeAgency'] for r in rows] == [False, False, False, True, True]
