"""
Gameplan module — pre-game coaching strategy + per-play defensive scheme selection.

OffensiveGameplan: run/pass ratio, gap distribution, pass depth, aggressiveness.
DefensiveGameplan: blitz frequency, run-stop focus, aggressiveness.
getDefensiveScheme(): per-play multipliers for run/pass defense and pass rush.
adjustOffensiveGameplan(): halftime adjustment based on first-half offensive stats.
adjustDefensiveGameplan(): halftime adjustment based on what opponent's offense did.
"""

import random as _random
import numpy as np

from constants import RATING_SCALE_MIN, RATING_RANGE


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


def generateDefensiveGameplan(coach, defenseTeam, offenseTeam) -> DefensiveGameplan:
    """
    Build a pre-game defensive gameplan from coach scouting of the opponent.
    Falls back to neutral defaults if coach is None.
    """
    plan = DefensiveGameplan()
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
    return plan


# ---------------------------------------------------------------------------
# Per-play defensive scheme
# ---------------------------------------------------------------------------

def getDefensiveScheme(defGameplan, down: int, yardsToGo: int, fieldPos: int,
                       scoreDiff: int, quarter: int, clockSeconds: int) -> dict:
    """
    Return per-play rating multipliers based on the defensive gameplan and
    current game situation.

    Returns:
        dict with keys runDefMult, passDefMult, passRushMult (all floats).
    """
    neutral = {'runDefMult': 1.0, 'passDefMult': 1.0, 'passRushMult': 1.0}
    if defGameplan is None:
        return neutral

    blitz = defGameplan.blitzFrequency
    runFocus = defGameplan.runStopFocus
    aggr = defGameplan.aggressiveness

    runDefMult = 1.0
    passDefMult = 1.0
    passRushMult = 1.0

    # Situational adjustments
    if down == 3 and yardsToGo > 7:
        # 3rd & long: drop into coverage, prevent the first down
        passDefMult += 0.20
        runDefMult -= 0.10
        passRushMult -= 0.15
    elif down in (1, 2) and yardsToGo <= 3:
        # Short yardage: stack the box, stop the run
        runDefMult += 0.25
        passDefMult -= 0.15
        passRushMult += 0.10
    elif fieldPos >= 80:
        # Red zone: tighter coverage, prevent TD
        passDefMult += 0.15
        runDefMult += 0.10
    elif quarter == 4 and scoreDiff > 7 and clockSeconds < 480:
        # Protecting lead late: prevent big plays
        passDefMult += 0.20
        passRushMult -= 0.10
    elif quarter == 4 and scoreDiff < -7 and clockSeconds < 480:
        # Desperate to force turnover: blitz heavily
        passRushMult += 0.30 * aggr
        passDefMult -= 0.15   # exposed in coverage

    # Blitz tendency (random draw each play)
    if _random.random() < blitz:
        passRushMult += 0.35
        passDefMult -= 0.25   # man coverage is weaker under blitz

    # Apply base run/pass focus from gameplan
    runDefMult += (runFocus - 0.5) * 0.50
    passDefMult += (0.5 - runFocus) * 0.50

    return {
        'runDefMult': max(0.5, runDefMult),
        'passDefMult': max(0.5, passDefMult),
        'passRushMult': max(0.5, passRushMult),
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

    oppOffStats keys: runPlays, runYards, passAttempts, passYards
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
