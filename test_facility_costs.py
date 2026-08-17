"""Facilities are never free, and a share is a share of the REAL league.

⚠️ `computeShareUnit` returned 0.0 whenever there was no previous season, and its
docstring called that "inert". It is not inert, it is FREE: season 1 showed 0F upkeep
and 0F to build, so every team could max every facility for nothing. A floor is the
difference between "the economy has not started" and "the economy does not apply".

⚠️ It also divided by a hardcoded 24 that no caller ever overrode. The league is 32,
so every share came out 33% too large and every facility 33% too expensive.
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from constants import (FACILITY_SHARE_UNIT_FLOOR, FACILITY_UPGRADE_COST_SHARES,
                       FACILITY_UPKEEP_SHARES, FACILITY_MAX_LEVEL)
from managers.facilitiesManager import (computeShareUnit, upkeepCostFloobits,
                                        upgradeCostFloobits)


class FacilityCostTests(unittest.TestCase):
    def setUp(self):
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from database.models import Base
        self.tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.tmp.close()
        self.engine = create_engine(f'sqlite:///{self.tmp.name}')
        Base.metadata.create_all(bind=self.engine)
        self.session = sessionmaker(bind=self.engine)()

    def tearDown(self):
        self.session.close()
        self.engine.dispose()
        os.unlink(self.tmp.name)

    def addTeams(self, n):
        from database.models import Team
        for i in range(n):
            self.session.add(Team(
                id=i + 1, name=f'T{i}', city=f'C{i}', abbr=f'T{i:02d}', color='#334155',
                offense_rating=80, defense_rating=80, overall_rating=80))
        self.session.commit()

    def addGrants(self, season, total, n=10):
        from database.models import CurrencyTransaction
        for i in range(n):
            self.session.add(CurrencyTransaction(
                user_id=1, amount=total // n, transaction_type='grant', season=season,
                balance_after=0))
        self.session.commit()

    # -- the floor ---------------------------------------------------------

    def testAFreshLeagueIsNotFree(self):
        # THE REGRESSION. Season 1 has no season 0 to price against.
        self.addTeams(32)
        self.assertEqual(computeShareUnit(self.session, 0), FACILITY_SHARE_UNIT_FLOOR)

    def testNoPriorSeasonStillCostsSomethingToBuild(self):
        self.addTeams(32)
        unit = computeShareUnit(self.session, 0)
        for level in range(1, FACILITY_MAX_LEVEL + 1):
            self.assertGreater(upgradeCostFloobits(level - 1, unit), 0, f'L{level}')

    def testTheTopLevelStillCostsSomethingToHold(self):
        self.addTeams(32)
        unit = computeShareUnit(self.session, 0)
        self.assertGreater(upkeepCostFloobits(FACILITY_MAX_LEVEL, unit), 0)

    def testANoneSeasonIsFlooredNotCrashing(self):
        self.addTeams(32)
        self.assertEqual(computeShareUnit(self.session, None), FACILITY_SHARE_UNIT_FLOOR)

    def testAThinSeasonIsLiftedToTheFloor(self):
        # A season that barely paid out must not price facilities below the floor.
        self.addTeams(32)
        self.addGrants(season=1, total=320)          # 10 per team
        self.assertEqual(computeShareUnit(self.session, 1), FACILITY_SHARE_UNIT_FLOOR)

    def testARealSeasonOverridesTheFloor(self):
        # Once the league earns more than the floor, the floor gets out of the way.
        self.addTeams(32)
        self.addGrants(season=1, total=32000)        # 1000 per team
        self.assertEqual(computeShareUnit(self.session, 1), 1000.0)

    # -- the team count ----------------------------------------------------

    def testTheShareDividesByTheRealTeamCount(self):
        # 32 teams, not the 24 that was hardcoded.
        self.addTeams(32)
        self.addGrants(season=1, total=32000)
        self.assertEqual(computeShareUnit(self.session, 1), 1000.0)

    def testASmallerLeagueGetsALargerShare(self):
        self.addTeams(16)
        self.addGrants(season=1, total=32000)
        self.assertEqual(computeShareUnit(self.session, 1), 2000.0)

    def testAnEmptyLeagueDoesNotDivideByZero(self):
        self.addGrants(season=1, total=32000)
        self.assertGreaterEqual(computeShareUnit(self.session, 1), FACILITY_SHARE_UNIT_FLOOR)

    def testAnExplicitTeamCountStillWins(self):
        self.addTeams(32)
        self.addGrants(season=1, total=32000)
        self.assertEqual(computeShareUnit(self.session, 1, numTeams=8), 4000.0)


class OneUserCannotPriceTheLeague(FacilityCostTests):
    """⚠️ THE SHARE UNIT IS A MEAN, AND A MEAN IS WHAT ONE OUTLIER BREAKS.

    Measured on the season-1 production database: one user earned 79,237F of a 212,614F
    faucet (37% of the league's whole season), and 89% of that came from a SINGLE week —
    1,453,601 FP in week 27, a Criticality week where Pyre's Equation and Amplify stacked.
    That one week raised the price of every facility for all 32 teams by 50%: a full
    level-5 build went 7,195F -> 10,764F. Nobody else got a Floobit richer.

    The windfall is real income for the user who earned it. It is not evidence that other
    teams can afford more, which is the only thing the share unit is trying to express.
    """

    def addUserGrants(self, season, perUser):
        """One lump per user, so the cap has real per-user rows to group over."""
        from database.models import CurrencyTransaction
        for uid, amount in enumerate(perUser, start=1):
            self.session.add(CurrencyTransaction(
                user_id=uid, amount=int(amount), transaction_type='grant',
                season=season, balance_after=0))
        self.session.commit()

    def testAWindfallDoesNotRepriceEveryoneElse(self):
        """The production shape: 29 ordinary earners and one user with a Criticality week."""
        self.addTeams(32)
        ordinary = [4000.0] * 29
        self.addUserGrants(season=1, perUser=ordinary + [79237.0])
        withSpike = computeShareUnit(self.session, 1, numTeams=32)

        self.tearDown(); self.setUp()
        self.addTeams(32)
        self.addUserGrants(season=1, perUser=ordinary + [4000.0])
        without = computeShareUnit(self.session, 1, numTeams=32)

        swing = withSpike / without - 1
        self.assertLess(swing, 0.25,
                        f'one user still moves the whole league by {swing:.0%}; '
                        f'uncapped this was +59%')

    def testTheUnitStillTracksGenuineLeagueWideGrowth(self):
        """⚠️ The cap must not flatten the economy. If EVERY user earns more, the unit has
        to rise — otherwise facilities get cheaper in real terms every season and the
        share stops meaning anything."""
        self.addTeams(32)
        self.addUserGrants(season=1, perUser=[4000.0] * 30)
        lean = computeShareUnit(self.session, 1, numTeams=32)

        self.tearDown(); self.setUp()
        self.addTeams(32)
        self.addUserGrants(season=1, perUser=[8000.0] * 30)
        rich = computeShareUnit(self.session, 1, numTeams=32)

        self.assertGreater(rich, lean * 1.8,
                           'a league that genuinely doubled its earnings must pay more')

    def testASmallLeagueIsLeftAlone(self):
        """Below the min-user floor a percentile is computed from too few points to mean
        anything, and clipping there would just lower the unit rather than de-skew it."""
        from constants import FACILITY_SHARE_CAP_MIN_USERS
        self.addTeams(4)
        perUser = [1000.0] * (FACILITY_SHARE_CAP_MIN_USERS - 2) + [50000.0]
        self.addUserGrants(season=1, perUser=perUser)
        unit = computeShareUnit(self.session, 1, numTeams=4)
        self.assertAlmostEqual(unit, sum(perUser) / 4, places=4,
                               msg='a small league must not be clipped')

    def testCappingNeverRaisesTheUnit(self):
        """A clip can only ever remove faucet, never add it."""
        from managers.facilitiesManager import _cappedFaucetTotal
        for perUser in ([100.0] * 20,
                        [100.0] * 19 + [90000.0],
                        [float(i) * 500 for i in range(1, 31)]):
            self.assertLessEqual(_cappedFaucetTotal(perUser), sum(perUser) + 1e-9)

    def testAnEvenLeagueIsBarelyTouched(self):
        """Where nobody is an outlier there is nothing to clip, so the unit should be
        essentially the plain mean — the cap must be inert on a healthy distribution."""
        from managers.facilitiesManager import _cappedFaucetTotal
        even = [5000.0] * 30
        self.assertAlmostEqual(_cappedFaucetTotal(even), sum(even), places=4)


if __name__ == '__main__':
    unittest.main(verbosity=2)
