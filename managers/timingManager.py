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


def _isEdtDate(d):
    """Return True if date d falls within US Eastern Daylight Time.

    EDT: 2nd Sunday of March → 1st Sunday of November.  Date-level
    granularity is sufficient for scheduling purposes.
    """
    year = d.year
    mar1 = datetime.date(year, 3, 1)
    firstSunMar = (6 - mar1.weekday()) % 7 + 1
    secondSunMar = firstSunMar + 7

    nov1 = datetime.date(year, 11, 1)
    firstSunNov = (6 - nov1.weekday()) % 7 + 1

    edtStart = datetime.date(year, 3, secondSunMar)
    edtEnd = datetime.date(year, 11, firstSunNov)

    asDate = d if isinstance(d, datetime.date) and not isinstance(d, datetime.datetime) else d.date() if hasattr(d, 'date') else d
    return edtStart <= asDate < edtEnd


def _nowEastern():
    """Return the current time as a naive datetime in US Eastern time,
    computed from UTC with a manual EDT/EST offset (avoids stale tzdata)."""
    utcNow = datetime.datetime.utcnow()
    offset = 4 if _isEdtDate(utcNow) else 5
    return utcNow - datetime.timedelta(hours=offset)

class TimingMode(Enum):
    """Different timing modes for game simulation"""
    SCHEDULED = "scheduled"    # Games played at specific scheduled times
    SEQUENTIAL = "sequential"  # Games played sequentially with delays but no real-time scheduling
    TURBO = "turbo"           # No in-game delays, but pauses between games/weeks/seasons
    FAST = "fast"             # No delays, immediate execution
    DEMO = "demo"             # Like FAST but with visible offseason pick delays for UI testing
    TEST_SCHEDULED = "test-scheduled"  # Compressed SCHEDULED: real polling but minutes apart instead of hours
    OFFSEASON_TEST = "offseason-test"  # Fast regular season (no broadcast), interactive offseason
    CATCHUP = "catchup"                # Backdate season to last Monday, catch up, then behave like SCHEDULED
    FAST_CATCHUP = "fast-catchup"      # Like CATCHUP but skips ALL delays during catch-up (instant sim)
    PLAYOFF_TEST = "playoff-test"      # FAST regular season + compressed scheduled playoffs (with broadcasting)
    TURBO_SILENT = "turbo-silent"      # Sequential delays between games/weeks, no in-game delays, no broadcasting
    FAST_WEEKLY = "fast-weekly"        # FAST games (no delays, no broadcast), 30s pause between weeks

class TimingManager:
    """Manages timing and delays for different simulation modes"""
    
    def __init__(self, mode: TimingMode = TimingMode.FAST, scheduleGap: int = 60):
        self.mode = mode
        self.scheduleGap = scheduleGap  # seconds between rounds in TEST_SCHEDULED / PLAYOFF_TEST mode
        self.catchingUp = False  # When True, week-level waits use SEQUENTIAL delays for catch-up
        self.playoffPhase = False  # Set by seasonManager when playoffs begin (for PLAYOFF_TEST)
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
        elif mode in (TimingMode.CATCHUP, TimingMode.FAST_CATCHUP):
            self.delays.update(self._getScheduledDelays())
        elif mode == TimingMode.PLAYOFF_TEST:
            self.delays.update(self._getPlayoffTestDelays())
        elif mode == TimingMode.FAST_WEEKLY:
            self.delays.update(self._getFastWeeklyDelays())
        # TURBO_SILENT: uses default (sequential) delays — no overrides needed

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
            'post_championship': 30.0, # Time after Floos Bowl before offseason starts
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
            'post_championship': 3600.0, # 1 hour — let users see Floos Bowl results
            'offseason': 300.0,        # 5 minutes — breathing room before FA draft
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

    def _getPlayoffTestDelays(self) -> Dict[str, float]:
        """Playoff-test overrides: FAST regular season, compressed scheduled playoffs.
        Regular season has no delays; playoffs use real polling with scheduleGap spacing."""
        return {
            'daily_check': 2.0,        # Fast polling during playoff waits
        }

    def _getFastWeeklyDelays(self) -> Dict[str, float]:
        """Fast-weekly overrides: no in-game or between-games delays (games blast
        through instantly), 30-second pause between weeks, and a roomier offseason
        (~1–2 min) since that's the phase most worth examining in this mode.
        Broadcasting is disabled in run_api.py for this mode — no WebSocket
        traffic, pure sim output."""
        return {
            # In-game: zero everything so games resolve instantly
            'between_plays': 0.0,
            'quarter_break': 0.0,
            'halftime': 0.0,
            'between_games': 0.0,
            'game_announcement': 0.0,
            # Week boundaries: 30s pause so you can follow the season
            'week_setup': 30.0,
            'week_start_wait': 0.0,
            'week_end_wait': 30.0,
            # Offseason: breathing room for inspecting offseason features
            # (rookie class, retirement watch, prospect pipeline, FA draft)
            'post_championship': 60.0,     # 1 min after Floos Bowl
            'offseason': 90.0,             # 1.5 min pre-draft pause
            'offseason_pick': 1.5,         # visible FA + rookie draft picks
            'season_transition': 60.0,     # 1 min between seasons
            'playoff_round': 30.0,
            'championship': 30.0,
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
        elif mode in (TimingMode.CATCHUP, TimingMode.FAST_CATCHUP):
            self.delays.update(self._getScheduledDelays())
        elif mode == TimingMode.PLAYOFF_TEST:
            self.delays.update(self._getPlayoffTestDelays())
        elif mode == TimingMode.FAST_WEEKLY:
            self.delays.update(self._getFastWeeklyDelays())
        # TURBO_SILENT: uses default (sequential) delays — no overrides needed
        logger.info(f"Timing mode changed to {mode.value}")
    
    def setCustomDelays(self, delays: Dict[str, float]) -> None:
        """Set custom delay values"""
        self.delays.update(delays)
        logger.info(f"Updated timing delays: {delays}")
    
    @property
    def _isScheduledMode(self) -> bool:
        return self.mode in (TimingMode.SCHEDULED, TimingMode.TEST_SCHEDULED, TimingMode.CATCHUP, TimingMode.FAST_CATCHUP)

    @property
    def _isFastCatchingUp(self) -> bool:
        """True when in FAST_CATCHUP mode and still behind schedule — skip all delays."""
        return self.mode == TimingMode.FAST_CATCHUP and self.catchingUp

    async def waitForWeekStart(self, weekStartTime: datetime.datetime) -> None:
        """Wait until week should start based on timing mode.

        In SCHEDULED mode the week begins 15 minutes before game time so
        users still have time to view the previous week's results.
        """
        if self._isFastCatchingUp:
            return
        if self._isScheduledMode:
            # Start the week 15 minutes before games kick off
            weekRolloverTime = weekStartTime - datetime.timedelta(minutes=15)
            now = datetime.datetime.utcnow()
            timeToStart = weekRolloverTime - now

            if timeToStart.total_seconds() > 0:
                logger.info(f"Waiting {timeToStart.total_seconds():.1f}s for scheduled week start (15 min before games)")

                # Check periodically if it's time to start
                while datetime.datetime.utcnow() < weekRolloverTime:
                    await asyncio.sleep(self.delays['daily_check'])

        elif self.mode in (TimingMode.SEQUENTIAL, TimingMode.TURBO, TimingMode.TURBO_SILENT, TimingMode.FAST_WEEKLY):
            # Fixed delay for sequential/turbo mode
            logger.info(f"{self.mode.value} mode: waiting {self.delays['week_setup']}s before week")
            await asyncio.sleep(self.delays['week_setup'])

        # FAST mode: no delay

    async def waitForWeekSetup(self, weekSetupTime: datetime.datetime) -> None:
        """Wait for week setup time"""
        if self._isFastCatchingUp:
            return
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

        elif self.mode in (TimingMode.SEQUENTIAL, TimingMode.TURBO, TimingMode.TURBO_SILENT, TimingMode.FAST_WEEKLY):
            logger.info(f"{self.mode.value} mode: week setup delay {self.delays['week_start_wait']}s")
            await asyncio.sleep(self.delays['week_start_wait'])

    async def waitForGamesStart(self, weekStartTime: datetime.datetime) -> None:
        """Wait until games should start"""
        if self._isFastCatchingUp:
            return
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

        elif self.mode == TimingMode.PLAYOFF_TEST and self.playoffPhase:
            # During playoffs: wait for exact scheduled start time
            now = datetime.datetime.utcnow()
            if now < weekStartTime:
                timeToStart = weekStartTime - now
                logger.info(f"PLAYOFF_TEST: waiting {timeToStart.total_seconds():.1f}s for playoff games to start")
                while datetime.datetime.utcnow() < weekStartTime:
                    await asyncio.sleep(self.delays['daily_check'])

        elif self.mode in (TimingMode.SEQUENTIAL, TimingMode.TURBO, TimingMode.TURBO_SILENT, TimingMode.FAST_WEEKLY):
            logger.info(f"{self.mode.value} mode: games start delay {self.delays['game_announcement']}s")
            await asyncio.sleep(self.delays['game_announcement'])

    async def waitAfterWeek(self) -> None:
        """Wait after week completes"""
        if self._isFastCatchingUp:
            return
        if self.mode in (TimingMode.SEQUENTIAL, TimingMode.TURBO, TimingMode.TURBO_SILENT, TimingMode.FAST_WEEKLY):
            logger.info(f"{self.mode.value} mode: post-week delay {self.delays['week_end_wait']}s")
            await asyncio.sleep(self.delays['week_end_wait'])
        # SCHEDULED: no fixed delay — waitForWeekStart handles the 15-min pre-game buffer

    async def waitBetweenGames(self) -> None:
        """Wait between individual games"""
        if self._isFastCatchingUp:
            return
        if self.mode in (TimingMode.SEQUENTIAL, TimingMode.TURBO, TimingMode.TURBO_SILENT, TimingMode.FAST_WEEKLY):
            logger.debug(f"{self.mode.value} mode: between games delay {self.delays['between_games']}s")
            await asyncio.sleep(self.delays['between_games'])

    async def waitPostChampionship(self) -> None:
        """Wait after Floos Bowl before starting offseason, so users can see results."""
        if self._isFastCatchingUp:
            return
        delay = self.delays.get('post_championship', 30.0)
        if self.mode in (TimingMode.SCHEDULED, TimingMode.SEQUENTIAL, TimingMode.TURBO, TimingMode.TURBO_SILENT, TimingMode.CATCHUP):
            logger.info(f"{self.mode.value} mode: post-championship delay {delay}s")
            await asyncio.sleep(delay)
        elif self._isScheduledMode:
            await asyncio.sleep(delay / 2)

    async def waitForOffseason(self) -> None:
        """Wait during offseason processing"""
        if self._isFastCatchingUp:
            return
        if self.mode in (TimingMode.SCHEDULED, TimingMode.SEQUENTIAL, TimingMode.TURBO, TimingMode.OFFSEASON_TEST, TimingMode.CATCHUP, TimingMode.FAST_WEEKLY):
            logger.info(f"{self.mode.value} mode: offseason delay {self.delays['offseason']}s")
            await asyncio.sleep(self.delays['offseason'])
        elif self._isScheduledMode:
            # Test-scheduled: shorter delay
            await asyncio.sleep(self.delays['offseason'] / 2)

    async def waitBetweenSeasons(self) -> None:
        """Wait between seasons.

        SCHEDULED mode: poll until next Monday at 04:00 Eastern.
        This gives a maintenance window (Sunday) between offseason and new season.
        SEQUENTIAL / TURBO: fixed delay from config.
        """
        if self.mode == TimingMode.SCHEDULED:
            targetUtc = self._nextMondayUtc(hour=4)
            pollInterval = self.delays.get('daily_check', 30.0)
            logger.info(f"SCHEDULED mode: waiting for next season start at {targetUtc.isoformat()} (polling every {pollInterval}s)")
            while datetime.datetime.utcnow() < targetUtc:
                await asyncio.sleep(pollInterval)
            logger.info("Season start time reached — proceeding")
        elif self.mode in (TimingMode.SEQUENTIAL, TimingMode.TURBO, TimingMode.TURBO_SILENT, TimingMode.FAST_WEEKLY):
            logger.info(f"{self.mode.value} mode: season transition delay {self.delays['season_transition']}s")
            await asyncio.sleep(self.delays['season_transition'])
        elif self.mode == TimingMode.TEST_SCHEDULED:
            await asyncio.sleep(self.delays['season_transition'])
        elif self.mode in (TimingMode.CATCHUP, TimingMode.FAST_CATCHUP):
            logger.info(f"{self.mode.value} mode: starting season immediately (backdated to last Monday)")

    @staticmethod
    def _nextMondayUtc(hour: int = 4) -> datetime.datetime:
        """Compute the next Monday at the given Eastern hour, returned as naive UTC."""
        nowEt = _nowEastern()

        # Find next Monday (weekday 0)
        daysAhead = (7 - nowEt.weekday()) % 7  # 0=Monday
        if daysAhead == 0:
            # It's already Monday — if before target hour, use today; otherwise next week
            if nowEt.hour >= hour:
                daysAhead = 7
        targetEt = nowEt.replace(hour=hour, minute=0, second=0, microsecond=0) + datetime.timedelta(days=daysAhead)
        # Convert naive ET back to naive UTC
        offset = 4 if _isEdtDate(targetEt) else 5
        return targetEt + datetime.timedelta(hours=offset)

    @staticmethod
    def _lastMondayUtc(hour: int = 4) -> datetime.datetime:
        """Compute the most recent Monday at the given Eastern hour, returned as naive UTC."""
        nowEt = _nowEastern()

        daysBack = nowEt.weekday()  # Monday=0, so 0 days back on Monday
        if daysBack == 0 and nowEt.hour < hour:
            daysBack = 7  # Before target hour on Monday — use previous Monday
        targetEt = nowEt.replace(hour=hour, minute=0, second=0, microsecond=0) - datetime.timedelta(days=daysBack)
        # Convert naive ET back to naive UTC
        offset = 4 if _isEdtDate(targetEt) else 5
        return targetEt + datetime.timedelta(hours=offset)

    async def waitForPlayoffRound(self, roundStartTime: 'datetime.datetime | None' = None, earlyMinutes: int = 15) -> None:
        """Wait between playoff rounds.
        In SCHEDULED mode, rolls over earlyMinutes before start so
        matchups are visible before kickoff."""
        if self._isFastCatchingUp:
            return
        if self._isScheduledMode and roundStartTime:
            rolloverTime = roundStartTime - datetime.timedelta(minutes=earlyMinutes)
            now = datetime.datetime.utcnow()
            if now < rolloverTime:
                logger.info(f"Waiting {(rolloverTime - now).total_seconds():.1f}s for playoff round rollover ({earlyMinutes} min before start)")
                while datetime.datetime.utcnow() < rolloverTime:
                    await asyncio.sleep(self.delays['daily_check'])
        elif self.mode == TimingMode.PLAYOFF_TEST and roundStartTime:
            # Scaled rollover: 1/3 of gap before start (e.g. 20s before with gap=60)
            rolloverSec = max(5, self.scheduleGap / 3)
            rolloverTime = roundStartTime - datetime.timedelta(seconds=rolloverSec)
            now = datetime.datetime.utcnow()
            if now < rolloverTime:
                logger.info(f"PLAYOFF_TEST: waiting {(rolloverTime - now).total_seconds():.1f}s for rollover ({rolloverSec:.0f}s before start)")
                while datetime.datetime.utcnow() < rolloverTime:
                    await asyncio.sleep(self.delays['daily_check'])
        elif self.mode in (TimingMode.SEQUENTIAL, TimingMode.TURBO, TimingMode.TURBO_SILENT, TimingMode.FAST_WEEKLY):
            logger.info(f"{self.mode.value} mode: playoff round delay {self.delays['playoff_round']}s")
            await asyncio.sleep(self.delays['playoff_round'])

    async def waitForChampionship(self, roundStartTime: 'datetime.datetime | None' = None) -> None:
        """Wait for championship game start.
        In SCHEDULED mode, rolls over 15 min early so matchups are visible."""
        if self._isFastCatchingUp:
            return
        if self._isScheduledMode and roundStartTime:
            rolloverTime = roundStartTime - datetime.timedelta(minutes=15)
            now = datetime.datetime.utcnow()
            if now < rolloverTime:
                logger.info(f"Waiting {(rolloverTime - now).total_seconds():.1f}s for championship rollover (15 min before start)")
                while datetime.datetime.utcnow() < rolloverTime:
                    await asyncio.sleep(self.delays['daily_check'])
        elif self.mode == TimingMode.PLAYOFF_TEST and roundStartTime:
            rolloverSec = max(5, self.scheduleGap / 3)
            rolloverTime = roundStartTime - datetime.timedelta(seconds=rolloverSec)
            now = datetime.datetime.utcnow()
            if now < rolloverTime:
                logger.info(f"PLAYOFF_TEST: waiting {(rolloverTime - now).total_seconds():.1f}s for championship rollover ({rolloverSec:.0f}s before start)")
                while datetime.datetime.utcnow() < rolloverTime:
                    await asyncio.sleep(self.delays['daily_check'])
        elif self.mode in (TimingMode.SEQUENTIAL, TimingMode.TURBO, TimingMode.TURBO_SILENT, TimingMode.FAST_WEEKLY):
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
        if self.mode in (TimingMode.SCHEDULED, TimingMode.SEQUENTIAL, TimingMode.CATCHUP):
            logger.debug(f"{self.mode.value} mode: quarter break delay {self.delays['quarter_break']}s")
            await asyncio.sleep(self.delays['quarter_break'])
        else:
            await asyncio.sleep(0)

    async def waitForHalftime(self) -> None:
        """Wait during halftime"""
        if self.mode in (TimingMode.SCHEDULED, TimingMode.SEQUENTIAL, TimingMode.CATCHUP):
            logger.debug(f"{self.mode.value} mode: halftime delay {self.delays['halftime']}s")
            await asyncio.sleep(self.delays['halftime'])
        else:
            await asyncio.sleep(0)

    async def waitBetweenPlays(self) -> None:
        """Wait between individual plays in a game"""
        if self.mode in (TimingMode.SCHEDULED, TimingMode.SEQUENTIAL, TimingMode.CATCHUP):
            import random
            delay = random.uniform(self.delays['between_plays'] * 0.6, self.delays['between_plays'] * 1.4)
            logger.debug(f"{self.mode.value} mode: between plays delay {delay:.1f}s")
            await asyncio.sleep(delay)
        else:
            await asyncio.sleep(0)

    async def waitAfterKickoff(self) -> None:
        """Brief pause after kickoff broadcast, before first play of new drive."""
        if self.mode in (TimingMode.SCHEDULED, TimingMode.SEQUENTIAL, TimingMode.CATCHUP):
            import random
            delay = random.uniform(
                self.delays.get('after_kickoff', 3.0) * 0.6,
                self.delays.get('after_kickoff', 3.0) * 1.4
            )
            logger.debug(f"{self.mode.value} mode: after kickoff delay {delay:.1f}s")
            await asyncio.sleep(delay)
        else:
            await asyncio.sleep(0)

    async def waitAfterTimeout(self) -> None:
        """Pause after a timeout is called, before the next play resumes."""
        if self.mode in (TimingMode.SCHEDULED, TimingMode.SEQUENTIAL, TimingMode.CATCHUP):
            import random
            delay = random.uniform(
                self.delays.get('after_timeout', 3.0) * 0.6,
                self.delays.get('after_timeout', 3.0) * 1.4
            )
            logger.debug(f"{self.mode.value} mode: after timeout delay {delay:.1f}s")
            await asyncio.sleep(delay)
        else:
            await asyncio.sleep(0)

    async def waitBetweenOffseasonPicks(self) -> None:
        """Wait between offseason free agency pick broadcasts"""
        if self._isFastCatchingUp:
            return
        if self.mode in (TimingMode.SCHEDULED, TimingMode.SEQUENTIAL, TimingMode.TURBO, TimingMode.TURBO_SILENT, TimingMode.DEMO, TimingMode.OFFSEASON_TEST, TimingMode.CATCHUP, TimingMode.FAST_WEEKLY):
            await asyncio.sleep(self.delays['offseason_pick'])

    async def waitBeforeOnsideResult(self) -> None:
        """Dramatic pause between 'attempts onside kick' announcement and recovery result."""
        if self.mode in (TimingMode.SCHEDULED, TimingMode.SEQUENTIAL, TimingMode.CATCHUP):
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