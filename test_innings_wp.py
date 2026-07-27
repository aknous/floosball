"""Innings win-probability model regression.

Owner-reported bug: innings WP spiked toward 100% on scoring plays. The engine's WP is a
football-clock model whose score logistic steepens as the clock runs out — but innings gives
the trailing team a GUARANTEED at-bat to answer, so a lead is far softer than the clock model
assumes. InningsFormat now supplies a run-differential WP (a lead worth less the more at-bats
remain, firming as the innings run out) via adjustWinProbability.

Run: .venv/bin/python test_innings_wp.py   (exits non-zero on any failure)
"""
import sys
sys.path.insert(0, '/Users/andrew/Projects/floosball')
import logging; logging.disable(logging.CRITICAL)
from types import SimpleNamespace as NS
from game_formats import InningsFormat

failures = []
def expect(desc, cond):
    print(f"  [{'OK' if cond else 'FAIL'}] {desc}")
    if not cond:
        failures.append(desc)

fmt = InningsFormat()

def wp(homeS, awayS, inning, half='top', tries=0, N=3, T=3, eloH=1500, eloA=1500):
    g = NS(homeScore=homeS, awayScore=awayS, _inningsNumber=inning, _inningsHalf=half,
           _inningsTries=tries, homeTeamElo=eloH, awayTeamElo=eloA,
           gameRules=NS(inningsPerGame=N, triesPerInning=T))
    return round(fmt.adjustWinProbability(g, 50, 50, 0)[0], 1)


print("1. No spike: a mid-game lead stays well under certainty")
# The reported bug: a single score sent WP toward ~100%. A one-score lead mid-game should read
# comfortably below that — the opponent still bats.
expect(f"up 7, inning 2 of 3 -> {wp(7,0,2)}% (not a spike)", wp(7, 0, 2) < 80)
expect(f"up 7, inning 1 of 3 -> {wp(7,0,1)}% (early lead is soft)", wp(7, 0, 1) < 70)
expect(f"even a 21-pt blowout in inning 2 isn't ~100% -> {wp(21,0,2)}%", wp(21, 0, 2) < 95)

print("\n2. A lead FIRMS UP as the at-bats run out")
early = wp(7, 0, 1)          # up 7, first inning
mid = wp(7, 0, 2)            # up 7, second inning
late = wp(7, 0, 3, 'bottom', 2)  # up 7, last inning / last try
expect(f"the same +7 lead climbs as innings pass ({early} < {mid} < {late})",
       early < mid < late)
expect(f"up 7 on the last try is strongly favored -> {late}%", late >= 80)

print("\n3. Symmetry + tie behave")
expect("tied is 50/50 at any point", wp(0, 0, 1) == 50.0 and wp(0, 0, 3, 'bottom', 2) == 50.0)
expect(f"down 7 mirrors up 7 ({wp(0,7,2)} == 100-{wp(7,0,2)})",
       abs(wp(0, 7, 2) - (100 - wp(7, 0, 2))) < 0.2)
expect(f"a bigger deficit is worse ({wp(0,14,2)} < {wp(0,7,2)})", wp(0, 14, 2) < wp(0, 7, 2))

print("\n4. ELO nudges the pre-game / early prior, fading as the game runs on")
expect(f"a +80-ELO home favorite leads pre-game -> {wp(0,0,1,eloH=1540,eloA=1460)}%",
       wp(0, 0, 1, eloH=1540, eloA=1460) > 52)
# ...but late, the run diff dominates — ELO barely moves a tied last-try game.
lateFav = wp(0, 0, 3, 'bottom', 2, eloH=1540, eloA=1460)
expect(f"ELO barely moves a tied LAST-try game -> {lateFav}% (~50)", abs(lateFav - 50) < 4)


print()
if failures:
    print(f">>> {len(failures)} FAILURE(S)")
    for f in failures:
        print("   -", f)
    sys.exit(1)
print("PASS — innings WP is run-driven: no scoring-play spikes, leads firm up as at-bats run out.")
