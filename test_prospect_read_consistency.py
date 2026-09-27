"""Fans see a prospect's TRUE expected and ceiling, on every surface.

Reported from prod: prospect Dialup McAvoy read expected 81 / ceiling 88 on his team page
and 72 / 74 on his profile. The team page served the drafting team's scouted band (drawn
at its widest in the offseason), the draft class the viewer's team's band, and the
profile chart the truth.

Owner ruling (2026-09-27): fans always see the true values. Only the teams guess, through
their own scouting, and those guesses are never presented. Blurred bands made sense while
fans voted on prospects as the GM; the front office is autonomous now.

Run: .venv/bin/python test_prospect_read_consistency.py
"""

import os
import re
import sys
import types
import logging
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
logging.disable(logging.CRITICAL)

import api.main as M  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))


def _prospect(drafted=True):
    return types.SimpleNamespace(
        id=276, is_prospect=drafted, is_upcoming_rookie=not drafted,
        drafting_team_id=3 if drafted else None, playerRating=70.0,
        computeCeilingRating=lambda: 74.0, computeExpectedRating=lambda: 72.0)


class ProspectProjectionTest(unittest.TestCase):
    def test_projection_is_the_truth_drafted_or_not(self):
        for drafted in (True, False):
            self.assertEqual(M._prospectProjection(_prospect(drafted)),
                             {'expected': 72.0, 'ceiling': 74.0})

    def test_no_fan_facing_endpoint_serves_a_scouted_read(self):
        # The API layer must never reach the per-team scouting model or ship a band.
        src = open(os.path.join(HERE, 'api', 'main.py')).read()
        self.assertIsNone(re.search(r'prospect_scouting|scoutedView|believedPotential', src))
        self.assertNotIn('ceilingRange', src)

    def test_every_prospect_surface_uses_the_one_projection(self):
        src = open(os.path.join(HERE, 'api', 'main.py')).read()
        # team pipeline + draft class
        self.assertGreaterEqual(src.count('"projection": _prospectProjection(p)'), 2)
        # profile
        self.assertIn("projection = _prospectProjection(player)", src)


if __name__ == '__main__':
    unittest.main(verbosity=2)
