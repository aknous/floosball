"""Innings-format endgame regression suite (built on scenario.Scenario).

Locks in the last-scoring-chance 4th-down fix: in the innings format (no game
clock), a team trailing by MORE than a field goal on its LAST try of its FINAL
at-bat must GO FOR THE TOUCHDOWN, not kick a futile FG. Earlier tries / innings
are unchanged (a team with a future at-bat can still kick and get the ball back).

The gate is `GameFormat.isLastScoringChance` (overridden on InningsFormat), folded
into `_fourthDownCaller`'s `lateHopeless`. The FG-vs-TD threshold uses the mutable
`_fgValue()` (not a hardcoded 3), so it tracks changed scoring rules.

Runs the REAL 4th-down caller over constructed innings situations.
Run: .venv/bin/python test_innings_endgame.py   (exits non-zero on any failure)
"""
import sys, types
sys.path.insert(0, '/Users/andrew/Projects/floosball')
_stub = types.ModuleType('floosball_game'); _stub.Game = type('G', (), {})
sys.modules['floosball_game'] = _stub
import managers.timingManager  # noqa: F401
del sys.modules['floosball_game']
from scenario import Scenario, PlayType
from game_rules import GameRules

failures = []
def expect(desc, cond):
    print(f"  [{'OK' if cond else 'FAIL'}] {desc}")
    if not cond:
        failures.append(desc)


def _rules(fieldGoalPoints=3, touchdownPoints=6, inningsPerGame=3, triesPerInning=3):
    gr = GameRules()
    gr.gameFormat = 'innings'
    gr.inningsPerGame = inningsPerGame
    gr.triesPerInning = triesPerInning
    gr.fieldGoalPoints = fieldGoalPoints
    gr.touchdownPoints = touchdownPoints
    return gr


def fgRate(*, inning, half, tries, offense, offScore, defScore,
           ballOn=15, down=4, dist=8, trials=15, **ruleKw):
    """Fraction of trials the REAL 4th-down caller picks a FIELD GOAL in the given
    innings situation (a makeable kick from ballOn=15)."""
    s = Scenario(gameRules=_rules(**ruleKw))
    s.setKickerLeg('home', 60); s.setKickerLeg('away', 60)   # solid leg → 15 is in range
    hits = 0
    for _ in range(trials):
        s.situation(quarter=1, clock=900, offense=offense, offScore=offScore,
                    defScore=defScore, down=down, distance=dist, ballOn=ballOn)
        g = s.g
        g._inningsNumber = inning; g._inningsHalf = half; g._inningsTries = tries
        if s.fourthDownPlay() is PlayType.FieldGoal:
            hits += 1
    return hits / trials


# ── 1. Last try of the last inning — the reported bug ────────────────────
print("1. Last try (tries=2 of 3) of the LAST inning: FG only if it ties/wins")
# TOP of last inning = away batting; BOTTOM = home batting. Both are last chances.
for half, off in (('top', 'away'), ('bottom', 'home')):
    r6 = fgRate(inning=3, half=half, tries=2, offense=off, offScore=0, defScore=6)
    r4 = fgRate(inning=3, half=half, tries=2, offense=off, offScore=0, defScore=4)
    r3 = fgRate(inning=3, half=half, tries=2, offense=off, offScore=0, defScore=3)
    r2 = fgRate(inning=3, half=half, tries=2, offense=off, offScore=0, defScore=2)
    tied = fgRate(inning=3, half=half, tries=2, offense=off, offScore=7, defScore=7)
    expect(f"{half}: down 6 (>FG) → NEVER kicks, goes for TD (rate {r6:.2f})", r6 == 0.0)
    expect(f"{half}: down 4 (>FG) → NEVER kicks (rate {r4:.2f})", r4 == 0.0)
    expect(f"{half}: down 3 (=FG) → ALWAYS kicks to tie (rate {r3:.2f})", r3 == 1.0)
    expect(f"{half}: down 2 (<FG) → ALWAYS kicks (rate {r2:.2f})", r2 == 1.0)
    expect(f"{half}: tied → ALWAYS kicks to take the lead (rate {tied:.2f})", tied == 1.0)


# ── 2. Not the last chance → unchanged (can still kick, has a future at-bat) ──
print("2. A future at-bat exists → down 6 still kicks (unchanged)")
expect("non-last try (tries=0), last inning, down 6 → kicks (rate 1.0)",
       fgRate(inning=3, half='top', tries=0, offense='away', offScore=0, defScore=6) == 1.0)
expect("last try but EARLIER inning (inning 1), down 6 → kicks (rate 1.0)",
       fgRate(inning=1, half='top', tries=2, offense='away', offScore=0, defScore=6) == 1.0)


# ── 3. Extra innings — every last try is a must-score ────────────────────
print("3. Extra innings (inning 4 > inningsPerGame): last try, down 6 → goes for TD")
expect("extra-inning last try, down 6 → never kicks (rate 0.0)",
       fgRate(inning=4, half='bottom', tries=2, offense='home', offScore=0, defScore=6) == 0.0)


# ── 4. Mutable scoring — threshold tracks _fgValue(), not a hardcoded 3 ───
print("4. Mutated FG value (FG=4): the kick/go boundary shifts with it")
# FG=4: down 4 now TIES with a kick → kick; down 5 (>FG) → go for it.
expect("FG=4, last try, down 4 (=FG) → kicks (rate 1.0)",
       fgRate(inning=3, half='top', tries=2, offense='away', offScore=0, defScore=4,
              fieldGoalPoints=4) == 1.0)
expect("FG=4, last try, down 5 (>FG) → goes for TD (rate 0.0)",
       fgRate(inning=3, half='top', tries=2, offense='away', offScore=0, defScore=5,
              fieldGoalPoints=4) == 0.0)


# ── 5. Displayed inning — the end-of-game counter leak stays off the board ─
print("5. displayInning: a regulation finish never reads as an extra inning")
import game_formats as _GFMT
from types import SimpleNamespace as _NS
_fmt = _GFMT.InningsFormat()
def _state(num, half, tries, home, away, innings=3):
    return _NS(_inningsNumber=num, _inningsHalf=half, _inningsTries=tries,
               homeScore=home, awayScore=away,
               gameRules=_NS(inningsPerGame=innings, triesPerInning=3))
# The flip that ends the final inning bumps the counter to N+1 (checkEarlyEnd reads that
# as "an inning completed"), so the raw value is 4 on a decided 3-inning game.
expect("regulation finish (counter leaked to 4) displays inning 3",
       _fmt.displayInning(_state(4, 'top', 0, 45, 41)) == 3)
# Extra innings are REAL — never clamp a game that's actually still playing.
expect("tied after 3 (heading to extras) displays inning 4",
       _fmt.displayInning(_state(4, 'top', 0, 41, 41)) == 4)
expect("mid extra inning (top 4, try in progress) displays inning 4",
       _fmt.displayInning(_state(4, 'top', 1, 41, 41)) == 4)
expect("walk-off during extra inning 4 displays inning 4",
       _fmt.displayInning(_state(4, 'bottom', 1, 44, 41)) == 4)
expect("extras finished (counter leaked to 5) displays inning 4",
       _fmt.displayInning(_state(5, 'top', 0, 48, 41)) == 4)
expect("a tie accepted at the extra-innings cap displays the last inning played",
       _fmt.displayInning(_state(9, 'top', 0, 41, 41)) == 8)
expect("mid-regulation inning is untouched", _fmt.displayInning(_state(2, 'top', 1, 10, 7)) == 2)

# The displayed HALF must describe the same at-bat as the displayed inning. Consumers ask
# "has the home team batted this inning yet?" (the line score's blank-vs-value gate); a
# clamped inning paired with the raw post-flip 'top' half hid the whole bottom of the
# final inning on any game that went the distance (walk-offs were unaffected — hence
# "sometimes the points show, sometimes they don't").
expect("regulation finish reports the BOTTOM of the last inning, not the top of the next",
       _fmt.displayHalf(_state(4, 'top', 0, 45, 41)) == 'bottom')
expect("extras finished likewise reports the bottom of the last inning played",
       _fmt.displayHalf(_state(5, 'top', 0, 48, 41)) == 'bottom')
expect("walk-off is already in the bottom half — untouched",
       _fmt.displayHalf(_state(3, 'bottom', 1, 44, 41)) == 'bottom')
expect("tied into extras is still genuinely the TOP of the new inning",
       _fmt.displayHalf(_state(4, 'top', 0, 41, 41)) == 'top')
expect("mid-regulation half is untouched", _fmt.displayHalf(_state(2, 'top', 1, 10, 7)) == 'top')


print()
if failures:
    print(f"FAILED: {len(failures)} check(s):")
    for f in failures:
        print("  -", f)
    raise SystemExit(1)
print("All innings-endgame 4th-down checks passed.")
