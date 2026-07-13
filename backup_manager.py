"""Periodic consistent SQLite backups.

`VACUUM INTO` produces a fully consistent copy even with WAL active, so this is
safe to run alongside the live sim. Backups land in BACKUP_DIR (default
<db-dir>/backups) with a rotating retention. Point BACKUP_DIR at a *second* Fly
volume (or a mounted bucket) to get off-the-primary-volume redundancy without
any external service; for continuous off-box point-in-time replication, layer
Litestream on top (see docs/AUDIT_2026-05.md §1.1).

Env:
  BACKUP_ENABLED          default "1"   — set "0" to disable the loop
  BACKUP_INTERVAL_HOURS   default "24"
  BACKUP_INITIAL_DELAY_S  default "300" — first backup this long after boot
                                          (so short-lived processes/sims skip it)
  BACKUP_DIR              default "<db-dir>/backups"
  BACKUP_KEEP             default "7"   — most recent N copies kept
"""
import os
import re
import glob
import asyncio
import sqlite3
import datetime

from logger_config import get_logger

logger = get_logger("floosball.backup")


def _resolveDbPath():
    """Resolve the live DB path the same way the rest of the app does."""
    dbDir = os.environ.get('DATABASE_DIR', 'data')
    if os.path.exists('/data') and os.path.isdir('/data'):
        dbDir = '/data'
    return os.path.join(dbDir, 'floosball.db'), dbDir


def runBackupOnce():
    """Write one consistent backup and prune to BACKUP_KEEP. Returns the path
    written (or None if there was no DB). Synchronous — call via a thread."""
    dbPath, dbDir = _resolveDbPath()
    if not os.path.exists(dbPath):
        return None
    backupDir = os.environ.get('BACKUP_DIR') or os.path.join(dbDir, 'backups')
    os.makedirs(backupDir, exist_ok=True)

    ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    outPath = os.path.join(backupDir, f'floosball_{ts}.db')
    # Write to a temp name first so a crash mid-copy can't leave a half-written
    # file that looks like a valid backup.
    tmpPath = outPath + '.partial'
    con = sqlite3.connect(dbPath)
    try:
        con.execute("VACUUM INTO ?", (tmpPath,))
    finally:
        con.close()
    os.replace(tmpPath, outPath)

    keep = max(1, int(os.environ.get('BACKUP_KEEP', '3')))
    # Prune only the AUTO backups (floosball_<YYYYMMDD>_<HHMMSS>.db), oldest first by
    # mtime, and NEVER the one we just wrote. Manual/named backups (e.g.
    # floosball_pre_freeze_*.db) are left alone — sorting the raw glob by NAME put those
    # after the timestamped ones, so a low BACKUP_KEEP could delete the fresh auto backup.
    autoRe = re.compile(r'^floosball_\d{8}_\d{6}\.db$')
    autos = [p for p in glob.glob(os.path.join(backupDir, 'floosball_*.db'))
             if autoRe.match(os.path.basename(p)) and os.path.abspath(p) != os.path.abspath(outPath)]
    autos.sort(key=os.path.getmtime)  # oldest first
    excess = len(autos) - (keep - 1)  # keep newest (keep-1) others + the just-written one
    for old in autos[:max(0, excess)]:
        try:
            os.remove(old)
        except OSError:
            pass
    # Clean up any leftover .partial files (a backup that died mid-write, e.g. on a
    # full disk). The retention glob above only matches completed *.db backups, so
    # without this a failed partial would sit on the volume forever.
    for partial in glob.glob(os.path.join(backupDir, 'floosball_*.db.partial')):
        if partial != tmpPath:
            try:
                os.remove(partial)
            except OSError:
                pass
    return outPath


async def runBackupLoop():
    """Background task: a first backup after BACKUP_INITIAL_DELAY_S, then every
    BACKUP_INTERVAL_HOURS. Self-supervising — a failed backup is logged and the
    loop continues."""
    if os.environ.get('BACKUP_ENABLED', '1').lower() not in ('1', 'true', 'yes'):
        logger.info("DB backup loop disabled (BACKUP_ENABLED=0).")
        return
    intervalS = max(60.0, float(os.environ.get('BACKUP_INTERVAL_HOURS', '24')) * 3600)
    initialDelay = max(0.0, float(os.environ.get('BACKUP_INITIAL_DELAY_S', '300')))
    keep = os.environ.get('BACKUP_KEEP', '7')
    logger.info(f"DB backup loop: first in {initialDelay:.0f}s, then every "
                f"{intervalS / 3600:.1f}h, keeping {keep}.")
    await asyncio.sleep(initialDelay)
    while True:
        try:
            outPath = await asyncio.to_thread(runBackupOnce)
            if outPath and os.path.exists(outPath):
                sizeMb = os.path.getsize(outPath) / 1e6
                logger.info(f"DB backup written: {outPath} ({sizeMb:.1f}MB)")
        except Exception as e:
            logger.error(f"DB backup failed: {e}", exc_info=True)
        await asyncio.sleep(intervalS)
