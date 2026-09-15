"""The champion unpin must RELEASE SQLite's write lock, even when it changes nothing.

⚠️ A BULK `.update()` EXECUTES IMMEDIATELY AND TAKES THE WRITE LOCK WHETHER OR NOT IT
MATCHES A ROW. `_unpinStaleChampions` committed only `if changed`, so in the one case
where there was nothing to unpin it left the shared session sitting on an open write
transaction — and every other session's write then waited out the full 30s busy_timeout
and failed.

⚠️ IT MADE A FRESH START UNREACHABLE. A brand-new league has no champion row, so
`changed` is 0 every time; two lines later `maybeResetRuleOverridesForSeason` opens its
own session and dies with "database is locked" before week 1 exists. Both
`run_api.py --fresh --timing=fast` and a headless boot reproduced it.

⚠️ AND IT IS THE SAME SHAPE THAT ALREADY TOOK PRODUCTION DOWN ONCE, through
`_publishChampionNews` — an unpin that has written and then does not release. This
function's own docstring warned about it, and it was one `if` away from repeating it.
See CLAUDE.md, League News Feed: "Any `except` around a publisher that has already
WRITTEN must release the lock."
"""

import os
import tempfile

# ⚠️ Import AFTER DATABASE_DIR is set so the engine points at the temp DB — the pattern
# test_anomaly_suppression.py already uses. Reversed, this writes to the real database.
_tmp = tempfile.mkdtemp(prefix='floos_unpin_')
os.environ['DATABASE_DIR'] = _tmp

from sqlalchemy import text                                          # noqa: E402
from database.connection import init_db, SessionLocal, get_session   # noqa: E402
from database.models import LeagueNewsItem                           # noqa: E402
from managers.seasonManager import SeasonManager                     # noqa: E402

init_db()


class Shim:
    """Just the two attributes `_unpinStaleChampions` touches."""

    def __init__(self, session):
        self.db_session = session

    _unpinStaleChampions = SeasonManager._unpinStaleChampions


def _independentWriteWorks() -> bool:
    """Can a DIFFERENT session write? This is the whole question — an open write
    transaction on the shared session is invisible until something else tries."""
    other = SessionLocal()
    try:
        other.execute(text(
            "INSERT INTO app_settings (key, value, updated_at) "
            "VALUES ('unpin_probe', '1', CURRENT_TIMESTAMP) "
            "ON CONFLICT(key) DO UPDATE SET value = '1'"))
        other.commit()
        return True
    except Exception:
        return False
    finally:
        other.close()


def test_unpin_releases_the_lock_when_nothing_matched():
    """⚠️ THE ZERO-ROW CASE IS THE BUG, and it is the case a fresh league is always in."""
    session = get_session()
    try:
        assert session.query(LeagueNewsItem).count() == 0, "fixture expects an empty feed"
        Shim(session)._unpinStaleChampions(1)
        assert not session.in_transaction(), \
            "the shared session is still holding a write transaction"
        assert _independentWriteWorks(), \
            "another session cannot write — the lock was never released"
    finally:
        session.close()
    print("PASS a 0-row unpin leaves no write transaction behind")


def test_unpin_still_unpins_and_releases():
    """The over-reach guard: releasing the lock must not stop it doing its job."""
    session = get_session()
    try:
        session.add(LeagueNewsItem(
            season=1, week=32, category='champion', event_type='floosbowl_champion',
            text='Old champion', pinned=True))
        session.add(LeagueNewsItem(
            season=2, week=32, category='champion', event_type='floosbowl_champion',
            text='This season', pinned=True))
        session.commit()

        Shim(session)._unpinStaleChampions(2)

        assert not session.in_transaction()
        assert _independentWriteWorks()
        session.expire_all()
        rows = {r.text: r.pinned for r in session.query(LeagueNewsItem).all()}
        assert rows['Old champion'] is False, rows
        # ⚠️ Scoped `season < seasonNumber` so a champion crowned in THIS season
        # survives a mid-season restart — startNewSeason runs on resume too.
        assert rows['This season'] is True, rows
    finally:
        session.close()
    print("PASS a stale champion is unpinned, the current one is not, lock released")
