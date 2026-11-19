"""An end-of-game field goal that ties or takes the lead ends the game.

Reported 2026-11-19: teams kicking at the end of Q4 to tie or go ahead "still leave time for
the other team to run at least one play". A kickoff takes no time in this engine (an instant
touchback, clock stopped), so every second the kick leaves is a snap from the opponent's 20.
Three faults, all fixed together:

1. The drain aimed the kick's snap at 0:07 with a +-3s jitter, so a 4-6s kick ended at
   0:01-0:06. It now aims at `FG_DRAIN_SNAP_TARGET_SECS` (3) with no jitter.
2. The save-the-snap timeout fired on a running clock under 0:15 for a field goal too: a
   tied team kicking at 0:14 stopped the clock and gave back ~9s. The pre-snap clamp always
   gets a kick off with time on the clock, so a draining kick skips it.
3. It misjudged whether one more snap fits. From a stopped clock it kicked a play early
   (`_estimateAvailablePlays` already holds back the kick's snap, and `<= 1` was read as
   "last play"); on a running clock with a timeout it treated the next snap as free and ran
   the clock out (harness game 5972). `_snapFitsBeforeKick` prices that snap directly.

Run: .venv/bin/python test_late_fg_clock.py
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


def kickSituation(clock, deficit=0, offTO=2, running=True):
    s = Scenario()
    s.situation(quarter=4, clock=clock, offense='home', offScore=20, defScore=20 + deficit,
                down=4, distance=6, ballOn=16, offTimeouts=offTO, defTimeouts=3,
                clockRunning=running)
    s.g.play.playType = PlayType.FieldGoal
    return s.g


print("1. A tying or go-ahead kick drains to about 3s before the snap")
for clock in (30, 14):
    snaps = []
    for seed in range(40):
        random.seed(seed)
        g = kickSituation(clock)
        intent, _ = g._classifyTempoIntent()
        snaps.append(clock - g.calculatePreSnapTime())
    expect(f"0:{clock:02d} running -> setupFG, snaps at {min(snaps)}-{max(snaps)}s",
           intent == 'setupFG' and 1 <= min(snaps) and max(snaps) <= 5)

print("\n2. The save-the-snap timeout is not spent in front of a draining kick")
g = kickSituation(14, deficit=0, offTO=2)
g._maybeCallTimeoutToSaveSnap()
expect(f"tied, 0:14 running -> no timeout ({g.homeTimeoutsRemaining} left)", g.homeTimeoutsRemaining == 2)
g = kickSituation(14, deficit=2, offTO=2)
g._maybeCallTimeoutToSaveSnap()
expect(f"down 2, 0:14 running -> no timeout ({g.homeTimeoutsRemaining} left)", g.homeTimeoutsRemaining == 2)
g = kickSituation(3, deficit=2, offTO=2)
g._maybeCallTimeoutToSaveSnap()
expect(f"down 2, 0:03 running -> timeout, or the administration runs it out ({g.homeTimeoutsRemaining} left)",
       g.homeTimeoutsRemaining == 1)

print("\n2b. On a running clock, the next snap's own pre-snap is charged")
# Harness game 5972: tied at 0:15 with a timeout, the play count said 2, the drain run
# was snapped at 0:06 after administration and a no-huddle set, and ran the clock out.
def call(clock, offTO=1):
    s = Scenario()
    s.situation(quarter=4, clock=clock, offense='home', offScore=20, defScore=20,
                down=1, distance=10, ballOn=16, offTimeouts=offTO, defTimeouts=3,
                clockRunning=True)
    return s.callPlay()
expect("tied, 0:15 running, a timeout -> kicks (the kick drains the clock itself)",
       call(15) is PlayType.FieldGoal)
expect("tied, 0:35 running, a timeout -> one more snap first", call(35) is not PlayType.FieldGoal)

print("\n3. Whole games: a late kick with the clock running leaves the opponent no snap")
calls = []
_orig = FG.Game.playCaller
def _wrapped(self, *a, **k):
    pre = (self.gameClockSeconds, self.clockRunning)
    r = _orig(self, *a, **k)
    if (self.play.playType is PlayType.FieldGoal and self.currentQuarter == 4
            and pre[0] <= 60 and pre[1]):
        diff = (self.homeScore - self.awayScore) * (1 if self.offensiveTeam is self.homeTeam else -1)
        if -3 <= diff <= 0:
            calls.append((self, self.play))
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

for i in range(400):
    asyncio.run(_game(i))
FG.Game.playCaller = _orig

gave = 0
for g, play in calls:
    feed = list(reversed(g.gameFeed))
    idx = next((i for i, f in enumerate(feed) if f.get('play') is play), None)
    if idx is None:
        continue
    gave += any(f.get('play') is not None and f['play'].offense is not play.offense
                and f['play'].quarter == 4
                and f['play'].playType in (PlayType.Run, PlayType.Pass)
                for f in feed[idx + 1:])
expect(f"enough late kicks to measure ({len(calls)})", len(calls) >= 8)
# Old engine: ~30% of these handed the opponent a snap.
expect(f"opponent got a snap after {gave} of {len(calls)}", gave <= max(1, len(calls) // 20))

print()
if fails:
    print(f"FAILED ({len(fails)}): " + "; ".join(fails))
    raise SystemExit(1)
print("PASS — a kick that ties or takes the lead ends the game.")
