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


def _defaultConversionLadder() -> List[Dict[str, Any]]:
    """The default Conversion-Ladder rungs (the ADDED 3/4/5-point tries). Sourced
    from constants so there's one tunable place; falls back to a hardcoded copy if
    constants can't be imported (keeps a bare GameRules() construction safe)."""
    try:
        from constants import CONVERSION_LADDER_RUNGS
        return [dict(r) for r in CONVERSION_LADDER_RUNGS]
    except Exception:
        return [{"points": 3, "distance": 5}, {"points": 4, "distance": 10}, {"points": 5, "distance": 15}]


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

    # ── Clock stoppage (the Cores can flip this to a "running clock") ──
    # One general dead-ball rule: when True (standard football) the clock stops on an
    # incompletion, going out of bounds, AND a turnover. When False it's a RUNNING CLOCK
    # — none of those stop it, so the inter-play clock keeps draining and games have far
    # fewer plays. (A score, FG, punt, or spike always stops the clock regardless.)
    clockStopsOnDeadBall: bool = True

    # ── Scoring values ─────────────────────────────────────────────
    touchdownPoints: int = 6
    fieldGoalPoints: int = 3
    extraPointPoints: int = 1
    twoPointConversionPoints: int = 2
    safetyPoints: int = 2

    # ── Score display model (presentation only) ────────────────────
    # How the running tally is SHOWN, not the points earned. The engine
    # still tracks cumulative points and decides the winner by them — this
    # is a lens over the two scores at the render sites only. No engine,
    # decision, or fairness effect. 'additive' = each team's cumulative
    # points (today's behavior); 'spread' = leader-centric margin (+N/-N,
    # EVEN on tie); 'share' = each team's % of total points scored.
    scoringModel: str = 'additive'

    # ── Conversion Ladder (dormant mechanic) ──────────────────────
    # When enabled, the post-TD try becomes a ladder: the safe 1-pt kick and the
    # 2-pt try always exist; these rungs add higher-value tries from further out.
    # `conversionLadder` = ordered [{points, distance}] for the ADDED rungs (1 and
    # 2 come from extraPointPoints / twoPointConversionPoints + their distances).
    # A complex collection, so it's excluded from applyPatch (mutated wholesale,
    # like fieldGoalUprights); the on/off gate is the votable scalar.
    conversionLadderEnabled: bool = False
    conversionLadder: List[Dict[str, Any]] = field(default_factory=lambda: _defaultConversionLadder())

    # ── Drive Clock (dormant mechanic) ─────────────────────────────
    # A shot-clock for possessions. `driveClockUnit` = what it counts
    # ('seconds' of game clock, pausing when the game clock stops, or
    # 'plays' — one per snap). `driveClockReset` = when it refills
    # ('possession' = a hard cap on the whole drive, 'series' = refills
    # on each first down). Expire before scoring (or a first down, in
    # series mode) → turnover on downs at the spot. Off by default;
    # a Cores vote picks a preset. Scalars, so all four fields are
    # mutable (the preset applies them as a patch).
    driveClockEnabled: bool = False
    driveClockUnit: str = 'seconds'        # 'seconds' | 'plays'
    driveClockReset: str = 'possession'    # 'possession' | 'series'
    driveClockLimit: int = 90              # seconds or plays, per the unit

    # ── Sideline Goals (dormant mechanic) ──────────────────────────
    # Quidditch-style: on any down the offense may throw at a sideline hoop for
    # bonus points. A MAKE banks `sidelineGoalPoints` and CONSUMES the down but the
    # drive continues (no yards gained → repeated shots march toward a turnover on
    # downs). A MISS is a turnover at the current line of scrimmage (a rare tipped
    # throw is a returnable INT). Make prob emerges from the QB's accuracy/arm vs the
    # hoop, minus defensive pressure (tunables in constants.py `SIDELINE_GOAL_*`).
    # Off by default; a Cores vote flips the gate. Fine-grained 1-pt scoring is the
    # prerequisite for the 'bust'/darts game format (which bundles this on).
    sidelineGoalsEnabled: bool = False
    sidelineGoalPoints: int = 1            # points banked per made hoop shot

    # Contested Scoring (dormant mechanic — docs/CONTESTED_SCORING_PLAN.md). When on, a
    # rushing / receiving / QB-scramble TD is only PROVISIONAL: the scorer completes an
    # action (dunk/race/arm-wrestle/beauty/backflip, each keyed to a real attribute) to
    # bank it, and the best-suited defender gets one last-resort contest to cancel it (a
    # stuff = no points, back to the play's LOS, down advances). Tunables in constants
    # `CONTEST_*`. Off by default; a Cores vote flips the gate.
    contestedScoringEnabled: bool = False

    # ── Game format / win condition (dormant) ──────────────────────
    # How the game is won / when it ends. 'standard' = today (cumulative
    # score, higher wins at the end of regulation/OT). Alternates change
    # the win condition or the game loop — one format at a time, set by a
    # Cores vote preset (docs/GAME_FORMATS_PLAN.md). `targetScore` is the
    # finish line for the 'target' format (first to X). Other formats add
    # their own config as they're built.
    gameFormat: str = 'standard'           # 'standard' | 'target' | 'play_limit' | 'chess_clock' | 'innings' | 'frames' | 'bust'
    targetScore: int = 30                  # 'target' format: first to this many points wins
    playsPerQuarter: int = 30              # 'play_limit' format: fixed plays per quarter (no clock)
    offenseClockBudgetSeconds: int = 1080  # 'chess_clock' format: each team's offense-time budget (18:00)
    inningsPerGame: int = 3                # 'innings' format: innings each team bats (no clock)
    triesPerInning: int = 3                # 'innings' format: possession-ends (tries) per at-bat
    framesPerGame: int = 6                 # 'frames' format: match-play frames (win a frame = +1; most frames wins)

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
            "patchHistory", "fieldGoalUprights", "conversionLadder",
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
            "clockStopsOnDeadBall": self.clockStopsOnDeadBall,
            "touchdownPoints": self.touchdownPoints,
            "fieldGoalPoints": self.fieldGoalPoints,
            "extraPointPoints": self.extraPointPoints,
            "twoPointConversionPoints": self.twoPointConversionPoints,
            "safetyPoints": self.safetyPoints,
            "scoringModel": self.scoringModel,
            "conversionLadderEnabled": self.conversionLadderEnabled,
            "conversionLadder": [dict(r) for r in self.conversionLadder],
            "gameFormat": self.gameFormat,
            "targetScore": self.targetScore,
            "playsPerQuarter": self.playsPerQuarter,
            "offenseClockBudgetSeconds": self.offenseClockBudgetSeconds,
            "inningsPerGame": self.inningsPerGame,
            "triesPerInning": self.triesPerInning,
            "framesPerGame": self.framesPerGame,
            "driveClockEnabled": self.driveClockEnabled,
            "driveClockUnit": self.driveClockUnit,
            "driveClockReset": self.driveClockReset,
            "driveClockLimit": self.driveClockLimit,
            "sidelineGoalsEnabled": self.sidelineGoalsEnabled,
            "contestedScoringEnabled": self.contestedScoringEnabled,
            "sidelineGoalPoints": self.sidelineGoalPoints,
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
    # Score DISPLAY model — presentation only (additive / spread / share).
    # Zero engine blast radius: every score consumer reads the real cumulative
    # values; only the frontend render sites apply the lens. Safe to mutate.
    "scoringModel",
    # Conversion Ladder on/off gate (the rung LIST rides on gameRules.conversionLadder,
    # a complex collection mutated wholesale — not a votable scalar). Contained in
    # the post-TD conversion path.
    "conversionLadderEnabled",
    # Drive Clock — all four scalar fields are mutable; a vote preset applies them
    # together as a patch (enabled + unit + reset + limit). Contained in the
    # possession/down loop + the situational play-weights.
    "driveClockEnabled", "driveClockUnit", "driveClockReset", "driveClockLimit",
    # Sideline Goals — on/off gate + the point value per made hoop shot. Contained
    # in the play-calling + resolution path (a new hoop-shot play type).
    "sidelineGoalsEnabled", "sidelineGoalPoints",
    # Contested Scoring — on/off gate; contained in the TD scoring-resolution step.
    "contestedScoringEnabled",
    # Game format / win condition — one format at a time; a vote preset sets the
    # format + its config together. targetScore is the 'target' finish line;
    # playsPerQuarter is the 'play_limit' per-quarter play budget;
    # offenseClockBudgetSeconds is each team's 'chess_clock' offense-time budget;
    # inningsPerGame/triesPerInning configure the 'innings' format;
    # framesPerGame configures the 'frames' (match-play) format.
    "gameFormat", "targetScore", "playsPerQuarter", "offenseClockBudgetSeconds",
    "inningsPerGame", "triesPerInning", "framesPerGame",
    # Structural rule #1 — yards needed to convert a first down. Core mechanic
    # (reset/decrement/goal-to-go) reads gameRules; play-calling heuristics use
    # the live yardsToFirstDown so they degrade gracefully at non-default values.
    "firstDownDistance",
    # Structural rule #2 — number of downs in a series. Core flow (possession
    # loop bound, advance-vs-turnover, final-down punt/FG/go decision, kneel
    # count, spike availability, down-text/PlayResult) all reference this.
    # Down-text + PlayResult support up to 6 downs (downOrdinal/downPlayResult).
    "downsPerSeries",
    # Clock / FG knobs — already read from gameRules throughout the engine, so
    # these are low-blast-radius scalars (the two-minute pressure heuristics are
    # a separate concept and stay fixed). kneelDrainSeconds is the single source
    # of truth for the per-kneel drain (snap 4s + play-clock kneelDrainSeconds-4).
    "overtimeLengthSeconds", "timeoutClockThreshold", "spikeClockThreshold",
    "kneelDrainSeconds", "fgSnapDistance",
    # Running-clock rule — one general dead-ball toggle: suppress the incompletion /
    # out-of-bounds / turnover clock stops (gated in shouldClockRun). Far fewer plays
    # per game. Clock-management play-calling heuristics still assume dead balls stop
    # the clock, so they degrade gracefully (a later pass can make them rule-aware).
    "clockStopsOnDeadBall",
}

# ── What the Rulebook currently EXPOSES as changeable ───────────────────────
# A deliberately small, curated subset of MUTABLE_RULE_FIELDS: the rules we
# actually intend to surface as changeable RIGHT NOW (foreshadowed in the
# Rulebook UI). The engine can safely mutate everything in MUTABLE_RULE_FIELDS,
# but the design surface starts narrow and grows. For now: downs, the core
# scoring values (TD / FG / safety), and the two clock-STOPPAGE rules only.
# Deliberately EXCLUDED: extraPointPoints + twoPointConversionPoints (those fall
# under the future "Conversion Ladder" mechanic, not standalone value tweaks);
# clock TIMING (OT length, spike/timeout windows, kneel drain) and FG geometry
# stay hidden until we choose to expose them. Intersected with
# MUTABLE_RULE_FIELDS so this can never claim a rule the engine can't apply.
RULEBOOK_EXPOSED_FIELDS = {
    "downsPerSeries", "firstDownDistance",
    "touchdownPoints", "fieldGoalPoints", "safetyPoints",
    "clockStopsOnDeadBall",
    # The score DISPLAY model — surfaced as the Rulebook's own "Scoring Model"
    # row (its own presentation), and votable like the rest.
    "scoringModel",
    # Conversion Ladder — a dormant on/off mechanic (surfaced in the Rulebook's
    # "Dormant Rules" list, votable on).
    "conversionLadderEnabled",
    # Drive Clock gate — the dormant mechanic's on/off marker (the mode config
    # rides alongside in `rules`, shown as the active preset).
    "driveClockEnabled",
    # Sideline Goals gate — dormant on/off mechanic (Rulebook "Dormant Rules" list).
    "sidelineGoalsEnabled",
    # Contested Scoring gate — dormant on/off mechanic (Rulebook "Dormant Rules" list).
    "contestedScoringEnabled",
    # Game format gate — surfaced as the Rulebook's "Game Format" row (the active
    # format + its config); the config (targetScore, ...) rides alongside in `rules`.
    "gameFormat",
} & MUTABLE_RULE_FIELDS

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


def clearRuleOverrides() -> None:
    """Wipe all persisted rule overrides — the league returns to the pristine
    defaults. Called at season start so each season begins on a clean rulebook and
    the fan-voted mutations only live for the season that voted them in."""
    saveRuleOverrides({})


def defaultRuleValue(field: str) -> Any:
    """The pristine default for a rule field (from a fresh GameRules)."""
    return getattr(GameRules(), field, None)


def applyRuleChange(gameRules: "GameRules", field: str, value: Any,
                    reason: str = "cores vote", source: str = "cores_vote"):
    """Apply a single rule change to the LIVE gameRules object AND persist it.

    The live patch takes effect on every game that reads this shared instance; the
    persisted override map (app_settings) survives restarts and is re-applied at each
    Season.__init__, so the change drifts into future seasons until reverted. Returns
    the new override map, or None if the field isn't mutable (a no-op guard)."""
    if field not in MUTABLE_RULE_FIELDS:
        return None
    gameRules.applyPatch(field, value, reason=reason, source=source)
    overrides = loadRuleOverrides()
    overrides[field] = value
    saveRuleOverrides(overrides)
    return overrides


def revertRule(gameRules: "GameRules", field: str,
               reason: str = "cores revert", source: str = "cores_vote"):
    """Restore a rule field to its default on the LIVE gameRules object and drop it
    from the persisted override map. Returns the new override map, or None if the
    field isn't mutable."""
    if field not in MUTABLE_RULE_FIELDS:
        return None
    gameRules.applyPatch(field, defaultRuleValue(field), reason=reason, source=source)
    overrides = loadRuleOverrides()
    overrides.pop(field, None)
    saveRuleOverrides(overrides)
    return overrides
