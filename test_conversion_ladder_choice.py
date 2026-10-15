"""Conversion choice under the Conversion Ladder: the two-pointer is the default, and the
rungs above it are taken where the score calls for them, overtime included.

⚠️ AUDITED 2026-10-15 ahead of a ladder postseason. Three faults:
  * Overtime took the default whatever the score, so the second team, down 3 after its
    touchdown, went for two and lost even when it made it. Same in a normal game: down 2,
    it kicked one and lost.
  * A touchdown at 0:00 was valued as if the game went on, so a team that had just tied it
    took the 3 about half the time over the likelier 2.
  * Before Q4 a 90+ coach reached for the 3 or 4 on every touchdown, off a make-rate
    estimate that assumes the two-pointer converts 70% (measured 45%). Owner: "the 2 pt
    conversion should essentially be the default like the 1pt kick usually is".

Run: .venv/bin/python -m pytest -q test_conversion_ladder_choice.py
"""
import collections
import logging
import unittest

logging.disable(logging.CRITICAL)

from game_rules import GameRules
from scenario import Scenario


STINGY = (9, 3)      # opponent drives, offensive points: the defense has been holding
SHREDDED = (9, 42)   # the defense has been run over


def picks(*, quarter, clock, margin, ladder=True, aggr=80, ot=None, defense=None, trials=60):
    """Tally the chosen rung (points, or 'kick') with the scoring team at `margin`
    after its touchdown. `defense` = (opponent drives, opponent offensive points) so far."""
    out = collections.Counter()
    for _ in range(trials):
        rules = GameRules()
        rules.conversionLadderEnabled = ladder
        scenario = Scenario(gameRules=rules)
        game = scenario.game
        scenario.situation(quarter=quarter, clock=clock, offense='home',
                           offScore=20 + margin, defScore=20, down=1, distance=10, ballOn=50)
        game.homeTeam.coach.aggressiveness = aggr
        if defense:
            game._drivesBy[id(game.awayTeam)], game._offensePointsBy[id(game.awayTeam)] = defense
        if ot:
            game.otPeriod = 1
            game.otFirstPossTeam = game.homeTeam if ot == 'first' else game.awayTeam
            game.otFirstPossComplete = ot != 'first'
            game.otSecondPossComplete = False
        rung = game._chooseConversion(game.homeTeam)
        out['kick' if rung['kind'] == 'kick' else rung['points']] += 1
    return out


class TheTwoIsTheDefault(unittest.TestCase):

    def test_beforeTheFourthEveryCoachGoesForTwo(self):
        for aggr in (60, 80, 100):
            with self.subTest(aggr=aggr):
                self.assertEqual(picks(quarter=2, clock=420, margin=6, aggr=aggr), {2: 60})


class OvertimeReadsTheScore(unittest.TestCase):

    def test_theSecondTeamTakesTheRungThatWins(self):
        """Its try is the last word: down 2/3/4 after the touchdown, only the 3/4/5 wins
        (a neutral coach, no evidence on the defense yet)."""
        for margin, rung in ((-2, 3), (-3, 4), (-4, 5)):
            with self.subTest(margin=margin):
                self.assertEqual(picks(quarter=5, clock=400, margin=margin, ot='second'),
                                 {rung: 60})

    def test_aTiedSecondTeamTakesTheLikeliestMake(self):
        """Tied after the touchdown, any make wins, so the two."""
        self.assertEqual(picks(quarter=5, clock=400, margin=0, ot='second'), {2: 60})

    def test_withoutTheLadderDownTwoGoesForTwo(self):
        """The same fault under the normal rules: the kick only gets to down 1 and loses."""
        self.assertEqual(picks(quarter=5, clock=400, margin=-2, ladder=False, ot='second'),
                         {2: 60})


class TemperamentAndTheDefense(unittest.TestCase):
    """Owner (2026-10-15): a conservative coach goes for the tie instead of the win, and
    every coach weighs whether they trust their defense to get the stop, in any game. It
    works through one channel: how likely the coach thinks the opponent is to score, read
    from the defense's showing this game and scaled by the coach's temperament."""

    def test_aConservativeCoachTakesTheTieInOvertime(self):
        """Down 4 after the touchdown: the 4 ties (36%), the 5 wins (21%). A conservative
        coach ties, a neutral one goes for the win."""
        self.assertEqual(picks(quarter=5, clock=400, margin=-4, aggr=60, ot='second'), {4: 60})
        self.assertEqual(picks(quarter=5, clock=400, margin=-4, aggr=80, ot='second'), {5: 60})

    def test_theDefenseDecidesForACautiousCoach(self):
        """Same spot, aggressiveness 70: a defense that has been holding earns the tie, one
        that has been shredded does not."""
        self.assertEqual(picks(quarter=5, clock=400, margin=-4, aggr=70, ot='second',
                               defense=STINGY), {4: 60})
        self.assertEqual(picks(quarter=5, clock=400, margin=-4, aggr=70, ot='second',
                               defense=SHREDDED), {5: 60})

    def test_withoutTheLadderACautiousCoachKicksToTie(self):
        """Overtime, down 1: kick to tie unless the defense has been run over."""
        out = picks(quarter=5, clock=400, margin=-1, ladder=False, aggr=70, ot='second')
        self.assertGreaterEqual(out['kick'], 55, out)   # a weak generated kicker can flip one
        self.assertEqual(picks(quarter=5, clock=400, margin=-1, ladder=False, aggr=70,
                               ot='second', defense=SHREDDED), {2: 60})

    def test_aStingyDefenseMeansMoreKicksInTheFourth(self):
        """Down 1 with 3:00 left, a neutral coach: trusting the defense to get the ball
        back, the tie is worth more."""
        stingy = picks(quarter=4, clock=180, margin=-1, ladder=False, defense=STINGY)
        shredded = picks(quarter=4, clock=180, margin=-1, ladder=False, defense=SHREDDED)
        self.assertGreater(stingy['kick'], shredded['kick'] + 15, (stingy, shredded))


class TheLastPlayOfRegulation(unittest.TestCase):

    def test_tiedAtZeroTakesTheLikeliestMake(self):
        self.assertEqual(picks(quarter=4, clock=0, margin=0), {2: 60})

    def test_downThreeAtZeroGoesForTheWinEveryTime(self):
        self.assertEqual(picks(quarter=4, clock=0, margin=-3), {4: 60})


if __name__ == '__main__':
    unittest.main()
