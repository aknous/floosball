"""Game pressure is format-aware (innings).

Bug: calculateGamePressure read the raw currentQuarter/gameClockSeconds, but innings
leaves those INERT (no clock drain → quarter stuck at 1), so every play — even a tied
final inning — read as Q1 and got the earlyGameScale 0.3 dampening → "low" pressure.

Fix: GameFormat.pressureQuarterClock maps a format's period counters onto an effective
(quarter, secs). InningsFormat maps innings-remaining → quarter (final inning → Q4, extra
innings → Q5/OT) so pressure ramps like a real 4th-quarter push. Standard is the identity.

Run: .venv/bin/python test_innings_pressure.py
"""
import sys
sys.path.insert(0, '/Users/andrew/Projects/floosball')
import logging; logging.disable(logging.CRITICAL)
from types import SimpleNamespace
from game_formats import GameFormat, InningsFormat

failures = []
def expect(desc, cond):
    print(f"  [{'OK' if cond else 'FAIL'}] {desc}")
    if not cond:
        failures.append(desc)


def game(N=3, T=3, inning=1, half='top', tries=0, q=1, secs=900):
    return SimpleNamespace(
        gameRules=SimpleNamespace(inningsPerGame=N, triesPerInning=T),
        _inningsNumber=inning, _inningsHalf=half, _inningsTries=tries,
        currentQuarter=q, gameClockSeconds=secs)


inn = InningsFormat()

print("1. Standard format is the identity (unchanged pressure)")
q, s = GameFormat().pressureQuarterClock(game(q=4, secs=45))
expect("base returns the real (quarter, secs)", (q, s) == (4, 45))

print("\n2. Innings maps innings-remaining onto the quarter")
expect("inning 1 of 3 -> effQ 2", inn.pressureQuarterClock(game(inning=1))[0] == 2)
expect("inning 2 of 3 -> effQ 3", inn.pressureQuarterClock(game(inning=2))[0] == 3)
expect("final inning (3 of 3) -> effQ 4", inn.pressureQuarterClock(game(inning=3))[0] == 4)
expect("extra inning (4) -> effQ 5 (OT)", inn.pressureQuarterClock(game(inning=4))[0] == 5)

print("\n3. Deeper into the at-bat drains the synthetic clock (more pressure)")
topSecs = inn.pressureQuarterClock(game(inning=3, half='top', tries=0))[1]
endSecs = inn.pressureQuarterClock(game(inning=3, half='bottom', tries=2))[1]
print(f"     final inning: top/0-outs secs={topSecs}  bottom/last-try secs={endSecs}")
expect("clock drains as the at-bat progresses", endSecs < topSecs)

print("\n4. The reported case: tied 3rd inning of 3 no longer reads as Q1")
effQ, _ = inn.pressureQuarterClock(game(inning=3))
expect("tied final inning maps to Q4, not Q1 (full score-pressure, no early dampening)",
       effQ == 4)

print("\n5. Longer games only ramp over their final innings")
# N=9: innings 1-6 stay Q1, then 7->Q2, 8->Q3, 9->Q4 (like a 4th-quarter push)
expect("9-inning: inning 4 -> Q1", inn.pressureQuarterClock(game(N=9, inning=4))[0] == 1)
expect("9-inning: inning 7 -> Q2", inn.pressureQuarterClock(game(N=9, inning=7))[0] == 2)
expect("9-inning: inning 9 -> Q4", inn.pressureQuarterClock(game(N=9, inning=9))[0] == 4)

print("\n" + ("ALL PASS" if not failures else f"{len(failures)} FAILED: {failures}"))
sys.exit(1 if failures else 0)
