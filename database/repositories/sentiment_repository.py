"""Fan sentiment ratings — storage + aggregation (AFO plan Part D).

Fans rate players 1-5. Net ONE rating per fan per player, persistent across
seasons (a standing stance, not a season-scoped ballot — that's what separates
this from AwardVote).

Aggregation deliberately gates on a minimum number of distinct raters: below it
a player reads NEUTRAL, so a single loud fan can't move a roster decision.
"""

from datetime import datetime
from typing import Dict, List, Optional, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session

from database.models import PlayerSentimentRating
from constants import (
    SENTIMENT_RATING_MIN, SENTIMENT_RATING_MAX, SENTIMENT_NEUTRAL,
    SENTIMENT_MIN_RATERS,
)


# The active-user count is a few queries, and a team page asks for the quorum
# once per rating control. Cache it briefly so one page load doesn't re-count
# the league seven times over.
_quorumCache: dict = {'value': None, 'at': None}
_QUORUM_TTL_SECONDS = 60


def requiredRaters(session, floor: Optional[int] = None) -> int:
    """Distinct raters needed before a subject's sentiment counts.

    Scales with the engaged user base, mirroring `AwardsManager._quorum` so the
    two can't drift into different notions of "enough turnout". Falls back to
    the floor if the count is unavailable — never gate harder on an error.
    """
    import math
    from datetime import datetime
    from constants import SENTIMENT_MIN_RATERS, SENTIMENT_QUORUM_ACTIVE_FRACTION
    base = SENTIMENT_MIN_RATERS if floor is None else floor

    now = datetime.utcnow()
    cached, at = _quorumCache['value'], _quorumCache['at']
    if cached is not None and at is not None and (now - at).total_seconds() < _QUORUM_TTL_SECONDS:
        active = cached
    else:
        try:
            from managers.anomalyManager import _countActiveUsers
            active = _countActiveUsers(session)
        except Exception:
            return base
        _quorumCache['value'], _quorumCache['at'] = active, now

    return max(base, math.ceil(active * SENTIMENT_QUORUM_ACTIVE_FRACTION))


def normalizeSentiment(average: Optional[float]) -> float:
    """Map a 1-5 average onto -1.0 .. +1.0, with the midpoint at 0.

    -1 = universally hated, 0 = neutral/unknown, +1 = universally adored.
    """
    if average is None:
        return 0.0
    span = (SENTIMENT_RATING_MAX - SENTIMENT_NEUTRAL) or 1.0
    return max(-1.0, min(1.0, (float(average) - SENTIMENT_NEUTRAL) / span))


class SentimentRepository:
    """Read/write fan sentiment ratings."""

    def __init__(self, session: Session):
        self.session = session

    # ------------------------------------------------------------- write

    def setRating(self, userId: int, playerId: int, rating: int) -> PlayerSentimentRating:
        """Cast or CHANGE this fan's rating of a player.

        Re-rating updates the existing row rather than inserting another, which
        is what makes the signal net-one-per-fan and brigade-resistant.
        """
        rating = int(rating)
        if not (SENTIMENT_RATING_MIN <= rating <= SENTIMENT_RATING_MAX):
            raise ValueError(
                f"rating must be {SENTIMENT_RATING_MIN}-{SENTIMENT_RATING_MAX}")

        row = (self.session.query(PlayerSentimentRating)
               .filter(PlayerSentimentRating.user_id == userId,
                       PlayerSentimentRating.player_id == playerId)
               .first())
        now = datetime.utcnow()
        if row is None:
            row = PlayerSentimentRating(user_id=userId, player_id=playerId,
                                        rating=rating, created_at=now, updated_at=now)
            self.session.add(row)
        else:
            row.rating = rating
            row.updated_at = now
        return row

    def clearRating(self, userId: int, playerId: int) -> bool:
        """Withdraw a rating entirely. Returns True if one was removed."""
        row = (self.session.query(PlayerSentimentRating)
               .filter(PlayerSentimentRating.user_id == userId,
                       PlayerSentimentRating.player_id == playerId)
               .first())
        if row is None:
            return False
        self.session.delete(row)
        return True

    # -------------------------------------------------------------- read

    def getUserRating(self, userId: int, playerId: int) -> Optional[int]:
        row = (self.session.query(PlayerSentimentRating.rating)
               .filter(PlayerSentimentRating.user_id == userId,
                       PlayerSentimentRating.player_id == playerId)
               .first())
        return int(row[0]) if row else None

    def getUserRatings(self, userId: int) -> Dict[int, int]:
        """Every rating this fan holds, keyed by player id."""
        rows = (self.session.query(PlayerSentimentRating.player_id,
                                   PlayerSentimentRating.rating)
                .filter(PlayerSentimentRating.user_id == userId)
                .all())
        return {int(pid): int(r) for pid, r in rows}

    def getAggregate(self, playerId: int) -> Tuple[float, int]:
        """(averageRating, raterCount) for one player. (0.0, 0) if unrated."""
        row = (self.session.query(func.avg(PlayerSentimentRating.rating),
                                  func.count(PlayerSentimentRating.id))
               .filter(PlayerSentimentRating.player_id == playerId)
               .first())
        if not row or not row[1]:
            return 0.0, 0
        return float(row[0] or 0.0), int(row[1])

    def getAggregates(self, playerIds=None) -> Dict[int, Tuple[float, int]]:
        """Bulk aggregate — one query for the whole league.

        The GM sweep values every roster on every team, so per-player queries
        would be a needless N+1 in the offseason hot path.
        """
        q = (self.session.query(PlayerSentimentRating.player_id,
                                func.avg(PlayerSentimentRating.rating),
                                func.count(PlayerSentimentRating.id))
             .group_by(PlayerSentimentRating.player_id))
        if playerIds:
            q = q.filter(PlayerSentimentRating.player_id.in_(list(playerIds)))
        return {int(pid): (float(avg or 0.0), int(cnt)) for pid, avg, cnt in q.all()}

    def requiredRaters(self) -> int:
        """Turnout this league needs before a rating counts."""
        return requiredRaters(self.session)

    def getSentiment(self, playerId: int) -> float:
        """Normalized -1..+1 sentiment, or 0.0 below the rater quorum."""
        avg, count = self.getAggregate(playerId)
        if count < self.requiredRaters():
            return 0.0
        return normalizeSentiment(avg)

    def getSentimentMap(self, playerIds=None) -> Dict[int, float]:
        """Bulk normalized sentiment, already rater-gated. Players below the
        floor are simply absent — callers should default to 0.0."""
        need = self.requiredRaters()
        out = {}
        for pid, (avg, count) in self.getAggregates(playerIds).items():
            if count >= need:
                out[pid] = normalizeSentiment(avg)
        return out

    # ------------------------------------------------------------ boards

    def getBoard(self, limit: int, mostLoved: bool = True,
                 playerIds=None) -> List[dict]:
        """Fan Favorites / Most Hated. Rater-gated, so a board can't be topped
        by a player one person rated once."""
        rows = (self.session.query(
                    PlayerSentimentRating.player_id,
                    func.avg(PlayerSentimentRating.rating).label('avg'),
                    func.count(PlayerSentimentRating.id).label('cnt'))
                .group_by(PlayerSentimentRating.player_id)
                .having(func.count(PlayerSentimentRating.id) >= requiredRaters(self.session)))
        if playerIds:
            rows = rows.filter(PlayerSentimentRating.player_id.in_(list(playerIds)))
        rows = rows.all()

        entries = [{
            'playerId': int(pid),
            'average': round(float(avg), 2),
            'raters': int(cnt),
            'sentiment': round(normalizeSentiment(avg), 3),
        } for pid, avg, cnt in rows]
        entries.sort(key=lambda e: (-e['average'], -e['raters']) if mostLoved
                     else (e['average'], -e['raters']))
        return entries[:limit]


def buildSentimentMap(session, now=None) -> dict:
    """The league-wide {playerId: -1..+1} map the GM brain consumes.

    Ratings ONLY. An earlier design blended in a post-derived "pulse", but
    player opinions now reach the feed as AUTO posts generated from these same
    ratings — counting them again would double every vote. Kept as a named
    builder so callers have one obvious entry point.
    """
    return SentimentRepository(session).getSentimentMap()


class CoachSentimentRepository:
    """GM 1-5 ratings — same scale and same maths as players (plan Part D).

    Deliberately mirrors SentimentRepository rather than reimplementing it:
    both share `normalizeSentiment` and the rater-floor idea, so the two can't
    drift into judging a GM on a different curve than a player.

    Drives GM fire/leave risk.
    """

    def __init__(self, session):
        self.session = session

    def setRating(self, userId: int, coachId: int, rating: int) -> int:
        """Cast or change this fan's rating. Re-rating replaces."""
        from database.models import CoachSentimentVote
        rating = int(rating)
        if not (SENTIMENT_RATING_MIN <= rating <= SENTIMENT_RATING_MAX):
            raise ValueError(
                f"rating must be {SENTIMENT_RATING_MIN}-{SENTIMENT_RATING_MAX}")
        row = (self.session.query(CoachSentimentVote)
               .filter(CoachSentimentVote.user_id == userId,
                       CoachSentimentVote.coach_id == coachId)
               .first())
        now = datetime.utcnow()
        if row is None:
            self.session.add(CoachSentimentVote(
                user_id=userId, coach_id=coachId, rating=rating,
                created_at=now, updated_at=now))
        else:
            row.rating = rating
            row.updated_at = now
        return rating

    def clearRating(self, userId: int, coachId: int) -> bool:
        from database.models import CoachSentimentVote
        row = (self.session.query(CoachSentimentVote)
               .filter(CoachSentimentVote.user_id == userId,
                       CoachSentimentVote.coach_id == coachId)
               .first())
        if row is None:
            return False
        self.session.delete(row)
        return True

    def getUserRating(self, userId: int, coachId: int):
        from database.models import CoachSentimentVote
        row = (self.session.query(CoachSentimentVote.rating)
               .filter(CoachSentimentVote.user_id == userId,
                       CoachSentimentVote.coach_id == coachId)
               .first())
        return int(row[0]) if row else None

    def getAggregate(self, coachId: int):
        """(averageRating, raterCount). (0.0, 0) when unrated."""
        from database.models import CoachSentimentVote
        row = (self.session.query(func.avg(CoachSentimentVote.rating),
                                  func.count(CoachSentimentVote.id))
               .filter(CoachSentimentVote.coach_id == coachId)
               .first())
        if not row or not row[1]:
            return 0.0, 0
        return float(row[0] or 0.0), int(row[1])

    def requiredRaters(self) -> int:
        from constants import GM_SENTIMENT_MIN_VOTERS
        return requiredRaters(self.session, floor=GM_SENTIMENT_MIN_VOTERS)

    def getStanding(self, coachId: int) -> float:
        """-1..+1, or 0.0 below the rater quorum — what turnover reads."""
        avg, count = self.getAggregate(coachId)
        if count < self.requiredRaters():
            return 0.0
        return normalizeSentiment(avg)

    def getStandingMap(self) -> dict:
        """{coachId: -1..+1} for the league in one query — the offseason
        turnover pass runs across every team."""
        from database.models import CoachSentimentVote
        need = self.requiredRaters()
        rows = (self.session.query(CoachSentimentVote.coach_id,
                                   func.avg(CoachSentimentVote.rating),
                                   func.count(CoachSentimentVote.id))
                .group_by(CoachSentimentVote.coach_id).all())
        return {int(cid): normalizeSentiment(float(avg or 0.0))
                for cid, avg, cnt in rows if int(cnt) >= need}

    def getBoard(self, limit: int, mostLiked: bool = True):
        """Best / worst regarded GMs league-wide."""
        from database.models import CoachSentimentVote
        rows = (self.session.query(CoachSentimentVote.coach_id,
                                   func.avg(CoachSentimentVote.rating),
                                   func.count(CoachSentimentVote.id))
                .group_by(CoachSentimentVote.coach_id)
                .having(func.count(CoachSentimentVote.id) >= self.requiredRaters())
                .all())
        entries = [{
            'coachId': int(cid),
            'average': round(float(avg), 2),
            'raters': int(cnt),
            'standing': round(normalizeSentiment(float(avg)), 3),
        } for cid, avg, cnt in rows]
        entries.sort(key=lambda e: (-e['average'], -e['raters']) if mostLiked
                     else (e['average'], -e['raters']))
        return entries[:limit]
