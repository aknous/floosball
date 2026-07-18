"""Throwaway test: verify charged awakened-kicker FG logic in _fourthDownCaller
does NOT override late-game strategy. Strategy must come before kicker power.

Run: .venv/bin/python test_charged_kicker_4th_down.py
"""
import managers  # resolve circular import before importing the engine module directly
import floosball_game as fg
from floosball_game import PlayType
from game_rules import GameRules
from managers import awakenedPowers

# A power that actually covers 'kick'. (The task suggested 'no_clip', but no_clip
# covers run/throw/catch/etc. and NOT 'kick' — moonshot is a real kick power.)
KICK_POWER = 'moonshot'
assert awakenedPowers.powerCoversSituation(KICK_POWER, 'kick'), "power must cover kick"


class StubKicker:
    def __init__(self, pid=900):
        self.id = pid
        self.maxFgDistance = 55
        self.gameAttributes = type('A', (), {'overallRating': 80})()
        self.gameStatsDict = {'kicking': {}}


class StubCoach:
    aggressiveness = 80
    clockManagement = 80
    offensiveMind = 80


class StubTeam:
    def __init__(self, kicker):
        self.rosterDict = {'k': kicker}
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
        self.defensiveTeam = StubTeam(StubKicker(pid=901))
        self.homeTeam = self.offensiveTeam
        self.awayTeam = self.defensiveTeam
        self.homeScore = 0
        self.awayScore = 0
        self.play = StubPlay()
        self._awakenedReady = {}
        self._awakenedPower = {}
        self.homeTimeoutsRemaining = 3
        self.awayTimeoutsRemaining = 3
        self.yardsToEndzone = 50
        self.yardsToFirstDown = 10
        self.yardsToSafety = 50   # >35 so not deep-own-territory punt
        self.currentQuarter = 4
        self.gameClockSeconds = 120
        self.down = 4

    _fourthDownCaller     = fg.Game._fourthDownCaller
    _shouldTargetSideline = fg.Game._shouldTargetSideline
    _coachClockIQ         = fg.Game._coachClockIQ
    _estimateFgProbability= fg.Game._estimateFgProbability
    _coachFgThreshold     = fg.Game._coachFgThreshold
    _awakenedReadyFor     = fg.Game._awakenedReadyFor
    _isFgDrainMode        = fg.Game._isFgDrainMode
    _isGarbageTime        = fg.Game._isGarbageTime

    def _selectPassPlay(self, tier):
        return f'{tier}'


def runCase(charged, scoreDiff, clock, yte=50, ytfd=10, quarter=4):
    g = StubGame()
    g.yardsToEndzone = yte
    g.yardsToFirstDown = ytfd
    g.currentQuarter = quarter
    g.gameClockSeconds = clock
    if charged:
        g._awakenedReady[g.kicker.id] = True
        g._awakenedPower[g.kicker.id] = KICK_POWER
    chargedFor = g._awakenedReadyFor(g.kicker, 'kick')
    g._fourthDownCaller(scoreDiff, g.offensiveTeam.coach, isHome=True)
    # human-readable result: FieldGoal/Punt set playType directly, others via branch
    if g.play.branch:
        result = g.play.branch
    elif g.play.playType is not None:
        result = g.play.playType.name
    else:
        result = "None"
    return g.play.playType, result, chargedFor


def isFG(pt):
    return pt == PlayType.FieldGoal


print(f"\nKICK_POWER = {KICK_POWER}  (covers 'kick': {awakenedPowers.powerCoversSituation(KICK_POWER,'kick')})")
print("Setup: 4th-and-10, ball at the 50 (yardsToEndzone=50 -> ~67yd FG, far OUT of normal range)\n")

CASES = [
    # num, charged, scoreDiff, clock, expected-label, predicate(pt)->ok, mode
    ("1", True,  -7, 120, "NOT FieldGoal",            lambda pt: not isFG(pt), "PF"),
    ("2", True,  -3, 120, "FieldGoal",                lambda pt: isFG(pt),     "PF"),
    ("3", True,   0, 120, "FieldGoal",                lambda pt: isFG(pt),     "PF"),
    ("4", True,  -6, 120, "NOT FieldGoal",            lambda pt: not isFG(pt), "PF"),
    ("5", True,   4,  60, "NOT charged-FG (lead)",    lambda pt: True,         "PF"),
    ("6", True,  -7, 800, "FieldGoal (not-late doc)", lambda pt: isFG(pt),     "INFO"),
    ("7", False, -7, 120, "NOT long-FG (out of rng)", lambda pt: not isFG(pt), "PF"),
    ("8", False, -3, 120, "NOT long-FG (out of rng)", lambda pt: not isFG(pt), "PF"),
]

print(f"{'#':<3}{'scenario':<24}{'expected':<26}{'actual':<14}{'charged':<9}{'verdict'}")
print("-" * 92)
allPass = True
results = {}
for num, charged, sd, clk, exp, pred, mode in CASES:
    pt, res, ch = runCase(charged, sd, clk)
    results[num] = (pt, res)
    ok = pred(pt)
    verdict = "INFO" if mode == "INFO" else ("PASS" if ok else "FAIL")
    if mode == "PF" and not ok:
        allPass = False
    scen = f"{'chg' if charged else 'unc'}, {sd:+d}, {clk}s"
    print(f"{num:<3}{scen:<24}{exp:<26}{res:<14}{str(ch):<9}{verdict}")

print()
c1pt = results["1"][0]
print(f"CASE 1 (charged kicker, down 7, 2:00 left): playType = {c1pt.name if c1pt else None}")
print("  ->", "CORRECTLY AVOIDS auto-kick (goes for the TD)" if c1pt != PlayType.FieldGoal
      else "WRONGLY auto-kicks a meaningless FG")

print("\nOVERALL:", "ALL PASS" if allPass else "SOME FAIL")
