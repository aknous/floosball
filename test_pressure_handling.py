"""
Test script to analyze pressure handling mechanics.
Simulates various player types and game pressure situations.
"""

from floosball_player import PlayerAttributes
from collections import defaultdict
import statistics

def test_pressure_outcomes(pressureHandling: int, clutchFactor: int, gamePressure: int, iterations: int = 10000):
    """Test the pressure modifier outcomes for a given player configuration."""
    
    # Create a mock attributes object
    class MockAttributes:
        def __init__(self, pressureHandling, clutchFactor):
            self.pressureHandling = pressureHandling
            self.clutchFactor = clutchFactor
            # Add other required attributes with dummy values
            self.speed = 70
            self.agility = 70
            self.power = 70
            self.hands = 70
            self.accuracy = 70
            self.xFactor = 70
            self.awareness = 70
            self.discipline = 70
            self.playMakingAbility = 70
            self.vision = 70
            self.experience = 70
            self.leadership = 70
            self.focus = 70
            self.instinct = 70
            self.creativity = 70
            self.resilience = 70
            self.blocking = 70
            self.blockingModifier = 0
        
        # Copy the getPressureModifier method
        def getPressureModifier(self, gamePressure: int) -> float:
            from random_batch import batched_randint, batched_random
            
            # Normalize game pressure to 0-1 scale
            normalizedPressure = min(100, max(0, gamePressure)) / 100.0
            
            # In low pressure situations, minimal impact
            if normalizedPressure < 0.3:
                return 0
            
            # Calculate the magnitude of potential variance based on pressure and pressureHandling
            maxVariance = abs(self.pressureHandling) * normalizedPressure
            
            # Clutch factor increases the magnitude of potential swings
            clutchMultiplier = 1 + (self.clutchFactor / 100.0)
            maxVariance *= clutchMultiplier
            
            # Roll for outcome (1-100)
            roll = batched_randint(1, 100)
            
            # Map pressureHandling to probability zones
            if self.pressureHandling >= 0:
                # Positive pressure handling: more overperform, less underperform
                overPerformChance = 15 + (self.pressureHandling * 4.5)  # 15 to 60
                noEffectChance = 70 - (self.pressureHandling * 4)       # 70 to 30
            else:
                # Negative pressure handling: less overperform, more underperform
                overPerformChance = 15 + (self.pressureHandling * 0.5)  # 15 to 10
                noEffectChance = 70 + (self.pressureHandling * 4)       # 70 to 30
            
            if roll <= overPerformChance:
                # Overperform
                return batched_random() * maxVariance
            elif roll <= overPerformChance + noEffectChance:
                # No effect
                return 0
            else:
                # Underperform
                return -(batched_random() * maxVariance)
    
    attrs = MockAttributes(pressureHandling, clutchFactor)
    
    outcomes = {
        'overperform': [],
        'no_effect': [],
        'underperform': []
    }
    
    for _ in range(iterations):
        modifier = attrs.getPressureModifier(gamePressure)
        
        if modifier > 0:
            outcomes['overperform'].append(modifier)
        elif modifier == 0:
            outcomes['no_effect'].append(modifier)
        else:
            outcomes['underperform'].append(modifier)
    
    return outcomes

def print_test_results(player_type: str, pressureHandling: int, clutchFactor: int, gamePressure: int, iterations: int = 10000):
    """Print formatted test results for a player configuration."""
    
    print(f"\n{'='*70}")
    print(f"{player_type}")
    print(f"pressureHandling: {pressureHandling:+d} | clutchFactor: {clutchFactor} | gamePressure: {gamePressure}")
    print(f"{'='*70}")
    
    outcomes = test_pressure_outcomes(pressureHandling, clutchFactor, gamePressure, iterations)
    
    overperform_count = len(outcomes['overperform'])
    no_effect_count = len(outcomes['no_effect'])
    underperform_count = len(outcomes['underperform'])
    
    overperform_pct = (overperform_count / iterations) * 100
    no_effect_pct = (no_effect_count / iterations) * 100
    underperform_pct = (underperform_count / iterations) * 100
    
    print(f"\nOutcome Distribution (n={iterations}):")
    print(f"  Overperform:  {overperform_count:5d} ({overperform_pct:5.1f}%)")
    print(f"  No Effect:    {no_effect_count:5d} ({no_effect_pct:5.1f}%)")
    print(f"  Underperform: {underperform_count:5d} ({underperform_pct:5.1f}%)")
    
    if outcomes['overperform']:
        avg_over = statistics.mean(outcomes['overperform'])
        max_over = max(outcomes['overperform'])
        print(f"\nOverperform modifiers: avg={avg_over:+.2f}, max={max_over:+.2f}")
    
    if outcomes['underperform']:
        avg_under = statistics.mean(outcomes['underperform'])
        min_under = min(outcomes['underperform'])
        print(f"Underperform modifiers: avg={avg_under:+.2f}, min={min_under:+.2f}")

if __name__ == "__main__":
    print("\n" + "="*70)
    print("PRESSURE HANDLING SYSTEM TEST")
    print("="*70)
    
    # Test various player archetypes
    print("\n" + "#"*70)
    print("# TEST 1: HIGH PRESSURE SITUATIONS (gamePressure = 80)")
    print("#"*70)
    
    print_test_results("Elite Clutch Player", pressureHandling=10, clutchFactor=90, gamePressure=80)
    print_test_results("Good Clutch Player", pressureHandling=6, clutchFactor=70, gamePressure=80)
    print_test_results("Average Player", pressureHandling=0, clutchFactor=60, gamePressure=80)
    print_test_results("Pressure-Sensitive Player", pressureHandling=-6, clutchFactor=50, gamePressure=80)
    print_test_results("Major Choker", pressureHandling=-10, clutchFactor=40, gamePressure=80)
    
    print("\n" + "#"*70)
    print("# TEST 2: MODERATE PRESSURE SITUATIONS (gamePressure = 50)")
    print("#"*70)
    
    print_test_results("Elite Clutch Player", pressureHandling=10, clutchFactor=90, gamePressure=50)
    print_test_results("Average Player", pressureHandling=0, clutchFactor=60, gamePressure=50)
    print_test_results("Major Choker", pressureHandling=-10, clutchFactor=40, gamePressure=50)
    
    print("\n" + "#"*70)
    print("# TEST 3: LOW PRESSURE SITUATIONS (gamePressure = 20)")
    print("#"*70)
    
    print_test_results("Elite Clutch Player", pressureHandling=10, clutchFactor=90, gamePressure=20)
    print_test_results("Major Choker", pressureHandling=-10, clutchFactor=40, gamePressure=20)
    
    print("\n" + "#"*70)
    print("# TEST 4: EXTREME PRESSURE (gamePressure = 100)")
    print("#"*70)
    
    print_test_results("Elite Clutch Player", pressureHandling=10, clutchFactor=90, gamePressure=100)
    print_test_results("Major Choker", pressureHandling=-10, clutchFactor=40, gamePressure=100)
    
    print("\n" + "="*70)
    print("TEST COMPLETE")
    print("="*70 + "\n")
