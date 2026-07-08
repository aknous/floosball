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

    def _respectsScoreOrder(self, field: str, value, gameRules) -> bool:
        """Enforce the invariant TOUCHDOWN > FIELD GOAL: a proposed field-goal value
        must stay strictly below the current touchdown value, and a proposed touchdown
        value strictly above the current field-goal value. (Reverts move toward the
        defaults 6/3, which already satisfy this given the candidate ranges.)"""
        if field == 'fieldGoalPoints':
            return value < float(getattr(gameRules, 'touchdownPoints', 6))
        if field == 'touchdownPoints':
            return value > float(getattr(gameRules, 'fieldGoalPoints', 3))
        return True

    def _pickProposedValue(self, field: str, current, gameRules):
        """Choose a specific CHANGE value for a field from its alternate space —
        always different from the current value AND the default (so a change moves a
        rule to a genuinely new value; returning to default is REVERT's job), and
        always keeping TD > FG. Returns None if no such value exists (e.g. a bool
        already flipped off, or no in-range value keeps TD above FG)."""
        import game_rules as gr
        from constants import RULE_VOTE_CANDIDATES
        spec = RULE_VOTE_CANDIDATES.get(field, {})
        default = gr.defaultRuleValue(field)
        if 'values' in spec:
            pool = [v for v in spec['values']
                    if v != current and v != default
                    and self._respectsScoreOrder(field, v, gameRules)]
            return random.choice(pool) if pool else None
        rng = spec.get('range')
        if not rng:
            return None
        lo, hi = rng
        isFloat = bool(spec.get('float'))
        for _ in range(30):
            if isFloat and random.random() < 0.5:
                v = round(random.uniform(lo, hi), 1)      # e.g. 6.4
            else:
                v = random.randint(int(lo), int(hi))       # e.g. 5
            if v != current and v != default and self._respectsScoreOrder(field, v, gameRules):
                return v
        return None

    def _changeOptions(self, gameRules) -> List[dict]:
        """Candidate {field, value} pairs available for a CHANGE vote — includes
        already-changed fields that can move to a NEW value, not just default ones."""
        from constants import RULE_VOTE_CANDIDATES
        out = []
        for f in RULE_VOTE_CANDIDATES:
            v = self._pickProposedValue(f, getattr(gameRules, f, None), gameRules)
            if v is not None:
                out.append({"field": f, "value": v})
        return out

    def _revertOptions(self, gameRules) -> List[dict]:
        """Candidate {field, value=default} pairs for a REVERT vote — fields currently
        away from their default."""
        import game_rules as gr
        from constants import RULE_VOTE_CANDIDATES
        out = []
        for f in RULE_VOTE_CANDIDATES:
            default = gr.defaultRuleValue(f)
            if getattr(gameRules, f, None) != default:
                out.append({"field": f, "value": default})
        return out

    def _changedCount(self, gameRules) -> int:
        import game_rules as gr
        from constants import RULE_VOTE_CANDIDATES
        return sum(1 for f in RULE_VOTE_CANDIDATES
                   if getattr(gameRules, f, None) != gr.defaultRuleValue(f))

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
            changeOpts = self._changeOptions(gameRules)
            revertOpts = self._revertOptions(gameRules)
            canChange = len(changeOpts) > 0
            canRevert = len(revertOpts) >= RULE_VOTE_REVERT_GATE
            if canRevert and canChange:
                kind = 'revert' if random.random() < 0.5 else 'change'
            elif canChange:
                kind = 'change'
            elif revertOpts:
                kind = 'revert'  # nothing left to change; offer a revert instead
            else:
                repo.recordDay(season, dayIndex, fired=False)
                session.commit()
                logger.info(f"Rule vote: S{season} day {dayIndex} fired but no candidates")
                return

            pool = list(revertOpts if kind == 'revert' else changeOpts)
            random.shuffle(pool)
            options = pool[:RULE_VOTE_BALLOT_SIZE]

            from managers.coresManager import ruleVoteConversation
            convo = ruleVoteConversation(kind)

            openedAt = datetime.datetime.utcnow()
            closesAt = (weekStartTime - datetime.timedelta(minutes=RULE_VOTE_CLOSE_LEAD_MINUTES)
                        if weekStartTime is not None else None)

            window = repo.recordDay(
                season, dayIndex, fired=True, kind=kind, core=convo['core'],
                options=options, promptLine=convo['prompt'],
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
            specs = repo.optionSpecsOf(window)
            options = [s["field"] for s in specs]
            tally = repo.tally(window.id)
            winner = self._pickWinner(options, tally)

            applied = False
            prevValue = newValue = None
            if winner != 'none' and winner in options:
                import game_rules as gr
                prevValue = getattr(gameRules, winner, None)
                if window.kind == 'revert':
                    gr.revertRule(gameRules, winner, reason="pyre revert vote",
                                  source="cores_vote")
                else:
                    value = next((s["value"] for s in specs if s["field"] == winner), None)
                    gr.applyRuleChange(gameRules, winner, value, reason="aris change vote",
                                       source="cores_vote")
                newValue = getattr(gameRules, winner, None)
                applied = True

            repo.resolveWindow(window.id, winnerKey=winner, applied=applied,
                               prevValue=prevValue, newValue=newValue)
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
