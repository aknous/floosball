"""A glitch is a window, not a permanent upgrade.

⚠️ IT USED TO BE FOREVER. `user_cards.glitched` is a boolean and nothing ever cleared it, so
every Criticality's marks accumulated for the life of the account. Measured on production
after ONE season: three Criticalities (weeks 9, 14, 27), 48 glitched cards across 22 users,
and 9 users already holding three apiece. Five seasons of that is fifteen.

Two changes, decided together because they pull in opposite directions on purpose (owner,
2026-08-17):

  EXPIRY   a glitch fades after `GLITCH_MAX_TRIGGERS` surges. Counted in TRIGGERS, not
           weeks, so lifespan tracks value actually received: a card that never fires keeps
           its glitch rather than expiring having given nothing, and a hot card burns out
           fastest.

  SWARM    each additional glitched card IN THE LINEUP raises every glitched card's odds.
           With the stockpile gone, what is left to reward is assembling a window -- so it
           counts what is equipped, never what is owned.

⚠️ THE TRAP THIS FILE EXISTS FOR: the surge is ROLLED in `cardEffectCalculator`, which
re-runs on every projection and every page load, and whose RNG is deliberately stable per
(user, season, week, card) so a settled week never moves. Counting triggers there would
spend a glitch's entire life on one afternoon of refreshes. The trigger is consumed at the
BANK write instead -- the one place a week happens exactly once.

Run: .venv/bin/python test_glitch_expiry.py
"""
import unittest
from types import SimpleNamespace

from constants import (GLITCH_MAX_TRIGGERS, GLITCH_SWARM_STEP, GLITCH_TRIGGER_BASE,
                       GLITCH_TRIGGER_CAP)
from managers.glitchCards import triggerChance, triggersRemaining, consumeTriggers


class _Card:
    def __init__(self, cardId, glitched=True, used=0):
        self.id = cardId
        self.glitched = glitched
        self.glitch_triggers_used = used


class _Session:
    """Enough of a session for `consumeTriggers`: an id-filtered, glitched-only query."""

    def __init__(self, cards):
        self._cards = {c.id: c for c in cards}
        self.flushed = 0

    def query(self, *a, **k):
        return self

    def filter(self, *criteria):
        self._criteria = criteria
        return self

    def all(self):
        return [c for c in self._cards.values() if c.glitched]

    def flush(self):
        self.flushed += 1


def consume(cards, firing):
    session = _Session(cards)
    # The real call filters by id in SQL; the stub returns every glitched card, so restrict
    # here to keep the fixture honest about which cards actually fired.
    session._cards = {c.id: c for c in cards if c.id in set(firing)}
    return consumeTriggers(session, firing)


class TheGlitchFades(unittest.TestCase):

    def test_aFreshGlitchHasItsFullLifespan(self):
        self.assertEqual(triggersRemaining(_Card(1)), GLITCH_MAX_TRIGGERS)

    def test_eachSurgeSpendsOne(self):
        card = _Card(1)
        for spent in range(1, GLITCH_MAX_TRIGGERS):
            consume([card], [1])
            self.assertEqual(card.glitch_triggers_used, spent)
            self.assertTrue(card.glitched, 'faded early')
            self.assertEqual(triggersRemaining(card), GLITCH_MAX_TRIGGERS - spent)

    def test_theLastSurgeFadesIt(self):
        """THE FEATURE. After the limit the card goes back to normal."""
        card = _Card(1)
        faded = {}
        for _ in range(GLITCH_MAX_TRIGGERS):
            faded = consume([card], [1])
        self.assertFalse(card.glitched, 'the glitch should have faded')
        self.assertTrue(faded[1])
        self.assertEqual(triggersRemaining(card), 0)

    def test_aFadedGlitchCannotBeSpentAgain(self):
        """⚠️ `consumeTriggers` filters on `glitched`, so a faded card is not found and its
        counter cannot run away past the limit."""
        card = _Card(1, glitched=False, used=GLITCH_MAX_TRIGGERS)
        consume([card], [1])
        self.assertEqual(card.glitch_triggers_used, GLITCH_MAX_TRIGGERS)

    def test_aDormantGlitchNeverExpires(self):
        """⚠️ WHY TRIGGERS AND NOT WEEKS. A card that has not surged has given its owner
        nothing; expiring it on a clock would take away something never received."""
        card = _Card(1)
        for _ in range(40):
            consume([card], [])          # forty weeks, no surge
        self.assertTrue(card.glitched)
        self.assertEqual(triggersRemaining(card), GLITCH_MAX_TRIGGERS)

    def test_onlyTheCardsThatFiredAreCharged(self):
        fired, quiet = _Card(1), _Card(2)
        consume([fired, quiet], [1])
        self.assertEqual(fired.glitch_triggers_used, 1)
        self.assertEqual(quiet.glitch_triggers_used, 0)

    def test_aNewGlitchRestoresTheFullLifespan(self):
        """⚠️ `markCardsForCriticality` zeroes the counter, or a card that had already
        burned three surges would catch a glitch and fade on its very next trigger."""
        with open('managers/glitchCards.py') as fh:
            src = fh.read()
        mark = src.split('def markCardsForCriticality')[1]
        self.assertIn('glitch_triggers_used = 0', mark)


class TheCounterIsNotSpentByRecomputing(unittest.TestCase):
    """⚠️ THE CENTRAL RISK. Guarding it structurally, because the failure is invisible in
    normal play: a glitch would simply seem to expire faster than the rule says, and only
    for people who look at their lineup a lot."""

    def test_theCalculatorNeverConsumesATrigger(self):
        with open('managers/cardEffectCalculator.py') as fh:
            src = fh.read()
        self.assertNotIn('consumeTriggers', src,
                         'the surge roll must not spend the glitch -- it re-runs per view')
        self.assertNotIn('glitch_triggers_used', src)

    def test_theBankSiteDoesConsume(self):
        with open('managers/seasonManager.py') as fh:
            src = fh.read()
        self.assertIn('consumeTriggers', src)
        # In the same block as the bank write, so it inherits its once-per-user-week gate.
        bank = src.split('weekBonus = WeeklyCardBonus(')[1][:2000]
        self.assertIn('consumeTriggers', bank,
                      'consumption must sit with the bank write, not on some other path')

    def test_theBreakdownCarriesTheCardIdToChargeIt(self):
        from managers.cardEffectCalculator import CardBreakdown
        self.assertTrue(hasattr(CardBreakdown(), 'glitchUserCardId'))


class TheSwarmBonus(unittest.TestCase):

    def test_oneGlitchedCardIsUnchanged(self):
        """A lone glitch must score exactly as it did before the swarm term existed."""
        self.assertAlmostEqual(triggerChance('stable', {}, 1.0, glitchedEquipped=1),
                               GLITCH_TRIGGER_BASE['stable'], places=6)

    def test_eachExtraCardRaisesTheOdds(self):
        chances = [triggerChance('stable', {}, 1.0, glitchedEquipped=n) for n in range(1, 7)]
        self.assertEqual(chances, sorted(chances))
        for lower, higher in zip(chances, chances[1:]):
            self.assertAlmostEqual(higher - lower, GLITCH_SWARM_STEP, places=6)

    def test_aFullLineupIsFeltButDoesNotDominate(self):
        """Six glitched cards is +0.25 on a base of 0.28 -- a real lift that still leaves
        the ladder and the week's events deciding most of it."""
        solo = triggerChance('stable', {}, 1.0, glitchedEquipped=1)
        full = triggerChance('stable', {}, 1.0, glitchedEquipped=6)
        self.assertGreater(full, solo)
        self.assertLess(full, GLITCH_TRIGGER_CAP,
                        'the swarm alone should not reach the cap')

    def test_itStillRespectsTheCap(self):
        hot = triggerChance('rampant', {'signature': 3}, 5.0, glitchedEquipped=6)
        self.assertLessEqual(hot, GLITCH_TRIGGER_CAP)

    def test_theDefaultCallerIsUnaffected(self):
        """⚠️ Existing call sites pass no count. The default has to be the solo value or
        every one of them silently changes."""
        self.assertEqual(triggerChance('erratic', {'micro': 1}, 2.0),
                         triggerChance('erratic', {'micro': 1}, 2.0, glitchedEquipped=1))

    def test_itCountsTheLineupNotTheCollection(self):
        """⚠️ Owning more must do nothing -- that is the behaviour expiry exists to end."""
        with open('managers/cardEffectCalculator.py') as fh:
            src = fh.read()
        block = src.split('def _applyGlitchSurges')[1]
        self.assertIn('glitchedEquipped=len(glitchedIds)', block)
        # glitchedIds is built from equippedCards, so it is the lineup by construction.
        self.assertIn('for eq in equippedCards:', block)


class TheMigrationIsSafeForExistingGlitches(unittest.TestCase):

    def test_liveGlitchesStartWithAFullLifespan(self):
        """⚠️ The 48 already-marked production cards must not retire on arrival. Defaulting
        to 0 gives them a full window from the day this ships, which is the same rule the
        whole glitch system runs on: it never takes anything away."""
        with open('database/connection.py') as fh:
            src = fh.read()
        self.assertIn("('glitch_triggers_used', 'INTEGER DEFAULT 0 NOT NULL')", src)

    def test_theModelAgreesWithTheMigration(self):
        from database.models import UserCard
        self.assertIn('glitch_triggers_used', UserCard.__table__.columns)


if __name__ == '__main__':
    unittest.main(verbosity=2)
