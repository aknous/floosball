"""A play is listed in the feed once, however its drive ended.

⚠️ THE DRIVE-ENDING BRANCH HAS TO SIGNAL THAT IT ALREADY FED ITS PLAY, and the only
signal it had was `_pendingPossessionChange`. `lastPlayFormatted` is a LOCAL of the play
loop, so it dies with each drive and is re-derived at the top of the next outer
iteration from that flag — meaning "possession changed" was standing in for "the play is
already in the feed". Every drive-ending branch sets both together EXCEPT one: a punt
MUFFED AND RECOVERED BY THE KICKING TEAM formats, feeds and broadcasts its play and then
breaks with the SAME offense still on the field, so no possession change was pending and
the next iteration listed that play a SECOND time.

Reported on prod game 108, Q3 4:06 ("Leslie Waterguns punts 61 yards, Threebeans
Clarkson muffs it and Caddies recover", twice). It was the only duplicated play in that
game's 103, and the shape is rare enough — a muff is ~2% of punts and the kicking team
recovers a fraction of those — that it reads as a display glitch rather than as the feed
faithfully reporting what it holds.

The fix asks the feed itself (`_playAlreadyInFeed`), so a branch that ends a drive
without changing possession can't reintroduce this.

Run: .venv/bin/python test_play_feed_dedup.py
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


def _playGame(index, forceMuffRecovery=False):
    """Play one full game and hand back the finished Game.

    `forceMuffRecovery` turns EVERY punt into a muff the kicking team recovers, which is
    what makes this deterministic — waiting for the real roll needs ~10 games per
    occurrence, and a regression that only sometimes runs is not a regression test.
    """
    rr = random.Random(1000 + index)
    home = _makeTeam('H', 'HOM', 1000 + index * 10,
                     phys=rr.randint(74, 92), ment=rr.randint(74, 92))
    away = _makeTeam('A', 'AWY', 5000 + index * 10,
                     phys=rr.randint(74, 92), ment=rr.randint(74, 92))
    game = FG.Game(home, away, gameRules=GameRules(),
                   timingManager=TimingManager(TimingMode.FAST))
    game.id = index
    if forceMuffRecovery:
        def _muff(landing, puntType, receivingTeam, _g=game):
            return {'action': 'muff',
                    'returner': _g._pickReturner(receivingTeam),
                    'returnYards': 0,
                    'muffRecoveredBy': 'kicking'}
        game._resolvePuntReturn = _muff
    asyncio.run(asyncio.wait_for(game.playGame(), timeout=120))
    return game


def _feedPlays(game):
    return [entry['play'] for entry in game.gameFeed
            if isinstance(entry, dict) and 'play' in entry]


def _duplicates(game):
    """Plays listed more than once, by object identity — the loop reuses one Play
    per snap, so identity is the whole question."""
    counts = {}
    for play in _feedPlays(game):
        counts[id(play)] = counts.get(id(play), 0) + 1
    return [play for play in _feedPlays(game) if counts[id(play)] > 1]


class PlayFeedDedupTests(unittest.TestCase):
    def testAMuffRecoveredByTheKickingTeamIsListedOnce(self):
        """THE REGRESSION, with the branch forced so it runs every punt."""
        for index in range(3):
            game = _playGame(index, forceMuffRecovery=True)
            muffs = [p for p in _feedPlays(game)
                     if getattr(p, 'puntMuffRecoveredBy', None) == 'kicking']
            self.assertTrue(muffs, f'game {index} punted no muff — nothing was exercised')
            dupes = _duplicates(game)
            self.assertEqual(
                [], dupes,
                f'game {index} listed {len(dupes)} play(s) twice: '
                + ' | '.join(getattr(p, 'playText', '?') for p in dupes[:3]))

    def testTheMuffPlayIsStillListedAtAll(self):
        """The fix suppresses a re-insert, so the failure mode on the other side is a
        play that goes missing entirely."""
        game = _playGame(7, forceMuffRecovery=True)
        muffs = [p for p in _feedPlays(game)
                 if getattr(p, 'puntMuffRecoveredBy', None) == 'kicking']
        self.assertTrue(muffs)
        for play in muffs:
            self.assertTrue(getattr(play, 'playText', ''),
                            'a fed play must carry its narration')

    def testOrdinaryGamesListEveryPlayOnce(self):
        """The general invariant, over unforced games — no other drive-ending branch
        may start double-listing."""
        for index in range(6):
            game = _playGame(index)
            dupes = _duplicates(game)
            self.assertEqual(
                [], dupes,
                f'game {index} listed {len(dupes)} play(s) twice: '
                + ' | '.join(getattr(p, 'playText', '?') for p in dupes[:3]))

    def testTheHelperMatchesOnIdentityNotEquality(self):
        """Two snaps can be identical in every field (two 0-yard runs from the same
        spot). Only the same object is a duplicate."""
        game = FG.Game.__new__(FG.Game)
        first, second = object(), object()
        game.gameFeed = [{'play': first}, {'event': {'text': 'cutaway'}}]
        self.assertTrue(game._playAlreadyInFeed(first))
        self.assertFalse(game._playAlreadyInFeed(second))
        self.assertFalse(game._playAlreadyInFeed(None))


if __name__ == '__main__':
    unittest.main(verbosity=2)
