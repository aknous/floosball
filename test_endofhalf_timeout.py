"""End-of-half clock-management regression: the offense must spend a timeout to
save a scoring snap instead of letting the clock run out.

Guards the reported bug: a team driving at the end of the half with all three
timeouts reached 4th down with 8s and let the clock expire (the pre-snap huddle
burned the running clock and the play never ran). The safety net
`_maybeCallTimeoutToSaveSnap` now stops the clock — regardless of score in Q2.

Run: .venv/bin/python test_endofhalf_timeout.py
"""
import managers  # resolve circular import
import floosball_game as fg
from floosball_game import PlayType


class Team:
    def __init__(self, name):
        self.name = name


class StubPlay:
    def __init__(self, playType=PlayType.FieldGoal):
        self.playType = playType
        self.insights = {}


class StubGame:
    _maybeCallTimeoutToSaveSnap = fg.Game._maybeCallTimeoutToSaveSnap
    _callTimeout = fg.Game._callTimeout
    _isGarbageTime = fg.Game._isGarbageTime

    def __init__(self, *, quarter, secs, homeScore, awayScore, timeouts=3,
                 clockRunning=True, playType=PlayType.FieldGoal, offenseIsHome=True):
        self.homeTeam = Team('HOME')
        self.awayTeam = Team('AWAY')
        self.offensiveTeam = self.homeTeam if offenseIsHome else self.awayTeam
        self.currentQuarter = quarter
        self.gameClockSeconds = secs
        self.homeScore = homeScore
        self.awayScore = awayScore
        self.homeTimeoutsRemaining = timeouts
        self.awayTimeoutsRemaining = timeouts
        self.clockRunning = clockRunning
        self.play = StubPlay(playType)
        self._timeoutCalled = False
        self.gameFeed = []

    # stubs used by _callTimeout
    def formatTime(self, s): return f'{s}s'
    def broadcastGameState(self, **kw): pass


def calledTimeout(g):
    before = g.homeTimeoutsRemaining
    g._maybeCallTimeoutToSaveSnap()
    return g.homeTimeoutsRemaining < before and not g.clockRunning


CASES = [
    # label, kwargs, expect-timeout
    ("Q2 LEADING, 8s, FG, has TOs -> save the snap",
     dict(quarter=2, secs=8, homeScore=14, awayScore=7), True),
    ("Q2 TRAILING, 8s, FG -> save the snap",
     dict(quarter=2, secs=8, homeScore=7, awayScore=14), True),
    ("Q2 TIED, 8s, pass -> save the snap",
     dict(quarter=2, secs=8, homeScore=10, awayScore=10, playType=PlayType.Pass), True),
    ("Q2 leading, 8s, NO timeouts -> cannot save",
     dict(quarter=2, secs=8, homeScore=14, awayScore=7, timeouts=0), False),
    ("Q2 leading, 30s (plenty) -> no timeout needed",
     dict(quarter=2, secs=30, homeScore=14, awayScore=7), False),
    ("Q2 leading, 8s, clock already stopped -> nothing to save",
     dict(quarter=2, secs=8, homeScore=14, awayScore=7, clockRunning=False), False),
    ("Q2 leading, 8s, PUNT -> not a scoring play",
     dict(quarter=2, secs=8, homeScore=14, awayScore=7, playType=PlayType.Punt), False),
    ("Q4 LEADING, 8s, FG -> leading team drains, no timeout",
     dict(quarter=4, secs=8, homeScore=14, awayScore=7), False),
    ("Q4 TRAILING, 8s, FG -> save the snap",
     dict(quarter=4, secs=8, homeScore=7, awayScore=10), True),
    ("Q4 trailing by 40 (garbage) -> give up",
     dict(quarter=4, secs=8, homeScore=0, awayScore=40), False),
]


def main():
    print(f"\n{'scenario':<52}{'expected':<10}verdict")
    print("-" * 78)
    allPass = True
    for label, kw, expect in CASES:
        got = calledTimeout(StubGame(**kw))
        ok = (got == expect)
        allPass &= ok
        print(f"{label:<52}{'timeout' if expect else 'none':<10}{'PASS' if ok else 'FAIL (got '+('timeout' if got else 'none')+')'}")
    print("\nOVERALL:", "ALL PASS" if allPass else "SOME FAIL")
    return 0 if allPass else 1


if __name__ == '__main__':
    raise SystemExit(main())
