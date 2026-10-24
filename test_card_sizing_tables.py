"""Regression: every card-sizing table names keys the card actually mints.

_BAND_TRIM, _DIAMOND_SIZE, _BAND_LIFT and _SYNERGY_LIFT scale a card's payout keys at mint by name. A
misspelled or renamed key is not an error, it is a silent no-op: the card simply keeps its
old size while the table claims otherwise. This mints every listed card at every position
it can take and checks each named key is present and numeric (or a tier list).

Run: python3 test_card_sizing_tables.py
"""
import unittest

import managers.cardEffects as ce


def positions(effect):
    return [p for p in (1, 2, 3, 4, 5) if p in (ce.effectValidPositions(effect) or set())]


class SizingTablesNameRealKeys(unittest.TestCase):

    def _check(self, table, keysOf):
        for effect, entry in table.items():
            edition = ce.EFFECT_EDITION_TIER[effect]
            pos = positions(effect)
            self.assertTrue(pos, f"{effect} mints nowhere")
            for p in pos:
                primary = ce.buildEffectConfig(edition, 92, p, forceEffect=effect)["primary"]
                for key in keysOf(entry):
                    self.assertIn(key, primary, f"{effect} at {p}: no '{key}' to scale")
                    self.assertTrue(isinstance(primary[key], (int, float, list)),
                                    f"{effect}.{key} is {type(primary[key]).__name__}")

    def testBandTrim(self):
        self._check(ce._BAND_TRIM, lambda entry: entry[1])

    def testDiamondSize(self):
        self._check(ce._DIAMOND_SIZE, lambda entry: entry[1].keys())

    def testBandLift(self):
        self._check(ce._BAND_LIFT, lambda entry: entry[1].keys())

    def testSynergyLift(self):
        self._check(ce._SYNERGY_LIFT, lambda entry: entry[1].keys())

    def testSynergyLiftLands(self):
        """The lift reaches the minted card, and the text quotes the lifted number."""
        saved = dict(ce._SYNERGY_LIFT)
        try:
            lifted = ce.buildEffectConfig("diamond", 92, 1, forceEffect="catalyst")
            ce._SYNERGY_LIFT.clear()
            plain = ce.buildEffectConfig("diamond", 92, 1, forceEffect="catalyst")
        finally:
            ce._SYNERGY_LIFT.update(saved)
        factor = saved["catalyst"][0]
        self.assertAlmostEqual(lifted["primary"]["perFpPct"],
                               plain["primary"]["perFpPct"] * factor, places=2)
        shown = lifted["primary"]["perFpPctDisplay"]
        self.assertAlmostEqual(shown, round(lifted["primary"]["perFpPct"] * 100, 1))
        self.assertIn(f"+{shown}%", lifted["detail"])
        self.assertIn(f"+{lifted['primary']['maxBoostDisplay']}%", lifted["detail"])

    def testLiftFactorsAreCapped(self):
        """A factor over 4x turns a rare week into a jackpot rather than lifting the card."""
        for effect, (factor, _) in ce._BAND_LIFT.items():
            for f in (factor.values() if isinstance(factor, dict) else [factor]):
                self.assertLessEqual(f, 4.0, effect)


if __name__ == "__main__":
    unittest.main()
