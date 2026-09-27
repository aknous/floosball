"""A muffed punt the kicking team recovers is a turnover, and every counter says so.

⚠️ THE MUFF BRANCH SET ONLY THE PLAY FLAGS. `play.isFumbleLost` made the feed badge and
the field graphic read it as a turnover, but none of the counters a lost fumble moves
elsewhere were touched: the recovering team's `gameDefenseStats['fumRec']` (which is
the box score's turnovers, `games.*_fum_rec`, `games.team_stats`, the team page's
turnover margin and season fumble recoveries), the `*TurnoversTotal` game totals, the
defense's takeaway fantasy points, and nothing on the returner's line. Reported as
fumbled punts not counting as turnovers in player stats or box scores.

On a punt the OFFENSE is the kicking team, so the sides are flipped relative to a
scrimmage fumble: the offense recovers, the defense gives it away.

Run: .venv/bin/python test_muff_turnover.py
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_play_feed_dedup import _playGame, _feedPlays  # noqa: E402


def _lostMuffs(game):
    return [p for p in _feedPlays(game)
            if getattr(p, 'isFumbleLost', False) and getattr(p, 'puntAction', None) == 'muff']


def _playWithProbe(index):
    """Forced-muff game that records every counter either side of each lost muff.

    `_applyMomentumEvent` runs just before the counters move and `formatPlayText` just
    after, so the delta between the two is exactly what the muff itself added. A total
    over the whole game would pass vacuously on the old code, since ordinary fumbles and
    interceptions already fill those counters.
    """
    import asyncio, random
    import floosball_game as FG
    from managers.timingManager import TimingManager, TimingMode
    from game_rules import GameRules
    from scenario import _makeTeam
    rr = random.Random(1000 + index)
    home = _makeTeam('H', 'HOM', 1000 + index * 10, phys=rr.randint(74, 92), ment=rr.randint(74, 92))
    away = _makeTeam('A', 'AWY', 5000 + index * 10, phys=rr.randint(74, 92), ment=rr.randint(74, 92))
    game = FG.Game(home, away, gameRules=GameRules(), timingManager=TimingManager(TimingMode.FAST))
    game.id = index

    def _muff(landing, puntType, receivingTeam, _g=game):
        return {'action': 'muff', 'returner': _g._pickReturner(receivingTeam),
                'returnYards': 0, 'muffRecoveredBy': 'kicking'}
    game._resolvePuntReturn = _muff

    deltas, pending = [], {}

    def _counters(g):
        return (g.offensiveTeam.gameDefenseStats['fumRec'],
                g.offensiveTeam.gameDefenseStats['fantasyPoints'],
                g.homeTurnoversTotal if g.defensiveTeam is g.homeTeam else g.awayTurnoversTotal)

    origMomentum, origFormat = game._applyMomentumEvent, game.formatPlayText

    def momentum(*a, **kw):
        if game.play is not None and getattr(game.play, 'isFumbleLost', False) \
                and getattr(game.play, 'puntAction', None) == 'muff':
            pending['before'] = _counters(game)
        return origMomentum(*a, **kw)

    def fmt(*a, **kw):
        if 'before' in pending:
            after = _counters(game)
            deltas.append(tuple(x - y for x, y in zip(after, pending.pop('before'))))
        return origFormat(*a, **kw)

    game._applyMomentumEvent, game.formatPlayText = momentum, fmt
    asyncio.run(asyncio.wait_for(game.playGame(), timeout=120))
    return game, deltas


class MuffTurnoverTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.game, cls.deltas = _playWithProbe(7)

    def test_lost_muffs_happened(self):
        self.assertGreater(len(self.deltas), 0, 'forced muffs never occurred')

    def test_each_lost_muff_moves_every_counter_once(self):
        # (recovering team's fumRec, its takeaway fantasy points, giver's turnover total)
        for d in self.deltas:
            self.assertEqual(d, (1, 2, 1))

    def test_returner_line_carries_the_lost_muff(self):
        g = self.game
        counted = 0
        for team in (g.homeTeam, g.awayTeam):
            for pl in team.rosterDict.values():
                if pl is None:
                    continue
                ret = (pl.gameStatsDict or {}).get('returning') or {}
                self.assertLessEqual(ret.get('muffsLost', 0), ret.get('muffs', 0))
                counted += ret.get('muffsLost', 0)
        self.assertEqual(counted, len(_lostMuffs(g)))


class RecoveredMuffIsNotATurnoverTest(unittest.TestCase):
    def test_own_recovery_counts_nothing(self):
        import test_play_feed_dedup as T
        import floosball_game as FG

        # Same forced-muff harness, but the RECEIVING team falls on it.
        import random, asyncio
        from managers.timingManager import TimingManager, TimingMode
        from game_rules import GameRules
        from scenario import _makeTeam
        rr = random.Random(1007)
        home = _makeTeam('H', 'HOM', 1070, phys=rr.randint(74, 92), ment=rr.randint(74, 92))
        away = _makeTeam('A', 'AWY', 5070, phys=rr.randint(74, 92), ment=rr.randint(74, 92))
        game = FG.Game(home, away, gameRules=GameRules(),
                       timingManager=TimingManager(TimingMode.FAST))
        game.id = 7

        def _muff(landing, puntType, receivingTeam, _g=game):
            return {'action': 'muff', 'returner': _g._pickReturner(receivingTeam),
                    'returnYards': 0, 'muffRecoveredBy': 'receiving'}
        game._resolvePuntReturn = _muff
        asyncio.run(asyncio.wait_for(game.playGame(), timeout=120))
        for team in (game.homeTeam, game.awayTeam):
            for pl in team.rosterDict.values():
                if pl is not None:
                    ret = (pl.gameStatsDict or {}).get('returning') or {}
                    self.assertEqual(ret.get('muffsLost', 0), 0)
        self.assertEqual(len(_lostMuffs(game)), 0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
