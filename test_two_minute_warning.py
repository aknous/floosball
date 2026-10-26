"""The two-minute warning stops the clock AT 2:00, and it frees the timeouts it holds.

Two faults, found on prod season 12 week 1 (fixed 2026-10-26):

1. The pre-snap window (dead-ball administration and the huddle) was charged in full and
   the warning only checked after it, so a huddle that started at 2:09 ran the clock to
   1:25 before the warning fired. It fired at 1:23-2:00 in all 32 halves of the slate,
   19.5 seconds late on average and up to 37. Both sides were told to hold their
   timeouts for that free stop (`_twoMinuteWarningPending`), so the lost time came out of
   the trailing team's clock.
2. The "warning stopped the clock" flag was cleared before the huddle. A warning that
   fired DURING the huddle left it set through the following play, and both timeout
   checks skip while it is set, so neither team could stop the clock after that play.
   WAS down 6 with two timeouts at 1:21 and TAM down 9 with three at 1:19 each let a
   45-second huddle run.

Run: .venv/bin/python test_two_minute_warning.py   (exits non-zero on any failure)
"""
import sys, os, random, asyncio
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import logging; logging.disable(logging.WARNING)

import numpy as np
from scenario import Scenario, _makeTeam
from game_rules import GameRules
import floosball_game as FG

fails = []
def expect(d, c):
    print(f"  [{'OK' if c else 'FAIL'}] {d}")
    if not c: fails.append(d)


print("\n-- the huddle stops at 2:00 --")
s = Scenario().situation(quarter=4, clock=129, clockRunning=True, twoMinuteWarningShown=False)
g = s.game
g._inPreSnap = True
g.consumeGameTime(40)
g._inPreSnap = False
expect(f"a 40-second huddle from 2:09 stops at 2:00 (clock {g.formatTime(g.gameClockSeconds)})",
       g.gameClockSeconds == 120)
g.checkTwoMinuteWarning()
expect("...and the warning fires there", g.twoMinuteWarningShown and not g.clockRunning)
expect("...stamped 2:00", g.gameFeed and g.gameFeed[0].get('event', {}).get('timeRemaining') == '2:00')

s = Scenario().situation(quarter=4, clock=125, clockRunning=True, twoMinuteWarningShown=False)
g = s.game
g.consumeGameTime(10)
expect("a play in progress still runs through 2:00 (the warning follows the play)",
       g.gameClockSeconds == 115)

s = Scenario().situation(quarter=3, clock=129, clockRunning=True, twoMinuteWarningShown=False)
s.game._inPreSnap = True; s.game.consumeGameTime(40)
expect("no warning in Q3, so nothing to stop at", s.game.gameClockSeconds == 89)

s = Scenario().situation(quarter=4, clock=110, clockRunning=True, twoMinuteWarningShown=True)
s.game._inPreSnap = True; s.game.consumeGameTime(40)
expect("once the warning has been given the huddle runs normally", s.game.gameClockSeconds == 70)


print("\n-- over whole games --")

async def _game(gid):
    random.seed(gid); np.random.seed(gid % (2**31))
    h = _makeTeam('H', 'HOM', 100 + gid * 10); a = _makeTeam('A', 'AWY', 500 + gid * 10)
    g = FG.Game(h, a, gameRules=GameRules()); g.id = gid
    g._anomalyAttentionLoaded = True; g._anomalyEnabled = False
    g._anomalyAttention = {}; g._anomalyState = {}
    g._criticalityMultiplier = 1.0; g._criticalityActive = False; g._anomalyIntensity = 1.0
    stale = []
    real = g._checkDefensiveTimeout
    def watched():
        # The flag means "the warning stopped the clock and nothing has been snapped since".
        # It can never be true while the clock is running.
        if g.clockRunning and g._clockStoppedByWarning:
            stale.append((g.currentQuarter, g.gameClockSeconds))
        return real()
    g._checkDefensiveTimeout = watched
    await g.playGame()
    return g, stale

def secs(t):
    m, s_ = t.split(':'); return int(m) * 60 + int(s_)

warnings = late = staleSeen = 0
for i in range(30):
    g, stale = asyncio.run(_game(i))
    staleSeen += len(stale)
    feed = list(reversed(g.gameFeed))
    for j, item in enumerate(feed):
        ev = item.get('event')
        if not ev or ev.get('text') != 'Two-Minute Warning':
            continue
        warnings += 1
        # Either the huddle reached 2:00, or a play in progress carried the clock past it
        # and the warning came at the end of that play. That play is entered in the feed
        # AFTER the warning its own post-play check raised, so it is the next play.
        nxt = next((f['play'] for f in feed[j + 1:] if f.get('play') is not None), None)
        if ev['timeRemaining'] != '2:00' and ev['timeRemaining'] != getattr(nxt, 'timeRemaining', None):
            late += 1
expect(f"{warnings} warnings, none given late in a huddle ({late})", warnings >= 50 and late == 0)
expect(f"the warning flag never outlives the snap after it ({staleSeen} stale reads)", staleSeen == 0)

print()
if fails:
    print(f"FAIL — {len(fails)} problem(s):")
    for f in fails:
        print(f"  - {f}")
    sys.exit(1)
print("PASS — the clock stops at 2:00, and both sides can use their timeouts after it.")
