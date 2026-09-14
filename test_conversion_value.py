"""In Q4 the post-TD try is chosen on win value, with the sim's own odds.

⚠️ THE OLD CHART ONLY EVER LET A TRAILING TEAM GO, AND LET IT GO ALMOST EVERYWHERE.
Leading teams never went for two, though up 1 (make it 3, a field goal only ties) and up
5 (make it 7, a touchdown only ties) are the plainest calls in football — the NFL goes
there essentially every time in Q4 — and one-score deficits went for two ~65% of the time
on a flat rule, including down 3, where the kick already leaves a field goal to win.

⚠️ THE SIM'S ODDS, NOT THE NFL'S (owner, 2026-09-14): two-point tries convert ~70% here,
so the chart is more aggressive than the NFL's. Q4 only — at 70% the model would go for
two on nearly every touchdown when plenty of game is left.

⚠️ UNDER THE CONVERSION LADDER THERE IS NO KICK and the decision is WHICH RUNG (2-5
points). In Q4 the same model picks the rung that best serves the score.

Run: .venv/bin/python test_conversion_value.py
"""
import os
import sys
import unittest
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import logging
logging.disable(logging.CRITICAL)

from scenario import Scenario  # noqa: E402
from game_rules import GameRules  # noqa: E402

N = 300


def picks(margin, quarter=4, clock=90, rules=None):
    s = Scenario(gameRules=rules)
    s.situation(quarter=quarter, clock=clock, offScore=21 + max(0, margin),
                defScore=21 + max(0, -margin))
    g = s.game
    return [g._chooseConversion(g.offensiveTeam) for _ in range(N)]


def goRate(margin, **kw):
    return sum(p['kind'] == 'go' for p in picks(margin, **kw)) / N


class TheStandardChart(unittest.TestCase):

    def testLeadingTeamsGoWhereTheExtraPointMovesAKeyNumber(self):
        self.assertGreater(goRate(1), 0.85, 'up 1 does not go for up 3')
        self.assertGreater(goRate(5), 0.85, 'up 5 does not go for up 7')

    def testLeadingTeamsKickWhereItDoesNot(self):
        self.assertLess(goRate(3), 0.1)
        self.assertLess(goRate(0), 0.1)

    def testDominatedTriesAreGoneLate(self):
        """Down 3: the kick leaves a field goal to win, the make can do no better, and a
        miss leaves a field goal only to tie. (Down 7 is NOT in here: after the score the
        opponent possesses first, and the try insures against a field goal of theirs —
        down 8 is still tied up by a touchdown and two, down 9 is not — so it is a close
        call that turns on the kicker's extra-point reliability.)"""
        self.assertLess(goRate(-3), 0.1)

    def testTheTyingTryIsTaken(self):
        self.assertGreater(goRate(-2), 0.85)

    def testBeforeTheFourthQuarterItKicks(self):
        self.assertEqual(goRate(1, quarter=3, clock=600), 0.0)
        self.assertEqual(goRate(-2, quarter=2, clock=600), 0.0)


class TheLadder(unittest.TestCase):

    def _rules(self):
        r = GameRules()
        r.conversionLadderEnabled = True
        return r

    def testThereIsNoKick(self):
        self.assertTrue(all(p['kind'] == 'go' for p in picks(1, rules=self._rules())))

    def testQ4PicksTheRungThatFitsTheScore(self):
        """Down 2 wants a rung that takes the lead, not merely the one a bold coach reaches
        for; up 1 wants one that makes it a field goal-plus lead."""
        down2 = Counter(p['points'] for p in picks(-2, rules=self._rules())).most_common(1)[0][0]
        self.assertGreaterEqual(down2, 3)
        up1 = Counter(p['points'] for p in picks(1, rules=self._rules())).most_common(1)[0][0]
        self.assertGreaterEqual(1 + up1, 4)


if __name__ == '__main__':
    unittest.main()
