"""A player develops the same whether he is in the pipeline or on a roster.

Owner, 2026-09-27: "they should just develop the same regardless of roster status".
The arc read `seasonsPlayed` alone, which does not advance while a player is a prospect,
so pipeline seasons were free RISING seasons and promotion started the clock; the
boom/bust spread also ran for every pipeline season but only two rostered ones. The
development clock is now pro seasons + pipeline seasons (`careerSeasons`), and
`prospect_seasons` survives promotion so the sum does not reset.

Run: .venv/bin/python test_development_parity.py
"""

import os
import sys
import types
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from player_development import PlayerDevelopment  # noqa: E402


def _player(pid, seasonsPlayed, prospectSeasons, isProspect):
    return types.SimpleNamespace(
        id=pid, name='x', seasonsPlayed=seasonsPlayed, prospect_seasons=prospectSeasons,
        is_prospect=isProspect, attributes=types.SimpleNamespace(longevity=8))


class DevelopmentParityTest(unittest.TestCase):
    def test_same_arc_in_the_pipeline_and_on_a_roster(self):
        # Two seasons after the draft. One stayed in the pipeline the whole time; one was
        # promoted at the draft and has played two pro seasons; one was promoted after a
        # season in the pipeline. Same player (same id, so the same peak), same stage.
        stayed = _player(7, seasonsPlayed=0, prospectSeasons=2, isProspect=True)
        promotedAtDraft = _player(7, seasonsPlayed=2, prospectSeasons=0, isProspect=False)
        promotedLater = _player(7, seasonsPlayed=1, prospectSeasons=1, isProspect=False)
        ctxs = [PlayerDevelopment.careerContext(p, devBias=2)
                for p in (stayed, promotedAtDraft, promotedLater)]
        self.assertEqual(len({(c.phase, c.intensity, c.isProspect) for c in ctxs}), 1)

    def test_pipeline_seasons_age_a_player(self):
        # Past his peak on pipeline seasons alone: not a free rising season any more.
        p = _player(7, seasonsPlayed=0, prospectSeasons=6, isProspect=True)
        peak = PlayerDevelopment.peakSeason(p)
        self.assertLess(peak, 6)
        self.assertNotEqual(PlayerDevelopment.careerContext(p, 0).phase.name, 'RISING')

    def test_volatility_is_the_same_rule_for_both(self):
        inPipeline = _player(7, 0, 2, True)
        onRoster = _player(7, 2, 0, False)
        self.assertEqual(PlayerDevelopment.careerContext(inPipeline, 0).isProspect,
                         PlayerDevelopment.careerContext(onRoster, 0).isProspect)

    def test_promotion_keeps_the_pipeline_seasons(self):
        # Every promotion site must leave prospect_seasons alone, or the clock resets.
        here = os.path.dirname(os.path.abspath(__file__))
        for rel in ('managers/playerManager.py', 'managers/seasonManager.py',
                    'managers/tradeManager.py'):
            src = open(os.path.join(here, rel)).read()
            for line in src.splitlines():
                stripped = line.strip()
                if stripped.startswith('#'):
                    continue
                self.assertNotIn('.prospect_seasons = 0', stripped.replace('pick.prospect_seasons = 0', ''),
                                 f'{rel}: {stripped}')


if __name__ == '__main__':
    unittest.main(verbosity=2)
