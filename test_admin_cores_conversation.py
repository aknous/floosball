"""A hand-written Cores conversation threads like the sim's own, and can headline.

The single-line admin endpoint could already post AS a Core, but one line is a remark, not
a conversation. The sim publishes an exchange as one row per turn sharing an `exchangeId`,
and `front_page._groupExchanges` folds those back into ONE feed entry with its turns in
spoken order. Writing that same shape means an authored exchange is indistinguishable
downstream: it threads, renders in each Core's own color, and counts as one row against the
caps.

⚠️ CORES LINES ARE IN `NEVER_LEAD` -- they are voice, not report -- and `pinned` is the one
thing that outranks it. So "make this the headline" IS pinning, which is why the endpoint
defaults the flag on rather than making the caller find it.

Three ways this could have shipped broken, each fixed and pinned below:

  * `_groupExchanges` seeds the grouped entry from whichever turn arrives FIRST, which is
    the NEWEST, so `pinned` was read off the last line of the conversation alone.
  * the pinned fetch is limited in ROWS while `PINNED_MAX` counts ITEMS, so a four-turn
    pinned conversation plus two notices would have fetched a partial exchange and rendered
    it with its opening lines missing -- worse than not pinning it, since it reads complete.
  * deleting one turn would leave the rest published, a conversation with a line torn out.

Run: .venv/bin/python test_admin_cores_conversation.py
"""
import unittest

import front_page
from front_page import _groupExchanges, PINNED_MAX, PINNED_MAX_TURNS, NEVER_LEAD


def turnRow(exchangeId, index, core, text, *, pinned=False, leadWeight=None, count=3):
    """One turn as `_rowsToItems` would hand it to the grouper."""
    return {
        'exchangeId': exchangeId, 'turnIndex': index, 'turnCount': count,
        'core': core, 'coreDisplayName': core.capitalize(),
        'text': text, 'rawText': text, 'rawCategory': 'cores',
        'pinned': pinned, 'leadWeight': leadWeight, 'stats': [],
    }


def conversation(exchangeId='admin-abc', pinned=True, weight=100.0):
    """Newest-first, the order the query returns."""
    lines = [(0, 'vera', 'The instance is holding.'),
             (1, 'pyre', 'It is not holding. It is deciding.'),
             (2, 'aris', 'I love this part.')]
    return [turnRow(exchangeId, i, c, t, pinned=pinned, leadWeight=weight)
            for i, c, t in reversed(lines)]


class ItReadsAsAConversation(unittest.TestCase):

    def test_theTurnsFoldIntoOneEntry(self):
        grouped = _groupExchanges(conversation())
        self.assertEqual(len(grouped), 1, 'an exchange must be a single feed entry')
        self.assertEqual(len(grouped[0]['turns']), 3)

    def test_theTurnsAreInSpokenOrder(self):
        """⚠️ Rows come newest-first, so without the index the reply lands above the line
        it answers and the argument runs backwards."""
        turns = _groupExchanges(conversation())[0]['turns']
        self.assertEqual([t['core'] for t in turns], ['vera', 'pyre', 'aris'])
        self.assertTrue(turns[0]['text'].startswith('The instance'))

    def test_theFlatTextIsTheOpeningLine(self):
        entry = _groupExchanges(conversation())[0]
        self.assertEqual(entry['text'], 'The instance is holding.')
        self.assertEqual(entry['core'], 'vera')


class ItCanHeadline(unittest.TestCase):

    def test_aPinnedConversationIsPinnedAsAWhole(self):
        self.assertTrue(_groupExchanges(conversation(pinned=True))[0]['pinned'])

    def test_oneUnpinnedTurnDoesNotUnpinTheConversation(self):
        """THE GROUPING BUG. The entry is seeded from the newest turn, so a single
        unpinned last line would have dropped the whole exchange out of the lead."""
        rows = conversation(pinned=True)
        rows[0]['pinned'] = False          # the newest turn, i.e. the seed
        self.assertTrue(_groupExchanges(rows)[0]['pinned'])

    def test_theWeightIsTheStrongestTurns(self):
        rows = conversation(weight=100.0)
        rows[0]['leadWeight'] = 1.0
        self.assertEqual(_groupExchanges(rows)[0]['leadWeight'], 100.0)

    def test_pinningIsWhatLetsACoresRowLeadAtAll(self):
        """⚠️ Records the reason the endpoint defaults `pinned` on: without it a Cores
        entry can never be the headline, however heavy its weight."""
        self.assertIn('cores', NEVER_LEAD)
        with open('front_page.py') as fh:
            src = fh.read()
        pick = src.split('def _pickLead')[1] if 'def _pickLead' in src else src
        self.assertIn("item.get('pinned')", pick)

    def test_anUnpinnedConversationIsStillJustVoice(self):
        """The counterpart — posting one WITHOUT pinning must not quietly promote every
        Cores line the sim writes."""
        self.assertFalse(_groupExchanges(conversation(pinned=False))[0]['pinned'])


class ThePinnedFetchHasRoomForIt(unittest.TestCase):

    def test_theRowLimitCoversWholeConversations(self):
        """⚠️ `PINNED_MAX` counts ITEMS; the query limits ROWS. They are the same number
        only until a pinned conversation exists."""
        with open('front_page.py') as fh:
            src = fh.read()
        self.assertIn('.limit(PINNED_MAX * PINNED_MAX_TURNS)', src)
        self.assertGreaterEqual(PINNED_MAX * PINNED_MAX_TURNS, PINNED_MAX)

    def test_theHeadroomMatchesWhatTheEndpointWillAccept(self):
        """Drift here costs a truncated fetch, so it is worth pinning to the real limit.

        ⚠️ Read from source rather than imported: `api.main` pulls in the game engine and
        the manager package, which are circular at import time and only resolve through the
        stub dance in `scenario.py`. One constant is not worth booting that."""
        import re
        with open('api/main.py') as fh:
            match = re.search(r'^ADMIN_CONVERSATION_MAX_TURNS = (\d+)', fh.read(), re.M)
        self.assertIsNotNone(match, 'the endpoint lost its turn limit')
        self.assertGreaterEqual(PINNED_MAX_TURNS, int(match.group(1)))

    def test_aFullyPinnedFeedStillReturnsWholeConversations(self):
        """The failure it prevents: enough pinned rows to exceed a flat limit, with the
        conversation's opening lines the ones that would have been cut."""
        rows = []
        for n in range(PINNED_MAX - 1):
            rows.append({'exchangeId': None, 'rawCategory': 'announcement',
                         'pinned': True, 'text': f'notice {n}', 'stats': []})
        rows = conversation() + rows
        self.assertLessEqual(len(rows), PINNED_MAX * PINNED_MAX_TURNS,
                             'the fetch limit must cover this shape')
        grouped = _groupExchanges(rows)
        exchange = [g for g in grouped if g.get('turns')][0]
        self.assertEqual(len(exchange['turns']), 3, 'the conversation lost a line')


class TheEndpointIsShaped(unittest.TestCase):
    """Structural, since driving FastAPI here would need a live app and a session."""

    def _endpoint(self):
        with open('api/main.py') as fh:
            src = fh.read()
        return src.split('async def admin_post_cores_conversation')[1].split('\n@app.')[0]

    def test_everyTurnSharesOneExchangeIdAndCarriesItsPosition(self):
        body = self._endpoint()
        self.assertIn('exchangeId=exchangeId', body)
        self.assertIn('turnIndex=index', body)
        self.assertIn('turnCount=len(turns)', body)

    def test_itPostsAsCoresRatherThanAsAnAnnouncement(self):
        body = self._endpoint()
        self.assertIn("category='cores'", body)

    def test_itIsMarkedHandWrittenSoItCanBeManaged(self):
        """Without the admin event type the row is indistinguishable from the Cores'
        own chatter, and the management list would refuse to edit or delete it."""
        self.assertIn('eventType=ADMIN_POST_EVENT_TYPE', self._endpoint())

    def test_headliningIsTheDefault(self):
        self.assertIn('if "pinned" not in payload:', self._endpoint())

    def test_onlyRealCoresMaySpeak(self):
        self.assertIn('_ANNOUNCEMENT_CORES', self._endpoint())

    def test_deletingRemovesTheWholeConversation(self):
        with open('api/main.py') as fh:
            src = fh.read()
        body = src.split('async def admin_delete_league_news')[1].split('\n@app.')[0]
        self.assertIn('exchange_id == exchangeId', body)
        self.assertIn('event_type == ADMIN_POST_EVENT_TYPE', body,
                      'deleting by exchange must not reach the sim\'s own rows')


if __name__ == '__main__':
    unittest.main(verbosity=2)
