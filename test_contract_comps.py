"""Comparable contracts set asking salaries (owner, 2026-11-01).

"if a player signs for that high of a price, shouldnt that drive prices for other players?
right now in actual free agent markets, contracts are based on what a comparable player
recently received. this should be an incentive to not overspend because that will make
players more expensive"

A player's asking salary is the curve price times `payroll.marketRate`: recent contracts at
his position and a similar rating, as salary over the curve price, shrunk toward 1.0 and
capped. An overpay raises comparable players' prices; a discount lowers them.

Run: .venv/bin/python -m pytest -q test_contract_comps.py
"""
from types import SimpleNamespace

import pytest

from managers import payroll
import constants


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    monkeypatch.setattr(payroll, '_comps', [])
    monkeypatch.setattr(payroll, '_pendingContracts', [])
    monkeypatch.setattr(payroll, '_compSeason', 0)
    monkeypatch.setattr(payroll, 'salariesActive', lambda: True)
    payroll.setShareUnit(5000)


def _p(rating, pos='WR', pid=1):
    return SimpleNamespace(id=pid, playerRating=rating, position=SimpleNamespace(name=pos))


def test_withNoComparablesTheAskIsTheCurvePrice():
    p = _p(88)
    assert payroll.askingSalary(p) == payroll.baseAskingSalary(p)


def test_anOverpayRaisesComparablePlayersAndNoOneElse():
    star = _p(90, pid=1)
    payroll.recordContract(star, 2 * payroll.baseAskingSalary(star), 'market', 13)
    near, far, otherPos = _p(89, pid=2), _p(80, pid=3), _p(90, 'QB', pid=4)
    assert payroll.askingSalary(near) > payroll.baseAskingSalary(near)
    assert payroll.askingSalary(far) == payroll.baseAskingSalary(far)        # 10 points away
    assert payroll.askingSalary(otherPos) == payroll.baseAskingSalary(otherPos)


def test_oneContractMovesThePriceOnlyPartWay():
    # Shrunk toward the curve by FA_COMP_PRIOR contracts at exactly the curve price.
    star = _p(90)
    payroll.recordContract(star, 2 * payroll.baseAskingSalary(star), 'market', 13)
    expected = (constants.FA_COMP_PRIOR + 2.0) / (constants.FA_COMP_PRIOR + 1.0)
    assert payroll.marketRate('WR', 90) == pytest.approx(expected)


def test_aDiscountLowersThePriceAndTheRateIsCapped():
    for i in range(30):
        payroll.recordContract(_p(85, pid=i), int(0.3 * payroll.baseAskingSalary(_p(85))), 'fill', 13)
    assert payroll.marketRate('WR', 85) == pytest.approx(constants.FA_COMP_MIN)
    for i in range(60):
        payroll.recordContract(_p(92, pid=100 + i), 5 * payroll.baseAskingSalary(_p(92)), 'market', 13)
    assert payroll.marketRate('WR', 92) == pytest.approx(constants.FA_COMP_MAX)


def test_lastOffseasonCountsLess():
    payroll.recordContract(_p(90, pid=1), 2 * payroll.baseAskingSalary(_p(90)), 'market', 12)
    old = payroll.marketRate('WR', 90)
    payroll._compSeason = 13
    assert 1.0 < payroll.marketRate('WR', 90) < old


def test_aProspectDealIgnoresComparables():
    star = _p(90)
    payroll.recordContract(star, 2 * payroll.baseAskingSalary(star), 'market', 13)
    prospect = _p(90, pid=9)
    assert payroll.askingSalary(prospect, prospect=True) == max(
        payroll.minimumSalary(), round(payroll.baseAskingSalary(prospect) * constants.SALARY_PROSPECT_FRACTION))


def test_aMarketAskCapsThePriceForTheFillStep():
    p = _p(95)
    p._marketAsk = 1000
    assert payroll.askingSalary(p) == 1000
    p._marketAsk = None
    assert payroll.askingSalary(p) == payroll.baseAskingSalary(p)


def test_nothingIsRecordedBeforeSalariesStart(monkeypatch):
    monkeypatch.setattr(payroll, 'salariesActive', lambda: False)
    payroll.recordContract(_p(90), 5000, 'market', 13)
    assert payroll._comps == [] and payroll._pendingContracts == []
