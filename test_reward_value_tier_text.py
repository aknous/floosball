"""Regression: a leveled card's text quotes the FPx the calculator actually pays.

Backfield Buddies stores `rewardValue` as a bare delta (+0.40 FPx) but the tier text
treated it as a full multiplier, so tier II previewed as 1 + (0.40 - 1) x 1.15 = +0.31:
a smaller number for an upgrade. Checked here for every effect that stores an FPx
rewardValue, against the calculator's rule (step 1b scales the delta of multBonus).
"""
import re
from types import SimpleNamespace as N

from constants import CARD_TIER_MULT
from managers.cardEffects import buildEffectConfig, REWARDVALUE_IS_MULT_EFFECTS
from managers.cardManager import CardManager

CASES = {  # effect -> (edition, position)
    "backfield_buddies": ("holographic", 1),
    "stack": ("holographic", 1),
    "bandwagon": ("holographic", 3),
    "full_roster": ("prismatic", 3),
}

fails = []
cm = CardManager(None)
for effect, (edition, pos) in CASES.items():
    cfg = buildEffectConfig(edition, 85, pos, None, forceEffect=effect)
    rv = cfg["primary"]["rewardValue"]
    delta = rv - 1 if effect in REWARDVALUE_IS_MULT_EFFECTS else rv
    tpl = N(id=1, player_id=1, player_name="X", team_id=None, team=None, player_rating=85,
            position=pos, edition=edition, effect_config=cfg, season_created=1,
            is_rookie=False, classification=None, is_synthetic=False, is_upgraded=False,
            is_showpiece=False, sell_value=10)
    for tier in (1, 2, 3, 4):
        uc = N(id=1, card_template=tpl, card_template_id=1, tier=tier, vaulted=False,
               vault_position=None, glitched=False, glitched_season=None, glitched_week=None,
               acquired_at=None, acquired_via="test")
        detail = cm.serializeCard(uc, 1)["detail"]
        shown = float(re.search(r"\+([\d.]+) FPx", detail).group(1))
        paid = round(delta * CARD_TIER_MULT[tier], 2)
        if abs(shown - paid) > 0.011:
            fails.append(f"{effect} tier {tier}: text +{shown} FPx, calc pays +{paid}")

if fails:
    print("FAIL\n  " + "\n  ".join(fails))
    raise SystemExit(1)
print("PASS - leveled rewardValue text matches the calculator for", ", ".join(CASES))
