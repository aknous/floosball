"""
Standalone run play simulation — simplified two-step model
(single Gaussian + breakaway) to verify yardage distributions.
"""
import numpy as np

def calculateGapQuality(gapType, rbPower, rbAgility, blockingRating, defenseRunCoverage):
    if gapType == 'A-gap':
        rbSkill = (rbPower * 1.5 + rbAgility * 0.5) / 2
        blockingImpact = 0.7
    elif gapType == 'B-gap':
        rbSkill = (rbPower * 1.0 + rbAgility * 1.0) / 2
        blockingImpact = 0.5
    elif gapType == 'C-gap':
        rbSkill = (rbPower * 0.5 + rbAgility * 1.5) / 2
        blockingImpact = 0.4
    else:  # bounce
        rbSkill = rbAgility
        blockingImpact = 0.2

    offenseStrength = (rbSkill * (1 - blockingImpact)) + (blockingRating * blockingImpact)
    skillDiff = offenseStrength - defenseRunCoverage
    meanQuality = max(10, min(90, 50 + skillDiff / 2.5))
    stdDev = 30 if gapType == 'bounce' else (20 if gapType == 'C-gap' else 15)
    return max(0, min(100, np.random.normal(meanQuality, stdDev)))


def simulateRun(rbPower, rbAgility, rbSpeed, rbPMA, rbXF,
                blockerRating, defRunCoverage,
                gapType='B-gap', yardsToEndzone=60, n=10000,
                # Tuning knobs
                meanCap=5.5, baseMean=3.0, divisor=8.0, stdDev=2.5,
                breakTrigger=8, breakChanceMax=12, breakScale=8):
    """Simulate n run plays with the simplified two-step model."""
    yards = []
    breakaways = 0
    tfls = 0

    for _ in range(n):
        gapQuality = calculateGapQuality(gapType, rbPower, rbAgility, blockerRating, defRunCoverage)

        # RB composite rating weighted by gap type
        if gapType == 'A-gap':
            rbRating = (rbPower * 1.5 + rbAgility * 0.5) / 2
        elif gapType == 'B-gap':
            rbRating = (rbPower + rbAgility) / 2
        elif gapType == 'C-gap':
            rbRating = (rbPower * 0.5 + rbAgility * 1.5) / 2
        else:  # bounce
            rbRating = rbAgility

        # Offensive rating: RB + blocking
        offRating = (rbRating * 0.6) + (blockerRating * 0.4)

        # Gap quality bonus (±2.5 range)
        qualityBonus = (gapQuality - 50) / 20

        # Skill differential determines mean yardage
        diff = offRating + qualityBonus - defRunCoverage
        mean = baseMean + (diff / divisor)
        mean = max(-1, min(meanCap, mean))

        maxYards = min(12, yardsToEndzone + 3)
        yardages = np.arange(-3, maxYards + 1)
        curve = np.exp(-((yardages - mean) ** 2) / (2 * stdDev ** 2))
        curve /= np.sum(curve)
        yardage = int(np.random.choice(yardages, p=curve))

        if yardage < 0:
            tfls += 1

        # Breakaway chance
        if yardage >= breakTrigger and yardage < yardsToEndzone:
            speedRating = (rbSpeed * 2 + rbAgility + rbPMA) / 4
            breakChance = max(2, min(breakChanceMax, (speedRating - 60) * 0.25 + 2))
            if np.random.randint(1, 101) <= breakChance:
                rem = yardsToEndzone - yardage
                yardage += min(rem, int(np.random.exponential(breakScale)))
                breakaways += 1

        if yardage > yardsToEndzone:
            yardage = yardsToEndzone
        yards.append(yardage)

    yards = np.array(yards)
    return {
        'mean': round(np.mean(yards), 1),
        'median': int(np.median(yards)),
        'p10': int(np.percentile(yards, 10)),
        'p90': int(np.percentile(yards, 90)),
        'max': int(np.max(yards)),
        'min': int(np.min(yards)),
        'pct_neg': round(np.mean(yards < 0) * 100, 1),
        'pct_0': round(np.mean(yards == 0) * 100, 1),
        'pct_10plus': round(np.mean(yards >= 10) * 100, 1),
        'pct_20plus': round(np.mean(yards >= 20) * 100, 1),
        'breakaway_pct': round(breakaways / n * 100, 2),
        'tfl_pct': round(tfls / n * 100, 1),
    }

def printResult(label, result):
    print(f"    {label}")
    print(f"      Avg: {result['mean']}  Median: {result['median']}  "
          f"P10: {result['p10']}  P90: {result['p90']}  Max: {result['max']}")
    print(f"      TFL: {result['tfl_pct']}%  10+: {result['pct_10plus']}%  "
          f"20+: {result['pct_20plus']}%  Breakaway: {result['breakaway_pct']}%")

def gameProjection(ypc, carries):
    """Project game yardage from YPC."""
    return round(ypc * carries)

PARAMS = dict(meanCap=5.5, baseMean=4.0, divisor=10.0, stdDev=3.0,
              breakTrigger=6, breakChanceMax=15, breakScale=8)

SCENARIOS = [
    ("Average RB vs Average D (80v80)",
     dict(rbPower=80, rbAgility=80, rbSpeed=80, rbPMA=80, rbXF=80, blockerRating=80, defRunCoverage=80),
     10),  # carries per game
    ("Elite RB vs Weak D (92v68)",
     dict(rbPower=93, rbAgility=90, rbSpeed=94, rbPMA=88, rbXF=85, blockerRating=90, defRunCoverage=68),
     12),
    ("Weak RB vs Strong D (68v90)",
     dict(rbPower=68, rbAgility=66, rbSpeed=65, rbPMA=64, rbXF=62, blockerRating=70, defRunCoverage=90),
     8),
    ("Good RB vs Good D (85v85)",
     dict(rbPower=86, rbAgility=84, rbSpeed=86, rbPMA=82, rbXF=80, blockerRating=82, defRunCoverage=85),
     10),
    ("Good RB vs Average D (85v78)",
     dict(rbPower=86, rbAgility=84, rbSpeed=86, rbPMA=82, rbXF=80, blockerRating=82, defRunCoverage=78),
     11),
    ("Speed back outside vs Avg D",
     dict(rbPower=72, rbAgility=88, rbSpeed=92, rbPMA=82, rbXF=78, blockerRating=78, defRunCoverage=80, gapType='C-gap'),
     10),
]

print("=" * 72)
print("RUN PLAY SIMULATION — Two-Step Model (10,000 plays per scenario)")
print("=" * 72)

for label, kwargs, carries in SCENARIOS:
    gap = kwargs.pop('gapType', 'B-gap')
    print(f"\n--- {label} ({gap}) ---")

    result = simulateRun(**kwargs, gapType=gap, **PARAMS)
    printResult(gap, result)
    print(f"      ~Game projection ({carries} carries): {gameProjection(result['mean'], carries)} yards")

print("\n" + "=" * 72)
print("NFL reference: League-avg YPC ~4.3, elite ~5.5, game totals 60-100 avg")
print("=" * 72)
