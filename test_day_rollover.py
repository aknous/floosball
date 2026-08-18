"""The next game day opens right after the last one finishes.

A game day is 7 rounds on the hour, 12:00-18:00 ET, so a cross-day boundary (weeks 8, 15,
22) is an 18-hour gap. The week rollover across that gap is what publishes the next day's
slate for pick-em and advances `shopDay` for the pack rotation — so its lead is really
"how long after the games do users wait for tomorrow to open".

⚠️ IT WAS 480 MINUTES, WHICH IS 04:00 ET ON THE GAME DAY — not "the prior evening" as both
CLAUDE.md and the engine comment claimed. So the next slate stayed hidden for ~9 hours
after the day's games ended. Reported by a user. Now 1020 (17h) = 19:00 ET, about 15
minutes after the final whistle.

⚠️ CLEARING `completedWeekGames` EARLY IS ONLY SAFE BECAUSE FINISHED GAMES ARE VIEWABLE.
`games.team_stats` plus `game_player_stats` keep the box score, served by
`GET /api/games/{id}` and `/api/weekGames`. Before those were persisted, an early rollover
would have taken the day's results off the site.

⚠️ THE SHOP'S TWO REFRESH PATHS ARE NOW ONE MOMENT. The pack rotation follows `shopDay`
off the week rollover, and the daily allowances (reroll costs, per-day buy limits) used to
follow a fixed `DAILY_RESET_HOUR_UTC`. That constant is GONE: under EST the rollover landed
at 00:00 UTC, exactly its value, so the two agreed and the fixed hour looked right; under
EDT the rollover is 23:00 UTC and the reset stayed at midnight, leaving an hour each game
day with new packs beside yesterday's reroll prices. See test_shop_day_boundary.py.

⚠️ AND THE PACK CAP'S CYCLE BOUNDARY IS LOAD-BEARING. `_shopCycleStartDate` used
`start_date + days` (04:00 UTC), which sat safely in the past only while the rollover ran
at 08:00 UTC. Against a 19:00 ET rollover that anchor is ~5 hours in the FUTURE, which
trips its `cycleStart > now` clamp — and that clamp reaches a YEAR back, so the per-cycle
count would include every paid open of the season and the shop would refuse to sell
anything for the first five hours of each new game day. The boundary is now derived from
the same kickoff-minus-lead the rollover uses.

Run: .venv/bin/python test_day_rollover.py
"""
import datetime as dt
import unittest

from constants import CROSS_DAY_ROLLOVER_LEAD_MINUTES as LEAD
from managers.timingManager import _isEdtDate

# Season anchors chosen to exercise both DST states: August is EDT, January is EST.
EDT_START = dt.datetime(2026, 8, 10, 4)     # prod season 1's real anchor
EST_START = dt.datetime(2027, 1, 11, 4)
CROSS_DAY_WEEKS = (8, 15, 22)


def _dayTimes(startDate, dayIndex):
    """(kickoff, lastRoundStart, utcOffset) in UTC for a given game day."""
    tgt = (startDate + dt.timedelta(days=dayIndex)).date()
    off = 4 if _isEdtDate(tgt) else 5
    return (dt.datetime(tgt.year, tgt.month, tgt.day, 12 + off),
            dt.datetime(tgt.year, tgt.month, tgt.day, 18 + off),
            off)


def _rollover(startDate, dayIndex):
    kick, _, _ = _dayTimes(startDate, dayIndex)
    return kick - dt.timedelta(minutes=LEAD)


def _shopCycleBoundary(startDate, shopDay):
    """Mirrors cardManager._shopCycleStartDate's cross-day branch."""
    if shopDay <= 1:
        return startDate
    tgt = (startDate + dt.timedelta(days=shopDay - 1)).date()
    off = 4 if _isEdtDate(tgt) else 5
    kick = dt.datetime(tgt.year, tgt.month, tgt.day, 12 + off)
    return kick - dt.timedelta(minutes=LEAD)


class TheNextDayOpensAfterTheLastOneEnds(unittest.TestCase):

    def test_rollsOverAfterTheFinalWhistleAndBeforeKickoff(self):
        """The window is bounded on both sides: never while the day's last game is still
        being played, and never so late that the slate is hidden into the game day."""
        for label, start in (('EDT', EDT_START), ('EST', EST_START)):
            for dayIndex in (1, 2, 3):
                kick, _, _ = _dayTimes(start, dayIndex)
                _, prevLast, _ = _dayTimes(start, dayIndex - 1)
                prevEnd = prevLast + dt.timedelta(minutes=45)   # rounds fit inside the hour
                roll = _rollover(start, dayIndex)
                self.assertGreaterEqual(roll, prevEnd,
                                        f'{label} day {dayIndex}: rollover lands mid-slate')
                self.assertLess(roll, kick,
                                f'{label} day {dayIndex}: rollover is not before kickoff')

    def test_rollsOverTheEveningBefore(self):
        """The whole point of the change: 19:00 ET, not 04:00 ET on the game day.

        ⚠️ Asserted in EASTERN, not UTC — the lead is subtracted from an ET-anchored
        kickoff, so it is DST-stable in ET and would drift by an hour if read as UTC."""
        for label, start in (('EDT', EDT_START), ('EST', EST_START)):
            for dayIndex in (1, 2, 3):
                _, _, off = _dayTimes(start, dayIndex)
                roll = _rollover(start, dayIndex)
                etHour = (roll - dt.timedelta(hours=off)).hour
                self.assertGreaterEqual(etHour, 12,
                                        f'{label}: rollover at {etHour}:00 ET is the game-day '
                                        f'morning, not the evening before')

    def test_leadStaysInsideTheSafeBand(self):
        """Below 15 min it is not a cross-day rollover at all; past 1035 (18:45 ET) the
        moment lands while the day's final game is still running."""
        self.assertGreater(LEAD, 15)
        self.assertLessEqual(LEAD, 1035)


class TheShopRefreshesWithIt(unittest.TestCase):

    def test_theDailyAllowancesResetAtTheRolloverItself(self):
        """⚠️ ONE BOUNDARY, NOT TWO. This is the assertion the old fixed-hour version could
        not make: it checked only that the reset landed within 12 hours of the whistle,
        which an hour of drift passes comfortably."""
        from database.repositories.shop_repository import _rolloverMomentUtc
        for label, start in (('EDT', EDT_START), ('EST', EST_START)):
            for dayIndex in (1, 2, 3):
                gameDate = (start + dt.timedelta(days=dayIndex)).date()
                self.assertEqual(_rolloverMomentUtc(gameDate), _rollover(start, dayIndex),
                                 f'{label}: the shop day and the week rollover disagree')

    def test_cycleBoundaryEqualsTheRolloverSoTheClampCannotFire(self):
        """⚠️ THIS IS THE ONE THAT BREAKS PURCHASES. If the cycle boundary is later than
        the rollover, it is in the future at the moment `shopDay` advances, the
        `cycleStart > now` clamp reaches a year back, and the per-cycle pack cap reads as
        already spent."""
        for label, start in (('EDT', EDT_START), ('EST', EST_START)):
            for shopDay in (2, 3, 4):
                boundary = _shopCycleBoundary(start, shopDay)
                roll = _rollover(start, shopDay - 1)
                self.assertLessEqual(boundary, roll,
                                     f'{label} shopDay {shopDay}: boundary is after the '
                                     f'rollover — the cap will read as exhausted')

    def test_cycleBoundariesAreExactlyOneDayApart(self):
        """Consecutive cycles must not overlap (double allowance) or gap (opens escaping
        the count entirely)."""
        for label, start in (('EDT', EDT_START), ('EST', EST_START)):
            for shopDay in (3, 4):
                delta = _shopCycleBoundary(start, shopDay) - _shopCycleBoundary(start, shopDay - 1)
                self.assertEqual(delta, dt.timedelta(days=1),
                                 f'{label} shopDay {shopDay}: cycles are {delta} apart')


class TheWiringIsWhereItClaimsToBe(unittest.TestCase):

    def test_seasonManagerUsesTheConstant(self):
        with open('managers/seasonManager.py') as fh:
            src = fh.read()
        self.assertIn('CROSS_DAY_ROLLOVER_LEAD_MINUTES if isCrossDayTransition', src)
        self.assertNotIn('earlyMinutes = 480 if isCrossDayTransition', src,
                         'the hardcoded 8-hour lead is back')

    def test_shopCycleDerivesFromTheSameLead(self):
        with open('managers/cardManager.py') as fh:
            src = fh.read()
        body = src.split('def _shopCycleStartDate')[1].split('\ndef ')[0]
        self.assertIn('CROSS_DAY_ROLLOVER_LEAD_MINUTES', body,
                      'the cycle boundary must track the rollover, not a bare day anchor')
        self.assertNotIn('cycleStart = season.start_date + _dt.timedelta(days=shopDay - 1)', body,
                         'the naive 04:00 UTC anchor is back — it trips the year-long clamp')


if __name__ == '__main__':
    unittest.main(verbosity=2)
