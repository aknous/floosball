"""A punt charges the game clock once.

The punt block charges kick + hang + return in one place. Below it sat the old one-line
punt's own `calculatePlayDuration(Punt)` + `consumeGameTime`, left behind when the return
model arrived, so every ordinary punt paid the snap-and-kick twice (4-6s) while a muff
or a return TD, which break out before it, paid it once.

Run: .venv/bin/python test_punt_clock.py
"""

import os
import sys
import asyncio
import random
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_play_feed_dedup import FG, TimingManager, TimingMode, GameRules, _makeTeam  # noqa: E402


class PuntClockTest(unittest.TestCase):
    def test_each_punt_consumes_game_time_once(self):
        rr = random.Random(4242)
        home = _makeTeam('H', 'HOM', 4242, phys=rr.randint(74, 92), ment=rr.randint(74, 92))
        away = _makeTeam('A', 'AWY', 5242, phys=rr.randint(74, 92), ment=rr.randint(74, 92))
        game = FG.Game(home, away, gameRules=GameRules(), timingManager=TimingManager(TimingMode.FAST))
        game.id = 4242

        # Count clock charges made while a punt is being resolved: between the kick
        # duration being computed and the play being formatted.
        charges, state = [], {'inPunt': False, 'n': 0}
        origDur, origConsume, origFormat = game.calculatePlayDuration, game.consumeGameTime, game.formatPlayText

        def dur(playType, *a, **kw):
            if playType is FG.PlayType.Punt and not state['inPunt']:
                state['inPunt'], state['n'] = True, 0
            return origDur(playType, *a, **kw)

        def consume(*a, **kw):
            if state['inPunt']:
                state['n'] += 1
            return origConsume(*a, **kw)

        def fmt(*a, **kw):
            if state['inPunt']:
                charges.append(state['n'])
                state['inPunt'] = False
            return origFormat(*a, **kw)

        game.calculatePlayDuration, game.consumeGameTime, game.formatPlayText = dur, consume, fmt
        asyncio.run(asyncio.wait_for(game.playGame(), timeout=120))
        self.assertGreater(len(charges), 3, 'too few punts to measure')
        self.assertEqual(set(charges), {1}, f'clock charges per punt: {charges}')


if __name__ == '__main__':
    unittest.main(verbosity=2)
