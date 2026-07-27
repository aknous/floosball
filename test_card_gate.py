"""Card gate — the FP power bar.

Fantasy/cards fusion (docs/CARD_ONCARD_REBASE_PLAN.md). Every effect-bearing card has a
power bar filled by the depicted player's weekly fantasy points:

  * normal cards: the bar FILLS with FP; the effect unlocks once it's full (player clears
    the position threshold). Pure on/off, no scaling above.
  * inverse / underdog cards: the bar runs in REVERSE — full at 0 FP, depleting as they
    score, the effect disabled once it empties.

One stat (FP), one threshold per position. Only the no-effect floor card is ungated.

Run: .venv/bin/python test_card_gate.py
"""
import sys
sys.path.insert(0, '/Users/andrew/Projects/floosball')
import logging; logging.disable(logging.CRITICAL)
from managers.cardEffects import (buildGateSpec, gateRatio, _applyGateRatio,
                                   EffectResult, buildEffectConfig)
from managers.cardEffectCalculator import CardCalcContext
from constants import CARD_GATE_FP_THRESHOLDS

failures = []
def expect(desc, cond):
    print(f"  [{'OK' if cond else 'FAIL'}] {desc}")
    if not cond:
        failures.append(desc)

WR = 3
WR_THR = CARD_GATE_FP_THRESHOLDS[WR]   # 8


def ctxFP(pid, fp):
    c = CardCalcContext()
    c.rosterPlayerIds = {pid}
    c.rosterPlayerPositions = {pid: WR}
    c.weekPlayerStats = {pid: {"fantasyPoints": fp}}
    return c


print("1. Every effect-bearing card gets an FP bar; only the floor card is ungated")
g = buildGateSpec("freebie", WR)
expect(f"a value effect gets a bar at the WR threshold  {g}",
       g and g['threshold'] == WR_THR)
expect("a cross / hand-modifier effect gets a bar too (uniform)",
       buildGateSpec("copycat", 1) is not None)
expect("a re-based / on-card effect gets a bar too",
       buildGateSpec("possession", WR) is not None and buildGateSpec("piggy_bank", WR) is not None)
expect("the no-effect floor card gets no gate", buildGateSpec("none", WR) is None)
# CHANCE cards are exempt from the on/off gate — their bar is a probability meter instead
# (fill = trigger odds), so buildGateSpec returns None (fusion chance rework 2026-07-26).
expect("a chance card (scrappy) is gate-exempt", buildGateSpec("scrappy", WR) is None)
expect("a chance card (crescendo) is gate-exempt", buildGateSpec("crescendo", 1) is None)

print("2. gateRatio — pure on/off, no scaling")
gate = buildGateSpec("freebie", WR)
expect(f"below {WR_THR} FP -> 0 (bar not full, effect off)", gateRatio(gate, ctxFP(1, WR_THR - 1), 1) == 0.0)
expect("0 FP -> 0", gateRatio(gate, ctxFP(1, 0), 1) == 0.0)
expect(f"at {WR_THR} FP -> 1.0 (unlocked)", gateRatio(gate, ctxFP(1, WR_THR), 1) == 1.0)
expect("well above -> still exactly 1.0 (no overflow)", gateRatio(gate, ctxFP(1, WR_THR * 5), 1) == 1.0)

print("3. Underperformance effects are UNGATED (no bar); inverse gate retired")
# Effects whose trigger IS low scoring get no power bar — gating them on the player
# showing up would fight the effect (owner call 2026-07-25/26).
expect("hedge is ungated (tops up the player's OWN low FP)", buildGateSpec("hedge", WR) is None)
expect("snake_eyes is ungated (pays more the worse the game)", buildGateSpec("snake_eyes", WR) is None)
expect("buy_low is ungated (rewards roster underperformance)", buildGateSpec("buy_low", WR) is None)
# No effect runs the bar in reverse anymore; the inverse gate is retired.
expect("a normal effect is NOT inverse", buildGateSpec("freebie", WR).get("inverse") is False)

print("3b. _applyGateRatio — on/off only")
r = _applyGateRatio(EffectResult(fpBonus=10.0), 0.0)
expect("off zeroes the effect", r.fpBonus == 0.0)
r = _applyGateRatio(EffectResult(fpBonus=10.0), 1.0)
expect("on leaves it untouched (no scaling)", r.fpBonus == 10.0)
r = _applyGateRatio(EffectResult(multBonus=2.0), 0.0)
expect("off resets an FPx factor to 1.0", r.multBonus == 1.0)

print("4. Thresholds are position-tuned")
expect(f"QB {CARD_GATE_FP_THRESHOLDS[1]} / RB {CARD_GATE_FP_THRESHOLDS[2]} / "
       f"TE {CARD_GATE_FP_THRESHOLDS[4]} differ by position",
       len(set(CARD_GATE_FP_THRESHOLDS.values())) > 1)

print("4b. Thresholds RISE with edition (higher rarity depicts a better player + higher ceiling)")
wrThr = [buildGateSpec("freebie", WR, edition=e)["threshold"]
         for e in ("metallic", "holographic", "prismatic", "diamond")]
expect(f"WR bar climbs by edition: {wrThr}", wrThr == sorted(wrThr) and wrThr[0] < wrThr[-1])
expect("no edition -> metallic base fallback",
       buildGateSpec("freebie", WR)["threshold"] == buildGateSpec("freebie", WR, edition="metallic")["threshold"])

print("5. Minted templates carry the gate + power-bar text")
cfg = buildEffectConfig('metallic', 80, WR, forceEffect='freebie')
expect(f"minted card has a gate  {cfg.get('gate')}", cfg.get('gate', {}).get('threshold') == WR_THR)
expect(f"and gateText  {cfg.get('gateText')}", 'Unlocks' in (cfg.get('gateText') or ''))
floor = buildEffectConfig('base', 80, WR)
expect("the no-effect floor card has no gate", 'gate' not in floor)

print()
if failures:
    print(f">>> {len(failures)} FAILURE(S)")
    for f in failures:
        print("   -", f)
    sys.exit(1)
print("PASS — the FP power bar switches every card on/off; inverse cards run in reverse.")
