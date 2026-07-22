"""Frames: the team leading a frame plays on, just without urgency.

Owner direction (2026-07-22, revising an earlier call to kneel the frame out):
teams should STILL TRY TO SCORE in a frame they lead — points decide the match
whenever the frames finish level, so kneeling throws away the tiebreak — but the
team ahead in the frame should not be in hurry-up or fast tempo.

So the leader:
  * never kneels the frame out (that was the earlier direction, now reverted), and
  * is never put into hurry-up by the frame winding down,
while the team BEHIND in the frame still gets the two-minute-drill treatment.

Run: .venv/bin/python test_frames_kneel.py
"""
import sys, types
sys.path.insert(0, '/Users/andrew/Projects/floosball')
_stub = types.ModuleType('floosball_game'); _stub.Game = type('G', (), {})
sys.modules['floosball_game'] = _stub
import managers.timingManager  # noqa: F401
del sys.modules['floosball_game']
from scenario import Scenario
from game_rules import GameRules

failures = []
def expect(desc, cond):
    print(f"  [{'OK' if cond else 'FAIL'}] {desc}")
    if not cond:
        failures.append(desc)


def _rules(framesPerGame=6):
    gr = GameRules()
    gr.gameFormat = 'frames'
    gr.framesPerGame = framesPerGame
    return gr


def build(*, frameMargin, secsIntoFrame, down=1, ballOn=40, offense='home',
          framesPerGame=6, oppTimeouts=0):
    """A frames game positioned `secsIntoFrame` into the current frame, with the
    offense ahead/behind by `frameMargin` INSIDE that frame."""
    gr = _rules(framesPerGame)
    s = Scenario(gameRules=gr)
    clock = gr.quarterLengthSeconds - (secsIntoFrame % gr.quarterLengthSeconds)
    s.situation(quarter=1, clock=int(clock), offense=offense,
                offScore=20, defScore=20, down=down, distance=10, ballOn=ballOn)
    g = s.g
    g._frameStartHome = g._frameStartAway = 20
    g.homeScore, g.awayScore = 20, 20
    if offense == 'home':
        g.homeScore += max(0, frameMargin); g.awayScore += max(0, -frameMargin)
    else:
        g.awayScore += max(0, frameMargin); g.homeScore += max(0, -frameMargin)
    g._framesWonHome = g._framesWonAway = 0
    if offense == 'home':
        g.awayTimeoutsRemaining = oppTimeouts
    else:
        g.homeTimeoutsRemaining = oppTimeouts
    return s, g


def kneelRate(*, trials=20, **kw):
    hits = 0
    for _ in range(trials):
        s, _g = build(**kw)
        if s.clockDecision() == 'kneel':
            hits += 1
    return hits / trials


FRAME_LEN = 600   # 3600s / 6 frames

print("1. The frame leader never kneels the frame out")
for secs, label in ((FRAME_LEN - 40, '~40s left'), (FRAME_LEN - 12, '~12s left'),
                    (FRAME_LEN - 5, '~5s left')):
    r = kneelRate(frameMargin=4, secsIntoFrame=secs)
    expect(f"up 4 in the frame, {label} → does NOT kneel (rate {r:.2f})", r == 0.0)
r = kneelRate(frameMargin=20, secsIntoFrame=FRAME_LEN - 30)
expect(f"up 20 in the frame → still does NOT kneel (rate {r:.2f})", r == 0.0)

print("2. The frame leader is not put into hurry-up by the frame ending")
for secs, label in ((FRAME_LEN - 30, '~30s left'), (FRAME_LEN - 90, '~90s left')):
    _s, g = build(frameMargin=4, secsIntoFrame=secs)
    expect(f"up 4 in the frame, {label} → not hurry-up", g._isHurryUp() is False)

print("3. The team BEHIND in the frame still gets the two-minute drill")
_s, g = build(frameMargin=-4, secsIntoFrame=FRAME_LEN - 30)
expect("down 4 in the frame, ~30s left → hurry-up", g._isHurryUp() is True)
_s, g = build(frameMargin=0, secsIntoFrame=FRAME_LEN - 30)
expect("frame TIED, ~30s left → hurry-up (a tie is still worth winning)",
       g._isHurryUp() is True)

print("4. Plenty of frame left → nobody is hurrying")
_s, g = build(frameMargin=-4, secsIntoFrame=60)
expect("down 4 but ~540s of frame left → not hurry-up", g._isHurryUp() is False)

print("5. Away offense reads the same")
_s, g = build(frameMargin=4, secsIntoFrame=FRAME_LEN - 30, offense='away')
expect("away leading the frame → not hurry-up", g._isHurryUp() is False)
_s, g = build(frameMargin=-4, secsIntoFrame=FRAME_LEN - 30, offense='away')
expect("away trailing the frame → hurry-up", g._isHurryUp() is True)

print()
if failures:
    print(f">>> {len(failures)} FAILURE(S)")
    for f in failures:
        print("   -", f)
    sys.exit(1)
print("PASS — the frame leader plays on without urgency; the trailer still pushes.")
