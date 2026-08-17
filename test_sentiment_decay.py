"""A fan's verdict goes stale unless they come back and re-cast it.

⚠️ A RATING NEVER EXPIRED. A fan casts one standing opinion per subject and can change it
whenever they like — `setRating`'s own docstring says "Cast or change" — but nothing aged
it. A 1-star cast in season 1 counted at full weight in season 5, against a GM who had
since won two titles. Owner: let fans make a new rating every season.

⚠️ DECAY SHRINKS EACH VOTE'S DEVIATION FROM NEUTRAL, NOT ITS WEIGHT IN AN AVERAGE. The
obvious implementation — a weighted mean — does NOTHING when every voter is equally stale,
because the weights cancel and it reduces to the plain mean. Each vote's normalized
sentiment is scaled individually and the mean taken over the RATER COUNT, which is what
actually pulls an aged verdict back toward 0.

⚠️ THE QUORUM COUNTS RATERS RAW; ONLY THE VALUE DECAYS. Turnout is turnout — a club that
mustered its raters cleared the bar whenever they voted. Decaying the count as well would
silently drop small clubs below quorum and switch the whole axis off, which is the failure
mode that made a flat league-wide bar wrong in the first place.

⚠️ BOARDS STAY RAW. The love/hate boards report what fans actually said ("1.2 stars from 3
fans"); the aged value is what the SIM reads. Two different questions.

Run: .venv/bin/python test_sentiment_decay.py
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database.repositories.sentiment_repository import (
    decayWeight, decayedSentiment, normalizeSentiment)
from constants import SENTIMENT_DECAY_PER_SEASON, SENTIMENT_DECAY_FLOOR


class DecayMath(unittest.TestCase):
    def test_afreshRatingIsUndiminished(self):
        self.assertEqual(decayWeight(5, 5), 1.0)

    def test_ageShrinksTheWeight(self):
        weights = [decayWeight(5 - age, 5) for age in range(5)]
        self.assertEqual(weights, sorted(weights, reverse=True))
        self.assertAlmostEqual(weights[1], SENTIMENT_DECAY_PER_SEASON)

    def test_itNeverReachesZero(self):
        """A fan who felt strongly and never came back still counts for something."""
        self.assertGreaterEqual(decayWeight(1, 99), SENTIMENT_DECAY_FLOOR)

    def test_aFutureStampIsNotAmplified(self):
        """Clock skew or a bad stamp must not make a rating count MORE than fresh."""
        self.assertEqual(decayWeight(9, 5), 1.0)

    def test_unanimousStaleVerdictDecaysTowardNeutral(self):
        """⚠️ THE TRAP. A weighted average over equally-stale voters equals the plain
        average — the weights cancel. This is what proves decay actually bites."""
        fresh = decayedSentiment([(1, 5)] * 5, 5)
        stale = decayedSentiment([(1, 2)] * 5, 5)
        self.assertAlmostEqual(fresh, -1.0)
        self.assertGreater(stale, fresh, 'a stale unanimous verdict must pull toward 0')
        self.assertLess(stale, 0.0, 'but it must not flip sign')

    def test_aFreshVoteOutweighsAStaleOne(self):
        mixed = decayedSentiment([(5, 5), (1, 1)], 5)
        self.assertGreater(mixed, 0.0, 'the fresh 5-star should dominate a 4-season-old 1-star')

    def test_noVotesIsNeutral(self):
        self.assertEqual(decayedSentiment([], 5), 0.0)

    def test_staysInRange(self):
        for rows in ([(1, 5)] * 9, [(5, 5)] * 9, [(1, 5), (5, 5)]):
            self.assertGreaterEqual(decayedSentiment(rows, 5), -1.0)
            self.assertLessEqual(decayedSentiment(rows, 5), 1.0)


class LiveBehaviour(unittest.TestCase):
    """Against a real session, both subjects, through the real repositories."""

    def setUp(self):
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from database.models import Base, User, Player, Team, Coach, SimulationState
        self.tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.tmp.close()
        self.engine = create_engine(f'sqlite:///{self.tmp.name}')
        Base.metadata.create_all(bind=self.engine)
        self.session = sessionmaker(bind=self.engine)()
        self.session.add(SimulationState(id=1, current_season=1, current_week=1))
        self.session.add(Team(id=1, name='T', city='C', abbr='T', color='#111',
                              offense_rating=80, defense_rating=80, overall_rating=80))
        self.session.add(Coach(id=1, name='GM'))
        self.session.add(Player(id=1, name='P', team_id=1))
        for i in (1, 2, 3):
            self.session.add(User(id=i, email=f'{i}@x', username=f'u{i}', favorite_team_id=1))
        self.session.commit()

    def tearDown(self):
        self.session.close()
        self.engine.dispose()
        os.unlink(self.tmp.name)

    def _setSeason(self, n):
        from sqlalchemy import text
        self.session.execute(text("UPDATE simulation_state SET current_season=:s"), {"s": n})
        self.session.commit()

    def _rateAll(self, rating=1):
        from database.repositories.sentiment_repository import (
            SentimentRepository, CoachSentimentRepository)
        pr, cr = SentimentRepository(self.session), CoachSentimentRepository(self.session)
        for uid in (1, 2, 3):
            pr.setRating(uid, 1, rating)
            cr.setRating(uid, 1, rating)
        self.session.commit()
        return pr, cr

    def test_bothSubjectsDecayTogether(self):
        pr, cr = self._rateAll()
        fresh = (pr.getSentiment(1), cr.getStanding(1))
        self._setSeason(4)
        aged = (pr.getSentiment(1), cr.getStanding(1))
        for f, a in zip(fresh, aged):
            self.assertAlmostEqual(f, -1.0)
            self.assertGreater(a, f, 'both player and GM sentiment must age')

    def test_reRatingRefreshesTheVerdict(self):
        from database.repositories.sentiment_repository import (
            SentimentRepository, CoachSentimentRepository)
        pr, cr = self._rateAll()
        self._setSeason(5)
        stale = pr.getSentiment(1)
        SentimentRepository(self.session).setRating(1, 1, 1)
        CoachSentimentRepository(self.session).setRating(1, 1, 1)
        self.session.commit()
        self.assertLess(pr.getSentiment(1), stale, 'a returning fan restores their full weight')
        self.assertLess(cr.getStanding(1), -0.15)

    def test_theBulkMapsAgreeWithTheSingleReads(self):
        """⚠️ `getStandingMap` is what GM turnover actually reads — it must not drift from
        `getStanding`, which is the one the tests and the UI exercise."""
        pr, cr = self._rateAll()
        self._setSeason(3)
        self.assertAlmostEqual(pr.getSentimentMap([1]).get(1), pr.getSentiment(1), places=6)
        self.assertAlmostEqual(cr.getStandingMap().get(1), cr.getStanding(1), places=6)

    def test_displayAveragesAreNotDecayed(self):
        """The board reports what fans said, not how much it still counts."""
        pr, _ = self._rateAll()
        self._setSeason(6)
        avg, count = pr.getAggregate(1)
        self.assertEqual((avg, count), (1.0, 3))


if __name__ == '__main__':
    unittest.main(verbosity=2)
