"""Veteran counts the weeks a reader actually fielded a lineup.

⚠️ IT COUNTED OFF TABLES THE FUSION LEFT UNWRITTEN. `_creditVeteranForWeek` selected
users from `FantasyRoster` whose id appeared in `FantasyRosterPlayer` — and the
fantasy/cards fusion made the EQUIPPED CARDS the roster, so nothing writes those tables
any more. Measured on a live database: `fantasy_roster_players` holds 0 rows while
`equipped_cards` holds 24, so the subquery matched nothing and NOBODY was ever credited.
Reported as Veteran never tracking progress, and confirmed by the owner.

The same fault took Field General's backfill; the note above it in `achievementManager`
says so. This is that fault's second appearance.

Two things had to be true:

  1. the weekly credit reads a table that is actually written, and
  2. the season's already-played weeks are not lost — fixing the hook alone would start
     everyone from zero after a season of playing.

Run: .venv/bin/python test_veteran_progress.py
"""

import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import logging
logging.disable(logging.CRITICAL)

import managers  # noqa: F401  — breaks the floosball_game circular import


def _source(path):
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), path)) as fh:
        return fh.read()


class VeteranProgressTests(unittest.TestCase):
    def testTheWeeklyCreditDoesNotReadTheDeadTables(self):
        """THE REGRESSION, stated as the rule it broke. FantasyRoster and
        FantasyRosterPlayer are unwritten under the fusion — anything gating a credit on
        them credits nobody."""
        src = _source('managers/seasonManager.py')
        body = re.search(r'def _creditVeteranForWeek\(.*?\n    def ', src, re.S)
        self.assertIsNotNone(body, '_creditVeteranForWeek is gone')
        block = body.group(0)
        # ⚠️ The dead tables are NAMED in the docstring on purpose — that is where the
        # history lives. Strip the docstring and the comments, and test the CODE.
        code = re.sub(r'""".*?"""', '', block, flags=re.S)
        code = '\n'.join(l for l in code.split('\n') if not l.strip().startswith('#'))
        self.assertNotIn('FantasyRosterPlayer', code,
                         'Veteran is still counting off a table the fusion left unwritten')
        self.assertIn('WeeklyCardBonus', code,
                      'Veteran should count off the banked weekly record')

    def testTheCreditIsScopedToTheWeekThatEnded(self):
        """It used to take every user with a roster this SEASON and credit them on every
        week — which would have over-credited had the query ever matched. The banked row
        is per week, so the query has to be too."""
        src = _source('managers/seasonManager.py')
        block = re.search(r'def _creditVeteranForWeek\(.*?\n    def ', src, re.S).group(0)
        self.assertIn('week: int', block, 'the credit does not take a week')
        self.assertIn('WeeklyCardBonus.week == week', block,
                      'the credit is not scoped to the week that ended')
        # And the caller passes it.
        self.assertRegex(src, r'_creditVeteranForWeek\(\s*self\.currentSeason\.seasonNumber,\s*week\s*\)')

    def testABackfillExistsAndIsAbsolute(self):
        """Fixing the hook alone starts the count from today. The backfill has to be
        absolute so it is idempotent — it runs on every achievements visit."""
        src = _source('managers/achievementManager.py')
        self.assertIn('def backfillVeteran', src)
        block = re.search(r'def backfillVeteran\(.*?\n\ndef ', src, re.S).group(0)
        self.assertIn('absolute=weeks', block,
                      'the backfill must set progress absolutely, not increment it')

    def testTheBackfillCountsEquippedWeeksAsWellAsBankedOnes(self):
        """A bonus row is only written once a week is PROCESSED, so the week in flight is
        missing from it — measured on a live database as equipped weeks 10-13 against
        banked 10-12. A reader who has equipped all season should not wait for a rollover
        to see the current week counted."""
        src = _source('managers/achievementManager.py')
        block = re.search(r'def backfillVeteran\(.*?\n\ndef ', src, re.S).group(0)
        self.assertIn('EquippedCard', block)
        self.assertIn('max(banked, equipped)', block,
                      'the two sources overlap — summing them double-counts')

    def testTheBackfillRunsWhereUsersWillSeeIt(self):
        """It has to be wired, not merely written. The whole bug was a hook nobody
        called: `onFantasyRosterWeekCompleted` had exactly zero call sites in the app
        until `_creditVeteranForWeek` was pointed at it."""
        src = _source('api/main.py')
        self.assertIn('backfillVeteran', src,
                      'the backfill is never called from the API')


if __name__ == '__main__':
    unittest.main(verbosity=2)
