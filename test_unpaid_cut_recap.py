"""A forced payroll cut reaches the season recap.

The season-end payroll check (`_enforcePayrollAtSeasonEnd`) records each forced cut as a
'cut' recap row with an "Unpaid:" detail, then the fresh offseason wipes the season's
recap log for a clean rebuild (`_clearRecapEvents`). The wipe deleted every forced cut
moments after it was written: the "Unpaid, X leaves the Y" news went out and the cut
never showed in the recap or the offseason moves feed (found on a prod-snapshot run:
7 forced cuts in the log, 0 recap rows). The wipe now spares those rows.

Run: .venv/bin/python -m pytest -q test_unpaid_cut_recap.py
"""
import os
import sys
import tempfile
import types

HERE = os.path.dirname(os.path.abspath(__file__))
os.environ['DATABASE_DIR'] = tempfile.mkdtemp(prefix='floo_unpaid_cut_')
sys.path.insert(0, HERE)
import logging
logging.disable(logging.CRITICAL)

from database.connection import init_db, get_session
from database.models import SeasonRecapEvent

init_db()
from managers.seasonManager import SeasonManager  # noqa: E402

SEASON = 12


def _row(eventType, pid, detail=None, season=SEASON):
    return SeasonRecapEvent(season=season, event_type=eventType, team_id=3, team_abbr='TRN',
                            team_name='Trains', player_id=pid, player_name=f'P{pid}', detail=detail)


def test_theWipeSparesForcedPayrollCutsAndNothingElse():
    s = get_session()
    s.query(SeasonRecapEvent).delete()
    s.add_all([
        _row('cut', 1, f"{SeasonManager.UNPAID_CUT_DETAIL} payroll short by 42F"),
        _row('cut', 2, 'GM upgrade cut'),
        _row('resign', 3, '2 season(s)'),
        _row('resign', 4, season=SEASON - 1),
    ])
    s.commit()
    s.close()

    SeasonManager._clearRecapEvents(SeasonManager, SEASON)

    s = get_session()
    left = {(r.season, r.player_id) for r in s.query(SeasonRecapEvent).all()}
    s.close()
    assert left == {(SEASON, 1), (SEASON - 1, 4)}
