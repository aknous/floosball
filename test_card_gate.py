"""Card gate: a card's output scales with how well its depicted player played.

Fantasy/cards fusion (docs/CARD_ONCARD_REBASE_PLAN.md). An equipped card's output is
tied to the DEPICTED PLAYER's week — a linear ramp on one of their stats, capped at 1.0,
so a full hand can't score off a bench-warming roster:

  * VALUE effects (FP / FPx / floobits): output * min(1, stat/threshold).
    +1 FPx card, 100-yd threshold, player gains 50 yds -> +0.5 FPx.
  * CROSS / hand-modifier effects (copycat, doubler, …): all-or-nothing, since "60% of a
    2x multiplier" is meaningless — fires only if the player clears the threshold.
  * EXEMPT effects (already scale with the card player's own stat) get no gate.

Run: .venv/bin/python test_card_gate.py
"""
import sys
sys.path.insert(0, '/Users/andrew/Projects/floosball')
import logging; logging.disable(logging.CRITICAL)
from managers.cardEffects import (buildGateSpec, gateRatio, _applyGateRatio,
                                   EffectResult, buildEffectConfig)
from managers.cardEffectCalculator import CardCalcContext

failures = []
def expect(desc, cond):
    print(f"  [{'OK' if cond else 'FAIL'}] {desc}")
    if not cond:
        failures.append(desc)


# WR threshold is 100 rec yards (constants.CARD_GATE_THRESHOLDS[3]).
def ctxWith(pid, recYards):
    c = CardCalcContext()
    c.rosterPlayerIds = {pid}
    c.rosterPlayerPositions = {pid: 3}
    c.weekPlayerStats = {pid: {"receiving_stats": {"rcvYards": recYards}}}
    return c


print("1. buildGateSpec — value vs cross vs exempt")
g = buildGateSpec("freebie", 3)          # a flat-FP WR effect
expect(f"a value effect gets a ramp gate from the WR menu  {g}",
       g and g['mode'] == 'ramp' and g['stat'] in ('rcvYards', 'receptions', 'yac'))
g = buildGateSpec("copycat", 3)          # a cross / hand modifier
expect(f"a cross effect gets a HARD gate  {g}", g and g['mode'] == 'hard')
expect("an exempt (already-on-card) effect gets no gate",
       buildGateSpec("possession", 3) is None)
expect("the no-effect floor card gets no gate", buildGateSpec("none", 3) is None)

# An explicit rec-yards ramp gate (threshold 100), so the ratio math is deterministic
# regardless of which stat a random mint would have rolled.
GATE_RECYDS = {'mode': 'ramp', 'group': 'receiving_stats', 'stat': 'rcvYards',
               'threshold': 100, 'label': 'rec yds'}
GATE_HARD = {'mode': 'hard', 'group': 'receiving_stats', 'stat': 'rcvYards',
             'threshold': 100, 'label': 'rec yds'}

print("2. gateRatio — linear ramp on the value effect")
gate = GATE_RECYDS
expect("100 of 100 yds -> full (1.0)", gateRatio(gate, ctxWith(1, 100), 1) == 1.0)
expect("150 of 100 yds -> capped at 1.0", gateRatio(gate, ctxWith(1, 150), 1) == 1.0)
r = gateRatio(gate, ctxWith(1, 50), 1)
expect(f"50 of 100 yds -> 0.5  (got {r})", abs(r - 0.5) < 1e-9)
r = gateRatio(gate, ctxWith(1, 20), 1)
expect(f"20 of 100 yds -> 0.2  (got {r})", abs(r - 0.2) < 1e-9)
expect("0 yds -> 0.0 (card pays nothing)", gateRatio(gate, ctxWith(1, 0), 1) == 0.0)

print("3. gateRatio — hard gate snaps to 0 or 1")
hg = GATE_HARD
expect("99 of 100 -> 0 (didn't clear)", gateRatio(hg, ctxWith(1, 99), 1) == 0.0)
expect("100 of 100 -> 1 (cleared)", gateRatio(hg, ctxWith(1, 100), 1) == 1.0)
expect("50 of 100 -> 0 (no partial for a hand modifier)",
       gateRatio(hg, ctxWith(1, 50), 1) == 0.0)

print("4. _applyGateRatio — FP, FPx and floobits all scale (the +1 FPx example)")
r = _applyGateRatio(EffectResult(fpBonus=10.0), 0.5)
expect(f"+10 FP at 0.5 -> +5 FP (got {r.fpBonus})", r.fpBonus == 5.0)
r = _applyGateRatio(EffectResult(floobits=20), 0.5)
expect(f"+20 floobits at 0.5 -> +10 (got {r.floobits})", r.floobits == 10)
# multBonus is the FACTOR: +1 FPx = factor 2.0. At 0.5 -> +0.5 FPx = factor 1.5.
r = _applyGateRatio(EffectResult(multBonus=2.0), 0.5)
expect(f"+1 FPx (x2.0) at 0.5 -> +0.5 FPx (x1.5)  (got x{r.multBonus})", r.multBonus == 1.5)
r = _applyGateRatio(EffectResult(fpBonus=10.0), 1.0)
expect("ratio 1.0 leaves output untouched", r.fpBonus == 10.0)
# a full-miss zeroes a value card but must not turn an unset mult into a penalty
r = _applyGateRatio(EffectResult(fpBonus=8.0, multBonus=0.0), 0.0)
expect("0.0 zeroes FP", r.fpBonus == 0.0)
expect("0.0 leaves an unset mult (0.0) alone, not a penalty", r.multBonus == 0.0)

print("5. Minted templates actually carry the gate")
cfgVal = buildEffectConfig('base', 80, 3, forceEffect='freebie')
expect(f"minted value card carries a ramp gate  {cfgVal.get('gate')}",
       cfgVal.get('gate', {}).get('mode') == 'ramp')
cfgExempt = buildEffectConfig('base', 3, 3, forceEffect='possession')
expect("minted exempt card carries no gate", 'gate' not in cfgExempt)

print("6. The gate STAT varies across mints (diversity)")
seen = {buildGateSpec("freebie", 3)['stat'] for _ in range(60)}
expect(f"WR value cards roll a variety of gate stats  {seen}", len(seen) >= 2)
seenQb = {buildGateSpec("freebie", 1)['stat'] for _ in range(60)}
expect(f"QB cards can gate on completions/attempts too  {seenQb}",
       {'comp', 'att'} & seenQb)

print()
if failures:
    print(f">>> {len(failures)} FAILURE(S)")
    for f in failures:
        print("   -", f)
    sys.exit(1)
print("PASS — card output scales with the depicted player; value ramps, cross hard-gates.")
