"""A live game is matched to its fixture by who is playing, not by list position.

⚠️ TWO LISTS ASSUMED PARALLEL. The pick-em endpoints build a week's cards from the
SCHEDULE, then substitute the live game object for extra state (status, quarter) — and
did it by index: `activeGames[i]` against `scheduleGames[i]`. Nothing guarantees the sim
holds those in the same order.

Measured on production during a live week: 11 of 16 cards showed a pick for a team that
was not in the matchup on the card, each card carrying the PREVIOUS card's home team —
the signature of two lists offset from one another. Every PAST week read correctly, since
those never substitute anything and fall back to the schedule object.

It matters because a pick is stored against `(week, gameIndex)` where gameIndex is the
position in the schedule. A mismatch shows a reader someone else's pick on their card,
lands the check or cross on the wrong matchup once results arrive, and on the submit
paths validates a pick against the wrong fixture — where it is either refused as an
invalid team or filed against another game.

Run: .venv/bin/python test_pickem_live_pairing.py
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import logging
logging.disable(logging.CRITICAL)

# api.main pulls in the whole application, and `seasonManager` annotates against
# floosball_game.Game at class-definition time — the same circular-import dance the other
# headless tests do. The function under test is pure, so it is imported directly from the
# source rather than by importing the app.
import types as _types
if 'floosball_game' not in sys.modules:
    _stub = _types.ModuleType('floosball_game')
    _stub.Game = type('G', (), {})
    sys.modules['floosball_game'] = _stub
    import managers.timingManager  # noqa: F401
    del sys.modules['floosball_game']


class _Team:
    def __init__(self, tid):
        self.id = tid
        self.abbr = f'T{tid}'


class _Game:
    """Enough of a game for the pairing to work on."""
    def __init__(self, home, away, status='Scheduled'):
        self.homeTeam = _Team(home)
        self.awayTeam = _Team(away)
        self.status = status

    def __repr__(self):
        return f'{self.awayTeam.id}@{self.homeTeam.id}:{self.status}'


def _loadLiveGameFor():
    """Pull the function out of api/main.py without importing the application.

    ⚠️ Deliberate: importing `api.main` boots the whole app (DB, managers, the sim's
    circular imports) for one pure helper. Compiling just its source keeps this test the
    fast, dependency-free thing it should be — and it still fails if the function is
    renamed or deleted, which is what a regression test needs to notice.
    """
    import re as _re
    src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'api', 'main.py')).read()
    match = _re.search(r'^def _liveGameFor\(.*?(?=\n\ndef |\n\nclass |\n@app)', src, _re.S | _re.M)
    assert match, '_liveGameFor is gone from api/main.py'
    namespace = {}
    exec(compile(match.group(0), 'api/main.py:_liveGameFor', 'exec'), namespace)
    return namespace['_liveGameFor']


_liveGameFor = _loadLiveGameFor()


class LivePairingTests(unittest.TestCase):
    def testAReorderedLiveListStillMatchesTheRightFixture(self):
        """THE REGRESSION. The live pool holds the same games in another order."""
        schedule = [_Game(17, 1), _Game(15, 6), _Game(12, 3), _Game(16, 4)]
        # Rotated by one, which is what production was showing.
        live = [_Game(16, 4, 'Active'), _Game(17, 1, 'Active'),
                _Game(15, 6, 'Active'), _Game(12, 3, 'Active')]
        for fixture in schedule:
            got = _liveGameFor(fixture, live)
            self.assertEqual(got.homeTeam.id, fixture.homeTeam.id)
            self.assertEqual(got.awayTeam.id, fixture.awayTeam.id)
            self.assertEqual(got.status, 'Active', 'took the schedule entry, not the live one')

    def testTheIndexApproachWouldHaveFailedThisTest(self):
        """Guards the test: the shape it exists to catch has to be catchable."""
        schedule = [_Game(17, 1), _Game(15, 6)]
        live = [_Game(15, 6, 'Active'), _Game(17, 1, 'Active')]
        byIndex = live[0]
        self.assertNotEqual(byIndex.homeTeam.id, schedule[0].homeTeam.id,
                            'the fixture ordering used here does not reproduce the fault')

    def testAnAlreadyAlignedListIsUnaffected(self):
        """The common case must not move: same order in, same answers out."""
        schedule = [_Game(17, 1), _Game(15, 6), _Game(12, 3)]
        live = [_Game(17, 1, 'Final'), _Game(15, 6, 'Final'), _Game(12, 3, 'Final')]
        for i, fixture in enumerate(schedule):
            self.assertIs(_liveGameFor(fixture, live), live[i])

    def testAFixtureWithNoLiveCounterpartFallsBackToTheSchedule(self):
        """A future week has no live objects at all, and a partial pool must not
        hand back somebody else's game."""
        schedule = [_Game(17, 1), _Game(9, 2)]
        live = [_Game(17, 1, 'Active')]           # only the first has kicked off
        self.assertEqual(_liveGameFor(schedule[1], live).status, 'Scheduled')
        self.assertIs(_liveGameFor(schedule[1], live), schedule[1])
        self.assertIs(_liveGameFor(schedule[0], None), schedule[0])
        self.assertIs(_liveGameFor(schedule[0], []), schedule[0])

    def testItSearchesThePoolsInOrder(self):
        """Live state beats completed state — the endpoint passes activeGames first."""
        fixture = _Game(17, 1)
        active = [_Game(17, 1, 'Active')]
        completed = [_Game(17, 1, 'Final')]
        self.assertEqual(_liveGameFor(fixture, active, completed).status, 'Active')
        self.assertEqual(_liveGameFor(fixture, None, completed).status, 'Final')

    def testAGameObjectWithoutTeamsIsHandedBackUntouched(self):
        """Defensive: a malformed entry must not match the first thing in the pool."""
        class _Bare:
            pass
        bare = _Bare()
        self.assertIs(_liveGameFor(bare, [_Game(17, 1, 'Active')]), bare)


if __name__ == '__main__':
    unittest.main(verbosity=2)
