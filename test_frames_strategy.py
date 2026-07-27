"""Frames: 4th-down FG-vs-go reasons off the FRAME score, not the running total.

Owner-reported bug (2026-07-27): in a frames game a team was DOWN A TOUCHDOWN in the
current frame on the last play, but AHEAD on total points, and kicked a field goal —
losing the frame. Each frame is a mini-game you're trying to WIN; total points only
break a frames tie, so a FG that leaves you trailing the frame (when a TD would win it)
on the last play of the frame is the wrong call.

The fix: _fourthDownCaller rebases scoreDiff onto _frameScoreDiff() in frames, and the
"no subsequent possession" test (lateHopeless) counts a frame that's winding down. So a
team down a TD in the frame, with the frame about to close, goes for the TD.

Run: .venv/bin/python test_frames_strategy.py   (exits non-zero on any failure)
"""
import sys
sys.path.insert(0, '/Users/andrew/Projects/floosball')
import logging; logging.disable(logging.CRITICAL)
import managers  # resolve circular import
from scenario import Scenario, PlayType
from game_rules import GameRules

failures = []
def expect(desc, cond):
    print(f"  [{'OK' if cond else 'FAIL'}] {desc}")
    if not cond:
        failures.append(desc)


FRAME_LEN = 600   # 3600s / 6 frames


def _rules(fmt='frames', framesPerGame=6):
    gr = GameRules()
    gr.gameFormat = fmt
    gr.framesPerGame = framesPerGame
    return gr


def build(*, fmt='frames', frameMargin, totalMargin, secsIntoFrame,
          ballOn=28, offense='home'):
    """A frames game `secsIntoFrame` into the current frame, offense ahead/behind by
    `frameMargin` INSIDE the frame while ahead/behind by `totalMargin` on the RUNNING
    TOTAL. On 4th-and-goalish inside FG range so the FG-vs-go branch is live."""
    gr = _rules(fmt)
    s = Scenario(gameRules=gr)
    # Position the clock so `secsIntoFrame` of the 600s frame have elapsed. Frames span
    # quarters (1.5 frames per 900s quarter); for the first frame the game clock is just
    # the quarter clock counting down.
    clock = max(1, gr.quarterLengthSeconds - secsIntoFrame)
    s.situation(quarter=1, clock=int(clock), offense=offense,
                offScore=0, defScore=0, down=4, distance=8, ballOn=ballOn)
    g = s.g
    # Frame entry scores: chosen so the in-frame margin is `frameMargin` and the total
    # margin is `totalMargin` (offense-relative).
    entryLead = totalMargin - frameMargin   # points the offense led by ENTERING the frame
    if offense == 'home':
        g._frameStartHome, g._frameStartAway = max(0, entryLead), max(0, -entryLead)
        g.homeScore = g._frameStartHome + max(0, frameMargin)
        g.awayScore = g._frameStartAway + max(0, -frameMargin)
    else:
        g._frameStartAway, g._frameStartHome = max(0, entryLead), max(0, -entryLead)
        g.awayScore = g._frameStartAway + max(0, frameMargin)
        g.homeScore = g._frameStartHome + max(0, -frameMargin)
    g._framesWonHome = g._framesWonAway = 1   # frames level — total tiebreak in play
    g._frameIndex = 0
    return s, g


def goRate(*, trials=25, **kw):
    """Fraction of trials the offense GOES for it (Run/Pass) rather than kicking/punting."""
    go = 0
    for _ in range(trials):
        s, _g = build(**kw)
        pt = s.fourthDownPlay()
        if pt in (PlayType.Run, PlayType.Pass):
            go += 1
    return go / trials


print("1. THE BUG: down a TD in the frame, ahead on total, frame closing → go for the TD")
r = goRate(frameMargin=-7, totalMargin=+13, secsIntoFrame=FRAME_LEN - 12, ballOn=27)
expect(f"down 7 in-frame / up 13 total / ~12s of frame left → GOES for it (rate {r:.2f})",
       r == 1.0)
r = goRate(frameMargin=-7, totalMargin=+13, secsIntoFrame=FRAME_LEN - 40, ballOn=30)
expect(f"down 7 in-frame / up 13 total / ~40s of frame left → GOES for it (rate {r:.2f})",
       r == 1.0)

print("2. Down a TD in the frame BEHIND on total too → same call (frame is what matters)")
r = goRate(frameMargin=-7, totalMargin=-7, secsIntoFrame=FRAME_LEN - 12, ballOn=27)
expect(f"down 7 in-frame / down 7 total / frame closing → GOES for it (rate {r:.2f})",
       r == 1.0)

print("3. WINNING the frame late → a makeable FG is fine (still scoring; helps the tiebreak)")
# Up in the frame, the FG helps (extends the frame lead AND the point tiebreak), so kicking
# is acceptable — the offense should NOT be forced to go for it here.
r = goRate(frameMargin=+3, totalMargin=+3, secsIntoFrame=FRAME_LEN - 12, ballOn=27, trials=25)
expect(f"up 3 in-frame, frame closing, makeable FG → does NOT always go (rate {r:.2f})",
       r < 1.0)

print("4. Early in the frame, down a TD → a FG to cut the deficit is still allowed")
# Plenty of frame left to get the ball back and score again, so a bail-out FG is a
# legitimate option — the fix must NOT force a go-for-it this early.
r = goRate(frameMargin=-7, totalMargin=+13, secsIntoFrame=60, ballOn=27, trials=25)
expect(f"down 7 in-frame, ~540s of frame left → does NOT always go (rate {r:.2f})",
       r < 1.0)

print("5. STANDARD format is untouched: ahead on total late → not forced to go for it")
# Same board read as a standard game (no frames): up 13, 4th & short in FG range late —
# the team kicks / manages normally; the frame override is a no-op off frames.
def stdGoRate(trials=25):
    go = 0
    for _ in range(trials):
        gr = _rules(fmt='standard')
        s = Scenario(gameRules=gr)
        s.situation(quarter=4, clock=90, offense='home',
                    offScore=27, defScore=14, down=4, distance=8, ballOn=27)
        pt = s.fourthDownPlay()
        if pt in (PlayType.Run, PlayType.Pass):
            go += 1
    return go / trials
r = stdGoRate()
expect(f"standard, up 13, 4th&8 in FG range, 90s left → does NOT always go (rate {r:.2f})",
       r < 1.0)


print()
if failures:
    print(f">>> {len(failures)} FAILURE(S)")
    for f in failures:
        print("   -", f)
    sys.exit(1)
print("PASS — frames 4th-down play-calling plays to WIN THE FRAME.")
