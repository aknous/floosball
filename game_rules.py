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


# Module-level default — used by code paths that need to fall back to
# standard rules when no Season-scoped instance is available (tests,
# isolated game sims, etc.).
DEFAULT_RULES = GameRules()
