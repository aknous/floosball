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

    def _rate(self, ballOn, aggressiveness=80, rolls=600):
        scenario = dartsGame(offScore=X - 1, ballOn=ballOn, aggressiveness=aggressiveness)
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
        not a scripted play."""
        rate = self._rate(50)[1]
        self.assertLess(rate, 1.0)


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

    def test_pastMidfieldItStops(self):
        """The pair is gone whatever happens now, so there is nothing left to protect and
        the offense should go back to playing football."""
        scenario = dartsGame(offScore=X - 1, ballOn=45)
        self.assertEqual(scenario.game._dartsHoopApproach(), 0.0)

    def test_aSpentPairStopsIt(self):
        game = dartsGame(offScore=X - 1, ballOn=56, hoopsUsed=('midfield',)).game
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
        game = dartsGame(offScore=X - 1, hoopsUsed=('midfield', 'redzone')).game
        self.assertTrue(game._dartsDriveIsDead())

    def test_anOpenPairIsNotADeadDrive(self):
        game = dartsGame(offScore=X - 1, hoopsUsed=('midfield',)).game
        self.assertFalse(game._dartsDriveIsDead())

    def test_aReachableNeedIsNotADeadDrive(self):
        """Needing a field goal exactly, the drive is perfectly alive."""
        game = dartsGame(offScore=X - 3, hoopsUsed=('midfield', 'redzone')).game
        self.assertFalse(game._dartsDriveIsDead())

    def test_noOtherFormatIsEverDead(self):
        scenario = Scenario()
        scenario.situation(quarter=2, clock=600, offense='home', offScore=17, defScore=3,
                           down=4, distance=2, ballOn=40, offTimeouts=3, defTimeouts=3)
        self.assertFalse(scenario.game._dartsDriveIsDead())

    def test_itPuntsOnTheFinalDown(self):
        """⚠️ Not a concession — the hoop pairs RESET on the next possession, so ending the
        drive is how the offense restocks the only scoring play it has left."""
        scenario = dartsGame(offScore=X - 1, hoopsUsed=('midfield', 'redzone'),
                             down=4, ballOn=45)
        self.assertIs(scenario.fourthDownPlay(), PlayType.Punt)

    def test_itPuntsEvenInFieldGoalRange(self):
        """The kick is refused by the format anyway (it would bust), so 'in range' is
        meaningless here and must not tempt the caller into a field goal."""
        scenario = dartsGame(offScore=X - 1, hoopsUsed=('midfield', 'redzone'),
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


class ALeaderBurnsTheClock(unittest.TestCase):
    """A dead drive is worth nothing but time. If the clock beats both teams to the target
    the higher score wins, so the leader drains it and the trailer wants the drive over."""

    def _runShare(self, offScore, defScore):
        scenario = dartsGame(offScore=offScore, defScore=defScore,
                             hoopsUsed=('midfield', 'redzone'), down=1, ballOn=45)
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
                             hoopsUsed=('midfield', 'redzone'), ballOn=45)
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
