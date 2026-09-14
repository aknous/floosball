"""An audible has to fit the situation, not just the box.

⚠️ THE READ LOOKS AT THE DEFENSE ALONE. Before this, a QB checked at the same ~15% on
every down: into a run on 3rd & 8 because the box was light, out of a run while
protecting a late lead because the box was stacked. Measured against NFL 2021-25
play-by-play it flattened every situation — 3rd & 7-10 ran 24% of the time against the
NFL's 3% — and switching audibles off recovered ~10 points of 3rd-down pass rate.

The rule: willingness is scaled by how hard the caller's own weights argue against the
call being checked INTO. A check toward the situation's lean is never scaled.

Run: .venv/bin/python test_audible_situation.py
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import logging
logging.disable(logging.CRITICAL)

from scenario import Scenario  # noqa: E402
import constants  # noqa: E402

COIN_FLIP = {'run': 50.0, 'short': 22.0, 'medium': 18.0, 'long': 8.0, 'deep': 2.0}
PASS_DOWN = {'run': 12.0, 'short': 15.0, 'medium': 48.0, 'long': 23.0, 'deep': 2.0}
N = 4000


class AudiblesFitTheSituation(unittest.TestCase):

    def setUp(self):
        self._saved = (constants.DEFENSIVE_DISGUISE_ENABLED, constants.AUDIBLE_SITUATION_AWARE)
        constants.DEFENSIVE_DISGUISE_ENABLED = False

    def tearDown(self):
        constants.DEFENSIVE_DISGUISE_ENABLED, constants.AUDIBLE_SITUATION_AWARE = self._saved

    def _game(self, runStopFocus):
        s = Scenario()
        s.situation(quarter=2, clock=600, offense='home', offScore=14, defScore=14,
                    down=3, distance=8, ballOn=55)
        g = s.game
        gp = g.awayDefGameplan if g.offensiveTeam is g.homeTeam else g.homeDefGameplan
        if gp is None:
            self.skipTest('no defensive gameplan in the scenario')
        gp.runStopFocus = runStopFocus
        return s, g

    def _checkRate(self, g, s, call, weights, target):
        hits = 0
        for _ in range(N):
            s._newPlay()
            if g._maybeAudible(call, weights) == target:
                hits += 1
        return hits / N

    def testACheckIntoARunIsRareOnAPassingDown(self):
        """A light box invites a run; on 3rd & 8 the caller wanted 12% runs."""
        s, g = self._game(runStopFocus=0.30)
        flip = self._checkRate(g, s, 'medium', COIN_FLIP, 'run')
        passDown = self._checkRate(g, s, 'medium', PASS_DOWN, 'run')
        self.assertGreater(flip, 0.05, 'no checks at all on a coin-flip down')
        # (0.12 / 0.5) ** 1 = 0.24 of the coin-flip rate, with room for noise.
        self.assertLess(passDown, flip * 0.45,
                        'a QB still checks into a run on 3rd & long as freely as on 1st & 10')

    def testACheckTowardTheSituationIsNotScaled(self):
        """A stacked box invites a throw; on 3rd & 8 that is what the caller wanted anyway."""
        s, g = self._game(runStopFocus=0.80)
        flip = self._checkRate(g, s, 'run', COIN_FLIP, 'short') + \
            self._checkRate(g, s, 'run', COIN_FLIP, 'medium')
        passDown = self._checkRate(g, s, 'run', PASS_DOWN, 'short') + \
            self._checkRate(g, s, 'run', PASS_DOWN, 'medium')
        self.assertAlmostEqual(passDown, flip, delta=0.05,
                               msg='a check toward the lean was scaled down')

    def testTheFlagRestoresTheBoxOnlyRead(self):
        constants.AUDIBLE_SITUATION_AWARE = False
        s, g = self._game(runStopFocus=0.30)
        flip = self._checkRate(g, s, 'medium', COIN_FLIP, 'run')
        passDown = self._checkRate(g, s, 'medium', PASS_DOWN, 'run')
        self.assertAlmostEqual(passDown, flip, delta=0.04)


if __name__ == '__main__':
    unittest.main()
