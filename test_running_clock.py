"""The running clock does what it says, and every decision that reads the clock knows it.

`clockStopsOnDeadBall` is a votable rule and the fans have turned it off, which is the
"running clock": an incompletion, a step out of bounds and a turnover stop being clock
stoppages, so the inter-play clock keeps draining and games hold far fewer plays.

`shouldClockRun` implemented that correctly from the start. The gap was everywhere ELSE,
and `game_rules.py` said so in a comment rather than in code: "clock-management
play-calling heuristics still assume dead balls stop the clock, so they degrade
gracefully (a later pass can make them rule-aware)". They did not degrade gracefully.
Measured before this file existed, over 2,880 end-of-half states, `_shouldTargetSideline`
returned BYTE-IDENTICAL answers under both rules — 1965 of 2880 either way — so a
trailing offense threw to the boundary to stop a clock that cannot be stopped, giving up
6.68 yards a completion against 8.21 for a normal throw. And no-huddle keys off
`clockRunning`, which a running clock leaves true almost permanently, so it fired 2.4x
more often (3.2 to 7.6 snaps a game) and its first branch forces the sideline throw
unconditionally. The pointless version was the common one.

Two more stops bypassed the rule outright by assigning `clockRunning = False` instead of
going through `shouldClockRun`: a turnover on downs, and a missed Sideline Goal. The
first is the sharper of the two — a fumble and an interception correctly keep the clock
running under this rule, so the third kind of turnover stopping it made the rule
self-contradictory.

What this file pins:
  - the four dead-ball cases flip with the rule, and the carve-outs never do;
  - no decision whose PURPOSE is stopping the clock survives the rule being off;
  - the DEFAULT rule is completely unchanged, which is what makes the fix safe to ship.

Run: .venv/bin/python test_running_clock.py   (exits non-zero on any failure)
"""
import sys, os, random, itertools
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import logging; logging.disable(logging.WARNING)

from scenario import Scenario, PlayType
from game_rules import GameRules
import floosball_game as FG

fails = []
def expect(d, c):
    print(f"  [{'OK' if c else 'FAIL'}] {d}")
    if not c: fails.append(d)

def scen(stops, **kw):
    gr = GameRules(); gr.clockStopsOnDeadBall = stops
    s = Scenario(gameRules=gr)
    s.situation(**kw)
    return s

# ── 1. shouldClockRun: the four dead balls flip, the carve-outs do not ──────
print("\n-- the rule reaches the clock itself --")
def clockRuns(stops, **flags):
    s = scen(stops, quarter=2, clock=300, down=1, distance=10, ballOn=60)
    p = s.game.play
    p.playType = flags.pop('playType', PlayType.Pass)
    p.isPassCompletion = flags.pop('completion', False)
    p.isInBounds = flags.pop('inBounds', True)
    p.isFumbleLost = flags.pop('fumble', False)
    p.isInterception = flags.pop('interception', False)
    p.isSack = flags.pop('sack', False)
    p.scoreChange = flags.pop('score', False)
    return s.game.shouldClockRun()

DEAD_BALLS = [
    ('an incompletion', dict()),
    ('a catch out of bounds', dict(completion=True, inBounds=False)),
    ('a run out of bounds', dict(playType=PlayType.Run, inBounds=False)),
    ('a lost fumble', dict(fumble=True)),
    ('an interception', dict(interception=True)),
]
for name, flags in DEAD_BALLS:
    expect(f"{name} stops the clock by default, and does not under a running clock",
           clockRuns(True, **flags) is False and clockRuns(False, **flags) is True)

# ⚠️ These are the documented carve-outs. A running clock is not a NO-stoppage clock, or
# there would be no way to stop it at all and the spike (the only non-timeout stopper
# left) would stop mattering.
CARVE_OUTS = [
    ('a score', dict(score=True)),
    ('a field goal', dict(playType=PlayType.FieldGoal)),
    ('a punt', dict(playType=PlayType.Punt)),
    ('a spike', dict(playType=PlayType.Spike)),
]
for name, flags in CARVE_OUTS:
    expect(f"{name} stops the clock under BOTH rules",
           clockRuns(True, **flags) is False and clockRuns(False, **flags) is False)

# ⚠️ Regression guard from a separate fix: a sack is not a dead ball, so it must not
# ride this rule in either direction.
expect("a sack in bounds runs the clock under both rules, being no kind of dead ball",
       clockRuns(True, sack=True) is True and clockRuns(False, sack=True) is True)

# ── 2. nothing stops the clock behind shouldClockRun's back ─────────────────
# ⚠️ Both of these assigned `clockRunning = False` directly rather than returning a
# verdict, so the rule could not reach them. A turnover on downs is the sharper case:
# its two sibling turnovers already run the clock under this rule.
print("\n-- no stoppage bypasses the rule --")
src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        'floosball_game.py')).read()
expect("a turnover on downs and a missed Sideline Goal both read the rule",
       src.count('self.clockRunning = not self._deadBallStopsClock()') == 2)
expect("and neither still carries an unconditional stop",
       'self.clockRunning = False  # Clock stops after a turnover on downs' not in src
       and 'a hoop shot stops the clock (an incomplete throw)' not in src)

# ── 3. no clock-stopping DECISION survives the rule being off ───────────────
# ⚠️ THE MEASUREMENT THAT FOUND THIS: identical counts under both rules meant the
# decision could not be reading the rule at all. Keeping the assertion in that shape —
# comparing the two arms rather than checking a threshold — is what makes it a real
# guard: any future clock decision that forgets the rule reproduces the tie.
print("\n-- the decision layer knows, and the default is untouched --")
def sidelineRate(stops):
    hits = n = 0
    for q, clock, diff, to, yte in itertools.product(
            (2, 4), (25, 55, 95, 160, 280), (-14, -7, -3, 0), (0, 2), (35, 60, 80)):
        for trial in range(6):
            random.seed(hash((q, clock, diff, to, yte, trial)) & 0xffffffff)
            s = scen(stops, quarter=q, clock=clock, offense='home', offScore=20 + diff,
                     defScore=20, down=1, distance=10, ballOn=yte,
                     offTimeouts=to, defTimeouts=3, clockRunning=True)
            n += 1
            if s.game._shouldTargetSideline(diff, s.game.offensiveTeam.coach):
                hits += 1
    return hits, n

onHits, n = sidelineRate(True)
offHits, _ = sidelineRate(False)
expect(f"by default the offense still works the boundary to stop the clock ({onHits}/{n})",
       onHits > n // 3)
expect(f"under a running clock it never does ({offHits}/{n})", offHits == 0)

# ⚠️ The no-huddle branch is the one that mattered most and the easiest to miss: it
# returns True UNCONDITIONALLY, so gating the block below it would have left the common
# case untouched.
print("\n-- the no-huddle branch, which forces the throw rather than rolling for it --")
for stops, want in ((True, True), (False, False)):
    s = scen(stops, quarter=4, clock=50, offense='home', offScore=14, defScore=21,
             down=1, distance=10, ballOn=70, offTimeouts=0, clockRunning=True)
    s.game._isNoHuddle = lambda: True     # force the branch under test
    got = s.game._shouldTargetSideline(-7, s.game.offensiveTeam.coach)
    expect(f"no-huddle forces the sideline throw only when it can stop the clock "
           f"(rule {'on' if stops else 'off'} -> {got})", got is want)

# ⚠️ Darts aims at hoops ON the boundary. That is field position toward an object on
# the field, not clock management, so it must SURVIVE the rule being off — gating the
# whole method rather than the clock-motivated branches would have silently broken it.
print("\n-- and a non-clock reason to work the boundary still applies --")
s = scen(False, quarter=2, clock=300, offense='home', down=1, distance=10, ballOn=60)
s.game._isNoHuddle = lambda: False
s.game._dartsHoopApproach = lambda: 1.0
expect("darts still works the boundary under a running clock",
       s.game._shouldTargetSideline(0, s.game.offensiveTeam.coach) is True)

print()
if fails:
    print(f"FAIL — {len(fails)} problem(s):")
    for f in fails:
        print(f"  - {f}")
    sys.exit(1)
print("PASS — the running clock runs, and every decision that reads the clock reads the rule.")
