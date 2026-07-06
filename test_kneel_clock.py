"""Kneel clock-drain regression: a kneel only drains the full play clock when the
clock was RUNNING before the snap.

Guards the reported bug: a defense's last timeout stopped the clock at 31s, then
the leading offense kneeled on 4th down and the sim drained the full ~40s to 0.
A kneel from a STOPPED clock burns only the ~4s of the kneel itself (the clock
restarts at the snap, ball immediately dead), so on 4th down it's a
turnover-on-downs with time still on the clock.

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


class StubPlay:
    kneel = fg.Play.kneel
    def __init__(self, game):
        self.game = game


def main():
    fails = []

    # 1. Clock RUNNING before the snap: kneel drains its 4s snap now; the loop
    #    will additionally drain (kneelDrainSeconds - 4) because _kneelClockWasRunning.
    g = StubGame(clockRunning=True); p = StubPlay(g); p.kneel()
    ok = (g._kneelClockWasRunning is True and g.gameClockSeconds == 27 and g.clockRunning is True)
    print(f"{'clock RUNNING -> remembers True, drains 4s snap':<58}{'PASS' if ok else 'FAIL'}")
    fails.append(not ok)

    # 2. Clock STOPPED before the snap (timeout): kneel must remember that so the
    #    loop SKIPS the ~36s play-clock drain — only the 4s snap comes off.
    g = StubGame(clockRunning=False); p = StubPlay(g); p.kneel()
    ok = (g._kneelClockWasRunning is False and g.gameClockSeconds == 27)
    print(f"{'clock STOPPED -> remembers False (loop skips 36s drain)':<58}{'PASS' if ok else 'FAIL'}")
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
