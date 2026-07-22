"""Frames-format clock-management regression.

Frames is the one format where the winner is decoupled from total points: the match
is decided by FRAMES WON, and points only break a frames tie (`FramesFormat.winnerSide`).
So any clock decision that would END the match has to read the frames standing, not the
score margin.

Guards the reported bug: a team ahead on total points but LOSING on frames read itself
as winning and kneeled out the clock late — kneeling the match away.

Run: .venv/bin/python test_frames_clock.py   (exits non-zero on any failure)
"""
import sys
sys.path.insert(0, '/Users/andrew/Projects/floosball')
import logging; logging.disable(logging.CRITICAL)
import managers  # resolve circular import
import floosball_game as fg
from types import SimpleNamespace as NS

failures = []
def expect(desc, cond):
    print(f"  [{'OK' if cond else 'FAIL'}] {desc}")
    if not cond:
        failures.append(desc)


class Stub:
    """Duck-typed stand-in — _framesLeadingNow only reads these attributes."""
    _framesLeadingNow = fg.Game._framesLeadingNow


def state(framesHome, framesAway, homeScore, awayScore,
          frameStartHome, frameStartAway, offense='home', key='frames'):
    o = Stub()
    o.format = NS(key=key)
    o.homeTeam, o.awayTeam = 'H', 'A'
    o.offensiveTeam = o.homeTeam if offense == 'home' else o.awayTeam
    o._framesWonHome, o._framesWonAway = framesHome, framesAway
    o.homeScore, o.awayScore = homeScore, awayScore
    o._frameStartHome, o._frameStartAway = frameStartHome, frameStartAway
    return o


print("1. 'Leading' in frames means leading the MATCH, not the scoreboard")
# THE BUG: home is up 45-20 on points but down 1-2 on frames and losing the live frame.
expect("ahead on points, behind on frames, losing the live frame → NOT leading",
       state(1, 2, 45, 20, 38, 10)._framesLeadingNow() is False)
expect("ahead on points AND on frames → leading",
       state(2, 1, 45, 20, 38, 10)._framesLeadingNow() is True)
expect("behind on points but ahead on frames → leading",
       state(2, 0, 20, 45, 18, 38)._framesLeadingNow() is True)
expect("away offense ahead on frames → leading",
       state(0, 2, 45, 20, 38, 10, offense='away')._framesLeadingNow() is True)

print("2. The frame in progress counts toward the standing (as awardFrames would)")
# Winning the live frame takes frames from 1-2 to 2-2 — level, so the POINTS tiebreak
# decides, and home is way ahead there.
expect("winning the live frame levels frames → points tiebreak makes it leading",
       state(1, 2, 45, 20, 38, 20)._framesLeadingNow() is True)
expect("level frames + tied live frame, ahead on points → leading",
       state(1, 1, 45, 40, 40, 35)._framesLeadingNow() is True)
expect("level frames + tied live frame, behind on points → NOT leading",
       state(1, 1, 40, 45, 35, 40)._framesLeadingNow() is False)
expect("dead level on everything → NOT leading (never drain a tie out)",
       state(1, 1, 40, 40, 35, 35)._framesLeadingNow() is False)

print("3. Every other format is untouched")
expect("standard format → None (callers keep using the score margin)",
       state(0, 0, 21, 14, 0, 0, key='standard')._framesLeadingNow() is None)


print()
if failures:
    print(f"FAILED: {len(failures)} check(s):")
    for f in failures:
        print("  -", f)
    raise SystemExit(1)
print("All frames clock-management checks passed.")
