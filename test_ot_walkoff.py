"""Constructed-scenario regression test: defensive scores in overtime.

These OT situations (a fumble/INT returned for a TD, or a safety, during OT)
are far too rare to hit reliably in a fast sim — ~0 occurrences in 850 games.
So instead of relying on chance, we CONSTRUCT the exact game state and drive
the real decision methods (`checkOvertimeEnd` + `isGameOver`) over it.

The bug being guarded against: a defensive/return TD in OT did not end the
game. `checkOvertimeEnd` was returning False on a scoop-and-score (its 1st-OT
path needed `otSecondPossComplete`, only set in `turnover()` which runs AFTER
the OT-end check), and even once that was fixed, `isGameOver` — which gates on
`otSecondPossComplete` and does NOT call `checkOvertimeEnd` — still returned
False, so the game continued into a bogus extra possession.

Run: .venv/bin/python test_ot_walkoff.py   (exits non-zero on any failure)
"""
import sys, os, types
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Break the floosball_game <-> managers circular import (same trick the other
# headless tests use): register a stub so seasonManager's annotations resolve,
# then load the real module once managers is cached.
_stub = types.ModuleType('floosball_game')
class _GameStub: pass
_stub.Game = _GameStub
sys.modules['floosball_game'] = _stub
import managers.timingManager  # noqa: F401  (caches managers using the stub)
del sys.modules['floosball_game']
import floosball_game as FG  # real load

checkOvertimeEnd = FG.Game.checkOvertimeEnd
isGameOver = FG.Game.isGameOver


def makeOtState(*, quarter=5, otPeriod=1, home=20, away=14,
                otFirstPossComplete=True, otSecondPossComplete=False,
                clock=240):
    """A Game-shaped namespace carrying only what the two methods read."""
    return types.SimpleNamespace(
        status=None,                      # not Final
        currentQuarter=quarter,
        gameClockSeconds=clock,
        homeScore=home, awayScore=away,
        otPeriod=otPeriod,
        otFirstPossComplete=otFirstPossComplete,
        otSecondPossComplete=otSecondPossComplete,
    )


failures = []
def check(desc, got, expect):
    ok = got == expect
    print(f"  [{'OK' if ok else 'FAIL'}] {desc}: got={got} expect={expect}")
    if not ok:
        failures.append(desc)


print("Scenario 1 — the reported bug: 1st OT, DEFENSE just returned a fumble for")
print("a TD (home leads 20-14), second-possession flag not yet set, clock running.")
st = makeOtState(home=20, away=14, otSecondPossComplete=False, clock=240)
# (a) Pre-fix reality: isGameOver alone would NOT end the game -> the bug.
check("isGameOver BEFORE the walk-off flag is set (the old bug)", isGameOver(st), False)
# (b) checkOvertimeEnd flags it as a walk-off...
check("checkOvertimeEnd(defensiveScore=True) detects the walk-off", checkOvertimeEnd(st, defensiveScore=True), True)
# (c) ...and the fix sets otSecondPossComplete=True, so isGameOver now ends it.
st.otSecondPossComplete = True
check("isGameOver AFTER the fix sets the flag (game ends)", isGameOver(st), True)

print("\nScenario 2 — first-possession defensive TD also walks off (1st OT, the team")
print("that had the ball first fumbled it back for a TD).")
st = makeOtState(home=14, away=20, otFirstPossComplete=False, otSecondPossComplete=False, clock=300)
check("checkOvertimeEnd(defensiveScore=True) -> walk-off", checkOvertimeEnd(st, defensiveScore=True), True)
st.otSecondPossComplete = True
check("isGameOver -> ends", isGameOver(st), True)

print("\nScenario 3 — regression: an OFFENSIVE score in 1st OT still obeys the")
print("both-possessions rule (does NOT end early).")
st = makeOtState(home=20, away=14, otSecondPossComplete=False)
check("offensive score, 2nd poss NOT done -> keep playing", checkOvertimeEnd(st, defensiveScore=False), False)
check("isGameOver -> keep playing", isGameOver(st), False)
st.otSecondPossComplete = True
check("offensive score, both poss done -> ends", checkOvertimeEnd(st, defensiveScore=False), True)
check("isGameOver -> ends", isGameOver(st), True)

print("\nScenario 4 — a safety that TIES the game must NOT end it.")
st = makeOtState(home=20, away=20, otSecondPossComplete=False)
check("tied defensive score -> not a walk-off", checkOvertimeEnd(st, defensiveScore=True), False)
check("isGameOver -> keep playing (tied)", isGameOver(st), False)

print("\nScenario 5 — 2nd+ OT is sudden death: any score ends it immediately.")
st = makeOtState(quarter=6, otPeriod=2, home=23, away=20, otSecondPossComplete=False)
check("sudden death, offensive score -> ends", checkOvertimeEnd(st, defensiveScore=False), True)

print("\nScenario 6 — not OT (regulation Q4 tied at the gun) is unaffected.")
st = makeOtState(quarter=4, home=20, away=14, clock=0)
check("defensive score flag in Q4 -> checkOvertimeEnd False", checkOvertimeEnd(st, defensiveScore=True), False)

print()
if failures:
    print(f"FAILED ({len(failures)}): " + "; ".join(failures))
    sys.exit(1)
print("ALL SCENARIOS PASS")
