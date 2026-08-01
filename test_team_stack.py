"""Team stacking + Champion amplifier + All-Pro gate cut (fusion strategy layer).

- Team stacking: fielding N cards whose depicted players share a real team grants a
  lineup-wide FPx that escalates with the largest same-team group.
- Champion (team accolade) AMPLIFIES a stack — a champ stack ("Dynasty") pays more than
  the same-size stack of a random team (per-champion, no cliff).
- All-Pro (individual accolade) took over the on-card gate cut (lower own bar); Champion
  no longer cuts the gate.

Run: .venv/bin/python test_team_stack.py
"""
import sys
sys.path.insert(0, '/Users/andrew/Projects/floosball')
import logging; logging.disable(logging.CRITICAL)
from types import SimpleNamespace
from managers.cardEffects import buildEffectConfig
from managers.cardEffectCalculator import CardCalcContext, calculateWeekCardBonuses, aggregateMultFactors
from constants import (CARD_TEAM_STACK_BONUS, CARD_CHAMPION_STACK_PREMIUM,
                       CARD_GATE_FP_THRESHOLDS, CARD_GATE_ALLPRO_MULT,
                       SYNERGY_MODIFIER_STACK_MULT)

failures = []
def expect(desc, cond):
    print(f"  [{'OK' if cond else 'FAIL'}] {desc}")
    if not cond:
        failures.append(desc)

WR = 3


def mk(eqId, pid, teamId, classification=None):
    cfg = buildEffectConfig('base', 80, WR, forceEffect='freebie')
    tmpl = SimpleNamespace(effect_config=cfg, player_id=pid, position=WR, team_id=teamId,
        edition='base', player_rating=80, player_name=f"P{pid}", classification=classification, is_rookie=False)
    uc = SimpleNamespace(card_template=tmpl, tier=1, id=eqId * 100)
    return SimpleNamespace(id=eqId, user_card=uc, slot_number=eqId, slot=None, peak_output=0.0, weeks_since_break=0)


def runStack(cards, activeModifier=""):
    c = CardCalcContext(); c.gamesActive = False
    c.activeModifier = activeModifier
    pids = {eq.user_card.card_template.player_id for eq in cards}
    c.rosterPlayerIds = pids
    c.rosterPlayerPositions = {p: WR for p in pids}
    c.rosterPlayerNames = {p: f"P{p}" for p in pids}
    c.weekPlayerStats = {p: {"fantasyPoints": 20} for p in pids}  # all clear their bar
    res = calculateWeekCardBonuses(cards, c)
    return res


print("1. Stacking same-team players grants an escalating FPx")
# 3 players on team 7, 3 spread across other teams -> largest stack = 3
cards = [mk(1, 1, 7), mk(2, 2, 7), mk(3, 3, 7), mk(4, 4, 11), mk(5, 5, 12), mk(6, 6, 13)]
r = runStack(cards)
print(f"     stackSize={r.stackSize} champs={r.stackChampions} bonus=+{r.stackBonus} FPx")
expect("largest stack detected as 3", r.stackSize == 3)
expect(f"bonus ≈ base(3)={CARD_TEAM_STACK_BONUS[3]}", abs(r.stackBonus - CARD_TEAM_STACK_BONUS[3]) < 0.001)

print("\n2. No stack (all different teams) -> no bonus")
cards = [mk(i, i, 10 + i) for i in range(1, 7)]
r = runStack(cards)
expect(f"stackSize < 2 -> no bonus (size={r.stackSize}, bonus={r.stackBonus})", r.stackBonus == 0.0)

print("\n3. A Champion stack pays MORE than a same-size non-champion stack")
plain = runStack([mk(1, 1, 7), mk(2, 2, 7), mk(3, 3, 7)])                  # 3 same-team, 0 champs
champ = runStack([mk(1, 1, 7, 'champion'), mk(2, 2, 7, 'champion'), mk(3, 3, 7, 'champion')])  # 3 champs
print(f"     plain 3-stack=+{plain.stackBonus}  champion 3-stack=+{champ.stackBonus}")
expected = CARD_TEAM_STACK_BONUS[3] * (1 + CARD_CHAMPION_STACK_PREMIUM)
expect("champion stack > plain stack", champ.stackBonus > plain.stackBonus)
expect(f"champion stack ≈ base × (1+{CARD_CHAMPION_STACK_PREMIUM}) = {round(expected,3)}",
       abs(champ.stackBonus - expected) < 0.002)
expect("champion count recorded", champ.stackChampions == 3)

print("\n4. Partial-champion stack scales per-champion (no cliff)")
half = runStack([mk(1, 1, 7, 'champion'), mk(2, 2, 7), mk(3, 3, 7)])  # 1 of 3 champs
midExpected = CARD_TEAM_STACK_BONUS[3] * (1 + (1 / 3) * CARD_CHAMPION_STACK_PREMIUM)
print(f"     1-of-3-champ stack=+{half.stackBonus} (between plain {plain.stackBonus} and full {champ.stackBonus})")
expect("partial sits between plain and full", plain.stackBonus < half.stackBonus < champ.stackBonus)
expect(f"partial ≈ per-champion value {round(midExpected,3)}", abs(half.stackBonus - midExpected) < 0.002)

print("\n5. Ties resolve toward the champion (best-paying) group")
# two 3-stacks: team 7 all champions, team 8 no champions
cards = [mk(1, 1, 7, 'champion'), mk(2, 2, 7, 'champion'), mk(3, 3, 7, 'champion'),
         mk(4, 4, 8), mk(5, 5, 8), mk(6, 6, 8)]
r = runStack(cards)
expect(f"picks the champion group (champs={r.stackChampions})", r.stackChampions == 3)

print("\n6. Gate cut moved to All-Pro; Champion no longer cuts the gate")
base = CARD_GATE_FP_THRESHOLDS[WR]  # 8
ap = buildEffectConfig('holographic', 88, WR, forceEffect='freebie', classification='all_pro')
ch = buildEffectConfig('holographic', 88, WR, forceEffect='freebie', classification='champion')
print(f"     base bar={base}  all_pro bar={ap['gate']['threshold']}  champion bar={ch['gate']['threshold']}")
expect(f"All-Pro card has the lowered bar ({ap['gate']['threshold']})",
       ap['gate']['threshold'] == max(1, round(base * CARD_GATE_ALLPRO_MULT)))
expect("Champion card has the NORMAL bar (no cut)", ch['gate']['threshold'] == base)

print("\n7. Synergy weekly modifier DOUBLES the team-stack FPx (repurposed from unique-positions)")
# Owner-reported (2026-07-28): the old Synergy modifier keyed off unique equipped positions,
# which fusion pins constant (every card is a different slot). Repurposed to amplify the
# fusion-native team-stack axis: a stacked lineup pays 2x stack FPx on a Synergy week.
threeStack = [mk(1, 1, 7), mk(2, 2, 7), mk(3, 3, 7), mk(4, 4, 11), mk(5, 5, 12), mk(6, 6, 13)]
plain = runStack(threeStack)
syn = runStack(threeStack, activeModifier="synergy")
print(f"     plain 3-stack=+{plain.stackBonus}  synergy 3-stack=+{syn.stackBonus} (extra {syn.stackModifierBonus})")
expect(f"synergy doubles the stack bonus ({plain.stackBonus} -> {round(plain.stackBonus * SYNERGY_MODIFIER_STACK_MULT,3)})",
       abs(syn.stackBonus - plain.stackBonus * SYNERGY_MODIFIER_STACK_MULT) < 0.002)
expect("the modifier's extra is tracked for the achievement exclusion",
       abs(syn.stackModifierBonus - plain.stackBonus * (SYNERGY_MODIFIER_STACK_MULT - 1)) < 0.002)

print("\n8. Synergy does NOTHING for a non-stacked lineup (all different teams)")
noStack = [mk(i, i, 10 + i) for i in range(1, 7)]
synNone = runStack(noStack, activeModifier="synergy")
expect(f"no stack -> synergy grants nothing (bonus={synNone.stackBonus}, extra={synNone.stackModifierBonus})",
       synNone.stackBonus == 0.0 and synNone.stackModifierBonus == 0.0)


print("\n" + ("ALL PASS" if not failures else f"{len(failures)} FAILED: {failures}"))
sys.exit(1 if failures else 0)
