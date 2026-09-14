"""The season opens 19:00 ET Sunday, and day 0 is still Monday.

⚠️ THIS EXISTS BECAUSE THE ANCHOR'S DATE WAS LOAD-BEARING AND NOBODY COULD SEE IT.
`getWeekStartTime` read `startDate.date()` -- the UTC date of a naive stamp -- so day 0 was
"whatever day it is in London when the season opens". That happened to be right while the
anchor sat at 04:00 ET Monday (08:00/09:00 UTC, Monday either way) and silently breaks the
moment it moves: 19:00 ET Sunday is 23:00 UTC Sunday under EDT and 00:00 UTC MONDAY under
EST, so a naive read puts the whole season on Sunday for half the year. A one-day schedule
shift twice a year, with nothing to catch it.

Run: .venv/bin/python test_season_anchor.py
"""
import sys, os, datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import logging; logging.disable(logging.WARNING)

fails = []
def expect(d, c):
    print(f"  [{'OK' if c else 'FAIL'}] {d}")
    if not c: fails.append(d)

from constants import (SEASON_FIRST_GAME_WEEKDAY, SEASON_FIRST_KICKOFF_HOUR_ET,
                       CROSS_DAY_ROLLOVER_LEAD_MINUTES)
from managers.timingManager import TimingManager, _isEdtDate
from managers.seasonManager import SeasonManager

def toEt(utc):
    return utc - datetime.timedelta(hours=4 if _isEdtDate(utc) else 5)

print("\n1. The anchor is 19:00 Eastern the evening before the first game day")
expect("games start on Monday (weekday 0)", SEASON_FIRST_GAME_WEEKDAY == 0)
expect("first kickoff is noon ET", SEASON_FIRST_KICKOFF_HOUR_ET == 12)
# 12:00 ET minus a 17h lead is 19:00 ET the night before -- DERIVED, not written down.
for name, fn in (("next", TimingManager._nextSeasonAnchorUtc),
                 ("last", TimingManager._lastSeasonAnchorUtc)):
    et = toEt(fn())
    expect(f"{name} anchor lands Sunday 19:00 ET ({et:%a %Y-%m-%d %H:%M})",
           et.weekday() == 6 and et.hour == 19 and et.minute == 0)
expect("it tracks the rollover lead rather than repeating it",
       (SEASON_FIRST_KICKOFF_HOUR_ET * 60 - CROSS_DAY_ROLLOVER_LEAD_MINUTES) == -300)
expect("the two anchors are a week apart",
       (TimingManager._nextSeasonAnchorUtc() - TimingManager._lastSeasonAnchorUtc()).days == 7)

print("\n1b. It does NOT skip a week when the anchor hour has already passed")
# ⚠️ THIS COST A PRODUCTION WEEK (2026-09-13). Keyed on the anchor's own weekday and asked
# for "the next Sunday 19:00 ET that has not passed", a deploy at 22:33 on a Sunday answered
# SEVEN DAYS LATER: season 6 was stamped 2026-09-20 23:00 UTC and its first game day moved
# from Monday the 14th to Monday the 21st. The question is which MONDAY games start on; the
# anchor follows from the lead and is allowed to sit in the past.
import managers.timingManager as _tm
_realNow = _tm._nowEastern
try:
    for label, fakeEt, wantGameDay in (
            ("Sunday 22:33 ET (the deploy that broke it)",
             datetime.datetime(2026, 9, 13, 22, 33), datetime.date(2026, 9, 14)),
            ("Sunday 18:00 ET, before the anchor",
             datetime.datetime(2026, 9, 13, 18, 0), datetime.date(2026, 9, 14)),
            ("Monday 09:00 ET, before kickoff",
             datetime.datetime(2026, 9, 14, 9, 0), datetime.date(2026, 9, 14)),
            ("Monday 14:00 ET, after kickoff",
             datetime.datetime(2026, 9, 14, 14, 0), datetime.date(2026, 9, 21)),
            ("Wednesday 10:00 ET, mid-offseason",
             datetime.datetime(2026, 9, 16, 10, 0), datetime.date(2026, 9, 21))):
        _tm._nowEastern = (lambda v: (lambda: v))(fakeEt)
        got = SeasonManager._firstGameDate(TimingManager._nextSeasonAnchorUtc())
        expect(f"{label} -> first game day {got:%a %Y-%m-%d}", got == wantGameDay)
finally:
    _tm._nowEastern = _realNow

print("\n2. Day 0 is Monday whatever the anchor is, in BOTH DST regimes")
# (anchor UTC, what it is in ET, the Monday it must produce)
CASES = [
    (datetime.datetime(2026, 9, 20, 23, 0),  "Sun 19:00 ET, EDT",  datetime.date(2026, 9, 21)),
    (datetime.datetime(2026, 12, 14, 0, 0),  "Sun 19:00 ET, EST",  datetime.date(2026, 12, 14)),
    # the two legacy anchors -- an existing database must not move
    (datetime.datetime(2026, 9, 21, 8, 0),   "Mon 04:00 ET, EDT",  datetime.date(2026, 9, 21)),
    (datetime.datetime(2026, 12, 14, 9, 0),  "Mon 04:00 ET, EST",  datetime.date(2026, 12, 14)),
    (datetime.datetime(2026, 9, 21, 4, 0),   "Mon 04:00 UTC",      datetime.date(2026, 9, 21)),
]
for anchor, label, want in CASES:
    got = SeasonManager._firstGameDate(anchor)
    expect(f"{label:20} -> day 0 = {got:%a %Y-%m-%d}", got == want and got.weekday() == 0)

print("\n3. The naive read this replaces would have been wrong")
# The EST Sunday case is the one that proves it: .date() on the UTC stamp says Monday only
# by accident of the offset, and the EDT one says Sunday outright.
edt = datetime.datetime(2026, 9, 20, 23, 0)
expect("a naive .date() on the EDT Sunday anchor reads Sunday (the bug)",
       edt.date().weekday() == 6 and SeasonManager._firstGameDate(edt).weekday() == 0)

print("\n4. Nothing still calls the Monday-named helpers")
import subprocess
# ⚠️ EXCLUDES THIS FILE, which otherwise matches its own search string and fails forever.
out = subprocess.run(["grep", "-rn", "--include=*.py",
                      "--exclude=" + os.path.basename(__file__),
                      "_nextMondayUtc(\|_lastMondayUtc(", "."],
                     capture_output=True, text=True).stdout
expect(f"no live callers of the old names ({len(out.splitlines())} hits)", not out.strip())

print("\n" + ("FAIL" if fails else "PASS") + " — the season opens Sunday evening; games still start Monday.")
for f in fails: print("   -", f)
sys.exit(1 if fails else 0)
