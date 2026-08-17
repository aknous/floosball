"""The shop slate stays put, and the first reroll each day is free.

⚠️ THE SHOP USED TO REPOPULATE ITS OWN CARD SLATE EVERY DAY. A user saving up for a
specific single would come back to find it simply gone — reported as the shop "making the
card they're trying to buy disappear" (owner, 2026-08-16). Saving toward a card only works
if the card is still there when the Floobits are, so the slate now persists until the USER
changes it, and the free daily reroll is what lets them change it deliberately.

⚠️ THE FREE REROLL IS THE REPLACEMENT FOR THE AUTO-REFRESH, NOT A BONUS ON TOP OF IT.
Removing the refresh without it would leave a user who bought out the shelf with no way to
restock except paying; adding it without removing the refresh would just be a discount on
undoing something they never asked for.

⚠️ A FREE REROLL MUST NOT GO THROUGH `spendFunds`. Spending 0 still writes a 0-Floobit row
into the currency ledger and fires the Magnate (season floobits spent) achievement hook for
a purchase that did not happen.

Run: .venv/bin/python test_shop_reroll.py
"""
import unittest

from constants import (shopRerollCost, SHOP_REROLL_BASE_COST,
                       SHOP_REROLL_COST_INCREMENT, SHOP_REROLL_FREE_PER_DAY)


class TheFirstRerollEachDayIsFree(unittest.TestCase):

    def test_firstIsFree(self):
        self.assertEqual(shopRerollCost(0), 0)

    def test_theSecondCostsTheOldBasePrice(self):
        """The paid ladder is shifted one place right, not rescaled — someone churning the
        shelf inside a day pays what they always did from their second roll on."""
        self.assertEqual(shopRerollCost(1), SHOP_REROLL_BASE_COST)
        self.assertEqual(shopRerollCost(2), SHOP_REROLL_BASE_COST + SHOP_REROLL_COST_INCREMENT)
        self.assertEqual(shopRerollCost(3), SHOP_REROLL_BASE_COST + 2 * SHOP_REROLL_COST_INCREMENT)

    def test_costNeverDecreases(self):
        costs = [shopRerollCost(i) for i in range(12)]
        self.assertEqual(costs, sorted(costs), f'reroll ladder is not monotonic: {costs}')

    def test_onlyOneIsFree(self):
        """Exactly `SHOP_REROLL_FREE_PER_DAY` free rolls — a second free one would make
        the shelf churnable at no cost, which is the thing the price ladder exists to stop."""
        free = [i for i in range(12) if shopRerollCost(i) == 0]
        self.assertEqual(len(free), SHOP_REROLL_FREE_PER_DAY, f'free rolls: {free}')

    def test_negativeCountIsTreatedAsFresh(self):
        """A missing/garbled count must not produce a negative price (a paid refund)."""
        self.assertEqual(shopRerollCost(-3), 0)


class TheSlateDoesNotRepopulateItself(unittest.TestCase):

    def _src(self):
        with open('managers/cardManager.py') as fh:
            return fh.read()

    def test_fantasySlateHasNoAutomaticRefresh(self):
        src = self._src()
        self.assertNotIn('needsRefresh = sampleRow.generated_at < boundary', src,
                         'the daily auto-refresh is back — the saved-for card will vanish again')
        self.assertNotIn('needsRefresh = currentCycle > genCycle', src,
                         'the 7-week cycle auto-refresh is back')
        self.assertIn('needsRefresh = False', src)

    def test_collectionShelfHasNoAutomaticRefresh(self):
        src = self._src()
        self.assertNotIn('stale = any((r.generated_at or datetime.min) < lastReset for r in rows)', src,
                         'the collection shelf still rotates on its own')

    def test_rerollStillRegenerates(self):
        """The user-initiated path has to survive — otherwise the shelf can never change."""
        src = self._src()
        self.assertIn('forceRegenerate', src,
                      'reroll must still be able to force a fresh slate')


class TheEndpointsAgree(unittest.TestCase):

    def _src(self):
        with open('api/main.py') as fh:
            return fh.read()

    def test_bothEndpointsUseTheOneCostFunction(self):
        """The cost was computed inline in two places; they have to stay in step or the
        quoted price and the charged price drift."""
        src = self._src()
        self.assertEqual(src.count('cost = shopRerollCost(rerollCount)'), 2,
                         'the GET and the POST must both price through shopRerollCost')
        self.assertNotIn('cost = SHOP_REROLL_BASE_COST + (rerollCount * SHOP_REROLL_COST_INCREMENT)', src,
                         'inline cost arithmetic is back')

    def test_nextCostIsQuotedFromTheLadderNotIncremented(self):
        """⚠️ `cost + INCREMENT` was wrong the moment the first roll became free — it
        quotes 5 for a roll that actually costs 10."""
        src = self._src()
        self.assertIn('nextCost = shopRerollCost(rerollCount + 1)', src)
        self.assertNotIn('nextCost = cost + SHOP_REROLL_COST_INCREMENT', src)

    def test_freeRerollSkipsSpendFunds(self):
        """A 0 spend would still write a ledger row and fire the Magnate hook."""
        src = self._src()
        body = src.split('def rerollFeaturedCards')[1].split('\n@app.')[0]
        self.assertIn('if cost > 0:', body,
                      'a free reroll must not call spendFunds')
        self.assertIn('currencyRepo.getOrCreate(user.id)', body,
                      'the free path still needs a balance for the response')

    def test_freeIsSurfacedToTheClient(self):
        """A 0 cost is otherwise indistinguishable from a pricing bug, and the button
        should say Free rather than '0 Floobits'."""
        src = self._src()
        self.assertIn('"free": cost == 0', src)


if __name__ == '__main__':
    unittest.main(verbosity=2)
