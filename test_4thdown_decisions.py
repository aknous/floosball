"""4th-down decision regression tests — trailing-late FG/punt logic.

Guards two reported bugs in `_fourthDownCaller`:
  1. Down by more than a FG, late, inside the opponent's 40: the caller kicked a
     useless FG (still losing) instead of going for the TD. Fixed by gating the
     "inside the 40" auto-kick on fgHelps.
  2. Trailing late in Q4, deep in own territory: an average-clock-management coach
     punted ~25% of the time (basically conceding). Fixed by widening the
     never-punt window to under 2:00 and tightening the poor-coach punt gate.

Run: .venv/bin/python test_4thdown_decisions.py
"""
import managers  # resolve circular import before importing the engine module
import floosball_game as fg
from floosball_game import PlayType
from game_rules import GameRules
from collections import Counter


class StubKicker:
    def __init__(self, pid=900):
        self.id = pid
        self.maxFgDistance = 55  # kickerMaxDistance = 55 - 17 = 38 (a ~43yd kick is in range)
        self.gameAttributes = type('A', (), {'overallRating': 80})()
        self.gameStatsDict = {'kicking': {}}


class StubCoach:
    # average coach — clockManagement 80 -> _coachClockIQ 0.5
    aggressiveness = 80
    clockManagement = 80
    offensiveMind = 80


class StubTeam:
    def __init__(self, k):
        self.rosterDict = {'k': k}
        self.coach = StubCoach()


class StubPlay:
    def __init__(self):
        self.playType = None
        self.passType = None
        self.targetSideline = False
        self.insights = {}
        self.branch = None
    def passPlay(self, key):
        self.playType = PlayType.Pass
        self.branch = f'Pass({key})'
    def runPlay(self):
        self.playType = PlayType.Run
        self.branch = 'Run'
    def kneel(self):
        self.playType = PlayType.Kneel
        self.branch = 'Kneel'


class StubGame:
    def __init__(self):
        self.gameRules = GameRules()
        self.kicker = StubKicker()
        self.offensiveTeam = StubTeam(self.kicker)
        self.defensiveTeam = StubTeam(StubKicker(901))
        self.homeTeam = self.offensiveTeam
        self.awayTeam = self.defensiveTeam
        self.homeScore = 0
        self.awayScore = 0
        self.play = StubPlay()
        self._awakenedReady = {}
        self._awakenedPower = {}
        self.homeTimeoutsRemaining = 3
        self.awayTimeoutsRemaining = 3
        self.yardsToEndzone = 40
        self.yardsToFirstDown = 10
        self.yardsToSafety = 60
        self.currentQuarter = 4
        self.gameClockSeconds = 120
        self.down = 4

    _fourthDownCaller      = fg.Game._fourthDownCaller
    _shouldTargetSideline  = fg.Game._shouldTargetSideline
    _coachClockIQ          = fg.Game._coachClockIQ
    _estimateFgProbability = fg.Game._estimateFgProbability
    _coachFgThreshold      = fg.Game._coachFgThreshold
    _awakenedReadyFor      = fg.Game._awakenedReadyFor
    _isFgDrainMode         = fg.Game._isFgDrainMode
    _isGarbageTime         = fg.Game._isGarbageTime

    def _selectPassPlay(self, tier):
        return tier


def distribution(scoreDiff, yte, ytfd, ysafe, clk, n=400):
    """Run a 4th-down scenario n times and return the play-type distribution."""
    c = Counter()
    for _ in range(n):
        g = StubGame()
        g.yardsToEndzone = yte
        g.yardsToFirstDown = ytfd
        g.yardsToSafety = ysafe
        g.gameClockSeconds = clk
        g._fourthDownCaller(scoreDiff, g.offensiveTeam.coach, isHome=True)
        c[g.play.playType.name if g.play.playType else 'None'] += 1
    return c


# scenario, params (scoreDiff, yte, ytfd, ysafe, clk), predicate(distribution)->bool, expectation
CASES = [
    ("BUG1 down 5, opp 26, 4th&8, Q4 0:05",
     (-5, 26, 8, 74, 5),   lambda d: d['FieldGoal'] == 0,               "never FieldGoal (go for the TD)"),
    ("BUG2 down 4, own 35, 4th&10, Q4 1:00",
     (-4, 65, 10, 35, 60), lambda d: d['Punt'] == 0,                    "never Punt (avg coach goes for it)"),
    ("down 4, own 35, 4th&10, Q4 1:59 (edge of window)",
     (-4, 65, 10, 35, 119), lambda d: d['Punt'] == 0,                   "never Punt under 2:00"),
    ("CTRL down 2, opp 30, 4th&8, Q4 0:05",
     (-2, 30, 8, 70, 5),   lambda d: d['FieldGoal'] == d.total() if hasattr(d,'total') else d['FieldGoal'] > 0, "FieldGoal (a FG ties/helps)"),
    ("CTRL leading +3, own 20, 4th&10, Q4 3:00",
     (3, 80, 10, 20, 180), lambda d: d['Punt'] > 0,                     "Punt allowed (not desperation)"),
]


def main():
    print(f"\n{'scenario':<48}{'result':<28}{'expected':<40}verdict")
    print("-" * 130)
    allPass = True
    for label, params, pred, exp in CASES:
        d = distribution(*params)
        ok = pred(d)
        allPass &= ok
        res = ", ".join(f"{k}:{v}" for k, v in sorted(d.items()))
        print(f"{label:<48}{res:<28}{exp:<40}{'PASS' if ok else 'FAIL'}")
    print("\nOVERALL:", "ALL PASS" if allPass else "SOME FAIL")
    return 0 if allPass else 1


if __name__ == '__main__':
    raise SystemExit(main())
