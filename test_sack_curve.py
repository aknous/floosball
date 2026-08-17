"""The sack curve: the league mean was right, the SPREAD was not.

Reported as an explosion of sacks — 19 by one team in a Floos Bowl. Measured over
1,511 logged games the league AVERAGE was already on target (2.85/team/game, 6.1% per
dropback, against a real-world ~2.4), so the base rate was never the fault. The TAIL
was: per-game sack rate p99 16.3%, top games 19%.

⚠️ `SACK_PROB_CAP` (30) and a HARDCODED steepness (0.15) were what set the spread. A 90
pass rush against a 70-mobility QB sat at 22.9% per dropback for the WHOLE GAME, so a
20-point attribute gap bought a 4x sack rate where real football buys about 2x — and
over ~42 dropbacks the high teens stopped being a freak result.

⚠️ TUNE THIS AGAINST THE SPREAD, NEVER THE MEAN. Dropping the cap far enough forces the
base rate up to hold the mean, which parks most plays at the ceiling and flattens the
curve into "pass rush quality is irrelevant" — a league that reads correct on average
and has stopped modelling the thing. These tests pin BOTH ends: a ceiling on the worst
matchup and a floor on how much the rush still matters.

Run: .venv/bin/python test_sack_curve.py
"""

import os
import re
import sys
import types
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import logging
logging.disable(logging.CRITICAL)

if 'floosball_game' not in sys.modules:
    _stub = types.ModuleType('floosball_game')
    class _GameStub: pass
    _stub.Game = _GameStub
    sys.modules['floosball_game'] = _stub
    import managers.timingManager  # noqa: F401
    del sys.modules['floosball_game']

import floosball_game as FG  # noqa: E402
from constants import SACK_BASE_RATE, SACK_PROB_CAP, SACK_CURVE_STEEPNESS  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))

# Measured off the real 32-team roster in `data/floosball.db` (derived pass rush per
# team, QB mobility, TE/RB blocking modifiers). These are the ENDS of the league, not
# hypotheticals — the curve has to behave at both.
RUSH_ELITE, RUSH_POOR = 91, 66
MOB_ELITE, MOB_POOR = 97, 58
BLK_TYPICAL = 2

# `calculateSackProbability` reads nothing off self, so an unbound call keeps this
# test free of a constructed Play.
_prob = FG.Play.calculateSackProbability


def sackPct(rush, mobility, blockers=BLK_TYPICAL, dropback=2):
    return _prob(None, rush, mobility, blockers, dropback)


class SackCurveTests(unittest.TestCase):
    def testTheWorstMatchupIsNotAGuaranteedSack(self):
        """The reported bug, at its source: the league's best rush against its worst
        protection, sustained for a whole game."""
        worst = sackPct(RUSH_ELITE, MOB_POOR, blockers=0)
        self.assertLessEqual(
            worst, 16.5,
            'worst matchup at %.1f%% per dropback — over ~42 dropbacks that is the '
            '19-sack game coming back' % worst)

    def testAnEvenMatchupReadsTheBaseRate(self):
        """The curve is centered so a differential of exactly 0 reads the base rate —
        rush == mobility + blocking*4, on a dropback that adds nothing. ⚠️ That is NOT
        the realized league rate: protection systematically outweighs the rush, so the
        typical differential is about -17 and the league lands near 6%. Anyone reading
        SACK_BASE_RATE as "the sack rate" has misread it."""
        even = sackPct(80, 80 - BLK_TYPICAL * 4, dropback=1)
        self.assertAlmostEqual(even, SACK_BASE_RATE, delta=0.1)

    def testPassRushQualityStillMatters(self):
        """The floor that stops a fix for the tail turning into a flat curve. Elite vs
        poor rush, same offense, must be a real gap."""
        elite = sackPct(RUSH_ELITE, 78)
        poor = sackPct(RUSH_POOR, 78)
        self.assertGreater(elite / poor, 2.0,
                           'pass rush has stopped mattering (%.1f%% vs %.1f%%)'
                           % (elite, poor))

    def testQbMobilityStillMatters(self):
        """The other side of the same matchup."""
        self.assertGreater(sackPct(80, MOB_POOR) / sackPct(80, MOB_ELITE), 2.0)

    def testBlockersMatter(self):
        """14 of the 24 pass plays leave only one back or tight end in to block, so
        this is the single biggest per-play swing in the whole model."""
        self.assertGreater(sackPct(85, 75, blockers=0), sackPct(85, 75, blockers=4))

    def testTheDeepDropbackCapIsALift(self):
        """⚠️ The `28 if dropbackDepth >= 6` ceiling is written to LIFT the standard cap
        for hail marys — the QB is exposed far longer. While SACK_PROB_CAP sat at 30 it
        was silently a REDUCTION, doing the exact opposite of what its comment claims.
        Whoever moves the cap next has to keep these two ordered."""
        self.assertLess(SACK_PROB_CAP, 28,
                        'the deep-dropback ceiling (28) is no longer a lift over '
                        'SACK_PROB_CAP (%s)' % SACK_PROB_CAP)
        deep = sackPct(RUSH_ELITE, MOB_POOR, blockers=0, dropback=6)
        normal = sackPct(RUSH_ELITE, MOB_POOR, blockers=0, dropback=2)
        self.assertGreater(deep, normal)

    def testSteepnessComesFromConstants(self):
        """It was a magic number in the function body, which is why it was never a
        tuning candidate despite being half of what sets the spread."""
        with open(os.path.join(HERE, 'floosball_game.py')) as fh:
            src = fh.read()
        start = src.index('def calculateSackProbability')
        body = src[start:src.index('\n    def ', start + 10)]
        self.assertIn('SACK_CURVE_STEEPNESS', body)
        self.assertIsNone(
            re.search(r'steepness\s*=\s*0\.\d+', body),
            'steepness is hardcoded again — put it back in constants.py')
        self.assertGreater(SACK_CURVE_STEEPNESS, 0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
