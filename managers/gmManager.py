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
    GM_PASS_FRACTION,
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
        """Threshold = a majority of the team's active fanbase.

        A fire / resign / cut directive passes when its net vote tally
        (yea − nay) reaches ``ceil(teamFanCount × GM_PASS_FRACTION)`` — a
        majority of the fanbase, not the whole of it. The bar moves with the
        size of the fanbase, not with how actively those fans vote, so it
        never punishes participation: a large turnout doesn't suddenly need a
        mountain of votes just because more people showed up.

        Under single-vote each fan contributes at most one net vote per
        target (yea or nay, withdraw to change), so clearing the bar means a
        clear majority of the fanbase is pulling the same direction. (At
        GM_PASS_FRACTION = 1.0 this collapses back to near-unanimity.)

        Low-quorum / test mode keeps the threshold at 1.

        voteType is unused — kept in the signature for caller compatibility.
        """
        if self._lowQuorum:
            return 1
        return max(1, math.ceil(teamFanCount * GM_PASS_FRACTION))

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
        # votes is the NET tally (for - against) and can be negative when
        # opposition outweighs support; clamp so the meter floors at empty.
        return max(0.0, min(1.0, votes / threshold))

    @staticmethod
    def _rollSuccess(probability: float) -> bool:
        return random.random() < probability

    @staticmethod
    def _tallyByTargetDirection(votes) -> Tuple[Dict[int, int], Dict[int, int]]:
        """Split a vote list into (votesFor, votesAgainst) dicts keyed by
        target_player_id, for the per-target net threshold directives."""
        votesFor: Dict[int, int] = {}
        votesAgainst: Dict[int, int] = {}
        for v in votes:
            if not v.target_player_id:
                continue
            if (getattr(v, 'direction', 'yea') or 'yea') == 'nay':
                votesAgainst[v.target_player_id] = votesAgainst.get(v.target_player_id, 0) + 1
            else:
                votesFor[v.target_player_id] = votesFor.get(v.target_player_id, 0) + 1
        return votesFor, votesAgainst

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
            if not votes:
                continue
            yeaVotes = sum(1 for v in votes if (getattr(v, 'direction', 'yea') or 'yea') != 'nay')
            nayVotes = len(votes) - yeaVotes
            netVotes = yeaVotes - nayVotes

            fanCount = self.voteRepo.getTeamFanCount(team.id, season=season)
            threshold = self.calculateThreshold(fanCount)
            probability = self.calculateProbability(netVotes, threshold)

            if netVotes < threshold:
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
                    f"({yeaVotes} for / {nayVotes} against, net {netVotes} of {threshold} required)"
                )

            self.voteRepo.recordResult(
                teamId=team.id, season=season, voteType="fire_coach",
                totalVotes=yeaVotes, votesAgainst=nayVotes, threshold=threshold,
                probability=probability, outcome=outcome,
            )
            results.append({
                "teamId": team.id, "teamName": team.name,
                "voteType": "fire_coach", "totalVotes": yeaVotes,
                "votesAgainst": nayVotes, "threshold": threshold,
                "probability": probability, "outcome": outcome,
            })
        return results, firedTeamIds

    # ── Hire Coach ─────────────────────────────────────────────────────

    def resolveHireCoachVotes(self, teams, season: int,
                              teamManager, firedTeamIds: set) -> List[Dict]:
        """Resolve hire_coach votes for teams that fired or lost their coach.

        Per-team candidate model (replaces shared coach pool):
          - Each team has its own 3-coach candidate slate (CoachCandidate
            rows), generated lazily when the team needs to hire.
          - Votes target coach IDs within that team's slate.
          - **Plurality wins, period.** No tier order, no cross-team
            contention, no fallthrough to other teams' candidates.
          - Ties broken by lowest coach ID for stability.
          - If no votes were cast, the highest-rated candidate wins by
            default (better than auto-pick — the user already saw all
            candidates and just didn't engage).

        After resolution, the team's losing candidates are deleted and
        their names returned to the unused-name pool.
        """
        from database.models import CoachCandidate
        results = []

        firedTeams = [t for t in teams if t.id in firedTeamIds]
        # Sort by team_id for stable result ordering — priority no longer
        # matters since each team's candidate slate is isolated.
        firedTeams.sort(key=lambda t: t.id)

        for team in firedTeams:
            # Pull (or lazily generate) this team's candidate slate.
            candidates = teamManager.getCoachCandidates(team, season, session=self.session)
            if not candidates:
                # No candidates and we couldn't generate any (e.g. empty
                # name pool) — fall back to the legacy auto-pick path so
                # the team still gets a coach. deferSave so we don't
                # contend with the outer write lock; seasonManager
                # commits the session and saves names once at the end.
                newCoach = teamManager.generateCoach(deferSave=True)
                teamManager.hireCoach(team, newCoach, session=self.session)
                logger.warning(
                    f"GM: {team.name} auto-hired {newCoach.name} "
                    f"(no candidates available)"
                )
                continue

            candidateById = {c.coach_id: c for c in candidates}
            candidateIds = set(candidateById.keys())
            # Capture candidate names NOW, while their Coach rows still exist.
            # clearCoachCandidates() below DELETES every losing candidate's Coach
            # row, after which `cand.coach` lazy-loads as None and reading
            # `cand.coach.name` raises 'NoneType' has no attribute 'name' — which
            # rolled back the whole fire/hire transaction (coaches silently never
            # got fired despite passing votes).
            candNamesById = {c.coach_id: (c.coach.name if c.coach else None) for c in candidates}

            votes = self.voteRepo.getVotesForTeam(team.id, season, "hire_coach")
            votesByTarget: Dict[int, int] = {}
            for v in votes:
                # Only count votes targeting this team's own candidates.
                # Stale votes from before the slate was generated are ignored.
                if v.target_player_id and v.target_player_id in candidateIds:
                    votesByTarget[v.target_player_id] = (
                        votesByTarget.get(v.target_player_id, 0) + 1
                    )

            # Pick winner. With votes: highest plurality wins (ties broken
            # by lowest coach_id). Without votes: highest-rated candidate
            # wins by default since the user has already seen them all.
            if votesByTarget:
                winnerId = min(
                    sorted(votesByTarget.items(), key=lambda x: (-x[1], x[0])),
                    key=lambda x: (-x[1], x[0]),
                )[0]
                winnerVotes = votesByTarget[winnerId]
                reason = "vote_winner"
            else:
                # Default: pick highest overall_rating among candidates
                rankedCands = sorted(
                    candidates,
                    key=lambda c: (-c.coach.overall_rating, c.coach_id),
                )
                winnerId = rankedCands[0].coach_id
                winnerVotes = 0
                reason = "no_votes_default_best"

            winnerCandidate = candidateById[winnerId]
            winnerName = candNamesById.get(winnerId)

            # Hire the winning candidate. `hireCoachFromPool` flips
            # Team.coach_id and builds the in-memory Coach on the team.
            hired = teamManager.hireCoachFromPool(team, winnerId, session=self.session)
            if not hired:
                logger.warning(
                    f"GM: {team.name} winner {winnerName} hire failed — "
                    f"falling back to auto-generated coach"
                )
                newCoach = teamManager.generateCoach(deferSave=True)
                teamManager.hireCoach(team, newCoach, session=self.session)
                # Clear the entire slate since none was used. Defer the
                # name-pool write — the seasonManager driver issues a
                # single saveUnusedNames after committing this session
                # so we don't fight the outer write lock per-team.
                teamManager.clearCoachCandidates(
                    team.id, season, keepCoachId=None, session=self.session,
                    deferNameSave=True,
                )
                continue

            # Clear the losing candidates: delete rows + return names to pool.
            # Defer the name-pool save for the same reason as above.
            teamManager.clearCoachCandidates(
                team.id, season, keepCoachId=winnerId, session=self.session,
                deferNameSave=True,
            )

            logger.info(
                f"GM: {team.name} hired {winnerName} ({winnerVotes} votes, {reason})"
            )

            # Record results for the winner and each other candidate so the
            # offseason recap can show vote totals across the slate.
            for cand in candidates:
                coachId = cand.coach_id
                count = votesByTarget.get(coachId, 0)
                isWinner = (coachId == winnerId)
                outcome = "success" if isWinner else "trailing"
                self.voteRepo.recordResult(
                    teamId=team.id, season=season, voteType="hire_coach",
                    targetPlayerId=coachId, totalVotes=count,
                    threshold=0, probability=1.0 if isWinner else 0.0,
                    outcome=outcome,
                )
                results.append({
                    "teamId": team.id, "teamName": team.name,
                    "voteType": "hire_coach",
                    "targetPlayerName": candNamesById.get(cand.coach_id),
                    "totalVotes": count, "threshold": 0,
                    "probability": 1.0 if isWinner else 0.0,
                    "outcome": outcome,
                })

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

            # Group votes by target player, split by direction.
            votesFor, votesAgainst = self._tallyByTargetDirection(votes)

            fanCount = self.voteRepo.getTeamFanCount(team.id, season=season)
            threshold = self.calculateThreshold(fanCount)

            for playerId in set(votesFor) | set(votesAgainst):
                yea = votesFor.get(playerId, 0)
                nay = votesAgainst.get(playerId, 0)
                net = yea - nay
                probability = self.calculateProbability(net, threshold)
                player = self._findPlayerOnTeam(team, playerId)

                if player is None:
                    outcome = "ineligible"
                elif not hasattr(player, 'termRemaining') or player.termRemaining != 1:
                    outcome = "ineligible"
                elif getattr(player, 'willRetire', False):
                    # Player has already announced retirement — no resign possible.
                    outcome = "retiring"
                elif net < threshold:
                    outcome = "below_threshold"
                else:
                    outcome = "success"
                    player._gmResigned = True
                    logger.info(
                        f"GM: {team.name} re-signing {player.name} "
                        f"({yea} for / {nay} against, net {net} of {threshold} required)"
                    )

                playerName = player.name if player else f"Player#{playerId}"
                self.voteRepo.recordResult(
                    teamId=team.id, season=season, voteType="resign_player",
                    targetPlayerId=playerId, totalVotes=yea, votesAgainst=nay,
                    threshold=threshold, probability=probability,
                    outcome=outcome,
                )
                results.append({
                    "teamId": team.id, "teamName": team.name,
                    "voteType": "resign_player", "targetPlayerName": playerName,
                    "totalVotes": yea, "votesAgainst": nay, "threshold": threshold,
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

            votesFor, votesAgainst = self._tallyByTargetDirection(votes)

            fanCount = self.voteRepo.getTeamFanCount(team.id, season=season)
            threshold = self.calculateThreshold(fanCount)

            for playerId in set(votesFor) | set(votesAgainst):
                yea = votesFor.get(playerId, 0)
                nay = votesAgainst.get(playerId, 0)
                net = yea - nay
                probability = self.calculateProbability(net, threshold)
                player = self._findPlayerOnTeam(team, playerId)

                if player is None:
                    outcome = "ineligible"
                elif net < threshold:
                    outcome = "below_threshold"
                else:
                    outcome = "success"
                    # Release player to FA pool
                    playerManager.releasePlayerToFreeAgency(player, team, freeAgentLists)
                    logger.info(
                        f"GM: {team.name} cut {player.name} "
                        f"({yea} for / {nay} against, net {net} of {threshold} required)"
                    )

                playerName = player.name if player else f"Player#{playerId}"
                self.voteRepo.recordResult(
                    teamId=team.id, season=season, voteType="cut_player",
                    targetPlayerId=playerId, totalVotes=yea, votesAgainst=nay,
                    threshold=threshold, probability=probability,
                    outcome=outcome,
                )
                results.append({
                    "teamId": team.id, "teamName": team.name,
                    "voteType": "cut_player", "targetPlayerName": playerName,
                    "targetPlayerId": playerId,
                    "targetPosition": (player.position.name if player and getattr(player, 'position', None) else None),
                    "targetRating": (getattr(player, 'playerRating', None) if player else None),
                    "targetTier": (player.playerTier.name if player and getattr(player, 'playerTier', None) else None),
                    "totalVotes": yea, "votesAgainst": nay, "threshold": threshold,
                    "probability": probability, "outcome": outcome,
                })
        return results

    # ── Sign FA (Ranked Choice Voting) ──────────────────────────────────

    def _aggregatePositionPriorities(self, priorities: List[List[int]]) -> List[int]:
        """Borda-count fans' position-fill orderings into one team order.

        Each ballot ranks positions best-first; a ranking of N awards (N - index)
        points to each position. Returns position values (1-5) sorted by total
        points desc (tie-break: more appearances, then position value) — the
        order the FA-draft fallback fills open slots when voted players run out.
        Positions no fan ranked are omitted; empty input -> []."""
        if not priorities:
            return []
        scores: Dict[int, float] = {}
        appearances: Dict[int, int] = {}
        for ranking in priorities:
            n = len(ranking)
            seen = set()
            for idx, pos in enumerate(ranking):
                if pos in seen:
                    continue
                seen.add(pos)
                scores[pos] = scores.get(pos, 0) + (n - idx)
                appearances[pos] = appearances.get(pos, 0) + 1
        return sorted(scores.keys(),
                      key=lambda p: (-scores[p], -appearances.get(p, 0), p))

    def resolveSignFaVotes(self, teams, season: int,
                           freeAgentLists: Dict,
                           teamOpenPositions: Dict) -> Tuple[Dict[int, List[int]], Dict[int, List[int]], Dict[int, List[int]]]:
        """Resolve sign_fa ballots via overall ranked-choice voting.

        Single-list IRV across all candidates whose position is currently
        open for the team — the order encodes both who and which position
        the team should pursue first. The directive walks the resolved
        ranking and assigns each player to the first remaining open slot
        at their position; players whose positions are already filled get
        skipped — so a single ballot resolution can sign MULTIPLE FAs when
        several positions are open.

        NO THRESHOLD: this isn't a pass/fail vote — it's "who do the fans
        want?". Any ballots at all (even one) resolve via IRV to a ranked list
        of available targets, and the team pursues them in that priority order.
        The result is surfaced as that ranked target list, not a ratify tally.

        Returns:
          - directives: {teamId: [playerId, ...]} the slot-walk-trimmed
            sign list used by the FA draft.
          - overallRankings: {teamId: [playerId, ...]} the full IRV
            ranking before slot-walking, for tally display.
          - positionPriorities: {teamId: [posVal, ...]} the fan-aggregated
            order to fill open slots once the voted players run out (drives
            the FA-draft best-available fallback instead of pure rating).
        """
        directives: Dict[int, List[int]] = {}
        overallRankingsByTeam: Dict[int, List[int]] = {}
        positionPrioritiesByTeam: Dict[int, List[int]] = {}

        # Position-value → name lookup for slot-fill bookkeeping.
        for team in teams:
            ballots = self.ballotRepo.getRankingsForTeam(team.id, season)
            totalBallots = len(ballots)
            if totalBallots == 0:
                continue

            openPositions = teamOpenPositions.get(team.id, [])
            if not openPositions:
                continue

            # Fan-aggregated position fill order (used only by the best-available
            # fallback in the FA draft, once voted players are exhausted).
            posPriorities = self.ballotRepo.getPositionPrioritiesForTeam(team.id, season)
            aggPriority = self._aggregatePositionPriorities(posPriorities)
            if aggPriority:
                positionPrioritiesByTeam[team.id] = aggPriority

            # Eligible candidates: all FAs at any open position, plus team's
            # own prospects at any open position. Prospects share ID space.
            openPosSet = set(openPositions)
            eligibleCandidates: set = set()
            for posKey, players in freeAgentLists.items():
                for p in players:
                    posVal = getattr(getattr(p, 'position', None), 'value', None)
                    if posVal in openPosSet:
                        eligibleCandidates.add(p.id)
            for prospect in getattr(team, 'prospects', []):
                posVal = getattr(getattr(prospect, 'position', None), 'value', None)
                if posVal in openPosSet:
                    eligibleCandidates.add(prospect.id)

            overallRanking = self._tallyFullRankingOverall(ballots, eligibleCandidates)
            if overallRanking:
                overallRankingsByTeam[team.id] = list(overallRanking)

            # NO THRESHOLD: a ranked-choice FA requisition isn't pass/fail — it's
            # "who do the fans want?". ANY ballots (even one) resolve. IRV
            # (_tallyFullRankingOverall) produces a full ranking over the AVAILABLE
            # candidates only — unavailable players are excluded from
            # eligibleCandidates, so an unavailable top choice naturally falls
            # through to the next vote-getter. The slot-walk below signs down that
            # ranking into open slots (multiple FAs when several positions are open).

            # Slot-walk: each player in the ranking consumes one open slot
            # at their position. Once a position runs out of slots, further
            # candidates at that position are skipped (the team has filled
            # its need there).
            remainingSlots: Dict[int, int] = {}
            for pos in openPositions:
                remainingSlots[pos] = remainingSlots.get(pos, 0) + 1

            playerLookup = {}
            for posKey, players in freeAgentLists.items():
                for p in players:
                    playerLookup[p.id] = p
            for prospect in getattr(team, 'prospects', []):
                playerLookup[prospect.id] = prospect

            teamDirectives = []
            for pid in overallRanking:
                p = playerLookup.get(pid)
                if not p:
                    continue
                posVal = getattr(getattr(p, 'position', None), 'value', None)
                if posVal is None or remainingSlots.get(posVal, 0) <= 0:
                    continue
                teamDirectives.append(pid)
                remainingSlots[posVal] -= 1

            if teamDirectives:
                directives[team.id] = teamDirectives

            # Priority-ordered target list for the Front Office display — the FA
            # requisition is shown as a ranked list of who the team is pursuing,
            # not a pass/fail tally. threshold=0 / probability=1.0 signals "no
            # threshold" (same convention as the plurality hire_coach result).
            targetList = []
            for pid in teamDirectives:
                p = playerLookup.get(pid)
                if p:
                    targetList.append({
                        'id': pid,
                        'name': getattr(p, 'name', f'Player {pid}'),
                        'position': getattr(getattr(p, 'position', None), 'value', None),
                    })

            self.voteRepo.recordResult(
                teamId=team.id, season=season, voteType="sign_fa",
                totalVotes=totalBallots, threshold=0,
                probability=1.0, outcome="success",
                details=json.dumps({"directives": teamDirectives, "targets": targetList}),
            )
            logger.info(
                f"GM: {team.name} FA targets (priority order): {teamDirectives} "
                f"({totalBallots} ballots)"
            )

        return directives, overallRankingsByTeam, positionPrioritiesByTeam

    def _tallyFullRankingOverall(self, ballots: List[List[int]],
                                 eligibleCandidates: set) -> List[int]:
        """Run repeated IRV across the full eligible candidate pool to produce
        a single overall ranking. Order encodes both who and which position
        a team should pursue — fans whose top picks cluster on one position
        implicitly vote for that position as the priority.
        """
        ranking = []
        excluded: List[int] = []
        while True:
            winner = self._tallyRankedChoiceOverall(
                ballots, eligibleCandidates, alreadyPicked=excluded,
            )
            if winner is None:
                break
            ranking.append(winner)
            excluded.append(winner)
        return ranking

    def _tallyRankedChoiceOverall(self, ballots: List[List[int]],
                                   eligibleCandidates: set,
                                   alreadyPicked: List[int]) -> Optional[int]:
        """Single-pass IRV across the full eligible candidate pool.

        Same rules as `_tallyRankedChoice` (majority winner, eliminate
        lowest, ties eliminate together) but candidate eligibility is
        determined by membership in `eligibleCandidates` rather than by
        position. Filters ballots to only the still-active candidates.
        """
        active = {pid for pid in eligibleCandidates if pid not in alreadyPicked}
        if not active:
            return None

        totalBallots = len(ballots)
        if totalBallots > 0:
            appearanceCounts: Dict[int, int] = {}
            for ranking in ballots:
                seen = set()
                for pid in ranking:
                    if pid in active and pid not in seen:
                        appearanceCounts[pid] = appearanceCounts.get(pid, 0) + 1
                        seen.add(pid)
            minAppearances = max(1, math.ceil(totalBallots * GM_FA_MIN_APPEARANCE_PCT))
            active = {pid for pid in active
                      if appearanceCounts.get(pid, 0) >= minAppearances}
            if not active:
                return None

        activeBallots = []
        for ranking in ballots:
            filtered = [pid for pid in ranking if pid in active]
            if filtered:
                activeBallots.append(filtered)

        if not activeBallots:
            return None

        eliminated: set = set()
        while True:
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
            for pid, count in firstChoiceCounts.items():
                if count > majority:
                    return pid

            if len(firstChoiceCounts) == 1:
                return next(iter(firstChoiceCounts))

            minVotes = min(firstChoiceCounts.values())
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
