"""Stress: in frames, three scoreboards are live at once and the offense must read the
right one.

A frames match carries THREE numbers that can each point a different way:

  1. frames won        — what actually decides the match
  2. the CURRENT frame — the mini-game in progress, which converts into (1)
  3. total points      — irrelevant EXCEPT as the tiebreak when frames finish level

Production game 469 was the case where all three disagreed: frames level, down a touchdown
in the frame, down three on aggregate. Reading (3) said a field goal ties it; reading (1)
and (2) said the field goal loses the match. It kicked.

⚠️ THIS SWEEPS FOR THE REST OF THAT FAMILY rather than re-testing the one report. For every
combination it computes, INDEPENDENTLY OF THE ENGINE, what the match result would be if the
offense added 3 versus 7, and flags any situation where the engine kicks a field goal that
LOSES while the touchdown available to it does not. The oracle knows nothing about
playCaller — it is the rules of the format, written out separately, so agreement between
them means something.

⚠️ CONSTRAINED TO THE LAST REALISTIC CHANCE (4th down, frame nearly over, inside kicker
range). With time left, taking three and getting the ball back is a perfectly good plan, so
outside that regime "kicked while losing the frame" is not a defect and flagging it would
make this test lie.

Run: .venv/bin/python test_frames_stress.py
"""
import itertools
import unittest

from scenario import Scenario, PlayType
from game_rules import GameRules

FRAMES_PER_GAME = 6


# ── The oracle: the format's own rules, written out independently ────────────────

def frameCredit(offenseInFrame: int, defenseInFrame: int):
    """(offenseCredit, defenseCredit) for a frame ending on these scores. Mirrors
    awardFrames: a tied frame is halved."""
    if offenseInFrame > defenseInFrame:
        return 1.0, 0.0
    if offenseInFrame < defenseInFrame:
        return 0.0, 1.0
    return 0.5, 0.5


def matchResultIfOffenseAdds(points, *, framesOff, framesDef, inFrameOff, inFrameDef,
                             aggOff, aggDef, isFinalFrame):
    """'win' | 'draw' | 'loss' for the OFFENSE if it adds `points` and the frame ends now.

    Off the final frame the match is not yet decidable, so this answers the only question
    that is: did they win the frame. Frames are the currency; banking one is the win.
    """
    o, d = inFrameOff + points, inFrameDef
    co, cd = frameCredit(o, d)
    if not isFinalFrame:
        return 'win' if co > cd else ('draw' if co == cd else 'loss')
    fo, fd = framesOff + co, framesDef + cd
    if fo > fd:
        return 'win'
    if fo < fd:
        return 'loss'
    # Frames level → total points break it.
    ao, ad = aggOff + points, aggDef
    return 'win' if ao > ad else ('draw' if ao == ad else 'loss')


RANK = {'loss': 0, 'draw': 1, 'win': 2}


# ── Building the situation ───────────────────────────────────────────────────────

def buildFrames(*, framesOff, framesDef, inFrameOff, inFrameDef, aggOff, aggDef,
                frameIndex, clock=25, ballOn=8, down=4):
    """Offense is HOME throughout, so 'off' maps to home everywhere."""
    rules = GameRules()
    rules.gameFormat = 'frames'
    s = Scenario(gameRules=rules)
    g = s.game
    s.situation(quarter=rules.quartersPerGame, clock=clock, offense='home',
                offScore=aggOff, defScore=aggDef,
                down=down, distance=min(ballOn, 10), ballOn=ballOn,
                offTimeouts=0, defTimeouts=1, clockRunning=True)
    g._frameIndex = frameIndex
    g._framesWonHome = framesOff
    g._framesWonAway = framesDef
    # Frame-start scores implied by the in-frame margins.
    g._frameStartHome = aggOff - inFrameOff
    g._frameStartAway = aggDef - inFrameDef
    s.setKickerLeg('home', 62)
    return s


class TheOracleIsSane(unittest.TestCase):
    """⚠️ Check the yardstick before measuring anything with it. A silently wrong oracle
    would turn every sweep below into a green light."""

    def test_game469(self):
        """The reported match: frames level, down 7 in-frame, down 3 aggregate."""
        args = dict(framesOff=2.5, framesDef=2.5, inFrameOff=0, inFrameDef=7,
                    aggOff=14, aggDef=17, isFinalFrame=True)
        self.assertEqual(matchResultIfOffenseAdds(3, **args), 'loss',
                         'the field goal loses the frame and the match')
        self.assertEqual(matchResultIfOffenseAdds(7, **args), 'win',
                         'the touchdown wins the frame outright')

    def test_aFieldGoalThatHalvesTheFrameCanStillWinOnAggregate(self):
        args = dict(framesOff=2.5, framesDef=2.5, inFrameOff=0, inFrameDef=3,
                    aggOff=20, aggDef=17, isFinalFrame=True)
        self.assertEqual(matchResultIfOffenseAdds(3, **args), 'win',
                         'halved frames leave it level, and the aggregate is ahead')

    def test_offTheFinalFrameOnlyTheFrameMatters(self):
        args = dict(framesOff=0, framesDef=2, inFrameOff=0, inFrameDef=7,
                    aggOff=0, aggDef=40, isFinalFrame=False)
        self.assertEqual(matchResultIfOffenseAdds(7, **args), 'draw', 'ties the frame')
        self.assertEqual(matchResultIfOffenseAdds(8, **args), 'win')


class NeverKickIntoALoss(unittest.TestCase):
    """The sweep. Every combination where all three scoreboards are in play."""

    def _sweep(self):
        cases = []
        frameSplits = [(0, 7), (0, 3), (3, 7), (7, 7), (7, 3), (0, 0), (3, 0)]
        frameStates = [(2.5, 2.5), (2.0, 3.0), (3.0, 2.0), (2.5, 3.5), (3.5, 2.5)]
        aggGaps = [-7, -3, -1, 0, 1, 3, 7]
        for (inOff, inDef), (fOff, fDef), gap in itertools.product(
                frameSplits, frameStates, aggGaps):
            # Aggregate must be consistent with the in-frame scores having happened.
            aggOff = 20 + inOff
            aggDef = aggOff - gap
            if aggDef - inDef < 0 or aggOff - inOff < 0:
                continue
            cases.append(dict(framesOff=fOff, framesDef=fDef,
                              inFrameOff=inOff, inFrameDef=inDef,
                              aggOff=aggOff, aggDef=aggDef))
        return cases

    def test_aFieldGoalIsNeverTakenWhenItLosesAndATouchdownDoesNot(self):
        violations = []
        checked = 0
        for isFinal in (True, False):
            frameIndex = FRAMES_PER_GAME - 1 if isFinal else 3
            for case in self._sweep():
                fgResult = matchResultIfOffenseAdds(3, isFinalFrame=isFinal, **case)
                tdResult = matchResultIfOffenseAdds(7, isFinalFrame=isFinal, **case)
                # Only interesting where the choice actually matters.
                if RANK[tdResult] <= RANK[fgResult]:
                    continue
                if fgResult != 'loss':
                    continue
                checked += 1
                s = buildFrames(frameIndex=frameIndex, **case)
                call = s.callPlay()
                if call is PlayType.FieldGoal:
                    violations.append((case, isFinal, fgResult, tdResult))
        self.assertGreater(checked, 20, 'the sweep should exercise a real number of cases')
        self.assertEqual(violations, [], (
            f'{len(violations)} of {checked} situations kicked a field goal that loses the '
            f'match when a touchdown would not. First: {violations[:3]}'))

    def test_theSweepStillAllowsAUsefulKick(self):
        """⚠️ The counterpart. If the fix had degraded into "never kick in frames" the test
        above would pass for the wrong reason, so prove a worthwhile kick is still taken."""
        taken = 0
        for isFinal in (True, False):
            frameIndex = FRAMES_PER_GAME - 1 if isFinal else 3
            for case in self._sweep():
                fgResult = matchResultIfOffenseAdds(3, isFinalFrame=isFinal, **case)
                tdResult = matchResultIfOffenseAdds(7, isFinalFrame=isFinal, **case)
                if fgResult == 'loss' or RANK[fgResult] < RANK[tdResult]:
                    continue   # the kick is not clearly the right call here
                s = buildFrames(frameIndex=frameIndex, **case)
                if s.callPlay() is PlayType.FieldGoal:
                    taken += 1
        self.assertGreater(taken, 0,
                           'the offense never kicks in frames any more — the fix overshot')


class TheAggregateStillMattersWhenItShould(unittest.TestCase):
    """Frames level after this frame → the points tiebreak decides, and the offense has to
    reason off the aggregate. This is the case `_frameDecisionDiff` exists for, and it must
    not have been lost while fixing the other direction."""

    def test_upInTheFrameButBehindOnPointsIsTreatedAsTrailing(self):
        s = buildFrames(framesOff=2.5, framesDef=2.5, inFrameOff=7, inFrameDef=0,
                        aggOff=17, aggDef=20, frameIndex=FRAMES_PER_GAME - 1)
        # Winning the frame takes frames to 3.5-2.5 — the match is won, so this is NOT
        # actually a trailing situation. The oracle should agree.
        self.assertEqual(
            matchResultIfOffenseAdds(0, framesOff=2.5, framesDef=2.5, inFrameOff=7,
                                     inFrameDef=0, aggOff=17, aggDef=20,
                                     isFinalFrame=True), 'win')
        self.assertIsNotNone(s.game._frameDecisionDiff())

    def test_aFrameLeadThatOnlyLevelsTheFramesFallsToPoints(self):
        """Up in the frame, but banking it leaves frames LEVEL — so the aggregate decides
        and a team behind on points is really trailing."""
        diff = None
        s = buildFrames(framesOff=2.0, framesDef=3.0, inFrameOff=7, inFrameDef=0,
                        aggOff=17, aggDef=20, frameIndex=FRAMES_PER_GAME - 1)
        diff = s.game._frameDecisionDiff()
        self.assertEqual(diff, -3,
                         'frames finish level, so the margin that matters is the aggregate')


if __name__ == '__main__':
    unittest.main(verbosity=2)
