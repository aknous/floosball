"""Regression: Doubler must not double-count roster TDs across passes.

Repro of the reported bug: a roster with 6 real TDs + Doubler + Touchdown
Pinata read 24 TDs at week end (correct 12 during live games). Cause: the
amplifier pre-pass mutated the shared per-player stat dicts in place, so the
week-end pass re-derived the count from already-doubled stats (6 -> 12 live
-> 24 banked). The fix deep-copies weekPlayerStats before amplifying.

Run: python3 test_doubler_double_count.py
"""
import re as _re
from types import SimpleNamespace

from managers.cardEffects import _countPlayerTds
from managers.cardEffectCalculator import calculateWeekCardBonuses, CardCalcContext


def makeCard(eqId, effectName, position, playerId, primary, tier=1):
    template = SimpleNamespace(
        effect_config={"effectName": effectName, "primary": primary,
                       "outputType": "fp", "position": position,
                       "editionScale": 1.0},
        position=position,
        player_id=playerId,
        player_rating=80,
        edition="base",
        player_name=f"Player{playerId}",
    )
    userCard = SimpleNamespace(card_template=template, tier=tier)
    return SimpleNamespace(id=eqId, user_card=userCard, slot_number=eqId)


def buildSourceStats():
    """Per-player week stats summing to exactly 6 roster TDs (the shared dicts
    handed in by fantasyTracker, by reference)."""
    return {
        101: {"passing_stats": {"tds": 3}},      # QB: 3 pass TDs
        102: {"rushing_stats": {"runTds": 2}},   # RB: 2 rush TDs
        103: {"receiving_stats": {"rcvTds": 1}}, # WR: 1 rec TD
    }


def runPass(sourceStats, cards):
    """Mimic fantasyTracker: derive rosterTotalTds from the (shared) source
    dicts, hand them to the calculator by reference, return pinata's FP."""
    rosterTotalTds = sum(_countPlayerTds(s) for s in sourceStats.values())
    ctx = CardCalcContext()
    ctx.weekPlayerStats = sourceStats            # by reference, as in prod
    ctx.rosterTotalTds = rosterTotalTds
    ctx.rosterPlayerIds = set(sourceStats.keys())
    ctx.rosterPlayerPositions = {101: 1, 102: 2, 103: 3}
    result = calculateWeekCardBonuses(cards, ctx)
    pinata = next(b for b in result.cardBreakdowns
                  if b.effectName == "touchdown_pinata")
    # The TD count the pinata actually consumed, parsed from its equation
    # (e.g. "9.6/TD × 12 roster TDs"). This is the value the bug inflates.
    m = _re.search(r"×\s*(\d+)\s*roster TDs", pinata.equation)
    tdsUsed = int(m.group(1)) if m else None
    return rosterTotalTds, tdsUsed, pinata.totalFP


def main():
    perTd = 9.6
    cards = [
        makeCard(1, "touchdown_pinata", 1, 101, {"perTdFP": perTd}),
        makeCard(2, "doubler", 5, 999, {"tdMult": 2.0}, tier=1),
    ]

    # Baseline: pinata alone, 6 real TDs, no Doubler.
    _, baseTds, baseFP = runPass(buildSourceStats(),
                                 [makeCard(1, "touchdown_pinata", 1, 101,
                                           {"perTdFP": perTd})])

    # The reported hand. Pass 1 = live; Pass 2 = week-end banking, both
    # re-reading the SAME shared source dicts (as fantasyTracker does).
    sourceStats = buildSourceStats()
    derived1, tds1, fp1 = runPass(sourceStats, cards)
    derived2, tds2, fp2 = runPass(sourceStats, cards)

    print(f"Real roster TDs: 6")
    print(f"No Doubler:        pinata consumed {baseTds} TDs (FP={baseFP})")
    print(f"Pass 1 (live):     derived={derived1}, pinata consumed {tds1} TDs (FP={fp1})")
    print(f"Pass 2 (week-end): derived={derived2}, pinata consumed {tds2} TDs (FP={fp2})")

    ok = True
    if baseTds != 6:
        print(f"FAIL: baseline pinata should see 6 TDs, saw {baseTds}")
        ok = False
    if derived1 != 6 or derived2 != 6:
        print(f"FAIL: source dicts were mutated in place — derived should be 6 "
              f"both passes, got {derived1} then {derived2}")
        ok = False
    if tds1 != 12 or tds2 != 12:
        print(f"FAIL: Doubler should make pinata see exactly 12 TDs both passes "
              f"(6 x2); saw {tds1} then {tds2}. A week-end value of 24 is the "
              f"4x stacking bug.")
        ok = False
    if fp1 != fp2:
        print(f"FAIL: pinata FP drifted between live and week-end ({fp1} -> {fp2})")
        ok = False

    print("PASS — Doubler doubles exactly once; no cross-pass stacking."
          if ok else ">>> REGRESSION PRESENT <<<")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
