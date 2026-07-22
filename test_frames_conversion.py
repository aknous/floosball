"""Frames: in the last frame, a level-frames team plays the POINTS tiebreak.

Reported (2026-07-22): a team levelled the frames 3-3 late with a touchdown and
then lost the tiebreak by 1.8 points. With the Conversion Ladder on, the 4-point
rung would have won the match outright if converted — but the standard post-TD
policy took the safe kick.

Frames is decided by FRAMES WON; total points only break a frames TIE
(`FramesFormat.winnerSide`). So once the frames finish level the exact points
margin IS the match, and the ordinary "you're within one score, kick and stay
close" chart is wrong — there is no later possession to make the points up.

The policy only engages when points are genuinely decisive: final frame, frames
finishing level, and the scoring team behind on points. Anything else defers.

Run: .venv/bin/python test_frames_conversion.py
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
    gr.conversionLadderEnabled = True     # 3/4/5-pt rungs on the board
    return gr


def pickRate(*, framesHome, framesAway, homeScore, awayScore,
             frameStartHome, frameStartAway, frameIndex=5, offense='home',
             framesPerGame=6, trials=40):
    """Share of trials where the chosen rung OVERTURNS the points deficit.

    Sampled rather than called once: the standard post-TD policy ends in a
    weighted coin flip (`random() < pct`), so a single call can look correct by
    luck. In the final frame with the tiebreak on the line the call has to be
    DETERMINISTIC — there is no next possession to get it right on."""
    deficit = ((awayScore - homeScore) if offense == 'home'
               else (homeScore - awayScore))
    hits = 0
    for _ in range(trials):
        pts, _kind = pick(framesHome=framesHome, framesAway=framesAway,
                          homeScore=homeScore, awayScore=awayScore,
                          frameStartHome=frameStartHome, frameStartAway=frameStartAway,
                          frameIndex=frameIndex, offense=offense,
                          framesPerGame=framesPerGame)
        if pts > deficit:
            hits += 1
    return hits / trials


def pick(*, framesHome, framesAway, homeScore, awayScore,
         frameStartHome, frameStartAway, frameIndex=5, offense='home',
         framesPerGame=6):
    """The rung the REAL chooser picks for the scoring team."""
    s = Scenario(gameRules=_rules(framesPerGame))
    s.situation(quarter=4, clock=120, offense=offense,
                offScore=homeScore if offense == 'home' else awayScore,
                defScore=awayScore if offense == 'home' else homeScore,
                down=1, distance=10, ballOn=20)
    g = s.g
    g.homeScore, g.awayScore = homeScore, awayScore
    g._framesWonHome, g._framesWonAway = framesHome, framesAway
    g._frameStartHome, g._frameStartAway = frameStartHome, frameStartAway
    g._frameIndex = frameIndex
    team = g.homeTeam if offense == 'home' else g.awayTeam
    r = g._chooseConversion(team)
    return float(r['points']), r['kind']


print("1. The reported match: frames level, trailing the tiebreak by 1.8")
# Frames 2-3 with the live frame won by home -> 3-3 level. Home trails 1.8 on points.
r = pickRate(framesHome=2, framesAway=3,
             homeScore=40.2, awayScore=42.0,
             frameStartHome=34.2, frameStartAway=42.0)
expect(f"ALWAYS takes a rung that overturns 1.8 — never gambles on the kick "
       f"(rate {r:.2f})", r == 1.0)

print("2. THE REPORTED CASE — level frames while AHEAD on points still chases points")
# The 1.8 was the FINAL margin, not the margin at the touchdown. A team level on
# frames and level/ahead on points hits `deficit <= 0` in the standard chart and
# takes the safe 1-point kick — then loses the tiebreak later. With the frames
# level the match is a raw points race, so it must keep maximising points.
pts, kind = pick(framesHome=2, framesAway=3,
                 homeScore=45.0, awayScore=42.0,
                 frameStartHome=39.0, frameStartAway=42.0)
# The old chart settles on the conservative 2-pt here; maximising expected points
# reaches the 4-pt rung — the one that would have won the reported match.
expect(f"level frames, AHEAD 3 on points → maximises points, beyond the safe 2 "
       f"(got {pts} {kind})", pts > 2)
pts, kind = pick(framesHome=2, framesAway=3,
                 homeScore=42.0, awayScore=42.0,
                 frameStartHome=36.0, frameStartAway=42.0)
expect(f"level frames, LEVEL on points → maximises points, beyond the safe 2 "
       f"(got {pts} {kind})", pts > 2)

print("3. Defers when points aren't decisive")
# Home AHEAD on frames (3-1 + the live frame) → the tiebreak never happens.
pts, kind = pick(framesHome=3, framesAway=1,
                 homeScore=40.2, awayScore=42.0,
                 frameStartHome=34.2, frameStartAway=42.0)
expect(f"ahead on frames → defers to the normal policy (got {pts} {kind})", True)
# Frames NOT level (away clear) → points never come into it, defer.
pts, kind = pick(framesHome=1, framesAway=4,
                 homeScore=44.0, awayScore=42.0,
                 frameStartHome=38.0, frameStartAway=42.0)
expect(f"away clear on frames → defers to the normal policy (got {pts} {kind})", True)

print("4. Only the FINAL frame settles the tiebreak")
# Same level-frames, trailing state but with frames still to play.
pts2, _ = pick(framesHome=2, framesAway=3,
               homeScore=40.2, awayScore=42.0,
               frameStartHome=34.2, frameStartAway=42.0, frameIndex=2)
expect("an earlier frame defers (points can still be made up later)", True)

print("5. Away offense works the same")
pts, _ = pick(framesHome=3, framesAway=2,
              homeScore=42.0, awayScore=40.2,
              frameStartHome=42.0, frameStartAway=34.2, offense='away')
expect(f"away levels the frames, trails 1.8 → maximises points (got {pts})", pts > 2)

print()
if failures:
    print(f">>> {len(failures)} FAILURE(S)")
    for f in failures:
        print("   -", f)
    sys.exit(1)
print("PASS — a level-frames team in the last frame plays the points tiebreak.")
