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
    def __init__(self, name, maxFg=55, accuracy=80):
        self.name = name
        self.coach = None
        self.rosterDict = {'k': Kicker(maxFg, accuracy)}


class Attrs:
    def __init__(self, accuracy):
        self.accuracy = accuracy


class Kicker:
    def __init__(self, maxFg, accuracy=80):
        self.maxFgDistance = maxFg
        self.attributes = Attrs(accuracy)
        self.gameAttributes = None
        self.gameStatsDict = {'kicking': {}}


class Rules:
    timeoutClockThreshold = 120
    fgSnapDistance = 17
    fieldGoalPoints = 3
    touchdownPoints = 6
    extraPointPoints = 1


class StubGame:
    _checkDefensiveTimeout = fg.Game._checkDefensiveTimeout
    _fgValue = fg.Game._fgValue
    _leadIsAboutToEvaporate = fg.Game._leadIsAboutToEvaporate
    _isGarbageTime = fg.Game._isGarbageTime
    _coachClockIQ = fg.Game._coachClockIQ
    _maxPossession = fg.Game._maxPossession
    fgMakeProbability = fg.Game.fgMakeProbability
    _estimateFgProbability = fg.Game._estimateFgProbability

    def __init__(self, *, quarter=4, secs=50, defScore=17, offScore=14,
                 yardsToEndzone=30, timeouts=3, maxFg=55, accuracy=80):
        self.homeTeam = Team('DEFENSE', maxFg, accuracy)   # home = defense
        self.awayTeam = Team('OFFENSE', maxFg, accuracy)
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
        return 2   # the real default two-point conversion

    def _awakenedReadyFor(self, player, kind):
        return False

    def _chargedKickerMaxFg(self, kicker):
        return 99

    def formatTime(self, s):
        return f"0:{s:02d}"

    def wx(self, key):
        return 1.0


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

# ── the touchdown limb: a red-zone threat erases more than a kick can ──────
# Without this the defense had a hole the width of the red zone. Up 5 with the opponent on
# the 3, a FG does not help them, so the kick limb says "clock is your friend" — but they
# are not kicking, they are scoring to go ahead. This is the mirror of _isTdDrainMode,
# which holds exactly that score back; without it the defense cannot answer that play.
r = calls(defScore=19, offScore=14, yardsToEndzone=3, secs=50)
expect(f"up 5, opponent on the 3 -> stops the clock ({r:.0%})", r > 0.4)

r = calls(defScore=21, offScore=14, yardsToEndzone=3, secs=50)
expect(f"up 7 on the 3: a TD still ties, so the clock is not safe ({r:.0%})", r > 0.4)

r = calls(defScore=23, offScore=14, yardsToEndzone=3, secs=50)
expect(f"up 9: beyond one possession, the lead survives any single score ({r:.0%})", r == 0)

r = calls(defScore=19, offScore=14, yardsToEndzone=35, secs=50)
expect(f"up 5 but they are on the 35 — a TD there is a hope, not a threat ({r:.0%})", r == 0)

# ── where the old reasoning is still right ─────────────────────────────────
r = calls(defScore=21, offScore=14, yardsToEndzone=30, secs=50)
expect(f"up 7 at midfield range: a FG leaves them ahead, clock IS their friend ({r:.0%})", r == 0)

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
short = calls(defScore=17, offScore=14, yardsToEndzone=32, secs=50, maxFg=45, accuracy=74)
long_ = calls(defScore=17, offScore=14, yardsToEndzone=32, secs=50, maxFg=62, accuracy=90)
expect(f"a weak-legged kicker is out of range at 32 out ({short:.0%})", short == 0)
expect(f"a big leg at the same spot is a real threat ({long_:.0%})", long_ > 0.4)


# ── IN RANGE IS NOT A THREAT ───────────────────────────────────────────────
# `maxFgDistance` is the kicker's LIMIT, not the distance he converts from, and reading
# only the range is what made this rule help the offense: stopping the clock returns ~18
# yards of field position, worth +0.54 of a made kick at 0.42 and +0.27 at 0.69. So the
# defense spent a timeout to turn a coin flip into a gimme. Reported as the leader
# stopping the clock while the offense was not safely in range.
#
# Bite check: restore `return self.yardsToEndzone <= maxFg` and these three fail.
r = calls(defScore=17, offScore=14, yardsToEndzone=44, secs=50, maxFg=62, accuracy=90)
expect(f"a 61-yard try at 42% is not the expected end of the drive ({r:.0%})", r == 0)

r = calls(defScore=17, offScore=14, yardsToEndzone=38, secs=50, maxFg=55, accuracy=80)
expect(f"nor a 55-yarder at 54%, right at the leg's limit ({r:.0%})", r == 0)

r = calls(defScore=17, offScore=14, yardsToEndzone=20, secs=50, maxFg=55, accuracy=80)
expect(f"a 37-yarder at 94% is, and the clock is nearly free to give back ({r:.0%})",
       r > 0.4)

# The touchdown limb does NOT consult the kick at all — inside 10 yards the score is one
# snap away whoever is kicking, so a hopeless kicker must not make the threat go away.
r = calls(defScore=17, offScore=14, yardsToEndzone=3, secs=50, maxFg=40, accuracy=60)
expect(f"on the 3 with a poor kicker: still a touchdown threat ({r:.0%})", r > 0.4)


# ── THERE MUST BE TIME TO USE WHAT THE TIMEOUT SAVES ───────────────────────
# The exception exists to buy a possession to win in regulation. Nothing checked that a
# possession was still possible: measured over a 432-state sweep the rule fired at the
# same 74% rate at 0:15 as at 1:50, so the clock played no part in the decision. Reported
# as the leader stopping the clock at 0:20 and getting the ball back with nothing to do.
#
# ⚠️ THE BOUNDS ARE DERIVED FROM THE CONSTANT, NOT WRITTEN OUT. This floor has already
# moved once (30 -> 50, after a real season measured the clock falling a median 15s and
# up to 32s between the timeout and the leader's answering possession — the offense plays
# out the REST of its drive, it does not score on the next snap), and the hardcoded 0:45
# case here asserted the old value as correct rather than testing the rule.
#
# Bite check: delete the LEAD_ANSWER_MIN_SECONDS gate and the below-floor cases fail.
from constants import LEAD_ANSWER_MIN_SECONDS as FLOOR              # noqa: E402

for secs in (15, FLOOR // 2, FLOOR - 5):
    r = calls(defScore=17, offScore=14, yardsToEndzone=3, secs=secs)
    expect(f"up 3, they are on the 3, but only 0:{secs} left — no answer to save for "
           f"({r:.0%})", r == 0)

r = calls(defScore=17, offScore=14, yardsToEndzone=3, secs=FLOOR + 5)
expect(f"0:{FLOOR + 5} clears the floor — time for them to score and us to reply "
       f"({r:.0%})", r > 0.4)

# ⚠️ ASYMMETRIC ON PURPOSE. A TRAILING defense at 0:15 loses if it does nothing, so a
# slim chance beats none; the leader is spending the clock that protects its own lead.
r = calls(defScore=14, offScore=17, yardsToEndzone=30, secs=15)
expect(f"a TRAILING defense still spends timeouts at 0:15 ({r:.0%})", r > 0.4)

print("\nPASS — the leader stops the clock exactly when the clock stops helping it."
      if not fails else f"\n{len(fails)} FAILED")
raise SystemExit(1 if fails else 0)
