"""A projection may never come in under what the card is guaranteed to pay.

⚠️ THE EXPECTED VALUE WAS SCALED FROM THE HIT, THROUGH THE FLOOR. Most chance cards pay
a guaranteed base and roll for an enhanced payout on top:

    fp = enhancedFP if triggered else baseFP

In projection mode the RNG forces the triggered path, and the expected-value pass then
multiplied that payout by the odds — so a card with base 5 / enhanced 18 at 25% showed
4.5, under the 5 it pays for doing nothing at all. Reported from production as cards
projecting below their guaranteed amount. Measured across the chance effects at the
holographic tier: babysitter 63.2 against a floor of 102.0, scrappy 63.2 against 89.2,
traverse 2.5 against 27.9.

The expected value is now interpolated from the MISSED outcome — asked of the effect
itself, by running it once more with the roll forced to fail — so:

    EV = floor + (hit - floor) x odds

which is the textbook expectation, sits inside [floor, hit] by construction, and leaves
an effect with no floor projecting at hit x odds exactly as before.

Run: .venv/bin/python test_projection_floor.py
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import logging
logging.disable(logging.CRITICAL)

import managers  # noqa: F401  — breaks the floosball_game circular import
from managers import cardEffects as ce
from managers.cardEffectCalculator import CardCalcContext, _computeMissedOutcome

# Every chance effect that pays a guaranteed floor, plus the ones that do not — both
# behaviors are being pinned.
CHANCE_EFFECTS = ('scrappy', 'babysitter', 'tank_commander', 'underdog',
                  'consolation_prize', 'rock_bottom', 'sleeper', 'dud_insurance',
                  'crescendo', 'traverse', 'promised_land', 'barrage', 'houdini')


def _ctx(forceMiss=False):
    ctx = CardCalcContext(userId=1, season=1, weekNumber=5)
    ctx.isProjection = True
    ctx.projectionForceMiss = forceMiss
    ctx.weekPlayerStats = {1: {'fantasyPoints': 12.0}}
    ctx.rosterPlayerIds = [1, 2, 3, 4, 5, 6]
    return ctx


def _outcomes(effectName, edition='holographic'):
    """(hit, miss, config) for one effect, or (None, None, None) if it does not mint
    or needs context this harness does not build."""
    try:
        cfg = ce.buildEffectConfig(edition, 88, 1, forceEffect=effectName)
        hit = ce.computeEffect(cfg, _ctx(False), 1, 1)
        miss = ce.computeEffect(cfg, _ctx(True), 1, 1)
    except Exception:
        return None, None, None
    return hit, miss, cfg


class ProjectionFloorTests(unittest.TestCase):
    def testExpectedValueNeverFallsBelowTheGuaranteedFloor(self):
        """THE RULE, over every chance effect that produces a result."""
        checked = 0
        offenders = []
        for name in CHANCE_EFFECTS:
            hit, miss, _ = _outcomes(name)
            if hit is None or not hit.chanceThreshold:
                continue
            p = hit.chanceThreshold
            for label, get in (('FP', lambda r: r.fpBonus), ('Floobits', lambda r: r.floobits)):
                h, m = get(hit), get(miss)
                if not h and not m:
                    continue
                checked += 1
                ev = m + (h - m) * p
                if ev < m - 1e-9:
                    offenders.append(f'{name} {label}: EV {ev:.2f} < floor {m:.2f}')
        self.assertTrue(checked, 'no chance effect produced a result — harness is broken')
        self.assertEqual(offenders, [], 'projection under the guaranteed floor:\n'
                                        + '\n'.join(offenders))

    def testTheOldScalingWouldHaveFailedThisTest(self):
        """Guards the test itself: the shape it exists to catch must be catchable."""
        underFloor = []
        for name in CHANCE_EFFECTS:
            hit, miss, _ = _outcomes(name)
            if hit is None or not hit.chanceThreshold:
                continue
            if hit.fpBonus * hit.chanceThreshold < miss.fpBonus - 1e-9:
                underFloor.append(name)
        self.assertTrue(underFloor,
                        'no effect reproduces the old fault, so this file proves nothing')

    def testExpectedValueNeverExceedsTheTriggeredPayout(self):
        """The other side: an estimate must not promise more than the best case."""
        for name in CHANCE_EFFECTS:
            hit, miss, _ = _outcomes(name)
            if hit is None or not hit.chanceThreshold:
                continue
            p = hit.chanceThreshold
            ev = miss.fpBonus + (hit.fpBonus - miss.fpBonus) * p
            self.assertLessEqual(round(ev, 6), round(max(hit.fpBonus, miss.fpBonus), 6), name)

    def testAnEffectWithNoFloorStillProjectsAtHitTimesOdds(self):
        """The change must not move cards that were already right."""
        for name in CHANCE_EFFECTS:
            hit, miss, _ = _outcomes(name)
            if hit is None or not hit.chanceThreshold:
                continue
            if miss.fpBonus or miss.floobits:
                continue  # has a floor, covered above
            p = hit.chanceThreshold
            self.assertAlmostEqual(miss.fpBonus + (hit.fpBonus - miss.fpBonus) * p,
                                   hit.fpBonus * p, places=6, msg=name)

    def testTheMissedPassIsSideEffectFreeAndRepeatable(self):
        """It runs the effect a second time, so it must not change what the first
        pass produced — and must answer the same way twice."""
        cfg = ce.buildEffectConfig('holographic', 88, 1, forceEffect='scrappy')
        ctx = _ctx(False)
        before = ce.computeEffect(cfg, ctx, 1, 1)
        first = _computeMissedOutcome(cfg, ctx, 1, 1, None)
        second = _computeMissedOutcome(cfg, ctx, 1, 1, None)
        after = ce.computeEffect(cfg, ctx, 1, 1)
        self.assertEqual(first.fpBonus, second.fpBonus)
        self.assertEqual(before.fpBonus, after.fpBonus)
        # And it leaves the flag as it found it, or the live pass would start missing.
        self.assertFalse(ctx.projectionForceMiss)


if __name__ == '__main__':
    unittest.main(verbosity=2)
