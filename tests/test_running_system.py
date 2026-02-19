"""
Test suite for improved running play mechanics.
Tests vision-based gap selection and discipline-based decision making.
Similar structure to test_passing_system.py
"""

import numpy as np
from random_batch import batched_randint, batched_random, batched_choice
import enum


class PlayType(enum.Enum):
    Run = 'Run'
    Pass = 'Pass'


class PlayResult(enum.Enum):
    FirstDown = '1st Down'
    Fumble = 'Fumble'


class RunningMechanics:
    """Standalone copy of running mechanics for testing"""
    
    def __init__(self):
        self.playType = None
        self.yardage = 0
        self.isFumble = False
        self.isFumbleLost = False
        self.playResult = None
    
    def calculateGapQuality(self, gapType: str, rbPower: int, rbAgility: int, blockingRating: int, defenseRunCoverage: int) -> float:
        """Calculate how good each gap is (0-100)"""
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
        skillDifferential = offenseStrength - defenseRunCoverage
        
        meanQuality = 50 + (skillDifferential / 2.5)
        meanQuality = max(10, min(90, meanQuality))
        
        if gapType == 'bounce':
            stdDev = 30
        elif gapType == 'C-gap':
            stdDev = 20
        else:
            stdDev = 15
        
        quality = np.random.normal(meanQuality, stdDev)
        return max(0, min(100, quality))
    
    def selectRunGap(self, gapList: list, rbVision: int, rbDiscipline: int):
        """RB selects gap based on vision and discipline"""
        # Vision error ranges
        if rbVision >= 85:
            visionErrorRange = 5
        elif rbVision >= 70:
            visionErrorRange = 15
        else:
            visionErrorRange = 25
        
        # Create perceived gaps
        perceivedGaps = []
        for gap in gapList:
            actualQuality = gap['quality']
            visionError = batched_randint(-visionErrorRange, visionErrorRange)
            perceivedQuality = max(0, min(100, actualQuality + visionError))
            
            perceivedGaps.append({
                'type': gap['type'],
                'quality': perceivedQuality,
                'actualQuality': actualQuality,
                'isDesigned': gap['isDesigned']
            })
        
        # Sort by perceived quality
        sortedGaps = sorted(perceivedGaps, key=lambda g: g['quality'], reverse=True)
        
        # Find designed gap and best perceived
        designedGap = next((g for g in sortedGaps if g['isDesigned']), sortedGaps[0])
        bestPerceivedGap = sortedGaps[0]
        
        # Discipline-based decision
        if rbDiscipline >= 85:
            if designedGap['quality'] >= 30 or batched_randint(1, 100) <= 90:
                return designedGap
            else:
                return bestPerceivedGap
        elif rbDiscipline >= 70:
            if designedGap['quality'] >= 25 or batched_randint(1, 100) <= 70:
                return designedGap
            else:
                return bestPerceivedGap
        elif rbDiscipline >= 55:
            if designedGap['quality'] >= 40 and batched_randint(1, 100) <= 60:
                return designedGap
            else:
                return bestPerceivedGap
        else:
            if batched_randint(1, 100) <= 40:
                return designedGap
            else:
                bounceGap = next((g for g in sortedGaps if g['type'] == 'bounce'), bestPerceivedGap)
                return bounceGap


def test_gap_quality_calculation():
    """Test that different gaps produce different quality ratings"""
    print("\n" + "="*80)
    print("TEST 1: Gap Quality Calculation")
    print("="*80)
    
    mechanics = RunningMechanics()
    
    # Test power back vs speed back in different gaps
    scenarios = [
        {
            'name': 'Power Back (90 power, 70 agility) vs Average Defense (75)',
            'rbPower': 90,
            'rbAgility': 70,
            'blocking': 80,
            'defense': 75
        },
        {
            'name': 'Speed Back (70 power, 90 agility) vs Average Defense (75)',
            'rbPower': 70,
            'rbAgility': 90,
            'blocking': 80,
            'defense': 75
        },
        {
            'name': 'Average Back (75/75) vs Elite Defense (90)',
            'rbPower': 75,
            'rbAgility': 75,
            'blocking': 70,
            'defense': 90
        }
    ]
    
    for scenario in scenarios:
        print(f"\n{scenario['name']}")
        print("-" * 80)
        
        gapQualities = {}
        for _ in range(100):
            for gapType in ['A-gap', 'B-gap', 'C-gap', 'bounce']:
                quality = mechanics.calculateGapQuality(
                    gapType,
                    scenario['rbPower'],
                    scenario['rbAgility'],
                    scenario['blocking'],
                    scenario['defense']
                )
                if gapType not in gapQualities:
                    gapQualities[gapType] = []
                gapQualities[gapType].append(quality)
        
        for gapType in ['A-gap', 'B-gap', 'C-gap', 'bounce']:
            avgQuality = np.mean(gapQualities[gapType])
            stdDev = np.std(gapQualities[gapType])
            print(f"  {gapType:12s}: {avgQuality:5.1f} quality (σ={stdDev:4.1f})")


def test_vision_impact_on_gap_selection():
    """Test how vision affects gap perception and selection"""
    print("\n" + "="*80)
    print("TEST 2: Vision Impact on Gap Selection")
    print("="*80)
    
    mechanics = RunningMechanics()
    
    # Scenario: A-gap is open (70), B-gap moderate (50), C-gap stuffed (25), bounce risky (40)
    testGaps = [
        {'type': 'A-gap', 'quality': 70, 'isDesigned': True},
        {'type': 'B-gap', 'quality': 50, 'isDesigned': False},
        {'type': 'C-gap', 'quality': 25, 'isDesigned': False},
        {'type': 'bounce', 'quality': 40, 'isDesigned': False}
    ]
    
    visionLevels = [
        ('Elite Vision (90)', 90),
        ('Good Vision (75)', 75),
        ('Poor Vision (65)', 65)
    ]
    
    discipline = 80  # High discipline to isolate vision impact
    
    for visionName, visionRating in visionLevels:
        print(f"\n{visionName} | High Discipline (80)")
        print("-" * 80)
        
        selections = {'A-gap': 0, 'B-gap': 0, 'C-gap': 0, 'bounce': 0}
        visionErrors = []
        correctReads = 0
        
        for _ in range(1000):
            selected = mechanics.selectRunGap(testGaps, visionRating, discipline)
            selections[selected['type']] += 1
            
            # Track vision error
            visionError = abs(selected['quality'] - selected['actualQuality'])
            visionErrors.append(visionError)
            
            # Did they pick the designed (open) gap?
            if selected['isDesigned']:
                correctReads += 1
        
        print(f"  A-gap (designed, 70 quality): {selections['A-gap']:4d} selections ({selections['A-gap']/10:.1f}%)")
        print(f"  B-gap (moderate, 50 quality):  {selections['B-gap']:4d} selections ({selections['B-gap']/10:.1f}%)")
        print(f"  C-gap (stuffed, 25 quality):   {selections['C-gap']:4d} selections ({selections['C-gap']/10:.1f}%)")
        print(f"  Bounce (risky, 40 quality):    {selections['bounce']:4d} selections ({selections['bounce']/10:.1f}%)")
        print(f"  Average vision error: {np.mean(visionErrors):.1f} quality points")
        print(f"  Correct reads (hit designed gap): {correctReads}/1000 ({correctReads/10:.1f}%)")


def test_discipline_impact_on_gap_selection():
    """Test how discipline affects sticking to designed play vs audibling"""
    print("\n" + "="*80)
    print("TEST 3: Discipline Impact on Gap Selection")
    print("="*80)
    
    mechanics = RunningMechanics()
    
    disciplineLevels = [
        ('Elite Discipline (90)', 90),
        ('Good Discipline (75)', 75),
        ('Average Discipline (60)', 60),
        ('Poor Discipline (45)', 45)
    ]
    
    vision = 85  # High vision to isolate discipline impact
    
    # Scenario 1: Designed gap is moderate, another gap looks better
    print("\nScenario 1: Designed gap (B-gap) moderate (45), A-gap looks better (65)")
    print("-" * 80)
    
    scenario1Gaps = [
        {'type': 'A-gap', 'quality': 65, 'isDesigned': False},
        {'type': 'B-gap', 'quality': 45, 'isDesigned': True},
        {'type': 'C-gap', 'quality': 30, 'isDesigned': False},
        {'type': 'bounce', 'quality': 35, 'isDesigned': False}
    ]
    
    for disciplineName, disciplineRating in disciplineLevels:
        selections = {'A-gap': 0, 'B-gap': 0, 'C-gap': 0, 'bounce': 0}
        
        for _ in range(1000):
            selected = mechanics.selectRunGap(scenario1Gaps, vision, disciplineRating)
            selections[selected['type']] += 1
        
        designedRate = selections['B-gap'] / 10
        audibledRate = selections['A-gap'] / 10
        
        print(f"  {disciplineName:30s}: Designed={designedRate:5.1f}%, Audible to better={audibledRate:5.1f}%")
    
    # Scenario 2: Designed gap is terrible, another gap looks much better
    print("\nScenario 2: Designed gap (A-gap) terrible (20), C-gap looks much better (70)")
    print("-" * 80)
    
    scenario2Gaps = [
        {'type': 'A-gap', 'quality': 20, 'isDesigned': True},
        {'type': 'B-gap', 'quality': 40, 'isDesigned': False},
        {'type': 'C-gap', 'quality': 70, 'isDesigned': False},
        {'type': 'bounce', 'quality': 50, 'isDesigned': False}
    ]
    
    for disciplineName, disciplineRating in disciplineLevels:
        selections = {'A-gap': 0, 'B-gap': 0, 'C-gap': 0, 'bounce': 0}
        
        for _ in range(1000):
            selected = mechanics.selectRunGap(scenario2Gaps, vision, disciplineRating)
            selections[selected['type']] += 1
        
        designedRate = selections['A-gap'] / 10
        bounceRate = selections['bounce'] / 10
        
        print(f"  {disciplineName:30s}: Designed={designedRate:5.1f}%, Audible={100-designedRate:5.1f}% (bounce={bounceRate:4.1f}%)")


def test_rb_archetypes():
    """Test different RB archetypes to show mental vs physical attributes"""
    print("\n" + "="*80)
    print("TEST 4: RB Archetypes - Mental vs Physical Attributes")
    print("="*80)
    
    mechanics = RunningMechanics()
    
    # Define RB archetypes
    archetypes = [
        {
            'name': 'Elite Vision/Discipline (Smart Vet)',
            'power': 75,
            'agility': 75,
            'vision': 90,
            'discipline': 90,
            'description': 'Average physical, elite mental'
        },
        {
            'name': 'Elite Physical (Raw Talent)',
            'power': 90,
            'agility': 90,
            'vision': 60,
            'discipline': 55,
            'description': 'Elite physical, poor mental'
        },
        {
            'name': 'Power Back (Low Discipline)',
            'power': 90,
            'agility': 70,
            'vision': 70,
            'discipline': 50,
            'description': 'Bounces outside looking for home run'
        },
        {
            'name': 'Balanced Back',
            'power': 80,
            'agility': 80,
            'vision': 80,
            'discipline': 80,
            'description': 'All attributes good'
        }
    ]
    
    # Test scenario: B-gap is designed and best (quality 65), others are moderate/poor
    testGaps = [
        {'type': 'A-gap', 'quality': 40, 'isDesigned': False},
        {'type': 'B-gap', 'quality': 65, 'isDesigned': True},
        {'type': 'C-gap', 'quality': 35, 'isDesigned': False},
        {'type': 'bounce', 'quality': 30, 'isDesigned': False}
    ]
    
    for archetype in archetypes:
        print(f"\n{archetype['name']} - {archetype['description']}")
        print(f"  Power={archetype['power']}, Agility={archetype['agility']}, Vision={archetype['vision']}, Discipline={archetype['discipline']}")
        print("-" * 80)
        
        selections = {'A-gap': 0, 'B-gap': 0, 'C-gap': 0, 'bounce': 0}
        visionErrors = []
        correctReads = 0
        
        for _ in range(1000):
            selected = mechanics.selectRunGap(
                testGaps,
                archetype['vision'],
                archetype['discipline']
            )
            selections[selected['type']] += 1
            
            visionError = abs(selected['quality'] - selected['actualQuality'])
            visionErrors.append(visionError)
            
            if selected['type'] == 'B-gap':
                correctReads += 1
        
        print(f"  Correct reads (hit best gap): {correctReads}/1000 ({correctReads/10:.1f}%)")
        print(f"  Average vision error: {np.mean(visionErrors):.1f} quality points")
        print(f"  Gap selection breakdown:")
        for gap in ['A-gap', 'B-gap', 'C-gap', 'bounce']:
            print(f"    {gap:8s}: {selections[gap]:4d} ({selections[gap]/10:5.1f}%)")


def simulate_full_running_play(rbPower, rbAgility, rbVision, rbDiscipline, blocking, defenseRunCoverage, yardsToEndzone=50):
    """
    Simulate a complete running play with yardage outcome.
    Simplified version of the full runPlay logic.
    """
    mechanics = RunningMechanics()
    
    # STAGE 1: Calculate gap qualities
    designedGapType = batched_choice(['A-gap', 'B-gap', 'C-gap'])
    gapList = []
    for gapType in ['A-gap', 'B-gap', 'C-gap', 'bounce']:
        quality = mechanics.calculateGapQuality(gapType, rbPower, rbAgility, blocking, defenseRunCoverage)
        gapList.append({
            'type': gapType,
            'quality': quality,
            'isDesigned': (gapType == designedGapType)
        })
    
    # STAGE 2: RB selects gap
    selectedGap = mechanics.selectRunGap(gapList, rbVision, rbDiscipline)
    gapQuality = selectedGap['actualQuality']
    
    # STAGE 3: Calculate yardage
    rbPowerRating = (rbPower * 1.5 + rbAgility * 1.2 + 75 * 0.8 + 70 * 0.5) / 4  # Assume playmaking=75, xfactor=70
    stage1Offense = (rbPowerRating * 0.8) + (blocking * 0.2)
    qualityBonus = (gapQuality - 50) / 10
    adjustedOffense = stage1Offense + qualityBonus
    
    # Calculate initial burst
    stage1MaxYards = min(10, yardsToEndzone + 5)
    stage1Yardages = np.arange(0, stage1MaxYards + 1)
    
    mean_stage1 = (adjustedOffense - defenseRunCoverage) / 5
    mean_stage1 = min(stage1MaxYards + 1, max(0, mean_stage1))
    
    relative_strength = ((adjustedOffense * 2) - defenseRunCoverage) / 100
    absolute_skill = (adjustedOffense + defenseRunCoverage) / 200
    std_dev_stage1 = max(1, (stage1MaxYards + 1) / 4 * (1 + relative_strength) * absolute_skill)
    
    stage1Curve = np.exp(-((stage1Yardages - mean_stage1) ** 2) / (2 * std_dev_stage1 ** 2))
    stage1Curve /= np.sum(stage1Curve)
    
    stage1YardsGained = int(np.random.choice(stage1Yardages, p=stage1Curve))
    yardage = stage1YardsGained
    
    # STAGE 4: Breakaway potential
    if yardage < yardsToEndzone and stage1YardsGained >= stage1MaxYards * 0.5:
        stage2Offense = ((rbAgility * 1.5 + rbAgility * 1.2 + 75 * 0.8 + 70 * 0.5) / 4)  # Speed≈agility for simplicity
        offenseContribution2 = (1.2 * stage2Offense) / 100
        defenseContribution = 0.4 * defenseRunCoverage / 100
        stage2DecayRate = round(0.1 + 0.1 * (np.exp(defenseContribution) - offenseContribution2), 3)
        
        stage2MaxYards = min(10, yardsToEndzone + 5)
        stage2Yardages = np.arange(0, stage2MaxYards + 1)
        stage2Curve = np.exp(-stage2DecayRate * stage2Yardages)
        stage2Curve /= np.sum(stage2Curve)
        
        stage2YardsGained = int(np.random.choice(stage2Yardages, p=stage2Curve))
        yardage += stage2YardsGained
    
    return {
        'yardage': min(yardage, yardsToEndzone),
        'selectedGap': selectedGap['type'],
        'gapQuality': gapQuality,
        'isDesigned': selectedGap['isDesigned']
    }


def test_skill_matchups_with_yardage():
    """Test different skill level matchups and show yardage breakdowns"""
    print("\n" + "="*80)
    print("TEST 5: Skill Level Matchups - Yardage Breakdown")
    print("="*80)
    
    # Define matchups
    matchups = [
        {
            'name': 'Elite RB vs Average Defense',
            'rb': {'power': 90, 'agility': 88, 'vision': 85, 'discipline': 82},
            'defense': 70,
            'blocking': 75
        },
        {
            'name': 'Elite RB vs Elite Defense',
            'rb': {'power': 90, 'agility': 88, 'vision': 85, 'discipline': 82},
            'defense': 90,
            'blocking': 75
        },
        {
            'name': 'Average RB vs Average Defense',
            'rb': {'power': 75, 'agility': 75, 'vision': 72, 'discipline': 70},
            'defense': 75,
            'blocking': 72
        },
        {
            'name': 'Average RB vs Elite Defense',
            'rb': {'power': 75, 'agility': 75, 'vision': 72, 'discipline': 70},
            'defense': 90,
            'blocking': 72
        },
        {
            'name': 'Poor RB vs Average Defense',
            'rb': {'power': 65, 'agility': 63, 'vision': 60, 'discipline': 58},
            'defense': 75,
            'blocking': 68
        },
        {
            'name': 'Elite Physical/Poor Mental vs Average Defense',
            'rb': {'power': 92, 'agility': 90, 'vision': 62, 'discipline': 55},
            'defense': 75,
            'blocking': 75
        },
        {
            'name': 'Average Physical/Elite Mental vs Average Defense',
            'rb': {'power': 75, 'agility': 73, 'vision': 92, 'discipline': 90},
            'defense': 75,
            'blocking': 75
        }
    ]
    
    for matchup in matchups:
        print(f"\n{matchup['name']}")
        rb = matchup['rb']
        print(f"  RB: Power={rb['power']}, Agility={rb['agility']}, Vision={rb['vision']}, Disc={rb['discipline']}")
        print(f"  Defense: {matchup['defense']}, Blocking: {matchup['blocking']}")
        print("-" * 80)
        
        results = []
        gapSelections = {'A-gap': 0, 'B-gap': 0, 'C-gap': 0, 'bounce': 0}
        designedGapHits = 0
        
        for _ in range(500):
            result = simulate_full_running_play(
                rb['power'], rb['agility'], rb['vision'], rb['discipline'],
                matchup['blocking'], matchup['defense']
            )
            results.append(result)
            gapSelections[result['selectedGap']] += 1
            if result['isDesigned']:
                designedGapHits += 1
        
        # Calculate statistics
        yards = [r['yardage'] for r in results]
        avgYards = np.mean(yards)
        medianYards = np.median(yards)
        
        stuffedRate = sum(1 for y in yards if y <= 0) / len(yards) * 100
        shortGainRate = sum(1 for y in yards if 1 <= y <= 3) / len(yards) * 100
        successRate = sum(1 for y in yards if y >= 4) / len(yards) * 100
        bigPlayRate = sum(1 for y in yards if y >= 10) / len(yards) * 100
        explosiveRate = sum(1 for y in yards if y >= 20) / len(yards) * 100
        
        print(f"  Yards per Carry: {avgYards:.2f} (median: {medianYards:.1f})")
        print(f"  Stuffed (≤0 yards): {stuffedRate:5.1f}%")
        print(f"  Short gain (1-3):   {shortGainRate:5.1f}%")
        print(f"  Success (≥4 yards): {successRate:5.1f}%")
        print(f"  Big play (≥10):     {bigPlayRate:5.1f}%")
        print(f"  Explosive (≥20):    {explosiveRate:5.1f}%")
        print(f"  Hit designed gap:   {designedGapHits/5:.1f}%")
        print(f"  Gap selection: A={gapSelections['A-gap']/5:.0f}%, B={gapSelections['B-gap']/5:.0f}%, C={gapSelections['C-gap']/5:.0f}%, Bounce={gapSelections['bounce']/5:.0f}%")


def test_rb_archetypes_with_yardage():
    """Compare RB archetypes with actual yardage outcomes"""
    print("\n" + "="*80)
    print("TEST 6: RB Archetype Comparison - Full Simulation")
    print("="*80)
    
    archetypes = [
        {
            'name': 'Elite All-Around (Superstar)',
            'power': 90, 'agility': 90, 'vision': 88, 'discipline': 85,
            'description': 'Elite everything'
        },
        {
            'name': 'Smart Veteran',
            'power': 75, 'agility': 73, 'vision': 92, 'discipline': 90,
            'description': 'Average physical, elite mental'
        },
        {
            'name': 'Raw Talent (Bust Risk)',
            'power': 92, 'agility': 90, 'vision': 62, 'discipline': 55,
            'description': 'Elite physical, poor mental - wastes talent'
        },
        {
            'name': 'Power Back',
            'power': 92, 'agility': 72, 'vision': 75, 'discipline': 78,
            'description': 'Bruiser - best in A/B gaps'
        },
        {
            'name': 'Speed Back',
            'power': 70, 'agility': 92, 'vision': 80, 'discipline': 75,
            'description': 'Home run hitter - best in C gap/bounce'
        },
        {
            'name': 'Boom-or-Bust Freelancer',
            'power': 85, 'agility': 88, 'vision': 68, 'discipline': 50,
            'description': 'Always looking to bounce outside'
        },
        {
            'name': 'Backup RB',
            'power': 68, 'agility': 65, 'vision': 65, 'discipline': 70,
            'description': 'Below average everything'
        }
    ]
    
    scenarios = [
        {'name': 'vs Average Defense (75)', 'defense': 75, 'blocking': 75},
        {'name': 'vs Elite Defense (90)', 'defense': 90, 'blocking': 75},
        {'name': 'vs Poor Defense (60)', 'defense': 60, 'blocking': 75}
    ]
    
    for scenario in scenarios:
        print(f"\n{'='*80}")
        print(f"SCENARIO: {scenario['name']}")
        print(f"{'='*80}")
        
        for archetype in archetypes:
            results = []
            bounceAttempts = 0
            
            for _ in range(500):
                result = simulate_full_running_play(
                    archetype['power'], archetype['agility'],
                    archetype['vision'], archetype['discipline'],
                    scenario['blocking'], scenario['defense']
                )
                results.append(result)
                if result['selectedGap'] == 'bounce':
                    bounceAttempts += 1
            
            yards = [r['yardage'] for r in results]
            avgYards = np.mean(yards)
            successRate = sum(1 for y in yards if y >= 4) / len(yards) * 100
            bigPlayRate = sum(1 for y in yards if y >= 10) / len(yards) * 100
            stuffedRate = sum(1 for y in yards if y <= 0) / len(yards) * 100
            
            print(f"\n{archetype['name']} - {archetype['description']}")
            print(f"  Attributes: Pwr={archetype['power']}, Agi={archetype['agility']}, Vis={archetype['vision']}, Disc={archetype['discipline']}")
            print(f"  YPC: {avgYards:.2f} | Success: {successRate:4.1f}% | Big Play: {bigPlayRate:4.1f}% | Stuffed: {stuffedRate:4.1f}% | Bounce: {bounceAttempts/5:.0f}%")


def main():
    """Run all running system tests"""
    print("\n" + "="*80)
    print(" RUNNING PLAY MECHANICS TEST SUITE")
    print(" Testing vision-based gap selection and discipline-based decisions")
    print("="*80)
    
    test_gap_quality_calculation()
    test_vision_impact_on_gap_selection()
    test_discipline_impact_on_gap_selection()
    test_rb_archetypes()
    test_skill_matchups_with_yardage()
    test_rb_archetypes_with_yardage()
    
    print("\n" + "="*80)
    print(" KEY TAKEAWAYS")
    print("="*80)
    print("""
1. VISION affects gap perception accuracy:
   - Elite vision (90+): ±5 quality error - consistently sees correct gap
   - Poor vision (65-): ±25 quality error - often misreads which gap is open

2. DISCIPLINE affects gap selection:
   - Elite discipline (90+): Sticks to designed play unless it's terrible
   - Poor discipline (45-): Freelances often, bounces outside looking for home run
   
3. PHYSICAL ATTRIBUTES affect gap quality:
   - Power backs excel in A-gap (inside runs)
   - Speed backs excel in C-gap (outside runs)
   - B-gap favors balanced backs
   - Bounce outside is high risk/reward, favors agility

4. MENTAL ATTRIBUTES CREATE CONSISTENCY:
   - Smart veteran (elite mental) makes correct reads even with average physical
   - Raw talent (elite physical, poor mental) wastes talent with bad reads
   - Low discipline backs are volatile - sometimes hit home run, often waste downs

5. DESIGNED VS AUDIBLE:
   - High discipline RBs trust blocking scheme
   - Low discipline RBs freelance, can break big plays but also lose yards
   - Vision determines if they audible to *actually* better gap or just *looks* better
""")


if __name__ == '__main__':
    main()
