"""A card's text must not ask for a number the card was never minted with.

⚠️ THE TEXT AND THE PARAMS ARE EDITED SEPARATELY AND SHIP SEPARATELY. Effect values are
frozen at mint and templates are minted once a season, so an effect whose text starts
asking for a NEW key leaves every already-minted card unable to fill it — and
`_renderTemplate` prints `?` where the number belongs. That is what a reader sees.

Both live cases, found in production on 764 templates:

  honor_roll  — the rework added `baseMult` (clearing the bar should pay something) and
                the detail started asking for `{baseDelta}`. 10 of 10 minted templates
                read "+? FPx once this player reaches 15 FP". Worse than cosmetic:
                `_computeHonorRoll` falls back to `baseMult = 1.0`, so those cards were
                still paying nothing at the bar — the exact behavior the rework removed.
  gunslinger  — re-pointed from pass yards onto well-placed throws. The compute was
                updated (with a legacy fallback) and the builder now mints
                `perGoodThrowFP`, but BOTH texts were left describing the retired
                mechanic, so the detail asked for `{perHundredYardsFP}` — a key nothing
                mints any more — and described a mechanic the card no longer scores.

The rule this pins: for every effect, the placeholders in its CURRENT tooltip and detail
must be fillable from what its CURRENT builder mints (plus the `*Delta` variants
`buildEffectConfig` synthesises). It cannot catch a card minted under older params — that
is what `_backfillEffectParams` is for — but it stops the next one being introduced.

Run: .venv/bin/python test_effect_placeholders.py
"""

import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import managers  # noqa: F401  — breaks the floosball_game circular import
from managers.cardEffects import (EFFECT_DETAIL_TEMPLATES, EFFECT_TOOLTIPS,
                                  EFFECT_EDITION_TIER, buildEffectConfig)

PLACEHOLDER = re.compile(r'\{([a-zA-Z_]+)\}')

# Synthesised by buildEffectConfig from a full-multiplier field, so a template may use
# them without the builder returning them. Keep in step with `_FULL_MULT_FIELDS` in
# connection.py and the delta block in buildEffectConfig.
DERIVED = {
    'xMultValue': 'xMultDelta', 'baseXMult': 'baseXDelta', 'baseMult': 'baseDelta',
    'enhancedMult': 'enhancedDelta', 'maxMult': 'maxDelta', 'q4MultFactor': 'q4MultDelta',
    'rewardValue': 'rewardDelta', 'baseReward': 'baseRewardDelta',
}
# Filled from the effect's own `stat`, not from a param of its own.
ALWAYS_AVAILABLE = {'statDisplay', 'posLabel'}

POSITIONS = (1, 2, 3, 4, 5)


# A rating high enough to clear every edition's threshold, so the mint is never
# refused for being under the bar (diamond wants 90).
MINT_RATING = 95


def _mintedKeys(effectName, edition, position):
    """Every key a freshly minted card of this effect could fill, or None if this
    effect/position/edition combination does not mint."""
    try:
        cfg = buildEffectConfig(edition, MINT_RATING, position, forceEffect=effectName)
    except Exception:
        return None
    primary = (cfg or {}).get('primary') or {}
    keys = set(primary.keys()) | ALWAYS_AVAILABLE
    for full, delta in DERIVED.items():
        if full in primary:
            keys.add(delta)
    return keys


class EffectPlaceholderTests(unittest.TestCase):
    def testEveryPlaceholderCanBeFilledByTheBuilder(self):
        """THE RULE. A template may only ask for what its effect mints."""
        offenders = []
        for effectName, edition in sorted(EFFECT_EDITION_TIER.items()):
            text = f"{EFFECT_TOOLTIPS.get(effectName, '')} {EFFECT_DETAIL_TEMPLATES.get(effectName, '')}"
            wanted = set(PLACEHOLDER.findall(text))
            if not wanted:
                continue
            # An effect is minted per position; a key only has to exist for the
            # positions that actually mint it.
            fillable = set()
            minted = False
            for position in POSITIONS:
                keys = _mintedKeys(effectName, edition, position)
                if keys is None:
                    continue
                minted = True
                fillable |= keys
            if not minted:
                continue
            missing = sorted(wanted - fillable)
            if missing:
                offenders.append(f'{effectName} ({edition}): text wants {missing}, '
                                 f'builder mints {sorted(fillable - ALWAYS_AVAILABLE)}')
        self.assertEqual(offenders, [],
                         'card text asks for a param the effect never mints — a reader '
                         'sees "?" where the number goes:\n' + '\n'.join(offenders))

    def testTheTwoReportedEffectsResolve(self):
        """Pin the two by name, so neither regresses quietly."""
        for effectName in ('honor_roll', 'gunslinger'):
            edition = EFFECT_EDITION_TIER[effectName]
            wanted = set(PLACEHOLDER.findall(
                f"{EFFECT_TOOLTIPS.get(effectName, '')} {EFFECT_DETAIL_TEMPLATES.get(effectName, '')}"))
            fillable = set()
            for position in POSITIONS:
                keys = _mintedKeys(effectName, edition, position)
                if keys:
                    fillable |= keys
            self.assertEqual(sorted(wanted - fillable), [], effectName)

    def testGunslingerDescribesTheStatItScores(self):
        """It scores well-placed throws. Both texts said passing yards, which is the
        stat it was re-pointed AWAY from (that one is Slipstream's now)."""
        for text in (EFFECT_TOOLTIPS['gunslinger'], EFFECT_DETAIL_TEMPLATES['gunslinger']):
            self.assertNotIn('passing yards', text.lower(), text)
            self.assertIn('well-placed', text.lower(), text)

    def testHonorRollBackfillReproducesTheMintFormula(self):
        """The backfill has to hand an old card the number it would have been minted
        with, not a fresh guess — `rebuildPrimaryParams` works off the raw rating and
        would not reproduce the mint-time dampening."""
        from database.connection import _backfillEffectParams
        from managers.cardEffects import HONOR_ROLL_BASE_SHARE
        for maxMult in (1.26, 1.30, 1.42, 1.55):
            primary = {'rewardType': 'mult', 'maxMult': maxMult, 'fpThreshold': 15}
            self.assertTrue(_backfillEffectParams(primary, 'honor_roll'))
            self.assertEqual(primary['baseMult'],
                             round(1 + (maxMult - 1) * HONOR_ROLL_BASE_SHARE, 2))
        # Idempotent, and it never overwrites a value a card was minted with.
        minted = {'maxMult': 1.30, 'baseMult': 1.99}
        self.assertFalse(_backfillEffectParams(minted, 'honor_roll'))
        self.assertEqual(minted['baseMult'], 1.99)


if __name__ == '__main__':
    unittest.main(verbosity=2)
