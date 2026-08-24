"""Darts: what a team does when only a sideline hoop can score, and when nothing can.

Three states the format creates and the engine had no answer for (owner, 2026-08-17).

⚠️ ONE: THE OFFENSE DID NOT KNOW IT SHOULD BE SHOOTING. `_hoopPointsNeeded` reasons in
standard-football terms -- can a field goal or touchdown PLUS a hoop reach a tie or a lead
-- and returns None outright when the team is winning. In darts the opponent is irrelevant
to that decision: what matters is the distance to the TARGET, and a team leading 17-3 at
X=18 needs a hoop more urgently than anybody. Measured over 30 games before the fix: 531
snaps where a hoop was the only score that would not bust, taken 9% of the time. The
standard-football logic was declining the format's own win condition.

⚠️ TWO: A MISS IS AN INCOMPLETION, NOT A TURNOVER. `game_rules.py` documented the opposite
("a turnover at the current line of scrimmage") and the implementation has always said
otherwise. Nothing downstream changes possession. The doc was stale; the behaviour is the
one pinned here.

⚠️ THREE: A DRIVE CAN DIE. There are exactly two hoop pairs per drive, one shot each, and
they lock once used -- so a team needing 1 or 2 with both spent cannot score at all for the
rest of the possession. It plays on and grinds into a turnover on downs.

The settled answers: hoop hunting is COACH-SCALED, and a dead drive PUNTS -- burning clock
first if it is ahead on points, since the hoop pairs reset on the next possession and the
clock is the only thing a dead drive is still worth.

Run: .venv/bin/python test_darts_hoops.py
"""
import unittest

from constants import DARTS_HOOP_HUNT_BASE, DARTS_HOOP_HUNT_AGGR_SPAN
from game_rules import GameRules
from scenario import Scenario, PlayType

X = 18


# The real pair names, in the order a drive meets them. ALL_PAIRS_SPENT is the only
# fixture that strands a drive from anywhere on the field — with the end-zone pair unused
# the offense simply advances into it, whatever else it has spent.
HOOP_PAIRS = ('midfield', 'midrange', 'endzone')
ALL_PAIRS_SPENT = HOOP_PAIRS


def dartsGame(*, offScore, defScore=4, ballOn=35, down=1, distance=10,
              hoopsUsed=(), aggressiveness=80):
    """A darts game with the offense on `offScore`, i.e. needing X - offScore."""
    rules = GameRules()
    rules.gameFormat = 'bust'
    rules.targetScore = X
    scenario = Scenario(gameRules=rules)
    game = scenario.game
    scenario.situation(quarter=2, clock=600, offense='home',
                       offScore=offScore, defScore=defScore,
                       down=down, distance=distance, ballOn=ballOn,
                       offTimeouts=3, defTimeouts=3, clockRunning=True)
    # ⚠️ VALIDATED, because a typo here is INVISIBLE. `_dartsDriveIsDead` used to count
    # `len(_hoopPairResult) >= 2`, so a phantom key was as good as a real one — every
    # dead-drive fixture below said `'redzone'` (the pair is `'endzone'`) and the whole
    # class passed with the end-zone pair still live. The check now asks which pairs are
    # REACHABLE, which is what surfaced it.
    unknown = set(hoopsUsed) - set(HOOP_PAIRS)
    assert not unknown, f'no such hoop pair: {sorted(unknown)} (pairs are {HOOP_PAIRS})'
    game._hoopPairResult = {pair: 'missed' for pair in hoopsUsed}
    coach = getattr(game.homeTeam, 'coach', None)
    if coach is not None:
        coach.aggressiveness = aggressiveness
    return scenario


def need(game):
    return game.format.bustNeed(game, game.offensiveTeam)


class TheOffenseKnowsAHoopIsTheOnlyWay(unittest.TestCase):

    def test_theFixtureIsWhatItClaims(self):
        game = dartsGame(offScore=X - 1).game
        self.assertEqual(game.format.key, 'bust')
        self.assertEqual(need(game), 1)
        self.assertTrue(game.gameRules.sidelineGoalsEnabled, 'the format bundles hoops')

    def test_belowAFieldGoalTheHoopIsCritical(self):
        for remaining in (1, 2):
            game = dartsGame(offScore=X - remaining).game
            self.assertEqual(game._hoopPointsNeeded(0), 'critical',
                             f'needing {remaining}, only a hoop scores')

    def test_leadingDoesNotSwitchItOff(self):
        """THE BUG. The old logic bailed at `scoreDiff > 0` — a winning team has nothing
        to chase — which in darts is exactly backwards."""
        game = dartsGame(offScore=X - 1, defScore=2).game
        self.assertGreater(game.homeScore, game.awayScore, 'fixture should be leading')
        self.assertEqual(game._hoopPointsNeeded(game.homeScore - game.awayScore), 'critical')

    def test_aConventionalScoreThatLandsExactlyNeedsNoHoop(self):
        """Needing exactly a field goal, spending downs on hoops is wasteful."""
        game = dartsGame(offScore=X - 3).game
        self.assertEqual(need(game), 3)
        self.assertIsNone(game._hoopPointsNeeded(0))

    def test_hoopsBridgeToAnExactLanding(self):
        """Needing 4: a field goal alone leaves 1, but hoop + field goal lands it."""
        game = dartsGame(offScore=X - 4).game
        self.assertEqual(game._hoopPointsNeeded(0), 'helpful')

    def test_aTargetAlreadyReachedAsksForNothing(self):
        game = dartsGame(offScore=X).game
        self.assertIsNone(game._hoopPointsNeeded(0))

    def test_everyPairSpentMeansNoHoopToWant(self):
        """⚠️ Spends EVERY pair, read from the engine rather than a literal — the count
        changed from two to three when the midrange pair was added, and a hardcoded pair
        list here would have gone on passing while testing nothing."""
        game = dartsGame(offScore=X - 1).game
        allPairs = ('midfield', 'endzone', 'midrange')[:game._hoopPairCount()]
        game._hoopPairResult = {pair: 'missed' for pair in allPairs}
        self.assertIsNone(game._hoopPointsNeeded(0))

    def test_standardFootballIsUntouched(self):
        """⚠️ The darts branch sits above the existing logic, so the deficit reasoning
        every other format uses has to be unchanged."""
        scenario = Scenario()
        scenario.situation(quarter=4, clock=90, offense='home', offScore=14, defScore=17,
                           down=1, distance=10, ballOn=40, offTimeouts=1, defTimeouts=1)
        game = scenario.game
        game.gameRules.sidelineGoalsEnabled = True
        game._hoopPairResult = {}
        self.assertIsNone(game._hoopPointsNeeded(5), 'a leading team still wants nothing')


class TheFinalDownGetsTheHoopDecisionToo(unittest.TestCase):
    """⚠️ THE RULE WAS WRITTEN, DOCUMENTED, AND UNREACHABLE (owner report, 2026-08-24).

    `_shouldAttemptHoopShot`'s darts branch says the final-down guard INVERTS: a hoop
    normally forfeits the real scoring play, but under a target with the need below a field
    goal there is no real scoring play to forfeit — a touchdown is held up short and a kick
    busts. Correct, and it never ran. The check is consulted from exactly ONE place, inside
    `_executeWeightedPlay`, and `playCaller` routes the final down to `_fourthDownCaller`,
    which sets Punt/FieldGoal directly or calls runPlay/passPlay. The inversion sat behind a
    door the final down never opens.

    Measured over 400 games: 26 final-down snaps where only a hoop could score and one was
    in range. It shot 1 — the rest punted (12), ran (6), passed (5) or knelt (2). After: 8
    of 13 (the total falls because a taken shot resolves the state instead of leaving the
    offense sitting in it).

    ⚠️ The end-zone pair partly escaped this BY ACCIDENT, which is why a sweep showed it
    shooting on fourth down while midfield did not: in the red zone the kick is in range, so
    the caller picks a FieldGoal, it busts, `_refuseBustingKick` refuses it, and its
    "play on" branch re-enters `_executeWeightedPlay` through the back door.
    """

    def _finalDown(self, need=1, ballOn=55, hoopsUsed=()):
        from floosball_game import Play
        scenario = dartsGame(offScore=X - need, defScore=max(0, X - need - 3),
                             ballOn=ballOn, distance=8, hoopsUsed=hoopsUsed)
        g = scenario.game
        g.down = g.gameRules.downsPerSeries
        g.play = Play(g)
        return g

    def test_theFixtureIsTheStateTheRuleDescribes(self):
        g = self._finalDown()
        self.assertLess(g.format.bustNeed(g, g.homeTeam), g._fgValue(),
                        'a field goal would bust, so no conventional score is possible')
        self.assertIsNotNone(g._hoopTarget(), 'a pair really is in range')
        self.assertEqual(g.down, g.gameRules.downsPerSeries)

    def test_aPuntOnTheFinalDownBecomesTheShot(self):
        from floosball_game import PlayType
        g = self._finalDown()
        g.play.playType = PlayType.Punt
        self.assertTrue(g._dartsFinalDownHoop(), 'punted away the only scoring play')
        self.assertTrue(g.play.isHoopShot)

    def test_soDoARunOrAPass(self):
        from floosball_game import PlayType
        for kind in (PlayType.Run, PlayType.Pass):
            g = self._finalDown()
            g.play.playType = kind
            self.assertTrue(g._dartsFinalDownHoop(), f'ran a {kind.name} that cannot score')
            self.assertTrue(g.play.isHoopShot)

    def test_itDoesNotFireOnEarlierDowns(self):
        """⚠️ `_executeWeightedPlay` already asked on those, and asking twice would shoot a
        second hoop on a snap that has already resolved one."""
        from floosball_game import PlayType
        g = self._finalDown()
        g.down = 1
        g.play.playType = PlayType.Run
        self.assertFalse(g._dartsFinalDownHoop())

    def test_itLeavesAnAlreadyResolvedShotAlone(self):
        g = self._finalDown()
        g.play.isHoopShot = True
        self.assertFalse(g._dartsFinalDownHoop())

    def test_itLeavesAKneelAndASpikeAlone(self):
        from floosball_game import PlayType
        for kind in (PlayType.Kneel, PlayType.Spike):
            g = self._finalDown()
            g.play.playType = kind
            self.assertFalse(g._dartsFinalDownHoop(), f'overrode a {kind.name}')

    def test_withNoPairInRangeItDoesNothing(self):
        from floosball_game import PlayType
        # ⚠️ 25, not 35. The windows are end zone 1-18, midrange 30-50, midfield 50-64, so
        # the 35 is INSIDE the midrange pair — the third pair closed the gap the old
        # two-pair layout had (see `TheThirdPairFillsTheDeadZone`). 19-29 is a real gap.
        g = self._finalDown(ballOn=25)
        self.assertIsNone(g._hoopTarget())
        g.play.playType = PlayType.Punt
        self.assertFalse(g._dartsFinalDownHoop())
        self.assertIs(g.play.playType, PlayType.Punt)

    def test_whenAConventionalScoreIsAvailableItDefers(self):
        """Needing a field goal, the kick is the play — the hoop would spoil the landing."""
        from floosball_game import PlayType
        g = self._finalDown(need=int(dartsGame(offScore=0).game._fgValue()))
        g.play.playType = PlayType.FieldGoal
        self.assertFalse(g._dartsFinalDownHoop())
        self.assertIs(g.play.playType, PlayType.FieldGoal)

    def test_itIsANoOpInStandardFootball(self):
        from floosball_game import Play, PlayType
        scenario = Scenario()
        scenario.situation(quarter=2, clock=600, offense='home', offScore=17, defScore=14,
                           down=4, distance=8, ballOn=55, offTimeouts=3, defTimeouts=3)
        g = scenario.game
        g.play = Play(g)
        g.play.playType = PlayType.Punt
        self.assertFalse(g._dartsFinalDownHoop())
        self.assertIs(g.play.playType, PlayType.Punt)


class AHoopTheDriveCannotAffordToLoseIsShot(unittest.TestCase):
    """⚠️ Reported (owner, 2026-08-24): teams needing a single point drive straight past the
    midfield goal. They do — and most of the time that is FINE, which is why the rule is not
    "always shoot". A shot costs a down and no yards, and the end-zone pair is always still
    ahead, so a team needing 1 with everything unused has two more chances and is right to
    keep driving.

    It stops being fine when the hoops still REACHABLE after this one no longer add up to
    the need: driving on then forfeits the only path the drive has. Measured over 300 games,
    of 26 snaps where a team needing 2 or fewer drove past the midfield pair, **12 left it
    unable to cover its need**. That half is the mistake; the other 14 are football.

    ⚠️ CLOSING PAIRS ONLY. Passing up the END-ZONE pair does not lose it — it stays in range
    as the drive continues — so the cost there is a down, not the chance. Applied to it, this
    fired on every red-zone snap and flattened the coach dial the whole hunt is built on;
    `TheHuntIsCoachScaled` caught it, its fixture sitting at the 12.
    """

    def _rate(self, need, ballOn, hoopsUsed=(), rolls=400):
        game = dartsGame(offScore=X - need, ballOn=ballOn, hoopsUsed=hoopsUsed).game
        self.assertIsNotNone(game._hoopTarget(), 'fixture has no pair in range')
        return sum(game._shouldAttemptHoopShot() for _ in range(rolls)) / rolls

    def test_theCoverCountsOnlyWhatIsStillReachable(self):
        from constants import SIDELINE_GOAL_MIDRANGE_YARD as MR
        # At the midfield pair, the midrange pair is still ahead and the end-zone pair always is.
        far = dartsGame(offScore=X - 1, ballOn=60).game
        self.assertEqual(far._dartsHoopCoverAfterDeclining('midfield'), 2.0)
        # Past the midrange pair, only the end-zone pair is left.
        near = dartsGame(offScore=X - 1, ballOn=int(MR) - 5).game
        self.assertEqual(near._dartsHoopCoverAfterDeclining('midfield'), 1.0)
        # A spent pair does not count either.
        spent = dartsGame(offScore=X - 1, ballOn=60, hoopsUsed=('endzone',)).game
        self.assertEqual(spent._dartsHoopCoverAfterDeclining('midfield'), 1.0)

    def test_withChancesLeftItStillWeighsTheShot(self):
        """The control, and the reason this is not just 'always shoot'. Uses a BRIDGING
        need — at a need of 1 the shot wins the game outright and is taken regardless."""
        self.assertLess(self._rate(need=2, ballOn=60), 0.75,
                        'shooting on reflex with two chances still ahead')

    def test_aWinningClosingShotIsTakenEvenWithChancesLeft(self):
        """⚠️ Owner, 2026-08-24: needing one point the midfield goals are the nearest score,
        and driving past them risks the ball for nothing. The case is DOMINATED rather than
        merely risky — crossing the pair loses it either way, so declining loses it for
        nothing while shooting loses it only after a ~71% chance of ending the match, and a
        miss is an incompletion that keeps the ball. Measured over 400 games, drives that
        passed up an in-range midfield hoop needing 2 or fewer went on to score AT ALL 11
        times out of 22."""
        from constants import DARTS_HOOP_LOADBEARING_CHANCE
        rate = self._rate(need=1, ballOn=60)      # every pair still unused
        self.assertGreater(rate, DARTS_HOOP_LOADBEARING_CHANCE - 0.08,
                           f'passed up the shot that wins the game ({rate:.0%})')

    def test_aBridgingNeedIsNotTreatedAsStranded(self):
        """⚠️ THIS SHIPPED WRONG FOR ONE COMMIT. The stranding test was `cover < need`,
        which is only the right question BELOW a field goal, where hoops are the only score.
        Above it they BRIDGE — a need of 4 is a field goal plus one hoop — so demanding the
        hoops cover the whole need declared an ordinary kick-plus-dink drive stranded and
        shot at 93% where 57% belongs. Caught by sweeping the needs rather than spot-checking.
        """
        from constants import DARTS_HOOP_HUNT_BASE
        game = dartsGame(offScore=X - 4, ballOn=60).game
        self.assertEqual(game._dartsHoopCoverAfterDeclining('midfield'), 2.0)
        self.assertTrue(game._dartsNeedCoverableBy(2.0),
                        'a field goal plus a hoop still lands a need of 4')
        rate = self._rate(need=4, ballOn=60)
        self.assertLess(rate, DARTS_HOOP_HUNT_BASE + 0.15,
                        f'forced a bridging shot that had chances left ({rate:.0%})')

    def test_theBridgeMustActuallyReachALanding(self):
        """The counterpart: with only the midfield pair able to supply the bridging point,
        passing it up does strand the drive."""
        from constants import DARTS_HOOP_LOADBEARING_CHANCE
        game = dartsGame(offScore=X - 4, ballOn=60, hoopsUsed=('midrange', 'endzone')).game
        self.assertEqual(game._dartsHoopCoverAfterDeclining('midfield'), 0.0)
        self.assertFalse(game._dartsNeedCoverableBy(0.0))
        rate = self._rate(need=4, ballOn=60, hoopsUsed=('midrange', 'endzone'))
        self.assertGreater(rate, DARTS_HOOP_LOADBEARING_CHANCE - 0.08)

    def test_whenDecliningWouldStrandTheDriveItShoots(self):
        from constants import DARTS_HOOP_LOADBEARING_CHANCE
        cases = ((1, ('midrange', 'endzone')),   # nothing left behind the midfield pair
                 (2, ('midrange',)),             # only the end-zone pair, and it is 1 short
                 (2, ('endzone',)))
        for need, used in cases:
            rate = self._rate(need=need, ballOn=60, hoopsUsed=used)
            self.assertGreater(rate, DARTS_HOOP_LOADBEARING_CHANCE - 0.08,
                               f'need {need} with {used} spent shot only {rate:.0%}')

    def test_theEndZonePairIsNeverTreatedAsLoadBearing(self):
        """⚠️ It is not lost by driving on, so declining it costs a down and nothing else —
        and forcing it would erase the coach dial across the whole red zone."""
        from constants import DARTS_HOOP_HUNT_BASE
        rate = self._rate(need=1, ballOn=12, hoopsUsed=('midfield', 'midrange'))
        self.assertLess(rate, DARTS_HOOP_HUNT_BASE + 0.15,
                        f'the end-zone pair was forced ({rate:.0%})')

    def test_itIsInertWhenNoHoopIsWanted(self):
        """Needing exactly a field goal, the hoop is worth nothing and nothing is forced."""
        game = dartsGame(offScore=X - 3, ballOn=60, hoopsUsed=('midrange', 'endzone')).game
        rate = sum(game._shouldAttemptHoopShot() for _ in range(200)) / 200
        self.assertEqual(rate, 0.0)


class TheHuntIsCoachScaled(unittest.TestCase):
    """⚠️ Measured over many rolls rather than asserted on one, since the decision is a
    coin weighted by the coach — a single call proves nothing either way."""

    def _shootRate(self, aggressiveness, rolls=600):
        scenario = dartsGame(offScore=X - 1, ballOn=12, aggressiveness=aggressiveness)
        game = scenario.game
        if game._hoopTarget() is None:
            self.skipTest('fixture is out of hoop range')
        return sum(game._shouldAttemptHoopShot() for _ in range(rolls)) / rolls

    def test_anAggressiveCoachHuntsAndACautiousOneWaits(self):
        cautious = self._shootRate(62)
        aggressive = self._shootRate(98)
        self.assertGreater(aggressive, cautious + 0.2,
                           f'the dial is flat: {cautious:.2f} vs {aggressive:.2f}')

    def test_theNeutralCoachSitsAtTheBase(self):
        self.assertAlmostEqual(self._shootRate(80), DARTS_HOOP_HUNT_BASE, delta=0.08)

    def test_evenTheMostCautiousCoachSometimesShoots(self):
        """⚠️ Never shooting would mean a club that cannot win the format at all."""
        self.assertGreater(self._shootRate(60), 0.0)

    def test_theSpanIsWideEnoughToBeVisible(self):
        self.assertGreaterEqual(DARTS_HOOP_HUNT_AGGR_SPAN, 0.2)

    def test_itShootsOnTheFinalDownToo(self):
        """⚠️ THE INVERTED GUARD. 'Never on the final down' exists because a hoop consumes
        the down without gaining yards, forfeiting the real scoring play. Under a target
        there is no scoring play to forfeit: a TD is held up short and a FG is refused, so
        declining means the drive ends having never had a chance."""
        scenario = dartsGame(offScore=X - 1, ballOn=12, down=4, aggressiveness=98)
        game = scenario.game
        if game._hoopTarget() is None:
            self.skipTest('fixture is out of hoop range')
        self.assertTrue(any(game._shouldAttemptHoopShot() for _ in range(200)),
                        'never shoots on the final down, so the drive cannot score')


class TheMidfieldWindowShuts(unittest.TestCase):
    """⚠️ THE MIDFIELD PAIR IS USE-IT-OR-LOSE-IT (owner, 2026-08-17). It is reachable only
    while APPROACHING the 50; once the line of scrimmage crosses it the hoops are behind the
    offense and that pair is gone for the drive. `_hoopTarget` always enforced the geometry
    — what was missing is the offense ACTING on it. Driving forward is normally pure
    progress, and here it silently destroys one of the two scoring options a team needing
    1 or 2 points has, so the shot gets more urgent as the window shuts."""

    def _rate(self, ballOn, aggressiveness=80, rolls=600, need=2):
        """⚠️ A BRIDGING need (2) by default, NOT 1. At a need of 1 the closing shot WINS
        THE GAME and floors at `DARTS_HOOP_LOADBEARING_CHANCE` on every snap of the window,
        which is deliberate — but it swamps the gradient this class exists to measure and
        makes the curve read flat. Measure the lift where the shot is genuinely weighed."""
        scenario = dartsGame(offScore=X - need, ballOn=ballOn, aggressiveness=aggressiveness)
        game = scenario.game
        target = game._hoopTarget()
        self.assertIsNotNone(target, f'fixture at {ballOn} is out of hoop range')
        return target[0], sum(game._shouldAttemptHoopShot() for _ in range(rolls)) / rolls

    def test_theGeometryIsWhatTheFixtureAssumes(self):
        """Guard the yard numbers this class reasons about: yardsToEndzone 64 down to 50 is
        approaching the 50.

        ⚠️ Past the 50 the MIDFIELD pair is gone, but the field is no longer empty there —
        the third (midrange) pair covers yte 30-50, so the assertion is that the midfield
        pair specifically has dropped out, not that nothing is in range."""
        self.assertEqual(self._rate(64)[0], 'midfield')
        self.assertEqual(self._rate(52)[0], 'midfield')
        game = dartsGame(offScore=X - 1, ballOn=48).game
        target = game._hoopTarget()
        self.assertNotEqual((target or (None,))[0], 'midfield',
                            'past midfield that pair should be gone')

    def test_theShotGetsMoreUrgentAsTheWindowShuts(self):
        far = self._rate(64)[1]      # 14 yards before the crossing
        near = self._rate(51)[1]     # one yard before it
        self.assertGreater(near, far + 0.15,
                           f'no last-chance urgency: {far:.2f} at 14 out vs {near:.2f} at 1')

    def test_evenACautiousCoachTakesTheLastLook(self):
        """A cautious coach declining the final look loses the pair outright."""
        self.assertGreater(self._rate(50, aggressiveness=62)[1], 0.4)

    def test_theEndZonePairGetsNoSuchLift(self):
        """⚠️ It OPENS as the offense advances rather than closing, so there is never a last
        chance at it and a lift there would just be a blanket rate rise."""
        _, atEighteen = self._rate(18)
        _, atThree = self._rate(3)
        self.assertAlmostEqual(atEighteen, atThree, delta=0.12)

    def test_itIsStillAChanceRatherThanACertainty(self):
        """Even at the crossing a neutral coach sometimes plays on — the lift is urgency,
        not a scripted play.

        ⚠️ True of a BRIDGING need only. When the shot wins the game outright it is
        deliberately near-scripted (see `test_aWinningShotIsScriptedNotWeighed`), because
        crossing the pair loses it either way and declining buys nothing."""
        rate = self._rate(50)[1]
        self.assertLess(rate, 1.0)

    def test_aWinningShotIsScriptedNotWeighed(self):
        """The deliberate exception, and the reason `_rate` defaults to a bridging need."""
        self.assertGreater(self._rate(64, need=1)[1], 0.85,
                           'a shot that wins the game is still being weighed 14 yards out')
        self.assertGreater(self._rate(50, need=1)[1], 0.95)


class TheThirdPairFillsTheDeadZone(unittest.TestCase):
    """⚠️ WITH ONLY TWO PAIRS THERE WAS A 31-YARD DEAD ZONE between the end-zone band
    (yte 1-18) and the midfield window (yte 50-64), and measurement showed that is exactly
    where a team one point short spent its time: 81% of stuck snaps had nothing in range.
    The third pair sits at the 30 with a 20-yard reach, covering yte 30-50.

    ⚠️ What it buys is CONVERSION, not speed. Across three seeds the stuck spell did not
    reliably shorten -- a third pair does not make possessions arrive faster -- but those
    spells end in a landing far more often: 68 -> 74%, 58 -> 70%, 62 -> 70%, with target
    finishes overall 67 -> 81%.
    """

    def _pairAt(self, ballOn):
        game = dartsGame(offScore=X - 1, ballOn=ballOn).game
        return (game._hoopTarget() or (None, None))[0]

    def test_theDeadZoneIsSmallerThanItWas(self):
        """The old field had nothing between the 19 and the 49. Most of that is covered."""
        covered = [yte for yte in range(19, 50) if self._pairAt(yte) is not None]
        self.assertGreater(len(covered), 15,
                           'the third pair is not covering the gap it exists for')

    def test_itIsTheMidrangePairDoingIt(self):
        self.assertEqual(self._pairAt(40), 'midrange')
        self.assertEqual(self._pairAt(31), 'midrange')

    def test_theNearestPairWinsWhereWindowsOverLAP(self):
        """⚠️ THE BUG THIS INTRODUCED. Midrange reaches to the 50, exactly where midfield
        opens, so at that spot both match -- midfield at d=0 (a tap) and midrange at d=20
        (a heave). A fixed priority order picked the harder shot, and silently disabled the
        closing-window urgency, which applies only to the midfield pair."""
        game = dartsGame(offScore=X - 1, ballOn=50).game
        pair, distance = game._hoopTarget()
        self.assertEqual(pair, 'midfield')
        self.assertEqual(distance, 0.0)

    def test_theEndZonePairIsStillPreferredUpClose(self):
        self.assertEqual(self._pairAt(12), 'endzone')

    def test_thePairCountIsReadNotAssumed(self):
        """⚠️ `_hoopPointsNeeded` had the literal `2` for how many hoops a drive holds. Left
        alone it would have under-counted with three pairs, so a team needing 3 would have
        read its hoops as unable to reach."""
        game = dartsGame(offScore=X - 1).game
        self.assertEqual(game._hoopPairCount(), 3)
        with open('floosball_game.py') as fh:
            body = fh.read().split('def _hoopPointsNeeded')[1].split('\n    def ')[0]
        self.assertIn('self._hoopPairCount()', body)
        self.assertNotIn('max(0, 2 -', body)

    def test_threeHoopsCanCarryANeedOfThree(self):
        """The point of the count being right: with three pairs open, a need of 3 is
        reachable on hoops alone -- though a field goal lands it too, so the card is only
        'critical' below a field goal."""
        game = dartsGame(offScore=X - 3).game
        self.assertEqual(game._hoopPairCount(), 3)

    def test_switchingItOffRestoresTheTwoPairField(self):
        """One constant reverts it, which is what made the experiment cheap."""
        import constants
        original = constants.SIDELINE_GOAL_MIDRANGE_YARD
        try:
            constants.SIDELINE_GOAL_MIDRANGE_YARD = 0
            game = dartsGame(offScore=X - 1, ballOn=40).game
            self.assertIsNone(game._hoopTarget())
            self.assertEqual(game._hoopPairCount(), 2)
        finally:
            constants.SIDELINE_GOAL_MIDRANGE_YARD = original


class ADisciplinedSideManagesTheApproach(unittest.TestCase):
    """⚠️ The midfield pair is the only scoring chance a drive can drive PAST. A chunk gain
    over the 50 is an ordinary good outcome that destroys it, and for a team needing 1 or 2
    points that is one of only two ways left to score. So a disciplined side stops trying to
    go downfield and works the sideline the hoops stand on (owner, 2026-08-17).

    Both terms are required to execute: the COACH has to see the situation
    (`clockManagement`) and the TEAM has to hold the discipline to run short when a big
    play is available (`collectiveDiscipline`)."""

    def _probe(self, ballOn, discipline=98, clockManagement=98):
        scenario = dartsGame(offScore=X - 1, ballOn=ballOn)
        game = scenario.game
        for player in game.homeTeam.rosterDict.values():
            live = getattr(player, 'gameAttributes', None) if player else None
            if live is not None:
                live.discipline = discipline
        game.homeTeam.coach.clockManagement = clockManagement
        weights = {'run': 100.0, 'shortPass': 100.0, 'mediumPass': 100.0,
                   'longPass': 50.0, 'deepPass': 20.0}
        out = game._applySituationalMods(dict(weights), game.homeScore - game.awayScore,
                                         game.homeTeam.coach)
        total = sum(out.values())
        diff = game.homeScore - game.awayScore
        sideline = sum(game._shouldTargetSideline(diff, game.homeTeam.coach)
                       for _ in range(400)) / 400.0
        return {
            'approach': game._dartsHoopApproach(),
            'downfield': (out.get('longPass', 0) + out.get('deepPass', 0)) / total,
            'control': (out['run'] + out.get('shortPass', 0)) / total,
            'sideline': sideline,
        }

    def test_farOutThereIsNoConflictAtAll(self):
        """⚠️ Beyond the horizon advancing IS what the offense wants, so this must be
        completely inert — otherwise darts teams would never drive."""
        self.assertEqual(self._probe(75)['approach'], 0.0)

    def test_itTightensAsTheWindowCloses(self):
        approaches = [self._probe(ballOn)['approach'] for ballOn in (75, 64, 56, 51)]
        self.assertEqual(approaches, sorted(approaches))
        self.assertGreater(approaches[-1], 0.7, 'no restraint at the crossing')

    def test_theDisciplinedSideStopsGoingDownfield(self):
        near = self._probe(51)
        self.assertLess(near['downfield'], 0.10)
        self.assertGreater(near['control'], 0.75)

    def test_aLooseSideJustPlaysOn(self):
        """THE POINT OF MAKING IT AN ATTRIBUTE. An undisciplined team drives straight past
        its own scoring chance, which is the mistake worth being able to make."""
        loose = self._probe(51, discipline=62, clockManagement=62)
        disciplined = self._probe(51)
        self.assertLess(loose['approach'], 0.15)
        self.assertGreater(disciplined['downfield'] * 2, loose['downfield'] * 0.5)
        self.assertLess(loose['control'], disciplined['control'])

    def test_bothTermsAreNeeded(self):
        """A sharp coach with a loose roster, or the reverse, gets part of the effect —
        neither alone should produce the full clamp."""
        full = self._probe(51)['approach']
        coachOnly = self._probe(51, discipline=62)['approach']
        teamOnly = self._probe(51, clockManagement=62)['approach']
        for partial in (coachOnly, teamOnly):
            self.assertLess(partial, full)
            self.assertGreater(partial, 0.0)

    def test_itWorksTheSideline(self):
        """The hoops stand on the boundary, so the throw that gets closer to the thing you
        intend to shoot at is the one going that way."""
        self.assertGreater(self._probe(51)['sideline'], 0.7)
        self.assertLess(self._probe(51, discipline=62, clockManagement=62)['sideline'], 0.2)

    def test_pastMidfieldTheMidrangePairTakesOver(self):
        """⚠️ THIS TEST USED TO ASSERT THE BUG. It read "past midfield it stops" and pinned
        `_dartsHoopApproach() == 0.0` from the 45 — true of the MIDFIELD pair and false of
        the drive, because the midrange pair at the 30 is still ahead and shuts the same
        way. Restraint fell to exactly zero across the whole 48-to-30 stretch, which is
        precisely where the last hoop was about to be driven past.

        Restraint stops when there is nothing left AHEAD to destroy, not at a fixed yard.
        """
        from constants import SIDELINE_GOAL_MIDRANGE_YARD
        game = dartsGame(offScore=X - 1, ballOn=45).game
        self.assertEqual(game._dartsClosingPair()[0], 'midrange')
        self.assertGreater(game._dartsHoopApproach(), 0.0,
                           'the drive is unrestrained with a hoop still in front of it')
        # Ramps as that window shuts, exactly as it did approaching the 50.
        near = dartsGame(offScore=X - 1, ballOn=int(SIDELINE_GOAL_MIDRANGE_YARD) + 2).game
        self.assertGreater(near._dartsHoopApproach(), game._dartsHoopApproach())

    def test_pastTheLastClosingPairItStops(self):
        """The real version of the rule: inside the final pair, nothing a drive does can
        destroy a scoring chance, so it goes back to playing football.

        ⚠️ The END-ZONE pair is deliberately not a closing pair — it OPENS as the offense
        advances, so there is never a last chance at it and nothing to hold back for."""
        from constants import SIDELINE_GOAL_MIDRANGE_YARD
        game = dartsGame(offScore=X - 1, ballOn=int(SIDELINE_GOAL_MIDRANGE_YARD) - 5).game
        self.assertIsNone(game._dartsClosingPair())
        self.assertEqual(game._dartsHoopApproach(), 0.0)

    def test_aSpentPairHandsOffToTheNextOne(self):
        """A spent midfield pair does not end the restraint — it moves it to the midrange
        pair, which is still in front of the ball."""
        game = dartsGame(offScore=X - 1, ballOn=40, hoopsUsed=('midfield',)).game
        self.assertEqual(game._dartsClosingPair()[0], 'midrange')
        self.assertGreater(game._dartsHoopApproach(), 0.0)

    def test_everyClosingPairSpentStopsIt(self):
        game = dartsGame(offScore=X - 1, ballOn=40,
                         hoopsUsed=('midfield', 'midrange')).game
        self.assertIsNone(game._dartsClosingPair())
        self.assertEqual(game._dartsHoopApproach(), 0.0)

    def test_noHoopWantedNoRestraint(self):
        """Needing exactly a field goal, the hoop is worth nothing and the drive should be
        run normally."""
        game = dartsGame(offScore=X - 3, ballOn=56).game
        self.assertEqual(game._dartsHoopApproach(), 0.0)

    def test_noOtherFormatIsAffected(self):
        scenario = Scenario()
        scenario.situation(quarter=2, clock=600, offense='home', offScore=17, defScore=3,
                           down=1, distance=10, ballOn=56, offTimeouts=3, defTimeouts=3)
        self.assertEqual(scenario.game._dartsHoopApproach(), 0.0)

    def test_theTeamCompositeReadsTheLivePlayers(self):
        """⚠️ `gameAttributes`, not `attributes` — compression, fatigue, morale and form all
        land on the live copy, and a decision made during a game should see the same
        players the plays do."""
        game = dartsGame(offScore=X - 1, ballOn=56).game
        for player in game.homeTeam.rosterDict.values():
            live = getattr(player, 'gameAttributes', None) if player else None
            if live is not None:
                live.discipline = 100
        high = game.homeTeam.collectiveDiscipline()
        for player in game.homeTeam.rosterDict.values():
            live = getattr(player, 'gameAttributes', None) if player else None
            if live is not None:
                live.discipline = 60
        self.assertLess(game.homeTeam.collectiveDiscipline(), high)

    def test_anEmptyRosterReadsNeutralRatherThanLoose(self):
        from floosball_team import Team
        team = Team.__new__(Team)
        team.rosterDict = {}
        self.assertEqual(team.collectiveDiscipline(), 0.5)


class ADeadDrivePunts(unittest.TestCase):
    """Both pairs spent and the need under a field goal: nothing can score this possession."""

    def test_theStateIsRecognised(self):
        game = dartsGame(offScore=X - 1, hoopsUsed=ALL_PAIRS_SPENT).game
        self.assertTrue(game._dartsDriveIsDead())

    def test_anOpenPairIsNotADeadDrive(self):
        game = dartsGame(offScore=X - 1, hoopsUsed=('midfield',)).game
        self.assertFalse(game._dartsDriveIsDead())

    def test_aReachableNeedIsNotADeadDrive(self):
        """Needing a field goal exactly, the drive is perfectly alive."""
        game = dartsGame(offScore=X - 3, hoopsUsed=ALL_PAIRS_SPENT).game
        self.assertFalse(game._dartsDriveIsDead())

    def test_noOtherFormatIsEverDead(self):
        scenario = Scenario()
        scenario.situation(quarter=2, clock=600, offense='home', offScore=17, defScore=3,
                           down=4, distance=2, ballOn=40, offTimeouts=3, defTimeouts=3)
        self.assertFalse(scenario.game._dartsDriveIsDead())

    def test_itPuntsOnTheFinalDown(self):
        """⚠️ Not a concession — the hoop pairs RESET on the next possession, so ending the
        drive is how the offense restocks the only scoring play it has left."""
        scenario = dartsGame(offScore=X - 1, hoopsUsed=ALL_PAIRS_SPENT,
                             down=4, ballOn=45)
        self.assertIs(scenario.fourthDownPlay(), PlayType.Punt)

    def test_itPuntsEvenInFieldGoalRange(self):
        """The kick is refused by the format anyway (it would bust), so 'in range' is
        meaningless here and must not tempt the caller into a field goal."""
        scenario = dartsGame(offScore=X - 1, hoopsUsed=ALL_PAIRS_SPENT,
                             down=4, ballOn=20)
        scenario.setKickerLeg('home', 60)
        self.assertIs(scenario.fourthDownPlay(), PlayType.Punt)

    def test_aLiveDriveStillDoesSomethingElse(self):
        """The counterpart: if this always punted, darts would never convert a fourth down.

        ⚠️ Short yardage in scoring territory, deliberately — at 4th and 10 from the 45 a
        punt is simply the right call, so a fixture there would pass this for the wrong
        reason and prove nothing about the dead-drive rule."""
        scenario = dartsGame(offScore=X - 6, down=4, distance=1, ballOn=30)
        calls = {scenario.fourthDownPlay() for _ in range(30)}
        self.assertTrue(calls - {PlayType.Punt},
                        'every fourth down punts — the dead-drive rule is too broad')


class ADeadDriveKneelsItOutAtTheGoal(unittest.TestCase):
    """A drive that can no longer score plays for FIELD POSITION and then kneels it out
    (owner, 2026-08-24).

    ⚠️ THE OFFENSE WAS PUNTING FROM THE OPPONENT'S 1-YARD LINE. On a dead drive the need is
    under a field goal, so a would-bust touchdown is held up short — `_holdUpShortCap` caps
    the carrier at `yardsToEndzone - 1` — and the offense piles up ON the goal line unable
    to cross it. `_fourthDownCaller` then punted, which from there is a touchback: the
    opponent takes the ball on their own `PUNT_TOUCHBACK_TO` (20). Giving it up on downs
    where it already sits hands them their own 1 instead. Measured over 400 games at X=24,
    the rule refuses 19 punts, struck from a median `yardsToEndzone` of 4 and three of them
    from the literal 1-yard line. It also turns 15 dead-drive runs and passes at the goal
    into kneels.

    ⚠️ A snap at the goal line there is PURE DOWNSIDE — it cannot produce a point, the cap
    leaves nothing to gain, and it can still fumble or throw a pick. The down is being
    surrendered either way, so a kneel forfeits nothing the drive still had.
    """

    def _dead(self, ballOn, down=1, **kw):
        return dartsGame(offScore=X - 1, hoopsUsed=ALL_PAIRS_SPENT,
                         ballOn=ballOn, down=down, **kw)

    def test_theFixtureIsActuallyDead(self):
        g = self._dead(ballOn=1).game
        self.assertTrue(g._dartsDriveIsDead())
        self.assertLess(need(g), g._fgValue(), 'a field goal would still land')

    def test_itKneelsAtTheGoalLine(self):
        from constants import DARTS_KNEEL_OUT_YARDS
        for ballOn in range(1, DARTS_KNEEL_OUT_YARDS + 1):
            g = self._dead(ballOn=ballOn).game
            g.play.playType = PlayType.Run
            self.assertTrue(g._dartsKneelOut(), f'did not kneel from the {ballOn}')
            self.assertIs(g.play.playType, PlayType.Kneel)

    def test_itKneelsOnAnyDownNotJustTheLast(self):
        """The down is going either way, so there is nothing to save it for."""
        for down in range(1, 5):
            g = self._dead(ballOn=1, down=down).game
            g.play.playType = PlayType.Pass
            self.assertTrue(g._dartsKneelOut(), f'did not kneel on down {down}')
            self.assertIs(g.play.playType, PlayType.Kneel)

    def test_itRefusesThePuntInsideTheTouchbackLine(self):
        """⚠️ THE POINT OF THE WHOLE RULE. A punt cannot do better than spotting them the
        touchback, so from inside it the punt gives away field position to gain nothing."""
        g = self._dead(ballOn=12, down=4).game
        g.play.playType = PlayType.Punt
        self.assertTrue(g._dartsKneelOut())
        self.assertIsNot(g.play.playType, PlayType.Punt,
                         'punted from inside the touchback line on a dead drive')

    def test_beyondTheTouchbackLineThePuntStays(self):
        """⚠️ NOT an oversight. From out there a punt genuinely buys field position a
        turnover on downs does not, and the pairs RESET next possession — so ending the
        drive is how the offense restocks the only scoring play it has."""
        from constants import PUNT_TOUCHBACK_TO
        g = self._dead(ballOn=PUNT_TOUCHBACK_TO + 5, down=4).game
        g.play.playType = PlayType.Punt
        self.assertFalse(g._dartsKneelOut())
        self.assertIs(g.play.playType, PlayType.Punt)

    def test_aLiveDriveIsNeverKnelt(self):
        """The counterpart: with the drive still able to score, kneeling throws the game."""
        for hoops in ((), ('midfield',), ('midfield', 'midrange')):
            g = dartsGame(offScore=X - 1, hoopsUsed=hoops, ballOn=1).game
            g.play.playType = PlayType.Run
            self.assertFalse(g._dartsKneelOut(), f'knelt with {hoops or "no"} pairs spent')
        g = dartsGame(offScore=X - 3, hoopsUsed=ALL_PAIRS_SPENT, ballOn=1).game
        g.play.playType = PlayType.Run
        self.assertFalse(g._dartsKneelOut(), 'knelt while a field goal would land')

    def test_itIsANoOpInStandardFootball(self):
        scenario = Scenario()
        scenario.situation(quarter=2, clock=600, offense='home', offScore=17, defScore=3,
                           down=4, distance=2, ballOn=1, offTimeouts=3, defTimeouts=3)
        g = scenario.game
        g.play.playType = PlayType.Punt
        self.assertFalse(g._dartsKneelOut())
        self.assertIs(g.play.playType, PlayType.Punt)


class WhichHoopsAreStillReachable(unittest.TestCase):
    """⚠️ "OPEN" IS NOT "UNUSED". `_hoopTarget` only returns a pair while the ball is still
    APPROACHING it, so once the line of scrimmage clears the 50 the midfield pair is behind
    the offense forever — as gone as one already shot at. `_dartsDriveIsDead` counted SPENT
    pairs (`len(used) >= 2`, against three pairs), which was wrong in both directions at
    once: it called a drive dead while a live midrange pair sat in front of it, and called
    one alive with nothing ahead but pairs it had already driven past.

    Measured by evaluating BOTH predicates at the same snap across 400 games at X=24 (a
    within-run pairing — this harness is not reproducible run to run, so two separate sims
    cannot be compared): over 1,424 snaps where only a hoop could score, of the 162 the
    count called dead it was wrong about 102 — 77 dead with a hoop still reachable, 25
    alive with nothing left in front of them.
    """

    def test_anUnusedEndZonePairIsAlwaysReachable(self):
        """Every drive advances into it, so it is the pair whose loss actually strands a
        possession."""
        for ballOn in (1, 12, 35, 60, 90):
            g = dartsGame(offScore=X - 1, hoopsUsed=('midfield', 'midrange'),
                          ballOn=ballOn).game
            self.assertTrue(g._dartsHoopReachable(), f'unreachable from the {ballOn}')
            self.assertFalse(g._dartsDriveIsDead())

    def test_aPairTheBallHasDrivenPastIsGone(self):
        """End-zone pair spent and the ball inside the midrange pair: nothing ahead."""
        from constants import SIDELINE_GOAL_MIDRANGE_YARD
        g = dartsGame(offScore=X - 1, hoopsUsed=('endzone',),
                      ballOn=int(SIDELINE_GOAL_MIDRANGE_YARD) - 5).game
        self.assertFalse(g._dartsHoopReachable())
        self.assertTrue(g._dartsDriveIsDead())

    def test_thatSamePairIsReachableFromBehindIt(self):
        """The control for the case above — one fixture, moved back up the field."""
        from constants import SIDELINE_GOAL_MIDRANGE_YARD
        g = dartsGame(offScore=X - 1, hoopsUsed=('endzone',),
                      ballOn=int(SIDELINE_GOAL_MIDRANGE_YARD) + 5).game
        self.assertTrue(g._dartsHoopReachable())
        self.assertFalse(g._dartsDriveIsDead())

    def test_aPairInRangeRightNowCounts(self):
        g = dartsGame(offScore=X - 1, hoopsUsed=('midfield', 'midrange'), ballOn=8).game
        self.assertIsNotNone(g._hoopTarget())
        self.assertTrue(g._dartsHoopReachable())


class ALeaderBurnsTheClock(unittest.TestCase):
    """A dead drive is worth nothing but time. If the clock beats both teams to the target
    the higher score wins, so the leader drains it and the trailer wants the drive over."""

    def _runShare(self, offScore, defScore):
        scenario = dartsGame(offScore=offScore, defScore=defScore,
                             hoopsUsed=ALL_PAIRS_SPENT, down=1, ballOn=45)
        game = scenario.game
        weights = {'run': 100.0, 'shortPass': 100.0, 'mediumPass': 100.0,
                   'longPass': 50.0, 'deepPass': 20.0}
        out = game._applySituationalMods(dict(weights), offScore - defScore,
                                         getattr(game.homeTeam, 'coach', None))
        return out['run'] / sum(out.values())

    def test_theLeaderLeansRun(self):
        leading = self._runShare(X - 1, 2)
        trailing = self._runShare(X - 1, X - 1)
        self.assertGreater(leading, trailing,
                           'a leading dead drive should drain the clock with runs')

    def test_theTrailerIsNotSlowedDown(self):
        """⚠️ Burning clock while behind spends the very thing that team needs — it wants
        this drive over so it can restock its hoops."""
        scenario = dartsGame(offScore=X - 1, defScore=X - 1,
                             hoopsUsed=ALL_PAIRS_SPENT, ballOn=45)
        game = scenario.game
        base = {'run': 100.0, 'shortPass': 100.0}
        withMods = game._applySituationalMods(dict(base), 0,
                                              getattr(game.homeTeam, 'coach', None))
        plain = dartsGame(offScore=X - 6, defScore=X - 1, ballOn=45).game
        plainMods = plain._applySituationalMods(dict(base), -5,
                                                getattr(plain.homeTeam, 'coach', None))
        self.assertAlmostEqual(withMods['run'] / sum(withMods.values()),
                               plainMods['run'] / sum(plainMods.values()), delta=0.15)


class TheRulesDocMatchesTheCode(unittest.TestCase):

    def test_aMissIsAnIncompletionNotATurnover(self):
        """⚠️ `game_rules.py` said a miss is 'a turnover at the current line of scrimmage'.
        The implementation has always been an incompletion, and nothing downstream changes
        possession, so the doc was simply wrong about a rule people reason from."""
        with open('game_rules.py') as fh:
            doc = fh.read()
        block = doc.split('Sideline Goals')[1][:900]
        self.assertNotIn('MISS is a turnover', block,
                         'the rules doc still describes a miss as a turnover')
        with open('floosball_game.py') as fh:
            src = fh.read()
        self.assertIn('SidelineHoopMiss   # an incompletion; no turnover', src)


if __name__ == '__main__':
    unittest.main(verbosity=2)
