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
        # Emulate the real filter: pinned champions from earlier seasons only.
        hit = [r for r in self.store['rows']
               if r['event_type'] == 'floosbowl_champion' and r['pinned']
               and r['season'] < self.store['season']]
        for r in hit:
            r['pinned'] = values['pinned']
        return len(hit)


class FakeSession:
    def __init__(self, rows, season):
        self.store = {'rows': rows, 'season': season}
        self.commits = 0
        self.rollbacks = 0
    def query(self, model): return FakeQuery(self.store)
    def commit(self): self.commits += 1
    def rollback(self): self.rollbacks += 1


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
        rows = self.rows()
        sm = manager(rows, 4)
        sm._unpinStaleChampions(4)
        first = sm.db_session.commits
        sm._unpinStaleChampions(4)
        self.assertEqual(first, sm.db_session.commits,
                         "a second pass wrote again with nothing to change")

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
