"""Why a chess-clock game ended has to travel over the socket, not just the API.

⚠️ The "ran out of time" line existed only as a `gameFeed` entry. The REST feed serves
that; the socket never carries it. So a reader watching live saw the whistle with no
reason for it — and a chess-clock game can end MID-QUARTER with the clock still reading
well above 0:00, which is exactly when a reason is most needed.

It is the same kind of fact as the frames points tiebreak, so it rides the same field
rather than growing a second channel.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import managers  # noqa: F401  — breaks the floosball_game circular import
from api.event_models import GameEvent


class FakeTeam:
    def __init__(self, abbr, name):
        self.abbr = abbr
        self.name = name


class FakeFormat:
    """Stands in for ChessClockFormat: only `key` and `_lockedOut` are consulted."""

    key = 'chess_clock'

    def __init__(self, lockedTeams=()):
        self.lockedTeams = set(lockedTeams)

    def _lockedOut(self, game, team):
        return team.abbr in self.lockedTeams


def noteFor(fmt, losingTeam):
    """The branch as `playGame` runs it, isolated from the 100-line method."""
    if getattr(fmt, 'key', '') != 'chess_clock':
        return None
    try:
        if losingTeam is not None and fmt._lockedOut(None, losingTeam):
            lt = getattr(losingTeam, 'abbr', None) or getattr(losingTeam, 'name', 'The loser')
            return f"{lt} ran out of time"
    except Exception:
        pass
    return None


class ChessClockReasonTests(unittest.TestCase):
    def setUp(self):
        self.was = FakeTeam('WAS', 'Washington Monuments')
        self.nys = FakeTeam('NYS', 'New York Statues')

    def testALockedOutLoserProducesTheReason(self):
        note = noteFor(FakeFormat(lockedTeams={'WAS'}), self.was)
        self.assertEqual(note, 'WAS ran out of time')

    def testALoserWhoSimplyLostGetsNoReason(self):
        # Ran the clock down but was never locked out — nothing to explain.
        self.assertIsNone(noteFor(FakeFormat(), self.was))

    def testATieProducesNoReason(self):
        self.assertIsNone(noteFor(FakeFormat(lockedTeams={'WAS'}), None))

    def testAnotherFormatIsUntouched(self):
        fmt = FakeFormat(lockedTeams={'WAS'})
        fmt.key = 'standard'
        self.assertIsNone(noteFor(fmt, self.was))

    def testAFormatThatRaisesDoesNotBreakTheWhistle(self):
        class Exploding(FakeFormat):
            def _lockedOut(self, game, team):
                raise RuntimeError('boom')
        self.assertIsNone(noteFor(Exploding(), self.was))

    # -- transport ---------------------------------------------------------

    def testTheReasonRidesTheGameEndEvent(self):
        event = GameEvent.gameEnd(
            gameId=1, finalScore={'home': 17, 'away': 20}, winner='New York Statues',
            tiebreakNote='WAS ran out of time',
        )
        self.assertEqual(event['tiebreakNote'], 'WAS ran out of time')

    def testTheReasonIsAlsoInTheFinalMessage(self):
        # Consumers that only read `message` (the bot's final line) get it too.
        event = GameEvent.gameEnd(
            gameId=1, finalScore={'home': 17, 'away': 20}, winner='New York Statues',
            tiebreakNote='WAS ran out of time',
        )
        self.assertIn('WAS ran out of time', event['message'])

    def testAGameWithNoReasonCarriesNone(self):
        event = GameEvent.gameEnd(
            gameId=1, finalScore={'home': 17, 'away': 20}, winner='New York Statues')
        self.assertIsNone(event['tiebreakNote'])
        self.assertNotIn('ran out of time', event['message'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
