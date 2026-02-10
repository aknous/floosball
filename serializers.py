"""Modern serialization utilities using dataclasses and type-safe conversion"""

from dataclasses import dataclass, asdict, fields, is_dataclass
from typing import Any, Dict, List, Union, Optional
from enum import Enum
import json
from logger_config import get_logger

logger = get_logger("floosball.serializers")

class SerializationMixin:
    """Mixin to add serialization capabilities to any class"""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert object to dictionary recursively"""
        return serialize_object(self)
    
    def to_json(self, indent: Optional[int] = None) -> str:
        """Convert object to JSON string"""
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

def serialize_object(obj: Any, _visited: Optional[set] = None, _depth: int = 0) -> Any:
    """
    Recursively serialize an object to a JSON-compatible format
    Handles: dataclasses, enums, lists, dicts, and custom objects
    Prevents circular references by tracking visited objects
    """
    # Initialize visited set on first call
    if _visited is None:
        _visited = set()
    
    # Prevent infinite recursion with depth limit
    if _depth > 10:
        return f"<max depth reached: {type(obj).__name__}>"
    
    try:
        # Handle None
        if obj is None:
            return None
        
        # Handle primitive types
        if isinstance(obj, (str, int, float, bool)):
            return obj
        
        # Handle Enum types
        if isinstance(obj, Enum):
            return obj.name
        
        # Check for circular references (for objects with identity)
        obj_id = id(obj)
        if obj_id in _visited and not isinstance(obj, (dict, list, tuple, str)):
            # Return a simple reference for circular dependencies
            if hasattr(obj, 'name'):
                return f"<ref: {obj.name}>"
            elif hasattr(obj, 'id'):
                return f"<ref: {type(obj).__name__}#{obj.id}>"
            return f"<ref: {type(obj).__name__}>"
        
        # Mark as visited
        _visited.add(obj_id)
        
        # Handle dataclass
        if is_dataclass(obj):
            result = {}
            for field in fields(obj):
                value = getattr(obj, field.name)
                result[field.name] = serialize_object(value, _visited, _depth + 1)
            return result
        
        # Handle dictionary
        if isinstance(obj, dict):
            return {key: serialize_object(value, _visited, _depth + 1) for key, value in obj.items() if value is not None}
        
        # Handle list/tuple
        if isinstance(obj, (list, tuple)):
            return [serialize_object(item, _visited, _depth + 1) for item in obj]
        
        # Handle custom objects with __dict__
        if hasattr(obj, '__dict__'):
            result = {}
            for key, value in obj.__dict__.items():
                if not key.startswith('_'):  # Skip private attributes
                    serialized_value = serialize_object(value, _visited, _depth + 1)
                    if serialized_value is not None:  # Skip None values
                        result[key] = serialized_value
            return result
        
        # Handle objects with name attribute (like Position, PlayerTier, etc.)
        if hasattr(obj, 'name'):
            return obj.name
        
        # Fallback: try to convert to string
        logger.warning(f"Could not serialize object of type {type(obj)}, converting to string")
        return str(obj)
        
    except RecursionError as e:
        logger.error(f"Recursion error serializing {type(obj)}: {e}")
        return f"<recursion: {type(obj).__name__}>"
    except Exception as e:
        logger.error(f"Error serializing object {type(obj)}: {e}")
        return str(obj)

@dataclass
class PlayerStatsData:
    """Dataclass for player statistics"""
    team: Optional[str] = None
    season: int = 0
    gp: int = 0
    fantasyPoints: int = 0
    
    # Nested stats will be handled by separate dataclasses

@dataclass  
class PassingStats:
    """Dataclass for passing statistics"""
    att: int = 0
    comp: int = 0
    compPerc: float = 0.0
    missedPass: int = 0
    tds: int = 0
    ints: int = 0
    yards: int = 0
    ypc: float = 0.0
    twenty_plus: int = 0  # Using underscore instead of '20+'
    longest: int = 0

@dataclass
class RushingStats:
    """Dataclass for rushing statistics"""
    carries: int = 0
    yards: int = 0
    ypc: float = 0.0
    longest: int = 0
    tds: int = 0
    twenty_plus: int = 0
    fumblesLost: int = 0

@dataclass  
class ReceivingStats:
    """Dataclass for receiving statistics"""
    targets: int = 0
    receptions: int = 0
    rcvPerc: float = 0.0
    drops: int = 0
    yards: int = 0
    ypr: float = 0.0
    yac: int = 0
    longest: int = 0
    tds: int = 0
    twenty_plus: int = 0

@dataclass
class KickingStats:
    """Dataclass for kicking statistics"""
    fgAtt: int = 0
    fgs: int = 0
    fgPerc: float = 0.0
    fgYards: int = 0
    longest: int = 0
    fgUnder20att: int = 0
    fgUnder20: int = 0
    fgUnder20perc: float = 0.0
    fg20to40att: int = 0
    fg20to40: int = 0
    fg20to40perc: float = 0.0
    fg40to50att: int = 0
    fg40to50: int = 0
    fg40to50perc: float = 0.0
    fgOver50att: int = 0
    fgOver50: int = 0
    fgOver50perc: float = 0.0
    xpAtt: int = 0
    xps: int = 0
    xpPerc: float = 0.0

@dataclass
class ComprehensivePlayerStats(SerializationMixin):
    """Complete player statistics with all categories"""
    team: Optional[str] = None
    season: int = 0
    gp: int = 0
    fantasyPoints: int = 0
    passing: PassingStats = None
    rushing: RushingStats = None  
    receiving: ReceivingStats = None
    kicking: KickingStats = None
    
    def __post_init__(self):
        """Initialize nested dataclasses if None"""
        if self.passing is None:
            self.passing = PassingStats()
        if self.rushing is None:
            self.rushing = RushingStats()
        if self.receiving is None:
            self.receiving = ReceivingStats()
        if self.kicking is None:
            self.kicking = KickingStats()

class ModernSerializer:
    """Modern replacement for the old _prepare_for_serialization function"""
    
    @staticmethod
    def serialize(obj: Any) -> Dict[str, Any]:
        """
        Main serialization method - replaces _prepare_for_serialization
        """
        return serialize_object(obj)
    
    @staticmethod
    def convert_legacy_stats_dict(stats_dict: Dict) -> ComprehensivePlayerStats:
        """
        Convert legacy stats dictionary to modern dataclass structure
        """
        try:
            # Extract basic info
            team = stats_dict.get('team')
            season = stats_dict.get('season', 0)
            gp = stats_dict.get('gp', 0)
            fantasy_points = stats_dict.get('fantasyPoints', 0)
            
            # Convert passing stats
            passing_data = stats_dict.get('passing', {})
            passing_stats = PassingStats(
                att=passing_data.get('att', 0),
                comp=passing_data.get('comp', 0),
                compPerc=passing_data.get('compPerc', 0.0),
                missedPass=passing_data.get('missedPass', 0),
                tds=passing_data.get('tds', 0),
                ints=passing_data.get('ints', 0),
                yards=passing_data.get('yards', 0),
                ypc=passing_data.get('ypc', 0.0),
                twenty_plus=passing_data.get('20+', 0),
                longest=passing_data.get('longest', 0)
            )
            
            # Convert rushing stats
            rushing_data = stats_dict.get('rushing', {})
            rushing_stats = RushingStats(
                carries=rushing_data.get('carries', 0),
                yards=rushing_data.get('yards', 0),
                ypc=rushing_data.get('ypc', 0.0),
                longest=rushing_data.get('longest', 0),
                tds=rushing_data.get('tds', 0),
                twenty_plus=rushing_data.get('20+', 0),
                fumblesLost=rushing_data.get('fumblesLost', 0)
            )
            
            # Convert receiving stats
            receiving_data = stats_dict.get('receiving', {})
            receiving_stats = ReceivingStats(
                targets=receiving_data.get('targets', 0),
                receptions=receiving_data.get('receptions', 0),
                rcvPerc=receiving_data.get('rcvPerc', 0.0),
                drops=receiving_data.get('drops', 0),
                yards=receiving_data.get('yards', 0),
                ypr=receiving_data.get('ypr', 0.0),
                yac=receiving_data.get('yac', 0),
                longest=receiving_data.get('longest', 0),
                tds=receiving_data.get('tds', 0),
                twenty_plus=receiving_data.get('20+', 0)
            )
            
            # Convert kicking stats
            kicking_data = stats_dict.get('kicking', {})
            kicking_stats = KickingStats(
                fgAtt=kicking_data.get('fgAtt', 0),
                fgs=kicking_data.get('fgs', 0),
                fgPerc=kicking_data.get('fgPerc', 0.0),
                fgYards=kicking_data.get('fgYards', 0),
                longest=kicking_data.get('longest', 0),
                fgUnder20att=kicking_data.get('fgUnder20att', 0),
                fgUnder20=kicking_data.get('fgUnder20', 0),
                fgUnder20perc=kicking_data.get('fgUnder20perc', 0.0),
                fg20to40att=kicking_data.get('fg20to40att', 0),
                fg20to40=kicking_data.get('fg20to40', 0),
                fg20to40perc=kicking_data.get('fg20to40perc', 0.0),
                fg40to50att=kicking_data.get('fg40to50att', 0),
                fg40to50=kicking_data.get('fg40to50', 0),
                fg40to50perc=kicking_data.get('fg40to50perc', 0.0),
                fgOver50att=kicking_data.get('fgOver50att', 0),
                fgOver50=kicking_data.get('fgOver50', 0),
                fgOver50perc=kicking_data.get('fgOver50perc', 0.0),
                xpAtt=kicking_data.get('xpAtt', 0),
                xps=kicking_data.get('xps', 0),
                xpPerc=kicking_data.get('xpPerc', 0.0)
            )
            
            return ComprehensivePlayerStats(
                team=team,
                season=season,
                gp=gp,
                fantasyPoints=fantasy_points,
                passing=passing_stats,
                rushing=rushing_stats,
                receiving=receiving_stats,
                kicking=kicking_stats
            )
            
        except Exception as e:
            logger.error(f"Error converting legacy stats dict: {e}")
            return ComprehensivePlayerStats()  # Return empty stats on error