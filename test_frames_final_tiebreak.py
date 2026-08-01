"""Frames: the FINAL frame's points tiebreak drives end-game 4th-down calls.

Owner-reported bug (2026-07-28, game 5324): late in the 6th (final) frame a team was
WINNING the current frame — but winning it only LEVELLED the frames won, and they were
DOWN 1 on total points. Frames level -> the match is decided by TOTAL POINTS, so they
were actually LOSING. They got the ball at midfield with under a minute and PUNTED (the
play-caller read the frame lead as "ahead"), losing the game. They needed to treat it as
TRAILING and go for it to get at least a FG before the frame closed.

The fix: _frameDecisionDiff() — in the FINAL frame, if the frame's current lean leaves
the frames WON level, the decision margin becomes the TOTAL-POINTS margin (the real
tiebreak), so the end-game 4th-down / clock logic knows the team is trailing the match.
Non-final frames and frames-that-still-decide are unchanged (win the mini-game).

Run: .venv/bin/python test_frames_final_tiebreak.py   (exits non-zero on any failure)
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


def _rules(framesPerGame=6):
    gr = GameRules()
    gr.gameFormat = 'frames'
    gr.framesPerGame = framesPerGame
    return gr


def build(*, framesWonHome, framesWonAway, frameStartHome, frameStartAway,
          homeScore, awayScore, clock=45, ballOn=52, offense='home',
          frameIndex=5):
    """A frames game in the FINAL frame (index 5 of 6), Q4, clock winding down, on 4th
    down. Scores are set explicitly so the in-frame margin and the running total are both
    exactly what the scenario needs."""
    gr = _rules()
    s = Scenario(gameRules=gr)
    off = homeScore if offense == 'home' else awayScore
    dfn = awayScore if offense == 'home' else homeScore
    s.situation(quarter=4, clock=int(clock), offense=offense,
                offScore=off, defScore=dfn, down=4, distance=8, ballOn=ballOn)
    g = s.g
    g.homeScore, g.awayScore = homeScore, awayScore
    g._frameStartHome, g._frameStartAway = frameStartHome, frameStartAway
    g._framesWonHome, g._framesWonAway = framesWonHome, framesWonAway
    g._frameIndex = frameIndex
    return s, g


def punts(*, trials=40, **kw):
    """Fraction of trials the offense PUNTS."""
    p = 0
    for _ in range(trials):
        s, _g = build(**kw)
        if s.fourthDownPlay() == PlayType.Punt:
            p += 1
    return p / trials


print("1. THE BUG: final frame, winning the frame only LEVELS it, down 1 on total, midfield")
# frames 2-3 (home down 1). In-frame home up 3 (0->3 vs away 4 static): winning -> 3-3 level.
# Total home 3, away 4 -> home down 1 on the tiebreak = LOSING the match. Must NOT punt.
r = punts(framesWonHome=2, framesWonAway=3, frameStartHome=0, frameStartAway=4,
          homeScore=3, awayScore=4, clock=45, ballOn=52)
expect(f"up in frame / frames level if won / down 1 total / midfield -> does NOT punt (punt rate {r:.2f})",
       r == 0.0)

print("2. Same but a hair more frame time left (still under a minute) -> still no punt")
r = punts(framesWonHome=2, framesWonAway=3, frameStartHome=0, frameStartAway=4,
          homeScore=3, awayScore=4, clock=55, ballOn=50)
expect(f"~55s, midfield, losing the tiebreak -> does NOT punt (punt rate {r:.2f})", r == 0.0)

print("3. WINNING the match (frames level but AHEAD on points) -> may manage/punt the lead")
# Same frame lead, but home is UP 3 on total (3-0): frames level -> points -> home WINS.
# A team winning the match late is allowed to sit on it (this is NOT the bug).
r = punts(framesWonHome=2, framesWonAway=3, frameStartHome=0, frameStartAway=0,
          homeScore=3, awayScore=0, clock=45, ballOn=52)
expect(f"leading the tiebreak -> punting/managing is allowed (punt rate {r:.2f})", r > 0.0)

print("4. Winning the frame gives the frames LEAD (not a tie) -> frame margin governs")
# frames 3-2 (home already ahead); winning this frame -> 4-2, home wins on FRAMES.
# Down on total points is irrelevant, so the team plays to the frame (up in it) -> manage.
r = punts(framesWonHome=3, framesWonAway=2, frameStartHome=0, frameStartAway=4,
          homeScore=3, awayScore=4, clock=45, ballOn=52)
expect(f"frames lead secured by winning frame -> not forced to go (punt rate {r:.2f})", r > 0.0)

print("5. AWAY offense mirror: losing the tiebreak in the final frame -> no punt")
# away up in frame (frame 3-0), frames 2-3 (away down 1 -> would level), away down 1 total.
r = punts(framesWonHome=3, framesWonAway=2, frameStartHome=4, frameStartAway=0,
          homeScore=4, awayScore=3, clock=45, ballOn=52, offense='away')
expect(f"away losing the tiebreak, midfield -> does NOT punt (punt rate {r:.2f})", r == 0.0)


print()
if failures:
    print(f">>> {len(failures)} FAILURE(S)")
    for f in failures:
        print("   -", f)
    sys.exit(1)
print("PASS — frames final-frame tiebreak drives the end-game 4th-down call.")
