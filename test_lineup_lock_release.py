"""A lineup lock must have a way out that does not depend on the week finishing.

⚠️ THE LOCK HAD EXACTLY ONE RELEASE. `lockAllForWeek` fires at kickoff, `unlockWeek` at the
final whistle, and nothing else ever cleared it — so a restart between those two points
froze every lineup permanently. Reported from the app; the database carried 448 scheduled
games, ZERO final, and every equipped row locked.
"""
import unittest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.models import Base, EquippedCard
from database.repositories.card_repositories import EquippedCardRepository


def _session():
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


SLOTS = ('QB', 'RB', 'WR1', 'WR2', 'TE', 'K')


def _equip(s, week=1, locked=True, first=0, n=1):
    # (user, season, week, slot) is UNIQUE - vary the SLOT, not just the index.
    for i in range(n):
        s.add(EquippedCard(user_id=1, season=1, week=week, slot_number=first + i + 1,
                           slot=SLOTS[(first + i) % len(SLOTS)],
                           user_card_id=100 + first + i, locked=locked))
    s.commit()


class StaleLocksAreReleased(unittest.TestCase):

    def testABootReleasesThem(self):
        s = _session()
        _equip(s, n=3)
        freed = EquippedCardRepository(s).releaseStaleLocks()
        s.commit()
        self.assertEqual(freed, 3)
        self.assertEqual(s.query(EquippedCard).filter_by(locked=True).count(), 0)

    def testItIsIdempotent(self):
        s = _session()
        _equip(s, n=2)
        r = EquippedCardRepository(s)
        r.releaseStaleLocks(); s.commit()
        self.assertEqual(r.releaseStaleLocks(), 0)

    def testItReleasesEveryWeekNotJustTheCurrentOne(self):
        """A restart can strand more than one week's rows — nothing was clearing any."""
        s = _session()
        _equip(s, week=1, n=1)
        _equip(s, week=2, n=1)
        EquippedCardRepository(s).releaseStaleLocks(); s.commit()
        self.assertEqual(s.query(EquippedCard).filter_by(locked=True).count(), 0)

    def testItDoesNotTouchAnythingElse(self):
        s = _session()
        _equip(s, n=2)
        EquippedCardRepository(s).releaseStaleLocks(); s.commit()
        self.assertEqual(s.query(EquippedCard).count(), 2, 'rows were deleted, not unlocked')


class ItCannotFilterOnAStatusThatIsNeverStored(unittest.TestCase):
    """⚠️ THE FIRST VERSION KEPT LOCKS WHERE A GAME WAS `status == 'in_progress'`, which
    reads as the careful, narrow rule and is in fact a no-op: `games.status` only ever holds
    'scheduled' or 'final', because a live game is Active in MEMORY and never persists that
    state. The filter matches nothing and silently degrades to releasing everything — the
    same behaviour, minus the honesty about it."""

    def testTheEngineNeverPersistsAnInProgressStatus(self):
        src = open('managers/seasonManager.py').read()
        self.assertNotIn(".status = 'in_progress'", src)
        self.assertIn(".status = 'final'", src)

    def testTheReleaseDoesNotClaimToCheckGameState(self):
        import inspect
        src = inspect.getsource(EquippedCardRepository.releaseStaleLocks)
        # Strip the docstring first - it NAMES the status precisely to record why
        # the filter is not there, so a naive substring check fails on the very
        # explanation that keeps the mistake from coming back.
        code = src.split('"""')[-1]
        self.assertNotIn('in_progress', code)
        self.assertNotIn('Game', code, 'the release is querying game state again')


class TheBootPathCallsIt(unittest.TestCase):
    def testWiredBeforeTheSeasonLoop(self):
        src = open('managers/floosballApplication.py').read()
        self.assertIn('releaseStaleLocks()', src)


if __name__ == '__main__':
    unittest.main(verbosity=2)
