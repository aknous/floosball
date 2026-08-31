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

from managers.fantasyTracker import (_SLOT_LABEL_BY_ORDINAL, bankedLineupPlayerIds,
                                     completeSnapshotFrom, weekIsFullyRecorded)


def weekIsClosed(week, settledWeeks, boundary, season=1):
    """`getSnapshot`'s predicate: the week finished AND its record is complete."""
    return week in settledWeeks and weekIsFullyRecorded(season, week, boundary)


def lineupForWeek(week, currentWeek, banked, equippedRows, live, boundary=None,
                  settledWeeks=None, season=1):
    """`getSnapshot`'s resolver, in the order it decides."""
    if settledWeeks is None:
        settledWeeks = set(banked)
    row = banked.get(week)
    if row is not None:
        pids = bankedLineupPlayerIds(row)
        if pids:
            return pids
    elif weekIsClosed(week, settledWeeks, boundary, season):
        return []
    return live if week == currentWeek else equippedRows.get(week, [])


def weekFP(week, currentWeek, banked, equippedRows, live, fpByPlayerWeek, boundary=None,
           settledWeeks=None):
    """`getSnapshot`'s per-week base FP."""
    return sum(fpByPlayerWeek.get((p, week), 0)
               for p in lineupForWeek(week, currentWeek, banked, equippedRows, live,
                                      boundary, settledWeeks))


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
    # NO GAMES MEANS NO POINTS. A lineup assembled after a week's games have finished
    # did not play that week. Absence of a snapshot row is what proves it, which is only
    # sound once the row is written for EVERY fielded lineup — it used to be written only
    # `if totalFP > 0 or floobitsEarned > 0`. The boundary stamped by
    # `_processWeekCardEffects` is where the gate switches on; before it, absence is
    # ambiguous and stays permissive.

    def testALineupBuiltAfterTheGamesEarnsNothingForThatWeek(self):
        """THE RULE: no games means no points (owner, 2026-08-10).

        Equipping lands rows on `currentWeek`, which does not advance until rollover, so
        a first-time equip between the final whistle and the rollover otherwise collects
        the whole week's FP. Measured on production at 59.0 and 33.0 FP for two users in
        week 7.
        """
        self.assertEqual(
            weekFP(7, 7, {}, {7: [9]}, [9], self.FP, boundary=(1, 1), settledWeeks={7}), 0.0)

    def testAWeekRecordedBeforeTheBoundaryStaysPermissive(self):
        """⚠️ The gate must NOT reach back over weeks whose record is incomplete.

        Before the unconditional snapshot a row was written only when a lineup PAID, so
        an absence there can equally mean "fielded and earned nothing" — 13 of 21
        production users have such a week, some MID-TENURE. Zeroing those deletes FP
        from users who did play.
        """
        self.assertEqual(
            weekFP(7, 7, {}, {7: [9]}, [9], self.FP, boundary=(1, 8), settledWeeks={7}), 98.0)

    def testALiveWeekStillAccruesBeforeItBanks(self):
        """⚠️ THE REGRESSION THIS GATE CAUSED, caught in testing.

        Nobody has a banked row until the whistle, and a live week is also at or after
        the boundary — so gating on the boundary ALONE zeroed everyone's base FP for the
        whole week they were watching. The week must have actually CLOSED (someone banked
        it) before absence can mean anything.
        """
        self.assertEqual(
            weekFP(7, 7, {}, {}, [9], self.FP, boundary=(1, 1), settledWeeks=set()), 98.0)

    def testAClosedWeekIsBothProcessedAndPastTheBoundary(self):
        self.assertTrue(weekIsClosed(7, {7}, (1, 1)))
        self.assertFalse(weekIsClosed(7, set(), (1, 1)), 'week never processed')
        self.assertFalse(weekIsClosed(7, {7}, (1, 8)), 'week predates the boundary')
        self.assertFalse(weekIsClosed(7, {7}, None), 'league never stamped')

    def testAWeekNobodyPlayedStillCountsAsClosed(self):
        """⚠️ The second miss, also caught in testing.

        `settledWeeks` was derived from the card-bonus rows, but those only exist if
        somebody fielded a lineup. An early week with no participants therefore looked
        UNCLOSED and switched the gate off exactly where a newcomer's rows land. Observed
        locally: weeks 1-4 banked, only 3-4 had bonus rows, and a user who equipped in
        week 2 was credited for it.
        """
        self.assertTrue(weekIsClosed(2, {1, 2, 3, 4}, (1, 1)), 'banked week read as open')
        self.assertFalse(weekIsClosed(2, {3, 4}, (1, 1)), 'the bug: derived from bonuses')

    def testSettledWeeksComeFromBankedPlayerFp(self):
        """Pin the SOURCE, since that is what was wrong rather than the logic."""
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            'managers', 'fantasyTracker.py')
        with open(path, encoding='utf-8') as fh:
            src = fh.read()
        block = src[src.index('settledWeeks = {'):src.index('settledWeeks = {') + 260]
        self.assertIn('WeeklyPlayerFP', block,
                      'settledWeeks must not be derived from card-bonus rows')

    def testTheBoundaryIsStampedBeforeTheEarlyReturn(self):
        """⚠️ The third miss, and the one the user actually saw.

        `_processWeekCardEffects` returns early when nobody has cards equipped. Stamping
        after that meant WEEK 1 OF A NEW LEAGUE never stamped, the boundary landed on the
        first week someone played, and week 1 sat permanently BEFORE the boundary. A user
        equipping between week 1's whistle and the rollover then had week 1's FP credited
        on the week 2 board. Completeness is a property of the CODE, not of turnout.
        """
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            'managers', 'seasonManager.py')
        with open(path, encoding='utf-8') as fh:
            src = fh.read()
        stamp = src.index('COMPLETE_SNAPSHOT_SETTING as _CSS')
        earlyReturn = src.index('allEquipped = equippedRepo.getAllForWeek(season, week)')
        self.assertLess(stamp, earlyReturn,
                        'the boundary is stamped after the no-participants early return')

    def testAWeekBeforeTheBoundaryCreditsEquipmentPutOnAfterTheWhistle(self):
        # The consequence, stated as behavior: this is what the user saw, and it is
        # correct ONLY because such a week's record is genuinely incomplete.
        self.assertEqual(
            weekFP(1, 2, {}, {1: [9]}, [], {(9, 1): 98.0}, boundary=(1, 2),
                   settledWeeks={1}), 98.0)
        # With the stamp in the right place, week 1 IS the boundary and the leak closes.
        self.assertEqual(
            weekFP(1, 2, {}, {1: [9]}, [], {(9, 1): 98.0}, boundary=(1, 1),
                   settledWeeks={1}), 0.0)

    def testAFreshStartClearsTheBoundary(self):
        """⚠️ The fourth miss, and why fresh sims kept reproducing the leak.

        `clear_db()` preserves `app_settings` WHOLESALE, so the boundary stamp outlived
        every wipe while the data it describes was dropped. With the season counter
        restarting at 1, a stale "1:2" left the NEW week 1 sitting before the boundary
        and permanently exempt from the gate — on a clean run, every time.
        """
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            'database', 'connection.py')
        with open(path, encoding='utf-8') as fh:
            src = fh.read()
        self.assertIn('COMPLETE_SNAPSHOT_SETTING', src,
                      'clear_db does not clear the season-scoped boundary stamp')
        clear = src.index('def clear_db')
        self.assertLess(clear, src.index('COMPLETE_SNAPSHOT_SETTING'),
                        'the boundary is cleared outside clear_db')

    def testAStaleBoundaryFromAPriorRunExemptsWeekOne(self):
        # The behavior that made it invisible: week 1 looks fine in isolation, and only
        # a boundary carried over from a PREVIOUS run turns the gate off.
        fp = {(9, 1): 98.0}
        self.assertEqual(weekFP(1, 2, {}, {1: [9]}, [], fp, boundary=(1, 2),
                                settledWeeks={1}), 98.0)
        self.assertEqual(weekFP(1, 2, {}, {1: [9]}, [], fp, boundary=(1, 1),
                                settledWeeks={1}), 0.0)

    def testTheWeeklyBoardAppliesTheSameGate(self):
        """⚠️ The fifth miss: a SECOND door onto the same mutable rows.

        `/api/fantasy/leaderboard/weekly` builds straight from `_equippedRostersByWeek`
        and never touched `getSnapshot`, so gating the snapshot left it wide open.
        Reported from testing: equipping after week 2's games but before the week 3
        rollover put week 2's points on the week 2 board.
        """
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'api', 'main.py')
        with open(path, encoding='utf-8') as fh:
            src = fh.read()
        start = src.index('def get_fantasy_weekly_leaderboard')
        body = src[start:src.index('# CURRENCY (FLOOBITS)', start)]
        self.assertIn('weekIsFullyRecorded', body, 'the weekly board has no boundary gate')
        self.assertIn('bankedRows', body, 'the weekly board does not read the banked record')
        self.assertIn('continue', body, 'a closed week with no row is not skipped')

    def testEveryHistoricalFpReaderIsAccountedFor(self):
        """The sweep that should have happened before declaring the first fix done.

        Any reader of a PAST week's equipped rows can credit a lineup put on after the
        whistle. Readers pinned to `currentWeek` are the live lineup and are fine.
        """
        import re
        root = os.path.dirname(os.path.abspath(__file__))
        # Match the operand itself rather than using a lookahead: `\s*` backtracks to
        # zero width, so `(?!currentWeek)` passes on the space and flags every line.
        pattern = re.compile(r'EquippedCard\.week\s*==\s*(\w+)')
        offenders = []
        for rel in ('api/main.py', 'managers/fantasyTracker.py'):
            with open(os.path.join(root, rel), encoding='utf-8') as fh:
                for i, line in enumerate(fh, 1):
                    m = pattern.search(line)
                    if m and m.group(1) != 'currentWeek':
                        offenders.append(f'{rel}:{i} reads week={m.group(1)}')
        self.assertEqual(offenders, [],
                         f'past-week equipped reads outside the gate: {offenders}')

    def testTheBoundaryIsReadFromTheStampedSetting(self):
        self.assertEqual(completeSnapshotFrom(lambda k: '2:5'), (2, 5))
        self.assertIsNone(completeSnapshotFrom(lambda k: None))
        self.assertIsNone(completeSnapshotFrom(lambda k: 'garbage'))

    def testAnUnstampedLeagueEnforcesNothing(self):
        # Until the first week is recorded completely there is no safe boundary, so the
        # gate stays off rather than defaulting to on.
        self.assertFalse(weekIsFullyRecorded(1, 7, None))

    def testALaterSeasonIsAlwaysPastTheBoundary(self):
        self.assertTrue(weekIsFullyRecorded(2, 1, (1, 8)))
        self.assertFalse(weekIsFullyRecorded(1, 7, (1, 8)))
        self.assertTrue(weekIsFullyRecorded(1, 8, (1, 8)))

    def testFieldingALineupThatEarnedNoBonusStillCountsItsBaseFP(self):
        # The case that makes a bare "no row" test unsafe: a zero row is still a roll
        # call, so the week counts normally.
        banked = {7: {'breakdowns': [{'playerId': 2, 'playerName': 'Robbie Tumbles'}]}}
        self.assertEqual(weekFP(7, 7, banked, {7: [9]}, [9], self.FP, boundary=(1, 1)), 61.0)

    def testAnOpenWeekIsNotTreatedAsAbsence(self):
        # Before the week closes there is no roll call, so equipment is all there is.
        self.assertEqual(weekFP(7, 7, {}, {}, [9], self.FP, boundary=(1, 8)), 98.0)

    def testALegacyRowWithNoBreakdownDoesNotZeroTheWeek(self):
        # Weeks banked before breakdowns were stored must not read as absence.
        self.assertEqual(
            weekFP(7, 8, {7: {'breakdowns': []}}, {7: [9]}, [], self.FP,
                   boundary=(1, 1)), 98.0)

    def testTheSnapshotIsWrittenForALineupThatPaidNothing(self):
        """The write-side half, and the reason absence stays unreadable.

        The row used to be written only `if totalFP > 0 or result.floobitsEarned > 0`, so
        a lineup of no-effect `standard` starter cards was fielded and left no trace.
        Read as source text because importing seasonManager drags in the whole app.
        """
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            'managers', 'seasonManager.py')
        with open(path, encoding='utf-8') as fh:
            src = fh.read()
        marker = 'weekBonus = WeeklyCardBonus('
        self.assertIn(marker, src)
        # ⚠️ A FIXED BYTE WINDOW IS FRAGILE — this was 4200 and a comment added inside the
        # serializer above pushed `if userEquipped:` out of it, failing a test about
        # something the comment did not touch. Anchor on the enclosing block instead, so
        # the window tracks the code rather than its length.
        anchor = src.rindex('for userId, userEquipped in', 0, src.index(marker))
        guard = src[anchor:src.index(marker)]
        self.assertNotIn('if totalFP > 0 or result.floobitsEarned > 0:', guard,
                         'the week snapshot is conditional on the lineup paying out')
        self.assertIn('if userEquipped:', guard)

    def testTheSlotMapMatchesTheOneCardsAreEquippedWith(self):
        from managers.cardManager import SLOT_TO_ORDINAL
        for label, ordinal in SLOT_TO_ORDINAL.items():
            self.assertEqual(_SLOT_LABEL_BY_ORDINAL.get(ordinal), label, label)


if __name__ == '__main__':
    unittest.main(verbosity=2)
