"""A drive clock about to expire in the offense's own half is a punt, not a heave.

⚠️ REPORTED FROM A LIVE GAME (one team scored 100+). Drive clock on: teams reached the
end of their drive clock deep in their own territory, the clock expired, and the
opponent took over on a short field, over and over.

The early-down punt existed, but it was early downs only ("4th is the fourth-down
caller's job"), and the drive-clock Hail Mary in `playCaller` runs BEFORE the
fourth-down caller and fired whenever the offense was tied or trailing, in any quarter,
from 30+ yards out. So on the final down the punt never got a look. Measured over 20
games at 70s/series: 18 of 26 expiries were in the offense's own half, 15 of them
4th-down heaves (4th & 6 from its own 26 in the first quarter).

Now: the Hail Mary is barred from the offense's own half, and under 'possession' reset
(where a conversion cannot save the drive) the punt applies on every down.

Run: .venv/bin/python -m pytest -q test_drive_clock_punt.py
"""
import collections
import logging
import unittest

logging.disable(logging.CRITICAL)

from game_rules import GameRules
from scenario import Scenario


def driveClockScenario(*, reset, down, distance, ballOn, driveClockLeft=8,
                       quarter=1, clock=600, offScore=0, defScore=0, downs=4):
    rules = GameRules()
    rules.downsPerSeries = downs
    rules.driveClockEnabled = True
    rules.driveClockUnit = 'seconds'
    rules.driveClockReset = reset
    rules.driveClockLimit = 70 if reset == 'series' else 120
    scenario = Scenario(gameRules=rules)
    scenario.situation(quarter=quarter, clock=clock, offense='home',
                       offScore=offScore, defScore=defScore,
                       down=down, distance=distance, ballOn=ballOn,
                       offTimeouts=3, defTimeouts=3, clockRunning=True)
    scenario.game.driveClockRemaining = driveClockLeft
    return scenario


def calls(factory, trials=40):
    out, reasons = collections.Counter(), collections.Counter()
    for _ in range(trials):
        scenario = factory()
        out[str(scenario.callPlay()).replace('PlayType.', '')] += 1
        cm = scenario.game.play.insights.get('clockMgmt') or {}
        if cm.get('decision'):
            reasons[cm['decision']] += 1
    return out, reasons


class DeepInOwnTerritory(unittest.TestCase):

    def test_theReportedSituationPunts(self):
        """4th & 6 from its own 26, tied in Q1, series reset: the fourth-down caller
        decides, and it punts. It used to heave every time."""
        out, reasons = calls(lambda: driveClockScenario(
            reset='series', down=4, distance=6, ballOn=74))
        self.assertEqual(reasons['hailMary'], 0, reasons)
        self.assertGreaterEqual(out['Punt'], 36, out)

    def test_possessionResetPuntsOnTheFinalDownAtAnyDistance(self):
        """Under 'possession' a conversion does not save the drive, so 4th & 1 from
        its own 35 is a punt too."""
        out, reasons = calls(lambda: driveClockScenario(
            reset='possession', down=4, distance=1, ballOn=65))
        self.assertEqual(reasons['hailMary'], 0, reasons)
        self.assertGreaterEqual(out['Punt'], 28, out)

    def test_possessionResetPuntsOnAnEarlyDownAtShortYardage(self):
        out, _ = calls(lambda: driveClockScenario(
            reset='possession', down=2, distance=3, ballOn=70))
        self.assertGreaterEqual(out['Punt'], 28, out)

    def test_seriesResetStillRunsForAShortConversion(self):
        """Under 'series' a first down refills the clock, so 2nd & 2 is worth a snap."""
        out, _ = calls(lambda: driveClockScenario(
            reset='series', down=2, distance=2, ballOn=70))
        self.assertEqual(out['Punt'], 0, out)


class AnyNumberOfDowns(unittest.TestCase):
    """`downsPerSeries` is votable (3 to 5). The final down is whichever down that is,
    not the 4th, so the punt has to follow it."""

    def test_theFinalDownPuntsAtThreeAndFiveDowns(self):
        for downs in (3, 5):
            for reset in ('series', 'possession'):
                with self.subTest(downs=downs, reset=reset):
                    out, reasons = calls(lambda: driveClockScenario(
                        reset=reset, down=downs, distance=6, ballOn=74, downs=downs))
                    self.assertEqual(reasons['hailMary'], 0, reasons)
                    self.assertGreaterEqual(out['Punt'], 36, out)

    def test_thePenultimateDownPuntsAtLongYardage(self):
        for downs in (3, 5):
            with self.subTest(downs=downs):
                out, _ = calls(lambda: driveClockScenario(
                    reset='series', down=downs - 1, distance=8, ballOn=74, downs=downs))
                self.assertGreaterEqual(out['Punt'], 28, out)


class InTheOpponentsHalf(unittest.TestCase):

    def test_theHeaveSurvivesWhereItCanScore(self):
        """At the opponent's 47, out of field-goal range, tied: the heave is still the
        call. The fix bars it only from the offense's own half. (When the generated
        kicker has the range, the fourth-down model weighs kick against punt instead.)"""
        out, reasons = calls(lambda: driveClockScenario(
            reset='series', down=4, distance=9, ballOn=47))
        self.assertGreater(reasons['hailMary'] + reasons['trickPlay'], out['Punt'],
                           (out, reasons))

    def test_theGameClockHailMaryIsUntouched(self):
        """Trailing, last snap of the game, own 30: still a heave (the drive-clock gate
        does not reach the game-clock branch)."""
        out, reasons = calls(lambda: driveClockScenario(
            reset='possession', down=2, distance=10, ballOn=70, driveClockLeft=100,
            quarter=4, clock=6, offScore=14, defScore=17))
        self.assertGreater(reasons['hailMary'], 0, (out, reasons))


if __name__ == '__main__':
    unittest.main()
