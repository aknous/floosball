"""Who won is PERSISTED, because in some formats the scores do not say.

⚠️ REPORTED ON A FRAMES GAME (production game 572). Buffalo won more frames; Miami scored
more points. Frames is decided by FRAMES WON with points only breaking a level match, so
Buffalo won -- and the surfaces disagreed about it:

    team page          green (win)      correct
    the Discord bot    "Buffalo wins"   correct
    standings record   counted the win  correct
    standings Last 5   red 'L'          WRONG
    daily recap email  listed an 'L'    WRONG  (against a record that counted it a W)

One game, four surfaces, two answers. The cause is that `games` stored only SCORES, so
every reader re-derived the winner, and any reader holding only scores asks
`home_score > away_score` -- the wrong question under frames. The engine had the right
answer all along (`format.winnerSide`) and simply never wrote it down.

The column is the fix: written once at completion from the format's own rule, so a format
added later is correct for free, and read by everything downstream.

Run: .venv/bin/python test_game_winner.py
"""
import json
import unittest
from types import SimpleNamespace

from game_formats import getFormat


class _Row:
    winner_team_id = None


class _Game:
    """Just enough game for `_applyWinnerToRow`."""
    def __init__(self, fmt, homeScore, awayScore, framesHome=None, framesAway=None):
        self.format = getFormat(fmt)
        self.homeScore, self.awayScore = homeScore, awayScore
        self.homeTeam = SimpleNamespace(id=11, name='Buffalo')
        self.awayTeam = SimpleNamespace(id=22, name='Miami')
        if framesHome is not None:
            self._framesWonHome, self._framesWonAway = framesHome, framesAway


def applyWinner(game):
    from managers.seasonManager import SeasonManager
    row = _Row()
    SeasonManager._applyWinnerToRow(SimpleNamespace(), row, game)
    return row.winner_team_id


class TheWinnerComesFromTheFormat(unittest.TestCase):

    def test_theReportedGame(self):
        """THE REGRESSION. More frames, fewer points -- the frames winner takes it."""
        game = _Game('frames', homeScore=17, awayScore=20, framesHome=3.5, framesAway=2.5)
        self.assertEqual(applyWinner(game), 11, 'the frames winner should have won')

    def test_pointsOnlyBreakALevelMatch(self):
        game = _Game('frames', homeScore=17, awayScore=20, framesHome=3.0, framesAway=3.0)
        self.assertEqual(applyWinner(game), 22, 'level on frames, so points decide')

    def test_aTrulyLevelMatchStoresNoWinner(self):
        """⚠️ NULL means a draw. It must not fall back to the home side."""
        game = _Game('frames', homeScore=20, awayScore=20, framesHome=3.0, framesAway=3.0)
        self.assertIsNone(applyWinner(game))

    def test_standardGamesAreUnchanged(self):
        self.assertEqual(applyWinner(_Game('standard', 24, 17)), 11)
        self.assertEqual(applyWinner(_Game('standard', 17, 24)), 22)
        self.assertIsNone(applyWinner(_Game('standard', 17, 17)))

    def test_dartsUsesItsOwnRuleToo(self):
        """Every format answers through `winnerSide`, so this is right for free."""
        self.assertEqual(applyWinner(_Game('bust', 21, 18)), 11)

    def test_itIsWrittenAtBothCompletionPaths(self):
        """⚠️ There are TWO save paths (update and insert). A fix applied to one leaves
        half the league's games without a winner, which is how the format-state column was
        nearly shipped broken."""
        with open('managers/seasonManager.py') as fh:
            src = fh.read()
        self.assertEqual(src.count('self._applyWinnerToRow(db_game, game)'), 2)


class TheReadersUseIt(unittest.TestCase):
    """⚠️ Storing it changes nothing until the surfaces stop asking the scores."""

    def test_theStandingsFormColumnPrefersIt(self):
        with open('standings_view.py') as fh:
            body = fh.read().split('def buildFormAndMovement')[1]
        self.assertIn('Game.winner_team_id', body)
        self.assertIn('if winnerId is not None:', body)

    def test_theStreakBackfillPrefersIt(self):
        with open('database/connection.py') as fh:
            src = fh.read()
        body = src.split('def _backfillTeamPeakStreaks')[1].split('\ndef ')[0]
        self.assertIn('g.winner_team_id', body)
        self.assertIn('if winnerId is not None:', body)

    def test_theScoreComparisonSurvivesOnlyAsAFallback(self):
        """Rows finished before the column existed still have to read sensibly, and for
        every points-decided format the fallback gives the same answer."""
        with open('standings_view.py') as fh:
            body = fh.read().split('def buildFormAndMovement')[1]
        self.assertIn('elif homeScore > awayScore:', body,
                      'the pre-column fallback was removed')


class TheBackfillCanRecoverHistory(unittest.TestCase):
    """⚠️ A score comparison cannot repair the existing rows, which is the whole point. The
    frames breakdown is already persisted in `format_state`, so history is recoverable."""

    def _decide(self, formatState, homeScore, awayScore, homeId=11, awayId=22):
        """Mirrors the backfill's decision, which is what the test is about."""
        frames = (json.loads(formatState) or {}).get('frames') if formatState else None
        if frames and frames.get('active'):
            fh = float(frames.get('framesWonHome') or 0)
            fa = float(frames.get('framesWonAway') or 0)
            if fh != fa:
                return homeId if fh > fa else awayId
            if homeScore != awayScore:
                return homeId if homeScore > awayScore else awayId
            return None
        if homeScore != awayScore:
            return homeId if homeScore > awayScore else awayId
        return None

    def test_aFramesGameIsRecoveredFromItsStoredBreakdown(self):
        state = json.dumps({'frames': {'active': True, 'framesWonHome': 3.5,
                                       'framesWonAway': 2.5}})
        self.assertEqual(self._decide(state, 17, 20), 11)

    def test_aLevelFramesGameFallsToPoints(self):
        state = json.dumps({'frames': {'active': True, 'framesWonHome': 3.0,
                                       'framesWonAway': 3.0}})
        self.assertEqual(self._decide(state, 17, 20), 22)

    def test_aStandardGameTakesTheScore(self):
        self.assertEqual(self._decide(None, 24, 17), 11)

    def test_aDrawIsLeftAlone(self):
        """⚠️ Left NULL rather than guessed, so the backfill is idempotent — a draw would
        otherwise be 'repaired' on every boot."""
        self.assertIsNone(self._decide(None, 17, 17))

    def test_theBackfillOnlyTouchesUnsetFinalGames(self):
        with open('database/connection.py') as fh:
            body = fh.read().split('def _backfillGameWinners')[1].split('\ndef ')[0]
        self.assertIn('winner_team_id IS NULL', body)
        # ⚠️ LOWER(status), and this assertion is why. The column holds 'final'; a literal
        # 'Final' matched nothing, so the backfill ran clean and repaired zero rows — the
        # worst kind of failure, because the log line still says it did its job. Caught by
        # dry-running the shipped SQL against a copy of production rather than trusting it.
        self.assertIn("LOWER(status) = 'final'", body)
        self.assertNotIn("status = 'Final'", body)

    def test_theMigrationExists(self):
        """alembic does not run on deploy, so the column needs an inline migration."""
        with open('database/connection.py') as fh:
            src = fh.read()
        self.assertIn('ALTER TABLE games ADD COLUMN winner_team_id INTEGER', src)


if __name__ == '__main__':
    unittest.main(verbosity=2)
