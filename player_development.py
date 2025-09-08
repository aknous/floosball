"""Player development service for offseason training logic"""

from random import randint
from typing import Dict, Any, Tuple
from dataclasses import dataclass
from enum import Enum
from constants import MIN_ATTRIBUTE_VALUE, MAX_ATTRIBUTE_VALUE
from logger_config import get_logger

logger = get_logger("floosball.development")

class XFactorTier(Enum):
    ELITE = "elite"    # > 90
    GOOD = "good"      # 75-90  
    AVERAGE = "average" # <= 75

class AttributeLevel(Enum):
    HIGH = "high"      # >= 95
    LOW = "low"        # <= 70
    MEDIUM = "medium"  # 71-94

@dataclass
class AttributeModifier:
    """Defines the range of attribute change for different conditions"""
    min_change: int
    max_change: int

@dataclass  
class DevelopmentRules:
    """Rules for attribute development based on performance and potential"""
    elite_performance: Dict[AttributeLevel, AttributeModifier]
    good_performance: Dict[AttributeLevel, AttributeModifier]
    average_performance: Dict[AttributeLevel, AttributeModifier]
    declining_performance: Dict[AttributeLevel, AttributeModifier]

class PlayerDevelopment:
    """Service class for handling player development during offseason"""
    
    # Development rules for players in their prime (before longevity threshold)
    PRIME_RULES = DevelopmentRules(
        elite_performance={
            AttributeLevel.HIGH: AttributeModifier(0, 2),
            AttributeLevel.LOW: AttributeModifier(0, 10), 
            AttributeLevel.MEDIUM: AttributeModifier(0, 5)
        },
        good_performance={
            AttributeLevel.HIGH: AttributeModifier(-1, 2),
            AttributeLevel.LOW: AttributeModifier(0, 7),
            AttributeLevel.MEDIUM: AttributeModifier(-2, 3)
        },
        average_performance={
            AttributeLevel.HIGH: AttributeModifier(-5, 1),
            AttributeLevel.LOW: AttributeModifier(0, 5),
            AttributeLevel.MEDIUM: AttributeModifier(-5, 5)
        },
        declining_performance={
            AttributeLevel.HIGH: AttributeModifier(-3, 0),
            AttributeLevel.LOW: AttributeModifier(-1, 5),
            AttributeLevel.MEDIUM: AttributeModifier(-3, 3)
        }
    )
    
    # Development rules for players past their prime (after longevity threshold)  
    DECLINING_RULES = DevelopmentRules(
        elite_performance={
            AttributeLevel.HIGH: AttributeModifier(-3, 0),
            AttributeLevel.LOW: AttributeModifier(-1, 5),
            AttributeLevel.MEDIUM: AttributeModifier(-3, 3)
        },
        good_performance={
            AttributeLevel.HIGH: AttributeModifier(-5, 0), 
            AttributeLevel.LOW: AttributeModifier(-2, 3),
            AttributeLevel.MEDIUM: AttributeModifier(-5, 2)
        },
        average_performance={
            AttributeLevel.HIGH: AttributeModifier(-8, -2),
            AttributeLevel.LOW: AttributeModifier(-3, 2),
            AttributeLevel.MEDIUM: AttributeModifier(-8, 1)
        },
        declining_performance={
            AttributeLevel.HIGH: AttributeModifier(-10, -5),
            AttributeLevel.LOW: AttributeModifier(-5, 0),
            AttributeLevel.MEDIUM: AttributeModifier(-10, -2)
        }
    )
    
    @staticmethod
    def get_x_factor_tier(x_factor: int) -> XFactorTier:
        """Determine X-Factor performance tier"""
        if x_factor > 90:
            return XFactorTier.ELITE
        elif x_factor > 75:
            return XFactorTier.GOOD
        else:
            return XFactorTier.AVERAGE
    
    @staticmethod
    def get_attribute_level(attribute_value: int) -> AttributeLevel:
        """Determine attribute level category"""
        if attribute_value >= 95:
            return AttributeLevel.HIGH
        elif attribute_value <= 70:
            return AttributeLevel.LOW
        else:
            return AttributeLevel.MEDIUM
    
    @staticmethod
    def apply_attribute_change(current_value: int, modifier: AttributeModifier) -> int:
        """Apply random attribute change within the modifier range"""
        change = randint(modifier.min_change, modifier.max_change)
        new_value = current_value + change
        
        # Ensure value stays within bounds
        return max(MIN_ATTRIBUTE_VALUE, min(MAX_ATTRIBUTE_VALUE, new_value))
    
    @staticmethod
    def update_intangible_attributes(attributes: Any) -> None:
        """Update attitude and discipline with random changes"""
        # Attitude change
        attitude_change = randint(-5, 5)
        attributes.attitude = max(0, min(100, attributes.attitude + attitude_change))
        
        # Discipline change  
        discipline_change = randint(-5, 5)
        attributes.discipline = max(0, min(100, attributes.discipline + discipline_change))
        
        # Recalculate intangibles
        if hasattr(attributes, 'calculateIntangibles'):
            attributes.calculateIntangibles()
    
    @staticmethod
    def develop_quarterback_attributes(attributes: Any, x_factor_tier: XFactorTier, 
                                     is_prime: bool) -> None:
        """Develop QB-specific attributes: armStrength, accuracy, agility"""
        rules = PlayerDevelopment.PRIME_RULES if is_prime else PlayerDevelopment.DECLINING_RULES
        
        # Get the appropriate rule set based on X-Factor tier
        if x_factor_tier == XFactorTier.ELITE:
            rule_set = rules.elite_performance
        elif x_factor_tier == XFactorTier.GOOD:
            rule_set = rules.good_performance
        else:
            rule_set = rules.average_performance
        
        # Update each attribute
        arm_level = PlayerDevelopment.get_attribute_level(attributes.armStrength)
        attributes.armStrength = PlayerDevelopment.apply_attribute_change(
            attributes.armStrength, rule_set[arm_level])
        
        acc_level = PlayerDevelopment.get_attribute_level(attributes.accuracy)
        attributes.accuracy = PlayerDevelopment.apply_attribute_change(
            attributes.accuracy, rule_set[acc_level])
        
        agi_level = PlayerDevelopment.get_attribute_level(attributes.agility)  
        attributes.agility = PlayerDevelopment.apply_attribute_change(
            attributes.agility, rule_set[agi_level])
    
    @staticmethod
    def develop_skill_position_attributes(attributes: Any, x_factor_tier: XFactorTier,
                                        is_prime: bool, position_type: str) -> None:
        """Develop attributes for RB/WR/TE: speed, power/hands, agility"""
        rules = PlayerDevelopment.PRIME_RULES if is_prime else PlayerDevelopment.DECLINING_RULES
        
        # Get the appropriate rule set based on X-Factor tier
        if x_factor_tier == XFactorTier.ELITE:
            rule_set = rules.elite_performance
        elif x_factor_tier == XFactorTier.GOOD:
            rule_set = rules.good_performance
        else:
            rule_set = rules.average_performance
        
        # Speed (common to all skill positions)
        speed_level = PlayerDevelopment.get_attribute_level(attributes.speed)
        attributes.speed = PlayerDevelopment.apply_attribute_change(
            attributes.speed, rule_set[speed_level])
        
        # Position-specific second attribute
        if position_type == "RB":
            power_level = PlayerDevelopment.get_attribute_level(attributes.power)
            attributes.power = PlayerDevelopment.apply_attribute_change(
                attributes.power, rule_set[power_level])
        else:  # WR/TE
            hands_level = PlayerDevelopment.get_attribute_level(attributes.hands)
            attributes.hands = PlayerDevelopment.apply_attribute_change(
                attributes.hands, rule_set[hands_level])
        
        # Agility (common to all)
        agi_level = PlayerDevelopment.get_attribute_level(attributes.agility)
        attributes.agility = PlayerDevelopment.apply_attribute_change(
            attributes.agility, rule_set[agi_level])
    
    @staticmethod
    def develop_kicker_attributes(attributes: Any, x_factor_tier: XFactorTier,
                                is_prime: bool) -> None:
        """Develop kicker-specific attributes: legStrength, accuracy"""
        rules = PlayerDevelopment.PRIME_RULES if is_prime else PlayerDevelopment.DECLINING_RULES
        
        # Get the appropriate rule set based on X-Factor tier
        if x_factor_tier == XFactorTier.ELITE:
            rule_set = rules.elite_performance
        elif x_factor_tier == XFactorTier.GOOD:
            rule_set = rules.good_performance
        else:
            rule_set = rules.average_performance
        
        # Update leg strength
        leg_level = PlayerDevelopment.get_attribute_level(attributes.legStrength)
        attributes.legStrength = PlayerDevelopment.apply_attribute_change(
            attributes.legStrength, rule_set[leg_level])
        
        # Update accuracy
        acc_level = PlayerDevelopment.get_attribute_level(attributes.accuracy)
        attributes.accuracy = PlayerDevelopment.apply_attribute_change(
            attributes.accuracy, rule_set[acc_level])
    
    @staticmethod
    def apply_offseason_training(player: Any, position_type: str = None) -> Dict[str, Any]:
        """
        Main method to apply offseason training to a player
        Returns a dictionary with development details for logging
        """
        try:
            # Store original values for comparison
            original_values = {
                'attitude': getattr(player.attributes, 'attitude', 0),
                'discipline': getattr(player.attributes, 'discipline', 0)
            }
            
            # Update intangible attributes  
            PlayerDevelopment.update_intangible_attributes(player.attributes)
            
            # Determine if player is in prime or declining phase
            is_prime = player.seasonsPlayed <= player.attributes.longevity
            x_factor_tier = PlayerDevelopment.get_x_factor_tier(player.attributes.xFactor)
            
            # Apply position-specific development
            if position_type == "QB":
                original_values.update({
                    'armStrength': player.attributes.armStrength,
                    'accuracy': player.attributes.accuracy, 
                    'agility': player.attributes.agility
                })
                PlayerDevelopment.develop_quarterback_attributes(
                    player.attributes, x_factor_tier, is_prime)
                    
            elif position_type in ["RB", "WR", "TE"]:
                original_values.update({
                    'speed': player.attributes.speed,
                    'agility': player.attributes.agility
                })
                if position_type == "RB":
                    original_values['power'] = player.attributes.power
                else:
                    original_values['hands'] = player.attributes.hands
                    
                PlayerDevelopment.develop_skill_position_attributes(
                    player.attributes, x_factor_tier, is_prime, position_type)
                    
            elif position_type == "K":
                original_values.update({
                    'legStrength': player.attributes.legStrength,
                    'accuracy': player.attributes.accuracy
                })
                PlayerDevelopment.develop_kicker_attributes(
                    player.attributes, x_factor_tier, is_prime)
            
            # Calculate changes for logging
            changes = {}
            for attr, original in original_values.items():
                new_value = getattr(player.attributes, attr, original)
                change = new_value - original
                if change != 0:
                    changes[attr] = {'from': original, 'to': new_value, 'change': change}
            
            logger.info(f"Player {player.name} development: {changes}")
            
            return {
                'player_name': getattr(player, 'name', 'Unknown'),
                'position': position_type,
                'is_prime': is_prime,
                'x_factor_tier': x_factor_tier.value,
                'changes': changes
            }
            
        except Exception as e:
            logger.error(f"Error in offseason training for player {getattr(player, 'name', 'Unknown')}: {e}")
            return {
                'player_name': getattr(player, 'name', 'Unknown'),
                'error': str(e)
            }