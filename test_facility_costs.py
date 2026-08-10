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


if __name__ == '__main__':
    unittest.main(verbosity=2)
