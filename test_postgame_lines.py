"""Postgame player lines: real win/loss voices, and they survive the game.

⚠️ TWO SEPARATE PROBLEMS, reported together as "those aren't coming through to the front
end anymore".

THE PLUMBING. The lines were built and inserted into the in-memory play feed, and
play-by-play is deliberately never persisted because it is large. That was survivable while
a finished game sat in memory for hours -- but the cross-day rollover now fires about
fifteen minutes after the final whistle, so the game object disappears almost immediately
and the Bleachers rail goes empty. Measured: games used to stay in memory ~9.2 hours after
the whistle and now stay ~0.2. The lines are a handful of rows per game rather than a whole
feed, so they get their own column and are handed back in the cutaway shape the live feed
used -- which is why no client change was needed to render them.

THE CONTENT. `composePolarityReaction` passed an EMPTY event key, which falls through to
`positive_generic` / `negative_generic` -- pools of reactions to a PLAY. So a player who had
just lost a game was described "jogging back to the huddle", and the beat read as more
in-game chatter. Every personality now has `won_game` and `lost_game`, and they are STRICT
(no generic fallback) precisely because the generic lines assume there is another snap
coming.

Run: .venv/bin/python test_postgame_lines.py
"""
import unittest

import yaml

from managers.personalityReactionEngine import (PersonalityReactionEngine,
                                                CONTEXT_STRICT_EVENT_KEYS)

VIBES = 'data/templates/vibe_reactions.yaml'


class EveryPersonalityHasBoth(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        with open(VIBES) as fh:
            cls.data = yaml.safe_load(fh)

    def test_nobodyIsMissingAPool(self):
        missing = [n for n, v in self.data.items()
                   if not v.get('won_game') or not v.get('lost_game')]
        self.assertEqual(missing, [], f'no postgame lines for: {missing}')

    def test_thePoolsAreBigEnoughToNotRepeat(self):
        """The engine draws from a shuffled deck, so a thin pool is a visible loop."""
        for name, v in self.data.items():
            self.assertGreaterEqual(len(v['won_game']), 6, f'{name} won_game is thin')
            self.assertGreaterEqual(len(v['lost_game']), 6, f'{name} lost_game is thin')

    def test_theyAreNotJustCopiesOfTheGenericPools(self):
        """⚠️ THE WHOLE POINT. If these were the play-reaction pools again, nothing would
        have changed except the key they are stored under."""
        for name, v in self.data.items():
            self.assertFalse(set(v['won_game']) & set(v['positive_generic']),
                             f'{name} recycles positive_generic as postgame')
            self.assertFalse(set(v['lost_game']) & set(v['negative_generic']),
                             f'{name} recycles negative_generic as postgame')

    def test_winAndLossAreDifferentFromEachOther(self):
        for name, v in self.data.items():
            shared = set(v['won_game']) & set(v['lost_game'])
            # A couple of personalities react identically either way ON PURPOSE -- ghost
            # leaves before the whistle whatever happened, stoic shakes every hand -- so a
            # small overlap is characterisation, not duplication.
            self.assertLess(len(shared), 4,
                            f'{name} says the same {len(shared)} things winning and losing')

    def test_thePlaceholdersAreOnesTheRendererKnows(self):
        """⚠️ An unknown token renders literally. Postgame has no play context, so only
        `{name}` is safe here -- `{receiver}`, `{tackler}` and friends have nothing to
        resolve against once the game is over."""
        import re
        for name, v in self.data.items():
            for key in ('won_game', 'lost_game'):
                for line in v[key]:
                    for token in re.findall(r'\{(\w+)\}', line):
                        self.assertEqual(token, 'name',
                                         f'{name}.{key} uses {{{token}}}, which has no '
                                         f'value after the final whistle')

    def test_noEmoji(self):
        for name, v in self.data.items():
            for key in ('won_game', 'lost_game'):
                for line in v[key]:
                    self.assertTrue(all(ord(c) < 0x2190 or c in '—’‘' for c in line),
                                    f'{name}.{key} contains a non-text character: {line!r}')


class ThePoolsAreUsedExclusively(unittest.TestCase):

    def setUp(self):
        self.engine = PersonalityReactionEngine()

    def test_postgameIsStrict(self):
        """⚠️ Strict for a different reason than the turnover pools: the generic lines are
        reactions to a SNAP ("jogs back to the huddle"), and the game is over."""
        self.assertIn('won_game', CONTEXT_STRICT_EVENT_KEYS)
        self.assertIn('lost_game', CONTEXT_STRICT_EVENT_KEYS)

    @staticmethod
    def _rendered(line):
        """What a raw pool line looks like once rendered.

        ⚠️ A line WITHOUT `{name}` is quote-style and the renderer prefixes the speaker
        ("Someone: Good. Next week."), while a line WITH it is a stage direction and is
        substituted in place. Comparing against the raw pool without accounting for that
        makes this test fail on correct behaviour, which is exactly what it did first."""
        return (line.replace('{name}', 'Someone') if '{name}' in line
                else f'Someone: {line}')

    def _assertDrawnFrom(self, key, polarity):
        with open(VIBES) as fh:
            data = yaml.safe_load(fh)
        for personality in ('stoic', 'fiery', 'poetic', 'ghost'):
            seen = {self.engine.pickPersonalityLine(personality, key, polarity,
                                                    {'name': 'Someone'})
                    for _ in range(40)}
            pool = {self._rendered(l) for l in data[personality][key]}
            outside = seen - pool
            self.assertFalse(outside,
                             f'{personality} drew a {key} line from outside the pool: '
                             f'{sorted(outside)[:2]}')

    def test_aWinLineComesFromTheWinPool(self):
        self._assertDrawnFrom('won_game', 'positive')

    def test_aLossLineComesFromTheLossPool(self):
        self._assertDrawnFrom('lost_game', 'negative')

    def test_theComposerAsksForThePostgamePool(self):
        """It used to pass an empty event key, which is what routed it to the play pools."""
        with open('managers/personalityManager.py') as fh:
            body = fh.read().split('def composePolarityReaction')[1].split('\n    def ')[0]
        self.assertIn("eventKey = 'won_game' if polarity == 'positive' else 'lost_game'", body)
        self.assertIn('composeReaction(personality, quirk, eventKey, polarity', body)


class TheyOutliveTheGame(unittest.TestCase):
    """⚠️ The engine building them is not the same as anyone reading them — the whole
    reported symptom was lines that existed and reached nobody."""

    def test_theEngineKeepsThemOffTheFeedAsWell(self):
        with open('floosball_game.py') as fh:
            body = fh.read().split('def _buildPostgameReactions')[1].split('\n    def ')[0]
        self.assertIn('self.postgameQuotes.append(eventDict)', body)
        self.assertIn('self.postgameQuotes = []', body)

    def test_theTeamIsStampedFromTheGameNotThePlayer(self):
        """⚠️ `player.team` is a NAME (or an id), never a Team object, so the manager's
        `getattr(team, 'id')` yields None and the rail loses the crest. This loop has the
        real Team objects."""
        with open('floosball_game.py') as fh:
            body = fh.read().split('def _buildPostgameReactions')[1].split('\n    def ')[0]
        self.assertIn("eventDict['teamId'] = getattr(team, 'id', None)", body)
        self.assertIn("eventDict['teamAbbr'] = getattr(team, 'abbr', None)", body)

    def test_theyArePersistedAtBothSavePaths(self):
        with open('managers/seasonManager.py') as fh:
            src = fh.read()
        self.assertEqual(src.count('self._applyPostgameQuotesToRow(db_game, game)'), 2)

    def test_aFinishedGameServesThemBackAsCutaways(self):
        """Handed back in the shape the live feed used, so the Bleachers renders them with
        no client change — it reads cutaways out of `plays` and cannot tell the difference."""
        import json
        from game_box_score import _postgamePlays

        class Row:
            postgame_quotes = json.dumps([
                {'text': 'It counted.', 'playerName': 'A', 'teamAbbr': 'HOM', 'won': True},
                {'text': 'Rough one.', 'playerName': 'B', 'teamAbbr': 'AWY', 'won': False},
            ])
        plays = _postgamePlays(Row())
        self.assertEqual(len(plays), 2)
        self.assertTrue(all(p['isSidelineCutaway'] for p in plays))
        self.assertEqual(plays[0]['sidelineCutaway']['text'], 'It counted.')

    def test_aGameWithoutThemIsUnaffected(self):
        """Games that finished before the column existed have nothing to recover — these
        only ever lived in memory — so the archive path must degrade quietly."""
        from game_box_score import _postgamePlays

        class Empty:
            postgame_quotes = None

        class Junk:
            postgame_quotes = 'not json'
        self.assertEqual(_postgamePlays(Empty()), [])
        self.assertEqual(_postgamePlays(Junk()), [])

    def test_theMigrationExists(self):
        with open('database/connection.py') as fh:
            src = fh.read()
        self.assertIn('ALTER TABLE games ADD COLUMN postgame_quotes TEXT', src)


if __name__ == '__main__':
    unittest.main(verbosity=2)
