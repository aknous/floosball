"""Odometer's description states exactly what the card pays.

A user found the old text ambiguous: "Escalating FP as this player piles up yards this
week (40 / 80 / 120 / 160+)" gave no amounts, did not say the gates stack, and did not say
passing yards count (which makes it far stronger on a quarterback). The card pays
_computeOdometer's fallback gates on every card, because minted cards carry roster-scale
`gates` the compute does not read, so the text states those amounts and this test holds
the two together.

Run: .venv/bin/python test_odometer_text.py
"""
import os
import re
import sys
import types
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from managers.cardEffects import _computeOdometer, EFFECT_DETAIL_TEMPLATES  # noqa: E402


def pay(passYards=0, runYards=0, rcvYards=0, primary=None):
    ctx = types.SimpleNamespace(weekPlayerStats={7: {
        'passing_stats': {'passYards': passYards},
        'rushing_stats': {'runYards': runYards},
        'receiving_stats': {'rcvYards': rcvYards},
    }})
    return _computeOdometer(primary or {}, ctx, 7, None).fpBonus


class OdometerTextTest(unittest.TestCase):
    TEXT = EFFECT_DETAIL_TEMPLATES['odometer']

    def test_the_stated_gates_and_amounts_are_what_it_pays(self):
        nums = [float(x) for x in re.findall(r'\d+', self.TEXT)]
        amounts, gates, cap = nums[:4], nums[4:8], nums[8]
        running = 0.0
        for yards, amount in zip(gates, amounts):
            self.assertEqual(pay(runYards=yards - 1), running, f'paid before the {yards}-yard gate')
            running += amount
            self.assertEqual(pay(runYards=yards), running, f'{yards} yards should pay {running}')
        self.assertEqual(cap, running, 'the stated maximum is the sum of the gates')
        self.assertEqual(pay(runYards=900), cap, 'nothing past the last gate')

    def test_minted_gate_tables_do_not_change_the_payout(self):
        # What a real card stores: roster-scale gates the compute ignores.
        minted = {'rewardType': 'fp', 'gates': [{'yards': 200, 'fp': 3.8}, {'yards': 400, 'fp': 7.7},
                                                {'yards': 600, 'fp': 10.6}, {'yards': 800, 'fp': 14.4}]}
        self.assertEqual(pay(runYards=160, primary=minted), pay(runYards=160))

    def test_passing_rushing_and_receiving_all_count(self):
        self.assertIn('passing, rushing and receiving', self.TEXT)
        self.assertEqual(pay(passYards=100, runYards=40, rcvYards=20), pay(runYards=160))


if __name__ == '__main__':
    unittest.main(verbosity=2)
