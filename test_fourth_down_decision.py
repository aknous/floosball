"""The normal-game 4th down is one model, fitted to the NFL.

⚠️ GOING FOR IT ON 4TH & 1 WAS ROLLED IN ABOUT EIGHT PLACES, each with its own threshold
and its own idea of score and field position — a team trailing in the first half outside
FG range never went for it at all. Against NFL 2021-25 the sim went 32-52% of the time
in opponent territory where the NFL goes 85-94%, and 0-10% in its own half where the NFL
goes 32-64%, while converting MORE often than the NFL (76% vs 70%).

⚠️ AND A FINAL-DOWN SNEAK COULD NOT HAPPEN. The 4th-down caller called runPlay()
directly, which never picks a run concept, so the QB sneak (which is allowed on 3rd AND
4th & short) only ever fired on 3rd down. The go play now runs through the normal play
path.

⚠️ AND THE KICK WAS A HARD CUTOFF. Inside the opponent's 40 a makeable field goal was
taken ~90% of the time out to 57 yards, where NFL coaches mostly go for it or punt. The
kick-or-punt choice now follows the kicker's make probability along the NFL's 52-58 yard
cliff, so a big leg earns longer tries.

Run: .venv/bin/python test_fourth_down_decision.py
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import logging
logging.disable(logging.CRITICAL)

from scenario import Scenario, PlayType  # noqa: E402


def prob(ballOn, offScore=14, defScore=14, quarter=2, clock=600, distance=1, aggr=80):
    s = Scenario()
    s.situation(quarter=quarter, clock=clock, down=4, distance=distance, ballOn=ballOn,
                offScore=offScore, defScore=defScore)
    s.home.coach.aggressiveness = aggr
    return s.game._fourthDownGoProbability(s._scoreDiff(), s.home.coach)


class TheCurve(unittest.TestCase):

    def testOpponentTerritoryIsAlmostAlwaysAGo(self):
        for ballOn in (3, 25, 45):
            self.assertGreater(prob(ballOn), 0.8, ballOn)

    def testItFallsOffThroughTheOffensesOwnHalf(self):
        ps = [prob(b) for b in (45, 57, 72, 90)]
        self.assertEqual(ps, sorted(ps, reverse=True), ps)
        self.assertLess(prob(90), 0.15)

    def testTrailingGoesMoreAndLeadingLess(self):
        self.assertGreater(prob(65, offScore=7, defScore=21), prob(65))
        self.assertLess(prob(65, offScore=21, defScore=7), prob(65))

    def testABoldCoachGoesMoreThanATimidOne(self):
        self.assertGreater(prob(65, aggr=98), prob(65, aggr=62) + 0.2)

    def testTheClockBranchesStillOwnTheLateWindows(self):
        self.assertIsNone(prob(40, quarter=4, clock=240))
        self.assertIsNone(prob(40, quarter=2, clock=45))
        self.assertIsNone(prob(40, quarter=5, clock=400))

    def testTheShortYardageGoPeaksBetweenTheThirtyAndTheFortyFive(self):
        """Too far for an easy kick, too close to punt. In the red zone the short field
        goal is the play, so a 4th & 3 goes LESS there than at the 40."""
        self.assertGreater(prob(40, distance=3), prob(15, distance=3) + 0.2)

    def testLongYardageAlmostNeverGoes(self):
        self.assertLess(prob(40, distance=12), 0.1)


class TheDecision(unittest.TestCase):

    def _calls(self, n=300, **situation):
        kinds, sneaks = [], 0
        for _ in range(n):
            s = Scenario()
            s.situation(down=4, distance=1, **situation)
            kinds.append(s.fourthDownPlay())
            sneaks += int(getattr(s.game.play, 'runConcept', None) == 'sneak')
        return kinds, sneaks

    def testMidfieldFourthAndOneGoesAndSometimesSneaks(self):
        kinds, sneaks = self._calls(quarter=2, clock=600, ballOn=48, offScore=14, defScore=14)
        goes = sum(1 for k in kinds if k in (PlayType.Run, PlayType.Pass))
        self.assertGreater(goes / len(kinds), 0.75)
        self.assertGreater(sneaks, 0, 'a final-down sneak can still never happen')

    def testDeepInItsOwnEndItUsuallyPunts(self):
        kinds, _ = self._calls(quarter=1, clock=600, ballOn=90, offScore=0, defScore=0)
        punts = sum(1 for k in kinds if k is PlayType.Punt)
        self.assertGreater(punts / len(kinds), 0.75)


class TheKick(unittest.TestCase):

    def _share(self, ballOn, leg):
        s = Scenario()
        s.situation(quarter=2, clock=600, down=4, distance=8, ballOn=ballOn)
        s.setKickerLeg('home', leg)
        g = s.game
        kicker = g.offensiveTeam.rosterDict['k']
        maxDist = kicker.maxFgDistance - g.gameRules.fgSnapDistance
        return g._fourthDownKickShare(g._estimateFgProbability(), g._coachFgThreshold(g.offensiveTeam.coach),
                                      maxDist, True)

    def testAShortKickIsTakenAndALongOneMostlyIsNot(self):
        self.assertGreater(self._share(25, 62), 0.9)        # 42 yards
        self.assertLess(self._share(41, 62), 0.3)           # 58 yards

    def testOutOfRangeIsNeverAKick(self):
        self.assertEqual(self._share(45, 55), 0.0)          # 62 yards, range 55

    def testAFutileKickIsNeverTaken(self):
        s = Scenario()
        s.situation(quarter=2, clock=600, down=4, distance=8, ballOn=20)
        self.assertEqual(s.game._fourthDownKickShare(0.95, 0.38, 60, False), 0.0)


if __name__ == '__main__':
    unittest.main()
