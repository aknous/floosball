"""Test YAC and dynamic route running systems across scenarios.
No server needed — replicates the core math from floosball_game.py."""
import numpy as np
from random import randint

NUM_SAMPLES = 5000

# ─── Route Running (from calculateReceiverOpenness) ───

def calcRouteQuality(baseRouteRunning, discipline, baseConf, baseDet, confDrift, detDrift, gamePressure, pressureHandling, defPassCoverage):
    """Replicate dynamic route quality calc."""
    # 1. Pressure effect
    pressureMod = calcPressureMod(gamePressure, pressureHandling)
    pressureEffect = pressureMod * 5

    # 2. Coverage disruption
    coverageDisruption = -max(0, (defPassCoverage - 60) * 0.2)

    # 3. Mental state: base personality (moderate) + in-game drift (amplified)
    mentalEffect = (baseConf + baseDet) * 2 + (confDrift + detDrift) * 25

    # 4. Per-play variance
    routeVariance = np.random.normal(0, max(4, 10 - discipline / 15))

    effective = baseRouteRunning + pressureEffect + coverageDisruption + mentalEffect + routeVariance
    return max(30, min(100, effective))

def calcPressureMod(gamePressure, pressureHandling):
    """Simplified pressure modifier (from PlayerAttributes.getPressureModifier)."""
    if gamePressure < 20:
        return 0
    intensity = gamePressure / 100
    if pressureHandling >= 5:
        # Clutch player — likely to overperform
        roll = np.random.random()
        if roll < 0.4 * intensity:
            return pressureHandling * 0.3 * intensity  # overperform
        elif roll < 0.8:
            return 0
        else:
            return -2 * intensity  # rare choke
    elif pressureHandling <= -5:
        # Choke-prone
        roll = np.random.random()
        if roll < 0.4 * intensity:
            return pressureHandling * 0.3 * intensity  # underperform
        elif roll < 0.8:
            return 0
        else:
            return 2 * intensity  # rare clutch
    else:
        return 0

def calcOpenness(routeQuality, defPassCoverage):
    """Replicate openness sampling."""
    skillDiff = routeQuality - defPassCoverage
    meanOpenness = max(10, min(90, 50 + skillDiff / 2))
    stdDev = max(10, 25 - routeQuality / 10)
    openness = np.random.normal(meanOpenness, stdDev)
    return max(0, min(100, openness))


# ─── YAC (from passPlay) ───

def calcYAC(receiverSpeed, receiverAgility, receiverPMA, receiverPressureMod,
            defPassCoverage, throwQuality, openness, yardsToEndzone, passYards,
            targetSideline=False, discipline=75):
    """Replicate YAC + breakaway calc."""
    if passYards >= yardsToEndzone:
        return 0

    receiverYACRating = (receiverAgility + receiverSpeed + receiverPMA) / 3

    if targetSideline:
        if discipline >= 85:
            yacCap, decayMult = 5, 2.0
        elif discipline >= 75:
            yacCap, decayMult = 8, 1.6
        elif discipline >= 70:
            yacCap, decayMult = 10, 1.3
        else:
            yacCap, decayMult = 12, 1.1
    else:
        yacCap, decayMult = 25, 1.0

    # Throw quality mult
    if throwQuality >= 80:
        throwYacMult = 1.0
    elif throwQuality >= 60:
        throwYacMult = 0.7
    elif throwQuality >= 40:
        throwYacMult = 0.4
    else:
        throwYacMult = 0.15
    yacCap = max(1, int(yacCap * throwYacMult))

    yacMaxYards = min(yacCap, yardsToEndzone - passYards)
    yac = 0

    if yacMaxYards > 0:
        yacYardages = np.arange(0, yacMaxYards + 1)
        yacOffense = receiverYACRating + receiverPressureMod
        yacDefense = defPassCoverage
        yacDecayRate = max(0.06, 0.14 + 0.005 * (yacDefense - yacOffense))
        yacDecayRate *= decayMult
        yacCurve = np.exp(-yacDecayRate * yacYardages)
        yacCurve /= np.sum(yacCurve)
        yac = int(np.random.choice(yacYardages, p=yacCurve))

    # Breakaway check
    if yac >= 4 and (passYards + yac) < yardsToEndzone:
        rcvSpeed = (receiverSpeed * 2 + receiverAgility + receiverPMA) / 4
        execBonus = 0
        if throwQuality >= 75:
            execBonus += 5
        if openness >= 70:
            execBonus += 5
        breakChance = max(3, min(25, (rcvSpeed - 60) * 0.3 + 3 + execBonus))
        if randint(1, 100) <= breakChance:
            remYards = yardsToEndzone - passYards - yac
            yac += min(remYards, int(np.random.exponential(15)))

    return min(yac, yardsToEndzone - passYards)


# ─── Test Scenarios ───

def printDist(values, label, buckets):
    print(f"\n  {label} (n={len(values)}, avg={np.mean(values):.1f}, median={np.median(values):.0f}):")
    for name, lo, hi in buckets:
        count = sum(1 for v in values if lo <= v <= hi)
        pct = count / len(values) * 100
        bar = '#' * int(pct / 2)
        print(f"    {name:>12s}: {count:4d} ({pct:5.1f}%) {bar}")

def runRouteScenario(name, **kwargs):
    defaults = dict(baseRouteRunning=78, discipline=75, baseConf=0, baseDet=0,
                    confDrift=0, detDrift=0, gamePressure=30, pressureHandling=0, defPassCoverage=72)
    defaults.update(kwargs)
    print(f"\n{'─'*60}")
    print(f"ROUTE SCENARIO: {name}")
    for k, v in kwargs.items():
        print(f"  {k}={v}")

    routeQualities = [calcRouteQuality(**defaults) for _ in range(NUM_SAMPLES)]
    opennesses = [calcOpenness(rq, defaults['defPassCoverage']) for rq in routeQualities]

    printDist(routeQualities, "Route Quality", [
        ("Crisp (80+)", 80, 100), ("Solid (70-79)", 70, 79), ("Sloppy (<70)", 30, 69)])
    printDist(opennesses, "Resulting Openness", [
        ("Wide Open (70+)", 70, 100), ("Open (50-69)", 50, 69),
        ("Contested (30-49)", 30, 49), ("Covered (<30)", 0, 29)])

def runYACScenario(name, **kwargs):
    defaults = dict(receiverSpeed=80, receiverAgility=78, receiverPMA=75, receiverPressureMod=0,
                    defPassCoverage=72, throwQuality=75, openness=65, yardsToEndzone=60,
                    passYards=8, targetSideline=False, discipline=75)
    defaults.update(kwargs)
    print(f"\n{'─'*60}")
    print(f"YAC SCENARIO: {name}")
    for k, v in kwargs.items():
        print(f"  {k}={v}")

    yacs = [calcYAC(**defaults) for _ in range(NUM_SAMPLES)]
    totalYards = [defaults['passYards'] + y for y in yacs]

    printDist(yacs, "YAC", [
        ("0", 0, 0), ("1-4", 1, 4), ("5-9", 5, 9), ("10-19", 10, 19), ("20-29", 20, 29), ("30+", 30, 200)])
    printDist(totalYards, "Total Yards (air + YAC)", [
        ("0-9", 0, 9), ("10-19", 10, 19), ("20-29", 20, 29),
        ("30-39", 30, 39), ("40-49", 40, 49), ("50+", 50, 200)])

    breakaways = sum(1 for y in yacs if y >= 20)
    print(f"\n  Breakaway plays (20+ YAC): {breakaways} ({breakaways/NUM_SAMPLES*100:.1f}%)")


# ═══════════════════════════════════════════════════════
print("=" * 60)
print("ROUTE RUNNING SCENARIOS")
print("=" * 60)

runRouteScenario("Baseline — avg receiver, neutral mental, avg defense")

runRouteScenario("Elite receiver, crisp routes",
    baseRouteRunning=90, discipline=88, pressureHandling=7)

runRouteScenario("Undisciplined receiver, sloppy variance",
    baseRouteRunning=78, discipline=62, pressureHandling=-3)

# --- In-game drift scenarios (base conf 0, varying drift) ---
# Typical drift values: TD = +0.03 conf, completion = +0.005, drop = -0.005, INT = -0.02
# Momentum = ±0.003-0.006/play. Over a game, drift is roughly ±0.05 to ±0.20

runRouteScenario("Receiver having a quiet game (0 catches, no targets)",
    confDrift=-0.04, detDrift=-0.02)

runRouteScenario("Receiver on fire (3 catches, 1 TD, momentum)",
    confDrift=0.12, detDrift=0.05)

runRouteScenario("Receiver having terrible game (2 drops, 0 catches, negative momentum)",
    confDrift=-0.15, detDrift=-0.08)

runRouteScenario("Receiver having career game (6 catches, 2 TDs, team rolling)",
    confDrift=0.22, detDrift=0.10)

# --- Personality base matters too ---
runRouteScenario("Naturally confident receiver (base +2) having avg game",
    baseConf=2, baseDet=1)

runRouteScenario("Low confidence receiver (base -2) having avg game",
    baseConf=-2, baseDet=-1)

# --- Pressure scenarios ---
runRouteScenario("High pressure, clutch receiver",
    gamePressure=80, pressureHandling=8, baseRouteRunning=82)

runRouteScenario("High pressure, choke-prone receiver",
    gamePressure=80, pressureHandling=-7, baseRouteRunning=82)

# --- Defense scenarios ---
runRouteScenario("Elite defense disrupting routes",
    defPassCoverage=90)

runRouteScenario("Weak defense, easy routes",
    defPassCoverage=60)

# --- Combined scenarios ---
runRouteScenario("Worst: bad base, frustrated, elite D, pressure, undisciplined",
    baseConf=-2, baseDet=-1.5, confDrift=-0.15, detDrift=-0.08, defPassCoverage=88,
    gamePressure=75, pressureHandling=-6, discipline=62)

runRouteScenario("Best: confident, on fire, weak D, clutch, disciplined",
    baseConf=2, baseDet=1, confDrift=0.20, detDrift=0.10, defPassCoverage=60,
    gamePressure=20, pressureHandling=8, discipline=88, baseRouteRunning=90)

print("\n\n")
print("=" * 60)
print("YAC SCENARIOS")
print("=" * 60)

runYACScenario("Baseline — short pass, avg everything",
    passYards=4, throwQuality=72, openness=55)

runYACScenario("Perfect execution — sharp throw to open receiver",
    passYards=4, throwQuality=88, openness=80, receiverSpeed=85, receiverAgility=84)

runYACScenario("Poor execution — bad throw to covered receiver",
    passYards=4, throwQuality=42, openness=25, receiverSpeed=75)

runYACScenario("Speed demon catches short pass in stride",
    passYards=3, throwQuality=85, openness=75, receiverSpeed=95, receiverAgility=90, receiverPMA=82)

runYACScenario("Medium pass, good throw, open field",
    passYards=12, throwQuality=80, openness=70, yardsToEndzone=70)

runYACScenario("Deep pass with room to run",
    passYards=25, throwQuality=82, openness=72, yardsToEndzone=65, receiverSpeed=88)

runYACScenario("Sideline route — disciplined receiver gets out",
    passYards=8, throwQuality=78, openness=60, targetSideline=True, discipline=88)

runYACScenario("Sideline route — undisciplined receiver stays in",
    passYards=8, throwQuality=78, openness=60, targetSideline=True, discipline=62)

runYACScenario("Short pass, elite defense",
    passYards=4, throwQuality=72, openness=45, defPassCoverage=90)

runYACScenario("Short pass, weak defense, fast receiver",
    passYards=3, throwQuality=82, openness=78, defPassCoverage=60, receiverSpeed=92, receiverAgility=88)


# ═══════════════════════════════════════════════════════
print("\n\n")
print("=" * 60)
print("QB THROW QUALITY SCENARIOS")
print("=" * 60)

def mentalDrift(baseConf, baseDet, confDrift, detDrift, baseWeight=2, driftWeight=25):
    return (baseConf + baseDet) * baseWeight + (confDrift + detDrift) * driftWeight

def calcThrowQuality(qbAccuracy, qbXFactor, qbPressureMod, passType, rushDiff,
                     baseConf=0, baseDet=0, confDrift=0, detDrift=0):
    """Replicate throw quality calc with mental drift."""
    baseAccuracy = (qbAccuracy + qbXFactor) / 2 + qbPressureMod
    baseAccuracy += mentalDrift(baseConf, baseDet, confDrift, detDrift)

    difficultyMods = {'short': 1.0, 'medium': 0.85, 'long': 0.7, 'hailMary': 0.5}
    diffMod = difficultyMods.get(passType, 0.85)

    # Simplified pressure degradation
    maxDeg = 0.35
    steepness = 3.5
    degAmount = maxDeg * (1 / (1 + np.exp(-steepness * rushDiff)))
    pressDeg = max(0.65, min(1.0, 1.0 - degAmount))

    throwQuality = baseAccuracy * diffMod * pressDeg
    throwQuality += randint(-10, 10)
    return max(5, min(100, throwQuality))

def runQBScenario(name, **kwargs):
    defaults = dict(qbAccuracy=78, qbXFactor=75, qbPressureMod=0, passType='medium',
                    rushDiff=0, baseConf=0, baseDet=0, confDrift=0, detDrift=0)
    defaults.update(kwargs)
    print(f"\n{'─'*60}")
    print(f"QB SCENARIO: {name}")
    for k, v in kwargs.items():
        print(f"  {k}={v}")

    qualities = [calcThrowQuality(**defaults) for _ in range(NUM_SAMPLES)]
    printDist(qualities, "Throw Quality", [
        ("Sharp (80+)", 80, 100), ("Decent (60-79)", 60, 79),
        ("Errant (40-59)", 40, 59), ("Terrible (<40)", 5, 39)])

runQBScenario("Baseline — avg QB, medium pass, no drift")

runQBScenario("QB in rhythm (2 TDs, completions, momentum)",
    confDrift=0.15, detDrift=0.06)

runQBScenario("QB rattled (INT + sack fumble, neg momentum)",
    confDrift=-0.12, detDrift=-0.06)

runQBScenario("QB having nightmare game (2 INTs, fumble, team collapsing)",
    confDrift=-0.22, detDrift=-0.10)

runQBScenario("Elite QB in rhythm, short pass",
    qbAccuracy=90, qbXFactor=85, passType='short', confDrift=0.12, detDrift=0.05)

runQBScenario("Avg QB rattled, deep ball",
    passType='long', confDrift=-0.15, detDrift=-0.08)

runQBScenario("Confident QB (base +2) having avg game",
    baseConf=2, baseDet=1)

runQBScenario("Low confidence QB (base -2) having avg game",
    baseConf=-2, baseDet=-1)


# ═══════════════════════════════════════════════════════
print("\n\n")
print("=" * 60)
print("RB RUN EXECUTION SCENARIOS")
print("=" * 60)

def calcRunYards(rbPower, rbAgility, rbPMA, rbXFactor, blockerRating, defRunCoverage,
                 gapQuality, runnerPressureMod=0, yardsToEndzone=60,
                 baseConf=0, baseDet=0, confDrift=0, detDrift=0):
    """Replicate stage 1 run yards with mental drift."""
    rawPower = (rbPower * 1.5 + rbAgility * 1.2 + rbPMA * 0.8 + rbXFactor * 0.5) / 4
    rawPower += mentalDrift(baseConf, baseDet, confDrift, detDrift)

    stage1Offense = (rawPower * 0.65 + blockerRating * 0.35) + runnerPressureMod
    qualityBonus = (gapQuality - 50) / 10
    adjustedOffense = stage1Offense + qualityBonus

    stage1Max = min(10, yardsToEndzone + 5)
    stage1Yardages = np.arange(0, stage1Max + 1)

    meanS1 = ((adjustedOffense - defRunCoverage) / 2.5) + 2.5
    meanS1 = min(stage1Max + 1, max(0, meanS1))

    relStrength = ((adjustedOffense * 2) - defRunCoverage) / 100
    absSkill = (adjustedOffense + defRunCoverage) / 200
    stdS1 = max(1, (stage1Max + 1) / 4 * (1 + relStrength) * absSkill)

    curve = np.exp(-((stage1Yardages - meanS1) ** 2) / (2 * stdS1 ** 2))
    curve /= np.sum(curve)

    return int(np.random.choice(stage1Yardages, p=curve))

def runRBScenario(name, **kwargs):
    defaults = dict(rbPower=78, rbAgility=76, rbPMA=72, rbXFactor=70, blockerRating=72,
                    defRunCoverage=72, gapQuality=55, runnerPressureMod=0, yardsToEndzone=60,
                    baseConf=0, baseDet=0, confDrift=0, detDrift=0)
    defaults.update(kwargs)
    print(f"\n{'─'*60}")
    print(f"RB SCENARIO: {name}")
    for k, v in kwargs.items():
        print(f"  {k}={v}")

    yards = [calcRunYards(**defaults) for _ in range(NUM_SAMPLES)]
    printDist(yards, "Stage 1 Yards", [
        ("0-1", 0, 1), ("2-4", 2, 4), ("5-7", 5, 7), ("8-10", 8, 10)])

runRBScenario("Baseline — avg RB, avg gap, no drift")

runRBScenario("RB in rhythm (big run earlier, momentum)",
    confDrift=0.12, detDrift=0.05)

runRBScenario("RB stuffed all game (fumble, no yards, neg momentum)",
    confDrift=-0.15, detDrift=-0.08)

runRBScenario("RB having monster game (2 TDs, big runs, team dominating)",
    confDrift=0.25, detDrift=0.12)

runRBScenario("Elite RB in rhythm, great gap",
    rbPower=90, rbAgility=88, rbPMA=82, gapQuality=75, confDrift=0.15, detDrift=0.06)

runRBScenario("Avg RB frustrated, stuffed gap",
    gapQuality=30, confDrift=-0.12, detDrift=-0.06)

runRBScenario("Confident RB (base +2) having avg game",
    baseConf=2, baseDet=1)

runRBScenario("Low confidence RB (base -2) having avg game",
    baseConf=-2, baseDet=-1)
