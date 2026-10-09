"""Frames: a score that ends a frame must not leave a kickoff queued for later.

A touchdown, field goal or safety sets `_pendingKickoff`. At a frame boundary the
kickoff block is skipped, because `_frameBoundaryReset` starts the next frame itself
(alternating team, own 20). The reset cleared `_pendingPossessionChange` but not
`_pendingKickoff`, so the flag survived into the new frame and fired on the NEXT
possession change, whatever it was. Prod game 4073: a field goal ended frame 1, and in
frame 2 a lost fumble printed "WAS kicks off" between the fumble and the recovering
team's first snap. Field position was right; only the feed line was wrong.

Checked two ways: the reset clears the flag directly, and across full Frames games
every "kicks off" line follows a play that scored.

Run: .venv/bin/python test_frames_stale_kickoff.py
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

# Same circular-import dance the other sim tests use.
if 'floosball_game' not in sys.modules:
    _stub = types.ModuleType('floosball_game')
    _stub.Game = type('G', (), {})
    sys.modules['floosball_game'] = _stub
    import managers.timingManager  # noqa: F401
    del sys.modules['floosball_game']

import floosball_game as FG  # noqa: E402
from managers.timingManager import TimingManager, TimingMode  # noqa: E402
from game_rules import GameRules  # noqa: E402
from scenario import _makeTeam  # noqa: E402

GAMES = 40


def _framesGame(index):
    rr = random.Random(7000 + index)
    home = _makeTeam('H', 'HOM', 1000 + index * 10,
                     phys=rr.randint(74, 92), ment=rr.randint(74, 92))
    away = _makeTeam('A', 'AWY', 5000 + index * 10,
                     phys=rr.randint(74, 92), ment=rr.randint(74, 92))
    rules = GameRules()
    rules.gameFormat = 'frames'
    game = FG.Game(home, away, gameRules=rules,
                   timingManager=TimingManager(TimingMode.FAST))
    game.id = index
    return game


def _scored(play):
    """True if this play put points on the board (TD, FG, safety or a try)."""
    if getattr(play, 'scoreChange', False):
        return True
    name = getattr(getattr(play, 'playType', None), 'name', '')
    return name in ('ExtraPoint', 'TwoPointConversion', 'Conversion')


def _staleKickoffs(game):
    """Kickoff lines whose preceding play did not score, in game order."""
    bad = []
    lastPlay = None
    for entry in reversed(game.gameFeed):   # the feed is newest-first
        if not isinstance(entry, dict):
            continue
        if 'play' in entry:
            lastPlay = entry['play']
        elif 'event' in entry:
            text = entry['event'].get('text', '')
            if text.endswith(' kicks off') and lastPlay is not None and not _scored(lastPlay):
                bad.append((text, getattr(lastPlay, 'playText', '')))
    return bad


class FramesStaleKickoffTests(unittest.TestCase):

    def testTheFrameResetClearsAQueuedKickoff(self):
        game = _framesGame(0)
        game._coinFlipWinner, game._coinFlipLoser = game.homeTeam, game.awayTeam
        game.offensiveTeam, game.defensiveTeam = game.homeTeam, game.awayTeam
        game.currentQuarter = 1
        game._frameIndex = 1
        game._frameBoundaryPending = True
        game._pendingPossessionChange = True
        game._pendingKickoff = True
        self.assertTrue(game._frameBoundaryReset())
        self.assertFalse(game._pendingPossessionChange)
        self.assertFalse(game._pendingKickoff)

    def testEveryKickoffLineFollowsAScore(self):
        stale = []
        for index in range(GAMES):
            game = _framesGame(index)
            asyncio.run(asyncio.wait_for(game.playGame(), timeout=120))
            stale.extend((index, *s) for s in _staleKickoffs(game))
        self.assertEqual(stale, [], f'{len(stale)} kickoff line(s) after a non-scoring play: {stale[:3]}')


if __name__ == '__main__':
    unittest.main(verbosity=2)
