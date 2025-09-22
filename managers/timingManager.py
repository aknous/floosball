"""
TimingManager - Handles different timing modes for game simulation
Provides configurable timing between SCHEDULED, SEQUENTIAL, and FAST modes
"""

import asyncio
import datetime
from enum import Enum
from typing import Optional, Dict, Any
from logger_config import get_logger

logger = get_logger("floosball.timingManager")

class TimingMode(Enum):
    """Different timing modes for game simulation"""
    SCHEDULED = "scheduled"    # Games played at specific scheduled times
    SEQUENTIAL = "sequential"  # Games played sequentially with delays but no real-time scheduling
    FAST = "fast"             # No delays, immediate execution

class TimingManager:
    """Manages timing and delays for different simulation modes"""
    
    def __init__(self, mode: TimingMode = TimingMode.FAST):
        self.mode = mode
        self.delays = self._getDefaultDelays()
        
        logger.info(f"TimingManager initialized in {mode.value} mode")
    
    def _getDefaultDelays(self) -> Dict[str, float]:
        """Get default delay values in seconds"""
        return {
            # Week-level delays
            'week_setup': 30.0,        # Time before week starts
            'week_start_wait': 30.0,   # Time between week announcement and games
            'week_end_wait': 120.0,    # Time after week ends
            
            # Game-level delays  
            'between_games': 2.0,      # Time between individual games
            'game_announcement': 30.0,  # Time for game announcements
            
            # In-game delays (floosball_game.py)
            'quarter_break': 15.0,     # Time between quarters
            'halftime': 60.0,          # Halftime delay
            'between_plays': 8.0,      # Time between individual plays (random 5-15s)
            
            # Season-level delays
            'offseason': 30.0,         # Time for offseason processing
            'season_transition': 120.0, # Time between seasons
            
            # Playoff delays
            'playoff_round': 30.0,     # Time between playoff rounds
            'championship': 60.0,      # Extra time for championship
            
            # Daily scheduling (for SCHEDULED mode)
            'daily_check': 30.0,       # How often to check if it's time for next game
        }
    
    def setMode(self, mode: TimingMode) -> None:
        """Change timing mode"""
        self.mode = mode
        logger.info(f"Timing mode changed to {mode.value}")
    
    def setCustomDelays(self, delays: Dict[str, float]) -> None:
        """Set custom delay values"""
        self.delays.update(delays)
        logger.info(f"Updated timing delays: {delays}")
    
    async def waitForWeekStart(self, weekStartTime: datetime.datetime) -> None:
        """Wait until week should start based on timing mode"""
        if self.mode == TimingMode.SCHEDULED:
            # Wait for actual scheduled time
            now = datetime.datetime.utcnow()
            timeToStart = weekStartTime - now
            
            if timeToStart.total_seconds() > 0:
                logger.info(f"Waiting {timeToStart.total_seconds():.1f}s for scheduled week start")
                
                # Check periodically if it's time to start
                while datetime.datetime.utcnow() < weekStartTime:
                    await asyncio.sleep(self.delays['daily_check'])
                    
        elif self.mode == TimingMode.SEQUENTIAL:
            # Fixed delay for sequential mode
            logger.info(f"Sequential mode: waiting {self.delays['week_setup']}s before week")
            await asyncio.sleep(self.delays['week_setup'])
            
        # FAST mode: no delay
    
    async def waitForWeekSetup(self, weekSetupTime: datetime.datetime) -> None:
        """Wait for week setup time"""
        if self.mode == TimingMode.SCHEDULED:
            # Wait for setup time (usually 10 minutes before start)
            now = datetime.datetime.utcnow()
            if now < weekSetupTime:
                timeToSetup = weekSetupTime - now
                logger.info(f"Waiting {timeToSetup.total_seconds():.1f}s for week setup")
                
                while datetime.datetime.utcnow() < weekSetupTime:
                    await asyncio.sleep(self.delays['daily_check'])
                    
        elif self.mode == TimingMode.SEQUENTIAL:
            logger.info(f"Sequential mode: week setup delay {self.delays['week_start_wait']}s")
            await asyncio.sleep(self.delays['week_start_wait'])
    
    async def waitForGamesStart(self, weekStartTime: datetime.datetime) -> None:
        """Wait until games should start"""
        if self.mode == TimingMode.SCHEDULED:
            # Wait for exact start time
            now = datetime.datetime.utcnow()
            if now < weekStartTime:
                timeToStart = weekStartTime - now
                logger.info(f"Waiting {timeToStart.total_seconds():.1f}s for games to start")
                
                while datetime.datetime.utcnow() < weekStartTime:
                    await asyncio.sleep(self.delays['daily_check'])
                    
        elif self.mode == TimingMode.SEQUENTIAL:
            logger.info(f"Sequential mode: games start delay {self.delays['game_announcement']}s")
            await asyncio.sleep(self.delays['game_announcement'])
    
    async def waitAfterWeek(self) -> None:
        """Wait after week completes"""
        if self.mode == TimingMode.SEQUENTIAL:
            logger.info(f"Sequential mode: post-week delay {self.delays['week_end_wait']}s")
            await asyncio.sleep(self.delays['week_end_wait'])
        elif self.mode == TimingMode.SCHEDULED:
            # Shorter delay for scheduled mode since timing is handled by schedule
            await asyncio.sleep(self.delays['week_end_wait'] / 4)
    
    async def waitBetweenGames(self) -> None:
        """Wait between individual games"""
        if self.mode == TimingMode.SEQUENTIAL:
            logger.debug(f"Sequential mode: between games delay {self.delays['between_games']}s")
            await asyncio.sleep(self.delays['between_games'])
    
    async def waitForOffseason(self) -> None:
        """Wait during offseason processing"""
        if self.mode == TimingMode.SEQUENTIAL:
            logger.info(f"Sequential mode: offseason delay {self.delays['offseason']}s")
            await asyncio.sleep(self.delays['offseason'])
        elif self.mode == TimingMode.SCHEDULED:
            # Shorter delay for scheduled mode
            await asyncio.sleep(self.delays['offseason'] / 2)
    
    async def waitBetweenSeasons(self) -> None:
        """Wait between seasons"""
        if self.mode == TimingMode.SEQUENTIAL:
            logger.info(f"Sequential mode: season transition delay {self.delays['season_transition']}s")
            await asyncio.sleep(self.delays['season_transition'])
        elif self.mode == TimingMode.SCHEDULED:
            await asyncio.sleep(self.delays['season_transition'] / 4)
    
    async def waitForPlayoffRound(self) -> None:
        """Wait between playoff rounds"""
        if self.mode == TimingMode.SEQUENTIAL:
            logger.info(f"Sequential mode: playoff round delay {self.delays['playoff_round']}s")
            await asyncio.sleep(self.delays['playoff_round'])
    
    async def waitForChampionship(self) -> None:
        """Extra wait for championship game"""
        if self.mode == TimingMode.SEQUENTIAL:
            logger.info(f"Sequential mode: championship delay {self.delays['championship']}s")
            await asyncio.sleep(self.delays['championship'])
    
    def shouldWaitForTime(self) -> bool:
        """Check if current mode uses real-time scheduling"""
        return self.mode == TimingMode.SCHEDULED
    
    def shouldUseDelays(self) -> bool:
        """Check if current mode uses any delays"""
        return self.mode != TimingMode.FAST
    
    def getMode(self) -> TimingMode:
        """Get current timing mode"""
        return self.mode
    
    def getModeString(self) -> str:
        """Get current mode as string"""
        return self.mode.value
    
    def getDelayConfig(self) -> Dict[str, float]:
        """Get current delay configuration"""
        return self.delays.copy()
    
    # Game-specific timing methods
    async def waitForQuarterBreak(self) -> None:
        """Wait between quarters in a game"""
        if self.mode == TimingMode.SEQUENTIAL:
            logger.debug(f"Sequential mode: quarter break delay {self.delays['quarter_break']}s")
            await asyncio.sleep(self.delays['quarter_break'])
    
    async def waitForHalftime(self) -> None:
        """Wait during halftime"""
        if self.mode == TimingMode.SEQUENTIAL:
            logger.debug(f"Sequential mode: halftime delay {self.delays['halftime']}s")
            await asyncio.sleep(self.delays['halftime'])
    
    async def waitBetweenPlays(self) -> None:
        """Wait between individual plays in a game"""
        if self.mode == TimingMode.SEQUENTIAL:
            # Use randomized delay based on original random(5,15) pattern
            import random
            delay = random.uniform(self.delays['between_plays'] * 0.6, self.delays['between_plays'] * 1.4)
            logger.debug(f"Sequential mode: between plays delay {delay:.1f}s")
            await asyncio.sleep(delay)
    
    @classmethod
    def fromConfig(cls, config: Dict[str, Any]) -> 'TimingManager':
        """Create TimingManager from configuration"""
        mode_str = config.get('timingMode', 'fast').lower()
        
        # Convert string to enum
        mode = TimingMode.FAST  # default
        for tm in TimingMode:
            if tm.value == mode_str:
                mode = tm
                break
        
        manager = cls(mode)
        
        # Set custom delays if provided
        if 'timingDelays' in config:
            manager.setCustomDelays(config['timingDelays'])
        
        return manager