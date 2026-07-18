"""
Standalone YAC calculation test — replicates the core math from floosball_game.py
without needing imports from the game engine.
"""
import numpy as np
from collections import Counter

def simulate_yac(rcvRating, defRating, throwQuality, openness, rcvSpeed,
                 targetSideline=False, rcvDisc=75, yardsToEndzone=60,
                 passYards=10, pressureMod=0, n=10000):
    """Simulate n YAC outcomes and return stats."""
    yacs = []
    breakaways = 0

    for _ in range(n):
        # Cap
        if targetSideline:
            if rcvDisc >= 85:
                yacCap, decayMult = 5, 2.0
            elif rcvDisc >= 75:
                yacCap, decayMult = 8, 1.6
            elif rcvDisc >= 70:
                yacCap, decayMult = 10, 1.3
            else:
                yacCap, decayMult = 12, 1.1
        else:
            yacCap = 15
            decayMult = 1.0

        # Throw quality multiplier
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
            yacOffense = rcvRating + pressureMod
            yacDefense = defRating
            yacDecayRate = max(0.10, 0.18 + 0.005 * (yacDefense - yacOffense))
            yacDecayRate *= decayMult

            yacCurve = np.exp(-yacDecayRate * yacYardages)
            yacCurve /= np.sum(yacCurve)
            yac = int(np.random.choice(yacYardages, p=yacCurve))

        # Breakaway
        if yac >= 7 and (passYards + yac) < yardsToEndzone:
            execBonus = 0
            if throwQuality >= 75:
                execBonus += 5
            if openness >= 70:
                execBonus += 5
            breakChance = max(3, min(25, (rcvSpeed - 60) * 0.3 + 3 + execBonus))
            if np.random.randint(1, 101) <= breakChance:
                remYards = yardsToEndzone - passYards - yac
                yac += min(remYards, int(np.random.exponential(10)))
                breakaways += 1

        totalYards = passYards + yac
        if totalYards > yardsToEndzone:
            yac = yardsToEndzone - passYards
        yacs.append(yac)

    yacs = np.array(yacs)
    return {
        'mean': round(np.mean(yacs), 1),
        'median': int(np.median(yacs)),
        'p90': int(np.percentile(yacs, 90)),
        'p95': int(np.percentile(yacs, 95)),
        'p99': int(np.percentile(yacs, 99)),
        'max': int(np.max(yacs)),
        'pct_0': round(np.mean(yacs == 0) * 100, 1),
        'pct_10plus': round(np.mean(yacs >= 10) * 100, 1),
        'pct_20plus': round(np.mean(yacs >= 20) * 100, 1),
        'breakaway_pct': round(breakaways / n * 100, 2),
    }

def print_result(label, result):
    print(f"\n  {label}")
    print(f"    Avg: {result['mean']}  Median: {result['median']}  "
          f"P90: {result['p90']}  P95: {result['p95']}  P99: {result['p99']}  Max: {result['max']}")
    print(f"    0 YAC: {result['pct_0']}%  10+: {result['pct_10plus']}%  "
          f"20+: {result['pct_20plus']}%  Breakaway: {result['breakaway_pct']}%")

print("=" * 70)
print("YAC SIMULATION (10,000 completions per scenario)")
print("=" * 70)

# --- Scenario 1: Even matchup, good throw ---
print("\n--- SCENARIO 1: Even matchup, good throw ---")
print("    rcvRating=70, defRating=70, throwQuality=80, openness=60, rcvSpeed=70")
print_result("Non-sideline", simulate_yac(70, 70, 80, 60, 70))
print_result("Sideline (disc=80)", simulate_yac(70, 70, 80, 60, 70, targetSideline=True, rcvDisc=80))

# --- Scenario 2: Elite WR vs weak defense ---
print("\n--- SCENARIO 2: Elite WR vs weak defense ---")
print("    rcvRating=85, defRating=55, throwQuality=85, openness=80, rcvSpeed=85")
print_result("Non-sideline", simulate_yac(85, 55, 85, 80, 85))

# --- Scenario 3: Weak WR vs strong defense ---
print("\n--- SCENARIO 3: Weak WR vs strong defense ---")
print("    rcvRating=60, defRating=80, throwQuality=65, openness=45, rcvSpeed=60")
print_result("Non-sideline", simulate_yac(60, 80, 65, 45, 60))

# --- Scenario 4: Average WR, mediocre throw ---
print("\n--- SCENARIO 4: Average WR, mediocre throw ---")
print("    rcvRating=70, defRating=70, throwQuality=55, openness=55, rcvSpeed=68")
print_result("Non-sideline", simulate_yac(70, 70, 55, 55, 68))

# --- Scenario 5: Great throw to fast WR in space ---
print("\n--- SCENARIO 5: Great throw to fast WR in space ---")
print("    rcvRating=80, defRating=65, throwQuality=90, openness=75, rcvSpeed=88")
print_result("Non-sideline", simulate_yac(80, 65, 90, 75, 88))

# --- Scenario 6: Short pass (screen/check-down), lots of room ---
print("\n--- SCENARIO 6: Short pass near midfield, lots of room ---")
print("    rcvRating=75, defRating=70, throwQuality=82, openness=65, rcvSpeed=78, passYards=4")
print_result("Non-sideline", simulate_yac(75, 70, 82, 65, 78, passYards=4, yardsToEndzone=55))

# --- Scenario 7: Deep ball — minimal YAC expected ---
print("\n--- SCENARIO 7: Deep ball (long pass) ---")
print("    rcvRating=75, defRating=70, throwQuality=75, openness=55, rcvSpeed=80, passYards=30")
print_result("Non-sideline", simulate_yac(75, 70, 75, 55, 80, passYards=30, yardsToEndzone=45))

# --- Scenario 8: Bad throw, barely caught ---
print("\n--- SCENARIO 8: Bad throw, barely caught ---")
print("    rcvRating=70, defRating=70, throwQuality=35, openness=50, rcvSpeed=70")
print_result("Non-sideline", simulate_yac(70, 70, 35, 50, 70))

print("\n" + "=" * 70)
print("NFL reference: League-avg YAC ~4.5-5.5 yards per completion")
print("=" * 70)
