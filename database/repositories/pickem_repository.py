"""Repository for Pick-Em (Prognostications) picks."""

from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func, case, and_

from database.models import PickEmPick
from constants import PICKEM_BASE_POINTS


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
                   homeTeamId: int, awayTeamId: int, pickedTeamId: int,
                   pointsMultiplier: float = 1.0) -> PickEmPick:
        """Submit or update a pick. Only allowed if correct IS NULL (game not resolved).
        pointsMultiplier is set based on game quarter at time of pick.
        """
        existing = self.session.query(PickEmPick).filter_by(
            user_id=userId, season=season, week=week, game_index=gameIndex,
        ).first()

        if existing:
            if existing.correct is not None:
                raise ValueError("Cannot change a resolved pick")
            existing.picked_team_id = pickedTeamId
            existing.points_multiplier = pointsMultiplier
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
            points_multiplier=pointsMultiplier,
        )
        self.session.add(pick)
        self.session.flush()
        return pick

    def resolvePicks(self, season: int, week: int, gameIndex: int, winningTeamId: int) -> int:
        """Resolve all picks for a specific game. Computes points_earned per pick.
        Returns count of rows updated.
        """
        picks = self.session.query(PickEmPick).filter(
            PickEmPick.season == season,
            PickEmPick.week == week,
            PickEmPick.game_index == gameIndex,
            PickEmPick.correct.is_(None),
        ).all()

        for pick in picks:
            isCorrect = (pick.picked_team_id == winningTeamId)
            pick.correct = isCorrect
            multiplier = pick.points_multiplier if pick.points_multiplier is not None else 1.0
            pick.points_earned = int(PICKEM_BASE_POINTS * multiplier) if isCorrect else 0

        self.session.flush()
        return len(picks)

    def getWeekResultsByUser(self, season: int, week: int) -> List[Tuple[int, int, int, int]]:
        """Get aggregated results per user for a week.
        Returns list of (userId, correctCount, totalPicks, totalPoints).
        """
        return self.session.query(
            PickEmPick.user_id,
            func.count(case((PickEmPick.correct == True, 1))),  # noqa: E712
            func.count(PickEmPick.id),
            func.coalesce(func.sum(PickEmPick.points_earned), 0),
        ).filter(
            PickEmPick.season == season,
            PickEmPick.week == week,
            PickEmPick.correct.isnot(None),
        ).group_by(PickEmPick.user_id).all()

    def getWeekLeaderboard(self, season: int, week: int) -> List[Tuple[int, int, int, int]]:
        """Week leaderboard: (userId, correctCount, totalPicks, totalPoints)
        ordered by totalPoints DESC."""
        return self.session.query(
            PickEmPick.user_id,
            func.count(case((PickEmPick.correct == True, 1))),  # noqa: E712
            func.count(PickEmPick.id),
            func.coalesce(func.sum(PickEmPick.points_earned), 0),
        ).filter(
            PickEmPick.season == season,
            PickEmPick.week == week,
            PickEmPick.correct.isnot(None),
        ).group_by(PickEmPick.user_id).order_by(
            func.coalesce(func.sum(PickEmPick.points_earned), 0).desc(),
            func.count(case((PickEmPick.correct == True, 1))).desc(),  # noqa: E712
            func.count(PickEmPick.id).desc(),
        ).all()

    def getSeasonLeaderboard(self, season: int) -> List[Tuple[int, int, int, int]]:
        """Season leaderboard: (userId, correctCount, totalPicks, totalPoints)
        ordered by totalPoints DESC."""
        return self.session.query(
            PickEmPick.user_id,
            func.count(case((PickEmPick.correct == True, 1))),  # noqa: E712
            func.count(PickEmPick.id),
            func.coalesce(func.sum(PickEmPick.points_earned), 0),
        ).filter(
            PickEmPick.season == season,
            PickEmPick.correct.isnot(None),
        ).group_by(PickEmPick.user_id).order_by(
            func.coalesce(func.sum(PickEmPick.points_earned), 0).desc(),
            func.count(case((PickEmPick.correct == True, 1))).desc(),  # noqa: E712
            func.count(PickEmPick.id).desc(),
        ).all()

    def getUserSeasonStats(self, userId: int, season: int) -> dict:
        """Get a user's season-wide pick-em stats."""
        result = self.session.query(
            func.count(case((PickEmPick.correct == True, 1))),  # noqa: E712
            func.count(PickEmPick.id),
            func.coalesce(func.sum(PickEmPick.points_earned), 0),
        ).filter(
            PickEmPick.user_id == userId,
            PickEmPick.season == season,
            PickEmPick.correct.isnot(None),
        ).first()
        correctCount = result[0] if result else 0
        totalPicks = result[1] if result else 0
        totalPoints = result[2] if result else 0

        # Count Clairvoyant weeks (points >= threshold)
        clairvoyantWeeks = self._countClairvoyantWeeks(userId, season)

        return {
            "correctCount": correctCount,
            "totalPicks": totalPicks,
            "totalPoints": totalPoints,
            "clairvoyantWeeks": clairvoyantWeeks,
        }

    def _countClairvoyantWeeks(self, userId: int, season: int) -> int:
        """Count weeks where user reached the Clairvoyant points threshold."""
        from constants import PICKEM_CLAIRVOYANT_THRESHOLD
        weekStats = self.session.query(
            PickEmPick.week,
            func.coalesce(func.sum(PickEmPick.points_earned), 0),
        ).filter(
            PickEmPick.user_id == userId,
            PickEmPick.season == season,
            PickEmPick.correct.isnot(None),
        ).group_by(PickEmPick.week).all()

        return sum(1 for _, pts in weekStats if pts >= PICKEM_CLAIRVOYANT_THRESHOLD)

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
