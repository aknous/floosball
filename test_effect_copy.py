"""Card text must not lie to a new user.

`test_effect_placeholders` proves every `{placeholder}` can be FILLED. That is a
different question from whether the filled sentence is TRUE, or parseable by someone
who has never read the source. This file covers the second.

⚠️ THE ONE THAT WAS ACTIVELY WRONG: Group Round (`bonus_round`) advertised "4 or more
of your other cards" while `_BONUS_ROUND_THRESHOLD` had been raised 4 -> 6 in the fusion.
A user who assembled exactly four triggering cards was told they had earned it and paid
nothing. A number the CODE owns was hardcoded into prose, so moving the constant left the
promise behind. Anything of that shape gets pinned here.

Also covered, all found in the same sweep and all user-visible:
  chain_reaction    detail said "every card in your hand" where the compute counts OTHERS,
                    and the tooltip named "your other 4 cards" — stale, the lineup is six
                    slots plus FLEX. Naming a hand size that moves is the bonus_round bug.
  updraft           interpolated a raw Python list onto the card face ("at each of
                    [299, 391, 483]") while its tooltip quoted 300/400/500 — the detail
                    and the tooltip disagreed about the card's own thresholds.
  lead_blocker      "the TE team's RB" (garbled possessive)
  spotlight_moment  "WR counts either WR scoring a TD." (sentence fragment)
  bonsai            "Every grow slows the next." (not English)
  barrage,
  promised_land     "escalating odds at 71.5 FP on each one" parses as odds AT a value
                    rather than a chance OF one
  rng               en-dash in user-facing copy

Run: .venv/bin/python test_effect_copy.py
"""

import logging
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
logging.disable(logging.CRITICAL)

import managers.cardEffects as CE  # noqa: E402
from managers.cardEffects import buildEffectConfig  # noqa: E402


def rendered():
    """Every mintable effect's text as a user actually sees it, numbers filled in."""
    out = {}
    for edition in ('metallic', 'holographic', 'prismatic', 'diamond'):
        pool = set()
        for pos in (1, 2, 3, 4, 5):
            pool |= set(CE.effectPoolFor(edition, pos))
        for eff in sorted(pool):
            pos = sorted(CE.effectValidPositions(eff) or {3})[0]
            cfg = buildEffectConfig(edition, 85, pos, 10, forceEffect=eff)
            out[eff] = (cfg.get('detail') or '', cfg.get('tooltip') or '')
    return out


RENDERED = rendered()


class ThresholdsMustBeReachable(unittest.TestCase):
    """⚠️ GROUP PROJECT COUNTS *OTHER* CARDS, NOT SEATS, AND AT 6 IT COULD NOT FIRE.

    `_computeBonusRound` reads first-pass breakdowns (which exclude this card, a
    second-pass effect) plus other second-pass cards — so the most it can ever count is
    `len(FUSION_BASE_SLOTS) - 1`, five at the standard lineup. The fusion raised the
    threshold to 6 on a note reading "with a 6-7 card lineup", counting SEATS where the
    compute counts OTHERS. Measured over 200 real-hand trials: hit rate 0%.

    Matching the text to the constant (below) would have kept a truthful description of
    an impossible card. This is the check that actually mattered.
    """

    def testBonusRoundCanFireAtTheStandardLineupSize(self):
        from managers.cardManager import FUSION_BASE_SLOTS
        others = len(FUSION_BASE_SLOTS) - 1
        self.assertLessEqual(
            CE._BONUS_ROUND_THRESHOLD, others,
            f'_BONUS_ROUND_THRESHOLD is {CE._BONUS_ROUND_THRESHOLD} but a standard '
            f'{len(FUSION_BASE_SLOTS)}-slot lineup only has {others} OTHER cards — '
            f'the card cannot fire without FLEX. Compare against the count of others, '
            f'never the seat count.')

    def testItDoesNotRequireEveryOtherCardToFire(self):
        """At exactly `others` it is reachable but demands a perfect hand, which is the
        same non-payoff in practice. Leave headroom."""
        from managers.cardManager import FUSION_BASE_SLOTS
        self.assertLess(CE._BONUS_ROUND_THRESHOLD, len(FUSION_BASE_SLOTS) - 1,
                        'threshold requires literally every other card to trigger')


class NoPreFusionRemnants(unittest.TestCase):
    """⚠️ CARD TEXT MUST DESCRIBE ONE PLAYER: THE ONE ON THE CARD.

    Before the fusion the fantasy roster was separate from the cards, so a WR card could
    reasonably speak about both WR slots. Spotlight Moment's detail still did —
    "a TD by either of your WRs counts" — describing behavior `_computeSpotlightMoment`
    never had: it has always read `_getCardPlayerStats(ctx, cardPlayerId)`.

    So the compute was right and only the prose was stale, which is the hardest kind of
    copy bug to notice: nothing misbehaves, the card just tells you it does something
    generous that it does not.

    Double Trouble is the deliberate exception and is NOT covered here. Reading both WR
    slots is its entire premise, and it is WR-exclusive already.
    """

    def testSpotlightMomentIsWrOnly(self):
        """Its sentence only means one thing if the card can only be a receiver."""
        self.assertEqual(CE.effectValidPositions('spotlight_moment'), {3})
        self.assertNotIn('spotlight_moment', CE.SHARED_EFFECT_POOL)

    def testSpotlightMomentTextDoesNotSpeakAboutOtherSlots(self):
        for text in RENDERED['spotlight_moment']:
            for phrase in ('either', 'both', 'your WRs', 'WR card'):
                self.assertNotIn(phrase, text,
                                 f'pre-fusion multi-slot phrasing is back: {text}')

    def testCardPlayerEffectsDoNotClaimToReadOtherSlots(self):
        """A card that speaks about "either of your" anything is describing the roster,
        not itself. Double Trouble is allowed; it is built that way on purpose."""
        allowed = {'double_trouble'}
        for eff, (detail, tooltip) in RENDERED.items():
            if eff in allowed:
                continue
            for text in (detail, tooltip):
                self.assertIsNone(
                    re.search(r'either of your', text, re.I),
                    f'{eff} claims to read another slot: {text}')


class StatLadderWording(unittest.TestCase):
    """⚠️ A BARE NUMBER IS NOT A RULE. The stat-ladder cards used to end on one:
    "plus a streak growing 0.03 FPx per week past 32". Thirty-two what? And "per week
    past N" reads as though the GROWTH is per-week, when N is a weekly BAR the card's own
    player has to clear for the streak to survive (STREAK_CONFIGS.resetCondition, checked
    at week end). Two wrong readings from one clause.

    Thirteen effects shared the phrasing, so it is pinned as a family rather than
    individually — a fourteenth added later inherits the check.
    """

    STREAK_FAMILY = ('clockwork', 'dead_eye', 'dominion', 'getaway', 'iron_man',
                     'landslide', 'odyssey', 'stratosphere', 'tenure', 'undertaker')
    TWO_TIER_FAMILY = ('beast_of_burden', 'custody', 'rhythm')

    def testNoBareThresholdSurvives(self):
        """'past 32' with nothing after it. The unit has to be named."""
        for eff in self.STREAK_FAMILY + self.TWO_TIER_FAMILY:
            detail = RENDERED[eff][0]
            self.assertIsNone(
                re.search(r'past \d+\s*$', detail),
                f'{eff} still ends on a unitless threshold: {detail}')
            self.assertNotIn('per week past', detail,
                             f'{eff} still reads as though the growth is per-week: {detail}')

    def testEveryStreakCardSaysWhatKeepsTheStreakAlive(self):
        for eff in self.STREAK_FAMILY:
            detail = RENDERED[eff][0]
            self.assertIn('Streak:', detail, f'{eff} does not label its streak clause')
            self.assertIn('straight week', detail,
                          f'{eff} does not say the weeks must be consecutive: {detail}')

    def testTheTwoTierCardsNameTheUnitOnTheirBonusTier(self):
        for eff in self.TWO_TIER_FAMILY:
            detail = RENDERED[eff][0]
            self.assertIn('in a week with', detail,
                          f'{eff} does not say when the extra applies: {detail}')

    def testNoSoccerJargon(self):
        """'clean sheet' was carrying the Dead Eye streak condition."""
        for eff, (detail, tooltip) in RENDERED.items():
            for text in (detail, tooltip):
                self.assertNotIn('clean sheet', text.lower(),
                                 f'{eff} uses a soccer term in a football game: {text}')


class ConstantsOwnTheirNumbers(unittest.TestCase):
    """⚠️ A number the CODE decides must not be retyped into prose."""

    def testBonusRoundQuotesTheRealThreshold(self):
        want = CE._BONUS_ROUND_THRESHOLD
        for text in RENDERED['bonus_round']:
            found = re.search(r'(\d+) or more', text)
            self.assertIsNotNone(found, f'bonus_round no longer states a threshold: {text}')
            self.assertEqual(
                int(found.group(1)), want,
                f'text promises {found.group(1)} but _BONUS_ROUND_THRESHOLD is {want} — '
                f'a user hitting the advertised number gets paid nothing')

    def testNoEffectNamesAStaleHandSize(self):
        """The lineup is six slots plus FLEX and has moved before. Text that hardcodes
        'your other N cards' goes stale silently."""
        for eff, (detail, tooltip) in RENDERED.items():
            for text in (detail, tooltip):
                self.assertIsNone(
                    re.search(r'your other \d+ cards', text),
                    f'{eff} hardcodes a hand size: {text}')


class ReadableCopy(unittest.TestCase):
    def testNoRawPythonStructuresOnTheCardFace(self):
        for eff, (detail, tooltip) in RENDERED.items():
            for text in (detail, tooltip):
                self.assertIsNone(re.search(r'\[\s*\d+\s*,', text),
                                  f'{eff} renders a list literal: {text}')
                for junk in ('None', 'True', 'False', '{', '}'):
                    self.assertNotIn(junk, text, f'{eff} leaks {junk!r}: {text}')

    def testDetailAndTooltipDoNotContradictOnNumbers(self):
        """⚠️ Updraft's detail said 299/391/483 and its tooltip said 300/400/500. A
        tooltip may be vaguer than the detail; it may not state DIFFERENT figures."""
        for eff, (detail, tooltip) in RENDERED.items():
            dn = set(re.findall(r'\b(\d{2,4})\b', detail))
            tn = set(re.findall(r'\b(\d{2,4})\b', tooltip))
            self.assertFalse(
                tn - dn - {'20', '10'},   # "inside the 20" / "inside the 10" are field spots
                f'{eff} tooltip states numbers the detail does not: '
                f'{sorted(tn - dn)}\n  D: {detail}\n  T: {tooltip}')

    def testNoEmOrEnDashesInUserFacingCopy(self):
        for eff, (detail, tooltip) in RENDERED.items():
            for text in (detail, tooltip):
                self.assertNotIn('—', text, f'{eff} uses an em-dash: {text}')
                self.assertNotIn('–', text, f'{eff} uses an en-dash: {text}')

    def testKnownGarbledPhrasingsStayFixed(self):
        banned = {
            "team's RB": 'garbled possessive',
            'WR counts either': 'sentence fragment',
            'Every grow': 'not English',
            'escalating odds at': 'parses as odds AT a value, not a chance OF one',
        }
        for eff, (detail, tooltip) in RENDERED.items():
            for text in (detail, tooltip):
                for phrase, why in banned.items():
                    self.assertNotIn(phrase, text, f'{eff} ({why}): {text}')

    def testEveryMintableEffectHasBothADetailAndATooltip(self):
        for eff, (detail, tooltip) in RENDERED.items():
            self.assertTrue(detail.strip(), f'{eff} has no detail line')
            self.assertTrue(tooltip.strip(), f'{eff} has no tooltip')

    def testDetailLinesStayShortEnoughToRead(self):
        """The detail is the always-visible rule text on the card face. Past roughly two
        lines it stops being read."""
        for eff, (detail, _) in RENDERED.items():
            self.assertLess(len(detail), 210,
                            f'{eff} detail is {len(detail)} chars: {detail}')


if __name__ == '__main__':
    unittest.main(verbosity=2)
