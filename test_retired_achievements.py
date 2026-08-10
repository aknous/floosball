"""A retired achievement accrues nothing, ever.

Retiring hides a badge from anyone who has not already earned it, and keeps it on the
shelf for anyone who has. What it did NOT do was stop progress being recorded, so a
retired achievement with a live hook still granted its floobits and fired an unlock
toast for a badge the UI never shows.

⚠️ Not hypothetical. `arsenal` was retired with two of its hooks still in place, saved
only by the buy handler happening to reject the powerup they key off. `recordProgress`
is now the single place that knows, which is the point of having the flag.
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


class RetiredAchievementTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.tmp.close()
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from database.models import Base, Achievement, User
        import managers.achievementManager as am

        self.am = am
        self.engine = create_engine(f'sqlite:///{self.tmp.name}')
        Base.metadata.create_all(bind=self.engine)
        self.session = sessionmaker(bind=self.engine)()

        self.session.add(User(id=1, clerk_id='c1', email='c1@example.com'))
        self.session.add(Achievement(
            key='live_one', name='Live One', description='A live one.',
            category='onboarding', scope='once',
            target=1, sort_order=1, retired=False,
            reward_config={'floobits': 25, 'packs': [], 'powerups': [], 'deferred': False}))
        self.session.add(Achievement(
            key='retired_one', name='Retired One', description='A retired one.',
            category='onboarding', scope='once',
            target=1, sort_order=2, retired=True,
            reward_config={'floobits': 25, 'packs': [], 'powerups': [], 'deferred': False}))
        self.session.commit()

    def tearDown(self):
        self.session.close()
        self.engine.dispose()
        os.unlink(self.tmp.name)

    def userRows(self, key):
        from database.models import UserAchievement, Achievement
        return (self.session.query(UserAchievement)
                .join(Achievement, UserAchievement.achievement_id == Achievement.id)
                .filter(Achievement.key == key).all())

    def testALiveAchievementStillCompletes(self):
        self.assertIsNotNone(self.am.recordProgress(self.session, 1, 'live_one', absolute=1))

    def testARetiredAchievementNeverCompletes(self):
        self.assertIsNone(self.am.recordProgress(self.session, 1, 'retired_one', absolute=1))

    def testARetiredAchievementRecordsNoProgressAtAll(self):
        # Not merely "does not complete" — it must not leave a progress row behind
        # either, or the badge reappears the moment it is un-retired.
        self.am.recordProgress(self.session, 1, 'retired_one', absolute=1)
        self.assertEqual(self.userRows('retired_one'), [])

    def testARetiredSecretDoesNotUnlock(self):
        # unlockSecret delegates to recordProgress, so one guard covers both paths.
        self.assertIsNone(self.am.unlockSecret(self.session, 1, 'retired_one'))

    def testAnUnknownKeyIsStillSafe(self):
        self.assertIsNone(self.am.recordProgress(self.session, 1, 'no_such_key'))

    def testRepeatedCallsOnARetiredAchievementStayInert(self):
        for _ in range(5):
            self.assertIsNone(self.am.recordProgress(self.session, 1, 'retired_one'))
        self.assertEqual(self.userRows('retired_one'), [])


class FieldGeneralRetirementTests(unittest.TestCase):
    """Field General and Deck Builder fired off ONE condition, one after the other."""

    def testFieldGeneralIsSeededRetired(self):
        import database.connection as conn
        seeds = self.seedRows(conn)
        self.assertTrue(seeds['field_general'].get('retired'),
                        'Field General must ship retired')

    def testDeckBuilderIsTheSurvivor(self):
        import database.connection as conn
        seeds = self.seedRows(conn)
        self.assertFalse(seeds['deck_builder'].get('retired', False),
                         'Deck Builder is what actually happens now')

    def testTheEquipHandlerNoLongerFiresBothHooks(self):
        source = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                   'api', 'main.py')).read()
        self.assertNotIn('_am.onFantasyRosterSet(', source)

    def testTheRetiredHookIsGone(self):
        import managers.achievementManager as am
        self.assertFalse(hasattr(am, 'onFantasyRosterSet'))

    def seedRows(self, conn):
        """Pull the seeded achievement dicts straight out of the source.

        Read from the module rather than a live DB so the assertion is about what
        ships, not about whatever a local database happens to hold.
        """
        import ast
        source = open(conn.__file__).read()
        rows = {}
        for match in ast.walk(ast.parse(source)):
            if not isinstance(match, ast.Dict):
                continue
            keys = [k.value for k in match.keys if isinstance(k, ast.Constant)]
            if 'key' not in keys or 'category' not in keys:
                continue
            try:
                row = ast.literal_eval(match)
            except ValueError:
                continue
            if row.get('key') in ('field_general', 'deck_builder'):
                rows[row['key']] = row
        return rows


if __name__ == '__main__':
    unittest.main(verbosity=2)
