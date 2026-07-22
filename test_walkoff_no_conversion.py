"""A touchdown that ends the game skips the extra point — every format.

Owner rule (2026-07-22): if a team scores a TD on the very last play — the clock
has run out, or in innings and the other formats it's effectively a walk-off —
the try isn't needed.

The rule is deliberately "no outcome can change the result", not just "the clock
hit zero": a TD that only TIES the game still needs its try (a make wins it), and
a team still within one rung of a tie still has something to play for. Only a
decided game with a result no conversion can move skips the play.

Format-agnostic: `isGameOver()` already defers to `format.checkEarlyEnd`, so
innings walk-offs and target's first-to-X come along for free.

Run: .venv/bin/python test_walkoff_no_conversion.py
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


def _clockRules():
    return GameRules()


def _inningsRules(ladder=False):
    gr = GameRules()
    gr.gameFormat = 'innings'
    gr.inningsPerGame = 3
    gr.triesPerInning = 3
    gr.conversionLadderEnabled = ladder
    return gr


def moot(*, rules, quarter, clock, homeScore, awayScore, scoring='home',
         inning=None, half=None, tries=None, otComplete=False):
    s = Scenario(gameRules=rules)
    s.situation(quarter=quarter, clock=clock, offense=scoring,
                offScore=homeScore if scoring == 'home' else awayScore,
                defScore=awayScore if scoring == 'home' else homeScore,
                down=1, distance=10, ballOn=20)
    g = s.g
    g.homeScore, g.awayScore = homeScore, awayScore
    if inning is not None:
        g._inningsNumber = inning; g._inningsHalf = half; g._inningsTries = tries
    if otComplete:
        # In OT a lead only ends the game once the guaranteed possessions are done —
        # which is exactly the state a walk-off TD is scored in.
        g.otFirstPossComplete = True
        g.otSecondPossComplete = True
    team = g.homeTeam if scoring == 'home' else g.awayTeam
    return g._conversionIsMoot(team)


# ── 1. Clock formats ─────────────────────────────────────────────────────
print("1. Clock format — Q4 with the clock at 0:00")
expect("winning TD as time expires (up 4) → NO try",
       moot(rules=_clockRules(), quarter=4, clock=0, homeScore=24, awayScore=20) is True)
expect("TD that only TIES as time expires → try IS attempted (a make wins it)",
       moot(rules=_clockRules(), quarter=4, clock=0, homeScore=20, awayScore=20) is False)
expect("TD leaves them down 1 → within a kick of a tie → try IS attempted",
       moot(rules=_clockRules(), quarter=4, clock=0, homeScore=20, awayScore=21) is False)
expect("TD leaves them down 9 → nothing reaches a tie → NO try",
       moot(rules=_clockRules(), quarter=4, clock=0, homeScore=20, awayScore=29) is True)

print("2. Clock still running → always attempted")
for cl in (1, 45, 600):
    expect(f"Q4 {cl}s left, up 4 → try attempted",
           moot(rules=_clockRules(), quarter=4, clock=cl, homeScore=24, awayScore=20) is False)
expect("Q2 0:00 (halftime, not the end) → try attempted",
       moot(rules=_clockRules(), quarter=2, clock=0, homeScore=24, awayScore=20) is False)

print("3. Overtime — a lead after both possessions ends it")
expect("OT walk-off (both possessions done, ahead) → NO try",
       moot(rules=_clockRules(), quarter=5, clock=0, homeScore=27, awayScore=24,
            otComplete=True) is True)
expect("OT but the opponent still has its guaranteed possession → try attempted",
       moot(rules=_clockRules(), quarter=5, clock=300, homeScore=27, awayScore=24) is False)

# ── 4. Innings — the walk-off case ───────────────────────────────────────
print("4. Innings — bottom of the final inning")
expect("home takes the lead batting last → walk-off → NO try",
       moot(rules=_inningsRules(), quarter=1, clock=900, homeScore=21, awayScore=17,
            inning=3, half='bottom', tries=2) is True)
expect("home only TIES batting last → try IS attempted",
       moot(rules=_inningsRules(), quarter=1, clock=900, homeScore=17, awayScore=17,
            inning=3, half='bottom', tries=2) is False)
expect("home still trails batting last → try IS attempted (can still reach)",
       moot(rules=_inningsRules(), quarter=1, clock=900, homeScore=15, awayScore=17,
            inning=3, half='bottom', tries=2) is False)
expect("EARLIER inning, home ahead → not a walk-off → try attempted",
       moot(rules=_inningsRules(), quarter=1, clock=900, homeScore=21, awayScore=17,
            inning=1, half='bottom', tries=0) is False)
expect("TOP half of the final inning, away ahead → away still has to be batted at "
       "→ try attempted",
       moot(rules=_inningsRules(), quarter=1, clock=900, homeScore=17, awayScore=21,
            scoring='away', inning=3, half='top', tries=2) is False)

print("5. Innings + Conversion Ladder — the bigger rungs widen 'still reachable'")
# Down 8 with a 5-pt rung on the board: unreachable by the ladder, so if the game
# were over there'd be no point. But batting last it is NOT over — the try can
# extend the at-bat — so it must still be attempted.
expect("down 8 batting last with the ladder on → try attempted",
       moot(rules=_inningsRules(ladder=True), quarter=1, clock=900,
            homeScore=13, awayScore=21, inning=3, half='bottom', tries=2) is False)

print()
if failures:
    print(f">>> {len(failures)} FAILURE(S)")
    for f in failures:
        print("   -", f)
    sys.exit(1)
print("PASS — a game-ending touchdown skips the try; anything still live keeps it.")
