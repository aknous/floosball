"""Post-deploy: compensate players whose teams trained with team.coach=None.

Background: STEP 7 offseason training uses
    devBias = round((coachDevRating - 60) / 10) + fundingDevBonus
and applies the bias to position-specific attribute roll ranges (clamped
to each player's per-attribute potential). When team.coach is None, the
default coachDevRating=50 produces devBias = -1 + funding. Their actual
coach (typically 75–85) would have produced devBias = 1.5–2.5 + funding,
so each rolled attribute change was short by `realBias - (-1)`.

Adding that delta as a flat additive correction to each developing
attribute is mathematically exact on expectation: devBias shifts the
modifier range linearly, so the missing growth equals the missing bias.

Run AFTER your post-offseason deploy (when team.coach is hydrated from
DB). This script reads the marker file written by
capture_coachless_teams.py, queries each affected team's *current*
coach.player_development from the DB, and applies the missing bias to
every roster player on those teams (clamped to potential).

Self-contained: no project imports, runs against the SQLite file.
Idempotent on the marker file: deletes/renames it after success so
re-running is a no-op (refuses without an unconsumed marker).

Usage:
    fly ssh console
    python3 /data/compensate_coachless_training.py
"""

import json
import os
import sqlite3
import sys
from datetime import datetime, timezone

DB_PATH = '/data/floosball.db' if os.path.exists('/data/floosball.db') else 'data/floosball.db'
MARKER_PATH = '/data/coachless_at_training.json' if os.path.isdir('/data') else 'data/coachless_at_training.json'

# Position enum: QB=0, RB=1, WR=2, TE=3, K=4 (matches database/models.py + Position enum)
POS_QB, POS_RB, POS_WR, POS_TE, POS_K = 0, 1, 2, 3, 4

# Attributes developed by offseasonTraining for each position, mapped to their
# potential ceilings. Mirrors player_development.py develop_*_attributes.
POSITION_ATTRS = {
    POS_QB: [('arm_strength', 'potential_arm_strength'),
             ('accuracy',     'potential_accuracy'),
             ('agility',      'potential_agility')],
    POS_RB: [('speed',        'potential_speed'),
             ('power',        'potential_power'),
             ('agility',      'potential_agility'),
             ('reach',        'potential_reach')],
    POS_WR: [('speed',        'potential_speed'),
             ('hands',        'potential_hands'),
             ('agility',      'potential_agility'),
             ('reach',        'potential_reach')],
    POS_TE: [('speed',        'potential_speed'),
             ('hands',        'potential_hands'),
             ('agility',      'potential_agility'),
             ('reach',        'potential_reach')],
    POS_K:  [('leg_strength', 'potential_leg_strength'),
             ('accuracy',     'potential_accuracy')],
}


def computeMissingBias(realCoachDev: int) -> int:
    """devBias used at training (with fallback default 50): round((50-60)/10) = -1.
    devBias that should have been used: round((realCoachDev - 60) / 10).
    Missing bias to apply now = (should_have - was) = round((real-60)/10) + 1.
    """
    return round((realCoachDev - 60) / 10) + 1


def main() -> int:
    if not os.path.exists(DB_PATH):
        print(f"DB not found at {DB_PATH}", file=sys.stderr)
        return 1
    if not os.path.exists(MARKER_PATH):
        print(f"No marker file at {MARKER_PATH} — nothing to compensate "
              f"(or this script has already run; rename "
              f"{MARKER_PATH}.consumed-* if you intend to re-apply).",
              file=sys.stderr)
        return 1

    with open(MARKER_PATH, 'r') as f:
        marker = json.load(f)

    teamIds = marker.get('team_ids') or []
    if not teamIds:
        print("Marker has no affected teams — nothing to do.")
        return 0

    print(f"Marker captured at {marker.get('captured_at')} for season {marker.get('season')}.")
    print(f"Compensating {len(teamIds)} team(s): {[t['name'] for t in marker.get('teams', [])]}")
    print()

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    totalPlayersAdjusted = 0
    perTeamSummary = []

    for teamId in teamIds:
        cur.execute("SELECT id, name FROM teams WHERE id = ?", (teamId,))
        team = cur.fetchone()
        if not team:
            print(f"  team_id={teamId}: not found, skipping")
            continue

        cur.execute("""
            SELECT id, name, player_development, overall_rating
            FROM coaches
            WHERE team_id = ?
            ORDER BY created_at DESC LIMIT 1
        """, (teamId,))
        coach = cur.fetchone()
        if not coach:
            print(f"  team_id={teamId} {team['name']}: STILL no coach in DB — skipping. "
                  f"Run patch_coachless_teams.py first.")
            continue
        realDev = coach['player_development']
        missingBias = computeMissingBias(realDev)
        if missingBias <= 0:
            print(f"  team_id={teamId} {team['name']}: coach {coach['name']} dev={realDev} "
                  f"→ missing_bias={missingBias} (no compensation needed)")
            continue

        # Gather active rostered players (post-FA draft state). is_prospect
        # players didn't go through STEP 7's rostered-player path the same way,
        # but they DO get coach dev — including them is consistent.
        cur.execute("""
            SELECT p.id, p.name, p.position, p.is_prospect
            FROM players p
            WHERE p.team_id = ?
              AND (p.is_undrafted IS NULL OR p.is_undrafted = 0)
              AND (p.is_upcoming_rookie IS NULL OR p.is_upcoming_rookie = 0)
            ORDER BY p.id
        """, (teamId,))
        roster = cur.fetchall()
        if not roster:
            print(f"  team_id={teamId} {team['name']}: empty roster — skipping")
            continue

        teamAdjustments = 0
        teamAttrChanges = 0
        for p in roster:
            pos = p['position']
            attrPairs = POSITION_ATTRS.get(pos)
            if not attrPairs:
                continue
            cur.execute("""
                SELECT speed, hands, reach, agility, power,
                       arm_strength, accuracy, leg_strength,
                       potential_speed, potential_hands, potential_reach,
                       potential_agility, potential_power,
                       potential_arm_strength, potential_accuracy, potential_leg_strength
                FROM player_attributes WHERE player_id = ?
            """, (p['id'],))
            attrs = cur.fetchone()
            if not attrs:
                continue

            updates = []
            playerChange = 0
            for attrCol, potCol in attrPairs:
                cur_val = attrs[attrCol]
                pot_val = attrs[potCol]
                if cur_val is None or pot_val is None:
                    continue
                # Apply the missing bias, clamped to per-attribute potential.
                # Attribute hard cap is 100 (MAX_ATTRIBUTE_VALUE).
                new_val = min(cur_val + missingBias, pot_val, 100)
                if new_val > cur_val:
                    delta = new_val - cur_val
                    updates.append(f"{attrCol}={new_val}")
                    playerChange += delta
                    cur.execute(
                        f"UPDATE player_attributes SET {attrCol} = ? WHERE player_id = ?",
                        (new_val, p['id'])
                    )
            if updates:
                teamAdjustments += 1
                teamAttrChanges += playerChange

        totalPlayersAdjusted += teamAdjustments
        perTeamSummary.append({
            'team': team['name'], 'team_id': teamId,
            'coach': coach['name'], 'coach_dev': realDev,
            'missing_bias': missingBias,
            'players_adjusted': teamAdjustments,
            'total_attr_points_added': teamAttrChanges,
        })
        print(f"  team_id={teamId:>3} {team['name']:<24}  coach={coach['name']:<22} "
              f"dev={realDev}  bias=+{missingBias}  "
              f"players={teamAdjustments}  attr_points=+{teamAttrChanges}")

    conn.commit()
    conn.close()

    # Mark marker as consumed so re-running is a no-op
    consumedPath = f"{MARKER_PATH}.consumed-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    os.rename(MARKER_PATH, consumedPath)

    print(f"\nSummary:")
    print(f"  Teams compensated: {len(perTeamSummary)}")
    print(f"  Players adjusted:  {totalPlayersAdjusted}")
    print(f"  Marker file moved → {consumedPath}")
    print(f"\nIMPORTANT: this only updates DB attribute columns. The running")
    print(f"app's in-memory player attributes are stale until next restart.")
    print(f"If you need the change visible immediately, restart the app.")
    return 0


if __name__ == '__main__':
    sys.exit(main())
