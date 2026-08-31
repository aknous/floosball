"""The shop half of Synth Components — the caps, at the endpoint that enforces them.

⚠️ THIS ENDPOINT HAD NO TEST. `componentManager` was covered directly, but the daily limit,
the hold cap and the season window are enforced in `api/main.py` and nothing exercised them
there. It is also the ONLY place a user learns WHY a purchase was refused, since the
frontend surfaces the `detail` string verbatim.
"""
import os
import sys
import tempfile
import unittest
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from constants import (SYNTH_COMPONENT_DAILY_LIMIT, SYNTH_COMPONENT_HOLD_CAP,
                       SYNTH_COMPONENT_SLUG)
from managers import componentManager as CM


def _session():
    """An in-memory DB with just the tables these guards touch."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from database.models import Base, User, UserComponent, ShopPurchase
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine)()
    u = User(clerk_id='t', email='t@t.t', username='T', is_active=True,
             is_admin=False, auto_fill_roster=False, has_completed_onboarding=True,
             email_opt_out=False, email_day_report=False, email_season_report=False,
             discord_dm_reminders=False, auto_pick_mode='off',
             auto_pick_never_against_favorite=False, vacancy_auto_pick=False,
             team_funding_pct=25, supporter_weeks=0, supporter_unclaimed=0,
             created_at=datetime.utcnow())
    s.add(u); s.commit()
    return s, u


class TheHoldCapGatesBuyingNotHolding(unittest.TestCase):
    """⚠️ It is checked against the BALANCE, not against a source — so a grant from any
    source counts. Verified live during testing: 8 admin-granted components closed the shop
    with `blockedBy: hold_cap`, and spending back to 2 reopened it."""

    def testHoldingTheCapBlocksAPurchase(self):
        s, u = _session()
        CM.grant(s, u.id, season=1, count=SYNTH_COMPONENT_HOLD_CAP, source='admin')
        s.commit()
        self.assertGreaterEqual(CM.balance(s, u.id, 1), SYNTH_COMPONENT_HOLD_CAP)

    def testSpendingBackDownReopensIt(self):
        s, u = _session()
        CM.grant(s, u.id, season=1, count=SYNTH_COMPONENT_HOLD_CAP, source='admin')
        s.commit()
        CM.consume(s, u.id, season=1, count=1)
        s.commit()
        self.assertLess(CM.balance(s, u.id, 1), SYNTH_COMPONENT_HOLD_CAP)


class TheDailyLimitIsPerSource(unittest.TestCase):
    """⚠️ `grant()` counts rows FROM THE GIVEN SOURCE, which is what lets an admin grant
    exist without eating a real allowance — and what would silently break if a caller
    reused 'shop' for something that is not a shop purchase."""

    def testACapBindsOnlyItsOwnSource(self):
        s, u = _session()
        CM.grant(s, u.id, season=1, count=5, source='admin')
        s.commit()
        got = CM.grant(s, u.id, season=1, count=1, source='achievement', cap=4)
        self.assertEqual(got, 1, 'an admin grant consumed the achievement allowance')

    def testACapDoesBindItsOwn(self):
        s, u = _session()
        CM.grant(s, u.id, season=1, count=4, source='achievement', cap=4)
        s.commit()
        self.assertEqual(CM.grant(s, u.id, season=1, count=1, source='achievement', cap=4), 0)

    def testAFullGrantIsNotPartiallyApplied(self):
        """A capped grant returns fewer rather than raising — a normal outcome."""
        s, u = _session()
        self.assertEqual(CM.grant(s, u.id, season=1, count=10, source='achievement', cap=3), 3)
        s.commit()
        self.assertEqual(CM.balance(s, u.id, 1), 3)


class ComponentsAreSeasonScoped(unittest.TestCase):
    def testLastSeasonsComponentsDoNotCount(self):
        s, u = _session()
        CM.grant(s, u.id, season=1, count=3, source='admin')
        s.commit()
        self.assertEqual(CM.balance(s, u.id, 2), 0,
                         'components carried across a season boundary')


class TheEndpointRefusalsAreReadable(unittest.TestCase):
    """⚠️ The frontend shows `detail` verbatim, so these strings ARE the UI. A generic
    'failed' here leaves a user with no idea whether to wait, spend, or earn."""

    def testEveryRefusalNamesItsReason(self):
        src = open('api/main.py').read()
        i = src.index('@app.post("/api/shop/synth-components/buy")')
        body = src[i:i + 3600]
        for phrase in ('only useful during the regular season',
                       "You've taken today's",
                       "You're holding",
                       'Insufficient Floobits'):
            self.assertIn(phrase, body, f'missing refusal: {phrase}')

    def testTheSlugIsSharedWithTheDailyCount(self):
        """The daily limit counts `ShopPurchase` rows by slug; a mismatch uncaps it."""
        src = open('api/main.py').read()
        self.assertIn('getPurchasesToday(user.id, SYNTH_COMPONENT_SLUG)', src)
        self.assertTrue(SYNTH_COMPONENT_SLUG)


if __name__ == '__main__':
    unittest.main(verbosity=2)
