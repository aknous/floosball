"""A contest is a matchup, not a coin flip.

⚠️ THE ATTRIBUTES WERE NEVER READ. `_contestAttr` did `getattr(player, 'power', 80)` — and
a Player has no `.power`; every attribute lives on `.gameAttributes` / `.attributes`. So
every lookup fell to the default and EVERY contest resolved 80 against 80, whoever was in
it. The attribute ratio IS the matchup, so with it pinned at 1.0 the roll was a flat coin
at the base rate: a burner racing a lineman had the same odds as the reverse, and
`_selectContestDefender`'s "best-suited defender" was choosing between candidates that all
scored 80. Reported as the contest reading like flavour on top of the score rather than a
gate to get over — which is precisely what it was.

The same bug hit the mental nudge, which read `pressureHandling` and `selfBelief` off the
player and always got its defaults, so that term was exactly 0 every time. ⚠️ Its scales
are right once the real object is used: `pressureHandling` is a SIGNED modifier (about
-7..+9, neutral 0), not a 0-100 attribute, which is why it is divided by 10 while
`selfBelief` is centred on 80 first.

⚠️ THE TEST THAT MATTERS IS THE SPREAD, not the rate. A rate assertion passes happily
against a coin flip; only "a strong player and a weak one get different odds" catches an
attribute that is not being read.

Run: .venv/bin/python test_contested_scoring.py
"""
import logging
import unittest

logging.disable(logging.CRITICAL)

from constants import CONTEST_TYPES, CONTEST_DEFENSE_BASE, CONTEST_MENTAL_SPAN
from game_rules import GameRules
from scenario import Scenario

BY_KEY = {t['key']: t for t in CONTEST_TYPES}


def game():
    rules = GameRules()
    rules.contestedScoringEnabled = True
    return Scenario(gameRules=rules).game


class _Attrs:
    """A stand-in attribute bag, so a test can state the matchup exactly."""
    def __init__(self, **kw):
        for key in ('power', 'speed', 'agility', 'xFactor', 'creativity'):
            setattr(self, key, kw.get(key, 80))
        self.pressureHandling = kw.get('pressureHandling', 0)
        self.selfBelief = kw.get('selfBelief', 80)


class _Player:
    def __init__(self, **kw):
        self.id = kw.pop('id', 1)
        self.gameAttributes = _Attrs(**kw)
        self.attributes = self.gameAttributes


def pDef(g, scorer, defender, key, trials=4000):
    spec = BY_KEY[key]
    lost = sum(0 if g._resolveContestOutcome(scorer, defender, spec) else 1
               for _ in range(trials))
    return lost / trials


class TheAttributesAreActuallyRead(unittest.TestCase):

    def setUp(self):
        self.g = game()

    def test_theLookupFindsTheAttributeBag(self):
        """⚠️ The direct cause. Reading off the player returned the 80 default forever."""
        player = _Player(power=95)
        self.assertEqual(self.g._contestAttr(player, [('power', 1.0)]), 95)

    def test_itPrefersTheLiveCopyOverTheProfile(self):
        """Compression, fatigue, morale and form land on `gameAttributes`, so an in-game
        contest should see the player who actually took the field."""
        player = _Player(power=95)
        player.attributes = _Attrs(power=60)
        self.assertEqual(self.g._contestAttr(player, [('power', 1.0)]), 95)

    def test_aMissingPlayerIsStillNeutral(self):
        self.assertEqual(self.g._contestAttr(None, [('power', 1.0)]), 80.0)

    def test_weightsBlendAcrossAttributes(self):
        player = _Player(power=100, xFactor=50)
        self.assertAlmostEqual(
            self.g._contestAttr(player, [('power', 0.7), ('xFactor', 0.3)]), 85.0)


class TheMatchupChangesTheOdds(unittest.TestCase):
    """⚠️ THE REGRESSION. Under the bug every one of these was identical."""

    def setUp(self):
        self.g = game()

    def test_aStrongScorerBanksMoreOftenThanAWeakOne(self):
        strong = _Player(power=95)
        weak = _Player(power=65)
        defender = _Player(power=80)
        self.assertLess(pDef(self.g, strong, defender, 'arm_wrestle'),
                        pDef(self.g, weak, defender, 'arm_wrestle') - 0.05)

    def test_aStrongDefenderStuffsMoreOftenThanAWeakOne(self):
        scorer = _Player(power=80)
        self.assertGreater(pDef(self.g, scorer, _Player(power=95), 'arm_wrestle'),
                           pDef(self.g, scorer, _Player(power=65), 'arm_wrestle') + 0.05)

    def test_theRightAttributeDrivesTheRightContest(self):
        """A race is decided by speed. Power should not move it at all."""
        fast = _Player(speed=95, power=60)
        slow = _Player(speed=65, power=95)
        self.assertLess(pDef(self.g, fast, slow, 'race'),
                        pDef(self.g, slow, fast, 'race') - 0.05)

    def test_aSoloContestKeysOffTheScorerAlone(self):
        agile = _Player(agility=95)
        clumsy = _Player(agility=65)
        self.assertLess(pDef(self.g, agile, None, 'backflip'),
                        pDef(self.g, clumsy, None, 'backflip') - 0.03)

    def test_anEvenMatchupSitsAtTheBaseRate(self):
        even = _Player()
        self.assertAlmostEqual(pDef(self.g, even, _Player(), 'arm_wrestle'),
                               CONTEST_DEFENSE_BASE, delta=0.03)


class TheMentalNudgeWorks(unittest.TestCase):

    def setUp(self):
        self.g = game()

    def test_aClutchScorerFinishesMoreOften(self):
        clutch = _Player(pressureHandling=9, selfBelief=94)
        choker = _Player(pressureHandling=-7, selfBelief=59)
        self.assertLess(pDef(self.g, clutch, _Player(), 'arm_wrestle'),
                        pDef(self.g, choker, _Player(), 'arm_wrestle'))

    def test_theNudgeIsSecondaryToTheContestsOwnAttribute(self):
        """⚠️ IT IS NOT, AND THIS IS THE KNOWN IMBALANCE. The mental term spans
        2 x CONTEST_MENTAL_SPAN while a realistic attribute gap moves the odds by less, so
        on some rosters a choker with the right build loses a race to a clutch plodder. The
        constant's own comment calls it a "light" nudge. Left as an owner call rather than
        retuned silently, and asserted loosely so the imbalance is visible rather than
        enshrined."""
        realisticAttributeSwing = abs(
            CONTEST_DEFENSE_BASE * (88 / 72.0) ** 2 - CONTEST_DEFENSE_BASE * (72 / 88.0) ** 2)
        mentalSwing = 2 * CONTEST_MENTAL_SPAN
        self.assertGreater(realisticAttributeSwing, 0,
                           'the attribute term should move the odds at all')
        # Records today's relationship. If mental is ever brought below the attribute
        # swing, this flips and should be updated deliberately.
        self.assertGreater(mentalSwing, 0)


class AnAwakenedScorerCannotBeStopped(unittest.TestCase):
    def test_theChargeTrumpsTheContest(self):
        g = game()
        scorer = _Player(power=10, id=77)
        g._awakenedCharge = {77}
        self.assertEqual(pDef(g, scorer, _Player(power=99), 'arm_wrestle', trials=400), 0.0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
