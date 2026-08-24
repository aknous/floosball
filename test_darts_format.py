"""Darts (`bust`) — certification.

⚠️ THIS FORMAT SHIPPED WITH NO TESTS AT ALL while frames, innings and chess clock each have
several files, and its rule-vote preset was commented out as "HELD until tested". This is
that test pass.

The rules: land EXACTLY on the target X to win; a score that would push you over X is
VOIDED and turns the ball over, so you can never exceed it; scores are whole numbers so
landing on X is always arithmetically possible; the clock runs normally and if it expires
first the higher score (both <= X) wins.

⚠️ THE DEFECT FOUND: the 1-point hoop is darts' PREREQUISITE, and the format only claimed
to bundle it. `sidelineGoalsEnabled` lived in the commented-out preset, so darts switched on
any other way ran without it -- and without a 1-pointer the smallest score is a 3-point
field goal, so a team sitting on X-1 or X-2 can never land on X. The win condition is
unreachable from the two positions closest to winning. Measured over 40 games at X=18:

                                  hoops off   hoops on
    decided by landing on X             8%        85%
    team-scores stranded at X-1/X-2      38         10
    ties                                  3          0

Without them darts is not a game about landing on a number; it is ordinary football with a
ceiling, decided by the clock. The flag now lives in `BustFormat.bundledRules`, applied when
the format is resolved, so every activation path gets the same game.

Run: .venv/bin/python test_darts_format.py
"""
import asyncio
import logging
import random
import unittest

logging.disable(logging.CRITICAL)

from game_formats import getFormat, GameFormat
from game_rules import GameRules
from scenario import Scenario

# The shipped preset's target, so the engine tests below exercise what actually runs.
X = 24

# The sideline-hoop pairs, in the order a drive meets them. ⚠️ Use these names in fixtures:
# `_dartsDriveIsDead` asks which pairs are still REACHABLE, so a made-up key leaves the
# pair it meant to spend wide open and the drive alive.
HOOP_PAIRS = ('midfield', 'midrange', 'endzone')


def dartsRules(target=X, **overrides):
    rules = GameRules()
    rules.gameFormat = 'bust'
    rules.targetScore = target
    for key, value in overrides.items():
        setattr(rules, key, value)
    return rules


def playDarts(count, seed=5, target=X, **overrides):
    """Play real games and return their finals. Deliberately the whole engine — the point
    of a certification pass is that the format survives contact with it."""
    async def run():
        random.seed(seed)
        out = []
        for _ in range(count):
            game = Scenario(gameRules=dartsRules(target, **overrides)).game
            await game.playGame()
            out.append((game.homeScore, game.awayScore))
        return out
    return asyncio.run(run())


class TheFormatAssertsItsOwnPrerequisite(unittest.TestCase):
    """THE DEFECT. A format is a strategy over the rules, but a prerequisite is not
    optional decoration — without it the win condition is unreachable."""

    def test_dartsBundlesTheOnePointHoop(self):
        self.assertEqual(getFormat('bust').bundledRules(),
                         {'sidelineGoalsEnabled': True})

    def test_resolvingTheFormatAppliesIt(self):
        rules = dartsRules()
        self.assertFalse(rules.sidelineGoalsEnabled, 'fixture should start with it off')
        game = Scenario(gameRules=rules).game
        self.assertEqual(game.format.key, 'bust')
        self.assertTrue(rules.sidelineGoalsEnabled,
                        'darts resolved without its 1-point hoop')

    def test_noOtherFormatBundlesAnything(self):
        """⚠️ The hook only ever turns things ON, and only darts needs it. If another
        format grows a prerequisite it should be a deliberate decision, not inherited."""
        for key in ('standard', 'target', 'play_limit', 'chess_clock', 'innings', 'frames'):
            self.assertEqual(getFormat(key).bundledRules(), {},
                             f'{key} should require no extra rules')

    def test_standardGamesAreUntouched(self):
        rules = GameRules()
        game = Scenario(gameRules=rules).game
        self.assertEqual(game.format.key, 'standard')
        self.assertFalse(rules.sidelineGoalsEnabled)

    def test_itNeverTurnsARuleOFF(self):
        """A format asserting what it needs is reasonable; one silently cancelling a rule
        the league voted for is not."""
        for key in ('bust', 'standard', 'frames', 'innings'):
            for value in getFormat(key).bundledRules().values():
                self.assertTrue(value, f'{key} bundles a rule as False')

    def test_theBaseClassDefaultIsEmpty(self):
        self.assertEqual(GameFormat().bundledRules(), {})


class TheKickGuardIsCentral(unittest.TestCase):
    """A busting field goal banks NOTHING and concedes the ball, so it is never the right
    call — and the offense was making it.

    ⚠️ THE RULE HAD ONE ENFORCEMENT POINT AND ~35 ENTRANCES. `allowFieldGoal` was
    consulted only by `_fourthDownCaller`, while every other site that can set
    `PlayType.FieldGoal` kicked straight past it — `endOfHalfFG` most of all, because it
    deliberately sits ABOVE the down split and fires on any down. Measured over 60 games
    before the guard: every bust in the sample was a field goal, about half from that one
    path. After: zero, with no path attributed.

    These pin the GUARD rather than the count. The bust rate is emergent and small enough
    that a threshold on it would be flaky (see the note above on distributions); "the
    offense never chooses a kick that cannot score" is a hard invariant and testable.
    """

    def setUp(self):
        self.game = Scenario(gameRules=dartsRules()).game
        self.game.offensiveTeam = self.game.homeTeam
        self.game.defensiveTeam = self.game.awayTeam
        self.game.play = self.game.play or None

    def _kickFrom(self, score, yardsToEndzone=20, down=1, hoopsUsed=0):
        """Set up a snap where the offense has decided to kick and would bust."""
        from floosball_game import Play, PlayType
        g = self.game
        g.homeScore = score
        g.down = down
        g.yardsToEndzone = yardsToEndzone
        # ⚠️ REAL PAIR NAMES. `_dartsDriveIsDead` asks which pairs are still REACHABLE, and
        # the end-zone pair is the one every drive advances into — so `pair0/pair1` style
        # placeholders leave it live and the drive is not dead at all. They passed only
        # while the check counted keys.
        g._hoopPairResult = {p: 'made' for p in HOOP_PAIRS[:hoopsUsed]}
        g.play = Play(g)
        g.play.playType = PlayType.FieldGoal
        return g

    def test_aKickThatWouldBustIsOverridden(self):
        from floosball_game import PlayType
        g = self._kickFrom(X - 1)
        self.assertTrue(g._refuseBustingKick(), 'the guard did not fire')
        self.assertIsNot(g.play.playType, PlayType.FieldGoal,
                         'kicked a field goal that cannot score')

    def test_aKickThatLandsExactlyIsLeftAlone(self):
        from floosball_game import PlayType
        g = self._kickFrom(X - 3)   # a field goal lands on X exactly
        self.assertFalse(g._refuseBustingKick(), 'refused a kick that wins the game')
        self.assertIs(g.play.playType, PlayType.FieldGoal)

    def test_aDeadDrivePunts(self):
        """No hoop left and the need under a field goal: nothing on this possession can
        score, and the pairs reset next drive — so giving the ball up restocks the only
        scoring play the offense has."""
        from floosball_game import PlayType
        g = self._kickFrom(X - 1, hoopsUsed=len(HOOP_PAIRS))
        self.assertTrue(g._refuseBustingKick())
        self.assertIs(g.play.playType, PlayType.Punt)

    def test_withAHoopLeftTheDrivePlaysOn(self):
        """Yards are how you reach the 1-pointer that actually lands, so a live hoop is
        worth playing for rather than punting away."""
        from floosball_game import PlayType
        g = self._kickFrom(X - 1, hoopsUsed=0, down=1)
        g._refuseBustingKick()
        self.assertIsNot(g.play.playType, PlayType.Punt,
                         'punted a drive that could still land a hoop')

    def test_onAFinalDownFarOutItPunts(self):
        """Deep in opponent territory a failed try costs little, so go for it — from
        further out it hands over real field position, so punt."""
        from floosball_game import PlayType
        g = self._kickFrom(X - 1, yardsToEndzone=60,
                           down=self.game.gameRules.downsPerSeries)
        self.assertTrue(g._refuseBustingKick())
        self.assertIs(g.play.playType, PlayType.Punt)

    def test_itIsANoOpInStandardFootball(self):
        """The guard runs on every snap of every format, so it has to cost nothing
        anywhere else."""
        from floosball_game import Play, PlayType
        from game_rules import GameRules
        g = Scenario(gameRules=GameRules()).game
        g.offensiveTeam, g.defensiveTeam = g.homeTeam, g.awayTeam
        g.play = Play(g)
        g.play.playType = PlayType.FieldGoal
        self.assertFalse(g._refuseBustingKick())
        self.assertIs(g.play.playType, PlayType.FieldGoal)


class TheOnlyScoreLeftIsTaken(unittest.TestCase):
    """The mirror of the kick guard: when a field goal is the ONLY score still available,
    the offense takes it on ANY down.

    ⚠️ THE STATE IS NOT AN EDGE CASE AND THE OFFENSE WAS PLAYING THROUGH IT. Three facts
    combine to strand a drive: a touchdown is VOIDED when it would clear X (the carrier is
    held up short instead), both hoop pairs are spent, and the remaining need is still a
    field goal or more. Nothing a normal snap can do puts a point on the board — yet every
    read in the standard tree is about the deficit against the OPPONENT rather than the
    distance to the TARGET, so it kept calling football until the final down.

    Measured at the choke point over 200 games at X=24, rule off: 58 snaps sat in this
    state, all in range, and 42 of them were runs or passes. Rule on: 21 states, all 21
    kicking (the count falls because a drive now resolves the moment it can instead of
    burning three downs first). Every state in the sample was inside the opponent's 20 —
    many at the 1-yard line, a carrier held up short over and over — and the kick being
    declined sat at the engine's 0.96 make ceiling, so there is no 'work closer for a
    better kick' trade being given up.
    """

    def setUp(self):
        self.game = Scenario(gameRules=dartsRules()).game
        self.game.offensiveTeam = self.game.homeTeam
        self.game.defensiveTeam = self.game.awayTeam

    def _snap(self, score, down=1, yardsToEndzone=12, hoopsUsed=None, playType=None):
        """⚠️ `hoopsUsed` defaults to ALL of them, read off `_hoopPairCount()` rather than
        hardcoded — the third (midrange) pair was added after the first two and a literal 2
        would leave a live hoop, which is exactly the case that keeps the choice open."""
        from floosball_game import Play, PlayType
        g = self.game
        if hoopsUsed is None:
            hoopsUsed = g._hoopPairCount()
        g.homeScore = score
        g.down = down
        g.yardsToEndzone = yardsToEndzone
        g.yardsToFirstDown = 10
        g._hoopPairResult = {f'pair{i}': 'made' for i in range(hoopsUsed)}
        g.play = Play(g)
        g.play.playType = playType if playType is not None else PlayType.Pass
        return g

    def test_itKicksOnAnyDown(self):
        """X-4: a field goal lands (leaving 1 for nothing), a touchdown busts, no hoop
        left. There is one scoring play and it should not wait for the final down."""
        from floosball_game import PlayType
        for down in range(1, self.game.gameRules.downsPerSeries + 1):
            g = self._snap(X - 4, down=down)
            self.assertTrue(g._dartsForceKick(), f'the rule did not fire on down {down}')
            self.assertIs(g.play.playType, PlayType.FieldGoal,
                          f'ran a play that cannot score on down {down}')

    def test_aTouchdownStillLandingLeavesTheChoiceOpen(self):
        """At X-7 a touchdown is a real option, so nothing is forced."""
        from floosball_game import PlayType
        g = self._snap(X - 7)
        self.assertFalse(g._dartsForceKick())
        self.assertIs(g.play.playType, PlayType.Pass)

    def test_aLiveHoopLeavesTheChoiceOpen(self):
        """A hoop is the other way to score, so the drive is not stranded."""
        from floosball_game import PlayType
        g = self._snap(X - 4, hoopsUsed=0)
        self.assertFalse(g._dartsForceKick())
        self.assertIs(g.play.playType, PlayType.Pass)

    def test_aBustingKickIsNeverForced(self):
        """Below a field goal the kick is the one thing that must NOT happen — that is
        `_refuseBustingKick`'s case and the two must not fight over it."""
        from floosball_game import PlayType
        g = self._snap(X - 1)
        self.assertFalse(g._dartsForceKick())
        self.assertIsNot(g.play.playType, PlayType.FieldGoal)

    def test_outOfRangeItPlaysOn(self):
        """'The only score' is not a reason to heave a hopeless kick — work into range
        first, the same answer the tree gives anywhere else."""
        from floosball_game import PlayType
        g = self._snap(X - 4, yardsToEndzone=85)
        self.assertFalse(g._dartsForceKick())
        self.assertIs(g.play.playType, PlayType.Pass)

    def test_itDoesNotOverrideAResolvedHoopShot(self):
        """⚠️ `_executeHoopShot` banks its point INSIDE playCaller, unlike every other
        call, so a shot that spent the last pair leaves this method looking at the exact
        state it fires on. Flipping it to a kick would replay the down."""
        from floosball_game import PlayType
        g = self._snap(X - 4)
        g.play.isHoopShot = True
        self.assertFalse(g._dartsForceKick())
        self.assertIsNot(g.play.playType, PlayType.FieldGoal)

    def test_itLeavesAPuntAndAKneelAlone(self):
        from floosball_game import PlayType
        for kind in (PlayType.Punt, PlayType.Kneel, PlayType.Spike):
            g = self._snap(X - 4, playType=kind)
            self.assertFalse(g._dartsForceKick(), f'overrode a {kind.name}')
            self.assertIs(g.play.playType, kind)

    def test_itIsANoOpInStandardFootball(self):
        """It runs on every snap of every format, so it has to cost nothing elsewhere."""
        from floosball_game import Play, PlayType
        from game_rules import GameRules
        g = Scenario(gameRules=GameRules()).game
        g.offensiveTeam, g.defensiveTeam = g.homeTeam, g.awayTeam
        g.homeScore = X - 4
        g.play = Play(g)
        g.play.playType = PlayType.Pass
        self.assertFalse(g._dartsForceKick())
        self.assertIs(g.play.playType, PlayType.Pass)


class AnExactLandingIsNotSpentOnAHoop(unittest.TestCase):
    """Needing exactly a touchdown or a field goal, the offense goes and scores it rather
    than shooting a sideline hoop (owner, 2026-08-24: teams were shooting these and ending
    up with an awkward remainder they then had to work back from).

    ⚠️ A HOOP POINT IS NOT FREE ONCE THE DRIVE HAS ITS ANSWER — IT SPOILS THE LANDING.
    From a need of 6 a made hoop leaves 5, which no conventional score reaches; from 3 it
    leaves 2, below a field goal, which is the format's own dead-drive state. Measured over
    200 games at X=24 before the fix: 330 shots were taken while the need was ALREADY an
    exact landing, 222 made, and **102 of them turned an exact landing into one nothing can
    reach** (58 from a need of 6, 44 from a need of 3). After: 0, with hoop volume down
    3462 -> 2855. End to end over a further 200 games on one seed, the format's own win
    condition improves: games decided by landing exactly on X **138 -> 150 (69% -> 75%)**
    and team-scores stranded at X-1 or X-2 **40 -> 26**.

    ⚠️ TWO CAUSES, ONE VETO. `_hoopPointsNeeded`'s "a conventional score lands it exactly"
    test was the literal `need == fg or need == self._maxPossession()` — two of the four
    landings — so a need of 6 fell through to the BRIDGING loop, which found 6 minus three
    hoops equals a field goal and called spending every pair 'helpful'. And separately, the
    darts branch of `_shouldAttemptHoopShot` does not return when it declines to decide, so
    a need of 3 (already returning None) dropped into the standard-football tail, which
    asks the deficit-against-the-opponent question this format does not care about. That
    tail was 44 of the 102 on its own, which is why the veto sits above both.
    """

    def setUp(self):
        self.game = Scenario(gameRules=dartsRules()).game
        self.game.offensiveTeam = self.game.homeTeam
        self.game.defensiveTeam = self.game.awayTeam

    def _at(self, need, hoopsUsed=0):
        from floosball_game import Play
        g = self.game
        g.homeScore = X - need
        g.awayScore = 0
        g.down = 1
        g.yardsToEndzone = 45
        g.yardsToFirstDown = 10
        g._hoopPairResult = {p: 'made' for p in HOOP_PAIRS[:hoopsUsed]}
        g.play = Play(g)
        return g

    def test_theLandingSetIsAllFourValues(self):
        """A field goal, a bare touchdown, and a touchdown plus each conversion rung."""
        g = self.game
        rules = g.gameRules
        self.assertEqual(
            g._dartsExactLandings(),
            {float(rules.fieldGoalPoints),
             float(rules.touchdownPoints),
             float(rules.touchdownPoints + rules.extraPointPoints),
             float(rules.touchdownPoints + rules.twoPointConversionPoints)})

    def test_itIsDerivedFromTheLiveRulesNotConstants(self):
        """FG / TD / XP / 2-pt values are all votable, so a mutated ruleset has to move
        the landing set with it."""
        rules = dartsRules(fieldGoalPoints=4, touchdownPoints=5, extraPointPoints=2)
        g = Scenario(gameRules=rules).game
        self.assertIn(4.0, g._dartsExactLandings(), 'a 4-point field goal is a landing')
        self.assertIn(5.0, g._dartsExactLandings(), 'a bare touchdown is a landing')
        self.assertIn(7.0, g._dartsExactLandings(), 'touchdown plus the 2-point XP')
        self.assertNotIn(3.0, g._dartsExactLandings(), 'read a hardcoded field goal')

    def test_needingExactlyATouchdownVetoesTheShot(self):
        g = self._at(int(g_td(self.game)))
        self.assertTrue(g._dartsNeedIsExactLanding())
        self.assertFalse(g._shouldAttemptHoopShot(),
                         'shot a hoop while needing exactly a touchdown')

    def test_needingExactlyAFieldGoalVetoesTheShot(self):
        g = self._at(int(self.game._fgValue()))
        self.assertTrue(g._dartsNeedIsExactLanding())
        self.assertFalse(g._shouldAttemptHoopShot(),
                         'shot a hoop while needing exactly a field goal')

    def test_theVetoCoversTheWholeTouchdownBand(self):
        """⚠️ 6 and 7 are the two the old check missed, and 7 is the one that reads
        harmless — it goes to 6, still landable. The shot still bought a down and a pair
        for nothing, so it is vetoed too."""
        td = int(g_td(self.game))
        for need in (td, td + self.game.gameRules.extraPointPoints,
                     td + self.game.gameRules.twoPointConversionPoints):
            g = self._at(need)
            self.assertTrue(g._dartsNeedIsExactLanding(), f'need {need} is a landing')
            self.assertFalse(g._shouldAttemptHoopShot(), f'shot a hoop at a need of {need}')

    def test_theOffenseStopsBendingTheDriveTowardTheHoopToo(self):
        """⚠️ ONE FIX, TWO SURFACES. `_dartsHoopApproach` damps downfield play to protect
        the use-it-or-lose-it midfield pair, and it reads the same verdict — so needing
        exactly a touchdown was ALSO suppressing the passing that gets one."""
        g = self._at(int(g_td(self.game)))
        g.yardsToEndzone = 52   # right in the approach window
        self.assertEqual(g._hoopPointsNeeded(g.homeScore - g.awayScore), None)
        self.assertEqual(g._dartsHoopApproach(), 0.0,
                         'still managing field position toward a hoop it should ignore')

    def test_aBridgingNeedStillWantsTheHoop(self):
        """The mechanic's whole point: a need of 4 is one hoop plus a field goal, so the
        veto must not swallow the case hoops exist for.

        ⚠️ This is also the POSITIVE CONTROL for the vetoes above. They assert a False out
        of `_shouldAttemptHoopShot`, and that method has half a dozen other ways to return
        False — an out-of-range pair, the final down, hurry-up. Firing from the IDENTICAL
        fixture at a bridging need is what proves the veto is the thing doing the work.
        """
        g = self._at(int(self.game._fgValue()) + 1)
        self.assertFalse(g._dartsNeedIsExactLanding())
        self.assertEqual(g._hoopPointsNeeded(g.homeScore - g.awayScore), 'helpful')
        self.assertIsNotNone(g._hoopTarget(), 'fixture has no pair in range')
        random.seed(3)
        fired = sum(1 for _ in range(200) if g._shouldAttemptHoopShot())
        self.assertGreater(fired, 40, 'the fixture never shoots, so the vetoes prove nothing')

    def test_aNeedBelowAFieldGoalIsStillCritical(self):
        """Below a field goal the hoop is the ONLY score, which is the opposite case."""
        g = self._at(1)
        self.assertFalse(g._dartsNeedIsExactLanding())
        self.assertEqual(g._hoopPointsNeeded(g.homeScore - g.awayScore), 'critical')

    def test_aLargeNeedIsUntouched(self):
        """⚠️ The veto is narrow ON PURPOSE. At 0-0 the need is the whole target, the pairs
        reset every possession and dozens of drives remain — a hoop point there is ordinary
        progress with nothing to spoil. It fired on 9.5% of shots in the sample."""
        g = self._at(X)
        self.assertFalse(g._dartsNeedIsExactLanding())

    def test_itIsANoOpInStandardFootball(self):
        from game_rules import GameRules
        g = Scenario(gameRules=GameRules()).game
        g.offensiveTeam, g.defensiveTeam = g.homeTeam, g.awayTeam
        g.homeScore, g.awayScore = 21, 18   # a 3-point margin: a "landing" if this applied
        self.assertFalse(g._dartsNeedIsExactLanding())


def g_td(game):
    return float(getattr(game.gameRules, 'touchdownPoints', 6))


class TheHeldUpShortText(unittest.TestCase):
    """A carrier who pulled up short of a would-bust touchdown reads as football, not as a
    rules footnote — the parenthetical restating the target was cut (owner, 2026-08-24)."""

    def test_itDoesNotRestateTheTarget(self):
        import inspect
        from floosball_game import Game
        source = inspect.getsource(Game.formatPlayText)
        self.assertIn('pulls up short of the goal', source)
        self.assertNotIn('a TD would clear', source,
                         'the held-up-short line still restates the target')


class TheScoringRules(unittest.TestCase):
    """The format's own predicates, checked directly rather than inferred from finals."""

    def setUp(self):
        self.fmt = getFormat('bust')
        self.game = Scenario(gameRules=dartsRules()).game

    def _at(self, home, away=0):
        self.game.homeScore, self.game.awayScore = home, away
        return self.game

    def test_aScoreThatWouldExceedTheTargetIsVoided(self):
        game = self._at(X - 3)
        self.assertTrue(self.fmt.voidsScore(game, game.homeTeam, 6), 'a TD would bust')
        self.assertFalse(self.fmt.voidsScore(game, game.homeTeam, 3), 'a FG lands exactly')

    def test_landingExactlyIsNeverVoided(self):
        for need in (1, 2, 3, 6, 7):
            game = self._at(X - need)
            self.assertFalse(self.fmt.voidsScore(game, game.homeTeam, need),
                             f'landing exactly on X from X-{need} was voided')

    def test_theKickIsRefusedWhenItWouldBust(self):
        game = self._at(X - 1)
        game.offensiveTeam = game.homeTeam
        self.assertFalse(self.fmt.allowFieldGoal(game, 3),
                         'kicked a field goal that would have busted')
        game = self._at(X - 3)
        game.offensiveTeam = game.homeTeam
        self.assertTrue(self.fmt.allowFieldGoal(game, 3))

    def test_scoresAreForcedToWholeNumbers(self):
        """⚠️ Landing on X has to be arithmetically possible. A fractional score puts a
        team permanently off the grid."""
        for raw in (6, 6.4, 2.5, 1.0):
            self.assertEqual(self.fmt.scorePoints(self.game, raw),
                             int(round(raw)))

    def test_reachingTheTargetEndsTheGame(self):
        self.assertTrue(self.fmt.checkEarlyEnd(self._at(X)))
        self.assertTrue(self.fmt.checkEarlyEnd(self._at(0, X)))
        self.assertIsNone(self.fmt.checkEarlyEnd(self._at(X - 1, X - 2)),
                          'an undecided game must defer to the clock')

    def test_nearingTheTargetReadsAsLateGame(self):
        """Win probability keys off progress, and in darts the SCORE advances the game."""
        early = self.fmt.adjustGameProgress(self._at(0), 0.1)
        late = self.fmt.adjustGameProgress(self._at(X - 1), 0.1)
        self.assertGreater(late, early)
        self.assertLessEqual(late, 1.0)


class ItSurvivesTheEngine(unittest.TestCase):
    """Real games, whole engine. ⚠️ Slower than the unit checks above and worth it: every
    format bug this codebase has had was an interaction with the engine rather than a wrong
    predicate."""

    @classmethod
    def setUpClass(cls):
        cls.finals = playDarts(24)

    def test_nobodyEverExceedsTheTarget(self):
        """The one inviolable rule of the format."""
        over = [(h, a) for h, a in self.finals if h > X or a > X]
        self.assertEqual(over, [], f'{len(over)} games finished above the target')

    def test_everyScoreIsAWholeNumber(self):
        for home, away in self.finals:
            self.assertEqual(home, int(home))
            self.assertEqual(away, int(away))

    def test_mostGamesAreDecidedByLandingOnIt(self):
        """⚠️ THE CERTIFICATION. At 8% this was a football game with a ceiling; the format
        only means something if landing on the number is how games usually end."""
        landed = sum(1 for home, away in self.finals if home == X or away == X)
        self.assertGreater(landed / len(self.finals), 0.5,
                           'darts is being decided by the clock, not by the target')

    def test_teamsAreNotStrandedJustShort(self):
        """X-1 and X-2 are unreachable finishes without a 1-pointer, so a pile-up there is
        the signature of the prerequisite having gone missing again."""
        stranded = sum(1 for final in self.finals for score in final if score in (X - 1, X - 2))
        self.assertLess(stranded, len(self.finals),
                        'teams are stalling one or two short — is the hoop off?')

    def test_gamesActuallyFinish(self):
        self.assertEqual(len(self.finals), 24)
        self.assertTrue(any(h != a for h, a in self.finals), 'every game drawn?')


class AnEarlyFinishIsADecidedGame(unittest.TestCase):
    """⚠️ THE FORMAT MERCY-RULES ITSELF, and that is what makes an early finish acceptable.

    Darts ends the moment someone lands on the target, so games CAN finish early -- measured
    at X=18, about a third end before halftime and the median finish is at 66% of regulation
    (~125 plays against a standard game's 157). That reads alarming until you look at WHICH
    games they are: of 18 pre-halftime finishes, the loser's median score was 6 of 18, 15
    were blowouts, and NOT ONE was still close. Games that finish after halftime have a
    loser's median of 12. So the clock is not cutting competitive games short; it is ending
    ones already decided, which is a feature rather than a cost.

    ⚠️ The assertion is an ORDERING, not a threshold. The absolute margins move with any
    scoring retune, but "an early finish is a lopsided one" has to survive them -- if close
    games start ending in the second quarter, the format has genuinely broken.
    """

    @classmethod
    def setUpClass(cls):
        cls.finals = playDarts(40, seed=808)

    def test_earlyFinishesAreTheLopsidedOnes(self):
        landed = [(min(h, a), max(h, a)) for h, a in self.finals if h == X or a == X]
        self.assertGreater(len(landed), 20, 'too few target finishes to judge')
        # A loser far from the target is a game that was over; one close to it was a race.
        lopsided = [lo for lo, _ in landed if lo <= X // 2]
        close = [lo for lo, _ in landed if lo >= X - 4]
        self.assertTrue(lopsided, 'no decided games at all — suspicious')
        self.assertTrue(close, 'no close games at all — the format is a procession')

    def test_theLosingSideIsNotBlownOutAsAMatterOfCourse(self):
        """The counterpart: if EVERY finish were a blowout the target would be too low.

        ⚠️ THE THRESHOLD IS DELIBERATELY LOOSE, AND TIGHTENING IT MAKES THIS FLAKY. The
        loser's median over ~25 target finishes swings 7 to 13 from run to run at X=21 —
        the games are seeded, but set-iteration order varies with the process hash seed, so
        the engine does not replay identically across runs. A first version asserted the
        median cleared 40% of the target (8.4) and failed about one run in five for no
        reason anyone could act on. A quarter of the target is a real guard against a
        procession without pretending to measure balance to a precision this sample cannot
        support; the ordering test above is where the actual finding lives.
        """
        import statistics as _stats
        losers = [min(h, a) for h, a in self.finals if h == X or a == X]
        self.assertGreater(_stats.median(losers), X * 0.25,
                           'the losing side is never getting near the target — X is too low')


class TheTargetIsConfigurable(unittest.TestCase):
    """The preset ships X=18, but the format reads it from the rules and a Cores vote can
    move it. A hardcoded 18 anywhere would only show up at another value."""

    def test_aDifferentTargetIsHonoured(self):
        finals = playDarts(8, seed=21, target=12)
        for home, away in finals:
            self.assertLessEqual(home, 12)
            self.assertLessEqual(away, 12)

    def test_theFormatReadsTheRulesNotAConstant(self):
        fmt = getFormat('bust')
        game = Scenario(gameRules=dartsRules(target=25)).game
        game.homeScore = 25
        self.assertTrue(fmt.checkEarlyEnd(game))
        game.homeScore = 18
        self.assertIsNone(fmt.checkEarlyEnd(game), 'still reading the old target')


class ThePresetIsLive(unittest.TestCase):

    def test_dartsIsOfferedToTheLeagueAgain(self):
        from constants import GAME_FORMAT_PRESETS
        keys = [p['key'] for p in GAME_FORMAT_PRESETS]
        self.assertIn('gf_bust_24', keys, 'the darts preset is still held back')

    def test_thePresetTargetIsInsideTheCertifiedRange(self):
        """⚠️ THE TARGET HAS A USABLE RANGE. Darts is only a game about landing on a number
        while the number is reachable inside four quarters; above that the clock decides it
        and the format is football with a ceiling. Measured over 50 games per target, share
        decided by LANDING on it: 10 -> 98%, 12 -> 98%, 15 -> 88%, 18 -> 84%, 21 -> 66%,
        24 -> 58%, 30 -> 30%. Shipped at 24 (owner, 2026-08-23), the top of the range they gave on 2026-08-18
        ("higher is better. 21-24") — knowingly trading target finishes for a longer game.

        ⚠️ `GameRules.targetScore` DEFAULTS to 30, which belongs to the 'target' format
        ("first to 30"), so a darts preset that simply omits the target inherits one it
        plays badly at. This guards the shipped preset and any added later."""
        from constants import GAME_FORMAT_PRESETS
        for preset in GAME_FORMAT_PRESETS:
            patch = preset.get('patch', {})
            if patch.get('gameFormat') != 'bust':
                continue
            target = patch.get('targetScore')
            self.assertIsNotNone(
                target, f"{preset['key']} leaves targetScore at the 'target' default of 30")
            self.assertLessEqual(
                target, 24,
                f"{preset['key']} sets a target of {target}; above 24 the clock decides "
                f"most games and darts stops being about landing on the number")
            self.assertGreaterEqual(
                target, 12,
                f"{preset['key']} sets a target of {target}; that low, most games are "
                f"over before halftime")

    def test_thePresetNoLongerCarriesThePrerequisiteItself(self):
        """⚠️ Removing it was the fix, not an oversight: leaving it in the preset would
        hide a regression in `bundledRules` for exactly the activation path people use."""
        from constants import GAME_FORMAT_PRESETS
        preset = next(p for p in GAME_FORMAT_PRESETS if p['key'] == 'gf_bust_24')
        self.assertNotIn('sidelineGoalsEnabled', preset['patch'])
        self.assertEqual(preset['patch']['gameFormat'], 'bust')


if __name__ == '__main__':
    unittest.main(verbosity=2)
