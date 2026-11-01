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
def _clean():
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


def test_theFirstFundedSeasonSignsForNothing():
    payroll.markFundedSeasonStarted(13)
    assert not payroll.salariesActive()
    assert payroll.stampSalary(_player()) == 0
    assert SeasonManager._resignLimitOn()


def test_salariesStartWhenThatSeasonEnds():
    payroll.markFundedSeasonStarted(13)
    assert payroll.markSalariesStartIfDue(12) is False     # an earlier season ending
    assert not payroll.salariesActive()
    assert payroll.markSalariesStartIfDue(13) is True
    assert payroll.salariesActive()
    assert payroll.stampSalary(_player()) > 0
    assert not SeasonManager._resignLimitOn()
    assert payroll.markSalariesStartIfDue(14) is False     # stamped once


def test_onlyTheFirstFundedSeasonIsKept():
    payroll.markFundedSeasonStarted(13)
    payroll.markFundedSeasonStarted(14)
    assert payroll._readSetting(payroll.FIRST_FUNDED_KEY) == '13'


def test_noFundedSeasonMeansNoStart():
    assert payroll.markSalariesStartIfDue(13) is False
    assert not payroll.salariesActive()
