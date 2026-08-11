"""A target is a pass thrown at you, not a pass you caught.

⚠️ THE TARGET WAS BOOKED BY OUTCOME. `addRcvPassTarget` was called inside the completion
branch and the drop branch, and nowhere else — so an incompletion, a ball broken up by
the corner, and an interception on a ball aimed at a receiver all left his line
untouched. That is not what the stat means anywhere in football: a target is any pass
thrown toward an intended receiver, whatever happens to it. Only a spike or a throwaway
has no target.

The signature was exact, which is what makes it testable: for EVERY player in a real
league, `targets == receptions + drops`. Reported as receivers finishing a day of games
with a 100% reception rate; measured league-wide at 94.3% against a real-world ~65%, and
over a 20-game batch at 96.5% before the fix and 72.7% after.

⚠️ It also moved a card. Attention pays FPx per 5 targets and its rate is sized from
`_LADDER_VOLUMES['targets']`, measured under the old counting at 9.9 WR / 8.7 TE. The
true volumes are 12.3 / 11.0, so the table was reading ~24% light and the card would
have silently paid a quarter more than its rung. Effect values are frozen at mint, so
cards already minted keep the hot rate until the next season's templates.

Run: .venv/bin/python test_receiver_targets.py
"""

import os
import re
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
from managers.timingManager import TimingManager, TimingMode  # noqa: E402
from game_rules import GameRules  # noqa: E402
from scenario import _makeTeam  # noqa: E402

GAMES = 8
# A league of real receivers catches roughly two thirds of what is thrown at them. These
# are wide enough to be about the RULE rather than about this week's tuning: the fault
# being pinned pushed the figure into the nineties.
CATCH_RATE_FLOOR = 0.55
CATCH_RATE_CEILING = 0.90


def _playLeague(games=GAMES):
    """Play a batch and total the receiving lines."""
    totals = {'receptions': 0, 'targets': 0, 'drops': 0, 'att': 0, 'comp': 0}
    for i in range(games):
        rr = random.Random(4000 + i)
        home = _makeTeam('H', 'HOM', 1000 + i * 10,
                         phys=rr.randint(74, 92), ment=rr.randint(74, 92))
        away = _makeTeam('A', 'AWY', 5000 + i * 10,
                         phys=rr.randint(74, 92), ment=rr.randint(74, 92))
        game = FG.Game(home, away, gameRules=GameRules(),
                       timingManager=TimingManager(TimingMode.FAST))
        game.id = i
        asyncio.run(asyncio.wait_for(game.playGame(), timeout=120))
        for team in (home, away):
            for player in team.rosterDict.values():
                if player is None:
                    continue
                stats = player.gameStatsDict or {}
                rcv = stats.get('receiving', {})
                totals['receptions'] += rcv.get('receptions', 0)
                totals['targets'] += rcv.get('targets', 0)
                totals['drops'] += rcv.get('drops', 0)
                pas = stats.get('passing', {})
                totals['att'] += pas.get('att', 0)
                totals['comp'] += pas.get('comp', 0)
    return totals


class ReceiverTargetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.totals = _playLeague()

    def testTargetsExceedReceptionsPlusDrops(self):
        """THE REGRESSION, stated as its own signature. Equality here means the
        incompletions and interceptions went missing again."""
        t = self.totals
        self.assertGreater(
            t['targets'], t['receptions'] + t['drops'],
            f"targets ({t['targets']}) == receptions + drops "
            f"({t['receptions'] + t['drops']}): a pass broken up or picked off is "
            f"still a target")

    def testCatchRateIsBelievable(self):
        t = self.totals
        rate = t['receptions'] / t['targets']
        self.assertGreater(rate, CATCH_RATE_FLOOR, f'catch rate {rate:.1%}')
        self.assertLess(rate, CATCH_RATE_CEILING,
                        f'catch rate {rate:.1%} — receivers do not catch nearly '
                        f'everything thrown at them')

    def testEveryAttemptAtAReceiverIsATarget(self):
        """Nearly every pass in this sim has an intended receiver, so targets should
        track attempts closely. A large gap means a path stopped counting."""
        t = self.totals
        self.assertGreater(t['targets'], t['att'] * 0.85,
                           f"targets {t['targets']} against {t['att']} attempts")
        self.assertLessEqual(t['targets'], t['att'],
                             'more targets than passes thrown')

    def testTheTargetIsBookedOnceAtRelease(self):
        """Structural: one credit on the outcome path, not one per outcome. Two
        branches crediting it is how an outcome gets missed, and three is how one gets
        counted twice."""
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               'floosball_game.py')) as fh:
            source = fh.read()
        # The RB checkdown resolves on its own path and books its own target.
        calls = re.findall(r'^\s*(?:self\.receiver|rb)\.addRcvPassTarget\(', source, re.M)
        self.assertEqual(len(calls), 2,
                         f'expected the release-point credit plus the checkdown, '
                         f'found {len(calls)} call sites')

    def testAttentionsRateIsSizedOffTheRealVolume(self):
        """The card that pays per target must be sized against what a receiver
        actually sees, or the fix hands it a quiet raise."""
        from managers.cardEffects import _LADDER_VOLUMES
        volumes = _LADDER_VOLUMES['targets']
        self.assertGreater(volumes[3], 11.0, 'WR target volume still the pre-fix figure')
        self.assertGreater(volumes[4], 10.0, 'TE target volume still the pre-fix figure')


if __name__ == '__main__':
    unittest.main(verbosity=2)
