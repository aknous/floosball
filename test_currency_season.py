"""Every grant says which season it belongs to.

⚠️ `currency_transactions.season` is NULLABLE and four grant paths never passed it, so
nothing ever complained. Measured on production: 1,100 positive grants worth 82,534F
carried NULL against 212,614F stamped to season 1 — a **28% undercount of the faucet**.

That is not bookkeeping. `facilitiesManager.computeShareUnit` is exactly "last season's
grants divided by the team count", so every unstamped grant quietly made every facility in
the league cheaper than the economy warranted. Sources: `achievement` (883 rows),
`starter_bonus` (185) and `card_sell` (32). The 13 stamped `achievement` rows came from the
single call site that did pass it, which is what identified this as path-specific rather
than something that broke on a date.

⚠️ THE DEFAULT LIVES IN `addFunds`, NOT AT THE CALL SITES. Four sites forgetting the same
argument is a sign the argument should not have been optional at the edge; defaulting at the
one choke point also covers every grant site added later.

⚠️ THE TWO ECONOMY BUGS WERE MASKING EACH OTHER. This undercount pushed the share unit DOWN
about 28% while a single user's Criticality windfall pushed it UP about 59% (see
`test_facility_costs.py`). Fixing either alone moves prices further from correct than fixing
both: on production, cap-only gives 4,536F, backfill-only 8,706F, and both 6,074F against a
broken 6,644F.

Run: .venv/bin/python test_currency_season.py
"""
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


class CurrencySeasonTests(unittest.TestCase):
    def setUp(self):
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from database.models import Base
        self.tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.tmp.close()
        self.engine = create_engine(f'sqlite:///{self.tmp.name}')
        Base.metadata.create_all(bind=self.engine)
        self.session = sessionmaker(bind=self.engine)()

    def tearDown(self):
        self.session.close()
        self.engine.dispose()
        os.unlink(self.tmp.name)

    def _repo(self):
        from database.repositories.card_repositories import CurrencyRepository
        return CurrencyRepository(self.session)

    def _setSimSeason(self, n):
        """Through the ORM so the model's own column defaults apply."""
        from database.models import SimulationState
        self.session.add(SimulationState(id=1, current_season=n, current_week=1))
        self.session.commit()

    def _addSeasons(self, *pairs):
        """Through the ORM so the model's own column defaults apply."""
        from database.models import Season
        for num, start in pairs:
            self.session.add(Season(season_number=num, start_date=start))
        self.session.commit()

    def _grants(self):
        from database.models import CurrencyTransaction
        return self.session.query(CurrencyTransaction).all()

    # -- the default -------------------------------------------------------

    def testAGrantWithNoSeasonIsStampedAnyway(self):
        """THE REGRESSION. A caller that omits the season must not produce a NULL row."""
        self._setSimSeason(3)
        self._repo().addFunds(userId=1, amount=100, transactionType='card_sell')
        rows = self._grants()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].season, 3, 'grant landed with no season')

    def testAnExplicitSeasonStillWins(self):
        """The default must never override a caller that knows better — a settled week
        credited late belongs to ITS season, not to whatever the sim is on now."""
        self._setSimSeason(9)
        self._repo().addFunds(userId=1, amount=100, transactionType='achievement', season=4)
        self.assertEqual(self._grants()[0].season, 4)

    def testNoSimStateFallsBackToTheSeasonsTable(self):
        self._addSeasons((2, datetime(2026, 1, 1)))
        self._repo().addFunds(userId=1, amount=50, transactionType='card_sell')
        self.assertEqual(self._grants()[0].season, 2)

    def testAGrantNeverFailsOverAMissingSeason(self):
        """⚠️ A grant is real money to a user. Not knowing the season is a reason to
        record NULL, never a reason to lose the credit."""
        self._repo().addFunds(userId=1, amount=75, transactionType='card_sell')
        rows = self._grants()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].amount, 75)

    def testTheStarterBonusIsStamped(self):
        """It is built directly rather than through addFunds, so it does not inherit the
        default — 185 of these landed NULL on production."""
        with open('api/auth.py') as fh:
            src = fh.read()
        block = src.split("transaction_type='starter_bonus'")[1][:400]
        self.assertIn('season=', block,
                      'the starter bonus is still written without a season')

    # -- the backfill ------------------------------------------------------

    def testBackfillStampsByWhichSeasonHadStarted(self):
        from database.models import CurrencyTransaction
        import database.connection as conn
        self._addSeasons((1, datetime(2026, 1, 1)), (2, datetime(2026, 3, 1)))
        for when in (datetime(2026, 1, 15), datetime(2026, 4, 1), datetime(2025, 12, 1)):
            self.session.add(CurrencyTransaction(
                user_id=1, amount=10, transaction_type='achievement',
                balance_after=0, season=None, created_at=when))
        self.session.commit()

        realEngine = conn.engine
        conn.engine = self.engine
        try:
            conn._backfillCurrencyTransactionSeason()
        finally:
            conn.engine = realEngine

        self.session.expire_all()
        got = {r.created_at.date().isoformat(): r.season for r in self._grants()}
        self.assertEqual(got['2026-01-15'], 1, 'mid-season-1 grant not stamped 1')
        self.assertEqual(got['2026-04-01'], 2, 'post-season-2-start grant not stamped 2')
        self.assertIsNone(got['2025-12-01'],
                          'a grant predating every season must stay NULL, not join the '
                          'faucet that prices season 1')

    def testBackfillNeverRewritesAStampedRow(self):
        from database.models import CurrencyTransaction
        import database.connection as conn
        self._addSeasons((1, datetime(2026, 1, 1)))
        self.session.add(CurrencyTransaction(
            user_id=1, amount=10, transaction_type='achievement', balance_after=0,
            season=7, created_at=datetime(2026, 2, 1)))
        self.session.commit()

        realEngine = conn.engine
        conn.engine = self.engine
        try:
            conn._backfillCurrencyTransactionSeason()
        finally:
            conn.engine = realEngine
        self.session.expire_all()
        self.assertEqual(self._grants()[0].season, 7,
                         'the backfill overwrote a season the sim had already recorded')


if __name__ == '__main__':
    unittest.main(verbosity=2)
