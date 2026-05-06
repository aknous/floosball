"""Repository classes for GM Mode database access."""

import json
from typing import List, Optional, Dict
from datetime import datetime

from sqlalchemy.orm import Session
from sqlalchemy import func

from database.models import GmVote, GmVoteResult, GmFaBallot, User


class GmVoteRepository:
    """Repository for GM vote operations."""

    def __init__(self, session: Session):
        self.session = session

    def castVote(self, userId: int, teamId: int, season: int,
                 voteType: str, costPaid: int,
                 targetPlayerId: int = None) -> GmVote:
        vote = GmVote(
            user_id=userId,
            team_id=teamId,
            season=season,
            vote_type=voteType,
            target_player_id=targetPlayerId,
            cost_paid=costPaid,
        )
        self.session.add(vote)
        self.session.flush()
        return vote

    def getVotesForTeam(self, teamId: int, season: int,
                        voteType: str = None) -> List[GmVote]:
        query = self.session.query(GmVote).filter_by(
            team_id=teamId, season=season
        )
        if voteType:
            query = query.filter_by(vote_type=voteType)
        return query.all()

    def getUserVotes(self, userId: int, season: int) -> List[GmVote]:
        return (
            self.session.query(GmVote)
            .filter_by(user_id=userId, season=season)
            .all()
        )

    def getUserVoteCounts(self, userId: int, season: int) -> Dict[str, int]:
        """Returns {total, per_type: {type: count}, per_target: {(type, playerId): count}}."""
        votes = self.getUserVotes(userId, season)
        total = len(votes)
        perType: Dict[str, int] = {}
        perTarget: Dict[str, int] = {}
        for v in votes:
            perType[v.vote_type] = perType.get(v.vote_type, 0) + 1
            key = f"{v.vote_type}:{v.target_player_id or 'none'}"
            perTarget[key] = perTarget.get(key, 0) + 1
        return {"total": total, "perType": perType, "perTarget": perTarget}

    def getTotalVotesCastForTeam(self, teamId: int, season: int) -> int:
        """Total raw vote count cast on a team this season (any type/target).

        Used as the denominator for majority-based thresholds: a fire/
        resign/cut decision needs more than half of the team's cast votes
        to pass. This way the bar scales with how engaged fans actually
        are this season — quiet teams pass things on a few votes, hot
        teams need a real consensus.
        """
        return int(
            self.session.query(func.count(GmVote.id))
            .filter_by(team_id=teamId, season=season)
            .scalar() or 0
        )

    def getVoteTallies(self, teamId: int, season: int) -> List[Dict]:
        """Aggregate votes by (vote_type, target_player_id) for a team."""
        rows = (
            self.session.query(
                GmVote.vote_type,
                GmVote.target_player_id,
                func.count(GmVote.id).label("vote_count"),
            )
            .filter_by(team_id=teamId, season=season)
            .group_by(GmVote.vote_type, GmVote.target_player_id)
            .all()
        )
        return [
            {
                "voteType": r.vote_type,
                "targetPlayerId": r.target_player_id,
                "votes": r.vote_count,
            }
            for r in rows
        ]

    def recordResult(self, teamId: int, season: int, voteType: str,
                     totalVotes: int, threshold: int, probability: float,
                     outcome: str, targetPlayerId: int = None,
                     details: str = None) -> GmVoteResult:
        result = GmVoteResult(
            team_id=teamId,
            season=season,
            vote_type=voteType,
            target_player_id=targetPlayerId,
            total_votes=totalVotes,
            threshold=threshold,
            success_probability=probability,
            outcome=outcome,
            details=details,
        )
        self.session.add(result)
        self.session.flush()
        return result

    def getEngagedVoterCount(self, teamId: int, season: int) -> int:
        """Count distinct users who have favorite_team_id == teamId AND cast ≥1 GM vote this season."""
        return (
            self.session.query(func.count(func.distinct(GmVote.user_id)))
            .join(User, User.id == GmVote.user_id)
            .filter(
                GmVote.team_id == teamId,
                GmVote.season == season,
                User.favorite_team_id == teamId,
            )
            .scalar()
        ) or 0

    def getTeamFanCount(self, teamId: int) -> int:
        """Total fans of a team — users with favorite_team_id == teamId.

        Used as the threshold target for fire/resign/cut votes: a directive
        passes when its vote tally meets or exceeds the team's fan count.
        That's roughly "each fan contributes one vote on average," which
        scales linearly with the fanbase without punishing engagement —
        the bar moves with how many fans EXIST, not with how many actually
        vote, so cost doesn't blow up just because more people participate.
        """
        return int(
            self.session.query(func.count(User.id))
            .filter(User.favorite_team_id == teamId)
            .scalar() or 0
        )

    def getResults(self, teamId: int, season: int) -> List[GmVoteResult]:
        return (
            self.session.query(GmVoteResult)
            .filter_by(team_id=teamId, season=season)
            .all()
        )


class GmFaBallotRepository:
    """Repository for GM FA ranked-choice ballot operations."""

    def __init__(self, session: Session):
        self.session = session

    def submitBallot(self, userId: int, teamId: int, season: int,
                     rankings: List[int], costPaid: int) -> GmFaBallot:
        """Submit or update a ballot. Returns the ballot."""
        existing = self.getUserBallot(userId, teamId, season)
        if existing:
            existing.rankings = json.dumps(rankings)
            existing.updated_at = datetime.utcnow()
            self.session.flush()
            return existing
        ballot = GmFaBallot(
            user_id=userId,
            team_id=teamId,
            season=season,
            rankings=json.dumps(rankings),
            cost_paid=costPaid,
        )
        self.session.add(ballot)
        self.session.flush()
        return ballot

    def getUserBallot(self, userId: int, teamId: int,
                      season: int) -> Optional[GmFaBallot]:
        return (
            self.session.query(GmFaBallot)
            .filter_by(user_id=userId, team_id=teamId, season=season)
            .first()
        )

    def getBallotsByTeam(self, teamId: int, season: int) -> List[GmFaBallot]:
        return (
            self.session.query(GmFaBallot)
            .filter_by(team_id=teamId, season=season)
            .all()
        )

    def getRankingsForTeam(self, teamId: int, season: int) -> List[List[int]]:
        """Return list of parsed ranking arrays for all ballots for a team."""
        ballots = self.getBallotsByTeam(teamId, season)
        result = []
        for b in ballots:
            try:
                result.append(json.loads(b.rankings))
            except (json.JSONDecodeError, TypeError):
                continue
        return result
