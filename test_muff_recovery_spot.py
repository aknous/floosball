"""A muff the kicking team recovers puts the ball, and the next drive, at the muff spot.

Prod game 5318 (2026-10-28): the Strangers punted from their own 41 with the drive clock
nearly out, recovered the Waffles' muff on the STL 3, ran once, and the drive clock
expired. The Waffles then took over at the NYS 41, where the punt had come from.

The muff branch set `yardsToEndzone` but not `yardsToSafety`, which the play loop only
ever advances by `+=` yardage, so it kept the punt spot. The drive-clock expiry (like
every turnover on downs) hands the ball over at `yardsToSafety`. The branch also kept
the punting drive's drive clock, so the recovery started nearly expired.

Run: .venv/bin/python test_muff_recovery_spot.py   (exits non-zero on any failure)
"""
import os, sys, types, asyncio, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import logging; logging.disable(logging.CRITICAL)

if 'floosball_game' not in sys.modules:
    _stub = types.ModuleType('floosball_game')
    _stub.Game = type('G', (), {})
    sys.modules['floosball_game'] = _stub
    import managers.timingManager  # noqa: F401
    del sys.modules['floosball_game']

import numpy as np
import floosball_game as FG
from managers.timingManager import TimingManager, TimingMode
from game_rules import GameRules
from scenario import _makeTeam

fails = []
def expect(d, c):
    print(f"  [{'OK' if c else 'FAIL'}] {d}")
    if not c: fails.append(d)

LIMIT = 8


def _game(index):
    random.seed(index); np.random.seed(index)
    home = _makeTeam('H', 'HOM', 1000 + index * 10)
    away = _makeTeam('A', 'AWY', 5000 + index * 10)
    rules = GameRules(driveClockEnabled=True, driveClockUnit='plays',
                      driveClockReset='possession', driveClockLimit=LIMIT)
    g = FG.Game(home, away, gameRules=rules, timingManager=TimingManager(TimingMode.FAST))
    g.id = index

    # Every punt is a muff the kicking team recovers.
    def _muff(landing, puntType, receivingTeam, _g=g):
        return {'action': 'muff', 'returner': _g._pickReturner(receivingTeam),
                'returnYards': 0, 'muffRecoveredBy': 'kicking'}
    g._resolvePuntReturn = _muff

    seen = {'snaps': 0, 'badSpot': 0, 'afterMuff': 0, 'staleClock': 0, 'muffs': 0}
    lastMuff = [None]
    real = g.playCaller
    def watched():
        seen['snaps'] += 1
        if g.yardsToEndzone + g.yardsToSafety != g.gameRules.fieldLength:
            seen['badSpot'] += 1
        newest = next((e['play'] for e in g.gameFeed if isinstance(e, dict) and 'play' in e), None)
        if (newest is not None and newest is not lastMuff[0]
                and getattr(newest, 'puntAction', None) == 'muff'
                and getattr(newest, 'isFumbleLost', False)):
            lastMuff[0] = newest
            seen['muffs'] += 1
            seen['afterMuff'] += 1
            if g.driveClockRemaining != LIMIT:
                seen['staleClock'] += 1
        return real()
    g.playCaller = watched
    asyncio.run(asyncio.wait_for(g.playGame(), timeout=120))
    return seen


tot = {'snaps': 0, 'badSpot': 0, 'afterMuff': 0, 'staleClock': 0, 'muffs': 0}
for i in range(12):
    s = _game(i)
    for k in tot:
        tot[k] += s[k]

expect(f"{tot['muffs']} kicking-team muff recoveries happened", tot['muffs'] >= 20)
expect(f"both field-position readings agree on every snap ({tot['badSpot']} of {tot['snaps']} off)",
       tot['badSpot'] == 0)
expect(f"the recovery starts a full drive clock ({tot['staleClock']} of {tot['afterMuff']} stale)",
       tot['staleClock'] == 0)

print()
if fails:
    print(f"FAIL — {len(fails)} problem(s):")
    for f in fails:
        print(f"  - {f}")
    sys.exit(1)
print("PASS")
