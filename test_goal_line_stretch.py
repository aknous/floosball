"""Reaching for the goal line: the right words, and every carrier can do it.

`_stretchForFirst` already aimed at whichever line is closer (marker or goal), but
two things around it were wrong:

- a FAILED reach at the goal line read "lunges for the marker but comes up just
  short" — the marker is the first-down line, and there is none to reach for on a
  play that just ended at the 1;
- a SCRAMBLING quarterback never reached at all. Both carrier tails (the run and the
  catch) call the stretch; `_resolveQbScramble` called neither, so a scramble ending
  at the 1 simply stopped there.

Measured over 300 games after: scrambles produced 4 converted reaches and 8 that came
up short, and 87 failed goal-line reaches now name the goal line.

Run: .venv/bin/python test_goal_line_stretch.py
"""
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import logging
logging.disable(logging.CRITICAL)

import managers  # noqa: F401  — breaks the floosball_game circular import
import floosball_game as fg

HERE = os.path.dirname(os.path.abspath(__file__))


class Attrs:
    def __init__(self, power=80):
        self.power = power


class Carrier:
    def __init__(self, power=80):
        self.gameAttributes = Attrs(power)
        self.attributes = Attrs(power)
        self.name = 'Carrier'


class StubGame:
    def __init__(self, yardsToFirstDown):
        self.yardsToFirstDown = yardsToFirstDown


class StubPlay:
    """Only what `_stretchForFirst` reads. The mental terms are pinned so the note,
    not the roll, is what each case is testing."""

    _stretchForFirst = fg.Play._stretchForFirst

    def __init__(self, *, yardage, yardsToEndzone, yardsToFirstDown, confidence=1.0):
        self.yardage = yardage
        self.yardsToEndzone = yardsToEndzone
        self.game = StubGame(yardsToFirstDown)
        self.isTd = False
        self._c = confidence

    def _confidenceState(self, p):
        return self._c

    def _determinationState(self, p):
        return 0.0

    def _flair(self, p):
        return 0.5

    def _undiscipline(self, p):
        return 0.0


def noteFor(**kw):
    """The note only — `alwaysMake` decides whether the roll is beaten."""
    make = kw.pop('make', True)
    play = StubPlay(**kw)
    real = fg.batched_randint
    fg.batched_randint = lambda a, b: (1 if make else 100)
    try:
        return play._stretchForFirst(Carrier())[1]
    finally:
        fg.batched_randint = real


class StretchNoteTests(unittest.TestCase):
    def testAMissedGoalLineReachNamesTheGoalLine(self):
        self.assertEqual(
            noteFor(yardage=3, yardsToEndzone=4, yardsToFirstDown=4, make=False),
            'stretch_short_goal')

    def testAMissedMarkerReachStillNamesTheMarker(self):
        self.assertEqual(
            noteFor(yardage=3, yardsToEndzone=40, yardsToFirstDown=5, make=False),
            'stretch_short')

    def testTheMadeNotesAreUnchanged(self):
        self.assertEqual(noteFor(yardage=3, yardsToEndzone=4, yardsToFirstDown=4), 'stretch_goal')
        self.assertEqual(noteFor(yardage=3, yardsToEndzone=40, yardsToFirstDown=5), 'stretch_first')

    def testACarrierDrivenBackwardsDoesNotReach(self):
        """The window is measured off where the play ENDED, so a man tackled for a
        loss two yards out was still inside it — "is dropped for -1 yards, and
        reaches for the goal line". He is going the wrong way. Measured: 38 such
        reaches per 300 games before, 0 after."""
        self.assertIsNone(noteFor(yardage=-1, yardsToEndzone=1, yardsToFirstDown=1))
        self.assertIsNone(noteFor(yardage=-2, yardsToEndzone=0, yardsToFirstDown=8))

    def testANoGainStillReaches(self):
        """Stopped at the spot, not pushed off it — he can still extend. Measured
        at 132 such reaches per 300 games, deliberately kept."""
        self.assertEqual(noteFor(yardage=0, yardsToEndzone=1, yardsToFirstDown=1), 'stretch_goal')

    def testEveryNoteHasItsOwnSentence(self):
        """A note with no text in the map appends nothing, so the reach happens
        silently — the failure that is invisible by construction."""
        src = open(os.path.join(HERE, 'floosball_game.py')).read()
        block = src[src.index("_stNote = getattr(self.play, '_stretchNote', None)"):][:900]
        for note in ('stretch_first', 'stretch_goal', 'stretch_short', 'stretch_short_goal'):
            self.assertIn(f"'{note}':", block)
        self.assertIn('goal line but comes up just short', block)


class ScrambleTests(unittest.TestCase):
    def testTheScrambleReachesToo(self):
        src = open(os.path.join(HERE, 'floosball_game.py')).read()
        body = re.search(r'    def _resolveQbScramble\(.*?\n    def ', src, re.S).group(0)
        self.assertIn('_stretchForFirst(self.passer)', body)
        # The bonus has to reach the CREDITED yardage, not just `self.yardage`.
        self.assertIn('yds = self.yardage', body)
        self.assertLess(body.index('_stretchForFirst'), body.index('addRushYards'))

    def testTheReachesFumbleRiskRidesTheScrambleRoll(self):
        src = open(os.path.join(HERE, 'floosball_game.py')).read()
        body = re.search(r'    def _resolveQbScramble\(.*?\n    def ', src, re.S).group(0)
        self.assertIn('QB_SCRAMBLE_FUMBLE_CHANCE - _stFumbleBump', body)


if __name__ == '__main__':
    unittest.main(verbosity=2)
