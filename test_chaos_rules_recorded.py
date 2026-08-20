"""A Criticality game records what it was played under.

⚠️ REPORTED PLAY, UNDIAGNOSABLE: "5th & Goal, STL 5 — punts 15 yards." Five downs, when the
league's own `rule_overrides` are `{"gameFormat": "frames", "framesPerGame": 6,
"contestedScoringEnabled": true}` — four downs. So it was a chaos game, and a chaos game
gets its own randomized ruleset generated just before kickoff, applied to the game object,
and then thrown away. Nothing recorded it. The rules that produced the play no longer
existed anywhere by the time anyone looked.

That matters because chaos can change the decision it is being judged on: `downsPerSeries`
can be 3 or 5, and `fieldGoalPoints` anywhere from 1 to 5 — so a field goal from the 5 may
genuinely have been worth almost nothing, and declining to kick may have been correct. With
no record, "is this a bug?" is unanswerable either way.

⚠️ Kept hidden from PLAYERS, which was always the design — a Criticality game should feel
wrong without announcing why. The record is admin-only.

⚠️ Stored as the DIFF from the league's rules rather than the whole ruleset: what was
different IS the question, and a full dump buries it.

Run: .venv/bin/python test_chaos_rules_recorded.py
"""
import json
import unittest
from types import SimpleNamespace


class _Rules:
    def __init__(self, **kw):
        self.downsPerSeries = kw.get('downsPerSeries', 4)
        self.fieldGoalPoints = kw.get('fieldGoalPoints', 3)
        self.touchdownPoints = kw.get('touchdownPoints', 6)
        self.firstDownDistance = kw.get('firstDownDistance', 10)


def diff(seasonRules, chaosRules):
    from managers.seasonManager import SeasonManager
    return SeasonManager._chaosRuleDiff(seasonRules, chaosRules)


class TheDiffSaysWhatChanged(unittest.TestCase):

    def test_theReportedShape(self):
        """Five downs against a four-down league is exactly what could not be explained."""
        out = diff(_Rules(), _Rules(downsPerSeries=5))
        self.assertEqual(out, {'downsPerSeries': {'was': 4, 'now': 5}})

    def test_itCarriesBothSidesOfEachChange(self):
        """'now' alone is not enough — the question is what it was different FROM."""
        out = diff(_Rules(), _Rules(downsPerSeries=5, fieldGoalPoints=1))
        self.assertEqual(out['fieldGoalPoints'], {'was': 3, 'now': 1})

    def test_anOrdinaryGameRecordsNothing(self):
        """No chaos, no row — this must not bloat every game."""
        self.assertEqual(diff(_Rules(), _Rules()), {})

    def test_itOnlyReportsFieldsChaosCanActuallyTouch(self):
        """Reads the candidate list rather than dumping every attribute, so the record is
        the decision that was made and not unrelated state."""
        seasonRules = _Rules()
        chaosRules = _Rules()
        chaosRules.somethingUnrelated = 'noise'
        self.assertEqual(diff(seasonRules, chaosRules), {})

    def test_aMissingFieldIsNotAChange(self):
        """⚠️ A rules object that simply lacks a candidate must not read as 'changed to
        None' — that would mark every ordinary game as chaotic."""
        class Sparse:
            downsPerSeries = 4
        self.assertEqual(diff(_Rules(), Sparse()), {})


class ItIsWrittenAndReadable(unittest.TestCase):

    def test_itIsPersistedAtBothCompletionPaths(self):
        """⚠️ There are two save paths. A fix applied to one leaves half the games
        unrecorded, which is how the format-state column was nearly shipped broken."""
        with open('managers/seasonManager.py') as fh:
            src = fh.read()
        self.assertEqual(src.count('self._applyChaosRulesToRow(db_game, game)'), 2)

    def test_theDiffIsCapturedWhereChaosIsApplied(self):
        with open('managers/seasonManager.py') as fh:
            body = fh.read().split('def _applyChaosRulesIfCritical')[1].split('\n    def ')[0]
        self.assertIn('game._chaosRules = self._chaosRuleDiff(', body)

    def test_theWriterSkipsAnOrdinaryGame(self):
        from managers.seasonManager import SeasonManager
        row = SimpleNamespace(chaos_rules=None)
        SeasonManager._applyChaosRulesToRow(SimpleNamespace(), row,
                                            SimpleNamespace(_chaosRules={}))
        self.assertIsNone(row.chaos_rules)

    def test_theWriterStoresJson(self):
        from managers.seasonManager import SeasonManager
        row = SimpleNamespace(chaos_rules=None)
        SeasonManager._applyChaosRulesToRow(
            SimpleNamespace(), row,
            SimpleNamespace(_chaosRules={'downsPerSeries': {'was': 4, 'now': 5}}))
        self.assertEqual(json.loads(row.chaos_rules)['downsPerSeries']['now'], 5)

    def test_theMigrationExists(self):
        """alembic does not run on deploy."""
        with open('database/connection.py') as fh:
            self.assertIn('ALTER TABLE games ADD COLUMN chaos_rules TEXT', fh.read())

    def test_itIsAdminOnlyAndNotInThePublicPayload(self):
        """⚠️ Hidden from players is the DESIGN — a Criticality game should feel wrong
        without announcing why. Only the diagnosis surface changes."""
        with open('api/main.py') as fh:
            src = fh.read()
        self.assertIn('/api/admin/games/{game_id}/rules', src)
        endpoint = src.split('async def admin_game_chaos_rules')[1].split('\n@app.')[0]
        # The gate is on the SIGNATURE, which follows the function name — looking at the
        # decorator line above it finds the route and not the dependency.
        self.assertIn('_checkAdminAuth', endpoint.split('\n')[0])
        self.assertIn('leagueRules', endpoint, 'the diff needs its baseline for context')


if __name__ == '__main__':
    unittest.main(verbosity=2)
