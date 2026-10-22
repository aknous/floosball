"""Measure how often a post-touchdown try converts from each distance.

`CONVERSION_MAKE_BY_DISTANCE` (constants.py) is the coaches' read of these rates, used by
every conversion decision (kick or two, which Conversion Ladder rung). It is the engine's
own rate, so it has to be re-measured whenever the conversion play calling
(`Game._simulateConversionPlay`) or the passing / goal-line models move.

  .venv/bin/python conversion_rate_check.py               # 200 matchups x 20 tries a distance
  .venv/bin/python conversion_rate_check.py --pairs 60    # quicker, noisier
"""
import argparse
import logging
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
logging.disable(logging.CRITICAL)
os.environ.setdefault('TIMING_MODE', 'fast')

from game_rules import GameRules
from scenario import Scenario


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pairs', type=int, default=200, help='team matchups')
    ap.add_argument('--tries', type=int, default=20, help='tries per distance per matchup')
    ap.add_argument('--max', type=int, default=20, help='longest distance')
    args = ap.parse_args()

    made, tot = defaultdict(int), defaultdict(int)
    for _ in range(args.pairs):
        rules = GameRules()
        rules.conversionLadderEnabled = True
        scenario = Scenario(gameRules=rules)
        game = scenario.game
        scenario.situation(quarter=2, clock=500, offense='home', down=1, distance=10, ballOn=50)
        game.broadcastGameState = lambda *a, **k: None
        for dist in range(1, args.max + 1):
            for _ in range(args.tries):
                before = game.homeScore
                game._simulateConversionPlay(game.homeTeam, game.awayTeam, 3, dist)
                tot[dist] += 1
                made[dist] += game.homeScore > before

    for dist in range(1, args.max + 1):
        p = made[dist] / tot[dist]
        se = (p * (1 - p) / tot[dist]) ** 0.5
        print(f'{dist:2d} yd: {p:.3f} +/- {se:.3f}  (n={tot[dist]})')


if __name__ == '__main__':
    main()
