"""Test scenarios for coach-influenced FG attempt thresholds.

Verifies that _coachFgThreshold produces sensible thresholds based on:
1. Coach aggressiveness (conservative → aggressive)
2. Kicker in-game performance (misses raise threshold, makes lower it)
"""

import sys
import types

# ── Minimal stubs to test _coachFgThreshold without booting the full engine ──

from constants import FG_MIN_ATTEMPT_PROB, COACH_ATTR_NEUTRAL, COACH_ATTR_RANGE, FG_SNAP_DISTANCE

class MockCoach:
    def __init__(self, aggressiveness=80):
        self.aggressiveness = aggressiveness

class MockKickingStats:
    def __init__(self, fgAtt=0, fgs=0):
        self._stats = {'fgAtt': fgAtt, 'fgs': fgs}

    def get(self, key, default=0):
        return self._stats.get(key, default)

class MockKicker:
    def __init__(self, fgAtt=0, fgs=0, overallRating=75, legStrength=75):
        self.gameStatsDict = {'kicking': MockKickingStats(fgAtt, fgs)}
        self.gameAttributes = types.SimpleNamespace(overallRating=overallRating)
        self.maxFgDistance = round(70 * (legStrength / 100))

class MockTeam:
    def __init__(self, coach=None, kicker=None):
        self.coach = coach
        self.rosterDict = {'k': kicker}

class FgThresholdTester:
    """Lightweight wrapper that exposes _coachFgThreshold for testing."""
    def __init__(self, team):
        self.offensiveTeam = team

    def _coachFgThreshold(self, coach):
        baseThreshold = FG_MIN_ATTEMPT_PROB

        aggrNorm = (coach.aggressiveness - COACH_ATTR_NEUTRAL) / COACH_ATTR_RANGE if coach else 0.0
        aggrShift = aggrNorm * 0.08
        threshold = baseThreshold - aggrShift

        kicker = self.offensiveTeam.rosterDict.get('k')
        if kicker:
            kStats = kicker.gameStatsDict.get('kicking', {})
            att = kStats.get('fgAtt', 0)
            made = kStats.get('fgs', 0)
            misses = att - made
            if att > 0:
                if misses > 0:
                    perfPenalty = min(0.09, misses * 0.04 - (misses - 1) * 0.005)
                    threshold += perfPenalty
                elif made >= 2:
                    perfBonus = min(0.04, made * 0.015)
                    threshold -= perfBonus

        return max(0.10, min(0.35, threshold))


def fmtPct(val):
    return f"{val:.1%}"


def runScenarios():
    print("=" * 72)
    print("FG ATTEMPT THRESHOLD SCENARIOS")
    print(f"Base threshold (FG_MIN_ATTEMPT_PROB): {fmtPct(FG_MIN_ATTEMPT_PROB)}")
    print(f"Coach neutral: {COACH_ATTR_NEUTRAL}, range: {COACH_ATTR_RANGE}")
    print("=" * 72)

    # ── Part 1: Coach Aggressiveness (no game history) ──
    print("\n--- Part 1: Coach Aggressiveness (fresh kicker, 0 FG attempts) ---")
    print(f"{'Coach Aggr':>12} {'aggrNorm':>10} {'Threshold':>10}")
    print("-" * 36)
    for aggr in [60, 65, 70, 75, 80, 85, 90, 95, 100]:
        coach = MockCoach(aggr)
        kicker = MockKicker()
        team = MockTeam(coach, kicker)
        tester = FgThresholdTester(team)
        t = tester._coachFgThreshold(coach)
        aggrNorm = (aggr - COACH_ATTR_NEUTRAL) / COACH_ATTR_RANGE
        print(f"{aggr:>12} {aggrNorm:>+10.2f} {fmtPct(t):>10}")

    # ── Part 2: Kicker In-Game Performance (neutral coach) ──
    print("\n--- Part 2: Kicker In-Game Performance (neutral coach, aggr=80) ---")
    print(f"{'Game Record':>15} {'Misses':>8} {'Threshold':>10} {'vs Base':>10}")
    print("-" * 48)
    coach = MockCoach(80)
    scenarios = [
        (0, 0, "No attempts"),
        (1, 1, "1/1 (perfect)"),
        (2, 2, "2/2 (perfect)"),
        (3, 3, "3/3 (perfect)"),
        (4, 4, "4/4 (perfect)"),
        (1, 0, "0/1 (missed)"),
        (2, 1, "1/2 (50%)"),
        (3, 1, "1/3 (33%)"),
        (3, 2, "2/3 (missed 1)"),
        (4, 2, "2/4 (missed 2)"),
        (4, 1, "1/4 (missed 3)"),
    ]
    baseT = FG_MIN_ATTEMPT_PROB
    for att, made, label in scenarios:
        kicker = MockKicker(fgAtt=att, fgs=made)
        team = MockTeam(coach, kicker)
        tester = FgThresholdTester(team)
        t = tester._coachFgThreshold(coach)
        diff = t - baseT
        diffStr = f"{diff:>+.1%}" if diff != 0 else "—"
        print(f"{label:>15} {att - made:>8} {fmtPct(t):>10} {diffStr:>10}")

    # ── Part 3: Combined Scenarios ──
    print("\n--- Part 3: Combined (Coach Aggr + Kicker Performance) ---")
    print(f"{'Scenario':<45} {'Threshold':>10}")
    print("-" * 58)

    combos = [
        ("Conservative (60) + kicker missed 2", 60, 3, 1),
        ("Conservative (60) + fresh kicker", 60, 0, 0),
        ("Conservative (60) + kicker 3/3", 60, 3, 3),
        ("Neutral (80) + kicker missed 2", 80, 3, 1),
        ("Neutral (80) + fresh kicker", 80, 0, 0),
        ("Neutral (80) + kicker 3/3", 80, 3, 3),
        ("Aggressive (100) + kicker missed 2", 100, 3, 1),
        ("Aggressive (100) + fresh kicker", 100, 0, 0),
        ("Aggressive (100) + kicker 3/3", 100, 3, 3),
    ]
    for label, aggr, att, made in combos:
        coach = MockCoach(aggr)
        kicker = MockKicker(fgAtt=att, fgs=made)
        team = MockTeam(coach, kicker)
        tester = FgThresholdTester(team)
        t = tester._coachFgThreshold(coach)
        print(f"{label:<45} {fmtPct(t):>10}")

    # ── Part 4: What distance does each threshold translate to? ──
    print("\n--- Part 4: Max FG Distance at Threshold (75-rated kicker) ---")
    print("  Shows the longest FG a coach would attempt (prob >= threshold)")
    print(f"{'Scenario':<45} {'Thresh':>8} {'Max Dist':>10}")
    print("-" * 66)

    import math
    kickerRating = 75
    normalizedSkill = (kickerRating - 50) / 50

    for label, aggr, att, made in combos:
        coach = MockCoach(aggr)
        kicker = MockKicker(fgAtt=att, fgs=made, overallRating=kickerRating)
        team = MockTeam(coach, kicker)
        tester = FgThresholdTester(team)
        threshold = tester._coachFgThreshold(coach)

        # Find max distance where estimated prob >= threshold
        maxDist = 0
        for dist in range(20, 70):
            baseFgProb = 1 / (1 + math.exp(0.18 * (dist - 52)))
            fgProb = baseFgProb * (0.52 + normalizedSkill * 0.85)
            if dist < 30:
                fgProb = min(0.96, fgProb + 0.10)
            fgProb = max(0.05, min(0.96, fgProb))
            if fgProb >= threshold:
                maxDist = dist
        # Convert to field position (yardsToEndzone = fgDist - 17)
        fieldPos = maxDist - 17 if maxDist else 0
        print(f"{label:<45} {fmtPct(threshold):>8} {maxDist:>4}yd ({fieldPos} YTE)")

    # ── Part 5: Edge cases ──
    print("\n--- Part 5: Edge Cases ---")
    # No coach
    kicker = MockKicker(fgAtt=0, fgs=0)
    team = MockTeam(None, kicker)
    tester = FgThresholdTester(team)
    t = tester._coachFgThreshold(None)
    print(f"  No coach (None):                     {fmtPct(t)}")

    # No kicker
    team2 = MockTeam(MockCoach(80), None)
    tester2 = FgThresholdTester(team2)
    t2 = tester2._coachFgThreshold(MockCoach(80))
    print(f"  No kicker (None):                    {fmtPct(t2)}")

    # Extreme aggressive + perfect kicker (should floor at 10%)
    coach = MockCoach(100)
    kicker = MockKicker(fgAtt=5, fgs=5)
    team = MockTeam(coach, kicker)
    tester = FgThresholdTester(team)
    t = tester._coachFgThreshold(coach)
    print(f"  Max aggressive (100) + 5/5 perfect:  {fmtPct(t)} (floor=10%)")

    # Extreme conservative + 3 misses (should cap at 35%)
    coach = MockCoach(60)
    kicker = MockKicker(fgAtt=3, fgs=0)
    team = MockTeam(coach, kicker)
    tester = FgThresholdTester(team)
    t = tester._coachFgThreshold(coach)
    print(f"  Max conservative (60) + 0/3 misses:  {fmtPct(t)} (cap=35%)")


if __name__ == '__main__':
    runScenarios()
