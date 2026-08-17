"""A sack keeps the clock running — it is a tackle, not a dead ball.

⚠️ `shouldClockRun` splits pass plays on `isPassCompletion`, and a sack is a pass play
that never completed, so it fell into the INCOMPLETION branch and stopped the clock.
The quarterback was tackled in the field of play; that is a running clock, exactly as
a run in bounds is.

⚠️ THE RUNOFF WAS THE SMALLER HALF. The pre-snap huddle is only charged while the
clock is running (`if self.clockRunning` in the play loop), so a sack also made the
FOLLOWING huddle free — 12s hurry-up to 35s relaxed. Roughly 25-35s of game clock
handed back per sack, which is why a team taking a dozen of them played several extra
minutes of football, and why the sack-heavy games were also the longest ones.

Measured over 30 games/arm: plays/game 154.4 -> 147.8, points/game 42.0 -> 34.6. At
five downs over 70 games/arm: 156.3 -> 151.6 and 46.5 -> 43.6.

Scores, turnovers and sack-fumbles are handled by the branches ABOVE the pass split,
so they keep stopping the clock — the tests below pin that ordering, since a sack
guard placed too high would swallow all three.

Run: .venv/bin/python test_sack_clock.py
"""

import os
import sys
import types
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import logging
logging.disable(logging.CRITICAL)

if 'floosball_game' not in sys.modules:
    _stub = types.ModuleType('floosball_game')
    class _GameStub: pass
    _stub.Game = _GameStub
    sys.modules['floosball_game'] = _stub
    import managers.timingManager  # noqa: F401
    del sys.modules['floosball_game']

from scenario import Scenario, PlayType  # noqa: E402


def _sack(**overrides):
    """A game sitting on a resolved sack. Returns (scenario, shouldClockRun())."""
    s = Scenario()
    s.situation(quarter=2, clock=400, down=2, distance=10, ballOn=60)
    play = s.g.play
    play.playType = PlayType.Pass
    play.isSack = True
    play.isPassCompletion = False
    play.isInBounds = True
    play.yardage = -7
    for key, value in overrides.items():
        setattr(play, key, value)
    return s, s.g.shouldClockRun()


class SackClockTests(unittest.TestCase):
    def testASackKeepsTheClockRunning(self):
        """The reported bug: the clock stopped on every sack."""
        _, runs = _sack()
        self.assertTrue(runs, 'a sack is a tackle in the field of play — clock runs')

    def testARunningClockIsNotWhyItRuns(self):
        """The sack must not be riding `clockStopsOnDeadBall`. Under the DEFAULT
        ruleset (dead balls stop the clock) a sack still runs it, because a sack was
        never a dead ball to begin with."""
        s, runs = _sack()
        self.assertTrue(s.g.gameRules.clockStopsOnDeadBall,
                        'default ruleset should stop the clock on dead balls')
        self.assertTrue(runs)

    def testAnIncompletionStillStopsTheClock(self):
        """The branch the sack used to fall into is untouched."""
        s = Scenario()
        s.situation(quarter=2, clock=400)
        play = s.g.play
        play.playType = PlayType.Pass
        play.isSack = False
        play.isPassCompletion = False
        play.isInBounds = True
        self.assertFalse(s.g.shouldClockRun())

    def testASackFumbleLostStillStopsTheClock(self):
        """A turnover is a change of possession however it happened. The guard sits
        BELOW the fumble branch, so this is about ordering, not about sacks."""
        _, runs = _sack(isFumbleLost=True)
        self.assertFalse(runs)

    def testASackSafetyStillStopsTheClock(self):
        """Same ordering point for a score — a sack in the end zone is a safety."""
        _, runs = _sack(isSafety=True, scoreChange=True)
        self.assertFalse(runs)

    def testASackOutOfBoundsFollowsTheDeadBallRule(self):
        """Not currently reachable (the engine never puts a sack out of bounds), but
        the guard reads `isInBounds` rather than assuming it, so it degrades the same
        way a run does if that ever changes."""
        _, runs = _sack(isInBounds=False)
        self.assertFalse(runs)

    def testARunInBoundsIsUnchanged(self):
        """The shape the sack now matches."""
        s = Scenario()
        s.situation(quarter=2, clock=400)
        play = s.g.play
        play.playType = PlayType.Run
        play.isInBounds = True
        self.assertTrue(s.g.shouldClockRun())


if __name__ == '__main__':
    unittest.main(verbosity=2)
