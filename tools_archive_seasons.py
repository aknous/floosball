"""Snapshot completed seasons into `league_archive` BEFORE a fresh start.

Run this, verify it, and only then wipe. A fresh start drops 68 tables and every id
restarts from 1, so this is the last moment the old league can be read.

    .venv/bin/python tools_archive_seasons.py                       # dry run
    .venv/bin/python tools_archive_seasons.py --apply
    .venv/bin/python tools_archive_seasons.py --db data/x.db --era 1 --label "The 24-Club Era"

⚠️ WHY THIS EXISTS AS A SCRIPT rather than a hook inside clear_db: the archive has to READ
the old data, so it must complete before anything is dropped. Wiring it into the wipe means
a failed archive still leaves you with a wiped database, which is precisely the outcome it
is meant to prevent.

⚠️ WHY IT STORES NAMES. `records`, `championships` and `seasons` all reference player_id /
team_id and carry no names — `records` has no player_name column at all. Ids restart from 1
on a wipe, so keeping those tables would REATTACH history to unrelated entities rather than
preserve it. This resolves names now, while they still mean something.

Idempotent: re-running updates the same (era, season) rows rather than duplicating.
"""
import sys, sqlite3, json
from datetime import datetime

args = sys.argv[1:]
def flag(name, default=None):
    return args[args.index(name) + 1] if name in args else default

DB = flag('--db', 'data/floosball.db')
ERA = int(flag('--era', '1'))
LABEL = flag('--label', 'The 24-Club Era')
APPLY = '--apply' in args

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row


def resolve(table, col, rowId):
    if not rowId:
        return None
    r = conn.execute(f"select {col} from {table} where id=?", (rowId,)).fetchone()
    return r[0] if r else None


try:
    conn.execute("select 1 from seasons limit 1")
except sqlite3.OperationalError:
    print(f"{DB}: no seasons table — nothing to archive")
    raise SystemExit(1)

conn.execute("""CREATE TABLE IF NOT EXISTS league_archive (
    id INTEGER PRIMARY KEY AUTOINCREMENT, era INTEGER NOT NULL DEFAULT 1,
    era_label VARCHAR(80), season INTEGER NOT NULL, champion VARCHAR(120),
    league_champions TEXT, mvp VARCHAR(120), created_at DATETIME,
    UNIQUE(era, season))""")

rows = []
for s in conn.execute("select season_number, champion_team_id, mvp_player_id from seasons order by season_number"):
    season = s['season_number']
    champ = resolve('teams', "city || ' ' || name", s['champion_team_id'])
    mvp = resolve('players', 'name', s['mvp_player_id'])
    leagues = [r[0] for r in conn.execute(
        """select t.city || ' ' || t.name from championships ch
           join teams t on t.id = ch.team_id
           where ch.season = ? and ch.championship_type = 'league'
           order by t.city""", (season,))]
    # A season with no champion is one that never finished — archiving it as a blank row
    # is worse than leaving it out, because it reads as "nobody won" rather than "in
    # progress when the league ended".
    if not champ and not leagues and not mvp:
        print(f"  season {season}: nothing resolved, skipping (unfinished?)")
        continue
    rows.append((ERA, LABEL, season, champ, json.dumps(leagues) if leagues else None, mvp))

print(f"\n{DB}   era {ERA} — {LABEL}   ({'APPLY' if APPLY else 'DRY RUN'})\n")
print(f"{'season':>7}  {'Floos Bowl champion':26} {'MVP':22} league champions")
for era, label, season, champ, leagues, mvp in rows:
    lg = ', '.join(json.loads(leagues)) if leagues else '-'
    print(f"{season:>7}  {(champ or '-'):26} {(mvp or '-'):22} {lg}")
print(f"\n{len(rows)} season(s)")

if not rows:
    print("nothing to write")
elif APPLY:
    conn.executemany("""INSERT INTO league_archive
            (era, era_label, season, champion, league_champions, mvp, created_at)
        VALUES (?,?,?,?,?,?,?)
        ON CONFLICT(era, season) DO UPDATE SET
            era_label=excluded.era_label, champion=excluded.champion,
            league_champions=excluded.league_champions, mvp=excluded.mvp""",
        [r + (datetime.utcnow(),) for r in rows])
    conn.commit()
    total = conn.execute("select count(*) from league_archive").fetchone()[0]
    print(f"written. league_archive now holds {total} row(s) across "
          f"{conn.execute('select count(distinct era) from league_archive').fetchone()[0]} era(s)")
else:
    print("dry run only — re-run with --apply to write")
conn.close()
