"""Win probability lands on the play that earned it: turnovers and overtime.

1. A possession-ending play is priced at the possession the NEXT snap will have. Every
   turnover branch broadcasts the play before `turnover()` runs, so an interception or
   a turnover on downs used to show ~0 WPA and hand its swing to the other team's next
   snap (often a kneel, tagged BIG PLAY).
2. A tie at regulation's 0:00 reads as the coin flip, tied overtime uses the measured
   offense win rates, and the coin toss / kickoff moves the baseline without being
   charged to the first overtime snap (which was tagged BIG PLAY in 3 of 4 overtimes).
3. The answering possession (first team scored, second team trailing on its one
   guaranteed possession) is valued from measured drive rates and what each score is
   worth, and a touchdown with its try still owed is never read as a finished game.

  .venv/bin/python test_wp_possession_and_overtime.py      (or with pytest)
"""
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
logging.disable(logging.CRITICAL)
os.environ.setdefault('TIMING_MODE', 'fast')

from scenario import Scenario                     # noqa: E402
from game_rules import GameRules                  # noqa: E402
import floosball_game as FG                       # noqa: E402
from constants import (OT_FIRST_POSS_WP, OT_FIRST_POSS_WP_YTE, OT_NEXT_SCORE_WP,  # noqa: E402
                       OT_NEXT_SCORE_WP_YTE, OT_ANSWER_WP_YTE, OT_ANSWER_TD_DRIVE_TD,
                       OT_ANSWER_FG_DRIVE_TD, OT_ANSWER_FG_DRIVE_SCORE)
import numpy as np                                # noqa: E402

STATE = FG.Game._POSSESSION_STATE


def _snapshot(g):
    return {k: getattr(g, k, None) for k in STATE}


def _equalElo(g):
    g.homeTeamElo = g.awayTeamElo = 1500


def test_a_turnover_play_is_priced_at_the_next_possession():
    # Home, leading by 3 late, throws a pick at the opponent's 40: the away team will
    # take over at its own 40 (yardsToEndzone 60).
    sc = Scenario().situation(quarter=4, clock=150, offense='home', offScore=20, defScore=17,
                              down=2, distance=8, ballOn=40)
    g = sc.game
    _equalElo(g)
    g.play.playType = FG.PlayType.Pass
    g.previousHomeWinProbability = g.calculateWinProbability()['home']
    g.previousAwayWinProbability = 100 - g.previousHomeWinProbability
    before = _snapshot(g)

    g._priceAtNextPossession(g.offensiveTeam, g.defensiveTeam, 60)
    homeWp, _, homeWpa, _ = g._resolvePlayWpa()
    assert _snapshot(g) == before, 'pricing the next possession must leave the game state untouched'
    assert getattr(g, '_wpNextPossession', None) is None, 'the note is consumed'

    # The same number the game reads once the turnover has actually happened.
    g.play = FG.Play(g)
    g.turnover(g.offensiveTeam, g.defensiveTeam, 60)
    assert abs(g.calculateWinProbability()['home'] - homeWp) < 0.05
    assert homeWpa <= -7.0, f'losing the ball while leading late is a big swing, got {homeWpa}'


def test_without_a_note_the_play_is_priced_as_it_stands():
    sc = Scenario().situation(quarter=2, clock=400, offense='home', down=1, distance=10, ballOn=50)
    g = sc.game
    expected = g.calculateWinProbability()['home']
    g.previousHomeWinProbability = g.previousAwayWinProbability = 50.0
    g.play.playType = FG.PlayType.Run
    homeWp, *_ = g._resolvePlayWpa()
    assert abs(homeWp - expected) < 0.05


def test_innings_cannot_preview_its_receiver():
    # possessionReceiver spends tries and re-runs gameplans, so innings opts out.
    rules = GameRules()
    rules.gameFormat = 'innings'
    sc = Scenario(gameRules=rules).situation(quarter=1, clock=600, offense='away', ballOn=60)
    g = sc.game
    assert g.format.previewPossessionReceiver(g, g.offensiveTeam, g.defensiveTeam) is None
    tries = getattr(g, '_inningsTries', 0)
    g.previousHomeWinProbability = g.previousAwayWinProbability = 50.0
    g._priceAtNextPossession(g.offensiveTeam, g.defensiveTeam, 60)
    g.play.playType = FG.PlayType.Pass
    g._resolvePlayWpa()
    assert getattr(g, '_inningsTries', 0) == tries


def test_a_tie_at_the_end_of_regulation_is_a_coin_flip():
    # Tied, regulation clock spent, the offense sitting at midfield: overtime is next and
    # nobody has the ball yet.
    sc = Scenario().situation(quarter=4, clock=0, offense='home', offScore=17, defScore=17,
                              down=3, distance=4, ballOn=50)
    g = sc.game
    _equalElo(g)
    assert abs(g.calculateWinProbability()['home'] - 50.0) < 0.05


def test_tied_overtime_uses_the_measured_rates():
    sc = Scenario().situation(quarter=5, clock=600, offense='home', offScore=10, defScore=10,
                              down=1, distance=10, ballOn=80, otPeriod=1)
    g = sc.game
    _equalElo(g)
    first = float(np.interp(80, OT_FIRST_POSS_WP_YTE, OT_FIRST_POSS_WP))
    assert abs(g.calculateWinProbability()['home'] - first) < 0.1

    # First team's possession ended without a score: any score by the offense now wins.
    sc.situation(quarter=5, clock=400, offense='away', offScore=10, defScore=10,
                 down=1, distance=10, ballOn=25, otPeriod=1, otFirstPossTeam=sc.home,
                 otFirstPossComplete=True)
    _equalElo(g)
    nxt = float(np.interp(25, OT_NEXT_SCORE_WP_YTE, OT_NEXT_SCORE_WP))
    assert abs(g.calculateWinProbability()['away'] - nxt) < 0.1


def test_the_coin_toss_is_not_charged_to_the_first_overtime_snap():
    sc = Scenario().situation(quarter=5, clock=600, offense='home', offScore=10, defScore=10,
                              down=1, distance=10, ballOn=80, otPeriod=1)
    g = sc.game
    _equalElo(g)
    g.previousHomeWinProbability = g.previousAwayWinProbability = 50.0   # end of regulation
    g._rebaseWinProbability()
    assert abs(g.previousHomeWinProbability - g.calculateWinProbability()['home']) < 0.05
    # A short gain from the own 20 does not move a tied overtime, so the snap is not big.
    sc._newPlay()
    g.play.playType = FG.PlayType.Run
    g.yardsToEndzone = 76
    _, _, homeWpa, _ = g._resolvePlayWpa()
    assert abs(homeWpa) < 7.0 and not g.play.isBigPlay


def _answering(sc, deficit, ballOn):
    """Away answers, trailing by `deficit`, after home scored on the first possession."""
    sc.situation(quarter=5, clock=420, offense='away', offScore=10, defScore=10 + deficit,
                 down=1, distance=10, ballOn=ballOn, otPeriod=1, otFirstPossTeam=sc.home,
                 otFirstPossComplete=True)
    _equalElo(sc.game)
    return sc.game


def test_answering_down_a_touchdown_is_the_td_rate_times_what_the_td_is_worth():
    sc = Scenario()
    g = _answering(sc, 7, 80)
    pTd = float(np.interp(80, OT_ANSWER_WP_YTE, OT_ANSWER_TD_DRIVE_TD))
    worth = g._otConversionValue(g.awayTeam, 7 - 6)      # TD leaves them down 1
    assert 0.40 < worth < 0.60, worth                     # a kick ties, a two wins
    assert abs(g.calculateWinProbability()['away'] - pTd * worth) < 0.1


def test_answering_down_a_field_goal_counts_the_tying_kick():
    sc = Scenario()
    g = _answering(sc, 3, 25)
    pTd = float(np.interp(25, OT_ANSWER_WP_YTE, OT_ANSWER_FG_DRIVE_TD))
    pScore = float(np.interp(25, OT_ANSWER_WP_YTE, OT_ANSWER_FG_DRIVE_SCORE))
    expected = pTd + (pScore - pTd) * g._otTieValue()
    assert abs(g.calculateWinProbability()['away'] - expected) < 0.1
    assert g.calculateWinProbability()['away'] > 55, 'on the 25 down 3 the answering team is favored'


def test_an_overtime_touchdown_with_its_try_owed_is_not_final():
    # The answering team scores from down 7: down 1, try to come.
    sc = Scenario()
    g = _answering(sc, 7, 2)
    g.play.playType = FG.PlayType.Run
    g._addScore(g.awayTeam, 6)
    g.play.playResult = FG.PlayResult.Touchdown
    g.play.scoreChange = True
    g.play.isTd = True
    assert g._tryStillOwed()
    away = g.calculateWinProbability()['away']
    assert 30 < away < 70, f'the try decides it, got {away}'
    # Priced at the next possession too (both guaranteed possessions look done there).
    g.previousHomeWinProbability = g.previousAwayWinProbability = 30.0
    g._priceAtNextPossession(g.awayTeam, g.homeTeam, 80)
    homeWp, awayWp, _, _ = g._resolvePlayWpa()
    assert abs(awayWp - away) < 0.2, (awayWp, away)


def test_a_regulation_touchdown_at_zero_with_its_try_owed_is_not_final():
    sc = Scenario().situation(quarter=4, clock=0, offense='home', offScore=14, defScore=21,
                              down=1, distance=2, ballOn=2)
    g = sc.game
    _equalElo(g)
    g._addScore(g.homeTeam, 6)
    g.play.playResult = FG.PlayResult.Touchdown
    g.play.scoreChange = True
    g.play.isTd = True
    home = g.calculateWinProbability()['home']
    assert 1 < home < 99, f'down 1 with the try to come is not decided, got {home}'


if __name__ == '__main__':
    for name, fn in list(globals().items()):
        if name.startswith('test_'):
            fn()
            print('ok', name)
