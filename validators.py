"""Input validation utilities for Floosball application"""

import os
import json
from typing import Any, Dict, List, Optional, Union
from constants import RATING_SCALE_MIN, RATING_SCALE_MAX
from exceptions import ValidationError, FileOperationError

class InputValidator:
    """Utility class for input validation"""
    
    @staticmethod
    def validate_rating(rating: Union[int, float], min_val: int = RATING_SCALE_MIN, 
                       max_val: int = RATING_SCALE_MAX, field_name: str = "rating") -> int:
        """Validate that a rating is within acceptable bounds"""
        try:
            rating = int(rating)
        except (ValueError, TypeError):
            raise ValidationError(f"{field_name} must be a number, got {type(rating).__name__}")
        
        if not min_val <= rating <= max_val:
            raise ValidationError(f"{field_name} must be between {min_val} and {max_val}, got {rating}")
        
        return rating
    
    @staticmethod
    def validate_positive_integer(value: Union[int, str], field_name: str = "value") -> int:
        """Validate that a value is a positive integer"""
        try:
            value = int(value)
        except (ValueError, TypeError):
            raise ValidationError(f"{field_name} must be an integer, got {type(value).__name__}")
        
        if value < 0:
            raise ValidationError(f"{field_name} must be positive, got {value}")
        
        return value
    
    @staticmethod
    def validate_non_empty_string(value: Any, field_name: str = "value") -> str:
        """Validate that a value is a non-empty string"""
        if not isinstance(value, str):
            raise ValidationError(f"{field_name} must be a string, got {type(value).__name__}")
        
        if not value.strip():
            raise ValidationError(f"{field_name} cannot be empty")
        
        return value.strip()
    
    @staticmethod
    def validate_file_exists(file_path: str) -> str:
        """Validate that a file exists and is readable"""
        if not isinstance(file_path, str):
            raise ValidationError(f"File path must be a string, got {type(file_path).__name__}")
        
        if not os.path.exists(file_path):
            raise FileOperationError(f"File does not exist: {file_path}")
        
        if not os.path.isfile(file_path):
            raise FileOperationError(f"Path is not a file: {file_path}")
        
        if not os.access(file_path, os.R_OK):
            raise FileOperationError(f"File is not readable: {file_path}")
        
        return file_path
    
    @staticmethod
    def validate_json_file(file_path: str) -> Dict[str, Any]:
        """Validate that a file exists and contains valid JSON"""
        validated_path = InputValidator.validate_file_exists(file_path)
        
        try:
            with open(validated_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            raise FileOperationError(f"Invalid JSON in file {file_path}: {e}")
        except Exception as e:
            raise FileOperationError(f"Error reading file {file_path}: {e}")
        
        return data
    
    @staticmethod
    def validate_player_position(position: str) -> str:
        """Validate player position"""
        valid_positions = ['QB', 'RB', 'WR', 'TE', 'K']
        position = InputValidator.validate_non_empty_string(position, "position").upper()
        
        if position not in valid_positions:
            raise ValidationError(f"Invalid position: {position}. Must be one of {valid_positions}")
        
        return position
    
    @staticmethod
    def validate_game_id(game_id: Union[int, str]) -> int:
        """Validate game ID"""
        return InputValidator.validate_positive_integer(game_id, "game_id")
    
    @staticmethod
    def validate_season_number(season: Union[int, str]) -> int:
        """Validate season number"""
        season_num = InputValidator.validate_positive_integer(season, "season")
        
        if season_num > 50:  # Reasonable upper limit
            raise ValidationError(f"Season number seems too high: {season_num}")
        
        return season_num
    
    @staticmethod
    def validate_yards(yards: Union[int, str], field_name: str = "yards") -> int:
        """Validate yard values (can be negative for losses)"""
        try:
            yards = int(yards)
        except (ValueError, TypeError):
            raise ValidationError(f"{field_name} must be an integer, got {type(yards).__name__}")
        
        # Reasonable bounds for football yards
        if yards < -50 or yards > 200:
            raise ValidationError(f"{field_name} value seems unrealistic: {yards}")
        
        return yards
    
    @staticmethod
    def validate_probability(prob: Union[int, float], field_name: str = "probability") -> float:
        """Validate probability value (0.0 to 1.0)"""
        try:
            prob = float(prob)
        except (ValueError, TypeError):
            raise ValidationError(f"{field_name} must be a number, got {type(prob).__name__}")
        
        if not 0.0 <= prob <= 1.0:
            raise ValidationError(f"{field_name} must be between 0.0 and 1.0, got {prob}")
        
        return prob

class ConfigValidator:
    """Validator specifically for configuration data"""
    
    @staticmethod
    def validate_team_config(team_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate team configuration data"""
        required_fields = ['city', 'name', 'abbr', 'color']
        
        for field in required_fields:
            if field not in team_data:
                raise ValidationError(f"Missing required field in team config: {field}")
            
            team_data[field] = InputValidator.validate_non_empty_string(
                team_data[field], f"team.{field}")
        
        # Validate abbreviation length
        if len(team_data['abbr']) > 5:
            raise ValidationError(f"Team abbreviation too long: {team_data['abbr']}")
        
        return team_data
    
    @staticmethod
    def validate_league_config(config_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate league configuration data"""
        if 'leagueConfig' not in config_data:
            raise ValidationError("Missing leagueConfig in configuration")
        
        league_config = config_data['leagueConfig']
        
        # Validate cap
        if 'cap' in league_config:
            league_config['cap'] = InputValidator.validate_positive_integer(
                league_config['cap'], "leagueConfig.cap")
        
        # Validate totalSeasons
        if 'totalSeasons' in league_config:
            league_config['totalSeasons'] = InputValidator.validate_positive_integer(
                league_config['totalSeasons'], "leagueConfig.totalSeasons")
        
        return config_data