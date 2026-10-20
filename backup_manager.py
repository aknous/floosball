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
  BACKUP_MIN_FREE_MB      default "64"  — free space a backup must leave behind

⚠️ A BACKUP MUST NEVER FILL THE VOLUME IT SHARES WITH THE LIVE DB. On 2026-10-20 the
12:30 backup ran prod's 1GB volume out of space part-way through `VACUUM INTO`: every
write after it failed, including the login stamp in `api/auth.getCurrentUser`, so every
signed-in request was refused for 78 minutes. So a backup checks free space first, prunes
down to the copies it would keep anyway before writing when that makes room, skips when it
still will not fit, and removes its own partial file on any failure.
"""
import os
import re
import glob
import shutil
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

    keep = max(1, int(os.environ.get('BACKUP_KEEP', '3')))
    need = _bytesNeeded(dbPath)
    if _freeBytes(backupDir) < need:
        # The copies we would delete after writing are deleted now instead, so the
        # backup we are about to write has room. Same end state, reached earlier.
        _pruneAutos(backupDir, keep - 1)
        if _freeBytes(backupDir) < need:
            logger.error(
                f"DB backup skipped: needs {need / 1e6:.0f}MB free, "
                f"{_freeBytes(backupDir) / 1e6:.0f}MB available in {backupDir}. "
                f"Extend the volume or lower BACKUP_KEEP.")
            return None

    ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    outPath = os.path.join(backupDir, f'floosball_{ts}.db')
    # Write to a temp name first so a crash mid-copy can't leave a half-written
    # file that looks like a valid backup.
    tmpPath = outPath + '.partial'
    try:
        con = sqlite3.connect(dbPath)
        try:
            con.execute("VACUUM INTO ?", (tmpPath,))
        finally:
            con.close()
        os.replace(tmpPath, outPath)
    except Exception:
        # A half-written copy is useless and is exactly what keeps a full disk full.
        for leftover in (tmpPath, tmpPath + '-journal'):
            try:
                os.remove(leftover)
            except OSError:
                pass
        raise

    # Prune only the AUTO backups (floosball_<YYYYMMDD>_<HHMMSS>.db), oldest first by
    # mtime, and NEVER the one we just wrote. Manual/named backups (e.g.
    # floosball_pre_freeze_*.db) are left alone — sorting the raw glob by NAME put those
    # after the timestamped ones, so a low BACKUP_KEEP could delete the fresh auto backup.
    _pruneAutos(backupDir, keep - 1, exclude=outPath)
    # Clean up any leftover .partial files from an older process that died mid-write.
    # The retention glob only matches completed *.db backups, so without this a failed
    # partial would sit on the volume forever.
    for partial in glob.glob(os.path.join(backupDir, 'floosball_*.db.partial*')):
        if not partial.startswith(tmpPath):
            try:
                os.remove(partial)
            except OSError:
                pass
    return outPath


_AUTO_BACKUP_RE = re.compile(r'^floosball_\d{8}_\d{6}\.db$')


def _pruneAutos(backupDir, keepOthers, exclude=None):
    """Delete the oldest auto backups until at most `keepOthers` remain, never touching
    `exclude` (the copy just written)."""
    autos = [p for p in glob.glob(os.path.join(backupDir, 'floosball_*.db'))
             if _AUTO_BACKUP_RE.match(os.path.basename(p))
             and (exclude is None or os.path.abspath(p) != os.path.abspath(exclude))]
    autos.sort(key=os.path.getmtime)  # oldest first
    for old in autos[:max(0, len(autos) - max(0, keepOthers))]:
        try:
            os.remove(old)
        except OSError:
            pass


def _bytesNeeded(dbPath):
    """A `VACUUM INTO` copy is at most the DB plus its WAL; on top of that the live DB
    must keep `BACKUP_MIN_FREE_MB` to go on writing."""
    size = os.path.getsize(dbPath)
    wal = dbPath + '-wal'
    if os.path.exists(wal):
        size += os.path.getsize(wal)
    headroom = float(os.environ.get('BACKUP_MIN_FREE_MB', '64')) * 1e6
    return int(size + headroom)


def _freeBytes(path):
    return shutil.disk_usage(path).free


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
