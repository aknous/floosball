"""No-huddle: the offense stays at the line, and a snap stops costing a huddle.

⚠️ THE OFFENSE HAD NO PRESENCE BETWEEN THE WHISTLE AND THE SNAP. Tempo was one
coach-scaled number, so "hurry-up" meant a 12-second huddle instead of a 25-40 second one
and the team ALWAYS huddled — there was no state in which they did not.

The trigger is the CLOCK, not a coach preference (owner, 2026-08-12): if the clock did not
stop on the last play and the offense is in hurry-up, they stay at the line. Both halves
are state the engine already had.

Measured, step 1 of `docs/NO_HUDDLE_AUDIBLES_PLAN.md`:

    pre-snap drain      12.0s  ->  6.0s
    snaps in a 110s drill  6.0  ->  9.5   (+58%)

⚠️ THAT IS THE PURCHASE, NOT THE BALANCE. No-huddle is supposed to buy ~6 seconds a snap
and pay for it by being predictable — step 3 of the plan adds that cost as a negative
disguise in `_applyPreSnapRead`. Until it lands, no-huddle is a free win, and these tests
deliberately assert the PURCHASE so the later step has a fixed baseline to be measured
against.

Run: .venv/bin/python test_no_huddle.py
"""

import logging
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
logging.disable(logging.CRITICAL)

import constants  # noqa: E402
from scenario import Scenario  # noqa: E402


def drill(clock=110, offScore=14, defScore=21, quarter=4, timeouts=1):
    """A trailing offense in a two-minute drill with the clock running."""
    s = Scenario()
    s.situation(quarter=quarter, clock=clock, offense='home',
                offScore=offScore, defScore=defScore,
                down=1, distance=10, ballOn=60,
                offTimeouts=timeouts, defTimeouts=3)
    s.game.clockRunning = True
    return s.game


class TheTriggerIsTheClock(unittest.TestCase):
    def testHurryUpWithARunningClockIsNoHuddle(self):
        g = drill()
        self.assertEqual(g._classifyTempoIntent()[0], 'hurryUp')
        self.assertTrue(g._isNoHuddle())

    def testAStoppedClockMeansTheyMayHuddle(self):
        """Nothing is saved by rushing when the clock is not moving."""
        g = drill()
        g.clockRunning = False
        self.assertFalse(g._isNoHuddle())

    def testANeutralTempoIsNeverNoHuddle(self):
        g = drill(clock=800, offScore=21, defScore=21, quarter=1)
        self.assertNotEqual(g._classifyTempoIntent()[0], 'hurryUp')
        self.assertFalse(g._isNoHuddle())

    def testTheFlagTurnsItOffEntirely(self):
        g = drill()
        original = constants.NO_HUDDLE_ENABLED
        try:
            constants.NO_HUDDLE_ENABLED = False
            self.assertFalse(g._isNoHuddle())
        finally:
            constants.NO_HUDDLE_ENABLED = original


class TheCostModel(unittest.TestCase):
    def testANoHuddleSnapCostsAboutHalfAHurryUpHuddle(self):
        g = drill()
        noHuddle = [g._noHuddlePreSnapSecs() for _ in range(200)]
        self.assertLess(max(noHuddle), constants.LAST_SNAP_HUDDLE_SECS,
                        'a no-huddle snap should never cost a full hurry-up huddle')
        self.assertLessEqual(sum(noHuddle) / len(noHuddle), 8.0)
        self.assertGreaterEqual(min(noHuddle), constants.NO_HUDDLE_PRESNAP_FLOOR)

    def testItGoesBelowTheHuddleFloor(self):
        """⚠️ `calculatePreSnapTime` floors at 8s, and that floor models a HUDDLE being
        unrealistically quick. This is the state of not huddling, so it must be allowed
        under it — otherwise no-huddle buys almost nothing."""
        self.assertLess(constants.NO_HUDDLE_PRESNAP_FLOOR, 8)
        g = drill()
        self.assertLess(min(g._noHuddlePreSnapSecs() for _ in range(200)), 8)

    def testTheDrainRunsThroughCalculatePreSnapTime(self):
        """The short-circuit has to be in the real entry point, or nothing consumes it."""
        g = drill()
        g.recordTempoIntent()
        self.assertLessEqual(g.calculatePreSnapTime(), 8)

    def testASharpClockManagerLinesUpFaster(self):
        """Coach IQ still matters at the line, at half the huddle's spread."""
        self.assertGreater(constants.NO_HUDDLE_IQ_SPREAD, 0)
        self.assertLess(constants.NO_HUDDLE_IQ_SPREAD, 6)


class TheLastSnapHelperReadsTheTempo(unittest.TestCase):
    """⚠️ The chess-clock fix (2026-08-13) already made this helper tempo-aware in ITS
    branch, while the standard branch kept charging a flat 12s whatever the offense was
    doing. Overcharging makes the helper declare the LAST snap early, ending drives that
    had another play in them."""

    def testItChargesTheNoHuddleCostNotTheHuddle(self):
        # No timeouts and a running clock is the branch that pays a huddle.
        g = drill(clock=14, timeouts=0)
        self.assertTrue(g._isNoHuddle())
        self.assertFalse(g._lastSnapBeforeBreak(),
                         'at 14s a no-huddle snap plus the live ball still fits')

    def testAHuddlingOffenseStillPaysTheHuddle(self):
        g = drill(clock=14, timeouts=0)
        original = constants.NO_HUDDLE_ENABLED
        try:
            constants.NO_HUDDLE_ENABLED = False
            self.assertTrue(g._lastSnapBeforeBreak(),
                            'at 14s a 12s huddle plus the live ball does not fit')
        finally:
            constants.NO_HUDDLE_ENABLED = original


class TheAnnouncementLatch(unittest.TestCase):
    """⚠️ Announce on ENTERING, once. A six-play drill saying "goes no-huddle" six times is
    noise, and the cadence rule is one pre-snap line per snap."""

    def testItAnnouncesOnlyOnTheFirstSnapOfTheState(self):
        g = drill()
        g.recordTempoIntent()
        self.assertTrue(g.play.enteringNoHuddle)
        for _ in range(4):
            g._newPlay() if hasattr(g, '_newPlay') else None
            g.recordTempoIntent()
            self.assertFalse(g.play.enteringNoHuddle,
                             'no-huddle re-announced inside the same state')

    def testANewOffenseAnnouncesItsOwn(self):
        """⚠️ The latch holds the TEAM, not a bool. A plain flag would survive a turnover
        and silently swallow the next offense's own first no-huddle snap.

        ⚠️ TIED, not trailing. A trailing offense that turns the ball over hands it to a
        LEADING one, which classifies as `burnClock` and is correctly never no-huddle — so
        that setup tests nothing. Tied under 2:00 is the state where BOTH teams hurry, and
        it is the only one where this latch can actually be wrong.
        """
        g = drill(offScore=21, defScore=21)
        g.recordTempoIntent()
        self.assertTrue(g.play.enteringNoHuddle)
        g.offensiveTeam, g.defensiveTeam = g.defensiveTeam, g.offensiveTeam
        g.recordTempoIntent()
        self.assertTrue(g.play.noHuddle, 'a tied offense late should also be hurrying')
        self.assertTrue(g.play.enteringNoHuddle,
                        'the new offense never got its own announcement')

    def testLeavingTheStateClearsTheLatch(self):
        g = drill()
        g.recordTempoIntent()
        self.assertTrue(g.play.enteringNoHuddle)
        g.clockRunning = False           # they huddle
        g.recordTempoIntent()
        self.assertFalse(g.play.noHuddle)
        g.clockRunning = True            # and go back to the line
        g.recordTempoIntent()
        self.assertTrue(g.play.enteringNoHuddle, 're-entering should announce again')


class TheFeedPrefix(unittest.TestCase):
    def testEnteringNoHuddlePrependsToThePlayText(self):
        g = drill()
        g.recordTempoIntent()
        out = g._prependPreSnapBeat('Hands off to Tuck Marlow for 6 yards.')
        self.assertIn('no-huddle', out.lower())
        self.assertTrue(out.endswith('Hands off to Tuck Marlow for 6 yards.'))

    def testASnapInsideTheStateGetsNoPrefix(self):
        g = drill()
        g.recordTempoIntent()
        g.recordTempoIntent()          # second snap, same state
        self.assertEqual(g._prependPreSnapBeat('Run for 3.'), 'Run for 3.')

    def testAnAudibleOutranksTheTempoLine(self):
        """⚠️ At most one pre-snap line per snap, taking the most significant. They can
        collide only on the first no-huddle snap, but the rule has to exist."""
        g = drill()
        g.recordTempoIntent()
        g.play.audibleText = 'Vance calls an audible!'
        out = g._prependPreSnapBeat('Run for 3.')
        self.assertTrue(out.startswith('Vance calls an audible!'))
        self.assertNotIn('no-huddle', out.lower())

    def testEmptyTextIsLeftAlone(self):
        g = drill()
        g.recordTempoIntent()
        self.assertEqual(g._prependPreSnapBeat(''), '')


class TheMenuShrinks(unittest.TestCase):
    """⚠️ THE RESTRICTION IS THE BALANCE, NOT A LIMITATION TO ENGINEER AROUND. No-huddle
    buys ~6 seconds a snap; if it cost nothing every trailing offense would always do it
    and the two-minute drill would be solved. The extra snaps have to be WORSE snaps.

    Measured over 600 weight sets, trailing in Q4 with the clock live:

        run     19.4%  ->   0.0%
        short   28.3%  ->  48.7%
        medium  29.8%  ->  51.3%
        long    17.4%  ->   0.0%
        deep     5.1%  ->   0.0%
        sideline   40%  ->   100%
    """

    def _weights(self, enabled):
        original = constants.NO_HUDDLE_ENABLED
        try:
            constants.NO_HUDDLE_ENABLED = enabled
            g = drill(clock=100)
            g.recordTempoIntent()
            coach = getattr(g.offensiveTeam, 'coach', None)
            return g._computePlayWeights(g.homeScore - g.awayScore, coach), g, coach
        finally:
            constants.NO_HUDDLE_ENABLED = original

    def testDepthIsGone(self):
        w, _g, _c = self._weights(True)
        self.assertEqual(w.get('long', 0), 0, 'long needs a protection call')
        self.assertEqual(w.get('deep', 0), 0, 'deep needs a route stem')

    def testTheRunGameIsGone(self):
        w, _g, _c = self._weights(True)
        self.assertEqual(w.get('run', 0), 0)

    def testShortAndMediumSurvive(self):
        w, _g, _c = self._weights(True)
        self.assertGreater(w.get('short', 0) + w.get('medium', 0), 0,
                           'the restriction emptied the menu')

    def testAHuddlingOffenseKeepsTheWholePlaybook(self):
        w, _g, _c = self._weights(False)
        for key in ('run', 'short', 'medium', 'long', 'deep'):
            self.assertGreater(w.get(key, 0), 0, f'{key} vanished with the flag off')

    def testSidelineIsSetNotRolled(self):
        """⚠️ Getting out of bounds is the POINT of the play, not a probability. Left as a
        roll the drill sometimes forgets why it is hurrying — and step 3's predictability
        penalty depends on the sideline route being reliable, not occasional."""
        _w, g, coach = self._weights(True)
        for _ in range(40):
            self.assertTrue(g._shouldTargetSideline(g.homeScore - g.awayScore, coach))

    def testTheRestrictionIsAppliedLast(self):
        """⚠️ Placement is the point. The situational, matchup, coach, gameplan and
        drive-clock layers all reach for long/deep when an offense is behind and hurrying —
        which is exactly when no-huddle fires. Restricting earlier lets them put it back."""
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               'floosball_game.py')) as fh:
            src = fh.read()
        start = src.index('def _computePlayWeights')
        body = src[start:src.index('\n    def _applyNoHuddleMenu', start)]
        self.assertIn('return self._applyNoHuddleMenu(weights)', body,
                      'the menu restriction is no longer the final pass')

    def testTheSneakLookDeclines(self):
        """A fake is a huddle call — it sells one thing and does another, which needs the
        whole offense briefed."""
        _w, g, _c = self._weights(True)
        self.assertIsNone(g._selectSneakLook())

    def testTheMenuDoesNotReachIntoTheSneak(self):
        """The sneak is injected by `_selectRunConcept` on its own trigger and is never
        carried in these weights, so zeroing `run` neither keeps nor removes it. The menu
        must not try."""
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               'floosball_game.py')) as fh:
            src = fh.read()
        start = src.index('def _applyNoHuddleMenu')
        body = src[start:src.index('\n    def ', start + 10)]
        self.assertNotIn('sneak', body.split('"""')[-1],
                         'the menu must not reach into the sneak at all')

    def testTheSneakIsAlreadyOffInADrill(self):
        """⚠️ THE PLAN CLAIMED THE SNEAK STAYS AVAILABLE IN NO-HUDDLE. It does not, and
        should not: `_isSneakSituation()` has bailed on `_isHurryUp()` since the sneak
        shipped, because a sneak burns clock and stays in bounds — the opposite of what a
        two-minute drill wants. That reason is better than the plan's ("it needs no
        call"), and this pins the real behavior against the doc."""
        g = drill(clock=95)
        g.down, g.yardsToFirstDown, g.yardsToEndzone = 3, 1, 40
        self.assertTrue(g._isNoHuddle())
        self.assertFalse(g._isSneakSituation(),
                         'a sneak in a two-minute drill wastes the clock it is racing')


class TheTriggerIsTheDrillNotJustADeficit(unittest.TestCase):
    """⚠️ `hurryUp` COVERS TWO DIFFERENT THINGS. Seven of the classifier's eight hurry-up
    branches return a base of 12 — the genuine two-minute drill. The eighth is "mid-late
    deficit" and returns 15 or 25, which is a SHORTER HUDDLE, not the absence of one: down
    17 in Q3 with 5:00 left an offense pushes tempo and still huddles, because it has time
    to call a play.

    Reading the intent alone put the offense at the line for a third of a game, and would
    have charged the menu restriction in situations where a huddle was available.
    """

    def testAMidLateDeficitIsNotNoHuddle(self):
        g = drill(clock=240, offScore=7, defScore=21, quarter=4)
        intent, base = g._classifyTempoIntent()
        self.assertEqual(intent, 'hurryUp')
        self.assertGreater(base, constants.LAST_SNAP_HUDDLE_SECS,
                           'this case is meant to be a slower hurry-up')
        self.assertFalse(g._isNoHuddle(), 'a 25-second huddle is still a huddle')

    def testTheRealDrillStillQualifies(self):
        g = drill(clock=95)
        intent, base = g._classifyTempoIntent()
        self.assertEqual((intent, base), ('hurryUp', constants.LAST_SNAP_HUDDLE_SECS))
        self.assertTrue(g._isNoHuddle())


class TheTightEndIsTheSecurityBlanket(unittest.TestCase):
    """The tight end should be the reliable short-medium target in a drill.

    ⚠️ THE MENU RESTRICTION DID NOT DELIVER THIS ON ITS OWN, which is worth recording
    because it looked like it would: the TE appears in 5 of 8 short plays and 9 of 14
    medium ones and in ZERO long or deep plays, so cutting the deep game should have
    raised his share. Measured, it moved TE involvement only 67.2% -> 64.8% of called
    plays — because most plays already list all three receivers, so which receiver a play
    NAMES was never the lever. Who the quarterback LOOKS AT is.

    From an equal-openness three-man read, the nudge takes the TE from 32.8% to 63.4%.

    ⚠️ AND IT MUST LOSE TO REAL SEPARATION, or it is a compulsion rather than a tendency:

        WR open 85 vs TE 45  ->  TE chosen   0.0%
        WR      75 vs    50  ->             12.8%
        WR      65 vs    55  ->             47.8%
        WR      55 vs    55  ->             76.2%
        WR      45 vs    60  ->             97.3%
    """

    def _read(self, wrOpen, teOpen, n=800):
        g = drill(clock=100)
        g.recordTempoIntent()
        self.assertTrue(g._isNoHuddle())
        rd = g.offensiveTeam.rosterDict
        qb, te = rd['qb'], rd['te']
        chosen = 0
        for _ in range(n):
            targets = [
                {'receiver': rd['wr1'], 'openness': wrOpen, 'route': 'go',
                 'coveringDefender': None, 'routeQuality': 70},
                {'receiver': te, 'openness': teOpen, 'route': 'seam',
                 'coveringDefender': None, 'routeQuality': 70},
            ]
            sel, _threw = g.play.selectPassTarget(
                targets, qb.attributes.vision, qb.attributes.discipline)
            if sel and sel['receiver'] is te:
                chosen += 1
        return chosen / n

    def testTheQbLooksAtTheTightEndOnAnEvenRead(self):
        self.assertGreater(self._read(55, 55), 0.55,
                           'the tight end should win a coin-flip read in a drill')

    def testAWideOpenReceiverStillWins(self):
        """⚠️ The guardrail. A nudge that beats real separation is not a tendency."""
        self.assertLess(self._read(85, 45), 0.10,
                        'the nudge overrode a genuinely open receiver')

    def testItOnlyAppliesInNoHuddle(self):
        """Outside a drill the TE's share should come from the playbook and the matchup,
        where it already does."""
        g = drill(clock=800, offScore=21, defScore=21, quarter=1)
        g.recordTempoIntent()
        self.assertFalse(g._isNoHuddle())
        rd = g.offensiveTeam.rosterDict
        qb, te = rd['qb'], rd['te']
        chosen = 0
        for _ in range(800):
            targets = [
                {'receiver': rd['wr1'], 'openness': 55, 'route': 'go',
                 'coveringDefender': None, 'routeQuality': 70},
                {'receiver': te, 'openness': 55, 'route': 'seam',
                 'coveringDefender': None, 'routeQuality': 70},
            ]
            sel, _t = g.play.selectPassTarget(
                targets, qb.attributes.vision, qb.attributes.discipline)
            if sel and sel['receiver'] is te:
                chosen += 1
        self.assertLess(chosen / 800, 0.60, 'the drill bonus leaked outside a drill')

    def testItIsSmallerThanTheAwakenedNudge(self):
        """It shares that mechanism deliberately, and must stay the quieter of the two —
        a powered-up receiver should still out-draw a tendency."""
        from constants import AWAKENED_RECEIVER_OPENNESS_BONUS
        self.assertLess(constants.NO_HUDDLE_TE_OPENNESS_BONUS,
                        AWAKENED_RECEIVER_OPENNESS_BONUS)

    def testItMovesPerceptionNotSafety(self):
        """⚠️ It nudges PERCEIVED openness only, so it never makes the throw safer than it
        is — a covered tight end stays covered and the ball can still be broken up. That
        matters because this fires in exactly the situation the defense starts reading."""
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               'floosball_game.py')) as fh:
            src = fh.read()
        start = src.index('NO_HUDDLE_TE_OPENNESS_BONUS')
        window = src[start:start + 600]
        self.assertIn('perceivedOpenness', window,
                      'the TE bonus must apply to perceived openness, not actual')


class ThePredictabilityPenalty(unittest.TestCase):
    """⚠️ THE BALANCE GATE. No-huddle buys ~6 seconds a snap and +58% snaps in a drill; it
    has to pay for that by being readable. The offense at the line can only throw short or
    medium at the sideline, and a defense that knows this reads it — so the telegraph is a
    NEGATIVE disguise, the same quantity a fake subtracts, pointed the other way.

    Measured paired (one set of rosters, arms differing only by the flag), n=8000:

        arm                        ypp   +/-se   20+ rate
        huddled hurry-up          6.69    0.08      6.5%
        no-huddle, no telegraph   6.26    0.08      4.9%
        no-huddle + telegraph     5.87    0.07      4.4%

    Menu restriction alone -0.43 ypp; the telegraph adds another -0.39. Total -0.82 ypp
    (-12%) and explosive plays down 32%. Read accuracy 52% -> 79%.

    ⚠️ THE FIRST THREE MEASUREMENTS OF THIS WERE NOISE. `Scenario()` generates teams, so
    arms that each built their own were comparing ROSTERS, not tempos — run-to-run spread
    was 0.6-0.9 ypp against an effect of 0.4. The same trap the runner-move measurement
    recorded. Pair the arms on one Scenario and take n>=8000.
    """

    def testTheTelegraphRaisesTheDefensiveRead(self):
        g = drill(clock=100)
        g.recordTempoIntent()
        self.assertTrue(g.play.noHuddle)
        scheme = {'passDefMult': 1.0}
        hits = 0
        for _ in range(2000):
            sc = dict(scheme)
            g.play.noHuddle = True
            g.play._applyPreSnapRead(sc, isRun=False)
            hits += bool(g.play.preSnapRead['correct'])
        self.assertGreater(hits / 2000, 0.65,
                           'a telegraphed drill should be read far more often than a coin flip')

    def testAHuddlingOffenseIsNotTelegraphed(self):
        g = drill(clock=100)
        g.recordTempoIntent()
        scheme = {'passDefMult': 1.0}
        hits = 0
        for _ in range(2000):
            sc = dict(scheme)
            g.play.noHuddle = False
            g.play._applyPreSnapRead(sc, isRun=False)
            hits += bool(g.play.preSnapRead['correct'])
        self.assertLess(hits / 2000, 0.62,
                        'the telegraph leaked onto a huddling offense')

    def testItIsSizedAlongsideTheFakesItMirrors(self):
        from constants import PRESNAP_DISGUISE, NO_HUDDLE_TELEGRAPH
        self.assertGreaterEqual(NO_HUDDLE_TELEGRAPH, min(PRESNAP_DISGUISE.values()))
        self.assertLessEqual(NO_HUDDLE_TELEGRAPH, max(PRESNAP_DISGUISE.values()))


class TheCapturedFlagIsWhatGetsRead(unittest.TestCase):
    """⚠️ THE TRAP I DOCUMENTED IN STEP 1 AND THEN WALKED INTO TWICE.

    `_isNoHuddle()` depends on `clockRunning`, and the play resolution MOVES it — measured,
    it was already False on five snaps in six by the time the pre-snap read ran. So a live
    call silently dropped the telegraph on most plays (read accuracy 56% against the 78% it
    should have been) and would have dropped the tight-end nudge the same way. Both were
    written live and both were wrong.

    `recordTempoIntent` stamps `play.noHuddle` in the pre-snap block, before anything
    moves. Everything downstream must read that.
    """

    def testTheReadUsesTheCapturedFlag(self):
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               'floosball_game.py')) as fh:
            src = fh.read()
        start = src.index('def _applyPreSnapRead')
        body = src[start:src.index('\n    def ', start + 10)]
        self.assertIn("getattr(self, 'noHuddle'", body,
                      'the pre-snap read is deriving no-huddle live again')

    def testTheTightEndNudgeUsesTheCapturedFlag(self):
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               'floosball_game.py')) as fh:
            src = fh.read()
        start = src.index('NO_HUDDLE_TE_OPENNESS_BONUS')
        window = src[max(0, start - 900):start]
        self.assertIn("self.noHuddle", window,
                      'the tight-end nudge is deriving no-huddle live again')

    def testAStampedFalseBeatsALiveTrue(self):
        """The capture must WIN over the live state, not merely default to it."""
        g = drill(clock=100)
        g.recordTempoIntent()
        self.assertTrue(g._isNoHuddle())        # live says yes
        g.play.noHuddle = False                 # but the snap was stamped huddling
        scheme = {'passDefMult': 1.0}
        hits = 0
        for _ in range(1500):
            sc = dict(scheme)
            g.play._applyPreSnapRead(sc, isRun=False)
            hits += bool(g.play.preSnapRead['correct'])
        self.assertLess(hits / 1500, 0.62, 'the live state overrode the captured one')


class TheAudible(unittest.TestCase):
    """The offensive mirror of `_applyPreSnapRead` — the QB looks at the box and changes
    the call, or does not.

    Measured over 4,000 snaps per profile, paired on one roster set:

        QB profile                   checks   good    bad   stood pat
        sharp + disciplined (95/95)     14%     9%     5%       35%
        sharp + gunslinger  (95/62)     39%    26%    13%        9%
        blind + disciplined (64/95)     14%     7%     7%       36%
        blind + gunslinger  (64/62)     39%    19%    21%       10%

    Discipline drives the RATE (14% against 39%); instinct drives the SPLIT (2:1 good/bad
    when sharp, 1:1 when blind). The trap cell is 4x bigger for a blind gunslinger than a
    sharp disciplined QB, which is the whole design.

    ⚠️ AND A GOOD CHECK IS WORTH REAL YARDS, but only measurably in one direction. Holding
    the resulting play type fixed, over 40,000 snaps with the box driven:

        checked to RUN    good 6.88   bad 6.07   diff +0.81 +/- 0.20
        checked to PASS   good 6.22   bad 6.11   diff +0.11 +/- 0.15

    Reading a light box and running is worth most of a yard; checking into the quick game
    against a stacked box is near-neutral. Recorded rather than tuned — the plan is
    explicit that a miscalibrated audible and a miscalibrated disguise mask each other, so
    this waits for step 5.

    ⚠️ YARDS PER PLAY ALONE CANNOT MEASURE THIS. A good check into a light box produces a
    RUN, and runs average well under a pass, so a CORRECT read lowers raw ypp while being
    the right call. The first measurement said a blind QB outperformed a sharp one for
    exactly that reason.
    """

    def _game(self, instinct=80, discipline=80, runStopFocus=0.30, quarter=2, clock=600):
        s = Scenario()
        s.situation(quarter=quarter, clock=clock, offense='home', offScore=14, defScore=14,
                    down=1, distance=10, ballOn=55, offTimeouts=3, defTimeouts=3)
        g = s.game
        g.clockRunning = True
        qb = g.homeTeam.rosterDict['qb']
        for holder in (qb.attributes, getattr(qb, 'gameAttributes', None)):
            if holder is not None:
                holder.instinct = instinct
                holder.discipline = discipline
        gp = g.awayDefGameplan if g.offensiveTeam is g.homeTeam else g.homeDefGameplan
        if gp is not None:
            gp.runStopFocus = runStopFocus
        return s, g

    def _rates(self, n=1500, **kw):
        s, g = self._game(**kw)
        out = {'checked': 0, 'good': 0, 'bad': 0, 'total': 0}
        for _ in range(n):
            s.situation(quarter=2, clock=600, offense='home', offScore=14, defScore=14,
                        down=1, distance=10, ballOn=55, offTimeouts=3, defTimeouts=3)
            g.clockRunning = True
            gpx = g.awayDefGameplan if g.offensiveTeam is g.homeTeam else g.homeDefGameplan
            if gpx is not None:
                gpx.runStopFocus = kw.get('runStopFocus', 0.30)
            s._newPlay()
            g.recordTempoIntent()
            try:
                g.playCaller()
            except Exception:
                continue
            a = g.play.insights.get('audible')
            if not a:
                continue
            out['total'] += 1
            if a.get('checked'):
                out['checked'] += 1
                out['good' if a['readRight'] else 'bad'] += 1
        return out

    def testDisciplineDrivesHowOftenHeChecks(self):
        """⚠️ Willingness is `_undiscipline`, NOT `flairOf` — settled against 34 QBs,
        where flairOf correlates +0.77 with instinct and collapses the grid."""
        gun = self._rates(discipline=62)
        pro = self._rates(discipline=95)
        self.assertGreater(gun['checked'] / max(1, gun['total']),
                           2 * pro['checked'] / max(1, pro['total']),
                           'a gunslinger should check far more often than a pro')

    def testInstinctDrivesWhetherTheCheckIsRight(self):
        sharp = self._rates(instinct=95, discipline=62)
        blind = self._rates(instinct=64, discipline=62)
        sharpRatio = sharp['good'] / max(1, sharp['bad'])
        blindRatio = blind['good'] / max(1, blind['bad'])
        self.assertGreater(sharpRatio, blindRatio,
                           'reading ability made no difference to check quality')

    def testTheTrapCellIsRealForABoldBlindQb(self):
        """⚠️ AN AUDIBLE MUST BE ABLE TO LOSE. A QB who never audibles is safer than one
        who audibles badly — that is what makes this a skill rather than a bonus."""
        blind = self._rates(instinct=64, discipline=62)
        self.assertGreater(blind['bad'] / max(1, blind['total']), 0.10,
                           'the bad check barely happens, so nothing is at risk')

    def testTheFlagTurnsItOff(self):
        original = constants.AUDIBLE_ENABLED
        try:
            constants.AUDIBLE_ENABLED = False
            out = self._rates(discipline=62)
            self.assertEqual(out['checked'], 0)
        finally:
            constants.AUDIBLE_ENABLED = original

    def testNoHuddleForbidsCheckingIntoARun(self):
        """⚠️ The tempo closed the run game; an audible must not reopen it."""
        s, g = self._game(discipline=62, runStopFocus=0.30, quarter=4, clock=95)
        g.homeScore, g.awayScore = 14, 21
        checkedToRun = 0
        for _ in range(600):
            s.situation(quarter=4, clock=95, offense='home', offScore=14, defScore=21,
                        down=1, distance=10, ballOn=55, offTimeouts=1, defTimeouts=3)
            g.clockRunning = True
            gpx = g.awayDefGameplan if g.offensiveTeam is g.homeTeam else g.homeDefGameplan
            if gpx is not None:
                gpx.runStopFocus = 0.30
            s._newPlay()
            g.recordTempoIntent()
            if not g.play.noHuddle:
                continue
            try:
                g.playCaller()
            except Exception:
                continue
            a = g.play.insights.get('audible') or {}
            if a.get('checked') and a.get('to') == 'run':
                checkedToRun += 1
        self.assertEqual(checkedToRun, 0, 'an audible reopened the run game in no-huddle')

    def testACheckNamesTheQuarterbackInTheFeed(self):
        s, g = self._game(discipline=62)
        for _ in range(400):
            s.situation(quarter=2, clock=600, offense='home', offScore=14, defScore=14,
                        down=1, distance=10, ballOn=55, offTimeouts=3, defTimeouts=3)
            g.clockRunning = True
            s._newPlay()
            g.recordTempoIntent()
            try:
                g.playCaller()
            except Exception:
                continue
            a = g.play.insights.get('audible') or {}
            if a.get('checked'):
                self.assertTrue(getattr(g.play, 'audibleText', None))
                out = g._prependPreSnapBeat('Run for 4 yards.')
                self.assertIn('audible', out.lower())
                self.assertIn(g.offensiveTeam.rosterDict['qb'].name, out)
                return
        self.skipTest('no check occurred in 400 snaps')

    def testUndisciplineIsCalledOnThePlayNotTheGame(self):
        """⚠️ `_undiscipline` lives on Play. Calling it on Game raised on every snap and
        made the whole layer silently absent — the same class-boundary slip that made
        `calculateSackProbability` look missing earlier this session."""
        import floosball_game as _fg
        self.assertTrue(hasattr(_fg.Play, '_undiscipline'))
        self.assertFalse(hasattr(_fg.Game, '_undiscipline'))
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               'floosball_game.py')) as fh:
            src = fh.read()
        start = src.index('def _maybeAudible')
        body = src[start:src.index('\n    def ', start + 10)]
        self.assertIn('self.play._undiscipline(', body)


class TheDefensiveDisguise(unittest.TestCase):
    """What the defense SHOWS, split from what it DOES.

    ⚠️ A DISGUISE DEGRADES RECOGNITION OF THE TRUTH — it does not redefine what "right"
    means. The first build had the QB read the SHOWN box and called a correct reading of
    it `readRight`, which inverted every label: a quarterback who "read right" had in fact
    been FOOLED. Measured, it reported fooled QBs beating sharp ones by 1.24 yards a carry
    against a held disguise, which is what exposed it. The box question is always about
    what the defense is ACTUALLY doing; the lie only makes it harder to see, exactly as
    `PRESNAP_DISGUISE` works for the defense's own read.

    After the fix, checks against a held disguise, resulting call held fixed:

        checked to RUN    saw through 7.03   fooled 6.82   +0.21 +/- 0.52
        checked to PASS   saw through 5.86   fooled 5.55   +0.32 +/- 0.32

    Both directions now correct, neither yet significant — see the asymmetry note in the
    commit; it is bounded by `runStopFocus` not opening the pass game.
    """

    def _game(self, runStopFocus=0.72):
        s = Scenario()
        s.situation(quarter=2, clock=600, offense='home', offScore=14, defScore=14,
                    down=1, distance=10, ballOn=55, offTimeouts=3, defTimeouts=3)
        g = s.game
        g.clockRunning = True
        gp = g.awayDefGameplan if g.offensiveTeam is g.homeTeam else g.homeDefGameplan
        if gp is not None:
            gp.runStopFocus = runStopFocus
        return s, g, gp

    def testTheReadIsAgainstTheActualBoxNotTheShownOne(self):
        """⚠️ The inversion regression. `boxStacked` must come from the real defense."""
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               'floosball_game.py')) as fh:
            src = fh.read()
        start = src.index('def _maybeAudible')
        body = src[start:src.index('\n    def ', start + 10)]
        self.assertIn('boxStacked = actualRunFocus >=', body,
                      'the audible is reading the shown box as if it were the truth again')

    def testAHeldDisguiseMakesTheTruthHarderToSee(self):
        s, g, _gp = self._game()
        self.assertGreater(g.DISGUISE_READ_PENALTY, 0)

    def testADisguiseCostsTheDefenseSomething(self):
        """⚠️ Or every defense disguises every play."""
        from constants import DISGUISE_ALIGNMENT_COST, DISGUISE_TIPPED_EXTRA_COST
        self.assertGreater(DISGUISE_ALIGNMENT_COST, 0)
        self.assertGreater(DISGUISE_TIPPED_EXTRA_COST, 0)
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               'floosball_game.py')) as fh:
            src = fh.read()
        start = src.index('def _applyPreSnapRead')
        body = src[start:src.index('\n    def ', start + 10)]
        self.assertIn("getattr(self, 'disguiseCost'", body,
                      'the alignment cost is no longer charged')

    def testATippedDisguisePaysMoreAndHidesNothing(self):
        """A blown look is WORSE than never lying: the QB gets a free read and the defense
        is still out of position. That is what makes `discipline` worth having."""
        from constants import DISGUISE_ALIGNMENT_COST, DISGUISE_TIPPED_EXTRA_COST
        self.assertGreater(DISGUISE_ALIGNMENT_COST + DISGUISE_TIPPED_EXTRA_COST,
                           DISGUISE_ALIGNMENT_COST)
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               'floosball_game.py')) as fh:
            src = fh.read()
        start = src.index('def _maybeAudible')
        body = src[start:src.index('\n    def ', start + 10)]
        self.assertIn('if disguised and not tipped:', body,
                      'a tipped disguise must not still be hiding the truth')

    def testTheFlagTurnsItOff(self):
        original = constants.DEFENSIVE_DISGUISE_ENABLED
        try:
            constants.DEFENSIVE_DISGUISE_ENABLED = False
            s, g, _gp = self._game()
            for _ in range(200):
                shown, disguised, tipped = g._resolveDisguise(0.72)
                self.assertFalse(disguised)
                self.assertEqual(shown, 0.72)
        finally:
            constants.DEFENSIVE_DISGUISE_ENABLED = original

    def testASharpStaffDisguisesMoreOften(self):
        s, g, _gp = self._game()
        rates = {}
        for mind in (62, 98):
            g.defensiveTeam.coach.defensiveMind = mind
            hits = sum(1 for _ in range(3000) if g._resolveDisguise(0.72)[1])
            rates[mind] = hits / 3000
        self.assertGreater(rates[98], rates[62] * 1.5,
                           'defensiveMind does not drive whether the defense lies')

    def testTheShownLookIsTheOtherSideOfTheBox(self):
        from constants import AUDIBLE_BOX_STACKED
        s, g, _gp = self._game()
        g.defensiveTeam.coach.defensiveMind = 100
        for actual, wantStacked in ((0.72, False), (0.30, True)):
            for _ in range(400):
                shown, disguised, tipped = g._resolveDisguise(actual)
                if disguised and not tipped:
                    self.assertEqual(shown >= AUDIBLE_BOX_STACKED, wantStacked,
                                     'a disguise showed the same thing it was doing')
                    break


class TheDocumentedTraps(unittest.TestCase):
    def testClassifyTempoIntentStillReturnsATwoTuple(self):
        """⚠️ Three sites unpack this, including `_lastSnapBeforeBreak`'s chess-clock
        branch. No-huddle is a different AXIS from huddle length, which is why it is a
        derived helper rather than a fourth intent."""
        g = drill()
        result = g._classifyTempoIntent()
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 2)

    def testTheTimeoutHelperChecksNoHuddleFirst(self):
        """⚠️ Standing at the line is the cheaper way to save a snap, and it is free.
        Without this the offense burns timeouts doing what the tempo already did — on the
        same drive that will want them to stop the clock after a completion inbounds."""
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               'floosball_game.py')) as fh:
            src = fh.read()
        start = src.index('def _maybeCallTimeoutToSaveSnap')
        body = src[start:src.index('\n    def ', start + 10)]
        self.assertIn('_isNoHuddle()', body)
        # ...and it must not short-circuit the chess clock, where a timeout preserves the
        # possession BUDGET, which no amount of tempo can do.
        self.assertIn('chess_clock', body)


if __name__ == '__main__':
    unittest.main(verbosity=2)
