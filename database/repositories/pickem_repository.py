"""Repository for Pick-Em (Prognostications) picks."""

from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func, case, and_

from database.models import PickEmPick


class PickEmRepository:
    """Repository for pick-em pick operations."""

    def __init__(self, session: Session):
        self.session = session

    def getUserPicks(self, userId: int, season: int, week: int) -> List[PickEmPick]:
        """Get all of a user's picks for a specific week."""
        return self.session.query(PickEmPick).filter_by(
            user_id=userId, season=season, week=week,
        ).order_by(PickEmPick.game_index).all()

    def submitPick(self, userId: int, season: int, week: int, gameIndex: int,
                   homeTeamId: int, awayTeamId: int, pickedTeamId: int) -> PickEmPick:
        """Submit or update a pick. Only allowed if correct IS NULL (game not resolved)."""
        existing = self.session.query(PickEmPick).filter_by(
            user_id=userId, season=season, week=week, game_index=gameIndex,
        ).first()

        if existing:
            if existing.correct is not None:
                raise ValueError("Cannot change a resolved pick")
            existing.picked_team_id = pickedTeamId
            self.session.flush()
            return existing

        pick = PickEmPick(
            user_id=userId,
            season=season,
            week=week,
            game_index=gameIndex,
            home_team_id=homeTeamId,
            away_team_id=awayTeamId,
            picked_team_id=pickedTeamId,
        )
        self.session.add(pick)
        self.session.flush()
        return pick

    def resolvePicks(self, season: int, week: int, gameIndex: int, winningTeamId: int) -> int:
        """Resolve all picks for a specific game. Returns count of rows updated."""
        count = self.session.query(PickEmPick).filter(
            PickEmPick.season == season,
            PickEmPick.week == week,
            PickEmPick.game_index == gameIndex,
            PickEmPick.correct.is_(None),
        ).update(
            {PickEmPick.correct: PickEmPick.picked_team_id == winningTeamId},
            synchronize_session='fetch',
        )
        return count

    def getWeekResultsByUser(self, season: int, week: int) -> List[Tuple[int, int, int]]:
        """Get aggregated results per user for a week.
        Returns list of (userId, correctCount, totalPicks).
        """
        return self.session.query(
            PickEmPick.user_id,
            func.count(case((PickEmPick.correct == True, 1))),  # noqa: E712
            func.count(PickEmPick.id),
        ).filter(
            PickEmPick.season == season,
            PickEmPick.week == week,
            PickEmPick.correct.isnot(None),
        ).group_by(PickEmPick.user_id).all()

    def getWeekLeaderboard(self, season: int, week: int) -> List[Tuple[int, int, int]]:
        """Week leaderboard: (userId, correctCount, totalPicks) ordered by correctCount DESC."""
        return self.session.query(
            PickEmPick.user_id,
            func.count(case((PickEmPick.correct == True, 1))),  # noqa: E712
            func.count(PickEmPick.id),
        ).filter(
            PickEmPick.season == season,
            PickEmPick.week == week,
            PickEmPick.correct.isnot(None),
        ).group_by(PickEmPick.user_id).order_by(
            func.count(case((PickEmPick.correct == True, 1))).desc(),  # noqa: E712
            func.count(PickEmPick.id).desc(),  # tiebreaker: more picks
        ).all()

    def getSeasonLeaderboard(self, season: int) -> List[Tuple[int, int, int]]:
        """Season leaderboard: (userId, correctCount, totalPicks) ordered by correctCount DESC."""
        return self.session.query(
            PickEmPick.user_id,
            func.count(case((PickEmPick.correct == True, 1))),  # noqa: E712
            func.count(PickEmPick.id),
        ).filter(
            PickEmPick.season == season,
            PickEmPick.correct.isnot(None),
        ).group_by(PickEmPick.user_id).order_by(
            func.count(case((PickEmPick.correct == True, 1))).desc(),  # noqa: E712
            func.count(PickEmPick.id).desc(),
        ).all()

    def getUserSeasonStats(self, userId: int, season: int) -> dict:
        """Get a user's season-wide pick-em stats."""
        result = self.session.query(
            func.count(case((PickEmPick.correct == True, 1))),  # noqa: E712
            func.count(PickEmPick.id),
        ).filter(
            PickEmPick.user_id == userId,
            PickEmPick.season == season,
            PickEmPick.correct.isnot(None),
        ).first()
        correctCount = result[0] if result else 0
        totalPicks = result[1] if result else 0

        # Count perfect weeks
        perfectWeeks = self._countPerfectWeeks(userId, season)

        return {
            "correctCount": correctCount,
            "totalPicks": totalPicks,
            "perfectWeeks": perfectWeeks,
        }

    def _countPerfectWeeks(self, userId: int, season: int) -> int:
        """Count weeks where user picked every game correctly."""
        # Get weeks where user has resolved picks
        weekStats = self.session.query(
            PickEmPick.week,
            func.count(PickEmPick.id),
            func.count(case((PickEmPick.correct == True, 1))),  # noqa: E712
        ).filter(
            PickEmPick.user_id == userId,
            PickEmPick.season == season,
            PickEmPick.correct.isnot(None),
        ).group_by(PickEmPick.week).all()

        return sum(1 for _, total, correct in weekStats if total > 0 and total == correct)

    def getPerfectWeekUsers(self, season: int, week: int, totalGames: int) -> List[int]:
        """Get user IDs who picked every game correctly in a week."""
        results = self.session.query(
            PickEmPick.user_id,
            func.count(PickEmPick.id),
            func.count(case((PickEmPick.correct == True, 1))),  # noqa: E712
        ).filter(
            PickEmPick.season == season,
            PickEmPick.week == week,
            PickEmPick.correct.isnot(None),
        ).group_by(PickEmPick.user_id).all()

        return [
            userId for userId, total, correct
            in results
            if total == totalGames and correct == totalGames
        ]

    def getUserHistory(self, userId: int, season: int) -> List[PickEmPick]:
        """Get all picks for a user in a season, ordered by week and game index."""
        return self.session.query(PickEmPick).filter_by(
            user_id=userId, season=season,
        ).order_by(PickEmPick.week, PickEmPick.game_index).all()
