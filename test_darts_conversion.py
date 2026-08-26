"""Darts conversions: land the dart, or bank the points — and who decides.

In darts a post-TD rung that scores EXACTLY the remainder wins the game outright, and one
that overshoots banks nothing at all. The standard conversion policy cannot see either
half: it measures a try against the OPPONENT'S score, not against the target.

Two things this file pins, and they fail in opposite directions.

⚠️ NOTHING MAY BUST. A busting try is never worth attempting — it leaves the team exactly
where the touchdown left it. This matters most with the Conversion Ladder ON, because
enabling the ladder REMOVES THE SAFE KICK (the ladder is defined as go-for-it football).
At a need of 1 every go-rung overshoots, so the kick is the only scoring play left AND it
wins the game; `_chooseDartsConversion` reaches past the fallback to pull it out of
`_conversionRungs()` for exactly that case.

⚠️ THE RUNG THAT WINS IS ALWAYS THE LEAST LIKELY ONE, so taking it is a real decision and
not a rule. Landing requires scoring exactly the remainder, so the landing rung is the
longest try still legal — measured at the shipped distances, a need of 5 is a 0.34 shot at
ending the game against a 0.70 shot at merely reaching a need of 3. A failed try costs
nothing either way (the touchdown is banked before it), so this is not risk aversion, and
neither line is strictly better. Owner, 2026-08-26: "an aggressive coach would go for the
higher score to win, conservative will bank easy points."

Run: .venv/bin/python test_darts_conversion.py   (exits non-zero on any failure)
"""
import sys, os, random, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import logging; logging.disable(logging.WARNING)

from scenario import Scenario
from game_rules import GameRules
from constants import GAME_FORMAT_PRESETS, COACH_ATTR_NEUTRAL

fails = []
def expect(d, c):
    print(f"  [{'OK' if c else 'FAIL'}] {d}")
    if not c: fails.append(d)

DARTS = next(p for p in GAME_FORMAT_PRESETS if 'Darts' in (p.get('label') or ''))

def rules(ladder):
    gr = GameRules()
    for k, v in DARTS['patch'].items():
        setattr(gr, k, v)
    gr.conversionLadderEnabled = ladder
    return gr

def picks(ladder, mine, aggr, n=120):
    """What the chooser takes, `n` times, from a score of `mine` after the TD."""
    gr = rules(ladder)
    s = Scenario(gameRules=gr)
    out = collections.Counter()
    for i in range(n):
        random.seed(i)
        s.situation(quarter=4, clock=400, offense='home', offScore=mine,
                    defScore=mine - 1, down=1, distance=10, ballOn=3)
        s.game.homeTeam.coach.aggressiveness = aggr
        out[s.game._chooseConversion(s.game.homeTeam)['points']] += 1
    return out, int(getattr(gr, 'targetScore', 24))

# ── 1. nothing busts, with the ladder either way ────────────────────────────
print("\n-- no conversion may overshoot the target --")
for ladder in (False, True):
    busts = []
    for aggr in (60, 80, 100):
        for mine in range(14, 24):
            got, T = picks(ladder, mine, aggr, n=40)
            for pts in got:
                if mine + pts > T:
                    busts.append((ladder, aggr, mine, pts))
    expect(f"ladder {'ON ' if ladder else 'off'}: no busting pick in any spot ({len(busts)})",
           not busts)

# ⚠️ The sharp one. With the ladder on the safe kick is gone, and at a need of 1 every
# go-rung busts — so the kick has to be recovered or the team cannot score at all.
print("\n-- at a need of 1 the kick wins, and the ladder must not remove it --")
for ladder in (False, True):
    got, T = picks(ladder, 23, 80)
    expect(f"ladder {'ON ' if ladder else 'off'}: takes the 1-pt kick to land on {T} "
           f"({dict(got)})", set(got) == {1})

# ── 2. the coach decides when there IS a trade-off ──────────────────────────
print("\n-- an aggressive coach takes the dart, a conservative one banks --")
T = 24
for need in (3, 4, 5):
    mine = T - need
    aggro, _ = picks(True, mine, 100)
    cons, _ = picks(True, mine, 60)
    expect(f"need {need}: aggressive wins it outright ({dict(aggro)})",
           set(aggro) == {need})
    expect(f"need {need}: conservative banks a shorter rung instead ({dict(cons)})",
           need not in cons)

# ⚠️ Need 2 has NO trade-off — the 2-pointer both lands and is the safest rung — so the
# coach must never be consulted, and every coach takes the win. A version of this that
# asked the coach anyway would have a conservative team decline a free game-winner.
print("\n-- and is never consulted when there is no trade-off --")
for aggr, label in ((60, 'conservative'), (80, 'neutral'), (100, 'aggressive')):
    got, _ = picks(True, T - 2, aggr)
    expect(f"need 2: {label} takes the 2-pt that wins ({dict(got)})", set(got) == {2})

# ── 3. the ladder is an improvement to darts, not a hazard ──────────────────
# ⚠️ Without it, needs 3/4/5 can only kick for 1 and stay short. This is the reason the
# interaction is worth having at all, so it is asserted rather than assumed.
print("\n-- the ladder gives darts more ways to land --")
landable = 0
for need in (2, 3, 4, 5):
    got, _ = picks(True, T - need, 100)
    if set(got) == {need}: landable += 1
expect(f"an aggressive team can land needs 2-5 off a touchdown ({landable} of 4)",
       landable == 4)
noLadder = sum(1 for need in (3, 4, 5) if set(picks(False, T - need, 100)[0]) == {need})
expect(f"and without the ladder none of needs 3-5 can be landed ({noLadder} of 3)",
       noLadder == 0)

# ── 4. non-darts formats are untouched ──────────────────────────────────────
# `_dartsBankInstead` is reachable only through `_chooseDartsConversion`, which is gated
# on `_dartsActive()`. Asserted directly so a future refactor cannot leak it.
print("\n-- standard football does not see any of this --")
gr = GameRules(); gr.conversionLadderEnabled = True
s = Scenario(gameRules=gr)
expect("darts is not active under the standard format", not s.game._dartsActive())

print()
if fails:
    print(f"FAIL — {len(fails)} problem(s):")
    for f in fails:
        print(f"  - {f}")
    sys.exit(1)
print("PASS — nothing busts, the kick survives the ladder, and the coach calls the gamble.")
