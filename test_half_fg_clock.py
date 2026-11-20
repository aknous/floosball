"""The last field goal of the first half leaves the opponent no time, at any score.

Reported 2026-11-20 from the season-15 Floos Bowl (prod game 6945): KCS, down 13, 2nd & 10
at the LAE 27 with the clock stopped at 0:14 and two timeouts, kicked on that snap and LAE
got the ball back at 0:09. The end-of-game kick fixes (test_late_fg_clock.py) applied only
to a kick that ties or takes the lead, and the end-of-half kick still read the play count's
`<= 1` as "last play". At the half the possession is free, so `_kickDrainsClock` drains any
kick to ~3s and `endOfHalfFG` runs one more snap when it and the kick fit.

Run: .venv/bin/python test_half_fg_clock.py
"""
import sys, os, random, asyncio
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import logging; logging.disable(logging.WARNING)
import numpy as np
import managers  # resolve circular import before floosball_game
from scenario import Scenario, PlayType, _makeTeam
from game_rules import GameRules
import floosball_game as FG

fails = []
def expect(label, cond):
    print(f"  [{'OK' if cond else 'FAIL'}] {label}")
    if not cond:
        fails.append(label)


def call(clock, offTO, running, down=2, offScore=3, defScore=16, ballOn=27, seed=0):
    random.seed(seed); np.random.seed(seed)
    s = Scenario()
    s.situation(quarter=2, clock=clock, offense='home', offScore=offScore, defScore=defScore,
                down=down, distance=10, ballOn=ballOn, offTimeouts=offTO, defTimeouts=3,
                clockRunning=running)
    return s, s.callPlay()


print("1. The reported spot: one more snap fits before the kick")
kicks = sum(call(14, 2, False, seed=i)[1] is PlayType.FieldGoal for i in range(40))
expect(f"down 13, 2nd & 10 at the 27, 0:14 stopped, two timeouts -> play on ({kicks}/40 kick)", kicks == 0)
kicks = sum(call(6, 2, False, seed=i)[1] is PlayType.FieldGoal for i in range(40))
expect(f"same at 0:06 stopped -> kick ({kicks}/40)", kicks == 40)

print("\n2. A first-half kick drains the clock at any score")
for offScore, defScore, label in ((16, 3, 'up 13'), (3, 16, 'down 13'), (10, 10, 'tied')):
    snaps = []
    for seed in range(30):
        random.seed(seed)
        s = Scenario()
        s.situation(quarter=2, clock=30, offense='home', offScore=offScore, defScore=defScore,
                    down=4, distance=6, ballOn=16, offTimeouts=2, defTimeouts=3, clockRunning=True)
        s.g.play.playType = PlayType.FieldGoal
        intent, _ = s.g._classifyTempoIntent()
        snaps.append(30 - s.g.calculatePreSnapTime())
    expect(f"{label}, 0:30 running -> {intent}, snaps at {min(snaps)}-{max(snaps)}s",
           intent == 'setupFG' and 1 <= min(snaps) and max(snaps) <= 5)

s = Scenario()
s.situation(quarter=2, clock=14, offense='home', offScore=16, defScore=3,
            down=4, distance=6, ballOn=16, offTimeouts=2, defTimeouts=3, clockRunning=True)
s.g.play.playType = PlayType.FieldGoal
s.g._maybeCallTimeoutToSaveSnap()
expect(f"up 13, 0:14 running -> no save-the-snap timeout ({s.g.homeTimeoutsRemaining} left)",
       s.g.homeTimeoutsRemaining == 2)

print("\n3. Not in Q4 for a leader, where a kick is not a tie or the lead")
s = Scenario()
s.situation(quarter=4, clock=30, offense='home', offScore=16, defScore=3,
            down=4, distance=6, ballOn=16, offTimeouts=2, defTimeouts=3, clockRunning=True)
s.g.play.playType = PlayType.FieldGoal
expect("up 13 at the end of the game -> the half rule is off", not s.g._kickDrainsClock()
       or s.g._isFgDrainMode(forKick=True))

print("\n4. Whole games: the last first-half kick leaves the opponent no snap")
calls = []
_orig = FG.Game.playCaller
def _wrapped(self, *a, **k):
    pre = (self.gameClockSeconds, self.clockRunning)
    r = _orig(self, *a, **k)
    if (self.play.playType is PlayType.FieldGoal and self.currentQuarter == 2
            and pre[0] <= 40):
        calls.append((self, self.play, pre[1]))
    return r
FG.Game.playCaller = _wrapped

async def _game(gid):
    random.seed(gid); np.random.seed(gid)
    h = _makeTeam('H', 'HOM', 100 + gid * 10); a = _makeTeam('A', 'AWY', 500 + gid * 10)
    g = FG.Game(h, a, gameRules=GameRules()); g.id = gid
    g._anomalyAttentionLoaded = True; g._anomalyEnabled = False
    g._anomalyAttention = {}; g._anomalyState = {}
    g._criticalityMultiplier = 1.0; g._criticalityActive = False; g._anomalyIntensity = 1.0
    await g.playGame()

N = int(os.environ.get('N', 300))
for i in range(N):
    asyncio.run(_game(i))
FG.Game.playCaller = _orig

gave = {True: 0, False: 0}; n = {True: 0, False: 0}
for g, play, running in calls:
    feed = list(reversed(g.gameFeed))
    idx = next((i for i, f in enumerate(feed) if f.get('play') is play), None)
    if idx is None:
        continue
    n[running] += 1
    gave[running] += any(f.get('play') is not None and f['play'].offense is not play.offense
                         and f['play'].quarter == 2
                         and f['play'].playType in (PlayType.Run, PlayType.Pass)
                         for f in feed[idx + 1:])
print(f"  running clock at the call: {gave[True]} of {n[True]} gave a snap; "
      f"stopped: {gave[False]} of {n[False]}")
expect(f"enough late first-half kicks to measure ({n[True] + n[False]})", n[True] + n[False] >= 15)
expect(f"running clock at the call -> the opponent never snaps ({gave[True]} of {n[True]})",
       gave[True] <= max(1, n[True] // 20))

print()
if fails:
    print(f"FAILED ({len(fails)}): " + "; ".join(fails))
    raise SystemExit(1)
print("PASS — the half's last kick leaves the opponent nothing.")
