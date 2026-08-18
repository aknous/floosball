"""In frames, a team that is winning does not heave it.

⚠️ REPORTED FROM A LIVE GAME. Final frame, 3:54 left, 5th & 15 at the opponent's 42. The
offense was AHEAD in the frame and ahead on frames won; only the aggregate score was tied.
It threw it deep into coverage, turned the ball over on downs, and handed the opponent the
field position to take the frame — and with it the match.

The play's own insight said why:

    decision:  Hail Mary
    rationale: Drive clock expiring, heave for the score

    _driveHailMary = _dcLastPlay and scoreDiff <= 0   # trailing or tied

`scoreDiff` there is the RAW POINT MARGIN. A frames match is decided by FRAMES WON, with
points only breaking a level tie, so "the aggregate is tied" says nothing about who is
winning. A team that is ahead has nothing to gamble for, and the gamble is a turnover.

⚠️ THIS IS THE SAME BUG THE END-OF-GAME FIELD GOAL BRANCH ALREADY HAD, fixed earlier for
exactly the same reason: a frames game reasoned about on the aggregate throws away the
frame. `playCaller` computes `decisionDiff` for this, and this branch was still reading past
it. Off frames `decisionDiff` IS `scoreDiff`, so every other format is untouched.

Run: .venv/bin/python test_frames_hail_mary.py
"""
import collections
import logging
import unittest

logging.disable(logging.CRITICAL)

from game_rules import GameRules
from scenario import Scenario

AGGREGATE = 21   # both teams, i.e. level on points


def framesGame(*, framesHome, framesAway, framePoints, driveClockLeft=2,
               ballOn=42, down=5, clock=234):
    """The reported situation: final frame, drive clock expiring, aggregate tied."""
    rules = GameRules()
    rules.gameFormat = 'frames'
    rules.framesPerGame = 6
    rules.downsPerSeries = 5
    rules.driveClockEnabled = True
    scenario = Scenario(gameRules=rules)
    game = scenario.game
    scenario.situation(quarter=4, clock=clock, offense='home',
                       offScore=AGGREGATE, defScore=AGGREGATE,
                       down=down, distance=15, ballOn=ballOn,
                       offTimeouts=2, defTimeouts=2, clockRunning=True)
    game._frameIndex = 5
    game._framesWonHome = framesHome
    game._framesWonAway = framesAway
    game._frameStartHome = AGGREGATE - framePoints
    game._frameStartAway = AGGREGATE
    game.driveClockRemaining = driveClockLeft
    return scenario


def decisions(scenarioFactory, trials=40):
    calls, reasons = collections.Counter(), collections.Counter()
    for _ in range(trials):
        scenario = scenarioFactory()
        calls[str(scenario.callPlay()).replace('PlayType.', '')] += 1
        clockMgmt = scenario.game.play.insights.get('clockMgmt') or {}
        if clockMgmt.get('decision'):
            reasons[clockMgmt['decision']] += 1
    return calls, reasons


class AWinningTeamDoesNotGamble(unittest.TestCase):

    def test_theFixtureIsTheReportedSituation(self):
        """Guard the setup: ahead in the frame, ahead on frames, level on points."""
        game = framesGame(framesHome=3.0, framesAway=2.0, framePoints=7).game
        self.assertEqual(game.homeScore, game.awayScore, 'aggregate should be tied')
        self.assertGreater(game._frameScoreDiff(), 0, 'should lead the frame')
        self.assertGreater(game._frameDecisionDiff(), 0,
                           'frames-aware margin should say LEADING')

    def test_itDoesNotHeaveWhileWinning(self):
        """THE REGRESSION."""
        calls, reasons = decisions(
            lambda: framesGame(framesHome=3.0, framesAway=2.0, framePoints=7))
        self.assertEqual(reasons.get('hailMary', 0), 0,
                         f'heaved while winning the frame: {dict(reasons)}')
        self.assertEqual(reasons.get('trickPlay', 0), 0,
                         'gambled on a gadget while winning')

    def test_itProtectsTheBallInstead(self):
        calls, _ = decisions(
            lambda: framesGame(framesHome=3.0, framesAway=2.0, framePoints=7))
        self.assertGreater(calls.get('Punt', 0), 30,
                           f'a leading team on its last down should punt: {dict(calls)}')


class ATeamThatNeedsPointsStillHeaves(unittest.TestCase):
    """⚠️ THE COUNTERPART. If this had become "never heave in frames", the desperation
    play would be gone from the format that needs it most."""

    def test_losingTheFrameStillHeaves(self):
        _, reasons = decisions(
            lambda: framesGame(framesHome=3.0, framesAway=2.0, framePoints=-7))
        self.assertGreater(reasons.get('hailMary', 0), 10,
                           f'a trailing team stopped trying: {dict(reasons)}')

    def test_aLevelMatchStillHeaves(self):
        """Frames level and points level — the match is genuinely undecided, so the
        aggregate tiebreak makes points worth chasing."""
        _, reasons = decisions(
            lambda: framesGame(framesHome=2.5, framesAway=2.5, framePoints=0))
        self.assertGreater(reasons.get('hailMary', 0), 10)

    def test_behindOnFramesStillHeaves(self):
        _, reasons = decisions(
            lambda: framesGame(framesHome=2.0, framesAway=3.0, framePoints=7))
        self.assertGreater(reasons.get('hailMary', 0), 10)


class TheBranchReadsTheRightMargin(unittest.TestCase):

    def test_itUsesTheFramesAwareMargin(self):
        with open('floosball_game.py') as fh:
            src = fh.read()
        body = src.split('# ── Hail Mary: desperation deep throw ──')[1][:2600]
        self.assertIn('_hmDiff = decisionDiff', body)
        self.assertIn('_driveHailMary = _dcLastPlay and _hmDiff <= 0', body)
        self.assertNotIn('_dcLastPlay and scoreDiff <= 0', body,
                         'the drive-clock heave is reading the aggregate again')

    def test_theGameClockHeaveUsesItToo(self):
        """Both triggers decide the same thing and must read the same margin."""
        with open('floosball_game.py') as fh:
            body = fh.read().split('# ── Hail Mary: desperation deep throw ──')[1][:2600]
        self.assertIn('_hmDiff < 0', body)

    def test_offFramesNothingChanges(self):
        """`decisionDiff` is `scoreDiff` outside frames, so standard football is untouched."""
        scenario = Scenario()
        scenario.situation(quarter=4, clock=10, offense='home', offScore=14, defScore=17,
                           down=4, distance=15, ballOn=45, offTimeouts=0, defTimeouts=0)
        self.assertIsNone(scenario.game._frameDecisionDiff())


if __name__ == '__main__':
    unittest.main(verbosity=2)
