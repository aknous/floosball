"""A kneel that ends the game outranks every scoring option, on ANY down.

⚠️ THE END-OF-HALF FIELD GOAL USED TO PREEMPT IT. `_lastSnapBeforeBreak` reads only the
clock and sits ABOVE the down split in `playCaller`, while the clock-management block
that owned kneeling is gated on `down < downsPerSeries` — so on a FINAL down there was no
kneel option at all. Reported: leading 21-20, 4th and 5 on the opponent's 33, 0:28 left,
opponent out of timeouts. It kicked a 50-yarder 100% of the time. The kneel ends the game
as a win; the kick can miss, and either way hands the ball back with time on it.

The rule is `_kneelOutDetail`: leading THE MATCH in Q4/OT, safe field position, and enough
drain in hand to reach 0:00. On a final down there is exactly one kneel and it is only
safe BECAUSE the clock dies on it — otherwise the down, and the ball, are gone.

Run: .venv/bin/python test_kneel_out.py
"""
import sys, os, random, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import logging; logging.disable(logging.WARNING)
import managers  # resolve circular import before floosball_game
from scenario import Scenario, PlayType

fails = []
def expect(label, cond):
    print(f"  [{'OK' if cond else 'FAIL'}] {label}")
    if not cond:
        fails.append(label)


def calls(*, trials=40, seed=4, **situation):
    """Distribution of 4th-down calls for a situation."""
    s = Scenario(); random.seed(seed)
    c = collections.Counter()
    for _ in range(trials):
        s.situation(**situation)
        c[s.fourthDownPlay()] += 1
    return c


REPORTED = dict(quarter=4, clock=28, offense='home', offScore=21, defScore=20,
                down=4, distance=5, ballOn=33, offTimeouts=2, clockRunning=True)

print("1. The reported case — a kneel ends it, so it is taken over a makeable FG")
c = calls(defTimeouts=0, **REPORTED)
expect(f"opponent out of timeouts -> kneel every time ({c[PlayType.Kneel]}/40)",
       c[PlayType.Kneel] == 40)

print("\n2. ...but only when the opponent cannot stop the clock")
c = calls(defTimeouts=2, **REPORTED)
expect(f"opponent holding timeouts -> never kneel ({c[PlayType.Kneel]}/40)",
       c[PlayType.Kneel] == 0)
expect("...and the end-of-half field goal is taken instead",
       c[PlayType.FieldGoal] > 0)

print("\n3. Not enough drain in hand is not a kneel — it would surrender the down")
# One kneel drains ~40s; 90s left cannot be run out from a final down.
c = calls(defTimeouts=0, **{**REPORTED, 'clock': 90})
expect(f"0:90 with one kneel available -> never kneel ({c[PlayType.Kneel]}/40)",
       c[PlayType.Kneel] == 0)

print("\n4. Trailing or tied never kneels it out")
c = calls(defTimeouts=0, **{**REPORTED, 'offScore': 20, 'defScore': 21})
expect(f"trailing -> never kneel ({c[PlayType.Kneel]}/40)", c[PlayType.Kneel] == 0)
c = calls(defTimeouts=0, **{**REPORTED, 'offScore': 20, 'defScore': 20})
expect(f"tied -> never kneel ({c[PlayType.Kneel]}/40)", c[PlayType.Kneel] == 0)

print("\n5. Not in Q4/OT — a kneel ends a HALF, not the game, so it is not a win")
c = calls(defTimeouts=0, **{**REPORTED, 'quarter': 2})
expect(f"Q2 -> never kneel ({c[PlayType.Kneel]}/40)", c[PlayType.Kneel] == 0)

print("\n6. Backed up on the goal line, a kneel is a safety, not a win")
# ballOn is yards to the opponent's endzone, so 97 puts the offense on its own 3.
c = calls(defTimeouts=0, **{**REPORTED, 'ballOn': 99})
expect(f"own goal line -> never kneel ({c[PlayType.Kneel]}/40)", c[PlayType.Kneel] == 0)

print("\n7. The helper itself, read directly")
s = Scenario(); random.seed(4)
s.situation(defTimeouts=0, **REPORTED)
detail = s.g._kneelOutDetail(s.g.offensiveTeam is s.g.homeTeam)
expect("returns the drain numbers when a kneel-out is on", bool(detail))
expect(f"one kneel is available on a final down ({(detail or {}).get('availableKneels')})",
       (detail or {}).get('availableKneels') == 1)
expect(f"and it outlasts the clock ({(detail or {}).get('drainableSeconds')}s vs 28s)",
       (detail or {}).get('drainableSeconds', 0) >= 28)

s.situation(defTimeouts=0, **{**REPORTED, 'offScore': 20, 'defScore': 21})
expect("returns None when trailing",
       s.g._kneelOutDetail(s.g.offensiveTeam is s.g.homeTeam) is None)

print()
if fails:
    print(f"FAILED ({len(fails)}): " + "; ".join(fails))
    raise SystemExit(1)
print("PASS — a decided game is knelt out, and never speculatively.")
