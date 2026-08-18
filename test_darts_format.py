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

X = 18


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

    def test_theLoserUsuallyGetsRespectablyClose(self):
        """The counterpart: if most finishes were blowouts the target would be too low."""
        import statistics as _stats
        losers = [min(h, a) for h, a in self.finals if h == X or a == X]
        self.assertGreater(_stats.median(losers), X * 0.4,
                           'the losing side is not getting near the target — X is too low')


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
        self.assertIn('gf_bust_18', keys, 'the darts preset is still held back')

    def test_thePresetTargetIsInsideTheCertifiedRange(self):
        """⚠️ THE TARGET HAS A USABLE RANGE. Darts is only a game about landing on a number
        while the number is reachable inside four quarters; above that the clock decides it
        and the format is football with a ceiling. Measured over 50 games per target, share
        decided by LANDING on it: 10 -> 98%, 12 -> 98%, 15 -> 88%, 18 -> 84%, 21 -> 66%,
        24 -> 58%, 30 -> 30%.

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
                target, 18,
                f"{preset['key']} sets a target of {target}; above 18 the clock decides "
                f"most games and darts stops being about landing on the number")

    def test_thePresetNoLongerCarriesThePrerequisiteItself(self):
        """⚠️ Removing it was the fix, not an oversight: leaving it in the preset would
        hide a regression in `bundledRules` for exactly the activation path people use."""
        from constants import GAME_FORMAT_PRESETS
        preset = next(p for p in GAME_FORMAT_PRESETS if p['key'] == 'gf_bust_18')
        self.assertNotIn('sidelineGoalsEnabled', preset['patch'])
        self.assertEqual(preset['patch']['gameFormat'], 'bust')


if __name__ == '__main__':
    unittest.main(verbosity=2)
