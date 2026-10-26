"""Timeouts and onside kicks follow the clock, not a flat roll (2026-10-26).

From the prod season 12 week 1 review, each checked against NFL 2019-23 play-by-play:

1. OFFENSIVE TIMEOUTS were rolled on every running-clock snap inside 2:00 (90%+ near FG
   range), so teams burned all three in seconds with plenty of clock (CLE at 1:26, 1:22
   and 1:18 from the PHI 23). NFL: 0-16% above 1:00, ~60% under 0:40. Now a timeout is
   spent when the clock binds: the drive's snaps no longer fit, or the timeouts held
   would otherwise go unused (`_offensiveTimeoutNeeded`).
2. END-OF-HALF DEFENSIVE TIMEOUTS fired on any down, handing the time to a drive that
   was moving. NFL: ~5% on 1st/2nd down, 17-26% on 3rd. Now only when a stop is likely.
3. ONSIDE KICKS were 75% for any deficit inside 4:00, timeouts ignored. Now the NFL rate
   by deficit, clock and timeouts (`ONSIDE_RATE_TABLE`).

Run: .venv/bin/python test_timeout_onside_rules.py   (exits non-zero on any failure)
"""
import sys, os, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import logging; logging.disable(logging.WARNING)

import numpy as np
from scenario import Scenario

fails = []
def expect(d, c):
    print(f"  [{'OK' if c else 'FAIL'}] {d}")
    if not c: fails.append(d)

TRIALS = 80


def offenseTimeouts(**kw):
    n = 0
    for i in range(TRIALS):
        random.seed(i); np.random.seed(i)
        s = Scenario().situation(clockRunning=True, **kw)
        n += s.clockDecision() == 'timeout'
    return n / TRIALS


print("\n-- 1. offensive timeouts wait until the clock binds --")
r = offenseTimeouts(quarter=2, clock=86, offScore=10, defScore=7, down=1, distance=10, ballOn=23)
expect(f"Q2 1:26 at the opponent's 23, three timeouts: hold them ({r:.0%})", r <= 0.10)
r = offenseTimeouts(quarter=2, clock=30, offScore=10, defScore=7, down=1, distance=10, ballOn=23)
expect(f"Q2 0:30 at the same spot: use them, or lose them at the half ({r:.0%})", r >= 0.5)
r = offenseTimeouts(quarter=4, clock=85, offScore=17, defScore=20, down=1, distance=10, ballOn=40)
expect(f"Q4 1:25 down 3 at the opponent's 40, three timeouts: no rush ({r:.0%})", r <= 0.10)
r = offenseTimeouts(quarter=4, clock=70, offScore=17, defScore=22, down=1, distance=10, ballOn=75)
expect(f"Q4 1:10 down 5 at its own 25 needs 75 yards: stop the clock ({r:.0%})", r >= 0.5)


def defenseTimeouts(**kw):
    n = 0
    for i in range(TRIALS):
        random.seed(i); np.random.seed(i)
        s = Scenario().situation(clockRunning=True, quarter=2, **kw)
        s.game._checkDefensiveTimeout()
        n += s.game.awayTimeoutsRemaining < 3
    return n / TRIALS


print("\n-- 2. before the half, the defense stops the clock only for a likely stop --")
r = defenseTimeouts(clock=50, down=1, distance=10, ballOn=45)
expect(f"0:50, offense 1st & 10 at midfield: let it run ({r:.0%})", r == 0)
r = defenseTimeouts(clock=50, down=2, distance=4, ballOn=30)
expect(f"0:50, 2nd & 4 in range: let it run ({r:.0%})", r == 0)
r = defenseTimeouts(clock=50, down=4, distance=6, ballOn=65)
expect(f"0:50, 4th & 6 deep in its own end: get the ball back ({r:.0%})", r >= 0.4)
r = defenseTimeouts(clock=50, down=3, distance=9, ballOn=70)
expect(f"0:50, 3rd & 9 at its own 30: likely to stall ({r:.0%})", r >= 0.4)


def onsideRate(deficit, secs, timeouts, trials=200):
    n = 0
    for i in range(trials):
        random.seed(i)
        # The kicking team is the defense when _shouldOnsideKick runs (it just scored).
        s = Scenario().situation(quarter=4, clock=secs, offScore=20 + deficit, defScore=20,
                                 defTimeouts=timeouts)
        n += s.game._shouldOnsideKick()
    return n / trials


print("\n-- 3. onside kicks by deficit, clock and timeouts --")
r = onsideRate(6, 210, 3)
expect(f"down 6, 3:30 left, three timeouts: kick deep ({r:.0%})", r <= 0.05)
r = onsideRate(6, 150, 3)
expect(f"down 6, 2:30, three timeouts: kick deep ({r:.0%})", r <= 0.10)
r = onsideRate(6, 150, 0)
expect(f"down 6, 2:30, no timeouts: onside ({r:.0%})", r >= 0.9)
r = onsideRate(6, 90, 2)
expect(f"down 6, 1:30: onside ({r:.0%})", r >= 0.8)
r = onsideRate(12, 210, 3)
expect(f"down 12, 3:30: onside ({r:.0%})", r >= 0.75)
r = onsideRate(12, 600, 3)
expect(f"down 12, 10:00: kick deep ({r:.0%})", r <= 0.05)

print()
if fails:
    print(f"FAIL — {len(fails)} problem(s):")
    for f in fails:
        print(f"  - {f}")
    sys.exit(1)
print("PASS")
