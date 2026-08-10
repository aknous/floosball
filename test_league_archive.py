"""The season archive must survive a fresh start, and must not lie about who won.

A fresh start drops 68 tables and restarts every id from 1. The instinct — add the history
tables to clear_db's preserveTables — is WORSE than losing them: `records` and
`championships` store player_id/team_id and no names at all, so a preserved row would
reattach a 15-season record to whichever rookie inherited id 292.

league_archive exists to hold resolved NAMES with no foreign keys, so there is nothing left
to re-point. These tests pin both halves: that it survives, and that the tables which must
NOT survive still do not.

Run: .venv/bin/python test_league_archive.py   (exits non-zero on any failure)
"""
import sys, os, sqlite3, subprocess, tempfile, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

fails = []
def expect(d, c):
    print(f"  [{'OK' if c else 'FAIL'}] {d}")
    if not c: fails.append(d)


# ── the archive holds NAMES, never ids ──────────────────────────────────────
from database.models import LeagueArchive
cols = {c.name for c in LeagueArchive.__table__.columns}
expect("archive stores a champion NAME", "champion" in cols)
expect("archive stores an MVP NAME", "mvp" in cols)
expect("archive holds NO player_id", "player_id" not in cols)
expect("archive holds NO team_id", "team_id" not in cols)
expect("archive has no foreign keys at all",
       not any(c.foreign_keys for c in LeagueArchive.__table__.columns))

# ── it is preserved across a wipe; the mis-attributing tables are not ───────
import inspect, re
from database.connection import clear_db
src = inspect.getsource(clear_db)
m = re.search(r'preserveTables\s*=\s*\{(.*?)\}', src, re.S)
preserved = {x.strip().strip('"\'') for x in m.group(1).split(',') if x.strip().strip('"\'')}
expect("league_archive survives a fresh start", "league_archive" in preserved)
for t in ("records", "championships", "seasons", "players"):
    expect(f"{t} is NOT preserved (its ids would re-point)", t not in preserved)

# ── the script resolves names and is idempotent ─────────────────────────────
db = tempfile.mktemp(suffix='.db')
c = sqlite3.connect(db)
c.executescript("""
CREATE TABLE teams (id INTEGER PRIMARY KEY, city TEXT, name TEXT);
CREATE TABLE players (id INTEGER PRIMARY KEY, name TEXT);
CREATE TABLE seasons (season_number INTEGER, champion_team_id INTEGER, mvp_player_id INTEGER);
CREATE TABLE championships (id INTEGER PRIMARY KEY, team_id INTEGER, season INTEGER, championship_type TEXT);
INSERT INTO teams VALUES (7,'Seattle','Cranes'),(9,'Arizona','Dry Heat');
INSERT INTO players VALUES (292,'Cries Cabrera');
INSERT INTO seasons VALUES (1,7,292),(2,9,NULL),(3,NULL,NULL);
INSERT INTO championships VALUES (1,7,1,'league'),(2,9,1,'league');
""")
c.commit(); c.close()

def run(*extra):
    return subprocess.run([sys.executable, 'tools_archive_seasons.py', '--db', db, *extra],
                          capture_output=True, text=True).stdout

out = run()
expect("dry run writes nothing", sqlite3.connect(db).execute(
    "select count(*) from sqlite_master where name='league_archive'").fetchone()[0] == 0
    or sqlite3.connect(db).execute("select count(*) from league_archive").fetchone()[0] == 0)

run('--apply')
c = sqlite3.connect(db); c.row_factory = sqlite3.Row
rows = {r['season']: r for r in c.execute("select * from league_archive")}
expect("resolves the champion to a name", rows[1]['champion'] == 'Seattle Cranes')
expect("resolves the MVP to a name", rows[1]['mvp'] == 'Cries Cabrera')
expect("captures both league champions",
       sorted(json.loads(rows[1]['league_champions'])) == ['Arizona Dry Heat', 'Seattle Cranes'])
expect("a season with a champion but no MVP still archives",
       2 in rows and rows[2]['champion'] == 'Arizona Dry Heat' and rows[2]['mvp'] is None)
# A season that resolved to nothing is one that never finished. Archiving it blank reads as
# "nobody won" rather than "in progress when the league ended", which is a different claim.
expect("an unfinished season is skipped, not archived blank", 3 not in rows)

run('--apply')
c2 = sqlite3.connect(db)
expect("re-running updates in place rather than duplicating",
       c2.execute("select count(*) from league_archive").fetchone()[0] == 2)

run('--apply', '--era', '2', '--label', 'The 32-Club Era')
expect("a later era appends rather than overwriting",
       c2.execute("select count(distinct era) from league_archive").fetchone()[0] == 2)
c.close(); c2.close(); os.unlink(db)

print("\nPASS — the archive keeps names, survives the wipe, and cannot re-point at new players."
      if not fails else f"\n{len(fails)} FAILED")
sys.exit(1 if fails else 0)
