"""Honor Roll starts paying exactly where its bar fills.

⚠️ IT USED TO HAVE TWO THRESHOLDS THAT DISAGREED. The power bar unlocked at the gate's
position- and edition-scaled figure — 9 FP for a metallic QB — while the effect's own
ramp was hardcoded to start at 15. Between the two the card sat full, green and reading
ACTIVE while paying +0.00 FPx, which is the exact contradiction the power bar exists to
prevent. A user asked what "up to X FPx on a big game" meant and this is what was
underneath it.

The ramp is the other half of the answer: the bonus is not flat once unlocked, it grows
from zero at the bar to the full figure at DOUBLE the bar, so "a big game" means twice
what it took to switch the card on.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from managers.cardEffects import buildEffectConfig, _computeHonorRoll

QB, RB, WR, TE, K = 1, 2, 3, 4, 5
EDITIONS = ('metallic', 'holographic', 'prismatic', 'diamond')


class Ctx:
    """The slice of the scoring context this effect reads."""

    def __init__(self, playerFP):
        self.weekPlayerStats = {7: {'fantasyPoints': playerFP}}


def cfgFor(edition='metallic', position=QB):
    return buildEffectConfig(edition, 82, position, forceEffect='honor_roll')


class HonorRollTests(unittest.TestCase):
    def testTheRampStartsWhereTheBarFills(self):
        """THE FIX. One threshold, not two."""
        for edition in EDITIONS:
            for position in (QB, RB, WR, TE, K):
                cfg = cfgFor(edition, position)
                self.assertEqual(cfg['primary']['fpThreshold'], cfg['gate']['threshold'],
                                 f'{edition} {position}')

    def testTheThresholdScalesWithPositionAndEdition(self):
        # A kicker and a quarterback were both asked for a flat 15 before.
        qb = cfgFor('metallic', QB)['primary']['fpThreshold']
        k = cfgFor('metallic', K)['primary']['fpThreshold']
        self.assertLess(k, qb, 'a kicker should not need a quarterback\'s FP')
        self.assertLess(cfgFor('metallic', QB)['primary']['fpThreshold'],
                        cfgFor('diamond', QB)['primary']['fpThreshold'],
                        'a rarer card should ask more')

    def testThereIsNoDeadBandWhereTheCardReadsActiveAndPaysNothing(self):
        """Above the bar, the card always earns something."""
        cfg = cfgFor('metallic', QB)
        thr = cfg['primary']['fpThreshold']
        for fp in range(thr + 1, thr * 2 + 1):
            result = _computeHonorRoll(cfg['primary'], Ctx(fp), 7, 1)
            self.assertGreater(result.multBonus or 0, 1.0, f'{fp} FP paid nothing')

    def testItPaysNothingBelowTheBar(self):
        cfg = cfgFor('metallic', QB)
        thr = cfg['primary']['fpThreshold']
        result = _computeHonorRoll(cfg['primary'], Ctx(thr - 1), 7, 1)
        self.assertFalse(result.multBonus)

    def testItRampsRatherThanSwitchingOnFlat(self):
        cfg = cfgFor('metallic', QB)
        thr = cfg['primary']['fpThreshold']
        quarter = _computeHonorRoll(cfg['primary'], Ctx(int(thr * 1.25)), 7, 1).multBonus
        half = _computeHonorRoll(cfg['primary'], Ctx(int(thr * 1.5)), 7, 1).multBonus
        full = _computeHonorRoll(cfg['primary'], Ctx(thr * 2), 7, 1).multBonus
        self.assertLess(quarter, half)
        self.assertLess(half, full)

    def testABigGameMeansDoubleTheBar(self):
        cfg = cfgFor('metallic', QB)
        thr = cfg['primary']['fpThreshold']
        full = _computeHonorRoll(cfg['primary'], Ctx(thr * 2), 7, 1).multBonus
        self.assertAlmostEqual(full, cfg['primary']['maxMult'], places=2)

    def testItIsCappedAboveDoubleTheBar(self):
        cfg = cfgFor('metallic', QB)
        thr = cfg['primary']['fpThreshold']
        full = _computeHonorRoll(cfg['primary'], Ctx(thr * 2), 7, 1).multBonus
        beyond = _computeHonorRoll(cfg['primary'], Ctx(thr * 5), 7, 1).multBonus
        self.assertEqual(beyond, full)

    def testClearingTheBarPaysTheBaseRatherThanNothing(self):
        """The last dead point. At EXACTLY the bar the ramp used to pay +0.00."""
        for edition in EDITIONS:
            cfg = cfgFor(edition, QB)
            thr = cfg['primary']['fpThreshold']
            result = _computeHonorRoll(cfg['primary'], Ctx(thr), 7, 1)
            self.assertGreater(result.multBonus or 0, 1.0, edition)
            self.assertAlmostEqual(result.multBonus, cfg['primary']['baseMult'], places=2)

    def testTheBaseIsBelowTheMaximum(self):
        # Otherwise "and grows if they score more" would be a lie.
        for edition in EDITIONS:
            p = cfgFor(edition, QB)['primary']
            self.assertLess(p['baseMult'], p['maxMult'], edition)

    def testAnOldCardWithNoBaseStillScores(self):
        # Cards minted before baseMult existed must not crash or pay a negative.
        cfg = cfgFor('metallic', QB)
        legacy = dict(cfg['primary'])
        legacy.pop('baseMult', None)
        thr = legacy['fpThreshold']
        result = _computeHonorRoll(legacy, Ctx(thr * 2), 7, 1)
        self.assertAlmostEqual(result.multBonus, legacy['maxMult'], places=2)

    def testTheAdvertisedThresholdIsTheOneItScoresAgainst(self):
        """The detail is formatted from the params, so a late sync would desync them."""
        import re
        for edition in EDITIONS:
            for position in (QB, K):
                cfg = cfgFor(edition, position)
                shown = re.search(r'reaches (\d+) FP', cfg['detail'])
                self.assertIsNotNone(shown, cfg['detail'])
                self.assertEqual(int(shown.group(1)), cfg['primary']['fpThreshold'])

    def testTheTextTellsTheReaderItGrows(self):
        from managers.cardEffects import EFFECT_DETAIL_TEMPLATES, EFFECT_TOOLTIPS
        for text in (EFFECT_DETAIL_TEMPLATES['honor_roll'], EFFECT_TOOLTIPS['honor_roll']):
            self.assertRegex(text, r'grow', f'ramp not described: {text}')

    def testNoEmDashInTheCardText(self):
        from managers.cardEffects import EFFECT_DETAIL_TEMPLATES, EFFECT_TOOLTIPS
        for text in (EFFECT_DETAIL_TEMPLATES['honor_roll'], EFFECT_TOOLTIPS['honor_roll']):
            self.assertNotIn('\u2014', text, f'em-dash in copy: {text}')


if __name__ == '__main__':
    unittest.main(verbosity=2)
