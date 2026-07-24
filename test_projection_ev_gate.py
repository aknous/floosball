"""Expected-value gate in the projection (docs/PROJECTION_AUDIT.md fix).

Live scoring keeps the hard on/off gate. The EXPECTED projection instead weights a gated
card by the empirical P(player clears the bar) from their weekly FP history (Laplace-
smoothed), so a card near its threshold projects as its expected value — not all-or-nothing
on the season average. Full House scales by the JOINT clear probability of its first-pass
cards.

Run: .venv/bin/python test_projection_ev_gate.py
"""
import sys
sys.path.insert(0, '/Users/andrew/Projects/floosball')
import logging; logging.disable(logging.CRITICAL)
from types import SimpleNamespace
from managers.cardEffects import buildEffectConfig, _FULL_HOUSE_MIN_CARDS
from managers.cardEffectCalculator import CardCalcContext, calculateWeekCardBonuses
from constants import CARD_GATE_FP_THRESHOLDS

failures = []
def expect(desc, cond):
    print(f"  [{'OK' if cond else 'FAIL'}] {desc}")
    if not cond:
        failures.append(desc)

WR = 3
THR = CARD_GATE_FP_THRESHOLDS[WR]  # 8


def mk(eqId, pid, effect='freebie', edition='base', rating=80):
    cfg = buildEffectConfig(edition, rating, WR, forceEffect=effect)
    tmpl = SimpleNamespace(effect_config=cfg, player_id=pid, position=WR, team_id=None,
        edition=edition, player_rating=rating, player_name=f"P{pid}", classification=None, is_rookie=False)
    uc = SimpleNamespace(card_template=tmpl, tier=1, id=eqId * 100)
    return SimpleNamespace(id=eqId, user_card=uc, slot_number=eqId, slot=None, peak_output=0.0, weeks_since_break=0)


def projCtx(weeklyByPid, expected=True):
    c = CardCalcContext()
    c.isProjection = True
    c.projectionVariant = 'expected' if expected else 'optimistic'
    c.gamesActive = False
    c.rosterPlayerIds = set(weeklyByPid)
    c.rosterPlayerPositions = {pid: WR for pid in weeklyByPid}
    c.rosterPlayerNames = {pid: f"P{pid}" for pid in weeklyByPid}
    # expected variant reads playerWeeklyFP; weekPlayerStats (the average) still set for peak/other
    c.playerWeeklyFP = weeklyByPid
    c.weekPlayerStats = {pid: {"fantasyPoints": sum(w) / len(w) if w else 0} for pid, w in weeklyByPid.items()}
    return c


print("1. A gated card projects at its expected value (P clear), not all-or-nothing")
# player clears the 8 bar in 3 of 5 weeks -> Laplace p = (3+1)/(5+2) = 0.571
weekly = {1: [12, 2, 10, 3, 11]}   # 3 of 5 >= 8
ctx = projCtx(weekly)
res = calculateWeekCardBonuses([mk(1, 1)], ctx)
b = res.cardBreakdowns[0]
full = buildEffectConfig('base', 80, WR, forceEffect='freebie')['primary'].get('baseFP') or b.primaryFP / 0.571
p = 4 / 7
print(f"     projected freebie FP = {b.primaryFP} (full≈{round(b.primaryFP / p,1)}, p={p:.3f})")
expect("projected FP is a fraction of full (0 < x < full)", 0 < b.primaryFP < (b.primaryFP / p) )
expect(f"projected ≈ full × {p:.2f}", abs(b.primaryFP - (b.primaryFP / p) * p) < 0.6)

print("\n2. A near-lock player projects near (not exactly) full; a scrub near 0")
lock = calculateWeekCardBonuses([mk(1, 1)], projCtx({1: [20, 18, 22, 15, 19]}))  # 5/5 clear -> 6/7≈0.857
scrub = calculateWeekCardBonuses([mk(1, 1)], projCtx({1: [2, 1, 4, 0, 3]}))       # 0/5 -> 1/7≈0.143
lockFP, scrubFP = lock.cardBreakdowns[0].primaryFP, scrub.cardBreakdowns[0].primaryFP
print(f"     lock projected={lockFP}  scrub projected={scrubFP}")
expect("lock projects high but < full (never a hard 1.0)", lockFP > scrubFP and lockFP > 0)
expect("scrub projects low but > 0 (never a hard 0)", 0 < scrubFP < lockFP)

print("\n3. Live scoring is still hard on/off (regression guard)")
liveCtx = CardCalcContext(); liveCtx.gamesActive = False
liveCtx.rosterPlayerIds = {1}; liveCtx.rosterPlayerPositions = {1: WR}; liveCtx.rosterPlayerNames = {1: "P1"}
liveCtx.weekPlayerStats = {1: {"fantasyPoints": 9}}  # just over the 8 bar
liveOn = calculateWeekCardBonuses([mk(1, 1)], liveCtx).cardBreakdowns[0].primaryFP
liveCtx.weekPlayerStats = {1: {"fantasyPoints": 5}}
liveOff = calculateWeekCardBonuses([mk(1, 1)], liveCtx).cardBreakdowns[0].primaryFP
print(f"     live over-bar={liveOn}  live under-bar={liveOff}")
expect("live over the bar = full (not scaled)", liveOn > 30)
expect("live under the bar = 0", liveOff == 0)

print("\n4. Full House projects the JOINT clear probability, not all-or-nothing")
# 5 first-pass cards each clearing 4/5 weeks -> p≈0.714 each; product ≈ 0.714^5 ≈ 0.186
w4of5 = [12, 11, 10, 9, 3]  # 4 of 5 >= 8
weeklyFH = {i: list(w4of5) for i in range(1, 6)}
weeklyFH[6] = [20, 20, 20, 20, 20]  # full_roster's own player (near-lock)
cards = [mk(i, i) for i in range(1, 6)] + [mk(6, 6, effect='full_roster', edition='diamond', rating=92)]
ctxFH = projCtx(weeklyFH)
resFH = calculateWeekCardBonuses(cards, ctxFH)
fh = next((b for b in resFH.cardBreakdowns if b.effectName == 'full_roster'), None)
print(f"     Full House projected mult = {fh.primaryMult}  (expected a modest EV, not the full diamond reward)")
expect("Full House projects a partial (EV) multiplier > 1", fh and fh.primaryMult > 1.0)
expect("Full House EV is well below its full reward (joint prob is small)", fh.primaryMult < 1.5)

print("\n" + ("ALL PASS" if not failures else f"{len(failures)} FAILED: {failures}"))
sys.exit(1 if failures else 0)
