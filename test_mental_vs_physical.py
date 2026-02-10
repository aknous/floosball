"""
Test suite comparing physical vs mental attributes in passing performance.
Shows how mental attributes (vision, discipline, pressureHandling) can make or break 
physically talented players, and how elite mental attributes can elevate average physical talent.
"""

import numpy as np
from enum import Enum


class PassType(Enum):
    short = 1
    medium = 2
    long = 3
    hailMary = 4
    throwAway = 5


def batched_randint(min_val, max_val):
    """Simple randint replacement for testing"""
    return np.random.randint(min_val, max_val + 1)


class PassingSimulator:
    """Simulate complete passing plays with physical and mental attributes"""
    
    @staticmethod
    def simulate_pass(qb_accuracy, qb_vision, qb_discipline, qb_pressure_mod,
                     receiver_hands, receiver_route_running,
                     defense_coverage, defense_rush, game_pressure,
                     pass_type=PassType.medium):
        """
        Simulate a complete passing play and return outcome.
        Returns: dict with outcome, interception, completion, etc.
        """
        result = {
            'outcome': None,  # 'completion', 'incompletion', 'interception', 'throwaway', 'sack'
            'yards': 0,
            'isCompletion': False,
            'isInterception': False,
            'isThrowaway': False,
            'isSack': False,
            'targetSelected': None,
            'perceivedOpenness': 0,
            'actualOpenness': 0
        }
        
        # SACK CHECK
        qbMobility = 70  # Baseline
        blockingModifier = 10  # Baseline
        qbProtection = qbMobility + blockingModifier
        rushDifferential = defense_rush - qbProtection
        rushDifferential += 5  # 5-step dropback
        
        baseSackRate = 8.0
        steepness = 0.15
        sackProbability = (baseSackRate * 2) / (1 + np.exp(-steepness * rushDifferential))
        sackProbability = max(1, min(35, sackProbability))
        
        if batched_randint(1, 100) <= sackProbability:
            result['outcome'] = 'sack'
            result['isSack'] = True
            result['yards'] = -batched_randint(3, 7)
            return result
        
        # STAGE 1: Calculate receiver openness
        skillDifferential = receiver_route_running - defense_coverage
        meanOpenness = 50 + (skillDifferential / 2)
        meanOpenness = max(10, min(90, meanOpenness))
        stdDev = max(10, 25 - (receiver_route_running / 10))
        
        actualOpenness = np.random.normal(meanOpenness, stdDev)
        actualOpenness = max(0, min(100, actualOpenness))
        result['actualOpenness'] = actualOpenness
        
        # STAGE 2: QB perceives openness (vision error)
        if qb_vision >= 90:
            visionErrorRange = 5
        elif qb_vision >= 70:
            visionErrorRange = 15
        else:
            visionErrorRange = 25
        
        visionError = batched_randint(-visionErrorRange, visionErrorRange)
        perceivedOpenness = max(0, min(100, actualOpenness + visionError))
        result['perceivedOpenness'] = perceivedOpenness
        
        # STAGE 2: Discipline check - will QB throw?
        willThrow = False
        if qb_discipline >= 90:
            if perceivedOpenness >= 60 or batched_randint(1, 100) <= 20:
                willThrow = True
        elif qb_discipline >= 75:
            if perceivedOpenness >= 40 or batched_randint(1, 100) <= 30:
                willThrow = True
        elif qb_discipline >= 60:
            if perceivedOpenness >= 25 or batched_randint(1, 100) <= 50:
                willThrow = True
        else:
            if batched_randint(1, 100) <= 70:
                willThrow = True
        
        # Throw away check
        if not willThrow:
            if qb_discipline >= 80 or batched_randint(1, 100) <= qb_discipline:
                result['outcome'] = 'throwaway'
                result['isThrowaway'] = True
                return result
            else:
                willThrow = True  # Force it
        
        # STAGE 3: Calculate throw quality
        baseAccuracy = (qb_accuracy + 70) / 2 + qb_pressure_mod  # xFactor baseline 70
        
        passTypeDifficulty = {
            PassType.short: 1.0,
            PassType.medium: 0.85,
            PassType.long: 0.7,
        }
        difficultyMod = passTypeDifficulty.get(pass_type, 0.85)
        
        # Pressure impact
        qbPressureResistance = (qb_accuracy * 0.7) + blockingModifier
        pressureDifferential = defense_rush - qbPressureResistance
        maxDegradation = 0.4
        steepness = 0.12
        degradationAmount = maxDegradation * (1 / (1 + np.exp(-steepness * pressureDifferential)))
        pressureDegradation = 1.0 - degradationAmount
        pressureDegradation = max(0.6, min(1.0, pressureDegradation))
        
        throwQuality = baseAccuracy * difficultyMod * pressureDegradation
        throwQuality += batched_randint(-10, 10)
        throwQuality = max(5, min(100, throwQuality))
        
        # STAGE 4: Catch probability
        adjustedHands = receiver_hands + 0  # No pressure mod on receiver for simplicity
        
        if throwQuality >= 70:
            baseCatchProb = adjustedHands * 0.9
        elif throwQuality >= 50:
            baseCatchProb = (adjustedHands * 0.6) + (actualOpenness * 0.3)
        else:
            baseCatchProb = (adjustedHands * 0.4) + (actualOpenness * 0.4)
        
        defenseFactor = max(0, (100 - actualOpenness) / 100) * (defense_coverage / 100)
        catchProb = baseCatchProb * (1 - defenseFactor * 0.5)
        
        intProb = 0
        if throwQuality < 50 and actualOpenness < 50:
            intProb = ((50 - throwQuality) / 10) * ((50 - actualOpenness) / 50) * (defense_coverage / 100) * 12
        
        dropProb = max(0, (100 - baseCatchProb) * (defense_coverage / 200))
        
        catchProb = min(95, max(5, catchProb))
        intProb = min(25, max(0, intProb))
        dropProb = min(30, max(0, dropProb))
        
        # Roll for outcome
        outcomeRoll = batched_randint(1, 100)
        
        if outcomeRoll <= intProb:
            result['outcome'] = 'interception'
            result['isInterception'] = True
            result['yards'] = batched_randint(-5, 10)
        elif outcomeRoll <= (intProb + catchProb):
            # COMPLETION
            result['outcome'] = 'completion'
            result['isCompletion'] = True
            
            # Calculate yards
            passTypeParams = {
                PassType.short: {'mean': 3, 'stdDev': 1.5},
                PassType.medium: {'mean': 8, 'stdDev': 2.5},
                PassType.long: {'mean': 15, 'stdDev': 4},
            }
            params = passTypeParams.get(pass_type, {'mean': 8, 'stdDev': 2.5})
            qualityFactor = throwQuality / 80
            adjustedMean = params['mean'] * qualityFactor
            airYards = int(np.random.normal(adjustedMean, params['stdDev']))
            airYards = max(0, airYards)
            
            # YAC (simplified)
            yac = batched_randint(0, 5)
            result['yards'] = airYards + yac
        else:
            result['outcome'] = 'incompletion'
        
        return result


def test_physical_vs_mental():
    """Test physical vs mental attribute combinations"""
    print("\n" + "="*80)
    print("PHYSICAL VS MENTAL ATTRIBUTES TEST")
    print("Testing how mental attributes can elevate or diminish physical talent")
    print("="*80)
    
    iterations = 1000
    
    # Define QB archetypes
    qb_profiles = [
        {
            'name': 'Elite Physical + Elite Mental',
            'accuracy': 90,
            'vision': 90,
            'discipline': 90,
            'pressure_mod': 5,  # Elite pressure handling
            'description': 'Perfect QB - high accuracy, great decision making'
        },
        {
            'name': 'Elite Physical + Poor Mental',
            'accuracy': 90,
            'vision': 55,
            'discipline': 55,
            'pressure_mod': -5,  # Poor pressure handling
            'description': 'Talented but poor decisions - "gunslinger"'
        },
        {
            'name': 'Poor Physical + Elite Mental',
            'accuracy': 60,
            'vision': 90,
            'discipline': 90,
            'pressure_mod': 5,  # Elite pressure handling
            'description': 'Game manager - limited arm, excellent decisions'
        },
        {
            'name': 'Poor Physical + Poor Mental',
            'accuracy': 60,
            'vision': 55,
            'discipline': 55,
            'pressure_mod': -5,  # Poor pressure handling
            'description': 'Backup QB - struggles physically and mentally'
        },
        {
            'name': 'Elite Physical + Average Mental',
            'accuracy': 90,
            'vision': 70,
            'discipline': 70,
            'pressure_mod': 0,
            'description': 'Raw talent with developing mental game'
        },
        {
            'name': 'Average Physical + Elite Mental',
            'accuracy': 75,
            'vision': 90,
            'discipline': 90,
            'pressure_mod': 5,
            'description': 'Smart veteran - maximizes limited physical tools'
        }
    ]
    
    # Test scenarios
    scenarios = [
        {
            'name': 'Against Average Defense (Low Pressure)',
            'defense_coverage': 70,
            'defense_rush': 70,
            'game_pressure': 30,
            'receiver_hands': 75,
            'receiver_route_running': 75
        },
        {
            'name': 'Against Elite Defense (High Pressure)',
            'defense_coverage': 90,
            'defense_rush': 90,
            'game_pressure': 80,
            'receiver_hands': 75,
            'receiver_route_running': 75
        },
        {
            'name': 'Against Poor Defense (Low Pressure)',
            'defense_coverage': 60,
            'defense_rush': 60,
            'game_pressure': 20,
            'receiver_hands': 75,
            'receiver_route_running': 75
        }
    ]
    
    for scenario in scenarios:
        print("\n" + "="*80)
        print(f"SCENARIO: {scenario['name']}")
        print(f"Defense Coverage: {scenario['defense_coverage']}, Pass Rush: {scenario['defense_rush']}")
        print("="*80)
        
        for qb in qb_profiles:
            stats = {
                'attempts': 0,
                'completions': 0,
                'yards': 0,
                'interceptions': 0,
                'sacks': 0,
                'throwaways': 0,
                'perception_errors': []  # Track how wrong their perception was
            }
            
            for _ in range(iterations):
                result = PassingSimulator.simulate_pass(
                    qb_accuracy=qb['accuracy'],
                    qb_vision=qb['vision'],
                    qb_discipline=qb['discipline'],
                    qb_pressure_mod=qb['pressure_mod'],
                    receiver_hands=scenario['receiver_hands'],
                    receiver_route_running=scenario['receiver_route_running'],
                    defense_coverage=scenario['defense_coverage'],
                    defense_rush=scenario['defense_rush'],
                    game_pressure=scenario['game_pressure'],
                    pass_type=PassType.medium
                )
                
                if result['isSack']:
                    stats['sacks'] += 1
                elif result['isThrowaway']:
                    stats['throwaways'] += 1
                else:
                    stats['attempts'] += 1
                    if result['isCompletion']:
                        stats['completions'] += 1
                        stats['yards'] += result['yards']
                    elif result['isInterception']:
                        stats['interceptions'] += 1
                    
                    # Track perception error
                    perception_error = abs(result['perceivedOpenness'] - result['actualOpenness'])
                    stats['perception_errors'].append(perception_error)
            
            # Calculate stats
            comp_pct = (stats['completions'] / stats['attempts'] * 100) if stats['attempts'] > 0 else 0
            int_pct = (stats['interceptions'] / stats['attempts'] * 100) if stats['attempts'] > 0 else 0
            yards_per_att = (stats['yards'] / stats['attempts']) if stats['attempts'] > 0 else 0
            avg_perception_error = np.mean(stats['perception_errors']) if stats['perception_errors'] else 0
            sack_rate = (stats['sacks'] / iterations * 100)
            throwaway_rate = (stats['throwaways'] / iterations * 100)
            
            print(f"\n{qb['name']}")
            print(f"  {qb['description']}")
            print(f"  Physical: Accuracy {qb['accuracy']:2d} | Mental: Vision {qb['vision']:2d}, Discipline {qb['discipline']:2d}, Pressure {qb['pressure_mod']:+2d}")
            print(f"  ----------------------------------------")
            print(f"  Completion %:      {comp_pct:5.1f}%")
            print(f"  Interception %:    {int_pct:5.1f}%")
            print(f"  Yards/Attempt:     {yards_per_att:5.1f}")
            print(f"  Sack Rate:         {sack_rate:5.1f}%")
            print(f"  Throwaway Rate:    {throwaway_rate:5.1f}%")
            print(f"  Avg Vision Error:  {avg_perception_error:5.1f} openness points")
    
    # Summary comparison
    print("\n" + "="*80)
    print("KEY TAKEAWAYS")
    print("="*80)
    print("""
1. Elite Physical + Poor Mental: High completion % BUT also high INT%
   - Can make every throw but makes bad decisions
   - Vision errors lead to throws into coverage
   - Poor pressure handling increases mistakes under duress

2. Poor Physical + Elite Mental: Lower completion % BUT very low INT%
   - Can't make all throws but rarely forces bad decisions
   - Accurate vision helps find truly open receivers
   - Elite pressure handling maintains composure

3. Mental attributes create 'floor' and 'ceiling':
   - Poor mental = low floor (can implode with turnovers)
   - Elite mental = high floor (stays consistent, avoids mistakes)
   - Physical talent determines ceiling (how good you CAN be)
   - Mental talent determines floor (how bad you WON'T be)
    """)


if __name__ == "__main__":
    test_physical_vs_mental()
