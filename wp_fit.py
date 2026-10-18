"""Fit the clock-format win-probability model (`Game.clockModelWp`) to the sim's own outcomes.

Plays seasons on the live league's rosters (`playcall_nfl_check.realTeams`; a synthetic
league if no database is given) with ELO carried the way the league carries it: every team
regressed halfway to 1500 at each season start and updated after every game by
`TeamManager.updateEloAfterGame`. That makes the ELO prior as noisy as production's, which
matters: fitting against a perfect strength estimate would make the model trust ELO more
than the real ratings deserve.

At every play the engine resolves WP for, the harness records `Game._wpClockFeatures`, the
exact inputs `clockModelWp` reads, so the fit and the engine cannot read the game
differently. It then fits the WP_* constants by log loss on half the games, reports the
other half against the model in the engine, and prints a replacement constants block.
It also prints the big-play threshold that holds a given rate (`--hold-rate`).

  .venv/bin/python wp_fit.py --db data/floosball.db                  # ~12 recorded seasons
  .venv/bin/python wp_fit.py --db data/floosball.db --seasons 6 --hold-rate 3.4

Re-fit whenever scoring, the clock, the field-position game or the ELO update moves.
"""
import argparse
import asyncio
import logging
import math
import os
import random
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
logging.disable(logging.CRITICAL)

import numpy as np                                       # noqa: E402
from scipy.optimize import minimize                      # noqa: E402
from scipy.stats import norm                             # noqa: E402
import playcall_nfl_check as P                           # noqa: E402  (handles the import dance)
from managers.teamManager import TeamManager             # noqa: E402

FG = P.FG
KNOTS = np.arange(0, 101, 10.0)


def league(dbPath, seed):
    if dbPath and os.path.exists(dbPath):
        return P.realTeams(dbPath)
    rng = random.Random(seed)
    teams = []
    for t in range(32):
        team = P._makeTeam(f'T{t}', f'T{t:02d}', 10000 + t * 100,
                           phys=rng.randint(74, 92), ment=rng.randint(74, 92),
                           defRun=rng.randint(70, 88), defPass=rng.randint(70, 88))
        team.id = t
        team.coach.generateAttributes()
        teams.append(team)
    return teams


def harvest(teams, seasons, warmup, rounds, seed):
    """Rows of (features..., homeWon, gameId, |homeWpa|) for every resolved play in the
    recorded seasons."""
    rng = random.Random(seed)
    random.seed(seed)
    np.random.seed(seed)
    eloKeeper = types.SimpleNamespace(logger=logging.getLogger('wp_fit'))
    feats, plays = [], []
    state = {'capture': False, 'gid': None}

    origFeatures = FG.Game._wpClockFeatures
    origResolve = FG.Game._resolvePlayWpa

    def features(game, *a, **k):
        f = origFeatures(game, *a, **k)
        if state['capture']:
            feats.append((state['gid'], f))
            state['capture'] = False          # the display call; the credit call repeats it
        return f

    def resolve(game):
        fresh = not getattr(game.play, '_wpaResolved', False)
        state['capture'] = fresh and state['gid'] is not None
        out = origResolve(game)
        state['capture'] = False
        if fresh and state['gid'] is not None:
            plays.append((state['gid'], abs(out[2]), game.play.isBigPlay))
        return out

    FG.Game._wpClockFeatures = features
    FG.Game._resolvePlayWpa = resolve
    outcomes = {}
    gid = 0
    try:
        for t in teams:
            t.elo = 1500
        for season in range(warmup + seasons):
            if season:
                for t in teams:
                    t.elo = max(800, min(2200, round((t.elo + 1500) / 2)))
            for _ in range(rounds):
                order = teams[:]
                rng.shuffle(order)
                for home, away in zip(order[::2], order[1::2]):
                    game = FG.Game(home, away, gameRules=P.GameRules(),
                                   timingManager=P.TimingManager(P.TimingMode.FAST))
                    gid += 1
                    game.id = gid
                    state['gid'] = gid if season >= warmup else None
                    asyncio.run(asyncio.wait_for(game.playGame(), timeout=120))
                    winner = (home if game.homeScore > game.awayScore
                              else away if game.awayScore > game.homeScore else None)
                    TeamManager.updateEloAfterGame(
                        eloKeeper, home, away, game.homeScore, game.awayScore, winner,
                        game.preGameEloHomeWinProbability, game.preGameEloAwayWinProbability)
                    if season >= warmup:
                        outcomes[gid] = (1.0 if winner is home else 0.0 if winner is away else 0.5)
            print(f'season {season + 1}/{warmup + seasons} done; ELO sd '
                  f'{np.std([t.elo for t in teams]):.0f}', flush=True)
    finally:
        FG.Game._wpClockFeatures = origFeatures
        FG.Game._resolvePlayWpa = origResolve
    return feats, plays, outcomes


def matrices(feats, outcomes):
    keys = ('homeLead', 'yte', 'downsLeft', 'ytg', 'timeLeft', 'strengthLogit')
    X = {k: np.array([f[k] for _, f in feats], dtype=float) for k in keys}
    X['sign'] = np.array([1.0 if f['offenseIsHome'] else -1.0 for _, f in feats])
    X['game'] = np.array([g for g, _ in feats])
    y = np.array([outcomes[g] for g, _ in feats])
    return X, y


def predict(th, X, idx):
    value = np.interp(X['yte'][idx], KNOTS, th[:11])
    left = X['downsLeft'][idx]
    pen = np.select([left == 0, left == 1, left == 2], [th[11], th[12], th[13]], 0.0)
    value = value + pen * np.minimum(X['ytg'][idx], 15) / 10
    margin = X['homeLead'][idx] + X['sign'][idx] * value + th[14] * X['strengthLogit'][idx] * X['timeLeft'][idx]
    spread = abs(th[15]) * np.sqrt(X['timeLeft'][idx] + abs(th[16]))
    return np.clip(norm.cdf(margin / spread), 1e-4, 1 - 1e-4)


def calibration(p, y):
    out = []
    for lo in range(0, 100, 10):
        m = (p * 100 >= lo) & (p * 100 < lo + 10)
        if m.sum() >= 50:
            out.append(f'{100 * p[m].mean():.0f}->{100 * y[m].mean():.0f}')
    return '  '.join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--db', default='data/floosball.db')
    ap.add_argument('--seasons', type=int, default=12, help='recorded seasons')
    ap.add_argument('--warmup', type=int, default=1, help='unrecorded seasons to settle ELO')
    ap.add_argument('--rounds', type=int, default=28, help='games per team per season')
    ap.add_argument('--seed', type=int, default=20261018)
    ap.add_argument('--legacy', action='store_true',
                    help='play the same seasons on the hand-built core and report only its '
                         'big-play rate (the rate --hold-rate should preserve)')
    ap.add_argument('--hold-rate', type=float, default=None,
                    help='big plays per game to hold: prints the WPA threshold that gives it')
    args = ap.parse_args()

    teams = league(args.db, args.seed)
    print(f'{len(teams)} teams', flush=True)
    if args.legacy:
        import game_formats
        game_formats.GameFormat.clockWinProbability = False
    feats, plays, outcomes = harvest(teams, args.seasons, args.warmup, args.rounds, args.seed)
    if args.legacy:
        ng = len({g for g, _, _ in plays})
        wpa = np.array([w for _, w, _ in plays])
        print(f'hand-built core: big plays/game at 7.0 = {(wpa >= 7.0).sum() / ng:.2f} over {ng} games')
        return
    X, y = matrices(feats, outcomes)
    games = np.unique(X['game'])
    rng = np.random.default_rng(1)
    rng.shuffle(games)
    trainGames = set(games[: len(games) // 2])
    # A tie at regulation's 0:00 is read as the coin flip by the engine whatever these say.
    live = ~((X['timeLeft'] <= 0) & (X['homeLead'] == 0))
    train = np.array([g in trainGames for g in X['game']]) & live
    test = ~np.array([g in trainGames for g in X['game']]) & live
    print(f'{len(y)} states from {len(games)} games', flush=True)

    def loss(th):
        p = predict(th, X, train)
        return -np.mean(y[train] * np.log(p) + (1 - y[train]) * np.log(1 - p))

    th0 = np.concatenate([np.interp(KNOTS, [0, 100], [5, -1]), [-2.5, -1.0, -0.3], [8.0], [15.0], [0.03]])
    res = minimize(loss, th0, method='L-BFGS-B', options={'maxiter': 3000})
    th = res.x
    fitted = predict(th, X, test)
    engine = np.array([FG.Game.clockModelWp(f) / 100 for (g, f), t in zip(feats, test) if t])
    yt = y[test]

    def score(p):
        return np.mean((p - yt) ** 2), -np.mean(yt * np.log(np.clip(p, 1e-4, 1 - 1e-4))
                                                 + (1 - yt) * np.log(np.clip(1 - p, 1e-4, 1 - 1e-4)))
    print(f'held-out  engine constants: Brier {score(engine)[0]:.4f} logloss {score(engine)[1]:.4f}')
    print(f'held-out  this fit:         Brier {score(fitted)[0]:.4f} logloss {score(fitted)[1]:.4f}')
    print(f'calibration engine: {calibration(engine, yt)}')
    print(f'calibration fit:    {calibration(fitted, yt)}')
    late = X['timeLeft'][test] <= 300 / 3600
    print(f'last 5:00 fit:      {calibration(fitted[late], yt[late])}')

    ng = len({g for g, _, _ in plays})
    wpa = np.array([w for _, w, _ in plays])
    print(f'big plays/game under the engine constants: {sum(b for _, _, b in plays) / ng:.2f} '
          f'(threshold {FG.BIG_PLAY_WPA_THRESHOLD})')
    if args.hold_rate:
        grid = np.arange(6.0, 14.01, 0.25)
        rates = np.array([(wpa >= t).sum() / ng for t in grid])
        best = grid[int(np.argmin(np.abs(rates - args.hold_rate)))]
        print(f'threshold holding {args.hold_rate}/game: {best:.2f} (gives '
              f'{(wpa >= best).sum() / ng:.2f}); nearby: ' +
              '  '.join(f'{t:.2f}->{r:.2f}' for t, r in zip(grid, rates) if abs(t - best) <= 0.75))

    r = lambda v: float(f'{v:.2f}')
    print('\n# ── paste into constants.py ──')
    print(f'WP_FIELD_VALUE = {[r(v) for v in th[:11]]}')
    print(f'WP_DOWN_PENALTY = {[r(v) for v in th[11:14]]}')
    print(f'WP_STRENGTH_PER_LOGIT = {r(th[14])}')
    print(f'WP_MARGIN_SIGMA = {r(abs(th[15]))}')
    print(f'WP_TIME_FLOOR = {abs(th[16]):.4f}')


if __name__ == '__main__':
    main()
