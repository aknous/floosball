"""Sideline Goals play-calling regression suite (built on scenario.Scenario).

Locks in the down/score-aware hoop-shot decision (floosball_game
_shouldAttemptHoopShot / _hoopPointsNeeded / _hoopScoreWinsNow):
  - a hoop shot consumes the down with no yardage, so NEVER on the final down and
    normally NOT on the penultimate down either;
  - late and trailing/tied, when a hoop point bridges a FG/TD to a tie/lead, the
    offense reliably banks both hoops (a 'critical' need overrides the penultimate
    down + hurry-up guards; OT sudden-death ties are 'critical');
  - all bands derive from _fgValue()/_maxPossession(), so they track MUTATED FG/TD
    point values (nothing hardcoded to 3/6).

Runs the REAL engine decisions over constructed situations (STANDARD format, the
mechanic switched on) — no waiting for a rare occurrence in a random sim.

Run: .venv/bin/python test_sideline_goals.py   (exits non-zero on any failure)
"""
import random
import numpy as np
from scenario import Scenario, PlayType
from random_batch import clear_all_batch_caches
from game_rules import GameRules


def reseed(s=0):
    random.seed(s); np.random.seed(s); clear_all_batch_caches()


failures = []
def expect(desc, cond):
    print(f"  [{'OK' if cond else 'FAIL'}] {desc}")
    if not cond:
        failures.append(desc)


def rulesOn(fieldGoalPoints=3, touchdownPoints=6):
    gr = GameRules()
    gr.sidelineGoalsEnabled = True
    gr.sidelineGoalPoints = 1
    gr.fieldGoalPoints = fieldGoalPoints
    gr.touchdownPoints = touchdownPoints
    return gr


def newScenario(**ruleKw):
    return Scenario(gameRules=rulesOn(**ruleKw))


def attemptRate(s, trials=300, *, ballOn=12, usedPairs=None, **situation):
    """Fraction of trials where the REAL _shouldAttemptHoopShot() fires, with a
    fresh in-range pair (ballOn=12 → the red-zone/end-zone pair). isOvertime is set
    from the quarter so OT scenarios exercise the sudden-death path."""
    hits = 0
    for _ in range(trials):
        s.situation(ballOn=ballOn, **situation)
        s.g._hoopPairResult = dict(usedPairs) if usedPairs else None
        s.g.isOvertime = situation.get('quarter', 4) >= 5
        if s.g._shouldAttemptHoopShot():
            hits += 1
    return hits / trials


# ── 1. _hoopPointsNeeded bands, default scoring (fg=3, maxPoss=8) ─────────
print("1. _hoopPointsNeeded bands at DEFAULT scoring (FG=3, TD=6 → maxPoss 8)")
s = newScenario()
def need(deficit, used=None):
    s.g._hoopPairResult = dict(used) if used else None
    return s.g._hoopPointsNeeded(-deficit)
expect("deficit 2 → None (a FG alone ties/wins)", need(2) is None)
expect("deficit 4 → helpful (FG+hoop ties; a TD alone would win)", need(4) == 'helpful')
expect("deficit 5 → helpful (FG+2 hoops ties)", need(5) == 'helpful')
expect("deficit 8 → None (a TD+2pt alone ties)", need(8) is None)
expect("deficit 9 → critical (no conventional score alone reaches; TD+hoop does)", need(9) == 'critical')
expect("deficit 10 → critical (TD+2pt+2 hoops ties)", need(10) == 'critical')
expect("deficit 11 → None (unreachable this drive)", need(11) is None)
expect("deficit 9 with one pair already used → critical (TD+2pt+1 hoop = 9 ties)",
       need(9, used={'midfield': 'made'}) == 'critical')
expect("deficit 10 with one pair already used → None (only 1 hoop left, TD+2pt+1 = 9 < 10)",
       need(10, used={'midfield': 'made'}) is None)
expect("tied (deficit 0), regulation → helpful (go-ahead point)", need(0) == 'helpful')


# ── 2. Mutated scoring shifts the bands (values are NOT hardcoded) ────────
print("2. Mutated scoring (FG=4, TD=8 → maxPoss 10) shifts the bands")
s4 = newScenario(fieldGoalPoints=4, touchdownPoints=8)
def need4(deficit):
    s4.g._hoopPairResult = None
    return s4.g._hoopPointsNeeded(-deficit)
expect("deficit 4 → None (a FG=4 alone ties)", need4(4) is None)
expect("deficit 6 → helpful (FG=4 + 2 hoops ties; was None at default rules)", need4(6) == 'helpful')
expect("deficit 10 → None (TD+2pt=10 alone ties)", need4(10) is None)
expect("deficit 11 → critical (shifted up from 9 at default rules)", need4(11) == 'critical')


# ── 3. Down guards in NORMAL play (not late) ─────────────────────────────
print("3. Normal play (Q2, tied-ish): shoots on early downs, never on 3rd/4th")
s = newScenario(); reseed(1)
r1 = attemptRate(s, quarter=2, clock=600, down=1, offScore=10, defScore=12)   # deficit 2 → None
r2 = attemptRate(s, quarter=2, clock=600, down=2, offScore=10, defScore=12)
r3 = attemptRate(s, quarter=2, clock=600, down=3, offScore=10, defScore=12)
r4 = attemptRate(s, quarter=2, clock=600, down=4, offScore=10, defScore=12)
expect(f"1st down in range → attempts sometimes (rate {r1:.2f} in 0.3–0.8)", 0.3 < r1 < 0.85)
expect(f"2nd down in range → attempts (rate {r2:.2f} > 0.3)", r2 > 0.3)
expect(f"3rd (penultimate) down → NEVER in normal play (rate {r3:.2f} == 0)", r3 == 0.0)
expect(f"4th (final) down → NEVER (rate {r4:.2f} == 0)", r4 == 0.0)


# ── 4. Late + trailing: reliable, critical overrides the 3rd-down guard ───
print("4. Late Q4, trailing: deficit-aware banking")
s = newScenario(); reseed(2)
# clock=100 (1:40) while trailing is hurry-up; a 'critical' need overrides it, a
# 'helpful' one does not, so the helpful cases use a late-but-not-hurry-up clock (250s).
hCrit1 = attemptRate(s, quarter=4, clock=100, down=1, offScore=0, defScore=9)   # critical (also hurry-up)
hCrit3 = attemptRate(s, quarter=4, clock=100, down=3, offScore=0, defScore=9)   # critical → override
hHelp1 = attemptRate(s, quarter=4, clock=250, down=1, offScore=0, defScore=4)   # helpful, late, not hurry-up
hHelp3 = attemptRate(s, quarter=4, clock=250, down=3, offScore=0, defScore=4)   # helpful → NO penultimate override
hCrit4 = attemptRate(s, quarter=4, clock=100, down=4, offScore=0, defScore=9)   # final down always blocked
expect(f"critical, 1st down → reliable, overrides hurry-up (rate {hCrit1:.2f} > 0.8)", hCrit1 > 0.8)
expect(f"critical, 3rd down → fires anyway, guard lifted (rate {hCrit3:.2f} > 0.8)", hCrit3 > 0.8)
expect(f"helpful, 1st down (late, not hurry-up) → reliable (rate {hHelp1:.2f} > 0.8)", hHelp1 > 0.8)
expect(f"helpful, 3rd down → still blocked (rate {hHelp3:.2f} == 0)", hHelp3 == 0.0)
expect(f"critical, 4th (final) down → still blocked (rate {hCrit4:.2f} == 0)", hCrit4 == 0.0)


# ── 5. OT sudden-death ties: a hoop point wins → mandatory ───────────────
print("5. OT tie-break")
s = newScenario(); reseed(3)
# 2nd+ OT is pure sudden death: an offensive score wins now → 'critical'.
otSd1 = attemptRate(s, quarter=5, clock=300, down=1, offScore=7, defScore=7, otPeriod=2)
otSd3 = attemptRate(s, quarter=5, clock=300, down=3, offScore=7, defScore=7, otPeriod=2)
otSd4 = attemptRate(s, quarter=5, clock=300, down=4, offScore=7, defScore=7, otPeriod=2)
# 1st OT before both guaranteed possessions: go-ahead point doesn't end it → 'helpful'.
ot1st1 = attemptRate(s, quarter=5, clock=300, down=1, offScore=7, defScore=7,
                     otPeriod=1, otSecondPossComplete=False)
ot1st3 = attemptRate(s, quarter=5, clock=300, down=3, offScore=7, defScore=7,
                     otPeriod=1, otSecondPossComplete=False)
expect(f"2nd-OT tie, 1st down → wins outright, reliable (rate {otSd1:.2f} > 0.8)", otSd1 > 0.8)
expect(f"2nd-OT tie, 3rd down → critical override (rate {otSd3:.2f} > 0.8)", otSd3 > 0.8)
expect(f"2nd-OT tie, 4th (final) down → still blocked, kick the winner (rate {otSd4:.2f} == 0)", otSd4 == 0.0)
expect(f"1st-OT tie (pre-both-poss), 1st down → reliable (rate {ot1st1:.2f} > 0.8)", ot1st1 > 0.8)
expect(f"1st-OT tie, 3rd down → not game-ending, guard holds (rate {ot1st3:.2f} == 0)", ot1st3 == 0.0)


# ── 6. A regulation tie is only boosted when LATE ────────────────────────
print("6. Regulation tie: boosted only late, and hurry-up is respected")
s = newScenario(); reseed(4)
tieEarly1 = attemptRate(s, quarter=2, clock=600, down=1, offScore=14, defScore=14)  # helpful but not late
tieLate1 = attemptRate(s, quarter=4, clock=200, down=1, offScore=14, defScore=14)   # helpful + late
tieHurry1 = attemptRate(s, quarter=4, clock=90, down=1, offScore=14, defScore=14)   # hurry-up → blocked
expect(f"tied, Q2 (not late) → normal chance, not boosted (rate {tieEarly1:.2f} in 0.3–0.8)",
       0.3 < tieEarly1 < 0.85)
expect(f"tied, Q4 late → reliable (rate {tieLate1:.2f} > 0.8)", tieLate1 > 0.8)
expect(f"tied, Q4 hurry-up (≤2:30) → helpful does not override hurry-up (rate {tieHurry1:.2f} == 0)",
       tieHurry1 == 0.0)


# ── 7. Full-caller integration: a hoop actually fires end-to-end ─────────
print("7. Full playCaller integration (late critical) fires a real hoop shot")
s = newScenario(); reseed(5)
hoopFired = 0
for _ in range(120):
    s.situation(quarter=4, clock=100, down=1, offScore=0, defScore=9, ballOn=12)
    s.g._hoopPairResult = None
    s.g.playCaller()
    if getattr(s.g.play, 'isHoopShot', False):
        hoopFired += 1
expect(f"playCaller routes to a hoop shot in a late-critical spot ({hoopFired}/120 > 40)", hoopFired > 40)


print()
if failures:
    print(f"FAILED: {len(failures)} check(s):")
    for f in failures:
        print("  -", f)
    raise SystemExit(1)
print("All sideline-goal play-calling checks passed.")
