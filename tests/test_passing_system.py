"""
Test suite for the new 5-stage passing system.
Tests probability distributions, sack mechanics, and pressure impacts.

This test file contains standalone implementations of the passing mechanics
to avoid circular import issues with the main game module.
"""

import numpy as np
from enum import Enum


class PassType(Enum):
    short = 1
    medium = 2
    long = 3
    hailMary = 4
    throwAway = 5


class PassType(Enum):
    short = 1
    medium = 2
    long = 3
    hailMary = 4
    throwAway = 5


def batched_randint(min_val, max_val):
    """Simple randint replacement for testing"""
    return np.random.randint(min_val, max_val + 1)


class PassingMechanics:
    """Standalone implementation of passing mechanics for testing"""
    
    @staticmethod
    def calculateSackProbability(defensePassRush: int, qbMobility: int, blockingModifier: int, dropbackDepth: int) -> float:
        """
        Calculate sack probability using logistic curve based on pass rush vs protection.
        Returns probability (0-100) that QB gets sacked.
        """
        qbProtection = qbMobility + blockingModifier
        rushDifferential = defensePassRush - qbProtection
        rushDifferential += (dropbackDepth - 1) * 5
        
        baseSackRate = 8.0
        steepness = 0.15
        probability = (baseSackRate * 2) / (1 + np.exp(-steepness * rushDifferential))
        
        return max(1, min(35, probability))
    
    @staticmethod
    def calculatePressureImpact(defensePassRush: int, qbAccuracy: int, blockingModifier: int) -> float:
        """
        Calculate throw quality degradation from defensive pressure.
        Returns degradation factor (0.6 to 1.0) where lower = more disruption.
        """
        qbPressureResistance = (qbAccuracy * 0.7) + blockingModifier
        pressureDifferential = defensePassRush - qbPressureResistance
        
        maxDegradation = 0.4
        steepness = 0.12
        
        degradationAmount = maxDegradation * (1 / (1 + np.exp(-steepness * pressureDifferential)))
        degradationFactor = 1.0 - degradationAmount
        
        return max(0.6, min(1.0, degradationFactor))
    
    @staticmethod
    def calculateReceiverOpenness(receiverRouteRunning: int, defensePassCoverage: int) -> float:
        """
        Stage 1: Calculate how open a receiver is on a scale of 0-100.
        """
        skillDifferential = receiverRouteRunning - defensePassCoverage
        meanOpenness = 50 + (skillDifferential / 2)
        meanOpenness = max(10, min(90, meanOpenness))
        stdDev = max(10, 25 - (receiverRouteRunning / 10))
        
        openness = np.random.normal(meanOpenness, stdDev)
        return max(0, min(100, openness))
    
    @staticmethod
    def selectPassTarget(targetList: list, qbVision: int, qbDiscipline: int):
        """
        Stage 2: QB finds and selects a receiver based on vision and discipline.
        Vision affects perceived openness accuracy.
        Returns: (selectedTarget, willThrowAway)
        """
        # Calculate how accurately QB perceives openness
        # High vision (90+): ±5% error, Medium (70-89): ±15% error, Low (<70): ±25% error
        if qbVision >= 90:
            visionErrorRange = 5
        elif qbVision >= 70:
            visionErrorRange = 15
        else:
            visionErrorRange = 25
        
        # Create perceived targets with vision-adjusted openness
        perceivedTargets = []
        for target in targetList:
            actualOpenness = target['openness']
            visionError = batched_randint(-visionErrorRange, visionErrorRange)
            perceivedOpenness = max(0, min(100, actualOpenness + visionError))
            
            perceivedTargets.append({
                'receiver': target['receiver'],
                'openness': perceivedOpenness,  # What QB thinks
                'actualOpenness': actualOpenness,  # What it really is
                'route': target['route']
            })
        
        # Sort by perceived openness (what QB thinks they see)
        sortedTargets = sorted(perceivedTargets, key=lambda t: t['openness'], reverse=True)
        
        # QB makes decision based on perceived openness
        for target in sortedTargets:
            perceivedOpenness = target['openness']
            
            # Discipline check using perceived openness
            if qbDiscipline >= 90:
                # Elite discipline: only throw to open receivers (60+) or throw away
                if perceivedOpenness >= 60 or batched_randint(1, 100) <= 20:
                    return (target, False)
            elif qbDiscipline >= 75:
                # Good discipline: prefer open, sometimes throw to partial (40+)
                if perceivedOpenness >= 40 or batched_randint(1, 100) <= 30:
                    return (target, False)
            elif qbDiscipline >= 60:
                # Average discipline: will throw to most receivers
                if perceivedOpenness >= 25 or batched_randint(1, 100) <= 50:
                    return (target, False)
            else:
                # Low discipline: throws to anyone, risky
                if batched_randint(1, 100) <= 70:
                    return (target, False)
        
        # No suitable receiver found - throw away or force it
        if qbDiscipline >= 80:
            return (None, True)  # Throw away
        elif batched_randint(1, 100) <= qbDiscipline:
            return (None, True)  # Throw away based on discipline
        else:
            # Force throw to what QB thinks is least covered
            return (sortedTargets[0], False)
    
    @staticmethod
    def calculateThrowQuality(passType, qbAccuracy: int, qbXFactor: int, defensePassRush: int, blockingModifier: int, qbPressureMod: float) -> float:
        """
        Stage 3: Calculate throw quality (0-100) based on QB skill, pass type, and pressure.
        """
        baseAccuracy = (qbAccuracy + qbXFactor) / 2 + qbPressureMod
        
        passTypeDifficulty = {
            PassType.short: 1.0,
            PassType.medium: 0.85,
            PassType.long: 0.7,
            PassType.hailMary: 0.5
        }
        difficultyMod = passTypeDifficulty.get(passType, 0.85)
        
        pressureDegradation = PassingMechanics.calculatePressureImpact(
            defensePassRush, qbAccuracy, blockingModifier
        )
        
        throwQuality = baseAccuracy * difficultyMod * pressureDegradation
        throwQuality += batched_randint(-10, 10)
        
        return max(5, min(100, throwQuality))
    
    @staticmethod
    def calculateCatchProbability(throwQuality: float, receiverHands: int, receiverOpenness: float, defensePassCoverage: int, receiverPressureMod: float) -> dict:
        """
        Stage 4: Calculate catch probability and interception risk.
        """
        adjustedHands = receiverHands + receiverPressureMod
        
        if throwQuality >= 70:
            baseCatchProb = adjustedHands * 0.9
        elif throwQuality >= 50:
            baseCatchProb = (adjustedHands * 0.6) + (receiverOpenness * 0.3)
        else:
            baseCatchProb = (adjustedHands * 0.4) + (receiverOpenness * 0.4)
        
        defenseFactor = max(0, (100 - receiverOpenness) / 100) * (defensePassCoverage / 100)
        catchProb = baseCatchProb * (1 - defenseFactor * 0.5)
        
        intProb = 0
        if throwQuality < 50 and receiverOpenness < 50:
            intProb = ((50 - throwQuality) / 10) * ((50 - receiverOpenness) / 50) * (defensePassCoverage / 100) * 12
        
        dropProb = max(0, (100 - baseCatchProb) * (defensePassCoverage / 200))
        
        return {
            'catchProb': min(95, max(5, catchProb)),
            'intProb': min(25, max(0, intProb)),
            'dropProb': min(30, max(0, dropProb))
        }
    
    @staticmethod
    def calculatePassYardage(passType, throwQuality: float) -> int:
        """
        Calculate air yards using Gaussian distribution based on pass type and throw quality.
        """
        passTypeParams = {
            PassType.short: {'mean': 3, 'stdDev': 1.5},
            PassType.medium: {'mean': 8, 'stdDev': 2.5},
            PassType.long: {'mean': 15, 'stdDev': 4},
            PassType.hailMary: {'mean': 50, 'stdDev': 10}
        }
        
        params = passTypeParams.get(passType, {'mean': 8, 'stdDev': 2.5})
        qualityFactor = throwQuality / 80
        adjustedMean = params['mean'] * qualityFactor
        airYards = int(np.random.normal(adjustedMean, params['stdDev']))
        
        return max(0, airYards)


class MockGame:
    """Mock game object for testing"""
    def __init__(self):
        self.gamePressure = 50
        self.isRegularSeasonGame = False
        self.homeScore = 14
        self.awayScore = 14
        self.currentQuarter = 2


class MockTeam:
    """Mock team object for testing"""
    def __init__(self, defensePassRushRating=70, defensePassCoverageRating=70):
        self.defensePassRushRating = defensePassRushRating
        self.defensePassCoverageRating = defensePassCoverageRating
        self.gameDefenseStats = {
            'sacks': 0,
            'ints': 0,
            'fumRec': 0,
            'passYardsAlwd': 0,
            'totalYardsAlwd': 0
        }


class MockPlayer:
    """Mock player for testing"""
    def __init__(self, **kwargs):
        self.attributes = PlayerAttributes()
        # Set specific attributes for testing
        for key, value in kwargs.items():
            if hasattr(self.attributes, key):
                setattr(self.attributes, value)
        
        self.gameAttributes = self.attributes
        
    def updateInGameConfidence(self, amount):
        pass


def test_receiver_openness():
    """Test Stage 1: Receiver openness probability distribution"""
    print("\n" + "="*70)
    print("STAGE 1: RECEIVER OPENNESS TEST")
    print("="*70)
    
    iterations = 10000
    
    # Test receivers with different route running skills against average coverage (70)
    receiver_skills = [
        (90, "Elite (90)"),
        (70, "Average (70)"),
        (50, "Poor (50)")
    ]
    
    print(f"\nTesting {iterations} iterations against 70 coverage:")
    print("-" * 70)
    
    for skill, label in receiver_skills:
        openness_values = []
        for _ in range(iterations):
            openness = PassingMechanics.calculateReceiverOpenness(skill, 70)
            openness_values.append(openness)
        
        covered = sum(1 for x in openness_values if x < 30)
        partial = sum(1 for x in openness_values if 30 <= x < 60)
        wide_open = sum(1 for x in openness_values if x >= 60)
        
        print(f"\n{label} Route Running:")
        print(f"  Covered (0-30):         {covered:5d} ({covered/iterations*100:5.1f}%)")
        print(f"  Partially Open (30-60): {partial:5d} ({partial/iterations*100:5.1f}%)")
        print(f"  Wide Open (60-100):     {wide_open:5d} ({wide_open/iterations*100:5.1f}%)")
        print(f"  Average Openness: {np.mean(openness_values):.1f}")


def test_qb_target_selection():
    """Test Stage 2: QB target selection based on vision and discipline"""
    print("\n" + "="*70)
    print("STAGE 2: QB TARGET SELECTION TEST")
    print("="*70)
    
    iterations = 10000
    
    # SCENARIO 1: One obvious target (wide open)
    print("\n" + "-"*70)
    print("SCENARIO 1: One Wide Open Receiver (80), Others Covered (45, 20)")
    print("-"*70)
    
    wide_open_target = {'receiver': 'WR1', 'openness': 80, 'route': PassType.medium}
    partial_target = {'receiver': 'WR2', 'openness': 45, 'route': PassType.short}
    covered_target = {'receiver': 'TE', 'openness': 20, 'route': PassType.long}
    targetList1 = [covered_target, partial_target, wide_open_target]
    
    qb_types = [
        (90, 90, "Elite Vision + Elite Discipline"),
        (60, 60, "Poor Vision + Poor Discipline")
    ]
    
    for vision, discipline, label in qb_types:
        throw_away = 0
        selected = {'WR1': 0, 'WR2': 0, 'TE': 0}
        
        for _ in range(iterations):
            target, will_throw = PassingMechanics.selectPassTarget(targetList1, vision, discipline)
            
            if will_throw or target is None:
                throw_away += 1
            else:
                selected[target['receiver']] += 1
        
        print(f"\n{label}:")
        print(f"  WR1 (80 open):  {selected['WR1']:5d} ({selected['WR1']/iterations*100:5.1f}%)")
        print(f"  WR2 (45 open):  {selected['WR2']:5d} ({selected['WR2']/iterations*100:5.1f}%)")
        print(f"  TE  (20 open):  {selected['TE']:5d} ({selected['TE']/iterations*100:5.1f}%)")
        print(f"  Throw Away:     {throw_away:5d} ({throw_away/iterations*100:5.1f}%)")
    
    # SCENARIO 2: All receivers moderately covered (no wide open option)
    print("\n" + "-"*70)
    print("SCENARIO 2: All Moderately Covered (55, 45, 35)")
    print("-"*70)
    
    target1 = {'receiver': 'WR1', 'openness': 55, 'route': PassType.medium}
    target2 = {'receiver': 'WR2', 'openness': 45, 'route': PassType.short}
    target3 = {'receiver': 'TE', 'openness': 35, 'route': PassType.long}
    targetList2 = [target3, target2, target1]
    
    qb_types = [
        (90, 90, "Elite Vision + Elite Discipline"),
        (90, 60, "Elite Vision + Poor Discipline"),
        (60, 90, "Poor Vision + Elite Discipline"),
        (60, 60, "Poor Vision + Poor Discipline")
    ]
    
    for vision, discipline, label in qb_types:
        throw_away = 0
        selected = {'WR1': 0, 'WR2': 0, 'TE': 0}
        
        for _ in range(iterations):
            target, will_throw = PassingMechanics.selectPassTarget(targetList2, vision, discipline)
            
            if will_throw or target is None:
                throw_away += 1
            else:
                selected[target['receiver']] += 1
        
        print(f"\n{label}:")
        print(f"  WR1 (55 open):  {selected['WR1']:5d} ({selected['WR1']/iterations*100:5.1f}%)")
        print(f"  WR2 (45 open):  {selected['WR2']:5d} ({selected['WR2']/iterations*100:5.1f}%)")
        print(f"  TE  (35 open):  {selected['TE']:5d} ({selected['TE']/iterations*100:5.1f}%)")
        print(f"  Throw Away:     {throw_away:5d} ({throw_away/iterations*100:5.1f}%)")
    
    # SCENARIO 3: All receivers well covered (testing throw away behavior)
    print("\n" + "-"*70)
    print("SCENARIO 3: All Well Covered (30, 25, 18)")
    print("-"*70)
    
    target1 = {'receiver': 'WR1', 'openness': 30, 'route': PassType.short}
    target2 = {'receiver': 'WR2', 'openness': 25, 'route': PassType.medium}
    target3 = {'receiver': 'TE', 'openness': 18, 'route': PassType.long}
    targetList3 = [target3, target2, target1]
    
    for vision, discipline, label in qb_types:
        throw_away = 0
        selected = {'WR1': 0, 'WR2': 0, 'TE': 0}
        
        for _ in range(iterations):
            target, will_throw = PassingMechanics.selectPassTarget(targetList3, vision, discipline)
            
            if will_throw or target is None:
                throw_away += 1
            else:
                selected[target['receiver']] += 1
        
        print(f"\n{label}:")
        print(f"  WR1 (30 open):  {selected['WR1']:5d} ({selected['WR1']/iterations*100:5.1f}%)")
        print(f"  WR2 (25 open):  {selected['WR2']:5d} ({selected['WR2']/iterations*100:5.1f}%)")
        print(f"  TE  (18 open):  {selected['TE']:5d} ({selected['TE']/iterations*100:5.1f}%)")
        print(f"  Throw Away:     {throw_away:5d} ({throw_away/iterations*100:5.1f}%)")
    
    # SCENARIO 4: One slightly open, rest covered (edge case)
    print("\n" + "-"*70)
    print("SCENARIO 4: One Slightly Open (65), Others Covered (25, 20)")
    print("-"*70)
    
    target1 = {'receiver': 'WR1', 'openness': 65, 'route': PassType.medium}
    target2 = {'receiver': 'WR2', 'openness': 25, 'route': PassType.short}
    target3 = {'receiver': 'TE', 'openness': 20, 'route': PassType.long}
    targetList4 = [target3, target2, target1]
    
    for vision, discipline, label in qb_types:
        throw_away = 0
        selected = {'WR1': 0, 'WR2': 0, 'TE': 0}
        
        for _ in range(iterations):
            target, will_throw = PassingMechanics.selectPassTarget(targetList4, vision, discipline)
            
            if will_throw or target is None:
                throw_away += 1
            else:
                selected[target['receiver']] += 1
        
        print(f"\n{label}:")
        print(f"  WR1 (65 open):  {selected['WR1']:5d} ({selected['WR1']/iterations*100:5.1f}%)")
        print(f"  WR2 (25 open):  {selected['WR2']:5d} ({selected['WR2']/iterations*100:5.1f}%)")
        print(f"  TE  (20 open):  {selected['TE']:5d} ({selected['TE']/iterations*100:5.1f}%)")
        print(f"  Throw Away:     {throw_away:5d} ({throw_away/iterations*100:5.1f}%)")
    
    # SCENARIO 5: Close openness values (testing vision differentiation)
    print("\n" + "-"*70)
    print("SCENARIO 5: Very Close Openness Values (52, 50, 48)")
    print("-"*70)
    
    target1 = {'receiver': 'WR1', 'openness': 52, 'route': PassType.medium}
    target2 = {'receiver': 'WR2', 'openness': 50, 'route': PassType.short}
    target3 = {'receiver': 'TE', 'openness': 48, 'route': PassType.long}
    targetList5 = [target3, target2, target1]
    
    for vision, discipline, label in qb_types:
        throw_away = 0
        selected = {'WR1': 0, 'WR2': 0, 'TE': 0}
        
        for _ in range(iterations):
            target, will_throw = PassingMechanics.selectPassTarget(targetList5, vision, discipline)
            
            if will_throw or target is None:
                throw_away += 1
            else:
                selected[target['receiver']] += 1
        
        print(f"\n{label}:")
        print(f"  WR1 (52 open):  {selected['WR1']:5d} ({selected['WR1']/iterations*100:5.1f}%)")
        print(f"  WR2 (50 open):  {selected['WR2']:5d} ({selected['WR2']/iterations*100:5.1f}%)")
        print(f"  TE  (48 open):  {selected['TE']:5d} ({selected['TE']/iterations*100:5.1f}%)")
        print(f"  Throw Away:     {throw_away:5d} ({throw_away/iterations*100:5.1f}%)")


def test_sack_probability():
    """Test sack probability logistic curve"""
    print("\n" + "="*70)
    print("SACK PROBABILITY TEST (Logistic Curve)")
    print("="*70)
    
    print("\nSack probability across different matchups:")
    print("-" * 70)
    print(f"{'Defense Rush':<15} {'QB Mobility':<15} {'Blocking':<12} {'Sack %':<10}")
    print("-" * 70)
    
    # Test various matchups
    scenarios = [
        (90, 60, 0, "Elite rush vs mobile QB"),
        (90, 70, 10, "Elite rush vs protected QB"),
        (70, 70, 0, "Even matchup"),
        (50, 70, 10, "Poor rush vs protected QB"),
        (60, 90, 0, "Average rush vs elite mobility"),
    ]
    
    for rush, mobility, blocking, description in scenarios:
        sack_prob = PassingMechanics.calculateSackProbability(rush, mobility, blocking, 2)  # 5-step drop
        print(f"{rush:<15} {mobility:<15} {blocking:<12} {sack_prob:>5.1f}%    ({description})")
    
    # Test dropback depth impact
    print("\nDropback depth impact (Defense: 80, Mobility: 70, Blocking: 5):")
    print("-" * 70)
    for depth in [1, 2, 3]:
        depth_names = {1: "3-step", 2: "5-step", 3: "7-step"}
        sack_prob = PassingMechanics.calculateSackProbability(80, 70, 5, depth)
        print(f"  {depth_names[depth]} dropback: {sack_prob:>5.1f}%")


def test_pressure_impact():
    """Test throw quality degradation from pressure"""
    print("\n" + "="*70)
    print("PRESSURE IMPACT ON THROW QUALITY TEST")
    print("="*70)
    
    print("\nThrow quality degradation across different matchups:")
    print("-" * 70)
    print(f"{'Defense Rush':<15} {'QB Accuracy':<15} {'Blocking':<12} {'Degradation':<15} {'Quality Factor':<15}")
    print("-" * 70)
    
    scenarios = [
        (90, 80, 0, "Elite rush vs accurate QB"),
        (90, 80, 15, "Elite rush vs well-protected QB"),
        (70, 70, 0, "Even matchup"),
        (50, 70, 10, "Poor rush vs protected QB"),
    ]
    
    for rush, accuracy, blocking, description in scenarios:
        degradation = PassingMechanics.calculatePressureImpact(rush, accuracy, blocking)
        quality_loss = (1.0 - degradation) * 100
        print(f"{rush:<15} {accuracy:<15} {blocking:<12} {quality_loss:>5.1f}%          {degradation:.2f}x         ({description})")


def test_throw_quality():
    """Test Stage 3: Throw quality calculation"""
    print("\n" + "="*70)
    print("STAGE 3: THROW QUALITY TEST")
    print("="*70)
    
    iterations = 5000
    
    # Test different scenarios
    scenarios = [
        (PassType.short, 85, 80, 60, 10, 0, "Elite QB, short pass, low pressure"),
        (PassType.long, 85, 80, 60, 10, 0, "Elite QB, deep pass, low pressure"),
        (PassType.medium, 85, 80, 90, 5, 0, "Elite QB, medium pass, heavy pressure"),
        (PassType.short, 65, 60, 70, 8, 0, "Average QB, short pass, moderate pressure"),
    ]
    
    print(f"\nTesting {iterations} iterations for each scenario:")
    print("-" * 70)
    
    for pass_type, accuracy, xfactor, rush, blocking, pressure_mod, description in scenarios:
        qualities = []
        for _ in range(iterations):
            quality = PassingMechanics.calculateThrowQuality(
                pass_type, accuracy, xfactor, rush, blocking, pressure_mod
            )
            qualities.append(quality)
        
        excellent = sum(1 for q in qualities if q >= 70)
        good = sum(1 for q in qualities if 50 <= q < 70)
        poor = sum(1 for q in qualities if q < 50)
        
        print(f"\n{description}:")
        print(f"  Excellent (70+): {excellent:5d} ({excellent/iterations*100:5.1f}%)")
        print(f"  Good (50-69):    {good:5d} ({good/iterations*100:5.1f}%)")
        print(f"  Poor (<50):      {poor:5d} ({poor/iterations*100:5.1f}%)")
        print(f"  Average Quality: {np.mean(qualities):.1f}")


def test_catch_probability():
    """Test Stage 4: Catch probability, interception, and drop calculations"""
    print("\n" + "="*70)
    print("STAGE 4: CATCH PROBABILITY TEST")
    print("="*70)
    
    scenarios = [
        (85, 85, 80, 70, 0, "Great throw to wide open receiver"),
        (85, 75, 40, 80, 0, "Great throw to covered receiver"),
        (40, 85, 80, 70, 0, "Bad throw to open receiver"),
        (40, 75, 30, 85, 0, "Bad throw to covered receiver (INT risk)"),
        (70, 70, 50, 75, 0, "Average scenario"),
    ]
    
    print("\nCatch probabilities across scenarios:")
    print("-" * 70)
    print(f"{'Scenario':<45} {'Catch%':<10} {'INT%':<10} {'Drop%':<10}")
    print("-" * 70)
    
    for throw_qual, hands, openness, defense, pressure_mod, description in scenarios:
        probs = PassingMechanics.calculateCatchProbability(throw_qual, hands, openness, defense, pressure_mod)
        print(f"{description:<45} {probs['catchProb']:>5.1f}%    {probs['intProb']:>5.1f}%    {probs['dropProb']:>5.1f}%")


def test_pass_yardage():
    """Test air yardage Gaussian distributions"""
    print("\n" + "="*70)
    print("AIR YARDAGE DISTRIBUTION TEST")
    print("="*70)
    
    iterations = 10000
    
    scenarios = [
        (PassType.short, 80, "Short pass, good throw"),
        (PassType.medium, 80, "Medium pass, good throw"),
        (PassType.long, 80, "Deep pass, good throw"),
        (PassType.short, 50, "Short pass, poor throw"),
        (PassType.long, 40, "Deep pass, poor throw"),
    ]
    
    print(f"\nTesting {iterations} iterations for each pass type:")
    print("-" * 70)
    
    for pass_type, throw_quality, description in scenarios:
        yardages = []
        for _ in range(iterations):
            yards = PassingMechanics.calculatePassYardage(pass_type, throw_quality)
            yardages.append(yards)
        
        print(f"\n{description}:")
        print(f"  Average Yards: {np.mean(yardages):.1f}")
        print(f"  Min: {min(yardages)}, Max: {max(yardages)}")
        print(f"  Std Dev: {np.std(yardages):.1f}")


def test_sack_yardage_distribution():
    """Test sack yardage exponential distribution"""
    print("\n" + "="*70)
    print("SACK YARDAGE DISTRIBUTION TEST")
    print("="*70)
    
    iterations = 10000
    
    # Test different rush advantages
    scenarios = [
        (0, "Even matchup (Defense: 70, QB Mobility: 70)"),
        (10, "Moderate rush advantage (Defense: 80, QB Mobility: 70)"),
        (20, "Strong rush advantage (Defense: 90, QB Mobility: 70)"),
    ]
    
    print(f"\nTesting {iterations} sacks for each scenario:")
    print("-" * 70)
    
    for rush_advantage, description in scenarios:
        sack_yardages = np.arange(0, 16)
        sack_decay_rate = max(0.3, 0.5 - rush_advantage / 20)
        sack_curve = np.exp(-sack_decay_rate * sack_yardages)
        sack_curve /= np.sum(sack_curve)
        
        yards = []
        for _ in range(iterations):
            sack_yards = int(np.random.choice(sack_yardages, p=sack_curve))
            yards.append(sack_yards)
        
        short = sum(1 for y in yards if y <= 3)
        medium = sum(1 for y in yards if 4 <= y <= 7)
        long = sum(1 for y in yards if y >= 8)
        
        print(f"\n{description}:")
        print(f"  0-3 yards:  {short:5d} ({short/iterations*100:5.1f}%)")
        print(f"  4-7 yards:  {medium:5d} ({medium/iterations*100:5.1f}%)")
        print(f"  8+ yards:   {long:5d} ({long/iterations*100:5.1f}%)")
        print(f"  Average: {np.mean(yards):.1f} yards")


def run_all_tests():
    """Run all passing system tests"""
    print("\n" + "="*70)
    print("PASSING SYSTEM COMPREHENSIVE TEST SUITE")
    print("="*70)
    
    test_receiver_openness()
    test_qb_target_selection()
    test_sack_probability()
    test_pressure_impact()
    test_throw_quality()
    test_catch_probability()
    test_pass_yardage()
    test_sack_yardage_distribution()
    
    print("\n" + "="*70)
    print("ALL TESTS COMPLETE")
    print("="*70 + "\n")


if __name__ == "__main__":
    run_all_tests()
