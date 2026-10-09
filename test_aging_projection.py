"""The GM projects aging with the sim's own development, not a separate guess.

Before 2026-10-09, `frontOfficeBrain.trueForwardRating` held a player flat until his
longevity and then took 6% a season past it, applying the whole accumulated amount in ONE
season (capped at 40%). Measured against the sim over 9,099 career offseasons, it was wrong
both ways: decline starts the season after a player's PEAK (~60% of longevity), so the GM
forecast growth for 3-4 seasons of real decline; and past longevity the sim never takes
more than ~2 rating points a season, while the guess took 4 to 28.

Now a player at or past his peak season is projected by `Player.computeNextSeasonRating`:
the offseason's rules (`PlayerDevelopment.expectedAttribute`) at their exact average, then
the rating recomputed.

Run: .venv/bin/python test_aging_projection.py
"""
import os
import random
import sys
import types
import unittest

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import logging
logging.disable(logging.CRITICAL)

import floosball_player as FP
from player_development import PlayerDevelopment, DevContext, CareerPhase
from managers.frontOfficeBrain import FrontOfficeBrain

HERE = os.path.dirname(os.path.abspath(__file__))


class _PM:
    def computeRetirementOdds(self, p):
        return 0, False, p.seasonsPlayed - p.attributes.longevity


def _player(cls, pid, seed, longevity, seasonsPlayed):
    random.seed(pid)
    np.random.seed(pid)   # the constructors draw attributes from numpy
    p = cls(seed, seed)
    p.id, p.name = pid, f'p{pid}'
    p.attributes.longevity = longevity
    p.seasonsPlayed, p.prospect_seasons, p.is_prospect = seasonsPlayed, 0, False
    p.updateRating()
    return p


def _meanAfterTraining(p, trials=400):
    """Average rating after one real offseason, over many rolls of the same player."""
    total = 0
    for t in range(trials):
        random.seed(10_000 + t)
        saved = {k: getattr(p.attributes, k) for k in vars(p.attributes)}
        p.offseasonTraining(coachDevRating=80, fundingDevBonus=0)
        total += p.playerRating
        for k, v in saved.items():
            setattr(p.attributes, k, v)
        p.updateRating()
    return total / trials


class AgingProjectionTests(unittest.TestCase):

    def testTheExpectationIsTheAverageOfTheRealRoll(self):
        cases = [
            (CareerPhase.DECLINING, 6, 0.85, 88, 90, 94, 92),
            (CareerPhase.DECLINING, 2, 1.40, 70, 74, 80, 74),
            (CareerPhase.DECLINING, 3, 0.50, 61, 70, 75, 76),   # near the 60 floor
            (CareerPhase.PEAK, 0, 1.00, 80, 84, 92, 80),          # overshoot can fire
            (CareerPhase.RISING, 0, 1.00, 70, 82, 90, 70),
        ]
        for phase, intensity, factor, current, trueSkill, potential, peak in cases:
            ctx = DevContext(phase=phase, intensity=intensity, isProspect=False,
                             devBias=2, declineFactor=factor)
            expected = PlayerDevelopment.expectedAttribute(current, trueSkill, potential, ctx, peak)
            random.seed(3)
            n = 40_000
            sampled = sum(PlayerDevelopment.developAttribute(current, trueSkill, potential, ctx, peak)
                          for _ in range(n)) / n
            self.assertAlmostEqual(expected, sampled, delta=0.06,
                                   msg=f'{phase.name} {current}: {expected:.3f} vs {sampled:.3f}')

    def testThePastPeakProjectionMatchesWhatTrainingDoes(self):
        brain = FrontOfficeBrain(_PM())
        coach = types.SimpleNamespace(playerDevelopment=80, scouting=80)
        checked = 0
        for i, cls in enumerate([FP.PlayerQB, FP.PlayerRB, FP.PlayerWR, FP.PlayerTE, FP.PlayerK]):
            for seasons in (7, 9, 12, 15):
                p = _player(cls, 500 + i * 10 + seasons, 86, 10, seasons)
                if PlayerDevelopment.careerContext(p, 0).phase == CareerPhase.RISING:
                    continue
                projected = brain.trueForwardRating(p, coach)
                actual = _meanAfterTraining(p)
                # The projection is a whole-number rating (updateRating rounds three
                # times) against an averaged float, so rounding alone moves it ~1.
                self.assertLess(abs(projected - actual), 1.5,
                                f'{cls.__name__} season {seasons}: projected {projected}, '
                                f'trained to {actual:.2f}')
                checked += 1
        self.assertGreater(checked, 10)

    def testAVeteranPastLongevityIsNotProjectedOffACliff(self):
        # Age a real career to five seasons past longevity, so he has already done his
        # declining and sits near his floor. The old guess took 30% off him here.
        brain = FrontOfficeBrain(_PM())
        p = _player(FP.PlayerWR, 901, 90, 8, 1)
        random.seed(901)
        for season in range(1, 14):
            p.seasonsPlayed = season
            p.offseasonTraining(coachDevRating=80, fundingDevBonus=0)
        p.seasonsPlayed = 13
        now = p.playerRating
        self.assertGreaterEqual(brain.trueForwardRating(p), now - 1)

    def testProjectingLeavesThePlayerUntouched(self):
        p = _player(FP.PlayerQB, 902, 88, 10, 9)
        before = (p.playerRating, dict(vars(p.attributes)))
        p.projectedRatingPastPeak(2)
        p.computeNextSeasonRating(2)
        self.assertEqual(before, (p.playerRating, dict(vars(p.attributes))))

    def testARisingPlayerKeepsTheDevelopingReading(self):
        brain = FrontOfficeBrain(_PM())
        p = _player(FP.PlayerRB, 903, 84, 12, 1)
        self.assertEqual(PlayerDevelopment.careerContext(p, 0).phase, CareerPhase.RISING)
        self.assertIsNone(p.projectedRatingPastPeak(2))
        self.assertIsNone(brain._nextSeasonRatingPastPeak(p))

    def testTheOldDeclineConstantsAreGone(self):
        import constants
        self.assertFalse(hasattr(constants, 'FO_DECLINE_PER_YEAR_PAST'))
        self.assertFalse(hasattr(constants, 'FO_DECLINE_MAX'))


if __name__ == '__main__':
    unittest.main(verbosity=2)
