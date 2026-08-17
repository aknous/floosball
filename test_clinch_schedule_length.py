"""Clinching is measured against the REGULAR season, not the schedule list's length.

⚠️ `seasonManager._simulatePlayoffRounds` APPENDS each playoff round to the very same
`currentSeason.schedule` the standings endpoint measures against, so a plain
`len(schedule)` climbed 28 -> 29 -> 30 -> 31 -> 32 across the postseason. `clinchStatus`
reads that as games still in hand, and its entire method is "can anyone still catch me",
so the badges dissolved exactly when the season was most settled — and got worse every
round.

Reported as the end-of-season standings being all wrong: no eliminated teams, no
division trophies, and clubs still reading "projected seed" after they had qualified.
All three are one cause. Measured on a played-out 16-club league below.

⚠️ The endpoint skips clinching entirely when the count is falsy, so returning 0 for an
unusable schedule is the safe direction: no badges rather than badges computed off a
guess.

Run: .venv/bin/python test_clinch_schedule_length.py
"""

import os
import sys
import types
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import logging
logging.disable(logging.CRITICAL)

if 'floosball_game' not in sys.modules:
    _stub = types.ModuleType('floosball_game')
    class _GameStub: pass
    _stub.Game = _GameStub
    sys.modules['floosball_game'] = _stub
    import managers.timingManager  # noqa: F401
    del sys.modules['floosball_game']

from standings_view import clinchStatus, regularSeasonWeeks  # noqa: E402

REGULAR_WEEKS = 28


class _Game:
    def __init__(self, isRegular):
        self.isRegularSeasonGame = isRegular


class _Team:
    def __init__(self, tid, division, wins, losses):
        self.id = tid
        self.name = 'T%d' % tid
        self.division = division
        self.seasonTeamStats = {
            'wins': wins, 'losses': losses, 'ties': 0,
            'winPerc': wins / (wins + losses), 'scoreDiff': (wins - losses) * 7,
            'Offense': {'pts': wins * 20}, 'Defense': {'ptsAlwd': losses * 20},
        }


def league():
    """One 16-club league, four divisions of four, a full 28-game season played out.
    The field is the top 8, so the right answer is 8 clinched and 8 eliminated."""
    recs = [(22, 6), (20, 8), (19, 9), (18, 10), (17, 11), (16, 12), (16, 12), (15, 13),
            (14, 14), (14, 14), (13, 15), (12, 16), (11, 17), (10, 18), (8, 20), (6, 22)]
    return [_Team(i + 1, 'Div%d' % (i % 4), w, l) for i, (w, l) in enumerate(recs)]


def schedule(playoffRounds=0):
    weeks = [{'startTime': None, 'games': [_Game(True)]} for _ in range(REGULAR_WEEKS)]
    weeks += [{'startTime': None, 'games': [_Game(False)]} for _ in range(playoffRounds)]
    return weeks


def counts(totalGames):
    c = clinchStatus(league(), totalGames)
    return {
        'clinched': sum(1 for v in c.values() if v['clinchedPlayoffs']),
        'eliminated': sum(1 for v in c.values() if v['eliminated']),
        'division': sum(1 for v in c.values() if v['clinchedDivision']),
        'topSeed': sum(1 for v in c.values() if v['clinchedTopSeed']),
    }


class RegularSeasonWeeksTests(unittest.TestCase):
    def testPlayoffRoundsDoNotCount(self):
        """The bug, at its source. Each round the sim appends one more week."""
        for rounds in range(5):
            self.assertEqual(regularSeasonWeeks(schedule(rounds)), REGULAR_WEEKS,
                             'playoff round %d leaked into the count' % rounds)

    def testAnUnusableScheduleReportsZero(self):
        """Zero means "unknown" to the caller, which skips clinching. Badging off a
        guess is the worse failure."""
        self.assertEqual(regularSeasonWeeks([]), 0)
        self.assertEqual(regularSeasonWeeks(None), 0)
        self.assertEqual(regularSeasonWeeks([{'startTime': None, 'games': []}]), 0)

    def testItReadsTheFlagRatherThanAssumingALength(self):
        """The season length has already moved once (24 clubs / 14 weeks -> 32 / 28),
        so this must not become a hardcoded 28."""
        self.assertEqual(regularSeasonWeeks(schedule(0)[:14]), 14)


class ClinchAtSeasonEndTests(unittest.TestCase):
    def testAFinishedSeasonIsFullySettled(self):
        """The correct answer, and what the board should show once week 28 is done."""
        self.assertEqual(counts(REGULAR_WEEKS),
                         {'clinched': 8, 'eliminated': 8, 'division': 4, 'topSeed': 1})

    def testPhantomGamesInHandDissolveTheBadges(self):
        """⚠️ The reported symptoms, reproduced: at 32 (the schedule length after the
        Floos Bowl) the badges collapse. Keep this test — it is the only thing that
        catches the count being taken off the wrong list again."""
        broken = counts(REGULAR_WEEKS + 4)
        self.assertLess(broken['clinched'], 8)
        self.assertLess(broken['eliminated'], 8)
        self.assertLess(broken['division'], 4)
        self.assertEqual(broken['topSeed'], 0)

    def testTheFixHoldsThroughEveryPlayoffRound(self):
        """What the endpoint now computes, round by round — the whole point is that the
        board stops changing once the regular season is over."""
        for rounds in range(5):
            self.assertEqual(counts(regularSeasonWeeks(schedule(rounds))),
                             {'clinched': 8, 'eliminated': 8, 'division': 4, 'topSeed': 1},
                             'board drifted after playoff round %d' % rounds)


if __name__ == '__main__':
    unittest.main(verbosity=2)
