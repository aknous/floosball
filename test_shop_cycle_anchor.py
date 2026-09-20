"""
THE SHOP CYCLE BOUNDARY IS THE WEEK ROLLOVER, AND THE FIRST GAME DAY IS DERIVED.

⚠️ `Season.start_date` is a NAIVE UTC stamp, so `start_date.date()` asks what day it is in
LONDON. At the old 04:00 ET Monday anchor that was Monday either way and the naive read
worked. At 19:00 ET Sunday it is **23:00 UTC Sunday in EDT and 00:00 UTC Monday in EST** —
so the naive read lands on Sunday for half the year, and every shop cycle starts a FULL DAY
EARLY.

Production symptom: day 1's pack opens were still inside day 2's window, so the shop said
"Cycle limit reached (5 of 5). Refreshes next cycle" from the first hour of the second game
day.

⚠️ THE WORST PART IS THAT IT IS SEASONAL — correct all winter, wrong from March to November.
A test written in December passes against the broken code.

`timingManager.firstGameDateFor` is the one definition; `seasonManager._firstGameDate`
delegates to it and the shop uses it. This pins all three.
"""
import datetime as dt

from constants import CROSS_DAY_ROLLOVER_LEAD_MINUTES as LEAD
from managers.timingManager import firstGameDateFor, _isEdtDate

EDT_ANCHOR = dt.datetime(2026, 9, 13, 23, 0)    # Sun 19:00 ET, EDT  -> first game Mon 09-14
EST_ANCHOR = dt.datetime(2026, 12, 14, 0, 0)    # Sun 19:00 ET, EST  -> first game Mon 12-14
OLD_ANCHOR = dt.datetime(2026, 9, 14, 8, 0)     # Mon 04:00 ET, the pre-2026-09 anchor


def _rolloverFor(anchor, shopDay):
    """The real moment shopDay begins: that day's first kickoff minus the lead."""
    d = firstGameDateFor(anchor) + dt.timedelta(days=shopDay - 1)
    off = 4 if _isEdtDate(d) else 5
    return dt.datetime(d.year, d.month, d.day, 12 + off) - dt.timedelta(minutes=LEAD)


def testFirstGameDayIsAlwaysAMonday():
    for a in (EDT_ANCHOR, EST_ANCHOR, OLD_ANCHOR):
        assert firstGameDateFor(a).weekday() == 0, (a, firstGameDateFor(a))


def testTheNaiveReadIsWrongInEdtAndThatIsTheBug():
    """⚠️ The exact fault, pinned in both directions so the seasonal half cannot hide."""
    # EDT: the naive date is SUNDAY, a day before the real first game day.
    assert EDT_ANCHOR.date() == dt.date(2026, 9, 13)
    assert firstGameDateFor(EDT_ANCHOR) == dt.date(2026, 9, 14)
    assert EDT_ANCHOR.date() != firstGameDateFor(EDT_ANCHOR), 'the EDT fault must be visible'
    # EST: the naive date happens to be right, which is why this passes half the year.
    assert EST_ANCHOR.date() == firstGameDateFor(EST_ANCHOR) == dt.date(2026, 12, 14)


def testTheOldAnchorStillResolvesToItself():
    """A season already anchored on a Monday is its own day 0 — a generalisation, not a move."""
    assert firstGameDateFor(OLD_ANCHOR) == dt.date(2026, 9, 14)


def testEachShopDayStartsOnItsOwnRollover():
    """Day N's cycle must begin at day N's rollover — not day N-1's."""
    for anchor in (EDT_ANCHOR, EST_ANCHOR):
        moments = [_rolloverFor(anchor, d) for d in (1, 2, 3, 4)]
        # strictly increasing, exactly 24h apart, and day 1 IS the season anchor
        assert moments[0] == anchor, (anchor, moments[0])
        for i in range(1, 4):
            gap = moments[i] - moments[i - 1]
            assert gap == dt.timedelta(days=1), (anchor, i, gap)


def testDayOneOpensDoNotCountOnDayTwo():
    """The production symptom, stated as arithmetic."""
    openedOnDay1 = _rolloverFor(EDT_ANCHOR, 1) + dt.timedelta(hours=6)   # Monday morning
    assert openedOnDay1 < _rolloverFor(EDT_ANCHOR, 2), \
        'a day-1 open must fall OUTSIDE day 2 window'


def testSeasonManagerDelegatesRatherThanDuplicating():
    """
    ⚠️ The math existed in two places and the copy was written naively. Assert they agree,
    so a future edit to one cannot silently reintroduce the split.
    """
    from managers.seasonManager import SeasonManager
    for a in (EDT_ANCHOR, EST_ANCHOR, OLD_ANCHOR):
        assert SeasonManager._firstGameDate(a) == firstGameDateFor(a), a


if __name__ == '__main__':
    for n, f in sorted(globals().items()):
        if n.startswith('test') and callable(f):
            f(); print('ok', n)
