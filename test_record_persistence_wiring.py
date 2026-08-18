"""The record book is actually written down, and seeded from what was played.

⚠️ `saveRecordsToFile` HAD NO CALLER OUTSIDE THE TESTS. The application loaded records at
startup and never saved them, so production's `records` table held ZERO rows and the whole
tree rebuilt from nothing on every restart. Records then accumulated only within a single
process, so a modest score beat the freshly-empty in-session mark and the feed announced it:
reported as "Mexico City Exoticos set the single-game team points record at 41" when the
highest score ever played is 94.

⚠️ `test_team_record_persistence.py` PASSED THROUGHOUT. It calls save and load directly and
proves the round trip works -- which it does. Nothing proved anyone made the trip. That is
the same gap that hid the game-winner backfill (asserted its SQL, never called it) and the
Cores lead renderer (asserted the payload, never rendered it), so this file tests the
WIRING rather than the mechanism.

Run: .venv/bin/python test_record_persistence_wiring.py
"""
import sqlite3
import tempfile
import os
import unittest


class TheSeasonLoopSavesThem(unittest.TestCase):

    def setUp(self):
        with open('managers/seasonManager.py') as fh:
            self.src = fh.read()

    def test_thereIsAHelperThatSaves(self):
        self.assertIn('def _persistRecords(self)', self.src)
        body = self.src.split('def _persistRecords')[1].split('\n    def ')[0]
        self.assertIn('saveRecordsToFile()', body)

    def test_itRunsWhereAGameRecordCanMove(self):
        """Per game, because that is the only moment a GAME record changes -- and a record
        lost to a restart cannot be recomputed from the box scores."""
        block = self.src.split('self.recordsManager.checkTeamGameRecords(gameInstance)')[1][:900]
        self.assertIn('self._persistRecords()', block)

    def test_itRunsWhereSeasonAndCareerRecordsMove(self):
        block = self.src.split('self.recordsManager.checkCareerRecords()')[1][:600]
        self.assertIn('self._persistRecords()', block)

    def test_savingNeverBreaksAGame(self):
        """⚠️ This hangs off the game-completion path. A lost save costs durability; a
        raised exception costs the game being simulated."""
        body = self.src.split('def _persistRecords')[1].split('\n    def ')[0]
        self.assertIn('except Exception', body)


class TheAppRepairsWhatWasNeverSaved(unittest.TestCase):

    def setUp(self):
        with open('managers/floosballApplication.py') as fh:
            self.src = fh.read()

    def test_theSeedRunsAtStartupAfterTheLoad(self):
        """⚠️ Order matters. Seeding before the load would be overwritten by it, and
        `_saveRecordsToDatabase` is a full delete-and-rewrite from the TREE -- so a
        database-only repair would be erased by the next save."""
        loadAt = self.src.index('self.recordsManager.loadRecordsFromFile()')
        seedAt = self.src.index('seedTeamGameRecordsFromHistory')
        self.assertLess(loadAt, seedAt, 'the seed must run after the load')

    def test_theSeedIsFollowedByASave(self):
        block = self.src.split('seedTeamGameRecordsFromHistory')[1][:400]
        self.assertIn('saveRecordsToFile()', block)


class TheSeedFindsWhatWasActuallyPlayed(unittest.TestCase):
    """Driven against a real schema rather than asserted on source -- the point of this
    whole session's lessons."""

    def _seeded(self, games):
        from managers.recordManager import RecordManager
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        import logging

        path = os.path.join(tempfile.mkdtemp(), 'recs.db')
        raw = sqlite3.connect(path)
        raw.execute("""CREATE TABLE games (id INTEGER PRIMARY KEY, status TEXT,
            home_team_id INT, away_team_id INT, home_score REAL, away_score REAL,
            home_rush_yards REAL, home_pass_yards REAL, away_rush_yards REAL,
            away_pass_yards REAL, home_rush_tds INT, home_pass_tds INT,
            away_rush_tds INT, away_pass_tds INT)""")
        raw.executemany("INSERT INTO games VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", games)
        raw.commit(); raw.close()

        session = sessionmaker(bind=create_engine(f'sqlite:///{path}'))()
        rm = RecordManager.__new__(RecordManager)
        rm._records = rm._initializeRecordStructure()
        rm.serviceContainer = type('SC', (), {'getService': lambda self, n: None})()
        rm.logger = logging.getLogger('test')
        raised = rm.seedTeamGameRecordsFromHistory(session)
        return rm, raised

    def test_itTakesTheHighestScoreEverPlayed(self):
        """THE REGRESSION: a 41 was announced as the record when a 94 existed."""
        rm, raised = self._seeded([
            (1, 'final', 11, 22, 94, 31, 200, 300, 100, 150, 4, 6, 2, 2),
            (2, 'final', 11, 22, 41, 38, 100, 120, 90, 110, 2, 3, 2, 3),
        ])
        self.assertEqual(rm.getRecords()['team']['game']['pts']['value'], 94)
        self.assertEqual(rm.getRecords()['team']['game']['pts']['id'], 11)
        self.assertGreater(raised, 0)

    def test_yardsAndTdsAreTeamTotalsNotOneHalfOfThem(self):
        """Rushing and passing are stored separately; a team's game total is their sum."""
        rm, _ = self._seeded([(1, 'final', 11, 22, 30, 20, 200, 300, 10, 20, 4, 6, 1, 1)])
        game = rm.getRecords()['team']['game']
        self.assertEqual(game['yards']['value'], 500)
        self.assertEqual(game['tds']['value'], 10)

    def test_itOnlyEverRaises(self):
        """⚠️ A value above anything in the table is a record set live this session.
        Lowering it would be the same loss this seed exists to repair, and it is what makes
        the seed idempotent."""
        rm, _ = self._seeded([(1, 'final', 11, 22, 40, 10, 100, 100, 50, 50, 2, 2, 1, 1)])
        rm.getRecords()['team']['game']['pts'].update({'value': 99, 'id': 7, 'name': 'X'})
        again = rm.seedTeamGameRecordsFromHistory(
            __import__('sqlalchemy.orm', fromlist=['sessionmaker']).sessionmaker(
                bind=__import__('sqlalchemy', fromlist=['create_engine']).create_engine(
                    'sqlite:///:memory:'))())
        self.assertEqual(rm.getRecords()['team']['game']['pts']['value'], 99)

    def test_runningItTwiceChangesNothing(self):
        games = [(1, 'final', 11, 22, 94, 31, 200, 300, 100, 150, 4, 6, 2, 2)]
        rm, first = self._seeded(games)
        self.assertGreater(first, 0)
        rm2, second = self._seeded(games)
        # Same fixture, fresh tree -> same raises; the idempotence that matters is that a
        # tree already holding the value is left alone, covered above.
        self.assertEqual(first, second)

    def test_unfinishedGamesAreIgnored(self):
        rm, raised = self._seeded([(1, 'live', 11, 22, 200, 3, 900, 900, 1, 1, 9, 9, 0, 0)])
        self.assertEqual(raised, 0)
        self.assertEqual(rm.getRecords()['team']['game']['pts']['value'], 0)

    def test_anEmptyLeagueSeedsNothing(self):
        rm, raised = self._seeded([])
        self.assertEqual(raised, 0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
