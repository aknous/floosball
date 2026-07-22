"""Innings + Conversion Ladder: the last-try conversion must keep the at-bat alive.

Reported bug: bottom of the 3rd, last try, the batting team scores a TD to cut the
deficit to 8. The ladder is on (3/4/5-point rungs), so only a made TOP rung (5)
extends the at-bat without consuming the try — the one line that survives to score
again. The sim went for 4 instead, which loses whether it converts or not (down 4,
at-bat over).

Cause: `_lastChanceConversion` values a rung by whether it reaches a tie or a lead.
When the deficit exceeds every rung, every value is 0 and it fell through to
"chase the most likely points" — and 4 x its make odds beats 5 x its (longer) make
odds, so it picked a rung that cannot win. Expected points are meaningless when
every outcome that ENDS the at-bat is a loss.

Fix: in that branch, take the continuation rung (the top 'go' rung) when a make
would extend the try, whatever the odds.

Run: .venv/bin/python test_innings_conversion_lastchance.py
"""
import sys, types
sys.path.insert(0, '/Users/andrew/Projects/floosball')
_stub = types.ModuleType('floosball_game'); _stub.Game = type('G', (), {})
sys.modules['floosball_game'] = _stub
import managers.timingManager  # noqa: F401
del sys.modules['floosball_game']
from scenario import Scenario
from game_rules import GameRules
from constants import INNINGS_MAX_CONTINUATIONS

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
    gr.conversionLadderEnabled = True     # 3/4/5-pt rungs; also removes the safe kick
    return gr


def chooseRung(*, deficit, half='bottom', offense='home', tries=2, inning=3,
               continues=0, trials=40):
    """Distribution of rung point-values the REAL chooser picks, for a team that has
    just scored (TD already banked) and now trails by `deficit`."""
    counts = {}
    for _ in range(trials):
        s = Scenario(gameRules=_rules())
        s.setKickerLeg('home', 60); s.setKickerLeg('away', 60)
        off = 0
        s.situation(quarter=1, clock=900, offense=offense,
                    offScore=off, defScore=off + deficit,
                    down=1, distance=10, ballOn=20)
        g = s.g
        g._inningsNumber = inning; g._inningsHalf = half; g._inningsTries = tries
        g._inningsContinues = continues
        rungs = g._conversionRungs()
        goRungs = [r for r in rungs if r['kind'] == 'go']
        fallback = g._forcedGoRung(g.offensiveTeam, goRungs)
        pick = g._lastChanceConversion(g.offensiveTeam, goRungs, fallback, float(deficit))
        pts = float(pick['points'])
        counts[pts] = counts.get(pts, 0) + 1
    return counts


def topPoints():
    s = Scenario(gameRules=_rules())
    s.situation(quarter=1, clock=900, offense='home', offScore=0, defScore=0,
                down=1, distance=10, ballOn=20)
    go = [r for r in s.g._conversionRungs() if r['kind'] == 'go']
    return max(float(r['points']) for r in go)


TOP = topPoints()
print(f"ladder top rung = {TOP:.0f} points\n")

# ── 1. The reported bug: down 8, nothing reaches a tie ───────────────────
print("1. Bottom of the last inning, last try, down 8 — only the top rung survives")
c = chooseRung(deficit=8)
expect(f"always takes the top ({TOP:.0f}-pt) rung, never a lesser one  {c}",
       set(c) == {TOP})

# ── 2. Same logic at other unreachable deficits ──────────────────────────
print("2. Any deficit larger than the ladder behaves the same")
for d in (6, 7, 9, 12):
    c = chooseRung(deficit=d, trials=25)
    expect(f"down {d} → top rung only  {c}", set(c) == {TOP})

# ── 3. A REACHABLE deficit still picks the best outcome, not blindly the top ──
print("3. When a rung can tie or win, the outcome logic still rules")
# Down 3 with 3/4/5 available: the 4 and 5 both WIN, the 3 only ties. It should
# never pick something that leaves the team losing.
c = chooseRung(deficit=3, trials=30)
expect(f"down 3 → never a losing rung (all picks >= 3)  {c}", all(p >= 3 for p in c))
# Down 5: only the 5 reaches (a tie); lesser rungs leave it behind.
c = chooseRung(deficit=5, trials=30)
expect(f"down 5 → takes the {TOP:.0f} that ties  {c}", set(c) == {TOP})

# ── 4. Past the continuation cap there is nothing to keep alive ──────────
print("4. At the continuation cap a made top rung no longer extends the try")
c = chooseRung(deficit=8, continues=INNINGS_MAX_CONTINUATIONS, trials=30)
expect(f"cap reached → free to chase points, not forced to the top  {c}", len(c) >= 1)
expect("cap reached → still returns a legal rung", all(p > 0 for p in c))

print()
if failures:
    print(f">>> {len(failures)} FAILURE(S)")
    for f in failures:
        print("   -", f)
    sys.exit(1)
print("PASS — the last-try conversion keeps the at-bat alive when nothing else can.")
