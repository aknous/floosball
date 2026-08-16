"""Records are a REGULAR-SEASON body of work — the playoffs do not set them.

Reported 2026-08-14: players were setting all-time records during the playoffs.

⚠️ `processPostGameStats` already gates season totals on `isRegularSeasonGame` so the
standings never absorb playoff results. The GAME-record checks were the hole — the
playoff path called `checkPlayerGameRecords()` and `checkTeamGameRecords()` identically
to the regular-season path, so a Floos Bowl performance took an all-time single-game
record.

⚠️ SEASON and CAREER records were never at risk: both read `seasonStatsDict`, which
playoff games are already gated out of accumulating into. Only the single-game records
leaked, which is why this showed up as one loud wrong entry rather than a skewed table.

⚠️ `checkPlayerGameRecords` CANNOT DEFEND ITSELF — it takes no game at all, it sweeps
every active player's `gameStatsDict`. So it has to be gated by its caller, and the test
below reads the call site to make sure it stays that way. `checkTeamGameRecords` does
take the game, so it carries its own guard.

Run: .venv/bin/python test_playoff_records.py
"""

import os
import re
import sys
import types
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import logging
logging.disable(logging.CRITICAL)

HERE = os.path.dirname(os.path.abspath(__file__))


def playoffGameBody(stripComments: bool = False) -> str:
    """`_simulatePlayoffGame`, as source.

    ⚠️ `stripComments` matters: the fix left a comment NAMING the calls it removed and
    explaining why, so a bare substring search finds the method name in prose and reports
    a bug that is not there. Strip the comments before asserting a call is absent.
    """
    with open(os.path.join(HERE, 'managers', 'seasonManager.py')) as fh:
        src = fh.read()
    start = src.index('async def _simulatePlayoffGame')
    end = src.index('\n    async def ', start + 10)
    nextDef = src.find('\n    def ', start + 10)
    if nextDef != -1:
        end = min(end, nextDef)
    body = src[start:end]
    if stripComments:
        body = '\n'.join(re.sub(r'#.*$', '', line) for line in body.split('\n'))
    return body


class _Team:
    def __init__(self):
        self.name = 'T'
        self.rosterDict = {}


class _Game:
    def __init__(self, isRegular):
        self.isRegularSeasonGame = isRegular
        self.homeTeam = _Team()
        self.awayTeam = _Team()
        self.homeScore = 99
        self.awayScore = 0


class PlayoffRecordTests(unittest.TestCase):
    def testThePlayoffPathDoesNotCheckPlayerGameRecords(self):
        """The reported bug. This one is a call-site test on purpose — the method has no
        game to gate on, so the call site is the only place the rule can live."""
        body = playoffGameBody(stripComments=True)
        self.assertNotIn('checkPlayerGameRecords', body,
                         'the playoff path is setting single-game player records again')

    def testThePlayoffPathDoesNotCheckTeamGameRecords(self):
        body = playoffGameBody(stripComments=True)
        self.assertNotIn('checkTeamGameRecords', body,
                         'the playoff path is setting single-game team records again')

    def testTheNewsSnapshotSurvives(self):
        """`_publishGameNews` still runs on the playoff path — it carries the upset story
        as well as the record one, so removing the record checks must not remove it."""
        self.assertIn('_publishGameNews', playoffGameBody())

    def testTeamRecordsRefuseAPlayoffGame(self):
        """`checkTeamGameRecords` HAS the game, so it defends itself rather than relying
        on every future caller remembering."""
        if 'floosball_game' not in sys.modules:
            stub = types.ModuleType('floosball_game')
            class _GameStub: pass
            stub.Game = _GameStub
            sys.modules['floosball_game'] = stub
            import managers.timingManager  # noqa: F401
            del sys.modules['floosball_game']
        from managers.recordManager import RecordManager

        calls = []

        class _Probe(RecordManager):
            def __init__(self):
                pass  # the guard runs before anything else is touched
            def getRecords(self):
                calls.append('read')
                return {'team': {'game': {}}}

        _Probe().checkTeamGameRecords(_Game(isRegular=False))
        self.assertEqual(calls, [], 'a playoff game reached the team record check')

    def testSeasonTotalsWereAlreadyGated(self):
        """The rule this fix follows, and the reason season/career records were safe."""
        with open(os.path.join(HERE, 'managers', 'recordManager.py')) as fh:
            src = fh.read()
        start = src.index('def processPostGameStats')
        body = src[start:src.index('\n    def ', start + 10)]
        self.assertIsNotNone(re.search(r'if\s+gameInstance\.isRegularSeasonGame\s*:', body))


if __name__ == '__main__':
    unittest.main(verbosity=2)
