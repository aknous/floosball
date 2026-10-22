"""Win probability prices who has the ball: nobody before kickoff, and the scorer after
a made sideline goal.

Prod season 11, week 22 (games 4983-4998), reported as odd momentum in the
Monuments-Strangers game (4983):

  * Every made sideline goal moved win probability AGAINST the team that made it, by
    3-8 points, and the next snap swung it back. A scoring play is priced at the
    possession after it (a kickoff), and a hoop is the one score where the scorer keeps
    the ball, so the model handed the ball to the other team at its own 20 for one play.
  * The kickoff number was computed before the coin toss, with no offense and the spot
    at 0, which the model read as the away team on the goal line: about a touchdown
    toward the away team (12.9 WP points on average over 60 games). The first snap then
    booked the correction as a 4-15 point home swing in all 16 games, several of them
    BIG PLAYS with their momentum bonus.

Run: .venv/bin/python -m pytest -q test_wp_possession_pricing.py
"""
import logging
import unittest

logging.disable(logging.CRITICAL)

from game_rules import GameRules
from scenario import Scenario


def _scenario():
    rules = GameRules()
    rules.sidelineGoalsEnabled = True
    return Scenario(gameRules=rules)


class TheKickoffHasNoPossession(unittest.TestCase):

    def _kickoffWp(self, homeElo, awayElo):
        game = _scenario().g
        game.homeTeamElo, game.awayTeamElo = homeElo, awayElo
        game.offensiveTeam = game.defensiveTeam = None
        game.yardsToEndzone = game.down = game.yardsToFirstDown = 0
        game.homeScore = game.awayScore = 0
        game.currentQuarter = 1
        game.gameClockSeconds = game.gameRules.quarterLengthSeconds
        return game.calculateWinProbability()['home']

    def test_evenTeamsAreAnEvenGame(self):
        self.assertAlmostEqual(self._kickoffWp(1500, 1500), 50.0, delta=0.1)

    def test_itIsSymmetric(self):
        self.assertAlmostEqual(self._kickoffWp(1600, 1500) + self._kickoffWp(1500, 1600),
                               100.0, delta=0.1)


class AMadeHoopKeepsTheBall(unittest.TestCase):

    def _wp(self, offScore, made):
        scenario = _scenario().situation(quarter=2, clock=600, offense='home',
                                         offScore=offScore, defScore=7, down=2,
                                         distance=10, ballOn=45)
        game = scenario.g
        if made:
            game.play.scoreChange = True
            game.play.hoopMade = True
            game.play.scoringTeam = game.homeTeam
        return game.calculateWinProbability()['home']

    def test_thePointHelpsTheTeamThatMadeIt(self):
        self.assertGreater(self._wp(8, made=True), self._wp(7, made=False))

    def test_itIsPricedWithTheScorerStillOnOffense(self):
        self.assertAlmostEqual(self._wp(8, made=True), self._wp(8, made=False), delta=0.01)


if __name__ == '__main__':
    unittest.main()
