"""Every pack's rarity weights must name editions its pool can actually supply.

⚠️ THE STARTER PACK CAME BACK EMPTY IN THE APP. The base-pool change moved its pool to
metallic-only — floor prints stopped being a gift once every one of them became free to
everybody — but left `rarity_weights` at `{'base': 100}`. `_drawPackCards` rolls the
EDITION first and picks a template within it second, so it rolled `base`, found no base
templates in a metallic-only pool, and drew nothing.

⚠️ IT RAISES NOTHING. The two-stage draw skips editions absent from the pool by design (so
a thin pool degrades instead of crashing), which means a pack weighted entirely toward an
absent edition returns an EMPTY pack and looks like a UI bug. That is why this is a static
sweep rather than a single case.
"""
import re
import unittest


def _seedSource():
    return open('database/repositories/card_repositories.py').read()


def _drawSource():
    return open('managers/cardManager.py').read()


class WeightsMatchThePool(unittest.TestCase):

    def testStarterIsWeightedForThePoolItDrawsFrom(self):
        """⚠️ The two halves live in different files, which is how they drifted."""
        draw = _drawSource()
        self.assertIn("if packType.name == 'starter':", draw)
        m = re.search(r"if packType\.name == 'starter':\s*\n\s*allTemplates = \[t for t in allTemplates if t\.edition == '(\w+)'\]", draw)
        self.assertIsNotNone(m, 'the starter pool filter has moved; re-point this test')
        poolEdition = m.group(1)

        seed = _seedSource()
        m2 = re.search(r"name='starter',.*?rarity_weights=\{([^}]*)\}", seed, re.S)
        self.assertIsNotNone(m2, 'could not find the starter weights')
        weights = dict(re.findall(r"'(\w+)':\s*(\d+)", m2.group(1)))
        nonZero = {k for k, v in weights.items() if int(v) > 0}

        self.assertEqual(nonZero, {poolEdition},
                         f'starter draws from {poolEdition!r} but is weighted for {sorted(nonZero)} '
                         f'— every roll that lands outside the pool draws NOTHING')

    def testNoPackWeightsAnEditionItsPoolExcludes(self):
        """⚠️ Every non-starter pack excludes `base`, so none may weight it."""
        seed = _seedSource()
        draw = _drawSource()
        self.assertIn("allTemplates = [t for t in allTemplates if t.edition != 'base']", draw,
                      'the non-starter exclusion has moved; re-point this test')
        offenders = []
        for m in re.finditer(r"name='(\w+)',.*?rarity_weights=(\{[^}]*\}|\w+)", seed, re.S):
            name, weights = m.group(1), m.group(2)
            if name == 'starter' or not weights.startswith('{'):
                continue
            for ed, val in re.findall(r"'(\w+)':\s*(\d+)", weights):
                if ed == 'base' and int(val) > 0:
                    offenders.append(name)
        self.assertFalse(offenders,
                         f'these packs weight `base`, which their pool excludes: {offenders}')

    def testTheSeedRefreshesExistingRows(self):
        """⚠️ Otherwise a weights fix never reaches a live database — and this one had to."""
        self.assertIn('existing.rarity_weights = pt.rarity_weights', _seedSource())


if __name__ == '__main__':
    unittest.main(verbosity=2)
