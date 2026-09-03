"""A defensive score does not hand the ball back to the team that scored.

⚠️ REPRODUCES PRODUCTION GAME 1630 (Sand Dollars 81, Strangers 10), reported by a user.
`Game.turnover(offense, defense, ...)` means "this side is handing the ball over", and on a
defensive touchdown the engine passes the SCORING team as the giver -- correct for standard
football, where the team that just scored kicks off. Innings reads `giver` as "whose at-bat
this is", and on a pick-six those are opposite teams, so the scorer kept batting inside the
other team's half:

    i2 bottom try1  NYS 20   Turnover! ... picked off ... Pick six!
    i2 bottom try2  SND 20   Bernie Plackett takes the pitch ...

VALIDATED END TO END, not just here. Two arms of a forced-innings season, 463 games each,
instrumented at `Game.turnover` to ask the user's own question -- after a defensive score, is
the team on offense the one the inning half says is batting?

    WITHOUT the fix   3 defensive scores in innings  ->  3 gave the ball back wrongly
    WITH the fix      5 defensive scores in innings  ->  0

⚠️ IT FAILS BOTH WAYS, which is why the fix reads the half rather than patching the caller.
Game 180 of the broken arm flipped the at-bat and then handed the ball to the team that had
just finished batting (scorer WAS, on offense STL, should have been WAS) -- the mirror of the
reported symptom, from the same cause.

⚠️ AND THE FIRST VERSION OF THAT HARNESS LIED TWICE, both worth knowing before rebuilding it.
`self.play` is ALREADY THE CONVERSION when `turnover()` runs -- `_attemptConversion` replaces
it -- so keying the probe off `play.isTd` found ZERO defensive scores across 8,250 innings
turnovers. And judging against the half read BEFORE the call reports a legitimate third-out
flip as a violation. The signature is the argument order; the verdict is the post-call half.

⚠️ FORCING A FORMAT LOCALLY ALSO NEEDS THE SEASON STAMP. `tools_force_format.py` writes
`rule_overrides` but not `rule_overrides_season`, so season start takes the branch that
writes the stamp itself -- and that write raced the shared session and died with "database is
locked" before a single game ran. Stamping it alongside the override skips the branch.

⚠️ THE TEST ASSERTS AGAINST THE HALF, NOT AGAINST THE ARGUMENTS. Checking that the return
differs from the giver would pass for the wrong reason the moment somebody "fixed" it by
swapping the call site; who bats in the bottom of an inning is a rule, and that is what is
pinned.
"""
import unittest
from game_formats import InningsFormat


class _Team:
    def __init__(self, abbr):
        self.abbr = abbr
        self.name = abbr


class _Game:
    """Only what the possession gate touches."""
    def __init__(self, half='bottom', tries=0):
        self.homeTeam = _Team('NYS')      # bats in the BOTTOM
        self.awayTeam = _Team('SND')      # bats in the TOP
        self.homeScore = self.awayScore = 0
        self.currentQuarter = 1
        self.gameFeed = []
        self._inningsHalf = half
        self._inningsTries = tries
        self._inningsNumber = 2
        self._inningsContinue = False
        self._inningsContinues = 0

        class _R:
            inningsPerGame = 3
            triesPerInning = 3
        self.gameRules = _R()

    def _maybeReadjustGameplans(self, _why):
        pass


class DefensiveScoreDoesNotStealTheAtBat(unittest.TestCase):
    def setUp(self):
        self.fmt = InningsFormat()

    def testThePickSixDoesNotPutTheScorerOnOffense(self):
        """The exact production sequence: bottom of the inning, home batting, away scores."""
        g = _Game(half='bottom', tries=0)
        # The engine's defensive-score call: the SCORER gives, the scored-on side receives.
        got = self.fmt.possessionReceiver(g, g.awayTeam, g.homeTeam)
        self.assertIs(got, g.homeTeam,
                      'the scoring team kept batting inside the other team\'s at-bat')

    def testItSpendsTheBattingTeamsTryNotTheScorers(self):
        g = _Game(half='bottom', tries=0)
        self.fmt.possessionReceiver(g, g.awayTeam, g.homeTeam)
        self.assertEqual(g._inningsTries, 1, 'a turnover is an out against the batting team')
        self.assertEqual(g._inningsHalf, 'bottom', 'the at-bat should not have flipped yet')

    def testTheThirdOutStillFlipsTheAtBat(self):
        """⚠️ The fix must not make the at-bat un-endable. On the last try the ball goes to
        the OTHER team, whichever way the arguments came in."""
        g = _Game(half='bottom', tries=2)
        got = self.fmt.possessionReceiver(g, g.awayTeam, g.homeTeam)
        self.assertIs(got, g.awayTeam)
        self.assertEqual(g._inningsHalf, 'top')
        self.assertEqual(g._inningsTries, 0)

    def testAPlainTurnoverIsUnchanged(self):
        """The control from the same production game: an interception with no score, where
        the giver genuinely IS the batting team, always worked and must keep working."""
        g = _Game(half='bottom', tries=1)
        got = self.fmt.possessionReceiver(g, g.homeTeam, g.awayTeam)
        self.assertIs(got, g.homeTeam)
        self.assertEqual(g._inningsTries, 2)

    def testTheTopOfTheInningIsTheMirror(self):
        """Away bats in the top, so a home pick-six there must not steal the at-bat either."""
        g = _Game(half='top', tries=0)
        got = self.fmt.possessionReceiver(g, g.homeTeam, g.awayTeam)
        self.assertIs(got, g.awayTeam)
        self.assertEqual(g._inningsHalf, 'top')


if __name__ == '__main__':
    unittest.main(verbosity=2)
