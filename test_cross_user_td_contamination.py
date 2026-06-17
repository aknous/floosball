"""Regression: an amplifier (Doubler) must not contaminate OTHER users' counts.

Reproduces the prod bug observed in S10 (W8/W12): the Diamond amplifier pre-pass
(doubler/surveyor/sharpshooter) iterates the *entire shared* weekPlayerStats dict
and doubles every player's TD stats IN PLACE. In the week-end banking path that
dict is built once and handed to every user (seasonManager.py:2134). So a user
with a Doubler doubles every player's TDs for everyone processed after them —
two Doubler users => 4x — even though the victim has no amplifier. This is why
Touchdown Jackpot / Feeding Frenzy / Touchdown Pinata read 2x-4x the real count
for users who had none of those amplifiers.

The fix (cardEffectCalculator: deep-copy ctx.weekPlayerStats before the amplifier
pre-pass) makes the amplifier mutate only a private copy, so the shared dict —
and every other user's count derived from it — stays correct.

Run: python3 test_cross_user_td_contamination.py
"""
import re as _re

from managers.cardEffects import _countPlayerTds
from managers.cardEffectCalculator import calculateWeekCardBonuses, CardCalcContext
from test_doubler_double_count import makeCard


def buildSharedWeekStats():
    """The full week's per-player stats (shared object, as the banking path
    builds once and hands to every user). Victim rosters 101/102/103 = 6 TDs.
    Players 201/202 belong to the Doubler users' rosters."""
    return {
        101: {"passing_stats": {"tds": 3}},      # victim QB
        102: {"rushing_stats": {"runTds": 2}},   # victim RB
        103: {"receiving_stats": {"rcvTds": 1}}, # victim WR
        201: {"rushing_stats": {"runTds": 1}},   # a doubler-user's player
        202: {"receiving_stats": {"rcvTds": 1}}, # a doubler-user's player
    }


def runUser(cards, rosterPids, sharedStore):
    """Mirror the banking path: derive rosterTotalTds from the (possibly already
    contaminated) shared dict, hand the SAME shared dict in as ctx.weekPlayerStats,
    then compute. Returns (derivedTds, pinataTdsConsumed-or-None)."""
    rt = sum(_countPlayerTds(sharedStore[p]) for p in rosterPids)
    ctx = CardCalcContext()
    ctx.weekPlayerStats = sharedStore          # full shared dict, same object (banking path)
    ctx.rosterTotalTds = rt
    ctx.rosterPlayerIds = set(rosterPids)
    ctx.rosterPlayerPositions = {101: 1, 102: 2, 103: 3, 201: 2, 202: 3}
    result = calculateWeekCardBonuses(cards, ctx)
    tdsUsed = None
    for b in result.cardBreakdowns:
        if b.effectName == "touchdown_pinata":
            m = _re.search(r"×\s*(\d+)\s*roster TDs", b.equation)
            tdsUsed = int(m.group(1)) if m else None
    return rt, tdsUsed


def scenario(nDoublers):
    """Process nDoublers amplifier users, then the victim, against one shared
    dict — exactly the banking loop. Return the victim's consumed TD count."""
    shared = buildSharedWeekStats()
    doublerHand = lambda i: [
        makeCard(10 + i, "doubler", 5, 900 + i, {"tdMult": 2.0}),
        makeCard(20 + i, "touchdown_pinata", 1, 201, {"perTdFP": 5.0}),
    ]
    for i in range(nDoublers):
        runUser(doublerHand(i), [201, 202], shared)   # doubler users roster OTHER players
    # victim: no amplifier, just a TD card, rosters 101/102/103
    victimCards = [makeCard(99, "touchdown_pinata", 1, 101, {"perTdFP": 9.6})]
    return runUser(victimCards, [101, 102, 103], shared)


def main():
    ok = True
    print("Victim has 6 real roster TDs and NO amplifier.")
    for nd in (0, 1, 2):
        derived, tdsUsed = scenario(nd)
        wouldBeBug = 6 * (2 ** nd)
        status = "OK" if tdsUsed == 6 else "CONTAMINATED"
        print(f"  upstream doublers={nd}: victim consumed {tdsUsed} TDs "
              f"(correct=6, bug would be {wouldBeBug})  [{status}]")
        if tdsUsed != 6:
            ok = False

    print("PASS — amplifiers don't leak into other users' TD counts."
          if ok else ">>> CROSS-USER CONTAMINATION PRESENT <<<")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
