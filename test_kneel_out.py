"""A kneel that ends the game outranks every scoring option, on ANY down.

⚠️ THE END-OF-HALF FIELD GOAL USED TO PREEMPT IT. `_lastSnapBeforeBreak` reads only the
clock and sits ABOVE the down split in `playCaller`, while the clock-management block
that owned kneeling is gated on `down < downsPerSeries` — so on a FINAL down there was no
kneel option at all. Reported: leading 21-20, 4th and 5 on the opponent's 33, 0:28 left,
opponent out of timeouts. It kicked a 50-yarder 100% of the time. The kneel ends the game
as a win; the kick can miss, and either way hands the ball back with time on it.

The rule is `_kneelOutDetail`: leading THE MATCH in Q4/OT, safe field position, and enough
drain in hand to reach 0:00. On a final down there is exactly one kneel, and it is a
turnover on downs, which STOPS THE CLOCK after the ~4s snap: no play-clock runoff, so it
ends the game only when the snap itself reaches 0:00 (prod game 6867: WAS up 15, 4th & 4
at its own 26, 0:15 left, knelt, NYS took over at 0:11 and scored).

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

print("1. A final-down kneel ends it only when the snap itself runs the clock out")
c = calls(defTimeouts=0, **{**REPORTED, 'clock': 4})
expect(f"0:04 -> kneel every time ({c[PlayType.Kneel]}/40)", c[PlayType.Kneel] == 40)
c = calls(defTimeouts=2, **{**REPORTED, 'clock': 4})
expect(f"0:04, opponent holding timeouts -> still kneel ({c[PlayType.Kneel]}/40)",
       c[PlayType.Kneel] == 40)

print("\n2. With more on the clock it is a turnover on downs, so it is not taken")
c = calls(defTimeouts=0, **REPORTED)
expect(f"0:28, opponent out of timeouts -> never kneel ({c[PlayType.Kneel]}/40)",
       c[PlayType.Kneel] == 0)
expect("...and the end-of-half field goal is taken instead",
       c[PlayType.FieldGoal] > 0)
c = calls(defTimeouts=2, **REPORTED)
expect(f"0:28, opponent holding timeouts -> never kneel ({c[PlayType.Kneel]}/40)",
       c[PlayType.Kneel] == 0)

print("\n3. Not enough drain in hand is not a kneel — it would surrender the down")
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
s.situation(defTimeouts=0, **{**REPORTED, 'clock': 4})
detail = s.g._kneelOutDetail(s.g.offensiveTeam is s.g.homeTeam)
expect("returns the drain numbers when a kneel-out is on", bool(detail))
expect(f"one kneel is available on a final down ({(detail or {}).get('availableKneels')})",
       (detail or {}).get('availableKneels') == 1)
expect(f"and a final-down kneel drains only its snap ({(detail or {}).get('drainableSeconds')}s)",
       (detail or {}).get('drainableSeconds') == 4)
s.situation(defTimeouts=0, **REPORTED)
expect("returns None on a final down with 0:28 left",
       s.g._kneelOutDetail(s.g.offensiveTeam is s.g.homeTeam) is None)

s.situation(defTimeouts=0, **{**REPORTED, 'offScore': 20, 'defScore': 21})
expect("returns None when trailing",
       s.g._kneelOutDetail(s.g.offensiveTeam is s.g.homeTeam) is None)

print("\n8. The reported case: a big lead does not make a final-down kneel a kneel-out")
# Prod game 6867: up 15, 4th & 4 on the own 26, 0:15, opponent holding two timeouts.
GAME_6867 = dict(quarter=4, clock=15, offense='home', offScore=24, defScore=9,
                 down=4, distance=4, ballOn=74, offTimeouts=0, clockRunning=False)
c = calls(defTimeouts=2, **GAME_6867)
expect(f"opponent holding timeouts -> never kneel ({c[PlayType.Kneel]}/40)",
       c[PlayType.Kneel] == 0)
expect(f"...it punts instead ({c[PlayType.Punt]}/40)", c[PlayType.Punt] == 40)
c = calls(defTimeouts=0, **GAME_6867)
expect(f"opponent out of timeouts -> still never kneel ({c[PlayType.Kneel]}/40)",
       c[PlayType.Kneel] == 0)
s.situation(defTimeouts=1, **{**GAME_6867, 'down': 2})
detail = s.g._kneelOutDetail(s.g.offensiveTeam is s.g.homeTeam)
expect("an earlier down still kneels it out (another kneel follows the timeout)",
       detail is not None)
s.situation(defTimeouts=2, **{**GAME_6867, 'down': 2})
expect("...but not against two timeouts: kneel, timeout, kneel, timeout, then 4th down",
       s.g._kneelOutDetail(s.g.offensiveTeam is s.g.homeTeam) is None)

print("\n9. The defense's timeouts count unless the defense itself has given up")
# Prod game 6946: PHI up 12, 3rd & 7 on its own 43, 0:21, NYS holding one timeout.
# It knelt (the kneel math ignored the timeout for any lead over 8 inside 1:00), NYS
# called time and PHI punted on 4th down. NYS's own timeout rule only quits past 16.
GAME_6946 = dict(quarter=4, clock=21, offense='home', offScore=35, defScore=23,
                 down=3, distance=7, ballOn=57, offTimeouts=0, clockRunning=True)
s.situation(defTimeouts=1, **GAME_6946)
expect("up 12, opponent holding a timeout -> not a kneel-out",
       s.g._kneelOutDetail(True) is None)
random.seed(4)
kneels = 0
for _ in range(40):
    s.situation(defTimeouts=1, **GAME_6946)
    kneels += s.callPlay() == PlayType.Kneel
expect(f"...so the snap is played for the first down ({kneels}/40 kneels)", kneels == 0)
s.situation(defTimeouts=0, **GAME_6946)
expect("opponent out of timeouts -> kneel it out", s.g._kneelOutDetail(True) is not None)
s.situation(defTimeouts=0, **GAME_6946)
expect(f"...and the play caller kneels ({s.callPlay().name})",
       s.g.play.playType == PlayType.Kneel)
s.situation(defTimeouts=1, **{**GAME_6946, 'offScore': 45})
expect("up 22 (the defense will not spend its timeout) -> kneel it out",
       s.g._kneelOutDetail(True) is not None)

print()
if fails:
    print(f"FAILED ({len(fails)}): " + "; ".join(fails))
    raise SystemExit(1)
print("PASS — a decided game is knelt out, and never speculatively.")
