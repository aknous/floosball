"""Drive-clock tuning sweep — measure how often each preset actually kills a drive.

Measured on live prod games (2026-07-22) the presets ended drives at very different
rates: 120s/possession 19%, 6 plays/possession 27%, 45s/series 32%. At 45s/series
the clock ended as many drives as PUNTS did, which makes the shot clock the primary
way drives die rather than a pressure on top of the down system.

This plays real games locally with a given {unit, reset, limit} and reports the
share of drive endings that were a drive-clock expiry, so limits can be set against
a target rather than guessed.

  .venv/bin/python tune_drive_clock.py                 # sweep the candidates
  .venv/bin/python tune_drive_clock.py --games 30      # more samples per config
"""
import argparse, asyncio, logging, os, sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
logging.disable(logging.CRITICAL)
os.environ.setdefault('TIMING_MODE', 'fast')

from scenario import _makeTeam            # real team construction
import floosball_game as _FG
from game_rules import GameRules

TARGET = 0.15   # share of drive endings that should be a drive-clock expiry


def _rules(unit, reset, limit):
    gr = GameRules()
    gr.driveClockEnabled = True
    gr.driveClockUnit = unit
    gr.driveClockReset = reset
    gr.driveClockLimit = limit
    return gr


def _endings(game) -> Counter:
    """Classify how each possession ended, from the play feed."""
    e = Counter()
    for entry in (game.gameFeed or []):
        play = entry.get('play') if isinstance(entry, dict) else None
        if play is None:
            continue
        res = str(getattr(getattr(play, 'playResult', None), 'value', '') or '')
        if 'Drive Clock Expired' in res:
            e['driveClockExpired'] += 1
        elif getattr(play, 'isTd', False):
            e['touchdown'] += 1
        elif getattr(play, 'isFumbleLost', False) or getattr(play, 'isInterception', False):
            e['turnover'] += 1
        elif res.startswith('Punt'):
            e['punt'] += 1
        elif 'Field Goal' in res:
            e['fieldGoal'] += 1
        elif 'Turnover on Downs' in res:
            e['downs'] += 1
    return e


async def runConfig(unit, reset, limit, games):
    total = Counter()
    for i in range(games):
        home = _makeTeam('Homers', 'HOM', 100 + i)
        away = _makeTeam('Awayers', 'AWY', 200 + i)
        g = _FG.Game(home, away, gameRules=_rules(unit, reset, limit))
        g.timingManager = None
        await g.playGame()
        total += _endings(g)
    return total


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--games', type=int, default=12)
    args = ap.parse_args()

    # current presets plus loosened candidates for each
    configs = [
        ('seconds', 'possession', 120), ('seconds', 'possession', 150),
        ('seconds', 'possession', 180),
        ('plays',   'possession', 6),   ('plays',   'possession', 8),
        ('plays',   'possession', 10),
        ('seconds', 'series',     45),  ('seconds', 'series',     70),
        ('seconds', 'series',     90),
    ]
    print(f"{args.games} games per config · target {TARGET:.0%} of drive endings\n")
    print(f"{'unit':<9} {'reset':<11} {'limit':>5} {'drives':>7} {'expired':>8} "
          f"{'rate':>6}  {'vs target':>9}")
    print('-' * 62)
    for unit, reset, limit in configs:
        e = await runConfig(unit, reset, limit, args.games)
        tot = sum(e.values())
        dce = e['driveClockExpired']
        rate = dce / max(tot, 1)
        flag = 'ok' if abs(rate - TARGET) <= 0.04 else ('HIGH' if rate > TARGET else 'low')
        print(f"{unit:<9} {reset:<11} {limit:>5} {tot:>7} {dce:>8} {rate:>5.0%}  {flag:>9}")


if __name__ == '__main__':
    asyncio.run(main())
