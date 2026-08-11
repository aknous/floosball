"""A leaderboard row shows one moment, not two.

⚠️ REPORTED FROM PRODUCTION with screenshots. A user's lineup read
"Frig Lagotis / Gold Rush", the leaderboard showed the same row as
"Frig Lagotis / Battering Ram", and an earlier capture of that row showed
"Locust Clambake / Battering Ram". Three different answers for one slot.

The two halves came from different moments. The PLAYERS were taken from the LIVE
equipped set, while `cardBreakdowns` for a banked week come from the stored record: the
cards that actually scored. Change a card after a week banks and the row pairs today's
player with that week's effect, which is why the card sat still while the player moved.

⚠️ `equipped_cards` CANNOT be the source either, which is the trap this file exists to
mark. The equip handler runs `deleteByUserWeek` and re-inserts, so a week's rows are
REWRITTEN on every change and end up describing the newest selection rather than the one
that played. Verified against production: that user's equipped_cards for week 7 held
Frig Lagotis / gold_rush while week 7's BANKED record held Robbie Tumbles /
battering_ram. The breakdown is the only thing written once and never revised, so a
banked row is rebuilt from it.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from managers.fantasyTracker import _SLOT_LABEL_BY_ORDINAL, bankedLineupPlayerIds


def lineupForWeek(week, currentWeek, banked, equippedRows, live, settledWeeks=()):
    """`getSnapshot`'s resolver, in the order it decides."""
    row = banked.get(week)
    if row is not None:
        pids = bankedLineupPlayerIds(row)
        if pids:
            return pids
    return live if week == currentWeek else equippedRows.get(week, [])


def weekFP(week, currentWeek, banked, equippedRows, live, fpByPlayerWeek, settledWeeks=()):
    """`getSnapshot`'s per-week base FP."""
    return sum(fpByPlayerWeek.get((p, week), 0)
               for p in lineupForWeek(week, currentWeek, banked, equippedRows, live,
                                      settledWeeks))


def rowsFor(banked, breakdowns, liveLineup):
    """The selection as fantasyTracker runs it: banked rows come from the breakdowns."""
    rows = list(liveLineup)
    if banked:
        fromBanked = [
            {'slot': _SLOT_LABEL_BY_ORDINAL.get(b.get('slotNumber'), ''),
             'playerName': b.get('playerName'), 'effect': b.get('effectName')}
            for b in breakdowns if b.get('playerId')
        ]
        if fromBanked:
            rows = fromBanked
    return rows


BANKED = [
    {'slotNumber': 1, 'playerId': 1, 'playerName': 'Dougie Malibu', 'effectName': 'piggy_bank'},
    {'slotNumber': 2, 'playerId': 2, 'playerName': 'Robbie Tumbles', 'effectName': 'battering_ram'},
]
LIVE = [
    {'slot': 'QB', 'playerName': 'Dougie Malibu', 'effect': 'piggy_bank'},
    {'slot': 'RB', 'playerName': 'Frig Lagotis', 'effect': 'gold_rush'},
]


class LeaderboardLineupTests(unittest.TestCase):
    def testABankedRowShowsThePlayerThatScored(self):
        """THE REGRESSION, in the exact shape it was reported."""
        rows = rowsFor(True, BANKED, LIVE)
        rb = next(r for r in rows if r['slot'] == 'RB')
        self.assertEqual(rb['playerName'], 'Robbie Tumbles')
        self.assertEqual(rb['effect'], 'battering_ram')

    def testABankedRowNeverPairsALivePlayerWithABankedCard(self):
        rows = rowsFor(True, BANKED, LIVE)
        self.assertNotIn('Frig Lagotis', [r['playerName'] for r in rows])

    def testALiveWeekStillShowsWhatIsEquippedNow(self):
        # Mid-week the reader is watching their current lineup score.
        self.assertEqual(rowsFor(False, [], LIVE), LIVE)

    def testABankedWeekWithNoBreakdownsFallsBackToLive(self):
        # Older rows banked a total without per-card detail; an empty expansion
        # would be worse than an approximate one.
        self.assertEqual(rowsFor(True, [], LIVE), LIVE)

    def testABreakdownWithNoPlayerIsSkippedRatherThanBlank(self):
        rows = rowsFor(True, BANKED + [{'slotNumber': 5, 'effectName': 'none'}], LIVE)
        self.assertEqual(len(rows), 2)

    def testChangingCardsAfterAWeekBanksDoesNotMoveTheRow(self):
        before = rowsFor(True, BANKED, LIVE)
        after = rowsFor(True, BANKED, [{'slot': 'RB', 'playerName': 'Locust Clambake',
                                        'effect': 'gold_rush'}])
        self.assertEqual(before, after,
                         'the banked row moved when the user changed a card')

    # -- the season total ---------------------------------------------------
    #
    # The same confusion, one layer down. `seasonEarnedFP` is recomputed from the
    # per-week rows on EVERY request, so overwriting a week's rows moved a total that
    # had already been earned. Reproduced from the production figures for user `bea`:
    # week 7 banked a lineup worth 61 FP, and the rows now standing in week 7 are
    # worth 98.

    BANKED_WK7 = {7: {'breakdowns': [{'playerId': 2, 'playerName': 'Robbie Tumbles'}]}}
    ROWS_AFTER_SWAP = {7: [9]}          # rewritten by the swap
    FP = {(2, 7): 61.0, (9, 7): 98.0}

    def testASettledWeekKeepsWhatItEarned(self):
        """THE REGRESSION. Measured on production as +41 FP for the worst-hit user."""
        self.assertEqual(
            weekFP(7, 8, self.BANKED_WK7, self.ROWS_AFTER_SWAP, [], self.FP), 61.0)

    def testSwappingBeforeTheWeekRollsOverDoesNotPayTheNewLineup(self):
        # bea's exact case: the week had banked but was still `currentWeek`, so the
        # live set was the swapped-in one and got counted.
        self.assertEqual(
            weekFP(7, 7, self.BANKED_WK7, self.ROWS_AFTER_SWAP, [9], self.FP), 61.0)

    def testAWeekThatHasNotBankedStillCountsWhatIsEquippedNow(self):
        # Mid-week the reader is watching their live lineup accumulate.
        self.assertEqual(weekFP(7, 7, {}, {}, [9], self.FP), 98.0)

    def testAPastWeekWithNoBreakdownFallsBackToItsRows(self):
        # Weeks banked before breakdowns were stored have no better source.
        self.assertEqual(
            weekFP(7, 8, {7: {'breakdowns': []}}, self.ROWS_AFTER_SWAP, [], self.FP), 98.0)

    def testABreakdownWithNoPlayerDoesNotZeroTheWeek(self):
        # An empty-slot breakdown row must not be mistaken for "this week scored 0".
        banked = {7: {'breakdowns': [{'effectName': 'none'}]}}
        self.assertEqual(weekFP(7, 8, banked, self.ROWS_AFTER_SWAP, [], self.FP), 98.0)

    # -- a closed week has a complete roll ----------------------------------
    #
    # The snapshot used to be written only `if totalFP > 0 or floobitsEarned > 0`, so a
    # settled week held no record of anyone whose cards earned nothing, and there was
    # no way to tell them from someone who equipped after the whistle. It is now written
    # whenever a lineup was fielded, which is what lets the absence below mean something.

    def testAMissingRowIsNotReadAsAbsence(self):
        """⚠️ The rule that was nearly shipped and would have deleted real FP.

        `_processWeekCardEffects` counts only LOCKED rows and `lockAllForWeek` runs once
        at week start, so a user who signed up mid-week banked no row despite fielding a
        lineup. On production that was 13 of 21 users, overwhelmingly their FIRST week.
        Absence of a row therefore means "no record", never "did not play".
        """
        self.assertEqual(
            weekFP(7, 7, {}, {7: [9]}, [9], self.FP, settledWeeks={7}), 98.0)

    def testFieldingALineupThatEarnedNoBonusStillCountsItsBaseFP(self):
        # The case that makes a bare "no row" test unsafe: a zero row is still a roll
        # call, so the week counts normally.
        banked = {7: {'breakdowns': [{'playerId': 2, 'playerName': 'Robbie Tumbles'}]}}
        self.assertEqual(weekFP(7, 7, banked, {7: [9]}, [9], self.FP, settledWeeks={7}), 61.0)

    def testAnOpenWeekIsNotTreatedAsAbsence(self):
        # Before the week closes there is no roll call, so equipment is all there is.
        self.assertEqual(weekFP(7, 7, {}, {}, [9], self.FP, settledWeeks={6}), 98.0)

    def testALegacyRowWithNoBreakdownDoesNotZeroTheWeek(self):
        # Weeks banked before breakdowns were stored must not read as absence.
        self.assertEqual(
            weekFP(7, 8, {7: {'breakdowns': []}}, {7: [9]}, [], self.FP,
                   settledWeeks={7}), 98.0)

    def testALineupSetIntoALiveSlateIsLocked(self):
        """The write-side half: an unlocked row banks nothing and leaves no snapshot.

        `lockAllForWeek` runs once at week start, and the equip handler's 409 guard only
        fires when EXISTING rows are locked, so a user with none — a mid-week signup —
        could equip into a running slate and never be locked. Read as source text
        because importing `api.main` drags in the whole app.
        """
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'api', 'main.py')
        with open(path, encoding='utf-8') as fh:
            src = fh.read()
        marker = 'equippedRepo.deleteByUserWeek(user.id, currentSeason, currentWeek)'
        self.assertIn(marker, src)
        writeBlock = src[src.index(marker):src.index(marker) + 1600]
        self.assertNotIn('locked=False', writeBlock,
                         'equip writes a row that a live slate will never lock')
        self.assertIn('locked=_areGamesStarted()', writeBlock)

    def testTheSlotMapMatchesTheOneCardsAreEquippedWith(self):
        from managers.cardManager import SLOT_TO_ORDINAL
        for label, ordinal in SLOT_TO_ORDINAL.items():
            self.assertEqual(_SLOT_LABEL_BY_ORDINAL.get(ordinal), label, label)


if __name__ == '__main__':
    unittest.main(verbosity=2)
