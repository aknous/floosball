"""Repository classes for fan-voted season awards (MVP & Hall of Fame).

League-wide voting + rolling HoF ballot state. Mirrors the single-net-vote
patterns of gm_repository, minus team scoping and minus cost (awards are free).
See docs/AWARDS_VOTING_PLAN.md.
"""

from typing import List, Optional, Dict, Set

from sqlalchemy.orm import Session
from sqlalchemy import func

from database.models import AwardVote, HofBallotEntry


class AwardVoteRepository:
    """MVP (single pick) and HoF (approval) fan votes for a season."""

    def __init__(self, session: Session):
        self.session = session

    # ── MVP: one pick per user per season ────────────────────────────────────
    def setMvpVote(self, userId: int, season: int, playerId: int) -> AwardVote:
        """Set (or replace) this user's single MVP pick for the season."""
        self.session.query(AwardVote).filter(
            AwardVote.user_id == userId,
            AwardVote.season == season,
            AwardVote.award_type == "mvp",
        ).delete()
        vote = AwardVote(
            user_id=userId, season=season,
            award_type="mvp", target_player_id=playerId,
        )
        self.session.add(vote)
        self.session.flush()
        return vote

    def getMvpVote(self, userId: int, season: int) -> Optional[int]:
        """The player this user voted MVP, or None."""
        row = (
            self.session.query(AwardVote.target_player_id)
            .filter(AwardVote.user_id == userId, AwardVote.season == season,
                    AwardVote.award_type == "mvp")
            .first()
        )
        return row[0] if row else None

    # ── HoF: approval — at most one 'yea' per (user, player) ──────────────────
    def toggleHofApproval(self, userId: int, season: int, playerId: int) -> bool:
        """Approve the player if not already approved, else withdraw. Returns
        True if now approved, False if withdrawn."""
        existing = (
            self.session.query(AwardVote)
            .filter(AwardVote.user_id == userId, AwardVote.season == season,
                    AwardVote.award_type == "hof",
                    AwardVote.target_player_id == playerId)
            .first()
        )
        if existing:
            self.session.delete(existing)
            self.session.flush()
            return False
        self.session.add(AwardVote(
            user_id=userId, season=season,
            award_type="hof", target_player_id=playerId,
        ))
        self.session.flush()
        return True

    def getHofApprovals(self, userId: int, season: int) -> Set[int]:
        """Set of player IDs this user approved for HoF this season."""
        rows = (
            self.session.query(AwardVote.target_player_id)
            .filter(AwardVote.user_id == userId, AwardVote.season == season,
                    AwardVote.award_type == "hof")
            .all()
        )
        return {r[0] for r in rows}

    # ── Tallies / quorum ──────────────────────────────────────────────────────
    def getTally(self, season: int, awardType: str) -> Dict[int, int]:
        """{playerId: voteCount} for an award this season."""
        rows = (
            self.session.query(AwardVote.target_player_id, func.count(AwardVote.id))
            .filter(AwardVote.season == season, AwardVote.award_type == awardType)
            .group_by(AwardVote.target_player_id)
            .all()
        )
        return {pid: cnt for pid, cnt in rows}

    def getVoterCount(self, season: int, awardType: str) -> int:
        """Distinct users who cast at least one vote for this award — the
        quorum denominator."""
        return (
            self.session.query(func.count(func.distinct(AwardVote.user_id)))
            .filter(AwardVote.season == season, AwardVote.award_type == awardType)
            .scalar()
        ) or 0


class HofBallotRepository:
    """Rolling Hall of Fame ballot state across seasons."""

    def __init__(self, session: Session):
        self.session = session

    def addEntry(self, playerId: int, firstEligibleSeason: int,
                 seasonsRemaining: int) -> Optional[HofBallotEntry]:
        """Seed a new ballot entry. Idempotent — returns None if the player is
        already (or was ever) on the ballot."""
        existing = (
            self.session.query(HofBallotEntry)
            .filter(HofBallotEntry.player_id == playerId)
            .first()
        )
        if existing:
            return None
        entry = HofBallotEntry(
            player_id=playerId,
            first_eligible_season=firstEligibleSeason,
            seasons_remaining=seasonsRemaining,
            status="on_ballot",
        )
        self.session.add(entry)
        self.session.flush()
        return entry

    def getActive(self) -> List[HofBallotEntry]:
        """Entries currently on the ballot (eligible to be voted on)."""
        return (
            self.session.query(HofBallotEntry)
            .filter(HofBallotEntry.status == "on_ballot")
            .all()
        )

    def getAllPlayerIds(self) -> Set[int]:
        """Every player who has ever been on the ballot (any status). Used as the
        safety-net exclusion so the points fallback only catches NOT-on-ballot
        retirees — the voted path owns everyone who reached the ballot."""
        rows = self.session.query(HofBallotEntry.player_id).all()
        return {r[0] for r in rows}

    def getEntry(self, playerId: int) -> Optional[HofBallotEntry]:
        return (
            self.session.query(HofBallotEntry)
            .filter(HofBallotEntry.player_id == playerId)
            .first()
        )

    def markInducted(self, playerId: int, season: int) -> None:
        entry = self.getEntry(playerId)
        if entry:
            entry.status = "inducted"
            entry.inducted_season = season
            self.session.flush()

    def decrementAndDrop(self) -> List[int]:
        """End-of-vote upkeep: decrement seasons_remaining on every still-on-ballot
        entry; drop those that hit 0. Returns the player IDs dropped."""
        dropped = []
        for entry in self.getActive():
            entry.seasons_remaining -= 1
            if entry.seasons_remaining <= 0:
                entry.status = "dropped"
                dropped.append(entry.player_id)
        self.session.flush()
        return dropped
