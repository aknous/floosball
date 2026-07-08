"""Cores rule-change vote — trigger, ballot, resolution (docs/RULE_CHANGES_PLAN.md).

Encapsulates the domain logic so seasonManager only makes two thin hook calls:
  - maybeOpenWindow(): at the start of a game day (weeks 1/8/15/22) roll the
    escalating chance a vote fires; if it does, open a window (Aris CHANGE or Pyre
    REVERT), pick the Core's conversation lines, and announce it.
  - resolveOpenWindow(): 15 min before the day's first game, tally the vote, apply
    the most-voted rule (or none), and announce the outcome.

Most-voted wins, no quorum. Applied changes drift across seasons until reverted.
"""

import datetime
import os
import random
from typing import List, Optional

from logger_config import get_logger

logger = get_logger('floosball.rulevote')

# Weeks that begin a game day (day index = (week-1)//7).
GAME_DAY_START_WEEKS = (1, 8, 15, 22)


class RuleVoteManager:
    def __init__(self, serviceContainer=None):
        self.serviceContainer = serviceContainer

    # ── helpers ──────────────────────────────────────────────────────────────
    def dayIndexForWeek(self, week: int) -> int:
        return (week - 1) // 7  # 0..3

    def _repo(self, session):
        from database.repositories.rule_vote_repository import RuleVoteRepository
        return RuleVoteRepository(session)

    def _changedFields(self, gameRules) -> List[str]:
        """Candidate fields currently at their alternate (i.e. changed from default)."""
        import game_rules as gr
        from constants import RULE_VOTE_CANDIDATES
        return [f for f in RULE_VOTE_CANDIDATES
                if getattr(gameRules, f, None) != gr.defaultRuleValue(f)]

    def _defaultFields(self, gameRules) -> List[str]:
        """Candidate fields currently at their default (available for a CHANGE vote)."""
        import game_rules as gr
        from constants import RULE_VOTE_CANDIDATES
        return [f for f in RULE_VOTE_CANDIDATES
                if getattr(gameRules, f, None) == gr.defaultRuleValue(f)]

    # ── open ─────────────────────────────────────────────────────────────────
    def maybeOpenWindow(self, season: int, week: int, gameRules,
                        weekStartTime: Optional[datetime.datetime] = None) -> None:
        from constants import (RULE_VOTE_ENABLED, RULE_VOTE_RAMP, RULE_VOTE_REVERT_GATE,
                               RULE_VOTE_BALLOT_SIZE, RULE_VOTE_CLOSE_LEAD_MINUTES)
        if not RULE_VOTE_ENABLED or week not in GAME_DAY_START_WEEKS:
            return
        dayIndex = self.dayIndexForWeek(week)
        from database.connection import get_session
        session = get_session()
        try:
            repo = self._repo(session)
            if repo.hasWindow(season, dayIndex):
                return  # this game day already processed (idempotent on restart)

            # Escalation: chance ramps with consecutive prior game-days this season
            # that didn't fire; guaranteed once three in a row have missed.
            maxFired = repo.maxFiredDayIndex(season)
            misses = dayIndex - ((maxFired + 1) if maxFired is not None else 0)
            misses = max(0, min(misses, len(RULE_VOTE_RAMP) - 1))
            prob = RULE_VOTE_RAMP[misses]
            if random.random() >= prob:
                repo.recordDay(season, dayIndex, fired=False)
                session.commit()
                logger.info(f"Rule vote: S{season} day {dayIndex} did not fire (p={prob:.2f})")
                return

            # Pick kind. Below the revert gate it's always a CHANGE; at/above it's a
            # 50/50 coin flip, with guards for empty pools on either side.
            changed = self._changedFields(gameRules)
            defaults = self._defaultFields(gameRules)
            canChange = len(defaults) > 0
            canRevert = len(changed) >= RULE_VOTE_REVERT_GATE
            if canRevert and canChange:
                kind = 'revert' if random.random() < 0.5 else 'change'
            elif canChange:
                kind = 'change'
            elif changed:
                kind = 'revert'  # nothing left to change; offer a revert instead
            else:
                repo.recordDay(season, dayIndex, fired=False)
                session.commit()
                logger.info(f"Rule vote: S{season} day {dayIndex} fired but no candidates")
                return

            pool = list(changed if kind == 'revert' else defaults)
            random.shuffle(pool)
            options = pool[:RULE_VOTE_BALLOT_SIZE]

            from managers.coresManager import ruleVoteConversation
            convo = ruleVoteConversation(kind)

            openedAt = datetime.datetime.utcnow()
            closesAt = (weekStartTime - datetime.timedelta(minutes=RULE_VOTE_CLOSE_LEAD_MINUTES)
                        if weekStartTime is not None else None)

            window = repo.recordDay(
                season, dayIndex, fired=True, kind=kind, core=convo['core'],
                optionKeys=options, promptLine=convo['prompt'],
                reactPickLine=convo['reactPick'], reactNoneLine=convo['reactNone'],
                openedAt=openedAt, closesAt=closesAt,
            )
            session.commit()
            logger.info(f"Rule vote OPEN: S{season} day {dayIndex} kind={kind} "
                        f"options={options} closes={closesAt}")

            # Announce it in the feed (Aris for change, Pyre for revert).
            self._broadcast(f'rule_vote_open_{kind}', session, season, week)
        except Exception as e:
            logger.warning(f"Rule vote open failed: {e}")
        finally:
            session.close()

    # ── resolve ──────────────────────────────────────────────────────────────
    def resolveOpenWindow(self, season: int, gameRules) -> Optional[str]:
        """Resolve the season's open vote (most-voted wins). Applies the winner to
        the live rules + persists it, and announces the outcome. Returns the winner
        key ('none' or a field), or None if there was nothing to resolve."""
        if not self._enabled():
            return None
        from database.connection import get_session
        session = get_session()
        try:
            repo = self._repo(session)
            window = repo.getOpenWindow(season)
            if window is None:
                return None
            options = repo.optionsOf(window)
            tally = repo.tally(window.id)
            winner = self._pickWinner(options, tally)

            applied = False
            if winner != 'none' and winner in options:
                import game_rules as gr
                from constants import RULE_VOTE_CANDIDATES
                if window.kind == 'revert':
                    gr.revertRule(gameRules, winner, reason="pyre revert vote",
                                  source="cores_vote")
                else:
                    alt = RULE_VOTE_CANDIDATES.get(winner, {}).get('alternate')
                    gr.applyRuleChange(gameRules, winner, alt, reason="aris change vote",
                                       source="cores_vote")
                applied = True

            repo.resolveWindow(window.id, winnerKey=winner, applied=applied)
            session.commit()
            logger.info(f"Rule vote RESOLVE: S{season} day {window.day_index} "
                        f"kind={window.kind} winner={winner} applied={applied} tally={tally}")

            # Announce the outcome (kind + whether anything happened).
            if window.kind == 'revert':
                event = 'rule_reverted' if applied else 'rule_revert_none'
            else:
                event = 'rule_change_applied' if applied else 'rule_change_none'
            self._broadcast(event, session, season, self._weekForDay(window.day_index))
            return winner
        except Exception as e:
            logger.warning(f"Rule vote resolve failed: {e}")
            return None
        finally:
            session.close()

    def _pickWinner(self, options: List[str], tally: dict) -> str:
        """Most-voted option. A tie for the lead, no votes, or 'none' leading all
        resolve to no change. RULE_VOTE_SIM_AUTOPICK breaks a zero-vote tie by
        random-picking a field (headless engine testing only)."""
        total = sum(tally.values()) if tally else 0
        if total == 0:
            if os.environ.get('RULE_VOTE_SIM_AUTOPICK') and options:
                return random.choice(options)
            return 'none'
        # Consider every option plus 'none'.
        keys = list(options) + ['none']
        best = max(tally.get(k, 0) for k in keys)
        leaders = [k for k in keys if tally.get(k, 0) == best]
        if len(leaders) != 1:
            return 'none'      # tie -> no change
        return leaders[0]

    # ── plumbing ─────────────────────────────────────────────────────────────
    def _enabled(self) -> bool:
        from constants import RULE_VOTE_ENABLED
        return bool(RULE_VOTE_ENABLED)

    def _weekForDay(self, dayIndex: int) -> int:
        return dayIndex * 7 + 1

    def _broadcast(self, eventType: str, session, season: int, week: int) -> None:
        try:
            from managers.coresManager import entriesForEvent
            from managers.anomalyManager import _broadcastCoreEntries
            entries = entriesForEvent(eventType)
            _broadcastCoreEntries(entries, session=session, seasonNumber=season, week=week)
        except Exception as e:
            logger.warning(f"Rule vote broadcast ({eventType}) failed: {e}")
