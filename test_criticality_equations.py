"""Regression: each Core's Criticality equation amplifies its own term, by a bounded K.

⚠️ THE OLD EQUATIONS ALL AMPLIFIED FPx, THREE OF THEM SUPER-LINEARLY (owner, 2026-10-07).
Pyre was (R+F)·e^M, Aris Γ(M+1), Cassian M·(M+1), Halverson M². Criticality weeks (1-5 a
season) supplied 55-99% of a top-3 finisher's season, one Pyre week ran 335x a normal week,
and the best strategy was "stack FPx and wait for Pyre". Now Pyre amplifies FPx, Cassian
card flat FP, Halverson roster FP, Aris all three gently, each by CRITICALITY_AMPLIFICATION.

And every weekly modifier is neutralized on a Criticality week (modifierInForce): Amplify +
Pyre produced a 1.47M-point season, and Grounded zeroed FPx on three Criticality weeks.

Run: python3 test_criticality_equations.py
"""
import os
import unittest
from unittest import mock

from constants import CRITICALITY_AMPLIFICATION as K
from managers.coreEquations import applyCoreEquation, equationTemplate, modifierInForce

CORES = ("pyre", "cassian", "halverson", "aris")


def ratio(core, R, F, mults):
    base, _ = applyCoreEquation(None, R, F, mults)
    out, _ = applyCoreEquation(core, R, F, mults)
    return out / base


class EachCoreOwnsATerm(unittest.TestCase):

    def testPyreOnlyAmplifiesFPx(self):
        self.assertAlmostEqual(ratio("pyre", 100, 150, []), 1.0)
        self.assertGreater(ratio("pyre", 100, 150, [2.0]), 1.0)

    def testCassianOnlyAmplifiesCardFlatFP(self):
        self.assertAlmostEqual(ratio("cassian", 100, 0, [1.5]), 1.0)
        self.assertGreater(ratio("cassian", 100, 150, [1.5]), 1.0)

    def testHalversonOnlyAmplifiesRosterFP(self):
        self.assertAlmostEqual(ratio("halverson", 0, 150, [1.5]), 1.0)
        self.assertGreater(ratio("halverson", 100, 150, [1.5]), 1.0)

    def testEachCoreFavorsADifferentBuild(self):
        """The point of the change: no single build wins every Criticality."""
        builds = {"fpx": (60, 20, [2.5, 2.0, 1.8]), "flat": (60, 400, []),
                  "roster": (200, 10, [])}
        best = {core: max(builds, key=lambda b: ratio(core, *builds[b]))
                for core in ("pyre", "cassian", "halverson")}
        self.assertEqual(best, {"pyre": "fpx", "cassian": "flat", "halverson": "roster"})


class TheBoostIsBounded(unittest.TestCase):

    def testNoCoreExceedsKOnAnyBuild(self):
        for core in CORES:
            for R, F, mults in [(100, 0, [9.0, 9.0]), (0, 500, []), (500, 0, []),
                                (80, 300, [3.0, 2.0]), (1, 1, [50.0])]:
                self.assertLessEqual(ratio(core, R, F, mults), K + 1e-9, (core, R, F, mults))

    def testAFullySpecializedBuildApproachesK(self):
        self.assertAlmostEqual(ratio("cassian", 0, 500, [1.5]), K)
        self.assertAlmostEqual(ratio("halverson", 500, 0, [1.5]), K)
        self.assertGreater(ratio("pyre", 100, 100, [200.0]), K * 0.99)

    def testArisGivesEveryBuildTheSameGentleRange(self):
        lo, hi = K ** (1 / 3), K ** (2 / 3)
        for R, F, mults in [(100, 0, []), (0, 500, []), (80, 300, [3.0, 2.0]), (1, 1, [500.0])]:
            r = ratio("aris", R, F, mults)
            self.assertGreaterEqual(r, lo - 1e-9)
            self.assertLessEqual(r, hi + 1e-9)

    def testTheShownEquationIsTheOneComputed(self):
        for core in CORES:
            out, eqn = applyCoreEquation(core, 100, 150, [1.5, 1.3])
            self.assertTrue(eqn.endswith(f"= {out:.0f}"), eqn)
            self.assertTrue(eqn.startswith(equationTemplate(core)), (eqn, equationTemplate(core)))


class ModifiersAreSuspendedOnACriticalityWeek(unittest.TestCase):

    def testEveryModifierBecomesSteady(self):
        with mock.patch("managers.anomalyManager.getActiveCriticalityCore", return_value="pyre"):
            for mod in ("amplify", "grounded", "frenzy", "payday", "ironclad",
                        "longshot", "synergy", "fortunate"):
                self.assertEqual(modifierInForce(mod, 9, 5), "steady", mod)

    def testAnOrdinaryWeekKeepsItsModifier(self):
        with mock.patch("managers.anomalyManager.getActiveCriticalityCore", return_value=None):
            self.assertEqual(modifierInForce("amplify", 9, 5), "amplify")

    def testEveryScoringPathResolvesThroughIt(self):
        """Three places resolve a week's modifier for scoring (week-end bank, the live
        snapshot, projection). One that skips the check scores a Criticality week with
        the modifier the other two suspended."""
        here = os.path.dirname(os.path.abspath(__file__))
        for rel in ("managers/seasonManager.py", "managers/fantasyTracker.py",
                    "managers/cardProjection.py"):
            with open(os.path.join(here, rel)) as fh:
                self.assertIn("modifierInForce(activeModifier", fh.read(), rel)


class GroundedIsRetired(unittest.TestCase):

    def testItCanNoLongerRoll(self):
        """Owner, 2026-10-07: Grounded zeroed every FPx effect for a week and fell on three
        Criticality weeks. It stays displayable for stored weeks but never rolls."""
        from managers.seasonManager import SeasonManager
        self.assertNotIn("grounded", SeasonManager.MODIFIER_WEIGHTS)
        self.assertIn("grounded", SeasonManager.MODIFIER_DISPLAY)


if __name__ == "__main__":
    unittest.main()
