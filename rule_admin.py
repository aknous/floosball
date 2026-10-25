"""The admin's view of the league ruleset, and the admin's way to change it.

The slate is the same set of rules fans see in the Rulebook and vote on
(`constants.RULE_VOTE_CANDIDATES`): scalars (downs, yards to a first down, score values),
on/off mechanics, the score display, and two preset rules (Game Format, Drive Clock).
Changes go through `game_rules.applyRuleChange` / `revertRule`, the same path a resolved
vote takes, so the live season ruleset and the persisted `rule_overrides` map move
together. Like a vote, a change lasts until the next season starts
(`maybeResetRuleOverridesForSeason` returns the rulebook to standard then).

⚠️ No news is published: an admin change is not something fans did. Post an
announcement from the News tab if one is wanted.
"""
from typing import Any, Dict, List, Optional

import game_rules as gr

ADMIN_SOURCE = "admin"

# The "nothing on" option of each preset rule.
_PRESET_OFF = {"gameFormat": ("standard", "Standard"), "driveClock": ("off", "Off")}


def _spec(key: str) -> dict:
    from constants import RULE_VOTE_CANDIDATES
    spec = RULE_VOTE_CANDIDATES.get(key)
    if spec is None:
        raise ValueError(f"Unknown rule: {key}")
    return spec


def _currentPresetKey(key: str, spec: dict, gameRules) -> str:
    """Which preset is in force: the 'off' key when the gate is at its default, the
    preset whose patch matches every live field, else 'custom'."""
    gate = spec["gate"]
    if getattr(gameRules, gate, None) == gr.defaultRuleValue(gate):
        return _PRESET_OFF[key][0]
    for p in spec["presets"]:
        if all(getattr(gameRules, f, None) == v for f, v in p["patch"].items()):
            return p["key"]
    return "custom"


def _activePreset(key: str, spec: dict, gameRules) -> Optional[dict]:
    """The preset owning the live gate value (matched on the gate field alone), so a
    format can be switched off cleanly even if one of its config fields was edited."""
    gate = spec["gate"]
    live = getattr(gameRules, gate, None)
    if live == gr.defaultRuleValue(gate):
        return None
    for p in spec["presets"]:
        if p["patch"].get(gate) == live:
            return p
    return None


def describeRules(gameRules) -> List[Dict[str, Any]]:
    """Every rule on the slate with its live value, its standard value and what it can
    be set to. Order follows `RULE_VOTE_CANDIDATES`."""
    from constants import RULE_VOTE_CANDIDATES
    out = []
    for key, spec in RULE_VOTE_CANDIDATES.items():
        label = spec.get("label", key)
        if "presets" in spec:
            offKey, offLabel = _PRESET_OFF[key]
            current = _currentPresetKey(key, spec, gameRules)
            options = [{"key": offKey, "label": offLabel}] + [
                {"key": p["key"], "label": p["label"]} for p in spec["presets"]]
            out.append({
                "key": key, "label": label, "kind": "preset",
                "current": current, "default": offKey, "changed": current != offKey,
                "options": options,
                # The raw fields, so a 'custom' state can still be read.
                "fields": {f: getattr(gameRules, f, None)
                           for p in spec["presets"] for f in p["patch"]},
            })
            continue
        current = getattr(gameRules, key, None)
        default = gr.defaultRuleValue(key)
        entry = {"key": key, "label": label, "current": current, "default": default,
                 "changed": current != default}
        labels = spec.get("valueLabels") or {}
        if "values" in spec:
            values = [default] + [v for v in spec["values"] if v != default]
            entry["kind"] = "toggle" if isinstance(default, bool) else "choice"
            entry["options"] = [{"value": v, "label": labels.get(v, str(v))} for v in values]
        else:
            lo, hi = spec["range"]
            entry["kind"] = "number"
            entry["range"] = {"min": lo, "max": hi, "float": bool(spec.get("float"))}
        out.append(entry)
    return out


def _coerce(key: str, spec: dict, value: Any) -> Any:
    """Validate a scalar against its spec; standard is always allowed."""
    default = gr.defaultRuleValue(key)
    if "values" in spec:
        allowed = [default] + list(spec["values"])
        for a in allowed:
            if value == a and type(value) is type(a):
                return a
        # JSON numbers arrive as int/float; accept a numerically equal choice.
        for a in allowed:
            if not isinstance(a, bool) and not isinstance(value, bool) \
                    and isinstance(value, (int, float)) and value == a:
                return a
        raise ValueError(f"{spec.get('label', key)} can't be {value!r}")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{spec.get('label', key)} needs a number")
    lo, hi = spec["range"]
    if spec.get("float"):
        value = round(float(value), 1)
        if value == int(value):
            value = int(value)
    elif value != int(value):
        raise ValueError(f"{spec.get('label', key)} must be a whole number")
    else:
        value = int(value)
    if value == default:
        return value
    if not (lo <= value <= hi):
        raise ValueError(f"{spec.get('label', key)} must be between {lo} and {hi}")
    return value


def setRule(gameRules, key: str, value: Any = None, preset: Optional[str] = None) -> List[str]:
    """Set one rule. A scalar takes `value`; a preset rule takes `preset` (a preset key,
    or 'standard' / 'off'). Setting a rule to its standard value REVERTS it, so the
    override map only ever holds real changes. Returns the fields touched.
    Raises ValueError on a bad key or value."""
    spec = _spec(key)
    touched: List[str] = []
    if "presets" in spec:
        offKey = _PRESET_OFF[key][0]
        if preset != offKey and not any(p["key"] == preset for p in spec["presets"]):
            raise ValueError(f"Unknown {spec.get('label', key)} option: {preset!r}")
        # Clear the preset in force first, so switching formats does not leave the old
        # format's config behind (a Darts target under Frames).
        active = _activePreset(key, spec, gameRules)
        clear = list(active["patch"]) if active else [spec["gate"]]
        for f in clear:
            gr.revertRule(gameRules, f, reason="admin", source=ADMIN_SOURCE)
            touched.append(f)
        if preset != offKey:
            patch = next(p for p in spec["presets"] if p["key"] == preset)["patch"]
            for f, v in patch.items():
                if v == gr.defaultRuleValue(f):
                    gr.revertRule(gameRules, f, reason="admin", source=ADMIN_SOURCE)
                else:
                    gr.applyRuleChange(gameRules, f, v, reason="admin", source=ADMIN_SOURCE)
                if f not in touched:
                    touched.append(f)
        return touched
    v = _coerce(key, spec, value)
    if v == gr.defaultRuleValue(key):
        gr.revertRule(gameRules, key, reason="admin", source=ADMIN_SOURCE)
    else:
        gr.applyRuleChange(gameRules, key, v, reason="admin", source=ADMIN_SOURCE)
    return [key]


def resetAllRules(gameRules) -> List[str]:
    """Every overridden field back to standard, live and persisted. Returns the fields
    that were reverted."""
    fields = list(gr.loadRuleOverrides().keys())
    for f in fields:
        gr.revertRule(gameRules, f, reason="admin reset", source=ADMIN_SOURCE)
    gr.saveRuleOverrides({})
    return fields
