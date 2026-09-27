"""A promoted prospect on his promotion contract can only stay rostered or be traded.

Owner, 2026-09-27: GMs must not cut rostered prospects to make room for a trade (or for
anything else). The promotion contract runs at least his seasons left in the pipeline
(`promotionTerm`), and for that whole contract he is protected at every cut path, not
just in the offseason he was promoted (`wasPromotedThisOffseason`, in memory).

Run: .venv/bin/python test_prospect_contract_protection.py
"""

import os
import re
import sys
import types
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from managers.playerManager import isCutProtected, stampPromotion  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))


def _src(rel):
    with open(os.path.join(HERE, rel)) as f:
        return f.read()


class ProspectContractProtectionTest(unittest.TestCase):
    def test_protected_for_the_whole_promotion_contract(self):
        p = types.SimpleNamespace(onProspectContract=True)
        for season in (7, 8, 9):                    # long after the promotion offseason
            self.assertTrue(isCutProtected(p, season))

    def test_ordinary_player_is_cuttable(self):
        self.assertFalse(isCutProtected(types.SimpleNamespace(), 8))
        self.assertFalse(isCutProtected(None, 8))

    def test_same_offseason_promotion_still_protected(self):
        p = types.SimpleNamespace()
        stampPromotion(p, 7)
        self.assertTrue(isCutProtected(p, 7))

    def test_every_cut_decider_reads_the_one_predicate(self):
        # The four deciders that reach a roster to cut someone.
        for rel in ('managers/frontOfficeBrain.py', 'managers/tradeManager.py',
                    'managers/playerManager.py', 'managers/seasonManager.py'):
            src = _src(rel)
            self.assertIn('isCutProtected(', src, rel)
            # No decider may fall back to the narrower, in-memory predicate.
            calls = [m.start() for m in re.finditer(r'\bwasPromotedThisOffseason\(', src)]
            if rel == 'managers/playerManager.py':
                # defined there, and used only inside isCutProtected
                self.assertEqual(len(calls), 2, calls)
            else:
                self.assertEqual(calls, [], rel)

    def test_every_promotion_site_sets_the_flag(self):
        total = sum(_src(rel).count('.onProspectContract = True')
                    for rel in ('managers/playerManager.py', 'managers/seasonManager.py',
                                'managers/tradeManager.py'))
        self.assertEqual(total, 3)

    def test_flag_clears_when_the_contract_runs_out(self):
        src = _src('managers/seasonManager.py')
        i = src.index('player.termRemaining -= 1')
        self.assertIn('player.onProspectContract = False', src[i:i + 500])

    def test_flag_reaches_the_pages(self):
        # The team roster and the player payload both carry it, for the PROSPECT tag.
        self.assertIn("'protectedProspect': bool(getattr(player, 'onProspectContract', False))",
                      _src('api/main.py'))
        self.assertIn("'protectedProspect': bool(getattr(player, 'onProspectContract', False))",
                      _src('api_response_builders.py'))

    def test_flag_is_persisted(self):
        pm = _src('managers/playerManager.py')
        self.assertIn("player.onProspectContract = bool(getattr(db_player, 'on_prospect_contract'", pm)
        self.assertIn("db_player.on_prospect_contract = bool(getattr(player, 'onProspectContract'", pm)
        self.assertIn("on_prospect_contract=bool(getattr(player, 'onProspectContract'", pm)
        self.assertIn("('on_prospect_contract', 'BOOLEAN DEFAULT 0')", _src('database/connection.py'))


if __name__ == '__main__':
    unittest.main(verbosity=2)
