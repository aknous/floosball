"""Odometer pays per-position yard gates, and its text states exactly what it pays.

A user found the old text ambiguous, and it hid a real problem. Every card paid the
compute's hardcoded fallback (40/80/120/160 yards for +5/+11/+17/+23 FP, max 56) because
minted cards carried roster-scale `gates` the compute never read. One set of gates also
could not fit every position once passing yards count: a QB cleared all four 91% of the
time, a TE 1%, a kicker never. And at a 56 max it averaged ~15 FP a week against ~52 for
other prismatic FP cards.

Now (owner, 2026-09-27): gates per position at that position's own quartiles of weekly
yardage, paying +20/+30/+40/+55 (max 145); kickers cannot mint it; the card face names
its own position's gates.

Run: .venv/bin/python test_odometer_text.py
"""
import os
import re
import sys
import types
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import logging  # noqa: E402
logging.disable(logging.CRITICAL)

from constants import ODOMETER_GATES_BY_POSITION, ODOMETER_GATE_FP  # noqa: E402
from managers.cardEffects import (  # noqa: E402
    _computeOdometer, EFFECT_DETAIL_TEMPLATES, EFFECT_TOOLTIPS, buildEffectConfig,
    effectValidPositions, odometerGatesText,
)


def pay(position, passYards=0, runYards=0, rcvYards=0, primary=None):
    ctx = types.SimpleNamespace(
        weekPlayerStats={7: {
            'passing_stats': {'passYards': passYards},
            'rushing_stats': {'runYards': runYards},
            'receiving_stats': {'rcvYards': rcvYards},
        }},
        rosterPlayerPositions={7: position}, cardPosition=position)
    return _computeOdometer(primary or {}, ctx, 7, None).fpBonus


class OdometerTest(unittest.TestCase):
    TEXT = EFFECT_DETAIL_TEMPLATES['odometer']
    CAP = sum(ODOMETER_GATE_FP)

    def test_each_position_pays_its_own_gates_cumulatively(self):
        for pos, gates in ODOMETER_GATES_BY_POSITION.items():
            running = 0.0
            for yards, amount in zip(gates, ODOMETER_GATE_FP):
                self.assertEqual(pay(pos, runYards=yards - 1), running, f'pos {pos} paid before {yards}')
                running += amount
                self.assertEqual(pay(pos, runYards=yards), running, f'pos {pos} at {yards}')
            self.assertEqual(pay(pos, runYards=5000), self.CAP)

    def test_the_text_states_the_payouts_and_the_cap(self):
        nums = [int(x) for x in re.findall(r'\+(\d+)', self.TEXT)]
        self.assertEqual(tuple(nums[:4]), ODOMETER_GATE_FP)
        self.assertEqual(nums[4], self.CAP)
        self.assertIn(f"up to +{self.CAP} FP", EFFECT_TOOLTIPS['odometer'])

    def test_a_minted_card_names_its_own_gates(self):
        for pos, gates in ODOMETER_GATES_BY_POSITION.items():
            detail = buildEffectConfig('prismatic', 85, pos, forceEffect='odometer')['detail']
            self.assertIn(' / '.join(str(g) for g in gates) + ' yards', detail)
            self.assertNotIn('?', detail)

    def test_stored_card_values_do_not_change_the_payout(self):
        legacy = {'rewardType': 'fp', 'gates': [{'yards': 200, 'fp': 3.8}, {'yards': 400, 'fp': 7.7}]}
        self.assertEqual(pay(3, rcvYards=150, primary=legacy), pay(3, rcvYards=150))

    def test_passing_rushing_and_receiving_all_count(self):
        self.assertIn('passing, rushing and receiving', self.TEXT)
        self.assertEqual(pay(1, passYards=300, runYards=50, rcvYards=0), pay(1, passYards=350))

    def test_kickers_cannot_mint_it_and_an_old_kicker_card_says_so(self):
        self.assertNotIn(5, effectValidPositions('odometer'))
        self.assertEqual(pay(5, runYards=500), 0)
        self.assertIn('pays nothing', odometerGatesText('K'))


class PlacedInThePrismaticBand(unittest.TestCase):
    """Any position clears gate k about as often as any other: the gates are that
    position's own ~25/50/75/90th-percentile weekly yardage, so the mean payout is the same
    rule everywhere. Sized to sit with prismatic FP peers (~52 FP a week)."""

    def test_expected_payout_is_in_the_prismatic_band(self):
        clear = (0.75, 0.50, 0.25, 0.10)
        expected = sum(p * a for p, a in zip(clear, ODOMETER_GATE_FP))
        self.assertGreater(expected, 40)
        self.assertLess(expected, 60)


if __name__ == '__main__':
    unittest.main(verbosity=2)
