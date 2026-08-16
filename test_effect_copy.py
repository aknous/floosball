"""Card text must not lie to a new user.

`test_effect_placeholders` proves every `{placeholder}` can be FILLED. That is a
different question from whether the filled sentence is TRUE, or parseable by someone
who has never read the source. This file covers the second.

⚠️ THE ONE THAT WAS ACTIVELY WRONG: Group Round (`bonus_round`) advertised "4 or more
of your other cards" while `_BONUS_ROUND_THRESHOLD` had been raised 4 -> 6 in the fusion.
A user who assembled exactly four triggering cards was told they had earned it and paid
nothing. A number the CODE owns was hardcoded into prose, so moving the constant left the
promise behind. Anything of that shape gets pinned here.

Also covered, all found in the same sweep and all user-visible:
  chain_reaction    detail said "every card in your hand" where the compute counts OTHERS,
                    and the tooltip named "your other 4 cards" — stale, the lineup is six
                    slots plus FLEX. Naming a hand size that moves is the bonus_round bug.
  updraft           interpolated a raw Python list onto the card face ("at each of
                    [299, 391, 483]") while its tooltip quoted 300/400/500 — the detail
                    and the tooltip disagreed about the card's own thresholds.
  lead_blocker      "the TE team's RB" (garbled possessive)
  spotlight_moment  "WR counts either WR scoring a TD." (sentence fragment)
  bonsai            "Every grow slows the next." (not English)
  barrage,
  promised_land     "escalating odds at 71.5 FP on each one" parses as odds AT a value
                    rather than a chance OF one
  rng               en-dash in user-facing copy

Run: .venv/bin/python test_effect_copy.py
"""

import logging
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
logging.disable(logging.CRITICAL)

import managers.cardEffects as CE  # noqa: E402
from managers.cardEffects import buildEffectConfig  # noqa: E402


def rendered():
    """Every mintable effect's text as a user actually sees it, numbers filled in."""
    out = {}
    for edition in ('metallic', 'holographic', 'prismatic', 'diamond'):
        pool = set()
        for pos in (1, 2, 3, 4, 5):
            pool |= set(CE.effectPoolFor(edition, pos))
        for eff in sorted(pool):
            pos = sorted(CE.effectValidPositions(eff) or {3})[0]
            cfg = buildEffectConfig(edition, 85, pos, 10, forceEffect=eff)
            out[eff] = (cfg.get('detail') or '', cfg.get('tooltip') or '')
    return out


RENDERED = rendered()


class ConstantsOwnTheirNumbers(unittest.TestCase):
    """⚠️ A number the CODE decides must not be retyped into prose."""

    def testBonusRoundQuotesTheRealThreshold(self):
        want = CE._BONUS_ROUND_THRESHOLD
        for text in RENDERED['bonus_round']:
            found = re.search(r'(\d+) or more', text)
            self.assertIsNotNone(found, f'bonus_round no longer states a threshold: {text}')
            self.assertEqual(
                int(found.group(1)), want,
                f'text promises {found.group(1)} but _BONUS_ROUND_THRESHOLD is {want} — '
                f'a user hitting the advertised number gets paid nothing')

    def testNoEffectNamesAStaleHandSize(self):
        """The lineup is six slots plus FLEX and has moved before. Text that hardcodes
        'your other N cards' goes stale silently."""
        for eff, (detail, tooltip) in RENDERED.items():
            for text in (detail, tooltip):
                self.assertIsNone(
                    re.search(r'your other \d+ cards', text),
                    f'{eff} hardcodes a hand size: {text}')


class ReadableCopy(unittest.TestCase):
    def testNoRawPythonStructuresOnTheCardFace(self):
        for eff, (detail, tooltip) in RENDERED.items():
            for text in (detail, tooltip):
                self.assertIsNone(re.search(r'\[\s*\d+\s*,', text),
                                  f'{eff} renders a list literal: {text}')
                for junk in ('None', 'True', 'False', '{', '}'):
                    self.assertNotIn(junk, text, f'{eff} leaks {junk!r}: {text}')

    def testDetailAndTooltipDoNotContradictOnNumbers(self):
        """⚠️ Updraft's detail said 299/391/483 and its tooltip said 300/400/500. A
        tooltip may be vaguer than the detail; it may not state DIFFERENT figures."""
        for eff, (detail, tooltip) in RENDERED.items():
            dn = set(re.findall(r'\b(\d{2,4})\b', detail))
            tn = set(re.findall(r'\b(\d{2,4})\b', tooltip))
            self.assertFalse(
                tn - dn - {'20', '10'},   # "inside the 20" / "inside the 10" are field spots
                f'{eff} tooltip states numbers the detail does not: '
                f'{sorted(tn - dn)}\n  D: {detail}\n  T: {tooltip}')

    def testNoEmOrEnDashesInUserFacingCopy(self):
        for eff, (detail, tooltip) in RENDERED.items():
            for text in (detail, tooltip):
                self.assertNotIn('—', text, f'{eff} uses an em-dash: {text}')
                self.assertNotIn('–', text, f'{eff} uses an en-dash: {text}')

    def testKnownGarbledPhrasingsStayFixed(self):
        banned = {
            "team's RB": 'garbled possessive',
            'WR counts either': 'sentence fragment',
            'Every grow': 'not English',
            'escalating odds at': 'parses as odds AT a value, not a chance OF one',
        }
        for eff, (detail, tooltip) in RENDERED.items():
            for text in (detail, tooltip):
                for phrase, why in banned.items():
                    self.assertNotIn(phrase, text, f'{eff} ({why}): {text}')

    def testEveryMintableEffectHasBothADetailAndATooltip(self):
        for eff, (detail, tooltip) in RENDERED.items():
            self.assertTrue(detail.strip(), f'{eff} has no detail line')
            self.assertTrue(tooltip.strip(), f'{eff} has no tooltip')

    def testDetailLinesStayShortEnoughToRead(self):
        """The detail is the always-visible rule text on the card face. Past roughly two
        lines it stops being read."""
        for eff, (detail, _) in RENDERED.items():
            self.assertLess(len(detail), 210,
                            f'{eff} detail is {len(detail)} chars: {detail}')


if __name__ == '__main__':
    unittest.main(verbosity=2)
