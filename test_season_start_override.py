"""An admin can start the next season early (`season_start_override`, 2026-10-04).

The override lives in `TimingManager._nextSeasonAnchorUtc`, the one helper the wait, the
schedule and the fans' countdown all read, and the schedule's day 0 follows the anchor
rather than snapping to a Monday, or an early start on any other weekday would slide back
to the next Monday.
"""
import datetime as dt

import managers.timingManager as tm
from managers.timingManager import TimingManager, firstGameDateFor


def test_day_zero_follows_the_anchor_on_any_weekday():
    for offset in range(7):
        day = dt.date(2026, 10, 5) + dt.timedelta(days=offset)
        assert firstGameDateFor(TimingManager._seasonAnchorFor(day)) == day, day


def test_monday_anchors_still_resolve_to_monday():
    for anchor in (dt.datetime(2026, 9, 13, 23, 0),     # Sun 19:00 ET, EDT
                   dt.datetime(2026, 12, 14, 0, 0),     # Sun 19:00 ET, EST
                   dt.datetime(2026, 9, 14, 8, 0)):     # Mon 04:00 ET, the old anchor
        assert firstGameDateFor(anchor).weekday() == 0, anchor


def test_a_future_override_moves_the_start(monkeypatch):
    day = (dt.datetime.utcnow() + dt.timedelta(days=3)).date()
    monkeypatch.setattr(tm, 'seasonStartOverride', lambda: day)
    assert TimingManager._nextSeasonAnchorUtc() == TimingManager._seasonAnchorFor(day)
    assert firstGameDateFor(TimingManager._nextSeasonAnchorUtc()) == day


def test_a_passed_override_is_ignored(monkeypatch):
    day = (dt.datetime.utcnow() - dt.timedelta(days=2)).date()
    monkeypatch.setattr(tm, 'seasonStartOverride', lambda: day)
    assert TimingManager._nextSeasonAnchorUtc() == TimingManager._defaultNextSeasonAnchorUtc()


def test_no_override_is_the_usual_monday(monkeypatch):
    monkeypatch.setattr(tm, 'seasonStartOverride', lambda: None)
    assert firstGameDateFor(TimingManager._nextSeasonAnchorUtc()).weekday() == 0


def test_the_season_that_uses_it_clears_it():
    src = open('managers/seasonManager.py').read()
    i = src.index('        if not scheduleLoaded:\n            self.createSchedule()')
    assert 'clearSeasonStartOverride()' in src[i:i + 400]


def _scheduledTiming():
    t = TimingManager(tm.TimingMode.SCHEDULED)
    t.delays['daily_check'] = 0.01
    return t


def test_the_week_waits_follow_a_moved_schedule():
    """A season created and waiting for week 1 can be moved (`rescheduleUnstartedSeason`);
    the waits must re-read their target, or they sit on the old kickoff."""
    import asyncio
    far = dt.datetime.utcnow() + dt.timedelta(days=7)
    moved = {'to': far}

    async def run(waitFn):
        async def moveSoon():
            await asyncio.sleep(0.05)
            moved['to'] = dt.datetime.utcnow() - dt.timedelta(seconds=1)
        mover = asyncio.ensure_future(moveSoon())
        await asyncio.wait_for(waitFn(far, targetFn=lambda: moved['to']), timeout=2)
        await mover

    asyncio.run(run(_scheduledTiming().waitForWeekSetup))
    moved['to'] = far
    asyncio.run(run(_scheduledTiming().waitForGamesStart))
