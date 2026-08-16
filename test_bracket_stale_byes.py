"""A frozen bye flag is not evidence — derive byes from the field size at READ time.

⚠️ `bye` is stamped INTO `seasons.playoff_seeds` when seeding locks, and there is no
backfill. A season seeded before the derived-bye fix therefore carries `bye` on its top
two seeds FOREVER, and the projected tree honors it literally: an 8-club field draws as
**3 round-1 games with the top two seeds sitting out**, against a real postseason of 4
games in which nobody sits out.

That is what "the bracket broke during the playoffs" looks like from the outside. The
fill-out UI offers three round-1 picks per league instead of four, and then the moment
round 1 resolves and four actual winners come back, the tree reshapes into something
the user never filled in.

⚠️ Scoring was NOT affected — `scoreBracket` pays per advancer and is re-seeding
agnostic — but users could only enter three round-1 picks where four were available, so
the points they could earn were capped by the display.

Deriving at read time fixes the season already frozen, which a code fix at freeze time
cannot, and keeps following the league if the qualifier count moves again (it has moved
once: 6 a side -> 8).

Run: .venv/bin/python test_bracket_stale_byes.py
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import playoff_bracket as pb  # noqa: E402


def field(n, staleByes=True):
    """A frozen conference as the OLD code would have written it: `bye` on seeds 1-2."""
    return [{"teamId": i + 1, "seed": i + 1, "winPct": 0.9 - 0.05 * i,
             "scoreDiff": 100 - 10 * i, "conference": "A",
             "bye": (i < 2) if staleByes else False}
            for i in range(n)]


class ByeCountTests(unittest.TestCase):
    def testAPowerOfTwoFieldHasNoByes(self):
        self.assertEqual(pb.byeCount(8), 0)
        self.assertEqual(pb.byeCount(4), 0)
        self.assertEqual(pb.byeCount(2), 0)

    def testANonPowerOfTwoFieldPadsUp(self):
        """The old six-a-side shape, which is where `bye: i < 2` came from."""
        self.assertEqual(pb.byeCount(6), 2)
        self.assertEqual(pb.byeCount(5), 3)
        self.assertEqual(pb.byeCount(7), 1)

    def testAnEmptyFieldIsNotAnError(self):
        self.assertEqual(pb.byeCount(0), 0)


class NormalizeByesTests(unittest.TestCase):
    def testAStaleFlagIsOverwrittenAtEightTeams(self):
        """The reported bug: a season frozen under the old rule."""
        out = pb.normalizeByes({"A": field(8)})["A"]
        self.assertEqual([t["bye"] for t in out], [False] * 8)

    def testASixTeamFieldKeepsItsRealByes(self):
        """The derivation must not simply zero the flag — a genuine non-power-of-two
        field still needs the top seeds held back or the tree cannot resolve."""
        out = pb.normalizeByes({"A": field(6)})["A"]
        self.assertEqual([t["bye"] for t in out], [True, True, False, False, False, False])

    def testNothingElseOnTheEntryIsDisturbed(self):
        """It rebuilds each dict, so the seed / record fields have to survive."""
        src = field(8)
        out = pb.normalizeByes({"A": src})["A"]
        for before, after in zip(src, out):
            self.assertEqual(after["teamId"], before["teamId"])
            self.assertEqual(after["seed"], before["seed"])
            self.assertEqual(after["winPct"], before["winPct"])
        self.assertIsNot(out[0], src[0], 'should not mutate the caller\'s dicts')

    def testTheStaleFlagCostAWholeRoundOneGame(self):
        """End to end, on the tree the user actually fills in: honoring the stale flag
        gives 3 round-1 games and leaves the top two seeds out of the round entirely."""
        stale = field(8)
        staleR1 = pb.pairTopVsBottom([t for t in stale if not t["bye"]])
        self.assertEqual(len(staleR1), 3)

        fixed = pb.normalizeByes({"A": stale})["A"]
        fixedR1 = pb.pairTopVsBottom([t for t in fixed if not t["bye"]])
        self.assertEqual(len(fixedR1), 4)
        playing = {t["teamId"] for pair in fixedR1 for t in pair}
        self.assertEqual(len(playing), 8, 'every qualifier plays round 1')


if __name__ == '__main__':
    unittest.main(verbosity=2)
