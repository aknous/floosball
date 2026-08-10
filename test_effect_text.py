"""A card's two descriptions must not describe two different cards.

Every effect carries user-facing text in two places: the SHOP/TOOLTIP description
(`EFFECT_TOOLTIPS`) and the ON-CARD detail (`EFFECT_DETAIL_TEMPLATES`). They are written and
edited separately, so nothing stops one being updated and the other left behind.

⚠️ THE ON-CARD REBASE DID EXACTLY THAT. Effects were re-based off the depicted player
(docs/CARD_ONCARD_REBASE_PLAN.md), the details and the compute functions were rewritten
to read `cardPlayerId`, and FIVE descriptions were left describing the old
roster-aggregate behaviour — honor_roll, bonsai, catalyst, snake_eyes and walk_off. A
reader comparing the shop text with the card in their hand saw two different effects,
which is how it was reported.
"""

import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from managers.cardEffects import (EFFECT_TOOLTIPS as EFFECT_DESCRIPTIONS,
                                  EFFECT_DETAIL_TEMPLATES as EFFECT_DETAILS,
                                  EFFECT_DISPLAY_NAMES)

ROSTER = re.compile(r'\broster\b', re.I)
SELF = re.compile(r'this player|their own', re.I)


class EffectTextConsistencyTests(unittest.TestCase):
    def testNoEffectDescribesTheRosterWhileItsDetailDescribesOnePlayer(self):
        """THE REGRESSION, stated as the rule it broke.

        A description that talks about your ROSTER while the detail talks about THIS
        player is the exact shape the rebase left behind. It is not a style question:
        the two texts promise different effects.
        """
        offenders = []
        for key in sorted(set(EFFECT_DESCRIPTIONS) & set(EFFECT_DETAILS)):
            desc, detail = EFFECT_DESCRIPTIONS[key], EFFECT_DETAILS[key]
            if ROSTER.search(desc) and SELF.search(detail) and not ROSTER.search(detail):
                offenders.append(f'{key}: "{desc}" vs "{detail}"')
        self.assertEqual(offenders, [], 'description says roster, detail says this player:\n'
                                        + '\n'.join(offenders))

    def testNoEffectDescribesOnePlayerWhileItsDetailDescribesTheRoster(self):
        """The mirror image, so a later fix cannot introduce the opposite drift."""
        offenders = []
        for key in sorted(set(EFFECT_DESCRIPTIONS) & set(EFFECT_DETAILS)):
            desc, detail = EFFECT_DESCRIPTIONS[key], EFFECT_DETAILS[key]
            if SELF.search(desc) and not ROSTER.search(desc) and ROSTER.search(detail):
                offenders.append(f'{key}: "{desc}" vs "{detail}"')
        self.assertEqual(offenders, [], 'description says this player, detail says roster:\n'
                                        + '\n'.join(offenders))

    def testTheFiveReportedEffectsReadAsOnCard(self):
        """Pin the specific ones a user reported, by name."""
        for key in ('honor_roll', 'bonsai', 'catalyst', 'snake_eyes', 'walk_off'):
            self.assertIn(key, EFFECT_DESCRIPTIONS, key)
            self.assertFalse(ROSTER.search(EFFECT_DESCRIPTIONS[key]),
                             f'{key} description still talks about the roster: '
                             f'{EFFECT_DESCRIPTIONS[key]}')

    def testEveryEffectWithADetailHasADescription(self):
        # A card with no shop text is not a contradiction, but it is a hole.
        missing = sorted(set(EFFECT_DETAILS) - set(EFFECT_DESCRIPTIONS))
        self.assertEqual(missing, [], f'details with no description: {missing}')

    def testEveryDescribedEffectHasADisplayName(self):
        missing = sorted(k for k in EFFECT_DESCRIPTIONS if k not in EFFECT_DISPLAY_NAMES)
        self.assertEqual(missing, [], f'described effects with no display name: {missing}')


if __name__ == '__main__':
    unittest.main(verbosity=2)
