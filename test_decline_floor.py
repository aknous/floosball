"""A declining attribute stops at 80% of its peak, and never below 60 (owner, 2026-10-09).

Before this, decline steepened every season to -5..-11 per attribute and ran until the
player retired, ending only at an absolute floor of 55. Now two floors apply and the
higher holds:
  - absolute: DEV_ATTRIBUTE_FLOOR (60), the lowest generated value;
  - relative: DEV_PEAK_FLOOR_FRACTION (0.80) of the highest value the attribute reached,
    tracked per attribute as `peak*` on PlayerAttributes / `peak_*` on player_attributes.
Neither LIFTS an attribute already below it; they only stop it falling.

Run: .venv/bin/python test_decline_floor.py
"""
import os
import random
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import logging
logging.disable(logging.CRITICAL)

import floosball_player  # noqa: F401  (resolves the import order before player_development)
from player_development import (PlayerDevelopment, DevContext, CareerPhase,
                                PEAK_ATTR_NAMES)
from constants import DEV_ATTRIBUTE_FLOOR, DEV_PEAK_FLOOR_FRACTION, DEV_DECLINE_MAX_STEEPEN

HERE = os.path.dirname(os.path.abspath(__file__))


def _read(*parts):
    with open(os.path.join(HERE, *parts)) as f:
        return f.read()


def _ctx(phase, intensity=0, factor=1.5):
    return DevContext(phase=phase, intensity=intensity, isProspect=False,
                      devBias=0, declineFactor=factor)


class _Attrs:
    def __init__(self, value, trueSkill, potential, peak=0):
        self.speed = value
        self.trueSkillSpeed = trueSkill
        self.potentialSpeed = potential
        self.peakSpeed = peak


def _ageSpeed(attrs, seasons, ctx):
    for _ in range(seasons):
        PlayerDevelopment._dev(attrs, 'speed', 'trueSkillSpeed', 'potentialSpeed', ctx)
    return attrs.speed


class DeclineFloorTests(unittest.TestCase):

    def setUp(self):
        random.seed(11)

    def testTheFloorIsTheHigherOfSixtyAndEightyPercentOfPeak(self):
        self.assertEqual(DEV_ATTRIBUTE_FLOOR, 60)
        self.assertEqual(DEV_PEAK_FLOOR_FRACTION, 0.80)
        self.assertEqual(PlayerDevelopment.declineFloor(95), 76)
        self.assertEqual(PlayerDevelopment.declineFloor(80), 64)
        self.assertEqual(PlayerDevelopment.declineFloor(70), 60)
        self.assertEqual(PlayerDevelopment.declineFloor(0), 60)

    def testAStarAtTheSteepestDeclineStopsAtEightyPercentOfPeak(self):
        attrs = _Attrs(95, 95, 98, peak=95)
        ctx = _ctx(CareerPhase.DECLINING, DEV_DECLINE_MAX_STEEPEN, factor=1.5)
        self.assertEqual(_ageSpeed(attrs, 30, ctx), 76)
        self.assertEqual(attrs.peakSpeed, 95)

    def testAModestPlayerStopsAtSixty(self):
        attrs = _Attrs(72, 72, 75, peak=72)
        ctx = _ctx(CareerPhase.DECLINING, DEV_DECLINE_MAX_STEEPEN, factor=1.5)
        self.assertEqual(_ageSpeed(attrs, 30, ctx), 60)

    def testTheFloorNeverLiftsAnAttributeAlreadyBelowIt(self):
        # A veteran who aged under 60 before the floor existed holds where he is.
        attrs = _Attrs(56, 70, 72, peak=70)
        ctx = _ctx(CareerPhase.DECLINING, DEV_DECLINE_MAX_STEEPEN, factor=1.5)
        self.assertEqual(_ageSpeed(attrs, 10, ctx), 56)
        # Likewise one below 80% of a high peak: no jump back up to the line.
        attrs = _Attrs(66, 92, 95, peak=92)
        self.assertEqual(_ageSpeed(attrs, 10, ctx), 66)

    def testAProspectBelowSixtyStillRisesNormally(self):
        attrs = _Attrs(54, 65, 70)
        _ageSpeed(attrs, 6, _ctx(CareerPhase.RISING))
        self.assertGreater(attrs.speed, 54)
        self.assertLessEqual(attrs.speed, 70)

    def testThePeakTracksTheHighestValueReached(self):
        attrs = _Attrs(70, 85, 85)
        _ageSpeed(attrs, 12, _ctx(CareerPhase.RISING))
        high = attrs.peakSpeed
        self.assertEqual(high, max(70, attrs.speed))
        self.assertGreaterEqual(high, attrs.speed)
        _ageSpeed(attrs, 30, _ctx(CareerPhase.DECLINING, DEV_DECLINE_MAX_STEEPEN))
        self.assertEqual(attrs.peakSpeed, high)
        self.assertEqual(attrs.speed, PlayerDevelopment.declineFloor(high))

    def testAnUnrecordedPeakOnADecliningPlayerReadsAsHisTrueSkill(self):
        # A veteran from before peaks were tracked: aged 90 -> 74, true skill 90.
        attrs = _Attrs(74, 90, 92, peak=0)
        PlayerDevelopment._dev(attrs, 'speed', 'trueSkillSpeed', 'potentialSpeed',
                               _ctx(CareerPhase.DECLINING, DEV_DECLINE_MAX_STEEPEN))
        self.assertEqual(attrs.peakSpeed, 90)
        self.assertEqual(attrs.speed, 72)   # 80% of 90; the drop was larger

    def testAnUnrecordedPeakOnARisingPlayerReadsAsTodaysValue(self):
        attrs = _Attrs(62, 80, 84, peak=0)
        PlayerDevelopment._dev(attrs, 'speed', 'trueSkillSpeed', 'potentialSpeed',
                               _ctx(CareerPhase.PEAK))
        self.assertEqual(attrs.peakSpeed, max(62, attrs.speed))

    def testEveryPeakColumnIsStoredLoadedAndSaved(self):
        models = _read('database', 'models.py')
        migration = _read('database', 'connection.py')
        manager = _read('managers', 'playerManager.py')
        for attr, peakName in PEAK_ATTR_NAMES.items():
            col = 'peak_' + re.sub(r'([A-Z])', r'_\1', attr).lower()
            self.assertIn(f'{col}: Mapped[int]', models, col)
            self.assertIn(f"'{col}'", migration, col)
            self.assertIn(f"player.attributes.{peakName} = getattr(attrs, '{col}'", manager, col)
            self.assertIn(f"{col}=getattr(attrs, '{peakName}'", manager, col)
            self.assertIn(f"db_attrs.{col} = getattr(attrs, '{peakName}'", manager, col)


if __name__ == '__main__':
    unittest.main(verbosity=2)
