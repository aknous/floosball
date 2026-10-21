"""A plays drive clock's last snap is a final down, decided as 4th & goal from the spot.

Under the "8 plays, whole drive" preset a first down refills nothing, so the 8th snap is
the drive's last whatever the down says. Before, only the real final down reached
`_fourthDownCaller`; an earlier-down last snap took a short list of special cases:

  * a field goal in range at ANY score (down 7 with 1:30 left at the opponent's 20, it
    kicked and stayed down 4),
  * a Hail Mary whenever tied or trailing, in any quarter, from the opponent's 30-50
    (the first quarter included, instead of punting),
  * a normal play when leading out of range on the opponent's side, i.e. a turnover on
    downs at the spot,
  * and on a real 4th down the call chased the first-down marker (4th & 3 at the 20,
    down 7, late: a run for three yards that could not save the drive).

Now `_isFinalDown` sends that snap to the fourth-down caller with the goal line as the
yards to go (`_decisionYardsToGo`), so the go / kick / punt model decides it.

Run: .venv/bin/python -m pytest -q test_drive_clock_last_snap.py
"""
import collections
import logging
import unittest

logging.disable(logging.CRITICAL)

from game_rules import GameRules
from scenario import Scenario

TRIALS = 30


def lastSnap(*, down, distance, ballOn, snapsLeft=1, unit='plays', reset='possession',
             quarter=1, clock=600, offScore=0, defScore=0, hoops=False, frames=False,
             offTimeouts=3):
    rules = GameRules()
    rules.sidelineGoalsEnabled = hoops
    if frames:
        rules.gameFormat = 'frames'
        rules.framesPerGame = 6
    rules.driveClockEnabled = True
    rules.driveClockUnit = unit
    rules.driveClockReset = reset
    rules.driveClockLimit = 8 if unit == 'plays' else 120
    scenario = Scenario(gameRules=rules)
    scenario.situation(quarter=quarter, clock=clock, offense='home',
                       offScore=offScore, defScore=defScore,
                       down=down, distance=distance, ballOn=ballOn,
                       offTimeouts=offTimeouts, defTimeouts=3, clockRunning=True)
    scenario.game.driveClockRemaining = snapsLeft
    return scenario


def calls(**kw):
    out = collections.Counter()
    for _ in range(TRIALS):
        out[str(lastSnap(**kw).callPlay()).replace('PlayType.', '')] += 1
    return out


class TheLastSnapIsAFinalDown(unittest.TestCase):

    def test_onlyThePlaysPossessionClockQualifies(self):
        self.assertTrue(lastSnap(down=2, distance=6, ballOn=45).game._driveClockFinalSnap())
        self.assertFalse(lastSnap(down=2, distance=6, ballOn=45, snapsLeft=2)
                         .game._driveClockFinalSnap())
        # A seconds clock only estimates its last snap; a series clock refills.
        self.assertFalse(lastSnap(down=2, distance=6, ballOn=45, unit='seconds')
                         .game._driveClockFinalSnap())
        self.assertFalse(lastSnap(down=2, distance=6, ballOn=45, reset='series')
                         .game._driveClockFinalSnap())

    def test_theGoalLineIsTheYardsToGo(self):
        game = lastSnap(down=2, distance=6, ballOn=45).game
        self.assertEqual(game._decisionYardsToGo(), 45)
        game = lastSnap(down=2, distance=6, ballOn=45, snapsLeft=2).game
        self.assertEqual(game._decisionYardsToGo(), 6)


class EarlyGame(unittest.TestCase):

    def test_tiedOnTheOpponentsSideOutOfRangePunts(self):
        """Tied in Q1 on the opponent's 45: it used to heave every time."""
        out = calls(down=2, distance=6, ballOn=45)
        self.assertGreaterEqual(out['Punt'], 27, out)

    def test_leadingOnTheOpponentsSideOutOfRangePunts(self):
        """Up 7: it used to run a normal play into a turnover on downs at the spot."""
        out = calls(down=1, distance=10, ballOn=45, offScore=7)
        self.assertGreaterEqual(out['Punt'], 27, out)

    def test_ownHalfPunts(self):
        out = calls(down=2, distance=6, ballOn=70)
        self.assertGreaterEqual(out['Punt'], 28, out)

    def test_inRangeKicks(self):
        out = calls(down=2, distance=6, ballOn=25)
        self.assertGreaterEqual(out['FieldGoal'], 27, out)


class LateAndTrailing(unittest.TestCase):

    def test_downSevenGoesForTheTouchdown(self):
        """Down 7 with 1:30 left on the opponent's 20: a field goal cannot save it. It
        used to kick every time on an early down."""
        out = calls(down=2, distance=6, ballOn=20, quarter=4, clock=90, defScore=7)
        self.assertLessEqual(out['FieldGoal'], 3, out)

    def test_aFinalDownThrowsForTheEndZoneNotTheMarker(self):
        """4th & 3 at the 20, down 7, last snap: a three-yard run converts nothing."""
        out = calls(down=4, distance=3, ballOn=20, quarter=4, clock=90, defScore=7)
        self.assertLessEqual(out['Run'], 3, out)
        self.assertGreaterEqual(out['Pass'], 25, out)

    def test_downTwoKicks(self):
        out = calls(down=2, distance=6, ballOn=20, quarter=4, clock=90, defScore=2)
        self.assertGreaterEqual(out['FieldGoal'], 27, out)


class NotTheLastSnap(unittest.TestCase):

    def test_twoSnapsLeftPlaysTheDown(self):
        """With a snap still to come the offense plays on; the last-snap decision waits."""
        out = calls(down=2, distance=6, ballOn=45, snapsLeft=2)
        self.assertEqual(out['Punt'] + out['FieldGoal'], 0, out)


class FramesLastSnap(unittest.TestCase):
    """Frames (and every non-standard format) decides a final down with the older branch
    tree, not the fitted model. Read as 4th & goal, it kicked from the 3-5 on a last snap
    (its go-for-it in range needs 2 yards or fewer), where the old early-down path ran a
    play for the touchdown."""

    def test_insideTheFiveGoesForTheTouchdown(self):
        out = calls(down=2, distance=3, ballOn=3, quarter=1, clock=850, frames=True)
        self.assertLessEqual(out['FieldGoal'], 3, out)


class NoSpikeOnTheSecondToLastSnap(unittest.TestCase):
    """A spike spends a snap. Prod game 4901, frame 5: 1st & goal at the 5, down 3,
    1:05 left, no timeouts, two snaps on the clock. The spike's down gate read 1st down
    as room to spare, so the Trains spiked and had only the tying kick left."""

    def test_twoSnapsLeftNeverSpikes(self):
        out = calls(down=1, distance=5, ballOn=5, snapsLeft=2, quarter=4, clock=25,
                    defScore=3, offTimeouts=0)
        self.assertEqual(out['Spike'], 0, out)

    def test_withSnapsToSpareItStillSpikes(self):
        out = calls(down=1, distance=5, ballOn=5, snapsLeft=6, quarter=4, clock=25,
                    defScore=3, offTimeouts=0)
        self.assertGreaterEqual(out['Spike'], 10, out)


class TheLastSnapFromDistanceIsAHeave(unittest.TestCase):
    """Prod game 4904: Rocks down 2 on the match, last snap on the SLC 47 at 0:17 of
    the final frame. The 4th-down tree threw a 10-yard sideline out, which ended the
    game. From 30+ out on a last snap only a touchdown counts, and a play short of the
    end zone hands the ball over at its spot."""

    def _calls(self, frames, **kw):
        out = collections.Counter()
        sideline = 0
        for _ in range(TRIALS):
            scenario = lastSnap(down=1, distance=10, ballOn=47, quarter=4, clock=17,
                                defScore=2, offTimeouts=0, frames=frames, hoops=True)
            if frames:
                scenario.game._frameIndex = 5
                scenario.game.framesWonHome, scenario.game.framesWonAway = 2.0, 3.0
            scenario.callPlay()
            out[scenario.game.play.insights.get('playCall')] += 1
            sideline += bool(scenario.game.play.targetSideline)
        return out, sideline

    def test_theReportedFinalFrame(self):
        out, sideline = self._calls(frames=True)
        self.assertEqual(out['hailMary'], TRIALS, out)
        self.assertEqual(sideline, 0)

    def test_standard(self):
        out, sideline = self._calls(frames=False)
        self.assertEqual(out['hailMary'], TRIALS, out)
        self.assertEqual(sideline, 0)


class NoPuntTheLeaderCanKneelOut(unittest.TestCase):
    """Prod game 4892, final frame: Jetskis down 7 on the match, last snap on their own
    48 with 0:22 left and no timeouts. They punted and the Pinecones knelt it out. A
    trailing team punts only when time is left to get the ball back."""

    def test_downSevenAtTheEndDoesNotPunt(self):
        for clock in (22, 120):
            out = calls(down=2, distance=10, ballOn=52, quarter=4, clock=clock,
                        defScore=7, offTimeouts=0)
            self.assertEqual(out['Punt'], 0, (clock, out))

    def test_withTimeToGetItBackItStillPunts(self):
        out = calls(down=2, distance=10, ballOn=52, quarter=4, clock=210,
                    defScore=7, offTimeouts=0)
        self.assertGreaterEqual(out['Punt'], 24, out)

    def test_theReportedFinalFrame(self):
        out = collections.Counter()
        for _ in range(TRIALS):
            scenario = lastSnap(down=2, distance=10, ballOn=52, quarter=4, clock=22,
                                defScore=7, offTimeouts=0, frames=True)
            game = scenario.game
            game._frameIndex = 5                         # the frame clock reads 0:22
            game.framesWonHome, game.framesWonAway = 2, 3
            out[str(scenario.callPlay()).replace('PlayType.', '')] += 1
        self.assertEqual(out['Punt'], 0, out)


def hoopShots(**kw):
    shots = 0
    for _ in range(TRIALS):
        scenario = lastSnap(hoops=True, **kw)
        scenario.callPlay()
        shots += bool(getattr(scenario.game.play, 'isHoopShot', False))
    return shots


class SidelineGoalsSpendASnap(unittest.TestCase):
    """A hoop shot gains no yards and spends a snap the way it spends a down, so its
    final-down and second-to-last-down guards count the drive clock's snaps too
    (`_seriesSnapsLeft`). They used to count downs only: down 4 at the 6 with two snaps
    left, the offense spent snap 7 on a hoop to set up a tying kick (35 of 40) instead
    of taking two shots at the winning touchdown."""

    def test_snapsLeftIsTheDownsLeftOffTheClock(self):
        game = lastSnap(down=2, distance=6, ballOn=45, snapsLeft=8).game
        self.assertEqual(game._seriesSnapsLeft(), 3)
        game = lastSnap(down=1, distance=10, ballOn=45, snapsLeft=2).game
        self.assertEqual(game._seriesSnapsLeft(), 2)

    def test_noHoopOnTheSecondToLastSnapWhenATouchdownStillWins(self):
        self.assertLessEqual(hoopShots(down=1, distance=6, ballOn=6, snapsLeft=2,
                                       quarter=4, clock=90, defScore=4), 2)

    def test_noHoopOnTheLastSnapEvenWhenOneIsNeeded(self):
        self.assertEqual(hoopShots(down=1, distance=10, ballOn=14, snapsLeft=1,
                                   quarter=4, clock=180, defScore=9), 0)

    def test_aNeededHoopIsStillTakenWithTwoSnapsLeft(self):
        """Down 9: no touchdown reaches it alone, so hoop now, touchdown on the last."""
        self.assertGreaterEqual(hoopShots(down=1, distance=10, ballOn=14, snapsLeft=2,
                                          quarter=4, clock=180, defScore=9), 22)

    def test_withSnapsToSpareTheHoopIsStillTaken(self):
        """Measured over 400 games: a hoop with three or more snaps left is worth more
        than the snap (barring it cost ~6 points a game), so it is not restricted."""
        self.assertGreaterEqual(hoopShots(down=1, distance=10, ballOn=14, snapsLeft=6), 12)


if __name__ == '__main__':
    unittest.main()
