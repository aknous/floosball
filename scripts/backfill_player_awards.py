"""One-shot backfill: re-populate player.mvp_awards, all_pro_seasons,
and league_championships from existing Season + PlayerSeasonStats data.

Background: career awards lived only in memory before the v0.17
persistence patch. Past MVPs, All-Pros, and Floosbowl winners are
lost from the player rows but the *source data* still exists:
  - Season.mvp_player_id      → MVP for that season
  - Season.all_pro_player_ids → JSON list of All-Pros for that season
  - Season.champion_team_id   → Floosbowl-winning team
  - PlayerSeasonStats          → maps player → team for that season

This script walks every completed Season row and writes the awards
into Player.mvp_awards / all_pro_seasons / league_championships using
the same dict shape the runtime append paths use. Idempotent — re-
running won't double-stack awards (checks for an existing entry with
the same Season number before appending).

Usage (production):
    fly ssh sftp shell
    put scripts/backfill_player_awards.py /data/backfill_player_awards.py
    exit
    fly ssh console
    cd /data
    # Optional backup:
    python3 -c "import sqlite3; src=sqlite3.connect('/data/floosball.db'); dst=sqlite3.connect('/data/floosball.db.preawards'); src.backup(dst); src.close(); dst.close()"
    python3 /data/backfill_player_awards.py
"""

import os
import sys
import json
import sqlite3

DB_PATH = os.environ.get('FLOOSBALL_DB', '/data/floosball.db')
if not os.path.exists(DB_PATH):
    # Fallback to local dev path
    DB_PATH = 'data/floosball.db'

print(f"Using DB: {DB_PATH}")
conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
cur = conn.cursor()


def _normalizeAwards(raw):
    """JSON-decode a player's award column. Returns a list."""
    if raw is None:
        return []
    if isinstance(raw, list):
        return raw
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, list) else []
    except Exception:
        return []


def _alreadyHasSeason(awards, seasonNum):
    """Check if the awards list already has an entry for this season."""
    for entry in awards:
        if isinstance(entry, dict) and entry.get('Season') == seasonNum:
            return True
        if entry == seasonNum:  # legacy bare-int format
            return True
    return False


def _teamForPlayerInSeason(playerId, seasonNum):
    """Return (abbr, color) for the team a player was on during seasonNum,
    or ('', '#334155') if not found."""
    row = cur.execute(
        """
        SELECT t.abbr, t.color
        FROM player_season_stats pss
        JOIN teams t ON t.id = pss.team_id
        WHERE pss.player_id = ? AND pss.season = ?
        LIMIT 1
        """,
        (playerId, seasonNum),
    ).fetchone()
    if row:
        return row['abbr'] or '', row['color'] or '#334155'
    return '', '#334155'


def _appendAward(playerId, column, entry, seasonNum):
    """Read current JSON column for player, append entry if season not
    already present, write back. Returns True if appended."""
    row = cur.execute(
        f"SELECT {column} FROM players WHERE id = ?", (playerId,)
    ).fetchone()
    if not row:
        return False
    awards = _normalizeAwards(row[column])
    if _alreadyHasSeason(awards, seasonNum):
        return False
    awards.append(entry)
    cur.execute(
        f"UPDATE players SET {column} = ? WHERE id = ?",
        (json.dumps(awards), playerId),
    )
    return True


seasons = cur.execute(
    "SELECT season_number, mvp_player_id, all_pro_player_ids, champion_team_id "
    "FROM seasons WHERE champion_team_id IS NOT NULL OR mvp_player_id IS NOT NULL "
    "ORDER BY season_number"
).fetchall()

print(f"Found {len(seasons)} season(s) with award data")

stats = {'mvp': 0, 'all_pro': 0, 'champ': 0}

for s in seasons:
    seasonNum = s['season_number']

    # MVP
    if s['mvp_player_id']:
        abbr, color = _teamForPlayerInSeason(s['mvp_player_id'], seasonNum)
        entry = {'Season': seasonNum, 'team': abbr, 'teamColor': color}
        if _appendAward(s['mvp_player_id'], 'mvp_awards', entry, seasonNum):
            stats['mvp'] += 1

    # All-Pros
    if s['all_pro_player_ids']:
        try:
            allProIds = json.loads(s['all_pro_player_ids'])
        except Exception:
            allProIds = []
        for pid in allProIds:
            abbr, color = _teamForPlayerInSeason(pid, seasonNum)
            entry = {'Season': seasonNum, 'team': abbr, 'teamColor': color}
            if _appendAward(pid, 'all_pro_seasons', entry, seasonNum):
                stats['all_pro'] += 1

    # Championship
    if s['champion_team_id']:
        team = cur.execute(
            "SELECT abbr, color FROM teams WHERE id = ?",
            (s['champion_team_id'],),
        ).fetchone()
        if team:
            abbr = team['abbr'] or ''
            color = team['color'] or '#334155'
            entry = {'Season': seasonNum, 'team': abbr, 'teamColor': color}
            # Players who actually played for the champion that season —
            # filter by games_played > 0 so practice-squad-only fillers
            # don't get a ring.
            rosterIds = cur.execute(
                """
                SELECT player_id FROM player_season_stats
                WHERE team_id = ? AND season = ? AND games_played > 0
                """,
                (s['champion_team_id'], seasonNum),
            ).fetchall()
            for r in rosterIds:
                if _appendAward(r['player_id'], 'league_championships', entry, seasonNum):
                    stats['champ'] += 1

conn.commit()
conn.close()

print("Backfill complete:")
print(f"  MVPs awarded:        {stats['mvp']}")
print(f"  All-Pros awarded:    {stats['all_pro']}")
print(f"  Championship rings:  {stats['champ']}")
