"""The first snap pays its pre-snap drain too.

⚠️ `_estimateAvailablePlays` CHARGED EVERY SNAP AFTER THE FIRST AN INTER-PLAY GAP AND THE
FIRST SNAP NOTHING. The loop subtracts 3s on a timeout, 5s on a spike and 18s otherwise
between plays, but it entered on `secs > FINAL_SNAP_SECS` and then charged the first snap
only its 7s of execution — so the huddle standing in front of it was free. That is the
whole "counts a play that does not fit" defect: at 0:15 with the clock running and no
timeout, a snap really costs a ~12s hurry-up huddle plus the live ball, and the helper
reported room for two.

⚠️ TIGHTENING THE LOOP CONDITION IS THE WRONG FIX AND MEASURED WORSE. `secs >= 7` was
tried first: late FG attempts fell 33 -> 18 over 40 games a side and halves ending in
range rose 21 -> 24. The count feeds six decisions with OPPOSITE senses — `<= 1` kicks,
`>= 2` and `>= 1` allow a clock-stopper — so a blunt reduction buys a kick and loses the
clock management that gets a drive into range at all. Over a 1,728-state sweep that
attempt moved **8.3%** of states; charging the first snap moves **1.4-1.7%**, because it
removes exactly one phantom play and only where one was really phantom.

⚠️ THE MEASURED OUTCOME EFFECT IS ZERO, and that is expected rather than disappointing.
`_lastSnapBeforeBreak` was added later and takes the end-of-half kick DIRECTLY, so it
already catches the kick decisions this over-count used to break. Over 500 games a side at
four downs and five: wasted halves 42 -> 39 and 39 -> 38, late FG attempts 648 -> 689 and
545 -> 538, every delta inside its confidence interval. The value here is that the helper's
contract is true again and no longer contradicts the cost model `_lastSnapBeforeBreak`
validated — it is still consulted by two spike gates that helper does not cover.

Run: .venv/bin/python test_available_plays.py
"""
import unittest

from scenario import Scenario
from constants import (LAST_SNAP_HUDDLE_SECS, LAST_SNAP_LIVE_SECS,
                       NO_HUDDLE_PRESNAP_FLOOR)


def _at(clock, *, timeouts=0, running=True, down=1, diff=-7, ballOn=35):
    """Place a real Game late in Q4 and hand back (game, estimate)."""
    s = Scenario()
    s.situation(quarter=4, clock=clock, offense='home', offScore=21 + diff,
                defScore=21, down=down, distance=8, ballOn=ballOn,
                offTimeouts=timeouts, defTimeouts=3, clockRunning=running)
    return s.game, s.game._estimateAvailablePlays()


class FirstSnapPaysItsHuddle(unittest.TestCase):

    def test_noRoomForASnapThatDoesNotFit(self):
        """Clock running, no timeout: a snap costs its pre-snap drain plus the live
        ball, so a clock too short to hold one must report zero productive plays.

        ⚠️ Anchored to the FLOOR, not to a sampled cost. `_noHuddlePreSnapSecs` carries
        coach-IQ spread and +/-1 jitter, so asserting against a second call samples a
        different number than the estimate used and the test flakes."""
        floor = NO_HUDDLE_PRESNAP_FLOOR + LAST_SNAP_LIVE_SECS
        clock = floor - 1          # cheaper than the cheapest snap in the game
        _, plays = _at(clock)
        self.assertEqual(plays, 0,
                         f'reported room for a snap at 0:{clock:02d}, under the {floor}s floor')

    def test_countNeverExceedsWhatTheClockCanHold(self):
        """The helper is allowed to be conservative; it is not allowed to be optimistic.
        Across the short band it must never claim more snaps than the clock affords.

        ⚠️ Bounded by the CHEAPEST a snap can be, not by a fresh sample. Calling
        `_noHuddlePreSnapSecs` again draws different jitter than the estimate used, so
        comparing against it fails ~25% of runs on a helper that is behaving correctly."""
        for clock in (8, 10, 12, 15, 20, 25, 30, 40):
            game, plays = _at(clock)
            per = (NO_HUDDLE_PRESNAP_FLOOR if game._isNoHuddle()
                   else LAST_SNAP_HUDDLE_SECS) + LAST_SNAP_LIVE_SECS
            self.assertLessEqual(plays * per, clock,
                                 f'at 0:{clock:02d} claimed {plays} snaps at >= {per}s each')

    def test_aTimeoutMakesTheHuddleFree(self):
        """⚠️ Guard against OVER-charging. A timeout in hand stops the clock, so the
        huddle costs nothing — charging it anyway would declare the last snap early and
        end drives that had another play in them."""
        _, withTO = _at(20, timeouts=2)
        _, without = _at(20, timeouts=0)
        self.assertGreater(withTO, without,
                           'a timeout has to buy at least one more snap than having none')

    def test_stoppedClockMakesTheHuddleFree(self):
        """Nothing is ticking during a huddle on a stopped clock, so it is not charged."""
        _, stopped = _at(20, running=False)
        _, running = _at(20, running=True)
        self.assertGreater(stopped, running,
                           'a stopped clock must afford at least one more snap')

    def test_noHuddlePaysItsOwnSmallerCost(self):
        """A no-huddle snap does not cost a huddle. The charge reads the tempo's real
        pre-snap time rather than a flat 12s, so the two cannot drift apart."""
        game, _ = _at(30)
        if not game._isNoHuddle():
            self.skipTest('fixture did not reach no-huddle tempo')
        self.assertLess(game._noHuddlePreSnapSecs(), LAST_SNAP_HUDDLE_SECS,
                        'no-huddle must be cheaper than a huddle or the charge is wrong')


class TheSpikeGatesStillOpen(unittest.TestCase):
    """⚠️ THIS IS THE REGRESSION THAT KILLED THE EARLIER ATTEMPT. The count gates both
    kicks (low) and clock-stoppers (high). Reducing it far enough to buy kicks closed the
    spike gates, drives stopped reaching field-goal range, and late attempts FELL. These
    assert the clock management survives the correction."""

    def test_spikeGateOpenInItsOperatingRange(self):
        """`>= 1` — room for the spike plus a real play — must still hold at the clock
        values a two-minute drill actually runs at."""
        for clock in (45, 60, 80, 100, 120):
            _, plays = _at(clock, down=1)
            self.assertGreaterEqual(plays, 1,
                                    f'spike gate closed at 0:{clock} — drives cannot stop the clock')

    def test_chessClockSpikeGateOpenInItsOperatingRange(self):
        """`>= 2` — room for the spike AND a real snap after it."""
        for clock in (60, 80, 100, 120):
            _, plays = _at(clock, down=1)
            self.assertGreaterEqual(plays, 2,
                                    f'the >= 2 spike gate closed at 0:{clock}')

    def test_aWholeDriveStillHasPlaysInIt(self):
        """A fresh possession with timeouts must read as a drive, not a last gasp."""
        _, plays = _at(120, timeouts=3)
        self.assertGreaterEqual(plays, 4,
                                'a two-minute drill with all timeouts must afford several snaps')


class TheFixIsWhereItClaimsToBe(unittest.TestCase):

    def test_chargeReusesTheValidatedCostModel(self):
        """The charge must be gated on `canStopClock` and read the no-huddle cost, so it
        stays tied to `_lastSnapBeforeBreak` instead of becoming a second cost model."""
        with open('floosball_game.py') as fh:
            src = fh.read()
        body = src.split('def _estimateAvailablePlays')[1].split('\n    def ')[0]
        self.assertIn('canStopClock', body,
                      'the huddle must only be charged when the clock cannot be stopped')
        self.assertIn('_noHuddlePreSnapSecs', body,
                      'a no-huddle snap must not be charged a full huddle')
        self.assertNotIn('while secs >= 7', body,
                         'the loop-condition tightening measured WORSE — see the docstring')


if __name__ == '__main__':
    unittest.main(verbosity=2)
