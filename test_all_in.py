"""All In / "Bet Big" (all_in) — the fusion redesign (Phase 5c).

Under fusion the old "stack duplicate positions" premise fired free (WR1+WR2 are both WR).
Bet Big re-bases onto the depicted player: the normal FP power-bar gate handles on/off,
and a higher STUD LINE scales the payout — nothing on an average week, FPx climbing with
every FP past the line (capped). A monster individual game pays big.

Run: .venv/bin/python test_all_in.py
"""
import sys
sys.path.insert(0, '/Users/andrew/Projects/floosball')
import logging; logging.disable(logging.CRITICAL)
from managers.cardEffects import computeEffect, buildEffectConfig, _ALL_IN_STUD_LINE
from managers.cardEffectCalculator import CardCalcContext
from constants import CARD_GATE_FP_THRESHOLDS

failures = []
def expect(desc, cond):
    print(f"  [{'OK' if cond else 'FAIL'}] {desc}")
    if not cond:
        failures.append(desc)

WR = 3
CARD = 500
# ⚠️ PER-EDITION BAR. `run()` mints a PRISMATIC card by default, and the gate bar is set
# by CARD_GATE_FP_THRESHOLDS_BY_EDITION (prismatic WR = 12), not by the flat
# CARD_GATE_FP_THRESHOLDS table (8). Reading the flat one compared the minted card
# against a bar no prismatic card ever gets.
from constants import CARD_GATE_FP_THRESHOLDS_BY_EDITION
WR_GATE = CARD_GATE_FP_THRESHOLDS_BY_EDITION['prismatic'][WR]   # 12
WR_STUD = _ALL_IN_STUD_LINE[WR]           # 20


def run(fp, edition='prismatic', position=WR):
    cfg = buildEffectConfig(edition, 88, position, forceEffect='all_in')
    c = CardCalcContext()
    c.gamesActive = False
    c.rosterPlayerIds = {CARD}
    c.rosterPlayerPositions = {CARD: position}
    c.weekPlayerStats = {CARD: {"fantasyPoints": fp}}
    return computeEffect(cfg, c, CARD, 1), cfg


print("0. Mint config carries a position-aware stud line + scaling params")
_, cfg = run(0)
p = cfg["primary"]
expect(f"studLine injected for WR ({p.get('studLine')})", p.get("studLine") == WR_STUD)
expect(f"perFPx present ({p.get('perFPx')})", isinstance(p.get("perFPx"), (int, float)) and p["perFPx"] > 0)
expect(f"maxXBonus cap present ({p.get('maxXBonus')})", p.get("maxXBonus", 0) > 0)
# ⚠️ ALL IN GATES AT ITS OWN STUD LINE, NOT THE GENERIC PER-EDITION BAR. The two are
# deliberately kept EQUAL on this card (see _allInStudLine: lowering both together is
# what keeps an All-Pro All In paying sooner without reopening the gap). This compared
# against the standard bar, which All In has never used.
expect(f"the card gates at its stud line ({cfg.get('gate', {}).get('threshold')})",
       cfg.get("gate", {}).get("threshold") == p.get("studLine") == WR_STUD)

print("\n1. Under the stud line -> no payout")
r, _ = run(WR_STUD - 3)                    # above the gate, below the stud line
expect(f"{WR_STUD-3} FP (over gate, under stud) -> no bonus  (x{r.multBonus})",
       not r.multBonus or r.multBonus <= 1.0)

print("\n2. Below the gate -> central gate zeros it too")
r, _ = run(WR_GATE - 5)
expect(f"{WR_GATE-5} FP (under the gate) -> nothing  (x{r.multBonus})",
       not r.multBonus or r.multBonus <= 1.0)

print("\n3. A monster week -> FPx scales up")
r_mid, _ = run(WR_STUD + 14)               # comfortably over the stud line
expect(f"{WR_STUD+14} FP -> FPx fires  (x{r_mid.multBonus})", r_mid.multBonus and r_mid.multBonus > 1.0)
r_more, _ = run(WR_STUD + 28)
expect(f"more FP -> bigger FPx  ({r_more.multBonus} > {r_mid.multBonus})",
       r_more.multBonus > r_mid.multBonus)

print("\n4. Runaway week is capped")
cap = run(0)[1]["primary"]["maxXBonus"]
r_huge, _ = run(WR_STUD + 500)
expect(f"a freak 500-over week is capped at 1 + {cap}  (x{r_huge.multBonus})",
       abs(r_huge.multBonus - (1.0 + cap)) < 0.011)

print("\n5. Stud line is position-aware (TE lower than QB)")
expect(f"TE stud ({_ALL_IN_STUD_LINE[4]}) < QB stud ({_ALL_IN_STUD_LINE[1]})",
       _ALL_IN_STUD_LINE[4] < _ALL_IN_STUD_LINE[1])

print("\n" + ("ALL PASS" if not failures else f"{len(failures)} FAILED: {failures}"))
sys.exit(1 if failures else 0)
