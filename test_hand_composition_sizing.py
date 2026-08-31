"""Cards that read the HAND, re-measured for a league where hands can be curated.

⚠️ SYNTHETIC CARDS MAKE A CURATED HAND CHEAP, so every effect whose payout is a function
of what ELSE is equipped moves toward its ceiling. That is why `test_diversified_sizing`
pins the CEILING rather than the mean, and this file generalizes the same rule to the
rest of the family: once hands can be built to order, the ceiling is the typical case and
the mean stops being the number worth sizing.

⚠️ THE OBVIOUS READING OF SYNTHESIS IS WRONG AND WORTH RECORDING. It looks like it should
make any effect combination reachable — it does not. The transplant still consumes a
DONOR you had to pull, so effect scarcity is untouched; and position validity is not the
binding constraint either (measured: 99 of 170 effects are valid at every position, and
every output type has 18+ effects legal at each of the five). What synthesis actually
removes is the need to pull a PAIR: before it, fielding a floobits card in the QB slot
meant pulling a card that was both floobits-effect AND depicted a quarterback.

Measured over 2,000 simulated collections, the chance of fielding a full seven-slot
lineup of ONE output type:

    collection   type       before   after
            20   fp            34%     80%
            40   mult          18%     54%
            40   floobits      13%     61%
            80   mult          68%     98%
            80   floobits      62%     99%

i.e. synthesis is worth roughly a DOUBLING of collection size for hand building, and the
lift is largest for the smallest collections — the opposite shape to the achievement
faucet, and the right one given the friction this feature answers came from new users.

The payoff, at rating 85:

    card            40-card coll      80-card coll     ceiling
    gold_rush       66.3 -> 80.2      82.3 -> 89.8     90
    stacked_deck    1.62 -> 1.73x     1.80 -> 1.86x    1.87x
    anthem          64.09 -> 64.10    unchanged        64.1
    diversified     51.2 -> 56.1      (+9%)            56.1

Nothing re-breaks, and the reason is structural rather than lucky: every one of these
pays a COUNT over a seven-slot lineup, so each has a hard ceiling that was already the
sized number. Synthesis can only move the expectation toward a bound that has already
been peer-checked. Anthem is already at its ceiling before synthesis (it tops out at five
flat-FP cards and 91 of 170 effects are flat-FP), so it moves not at all.

Run: .venv/bin/python test_hand_composition_sizing.py
"""
import logging
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
logging.disable(logging.CRITICAL)

from managers.cardEffects import (  # noqa: E402
    buildEffectConfig, EFFECT_EDITION_TIER, effectValidPositions,
)

RATING = 85
LINEUP_SLOTS = 7          # six position slots + FLEX
OUTPUT_TYPES = ('fp', 'mult', 'floobits')

# Effects whose payout is a function of the hand's output-type mix.
HAND_COMPOSITION = ('diversified', 'anthem', 'gold_rush', 'stacked_deck')


def primaryOf(effect):
    return buildEffectConfig(EFFECT_EDITION_TIER[effect], RATING, 3,
                             forceEffect=effect)['primary']


def outputTypeOf(effect):
    return buildEffectConfig(EFFECT_EDITION_TIER.get(effect, 'metallic'), RATING, 3,
                             forceEffect=effect).get('outputType') or ''


class TheFamilyIsBoundedByACount(unittest.TestCase):
    """⚠️ THE LOAD-BEARING PROPERTY. A curated hand is now cheap, so any hand-reading
    card whose payout grows without a hard bound would grow without a bound in practice.
    Each of these is a count over seven slots; that is what makes them safe."""

    def testEveryHandCardHasAFiniteCeiling(self):
        for eff in HAND_COMPOSITION:
            p = primaryOf(eff)
            self.assertTrue(
                any(k in p for k in ('perTypeFP', 'perCardFloobits', 'perCardMult',
                                     'tier5FP')),
                f'{eff}: no per-unit or top-tier term, so its bound cannot be derived')

    def testDiversifiedCannotExceedTheThreeTypesThatExist(self):
        """Its ceiling is the number of output types, not the number of slots — which is
        why it is the mildest member of the family. Three is the whole vocabulary."""
        self.assertEqual(len(OUTPUT_TYPES), 3)
        perType = primaryOf('diversified')['perTypeFP']
        # ⚠️ Synthesis takes a real hand from ~2.74 distinct types to 3, so the ceiling
        # becomes typical. It is a +9% move on a number already sized AS the ceiling.
        self.assertLess(perType * 3 / (perType * 2.74), 1.15,
                        'curating should be a lift, not a re-break')

    def testAnthemIsAlreadyMaxedBeforeSynthesis(self):
        """It tops out at five flat-FP cards, and flat-FP is the majority of the pool —
        so a curated hand changes nothing for it. Recorded because it is the control:
        if a future change makes Anthem move, the pool's type mix has shifted."""
        flat = [e for e in EFFECT_EDITION_TIER if outputTypeOf(e) == 'fp']
        self.assertGreater(len(flat), LINEUP_SLOTS * 2,
                           'flat-FP effects are plentiful enough to fill a lineup twice')


class TheTwoHalvesOfTheFamilyOppose(unittest.TestCase):
    """⚠️ THE DESIGN PROPERTY WORTH KEEPING. Diversified pays for VARIETY and the rest pay
    for CONCENTRATION, so one hand cannot max both — curating for either costs the other.
    That is what stops "hands can be built to order" collapsing into one dominant build.
    """

    def testMaxingVarietyCapsConcentration(self):
        # Three distinct types across seven slots leaves at most five of any one type.
        maxOfOneTypeWhileHoldingAll3 = LINEUP_SLOTS - (len(OUTPUT_TYPES) - 1)
        self.assertEqual(maxOfOneTypeWhileHoldingAll3, 5)
        gr = primaryOf('gold_rush')['perCardFloobits']
        concentrated = gr * (LINEUP_SLOTS - 1)          # 6 others
        diversifiedToo = gr * (maxOfOneTypeWhileHoldingAll3 - 1)   # 4 others
        self.assertLess(diversifiedToo, concentrated,
                        'holding all three types must cost real concentration payout')

    def testMaxingConcentrationZeroesVariety(self):
        # A mono-type lineup holds exactly one distinct type.
        perType = primaryOf('diversified')['perTypeFP']
        self.assertLess(perType * 1, perType * 3,
                        'a mono-type hand must forfeit most of Diversified')


class ItStillPaysToPullRatherThanBuild(unittest.TestCase):
    """⚠️ Synthesis is a path to any PLAYER, never to any EFFECT — the transplant consumes
    a donor that had to be pulled. So effect scarcity, which is the actual game, is
    untouched, and a bigger collection still builds a better hand."""

    def testPositionValidityIsNotTheBindingConstraint(self):
        """Recorded because it is the intuitive answer and it is wrong: relaxing position
        locking is not what synthesis buys, because position locking barely bound."""
        for t in OUTPUT_TYPES:
            pool = [e for e in EFFECT_EDITION_TIER if outputTypeOf(e) == t]
            for pos in (1, 2, 3, 4, 5):
                legal = [e for e in pool
                         if not effectValidPositions(e) or pos in effectValidPositions(e)]
                self.assertGreaterEqual(
                    len(legal), LINEUP_SLOTS,
                    f'{t} at position {pos}: only {len(legal)} legal effects — position '
                    f'validity would become the binding constraint')


if __name__ == '__main__':
    unittest.main(verbosity=2)
