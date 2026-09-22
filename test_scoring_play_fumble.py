"""A carrier who breaks the plane has scored, so he cannot also fumble.

Reported from prod game 2923, Q4 1:35: the Strangers went for two and the feed read
"Bitmap Forte runs for 2 yards, Davion Perper forces the fumble, SLC recover" while
booking the try GOOD. The run's fumble check ran after the yardage was final with no
goal-line test, and `_simulateConversionPlay` scores on yardage alone, so the try was
both converted and lost. On a NORMAL down the same roll is worse: the turnover branch
reads the fumble first, so a touchdown run became a touchback.

(The possession that followed, "SLC kicks off" with the Strangers keeping the ball, was
correct: it was a chess-clock game and SLC's budget was spent, so a locked-out team
cannot take the ball.)

The fix gates the natural fumble on the run, the scramble and the catch-and-strip on
the carrier NOT having reached the end zone, holds an awakened strip a yard short of the
line (it is a guaranteed takeaway, so he was stripped before he got in), and refuses to
book a conversion that ended in a lost ball.

These games force the fumble gate open (`_wxFumbleAdjust` always True), so every run and
every in-bounds catch that could fumble does, and every touchdown goes for two.

Run: .venv/bin/python test_scoring_play_fumble.py
"""

import os
import sys
import types
import asyncio
import random
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import logging
logging.disable(logging.CRITICAL)

if 'floosball_game' not in sys.modules:
    _stub = types.ModuleType('floosball_game')
    _stub.Game = type('G', (), {})
    sys.modules['floosball_game'] = _stub
    import managers.timingManager  # noqa: F401
    del sys.modules['floosball_game']

import floosball_game as FG  # noqa: E402
from managers.timingManager import TimingManager, TimingMode  # noqa: E402
from game_rules import GameRules  # noqa: E402
from scenario import _makeTeam  # noqa: E402


def _playGame(index):
    """One full game with fumbles forced and every try a 2-pt run/pass. Each snap's
    raw outcome is recorded straight out of runPlay/passPlay, before the game loop
    rewrites yardage for a defensive return."""
    rr = random.Random(2923 + index)
    home = _makeTeam('H', 'HOM', 1000 + index * 10,
                     phys=rr.randint(74, 92), ment=rr.randint(74, 92))
    away = _makeTeam('A', 'AWY', 5000 + index * 10,
                     phys=rr.randint(74, 92), ment=rr.randint(74, 92))
    game = FG.Game(home, away, gameRules=GameRules(),
                   timingManager=TimingManager(TimingMode.FAST))
    game.id = index
    game._wxFumbleAdjust = lambda happened, threshold: True

    def _goForTwo(scoringTeam, _g=game):
        return next(r for r in _g._conversionRungs() if r['kind'] == 'go')
    game._chooseConversion = _goForTwo

    asyncio.run(asyncio.wait_for(game.playGame(), timeout=120))
    return game


class _Recorder:
    """Wrap Play.runPlay / passPlay for the duration of the tests."""

    def __init__(self):
        self.snaps = []
        self._run = FG.Play.runPlay
        self._pass = FG.Play.passPlay

    def __enter__(self):
        rec = self.snaps
        run, pas = self._run, self._pass

        def runPlay(play, *a, **kw):
            out = run(play, *a, **kw)
            rec.append((play.yardage, play.yardsToEndzone, play.isFumbleLost, play))
            return out

        def passPlay(play, *a, **kw):
            out = pas(play, *a, **kw)
            rec.append((play.yardage, play.yardsToEndzone, play.isFumbleLost, play))
            return out

        FG.Play.runPlay = runPlay
        FG.Play.passPlay = passPlay
        return self

    def __exit__(self, *exc):
        FG.Play.runPlay = self._run
        FG.Play.passPlay = self._pass


class ScoringPlayFumbleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with _Recorder() as rec:
            cls.games = [_playGame(i) for i in range(4)]
        cls.snaps = rec.snaps

    def testTheGateWasActuallyExercised(self):
        """Fumbles forced means plenty of lost balls, and some snaps reach the end zone —
        otherwise nothing below means anything."""
        lost = [s for s in self.snaps if s[2]]
        scored = [s for s in self.snaps if s[0] >= s[1]]
        self.assertGreater(len(lost), 20, 'forced fumbles did not fire')
        self.assertGreater(len(scored), 5, 'no snap reached the end zone')

    def testNoSnapBothReachesTheEndZoneAndLosesTheBall(self):
        """THE REGRESSION: a play that broke the plane is a dead ball."""
        bad = [s for s in self.snaps if s[2] and s[0] >= s[1]]
        self.assertEqual(
            [], bad,
            f'{len(bad)} snap(s) reached the end zone AND lost a fumble: '
            + ' | '.join(getattr(s[3], 'playText', '') or '?' for s in bad[:3]))

    def testNoConversionIsBookedGoodOnALostBall(self):
        good = {FG.PlayResult.Touchdown2PtGood, FG.PlayResult.ConversionGood}
        tries = []
        for game in self.games:
            for entry in game.gameFeed:
                play = entry.get('play') if isinstance(entry, dict) else None
                if play is not None and getattr(play, 'conversionPoints', None):
                    tries.append(play)
        self.assertTrue(tries, 'no conversion was attempted')
        bad = [p for p in tries
               if p.playResult in good
               and (getattr(p, 'isFumbleLost', False) or getattr(p, 'isInterception', False))]
        self.assertEqual([], bad, 'a try was booked Good on a lost ball: '
                         + ' | '.join(p.playText or '?' for p in bad[:3]))


if __name__ == '__main__':
    unittest.main(verbosity=2)
