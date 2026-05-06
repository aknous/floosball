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

    def calculateThreshold(self, teamFanCount: int, voteType: str = None) -> int:
        """Threshold = the team's total fan count.

        A fire / resign / cut directive passes when its vote tally meets or
        exceeds the number of fans that team has. The bar moves with the
        size of the fanbase, not with how actively those fans vote — that
        keeps the math from punishing participation. A small turnout that
        spends a few votes each can pass; a large turnout doesn't suddenly
        need a mountain of votes just because more people showed up.

        Each fan can still cast multiple votes (GM_VOTES_PER_TYPE) for
        emphasis. Roughly: "every fan kicking in one vote" hits the
        threshold; smaller groups can hit it with multi-votes.

        Low-quorum / test mode keeps the threshold at 1.

        voteType is unused — kept in the signature for caller compatibility.
        """
        if self._lowQuorum:
            return 1
        return max(1, teamFanCount)

    def calculateBallotThreshold(self, engagedFanCount: int) -> int:
        """Threshold for sign_fa ballots (ranked-choice).

        Sign_fa is a different mechanic — fans submit ranked-choice ballots
        rather than discrete votes — so it sticks to the original engaged-
        fan-based threshold instead of the majority-of-cast-votes rule
        used by fire/resign/cut.
        """
        weight = GM_VOTE_WEIGHT.get("sign_fa", 1.0)
        baseMin = 1 if self._lowQuorum else GM_VOTE_BASE_MIN.get("sign_fa", 2)
        return max(baseMin, math.ceil(engagedFanCount * GM_THRESHOLD_USER_FACTOR * weight))

    def hireCoachDisplay(self, votes: int, leaderVotes: int, leaderCount: int) -> Tuple[int, float]:
        """Threshold + probability for a hire_coach candidate's UI display.

        Returns (threshold, probability) where:
          - probability is the bar-fill / label percentage
          - threshold is the bar a candidate must cross for the UI's
            "Will pass" label to trigger

        Plurality resolution: most votes wins. The display has to handle
        three cases:
          - Sole leader: probability=1.0, threshold=leaderVotes → "Will pass"
          - Tied for lead: probability=votes/(leaderVotes+1), threshold=leaderVotes+1
            so the bar shows a non-100% fill and the "Will pass" label
            does not trigger (leaders are competing, not winning yet)
          - Trailing: probability=votes/threshold against the same gating
            threshold, scaled down so they read as "behind"

        Zero leaderVotes (no votes at all) returns (1, 0.0) so the meter
        is empty and the auto-pick fires when resolution runs.
        """
        if leaderVotes <= 0:
            return 1, 0.0
        tied = leaderCount > 1
        threshold = leaderVotes + 1 if tied else leaderVotes
        probability = min(1.0, votes / threshold) if threshold > 0 else 0.0
        return threshold, probability

    def calculateProbability(self, votes: int, threshold: int) -> float:
        """Progress toward threshold for fire_coach / resign_player / cut_player.

        Threshold-gated votes resolve deterministically: votes >= threshold
        passes, otherwise fails. The returned value is a linear progress
        meter (votes / threshold capped at 1.0) so the UI can render a
        "how close are we?" bar. At 1.0 the vote will pass; below 1.0
        it won't. No probability roll, no "70% chance" feel.
        """
        if threshold <= 0:
            return 1.0 if votes > 0 else 0.0
        return min(1.0, votes / threshold)

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

            fanCount = self.voteRepo.getTeamFanCount(team.id)
            threshold = self.calculateThreshold(fanCount)
            probability = self.calculateProbability(totalVotes, threshold)

            if totalVotes < threshold:
                outcome = "below_threshold"
            else:
                outcome = "success"
                oldCoachName = team.coach.name if team.coach else "None"
                # Pass the gm session so fire DB write and result record share
                # one connection — without this SQLite "database is locked"
                # contention rolls back the entire resolution.
                teamManager.fireCoach(team, session=self.session)
                firedTeamIds.add(team.id)
                logger.info(
                    f"GM: {team.name} fired coach {oldCoachName} "
                    f"({totalVotes} of {threshold} required)"
                )

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

        Hire-coach is deterministic plurality: whichever candidate has the
        most votes wins, regardless of total vote count. One vote is enough
        if nobody else has more. Ties broken by lowest coach ID for
        stability. Only when zero hire votes were cast does the resolver
        fall back to an auto-pick (random generated coach).

        For each team in firedTeamIds:
        - Tally hire_coach votes by candidate
        - Pick the leader; if leader is no longer in the pool (e.g. another
          team's resolution claimed them this offseason), try the next
        - If no votes at all, generate a fallback coach
        """
        results = []
        availableCoaches = teamManager.getAvailableCoaches()
        coachNames = {c.id: c.name for c in availableCoaches}
        availableIds = {c.id for c in availableCoaches}

        for team in teams:
            if team.id not in firedTeamIds:
                continue

            votes = self.voteRepo.getVotesForTeam(team.id, season, "hire_coach")
            votesByTarget: Dict[int, int] = {}
            for v in votes:
                if v.target_player_id:
                    votesByTarget[v.target_player_id] = (
                        votesByTarget.get(v.target_player_id, 0) + 1
                    )

            leaderVotes = max(votesByTarget.values()) if votesByTarget else 0
            leaderCount = sum(1 for v in votesByTarget.values() if v == leaderVotes) if leaderVotes > 0 else 0
            hired = False
            # Sort by votes desc, then coachId asc for stable tiebreak
            ranked = sorted(
                votesByTarget.items(), key=lambda x: (-x[1], x[0])
            )
            for coachId, count in ranked:
                coachName = coachNames.get(coachId, f"Coach#{coachId}")
                threshold, displayProb = self.hireCoachDisplay(
                    count, leaderVotes, leaderCount
                )
                isLeader = (count == leaderVotes and not hired)

                if coachId not in availableIds:
                    outcome = "ineligible"
                elif isLeader:
                    if teamManager.hireCoachFromPool(team, coachId, session=self.session):
                        outcome = "success"
                        availableIds.discard(coachId)
                        hired = True
                        logger.info(
                            f"GM: {team.name} hired {coachName} by vote "
                            f"({count} votes, leader of {leaderCount})"
                        )
                    else:
                        outcome = "ineligible"
                        logger.warning(
                            f"GM: {team.name} leader {coachName} (id={coachId}) "
                            f"unavailable in pool — falling through to next"
                        )
                else:
                    outcome = "trailing"

                self.voteRepo.recordResult(
                    teamId=team.id, season=season, voteType="hire_coach",
                    targetPlayerId=coachId, totalVotes=count,
                    threshold=threshold, probability=displayProb,
                    outcome=outcome,
                )
                results.append({
                    "teamId": team.id, "teamName": team.name,
                    "voteType": "hire_coach",
                    "targetPlayerName": coachName,
                    "totalVotes": count, "threshold": threshold,
                    "probability": displayProb, "outcome": outcome,
                })

            if not hired:
                # No votes at all OR every vote target was unavailable — auto-pick
                newCoach = teamManager.generateCoach()
                teamManager.hireCoach(team, newCoach)
                reason = "no hire_coach votes" if not votesByTarget else "all candidates unavailable"
                logger.info(
                    f"GM: {team.name} auto-hired {newCoach.name} ({reason})"
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

            fanCount = self.voteRepo.getTeamFanCount(team.id)
            threshold = self.calculateThreshold(fanCount)

            for playerId, count in votesByTarget.items():
                probability = self.calculateProbability(count, threshold)
                player = self._findPlayerOnTeam(team, playerId)

                if player is None:
                    outcome = "ineligible"
                elif not hasattr(player, 'termRemaining') or player.termRemaining != 1:
                    outcome = "ineligible"
                elif getattr(player, 'willRetire', False):
                    # Player has already announced retirement — no resign possible.
                    outcome = "retiring"
                elif count < threshold:
                    outcome = "below_threshold"
                else:
                    outcome = "success"
                    player._gmResigned = True
                    logger.info(
                        f"GM: {team.name} re-signing {player.name} "
                        f"({count} of {threshold} required)"
                    )

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

            fanCount = self.voteRepo.getTeamFanCount(team.id)
            threshold = self.calculateThreshold(fanCount)

            for playerId, count in votesByTarget.items():
                probability = self.calculateProbability(count, threshold)
                player = self._findPlayerOnTeam(team, playerId)

                if player is None:
                    outcome = "ineligible"
                elif count < threshold:
                    outcome = "below_threshold"
                else:
                    outcome = "success"
                    # Release player to FA pool
                    playerManager.releasePlayerToFreeAgency(player, team, freeAgentLists)
                    logger.info(
                        f"GM: {team.name} cut {player.name} "
                        f"({count} of {threshold} required)"
                    )

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
                           teamOpenPositions: Dict) -> Tuple[Dict[int, List[int]], Dict[int, Dict[int, List[int]]]]:
        """Resolve sign_fa ballots via ranked choice voting.

        Returns:
          - directives: {teamId: [playerId, ...]} flat priority list used by
            the FA draft. Interleaves positions round-robin.
          - positionRankings: {teamId: {positionValue: [playerId, ...]}} raw
            per-position IRV rankings. Lets the UI show "for QB fans ranked:
            X, Y, Z" without the interleave collapsing the structure.
        """
        directives: Dict[int, List[int]] = {}
        positionRankingsByTeam: Dict[int, Dict[int, List[int]]] = {}

        for team in teams:
            ballots = self.ballotRepo.getRankingsForTeam(team.id, season)
            totalBallots = len(ballots)
            if totalBallots == 0:
                continue

            engagedFans = self.voteRepo.getEngagedVoterCount(team.id, season)
            threshold = self.calculateBallotThreshold(engagedFans)
            probability = self.calculateProbability(totalBallots, threshold)

            # Tally per-position rankings for EVERY team with ballots, even
            # below quorum — fans still want to see how votes shook out. The
            # threshold/roll only gate whether the directives actually drive
            # the FA draft.
            teamProspectsByPos: Dict[int, set] = {}
            for prospect in getattr(team, 'prospects', []):
                if hasattr(prospect, 'position') and hasattr(prospect.position, 'value'):
                    teamProspectsByPos.setdefault(prospect.position.value, set()).add(prospect.id)

            openPositions = teamOpenPositions.get(team.id, [])
            positionRankings = {}
            for pos in openPositions:
                ranked = self._tallyFullRanking(
                    ballots, pos, freeAgentLists,
                    prospectIds=teamProspectsByPos.get(pos, set()),
                )
                if ranked:
                    positionRankings.setdefault(pos, []).extend(ranked)
            if positionRankings:
                positionRankingsByTeam[team.id] = dict(positionRankings)

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

        return directives, positionRankingsByTeam

    def _tallyFullRanking(self, ballots: List[List[int]], position: int,
                          freeAgentLists: Dict, prospectIds: set = None) -> List[int]:
        """Run repeated IRV for a position to produce a full ranking of candidates.
        prospectIds are team-specific prospect IDs eligible for this position, which
        share the ballot pool with FAs.
        """
        ranking = []
        excluded = []
        while True:
            winner = self._tallyRankedChoice(ballots, position, freeAgentLists,
                                              alreadyPicked=excluded,
                                              prospectIds=prospectIds or set())
            if winner is None:
                break
            ranking.append(winner)
            excluded.append(winner)
        return ranking

    def _tallyRankedChoice(self, ballots: List[List[int]], position: int,
                            freeAgentLists: Dict,
                            alreadyPicked: List[int],
                            prospectIds: set = None) -> Optional[int]:
        """Run instant-runoff for a single position. Returns winner player ID or None.
        prospectIds are team-specific prospects eligible for this position, treated
        as first-class ballot candidates alongside FAs.
        """
        # Eligible candidates: FAs at this position + team's prospects at this position
        faAtPosition = set()
        for posKey, players in freeAgentLists.items():
            for p in players:
                if getattr(p, 'position', None) is not None and p.position.value == position and p.id not in alreadyPicked:
                    faAtPosition.add(p.id)
        if prospectIds:
            faAtPosition |= {pid for pid in prospectIds if pid not in alreadyPicked}

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
        rosterDict = getattr(team, 'rosterDict', None)
        if rosterDict is None:
            return None
        for player in rosterDict.values():
            if player is not None and player.id == playerId:
                return player
        return None
