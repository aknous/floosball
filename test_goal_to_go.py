"""A fresh set of downs inside the 10 is 1st & goal, not 1st & 10.

⚠️ THE GOAL-TO-GO TEST READ A STALE SPOT. When a play earned a first down, the check
"is the goal line closer than the first-down distance?" ran BEFORE the ball was moved
for the play, so it asked about where the play STARTED. A 15-yard gain from the 20
checked "20 out", set 1st & 10, and only then placed the ball on the 5. Compared with
NFL 2021-25 play-by-play, 86% of the sim's 1st downs inside the 10 carried a distance of
10, so the play caller read 1st & goal from the 3 as 1st & 10 and 3rd & goal from the 2
as 3rd & long. The display was never wrong (Play.yardsTo1st prints 'Goal' off the spot),
which is why it went unnoticed.

A turnover recovered inside the 10 had the same fault (it always handed over 1st & 10).

Run: .venv/bin/python test_goal_to_go.py
"""
import os
import sys
import types
import asyncio
import random
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import logging
logging.disable(logging.CRITICAL)

if 'floosball_game' not in sys.modules:
    _stub = types.ModuleType('floosball_game')
    _stub.Game = type('G', (), {})
    sys.modules['floosball_game'] = _stub
    import managers.timingManager  # noqa: F401
    del sys.modules['floosball_game']

import floosball_game as FG  # noqa: E402
import floosball_team as FT  # noqa: E402
from managers.timingManager import TimingManager, TimingMode  # noqa: E402
from game_rules import GameRules  # noqa: E402
from scenario import _makeTeam  # noqa: E402


class GoalToGo(unittest.TestCase):

    def testEveryFirstDownInsideTheTenIsGoalToGo(self):
        seen = []
        original = FG.Game.playCaller
        savedAverages = FT.Team.getAverages

        def hooked(game):
            if game.down == 1 and game.yardsToEndzone < game.gameRules.firstDownDistance:
                seen.append((game.yardsToEndzone, game.yardsToFirstDown))
            return original(game)

        FG.Game.playCaller = hooked
        FT.Team.getAverages = lambda self, season=None: None   # DB-backed display stat
        try:
            for i in range(25):
                rr = random.Random(300 + i)
                home = _makeTeam('H', 'HOM', 1000 + i * 10, phys=rr.randint(78, 94), ment=80)
                away = _makeTeam('A', 'AWY', 5000 + i * 10, phys=rr.randint(70, 86), ment=80)
                game = FG.Game(home, away, gameRules=GameRules(),
                               timingManager=TimingManager(TimingMode.FAST))
                game.id = i
                asyncio.run(asyncio.wait_for(game.playGame(), timeout=120))
        finally:
            FG.Game.playCaller = original
            FT.Team.getAverages = savedAverages
        self.assertGreater(len(seen), 20, 'too few 1st downs inside the 10 to judge')
        wrong = [s for s in seen if s[1] != s[0]]
        self.assertEqual(wrong, [], f'{len(wrong)} of {len(seen)} 1st downs inside the 10 '
                                    f'were not goal-to-go, e.g. {wrong[:5]} (spot, to go)')


if __name__ == '__main__':
    unittest.main()
