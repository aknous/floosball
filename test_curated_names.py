"""Fan-submitted names must survive a reset, which config.json cannot deliver.

`_seedUnusedNames` re-merges config.json on every boot, so config-origin names survive a
fresh start for free. Names added AFTER the seed — admin box or approved Discord /name —
had no equivalent: `unused_names` loses a name the moment it is drawn onto a player, and
the only remaining copy is the player row, which every reset drops. 16 such names on the
prod snapshot.

⚠️ The obvious fix — write approved names back to config.json — does NOT work in prod.
config.json is read from a relative path, so the container copy is /app/config.json and
only /data is a volume; the write survives until the next deploy, then vanishes. That is
worse than no fix, because it looks like one. Hence a DB table on the volume.

Run: .venv/bin/python test_curated_names.py   (exits non-zero on any failure)
"""
import sys, types, inspect, re
sys.path.insert(0, '/Users/andrew/Projects/floosball')
import logging; logging.disable(logging.CRITICAL)
if 'floosball_game' not in sys.modules:
    _s = types.ModuleType('floosball_game'); _s.Game = type('G', (), {})
    sys.modules['floosball_game'] = _s
    import managers.timingManager  # noqa
    del sys.modules['floosball_game']

fails = []
def expect(d, c):
    print(f"  [{'OK' if c else 'FAIL'}] {d}")
    if not c: fails.append(d)


from database.models import CuratedName
from database.connection import clear_db, _seedCuratedNames
import api.main as M

# ── it survives the wipe, which is the entire reason it exists ──────────────
src = inspect.getsource(clear_db)
m = re.search(r'preserveTables\s*=\s*\{(.*?)\}', src, re.S)
preserved = {x.strip().strip('"\'') for x in m.group(1).split(',') if x.strip().strip('"\'')}
expect("curated_names survives a fresh start", "curated_names" in preserved)
expect("unused_names does too (the working pool)", "unused_names" in preserved)

# ── and it is merged back on boot, like config is ──────────────────────────
from database import connection as conn_mod
initSrc = inspect.getsource(conn_mod.init_db)
expect("_seedCuratedNames runs at init", "_seedCuratedNames()" in initSrc)
# Also after a wipe: clear_db re-seeds, and the curated names have to come back with the
# config ones or the fresh league starts without them.
expect("...and again after a fresh start re-seeds",
       inspect.getsource(conn_mod).count("_seedCuratedNames()") >= 3)
seedSrc = inspect.getsource(_seedCuratedNames)
expect("the merge skips names already in the pool", "existing" in seedSrc)
expect("...and names held by a live player or coach", "inUse" in seedSrc)

# ── approvals record a permanent copy ──────────────────────────────────────
acceptSrc = inspect.getsource(M._acceptNamesIntoPool)
expect("_acceptNamesIntoPool records a curated copy", "_recordCuratedNames" in acceptSrc)
expect("it takes a source so Discord and admin are distinguishable",
       "source" in inspect.signature(M._acceptNamesIntoPool).parameters)

mainSrc = inspect.getsource(M)
expect("the Discord approval path tags itself", 'source="discord"' in mainSrc)

# ── the model holds a NAME and nothing re-pointable ────────────────────────
cols = {c.name for c in CuratedName.__table__.columns}
expect("stores the name itself", "name" in cols)
expect("no player_id — a name outlives the player who wore it", "player_id" not in cols)
expect("names are unique", CuratedName.__table__.c.name.unique)

# ── recording is best-effort and must never fail the actual add ────────────
recSrc = inspect.getsource(M._recordCuratedNames)
expect("bookkeeping cannot break the name being added",
       "except Exception" in recSrc)


class _FakePM:
    unusedNames = []
    name_repo = None
    db_session = None
    def isNameInUse(self, n): return False


res = M._acceptNamesIntoPool(_FakePM(), ["ZZ Curated One", "ZZ Curated One", "  "])
expect("still dedupes and accepts normally with no session",
       res["accepted"] == ["ZZ Curated One"] and res["duplicatesInBatch"] == ["ZZ Curated One"])

print("\nPASS — approved names have a durable home that a reset cannot take away."
      if not fails else f"\n{len(fails)} FAILED")
sys.exit(1 if fails else 0)
