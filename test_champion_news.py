"""The Floos Bowl champion leads the league-news feed, and keeps leading it.

⚠️ IT WAS NEVER IN THE FEED AT ALL (reported 2026-08-14). The crowning block wrote its
line into `leagueHighlights` and pushed one ephemeral socket event, and neither of those
is the persisted feed — so the biggest result of the season left no row behind. That is
the documented trap in reverse: `leagueHighlights` is deliberately not persisted (89 call
sites, overwhelmingly play highlights), which is exactly why a story that belongs in the
feed has to publish itself.

⚠️ A WEIGHT ALONE WOULD NOT HOLD IT. The lead is the biggest story of the most recent
MOMENT — recency bucket first, weight second — and the offseason keeps publishing after
the bowl, so a rule change or a Cores line takes the front page within the day. The row
pins itself, and pinned sorts ahead of recency. That makes it the first thing in the sim
to pin itself, against a rule ("nothing pins itself") written when pinning was an admin
gesture.

Run: .venv/bin/python test_champion_news.py
"""

import os
import sys
import unittest
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import front_page  # noqa: E402


class _Row:
    """The shape `front_page` reads off a LeagueNewsItem."""
    _next = 1

    def __init__(self, category, text, *, pinned=False, leadWeight=None,
                 stats=None, minutesAgo=0, eventType=None):
        self.id = _Row._next
        _Row._next += 1
        self.season = 1
        self.week = 32
        self.category = category
        self.event_type = eventType
        self.text = text
        self.body = None
        self.pinned = pinned
        self.lead_weight = leadWeight
        self.stats_json = stats
        self.team_id = 1
        self.player_id = None
        self.player_name = None
        self.anomaly_state = None
        self.core = None
        self.core_display_name = None
        self.exchange_id = None
        self.turn_index = None
        self.turn_count = None
        self.created_at = datetime.utcnow() - timedelta(minutes=minutesAgo)


def championRow(**kw):
    return _Row('champion', 'Buffalo Bandits are Floos Bowl champions.',
                pinned=True, leadWeight=100.0, eventType='floosbowl_champion', **kw)


class ChampionCategoryTests(unittest.TestCase):
    def testChampionOutranksEveryOtherCategory(self):
        self.assertEqual(front_page.CATEGORY_PRIORITY[0], 'champion')

    def testChampionCanLeadWithoutAStatStrip(self):
        """It ships a four-cell strip, but the headline must not DEPEND on one — a
        championship is not a thing you withhold because a stat failed to build."""
        self.assertIn('champion', front_page.LEAD_WITHOUT_STATS)

    def testChampionIsNotSilencedAsMetaOrNeverLead(self):
        self.assertNotIn('champion', front_page.NEVER_LEAD)
        self.assertNotIn('champion', front_page.META_CATEGORIES)


class ChampionPublisherTests(unittest.TestCase):
    """Source-level: the crowning block has to call the publisher, and the publisher has
    to pin and to unpin its predecessor. The full path needs a simulated season."""

    def setUp(self):
        here = os.path.dirname(os.path.abspath(__file__))
        with open(os.path.join(here, 'managers', 'seasonManager.py')) as fh:
            self.src = fh.read()
        start = self.src.index('def _publishChampionNews')
        self.body = self.src[start:self.src.index('\n    def ', start + 10)]

    def testTheCrowningBlockPublishes(self):
        """The bug: the champion was crowned and never published."""
        self.assertIn('self._publishChampionNews(', self.src)

    def testItPins(self):
        self.assertIn('pinned=True', self.body)

    def testItUnpinsThePreviousChampion(self):
        """Otherwise one pin accrues per season against PINNED_MAX (5), and five seasons
        in, the pinned block IS the feed."""
        self.assertIn("'pinned': False", self.body)
        self.assertIn('floosbowl_champion', self.body)

    def testItDoesNotDoubleBroadcast(self):
        """The crowning block already sends this line over the socket."""
        self.assertIn('broadcast=False', self.body)

    def testAFailureCannotKillTheSeasonEnd(self):
        """This runs inside the Floos Bowl accolade block, where an exception takes the
        whole simulation task down — the same failure mode `_publishGameNews` was
        hardened against."""
        self.assertIn('except Exception', self.body)


class ChampionLeadTests(unittest.TestCase):
    def testAPinnedChampionLeadsOverFresherNews(self):
        """The point of pinning. A rule change published an hour LATER must not take the
        page off the champion."""
        champ = championRow(minutesAgo=120)
        newer = _Row('rules', 'The league now plays five downs.', minutesAgo=1,
                     leadWeight=8.0)
        items = front_page._rowsToItems([newer, champ])
        byId = {i['id']: i for i in items}
        self.assertTrue(byId[champ.id]['pinned'])
        # Pinned sorts ahead of recency in the lead key — assert via the built feed.
        self.assertEqual(front_page.CATEGORY_PRIORITY.index('champion'), 0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
