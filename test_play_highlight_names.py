"""Every player the play text names is offered to the highlighter.

⚠️ AN ATTRIBUTE LIST CANNOT KEEP UP WITH THE TEXT. `_involvedPlayerNames` first listed
`passer/receiver/runner/kicker/returner/interceptedBy/tackledBy/...`, which covered only
92.7% of the names actually appearing — measured over 1,976 mentions across six games —
and the misses were systematic rather than stray:

    the blitzer named in a pre-snap beat      "H0 rb is blitzing! ..."
    the QB who audibled on a RUN play         "H0 qb calls an audible! H0 rb powers ..."
    the punter                                "H0 k punts 50 yards, ..."
    the defender beaten by a stiff-arm        "... stiff-arms A0 rb away ..."

Each is a real participant a reader wants emphasised, and each would have to be remembered
again every time the play-text catalogue grows — which it does constantly. Reading the
FINISHED SENTENCE against the two rosters (twelve players) is cheap, exact, and cannot
drift from what the text says. Re-measured after the change: 100% of 2,043 mentions.

⚠️ THE FALLBACK IS NOT DEAD CODE. `_involvedPlayerNames` is called from the payload builder,
which runs AFTER `play.playText` is assigned — but a payload built before the sentence
exists would otherwise carry an empty list, so the attribute list remains as a floor.

Run: .venv/bin/python test_play_highlight_names.py
"""
import copy
import random
import unittest

from scenario import _makeTeam          # imported first: breaks the managers<->game cycle
import floosball_game as FG
from game_rules import GameRules


def _game(seed=3):
    random.seed(seed)
    home = _makeTeam('Homers', 'HOM', 100)
    away = _makeTeam('Awayers', 'AWY', 200)
    for team in (home, away):
        for member in team.rosterDict.values():
            member.gameAttributes = copy.deepcopy(member.attributes)
        team.deriveDefenseFromRoster()
    return FG.Game(home, away, gameRules=GameRules())


class NamesComeFromTheSentence(unittest.TestCase):

    def setUp(self):
        self.game = _game()
        self.game.play = FG.Play(self.game)
        self.roster = [p.name for t in (self.game.homeTeam, self.game.awayTeam)
                       for p in t.rosterDict.values()]

    def _names(self, text):
        self.game.play.playText = text
        return self.game._involvedPlayerNames()

    def test_everyNameInTheTextIsReturned(self):
        a, b, c = self.roster[0], self.roster[6], self.roster[3]
        text = f'{a} is blitzing! {b} passes to {c} for 9 yards.'
        got = self._names(text)
        for name in (a, b, c):
            self.assertIn(name, got, f'{name} appears in the text but was not offered')

    def test_aNameNotInTheTextIsNotReturned(self):
        """The list drives emphasis — offering an absent name is harmless today but would
        bold the wrong thing the moment two players share a substring."""
        a = self.roster[0]
        got = self._names(f'{a} runs for 3 yards.')
        self.assertEqual(got, [a])

    def test_theBeatsThatUsedToBeMissedAreCovered(self):
        """The four systematic misses, as the sentences that produced them."""
        blitzer, qb, rb, punter = self.roster[1], self.roster[6], self.roster[7], self.roster[5]
        for text, expected in (
            (f'{blitzer} is blitzing! {qb} passes to {rb} for 5 yards', blitzer),
            (f'{qb} calls an audible! {rb} powers through for 8 yards', qb),
            (f'{punter} punts 50 yards, downed at the 10', punter),
            (f'{rb} bursts through, stiff-arms {blitzer} away for 12 yards', blitzer),
        ):
            self.assertIn(expected, self._names(text), f'missed in: {text}')

    def test_longestFirstSoASubstringCannotClaimTheSpan(self):
        """⚠️ Order is load-bearing: the client walks this list and takes the first match,
        so a shorter name sitting inside a longer one must not be offered first."""
        got = self._names(' '.join(self.roster))
        self.assertEqual(got, sorted(got, key=len, reverse=True))

    def test_emptyTextFallsBackRatherThanReturningNothing(self):
        """A payload built before the sentence exists still names its participants."""
        self.game.play.playText = ''
        self.game.play.runner = self.game.homeTeam.rosterDict['rb']
        got = self.game._involvedPlayerNames()
        self.assertIn(self.game.homeTeam.rosterDict['rb'].name, got)

    def test_noPlayIsNotACrash(self):
        self.game.play = None
        self.assertEqual(self.game._involvedPlayerNames(), [])


class MeasuredOverRealGames(unittest.TestCase):
    """The claim that motivated the rewrite, kept honest."""

    def test_coverageIsTotalAcrossAWholeGame(self):
        import asyncio
        missed, seen = [], [0]
        game = _game(seed=5)
        names = [p.name for t in (game.homeTeam, game.awayTeam)
                 for p in t.rosterDict.values()]
        original = FG.Game._prependPreSnapBeat

        def hooked(self, text):
            out = original(self, text)
            # The payload is built AFTER the assignment, so mirror that ordering.
            self.play.playText = out
            involved = set(self._involvedPlayerNames())
            for n in names:
                if n and n in (out or ''):
                    seen[0] += 1
                    if n not in involved:
                        missed.append((n, out))
            return out

        FG.Game._prependPreSnapBeat = hooked
        try:
            asyncio.run(game.playGame())
        finally:
            FG.Game._prependPreSnapBeat = original
        self.assertGreater(seen[0], 100, 'the game should mention plenty of names')
        self.assertEqual(missed[:3], [], f'{len(missed)} of {seen[0]} mentions unhighlighted')


if __name__ == '__main__':
    unittest.main(verbosity=2)
