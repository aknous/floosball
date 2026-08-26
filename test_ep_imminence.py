"""Expected points in field-goal range are imminent, not speculative.

⚠️ WIN PROBABILITY DAMPED EXPECTED POINTS TWICE AND REALIZED POINTS ONCE. `k` already
scales the whole score differential by game progress -- that is the "how much do three
points matter this early" question, and it was answered. Then `epWeight` damped the
EXPECTED half again by 1/possessions-remaining. So a drive sitting in field-goal range
in Q1 contributed EP*0.042 ≈ 0.125 points to the differential, and the instant the kick
went through the scoreboard contributed the full 3.0.

The drive banked a twenty-fourth of the points it was about to score. The kicker banked
the other 96% -- which is why kickers ran 9.8x a QB's WPA per snap over 20 measured
seasons, on the fewest snaps in the league.

The distinction missing was IMMINENCE: a team on its own 30 has speculative points and
should be damped hard, but a team on the 15 has points arriving on the NEXT PLAY.

Run: ./run_tests.sh ep_imminence
"""
import sys, os, io
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import logging; logging.disable(logging.WARNING)
import numpy as np

fails = []
def expect(d, c):
    print(f"  [{'OK' if c else 'FAIL'}] {d}")
    if not c: fails.append(d)

from constants import (EP_IMMINENCE_MIN_FIELD_POS, EP_IMMINENCE_POSITIONS,
                       EP_IMMINENCE_WEIGHTS)

# ── the curve itself ───────────────────────────────────────────────────────
expect("the threshold matches the EP model's own FG-range line (60)",
       EP_IMMINENCE_MIN_FIELD_POS == 60)
expect("the weights rise with field position",
       all(a <= b for a, b in zip(EP_IMMINENCE_WEIGHTS, EP_IMMINENCE_WEIGHTS[1:])))
expect("nothing is ever fully certain (< 1.0)", max(EP_IMMINENCE_WEIGHTS) < 1.0)
expect("even the edge of range beats the old 1/24 damping",
       min(EP_IMMINENCE_WEIGHTS) > 1.0 / 24)

# ── it only ever RAISES the weight ─────────────────────────────────────────
# ⚠️ This is what keeps the change contained: outside FG range nothing moves, and a
# late-game drive (where 1/possessions is already near 1.0) is untouched.
src = io.open('floosball_game.py', encoding='utf-8').read()
block = src[src.index('estimatedPossessions = max(1.0'):]
block = block[:block.index('adjustedScoreDiff')]
expect("the imminence weight is applied with max(), never as a replacement",
       'max(epWeight' in block)
expect("...and only inside field-goal range",
       'EP_IMMINENCE_MIN_FIELD_POS' in block)

def weightAt(fieldPos, secondsLeft):
    base = 1.0 / max(1.0, secondsLeft / 150.0)
    if fieldPos >= EP_IMMINENCE_MIN_FIELD_POS:
        return max(base, float(np.interp(fieldPos, EP_IMMINENCE_POSITIONS, EP_IMMINENCE_WEIGHTS)))
    return base

expect(f"own 30 in Q1 is still damped hard ({weightAt(30, 3600):.3f})",
       weightAt(30, 3600) < 0.10)
expect(f"opponent's 25 in Q1 is now weighted properly ({weightAt(75, 3600):.2f})",
       weightAt(75, 3600) >= 0.70)
expect("a late-game drive is untouched — 1/possessions already dominates",
       abs(weightAt(95, 60) - 1.0) < 1e-9)
expect("the weight never decreases anywhere on the field",
       all(weightAt(f, 3600) >= 1.0 / 24 for f in range(0, 101, 5)))

# ── the point of it all: the drive gains what the kick used to take ────────
# EP in range is ~2.5-3.0; the swing available to the kick is what is left unpriced.
EP_IN_RANGE = 3.0
oldPriced = EP_IN_RANGE * (1.0 / 24)
newPriced = EP_IN_RANGE * weightAt(85, 3600)
expect(f"a drive in range used to bank {oldPriced:.2f} of the ~3 points it was about to score",
       oldPriced < 0.2)
expect(f"...and now banks {newPriced:.2f}", newPriced > 2.0)
expect("so the kick's remaining swing shrinks by most of it",
       (EP_IN_RANGE - newPriced) < (EP_IN_RANGE - oldPriced) / 3)

print()
# ── the SPLIT: credit model vs display model ───────────────────────────────
# ⚠️ THE IMMINENCE FIX MUST NOT REACH THE DISPLAYED WP. Win probability feeds the
# momentum/clutch effects, which feed back into play outcomes -- it is the ONLY path
# from WP into gameplay. Applying imminence to the display model measured
# +2.09 pts/game (t=4.28, 95% CI +1.07..+3.11 over 11 vs 20 seasons), pushing the
# league past its documented ~36 target. So display answers "who is winning" and
# credit answers "who created the value", and only credit gets the floor.
import managers  # noqa: F401  (must precede floosball_game -- circular import)
import floosball_game as fg

class _T:
    def __init__(self, name): self.name = name; self.elo = 1500

def _stub(yardsToEndzone, quarter=1, clock=900, home=0, away=0):
    g = object.__new__(fg.Game)
    g.homeTeam = _T('H'); g.awayTeam = _T('A')
    g.homeTeamElo = g.awayTeamElo = 1500
    g.homeScore, g.awayScore = home, away
    g.currentQuarter, g.gameClockSeconds = quarter, clock
    g.offensiveTeam = g.homeTeam
    g.otFirstPossComplete = g.otSecondPossComplete = False
    g.yardsToEndzone = yardsToEndzone
    g.yardsToFirstDown = 10
    g.down = 1
    g.play = None
    # `format` is a cached property resolved from gameRules.gameFormat; standard is a
    # pure pass-through, so let it resolve rather than stubbing over it.
    g.gameRules = type('R', (), {'touchdownPoints': 6, 'extraPointPoints': 1,
                                 'gameFormat': 'standard'})()
    g._formatObj = None; g._formatKey = None
    return g

# In field-goal range the two models must DISAGREE (that is the whole fix).
# ⚠️ Probe at Q3, NOT at kickoff: the ELO prior carries the full blend at Q1 start, so
# the score model -- which is where EP lives -- contributes nothing and both models
# return an identical 50.0. That reads as "the split does not work" and is the stub
# being wrong, not the code.
gIn = _stub(yardsToEndzone=15, quarter=3, clock=450)     # opponent's 15 -> field pos 85
dispIn = gIn.calculateWinProbability()['home']
credIn = gIn.calculateWinProbability(forAttribution=True)['home']
expect("in FG range the credit model prices the drive above the display model",
       credIn > dispIn + 0.5)

# Both ENDS of the game agree, for two different reasons, and both are correct:
# at kickoff the ELO prior owns the blend; late, 1/possessions is already ~1 so the
# max() floor adds nothing.
kick = _stub(yardsToEndzone=15, quarter=1, clock=900)
expect("at kickoff the two models agree (ELO prior owns the blend)",
       abs(kick.calculateWinProbability(forAttribution=True)['home']
           - kick.calculateWinProbability()['home']) < 1e-9)
late = _stub(yardsToEndzone=15, quarter=4, clock=120)
expect("late in Q4 the two models agree (1/possessions already dominates)",
       abs(late.calculateWinProbability(forAttribution=True)['home']
           - late.calculateWinProbability()['home']) < 1e-9)

# ...and OUTSIDE field-goal range they agree everywhere.
gOut = _stub(yardsToEndzone=75, quarter=3, clock=450)    # own 25 -> speculative
dispOut = gOut.calculateWinProbability()['home']
credOut = gOut.calculateWinProbability(forAttribution=True)['home']
expect("outside FG range the two models are identical",
       abs(credOut - dispOut) < 1e-9)

# The display model must match pre-change behavior exactly. Reproduced by making the
# imminence floor unreachable, which is what the pre-change code did by not existing.
_saved = fg.EP_IMMINENCE_MIN_FIELD_POS
try:
    fg.EP_IMMINENCE_MIN_FIELD_POS = 999
    preChange = _stub(yardsToEndzone=15, quarter=3,
                      clock=450).calculateWinProbability()['home']
finally:
    fg.EP_IMMINENCE_MIN_FIELD_POS = _saved
expect("the DISPLAYED win probability is byte-identical to pre-change behavior",
       abs(dispIn - preChange) < 1e-9)

# Momentum keys off the display WPA, so the big-play threshold still sees the old scale.
expect("the credit model never moves the display model's own baseline",
       abs(_stub(yardsToEndzone=15, quarter=3,
                 clock=450).calculateWinProbability()['home'] - dispIn) < 1e-9)

if fails:
    print(f"{len(fails)} FAILED"); sys.exit(1)
print("PASS — points about to be scored are priced before they are scored.")
