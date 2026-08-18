"""The shop has one day boundary, not two.

⚠️ REPORTED BY A USER: "day 2 packs are purchaseable, the week rolled over, but the card
and pack reroll costs haven't reset yet."

Both halves of the shop are meant to turn over together, and they were computed two
different ways:

    pack rotation      `shopDay` off the week rollover -- 12:00 ET minus the cross-day
                       lead, i.e. ET-anchored
    daily allowances   `DAILY_RESET_HOUR_UTC`, a fixed UTC hour

⚠️ THEY AGREED IN WINTER, WHICH IS WHY THE FIXED HOUR LOOKED CORRECT WHEN IT WAS CHOSEN.
Under EST the rollover is 12:00 + 5 - 17h = 00:00 UTC -- exactly midnight, the constant's
value. Under EDT it is 23:00 UTC while the reset stayed at 00:00, so every game day of the
summer had a ONE-HOUR WINDOW, 19:00-20:00 ET, in which the new day's packs were on sale
beside yesterday's reroll prices. The report arrived inside that window.

The boundary is now derived from the same expression the rollover uses, so the two cannot
drift and both follow the lead if it is ever moved again. The old constant is deleted;
this file also guards against a fixed hour being reintroduced.

Run: .venv/bin/python test_shop_day_boundary.py
"""
import datetime as dt
import unittest
from unittest.mock import patch

from constants import CROSS_DAY_ROLLOVER_LEAD_MINUTES as LEAD
from managers.timingManager import _isEdtDate
from database.repositories import shop_repository
from database.repositories.shop_repository import _rolloverMomentUtc, _dailyResetBoundary

EDT_DAY = dt.date(2026, 8, 18)     # the reported season
EST_DAY = dt.date(2027, 1, 14)


def rolloverFromTheSimSide(gameDate):
    """The rollover moment, written out independently of the code under test -- the same
    arithmetic `seasonManager.getWeekStartTime` and `cardManager._shopCycleStartDate` do."""
    offset = 4 if _isEdtDate(gameDate) else 5
    kickoff = dt.datetime(gameDate.year, gameDate.month, gameDate.day, 12 + offset)
    return kickoff - dt.timedelta(minutes=LEAD)


class OneBoundary(unittest.TestCase):

    def test_theShopDayStartsExactlyWhenTheWeekRollsOver(self):
        """THE REGRESSION, stated directly."""
        for label, day in (('EDT', EDT_DAY), ('EST', EST_DAY)):
            self.assertEqual(_rolloverMomentUtc(day), rolloverFromTheSimSide(day),
                             f'{label}: packs and allowances turn over at different times')

    def test_theOldFixedHourWasAnHourLateInSummer(self):
        """⚠️ Pins the defect itself, so the fix cannot be quietly undone by someone
        reinstating a constant that 'looks equivalent'. It IS equivalent -- in winter."""
        oldReset = 0   # the deleted DAILY_RESET_HOUR_UTC

        def gapHours(day):
            roll = rolloverFromTheSimSide(day)
            reset = roll.replace(hour=oldReset, minute=0, second=0, microsecond=0)
            if reset < roll:
                reset += dt.timedelta(days=1)
            return (reset - roll).total_seconds() / 3600.0

        self.assertEqual(gapHours(EDT_DAY), 1.0, 'the summer gap should be exactly an hour')
        self.assertEqual(gapHours(EST_DAY), 0.0, 'winter is why it went unnoticed')

    def test_theConstantIsGone(self):
        """A fixed UTC hour cannot track an ET-anchored schedule. Deleting it is the fix;
        this fails loudly if one comes back."""
        import constants
        self.assertFalse(hasattr(constants, 'DAILY_RESET_HOUR_UTC'))


class TheBoundaryBehavesAcrossADay(unittest.TestCase):
    """`_dailyResetBoundary` picks the most recent rollover that has passed. Driven at
    real instants rather than asserted on its internals."""

    def _at(self, whenUtc):
        class FrozenDatetime(dt.datetime):
            @classmethod
            def utcnow(cls):
                return whenUtc
        with patch.object(shop_repository, 'datetime', FrozenDatetime):
            return _dailyResetBoundary()

    def test_justBeforeTheRolloverTheBoundaryIsStillYesterdays(self):
        roll = rolloverFromTheSimSide(EDT_DAY)
        got = self._at(roll - dt.timedelta(minutes=1))
        self.assertEqual(got, rolloverFromTheSimSide(EDT_DAY - dt.timedelta(days=1)))

    def test_atTheRolloverTheNewShopDayHasStarted(self):
        roll = rolloverFromTheSimSide(EDT_DAY)
        self.assertEqual(self._at(roll), roll)

    def test_insideTheOldGapTheAllowancesHaveAlreadyReset(self):
        """⚠️ THE REPORTED MOMENT: 19:30 ET, after the packs rotated and before midnight
        UTC. Under the old rule this still returned the PREVIOUS day, which is precisely
        why the reroll price had not moved."""
        roll = rolloverFromTheSimSide(EDT_DAY)
        inGap = roll + dt.timedelta(minutes=30)
        self.assertEqual(self._at(inGap), roll)

    def test_itNeverReturnsAMomentInTheFuture(self):
        """A boundary ahead of now counts nothing, so every allowance would read as unused
        and every reroll would be free."""
        for hour in range(0, 24, 3):
            now = dt.datetime(2026, 8, 18, hour, 17)
            self.assertLessEqual(self._at(now), now)

    def test_theBoundaryIsNeverMoreThanADayBack(self):
        """The other direction: too far back and yesterday's rerolls keep counting, so the
        price never resets at all."""
        for hour in range(0, 24, 3):
            now = dt.datetime(2026, 8, 18, hour, 17)
            self.assertGreater(self._at(now), now - dt.timedelta(days=1, minutes=1))

    def test_itAdvancesExactlyOncePerDay(self):
        """Sweep a week at ten-minute steps: the boundary must take exactly one distinct
        value per game day, never oscillate."""
        DAYS = 7
        seen = []
        now = dt.datetime(2026, 8, 15, 0, 0)
        end = now + dt.timedelta(days=DAYS)
        while now < end:
            boundary = self._at(now)
            if not seen or boundary != seen[-1]:
                seen.append(boundary)
            now += dt.timedelta(minutes=10)
        # DAYS + 1: one boundary is already in force when the sweep starts, then the sweep
        # crosses one per day.
        self.assertEqual(len(seen), DAYS + 1, f'expected {DAYS + 1} boundaries, got {seen}')
        for earlier, later in zip(seen, seen[1:]):
            self.assertEqual(later - earlier, dt.timedelta(days=1),
                             'the shop day should advance in exact days')


if __name__ == '__main__':
    unittest.main(verbosity=2)
