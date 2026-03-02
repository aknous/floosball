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
    def _applyDevBias(modifier: AttributeModifier, devBias: int) -> AttributeModifier:
        """Shift modifier range by coach development quality bias."""
        return AttributeModifier(
            min_change=modifier.min_change + devBias,
            max_change=modifier.max_change + devBias
        )

    @staticmethod
    def apply_attribute_change(current_value: int, modifier: AttributeModifier,
                                potential: int = MAX_ATTRIBUTE_VALUE) -> int:
        """Apply random attribute change within the modifier range, capped by potential."""
        change = randint(modifier.min_change, modifier.max_change)
        new_value = current_value + change

        # Positive growth is capped at potential ceiling
        if change > 0:
            new_value = min(new_value, potential)

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
                                       is_prime: bool, devBias: int = 0) -> None:
        """Develop QB-specific attributes: armStrength, accuracy, agility"""
        rules = PlayerDevelopment.PRIME_RULES if is_prime else PlayerDevelopment.DECLINING_RULES

        if x_factor_tier == XFactorTier.ELITE:
            rule_set = rules.elite_performance
        elif x_factor_tier == XFactorTier.GOOD:
            rule_set = rules.good_performance
        else:
            rule_set = rules.average_performance

        arm_level = PlayerDevelopment.get_attribute_level(attributes.armStrength)
        attributes.armStrength = PlayerDevelopment.apply_attribute_change(
            attributes.armStrength,
            PlayerDevelopment._applyDevBias(rule_set[arm_level], devBias),
            getattr(attributes, 'potentialArmStrength', MAX_ATTRIBUTE_VALUE))

        acc_level = PlayerDevelopment.get_attribute_level(attributes.accuracy)
        attributes.accuracy = PlayerDevelopment.apply_attribute_change(
            attributes.accuracy,
            PlayerDevelopment._applyDevBias(rule_set[acc_level], devBias),
            getattr(attributes, 'potentialAccuracy', MAX_ATTRIBUTE_VALUE))

        agi_level = PlayerDevelopment.get_attribute_level(attributes.agility)
        attributes.agility = PlayerDevelopment.apply_attribute_change(
            attributes.agility,
            PlayerDevelopment._applyDevBias(rule_set[agi_level], devBias),
            getattr(attributes, 'potentialAgility', MAX_ATTRIBUTE_VALUE))
    
    @staticmethod
    def develop_skill_position_attributes(attributes: Any, x_factor_tier: XFactorTier,
                                          is_prime: bool, position_type: str,
                                          devBias: int = 0) -> None:
        """Develop attributes for RB/WR/TE: speed, power/hands, agility"""
        rules = PlayerDevelopment.PRIME_RULES if is_prime else PlayerDevelopment.DECLINING_RULES

        if x_factor_tier == XFactorTier.ELITE:
            rule_set = rules.elite_performance
        elif x_factor_tier == XFactorTier.GOOD:
            rule_set = rules.good_performance
        else:
            rule_set = rules.average_performance

        speed_level = PlayerDevelopment.get_attribute_level(attributes.speed)
        attributes.speed = PlayerDevelopment.apply_attribute_change(
            attributes.speed,
            PlayerDevelopment._applyDevBias(rule_set[speed_level], devBias),
            getattr(attributes, 'potentialSpeed', MAX_ATTRIBUTE_VALUE))

        if position_type == "RB":
            power_level = PlayerDevelopment.get_attribute_level(attributes.power)
            attributes.power = PlayerDevelopment.apply_attribute_change(
                attributes.power,
                PlayerDevelopment._applyDevBias(rule_set[power_level], devBias),
                getattr(attributes, 'potentialPower', MAX_ATTRIBUTE_VALUE))
        else:  # WR/TE
            hands_level = PlayerDevelopment.get_attribute_level(attributes.hands)
            attributes.hands = PlayerDevelopment.apply_attribute_change(
                attributes.hands,
                PlayerDevelopment._applyDevBias(rule_set[hands_level], devBias),
                getattr(attributes, 'potentialHands', MAX_ATTRIBUTE_VALUE))

        agi_level = PlayerDevelopment.get_attribute_level(attributes.agility)
        attributes.agility = PlayerDevelopment.apply_attribute_change(
            attributes.agility,
            PlayerDevelopment._applyDevBias(rule_set[agi_level], devBias),
            getattr(attributes, 'potentialAgility', MAX_ATTRIBUTE_VALUE))
    
    @staticmethod
    def develop_kicker_attributes(attributes: Any, x_factor_tier: XFactorTier,
                                   is_prime: bool, devBias: int = 0) -> None:
        """Develop kicker-specific attributes: legStrength, accuracy"""
        rules = PlayerDevelopment.PRIME_RULES if is_prime else PlayerDevelopment.DECLINING_RULES

        if x_factor_tier == XFactorTier.ELITE:
            rule_set = rules.elite_performance
        elif x_factor_tier == XFactorTier.GOOD:
            rule_set = rules.good_performance
        else:
            rule_set = rules.average_performance

        leg_level = PlayerDevelopment.get_attribute_level(attributes.legStrength)
        attributes.legStrength = PlayerDevelopment.apply_attribute_change(
            attributes.legStrength,
            PlayerDevelopment._applyDevBias(rule_set[leg_level], devBias),
            getattr(attributes, 'potentialLegStrength', MAX_ATTRIBUTE_VALUE))

        acc_level = PlayerDevelopment.get_attribute_level(attributes.accuracy)
        attributes.accuracy = PlayerDevelopment.apply_attribute_change(
            attributes.accuracy,
            PlayerDevelopment._applyDevBias(rule_set[acc_level], devBias),
            getattr(attributes, 'potentialAccuracy', MAX_ATTRIBUTE_VALUE))
    
    @staticmethod
    def apply_offseason_training(player: Any, position_type: str = None,
                                 coachDevRating: int = 50) -> Dict[str, Any]:
        """
        Main method to apply offseason training to a player.
        coachDevRating (0-100): coach's playerDevelopment attribute — shifts modifier ranges.
        Returns a dictionary with development details for logging.
        """
        try:
            # -4 to +4 bias: elite coach accelerates growth/slows decline, poor coach reverses
            devBias = round((coachDevRating - 60) / 10)

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
                    player.attributes, x_factor_tier, is_prime, devBias)

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
                    player.attributes, x_factor_tier, is_prime, position_type, devBias)

            elif position_type == "K":
                original_values.update({
                    'legStrength': player.attributes.legStrength,
                    'accuracy': player.attributes.accuracy
                })
                PlayerDevelopment.develop_kicker_attributes(
                    player.attributes, x_factor_tier, is_prime, devBias)
            
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