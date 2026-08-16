"""Every stat a card scores off has somewhere a user can go and read it.

⚠️ A CARD CAN PAY ON A NUMBER THE GAME NEVER SHOWS YOU. Roughly twenty mintable effects
key off stats that appeared on no table in the app: well-placed and bad throws, air
yards, yards after contact, broken tackles, stuffs, contested catches and targets,
bailouts, punt placement, punt return yards. The sim records all of them and the API has
always sent them inside the stat blobs — they were being dropped at the last step, in the
frontend, which rendered only the standard line.

So a card read "+0.03 FPx per 5 well-placed throws" and there was nowhere to find out how
many your quarterback had.

This file guards the two halves of the contract:

  1. Every key a card reads is a key the sim actually writes. A card scoring off a stat
     nobody records is a dead card, and it fails silently — the effect computes 0 and
     looks like a quiet week.
  2. Every key the player page's CARD STATS view displays is one of those same keys, so
     the view cannot drift into showing a column that is permanently blank.

⚠️ Card code reads CARD FORMAT, not DB format. `fantasyTracker._buildCardStatFormat`
renames on the way through — the DB stores `fg40+` and a card asks for `fg40plus`,
`rcvYards` is the card-format name for the DB's receiving `yards`. Checking card reads
against raw DB keys reports false failures on both, which is exactly the mistake that
made Sniper look like a dead card when it works correctly.

Run: .venv/bin/python test_card_stat_visibility.py
"""

import logging
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
logging.disable(logging.CRITICAL)

from floosball_player import playerStatsDict  # noqa: E402
from managers.fantasyTracker import _dbStatsToCardFormat  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
PLAYER_PAGE = os.path.join(
    os.path.dirname(HERE), 'floosball-react', 'src', 'Views', 'Players', 'PlayerPage.tsx')

# The advanced stats that exist BECAUSE cards score off them. Each maps to the group it
# lives in. Standard box-score stats are covered by the ordinary tables and not listed.
CARD_STATS = {
    'passing': ('goodThrows', 'badThrows', 'throws', 'airYardsSum', 'sacked'),
    'rushing': ('yardsAfterContact', 'brokenTackles', 'stuffs'),
    'receiving': ('yac', 'contestedCatches', 'contestedTargets', 'bailouts', 'drops'),
    'kicking': ('punts', 'puntsInside20', 'puntsInside10', 'puntTouchbacks'),
    'returning': ('puntReturnYards', 'puntReturnTds'),
}


class TheSimRecordsThem(unittest.TestCase):
    """Half one: a card cannot score off a stat nobody writes."""

    def testTheCanonicalTemplateCarriesEveryCardStat(self):
        for group, keys in CARD_STATS.items():
            stored = playerStatsDict.get(group) or {}
            for key in keys:
                self.assertIn(
                    key, stored,
                    f'{group}.{key} is read by a card but is not in playerStatsDict, so '
                    f'nothing accumulates it and the effect silently scores 0')

    def testTheCardFormatConverterCarriesThemThrough(self):
        """⚠️ Cards read CARD format, not DB format, and the converter RENAMES some keys.
        This is the step that made Sniper look dead: the DB stores `fg40+` and the card
        asks for `fg40plus`, so checking the card's key against the DB blob reports a
        failure on code that is correct."""
        card = _dbStatsToCardFormat(
            {'goodThrows': 9, 'badThrows': 2, 'throws': 30, 'airYardsSum': 210, 'sacked': 1},
            {'yardsAfterContact': 44, 'brokenTackles': 3, 'stuffs': 2},
            {'yac': 51, 'contestedCatches': 2, 'contestedTargets': 4, 'bailouts': 1, 'drops': 1},
            {'punts': 4, 'puntsInside20': 2, 'puntsInside10': 1, 'puntTouchbacks': 1,
             'fg40+': 3},
            12.0,
            returningStats={'puntReturnYards': 38, 'puntReturnTds': 1},
        )
        for group, keys in CARD_STATS.items():
            blob = card.get(f'{group}_stats') or {}
            for key in keys:
                self.assertIn(key, blob, f'{group}_stats.{key} lost in the card format')
                self.assertGreater(blob[key], 0, f'{group}_stats.{key} came through as 0')

    def testTheRenamedKickerKeyStillArrives(self):
        """`fg40+` in the DB becomes `fg40plus` for cards. Sniper depends on it."""
        card = _dbStatsToCardFormat({}, {}, {}, {'fg40+': 3, 'fgs': 4}, 0)
        self.assertEqual(card['kicking_stats']['fg40plus'], 3)


class TheApiSendsThem(unittest.TestCase):
    def testThePlayerDetailRowIncludesReturning(self):
        """⚠️ Return production was the one group the player endpoint dropped, and two
        cards score off it. Without it a profile could not show the stat its own card is
        paying on."""
        with open(os.path.join(HERE, 'api', 'main.py')) as fh:
            src = fh.read()
        self.assertIn("'returning': getattr(row, 'returning_stats', None) or {}", src)

    def testTheStatsRowSendsWholeBlobsRatherThanAWhitelist(self):
        """The stats endpoint forwards each blob entire, which is why these stats reach a
        client at all. A whitelist here would silently drop every future metric."""
        with open(os.path.join(HERE, 'api', 'main.py')) as fh:
            src = fh.read()
        block = src[src.index('def _statsPlayerRow'):]
        block = block[:block.index('\ndef ', 10)]
        for group in ('passing', 'rushing', 'receiving', 'kicking', 'returning'):
            self.assertIn(f"'{group}': blobs.get('{group}') or {{}}", block,
                          f'{group} is no longer forwarded whole')


@unittest.skipUnless(os.path.exists(PLAYER_PAGE), 'frontend repo not checked out alongside')
class ThePlayerPageShowsThem(unittest.TestCase):
    """Half two: the view cannot drift into a column that is permanently blank."""

    def _cardStatBlock(self) -> str:
        with open(PLAYER_PAGE) as fh:
            src = fh.read()
        start = src.index('const CARD_STAT_COLUMNS')
        return src[start:src.index('CARD_STAT_COLUMNS.TE', start)]

    def testEveryDisplayedKeyIsOneTheSimWrites(self):
        block = self._cardStatBlock()
        known = {k for keys in CARD_STATS.values() for k in keys}
        # Derived columns compute from parts rather than reading a stored key.
        derived = {'20+', 'fg40to50', 'fgOver50', 'gp'}
        found = set(re.findall(r"r\.(?:passing|rushing|receiving|kicking|returning)\?\.(\w+)", block))
        found |= set(re.findall(r"r\.(?:passing|rushing|receiving|kicking|returning)\?\.\['([\w+]+)'\]", block))
        for key in found - derived:
            self.assertIn(
                key, known,
                f'the CARD STATS view reads {key}, which no card scores off and this '
                f'file does not list as recorded')

    def testTheHeadlineCardStatsAreAllPresent(self):
        """The ones users were specifically unable to see."""
        block = self._cardStatBlock()
        for key in ('goodThrows', 'badThrows', 'yardsAfterContact', 'brokenTackles',
                    'contestedCatches', 'bailouts', 'yac', 'puntsInside20',
                    'puntReturnYards'):
            self.assertIn(key, block, f'{key} is not shown anywhere on the player page')

    def testEveryPositionHasAView(self):
        block = self._cardStatBlock()
        for position in ('QB:', 'RB:', 'WR:', 'K:'):
            self.assertIn(position, block, f'no card-stat columns for {position}')


if __name__ == '__main__':
    unittest.main(verbosity=2)
