"""Repository for the Cores rule-change vote (docs/RULE_CHANGES_PLAN.md).

One RuleVoteWindow per (season, game day) — recorded whether or not a vote fired,
so the daily escalation roll stays idempotent on restart. RuleVote is one free,
changeable pick per (user, window). Most-voted wins; no quorum. Mirrors the
lightweight, cost-free style of AwardVoteRepository.
"""

import json
from typing import Dict, List, Optional

from sqlalchemy.orm import Session
from sqlalchemy import func

from database.models import RuleVoteWindow, RuleVote


class RuleVoteRepository:
    def __init__(self, session: Session):
        self.session = session

    # ── Windows ──────────────────────────────────────────────────────────────
    def getWindow(self, season: int, dayIndex: int) -> Optional[RuleVoteWindow]:
        return (
            self.session.query(RuleVoteWindow)
            .filter(RuleVoteWindow.season == season,
                    RuleVoteWindow.day_index == dayIndex)
            .first()
        )

    def hasWindow(self, season: int, dayIndex: int) -> bool:
        """True if this game day has already been processed (fired or not)."""
        return self.getWindow(season, dayIndex) is not None

    def recordDay(self, season: int, dayIndex: int, fired: bool,
                  kind: Optional[str] = None, core: Optional[str] = None,
                  optionKeys: Optional[List[str]] = None,
                  promptLine: Optional[str] = None,
                  reactPickLine: Optional[str] = None,
                  reactNoneLine: Optional[str] = None,
                  openedAt=None, closesAt=None) -> RuleVoteWindow:
        """Record the per-day escalation outcome. A non-fired day is a bare marker;
        a fired day carries the live vote (kind/core/options/conversation/timing)."""
        window = RuleVoteWindow(
            season=season, day_index=dayIndex, fired=fired,
            kind=kind, core=core,
            option_keys=json.dumps(optionKeys) if optionKeys is not None else None,
            prompt_line=promptLine, react_pick_line=reactPickLine,
            react_none_line=reactNoneLine,
            opened_at=openedAt, closes_at=closesAt,
        )
        self.session.add(window)
        self.session.flush()
        return window

    def maxFiredDayIndex(self, season: int) -> Optional[int]:
        """Highest game-day index that fired a vote this season (for the escalation
        ramp: misses = dayIndex - (this + 1)). None if none fired yet."""
        row = (
            self.session.query(func.max(RuleVoteWindow.day_index))
            .filter(RuleVoteWindow.season == season,
                    RuleVoteWindow.fired.is_(True))
            .first()
        )
        return row[0] if row and row[0] is not None else None

    def countChangedFires(self, season: int) -> int:
        """Number of fired windows this season (any kind) — informational."""
        return (
            self.session.query(func.count(RuleVoteWindow.id))
            .filter(RuleVoteWindow.season == season,
                    RuleVoteWindow.fired.is_(True))
            .scalar()
        ) or 0

    def getOpenWindow(self, season: int) -> Optional[RuleVoteWindow]:
        """The season's currently-open vote (fired, not yet resolved), if any."""
        return (
            self.session.query(RuleVoteWindow)
            .filter(RuleVoteWindow.season == season,
                    RuleVoteWindow.fired.is_(True),
                    RuleVoteWindow.resolved.is_(False))
            .order_by(RuleVoteWindow.day_index.desc())
            .first()
        )

    def getWindowById(self, windowId: int) -> Optional[RuleVoteWindow]:
        return self.session.get(RuleVoteWindow, windowId)

    def resolveWindow(self, windowId: int, winnerKey: str, applied: bool) -> None:
        window = self.session.get(RuleVoteWindow, windowId)
        if window is not None:
            window.resolved = True
            window.winner_key = winnerKey
            window.applied = applied
            self.session.flush()

    def lastResolvedApplied(self, season: int) -> Optional[RuleVoteWindow]:
        """Most recent resolved window that actually applied a change (drives the
        Rulebook pill's 'what changed' line)."""
        return (
            self.session.query(RuleVoteWindow)
            .filter(RuleVoteWindow.season == season,
                    RuleVoteWindow.applied.is_(True))
            .order_by(RuleVoteWindow.day_index.desc())
            .first()
        )

    @staticmethod
    def optionsOf(window: RuleVoteWindow) -> List[str]:
        """Decode a window's offered candidate field keys."""
        if not window or not window.option_keys:
            return []
        try:
            return list(json.loads(window.option_keys))
        except Exception:
            return []

    # ── Votes ────────────────────────────────────────────────────────────────
    def castVote(self, userId: int, windowId: int, optionKey: str) -> RuleVote:
        """Set (or replace) this user's single pick for the window. Free + changeable."""
        existing = (
            self.session.query(RuleVote)
            .filter(RuleVote.user_id == userId, RuleVote.window_id == windowId)
            .first()
        )
        if existing:
            existing.option_key = optionKey
            self.session.flush()
            return existing
        vote = RuleVote(user_id=userId, window_id=windowId, option_key=optionKey)
        self.session.add(vote)
        self.session.flush()
        return vote

    def withdrawVote(self, userId: int, windowId: int) -> None:
        self.session.query(RuleVote).filter(
            RuleVote.user_id == userId, RuleVote.window_id == windowId
        ).delete()
        self.session.flush()

    def getUserVote(self, userId: int, windowId: int) -> Optional[str]:
        row = (
            self.session.query(RuleVote.option_key)
            .filter(RuleVote.user_id == userId, RuleVote.window_id == windowId)
            .first()
        )
        return row[0] if row else None

    def tally(self, windowId: int) -> Dict[str, int]:
        """Vote counts per option key for the window (includes 'none')."""
        rows = (
            self.session.query(RuleVote.option_key, func.count(RuleVote.id))
            .filter(RuleVote.window_id == windowId)
            .group_by(RuleVote.option_key)
            .all()
        )
        return {key: int(count) for key, count in rows}
