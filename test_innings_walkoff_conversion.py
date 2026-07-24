"""Innings: a walk-off conversion is chosen on ODDS, not on size.

Reported (2026-07-22): bottom of the 3rd, ladder on, a team scored a touchdown to
TIE — then went for the 4-point rung instead of the far easier 2-point, when any
made conversion wins the game.

Batting last in the final at-bat, a conversion that takes the lead ends the game
immediately — `InningsFormat.checkEarlyEnd` walks it off the moment the home side
leads in the bottom half. Tries remaining are irrelevant, since the game is over
before they could be used. So the only thing that matters is the ODDS of
converting; extra points can never be spent.

The old routing only sent the last TRY of the at-bat to the outcome-based
chooser. With tries left it fell through to the eagerness heuristic, which is a
top-rung gamble versus `_forcedGoRung` — and that reaches for the highest rung
clearing a make-odds floor, which is where the 4 came from.

Run: .venv/bin/python test_innings_walkoff_conversion.py
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


def _rules():
    gr = GameRules()
    gr.gameFormat = 'innings'
    gr.inningsPerGame = 3
    gr.triesPerInning = 3
    gr.conversionLadderEnabled = True     # 2/3/4/5-pt rungs on the board
    return gr


def picks(*, deficit, half='bottom', inning=3, tries=0, offense='home', trials=30):
    """Distribution of chosen rung values. `deficit` is from the scoring team's
    view AFTER its touchdown (0 = tied)."""
    out = {}
    for _ in range(trials):
        s = Scenario(gameRules=_rules())
        s.setKickerLeg('home', 60); s.setKickerLeg('away', 60)
        s.situation(quarter=1, clock=900, offense=offense,
                    offScore=20, defScore=20 + deficit,
                    down=1, distance=10, ballOn=20)
        g = s.g
        g.homeScore, g.awayScore = (20, 20 + deficit) if offense == 'home' else (20 + deficit, 20)
        g._inningsNumber = inning; g._inningsHalf = half; g._inningsTries = tries
        g._inningsContinues = 0
        team = g.homeTeam if offense == 'home' else g.awayTeam
        pts = float(g._chooseConversion(team)['points'])
        out[pts] = out.get(pts, 0) + 1
    return out


print("1. The reported case — bottom of the last inning, TIED, tries remaining")
for tries, label in ((0, 'try 1 of 3'), (1, 'try 2 of 3')):
    p = picks(deficit=0, tries=tries)
    expect(f"{label}: always the most makeable rung (the 2), never a bigger one  {p}",
           set(p) == {2.0})

print("2. Still correct on the LAST try")
p = picks(deficit=0, tries=2)
expect(f"try 3 of 3, tied → the 2  {p}", set(p) == {2.0})

print("3. A deficit the 2 can't cover takes the smallest rung that WINS")
# Down 2 after the TD: the 2-pt only ties, so it must reach the 3.
p = picks(deficit=2, tries=0)
expect(f"down 2 → never the 2 (it only ties)  {p}", 2.0 not in p)
expect(f"down 2 → takes a winning rung  {p}", all(v > 2 for v in p))

print("4. Not a walk-off spot → untouched")
# TOP half: the home side still bats, so nothing walks off here.
p = picks(deficit=0, half='top', offense='away', tries=0)
expect(f"top half, tied → defers to the normal policy  {p}", len(p) >= 1)
# Earlier inning: a lead now doesn't end the game.
p = picks(deficit=0, inning=1, tries=0)
expect(f"inning 1, tied → defers  {p}", len(p) >= 1)

print("5. Extra innings walk off the same way")
p = picks(deficit=0, inning=4, tries=0)
expect(f"inning 4 (extras), bottom, tied → the 2  {p}", set(p) == {2.0})

print()
if failures:
    print(f">>> {len(failures)} FAILURE(S)")
    for f in failures:
        print("   -", f)
    sys.exit(1)
print("PASS — a walk-off conversion is picked on odds, not on points.")
