"""A punt cannot land past the goal line.

⚠️ REPORTED FROM A LIVE GAME: "5th & Goal, STL 5 — Newt Bleeze punts 15 yards, downed at
the -10." There is no -10 yard line.

The clamp was written the wrong way round:

    dist = max(15, min(dist, yardsToEndzone - 1))

From the opponent's 5 that is `min(dist, 4)` = 4, then `max(15, 4)` = 15 — the floor
overrides the field and INVENTS ten yards of grass. Every field position inside the 15 came
out negative: yte 5 -> -10, yte 8 -> -7, yte 12 -> -3.

A punt does have a floor -- nobody deliberately shanks it three yards -- but the floor can
never beat the field. Past the goal line there is nothing to land on, so a punt that reaches
it is a TOUCHBACK, which is what really happens and what the call site and the play text
already knew how to render.

⚠️ The same statement also appeared TWICE in a row, which is harmless (it is idempotent) but
is the fingerprint of the edit that broke it.

Run: .venv/bin/python test_punt_short_field.py
"""
import logging
import unittest

logging.disable(logging.CRITICAL)

from scenario import Scenario


def kickerAndGame():
    game = Scenario().game
    return game, game.homeTeam.rosterDict['k']


def landingFor(game, kicker, yardsToEndzone):
    """What the CALL SITE would record — it forces a touchback to land at 0."""
    dist, puntType, result = game.resolvePunt(kicker, yardsToEndzone)
    landing = 0 if result == 'touchback' else yardsToEndzone - dist
    return dist, result, landing


class APuntNeverLandsOffTheField(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.game, cls.kicker = kickerAndGame()

    def test_theReportedPlay(self):
        """THE REGRESSION: from the opponent's 5 it produced a 15-yard punt to the -10.

        ⚠️ A SHANK is a legitimate non-touchback here and always was: that branch returns
        early with `min(randint(...), max(1, yte - 1))` — the field clamp applied LAST,
        which is the correct order. It is the main path that had it backwards. So the
        assertion is that the ball lands ON the field, not that every punt is a touchback."""
        for _ in range(300):
            dist, result, landing = landingFor(self.game, self.kicker, 5)
            self.assertGreaterEqual(landing, 0, f'landed at {landing} ({result})')
            if result != 'touchback':
                self.assertLess(dist, 5,
                                f'{result} punted {dist} yards into a 5-yard field')

    def test_everyFieldPositionLandsOnTheField(self):
        for yardsToEndzone in range(1, 100):
            for _ in range(12):
                dist, result, landing = landingFor(self.game, self.kicker, yardsToEndzone)
                self.assertGreaterEqual(
                    landing, 0, f'yte {yardsToEndzone}: landed at {landing}')
                self.assertLessEqual(
                    landing, yardsToEndzone,
                    f'yte {yardsToEndzone}: the ball went backwards to {landing}')

    def test_aPuntNeverTravelsFurtherThanTheFieldInFrontOfIt(self):
        """⚠️ The floor must not override the field — that inversion is the whole bug."""
        for yardsToEndzone in (1, 3, 5, 10, 14, 16, 30):
            for _ in range(20):
                dist, result, _ = landingFor(self.game, self.kicker, yardsToEndzone)
                if result != 'touchback':
                    self.assertLess(dist, yardsToEndzone,
                                    f'yte {yardsToEndzone}: punted {dist} into a '
                                    f'{yardsToEndzone}-yard field without a touchback')

    def test_aShortFieldIsUsuallyATouchback(self):
        """A struck punt from inside the 15 reaches the end zone. The alternative fix —
        clamping the distance down — would give a four-yard punt downed at the 1, which is
        legal and absurd. Shanks are the exception and are field-clamped on their own."""
        for yardsToEndzone in (2, 5, 9, 15):
            results = [landingFor(self.game, self.kicker, yardsToEndzone)[1]
                       for _ in range(60)]
            touchbacks = sum(1 for r in results if r == 'touchback')
            self.assertGreater(touchbacks, len(results) * 0.7,
                               f'yte {yardsToEndzone}: only {touchbacks} touchbacks '
                               f'of {len(results)}')
            self.assertTrue(set(results) <= {'touchback', 'shank'},
                            f'yte {yardsToEndzone} produced {set(results)}')

    def test_normalFieldPositionIsUnchanged(self):
        """⚠️ The counterpart. If this had turned into "always a touchback", punting would
        be broken everywhere it currently works."""
        deep = [landingFor(self.game, self.kicker, 85) for _ in range(40)]
        self.assertTrue(any(result != 'touchback' for _, result, _ in deep),
                        'a punt from deep in own territory should not be a touchback')
        self.assertTrue(all(dist >= 15 for dist, _, _ in deep),
                        'the distance floor should still apply where there is room')

    def test_theDuplicatedClampIsGone(self):
        """The same statement twice was the fingerprint of the edit that broke it."""
        with open('floosball_game.py') as fh:
            body = fh.read().split('def resolvePunt')[1].split('\n    def ')[0]
        self.assertEqual(body.count('dist = max(15, min(dist, yardsToEndzone - 1))'), 0,
                         'the inverted clamp is still present')


if __name__ == '__main__':
    unittest.main(verbosity=2)
