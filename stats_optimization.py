"""Optimized statistics dictionary system to reduce deep copying overhead"""

from typing import Dict, Any, Optional
from dataclasses import dataclass, field
import copy
from logger_config import get_logger

logger = get_logger("floosball.stats_optimization")

@dataclass
class PassingStats:
    """Optimized passing statistics structure"""
    att: int = 0
    comp: int = 0
    compPerc: float = 0.0
    missedPass: int = 0
    tds: int = 0
    ints: int = 0
    yards: int = 0
    ypc: float = 0.0
    twenty_plus: int = 0  # 20+
    longest: int = 0
    
    def reset(self):
        """Reset all stats to zero (faster than creating new instance)"""
        self.att = 0
        self.comp = 0
        self.compPerc = 0.0
        self.missedPass = 0
        self.tds = 0
        self.ints = 0
        self.yards = 0
        self.ypc = 0.0
        self.twenty_plus = 0
        self.longest = 0
    
    def copy_from(self, other: 'PassingStats'):
        """Copy values from another PassingStats instance"""
        self.att = other.att
        self.comp = other.comp
        self.compPerc = other.compPerc
        self.missedPass = other.missedPass
        self.tds = other.tds
        self.ints = other.ints
        self.yards = other.yards
        self.ypc = other.ypc
        self.twenty_plus = other.twenty_plus
        self.longest = other.longest

@dataclass
class RushingStats:
    """Optimized rushing statistics structure"""
    carries: int = 0
    yards: int = 0
    ypc: float = 0.0
    longest: int = 0
    tds: int = 0
    twenty_plus: int = 0  # 20+
    fumblesLost: int = 0
    
    def reset(self):
        """Reset all stats to zero"""
        self.carries = 0
        self.yards = 0
        self.ypc = 0.0
        self.longest = 0
        self.tds = 0
        self.twenty_plus = 0
        self.fumblesLost = 0
    
    def copy_from(self, other: 'RushingStats'):
        """Copy values from another RushingStats instance"""
        self.carries = other.carries
        self.yards = other.yards
        self.ypc = other.ypc
        self.longest = other.longest
        self.tds = other.tds
        self.twenty_plus = other.twenty_plus
        self.fumblesLost = other.fumblesLost

@dataclass
class ReceivingStats:
    """Optimized receiving statistics structure"""
    targets: int = 0
    receptions: int = 0
    rcvPerc: float = 0.0
    drops: int = 0
    yards: int = 0
    ypr: float = 0.0
    yac: int = 0
    longest: int = 0
    tds: int = 0
    twenty_plus: int = 0  # 20+
    
    def reset(self):
        """Reset all stats to zero"""
        self.targets = 0
        self.receptions = 0
        self.rcvPerc = 0.0
        self.drops = 0
        self.yards = 0
        self.ypr = 0.0
        self.yac = 0
        self.longest = 0
        self.tds = 0
        self.twenty_plus = 0
    
    def copy_from(self, other: 'ReceivingStats'):
        """Copy values from another ReceivingStats instance"""
        self.targets = other.targets
        self.receptions = other.receptions
        self.rcvPerc = other.rcvPerc
        self.drops = other.drops
        self.yards = other.yards
        self.ypr = other.ypr
        self.yac = other.yac
        self.longest = other.longest
        self.tds = other.tds
        self.twenty_plus = other.twenty_plus

@dataclass
class KickingStats:
    """Optimized kicking statistics structure"""
    fgAtt: int = 0
    fgs: int = 0
    fgPerc: float = 0.0
    fgYards: int = 0
    longest: int = 0
    fg45_plus: int = 0  # fg45+
    
    # Distance-specific stats
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
    
    # Extra points
    xpAtt: int = 0
    xps: int = 0
    xpPerc: float = 0.0
    
    def reset(self):
        """Reset all stats to zero"""
        self.fgAtt = 0
        self.fgs = 0
        self.fgPerc = 0.0
        self.fgYards = 0
        self.longest = 0
        self.fg45_plus = 0
        self.fgUnder20att = 0
        self.fgUnder20 = 0
        self.fgUnder20perc = 0.0
        self.fg20to40att = 0
        self.fg20to40 = 0
        self.fg20to40perc = 0.0
        self.fg40to50att = 0
        self.fg40to50 = 0
        self.fg40to50perc = 0.0
        self.fgOver50att = 0
        self.fgOver50 = 0
        self.fgOver50perc = 0.0
        self.xpAtt = 0
        self.xps = 0
        self.xpPerc = 0.0

@dataclass
class OptimizedPlayerStats:
    """Optimized player statistics using dataclass structures"""
    team: Optional[str] = None
    season: int = 0
    gp: int = 0
    fantasyPoints: int = 0
    
    # Nested stats - using instances instead of dicts
    passing: PassingStats = field(default_factory=PassingStats)
    rushing: RushingStats = field(default_factory=RushingStats)
    receiving: ReceivingStats = field(default_factory=ReceivingStats)
    kicking: KickingStats = field(default_factory=KickingStats)
    
    def reset_for_new_game(self):
        """Reset game stats (much faster than deepcopy)"""
        self.gp = 0
        self.fantasyPoints = 0
        self.passing.reset()
        self.rushing.reset()
        self.receiving.reset()
        self.kicking.reset()
    
    def copy_from(self, other: 'OptimizedPlayerStats'):
        """Copy stats from another instance (faster than deepcopy)"""
        self.team = other.team
        self.season = other.season
        self.gp = other.gp
        self.fantasyPoints = other.fantasyPoints
        self.passing.copy_from(other.passing)
        self.rushing.copy_from(other.rushing)
        self.receiving.copy_from(other.receiving)
        # Note: kicking copy_from method would need to be implemented if needed
    
    def to_legacy_dict(self) -> Dict[str, Any]:
        """Convert to legacy dictionary format for backwards compatibility"""
        return {
            'team': self.team,
            'season': self.season,
            'gp': self.gp,
            'fantasyPoints': self.fantasyPoints,
            'passing': {
                'att': self.passing.att,
                'comp': self.passing.comp,
                'compPerc': self.passing.compPerc,
                'missedPass': self.passing.missedPass,
                'tds': self.passing.tds,
                'ints': self.passing.ints,
                'yards': self.passing.yards,
                'ypc': self.passing.ypc,
                '20+': self.passing.twenty_plus,
                'longest': self.passing.longest
            },
            'rushing': {
                'carries': self.rushing.carries,
                'yards': self.rushing.yards,
                'ypc': self.rushing.ypc,
                'longest': self.rushing.longest,
                'tds': self.rushing.tds,
                '20+': self.rushing.twenty_plus,
                'fumblesLost': self.rushing.fumblesLost
            },
            'receiving': {
                'targets': self.receiving.targets,
                'receptions': self.receiving.receptions,
                'rcvPerc': self.receiving.rcvPerc,
                'drops': self.receiving.drops,
                'yards': self.receiving.yards,
                'ypr': self.receiving.ypr,
                'yac': self.receiving.yac,
                'longest': self.receiving.longest,
                'tds': self.receiving.tds,
                '20+': self.receiving.twenty_plus
            },
            'kicking': {
                'fgAtt': self.kicking.fgAtt,
                'fgs': self.kicking.fgs,
                'fgPerc': self.kicking.fgPerc,
                'fgYards': self.kicking.fgYards,
                'longest': self.kicking.longest,
                'fg45+': self.kicking.fg45_plus,
                'fgUnder20att': self.kicking.fgUnder20att,
                'fgUnder20': self.kicking.fgUnder20,
                'fgUnder20perc': self.kicking.fgUnder20perc,
                'fg20to40att': self.kicking.fg20to40att,
                'fg20to40': self.kicking.fg20to40,
                'fg20to40perc': self.kicking.fg20to40perc,
                'fg40to50att': self.kicking.fg40to50att,
                'fg40to50': self.kicking.fg40to50,
                'fg40to50perc': self.kicking.fg40to50perc,
                'fgOver50att': self.kicking.fgOver50att,
                'fgOver50': self.kicking.fgOver50,
                'fgOver50perc': self.kicking.fgOver50perc,
                'xpAtt': self.kicking.xpAtt,
                'xps': self.kicking.xps,
                'xpPerc': self.kicking.xpPerc
            }
        }
    
    @classmethod
    def from_legacy_dict(cls, data: Dict[str, Any]) -> 'OptimizedPlayerStats':
        """Create from legacy dictionary format"""
        stats = cls()
        stats.team = data.get('team')
        stats.season = data.get('season', 0)
        stats.gp = data.get('gp', 0)
        stats.fantasyPoints = data.get('fantasyPoints', 0)
        
        # Load passing stats
        if 'passing' in data:
            p = data['passing']
            stats.passing.att = p.get('att', 0)
            stats.passing.comp = p.get('comp', 0)
            stats.passing.compPerc = p.get('compPerc', 0.0)
            stats.passing.missedPass = p.get('missedPass', 0)
            stats.passing.tds = p.get('tds', 0)
            stats.passing.ints = p.get('ints', 0)
            stats.passing.yards = p.get('yards', 0)
            stats.passing.ypc = p.get('ypc', 0.0)
            stats.passing.twenty_plus = p.get('20+', 0)
            stats.passing.longest = p.get('longest', 0)
        
        # Load rushing stats
        if 'rushing' in data:
            r = data['rushing']
            stats.rushing.carries = r.get('carries', 0)
            stats.rushing.yards = r.get('yards', 0)
            stats.rushing.ypc = r.get('ypc', 0.0)
            stats.rushing.longest = r.get('longest', 0)
            stats.rushing.tds = r.get('tds', 0)
            stats.rushing.twenty_plus = r.get('20+', 0)
            stats.rushing.fumblesLost = r.get('fumblesLost', 0)
        
        # Load receiving stats
        if 'receiving' in data:
            rec = data['receiving']
            stats.receiving.targets = rec.get('targets', 0)
            stats.receiving.receptions = rec.get('receptions', 0)
            stats.receiving.rcvPerc = rec.get('rcvPerc', 0.0)
            stats.receiving.drops = rec.get('drops', 0)
            stats.receiving.yards = rec.get('yards', 0)
            stats.receiving.ypr = rec.get('ypr', 0.0)
            stats.receiving.yac = rec.get('yac', 0)
            stats.receiving.longest = rec.get('longest', 0)
            stats.receiving.tds = rec.get('tds', 0)
            stats.receiving.twenty_plus = rec.get('20+', 0)
        
        # Load kicking stats (if present)
        if 'kicking' in data:
            k = data['kicking']
            stats.kicking.fgAtt = k.get('fgAtt', 0)
            stats.kicking.fgs = k.get('fgs', 0)
            stats.kicking.fgPerc = k.get('fgPerc', 0.0)
            stats.kicking.fgYards = k.get('fgYards', 0)
            stats.kicking.longest = k.get('longest', 0)
            stats.kicking.fg45_plus = k.get('fg45+', 0)
            # ... other kicking stats as needed
        
        return stats

class StatsPool:
    """Object pool for reusing stats instances"""
    
    def __init__(self, initial_size: int = 50):
        self._available_stats: list = []
        self._in_use: set = set()
        
        # Pre-populate pool
        for _ in range(initial_size):
            self._available_stats.append(OptimizedPlayerStats())
    
    def get_stats(self) -> OptimizedPlayerStats:
        """Get a stats instance from the pool"""
        if self._available_stats:
            stats = self._available_stats.pop()
            stats.reset_for_new_game()  # Ensure it's clean
            self._in_use.add(id(stats))
            return stats
        else:
            # Pool is empty, create new instance
            stats = OptimizedPlayerStats()
            self._in_use.add(id(stats))
            logger.debug("Stats pool exhausted, creating new instance")
            return stats
    
    def return_stats(self, stats: OptimizedPlayerStats):
        """Return a stats instance to the pool"""
        stats_id = id(stats)
        if stats_id in self._in_use:
            self._in_use.remove(stats_id)
            stats.reset_for_new_game()
            self._available_stats.append(stats)
    
    def get_pool_size(self) -> tuple:
        """Get (available, in_use) pool sizes"""
        return len(self._available_stats), len(self._in_use)

# Global stats pool
stats_pool = StatsPool()

def get_optimized_stats() -> OptimizedPlayerStats:
    """Get an optimized stats instance from the pool"""
    return stats_pool.get_stats()

def return_optimized_stats(stats: OptimizedPlayerStats):
    """Return an optimized stats instance to the pool"""
    stats_pool.return_stats(stats)