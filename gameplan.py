"""
Gameplan module — pre-game coaching strategy + per-play defensive scheme selection.

OffensiveGameplan: run/pass ratio, gap distribution, pass depth, aggressiveness.
DefensiveGameplan: coverage type, blitz packages, run-stop focus, aggressiveness.
getDefensiveScheme(): per-play multipliers + coverage/blitz decisions.
adjustOffensiveGameplan(): halftime adjustment based on first-half offensive stats.
adjustDefensiveGameplan(): halftime adjustment based on what opponent's offense did.
"""

import random as _random
import numpy as np
from enum import Enum

from constants import RATING_SCALE_MIN, RATING_RANGE


# ---------------------------------------------------------------------------
# Coverage & Blitz enums
# ---------------------------------------------------------------------------

class CoverageType(Enum):
    """How the secondary covers receivers on a given play."""
    MAN = 'man'       # 1-on-1; individual matchups dominate
    ZONE = 'zone'     # Area-based; pooled coverage, soft spots between zones
    MATCH = 'match'   # Hybrid; start zone, switch to man when receiver enters zone

class BlitzPackage(Enum):
    """Who rushes the QB beyond the base DE pass rush."""
    BASE = 'base'           # DE only — no extra rushers
    LB_BLITZ = 'lb_blitz'   # DE + LB — TE left uncovered
    SAFETY_BLITZ = 'safety_blitz'  # DE + S — deep help gone, big play risk
    ALL_OUT = 'all_out'     # DE + LB + S — massive pressure, skeletal coverage


# ---------------------------------------------------------------------------
# Offensive Gameplan
# ---------------------------------------------------------------------------

class OffensiveGameplan:
    def __init__(self):
        self.runPassRatio: float = 0.5            # 0=all pass, 1=all run
        self.gapDistribution: dict = {'A-gap': 0.33, 'B-gap': 0.33, 'C-gap': 0.34}
        self.passDepthDistribution: dict = {'short': 0.50, 'medium': 0.35, 'long': 0.15}
        self.aggressiveness: float = 0.5          # affects 4th-down go-for-it thresholds


def generateOffensiveGameplan(coach, offenseTeam, defenseTeam) -> OffensiveGameplan:
    """
    Build a pre-game offensive gameplan from coach scouting of the opponent.
    Falls back to neutral defaults if coach is None.
    """
    plan = OffensiveGameplan()
    if coach is None:
        return plan

    accuracy = (coach.offensiveMind - RATING_SCALE_MIN) / RATING_RANGE  # 0.0 at 60, 1.0 at 100
    noise = (1.0 - accuracy) * 0.25

    # Evaluate RB vs. opponent run defense
    rb = getattr(offenseTeam, 'rosterDict', {}).get('rb', None)
    rbPower = getattr(getattr(rb, 'attributes', None), 'power', 50) if rb else 50
    rbSpeed = getattr(getattr(rb, 'attributes', None), 'speed', 50) if rb else 50
    oppRunDef = getattr(defenseTeam, 'defenseRunCoverageRating', 50)

    rbAvg = (rbPower + rbSpeed) / 2.0
    runAdvantage = (rbAvg - oppRunDef) / 100.0   # roughly -0.5 to +0.5

    plan.runPassRatio = float(np.clip(
        0.5 + runAdvantage * 0.3 + np.random.normal(0, noise),
        0.25, 0.75
    ))

    # Gap distribution: speed back → edge (C-gap), power back → inside (A-gap)
    isSpeedBack = rbSpeed > rbPower
    if isSpeedBack:
        baseGaps = {'A-gap': 0.25, 'B-gap': 0.30, 'C-gap': 0.45}
    else:
        baseGaps = {'A-gap': 0.45, 'B-gap': 0.35, 'C-gap': 0.20}

    for gap in baseGaps:
        baseGaps[gap] = max(0.05, baseGaps[gap] + float(np.random.normal(0, noise * 0.3)))
    total = sum(baseGaps.values())
    plan.gapDistribution = {k: v / total for k, v in baseGaps.items()}

    plan.aggressiveness = (coach.aggressiveness - RATING_SCALE_MIN) / RATING_RANGE  # 0.0–1.0
    return plan


# ---------------------------------------------------------------------------
# Defensive Gameplan
# ---------------------------------------------------------------------------

class DefensiveGameplan:
    def __init__(self):
        self.blitzFrequency: float = 0.25         # base blitz rate
        self.runStopFocus: float = 0.5            # 0=pass-focused, 1=run-focused
        self.aggressiveness: float = 0.5          # affects turnover-forcing tendencies
        self.defensiveMind: float = 0.5           # smart-coach factor (0-1 normalized)
        # Coverage assignments: opponent receiver slot → defending player
        # e.g. {'wr1': <PlayerWR acting as CB>, 'wr2': <PlayerWR>, 'te': <PlayerRB as LB>, 'rb': <PlayerQB as S>}
        self.coverageAssignments: dict = {}
        # Pass rusher: the defensive end (TE playing DE)
        self.passRusher = None

        # --- Phase 4: coverage & blitz ---
        # Base coverage tendency weights (sum to 1.0)
        self.coverageTendency: dict = {
            CoverageType.MAN: 0.45,
            CoverageType.ZONE: 0.40,
            CoverageType.MATCH: 0.15,
        }
        # Blitz package weights when a blitz IS called (sum to 1.0)
        self.blitzPackageWeights: dict = {
            BlitzPackage.LB_BLITZ: 0.55,
            BlitzPackage.SAFETY_BLITZ: 0.30,
            BlitzPackage.ALL_OUT: 0.15,
        }


def _assignCoverage(coach, defenseTeam, offenseTeam):
    """Assign individual defenders to opponent receivers.

    Defense positions (two-way):
      - defenseTeam WR1, WR2 → play CB (cover opponent WRs)
      - defenseTeam RB → plays LB (covers opponent TE)
      - defenseTeam QB → plays S (covers opponent RB / deep help)
      - defenseTeam TE → plays DE (pass rush, not coverage)

    Good coaches (high defensiveMind) match their best CB to the opponent's
    best WR. Poor coaches get it wrong ~60% of the time.
    """
    assignments = {}

    # Defensive players
    cb1 = getattr(defenseTeam, 'rosterDict', {}).get('wr1')  # CB
    cb2 = getattr(defenseTeam, 'rosterDict', {}).get('wr2')  # CB
    lb = getattr(defenseTeam, 'rosterDict', {}).get('rb')    # LB
    safety = getattr(defenseTeam, 'rosterDict', {}).get('qb') # S
    de = getattr(defenseTeam, 'rosterDict', {}).get('te')    # DE

    # Opponent receivers
    oppWr1 = getattr(offenseTeam, 'rosterDict', {}).get('wr1')
    oppWr2 = getattr(offenseTeam, 'rosterDict', {}).get('wr2')

    # Determine which CB is better at coverage
    if cb1 and cb2:
        cb1Cov = cb1.attributes.getDefensiveAttributes(cb1.position).get('coverage', 70)
        cb2Cov = cb2.attributes.getDefensiveAttributes(cb2.position).get('coverage', 70)
        bestCB, worstCB = (cb1, cb2) if cb1Cov >= cb2Cov else (cb2, cb1)

        # Determine which opponent WR is more dangerous
        oppWr1Rating = getattr(oppWr1, 'offensiveRating', 70) if oppWr1 else 70
        oppWr2Rating = getattr(oppWr2, 'offensiveRating', 70) if oppWr2 else 70
        bestOppSlot = 'wr1' if oppWr1Rating >= oppWr2Rating else 'wr2'
        worstOppSlot = 'wr2' if bestOppSlot == 'wr1' else 'wr1'

        # Coach quality determines if assignment is optimal
        if coach is not None:
            accuracy = (coach.defensiveMind - RATING_SCALE_MIN) / RATING_RANGE
            # Good coach: high chance of correct assignment
            # correctProb ranges from ~0.4 (worst coach) to ~1.0 (best coach)
            correctProb = 0.4 + accuracy * 0.6
            if _random.random() < correctProb:
                assignments[bestOppSlot] = bestCB
                assignments[worstOppSlot] = worstCB
            else:
                assignments[bestOppSlot] = worstCB
                assignments[worstOppSlot] = bestCB
        else:
            # No coach: random assignment
            assignments['wr1'] = cb1
            assignments['wr2'] = cb2
    else:
        # Fallback if missing CBs
        if cb1:
            assignments['wr1'] = cb1
        if cb2:
            assignments['wr2'] = cb2

    # LB covers opponent TE
    if lb:
        assignments['te'] = lb

    # Safety covers opponent RB (checkdowns / deep help)
    if safety:
        assignments['rb'] = safety

    return assignments, de


def generateDefensiveGameplan(coach, defenseTeam, offenseTeam) -> DefensiveGameplan:
    """
    Build a pre-game defensive gameplan from coach scouting of the opponent.
    Falls back to neutral defaults if coach is None.
    """
    plan = DefensiveGameplan()

    # Assign individual coverage even without a coach (random assignments)
    plan.coverageAssignments, plan.passRusher = _assignCoverage(coach, defenseTeam, offenseTeam)

    if coach is None:
        return plan

    accuracy = (coach.defensiveMind - RATING_SCALE_MIN) / RATING_RANGE  # 0.0 at 60, 1.0 at 100
    noise = (1.0 - accuracy) * 0.20

    # Evaluate opponent backfield vs. passing threat
    rb = getattr(offenseTeam, 'rosterDict', {}).get('rb', None)
    qb = getattr(offenseTeam, 'rosterDict', {}).get('qb', None)

    rbRating = getattr(rb, 'playerRating', RATING_SCALE_MIN) if rb else RATING_SCALE_MIN
    qbRating = getattr(qb, 'playerRating', RATING_SCALE_MIN) if qb else RATING_SCALE_MIN
    rbThreat = (rbRating - RATING_SCALE_MIN) / RATING_RANGE  # 0.0–1.0
    qbThreat = (qbRating - RATING_SCALE_MIN) / RATING_RANGE  # 0.0–1.0

    baseRunFocus = 0.5 + (rbThreat - qbThreat) * 0.3
    plan.runStopFocus = float(np.clip(
        baseRunFocus + np.random.normal(0, noise),
        0.2, 0.8
    ))

    aggrNorm = (coach.aggressiveness - RATING_SCALE_MIN) / RATING_RANGE  # 0.0–1.0
    plan.blitzFrequency = float(np.clip(
        aggrNorm * 0.4 + float(np.random.normal(0, noise * 0.5)),
        0.05, 0.5
    ))

    plan.aggressiveness = aggrNorm
    plan.defensiveMind = accuracy

    # --- Coverage tendency ---
    # Smart coaches (high defensiveMind) use more match coverage;
    # aggressive coaches favor man; conservative coaches favor zone.
    defMindNorm = accuracy  # reuse already-computed accuracy (0.0–1.0)
    manWeight = 0.35 + aggrNorm * 0.20       # aggressive → more man
    zoneWeight = 0.35 + (1 - aggrNorm) * 0.15  # conservative → more zone
    matchWeight = 0.10 + defMindNorm * 0.20   # smart → more match
    covTotal = manWeight + zoneWeight + matchWeight
    plan.coverageTendency = {
        CoverageType.MAN: manWeight / covTotal,
        CoverageType.ZONE: zoneWeight / covTotal,
        CoverageType.MATCH: matchWeight / covTotal,
    }

    # --- Blitz package weights ---
    # Aggressive coaches use more all-out blitzes; smart coaches use
    # targeted LB blitzes (lower risk) more than safety blitzes.
    lbWeight = 0.50 + defMindNorm * 0.15
    safetyWeight = 0.30 + aggrNorm * 0.10
    allOutWeight = 0.10 + aggrNorm * 0.15
    blitzTotal = lbWeight + safetyWeight + allOutWeight
    plan.blitzPackageWeights = {
        BlitzPackage.LB_BLITZ: lbWeight / blitzTotal,
        BlitzPackage.SAFETY_BLITZ: safetyWeight / blitzTotal,
        BlitzPackage.ALL_OUT: allOutWeight / blitzTotal,
    }

    return plan


# ---------------------------------------------------------------------------
# Per-play defensive scheme
# ---------------------------------------------------------------------------

def _pickCoverage(defGameplan, down: int, yardsToGo: int, quarter: int,
                   scoreDiff: int, clockSeconds: int) -> CoverageType:
    """Choose coverage type for this play based on tendency + situation +
    coach archetype.

    Defensive archetypes (parallel to offensive playcalling):
      - Predator (aggr × defMind): blitz-heavy man pressure when leading
      - Bend-Don't-Break ((1-aggr) × defMind): zone shell, prevent big play
      - Reckless Blitzer (aggr × (1-defMind)): predictable pressure
      - Vanilla (low both): no situational shift
    """
    weights = dict(defGameplan.coverageTendency)
    aggr = getattr(defGameplan, 'aggressiveness', 0.5)
    defMind = getattr(defGameplan, 'defensiveMind', 0.5)

    # Down/distance overrides (universal — apply to every defense)
    if down == 3 and yardsToGo > 7:
        weights[CoverageType.ZONE] *= 1.5
        weights[CoverageType.MAN] *= 0.7
    elif down in (1, 2) and yardsToGo <= 3:
        weights[CoverageType.MAN] *= 1.3

    # Score/clock state with coach-archetype modulation (Q3+)
    if quarter >= 3 and scoreDiff > 7:
        # LEADING — let the archetype pick the shell
        predator = aggr * defMind
        prevent  = (1 - aggr) * defMind
        if prevent > 0.32:
            # Bend-Don't-Break: zone shell to prevent big plays
            weights[CoverageType.ZONE] *= 1.8
            weights[CoverageType.MAN] *= 0.5
        elif predator > 0.42:
            # Predator: stay in man, force the bad throw
            weights[CoverageType.MAN] *= 1.4
            weights[CoverageType.ZONE] *= 0.8
        # else (reckless / vanilla): no coverage adjustment

    elif quarter >= 3 and scoreDiff < -7:
        # TRAILING — defense needs stops
        predator = aggr * defMind
        prevent  = (1 - aggr) * defMind
        if predator > 0.42:
            # Sell out — man pressure, force the panic throw
            weights[CoverageType.MAN] *= 1.5
            weights[CoverageType.ZONE] *= 0.6
        elif prevent > 0.32:
            # Bend-don't-break still — accept underneath, deny big plays
            weights[CoverageType.ZONE] *= 1.3
            weights[CoverageType.MAN] *= 0.9
        # else: no adjustment

    choices = list(weights.keys())
    probs = np.array([weights[c] for c in choices], dtype=float)
    probs /= probs.sum()
    return choices[int(np.random.choice(len(choices), p=probs))]


def _pickBlitz(defGameplan, down: int, yardsToGo: int, quarter: int,
               scoreDiff: int, clockSeconds: int) -> BlitzPackage:
    """Choose blitz package for this play (called only when blitz triggers).
    Coach archetype shapes the call when score/time pressure is on.
    """
    weights = dict(defGameplan.blitzPackageWeights)
    aggr = getattr(defGameplan, 'aggressiveness', 0.5)
    defMind = getattr(defGameplan, 'defensiveMind', 0.5)

    # Down/distance universal
    if down == 3 and yardsToGo > 10:
        weights[BlitzPackage.ALL_OUT] *= 0.6
        weights[BlitzPackage.LB_BLITZ] *= 1.3

    # Score/clock state with coach archetype
    if quarter >= 4 and scoreDiff < -7 and clockSeconds < 300:
        # Trailing late — archetype matters most here. Multipliers softened
        # from earlier pass; previous values pushed league sack rate to 1.48
        # (NFL ~1.0/team game), cascading into TQ drops and shutouts.
        predator = aggr * defMind  # smart-aggressive sells out
        reckless = aggr * (1 - defMind)  # dumb-aggressive overcommits
        if predator > 0.42:
            weights[BlitzPackage.ALL_OUT] *= 1.5
            weights[BlitzPackage.SAFETY_BLITZ] *= 1.3
        elif reckless > 0.42:
            weights[BlitzPackage.ALL_OUT] *= 1.4
            weights[BlitzPackage.LB_BLITZ] *= 0.8
        else:
            weights[BlitzPackage.ALL_OUT] *= 1.2
            weights[BlitzPackage.SAFETY_BLITZ] *= 1.1

    elif quarter >= 3 and scoreDiff > 7:
        # Leading — protect lead. Archetype splits between predator and prevent.
        predator = aggr * defMind
        if predator > 0.42:
            # Smart-aggressive: still hunting sacks/INTs to seal
            weights[BlitzPackage.LB_BLITZ] *= 1.3
            weights[BlitzPackage.ALL_OUT] *= 0.7
        else:
            # Conservative — LB only, no all-out
            weights[BlitzPackage.ALL_OUT] *= 0.3
            weights[BlitzPackage.SAFETY_BLITZ] *= 0.5
            weights[BlitzPackage.LB_BLITZ] *= 1.5

    choices = list(weights.keys())
    probs = np.array([weights[c] for c in choices], dtype=float)
    probs /= probs.sum()
    return choices[int(np.random.choice(len(choices), p=probs))]


def getDefensiveScheme(defGameplan, down: int, yardsToGo: int, fieldPos: int,
                       scoreDiff: int, quarter: int, clockSeconds: int) -> dict:
    """
    Return per-play rating multipliers plus coverage type and blitz package
    based on the defensive gameplan and current game situation.

    Returns dict with keys:
        runDefMult, passDefMult, passRushMult (floats)
        coverageType (CoverageType)
        blitzPackage (BlitzPackage or None)
    """
    neutral = {
        'runDefMult': 1.0, 'passDefMult': 1.0, 'passRushMult': 1.0,
        'coverageType': CoverageType.MAN, 'blitzPackage': None,
        'archetype': None,
    }
    if defGameplan is None:
        return neutral

    blitz = defGameplan.blitzFrequency
    runFocus = defGameplan.runStopFocus
    aggr = defGameplan.aggressiveness
    defMind = getattr(defGameplan, 'defensiveMind', 0.5)

    # Classify the defensive archetype for this snap based on score/clock
    # and coach attributes. Used downstream for observability.
    archetype = None
    if quarter >= 3 and scoreDiff > 7:
        predator = aggr * defMind
        prevent  = (1 - aggr) * defMind
        if predator > 0.42:
            archetype = 'def_leading_predator'
        elif prevent > 0.32:
            archetype = 'def_leading_prevent'
        elif aggr > 0.5:
            archetype = 'def_leading_reckless'
        else:
            archetype = 'def_leading_vanilla'
    elif quarter >= 3 and scoreDiff < -7:
        predator = aggr * defMind
        prevent  = (1 - aggr) * defMind
        if predator > 0.42:
            archetype = 'def_trailing_predator'
        elif prevent > 0.32:
            archetype = 'def_trailing_prevent'
        elif aggr > 0.5:
            archetype = 'def_trailing_reckless'
        else:
            archetype = 'def_trailing_vanilla'

    runDefMult = 1.0
    passDefMult = 1.0
    passRushMult = 1.0

    # --- Pick coverage type ---
    coverageType = _pickCoverage(defGameplan, down, yardsToGo, quarter,
                                  scoreDiff, clockSeconds)

    # Coverage type effects on multipliers
    if coverageType == CoverageType.MAN:
        # Man: strong against short/quick passes, weaker vs crossing routes
        passDefMult += 0.05
    elif coverageType == CoverageType.ZONE:
        # Zone: softer individual coverage, but better against broken plays
        passDefMult -= 0.05
        runDefMult += 0.05   # zone defenders read and react to run
    elif coverageType == CoverageType.MATCH:
        # Match: hybrid, slight bonus to both but requires good safety play
        passDefMult += 0.03
        runDefMult += 0.02

    # --- Situational multiplier adjustments ---
    if down == 3 and yardsToGo > 7:
        passDefMult += 0.15
        runDefMult -= 0.10
        passRushMult -= 0.10
    elif down in (1, 2) and yardsToGo <= 3:
        runDefMult += 0.25
        passDefMult -= 0.15
        passRushMult += 0.10
    elif fieldPos >= 80:
        passDefMult += 0.15
        runDefMult += 0.10
    elif quarter == 4 and scoreDiff > 7 and clockSeconds < 480:
        passDefMult += 0.20
        passRushMult -= 0.10
    elif quarter == 4 and scoreDiff < -7 and clockSeconds < 480:
        passRushMult += 0.30 * aggr
        passDefMult -= 0.15

    # --- Blitz decision ---
    blitzPackage = None
    if _random.random() < blitz:
        blitzPackage = _pickBlitz(defGameplan, down, yardsToGo, quarter,
                                   scoreDiff, clockSeconds)
        # Blitz effects
        if blitzPackage == BlitzPackage.LB_BLITZ:
            passRushMult += 0.25
            passDefMult -= 0.10  # TE is uncovered
        elif blitzPackage == BlitzPackage.SAFETY_BLITZ:
            passRushMult += 0.30
            passDefMult -= 0.20  # deep coverage gone
        elif blitzPackage == BlitzPackage.ALL_OUT:
            passRushMult += 0.50
            passDefMult -= 0.35  # skeletal coverage, any completion = big

    # Apply base run/pass focus from gameplan
    runDefMult += (runFocus - 0.5) * 0.50
    passDefMult += (0.5 - runFocus) * 0.50

    return {
        'runDefMult': max(0.5, runDefMult),
        'passDefMult': max(0.5, passDefMult),
        'passRushMult': max(0.5, passRushMult),
        'coverageType': coverageType,
        'blitzPackage': blitzPackage,
        'archetype': archetype,
    }


# ---------------------------------------------------------------------------
# Halftime adjustments
# ---------------------------------------------------------------------------

def adjustOffensiveGameplan(plan: OffensiveGameplan, coach, offStats: dict) -> None:
    """
    Mutate plan in-place based on first-half offensive performance.

    offStats keys: runPlays, runYards, passAttempts, passYards

    High-adaptability coaches make larger corrections; low-adaptability coaches
    stay closer to the original gameplan.
    """
    if coach is None or plan is None:
        return

    adaptFactor = (coach.adaptability - RATING_SCALE_MIN) / RATING_RANGE  # 0.0 at 60, 1.0 at 100

    ypc = offStats['runYards'] / max(1, offStats['runPlays'])
    ypa = offStats['passYards'] / max(1, offStats['passAttempts'])

    # Signal: how far above/below average each attack was (YPC avg ~4, YPA avg ~6)
    runSignal = max(-1.0, min(1.0, (ypc - 4.0) / 4.0))
    passSignal = max(-1.0, min(1.0, (ypa - 6.0) / 6.0))

    # Shift runPassRatio toward what worked; max shift ±0.25 at full adaptability
    shift = (runSignal - passSignal) * adaptFactor * 0.25
    plan.runPassRatio = float(np.clip(plan.runPassRatio + shift, 0.25, 0.75))

    # If run game was consistently stuffed, diversify away from the overused gap
    if ypc < 3.0 and offStats['runPlays'] >= 5 and adaptFactor > 0.25:
        overusedGap = max(plan.gapDistribution, key=plan.gapDistribution.get)
        newDist = dict(plan.gapDistribution)
        redirectAmount = adaptFactor * 0.18
        newDist[overusedGap] = max(0.20, newDist[overusedGap] - redirectAmount)
        others = [g for g in newDist if g != overusedGap]
        for g in others:
            newDist[g] = newDist[g] + redirectAmount / len(others)
        total = sum(newDist.values())
        plan.gapDistribution = {k: v / total for k, v in newDist.items()}


def adjustDefensiveGameplan(plan: DefensiveGameplan, coach, oppOffStats: dict) -> None:
    """
    Mutate plan in-place based on what the opponent's offense did in the first half.

    oppOffStats keys: runPlays, runYards, passAttempts, passYards,
                      wr1Yards (optional), wr2Yards (optional)
    """
    if coach is None or plan is None:
        return

    adaptFactor = (coach.adaptability - RATING_SCALE_MIN) / RATING_RANGE  # 0.0 at 60, 1.0 at 100

    oppYPC = oppOffStats['runYards'] / max(1, oppOffStats['runPlays'])
    oppYPA = oppOffStats['passYards'] / max(1, oppOffStats['passAttempts'])

    runThreat = max(-1.0, min(1.0, (oppYPC - 4.0) / 4.0))
    passThreat = max(-1.0, min(1.0, (oppYPA - 6.0) / 6.0))

    # Shift run/pass focus toward stopping what the opponent did well
    focusShift = (runThreat - passThreat) * adaptFactor * 0.30
    plan.runStopFocus = float(np.clip(plan.runStopFocus + focusShift, 0.20, 0.80))

    # Blitz more if opponent QB struggled, less if they thrived
    blitzShift = -passThreat * adaptFactor * 0.15
    plan.blitzFrequency = float(np.clip(plan.blitzFrequency + blitzShift, 0.05, 0.50))

    # --- Coverage tendency adjustment ---
    # If opponent's passing game thrived → shift toward more zone (prevent big plays)
    # If opponent's passing game struggled → keep man (keep the pressure on)
    if adaptFactor > 0.3:
        if passThreat > 0.3:
            # Opponent passing well → more zone to take away deep shots
            shift = passThreat * adaptFactor * 0.15
            plan.coverageTendency[CoverageType.ZONE] += shift
            plan.coverageTendency[CoverageType.MAN] -= shift * 0.7
            plan.coverageTendency[CoverageType.MATCH] -= shift * 0.3
        elif passThreat < -0.3:
            # Opponent struggling to pass → more man, keep it tight
            shift = abs(passThreat) * adaptFactor * 0.10
            plan.coverageTendency[CoverageType.MAN] += shift
            plan.coverageTendency[CoverageType.ZONE] -= shift
        # Renormalize
        covTotal = sum(plan.coverageTendency.values())
        if covTotal > 0:
            plan.coverageTendency = {k: max(0.05, v / covTotal)
                                      for k, v in plan.coverageTendency.items()}
            covTotal2 = sum(plan.coverageTendency.values())
            plan.coverageTendency = {k: v / covTotal2
                                      for k, v in plan.coverageTendency.items()}

    # CB swap: if one WR is torching their assigned CB, high-adaptability coach swaps
    wr1Yards = oppOffStats.get('wr1Yards', 0)
    wr2Yards = oppOffStats.get('wr2Yards', 0)
    yardGap = abs(wr1Yards - wr2Yards)
    if yardGap > 40 and adaptFactor > 0.4 and plan.coverageAssignments:
        cb1 = plan.coverageAssignments.get('wr1')
        cb2 = plan.coverageAssignments.get('wr2')
        if cb1 and cb2:
            # Swap: the WR getting torched gets the other CB
            plan.coverageAssignments['wr1'] = cb2
            plan.coverageAssignments['wr2'] = cb1
