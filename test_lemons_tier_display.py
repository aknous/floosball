"""Regression: a tiered Lemons quotes ONE multiplier everywhere.

A tier II Lemons read x2.5 on the lineup pill (untiered), x2.9 in its description
(whole value scaled) and x2.72 in the breakdown (delta scaled, which is what the calc
applies). All three must match the calc's 1 + (m - 1) * tierMult.
"""
from types import SimpleNamespace as N

from constants import CARD_TIER_MULT
from managers.cardEffects import tierScaledStrength
from managers.cardProjection import _amplifierStatus

BASE = 2.5
fails = []
for tier in (2, 3, 4):
    calc = round(1 + (BASE - 1) * CARD_TIER_MULT[tier], 2)
    text = tierScaledStrength("double_down", {"rewardValue": BASE}, CARD_TIER_MULT[tier])["rewardValue"]
    tpl = N(effect_config={"effectName": "double_down",
                           "primary": {"rewardType": "mult", "rewardValue": BASE}})
    eq = N(user_card=N(tier=tier, card_template=tpl))
    pill = _amplifierStatus(eq, [eq, object()])["description"]
    if text != calc:
        fails.append(f"tier {tier}: description {text} != calc {calc}")
    if f"×{calc} " not in pill:
        fails.append(f"tier {tier}: pill '{pill}' does not quote x{calc}")

# The Lemons card's OWN breakdown row, through the real post-pass.
from managers.cardEffectCalculator import CardBreakdown, _applyTradeoffEffects
for tier in (2, 4):
    calc = round(1 + (BASE - 1) * CARD_TIER_MULT[tier], 2)
    dd = CardBreakdown(effectName="double_down", primaryMult=calc,
                       equation=f"× {BASE} on your lowest-earning FP card")
    other = CardBreakdown(effectName="freebie", outputType="fp", primaryFP=10.0, totalFP=10.0,
                          equation="+10.0 FP")
    _applyTradeoffEffects([dd, other])
    if f"× {calc} on" not in dd.equation:
        fails.append(f"tier {tier}: Lemons row reads '{dd.equation}', applied x{calc}")
    if f"× {calc} (Lemons)" not in other.equation:
        fails.append(f"tier {tier}: boosted card reads '{other.equation}'")

if fails:
    print("FAIL\n  " + "\n  ".join(fails))
    raise SystemExit(1)
print("PASS - tiered Lemons quotes the applied multiplier on every surface")
