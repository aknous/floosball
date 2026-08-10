"""The name pool holds one form of a lineage at a time.

Covers the two ways that invariant broke:

  1. `clear_db()` preserves `unused_names` but drops every player and coach, so a
     generational variant left behind has no parent anywhere and never will.
  2. `_seedUnusedNames` compared EXACT strings, so a pool holding "Bob Jr." looked
     to config's "Bob" like an unseen name and re-seeded the base on the next boot.
     That one forks a lineage on a healthy long-running database, no wipe needed.

Measured on the season-1 production database before the fix: 712 pooled names,
39 of them variants — 32 with the base also pooled, 7 with the base worn by a
player or a coach.
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


class NamePoolTests(unittest.TestCase):
    def setUp(self):
        # A private database per test. connection.py binds its engine at import,
        # so the swap has to happen on the module's own SessionLocal.
        self.tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.tmp.close()
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        import database.connection as conn
        from database.models import Base

        self.conn = conn
        self.engine = create_engine(f'sqlite:///{self.tmp.name}')
        Base.metadata.create_all(bind=self.engine)
        self._savedSession = conn.SessionLocal
        conn.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        self.session = conn.SessionLocal()

    def tearDown(self):
        self.session.close()
        self.conn.SessionLocal = self._savedSession
        self.engine.dispose()
        os.unlink(self.tmp.name)

    def pool(self):
        from database.models import UnusedName
        s = self.conn.SessionLocal()
        try:
            return sorted(r.name for r in s.query(UnusedName).all())
        finally:
            s.close()

    def seedPool(self, *names):
        from database.models import UnusedName
        for n in names:
            self.session.add(UnusedName(name=n))
        self.session.commit()

    # -- baseName ---------------------------------------------------------

    def testBaseNameWalksTheWholeLadder(self):
        base = self.conn.baseName
        for variant in ('Bob Vance', 'Bob Vance Jr.', 'Bob Vance III', 'Bob Vance IV',
                        'Bob Vance V', 'Bob Vance VIII', 'Bob Vance IX', 'Bob Vance X',
                        'Bob Vance XI'):
            self.assertEqual(base(variant), 'Bob Vance', variant)

    def testBaseNameDoesNotEatVIIIAsV(self):
        # "VIII" must not reduce to a stranded "III".
        self.assertEqual(self.conn.baseName('Cheshire Spacious VIII'), 'Cheshire Spacious')

    def testBaseNameUnstacksStoredLadders(self):
        self.assertEqual(self.conn.baseName('Foo Bar Jr. III'), 'Foo Bar')

    def testBaseNameLeavesRealNamesAlone(self):
        # A name is not a suffix just because it looks Roman.
        self.assertEqual(self.conn.baseName('Elvis Amigo'), 'Elvis Amigo')

    # -- _normalizeNamePool ------------------------------------------------

    def testDropsVariantWhoseBaseIsAlsoPooled(self):
        self.seedPool('Acid Del Mar', 'Acid Del Mar Jr.', 'Elvis Amigo')
        self.conn._normalizeNamePool()
        # The BASE survives: an orphaned Junior is the row that reads wrong.
        self.assertEqual(self.pool(), ['Acid Del Mar', 'Elvis Amigo'])

    def testDropsVariantWhoseBaseIsWornByAPlayer(self):
        from database.models import Player
        self.session.add(Player(name='Acid Del Mar', position='QB'))
        self.session.commit()
        self.seedPool('Acid Del Mar Jr.', 'Elvis Amigo')
        self.conn._normalizeNamePool()
        self.assertEqual(self.pool(), ['Elvis Amigo'])

    def testDropsVariantWhoseBaseIsWornByACoach(self):
        from database.models import Coach
        self.session.add(Coach(name='Basil Paracelsus'))
        self.session.commit()
        self.seedPool('Basil Paracelsus Jr.', 'Elvis Amigo')
        self.conn._normalizeNamePool()
        self.assertEqual(self.pool(), ['Elvis Amigo'])

    def testDropsPooledBaseWhenTheJuniorIsAlreadyPlaying(self):
        # The reverse of the case above, and 11 rows of it on production. The son is
        # on a roster, so the father must not debut beside him. Nothing is lost: when
        # the son retires the lineage goes up a rung and returns to the pool.
        from database.models import Player
        self.session.add(Player(name='Bob Vance Jr.', position='WR'))
        self.session.commit()
        self.seedPool('Bob Vance', 'Elvis Amigo')
        self.conn._normalizeNamePool()
        self.assertEqual(self.pool(), ['Elvis Amigo'])

    def testResetLaddersLeavesARealNameAlone(self):
        # Collapsing is about the SUFFIX, not about rewriting names wholesale.
        self.seedPool('Elvis Amigo')
        self.conn._normalizeNamePool(resetLadders=True)
        self.assertEqual(self.pool(), ['Elvis Amigo'])

    def testResetLaddersStillPrefersAnExistingBase(self):
        self.seedPool('Acid Del Mar Jr.', 'Acid Del Mar')
        self.conn._normalizeNamePool(resetLadders=True)
        self.assertEqual(self.pool(), ['Acid Del Mar'])

    def testKeepsALegitimateRecycledVariant(self):
        # The parent retired and the name went up a rung. Nothing else holds the
        # lineage, so this is the pool working as designed and must not be touched.
        self.seedPool('Freed Marinara Jr.', 'Elvis Amigo')
        self.conn._normalizeNamePool()
        self.assertEqual(self.pool(), ['Elvis Amigo', 'Freed Marinara Jr.'])

    def testIsIdempotent(self):
        self.seedPool('Acid Del Mar', 'Acid Del Mar Jr.')
        self.conn._normalizeNamePool()
        first = self.pool()
        self.conn._normalizeNamePool()
        self.assertEqual(self.pool(), first)

    def testBaseSurvivesRegardlessOfInsertOrder(self):
        # The variant was inserted first; row order must not decide the winner.
        self.seedPool('Acid Del Mar Jr.', 'Acid Del Mar')
        self.conn._normalizeNamePool()
        self.assertEqual(self.pool(), ['Acid Del Mar'])

    def testCollapsesAWholeLineage(self):
        self.seedPool('Bob Vance', 'Bob Vance Jr.', 'Bob Vance III', 'Bob Vance IV')
        self.conn._normalizeNamePool()
        self.assertEqual(self.pool(), ['Bob Vance'])

    # -- _collapseLiveGenerationalNames ------------------------------------

    def livePlayerNames(self):
        from database.models import Player
        s = self.conn.SessionLocal()
        try:
            return sorted(p.name for p in s.query(Player).all())
        finally:
            s.close()

    def addPlayers(self, *names):
        from database.models import Player
        for n in names:
            self.session.add(Player(name=n, position='QB'))
        self.session.commit()

    def testCollapseDropsTheSuffixFromLivePlayers(self):
        self.addPlayers('Freed Marinara Jr.', 'Elvis Amigo')
        self.conn._collapseLiveGenerationalNames()
        self.assertEqual(self.livePlayerNames(), ['Elvis Amigo', 'Freed Marinara'])

    def testCollapseSkipsWhenTheBaseIsAlreadyOnTheField(self):
        # THE PRODUCTION CASE, three of them: the fork generated both forms of a
        # lineage into the same league. Renaming would put two identical names on
        # the field, which is worse than the suffix.
        self.addPlayers('Mochi Pushpin', 'Mochi Pushpin Jr.')
        self.conn._collapseLiveGenerationalNames()
        self.assertEqual(self.livePlayerNames(), ['Mochi Pushpin', 'Mochi Pushpin Jr.'])

    def testCollapseSkipsWhenTheBaseIsWornByACoach(self):
        from database.models import Coach
        self.session.add(Coach(name='Sarasota Speedrun'))
        self.session.commit()
        self.addPlayers('Sarasota Speedrun Jr.')
        self.conn._collapseLiveGenerationalNames()
        self.assertEqual(self.livePlayerNames(), ['Sarasota Speedrun Jr.'])

    def testCollapseAlsoRenamesCoaches(self):
        from database.models import Coach
        self.session.add(Coach(name='Sarasota Speedrun Jr.'))
        self.session.commit()
        self.conn._collapseLiveGenerationalNames()
        s = self.conn.SessionLocal()
        try:
            self.assertEqual([c.name for c in s.query(Coach).all()], ['Sarasota Speedrun'])
        finally:
            s.close()

    def testCollapseRemovesTheNowDuplicatePooledCopy(self):
        self.seedPool('Freed Marinara', 'Elvis Amigo')
        self.addPlayers('Freed Marinara Jr.')
        self.conn._collapseLiveGenerationalNames()
        self.assertEqual(self.pool(), ['Elvis Amigo'])

    def testCollapseRunsOnlyOnce(self):
        # THE SAFETY MECHANISM. A player named "Bob Jr." is normally correct — the
        # ladder exists so a newcomer can debut as the next generation. A second
        # run must not touch one.
        self.addPlayers('Freed Marinara Jr.')
        self.conn._collapseLiveGenerationalNames()
        self.addPlayers('Bob Vance Jr.')
        self.conn._collapseLiveGenerationalNames()
        self.assertEqual(self.livePlayerNames(), ['Bob Vance Jr.', 'Freed Marinara'])

    def testCollapseStampsItsMarkerEvenWithNothingToDo(self):
        from database.models import AppSetting
        self.conn._collapseLiveGenerationalNames()
        s = self.conn.SessionLocal()
        try:
            self.assertIsNotNone(
                s.query(AppSetting).filter(AppSetting.key == self.conn._COLLAPSE_MARKER).first())
        finally:
            s.close()

    def testCollapseTwoJuniorsOfTheSameLineageKeepsOne(self):
        # Only one can take the base; the second would collide with the first.
        self.addPlayers('Bob Vance Jr.', 'Bob Vance III')
        self.conn._collapseLiveGenerationalNames()
        self.assertEqual(self.livePlayerNames(), ['Bob Vance', 'Bob Vance III'])

    # -- _seedUnusedNames --------------------------------------------------

    def seedFromConfig(self, names):
        """Run the seeder with a stubbed config."""
        import config_manager

        class _Cfg(dict):
            pass
        saved = config_manager.get_config
        config_manager.get_config = lambda: {'players': names}
        try:
            self.conn._seedUnusedNames()
        finally:
            config_manager.get_config = saved

    def testSeederDoesNotReviveTheParentOfAPooledVariant(self):
        # THE REGRESSION. "Bob Vance Jr." is circulating; config's "Bob Vance" must
        # not be re-seeded alongside it, or father and son both wait to debut.
        self.seedPool('Bob Vance Jr.')
        self.seedFromConfig(['Bob Vance', 'Elvis Amigo'])
        self.assertEqual(self.pool(), ['Bob Vance Jr.', 'Elvis Amigo'])

    def testSeederDoesNotReviveTheParentOfALivePlayer(self):
        from database.models import Player
        self.session.add(Player(name='Bob Vance Jr.', position='RB'))
        self.session.commit()
        self.seedFromConfig(['Bob Vance', 'Elvis Amigo'])
        self.assertEqual(self.pool(), ['Elvis Amigo'])

    def testSeederStillAddsGenuinelyNewNames(self):
        self.seedPool('Bob Vance')
        self.seedFromConfig(['Bob Vance', 'Elvis Amigo', 'Acid Del Mar'])
        self.assertEqual(self.pool(), ['Acid Del Mar', 'Bob Vance', 'Elvis Amigo'])

    def testSeederRepeatedBootsDoNotGrowThePool(self):
        # The fork was per-boot, so a stable pool across restarts is the assertion
        # that actually proves it is closed.
        self.seedPool('Bob Vance Jr.')
        names = ['Bob Vance', 'Elvis Amigo']
        for _ in range(5):
            self.seedFromConfig(names)
        self.assertEqual(self.pool(), ['Bob Vance Jr.', 'Elvis Amigo'])

    def testFreshStartOrderRepairsThenSeeds(self):
        # clear_db()'s order: normalize the preserved pool, then merge config in.
        # Reproduces the production signature — a wiped league whose pool still
        # holds Juniors of names config is about to re-seed.
        self.seedPool('Acid Del Mar Jr.', 'Cheshire Spacious III', 'Elvis Amigo')
        self.conn._normalizeNamePool(resetLadders=True)
        self.seedFromConfig(['Acid Del Mar', 'Cheshire Spacious', 'Elvis Amigo'])
        # Every lineage present exactly once. The variants had no parent left
        # after the wipe, so the base is what circulates.
        self.assertEqual(self.pool(), ['Acid Del Mar', 'Cheshire Spacious', 'Elvis Amigo'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
