"""COMPLACENT needs a record to be complacent about.

The state has two triggers that are meant to PARTITION the season — pedigree (top-10%
ELO) before enough games exist to judge a record, the record itself afterwards. The
record path had no games floor, so both ran from week 1 and `winPct >= 0.70` was
satisfied by a 1-0 record.

⚠️ Measured on production one game into a season: 12 of the 16 winners came back
COMPLACENT — 38% of the league, every division's leaders wearing "Winning, but
cracking" off a single result. A team that has won its only game has nothing banked
to coast on, which is the premise of the state.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from api_response_builders import TeamResponseBuilder, COMPLACENT_HANDOVER_GAMES


class FakeAttributes:
    """Attribute bag driving the vulnerability / resolve composites."""

    def __init__(self, discipline=80, pressureHandling=0, focus=80, attitude=80,
                 resilience=80, creativity=80):
        self.discipline = discipline
        self.pressureHandling = pressureHandling
        self.focus = focus
        self.attitude = attitude
        self.resilience = resilience
        self.creativity = creativity


class FakePlayer:
    def __init__(self, **kw):
        self.attributes = FakeAttributes(**kw)


class FakeTeam:
    def __init__(self, wins, losses, streak, vulnerable=True, elo=1500):
        self.seasonTeamStats = {'wins': wins, 'losses': losses, 'streak': streak}
        self.elo = elo
        # A vulnerable roster clears the 0.06 bar comfortably; a solid one does not.
        # Production's median team sits at 0.155, so "vulnerable" is the common case.
        attrs = dict(discipline=64, focus=64, attitude=64) if vulnerable else {}
        self.rosterDict = {f'p{i}': FakePlayer(**attrs) for i in range(6)}


def state(wins, losses, streak, **kw):
    return TeamResponseBuilder.computeFormState(FakeTeam(wins, losses, streak, **kw))


class ComplacentTests(unittest.TestCase):
    """`_isPedigreed` returns False without a live app, so these exercise the record
    path in isolation — which is the one that fired on production."""

    def testAOneAndZeroTeamIsNotComplacent(self):
        # THE REGRESSION, exactly as production hit it.
        self.assertNotEqual(state(1, 0, 1), 'COMPLACENT')

    def testNoWinnerIsComplacentAfterASingleRound(self):
        # Every shape a club can have one game in.
        for wins, losses, streak in ((1, 0, 1), (0, 1, -1)):
            self.assertNotEqual(state(wins, losses, streak), 'COMPLACENT',
                                f'{wins}-{losses}')

    def testAnUndefeatedShortRecordIsNotComplacent(self):
        # 0.70+ winPct the whole way, but nothing banked yet.
        for games in range(1, COMPLACENT_HANDOVER_GAMES):
            self.assertNotEqual(state(games, 0, min(games, 2)), 'COMPLACENT',
                                f'{games}-0')

    def testItStillFiresOnceTheRecordIsReal(self):
        # 6-2 at the handover: strong record, not currently surging.
        self.assertEqual(state(6, 2, 1), 'COMPLACENT')

    def testASurgingTeamIsHotNotComplacent(self):
        # streak >= 3 is momentum, not coasting — the gate that separates the two.
        self.assertEqual(state(6, 2, 3), 'HOT_STREAK')

    def testASolidRosterIsNotComplacentOnRecordAlone(self):
        # The composite is a required term, not decoration.
        self.assertNotEqual(state(6, 2, 1, vulnerable=False), 'COMPLACENT')

    def testAMiddlingRecordIsNotComplacent(self):
        self.assertNotEqual(state(4, 4, 1), 'COMPLACENT')

    def testTheHandoverIsExclusiveNotOverlapping(self):
        # One game short of the handover the record path must be silent; at it,
        # available. Pinning both sides stops the two paths drifting back together.
        self.assertNotEqual(state(COMPLACENT_HANDOVER_GAMES - 1, 0, 1), 'COMPLACENT')
        self.assertEqual(state(COMPLACENT_HANDOVER_GAMES, 0, 1), 'COMPLACENT')


class OtherStatesTests(unittest.TestCase):
    def testEarlySeasonReadsUnknownRatherThanComplacent(self):
        # With the record path closed, a 1-0 team falls through to the games<4 gate.
        self.assertEqual(state(1, 0, 1), 'UNKNOWN')

    def testASlidingWinnerStillCoolsOff(self):
        self.assertEqual(state(5, 3, -1), 'COOLING_OFF')

    def testACollapseStillSpirals(self):
        self.assertEqual(state(2, 6, -3, vulnerable=True), 'SPIRALING')

    def testTwoInARowStillReadsGettingHot(self):
        self.assertEqual(state(4, 4, 2), 'GETTING_HOT')


if __name__ == '__main__':
    unittest.main(verbosity=2)
