"""A power-of-two playoff field has no byes.

⚠️ THE BYE FLAG WAS HARDCODED. `_freezePlayoffSeeds` stamped `bye: i < 2` — the top two
seeds of each league, always — and its docstring said so. That was right when the field
was six a side. At 32 clubs the top HALF of each league qualifies, so the field is **8 per
league: a power of two, and nobody sits out.**

The bracket challenge read the flag literally and drew a tree with two teams waiting in
round 2, against a real postseason of four clean rounds. Measured on the local database
before the fix: both leagues frozen as "8 qualifiers, byes at seeds [1, 2]".

The rule is the one the seeding already follows — a bye exists only to pad a field up to
the next power of two, so a field that IS one has none. Deriving it means the bracket
follows the league if the qualifier count moves again, which it has once already.

Run: .venv/bin/python test_bracket_byes.py
"""

import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import logging
logging.disable(logging.CRITICAL)

HERE = os.path.dirname(os.path.abspath(__file__))


def _byeCount(n: int) -> int:
    """The derivation as it appears in `_freezePlayoffSeeds`."""
    size = 1
    while size < max(1, n):
        size *= 2
    return size - n


class ByeDerivationTests(unittest.TestCase):
    def testTheCurrentFieldHasNoByes(self):
        """THE REGRESSION. 32 clubs, top half of each 16-club league = 8, a power of two."""
        self.assertEqual(_byeCount(8), 0)

    def testAPowerOfTwoNeverHasByes(self):
        for n in (2, 4, 8, 16):
            self.assertEqual(_byeCount(n), 0, f'field of {n}')

    def testTheOldSixTeamFieldStillGetsItsTwo(self):
        """The hardcoded 2 was not wrong, it was wrong NOW — so the derivation has to
        reproduce it, or this is a rewrite rather than a fix."""
        self.assertEqual(_byeCount(6), 2)

    def testAnOddFieldPadsToTheNextPowerOfTwo(self):
        self.assertEqual(_byeCount(5), 3)
        self.assertEqual(_byeCount(12), 4)

    def testAFieldOfOneIsSafe(self):
        """Guards the loop's `max(1, n)` — a league with a single qualifier must not spin."""
        self.assertEqual(_byeCount(1), 0)
        self.assertEqual(_byeCount(0), 1)


class SourceTests(unittest.TestCase):
    def testTheFlagIsDerivedNotHardcoded(self):
        with open(os.path.join(HERE, 'managers', 'seasonManager.py')) as fh:
            src = fh.read()
        block = re.search(r'def _freezePlayoffSeeds\(.*?\n    def ', src, re.S)
        self.assertIsNotNone(block, '_freezePlayoffSeeds is gone')
        body = block.group(0)
        self.assertNotIn('"bye": i < 2', body,
                         'the bye flag is hardcoded again — a power-of-two field will '
                         'draw a bracket with teams waiting in round 2')
        self.assertIn('_byeCount', body)
        self.assertIn('"bye": i < _byeCount', body)

    def testTheDocstringNoLongerClaimsTwoByes(self):
        """It said "top 2 per conference are byes", which is what sent the next reader
        looking in the wrong place."""
        with open(os.path.join(HERE, 'managers', 'seasonManager.py')) as fh:
            src = fh.read()
        body = re.search(r'def _freezePlayoffSeeds\(.*?\n    def ', src, re.S).group(0)
        self.assertNotIn('top 2 per conference are byes', body)


if __name__ == '__main__':
    unittest.main(verbosity=2)
