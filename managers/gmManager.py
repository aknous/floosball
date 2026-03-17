"""GM Mode manager — resolves crowdsourced team votes during offseason."""

import json
import logging
import math
import random
from typing import Dict, List, Optional, Tuple

from database.repositories.gm_repository import GmVoteRepository, GmFaBallotRepository
from constants import (
    GM_VOTE_WEIGHT,
    GM_VOTE_BASE_MIN,
    GM_THRESHOLD_USER_FACTOR,
    GM_PROB_BASE,
    GM_PROB_RANGE,
    GM_PROB_CAP,
    GM_FA_MIN_APPEARANCE_PCT,
)

logger = logging.getLogger("floosball")


class GmManager:
    """Resolves GM Mode votes and FA ballots during offseason."""

    def __init__(self, session, lowQuorum: bool = False):
        self.session = session
        self.voteRepo = GmVoteRepository(session)
        self.ballotRepo = GmFaBallotRepository(session)
        self._lowQuorum = lowQuorum

    # ── Threshold & Probability ─────────────────────────────────────────

    def calculateThreshold(self, engagedFanCount: int, voteType: str) -> int:
        weight = GM_VOTE_WEIGHT.get(voteType, 1.0)
        baseMin = 1 if self._lowQuorum else GM_VOTE_BASE_MIN.get(voteType, 2)
        return max(baseMin, math.ceil(engagedFanCount * GM_THRESHOLD_USER_FACTOR * weight))

    def calculateProbability(self, votes: int, threshold: int) -> float:
        if votes < threshold:
            return 0.0
        if self._lowQuorum:
            return 1.0
        ratio = votes / threshold - 1.0
        return min(GM_PROB_CAP, GM_PROB_BASE + GM_PROB_RANGE * min(1.0, ratio))

    @staticmethod
    def _rollSuccess(probability: float) -> bool:
        return random.random() < probability

    # ── Fire Coach ──────────────────────────────────────────────────────

    def resolveFireCoachVotes(self, teams, season: int,
                              teamManager) -> List[Dict]:
        """Resolve fire_coach votes for all teams. Returns list of result dicts.

        On success, fires the coach but does NOT auto-hire. The calling code
        should call resolveHireCoachVotes afterward to fill the vacancy.
        Returns the set of team IDs that had a coach fired via firedTeamIds.
        """
        results = []
        firedTeamIds = set()
        for team in teams:
            votes = self.voteRepo.getVotesForTeam(team.id, season, "fire_coach")
            totalVotes = len(votes)
            if totalVotes == 0:
                continue

            engagedFans = self.voteRepo.getEngagedVoterCount(team.id, season)
            threshold = self.calculateThreshold(engagedFans, "fire_coach")
            probability = self.calculateProbability(totalVotes, threshold)

            if probability == 0.0:
                outcome = "below_threshold"
            elif self._rollSuccess(probability):
                outcome = "success"
                oldCoachName = team.coach.name if team.coach else "None"
                teamManager.fireCoach(team)
                firedTeamIds.add(team.id)
                logger.info(
                    f"GM: {team.name} fired coach {oldCoachName} "
                    f"({totalVotes} votes, p={probability:.0%})"
                )
            else:
                outcome = "failed_roll"

            self.voteRepo.recordResult(
                teamId=team.id, season=season, voteType="fire_coach",
                totalVotes=totalVotes, threshold=threshold,
                probability=probability, outcome=outcome,
            )
            results.append({
                "teamId": team.id, "teamName": team.name,
                "voteType": "fire_coach", "totalVotes": totalVotes,
                "threshold": threshold, "probability": probability,
                "outcome": outcome,
            })
        return results, firedTeamIds

    # ── Hire Coach ─────────────────────────────────────────────────────

    def resolveHireCoachVotes(self, teams, season: int,
                              teamManager, firedTeamIds: set) -> List[Dict]:
        """Resolve hire_coach votes for teams that fired their coach.

        For each team in firedTeamIds:
        - Check hire_coach votes targeting specific coach IDs
        - Candidates are sorted by vote count (descending); first to pass gets hired
        - If no hire_coach vote meets threshold or passes roll, random coach is hired
        """
        results = []
        # Build a name lookup from the available coach pool
        availableCoaches = teamManager.getAvailableCoaches()
        coachNames = {c.id: c.name for c in availableCoaches}
        availableIds = {c.id for c in availableCoaches}

        for team in teams:
            if team.id not in firedTeamIds:
                continue

            votes = self.voteRepo.getVotesForTeam(team.id, season, "hire_coach")

            # Group votes by target (coach DB ID stored as target_player_id)
            votesByTarget: Dict[int, int] = {}
            for v in votes:
                if v.target_player_id:
                    votesByTarget[v.target_player_id] = (
                        votesByTarget.get(v.target_player_id, 0) + 1
                    )

            engagedFans = self.voteRepo.getEngagedVoterCount(team.id, season)
            threshold = self.calculateThreshold(engagedFans, "hire_coach")

            hired = False
            # Evaluate candidates in order of most votes
            for coachId, count in sorted(votesByTarget.items(),
                                          key=lambda x: -x[1]):
                probability = self.calculateProbability(count, threshold)
                coachName = coachNames.get(coachId, f"Coach#{coachId}")

                if coachId not in availableIds:
                    outcome = "ineligible"
                elif probability == 0.0:
                    outcome = "below_threshold"
                elif self._rollSuccess(probability):
                    outcome = "success"
                    teamManager.hireCoachFromPool(team, coachId)
                    availableIds.discard(coachId)
                    hired = True
                    logger.info(
                        f"GM: {team.name} hired {coachName} by vote "
                        f"({count} votes, p={probability:.0%})"
                    )
                else:
                    outcome = "failed_roll"

                self.voteRepo.recordResult(
                    teamId=team.id, season=season, voteType="hire_coach",
                    targetPlayerId=coachId, totalVotes=count,
                    threshold=threshold, probability=probability,
                    outcome=outcome,
                )
                results.append({
                    "teamId": team.id, "teamName": team.name,
                    "voteType": "hire_coach",
                    "targetPlayerName": coachName,
                    "totalVotes": count, "threshold": threshold,
                    "probability": probability, "outcome": outcome,
                })
                if hired:
                    break

            if not hired:
                # Fallback: hire a random coach
                newCoach = teamManager.generateCoach()
                teamManager.hireCoach(team, newCoach)
                logger.info(
                    f"GM: {team.name} auto-hired {newCoach.name} "
                    f"(no hire_coach vote met quorum)"
                )

        return results

    # ── Re-sign Players ─────────────────────────────────────────────────

    def resolveResignVotes(self, teams, season: int,
                           playerManager) -> List[Dict]:
        """Resolve resign_player votes. Returns list of result dicts.

        On success, sets player._gmResigned = True so contract processing
        skips expiration for that player.
        """
        results = []
        for team in teams:
            votes = self.voteRepo.getVotesForTeam(team.id, season, "resign_player")
            if not votes:
                continue

            # Group votes by target player
            votesByTarget: Dict[int, int] = {}
            for v in votes:
                if v.target_player_id:
                    votesByTarget[v.target_player_id] = (
                        votesByTarget.get(v.target_player_id, 0) + 1
                    )

            engagedFans = self.voteRepo.getEngagedVoterCount(team.id, season)
            threshold = self.calculateThreshold(engagedFans, "resign_player")

            for playerId, count in votesByTarget.items():
                probability = self.calculateProbability(count, threshold)
                player = self._findPlayerOnTeam(team, playerId)

                if player is None:
                    outcome = "ineligible"
                elif not hasattr(player, 'termRemaining') or player.termRemaining != 1:
                    outcome = "ineligible"
                elif probability == 0.0:
                    outcome = "below_threshold"
                elif self._rollSuccess(probability):
                    outcome = "success"
                    player._gmResigned = True
                    logger.info(
                        f"GM: {team.name} re-signing {player.name} "
                        f"({count} votes, p={probability:.0%})"
                    )
                else:
                    outcome = "failed_roll"

                playerName = player.name if player else f"Player#{playerId}"
                self.voteRepo.recordResult(
                    teamId=team.id, season=season, voteType="resign_player",
                    targetPlayerId=playerId, totalVotes=count,
                    threshold=threshold, probability=probability,
                    outcome=outcome,
                )
                results.append({
                    "teamId": team.id, "teamName": team.name,
                    "voteType": "resign_player", "targetPlayerName": playerName,
                    "totalVotes": count, "threshold": threshold,
                    "probability": probability, "outcome": outcome,
                })
        return results

    # ── Cut Players ─────────────────────────────────────────────────────

    def resolveCutVotes(self, teams, season: int,
                        playerManager,
                        freeAgentLists: Dict) -> List[Dict]:
        """Resolve cut_player votes. Successfully cut players are moved to FA pool.

        Returns list of result dicts.
        """
        results = []
        for team in teams:
            votes = self.voteRepo.getVotesForTeam(team.id, season, "cut_player")
            if not votes:
                continue

            votesByTarget: Dict[int, int] = {}
            for v in votes:
                if v.target_player_id:
                    votesByTarget[v.target_player_id] = (
                        votesByTarget.get(v.target_player_id, 0) + 1
                    )

            engagedFans = self.voteRepo.getEngagedVoterCount(team.id, season)
            threshold = self.calculateThreshold(engagedFans, "cut_player")

            for playerId, count in votesByTarget.items():
                probability = self.calculateProbability(count, threshold)
                player = self._findPlayerOnTeam(team, playerId)

                if player is None:
                    outcome = "ineligible"
                elif probability == 0.0:
                    outcome = "below_threshold"
                elif self._rollSuccess(probability):
                    outcome = "success"
                    # Release player to FA pool
                    playerManager.releasePlayerToFreeAgency(player, team, freeAgentLists)
                    logger.info(
                        f"GM: {team.name} cut {player.name} "
                        f"({count} votes, p={probability:.0%})"
                    )
                else:
                    outcome = "failed_roll"

                playerName = player.name if player else f"Player#{playerId}"
                self.voteRepo.recordResult(
                    teamId=team.id, season=season, voteType="cut_player",
                    targetPlayerId=playerId, totalVotes=count,
                    threshold=threshold, probability=probability,
                    outcome=outcome,
                )
                results.append({
                    "teamId": team.id, "teamName": team.name,
                    "voteType": "cut_player", "targetPlayerName": playerName,
                    "totalVotes": count, "threshold": threshold,
                    "probability": probability, "outcome": outcome,
                })
        return results

    # ── Sign FA (Ranked Choice Voting) ──────────────────────────────────

    def resolveSignFaVotes(self, teams, season: int,
                           freeAgentLists: Dict,
                           teamOpenPositions: Dict) -> Dict[int, List[int]]:
        """Resolve sign_fa ballots via ranked choice voting.

        Returns {teamId: [playerId, ...]} directives for the FA draft.
        Directives are player IDs the team should prioritize signing.
        """
        directives: Dict[int, List[int]] = {}

        for team in teams:
            ballots = self.ballotRepo.getRankingsForTeam(team.id, season)
            totalBallots = len(ballots)
            if totalBallots == 0:
                continue

            engagedFans = self.voteRepo.getEngagedVoterCount(team.id, season)
            threshold = self.calculateThreshold(engagedFans, "sign_fa")
            probability = self.calculateProbability(totalBallots, threshold)

            if probability == 0.0:
                self.voteRepo.recordResult(
                    teamId=team.id, season=season, voteType="sign_fa",
                    totalVotes=totalBallots, threshold=threshold,
                    probability=0.0, outcome="below_threshold",
                )
                continue

            if not self._rollSuccess(probability):
                self.voteRepo.recordResult(
                    teamId=team.id, season=season, voteType="sign_fa",
                    totalVotes=totalBallots, threshold=threshold,
                    probability=probability, outcome="failed_roll",
                )
                continue

            # RCV succeeded — tally full ranking per open position
            openPositions = teamOpenPositions.get(team.id, [])
            positionRankings = {}
            for pos in openPositions:
                ranked = self._tallyFullRanking(ballots, pos, freeAgentLists)
                if ranked:
                    positionRankings.setdefault(pos, []).extend(ranked)

            # Interleave: first picks from all positions, then second picks, etc.
            teamDirectives = []
            uniquePositions = list(dict.fromkeys(openPositions))
            maxDepth = max((len(positionRankings.get(p, [])) for p in uniquePositions), default=0)
            for depth in range(maxDepth):
                for pos in uniquePositions:
                    ranked = positionRankings.get(pos, [])
                    if depth < len(ranked) and ranked[depth] not in teamDirectives:
                        teamDirectives.append(ranked[depth])

            if teamDirectives:
                directives[team.id] = teamDirectives

            self.voteRepo.recordResult(
                teamId=team.id, season=season, voteType="sign_fa",
                totalVotes=totalBallots, threshold=threshold,
                probability=probability, outcome="success",
                details=json.dumps({"directives": teamDirectives}),
            )
            logger.info(
                f"GM: {team.name} FA directives: {teamDirectives} "
                f"({totalBallots} ballots, p={probability:.0%})"
            )

        return directives

    def _tallyFullRanking(self, ballots: List[List[int]], position: int,
                          freeAgentLists: Dict) -> List[int]:
        """Run repeated IRV for a position to produce a full ranking of candidates."""
        ranking = []
        excluded = []
        while True:
            winner = self._tallyRankedChoice(ballots, position, freeAgentLists,
                                              alreadyPicked=excluded)
            if winner is None:
                break
            ranking.append(winner)
            excluded.append(winner)
        return ranking

    def _tallyRankedChoice(self, ballots: List[List[int]], position: int,
                            freeAgentLists: Dict,
                            alreadyPicked: List[int]) -> Optional[int]:
        """Run instant-runoff for a single position. Returns winner player ID or None."""
        # Get all FA player IDs at this position
        faAtPosition = set()
        for posKey, players in freeAgentLists.items():
            for p in players:
                if getattr(p, 'position', None) is not None and p.position.value == position and p.id not in alreadyPicked:
                    faAtPosition.add(p.id)

        if not faAtPosition:
            return None

        # Filter out players that don't appear on enough ballots
        totalBallots = len(ballots)
        if totalBallots > 0:
            appearanceCounts: Dict[int, int] = {}
            for ranking in ballots:
                seen = set()
                for pid in ranking:
                    if pid in faAtPosition and pid not in seen:
                        appearanceCounts[pid] = appearanceCounts.get(pid, 0) + 1
                        seen.add(pid)
            minAppearances = max(1, math.ceil(totalBallots * GM_FA_MIN_APPEARANCE_PCT))
            faAtPosition = {pid for pid in faAtPosition
                           if appearanceCounts.get(pid, 0) >= minAppearances}
            if not faAtPosition:
                return None

        # Filter ballots to only include eligible candidates at this position
        activeBallots = []
        for ranking in ballots:
            filtered = [pid for pid in ranking if pid in faAtPosition]
            if filtered:
                activeBallots.append(filtered)

        if not activeBallots:
            return None

        eliminated = set()

        while True:
            # Count first-choice votes
            firstChoiceCounts: Dict[int, int] = {}
            for ballot in activeBallots:
                for pid in ballot:
                    if pid not in eliminated:
                        firstChoiceCounts[pid] = firstChoiceCounts.get(pid, 0) + 1
                        break

            if not firstChoiceCounts:
                return None

            totalActive = sum(firstChoiceCounts.values())
            majority = totalActive / 2.0

            # Check for majority winner
            for pid, count in firstChoiceCounts.items():
                if count > majority:
                    return pid

            # If only one candidate left, they win
            if len(firstChoiceCounts) == 1:
                return next(iter(firstChoiceCounts))

            # Eliminate candidate with fewest first-choice votes
            minVotes = min(firstChoiceCounts.values())
            # Break ties by eliminating all tied-lowest candidates
            toEliminate = [pid for pid, c in firstChoiceCounts.items() if c == minVotes]
            eliminated.update(toEliminate)

    # ── Helpers ─────────────────────────────────────────────────────────

    @staticmethod
    def _findPlayerOnTeam(team, playerId: int):
        """Find a player on a team's roster by ID."""
        roster = getattr(team, 'roster', None)
        if roster is None:
            return None
        for player in roster:
            if player.id == playerId:
                return player
        return None
