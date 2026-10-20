"""A backup must never fill the volume it shares with the live DB (prod, 2026-10-20).

Run: python test_backup_space.py
"""
import os
import shutil
import sqlite3
import tempfile
import unittest
from collections import namedtuple
from unittest import mock

import backup_manager

_Usage = namedtuple('_Usage', 'total used free')


class BackupSpaceTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.db = os.path.join(self.dir, 'floosball.db')
        con = sqlite3.connect(self.db)
        con.execute("CREATE TABLE t (x TEXT)")
        con.executemany("INSERT INTO t VALUES (?)", [('x' * 200,)] * 500)
        con.commit()
        con.close()
        self.backups = os.path.join(self.dir, 'backups')
        os.makedirs(self.backups)
        self.env = mock.patch.dict(os.environ, {
            'BACKUP_DIR': self.backups, 'BACKUP_KEEP': '3', 'BACKUP_MIN_FREE_MB': '0'})
        self.env.start()
        self.path = mock.patch.object(backup_manager, '_resolveDbPath',
                                      return_value=(self.db, self.dir))
        self.path.start()

    def tearDown(self):
        self.path.stop()
        self.env.stop()
        shutil.rmtree(self.dir, ignore_errors=True)

    def _autos(self):
        return sorted(f for f in os.listdir(self.backups)
                      if backup_manager._AUTO_BACKUP_RE.match(f))

    def _seedAutos(self, n):
        for i in range(n):
            p = os.path.join(self.backups, f'floosball_2026101{i}_000000.db')
            open(p, 'wb').close()
            os.utime(p, (1_000_000 + i, 1_000_000 + i))

    def testAPlainBackupStillWritesAndPrunes(self):
        self._seedAutos(3)
        out = backup_manager.runBackupOnce()
        self.assertTrue(out and os.path.exists(out))
        self.assertEqual(len(self._autos()), 3)

    def testSkipsWhenTheCopyCannotFit(self):
        with mock.patch.object(backup_manager, '_freeBytes', return_value=10):
            self.assertIsNone(backup_manager.runBackupOnce())
        self.assertEqual(os.listdir(self.backups), [])

    def testPrunesFirstWhenThatMakesRoom(self):
        self._seedAutos(3)
        need = backup_manager._bytesNeeded(self.db)
        calls = iter([0, need, need])   # short before the prune, enough after
        with mock.patch.object(backup_manager, '_freeBytes', side_effect=lambda _p: next(calls)):
            out = backup_manager.runBackupOnce()
        self.assertTrue(out and os.path.exists(out))
        autos = self._autos()
        self.assertEqual(len(autos), 3)
        self.assertNotIn('floosball_20261010_000000.db', autos)   # the oldest went first

    def testAFailedWriteLeavesNoPartial(self):
        real = sqlite3.connect

        def failing(path, *a, **kw):
            con = real(path, *a, **kw)

            class _Con:
                def execute(self, sql, params=()):
                    if sql.startswith('VACUUM INTO'):
                        open(params[0], 'wb').write(b'half')
                        raise sqlite3.OperationalError('database or disk is full')
                    return con.execute(sql, params)

                def close(self):
                    con.close()
            return _Con()

        with mock.patch.object(backup_manager.sqlite3, 'connect', side_effect=failing):
            with self.assertRaises(sqlite3.OperationalError):
                backup_manager.runBackupOnce()
        self.assertEqual(os.listdir(self.backups), [])

    def testAnOldPartialAndItsJournalAreCleanedUp(self):
        for f in ('floosball_20261020_123031.db.partial',
                  'floosball_20261020_123031.db.partial-journal'):
            open(os.path.join(self.backups, f), 'wb').close()
        backup_manager.runBackupOnce()
        self.assertFalse([f for f in os.listdir(self.backups) if 'partial' in f])


    def testDiskStatusUsesTheSameFitTestAsTheBackup(self):
        self._seedAutos(2)
        need = backup_manager._bytesNeeded(self.db)
        with mock.patch.object(backup_manager.shutil, 'disk_usage',
                               return_value=_Usage(10_000_000, 9_000_000, need - 1)):
            st = backup_manager.diskStatus()
        self.assertFalse(st['nextBackupFits'])
        self.assertEqual(st['backupCount'], 2)
        self.assertGreater(st['dbMb'], 0)
        with mock.patch.object(backup_manager.shutil, 'disk_usage',
                               return_value=_Usage(10_000_000, 9_000_000, need)):
            self.assertTrue(backup_manager.diskStatus()['nextBackupFits'])

if __name__ == '__main__':
    unittest.main()
