"""Salaries start after the first funded season (owner, 2026-11-01).

The first season played under the new funding (share-denominated baseline, gate revenue,
the donation match) carries no salaries, so Treasuries are built up before payroll is
first due. Its funding records stamp `payroll.FIRST_FUNDED_KEY`; its season end stamps
`payroll.SALARIES_FROM_KEY`, and from that offseason on contracts carry a salary, the
budget and the season-end check apply, and the re-sign limit is lifted.

Run: .venv/bin/python -m pytest -q test_salary_start.py
"""
import os
import sys
import tempfile
from types import SimpleNamespace

HERE = os.path.dirname(os.path.abspath(__file__))
os.environ['DATABASE_DIR'] = tempfile.mkdtemp(prefix='floo_salary_start_')
sys.path.insert(0, HERE)
import logging
logging.disable(logging.CRITICAL)

import pytest

from database.connection import init_db, get_session
from database.models import AppSetting

init_db()
from managers import payroll  # noqa: E402
from managers.seasonManager import SeasonManager  # noqa: E402


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    # These test how salaries START; charging itself is switched off for now (owner,
    # 2026-11-02), which `test_salariesNeverStartWhileChargingIsOff` covers.
    monkeypatch.setattr(payroll, 'SALARIES_CHARGE_ENABLED', True)
    s = get_session()
    s.query(AppSetting).filter(AppSetting.key.in_(
        [payroll.FIRST_FUNDED_KEY, payroll.SALARIES_FROM_KEY])).delete(synchronize_session=False)
    s.commit()
    s.close()
    payroll.resetSalariesActiveCache()
    payroll.setShareUnit(5000)
    yield
    payroll.resetSalariesActiveCache()


def _player():
    return SimpleNamespace(playerRating=90, position=SimpleNamespace(name='QB'), salary=0)


def _markFunded(season):
    s = get_session()
    payroll.markFundedSeasonStarted(season, s)
    s.commit()
    s.close()


def test_theFirstFundedSeasonSignsForNothing():
    _markFunded(13)
    assert not payroll.salariesActive()
    assert payroll.stampSalary(_player()) == 0
    assert SeasonManager._resignLimitOn()


def test_salariesStartWhenThatSeasonEnds():
    _markFunded(13)
    assert payroll.markSalariesStartIfDue(12) is False     # an earlier season ending
    assert not payroll.salariesActive()
    assert payroll.markSalariesStartIfDue(13) is True
    assert payroll.salariesActive()
    assert payroll.stampSalary(_player()) > 0
    assert not SeasonManager._resignLimitOn()
    assert payroll.markSalariesStartIfDue(14) is False     # stamped once


def test_onlyTheFirstFundedSeasonIsKept():
    _markFunded(13)
    _markFunded(14)
    assert payroll._readSetting(payroll.FIRST_FUNDED_KEY) == '13'


def test_theStampWritesOnTheCallersOpenWrite():
    # The caller holds a pending write; a second session would wait on SQLite's lock.
    from database.models import TeamFunding
    s = get_session()
    s.add(TeamFunding(team_id=1, season=13, baseline_funding=200, fan_contributions=0,
                      current_funding=200, carried_funding=0, effective_funding=200,
                      tier_locked_funding=200))
    s.flush()
    payroll.markFundedSeasonStarted(13, s)
    s.commit()
    s.close()
    assert payroll._readSetting(payroll.FIRST_FUNDED_KEY) == '13'


def test_noFundedSeasonMeansNoStart():
    assert payroll.markSalariesStartIfDue(13) is False
    assert not payroll.salariesActive()


def test_salariesNeverStartWhileChargingIsOff(monkeypatch):
    """Owner, 2026-11-02: the treasury ships, salaries do not. Nothing is stamped toward a
    start and contracts stay unpaid, while the league baseline stays share-denominated."""
    monkeypatch.setattr(payroll, 'SALARIES_CHARGE_ENABLED', False)
    s = get_session()
    payroll.markFundedSeasonStarted(13, s)
    s.commit()
    s.close()
    assert payroll._readSetting(payroll.FIRST_FUNDED_KEY) is None
    assert payroll.markSalariesStartIfDue(13) is False
    payroll.resetSalariesActiveCache()
    assert payroll.salariesActive() is False
    assert payroll.leagueBaseline(5000) == 1250
