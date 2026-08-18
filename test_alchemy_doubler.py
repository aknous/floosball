"""Doubler doubles the touchdowns Alchemy makes.

⚠️ REPORTED BY A USER: Doubler did not work on Alchemy. Owner ruling — it should.

Both cards write to the same pool, `ctx.rosterTotalTds`, in a pre-pass before any card
computes. Alchemy adds the roster kicker's made field goals to it ("your kicker's field
goals count as touchdowns"); Doubler multiplies it ("your roster's touchdowns count twice").
A reader applying both sentences expects the converted scores to double. They did not —
purely because Doubler's block sat ABOVE Alchemy's in the pre-pass, so it multiplied the
pool one block before Alchemy added to it:

    (2 real x 2) + 3 converted =  7      what it did
    (2 real + 3 converted) x 2 = 10      what the two cards say

⚠️ NOTHING ABOUT THE MATH WAS WRONG — each card computed exactly what it claims, in the
wrong order. That is why it read as "Doubler is broken on Alchemy" rather than as a bad
number: five of the six lineups below were already correct.

⚠️ SHARPSHOOTER STILL RUNS FIRST, and always did. It multiplies the kicker's `fgs` before
Alchemy converts them, so a made field goal counts twice and then becomes two touchdowns.
That asymmetry is what made the bug visible at all: one amplifier fed Alchemy and the other
did not, decided by nothing but line order. The order is therefore load-bearing and is
asserted directly below — Sharpshooter -> Alchemy -> Doubler.

Run: .venv/bin/python test_alchemy_doubler.py
"""
import logging
import unittest
from types import SimpleNamespace

logging.disable(logging.CRITICAL)

from managers.cardEffects import buildEffectConfig
from managers.cardEffectCalculator import CardCalcContext, calculateWeekCardBonuses

WR, K = 3, 5

REAL_TDS = 2      # touchdowns the roster actually scored
FGS_MADE = 3      # field goals the roster kicker actually made


def mkCard(eqId, pid, effect, *, edition='diamond', rating=92, pos=WR):
    cfg = buildEffectConfig(edition, rating, pos, forceEffect=effect)
    tmpl = SimpleNamespace(effect_config=cfg, player_id=pid, position=pos, team_id=None,
                           edition=edition, player_rating=rating, player_name=f"P{pid}",
                           classification=None, is_rookie=False)
    uc = SimpleNamespace(card_template=tmpl, tier=1, id=eqId * 100)
    return SimpleNamespace(id=eqId, user_card=uc, slot_number=eqId, slot=None,
                           peak_output=0.0, weeks_since_break=0)


def rosterTdsWith(*effects):
    """Field a lineup carrying `effects` and report the shared TD pool afterwards."""
    cards = [mkCard(i + 1, 3 if e == 'alchemy' else 1, e,
                    pos=K if e == 'alchemy' else WR)
             for i, e in enumerate(effects)]
    # A filler card so the lineup is never empty when no amplifier is equipped.
    cards.append(mkCard(9, 2, 'freebie', edition='base', rating=80))

    ctx = CardCalcContext()
    ctx.gamesActive = True
    ctx.rosterPlayerIds = {1, 2, 3}
    ctx.rosterPlayerPositions = {1: WR, 2: WR, 3: K}
    ctx.rosterPlayerNames = {p: f"P{p}" for p in (1, 2, 3)}
    ctx.rosterTotalTds = REAL_TDS
    ctx.weekPlayerStats = {
        1: {"fantasyPoints": 20},
        2: {"fantasyPoints": 20},
        3: {"fantasyPoints": 20, "kicking_stats": {"fgs": FGS_MADE, "fgYards": 120}},
    }
    calculateWeekCardBonuses(cards, ctx)
    return ctx.rosterTotalTds


class TheCardsCompound(unittest.TestCase):

    def test_theFixtureItselfIsSane(self):
        """Guard the baseline: with no amplifier the pool is untouched. If this drifts,
        every assertion below compares against a moved goalpost rather than failing."""
        self.assertEqual(rosterTdsWith(), REAL_TDS)

    def test_alchemyConvertsFieldGoals(self):
        self.assertEqual(rosterTdsWith('alchemy'), REAL_TDS + FGS_MADE)

    def test_doublerDoublesRealTouchdowns(self):
        self.assertEqual(rosterTdsWith('doubler'), REAL_TDS * 2)

    def test_doublerDoublesTheConvertedTouchdowns(self):
        """THE REGRESSION. Was 7 — (2 x 2) + 3 — because Doubler ran first."""
        self.assertEqual(rosterTdsWith('alchemy', 'doubler'),
                         (REAL_TDS + FGS_MADE) * 2)

    def test_sharpshooterStillFeedsAlchemy(self):
        """⚠️ Pre-existing and deliberate: the doubled field goals convert."""
        self.assertEqual(rosterTdsWith('alchemy', 'sharpshooter'),
                         REAL_TDS + FGS_MADE * 2)

    def test_allThreeChain(self):
        self.assertEqual(rosterTdsWith('alchemy', 'doubler', 'sharpshooter'),
                         (REAL_TDS + FGS_MADE * 2) * 2)

    def test_theOrderIsIndependentOfHowTheLineupIsArranged(self):
        """⚠️ The pre-pass is a fixed sequence of blocks, NOT a walk over the equipped
        cards, so slot order must not change the answer. If it ever does, the amplifiers
        have moved back into the per-card loop and this whole file is measuring luck."""
        self.assertEqual(rosterTdsWith('doubler', 'alchemy'),
                         rosterTdsWith('alchemy', 'doubler'))
        self.assertEqual(rosterTdsWith('doubler', 'sharpshooter', 'alchemy'),
                         rosterTdsWith('alchemy', 'doubler', 'sharpshooter'))


class TheOrderIsLoadBearing(unittest.TestCase):
    """The three blocks are ordinary top-level statements — nothing enforces their order at
    runtime, so a later edit can silently reintroduce this by moving one. Pin it."""

    def test_sharpshooterThenAlchemyThenDoubler(self):
        with open('managers/cardEffectCalculator.py') as fh:
            src = fh.read()
        sharp = src.index('if "sharpshooter" in equippedNames')
        alchemy = src.index('alchemyEquipped = any(')
        doubler = src.index('if "doubler" in equippedNames')
        self.assertLess(sharp, alchemy,
                        'Sharpshooter must double the field goals before Alchemy converts')
        self.assertLess(alchemy, doubler,
                        'Alchemy must convert before Doubler multiplies the TD pool')


if __name__ == '__main__':
    unittest.main(verbosity=2)
