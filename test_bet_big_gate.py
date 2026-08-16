"""Bet Big's power bar and its payout line are the same number.

⚠️ THE BAR SAID UNLOCKED AND THE CARD PAID NOTHING. Every card carries a generic
per-position FP gate, which is the right shape when the gate only asks "did this player
show up". Bet Big's entire effect IS an FP threshold, so a generic gate put TWO different
lines on one card:

    position   power bar   payout starts at   gap
    QB            13             22           bar filled 9 FP early
    RB            11             22           11
    WR            12             20            8
    TE             6             14            8
    K              8             15            7

A user watched the bar fill, read the card as unlocked, and got nothing for another 7 to
11 points. Reported exactly that way.

⚠️ THIS CHANGED NO PAYOUT. Below the stud line `_computeAllIn` returns 0 regardless of the
gate, so the old bar was never buying anything — it was only lying about when the card
starts working. Verified across the FP range in `PayoutsAreUnchanged` below. That is worth
pinning: a future edit that "fixes" this by moving the stud line instead would be a
balance change wearing a bug fix's clothes.

⚠️ ALL-PRO MOVES BOTH OR NEITHER. The classification lowers a card's gate, because an
individual accolade buys individual reliability. Applying that to the bar alone would
re-open the very gap being closed. Lowering both keeps them equal and keeps the accolade
worth holding on this card — an All-Pro Bet Big starts paying sooner, which is the point
of the accolade. That IS a real (intended) buff, and it is the only payout this change
moves.

Run: .venv/bin/python test_bet_big_gate.py
"""

import logging
import os
import sys
import unittest
from types import SimpleNamespace as NS

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
logging.disable(logging.CRITICAL)

from managers.cardEffects import allInStudLine, buildEffectConfig  # noqa: E402
from managers.cardEffectCalculator import (  # noqa: E402
    CardCalcContext, calculateWeekCardBonuses,
)

POSITIONS = (1, 2, 3, 4, 5)


def config(position, classification=None):
    return buildEffectConfig('prismatic', 85, position, 10,
                             forceEffect='all_in', classification=classification)


def payout(fp, position=1, gateOverride=None, classification=None):
    cfg = config(position, classification)
    if gateOverride is not None:
        cfg['gate']['threshold'] = gateOverride
    tmpl = NS(player_id=1, edition='prismatic', position=position, player_name='P',
              player_rating=85, effect_config=cfg, classification=classification, team_id=10)
    eq = NS(id=1, slot_number=1, user_card=NS(card_template=tmpl, tier=1))
    ctx = CardCalcContext()
    ctx.gamesActive = False
    ctx.isProjection = False
    ctx.rosterPlayerIds = {1}
    ctx.rosterPlayerPositions = {1: position}
    ctx.rosterPlayerTeamIds = {1: 10}
    ctx.rosterPlayerRatings = {1: 85}
    ctx.weekPlayerStats = {1: {'fantasyPoints': fp,
                               'passing_stats': {'comp': 20, 'yards': fp * 10, 'tds': 2}}}
    ctx.weekRawFP = fp
    ctx.teamResults = {10: True}
    row = next(b for b in calculateWeekCardBonuses([eq], ctx).cardBreakdowns
               if b.effectName == 'all_in')
    return row.primaryMult


class OneNumberOnTheCard(unittest.TestCase):
    def testTheBarMatchesThePayoutLineAtEveryPosition(self):
        """⚠️ The reported bug."""
        for position in POSITIONS:
            cfg = config(position)
            self.assertEqual(
                cfg['gate']['threshold'], cfg['primary']['studLine'],
                f'position {position}: the bar fills at '
                f"{cfg['gate']['threshold']} FP but the payout starts at "
                f"{cfg['primary']['studLine']}")

    def testTheGateTextQuotesTheSameNumberAsTheDetail(self):
        """Both strings are on the card face at once, so disagreeing is visible."""
        for position in POSITIONS:
            cfg = config(position)
            line = str(cfg['primary']['studLine'])
            self.assertIn(line, cfg['gateText'])
            self.assertIn(line, cfg['detail'])

    def testAllProLowersBothTogether(self):
        for position in POSITIONS:
            plain, allPro = config(position), config(position, 'all_pro')
            self.assertEqual(allPro['gate']['threshold'], allPro['primary']['studLine'],
                             f'position {position}: All-Pro re-opened the gap')
            self.assertLess(allPro['primary']['studLine'], plain['primary']['studLine'],
                            f'position {position}: All-Pro bought nothing on this card')

    def testTheHelperIsWhatBothSidesRead(self):
        for position in POSITIONS:
            for classification in (None, 'all_pro', 'mvp_all_pro'):
                expected = allInStudLine(position, classification)
                cfg = config(position, classification)
                self.assertEqual(cfg['primary']['studLine'], expected)
                self.assertEqual(cfg['gate']['threshold'], expected)


class PayoutsAreUnchanged(unittest.TestCase):
    """⚠️ Pinning that this was a truth fix, not a balance one. A later edit that closed
    the same gap by moving the STUD LINE down instead would silently make the card pay
    from a lower bar."""

    OLD_GATE = {1: 13, 2: 11, 3: 12, 4: 6, 5: 8}

    def testEveryFpLevelPaysWhatItUsedTo(self):
        for position in POSITIONS:
            for fp in (0, 5, 10, 13, 16, 20, 22, 26, 32, 45):
                with self.subTest(position=position, fp=fp):
                    self.assertEqual(
                        payout(fp, position, gateOverride=self.OLD_GATE[position]),
                        payout(fp, position),
                        f'position {position} at {fp} FP now pays differently')

    def testNothingPaysBelowTheStudLine(self):
        for position in POSITIONS:
            line = config(position)['primary']['studLine']
            self.assertEqual(payout(line - 1, position), 0.0)
            self.assertEqual(payout(line, position), 0.0)

    def testItStillPaysAboveTheLine(self):
        for position in POSITIONS:
            line = config(position)['primary']['studLine']
            self.assertGreater(payout(line + 10, position), 1.0)


class NoOtherCardHasTwoLines(unittest.TestCase):
    def testOnlyBetBigOverridesItsOwnGate(self):
        """If another effect grows a self-referential FP threshold it needs the same
        treatment, and this is where that gets noticed."""
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               'managers', 'cardEffects.py')) as fh:
            src = fh.read()
        block = src[src.index('def buildGateSpec'):]
        block = block[:block.index('\ndef ', 10)]
        overrides = [line for line in block.split('\n')
                     if 'effectName ==' in line and 'return None' not in line]
        self.assertEqual(len(overrides), 1,
                         f'gate overrides changed: {overrides}')
        self.assertIn('all_in', overrides[0])


if __name__ == '__main__':
    unittest.main(verbosity=2)
