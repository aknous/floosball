"""A defensive touchdown belongs to the defense everywhere it is reported.

Reported from prod game 2891: an awakened defender stripped the ball on the offense's
own 11 and returned it for a touchdown. The ENGINE scored it correctly (the points
went to the defense), but every report of it pointed at the offense:

- the play payloads carried no scoring team, so the game page anchored the score in
  the OFFENSE's end zone and drew an 89-yard run the wrong way;
- the personality reaction handed "I think I scored. Did I score? I scored." to the
  ball carrier who had just fumbled;
- the power text stopped at "returned 11 yards" where the normal turnover text calls
  the score ("Taken to the house!");
- the legacy score_update event named the offense as the scoring team.

Run: .venv/bin/python test_defensive_td_attribution.py
"""
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import logging
logging.disable(logging.CRITICAL)

import managers  # noqa: F401  — breaks the floosball_game circular import
import floosball_game as fg

HERE = os.path.dirname(os.path.abspath(__file__))


def _src(name):
    with open(os.path.join(HERE, name)) as fh:
        return fh.read()


class Team:
    def __init__(self, abbr):
        self.abbr = abbr


class Player:
    def __init__(self, name):
        self.name = name


class StubPlay:
    def __init__(self, offense, defense, **kw):
        self.offense, self.defense = offense, defense
        self.isTd = False
        self.isPassCompletion = False
        self.isSafety = self.isInterception = self.isFumbleLost = self.isSack = False
        self.runner = self.passer = self.receiver = self.kicker = None
        self.interceptedBy = self.forcedFumbleBy = self.returner = self.sackedBy = None
        self.scoringTeam = None
        self.fgDistance = 0
        self.playResult = None
        self.down, self.yardage, self.yardsTo1st = 1, 0, 10
        for k, v in kw.items():
            setattr(self, k, v)


class StubGame:
    _resolvePersonalityTrigger = fg.Game._resolvePersonalityTrigger

    def __init__(self, play):
        self.play = play


def trigger(play):
    return StubGame(play)._resolvePersonalityTrigger()


class ReactionTests(unittest.TestCase):
    def setUp(self):
        self.off, self.dfn = Team('MIN'), Team('NYS')
        self.runner, self.stripper = Player('Frig Lagotis'), Player('Delimeat Garrison')

    def testTheReportedCaseTheStripperScored(self):
        p = StubPlay(self.off, self.dfn, isTd=True, isFumbleLost=True, runner=self.runner,
                     forcedFumbleBy=self.stripper, scoringTeam=self.dfn)
        self.assertEqual(trigger(p), (self.stripper, 'td_scored'))

    def testAPickSixIsTheInterceptors(self):
        qb, cb = Player('QB'), Player('CB')
        p = StubPlay(self.off, self.dfn, isTd=True, isInterception=True, passer=qb,
                     interceptedBy=cb, scoringTeam=self.dfn)
        self.assertEqual(trigger(p), (cb, 'td_scored'))

    def testNoNamedDefenderFallsToTheTurnoverLine(self):
        """Never the offense's 'I scored' — the fumble line is right for the carrier."""
        p = StubPlay(self.off, self.dfn, isTd=True, isFumbleLost=True, runner=self.runner,
                     scoringTeam=self.dfn)
        self.assertEqual(trigger(p), (self.runner, 'fumble_lost'))

    def testAnOffensiveTouchdownIsUnchanged(self):
        p = StubPlay(self.off, self.dfn, isTd=True, runner=self.runner, scoringTeam=self.off)
        self.assertEqual(trigger(p), (self.runner, 'td_scored'))


class PayloadTests(unittest.TestCase):
    def testAllThreeBuildersCarryTheScoringTeam(self):
        """Two payloads live in the engine, the third is the REST feed. Any one left
        out puts the score back in the wrong end zone on that transport."""
        game = _src('floosball_game.py')
        self.assertEqual(game.count("'scoringTeam': getattr(getattr(playObj, 'scoringTeam'"), 1)
        self.assertEqual(game.count("'scoringTeam': getattr(getattr(self.play, 'scoringTeam'"), 1)
        self.assertEqual(_src('api/main.py').count(
            "'scoringTeam': getattr(getattr(play_data, 'scoringTeam'"), 1)

    def testTheScoreEventNamesTheDefense(self):
        game = _src('floosball_game.py')
        self.assertNotIn("scoringPlay={'type': 'touchdown', 'team': self.offensiveTeam.abbr}", game)

    def testThePowerTextCallsTheScore(self):
        game = _src('floosball_game.py')
        start = game.index("if fire.get('situation') in ('pick', 'strip'):")
        block = game[start:start + 1200]
        self.assertIn('self.yardsToSafety + (self.play.yardage or 0)) <= 0', block)
        self.assertIn('Taken to the house!', block)
        self.assertIn('Pick six!', block)


if __name__ == '__main__':
    unittest.main(verbosity=2)
