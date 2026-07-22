"""Regression: position-specific effects score off the CARD'S OWN player.

Fantasy/Cards fusion Stage 1 of the on-card re-base
(docs/CARD_ONCARD_REBASE_PLAN.md). Position-specific stat effects used to read
`_getRosterStatsAtPosition(ctx, ctx.cardPosition)` — "whoever occupies this
position". Under fusion's position-locked slots that's almost the card's own
player, EXCEPT at WR, where position 3 holds two slots and the helper SUMMED
WR1 + WR2. So both receiver cards scored off the pair's combined output and each
paid roughly double.

This pins the fix: two WR cards depicting two different receivers must each
score off their own player's line, not the combined total.

Run: python3 test_oncard_rebase.py
"""
from managers.cardEffectCalculator import calculateWeekCardBonuses, CardCalcContext
from test_doubler_double_count import makeCard

WR1_ID, WR2_ID = 101, 102
WR1_YARDS, WR2_YARDS = 120, 40
WR1_RECS, WR2_RECS = 9, 3


def buildCtx():
    ctx = CardCalcContext()
    ctx.rosterPlayerIds = {WR1_ID, WR2_ID}
    ctx.rosterPlayerPositions = {WR1_ID: 3, WR2_ID: 3}
    ctx.rosterPlayerRatings = {WR1_ID: 80, WR2_ID: 80}
    ctx.rosterPlayerNames = {WR1_ID: "Split End", WR2_ID: "Flanker"}
    ctx.weekPlayerStats = {
        WR1_ID: {"fantasyPoints": 20,
                 "receiving_stats": {"rcvYards": WR1_YARDS, "receptions": WR1_RECS,
                                     "rcvTds": 1, "longest": 44}},
        WR2_ID: {"fantasyPoints": 7,
                 "receiving_stats": {"rcvYards": WR2_YARDS, "receptions": WR2_RECS,
                                     "rcvTds": 0, "longest": 12}},
    }
    ctx.rosterTotalTds = 1
    return ctx


def scoreOf(effectName, cardPlayerId, primary):
    """Score one card in isolation so no cross-card effect muddies the read."""
    card = makeCard(1, effectName, 3, cardPlayerId, primary)
    res = calculateWeekCardBonuses([card], buildCtx())
    return next(b for b in res.cardBreakdowns if b.effectName == effectName)


def main():
    ok = True

    # ── Possession: FP per reception, position-specific.
    perRec = 1.0
    b1 = scoreOf("possession", WR1_ID, {"perReceptionFP": perRec})
    b2 = scoreOf("possession", WR2_ID, {"perReceptionFP": perRec})
    combined = WR1_RECS + WR2_RECS
    print(f"Possession  WR1({WR1_RECS} rec) primaryFP={b1.primaryFP}  eq={b1.equation!r}")
    print(f"Possession  WR2({WR2_RECS} rec) primaryFP={b2.primaryFP}  eq={b2.equation!r}")

    if b1.primaryFP != perRec * WR1_RECS:
        print(f"FAIL: WR1 card scored {b1.primaryFP}, expected {perRec * WR1_RECS} "
              f"(its own receptions).")
        ok = False
    if b2.primaryFP != perRec * WR2_RECS:
        print(f"FAIL: WR2 card scored {b2.primaryFP}, expected {perRec * WR2_RECS} "
              f"(its own receptions).")
        ok = False
    if b1.primaryFP == perRec * combined or b2.primaryFP == perRec * combined:
        print(f"FAIL: a WR card scored off the COMBINED {combined} receptions "
              f"— the WR1+WR2 double-count is back.")
        ok = False
    if b1.primaryFP == b2.primaryFP:
        print("FAIL: both WR cards scored identically — still reading the same "
              "position-aggregate rather than their own players.")
        ok = False

    # ── Trebuchet: threshold on the card player's longest catch.
    # WR1 has a 44-yd catch (clears 25), WR2's best is 12 (does not).
    t1 = scoreOf("trebuchet", WR1_ID, {"baseFP": 3.0, "rewardValue": 8, "threshold": 25})
    t2 = scoreOf("trebuchet", WR2_ID, {"baseFP": 3.0, "rewardValue": 8, "threshold": 25})
    print(f"Trebuchet   WR1(long 44) primaryFP={t1.primaryFP}  eq={t1.equation!r}")
    print(f"Trebuchet   WR2(long 12) primaryFP={t2.primaryFP}  eq={t2.equation!r}")
    if t1.primaryFP != 11.0:
        print(f"FAIL: WR1 trebuchet scored {t1.primaryFP}, expected 11.0 (3 base + 8 bonus).")
        ok = False
    if t2.primaryFP != 3.0:
        print(f"FAIL: WR2 trebuchet scored {t2.primaryFP}, expected 3.0 (base only) — "
              f"it should NOT inherit WR1's 44-yd catch.")
        ok = False

    print("\nPASS — position-specific effects read the card's own player."
          if ok else "\n>>> ON-CARD RE-BASE REGRESSION <<<")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
