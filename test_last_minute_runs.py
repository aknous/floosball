"""The last minute of each half, tied or trailing at the end of the game, is pass-first (2026-10-29, prod week of 10-29).

1. The trailing desperation cut on the run weight went through `_mul`, which scales it by
   the coach's clock IQ, so an average coach kept ~37% of it; a TIED team got no cut at
   all. Prod game 5464: the Normals, tied at the KCS 39 with 0:29 and two timeouts, ran
   for 1 and 2 yards (a timeout after each) and missed a 53-yard kick. Harness vs NFL
   2016-24, last 1:00 in its own half: tied 37% runs (NFL 11%), trailing 11-13% (0-1%).
2. A snap the coach plays for the touchdown (`deferFG`, `pushForTD`) kept the field-goal
   drain's tripled run weight. Prod game 5469: the Sand Dollars, down 3 at the COL 26 with
   0:23, "try for the TD to win outright", ran for a yard and burned 18 seconds (60% runs
   in that spot on the old engine). Off the drain, a running clock now gets a timeout too.
3. The drains themselves are untouched: tied in a comfortable kick with the clock short,
   the offense still runs it down and kicks last (NFL 84% runs inside the 30).
4. The last 1:00 of the first half used a flat clock-IQ-scaled cut at any field position,
   so it ran 20-27% between the 30s under 0:40 (NFL 4-6%) and 22% at the opponent's 1-10
   with 1:30 (NFL 51%). Now the cut follows `_halfRunWeight`: how short the clock is for
   the yards to the end zone, nothing when nothing is in reach.
5. Behind at the end of the game with no timeout, a run that does not score loses: it is
   tackled in bounds and no snap fits after it (`_runEndsTheGame`). Prod game 5525: SEO,
   down 7, 4th & 3 at the MEX 8 with 0:11, ran and was tackled at the 9. The late
   fourth-down tree also hardcoded its go play (a run on every 4th & 1-3 inside the 40, a
   pass everywhere else); it now goes through the normal play path (`_lateGoForIt`).
6. At the half with nothing in reach, the offense does not spend timeouts (`_halfPlayedOut`):
   games 5518 and 5525 had teams on their own 6 and 27 calling a timeout, then running.

Run: .venv/bin/python test_last_minute_runs.py   (exits non-zero on any failure)
"""
import sys, os, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import logging; logging.disable(logging.WARNING)

import numpy as np
from scenario import Scenario
import floosball_game as FG

fails = []
def expect(d, c):
    print(f"  [{'OK' if c else 'FAIL'}] {d}")
    if not c: fails.append(d)

TRIALS = 200


def runRate(kickerLeg=None, onlyDecision=None, **kw):
    runs = n = 0
    for i in range(TRIALS):
        random.seed(i); np.random.seed(i)
        s = Scenario()
        if kickerLeg:
            s.setKickerLeg('home', kickerLeg)
        s.situation(**kw)
        pt = s.callPlay()
        cm = s.g.play.insights.get('clockMgmt') or {}
        if onlyDecision and cm.get('decision') != onlyDecision:
            continue
        if pt not in (FG.PlayType.Run, FG.PlayType.Pass):
            continue
        n += 1
        runs += pt is FG.PlayType.Run and not getattr(s.g.play, 'isScramble', False)
    return (runs / n if n else float('nan')), n


print("\n-- 1. tied or trailing in the last minute, needing yards --")
r, n = runRate(kickerLeg=73, quarter=4, clock=29, down=1, distance=10, ballOn=39,
               offScore=13, defScore=13, offTimeouts=2)
expect(f"tied at the opponent's 39, 0:29, edge of range (game 5464): pass ({r:.0%} runs, n={n})",
       r <= 0.12)
r, n = runRate(quarter=4, clock=28, down=1, distance=10, ballOn=80, offScore=20, defScore=20,
               offTimeouts=3)
expect(f"tied at its own 20, 0:28: pass-first ({r:.0%} runs, n={n})", r <= 0.15)
r, n = runRate(quarter=4, clock=45, down=2, distance=8, ballOn=60, offScore=17, defScore=20,
               offTimeouts=1)
expect(f"down 3 at its own 40, 0:45: pass ({r:.0%} runs, n={n})", r <= 0.12)

print("\n-- 2. a snap played for the touchdown does not drain --")
r, n = runRate(onlyDecision='deferFG', quarter=4, clock=23, down=2, distance=5, ballOn=26,
               offScore=13, defScore=16, offTimeouts=2, clockRunning=False)
expect(f"down 3 at the COL 26, 0:23, clock stopped, deferFG (game 5469): pass ({r:.0%} runs, n={n})",
       n >= 100 and r <= 0.15)
# With the clock running, playing for the touchdown stops it rather than draining it.
stops = 0
for i in range(TRIALS):
    random.seed(i); np.random.seed(i)
    s = Scenario().situation(quarter=4, clock=23, down=2, distance=5, ballOn=26,
                             offScore=13, defScore=16, offTimeouts=2, clockRunning=True)
    s.callPlay()
    stops += s.g.homeTimeoutsRemaining < 2
expect(f"same with the clock running: call a timeout ({stops / TRIALS:.0%})", stops / TRIALS >= 0.6)

print("\n-- 3. the drains still run the clock down --")
r, n = runRate(quarter=4, clock=40, down=1, distance=10, ballOn=15, offScore=20, defScore=20,
               offTimeouts=2)
expect(f"tied at the opponent's 15, 0:40, chip-shot kick: drain ({r:.0%} runs, n={n})", r >= 0.5)

print("\n-- 4. the end of the first half: the run follows the clock left for the yards --")
# Stopped clock: on a running one a no-huddle snap's menu is passes only. Ahead 10-7, so
# the field-goal drain (tied or down 1-3) is not what is being measured.
r, n = runRate(quarter=2, clock=30, down=1, distance=10, ballOn=22, offScore=10, defScore=7,
               offTimeouts=2, clockRunning=False)
expect(f"Q2 0:30 at the opponent's 22, two timeouts: pass ({r:.0%} runs, n={n})", r <= 0.25)
r, n = runRate(quarter=2, clock=30, down=1, distance=5, ballOn=5, offScore=10, defScore=7,
               offTimeouts=2, clockRunning=False)
expect(f"Q2 0:30, 1st & goal at the 5, two timeouts: mostly pass ({r:.0%} runs, n={n})", r <= 0.4)
r, n = runRate(quarter=2, clock=90, down=1, distance=8, ballOn=8, offScore=10, defScore=7,
               offTimeouts=3, clockRunning=False)
expect(f"Q2 1:30, 1st & goal at the 8: no hurry, no clock cut ({r:.0%} runs, n={n})",
       r >= 0.68)
r, n = runRate(quarter=2, clock=15, down=1, distance=10, ballOn=82, offScore=10, defScore=7,
               offTimeouts=3, clockRunning=False)
expect(f"Q2 0:15 at its own 18: nothing in reach, the half is played out ({r:.0%} runs, n={n})",
       r >= 0.25)

print("\n-- 5. behind at the end, a run that does not score loses the game --")
def goRunShare(**kw):
    runs = goes = 0
    for i in range(TRIALS):
        random.seed(i); np.random.seed(i)
        s = Scenario().situation(**kw)
        pt = s.callPlay()
        if pt in (FG.PlayType.Run, FG.PlayType.Pass):
            goes += 1
            runs += pt is FG.PlayType.Run and not getattr(s.g.play, 'isScramble', False)
    return runs / max(goes, 1), goes
r, n = goRunShare(quarter=4, clock=11, down=4, distance=3, ballOn=8, offScore=23, defScore=30,
                  offTimeouts=0, clockRunning=False)
expect(f"down 7, 4th & 3 at the 8, 0:11, no timeouts (game 5525): never run ({r:.0%}, n={n})",
       n == TRIALS and r == 0)
r, n = goRunShare(quarter=4, clock=11, down=2, distance=10, ballOn=15, offScore=23, defScore=30,
                  offTimeouts=0, clockRunning=False)
expect(f"down 7, 2nd & 10 at the 15, 0:11, no timeouts: never run ({r:.0%}, n={n})", r == 0)
r, n = goRunShare(quarter=4, clock=11, down=4, distance=2, ballOn=2, offScore=20, defScore=24,
                  offTimeouts=0, clockRunning=False)
expect(f"down 4, 4th & goal at the 2, 0:11: converting is scoring, a run is allowed ({r:.0%}, n={n})",
       r > 0)
r, n = goRunShare(quarter=4, clock=90, down=4, distance=1, ballOn=60, offScore=17, defScore=20,
                  offTimeouts=1, clockRunning=False)
expect(f"down 3, 4th & 1 at its own 40, 1:30: the go play is called, not fixed ({r:.0%} runs)",
       0.2 <= r <= 0.7)
r, n = goRunShare(quarter=4, clock=180, down=4, distance=2, ballOn=25, offScore=14, defScore=19,
                  offTimeouts=2, clockRunning=False)
expect(f"down 5, 4th & 2 at the 25, 3:00: the go play is called, not fixed ({r:.0%} runs)",
       0.1 <= r <= 0.7)

print("\n-- 6. at the half with nothing in reach, no timeouts --")
def toRate(**kw):
    used = 0
    for i in range(TRIALS):
        random.seed(i); np.random.seed(i)
        s = Scenario().situation(**kw)
        s.callPlay()
        used += s.g.homeTimeoutsRemaining < kw['offTimeouts']
    return used / TRIALS
r = toRate(quarter=2, clock=26, down=1, distance=10, ballOn=94, offScore=0, defScore=3,
           offTimeouts=3, clockRunning=True)
expect(f"Q2 0:26 at its own 6, three timeouts (game 5518): no timeout ({r:.0%})", r == 0)
r = toRate(quarter=2, clock=30, down=1, distance=10, ballOn=40, offScore=7, defScore=7,
           offTimeouts=2, clockRunning=True)
expect(f"Q2 0:30 at the opponent's 40, two timeouts: still stops the clock ({r:.0%})", r >= 0.6)

print()
if fails:
    print(f"{len(fails)} FAILED"); sys.exit(1)
print("all passed")
