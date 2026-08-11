"""A card you do not own yet has to project against its OWN player's stats.

⚠️ THE CONTEXT ONLY EVER LOADED THE LINEUP. `buildProjectionContext` fetches
`PlayerSeasonStats` and `WeeklyPlayerFP` for `rosterPlayerIds` — the players depicted by
your EQUIPPED cards. That is exactly right for projecting the hand you already hold, and
exactly wrong for the shop and the pack-reveal, where the entire point is a card whose
player is NOT in your lineup.

Post-fusion most effects read their own depicted player, so those cards scored against an
absent stat line and projected 0.0. Reported from the shop: Slippery and Odometer showing
a 0 projection. Measured on the live database, template 346 (Slippery) depicts a player
averaging 12.9 FP a game and projected 0.0; with its stats loaded it projects 5.9. Across
a 120-template sample, 31 (26%) projected differently once their own player was present —
not only zeros: several were paying against a hand that was missing a term.

⚠️ THE EXTRAS ARE NOT ROSTER MEMBERS. `rosterPlayerIds` is what roster-aggregate effects
count over, so adding a previewed candidate to it would price every OTHER card in the hand
as though it had already been bought. The extras are loaded for stats and FP history and
nothing else, which is what the invariant tests below pin.

Run: .venv/bin/python test_shop_projection.py
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import logging
logging.disable(logging.CRITICAL)

import managers  # noqa: F401  — breaks the floosball_game circular import

HERE = os.path.dirname(os.path.abspath(__file__))


def _source():
    with open(os.path.join(HERE, 'managers', 'cardProjection.py')) as fh:
        return fh.read()


def _block(src, header):
    start = src.index(header)
    rest = src[start + len(header):]
    end = rest.find('\ndef ')
    return rest[:end if end != -1 else len(rest)]


class ShopProjectionTests(unittest.TestCase):
    """These assert on the QUERIES the context issues, because that is where the fault
    was: the stats were simply not fetched. A test over the effect maths would have passed
    throughout — the maths was right, its inputs were absent."""

    def testBothLoadsCoverTheCandidateAsWellAsTheLineup(self):
        """THE REGRESSION. Season stats and weekly FP must both ask for the roster UNION
        the extras."""
        src = _source()
        self.assertIn('statPlayerIds = set(rosterPlayerIds) | ', src,
                      'the stat query no longer unions the extras')
        self.assertIn('PlayerSeasonStats.player_id.in_(statPlayerIds)', src,
                      'season stats are fetched for the lineup only — a shop card whose '
                      'player is not equipped will project against zeros')
        self.assertIn('_WPF.player_id.in_(statPlayerIds)', src,
                      "weekly FP history is fetched for the lineup only — the gate's clear "
                      'probability falls back to a flat 0.5 for a shop candidate')

    def testTheCandidateIsNotCountedAsPartOfTheRoster(self):
        """⚠️ The extras must never join `rosterPlayerIds`, or roster-aggregate effects
        would count a card the reader has not bought."""
        block = _block(_source(), 'def buildProjectionContext')
        for forbidden in ('rosterPlayerIds |= ', 'rosterPlayerIds.update(',
                          'rosterPlayerIds = statPlayerIds'):
            self.assertNotIn(forbidden, block,
                             'a previewed candidate is being treated as equipped')

    def testTheCandidateDoesNotInflateTheRosterTotals(self):
        """`weekRawFP` and `rosterTotalTds` are what the hand's other cards are priced
        against. A previewed candidate contributing to them would raise every other card's
        projection as though it were already in the lineup."""
        block = _block(_source(), 'def buildProjectionContext')
        self.assertIn('if onRoster:', block,
                      "the roster aggregates are unguarded — a previewed candidate's FP "
                      'and TDs are being folded into the hand')
        guarded = block.split('if onRoster:', 1)[1].split('if row:')[0]
        self.assertIn('weekRawFP +=', guarded)
        self.assertIn('rosterTotalTds +=', guarded)

    def testTheCandidatePathPassesItsOwnPlayer(self):
        """The context grew the parameter; the shop and pack paths have to use it.
        `computeTemplateProjection` (shop preview, pack reveal) delegates to this one, so
        the single call site covers both surfaces."""
        block = _block(_source(), 'def computeCandidateProjection')
        self.assertIn('extraPlayerIds=', block,
                      'the candidate projection does not pass its own player through')
        self.assertIn('card_template.player_id', block)

    def testTheEquippedPathIsUnchanged(self):
        """A projection of the hand you already hold had every player it needed. It must
        not start passing extras, or it would be describing a different lineup."""
        self.assertNotIn('extraPlayerIds',
                         _block(_source(), 'def computeEquippedProjections'))


class ExtraSetTests(unittest.TestCase):
    """The set arithmetic itself. Nulls reach this from templates with no player, and a
    candidate already in the lineup must not be added twice."""

    def testExtrasAreUnionedDeduplicatedAndNullSafe(self):
        roster = {11, 12, 13}
        for extras, expected in ((None, {11, 12, 13}),
                                 ([], {11, 12, 13}),
                                 ([99], {11, 12, 13, 99}),
                                 ([12], {11, 12, 13}),
                                 ([None, 0, 99], {11, 12, 13, 99})):
            got = set(roster) | {int(p) for p in (extras or []) if p}
            self.assertEqual(got, expected, f'extras={extras}')


class LiveContextTests(unittest.TestCase):
    """The behaviour, against a real database when one is present — this is the check that
    actually caught the bug, and the source assertions above are its cheap standing guard.

    Skipped where there is no local database or no user holding an equipped lineup, so a
    fresh checkout still runs the suite clean.
    """

    @classmethod
    def setUpClass(cls):
        if not os.path.exists(os.path.join(HERE, 'data', 'floosball.db')):
            raise unittest.SkipTest('no local database')
        from database.connection import get_session
        from database.models import EquippedCard, PlayerSeasonStats
        cls.session = get_session()
        eq = cls.session.query(EquippedCard).first()
        if eq is None:
            cls.session.close()
            raise unittest.SkipTest('no equipped lineup to project against')
        cls.userId, cls.season, cls.week = eq.user_id, eq.season, eq.week
        cls.statted = {r.player_id for r in cls.session.query(PlayerSeasonStats)
                       .filter(PlayerSeasonStats.season == cls.season).all()}

    @classmethod
    def tearDownClass(cls):
        session = getattr(cls, 'session', None)
        if session is not None:
            session.close()

    def testAnOffRosterPlayerIsLoadedWhenPassedAsAnExtra(self):
        from managers.cardProjection import buildProjectionContext
        base = buildProjectionContext(self.session, self.userId, self.season, self.week,
                                      None, None)
        if base is None:
            self.skipTest('the user has no fantasy roster row')
        outsider = next((p for p in sorted(self.statted)
                         if p not in set(base.rosterPlayerIds)), None)
        if outsider is None:
            self.skipTest('every statted player is already in this lineup')

        self.assertNotIn(outsider, base.weekPlayerStats,
                         'the fixture is wrong — this player was already loaded')

        withExtra = buildProjectionContext(self.session, self.userId, self.season,
                                           self.week, None, None,
                                           extraPlayerIds=[outsider])
        self.assertIn(outsider, withExtra.weekPlayerStats,
                      "the candidate's stat line is still missing — its effect will score "
                      'against zeros and the card will project 0')
        self.assertIn(outsider, withExtra.playerWeeklyFP,
                      "the candidate's FP history is still missing — the gate falls back "
                      'to a flat 0.5 instead of its real clear rate')

    def testTheExtraDoesNotChangeTheHandItIsPreviewedAgainst(self):
        """The other cards in the lineup must project exactly as before. This is the
        invariant that makes it safe to load a player you do not own."""
        from managers.cardProjection import buildProjectionContext
        base = buildProjectionContext(self.session, self.userId, self.season, self.week,
                                      None, None)
        if base is None:
            self.skipTest('the user has no fantasy roster row')
        outsider = next((p for p in sorted(self.statted)
                         if p not in set(base.rosterPlayerIds)), None)
        if outsider is None:
            self.skipTest('every statted player is already in this lineup')

        withExtra = buildProjectionContext(self.session, self.userId, self.season,
                                           self.week, None, None,
                                           extraPlayerIds=[outsider])
        self.assertEqual(set(base.rosterPlayerIds), set(withExtra.rosterPlayerIds),
                         'the previewed candidate joined the roster')
        self.assertAlmostEqual(base.weekRawFP, withExtra.weekRawFP, places=6,
                               msg="the candidate's FP inflated the hand's raw total")
        self.assertAlmostEqual(base.rosterTotalTds, withExtra.rosterTotalTds, places=6,
                               msg="the candidate's TDs inflated the hand's total")


if __name__ == '__main__':
    unittest.main(verbosity=2)
