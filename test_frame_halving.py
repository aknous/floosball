"""A tied frame is HALVED, and fractional scores were deciding it on an ulp.

Reported from a frames game on a Criticality week: frame 4 showed the same points for both
teams and was not halved.

⚠️ CHAOS SCORES ARE FRACTIONAL. `ruleVoteManager._randomChaosValue` returns
`round(uniform(lo, hi), 1)`, so under a chaos ruleset a touchdown can be worth 7.1 and every
running total is a one-decimal number. `awardFrames` then computed the frame's points as
`game.homeScore - game._frameStartHome` and compared the RAW floats -- and subtracting two
accumulated floats leaves an ulp behind: `27.8 - 20.7` is 7.100000000000001 against a home
frame of exactly 7.1. The away side "outscored" the home side by 1e-15, took the whole frame,
and `_cleanNum` rounded both to 7.1 for the line score. The box score was telling the truth;
the comparison was not.

⚠️ THE BOX SCORE WAS THE SMALLER HALF. Five decision helpers ran the same subtraction, so
"am I leading this frame" and the whole `_framesFgWins` / `_framesFgFutile` family answered
off an ulp too. A coach kicking to win a match he had already drawn is this bug one layer in.

⚠️ ROUNDING TO 2dp IS EXACT, NOT A FUDGE. `_addScore` keeps every running total at
`round(x, 2)` and chaos values carry one decimal, so a real frame margin is always a multiple
of 0.1 and cannot hide under the rounding. Case 4 pins that a genuine 0.1 margin still decides
the frame.

Run: .venv/bin/python test_frame_halving.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import logging; logging.disable(logging.WARNING)
from types import SimpleNamespace

from game_formats import framePoints, _cleanNum

fails = []
def expect(label, cond):
    print(f"  [{'OK' if cond else 'FAIL'}] {label}")
    if not cond:
        fails.append(label)


def frame(homeNow, homeStart, awayNow, awayStart):
    g = SimpleNamespace(homeScore=homeNow, awayScore=awayNow,
                        _frameStartHome=homeStart, _frameStartAway=awayStart)
    h, a = framePoints(g)
    return h, a, ('home' if h > a else 'away' if a > h else 'tie')


print("\n1. THE REPORTED FRAME -- both sides scored 7.1, an ulp apart")
h, a, who = frame(20.7, 13.6, 27.8, 20.7)
expect('the raw subtraction really does differ',
       (27.8 - 20.7) != (20.7 - 13.6))
expect(f'the frame is a TIE ({h} vs {a}, was awarded away)', who == 'tie')

print("\n2. The other direction, where the noise favours home")
h, a, who = frame(13.6, 6.8, 10.2, 3.4)
expect(f'still a tie ({h} vs {a})', who == 'tie')

print("\n3. What is DECIDED and what is SHOWN are the same number")
for args in ((20.7, 13.6, 27.8, 20.7), (13.6, 6.8, 10.2, 3.4), (25.5, 17.0, 17.0, 8.5)):
    h, a, who = frame(*args)
    shown = (_cleanNum(h) == _cleanNum(a))
    expect(f'displayed {"tied" if shown else "split"} and decided {who}',
           shown == (who == 'tie'))

print("\n4. A REAL margin still decides the frame -- the rounding hides nothing")
h, a, who = frame(20.8, 13.6, 27.8, 20.7)      # home 7.2, away 7.1
expect(f'home wins by a tenth ({h} vs {a})', who == 'home')
h, a, who = frame(20.7, 13.6, 27.9, 20.7)      # home 7.1, away 7.2
expect(f'away wins by a tenth ({h} vs {a})', who == 'away')

print("\n5. Whole-number scores are untouched")
h, a, who = frame(21, 14, 21, 14)
expect('7-7 is a tie', who == 'tie' and h == 7 and a == 7)
h, a, who = frame(21, 14, 24, 14)
expect('7-10 goes to the away side', who == 'away')

print("\n6. The helper is the ONE definition -- every caller is routed through it")
import re
src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        'floosball_game.py')).read()
expect('no frame-points subtraction left inline in the engine',
       "_frameStartHome', 0)" not in src)

print(f"\n{len(fails)} failed" if fails else "\nall good")
sys.exit(1 if fails else 0)
