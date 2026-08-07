"""A leading defense must stop the clock when its lead is about to evaporate.

Reported live: a defense up 3 let the offense milk the clock from inside field-goal range
and kick with 0:07 left, holding three timeouts the whole way. `_checkDefensiveTimeout`
returned immediately for any Q4 defense that was level or ahead, on the reasoning that a
leading team wants the clock to run.

That reasoning only holds while the lead SURVIVES the drive. Once the offense is in range
with a lead of 3 or less, the likely end of the possession is a kick that ties or wins it,
so every second the leader lets tick away comes off its OWN answer. Stopping the clock
costs a timeout it has no other use for and buys a possession to win in regulation instead
of a coin-flip overtime.

Run: .venv/bin/python test_leading_defense_timeout.py   (exits non-zero on any failure)
"""
import random
import managers  # resolve circular import
import floosball_game as fg


class Team:
    def __init__(self, name, maxFg=55):
        self.name = name
        self.coach = None
        self.rosterDict = {'k': Kicker(maxFg)}


class Kicker:
    def __init__(self, maxFg):
        self.maxFgDistance = maxFg


class Rules:
    timeoutClockThreshold = 120
    fgSnapDistance = 17


class StubGame:
    _checkDefensiveTimeout = fg.Game._checkDefensiveTimeout
    _leadIsAboutToEvaporate = fg.Game._leadIsAboutToEvaporate
    _isGarbageTime = fg.Game._isGarbageTime
    _coachClockIQ = fg.Game._coachClockIQ
    _maxPossession = fg.Game._maxPossession

    def __init__(self, *, quarter=4, secs=50, defScore=17, offScore=14,
                 yardsToEndzone=30, timeouts=3, maxFg=55):
        self.homeTeam = Team('DEFENSE', maxFg)      # home = defense
        self.awayTeam = Team('OFFENSE', maxFg)
        self.offensiveTeam = self.awayTeam
        self.defensiveTeam = self.homeTeam
        self.currentQuarter = quarter
        self.gameClockSeconds = secs
        self.homeScore = defScore
        self.awayScore = offScore
        self.homeTimeoutsRemaining = timeouts
        self.awayTimeoutsRemaining = timeouts
        self.clockRunning = True
        self.yardsToEndzone = yardsToEndzone
        self.gameRules = Rules()
        self.gameFeed = []
        self._timeoutCalled = False
        self._clockStoppedByWarning = False
        self.twoMinuteWarningShown = True
        self.timingManager = None

    def broadcastGameState(self, **kw):
        pass

    def _maxLadderPoints(self):
        return 0

    def _awakenedReadyFor(self, player, kind):
        return False

    def _chargedKickerMaxFg(self, kicker):
        return 99

    def formatTime(self, s):
        return f"0:{s:02d}"


def calls(**kw):
    """Fraction of runs where the defense burns a timeout."""
    random.seed(4)
    hits = 0
    for _ in range(400):
        g = StubGame(**kw)
        g._checkDefensiveTimeout()
        if g._timeoutCalled:
            hits += 1
    return hits / 400


fails = []
def expect(d, c):
    print(f"  [{'OK' if c else 'FAIL'}] {d}")
    if not c: fails.append(d)


# ── the reported game ───────────────────────────────────────────────────────
r = calls(defScore=17, offScore=14, yardsToEndzone=30, secs=50)
expect(f"up 3, offense in FG range, 0:50 left -> stops the clock ({r:.0%})", r > 0.4)

r = calls(defScore=17, offScore=17, yardsToEndzone=30, secs=50)
expect(f"TIED with the offense in range -> also stops the clock ({r:.0%})", r > 0.4,)

# ── where the old reasoning is still right ─────────────────────────────────
r = calls(defScore=21, offScore=14, yardsToEndzone=30, secs=50)
expect(f"up 7: a FG leaves them ahead, so the clock IS their friend ({r:.0%})", r == 0)

r = calls(defScore=17, offScore=14, yardsToEndzone=75, secs=50)
expect(f"up 3 but the offense is 75 out, nowhere near range ({r:.0%})", r == 0)

r = calls(defScore=17, offScore=14, yardsToEndzone=30, secs=50, timeouts=0)
expect("no timeouts left -> nothing to spend", r == 0)

# ── it is a LATE-game rule, not a whole-quarter one ────────────────────────
r = calls(defScore=17, offScore=14, yardsToEndzone=30, secs=400)
expect(f"6:40 left is too early to burn timeouts on this ({r:.0%})", r == 0)

# ── a trailing defense is unaffected ───────────────────────────────────────
r = calls(defScore=14, offScore=17, yardsToEndzone=30, secs=50)
expect(f"trailing defense still stops the clock as before ({r:.0%})", r > 0.4)

# ── range is read off the kicker, not a constant ───────────────────────────
short = calls(defScore=17, offScore=14, yardsToEndzone=45, secs=50, maxFg=45)
long_ = calls(defScore=17, offScore=14, yardsToEndzone=45, secs=50, maxFg=62)
expect(f"a weak-legged kicker is not yet a threat at 45 out ({short:.0%})", short == 0)
expect(f"a big leg at the same spot is ({long_:.0%})", long_ > 0.4)

print("\nPASS — the leader stops the clock exactly when the clock stops helping it."
      if not fails else f"\n{len(fails)} FAILED")
raise SystemExit(1 if fails else 0)
