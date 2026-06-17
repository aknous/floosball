"""Regression: a pure-marker card (Doubler) must not bank a position-conditional
match bonus, and Lemons must not amplify it.

Repro of the reported bug: Doubler depicts a rostered player (MATCH) who cleared
a position stat threshold (WR 100+ rec yds = +15). The conditional block handed
that 15 FP to Doubler — a marker that outputs nothing — and Lemons then grabbed
it as the "lowest earner" and added base x (mult-1) (15 x 2.25 = +33.8).

Fix: skip the position-conditional for marker cards (they stay at 0), and have
Lemons/Conductor select + multiply each card's OWN effect output (primaryFP),
not totalFP (which includes the performance bonus).

Run: python3 test_lemons_marker_leak.py
"""
from managers.cardEffectCalculator import calculateWeekCardBonuses, CardCalcContext
from test_doubler_double_count import makeCard


def run():
    # Doubler depicts player 101 (a rostered WR) who hit 100+ rec yards.
    doubler = makeCard(1, "doubler", 3, 101, {"tdMult": 2.0})
    lemons = makeCard(2, "double_down", 1, 999, {})

    ctx = CardCalcContext()
    ctx.rosterPlayerIds = {101}                       # → Doubler isMatch = True
    ctx.rosterPlayerPositions = {101: 3}              # WR
    ctx.weekPlayerStats = {101: {"receiving_stats": {"rcvYards": 100}}}  # clears WR conditional
    ctx.rosterTotalTds = 0

    result = calculateWeekCardBonuses([doubler, lemons], ctx)
    dbl = next(b for b in result.cardBreakdowns if b.effectName == "doubler")
    return dbl


def main():
    dbl = run()
    print(f"Doubler row: totalFP={dbl.totalFP}  primaryFP={dbl.primaryFP}  eq={dbl.equation!r}")

    ok = True
    if dbl.totalFP != 0:
        print(f"FAIL: marker Doubler banked {dbl.totalFP} FP from a conditional/Lemons "
              f"(should be 0).")
        ok = False
    if "Lemons" in (dbl.equation or ""):
        print("FAIL: Lemons amplified the marker Doubler (should never target it).")
        ok = False

    print("PASS — markers earn no conditional bonus and Lemons leaves them alone."
          if ok else ">>> MARKER FP LEAK PRESENT <<<")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
