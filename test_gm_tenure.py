"""A GM is judged on their tenure, not only on last season.

⚠️ PERSISTENT MEDIOCRITY USED TO BE FREE. `fireChance`'s deficit term reads the LATEST
season and goes to zero at a 0.45 win rate, so a club going 13-15 forever produced exactly
0.0% fire risk every year without end — five such seasons left an 86% chance of the same
GM still being in post, and being reliably slightly-below-average was the safest place in
the league to stand. Owner: seasons since making the playoffs, seasons around .500, and
seasons making the playoffs without progressing should all be considered.

Two axes, deliberately separate:

  **Stall** — seasons since this GM's club won a playoff game. Missing the postseason costs
  more per season than reaching it and going out immediately, so "no playoffs in years" and
  "one-and-done in years" stay distinguishable instead of collapsing into one number. A
  playoff WIN is the only thing that resets the clock.

  **Treading water** — consecutive seasons whose RECORD sits around .500. Its band starts at
  the fire baseline so a season already generating deficit pressure is never counted twice.

⚠️ SCOPED TO THIS CLUB. `seasonsCoached` is a CAREER counter that follows a GM to a new
club, so tenure read off it would blame an incoming GM for the drought that got their
predecessor fired. `Coach.seasonsWithTeam` is the window, and it resets on hire.

Measured over 40 leagues x 12 seasons x 32 clubs: exits/season 3.39 -> 3.89. The plan's
target is "a few per season, NOT a carousel".

Run: .venv/bin/python test_gm_tenure.py
"""
import unittest

from managers.gmTurnover import GmTurnover
from constants import (GM_FIRE_STALL_GRACE, GM_FIRE_DROUGHT_STEP,
                       GM_FIRE_STAGNATION_STEP, GM_FIRE_TENURE_MAX,
                       GM_FIRE_MEDIOCRITY_GRACE, GM_FIRE_BASELINE_WINPCT)


class _Team:
    def __init__(self, wins, losses):
        self.seasonTeamStats = {'wins': wins, 'losses': losses}
        self.name = 'Testers'


class _Coach:
    def __init__(self, seasons=5, attitude=80):
        self.seasonsCoached = seasons
        self.seasonsWithTeam = seasons
        self.attitude = attitude
        self.name = 'GM'


def season(wins, losses, playoffs=False, wonRound=False):
    return {'winPct': wins / (wins + losses),
            'madePlayoffs': playoffs, 'wonPlayoffRound': wonRound}


BARREN = season(13, 15)                       # .464 — above the fire baseline, no playoffs
ONE_AND_DONE = season(14, 14, playoffs=True)  # reaches them, wins nothing
ADVANCED = season(16, 12, playoffs=True, wonRound=True)


class TenurePressure(unittest.TestCase):
    def setUp(self):
        self.g = GmTurnover()

    def test_graceMeansEarlySeasonsAreFree(self):
        for n in range(GM_FIRE_STALL_GRACE + 1):
            self.assertEqual(self.g.tenurePressure([BARREN] * n), 0.0,
                             f'{n} barren season(s) should still be free')

    def test_aBarrenTenureAccumulates(self):
        pressures = [self.g.tenurePressure([BARREN] * n) for n in range(1, 8)]
        self.assertEqual(pressures, sorted(pressures), 'pressure must not decrease')
        self.assertGreater(pressures[-1], 0.0, 'a long barren run must carry real risk')

    def test_missingThePlayoffsCostsMoreThanGoingOutEarly(self):
        """⚠️ The two failure modes the owner named are NOT the same. Both mean the GM has
        not got anywhere, but never qualifying is the worse of the two."""
        n = GM_FIRE_STALL_GRACE + 3
        self.assertGreater(self.g.tenurePressure([BARREN] * n),
                           self.g.tenurePressure([ONE_AND_DONE] * n))
        self.assertGreater(GM_FIRE_DROUGHT_STEP, GM_FIRE_STAGNATION_STEP)

    def test_oneAndDoneStillAccumulates(self):
        """Reaching the playoffs is not a defence if you never win a round."""
        n = GM_FIRE_STALL_GRACE + 4
        self.assertGreater(self.g.tenurePressure([ONE_AND_DONE] * n), 0.0)

    def test_aPlayoffWinResetsTheClock(self):
        """⚠️ THE ONLY RESET. Winning a round says the project is going somewhere."""
        barren = self.g.tenurePressure([BARREN] * 6)
        withWin = self.g.tenurePressure([BARREN] * 2 + [ADVANCED] + [BARREN] * 3)
        self.assertGreater(barren, 0.0)
        self.assertLess(withWin, barren)

    def test_pressureIsCapped(self):
        self.assertLessEqual(self.g.tenurePressure([BARREN] * 40), GM_FIRE_TENURE_MAX)

    def test_theMediocrityBandStartsAtTheFireBaseline(self):
        """⚠️ No double counting. A season bad enough to generate deficit pressure must not
        also be counted as treading water."""
        from constants import GM_FIRE_MEDIOCRITY_BAND
        self.assertGreaterEqual(GM_FIRE_MEDIOCRITY_BAND[0], GM_FIRE_BASELINE_WINPCT)

    def test_aWinningTenureIsFree(self):
        self.assertEqual(self.g.tenurePressure([ADVANCED] * 10), 0.0)

    def test_noHistoryIsNotPressure(self):
        """A missing or failed history load must read as 0, never as a barren tenure."""
        self.assertEqual(self.g.tenurePressure([]), 0.0)
        self.assertEqual(self.g.tenurePressure(None), 0.0)


class FireChanceUsesIt(unittest.TestCase):
    def setUp(self):
        self.g = GmTurnover()

    def test_theMediocreGmIsNoLongerUntouchable(self):
        """THE REGRESSION: 13-15 forever used to be 0.0% every year, without end."""
        long = [BARREN] * 6
        self.assertGreater(self.g.fireChance(_Team(13, 15), _Coach(7), history=long), 0.0)

    def test_aGoodSeasonDoesNotBypassTenure(self):
        """⚠️ The early return used to fire whenever the latest record cleared the baseline,
        which is exactly how a long barren tenure escaped the rest of the function."""
        self.assertGreater(
            self.g.fireChance(_Team(15, 13), _Coach(7), history=[BARREN] * 6), 0.0)

    def test_tenureNeverOutweighsACatastrophe(self):
        alone = self.g.fireChance(_Team(4, 24), _Coach(5), history=[])
        withRun = self.g.fireChance(_Team(4, 24), _Coach(5), history=[season(4, 24)] * 5)
        self.assertGreaterEqual(withRun, alone)
        self.assertGreater(alone, self.g.fireChance(_Team(13, 15), _Coach(7),
                                                    history=[BARREN] * 6),
                           'a 4-24 season must still outweigh a grey tenure')

    def test_theTenureGraceStillProtectsANewGm(self):
        """⚠️ A GM in their first season cannot be fired for a drought they inherited —
        which is the whole reason tenure is scoped to THIS club."""
        self.assertEqual(
            self.g.fireChance(_Team(13, 15), _Coach(1), history=[BARREN] * 6), 0.0)

    def test_aWinnerIsStillUntouchable(self):
        self.assertEqual(
            self.g.fireChance(_Team(20, 8), _Coach(6), history=[ADVANCED] * 5), 0.0)


class TenureIsScopedToTheClub(unittest.TestCase):
    def test_theHistoryWindowUsesClubTenureNotCareer(self):
        """`seasonsCoached` follows a GM to a new club; `seasonsWithTeam` does not."""
        with open('managers/teamManager.py') as fh:
            src = fh.read()
        body = src.split('def _gmTenureHistory')[1].split('\n    def ')[0]
        self.assertIn('seasonsWithTeam', body)
        self.assertNotIn('seasonsCoached', body,
                         'the window must not be the career counter')

    def test_aNewHireStartsAtZero(self):
        with open('managers/teamManager.py') as fh:
            src = fh.read()
        self.assertIn('team.coach.seasonsWithTeam = 0', src,
                      'an incoming GM must not inherit the predecessor\'s drought')


class GraceIsScopedToTheClub(unittest.TestCase):
    """⚠️ PRE-EXISTING GAP, found while reviewing this change. The grace period read
    `seasonsCoached` — a CAREER counter that follows a GM to a new job — so a veteran hired
    to fix a bad team had no protection at all in their first season there and could be
    fired at 54% for the roster they had just walked into. That is exactly the case the
    grace exists to cover, and its own justification ("they inherited the roster and haven't
    had an offseason to shape it") is about the club."""

    def setUp(self):
        self.g = GmTurnover()

    def test_aVeteranHiredElsewhereGetsGraceAtTheNewClub(self):
        vet = _Coach(seasons=8)
        vet.seasonsWithTeam = 1          # first season at THIS club
        self.assertEqual(self.g.fireChance(_Team(6, 22), vet), 0.0)

    def test_butOnlyForTheGracePeriod(self):
        vet = _Coach(seasons=10)
        vet.seasonsWithTeam = 3
        self.assertGreater(self.g.fireChance(_Team(6, 22), vet), 0.0)

    def test_aCoachObjectWithoutClubTenureStillWorks(self):
        """Falls back to the career count rather than raising or granting infinite grace."""
        class Legacy:
            seasonsCoached = 8
            attitude = 80
        self.assertGreater(self.g.fireChance(_Team(6, 22), Legacy()), 0.0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
