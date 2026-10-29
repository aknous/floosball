"""Two fourth-down punt rules that ignored the clock (2026-10-29, prod week of 10-29).

1. OVERTIME, TIED, OUT OF FIELD-GOAL RANGE: `_otPlayCaller` went for it from anywhere
   (it punted only on 16+ to go inside its own 15). MIN went on 4th & 1 at its own 29
   with 7:55 left (game 5466), COL on 4th & 6 at its own 38 with 7:45 left (game 5469);
   both failed. NFL 2016-24, tied in OT in its own territory with 5:00+ left: 0 of 24 go
   on 4th & 6-10, 17-25% on 4th & 1-2. Now the regulation go table decides.
2. TRAILING IN THE LAST 5:00, INSIDE ITS OWN 35: the deep-territory gate punted every
   such 4th down unless under 2:30 was left. TAM, down 5 with no timeouts, punted on 4th
   & 2 at its own 28 with 2:31 left (game 5472) and MIA knelt it out. NFL: go 83% on 4th
   & 1, ~50% on 4th & 2-5, 86% with no timeouts. Now a punt the leader can kneel away
   always goes, 4th & 1 goes, 4th & 2-3 is the coach's call, longer still punts.

Run: .venv/bin/python test_late_fourth_down_punts.py   (exits non-zero on any failure)
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

TRIALS = 100


def goRate(**kw):
    goes = 0
    for i in range(TRIALS):
        random.seed(i); np.random.seed(i)
        s = Scenario().situation(**kw)
        pt = s.callPlay()
        goes += pt not in (FG.PlayType.Punt, FG.PlayType.FieldGoal)
    return goes / TRIALS


print("\n-- 1. overtime, tied, out of field-goal range --")
r = goRate(quarter=5, clock=465, down=4, distance=6, ballOn=62)
expect(f"4th & 6 at its own 38, 7:45 left (game 5469): punt ({r:.0%} go)", r <= 0.05)
r = goRate(quarter=5, clock=475, down=4, distance=1, ballOn=71)
expect(f"4th & 1 at its own 29, 7:55 left (game 5466): mostly punt ({r:.0%} go)", 0.05 <= r <= 0.5)
r = goRate(quarter=5, clock=300, down=4, distance=8, ballOn=62, offScore=0, defScore=3,
           otFirstPossComplete=True)
expect(f"down 3 on the answering possession, 4th & 8 at its own 38: always go ({r:.0%})", r == 1.0)

print("\n-- 2. trailing in the last 5:00, inside its own 35 --")
r = goRate(quarter=4, clock=151, down=4, distance=2, ballOn=72, offScore=14, defScore=19,
           offTimeouts=0)
expect(f"down 5, 4th & 2 at its own 28, 2:31, no timeouts (game 5472): go ({r:.0%})", r == 1.0)
r = goRate(quarter=4, clock=155, down=4, distance=12, ballOn=72, offScore=14, defScore=19,
           offTimeouts=0)
expect(f"same at 4th & 12, 2:35: a punt never comes back, go ({r:.0%})", r == 1.0)
r = goRate(quarter=4, clock=270, down=4, distance=1, ballOn=72, offScore=14, defScore=19)
expect(f"down 5, 4th & 1 at its own 28, 4:30, three timeouts: go ({r:.0%})", r >= 0.8)
r = goRate(quarter=4, clock=270, down=4, distance=2, ballOn=72, offScore=14, defScore=19)
expect(f"down 5, 4th & 2 at its own 28, 4:30, three timeouts: the coach's call ({r:.0%})",
       0.2 <= r <= 0.9)
r = goRate(quarter=4, clock=270, down=4, distance=8, ballOn=72, offScore=14, defScore=19)
expect(f"down 5, 4th & 8 at its own 28, 4:30, three timeouts: punt ({r:.0%} go)", r == 0)
r = goRate(quarter=4, clock=240, down=4, distance=2, ballOn=72, offScore=14, defScore=14)
expect(f"tied, 4th & 2 at its own 28, 4:00: punt ({r:.0%} go)", r == 0)
r = goRate(quarter=3, clock=240, down=4, distance=1, ballOn=72, offScore=14, defScore=19)
expect(f"down 5 in Q3, 4th & 1 at its own 28: the normal model, mostly punt ({r:.0%} go)",
       r <= 0.5)

print()
if fails:
    print(f"{len(fails)} FAILED"); sys.exit(1)
print("all passed")
