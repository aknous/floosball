"""Attribute validation utility for player attributes with min/max bounds"""

from typing import Any, Dict, List, Optional, Union
from constants import MIN_ATTRIBUTE_VALUE, MAX_ATTRIBUTE_VALUE
from exceptions import ValidationError
from logger_config import get_logger

logger = get_logger("floosball.attributes")

class AttributeValidator:
    """Utility class for validating and capping player attributes"""
    
    # Define attribute bounds for different categories
    ATTRIBUTE_BOUNDS = {
        # Physical attributes
        'speed': (MIN_ATTRIBUTE_VALUE, MAX_ATTRIBUTE_VALUE),
        'power': (MIN_ATTRIBUTE_VALUE, MAX_ATTRIBUTE_VALUE),
        'agility': (MIN_ATTRIBUTE_VALUE, MAX_ATTRIBUTE_VALUE),
        'armStrength': (MIN_ATTRIBUTE_VALUE, MAX_ATTRIBUTE_VALUE),
        'legStrength': (MIN_ATTRIBUTE_VALUE, MAX_ATTRIBUTE_VALUE),
        
        # Skill attributes
        'accuracy': (MIN_ATTRIBUTE_VALUE, MAX_ATTRIBUTE_VALUE),
        'hands': (MIN_ATTRIBUTE_VALUE, MAX_ATTRIBUTE_VALUE),
        
        # Mental attributes  
        'playMakingAbility': (MIN_ATTRIBUTE_VALUE, MAX_ATTRIBUTE_VALUE),
        'xFactor': (MIN_ATTRIBUTE_VALUE, MAX_ATTRIBUTE_VALUE),
        'skillRating': (MIN_ATTRIBUTE_VALUE, MAX_ATTRIBUTE_VALUE),
        
        # Special attributes with different bounds
        'attitude': (0, 100),
        'discipline': (0, 100),
        'longevity': (1, 20),  # Career length in years
        
        # Rating attributes
        'playerRating': (MIN_ATTRIBUTE_VALUE, MAX_ATTRIBUTE_VALUE),
        'overallRating': (MIN_ATTRIBUTE_VALUE, MAX_ATTRIBUTE_VALUE),
        'seasonPerformanceRating': (MIN_ATTRIBUTE_VALUE, MAX_ATTRIBUTE_VALUE),
        
        # Potential attributes
        'potentialSpeed': (MIN_ATTRIBUTE_VALUE, MAX_ATTRIBUTE_VALUE),
        'potentialPower': (MIN_ATTRIBUTE_VALUE, MAX_ATTRIBUTE_VALUE),
        'potentialAgility': (MIN_ATTRIBUTE_VALUE, MAX_ATTRIBUTE_VALUE),
        'potentialArmStrength': (MIN_ATTRIBUTE_VALUE, MAX_ATTRIBUTE_VALUE),
        'potentialLegStrength': (MIN_ATTRIBUTE_VALUE, MAX_ATTRIBUTE_VALUE),
        'potentialAccuracy': (MIN_ATTRIBUTE_VALUE, MAX_ATTRIBUTE_VALUE),
        'potentialHands': (MIN_ATTRIBUTE_VALUE, MAX_ATTRIBUTE_VALUE),
    }
    
    # Position-specific attribute requirements
    POSITION_ATTRIBUTES = {
        'QB': ['armStrength', 'accuracy', 'agility', 'playMakingAbility'],
        'RB': ['speed', 'power', 'agility'],
        'WR': ['speed', 'hands', 'agility'],
        'TE': ['hands', 'power', 'agility'],
        'K': ['legStrength', 'accuracy']
    }
    
    @staticmethod
    def validate_attribute_value(value: Union[int, float], attribute_name: str, 
                                min_val: Optional[int] = None, max_val: Optional[int] = None) -> int:
        """
        Validate and cap a single attribute value
        
        Args:
            value: The attribute value to validate
            attribute_name: Name of the attribute for error messages
            min_val: Override minimum value (uses defaults if None)
            max_val: Override maximum value (uses defaults if None)
            
        Returns:
            Validated and capped integer value
            
        Raises:
            ValidationError: If value cannot be converted to int
        """
        try:
            value = int(value)
        except (ValueError, TypeError):
            raise ValidationError(f"Attribute '{attribute_name}' must be a number, got {type(value).__name__}")
        
        # Get bounds
        if attribute_name in AttributeValidator.ATTRIBUTE_BOUNDS:
            default_min, default_max = AttributeValidator.ATTRIBUTE_BOUNDS[attribute_name]
            min_val = min_val if min_val is not None else default_min
            max_val = max_val if max_val is not None else default_max
        else:
            # Use defaults if attribute not in bounds dict
            min_val = min_val if min_val is not None else MIN_ATTRIBUTE_VALUE
            max_val = max_val if max_val is not None else MAX_ATTRIBUTE_VALUE
        
        # Cap the value
        capped_value = max(min_val, min(max_val, value))
        
        # Log if value was capped
        if capped_value != value:
            logger.debug(f"Capped attribute '{attribute_name}' from {value} to {capped_value} (bounds: {min_val}-{max_val})")
        
        return capped_value
    
    @staticmethod
    def cap_attribute(value: Union[int, float], min_val: int, max_val: int) -> int:
        """
        Simple attribute capping function (replaces repetitive min/max logic)
        
        Args:
            value: Value to cap
            min_val: Minimum allowed value
            max_val: Maximum allowed value
            
        Returns:
            Capped integer value
        """
        try:
            value = int(value)
            return max(min_val, min(max_val, value))
        except (ValueError, TypeError):
            logger.warning(f"Could not cap non-numeric value: {value}, returning minimum")
            return min_val
    
    @staticmethod
    def validate_player_attributes(attributes: Any, position: str = None) -> Dict[str, Any]:
        """
        Validate all attributes on a player attributes object
        
        Args:
            attributes: Player attributes object
            position: Player position for position-specific validation
            
        Returns:
            Dictionary with validation results and any corrections made
        """
        validation_results = {
            'corrections_made': [],
            'warnings': [],
            'position': position
        }
        
        # Get all attributes from the object
        attribute_dict = attributes.__dict__ if hasattr(attributes, '__dict__') else {}
        
        for attr_name, value in attribute_dict.items():
            if attr_name.startswith('_'):  # Skip private attributes
                continue
                
            try:
                if attr_name in AttributeValidator.ATTRIBUTE_BOUNDS:
                    original_value = value
                    corrected_value = AttributeValidator.validate_attribute_value(value, attr_name)
                    
                    # Update the attribute if it was corrected
                    if corrected_value != original_value:
                        setattr(attributes, attr_name, corrected_value)
                        validation_results['corrections_made'].append({
                            'attribute': attr_name,
                            'original': original_value,
                            'corrected': corrected_value
                        })
                        
            except ValidationError as e:
                validation_results['warnings'].append(f"Validation error for {attr_name}: {e}")
            except Exception as e:
                validation_results['warnings'].append(f"Unexpected error validating {attr_name}: {e}")
        
        # Position-specific validation
        if position and position in AttributeValidator.POSITION_ATTRIBUTES:
            required_attributes = AttributeValidator.POSITION_ATTRIBUTES[position]
            for required_attr in required_attributes:
                if not hasattr(attributes, required_attr):
                    validation_results['warnings'].append(f"Missing required attribute '{required_attr}' for position {position}")
                elif getattr(attributes, required_attr) is None:
                    validation_results['warnings'].append(f"Required attribute '{required_attr}' is None for position {position}")
        
        # Log results
        if validation_results['corrections_made']:
            logger.info(f"Made {len(validation_results['corrections_made'])} attribute corrections")
        if validation_results['warnings']:
            logger.warning(f"Attribute validation warnings: {validation_results['warnings']}")
        
        return validation_results
    
    @staticmethod
    def ensure_attributes_within_bounds(attributes: Any) -> None:
        """
        Ensure all attributes are within their proper bounds (in-place modification)
        Replaces the repetitive if/else capping logic throughout the codebase
        
        Args:
            attributes: Player attributes object to validate
        """
        if not hasattr(attributes, '__dict__'):
            return
        
        for attr_name in dir(attributes):
            if attr_name.startswith('_'):
                continue
                
            try:
                value = getattr(attributes, attr_name)
                if isinstance(value, (int, float)) and attr_name in AttributeValidator.ATTRIBUTE_BOUNDS:
                    min_val, max_val = AttributeValidator.ATTRIBUTE_BOUNDS[attr_name]
                    capped_value = AttributeValidator.cap_attribute(value, min_val, max_val)
                    setattr(attributes, attr_name, capped_value)
            except Exception as e:
                logger.debug(f"Could not validate attribute {attr_name}: {e}")
    
    @staticmethod
    def validate_attribute_progression(current_attrs: Any, potential_attrs: Any) -> List[str]:
        """
        Validate that potential attributes are reasonable compared to current attributes
        
        Args:
            current_attrs: Current attribute values
            potential_attrs: Potential attribute values
            
        Returns:
            List of warning messages if any issues found
        """
        warnings = []
        
        potential_mappings = {
            'speed': 'potentialSpeed',
            'power': 'potentialPower', 
            'agility': 'potentialAgility',
            'armStrength': 'potentialArmStrength',
            'legStrength': 'potentialLegStrength',
            'accuracy': 'potentialAccuracy',
            'hands': 'potentialHands'
        }
        
        for current_attr, potential_attr in potential_mappings.items():
            try:
                if hasattr(current_attrs, current_attr) and hasattr(potential_attrs, potential_attr):
                    current_val = getattr(current_attrs, current_attr)
                    potential_val = getattr(potential_attrs, potential_attr)
                    
                    # Potential should generally be >= current
                    if potential_val < current_val:
                        warnings.append(f"Potential {potential_attr} ({potential_val}) is less than current {current_attr} ({current_val})")
                    
                    # Check for unrealistic gaps
                    gap = potential_val - current_val
                    if gap > 30:  # Arbitrary threshold for unrealistic potential
                        warnings.append(f"Large gap between current {current_attr} ({current_val}) and potential ({potential_val})")
                        
            except Exception as e:
                logger.debug(f"Could not validate progression for {current_attr}: {e}")
        
        return warnings