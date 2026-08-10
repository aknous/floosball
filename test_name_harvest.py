"""Names added to the pool must survive a fresh start; lineage variants must not.

`unused_names` IS preserved by clear_db, so the pool looks safe. It is not: a name is
REMOVED from the pool when a player is created and never returned. Retirement adds a
*variant* ("Name Jr.", then III, IV...) via seasonManager._recyclePlayerName, not the
original. So every name attached to a player exists only on a `players` row — and `players`
is dropped.

Measured on prod: 401 base names sat on player rows and nowhere else, including every name
submitted through Discord /name or added by an admin that had since been assigned.

Run: .venv/bin/python test_name_harvest.py   (exits non-zero on any failure)
"""
import sys, os, sqlite3, subprocess, tempfile

fails = []
def expect(d, c):
    print(f"  [{'OK' if c else 'FAIL'}] {d}")
    if not c: fails.append(d)


db = tempfile.mktemp(suffix='.db')
c = sqlite3.connect(db)
c.executescript("""
CREATE TABLE unused_names (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT);
CREATE TABLE pending_names (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, available_season INTEGER);
CREATE TABLE players (id INTEGER PRIMARY KEY, name TEXT, service_time TEXT);
INSERT INTO unused_names (name) VALUES ('Spare Name'), ('Old Timer Jr.'), ('Dynasty III');
INSERT INTO pending_names (name, available_season) VALUES ('Held Guy Jr.', 20);
INSERT INTO players (name, service_time) VALUES
    ('Submitted Byfan','Veteran2'),      -- the case that matters: on a player, not in the pool
    ('Chick Neriardi','Retired'),        -- retired rows keep the base name
    ('Chick Neriardi Jr.','Veteran3'),
    ('Spare Name','Rookie');             -- already in the pool, must not duplicate
""")
c.commit(); c.close()

def run(*extra):
    return subprocess.run([sys.executable, 'tools_harvest_names.py', '--db', db, *extra],
                          capture_output=True, text=True).stdout

run()
c = sqlite3.connect(db)
expect("dry run changes nothing",
       c.execute("select count(*) from unused_names").fetchone()[0] == 3)
c.close()

run('--apply')
c = sqlite3.connect(db)
pool = {r[0] for r in c.execute("select name from unused_names")}
pend = {r[0] for r in c.execute("select name from pending_names")}

# THE POINT OF THE TOOL: a name a fan submitted, since assigned to a player, is not in the
# pool and would vanish with the players table.
expect("a name living only on a player row is recovered", "Submitted Byfan" in pool)
expect("a retired player's base name is recovered", "Chick Neriardi" in pool)
expect("no duplicate for a name already in the pool",
       [r[0] for r in c.execute("select name from unused_names")].count("Spare Name") == 1)

# Owner call: keep the names, not the Jr artifacts — they are bookkeeping from a league
# that is about to stop existing.
expect("lineage variants are dropped from the pool", "Old Timer Jr." not in pool)
expect("roman-numeral variants are dropped too", "Dynasty III" not in pool)
expect("held variants are dropped as well", "Held Guy Jr." not in pend)
expect("a Jr. player does not re-add itself as a variant", "Chick Neriardi Jr." not in pool)

before = len(pool)
run('--apply')
c2 = sqlite3.connect(db)
expect("re-running is idempotent",
       c2.execute("select count(*) from unused_names").fetchone()[0] == before)
c.close(); c2.close()

# --keep-variants leaves them alone, for a reset that wants the lineage intact.
db2 = tempfile.mktemp(suffix='.db')
import shutil
c = sqlite3.connect(db2)
c.executescript("""
CREATE TABLE unused_names (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT);
CREATE TABLE pending_names (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, available_season INTEGER);
CREATE TABLE players (id INTEGER PRIMARY KEY, name TEXT, service_time TEXT);
INSERT INTO unused_names (name) VALUES ('Old Timer Jr.');
""")
c.commit(); c.close()
subprocess.run([sys.executable, 'tools_harvest_names.py', '--db', db2, '--apply', '--keep-variants'],
               capture_output=True, text=True)
c = sqlite3.connect(db2)
expect("--keep-variants leaves lineage names in place",
       "Old Timer Jr." in {r[0] for r in c.execute("select name from unused_names")})
c.close()
os.unlink(db); os.unlink(db2)

print("\nPASS — submitted names survive the reset, lineage variants do not."
      if not fails else f"\n{len(fails)} FAILED")
sys.exit(1 if fails else 0)
