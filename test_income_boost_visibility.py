"""An active Endowment has to be visible on the grant it boosted.

⚠️ REPORTED BY A USER, as a suspected balance bug: they claimed a supporter dividend with
an Endowment active and nothing in the notification said it had been boosted, so they
reasonably concluded the powerup might not be firing at all.

⚠️ IT WAS FIRING. Production carries `supporter_dividend ... 'Supporter dividend claimed
(+38 Endowment)'` among 200 boosted rows. The fault was entirely on the display side, and
it is a good example of an invisible correct behaviour reading as a broken one.

⚠️ THE DESCRIPTION IS NOT A DISPLAY CHANNEL. The toast renders it on one nowrap/ellipsis
line roughly 19 characters wide -- `font-pixel` is Press Start 2P, a full-em pixel font, so
at 11px each character is 11px and the line is ~212px. The tag is appended at the END of
every description, so it was clipped in 100% of real grants:

    'Supporter dividend claimed (+38 Endowment)'   -> 'Supporter dividend '...
    'Week 28: 64 pts (5/16 correct) (+10 Endowment)' -> 'Week 28: 64 pts (5/'...

So the bonus now travels as its own NUMBER on the event, and the toast renders it as a
badge that cannot be truncated. The two channels are deliberately separate: the ledger row
keeps the prose with the suffix (it is the record, and is read in full), the wire gets the
prose WITHOUT it plus the number. Sending both would print the boost twice; stripping the
suffix client-side would mean parsing prose to recover a number the server already had.

Run: .venv/bin/python test_income_boost_visibility.py
"""
import unittest
from unittest.mock import patch

from api.event_models import CurrencyEvent


# ── The wire format ──────────────────────────────────────────────────────────────

class TheEventCarriesTheBonusAsANumber(unittest.TestCase):

    def test_theFieldIsPresentAndTyped(self):
        ev = CurrencyEvent.received(amount=60, transactionType='supporter_dividend',
                                    description='Supporter dividend claimed',
                                    balanceAfter=500, season=1, week=28, boostBonus=12)
        self.assertEqual(ev['boostBonus'], 12)
        self.assertIsInstance(ev['boostBonus'], int)

    def test_noBoostSendsZeroRatherThanOmittingTheField(self):
        """⚠️ A fact, not an absence to infer. A client distinguishing 'no boost' from
        'this server does not send boosts' would otherwise have to guess."""
        ev = CurrencyEvent.received(amount=48, transactionType='supporter_dividend',
                                    description='Supporter dividend claimed',
                                    balanceAfter=500, season=1, week=28)
        self.assertEqual(ev['boostBonus'], 0)

    def test_theBonusIsNotOnlyInTheProse(self):
        """THE REGRESSION. The whole defect was that the tag lived exclusively in a string
        the client could not show. A number in the payload is what fixes it."""
        ev = CurrencyEvent.received(amount=60, transactionType='supporter_dividend',
                                    description='Supporter dividend claimed',
                                    balanceAfter=500, season=1, week=28, boostBonus=12)
        self.assertNotIn('Endowment', ev['description'],
                         'the wire description should not repeat what boostBonus says')
        self.assertGreater(ev['boostBonus'], 0)


# ── The two channels, through the real addFunds ──────────────────────────────────

class _FakeQuery:
    def __init__(self, result=None):
        self._result = result

    def filter(self, *a, **k):
        return self

    def filter_by(self, *a, **k):
        return self

    def first(self):
        return self._result

    def order_by(self, *a, **k):
        return self


class TheLedgerAndTheWireDisagreeOnPurpose(unittest.TestCase):
    """Drives the real `CurrencyRepository.addFunds` with the Endowment lookup forced on,
    and reads what each channel got. ⚠️ Asserting the two SEPARATELY is the point: a single
    assertion on either one passes under the bug."""

    def _run(self, boostActive):
        from database.repositories.card_repositories import CurrencyRepository

        captured = {}

        class FakeSession:
            def query(self, *a, **k):
                return _FakeQuery()

            def add(self, obj):
                # The ledger row is the only thing added that carries a description.
                if hasattr(obj, 'description'):
                    captured['ledger'] = obj.description

            def flush(self):
                pass

        repo = CurrencyRepository(FakeSession())

        class Currency:
            balance = 0
            lifetime_earned = 0

        def fakeReceived(**kw):
            captured['wire'] = kw
            return {}

        with patch.object(CurrencyRepository, 'getOrCreate', return_value=Currency()), \
             patch.object(CurrencyRepository, '_currentSeasonNumber', return_value=1), \
             patch('database.repositories.shop_repository.ShopPurchaseRepository'
                   '.getActiveIncomeBoost', return_value=(object() if boostActive else None)), \
             patch('api.event_models.CurrencyEvent.received', side_effect=fakeReceived), \
             patch('api.game_broadcaster.broadcaster.broadcast_to_user_sync'):
            repo.addFunds(1, 48, 'supporter_dividend',
                          description='Supporter dividend claimed', season=1, week=28)
        return captured

    def test_theLedgerKeepsTheProse(self):
        """The transaction row is the record, read in full, and should say so in words."""
        got = self._run(boostActive=True)
        self.assertIn('Endowment', got.get('ledger', ''),
                      'the ledger row lost its human-readable boost tag')

    def test_theWireCarriesTheNumberAndNotTheSuffix(self):
        got = self._run(boostActive=True)
        wire = got.get('wire', {})
        self.assertEqual(wire.get('boostBonus'), 12, '48 boosted by 25% is 60, i.e. +12')
        self.assertNotIn('Endowment', wire.get('description') or '')

    def test_theAmountItselfIsTheBoostedOne(self):
        """⚠️ Guard the thing that was never broken. The user's real fear was that the
        powerup was not paying; if this ever fails, the report was right after all."""
        got = self._run(boostActive=True)
        self.assertEqual(got['wire']['amount'], 60)

    def test_withNoBoostNothingIsAddedToEitherChannel(self):
        got = self._run(boostActive=False)
        self.assertNotIn('Endowment', got.get('ledger', ''))
        self.assertEqual(got['wire']['boostBonus'], 0)
        self.assertEqual(got['wire']['amount'], 48)


class TheDescriptionIsNotWideEnoughToCarryIt(unittest.TestCase):
    """⚠️ Pins the measurement the fix rests on, so nobody 'simplifies' this back into the
    description. Press Start 2P advances a full em per glyph, so the toast's ~212px
    description line holds ~19 characters -- and the tag is always last."""

    LINE_PX = 212
    CHAR_PX = 11   # 11px font, 1em advance

    def test_everyRealDescriptionClipsBeforeTheTag(self):
        fits = self.LINE_PX // self.CHAR_PX
        real = [
            'Supporter dividend claimed (+38 Endowment)',
            'Week 28: 64 pts (5/16 correct) (+10 Endowment)',
            'Week 28: 702 FP -> 183F (+46 Endowment)',
            'Favorite team clinched playoffs (Week 28) (+19 Endowment)',
        ]
        for text in real:
            self.assertGreater(text.index('(+'), fits,
                               f'tag would have been visible in {text!r} -- re-measure')


if __name__ == '__main__':
    unittest.main(verbosity=2)
