"""A fan may switch clubs until week 1 kicks off, then they are in for the season.

Open through the offseason and right up to the first snap; closed for the rest of the
season (owner, 2026-08-10). Before that snap nothing has happened, so a switch costs
the league nothing. After it, picking up a winner mid-run is the bandwagon the lock
exists to prevent.

⚠️ The window is deliberately NOT keyed on `currentSeason.currentWeek`, which is known
to go stale. A stale week here would fail OPEN and hand out mid-season switches all
year, so the test below pins that: a wrong week must not widen the window.
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


class FavoriteTeamWindowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.tmp.close()
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from database.models import Base
        # ⚠️ `managers` first. Importing api.main cold trips a circular import
        # (api.main -> floosball_game -> managers -> seasonManager -> floosball_game),
        # and the cycle resolves once the package is already initialised.
        import managers  # noqa: F401
        import api.main as main

        self.main = main
        self.engine = create_engine(f'sqlite:///{self.tmp.name}')
        Base.metadata.create_all(bind=self.engine)
        self.session = sessionmaker(bind=self.engine)()

        self._saved = (main._isOffseason, main._areGamesStarted, main._getCurrentSeasonNumber)
        self.setState(offseason=False, gamesStarted=False, season=4)

    def tearDown(self):
        (self.main._isOffseason, self.main._areGamesStarted,
         self.main._getCurrentSeasonNumber) = self._saved
        self.session.close()
        self.engine.dispose()
        os.unlink(self.tmp.name)

    def setState(self, offseason, gamesStarted, season):
        self.main._isOffseason = lambda: offseason
        self.main._areGamesStarted = lambda: gamesStarted
        self.main._getCurrentSeasonNumber = lambda: season

    def addFinal(self, season, week=1):
        from database.models import Game
        self.session.add(Game(season=season, week=week, status='final',
                              home_team_id=1, away_team_id=2))
        self.session.commit()

    def addScheduled(self, season, week=1):
        from database.models import Game
        self.session.add(Game(season=season, week=week, status='scheduled',
                              home_team_id=1, away_team_id=2))
        self.session.commit()

    def open_(self):
        return self.main._favoriteTeamWindowOpen(self.session)

    # -- the window --------------------------------------------------------

    def testOpenInTheOffseason(self):
        self.setState(offseason=True, gamesStarted=False, season=4)
        self.assertTrue(self.open_())

    def testOpenBeforeWeekOneKicksOff(self):
        # The slate exists but nothing has been played.
        self.addScheduled(season=4)
        self.assertTrue(self.open_())

    def testClosedOnceTheFirstSlateIsInFlight(self):
        self.setState(offseason=False, gamesStarted=True, season=4)
        self.addScheduled(season=4)
        self.assertFalse(self.open_())

    def testClosedForTheRestOfTheSeasonAfterWeekOne(self):
        # Between weeks, nothing is running — but week 1 has been played.
        self.setState(offseason=False, gamesStarted=False, season=4)
        self.addFinal(season=4, week=1)
        self.assertFalse(self.open_())

    def testAFinalFromAnEarlierSeasonDoesNotCloseTheWindow(self):
        # Season 5 has not kicked off; season 4's results must not leak into it.
        self.addFinal(season=4, week=12)
        self.setState(offseason=False, gamesStarted=False, season=5)
        self.assertTrue(self.open_())

    def testAStaleWeekCannotWidenTheWindow(self):
        """THE TRAP. `currentWeek` going stale must not reopen switching.

        Nothing here consults the week at all, so a season sitting on a wrong week
        still reads as closed off its played games.
        """
        self.setState(offseason=False, gamesStarted=False, season=4)
        self.addFinal(season=4, week=1)
        self.main._getCurrentSeasonNumber = lambda: 4   # week is never asked for
        self.assertFalse(self.open_())

    def testOpenWhenThereIsNoSeasonAtAll(self):
        # Boot, or a sim that has not started. Nothing to protect yet.
        self.setState(offseason=False, gamesStarted=False, season=None)
        self.assertTrue(self.open_())


if __name__ == '__main__':
    unittest.main(verbosity=2)
