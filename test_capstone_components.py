"""A capstone grants a Synthesis Component, and "capstone" means what it already pays.

⚠️ THE DEFINITION IS "ALREADY GRANTS A PACK OR A POWERUP", NOT AN `_iv` SUFFIX. The
`dedicated` ladder runs i..vi, so `dedicated_iv` is a MIDDLE rung and a `%_iv` match
sweeps it in. Reading the definition off the reward itself makes the grant list
self-maintaining: a new capstone gets a component by virtue of being one, and a new
mid-ladder rung cannot accidentally collect one.

⚠️ AND THE FAUCET WAS DEAD. `achievementManager._applyReward` has read
`cfg["components"]` since synthetic cards shipped, `componentManager.grant` enforces
`SYNTH_COMPONENT_ACHIEVEMENT_CAP`, and `test_synthetic_cards.py` proves the cap bites.
But no seed row ever set the key, so every capstone paid its pack and zero components.
The mechanism was complete and simply had nothing pointed at it, which is invisible
from either side on its own.

Run: .venv/bin/python test_capstone_components.py
"""

import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

CONN = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                    'database', 'connection.py')

ROW = re.compile(
    r'\{"key": "(?P<key>[^"]+)"'          # the achievement
    r'(?P<mid>.*?)'
    r'"reward_config": (?P<cfg>\{[^}]*\{[^}]*\}[^}]*\}|\{[^}]*\})',
    re.S)


def seedRows():
    """Every seeded achievement as (key, rewardConfigText), read from the source.

    Read STATICALLY rather than by booting the app: the point is what ships in the
    seed, and a DB read would only tell us what some database happens to hold.
    """
    src = open(CONN).read()
    start = src.index('def _seedAchievements()')
    block = src[start:src.index('\ndef ', start + 10)]
    return [(m.group('key'), m.group('cfg')) for m in ROW.finditer(block)]


def grantsPackOrPowerup(cfg: str) -> bool:
    packs = re.search(r'"packs": \[([^\]]*)\]', cfg)
    pups = re.search(r'"powerups": \[([^\]]*)\]', cfg)
    return bool((packs and packs.group(1).strip()) or (pups and pups.group(1).strip()))


def componentCount(cfg: str) -> int:
    m = re.search(r'"components": \{"synth": (\d+)\}', cfg)
    return int(m.group(1)) if m else 0


class CapstoneComponentTests(unittest.TestCase):

    def setUp(self):
        self.rows = seedRows()
        self.assertGreater(len(self.rows), 80,
                           "the seed parse found too few achievements to trust")

    def testEveryCapstoneGrantsAComponent(self):
        missing = [k for k, cfg in self.rows
                   if grantsPackOrPowerup(cfg) and componentCount(cfg) == 0]
        self.assertEqual([], missing,
                         f"capstones granting no Synthesis Component: {missing}")

    def testNothingElseGrantsOne(self):
        """A component is the capstone's marker, so a non-capstone holding one means
        the definition has drifted and the 4-per-season cap is being spent elsewhere."""
        stray = [k for k, cfg in self.rows
                 if componentCount(cfg) > 0 and not grantsPackOrPowerup(cfg)]
        self.assertEqual([], stray,
                         f"non-capstones granting a component: {stray}")

    def testOnePerCapstone(self):
        """⚠️ Sizing depends on this. Production measures ~2 capstones per participating
        user-season with a tail of 9, so 1 each is self-limiting against the cap of 4.
        Handing out 2 doubles the faucet without the cap moving."""
        overpaid = [(k, componentCount(cfg)) for k, cfg in self.rows
                    if componentCount(cfg) > 1]
        self.assertEqual([], overpaid, f"capstones paying more than one: {overpaid}")

    def testMidLadderRungsAreNotSweptIn(self):
        """`dedicated_iv` is a middle rung of an i..vi ladder. An `_iv` match would
        grant it a component; the pack-or-powerup definition must not."""
        byKey = dict(self.rows)
        self.assertIn('dedicated_iv', byKey, "the ladder this guards moved or was renamed")
        self.assertEqual(0, componentCount(byKey['dedicated_iv']),
                         "dedicated_iv is a middle rung and must not grant a component")
        self.assertGreater(componentCount(byKey['dedicated_vi']), 0,
                           "dedicated_vi is the real capstone and must grant one")

    def testTheGrantPathReadsTheKeyWeWrite(self):
        """The seed and the consumer have to agree on the shape. `_applyReward` reads
        `cfg["components"]` as {kind: count} and routes synth through componentManager."""
        mgr = open(os.path.join(os.path.dirname(CONN), '..', 'managers',
                                'achievementManager.py')).read()
        self.assertIn('cfg.get("components")', mgr,
                      "achievementManager no longer reads the components key")
        self.assertIn('SYNTH_COMPONENT_ACHIEVEMENT_CAP', mgr,
                      "the achievement grant path dropped its cap")


if __name__ == '__main__':
    unittest.main(verbosity=2)
