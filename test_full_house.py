"""Full House (full_roster) — the fusion redesign (Phase 5c).

Under fusion the old "hand has all 5 positions" premise fired free (the position-locked
base slots always span all 5). Full House now re-bases onto the FP power bar: it's a big
Diamond FPx that fires ONLY in a week where EVERY performing (gated) card in the lineup
cleared its bar. One cold player and it pays nothing. It runs second-pass so all first-pass
gates are resolved first (calculator snapshots ctx._firstPassGatedCount / _firstPassGatedOn).

Run: .venv/bin/python test_full_house.py
"""
import sys
sys.path.insert(0, '/Users/andrew/Projects/floosball')
import logging; logging.disable(logging.CRITICAL)
from types import SimpleNamespace
from managers.cardEffects import buildEffectConfig, _FULL_HOUSE_MIN_CARDS
from managers.cardEffectCalculator import (CardCalcContext, calculateWeekCardBonuses,
                                           _SECOND_PASS_EFFECTS)
from constants import CARD_GATE_FP_THRESHOLDS

failures = []
def expect(desc, cond):
    print(f"  [{'OK' if cond else 'FAIL'}] {desc}")
    if not cond:
        failures.append(desc)

WR = 3
WR_THR = CARD_GATE_FP_THRESHOLDS[WR]  # 8
# ⚠️ FULL HOUSE IS A DIAMOND CARD, so its OWN player faces the diamond bar (14 for a WR),
# not the generic one. The fixture used to give every player WR_THR + 5 = 13, which clears
# the generic bar and MISSES the diamond one — so Full House's own gate zeroed a multiplier
# it had correctly computed, and this file failed for a reason that had nothing to do with
# the behaviour under test. It was failing that way at HEAD, which is exactly the kind of
# red that stops meaning anything.
from constants import CARD_GATE_FP_THRESHOLDS_BY_EDITION as _BY_ED
FH_THR = _BY_ED.get('diamond', {}).get(WR, WR_THR)  # 14


def mkCard(eqId, pid, cfg, pos=WR, tier=1, edition='base', rating=80):
    tmpl = SimpleNamespace(effect_config=cfg, player_id=pid, position=pos, team_id=None,
                           edition=edition, player_rating=rating, player_name=f"P{pid}",
                           classification=None, is_rookie=False)
    uc = SimpleNamespace(card_template=tmpl, tier=tier, id=eqId * 100)
    return SimpleNamespace(id=eqId, user_card=uc, slot_number=eqId, slot=None,
                           peak_output=0.0, weeks_since_break=0)


def valueCard(eqId, pid):
    """A simple first-pass, gated flat-FP card at WR."""
    return mkCard(eqId, pid, buildEffectConfig('base', 80, WR, forceEffect='freebie'))


def fullHouseCard(eqId, pid):
    return mkCard(eqId, pid, buildEffectConfig('diamond', 92, WR, forceEffect='full_roster'),
                  edition='diamond', rating=92)


def runLineup(cards, fpByPid):
    ctx = CardCalcContext()
    ctx.gamesActive = False
    ctx.rosterPlayerIds = set(fpByPid)
    ctx.rosterPlayerPositions = {pid: WR for pid in fpByPid}
    ctx.rosterPlayerNames = {pid: f"P{pid}" for pid in fpByPid}
    ctx.weekPlayerStats = {pid: {"fantasyPoints": fp} for pid, fp in fpByPid.items()}
    res = calculateWeekCardBonuses(cards, ctx)
    fh = next((b for b in res.cardBreakdowns if b.effectName == 'full_roster'), None)
    return res, fh, ctx


print("0. Wiring")
expect("full_roster is a second-pass effect", 'full_roster' in _SECOND_PASS_EFFECTS)
expect(f"_FULL_HOUSE_MIN_CARDS == 4 (5 was unreachable with any cross card)",
       _FULL_HOUSE_MIN_CARDS == 4)

print("\n1. Full lineup, every card clears its bar -> Full House FIRES")
# 5 value cards (players 1-5) + Full House (player 6), all FP >= threshold.
cards = [valueCard(i, i) for i in range(1, 6)] + [fullHouseCard(6, 6)]
fp = {i: WR_THR + 5 for i in range(1, 6)}
fp[6] = FH_THR + 5   # Full House's own player must clear the DIAMOND bar
res, fh, ctx = runLineup(cards, fp)
expect(f"snapshot counted 5 first-pass gated cards (got {ctx._firstPassGatedCount})",
       ctx._firstPassGatedCount == 5)
expect(f"all 5 on (got {ctx._firstPassGatedOn})", ctx._firstPassGatedOn == 5)
expect(f"Full House multiplier fired  (x{fh.primaryMult})", fh and fh.primaryMult > 1.0)

print("\n2. One cold player -> Full House pays NOTHING (one dud kills it)")
fp2 = dict(fp); fp2[3] = WR_THR - 6   # player 3 below the bar
res, fh, ctx = runLineup(cards, fp2)
expect(f"snapshot: 4/5 on (got {ctx._firstPassGatedOn}/{ctx._firstPassGatedCount})",
       ctx._firstPassGatedCount == 5 and ctx._firstPassGatedOn == 4)
expect(f"Full House did NOT fire  (x{fh.primaryMult})", fh and fh.primaryMult <= 1.0)

print("\n3. Below the min-card floor -> can't fire even if all on")
# 3 value cards + Full House = 3 first-pass gated cards (< 4).
cards3 = [valueCard(i, i) for i in range(1, 4)] + [fullHouseCard(6, 6)]
fp3 = {i: WR_THR + 5 for i in (1, 2, 3)}
fp3[6] = FH_THR + 5
res, fh, ctx = runLineup(cards3, fp3)
expect(f"only {ctx._firstPassGatedCount} first-pass gated cards (< {_FULL_HOUSE_MIN_CARDS})",
       ctx._firstPassGatedCount == 3)
expect(f"Full House did NOT fire  (x{fh.primaryMult})", fh and fh.primaryMult <= 1.0)

print("\n3b. THE REPORTED LINEUP: 4 gated cards + a cross card -> it FIRES")
# ⚠️ Why the floor moved. A 6-slot lineup holding Full House and ONE cross card (Copycat,
# Lemons, Chain Reaction, ...) leaves exactly 4 first-pass gated cards. At a floor of 5 that
# was mathematically unable to fire, silently — reported by a user whose lineup was
# touchdown_pinata / Full House / allowance / diversified / copycat / alchemy.
cards4 = [valueCard(i, i) for i in range(1, 5)] + [fullHouseCard(6, 6)]
fp4 = {i: WR_THR + 5 for i in (1, 2, 3, 4)}
fp4[6] = FH_THR + 5
res, fh, ctx = runLineup(cards4, fp4)
expect(f"exactly {ctx._firstPassGatedCount} first-pass gated cards (== floor)",
       ctx._firstPassGatedCount == 4)
expect(f"all 4 cleared (got {ctx._firstPassGatedOn})", ctx._firstPassGatedOn == 4)
expect(f"Full House FIRES on the realistic lineup  (x{fh.primaryMult})",
       fh and fh.primaryMult > 1.0)

print("\n4. Full House's OWN player must also show up (central gate)")
# All 5 value cards on, but Full House's own depicted player is cold -> its own gate zeros it.
res, fh, ctx = runLineup(cards, {**{i: WR_THR + 5 for i in range(1, 6)}, 6: 0})
expect(f"all 5 first-pass on (got {ctx._firstPassGatedOn})", ctx._firstPassGatedOn == 5)
expect(f"but Full House's own cold player zeros it  (x{fh.primaryMult})",
       fh and fh.primaryMult <= 1.0)

print("\n" + ("ALL PASS" if not failures else f"{len(failures)} FAILED: {failures}"))
sys.exit(1 if failures else 0)
