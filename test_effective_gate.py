"""Regression: a card's power bar is shown, scored and compared at the bar IN FORCE.

The live game format moves the bar (Innings x1.32), and that scale was applied inside
`gateRatio` alone. Reported from production, season 8 week 14 (Innings): an Eminence card
printed "Unlocks once this player reaches 9 FP", its player scored 10, the bar drew as
cleared — and the card paid nothing, because the bar in force was 12.
"""
import re
import time
from types import SimpleNamespace as N

import managers.cardEffects as ce
from managers.cardEffects import (buildEffectConfig, effectiveGate, effectiveGateThreshold,
                                  gateRatio, withEffectiveGate)
from managers.cardManager import CardManager

fails = []


def expect(desc, ok):
    print(("  [OK] " if ok else "  [FAIL] ") + desc)
    if not ok:
        fails.append(desc)


def pinFormat(scale, label):
    # Pin the cached live format so the test never depends on the local DB's rules.
    ce._FORMAT_GATE_CACHE["info"] = (scale, label)
    ce._FORMAT_GATE_CACHE["at"] = time.monotonic() + 3600


cfg = buildEffectConfig("holographic", 92, 1, None, forceEffect="eminence")
base = cfg["gate"]["threshold"]
storedBefore = dict(cfg["gate"])

print("1. Standard week: nothing moves")
pinFormat(1.0, None)
expect("threshold unchanged", effectiveGateThreshold(base) == base)
expect("gate returned as-is (no copy)", effectiveGate(cfg["gate"]) is cfg["gate"])

print("2. Innings week (x1.32)")
pinFormat(1.32, "Innings")
inForce = max(1, round(base * 1.32))
expect(f"bar {base} -> {inForce}", effectiveGateThreshold(base) == inForce)
ctx = lambda fp: N(isProjection=False, weekPlayerStats={151: {"fantasyPoints": fp}})
expect(f"scoring: {inForce - 1} FP misses", gateRatio(cfg["gate"], ctx(inForce - 1), 151) == 0.0)
expect(f"scoring: {inForce} FP clears", gateRatio(cfg["gate"], ctx(inForce), 151) == 1.0)

eff = withEffectiveGate(cfg)
expect("config gate carries the bar in force", eff["gate"]["threshold"] == inForce)
expect("...and the frozen bar as baseThreshold", eff["gate"]["baseThreshold"] == base)
expect(f"gateText states the bar in force ({inForce}) and does not name the format",
       f"reaches {inForce} FP" in eff["gateText"] and "Innings" not in eff["gateText"])
expect("the stored config is not mutated", cfg["gate"] == storedBefore)

print("3. serializeCard ships the bar in force (card face, lineup meter, gate line)")
tpl = N(id=1, player_id=151, player_name="X", team_id=None, team=None, player_rating=92,
        position=1, edition="holographic", effect_config=cfg, season_created=1,
        is_rookie=False, classification=None, is_synthetic=False, is_upgraded=False,
        is_showpiece=False, sell_value=10)
uc = N(id=1, card_template=tpl, card_template_id=1, tier=1, vaulted=False, vault_position=None,
       glitched=False, glitched_season=None, glitched_week=None, acquired_at=None,
       acquired_via="test")
card = CardManager(None).serializeCard(uc, 1)
expect("effectConfig.gate.threshold", card["effectConfig"]["gate"]["threshold"] == inForce)
expect("gateText", f"reaches {inForce} FP" in (card["gateText"] or ""))
expect("template row untouched", tpl.effect_config["gate"]["threshold"] == base)

print("4. Every calculator read of a card's bar goes through effectiveGateThreshold")
lines = open("managers/cardEffectCalculator.py").read().splitlines()
raw = [f"line {i + 1}: {ln.strip()}" for i, ln in enumerate(lines)
       if 'get("threshold"' in ln and "gate" in ln.lower()
       # the statement itself: this line, plus the previous one only when it opens the
       # call this line continues (an import or a comment above must not count)
       and "effectiveGateThreshold(" not in
       ((lines[i - 1] if i and lines[i - 1].rstrip().endswith("(") else "") + ln)]
expect(f"no raw gate threshold reads ({raw})", not raw)

ce._FORMAT_GATE_CACHE["at"] = 0.0
if fails:
    print(f"FAIL ({len(fails)})")
    raise SystemExit(1)
print("ALL PASS")
