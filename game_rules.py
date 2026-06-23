"""Game rules — the configurable contract the simulation reads from.

Historically, football rule numbers (field length, down counts, score
values, quarter length, FG range mechanics) were sprinkled through the
codebase as magic numbers or as flat constants in ``constants.py``. The
sim treated those as immutable facts.

The ``GameRules`` dataclass extracts every such rule into a single
object the simulation reads from at decision time. Default values match
real football, so wiring the sim to ``GameRules`` is a pure refactor
with no behavior change.

Down the road, the Cores' simulation-patching gameplay layer will
mutate rule values per-season (or mid-season) to respond to anomaly
buildup. When that ships, every consumer is already rule-aware — only
the trigger and the patch payload need building.

Lifecycle:
  - Each ``Season`` carries one ``GameRules`` instance.
  - Each ``Game`` is constructed with a reference to that season's
    rules (passed through ``Game.__init__``).
  - Sim code references ``self.gameRules.<field>`` instead of magic
    numbers or constants module imports.
  - ``patchHistory`` accumulates every Cores intervention as an audit
    trail surfaced to users in a future "rules ledger" UI.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any


@dataclass
class GameRules:
    """All configurable football rules in one place.

    Defaults reflect the standard ruleset the sim has always used.
    Mutate via ``applyPatch()`` so the audit trail stays consistent.
    """

    # ── Field geometry ─────────────────────────────────────────────
    fieldLength: int = 100              # Goal line to goal line (yards)
    endZoneDepth: int = 10              # Per end zone (yards)
    kickoffPosition: int = 35           # Kicking team's yard line for kickoff

    # ── Series mechanics ───────────────────────────────────────────
    firstDownDistance: int = 10         # Yards to convert a first down
    downsPerSeries: int = 4             # Plays before turnover on downs
    twoPointConversionDistance: int = 2 # Line of scrimmage for 2-pt try
    patSnapDistance: int = 15           # Yards from goal line for PAT setup

    # ── Game clock ─────────────────────────────────────────────────
    quarterLengthSeconds: int = 900     # 15 min quarters
    quartersPerGame: int = 4
    overtimeLengthSeconds: int = 600    # 10 min OT period
    suddenDeathStartsAtOt: int = 2      # 2nd+ OT period is sudden death
    twoMinuteWarningSeconds: int = 120
    spikeClockThreshold: int = 120      # Below this in Q2/Q4, spike considered
    timeoutClockThreshold: int = 120    # Below this in Q2/Q4, timeout considered
    kneelDrainSeconds: int = 40         # Clock burned per kneel

    # ── Scoring values ─────────────────────────────────────────────
    touchdownPoints: int = 6
    fieldGoalPoints: int = 3
    extraPointPoints: int = 1
    twoPointConversionPoints: int = 2
    safetyPoints: int = 2

    # ── Field goal mechanics ───────────────────────────────────────
    fgSnapDistance: int = 17            # Yards added to LOS for snap + hold
    fgMinAttemptProb: float = 0.20      # Coaches attempt FG if make-prob >= this

    # ── Multiple uprights (future: Cores may add weird ones) ───────
    # Each entry: { "name": str, "value": int, "rangeBonus": int }
    # The default ruleset has only the standard 3-point upright.
    # rangeBonus shifts effective distance for that upright (positive
    # = easier, negative = harder). Defaults to 0.
    fieldGoalUprights: List[Dict[str, Any]] = field(default_factory=lambda: [
        {"name": "standard", "value": 3, "rangeBonus": 0},
    ])

    # ── Audit trail ────────────────────────────────────────────────
    # Each entry: { "appliedAt": ISO datetime str, "field": str,
    #               "previousValue": Any, "newValue": Any,
    #               "reason": str, "source": "core_patch" | "manual" | ... }
    # Cores' "Conservators have determined that ..." news entries
    # generate one record per rule touched.
    patchHistory: List[Dict[str, Any]] = field(default_factory=list)

    # ── Methods ────────────────────────────────────────────────────
    def applyPatch(self, fieldName: str, newValue: Any,
                   reason: str = "", source: str = "core_patch") -> bool:
        """Mutate a rule and record the change in patchHistory.

        Returns True on success, False if fieldName isn't a real rule
        field (typo-proofing against future patch authors).
        """
        from datetime import datetime
        if not hasattr(self, fieldName) or fieldName in {
            "patchHistory", "fieldGoalUprights",
        }:
            # patchHistory and complex collections need their own
            # purpose-built mutators rather than generic apply.
            return False
        previousValue = getattr(self, fieldName)
        setattr(self, fieldName, newValue)
        self.patchHistory.append({
            "appliedAt": datetime.utcnow().isoformat() + "Z",
            "field": fieldName,
            "previousValue": previousValue,
            "newValue": newValue,
            "reason": reason,
            "source": source,
        })
        return True

    def toDict(self) -> Dict[str, Any]:
        """Serialize for API responses / DB persistence."""
        return {
            "fieldLength": self.fieldLength,
            "endZoneDepth": self.endZoneDepth,
            "kickoffPosition": self.kickoffPosition,
            "firstDownDistance": self.firstDownDistance,
            "downsPerSeries": self.downsPerSeries,
            "twoPointConversionDistance": self.twoPointConversionDistance,
            "patSnapDistance": self.patSnapDistance,
            "quarterLengthSeconds": self.quarterLengthSeconds,
            "quartersPerGame": self.quartersPerGame,
            "overtimeLengthSeconds": self.overtimeLengthSeconds,
            "suddenDeathStartsAtOt": self.suddenDeathStartsAtOt,
            "twoMinuteWarningSeconds": self.twoMinuteWarningSeconds,
            "spikeClockThreshold": self.spikeClockThreshold,
            "timeoutClockThreshold": self.timeoutClockThreshold,
            "kneelDrainSeconds": self.kneelDrainSeconds,
            "touchdownPoints": self.touchdownPoints,
            "fieldGoalPoints": self.fieldGoalPoints,
            "extraPointPoints": self.extraPointPoints,
            "twoPointConversionPoints": self.twoPointConversionPoints,
            "safetyPoints": self.safetyPoints,
            "fgSnapDistance": self.fgSnapDistance,
            "fgMinAttemptProb": self.fgMinAttemptProb,
            "fieldGoalUprights": list(self.fieldGoalUprights),
            "patchHistory": list(self.patchHistory),
        }

    def applyOverrides(self, overrides: Dict[str, Any],
                       reason: str = "persisted override",
                       source: str = "core_patch") -> List[str]:
        """Apply a ``{field: value}`` override map via ``applyPatch`` (audit-logged).

        Only fields in ``MUTABLE_RULE_FIELDS`` are applied — the remaining
        structural rules (field length / geometry, clock) are gated out until
        the sim's heuristics are safe under non-default values. Unknown/blocked
        fields are silently skipped. Returns the field names actually applied.
        """
        applied: List[str] = []
        for fieldName, value in (overrides or {}).items():
            if fieldName not in MUTABLE_RULE_FIELDS:
                continue
            if self.applyPatch(fieldName, value, reason=reason, source=source):
                applied.append(fieldName)
        return applied


# Module-level default — used by code paths that need to fall back to
# standard rules when no Season-scoped instance is available (tests,
# isolated game sims, etc.).
DEFAULT_RULES = GameRules()


# ── Rule-override persistence (the Cores' rule-mutation layer) ──────────────
# The current set of rules safe to mutate at runtime:
#   - scoring values + the FG attempt threshold (proven: every _addScore site
#     reads gameRules; see the rainbow-override proof);
#   - structural rules #1 firstDownDistance and #2 downsPerSeries (proven: down
#     distribution bounds at downsPerSeries, fresh-1st-down distance tracks the
#     override, scoring moves monotonically).
# STILL GATED OUT: field geometry (fieldLength / endZoneDepth / kickoffPosition)
# and clock rules — these touch the field-position model + win-probability (which
# feeds MVP/All-Pro/pick-em) and need an exhaustive sweep first. The next pass
# should wire fieldLength together with kickoffPosition. See docs/SIM_EVOLUTION.md.
MUTABLE_RULE_FIELDS = {
    "touchdownPoints", "fieldGoalPoints", "extraPointPoints",
    "twoPointConversionPoints", "safetyPoints", "fgMinAttemptProb",
    # Structural rule #1 — yards needed to convert a first down. Core mechanic
    # (reset/decrement/goal-to-go) reads gameRules; play-calling heuristics use
    # the live yardsToFirstDown so they degrade gracefully at non-default values.
    "firstDownDistance",
    # Structural rule #2 — number of downs in a series. Core flow (possession
    # loop bound, advance-vs-turnover, final-down punt/FG/go decision, kneel
    # count, spike availability, down-text/PlayResult) all reference this.
    # Down-text + PlayResult support up to 6 downs (downOrdinal/downPlayResult).
    "downsPerSeries",
}

RULE_OVERRIDES_SETTING_KEY = "rule_overrides"


def loadRuleOverrides() -> Dict[str, Any]:
    """Read the persisted rule-override map from ``app_settings``.

    Returns ``{}`` on any error (missing table, no row, bad JSON) so a fresh or
    test DB simply runs the default ruleset.
    """
    try:
        import json
        from sqlalchemy import text
        from database.connection import SessionLocal
        session = SessionLocal()
        try:
            row = session.execute(
                text("SELECT value FROM app_settings WHERE key = :k"),
                {"k": RULE_OVERRIDES_SETTING_KEY},
            ).fetchone()
        finally:
            session.close()
        if not row or not row[0]:
            return {}
        data = json.loads(row[0])
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def saveRuleOverrides(overrides: Dict[str, Any]) -> None:
    """Upsert the rule-override map into ``app_settings`` (the persistent store)."""
    import json
    from datetime import datetime
    from sqlalchemy import text
    from database.connection import SessionLocal
    session = SessionLocal()
    try:
        session.execute(
            text("INSERT INTO app_settings (key, value, updated_at) "
                 "VALUES (:k, :v, :t) "
                 "ON CONFLICT(key) DO UPDATE SET value = :v, updated_at = :t"),
            {"k": RULE_OVERRIDES_SETTING_KEY, "v": json.dumps(overrides),
             "t": datetime.utcnow()},
        )
        session.commit()
    finally:
        session.close()
