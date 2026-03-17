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
    TURBO = "turbo"           # No in-game delays, but pauses between games/weeks/seasons
    FAST = "fast"             # No delays, immediate execution
    DEMO = "demo"             # Like FAST but with visible offseason pick delays for UI testing
    TEST_SCHEDULED = "test-scheduled"  # Compressed SCHEDULED: real polling but minutes apart instead of hours
    OFFSEASON_TEST = "offseason-test"  # Fast regular season (no broadcast), interactive offseason

class TimingManager:
    """Manages timing and delays for different simulation modes"""
    
    def __init__(self, mode: TimingMode = TimingMode.FAST, scheduleGap: int = 60):
        self.mode = mode
        self.scheduleGap = scheduleGap  # seconds between rounds in TEST_SCHEDULED mode
        self.catchingUp = False  # When True, week-level waits use SEQUENTIAL delays for catch-up
        self.delays = self._getDefaultDelays()
        if mode == TimingMode.TURBO:
            self.delays.update(self._getTurboDelays())
        elif mode == TimingMode.DEMO:
            self.delays.update(self._getDemoDelays())
        elif mode == TimingMode.SCHEDULED:
            self.delays.update(self._getScheduledDelays())
        elif mode == TimingMode.TEST_SCHEDULED:
            self.delays.update(self._getTestScheduledDelays())
        elif mode == TimingMode.OFFSEASON_TEST:
            self.delays.update(self._getOffseasonTestDelays())

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
            'onside_kick_result': 2.0, # Dramatic pause between onside attempt and result
            
            # Season-level delays
            'offseason': 30.0,         # Time for offseason processing
            'offseason_pick': 0.4,     # Delay between each free agency pick broadcast
            'season_transition': 120.0, # Time between seasons
            
            # Playoff delays
            'playoff_round': 30.0,     # Time between playoff rounds
            'championship': 60.0,      # Extra time for championship
            
            # Daily scheduling (for SCHEDULED mode)
            'daily_check': 30.0,       # How often to check if it's time for next game
        }
    
    def _getDemoDelays(self) -> Dict[str, float]:
        """Demo-mode overrides: no game/week delays, but visible offseason pick delay for UI testing"""
        return {
            'offseason_pick': 5,  # Visible delay between free agency picks
        }

    def _getTurboDelays(self) -> Dict[str, float]:
        """Turbo-mode overrides: short pauses between games/weeks, nothing in-game"""
        return {
            'week_setup': 5.0,
            'week_start_wait': 5.0,
            'game_announcement': 5.0,
            'week_end_wait': 10.0,
            'between_games': 1.0,
            'offseason': 10.0,
            'offseason_pick': 0.1,
            'season_transition': 10.0,
            'playoff_round': 10.0,
            'championship': 10.0,
        }

    def _getScheduledDelays(self) -> Dict[str, float]:
        """Scheduled-mode overrides: longer offseason delay and visible pick pacing for real users"""
        return {
            'offseason': 300.0,        # 5 minutes — breathing room after Floosbowl
            'offseason_pick': 5.0,     # 5s per pick so users can follow the draft
        }

    def _getTestScheduledDelays(self) -> Dict[str, float]:
        """Test-scheduled overrides: compressed real-time scheduling with fast polling"""
        return {
            'daily_check': 2.0,        # Poll every 2s instead of 30s
            'week_setup': 5.0,
            'week_start_wait': 5.0,
            'week_end_wait': 5.0,
            'between_games': 1.0,
            'game_announcement': 5.0,
            'offseason': 5.0,
            'offseason_pick': 0.1,
            'season_transition': 10.0,
            'playoff_round': 5.0,
            'championship': 5.0,
        }

    def _getOffseasonTestDelays(self) -> Dict[str, float]:
        """Offseason-test overrides: fast games, but visible offseason picks"""
        return {
            'offseason_pick': 5.0,     # 5s per pick (same as SCHEDULED)
            'offseason': 10.0,         # Short offseason wait before FA window
            'season_transition': 10.0,
        }

    def setMode(self, mode: TimingMode) -> None:
        """Change timing mode"""
        self.mode = mode
        if mode == TimingMode.TURBO:
            self.delays.update(self._getTurboDelays())
        elif mode == TimingMode.DEMO:
            self.delays.update(self._getDemoDelays())
        elif mode == TimingMode.SCHEDULED:
            self.delays.update(self._getScheduledDelays())
        elif mode == TimingMode.TEST_SCHEDULED:
            self.delays.update(self._getTestScheduledDelays())
        elif mode == TimingMode.OFFSEASON_TEST:
            self.delays.update(self._getOffseasonTestDelays())
        logger.info(f"Timing mode changed to {mode.value}")
    
    def setCustomDelays(self, delays: Dict[str, float]) -> None:
        """Set custom delay values"""
        self.delays.update(delays)
        logger.info(f"Updated timing delays: {delays}")
    
    @property
    def _isScheduledMode(self) -> bool:
        return self.mode in (TimingMode.SCHEDULED, TimingMode.TEST_SCHEDULED)

    async def waitForWeekStart(self, weekStartTime: datetime.datetime) -> None:
        """Wait until week should start based on timing mode"""
        if self._isScheduledMode:
            # Wait for actual scheduled time
            now = datetime.datetime.utcnow()
            timeToStart = weekStartTime - now

            if timeToStart.total_seconds() > 0:
                logger.info(f"Waiting {timeToStart.total_seconds():.1f}s for scheduled week start")

                # Check periodically if it's time to start
                while datetime.datetime.utcnow() < weekStartTime:
                    await asyncio.sleep(self.delays['daily_check'])

        elif self.mode in (TimingMode.SEQUENTIAL, TimingMode.TURBO):
            # Fixed delay for sequential/turbo mode
            logger.info(f"{self.mode.value} mode: waiting {self.delays['week_setup']}s before week")
            await asyncio.sleep(self.delays['week_setup'])

        # FAST mode: no delay

    async def waitForWeekSetup(self, weekSetupTime: datetime.datetime) -> None:
        """Wait for week setup time"""
        if self._isScheduledMode:
            if self.catchingUp:
                # Catch-up: use SEQUENTIAL-style delay instead of waiting for schedule
                logger.info(f"Catch-up mode: short week setup delay ({self.delays['week_start_wait']}s)")
                await asyncio.sleep(self.delays['week_start_wait'])
            else:
                # Wait for setup time (usually 10 minutes before start)
                now = datetime.datetime.utcnow()
                if now < weekSetupTime:
                    timeToSetup = weekSetupTime - now
                    logger.info(f"Waiting {timeToSetup.total_seconds():.1f}s for week setup")

                    while datetime.datetime.utcnow() < weekSetupTime:
                        await asyncio.sleep(self.delays['daily_check'])

        elif self.mode in (TimingMode.SEQUENTIAL, TimingMode.TURBO):
            logger.info(f"{self.mode.value} mode: week setup delay {self.delays['week_start_wait']}s")
            await asyncio.sleep(self.delays['week_start_wait'])

    async def waitForGamesStart(self, weekStartTime: datetime.datetime) -> None:
        """Wait until games should start"""
        if self._isScheduledMode:
            if self.catchingUp:
                # Catch-up: use SEQUENTIAL-style delay instead of waiting for schedule
                logger.info(f"Catch-up mode: short games start delay ({self.delays['game_announcement']}s)")
                await asyncio.sleep(self.delays['game_announcement'])
            else:
                # Wait for exact start time
                now = datetime.datetime.utcnow()
                if now < weekStartTime:
                    timeToStart = weekStartTime - now
                    logger.info(f"Waiting {timeToStart.total_seconds():.1f}s for games to start")

                    while datetime.datetime.utcnow() < weekStartTime:
                        await asyncio.sleep(self.delays['daily_check'])

        elif self.mode in (TimingMode.SEQUENTIAL, TimingMode.TURBO):
            logger.info(f"{self.mode.value} mode: games start delay {self.delays['game_announcement']}s")
            await asyncio.sleep(self.delays['game_announcement'])

    async def waitAfterWeek(self) -> None:
        """Wait after week completes"""
        if self.mode in (TimingMode.SEQUENTIAL, TimingMode.TURBO):
            logger.info(f"{self.mode.value} mode: post-week delay {self.delays['week_end_wait']}s")
            await asyncio.sleep(self.delays['week_end_wait'])
        elif self._isScheduledMode:
            # Shorter delay for scheduled mode since timing is handled by schedule
            await asyncio.sleep(self.delays['week_end_wait'] / 4)

    async def waitBetweenGames(self) -> None:
        """Wait between individual games"""
        if self.mode in (TimingMode.SEQUENTIAL, TimingMode.TURBO):
            logger.debug(f"{self.mode.value} mode: between games delay {self.delays['between_games']}s")
            await asyncio.sleep(self.delays['between_games'])

    async def waitForOffseason(self) -> None:
        """Wait during offseason processing"""
        if self.mode in (TimingMode.SCHEDULED, TimingMode.SEQUENTIAL, TimingMode.TURBO, TimingMode.OFFSEASON_TEST):
            logger.info(f"{self.mode.value} mode: offseason delay {self.delays['offseason']}s")
            await asyncio.sleep(self.delays['offseason'])
        elif self._isScheduledMode:
            # Test-scheduled: shorter delay
            await asyncio.sleep(self.delays['offseason'] / 2)

    async def waitBetweenSeasons(self) -> None:
        """Wait between seasons.

        SCHEDULED mode: poll until next Monday at 11:00 local time.
        This gives a maintenance window (Sunday) between offseason and new season.
        SEQUENTIAL / TURBO: fixed delay from config.
        """
        if self.mode == TimingMode.SCHEDULED:
            targetUtc = self._nextMondayUtc(hour=11)
            pollInterval = self.delays.get('daily_check', 30.0)
            logger.info(f"SCHEDULED mode: waiting for next season start at {targetUtc.isoformat()} (polling every {pollInterval}s)")
            while datetime.datetime.utcnow() < targetUtc:
                await asyncio.sleep(pollInterval)
            logger.info("Season start time reached — proceeding")
        elif self.mode in (TimingMode.SEQUENTIAL, TimingMode.TURBO):
            logger.info(f"{self.mode.value} mode: season transition delay {self.delays['season_transition']}s")
            await asyncio.sleep(self.delays['season_transition'])
        elif self.mode == TimingMode.TEST_SCHEDULED:
            await asyncio.sleep(self.delays['season_transition'])

    @staticmethod
    def _nextMondayUtc(hour: int = 11) -> datetime.datetime:
        """Compute the next Monday at the given local hour, returned as UTC."""
        now = datetime.datetime.now()
        nowUtc = datetime.datetime.utcnow()
        utcOffset = round((nowUtc - now).total_seconds() / 3600)

        # Find next Monday (weekday 0)
        daysAhead = (7 - now.weekday()) % 7  # 0=Monday
        if daysAhead == 0:
            # It's already Monday — if before target hour, use today; otherwise next week
            if now.hour >= hour:
                daysAhead = 7
        targetLocal = now.replace(hour=hour, minute=0, second=0, microsecond=0) + datetime.timedelta(days=daysAhead)
        targetUtc = targetLocal + datetime.timedelta(hours=utcOffset)
        return targetUtc

    async def waitForPlayoffRound(self, roundStartTime: 'datetime.datetime | None' = None) -> None:
        """Wait between playoff rounds"""
        if self._isScheduledMode and roundStartTime:
            now = datetime.datetime.utcnow()
            if now < roundStartTime:
                logger.info(f"Waiting {(roundStartTime - now).total_seconds():.1f}s for playoff round start")
                while datetime.datetime.utcnow() < roundStartTime:
                    await asyncio.sleep(self.delays['daily_check'])
        elif self.mode in (TimingMode.SEQUENTIAL, TimingMode.TURBO):
            logger.info(f"{self.mode.value} mode: playoff round delay {self.delays['playoff_round']}s")
            await asyncio.sleep(self.delays['playoff_round'])

    async def waitForChampionship(self, roundStartTime: 'datetime.datetime | None' = None) -> None:
        """Wait for championship game start"""
        if self._isScheduledMode and roundStartTime:
            now = datetime.datetime.utcnow()
            if now < roundStartTime:
                logger.info(f"Waiting {(roundStartTime - now).total_seconds():.1f}s for championship start")
                while datetime.datetime.utcnow() < roundStartTime:
                    await asyncio.sleep(self.delays['daily_check'])
        elif self.mode in (TimingMode.SEQUENTIAL, TimingMode.TURBO):
            logger.info(f"{self.mode.value} mode: championship delay {self.delays['championship']}s")
            await asyncio.sleep(self.delays['championship'])
    
    def shouldWaitForTime(self) -> bool:
        """Check if current mode uses real-time scheduling"""
        return self._isScheduledMode
    
    def shouldUseDelays(self) -> bool:
        """Check if current mode uses any delays"""
        return self.mode not in (TimingMode.FAST,)

    def shouldUseInGameDelays(self) -> bool:
        """Check if current mode uses in-game delays (between plays, quarters, halftime)"""
        return self.mode == TimingMode.SEQUENTIAL
    
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
    # SCHEDULED uses the same in-game delays as SEQUENTIAL so users can watch live.
    async def waitForQuarterBreak(self) -> None:
        """Wait between quarters in a game"""
        if self.mode in (TimingMode.SCHEDULED, TimingMode.SEQUENTIAL):
            logger.debug(f"{self.mode.value} mode: quarter break delay {self.delays['quarter_break']}s")
            await asyncio.sleep(self.delays['quarter_break'])

    async def waitForHalftime(self) -> None:
        """Wait during halftime"""
        if self.mode in (TimingMode.SCHEDULED, TimingMode.SEQUENTIAL):
            logger.debug(f"{self.mode.value} mode: halftime delay {self.delays['halftime']}s")
            await asyncio.sleep(self.delays['halftime'])

    async def waitBetweenPlays(self) -> None:
        """Wait between individual plays in a game"""
        if self.mode in (TimingMode.SCHEDULED, TimingMode.SEQUENTIAL):
            import random
            delay = random.uniform(self.delays['between_plays'] * 0.6, self.delays['between_plays'] * 1.4)
            logger.debug(f"{self.mode.value} mode: between plays delay {delay:.1f}s")
            await asyncio.sleep(delay)

    async def waitAfterKickoff(self) -> None:
        """Brief pause after kickoff broadcast, before first play of new drive."""
        if self.mode in (TimingMode.SCHEDULED, TimingMode.SEQUENTIAL):
            import random
            delay = random.uniform(
                self.delays.get('after_kickoff', 3.0) * 0.6,
                self.delays.get('after_kickoff', 3.0) * 1.4
            )
            logger.debug(f"{self.mode.value} mode: after kickoff delay {delay:.1f}s")
            await asyncio.sleep(delay)

    async def waitBetweenOffseasonPicks(self) -> None:
        """Wait between offseason free agency pick broadcasts"""
        if self.mode in (TimingMode.SCHEDULED, TimingMode.SEQUENTIAL, TimingMode.TURBO, TimingMode.DEMO, TimingMode.OFFSEASON_TEST):
            await asyncio.sleep(self.delays['offseason_pick'])

    async def waitBeforeOnsideResult(self) -> None:
        """Dramatic pause between 'attempts onside kick' announcement and recovery result."""
        if self.mode in (TimingMode.SCHEDULED, TimingMode.SEQUENTIAL):
            import random
            delay = random.uniform(
                self.delays.get('onside_kick_result', 2.0) * 0.75,
                self.delays.get('onside_kick_result', 2.0) * 1.25
            )
            logger.debug(f"{self.mode.value} mode: onside kick result delay {delay:.1f}s")
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
        
        scheduleGap = int(config.get('scheduleGap', 60))
        manager = cls(mode, scheduleGap=scheduleGap)

        # Set custom delays if provided
        if 'timingDelays' in config:
            manager.setCustomDelays(config['timingDelays'])

        return manager