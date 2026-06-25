"""Retiree name reuse delay (NAME_REUSE_DELAY_SEASONS).

When a player retires, _recyclePlayerName bumps the name to its next generational
variant (Base -> Jr. -> III -> ...) and HOLDS it out of the usable pool for
NAME_REUSE_DELAY_SEASONS seasons before it can be assigned to a new player.
Held names live in pendingNames (persisted to the pending_names table alongside
unusedNames) and are released at season start once their hold elapses.

Run: python test_name_reuse.py   (uses a throwaway temp DB)
"""
import os, sys, tempfile, shutil

sys.path.insert(0, os.getcwd())
_tmp = tempfile.mkdtemp(prefix="floo_nametest_")
os.environ["DATABASE_DIR"] = _tmp

from constants import NAME_REUSE_DELAY_SEASONS
from database.connection import init_db
init_db()
from managers.playerManager import PlayerManager
from managers.seasonManager import SeasonManager
from database.models import PendingName, UnusedName

failures = []
def expect(label, cond):
    print(f"  [{'OK' if cond else 'FAIL'}] {label}")
    if not cond:
        failures.append(label)

print(f"Name-reuse delay = {NAME_REUSE_DELAY_SEASONS} seasons\n")

pm = PlayerManager(None)
pm.unusedNames = []
pm.pendingNames = []

# Bind the REAL _recyclePlayerName to a stub seasonManager retiring in season 5.
sm = type("StubSM", (), {})()
sm.currentSeason = type("S", (), {"seasonNumber": 5})()
sm.playerManager = pm
sm._recyclePlayerName = SeasonManager._recyclePlayerName.__get__(sm)

print("1. Retiring recycles + HOLDS the name (not immediately reusable)")
sm._recyclePlayerName("Buck Compass")               # base -> "Buck Compass Jr."
held = 5 + NAME_REUSE_DELAY_SEASONS
expect("base name recycled to ' Jr.' and held with the right release season",
       ("Buck Compass Jr.", held) in pm.pendingNames)
expect("held name is NOT in the usable pool", "Buck Compass Jr." not in pm.unusedNames)
sm._recyclePlayerName("Dex Vandal Jr.")             # Jr. -> III (suffix progression intact)
expect("a 'Jr.' recycles to 'III'", ("Dex Vandal III", held) in pm.pendingNames)

print("\n2. Held names survive a save + reload (durable, off the shared session)")
pm.saveUnusedNames()
expect("held names persisted to pending_names table",
       pm.db_session.query(PendingName).filter_by(name="Buck Compass Jr.").count() == 1)
pm2 = PlayerManager(None)
pm2._loadNamesFromDatabase()
expect("a fresh manager reloads the held names", ("Buck Compass Jr.", held) in pm2.pendingNames)
expect("reloaded held name still not usable", "Buck Compass Jr." not in pm2.unusedNames)

print("\n3. Release happens only once the hold elapses")
expect(f"season {held - 1}: nothing released (still held)", pm2.releaseDueNames(held - 1) == 0)
expect("still not usable before the hold elapses", "Buck Compass Jr." not in pm2.unusedNames)
expect(f"season {held}: both held names release", pm2.releaseDueNames(held) == 2)
expect("released name is now usable", "Buck Compass Jr." in pm2.unusedNames)
expect("released name persisted to unused_names",
       pm2.db_session.query(UnusedName).filter_by(name="Buck Compass Jr.").count() == 1)
expect("pending rows cleared after release",
       pm2.db_session.query(PendingName).filter_by(name="Buck Compass Jr.").count() == 0)

shutil.rmtree(_tmp, ignore_errors=True)
print()
if failures:
    print(f"FAILED ({len(failures)}): " + "; ".join(failures))
    raise SystemExit(1)
print("ALL NAME-REUSE TESTS PASS")
