"""Payroll (docs/TREASURY_PAYROLL_PLAN.md §5): the salary curve, the budget check, the
forced-cut chooser and the payment run paying players before facilities."""
import unittest
from types import SimpleNamespace

from managers import payroll
from managers.facilitiesManager import resolvePaymentRun, upkeepCostFloobits

UNIT = 5000.0


def _player(rating, pos='QB', term=2, salary=0, pid=None):
    return SimpleNamespace(playerRating=rating, position=SimpleNamespace(name=pos),
                           termRemaining=term, salary=salary, id=pid or id(object()),
                           willRetire=False)


class SalaryCurveTests(unittest.TestCase):
    def setUp(self):
        payroll.setShareUnit(UNIT)

    def testConvexInRating(self):
        a, b, c = (payroll.askingSalary(_player(r)) for r in (78, 86, 94))
        self.assertGreater(c - b, b - a)          # each point costs more than the last
        self.assertGreater(payroll.askingSalary(_player(95)),
                           2 * payroll.askingSalary(_player(78)) * 3)

    def testMinimumFloor(self):
        self.assertEqual(payroll.askingSalary(_player(55)), payroll.minimumSalary())
        self.assertEqual(payroll.minimumSalary(), int(round(0.01 * UNIT)))

    def testKickerAsksLessThanQuarterback(self):
        self.assertLess(payroll.askingSalary(_player(92, 'K')),
                        payroll.askingSalary(_player(92, 'QB')))

    def testProspectContractIsCheap(self):
        full = payroll.askingSalary(_player(90))
        cheap = payroll.askingSalary(_player(90), prospect=True)
        self.assertLess(cheap, full / 2)
        self.assertGreaterEqual(cheap, payroll.minimumSalary())

    def testTracksTheShareUnit(self):
        p = _player(90)
        self.assertAlmostEqual(payroll.askingSalary(p, unit=2 * UNIT),
                               2 * payroll.askingSalary(p, unit=UNIT), delta=2)


class BudgetTests(unittest.TestCase):
    def testFirstRunHasOnlyTheBalance(self):
        # 1,000F balance, no income: a 1,200F one-season deal does not fit.
        self.assertLess(payroll.maxAffordable([], 1, 1000, 0, 0), 1200)
        self.assertEqual(payroll.maxAffordable([], 1, 1000, 0, 0), 1000)

    def testLaterSeasonsAddIncome(self):
        # A 3-season deal: season s needs salary*s <= 1000 + 800*(s-1).
        # s=1: 1000, s=2: 900, s=3: 866 -> room 866.
        self.assertEqual(payroll.maxAffordable([], 3, 1000, 800, 0), 866)

    def testUpkeepCounts(self):
        self.assertEqual(payroll.maxAffordable([], 1, 1000, 0, 300), 700)
        self.assertEqual(payroll.maxAffordable([], 1, 1000, 0, 300, includeUpkeep=False), 1000)

    def testStandingContractsCount(self):
        # With no income the standing 400F deal needs 800F over its two seasons.
        self.assertEqual(payroll.maxAffordable([(400, 2)], 1, 1000, 0, 0), 200)
        self.assertEqual(payroll.maxAffordable([(400, 1)], 1, 1000, 0, 0), 600)
        self.assertFalse(payroll.fits([(600, 2)], 1000, 0, 0))      # 1,200 by season 2
        self.assertTrue(payroll.fits([(600, 2)], 1000, 300, 0))

    def testPreDecrementSchedule(self):
        team = SimpleNamespace(rosterDict={'qb': _player(90, term=3, salary=500),
                                           'rb': _player(80, 'RB', term=1, salary=200)})
        # Before the decrement a 3-season contract has 2 runs left; a walk-year one none.
        self.assertEqual(payroll.schedule(team, preDecrement=True), [(500, 2)])
        self.assertEqual(payroll.nextSeasonPayroll(team), 500)


class ForcedCutTests(unittest.TestCase):
    def _e(self, name, salary, value, protected=False):
        return {'player': name, 'salary': salary, 'value': value, 'protected': protected}

    def _names(self, cuts):
        return sorted(e['player'] for e in cuts)

    def testFewestPlayersFirst(self):
        es = [self._e('a', 600, 50), self._e('b', 300, 10), self._e('c', 300, 10)]
        self.assertEqual(self._names(payroll.chooseForcedCuts(es, 550)), ['a'])

    def testLeastValueAmongEqualCounts(self):
        es = [self._e('a', 600, 50), self._e('b', 600, 20)]
        self.assertEqual(self._names(payroll.chooseForcedCuts(es, 500)), ['b'])

    def testNoGapNoCuts(self):
        self.assertEqual(payroll.chooseForcedCuts([self._e('a', 600, 50)], 0), [])

    def testProtectedOnlyAsALastResortLeastValuableFirst(self):
        es = [self._e('u', 100, 5), self._e('star', 3000, 90, True),
              self._e('fan', 2000, 60, True)]
        # Unprotected alone (100) cannot close 1,500: add the cheaper-valued protected
        # (fan, 2,000) and then drop the unprotected player, no longer needed.
        self.assertEqual(self._names(payroll.chooseForcedCuts(es, 1500)), ['fan'])

    def testNoUnneededProtectedCuts(self):
        # A cheap star-track prospect (value 30) is cut first, not enough; then the top
        # player (value 90) closes it alone, so the prospect is kept back.
        es = [self._e('prospect', 100, 30, True), self._e('top', 3000, 90, True)]
        self.assertEqual(self._names(payroll.chooseForcedCuts(es, 2500)), ['top'])

    def testGrandfatheredContractsAreNotCut(self):
        es = [self._e('old', 0, 1), self._e('paid', 500, 80)]
        self.assertEqual(self._names(payroll.chooseForcedCuts(es, 400)), ['paid'])


class PaymentRunTests(unittest.TestCase):
    def testPayrollIsPaidBeforeUpkeep(self):
        facilities = [{'key': 'stadium', 'level': 3, 'upkeep_funded': 0}]
        upkeep = upkeepCostFloobits(3, UNIT)
        res = resolvePaymentRun(facilities, [], treasury=1000, shareUnit=UNIT, payroll=900)
        self.assertEqual(res['payrollPaid'], 900)
        self.assertEqual(res['payrollShort'], 0)
        self.assertGreater(upkeep, 100)
        self.assertEqual(res['facilities'][0]['level'], 2)        # unpaid, decays
        self.assertEqual(res['leftover'], 100)

    def testShortfallNeverGoesNegative(self):
        res = resolvePaymentRun([], [], treasury=300, shareUnit=UNIT, payroll=500)
        self.assertEqual(res['payrollPaid'], 300)
        self.assertEqual(res['payrollShort'], 200)
        self.assertEqual(res['leftover'], 0)


class ContractTermTests(unittest.TestCase):
    def testSeededTermIsStable(self):
        from managers.playerManager import PlayerManager
        pm = PlayerManager.__new__(PlayerManager)
        pm.db_session = None
        p = SimpleNamespace(id=77, playerTier=None, seasonsPlayed=4,
                            attributes=SimpleNamespace(longevity=10))
        import floosball_player as FP
        p.playerTier = FP.PlayerTier.TierB
        terms = {payroll.contractTerm(pm, p, 9) for _ in range(5)}
        self.assertEqual(len(terms), 1)


if __name__ == '__main__':
    unittest.main()
