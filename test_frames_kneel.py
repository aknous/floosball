"""Frames: a team leading a frame kneels the rest of it out.

Owner rule (2026-07-22): if a team is leading a frame and the frame is ending,
there's no point running more plays — kneel to drain the clock and win the frame.
It must also respect a drive clock if one is active.

Why draining is strictly right here: a frame is its own mini-game and whoever
outscores the other inside it takes it (+1). A blowout frame is worth exactly the
same as a squeaker (`FramesFormat.awardFrames`), so once ahead in the frame more
plays can only RISK it. Unlike the game-end kneel this doesn't end the match —
play resumes in the next frame — so it is not gated on Q4.

Drives the REAL playCaller through `Scenario`.
Run: .venv/bin/python test_frames_kneel.py
"""
import sys, types
sys.path.insert(0, '/Users/andrew/Projects/floosball')
_stub = types.ModuleType('floosball_game'); _stub.Game = type('G', (), {})
sys.modules['floosball_game'] = _stub
import managers.timingManager  # noqa: F401
del sys.modules['floosball_game']
from scenario import Scenario, PlayType
from game_rules import GameRules

failures = []
def expect(desc, cond):
    print(f"  [{'OK' if cond else 'FAIL'}] {desc}")
    if not cond:
        failures.append(desc)


def _rules(framesPerGame=6, driveClock=False, driveUnit='seconds', driveRemaining=0):
    gr = GameRules()
    gr.gameFormat = 'frames'
    gr.framesPerGame = framesPerGame
    if driveClock:
        gr.driveClockEnabled = True
        gr.driveClockUnit = driveUnit
    return gr


def kneelRate(*, frameMargin, secsIntoFrame, down=1, ballOn=40, trials=20,
              offense='home', driveClock=False, driveUnit='seconds',
              driveRemaining=0, framesPerGame=6, oppTimeouts=0):
    """Fraction of trials the REAL play-caller returns a 'kneel' clock decision.

    `secsIntoFrame` positions the game clock so the current frame has
    (frameLength - secsIntoFrame) left. The frame is set up level at 20-20 with
    `frameMargin` scored inside it by the offense."""
    gr = _rules(framesPerGame, driveClock, driveUnit)
    hits = 0
    for _ in range(trials):
        s = Scenario(gameRules=gr)
        clock = gr.quarterLengthSeconds - (secsIntoFrame % gr.quarterLengthSeconds)
        s.situation(quarter=1, clock=int(clock), offense=offense,
                    offScore=20, defScore=20,
                    down=down, distance=10, ballOn=ballOn)
        g = s.g
        # Frame opened level at 20-20; the offense has since scored `frameMargin`
        # inside THIS frame (negative = the defense has).
        g._frameStartHome = g._frameStartAway = 20
        g.homeScore, g.awayScore = 20, 20
        if offense == 'home':
            g.homeScore += max(0, frameMargin); g.awayScore += max(0, -frameMargin)
        else:
            g.awayScore += max(0, frameMargin); g.homeScore += max(0, -frameMargin)
        g._framesWonHome = g._framesWonAway = 0
        # Opponent timeouts gate how much a kneel actually drains: a timed-out kneel
        # burns only the ~4s snap, so with timeouts in hand the frame CAN'T be run out
        # and kneeling would just hand the ball back. Default 0 = they're spent.
        if offense == 'home':
            g.awayTimeoutsRemaining = oppTimeouts
        else:
            g.homeTimeoutsRemaining = oppTimeouts
        if driveClock:
            g.driveClockRemaining = driveRemaining
        if s.clockDecision() == 'kneel':
            hits += 1
    return hits / trials


FRAME_LEN = 600   # 3600s / 6 frames

print("1. Leading the frame with the frame ending → kneel it out")
r = kneelRate(frameMargin=4, secsIntoFrame=FRAME_LEN - 40)
expect(f"up 4 in the frame, ~40s left, opp out of timeouts → kneels (rate {r:.2f})",
       r == 1.0)
r = kneelRate(frameMargin=1, secsIntoFrame=FRAME_LEN - 30)
expect(f"up 1 in the frame, ~30s left → kneels (rate {r:.2f})", r == 1.0)

print("1b. But only when the frame can ACTUALLY be run out")
# With timeouts in hand the opponent stops the clock, so 3 kneels drain only ~12s of
# a 40s frame — kneeling would hand the ball back instead of banking the frame.
r = kneelRate(frameMargin=4, secsIntoFrame=FRAME_LEN - 40, oppTimeouts=3)
expect(f"opp holds 3 timeouts, 40s of frame left → does NOT kneel (rate {r:.2f})",
       r == 0.0)
# Same timeouts, but little enough frame left that the snap time alone covers it.
r = kneelRate(frameMargin=4, secsIntoFrame=FRAME_LEN - 12, oppTimeouts=3)
expect(f"opp holds 3 timeouts but only 12s left → kneels anyway (rate {r:.2f})",
       r == 1.0)
# A margin outside the comeback window means their timeouts are irrelevant.
r = kneelRate(frameMargin=20, secsIntoFrame=FRAME_LEN - 40, oppTimeouts=3)
expect(f"up 20 in the frame → timeouts don't matter, kneels (rate {r:.2f})", r == 1.0)

print("2. Not gated on Q4 — this fires anywhere in the match")
expect("it fired above in Q1, which the game-end kneel never would", True)

print("3. Never kneel a frame you aren't winning")
r = kneelRate(frameMargin=0, secsIntoFrame=FRAME_LEN - 30)
expect(f"frame TIED, ~30s left → never kneels (rate {r:.2f})", r == 0.0)
r = kneelRate(frameMargin=-3, secsIntoFrame=FRAME_LEN - 30)
expect(f"DOWN 3 in the frame → never kneels (rate {r:.2f})", r == 0.0)

print("4. Plenty of frame left → play on")
r = kneelRate(frameMargin=4, secsIntoFrame=60)
expect(f"up 4 but ~540s of frame left → never kneels (rate {r:.2f})", r == 0.0)
r = kneelRate(frameMargin=4, secsIntoFrame=FRAME_LEN - 300)
expect(f"up 4 with 300s left → never kneels (rate {r:.2f})", r == 0.0)

print("5. Field-position guard — never kneel into a safety")
# ballOn is yards to the OPPONENT's end zone, so backed up on our own 1 is 99.
r = kneelRate(frameMargin=4, secsIntoFrame=FRAME_LEN - 40, ballOn=99)
expect(f"on own 1, up 4, frame ending → never kneels (rate {r:.2f})", r == 0.0)
r = kneelRate(frameMargin=4, secsIntoFrame=FRAME_LEN - 40, ballOn=90)
expect(f"on own 10 (safe), up 4 → kneels (rate {r:.2f})", r == 1.0)

print("6. Drive clock must outlast the frame")
r = kneelRate(frameMargin=4, secsIntoFrame=FRAME_LEN - 40,
              driveClock=True, driveUnit='seconds', driveRemaining=200)
expect(f"drive clock 200s vs ~40s of frame → still kneels (rate {r:.2f})", r == 1.0)
r = kneelRate(frameMargin=4, secsIntoFrame=FRAME_LEN - 40,
              driveClock=True, driveUnit='seconds', driveRemaining=10)
expect(f"drive clock only 10s vs ~40s of frame → does NOT kneel "
       f"(would turn it over on downs first) (rate {r:.2f})", r == 0.0)

print("7. Away offense works the same")
r = kneelRate(frameMargin=4, secsIntoFrame=FRAME_LEN - 40, offense='away')
expect(f"away up 4 in the frame, frame ending → kneels (rate {r:.2f})", r == 1.0)

print()
if failures:
    print(f">>> {len(failures)} FAILURE(S)")
    for f in failures:
        print("   -", f)
    sys.exit(1)
print("PASS — a leading team drains out the frame, and only when it's safe to.")
