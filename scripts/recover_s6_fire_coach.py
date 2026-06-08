"""One-off recovery: re-run fire_coach + hire_coach resolution for season 6.

Background: during the s6 offseason, _resolveGmFireCoachVotes committed
nothing (gm_vote_results has zero s6 fire_coach rows despite raw votes in
gm_votes). The most likely cause is a SQLite write-lock contention that
silently rolled the session back inside the except handler. Cut votes ran
in their own session and committed fine, which is why those teams' rosters
look correct but the coaches still match preseason.

This script re-runs the resolution ONLY for teams whose s6 raw fire vote
count meets/exceeds threshold AND who do not already have a fire_coach
result row recorded for s6. Idempotent: re-running won't duplicate work.

Usage (production):
    fly ssh sftp shell
    put scripts/recover_s6_fire_coach.py /data/recover_s6_fire_coach.py
    exit
    fly ssh console
    cd /data
    # Optional backup:
    python3 -c "import sqlite3; src=sqlite3.connect('/data/floosball.db'); dst=sqlite3.connect('/data/floosball.db.pres6firerecovery'); src.backup(dst); src.close(); dst.close()"
    python3 /data/recover_s6_fire_coach.py

After running:
- gm_vote_results has fire_coach + hire_coach rows for affected teams.
- Team.coach_id realigned to the newly hired coach (single source of truth).
- App restart will load the correct in-memory coach via _loadCoachFromDatabase.

Schema note: as of the single-source-of-truth refactor, coaches.team_id no
longer exists. This script only writes teams.coach_id. If the legacy column
is still present (pre-migration boot), it stays untouched — the migration
will drop it cleanly when the app next starts.
"""

import os
import sqlite3
from collections import defaultdict
from datetime import datetime

DB_PATH = os.environ.get('FLOOSBALL_DB', '/data/floosball.db')
SEASON = 6

# Threshold matches gmManager.calculateThreshold: ceil(fanCount * 0.6),
# with low-quorum exceptions removed for prod safety. We trust whatever
# threshold the resolver would have computed by recomputing it from
# user counts here. If a team's fan count snapshot is missing we fall
# back to the historical resolver threshold of max(2, ceil(0.6 * voters)).
import math


def calcThreshold(fanCount):
    return max(2, math.ceil(fanCount * 0.6))


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # 1. Find s6 fire_coach votes by team
    cur.execute(
        "SELECT team_id, COUNT(*) AS cnt FROM gm_votes "
        "WHERE season = ? AND vote_type = 'fire_coach' GROUP BY team_id",
        (SEASON,),
    )
    fireVotesByTeam = {row['team_id']: row['cnt'] for row in cur.fetchall()}
    if not fireVotesByTeam:
        print(f'No s{SEASON} fire_coach votes found. Nothing to do.')
        conn.close()
        return

    # 2. Skip teams that already have a fire_coach result row
    cur.execute(
        "SELECT team_id FROM gm_vote_results "
        "WHERE season = ? AND vote_type = 'fire_coach'",
        (SEASON,),
    )
    alreadyResolved = {row['team_id'] for row in cur.fetchall()}

    teamsToProcess = {
        tid: cnt for tid, cnt in fireVotesByTeam.items()
        if tid not in alreadyResolved
    }
    if not teamsToProcess:
        print(f'All s{SEASON} fire_coach votes already have result rows. Nothing to do.')
        conn.close()
        return

    print(f'Found {len(teamsToProcess)} team(s) with unresolved s{SEASON} fire votes:')

    # 3. Determine fan count per team (for threshold calc). We use the
    # gm_team_fan_snapshots table if present; otherwise count distinct
    # users who cast any vote for the team this season.
    fanCountByTeam = {}
    try:
        cur.execute(
            "SELECT team_id, fan_count FROM gm_team_fan_snapshots WHERE season = ?",
            (SEASON,),
        )
        for row in cur.fetchall():
            fanCountByTeam[row['team_id']] = row['fan_count']
    except sqlite3.OperationalError:
        pass

    for teamId in teamsToProcess:
        if teamId not in fanCountByTeam:
            cur.execute(
                "SELECT COUNT(DISTINCT user_id) AS c FROM gm_votes "
                "WHERE team_id = ? AND season = ?",
                (teamId, SEASON),
            )
            fanCountByTeam[teamId] = cur.fetchone()['c'] or 0

    now = datetime.utcnow().isoformat()
    firedTeams = []

    for teamId, voteCount in sorted(teamsToProcess.items()):
        fanCount = fanCountByTeam.get(teamId, 0)
        threshold = calcThreshold(fanCount)
        cur.execute("SELECT name FROM teams WHERE id = ?", (teamId,))
        row = cur.fetchone()
        teamName = row['name'] if row else f'team_id={teamId}'

        if voteCount < threshold:
            outcome = 'below_threshold'
            print(f'  {teamName}: {voteCount}/{threshold} -> {outcome}')
        else:
            outcome = 'success'
            print(f'  {teamName}: {voteCount}/{threshold} -> {outcome}')
            firedTeams.append((teamId, teamName))

        # Record the fire_coach result row
        cur.execute(
            "INSERT INTO gm_vote_results "
            "(team_id, season, vote_type, target_player_id, total_votes, "
            " threshold, success_probability, outcome, resolved_at) "
            "VALUES (?, ?, 'fire_coach', NULL, ?, ?, ?, ?, ?)",
            (teamId, SEASON, voteCount, threshold,
             1.0 if outcome == 'success' else voteCount / max(1, threshold),
             outcome, now),
        )

        if outcome != 'success':
            continue

        # The fire itself is just "set Team.coach_id = NULL" (single source
        # of truth — no Coach.team_id to maintain anymore). Old coach's row
        # becomes naturally unassigned because no Team.coach_id points at it.
        cur.execute("SELECT coach_id FROM teams WHERE id = ?", (teamId,))
        currentRow = cur.fetchone()
        if currentRow and currentRow['coach_id']:
            print(f'    fire: clear teams.coach_id (was {currentRow["coach_id"]})')
            cur.execute("UPDATE teams SET coach_id = NULL WHERE id = ?", (teamId,))

    # 4. Hire phase — pick winning candidate per fired team
    for teamId, teamName in firedTeams:
        cur.execute(
            "SELECT coach_id FROM coach_candidates WHERE team_id = ? AND season = ?",
            (teamId, SEASON),
        )
        candidateRows = cur.fetchall()
        candidateIds = [row['coach_id'] for row in candidateRows]
        if not candidateIds:
            # No candidate slate generated — fall back to highest-rated
            # unassigned coach. "Unassigned" = no team has them as coach_id.
            cur.execute(
                "SELECT id, name, overall_rating FROM coaches "
                "WHERE id NOT IN (SELECT coach_id FROM teams WHERE coach_id IS NOT NULL) "
                "ORDER BY overall_rating DESC LIMIT 1"
            )
            fb = cur.fetchone()
            if not fb:
                print(f'  {teamName}: no candidates and no unassigned coaches — '
                      f'team left coachless (boot safety net will generate one).')
                continue
            winnerId = fb['id']
            winnerName = fb['name']
            print(f'    hire (fallback): {winnerName} (no candidates)')
        else:
            # Tally hire_coach votes for this team's candidates
            cur.execute(
                "SELECT target_player_id, COUNT(*) AS cnt FROM gm_votes "
                "WHERE team_id = ? AND season = ? AND vote_type = 'hire_coach' "
                "AND target_player_id IN (%s) GROUP BY target_player_id"
                % ','.join('?' * len(candidateIds)),
                [teamId, SEASON] + candidateIds,
            )
            votesByCand = {row['target_player_id']: row['cnt']
                           for row in cur.fetchall()}

            if votesByCand:
                # Plurality wins; lowest coach_id breaks ties.
                winnerId = min(
                    sorted(votesByCand.items(), key=lambda x: (-x[1], x[0]))
                )[0]
                reason = 'vote_winner'
            else:
                # No votes — pick highest overall_rating candidate.
                placeholders = ','.join('?' * len(candidateIds))
                cur.execute(
                    f"SELECT id, name, overall_rating FROM coaches "
                    f"WHERE id IN ({placeholders}) "
                    f"ORDER BY overall_rating DESC, id ASC LIMIT 1",
                    candidateIds,
                )
                pick = cur.fetchone()
                winnerId = pick['id']
                reason = 'no_votes_default_best'

            cur.execute("SELECT name FROM coaches WHERE id = ?", (winnerId,))
            winnerName = cur.fetchone()['name']
            print(f'    hire: {winnerName} ({reason}, '
                  f'votes={votesByCand.get(winnerId, 0)})')

            # Write hire_coach result rows for the entire slate
            for cId in candidateIds:
                count = votesByCand.get(cId, 0)
                isWinner = (cId == winnerId)
                outcome = 'success' if isWinner else 'trailing'
                cur.execute(
                    "INSERT INTO gm_vote_results "
                    "(team_id, season, vote_type, target_player_id, total_votes, "
                    " threshold, success_probability, outcome, resolved_at) "
                    "VALUES (?, ?, 'hire_coach', ?, ?, 0, ?, ?, ?)",
                    (teamId, SEASON, cId, count,
                     1.0 if isWinner else 0.0, outcome, now),
                )

        # Single write — point the team at the winner. With Coach.team_id
        # gone, this is the only place that "what coach does this team have"
        # is stored, so the hire takes effect atomically.
        cur.execute(
            "UPDATE teams SET coach_id = ? WHERE id = ?", (winnerId, teamId)
        )

        # Clear remaining candidates' rows so the slate isn't reused next season
        cur.execute(
            "DELETE FROM coach_candidates WHERE team_id = ? AND season = ?",
            (teamId, SEASON),
        )

    conn.commit()
    conn.close()
    print()
    print('Recovery complete. Restart the app to load the new coaches into memory.')


if __name__ == '__main__':
    main()
