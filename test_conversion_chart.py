"""The go-for-two chart counts possessions in what a possession can MAXIMALLY yield.

⚠️ IT USED TO COUNT IN TD+XP, AND THAT INVERTED THE CHART EITHER SIDE OF A GAP OF 8.
`_conversionDesire` measured the remaining gap in `one` (TD + XP = 7 at default rules)
while a possession can actually produce `_maxPossession()` (8 = TD + the best conversion
rung) — whose own docstring calls it "the 'still a one-score game' bound". A gap of
exactly 8 therefore read as two possessions when it is one, and the two deficits around
it came out backwards:

  down 9  — the kick GUARANTEES a one-possession game (8). Going for two reaches 7, still
            one possession, and risks 9, which is two. The kick strictly dominates.
            Measured: the sim went for it 94% of the time.
  down 10 — the kick leaves 9, two possessions. Two makes it 8 (ONE), and a miss leaves
            10 — also two, exactly what the kick would have given. The try is a FREE
            ROLL. Measured: the sim took it 23% of the time.

Reported from a live game as a team going for two while down ten. It was not a coaching
error; the chart rated the correct call as an occasional longshot.

The dominance below is derived from the rules rather than hardcoded, so this keeps
holding if the TD / XP / 2-pt / ladder values are voted to something else.

Run: .venv/bin/python test_conversion_chart.py
"""
import sys, os, math, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import logging; logging.disable(logging.WARNING)
import managers
from scenario import Scenario

fails = []
def expect(label, cond):
    print(f"  [{'OK' if cond else 'FAIL'}] {label}")
    if not cond:
        fails.append(label)


s = Scenario()
g0 = s.game
MAXPOSS = g0._maxPossession()
XP = float(getattr(g0.gameRules, 'extraPointPoints', 1))
TWO = 2.0
need = lambda gap: math.ceil(gap / MAXPOSS) if gap > 0 else 0


def goRate(deficit, trials=200):
    """Share of trials the post-TD decision takes a go-rung. `deficit` is measured AFTER
    the touchdown is banked, which is the state `_chooseConversion` is handed."""
    go = 0
    random.seed(3)
    for _ in range(trials):
        s.situation(quarter=4, clock=349, offense='home', offScore=0, defScore=int(deficit),
                    down=1, distance=10, ballOn=50)
        if s.g._chooseConversion(s.g.homeTeam)['kind'] == 'go':
            go += 1
    return go / trials


print(f"Rules: maxPossession={MAXPOSS}  xp={XP}  two={TWO}")

print("\n1. The possession unit is the one-score bound, not TD+XP")
expect(f"a gap of exactly maxPossession ({MAXPOSS:.0f}) is ONE possession",
       need(MAXPOSS) == 1)
expect(f"one more than that ({MAXPOSS + 1:.0f}) is TWO",
       need(MAXPOSS + 1) == 2)

# Derived dominance, straight from the rules:
#   going is FREE   — the make gains a possession and the miss costs nothing
#   kicking DOMINATES — the make gains nothing and the miss costs a possession
# ⚠️ ONLY WHERE THE KICK STILL LEAVES YOU TRAILING. Possession-counting cannot tell a
# TIE from a LEAD — need() is 0 for both — so at a deficit the extra point already erases
# (down 1), it reports "kicking dominates" for what is really a sure tie against a shot at
# the lead. That is a genuine aggression call the TIE_OR_WIN branch owns, not a dominated
# play, and the sim taking it 66% of the time is a tuning choice rather than a defect.
freeRoll, kickDominates = [], []
for d in range(1, 25):
    if d - XP <= 0:
        continue
    nKick, nMake, nMiss = need(d - XP), need(d - TWO), need(d)
    if nMake < nKick and nMiss == nKick:
        freeRoll.append(d)
    elif nMake == nKick and nMiss > nKick:
        kickDominates.append(d)

print(f"\n2. Free-roll deficits {freeRoll} — the try gains a possession and risks nothing")
expect("at least one such deficit exists", bool(freeRoll))
for d in freeRoll:
    r = goRate(d)
    expect(f"down {d}: goes for two ({r:.2f} >= 0.80)", r >= 0.80)

print(f"\n3. Kick-dominant deficits {kickDominates} — the try gains nothing and risks a possession")
expect("at least one such deficit exists", bool(kickDominates))
for d in kickDominates:
    r = goRate(d)
    expect(f"down {d}: mostly kicks ({r:.2f} <= 0.35)", r <= 0.35)

print("\n4. The try that ties or wins outright is still taken")
tieNow = int(TWO)   # a deficit the go-rung erases exactly
expect(f"down {tieNow}: goes for the tie/win ({goRate(tieNow):.2f} >= 0.80)",
       goRate(tieNow) >= 0.80)

print("\n5. Sanity — the two classes never overlap")
expect("no deficit is both a free roll and kick-dominant",
       not (set(freeRoll) & set(kickDominates)))

print()
if fails:
    print(f"FAILED ({len(fails)}): " + "; ".join(fails))
    raise SystemExit(1)
print("PASS — the chart counts possessions in what a possession can actually score.")
