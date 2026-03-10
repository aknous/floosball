import math
from enum import Enum

class StatCategory(Enum):
    PASSING = 'passing'
    RECEIVING = 'receiving'
    RUSHING = 'rushing'
    KICKING = 'kicking'

class StatType(Enum):
    GAME = 'game'
    SEASON = 'season'
    CAREER = 'career'

class StatTracker:
    """Base class for tracking player statistics across game, season, and career"""
    
    def __init__(self, game_stats_dict, season_stats_dict, career_stats_dict,
                 on_fantasy_points=None):
        self.game_stats_dict = game_stats_dict
        self.season_stats_dict = season_stats_dict
        self.career_stats_dict = career_stats_dict
        self._on_fantasy_points = on_fantasy_points
    
    def add_stat(self, category: StatCategory, subcategory: str, value: int = 1, is_regular_season: bool = True):
        """Generic method to add stats across all stat dictionaries"""
        category_name = category.value
        
        # Always update game stats
        if category_name in self.game_stats_dict and subcategory in self.game_stats_dict[category_name]:
            self.game_stats_dict[category_name][subcategory] += value
        
        # Update season and career stats only if regular season
        if is_regular_season:
            if category_name in self.season_stats_dict and subcategory in self.season_stats_dict[category_name]:
                self.season_stats_dict[category_name][subcategory] += value
            
            if category_name in self.career_stats_dict and subcategory in self.career_stats_dict[category_name]:
                self.career_stats_dict[category_name][subcategory] += value
    
    def add_fantasy_points(self, points: int):
        """Add fantasy points — routes through callback if set.

        When callback is set (during games with fantasy tracker), delegates to
        FantasyTracker which updates both _weekFP and gameStatsDict.
        When not set, falls back to direct dict update (tests, non-fantasy contexts).
        """
        if self._on_fantasy_points:
            self._on_fantasy_points(points)
        else:
            if 'fantasyPoints' in self.game_stats_dict:
                self.game_stats_dict['fantasyPoints'] += points
    
    def calculate_fantasy_points_for_yards(self, current_yards: int, additional_yards: int, points_per_interval: int, interval_size: int) -> int:
        """Calculate fantasy points based on yard intervals"""
        old_intervals = math.floor(current_yards / interval_size)
        new_intervals = math.floor((current_yards + additional_yards) / interval_size)
        return (new_intervals - old_intervals) * points_per_interval

    # Passing statistics methods
    def add_pass_td(self, yards: int, is_regular_season: bool = True):
        """Add passing touchdown"""
        self.add_stat(StatCategory.PASSING, 'tds', 1, is_regular_season)
        self.add_fantasy_points(4)
        if yards >= 40:
            self.add_fantasy_points(2)
    
    def add_completion(self, is_regular_season: bool = True):
        """Add completion"""
        self.add_stat(StatCategory.PASSING, 'comp', 1, is_regular_season)
    
    def add_interception(self, is_regular_season: bool = True):
        """Add interception"""
        self.add_stat(StatCategory.PASSING, 'ints', 1, is_regular_season)
        self.add_fantasy_points(-2)
    
    def add_pass_attempt(self, is_regular_season: bool = True):
        """Add pass attempt"""
        self.add_stat(StatCategory.PASSING, 'att', 1, is_regular_season)
    
    def add_pass_yards(self, yards: int, is_regular_season: bool = True):
        """Add passing yards"""
        current_yards = self.game_stats_dict['passing']['yards']
        fantasy_points = self.calculate_fantasy_points_for_yards(current_yards, yards, 1, 25)
        self.add_fantasy_points(fantasy_points)
        self.add_stat(StatCategory.PASSING, 'yards', yards, is_regular_season)
    
    def add_missed_pass(self, is_regular_season: bool = True):
        """Add missed pass"""
        self.add_stat(StatCategory.PASSING, 'missedPass', 1, is_regular_season)
    
    # Receiving statistics methods
    def add_rcv_pass_target(self, is_regular_season: bool = True):
        """Add receiving target"""
        self.add_stat(StatCategory.RECEIVING, 'targets', 1, is_regular_season)
    
    def add_reception(self, is_regular_season: bool = True):
        """Add reception"""
        self.add_stat(StatCategory.RECEIVING, 'receptions', 1, is_regular_season)
    
    def add_pass_drop(self, is_regular_season: bool = True):
        """Add pass drop"""
        self.add_stat(StatCategory.RECEIVING, 'drops', 1, is_regular_season)
    
    def add_receive_yards(self, yards: int, is_regular_season: bool = True):
        """Add receiving yards"""
        current_yards = self.game_stats_dict['receiving']['yards']
        fantasy_points = self.calculate_fantasy_points_for_yards(current_yards, yards, 1, 10)
        self.add_fantasy_points(fantasy_points)
        self.add_stat(StatCategory.RECEIVING, 'yards', yards, is_regular_season)
    
    def add_yac(self, yac: int, is_regular_season: bool = True):
        """Add yards after catch"""
        self.add_stat(StatCategory.RECEIVING, 'yac', yac, is_regular_season)
    
    def add_receive_td(self, yards: int, is_regular_season: bool = True):
        """Add receiving touchdown"""
        self.add_stat(StatCategory.RECEIVING, 'tds', 1, is_regular_season)
        self.add_fantasy_points(6)
        if yards >= 40:
            self.add_fantasy_points(2)
    
    # Rushing statistics methods
    def add_carry(self, is_regular_season: bool = True):
        """Add rushing carry"""
        self.add_stat(StatCategory.RUSHING, 'carries', 1, is_regular_season)
    
    def add_rush_td(self, yards: int, is_regular_season: bool = True):
        """Add rushing touchdown"""
        self.add_stat(StatCategory.RUSHING, 'tds', 1, is_regular_season)
        self.add_fantasy_points(6)
        if yards >= 40:
            self.add_fantasy_points(2)
    
    def add_rush_yards(self, yards: int, is_regular_season: bool = True):
        """Add rushing yards"""
        current_yards = self.game_stats_dict['rushing']['yards']
        fantasy_points = self.calculate_fantasy_points_for_yards(current_yards, yards, 1, 10)
        self.add_fantasy_points(fantasy_points)
        self.add_stat(StatCategory.RUSHING, 'yards', yards, is_regular_season)
    
    def add_fumble(self, is_regular_season: bool = True):
        """Add fumble"""
        self.add_stat(StatCategory.RUSHING, 'fumblesLost', 1, is_regular_season)
        self.add_fantasy_points(-2)
    
    # Kicking statistics methods
    def add_fg_attempt(self, is_regular_season: bool = True):
        """Add field goal attempt"""
        self.add_stat(StatCategory.KICKING, 'fgAtt', 1, is_regular_season)
    
    def add_fg(self, yards: int, is_regular_season: bool = True):
        """Add field goal"""
        self.add_stat(StatCategory.KICKING, 'fgs', 1, is_regular_season)
        self.add_stat(StatCategory.KICKING, 'fgYards', yards, is_regular_season)
        
        # Fantasy points based on distance
        if yards >= 50:
            self.add_fantasy_points(5)
        elif yards >= 40:
            self.add_fantasy_points(4)
        else:
            self.add_fantasy_points(3)