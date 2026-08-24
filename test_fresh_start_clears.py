"""A fresh start really clears the season-scoped state it claims to.

⚠️ THIS TEST CALLS clear_db. It does not read the source. Two fixes in this function had
been written, reviewed and shipped, and NEITHER HAD EVER RUN: `text` is imported locally
inside other functions in connection.py and was not in scope here, so both blocks raised
NameError. One logged a warning nobody read; the other sat inside a bare `except: pass`
and failed in total silence.

The consequences were exactly what their own comments warned about:
  * `lineup_snapshot_complete_from` survived every wipe, leaving the NEW week 1 sitting
    before the boundary and permanently exempt from the no-games-no-points gate -- which
    CLAUDE.md records as "why the leak kept reproducing on clean runs";
  * `starter_pack_claimed_season=1` survived, matched the new season 1, and hid the
    starter pack from every returning user.

A source-reading test would have passed against the broken code, because the code LOOKED
right. Only running it finds this.

Run: ./run_tests.sh fresh_start_clears
"""
import sys, os, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import logging; logging.disable(logging.WARNING)

fails = []
def expect(d, c):
    print(f"  [{'OK' if c else 'FAIL'}] {d}")
    if not c: fails.append(d)

tmp = tempfile.mkdtemp(prefix='floo_fresh_')

# ⚠️ THE ENV VAR IS `DATABASE_DIR`, AND IT SETS THE DIRECTORY, not the file. Getting this
# wrong is not a small mistake: anything that boots the app with `--fresh` and the wrong
# variable clears the REAL data/floosball.db, which is exactly what happened during this
# investigation. It must be set BEFORE database.connection is imported, because the
# engine is built at module import time.
os.environ['DATABASE_DIR'] = tmp
dbPath = os.path.join(tmp, 'floosball.db')

import database.connection as conn
from sqlalchemy import text

assert dbPath in str(conn.engine.url), (
    'refusing to run: pointed at ' + str(conn.engine.url) + ', not the temp file')

conn.init_db()
from managers.fantasyTracker import COMPLETE_SNAPSHOT_SETTING

# Seed exactly the state a fresh start must clear.
# ⚠️ Separate connections, not nested — an ORM write inside an open raw connection
# deadlocks SQLite ("database is locked").
with conn.engine.connect() as c:
    c.execute(text("INSERT INTO app_settings (key, value, updated_at)"
                   " VALUES (:k, :v, CURRENT_TIMESTAMP)"),
              {"k": COMPLETE_SNAPSHOT_SETTING, "v": "1:2"})
    c.commit()

from database.models import User as _U
from sqlalchemy.orm import Session as _S
with _S(conn.engine) as sess:
    sess.add(_U(clerk_id='c1', email='a@b.c', username='tester',
                starter_pack_claimed_season=1, favorite_team_locked_season=1))
    sess.commit()

with conn.engine.connect() as c:
    before = c.execute(text("SELECT value FROM app_settings WHERE key=:k"),
                       {"k": COMPLETE_SNAPSHOT_SETTING}).fetchone()
expect("the season-scoped setting is present before the wipe", before is not None)

conn.clear_db()

with conn.engine.connect() as c:
    after = c.execute(text("SELECT value FROM app_settings WHERE key=:k"),
                      {"k": COMPLETE_SNAPSHOT_SETTING}).fetchone()
    flags = c.execute(text("SELECT starter_pack_claimed_season, favorite_team_locked_season"
                           " FROM users WHERE clerk_id='c1'")).fetchone()
    stillThere = c.execute(text("SELECT COUNT(*) FROM users")).fetchone()[0]

expect(f"the season-scoped app setting is CLEARED ({after})", after is None)
expect(f"starter_pack_claimed_season is nulled ({flags[0] if flags else '?'})",
       flags is not None and flags[0] is None)
expect(f"favorite_team_locked_season is nulled ({flags[1] if flags else '?'})",
       flags is not None and flags[1] is None)
# ⚠️ Guard the guard: if the users table were dropped the flags would read as cleared
# for the wrong reason, and the whole point is that users are PRESERVED.
expect(f"...and the user row itself survived, which is why the null matters ({stillThere})",
       stillThere == 1)

print()
if fails:
    print(f"{len(fails)} FAILED"); sys.exit(1)
print("PASS — a fresh start clears what it says it clears.")
