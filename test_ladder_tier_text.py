"""Regression: a leveled stat-ladder card's text quotes what the calculator pays.

Stat-ladder cards are sized per position, not by edition, so the tier text's edition
probe moved none of their params: a tier II Paydirt still read "+0.12 FPx for every
receiving TD" while it paid +0.138, with only a "x1.15 output" line under it, which a
user read as 1.15x the player's own points. Their payouts now scale by name; their
thresholds do not. Every other tiered card either rewrites its text or says what the
multiplier scales.
"""
import re
from types import SimpleNamespace as N

from constants import CARD_TIER_MULT, ODOMETER_GATE_FP_BY_POSITION
from managers.cardEffects import buildEffectConfig, effectPoolFor
from managers.cardManager import CardManager

cm = CardManager(None)


def serialize(effect, edition, pos, tier):
    cfg = buildEffectConfig(edition, 85, pos, None, forceEffect=effect)
    tpl = N(id=1, player_id=1, player_name="X", team_id=None, team=None, player_rating=85,
            position=pos, edition=edition, effect_config=cfg, season_created=1,
            is_rookie=False, classification=None, is_synthetic=False, is_upgraded=False,
            is_showpiece=False, sell_value=10)
    uc = N(id=1, card_template=tpl, card_template_id=1, tier=tier, vaulted=False,
           vault_position=None, glitched=False, glitched_season=None, glitched_week=None,
           acquired_at=None, acquired_via="test")
    return cfg["primary"], cm.serializeCard(uc, 1)


def nums(text):
    return [float(x) for x in re.findall(r"\d+(?:\.\d+)?", text or "")]


def test_paydirt_quotes_the_tiered_rate_and_cap():
    prim, card = serialize("paydirt", "metallic", 3, 2)
    assert f"+{round(prim['perTdMult'] * 1.15, 2)} FPx" in card["detail"], card["detail"]
    assert card["tierNote"] is None, card["tierNote"]


def test_end_zone_scales_its_payouts_and_keeps_its_threshold():
    prim, card = serialize("end_zone", "holographic", 3, 4)
    shown = nums(card["detail"])
    assert round(prim["perTdFP"] * 1.5, 1) in shown, card["detail"]
    assert round(prim["bonusFP"] * 1.5, 1) in shown, card["detail"]
    assert prim["threshold"] in shown, card["detail"]       # the second TD stays the second


def test_odometer_scales_every_gate_payout():
    _prim, card = serialize("odometer", "prismatic", 3, 3)
    pays = ODOMETER_GATE_FP_BY_POSITION[3]
    for p in pays:
        assert f"+{round(p * 1.32, 1):g}" in card["detail"], card["detail"]


def test_every_tiered_card_shows_its_tier():
    """At tier II every mintable card either rewrites its text or names what x1.15 scales."""
    silent = []
    seen = set()
    for edition in ("metallic", "holographic", "prismatic", "diamond"):
        for pos in (1, 2, 3, 4, 5):
            for effect in effectPoolFor(edition, pos) or []:
                if effect in seen:
                    continue
                seen.add(effect)
                _p, base = serialize(effect, edition, pos, 1)
                _p, tiered = serialize(effect, edition, pos, 2)
                if tiered["detail"] == base["detail"]:
                    note = tiered["tierNote"] or ""
                    if not re.search(r"×1\.15 (FPx bonus|FP|Floobits)$", note):
                        silent.append(f"{effect}: {note!r}")
    assert not silent, silent


def test_the_fallback_says_an_fpx_card_scales_its_bonus():
    _p, card = serialize("snake_eyes", "diamond", 3, 2)
    assert card["tierNote"] == "Tier II: ×1.15 FPx bonus", card["tierNote"]
