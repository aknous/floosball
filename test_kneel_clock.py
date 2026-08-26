"""Kneel clock behavior: the kneel itself drains only the snap-to-knee-down time
(~4s) and leaves the clock RUNNING, whatever the clock was doing before the snap.
The remaining ~36s of play clock is drained post-play in the game loop, AFTER the
defense gets its chance to call timeout.

⚠️ This originally asserted that a kneel from a STOPPED clock skipped the ~36s drain,
via a `_kneelClockWasRunning` flag. That rule was superseded and the flag deleted — a
stopped clock RESTARTS at the snap and then runs off, so the runoff applies either way.
What still holds, and is guarded below, is that a 4th-down kneel is a turnover on downs
with time left on the clock.

Run: .venv/bin/python test_kneel_clock.py
"""
import managers  # resolve circular import
import floosball_game as fg
from floosball_game import PlayResult
from game_rules import GameRules


class StubGame:
    def __init__(self, clockRunning, secs=31, down=4):
        self.clockRunning = clockRunning
        self.gameClockSeconds = secs
        self.down = down
        self.gameRules = GameRules()

    # ⚠️ `kneel` runs the clock through `self.game.format.consumeTime`, so a stub without
    # a format raises AttributeError before reaching a single assertion. Resolved the
    # same way `Game.format` does (from gameRules.gameFormat, defaulting to standard,
    # which is a pure pass-through) rather than stubbed to a fake, so this test keeps
    # exercising the real clock path.
    @property
    def format(self):
        from game_formats import getFormat
        return getFormat(getattr(self.gameRules, 'gameFormat', 'standard') or 'standard')


class StubPlay:
    kneel = fg.Play.kneel
    def __init__(self, game):
        self.game = game


def main():
    fails = []

    # ⚠️ THE PRIOR-CLOCK-STATE DISTINCTION WAS DELIBERATELY REMOVED. These two cases used
    # to assert a `_kneelClockWasRunning` flag that the loop read to decide whether to
    # drain the remaining ~36s. `kneel` no longer sets it and the attribute is gone from
    # the engine entirely: a stopped clock simply RESTARTS at the snap and then runs off,
    # so the runoff applies either way, and the defense's protection is its post-play
    # timeout chance rather than a skipped drain. Asserting the old flag failed with an
    # AttributeError before reaching cases 3 and 4, which are still live rules.
    # What remains true of the kneel ITSELF: it drains only the snap-to-knee-down time
    # and leaves the clock running, from either starting state.

    # 1. Clock RUNNING before the snap: only the ~4s snap comes off here.
    g = StubGame(clockRunning=True); p = StubPlay(g); p.kneel()
    ok = (g.gameClockSeconds == 27 and g.clockRunning is True)
    print(f"{'clock RUNNING -> drains the 4s snap, clock left running':<58}{'PASS' if ok else 'FAIL'}")
    fails.append(not ok)

    # 2. Clock STOPPED before the snap (timeout): identical, because the snap restarts it.
    g = StubGame(clockRunning=False); p = StubPlay(g); p.kneel()
    ok = (g.gameClockSeconds == 27 and g.clockRunning is True)
    print(f"{'clock STOPPED -> same 4s, snap restarts the clock':<58}{'PASS' if ok else 'FAIL'}")
    fails.append(not ok)

    # 3. A kneel on the FINAL down is a turnover on downs (so a non-game-ending
    #    kneel hands the ball to the defense).
    g = StubGame(clockRunning=False, down=4); p = StubPlay(g); p.kneel()
    ok = (p.playResult == PlayResult.TurnoverOnDowns)
    print(f"{'4th-down kneel -> TurnoverOnDowns':<58}{'PASS' if ok else 'FAIL'}")
    fails.append(not ok)

    # 4. A kneel on an earlier down keeps possession (labels the next down).
    g = StubGame(clockRunning=True, down=1); p = StubPlay(g); p.kneel()
    ok = (p.playResult != PlayResult.TurnoverOnDowns)
    print(f"{'1st-down kneel -> not a turnover':<58}{'PASS' if ok else 'FAIL'}")
    fails.append(not ok)

    allPass = not any(fails)
    print("\nOVERALL:", "ALL PASS" if allPass else "SOME FAIL")
    return 0 if allPass else 1


if __name__ == '__main__':
    raise SystemExit(main())
