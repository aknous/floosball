"""AwardsManager — resolves fan-voted season awards (MVP & Hall of Fame).

The value-metric MVP and the HoF-points induction become the *shortlister* and
the *below-quorum fallback*: fans elect from an algorithm-built ballot, and if
turnout is below quorum (or it's a fast/sim run with no votes at all) the
algorithm decides. See docs/AWARDS_VOTING_PLAN.md.

Self-contained brain — does NOT touch the season loop. The seasonManager wires
the trigger points (seed at wk22, resolve MVP at season end, resolve HoF in the
offseason `training` phase).
"""

import math
import logging
from typing import List, Dict, Optional

from database.repositories.award_repository import AwardVoteRepository, HofBallotRepository

logger = logging.getLogger("floosball.awards")


class AwardsManager:
    def __init__(self, session, playerManager, lowQuorum: bool = False):
        self.session = session
        self.playerManager = playerManager
        self.voteRepo = AwardVoteRepository(session)
        self.ballotRepo = HofBallotRepository(session)
        self.lowQuorum = lowQuorum

    # ── MVP ───────────────────────────────────────────────────────────────────
    def getMvpBallot(self) -> List[Dict]:
        """The eligible MVP ballot: top N per position by mvpScore (already the
        value metric). Candidates come back sorted by mvpScore desc."""
        from constants import AWARD_MVP_BALLOT_PER_POSITION
        candidates = self.playerManager._computeMvpCandidates()
        perPos: Dict[str, int] = {}
        ballot = []
        for c in candidates:  # mvpScore-desc order preserved
            pos = c.get('position')
            if perPos.get(pos, 0) >= AWARD_MVP_BALLOT_PER_POSITION:
                continue
            perPos[pos] = perPos.get(pos, 0) + 1
            ballot.append(c)
        return ballot

    def resolveMvp(self, season: int) -> Optional[Dict]:
        """Fan winner if turnout clears quorum, else the top-mvpScore candidate.
        Returns the winning candidate dict (with viaVote/votes), or None."""
        from constants import AWARD_MVP_QUORUM
        ballot = self.getMvpBallot()
        if not ballot:
            return None
        eligibleIds = {c['id'] for c in ballot}
        voters = self.voteRepo.getVoterCount(season, 'mvp')
        tally = {pid: n for pid, n in self.voteRepo.getTally(season, 'mvp').items()
                 if pid in eligibleIds}

        if voters >= AWARD_MVP_QUORUM and tally:
            # Most votes wins; ballot is mvpScore-sorted so iterating in order
            # with a strict '>' breaks ties toward the higher value metric.
            best = None
            for c in ballot:
                v = tally.get(c['id'], 0)
                if best is None or v > best[1]:
                    best = (c, v)
            winner = {**best[0], 'viaVote': True, 'votes': best[1]}
            logger.info(f"MVP (fan vote): {winner['name']} — {best[1]} votes of {voters}")
            return winner

        winner = {**ballot[0], 'viaVote': False, 'votes': tally.get(ballot[0]['id'], 0)}
        logger.info(f"MVP (algorithm fallback — {voters} voters < quorum): {winner['name']}")
        return winner

    # ── Hall of Fame ───────────────────────────────────────────────────────────
    def _pts(self, player) -> int:
        if player is None:
            return 0
        return self.playerManager._computeHofPoints(player)[0]

    def seedHofBallot(self, season: int, retirees: List) -> List:
        """Add this season's qualifying retirees to the rolling ballot. Each is
        pre-filtered by HoF points so the ballot holds only real contenders.
        Idempotent — skips players already on the ballot or already inducted.

        `retirees` is passed in (the wk-22 willRetire set) rather than read from
        retiredPlayers, because at seed time they haven't executed retirement yet.
        """
        from constants import AWARD_HOF_BALLOT_PREFILTER, AWARD_HOF_BALLOT_TENURE
        seeded = []
        seen = set()
        for player in retirees:
            pid = getattr(player, 'id', None)
            if pid is None or pid in seen or getattr(player, 'is_hof', False):
                continue
            seen.add(pid)
            if self.ballotRepo.getEntry(pid):
                continue
            if self._pts(player) < AWARD_HOF_BALLOT_PREFILTER:
                continue
            if self.ballotRepo.addEntry(pid, season, AWARD_HOF_BALLOT_TENURE):
                seeded.append(player)
        logger.info(f"HoF ballot seeded: {len(seeded)} new candidates (season {season})")
        return seeded

    def _induct(self, player, playerId: int, season: int) -> None:
        """Stamp a HoF induction (mirrors playerManager.inductHallOfFame) and
        mark the ballot entry inducted."""
        if player is not None and not getattr(player, 'is_hof', False):
            if player not in self.playerManager.hallOfFame:
                self.playerManager.hallOfFame.append(player)
            player.is_hof = True
            player.hof_season = season
        self.ballotRepo.markInducted(playerId, season)

    def resolveHofInductions(self, season: int) -> List[int]:
        """Resolve this offseason's HoF class from the rolling ballot.

        Fan path (turnout >= quorum): induct the top vote-getters that also clear
        the approval floor, capped at the class size. Fallback (below quorum /
        sim): induct by HoF points >= threshold, ranked, capped. Then decrement
        and drop the non-inducted ballot entries. Returns inducted player IDs.
        """
        from constants import (AWARD_HOF_QUORUM, AWARD_HOF_CLASS_CAP,
                               AWARD_HOF_APPROVAL_FRACTION)
        active = self.ballotRepo.getActive()
        if not active:
            return []
        byId = {e.player_id: self.playerManager.getPlayerById(e.player_id) for e in active}
        voters = self.voteRepo.getVoterCount(season, 'hof')
        tally = self.voteRepo.getTally(season, 'hof')

        inducted: List[int] = []
        if voters >= AWARD_HOF_QUORUM:
            floor = math.ceil(voters * AWARD_HOF_APPROVAL_FRACTION)
            ranked = sorted(
                active,
                key=lambda e: (tally.get(e.player_id, 0), self._pts(byId.get(e.player_id))),
                reverse=True,
            )
            for entry in ranked:
                if len(inducted) >= AWARD_HOF_CLASS_CAP:
                    break
                if tally.get(entry.player_id, 0) >= floor:
                    self._induct(byId.get(entry.player_id), entry.player_id, season)
                    inducted.append(entry.player_id)
            via = "fan vote"
        else:
            thresh = self.playerManager.HOF_INDUCT_THRESHOLD
            scored = [(e, self._pts(byId.get(e.player_id))) for e in active]
            scored = [(e, pts) for e, pts in scored if pts >= thresh]
            scored.sort(key=lambda x: x[1], reverse=True)
            for entry, _pts in scored[:AWARD_HOF_CLASS_CAP]:
                self._induct(byId.get(entry.player_id), entry.player_id, season)
                inducted.append(entry.player_id)
            via = f"algorithm fallback ({voters} voters < quorum)"

        self.ballotRepo.decrementAndDrop()
        logger.info(f"HoF inductions ({via}): {len(inducted)} inducted, "
                    f"cap {AWARD_HOF_CLASS_CAP}")
        return inducted

    def getHofBallot(self) -> List[Dict]:
        """The active rolling ballot, enriched with each candidate's HoF case +
        seasons remaining. Resolves players via getPlayerById (NOT just
        retiredPlayers): the ballot opens at week 22 while these players are
        STILL ACTIVE on rosters during their farewell run, so they haven't
        moved to retiredPlayers yet."""
        from api_response_builders import PlayerResponseBuilder
        out = []
        for entry in self.ballotRepo.getActive():
            player = self.playerManager.getPlayerById(entry.player_id)
            # Defense-in-depth: never show an already-enshrined player on the
            # ballot, even if one slipped onto it (the seed already skips is_hof).
            if player is not None and getattr(player, 'is_hof', False):
                continue
            pts, breakdown = (self.playerManager._computeHofPoints(player)
                              if player is not None else (0, {}))
            # Team + rating from the resolved player (still-active candidates
            # carry their team; retired carryovers may have none → null).
            team = getattr(player, 'team', None) if player is not None else None
            hasTeamObj = hasattr(team, 'name')
            out.append({
                'playerId': entry.player_id,
                'name': getattr(player, 'name', None),
                'position': player.position.name if player is not None and getattr(player, 'position', None) else None,
                'teamAbbr': getattr(team, 'abbr', '') if hasTeamObj else '',
                'teamId': team.id if hasTeamObj else None,
                'teamColor': getattr(team, 'color', '#334155') if hasTeamObj else '#334155',
                'ratingStars': PlayerResponseBuilder.calculateStarRating(player.playerRating) if player is not None else 0,
                'seasonsRemaining': entry.seasons_remaining,
                'firstEligibleSeason': entry.first_eligible_season,
                'points': pts,
                'case': breakdown,
            })
        # Strongest cases first.
        out.sort(key=lambda e: e['points'], reverse=True)
        return out
