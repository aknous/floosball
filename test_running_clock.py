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
    # ⚠️ A SPIKE IS AN INTENTIONAL INCOMPLETION, and it used to sit in the carve-out list
    # below (owner, 2026-08-25: "teams shouldnt even attempt a spike because its
    # effectively an incomplete pass and shouldnt stop the clock"). It was the one
    # carve-out that was arithmetically inconsistent rather than principled: a punt stops
    # the clock for a reason of its own, and a score and a kick likewise, but a spike is
    # the exact event this rule is ABOUT, merely chosen on purpose.
    ('a spike', dict(playType=PlayType.Spike)),
]
for name, flags in DEAD_BALLS:
    expect(f"{name} stops the clock by default, and does not under a running clock",
           clockRuns(True, **flags) is False and clockRuns(False, **flags) is True)

# ⚠️ These are the documented carve-outs and they are INTENDED, not an oversight. A
# running clock is not a NO-stoppage clock, or there would be no way to stop it at all
# and the spike (the only non-timeout stopper left) would stop mattering.
#
# ⚠️ THE PUNT IS THE ONE MOST LIKELY TO BE READ AS A BUG, and it was — measured, punts
# are 7.6 of the 15.4 stoppages a game that survive the rule, i.e. the single biggest
# residual, which makes a running clock look leaky. Reconfirmed by the owner on
# 2026-08-25 in the running-clock context specifically (the earlier 2026-08-05 call
# that "a punt is a change of possession" predates this rule being live): a punt stops
# the clock under BOTH rules and that is the design. Do not "fix" it.
CARVE_OUTS = [
    ('a score', dict(score=True)),
    ('a field goal', dict(playType=PlayType.FieldGoal)),
    ('a punt', dict(playType=PlayType.Punt)),
]
for name, flags in CARVE_OUTS:
    expect(f"{name} stops the clock under BOTH rules",
           clockRuns(True, **flags) is False and clockRuns(False, **flags) is False)

# ⚠️ Regression guard from a separate fix: a sack is not a dead ball, so it must not
# ride this rule in either direction.
expect("a sack in bounds runs the clock under both rules, being no kind of dead ball",
       clockRuns(True, sack=True) is True and clockRuns(False, sack=True) is True)

# ── 2. nothing stops the clock behind shouldClockRun's back ─────────────────
# ⚠️ Two sites assigned `clockRunning = False` directly instead of returning a verdict,
# and they needed OPPOSITE fixes, which is why a single blanket rule would have been
# wrong for one of them.
#
#   A TURNOVER ON DOWNS genuinely needs the rule, and is the sharper case: its two
#   sibling turnovers (a fumble, an interception) already keep the clock running here,
#   so the third kind stopping it made the rule contradict itself and handed the team
#   that just failed a free stop. `resolveTurnoverOnDowns` is not reached through
#   `shouldClockRun`, so it has to ask.
#
#   A MISSED SIDELINE GOAL needed the assignment DELETED, not corrected. The line looked
#   like the hoop making its own clock determination and was in fact dead: the main loop
#   runs `shouldClockRun()` a few lines later and overwrites it. Proven by removing it
#   and re-measuring — 378 hoop plays across both rules, zero change. `shouldClockRun`
#   reads the flags the hoop sets and gets both cases right on its own.
print("\n-- no stoppage bypasses the rule --")
src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        'floosball_game.py')).read()
expect("a turnover on downs asks the rule rather than assuming",
       src.count('self.clockRunning = not self._deadBallStopsClock()') == 1
       and 'self.clockRunning = False  # Clock stops after a turnover on downs' not in src)
expect("the hoop shot makes NO clock assignment of its own, leaving shouldClockRun to own it",
       'a hoop shot stops the clock (an incomplete throw)' not in src)

# ⚠️ Asserted BEHAVIORALLY rather than by grepping the source, because the point is the
# verdict and not where it comes from: a miss is an incompletion and must ride the rule,
# a make is a score and must stop the clock either way.
def hoopClockStops(stops, made):
    s = scen(stops, quarter=2, clock=300, down=1, distance=10, ballOn=60)
    p = s.game.play
    p.playType = PlayType.Pass
    p.isPassCompletion = made
    p.isInBounds = True
    p.isFumbleLost = p.isInterception = p.isSack = False
    p.scoreChange = made          # a made hoop banks points; a miss is an incompletion
    return s.game.shouldClockRun() is False

expect("a MISSED hoop stops the clock by default and does not under a running clock",
       hoopClockStops(True, False) is True and hoopClockStops(False, False) is False)
expect("a MADE hoop stops the clock under both rules, being a score",
       hoopClockStops(True, True) is True and hoopClockStops(False, True) is True)

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
# ⚠️ HONOURING THE RULE IN `shouldClockRun` IS ONLY HALF OF IT. If the spike stops
# stopping the clock but the DECISION still fires, the offense forfeits a down for
# nothing — the identical failure to throwing at the sideline under a running clock, and
# measured at 1.43 wasted downs a game before this gate. Asserted over full games rather
# than a state sweep, because the spike is gated on a run of conditions (no timeouts,
# late, trailing or Q2, a down to spare) that a constructed state can satisfy while a
# real one rarely does.
print("\n-- and the offense stops calling a play that can no longer do anything --")
import asyncio, numpy as np
from scenario import _makeTeam

async def _game(gid, stops):
    random.seed(gid); np.random.seed(gid % (2**31))
    h = _makeTeam('H', 'HOM', 100 + gid * 10); a = _makeTeam('A', 'AWY', 500 + gid * 10)
    gr = GameRules(); gr.clockStopsOnDeadBall = stops
    g = FG.Game(h, a, gameRules=gr); g.id = gid
    g._anomalyAttentionLoaded = True; g._anomalyEnabled = False
    g._anomalyAttention = {}; g._anomalyState = {}
    g._criticalityMultiplier = 1.0; g._criticalityActive = False; g._anomalyIntensity = 1.0
    await g.playGame(); return g

def spikeCount(stops, n=14):
    total = 0
    for i in range(n):
        g = asyncio.run(_game(i, stops))
        total += sum(1 for f in g.gameFeed
                     if f.get('play') is not None
                     and getattr(f['play'], 'playType', None) is PlayType.Spike)
    return total

onSpikes = spikeCount(True)
offSpikes = spikeCount(False)
expect(f"teams still spike by default ({onSpikes} across 14 games)", onSpikes > 0)
expect(f"and never attempt one under a running clock ({offSpikes})", offSpikes == 0)

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
