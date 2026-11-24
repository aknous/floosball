"""Gap selection: vision reads, agility cuts, discipline resists the bounce, no cliff.

`Play.selectRunGap` used discipline TIERS: a back at 70+ ran the called gap even when it
was stuffed, one under 70 read freely, so crossing 70 cost 1.35 yards a carry and vision
did nothing for a disciplined back. Each test below fails on that rule.

Run with `.venv/bin/python -m pytest test_run_gap_read.py` (or directly).
"""
import random
import unittest

import numpy as np

import constants
import floosball_game as FG

TRIALS = 4000
PLAY = FG.Play.__new__(FG.Play)   # selectRunGap reads nothing off the play


def gaps(designed, b, c, bounce, designedType='A-gap'):
    out = []
    for t, q in (('A-gap', designed if designedType == 'A-gap' else b),
                 ('B-gap', b if designedType == 'A-gap' else designed),
                 ('C-gap', c), ('bounce', bounce)):
        out.append({'type': t, 'quality': q, 'isDesigned': t == designedType})
    return out


def meanQuality(gapList, vision, discipline, agility=80, seed=7):
    random.seed(seed)
    np.random.seed(seed)
    qs = [PLAY.selectRunGap(gapList, vision, discipline, agility)['actualQuality']
          for _ in range(TRIALS)]
    return float(np.mean(qs))


class RunGapReadTests(unittest.TestCase):
    def setUp(self):
        self._flag = constants.RUN_GAP_READ_V2
        constants.RUN_GAP_READ_V2 = True

    def tearDown(self):
        constants.RUN_GAP_READ_V2 = self._flag

    def testNoDisciplineCliff(self):
        # Called gap stuffed, a cutback open: the old rule split this at 70.
        g = gaps(designed=20, b=70, c=45, bounce=40)
        q65, q75 = meanQuality(g, 85, 65), meanQuality(g, 85, 75)
        self.assertLess(abs(q75 - q65), 3.0)

    def testDisciplineNeverHurts(self):
        # A tempting but poor bounce lane: discipline is what stops the chase.
        g = gaps(designed=50, b=45, c=40, bounce=35)
        qs = [meanQuality(g, 85, d) for d in (55, 65, 75, 85, 95)]
        for lo, hi in zip(qs, qs[1:]):
            self.assertGreaterEqual(hi, lo - 0.5)
        self.assertGreater(qs[-1], qs[0] + 2.0)

    def testVisionFindsTheBetterGap(self):
        g = gaps(designed=25, b=65, c=40, bounce=30)
        qs = [meanQuality(g, v, 85) for v in (62, 77, 92)]
        self.assertLess(qs[0], qs[1])
        self.assertLess(qs[1], qs[2])

    def testAgilityMakesTheCutCheaper(self):
        g = gaps(designed=15, b=75, c=40, bounce=30)
        self.assertGreater(meanQuality(g, 92, 85, agility=95),
                           meanQuality(g, 92, 85, agility=65) + 5.0)

    def testStaysOnTheCallWhenNothingIsClearlyBetter(self):
        g = gaps(designed=55, b=58, c=50, bounce=40)
        random.seed(3)
        np.random.seed(3)
        picks = [PLAY.selectRunGap(g, 95, 85, 80)['isDesigned'] for _ in range(TRIALS)]
        self.assertGreater(np.mean(picks), 0.9)

    def testLegacyPathBehindTheFlag(self):
        constants.RUN_GAP_READ_V2 = False
        g = gaps(designed=20, b=70, c=45, bounce=40)
        self.assertGreater(meanQuality(g, 85, 65) - meanQuality(g, 85, 75), 10.0)


if __name__ == '__main__':
    unittest.main()
