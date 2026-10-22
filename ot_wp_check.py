"""Measure overtime win rates by field position: tied overtime, and the answering possession.

`OT_FIRST_POSS_WP` / `OT_NEXT_SCORE_WP` (constants.py) are the tied rates, and
`OT_ANSWER_*` are the answering team's drive rates (first team scored, second team trailing
on its one guaranteed possession): touchdown and any-score rate when a field goal ties or
wins (down 3 or less), touchdown rate when only a touchdown will do. Regulation is cut
to one second a quarter, so nearly every game reaches a fresh 0-0 overtime; each OT snap
is bucketed by phase and yards to the end zone and scored against who won. Prints
actual / model per 10-yard bucket. Re-measure when OT rules, the kicking model or the
offense move.

  .venv/bin/python ot_wp_check.py                  # 5000 games, seed 5
  .venv/bin/python ot_wp_check.py --games 3000 --seed 9
"""
import argparse
import asyncio
import logging
import os
import random
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
logging.disable(logging.CRITICAL)

import numpy as np                                     # noqa: E402
import playcall_nfl_check as P                         # noqa: E402  (handles the import dance)

FG = P.FG


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--games', type=int, default=5000)
    ap.add_argument('--seed', type=int, default=5)
    args = ap.parse_args()

    snaps = []
    answerSnaps = []      # (gid, deficit, bucket, modelWp)
    answerStart = {}      # gid -> (team, its score when the answer began)
    answerPts = {}        # gid -> points the answering possession scored
    original = FG.Game.playCaller
    originalTurnover = FG.Game.turnover

    def scoreOf(game, team):
        return game.homeScore if team is game.homeTeam else game.awayScore

    def turnover(game, offense, defense, yards):
        if game.id in answerStart and game.id not in answerPts and offense is answerStart[game.id][0]:
            answerPts[game.id] = scoreOf(game, offense) - answerStart[game.id][1]
        return originalTurnover(game, offense, defense, yards)

    def hooked(game):
        if (game.currentQuarter >= 5 and game.otPeriod <= 1 and game.otFirstPossComplete
                and not game.otSecondPossComplete and game.offensiveTeam is not game.otFirstPossTeam
                and game.homeScore != game.awayScore):
            off = game.offensiveTeam
            answerStart.setdefault(game.id, (off, scoreOf(game, off)))
            wp = game.calculateWinProbability()['home']
            answerSnaps.append((game.id, scoreOf(game, game.defensiveTeam) - scoreOf(game, off),
                                min(9, game.yardsToEndzone // 10),
                                wp if off is game.homeTeam else 100 - wp))
        if game.currentQuarter >= 5 and game.homeScore == game.awayScore:
            offHome = game.offensiveTeam is game.homeTeam
            nextScore = game.otPeriod >= 2 or game.otSecondPossComplete or game.otFirstPossComplete
            wp = game.calculateWinProbability()['home']
            snaps.append((game.id, 'nextScore' if nextScore else 'firstPoss', offHome,
                          min(9, game.yardsToEndzone // 10), wp if offHome else 100 - wp))
        return original(game)

    FG.Game.playCaller = hooked
    FG.Game.turnover = turnover
    rng = random.Random(args.seed)
    random.seed(args.seed)
    np.random.seed(args.seed)
    teams = []
    for t in range(32):
        team = P._makeTeam(f'T{t}', f'T{t:02d}', 10000 + t * 100,
                           phys=rng.randint(74, 92), ment=rng.randint(74, 92),
                           defRun=rng.randint(70, 88), defPass=rng.randint(70, 88))
        team.id = t
        team.coach.generateAttributes()
        teams.append(team)

    homeWon, firstWon = {}, []
    try:
        for g in range(args.games):
            home, away = rng.sample(teams, 2)
            rules = P.GameRules()
            rules.quarterLengthSeconds = 1
            game = FG.Game(home, away, gameRules=rules,
                           timingManager=P.TimingManager(P.TimingMode.FAST))
            game.id = g
            asyncio.run(asyncio.wait_for(game.playGame(), timeout=120))
            if g in answerStart:
                team = answerStart[g][0]
                answerPts.setdefault(g, scoreOf(game, team) - answerStart[g][1])
                answerStart[g] = (team, answerStart[g][1], scoreOf(game, team) > (
                    game.homeScore + game.awayScore - scoreOf(game, team)))
            if game.otPeriod >= 1 and game.homeScore != game.awayScore:
                homeWon[g] = game.homeScore > game.awayScore
                if game.otFirstPossTeam is not None:
                    firstWon.append((game.otFirstPossTeam is game.homeTeam) == homeWon[g])
    finally:
        FG.Game.playCaller = original
        FG.Game.turnover = originalTurnover

    print(f'{args.games} games, {len(homeWon)} decided in overtime; '
          f'first-possession team won {np.mean(firstWon):.3f}')
    agg = defaultdict(lambda: [0, 0, 0.0])
    for gid, phase, offHome, bucket, modelWp in snaps:
        if gid in homeWon:
            a = agg[(phase, bucket)]
            a[0] += 1
            a[1] += homeWon[gid] == offHome
            a[2] += modelWp
    for phase in ('firstPoss', 'nextScore'):
        print(f'{phase}  (yards to go: actual% / model%, n)')
        for b in range(10):
            n, won, model = agg[(phase, b)]
            if n >= 30:
                print(f'   {b * 10:>2}-{b * 10 + 9:<2}  {100 * won / n:5.1f} / {model / n:5.1f}  (n={n})')

    td = float(getattr(P.GameRules(), 'fieldGoalPoints', 3))
    for label, inDrive in (('answer, down a field goal or less', lambda d: d <= td),
                           ('answer, down more than a field goal', lambda d: d > td)):
        agg = defaultdict(lambda: [0, 0, 0, 0, 0.0])
        for gid, deficit, bucket, modelWp in answerSnaps:
            if not inDrive(deficit) or gid not in answerPts or len(answerStart[gid]) < 3:
                continue
            a = agg[bucket]
            a[0] += 1
            a[1] += answerPts[gid] >= 6
            a[2] += answerPts[gid] >= 3
            a[3] += answerStart[gid][2]
            a[4] += modelWp
        print(f'{label}  (yards to go: TD% / any-score% / won% / model%, n)')
        for b in range(10):
            n, tds, scores, won, model = agg[b]
            if n >= 30:
                print(f'   {b * 10:>2}-{b * 10 + 9:<2}  {100 * tds / n:5.1f} / {100 * scores / n:5.1f} / '
                      f'{100 * won / n:5.1f} / {model / n:5.1f}  (n={n})')


if __name__ == '__main__':
    main()

