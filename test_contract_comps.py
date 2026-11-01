"""Comparable contracts set asking salaries (owner, 2026-11-01).

"if a player signs for that high of a price, shouldnt that drive prices for other players?
right now in actual free agent markets, contracts are based on what a comparable player
recently received. this should be an incentive to not overspend because that will make
players more expensive"

A player's asking salary is the curve price times `payroll.marketRate`: 1 plus the premium
recent market contracts at his position and a similar rating paid over the ask they were
offered against, shrunk toward 1.0 and capped. An overpay raises comparable players' prices,
and prices return to the curve as those contracts age out; nothing compounds.

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
    payroll.recordContract(star, 1400, 'market', 13, ask=1000)        # a 1.4x bidding war
    near, far, otherPos = _p(89, pid=2), _p(80, pid=3), _p(90, 'QB', pid=4)
    assert payroll.askingSalary(near) > payroll.baseAskingSalary(near)
    assert payroll.askingSalary(far) == payroll.baseAskingSalary(far)        # 10 points away
    assert payroll.askingSalary(otherPos) == payroll.baseAskingSalary(otherPos)


def test_oneContractMovesThePriceOnlyPartWay():
    payroll.recordContract(_p(90), 1400, 'market', 13, ask=1000)
    # Shrunk toward 1.0 by FA_COMP_PRIOR contracts at exactly the ask.
    assert payroll.marketRate('WR', 90) == pytest.approx(1.0 + 0.4 / (constants.FA_COMP_PRIOR + 1.0))


def test_anUncontestedSigningLeavesThePriceAlone():
    for i in range(20):
        payroll.recordContract(_p(88, pid=i), 1000, 'market', 13, ask=1000)
    assert payroll.marketRate('WR', 88) == pytest.approx(1.0)


def test_pricesDoNotCompound():
    # A signing at today's raised ask reads as uncontested, so a raised rate does not feed
    # itself; only paying OVER the ask moves it.
    for i in range(10):
        payroll.recordContract(_p(90, pid=i), 1300, 'market', 12, ask=1000)
    raised = payroll.marketRate('WR', 90)
    payroll._compSeason = 13
    for i in range(10):
        ask = 1000 * raised
        payroll.recordContract(_p(90, pid=100 + i), int(round(ask)), 'market', 13, ask=ask)
    assert payroll.marketRate('WR', 90) < raised


def test_theRateIsCapped():
    for i in range(80):
        payroll.recordContract(_p(92, pid=i), 5000, 'market', 13, ask=1000)
    assert payroll.marketRate('WR', 92) == pytest.approx(constants.FA_COMP_MAX)


def test_lastOffseasonCountsLess():
    payroll.recordContract(_p(90, pid=1), 1400, 'market', 12, ask=1000)
    old = payroll.marketRate('WR', 90)
    payroll._compSeason = 13
    assert 1.0 < payroll.marketRate('WR', 90) < old


def test_aProspectDealIgnoresComparables():
    payroll.recordContract(_p(90), 1400, 'market', 13, ask=1000)
    prospect = _p(90, pid=9)
    assert payroll.askingSalary(prospect, prospect=True) == max(
        payroll.minimumSalary(), round(payroll.baseAskingSalary(prospect) * constants.SALARY_PROSPECT_FRACTION))


def test_aMarketAskCapsThePriceForTheFillStep():
    p = _p(95)
    p._marketAsk = 1000
    assert payroll.askingSalary(p) == 1000
    p._marketAsk = None
    assert payroll.askingSalary(p) == payroll.baseAskingSalary(p)


def test_nothingIsRecordedBeforeSalariesStartOrWithoutAnAsk(monkeypatch):
    payroll.recordContract(_p(90), 5000, 'market', 13)                  # no ask: no signal
    monkeypatch.setattr(payroll, 'salariesActive', lambda: False)
    payroll.recordContract(_p(90), 5000, 'market', 13, ask=1000)
    assert payroll._comps == [] and payroll._pendingContracts == []
