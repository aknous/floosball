"""A card is conditional when its payout is all-or-nothing on a condition.

⚠️ THE CATEGORY IS NOT A LABEL. `EFFECT_CATEGORY` decides three things: the blue
Conditional badge and its "triggers when a game condition is met" tooltip, param-builder
dispatch, and — the one that costs Floobits — the **longshot** weekly modifier, which
doubles FP, Floobits AND FPx for anything categorised conditional
(`cardEffectCalculator.py`). Longshot is 10 of 83 in the modifier roll, about one week in
eight.

Five effects drifted in by being REWORKED from a gate into a count and keeping the label:

  showoff       was "FP when your slot outperforms their rating", became per 5-star player
  believe       became per favourite-team season win
  comeback_kid  became per roster player whose club missed the playoffs
  domination    became per roster player on a top-6 club
  walk_off      became per Q4/OT score by this player

Each pays PROPORTIONALLY, with nothing to satisfy — and Longshot was doubling the whole
card for it. Reported by a user asking why Showoff counts as conditional.

`mismatch` stays conditional (owner): per-TD plus a real bonus tier at the threshold.

Run: .venv/bin/python test_effect_categories.py
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import logging
logging.disable(logging.CRITICAL)

import managers  # noqa: F401  — breaks the floosball_game circular import
from managers.cardEffects import (EFFECT_CATEGORY, EFFECT_EDITION_TIER,
                                  buildEffectConfig, effectPoolFor)

# The five that moved, and what they mint, so a re-categorisation can never quietly
# re-price them: their param branches still live in the conditional builder and are
# reached through _EFFECT_BUILDER_OVERRIDES.
MOVED = {
    'showoff': 'perStarFP',
    'believe': 'perWinFP',
    'comeback_kid': 'perPlayerFP',
    'domination': 'perPlayerFP',
    'walk_off': 'perScoreFP',
}

STILL_CONDITIONAL = ('bandwagon', 'reclamation', 'pedigree', 'mismatch')


class EffectCategoryTests(unittest.TestCase):
    def testAnAccumulatorIsNotConditional(self):
        """THE REGRESSION, by name. Each of these pays per something."""
        for name in MOVED:
            self.assertNotEqual(
                EFFECT_CATEGORY.get(name), 'conditional',
                f'{name} pays per unit with no gate — as "conditional" the longshot '
                f'modifier doubles it for meeting no condition')

    def testTheGatedOnesKeptTheirCategory(self):
        """The other half of the rule: a real all-or-nothing gate stays conditional, or
        the modifier ends up with nothing to double."""
        for name in STILL_CONDITIONAL:
            self.assertEqual(EFFECT_CATEGORY.get(name), 'conditional', name)

    def testTheMoveDidNotRepriceAnything(self):
        """Category drives param dispatch, so moving one without an override sends it to
        a different builder — which is how a re-label becomes a re-pricing."""
        for name, key in MOVED.items():
            edition = EFFECT_EDITION_TIER[name]
            for position in (1, 2, 3, 4, 5):
                cfg = buildEffectConfig(edition, 88, position, forceEffect=name)
                primary = (cfg or {}).get('primary') or {}
                self.assertIn(key, primary,
                              f'{name} at position {position} lost its {key} param — '
                              f'check _EFFECT_BUILDER_OVERRIDES')
                self.assertGreater(primary[key], 0, f'{name} minted a zero {key}')

    def testLongshotStillHasCardsToDouble(self):
        """A modifier whose whole job is doubling conditional cards needs some to be
        mintable, or it is a dead week for everyone holding one."""
        mintable = [n for n, cat in EFFECT_CATEGORY.items()
                    if cat == 'conditional'
                    and any(n in effectPoolFor(EFFECT_EDITION_TIER[n], pos)
                            for pos in (1, 2, 3, 4, 5))]
        self.assertTrue(mintable, 'no conditional effect can be minted at all')
        # Documented, not asserted tightly: four are mintable today (bandwagon, medium,
        # mismatch, pedigree) — reclamation is retired-dormant. If this drops to one,
        # Longshot has effectively stopped existing.
        self.assertGreaterEqual(len(mintable), 2,
                                f'only {mintable} left for longshot to double')


if __name__ == '__main__':
    unittest.main(verbosity=2)
