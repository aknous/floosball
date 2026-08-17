"""In frames, three points are only worth having if they win the frame.

⚠️ REPORTED FROM PRODUCTION GAME 469 (Waffles 17 - 17 Sodas, frames 2.5 - 3.5). Going into
the final frame the frames were LEVEL at 2.5 apiece. The offense was down a TOUCHDOWN in
that frame but only 3 on aggregate, and faced 4th and goal with 0:30 left. It kicked the
field goal. That tied the aggregate at 17-17 and LOST the frame 3-7, handing over the match
while the opponent simply knelt the clock out. The touchdown would have won the frame and
gone ahead on aggregate.

⚠️ THE CAUSE IS A DECISION READING THE WRONG SCOREBOARD — specifically playCaller's
END-OF-GAME FIELD GOAL branch, whose own comment reads "tied, leading by <= 3, or trailing
by <= 3":

    if -self._fgValue() <= scoreDiff <= self._fgValue() and ...

`scoreDiff` there is the raw AGGREGATE margin, so it asked its question against the wrong
scoreboard:

    aggregate   -3  ->  -3 <= -3 <= 3  = True   -> kicks
    frame-aware -7  ->  -3 <= -7       = False  -> falls through, goes for it

⚠️ A FIRST DIAGNOSIS BLAMED THE LAST-SNAP RULE AND WAS WRONG. `_lastSnapBeforeBreak()` is
False here — with 30s and a timeout there genuinely is another snap — so that branch never
ran, and tracing showed no field-goal assignment fired inside `_fourthDownCaller` either
(which does apply the frame hook, and was never the problem). The kick came from playCaller
several hundred lines further down. Trace the assignment; do not infer it.

⚠️ THE FIX IS LOCAL, NOT A CHANGE TO `playCaller`'s `scoreDiff`. About fifteen other
decisions read that variable and several legitimately want the aggregate; three sites
(`_framesLead`, `_comebackDiff`, `_fgDiff`) already compute a frame-aware value with a
fallback, and this now follows the same pattern.

⚠️ This is the THIRD bug of this shape — a decision reading standard-format state while a
format overlay changes what the number means (chess-clock snap cost, chess-clock FG gating,
now frames). See docs/format_clock_mgmt_refactor.md.

Run: .venv/bin/python test_frames_endgame.py
"""
import unittest

from scenario import Scenario, PlayType
from game_rules import GameRules


def framesGame(*, frameIndex=5, framesHome=2.5, framesAway=2.5,
               homeScore=14, awayScore=17, frameStartHome=14, frameStartAway=10,
               clock=30, ballOn=8, down=4):
    """The reported situation, built on a real Game.

    Defaults reproduce game 469's final frame from the OFFENSE's (home) side:
    frames level, down 7 IN THE FRAME (0 scored vs 7), down 3 on aggregate.
    """
    rules = GameRules()
    rules.gameFormat = 'frames'
    s = Scenario(gameRules=rules)
    g = s.game
    # Frames run over the normal clock; frame 6 of 6 with 30s left means the game clock
    # is 30s from the end of regulation.
    s.situation(quarter=rules.quartersPerGame, clock=clock, offense='home',
                offScore=homeScore, defScore=awayScore,
                down=down, distance=ballOn, ballOn=ballOn,
                offTimeouts=1, defTimeouts=1, clockRunning=True)
    g._frameIndex = frameIndex
    g._framesWonHome = framesHome
    g._framesWonAway = framesAway
    g._frameStartHome = frameStartHome
    g._frameStartAway = frameStartAway
    # A kicker who can comfortably make it, so "could not kick" is never the reason.
    s.setKickerLeg('home', 60)
    return s


class TheFrameIsWhatCounts(unittest.TestCase):

    def test_theSituationIsBuiltAsReported(self):
        """Guard the fixture itself: if the frame maths drifts, every assertion below
        becomes meaningless rather than failing honestly."""
        g = framesGame().game
        self.assertEqual(g.format.key, 'frames')
        self.assertEqual(g._frameSecsRemaining(), 30, 'frame should be 30s from closing')
        # Down 7 inside the frame, down 3 on aggregate.
        self.assertEqual(g.homeScore - g._frameStartHome, 0)
        self.assertEqual(g.awayScore - g._frameStartAway, 7)
        self.assertEqual(g.homeScore - g.awayScore, -3)

    def test_theDecisionMarginIsTheFrameNotTheAggregate(self):
        """⚠️ THE HEART OF IT. With frames level, the frame in progress decides the match,
        so the margin that matters is -7 (the frame) and not -3 (the aggregate)."""
        g = framesGame().game
        self.assertEqual(g._frameDecisionDiff(), -7,
                         'the frame margin should drive end-of-frame decisions')

    def test_itDoesNotKickAwayTheFrame(self):
        """THE REGRESSION: a field goal here loses the frame and the match."""
        s = framesGame()
        call = s.callPlay()
        cm = s.game.play.insights.get('clockMgmt') or {}
        self.assertNotEqual(cm.get('decision'), 'lastSnapFG',
                            'took the last-snap FG while losing the frame by a TD')
        self.assertIsNot(call, PlayType.FieldGoal,
                         'kicked a field goal that cannot win the frame')

    def test_itStillKicksWhenThreePointsActuallyWinTheFrame(self):
        """⚠️ The fix must not turn into "never kick in frames". Down 3 IN THE FRAME, a
        field goal ties it and halves the frame — that is worth having.

        Asserts the PLAY, not a decision tag: the kick can legitimately come from either the
        end-of-game branch or the last-snap one depending on the clock, and pinning the tag
        would make this a test of which branch won rather than of what the offense did."""
        s = framesGame(frameStartHome=14, frameStartAway=14, homeScore=14, awayScore=17)
        self.assertEqual(s.game._frameDecisionDiff(), -3, 'fixture should be down 3 in-frame')
        calls = [s.callPlay() for _ in range(12)]
        self.assertIn(PlayType.FieldGoal, calls,
                      'a field goal that halves the frame should still be taken')

    def test_standardFormatIsUntouched(self):
        """The frame hook returns None outside frames, so the aggregate still rules."""
        s = Scenario()
        s.situation(quarter=4, clock=30, offense='home', offScore=14, defScore=17,
                    down=4, distance=8, ballOn=8, offTimeouts=1, defTimeouts=1)
        self.assertIsNone(s.game._frameDecisionDiff())


class TheFixIsWhereItClaimsToBe(unittest.TestCase):

    def test_theEndGameBranchesUseTheFrameAwareMargin(self):
        """Both end-game field-goal branches must read `decisionDiff`, the frame-aware
        margin, rather than the raw aggregate `scoreDiff`."""
        with open('floosball_game.py') as fh:
            src = fh.read()
        body = src.split('def playCaller(self):')[1].split('\n    def ')[0]
        self.assertIn('decisionDiff = self._frameDecisionDiff()', body)
        # the end-of-game FG branch — the one that kicked in game 469
        self.assertIn('if -self._fgValue() <= decisionDiff <= self._fgValue()', body)
        self.assertNotIn('if -self._fgValue() <= scoreDiff <= self._fgValue()', body,
                         'the end-of-game FG branch is reading the aggregate again')
        # the last-snap-before-break branch
        self.assertIn('_routIsOn = _lastDiff', body)
        self.assertIn('_isGarbageTime(_lastDiff)', body)

    def test_playCallersGlobalScoreDiffWasNotRepointed(self):
        """⚠️ Deliberately local. ~15 other decisions read `scoreDiff` and several want the
        aggregate; repointing it would silently move all of them."""
        with open('floosball_game.py') as fh:
            src = fh.read()
        head = src.split('def playCaller(self):')[1][:400]
        self.assertIn('scoreDiff = (self.homeScore - self.awayScore)', head,
                      'playCaller should still compute the raw aggregate margin')


if __name__ == '__main__':
    unittest.main(verbosity=2)
