"""The 2026-11-23 attribute pass: QB throwing skill, the QB's read, TE blocking, and the
run model reading the game-day copy.

Each check compares the new rule with the old one through its switch, so a revert of
either side fails here rather than passing on a fixed threshold.

Run with `.venv/bin/python -m pytest test_pass_and_block_skill.py` (or directly).
"""
import random
import unittest

import numpy as np

import constants
import floosball_game as FG
from random_batch import clear_all_batch_caches
from scenario import Scenario

FLAGS = ('QB_SKILL_V2', 'RUN_BLOCKING_V2', 'RUN_READS_GAME_ATTRIBUTES')


def reseed(s):
    random.seed(s)
    np.random.seed(s)
    clear_all_batch_caches()


def recompute(attrs):
    attrs.calculateIntangibles()
    attrs.calculateSkills()


class AttributePassTests(unittest.TestCase):
    def setUp(self):
        self._saved = {f: getattr(constants, f) for f in FLAGS}
        for f in FLAGS:
            setattr(constants, f, True)

    def tearDown(self):
        for f, v in self._saved.items():
            setattr(constants, f, v)

    # ── QB ───────────────────────────────────────────────────────────────
    def _throwQuality(self, acc, arm, xf):
        reseed(9)   # a throw carries a ±10 random term; the same draw makes deltas exact
        s = Scenario().situation(quarter=2, clock=600, down=1, distance=10, ballOn=60)
        p = s.game.play
        p.passer = s.home.rosterDict['qb']
        return p.calculateThrowQuality(FG.PassType.medium, acc, arm, xf, 0.0, 0.0)

    def _accuracyVsXFactor(self):
        acc = self._throwQuality(100, 80, 80) - self._throwQuality(60, 80, 80)
        xf = self._throwQuality(80, 80, 100) - self._throwQuality(80, 80, 60)
        return acc, xf

    def testAccuracyCarriesTheThrow(self):
        acc, xf = self._accuracyVsXFactor()
        self.assertGreater(acc, 2.5 * xf)
        constants.QB_SKILL_V2 = False
        accOld, xfOld = self._accuracyVsXFactor()
        self.assertLess(accOld, 1.2 * xfOld)   # the old rule: X-Factor half of every throw

    def testArmMattersOnAMediumThrow(self):
        arm = self._throwQuality(80, 100, 80) - self._throwQuality(80, 60, 80)
        constants.QB_SKILL_V2 = False
        armOld = self._throwQuality(80, 100, 80) - self._throwQuality(80, 60, 80)
        self.assertGreater(arm, 1.4 * armOld)

    def testReadErrorHasNoTierJumps(self):
        steps = [FG.qbReadErrorRange(v) - FG.qbReadErrorRange(v + 1) for v in range(60, 100)]
        self.assertLessEqual(max(steps), 1)
        self.assertGreater(FG.qbReadErrorRange(65), FG.qbReadErrorRange(95))
        constants.QB_SKILL_V2 = False
        self.assertEqual(FG.qbReadErrorRange(69) - FG.qbReadErrorRange(70), 10)

    # ── run game ─────────────────────────────────────────────────────────
    def _ypc(self, setup, n=1500, seed=4):
        reseed(seed)
        s = Scenario()
        setup(s)
        tot = 0
        for _ in range(n):
            s.situation(quarter=2, clock=600, offense='home', down=1, distance=10, ballOn=60)
            s.game.play.runPlay()
            tot += s.game.play.yardage
        return tot / n

    def _blockingGap(self):
        def te(power):
            def setup(s):
                g = s.home.rosterDict['te'].gameAttributes
                g.power = power
                recompute(g)
            return setup
        return self._ypc(te(100)) - self._ypc(te(60))

    def testTheBlockerMakesTheHole(self):
        new = self._blockingGap()
        constants.RUN_BLOCKING_V2 = False
        old = self._blockingGap()
        self.assertGreater(new, 0.5)
        self.assertGreater(new, old + 0.2)

    def _gameDayMinusProfile(self):
        def split(gameAgility, profileAgility):
            def setup(s):
                rb = s.home.rosterDict['rb']
                rb.attributes.agility = profileAgility
                recompute(rb.attributes)
                rb.gameAttributes.agility = gameAgility
                recompute(rb.gameAttributes)
            return setup
        return self._ypc(split(100, 60)) - self._ypc(split(60, 100))

    def testRunModelReadsTheGameDayCopy(self):
        # Agility high on the game-day copy and low on the profile, against the reverse:
        # the copy the model reads decides which side runs better.
        self.assertGreater(self._gameDayMinusProfile(), 0.5)
        constants.RUN_READS_GAME_ATTRIBUTES = False
        self.assertLess(self._gameDayMinusProfile(), 0.0)


if __name__ == '__main__':
    unittest.main()
