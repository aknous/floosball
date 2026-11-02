"""A season that rolled over under the old code before the treasury and prospect changes
shipped (owner, 2026-11-02: season 13 rolled over a few hours before the deploy).

Two pieces of its start-of-season setup differ and are fixed once on boot:
  - its funding paid the flat FUNDING_BASELINE_PER_TEAM, not the share baseline;
  - its draft class was generated without hidden talent.

Run: .venv/bin/python -m pytest -q test_rollover_handoff.py
"""
import os
import sys
import tempfile
from types import SimpleNamespace

HERE = os.path.dirname(os.path.abspath(__file__))
os.environ['DATABASE_DIR'] = tempfile.mkdtemp(prefix='floo_rollover_')
sys.path.insert(0, HERE)
import logging
logging.disable(logging.CRITICAL)

from constants import FUNDING_BASELINE_PER_TEAM
from database.connection import init_db, get_session
from database.models import AppSetting, TeamFunding, TeamTreasury

init_db()
from managers.seasonManager import SeasonManager  # noqa: E402

FLAT = int(FUNDING_BASELINE_PER_TEAM)


def _sm(playerManager=None):
    sm = SeasonManager.__new__(SeasonManager)
    sm.playerManager = playerManager
    return sm


def _fund(session, teamId, season, baseline, treasury):
    session.add(TeamFunding(team_id=teamId, season=season, baseline_funding=baseline,
                            fan_contributions=0, current_funding=baseline, carried_funding=50,
                            effective_funding=baseline + 50, tier_locked_funding=baseline + 50))
    session.add(TeamTreasury(team_id=teamId, balance=treasury))
    session.commit()


def test_aFlatBaselineSeasonIsToppedUpOnce():
    s = get_session()
    _fund(s, 1, 13, FLAT, 1000)
    _fund(s, 2, 13, FLAT, 300)
    sm = _sm()
    sm._topUpFlatBaseline(s, 13, 1460)
    sm._topUpFlatBaseline(s, 13, 1460)          # a second boot adds nothing
    s.expire_all()
    assert s.query(TeamTreasury).filter_by(team_id=1).one().balance == 1000 + 1460 - FLAT
    assert s.query(TeamTreasury).filter_by(team_id=2).one().balance == 300 + 1460 - FLAT
    row = s.query(TeamFunding).filter_by(team_id=1, season=13).one()
    assert (row.baseline_funding, row.current_funding, row.effective_funding) == (1460, 1460, 1510)
    s.close()


def test_aSeasonTheNewCodeCreatedIsLeftAlone():
    s = get_session()
    _fund(s, 3, 14, 1460, 900)
    _sm()._topUpFlatBaseline(s, 14, 1460)
    s.expire_all()
    assert s.query(TeamTreasury).filter_by(team_id=3).one().balance == 900
    s.close()


class _P:
    def __init__(self, pid, shift=0):
        self.id, self.talentShift, self.applied = pid, shift, []

    def shiftTalent(self, points):
        self.applied.append(points)


def test_aLegacyClassGetsHiddenTalentOnceAndKeepsAnyItHas():
    draws = iter([5, -9, 3, 7, 7, 7])
    saved = []
    pm = SimpleNamespace(drawTalentShift=lambda: next(draws), savePlayerData=lambda: saved.append(1))
    sm = _sm(pm)
    rookies = [_P(1), _P(2), _P(3, shift=4)]
    sm._drawTalentForLegacyClass(rookies, 13)
    assert [r.talentShift for r in rookies] == [5, -9, 4]
    assert rookies[2].applied == []
    sm._drawTalentForLegacyClass(rookies, 13)    # a restart draws nothing more
    assert [r.applied for r in rookies] == [[5], [-9], []] and len(saved) == 1
    s = get_session()
    assert s.query(AppSetting).filter_by(key=SeasonManager.TALENT_CLASS_KEY).one().value == '13'
    s.close()


def test_aClassTheNewCodeGeneratedIsNotDrawnAgain():
    pm = SimpleNamespace(drawTalentShift=lambda: 6, savePlayerData=lambda: None)
    sm = _sm(pm)
    sm._writeTalentClassMarker(14)
    r = _P(1)
    sm._drawTalentForLegacyClass([r], 14)
    assert r.applied == [] and r.talentShift == 0


class _GrowPM:
    def __init__(self, size):
        self.size, self.activePlayers, self.saved, self.calls = size, [], 0, []

    def rookieClassSize(self):
        return self.size

    def _generateRookieClass(self, season, count=None):
        self.calls.append(count)
        return [_P(1000 + i + 100 * len(self.calls)) for i in range(count)]

    def addToPositionList(self, p):
        pass

    def sortPlayersByPosition(self):
        pass

    def savePlayerData(self):
        self.saved += 1


def test_aShortLegacyClassGrowsToFullSizeOnce():
    pm = _GrowPM(48)
    sm = _sm(pm)
    existing = [_P(i) for i in range(32)]
    sm._growLegacyClass(existing, 13)
    assert pm.calls == [16]
    added = [p for p in pm.activePlayers]
    assert len(added) == 16 and all(p.is_upcoming_rookie and p.team == 'Upcoming Rookie' for p in added)
    sm._growLegacyClass(existing + added, 13)    # a restart: full, and marked
    sm._growLegacyClass(existing, 13)            # even if the save had been lost
    assert pm.calls == [16] and pm.saved == 1


def test_aFullClassIsLeftAlone():
    pm = _GrowPM(48)
    _sm(pm)._growLegacyClass([_P(i) for i in range(48)], 14)
    assert pm.calls == []
