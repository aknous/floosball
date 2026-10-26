"""Four small clock and play-calling faults from the prod season 12 week 1 review (2026-10-26).

1. "& Goal" was printed whenever the ball was inside the 10, even when the line to gain
   was short of the goal line (a 4th & 1 at the 8 read as 4th & Goal).
2. A timeout called after a kneel was undone when the clock was re-derived from the
   kneel, so the defense called a second one in the same dead ball (Bees, twice at 0:25).
3. A Hail Mary could become the random RB screen (DET's last snap of the half from the
   KCS 42 went as a 1-yard screen).
4. Inside the last minute an offense draining to kick last (`_isFgDrainMode`) still
   stopped the clock with timeouts (NOR down 1 at the MIA 20, timeouts at 0:54 and 0:50).

Run: .venv/bin/python test_clock_cleanups.py   (exits non-zero on any failure)
"""
import sys, os, random, asyncio
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import logging; logging.disable(logging.WARNING)

import numpy as np
import constants
from scenario import Scenario, _makeTeam
from game_rules import GameRules
import floosball_game as FG

fails = []
def expect(d, c):
    print(f"  [{'OK' if c else 'FAIL'}] {d}")
    if not c: fails.append(d)


print("\n-- 1. goal to go means the marker is the goal line --")
s = Scenario().situation(quarter=2, clock=300, down=4, distance=1, ballOn=8)
expect(f"4th & 1 at the 8 is not goal to go ({s.game.play.yardsTo1st!r})", s.game.play.yardsTo1st == 1)
s = Scenario().situation(quarter=2, clock=300, down=1, distance=8, ballOn=8)
expect(f"1st & goal at the 8 is ({s.game.play.yardsTo1st!r})", s.game.play.yardsTo1st == 'Goal')
s = Scenario().situation(quarter=2, clock=300, down=2, distance=10, ballOn=15)
expect(f"2nd & 10 at the 15 is a number ({s.game.play.yardsTo1st!r})", s.game.play.yardsTo1st == 10)


print("\n-- 3. a Hail Mary is never a screen --")
_saved = constants.RB_SCREEN_CHANCE
constants.RB_SCREEN_CHANCE = 100      # every clean dropback would be a screen
screens = 0
for i in range(40):
    random.seed(i); np.random.seed(i)
    s = Scenario().situation(quarter=2, clock=3, down=1, distance=10, ballOn=42)
    s.game.play.passPlay('Play9')
    screens += (s.game.play.insights.get('pass') or {}).get('checkdown') == 'screen'
constants.RB_SCREEN_CHANCE = _saved
expect(f"the screen never replaces the heave ({screens} of 40)", screens == 0)


print("\n-- 4. draining to kick last does not stop the clock --")
def timeouts(offScore, defScore, ballOn, trials=60):
    n = 0
    for i in range(trials):
        random.seed(i); np.random.seed(i)
        s = Scenario().situation(quarter=4, clock=54, offScore=offScore, defScore=defScore,
                                 down=1, distance=10, ballOn=ballOn, clockRunning=True)
        n += s.clockDecision() == 'timeout'
    return n
reported = timeouts(31, 32, 20)
expect(f"down 1 at the 20 with 0:54: no clock-stopping timeout ({reported} of 60)", reported == 0)
needTd = timeouts(27, 32, 20)
expect(f"down 5 at the 20 (a kick does not do it) still stops the clock ({needTd} of 60)", needTd > 30)


print("\n-- 2. one timeout per dead ball, over whole games --")
async def _game(gid):
    random.seed(gid); np.random.seed(gid % (2**31))
    h = _makeTeam('H', 'HOM', 100 + gid * 10); a = _makeTeam('A', 'AWY', 500 + gid * 10)
    g = FG.Game(h, a, gameRules=GameRules()); g.id = gid
    g._anomalyAttentionLoaded = True; g._anomalyEnabled = False
    g._anomalyAttention = {}; g._anomalyState = {}
    g._criticalityMultiplier = 1.0; g._criticalityActive = False; g._anomalyIntensity = 1.0
    await g.playGame()
    return g

doubles = 0; kneels = 0
for i in range(60):
    g = asyncio.run(_game(i))
    feed = list(reversed(g.gameFeed))
    last = None
    for f in feed:
        if f.get('play') is not None:
            kneels += f['play'].playType is FG.PlayType.Kneel
            last = 'play'
        elif 'calls timeout' in (f.get('event') or {}).get('text', ''):
            doubles += last == 'timeout'
            last = 'timeout'
expect(f"no two timeouts without a snap between them ({doubles} over 60 games, {kneels} kneels)",
       doubles == 0 and kneels > 0)

print()
if fails:
    print(f"FAIL — {len(fails)} problem(s):")
    for f in fails:
        print(f"  - {f}")
    sys.exit(1)
print("PASS")
