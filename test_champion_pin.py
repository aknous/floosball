"""A champion holds the top of the news feed through the offseason, then lets go.

⚠️ THE ONLY UNPIN LIVED IN THE PUBLISHER. `_publishChampionNews` pins the Floos Bowl
winner and unpins the previous season's row — which means the release only happened when
the NEXT champion was crowned, about 32 weeks later. Reported as the past season's
champion being stuck at the top of the feed while a new season was under way.

The pin's own docstring explains the window it is for: the offseason keeps publishing
after the bowl, so a rule change or a Cores line would push the biggest result of the
year off the front page within a day. That argument ends when real games resume.

Run: .venv/bin/python test_champion_pin.py
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


class FakeQuery:
    def __init__(self, store): self.store = store; self._f = []
    def filter(self, *criteria): return self
    def update(self, values, synchronize_session=False):
        # ⚠️ A BULK UPDATE TAKES THE WRITE LOCK WHETHER OR NOT IT MATCHES A ROW, which is
        # the fact this whole file turns on, so the fake takes it unconditionally too.
        self.store['session'].open = True
        # Emulate the real filter: pinned champions from earlier seasons only.
        hit = [r for r in self.store['rows']
               if r['event_type'] == 'floosbowl_champion' and r['pinned']
               and r['season'] < self.store['season']]
        for r in hit:
            r['pinned'] = values['pinned']
        return len(hit)


class FakeSession:
    def __init__(self, rows, season):
        self.store = {'rows': rows, 'season': season, 'session': self}
        self.commits = 0
        self.rollbacks = 0
        # True while an executed statement is holding SQLite's single write lock.
        self.open = False
    def query(self, model): return FakeQuery(self.store)
    def commit(self): self.commits += 1; self.open = False
    def rollback(self): self.rollbacks += 1; self.open = False


def manager(rows, season):
    from managers.seasonManager import SeasonManager
    sm = SeasonManager.__new__(SeasonManager)
    sm.db_session = FakeSession(rows, season)
    return sm


class ChampionPinTests(unittest.TestCase):

    def rows(self):
        return [
            {'season': 3, 'event_type': 'floosbowl_champion', 'pinned': True},
            {'season': 2, 'event_type': 'floosbowl_champion', 'pinned': False},
            {'season': 3, 'event_type': 'admin_post', 'pinned': True},
        ]

    def testLastSeasonsChampionIsReleased(self):
        rows = self.rows()
        manager(rows, 4)._unpinStaleChampions(4)
        champ = [r for r in rows if r['event_type'] == 'floosbowl_champion' and r['season'] == 3][0]
        self.assertFalse(champ['pinned'], "the previous champion still holds the lead")

    def testAnAdminPinIsUntouched(self):
        """⚠️ Pinning is also an admin gesture. Season start must not sweep the board."""
        rows = self.rows()
        manager(rows, 4)._unpinStaleChampions(4)
        admin = [r for r in rows if r['event_type'] == 'admin_post'][0]
        self.assertTrue(admin['pinned'], "an admin pin was cleared by the season rollover")

    def testThisSeasonsChampionSurvivesARestart(self):
        """⚠️ `startNewSeason` also runs on resume. Unpinning unconditionally there would
        drop the pin the moment the server bounced mid-season."""
        rows = [{'season': 4, 'event_type': 'floosbowl_champion', 'pinned': True}]
        manager(rows, 4)._unpinStaleChampions(4)
        self.assertTrue(rows[0]['pinned'],
                        "a champion from the CURRENT season must keep its pin")

    def testItIsIdempotent(self):
        """⚠️ IDEMPOTENT IN THE ROWS, WHICH IS THE PROPERTY THAT MATTERS.

        This used to assert the COMMIT COUNT did not move on a second pass, treating a
        commit as a proxy for a write — and that proxy encoded a bug. A bulk update takes
        the write lock whether or not it matches anything, so the second pass MUST still
        commit; that commit is the RELEASE, not a write. Gating it on `changed` left the
        shared session holding an open write transaction in exactly the case where there
        was nothing to do, and a fresh league (which has no champion to unpin, every
        time) then died with "database is locked" before week 1 existed.
        """
        rows = self.rows()
        sm = manager(rows, 4)
        sm._unpinStaleChampions(4)
        after = [dict(r) for r in rows]
        sm._unpinStaleChampions(4)
        self.assertEqual(after, rows, "a second pass changed a row")

    def testItAlwaysReleasesTheWriteLock(self):
        """⚠️ THE ZERO-ROW CASE IS THE ONE THAT BROKE, and it is the case a fresh league
        is always in. See test_champion_unpin_lock.py, which asserts the same thing
        against a real SQLite connection."""
        nothingToDo = [{'season': 4, 'event_type': 'floosbowl_champion', 'pinned': True}]
        for rows, label in ((self.rows(), 'with a stale champion to unpin'),
                            (nothingToDo, 'with nothing to unpin'),
                            ([], 'on an empty feed')):
            sm = manager(rows, 4)
            sm._unpinStaleChampions(4)
            self.assertFalse(sm.db_session.open,
                             f"the write lock was still held {label}")

    def testItCommitsWhenItChangesSomething(self):
        """⚠️ A bulk update takes SQLite's single write lock immediately. Leaving it
        uncommitted on the shared session is the shape that took production down once."""
        rows = self.rows()
        sm = manager(rows, 4)
        sm._unpinStaleChampions(4)
        self.assertEqual(1, sm.db_session.commits)

    def testAFailureCannotStopTheSeason(self):
        class Boom(FakeSession):
            def query(self, model): raise RuntimeError("db gone")
        from managers.seasonManager import SeasonManager
        sm = SeasonManager.__new__(SeasonManager)
        sm.db_session = Boom([], 4)
        sm._unpinStaleChampions(4)   # must not raise


if __name__ == '__main__':
    unittest.main(verbosity=2)
