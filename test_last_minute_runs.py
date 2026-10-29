"""The last minute of Q4, tied or trailing, is pass-first (2026-10-29, prod week of 10-29).

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

print()
if fails:
    print(f"{len(fails)} FAILED"); sys.exit(1)
print("all passed")
