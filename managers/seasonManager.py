"""
SeasonManager - Manages season simulation, scheduling, and progression
Replaces the scattered season-related functions and global variables from floosball.py
"""

import math
import os
import json
import traceback
from typing import List, Dict, Any, Optional, Tuple
import asyncio
import datetime
import floosball_team as FloosTeam
import floosball_player as FloosPlayer
import floosball_game as FloosGame
from logger_config import get_logger
from .timingManager import TimingManager, TimingMode

# Database imports
try:
    from database.config import USE_DATABASE
    from database.connection import get_session
    from database import repositories
    from database.models import Game as DBGame, GamePlayerStats as DBGamePlayerStats
    DB_IMPORTS_AVAILABLE = True
except ImportError:
    USE_DATABASE = False
    DB_IMPORTS_AVAILABLE = False
    DBGame = None
    DBGamePlayerStats = None
    repositories = None
    get_session = None

# WebSocket broadcasting support (optional)
try:
    from api.game_broadcaster import broadcaster
    from api.event_models import SeasonEvent, StandingsEvent, LeagueNewsEvent, OffseasonEvent, GmEvent
    from api_response_builders import LeagueResponseBuilder
    BROADCASTING_AVAILABLE = True
except ImportError:
    BROADCASTING_AVAILABLE = False
    broadcaster = None
    SeasonEvent = None
    StandingsEvent = None
    LeagueNewsEvent = None
    OffseasonEvent = None
    LeagueResponseBuilder = None

logger = get_logger("floosball.seasonManager")


def _isEdt(d):
    """Return True if the given date falls within US Eastern Daylight Time.

    EDT runs from the 2nd Sunday of March at 2 AM ET to the 1st Sunday of
    November at 2 AM ET.  Since we only care about *date*-level granularity
    (we never schedule games at 2 AM), treating the boundary dates as EDT is
    fine.  US DST rules have been stable since 2007.
    """
    year = d.year if hasattr(d, 'year') else d.year
    # 2nd Sunday of March: March 1 weekday (0=Mon…6=Sun), find first Sunday,
    # then add 7 days.
    mar1 = datetime.date(year, 3, 1)
    firstSunMar = (6 - mar1.weekday()) % 7 + 1  # day-of-month of 1st Sunday
    secondSunMar = firstSunMar + 7               # day-of-month of 2nd Sunday

    # 1st Sunday of November
    nov1 = datetime.date(year, 11, 1)
    firstSunNov = (6 - nov1.weekday()) % 7 + 1

    edtStart = datetime.date(year, 3, secondSunMar)
    edtEnd = datetime.date(year, 11, firstSunNov)

    return edtStart <= (d if isinstance(d, datetime.date) and not isinstance(d, datetime.datetime) else d.date() if hasattr(d, 'date') else d) < edtEnd


class Season:
    """Represents a single season"""

    def __init__(self, seasonNumber: int):
        self.seasonNumber = seasonNumber
        self.currentSeason = seasonNumber  # Backward compatibility
        self.currentWeek = 0
        self.currentWeekText = None
        self.startDate: datetime.datetime = datetime.datetime.utcnow()
        # Rule book for this season. Defaults to the standard ruleset.
        # Cores' rule patches (e.g. a fan-voted scoring change) are persisted
        # in app_settings and hydrated here, so the mutated ruleset is in force
        # from this season's first game and survives restarts. The patch then
        # propagates to every game scheduled in this season (each Game holds a
        # reference to this object). No-op when nothing is persisted.
        from game_rules import GameRules, loadRuleOverrides
        self.gameRules = GameRules()
        _ruleOverrides = loadRuleOverrides()
        if _ruleOverrides:
            _appliedRules = self.gameRules.applyOverrides(
                _ruleOverrides, reason="season start", source="persisted")
            if _appliedRules:
                logger.info("  GameRules: applied persisted rule override(s): "
                            f"{ {k: _ruleOverrides[k] for k in _appliedRules} }")
        self.activeGames = None
        self.completedWeekGames = None  # Finished games kept for display until next week
        self.schedule: List[Dict[str, FloosGame.Game]] = []
        self.playoffBracket: List[Dict[str, Any]] = []
        self.isComplete = False
        self.champion: Optional[FloosTeam.Team] = None
        self.leagueChampions: Dict[str, FloosTeam.Team] = {}
        self.playoffTeams: Dict[str, List[FloosTeam.Team]] = {}
        self.nonPlayoffTeams: Dict[str, List[FloosTeam.Team]] = {}
        self.leagueHighlights: List[Dict[str, Any]] = []
        self.freeAgencyOrder: List[FloosTeam.Team] = []
        self.mvp: Optional[Dict[str, Any]] = None
        self.allProPlayerIds: set = set()

class SeasonManager:
    """Manages season simulation, scheduling, and progression"""
    
    def __init__(self, serviceContainer, leagueManager, playerManager, recordsManager):
        self.serviceContainer = serviceContainer
        self.leagueManager = leagueManager
        self.playerManager = playerManager
        self.recordsManager = recordsManager
        
        self.currentSeason: Optional[Season] = None
        self.seasonHistory: List[Season] = []
        
        # Callback for state updates (set by application)
        self.stateUpdateCallback = None
        
        # Database support
        self.db_session = None
        self.game_repo = None
        
        if DB_IMPORTS_AVAILABLE and USE_DATABASE:
            self.db_session = get_session()
            self.game_repo = repositories.GameRepository(self.db_session)
            logger.info("SeasonManager using DATABASE storage")
        else:
            logger.info("SeasonManager using JSON file storage")

        # Initialize timing manager with default fast mode
        self.timingManager = TimingManager(TimingMode.FAST)

        # Game stats file
        self.game_stats_file = None

        # Track games for verbose logging
        self.games_simulated_this_season = 0

        # Global game counter for unique IDs across all seasons
        self._gameIdCounter = 0

        # Offseason transaction history (persists for page refresh)
        self._offseasonTransactions: list = []

        # Per-team aggregated fan rankings for the rookie draft (Borda count).
        # Populated when ballots are collected at rookie draft time; surfaced
        # via /api/offseason so the Front Office page can show the team's
        # tallied rookie rankings (parallel to FA fan vote tallies).

        # Cached next-game-start timestamp (set once, survives page refreshes)
        self._cachedNextGameStart: Optional[datetime.datetime] = None

        # Phased offseason state — drives UI labels and countdowns.
        #   _offseasonFlowPhase: top-level flow stage:
        #     'post_bowl'   — Floos Bowl ended, waiting to open front office
        #     'frontoffice' — GM votes resolved, FA pool populated, waiting on
        #                     noon-ET kickoff for the rookie draft
        #     'pre_fa'      — rookie draft done, waiting on top-of-hour for FA
        #     'fa_draft'    — FA picks streaming live
        #     'training'    — sequential silent calculations after FA
        #     None          — no offseason active
        #   _offseasonFlowTarget: ISO target time for the *next* phase, set
        #     during wait gates (post_bowl/frontoffice/pre_fa) and cleared
        #     during active phases. Frontend renders a countdown when present.
        # NOTE: _offseasonPhase (separate attribute) tracks the OffseasonPanel
        # sub-phase render state ('predraft', 'free_agency')
        # and is owned by the draft generators, not this flow controller.
        self._offseasonFlowPhase: Optional[str] = None
        self._offseasonFlowTarget: Optional[datetime.datetime] = None
        # Step-completion gate set used by the phase-aware checkpoints. Each
        # entry is a step key marked via _markOffseasonStepComplete; the set
        # is persisted to simulation_state.offseason_completed_steps so a
        # restart can read it back and skip already-completed batch work.
        self._offseasonCompletedSteps: set = set()

        logger.info("SeasonManager initialized")

    @property
    def _isTestMode(self) -> bool:
        return self.timingManager.mode in (TimingMode.OFFSEASON_TEST, TimingMode.DEMO)

    def setStateUpdateCallback(self, callback):
        """Set callback function for state updates"""
        self.stateUpdateCallback = callback
        logger.debug("State update callback registered")
    
    def setTimingMode(self, mode: TimingMode) -> None:
        """Set timing mode for simulation"""
        self.timingManager.setMode(mode)
        logger.info(f"Season timing mode set to {mode.value}")
    
    def setTimingModeFromString(self, mode_str: str, scheduleGap: int = 60) -> None:
        """Set timing mode from string (scheduled/sequential/turbo/fast/test-scheduled)"""
        mode_str = mode_str.lower()
        if mode_str == 'scheduled':
            self.setTimingMode(TimingMode.SCHEDULED)
        elif mode_str == 'sequential':
            self.setTimingMode(TimingMode.SEQUENTIAL)
        elif mode_str == 'turbo':
            self.setTimingMode(TimingMode.TURBO)
        elif mode_str == 'fast':
            self.setTimingMode(TimingMode.FAST)
        elif mode_str == 'demo':
            self.setTimingMode(TimingMode.DEMO)
        elif mode_str == 'test-scheduled':
            self.timingManager.scheduleGap = scheduleGap
            self.setTimingMode(TimingMode.TEST_SCHEDULED)
        elif mode_str == 'offseason-test':
            self.setTimingMode(TimingMode.OFFSEASON_TEST)
        elif mode_str in ('catchup', 'catch-up'):
            self.setTimingMode(TimingMode.CATCHUP)
        elif mode_str in ('fast-catchup', 'fast_catchup'):
            self.setTimingMode(TimingMode.FAST_CATCHUP)
        elif mode_str == 'playoff-test':
            self.timingManager.scheduleGap = scheduleGap
            self.setTimingMode(TimingMode.PLAYOFF_TEST)
        elif mode_str == 'turbo-silent':
            self.setTimingMode(TimingMode.TURBO_SILENT)
        elif mode_str in ('fast-weekly', 'fast_weekly'):
            self.setTimingMode(TimingMode.FAST_WEEKLY)
        else:
            logger.warning(f"Unknown timing mode '{mode_str}', using FAST")
            self.setTimingMode(TimingMode.FAST)
    
    def setCustomTimingDelays(self, delays: Dict[str, float]) -> None:
        """Set custom timing delays"""
        self.timingManager.setCustomDelays(delays)
    
    def getTimingMode(self) -> str:
        """Get current timing mode as string"""
        return self.timingManager.getModeString()
    
    async def startNewSeason(self, resumeFromWeek: int = 0) -> None:
        """Initialize and start a new season.

        resumeFromWeek > 0 indicates a server restart mid-season — preserves
        in-memory state (e.g. fatigue, form) that would otherwise be reset
        as if it were a brand-new season.
        """
        seasonNumber = self.serviceContainer.getService('game_state').getState('seasonsPlayed', 0) + 1
        logger.info(f"Starting season {seasonNumber}")

        # Release any recycled retiree names whose hold has elapsed back into the
        # usable pool (held NAME_REUSE_DELAY_SEASONS seasons after retirement).
        if self.playerManager:
            self.playerManager.releaseDueNames(seasonNumber)

        # Rulebook resets to defaults every NEW season, so each season is a fresh canvas
        # and the fan-voted rule mutations only live for the season that voted them in.
        # Reset BEFORE the Season is built so its GameRules loads clean defaults. This is
        # season-STAMPED (not keyed off resumeFromWeek): a restart mid-season re-enters the
        # SAME season and keeps its rules even at week 1 in progress (resumeFromWeek == 0),
        # where the old `if resumeFromWeek == 0` check wrongly wiped a just-voted format.
        from game_rules import maybeResetRuleOverridesForSeason
        maybeResetRuleOverridesForSeason(seasonNumber)

        self.currentSeason = Season(seasonNumber)

        # Anchor season start to the correct Monday
        from managers.timingManager import TimingMode, TimingManager
        if self.timingManager.mode in (TimingMode.CATCHUP, TimingMode.FAST_CATCHUP):
            # CATCHUP: backdate to last Monday so schedule anchors to the past
            self.currentSeason.startDate = TimingManager._lastMondayUtc(hour=4)
            logger.info(f"{self.timingManager.mode.value} mode: season start backdated to {self.currentSeason.startDate.isoformat()}")
        elif self.timingManager._isScheduledMode:
            # SCHEDULED: anchor to next Monday (or today if already Monday)
            now = datetime.datetime.utcnow()
            daysUntilMonday = (7 - now.weekday()) % 7  # 0 if already Monday
            nextMonday = (now + datetime.timedelta(days=daysUntilMonday)).replace(
                hour=4, minute=0, second=0, microsecond=0
            )
            self.currentSeason.startDate = nextMonday
            logger.info(f"Scheduled mode: season start anchored to {nextMonday.isoformat()}")

        # Clear previous season data
        self._clearSeasonData()

        # One-time league realignment: rebalance the two leagues by recent win% so
        # one league isn't perpetually stronger. Must run BEFORE the schedule is
        # generated (the new alignment drives the matchups). Fires once, at a genuine
        # new-season boundary; self-gated so it never re-runs.
        self._maybeRealignLeagues(seasonNumber, resumeFromWeek)

        # Create new season schedule — load from DB if resuming, otherwise generate fresh
        scheduleLoaded = False
        if DB_IMPORTS_AVAILABLE and USE_DATABASE and self.game_repo:
            if self.game_repo.has_schedule(seasonNumber):
                logger.info(f"Existing schedule found for season {seasonNumber} — loading from database")
                # Restore the original startDate BEFORE schedule load so that
                # recalculated start times use the correct anchor date.
                self._restoreSeasonStartDate(seasonNumber)
                self._fillMissingScheduleWeeks(seasonNumber)
                scheduleLoaded = self._loadScheduleFromDatabase(seasonNumber)
                if not scheduleLoaded:
                    logger.warning("Schedule load from database failed — falling back to fresh generation")
        if not scheduleLoaded:
            self.createSchedule()

        # Initialize season stats. Pass resumeFromWeek so a mid-season
        # restart skips the fatigue reset (DB already has the accumulated
        # values; resetting them in-memory would zero everyone back to fresh).
        self._initializeSeasonStats(isResume=(resumeFromWeek > 0))

        # Restore reigning champion flag from DB
        self._restoreReigningChampion(seasonNumber)

        # Initialize team funding for the new season (baseline + carry-forward) and assign initial tiers
        self._initializeTeamFunding(seasonNumber)

        # Dev-only: spread teams across all 4 funding tiers so single-user
        # testing produces a realistic tier distribution. Set DEV_SPREAD_TIERS=1
        # in the environment to enable. Teams are assigned by ID into 4 equal
        # buckets (deterministic — same team gets same tier every season).
        self._applyDevTierOverride()

        # Set prior-season expectation pressure baselines (must run after
        # statArchive is populated by season completion last year — which it
        # has been by this point — and after funding tier is assigned so
        # market scaling can read the right value at game time).
        teamMgr = self.serviceContainer.getService('team_manager')
        teamMgr.setPressureModifiersForNewSeason(seasonNumber)

        # One-time parity re-map: at a genuine new-season cutover, deflate an
        # inflated legacy pool onto the new true-skill curve BEFORE card templates
        # mint off the (now corrected) ratings. Guarded to run exactly once; auto-
        # skips a fresh / already-on-curve pool. See docs/PARITY_PROSPECT_PLAN.md.
        if resumeFromWeek == 0:
            self._maybeRunParityRemap(seasonNumber)

        # Generate card templates for the new season
        self._generateCardTemplates(seasonNumber)

        # Sweep any pending achievement rewards the user didn't claim or stash
        # last season. Must run BEFORE starter-pack reprovision and deferred
        # achievement processing so the rewards those create aren't caught by
        # the sweep.
        #
        # ONLY at a genuine new-season start (resumeFromWeek == 0). startNewSeason
        # is ALSO the mid-season resume path (resumeFromWeek > 0) called on every
        # server restart / deploy, and the sweep deletes every undeferred unclaimed
        # reward — so running it on a restart wiped the CURRENT season's rewards.
        # That cleared users' unclaimed rewards on every deploy and on the weekly
        # Monday auto-deploy restart. Skip it when resuming mid-season.
        if resumeFromWeek == 0:
            self._sweepExpiredAchievementRewards()

        # Re-provision starter packs for users who lost them in a fresh start
        # (users table is preserved but currency/cards are cleared)
        self._reprovisionExistingUsers()

        # Release any deferred achievement rewards (e.g. Veteran → pack + powerup at next season)
        self._processDeferredAchievements()

        # Snapshot every player's rating at season start — feeds the
        # progression sparkline on rosters and prospect pipelines. Idempotent
        # per (player, season) so reruns don't duplicate rows.
        try:
            self.playerManager.snapshotRatingsForSeason(seasonNumber)
        except Exception as e:
            logger.warning(f"Rating snapshot at season {seasonNumber} start failed: {e}")

        # One-time: after the parity re-map deflated current ratings, smooth the
        # pre-remap progression history so the chart doesn't cliff at the boundary.
        # Runs after the snapshot above so the remap-season row exists. Marker-guarded.
        self._maybeRebaseRatingHistoryForParity()

        # One-time: freeze existing (non-prospect) players at their current level so
        # they don't show a spurious development arc from the re-map's runway.
        self._maybeFreezeLegacyDevArc()

        # There is no rookie class. New players arrive only as the
        # position-supply deficit fill — a trickle straight into the FA pool,
        # sized to what retirement actually took out, so the pool holds steady
        # instead of inflating by a full class every season.

        # Persist season record early so startDate survives restarts
        self._saveSeasonToDatabase()

        logger.info(f"Season {seasonNumber} initialized with {len(self.currentSeason.schedule)} games")

        # The season opening belongs in the news feed as well as on the wire. Without it a
        # brand-new league has an empty feed until the first game finishes, which reads as
        # broken rather than as "nothing has happened yet".
        self._publishScheduleNews(
            'season_start',
            f'Season {seasonNumber} is under way',
            week=1,
            season=seasonNumber,
        )

        # Broadcast season_start so connected frontends update immediately
        if BROADCASTING_AVAILABLE and broadcaster.is_enabled():
            seasonStartEvent = SeasonEvent.seasonStart(
                seasonNumber=seasonNumber,
                totalWeeks=len(self.currentSeason.schedule),
            )
            broadcaster.broadcast_sync('season', seasonStartEvent)

    async def runSeasonSimulation(self, resumeFromWeek: int = 0) -> None:
        """Run full season simulation.

        Args:
            resumeFromWeek: If > 0, skip regular-season weeks up to and including this week
                            (they were already completed before a restart).
        """
        if not self.currentSeason:
            logger.error("No current season to simulate")
            return

        logger.info(f"Running simulation for season {self.currentSeason.seasonNumber}")
        
        # Reset game counter for verbose logging
        self.games_simulated_this_season = 0
        
        # Open game stats file
        self._openGameStatsFile()
        
        # Simulate regular season
        await self._simulateRegularSeason(resumeFromWeek=resumeFromWeek)

        # MVP + All-Pro selection moved to _finishSeasonAfterPlayoffs (after the
        # bowl) so the fan-voted MVP counts votes cast through the playoffs AND
        # it runs on the playoff/offseason resume paths too (this call site only
        # ran on the uninterrupted full-season run). The value metric is
        # regular-season-only, so the later timing doesn't change the result.

        # End-of-regular-season cleanup (unequip cards, etc.)
        self._processEndOfRegularSeason()

        # Award fantasy season prizes now (before playoffs) so users see final results
        logger.info("Awarding season-end fantasy prizes")
        self._awardSeasonEndPrizes(self.currentSeason.seasonNumber)

        # Simulate playoffs (pick-em continues through playoffs)
        await self._simulatePlayoffs()

        # Season-end wrap-up (shared with the mid-playoff resume path)
        await self._finishSeasonAfterPlayoffs()

    async def _finishSeasonAfterPlayoffs(self) -> None:
        """Post-playoff season wrap-up: pick-em season prizes, season-end
        emails, the unspent-Floobit tax, funding-tier lock-in, and season
        completion. Extracted so the mid-playoff resume path runs the exact
        same tail after finishing the resumed bracket. All steps here run
        once per season (after the bowl), so they're safe on the resume path
        too — they never executed in the interrupted run."""
        # Select MVP + the combined All-Pro team now that the playoffs are over
        # and the fan-voted MVP window has closed (votes cast through the
        # playoffs now count). The value metric is regular-season-only (playoff
        # box stats / WPA are excluded in _accumulatePostgameStats), so the
        # candidates are identical to the old regular-season-end timing. Running
        # here also covers the playoff-resume path, so the Season row gets the
        # MVP / All-Pro persisted by saveSeasonStats (in _completeSeasonSimulation
        # below) instead of nulls.
        await self._selectSeasonMVP()
        await self._selectSeasonAllPro()

        # Award pick-em season prizes after playoffs so all rounds are included
        logger.info("Awarding pick-em season prizes")
        self._awardPickEmSeasonPrizes(self.currentSeason.seasonNumber)

        # Send season-end email reports. Offloaded to a worker thread (same hot-
        # path reason as day-end emails). Safe to run alongside the tax/offseason
        # that follow: the report's "earned totals" sum POSITIVE transactions
        # only (the tax is a negative transaction, excluded), and the rest
        # (champion, pick-em leaderboard) is immutable historical data.
        if not self.timingManager.catchingUp:
            asyncio.get_running_loop().run_in_executor(
                None, self._sendSeasonEndEmails, self.currentSeason.seasonNumber,
            )

        # Apply season-end tax on unspent Floobits
        self._applySeasonEndTax(self.currentSeason.seasonNumber)
        # Lock in funding tiers for the offseason — fans' season-long
        # contributions (mid-season + season-end tax) recompute the team's
        # market tier NOW, so FA bidding power / training / GM thresholds /
        # rookie scouting all use the upgraded tier instead of waiting for
        # next season to begin. Until this point tiers stayed frozen at
        # season-start values so in-season mechanics couldn't drift.
        self._recomputeFundingTiersForOffseason(self.currentSeason.seasonNumber)

        # Facilities (Markets→Facilities): first resolve the fan vote — the
        # Run the season-end waterfall FIRST (Treasury pays upkeep, then the
        # projects that were OPEN and fundable all season; offseason construction
        # builds funded projects and decays unmaintained facilities). THEN resolve
        # the vote, opening the winner as a fresh project — so it goes through an
        # Active Projects season of funding before next season's waterfall can
        # complete it, instead of being built instantly by this season's Treasury.
        # Costs are share-denominated off the PRIOR season's faucet.
        self._runFacilitySeasonEnd(self.currentSeason.seasonNumber)
        self._resolveFacilityVotes(self.currentSeason.seasonNumber)

        # Close game stats file
        self._closeGameStatsFile()

        # Handle season completion
        await self._completeSeasonSimulation()

        logger.info(f"Season {self.currentSeason.seasonNumber} simulation complete")

    async def _simulateRegularSeason(self, resumeFromWeek: int = 0) -> None:
        """Simulate all regular season games.

        Args:
            resumeFromWeek: Skip weeks up to and including this number (already completed).
        """
        strCurrentSeason = 'season{}'.format(self.currentSeason.seasonNumber)

        # On mid-season resume, restore accumulated stats from the DB checkpoint
        # so standings and leaderboards reflect weeks already simulated.
        if resumeFromWeek > 0:
            logger.info(f"Restoring season {self.currentSeason.seasonNumber} stats from week {resumeFromWeek} checkpoint")
            teamManager = self.serviceContainer.getService('team_manager')
            if teamManager:
                teamManager.loadSeasonTeamStats(self.currentSeason.seasonNumber)
            playerManager = self.serviceContainer.getService('player_manager')
            if playerManager:
                playerManager.loadCurrentSeasonStats(self.currentSeason.seasonNumber, currentWeek=resumeFromWeek)
            fantasyTracker = self.serviceContainer.getService('fantasy_tracker')
            if fantasyTracker:
                fantasyTracker.restoreWeekFP(
                    self.currentSeason.seasonNumber, resumeFromWeek
                )
            # Pre-set countdown cache so the API has the correct start time
            # immediately (before the loop reaches the next week)
            nextScheduleIdx = resumeFromWeek  # 0-indexed: schedule[N] = week N+1
            if nextScheduleIdx < len(self.currentSeason.schedule):
                self._cachedNextGameStart = self.currentSeason.schedule[nextScheduleIdx]['startTime']
            # Set currentWeek to the last completed week so API calls during
            # the pre-game wait show the correct week (not 0).
            self.currentSeason.currentWeek = resumeFromWeek
            self.currentSeason.currentWeekText = f'Week {resumeFromWeek}'
            # Clean up orphaned game data from any interrupted week
            # (the next week will replay from scratch with original matchups)
            self._cleanupOrphanedWeekGames(
                self.currentSeason.seasonNumber, resumeFromWeek + 1
            )
            # Reset in-memory Game objects for the interrupted week so games
            # loaded as Final from the DB are replayed instead of skipped.
            interruptedIdx = resumeFromWeek  # 0-indexed schedule position
            if interruptedIdx < len(self.currentSeason.schedule):
                for game in self.currentSeason.schedule[interruptedIdx]['games']:
                    game.status = FloosGame.GameStatus.Scheduled
                    game.homeScore = 0
                    game.awayScore = 0

        for week in self.currentSeason.schedule:
            roundIndex = self.currentSeason.schedule.index(week)  # 0-indexed
            nextWeek = roundIndex + 1
            dayNum = roundIndex // 7 + 1    # 1-indexed day (1–4), used for day-boundary events
            nextWeekText = f'Week {nextWeek}'

            # Skip weeks that were completed before a restart
            if nextWeek <= resumeFromWeek:
                logger.info(f"Skipping {nextWeekText} — already completed before restart")
                continue

            logger.info(f"Simulating {nextWeekText} in {self.timingManager.getModeString()} mode")

            # Select weekly modifier (and pre-roll the rest of this calendar
            # day's slot modifiers so the day's full slate can be announced
            # ahead of time — see getDayModifierSchedule).
            weeklyModifier = self._selectWeeklyModifier(
                self.currentSeason.seasonNumber, nextWeek
            )
            self._ensureDayModifiers(self.currentSeason.seasonNumber, nextWeek)

            # Notify users whose power-ups (Accession / Conscription) just expired
            self._notifyExpiredPowerups(
                self.currentSeason.seasonNumber, nextWeek
            )

            weekStartTime = week['startTime']

            # Pre-set the countdown cache so the /api/season `next_game_start_time`
            # field is correct during the long pre-game await below. Without this,
            # the cache stays None until `await waitForWeekSetup` returns, and the
            # API's fallback path (`getNextGameStartTime(currentWeek)`) lands on
            # `schedule[currentWeek]` which is *next* week — off by one hour.
            # Reproduced after a server restart that lands between rounds with
            # `activeGames` reset to the upcoming week but no cache.
            if self.timingManager._isScheduledMode and not self.timingManager.catchingUp:
                self._cachedNextGameStart = weekStartTime

            # Detect catch-up: current time is past this week's scheduled start
            if self.timingManager._isScheduledMode:
                isBehindSchedule = datetime.datetime.utcnow() > weekStartTime
                if isBehindSchedule and not self.timingManager.catchingUp:
                    logger.info(f"Week {nextWeek}: past scheduled time — entering catch-up mode")
                elif not isBehindSchedule and self.timingManager.catchingUp:
                    logger.info(f"Week {nextWeek}: back on schedule — resuming normal timing")
                    if self.timingManager.mode in (TimingMode.CATCHUP, TimingMode.FAST_CATCHUP):
                        self.timingManager.setMode(TimingMode.SCHEDULED)
                        logger.info(f"Catch-up complete — switched to SCHEDULED mode")
                self.timingManager.catchingUp = isBehindSchedule

            # If no games are currently visible (e.g. after a deploy/restart),
            # show the upcoming slate immediately so the API isn't empty.
            # Skip this when completedWeekGames has the previous week's results
            # — those should stay visible until rollover clears them.
            if not self.currentSeason.activeGames and not self.currentSeason.completedWeekGames:
                self.currentSeason.activeGames = week['games']

            # Wait for rollover BEFORE clearing previous week's results.
            # In scheduled mode this keeps completedWeekGames visible until
            # shortly before the next game start.
            # Cross-day transitions (weeks 8, 15, 22) have ~18-hour gaps;
            # roll over 8 hours early so the next slate shows up the evening before.
            isCrossDayTransition = nextWeek in (8, 15, 22)
            earlyMinutes = 480 if isCrossDayTransition else 15  # 8 hours vs 15 min
            weekSetupTime = weekStartTime - datetime.timedelta(minutes=earlyMinutes)

            # For the very first week, advance currentWeek before the wait so that
            # card equip API targets week 1 (not orphan week 0).
            if self.currentSeason.currentWeek == 0:
                self.currentSeason.currentWeek = nextWeek
                self.currentSeason.currentWeekText = nextWeekText
                # Day 0's rule vote (Aris, the Game Format ballot) opens HERE — the
                # moment the season starts — not at the rollover below. Week 1 is not a
                # cross-day transition, so it only gets the 15-minute setup lead, and
                # 15 minutes is not enough time for the league to vote on opening day's
                # format. Opening here gives the whole run-up from season creation to
                # first kickoff — in prod the season rolls over early Monday morning
                # (startDate anchors to Monday 04:00 UTC) and week 1 kicks at 12:00 ET,
                # so the ballot is up for the morning rather than 15 minutes. Idempotent
                # — the rollover call below no-ops once this window exists.
                self._maybeOpenRuleVote(nextWeek, weekStartTime)

            await self.timingManager.waitForWeekSetup(weekSetupTime)

            # ── Official week transition ──
            # Advance currentWeek AFTER the wait so that between-weeks API calls
            # still see the completed week's fantasy/card data (not the upcoming
            # empty week).  For week 1, this was already set above.
            self.currentSeason.currentWeek = nextWeek
            self.currentSeason.currentWeekText = nextWeekText

            # Cores rule-change vote: open AT the week rollover (right after the setup wait),
            # on the game-day-start weeks (1/8/15/22). Previously it opened BEFORE the wait —
            # the moment the prior day's games ended — so the ballot flashed up the evening
            # before. Opening here means it first appears when the week rolls over the following
            # day, then stays open through the run-up to kickoff (resolved as the day's first
            # game starts, below). Weeks 8/15/22 roll over 8 hours early, so those ballots go up
            # the evening before. Week 1 is handled above (opened at season start instead — its
            # rollover lead is only 15 minutes). Idempotent; never blocks the loop.
            self._maybeOpenRuleVote(nextWeek, weekStartTime)

            # Recompute regular-season pressure blend: prior-season expectations
            # wane over the first ~14 weeks while inSeasonPressure (set by
            # standings/elimination logic) takes over. Playoff weeks set
            # pressureModifier directly elsewhere and are not affected here.
            try:
                teamMgr = self.serviceContainer.getService('team_manager')
                teamMgr.applyRegularSeasonPressureBlend(
                    nextWeek, season=self.currentSeason.seasonNumber,
                )
            except Exception as e:
                logger.warning(f"Pressure blend at week {nextWeek} failed: {e}")

            # Anomaly system weekly tick: applies attention decay,
            # accumulates this week's engagement contributions, advances
            # the state ladder, and recomputes the league-wide aggregate
            # toward the Cracking threshold. Wrapped defensively so a
            # failure in this layer never blocks the actual game loop.
            try:
                from managers.anomalyManager import weeklyTick as anomalyWeeklyTick
                anomalyWeeklyTick(self.currentSeason.seasonNumber, nextWeek)
            except Exception as e:
                logger.warning(f"Anomaly weekly tick at week {nextWeek} failed: {e}")

            # Cache the game start time so REST API returns a stable value on refresh
            if self.timingManager._isScheduledMode and not self.timingManager.catchingUp:
                self._cachedNextGameStart = weekStartTime
            else:
                # Sequential/turbo/catch-up: compute from delays relative to now
                delays = self.timingManager.delays
                gap = delays.get('week_start_wait', 30) + delays.get('game_announcement', 30)
                self._cachedNextGameStart = datetime.datetime.utcnow() + datetime.timedelta(seconds=gap)

            # Rollover: show new week's games, clear previous week's completed data
            self.currentSeason.activeGames = week['games']
            self.currentSeason.completedWeekGames = None

            # Free play-by-play memory from all prior completed games
            self._cleanupCompletedGameMemory(excludeGames=week['games'])

            # Broadcast week start event
            if BROADCASTING_AVAILABLE and broadcaster.is_enabled():
                nextStartIso = self._cachedNextGameStart.isoformat() + 'Z' if self._cachedNextGameStart else None
                modInfo = {
                    "name": weeklyModifier,
                    "displayName": self.MODIFIER_DISPLAY.get(weeklyModifier, weeklyModifier.title()),
                    "description": self.MODIFIER_DESCRIPTIONS.get(weeklyModifier, ""),
                } if weeklyModifier else None
                week_event = SeasonEvent.weekStart(
                    seasonNumber=self.currentSeason.seasonNumber,
                    weekNumber=self.currentSeason.currentWeek,
                    gamesCount=len(week.get('games', [])),
                    weekText=self.currentSeason.currentWeekText,
                    modifier=weeklyModifier,
                    modifierInfo=modInfo,
                    nextGameStartTime=nextStartIso,
                )
                broadcaster.broadcast_sync('season', week_event)
                self._publishScheduleNews(
                    'week_start',
                    f'{self.currentSeason.currentWeekText} begins, '
                    f'{len(week.get("games", []))} games scheduled',
                )

            # Resolve duplicate-effect equipped sets that pre-date the
            # no-duplicate rule. Modifies the just-completed week's
            # equipped rows so carry-forward later (at game start) only
            # propagates one copy per effectName per user. Runs at week
            # start, not at the game-start lock — users see the change
            # before their cards lock.
            try:
                self._resolveDuplicateEquippedEffects(
                    self.currentSeason.seasonNumber,
                    sourceWeek=self.currentSeason.currentWeek - 1,
                )
            except Exception as _e:
                logger.warning(f"Duplicate-effect resolution failed: {_e}")

            # Open the FA voting window mid-season once Week 22 arrives (the
            # Front Office's activation threshold). Fans can rank projected
            # FAs — walk-year rostered players + existing FAs — from here
            # through end of regular season. Idempotent.
            try:
                from constants import GM_ACTIVE_WEEK
                if self.currentSeason.currentWeek >= GM_ACTIVE_WEEK and not getattr(self, '_faWindowOpen', False):
                    await self._openFaVotingWindowMidSeason()
            except Exception as _e:
                logger.warning(f"Could not open FA window mid-season: {_e}")

            # Retirement announcements fire at the START of week GM_ACTIVE_WEEK —
            # the moment the Front Office opens — so fans don't burn resign votes
            # on players who'll retire and have time to plan FA-ballot replacements.
            # Gated `>= week` + a persisted once-per-season marker (the fan-count
            # snapshot), NOT `== week`, so a restart/deploy at or after week 22
            # still fires it (on the replayed week 22 or the next week) without
            # re-rolling retirements. _evaluateRetirementCandidates re-rolls every
            # not-yet-flagged player, so running it more than once per season would
            # inflate the retiring set — the marker prevents that.
            try:
                from constants import GM_ACTIVE_WEEK as _GM_ACTIVE_WEEK
                if self.currentSeason.currentWeek >= _GM_ACTIVE_WEEK and not self._frontOfficeProcessed():
                    self._evaluateRetirementCandidates()
                    # Retire long-tenured free agents now too (preIncrement=True
                    # anticipates the offseason FA-years bump) so the FA pool is
                    # FINALIZED at front-office open — retirees gone, not just
                    # flagged. With rostered retirements flagged and the rookie
                    # class known since season start, the supply picture is complete.
                    faHighlights = self.currentSeason.leagueHighlights if hasattr(self.currentSeason, 'leagueHighlights') else []
                    self.playerManager._processFreeAgentRetirements(
                        self.currentSeason.seasonNumber, faHighlights, preIncrement=True
                    )
                    # Top up any thin position into the FA pool BEFORE fans ballot
                    # the FA draft (so they can rank the new players).
                    self._ensurePositionSupply(reason='week-22 supply check')
                    # CRITICAL ordering: commit willRetire (set in-memory above) to
                    # the DB BEFORE the fan snapshot. The snapshot is the once-per-
                    # season marker and commits IMMEDIATELY on its own session, but
                    # willRetire otherwise wouldn't reach the DB until the week-end
                    # checkpoint (days later in scheduled mode). A redeploy in that
                    # gap would load will_retire=False for everyone while the marker
                    # survived and blocked re-rolling — leaving the season with no
                    # retirements and no way to re-decide them. Persist first.
                    self.playerManager.savePlayerData()
                    # LAST step: stamp the once-per-season marker. Everything above is
                    # what it protects from re-running (retirements re-roll if it does).
                    # This used to be _snapshotActiveFanCounts(), which froze per-team
                    # fan counts for the GM vote threshold and doubled as the marker.
                    # Binding fan votes are gone, so the counts had no reader left.
                    self._markFrontOfficeProcessed()
            except Exception as _e:
                logger.warning(f"Front Office open (retirements) failed: {_e}")

            # HoF ballot seed opens at the START of week GM_ACTIVE_WEEK (with the
            # retirements above), not at week's end — so the Hall of Fame voting list
            # is present the MOMENT retirements are announced. Gated `>= week`
            # (idempotent, NOT the once-only retirement marker) so a deploy after week
            # 22 still seeds it; runs AFTER the retirement block so the willRetire set
            # is already populated (willRetire is persisted, so it survives a redeploy).
            #
            # The per-team 3-candidate coach slate is NO LONGER generated here. Fans no
            # longer vote to fire and hire coaches — the autonomous Front Office makes
            # that call and backfills via teamManager.generateCoach() directly, so the
            # slates had no remaining reader (getCoachCandidates had no callers, no API
            # endpoint served them, and the frontend kept only an orphan type field).
            # They were not free: each slate drew 3 names per team from the SAME
            # unusedNames pool the players use, 72 a season, and unhired candidates
            # never recycled their names (only retired players do, via
            # _recyclePlayerName). That burned the ~789-name seed pool dry in about 11
            # seasons, after which player generation silently failed —
            # ensurePositionSupply could not create the free agents it knew were
            # missing, the FA draft force-ended with empty roster slots, and playGame
            # then hit a None roster slot. Measured in a 14-season sim: 1,104 coaches
            # and 1,080 candidate rows against 262 players, with unused_names at 0.
            try:
                from constants import GM_ACTIVE_WEEK as _GM_ACTIVE_WEEK
                if self.currentSeason.currentWeek >= _GM_ACTIVE_WEEK:
                    self._seedHofBallot()
            except Exception as _e:
                logger.warning(f"Front Office open (HoF seed) failed: {_e}")

            for game in range(0,len(self.currentSeason.activeGames)):
                self.currentSeason.activeGames[game].leagueHighlights = self.currentSeason.leagueHighlights
                # Refresh ELO from current team values (stale since schedule creation)
                self.currentSeason.activeGames[game].homeTeamElo = self.currentSeason.activeGames[game].homeTeam.elo
                self.currentSeason.activeGames[game].awayTeamElo = self.currentSeason.activeGames[game].awayTeam.elo
                self.currentSeason.activeGames[game].calculateWinProbability()

            # Add league highlight for week starting
            if hasattr(self.currentSeason, 'leagueHighlights'):
                self.currentSeason.leagueHighlights.insert(0, {
                    'event': {'text': f'{self.currentSeason.currentWeekText} Starting Soon...'}
                })

            # Fire pre-game reminder 15 min before games start — bot uses this for
            # DM reminders, since week_start may have fired hours earlier on
            # cross-day transitions.
            await self._firePreGameReminder(weekStartTime, self.currentSeason.currentWeek,
                                            self.currentSeason.currentWeekText,
                                            len(week.get('games', [])))

            # Wait for games to start
            await self.timingManager.waitForGamesStart(weekStartTime)

            # Cores rule-change vote resolves right AS the day's games start — voting
            # stays open through the whole pre-game run-up, the winning rule applies to
            # the shared gameRules before any game plays. No-op unless a vote is open.
            self._resolveRuleVote()

            # Clear cached countdown — games are starting now
            self._cachedNextGameStart = None

            # Clear previous week's in-memory FP accumulator so it doesn't
            # bleed into the new week's snapshot overlay
            fantasyTracker = self.serviceContainer.getService('fantasy_tracker')
            if fantasyTracker:
                fantasyTracker.clearWeekFP()

            # Auto-carry-forward equipped cards for all users, then lock
            try:
                from database.connection import get_session as _getSession
                from database.repositories.card_repositories import EquippedCardRepository
                from database.models import FantasyRoster
                lockSession = _getSession()
                seasonNum = self.currentSeason.seasonNumber
                currentWeek = self.currentSeason.currentWeek
                equippedRepo = EquippedCardRepository(lockSession)
                if currentWeek > 1:
                    self._carryForwardEquippedCards(
                        lockSession, equippedRepo, seasonNum, currentWeek
                    )
                equippedRepo.lockAllForWeek(seasonNum, currentWeek)
                # Auto-lock rosters that have all slots filled
                unlocked = lockSession.query(FantasyRoster).filter_by(
                    season=self.currentSeason.seasonNumber, is_locked=False
                ).all()
                # Auto-lock anyone with at least the ROSTER_MIN_PLAYERS
                # floor. Previously required all 6 slots filled, so a
                # partially-set-up roster silently forfeited the week.
                from constants import ROSTER_MIN_PLAYERS as _ROSTER_MIN
                # Fusion: the roster IS the equipped cards, so a user's lineup is
                # legal (auto-lockable) when their equipped cards fill >= ROSTER_MIN
                # distinct slots — not FantasyRosterPlayer rows. Key off slot_number
                # (always set; the position-slot string is wired in Phase 6/7) so
                # distinct slot_numbers == distinct filled positions. Batch once.
                allEquippedThisWeek = equippedRepo.getAllForWeek(seasonNum, currentWeek)
                slotsByUser = {}
                for eq in allEquippedThisWeek:
                    slotsByUser.setdefault(eq.user_id, set()).add(eq.slot_number)
                for roster in unlocked:
                    filledSlots = slotsByUser.get(roster.user_id, set())
                    if len(filledSlots) >= _ROSTER_MIN:
                        roster.is_locked = True
                        roster.locked_at = datetime.datetime.utcnow()
                        # Fusion: no points_at_lock offset (weekly-sum scoring) and no
                        # All-Pro swap replay (swaps retired) — just lock the row.
                        logger.info(f"Auto-locked roster for user {roster.user_id}")
                lockSession.commit()
                lockSession.close()
            except Exception as e:
                logger.error(f"Failed to auto-lock cards/rosters for week {self.currentSeason.currentWeek}: {e}")

            # Auto-pick favorites for users who opted in
            try:
                self._autoPickFavorites(week['games'])
            except Exception as e:
                logger.error(f"Auto-pick favorites failed for week {self.currentSeason.currentWeek}: {e}")

            # Add game start highlight
            if hasattr(self.currentSeason, 'leagueHighlights'):
                self.currentSeason.leagueHighlights.insert(0, {
                    'event': {'text': f'{self.currentSeason.currentWeekText} Start'}
                })

            # Simulate games in the week concurrently (like original)
            weekGames = week['games']

            # Create tasks for all games in the week to run concurrently
            gameTasks = [self._simulateGame(game, gameIndex=i) for i, game in enumerate(weekGames)]

            # Start periodic leaderboard broadcast during games
            leaderboardTask = asyncio.ensure_future(self._broadcastLeaderboardPeriodically())

            # Wait for all games in the week to complete concurrently
            await asyncio.gather(*gameTasks)

            # Stop periodic leaderboard broadcast
            leaderboardTask.cancel()
            try:
                await leaderboardTask
            except asyncio.CancelledError:
                pass

            # Clear active games so roster swaps are unlocked between weeks.
            # Keep a reference so the API can still serve them until next week.
            self.currentSeason.completedWeekGames = self.currentSeason.activeGames
            self.currentSeason.activeGames = None

            # Cache next game start time immediately so countdown is available
            # before _onWeekComplete finishes its DB processing
            nextStart = self.getNextGameStartTime(self.currentSeason.currentWeek)
            if nextStart:
                self._cachedNextGameStart = nextStart

            # Post-week processing (matches original floosball.py lines 688-699)
            self._updateWeeklyStats()
            self._updateStandings()

            # Update player performance ratings for the week
            self._updatePlayerPerformanceRatings(self.currentSeason.currentWeek)

            # Sort players and defenses (matches original)
            self.playerManager.sortPlayersByPosition()
            teamManager = self.serviceContainer.getService('team_manager')
            if teamManager:
                teamManager.sortDefenses()

            # Update playoff picture and check for clinches (matches original)
            self.updatePlayoffPicture()
            newClinchEvents = self.checkForClinches()

            # Broadcast clinch/elimination events and award Floobits for team achievements
            from constants import CLINCH_PLAYOFF_REWARD, CLINCH_TOPSEED_REWARD
            for event in newClinchEvents:
                self.currentSeason.leagueHighlights.insert(0, {'event': {'text': event['text']}})
                if BROADCASTING_AVAILABLE and broadcaster.is_enabled() and LeagueNewsEvent:
                    await broadcaster.broadcast_season_event(LeagueNewsEvent.leagueNews(event['text']))
                if event['type'] == 'clinch_playoff':
                    self._awardFavoriteTeamBonus(
                        event['teamId'], CLINCH_PLAYOFF_REWARD, 'team_clinch_playoff',
                        description=f'Favorite team clinched playoffs (Week {self.currentSeason.currentWeek})',
                        season=self.currentSeason.seasonNumber, week=self.currentSeason.currentWeek)
                elif event['type'] == 'clinch_topseed':
                    self._awardFavoriteTeamBonus(
                        event['teamId'], CLINCH_TOPSEED_REWARD, 'team_clinch_topseed',
                        description=f'Favorite team clinched #1 seed (Week {self.currentSeason.currentWeek})',
                        season=self.currentSeason.seasonNumber, week=self.currentSeason.currentWeek)

            # Broadcast standings with updated clinch/elimination flags
            # Use await directly (we're in an async method) so it fires immediately, not as a deferred task
            if BROADCASTING_AVAILABLE and broadcaster.is_enabled() and StandingsEvent and LeagueResponseBuilder:
                standingsData = []
                for league in self.leagueManager.leagues:
                    standingsData.append({
                        'name': league.name,
                        'standings': LeagueResponseBuilder.buildStandingsResponse(league.teamList)['standings']
                    })
                await broadcaster.broadcast_season_event(StandingsEvent.standingsUpdate(standings=standingsData))

            self._checkRecords()

            # Additional record checks (matches original)
            self.recordsManager.checkCareerRecords()
            self.recordsManager.checkSeasonRecords(self.currentSeason.seasonNumber)

            # Accumulate fatigue after each week
            self._accumulateFatigue()

            # Mental-attribute-driven form shift: hot teams w/ low discipline
            # drift toward complacency, cold teams w/ high discipline mount a
            # professional resolve. Runs alongside fatigue on the weekly hook
            # so the effect compounds gradually across the season.
            self._applyMidseasonFormShift(self.currentSeason.currentWeek)
            # Attitude drifts with playing experience: winning trends a
            # roster toward leadership, losing toward toxicity. Feeds back
            # into the form-shift composites so a season-long arc shapes
            # how teams respond to streaks and standings.
            self._driftAttitudes(self.currentSeason.currentWeek)
            # Locker-room contagion: high-attitude (leader) teammates lift
            # confidence/determination across the roster; low-attitude (toxic)
            # teammates drag everyone down. The mechanism that makes attitude
            # itself a load-bearing attribute (it has no direct game-sim use,
            # so without this it'd only matter via the form-shift composites).
            self._propagateAttitudeContagion()
            # Track how many consecutive weeks each team has held their
            # current form state — feeds the regression-to-mean weakening
            # in _applyFormState.
            self._updateTeamFormHistory()
            # Continuous form oscillation: pull each club back toward its own
            # level, hard enough to overshoot, so seasons develop arcs instead
            # of every team playing at one fixed level for 28 weeks.
            self._updateTeamFormOffsets()

            # Checkpoint: save team + player stats BEFORE advancing the week
            # checkpoint.  If the process dies between here and _onWeekComplete,
            # the week replays on restart (stats get overwritten — safe).
            # Old order (checkpoint first, stats later) caused a lost week on
            # crash: checkpoint said "done" but stats were never persisted.
            self._saveTeamSeasonStatsToDatabase()
            playerManager = self.serviceContainer.getService('player_manager')
            if playerManager:
                playerManager.savePlayerData()

            # NOW advance the week checkpoint — must be LAST so a crash before
            # this point causes the week to replay rather than be silently skipped.
            await self._onWeekComplete(self.currentSeason.currentWeek, in_playoffs=False)

            # Add game end highlight
            if hasattr(self.currentSeason, 'leagueHighlights'):
                self.currentSeason.leagueHighlights.insert(0, {
                    'event': {'text': f'{self.currentSeason.currentWeekText} End'}
                })

            # Wait after week completes
            await self.timingManager.waitAfterWeek()

            # Broadcast day-boundary events after the last round of each day
            isLastRoundOfDay = (roundIndex % 7 == 6)
            if isLastRoundOfDay and BROADCASTING_AVAILABLE and broadcaster.is_enabled() and SeasonEvent:
                if dayNum < 4:
                    await broadcaster.broadcast_season_event(SeasonEvent.dayComplete(dayNum))
                else:
                    await broadcaster.broadcast_season_event(SeasonEvent.regularSeasonComplete())

            # Send day-end email reports (skip during catch-up / fast modes).
            # Offload to a worker thread: sending loops over every opted-in user
            # with a throttle sleep + blocking Resend HTTP call each, which would
            # otherwise freeze the event loop (and the API, same process) for the
            # whole batch. The method only READS shared state + writes to Resend
            # via its own DB session, so a background thread is safe. Fire-and-
            # forget — the executor runs it to completion even if we drop the
            # future, and the inter-day wait gives it idle time to finish.
            if isLastRoundOfDay and not self.timingManager.catchingUp:
                firstRound = roundIndex - 6  # 0-indexed first round of this day
                weekRange = list(range(firstRound + 1, roundIndex + 2))  # 1-indexed week numbers
                asyncio.get_running_loop().run_in_executor(
                    None, self._sendDayEndEmails,
                    self.currentSeason.seasonNumber, dayNum, weekRange,
                )

        # Catch-up is done — switch to SCHEDULED so playoffs run at normal speed
        if self.timingManager.mode in (TimingMode.CATCHUP, TimingMode.FAST_CATCHUP):
            self.timingManager.setMode(TimingMode.SCHEDULED)
            logger.info("Catch-up complete at end of regular season — switched to SCHEDULED mode")
        self.timingManager.catchingUp = False

    async def _simulatePlayoffs(self, resumeFromRound: int = 1, restoredState: Optional[dict] = None) -> None:
        """Simulate playoff games"""
        logger.info("Starting playoff simulation")


        # Simulate playoff rounds
        await self._simulatePlayoffRounds(resumeFromRound=resumeFromRound, restoredState=restoredState)

    async def _simulateGame(self, game: FloosGame.Game, gameIndex: int = -1) -> None:
        """Simulate a single game"""

        try:
            # Create game instance with timing manager
            gameInstance = game

            # Track games simulated this season
            self.games_simulated_this_season += 1

            # Wire fantasy tracker callback for each player so FP generation
            # flows through FantasyTracker (updates both _weekFP and gameStatsDict).
            # Skip for playoff games — fantasy is archived once the regular season ends,
            # so playoff FP should NOT accumulate (keeps the leaderboard frozen and the
            # bot's end-of-round reports from resurrecting fantasy data).
            isPlayoffGame = bool(getattr(gameInstance, 'isPlayoff', False))
            fantasyTracker = self.serviceContainer.getService('fantasy_tracker')
            if fantasyTracker and not isPlayoffGame:
                for team in [gameInstance.homeTeam, gameInstance.awayTeam]:
                    for player in team.rosterDict.values():
                        if player:
                            pid = player.id
                            def _makeFpCallback(_pid, _game, _ft):
                                def cb(pts):
                                    _ft.addPlayerPoints(_pid, pts)
                                    if _game.currentQuarter >= 4:
                                        _ft.addPlayerQ4Points(_pid, pts)
                                return cb
                            player.stat_tracker._on_fantasy_points = _makeFpCallback(
                                pid, gameInstance, fantasyTracker
                            )
                            def _makeScoreCallback(_pid, _game, _ft):
                                def cb(_kind):
                                    if _game.currentQuarter >= 4:
                                        _ft.addPlayerQ4Score(_pid)
                                return cb
                            player.stat_tracker._on_scoring_play = _makeScoreCallback(
                                pid, gameInstance, fantasyTracker
                            )

            # Simulate the game
            self._applyChaosRulesIfCritical(gameInstance)
            await gameInstance.playGame()

            # Clear fantasy tracker callbacks after game
            if fantasyTracker:
                for team in [gameInstance.homeTeam, gameInstance.awayTeam]:
                    for player in team.rosterDict.values():
                        if player:
                            player.stat_tracker._on_fantasy_points = None

            # Save game to database. Note: gameStatsDict['fantasyPoints'] is already
            # zeroed by _accumulatePostgameStats inside playGame(), but each player's
            # _lastGameFantasyPoints preserves the value for DB persistence.
            if DB_IMPORTS_AVAILABLE and USE_DATABASE and self.game_repo:
                self._saveGameToDatabase(gameInstance)

            # Update team records
            self._updateTeamRecords(gameInstance)

            # Process post-game statistics (record-checking, team stat accumulation)
            self.recordsManager.processPostGameStats(gameInstance)

            # Log detailed game stats
            self._logGameStats(gameInstance)

            # Update ELO ratings based on game result using pre-game win probability
            teamManager = self.serviceContainer.getService('team_manager')
            if teamManager and hasattr(gameInstance, 'winningTeam') and gameInstance.winningTeam:
                _eloHome, _eloAway = gameInstance.format.eloScores(gameInstance)
                teamManager.updateEloAfterGame(
                    gameInstance.homeTeam,
                    gameInstance.awayTeam,
                    _eloHome,
                    _eloAway,
                    gameInstance.winningTeam,
                    getattr(gameInstance, 'preGameHomeWinProbability', None),
                    getattr(gameInstance, 'preGameAwayWinProbability', None)
                )

            # Broadcast standings update after ELO has been updated
            if BROADCASTING_AVAILABLE and broadcaster.is_enabled() and StandingsEvent and LeagueResponseBuilder:
                standingsData = []
                for league in self.leagueManager.leagues:
                    standingsData.append({
                        'name': league.name,
                        'standings': LeagueResponseBuilder.buildStandingsResponse(league.teamList)['standings']
                    })
                await broadcaster.broadcast_season_event(StandingsEvent.standingsUpdate(standings=standingsData))

            # Check for records. Snapshot first so a break can be diffed out and
            # published to the news feed.
            _recordsBefore = self._snapshotRecords()
            self.recordsManager.checkPlayerGameRecords()
            self.recordsManager.checkTeamGameRecords(gameInstance)
            self._publishGameNews(gameInstance, _recordsBefore)

            # Resolve pick-em picks for this game immediately
            if gameIndex >= 0 and getattr(gameInstance, 'winningTeam', None):
                self._resolvePickEmGame(gameIndex, gameInstance)

        except Exception as e:
            tb = traceback.format_exc()
            logger.error(
                f"Error simulating game ({game.homeTeam.name} vs {game.awayTeam.name}): {e}\n"
                + tb
            )
            # Persist a crash dump to the volume so we can post-mortem even
            # after the rotating in-app log overwrites the trail. Best-effort —
            # never let dump failure block the force-finish below.
            try:
                self._writeGameCrashDump(game, e, tb)
            except Exception as dumpErr:
                logger.warning(f"Failed to write game crash dump: {dumpErr}")
            # Force-finish the game so it doesn't stay stuck as "Live" forever
            if getattr(game, 'status', None) != FloosGame.GameStatus.Final:
                game.status = FloosGame.GameStatus.Final
                tiedAtCrash = (game.homeScore == game.awayScore)
                if not getattr(game, 'winningTeam', None):
                    if game.homeScore > game.awayScore:
                        game.winningTeam = game.homeTeam
                        game.losingTeam = game.awayTeam
                    elif game.awayScore > game.homeScore:
                        game.winningTeam = game.awayTeam
                        game.losingTeam = game.homeTeam
                    else:
                        # Tied at crash time. Mark home as "winningTeam" for
                        # the legacy fields that demand a value, but apply
                        # a tie in the standings below — don't arbitrarily
                        # credit one team with a win they didn't earn.
                        game.winningTeam = game.homeTeam
                        game.losingTeam = game.awayTeam
                try:
                    # Update season win/loss/tie records.
                    if getattr(game, 'isRegularSeasonGame', False) and getattr(game, 'winningTeam', None):
                        if tiedAtCrash:
                            game.homeTeam.seasonTeamStats.setdefault('ties', 0)
                            game.awayTeam.seasonTeamStats.setdefault('ties', 0)
                            game.homeTeam.seasonTeamStats['ties'] += 1
                            game.awayTeam.seasonTeamStats['ties'] += 1
                        else:
                            game.winningTeam.seasonTeamStats.setdefault('wins', 0)
                            game.losingTeam.seasonTeamStats.setdefault('losses', 0)
                            game.winningTeam.seasonTeamStats['wins'] += 1
                            game.losingTeam.seasonTeamStats['losses'] += 1
                        # Division record has to survive the recovery path too, or a
                        # crashed division game silently drops out of the first playoff
                        # tiebreaker while still counting in the overall record.
                        _hd = getattr(game.homeTeam, 'division', None)
                        _isDiv = bool(_hd) and _hd == getattr(game.awayTeam, 'division', None)
                        # team.league is the league NAME (a string), not an object.
                        _hl = getattr(game.homeTeam, 'league', None)
                        _al = getattr(game.awayTeam, 'league', None)
                        _isLg = _isDiv or (bool(_hl) and _hl == _al)
                        if tiedAtCrash:
                            for _t in (game.homeTeam, game.awayTeam):
                                _s = _t.seasonTeamStats
                                if _isDiv: _s['divTies'] = _s.get('divTies', 0) + 1
                                if _isLg: _s['lgTies'] = _s.get('lgTies', 0) + 1
                        else:
                            _w, _l = game.winningTeam.seasonTeamStats, game.losingTeam.seasonTeamStats
                            if _isDiv:
                                _w['divWins'] = _w.get('divWins', 0) + 1
                                _l['divLosses'] = _l.get('divLosses', 0) + 1
                            if _isLg:
                                _w['lgWins'] = _w.get('lgWins', 0) + 1
                                _l['lgLosses'] = _l.get('lgLosses', 0) + 1
                    self._updateTeamRecords(game)
                except Exception as recordErr:
                    logger.warning(f"Failed to update records after game error recovery: {recordErr}")

    def _writeGameCrashDump(self, game, err, tb: str) -> None:
        """Persist a game's state at exception time to the data volume so
        we can post-mortem even after the rotating in-app log overwrites
        the original traceback. Keeps the most recent 50 dumps; older ones
        get pruned so the volume doesn't fill up.
        """
        import datetime as _dt
        import json as _json
        dumpDir = '/data/crashes'
        if not os.path.isdir('/data'):
            # Local dev — fall back to project-relative logs dir.
            dumpDir = os.path.join(os.getcwd(), 'logs', 'crashes')
        os.makedirs(dumpDir, exist_ok=True)

        ts = _dt.datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
        gid = getattr(game, 'dbId', None) or getattr(game, 'id', 'unknown')
        path = os.path.join(dumpDir, f'game_{gid}_{ts}.txt')

        homeTeamName = getattr(game.homeTeam, 'name', '?')
        awayTeamName = getattr(game.awayTeam, 'name', '?')
        feedTail = []
        for entry in (getattr(game, 'gameFeed', None) or [])[:25]:
            try:
                if isinstance(entry, dict):
                    if 'play' in entry:
                        p = entry['play']
                        feedTail.append({
                            'kind': 'play',
                            'quarter': getattr(p, 'quarter', None),
                            'time': getattr(p, 'timeRemaining', None),
                            'result': str(getattr(p, 'playResult', None)),
                            'text': getattr(p, 'playText', None),
                        })
                    elif 'event' in entry:
                        feedTail.append({'kind': 'event', 'event': entry['event']})
            except Exception:
                continue

        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(f"=== Game crash dump ===\n")
            fh.write(f"timestamp: {ts}\n")
            fh.write(f"game_id (dbId): {gid}\n")
            fh.write(f"matchup: {awayTeamName} @ {homeTeamName}\n")
            fh.write(f"score: away={getattr(game, 'awayScore', '?')} home={getattr(game, 'homeScore', '?')}\n")
            fh.write(f"quarter: {getattr(game, 'currentQuarter', '?')}  clock: {getattr(game, 'gameClockSeconds', '?')}\n")
            fh.write(f"isOvertime: {getattr(game, 'isOvertime', '?')}  otPeriod: {getattr(game, 'otPeriod', '?')}\n")
            fh.write(f"otFirstPossComplete: {getattr(game, 'otFirstPossComplete', '?')}  "
                     f"otSecondPossComplete: {getattr(game, 'otSecondPossComplete', '?')}\n")
            fh.write(f"totalPlays: {getattr(game, 'totalPlays', '?')}\n")
            fh.write(f"offense: {getattr(getattr(game, 'offensiveTeam', None), 'abbr', '?')}  "
                     f"defense: {getattr(getattr(game, 'defensiveTeam', None), 'abbr', '?')}\n")
            fh.write(f"down: {getattr(game, 'down', '?')}  "
                     f"yardsToEndzone: {getattr(game, 'yardsToEndzone', '?')}  "
                     f"yardsToFirstDown: {getattr(game, 'yardsToFirstDown', '?')}\n")
            fh.write(f"\nexception: {type(err).__name__}: {err}\n\n")
            fh.write("traceback:\n")
            fh.write(tb)
            fh.write("\nrecent_feed:\n")
            fh.write(_json.dumps(feedTail, indent=2, default=str))
            fh.write("\n")

        # Prune to last 50 dumps so the volume doesn't grow unbounded.
        try:
            files = sorted(
                (os.path.join(dumpDir, f) for f in os.listdir(dumpDir) if f.startswith('game_') and f.endswith('.txt')),
                key=os.path.getmtime,
            )
            for old in files[:-50]:
                try:
                    os.remove(old)
                except OSError:
                    pass
        except OSError:
            pass

    def _openGameStatsFile(self) -> None:
        """Open file for game statistics logging"""
        try:
            filename = f"logs/game_stats_season_{self.currentSeason.seasonNumber}.txt"
            os.makedirs(os.path.dirname(filename), exist_ok=True)
            self.game_stats_file = open(filename, 'w', encoding='utf-8')
            self.game_stats_file.write(f"GAME STATISTICS - SEASON {self.currentSeason.seasonNumber}\n")
            self.game_stats_file.write(f"{'='*80}\n\n")
            logger.info(f"Opened game stats file: {filename}")
        except Exception as e:
            logger.error(f"Failed to open game stats file: {e}")
            self.game_stats_file = None
    
    def _closeGameStatsFile(self) -> None:
        """Close game statistics file"""
        try:
            if self.game_stats_file:
                self.game_stats_file.write(f"\n{'='*80}\n")
                self.game_stats_file.write(f"END OF SEASON {self.currentSeason.seasonNumber}\n")
                self.game_stats_file.close()
                self.game_stats_file = None
                logger.info("Closed game stats file")
        except Exception as e:
            logger.error(f"Failed to close game stats file: {e}")
    
    def _logGameStats(self, game: FloosGame.Game) -> None:
        """Log detailed game statistics to file"""
        if not self.game_stats_file:
            return
            
        try:
            # Get game data which calculates yards
            gameData = game.getGameData()
            homeStats = gameData['homeTeam']
            awayStats = gameData['awayTeam']
            
            # Write to file instead of logger
            f = self.game_stats_file
            
            # Basic game info
            f.write(f"\n{'='*80}\n")
            f.write(f"GAME COMPLETE: {game.awayTeam.abbr} @ {game.homeTeam.abbr}\n")
            f.write(f"FINAL SCORE: {game.awayTeam.abbr} {game.awayScore} - {game.homeTeam.abbr} {game.homeScore}\n")
            
            # Quarter scores
            f.write(f"  Q1: {game.awayScoreQ1}-{game.homeScoreQ1}  |  Q2: {game.awayScoreQ2}-{game.homeScoreQ2}  |  Q3: {game.awayScoreQ3}-{game.homeScoreQ3}  |  Q4: {game.awayScoreQ4}-{game.homeScoreQ4}")
            if game.awayScoreOT > 0 or game.homeScoreOT > 0:
                f.write(f"  |  OT: {game.awayScoreOT}-{game.homeScoreOT}")
            f.write("\n")
            
            # Team stats comparison
            f.write(f"\nTEAM STATISTICS:\n")
            f.write(f"{'Stat':<25} {game.awayTeam.abbr:>10} {game.homeTeam.abbr:>10}\n")
            f.write(f"{'-'*45}\n")
            
            # Basic game stats
            f.write(f"{'Total Plays':<25} {awayStats['totalPlays']:>10} {homeStats['totalPlays']:>10}\n")
            f.write(f"{'First Downs':<25} {awayStats['1stDowns']:>10} {homeStats['1stDowns']:>10}\n")
            f.write(f"{'Turnovers':<25} {awayStats['turnovers']:>10} {homeStats['turnovers']:>10}\n")
            
            # Offensive stats
            f.write(f"{'Pass Yards':<25} {awayStats['offense']['passYards']:>10} {homeStats['offense']['passYards']:>10}\n")
            f.write(f"{'Rush Yards':<25} {awayStats['offense']['rushYards']:>10} {homeStats['offense']['rushYards']:>10}\n")
            f.write(f"{'Total Yards':<25} {awayStats['offense']['totalYards']:>10} {homeStats['offense']['totalYards']:>10}\n")
            f.write(f"{'Pass TDs':<25} {awayStats['offense']['passTds']:>10} {homeStats['offense']['passTds']:>10}\n")
            f.write(f"{'Rush TDs':<25} {awayStats['offense']['runTds']:>10} {homeStats['offense']['runTds']:>10}\n")
            f.write(f"{'Field Goals':<25} {awayStats['offense']['fgs']:>10} {homeStats['offense']['fgs']:>10}\n")
            
            # Defensive stats
            f.write(f"{'Sacks':<25} {awayStats['sacks']:>10} {homeStats['sacks']:>10}\n")
            f.write(f"{'Interceptions':<25} {game.awayTeam.gameDefenseStats.get('ints', 0):>10} {game.homeTeam.gameDefenseStats.get('ints', 0):>10}\n")
            f.write(f"{'Fumbles Recovered':<25} {game.awayTeam.gameDefenseStats.get('fumRec', 0):>10} {game.homeTeam.gameDefenseStats.get('fumRec', 0):>10}\n")
            
            # Team ratings
            f.write(f"\nTEAM RATINGS:\n")
            f.write(f"{'Offense Rating':<25} {game.awayTeam.offenseRating:>10} {game.homeTeam.offenseRating:>10}\n")
            f.write(f"{'Defense Rating':<25} {game.awayTeam.defenseOverallRating:>10} {game.homeTeam.defenseOverallRating:>10}\n")
            f.write(f"{'Overall Rating':<25} {game.awayTeam.overallRating:>10} {game.homeTeam.overallRating:>10}\n")
            
            f.write(f"{'='*80}\n\n")
            
            # Flush to ensure it's written
            f.flush()
            
        except Exception as e:
            logger.error(f"Error logging game stats: {e}")
    
    async def _broadcastLeaderboardPeriodically(self, interval: int = 10):
        """Broadcast leaderboard data every `interval` seconds while games are active."""
        while True:
            await asyncio.sleep(interval)
            self._broadcastLeaderboardUpdate()

    def _broadcastLeaderboardUpdate(self):
        """Compute and broadcast current leaderboard via WebSocket."""
        if not BROADCASTING_AVAILABLE or not broadcaster.is_enabled():
            return
        try:
            from api.main import _computeLeaderboardData
            data = _computeLeaderboardData()
            event = {
                'event': 'leaderboard_update',
                'leaderboard': data.get('leaderboard', []),
                'season': data.get('season'),
                'week': self.currentSeason.currentWeek if self.currentSeason else 0,
            }
            broadcaster.broadcast_sync('season', event)
        except Exception as e:
            logger.warning(f"Leaderboard broadcast failed: {e}")
            import traceback
            logger.debug(traceback.format_exc())

    async def _onWeekComplete(self, week: int, in_playoffs: bool, playoff_round: Optional[str] = None) -> None:
        """Called after each week completes - triggers state save and card effect processing"""
        if self.stateUpdateCallback:
            await self.stateUpdateCallback(
                current_season=self.currentSeason.seasonNumber,
                current_week=week,
                in_playoffs=in_playoffs,
                playoff_round=playoff_round
            )

        # Bank FP from in-memory accumulator to WeeklyPlayerFP DB table (regular season only)
        if not in_playoffs:
            fantasyTracker = self.serviceContainer.getService('fantasy_tracker')
            if fantasyTracker:
                fantasyTracker.bankWeek(self.currentSeason.seasonNumber, week)

        # (Weekly roster-swap grant retired with the swap system in the fusion.)

        # Process card effects for this week (regular season only)
        if not in_playoffs:
            self._processWeekCardEffects(self.currentSeason.seasonNumber, week)
            # Card bonuses just landed in WeeklyCardBonus — drop the cached
            # snapshot so downstream consumers (leaderboard prizes, FP payout,
            # achievements) recompute a weekTotal that includes them.
            _ft = self.serviceContainer.getService('fantasy_tracker')
            if _ft:
                _ft.invalidateSnapshotCache()

        # Award weekly leaderboard prizes (after card effects are finalized)
        if not in_playoffs:
            self._awardWeeklyLeaderboardPrizes(self.currentSeason.seasonNumber, week)

        # Award FP-based participation Floobits
        if not in_playoffs:
            self._awardWeeklyFpFloobits(self.currentSeason.seasonNumber, week)

        # Card Showcase weekly dividend (regular season only) — the live showcase
        # is re-graded each week and pays Floobits scaled by its score.
        if not in_playoffs:
            self._awardShowcaseDividends(self.currentSeason.seasonNumber, week)

        # Achievement hook — Veteran (rosters set this regular-season week)
        if not in_playoffs:
            self._creditVeteranForWeek(self.currentSeason.seasonNumber)

        # Supporter dividends (fan-income) — accrue every week, regular AND
        # playoff (backing a deep-run team keeps paying). Ticks tenure for all
        # fans; credits a dividend to those whose team played this week.
        self._accrueSupporterDividends(self.currentSeason.seasonNumber, week)

        # Resolve pick-em picks and award Floobits
        self._resolvePickEmWeek(self.currentSeason.seasonNumber, week)

        # Secret achievements that span both FP + pick-em week totals
        if not in_playoffs:
            self._checkWeekEndSecrets(self.currentSeason.seasonNumber, week)

        # Recompute mood (1-5) for all active players based on confidence/determination.
        # Personalities are static (assigned at creation); only mood updates over time.
        try:
            personalityManager = self.serviceContainer.getService('personality_manager')
            if personalityManager:
                for player in self.playerManager.activePlayers:
                    personalityManager.updateMood(player)
        except Exception as e:
            logger.error(f"Mood update failed: {e}")

        # Unlock equipped cards now that week is over
        try:
            from database.connection import get_session as _getSession
            from database.repositories.card_repositories import EquippedCardRepository
            unlockSession = _getSession()
            EquippedCardRepository(unlockSession).unlockWeek(
                self.currentSeason.seasonNumber, week
            )
            unlockSession.commit()
            unlockSession.close()
            logger.info(f"Unlocked equipped cards for week {week}")
        except Exception as e:
            logger.error(f"Failed to unlock equipped cards for week {week}: {e}")

        # The Cores narrate the slate that just finished. Before the week_end broadcast so
        # a client refreshing off that event already has the lines.
        self._publishCoresWeekNews(week)

        # Broadcast week_end event so frontend can refresh card state
        if BROADCASTING_AVAILABLE and broadcaster.is_enabled():
            nextStart = self.getNextGameStartTime(week)
            nextStartIso = nextStart.isoformat() + 'Z' if nextStart else None
            weekResults = []
            completedGames = (self.currentSeason.completedWeekGames
                              or self.currentSeason.activeGames or [])
            for g in completedGames:
                weekResults.append({
                    "homeTeam": {"name": g.homeTeam.name, "abbr": g.homeTeam.abbr},
                    "awayTeam": {"name": g.awayTeam.name, "abbr": g.awayTeam.abbr},
                    "homeScore": g.homeScore,
                    "awayScore": g.awayScore,
                    **self._frameAwareResultFields(g),
                })
            weekEndEvent = SeasonEvent.weekEnd(
                seasonNumber=self.currentSeason.seasonNumber,
                weekNumber=week,
                results=weekResults,
                nextGameStartTime=nextStartIso,
            )
            broadcaster.broadcast_sync('season', weekEndEvent)

        # Broadcast final leaderboard with persisted card bonuses
        self._broadcastLeaderboardUpdate()

    def _resolveDuplicateEquippedEffects(self, season: int, sourceWeek: int) -> None:
        """Auto-unequip duplicate-effect cards from a user's equipped set.

        Runs at week start (before the game-start auto-lock). Modifies
        the just-completed week's equipped rows so carry-forward later
        only propagates one copy per effectName per user. Picks the
        keeper by edition rarity, then by lowest slot for a stable tie
        break. The dropped EquippedCard row is deleted; the underlying
        UserCard stays in the user's collection, free to be sold,
        combined, or re-equipped to its own slot.

        No-op when sourceWeek < 1 (pre-week-1).
        """
        if not sourceWeek or sourceWeek < 1:
            return
        if not (DB_IMPORTS_AVAILABLE and USE_DATABASE and self.db_session):
            return
        try:
            from database.connection import get_session
            from database.models import EquippedCard, UserCard, CardTemplate
            from api.game_broadcaster import broadcaster as _broadcaster
        except Exception as e:
            logger.warning(f"Duplicate-effect resolver: import failed: {e}")
            return

        # Edition rarity order — keep the rarest in the duplicate group.
        editionRank = {'diamond': 4, 'prismatic': 3, 'holographic': 2, 'metallic': 1}

        session = get_session()
        try:
            rows = (
                session.query(EquippedCard, UserCard, CardTemplate)
                .join(UserCard, EquippedCard.user_card_id == UserCard.id)
                .join(CardTemplate, UserCard.card_template_id == CardTemplate.id)
                .filter(EquippedCard.season == season, EquippedCard.week == sourceWeek)
                .all()
            )
            byUser: dict = {}
            for eq, uc, tmpl in rows:
                cfg = tmpl.effect_config or {}
                effName = cfg.get('effectName') or ''
                # No-effect floor cards ('none'/blank) are EXEMPT from the
                # no-duplicate-effect rule (same as the equip setter) — a legal
                # fusion lineup fields several sub-base 'standard' cards, all with
                # effectName 'none'. Without this they'd be treated as one big
                # duplicate group and all but one unequipped every week.
                if effName in ('', 'none'):
                    continue
                byUser.setdefault(eq.user_id, {}).setdefault(effName, []).append((eq, uc, tmpl))

            unequippedCount = 0
            usersAffected = []
            for userId, effectGroups in byUser.items():
                droppedForUser = []
                for effName, group in effectGroups.items():
                    if len(group) <= 1:
                        continue
                    # Keeper rule for a duplicate-effect group:
                    #   1. Highest edition rarity wins (diamond > prismatic > holo > base).
                    #   2. Same edition: keep the higher-rated depicted player.
                    #   3. Same edition AND rating: keep the lower slot (stable).
                    group.sort(key=lambda x: (
                        -editionRank.get(x[2].edition, 0),
                        -int(getattr(x[2], 'player_rating', 0) or 0),
                        x[0].slot_number,
                    ))
                    keeper, *drops = group
                    for dropEq, dropUc, dropTmpl in drops:
                        # Delete the equipped row so carry-forward skips it.
                        # UserCard stays in the collection — user can sell,
                        # combine, or re-equip it on a free slot.
                        session.delete(dropEq)
                        droppedForUser.append({
                            'effectName': effName,
                            'displayName': (dropTmpl.effect_config or {}).get('displayName') or effName,
                            'slotNumber': dropEq.slot_number,
                            'userCardId': dropUc.id,
                        })
                        unequippedCount += 1
                if droppedForUser:
                    usersAffected.append((userId, droppedForUser))

            if unequippedCount:
                session.commit()
                logger.info(
                    f"Duplicate-effect resolver: unequipped {unequippedCount} cards "
                    f"across {len(usersAffected)} users in week {sourceWeek}"
                )
                # Per-user WebSocket notification so the UI can surface
                # what changed without forcing a manual refetch.
                for userId, dropped in usersAffected:
                    try:
                        payload = {
                            'type': 'duplicate_effects_resolved',
                            'data': {
                                'sourceWeek': sourceWeek,
                                'dropped': dropped,
                            },
                        }
                        _broadcaster.broadcast_to_user_sync(userId, payload)
                    except Exception:
                        pass
            else:
                session.rollback()
        except Exception as e:
            session.rollback()
            logger.warning(f"Duplicate-effect resolver: failed for season {season} week {sourceWeek}: {e}")
        finally:
            session.close()

    def _carryForwardEquippedCards(self, session, equippedRepo, season: int, currentWeek: int) -> None:
        """Carry forward equipped cards from the most recent week for users who don't have any yet."""
        from database.models import EquippedCard, UserCard, CardTemplate
        from sqlalchemy import func

        # Find users who already have rows for this week — skip them
        usersWithRows = {
            row[0] for row in
            session.query(EquippedCard.user_id)
            .filter_by(season=season, week=currentWeek)
            .distinct()
            .all()
        }

        # Find all users who had equipped cards in ANY previous week this season
        allEquippedUsers = {
            row[0] for row in
            session.query(EquippedCard.user_id)
            .filter(EquippedCard.season == season, EquippedCard.week < currentWeek)
            .distinct()
            .all()
        }

        needsCarry = allEquippedUsers - usersWithRows
        if not needsCarry:
            return

        carried = 0
        for userId in needsCarry:
            # Find the most recent week with equipped cards
            for lookback in range(currentWeek - 1, 0, -1):
                prevEquipped = equippedRepo.getByUserWeek(userId, season, lookback)
                if prevEquipped:
                    for prev in prevEquipped:
                        userCard = session.get(UserCard, prev.user_card_id)
                        # Skip missing or vaulted cards — a card vaulted after an
                        # earlier equip must not be carried forward and locked.
                        if not userCard or getattr(userCard, "vaulted", False):
                            continue
                        template = session.get(CardTemplate, userCard.card_template_id)
                        if not template or template.season_created != season:
                            continue
                        # Preserve a streak_count of 0 across carry-forward —
                        # an `or 1` fallback here would clobber the "just-
                        # broken streak" signal that drives the restart
                        # halving penalty in _processWeekCardEffects.
                        prevStreak = getattr(prev, 'streak_count', 1)
                        if prevStreak is None:
                            prevStreak = 1
                        # Preserve the All-Pro swap-bonus flag so a card that
                        # granted an unused swap last week still shows as
                        # "swap available" this week. Without this, every
                        # week boundary silently flips active grants to
                        # "used" — matching one of the swap-accounting bugs.
                        prevSwapBonus = bool(getattr(prev, 'swap_bonus_active', False))
                        # Carry forward peak-decay state so a cold-week
                        # streak compute on this new row can hold the
                        # peak and decay from it.
                        prevPeakOutput = getattr(prev, 'peak_output', None)
                        prevWeeksSinceBreak = getattr(prev, 'weeks_since_break', 0) or 0
                        equippedRepo.save(EquippedCard(
                            user_id=userId,
                            season=season,
                            week=currentWeek,
                            slot_number=prev.slot_number,
                            slot=prev.slot,  # fusion: carry the position-slot string too
                            user_card_id=prev.user_card_id,
                            locked=False,
                            streak_count=prevStreak,
                            swap_bonus_active=prevSwapBonus,
                            peak_output=prevPeakOutput,
                            weeks_since_break=prevWeeksSinceBreak,
                        ))
                    carried += 1
                    break
        if carried:
            session.flush()
            logger.info(f"Auto-carried equipped cards for {carried} users into week {currentWeek}")

    def _processWeekCardEffects(self, season: int, week: int) -> None:
        """Calculate and persist card effect bonuses for all users after a week completes."""
        try:
            from database.connection import get_session as _getSession
            from database.models import (
                FantasyRoster, Game, GamePlayerStats,
                Player, User, UserCurrency, WeeklyCardBonus, WeeklyPlayerFP
            )
            from database.repositories.card_repositories import EquippedCardRepository, CurrencyRepository
            from managers.cardEffectCalculator import calculateWeekCardBonuses, CardCalcContext
            from managers.cardEffects import _countPlayerTds, checkStreakCondition

            session = _getSession()
            try:
                equippedRepo = EquippedCardRepository(session)
                currencyRepo = CurrencyRepository(session)

                # Get all locked equipped cards for this week
                allEquipped = equippedRepo.getAllForWeek(season, week)
                if not allEquipped:
                    session.close()
                    return

                # Group by user_id
                byUser = {}
                for eq in allEquipped:
                    if not eq.locked:
                        continue
                    byUser.setdefault(eq.user_id, []).append(eq)

                # Get FP from WeeklyPlayerFP (banked by FantasyTracker)
                weekFPRows = session.query(WeeklyPlayerFP).filter_by(
                    season=season, week=week
                ).all()
                weekFPByPlayer = {row.player_id: row.fantasy_points for row in weekFPRows}

                # Get sub-stats from GamePlayerStats (for card conditionals)
                gameStats = (
                    session.query(GamePlayerStats)
                    .join(Game, GamePlayerStats.game_id == Game.id)
                    .filter(Game.season == season, Game.week == week)
                    .all()
                )

                # Build per-player stats dict (convert raw DB format to card-calc format)
                from managers.fantasyTracker import _dbStatsToCardFormat
                weekPlayerStats = {}
                for gps in gameStats:
                    weekPlayerStats[gps.player_id] = _dbStatsToCardFormat(
                        gps.passing_stats, gps.rushing_stats,
                        gps.receiving_stats, gps.kicking_stats,
                        weekFPByPlayer.get(gps.player_id, 0),
                        teamId=gps.team_id,
                    )
                for pid, fp in weekFPByPlayer.items():
                    if pid not in weekPlayerStats:
                        weekPlayerStats[pid] = _dbStatsToCardFormat(
                            {}, {}, {}, {}, fp,
                        )

                # Inject Q4 fantasy points for Closer card effect — mirrors
                # the fantasyTracker live-snapshot injection. Without this,
                # the persisted week-end breakdown always read 0 Q4 FP and
                # Closer paid nothing, because _dbStatsToCardFormat doesn't
                # surface the q4_fantasy_points column on its own.
                for gps in gameStats:
                    if gps.q4_fantasy_points and gps.player_id in weekPlayerStats:
                        weekPlayerStats[gps.player_id]["q4FantasyPoints"] = gps.q4_fantasy_points

                # ─── Build shared context data ───────────────────────────────

                # Team results from DB games (teamId → won)
                weekGames = session.query(Game).filter_by(season=season, week=week).all()
                teamResults = {}
                for g in weekGames:
                    if g.home_score > g.away_score:
                        teamResults[g.home_team_id] = True
                        teamResults[g.away_team_id] = False
                    elif g.away_score > g.home_score:
                        teamResults[g.away_team_id] = True
                        teamResults[g.home_team_id] = False
                    else:  # Tie
                        teamResults[g.home_team_id] = False
                        teamResults[g.away_team_id] = False

                # Build game lookup by team for opponent ELO
                teamGameMap = {}  # teamId → Game row
                for g in weekGames:
                    teamGameMap[g.home_team_id] = g
                    teamGameMap[g.away_team_id] = g

                # Player ratings and positions — Fusion: the roster IS the equipped
                # cards, so gather the players DEPICTED by every user's locked cards
                # (not FantasyRosterPlayer rows).
                allPlayerIds = set()
                for userId, userEquipped in byUser.items():
                    for eq in userEquipped:
                        pid = eq.user_card.card_template.player_id
                        if pid:
                            allPlayerIds.add(pid)

                playerRatingsMap = {}
                playerPositionMap = {}
                if allPlayerIds:
                    playerRows = session.query(
                        Player.id, Player.player_rating, Player.position
                    ).filter(Player.id.in_(allPlayerIds)).all()
                    for pid, rating, pos in playerRows:
                        playerRatingsMap[pid] = rating or 60
                        playerPositionMap[pid] = pos

                # Player performance ratings from live objects
                playerPerfRatings = {}
                if self.playerManager:
                    for p in self.playerManager.activePlayers:
                        perfRating = getattr(p, 'seasonPerformanceRating', 0)
                        if perfRating > 0:
                            playerPerfRatings[p.id] = perfRating

                # Game performance ratings (per-game, for Boom Week / Game Ball / Dud Insurance)
                gamePerfRatings = {}
                if self.playerManager and gameStats:
                    gamePerfRatings = self.playerManager.calculateGamePerformanceRatings(gameStats)

                # Team data from live objects (ELO, streaks, losses, playoff status)
                teamManager = self.serviceContainer.getService('team_manager')

                # Count big plays from in-memory game objects per team
                bigPlaysByTeam = {}
                if self.currentSeason and self.currentSeason.activeGames:
                    for game in self.currentSeason.activeGames:
                        homeId = getattr(game, 'homeTeam', {})
                        awayId = getattr(game, 'awayTeam', {})
                        if hasattr(homeId, 'id'):
                            homeId = homeId.id
                        if hasattr(awayId, 'id'):
                            awayId = awayId.id
                        homeCount = 0
                        awayCount = 0
                        for entry in getattr(game, 'gameFeed', []):
                            play = entry.get('play') if isinstance(entry, dict) else None
                            if getattr(play, 'isBigPlay', False):
                                # Count for both teams since we can't easily tell which
                                homeCount += 1
                                awayCount += 1
                        bigPlaysByTeam[homeId] = bigPlaysByTeam.get(homeId, 0) + homeCount
                        bigPlaysByTeam[awayId] = bigPlaysByTeam.get(awayId, 0) + awayCount

                # ─── Get weekly modifier ──────────────────────────────────────
                activeModifier = ""
                try:
                    from database.models import WeeklyModifier
                    modRow = session.query(WeeklyModifier).filter_by(
                        season=season, week=week
                    ).first()
                    if modRow:
                        activeModifier = modRow.modifier
                except Exception:
                    pass

                # Eminence + Cornerstone: position pace + leaderboard data
                # (same for all users this week). computeEminenceData returns 4
                # values — top10/top1 sets feed Cornerstone too.
                from managers.cardEffectCalculator import computeEminenceData
                (positionAvgFPs, playerSeasonFPPerGame,
                 top10PerPosition, top1PerPosition) = computeEminenceData(session, season, week)

                # Roster-trait context shared across users:
                #   priorSeasonMissedPlayoffTeamIds — Comeback Kid
                #   currentTop6TeamIds              — Domination
                from managers.cardProjection import (
                    _lookupPriorSeasonMissedPlayoffTeams,
                    _lookupCurrentTop6Teams,
                )
                priorSeasonMissedPlayoffTeamIds = _lookupPriorSeasonMissedPlayoffTeams(session, season)
                currentTop6TeamIds = _lookupCurrentTop6Teams(session, season)

                # ─── Process each user ───────────────────────────────────────
                for userId, userEquipped in byUser.items():
                    roster = session.query(FantasyRoster).filter_by(
                        user_id=userId, season=season, is_locked=True
                    ).first()
                    if not roster:
                        continue

                    # Fusion: this user's lineup = the players DEPICTED by their locked
                    # equipped cards (one per slot), NOT FantasyRosterPlayer rows. Keep a
                    # per-card list so the base FP mirrors getSnapshot exactly (a player
                    # depicted by two cards contributes twice, matching the live path).
                    depictedPairs = [
                        (eq, eq.user_card.card_template.player_id) for eq in userEquipped
                    ]
                    rosterPlayerIds = {pid for _eq, pid in depictedPairs}

                    # Compute user's raw weekly FP and TDs
                    weekRawFP = 0.0
                    rosterTotalTds = 0
                    for _eq, pid in depictedPairs:
                        pStats = weekPlayerStats.get(pid, {})
                        weekRawFP += pStats.get("fantasyPoints", 0)
                        rosterTotalTds += _countPlayerTds(pStats)

                    rosterPlayerRatings = {
                        pid: playerRatingsMap.get(pid, 60) for pid in rosterPlayerIds
                    }
                    rosterPlayerPositions = {
                        pid: playerPositionMap.get(pid, 0) for pid in rosterPlayerIds
                    }

                    # Build team IDs and names for roster players
                    rosterPlayerTeamIds = {}
                    rosterPlayerNames = {}
                    for pid in rosterPlayerIds:
                        ps = weekPlayerStats.get(pid, {})
                        teamId = ps.get("teamId")
                        if teamId:
                            rosterPlayerTeamIds[pid] = teamId
                    if self.playerManager:
                        for pid in rosterPlayerIds:
                            player = self.playerManager.getPlayerById(pid)
                            if player:
                                rosterPlayerNames[pid] = player.name
                                if pid not in rosterPlayerTeamIds and hasattr(player, 'team') and hasattr(player.team, 'id'):
                                    rosterPlayerTeamIds[pid] = player.team.id

                    streakCounts = {
                        eq.id: getattr(eq, 'streak_count', 1) for eq in userEquipped
                    }
                    # Streak peak-decay state — feeds _computeStreakEffect so a
                    # cold week after a recent streak pays a decaying tail
                    # instead of dropping straight to base.
                    streakPeakOutputs = {
                        eq.id: float(eq.peak_output) for eq in userEquipped
                        if getattr(eq, 'peak_output', None) is not None
                    }
                    streakWeeksSinceBreak = {
                        eq.id: int(getattr(eq, 'weeks_since_break', 0) or 0)
                        for eq in userEquipped
                    }

                    # Roster-trait card data (for Castaway, Rookie Hype) ──
                    # Team records: team_id → win pct, used by Castaway to detect
                    # sub-.500 team players on the roster.
                    teamRecords = {}
                    if teamManager:
                        for team in teamManager.teams:
                            stats = getattr(team, 'seasonTeamStats', {}) or {}
                            wp = stats.get('winPerc')
                            if wp is None:
                                w = stats.get('wins', 0) or 0
                                l = stats.get('losses', 0) or 0
                                wp = w / (w + l) if (w + l) > 0 else 0.5
                            teamRecords[team.id] = float(wp)
                    # Rookie flags: playerId → True if rookie. Used by Rookie Hype.
                    # Matches the "Rookie" service tier (seasonsPlayed 0–1) so
                    # the card fires for the same players the UI labels as
                    # rookies, not just the strict first-year subset.
                    rosterRookieFlags = {}
                    rosterSeasonsPlayed = {}  # Vanguard reads this for 5+ vets
                    if self.playerManager:
                        for pid in rosterPlayerIds:
                            player = self.playerManager.getPlayerById(pid)
                            if player:
                                svc = getattr(player, 'serviceTime', None)
                                isRookieSvc = bool(svc and getattr(svc, 'name', '') == 'Rookie')
                                rosterRookieFlags[pid] = bool(
                                    isRookieSvc
                                    or (getattr(player, 'seasonsPlayed', 99) or 99) <= 1
                                )
                                rosterSeasonsPlayed[pid] = int(getattr(player, 'seasonsPlayed', 0) or 0)

                    # Loyalty snapshot — original roster player IDs persisted
                    # at first-save on the FantasyRoster row. Empty if the user
                    # hasn't saved yet (shouldn't happen by week-end but guard).
                    initialRosterPlayerIds: set = set()
                    if roster and getattr(roster, 'initial_player_ids', None):
                        try:
                            import json as _json
                            initialRosterPlayerIds = {
                                int(pid) for pid in _json.loads(roster.initial_player_ids)
                            }
                        except Exception:
                            initialRosterPlayerIds = set()

                    # Pick-em stats this user/week — drives Conviction (manual
                    # submit streak), Augur (accuracy bonus), Tipster (FPx
                    # scaling with weekly points).
                    userManualPickSubmittedThisWeek = False
                    userWeeklyPickemCorrect = 0
                    userWeeklyPickemTotal = 0
                    userWeeklyPickemPoints = 0
                    try:
                        from database.models import PickEmPick
                        weekPicks = session.query(PickEmPick).filter_by(
                            user_id=userId, season=season, week=week,
                        ).all()
                        if weekPicks:
                            userManualPickSubmittedThisWeek = any(not p.is_auto for p in weekPicks)
                            for p in weekPicks:
                                if p.correct is True:
                                    userWeeklyPickemCorrect += 1
                                    userWeeklyPickemTotal += 1
                                elif p.correct is False:
                                    userWeeklyPickemTotal += 1
                                userWeeklyPickemPoints += int(p.points_earned or 0)
                    except Exception as e:
                        logger.debug(f"Pick-em ctx hydration skipped for user={userId} wk={week}: {e}")

                    # User's favorite team data
                    userRow = session.get(User, userId)
                    userFavoriteTeamId = userRow.favorite_team_id if userRow else None

                    # Believe reads favorite team season wins
                    favoriteTeamSeasonWins = 0
                    if userFavoriteTeamId and teamManager:
                        _favTeam = teamManager.getTeamById(userFavoriteTeamId)
                        if _favTeam:
                            favoriteTeamSeasonWins = int(
                                (getattr(_favTeam, 'seasonTeamStats', {}) or {}).get('wins', 0) or 0
                            )

                    favoriteTeamElo = 1500.0
                    favoriteTeamStreak = 0
                    favoriteTeamPriorStreak = 0
                    favoriteTeamPeakStreak = 0
                    favoriteTeamSeasonLosses = 0
                    favoriteTeamInPlayoffs = False
                    favoriteTeamWonThisWeek = False
                    favoriteTeamOpponentElo = 1500.0
                    favoriteTeamBigPlays = 0
                    favoriteTeamGameFinal = False

                    if userFavoriteTeamId and teamManager:
                        favTeam = teamManager.getTeamById(userFavoriteTeamId)
                        if favTeam:
                            favoriteTeamElo = getattr(favTeam, 'elo', 1500.0)
                            favStats = getattr(favTeam, 'seasonTeamStats', {})
                            favoriteTeamStreak = favStats.get('streak', 0)
                            favoriteTeamPriorStreak = favStats.get('priorStreak', 0)
                            favoriteTeamPeakStreak = favStats.get('peakStreak', 0)
                            favoriteTeamSeasonLosses = favStats.get('losses', 0)
                            favoriteTeamWonThisWeek = teamResults.get(userFavoriteTeamId, False)
                            favoriteTeamBigPlays = bigPlaysByTeam.get(userFavoriteTeamId, 0)

                            # Playoff status: check if team is in top 6 of its league
                            if self.leagueManager:
                                teamLeague = self.leagueManager.getTeamLeague(favTeam)
                                if teamLeague:
                                    standings = teamLeague.getStandings()
                                    for idx, entry in enumerate(standings):
                                        if entry['team'] == favTeam:
                                            favoriteTeamInPlayoffs = idx < 6
                                            break

                            # Opponent ELO from this week's game
                            favGame = teamGameMap.get(userFavoriteTeamId)
                            if favGame:
                                if favGame.home_team_id == userFavoriteTeamId:
                                    oppTeam = teamManager.getTeamById(favGame.away_team_id)
                                else:
                                    oppTeam = teamManager.getTeamById(favGame.home_team_id)
                                if oppTeam:
                                    favoriteTeamOpponentElo = getattr(oppTeam, 'elo', 1500.0)
                                # Week is complete — all games are final
                                favoriteTeamGameFinal = True

                    # League average ELO
                    leagueAverageElo = 1500.0
                    if teamManager:
                        allTeams = teamManager.teams
                        if allTeams:
                            leagueAverageElo = sum(getattr(t, 'elo', 1500.0) for t in allTeams) / len(allTeams)

                    # Fusion: swaps are retired — no swap history, so the lineup is
                    # treated as unchanged this season, and the swap-based effects
                    # (retired) compute 0 off these zeros.
                    rosterUnchangedWeeks = week
                    seasonSwapsUsed = 0

                    # Check for user-level modifier override (Modifier Nullifier power-up)
                    userModifier = activeModifier
                    try:
                        from database.models import UserModifierOverride
                        modOverride = session.query(UserModifierOverride).filter_by(
                            user_id=userId, season=season, week=week
                        ).first()
                        if modOverride:
                            userModifier = modOverride.override_modifier
                    except Exception:
                        pass

                    # Compute kicker season FG misses for Good Neighbor
                    kickerSeasonFgMisses = 0
                    kickerPids = [pid for _eq, pid in depictedPairs
                                  if playerPositionMap.get(pid) == 5]
                    if kickerPids:
                        seasonKickerStats = (
                            session.query(GamePlayerStats)
                            .join(Game, GamePlayerStats.game_id == Game.id)
                            .filter(Game.season == season, Game.week < week,
                                    GamePlayerStats.player_id.in_(kickerPids))
                            .all()
                        )
                        for ks in seasonKickerStats:
                            kStats = ks.kicking_stats or {}
                            if isinstance(kStats, str):
                                import json as _jsonk
                                kStats = _jsonk.loads(kStats)
                            kickerSeasonFgMisses += kStats.get("fg_missed", 0)

                    # Compute chanceBonus from Fortune's Favor + fortunate modifier
                    chanceBonus = 0.0
                    if userModifier == "fortunate":
                        chanceBonus += 0.15
                    try:
                        from database.repositories.shop_repository import ShopPurchaseRepository
                        shopRepo = ShopPurchaseRepository(session)
                        if hasattr(shopRepo, 'getActiveFortunesFavor') and shopRepo.getActiveFortunesFavor(userId, season, week):
                            chanceBonus += 0.10
                    except Exception:
                        pass

                    # Fat Cat / Opulence reads the user's Floobits balance. Mirrors
                    # fantasyTracker._buildCardCalcContext so the week-end persisted
                    # bonus matches what the live snapshot showed.
                    userFloobitsBalance = 0
                    try:
                        uc = session.query(UserCurrency).filter_by(user_id=userId).first()
                        if uc:
                            session.refresh(uc)
                            userFloobitsBalance = uc.balance or 0
                    except Exception as e:
                        logger.warning(f"Failed to fetch Floobits balance for user {userId}: {e}")

                    # FLEX slot detection — mirrors fantasyTracker._buildCardCalcContext.
                    # Fusion: the FLEX is an equipped-card slot, so detect a card in the
                    # FLEX slot (not a FantasyRosterPlayer FLEX row). Without this, Home
                    # Alone misses an empty FLEX slot at week-end.
                    hasFlexSlot = any(getattr(eq, 'slot', '') == 'FLEX' for eq in userEquipped)
                    if not hasFlexSlot:
                        try:
                            from database.models import ShopPurchase as _SP
                            for eqRow in userEquipped:
                                uc2 = getattr(eqRow, 'user_card', None)
                                tmpl = getattr(uc2, 'card_template', None) if uc2 else None
                                cls = getattr(tmpl, 'classification', None) or ''
                                if 'mvp' in cls:
                                    hasFlexSlot = True
                                    break
                            if not hasFlexSlot:
                                activeFlex = session.query(_SP).filter(
                                    _SP.user_id == userId,
                                    _SP.season == season,
                                    _SP.item_slug == 'temp_card_slot',
                                    _SP.expires_at_week >= week,
                                ).first()
                                if activeFlex:
                                    hasFlexSlot = True
                        except Exception:
                            pass

                    # Build context
                    calcCtx = CardCalcContext(
                        userId=userId,
                        season=season,
                        weekNumber=week,
                        chanceBonus=chanceBonus,
                        kickerSeasonFgMisses=kickerSeasonFgMisses,
                        rosterPlayerIds=rosterPlayerIds,
                        weekPlayerStats=weekPlayerStats,
                        weekRawFP=weekRawFP,
                        rosterPlayerRatings=rosterPlayerRatings,
                        rosterTotalTds=rosterTotalTds,
                        rosterPlayerPositions=rosterPlayerPositions,
                        streakCounts=streakCounts,
                        streakPeakOutputs=streakPeakOutputs,
                        streakWeeksSinceBreak=streakWeeksSinceBreak,
                        _teamRecords=teamRecords,
                        _rosterRookieFlags=rosterRookieFlags,
                        userManualPickSubmittedThisWeek=userManualPickSubmittedThisWeek,
                        userWeeklyPickemCorrect=userWeeklyPickemCorrect,
                        userWeeklyPickemTotal=userWeeklyPickemTotal,
                        userWeeklyPickemPoints=userWeeklyPickemPoints,
                        userFavoriteTeamId=userFavoriteTeamId,
                        favoriteTeamElo=favoriteTeamElo,
                        leagueAverageElo=leagueAverageElo,
                        favoriteTeamStreak=favoriteTeamStreak,
                        favoriteTeamPriorStreak=favoriteTeamPriorStreak,
                        favoriteTeamPeakStreak=favoriteTeamPeakStreak,
                        favoriteTeamSeasonLosses=favoriteTeamSeasonLosses,
                        favoriteTeamInPlayoffs=favoriteTeamInPlayoffs,
                        favoriteTeamWonThisWeek=favoriteTeamWonThisWeek,
                        favoriteTeamOpponentElo=favoriteTeamOpponentElo,
                        favoriteTeamBigPlays=favoriteTeamBigPlays,
                        favoriteTeamGameFinal=favoriteTeamGameFinal,
                        rosterUnchangedWeeks=rosterUnchangedWeeks,
                        teamResults=teamResults,
                        playerPerformanceRatings=playerPerfRatings,
                        gamePerformanceRatings=gamePerfRatings,
                        rosterPlayerTeamIds=rosterPlayerTeamIds,
                        rosterPlayerNames=rosterPlayerNames,
                        activeModifier=userModifier,
                        unusedSwaps=0,
                        seasonSwapsUsed=seasonSwapsUsed,
                        hasFlexSlot=hasFlexSlot,
                        userFloobitsBalance=userFloobitsBalance,
                        positionAvgFPs=positionAvgFPs,
                        playerSeasonFPPerGame=playerSeasonFPPerGame,
                        top10PerPosition=top10PerPosition,
                        top1PerPosition=top1PerPosition,
                        # Roster-trait card data (next-season additions)
                        priorSeasonMissedPlayoffTeamIds=priorSeasonMissedPlayoffTeamIds,
                        currentTop6TeamIds=currentTop6TeamIds,
                        _rosterSeasonsPlayed=rosterSeasonsPlayed,
                        initialRosterPlayerIds=initialRosterPlayerIds,
                        favoriteTeamSeasonWins=favoriteTeamSeasonWins,
                    )

                    # Populate streak conditions for breakdown display AND
                    # pre-bump streakCounts to the PROJECTED value when the
                    # condition is met. Without the bump, the persisted
                    # breakdown for week N pays at the count from end-of-
                    # week-N-1 (always one tick behind) — meaning the very
                    # first week the streak triggers pays base only, which
                    # contradicts the per-week growth users expect.
                    # The actual eq.streak_count DB bump still happens
                    # post-calc at line ~1914; this just keeps the calc-time
                    # view in sync with the live snapshot path.
                    from managers.cardEffects import STREAK_CONFIGS as _streakConfigs
                    streakConditions = {}
                    for eq in userEquipped:
                        ec = eq.user_card.card_template.effect_config or {}
                        eName = ec.get("effectName", "")
                        if eName not in _streakConfigs:
                            continue
                        cfg = _streakConfigs[eName]
                        # Weekly accumulators (touchdown_jackpot) compute
                        # their own ticks from this week's data; don't bump.
                        if cfg.get("isWeekly"):
                            streakConditions[eq.id] = True
                            continue
                        condMet = checkStreakCondition(
                            eName, calcCtx, eq.user_card.card_template.player_id
                        )
                        streakConditions[eq.id] = condMet
                        # Apply ironclad modifier — if active, treat as met
                        # for the bump too (matches the eq.streak_count
                        # bump path below at the streak-management block).
                        effectiveMet = condMet or (userModifier == "ironclad")
                        if effectiveMet:
                            # Streak restart penalty (applied pre-calc so
                            # THIS week's compute sees the halved peak): if
                            # this is the first met week after a break and
                            # a peak carries from a prior streak, halve the
                            # peak in calcCtx so carriedBase = halved value.
                            # Post-calc, the same halving is persisted to
                            # eq.peak_output for future weeks.
                            priorCount = eq.streak_count if eq.streak_count is not None else 1
                            if priorCount == 0:
                                priorPeak = calcCtx.streakPeakOutputs.get(eq.id)
                                if priorPeak is not None:
                                    primary = ec.get("primary", {}) or {}
                                    baseReward = primary.get("baseReward", 0) or 0
                                    halved = float(priorPeak) * 0.5
                                    if halved <= baseReward:
                                        calcCtx.streakPeakOutputs.pop(eq.id, None)
                                    else:
                                        calcCtx.streakPeakOutputs[eq.id] = halved
                                # Skip the "1 = idle baseline" value on restart
                                # so display (count - 1) shows 1 on first met
                                # week instead of 0.
                                calcCtx.streakCounts[eq.id] = 2
                            else:
                                calcCtx.streakCounts[eq.id] = calcCtx.streakCounts.get(eq.id, 0) + 1
                    calcCtx.liveStreakConditionsMet = streakConditions

                    # Calculate card bonuses
                    result = calculateWeekCardBonuses(userEquipped, calcCtx)

                    # When the Cracking is active, the simulation's math is
                    # the controlling Core's signature equation rather than
                    # the baseline aggregator. Resolved once per week per
                    # user against the persisted Cracking state. No
                    # Cracking → computeFinalOutput uses the standard
                    # bonus-additive formula (next-season's aggregator).
                    try:
                        from managers.anomalyManager import getActiveCriticalityCore
                        criticalityCore = getActiveCriticalityCore(season, week)
                    except Exception:
                        criticalityCore = None

                    from managers.coreEquations import computeFinalOutput, equationTemplate
                    rawTotalFP, totalEquation = computeFinalOutput(
                        weekRawFP, result.totalBonusFP, result.multFactors,
                        coreKey=criticalityCore,
                    )
                    # Subtract raw FP so we store only the card bonus portion
                    totalFP = round(rawTotalFP - weekRawFP, 2)
                    if totalFP < 0:
                        totalFP = 0.0
                    # multProduct feeds the Compound achievement hook below.
                    # Always use the bonus-additive aggregator — it's the
                    # user-facing effective multiplier from the card breakdown
                    # they see. During Cracking the totalFP is different but
                    # the achievement signal still tracks card-stacking strength.
                    from managers.cardEffectCalculator import aggregateMultFactors
                    multProduct = aggregateMultFactors(result.multFactors)

                    # Achievement hook — Compound tiers (single-week FPx from cards only)
                    # Exclude the synergy weekly modifier's contribution so the achievement
                    # reflects card-driven multipliers, not a "free" modifier bonus. Synergy
                    # now DOUBLES the team-stack FPx; the baseline stack (card-driven) still
                    # counts, only the modifier's extra is removed. multFactors aggregate
                    # bonus-additively, so subtracting the extra delta is exact.
                    cardMultProduct = multProduct
                    if userModifier == "synergy" and result.stackModifierBonus > 0:
                        cardMultProduct = max(1.0, multProduct - result.stackModifierBonus)
                    if cardMultProduct > 1.0:
                        try:
                            from managers import achievementManager as _amCompound
                            _amCompound.onWeeklyTotalFpMultiplier(session, userId, cardMultProduct, season)
                        except Exception as _e:
                            logger.warning(f"Compound hook failed: {_e}")

                    # Persist FP bonus
                    if totalFP > 0 or result.floobitsEarned > 0:
                        if totalFP > 0:
                            roster.card_bonus_points = (roster.card_bonus_points or 0) + totalFP
                        import json as _json
                        breakdownDicts = [{
                            "slotNumber": b.slotNumber,
                            "edition": b.edition,
                            "tier": b.tier,
                            "playerId": b.playerId,
                            "playerName": b.playerName,
                            "effectName": b.effectName,
                            "displayName": b.displayName,
                            "detail": b.detail,
                            "category": b.category,
                            "outputType": b.outputType,
                            "primaryFP": b.primaryFP,
                            "primaryMult": b.primaryMult,
                            "primaryFloobits": b.primaryFloobits,
                            "matchMultiplied": b.matchMultiplied,
                            "matchMultiplier": b.matchMultiplier,
                            "preMatchFP": b.preMatchFP,
                            "preMatchFloobits": b.preMatchFloobits,
                            "conditionalBonus": b.conditionalBonus,
                            "conditionalLabel": b.conditionalLabel,
                            "secondaryFP": b.secondaryFP,
                            "secondaryFloobits": b.secondaryFloobits,
                            "secondaryMult": b.secondaryMult,
                            "totalFP": b.totalFP,
                            "floobitsEarned": b.floobitsEarned,
                            "playerStatLine": b.playerStatLine,
                            "equation": b.equation,
                            "isChanceEffect": b.isChanceEffect,
                            "chanceRoll": b.chanceRoll,
                            "chanceThreshold": b.chanceThreshold,
                            "chanceTriggered": b.chanceTriggered,
                            "streakActive": b.streakActive,
                            "streakCount": b.streakCount,
                            # Glitch (docs/GLITCH_CARDS.md). Without these the line item
                            # rendered live and then VANISHED the moment the week banked,
                            # because the stored breakdown is what every later read uses.
                            "glitched": getattr(b, "glitched", False),
                            "glitchChance": getattr(b, "glitchChance", 0.0),
                            "glitchTriggered": getattr(b, "glitchTriggered", False),
                            "glitchOutcome": getattr(b, "glitchOutcome", None),
                            "glitchFp": getattr(b, "glitchFp", 0.0),
                            "glitchMultDelta": getattr(b, "glitchMultDelta", 0.0),
                            "glitchReadable": getattr(b, "glitchReadable", False),
                        } for b in result.cardBreakdowns]
                        storedJson = _json.dumps({
                            "breakdowns": breakdownDicts,
                            "equationSummary": {
                                "weekRawFP": round(weekRawFP, 1),
                                "totalBonusFP": round(result.totalBonusFP, 2),
                                "multFactors": [round(f, 2) for f in result.multFactors],
                                "criticalityCore": criticalityCore,
                                "criticalityEquation": totalEquation if criticalityCore else None,
                                "criticalityEquationTemplate": equationTemplate(criticalityCore) if criticalityCore else None,
                            },
                        })
                        weekBonus = WeeklyCardBonus(
                            roster_id=roster.id,
                            user_id=userId,
                            season=season,
                            week=week,
                            bonus_fp=totalFP,
                            breakdowns_json=storedJson,
                        )
                        session.add(weekBonus)
                        logger.info(
                            f"Card bonus for user {userId} week {week}: "
                            f"+{totalFP:.2f} FP (total: {roster.card_bonus_points:.2f})"
                        )

                    # Credit Floobits from cards
                    if result.floobitsEarned > 0:
                        cardNames = ", ".join(
                            b.displayName for b in result.cardBreakdowns if b.floobitsEarned > 0
                        )
                        currencyRepo.addFunds(
                            userId, result.floobitsEarned, "card_effect",
                            description=f"Week {week} card earnings ({cardNames})",
                            season=season, week=week,
                        )
                        logger.info(
                            f"Card Floobits for user {userId} week {week}: "
                            f"+{result.floobitsEarned} Floobits"
                        )
                        # Achievement hook — Windfall tiers (floobits from card effects in a single week)
                        try:
                            from managers import achievementManager as _am
                            _am.onWeeklyCardFloobits(session, userId, result.floobitsEarned, season)
                        except Exception as _e:
                            logger.warning(f"Windfall hook failed: {_e}")

                    # ─── Streak management ──────────────────────────────────
                    for eq in userEquipped:
                        effectConfig = eq.user_card.card_template.effect_config or {}
                        effectName = effectConfig.get("effectName", "")
                        category = effectConfig.get("category", "")

                        if category == "streak":
                            from managers.cardEffects import STREAK_CONFIGS
                            # Bonsai: probabilistic growth instead of auto-increment
                            if effectName == "bonsai":
                                self._rollCultivationGrowth(eq, effectConfig, calcCtx, weekBonus)
                                continue
                            # Ironclad modifier: streaks can't reset this week
                            if activeModifier == "ironclad":
                                conditionMet = True
                            else:
                                conditionMet = checkStreakCondition(
                                    effectName, calcCtx, eq.user_card.card_template.player_id
                                )
                            cfg = STREAK_CONFIGS.get(effectName, {})
                            isNoReset = cfg.get("noReset", False)
                            isWeekly = cfg.get("isWeekly", False)
                            if conditionMet:
                                priorCount = eq.streak_count if eq.streak_count is not None else 1
                                # Streak restart penalty: when condition is
                                # met again after a break (priorCount==0 but
                                # peak_output carries from a prior streak),
                                # halve the carried peak so the new streak
                                # has to climb back up rather than instantly
                                # paying the prior peak. Without this, a
                                # quick on/off cycle on a deep streak (e.g.
                                # Drought) sustained 500+ FP indefinitely.
                                if (priorCount == 0
                                        and getattr(eq, 'peak_output', None) is not None
                                        and not isWeekly and not isNoReset):
                                    halved = float(eq.peak_output) * 0.5
                                    primary = effectConfig.get("primary", {})
                                    baseReward = primary.get("baseReward", 0)
                                    if halved <= baseReward:
                                        eq.peak_output = None
                                    else:
                                        eq.peak_output = halved
                                # On restart from 0, skip the "1 = idle"
                                # baseline so display (count - 1) reads as 1
                                # for the first active week.
                                if priorCount == 0:
                                    eq.streak_count = 2
                                else:
                                    eq.streak_count = priorCount + 1
                                # peak_output stays LOCKED during an active
                                # streak — it represents the carried base
                                # the streak began at. Only break weeks and
                                # cold continuing weeks mutate it.
                                if not isWeekly and not isNoReset:
                                    eq.weeks_since_break = 0
                            elif not isNoReset:
                                if not isWeekly:
                                    primary = effectConfig.get("primary", {})
                                    baseReward = primary.get("baseReward", 0)
                                    growthPerTick = primary.get("growthPerTick", 0)
                                    rewardType = primary.get("rewardType", "fp")
                                    priorCount = eq.streak_count or 0
                                    currentPeak = eq.peak_output
                                    if currentPeak is not None and currentPeak > baseReward:
                                        carriedBase = currentPeak
                                    else:
                                        carriedBase = baseReward
                                    if priorCount > 0:
                                        # Streak just broke. New peak = the peak the
                                        # streak achieved. Compute this week already
                                        # paid this value; store it so subsequent
                                        # cold weeks decay from here.
                                        newPeak = carriedBase + growthPerTick * (priorCount - 1)
                                        if newPeak > baseReward:
                                            eq.peak_output = newPeak
                                        else:
                                            eq.peak_output = None
                                        eq.weeks_since_break = 0
                                    elif eq.peak_output is not None:
                                        # Continuing cold week — decay one step
                                        # of the streak's own growth amount. For
                                        # mult cards we step down the bonus
                                        # portion (peak − 1) by growthPerTick;
                                        # for FP cards just subtract directly.
                                        # Symmetric to build: a 10-week streak
                                        # decays over ~10 cold weeks, matching
                                        # the same pace as the climb.
                                        if rewardType == "mult":
                                            currentBonus = max(0.0, eq.peak_output - 1)
                                            steppedBonus = max(0.0, currentBonus - growthPerTick)
                                            stepped = 1.0 + steppedBonus
                                        else:
                                            stepped = eq.peak_output - growthPerTick
                                        if stepped <= baseReward:
                                            eq.peak_output = None
                                        else:
                                            eq.peak_output = stepped
                                        eq.weeks_since_break = (eq.weeks_since_break or 0) + 1
                                eq.streak_count = 0
                            # If noReset=True and condition not met, streak stays unchanged

                session.commit()
            except Exception as e:
                session.rollback()
                import traceback
                logger.error(
                    f"Error processing week card effects: {e}\n{traceback.format_exc()}"
                )
            finally:
                session.close()
        except ImportError as e:
            logger.warning(f"Card effect processing unavailable: {e}")

    @staticmethod
    def _frameAwareResultFields(g) -> dict:
        """Extra fields for a week_end result entry so the floosbot reports frames matches by
        FRAMES WON (not the point total), with the points-tiebreak note when a match finished
        level on frames. Empty for standard games (homeScore/awayScore already ARE the
        result). Mirrors the game_end event's frames handling in floosball_game.py."""
        fmt = getattr(g, 'format', None)
        if fmt is None or getattr(fmt, 'key', '') != 'frames':
            return {}
        try:
            from game_formats import _cleanNum
            dh, da = fmt.resultDisplay(g)
            fields = {'displayScore': {'home': _cleanNum(dh), 'away': _cleanNum(da)},
                      'scoreLabel': 'frames'}
            fh = getattr(g, '_framesWonHome', 0.0)
            fa = getattr(g, '_framesWonAway', 0.0)
            if fh == fa and g.homeScore != g.awayScore:
                wt = g.homeTeam if g.homeScore > g.awayScore else g.awayTeam
                wn = getattr(wt, 'abbr', None) or getattr(wt, 'name', 'The winner')
                hi, lo = max(g.homeScore, g.awayScore), min(g.homeScore, g.awayScore)
                fields['tiebreakNote'] = f"{wn} win on points {_cleanNum(hi)}-{_cleanNum(lo)}"
            return fields
        except Exception:
            return {}

    def _applyFormatStateToRow(self, dbRow, game) -> None:
        """Persist the format's display state (innings line score, frames results, ...) so
        the box score survives a restart. It's only ever computed live, so a finished game
        rebuilt from the DB has no other source for it. No-op for standard games, whose
        breakdown already lives in the quarter-score columns."""
        try:
            extra = game.format.stateExtra(game)
            if extra:
                import json
                dbRow.format_state = json.dumps(extra)
        except Exception:
            logger.debug("Could not serialize format state for game", exc_info=True)

    def _applyTeamStatsToRow(self, dbRow, game) -> None:
        """Persist the full per-team box score, so a finished game can say HOW it was won.

        The dedicated home_/away_ columns cover yards, TDs, FGs, sacks, ints and fumble
        recoveries. They do NOT cover first downs or third/fourth-down conversions, and
        those cannot be rebuilt from `game_player_stats` afterwards — a first down is a
        team event, not a player one. Persisted as the same `team` block the live
        broadcast sends, so the reader on the other side is the shape the frontend
        already understands.

        Play-by-play is deliberately still NOT persisted (owner): the feed is far larger
        than these totals and stays in memory only.
        """
        try:
            snapshot = game._buildGameStatsSnapshot()
            if not snapshot:
                return
            payload = {
                side: (snapshot.get(side) or {}).get('team')
                for side in ('home', 'away')
            }
            # Both sides or neither — a half-written box score reads as a real one.
            if not payload['home'] or not payload['away']:
                return
            import json
            dbRow.team_stats = json.dumps(payload)
        except Exception:
            logger.debug("Could not serialize team stats for game", exc_info=True)

    def _applyGameStatsToRow(self, dbRow, gameStatsDict: dict) -> None:
        """Copy team stat totals from gameDict['gameStats'] into a DB Game row."""
        if not gameStatsDict:
            return
        hOff = gameStatsDict.get('homeTeam', {}).get('offense', {})
        hDef = gameStatsDict.get('homeTeam', {}).get('defense', {})
        aOff = gameStatsDict.get('awayTeam', {}).get('offense', {})
        aDef = gameStatsDict.get('awayTeam', {}).get('defense', {})

        dbRow.home_rush_yards = hOff.get('rushYards')
        dbRow.home_pass_yards = hOff.get('passYards')
        dbRow.home_rush_tds   = hOff.get('runTds')
        dbRow.home_pass_tds   = hOff.get('passTds')
        dbRow.home_fgs        = hOff.get('fgs')
        dbRow.home_sacks      = hDef.get('sacks')
        dbRow.home_ints       = hDef.get('ints')
        dbRow.home_fum_rec    = hDef.get('fumRec')

        dbRow.away_rush_yards = aOff.get('rushYards')
        dbRow.away_pass_yards = aOff.get('passYards')
        dbRow.away_rush_tds   = aOff.get('runTds')
        dbRow.away_pass_tds   = aOff.get('passTds')
        dbRow.away_fgs        = aOff.get('fgs')
        dbRow.away_sacks      = aDef.get('sacks')
        dbRow.away_ints       = aDef.get('ints')
        dbRow.away_fum_rec    = aDef.get('fumRec')

    def _cleanupCompletedGameMemory(self, excludeGames=None):
        """Free play-by-play data from completed games to reduce memory usage.

        After a week's games are no longer served by the API (i.e., the next
        week has started and completedWeekGames is cleared), the full play
        feed, highlights, and Play object references are no longer needed.
        Game summary data (scores, teams, status) is preserved so
        /api/games/{id} still returns basic info.

        Args:
            excludeGames: set of game objects to skip (e.g., current active/completed games)
        """
        if not self.currentSeason or not self.currentSeason.schedule:
            return

        excludeSet = set(excludeGames) if excludeGames else set()
        cleaned = 0

        for weekEntry in self.currentSeason.schedule:
            games = weekEntry.get('games', [])
            for game in games:
                if game in excludeSet:
                    continue
                # Only clean finished games
                if not hasattr(game, 'status') or game.status.name != 'Final':
                    continue
                feedLen = len(getattr(game, 'gameFeed', []))
                if feedLen == 0:
                    continue  # already cleaned
                game.gameFeed = []
                game.highlights = []
                # Break the shared reference to season.leagueHighlights
                game.leagueHighlights = None
                # Clear the current Play object (holds player refs + insights)
                if hasattr(game, 'play'):
                    game.play = None
                cleaned += 1

        if cleaned > 0:
            logger.info(f"Memory cleanup: cleared play-by-play data from {cleaned} completed games")

    def _cleanupOrphanedWeekGames(self, season: int, week: int) -> None:
        """Reset completed games from an interrupted week so they replay cleanly.

        When the app crashes mid-week, some games may already be saved as 'final'.
        Instead of deleting them (which loses the matchup and leaves teams without
        a game that week), reset them to 'scheduled' and wipe their stats.  The
        simulation will then replay the full week with all original matchups intact.
        """
        if not DB_IMPORTS_AVAILABLE or not USE_DATABASE:
            return
        try:
            from database.connection import get_session as _getSession
            session = _getSession()
            orphanedGames = session.query(DBGame).filter_by(
                season=season, week=week, status='final'
            ).all()
            if not orphanedGames:
                session.close()
                return
            gameIds = [g.id for g in orphanedGames]
            # Delete player stats (they'll be regenerated on replay)
            deleted = session.query(DBGamePlayerStats).filter(
                DBGamePlayerStats.game_id.in_(gameIds)
            ).delete(synchronize_session='fetch')
            # Reset games to scheduled instead of deleting — preserves matchups
            for g in orphanedGames:
                g.status = 'scheduled'
                g.home_score = 0
                g.away_score = 0
                g.home_score_q1 = 0
                g.home_score_q2 = 0
                g.home_score_q3 = 0
                g.home_score_q4 = 0
                g.home_score_ot = 0
                g.away_score_q1 = 0
                g.away_score_q2 = 0
                g.away_score_q3 = 0
                g.away_score_q4 = 0
                g.away_score_ot = 0
                g.is_overtime = False
                g.total_plays = 0
                g.home_rush_yards = 0
                g.home_pass_yards = 0
                g.home_rush_tds = 0
                g.home_pass_tds = 0
                g.home_fgs = 0
                g.home_sacks = 0
                g.home_ints = 0
                g.home_fum_rec = 0
                g.away_rush_yards = 0
                g.away_pass_yards = 0
                g.away_rush_tds = 0
                g.away_pass_tds = 0
                g.away_fgs = 0
                g.away_sacks = 0
                g.away_ints = 0
                g.away_fum_rec = 0
            session.commit()
            session.close()
            logger.info(
                f"Reset {len(orphanedGames)} orphaned games to 'scheduled' and "
                f"deleted {deleted} player stat records for S{season}W{week}"
            )
        except Exception as e:
            logger.warning(f"Failed to clean up orphaned week games: {e}")

    def _cleanupOrphanedPlayoffData(self, season: int, fromWeek: int = 29) -> None:
        """Clean up stale playoff data so replaying playoffs is safe on restart.

        Resets team playoff state, deletes orphaned Game/PlayerStats records,
        unresolves pick-em picks, and removes duplicate prize transactions.
        This is a no-op on first run (nothing to clean up).

        ``fromWeek`` scopes the DB deletions to playoff weeks >= fromWeek. On a
        fresh run it's 29 (the first playoff week), wiping the whole bracket.
        On a mid-playoff resume it's 28 + resumeRound, so already-completed
        rounds are preserved and only the interrupted round (and later) are
        cleared for a clean replay.
        """
        # A. Reset team playoff state to prevent stacked modifiers and stale flags.
        # On resume the survivor list + eliminations are re-applied right after
        # the bracket is rebuilt, so resetting to a clean baseline here is safe.
        teamManager = self.serviceContainer.getService('team_manager')
        from managers.teamManager import logPressureDiag
        seasonNum = self.currentSeason.seasonNumber if self.currentSeason else None
        for team in teamManager.teams:
            team.eliminated = False
            team.leagueChampion = False
            team.pressureModifier = 1.0
            logPressureDiag(team, "playoff_reset", season=seasonNum, week=getattr(self.currentSeason, 'currentWeek', None))

        # B. Clear freeAgencyOrder — it gets rebuilt during playoffs (and is
        # restored from the persisted snapshot on a mid-playoff resume).
        self.currentSeason.freeAgencyOrder = []

        if not DB_IMPORTS_AVAILABLE or not USE_DATABASE:
            return

        try:
            from database.connection import get_session as _getSession
            from database.models import CurrencyTransaction
            from database.repositories.pickem_repository import PickEmRepository

            session = _getSession()

            # C. Delete orphaned playoff Game + GamePlayerStats records for the
            # interrupted round and later (week >= fromWeek). Completed rounds
            # below fromWeek are preserved so a resume keeps their results.
            orphanedGames = session.query(DBGame).filter(
                DBGame.season == season,
                DBGame.is_playoff == True,  # noqa: E712
                DBGame.week >= fromWeek,
            ).all()
            if orphanedGames:
                gameIds = [g.id for g in orphanedGames]
                statsDeleted = session.query(DBGamePlayerStats).filter(
                    DBGamePlayerStats.game_id.in_(gameIds)
                ).delete(synchronize_session='fetch')
                for g in orphanedGames:
                    session.delete(g)
                logger.info(
                    f"Cleaned up {len(orphanedGames)} orphaned playoff games and "
                    f"{statsDeleted} player stat records for S{season}"
                )

            # D. Unresolve pick-em picks for the affected playoff weeks
            # (fromWeek..32) so they re-resolve cleanly on replay.
            pickemRepo = PickEmRepository(session)
            totalUnresolved = 0
            for playoffWeek in range(fromWeek, 33):
                totalUnresolved += pickemRepo.unresolvePicksByWeek(season, playoffWeek)
            if totalUnresolved:
                logger.info(f"Unresolved {totalUnresolved} playoff pick-em picks for S{season}")

            # E. Delete currency transactions for the affected playoff weeks to
            # prevent double prizes on replay (completed rounds keep theirs).
            txDeleted = session.query(CurrencyTransaction).filter(
                CurrencyTransaction.season == season,
                CurrencyTransaction.week >= fromWeek,
                CurrencyTransaction.transaction_type.in_([
                    'pickem_correct', 'pickem_leaderboard_weekly'
                ]),
            ).delete(synchronize_session='fetch')
            if txDeleted:
                logger.info(f"Deleted {txDeleted} orphaned playoff pick-em transactions for S{season}")

            session.commit()
            session.close()
        except Exception as e:
            logger.warning(f"Failed to clean up orphaned playoff data: {e}")

    def _notifyExpiredPowerups(self, season: int, currentWeek: int) -> None:
        """Send notifications and clean up when Accession/Conscription power-ups expire."""
        if not DB_IMPORTS_AVAILABLE or not USE_DATABASE or currentWeek <= 1:
            return
        try:
            from database.connection import get_session as _getSession
            from database.models import (
                ShopPurchase, UserCard, CardTemplate,
                FantasyRoster, FantasyRosterPlayer,
            )
            from database.repositories.notification_repository import NotificationRepository

            session = _getSession()
            # Defensive sweep: catch any stale FLEX rosterPlayers whose powerup
            # expired before this week (covers cases where the precise
            # week-boundary notification didn't fire — server downtime, week
            # skip, etc.). Runs first so the per-week notifications below get
            # a clean state to compare against.
            self._sweepStaleFlexPlayers(session, season, currentWeek)
            # Find all power-ups that expired last week — this drives the
            # one-shot user notification (fires once per purchase).
            expiredPurchases = session.query(ShopPurchase).filter(
                ShopPurchase.item_slug.in_(["temp_card_slot", "temp_flex"]),
                ShopPurchase.season == season,
                ShopPurchase.expires_at_week == currentWeek - 1,
            ).all()

            if not expiredPurchases:
                session.close()
                return

            # Users with an MVP card still have 6 card slots — don't notify for temp_card_slot
            cardSlotUserIds = [p.user_id for p in expiredPurchases if p.item_slug == "temp_card_slot"]
            mvpUserIds = set()
            if cardSlotUserIds:
                mvpRows = (
                    session.query(UserCard.user_id)
                    .join(CardTemplate, UserCard.card_template_id == CardTemplate.id)
                    .filter(
                        UserCard.user_id.in_(cardSlotUserIds),
                        CardTemplate.season_created == season,
                        CardTemplate.classification.isnot(None),
                        CardTemplate.classification.contains("mvp"),
                    )
                    .distinct()
                    .all()
                )
                mvpUserIds = {row[0] for row in mvpRows}

            # Users with a champion card still have FLEX — don't notify/clean for temp_flex
            flexUserIds = [p.user_id for p in expiredPurchases if p.item_slug == "temp_flex"]
            championUserIds = set()
            if flexUserIds:
                from database.models import EquippedCard
                champRows = (
                    session.query(EquippedCard.user_id)
                    .join(UserCard, EquippedCard.user_card_id == UserCard.id)
                    .join(CardTemplate, UserCard.card_template_id == CardTemplate.id)
                    .filter(
                        EquippedCard.user_id.in_(flexUserIds),
                        EquippedCard.season == season,
                        EquippedCard.week == currentWeek,
                        CardTemplate.classification.isnot(None),
                        CardTemplate.classification.contains("champion"),
                    )
                    .distinct()
                    .all()
                )
                championUserIds = {row[0] for row in champRows}

            notifRepo = NotificationRepository(session)
            notifiedCount = 0
            for purchase in expiredPurchases:
                if purchase.item_slug == "temp_card_slot":
                    if purchase.user_id in mvpUserIds:
                        continue
                    notifRepo.create(
                        purchase.user_id,
                        'powerup_expired',
                        'Accession Expired',
                        'Your Accession power-up has expired. The 6th card slot is no longer available.',
                        data={'itemSlug': 'temp_card_slot', 'expiredAtWeek': currentWeek - 1},
                    )
                    notifiedCount += 1
                    logger.info(f"Notified user {purchase.user_id}: Accession expired (was active through week {currentWeek - 1})")

                elif purchase.item_slug == "temp_flex":
                    if purchase.user_id in championUserIds:
                        continue
                    # Remove the FLEX player from the roster
                    roster = session.query(FantasyRoster).filter_by(
                        user_id=purchase.user_id, season=season,
                    ).first()
                    if roster:
                        flexPlayer = session.query(FantasyRosterPlayer).filter_by(
                            roster_id=roster.id, slot="FLEX",
                        ).first()
                        if flexPlayer:
                            session.delete(flexPlayer)
                            logger.info(f"Removed FLEX player for user {purchase.user_id} (Conscription expired)")
                    notifRepo.create(
                        purchase.user_id,
                        'powerup_expired',
                        'Conscription Expired',
                        'Your Conscription power-up has expired. The FLEX roster slot is no longer available.',
                        data={'itemSlug': 'temp_flex', 'expiredAtWeek': currentWeek - 1},
                    )
                    notifiedCount += 1
                    logger.info(f"Notified user {purchase.user_id}: Conscription expired (was active through week {currentWeek - 1})")

            if notifiedCount:
                session.commit()
            session.close()
        except Exception as e:
            logger.warning(f"Failed to notify expired power-ups: {e}")

    def _sweepStaleFlexPlayers(self, session, season: int, currentWeek: int) -> None:
        """Remove FLEX rosterPlayers that no longer have backing entitlement.

        A FLEX slot is granted by an active temp_flex powerup OR a Champion-
        classified card equipped this week. If neither is true, any FLEX
        rosterPlayer is stranded and should be removed. This is a defensive
        sweep — the precise expiration handler runs alongside it but only
        catches the exact week-boundary case.
        """
        try:
            from database.models import (
                ShopPurchase, FantasyRoster, FantasyRosterPlayer,
                EquippedCard, UserCard, CardTemplate,
            )
            staleFlex = (
                session.query(FantasyRosterPlayer)
                .join(FantasyRoster, FantasyRosterPlayer.roster_id == FantasyRoster.id)
                .filter(
                    FantasyRosterPlayer.slot == "FLEX",
                    FantasyRoster.season == season,
                )
                .all()
            )
            removed = 0
            for rp in staleFlex:
                userId = rp.roster.user_id
                # Active temp_flex?
                hasActiveFlex = session.query(ShopPurchase.id).filter(
                    ShopPurchase.user_id == userId,
                    ShopPurchase.season == season,
                    ShopPurchase.item_slug == "temp_flex",
                    ShopPurchase.expires_at_week >= currentWeek,
                ).first() is not None
                if hasActiveFlex:
                    continue
                # Champion card equipped recently? The sweep runs at week
                # rollover BEFORE carry-forward fills the new week's rows,
                # so checking week == currentWeek would miss a Champion that
                # the user clearly still has equipped (just not yet copied
                # over). Use the latest week we have equipped data for to
                # answer "is Champion still in the loadout?".
                from sqlalchemy import func
                latestEqWeek = session.query(func.max(EquippedCard.week)).filter(
                    EquippedCard.user_id == userId,
                    EquippedCard.season == season,
                    EquippedCard.week <= currentWeek,
                ).scalar()
                hasChampion = False
                if latestEqWeek is not None:
                    hasChampion = (
                        session.query(EquippedCard.id)
                        .join(UserCard, EquippedCard.user_card_id == UserCard.id)
                        .join(CardTemplate, UserCard.card_template_id == CardTemplate.id)
                        .filter(
                            EquippedCard.user_id == userId,
                            EquippedCard.season == season,
                            EquippedCard.week == latestEqWeek,
                            CardTemplate.classification.isnot(None),
                            CardTemplate.classification.contains("champion"),
                        )
                        .limit(1).count()
                    ) > 0
                if hasChampion:
                    continue
                session.delete(rp)
                removed += 1
            if removed:
                session.commit()
                logger.info(f"Swept {removed} stale FLEX rosterPlayer(s) at week {currentWeek}")
        except Exception as e:
            logger.warning(f"Failed to sweep stale FLEX players: {e}")

    def _saveGameToDatabase(self, game: FloosGame.Game) -> None:
        """Save a completed game to the database"""
        try:
            # If the game was pre-inserted at schedule creation time, update that row
            if getattr(game, 'dbId', None):
                db_game = self.db_session.get(DBGame, game.dbId)
                if db_game:
                    db_game.home_score = game.homeScore
                    db_game.away_score = game.awayScore
                    db_game.status = 'final'
                    db_game.is_overtime = game.isOvertimeGame if hasattr(game, 'isOvertimeGame') else False
                    db_game.is_playoff = game.isPlayoff if hasattr(game, 'isPlayoff') else False
                    db_game.playoff_round = getattr(game, 'playoffRound', None)
                    db_game.total_plays = game.totalPlays if hasattr(game, 'totalPlays') else None
                    # ⚠️ The quarter line comes off `homeScoreQ1..Q4` / `homeScoreOT`, which is what the
                    # engine actually accumulates (`floosball_game` ~:12308). This used to read a
                    # `homeScoresByQuarter` LIST that has never existed on the game object, so the
                    # `hasattr` guard was always False and every quarter column stayed 0 — measured at
                    # 0 of 783 finished games. Nothing errored, which is why it survived.
                    for _side, _tgt in (('home', 'home'), ('away', 'away')):
                        for _q in ('q1', 'q2', 'q3', 'q4'):
                            setattr(db_game, f'{_tgt}_score_{_q}',
                                    getattr(game, f'{_side}Score{_q.upper()}', 0) or 0)
                        setattr(db_game, f'{_tgt}_score_ot', getattr(game, f'{_side}ScoreOT', 0) or 0)
                    self._applyGameStatsToRow(db_game, game.gameDict.get('gameStats'))
                    self._applyFormatStateToRow(db_game, game)
                    self._applyTeamStatsToRow(db_game, game)
                    self.db_session.flush()
                    playerStats = self._extractPlayerStatsFromGame(game)
                    if playerStats:
                        self._savePlayerGameStats(db_game.id, playerStats)
                    self.db_session.commit()
                    logger.debug(f"Updated game in database: {game.awayTeam.abbr} @ {game.homeTeam.abbr}, Score: {game.awayScore}-{game.homeScore}")
                    return

            # No pre-existing row — fall through to INSERT (playoff games and backward compat)
            # Create database game record
            db_game = DBGame(
                season=self.currentSeason.seasonNumber,
                week=self.currentSeason.currentWeek,
                home_team_id=game.homeTeam.id,
                away_team_id=game.awayTeam.id,
                home_score=game.homeScore,
                away_score=game.awayScore,
                is_overtime=game.isOvertimeGame if hasattr(game, 'isOvertimeGame') else False,
                is_playoff=game.isPlayoff if hasattr(game, 'isPlayoff') else False,
                playoff_round=getattr(game, 'playoffRound', None),
                total_plays=game.totalPlays if hasattr(game, 'totalPlays') else None,
                status='final',
            )
            
            # Save quarter scores if available
            # Same fix as the UPDATE path above: read the attributes the engine really
            # keeps, not a list that has never existed.
            for _side in ('home', 'away'):
                for _q in ('q1', 'q2', 'q3', 'q4'):
                    setattr(db_game, f'{_side}_score_{_q}',
                            getattr(game, f'{_side}Score{_q.upper()}', 0) or 0)
                setattr(db_game, f'{_side}_score_ot', getattr(game, f'{_side}ScoreOT', 0) or 0)
            
            self._applyGameStatsToRow(db_game, game.gameDict.get('gameStats'))
            self._applyFormatStateToRow(db_game, game)
            self._applyTeamStatsToRow(db_game, game)
            self.game_repo.save(db_game)
            self.db_session.flush()  # Get the ID

            # Save player stats from game rosters
            playerStats = self._extractPlayerStatsFromGame(game)
            if playerStats:
                self._savePlayerGameStats(db_game.id, playerStats)
            
            self.db_session.commit()
            logger.debug(f"Saved game to database: {game.awayTeam.abbr} @ {game.homeTeam.abbr}, Score: {game.awayScore}-{game.homeScore}")
            
        except Exception as e:
            logger.error(f"Failed to save game to database: {e}")
            self.db_session.rollback()
    
    def _extractPlayerStatsFromGame(self, game) -> Dict:
        """Extract per-player game stats from a Game object's team rosters."""
        playerStats = {}
        for team in [game.homeTeam, game.awayTeam]:
            if not hasattr(team, 'rosterDict'):
                continue
            for player in team.rosterDict.values():
                if not player or not hasattr(player, 'gameStatsDict'):
                    continue
                gd = player.gameStatsDict
                # Only include players who actually participated
                defStats = gd.get('defense', {})
                hasDefenseStats = (
                    defStats.get('sacks', 0) > 0
                    or defStats.get('ints', 0) > 0
                    or defStats.get('tackles', 0) > 0
                    or defStats.get('tfl', 0) > 0
                    or defStats.get('forcedFumbles', 0) > 0
                    or defStats.get('passBreakups', 0) > 0
                )
                hasStats = (
                    gd.get('passing', {}).get('att', 0) > 0
                    or gd.get('rushing', {}).get('carries', 0) > 0
                    or gd.get('receiving', {}).get('targets', 0) > 0
                    or gd.get('kicking', {}).get('fgAtt', 0) > 0
                    or gd.get('kicking', {}).get('xpAtt', 0) > 0
                    or gd.get('fantasyPoints', 0) != 0
                    or hasDefenseStats
                )
                if hasStats:
                    # _accumulatePostgameStats zeroes gd['fantasyPoints'] inside
                    # playGame(), so by the time we get here it's 0.  Use the
                    # preserved value stashed on the player object instead.
                    gameFP = getattr(player, '_lastGameFantasyPoints', None)
                    if gameFP is None:
                        gameFP = gd.get('fantasyPoints', 0)
                    # Get Q4 FP + scoring play count from fantasy tracker
                    fantasyTracker = self.serviceContainer.getService('fantasy_tracker') if self.serviceContainer else None
                    q4FP = fantasyTracker._weekQ4FP.get(player.id, 0) if fantasyTracker else 0
                    q4Scores = fantasyTracker._weekQ4Scores.get(player.id, 0) if fantasyTracker else 0
                    playerStats[player.id] = {
                        'teamId': team.id,
                        'fantasyPoints': gameFP,
                        'q4FantasyPoints': q4FP,
                        'q4ScoringPlays': q4Scores,
                        # Per-game WPA value (preserved on the player at postgame,
                        # like _lastGameFantasyPoints — gameStatsDict is regenerated)
                        'wpa': float(getattr(player, '_lastGameWpa', 0.0)),
                        'defWpa': float(getattr(player, '_lastGameDefWpa', 0.0)),
                        'wpaSnaps': int(getattr(player, '_lastGameWpaSnaps', 0)),
                        'defSnaps': int(getattr(player, '_lastGameDefWpaSnaps', 0)),
                        'passing': gd.get('passing'),
                        'rushing': gd.get('rushing'),
                        'receiving': gd.get('receiving'),
                        'kicking': gd.get('kicking'),
                        'defense': gd.get('defense'),
                    }
        return playerStats

    def _savePlayerGameStats(self, game_id: int, player_stats: Dict) -> None:
        """Save player game statistics to database"""
        try:
            for player_id, stats in player_stats.items():
                if isinstance(stats, dict):
                    db_stats = DBGamePlayerStats(
                        game_id=game_id,
                        player_id=player_id,
                        team_id=stats.get('teamId', 0),
                        fantasy_points=stats.get('fantasyPoints', 0),
                        q4_fantasy_points=stats.get('q4FantasyPoints', 0),
                        q4_scoring_plays=stats.get('q4ScoringPlays', 0),
                        wpa=stats.get('wpa', 0.0),
                        def_wpa=stats.get('defWpa', 0.0),
                        wpa_snaps=stats.get('wpaSnaps', 0),
                        def_snaps=stats.get('defSnaps', 0),
                        passing_stats=stats.get('passing'),
                        rushing_stats=stats.get('rushing'),
                        receiving_stats=stats.get('receiving'),
                        kicking_stats=stats.get('kicking'),
                        defense_stats=stats.get('defense'),
                        # Punt-return production. The season and career save paths
                        # already persisted this; the per-game write dropped it, so
                        # returning_stats was NULL on every game row and a returner's
                        # work never reached the box score, the card layer (which reads
                        # per-game stats) or the season backfill.
                        returning_stats=stats.get('returning'),
                    )
                    self.game_repo.save_player_stats(db_stats)
        except Exception as e:
            logger.error(f"Failed to save player game stats: {e}")
    
    def _updateTeamRecords(self, game) -> None:
        """Update team win/loss records"""
        try:
            homeTeam = game.homeTeam
            awayTeam = game.awayTeam
            
            # Check if game has score attributes
            if not hasattr(game, 'homeScore') or not hasattr(game, 'awayScore'):
                logger.error(f"Game object missing score attributes: {dir(game)}")
                return
                
            # Initialize season stats if needed
            if not hasattr(homeTeam, 'seasonTeamStats'):
                homeTeam.seasonTeamStats = {'wins': 0, 'losses': 0}
            if not hasattr(awayTeam, 'seasonTeamStats'):
                awayTeam.seasonTeamStats = {'wins': 0, 'losses': 0}
            
            # Ensure stats are initialized
            homeTeam.seasonTeamStats.setdefault('wins', 0)
            homeTeam.seasonTeamStats.setdefault('losses', 0)
            awayTeam.seasonTeamStats.setdefault('wins', 0)
            awayTeam.seasonTeamStats.setdefault('losses', 0)
        
            
            # Update all-time records
            if not hasattr(homeTeam, 'allTimeTeamStats'):
                homeTeam.allTimeTeamStats = {'wins': 0, 'losses': 0}
            if not hasattr(awayTeam, 'allTimeTeamStats'):
                awayTeam.allTimeTeamStats = {'wins': 0, 'losses': 0}
                
            if game.homeScore > game.awayScore:
                homeTeam.allTimeTeamStats['wins'] += 1
                awayTeam.allTimeTeamStats['losses'] += 1
            else:
                awayTeam.allTimeTeamStats['wins'] += 1
                homeTeam.allTimeTeamStats['losses'] += 1
                
        except Exception as e:
            logger.error(f"Error updating team records: {e}")
            logger.error(f"Game attributes: {dir(game) if hasattr(game, '__dict__') else 'No __dict__'}")
    
    def _syncGameIdCounter(self) -> None:
        """Advance the game-id counter past the highest game id already in the DB
        so newly created games never reuse an existing id. A restart/resume resets
        the in-memory counter to 0; without this, new games collide with old games
        and inherit their play_reactions (phantom reactions from other users) and
        any other game-id-keyed data. Monotonic — never lowers the counter."""
        try:
            if not (DB_IMPORTS_AVAILABLE and USE_DATABASE and self.db_session):
                return
            from database.models import Game as _DBGame
            from sqlalchemy import func as _func
            dbMax = self.db_session.query(_func.max(_DBGame.id)).scalar() or 0
            if int(dbMax) > self._gameIdCounter:
                self._gameIdCounter = int(dbMax)
        except Exception as e:
            logger.warning(f"_syncGameIdCounter failed: {e}")

    def _maybeRealignLeagues(self, seasonNumber: int, resumeFromWeek: int) -> None:
        """Fire the one-time league realignment exactly once, at a genuine new-season
        boundary before the schedule generates. Gated by the `league_realigned`
        app_setting so it never re-runs — this is a one-shot rebalance, not a recurring
        re-seed. Skipped on a mid-season restart, and when this season's schedule
        already exists (season already underway). If there's no completed-season
        history yet the realign is a no-op and stays unstamped, so it retries at the
        next boundary once data exists."""
        if resumeFromWeek > 0:
            return
        try:
            from game_rules import _readAppSetting, _writeAppSetting
        except Exception:
            return
        if _readAppSetting('league_realigned'):
            return
        try:
            if self.game_repo and self.game_repo.has_schedule(seasonNumber):
                return  # season already has a schedule — too late to realign it
        except Exception:
            pass
        if not self.leagueManager:
            return
        try:
            from constants import LEAGUE_REALIGN_WINDOW_SEASONS
        except Exception:
            LEAGUE_REALIGN_WINDOW_SEASONS = 2
        summary = self.leagueManager.realignByRecentPerformance(
            seasonNumber, LEAGUE_REALIGN_WINDOW_SEASONS)
        if not summary:
            return  # no history yet — leave unstamped to retry next season
        _writeAppSetting('league_realigned', str(seasonNumber))
        moved = summary.get('moved', [])
        logger.info(
            f"League realignment (season {seasonNumber}, window {summary.get('window')}): "
            f"{len(moved)} teams changed leagues")
        for m in moved:
            logger.info(f"  {m['team']}: {m['from']} -> {m['to']}")

    def createSchedule(self) -> None:
        """Generate season schedule (matches original floosball.py algorithm)"""
        import floosball_team as FloosTeam
        if not self.currentSeason:
            return
        # Never reuse a game id already in the DB (else new games inherit old
        # games' reactions/stats on a restart).
        self._syncGameIdCounter()
            
        logger.info("Creating season schedule using original algorithm")
        
        # Ensure we have exactly 2 leagues (original assumption)
        if len(self.leagueManager.leagues) != 2:
            logger.error(f"Original algorithm expects exactly 2 leagues, found {len(self.leagueManager.leagues)}")
            return
            
        # Generate full season schedule using original algorithm
        schedule = self._generateSchedule()
        self.currentSeason.schedule.clear()
        dateTimeNow = datetime.datetime.utcnow()

        # ⚠️ The schedule's OWN length, not a formula. This was
        #     ((teamsPerLeague - 1) * 2) + teamsPerLeague / 2
        # which is the length of the pre-divisional double round-robin plus interleague
        # — 38 for two leagues of 16. The divisional generator returns 28, so the loop
        # below iterated ten weeks past the end of its own input and the log announced a
        # "38-week schedule" for a 28-week season. Anything reading that number, or the
        # range it drives, was working from the wrong length of season.
        numOfWeeks = len(schedule)
        
        # Convert generated schedule to our current season format
        for week in range(numOfWeeks):
            if week < len(schedule):
                gameList = []
                weekGames = schedule[week]
                numOfGames = len(weekGames)
                weekStartTime = self.getWeekStartTime(dateTimeNow, week)
                for x in range(numOfGames):
                    game = weekGames[x]
                    homeTeam: FloosTeam.Team = game[0] 
                    awayTeam: FloosTeam.Team = game[1]
                    newGame: FloosGame.Game = FloosGame.Game(homeTeam=homeTeam, awayTeam=awayTeam, timingManager=self.timingManager, personalityManager=self.serviceContainer.getService('personality_manager'), gameRules=self.currentSeason.gameRules)
                    
                    # Assign unique integer ID and metadata
                    self._gameIdCounter += 1
                    newGame.id = self._gameIdCounter
                    newGame.seasonNumber = self.currentSeason.seasonNumber
                    newGame.week = week
                    newGame.gameNumber = x
                    newGame.gameType = 'regular'
                    
                    newGame.status = FloosGame.GameStatus.Scheduled
                    newGame.isRegularSeasonGame = True
                    newGame.startTime = weekStartTime

                    # Persist scheduled game to DB immediately so resume can reconstruct the schedule
                    if DB_IMPORTS_AVAILABLE and USE_DATABASE and self.game_repo:
                        dbRow = DBGame(
                            season=self.currentSeason.seasonNumber,
                            week=week + 1,  # store 1-indexed
                            home_team_id=homeTeam.id,
                            away_team_id=awayTeam.id,
                            game_date=weekStartTime,
                            status='scheduled',
                        )
                        self.game_repo.save(dbRow)
                        self.db_session.flush()
                        newGame.dbId = dbRow.id

                    homeTeam.schedule.append(newGame)
                    awayTeam.schedule.append(newGame)
                    gameList.append(newGame)
                self.currentSeason.schedule.append({'startTime': weekStartTime, 'games': gameList})

        if DB_IMPORTS_AVAILABLE and USE_DATABASE and self.game_repo:
            try:
                self.db_session.commit()
                logger.debug(f"Persisted {numOfWeeks}-week schedule to database")
            except Exception as e:
                logger.error(f"Failed to persist schedule to database: {e}")
                self.db_session.rollback()

        logger.info(f"Created {numOfWeeks}-week schedule with {len(self.currentSeason.schedule)} games")

    def _loadScheduleFromDatabase(self, seasonNumber: int) -> bool:
        """Reconstruct in-memory schedule from persisted DB rows.

        Returns True if the schedule was successfully loaded, False if it should
        fall back to fresh schedule generation.
        """
        if not (DB_IMPORTS_AVAILABLE and USE_DATABASE and self.game_repo):
            return False

        rows = self.game_repo.get_by_season_ordered(seasonNumber)
        if not rows:
            return False

        teamManager = self.serviceContainer.getService('team_manager')
        if not teamManager:
            logger.error("TeamManager not available for schedule reconstruction")
            return False

        teamById = {t.id: t for t in teamManager.teams}

        # ⚠️ Reset every team's schedule before refilling it. The loop below APPENDS each
        # game to `homeTeam.schedule` / `awayTeam.schedule`, and the only two places that
        # clear those lists are new-season paths (`teamManager` season roll-over and
        # `clearTeamSeasonStats`) — neither of which runs on a RESUME. So every restart
        # that resumed an existing season stacked another full copy of the season onto each
        # team, and a team page showed 56 weeks after one restart, 84 after two.
        #
        # `currentSeason.schedule` was never affected because it is ASSIGNED at the end of
        # this function rather than appended to, which is why the games table and the
        # league schedule both stayed at 28 weeks while team pages did not.
        for team in teamManager.teams:
            team.schedule = []

        now = datetime.datetime.utcnow()
        weekMap: Dict[int, Dict] = {}  # 1-indexed week → {startTime, games}

        for row in rows:
            homeTeam = teamById.get(row.home_team_id)
            awayTeam = teamById.get(row.away_team_id)
            if not homeTeam or not awayTeam:
                logger.error(f"Team not found for DB game id={row.id} "
                             f"(home={row.home_team_id}, away={row.away_team_id}); aborting schedule load")
                return False

            newGame = FloosGame.Game(homeTeam=homeTeam, awayTeam=awayTeam,
                                     timingManager=self.timingManager,
                                     personalityManager=self.serviceContainer.getService('personality_manager'),
                                     gameRules=self.currentSeason.gameRules)
            # Use the REAL DB id as the game's id, NOT a fresh per-run counter.
            # play_reactions (and the frontend) key off game.id, so reassigning
            # sequential counter ids on resume made new games collide with old
            # games' reactions — the "phantom reactions from other users" bug.
            # Keep the counter past the highest loaded id for games created later.
            newGame.id = row.id
            newGame.dbId = row.id
            if row.id > self._gameIdCounter:
                self._gameIdCounter = row.id
            newGame.seasonNumber = seasonNumber
            newGame.week = row.week - 1   # 0-indexed (matches original createSchedule convention)
            newGame.gameType = 'playoff' if row.is_playoff else 'regular'
            newGame.isRegularSeasonGame = not row.is_playoff
            newGame.status = (FloosGame.GameStatus.Final if row.status == 'final'
                              else FloosGame.GameStatus.Scheduled)
            newGame.homeScore = row.home_score or 0
            newGame.awayScore = row.away_score or 0

            # Always recompute start times from the 0-indexed week to avoid
            # stale or incorrect game_date values stored in the DB.
            weekIdx = row.week - 1
            startTime = self.getWeekStartTime(now, weekIdx)
            newGame.startTime = startTime

            # Reconstruct minimal gameDict['gameStats'] from stored columns so
            # getAverages() can include this game when calculating season averages.
            if row.status == 'final' and row.home_rush_yards is not None:
                hRushYds = row.home_rush_yards or 0
                hPassYds = row.home_pass_yards or 0
                aRushYds = row.away_rush_yards or 0
                aPassYds = row.away_pass_yards or 0
                hRushTds = row.home_rush_tds or 0
                hPassTds = row.home_pass_tds or 0
                aRushTds = row.away_rush_tds or 0
                aPassTds = row.away_pass_tds or 0
                newGame.gameDict['gameStats'] = {
                    'homeTeam': {
                        'offense': {
                            'rushYards': hRushYds, 'passYards': hPassYds,
                            'totalYards': hRushYds + hPassYds,
                            'runTds': hRushTds, 'passTds': hPassTds,
                            'tds': hRushTds + hPassTds,
                            'fgs': row.home_fgs or 0,
                            'score': row.home_score,
                        },
                        'defense': {
                            'sacks': row.home_sacks or 0,
                            'ints': row.home_ints or 0,
                            'fumRec': row.home_fum_rec or 0,
                            'passYardsAlwd': aPassYds, 'runYardsAlwd': aRushYds,
                            'totalYardsAlwd': aRushYds + aPassYds,
                            'passTdsAlwd': aPassTds, 'runTdsAlwd': aRushTds,
                            'tdsAlwd': aRushTds + aPassTds,
                            'ptsAlwd': row.away_score,
                        },
                    },
                    'awayTeam': {
                        'offense': {
                            'rushYards': aRushYds, 'passYards': aPassYds,
                            'totalYards': aRushYds + aPassYds,
                            'runTds': aRushTds, 'passTds': aPassTds,
                            'tds': aRushTds + aPassTds,
                            'fgs': row.away_fgs or 0,
                            'score': row.away_score,
                        },
                        'defense': {
                            'sacks': row.away_sacks or 0,
                            'ints': row.away_ints or 0,
                            'fumRec': row.away_fum_rec or 0,
                            'passYardsAlwd': hPassYds, 'runYardsAlwd': hRushYds,
                            'totalYardsAlwd': hRushYds + hPassYds,
                            'passTdsAlwd': hPassTds, 'runTdsAlwd': hRushTds,
                            'tdsAlwd': hRushTds + hPassTds,
                            'ptsAlwd': row.home_score,
                        },
                    },
                }

            if row.week not in weekMap:
                weekMap[row.week] = {'startTime': startTime, 'games': []}
            weekMap[row.week]['games'].append(newGame)

            homeTeam.schedule.append(newGame)
            awayTeam.schedule.append(newGame)

        self.currentSeason.schedule = [weekMap[w] for w in sorted(weekMap)]
        logger.info(f"Loaded {len(rows)} games ({len(weekMap)} weeks) from DB for season {seasonNumber}")
        return True

    def _recalculateScheduleTimes(self) -> None:
        """Patch all schedule start times using the current getWeekStartTime logic.

        This runs after the schedule is loaded (from DB or freshly created) to
        guarantee times use the correct EDT/EST offset.  It's a belt-and-suspenders
        guard against stale DB game_date values or bytecode-cache issues during
        startup."""
        if not self.currentSeason or not self.currentSeason.schedule:
            return
        now = datetime.datetime.utcnow()
        patched = 0
        for weekIdx, weekDict in enumerate(self.currentSeason.schedule):
            correctTime = self.getWeekStartTime(now, weekIdx)
            oldTime = weekDict.get('startTime')
            if oldTime != correctTime:
                patched += 1
            weekDict['startTime'] = correctTime
            for game in weekDict.get('games', []):
                game.startTime = correctTime
        if patched:
            logger.info(f"Recalculated start times for {patched}/{len(self.currentSeason.schedule)} weeks")

    def _fillMissingScheduleWeeks(self, seasonNumber: int) -> None:
        """Detect and fill missing or incomplete weeks in the DB before schedule load.

        Handles two scenarios:
        1. Entire week missing (all games deleted by old orphan cleanup)
        2. Incomplete week (some games deleted, leaving teams without a matchup)

        For missing weeks, generates random matchups.  For incomplete weeks,
        pairs up only the unscheduled teams and inserts new games.
        """
        if not (DB_IMPORTS_AVAILABLE and USE_DATABASE and self.game_repo):
            return

        leagueTeamCount = len(self.leagueManager.leagues[0].teamList) if self.leagueManager.leagues else 0
        if leagueTeamCount == 0:
            return

        expectedWeeks = int(((leagueTeamCount - 1) * 2) + (leagueTeamCount / 2))
        expectedGamesPerWeek = leagueTeamCount // 2

        import random
        from sqlalchemy import distinct, func
        teamManager = self.serviceContainer.getService('team_manager')
        if not teamManager:
            return
        allTeams = list(teamManager.teams)
        allTeamIds = {t.id for t in allTeams}
        teamById = {t.id: t for t in allTeams}
        now = datetime.datetime.utcnow()

        # Query game counts per week and teams scheduled per week
        rows = self.game_repo.get_by_season_ordered(seasonNumber)
        weekTeams: Dict[int, set] = {}   # week → set of team IDs with games
        weekMatchups: Dict[int, set] = {}  # week → set of (min_id, max_id) pairs
        for row in rows:
            weekTeams.setdefault(row.week, set()).update({row.home_team_id, row.away_team_id})
            pair = (min(row.home_team_id, row.away_team_id), max(row.home_team_id, row.away_team_id))
            weekMatchups.setdefault(row.week, set()).add(pair)

        existingWeeks = set(weekTeams.keys())
        missingWeeks = set(range(1, expectedWeeks + 1)) - existingWeeks
        incompleteWeeks = {
            w for w in existingWeeks
            if w <= expectedWeeks and len(weekTeams.get(w, set())) < leagueTeamCount
        }

        if not missingWeeks and not incompleteWeeks:
            return

        if missingWeeks:
            logger.warning(f"Detected {len(missingWeeks)} missing week(s): {sorted(missingWeeks)}")
        if incompleteWeeks:
            logger.warning(f"Detected {len(incompleteWeeks)} incomplete week(s): {sorted(incompleteWeeks)}")

        for missingWeek in sorted(missingWeeks):
            avoidPairs = weekMatchups.get(missingWeek - 1, set()) | weekMatchups.get(missingWeek + 1, set())

            # Generate random pairings that avoid adjacent-week repeats
            pairings = None
            for _attempt in range(200):
                shuffled = allTeams[:]
                random.shuffle(shuffled)
                candidate = [(shuffled[i], shuffled[i + 1]) for i in range(0, len(shuffled), 2)]
                candidatePairs = {(min(h.id, a.id), max(h.id, a.id)) for h, a in candidate}
                if not candidatePairs & avoidPairs:
                    pairings = candidate
                    break

            if pairings is None:
                logger.warning(f"Could not avoid back-to-back matchups for week {missingWeek}, using best effort")
                shuffled = allTeams[:]
                random.shuffle(shuffled)
                pairings = [(shuffled[i], shuffled[i + 1]) for i in range(0, len(shuffled), 2)]

            weekIdx = missingWeek - 1
            startTime = self.getWeekStartTime(now, weekIdx)

            for homeTeam, awayTeam in pairings:
                dbRow = DBGame(
                    season=seasonNumber,
                    week=missingWeek,
                    home_team_id=homeTeam.id,
                    away_team_id=awayTeam.id,
                    game_date=startTime,
                    status='scheduled',
                )
                self.game_repo.save(dbRow)

            try:
                self.db_session.commit()
                logger.info(f"Reconstructed week {missingWeek} with {len(pairings)} games")
            except Exception as e:
                logger.error(f"Failed to reconstruct week {missingWeek}: {e}")
                self.db_session.rollback()

        # Fill incomplete weeks: pair up teams that have no game in that week
        for incWeek in sorted(incompleteWeeks):
            scheduledTeamIds = weekTeams.get(incWeek, set())
            missingTeamIds = allTeamIds - scheduledTeamIds
            if len(missingTeamIds) < 2:
                continue
            missingTeamList = [teamById[tid] for tid in missingTeamIds if tid in teamById]
            if len(missingTeamList) % 2 != 0:
                logger.warning(f"Odd number of unscheduled teams ({len(missingTeamList)}) for week {incWeek}, skipping one")
                missingTeamList = missingTeamList[:-1]

            avoidPairs = weekMatchups.get(incWeek - 1, set()) | weekMatchups.get(incWeek + 1, set())
            pairings = None
            for _attempt in range(200):
                random.shuffle(missingTeamList)
                candidate = [(missingTeamList[i], missingTeamList[i + 1]) for i in range(0, len(missingTeamList), 2)]
                candidatePairs = {(min(h.id, a.id), max(h.id, a.id)) for h, a in candidate}
                if not candidatePairs & avoidPairs:
                    pairings = candidate
                    break
            if pairings is None:
                random.shuffle(missingTeamList)
                pairings = [(missingTeamList[i], missingTeamList[i + 1]) for i in range(0, len(missingTeamList), 2)]

            weekIdx = incWeek - 1
            startTime = self.getWeekStartTime(now, weekIdx)
            for homeTeam, awayTeam in pairings:
                dbRow = DBGame(
                    season=seasonNumber,
                    week=incWeek,
                    home_team_id=homeTeam.id,
                    away_team_id=awayTeam.id,
                    game_date=startTime,
                    status='scheduled',
                )
                self.game_repo.save(dbRow)
            try:
                self.db_session.commit()
                logger.info(f"Filled incomplete week {incWeek}: added {len(pairings)} games for {len(missingTeamIds)} unscheduled teams")
            except Exception as e:
                logger.error(f"Failed to fill incomplete week {incWeek}: {e}")
                self.db_session.rollback()

    def _restoreSeasonStartDate(self, seasonNumber: int) -> None:
        """Restore startDate from the DB so playoff/week scheduling stays anchored
        to the original season start rather than the current restart time."""
        try:
            from database.models import Season as DBSeason
            dbSeason = self.db_session.query(DBSeason).filter_by(season_number=seasonNumber).first()
            if dbSeason and dbSeason.start_date:
                self.currentSeason.startDate = dbSeason.start_date
                logger.info(f"Restored season start date from DB: {dbSeason.start_date.isoformat()}")
        except Exception as e:
            logger.warning(f"Could not restore season start date: {e}")

    def getWeekStartTime(self, now:datetime.datetime, week:int):
        from managers.timingManager import TimingMode

        # TEST_SCHEDULED: compressed timeline — each round starts gap seconds apart
        if self.timingManager.mode == TimingMode.TEST_SCHEDULED:
            if not hasattr(self, '_testScheduleAnchor'):
                self._testScheduleAnchor = datetime.datetime.utcnow()
            gap = self.timingManager.scheduleGap
            return self._testScheduleAnchor + datetime.timedelta(seconds=week * gap)

        # PLAYOFF_TEST: regular season gets no scheduling (returns now);
        # playoffs use compressed real scheduling from a playoff-start anchor
        if self.timingManager.mode == TimingMode.PLAYOFF_TEST:
            if week > 28:
                gap = self.timingManager.scheduleGap
                anchor = getattr(self, '_testPlayoffAnchor', datetime.datetime.utcnow())
                return anchor + datetime.timedelta(seconds=(week - 28) * gap)
            else:
                return now  # Already past → no wait

        # Hours are in Eastern time
        startTimeHoursList = [12, 13, 14, 15, 16, 17, 18]

        if week > 28:
            # Playoffs: anchored to season start date, all 4 rounds on day 4 (Fri).
            # Regular season uses days 0–3 (Mon–Thu).  Saturday is for offseason/FA.
            # Round 1 → 12 PM ET, Round 2 → 1 PM ET, etc.
            playoffRound = week - 28  # 1-based: 1, 2, 3, 4
            playoffHours = {1: 12, 2: 13, 3: 14, 4: 15}
            etHour = playoffHours.get(playoffRound, 12)
            seasonStart = self.currentSeason.startDate if self.currentSeason else now
            targetDate = (seasonStart + datetime.timedelta(days=4)).date()
        else:
            # Regular season: 28 rounds across 4 game days (7 rounds/day), anchored to
            # the season's actual start date instead of "next Thursday"
            etHour = startTimeHoursList[week % 7]
            dayNumber = math.floor(week / 7)  # 0–3
            seasonStart = self.currentSeason.startDate if self.currentSeason else now
            targetDate = (seasonStart + datetime.timedelta(days=dayNumber)).date()

        # Convert ET hour to UTC manually — avoids reliance on container tzdata
        # which can be stale and return EST offsets for EDT dates.
        utcOffset = 4 if _isEdt(targetDate) else 5
        targetUtc = datetime.datetime(targetDate.year, targetDate.month, targetDate.day, etHour + utcOffset)
        return targetUtc

    def getNextGameStartTime(self, currentWeek: int) -> 'datetime.datetime | None':
        """Return the start time of the next week's games, or None if no next week.

        For SCHEDULED / TEST_SCHEDULED modes the time comes from the schedule.
        For SEQUENTIAL / TURBO modes we estimate from delay config.
        For FAST mode we return None (no meaningful wait).
        """
        from managers.timingManager import TimingMode

        if self.timingManager.mode == TimingMode.FAST:
            return None

        schedule = self.currentSeason.schedule if self.currentSeason else []
        nextIndex = currentWeek  # schedule is 0-indexed, currentWeek is 1-indexed

        if self.timingManager._isScheduledMode:
            # Look up from schedule directly
            if nextIndex < len(schedule):
                return schedule[nextIndex]['startTime']
            # Playoff rounds aren't pre-scheduled — compute on demand
            if currentWeek >= 28 and self.currentSeason and not self.currentSeason.isComplete:
                return self.getWeekStartTime(datetime.datetime.utcnow(), currentWeek + 1)
            return None

        # SEQUENTIAL / TURBO: return cached timestamp if available
        if self._cachedNextGameStart is not None:
            return self._cachedNextGameStart

        # Compute once and cache
        delays = self.timingManager.delays
        gap = delays.get('week_end_wait', 120) + delays.get('week_start_wait', 30) + delays.get('game_announcement', 30)
        self._cachedNextGameStart = datetime.datetime.utcnow() + datetime.timedelta(seconds=gap)
        return self._cachedNextGameStart

    def _generateSchedule(self) -> List[List[tuple]]:
        """Generate full season schedule using original algorithm"""
        import random
        import copy
        
        schedule = []
        
        # Get copies of league team lists
        league1Teams = copy.copy(self.leagueManager.leagues[0].teamList)
        league2Teams = copy.copy(self.leagueManager.leagues[1].teamList)
        
        # Divisional format first (32 clubs / 4 divisions). Returns None and falls
        # through to the original round-robin for any other league shape.
        divisional = self._generateDivisionalSchedule()
        if divisional is not None:
            return divisional

        # ⚠️ SAY SO. The fallback is a double round-robin plus interleague, which for two
        # 16-club leagues is a THIRTY-EIGHT week season — ten weeks past the 28 the
        # calendar, the playoff weeks (29+) and every downstream week check assume. It
        # used to happen in silence, so a league that was briefly mis-shaped (one club
        # renamed in `teams` but not in `teamDistribution`, which is exactly what
        # happened on 2026-08-09) generated a 38-week schedule, persisted it, and nobody
        # noticed until week 31 arrived with a full 16-game slate and no playoffs.
        #
        # A club count that SHOULD be divisional is a misconfiguration, not a format
        # choice, so it is logged at ERROR with the shape that caused it.
        try:
            sizes = [len(l.teamList) for l in self.leagueManager.leagues]
        except Exception:
            sizes = []
        logger.error(
            "SCHEDULE: the divisional format did NOT apply — falling back to the "
            f"round-robin. League sizes {sizes} (need exactly two leagues of 16 that "
            f"divide into {self.DIVISIONS_PER_LEAGUE} divisions). The fallback runs far "
            "past 28 weeks, so playoffs will not start on time. Check config.json's "
            "teamDistribution covers every club in `teams`."
        )

        # Generate different types of games
        league1Games = self._generateIntraleagueGames(league1Teams)
        league2Games = self._generateIntraleagueGames(league2Teams)
        interleagueGames = self._generateInterleagueGames(copy.copy(league1Teams), copy.copy(league2Teams))
        
        # Combine intra-league games by week
        intraleagueGames = []
        for x in range(len(league1Games)):
            week = []
            week.extend(league1Games[x])
            week.extend(league2Games[x])
            intraleagueGames.append(week)
        
        # Combine all games and shuffle (matches original)
        schedule = interleagueGames + intraleagueGames
        random.shuffle(schedule)

        # Post-process: ensure no team plays the same opponent in consecutive weeks.
        # The double round-robin produces mirror weeks (same pairs, swapped home/away)
        # that can land adjacent after shuffling.
        schedule = self._fixBackToBackMatchups(schedule)

        return schedule
    
    DIVISIONS_PER_LEAGUE = 4

    def _divisionNames(self, leagueName: str) -> List[str]:
        """Division names for a league, from config.json's `divisions` map.

        Config-driven because the owner names these (2026-08-07), the same way team names
        and colours are owned there. Falls back to compass points so a config without the
        key still produces a division-shaped league rather than silently dropping to the
        flat round-robin.
        """
        try:
            from config_manager import get_config
            names = (get_config().get("divisions") or {}).get(leagueName)
            if names and len(names) >= self.DIVISIONS_PER_LEAGUE:
                return list(names)[:self.DIVISIONS_PER_LEAGUE]
        except Exception:
            pass
        return [f"{leagueName} {d}" for d in ("North", "South", "East", "West")]

    def _assignDivisions(self) -> bool:
        """Split each league into four fixed divisions, stamped on the teams.

        Returns True when the league is division-shaped: two leagues of equal size that
        divide evenly into `DIVISIONS_PER_LEAGUE`. Assignment is POSITIONAL and therefore
        stable for a given alignment — which is the point: a rivalry needs the same
        opponents every season, so nothing here reshuffles annually. It also mirrors how
        leagues themselves are split, by config order, so the owner controls which clubs
        share a division purely by their order in config.json.

        Was 2 divisions of 8; now 4 of 4 (owner, 2026-08-07).
        """
        lgs = getattr(self.leagueManager, 'leagues', None) or []
        if len(lgs) != 2:
            return False
        sizes = {len(l.teamList) for l in lgs}
        if len(sizes) != 1:
            return False
        n = sizes.pop()
        per = self.DIVISIONS_PER_LEAGUE
        if n < per * 2 or n % per:
            return False
        size = n // per
        for league in lgs:
            names = self._divisionNames(league.name)
            for i, team in enumerate(league.teamList):
                team.division = names[min(i // size, per - 1)]
        # Persist immediately. This only runs at schedule generation, so if the stamp is
        # not written now the next restart finds an un-divisioned league and nothing
        # re-runs to fix it until the following season.
        try:
            teamManager = self.serviceContainer.getService('team_manager')
            if teamManager:
                teamManager.saveTeamData()
        except Exception as e:
            logger.warning(f"Could not persist division assignment: {e}")
        return True

    def _crossDivisionWeeks(self, divA, divB) -> List[List[tuple]]:
        """Every club in one division plays every club in the other exactly once.
        n divisions of n teams -> n rounds, each a full slate.

        ⚠️ Home/away alternates by ROUND, not by `(i + r)`. The obvious-looking
        `if (i + r) % 2` is broken and was live: the opponent index is `j = (i + r) % n`,
        and a mod-n shift preserves parity, so "A hosts when (i+r) is even" means B only
        ever hosts when j is ODD. Half of division B — every even-indexed club — got ZERO
        home games in the entire cross-division block, in the shipped 8-club format as
        well as this one. Alternating on `r` gives each side exactly n/2 home rounds and
        does not correlate with either index.
        """
        n = len(divA)
        weeks = []
        for r in range(n):
            games = []
            aHosts = (r % 2 == 0)
            for i in range(n):
                j = (i + r) % n
                games.append((divA[i], divB[j]) if aHosts else (divB[j], divA[i]))
            weeks.append(games)
        return weeks

    def _generateDivisionalSchedule(self) -> Optional[List[List[tuple]]]:
        """The 28-week divisional season for a 32-club league of 8 four-team divisions.

            12  division rivals, twice home and away  (3 opponents x 4)
            12  the rest of your league, once each    (12 opponents x 1)
             4  one interleague division              (4 opponents x 1)
            --
            28  weeks -> exactly the 4 game days x 7 hourly slots the calendar has

        Replaces the 14/8/6 split that worked when a division held 8 clubs. With only 3
        rivals, a single home-and-away round is 6 games, so the rivalry weight had to come
        from playing them TWICE over (owner call 2026-08-07, "rivalry-heavy"). Division
        share lands at 43% against the old format's 50%, and every club in your league is
        still played at least once — which the wider-interleague alternative could not
        promise, since it would have drawn only 10 of the other league's 16.

        Ordering is deliberate and is the whole point of the format: the second division
        double-round is placed LAST, so the entire final game day is against the three
        clubs you are racing for the division title.

        Returns None when the league is not division-shaped, so the caller falls back to
        the original round-robin.
        """
        import copy
        import random
        if not self._assignDivisions():
            return None
        lgs = self.leagueManager.leagues
        perLeague = len(lgs[0].teamList)
        per = self.DIVISIONS_PER_LEAGUE
        size = perLeague // per
        if perLeague != 32 // 2 or size != 4:
            return None      # the 12/12/4 split only lands on 28 for four-club divisions

        # Divisions in config order, per league.
        divsByLeague = [[lg.teamList[i * size:(i + 1) * size] for i in range(per)]
                        for lg in lgs]

        def merge(blocks):
            """blocks: list of per-group week-lists -> combined weekly slates."""
            out = []
            for w in range(len(blocks[0])):
                week = []
                for b in blocks:
                    week.extend(b[w])
                out.append(week)
            return out

        # --- division: a home-and-away round robin is 6 weeks for 4 clubs; run it twice.
        # _generateIntraleagueGames returns the first pass followed by its mirror.
        divRounds = [[], []]
        for divs in divsByLeague:
            for div in divs:
                rr = self._generateIntraleagueGames(copy.copy(div))
                divRounds[0].append(rr)
        divFirst = merge(divRounds[0])          # 6 weeks
        divSecond = merge(divRounds[0])         # the same 6 fixtures again, reordered below

        # --- cross-division inside each league: every club meets the 12 outside its
        # division once. Six division pairings organise into THREE rounds of two
        # simultaneous pairings, so the whole league plays every week:
        #     round 1  (1v2) (3v4)      round 2  (1v3) (2v4)      round 3  (1v4) (2v3)
        # Each round is `size` weeks, so 3 x 4 = 12.
        PAIRINGS = (((0, 1), (2, 3)), ((0, 2), (1, 3)), ((0, 3), (1, 2)))
        crossBlocks = []
        for a, b in (p for rnd in PAIRINGS for p in rnd):
            for divs in divsByLeague:
                crossBlocks.append(self._crossDivisionWeeks(divs[a], divs[b]))
        # Two pairings per league run concurrently, so merge them four at a time
        # (2 pairings x 2 leagues) into one 4-week round.
        cross = []
        for i in range(0, len(crossBlocks), 4):
            cross.extend(merge(crossBlocks[i:i + 4]))

        # --- interleague: pair division i of one league with division i of the other,
        # so each club draws exactly one opposing division.
        interBlocks = [self._crossDivisionWeeks(divsByLeague[0][i], divsByLeague[1][i])
                       for i in range(per)]
        inter = merge(interBlocks)              # 4 weeks

        # Shuffle WITHIN each block so the run of weeks isn't identical every season, but
        # never across blocks — the block order is the format.
        for block in (divFirst, cross, inter, divSecond):
            random.shuffle(block)

        schedule = divFirst + cross + inter + divSecond
        expected = 6 + 12 + 4 + 6
        if len(schedule) != expected:
            logger.error(
                f"Divisional schedule built {len(schedule)} weeks, expected {expected} "
                f"— falling back to the round-robin schedule.")
            return None
        logger.info(
            f"Divisional schedule: {len(divFirst)} division + {len(cross)} cross-division "
            f"+ {len(inter)} interleague + {len(divSecond)} division (run-in) "
            f"= {len(schedule)} weeks")
        return schedule

    # A single game line worth a news item on its own.
    #
    # ⚠️ Thresholds are set from THIS SIM's measured distribution, at roughly the 99th
    # percentile of non-zero player-games, NOT from real-world intuition. The first pass
    # used NFL-shaped numbers and 3 sacks caught 5.6% of every player-game in the league —
    # big games alone filled the entire feed and pushed clinches, upsets and records off
    # it. Measured over 9,401 player-game lines (p50 / p90 / p99):
    #
    #   passing yards   220 / 332 / 425      rushing yards  71 / 169 / 271
    #   passing TDs       1 /   3 /   5      rushing TDs     1 /   2 /   4
    #   receiving yards  58 / 126 / 192      sacks           1 /   4 /   9
    #   receiving TDs     1 /   2 /   3      FGs made        2 /   4 /   6
    #
    # At ~420 player-lines a week that lands around four big games per week, which is a
    # feed item rather than a flood. Re-measure if the engine's scoring moves.
    BIG_GAME_TESTS = [
        ('passing', 'yards', 425, '{name} threw for {value} yards'),
        ('passing', 'tds', 5, '{name} threw {value} touchdown passes'),
        ('rushing', 'yards', 270, '{name} ran for {value} yards'),
        ('rushing', 'tds', 4, '{name} ran in {value} touchdowns'),
        ('receiving', 'yards', 190, '{name} went for {value} receiving yards'),
        ('receiving', 'tds', 3, '{name} had {value} receiving touchdowns'),
        ('defense', 'sacks', 9, '{name} recorded {value} sacks'),
        ('defense', 'ints', 2, '{name} picked off {value} passes'),
        ('kicking', 'fgs', 6, '{name} made {value} field goals'),
    ]

    # The four numbers a big-game item leads with — the player's line in whichever group
    # triggered it, so the strip explains the headline rather than repeating it.
    BIG_GAME_STRIP = {
        'passing': [('YARDS', 'yards'), ('TOUCHDOWNS', 'tds'), ('COMPLETIONS', 'comp'), ('ATTEMPTS', 'att')],
        'rushing': [('YARDS', 'yards'), ('TOUCHDOWNS', 'tds'), ('CARRIES', 'carries'), ('LONGEST', 'longest')],
        'receiving': [('YARDS', 'yards'), ('TOUCHDOWNS', 'tds'), ('CATCHES', 'receptions'), ('TARGETS', 'targets')],
        'defense': [('SACKS', 'sacks'), ('TACKLES', 'tackles'), ('INTERCEPTIONS', 'ints'), ('TFL', 'tfl')],
        'kicking': [('MADE', 'fgs'), ('ATTEMPTS', 'fgAtt'), ('LONGEST', 'longest'), ('POINTS', 'pts')],
    }

    # ⚠️ "How far past its own bar" is only comparable BETWEEN categories if each bar sits
    # at a comparable point in its own distribution — and they do not. The big-game
    # thresholds are p99 of this sim's measured player-game distribution, so a typical
    # qualifying big game clears its bar by 2%. `UPSET_NEWS_ELO_GAP` (120) is a far lower
    # bar, so a typical qualifying upset clears it by 50%. Shipping the raw ratio left
    # upsets taking 56-78% of measured headlines — the same bug the weighting was built to
    # fix, only smaller.
    #
    # Dividing by the MEDIAN qualifying event of each category fixes the footing: 1.0 means
    # "a typical one of these", whatever these are, so the headline goes to whatever was
    # most exceptional FOR ITS KIND. Measured over 528 feed rows of a fast sim — top
    # category share 55.7% -> 34.0%, big games 8.6% -> 33.5%. Re-measure if a threshold
    # moves. A category absent here divides by 1.0, which is what keeps a clinch's
    # deliberate 3.0 intact: clinching is rare and is meant to take its week.
    LEAD_WEIGHT_REFERENCE = {'upset': 1.50, 'big_game': 1.02, 'record': 1.06}

    def _leadWeight(self, category: str, raw: float) -> float:
        """A raw past-the-bar ratio, put on a footing comparable across categories."""
        return raw / self.LEAD_WEIGHT_REFERENCE.get(category, 1.0)

    # A record's weight in the headline race is scaled by how hard it was to take. All
    # four scopes fire off the same game, and a career mark falling should not lose the
    # front page to the single-game mark that caused it.
    RECORD_SCOPE_WEIGHT = {'game': 1.0, 'season': 1.2, 'career': 1.45, 'allTime': 1.7}

    # Readable names for the record tree's leaf keys. Without these a headline reads
    # "set the game wr record at 51", because the leaf under `players.fantasy.game` is a
    # POSITION, not a stat.
    RECORD_SCOPES = {'game': 'single-game', 'season': 'season', 'career': 'career', 'allTime': 'all-time'}
    RECORD_STATS = {
        'yards': 'yards', 'tds': 'touchdowns', 'comps': 'completions',
        'ints': 'interceptions', 'fumbles': 'fumbles', 'receptions': 'receptions',
        'fgs': 'field goals', 'fgYards': 'field goal distance', 'pts': 'points',
        'wins': 'wins', 'losses': 'losses', 'titles': 'titles',
        'leagueTitles': 'league titles', 'regSeasonTitles': 'regular-season titles',
        'fumRec': 'fumble recoveries', 'elo': 'ELO',
    }
    RECORD_GROUPS = {'passing': 'passing', 'rushing': 'rushing', 'receiving': 'receiving', 'kicking': 'kicking'}

    def _recordScope(self, path: str) -> str:
        """Which scope a record path belongs to — `players.receiving.game.yards` -> `game`.

        Mirrors `_recordLabel`'s parsing on purpose: the scope sits at a DIFFERENT index
        for player records (`players.group.scope.leaf`) than for team ones
        (`team.scope.leaf`), so reaching for a fixed position gets the leaf instead and
        every record silently weighs the same.
        """
        parts = path.split('.')
        if parts[0] == 'players' and len(parts) == 4:
            return parts[2]
        if parts[0] == 'team' and len(parts) == 3:
            return parts[1]
        return 'game'

    def _recordLabel(self, path: str) -> Optional[str]:
        """`players.receiving.game.yards` -> `single-game receiving yards`."""
        parts = path.split('.')
        if parts[0] == 'players' and len(parts) == 4:
            _, group, scope, leaf = parts
            scopeLabel = self.RECORD_SCOPES.get(scope, scope)
            if group == 'fantasy':
                # The leaf here is a position, and the stat is always fantasy points.
                return f'{scopeLabel} fantasy points by a {leaf.upper()}'
            statLabel = self.RECORD_STATS.get(leaf)
            groupLabel = self.RECORD_GROUPS.get(group, group)
            if not statLabel:
                return None
            # "receiving receptions" is a stutter; the group is implied by the stat.
            if leaf in ('receptions', 'fgs', 'fgYards'):
                return f'{scopeLabel} {statLabel}'
            return f'{scopeLabel} {groupLabel} {statLabel}'
        if parts[0] == 'team' and len(parts) == 3:
            _, scope, leaf = parts
            statLabel = self.RECORD_STATS.get(leaf)
            if not statLabel:
                return None
            return f'{self.RECORD_SCOPES.get(scope, scope)} team {statLabel}'
        return None

    def _snapshotRecords(self) -> Dict[str, Any]:
        """Flatten the records tree to `{path: value}` so a break can be diffed generically.

        Deliberately NOT instrumented at each comparison site: the record checks are dozens
        of near-identical `if stat > record` blocks spread over five methods, and a new
        record type added later would silently skip the feed. A before/after diff cannot
        drift.
        """
        flat: Dict[str, Any] = {}

        def walk(node, path):
            if isinstance(node, dict):
                if 'value' in node and not isinstance(node.get('value'), dict):
                    flat[path] = (node.get('value'), node.get('name'), node.get('id'))
                    return
                for key, child in node.items():
                    walk(child, f'{path}.{key}' if path else key)

        try:
            walk(self.recordsManager.getRecords(), '')
        except Exception as e:
            logger.debug(f"Record snapshot skipped: {e}")
        return flat

    def _publishGameNews(self, game, recordsBefore: Optional[Dict[str, Any]] = None) -> None:
        """Publish everything a finished game just made newsworthy.

        Three independent checks — a record broken, an upset, a big individual game — each
        wrapped so that a failure in one cannot lose the others.

        ⚠️ The WHOLE body is wrapped as well, and that is not belt-and-braces. This hangs
        off the game-completion path, and the first version computed the season and week
        above the inner try blocks — one wrong attribute name there raised straight out of
        `_simulateGame` and every game in the slate failed to simulate. Nothing about
        publishing a news item is worth a game, so nothing here is allowed to escape.
        """
        try:
            self._publishGameNewsInner(game, recordsBefore)
        except Exception as e:
            logger.debug(f"Game news skipped: {e}")

    def _publishGameNewsInner(self, game, recordsBefore: Optional[Dict[str, Any]] = None) -> None:
        from league_news import publish, stat
        from constants import UPSET_NEWS_ELO_GAP, UPSET_MIN_WEEK, BIG_GAME_NEWS_ENABLED

        # `currentWeek` lives on the SEASON, not the manager. The manager grows a
        # `currentWeek` attribute lazily during the playoffs and has none at all during the
        # regular season, so reading it here is an AttributeError for 28 weeks of every
        # 32 — which is exactly how this broke.
        season = getattr(self.currentSeason, 'seasonNumber', 0) or 0
        week = getattr(self.currentSeason, 'currentWeek', 0) or 0

        def emit(**kwargs):
            try:
                publish(self.db_session, season=season, week=week, **kwargs)
            except Exception as e:
                logger.debug(f"Game news publish skipped: {e}")

        # ── A record fell ────────────────────────────────────────────────────
        if recordsBefore:
            try:
                for path, (value, name, holderId) in self._snapshotRecords().items():
                    previous = recordsBefore.get(path)
                    if previous is None or previous[0] == value or not name:
                        continue
                    # ⚠️ Only a genuine BREAK. Every record starts at 0, so on a fresh
                    # league the very first game sets all sixty of them at once and the
                    # feed becomes a wall of "record set" items for one player.
                    if not previous[0]:
                        continue
                    label = self._recordLabel(path)
                    if not label:
                        continue
                    isPlayer = path.startswith('players.')
                    # A record now carries a strip, so it can headline. Three numbers,
                    # not four: the old mark, the new one, and the gap between them is
                    # the whole story of a record falling, and the lead strip flexes to
                    # however many cells it is given. Weighted by how comprehensively the
                    # old mark was beaten, scaled by how hard the record was to take —
                    # an all-time mark falling is a bigger story than a single-game one.
                    prevValue = previous[0]
                    margin = value - prevValue
                    scope = self._recordScope(path)
                    recordStats = [
                        stat('NEW', round(value), positive=True),
                        stat('PREVIOUS', round(prevValue)),
                        stat('BEATEN BY', f'+{round(margin)}', positive=margin > 0),
                    ]
                    # ⚠️ `holderId` IS the team id on a team record — `_checkTeamGameRecord`
                    # stores `id: team.id` right alongside the name. An earlier version
                    # ignored that and matched the record's name against `team.name`, which
                    # never hit: the record stores "Cleveland Rocks" (city + name) while
                    # `team.name` is just "Rocks", so every team record shipped without a
                    # crest. Player records get their team filled in at read time instead,
                    # from the player row (front_page).
                    emit(category='record', eventType=path,
                         text=f'{name} set the {label} record at {round(value)}',
                         teamId=None if isPlayer else holderId,
                         playerId=holderId if isPlayer else None,
                         playerName=name if isPlayer else None,
                         stats=recordStats,
                         leadWeight=self._leadWeight(
                             'record',
                             (value / prevValue) * self.RECORD_SCOPE_WEIGHT.get(scope, 1.0)))
            except Exception as e:
                logger.debug(f"Record news skipped: {e}")

        # ── An upset ─────────────────────────────────────────────────────────
        # Judged on PRE-GAME ELO, captured before the result moved it. Reading the live
        # elo here would compare the teams after the win had already been priced in.
        #
        # ⚠️ And not before `UPSET_MIN_WEEK`. ELO regresses halfway to 1500 at every
        # season reset, so a 120-point gap in the opening weeks is mostly last season's
        # residue rather than this season's form — the feed was calling results
        # surprising off a number the league had not yet earned. Playoff weeks are 29+
        # and clear the bar on their own.
        try:
            winner = getattr(game, 'winningTeam', None)
            loser = getattr(game, 'losingTeam', None)
            if winner is not None and loser is not None:
                homeIsWinner = winner is game.homeTeam
                winnerElo = getattr(game, '_preGameHomeElo' if homeIsWinner else '_preGameAwayElo', 1500)
                loserElo = getattr(game, '_preGameAwayElo' if homeIsWinner else '_preGameHomeElo', 1500)
                gap = (loserElo or 1500) - (winnerElo or 1500)
                if gap >= UPSET_NEWS_ELO_GAP and week >= UPSET_MIN_WEEK:
                    winnerScore = game.homeScore if homeIsWinner else game.awayScore
                    loserScore = game.awayScore if homeIsWinner else game.homeScore
                    emit(category='upset', eventType='upset',
                         text=f'{winner.city} {winner.name} have upset the {loser.city} {loser.name}',
                         teamId=winner.id,
                         stats=[
                             stat('FINAL', f'{round(winnerScore)}-{round(loserScore)}'),
                             stat('ELO GAP', f'-{round(gap)}'),
                             stat('WINNER ELO', round(winnerElo or 1500)),
                             stat('LOSER ELO', round(loserElo or 1500)),
                         ],
                         leadWeight=self._leadWeight('upset', gap / UPSET_NEWS_ELO_GAP))
        except Exception as e:
            logger.debug(f"Upset news skipped: {e}")

        # ── A big individual game ────────────────────────────────────────────
        # OFF by default — see `BIG_GAME_NEWS_ENABLED`. The feed is about the league and
        # the simulation running it, not about who had a good afternoon; measured, these
        # were 48% of all rows and crowded everything else off the visible feed.
        #
        # One item per player at most when enabled. A back who runs for 180 and three
        # scores is one story, not two, and firing both would let a single game flood it.
        if not BIG_GAME_NEWS_ENABLED:
            return
        try:
            for team in (game.homeTeam, game.awayTeam):
                for player in (getattr(team, 'rosterDict', {}) or {}).values():
                    if not player or not hasattr(player, 'gameStatsDict'):
                        continue
                    for group, key, threshold, template in self.BIG_GAME_TESTS:
                        line = player.gameStatsDict.get(group, {}) or {}
                        value = line.get(key, 0) or 0
                        if value < threshold:
                            continue
                        # The strip is the player's line in the group that triggered the
                        # item, so it explains the headline instead of repeating it.
                        strip = [
                            stat(label, round(line.get(field, 0) or 0))
                            for label, field in self.BIG_GAME_STRIP.get(group, [])
                        ]
                        emit(category='big_game', eventType=f'{group}.{key}',
                             text=template.format(name=player.name, value=round(value)),
                             playerId=player.id, playerName=player.name, teamId=team.id,
                             stats=strip if len(strip) == 4 else None,
                             leadWeight=self._leadWeight(
                                 'big_game', value / threshold if threshold else 1.0))
                        break
        except Exception as e:
            logger.debug(f"Big-game news skipped: {e}")

    def _publishCoresWeekNews(self, week: int) -> None:
        """The Cores react to the slate that just finished, and now and then just talk.

        This is what the feed is mostly FOR (owner, 2026-08-08): the league told by the
        things running it, rather than a list of who gained the most yards. Both pools
        already existed and were reachable only from the ephemeral control-room endpoint,
        so the Cores were characters nobody met unless they went looking.

        ⚠️ Reactions come from `gameResultExchange`, which references TEAMS AND SCORES —
        fine here. The `observation` beats do NOT go in the feed: those quote the raw
        aggregate and threshold, and the public surfaces stay number-free so the anomaly
        reads as a mood rather than a progress bar.

        ⚠️ Wrapped whole, like `_publishGameNews`. Nothing about narrating a week may
        break the week.
        """
        try:
            from constants import CORES_GAME_NEWS_EVERY_WEEKS, CORES_AMBIENT_NEWS_EVERY_WEEKS
            from managers.coresManager import gameResultEntriesFor, entriesForEvent
            from league_news import publish

            season = getattr(self.currentSeason, 'seasonNumber', 0) or 0
            entries = []

            if CORES_GAME_NEWS_EVERY_WEEKS and week % CORES_GAME_NEWS_EVERY_WEEKS == 0:
                games = self._coresGameDigest()
                if games:
                    entries.extend(gameResultEntriesFor(games) or [])

            # Untethered banter — world-building, bickering, the lore they invented. No
            # triggering event, which is the point: the simulation is inhabited whether or
            # not anything happened.
            if CORES_AMBIENT_NEWS_EVERY_WEEKS and week % CORES_AMBIENT_NEWS_EVERY_WEEKS == 0:
                entries.extend(entriesForEvent('idle') or [])

            for entry in entries:
                publish(
                    self.db_session,
                    season=season, week=week,
                    category='cores',
                    eventType=entry.get('eventType'),
                    text=entry.get('text', ''),
                    core=entry.get('core'),
                    coreDisplayName=entry.get('coreDisplayName'),
                    exchangeId=entry.get('exchangeId'),
                    turnIndex=entry.get('turnIndex'),
                    turnCount=entry.get('turnCount'),
                )
        except Exception as e:
            logger.debug(f"Cores week news skipped: {e}")

    def _coresGameDigest(self):
        """The week's finals, shaped the way `gameResultExchange` reads them.

        Built from the games already in memory rather than re-queried — this runs on the
        sim thread at week end, and the season object is holding them anyway.
        """
        from constants import UPSET_NEWS_ELO_GAP
        games = (getattr(self.currentSeason, 'completedWeekGames', None)
                 or getattr(self.currentSeason, 'activeGames', None) or [])
        out = []
        for g in games:
            try:
                home, away = g.homeTeam, g.awayTeam
                if home is None or away is None or g.homeScore == g.awayScore:
                    continue   # a tie has no winner to name, and the pools all name one
                homeWon = g.homeScore > g.awayScore
                if homeWon:
                    winner, loser, ws, ls = home, away, g.homeScore, g.awayScore
                else:
                    winner, loser, ws, ls = away, home, g.awayScore, g.homeScore
                # Judged on PRE-game Elo, captured before the result moved it — the same
                # basis and the same bar the upset news item uses, so the Cores and the
                # feed cannot disagree about what counted as an upset.
                winnerElo = getattr(g, '_preGameHomeElo' if homeWon else '_preGameAwayElo', 1500) or 1500
                loserElo = getattr(g, '_preGameAwayElo' if homeWon else '_preGameHomeElo', 1500) or 1500
                out.append({
                    'winner': winner.name, 'loser': loser.name,
                    'winnerScore': ws, 'loserScore': ls,
                    'margin': ws - ls, 'total': ws + ls,
                    'overtime': bool(getattr(g, 'isOvertime', False)),
                    'upset': loserElo - winnerElo >= UPSET_NEWS_ELO_GAP,
                    'week': getattr(self.currentSeason, 'currentWeek', 0) or 0,
                })
            except Exception:
                continue
        return out

    def _publishScheduleNews(self, eventType: str, text: str,
                             week: Optional[int] = None,
                             season: Optional[int] = None) -> None:
        """A schedule beat — a season opening, a week starting — in the news feed.

        Its own category so the feed can colour it apart from results, and it deliberately
        carries no stats: a slate that has not been played has no numbers worth a headline,
        and this should never take the lead slot from an actual result.

        Wrapped whole, like every other publisher hanging off the sim loop: nothing about a
        news item is worth interrupting a season roll-over for.
        """
        try:
            from league_news import publish
            publish(
                self.db_session,
                season=season if season is not None else getattr(self.currentSeason, 'seasonNumber', 0) or 0,
                week=week if week is not None else getattr(self.currentSeason, 'currentWeek', 0) or 0,
                category='schedule',
                eventType=eventType,
                text=text,
                # The surrounding code broadcasts its own season/week event; a second push
                # would double the beat in the live feed.
                broadcast=False,
            )
        except Exception as e:
            logger.debug(f"Schedule news skipped ({eventType}): {e}")

    def _publishTeamNews(self, category: str, text: str, team, lead: bool = False) -> None:
        """Persist a team event to the league-news feed.

        `lead=True` attaches the four-number strip that makes an item eligible to lead the
        front page. A clinch gets one; an elimination deliberately does not — a losing
        record, no seed and a negative differential is four numbers that say nothing, and
        it is the wrong thing to headline a page with.
        """
        try:
            from league_news import publish, stat
            stats = None
            if lead:
                s = getattr(team, 'seasonTeamStats', {}) or {}
                wins = s.get('wins', 0) or 0
                losses = s.get('losses', 0) or 0
                streak = s.get('streak', 0) or 0
                diff = round(s.get('scoreDiff', 0) or 0)
                stats = [
                    stat('RECORD', f'{wins}-{losses}'),
                    stat('STREAK', f'W{streak}' if streak > 0 else f'L{abs(streak)}' if streak else '-',
                         positive=streak > 0),
                    stat('POINTS FOR', round((s.get('Offense', {}) or {}).get('pts', 0) or 0)),
                    stat('POINT DIFF', f'+{diff}' if diff > 0 else str(diff), positive=diff > 0),
                ]
            publish(
                self.db_session,
                season=getattr(self.currentSeason, 'seasonNumber', 0) or 0,
                # On the season, not the manager — see `_publishGameNewsInner`.
                week=getattr(self.currentSeason, 'currentWeek', 0) or 0,
                category=category,
                text=text,
                teamId=team.id,
                stats=stats,
                # Clinching happens once a season per club. Weighted above anything a
                # single game can produce so it takes the headline of the week it lands
                # in rather than losing to whichever receiver had a big afternoon.
                leadWeight=3.0 if lead else None,
                # The surrounding code already broadcasts this line itself; publishing
                # would send it twice.
                broadcast=False,
            )
        except Exception as e:
            logger.debug(f"Team news publish skipped ({category}): {e}")

    def _applyDivisionSeeding(self, qualifiers, league):
        """Division winners take the top seeds, the wildcards by record behind them.

        A division winner is the best record inside its own division across the WHOLE
        league (not just among qualifiers) — a club can win a weak division without being
        top-half overall, and it should still get the seed. Falls back to plain record
        order when the league has no divisions stamped.

        Delegates to `standings_view.seedLeague`, which is also what the standings board
        renders, so the projected seeds a fan reads all season cannot contradict the field
        that actually gets built.

        ⚠️ This used to swap each missing winner in by dropping the LAST qualifier, which
        dropped the previously-swapped winner when a second one was missing: the field
        came back one club short of the winners it claimed to contain, so `len(field)`
        landed on 9 instead of 8 and the power-of-two check silently handed out byes.
        Building the field from winners + wildcards makes the size structural.
        """
        from seeding import buildH2HGames
        from standings_view import seedLeague
        season = self.currentSeason.seasonNumber if self.currentSeason else 0
        try:
            h2h = buildH2HGames(self.db_session, season)
        except Exception:
            h2h = []
        seeded = seedLeague(list(league.teamList), h2h)
        if not seeded['seeds']:
            return self._seedTeams(qualifiers)
        return [t for t in seeded['ordered'] if t.id in seeded['seeds']]

    def _fixBackToBackMatchups(self, schedule: List[List[tuple]]) -> List[List[tuple]]:
        """Eliminate consecutive weeks where the same two teams play each other.
        Uses restart-with-reshuffle to avoid getting stuck in swap cycles."""
        import random

        def matchupPairs(week):
            return frozenset((min(h.id, a.id), max(h.id, a.id)) for h, a in week)

        def hasConflicts(sched):
            return any(matchupPairs(sched[i]) & matchupPairs(sched[i + 1]) for i in range(len(sched) - 1))

        for _attempt in range(50):
            random.shuffle(schedule)
            n = len(schedule)
            for _ in range(50):
                changed = False
                for i in range(n - 1):
                    if matchupPairs(schedule[i]) & matchupPairs(schedule[i + 1]):
                        candidates = list(range(i + 2, n))
                        random.shuffle(candidates)
                        for j in candidates:
                            schedule[i + 1], schedule[j] = schedule[j], schedule[i + 1]
                            checkIdxs = sorted({i, i + 1, j - 1, j} & set(range(n - 1)))
                            if all(not (matchupPairs(schedule[k]) & matchupPairs(schedule[k + 1])) for k in checkIdxs):
                                changed = True
                                break
                            schedule[i + 1], schedule[j] = schedule[j], schedule[i + 1]  # revert
                if not changed:
                    break
            if not hasConflicts(schedule):
                return schedule  # clean solution found
        return schedule  # best effort after all restarts

    def _generateIntraleagueGames(self, teams: List[FloosTeam.Team]) -> List[List[tuple]]:
        """Generate intra-league games using original round-robin algorithm"""
        n = len(teams)
        tempTeams = teams.copy()
        weeks = []
        
        # First round-robin
        for week in range(n - 1):
            games = []
            for i in range(n // 2):
                if week % 2 == 0:
                    home = tempTeams[i]
                    away = tempTeams[n - 1 - i]
                    games.append((home, away))
                else:
                    home = tempTeams[n - 1 - i]
                    away = tempTeams[i]
                    games.append((home, away))
            
            weeks.append(games)
            tempTeams.insert(1, tempTeams.pop())
        
        # Second round-robin (reverse home/away)
        reverseWeeks = []
        for week in weeks:
            reverse = [(away, home) for home, away in week]
            reverseWeeks.append(reverse)
        
        weeks.extend(reverseWeeks)
        return weeks
    
    def _generateInterleagueGames(self, league1: List[FloosTeam.Team], league2: List[FloosTeam.Team]) -> List[List[tuple]]:
        """Generate inter-league games using original complex algorithm"""
        import random
        
        weeks = []
        group1Weeks = []
        group2Weeks = []
        league1Group1Teams = []
        league1Group2Teams = []
        league2Group1Teams = []
        league2Group2Teams = []

        # ⚠️ This routine assumes both leagues are the SAME size and that size is
        # EVEN. The split below walks `range(len(teamList))` and sends the first half
        # to group 1 — at an odd count that is 8 and 7, so `group2Weeks` comes back
        # one week short and the combine step dies on `group2Weeks[x]` with a bare
        # IndexError that says nothing about why.
        #
        # It happened for real: a club renamed in config's `teams` but not in
        # `teamDistribution` was silently dropped, leaving a 15-club league. Fail here,
        # naming the sizes, rather than 40 lines later naming an index.
        sizeA, sizeB = len(league1), len(league2)
        if sizeA != sizeB or sizeA % 2 != 0:
            raise ValueError(
                f"Interleague scheduling needs two equal, even-sized leagues; got "
                f"{sizeA} and {sizeB}. A club is probably missing from a league — check "
                f"config.json's `teamDistribution` names against its `teams` array.")

        # Split leagues into groups
        for x in range(len(self.leagueManager.leagues[0].teamList)):
            if x < (len(self.leagueManager.leagues[0].teamList) / 2):
                league1Group1Teams.append(league1.pop(random.randrange(len(league1))))
                league2Group1Teams.append(league2.pop(random.randrange(len(league2))))
            else:
                league1Group2Teams.append(league1.pop(random.randrange(len(league1))))
                league2Group2Teams.append(league2.pop(random.randrange(len(league2))))
        
        # Generate Group 1 matchups
        for x in range(len(league1Group1Teams)):
            games = []
            for y in range(len(league1Group1Teams)):
                a = x + y
                z = int(a % (len(league1Group1Teams)))
                if y % 2 == 0:
                    games.append((league1Group1Teams[y], league2Group1Teams[z]))
                else:
                    games.append((league2Group1Teams[z], league1Group1Teams[y]))
            group1Weeks.append(games)
        
        # Generate Group 2 matchups
        for x in range(len(league1Group2Teams)):
            games = []
            for y in range(len(league1Group2Teams)):
                a = x + y
                z = int(a % (len(league1Group2Teams)))
                if y % 2 == 0:
                    games.append((league1Group2Teams[y], league2Group2Teams[z]))
                else:
                    games.append((league2Group2Teams[z], league1Group2Teams[y]))
            group2Weeks.append(games)
        
        # Combine group weeks
        for x in range(len(group1Weeks)):
            week = []
            week.extend(group1Weeks[x])
            week.extend(group2Weeks[x])
            weeks.append(week)
        
        return weeks

    # ── Playoff bracket challenge hooks ──────────────────────────────────
    def _freezePlayoffSeeds(self, playoffTeamsByConf) -> None:
        """Freeze the bracket field when seeding locks so the challenge can
        project matchups. playoffTeamsByConf: {confName: [Team,...] best-first};
        top 2 per conference are byes."""
        try:
            seeds = {"conferences": {}}
            for confName, teams in playoffTeamsByConf.items():
                seeds["conferences"][confName] = [
                    {
                        "teamId": t.id,
                        "seed": i + 1,
                        "bye": i < 2,
                        "winPct": round(t.seasonTeamStats.get('winPerc', 0), 4),
                        "scoreDiff": t.seasonTeamStats.get('scoreDiff', 0),
                        "teamName": t.name,
                        "city": getattr(t, 'city', ''),
                        "abbreviation": getattr(t, 'abbreviation', None) or t.name[:3].upper(),
                    }
                    for i, t in enumerate(teams)
                ]
            from database.connection import get_session as _gs
            from database.repositories.playoff_bracket_repository import PlayoffBracketRepository
            s = _gs()
            try:
                PlayoffBracketRepository(s).freezeSeeds(self.currentSeason.seasonNumber, seeds)
                s.commit()
            finally:
                s.close()
            logger.info(
                f"Playoff bracket field frozen "
                f"({sum(len(v) for v in seeds['conferences'].values())} teams)"
            )
        except Exception as e:
            logger.error(f"Failed to freeze playoff seeds: {e}")

    def _scorePlayoffBrackets(self) -> None:
        """Recompute all bracket scores from results so far (idempotent).
        Called after each playoff round resolves."""
        try:
            from database.connection import get_session as _gs
            from database.repositories.playoff_bracket_repository import PlayoffBracketRepository
            from managers import achievementManager as _am
            season = self.currentSeason.seasonNumber
            s = _gs()
            try:
                repo = PlayoffBracketRepository(s)
                repo.scoreAllBrackets(season)
                s.commit()
                # Grant Bracketeer point tiers (I-IV) AS thresholds are crossed
                # each round, not batched at the Floos Bowl. recordProgress is
                # monotonic (absolute=max) + idempotent (no re-grant once
                # completed) and toasts on unlock, so calling it every round just
                # fires newly-crossed tiers. (flawless/pool_shark stay end-only —
                # they need the COMPLETE bracket / final leaderboard.)
                for b in repo.getLeaderboard(season):
                    if b.points > 0:
                        _am.onPlayoffBracketScored(s, b.user_id, b.points, season)
                s.commit()
            finally:
                s.close()
        except Exception as e:
            logger.error(f"Failed to score playoff brackets: {e}")

    def _awardPlayoffBracketPrizes(self) -> None:
        """After the Floos Bowl: final scoring + floobit prizes to the top
        brackets. Guarded against double-payment by a per-season tx check."""
        try:
            from database.connection import get_session as _gs
            from database.repositories.playoff_bracket_repository import PlayoffBracketRepository
            from database.repositories.card_repositories import CurrencyRepository
            from database.models import CurrencyTransaction
            from constants import (PLAYOFF_BRACKET_PRIZES, PLAYOFF_BRACKET_TOP_PCT,
                                   PLAYOFF_BRACKET_TOP_PCT_PRIZE)
            season = self.currentSeason.seasonNumber
            txType = 'playoff_bracket_prize'
            s = _gs()
            try:
                if s.query(CurrencyTransaction.id).filter(
                        CurrencyTransaction.transaction_type == txType,
                        CurrencyTransaction.season == season).first():
                    logger.info("Playoff bracket prizes already awarded — skipping")
                    return
                repo = PlayoffBracketRepository(s)
                repo.scoreAllBrackets(season)
                board = [b for b in repo.getLeaderboard(season) if b.points > 0]
                cur = CurrencyRepository(s)
                topPctCount = int(len(board) * PLAYOFF_BRACKET_TOP_PCT)
                paid = 0
                for rank, b in enumerate(board, start=1):
                    prize = PLAYOFF_BRACKET_PRIZES.get(rank, 0)
                    if prize == 0 and rank <= topPctCount:
                        prize = PLAYOFF_BRACKET_TOP_PCT_PRIZE
                    if prize > 0:
                        cur.addFunds(b.user_id, prize, txType,
                                     f"Playoff bracket #{rank} ({b.points} pts)", season)
                        paid += 1
                # Bracket achievements. Bracketeer point tiers are already
                # granted incrementally each round in _scorePlayoffBrackets; the
                # call below is an idempotent final backstop. The flawless /
                # pool_shark secrets are end-only — they need the COMPLETE
                # bracket (all advancers correct) and the FINAL leaderboard (#1).
                from managers import achievementManager as _am
                advancers, _champ = repo.computeActualAdvancers(season)
                totalAdvancers = sum(len(v) for v in advancers.values())
                topPoints = board[0].points if board else 0
                for b in board:
                    _am.onPlayoffBracketScored(s, b.user_id, b.points, season)  # Bracketeer I-IV
                    if totalAdvancers > 0 and b.correct_count >= totalAdvancers:
                        _am.unlockSecret(s, b.user_id, "flawless")              # perfect bracket
                    if b.points == topPoints:
                        _am.unlockSecret(s, b.user_id, "pool_shark")            # #1 on the leaderboard
                s.commit()
                logger.info(f"Playoff bracket prizes awarded to {paid} brackets")
            finally:
                s.close()
        except Exception as e:
            logger.error(f"Failed to award playoff bracket prizes: {e}")

    def _awardShowcaseDividends(self, season: int, week: int) -> None:
        """Weekly Card Showcase dividend: each user's currently-featured showcase
        is re-graded and pays Floobits scaled by its score. Guarded against
        double-payment by a per-(season, week) transaction check, so a resume/
        replay of the week is safe. Fires a per-user notification so the income is
        visible all season (parity with the weekly FP earnings)."""
        try:
            from database.connection import get_session as _gs
            from managers import showcaseManager
            s = _gs()
            try:
                summary = showcaseManager.awardWeeklyDividends(s, season, week)
                if summary.get("alreadyAwarded"):
                    s.commit()
                    logger.info(f"Showcase dividends already awarded for week {week} — skipping")
                    return
                # Notify the users who were actually paid.
                try:
                    from database.repositories.notification_repository import NotificationRepository
                    notifRepo = NotificationRepository(s)
                    for r in summary.get("results", []):
                        if r.get("dividend", 0) > 0:
                            notifRepo.create(
                                r["userId"], 'showcase_dividend',
                                f'Week {week} Showcase',
                                f'+{r["dividend"]} Floobits from your Showcase (grade {r["grade"]})',
                                data={'season': season, 'week': week,
                                      'dividend': r["dividend"], 'grade': r["grade"]},
                            )
                except Exception as _e:
                    logger.warning(f"Showcase dividend notifications failed: {_e}")
                s.commit()
                logger.info(f"Showcase dividends paid to {summary['paid']} users (S{season} wk{week})")
            finally:
                s.close()
        except Exception as e:
            logger.error(f"Failed to award showcase dividends: {e}")

    def _seedTeams(self, teams):
        """Order teams by the playoff-seeding tiebreaker chain — win% →
        score differential → head-to-head point differential → points-for →
        points-against. Shared with the standings board via seeding.orderTeams
        so the two can't diverge."""
        from seeding import orderTeams, buildH2HGames
        season = self.currentSeason.seasonNumber if self.currentSeason else 0
        try:
            h2h = buildH2HGames(self.db_session, season)
        except Exception:
            h2h = []
        return orderTeams(list(teams), h2h)

    async def _simulatePlayoffRounds(self, resumeFromRound: int = 1, restoredState: Optional[dict] = None) -> None:
        """Simulate all playoff rounds.

        ``resumeFromRound`` > 1 (with ``restoredState``) resumes an interrupted
        playoff run: completed rounds are preserved, the bracket survivors and
        free-agency order are restored from the persisted snapshot, and the loop
        picks up at the next unplayed round. The bracket-setup awards/broadcasts
        are skipped on resume (those clinch bonuses already fired and the team
        flags that gate them are runtime-only, so re-running would double-pay).
        """
        resuming = resumeFromRound > 1
        # Never reuse a game id already in the DB (phantom-reaction guard).
        self._syncGameIdCounter()

        # Clean up stale data from any previous playoff run (safe no-op on first
        # run). On resume, scope it to the interrupted round and later so the
        # already-completed rounds keep their games / pick-em / prizes.
        self._cleanupOrphanedPlayoffData(self.currentSeason.seasonNumber, fromWeek=28 + resumeFromRound)

        playoffDict = {}
        playoffTeams = {}
        playoffsByeTeams = {}
        playoffsNonByeTeams = {}
        nonPlayoffTeamList = []
        strCurrentSeason = 'season{}'.format(self.currentSeason.seasonNumber)
        x = 0
        for league in self.leagueManager.leagues:
            playoffTeamsList = []
            playoffsByeTeamList = []
            playoffsNonByeTeamList = []
            league.teamList[:] = self._seedTeams(league.teamList)

            # Division winners take the top seeds. Winning the division is the prize; it
            # buys a favourable matchup, not a free round. Ordered between themselves by
            # record, then the wildcards by record behind them.
            playoffTeamsList[:] = self._applyDivisionSeeding(
                league.teamList[:int(len(league.teamList) / 2)], league)

            # ⚠️ The eliminated set is the complement of the ACTUAL field, not the bottom
            # half by record. A division winner can finish outside the top half — at four
            # clubs per division that is routine, not a corner case — and taking the
            # record slice here marked that club eliminated and dropped it into the FA
            # draft order while it was still alive in the bracket.
            _qualified = {id(t) for t in playoffTeamsList}
            nonPlayoffTeamList.extend([t for t in league.teamList if id(t) not in _qualified])

            # A power-of-two field needs no byes — every club plays every round.
            # At 8 qualifiers (16-club leagues) that removes the structural advantage
            # that was handing the top two seeds 89% of Floos Bowls: a bye skipped the
            # round most likely to produce an upset. Non-power-of-two fields (the old
            # 6-per-league shape) still bye the top two, which is what makes the
            # bracket resolvable at all.
            fieldSize = len(playoffTeamsList)
            if fieldSize and (fieldSize & (fieldSize - 1)) == 0:
                playoffsNonByeTeamList.extend(playoffTeamsList)
            else:
                playoffsByeTeamList.extend(playoffTeamsList[:2])
                playoffsNonByeTeamList.extend(playoffTeamsList[2:])
            # Re-sort by record ONLY when byes are in play. With a power-of-two field
            # the list already carries the division-winner order set above, and
            # re-seeding here would sort those winners straight back out of seeds 1-2.
            if playoffsByeTeamList:
                playoffsByeTeamList[:] = self._seedTeams(playoffsByeTeamList)
                playoffsNonByeTeamList[:] = self._seedTeams(playoffsNonByeTeamList)

            # The #1 seed. Read it off the QUALIFIER list, not the bye list — a
            # power-of-two field has no byes at all, and this block used to index
            # playoffsByeTeamList[0] unconditionally (IndexError the moment byes went
            # away). The top qualifier is the top seed either way.
            topSeed = playoffTeamsList[0] if playoffTeamsList else None
            if topSeed is None:
                logger.error(f"{league.name} produced no playoff qualifiers — skipping top-seed award")
                continue

            # Award top seed Floobits if not already clinched mid-season.
            # Skipped on resume — the bonus already fired and clinchedTopSeed is
            # runtime-only, so re-running here would double-pay favorite-team fans.
            if not resuming and not getattr(topSeed, 'clinchedTopSeed', False):
                from constants import CLINCH_TOPSEED_REWARD
                self._awardFavoriteTeamBonus(
                    topSeed.id, CLINCH_TOPSEED_REWARD, 'team_clinch_topseed',
                    description='Favorite team clinched #1 seed',
                    season=self.currentSeason.seasonNumber)
            topSeed.clinchedTopSeed = True
            topSeed.seasonTeamStats['topSeed'] = True

            # Mark top seed in their league
            season_str = 'Season {}'.format(self.currentSeason.seasonNumber)
            if season_str not in topSeed.topSeeds:
                topSeed.topSeeds.append(season_str)
            if not resuming:
                _topSeedText = '{0} {1} clinched the {2} top seed!'.format(topSeed.city, topSeed.name, league.name)
                self.currentSeason.leagueHighlights.insert(0, {'event': {'text': _topSeedText}})
                if BROADCASTING_AVAILABLE and broadcaster.is_enabled() and LeagueNewsEvent:
                    await broadcaster.broadcast_season_event(LeagueNewsEvent.leagueNews(_topSeedText))

            season_str_div = 'Season {}'.format(self.currentSeason.seasonNumber)

            # ── Division titles ──
            # Awarded here rather than with the playoff seeds because a division winner is
            # the best record INSIDE its division across the whole league, which
            # _applyDivisionSeeding already computes — a club can win a weak division
            # without being top-4 overall, and it has still won it.
            divisions: Dict[str, list] = {}
            for _t in league.teamList:
                _d = getattr(_t, 'division', None)
                if _d:
                    divisions.setdefault(_d, []).append(_t)
            for _divName, _members in divisions.items():
                _ranked = self._seedTeams(list(_members))
                if not _ranked:
                    continue
                _winner = _ranked[0]
                _winner.seasonTeamStats['divisionChamp'] = True
                if not hasattr(_winner, 'divisionTitles'):
                    _winner.divisionTitles = []
                if season_str_div not in _winner.divisionTitles:
                    _winner.divisionTitles.append(season_str_div)
                if not resuming:
                    _divText = '{0} {1} win the {2}!'.format(
                        _winner.city, _winner.name, _divName)
                    self.currentSeason.leagueHighlights.insert(0, {'event': {'text': _divText}})
                    if BROADCASTING_AVAILABLE and broadcaster.is_enabled() and LeagueNewsEvent:
                        await broadcaster.broadcast_season_event(
                            LeagueNewsEvent.leagueNews(_divText))

            playoffTeams[league.name] = playoffTeamsList.copy()
            playoffsByeTeams[league.name] = playoffsByeTeamList.copy()
            playoffsNonByeTeams[league.name] = playoffsNonByeTeamList.copy()

            for team in playoffsByeTeamList:
                team: FloosTeam.Team
                team.playoffAppearances += 1
                team.seasonTeamStats['madePlayoffs'] = True
                if not resuming and not team.clinchedPlayoffs:
                    from constants import CLINCH_PLAYOFF_REWARD
                    self._awardFavoriteTeamBonus(
                        team.id, CLINCH_PLAYOFF_REWARD, 'team_clinch_playoff',
                        description='Favorite team clinched playoffs',
                        season=self.currentSeason.seasonNumber)
                team.clinchedPlayoffs = True
                team.winningStreak = False
            for team in playoffsNonByeTeamList:
                team: FloosTeam.Team
                team.playoffAppearances += 1
                team.seasonTeamStats['madePlayoffs'] = True
                team.winningStreak = False
                if not team.clinchedPlayoffs:
                    team.clinchedPlayoffs = True
                    team.eliminated = False
                    if not resuming:
                        from constants import CLINCH_PLAYOFF_REWARD
                        self._awardFavoriteTeamBonus(
                            team.id, CLINCH_PLAYOFF_REWARD, 'team_clinch_playoff',
                            description='Favorite team clinched playoffs',
                            season=self.currentSeason.seasonNumber)
                        _clinchText = '{0} {1} have clinched a playoff berth'.format(team.city, team.name)
                        self.currentSeason.leagueHighlights.insert(0, {'event': {'text': _clinchText}})
                        self._publishTeamNews('clinched', _clinchText, team, lead=True)
                        if BROADCASTING_AVAILABLE and broadcaster.is_enabled() and LeagueNewsEvent:
                            await broadcaster.broadcast_season_event(LeagueNewsEvent.leagueNews(_clinchText))

        for team in nonPlayoffTeamList:
            team: FloosTeam.Team
            team.winningStreak = False
            if not team.eliminated:
                team.eliminated = True
                team.clinchedPlayoffs = False
                if not resuming:
                    _elimText = '{0} {1} have faded from playoff contention'.format(team.city, team.name)
                    self.currentSeason.leagueHighlights.insert(0, {'event': {'text': _elimText}})
                    self._publishTeamNews('eliminated', _elimText, team)
                    if BROADCASTING_AVAILABLE and broadcaster.is_enabled() and LeagueNewsEvent:
                        await broadcaster.broadcast_season_event(LeagueNewsEvent.leagueNews(_elimText))


        # freeAgencyOrder seeding: on a fresh run, start it with the non-playoff
        # teams (worst-first). On resume it's restored wholesale from the
        # persisted snapshot below, so skip the rebuild here.
        if not resuming:
            self.currentSeason.freeAgencyOrder.extend(nonPlayoffTeamList)
            list.sort(self.currentSeason.freeAgencyOrder, key=lambda team: (team.seasonTeamStats['winPerc'],team.seasonTeamStats['scoreDiff']), reverse=False)
        import floosball_methods as FloosMethods
        numOfRounds = FloosMethods.getPower(2, len(self.leagueManager.teams)/2)

        # On resume, replace the freshly-seeded bracket with the persisted
        # snapshot: survivors entering the resume round (per league) and the
        # accumulated free-agency/draft order. Eliminations for completed rounds
        # are re-applied here so downstream offseason logic sees the right state.
        if resuming and restoredState:
            teamById = {t.id: t for t in self.serviceContainer.getService('team_manager').teams}
            survivors = restoredState.get('survivors', {}) or {}
            for league in self.leagueManager.leagues:
                survivingIds = survivors.get(league.name, [])
                survivingTeams = [teamById[tid] for tid in survivingIds if tid in teamById]
                playoffTeams[league.name] = survivingTeams
                # Anyone who made the playoffs in this league but isn't a
                # survivor was eliminated in a completed round.
                for team in league.teamList:
                    if team.seasonTeamStats.get('madePlayoffs') and team not in survivingTeams:
                        team.eliminated = True
            faOrderIds = restoredState.get('faOrder', []) or []
            self.currentSeason.freeAgencyOrder = [teamById[tid] for tid in faOrderIds if tid in teamById]
            logger.info(f"Playoff resume: restored bracket at round {resumeFromRound} — "
                        f"survivors={{ {', '.join(f'{lg}:{len(playoffTeams.get(lg, []))}' for lg in [l.name for l in self.leagueManager.leagues])} }}, "
                        f"faOrder={len(self.currentSeason.freeAgencyOrder)}")

        # PLAYOFF_TEST: set anchor for compressed scheduling and enable playoff waits
        from managers.timingManager import TimingMode
        if self.timingManager.mode == TimingMode.PLAYOFF_TEST:
            self._testPlayoffAnchor = datetime.datetime.utcnow()
            self.timingManager.playoffPhase = True
            logger.info(f"PLAYOFF_TEST: playoff anchor set, gap={self.timingManager.scheduleGap}s between rounds")

        # Seeding is locked — freeze the bracket-challenge field (opens it for
        # submission until Round 1 kicks off). Already frozen on a resume.
        if not resuming:
            self._freezePlayoffSeeds(playoffTeams)

        for x in range(resumeFromRound - 1, numOfRounds):

            playoffGamesDict = {}
            playoffGamesList = []
            playoffGamesTasks = []
            self.currentSeason.leagueHighlights = []
            currentRound = x + 1
            gameNumber = 1
            roundStartTime = self.getWeekStartTime(datetime.datetime.utcnow(), 28 + currentRound)
            logger.info(f"Playoff round {currentRound}: startTime={roundStartTime.isoformat()}, now={datetime.datetime.utcnow().isoformat()}, mode={self.timingManager.mode.value}")

            if x < numOfRounds - 1:
                for league in self.leagueManager.leagues:
                    teamsInRound = []
                    gamesList = []

                    # Pressure is set ABSOLUTELY by round (1.5 / 1.7 / 1.9 ...)
                    # rather than incremented, so it's correct regardless of how
                    # many rounds actually ran in-process — i.e. resume-safe.
                    roundPressure = round(1.5 + 0.2 * (currentRound - 1), 2)
                    if currentRound == 1:
                        teamsInRound.extend(playoffsNonByeTeams[league.name])
                        for team in playoffTeams[league.name]:
                            team: FloosTeam.Team
                            team.pressureModifier = roundPressure
                            from managers.teamManager import logPressureDiag
                            logPressureDiag(team, "playoff_r1", season=self.currentSeason.seasonNumber, week=getattr(self.currentSeason, 'currentWeek', None))

                    else:
                        teamsInRound.extend(playoffTeams[league.name])
                        for team in playoffTeams[league.name]:
                            team: FloosTeam.Team
                            team.pressureModifier = roundPressure
                            from managers.teamManager import logPressureDiag
                            logPressureDiag(team, f"playoff_r{currentRound}", season=self.currentSeason.seasonNumber, week=getattr(self.currentSeason, 'currentWeek', None))

                    teamsInRound[:] = self._seedTeams(teamsInRound)

                    hiSeed = 0
                    lowSeed = len(teamsInRound) - 1

                    while lowSeed > hiSeed:
                        newGame = FloosGame.Game(
                            teamsInRound[hiSeed], teamsInRound[lowSeed],
                            timingManager=self.timingManager,
                            personalityManager=self.serviceContainer.getService('personality_manager'),
                            gameRules=self.currentSeason.gameRules,
                        )

                        # Assign unique integer ID and metadata
                        self._gameIdCounter += 1
                        newGame.id = self._gameIdCounter
                        newGame.seasonNumber = self.currentSeason.seasonNumber
                        newGame.playoffRound = currentRound
                        newGame.gameNumber = gameNumber
                        newGame.gameType = 'playoff'
                        
                        newGame.status = FloosGame.GameStatus.Scheduled
                        newGame.startTime = roundStartTime
                        newGame.isRegularSeasonGame = False
                        newGame.calculateWinProbability()
                        gamesList.append(newGame)
                        playoffGamesTasks.append(self._simulatePlayoffGame(newGame, len(playoffGamesTasks)))
                        newGame.leagueHighlights = self.currentSeason.leagueHighlights
                        hiSeed += 1
                        lowSeed -= 1
                        gameNumber += 1
                    
                    playoffGamesDict[league.name] = gamesList.copy()
                    playoffGamesList.extend(gamesList)

                if currentRound == numOfRounds - 1:
                    self.currentWeek = 28 + currentRound
                    self.currentWeekText = 'League Championship'
                else:
                    self.currentWeek = 28 + currentRound
                    self.currentWeekText = 'Playoffs Round {}'.format(x+1)
            else:
                floosbowlTeams = []
                for league in self.leagueManager.leagues:
                    floosbowlTeams.extend(playoffTeams[league.name])
                for team in floosbowlTeams:
                    team.leagueChampion = True
                floosbowlTeams[:] = self._seedTeams(floosbowlTeams)
                newGame = FloosGame.Game(
                    floosbowlTeams[0], floosbowlTeams[1],
                    timingManager=self.timingManager,
                    personalityManager=self.serviceContainer.getService('personality_manager'),
                    gameRules=self.currentSeason.gameRules,
                )

                # Assign unique integer ID and metadata
                self._gameIdCounter += 1
                newGame.id = self._gameIdCounter
                newGame.seasonNumber = self.currentSeason.seasonNumber
                newGame.playoffRound = currentRound
                newGame.gameNumber = gameNumber
                newGame.gameType = 'playoff'
                newGame.isFloosBowl = True
                # Admin-configurable halftime pause so the Floos Bowl halftime
                # show has room to play. None / unset → default halftime delay.
                try:
                    from database.models import AppSetting as _AppSetting
                    _hsRow = self.db_session.query(_AppSetting).filter_by(key='halftime_show_pause_seconds').first()
                    newGame.halftimeShowPauseSeconds = float(_hsRow.value) if (_hsRow and _hsRow.value) else None
                except Exception:
                    newGame.halftimeShowPauseSeconds = None

                newGame.status = FloosGame.GameStatus.Scheduled
                newGame.startTime = roundStartTime
                newGame.isRegularSeasonGame = False
                newGame.calculateWinProbability()
                playoffGamesList.append(newGame)
                playoffGamesTasks.append(self._simulatePlayoffGame(newGame, 0))
                newGame.leagueHighlights = self.currentSeason.leagueHighlights
                self.currentWeek = 28 + currentRound
                self.currentWeekText = 'Floos Bowl'
                newGame.homeTeam.pressureModifier = 2.5
                newGame.awayTeam.pressureModifier = 2.5
                from managers.teamManager import logPressureDiag
                logPressureDiag(newGame.homeTeam, "floos_bowl", season=self.currentSeason.seasonNumber, week=getattr(self.currentSeason, 'currentWeek', None))
                logPressureDiag(newGame.awayTeam, "floos_bowl", season=self.currentSeason.seasonNumber, week=getattr(self.currentSeason, 'currentWeek', None))

            # Track playoff round so pick-em can use virtual week numbers (29+)
            self.currentSeason.currentPlayoffRound = currentRound

            # If no games are currently visible (e.g. after a deploy/restart),
            # show the upcoming slate immediately so the API isn't empty.
            if not self.currentSeason.activeGames and not self.currentSeason.completedWeekGames:
                self.currentSeason.activeGames = playoffGamesList

            # Cache countdown time so REST API can serve it during the wait.
            self._cachedNextGameStart = roundStartTime

            # Wait for rollover — first playoff round is a cross-day transition
            # (week 28 at 18:00 ET → round 1 at 12:00 ET next day), so roll over early
            earlyMin = 480 if currentRound == 1 else 15
            if x < numOfRounds - 1:
                await self.timingManager.waitForPlayoffRound(roundStartTime, earlyMinutes=earlyMin)
            else:
                await self.timingManager.waitForChampionship(roundStartTime)

            # Rollover: show new matchups, clear previous round's completed data
            self.currentSeason.activeGames = playoffGamesList
            self.currentSeason.completedWeekGames = None
            self.currentSeason.currentWeek = self.currentWeek
            self.currentSeason.currentWeekText = self.currentWeekText
            self.currentSeason.schedule.append({'startTime': roundStartTime, 'games': playoffGamesList})

            # Free play-by-play memory from all prior completed games
            self._cleanupCompletedGameMemory(excludeGames=playoffGamesList)

            if BROADCASTING_AVAILABLE and broadcaster.is_enabled():
                nextStartIso = roundStartTime.isoformat() + 'Z' if roundStartTime else None
                await broadcaster.broadcast_season_event(SeasonEvent.weekStart(
                    seasonNumber=self.currentSeason.seasonNumber,
                    weekNumber=28 + currentRound,
                    gamesCount=len(playoffGamesList),
                    weekText=self.currentWeekText,
                    nextGameStartTime=nextStartIso,
                ))

            # Fire pre-game reminder 15 min before playoff games start
            await self._firePreGameReminder(roundStartTime, 28 + currentRound,
                                            self.currentWeekText,
                                            len(playoffGamesList))

            # Wait for exact game start time
            await self.timingManager.waitForGamesStart(roundStartTime)

            # Games are about to start — clear cached countdown
            self._cachedNextGameStart = None

            # Clear previous round's in-memory FP accumulator
            fantasyTracker = self.serviceContainer.getService('fantasy_tracker')
            if fantasyTracker:
                fantasyTracker.clearWeekFP()

            # Lock equipped cards for playoff week
            try:
                from database.connection import get_session as _getSession
                from database.repositories.card_repositories import EquippedCardRepository
                lockSession = _getSession()
                EquippedCardRepository(lockSession).lockWeek(
                    self.currentSeason.seasonNumber, 28 + currentRound
                )
                lockSession.commit()
                lockSession.close()
            except Exception as e:
                logger.error(f"Failed to lock equipped cards for playoff round {currentRound}: {e}")

            self.currentSeason.leagueHighlights.insert(0, {'event': {'text': '{} Starting Soon...'.format(self.currentWeekText)}})

            # Auto-pick favorites for users who opted in
            try:
                self._autoPickFavorites(playoffGamesList)
            except Exception as e:
                logger.error(f"Auto-pick favorites failed for playoff round {currentRound}: {e}")

            # Clear cached countdown — games are starting now
            self._cachedNextGameStart = None

            self.currentSeason.leagueHighlights.insert(0, {'event': {'text': '{} Start'.format(self.currentWeekText)}})

            # Start periodic leaderboard broadcast during playoff games
            playoffLeaderboardTask = asyncio.ensure_future(self._broadcastLeaderboardPeriodically())

            await asyncio.gather(*playoffGamesTasks)

            # Stop periodic leaderboard broadcast
            playoffLeaderboardTask.cancel()
            try:
                await playoffLeaderboardTask
            except asyncio.CancelledError:
                pass

            # Accumulate fatigue after each playoff round
            self._accumulateFatigue()

            # Round-1 bye teams rested — give them a small, market-tier-scaled
            # fatigue reprieve so they enter round 2 a touch fresher than the
            # teams that had to play (offsets the accumulation just applied).
            if currentRound == 1:
                self._applyByeFatigueRecovery(playoffsByeTeams)

            # Clear active games so roster swaps are unlocked between rounds.
            # Keep a reference so the API can still serve them until next round.
            self.currentSeason.completedWeekGames = self.currentSeason.activeGames
            self.currentSeason.activeGames = None

            # Resolve pick-em weekly prizes for this playoff round
            self._resolvePickEmWeek(self.currentSeason.seasonNumber, 28 + currentRound)

            # Supporter dividends for this playoff round — pays deep-run fans
            # (incl. the playoff round bonus) but does NOT tick tenure, so only
            # full regular seasons build loyalty.
            self._accrueSupporterDividends(self.currentSeason.seasonNumber, 28 + currentRound, tickTenure=False)

            # Re-score playoff brackets now this round's results are final.
            self._scorePlayoffBrackets()

            if len(playoffGamesList) == 1:
                game: FloosGame.Game = playoffGamesList[0]
                # Bind the bowl's own results. Previously this relied on a stale
                # gameResults left over from an earlier round's multi-game branch,
                # which is unset when resuming straight into the bowl (round 4) —
                # raising UnboundLocalError — and stored the wrong game's dict even
                # in a normal run.
                gameResults = game.gameDict
                playoffTeamsList.clear()

                season_str = 'Season {}'.format(self.currentSeason.seasonNumber)

                # Belt-and-braces: _simulatePlayoffGame's fallback should always leave a
                # winner, but this block writes the season's champion and every accolade
                # off it, so a None here would take the whole simulation task down (and
                # did — see that fallback's comment). Bail out of the accolade write
                # loudly instead, leaving the season championless but the sim alive.
                if getattr(game, 'winningTeam', None) is None:
                    logger.error(
                        f"Floos Bowl has no winning team — season "
                        f"{self.currentSeason.seasonNumber} will finish without a champion. "
                        f"This means the bowl failed to simulate AND the winner fallback "
                        f"did not fire; check the playoff game errors above."
                    )
                    return

                # Both teams in the Floosbowl are league champions
                if season_str not in game.winningTeam.leagueChampionships:
                    game.winningTeam.leagueChampionships.append(season_str)
                game.winningTeam.seasonTeamStats['leagueChamp'] = True
                
                # Only the winner is the Floosball champion
                if season_str not in game.winningTeam.floosbowlChampionships:
                    game.winningTeam.floosbowlChampionships.append(season_str)
                game.winningTeam.floosbowlChampion = True
                game.winningTeam.seasonTeamStats['floosbowlChamp'] = True
                
                self.currentSeason.champion = game.winningTeam
                runnerUp: FloosTeam.Team = game.losingTeam
                
                # Runner-up is also a league champion (made it to Floosbowl)
                if season_str not in runnerUp.leagueChampionships:
                    runnerUp.leagueChampionships.append(season_str)
                runnerUp.seasonTeamStats['leagueChamp'] = True
                runnerUp.eliminated = True
                
                _champText = '{0} {1} are Floos Bowl champions!'.format(self.currentSeason.champion.city, self.currentSeason.champion.name)
                self.currentSeason.leagueHighlights.insert(0, {'event': {'text': _champText}})
                if BROADCASTING_AVAILABLE and broadcaster.is_enabled() and LeagueNewsEvent:
                    await broadcaster.broadcast_season_event(LeagueNewsEvent.leagueNews(_champText))

                # Bracket challenge: final scoring + floobit prizes to top brackets.
                self._awardPlayoffBracketPrizes()
                # (The Showcase no longer pays a season-end lump — it pays a weekly
                # dividend during the regular season; see _awardShowcaseDividends.)

                playoffDict['Floos Bowl'] = gameResults
                self.currentSeason.freeAgencyOrder.append(runnerUp)
                self.currentSeason.freeAgencyOrder.append(self.currentSeason.champion)
                for player in self.currentSeason.champion.rosterDict.values():
                    if player:
                        player:FloosPlayer.Player
                        # Make sure team reference is valid
                        team_abbr = player.team.abbr if hasattr(player.team, 'abbr') else 'UNK'
                        team_color = player.team.color if hasattr(player.team, 'color') else '#000000'
                        player.leagueChampionships.append({'Season': self.currentSeason.seasonNumber, 'team': team_abbr, 'teamColor': team_color})

                self.recordsManager.updateChampionshipHistory(self.currentSeason.seasonNumber, self.currentSeason.champion, runnerUp)

                # Award Floobits to users whose favorite team won the Floosbowl
                from constants import FLOOSBOWL_WIN_REWARD
                self._awardFavoriteTeamBonus(
                    self.currentSeason.champion.id, FLOOSBOWL_WIN_REWARD, 'team_floosbowl_win',
                    description='Favorite team won the Floos Bowl!',
                    season=self.currentSeason.seasonNumber)
            else:
                for league in self.leagueManager.leagues:
                    for game in playoffGamesDict[league.name]:
                        game: FloosGame.Game
                        gameResults = game.gameDict
                        playoffDict[game.id] = gameResults
                        for team in playoffTeams[league.name]:
                            # Use direct object reference instead of gameDict to avoid KeyError
                            if game.losingTeam and team.name == game.losingTeam.name:
                                team.eliminated = True
                                _playoffElimText = '{0} {1} have faded from playoff contention'.format(team.city, team.name)
                                self.currentSeason.leagueHighlights.insert(0, {'event': {'text': _playoffElimText}})
                                if BROADCASTING_AVAILABLE and broadcaster.is_enabled() and LeagueNewsEvent:
                                    await broadcaster.broadcast_season_event(LeagueNewsEvent.leagueNews(_playoffElimText))
                                self.currentSeason.freeAgencyOrder.append(team)
                                playoffTeams[league.name].remove(team)
                                break

                

            # Note: Postseason data is now stored in the database, JSON output disabled
            # games_dir = os.path.join('{}/games'.format(strCurrentSeason))
            # os.makedirs(games_dir, exist_ok=True)
            # jsonFile = open(os.path.join(games_dir, 'postseason.json'), "w+")
            # jsonFile.write(json.dumps(playoffDict, indent=4))
            # jsonFile.close()
            
            if x < numOfRounds - 1:
                self.playerManager.sortPlayersByPosition()
                teamManager = self.serviceContainer.getService('team_manager')
                if teamManager:
                    teamManager.sortDefenses()

                # Broadcast next playoff round start time for countdown
                nextRoundStart = self.getWeekStartTime(datetime.datetime.utcnow(), 28 + currentRound + 1)
                self._cachedNextGameStart = nextRoundStart
                nextStartIso = nextRoundStart.isoformat() + 'Z' if nextRoundStart else None
                if BROADCASTING_AVAILABLE and broadcaster.is_enabled():
                    nextRoundText = 'Floos Bowl' if currentRound + 1 == numOfRounds else (
                        'League Championship' if currentRound + 1 == numOfRounds - 1 else
                        f'Playoffs Round {currentRound + 1}'
                    )
                    playoffResults = []
                    for g in (self.currentSeason.completedWeekGames or []):
                        playoffResults.append({
                            "homeTeam": {"name": g.homeTeam.name, "abbr": g.homeTeam.abbr},
                            "awayTeam": {"name": g.awayTeam.name, "abbr": g.awayTeam.abbr},
                            "homeScore": g.homeScore,
                            "awayScore": g.awayScore,
                            **self._frameAwareResultFields(g),
                        })
                    weekEndEvent = SeasonEvent.weekEnd(
                        seasonNumber=self.currentSeason.seasonNumber,
                        weekNumber=28 + currentRound,
                        results=playoffResults,
                        nextGameStartTime=nextStartIso,
                    )
                    broadcaster.broadcast_sync('season', weekEndEvent)
            else:
                # Floosbowl finished — broadcast week_end for the final round too
                if BROADCASTING_AVAILABLE and broadcaster.is_enabled():
                    finalResults = []
                    for g in (self.currentSeason.completedWeekGames or []):
                        finalResults.append({
                            "homeTeam": {"name": g.homeTeam.name, "abbr": g.homeTeam.abbr},
                            "awayTeam": {"name": g.awayTeam.name, "abbr": g.awayTeam.abbr},
                            "homeScore": g.homeScore,
                            "awayScore": g.awayScore,
                            **self._frameAwareResultFields(g),
                        })
                    weekEndEvent = SeasonEvent.weekEnd(
                        seasonNumber=self.currentSeason.seasonNumber,
                        weekNumber=28 + currentRound,
                        results=finalResults,
                        nextGameStartTime=None,
                    )
                    broadcaster.broadcast_sync('season', weekEndEvent)

            # Checkpoint this completed round so a restart resumes at the NEXT
            # unplayed round instead of replaying the bracket. Must be LAST in
            # the round body: a crash before here replays the round; after here
            # it's durably done. The bowl (final round) needs no checkpoint — the
            # post-playoff finish flips simulation_state to the offseason.
            if x < numOfRounds - 1:
                self._persistPlayoffState(currentRound, self.currentWeekText, playoffTeams)

        # Clear PLAYOFF_TEST phase flag
        self.timingManager.playoffPhase = False

    async def _simulatePlayoffGame(self, game: FloosGame.Game, gameIndex: int = -1) -> None:
        """Simulate a single playoff game"""

        try:
            # Create game instance with timing manager
            gameInstance = game

            # Set game type (playoff games)
            gameInstance.isRegularSeasonGame = False
            gameInstance.isPlayoff = True

            # No fantasy tracker callbacks for playoff games — FP is regular season only

            # Simulate the game
            self._applyChaosRulesIfCritical(gameInstance)
            await gameInstance.playGame()

            # Determine winner
            winner = game.homeTeam if gameInstance.homeScore > gameInstance.awayScore else game.awayTeam
            
            # Save game to database (player._lastGameFantasyPoints preserves FP after zeroing)
            if DB_IMPORTS_AVAILABLE and USE_DATABASE and self.game_repo:
                self._saveGameToDatabase(gameInstance)

            # Update team records
            self._updateTeamRecords(gameInstance)

            # Process post-game statistics (record-checking, team stat accumulation)
            self.recordsManager.processPostGameStats(gameInstance)

            # Update ELO ratings based on playoff game result using pre-game win probability
            teamManager = self.serviceContainer.getService('team_manager')
            if teamManager and hasattr(gameInstance, 'winningTeam') and gameInstance.winningTeam:
                _eloHome, _eloAway = gameInstance.format.eloScores(gameInstance)
                teamManager.updateEloAfterGame(
                    gameInstance.homeTeam,
                    gameInstance.awayTeam,
                    _eloHome,
                    _eloAway,
                    gameInstance.winningTeam,
                    getattr(gameInstance, 'preGameHomeWinProbability', None),
                    getattr(gameInstance, 'preGameAwayWinProbability', None)
                )

            # Check for records. Snapshot first so a break can be diffed out and
            # published to the news feed.
            _recordsBefore = self._snapshotRecords()
            self.recordsManager.checkPlayerGameRecords()
            self.recordsManager.checkTeamGameRecords(gameInstance)
            self._publishGameNews(gameInstance, _recordsBefore)

            # Resolve pick-em picks for this playoff game
            if gameIndex >= 0 and getattr(gameInstance, 'winningTeam', None):
                self._resolvePickEmGame(gameIndex, gameInstance)

        except Exception as e:
            logger.error(f"Error simulating playoff game: {e}")
            # A playoff game that fails to simulate must STILL yield a winner, or the
            # bracket has a hole and everything downstream that reads winningTeam
            # (accolades, champion, the next round's field) dereferences None and kills
            # the whole simulation task. Fall back to the score if the game got far
            # enough to have one, else the better regular-season record, else the home
            # team. A wrong-but-decided result loses one game; an undecided one lost a
            # 14-season league (an empty roster slot raised inside playGame, the bowl's
            # winningTeam stayed None, and the sim died on the accolade write).
            try:
                if getattr(game, 'winningTeam', None) is None:
                    home, away = getattr(game, 'homeTeam', None), getattr(game, 'awayTeam', None)
                    hs, as_ = getattr(game, 'homeScore', 0) or 0, getattr(game, 'awayScore', 0) or 0
                    if home is None or away is None:
                        return None
                    if hs != as_:
                        winner = home if hs > as_ else away
                    else:
                        def _wins(team):
                            stats = getattr(team, 'seasonTeamStats', None) or {}
                            return stats.get('wins', 0) if hasattr(stats, 'get') else 0
                        winner = home if _wins(home) >= _wins(away) else away
                    game.winningTeam = winner
                    game.losingTeam = away if winner is home else home
                    logger.error(
                        f"Playoff game failed to simulate — awarding it to {winner.name} "
                        f"on {'score' if hs != as_ else 'regular-season record'} so the "
                        f"bracket can continue. Investigate the failure above."
                    )
            except Exception as inner:
                logger.error(f"Playoff winner fallback also failed: {inner}")
            return None

    async def _completeSeasonSimulation(self) -> None:
        """Handle season completion tasks"""
        if not self.currentSeason:
            return

        logger.info("Completing season simulation")

        # OFFSEASON_TEST runs the entire regular season + playoffs silently
        # to keep the sim fast — but the offseason portion needs broadcasts
        # enabled so users can actually watch what's happening. Flip it on
        # here (right when the bowl ends) so season_end + the post_bowl
        # phase change fire correctly. _handleOffseason will keep it on
        # through the offseason flow and disable at the very end.
        if self.timingManager.mode == TimingMode.OFFSEASON_TEST and BROADCASTING_AVAILABLE:
            from api.game_broadcaster import broadcaster as bc
            from api.websocket_manager import manager as wsMgr
            if not bc.is_enabled():
                bc.enable(wsMgr)
                logger.info("offseason-test: broadcasting enabled for season-end + offseason")
        
        # Mark season as complete
        self.currentSeason.isComplete = True
        
        # Update league champions
        self.currentSeason.leagueChampions = self.leagueManager.getLeagueChampions()
        
        # Check season records
        self.recordsManager.checkSeasonRecords(self.currentSeason)
        
        # Update career records
        self.recordsManager.checkCareerRecords()
        
        # Save final player season stats BEFORE progression resets them
        playerManager = self.serviceContainer.getService('player_manager')
        if playerManager:
            playerManager.savePlayerData()

        # Handle player season progression (archives then resets seasonStatsDict)
        await self._handlePlayerSeasonProgression()

        # Save season statistics (team stats, season record, championships)
        self.saveSeasonStats()
        
        # Add to season history
        self.seasonHistory.append(self.currentSeason)
        
        # Update game state
        seasonNumber = self.currentSeason.seasonNumber
        self.serviceContainer.getService('game_state').setState('seasonsPlayed', seasonNumber)

        # Enter the post-bowl phase: Floos Bowl is over, we'll open the front
        # office in `post_championship` seconds. Surface this so the UI can
        # render a "Offseason in 1h" countdown during the otherwise-quiet gap.
        # Skip during fast catch-up — the delays are bypassed entirely there.
        delays = self.timingManager.delays
        postBowlWait = delays.get('post_championship', 0.0)
        if postBowlWait > 0 and not self.timingManager._isFastCatchingUp:
            await self._setOffseasonFlow(
                'post_bowl',
                datetime.datetime.utcnow() + datetime.timedelta(seconds=postBowlWait),
            )
        else:
            # No wait (fast modes / catch-up): still mark the post_bowl phase so
            # downstream consumers (e.g. the awards HoF window) can tell the
            # offseason has begun but not yet reached induction. A None target
            # means _handleOffseason skips the wait and proceeds immediately.
            await self._setOffseasonFlow('post_bowl', None)

        # Broadcast season_end so connected frontends know the season is over
        if BROADCASTING_AVAILABLE and broadcaster.is_enabled():
            championData = {}
            if self.currentSeason.champion:
                championData = {'name': self.currentSeason.champion.name, 'abbr': self.currentSeason.champion.abbr}
            seasonEndEvent = SeasonEvent.seasonEnd(
                seasonNumber=seasonNumber,
                champion=championData,
                standings=[],
            )
            broadcaster.broadcast_sync('season', seasonEndEvent)

        # Secret achievements that fire at season end (Sovereign, Soothsayer, Consecration)
        self._checkSeasonEndSecrets(seasonNumber)

        logger.info(f"Season {seasonNumber} completed. Champion: {self.currentSeason.champion.name if self.currentSeason.champion else 'None'}")
    
    async def restoreForOffseasonResume(self, seasonNumber: int) -> None:
        """Rebuild minimal state needed to re-enter _handleOffseason after a
        mid-offseason restart, WITHOUT re-running the regular season / playoffs
        and WITHOUT _clearSeasonData (which would wipe standings + team stats).

        Loads the season record from the DB, restores the startDate anchor,
        re-loads the schedule so any inspection code works, rebuilds the
        pending rookie pool (so a partial-rookie-draft resume sees the right
        candidates), and lets _persistOffseasonFlow's loaded values (already
        hydrated in __init__ via _loadOffseasonStateFromDb on construction)
        drive the phase + completed-steps state.
        """
        self.currentSeason = Season(seasonNumber)
        # Re-hydrate offseason flow phase + completed-steps from DB so
        # _handleOffseason skips the right phases on resume.
        self.loadOffseasonFlowFromDb()
        # Restore startDate so any timing-anchored UI/logging stays consistent.
        self._restoreSeasonStartDate(seasonNumber)
        if DB_IMPORTS_AVAILABLE and USE_DATABASE and self.game_repo:
            try:
                self._fillMissingScheduleWeeks(seasonNumber)
                self._loadScheduleFromDatabase(seasonNumber)
            except Exception as e:
                logger.warning(f"restoreForOffseasonResume: schedule reload failed: {e}")
        # Mark the season as in the offseason week.
        self.currentSeason.currentWeek = 0
        self.currentSeason.currentWeekText = 'Offseason'

    # ── Mid-playoff resume (hotfix/playoff-resume) ──────────────────────────
    def _persistPlayoffState(self, completedRound: int, roundText: str, playoffTeams: dict) -> None:
        """Snapshot the bracket to simulation_state after a round completes.

        Stores the last completed round, the surviving teams per league, and
        the accumulated free-agency/draft order (the one order-sensitive piece
        that can't be safely rebuilt from game results). Also flips
        in_playoffs=True so the resume path triggers. Mirrors
        _persistOffseasonFlow — direct single-row write on its own session.
        """
        if not (DB_IMPORTS_AVAILABLE and USE_DATABASE):
            return
        # Persist team season stats (streak/peakStreak now move during playoffs)
        # so a mid-playoff resume — which reloads team stats from the DB via
        # loadSeasonTeamStats — keeps the playoff-updated form instead of
        # reverting to the regular-season-end streak.
        try:
            self._saveTeamSeasonStatsToDatabase()
        except Exception as e:
            logger.warning(f"Could not persist team season stats during playoffs: {e}")
        try:
            import json
            from database.connection import get_session as _gs
            from database.models import SimulationState
            survivors = {
                league.name: [t.id for t in playoffTeams.get(league.name, [])]
                for league in self.leagueManager.leagues
            }
            faOrder = [getattr(t, 'id', None) for t in (self.currentSeason.freeAgencyOrder or [])]
            faOrder = [tid for tid in faOrder if tid is not None]
            payload = json.dumps({
                'completedRound': completedRound,
                'roundText': roundText,
                'survivors': survivors,
                'faOrder': faOrder,
            })
            sess = _gs()
            try:
                row = sess.query(SimulationState).filter_by(id=1).first()
                if not row:
                    return
                row.in_playoffs = True
                row.playoff_round = roundText
                row.current_week = 28 + completedRound
                row.playoff_state = payload
                sess.commit()
                logger.info(f"Persisted playoff state: completed round {completedRound} "
                            f"({roundText}), survivors per league + faOrder of {len(faOrder)}")
            finally:
                sess.close()
        except Exception as e:
            logger.warning(f"Could not persist playoff state: {e}")

    def loadPlayoffStateFromDb(self) -> Optional[dict]:
        """Read the persisted playoff snapshot. Returns None if absent/unparseable."""
        if not (DB_IMPORTS_AVAILABLE and USE_DATABASE):
            return None
        try:
            import json
            from database.connection import get_session
            from database.models import SimulationState
            sess = get_session()
            try:
                row = sess.query(SimulationState).filter_by(id=1).first()
                encoded = getattr(row, 'playoff_state', None) if row else None
                if not encoded:
                    return None
                return json.loads(encoded)
            finally:
                sess.close()
        except Exception as e:
            logger.warning(f"Could not load playoff state: {e}")
            return None

    async def restoreForPlayoffResume(self, seasonNumber: int) -> None:
        """Rebuild the minimal state needed to resume mid-playoffs, WITHOUT
        re-running the regular season (which would re-award MVP / All-Pro /
        season-end fantasy prizes) and WITHOUT _clearSeasonData.

        Loads the season record, the startDate anchor, regular-season standings,
        and the full schedule (which also advances _gameIdCounter past every
        existing game so newly-simulated resume-round games get fresh ids).
        """
        self.currentSeason = Season(seasonNumber)
        self._restoreSeasonStartDate(seasonNumber)
        teamManager = self.serviceContainer.getService('team_manager')
        if teamManager:
            teamManager.loadSeasonTeamStats(seasonNumber)
        # Restore per-player regular-season stats + recompute seasonPerformanceRating
        # (week 28 = end of the regular season). Without this the MVP/All-Pro ballot
        # is empty on a playoff resume — every candidate is filtered out because its
        # performance rating reads 0 — and the season-end MVP/All-Pro selection has
        # nothing to pick from. Mirrors the mid-regular-season resume restore.
        playerManager = self.serviceContainer.getService('player_manager')
        if playerManager:
            playerManager.loadCurrentSeasonStats(seasonNumber, currentWeek=28)
        if DB_IMPORTS_AVAILABLE and USE_DATABASE and self.game_repo:
            try:
                self._fillMissingScheduleWeeks(seasonNumber)
                self._loadScheduleFromDatabase(seasonNumber)
            except Exception as e:
                logger.warning(f"restoreForPlayoffResume: schedule reload failed: {e}")
        # Seed the playoff round state from the persisted snapshot so playoff-
        # aware API paths (pick-em week/label, week_text) read correctly during
        # the resume window — otherwise a playoff week with an unset
        # currentPlayoffRound shows up as "Week 29/30" instead of the round name.
        ps = self.loadPlayoffStateFromDb() or {}
        completedRound = ps.get('completedRound', 0)
        self.currentSeason.currentPlayoffRound = completedRound or None
        self.currentSeason.currentWeek = 28 + completedRound if completedRound else 28
        self.currentSeason.currentWeekText = ps.get('roundText') or 'Playoffs'

    async def resumePlayoffsAndFinishSeason(self, resumeFromRound: int, restoredState: Optional[dict]) -> None:
        """Resume an interrupted playoff bracket at resumeFromRound and run the
        normal post-playoff season wrap-up. Called by floosballApplication's
        restart path when simulation_state.in_playoffs is set."""
        logger.info(f"Resuming playoffs at round {resumeFromRound} for season "
                    f"{self.currentSeason.seasonNumber if self.currentSeason else '?'}")
        self._openGameStatsFile()
        await self._simulatePlayoffs(resumeFromRound=resumeFromRound, restoredState=restoredState)
        await self._finishSeasonAfterPlayoffs()

    async def handleOffseason(self, resumeFromOffseason: bool = False) -> None:
        """Handle offseason activities.

        resumeFromOffseason=True is used by floosballApplication's restart
        path when in_offseason=True was found in simulation_state. It tells
        _handleOffseason to honor the persisted completed-steps set and
        skip phases that already finished, instead of replaying from scratch.
        """
        await self._handleOffseason(resumeFromOffseason=resumeFromOffseason)

    async def _handleOffseason(self, resumeFromOffseason: bool = False) -> None:
        """Handle offseason activities — phased flow.

        Phase model (set on self._offseasonFlowPhase, target on self._offseasonFlowTarget):
          post_bowl   → set in _completeSeasonSimulation; waitPostChampionship runs here.
          frontoffice → resolve contracts + populate FA pool, then wait for the FA draft.
          pre_fa      → wait until top of next hour.
          fa_draft    → live FA picks.
          training    → silent player development calculations.

        Each phase marks a corresponding step in _offseasonCompletedSteps when
        it finishes. On resumeFromOffseason=True, the persisted set is loaded
        instead of reset, and each phase guards itself on _isOffseasonStepComplete
        so completed phases are skipped. For partial-draft state, the pre-init
        snapshot-restore in run_api.py rolls the DB back to phase-start before
        we ever reach this method, so the in-progress draft re-runs cleanly.
        """
        if resumeFromOffseason:
            logger.info(
                f"Resuming offseason: phase={self._offseasonFlowPhase}, "
                f"completed_steps={sorted(self._offseasonCompletedSteps)}"
            )
        else:
            logger.info("Processing offseason activities")
            # Fresh offseason — reset the per-phase completion tracker.
            self._resetOffseasonCompletedSteps()

        # OFFSEASON_TEST runs the season silently and only broadcasts during
        # the offseason. Enable the broadcaster as the very first step so
        # phase-change events for post_bowl + frontoffice (set before / inside
        # waitPostChampionship and the front-office decisions) actually reach
        # connected clients. Without this the navbar countdown stays blank
        # for the whole post-bowl + front-office stretch.
        offseasonTestBroadcastEnabled = False
        if self.timingManager.mode == TimingMode.OFFSEASON_TEST and BROADCASTING_AVAILABLE:
            from api.game_broadcaster import broadcaster as bc
            from api.websocket_manager import manager as wsMgr
            bc.enable(wsMgr)
            offseasonTestBroadcastEnabled = True
            logger.info(f"{self.timingManager.mode.value}: broadcasting enabled for offseason")

        # Re-broadcast the post_bowl phase NOW that broadcasting is enabled.
        # _completeSeasonSimulation set the state but its broadcast was lost
        # (broadcaster disabled at that point in OFFSEASON_TEST).
        if self._offseasonFlowPhase == 'post_bowl' and self._offseasonFlowTarget:
            await self._setOffseasonFlow(self._offseasonFlowPhase, self._offseasonFlowTarget)

        # ── PHASE: post_bowl ───────────────────────────────────
        # _completeSeasonSimulation sets the phase + target before this runs;
        # we just honor the configured wait. In SCHEDULED that's 1h.
        # Skipped on resume if we've already moved past this phase — the
        # waitPostChampionship clock check is itself idempotent (it polls
        # until target time) so re-entering during the wait is also fine.
        if not self._isOffseasonStepComplete('post_bowl'):
            await self.timingManager.waitPostChampionship()
            self._markOffseasonStepComplete('post_bowl')

        # Clear stale state from previous season's offseason. Only safe
        # on a fresh offseason — on resume these may already hold meaningful
        # in-flight data that the FA / draft phases depend on.
        if not resumeFromOffseason:
            self._offseasonTransactions = []
            # Wipe this season's recap log for a clean rebuild (resume keeps it).
            if self.currentSeason:
                self._clearRecapEvents(self.currentSeason.seasonNumber)
            self._offseasonGmResults = []
            self._offseasonFaVoteResults = {}
            self._offseasonFaPositionPriority = {}
            self.playerManager._faDraftBoards = {}
        # Reset freeAgencyComplete on every team — last season's FA draft
        # left it True, which would make this season's panel boot with every
        # team showing DONE + "FREE AGENCY COMPLETE" until the draft starts.
        # Skip on resume so a completed FA draft mid-offseason isn't reverted.
        teamManager = self.serviceContainer.getService('team_manager')
        if teamManager and not resumeFromOffseason:
            for t in teamManager.teams:
                t.freeAgencyComplete = False

        # Set offseason status (always safe to re-apply)
        if self.currentSeason:
            self.currentSeason.currentWeek = 0
            self.currentSeason.currentWeekText = 'Offseason'

        # Season-end prizes already awarded at end of regular season (before playoffs).
        # Process user season transitions (All-Pro grants, etc.) — non-idempotent,
        # gate on the existing frontoffice_decisions marker so we don't
        # double-credit on resume.
        if not self._isOffseasonStepComplete('frontoffice_decisions'):
            self._processUserSeasonTransitions()

        # ── PHASE: frontoffice ─────────────────────────────────
        # Front-office decisions all resolve here, then we hold until draft
        # day — free agency is the next live event now that the rookie draft
        # is gone, and it keeps the same next-day noon ET slot.
        await self._setOffseasonFlow('frontoffice', self._computeDraftDayTarget())

        # All five front-office sub-steps are non-idempotent (FA-year increment,
        # GM-vote resolution, coach increments, contract decrements, cut votes
        # — each mutates persistent state). Gate behind a single completion
        # marker so a future phase-aware resume can skip the whole batch.
        gmResults = []
        if not self._isOffseasonStepComplete('frontoffice_decisions'):
            # STEP 1: Increment free agent years for existing free agents
            logger.info("Step 1: Increment free agent years")
            for player in self.playerManager.freeAgents:
                if hasattr(player, 'freeAgentYears'):
                    player.freeAgentYears += 1
                else:
                    player.freeAgentYears = 1

            # STEP 2: (was: resolve GM fire/re-sign votes). The binding votes
            # are gone — coach turnover is decided in STEP 2.5 by gmTurnover,
            # and re-signs by the GM brain in STEP 2.7.

            # Safety net: any team without a coach after fire/hire resolution
            # gets one auto-generated + persisted. Catches edge cases like a
            # passed fire vote with no quorum-meeting hire vote where every
            # candidate failed its roll. assignCoachesToTeams is a no-op for
            # teams that already have one, so this is cheap to call here.
            teamManager_safety = self.serviceContainer.getService('team_manager')
            if teamManager_safety:
                coachlessBefore = [t.name for t in teamManager_safety.teams if t.coach is None]
                if coachlessBefore:
                    logger.warning(
                        f"Coach safety net engaging for {len(coachlessBefore)} "
                        f"team(s) without a coach: {coachlessBefore}"
                    )
                    teamManager_safety.assignCoachesToTeams()

            # STEP 2.5: Increment coach seasons and handle retirements
            logger.info("Step 2.5: Coach season increments and retirements")
            teamManager = self.serviceContainer.getService('team_manager')
            if teamManager:
                seasonNum = self.currentSeason.seasonNumber if self.currentSeason else 1
                teamManager.handleCoachRetirement(seasonNum)
                # Save updated coach data (seasonsCoached increment + any new coaches)
                for team in teamManager.teams:
                    if team.coach:
                        teamManager._saveCoachToDatabase(team)

            # STEP 2.7: Retention limits — per team, decide which EXPIRING players
            # to keep, applying whichever levers are enabled (re-sign-once, per-
            # offseason count limit, salary cap). The rest WALK to FA. Sets
            # _gmResigned flags that STEP 3 consumes. Fan resign votes honored first.
            # See docs/PARITY_PROSPECT_PLAN.md Phase 5.
            logger.info("Step 2.7: Retention (re-sign) decisions")
            self._applyRetentionLimits()

            # STEP 3: Process contract decrements and retirements for rostered players
            logger.info("Step 3: Contract decrements and team retirements")
            await self._processRosteredPlayerContracts()

            # STEP 3.5: (was: resolve cut votes). Cuts are now the GM brain's
            # cut-for-upgrade call, made during the STEP 2.7 assessment sweep.

            # STEP 3.6: Award the "Scorched Earth" secret to fans who voted to
            # tear their team all the way down. Runs here, after cuts, while the
            # roster still reflects every removal and before the drafts refill it.
            logger.info("Step 3.6: Award clean-house achievements")

            self._markOffseasonStepComplete('frontoffice_decisions')
        else:
            logger.info("Frontoffice decisions already completed (resumed) — skipping STEP 1-3.5")

        # Final coach assertion before any draft phase fires. handleCoachRetirement
        # (STEP 2.5 above) replaces retiring coaches, and the fire-vote safety net
        # catches anyone whose hire vote fell through. This last sweep is paranoia
        # for any remaining hole — every team must have a coach once we leave the
        # frontoffice phase, since training, draft AI, and game sim all assume one.
        teamManager_final = self.serviceContainer.getService('team_manager')
        if teamManager_final:
            stillCoachless = [t.name for t in teamManager_final.teams if t.coach is None]
            if stillCoachless:
                logger.error(
                    f"Coach assertion failed entering rookie draft: {stillCoachless} "
                    f"— forcing assignCoachesToTeams"
                )
                teamManager_final.assignCoachesToTeams()

        # Fire offseason_start so the frontend transitions into OffseasonPanel
        # before rookie events start streaming. Broadcaster was already
        # enabled at the top of this method for OFFSEASON_TEST. FAST_WEEKLY
        # keeps broadcasting on the whole time with game-event suppression.
        needOffseasonStart = self.timingManager.mode in (TimingMode.OFFSEASON_TEST, TimingMode.FAST_WEEKLY) and BROADCASTING_AVAILABLE
        if needOffseasonStart:
            # Broadcast offseason_start with draft order + roster snapshots.
            # Rookie draft uses the worst-first order from playoffs. The FA
            # draft later updates the draft order to the tier-sorted sequence
            # via a lighter fa_draft_order_update event that doesn't reset
            # accumulated transactions.
            try:
                faOrderEarly = getattr(self.currentSeason, 'freeAgencyOrder', []) if self.currentSeason else []
                draftOrderList = [
                    {
                        'name': t.name,
                        'city': getattr(t, 'city', ''),
                        'abbr': getattr(t, 'abbr', t.name[:3].upper()),
                        'id': getattr(t, 'id', None),
                        'color': getattr(t, 'color', None),
                        'fundingTier': getattr(t, 'fundingTier', 'MID_MARKET'),
                        'fundingTierRank': getattr(t, 'fundingTierRank', 3),
                    }
                    for t in faOrderEarly
                ]
                rosterSnapshots = {}
                for t in faOrderEarly:
                    abbr = getattr(t, 'abbr', t.name[:3].upper())
                    roster = {}
                    for slot in ('qb', 'rb', 'wr1', 'wr2', 'te', 'k'):
                        p = t.rosterDict.get(slot)
                        if p:
                            roster[slot] = {
                                'id': p.id, 'name': p.name,
                                'position': p.position.name,
                                'rating': round(p.playerRating, 1),
                                'tier': p.playerTier.name,
                                'termRemaining': getattr(p, 'termRemaining', 0),
                            }
                        else:
                            roster[slot] = None
                    rosterSnapshots[abbr] = roster
                startEvent = OffseasonEvent.start(draftOrderList)
                startEvent['rosterSnapshots'] = rosterSnapshots
                await broadcaster.broadcast_season_event(startEvent)
                await asyncio.sleep(2)  # brief so frontend mounts panel
            except Exception as e:
                logger.warning(f"Could not broadcast offseason start: {e}")

        # Replay accumulated GM vote resolutions (fire coach, resign, cut)
        # now that the panel is mounted. The OffseasonPanel's Directives tab
        # surfaces these so users see what passed without bouncing to the
        # Front Office tab.
        self._offseasonGmResults = list(gmResults)
        if BROADCASTING_AVAILABLE and broadcaster:
            for r in gmResults:
                try:
                    await broadcaster.broadcast_season_event(
                        GmEvent.voteResolved(
                            teamId=r.get('teamId'),
                            teamName=r.get('teamName', ''),
                            voteType=r.get('voteType', ''),
                            outcome=r.get('outcome', ''),
                            targetPlayerName=r.get('targetPlayerName'),
                            totalVotes=r.get('totalVotes', 0),
                            votesAgainst=r.get('votesAgainst', 0),
                            threshold=r.get('threshold', 0),
                            probability=r.get('probability', 0.0),
                        )
                    )
                except Exception as e:
                    logger.warning(f"Could not broadcast gm vote resolution: {e}")

        # STEP 3.70: FA voting RESOLUTION (snapshot only — window stays open).
        # Resolves ballots so the predraft pass has each team's #1 ranked
        # choice for fan-directed prospect promotions. The window itself
        # stays open so users watching the rookie draft / pre-FA wait can
        # still revise their ballots — the final resolution + close happens
        # right before the FA draft kicks off (see Step 5.5 below).
        logger.info("Step 3.70: FA ballot resolution (window stays open)")

        # STEP 3.75: Pre-draft team setup (resigns / cuts / prospect promotions).
        # Computed and persisted instantly here so the FA pool is fully
        # resolved by the time the front-office phase ends — there's no
        # team-by-team roll-through later. The OffseasonPanel + Front Office
        # page render whatever has been persisted, so users browsing during
        # the noon-ET wait see the complete picture.
        logger.info("Step 3.75: Pre-draft team setup (instant)")
        faOrderForPredraft = getattr(self.currentSeason, 'freeAgencyOrder', []) if self.currentSeason else []
        if faOrderForPredraft:
            await self._runPreDraftPass(faOrderForPredraft, gmResults)

        # ── End of front-office phase ────────────────────────
        # The rookie draft used to sit here, between the front office and free
        # agency. There is no rookie class to draft any more, so the offseason
        # goes straight from front-office decisions to the FA draft — but it
        # still HOLDS for draft day first. Dropping that hold with the phase
        # would have pulled free agency to the next top of the hour, i.e. an
        # hour after the Floos Bowl, overnight.
        await self.timingManager.waitForOffseason()
        await self.timingManager.waitUntilNoonEt()

        # Pre-FA integrity sweep — the draft pool must not include players
        # who are already on a roster (promotions just moved some prospects up,
        # contract-expiration paths may have left stale refs, etc.).
        # Without this, the FA draft round-robin wastes rounds skipping
        # "already rostered" picks until every offender is weeded out.
        self._validateRosterIntegrity()

        # ── PHASE: pre_fa ────────────────────────────────────
        # Two-stage wait: first leave the front-office results on screen
        # for a beat, then fire the FA preview so
        # the team board switches to tier groupings + the FA pool with a
        # half-hour to spare before the actual draft.
        await self._setOffseasonFlow('pre_fa', self._computeFaDraftTarget())

        # Stage 1 — keep front-office results visible until 30 min before FA draft.
        # SCHEDULED: poll until (top-of-hour − 30 min). Test modes split the
        # configured fa_draft_wait in half (post-rookie / FA-preview).
        mode = self.timingManager.mode
        from managers.timingManager import TimingMode as _TM
        if not self.timingManager._isFastCatchingUp:
            if mode == _TM.SCHEDULED:
                faTarget = type(self.timingManager)._nextTopOfHourUtc()
                previewTime = faTarget - datetime.timedelta(minutes=30)
                pollInterval = self.timingManager.delays.get('daily_check', 30.0)
                while datetime.datetime.utcnow() < previewTime:
                    await asyncio.sleep(pollInterval)
            elif mode in (_TM.OFFSEASON_TEST, _TM.TEST_SCHEDULED):
                halfWait = self.timingManager.delays.get('fa_draft_wait', 60.0) / 2
                if halfWait > 0:
                    await asyncio.sleep(halfWait)

        # Stage 2 — broadcast the FA preview (tier-grouped team board + FA
        # pool) so users have ~30 min to study the order before picks fire.
        await self._broadcastFaDraftPreview()

        # Stage 3 — wait the remainder until the FA draft kicks off.
        # SCHEDULED: poll until top-of-hour (already past stage-1 target).
        # Test modes: sleep the second half of fa_draft_wait.
        if not self.timingManager._isFastCatchingUp:
            if mode == _TM.SCHEDULED:
                faTarget = type(self.timingManager)._nextTopOfHourUtc()
                pollInterval = self.timingManager.delays.get('daily_check', 30.0)
                while datetime.datetime.utcnow() < faTarget:
                    await asyncio.sleep(pollInterval)
            elif mode in (_TM.OFFSEASON_TEST, _TM.TEST_SCHEDULED):
                halfWait = self.timingManager.delays.get('fa_draft_wait', 60.0) / 2
                if halfWait > 0:
                    await asyncio.sleep(halfWait)

        # ── PHASE: fa_draft ──────────────────────────────────
        # Snapshot taken on phase entry. On partial-draft resume the pre-init
        # restore in run_api.py rolls the DB back to that snapshot so FA picks
        # re-run cleanly without leaving half-assigned free agents.
        await self._setOffseasonFlow('fa_draft', None)

        if self._isOffseasonStepComplete('fa_draft'):
            logger.info("Steps 5.5–6.5 skipped — fa_draft already complete")
        else:
            # STEP 5.5: Final FA ballot resolution + window close.
            # Re-runs RCV with whatever ballots have been submitted up to this
            # exact moment, then officially closes the window. Users watching
            # the post-rookie wait can revise ballots until this fires.
            logger.info("Step 5.5: Final FA ballot resolution + window close")

            # STEP 5.75: Apply prospect promotions. Driven by the
            # *final* ballot directives (just resolved above), so any post-cuts
            # ballot revisions are honored. Runs before the round-robin so
            # promoted prospects fill their slots first.
            logger.info("Step 5.75: Apply prospect promotions")
            await self._applyFanVotedPromotions()

            # STEP 5.9: Final supply guarantee — now that FA retirements, cuts,
            # expiries and the rookie draft are all resolved, top up any position
            # still short of filling every roster slot. Catches FA retirements
            # decided after the week-22 check. Idempotent with that earlier pass.
            self._ensurePositionSupply(reason='pre-FA-draft guarantee')

            # STEP 5.95: Every team builds its own board off the FINAL pool.
            # Two things are settled here and never revisited mid-draft: which
            # free agents would sign for this club, and what this GM thinks
            # each of them is worth. See _buildFaDraftBoards.
            logger.info("Step 5.95: Build per-team FA draft boards")
            self._buildFaDraftBoards()

            # STEP 6: FA Draft
            logger.info("Step 6: Free agency draft")
            await self._processFreeAgency()

            # STEP 6.5: Validate roster/FA integrity after draft too — defensive,
            # in case new mismatches were introduced during picks.
            self._validateRosterIntegrity()

            self._markOffseasonStepComplete('fa_draft')

        # ── PHASE: training ──────────────────────────────────
        # Players just signed by FA are now under their new team's coach +
        # market tier — training runs with that context.
        await self._setOffseasonFlow('training', None)

        # Training + post-training finalize (steps 7–12) are all non-idempotent
        # — they bump skills, retire/induct players, reset season counters.
        # Single completion gate so a future phase-aware resume skips them on
        # restart instead of double-training and double-inducting.
        if not self._isOffseasonStepComplete('training_and_finalize'):
            # STEP 7: Player offseason training (after FA draft so new signings train with their coach)
            # Prospects train through their drafting team's coach/funding too, so coaches
            # with strong playerDevelopment and MEGA-market teams grow pipelines faster.
            logger.info("Step 7: Player offseason training")
            teamDevRating: dict = {}       # player.id → coach dev rating
            teamFundingBonus: dict = {}    # player.id → facility dev bonus
            teamManager = self.serviceContainer.getService('team_manager')
            for team in teamManager.teams:
                coachDevRating = getattr(getattr(team, 'coach', None), 'playerDevelopment', 50)
                # Training Facility level (Markets→Facilities) replaces the old
                # market-tier dev bonus; migrated levels reproduce the tier perks.
                fundingBonus = team.facilityEffect('dev_bonus')
                # Rostered players train with this team's coach/funding
                for rosterPlayer in team.rosterDict.values():
                    if rosterPlayer is not None and hasattr(rosterPlayer, 'id'):
                        teamDevRating[rosterPlayer.id] = coachDevRating
                        teamFundingBonus[rosterPlayer.id] = fundingBonus
                # Prospects get the same treatment — they're part of this team's pipeline
                for prospect in getattr(team, 'prospects', []):
                    if hasattr(prospect, 'id'):
                        teamDevRating[prospect.id] = coachDevRating
                        teamFundingBonus[prospect.id] = fundingBonus
            for player in self.playerManager.activePlayers:
                if hasattr(player, 'offseasonTraining'):
                    pid = getattr(player, 'id', None)
                    # None (not 50) for anyone with no team — that is the signal
                    # to train off their OWN mental makeup. The old default of 50
                    # produced devBias -1, so an unsigned player decayed worse
                    # than one under the worst coach in the league.
                    devRating = teamDevRating.get(pid, None)
                    fundingBonus = teamFundingBonus.get(pid, 0)
                    player.offseasonTraining(coachDevRating=devRating, fundingDevBonus=fundingBonus)

            # STEP 7.5: Advance prospect development window — auto-release washouts
            logger.info("Step 7.5: Prospect development window advancement")
            self.playerManager._advanceProspectWindow()

            # STEP 8: (retired) Handling retired players on fantasy rosters is gone in
            # the fantasy/cards fusion — the roster IS the equipped cards, so a retired
            # player's card simply isn't re-minted next season (templates are
            # season-scoped); there is no bare-player roster slot to auto-fill.

            # STEP 9: Reset season performance ratings + season WPA value totals
            logger.info("Step 9: Reset season performance ratings")
            for player in self.playerManager.activePlayers:
                if hasattr(player, 'seasonPerformanceRating'):
                    player.seasonPerformanceRating = 0
                player.seasonWpa = 0.0
                player.seasonDefWpa = 0.0
                player.seasonWpaSnaps = 0
                player.seasonDefWpaSnaps = 0

            # STEP 10: Update team ratings and defenses after roster changes
            logger.info("Step 10: Update team ratings")
            await self._updateTeamRatings()

            # STEP 11: Induct Hall of Fame players
            logger.info("Step 11: Hall of Fame inductions")
            # Fan-voted path owns the ballot (vote + class cap, or points
            # fallback below quorum). Then inductHallOfFame runs as a points-only
            # SAFETY NET for NOT-on-ballot retirees (first-deploy / stragglers).
            ballotIds = set()
            try:
                from database.connection import get_session
                from managers.awardsManager import AwardsManager
                hofSeason = self.currentSeason.seasonNumber if self.currentSeason else 0
                _s = get_session()
                try:
                    am = AwardsManager(_s, self.playerManager, lowQuorum=self._isTestMode)
                    inducted = am.resolveHofInductions(hofSeason)
                    ballotIds = am.ballotRepo.getAllPlayerIds()
                    _s.commit()
                    logger.info(f"HoF: {len(inducted)} inducted via ballot (S{hofSeason})")
                finally:
                    _s.close()
            except Exception as e:
                logger.error(f"HoF ballot induction failed, safety net only: {e}")
            self.playerManager.inductHallOfFame(excludePlayerIds=ballotIds)

            # STEP 12: Save unused names
            self.playerManager.saveUnusedNames()

            self._markOffseasonStepComplete('training_and_finalize')
        else:
            logger.info("Training + finalize already completed (resumed) — skipping STEP 7-12")

        # ── Offseason flow complete ──────────────────────────
        # Clear phase + target so the UI falls back to the plain "Offseason"
        # label (until the next-season transition kicks in via /api/season's
        # next_season_start_time).
        await self._setOffseasonFlow(None, None)

        # Disable broadcasting now that the offseason is fully resolved —
        # OFFSEASON_TEST keeps games silent until the next bowl ends.
        if offseasonTestBroadcastEnabled:
            from api.game_broadcaster import broadcaster as bc
            bc.disable()
            logger.info(f"{self.timingManager.mode.value}: broadcasting disabled after offseason")

        logger.info("Offseason activities complete")
    
    def _reprovisionExistingUsers(self) -> None:
        """Re-grant starter floobits and cards to existing users who lost them in a fresh start."""
        try:
            from database.connection import get_session
            from database.models import User, UserCurrency
            from api.auth import _provisionStarterPack
            # Pass currentSeason explicitly — at boot time this runs BEFORE
            # api.main.floosball_app is wired, so _provisionStarterPack's
            # fallback lookup of seasonManager wouldn't find anything.
            currentSeason = self.currentSeason.seasonNumber if self.currentSeason else None
            session = get_session()
            usersWithoutCurrency = (
                session.query(User)
                .outerjoin(UserCurrency, User.id == UserCurrency.user_id)
                .filter(UserCurrency.user_id.is_(None))
                .all()
            )
            if not usersWithoutCurrency:
                session.close()
                return
            for user in usersWithoutCurrency:
                _provisionStarterPack(session, user, currentSeason=currentSeason)
            session.commit()
            session.close()
            logger.info(f"Re-provisioned starter packs for {len(usersWithoutCurrency)} existing user(s)")
        except Exception as e:
            logger.warning(f"Could not re-provision starter packs: {e}")

    def _maybeRunParityRemap(self, seasonNumber: int = 0) -> None:
        """One-time parity migration: deflate an inflated legacy pool onto the
        new true-skill curve and freeze it. Runs exactly once (persisted marker),
        auto-skips a pool already on the curve (fresh start or already re-mapped),
        and persists the re-rated players before marking done so a crash can't
        leave the marker set with the old ratings still on disk. Records the season
        the deflation landed on (`parity_remap_season`) so the rating-history rebase
        knows the cliff boundary. See docs/PARITY_PROSPECT_PLAN.md Phase 3."""
        from database.models import AppSetting
        KEY = 'parity_remap_done'
        try:
            row = self.db_session.query(AppSetting).filter_by(key=KEY).first()
            if row is not None and row.value == '1':
                return
            frac = self.playerManager.parityStarFraction()
            # Old inflated pools sit ~40% 4-5-star; fresh/re-mapped pools ~19-21%.
            if frac > 0.28:
                n = self.playerManager.remapPoolToTrueSkill()
                self.playerManager.savePlayerData()   # persist BEFORE marking done
                logger.info(f"Parity re-map applied to {n} players (pool was {frac:.0%} 4-5-star)")
                # Record the boundary season for the history rebase (only when the
                # deflation actually applied — a skipped/already-on-curve pool has no cliff).
                if seasonNumber:
                    seasonRow = self.db_session.query(AppSetting).filter_by(key='parity_remap_season').first()
                    if seasonRow is None:
                        self.db_session.add(AppSetting(key='parity_remap_season', value=str(seasonNumber)))
                    else:
                        seasonRow.value = str(seasonNumber)
            else:
                logger.info(f"Parity re-map skipped — pool already on curve ({frac:.0%} 4-5-star)")
            if row is None:
                self.db_session.add(AppSetting(key=KEY, value='1'))
            else:
                row.value = '1'
            self.db_session.commit()
        except Exception as e:
            # Don't set the marker on failure — retry at the next cutover.
            logger.error(f"Parity re-map failed (will retry next cutover): {e}")

    def _maybeRebaseRatingHistoryForParity(self) -> None:
        """After the parity re-map deflated current ratings, rescale each player's
        PRE-remap progression history so the chart doesn't cliff at the boundary.
        Runs once (persisted marker), only after the remap applied AND the remap-
        season snapshot exists (so the boundary ratio is computable). Idempotent and
        approximate. See docs/PARITY_PROSPECT_PLAN.md Phase 3."""
        from database.models import AppSetting
        DONE = 'parity_history_rebased'
        try:
            if self.db_session.query(AppSetting).filter_by(key='parity_remap_done', value='1').first() is None:
                return  # remap hasn't applied — nothing to rebase
            if self.db_session.query(AppSetting).filter_by(key=DONE, value='1').first() is not None:
                return
            seasonRow = self.db_session.query(AppSetting).filter_by(key='parity_remap_season').first()
            if seasonRow is None or not (seasonRow.value or '').isdigit():
                return  # unknown boundary — dev DBs set this explicitly; retry later
            remapSeason = int(seasonRow.value)
            result = self.playerManager.rebaseRatingHistoryForRemap(remapSeason)
            # Only mark done once the boundary snapshot existed (eligible players found);
            # otherwise retry on a later boot when the remap-season row is present.
            if result.get('eligible', 0) > 0:
                self.db_session.add(AppSetting(key=DONE, value='1'))
                self.db_session.commit()
                logger.info(f"Parity history rebase complete: {result}")
        except Exception as e:
            logger.error(f"Parity history rebase failed (will retry): {e}")

    def _maybeFreezeLegacyDevArc(self) -> None:
        """After the parity re-map, freeze existing (non-prospect) players at their
        current level so they don't surface a spurious 'Expected'/'Ceiling' growth
        arc (the re-map had handed rising legacy vets a development runway). Runs
        once (persisted marker), only after the remap applied. Idempotent + a no-op
        on a pool re-mapped with the corrected freeze. See docs/PARITY_PROSPECT_PLAN.md."""
        from database.models import AppSetting
        DONE = 'legacy_devarc_frozen'
        try:
            if self.db_session.query(AppSetting).filter_by(key='parity_remap_done', value='1').first() is None:
                return  # remap hasn't applied — nothing to freeze
            if self.db_session.query(AppSetting).filter_by(key=DONE, value='1').first() is not None:
                return
            result = self.playerManager.freezeLegacyDevelopmentArc()
            self.db_session.add(AppSetting(key=DONE, value='1'))
            self.db_session.commit()
            logger.info(f"Legacy dev-arc freeze complete: {result}")
        except Exception as e:
            logger.error(f"Legacy dev-arc freeze failed (will retry): {e}")

    def _generateCardTemplates(self, seasonNumber: int) -> None:
        """Generate card templates for all active players for a season.

        Uses a dedicated session to avoid holding a write lock on the shared
        simulation session (which would block API endpoints on SQLite).
        Passes previous season's MVP, Champion, and All-Pro data for classification.
        """
        try:
            from managers.cardManager import CardManager
            from database.connection import get_session

            session = get_session()

            # Extract classification data from previous season
            mvpPlayerId = None
            championPlayerIds = set()
            allProPlayerIds = set()

            # Classifications come from the PREVIOUS season, not the current one
            prevSeasonNum = seasonNumber - 1
            prevSeason = self.seasonHistory[-1] if self.seasonHistory else None

            if prevSeason and prevSeason.seasonNumber == prevSeasonNum:
                # In-memory data available (normal flow after completing a season)
                mvpData = getattr(prevSeason, 'mvp', None)
                if mvpData and isinstance(mvpData, dict):
                    mvpPlayerId = mvpData.get('id')
                allProPlayerIds = getattr(prevSeason, 'allProPlayerIds', set())
            elif prevSeasonNum >= 1:
                # Resume fallback: read from DB + player objects
                mvpPlayerId, championPlayerIds, allProPlayerIds = \
                    self._loadClassificationsFromDB(session, prevSeasonNum)

            # Champion IDs ALWAYS come from the Floos-Bowl roster SNAPSHOT, never the
            # live roster — by the time this runs the offseason has churned the team, so
            # the live roster would tag players who weren't on it when it won.
            try:
                from database.models import Season as _SeasonRow
                _row = session.query(_SeasonRow).filter(_SeasonRow.season_number == prevSeasonNum).first()
                if _row and _row.champion_player_ids:
                    import json as _jsonC
                    championPlayerIds = set(_jsonC.loads(_row.champion_player_ids))
            except Exception as _e:
                logger.warning(f"Could not load champion snapshot for season {prevSeasonNum}: {_e}")
            cardManager = CardManager(self.serviceContainer)
            count = cardManager.generateSeasonTemplates(
                session, seasonNumber,
                mvpPlayerId=mvpPlayerId,
                championPlayerIds=championPlayerIds,
                allProPlayerIds=allProPlayerIds,
            )
            session.commit()
            # (No Hall of Fame minting pass. Legacy collection cards are the
            # inductee's OWN past-season prestige prints, which already exist and
            # are never pruned — see cardManager.getLegacyCollectionTemplates.)
            session.close()
            logger.info(f"Card template generation complete: {count} templates for season {seasonNumber}")
        except Exception as e:
            logger.warning(f"Card template generation failed: {e}")
            import traceback
            logger.debug(traceback.format_exc())

    def _loadClassificationsFromDB(self, session, prevSeasonNum: int):
        """Load classification data from DB and player objects on resume.

        Uses Season DB row for MVP and champion_team_id, player objects for
        All-Pro seasons, and team rosters for champion player IDs.
        Returns (mvpPlayerId, championPlayerIds, allProPlayerIds).
        """
        mvpPlayerId = None
        championPlayerIds = set()
        allProPlayerIds = set()

        try:
            from database.models import Season as DBSeason
            import json

            dbSeason = session.query(DBSeason).filter_by(season_number=prevSeasonNum).first()
            if not dbSeason:
                logger.info(f"No DB season record for season {prevSeasonNum} — skipping classifications")
                return mvpPlayerId, championPlayerIds, allProPlayerIds

            # MVP
            if dbSeason.mvp_player_id:
                mvpPlayerId = dbSeason.mvp_player_id
                logger.info(f"Resume: loaded MVP player ID {mvpPlayerId} from DB")

            # All-Pro from DB column
            if dbSeason.all_pro_player_ids:
                try:
                    ids = json.loads(dbSeason.all_pro_player_ids)
                    allProPlayerIds.update(ids)
                    logger.info(f"Resume: loaded {len(ids)} All-Pro player IDs from DB")
                except (json.JSONDecodeError, TypeError):
                    pass

            # If All-Pro not in DB, fall back to player objects
            if not allProPlayerIds:
                for player in self.playerManager.activePlayers:
                    apSeasons = getattr(player, 'allProSeasons', [])
                    if prevSeasonNum in apSeasons:
                        allProPlayerIds.add(player.id)
                if allProPlayerIds:
                    logger.info(f"Resume: loaded {len(allProPlayerIds)} All-Pro IDs from player objects")

            # Champion team roster
            if dbSeason.champion_team_id:
                teamManager = self.serviceContainer.getService('team_manager')
                champTeam = teamManager.getTeamById(dbSeason.champion_team_id)
                if champTeam and hasattr(champTeam, 'rosterDict'):
                    for player in champTeam.rosterDict.values():
                        if player and hasattr(player, 'id'):
                            championPlayerIds.add(player.id)
                    logger.info(f"Resume: loaded {len(championPlayerIds)} Champion player IDs from team {champTeam.name}")

        except Exception as e:
            logger.warning(f"Failed to load classifications from DB: {e}")

        return mvpPlayerId, championPlayerIds, allProPlayerIds

    def _generateRookieCardTemplates(self, seasonNumber: int) -> None:
        """Generate card templates for newly drafted rookies.

        Uses a dedicated session to avoid holding a write lock on the shared
        simulation session.
        """
        try:
            from managers.cardManager import CardManager
            from database.connection import get_session
            session = get_session()
            cardManager = CardManager(self.serviceContainer)
            count = cardManager.generateRookieTemplates(session, seasonNumber)
            session.commit()
            session.close()
            logger.info(f"Rookie card template generation complete: {count} templates for season {seasonNumber}")
        except Exception as e:
            logger.warning(f"Rookie card template generation failed: {e}")

    def _processUserSeasonTransitions(self) -> None:
        """Apply pending favorite team changes and finalize fantasy scores."""
        from database.connection import get_session
        from database.models import (
            User, FantasyRoster, WeeklyPlayerFP,
        )

        completedSeason = self.currentSeason.seasonNumber if self.currentSeason else None
        if completedSeason is None:
            return
        session = get_session()
        try:
            # Promote pending favorite teams
            pendingUsers = session.query(User).filter(
                User.pending_favorite_team_id.isnot(None)
            ).all()
            from managers.supporterManager import onFavoriteTeamChange
            for u in pendingUsers:
                logger.info(f"User {u.id}: promoting pending favorite team {u.pending_favorite_team_id}")
                # Switching teams — soft-reset Supporter loyalty tenure (anti-bandwagon).
                onFavoriteTeamChange(u)
                u.favorite_team_id = u.pending_favorite_team_id
                u.pending_favorite_team_id = None
                u.favorite_team_locked_season = None

            # Finalize fantasy roster scores. Fusion: the roster IS the equipped
            # cards, so the season base = Σ over weeks of that week's equipped
            # lineup's per-player WeeklyPlayerFP (weekly-sum, no season-lock offset).
            # Card bonuses are tracked separately in card_bonus_points.
            from managers.fantasyTracker import FantasyTracker
            lockedRosters = session.query(FantasyRoster).filter_by(
                season=completedSeason, is_locked=True
            ).all()
            equippedByUserWeek = FantasyTracker._equippedRostersByWeek(session, completedSeason)
            weekFpRows = session.query(
                WeeklyPlayerFP.player_id, WeeklyPlayerFP.week, WeeklyPlayerFP.fantasy_points
            ).filter(WeeklyPlayerFP.season == completedSeason).all()
            weekFpMap = {(pid, wk): fp for pid, wk, fp in weekFpRows}
            for roster in lockedRosters:
                totalPoints = 0.0
                for (uId, wk), lineup in equippedByUserWeek.items():
                    if uId != roster.user_id:
                        continue
                    for _eq, pid in lineup:
                        totalPoints += weekFpMap.get((pid, wk), 0)
                roster.total_points = totalPoints
                logger.info(f"Fantasy roster {roster.id} (user {roster.user_id}): finalized at {totalPoints:.1f} pts")

            # Rosters are NOT carried forward — users start each season fresh
            logger.info(f"Finalized {len(lockedRosters)} fantasy rosters for season {completedSeason}")

            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Error processing user season transitions: {e}")
            import traceback
            logger.debug(traceback.format_exc())
        finally:
            session.close()

    async def _runPreDraftPass(self, teamsWorstFirst: list, gmResults: list) -> None:
        """Roll through teams worst→best BEFORE the rookie draft begins.

        For each team, broadcast a setup event with:
          - resigns: players whose GM re-sign vote succeeded (still rostered)
          - cuts: players who left the roster this offseason (GM vote + contract
            expiration — both set previousTeam and reset freeAgentYears to 0)
          - promotions: prospects moved onto the roster. Promotion is RUN HERE
            (not during the FA draft) so the prospect slot opens up before the
            rookie draft fills it.

        The pass emits offseason_predraft_start, then offseason_team_setup per
        team (plus offseason_on_clock so the UI highlights the current row),
        then offseason_predraft_complete when done.
        """
        if not (BROADCASTING_AVAILABLE and broadcaster):
            # Still run promotions even without broadcasting — they mutate state.
            # (This branch called a method that never existed, so every
            # broadcast-off mode raised AttributeError here.)
            for team in teamsWorstFirst:
                self._promoteProspectsAutonomously(team)
            return

        # Index resign successes by team for O(1) lookup
        resignsByTeam: dict = {}
        # Track which players were released via GM cut vote (vs. contract expiry)
        # so the UI can show CUT (team decision) vs EXPIRED (natural departure).
        gmCutPlayerNames: set = set()
        for r in gmResults or []:
            if r.get('outcome') != 'success':
                continue
            vt = r.get('voteType')
            if vt == 'resign_player':
                tid = r.get('teamId')
                resignsByTeam.setdefault(tid, []).append(r.get('targetPlayerName'))
            elif vt == 'cut_player':
                gmCutPlayerNames.add(r.get('targetPlayerName'))

        # Collect cuts (FAs with previousTeam from this offseason)
        cutsByTeamName: dict = {}
        for p in self.playerManager.freeAgents:
            if getattr(p, 'freeAgentYears', 99) != 0:
                continue
            prev = getattr(p, 'previousTeam', None)
            if not prev:
                continue
            cutsByTeamName.setdefault(prev, []).append(p)

        # Predraft is no longer a visible roll-through — front-office decisions
        # land in one shot. Compute resigns/cuts/promotions per team, persist
        # them, broadcast each team_setup event so subscribed UIs render the
        # data, then fire predraft_complete. No per-team delays, no on_clock
        # highlight (there's no "current team" anymore — they all happen at once).
        self._offseasonPhase = 'predraft'
        try:
            await broadcaster.broadcast_season_event(
                OffseasonEvent.predraft_start(len(teamsWorstFirst))
            )
        except Exception as e:
            logger.warning(f"Could not broadcast predraft start: {e}")

        for team in teamsWorstFirst:
            teamAbbr = getattr(team, 'abbr', team.name[:3].upper())
            teamId = getattr(team, 'id', None)

            # Build resign list — look up player details from the roster
            resignList = []
            resignNames = set(resignsByTeam.get(teamId, []))
            if resignNames:
                for slot, p in team.rosterDict.items():
                    if p and p.name in resignNames:
                        resignList.append({
                            'id': getattr(p, 'id', None),
                            'name': p.name,
                            'position': p.position.name,
                            'rating': round(p.playerRating, 1),
                            'tier': p.playerTier.name,
                        })

            # Build cut list. GM-voted cuts are tagged 'gm_vote'; contract
            # expirations are 'expired' (player walked to FA naturally — not
            # the team's active decision).
            cutList = []
            for p in cutsByTeamName.get(team.name, []):
                reason = 'gm_vote' if p.name in gmCutPlayerNames else 'expired'
                cutList.append({
                    'id': getattr(p, 'id', None),
                    'name': p.name,
                    'position': p.position.name,
                    'rating': round(p.playerRating, 1),
                    'tier': p.playerTier.name,
                    'reason': reason,
                })

            # Promotions used to fire here, but they're now deferred to the
            # FA draft kickoff (see _applyFanVotedPromotions). That gives
            # users time to revise their FA ballots once the cuts/resigns
            # in this pass shake out the FA pool — a player they didn't
            # rank pre-bowl might be available now.
            promotionList: list = []

            try:
                await broadcaster.broadcast_season_event(
                    OffseasonEvent.team_setup(
                        team.name, teamAbbr, teamId,
                        resigns=resignList, cuts=cutList, promotions=promotionList,
                    )
                )
                # Persist for /api/offseason replay on refresh + Front Office
                self._offseasonTransactions.append({
                    'type': 'team_setup',
                    'team': team.name, 'teamAbbr': teamAbbr, 'teamId': teamId,
                    'resigns': resignList, 'cuts': cutList, 'promotions': promotionList,
                })
                # Tiny yield so the frontend's WS layer + React state can land
                # each event individually. Without this, a 32-team burst in the
                # same event-loop tick collapses to a single render and the
                # intermediate setups get lost. ~50ms per team = ~1.6s total —
                # imperceptible, but every event lands.
                await asyncio.sleep(0.05)
            except Exception as e:
                logger.warning(f"Predraft broadcast error for {team.name}: {e}")

        self._offseasonPhase = None
        try:
            await broadcaster.broadcast_season_event(
                OffseasonEvent.predraft_complete()
            )
        except Exception as e:
            logger.warning(f"Could not broadcast predraft complete: {e}")

    async def _applyFanVotedPromotions(self) -> None:
        """Apply fan-voted prospect promotions across all teams at the moment
        the FA draft kicks off.

        Used to happen during the predraft pass (front-office phase), but
        users couldn't revise FA ballots between cuts and the promotion —
        if a cut opened a new option they wanted to rank #1, the promotion
        had already locked in the prospect. Deferring to here means the
        user's *final* ballot drives the promotion decision.

        Each promotion is broadcast as a pick event (isPromotion=True) and
        appended to the offseason transactions log, so the OffseasonPanel +
        Front Office page see them as part of the FA draft phase.
        """
        teamManager = self.serviceContainer.getService('team_manager')
        if not teamManager or not self.currentSeason:
            return
        faOrder = getattr(self.currentSeason, 'freeAgencyOrder', []) or []
        if not faOrder:
            return

        for team in faOrder:
            # The fan ballot that used to drive this is gone with the GM vote
            # system; the front-office brain decides promotions now.
            promotions = self._promoteProspectsAutonomously(team)
            for promo in promotions:
                teamAbbr = getattr(team, 'abbr', team.name[:3].upper())
                entry = {
                    'type': 'pick', 'team': team.name, 'teamAbbr': teamAbbr,
                    'playerId': promo.get('id'),
                    'player': promo['name'], 'position': promo['position'],
                    'rating': promo['rating'], 'tier': promo['tier'],
                    'isPromotion': True,
                    'slot': promo.get('slot'),
                }
                self._offseasonTransactions.append(entry)
                self._recordOffseasonEvent(
                    'promotion', teamName=team.name, teamAbbr=teamAbbr, teamId=getattr(team, 'id', None),
                    playerId=promo.get('id'), playerName=promo['name'], position=promo['position'],
                    rating=promo['rating'], tier=promo['tier'])
                if BROADCASTING_AVAILABLE and broadcaster and broadcaster.is_enabled():
                    try:
                        await broadcaster.broadcast_season_event(
                            OffseasonEvent.pick(
                                team.name, teamAbbr,
                                promo['name'], promo['position'],
                                promo['rating'], promo['tier'],
                                isPromotion=True,
                                playerId=promo.get('id'),
                                slot=promo.get('slot'),
                            )
                        )
                        # Same 100ms breath as FA picks — keeps each
                        # promotion as its own React render tick.
                        await asyncio.sleep(0.1)
                    except Exception as e:
                        logger.warning(f"Could not broadcast promotion for {team.name}: {e}")

    def _foBrainForOffseason(self):
        """Build (and cache for this offseason) the front-office decider.

        Cached because the sentiment map is a whole-league fetch and several
        offseason steps want the same brain; rebuilt each offseason so a
        season's worth of new fan ratings is picked up.
        """
        season = getattr(self.currentSeason, 'seasonNumber', None)
        cached = getattr(self, '_foBrainCache', None)
        if cached and cached[0] == season:
            return cached[1]
        from managers.frontOfficeBrain import FrontOfficeBrain
        sentimentMap = {}
        try:
            from constants import SENTIMENT_ENABLED
            if SENTIMENT_ENABLED:
                from database.connection import get_session
                from database.repositories.sentiment_repository import buildSentimentMap
                sentimentMap = buildSentimentMap(get_session())
        except Exception as e:
            logger.warning(f"GM brain: sentiment unavailable, running neutral: {e}")
        brain = FrontOfficeBrain(self.playerManager, sentimentMap=sentimentMap)
        self._foBrainCache = (season, brain)
        return brain

    def _buildFaDraftBoards(self) -> None:
        """Give every team its own ranking of the free agents who'd sign there.

        Two teams do NOT see the same board. The order is each GM's
        `decisionValue`, which is scouting-gated (and now sharpened by the
        Scouting Department), so one club's top target is another's fifth
        choice. Players who wouldn't sign for a club are simply absent from its
        board.

        Built ONCE, here, before a pick is made:
          - the scouting error is drawn once, so a team's board can't reshuffle
            underneath it between rounds
          - destination preference is settled before any GM plans around it
        """
        from constants import AUTONOMOUS_FO_ENABLED
        boards = {}
        if not AUTONOMOUS_FO_ENABLED:
            self.playerManager._faDraftBoards = boards
            return
        teamManager = self.serviceContainer.getService('team_manager')
        teams = teamManager.teams if teamManager else []
        pool = list(getattr(self.playerManager, 'freeAgents', None) or [])
        if not teams or not pool:
            self.playerManager._faDraftBoards = boards
            return
        brain = self._foBrainForOffseason()
        for team in teams:
            try:
                boards[team.id] = brain.buildDraftBoard(
                    team, pool, coach=getattr(team, 'coach', None),
                    alsoValue=list(getattr(team, 'prospects', None) or []),
                )
            except Exception as e:
                # A team with no board falls back to true-rating order, which is
                # the pre-existing behaviour — never a missing pick.
                logger.warning(f"FA board build failed for {getattr(team, 'name', '?')}: {e}")
        self.playerManager._faDraftBoards = boards

        # One line per draft so a surprising pick can be traced back to the
        # board that produced it.
        try:
            sizes = [len(b) for b in boards.values()]
            if sizes:
                logger.info(
                    f"FA boards: {len(boards)} teams, pool {len(pool)}, "
                    f"signable per team min {min(sizes)} / avg {sum(sizes)//len(sizes)} / max {max(sizes)}"
                )
        except Exception:
            pass

    def _promoteProspectsAutonomously(self, team) -> list:
        """Promote this team's prospects when the GM rates them over the market.

        The prospect pipeline is CLOSED (ROOKIE_DRAFT_ENABLED False) but teams
        deployed into that change still own prospects, and those have to keep
        being able to make the roster — otherwise every one of them sits out its
        development window and washes out to free agency, which reads to a fan
        as the team losing its prospects the day the change landed.

        Promotion used to be fan-directed off the GM sign_fa ballot. With the
        autonomous front office there is no ballot, so the same decider that
        handles re-signs and cuts values the prospect against the free agent
        this team could realistically land at its own slot in the FA order.
        Returns promotion dicts in the shape the broadcast/log path expects.
        """
        prospects = list(getattr(team, 'prospects', []) or [])
        if not prospects:
            return []
        from constants import FO_PROSPECT_PROMOTE_EDGE
        brain = self._foBrainForOffseason()
        coach = getattr(team, 'coach', None)
        faOrder = getattr(self.currentSeason, 'freeAgencyOrder', None) or None
        pickDepth = brain.faPickDepth(team, faOrder)

        promotions: list = []
        # Loop: a promotion fills one slot, but a second prospect may fit a
        # different one, so re-evaluate until nothing more clears the bar.
        while True:
            best, bestSlot, bestValue = None, None, 0.0
            for prospect in prospects:
                try:
                    slot = self.playerManager._findOpenSlotForPosition(
                        team, prospect.position.value)
                except Exception:
                    slot = None
                if not slot:
                    continue        # no hole at his position — nothing to win
                value = brain.decisionValue(prospect, coach=coach)
                replacement = brain.bestReplacementValue(
                    prospect, coach=coach, pickDepth=pickDepth)
                if value < replacement * FO_PROSPECT_PROMOTE_EDGE:
                    continue        # free agency offers better — leave him down
                if value > bestValue:
                    best, bestSlot, bestValue = prospect, slot, value
            if best is None:
                break

            best.is_prospect = False
            best.prospect_seasons = 0
            best.drafting_team_id = None
            best.team = team
            team.rosterDict[bestSlot] = best
            if best in team.prospects:
                team.prospects.remove(best)
            prospects.remove(best)
            try:
                best.term = self.playerManager._getPlayerTerm(best)
                best.termRemaining = best.term
            except Exception:
                best.termRemaining = 1
            promotions.append({
                'id': getattr(best, 'id', None),
                'name': best.name,
                'position': best.position.name,
                'rating': round(best.playerRating, 1),
                'tier': best.playerTier.name,
                'slot': bestSlot,
            })
            logger.info(f"Promotion {team.name}: {best.name} "
                        f"({best.position.name}) -> {bestSlot}")
        return promotions


    async def _processFreeAgency(self) -> None:
        """Process free agency with live per-pick broadcasting.

        Instead of running the full simulation synchronously and replaying
        events, this iterates a generator that yields one event at a time.
        Each pick mutates rosters in-place before being broadcast, so REST
        endpoints always return accurate data — no snapshot system needed.
        """
        logger.info("Processing free agency")

        if not self.currentSeason or not hasattr(self.currentSeason, 'freeAgencyOrder'):
            logger.error("No free agency order available (playoffs must be completed first)")
            return

        # Rookie draft uses the worst-first freeAgencyOrder from playoffs (rebuild
        # path). FA draft, however, gives MEGA-market teams priority so funding
        # Reuse the tier-sorted draft order computed during pre_fa preview,
        # so picks fire against the same order users saw during the wait.
        # Fallback to rookie order if preview wasn't computed (e.g., offline
        # mode). The fa_draft_order_update event was also broadcast during
        # the preview — don't re-fire it here.
        freeAgencyOrder = getattr(self, '_pendingFaDraftOrder', None)
        if not freeAgencyOrder:
            freeAgencyOrder = self.currentSeason.freeAgencyOrder
        orderSummary = [getattr(t, 'abbr', t.name[:3]) for t in freeAgencyOrder]
        logger.info(f"FA draft order (from preview): {' → '.join(orderSummary)}")
        leagueHighlights = []
        if self.currentSeason and hasattr(self.currentSeason, 'leagueHighlights'):
            leagueHighlights = self.currentSeason.leagueHighlights

        # Mark the panel sub-phase so the OffseasonPanel renders FA grouping.
        self._offseasonPhase = 'free_agency'

        # Live pick-by-pick iteration. Do NOT clear _offseasonTransactions
        # here — the rookie draft already appended its picks/skips to the
        # list and we want them to survive into the FA phase so a mid-FA
        # refresh still shows the full offseason history. The single wipe
        # at the start of _handleOffseason covers the between-season reset.
        currentSeasonNum = self.currentSeason.seasonNumber if hasattr(self, 'currentSeasonNumber') else 1

        pickGen = self.playerManager.freeAgencyPickGenerator(
            freeAgencyOrder=freeAgencyOrder,
            currentSeason=currentSeasonNum,
            leagueHighlights=leagueHighlights,
            skipRetirements=True,
        )

        if BROADCASTING_AVAILABLE and broadcaster:
            try:
                for entry in pickGen:
                    if entry['type'] == 'on_clock':
                        await broadcaster.broadcast_season_event(
                            OffseasonEvent.on_clock(entry['team'], entry['teamAbbr'])
                        )
                        await self.timingManager.waitBetweenOffseasonPicks()
                    elif entry['type'] == 'pick':
                        await broadcaster.broadcast_season_event(
                            OffseasonEvent.pick(
                                entry['team'], entry['teamAbbr'],
                                entry['player'], entry['position'],
                                entry['rating'], entry['tier'],
                                isPromotion=entry.get('isPromotion', False),
                                playerId=entry.get('playerId'),
                                slot=entry.get('slot'),
                            )
                        )
                        self._offseasonTransactions.append(entry)
                        self._recordOffseasonEvent(
                            'promotion' if entry.get('isPromotion') else 'fa_pick',
                            teamName=entry['team'], teamAbbr=entry['teamAbbr'],
                            playerId=entry.get('playerId'), playerName=entry['player'],
                            position=entry['position'], rating=entry['rating'], tier=entry['tier'])
                        # Small yield so the pick lands as its own React render
                        # tick before the next team's on_clock fires. Without
                        # this, pick → on_clock can collapse into one update
                        # and the pick visually disappears (or worse, attaches
                        # to the wrong team in the UI). Imperceptible to users.
                        await asyncio.sleep(0.1)
                    elif entry['type'] == 'team_complete':
                        await broadcaster.broadcast_season_event(
                            OffseasonEvent.team_complete(entry['team'], entry['teamAbbr'])
                        )
                        await asyncio.sleep(0.05)
                self._offseasonPhase = None
                await broadcaster.broadcast_season_event(
                    OffseasonEvent.complete(len(self.playerManager.freeAgents))
                )
            except Exception as e:
                logger.warning(f"Could not broadcast offseason events: {e}")
                # Drain remaining generator events so simulation completes
                for _ in pickGen:
                    pass
        else:
            # No broadcaster — just drain the generator to run the simulation
            for _ in pickGen:
                pass

        logger.info("Free agency complete")
    
    def _recordOffseasonEvent(self, eventType, *, player=None, team=None, detail=None,
                              teamId=None, teamAbbr=None, teamName=None,
                              playerId=None, playerName=None, position=None,
                              rating=None, tier=None, session=None) -> None:
        """Persist one offseason transaction/announcement for the Season Recap.
        Best-effort + idempotent per (season, eventType, playerId|teamId) so an
        offseason resume/restart never duplicates or breaks the offseason.
        Pass `player`/`team` objects to auto-extract fields. Pass `session` to
        write on an existing open transaction (the caller commits) instead of
        opening a new one — opening a second SQLite session inside another open
        write (e.g. HoF induction) self-deadlocks on the single-writer lock and
        stalls the whole sim task for the 30s busy_timeout."""
        try:
            season = self.currentSeason.seasonNumber if self.currentSeason else 0
            if not season:
                return
            if team is not None:
                teamId = getattr(team, 'id', teamId)
                tn = getattr(team, 'name', None)
                teamName = tn or teamName
                teamAbbr = getattr(team, 'abbr', None) or (tn[:3].upper() if tn else teamAbbr)
            if player is not None:
                playerId = getattr(player, 'id', playerId)
                playerName = getattr(player, 'name', playerName)
                pos = getattr(player, 'position', None)
                position = position or (pos.name if pos is not None and hasattr(pos, 'name') else position)
                if rating is None:
                    rating = getattr(player, 'playerRating', None)
                t = getattr(player, 'playerTier', None)
                tier = tier or (t.name if t is not None and hasattr(t, 'name') else tier)
            from database.connection import get_session
            from database.models import SeasonRecapEvent
            ownSession = session is None
            s = get_session() if ownSession else session
            try:
                q = s.query(SeasonRecapEvent).filter_by(season=season, event_type=eventType)
                q = q.filter_by(player_id=playerId) if playerId is not None else q.filter_by(team_id=teamId)
                if q.first():
                    return  # already recorded (resume/restart safety)
                s.add(SeasonRecapEvent(
                    season=season, event_type=eventType, team_id=teamId, team_abbr=teamAbbr,
                    team_name=teamName, player_id=playerId, player_name=playerName,
                    position=position, rating=rating, tier=tier, detail=detail,
                ))
                if ownSession:
                    s.commit()
                else:
                    s.flush()  # caller's transaction commits — no nested session
            finally:
                if ownSession:
                    s.close()
        except Exception as e:
            logger.warning(f"recap event record failed ({eventType}): {e}")

    def _clearRecapEvents(self, season: int) -> None:
        """Wipe a season's recap event log (called on FRESH offseason entry so a
        rebuild starts clean; skipped on resume)."""
        try:
            from database.connection import get_session
            from database.models import SeasonRecapEvent
            s = get_session()
            try:
                s.query(SeasonRecapEvent).filter_by(season=season).delete()
                s.commit()
            finally:
                s.close()
        except Exception as e:
            logger.warning(f"clear recap events failed: {e}")

    def _applyRetentionLimits(self) -> None:
        """Per team, decide which EXPIRING players (contract up this offseason) get
        RE-SIGNED vs walk to FA. FAN-DRIVEN — a player is only kept if fans voted to
        re-sign them (`_gmResigned`, set by the resign vote in STEP 2). There is NO
        auto-keep: with no vote, a player walks (fans may deliberately let players
        go, or simply not vote; unmanaged teams circulate their talent faster). Two
        limits apply on top:
          - RE-SIGN-ONCE: a player already re-signed the limit number of times by
            this team is FORCED to walk even if fans voted to keep them.
          - COUNT LIMIT: at most RESIGN_LIMIT_PER_OFFSEASON re-signs per offseason;
            if fans voted for more, only the most-voted keep (rest walk).
        Kept players stay flagged `_gmResigned` (STEP 3 renews them + increments the
        re-sign count); the rest are cleared and walk. See PARITY_PROSPECT_PLAN.md P5."""
        from constants import (RESIGN_ONCE_ENABLED, RESIGN_ONCE_LIMIT,
                               RESIGN_LIMIT_ENABLED, RESIGN_LIMIT_PER_OFFSEASON,
                               AUTONOMOUS_FO_ENABLED)
        if not (RESIGN_ONCE_ENABLED or RESIGN_LIMIT_ENABLED):
            return
        # AUTONOMOUS FRONT OFFICE: when enabled, the GM brain picks the keepers
        # instead of the fans. The guardrails below (re-sign-once, per-offseason
        # count) are unchanged either way — only the DECIDER swaps. Env override
        # lets a sim harness exercise the brain without flipping the constant.
        brain = None
        faOrder = None
        if AUTONOMOUS_FO_ENABLED or os.environ.get('AUTONOMOUS_FO'):
            from managers.frontOfficeBrain import FrontOfficeBrain
            # Fan sentiment (plan Part D), fetched ONCE for the whole league —
            # the sweep values every roster on every team, so per-player lookups
            # would be an N+1 here. Absent players read neutral, so a league
            # with no ratings at all behaves exactly as before.
            sentimentMap = {}
            try:
                from constants import SENTIMENT_ENABLED
                if SENTIMENT_ENABLED:
                    from database.connection import get_session
                    from database.repositories.sentiment_repository import buildSentimentMap
                    # Combined signal: the 1-5 standing stance LEADS, the post
                    # pulse nudges. Built in one place so a caller can't read
                    # only half of it.
                    sentimentMap = buildSentimentMap(get_session())
            except Exception as e:
                logger.warning(f"GM brain: sentiment unavailable, running neutral: {e}")
            if sentimentMap:
                logger.info(f"GM brain: {len(sentimentMap)} player(s) carry fan sentiment")
            brain = FrontOfficeBrain(self.playerManager, sentimentMap=sentimentMap)
            # Worst-first FA order (snapshotted at playoffs). A team judges its
            # incumbent against the free agent still likely to be there at ITS
            # slot, so an early picker churns boldly and a late one holds.
            faOrder = getattr(self.currentSeason, 'freeAgencyOrder', None) or None
            if not faOrder:
                logger.warning("GM brain: no FA order available — every team will "
                               "shop the top of the board (churn will read high)")
        teamManager = self.serviceContainer.getService('team_manager')
        if not teamManager:
            return
        # SIM-ONLY: model fan behaviour (re-sign your best eligible players) so a
        # userless sim isn't an all-walk extreme. Prod is unaffected — it's driven
        # by real fan votes. Gated by env; set by retention_harness.py.
        simulateFans = bool(os.environ.get('SIMULATE_FAN_RESIGNS'))
        limit = RESIGN_LIMIT_PER_OFFSEASON if RESIGN_LIMIT_ENABLED else 99

        # ASSESSMENT SWEEP ORDER (plan Part A). With the brain driving, teams
        # are evaluated BEST-FIRST — Floos Bowl champion, then win% descending —
        # and each team's cuts drop into the shared FA pool immediately, so the
        # teams after it assess against the full market. This is decision order
        # ONLY: actual acquisition is still the worst-first FA draft, so there
        # is no anti-parity effect.
        sweepTeams = list(teamManager.teams)
        if brain is not None:
            def _sweepKey(t):
                stats = getattr(t, 'seasonTeamStats', None) or {}
                champ = 1 if stats.get('floosbowlChamp') else 0
                wins = float(stats.get('wins', 0) or 0)
                losses = float(stats.get('losses', 0) or 0)
                played = wins + losses
                winPct = (wins / played) if played else 0.0
                return (-champ, -winPct, getattr(t, 'name', ''))
            sweepTeams.sort(key=_sweepKey)
            logger.info("GM brain assessment sweep (best-first): "
                        + ", ".join(getattr(t, 'name', '?') for t in sweepTeams[:5]) + " ...")
            # Position-keyed lists releasePlayerToFreeAgency maintains alongside
            # playerManager.freeAgents.
            faLists = {
                'qb': [p for p in self.playerManager.freeAgents if p.position.value == 1],
                'rb': [p for p in self.playerManager.freeAgents if p.position.value == 2],
                'wr': [p for p in self.playerManager.freeAgents if p.position.value == 3],
                'te': [p for p in self.playerManager.freeAgents if p.position.value == 4],
                'k':  [p for p in self.playerManager.freeAgents if p.position.value == 5],
            }
            cutTally = 0

        for team in sweepTeams:
            expiring, forcedWalk = [], []
            for p in team.rosterDict.values():
                if p is None or getattr(p, 'willRetire', False):
                    continue  # empty slot, or retires in STEP 3 (vacates)
                if (getattr(p, 'termRemaining', 0) or 0) > 1:
                    continue  # stays on current deal
                if self.playerManager.hasReachedResignLimit(p):
                    forcedWalk.append(p)    # re-sign limit reached — must walk
                else:
                    expiring.append(p)      # contract up → keep only if voted
            if brain is not None:
                # GM BRAIN decides. A slot is spent only where the incumbent
                # beats the best replacement available at his position, so a
                # good player the market can replace is allowed to walk while a
                # modest one with nothing behind him is kept.
                pickDepth = brain.faPickDepth(team, faOrder)
                kept = brain.chooseResigns(expiring, limit,
                                           coach=getattr(team, 'coach', None),
                                           pickDepth=pickDepth)
                keptIds = {id(p) for p in kept}
                for p in expiring:
                    p._gmResigned = id(p) in keptIds
                for p in forcedWalk:
                    p._gmResigned = False        # re-sign-once override still wins
                logger.info(f"Retention {team.name} (GM brain): re-signed {len(kept)}, "
                            f"forced-walk {len(forcedWalk)}, walked {len(expiring) - len(kept)} "
                            f"(faDepth {pickDepth})")
                if os.environ.get('RETENTION_DEBUG'):
                    def _fmtb(pl): return f"{pl.name}({getattr(pl,'playerRating',0)}/{brain.classifyArc(pl)})"
                    logger.info(
                        f"  RESIGN[{team.name}] kept: {', '.join(_fmtb(p) for p in kept) or '-'} | "
                        f"walked: {', '.join(_fmtb(p) for p in expiring if id(p) not in keptIds) or '-'}")

                # CUT-FOR-UPGRADE. Released LIVE so the teams later in the sweep
                # assess against the fuller market this one just created.
                cuts = brain.chooseCuts(team, coach=getattr(team, 'coach', None),
                                        pickDepth=pickDepth)
                for player, slot in cuts:
                    self.playerManager.releasePlayerToFreeAgency(player, team, faLists)
                    cutTally += 1
                    self._recordOffseasonEvent(
                        'cut', team=team, player=player, detail='GM upgrade cut')
                if cuts:
                    logger.info(f"  CUT[{team.name}] " + ", ".join(
                        f"{p.name}({getattr(p, 'playerRating', 0)})" for p, _s in cuts))
                continue

            if simulateFans:
                # Stand in for fan resign votes: keep the best `limit` eligible.
                for p in sorted(expiring, key=lambda x: -(getattr(x, 'playerRating', 0) or 0))[:limit]:
                    p._gmResigned = True
            # Keep only players fans voted to re-sign (real votes, or the sim's
            # stand-in above), capped at the count limit. Tiebreak on net votes so
            # the most-supported stay; fall back to rating for the sim stand-in
            # (no real vote tallies) and any legacy flag without a stored count.
            def _resignRank(p):
                nv = getattr(p, '_gmResignNetVotes', None)
                return nv if nv is not None else (getattr(p, 'playerRating', 0) or 0)
            voted = sorted((p for p in expiring if getattr(p, '_gmResigned', False)),
                           key=lambda x: -_resignRank(x))
            kept = voted[:limit]
            keptIds = {id(p) for p in kept}
            for p in expiring:
                p._gmResigned = id(p) in keptIds     # NO auto-keep: unvoted -> walk
            for p in forcedWalk:
                p._gmResigned = False                # re-sign-once override
            logger.info(f"Retention {team.name}: re-signed {len(kept)}, forced-walk {len(forcedWalk)}, "
                        f"walked {len(expiring) - len(kept)}")
            # RETENTION_DEBUG: show the actual decision — which players were
            # re-signed (most-voted, capped at the limit) and who walked and why.
            # Off by default; a harness sets the env var to surface the logic.
            if os.environ.get('RETENTION_DEBUG'):
                def _fmt(pl): return f"{pl.name}({getattr(pl,'playerRating',0)})"
                keptStr = ", ".join(_fmt(p) for p in kept) or "-"
                walked = [p for p in expiring if id(p) not in keptIds]
                logger.info(
                    f"  RESIGN[{team.name}] kept: {keptStr} | "
                    f"walk(not-resigned): {', '.join(_fmt(p) for p in walked) or '-'} | "
                    f"walk(re-sign-limit): {', '.join(_fmt(p) for p in forcedWalk) or '-'}")

        if brain is not None:
            logger.info(f"GM brain sweep complete: {cutTally} upgrade cut(s) league-wide")

    async def _processRosteredPlayerContracts(self) -> None:
        """Process contract decrements and retirements for players on team rosters"""
        from random import randint

        teamManager = self.serviceContainer.getService('team_manager')
        if not teamManager:
            return
        
        leagueHighlights = []
        if self.currentSeason and hasattr(self.currentSeason, 'leagueHighlights'):
            leagueHighlights = self.currentSeason.leagueHighlights
        
        for team in teamManager.teams:
            for position, player in list(team.rosterDict.items()):
                if player is None:
                    continue
                
                # Note: seasonsPlayed and serviceTime are updated in _handlePlayerSeasonProgression
                # for ALL active players (rostered + FA). Don't increment here.

                # Decrement contract term
                player.termRemaining -= 1

                # Retirement is contract-end-only and pre-decided during the
                # regular season (see _evaluateRetirementCandidates). The flag
                # is only set on players whose contract expires this offseason,
                # so users see retirements coming and can vote on replacements.
                shouldRetire = bool(getattr(player, 'willRetire', False))

                if shouldRetire:
                    # Player retires (overrides re-sign)
                    self._executePlayerRetirement(player, team, position, leagueHighlights)
                elif getattr(player, '_gmResigned', False):
                    # Re-signed (fan vote or retention-limit keep) — renew contract
                    # and bump the re-sign count (re-sign-once forces a walk once the
                    # count hits RESIGN_ONCE_LIMIT).
                    player.term = self.playerManager._getPlayerTerm(player)
                    player.termRemaining = player.term
                    player.teamResignCount = int(getattr(player, 'teamResignCount', 0) or 0) + 1
                    player._gmResigned = False
                    leagueHighlights.insert(0, {
                        'event': {'text': f'{player.name} re-signed with {team.name} for {player.term} season(s) (GM vote)'}
                    })
                    logger.info(f"GM re-sign: {player.name} renewed with {team.name} for {player.term} seasons")
                    self._recordOffseasonEvent('resign', player=player, team=team,
                                               detail=f"{player.term} season(s)")
                elif player.termRemaining <= 0:
                    # Contract expired - move to free agency
                    player.previousTeam = team.name
                    player.teamResignCount = 0   # tenure ended; next team starts fresh
                    if player.currentNumber in team.playerNumbersList:
                        team.playerNumbersList.remove(player.currentNumber)
                    player.team = 'Free Agent'
                    player.freeAgentYears = 0
                    # Only add to free agents if not already there (defensive check)
                    if player not in self.playerManager.freeAgents:
                        self.playerManager.freeAgents.append(player)
                    self._recordOffseasonEvent('walked', player=player,
                                               teamId=team.id, teamAbbr=getattr(team, 'abbr', None),
                                               teamName=team.name)
                    team.rosterDict[position] = None

                    leagueHighlights.insert(0, {
                        'event': {'text': f'{player.name} has become a Free Agent'}
                    })

    def _validateRosterIntegrity(self) -> None:
        """Fix player-team reference mismatches after FA draft.

        Ensures every rostered player's .team points at the correct team object
        and that self.freeAgents does not contain any rostered players.
        """
        teamManager = self.serviceContainer.getService('team_manager')
        if not teamManager:
            return

        # Build lookup: playerId → team for all rostered players
        rosteredLookup: dict = {}
        for team in teamManager.teams:
            for pos, player in team.rosterDict.items():
                if player is not None:
                    rosteredLookup[player.id] = team

        fixes = 0
        # Fix rostered players whose .team is wrong
        for playerId, team in rosteredLookup.items():
            for pos, player in team.rosterDict.items():
                if player is not None and player.id == playerId:
                    if not hasattr(player.team, 'id') or getattr(player.team, 'id', None) != team.id:
                        logger.warning(f"Roster integrity fix: {player.name} on {team.name} had team='{player.team}', correcting")
                        player.team = team
                        fixes += 1
                    break

        # Remove rostered players from freeAgents list
        faRemovals = 0
        cleanFa = [p for p in self.playerManager.freeAgents if p.id not in rosteredLookup]
        faRemovals = len(self.playerManager.freeAgents) - len(cleanFa)
        if faRemovals > 0:
            self.playerManager.freeAgents[:] = cleanFa

        if fixes or faRemovals:
            logger.info(f"Roster integrity: fixed {fixes} team refs, removed {faRemovals} rostered players from FA list")

    def _evaluateRetirementCandidates(self) -> list:
        """Decide which players will retire after this season.

        Runs late in the regular season so users see retirements coming and
        can plan replacements via FA ballots. Eligibility + probability come
        from playerManager.computeRetirementOdds (shared with the displayed
        risk tier so they never drift): bands key off yearsPast = seasonsPlayed
        - longevity, gated to walk seasons until a player is well past longevity,
        at which point they retire mid-contract too.
        Returns the list of players newly flagged as retiring.
        """
        from random import randint

        teamManager = self.serviceContainer.getService('team_manager')
        if not teamManager:
            return []

        flagged = []
        for team in teamManager.teams:
            for player in team.rosterDict.values():
                if player is None:
                    continue
                if getattr(player, 'willRetire', False):
                    continue

                chancePct, eligible, _yearsPast = self.playerManager.computeRetirementOdds(player)
                if not eligible:
                    continue
                if randint(1, 100) <= chancePct:
                    player.willRetire = True
                    flagged.append((player, team))

        if flagged:
            leagueHighlights = []
            if self.currentSeason and hasattr(self.currentSeason, 'leagueHighlights'):
                leagueHighlights = self.currentSeason.leagueHighlights
            for player, team in flagged:
                leagueHighlights.insert(0, {
                    'event': {'text': f'{player.name} ({team.name}) has announced retirement at the end of the season'}
                })
                logger.info(f"Retirement announced: {player.name} ({team.name}) — {player.seasonsPlayed} seasons")

        return flagged

    def _seedHofBallot(self) -> None:
        """Seed the rolling Hall of Fame ballot with this season's retirees,
        pre-filtered by HoF points. Opens HoF voting for the wk22 -> offseason-
        induction window. Best-effort: a failure here must never block the week-22
        transition.

        Covers BOTH retirement paths. Rostered players are flagged `willRetire`;
        FREE AGENTS retire on a separate path (`_processFreeAgentRetirements`)
        that removes them rather than flagging them, so a roster-only sweep could
        never see them. That gap meant a free agent could not be voted on at all —
        while still being eligible for the points safety net, so for three seasons
        running the only players actually inducted were ones nobody could vote for
        (Billy Bloom S14, Shaggy Porcelain S15, Tennis O'Diaz S16, all with
        free_agent_years=2 and no ballot entry). The points pre-filter still
        applies, so this widens WHO is eligible, not how many get through.
        """
        try:
            from database.connection import get_session
            from managers.awardsManager import AwardsManager
            teamManager = self.serviceContainer.getService('team_manager')
            if not teamManager:
                return
            retirees = [p for team in teamManager.teams
                        for p in team.rosterDict.values()
                        if p is not None and getattr(p, 'willRetire', False)]
            # Free agents retiring this cycle — the half the roster sweep misses.
            try:
                freeAgents = getattr(self.playerManager, 'freeAgents', None) or []
                retirees += [p for p in freeAgents
                             if p is not None and getattr(p, 'willRetire', False)]
            except Exception as _faErr:
                logger.warning(f"HoF ballot: free-agent sweep failed: {_faErr}")
            if not retirees:
                return
            season = self.currentSeason.seasonNumber if self.currentSeason else 0
            session = get_session()
            try:
                am = AwardsManager(session, self.playerManager, lowQuorum=self._isTestMode)
                seeded = am.seedHofBallot(season, retirees)
                session.commit()
                logger.info(f"HoF ballot opened: {len(seeded)} candidate(s) seeded for S{season}")
            finally:
                session.close()
        except Exception as e:
            logger.error(f"HoF ballot seeding failed (non-fatal): {e}")

    def _ensurePositionSupply(self, reason: str = '') -> dict:
        """Guarantee enough living players at each position to fill all roster
        slots (see playerManager.ensurePositionSupply). No-op unless a position
        is genuinely short. Surfaces a league-news note when it has to generate."""
        teamManager = self.serviceContainer.getService('team_manager')
        numTeams = len(teamManager.teams) if teamManager else 24
        try:
            generated = self.playerManager.ensurePositionSupply(numTeams)
        except Exception as e:
            logger.error(f"ensurePositionSupply failed ({reason}): {e}")
            return {}
        if generated:
            total = sum(generated.values())
            detail = ', '.join(f'{n} {pos}' for pos, n in generated.items())
            logger.info(f"Position supply top-up ({reason}): +{total} FAs — {detail}")
            if self.currentSeason and hasattr(self.currentSeason, 'leagueHighlights'):
                self.currentSeason.leagueHighlights.insert(0, {
                    'event': {'text': f'{total} free agent(s) entered the pool to cover thin positions ({detail})'}
                })
        return generated

    def _executePlayerRetirement(self, player, team, position, leagueHighlights):
        """Execute the retirement of a player from a team roster"""
        self._recordOffseasonEvent('retirement', player=player, team=team,
                                   detail=f"{getattr(player, 'seasonsPlayed', 0)} seasons")
        player.previousTeam = team.name
        player.seasonPerformanceRating = 0
        # TODO: capHit feature not fully developed - disabled for now
        # team.playerCap -= getattr(player, 'capHit', 0)
        if player.currentNumber in team.playerNumbersList:
            team.playerNumbersList.remove(player.currentNumber)
        player.team = 'Retired'
        player.serviceTime = FloosPlayer.PlayerServiceTime.Retired
        # The retirement decision has now been carried out — clear the flag so a
        # retired player never carries a stale willRetire (it's set at wk22 and
        # otherwise never reset).
        player.willRetire = False

        self.playerManager.retiredPlayers.append(player)
        self.playerManager.newlyRetiredPlayers.append(player)
        if player in self.playerManager.activePlayers:
            self.playerManager.activePlayers.remove(player)
        if player in self.playerManager.freeAgents:
            self.playerManager.freeAgents.remove(player)
        self.playerManager.removeFromPositionList(player)
        
        team.rosterDict[position] = None
        
        leagueHighlights.insert(0, {
            'event': {'text': f'{player.name} has retired after {player.seasonsPlayed} seasons'}
        })
        
        # Add name variant back to unused names for legacy naming
        self._recyclePlayerName(player.name)
    
    def _recyclePlayerName(self, name: str) -> None:
        """Convert retired player name to legacy variant and add to unused names"""
        # Name progression: Base -> Jr. -> III -> IV -> V -> VI -> VII -> VIII -> IX -> X -> XI
        if name.endswith('Jr.'):
            name = name.replace('Jr.', 'III')
        elif name.endswith('IV'):
            name = name.replace('IV', 'V')
        elif name.endswith('VIII'):
            name = name.replace('VIII', 'IX')
        elif name.endswith('IX'):
            name = name.replace('IX', 'X')
        elif name.endswith('III'):
            name = name.replace('III', 'IV')
        elif name.endswith('V') or name.endswith('X'):
            name += 'I'
        else:
            name += ' Jr.'

        # Hold the recycled variant out of the usable pool for a few seasons so a
        # familiar name doesn't reappear the very next season.
        from constants import NAME_REUSE_DELAY_SEASONS
        currentSeasonNum = getattr(self.currentSeason, 'seasonNumber', 0) or 0
        self.playerManager.addPendingName(name, currentSeasonNum + NAME_REUSE_DELAY_SEASONS)
    
    # app_setting key holding the last season whose Front Office open block ran.
    FRONT_OFFICE_MARKER_KEY = 'front_office_open_season'

    def _frontOfficeProcessed(self) -> bool:
        """Has the week-GM_ACTIVE_WEEK Front Office open already run this season?

        This gate is what stops a restart or deploy at/after week 22 re-running the
        block and RE-ROLLING retirements (_evaluateRetirementCandidates re-rolls every
        not-yet-flagged player, so a second run inflates the retiring set).

        Keyed off its own app_setting. It used to key off the per-team fan-count
        snapshot written at the end of the same block — a side effect standing in for
        a marker. That snapshot existed to freeze GM vote thresholds, and binding fan
        votes are gone, so the snapshot went with them; the marker had to stop riding
        on it first. The legacy column is still honoured as a fallback so a prod DB
        that already ran week 22 this season under the old scheme isn't re-processed
        on the deploy that ships this.
        """
        if not (DB_IMPORTS_AVAILABLE and USE_DATABASE) or not self.currentSeason:
            return False
        season = self.currentSeason.seasonNumber
        try:
            from game_rules import _readAppSetting
            stored = _readAppSetting(self.FRONT_OFFICE_MARKER_KEY)
            if stored is not None and int(stored) >= int(season):
                return True
        except Exception:
            pass
        # Legacy fallback: the old marker was the fan-count snapshot on the season row.
        try:
            from database.connection import get_session as _getSession
            from database.models import Season as DBSeason
            session = _getSession()
            try:
                row = session.get(DBSeason, season)
                return bool(row and row.front_office_fan_snapshot)
            finally:
                session.close()
        except Exception:
            return False

    def _markFrontOfficeProcessed(self) -> None:
        """Stamp this season's Front Office open as done (see _frontOfficeProcessed).
        Must be the LAST step of the open block — everything before it is what the
        marker is protecting from a second run."""
        if not self.currentSeason:
            return
        try:
            from game_rules import _writeAppSetting
            _writeAppSetting(self.FRONT_OFFICE_MARKER_KEY,
                             str(self.currentSeason.seasonNumber))
        except Exception as e:
            logger.error(
                f"Could not stamp the Front Office marker for season "
                f"{self.currentSeason.seasonNumber}: {e}. A restart before week's end "
                f"would re-run the open block and re-roll retirements."
            )

    async def _openFaVotingWindowMidSeason(self) -> None:
        """Open the FA voting window mid-season when the Front Office activates.

        Idempotent: skips if already open. Called by the regular-season loop
        when currentWeek hits GM_ACTIVE_WEEK so fans can start ranking
        projected FAs (walk-year rostered players + existing FAs) well before
        the offseason cliff.
        """
        if getattr(self, '_faWindowOpen', False):
            return
        self._faWindowOpen = True
        self._faWindowEnd = None  # no fixed end — closes at offseason step 5

        if BROADCASTING_AVAILABLE and broadcaster:
            try:
                # Projected pool = current FAs (they're already candidates) +
                # rostered players in their walk year (termRemaining <= 1) who
                # are likely to be FA at season end
                from api.event_models import GmEvent
                faPool = [
                    {"id": p.id, "name": p.name, "position": p.position.name,
                     "rating": round(p.playerRating, 1), "tier": p.playerTier.name,
                     "projected": False}
                    for p in self.playerManager.freeAgents
                ]
                # Rostered walk-year projection
                teamManager = self.serviceContainer.getService('team_manager')
                if teamManager:
                    for team in teamManager.teams:
                        for pos, player in team.rosterDict.items():
                            if player is None:
                                continue
                            if getattr(player, 'termRemaining', 99) <= 1:
                                faPool.append({
                                    "id": player.id, "name": player.name,
                                    "position": player.position.name,
                                    "rating": round(player.playerRating, 1),
                                    "tier": player.playerTier.name,
                                    "projected": True,
                                })
                await broadcaster.broadcast_season_event(
                    GmEvent.faWindowOpen(
                        self.currentSeason.seasonNumber if self.currentSeason else 0,
                        faPool, 0  # duration 0 = no countdown timer; closes at offseason
                    )
                )
            except Exception as e:
                logger.warning(f"Could not broadcast FA window open (mid-season): {e}")
        logger.info("FA voting window opened mid-season — stays open through end of regular season")

    async def _broadcastFaDraftPreview(self) -> None:
        """Compute the tier-sorted FA draft order + current FA pool and
        broadcast them so the OffseasonPanel renders the team board as a single
        Appeal-ranked list and the FA pool list during the pre-FA wait.

        Stores the order on `self._pendingFaDraftOrder` so `_processFreeAgency`
        reuses it instead of recomputing — guarantees the order users saw
        during the wait is the order picks actually fire against.
        """
        if not self.currentSeason:
            return

        # FA draft order = WORST-FIRST (reverse standings), matching the rookie
        # draft — the weakest teams pick free agents first. This REPLACES the old
        # appeal-first order, which was a rich-get-richer loop (fund → appeal →
        # first pick → consolidate skill). `freeAgencyOrder` is already seeded
        # worst-first (non-playoff teams by ascending win%, then playoff teams,
        # champion last), so it IS the order. Combined with re-sign-once shedding
        # stacked cores into this pool, this is the parity engine. Appeal now only
        # affects fan-facing rewards, not FA position. See PARITY_PROSPECT_PLAN.md P5.
        from managers import facilitiesManager  # (still used for the display payload)
        freeAgencyOrder = list(self.currentSeason.freeAgencyOrder)
        self._pendingFaDraftOrder = freeAgencyOrder

        if not (BROADCASTING_AVAILABLE and broadcaster and broadcaster.is_enabled()):
            return

        try:
            draftOrderList = [
                {
                    'name': t.name,
                    'city': getattr(t, 'city', ''),
                    'abbr': getattr(t, 'abbr', t.name[:3].upper()),
                    'id': getattr(t, 'id', None),
                    'color': getattr(t, 'color', None),
                    # FA order is worst-first (reverse standings). appeal kept for
                    # reference/legacy display only.
                    'appeal': round(facilitiesManager.computeAppeal(getattr(t, 'facilities', {}) or {}), 1),
                }
                for t in freeAgencyOrder
            ]
            faPool = [
                {'id': p.id, 'name': p.name, 'position': p.position.name,
                 'rating': round(p.playerRating, 1), 'tier': p.playerTier.name}
                for p in sorted(self.playerManager.freeAgents, key=lambda p: -p.playerRating)
                if isinstance(getattr(p, 'team', None), str)
            ]
            await broadcaster.broadcast_season_event(
                OffseasonEvent.fa_draft_order_update(draftOrderList, faPool=faPool)
            )
        except Exception as e:
            logger.warning(f"Could not broadcast FA draft preview: {e}")

    async def _setOffseasonFlow(self, phase: Optional[str], target: Optional[datetime.datetime]) -> None:
        """Set flow phase + target and broadcast a phase-change event so any
        connected client can update its countdown without re-fetching.

        Using this helper everywhere keeps WS state and REST state in sync —
        without it, transitions like frontoffice → pre_fa stay invisible
        until the user manually refreshes the page.

        Also persists phase + target to simulation_state and snapshots the DB
        on each phase transition so a mid-offseason restart can resume rather
        than skip-and-advance.
        """
        previousPhase = self._offseasonFlowPhase
        self._offseasonFlowPhase = phase
        self._offseasonFlowTarget = target
        self._persistOffseasonFlow()
        if phase and phase != previousPhase:
            self._snapshotDbForPhase(phase)
        if BROADCASTING_AVAILABLE and broadcaster and broadcaster.is_enabled():
            try:
                await broadcaster.broadcast_season_event({
                    'event': 'offseason_phase_change',
                    'phase': phase,
                    'targetTime': target.isoformat() + 'Z' if target else None,
                })
            except Exception as e:
                logger.warning(f"Could not broadcast offseason_phase_change: {e}")

    def _persistOffseasonFlow(self) -> None:
        """Write current _offseasonFlowPhase / _offseasonFlowTarget to
        simulation_state. Called from _setOffseasonFlow and from the step
        completion helper so a restart sees the most recent in-memory state.
        """
        try:
            from database.connection import get_session as _gs
            from database.models import SimulationState
            sess = _gs()
            try:
                row = sess.query(SimulationState).filter_by(id=1).first()
                if not row:
                    return
                row.offseason_phase = self._offseasonFlowPhase
                row.offseason_phase_target = self._offseasonFlowTarget
                row.offseason_completed_steps = self._encodeCompletedSteps()
                sess.commit()
            finally:
                sess.close()
        except Exception as e:
            logger.debug(f"Could not persist offseason flow state: {e}")

    def _encodeCompletedSteps(self) -> Optional[str]:
        steps = getattr(self, '_offseasonCompletedSteps', None)
        if not steps:
            return None
        import json
        return json.dumps(sorted(steps))

    def loadOffseasonFlowFromDb(self) -> None:
        """Re-hydrate _offseasonFlowPhase + _offseasonFlowTarget +
        _offseasonCompletedSteps from simulation_state. Called by the resume
        path so a restart picks up exactly where the previous run left off.
        """
        if not (DB_IMPORTS_AVAILABLE and USE_DATABASE):
            return
        try:
            from database.connection import get_session
            from database.models import SimulationState
            import json
            sess = get_session()
            try:
                row = sess.query(SimulationState).filter_by(id=1).first()
                if not row:
                    return
                self._offseasonFlowPhase = getattr(row, 'offseason_phase', None)
                self._offseasonFlowTarget = getattr(row, 'offseason_phase_target', None)
                encoded = getattr(row, 'offseason_completed_steps', None)
                if encoded:
                    try:
                        self._offseasonCompletedSteps = set(json.loads(encoded))
                    except Exception:
                        self._offseasonCompletedSteps = set()
                else:
                    self._offseasonCompletedSteps = set()
                logger.info(
                    f"loadOffseasonFlowFromDb: phase={self._offseasonFlowPhase}, "
                    f"completed_steps={sorted(self._offseasonCompletedSteps)}"
                )
            finally:
                sess.close()
        except Exception as e:
            logger.warning(f"Could not load offseason flow state: {e}")

    def _isOffseasonStepComplete(self, step: str) -> bool:
        return step in getattr(self, '_offseasonCompletedSteps', set())

    def _markOffseasonStepComplete(self, step: str) -> None:
        """Record that a non-idempotent offseason step has finished. Lets
        phase resume skip work that already mutated DB state (e.g. front-
        office contract decrements, training stat development).
        """
        if not hasattr(self, '_offseasonCompletedSteps') or self._offseasonCompletedSteps is None:
            self._offseasonCompletedSteps = set()
        self._offseasonCompletedSteps.add(step)
        self._persistOffseasonFlow()

    def _resetOffseasonCompletedSteps(self) -> None:
        self._offseasonCompletedSteps = set()
        self._persistOffseasonFlow()

    def _snapshotDbForPhase(self, phase: str) -> None:
        """Snapshot the offseason-mutable tables to
        /data/offseason_${season}_${phase}.db so a mid-phase restart can roll the
        DB back and re-run the phase cleanly (drafts compound picks, so they
        aren't safe to replay). Skipped on non-prod paths (no /data) and silently
        noops on any error — snapshots are belt-and-suspenders, not load-bearing.

        Two things keep this cheap and flat across seasons:
          1. Only the non-idempotent phases (OFFSEASON_PARTIAL_PHASES) are
             snapshotted — the restore path never rolls back any other phase.
          2. Only the offseason-mutable tables are copied; the large in-season
             append-only tables (OFFSEASON_SNAPSHOT_EXCLUDE_TABLES) are skipped
             since drafts never touch them. That drops each snapshot from a full
             ~57MB copy to ~15MB, and — since the excluded tables are exactly the
             ones that grow every season — keeps it from ballooning over time.

        Restore (run_api._restorePartialPhaseSnapshotIfNeeded) replaces only the
        snapshotted tables, leaving the excluded ones (which never changed during
        the phase) untouched. Old snapshots from prior seasons are pruned first.
        """
        from constants import OFFSEASON_PARTIAL_PHASES, OFFSEASON_SNAPSHOT_EXCLUDE_TABLES
        # Only the non-idempotent phases need a rollback point.
        if phase not in OFFSEASON_PARTIAL_PHASES:
            return
        try:
            import os
            import glob
            import sqlite3
            # Resolve the DB path the same way run_api._restorePartialPhaseSnapshotIfNeeded
            # does, so the writer and reader always agree (prod → /data; local →
            # DATABASE_DIR or ./data).
            dbDir = os.environ.get('DATABASE_DIR', 'data')
            if os.path.exists('/data') and os.path.isdir('/data'):
                dbDir = '/data'
            dbPath = os.path.join(dbDir, 'floosball.db')
            if not os.path.exists(dbPath):
                return
            seasonNum = self.currentSeason.seasonNumber if self.currentSeason else 0
            outDir = os.path.dirname(dbPath)

            # Prune snapshots from prior seasons — only the current season's
            # checkpoints are useful for resume / rollback.
            for old in glob.glob(os.path.join(outDir, 'offseason_s*_*.db')):
                fname = os.path.basename(old)
                # parse season number out of 'offseason_s{N}_{phase}.db'
                try:
                    snap_season = int(fname.split('_')[1].lstrip('s'))
                except (ValueError, IndexError):
                    continue
                if snap_season < seasonNum:
                    try:
                        os.remove(old)
                        logger.info(f"  Pruned stale snapshot: {fname}")
                    except OSError:
                        pass

            outPath = os.path.join(outDir, f"offseason_s{seasonNum}_{phase}.db")
            # Start fresh — a stale same-season/phase file would collide with the
            # CREATE TABLE statements below.
            if os.path.exists(outPath):
                try:
                    os.remove(outPath)
                except OSError:
                    pass

            src = sqlite3.connect(dbPath)
            try:
                tables = [r[0] for r in src.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' "
                    "AND name NOT LIKE 'sqlite_%'"
                ).fetchall()]
                included = [t for t in tables
                            if t not in OFFSEASON_SNAPSHOT_EXCLUDE_TABLES]
                src.execute("ATTACH DATABASE ? AS snap", (outPath,))
                try:
                    # CREATE TABLE AS SELECT copies columns (in declared order) +
                    # rows. Constraints/indexes are intentionally omitted: restore
                    # inserts positionally back into the real (constrained) tables,
                    # so the snapshot is just a data carrier.
                    for t in included:
                        src.execute(
                            f'CREATE TABLE snap."{t}" AS SELECT * FROM main."{t}"'
                        )
                finally:
                    src.execute("DETACH DATABASE snap")
            finally:
                src.close()
            sizeMb = os.path.getsize(outPath) / 1e6 if os.path.exists(outPath) else 0
            logger.info(
                f"  Offseason checkpoint snapshot: {outPath} "
                f"({len(included)} tables, {sizeMb:.1f}MB)"
            )
        except Exception as e:
            logger.debug(f"Could not snapshot DB for phase {phase}: {e}")


    def _computeDraftDayTarget(self) -> Optional[datetime.datetime]:
        """Wall-clock target for draft day — noon ET the day after the Floos Bowl.

        The offseason holds here so free agency runs at a predictable hour with
        people watching. This used to anchor the rookie draft; with that gone
        the FA draft inherits the slot. Without this the front office would run
        straight into the next top of the hour and free agency would resolve an
        hour after the final, overnight.

        Returns:
            SCHEDULED → next noon ET (UTC datetime).
            OFFSEASON_TEST / TEST_SCHEDULED → now + 'offseason' + 'draft_day_wait'.
            All other modes → None (no countdown — they flow through instantly).
        """
        from managers.timingManager import TimingManager, TimingMode
        mode = self.timingManager.mode
        if self.timingManager._isFastCatchingUp:
            return None
        if mode == TimingMode.SCHEDULED:
            return TimingManager._nextNoonEasternUtc()
        if mode in (TimingMode.OFFSEASON_TEST, TimingMode.TEST_SCHEDULED):
            seconds = (self.timingManager.delays.get('offseason', 0.0)
                       + self.timingManager.delays.get('draft_day_wait', 0.0))
            if seconds <= 0:
                return None
            return datetime.datetime.utcnow() + datetime.timedelta(seconds=seconds)
        return None

    def _computeFaDraftTarget(self) -> Optional[datetime.datetime]:
        """Compute the wall-clock target for when the FA draft will begin.

        Returns:
            SCHEDULED → next top-of-hour (UTC datetime).
            OFFSEASON_TEST / TEST_SCHEDULED → now + configured 'fa_draft_wait'.
            All other modes → None.
        """
        from managers.timingManager import TimingManager, TimingMode
        mode = self.timingManager.mode
        if self.timingManager._isFastCatchingUp:
            return None
        if mode == TimingMode.SCHEDULED:
            return TimingManager._nextTopOfHourUtc()
        if mode in (TimingMode.OFFSEASON_TEST, TimingMode.TEST_SCHEDULED):
            seconds = self.timingManager.delays.get('fa_draft_wait', 0.0)
            if seconds <= 0:
                return None
            return datetime.datetime.utcnow() + datetime.timedelta(seconds=seconds)
        return None

    # NOTE: This method is no longer used - free agent retirements are handled
    # by playerManager._processFreeAgentRetirements() within conductFreeAgencySimulation()
    # Kept for reference only
    def _processFreeAgentRetirements_UNUSED(self) -> None:
        """Process retirements of players who've been free agents for 3+ years"""
        from random import randint
        
        leagueHighlights = []
        if self.currentSeason and hasattr(self.currentSeason, 'leagueHighlights'):
            leagueHighlights = self.currentSeason.leagueHighlights
        
        # Process free agent aging and retirement
        # Note: freeAgentYears is already incremented in _processContractExpirations
        for player in list(self.playerManager.freeAgents):
            if player.freeAgentYears > 3:
                shouldRetire = False
                x = randint(1, 10)
                
                # Retirement probability based on tier
                if player.playerTier.value == 1 and x > 3:  # TierD: 70% retire
                    shouldRetire = True
                elif player.playerTier.value == 2 and x > 5:  # TierC: 50% retire
                    shouldRetire = True
                elif x > 8:  # TierB/A/S: 20% retire
                    shouldRetire = True
                
                if shouldRetire:
                    player.team = 'Retired'
                    player.serviceTime = FloosPlayer.PlayerServiceTime.Retired
                    self.playerManager.retiredPlayers.append(player)
                    self.playerManager.newlyRetiredPlayers.append(player)
                    if player in self.playerManager.freeAgents:
                        self.playerManager.freeAgents.remove(player)
                    self.playerManager.safeRemove(self.playerManager.activePlayers, player)
                    self.playerManager.removeFromPositionList(player)
                    
                    leagueHighlights.insert(0, {
                        'event': {'text': f'{player.name} has retired after {player.seasonsPlayed} seasons'}
                    })
                    
                    # Recycle name
                    self._recyclePlayerName(player.name)
    
    def _generateReplacementPlayers(self) -> None:
        """Generate new players to replace retirees"""
        import numpy as np
        from random import randint
        
        newPlayerCount = 12  # Base number of new players per offseason
        numRetired = len(self.playerManager.newlyRetiredPlayers)
        numOfPlayers = max(newPlayerCount, numRetired)
        
        # Generate player skill seeds
        meanPlayerSkill = 80
        stdDevPlayerSkill = 7
        playerAverages = np.random.normal(meanPlayerSkill, stdDevPlayerSkill, numOfPlayers)
        playerAverages = np.clip(playerAverages, 60, 100).tolist()
        
        # Generate replacement for each retired player (position-matched)
        for player in self.playerManager.newlyRetiredPlayers:
            if not playerAverages:
                break
            
            seed = int(playerAverages.pop(randint(0, len(playerAverages) - 1)))
            newPlayer = None
            
            if player.position == FloosPlayer.Position.QB:
                newPlayer = FloosPlayer.PlayerQB(seed)
                self.playerManager.activeQbs.append(newPlayer)
            elif player.position == FloosPlayer.Position.RB:
                newPlayer = FloosPlayer.PlayerRB(seed)
                self.playerManager.activeRbs.append(newPlayer)
            elif player.position == FloosPlayer.Position.WR:
                newPlayer = FloosPlayer.PlayerWR(seed)
                self.playerManager.activeWrs.append(newPlayer)
            elif player.position == FloosPlayer.Position.TE:
                newPlayer = FloosPlayer.PlayerTE(seed)
                self.playerManager.activeTes.append(newPlayer)
            elif player.position == FloosPlayer.Position.K:
                newPlayer = FloosPlayer.PlayerK(seed)
                self.playerManager.activeKs.append(newPlayer)
            
            if newPlayer:
                newPlayer.name = self._getUnusedName()
                newPlayer.team = 'Free Agent'
                newPlayer.id = len(self.playerManager.activePlayers) + len(self.playerManager.retiredPlayers) + 1
                newPlayer.freeAgentYears = 0
                self.playerManager.activePlayers.append(newPlayer)
                self.playerManager.freeAgents.append(newPlayer)
        
        # Generate additional random rookies if we need more than just replacements
        if newPlayerCount > numRetired:
            posList = [FloosPlayer.Position.QB, FloosPlayer.Position.RB, 
                      FloosPlayer.Position.WR, FloosPlayer.Position.TE, FloosPlayer.Position.K]
            
            for _ in range(newPlayerCount - numRetired):
                if not playerAverages:
                    break
                
                seed = int(playerAverages.pop(randint(0, len(playerAverages) - 1)))
                pos = posList[randint(0, len(posList) - 1)]
                newPlayer = None
                
                if pos == FloosPlayer.Position.QB:
                    newPlayer = FloosPlayer.PlayerQB(seed)
                    self.playerManager.activeQbs.append(newPlayer)
                elif pos == FloosPlayer.Position.RB:
                    newPlayer = FloosPlayer.PlayerRB(seed)
                    self.playerManager.activeRbs.append(newPlayer)
                elif pos == FloosPlayer.Position.WR:
                    newPlayer = FloosPlayer.PlayerWR(seed)
                    self.playerManager.activeWrs.append(newPlayer)
                elif pos == FloosPlayer.Position.TE:
                    newPlayer = FloosPlayer.PlayerTE(seed)
                    self.playerManager.activeTes.append(newPlayer)
                elif pos == FloosPlayer.Position.K:
                    newPlayer = FloosPlayer.PlayerK(seed)
                    self.playerManager.activeKs.append(newPlayer)
                
                if newPlayer:
                    newPlayer.name = self._getUnusedName()
                    newPlayer.team = 'Free Agent'
                    newPlayer.id = len(self.playerManager.activePlayers) + len(self.playerManager.retiredPlayers) + 1
                    newPlayer.freeAgentYears = 0
                    self.playerManager.activePlayers.append(newPlayer)
                    self.playerManager.freeAgents.append(newPlayer)
        
        logger.info(f"Generated {numOfPlayers} new players to replace retirees")
    
    def _getUnusedName(self) -> str:
        """Get an unused name from the pool, skipping any already attached to
        a live player or coach. Goes through playerManager.popUniqueName so
        polluted entries get dropped instead of producing a duplicate.
        Falls back to a numeric placeholder if the pool is exhausted.
        """
        from random import randint
        name = self.playerManager.popUniqueName()
        if name is None:
            logger.error("No unused names available!")
            return f"Player {randint(1000, 9999)}"
        return name
    
    async def _updateTeamRatings(self) -> None:
        """Update team ratings and defenses based on current rosters"""
        teamManager = self.serviceContainer.getService('team_manager')
        if teamManager:
            # Update each team's defensive ratings based on their roster
            for team in teamManager.teams:
                team.updateDefense()
            
            # Sort and tier defenses across the league
            teamManager.sortDefenses()
            
            # Update overall team ratings
            teamManager.updateTeamRatings()
    
    async def _handlePlayerSeasonProgression(self) -> None:
        """Handle player progression at season end"""
        for player in self.playerManager.activePlayers:
            # Prospects and upcoming rookies haven't played a pro season — don't
            # accumulate seasonsPlayed/serviceTime or archive empty stat rows.
            # Their dev window is tracked separately via prospect_seasons, and
            # service time resets to Rookie on promotion or FA release.
            if getattr(player, 'is_prospect', False) or getattr(player, 'is_upcoming_rookie', False):
                continue
            # Increment seasons played
            if hasattr(player, 'seasonsPlayed'):
                player.seasonsPlayed += 1
            else:
                player.seasonsPlayed = 1
            
            # Note: contract termRemaining is decremented in _processRosteredPlayerContracts()
            # Do NOT decrement here — it would double-decrement rostered players

            # Update service time using proper progression logic
            if player.seasonsPlayed >= 10:
                player.serviceTime = FloosPlayer.PlayerServiceTime.Veteran4
            elif player.seasonsPlayed >= 7:
                player.serviceTime = FloosPlayer.PlayerServiceTime.Veteran3
            elif player.seasonsPlayed >= 4:
                player.serviceTime = FloosPlayer.PlayerServiceTime.Veteran2
            elif player.seasonsPlayed >= 2:
                player.serviceTime = FloosPlayer.PlayerServiceTime.Veteran1
            else:
                player.serviceTime = FloosPlayer.PlayerServiceTime.Rookie
            
            # Archive season stats
            if hasattr(player, 'seasonStatsDict') and hasattr(player, 'seasonStatsArchive'):
                import copy
                archivedStats = copy.deepcopy(player.seasonStatsDict)
                # Ensure season number and metadata are present
                archivedStats['season'] = self.currentSeason.seasonNumber if self.currentSeason else 0
                archivedStats['gp'] = player.gamesPlayed
                archivedStats['team'] = player.team.name if hasattr(player.team, 'name') else (player.team if isinstance(player.team, str) else 'FA')
                archivedStats['color'] = getattr(player.team, 'color', '#94a3b8') if hasattr(player.team, 'name') else '#94a3b8'
                player.seasonStatsArchive.append(archivedStats)

            # Reset season stats for next year
            if hasattr(player, 'seasonStatsDict'):
                import copy as _copy
                player.seasonStatsDict = _copy.deepcopy(FloosPlayer.playerStatsDict)
                player.seasonStatsDict['team'] = player.team.name if hasattr(player.team, 'name') else (player.team if isinstance(player.team, str) else None)
                player.gamesPlayed = 0
                # Update stat_tracker reference to new season dict
                if hasattr(player, 'stat_tracker'):
                    player.stat_tracker.season_stats_dict = player.seasonStatsDict
    
    def _clearSeasonData(self) -> None:
        """Clear season-specific data for new season"""
        # Clear league standings
        self.leagueManager.clearSeasonData()
        
        # Clear team season stats
        teamManager = self.serviceContainer.getService('team_manager')
        if teamManager:
            teamManager.clearTeamSeasonStats()
        
        # Clear player season stats (handled in progression)
    
    def _saveRosterHistory(self) -> None:
        """Save current roster for each team in their roster history"""
        teamManager = self.serviceContainer.getService('team_manager')
        if not teamManager:
            return
        
        for team in teamManager.teams:
            # Build roster snapshot
            rosterDict = {}
            for pos, player in team.rosterDict.items():
                if player:
                    # Get position as integer (enum value)
                    position_value = player.position if isinstance(player.position, int) else player.position.value if hasattr(player.position, 'value') else 0
                    # Get tier as integer (enum value)
                    tier_value = player.playerTier if isinstance(player.playerTier, int) else player.playerTier.value if hasattr(player, 'playerTier') and hasattr(player.playerTier, 'value') else 0
                    
                    rosterDict[pos] = {
                        'name': player.name,
                        'pos': position_value,
                        'rating': player.playerRating,
                        'stars': tier_value,
                        'termRemaining': player.termRemaining,
                        'id': player.id,
                        'number': player.currentNumber
                    }
            
            # Add defense info
            rosterDict['defense'] = {
                'passDefenseStars': round((((team.defensePassCoverageRating - 60)/40)*4)+1) if team.defensePassCoverageRating else 1,
                'runDefenseStars': round((((team.defenseRunCoverageRating - 60)/40)*4)+1) if team.defenseRunCoverageRating else 1,
                'passDefenseRating': team.defensePassCoverageRating,
                'runDefenseRating': team.defenseRunCoverageRating
            }
            
            # Add to roster history
            if not hasattr(team, 'rosterHistory'):
                team.rosterHistory = []
            
            team.rosterHistory.append({
                'season': self.currentSeason.seasonNumber,
                'roster': rosterDict
            })
            
            logger.debug(f"Saved roster history for {team.name}, season {self.currentSeason.seasonNumber}")
        
    def _initializeSeasonStats(self, isResume: bool = False) -> None:
        """Initialize season statistics tracking.

        isResume=True means we're restarting the server mid-season — the DB
        already has the accumulated values (fatigue, etc.) so we shouldn't
        zero them back to fresh.
        """
        # Save roster history for each team at the start of the season
        self._saveRosterHistory()

        # Reset fatigue for all players only at the start of a genuinely new
        # season — never on a mid-season restart.
        if not isResume:
            for team in self.leagueManager.teams:
                for player in team.rosterDict.values():
                    if player is not None:
                        player.attributes.fatigue = 0.0

        # Initialize team season stats
        for team in self.leagueManager.teams:
            if not hasattr(team, 'seasonTeamStats'):
                team.seasonTeamStats = {
                    'wins': 0,
                    'losses': 0,
                    'winPerc': 0.0,
                    'streak': 0,
                    'scoreDiff': 0,
                    'Offense': {
                        'pts': 0,
                        'runTds': 0,
                        'passTds': 0,
                        'tds': 0,
                        'fgs': 0,
                        'passYards': 0,
                        'runYards': 0,
                        'totalYards': 0
                    },
                    'Defense': {
                        'ints': 0,
                        'fumRec': 0,
                        'sacks': 0,
                        'safeties': 0,
                        'runYardsAlwd': 0,
                        'passYardsAlwd': 0,
                        'totalYardsAlwd': 0,
                        'runTdsAlwd': 0,
                        'passTdsAlwd': 0,
                        'tdsAlwd': 0,
                        'ptsAlwd': 0
                    }
                }
            
            # Initialize additional team attributes that Game class may need
            if not hasattr(team, 'winningStreak'):
                team.winningStreak = False

        # On resume, hydrate seasonTeamStats from DB so live-tracked fields
        # (streak, peakStreak, bigPlays, etc.) reflect the persisted values
        # rather than the class-default zeros. Without this, the first
        # _saveTeamSeasonStatsToDatabase after restart writes zeros back over
        # the persisted values, permanently losing season-cumulative state
        # for any field not also recomputed each game.
        if isResume:
            teamManager = self.serviceContainer.getService('team_manager')
            if teamManager and self.currentSeason:
                teamManager.loadSeasonTeamStats(self.currentSeason.seasonNumber)

    def _updateWeeklyStats(self) -> None:
        """Update weekly statistics and averages for teams and players"""
        # Update team averages (matches original)
        teamManager = self.serviceContainer.getService('team_manager')
        seasonNum = self.currentSeason.seasonNumber if self.currentSeason else None
        if teamManager:
            for team in teamManager.teams:
                if hasattr(team, 'getAverages'):
                    team.getAverages(season=seasonNum)
        
        # Sync stats dicts for all active players (postgameChanges is called per-game in floosball_game.py)
        for player in self.playerManager.activePlayers:
            if hasattr(player, 'sync_stats_dicts'):
                player.sync_stats_dicts()
        
        logger.debug(f"Updated weekly stats for week {self.currentSeason.currentWeek}")

    def _checkRecords(self) -> None:
        """Check for records after weekly games (matches original record checks)"""
        self.recordsManager.checkPlayerGameRecords()
        self.recordsManager.checkSeasonRecords(self.currentSeason.seasonNumber if self.currentSeason else 0)
        self.recordsManager.checkCareerRecords()
        
    def _updatePlayerPerformanceRatings(self, week: int) -> None:
        """Update player performance ratings for the given week (matches original getPerformanceRating call)"""
        self.playerManager.calculatePerformanceRatings(week)
        logger.debug(f"Updated player performance ratings for week {week}")

    async def _selectSeasonMVP(self) -> None:
        """Select the season MVP using z-score analysis of performance ratings across positions"""
        candidates = self.playerManager._computeMvpCandidates()
        if not candidates:
            logger.warning("Could not determine MVP — not enough eligible players")
            return

        # Fan-voted MVP: AwardsManager elects from the top-N-per-position ballot,
        # falling back to the top value-metric candidate below quorum / in sims.
        winner = candidates[0]
        try:
            from database.connection import get_session
            from managers.awardsManager import AwardsManager
            season = self.currentSeason.seasonNumber if self.currentSeason else 0
            _s = get_session()
            try:
                am = AwardsManager(_s, self.playerManager, lowQuorum=self._isTestMode)
                voted = am.resolveMvp(season)
                if voted and voted.get('player') is not None:
                    winner = voted
                # Freeze the ballot (top-5 candidates) at season end so the voting
                # view and the post-announcement results show the same players,
                # even after the offseason resets season stats. Strip the player
                # object for JSON persistence; stats aren't needed for the results.
                self.currentSeason.mvpBallot = [
                    {**{k: v for k, v in c.items() if k != 'player'}, 'stats': []}
                    for c in am.getMvpBallot()
                ]
            finally:
                _s.close()
        except Exception as e:
            logger.error(f"MVP vote resolution failed, using value-metric pick: {e}")
        mvpPlayer = winner['player']

        # Idempotency: skip if already awarded this season (replay safety)
        existingAwards = getattr(mvpPlayer, 'mvpAwards', [])
        if any(a.get('Season') == self.currentSeason.seasonNumber for a in existingAwards):
            logger.info(f"MVP already selected for S{self.currentSeason.seasonNumber}, skipping")
            return

        # Award MVP to the player
        if not hasattr(mvpPlayer, 'mvpAwards'):
            mvpPlayer.mvpAwards = []
        mvpPlayer.mvpAwards.append({
            'Season': self.currentSeason.seasonNumber,
            'team': winner.get('teamAbbr', ''),
            'teamColor': winner.get('teamColor', '#334155')
        })

        # Store broadcast-safe version (no player object)
        mvpResult = dict(winner)
        mvpResult.pop('player', None)
        self.currentSeason.mvp = mvpResult
        logger.info(f"Season {self.currentSeason.seasonNumber} MVP: {mvpResult['name']} ({mvpResult['position']}, {mvpResult['team']}) — z-score: {mvpResult['zScore']}")

        # Add to league highlight feed and broadcast
        mvpText = f"Season {self.currentSeason.seasonNumber} MVP: {mvpResult['name']} ({mvpResult['position']}, {mvpResult['team']})"
        self.currentSeason.leagueHighlights.insert(0, {'event': {'text': mvpText}})
        if BROADCASTING_AVAILABLE and broadcaster.is_enabled():
            if LeagueNewsEvent:
                await broadcaster.broadcast_season_event(LeagueNewsEvent.leagueNews(mvpText))
            if SeasonEvent:
                await broadcaster.broadcast_season_event(
                    SeasonEvent.mvpAnnouncement(mvpResult, self.currentSeason.seasonNumber)
                )

    # ─── Season Transition ──────────────────────────────────────────────────────

    def _processEndOfRegularSeason(self) -> None:
        """Clean up fantasy state at end of regular season (before playoffs).

        - Unequip all cards (deletes EquippedCard rows for the season)
        - Streak counts are on EquippedCard, so they're reset by deletion
        - Cards stay in user collections (UserCard untouched)
        """
        if not self.currentSeason:
            return

        seasonNum = self.currentSeason.seasonNumber
        try:
            from database.connection import get_session
            from database.models import EquippedCard

            session = get_session()
            try:
                deleted = session.query(EquippedCard).filter_by(season=seasonNum).delete()
                session.commit()
                logger.info(f"End of regular season S{seasonNum}: unequipped {deleted} cards")
            except Exception as e:
                session.rollback()
                logger.error(f"Error during end-of-regular-season cleanup: {e}")
            finally:
                session.close()
        except ImportError:
            pass

    # ─── Weekly Modifier Selection ────────────────────────────────────────────

    # Cascade was removed — it was a duplicate of Amplify (both doubled FPx
    # bonus portions). Existing prod rows with modifier='cascade' resolve
    # through the same code path as amplify in the calculator, but new
    # weekly rolls won't pick cascade.
    # Fantasy/Cards fusion: 'overdrive' (×2.5 match) and 'wildcard' (force all
    # matched) are retired — the match multiplier is gone, so both are no-ops.
    # Dropped from the roll weights so they never surface; display/description
    # entries stay below (legacy) for any historical rows.
    MODIFIER_WEIGHTS = {
        "amplify": 10, "ironclad": 10,
        "payday": 10, "grounded": 5,
        "longshot": 10, "frenzy": 10, "synergy": 10, "steady": 10,
        "fortunate": 8,
    }

    MODIFIER_DISPLAY = {
        "amplify": "Amplify", "ironclad": "Ironclad",
        "payday": "Payday", "grounded": "Grounded",
        "longshot": "Longshot",
        "frenzy": "Frenzy", "synergy": "Synergy", "steady": "Steady",
        "fortunate": "Fortunate",
        # Legacy display labels kept so historical rows still render with a
        # friendly name in the recap screens. 'cascade' == amplify; 'overdrive'
        # and 'wildcard' are retired with the match multiplier (fusion).
        "cascade": "Amplify",
        "overdrive": "Overdrive", "wildcard": "Wildcard",
    }

    MODIFIER_DESCRIPTIONS = {
        "amplify": "FPx bonus portions are doubled",
        "ironclad": "Streak cards can't reset this week",
        "payday": "Floobits earned are tripled",
        "grounded": "All FPx effects disabled",
        "longshot": "Conditional card rewards doubled",
        "frenzy": "+FP values are doubled",
        "synergy": "Same-team stack FPx is doubled this week",
        "steady": "No special effect — all normal rules apply",
        "fortunate": "Chance card trigger rates increased by 15%",
        # Legacy — retired modifiers, kept for historical row rendering.
        "cascade": "FPx bonus portions are doubled",
        "overdrive": "Match bonus (retired)",
        "wildcard": "All cards treated as matched (retired)",
    }

    def _selectWeeklyModifier(self, season: int, week: int) -> str:
        """Select a weekly modifier for the given season/week.

        Avoids repeats within the last 3 weeks. Stores the result in DB.
        Returns the modifier slug (e.g., "amplify").
        """
        import random as _random
        try:
            from database.connection import get_session
            from database.models import WeeklyModifier

            session = get_session()
            try:
                # Check if already selected (for resumability)
                existing = session.query(WeeklyModifier).filter_by(
                    season=season, week=week
                ).first()
                if existing:
                    logger.info(f"Weekly modifier already set for S{season}W{week}: {existing.modifier}")
                    return existing.modifier

                # Shuffle-bag selection: EVERY modifier must appear once before
                # any repeats. Replay this season's prior picks to find which
                # modifiers are still unused in the current cycle and draw from
                # those; when a cycle completes (all have appeared) a fresh bag
                # opens. Weights only bias WHICH unused modifier comes up next
                # (so heavier ones tend to land earlier in a cycle) — every
                # modifier still appears exactly once per cycle, so over a season
                # frequencies are uniform and none can be starved. (The old
                # 3-week-window roll could legitimately leave a modifier absent
                # an entire season — see payday in S11.)
                allMods = list(self.MODIFIER_WEIGHTS.keys())
                priorRows = (
                    session.query(WeeklyModifier.modifier)
                    .filter_by(season=season)
                    .filter(WeeklyModifier.week < week)
                    .order_by(WeeklyModifier.week)
                    .all()
                )
                # Ignore legacy/retired modifier keys (e.g. cascade/spotlight) so
                # they don't distort the cycle bookkeeping.
                prior = [r[0] for r in priorRows if r[0] in self.MODIFIER_WEIGHTS]
                used = set()
                for m in prior:
                    if m in used:
                        # A repeat before the cycle finished means the prior data
                        # didn't follow the bag rule (legacy 3-week-window picks);
                        # restart the cycle from this pick so the bag takes over.
                        used = {m}
                    else:
                        used.add(m)
                        if len(used) >= len(allMods):
                            used = set()  # full cycle complete — reshuffle the bag
                available = [m for m in allMods if m not in used]
                if not available:
                    available = list(allMods)
                # On a freshly reshuffled bag, avoid immediately repeating the
                # last pick of the cycle that just closed (a back-to-back repeat).
                if (len(available) == len(allMods) and prior
                        and prior[-1] in available and len(available) > 1):
                    available.remove(prior[-1])
                weights = [self.MODIFIER_WEIGHTS[m] for m in available]
                selected = _random.choices(available, weights=weights, k=1)[0]

                # Persist
                session.add(WeeklyModifier(season=season, week=week, modifier=selected))
                session.commit()
                logger.info(f"Weekly modifier for S{season}W{week}: {self.MODIFIER_DISPLAY.get(selected, selected)}")
                return selected
            except Exception as e:
                session.rollback()
                logger.error(f"Error selecting weekly modifier: {e}")
                return "steady"  # Default to no effect
            finally:
                session.close()
        except ImportError:
            return "steady"

    # Slot ET start hours within a calendar day, indexed by `(week-1) % 7`.
    # list[0] == 12pm is the day's first slot (week 1 → noon, week 7 → 6pm).
    _SLOT_ET_HOURS = [12, 13, 14, 15, 16, 17, 18]

    @staticmethod
    def _dayOfWeek(week: int) -> int:
        """Zero-based calendar day a 1-indexed sim-week (1-28) belongs to.
        Mirrors the season loop's `roundIndex // 7` (week = roundIndex + 1):
        weeks 1-7 → day 0, 8-14 → day 1, 15-21 → day 2, 22-28 → day 3 — four
        even days of 7. (The old `week // 7` was off by one, giving day 0 only
        weeks 1-6 and orphaning week 7 onto the next day.)"""
        return (week - 1) // 7

    def _slotWeeksForDay(self, week: int) -> list:
        """All regular-season sim-weeks that play on the same calendar day as
        `week`, ordered by kickoff (ET hour ascending)."""
        dayNum = self._dayOfWeek(week)
        slots = [w for w in range(1, 29) if self._dayOfWeek(w) == dayNum]
        slots.sort(key=lambda w: self._SLOT_ET_HOURS[(w - 1) % 7])
        return slots

    def _ensureDayModifiers(self, season: int, anchorWeek: int) -> None:
        """Pre-select weekly modifiers for every slot in anchorWeek's calendar
        day so the whole day can be announced ahead of time. Idempotent — rolls
        only missing slots, in kickoff order so within-day repeats are avoided
        by _selectWeeklyModifier's look-back. No-op outside the regular season."""
        if not anchorWeek or anchorWeek < 1 or anchorWeek > 28:
            return
        for w in self._slotWeeksForDay(anchorWeek):
            self._selectWeeklyModifier(season, w)

    def getDayModifierSchedule(self, currentWeek: int) -> dict:
        """The current calendar day's modifier slate (all slots), with the
        active slot and the 'next up' slot flagged. Pre-selects any unrolled
        slots for the day. Regular season only — returns empty during playoffs/
        offseason (no per-slot modifiers there)."""
        if self.currentSeason is None or not currentWeek or currentWeek < 1 or currentWeek > 28:
            return {"day": None, "slots": []}
        season = self.currentSeason.seasonNumber
        self._ensureDayModifiers(season, currentWeek)

        slotWeeks = self._slotWeeksForDay(currentWeek)
        modByWeek = {}
        try:
            from database.connection import get_session
            from database.models import WeeklyModifier
            session = get_session()
            try:
                rows = (
                    session.query(WeeklyModifier)
                    .filter(WeeklyModifier.season == season)
                    .filter(WeeklyModifier.week.in_(slotWeeks))
                    .all()
                )
                modByWeek = {r.week: r.modifier for r in rows}
            finally:
                session.close()
        except Exception as e:
            logger.error(f"getDayModifierSchedule lookup failed: {e}")

        nextWeek = next((w for w in slotWeeks if w > currentWeek), None)
        slots = []
        for w in slotWeeks:
            mod = modByWeek.get(w, "steady")
            etHour = self._SLOT_ET_HOURS[w % 7]
            display = (etHour - 12) if etHour > 12 else 12
            ampm = "PM" if etHour >= 12 else "AM"
            slots.append({
                "week": w,
                "etHour": etHour,
                "label": f"{display if display != 0 else 12}:00 {ampm}",
                "modifier": mod,
                "displayName": self.MODIFIER_DISPLAY.get(mod, mod.title()),
                "description": self.MODIFIER_DESCRIPTIONS.get(mod, ""),
                "isActive": (w == currentWeek),
                "isPast": (w < currentWeek),
                "isNext": (w == nextWeek),
            })
        return {"day": self._dayOfWeek(currentWeek), "slots": slots}

    # ─── Floobits Economy ─────────────────────────────────────────────────────

    def _awardFavoriteTeamBonus(self, teamId: int, amount: int, transactionType: str,
                                 description: str, season: int, week: int = None) -> int:
        """Award a milestone Floobit bonus to a team's fans, scaled per-fan by
        Supporter loyalty × patron rank (this is where the "profit only for
        long-tenure fans of great teams" envelope actually bites). Gated on the
        same activity rule as idle accrual — dormant accounts don't get paid.
        Returns the number of users rewarded."""
        try:
            from database.connection import get_session
            from database.models import User
            from database.repositories.card_repositories import CurrencyRepository
            from managers.supporterManager import (
                computePatronRanks, combinedMultiplier, isEarning,
            )

            session = get_session()
            try:
                users = session.query(User).filter_by(
                    favorite_team_id=teamId, is_active=True
                ).all()
                # Only fans who pass the activity gate (consistent with accrual).
                users = [u for u in users if isEarning(u)]
                if not users:
                    session.close()
                    return 0
                patronRanks = computePatronRanks(session, season)
                currencyRepo = CurrencyRepository(session)
                from database.repositories.notification_repository import NotificationRepository
                notifRepo = NotificationRepository(session)
                count = 0
                for user in users:
                    mult, _loyalty, _patron = combinedMultiplier(user, patronRanks)
                    scaled = int(round(amount * mult))
                    currencyRepo.addFunds(
                        user.id, scaled, transactionType,
                        description=description,
                        season=season, week=week,
                    )
                    notifRepo.create(
                        user.id, 'favorite_team',
                        'Team Bonus',
                        f'{description}! +{scaled} Floobits',
                        data={'teamId': teamId, 'amount': scaled},
                    )
                    count += 1
                session.commit()
                logger.info(f"Awarded scaled {transactionType} bonus (base {amount}F) to {count} fans of team {teamId}")
                return count
            except Exception as e:
                session.rollback()
                logger.error(f"Error awarding favorite team bonus: {e}")
                return 0
            finally:
                session.close()
        except ImportError:
            return 0

    def _accrueSupporterDividends(self, season: int, week: int, tickTenure: bool = True) -> None:
        """Accrue weekly Supporter (fan-loyalty) dividends. Idle income — accrues
        to each fan's claim pool; they collect via POST /api/supporter/claim.
        `tickTenure=False` for playoff rounds: pay the dividend without advancing
        tenure (full regular seasons drive tenure, not playoff weeks)."""
        try:
            from database.connection import get_session
            from managers.supporterManager import accrueWeekly
            session = get_session()
            try:
                accrueWeekly(session, season, week, tickTenure=tickTenure)
                session.commit()
            finally:
                session.close()
        except Exception as e:
            logger.error(f"Supporter dividend accrual failed (s{season} w{week}): {e}")

    def _awardWeeklyLeaderboardPrizes(self, season: int, week: int) -> None:
        """Award Floobits to top leaderboard performers for the week."""
        from constants import (
            WEEKLY_LEADERBOARD_PRIZES, WEEKLY_LEADERBOARD_TOP_PCT_PRIZE,
            WEEKLY_LEADERBOARD_TOP_PCT,
        )

        fantasyTracker = self.serviceContainer.getService('fantasy_tracker')
        if not fantasyTracker:
            return

        try:
            # forceFresh: this runs once at week end, right after card bonuses
            # are persisted — the 8s cache could otherwise serve a pre-card-bonus
            # snapshot and rank/pay prizes on the wrong weekTotal.
            snapshot = fantasyTracker.getSnapshot(season, forceFresh=True)
        except Exception as e:
            logger.error(f"Error getting snapshot for weekly leaderboard: {e}")
            return

        entries = snapshot.get('entries', [])
        if not entries:
            return

        # Sort by weekTotal descending for weekly ranking
        weekRanked = sorted(entries, key=lambda e: e['weekTotal'], reverse=True)

        totalEntries = len(weekRanked)
        top25Cutoff = max(3, int(totalEntries * WEEKLY_LEADERBOARD_TOP_PCT))

        try:
            from database.connection import get_session
            from database.repositories.card_repositories import CurrencyRepository

            session = get_session()
            try:
                currencyRepo = CurrencyRepository(session)
                from database.repositories.notification_repository import NotificationRepository
                notifRepo = NotificationRepository(session)
                awarded = 0
                for i, entry in enumerate(weekRanked):
                    userId = entry['userId']
                    weekRank = i + 1

                    if entry['weekTotal'] <= 0:
                        continue  # No prize for zero participation

                    prize = WEEKLY_LEADERBOARD_PRIZES.get(weekRank)
                    if prize is None and weekRank <= top25Cutoff and totalEntries >= 4:
                        prize = WEEKLY_LEADERBOARD_TOP_PCT_PRIZE

                    if not prize:
                        continue

                    currencyRepo.addFunds(
                        userId, prize, 'leaderboard_weekly',
                        description=f'Week {week} leaderboard #{weekRank}',
                        season=season, week=week,
                    )
                    notifRepo.create(
                        userId, 'leaderboard_weekly',
                        f'Week {week} Leaderboard',
                        f'You placed #{weekRank} on the Week {week} leaderboard! +{prize} Floobits',
                        data={'season': season, 'week': week, 'rank': weekRank, 'prize': prize},
                    )
                    # Achievement hook — Podium tiers (top-3 weekly fantasy finishes)
                    if weekRank <= 3:
                        try:
                            from managers import achievementManager as _am
                            _am.onWeeklyFantasyPodium(session, userId, season)
                        except Exception as _e:
                            logger.warning(f"Podium hook failed: {_e}")

                        # Secret hook — Giant Slayer (top-3 with every roster player ≤3★)
                        try:
                            from database.models import (
                                FantasyRoster as _FR, FantasyRosterPlayer as _FRP, Player as _Player,
                            )
                            from api_response_builders import PlayerResponseBuilder as _PRB
                            from managers import achievementManager as _amGS
                            rosterRows = (
                                session.query(_Player)
                                .join(_FRP, _FRP.player_id == _Player.id)
                                .join(_FR, _FR.id == _FRP.roster_id)
                                .filter(_FR.user_id == userId, _FR.season == season)
                                .all()
                            )
                            if len(rosterRows) >= 6 and all(
                                _PRB.calculateStarRating(p.player_rating) <= 3 for p in rosterRows
                            ):
                                _amGS.unlockSecret(session, userId, "giant_slayer")
                        except Exception as _e:
                            logger.warning(f"Giant Slayer hook failed: {_e}")
                    awarded += 1
                    logger.info(f"Weekly leaderboard prize: user {userId} #{weekRank} = {prize} Floobits")

                session.commit()
                if awarded:
                    logger.info(f"Awarded weekly leaderboard prizes to {awarded} users for week {week}")

            except Exception as e:
                session.rollback()
                logger.error(f"Error awarding weekly leaderboard prizes: {e}")
            finally:
                session.close()
        except ImportError:
            pass

    def _rollCultivationGrowth(self, eq, effectConfig, calcCtx, weekBonus=None):
        """Roll for Cultivation card growth. streak_count tracks growth level."""
        import random as _rand
        import json as _json
        from managers.cardEffects import cultivationGrowthChance, _countCultivationTriggers
        primary = effectConfig.get("primary", {})
        baseFP = primary.get("baseFP", 4.0)
        growthFP = primary.get("growthFP", 2.0)
        triggerEvent = primary.get("triggerEvent", "pass_td")
        # Count triggers for the ON-CARD player and use the SHARED grow-odds, so the % the
        # user watched climb on the meter/detail all week is the % actually rolled here.
        # (Previously this rolled on stale baseChance/chancePerTrigger params Bonsai never
        # sets, over a whole-roster trigger count — the shown odds were disconnected from
        # the real roll.)
        cardPlayerId = eq.user_card.card_template.player_id
        growthLevel = max(0, (getattr(eq, 'streak_count', 1) or 1) - 1)
        triggerCount = _countCultivationTriggers(triggerEvent, calcCtx, cardPlayerId)
        # Same chance-card amplifier (Fortunate modifier / Fortune's Favor / Providence / ...)
        # the live meter showed all week, so the odds watched are the odds rolled.
        growthChance = cultivationGrowthChance(primary, triggerCount, growthLevel,
                                               getattr(calcCtx, 'chanceBonus', 0.0))
        roll = _rand.randint(1, 100)
        # Apply advantage (double roll) if ctx has it
        if calcCtx.hasAdvantage:
            roll2 = _rand.randint(1, 100)
            roll = min(roll, roll2)
        currentFP = round(baseFP + growthFP * growthLevel, 1)
        grew = roll <= growthChance
        if grew:
            eq.streak_count = getattr(eq, 'streak_count', 0) + 1
            newFP = round(currentFP + growthFP, 1)
            resultEq = f"+{newFP} FP. Increased by +{growthFP} this week"
            logger.info(
                f"Cultivation growth! eq={eq.id} roll={roll}≤{growthChance}% "
                f"triggers={triggerCount} level={growthLevel + 1} (+{growthFP} FP)"
            )
        else:
            resultEq = f"+{currentFP} FP. Did not increase this week"
            logger.debug(
                f"Cultivation no growth: eq={eq.id} roll={roll}>{growthChance}% "
                f"triggers={triggerCount}"
            )
        # Patch the stored breakdown with the roll result. The stored
        # primaryFP/totalFP have already been multiplied by match bonus +
        # Conductor boost (run earlier in the calculator). When Bonsai grows
        # we need to scale the new raw value by the same multiplier or we
        # lose those bonuses; when it doesn't grow we leave the boosted
        # totals in place but reattach any conductor suffix the existing
        # equation carried.
        if weekBonus and weekBonus.breakdowns_json:
            try:
                stored = _json.loads(weekBonus.breakdowns_json)
                for bd in stored.get("breakdowns", []):
                    if bd.get("effectName") != "bonsai":
                        continue
                    # Pull any "+X% (Conductor)" suffix off the existing
                    # equation so we can re-append it to the result text.
                    existingEq = bd.get("equation", "") or ""
                    conductorSuffix = ""
                    if " (Conductor)" in existingEq:
                        idx = existingEq.rfind(" +")
                        if idx >= 0 and "(Conductor)" in existingEq[idx:]:
                            conductorSuffix = existingEq[idx:]

                    if grew:
                        # Scale the new raw value by the multiplier that was
                        # applied to the old one — preserves match + conductor.
                        oldRaw = currentFP
                        oldFinal = bd.get("totalFP", oldRaw)
                        multiplier = (oldFinal / oldRaw) if oldRaw > 0 else 1.0
                        newRaw = round(currentFP + growthFP, 1)
                        newFinal = round(newRaw * multiplier, 1)
                        bd["primaryFP"] = newFinal
                        bd["totalFP"] = newFinal

                    bd["equation"] = resultEq + conductorSuffix
                    # Sync the power-bar meter to the resolved roll: the final grow-odds as
                    # the bar fill, and whether it actually grew (green = grew, amber = not).
                    bd["chanceThreshold"] = round(growthChance / 100.0, 4)
                    bd["chanceTriggered"] = grew
                weekBonus.breakdowns_json = _json.dumps(stored)
            except Exception:
                pass

    def _awardWeeklyFpFloobits(self, season: int, week: int) -> None:
        """Award Floobits via the FP→F curve: scale × FP^exponent (Endowment shifts to flatter taper)."""
        from constants import WEEKLY_FP_FLOOBIT_SCALE, WEEKLY_FP_FLOOBIT_EXPONENT

        fantasyTracker = self.serviceContainer.getService('fantasy_tracker')
        if not fantasyTracker:
            return

        try:
            # forceFresh: card bonuses for this week just persisted; a stale
            # cached snapshot would under-pay the FP Floobit reward and
            # under-credit Banner Week / Dynamo achievements by the card bonus.
            snapshot = fantasyTracker.getSnapshot(season, forceFresh=True)
        except Exception as e:
            logger.error(f"Error getting snapshot for weekly FP floobits: {e}")
            return

        entries = snapshot.get('entries', [])
        if not entries:
            return

        try:
            from database.connection import get_session
            from database.repositories.card_repositories import CurrencyRepository
            from database.repositories.notification_repository import NotificationRepository

            session = get_session()
            try:
                currencyRepo = CurrencyRepository(session)
                notifRepo = NotificationRepository(session)
                from database.repositories.shop_repository import ShopPurchaseRepository
                shopRepo = ShopPurchaseRepository(session)
                # Pre-load Prosperity card flat-F bonuses per user
                prosperityBonuses = {}
                try:
                    from database.repositories.card_repositories import EquippedCardRepository
                    eqRepo = EquippedCardRepository(session)
                    allEquipped = eqRepo.getAllForWeek(season, week)
                    for eq in allEquipped:
                        ec = eq.user_card.card_template.effect_config or {}
                        if ec.get("effectName") == "surplus":
                            ownerId = eq.user_id
                            bonus = ec.get("primary", {}).get("flatBonus", ec.get("primary", {}).get("ceilingBonus", 0))
                            prosperityBonuses[ownerId] = prosperityBonuses.get(ownerId, 0) + int(bonus)
                except Exception as e:
                    logger.warning(f"Could not load Prosperity bonuses: {e}")
                awarded = 0
                for entry in entries:
                    weekFp = entry.get('weekTotal', 0)
                    if weekFp <= 0:
                        continue
                    userId = entry['userId']
                    # Endowment's +25% is applied uniformly at the bank (addFunds),
                    # so the FP curve here is always the standard one. We still look
                    # up the boost here purely to stamp the notification's `boosted`
                    # flag accurately.
                    activeBoost = shopRepo.getActiveIncomeBoost(userId, season, week)
                    base = round(WEEKLY_FP_FLOOBIT_SCALE * (weekFp ** WEEKLY_FP_FLOOBIT_EXPONENT))
                    prosperity = prosperityBonuses.get(userId, 0)
                    reward = int(base + prosperity)
                    if reward <= 0:
                        continue
                    descCore = f'Week {week}: {weekFp:.0f} FP → {base}F'
                    if prosperity:
                        descCore += f' (+{prosperity} Prosperity)'
                    currencyRepo.addFunds(
                        userId, reward, 'weekly_fp_bonus',
                        description=descCore,
                        season=season, week=week,
                    )
                    notifRepo.create(
                        userId, 'weekly_fp_bonus',
                        f'Week {week} Earnings',
                        f'+{reward} Floobits from {weekFp:.0f} FP',
                        data={'season': season, 'week': week, 'weekFp': weekFp, 'reward': reward,
                              'base': base, 'prosperity': prosperity, 'boosted': bool(activeBoost)},
                    )
                    # Achievement hooks — Banner Week (single-week) + Dynamo (cumulative season)
                    try:
                        from managers import achievementManager as _am
                        # Round (don't truncate) so the integer the achievement
                        # system compares against its target matches the rounded
                        # value the user sees on the fantasy page (.toFixed(0)).
                        # int(4999.6)=4999 would miss a 5000 target the UI shows
                        # as "5,000". Floobit-curve math above still uses the raw
                        # float weekFp.
                        _am.onWeeklyFantasyPoints(session, userId, round(weekFp), season)
                        seasonFp = round(entry.get('seasonTotal', 0) or 0)
                        if seasonFp > 0:
                            _am.onSeasonFantasyPointsTotal(session, userId, seasonFp, season)
                        # Secret — Blank (≤20 FP with a full roster of 6)
                        rosterSize = len(entry.get('players') or [])
                        if rosterSize >= 6 and weekFp <= 20:
                            _am.unlockSecret(session, userId, "blank")
                    except Exception as _e:
                        logger.warning(f"FP achievement hooks failed: {_e}")
                    awarded += 1
                session.commit()
                if awarded:
                    logger.info(f"Awarded weekly FP floobits to {awarded} users for week {week}")
            except Exception as e:
                session.rollback()
                logger.error(f"Error awarding weekly FP floobits: {e}")
            finally:
                session.close()
        except ImportError:
            pass

    def _awardSeasonEndPrizes(self, completedSeason: int) -> None:
        """Award season-end leaderboard prizes."""
        import math
        from constants import (
            SEASON_LEADERBOARD_PRIZES, SEASON_LEADERBOARD_TOP_PCT_PRIZE,
            SEASON_LEADERBOARD_TOP_PCT,
        )

        fantasyTracker = self.serviceContainer.getService('fantasy_tracker')
        if not fantasyTracker:
            return

        try:
            snapshot = fantasyTracker.getSnapshot(completedSeason)
        except Exception as e:
            logger.error(f"Error getting snapshot for season-end prizes: {e}")
            return

        entries = snapshot.get('entries', [])
        if not entries:
            return

        # Entries are already sorted by seasonTotal descending from getSnapshot()
        totalEntries = len(entries)
        top25Cutoff = max(3, int(totalEntries * SEASON_LEADERBOARD_TOP_PCT))

        try:
            from database.connection import get_session
            from database.repositories.card_repositories import CurrencyRepository

            session = get_session()
            try:
                currencyRepo = CurrencyRepository(session)

                # Idempotency: skip if already awarded for this season
                from database.models import CurrencyTransaction
                alreadyAwarded = session.query(CurrencyTransaction.id).filter_by(
                    transaction_type='leaderboard_season', season=completedSeason
                ).first()
                if alreadyAwarded:
                    logger.info(f"Season {completedSeason} fantasy prizes already awarded — skipping")
                    session.close()
                    return
                from database.repositories.notification_repository import NotificationRepository
                notifRepo = NotificationRepository(session)

                for i, entry in enumerate(entries):
                    userId = entry['userId']
                    seasonRank = i + 1
                    seasonTotal = entry['seasonTotal']

                    # --- Leaderboard prize ---
                    prize = SEASON_LEADERBOARD_PRIZES.get(seasonRank)
                    if prize is None and seasonRank <= top25Cutoff and totalEntries >= 4:
                        prize = SEASON_LEADERBOARD_TOP_PCT_PRIZE

                    if prize:
                        currencyRepo.addFunds(
                            userId, prize, 'leaderboard_season',
                            description=f'Season {completedSeason} leaderboard #{seasonRank}',
                            season=completedSeason,
                        )
                        notifRepo.create(
                            userId, 'leaderboard_season',
                            f'Season {completedSeason} Leaderboard',
                            f'You placed #{seasonRank} on the Season {completedSeason} leaderboard! +{prize} Floobits',
                            data={'season': completedSeason, 'rank': seasonRank, 'prize': prize},
                        )
                        logger.info(
                            f"Season leaderboard prize: user {userId} #{seasonRank} = {prize} Floobits"
                        )

                session.commit()
                logger.info(f"Season-end prizes awarded for season {completedSeason}")

            except Exception as e:
                session.rollback()
                logger.error(f"Error awarding season-end prizes: {e}")
            finally:
                session.close()
        except ImportError:
            pass

    # ── Email report methods ───────────────────────────────────────────────

    def _sendDayEndEmails(self, season: int, dayNum: int, weekRange: list) -> None:
        """Send game day recap emails to opted-in users."""
        try:
            from database.connection import get_session
            from database.models import User, CurrencyTransaction, Game, UserAchievement, Achievement
            from database.repositories.pickem_repository import PickEmRepository
            from managers.emailManager import sendDayReport
            from datetime import datetime, timedelta

            fantasyTracker = self.serviceContainer.getService('fantasy_tracker')
            if not fantasyTracker:
                return

            try:
                snapshot = fantasyTracker.getSnapshot(season)
            except Exception:
                logger.warning("Could not get fantasy snapshot for day-end emails")
                return

            entries = snapshot.get('entries', [])
            if not entries:
                return

            # Build season ranking lookup (sorted by seasonTotal desc)
            seasonRanked = sorted(entries, key=lambda e: e['seasonTotal'], reverse=True)
            rankByUser = {e['userId']: i + 1 for i, e in enumerate(seasonRanked)}
            fpByUser = {e['userId']: e for e in entries}
            totalUsers = len(entries)

            session = get_session()
            try:
                # Get eligible users
                users = session.query(User).filter(
                    User.is_active == True,
                    User.email_opt_out == False,
                    User.email_day_report == True,
                ).all()
                users = [u for u in users if not u.email.endswith('@clerk.user')]

                pickemRepo = PickEmRepository(session)

                # Pre-fetch team objects for name lookup
                teamManager = self.serviceContainer.getService('team_manager')

                from sqlalchemy import func
                # Season prognostication leaderboard (top 10 + rank lookup)
                pickEmSeasonRows = pickemRepo.getSeasonLeaderboard(season)
                pickEmRankByUser = {}
                pickEmLeaderboardTop = []
                usernameById = {e['userId']: e['username'] for e in entries}
                for idx, (uid, correct, total, points) in enumerate(pickEmSeasonRows):
                    pickEmRankByUser[uid] = idx + 1
                    if idx < 10:
                        uname = usernameById.get(uid)
                        if not uname:
                            u = session.query(User).filter_by(id=uid).first()
                            uname = u.username if u else f"User {uid}"
                        pickEmLeaderboardTop.append({
                            'rank': idx + 1,
                            'username': uname,
                            'points': int(points),
                            'correct': int(correct),
                            'total': int(total),
                        })
                pickEmTotalUsers = len(pickEmSeasonRows)

                # Day window for achievements unlocked today: earliest game start in weekRange
                earliestGame = session.query(func.min(Game.game_date)).filter(
                    Game.season == season,
                    Game.week.in_(weekRange),
                ).scalar()
                dayStart = earliestGame if earliestGame else (datetime.utcnow() - timedelta(hours=24))

                # Day 4: compute playoff teams + season leaderboard
                isDay4 = (dayNum == 4)
                playoffTeamIds = set()
                leaderboardTop = []
                if isDay4:
                    # Determine playoff teams: top half of each league by the
                    # full seeding tiebreaker chain (win% → scoreDiff → H2H → …).
                    for league in self.leagueManager.leagues:
                        sortedTeams = self._seedTeams(league.teamList)
                        cutoff = len(sortedTeams) // 2
                        for t in sortedTeams[:cutoff]:
                            playoffTeamIds.add(t.id)

                    # Season leaderboard top 10
                    for i, entry in enumerate(seasonRanked[:10]):
                        leaderboardTop.append({
                            'rank': i + 1,
                            'username': entry['username'],
                            'seasonTotal': round(entry['seasonTotal'], 1),
                        })

                sent = 0
                for user in users:
                    try:
                        userEntry = fpByUser.get(user.id)

                        # Day FP: roster player FP + card bonus FP for this day's weeks
                        dayFP = 0.0
                        if userEntry:
                            from database.models import (
                                WeeklyPlayerFP, WeeklyCardBonus, FantasyRoster,
                                EquippedCard, UserCard, CardTemplate,
                            )
                            roster = session.query(FantasyRoster).filter_by(
                                user_id=user.id, season=season
                            ).first()
                            if roster:
                                from sqlalchemy import func
                                # Fusion: sum each week's equipped lineup's per-player
                                # WeeklyPlayerFP (the lineup can differ week to week), not
                                # a single fixed roster across the day.
                                eqRows = (
                                    session.query(EquippedCard.week, CardTemplate.player_id)
                                    .join(UserCard, EquippedCard.user_card_id == UserCard.id)
                                    .join(CardTemplate, UserCard.card_template_id == CardTemplate.id)
                                    .filter(
                                        EquippedCard.user_id == user.id,
                                        EquippedCard.season == season,
                                        EquippedCard.week.in_(weekRange),
                                    ).all()
                                )
                                if eqRows:
                                    fpRows = session.query(
                                        WeeklyPlayerFP.player_id, WeeklyPlayerFP.week,
                                        WeeklyPlayerFP.fantasy_points,
                                    ).filter(
                                        WeeklyPlayerFP.season == season,
                                        WeeklyPlayerFP.week.in_(weekRange),
                                    ).all()
                                    fpMap = {(pid, wk): fp for pid, wk, fp in fpRows}
                                    for wk, pid in eqRows:
                                        dayFP += float(fpMap.get((pid, wk), 0) or 0)
                                dayCardBonus = session.query(
                                    func.coalesce(func.sum(WeeklyCardBonus.bonus_fp), 0)
                                ).filter(
                                    WeeklyCardBonus.roster_id == roster.id,
                                    WeeklyCardBonus.season == season,
                                    WeeklyCardBonus.week.in_(weekRange),
                                ).scalar()
                                dayFP += float(dayCardBonus or 0)

                        seasonFP = userEntry['seasonTotal'] if userEntry else 0.0
                        seasonRank = rankByUser.get(user.id, 0)

                        # Floobits earned this day
                        floobitsEarned = session.query(
                            func.coalesce(func.sum(CurrencyTransaction.amount), 0)
                        ).filter(
                            CurrencyTransaction.user_id == user.id,
                            CurrencyTransaction.season == season,
                            CurrencyTransaction.week.in_(weekRange),
                            CurrencyTransaction.amount > 0,
                        ).scalar()
                        floobitsEarned = int(floobitsEarned or 0)

                        # Leaderboard prizes this day
                        prizeRows = session.query(
                            CurrencyTransaction.week,
                            CurrencyTransaction.amount,
                            CurrencyTransaction.description,
                        ).filter(
                            CurrencyTransaction.user_id == user.id,
                            CurrencyTransaction.season == season,
                            CurrencyTransaction.week.in_(weekRange),
                            CurrencyTransaction.transaction_type == 'leaderboard_weekly',
                        ).all()
                        leaderboardPrizes = []
                        for row in prizeRows:
                            # Parse rank from description like "Week 3 leaderboard #1"
                            rank = 0
                            if row.description and '#' in row.description:
                                try:
                                    rank = int(row.description.split('#')[-1])
                                except ValueError:
                                    pass
                            leaderboardPrizes.append({
                                'week': row.week,
                                'rank': rank,
                                'prize': row.amount,
                            })

                        # Pick-em results
                        pickEmData = {}
                        pickEmCorrect = 0
                        pickEmTotal = 0
                        pickEmFloobits = 0
                        for w in weekRange:
                            weekResults = pickemRepo.getWeekResultsByUser(season, w)
                            for uid, correct, total, points in weekResults:
                                if uid == user.id:
                                    pickEmCorrect += correct
                                    pickEmTotal += total
                        # Pick-em floobits
                        pickEmFloobitsResult = session.query(
                            func.coalesce(func.sum(CurrencyTransaction.amount), 0)
                        ).filter(
                            CurrencyTransaction.user_id == user.id,
                            CurrencyTransaction.season == season,
                            CurrencyTransaction.week.in_(weekRange),
                            CurrencyTransaction.transaction_type == 'pickem_correct',
                            CurrencyTransaction.amount > 0,
                        ).scalar()
                        pickEmFloobits = int(pickEmFloobitsResult or 0)
                        if pickEmTotal > 0:
                            pickEmData = {
                                'correct': pickEmCorrect,
                                'total': pickEmTotal,
                                'floobitsEarned': pickEmFloobits,
                            }

                        # Favorite team
                        favTeamData = None
                        if user.favorite_team_id and teamManager:
                            team = teamManager.getTeamById(user.favorite_team_id)
                            if team:
                                games = session.query(Game).filter(
                                    Game.season == season,
                                    Game.week.in_(weekRange),
                                ).filter(
                                    (Game.home_team_id == user.favorite_team_id) |
                                    (Game.away_team_id == user.favorite_team_id)
                                ).all()
                                todayGames = []
                                for g in games:
                                    isHome = g.home_team_id == user.favorite_team_id
                                    teamScore = g.home_score if isHome else g.away_score
                                    oppScore = g.away_score if isHome else g.home_score
                                    won = teamScore > oppScore
                                    oppId = g.away_team_id if isHome else g.home_team_id
                                    oppTeam = teamManager.getTeamById(oppId)
                                    oppName = oppTeam.name if oppTeam else f"Team {oppId}"
                                    todayGames.append({
                                        'opponent': oppName,
                                        'won': won,
                                        'score': f"{teamScore}-{oppScore}",
                                        'isHome': isHome,
                                    })
                                favStats = getattr(team, 'seasonTeamStats', {})
                                favTeamData = {
                                    'name': team.name,
                                    'wins': favStats.get('wins', 0),
                                    'losses': favStats.get('losses', 0),
                                    'ties': favStats.get('ties', 0),
                                    'todayGames': todayGames,
                                }
                                if isDay4:
                                    madePlayoffs = user.favorite_team_id in playoffTeamIds
                                    favTeamData['madePlayoffs'] = madePlayoffs

                        # Achievements unlocked during this day
                        achievementsToday = []
                        achRows = session.query(UserAchievement, Achievement).join(
                            Achievement, UserAchievement.achievement_id == Achievement.id
                        ).filter(
                            UserAchievement.user_id == user.id,
                            UserAchievement.completed_at.isnot(None),
                            UserAchievement.completed_at >= dayStart,
                        ).order_by(UserAchievement.completed_at.asc()).all()
                        for ua, ach in achRows:
                            achievementsToday.append({
                                'name': ach.name,
                                'description': ach.description,
                            })

                        data = {
                            'season': season,
                            'dayNum': dayNum,
                            'dayFP': dayFP,
                            'seasonFP': seasonFP,
                            'seasonRank': seasonRank,
                            'totalUsers': totalUsers,
                            'floobitsEarned': floobitsEarned,
                            'leaderboardPrizes': leaderboardPrizes,
                            'pickEm': pickEmData,
                            'favoriteTeam': favTeamData,
                            'pickEmLeaderboardTop': pickEmLeaderboardTop,
                            'userPickEmSeasonRank': pickEmRankByUser.get(user.id, 0),
                            'pickEmTotalUsers': pickEmTotalUsers,
                            'achievementsToday': achievementsToday,
                        }
                        if isDay4:
                            data['leaderboardTop'] = leaderboardTop
                            data['userSeasonRank'] = rankByUser.get(user.id, 0)
                        sendDayReport(user.email, data)
                        sent += 1
                    except Exception as userErr:
                        logger.warning(f"Error building day report for user {user.id}: {userErr}")

                logger.info(f"Sent {sent} day-end report emails for day {dayNum}")
            finally:
                session.close()
        except Exception as e:
            logger.error(f"Error sending day-end emails: {e}")

    def _sendSeasonEndEmails(self, completedSeason: int) -> None:
        """Send season-end summary emails to opted-in users."""
        try:
            from database.connection import get_session
            from database.models import User, CurrencyTransaction
            from database.repositories.pickem_repository import PickEmRepository
            from managers.emailManager import sendSeasonReport
            from sqlalchemy import func

            session = get_session()
            try:
                users = session.query(User).filter(
                    User.is_active == True,
                    User.email_opt_out == False,
                    User.email_season_report == True,
                ).all()
                users = [u for u in users if not u.email.endswith('@clerk.user')]

                pickemRepo = PickEmRepository(session)
                teamManager = self.serviceContainer.getService('team_manager')

                # Champion name (same for all users)
                championName = None
                if hasattr(self.currentSeason, 'champion') and self.currentSeason.champion:
                    champ = self.currentSeason.champion
                    championName = f"{champ.city} {champ.name}" if hasattr(champ, 'city') else champ.name

                sent = 0
                for user in users:
                    try:
                        # Total floobits earned this season (positive transactions only)
                        totalFloobits = session.query(
                            func.coalesce(func.sum(CurrencyTransaction.amount), 0)
                        ).filter(
                            CurrencyTransaction.user_id == user.id,
                            CurrencyTransaction.season == completedSeason,
                            CurrencyTransaction.amount > 0,
                        ).scalar()
                        totalFloobits = int(totalFloobits or 0)

                        # Best weekly rank — check leaderboard_weekly notifications
                        bestWeeklyRank = None
                        weeklyPrizeRows = session.query(
                            CurrencyTransaction.description,
                        ).filter(
                            CurrencyTransaction.user_id == user.id,
                            CurrencyTransaction.season == completedSeason,
                            CurrencyTransaction.transaction_type == 'leaderboard_weekly',
                        ).all()
                        for row in weeklyPrizeRows:
                            if row.description and '#' in row.description:
                                try:
                                    rank = int(row.description.split('#')[-1])
                                    if bestWeeklyRank is None or rank < bestWeeklyRank:
                                        bestWeeklyRank = rank
                                except ValueError:
                                    pass

                        # Season leaderboard prize
                        seasonPrize = session.query(CurrencyTransaction.amount).filter(
                            CurrencyTransaction.user_id == user.id,
                            CurrencyTransaction.season == completedSeason,
                            CurrencyTransaction.transaction_type == 'leaderboard_season',
                        ).scalar()

                        # Pick-em season totals
                        pickEmData = {}
                        allWeekResults = []
                        for w in range(1, 29):
                            allWeekResults.extend(pickemRepo.getWeekResultsByUser(completedSeason, w))
                        # Also include playoff weeks (29+)
                        for w in range(29, 35):
                            allWeekResults.extend(pickemRepo.getWeekResultsByUser(completedSeason, w))
                        pickEmCorrect = 0
                        pickEmTotal = 0
                        for uid, correct, total, points in allWeekResults:
                            if uid == user.id:
                                pickEmCorrect += correct
                                pickEmTotal += total
                        if pickEmTotal > 0:
                            pickEmData = {'correct': pickEmCorrect, 'total': pickEmTotal}

                        # Favorite team
                        favTeamData = None
                        if user.favorite_team_id and teamManager:
                            team = teamManager.getTeamById(user.favorite_team_id)
                            if team:
                                # Determine playoff result
                                playoffResult = None
                                if hasattr(self.currentSeason, 'champion') and self.currentSeason.champion:
                                    if getattr(self.currentSeason.champion, 'id', None) == user.favorite_team_id:
                                        playoffResult = "Floosbowl Champions"
                                # Check if team made playoffs
                                if not playoffResult:
                                    for league in self.leagueManager.leagues:
                                        for t in league.teamList:
                                            if t.id == user.favorite_team_id:
                                                if getattr(t, 'clinchPlayoff', False) or getattr(t, 'madePlayoffs', False):
                                                    playoffResult = playoffResult or "Made Playoffs"

                                favStats = getattr(team, 'seasonTeamStats', {})
                                favTeamData = {
                                    'name': team.name,
                                    'wins': favStats.get('wins', 0),
                                    'losses': favStats.get('losses', 0),
                                    'ties': favStats.get('ties', 0),
                                    'playoffResult': playoffResult,
                                }

                        data = {
                            'season': completedSeason,
                            'totalFloobitsEarned': totalFloobits,
                            'bestWeeklyRank': bestWeeklyRank,
                            'seasonPrize': int(seasonPrize) if seasonPrize else None,
                            'pickEm': pickEmData,
                            'favoriteTeam': favTeamData,
                            'champion': championName,
                        }
                        sendSeasonReport(user.email, data)
                        sent += 1
                    except Exception as userErr:
                        logger.warning(f"Error building season report for user {user.id}: {userErr}")

                logger.info(f"Sent {sent} season-end report emails for season {completedSeason}")
            finally:
                session.close()
        except Exception as e:
            logger.error(f"Error sending season-end emails: {e}")

    def _accumulateFatigue(self) -> None:
        """Increase fatigue for all rostered players based on resilience and the
        team's Recovery Center level (Markets→Facilities)."""
        from constants import (BASE_FATIGUE_PER_WEEK, FATIGUE_RESILIENCE_SCALE,
                               FATIGUE_RESILIENCE_CEILING,
                               RATING_SCALE_MIN, RATING_SCALE_MAX)
        for team in self.leagueManager.teams:
            # Recovery Center level reduces weekly fatigue gain (migrated levels
            # reproduce the old market-tier fatigue reduction).
            fundingReduction = team.facilityEffect('fatigue_reduction')
            for player in team.rosterDict.values():
                if player is None:
                    continue
                resilience = getattr(player.attributes, 'resilience', 80)
                resilienceFactor = (resilience - RATING_SCALE_MIN) / (RATING_SCALE_MAX - RATING_SCALE_MIN)
                weeklyGain = BASE_FATIGUE_PER_WEEK * (FATIGUE_RESILIENCE_CEILING - FATIGUE_RESILIENCE_SCALE * resilienceFactor)
                adjustedGain = weeklyGain * (1.0 - fundingReduction)
                player.attributes.fatigue = min(1.0, (player.attributes.fatigue or 0.0) + adjustedGain)

    def _applyByeFatigueRecovery(self, byeTeamsByLeague: dict) -> None:
        """Give the round-1 bye teams a small fatigue reprieve for resting,
        scaled by market tier (richer clubs recover more). Applied once after
        round 1; modest by design and floored at 0. See PLAYOFF_BYE_FATIGUE_RECOVERY.
        """
        from constants import PLAYOFF_BYE_FATIGUE_RECOVERY
        byeTeams = []
        for teamList in (byeTeamsByLeague or {}).values():
            byeTeams.extend(teamList)
        for team in byeTeams:
            recovery = PLAYOFF_BYE_FATIGUE_RECOVERY.get(
                getattr(team, 'fundingTier', 'MID_MARKET'), 0.006)
            if recovery <= 0:
                continue
            for player in team.rosterDict.values():
                if player is None:
                    continue
                player.attributes.fatigue = max(0.0, (player.attributes.fatigue or 0.0) - recovery)
            logger.info(f"Playoff bye reprieve: {team.name} ({getattr(team, 'fundingTier', '?')}) "
                        f"recovered {recovery:.3f} fatigue")

    def _applyMidseasonFormShift(self, week: int) -> None:
        """
        Per-week, mental-attribute-driven shift to player confidence/
        determination so the team's collective mental makeup shapes whether
        they play to, above, or below their potential.

        The check is per-team (winPct gates the direction) but the effect is
        per-player (each starter's adjustment is scaled by their own mental
        composite). Two distinct composites drive the two directions:

          Hot team (winPct >= .6) — _complacencyVulnerability runs.
              Discipline + focus + attitude composite. Low values drift
              confidence/determination DOWN; high values hold steady. A
              hot team with a few low-discipline guys still slips on those
              specific players while their disciplined teammates anchor.

          Cold team (winPct <= .4) — _adversityResolve runs. Resilience +
              discipline + attitude composite. High values drift
              confidence/determination UP; low values stay flat (resignation).
              A cold team with high-resilience starters can mount a real
              comeback even with some checked-out teammates.

        These layer on top of the per-game streak modifiers in
        Player._updatePostGameModifiers. Streaks drive game-to-game
        volatility; this drives season-arc tilt.
        """
        # Need a few weeks of standings before form is meaningful
        if week < 4:
            return

        from random import randint as _formRand

        for team in self.leagueManager.teams:
            winPct = team.seasonTeamStats.get('winPerc', 0.5)
            starters = [p for p in team.rosterDict.values() if p is not None]
            if len(starters) < 4:
                continue

            # Hot team complacency check
            if winPct >= 0.6:
                # Surplus over .500 scales the pressure: .6 → 0.2; .8 → 0.6; 1.0 → 1.0
                overperformFactor = min(1.0, (winPct - 0.5) * 2)
                for p in starters:
                    vulnerability = p.attributes.complacencyVulnerability()
                    if vulnerability <= 0:
                        continue
                    # selfBelief gates the confidence component only —
                    # determination drift is a drive-to-win axis, not a
                    # belief axis, so it isn't scaled by stability.
                    sb = getattr(p.attributes, 'selfBelief', 80) or 80
                    confStability = max(0.4, min(1.6, 1.0 - (sb - 80) / 50))
                    drift = -(_formRand(5, 18) / 100) * vulnerability * overperformFactor
                    p.attributes.confidenceModifier = round(
                        max(-5.0, p.attributes.confidenceModifier + drift * confStability), 3)
                    p.attributes.determinationModifier = round(
                        max(-5.0, p.attributes.determinationModifier + drift * 0.5), 3)

            # Cold team resolve check
            elif winPct <= 0.4:
                # Deficit below .500 scales the resolve: .4 → 0.2; .2 → 0.6; .0 → 1.0
                underperformFactor = min(1.0, (0.5 - winPct) * 2)
                for p in starters:
                    resolve = p.attributes.adversityResolve()
                    if resolve <= 0:
                        continue
                    sb = getattr(p.attributes, 'selfBelief', 80) or 80
                    confStability = max(0.4, min(1.6, 1.0 - (sb - 80) / 50))
                    boost = (_formRand(5, 18) / 100) * resolve * underperformFactor
                    p.attributes.confidenceModifier = round(
                        min(5.0, p.attributes.confidenceModifier + boost * 0.5 * confStability), 3)
                    p.attributes.determinationModifier = round(
                        min(5.0, p.attributes.determinationModifier + boost), 3)

    def _recentTeamResults(self, window: int) -> dict:
        """{team_id: [1|0, ...]} — each team's last `window` completed regular
        season games this season, oldest first.

        Read back off the games table rather than tracked on the team object so
        a mid-season restart picks the window straight back up instead of
        rebuilding it over the next few weeks.
        """
        from collections import defaultdict
        out = defaultdict(list)
        if not (DB_IMPORTS_AVAILABLE and USE_DATABASE and self.db_session):
            return {}
        try:
            rows = self.db_session.query(
                DBGame.home_team_id, DBGame.away_team_id,
                DBGame.home_score, DBGame.away_score
            ).filter(
                DBGame.season == self.currentSeason.seasonNumber,
                DBGame.status == 'final',
                DBGame.is_playoff == False  # noqa: E712 — SQL boolean, not Python
            ).order_by(DBGame.week.asc(), DBGame.id.asc()).all()
        except Exception as e:
            logger.debug(f"_recentTeamResults: query failed ({e})")
            return {}
        for homeId, awayId, homeScore, awayScore in rows:
            if homeScore is None or awayScore is None:
                continue
            out[homeId].append(1 if homeScore > awayScore else 0)
            out[awayId].append(1 if awayScore > homeScore else 0)
        return {teamId: results[-window:] for teamId, results in out.items()}

    def _updateTeamFormOffsets(self) -> None:
        """Weekly update of every team's continuous form offset — the layer that
        makes a club run hot and cold across a season.

        Without it, measured form variance (sd of a team's wins across the four
        game days) sat at 1.06-1.13 against a coin-flip baseline of 1.32: every
        club played at one fixed level all year and nothing ever moved. With the
        shipped constants it reads 1.11, and clubs with a visibly flat season
        (sd < 1.0) drop from 45% to 39%. See constants.py for the full measured
        amplitude curve and why the plan's 1.6-1.9 target is out of reach here.

        The feedback is NEGATIVE by construction. `recent` is the club's win rate
        over the last FORM_WINDOW games MINUS its own season-to-date rate, so the
        target is a deviation from the team's own level, not from .500 — and the
        pull is the opposite sign. A team riding high gets pulled down toward its
        true level and overshoots into a trough; a team in a hole gets pulled up
        and overshoots into a run. It oscillates instead of running away, which
        is what lets it add within-season variance without moving the win spread.

        Both directions are trait-earned: collectiveVulnerability scales the fall
        from a peak, collectiveResolve scales the climb out of a slump. A club of
        disciplined professionals barely moves; a volatile one swings hard.

        Deliberately separate from FORM_STATE_RATING_MULT, which stays as the
        discrete badge layer with all its positive states pinned at 1.00.
        """
        from constants import (FORM_OSCILLATION_ENABLED, FORM_WINDOW, FORM_PULL,
                               FORM_REVERSION, FORM_NOISE, FORM_MAX,
                               FORM_FEEDBACK, FORM_DECAY)
        if not FORM_OSCILLATION_ENABLED:
            return
        from random import gauss as _gauss

        recentByTeam = self._recentTeamResults(FORM_WINDOW)
        moved = []
        for team in self.leagueManager.teams:
            recentGames = recentByTeam.get(team.id) or []
            wins = team.seasonTeamStats.get('wins', 0)
            losses = team.seasonTeamStats.get('losses', 0)
            played = wins + losses
            # Until the season is longer than the window the two rates are the
            # same number and `recent` is identically zero — nothing to react to.
            if played <= FORM_WINDOW or len(recentGames) < FORM_WINDOW:
                continue

            recent = (sum(recentGames) / len(recentGames)) - (wins / played)
            if FORM_FEEDBACK == 'momentum':
                # A run FEEDS itself, and a slump deepens — the only shape that
                # actually sustains a multi-week arc. Bounded by FORM_DECAY
                # below, not by a restoring force, so it cannot run away.
                target = recent * FORM_PULL
                if recent > 0:
                    target *= 0.5 + team.collectiveResolve()       # ride the run
                else:
                    target *= 0.5 + team.collectiveVulnerability()  # the collapse
            else:
                # Mean-reverting: above your own level pulls you down. Stable, and
                # measured to cancel arcs rather than create them — kept for A/B.
                target = -recent * FORM_PULL
                if recent > 0:
                    target *= 0.5 + team.collectiveVulnerability()
                else:
                    target *= 0.5 + team.collectiveResolve()

            offset = getattr(team, 'formOffset', 0.0) or 0.0
            offset += (target - offset) * FORM_REVERSION + _gauss(0, FORM_NOISE)
            offset *= FORM_DECAY
            team.formOffset = round(max(-FORM_MAX, min(FORM_MAX, offset)), 4)
            moved.append(team)

        # Persist here rather than leaving it to teamManager.saveTeamData(), which
        # only runs at app init — without this the column would sit at 0 all season
        # and a mid-season restart would flatten every club's arc.
        if moved and DB_IMPORTS_AVAILABLE and USE_DATABASE and self.db_session:
            try:
                from database.models import Team as DBTeam
                for team in moved:
                    self.db_session.query(DBTeam).filter_by(id=team.id).update(
                        {'form_offset': team.formOffset})
                self.db_session.commit()
            except Exception as e:
                self.db_session.rollback()
                logger.debug(f"_updateTeamFormOffsets: persist failed ({e})")

    def _updateTeamFormHistory(self) -> None:
        """Track how many consecutive weeks each team has been in their
        current form state. _applyFormState reads this at kickoff to apply
        a regression-to-mean weakening for teams stuck in the same state
        for several weeks — a SPIRALING team eventually catches a break, a
        HOT_STREAK team eventually has an off game, etc.

        Stored as ephemeral attributes on the team object since form state
        is recomputed dynamically and the streak count is meaningful only
        within a season anyway.
        """
        from api_response_builders import TeamResponseBuilder
        for team in self.leagueManager.teams:
            currentState = TeamResponseBuilder.computeFormState(team)
            lastState = getattr(team, '_lastFormState', None)
            if currentState == lastState:
                team._formStateWeeksHeld = getattr(team, '_formStateWeeksHeld', 0) + 1
            else:
                team._lastFormState = currentState
                team._formStateWeeksHeld = 1

    def _propagateAttitudeContagion(self) -> None:
        """
        Locker-room effect: each starter's confidence/determination is nudged
        by the team's average attitude. High-attitude teammates lift the
        room; low-attitude teammates drag it down. Runs every week.

        This is what makes attitude a load-bearing attribute — without this,
        attitude only affects play indirectly (via the season-form composites).
        Now: a toxic veteran genuinely poisons teammates' confidence; a strong
        leader genuinely lifts them.

        Per-player drift is bounded ±0.10 per week so the effect compounds
        slowly across the season but doesn't overwhelm the streak-driven and
        form-shift adjustments. Players closest to the team's attitude average
        are pulled less (already aligned with the room).
        """
        for team in self.leagueManager.teams:
            starters = [p for p in team.rosterDict.values() if p is not None]
            if len(starters) < 4:
                continue
            avgAttitude = sum(getattr(p.attributes, 'attitude', 80) or 80
                              for p in starters) / len(starters)

            # Coach acts as an anchor on the locker room. A leader-coach pulls
            # the room signal upward (reigning in toxic players); a toxic-coach
            # pulls it downward (or fails to dampen toxicity). Coach is roughly
            # 1/3 the weight of the player average — their job is to shape the
            # room, not to override the personalities in it.
            coach = getattr(team, 'coach', None)
            coachAttitude = getattr(coach, 'attitude', 80) if coach else 80
            effectiveAvg = (avgAttitude * 3 + coachAttitude) / 4

            # Neutral at 80; ±20 from neutral = ±0.20 raw swing
            roomSwing = (effectiveAvg - 80) / 100  # -0.20 .. +0.20

            # Toxic-coach amplifier: a low-attitude coach widens the negative
            # signal (toxicity festers under poor leadership). A leader-coach
            # blunts negative signals (active intervention reigns in toxic
            # players). No effect when the room signal is already positive.
            if roomSwing < 0:
                # coachInfluence: 70 → 1.25x (amplify), 80 → 1.0x, 95 → 0.65x (dampen)
                coachInfluence = max(0.5, min(1.4, 1.0 - (coachAttitude - 80) / 40))
                roomSwing *= coachInfluence

            if abs(roomSwing) < 0.04:
                continue  # Near-neutral team: no contagion signal worth applying
            for p in starters:
                # Selfish: a player's own attitude offsets how much they're
                # influenced. A player aligned with the room shifts less; a
                # player out of step (high-attitude on a toxic team, or vice
                # versa) gets pulled more strongly toward the average.
                selfPull = (effectiveAvg - (getattr(p.attributes, 'attitude', 80) or 80)) / 100
                # Final drift: room signal scaled by how far this player is
                # from the room (selfPull). Capped at ±0.10/week.
                drift = max(-0.10, min(0.10, roomSwing * 0.5 + selfPull * 0.3))
                p.attributes.confidenceModifier = round(
                    max(-5.0, min(5.0, p.attributes.confidenceModifier + drift)), 3)
                p.attributes.determinationModifier = round(
                    max(-5.0, min(5.0, p.attributes.determinationModifier + drift)), 3)

    def _driftAttitudes(self, week: int) -> None:
        """
        Per-week attitude drift driven by playing experiences. Players on
        winning teams trend upward (toxic → supportive); players on losing
        teams trend downward (supportive → toxic). High-resilience players
        resist the negative drift; players already at the extreme ends move
        more slowly (entrenched leaders / entrenched toxicity).

        Magnitude is small (±1-2 per week max) so a player's underlying
        attitude only changes meaningfully over multiple weeks. This feeds
        back into both composite scores: rising attitude raises a player's
        adversity resolve and lowers their complacency vulnerability over
        the course of a season — a young player on a winning team grows
        into a leader; a journeyman stuck on a losing team can sour.
        """
        if week < 4:
            return  # Same warm-up gate as the form shift
        from random import randint as _attRand, random as _attFrac
        from constants import (ATTITUDE_NEUTRAL, ATTITUDE_REVERT_RATE,
                               ATTITUDE_DRIFT_MAGNITUDE)

        for team in self.leagueManager.teams:
            winPct = team.seasonTeamStats.get('winPerc', 0.5)
            starters = [p for p in team.rosterDict.values() if p is not None]
            if len(starters) < 4:
                continue

            # Active win/loss push scales with distance from .500. Mid-tier teams
            # (magnitude < 0.5) get only the mean-reversion below, no active push.
            magnitude = abs(winPct - 0.5) * ATTITUDE_DRIFT_MAGNITUDE
            activeDrift = magnitude >= 0.5

            # Coach attitude scales the active drift. A leader-coach (90+) makes
            # upward drift faster and softens downward drift; a toxic-coach (<=70)
            # does the opposite. ~30% effect at extremes.
            coach = getattr(team, 'coach', None)
            coachAttitude = getattr(coach, 'attitude', 80) if coach else 80
            coachLift = (coachAttitude - 80) / 60  # -1/3 .. +1/3 across 60-100

            for p in starters:
                current = getattr(p.attributes, 'attitude', 80) or 80
                if activeDrift and winPct > 0.5:
                    # Toward leadership. Diminishing returns above 90; leader-coach
                    # adds up to +30% to the upward drift.
                    ceilingResist = max(0.0, (current - 80) / 20)  # 0..1
                    coachScale = 1.0 + max(-0.3, coachLift)  # leader: faster, toxic: same
                    cap = max(0, round(magnitude * coachScale * (1.0 - 0.6 * ceilingResist)))
                    if cap > 0:
                        current = min(100, current + _attRand(0, cap))
                elif activeDrift:
                    # Toward toxicity. Resilience cushions the slide; a leader-coach
                    # cushions further, a toxic-coach amplifies.
                    resilience = getattr(p.attributes, 'resilience', 80) or 80
                    resilienceResist = max(0.0, (resilience - 70) / 30)  # 0..1
                    coachScale = max(0.5, 1.0 - coachLift)  # leader: cushion, toxic: amp
                    cap = max(0, round(magnitude * coachScale * (1.0 - 0.5 * resilienceResist)))
                    if cap > 0:
                        current = max(0, current - _attRand(0, cap))

                # Mean-reversion toward neutral -- weak, proportional to distance,
                # applied EVERY week (even mid-tier/idle teams) so soured/inflated
                # extremes decay back toward the middle. Weaker than the active push,
                # so a losing team still sours (just slower) while a soured player on
                # a mid-tier team or in the FA pool recovers over a season or two.
                # Probabilistic 1-point step (fractional amount = chance of a move)
                # so a small rate still shifts the integer attribute.
                # Revert toward THIS player's disposition baseline, not a global neutral.
                _baseline = getattr(p.attributes, 'attitudeBaseline', 0) or ATTITUDE_NEUTRAL
                revertAmount = (_baseline - current) * ATTITUDE_REVERT_RATE
                step = int(revertAmount)
                frac = abs(revertAmount - step)
                if frac and _attFrac() < frac:
                    step += 1 if revertAmount > 0 else -1
                current = max(0, min(100, current + step))

                p.attributes.attitude = current

        # Free agents have no team record, so they get ONLY the mean-reversion --
        # without this the FA pool stays a permanent toxicity sink (the rostered
        # reversion above never reaches an unsigned player). Lets a soured FA
        # recover toward neutral while waiting to be signed.
        for p in (getattr(self.playerManager, 'freeAgents', None) or []):
            attrs = getattr(p, 'attributes', None)
            if attrs is None:
                continue
            current = getattr(attrs, 'attitude', 80) or 80
            _baseline = getattr(attrs, 'attitudeBaseline', 0) or ATTITUDE_NEUTRAL
            revertAmount = (_baseline - current) * ATTITUDE_REVERT_RATE
            step = int(revertAmount)
            frac = abs(revertAmount - step)
            if frac and _attFrac() < frac:
                step += 1 if revertAmount > 0 else -1
            if step:
                attrs.attitude = max(0, min(100, current + step))

    def _recomputeFundingTiersForOffseason(self, completedSeason: int) -> None:
        """Refresh funding tiers at offseason start using the completed
        season's final effective_funding (baseline + carried + in-season
        contributions + season-end tax).

        Tiers stay locked during the regular season (so in-season
        contributions don't shift competitive balance mid-game). At
        offseason start we unfreeze them once, letting fans' contributions
        translate immediately into FA bidding power, training quality, GM
        vote thresholds, and rookie scouting. Season N+1's `_initialize-
        TeamFunding` then carries the same effective_funding forward via
        FUNDING_DECAY_RATE, so the relative tier ordering is preserved.
        """
        if not (DB_IMPORTS_AVAILABLE and USE_DATABASE):
            return
        try:
            from database.connection import get_session
            session = get_session()
            try:
                self._assignFundingTiers(session, completedSeason)
                session.commit()
            except Exception as e:
                session.rollback()
                logger.error(f"Offseason tier recompute failed: {e}")
            finally:
                session.close()
        except ImportError:
            pass

    def _resolveFacilityVotes(self, completedSeason: int) -> None:
        """Resolve the season's facility vote per team — the plurality-winning
        facility gets an upgrade/build project opened into the queue (Phase 3).
        Runs AFTER the waterfall so the new project opens fresh for next season's
        funding (it shows in Active Projects and is funded over the coming season
        rather than built instantly by this season's Treasury). Reads post-waterfall
        levels. No votes → no new project (Treasury just accumulates)."""
        if not (DB_IMPORTS_AVAILABLE and USE_DATABASE):
            return
        try:
            from database.connection import get_session
            from database.models import TeamFacility
            from managers import facilitiesManager
            teamManager = self.serviceContainer.getService('team_manager')
            teams = teamManager.teams if teamManager else []
            session = get_session()
            try:
                opened = 0
                for team in teams:
                    levels = {f.facility_key: f.level for f in
                              session.query(TeamFacility).filter_by(team_id=team.id).all()}
                    proj = facilitiesManager.resolveFacilityVote(
                        session, team.id, completedSeason, levels)
                    if proj is not None:
                        opened += 1
                        logger.info(f"Facility vote: {getattr(team, 'name', team.id)} → "
                                    f"{proj.facility_key} Lv{proj.target_level}")
                session.commit()
                if opened:
                    logger.info(f"Facility votes resolved: {opened} project(s) opened")
            except Exception as e:
                session.rollback()
                logger.error(f"Facility vote resolution failed: {e}")
            finally:
                session.close()
        except ImportError:
            pass

    def _runFacilitySeasonEnd(self, completedSeason: int) -> None:
        """Season-end facility waterfall + offseason construction (Markets→
        Facilities). Treasury (already credited with the deposit) pays upkeep,
        then the oldest open project; funded projects build, unmaintained
        facilities decay. Costs are share-denominated off the PRIOR season's
        faucet (the rates fans funded against during the season)."""
        if not (DB_IMPORTS_AVAILABLE and USE_DATABASE):
            return
        try:
            from database.connection import get_session
            from managers import facilitiesManager
            teamManager = self.serviceContainer.getService('team_manager')
            teams = teamManager.teams if teamManager else []
            session = get_session()
            try:
                shareUnit = facilitiesManager.computeShareUnit(
                    session, completedSeason - 1, numTeams=max(1, len(teams)))
                logs = facilitiesManager.applySeasonEnd(session, teams, completedSeason, shareUnit)
                session.commit()
                logger.info(f"Facility season-end: shareUnit={shareUnit:.0f}, "
                            f"{len(logs)} team(s) had decay/builds")
            except Exception as e:
                session.rollback()
                logger.error(f"Facility season-end failed: {e}")
            finally:
                session.close()
        except ImportError:
            pass

    def _applySeasonEndTax(self, completedSeason: int) -> None:
        """Deduct each user's chosen funding percentage of unspent Floobits between seasons.
        Contributions update the existing TeamFunding records created at season start."""
        import math
        from constants import DEFAULT_FUNDING_PCT
        try:
            from database.connection import get_session
            from database.models import User, TeamFunding
            from database.repositories.card_repositories import CurrencyRepository
            session = get_session()
            try:
                currencyRepo = CurrencyRepository(session)
                users = session.query(User).all()
                contributed = 0
                totalCollected = 0
                teamFundingAccum = {}  # teamId -> total collected
                for user in users:
                    pct = getattr(user, 'team_funding_pct', DEFAULT_FUNDING_PCT)
                    if pct is None:
                        pct = DEFAULT_FUNDING_PCT
                    pct = max(0, min(100, pct))
                    if pct <= 0:
                        continue
                    # No favorite team means no contribution (floobits stay)
                    favTeamId = user.favorite_team_id
                    if favTeamId is None:
                        continue
                    currency = currencyRepo.getByUser(user.id)
                    balance = currency.balance if currency else 0
                    if balance <= 0:
                        continue
                    contribution = math.floor(balance * pct / 100.0)
                    if contribution <= 0:
                        continue
                    currencyRepo.spendFunds(
                        user.id, contribution, 'season_end_tax',
                        description=f'Season {completedSeason} team funding ({pct}%)',
                        season=completedSeason,
                    )
                    contributed += 1
                    totalCollected += contribution
                    teamFundingAccum[favTeamId] = teamFundingAccum.get(favTeamId, 0) + contribution

                # Update existing TeamFunding records (created at season start)
                records = session.query(TeamFunding).filter_by(season=completedSeason).all()
                recordMap = {r.team_id: r for r in records}
                from managers import facilitiesManager
                for teamId, amount in teamFundingAccum.items():
                    rec = recordMap.get(teamId)
                    if rec:
                        rec.fan_contributions = (rec.fan_contributions or 0) + amount
                        rec.current_funding = (rec.baseline_funding or 0) + rec.fan_contributions
                        rec.effective_funding = rec.current_funding + (rec.carried_funding or 0)
                    # Dual-feed: the season-end deposit also funds the new facility
                    # Treasury (the waterfall spends it next). Transitional — the old
                    # TeamFunding ledger above still drives the Market label until cutover.
                    facilitiesManager.addTreasury(session, teamId, amount)

                session.commit()
                logger.info(f"Season-end funding collected from {contributed} users, total {totalCollected}F")
            except Exception as e:
                session.rollback()
                logger.error(f"Error applying season-end funding: {e}")
            finally:
                session.close()
        except ImportError:
            pass

    def contributeToTeam(self, userId: int, teamId: int, amount: int) -> dict:
        """Allow a user to contribute Floobits to their favorite team's funding pool mid-season.

        Contributions are tracked on the current season's record but do NOT change the
        active funding tier — tiers are locked at season start. The contributions will
        factor into next season's carry-forward when _initializeTeamFunding reads
        effective_funding from the completed season.

        Returns dict with updated funding info and user balance, or raises ValueError on failure.
        """
        if amount <= 0:
            raise ValueError("Contribution amount must be positive")
        if not self.currentSeason:
            raise ValueError("No active season")

        from database.connection import get_session
        from database.models import User, TeamFunding
        from database.repositories.card_repositories import CurrencyRepository

        session = get_session()
        try:
            user = session.query(User).filter_by(id=userId).first()
            if not user:
                raise ValueError("User not found")
            if user.favorite_team_id != teamId:
                raise ValueError("You can only contribute to your favorite team")

            currencyRepo = CurrencyRepository(session)
            currency = currencyRepo.getByUser(userId)
            balance = currency.balance if currency else 0
            if balance < amount:
                raise ValueError(f"Insufficient balance ({balance}F available)")

            # Deduct from user
            currencyRepo.spendFunds(
                userId, amount, 'team_contribution',
                description=f'Season {self.currentSeason.seasonNumber} team contribution',
                season=self.currentSeason.seasonNumber,
            )

            # Update TeamFunding record — track contribution but don't change tier
            rec = session.query(TeamFunding).filter_by(
                team_id=teamId,
                season=self.currentSeason.seasonNumber,
            ).first()
            if not rec:
                raise ValueError("Team funding record not found for current season")

            rec.fan_contributions = (rec.fan_contributions or 0) + amount
            # Update totals for record-keeping, but tier stays locked from season start
            rec.current_funding = (rec.baseline_funding or 0) + rec.fan_contributions
            rec.effective_funding = rec.current_funding + (rec.carried_funding or 0)

            # Achievement hook — Benefactor tiers (cumulative season contributions)
            try:
                from managers import achievementManager as _am
                _am.onSeasonTeamContributions(session, userId, self.currentSeason.seasonNumber)
            except Exception as _e:
                logger.warning(f"Benefactor hook failed: {_e}")

            session.commit()

            # Re-read balance after spend
            currency = currencyRepo.getByUser(userId)
            newBalance = currency.balance if currency else 0

            logger.info(f"User {userId} contributed {amount}F to team {teamId} (fan_contributions: {rec.fan_contributions}F, tier unchanged: {rec.funding_tier})")

            return {
                'teamId': teamId,
                'amount': amount,
                'newBalance': newBalance,
                'funding': {
                    'baselineFunding': rec.baseline_funding or 0,
                    'fanContributions': rec.fan_contributions or 0,
                    'carriedFunding': rec.carried_funding or 0,
                    'currentFunding': rec.current_funding,
                    'effectiveFunding': rec.effective_funding,
                    'tier': rec.funding_tier,
                    'tierRank': rec.tier_rank,
                },
            }
        except ValueError:
            session.rollback()
            raise
        except Exception as e:
            session.rollback()
            logger.error(f"Error processing team contribution: {e}")
            raise ValueError(f"Contribution failed: {e}")
        finally:
            session.close()

    def contributeToFacilities(self, userId: int, teamId: int, amount: int,
                               target: str = 'treasury', facilityKey: str = None,
                               projectId: int = None) -> dict:
        """Contribute Floobits toward a team's facilities (Markets→Facilities).

        target:
          - 'treasury' (default) → the general Treasury pool (the season-end
            waterfall spends it on upkeep then the oldest open project).
          - 'upkeep' (+facilityKey) → that facility's upkeep bar — pre-protects
            it so the waterfall doesn't have to cover it.
          - 'project' (+projectId) → an open project's bar — accelerates it past
            the FIFO waterfall.

        Deducts from the user (favorite team only) and credits the chosen bar.
        Returns the new balance + the team's Treasury. Raises ValueError on failure.
        """
        if amount <= 0:
            raise ValueError("Contribution amount must be positive")
        if not self.currentSeason:
            raise ValueError("No active season")

        from database.connection import get_session
        from database.models import User, TeamFacility, FacilityProject
        from database.repositories.card_repositories import CurrencyRepository
        from managers import facilitiesManager

        season = self.currentSeason.seasonNumber
        session = get_session()
        try:
            user = session.query(User).filter_by(id=userId).first()
            if not user:
                raise ValueError("User not found")
            if user.favorite_team_id != teamId:
                raise ValueError("You can only contribute to your favorite team")

            currencyRepo = CurrencyRepository(session)
            currency = currencyRepo.getByUser(userId)
            balance = currency.balance if currency else 0

            # Resolve + validate the target BEFORE spending. For an upkeep or project
            # bar, clamp the contribution to what it still needs, so hitting "100F" on a
            # bar that only needs 99F deducts 99F (no overfunding / wasted spend). The
            # Treasury is an open pool, so it takes the full amount.
            shareUnit = facilitiesManager.computeShareUnit(session, season - 1)
            soloFunded = False  # user took a bar from empty to fully funded by themselves
            builtKey = None     # facility key built immediately if this completes a project
            builtLevel = None
            if target == 'upkeep':
                if not facilityKey:
                    raise ValueError("facilityKey required for an upkeep contribution")
                fac = session.query(TeamFacility).filter_by(
                    team_id=teamId, facility_key=facilityKey).first()
                if not fac:
                    raise ValueError("Facility not found")
                priorFunded = fac.upkeep_funded or 0
                need = max(0, facilitiesManager.upkeepCostFloobits(fac.level, shareUnit) - priorFunded)
                if need <= 0:
                    raise ValueError("Upkeep is already fully funded")
                amount = min(amount, need)
                soloFunded = (priorFunded == 0 and amount >= need)
                desc = f'Facility upkeep ({facilityKey})'
            elif target == 'project':
                if not projectId:
                    raise ValueError("projectId required for a project contribution")
                proj = session.query(FacilityProject).filter_by(
                    id=projectId, team_id=teamId, status='open').first()
                if not proj:
                    raise ValueError("Open project not found")
                priorFunded = proj.funded or 0
                need = max(0, facilitiesManager.projectCostFloobits(proj.cost_shares, shareUnit) - priorFunded)
                if need <= 0:
                    raise ValueError("Project is already fully funded")
                amount = min(amount, need)
                soloFunded = (priorFunded == 0 and amount >= need)
                desc = f'Facility project (#{projectId})'
            elif target == 'treasury':
                desc = 'Team Treasury'
            else:
                raise ValueError(f"Unknown contribution target: {target}")

            if balance < amount:
                raise ValueError(f"Insufficient balance ({balance}F available)")

            currencyRepo.spendFunds(userId, amount, 'facility_contribution',
                                    description=desc, season=season)
            if target == 'upkeep':
                fac.upkeep_funded = (fac.upkeep_funded or 0) + amount
            elif target == 'project':
                proj.funded = (proj.funded or 0) + amount
                # Immediate build: if this contribution completes the project, apply it
                # NOW — the facility level jumps and its perks go live from the team's
                # next game, instead of waiting for the season-end resolution. Upkeep on
                # a facility built this way is waived for the rest of this season.
                projectCostF = facilitiesManager.projectCostFloobits(proj.cost_shares, shareUnit)
                if (proj.funded or 0) >= projectCostF:
                    teamManager = self.serviceContainer.getService('team_manager')
                    teamObj = teamManager.getTeamById(teamId) if teamManager else None
                    builtLevel = facilitiesManager.buildProjectNow(session, teamId, proj, teamObj, season)
                    builtKey = proj.facility_key
                    logger.info(f"Facility project #{projectId} fully funded mid-season — "
                                f"{builtKey} built to Lv{builtLevel} immediately (team {teamId})")
            else:
                facilitiesManager.addTreasury(session, teamId, amount)

            session.commit()
            currency = currencyRepo.getByUser(userId)
            logger.info(f"User {userId} contributed {amount}F to team {teamId} facilities "
                        f"(target={target})")
            return {
                'teamId': teamId, 'amount': amount, 'target': target,
                'soloFunded': soloFunded,
                'projectBuilt': builtKey is not None,
                'builtFacilityKey': builtKey,
                'builtLevel': builtLevel,
                'newBalance': currency.balance if currency else 0,
                'treasury': facilitiesManager.getTreasury(session, teamId),
            }
        except ValueError:
            session.rollback()
            raise
        except Exception as e:
            session.rollback()
            logger.error(f"Error processing facility contribution: {e}")
            raise ValueError(f"Contribution failed: {e}")
        finally:
            session.close()

    def _assignFundingTiers(self, session, season: int) -> None:
        """Assign the MARKET tier by each team's share of the league FANBASE.

        Markets→Facilities cutover: "Market" now means fanbase SIZE (popularity),
        not funding — the dev/morale/fatigue/scouting effects come from facilities
        now, and FA order from Appeal. So MEGA/LARGE/MID/SMALL_MARKET band a team's
        fan count against the league average:
          ratio = fanCount / fairShare, fairShare = totalFans / teamCount.
        Thresholds (FUNDING_TIER_THRESHOLDS): ≥2.0 MEGA, ≥1.15 LARGE, ≥0.85 MID,
        else SMALL. The label still drives expectation-pressure scaling (a genuine
        market-size effect) and the Market display. (Method name kept for callers;
        the `funding_tier` column now holds the fanbase label.)
        """
        from database.models import TeamFunding, User
        from sqlalchemy import func
        from constants import FUNDING_TIER_NAMES, FUNDING_TIER_THRESHOLDS

        records = session.query(TeamFunding).filter_by(season=season).all()
        if not records:
            return

        # Fan count per team = users whose favorite team it is.
        fanCounts = dict(
            session.query(User.favorite_team_id, func.count())
            .filter(User.favorite_team_id.isnot(None))
            .group_by(User.favorite_team_id).all())
        teamCount = len(records)
        totalFans = sum(fanCounts.get(r.team_id, 0) for r in records)
        # Fanless league (no favorites set yet) → everyone neutral MID.
        fairShare = (totalFans / teamCount) if (totalFans > 0 and teamCount > 0) else 0

        def tierFor(fanCount: int) -> tuple:
            if fairShare <= 0:
                return 'MID_MARKET', 3
            ratio = fanCount / fairShare
            for idx, name in enumerate(FUNDING_TIER_NAMES):
                if ratio >= FUNDING_TIER_THRESHOLDS[name]:
                    return name, idx + 1
            last = len(FUNDING_TIER_NAMES) - 1
            return FUNDING_TIER_NAMES[last], last + 1

        for rec in records:
            tierName, tierRank = tierFor(fanCounts.get(rec.team_id, 0))
            rec.funding_tier = tierName
            rec.tier_rank = tierRank
            # tier_locked_funding is a legacy markets-chart snapshot (funding-based);
            # left as effective_funding for now — the chart is reworked in the UI phase.
            rec.tier_locked_funding = rec.effective_funding or 0

        session.flush()

        # Also update runtime team objects so game effects apply immediately.
        # Cache effective_funding too so downstream code (FA draft order,
        # market displays) can read it without a DB hit.
        teamManager = self.serviceContainer.getService('team_manager')
        tierMap = {
            r.team_id: (r.funding_tier, r.tier_rank, r.effective_funding or 0)
            for r in records
        }
        for team in teamManager.teams:
            tier, rank, eff = tierMap.get(team.id, ('MID_MARKET', 3, 0))
            team.fundingTier = tier
            team.fundingTierRank = rank
            team.effectiveFunding = eff

        tierCounts = {}
        for rec in records:
            tierCounts[rec.funding_tier] = tierCounts.get(rec.funding_tier, 0) + 1
        logger.info(f"Funding tiers assigned for season {season}: {tierCounts}")

    def _restoreReigningChampion(self, currentSeason: int) -> None:
        """Restore the floosbowlChampion flag on the team that won last season."""
        previousSeason = currentSeason - 1
        if previousSeason < 1:
            return
        if not (DB_IMPORTS_AVAILABLE and USE_DATABASE and self.db_session):
            return
        try:
            from database.models import Season as DBSeason
            prevDbSeason = self.db_session.query(DBSeason).filter_by(season_number=previousSeason).first()
            if prevDbSeason and prevDbSeason.champion_team_id:
                teamManager = self.serviceContainer.getService('team_manager')
                if teamManager:
                    champTeam = teamManager.getTeamById(prevDbSeason.champion_team_id)
                    if champTeam:
                        champTeam.floosbowlChampion = True
                        logger.info(f"Restored reigning champion: {champTeam.city} {champTeam.name}")
        except Exception as e:
            logger.error(f"Failed to restore reigning champion: {e}")

    def _initializeTeamFunding(self, currentSeason: int) -> None:
        """Create TeamFunding records at season start with league baseline + carry-forward.
        Assigns initial tiers so teams have funding effects from week 1."""
        import math
        from constants import FUNDING_BASELINE_PER_TEAM, FUNDING_DECAY_RATE
        previousSeason = currentSeason - 1
        try:
            from database.connection import get_session
            from database.models import TeamFunding
            session = get_session()
            try:
                # Retrofit: ensure prev season's tier reflects its final
                # effective_funding (baseline + carried + fan contributions
                # + season-end tax) before inheriting. Idempotent — if
                # the offseason recompute already ran for prev (post-
                # deploy seasons), this produces the same value. On the
                # FIRST season after this code deployed mid-cycle, prev
                # season's tier is still the baseline+carried value from
                # its start (the offseason recompute didn't exist when N
                # was simulated). Running it now upgrades the label so
                # the inheritance step picks up fans' contributions
                # immediately — no one-season delay.
                if previousSeason >= 1:
                    self._assignFundingTiers(session, previousSeason)
                    session.flush()

                # Fetch previous season's effective funding for carry-forward,
                # plus its (now-current) tier label so we can inherit rather
                # than recompute. Recomputing N+1's tier from baseline+carried
                # would compress ratios toward 1.0 (every team gets the same
                # +baseline bump), shifting a team that earned MEGA at
                # offseason end back to LARGE for no in-game reason.
                prevFunding = {}
                prevTiers: dict = {}
                if previousSeason >= 1:
                    prevRecords = session.query(TeamFunding).filter_by(season=previousSeason).all()
                    for rec in prevRecords:
                        prevFunding[rec.team_id] = rec.effective_funding
                        prevTiers[rec.team_id] = (
                            rec.funding_tier or 'MID_MARKET',
                            rec.tier_rank or 3,
                        )

                # Check if records already exist for this season (resume after restart)
                existing = session.query(TeamFunding).filter_by(season=currentSeason).first()
                if existing:
                    # Records already created — just load tiers onto runtime teams
                    records = session.query(TeamFunding).filter_by(season=currentSeason).all()
                    tierMap = {
                        r.team_id: (r.funding_tier, r.tier_rank, r.effective_funding or 0)
                        for r in records
                    }
                    teamManager = self.serviceContainer.getService('team_manager')
                    for team in teamManager.teams:
                        tier, rank, eff = tierMap.get(team.id, ('MID_MARKET', 3, 0))
                        team.fundingTier = tier
                        team.fundingTierRank = rank
                        team.effectiveFunding = eff
                    tierCounts = {}
                    for r in records:
                        tierCounts[r.funding_tier] = tierCounts.get(r.funding_tier, 0) + 1
                    logger.info(f"Resumed funding records for season {currentSeason}: {tierCounts}")
                    return

                # Create new records for every team
                teamManager = self.serviceContainer.getService('team_manager')
                carriedByTeam: dict = {}
                for team in teamManager.teams:
                    carriedFunding = math.floor(prevFunding.get(team.id, 0) * FUNDING_DECAY_RATE)
                    carriedByTeam[team.id] = carriedFunding
                    baseline = FUNDING_BASELINE_PER_TEAM
                    currentFunding = baseline
                    effectiveFunding = currentFunding + carriedFunding

                    funding = TeamFunding(
                        team_id=team.id,
                        season=currentSeason,
                        baseline_funding=baseline,
                        fan_contributions=0,
                        current_funding=currentFunding,
                        carried_funding=carriedFunding,
                        effective_funding=effectiveFunding,
                        # Tier locked at season-start values — baseline + carried.
                        # Will be overwritten by _assignFundingTiers at offseason
                        # recompute (which uses full effective_funding instead).
                        tier_locked_funding=effectiveFunding,
                    )
                    session.add(funding)

                session.flush()

                # Facilities (Markets→Facilities): reset each facility's upkeep
                # tally for the new season + top up the Treasury (first activation
                # seeds it from the 50% carry — no double-dip with the grandfathered
                # facilities; every season adds the baseline floor).
                try:
                    from managers import facilitiesManager
                    facilitiesManager.prepareSeasonStart(
                        session, [t.id for t in teamManager.teams],
                        carriedByTeam, FUNDING_BASELINE_PER_TEAM)
                    session.flush()
                except Exception as e:
                    logger.warning(f"Facility season-start prep failed: {e}")
                # Tier assignment:
                #   Season 1 (no prior season): assign by ratio. All teams
                #     start at baseline=200 with carried=0, so everyone
                #     lands at MID_MARKET — same outcome as inheriting.
                #   Season N>1: inherit the tier label from N-1's row.
                #     N-1's row was finalized by _recomputeFundingTiers-
                #     ForOffseason at the start of its offseason, so the
                #     label carries the team's actual end-of-season
                #     standing. Skipping the recompute here avoids the
                #     baseline-compression tier-flip.
                if prevTiers:
                    newRecords = session.query(TeamFunding).filter_by(season=currentSeason).all()
                    for rec in newRecords:
                        inheritedTier, inheritedRank = prevTiers.get(
                            rec.team_id, ('MID_MARKET', 3),
                        )
                        rec.funding_tier = inheritedTier
                        rec.tier_rank = inheritedRank
                    session.flush()
                    # Mirror to runtime team objects so game-day effects
                    # read the inherited tier immediately.
                    teamManager = self.serviceContainer.getService('team_manager')
                    tierMap = {
                        r.team_id: (r.funding_tier, r.tier_rank, r.effective_funding or 0)
                        for r in newRecords
                    }
                    for team in teamManager.teams:
                        tier, rank, eff = tierMap.get(team.id, ('MID_MARKET', 3, 0))
                        team.fundingTier = tier
                        team.fundingTierRank = rank
                        team.effectiveFunding = eff
                    tierCounts: dict = {}
                    for r in newRecords:
                        tierCounts[r.funding_tier] = tierCounts.get(r.funding_tier, 0) + 1
                    logger.info(f"Inherited funding tiers from S{previousSeason}: {tierCounts}")
                else:
                    # Season 1 fallback — uniform MID via ratio path
                    self._assignFundingTiers(session, currentSeason)
                session.commit()
                logger.info(f"Initialized team funding for season {currentSeason} (baseline={FUNDING_BASELINE_PER_TEAM}F)")
            except Exception as e:
                session.rollback()
                logger.error(f"Error initializing team funding: {e}")
                # Fall back to MID_MARKET defaults
                teamManager = self.serviceContainer.getService('team_manager')
                for team in teamManager.teams:
                    team.fundingTier = 'MID_MARKET'
                    team.fundingTierRank = 3
            finally:
                session.close()
        except ImportError:
            logger.info("First season — all teams default to MID_MARKET funding tier")

    def _applyDevTierOverride(self) -> None:
        """Dev/testing only: redistribute teams across all four funding tiers
        regardless of actual fan contributions. Bypasses the funding-derived
        tier assignment from `_assignFundingTiers` so single-user test runs
        produce a realistic 4-tier distribution.

        Two modes:
          - DEV_SPREAD_TIERS=1   → deterministic by team.id (same team gets
            the same tier every season). Good for trajectory diagnostics.
          - DEV_SHUFFLE_TIERS=1  → random per-season assignment seeded by the
            current season number. Same season number reproduces the same
            shuffle; consecutive seasons rotate teams through different tiers.
            Use when the deterministic mode keeps your favorite team in the
            same bucket every season.
        """
        import os
        import random as _random
        spread = os.environ.get("DEV_SPREAD_TIERS") == "1"
        shuffle = os.environ.get("DEV_SHUFFLE_TIERS") == "1"
        if not (spread or shuffle):
            return
        teamManager = self.serviceContainer.getService('team_manager')
        sortedTeams = sorted(teamManager.teams, key=lambda t: getattr(t, 'id', 0))
        n = len(sortedTeams)
        if n == 0:
            return
        if shuffle:
            seasonNum = getattr(self.currentSeason, 'seasonNumber', None) or 1
            seed = seasonNum * 1009 + 7
            rng = _random.Random(seed)
            rng.shuffle(sortedTeams)
            mode = f"shuffled (season={seasonNum}, seed={seed})"
        else:
            mode = "deterministic by team.id"
        chunk = max(1, n // 4)
        tiers = ["MEGA_MARKET", "LARGE_MARKET", "MID_MARKET", "SMALL_MARKET"]
        for idx, team in enumerate(sortedTeams):
            tierIdx = min(idx // chunk, 3)
            team.fundingTier = tiers[tierIdx]
            team.fundingTierRank = tierIdx + 1
        logger.info(
            f"Dev tier override active ({mode}) — {n} teams × 4 tiers × "
            f"{chunk} teams each"
        )

    def _getPickemWeek(self) -> int:
        """Return the effective week number for pick-em storage.
        Regular season: currentWeek (1-28). Playoffs: 28 + playoffRound (29-32)."""
        playoffRound = getattr(self.currentSeason, 'currentPlayoffRound', None)
        if playoffRound:
            return 28 + playoffRound
        week = self.currentSeason.currentWeek
        return week if isinstance(week, int) else 0

    def playoffRoundLabel(self, week: int) -> str:
        """Human label for a playoff virtual week (29+): 'Playoffs Round N',
        'League Championship', or 'Floos Bowl'. Derived from the week number so
        it's correct even when the volatile currentPlayoffRound flag is unset
        (e.g. a brief window during a mid-playoff restart)."""
        import floosball_methods as FloosMethods
        numOfRounds = int(FloosMethods.getPower(2, len(self.leagueManager.teams) / 2))
        rnd = week - 28
        if rnd >= numOfRounds:
            return 'Floos Bowl'
        if rnd == numOfRounds - 1:
            return 'League Championship'
        return f'Playoffs Round {max(1, rnd)}'

    def _autoPickFavorites(self, games) -> None:
        """Auto-submit picks for users who opted into auto-pick.

        Mode selection per user (users.auto_pick_mode):
        - "off":       no auto-picks (user will submit manually or skip)
        - "favorites": pick higher-ELO team (home breaks ties)
        - "underdogs": pick lower-ELO team (away breaks ties)
        - "random":    coin flip per game

        `users.auto_pick_never_against_favorite` then overrides ANY of those on a game
        involving the user's own club, so the auto-picker never calls against them.

        Uses 1.0x timing (pre-game) and ELO-based underdog multiplier."""
        import random as _random
        from datetime import datetime as _dt, timedelta as _td
        from constants import calculateUnderdogMultiplier, SUPPORTER_ACTIVITY_WINDOW_DAYS
        seasonNum = self.currentSeason.seasonNumber
        week = self._getPickemWeek()
        try:
            from database.connection import get_session
            from database.models import User
            from database.repositories.pickem_repository import PickEmRepository
            session = get_session()
            try:
                # Only auto-pick for users active within the window — a departed account
                # shouldn't keep silently accruing pick-em credit (and cluttering the board)
                # long after its owner stopped showing up. Same activity definition the live
                # leaderboard prunes on and the rest of the app uses.
                _cutoff = _dt.utcnow() - _td(days=SUPPORTER_ACTIVITY_WINDOW_DAYS)
                autoUsers = session.query(User).filter(
                    User.auto_pick_mode.in_(("favorites", "underdogs", "random")),
                    User.last_login_at.isnot(None),
                    User.last_login_at >= _cutoff,
                ).all()
                if not autoUsers:
                    return

                pickemRepo = PickEmRepository(session)
                totalAutoPicks = 0
                for user in autoUsers:
                    mode = user.auto_pick_mode or "off"
                    favouriteId = (getattr(user, 'favorite_team_id', None)
                                   if getattr(user, 'auto_pick_never_against_favorite', False)
                                   else None)
                    existingPicks = pickemRepo.getUserPicks(user.id, seasonNum, week)
                    pickedIndices = {p.game_index for p in existingPicks}
                    for i, game in enumerate(games):
                        if i in pickedIndices:
                            continue
                        homeTeam = game.homeTeam
                        awayTeam = game.awayTeam
                        homeElo = getattr(homeTeam, 'elo', 1500)
                        awayElo = getattr(awayTeam, 'elo', 1500)

                        if mode == "favorites":
                            # Higher ELO, home breaks ties
                            pickedId = homeTeam.id if homeElo >= awayElo else awayTeam.id
                        elif mode == "underdogs":
                            # Lower ELO, away breaks ties
                            pickedId = awayTeam.id if awayElo <= homeElo else homeTeam.id
                        elif mode == "random":
                            pickedId = _random.choice((homeTeam.id, awayTeam.id))
                        else:
                            continue

                        # ⚠️ Loyalty override. A user who runs auto-pick can ask never to
                        # have a machine call against their own club on their behalf —
                        # backing your team is the reason you have one, and the points it
                        # costs are a price they would rather pay than see the pick.
                        #
                        # Applied AFTER the mode has chosen, so it overrides every mode
                        # including "underdogs" and "random", and only ever flips the pick
                        # TO the favourite club — it never picks against anyone else's.
                        # Opt-in, because on average it loses points.
                        if favouriteId and pickedId != favouriteId:
                            if favouriteId in (homeTeam.id, awayTeam.id):
                                pickedId = favouriteId

                        pickedIsHome = (pickedId == homeTeam.id)
                        underdogMult = calculateUnderdogMultiplier(homeElo, awayElo, pickedIsHome)
                        pickemRepo.submitPick(
                            user.id, seasonNum, week, i,
                            homeTeam.id, awayTeam.id, pickedId,
                            pointsMultiplier=1.0,
                            underdogMultiplier=underdogMult,
                            isAuto=True,
                        )
                        totalAutoPicks += 1
                session.commit()
                if totalAutoPicks > 0:
                    logger.info(f"Auto-picked {totalAutoPicks} games for {len(autoUsers)} users (week {week})")
            except Exception as e:
                session.rollback()
                logger.error(f"Error auto-picking for week {week}: {e}")
            finally:
                session.close()
        except ImportError:
            pass

    def _resolvePickEmGame(self, gameIndex: int, game) -> None:
        """Resolve pick-em picks for a single game immediately when it ends."""
        season = self.currentSeason.seasonNumber
        week = self._getPickemWeek()
        winner = getattr(game, 'winningTeam', None)
        if winner is None:
            return
        try:
            from database.connection import get_session
            from database.repositories.pickem_repository import PickEmRepository
            session = get_session()
            try:
                pickemRepo = PickEmRepository(session)
                count = pickemRepo.resolvePicks(season, week, gameIndex, winner.id)
                session.commit()
                if count > 0:
                    logger.info(f"Resolved {count} pick-em picks for game {gameIndex} (winner: {winner.name})")
            except Exception as e:
                session.rollback()
                logger.error(f"Error resolving pick-em for game {gameIndex}: {e}")
            finally:
                session.close()
        except ImportError:
            pass


    def _processDeferredAchievements(self) -> None:
        """Grant any deferred achievement rewards owed to users (e.g. Veteran at new season)."""
        try:
            from database.connection import get_session
            from managers import achievementManager as _am
            session = get_session()
            try:
                _am.processDeferredRewards(session)
                session.commit()
            except Exception as e:
                session.rollback()
                logger.warning(f"Deferred achievement processing failed: {e}")
            finally:
                session.close()
        except Exception:
            pass

    def _sweepExpiredAchievementRewards(self) -> None:
        """Drop pending rewards the user didn't claim or stash-in-time, then
        convert any over-cap pack stash to Floobits.

        Passes the new season number so the sweep can also clear stashed
        rewards whose deferral target season has already come and gone
        without the reward being claimed. After the sweep, over-cap packs
        (held in violation of the soft cap due to legacy state or future
        bugs) are converted to Floobits at shop cost — keeps the cap
        consistent at the start of every new season.
        """
        try:
            from database.connection import get_session
            from managers import achievementManager as _am
            newSeason = self.currentSeason.seasonNumber if self.currentSeason else 0
            session = get_session()
            try:
                _am.sweepExpiredRewards(session, currentSeason=newSeason)
                _am.convertOverCapPackStash(session)
                session.commit()
            except Exception as e:
                session.rollback()
                logger.warning(f"Expired reward sweep / overcap conversion failed: {e}")
            finally:
                session.close()
        except Exception:
            pass

    def _ruleVoteMgr(self):
        """Lazily-constructed RuleVoteManager (Cores rule-change vote)."""
        if getattr(self, '_ruleVoteManager', None) is None:
            from managers.ruleVoteManager import RuleVoteManager
            self._ruleVoteManager = RuleVoteManager(self.serviceContainer)
        return self._ruleVoteManager

    def _maybeOpenRuleVote(self, week: int, weekStartTime) -> None:
        """Open a Cores rule-change vote if the game-day escalation roll fires.
        Wrapped so nothing here ever blocks or breaks the game loop."""
        try:
            if not self.currentSeason:
                return
            # closes_at = the real wall-clock time the day's games start (the vote's
            # countdown target). Scheduled: the true kickoff. Non-scheduled: kickoff is
            # backdated, so estimate from the setup + games-start delays the loop is
            # about to sleep, so the countdown reflects reality (~a minute), not hours.
            closesAt = weekStartTime
            if not getattr(self.timingManager, '_isScheduledMode', False):
                d = getattr(self.timingManager, 'delays', {}) or {}
                secs = (d.get('week_start_wait', 30) or 0) + (d.get('game_announcement', 30) or 0)
                closesAt = datetime.datetime.utcnow() + datetime.timedelta(seconds=secs)
            self._ruleVoteMgr().maybeOpenWindow(
                self.currentSeason.seasonNumber, week,
                self.currentSeason.gameRules, closesAt)
        except Exception as e:
            logger.warning(f"Rule vote open hook failed: {e}")

    def _resolveRuleVote(self) -> None:
        """Resolve the open Cores rule-change vote (applies the winner to the live
        rules). No-op if none is open. Never blocks/breaks the game loop."""
        try:
            if not self.currentSeason:
                return
            self._ruleVoteMgr().resolveOpenWindow(
                self.currentSeason.seasonNumber, self.currentSeason.gameRules,
                requireClosed=True)
        except Exception as e:
            logger.warning(f"Rule vote resolve hook failed: {e}")

    def _applyChaosRulesIfCritical(self, game) -> None:
        """During a Criticality, give this game its OWN randomized ruleset just
        before kickoff — chaos rules are hidden from users, both teams play by the
        same set, results count. Reverts naturally when Criticality ends (normal
        weeks keep the shared season ruleset). Never blocks the game loop."""
        try:
            if not self.currentSeason:
                return
            from managers.anomalyManager import isCriticalityWeek
            # game.week is 0-indexed (createSchedule convention), but isCriticalityWeek
            # keys on the 1-indexed week (like currentSeason.currentWeek / start_week) —
            # a raw game.week queries week N-1 and misses the window entirely, so chaos
            # rules never apply. Convert, matching the glitch/awakened path in
            # floosball_game.py:10720. The currentWeek fallback is already 1-indexed.
            gameWeek = getattr(game, 'week', None)
            week = (gameWeek + 1) if gameWeek is not None else self.currentSeason.currentWeek
            if isCriticalityWeek(self.currentSeason.seasonNumber, week):
                game.gameRules = self._ruleVoteMgr().randomChaosRules(self.currentSeason.gameRules)
        except Exception as e:
            logger.warning(f"Criticality chaos ruleset failed: {e}")

    async def _firePreGameReminder(self, gameStartTime: datetime.datetime, weekNumber: int,
                                   weekText: str, gamesCount: int) -> None:
        """Sleep until 15 min before game start, then broadcast games_starting_soon.

        Decouples the reminder from week_start, which can fire up to 8 hours early on
        cross-day transitions. Skips the event if we're already within the 15-min
        window (e.g. catch-up mode, non-scheduled timing modes, tests)."""
        if not (BROADCASTING_AVAILABLE and broadcaster.is_enabled()):
            return
        # Only meaningful in scheduled-mode (real-time) runs — other timing modes
        # either compress or fast-forward and don't need a 15-min heads-up.
        if not getattr(self.timingManager, '_isScheduledMode', False):
            return
        if getattr(self.timingManager, 'catchingUp', False):
            return

        reminderTime = gameStartTime - datetime.timedelta(minutes=15)
        now = datetime.datetime.utcnow()
        if now >= reminderTime:
            # Past the window already — fire immediately so the bot still gets a signal.
            pass
        else:
            while datetime.datetime.utcnow() < reminderTime:
                await asyncio.sleep(self.timingManager.delays.get('daily_check', 30))

        try:
            event = SeasonEvent.gamesStartingSoon(
                seasonNumber=self.currentSeason.seasonNumber,
                weekNumber=weekNumber,
                weekText=weekText,
                gamesCount=gamesCount,
                gameStartTime=gameStartTime.isoformat() + 'Z',
            )
            broadcaster.broadcast_sync('season', event)
        except Exception as e:
            logger.warning(f"Pre-game reminder broadcast failed: {e}")

    def _creditVeteranForWeek(self, season: int) -> None:
        """Bump Veteran achievement progress for every user who had a fantasy
        roster with at least one player this season when the week ended."""
        try:
            from database.connection import get_session
            from database.models import FantasyRoster, FantasyRosterPlayer
            from managers import achievementManager as _am
            session = get_session()
            try:
                userIds = [
                    r.user_id for r in session.query(FantasyRoster.user_id).filter(
                        FantasyRoster.season == season,
                        FantasyRoster.id.in_(
                            session.query(FantasyRosterPlayer.roster_id).distinct()
                        ),
                    ).distinct().all()
                ]
                for uid in userIds:
                    _am.onFantasyRosterWeekCompleted(session, uid, season)
                session.commit()
            except Exception as e:
                session.rollback()
                logger.warning(f"Veteran achievement credit failed: {e}")
            finally:
                session.close()
        except Exception:
            pass  # never break week-end over an achievement hook

    def _checkSeasonEndSecrets(self, season: int) -> None:
        """Evaluate secrets that fire once a season concludes:
        Sovereign (#1 fantasy), Soothsayer (#1 pick-em), Consecration (fav team wins)."""
        try:
            from database.connection import get_session
            from database.models import User
            from database.repositories.pickem_repository import PickEmRepository
            from managers import achievementManager as _am

            champTeamId = getattr(self.currentSeason.champion, 'id', None) if self.currentSeason else None

            # Fantasy #1 — top seasonTotal from snapshot
            sovereignUserId = None
            try:
                fantasyTracker = self.serviceContainer.getService('fantasy_tracker')
                if fantasyTracker:
                    snapshot = fantasyTracker.getSnapshot(season)
                    entries = snapshot.get("entries", [])
                    if entries:
                        # entries are sorted by seasonTotal desc and ranked
                        top = entries[0]
                        if (top.get("seasonTotal") or 0) > 0:
                            sovereignUserId = top.get("userId")
            except Exception as e:
                logger.warning(f"Sovereign lookup failed: {e}")

            session = get_session()
            try:
                if sovereignUserId:
                    _am.unlockSecret(session, sovereignUserId, "sovereign")

                # Pick-em #1 — top total points for the season
                try:
                    pickemRepo = PickEmRepository(session)
                    seasonBoard = pickemRepo.getSeasonLeaderboard(season)
                    if seasonBoard:
                        topUid, _corr, _tot, topPts = seasonBoard[0]
                        if topPts and topPts > 0:
                            _am.unlockSecret(session, topUid, "soothsayer")
                except Exception as e:
                    logger.warning(f"Soothsayer lookup failed: {e}")

                # Consecration — every user whose favorite team is the champion
                if champTeamId:
                    for (uid,) in session.query(User.id).filter(
                        User.favorite_team_id == champTeamId,
                    ).all():
                        _am.unlockSecret(session, uid, "consecration")

                # Monk — never opened a pack all season (only for engaged users with a roster)
                from database.models import (
                    PackOpening, FantasyRoster, EquippedCard,
                    TeamSeasonStats, CurrencyTransaction,
                )
                from sqlalchemy import func
                # Fusion: an "engaged" user fielded a full lineup — equipped cards
                # covering >= 6 distinct slots this season (not FantasyRosterPlayer).
                engagedUserRows = session.query(EquippedCard.user_id).filter(
                    EquippedCard.season == season,
                ).group_by(EquippedCard.user_id).having(
                    func.count(func.distinct(EquippedCard.slot_number)) >= 6
                ).all()
                engagedUserIds = {uid for (uid,) in engagedUserRows}

                for uid in engagedUserIds:
                    # Monk — zero packs this season
                    packCount = session.query(func.count(PackOpening.id)).filter(
                        PackOpening.user_id == uid,
                    ).scalar() or 0
                    # Filter by season: PackOpening doesn't store season directly. We join
                    # via opened_at within this season, but simpler: check no pack_purchase
                    # transactions this season.
                    packTxCount = session.query(func.count(CurrencyTransaction.id)).filter(
                        CurrencyTransaction.user_id == uid,
                        CurrencyTransaction.season == season,
                        CurrencyTransaction.transaction_type == "pack_purchase",
                    ).scalar() or 0
                    if packTxCount == 0:
                        _am.unlockSecret(session, uid, "monk")

                    # Stalwart ("no roster swaps this season") is retired with the
                    # swap system — every user would trivially qualify, so it no
                    # longer auto-grants. (Existing holders keep it.)

                # Faithful — favorite team missed playoffs 3 seasons in a row (this + prior 2)
                if season >= 3:
                    userFavTeams = session.query(User.id, User.favorite_team_id).filter(
                        User.favorite_team_id.isnot(None),
                    ).all()
                    # Build a lookup of (team_id, season) -> made_playoffs for the relevant window
                    relevantSeasons = [season, season - 1, season - 2]
                    playoffRows = session.query(
                        TeamSeasonStats.team_id,
                        TeamSeasonStats.season,
                        TeamSeasonStats.made_playoffs,
                    ).filter(TeamSeasonStats.season.in_(relevantSeasons)).all()
                    playoffMap = {
                        (r.team_id, r.season): bool(r.made_playoffs)
                        for r in playoffRows
                    }
                    for uid, favTid in userFavTeams:
                        madeAny = any(
                            playoffMap.get((favTid, s), False) for s in relevantSeasons
                        )
                        haveAllSeasons = all(
                            (favTid, s) in playoffMap for s in relevantSeasons
                        )
                        if haveAllSeasons and not madeAny:
                            _am.unlockSecret(session, uid, "faithful")

                # Devotee — 100% team funding pct AND a season_end_tax contribution this season
                devoteeUsers = session.query(User.id).filter(
                    User.team_funding_pct == 100,
                    User.favorite_team_id.isnot(None),
                ).all()
                for (uid,) in devoteeUsers:
                    hasContribution = session.query(CurrencyTransaction.id).filter(
                        CurrencyTransaction.user_id == uid,
                        CurrencyTransaction.season == season,
                        CurrencyTransaction.transaction_type == "season_end_tax",
                        CurrencyTransaction.amount < 0,
                    ).first()
                    if hasContribution:
                        _am.unlockSecret(session, uid, "devotee")

                # Lifer — backed the same favorite team for 5+ full seasons.
                # Keyed off Supporter loyalty tenure (supporter_weeks), which
                # ticks one per regular-season week and soft-resets on a team change.
                from constants import SUPPORTER_WEEKS_PER_SEASON as _SWPS
                liferRows = session.query(User.id).filter(
                    User.supporter_weeks >= 5 * _SWPS,
                ).all()
                for (uid,) in liferRows:
                    _am.unlockSecret(session, uid, "lifer")

                session.commit()
            except Exception as e:
                session.rollback()
                logger.warning(f"Season-end secrets check failed: {e}")
            finally:
                session.close()
        except Exception as e:
            logger.warning(f"Season-end secrets setup failed: {e}")

    def _checkWeekEndSecrets(self, season: int, week: int) -> None:
        """Evaluate secret achievements that need week-end context (FP snapshot + pickem resolution).
        Runs after both fantasy and pick-em have been finalized for the week."""
        try:
            from database.connection import get_session
            from database.models import EquippedCard, PickEmPick, FantasyRoster, FantasyRosterPlayer
            from sqlalchemy import func
            from managers import achievementManager as _am

            fantasyTracker = self.serviceContainer.getService('fantasy_tracker')
            snapshot = fantasyTracker.getSnapshot(season) if fantasyTracker else {"entries": []}
            entries = snapshot.get("entries", [])
            # userId → weekTotal FP for this week
            weekFpByUser = {e["userId"]: e.get("weekTotal", 0) for e in entries}

            session = get_session()
            try:
                # Purist ("full roster with zero cards equipped") is impossible in the
                # fusion — the equipped cards ARE the roster — so the secret is retired
                # and no longer auto-grants. (Existing holders keep it.)

                # Zenith — Perfect Week AND 800+ FP in the same week.
                # Threshold rescaled with the Balatro pass (was 300 — trivial
                # now since Hedge alone floors at 675). 800 keeps the secret
                # tied to a strong-composition week, not just any active one.
                # Perfect Week = user had picks this week and all were correct.
                # Aggregate per user, then compare in Python (portable across DBs).
                from sqlalchemy import case
                pickAgg = session.query(
                    PickEmPick.user_id,
                    func.count(PickEmPick.id).label("total"),
                    func.sum(case((PickEmPick.correct == True, 1), else_=0)).label("correct"),
                ).filter(
                    PickEmPick.season == season,
                    PickEmPick.week == week,
                    PickEmPick.correct.isnot(None),
                ).group_by(PickEmPick.user_id).all()
                for uid, total, correct in pickAgg:
                    if total > 0 and correct == total and weekFpByUser.get(uid, 0) >= 800:
                        _am.unlockSecret(session, uid, "zenith")

                session.commit()
            except Exception as e:
                session.rollback()
                logger.warning(f"Week-end secrets check failed: {e}")
            finally:
                session.close()
        except Exception as e:
            logger.warning(f"Week-end secrets setup failed: {e}")

    def _resolvePickEmWeek(self, season: int, week: int) -> None:
        """Award Floobits and leaderboard prizes for the completed week.
        Individual game picks are already resolved by _resolvePickEmGame."""
        from constants import (
            PICKEM_CLAIRVOYANT_THRESHOLD, PICKEM_CLAIRVOYANT_BONUS,
            PICKEM_POINTS_TO_FLOOBITS,
            PICKEM_WEEKLY_PRIZES, PICKEM_WEEKLY_TOP_PCT,
            PICKEM_WEEKLY_TOP_PCT_PRIZE,
        )

        # Display label: "Week 14" for regular season, playoff round name for weeks 29+
        if week > 28:
            weekLabel = self.currentSeason.currentWeekText or f'Playoffs Round {week - 28}'
        else:
            weekLabel = f'Week {week}'

        # Get the just-completed games
        completedGames = self.currentSeason.completedWeekGames
        if not completedGames:
            return

        try:
            from database.connection import get_session
            from database.repositories.pickem_repository import PickEmRepository
            from database.repositories.card_repositories import CurrencyRepository
            from database.repositories.notification_repository import NotificationRepository

            session = get_session()
            try:
                pickemRepo = PickEmRepository(session)
                currencyRepo = CurrencyRepository(session)
                notifRepo = NotificationRepository(session)

                # Picks are already resolved per-game by _resolvePickEmGame.
                # Award points-based Floobits + Clairvoyant bonus
                userResults = pickemRepo.getWeekResultsByUser(season, week)
                # ⚠️ How many games there were to pick. Perfect Week and Jinx are both
                # "the WHOLE slate", and both were counting the reader's own picks
                # instead: Perfect Week fired on `correctCount == totalPicks` with no
                # floor, so one correct pick and nothing else was a perfect week (which
                # is why prod shows it completed 413 times), and Jinx hardcoded 12, the
                # old 24-club slate size, so at 32 clubs it can fire on 12 of 16.
                slateSize = len(completedGames)
                for userId, correctCount, totalPicks, totalPoints in userResults:
                    if totalPicks == 0:
                        continue
                    reward = int(totalPoints * PICKEM_POINTS_TO_FLOOBITS)
                    isClairvoyant = totalPoints >= PICKEM_CLAIRVOYANT_THRESHOLD
                    if isClairvoyant:
                        reward += PICKEM_CLAIRVOYANT_BONUS

                    if reward > 0:
                        currencyRepo.addFunds(
                            userId, reward, 'pickem_correct',
                            description=f'{weekLabel}: {totalPoints} pts ({correctCount}/{totalPicks} correct)',
                            season=season, week=week,
                        )

                    # Achievement hook — Sharp (Clairvoyant this season)
                    if isClairvoyant:
                        from managers import achievementManager as _am
                        _am.onClairvoyant(session, userId, season)

                    # Achievement hook — Perfect Week: every game on the slate, picked
                    # and correct. Not merely "everything you picked came in".
                    if slateSize > 0 and totalPicks >= slateSize and correctCount == totalPicks:
                        from managers import achievementManager as _am2
                        _am2.onPerfectPickEmWeek(session, userId, season)

                    # Achievement hook — Oracle tiers (cumulative season points)
                    try:
                        from managers import achievementManager as _am3
                        seasonPoints = pickemRepo.getUserSeasonStats(userId, season).get("totalPoints", 0) or 0
                        if seasonPoints > 0:
                            _am3.onSeasonPickemPointsTotal(session, userId, int(seasonPoints), season)
                    except Exception as _e:
                        logger.warning(f"Oracle hook failed: {_e}")

                    # Secret hook — Contrarian (every MANUAL pick this week was on an underdog).
                    # Auto-picks don't count either way: "auto_pick_mode = underdogs" would
                    # otherwise unlock this trivially every week.
                    try:
                        from database.models import PickEmPick as _PEP
                        from managers import achievementManager as _am4
                        userPicks = session.query(_PEP).filter(
                            _PEP.user_id == userId,
                            _PEP.season == season,
                            _PEP.week == week,
                        ).all()
                        # Require at least 2 picks, all manual, all on underdogs (multiplier > 1.0).
                        if len(userPicks) >= 2 and all(
                            not p.is_auto and (p.underdog_multiplier or 1.0) > 1.0
                            for p in userPicks
                        ):
                            _am4.unlockSecret(session, userId, "contrarian")
                        # Secret — Jinx: the FULL slate, all MANUAL, every one WRONG.
                        # The inverse of Perfect Week — rewards deliberately picking
                        # every loser. Auto-picks excluded (same as Contrarian) so an
                        # unlucky auto-picker on a chalk week doesn't unlock it. Sized
                        # off the slate, not a hardcoded 12, which was the 24-club count.
                        if slateSize > 0 and len(userPicks) >= slateSize and all(
                            (not p.is_auto) and (p.correct is False)
                            for p in userPicks
                        ):
                            _am4.unlockSecret(session, userId, "jinx")
                    except Exception as _e:
                        logger.warning(f"Contrarian hook failed: {_e}")

                    # 3. Notify each user
                    title = f'{weekLabel} Prognostications'
                    if isClairvoyant:
                        body = f'CLAIRVOYANT! {totalPoints} pts ({correctCount}/{totalPicks} correct) — +{reward} Floobits'
                    elif correctCount > 0:
                        body = f'{correctCount}/{totalPicks} correct — {totalPoints} pts — +{reward} Floobits'
                    else:
                        body = f'0/{totalPicks} correct this week. Better luck next time!'
                    notifRepo.create(
                        userId, 'pickem_results', title, body,
                        data={'season': season, 'week': week, 'correct': correctCount,
                              'total': totalPicks, 'totalPoints': totalPoints,
                              'reward': reward, 'clairvoyant': isClairvoyant},
                    )

                # 4. Award weekly pick-em leaderboard prizes (ranked by points)
                weekRows = pickemRepo.getWeekLeaderboard(season, week)
                totalEntries = len(weekRows)
                topCutoff = max(3, int(totalEntries * PICKEM_WEEKLY_TOP_PCT))

                for i, (userId, correctCount, totalPicks, totalPoints) in enumerate(weekRows):
                    weekRank = i + 1
                    if totalPoints <= 0:
                        continue
                    # Achievement hook — Pundit tiers (top-3 weekly pick-em finishes)
                    if weekRank <= 3:
                        try:
                            from managers import achievementManager as _am
                            _am.onWeeklyPickemPodium(session, userId, season)
                        except Exception as _e:
                            logger.warning(f"Pundit hook failed: {_e}")
                    prize = PICKEM_WEEKLY_PRIZES.get(weekRank)
                    if prize is None and weekRank <= topCutoff and totalEntries >= 4:
                        prize = PICKEM_WEEKLY_TOP_PCT_PRIZE
                    if not prize:
                        continue
                    currencyRepo.addFunds(
                        userId, prize, 'pickem_leaderboard_weekly',
                        description=f'{weekLabel} Prognostications #{weekRank}',
                        season=season, week=week,
                    )
                    notifRepo.create(
                        userId, 'pickem_leaderboard_weekly',
                        f'{weekLabel} Prognostications Leaderboard',
                        f'You placed #{weekRank} on the {weekLabel} Prognostications leaderboard! +{prize} Floobits',
                        data={'season': season, 'week': week, 'rank': weekRank, 'prize': prize},
                    )
                    logger.info(f"Pick-em weekly prize: user {userId} #{weekRank} = {prize} Floobits")

                session.commit()

                # 5. Broadcast pick-em results via WebSocket
                if BROADCASTING_AVAILABLE and broadcaster.is_enabled():
                    from database.models import User
                    leaderboardData = []
                    for userId, correctCount, totalPicks, totalPoints in weekRows[:10]:
                        dbUser = session.query(User).filter_by(id=userId).first()
                        username = dbUser.username if dbUser and dbUser.username else f"User {userId}"
                        leaderboardData.append({
                            "userId": userId, "username": username,
                            "correct": correctCount, "total": totalPicks,
                            "totalPoints": totalPoints,
                        })
                    pickemEvent = {
                        "event": "pickem_results",
                        "season": season,
                        "week": week,
                        "games": [
                            {"gameIndex": i, "winnerId": getattr(g, 'winningTeam', None).id}
                            for i, g in enumerate(completedGames)
                            if getattr(g, 'winningTeam', None) is not None
                        ],
                        "leaderboard": leaderboardData,
                    }
                    broadcaster.broadcast_sync('season', pickemEvent)

                logger.info(f"Pick-em resolved for S{season}W{week}: {len(userResults)} users")

            except Exception as e:
                session.rollback()
                logger.error(f"Error resolving pick-em for week {week}: {e}")
            finally:
                session.close()
        except ImportError:
            pass

    def _awardPickEmSeasonPrizes(self, completedSeason: int) -> None:
        """Award season-end pick-em leaderboard prizes."""
        from constants import (
            PICKEM_SEASON_PRIZES, PICKEM_SEASON_TOP_PCT,
            PICKEM_SEASON_TOP_PCT_PRIZE,
        )

        try:
            from database.connection import get_session
            from database.repositories.pickem_repository import PickEmRepository
            from database.repositories.card_repositories import CurrencyRepository
            from database.repositories.notification_repository import NotificationRepository

            session = get_session()
            try:
                # Idempotency: skip if already awarded for this season
                from database.models import CurrencyTransaction
                alreadyAwarded = session.query(CurrencyTransaction.id).filter_by(
                    transaction_type='pickem_leaderboard_season', season=completedSeason
                ).first()
                if alreadyAwarded:
                    logger.info(f"Season {completedSeason} pick-em prizes already awarded — skipping")
                    session.close()
                    return

                pickemRepo = PickEmRepository(session)
                currencyRepo = CurrencyRepository(session)
                notifRepo = NotificationRepository(session)

                seasonRows = pickemRepo.getSeasonLeaderboard(completedSeason)
                totalEntries = len(seasonRows)
                topCutoff = max(3, int(totalEntries * PICKEM_SEASON_TOP_PCT))

                for i, (userId, correctCount, totalPicks, totalPoints) in enumerate(seasonRows):
                    seasonRank = i + 1
                    if totalPoints <= 0:
                        continue
                    prize = PICKEM_SEASON_PRIZES.get(seasonRank)
                    if prize is None and seasonRank <= topCutoff and totalEntries >= 4:
                        prize = PICKEM_SEASON_TOP_PCT_PRIZE
                    if not prize:
                        continue
                    currencyRepo.addFunds(
                        userId, prize, 'pickem_leaderboard_season',
                        description=f'Season {completedSeason} Prognostications #{seasonRank}',
                        season=completedSeason,
                    )
                    notifRepo.create(
                        userId, 'pickem_leaderboard_season',
                        f'Season {completedSeason} Prognostications Champion',
                        f'You placed #{seasonRank} on the Season Prognostications leaderboard! +{prize} Floobits',
                        data={'season': completedSeason, 'rank': seasonRank, 'prize': prize},
                    )
                    logger.info(f"Pick-em season prize: user {userId} #{seasonRank} = {prize} Floobits")

                session.commit()
                logger.info(f"Pick-em season prizes awarded for season {completedSeason}")
            except Exception as e:
                session.rollback()
                logger.error(f"Error awarding pick-em season prizes: {e}")
            finally:
                session.close()
        except ImportError:
            pass

    # ─── Awards ────────────────────────────────────────────────────────────────

    async def _selectSeasonAllPro(self) -> None:
        """Select the All-Pro team for the current season: a single six-player
        squad (QB/RB/WR/WR/TE/K), the best player at each offensive slot by
        mvpScore — which already folds in their defensive value, since players
        play both ways. No separate defensive squad."""
        candidates = self.playerManager._computeMvpCandidates()
        if not candidates:
            logger.warning("Could not determine All-Pro — not enough eligible players")
            return
        seasonNum = self.currentSeason.seasonNumber

        # ── Offense: top value per offensive slot (WR gets 2) ──
        positionOrder = ['QB', 'RB', 'WR', 'WR', 'TE', 'K']
        positionSlots = {'QB': 1, 'RB': 1, 'WR': 2, 'TE': 1, 'K': 1}
        bestByPosition: dict = {}
        for c in candidates:
            pos = c['position']
            bestByPosition.setdefault(pos, [])
            if len(bestByPosition[pos]) < positionSlots.get(pos, 1):
                bestByPosition[pos].append(c)

        allProList = []
        for pos in dict.fromkeys(positionOrder):
            for pick in bestByPosition.get(pos, []):
                allProList.append({
                    'id': pick['id'], 'name': pick['name'],
                    'position': pick['position'], 'side': 'offense',
                    'value': round(float(pick.get('mvpScore', 0.0)), 2),
                    'team': pick['team'], 'teamAbbr': pick['teamAbbr'],
                    'teamColor': pick['teamColor'], 'teamId': pick['teamId'],
                    'ratingStars': pick['ratingStars'],
                    'seasonPerformanceRating': pick.get('seasonPerformanceRating'),
                    'mvpScore': pick.get('mvpScore'), 'zScore': pick.get('zScore'),
                })

        # Credit the All-Pro season on every honoree so the player profile shows
        # a single All-Pro accolade.
        for pid in {e['id'] for e in allProList}:
            playerObj = self._defenderById(pid)
            if playerObj is not None:
                if not getattr(playerObj, 'allProSeasons', None):
                    playerObj.allProSeasons = []
                if seasonNum not in playerObj.allProSeasons:
                    playerObj.allProSeasons.append(seasonNum)

        # Flat id union (cards/classification + resume) and the rich six-player
        # team for durable recap rebuild.
        self.currentSeason.allProPlayerIds = {e['id'] for e in allProList}
        self.currentSeason.allPro = allProList
        self.currentSeason.allProTeam = [
            {'id': e['id'], 'side': e['side'], 'position': e['position'], 'value': e['value']}
            for e in allProList
        ]

        allProNames = [f"{c['name']} ({c['position']})" for c in allProList]
        logger.info(f"Season {seasonNum} All-Pro: {', '.join(allProNames)}")

        allProText = f"Season {seasonNum} All-Pro Team: {', '.join(allProNames)}"
        self.currentSeason.leagueHighlights.insert(0, {'event': {'text': allProText}})
        if BROADCASTING_AVAILABLE and broadcaster.is_enabled():
            if LeagueNewsEvent:
                await broadcaster.broadcast_season_event(LeagueNewsEvent.leagueNews(allProText))
            if SeasonEvent:
                await broadcaster.broadcast_season_event(
                    SeasonEvent.allProAnnouncement(allProList, seasonNum)
                )

    def _defenderById(self, playerId: int):
        """Resolve an active player object by id across every roster position
        (QB/RB/WR/TE/K — the offense, which also doubles as the defense). Used
        to credit All-Pro honors after selection; kickers are All-Pro-eligible
        on offense even though they have no defensive position."""
        for grp in (self.playerManager.activeQbs, self.playerManager.activeRbs,
                    self.playerManager.activeWrs, self.playerManager.activeTes,
                    self.playerManager.activeKs):
            for p in grp:
                if p.id == playerId:
                    return p
        return None

    def _updateStandings(self) -> None:
        """Update league standings"""
        for league in self.leagueManager.leagues:
            league.getStandings()
    
    def updatePlayoffPicture(self) -> None:
        """Update playoff picture based on current standings (matches original Season.updatePlayoffPicture)"""
        if not self.currentSeason:
            return
            
        self.currentSeason.playoffTeams = {}
        nonPlayoffTeams = {}
        
        for league in self.leagueManager.leagues:
            # Sort teams by win percentage and score differential
            standings = league.getStandings()
            teams = [standing['team'] for standing in standings]
            
            # Split into playoff and non-playoff teams (half make playoffs)
            sliceIndex = len(teams) // 2
            playoffTeams = teams[:sliceIndex]
            nonPlayoffTeams_league = teams[sliceIndex:]
            
            self.currentSeason.playoffTeams[league.name] = playoffTeams
            nonPlayoffTeams[league.name] = nonPlayoffTeams_league
        
        # Store non-playoff teams for clinching logic
        self.currentSeason.nonPlayoffTeams = nonPlayoffTeams
    
    def checkForClinches(self) -> list:
        """Check for playoff clinches, top seed clinches, and eliminations mid-season.
        Delegates to leagueManager.checkPlayoffClinching() and returns new event texts to broadcast.
        """
        if not self.currentSeason:
            return []
        leagueHighlights = getattr(self.currentSeason, 'leagueHighlights', [])
        return self.leagueManager.checkPlayoffClinching(
            currentWeek=self.currentSeason.currentWeek,
            leagueHighlights=leagueHighlights
        )
    
    def saveSeasonStats(self) -> None:
        """Save season statistics to file (matches original Season.saveSeasonStats)"""
        if not self.currentSeason:
            return
            
        import json
        import os
        
        # Save season to database
        self._saveSeasonToDatabase()

        # Save team season stats to database
        self._saveTeamSeasonStatsToDatabase()

        # Save championships to Championship table
        self._saveChampionshipsToDatabase()
        
        # Accumulate season stats into all-time stats
        self._accumulateAllTimeStats()
        
        # Note: Season directories and JSON files disabled - data is in database
        # seasonDir = f'season{self.currentSeason.seasonNumber}'
        # if not os.path.exists(seasonDir):
        #     os.makedirs(seasonDir)
        
        # Save standings history
        standingsData = {}
        for league in self.leagueManager.leagues:
            standings = league.getStandings()
            standingsData[league.name] = []
            
            for standing in standings:
                team = standing['team']
                teamData = {
                    'name': f"{team.city} {team.name}",
                    'wins': standing['wins'],
                    'losses': standing['losses'],
                    'winPct': standing['winPct'],
                    'id': team.id
                }
                standingsData[league.name].append(teamData)
        
        # Note: Standings and highlights are now stored in the database, JSON output disabled
        # standingsFile = os.path.join(seasonDir, 'standings.json')
        # try:
        #     with open(standingsFile, 'w') as f:
        #         json.dump(standingsData, f, indent=4)
        #     logger.info(f"Saved season {self.currentSeason.seasonNumber} standings")
        # except Exception as e:
        #     logger.error(f"Failed to save standings: {e}")
        # 
        # if hasattr(self.currentSeason, 'leagueHighlights') and self.currentSeason.leagueHighlights:
        #     highlightsFile = os.path.join(seasonDir, 'highlights.json')
        #     try:
        #         from serializers import serialize_object
        #         serializedHighlights = serialize_object(self.currentSeason.leagueHighlights)
        #         with open(highlightsFile, 'w') as f:
        #             json.dump(serializedHighlights, f, indent=4)
        #         logger.info(f"Saved season {self.currentSeason.seasonNumber} highlights")
        #     except Exception as e:
        #         logger.error(f"Failed to save highlights: {e}")
    
    def _saveSeasonToDatabase(self) -> None:
        """Save season record to database"""
        if not DB_IMPORTS_AVAILABLE or not USE_DATABASE or not self.db_session:
            return
            
        try:
            from database.models import Season as DBSeason
            
            # Create or update season record
            db_season = self.db_session.query(DBSeason).filter_by(season_number=self.currentSeason.seasonNumber).first()
            
            if not db_season:
                db_season = DBSeason(
                    season_number=self.currentSeason.seasonNumber,
                    start_date=getattr(self.currentSeason, 'startDate', None),
                    current_week=self.currentSeason.currentWeek if isinstance(self.currentSeason.currentWeek, int) else 1,
                    playoffs_started=getattr(self.currentSeason, 'playoffsStarted', False)
                )
            else:
                db_season.current_week = self.currentSeason.currentWeek if isinstance(self.currentSeason.currentWeek, int) else 1
                db_season.playoffs_started = getattr(self.currentSeason, 'playoffsStarted', False)
                db_season.end_date = datetime.datetime.now()
            
            # Set champion team ID + snapshot the championship roster NOW, before the
            # offseason churns it — the Champion classification + pack must reflect who
            # actually won, not whoever is on the team next season.
            if hasattr(self.currentSeason, 'champion') and self.currentSeason.champion:
                db_season.champion_team_id = self.currentSeason.champion.id
                try:
                    import json as _jsonChamp
                    champRosterIds = [p.id for p in self.currentSeason.champion.rosterDict.values()
                                      if p and getattr(p, 'id', None) is not None]
                    db_season.champion_player_ids = _jsonChamp.dumps(champRosterIds)
                except Exception as _e:
                    logger.warning(f"Could not snapshot champion roster: {_e}")

            # Persist MVP and All-Pro for classification lookups on resume
            mvpData = getattr(self.currentSeason, 'mvp', None)
            if mvpData and isinstance(mvpData, dict) and mvpData.get('id'):
                db_season.mvp_player_id = mvpData['id']
            allProIds = getattr(self.currentSeason, 'allProPlayerIds', None)
            if allProIds:
                import json
                db_season.all_pro_player_ids = json.dumps(list(allProIds))
            allProTeam = getattr(self.currentSeason, 'allProTeam', None)
            if allProTeam:
                import json
                db_season.all_pro_team = json.dumps(allProTeam)

            mvpBallot = getattr(self.currentSeason, 'mvpBallot', None)
            if mvpBallot:
                import json
                db_season.mvp_ballot = json.dumps(mvpBallot)

            self.db_session.add(db_season)
            self.db_session.commit()
            logger.info(f"Saved season {self.currentSeason.seasonNumber} to database")
            
        except Exception as e:
            logger.error(f"Failed to save season to database: {e}")
            self.db_session.rollback()
    
    def _saveTeamSeasonStatsToDatabase(self) -> None:
        """Save team season stats to database including ELO"""
        if not DB_IMPORTS_AVAILABLE or not USE_DATABASE or not self.db_session:
            return
            
        try:
            from database.models import TeamSeasonStats as DBTeamSeasonStats
            
            teamManager = self.serviceContainer.getService('team_manager')
            if not teamManager:
                return
            
            for team in teamManager.teams:
                if not hasattr(team, 'seasonTeamStats'):
                    continue
                
                stats = team.seasonTeamStats
                
                # Create or update team season stats
                db_stats = self.db_session.query(DBTeamSeasonStats).filter_by(
                    team_id=team.id,
                    season=self.currentSeason.seasonNumber
                ).first()
                
                if not db_stats:
                    db_stats = DBTeamSeasonStats(
                        team_id=team.id,
                        season=self.currentSeason.seasonNumber
                    )
                
                # Update stats
                db_stats.elo = stats.get('elo', getattr(team, 'elo', 1500))
                db_stats.wins = stats.get('wins', 0)
                db_stats.losses = stats.get('losses', 0)
                db_stats.win_percentage = stats.get('winPerc', 0.0)
                db_stats.streak = stats.get('streak', 0)
                db_stats.score_differential = stats.get('scoreDiff', 0)
                db_stats.made_playoffs = stats.get('madePlayoffs', False)
                db_stats.league_champion = stats.get('leagueChamp', False)
                db_stats.floosball_champion = stats.get('floosbowlChamp', False)
                db_stats.top_seed = stats.get('topSeed', False)
                
                # Denormalized offensive stats
                offense = stats.get('Offense', {})
                db_stats.points = offense.get('pts', 0)
                db_stats.touchdowns = offense.get('tds', 0)
                db_stats.field_goals = offense.get('fgs', 0)
                db_stats.total_yards = offense.get('totalYards', 0)
                db_stats.passing_yards = offense.get('passYards', 0)
                db_stats.rushing_yards = offense.get('runYards', 0)
                db_stats.passing_tds = offense.get('passTds', 0)
                db_stats.rushing_tds = offense.get('runTds', 0)
                
                # Denormalized defensive stats
                defense = stats.get('Defense', {})
                db_stats.points_allowed = defense.get('ptsAlwd', 0)
                db_stats.sacks = defense.get('sacks', 0)
                db_stats.interceptions = defense.get('ints', 0)
                db_stats.fumbles_recovered = defense.get('fumRec', 0)
                db_stats.total_yards_allowed = defense.get('totalYardsAlwd', 0)

                # Big plays — persisted so Highlight Reel's per-game
                # average survives backend restarts.
                db_stats.big_plays = stats.get('bigPlays', 0)

                # Peak streak — persisted so Gone Streaking survives
                # restarts. peakStreak is the longest win-or-loss run
                # (abs value) seen this season.
                db_stats.peak_streak = stats.get('peakStreak', 0)

                # JSON for detailed breakdown
                db_stats.offense_stats = stats.get('Offense', {})
                db_stats.defense_stats = stats.get('Defense', {})
                
                self.db_session.add(db_stats)
            
            self.db_session.commit()
            logger.info(f"Saved team season stats for season {self.currentSeason.seasonNumber}")
            
        except Exception as e:
            logger.error(f"Failed to save team season stats: {e}")
            self.db_session.rollback()
    
    def _saveChampionshipsToDatabase(self) -> None:
        """Save championships to Championship table for efficient querying"""
        if not DB_IMPORTS_AVAILABLE or not USE_DATABASE or not self.db_session:
            return
            
        try:
            from database.models import Championship as DBChampionship
            
            teamManager = self.serviceContainer.getService('team_manager')
            if not teamManager:
                return
            
            # One loop over (attribute, championship_type) instead of four near-identical
            # blocks — the copy-paste version is where a new title type gets half-added.
            TITLE_KINDS = (
                ('topSeeds', 'regular_season'),
                ('divisionTitles', 'division'),
                ('leagueChampionships', 'league'),
                ('floosbowlChampionships', 'floosbowl'),
            )
            for team in teamManager.teams:
                for attr, kind in TITLE_KINDS:
                    for season_str in (getattr(team, attr, None) or []):
                        try:
                            season_num = int(str(season_str).replace('Season ', ''))
                        except ValueError:
                            continue
                        existing = self.db_session.query(DBChampionship).filter_by(
                            team_id=team.id, season=season_num, championship_type=kind,
                        ).first()
                        if not existing:
                            self.db_session.add(DBChampionship(
                                team_id=team.id, season=season_num,
                                championship_type=kind,
                            ))

            self.db_session.commit()
            logger.info(f"Saved championships for season {self.currentSeason.seasonNumber}")
            
        except Exception as e:
            logger.error(f"Failed to save championships: {e}")
            self.db_session.rollback()
    
    def _accumulateAllTimeStats(self) -> None:
        """Accumulate season stats into all-time stats (matches legacy floosball_legacy.py lines 459-469)"""
        teamManager = self.serviceContainer.getService('team_manager')
        if not teamManager:
            return
        
        for team in teamManager.teams:
            if not hasattr(team, 'seasonTeamStats') or not hasattr(team, 'allTimeTeamStats'):
                continue
            
            # Accumulate stats from season into all-time
            team.allTimeTeamStats['wins'] += team.seasonTeamStats['wins']
            team.allTimeTeamStats['losses'] += team.seasonTeamStats['losses']
            team.allTimeTeamStats['Offense']['tds'] += team.seasonTeamStats['Offense']['tds']
            team.allTimeTeamStats['Offense']['fgs'] += team.seasonTeamStats['Offense']['fgs']
            team.allTimeTeamStats['Offense']['passYards'] += team.seasonTeamStats['Offense']['passYards']
            team.allTimeTeamStats['Offense']['runYards'] += team.seasonTeamStats['Offense']['runYards']
            team.allTimeTeamStats['Offense']['totalYards'] += team.seasonTeamStats['Offense']['totalYards']
            team.allTimeTeamStats['Defense']['sacks'] += team.seasonTeamStats['Defense']['sacks']
            team.allTimeTeamStats['Defense']['ints'] += team.seasonTeamStats['Defense']['ints']
            team.allTimeTeamStats['Defense']['fumRec'] += team.seasonTeamStats['Defense']['fumRec']
            
            # Calculate all-time win percentage
            total_games = team.allTimeTeamStats['wins'] + team.allTimeTeamStats['losses']
            if total_games > 0:
                team.allTimeTeamStats['winPerc'] = round(team.allTimeTeamStats['wins'] / total_games, 3)
        
        logger.info("Accumulated season stats into all-time stats")
    
    def advanceToNextSeason(self) -> None:
        """Move to next season"""
        if self.currentSeason:
            self.currentSeason = None
        
        logger.info("Advanced to next season")
    
    def clearPlayerSeasonStats(self) -> None:
        """Clear and archive player season stats (matches original Season.clearPlayerSeasonStats)"""
        import copy
        
        for player in self.playerManager.activePlayers:
            if player.seasonsPlayed > 0:
                # Set final rating for the season
                player.seasonStatsDict['rating'] = player.playerTier.value
                
                # Archive the season stats
                seasonStatsCopy = copy.deepcopy(player.seasonStatsDict)
                
                # Remove old archive entry and insert new one at beginning
                if hasattr(player, 'seasonStatsArchive') and player.seasonStatsArchive:
                    player.seasonStatsArchive.pop(0)
                player.seasonStatsArchive.insert(0, seasonStatsCopy)
                
                # Reset season stats to default
                import floosball_player as FloosPlayer
                if hasattr(FloosPlayer, 'playerStatsDict'):
                    player.seasonStatsDict = copy.deepcopy(FloosPlayer.playerStatsDict)
                else:
                    # Default reset if playerStatsDict not available
                    player.seasonStatsDict = {
                        'passing': {'att': 0, 'comp': 0, 'yards': 0, 'tds': 0, 'ints': 0},
                        'rushing': {'carries': 0, 'yards': 0, 'tds': 0, 'fumblesLost': 0},
                        'receiving': {'targets': 0, 'receptions': 0, 'yards': 0, 'tds': 0},
                        'kicking': {'fgAtt': 0, 'fgs': 0, 'xpAtt': 0, 'xps': 0, 'fgYards': 0},
                        'defense': {'tackles': 0, 'sacks': 0, 'interceptions': 0, 'fumbleRecoveries': 0},
                        'fantasyPoints': 0,
                        'team': '',
                        'season': 0,
                        'rating': 0,
                        'gp': 0
                    }
                
                # Reset games played
                player.gamesPlayed = 0
        
        logger.info("Cleared player season stats")
    
    def clearTeamSeasonStats(self) -> None:
        """Clear and archive team season stats (matches original Season.clearTeamSeasonStats)"""
        import copy
        
        for team in self.leagueManager.teams:
            # Archive current season stats
            if hasattr(team, 'seasonTeamStats'):
                # Set final values
                team.seasonTeamStats['elo'] = getattr(team, 'elo', 1500)
                team.seasonTeamStats['overallRating'] = getattr(team, 'overallRating', 80)
                
                # Archive the stats (skip empty defaults with no game data)
                if not hasattr(team, 'statArchive'):
                    team.statArchive = []
                hasGameData = team.seasonTeamStats.get('wins', 0) > 0 or team.seasonTeamStats.get('losses', 0) > 0
                if hasGameData:
                    team.statArchive.insert(0, team.seasonTeamStats.copy())
                
                # Reset season stats
                import floosball_team as FloosTeam
                if hasattr(FloosTeam, 'teamStatsDict'):
                    team.seasonTeamStats = copy.deepcopy(FloosTeam.teamStatsDict)
                else:
                    # Default reset if teamStatsDict not available
                    team.seasonTeamStats = {
                        'wins': 0,
                        'losses': 0,
                        'winPerc': 0.0,
                        'scoreDiff': 0,
                        'season': 0,
                        'Offense': {'totalYards': 0, 'tds': 0, 'pts': 0},
                        'Defense': {'ints': 0, 'fumRec': 0, 'sacks': 0}
                    }
            
            # Clear schedule
            if hasattr(team, 'schedule'):
                team.schedule = []
        
        logger.info("Cleared team season stats")
    
    def getSeasonStats(self) -> Dict[str, Any]:
        """Get current season statistics"""
        if not self.currentSeason:
            return {}
        
        stats = {
            'seasonNumber': self.currentSeason.seasonNumber,
            'currentWeek': self.currentSeason.currentWeek,
            'totalGames': len(self.currentSeason.schedule),
            'completedGames': len([g for g in self.currentSeason.schedule if g['completed']]),
            'isComplete': self.currentSeason.isComplete,
            'champion': self.currentSeason.champion.name if self.currentSeason.champion else None,
            'leagueChampions': {k: v.name for k, v in self.currentSeason.leagueChampions.items()}
        }
        
        return stats
    
    def getCurrentSeason(self) -> Optional[Season]:
        """Get current season object"""
        return self.currentSeason
    
    def getSeasonHistory(self) -> List[Season]:
        """Get all completed seasons"""
        return self.seasonHistory