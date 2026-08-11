"""A team record has to survive a restart.

⚠️ THE TEAM TREE IS ONE LEVEL SHALLOWER THAN THE PLAYER TREE. A player record lives at
`players.<group>.<scope>.<stat>` (passing.game.yards); a team record lives at
`team.<scope>.<stat>` (game.pts) — there is no group. `_saveRecordCategory` walked both
with the same code, so a team row went to the database as
`category='game', scope='pts', stat_name='pts'`, while `_updateRecordFromDB` read
`records['team'][category][scope][stat]` — a level too deep, matching nothing.

So EVERY TEAM RECORD WAS SILENTLY LOST ON RESTART. The value was written, and came back
zero. Nothing raised, because a lookup that misses simply leaves the initialised 0 in
place, which reads exactly like "no record set yet".

Reported from the front page: "Buffalo Buffalo set the single-game team points record at
24", previous 8 — the day after "Georgia Classics set the single-game team points record
at 42" had been announced. A 24 could only be a record against a table that had forgotten
the 42.

Measured before the fix: save 42 → reload 0, while a player record saved 411 and reloaded
411. That isolation is what pointed at the shared walker rather than at the record checks,
which compare correctly.

Run: .venv/bin/python test_team_record_persistence.py
"""

import os
import sys
import shutil
import sqlite3
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import logging
logging.disable(logging.CRITICAL)

REPO = os.path.dirname(os.path.abspath(__file__))


class TeamRecordPersistenceTests(unittest.TestCase):
    """Each test round-trips through a REAL database file, because the fault was in the
    round trip. A unit test over the tree alone would have passed throughout."""

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix='floos-records-')
        src = os.path.join(REPO, 'data', 'floosball.db')
        dst = os.path.join(self.dir, 'floosball.db')
        if os.path.exists(src):
            shutil.copy(src, dst)
        os.environ['DATABASE_DIR'] = self.dir
        # The connection module reads DATABASE_DIR at import time, so it has to be
        # imported fresh per test directory.
        for mod in [m for m in list(sys.modules) if m.startswith(('database', 'managers', 'service_container'))]:
            del sys.modules[mod]
        self._clearRecords(dst)

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)
        os.environ.pop('DATABASE_DIR', None)

    @staticmethod
    def _clearRecords(path):
        if not os.path.exists(path):
            return
        conn = sqlite3.connect(path)
        try:
            conn.execute('DELETE FROM records')
            conn.commit()
        except sqlite3.OperationalError:
            pass
        finally:
            conn.close()

    def _manager(self):
        from service_container import ServiceContainer
        from managers.recordManager import RecordManager
        return RecordManager(ServiceContainer())

    def testATeamRecordSurvivesTheRoundTrip(self):
        """THE REGRESSION, in the terms it was reported: a team points record set, then
        the process restarts, and the record is still there."""
        rm = self._manager()
        rm.getRecords()['team']['game']['pts'].update(
            {'value': 42, 'name': 'Georgia Classics', 'id': 7})
        rm.saveRecordsToFile()

        reloaded = self._manager()
        reloaded.loadRecordsFromFile()
        self.assertEqual(reloaded.getRecords()['team']['game']['pts']['value'], 42,
                         'the team points record was lost on reload — a lesser score '
                         'will now be announced as a new record')

    def testEveryTeamScopeSurvives(self):
        """`game` was the one reported; the same walker writes `season` and `allTime`."""
        rm = self._manager()
        records = rm.getRecords()
        records['team']['game']['yards'].update({'value': 491, 'name': 'GAC', 'id': 7})
        records['team']['season']['pts'].update({'value': 620, 'name': 'GAC', 'id': 7})
        records['team']['allTime']['wins'].update({'value': 14, 'name': 'GAC', 'id': 7})
        rm.saveRecordsToFile()

        reloaded = self._manager()
        reloaded.loadRecordsFromFile()
        after = reloaded.getRecords()['team']
        self.assertEqual(after['game']['yards']['value'], 491)
        self.assertEqual(after['season']['pts']['value'], 620)
        self.assertEqual(after['allTime']['wins']['value'], 14)

    def testPlayerRecordsStillSurvive(self):
        """The player path was never broken and must not be broken by the fix — it is the
        control that isolated this to the team tree."""
        rm = self._manager()
        rm.getRecords()['players']['passing']['game']['yards'].update(
            {'value': 411, 'name': 'Someone', 'id': 3})
        rm.saveRecordsToFile()

        reloaded = self._manager()
        reloaded.loadRecordsFromFile()
        self.assertEqual(
            reloaded.getRecords()['players']['passing']['game']['yards']['value'], 411)

    def testALegacyShapedRowIsStillRead(self):
        """⚠️ Rows already written by the broken save carry `category='<scope>'` and
        `scope='<stat>'`. They are the only record of what a league achieved, so the
        loader accepts both shapes and a live database recovers its team records on the
        next boot rather than starting from zero."""
        rm = self._manager()   # ensures the schema exists
        rm.getRecords()
        conn = sqlite3.connect(os.path.join(self.dir, 'floosball.db'))
        conn.execute(
            "INSERT INTO records (record_type, category, subcategory, scope, stat_name,"
            " player_id, team_id, value, season)"
            " VALUES ('Total Points', 'game', '', 'pts', 'pts', NULL, 7, 42.0, 1)")
        conn.commit()
        conn.close()

        reloaded = self._manager()
        reloaded.loadRecordsFromFile()
        self.assertEqual(reloaded.getRecords()['team']['game']['pts']['value'], 42,
                         'a record written by the broken save is not recovered')


if __name__ == '__main__':
    unittest.main(verbosity=2)
